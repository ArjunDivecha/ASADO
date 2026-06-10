#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: collect_optimizer_returns.py
=============================================================================

DESCRIPTION:
    Ingests monthly factor-return outputs from the three T2 optimizer pipelines
    (Econ, T2 Style, GDELT) into the ASADO tidy-panel layer. Each pipeline
    contributes two slices:

      1. factor_returns        -- date x factor monthly portfolio return (no country axis)
      2. factor_top20_membership -- date x country x factor weights (sparse, weight > 0)

    Joining membership ⨝ returns on (date, factor, source) gives genuine
    country-level attribution: which countries were in the bucket x the
    bucket's return.

    Resilience:
      - Each source wrapped in try/except. If one optimizer file is
        unreadable, the corresponding slice in the existing parquet panel is
        preserved unchanged.
      - 24-hour cache: skips re-melt when source file mtime is older than the
        existing parquet's mtime. --force bypasses.
      - Timestamped backup of both panels before overwrite.

INPUT FILES:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/econ/Econ_Optimizer.xlsx
        Wide monthly returns of top-20% portfolios. Sheet
        "Monthly_Net_Returns". First column: Date. Remaining columns: factor
        names suffixed with _CS or _TS.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/econ/Econ_Top_20_Exposure.csv
        Wide membership weights. Columns: Date, Country, then one column per
        factor variant. Cell value = portfolio weight (1/N when country is in
        the top-20% bucket for that factor that month, 0 otherwise).
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/t2/T2_Optimizer.xlsx
        Same layout as Econ_Optimizer.xlsx, from the T2 Style pipeline.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/t2/T2_Top_20_Exposure.csv
        Same layout as Econ_Top_20_Exposure.csv, from the T2 Style pipeline.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/gdelt/GDELT_Optimizer.xlsx
        Same layout as Econ_Optimizer.xlsx, from the GDELT pipeline.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/gdelt/GDELT_Top_20_Exposure.csv
        Same layout as Econ_Top_20_Exposure.csv, from the GDELT pipeline.

OUTPUT FILES:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/processed/factor_returns_panel.parquet
        Tidy long format: (date, factor, value, source). factor names retain
        _CS / _TS suffix (treated as separate variables). value = monthly net
        return of the top-20% portfolio.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/processed/factor_top20_membership_panel.parquet
        Tidy long format: (date, country, factor, weight, source). Sparse:
        only rows where weight > 0 are stored.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/processed/run_history.json
        Append-only record of last 24 runs (success/failure per source).
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/logs/collect_optimizer_returns_<timestamp>.log
        Log file created by the logging module on each run.

VERSION: 1.0
LAST UPDATED: 2026-06-05
AUTHOR: Arjun Divecha

DEPENDENCIES:
    - pandas
    - openpyxl
    - pyarrow

USAGE:
    python scripts/collect_optimizer_returns.py
    python scripts/collect_optimizer_returns.py --force
    python scripts/collect_optimizer_returns.py --dry-run

NOTES:
    - Factor names retain their _CS / _TS suffix; they are separate
      variables, not normalizations of one another (the construction rule
      differs).
    - All dates aligned to first-of-month.
    - T2 Style asymmetry: some factors only exist as _CS, others only as
      _TS. The schema allows that -- no enforcement of paired rows.
    - Source files live under /A Complete/, outside the ASADO repo. They are
      read in place; nothing is copied.
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Data"
PROCESSED_DIR = DATA_DIR / "processed"
BACKUP_DIR = DATA_DIR / "backups"
LOG_DIR = DATA_DIR / "logs"
RUN_HISTORY_PATH = PROCESSED_DIR / "run_history.json"

RETURNS_PQ = PROCESSED_DIR / "factor_returns_panel.parquet"
MEMBERSHIP_PQ = PROCESSED_DIR / "factor_top20_membership_panel.parquet"

for d in [PROCESSED_DIR, BACKUP_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)


SOURCES: List[Dict[str, Any]] = [
    {
        "key": "econ_optimizer",
        "returns_xlsx": Path(
            "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/econ/Econ_Optimizer.xlsx"
        ),
        "exposure_csv": Path(
            "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/econ/Econ_Top_20_Exposure.csv"
        ),
    },
    {
        "key": "t2_optimizer",
        "returns_xlsx": Path(
            "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/t2/T2_Optimizer.xlsx"
        ),
        "exposure_csv": Path(
            "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/t2/T2_Top_20_Exposure.csv"
        ),
    },
    {
        "key": "gdelt_optimizer",
        "returns_xlsx": Path(
            "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/gdelt/GDELT_Optimizer.xlsx"
        ),
        "exposure_csv": Path(
            "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/gdelt/GDELT_Top_20_Exposure.csv"
        ),
    },
]


def setup_logging() -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = LOG_DIR / f"collect_optimizer_returns_{timestamp}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_path)],
        force=True,
    )
    return log_path


def first_of_month(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series).dt.to_period("M").dt.to_timestamp()


def melt_returns(df: pd.DataFrame, source_key: str) -> pd.DataFrame:
    if "Date" not in df.columns:
        raise ValueError(f"[{source_key}] Returns sheet missing 'Date' column")
    df = df.dropna(subset=["Date"]).copy()
    long = (
        df.melt(id_vars="Date", var_name="factor", value_name="value")
        .dropna(subset=["value"])
    )
    long["date"] = first_of_month(long["Date"])
    long["factor"] = long["factor"].astype(str).str.strip()
    long["value"] = long["value"].astype(float)
    long["source"] = source_key
    long = long[(long["factor"].str.endswith("_CS")) | (long["factor"].str.endswith("_TS"))]
    return long[["date", "factor", "value", "source"]].reset_index(drop=True)


def melt_membership(df: pd.DataFrame, source_key: str) -> pd.DataFrame:
    if "Date" not in df.columns or "Country" not in df.columns:
        raise ValueError(f"[{source_key}] Exposure CSV missing 'Date' or 'Country' column")
    df = df.dropna(subset=["Date", "Country"]).copy()
    long = (
        df.melt(id_vars=["Date", "Country"], var_name="factor", value_name="weight")
        .dropna(subset=["weight"])
    )
    long = long[long["weight"] > 0]
    long["date"] = first_of_month(long["Date"])
    long["country"] = long["Country"].astype(str).str.strip()
    long["factor"] = long["factor"].astype(str).str.strip()
    long["weight"] = long["weight"].astype(float)
    long["source"] = source_key
    long = long[(long["factor"].str.endswith("_CS")) | (long["factor"].str.endswith("_TS"))]
    return long[["date", "country", "factor", "weight", "source"]].reset_index(drop=True)


def is_cache_fresh(source_file: Path, output_file: Path) -> bool:
    if not source_file.exists() or not output_file.exists():
        return False
    return source_file.stat().st_mtime <= output_file.stat().st_mtime


def collect_one_source(spec: Dict[str, Any]) -> Dict[str, Any]:
    """Load returns + membership for one optimizer source. Returns dataframes or None."""
    key = spec["key"]
    xlsx = spec["returns_xlsx"]
    csv = spec["exposure_csv"]
    result: Dict[str, Any] = {
        "source": key,
        "returns": None,
        "membership": None,
        "status": "ok",
        "error": None,
        "returns_rows": 0,
        "membership_rows": 0,
        "factors": 0,
        "countries": 0,
        "date_min": None,
        "date_max": None,
    }

    if not xlsx.exists():
        result["status"] = "missing_returns_file"
        result["error"] = f"missing: {xlsx}"
        logging.warning(f"[{key}] {result['error']}")
        return result
    if not csv.exists():
        result["status"] = "missing_exposure_file"
        result["error"] = f"missing: {csv}"
        logging.warning(f"[{key}] {result['error']}")
        return result

    try:
        logging.info(f"[{key}] reading returns: {xlsx.name}")
        returns_wide = pd.read_excel(xlsx, sheet_name="Monthly_Net_Returns")
        logging.info(f"[{key}] reading exposure: {csv.name}")
        membership_wide = pd.read_csv(csv)

        result["returns"] = melt_returns(returns_wide, key)
        result["membership"] = melt_membership(membership_wide, key)

        result["returns_rows"] = len(result["returns"])
        result["membership_rows"] = len(result["membership"])
        result["factors"] = result["returns"]["factor"].nunique()
        result["countries"] = result["membership"]["country"].nunique()
        if not result["returns"].empty:
            result["date_min"] = str(result["returns"]["date"].min().date())
            result["date_max"] = str(result["returns"]["date"].max().date())

        logging.info(
            f"[{key}] OK — returns={result['returns_rows']:,} "
            f"membership={result['membership_rows']:,} "
            f"factors={result['factors']} countries={result['countries']} "
            f"dates {result['date_min']}..{result['date_max']}"
        )
    except Exception as exc:
        result["status"] = "error"
        result["error"] = str(exc)
        logging.exception(f"[{key}] failed to ingest: {exc}")

    return result


def merge_with_existing(
    new_slice: Optional[pd.DataFrame],
    existing: Optional[pd.DataFrame],
    source_key: str,
) -> Optional[pd.DataFrame]:
    """Replace this source's slice in the existing panel with the new slice.

    If new_slice is None (source failed), return the existing slice unchanged.
    If existing is None (no prior panel), just return new_slice.
    """
    if existing is None or existing.empty:
        return new_slice
    preserved = existing[existing["source"] != source_key]
    if new_slice is None:
        return existing
    if new_slice.empty:
        return preserved.reset_index(drop=True) if not preserved.empty else preserved
    return pd.concat([preserved, new_slice], ignore_index=True)


def load_existing(path: Path) -> Optional[pd.DataFrame]:
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception as exc:
        logging.warning(f"[panel] could not read existing {path.name}: {exc}")
        return None


def backup_outputs(timestamp: str) -> None:
    targets = [RETURNS_PQ, MEMBERSHIP_PQ]
    backup_subdir = BACKUP_DIR / timestamp
    backup_subdir.mkdir(parents=True, exist_ok=True)
    for path in targets:
        if path.exists():
            shutil.copy2(path, backup_subdir / path.name)
            logging.info(f"[backup] {path.name} -> backups/{timestamp}/")


def append_run_history(entry: Dict[str, Any], keep: int = 24) -> None:
    history: List[Dict[str, Any]] = []
    if RUN_HISTORY_PATH.exists():
        try:
            history = json.loads(RUN_HISTORY_PATH.read_text())
            if not isinstance(history, list):
                history = []
        except Exception:
            history = []
    history.append(entry)
    history = history[-keep:]
    tmp = RUN_HISTORY_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(history, indent=2, default=str))
    tmp.replace(RUN_HISTORY_PATH)


def write_panel(df: pd.DataFrame, path: Path, sort_cols: List[str]) -> None:
    df = df.sort_values(sort_cols).reset_index(drop=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(path)
    logging.info(f"[write] {path.name}: {len(df):,} rows -> {path}")


def summarize(df: pd.DataFrame, label: str) -> None:
    if df is None or df.empty:
        logging.info(f"[summary] {label}: EMPTY")
        return
    n_factors = df["factor"].nunique()
    n_sources = df["source"].nunique()
    date_min = pd.to_datetime(df["date"]).min().date()
    date_max = pd.to_datetime(df["date"]).max().date()
    msg = (
        f"[summary] {label}: rows={len(df):,} "
        f"factors={n_factors} sources={n_sources} "
        f"dates {date_min}..{date_max}"
    )
    if "country" in df.columns:
        msg += f" countries={df['country'].nunique()}"
    logging.info(msg)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ASADO Optimizer Returns Collector — ingests factor returns + top-20 membership."
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Bypass mtime cache and re-melt all sources",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Read and summarize; do not write parquet outputs",
    )
    args = parser.parse_args()

    log_path = setup_logging()
    logging.info("=" * 60)
    logging.info("ASADO Optimizer Returns Collector")
    logging.info(f"force={args.force} dry_run={args.dry_run}")
    logging.info(f"log: {log_path}")
    logging.info("=" * 60)

    start = time.time()

    existing_returns = load_existing(RETURNS_PQ)
    existing_membership = load_existing(MEMBERSHIP_PQ)
    if existing_returns is not None:
        logging.info(f"existing factor_returns_panel: {len(existing_returns):,} rows")
    if existing_membership is not None:
        logging.info(f"existing factor_top20_membership_panel: {len(existing_membership):,} rows")

    per_source_status: List[Dict[str, Any]] = []
    new_returns = existing_returns
    new_membership = existing_membership
    any_changed = False

    for spec in SOURCES:
        key = spec["key"]
        cache_ok = (
            not args.force
            and is_cache_fresh(spec["returns_xlsx"], RETURNS_PQ)
            and is_cache_fresh(spec["exposure_csv"], MEMBERSHIP_PQ)
            and existing_returns is not None
            and existing_membership is not None
            and (existing_returns["source"] == key).any()
            and (existing_membership["source"] == key).any()
        )
        if cache_ok:
            logging.info(f"[{key}] cache fresh — skipping re-melt")
            per_source_status.append({
                "source": key, "status": "skipped_cache_fresh", "error": None
            })
            continue

        result = collect_one_source(spec)
        per_source_status.append({
            "source": key,
            "status": result["status"],
            "error": result["error"],
            "returns_rows": result["returns_rows"],
            "membership_rows": result["membership_rows"],
            "factors": result["factors"],
            "countries": result["countries"],
            "date_min": result["date_min"],
            "date_max": result["date_max"],
        })

        if result["status"] != "ok":
            logging.warning(
                f"[{key}] preserved existing slice (if any) due to status={result['status']}"
            )
            continue

        new_returns = merge_with_existing(result["returns"], new_returns, key)
        new_membership = merge_with_existing(result["membership"], new_membership, key)
        any_changed = True

    summarize(new_returns, "factor_returns_panel (final)")
    summarize(new_membership, "factor_top20_membership_panel (final)")

    if args.dry_run:
        logging.info("dry-run: no writes")
    elif not any_changed:
        logging.info("no source changed — leaving existing panels in place")
    else:
        timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
        backup_outputs(timestamp)
        if new_returns is not None and not new_returns.empty:
            write_panel(new_returns, RETURNS_PQ, sort_cols=["date", "source", "factor"])
        if new_membership is not None and not new_membership.empty:
            write_panel(
                new_membership, MEMBERSHIP_PQ,
                sort_cols=["date", "source", "country", "factor"],
            )

    elapsed = time.time() - start
    entry = {
        "script": "collect_optimizer_returns.py",
        "timestamp": datetime.now().isoformat(),
        "elapsed_sec": round(elapsed, 2),
        "force": args.force,
        "dry_run": args.dry_run,
        "sources": per_source_status,
        "returns_rows": int(len(new_returns)) if new_returns is not None else 0,
        "membership_rows": int(len(new_membership)) if new_membership is not None else 0,
    }
    if not args.dry_run:
        append_run_history(entry)
    logging.info(f"done in {elapsed:.1f}s")

    failed = [s for s in per_source_status if s["status"] not in ("ok", "skipped_cache_fresh")]
    if failed and (new_returns is None or new_membership is None):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
