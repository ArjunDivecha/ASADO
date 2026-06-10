"""
=============================================================================
SCRIPT NAME: scripts/collect_gdelt_deep.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/GDELT/Deep/data/features/
    country_signal_monthly_deep_treated.parquet
    (32,067 rows × 1,169 cols; 31 T2-relevant ISO3s × 133 months Feb 2015 – Apr 2026)
- config/country_mapping.json — provides T2 name → ISO3 (and implicit ISO3 → T2 fan-out)

OUTPUT FILES:
- Data/processed/gdelt_deep_panel.parquet — tidy long format
    (date, country, value, variable, source). Post-prune (2026-06) only the
    curated keep-list survives (see scripts/gdelt_keep_list.py); variables use
    their canonical (<=31-char) names:
      gdelt_deep_theme   — 48 vars (24 curated themes × {_share, _share_delta})
      gdelt_deep_event   — 16 vars (curated CAMEO/Goldstein event aggregates)
      gdelt_deep_gcam    — DROPPED (all GCAM emotional dictionaries removed)
- Data/backups/{ts}/gdelt_deep_panel.parquet — timestamped backup before overwrite
- Data/processed/run_history.json — appended with run metadata

VERSION: 1.0
LAST UPDATED: 2026-04-27
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
Ingests the GDELT Deep treated monthly panel into ASADO tidy format.

Per the warehouse-ingest plan in docs/gdelt_deep_ingest_plan.md, this collector:
  1. Loads country_signal_monthly_deep_treated.parquet (treated, EWMA + z).
  2. Filters to the 1,086 truly-new feature columns (theme_*, gcam_*, event_*).
     Drops upstream raw tone vars (sentiment_*, attention_*, risk_*, etc.) which
     are already in gdelt_panel as _CS / _TS variants.
  3. Filters to the 31 T2-relevant ISO3 codes derived from country_mapping.json.
  4. Fans ISO3 → T2 names: USA → 3 buckets (NASDAQ, U.S., US SmallCap),
     CHN → 2 buckets (ChinaA, ChinaH), all others 1:1.
  5. Converts dates: signal_month_end_date + 1 day = first of next month.
     Verified by spearman rank corr = 1.000 against existing gdelt_panel.
  6. Melts to tidy long format and tags each variable with its source family.
  7. Writes parquet, backs up the prior version, appends run_history.json.

DEPENDENCIES:
- pandas, numpy, pyarrow

USAGE:
  python scripts/collect_gdelt_deep.py            # incremental: append only
                                                  # months not already present
  python scripts/collect_gdelt_deep.py --force    # full rebuild from source
  python scripts/collect_gdelt_deep.py --dry-run  # validate, no writes

NOTES:
- Default behavior is INCREMENTAL: if Data/processed/gdelt_deep_panel.parquet
  exists, only month rows newer than the existing max date are read from the
  source parquet, melted, and appended. Past months are never re-read or
  re-written. If source has no new months, the script exits with status
  "no_change" without touching the parquet. --force triggers a full rebuild.
- This collector ONLY produces the parquet. Loading into DuckDB
  (gdelt_deep_factors table) is a separate stage in
  scripts/load_gdelt_deep_to_duckdb.py.
- Does NOT touch feature_panel view. Per the plan, normalization is
  decided as a separate stage before the table is unioned in.
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

# Canonical GDELT Deep keep-list — same prune rule as build_gdelt_panel.py so
# the orphan gdelt_deep_factors table never re-accumulates gcam / theme-tail.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from gdelt_keep_list import canonical_name, keep_deep_feature  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Data"
PROCESSED_DIR = DATA_DIR / "processed"
BACKUP_DIR = DATA_DIR / "backups"
CONFIG_DIR = BASE_DIR / "config"
LOG_DIR = DATA_DIR / "logs"

DEEP_PARQUET = Path(
    "/Users/arjundivecha/Dropbox/AAA Backup/A Working/GDELT/"
    "Deep/data/features/country_signal_monthly_deep_treated.parquet"
)
COUNTRY_MAPPING_JSON = CONFIG_DIR / "country_mapping.json"
OUT_PARQUET = PROCESSED_DIR / "gdelt_deep_panel.parquet"
RUN_HISTORY_JSON = PROCESSED_DIR / "run_history.json"

for d in (PROCESSED_DIR, BACKUP_DIR, LOG_DIR):
    d.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_DIR / f"collect_gdelt_deep_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
    ],
)
logger = logging.getLogger(__name__)


def load_iso3_to_t2() -> dict[str, list[str]]:
    """Build ISO3 → list[T2] fan-out map from country_mapping.json.

    Result: USA → [NASDAQ, U.S., US SmallCap], CHN → [ChinaA, ChinaH],
    all 29 other ISO3s map to a single T2 name.
    """
    with open(COUNTRY_MAPPING_JSON) as f:
        cm = json.load(f)
    iso3_to_t2: dict[str, list[str]] = {}
    for t2_name, props in cm["countries"].items():
        iso3 = props.get("iso3")
        if not iso3:
            continue
        iso3_to_t2.setdefault(iso3, []).append(t2_name)
    logger.info("Loaded ISO3→T2 mapping: %d unique ISO3s, %d T2 names",
                len(iso3_to_t2), sum(len(v) for v in iso3_to_t2.values()))
    return iso3_to_t2


META_COLS = {
    "signal_month", "signal_month_end_date", "date", "month_end_date_used",
    "country_iso3", "country_name", "country_code_gdelt",
    "month_obs_count", "month_calendar_days", "month_obs_share",
    "month_day_status_worst", "month_gkg_fetch_share_mean", "month_gkg_fetch_share_min",
}


def classify_column(col: str) -> str | None:
    """Return source tag for a Deep column, or None to drop.

    Post-prune (2026-06): only keep-list deep features survive (see
    scripts/gdelt_keep_list.py). All gcam_* and the theme tail are dropped.

    - kept theme_*  → gdelt_deep_theme
    - kept event_*  → gdelt_deep_event
    - everything else (gcam_*, theme tail, raw tone, composites, metadata) → drop
    """
    if not keep_deep_feature(col):
        return None
    if col.startswith("theme_"):
        return "gdelt_deep_theme"
    if col.startswith("event_"):
        return "gdelt_deep_event"
    return None


def build_tidy(df: pd.DataFrame, iso3_to_t2: dict[str, list[str]]) -> pd.DataFrame:
    """Convert wide Deep panel → tidy ASADO long format."""
    # 1. Keep only the truly-new feature columns plus the keys we need.
    feature_cols = [c for c in df.columns if classify_column(c) is not None]
    logger.info("Feature columns kept: %d (theme=%d, gcam=%d, event=%d)",
                len(feature_cols),
                sum(c.startswith("theme_") for c in feature_cols),
                sum(c.startswith("gcam_") for c in feature_cols),
                sum(c.startswith("event_") for c in feature_cols))

    # 2. Filter to T2-relevant ISO3s.
    in_scope = df["country_iso3"].isin(iso3_to_t2.keys())
    df = df.loc[in_scope, ["signal_month_end_date", "country_iso3", *feature_cols]].copy()
    logger.info("Rows after ISO3 filter: %d (31 T2-relevant ISO3s)", len(df))

    # 3. Date convention: signal_month_end_date + 1 day = first of next month.
    #    Verified rank-corr = 1.000 against existing gdelt_panel attention_fast_CS.
    df["date"] = pd.to_datetime(df["signal_month_end_date"]) + pd.Timedelta(days=1)
    # All conversions land on first-of-month because signal_month_end_date is always
    # the last calendar day. Sanity-check.
    assert (df["date"].dt.day == 1).all(), "date conversion did not produce first-of-month"

    # 4. Fan ISO3 → T2 by exploding (one input row → 1, 2, or 3 output rows).
    df["country"] = df["country_iso3"].map(iso3_to_t2)
    df = df.explode("country", ignore_index=True)
    logger.info("Rows after ISO3→T2 fan-out: %d", len(df))

    # 5. Melt features to long.
    long = df.melt(
        id_vars=["date", "country"],
        value_vars=feature_cols,
        var_name="variable",
        value_name="value",
    )
    # Drop NaN values (frequent in early months for many themes / gcam dims).
    n_before = len(long)
    long = long.dropna(subset=["value"]).reset_index(drop=True)
    logger.info("Rows after melt + NaN-drop: %d (%.1f%% retained)",
                len(long), 100 * len(long) / max(n_before, 1))

    # 6. Tag source (using the original upstream column name), then rename the
    #    variable to its canonical (<=31-char, collision-free) warehouse name so
    #    gdelt_deep_factors shares vocabulary with gdelt_panel.
    long["source"] = long["variable"].map(classify_column)
    assert long["source"].notna().all(), "unmapped variable encountered"
    long["variable"] = long["variable"].map(canonical_name)

    # 7. Final canonical column order + dtypes.
    long["date"] = pd.to_datetime(long["date"]).dt.date
    long["country"] = long["country"].astype(str)
    long["variable"] = long["variable"].astype(str)
    long["source"] = long["source"].astype(str)
    long["value"] = pd.to_numeric(long["value"], errors="coerce")
    long = long.dropna(subset=["value"]).reset_index(drop=True)
    return long[["date", "country", "value", "variable", "source"]]


def backup_existing(target: Path) -> Path | None:
    if not target.exists():
        return None
    ts = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    backup = BACKUP_DIR / ts / target.name
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(target, backup)
    logger.info("Backed up prior parquet → %s", backup)
    return backup


def append_run_history(out_path: Path, n_rows: int, n_vars: int,
                       elapsed_s: float, status: str) -> None:
    history = []
    if RUN_HISTORY_JSON.exists():
        try:
            with open(RUN_HISTORY_JSON) as f:
                history = json.load(f)
        except json.JSONDecodeError:
            history = []
    if not isinstance(history, list):
        history = []
    history.append({
        "timestamp": datetime.now().isoformat(),
        "collector": "collect_gdelt_deep",
        "status": status,
        "n_rows": int(n_rows),
        "n_variables": int(n_vars),
        "elapsed_seconds": round(elapsed_s, 2),
        "output": str(out_path),
    })
    history = history[-24:]  # keep last 24 runs
    with open(RUN_HISTORY_JSON, "w") as f:
        json.dump(history, f, indent=2)


def cache_is_fresh(path: Path, hours: int = 24) -> bool:
    if not path.exists():
        return False
    age_s = time.time() - path.stat().st_mtime
    return age_s < hours * 3600


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--force", action="store_true",
                    help="Full rebuild from source, ignoring any existing parquet.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate the pipeline without writing the parquet.")
    args = ap.parse_args()

    t0 = time.time()

    if not DEEP_PARQUET.exists():
        logger.error("Source parquet missing: %s", DEEP_PARQUET)
        return 2

    iso3_to_t2 = load_iso3_to_t2()

    # Incremental path: append only months not already present.
    # Past months never re-read; --force overrides for full rebuild.
    incremental = OUT_PARQUET.exists() and not args.force
    schema_names = pq.ParquetFile(DEEP_PARQUET).schema_arrow.names
    feature_cols = [c for c in schema_names if classify_column(c) is not None]
    needed_cols = ["signal_month_end_date", "country_iso3", *feature_cols]

    if incremental:
        existing = pd.read_parquet(OUT_PARQUET)
        existing["date"] = pd.to_datetime(existing["date"]).dt.date
        max_existing_date = pd.to_datetime(existing["date"].max())
        # Existing dates are first-of-next-month; the underlying source
        # signal_month_end_date is one day prior.
        max_existing_sme = max_existing_date - pd.Timedelta(days=1)
        logger.info("Existing parquet present: %d rows, max date = %s",
                    len(existing), max_existing_date.date())

        # Read source schema & filter rows beyond what we already have.
        logger.info("Reading new months from %s ...", DEEP_PARQUET)
        df = pd.read_parquet(DEEP_PARQUET, columns=needed_cols)
        df["signal_month_end_date"] = pd.to_datetime(df["signal_month_end_date"])
        new_mask = df["signal_month_end_date"] > max_existing_sme
        n_new_rows = int(new_mask.sum())

        if n_new_rows == 0:
            logger.info("No new months in source. Already up to date.")
            append_run_history(OUT_PARQUET, len(existing),
                               existing["variable"].nunique(),
                               time.time() - t0, "no_change")
            return 0

        df = df.loc[new_mask].copy()
        new_dates = sorted(df["signal_month_end_date"].dt.to_period("M").unique())
        logger.info("Source has %d new month(s) beyond existing: %s",
                    len(new_dates), [str(d) for d in new_dates])
        logger.info("Building tidy delta from %d source rows ...", len(df))
        new_tidy = build_tidy(df, iso3_to_t2)

        # Merge: append new rows, drop any accidental duplicates keeping new.
        merged = pd.concat([existing, new_tidy], ignore_index=True)
        before = len(merged)
        merged = merged.drop_duplicates(
            subset=["date", "country", "variable"], keep="last"
        ).reset_index(drop=True)
        n_dupes_dropped = before - len(merged)
        if n_dupes_dropped:
            logger.warning("Dropped %d duplicate rows after merge (kept newer)",
                           n_dupes_dropped)

        tidy = merged
        n_added = len(merged) - len(existing)
        logger.info("Merged: %d → %d rows (+%d new)", len(existing), len(merged), n_added)
    else:
        if args.force:
            logger.info("--force: full rebuild from source.")
        else:
            logger.info("No existing parquet — initial full build.")
        logger.info("Reading %s ...", DEEP_PARQUET)
        df = pd.read_parquet(DEEP_PARQUET, columns=needed_cols)
        logger.info("Loaded raw panel: %d rows × %d cols", *df.shape)
        tidy = build_tidy(df, iso3_to_t2)

    # Sanity checks before write
    assert tidy[["date", "country", "variable"]].duplicated().sum() == 0, "duplicate (date, country, variable)"
    assert set(tidy["source"].unique()) <= {"gdelt_deep_theme", "gdelt_deep_gcam", "gdelt_deep_event"}, "unexpected source"
    n_t2 = tidy["country"].nunique()
    assert n_t2 == 34, f"expected 34 T2 countries, got {n_t2}"

    n_vars = tidy["variable"].nunique()
    by_source = tidy.groupby("source")["variable"].nunique().to_dict()
    date_min, date_max = tidy["date"].min(), tidy["date"].max()
    logger.info("Tidy panel: %d rows, %d unique variables", len(tidy), n_vars)
    logger.info("  by source: %s", by_source)
    logger.info("  date range: %s → %s (%d unique months)",
                date_min, date_max, tidy["date"].nunique())
    logger.info("  countries: %d (%s)", n_t2, sorted(tidy["country"].unique())[:5] + ["..."])

    if args.dry_run:
        logger.info("--dry-run: not writing.")
        return 0

    backup_existing(OUT_PARQUET)
    tidy.to_parquet(OUT_PARQUET, index=False)
    elapsed = time.time() - t0
    logger.info("Wrote %s (%.1f MB, %.1fs)",
                OUT_PARQUET, OUT_PARQUET.stat().st_size / 1e6, elapsed)
    append_run_history(OUT_PARQUET, len(tidy), n_vars, elapsed,
                       "ok_incremental" if incremental else "ok_full")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
