"""
=============================================================================
SCRIPT NAME: scripts/strategy/analogs/pit_audit.py
=============================================================================

INPUT FILES:
- Data/asado.duckdb :: feature_panel             — full normalized panel.

OUTPUT FILES:
- Data/strategy/analogs/v1/pit_audit.csv         — one row per variable.

VERSION: 1.0
LAST UPDATED: 2026-04-19
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
Audits every variable that v1 might consume (the _CS family by default) for
point-in-time safety. Outputs a CSV that downstream worldstate construction
filters against — only variables flagged vintage_safe = True are admitted.

EXCLUSION RULES (PRD §6.3):
- Forecast variables: prefix IMF_WEO_ or BBG_ECFC_ (revised by vintage).
  Excluded outright in v1; phase 2 may admit with a vintage archive.
- Annual-only variables with long reporting lag: UNDP HDI, ND-GAIN.
  Admitted only with a year-lag treatment, flagged needs_year_lag=True.
- Variables with > 40% missingness across their stated coverage window:
  excluded.
- GDELT partial-month rows: GDELT publishes mid-month-to-date values; the
  worldstate builder must drop the latest incomplete month for any GDELT
  variable. Flagged as gdelt_partial_month_caveat=True.

PIT SAFETY OF _CS DENOMINATORS (PRD §12, open question #4):
Confirmed by inspection of build_normalized_panel.py::_build_cross_sectional —
z-scores are computed per (variable, source, date) using ONLY the same-date
cross-section. No future data leaks into the denominator. _CS is PIT-safe
unless the underlying raw value itself is revised (which is what the
IMF_WEO / BBG_ECFC exclusions cover separately).

DEPENDENCIES:
- duckdb, pandas

USAGE:
  python scripts/strategy/analogs/pit_audit.py            # write pit_audit.csv
  python scripts/strategy/analogs/pit_audit.py --check    # re-read & summarize

NOTES:
- Audit is deterministic: same DuckDB → same CSV.
=============================================================================
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.strategy.analogs import config as C  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

MISSINGNESS_THRESHOLD = 0.40

FORECAST_PREFIXES = ("IMF_WEO_", "BBG_ECFC_")
ANNUAL_LAG_PATTERNS = ("UNDP_HDI", "NDGAIN", "ND_GAIN")
GDELT_SOURCE = "gdelt"


def gather_variable_stats(con: duckdb.DuckDBPyConnection, prefix: str) -> pd.DataFrame:
    """For every variable matching the prefix filter, compute coverage stats.

    Returns one row per (variable, source) since the same variable name can
    appear under multiple sources (rare but possible in feature_panel).
    """
    sql = f"""
        SELECT
            variable,
            source,
            MIN(date) AS first_date,
            MAX(date) AS last_date,
            COUNT(DISTINCT date) AS n_dates,
            COUNT(DISTINCT country) AS n_countries,
            COUNT(*) AS n_obs
        FROM feature_panel
        WHERE variable LIKE ?
        GROUP BY variable, source
        ORDER BY variable, source
    """
    df = con.execute(sql, [f"%{prefix}"]).df()
    df["first_date"] = pd.to_datetime(df["first_date"])
    df["last_date"] = pd.to_datetime(df["last_date"])
    return df


def compute_missingness(row: pd.Series) -> float:
    """Approximate missingness over the variable's own coverage window.

    months_in_window × n_countries(observed) gives the maximum possible
    observation count; we compare against the actual count.
    """
    if pd.isna(row["first_date"]) or pd.isna(row["last_date"]):
        return 1.0
    months = (
        (row["last_date"].year - row["first_date"].year) * 12
        + (row["last_date"].month - row["first_date"].month)
        + 1
    )
    expected = months * max(row["n_countries"], 1)
    if expected <= 0:
        return 1.0
    return max(0.0, 1.0 - row["n_obs"] / expected)


def classify(df: pd.DataFrame) -> pd.DataFrame:
    """Apply exclusion rules. Returns df with vintage_safe + reason columns."""
    df = df.copy()
    df["missingness"] = df.apply(compute_missingness, axis=1)

    df["is_forecast_variable"] = df["variable"].apply(
        lambda v: any(v.startswith(p) for p in FORECAST_PREFIXES)
    )
    df["needs_year_lag"] = df["variable"].apply(
        lambda v: any(p in v.upper() for p in ANNUAL_LAG_PATTERNS)
    )
    df["gdelt_partial_month_caveat"] = df["source"].str.lower() == GDELT_SOURCE
    df["high_missingness"] = df["missingness"] > MISSINGNESS_THRESHOLD

    reasons: list[str] = []
    safe: list[bool] = []
    for _, r in df.iterrows():
        why: list[str] = []
        if r["is_forecast_variable"]:
            why.append("forecast_variable")
        if r["high_missingness"]:
            why.append(f"missingness>{MISSINGNESS_THRESHOLD:.0%}")
        # year-lag and GDELT caveats are admissible — flagged but not excluded.
        is_safe = len(why) == 0
        safe.append(is_safe)
        reasons.append(";".join(why) if why else "ok")

    df["vintage_safe"] = safe
    df["exclusion_reason"] = reasons
    df["notes"] = df.apply(_compose_notes, axis=1)
    return df


def _compose_notes(row: pd.Series) -> str:
    notes: list[str] = []
    if row["needs_year_lag"]:
        notes.append("apply_year_lag")
    if row["gdelt_partial_month_caveat"]:
        notes.append("drop_partial_current_month_in_worldstate")
    if not row["vintage_safe"]:
        notes.append("excluded_from_v1")
    return ";".join(notes)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="Read existing pit_audit.csv and print summary")
    ap.add_argument("--prefix", default=C.FEATURE_PREFIX,
                    help="Variable suffix to audit (default: _CS)")
    args = ap.parse_args()

    C.ensure_dirs()

    if args.check:
        df = pd.read_csv(C.PIT_AUDIT_CSV)
    else:
        with duckdb.connect(str(C.DUCKDB_PATH), read_only=True) as con:
            stats = gather_variable_stats(con, args.prefix)
        df = classify(stats)
        cols = [
            "variable", "source", "first_date", "last_date", "n_dates",
            "n_countries", "n_obs", "missingness",
            "is_forecast_variable", "needs_year_lag",
            "gdelt_partial_month_caveat", "high_missingness",
            "vintage_safe", "exclusion_reason", "notes",
        ]
        df = df[cols]
        df.to_csv(C.PIT_AUDIT_CSV, index=False)
        logger.info("Wrote %s (%d rows)", C.PIT_AUDIT_CSV, len(df))

    n_total = len(df)
    n_safe = int(df["vintage_safe"].sum())
    n_excl = n_total - n_safe
    logger.info("Audit summary: %d variables / %d safe / %d excluded", n_total, n_safe, n_excl)

    if n_excl:
        breakdown = df.loc[~df["vintage_safe"], "exclusion_reason"].value_counts()
        logger.info("Exclusion breakdown:")
        for reason, count in breakdown.items():
            logger.info("  %4d  %s", count, reason)

    n_year_lag = int(df["needs_year_lag"].sum())
    n_gdelt = int(df["gdelt_partial_month_caveat"].sum())
    logger.info("Caveats: year_lag=%d, gdelt_partial=%d", n_year_lag, n_gdelt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
