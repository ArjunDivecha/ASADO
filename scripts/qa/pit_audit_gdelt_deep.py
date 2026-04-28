"""
=============================================================================
SCRIPT NAME: scripts/qa/pit_audit_gdelt_deep.py
=============================================================================

INPUT FILES:
- Data/asado.duckdb :: gdelt_deep_factors      — raw treated Deep variables
- Data/asado.duckdb :: gdelt_deep_factors_cs   — _CS-treated variants

OUTPUT FILES:
- Data/processed/pit_audit_gdelt_deep.csv      — one row per (variable, source)
    with vintage_safe / exclusion_reason / notes columns.

VERSION: 1.0
LAST UPDATED: 2026-04-27
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
PIT-safety audit for the GDELT Deep variables. Mirrors the rules from the
v1 worldstate audit (see docs/strategy/analogs/v1/go_no_go.md §3 for context):

EXCLUSION RULES:
  - Forecast variables (IMF_WEO_*, BBG_ECFC_* prefixes) — N/A for Deep.
  - Annual-only with long reporting lag (UNDP_HDI, ND-GAIN) — N/A for Deep.
  - Missingness > 40% over the variable's coverage window — excluded.
  - GDELT partial-month caveat: Deep is built from month-end snapshots,
    so this is informational only, not exclusionary.

Z-score based variants (gcam_*_z, event_*_z, etc.) ARE PIT-safe by
construction in the Deep pipeline (trailing within-country window shifted
by 1 month — see Deep.md §"No Look-Ahead Guarantee"). The _CS variants
produced by build_gdelt_deep_cs.py use only same-date cross-section, also
PIT-safe (confirmed in v1 pit_audit § for _CS denominators).

DEPENDENCIES:
- duckdb, pandas

USAGE:
  python scripts/qa/pit_audit_gdelt_deep.py            # write audit CSV
  python scripts/qa/pit_audit_gdelt_deep.py --check    # read & summarize existing
=============================================================================
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import duckdb
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "Data"
DUCKDB_PATH = DATA_DIR / "asado.duckdb"
OUT_CSV = DATA_DIR / "processed" / "pit_audit_gdelt_deep.csv"
OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

MISSINGNESS_THRESHOLD = 0.40
RAW_TABLE = "gdelt_deep_factors"
CS_TABLE = "gdelt_deep_factors_cs"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def gather_stats(con: duckdb.DuckDBPyConnection, table: str) -> pd.DataFrame:
    df = con.execute(f"""
        SELECT
            variable,
            source,
            MIN(date) AS first_date,
            MAX(date) AS last_date,
            COUNT(DISTINCT date) AS n_dates,
            COUNT(DISTINCT country) AS n_countries,
            COUNT(*) AS n_obs
        FROM {table}
        GROUP BY variable, source
        ORDER BY source, variable
    """).df()
    df["first_date"] = pd.to_datetime(df["first_date"])
    df["last_date"] = pd.to_datetime(df["last_date"])
    df["table"] = table
    return df


def compute_missingness(row: pd.Series) -> float:
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
    df = df.copy()
    df["missingness"] = df.apply(compute_missingness, axis=1)
    df["is_forecast_variable"] = False  # N/A for Deep
    df["needs_year_lag"] = False        # N/A for Deep
    df["gdelt_partial_month_caveat"] = df["source"].str.startswith("gdelt")
    df["high_missingness"] = df["missingness"] > MISSINGNESS_THRESHOLD

    reasons, safe = [], []
    for _, r in df.iterrows():
        why = []
        if r["high_missingness"]:
            why.append(f"missingness>{MISSINGNESS_THRESHOLD:.0%}")
        is_safe = len(why) == 0
        safe.append(is_safe)
        reasons.append(";".join(why) if why else "ok")

    df["vintage_safe"] = safe
    df["exclusion_reason"] = reasons
    df["notes"] = df.apply(_compose_notes, axis=1)
    return df


def _compose_notes(row: pd.Series) -> str:
    notes = []
    if row["gdelt_partial_month_caveat"]:
        notes.append("month_end_snapshot_clean")  # Deep aggregates by signal_month_end_date
    if not row["vintage_safe"]:
        notes.append("excluded_by_missingness")
    return ";".join(notes)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="Read existing CSV and summarize.")
    args = ap.parse_args()

    if args.check:
        df = pd.read_csv(OUT_CSV)
    else:
        with duckdb.connect(str(DUCKDB_PATH), read_only=True) as con:
            raw = gather_stats(con, RAW_TABLE)
            cs = gather_stats(con, CS_TABLE)
        combined = pd.concat([raw, cs], ignore_index=True)
        df = classify(combined)
        cols = [
            "variable", "source", "table", "first_date", "last_date",
            "n_dates", "n_countries", "n_obs", "missingness",
            "is_forecast_variable", "needs_year_lag",
            "gdelt_partial_month_caveat", "high_missingness",
            "vintage_safe", "exclusion_reason", "notes",
        ]
        df = df[cols]
        df.to_csv(OUT_CSV, index=False)
        logger.info("Wrote %s (%d rows)", OUT_CSV, len(df))

    n_total = len(df)
    n_safe = int(df["vintage_safe"].sum())
    n_excl = n_total - n_safe
    logger.info("Audit summary: %d (variable, source, table) / %d safe / %d excluded",
                n_total, n_safe, n_excl)

    by_table = df.groupby(["table", "source"]).agg(
        n_total=("variable", "count"),
        n_safe=("vintage_safe", "sum"),
    )
    by_table["n_excluded"] = by_table["n_total"] - by_table["n_safe"]
    logger.info("Breakdown:\n%s", by_table.to_string())

    if n_excl:
        breakdown = df.loc[~df["vintage_safe"], "exclusion_reason"].value_counts()
        logger.info("Top exclusion reasons:")
        for reason, count in breakdown.items():
            logger.info("  %4d  %s", count, reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
