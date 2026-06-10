#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/gdelt_normalize_daily.py
=============================================================================

DESCRIPTION:
    DAILY analog of gdelt_normalize.py. Reads the DAILY GDELT signal workbook
    (GDELT_DAILY.xlsx, produced from the GKG source by the GDELT ingest) and
    produces tidy _CS/_TS normalized daily GDELT factors, plus the daily 1DRet
    country-return series. Reuses the exact GDELT normalize helpers (CS/TS
    z-scores, sign-flip prefixes, country mapping) — the only difference from
    monthly is the metronome: daily dates (no month collapse) and 1DRet instead
    of 1MRet.

INPUT FILES:
    - GDELT_DAILY.xlsx (--gdelt; default: ASADO Data/gdelt/spreadsheet/GDELT_DAILY.xlsx)
    - Data/work/t2_daily/Normalized_T2_MasterCSV.csv  (for the 1DRet series)

OUTPUT FILES:
    - Data/work/gdelt_daily/GDELT_Factors_MasterCSV.csv  (tidy: date,country,variable,value)

VERSION: 1.0
LAST UPDATED: 2026-06-09
AUTHOR: Arjun Divecha (ported by Claude Code)

DEPENDENCIES: pandas, numpy, openpyxl

USAGE:
    python scripts/gdelt_normalize_daily.py
    python scripts/gdelt_normalize_daily.py --gdelt PATH --t2csv PATH --out PATH
=============================================================================
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

import gdelt_normalize as gn   # reuse helpers (same scripts/ dir on sys.path)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
GDELT_DAILY_DIR = BASE_DIR / "Data" / "work" / "gdelt_daily"
DEFAULT_GDELT = BASE_DIR / "Data" / "gdelt" / "spreadsheet" / "GDELT_DAILY.xlsx"
DEFAULT_T2CSV = BASE_DIR / "Data" / "work" / "t2_daily" / "Normalized_T2_MasterCSV.csv"
DEFAULT_OUT = GDELT_DAILY_DIR / "GDELT_Factors_MasterCSV.csv"

METRONOME_SHEET = "daily_metronome"


def _load_1dret_long(t2csv: Path) -> pd.DataFrame:
    csv = pd.read_csv(t2csv)
    csv = csv.rename(columns={c: c.lower() for c in csv.columns if c.lower() == "date"})
    csv["date"] = pd.to_datetime(csv["date"], errors="coerce")
    ret = csv[csv["variable"] == "1DRet"][["date", "country", "variable", "value"]].copy()
    ret["country"] = ret["country"].astype(str)
    return ret


def _window(gdelt_path: Path):
    df = pd.read_excel(str(gdelt_path), sheet_name=METRONOME_SHEET, engine="openpyxl")
    dates = pd.to_datetime(df.iloc[:, 0], errors="coerce")
    has = df.iloc[:, 1:].notna().any(axis=1)
    start = pd.Timestamp(dates.loc[has[has].index[0]]).normalize()
    return start, pd.Timestamp(dates.max()).normalize()


def main() -> int:
    ap = argparse.ArgumentParser(description="Daily GDELT normalize -> tidy factor CSV.")
    ap.add_argument("--gdelt", default=str(DEFAULT_GDELT))
    ap.add_argument("--t2csv", default=str(DEFAULT_T2CSV))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    gdelt_path = Path(args.gdelt)
    if not gdelt_path.exists():
        logger.error("GDELT_DAILY workbook not found: %s", gdelt_path)
        return 1
    out_path = Path(args.out); out_path.parent.mkdir(parents=True, exist_ok=True)

    xl = pd.ExcelFile(str(gdelt_path), engine="openpyxl")
    data_sheets = [s for s in xl.sheet_names if s not in gn.GDELT_SKIP_SHEETS]
    all_parts, loaded = [], []
    for sheet in data_sheets:
        df = pd.read_excel(xl, sheet_name=sheet, engine="openpyxl")
        if df.empty or df.shape[1] < 2:
            continue
        df = df.rename(columns={df.columns[0]: "date"})
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        # DAILY: no month collapse (monthly version does .dt.to_period('M'))
        df = df.rename(columns={c: gn.map_country_label(c) for c in df.columns if c != "date"})
        wide = df.set_index("date")
        wide.index.name = "date"
        wide = wide.apply(pd.to_numeric, errors="coerce")
        if gn._should_flip(sheet):
            wide = wide * -1.0
        all_parts.extend(gn._sheet_to_long_variants(sheet, wide))
        loaded.append(sheet)

    if not all_parts:
        logger.error("No GDELT sheets produced tidy data.")
        return 1
    ret = _load_1dret_long(Path(args.t2csv)) if Path(args.t2csv).exists() else pd.DataFrame(
        columns=["date", "country", "variable", "value"])
    combined = pd.concat([pd.concat(all_parts, ignore_index=True), ret], ignore_index=True)
    win_s, win_e = _window(gdelt_path)
    combined["date"] = pd.to_datetime(combined["date"], errors="coerce")
    combined = combined.dropna(subset=["date"])
    combined = combined[(combined["date"] >= win_s) & (combined["date"] <= win_e)]
    combined = combined.sort_values(["date", "variable", "country"]).reset_index(drop=True)
    combined.to_csv(out_path, index=False)
    logger.info("Wrote %s (%d rows, %d vars, window %s..%s)",
                out_path, len(combined), combined["variable"].nunique(), win_s.date(), win_e.date())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
