"""
=============================================================================
SCRIPT NAME: scripts/t2_normalize.py
=============================================================================

INPUT FILES:
- T2 Master.xlsx (produced by build_t2_master.py from the Bloomberg master).
  Default location: the T2 Factor Timing Fuzzy directory (build_t2_master
  writes it there). One sheet per factor; rows = dates, cols = countries.

OUTPUT FILES:
- Normalized_T2_MasterCSV.csv — tidy long (date, country, value, variable).
  variable = {Factor}_CS / {Factor}_TS, or the raw return name for return
  sheets. This is the file setup_duckdb.py loads for t2_master / t2_raw.
- Normalized_T2_Master.xlsx — wide per-variant workbook (optional, --no-xlsx
  to skip).

VERSION: 1.0
LAST UPDATED: 2026-06-04
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
ASADO-internal port of "T2 Factor Timing Fuzzy/Step Two Create Normalized
Tidy.py" — makes ASADO standalone for T2 normalization (no external Step Two
run). Logic is a faithful copy: per factor sheet, cross-sectional (per-date)
and time-series (per-country expanding) z-scores; the ~21 "lower-is-better"
factors are sign-flipped after normalization; return sheets are kept raw.

DEPENDENCIES: pandas, numpy, openpyxl, xlsxwriter

USAGE:
  python scripts/t2_normalize.py                 # read default T2 Master.xlsx
  python scripts/t2_normalize.py --master PATH   # custom T2 Master.xlsx
  python scripts/t2_normalize.py --out-dir DIR   # custom output dir
  python scripts/t2_normalize.py --no-xlsx       # skip the wide xlsx output

NOTES:
- N-1 std (pandas default); TS uses an expanding window; std==0 -> 0.
- Faithful to the external Step Two so output matches Normalized_T2_MasterCSV.csv.
=============================================================================
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import List

import numpy as np
import pandas as pd

# build_t2_master.py writes T2 Master.xlsx into these dirs; the Fuzzy copy is
# the canonical T2 input and the dir setup_duckdb reads Normalized_T2_MasterCSV
# from today.
T2_FUZZY_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/t2")
T2_DAILY_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy Daily")
DEFAULT_MASTER = T2_FUZZY_DIR / "T2 Master.xlsx"
DEFAULT_OUT_DIR = T2_FUZZY_DIR

# Daily frequency uses daily return sheets + a slightly different invert list
# (faithful to "T2 Factor Timing Fuzzy Daily/Step Two Create Normalized Tidy.py").
COPY_DIRECT_DAILY = ["1DRet", "5DRet", "20DRet", "60DRet", "120DRet"]
INVERT_NORM_DAILY = [
    "Best Cash Flow", "Best PBK", "Best PE ", "Best Price Sales",
    "EV to EBITDA", "Shiller PE", "Trailing PE", "Positive PE ",
    "Currency Change", "Debt to GDP", "REER", "RSI14", "10Yr Bond 12",
    "Advance Decline", "Advance_Decline_15", "Debt To EV",
    "Bloom Country Risk", "Bond Yield Change", "120MA Signal", "Mcap Weights",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SKIP_SHEETS: List[str] = ["README", "Sheet1"]
COPY_DIRECT: List[str] = ["1MRet", "3MRet", "6MRet", "9MRet", "12MRet"]
# Lower-is-better factors: normalization multiplied by -1 (higher = better).
INVERT_NORM: List[str] = [
    "Best Cash Flow",
    "Best PBK", "Best PE ", "Best Price Sales",
    "EV to EBITDA", "Shiller PE", "Trailing PE", "Positive PE ",
    "Currency Change", "Debt to GDP", "REER", "RSI14", "10Yr Bond 12",
    "Advance Decline", "1MTR", "3MTR", "Debt To EV", "Best Price Sales",
    "Bloom Country Risk", "Bond Yield Change",
]


def _truncate_sheet_name(name: str, max_length: int = 31) -> str:
    if len(name) <= max_length:
        return name
    for suffix in ["_CS", "_Global", "_TS"]:
        if name.endswith(suffix):
            base = name[: -len(suffix)]
            trunc_length = max_length - len(suffix) - 1
            return f"{base[:trunc_length]}{suffix}"
    return name[:max_length]


def _create_tidy_df(df: pd.DataFrame, variable: str, normalization: str) -> pd.DataFrame:
    tidy_df = df.reset_index().melt(id_vars=["date"], var_name="country", value_name="value")
    if normalization != "Original":
        tidy_df["variable"] = f"{variable}_{normalization}"
    else:
        tidy_df["variable"] = variable
    return tidy_df[["date", "country", "value", "variable"]]


def normalize_data(master_path: Path, out_dir: Path, write_xlsx: bool = True,
                   copy_direct: List[str] | None = None,
                   invert_norm: List[str] | None = None, freq: str = "monthly") -> Path:
    """Port of Step Two. Returns the path to the written CSV.

    copy_direct / invert_norm default to the monthly lists; pass the daily
    lists for the daily pipeline. freq controls date alignment: 'monthly'
    collapses to first-of-month; 'daily' keeps the trading-day stamp.
    """
    copy_direct = COPY_DIRECT if copy_direct is None else copy_direct
    invert_norm = INVERT_NORM if invert_norm is None else invert_norm
    if not master_path.exists():
        raise FileNotFoundError(f"T2 Master not found: {master_path}")
    out_dir.mkdir(parents=True, exist_ok=True)
    xls = pd.ExcelFile(str(master_path))
    excel_output = out_dir / "Normalized_T2_Master.xlsx"
    csv_output = out_dir / "Normalized_T2_MasterCSV.csv"

    all_tidy_data: List[pd.DataFrame] = []
    writer = pd.ExcelWriter(str(excel_output), engine="xlsxwriter") if write_xlsx else None
    try:
        for sheet_name in xls.sheet_names:
            if sheet_name in SKIP_SHEETS:
                continue
            df = xls.parse(sheet_name)
            original_date_column = df.columns[0]
            df.rename(columns={original_date_column: "date"}, inplace=True)
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df.dropna(subset=["date"], inplace=True)
            if freq == "daily":
                df["date"] = df["date"].dt.normalize()
            else:
                df["date"] = df["date"].dt.to_period("M").dt.to_timestamp()
            df.set_index("date", inplace=True)

            variants = {}
            if sheet_name in copy_direct:
                variants["Original"] = df.copy()
            else:
                cs_df = df.copy()
                cs_means = cs_df.mean(axis=1)
                cs_stds = cs_df.std(axis=1)
                cs_norm = (cs_df.subtract(cs_means, axis=0)).divide(cs_stds, axis=0)
                if sheet_name in invert_norm:
                    cs_norm = -1 * cs_norm
                variants["CS"] = cs_norm

                ts_norm = pd.DataFrame(index=df.index, columns=df.columns)
                for country in df.columns:
                    country_data = df[country].copy()
                    ts_mean = country_data.expanding().mean()
                    ts_std = country_data.expanding().std()
                    ts_norm[country] = np.where(
                        ts_std == 0, 0, (country_data - ts_mean) / ts_std
                    )
                if sheet_name in invert_norm:
                    ts_norm = -1 * ts_norm
                variants["TS"] = ts_norm

            for variant_type, variant_df in variants.items():
                if write_xlsx:
                    if sheet_name in copy_direct:
                        safe = _truncate_sheet_name(sheet_name)
                    else:
                        safe = _truncate_sheet_name(f"{sheet_name}_{variant_type}")
                    variant_df.to_excel(writer, sheet_name=safe)
                all_tidy_data.append(_create_tidy_df(variant_df, sheet_name, variant_type))
    finally:
        if writer is not None:
            writer.close()

    combined_tidy = pd.concat(all_tidy_data, ignore_index=True)
    combined_tidy.to_csv(csv_output, index=False)
    logger.info("Wrote %s (%d rows, %d variables)",
                csv_output, len(combined_tidy), combined_tidy["variable"].nunique())
    return csv_output


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--freq", choices=["monthly", "daily"], default="monthly",
                    help="monthly (default) or daily T2 pipeline")
    ap.add_argument("--master", type=Path, default=None, help="Path to T2 Master.xlsx")
    ap.add_argument("--out-dir", type=Path, default=None, help="Output directory")
    ap.add_argument("--no-xlsx", action="store_true", help="Skip the wide xlsx output")
    args = ap.parse_args()
    if args.freq == "daily":
        master = args.master or (T2_DAILY_DIR / "T2 Master.xlsx")
        out_dir = args.out_dir or T2_DAILY_DIR
        normalize_data(master, out_dir, write_xlsx=not args.no_xlsx,
                       copy_direct=COPY_DIRECT_DAILY, invert_norm=INVERT_NORM_DAILY, freq="daily")
    else:
        master = args.master or DEFAULT_MASTER
        out_dir = args.out_dir or DEFAULT_OUT_DIR
        normalize_data(master, out_dir, write_xlsx=not args.no_xlsx)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
