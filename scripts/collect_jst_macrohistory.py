#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/collect_jst_macrohistory.py
=============================================================================

DESCRIPTION:
Ingests the Jordà-Schularick-Taylor (JST) Macrohistory Database — 150 years
of ANNUAL macro/financial data for 18 advanced economies (1870-2020) — into
ASADO as an ISOLATED long-cycle CALIBRATION CORPUS.

Why this exists (the design decision, 2026-06-15):
  ASADO's live factor surface starts ~2000 and is monthly. That window holds
  only ~3 true crises (2000, 2008, 2020) — far too few to calibrate regime
  transition behavior or once-in-a-century tail returns. JST supplies the
  missing tail population: ~65 banking-crisis onsets across the in-universe
  developed markets, plus Depressions, world wars and hyperinflations.

CRITICAL ARCHITECTURE RULE:
  JST is a CALIBRATION CORPUS, not a factor feed. It is ANNUAL and ends 2020.
  It is loaded into its OWN DuckDB table `jst_macrohistory` and is *never*
  unioned into `unified_panel` / `feature_panel` and *never* forward-filled to
  monthly. (Doing so would repeat the deprecated `wb_commodity_factor_panel`
  mistake: tiling static history across modern months, inflating variable
  counts and producing degenerate _CS variants.) Downstream calibration reads
  this annual panel offline and emits tiny prior/lookup tables; the live
  monthly system never touches the raw 150-year panel.

Scope (per user decision 2026-06-15): only the 13 JST countries that are in
ASADO's tradable 34-country universe are retained. The 5 JST-only DMs
(Belgium, Finland, Ireland, Norway, Portugal) are dropped here; if the tail
sample ever proves too thin they can be added back as a pooled robustness
overlay without entering the live universe.

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/raw/jst/JSTdatasetR6.xlsx
    Raw JST Release 6 workbook (single sheet 'Sheet1', 2718 rows x 59 cols).
    Downloaded from https://www.macrohistory.net/database/ (CC-licensed).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/country_mapping.json
    Used only to confirm iso3 for the 13 in-universe names (mapping itself is
    explicit in JST_TO_T2 below to avoid the USA->'US SmallCap' reverse-lookup
    ambiguity).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/processed/jst_macrohistory_panel.parquet
    Tidy ANNUAL panel: columns (date, year, country, iso3, variable, value, source).
    date = YYYY-12-01 (year-end annual convention). source = 'jst'.
    Isolated — loaded to DuckDB table `jst_macrohistory`, NOT unified_panel.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/backups/jst_macrohistory_panel_YYYY_MM_DD_HHMMSS.parquet
    Timestamped backup of the prior panel before any overwrite.

VERSION: 1.0
LAST UPDATED: 2026-06-15
AUTHOR: Claude Code for Arjun Divecha

DEPENDENCIES: pandas, openpyxl, pyarrow (ASADO venv).

USAGE:
  venv/bin/python scripts/collect_jst_macrohistory.py
  venv/bin/python scripts/collect_jst_macrohistory.py --refresh-download  # re-pull raw xlsx first

NOTES:
- JST is a STATIC historical release (R6 = 1870-2020). This is NOT a nightly
  collector; re-run only when macrohistory.net publishes a new release.
- Nominal returns are meaningless across hyperinflations (Germany 1923,
  eq_tr ~ 2.6e9). Real-return conversion happens downstream in the calibration
  step; this collector preserves raw JST values verbatim.
=============================================================================
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_XLSX = BASE_DIR / "Data" / "raw" / "jst" / "JSTdatasetR6.xlsx"
OUT_PARQUET = BASE_DIR / "Data" / "processed" / "jst_macrohistory_panel.parquet"
BACKUP_DIR = BASE_DIR / "Data" / "backups"
COUNTRY_MAP = BASE_DIR / "config" / "country_mapping.json"

# Stable JST R6 download (verified 2026-06-15 via macrohistory.net/database/).
JST_R6_XLSX_URL = (
    "https://www.macrohistory.net/app/download/9834512569/"
    "JSTdatasetR6.xlsx?t=1763503850"
)

# Explicit JST country-name -> ASADO T2 name for the 13 in-universe DMs.
# Explicit on purpose: an iso3 reverse-lookup picks 'US SmallCap'/'NASDAQ' for
# USA. JST is country-level macro, so USA -> the broad 'U.S.' index name.
JST_TO_T2 = {
    "Australia": "Australia",
    "Canada": "Canada",
    "Denmark": "Denmark",
    "France": "France",
    "Germany": "Germany",
    "Italy": "Italy",
    "Japan": "Japan",
    "Netherlands": "Netherlands",
    "Spain": "Spain",
    "Sweden": "Sweden",
    "Switzerland": "Switzerland",
    "UK": "U.K.",
    "USA": "U.S.",
}

# Identifier columns (carried through, not melted into variable/value).
ID_COLS = {"year", "country", "iso", "ifs"}
# Non-numeric descriptive columns we keep out of the tidy numeric panel.
DROP_COLS = {"peg_type", "peg_base"}


def maybe_download(refresh: bool) -> None:
    if refresh or not RAW_XLSX.exists():
        RAW_XLSX.parent.mkdir(parents=True, exist_ok=True)
        print(f"  Downloading JST R6 -> {RAW_XLSX}")
        urllib.request.urlretrieve(JST_R6_XLSX_URL, RAW_XLSX)
    if not RAW_XLSX.exists():
        raise FileNotFoundError(f"JST raw workbook missing: {RAW_XLSX}")


def backup_existing() -> None:
    if OUT_PARQUET.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y_%m_%d_%H%M%S")
        dest = BACKUP_DIR / f"jst_macrohistory_panel_{ts}.parquet"
        shutil.copy2(OUT_PARQUET, dest)
        print(f"  Backed up prior panel -> {dest}")


def build_panel() -> pd.DataFrame:
    raw = pd.read_excel(RAW_XLSX, sheet_name="Sheet1")
    iso3_ref = {
        name: m["iso3"].upper()
        for name, m in json.loads(COUNTRY_MAP.read_text())["countries"].items()
        if "iso3" in m
    }

    # Restrict to the 13 in-universe DMs and attach canonical T2 name.
    raw = raw[raw["country"].isin(JST_TO_T2)].copy()
    raw["t2_country"] = raw["country"].map(JST_TO_T2)
    raw["iso3"] = raw["iso"].str.upper()

    # Cross-check iso3 against country_mapping for the mapped names.
    for jst_name, t2 in JST_TO_T2.items():
        jst_iso = raw.loc[raw["country"] == jst_name, "iso3"].iloc[0]
        ref_iso = iso3_ref.get(t2)
        if ref_iso and ref_iso != jst_iso:
            raise ValueError(
                f"iso3 mismatch for {jst_name}->{t2}: JST={jst_iso} map={ref_iso}"
            )

    value_cols = [
        c for c in raw.columns
        if c not in ID_COLS and c not in DROP_COLS and c not in {"t2_country", "iso3"}
        and pd.api.types.is_numeric_dtype(raw[c])
    ]

    tidy = raw.melt(
        id_vars=["year", "t2_country", "iso3"],
        value_vars=value_cols,
        var_name="variable",
        value_name="value",
    ).dropna(subset=["value"])

    tidy = tidy.rename(columns={"t2_country": "country"})
    tidy["date"] = pd.to_datetime(tidy["year"].astype(int).astype(str) + "-12-01")
    tidy["source"] = "jst"
    tidy = tidy[["date", "year", "country", "iso3", "variable", "value", "source"]]
    tidy = tidy.sort_values(["country", "variable", "year"]).reset_index(drop=True)
    return tidy


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest JST Macrohistory R6 (annual calibration corpus).")
    ap.add_argument("--refresh-download", action="store_true",
                    help="Re-pull the raw xlsx from macrohistory.net before building.")
    args = ap.parse_args()

    print(f"{'='*64}\n  JST MACROHISTORY INGEST (annual calibration corpus)\n{'='*64}")
    maybe_download(args.refresh_download)
    tidy = build_panel()

    backup_existing()
    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    tidy.to_parquet(OUT_PARQUET, index=False)

    n_crisis = int(tidy[(tidy.variable == "crisisJST") & (tidy.value == 1)].shape[0])
    print(f"  countries: {tidy['country'].nunique()} (in-universe DMs)")
    print(f"  year span: {int(tidy['year'].min())}-{int(tidy['year'].max())}")
    print(f"  variables: {tidy['variable'].nunique()}")
    print(f"  rows: {len(tidy):,}")
    print(f"  banking-crisis onset-years (crisisJST==1): {n_crisis}")
    print(f"  -> {OUT_PARQUET}")
    print("  NOTE: isolated table — NOT unioned into unified_panel, NOT forward-filled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
