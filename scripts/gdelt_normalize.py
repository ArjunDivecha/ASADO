"""
=============================================================================
SCRIPT NAME: gdelt_normalize.py
=============================================================================

DESCRIPTION:
    Reads a GDELT factor workbook (GDELT.xlsx) and applies cross-sectional
    (CS) and time-series (TS) z-score normalization to each sheet. Applies
    sign-flip corrections for factors whose names match predefined prefixes
    (e.g., sentiment, tone). Merges a 1-month return series (1MRet) from
    a separate normalized CSV. Determines the analysis window from the
    "monthly_metronome" sheet in the GDELT workbook and clips all output
    to that date range. Writes the combined tidy long-format dataset and
    a factor categories workbook that additionally copies the Asset Class
    sheet from an external categories file.

INPUT FILES:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/gdelt/GDELT.xlsx
        Deep + curated GDELT factor workbook produced by build_gdelt_panel.py.
        Contains one sheet per factor: core signals, 24 curated themes, and
        16 events from the keep-list. Also read for the "monthly_metronome"
        sheet used to determine the analysis date window.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/gdelt/Normalized_T2_MasterCSV.csv
        Normalized T2 master CSV from which the 1MRet (1-month return) series
        is extracted and merged into the tidy output.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/gdelt/Step Factor Categories.xlsx
        External categories workbook whose "Asset Class" sheet is copied into
        the output categories file. Only accessed if the file exists; skipped
        with a warning otherwise.

OUTPUT FILES:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/gdelt/GDELT_Factors_MasterCSV.csv
        Tidy long-form dataset with columns: date, country, variable, value.
        Each input factor sheet produces two variables (_CS and _TS suffix
        for cross-sectional and time-series normalization). The 1MRet series
        is appended. All rows are clipped to the GDELT analysis window.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/gdelt/Step Factor Categories GDELT.xlsx
        Factor categories workbook with one row per _CS/_TS factor plus the
        Asset Class sheet copied from the input categories workbook.

VERSION: 1.0
LAST UPDATED: 2026-06-05
AUTHOR: Arjun Divecha

DEPENDENCIES:
    - pandas
    - numpy
    - openpyxl
    - xlsxwriter

USAGE:
    python gdelt_normalize.py            # default T2 GDELT dir
    python gdelt_normalize.py --dir DIR  # custom working dir

NOTES:
    - All default paths assume the T2 GDELT data directory at
      /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/gdelt.
    - The --dir flag overrides this for custom working directories.
    - Factor sign-flip logic is applied per-sheet based on prefix matching
      against a hardcoded set of prefixes (FLIP_PREFIXES).
=============================================================================
"""
from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

T2_GDELT_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/gdelt")
COUNTRY_MAPPING = Path(__file__).resolve().parent.parent / "config" / "country_mapping.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def _load_gdelt_to_t2(mapping_path: Path = COUNTRY_MAPPING) -> Dict[str, str]:
    """Build the {GDELT workbook label -> canonical T2 name} remap from the
    single source of truth (config/country_mapping.json). Only the few sleeves
    whose GDELT.xlsx column header differs from their T2 name carry a
    `gdelt_label` field (e.g. "China A" -> "ChinaA"); every other column is
    already canonical and maps to itself."""
    try:
        payload = json.loads(Path(mapping_path).read_text())
    except (OSError, ValueError) as exc:  # noqa: BLE001
        logger.warning("Could not load %s (%s); GDELT label remap is empty.", mapping_path, exc)
        return {}
    return {
        meta["gdelt_label"]: country
        for country, meta in payload.get("countries", {}).items()
        if meta.get("gdelt_label")
    }


GDELT_TO_T2_COUNTRY = _load_gdelt_to_t2()
GDELT_SKIP_SHEETS = frozenset({"README", "README_VARIABLES"})
NORMALIZED_T2_CSV = "Normalized_T2_MasterCSV.csv"
OUTPUT_CSV = "GDELT_Factors_MasterCSV.csv"
OUTPUT_CATEGORIES = "Step Factor Categories GDELT.xlsx"
T2_CATEGORIES_PATH = "Step Factor Categories.xlsx"

FLIP_PREFIXES = (
    "country_news_attention", "country_news_sentiment", "foreign_tone",
    "local_foreign_gap", "lf_gap", "local_tone", "metronome", "monthly_metronome",
    "sentiment", "tone_dispersion", "tone_mean", "tone_wavg",
)


def map_country_label(label: object) -> str:
    if label is None or (isinstance(label, float) and str(label) == "nan"):
        return ""
    s = str(label).strip()
    return GDELT_TO_T2_COUNTRY.get(s, s)


def _truncate_sheet_key(name: str, max_len: int = 80) -> str:
    s = str(name).strip()
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


def _infer_category(sheet_name: str) -> str:
    s = sheet_name.strip()
    return s.split("_")[0].title() if "_" in s else "GDELT"


def _should_flip(sheet_name: str) -> bool:
    lower = str(sheet_name).lower().strip()
    return any(lower.startswith(p) for p in FLIP_PREFIXES)


def _cs_normalize(df: pd.DataFrame) -> pd.DataFrame:
    cs_means = df.mean(axis=1)
    cs_stds = df.std(axis=1).replace(0, np.nan)
    return df.subtract(cs_means, axis=0).divide(cs_stds, axis=0).fillna(0.0)


def _ts_normalize(df: pd.DataFrame) -> pd.DataFrame:
    ts_norm = pd.DataFrame(index=df.index, columns=df.columns, dtype=float)
    for country in df.columns:
        cd = df[country].copy()
        ts_mean = cd.expanding().mean()
        ts_std = cd.expanding().std()
        ts_norm[country] = np.where(ts_std == 0, 0.0, (cd - ts_mean) / ts_std)
    return ts_norm.fillna(0.0)


def _sheet_to_long_variants(sheet_name: str, df_raw: pd.DataFrame) -> List[pd.DataFrame]:
    key = _truncate_sheet_key(sheet_name)
    parts: List[pd.DataFrame] = []
    for suffix, wide in {"CS": _cs_normalize(df_raw), "TS": _ts_normalize(df_raw)}.items():
        tidy = wide.reset_index().rename(columns={wide.reset_index().columns[0]: "date"})
        tidy = tidy.melt(id_vars=["date"], var_name="country", value_name="value")
        tidy["variable"] = f"{key}_{suffix}"
        parts.append(tidy[["date", "country", "variable", "value"]])
    return parts


def _load_1mret_long(work_dir: Path) -> pd.DataFrame:
    csv = pd.read_csv(work_dir / NORMALIZED_T2_CSV)
    lower = {c.lower(): c for c in csv.columns}
    col_date = lower.get("date", "date")
    csv = csv.rename(columns={col_date: "date"})
    csv["date"] = pd.to_datetime(csv["date"], errors="coerce")
    ret = csv[csv["variable"] == "1MRet"][["date", "country", "variable", "value"]].copy()
    ret["country"] = ret["country"].astype(str)
    ret["date"] = ret["date"].dt.to_period("M").dt.to_timestamp()
    return ret


def get_gdelt_analysis_window(gdelt_path: Path) -> Tuple[pd.Timestamp, pd.Timestamp]:
    df = pd.read_excel(str(gdelt_path), sheet_name="monthly_metronome", engine="openpyxl")
    dates = pd.to_datetime(df.iloc[:, 0], errors="coerce")
    has_data = df.iloc[:, 1:].notna().any(axis=1)
    first_row_label = has_data[has_data].index[0]
    start = pd.Timestamp(dates.loc[first_row_label]).normalize()
    end = pd.Timestamp(dates.max()).normalize()
    return start, end


def clip_long_format_dates(df: pd.DataFrame, start, end, date_col="date") -> pd.DataFrame:
    out = df.copy()
    out[date_col] = pd.to_datetime(out[date_col], errors="coerce")
    out = out.dropna(subset=[date_col])
    return out.loc[(out[date_col] >= start) & (out[date_col] <= end)]


def _write_factor_categories(work_dir: Path, sheet_names: List[str]) -> None:
    rows = []
    for sn in sheet_names:
        key, cat = _truncate_sheet_key(sn), _infer_category(sn)
        rows.append({"Factor Name": f"{key}_CS", "Category": cat, "Max": 1.0})
        rows.append({"Factor Name": f"{key}_TS", "Category": cat, "Max": 1.0})
    fc = pd.DataFrame(rows)
    cat_path = work_dir / T2_CATEGORIES_PATH
    if not cat_path.exists():
        logger.warning("Missing %s — skipping categories workbook.", cat_path)
        return
    asset = pd.read_excel(str(cat_path), sheet_name="Asset Class", engine="openpyxl")
    with pd.ExcelWriter(str(work_dir / OUTPUT_CATEGORIES), engine="openpyxl", mode="w") as w:
        fc.to_excel(w, sheet_name="Factor Categories", index=False)
        asset.to_excel(w, sheet_name="Asset Class", index=False)


def normalize_gdelt(work_dir: Path) -> Path:
    gdelt_path = work_dir / "GDELT.xlsx"
    if not gdelt_path.exists():
        raise FileNotFoundError(gdelt_path)
    xl = pd.ExcelFile(str(gdelt_path), engine="openpyxl")
    data_sheets = [s for s in xl.sheet_names if s not in GDELT_SKIP_SHEETS]
    all_parts, sheets_loaded = [], []
    for sheet in data_sheets:
        df = pd.read_excel(xl, sheet_name=sheet, engine="openpyxl")
        if df.empty or df.shape[1] < 2:
            continue
        df = df.rename(columns={df.columns[0]: "date"})
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"])
        df["date"] = df["date"].dt.to_period("M").dt.to_timestamp()
        df = df.rename(columns={c: map_country_label(c) for c in df.columns if c != "date"})
        wide = df.set_index("date")
        wide.index.name = "date"
        wide = wide.apply(pd.to_numeric, errors="coerce")
        if _should_flip(sheet):
            wide = wide * -1.0
        all_parts.extend(_sheet_to_long_variants(sheet, wide))
        sheets_loaded.append(sheet)
    if not all_parts:
        raise ValueError("No GDELT sheets produced tidy data.")
    combined = pd.concat([pd.concat(all_parts, ignore_index=True), _load_1mret_long(work_dir)],
                         ignore_index=True)
    win_s, win_e = get_gdelt_analysis_window(gdelt_path)
    combined = clip_long_format_dates(combined, win_s, win_e, date_col="date")
    combined = combined.sort_values(["date", "variable", "country"]).reset_index(drop=True)
    out = work_dir / OUTPUT_CSV
    combined.to_csv(out, index=False)
    logger.info("Wrote %s (%d rows, %d vars, window %s..%s)",
                out, len(combined), combined["variable"].nunique(), win_s.date(), win_e.date())
    _write_factor_categories(work_dir, sheets_loaded)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=Path, default=T2_GDELT_DIR)
    args = ap.parse_args()
    normalize_gdelt(args.dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
