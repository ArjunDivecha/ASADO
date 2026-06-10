"""
=============================================================================
SCRIPT NAME: scripts/econ_normalize.py
=============================================================================

INPUT FILES (default: A Complete/T2 Econ dir):
- Econ.xlsx  (built in-repo by build_econ_panel.py from unified_panel; one sheet
  per macro factor, post redundancy-prune)
- Normalized_T2_MasterCSV.csv  (for the 1MRet return series)

OUTPUT FILES (same dir):
- Econ_Factors_MasterCSV.csv  (tidy long: date, country, variable, value;
  level _CS/_TS + selected _D12 _CS/_TS + 1MRet), clipped to the overlap of the
  (publication-lagged) Econ window and the T2 return window.
- Step Factor Categories Econ.xlsx

VERSION: 1.0
LAST UPDATED: 2026-06-04
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
ASADO-internal port of "T2 Econ/Step Two Econ Create Tidy.py" — makes ASADO
standalone for Econ monthly normalization. Faithful copy of the macro-specific
logic: causal monthly fill for quarterly/annual panels, +1-month publication
lag, cross-country dispersion gate, level + calendar-D12 CS/TS variants, sign
flips, 1MRet merge, and the (lagged-source ∩ return) window clip. Window helpers
inlined from "Step T2_Econ_analysis_window.py". Output matches the external
Econ_Factors_MasterCSV.csv.

DEPENDENCIES: pandas, numpy, openpyxl

USAGE:
  python scripts/econ_normalize.py            # default T2 Econ dir
  python scripts/econ_normalize.py --dir DIR
=============================================================================
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd

T2_ECON_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/econ")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SOURCE_SKIP_SHEETS = frozenset({"INDEX", "README", "README_VARIABLES"})
SKIP_WINDOW_SHEETS = frozenset({"INDEX", "README", "README_VARIABLES"})
WINDOW_ANCHOR_SHEET = "monthly_metronome"
SOURCE_SIGNAL_LAG_MONTHS = 1
NORMALIZED_T2_CSV = "Normalized_T2_MasterCSV.csv"
OUTPUT_CSV = "Econ_Factors_MasterCSV.csv"
OUTPUT_CATEGORIES = "Step Factor Categories Econ.xlsx"
T2_CATEGORIES_PATH = "Step Factor Categories.xlsx"
SOURCE_TO_T2_COUNTRY = {"U.S. NASDAQ": "NASDAQ", "China A": "ChinaA", "China H": "ChinaH"}

MONTHLY_FILL_LIMITS = {"monthly": 2, "quarterly": 4, "annual": 15, "sparse": 0}

ECON_INVERT_SHEETS = frozenset({
    "BIS_Credit_GDP_Gap", "BIS_DSR_Private", "BIS_Property_Price", "BIS_REER",
    "FRED_USD_Broad_Index", "Global_GPR", "Global_GPR_Act", "Global_GPR_Threat",
    "IMF_Money_Market_Rate", "WB_Domestic_Credit_GDP", "WB_Inflation_CPI",
    "WB_Market_Cap_GDP", "ILO_Unemployment_Rate", "IMF_WEO_Unemployment",
    "WB_Unemployment", "WB_OldAge_Dependency", "WB_CO2_Per_Capita",
    "FAO_Import_Dependency", "IMF_WEO_Debt_GDP", "WB_Govt_Debt_GDP",
    "MS_Public_Debt_External_Cr_fcee", "MS_Public_Debt_Foreign_Cur_e9e1",
    "MS_Public_Debt_Foreign_Held_Pct", "MS_Public_Debt_Local_Curre_d3c7",
    "MS_Public_Debt_Short_Matur_9fea", "MS_Public_Debt_Short_Term__896c",
    "MS_Public_Debt_Total_Pct_GDP", "MS_NPL_Net_Provisions_to_C_3fee",
    "MS_NPL_Ratio", "MS_Investor_Base_Fragility", "MS_Passive_Flow_Distortion",
    "NDGAIN_Vulnerability", "UNDP_GII",
})

ECON_CHANGE_12M_SHEETS = frozenset({
    "BIS_Credit_GDP_Gap", "BIS_DSR_Private", "BIS_Policy_Rate", "BIS_Property_Price",
    "BIS_REER", "WB_Domestic_Credit_GDP", "WB_Market_Cap_GDP", "IMF_WEO_GDP_Growth",
    "IMF_WEO_Inflation", "IMF_WEO_Unemployment", "ILO_Unemployment_Rate",
    "WB_GDP_Growth_Real", "WB_Inflation_CPI", "WB_Unemployment", "IMF_WEO_Debt_GDP",
    "MS_Investor_Base_Fragility", "MS_NPL_Net_Provisions_to_C_3fee", "MS_NPL_Ratio",
    "MS_Passive_Flow_Distortion", "MS_Public_Debt_Total_Pct_GDP", "WB_Govt_Debt_GDP",
    "FAO_Import_Dependency", "MS_Reserve_Adequacy", "WB_Current_Account_GDP",
    "WB_FX_Reserves", "WB_Import_Cover_Months", "NDGAIN_Vulnerability", "UNDP_GII",
    "WB_CO2_Per_Capita", "WB_OldAge_Dependency",
})


def map_country_label(label: object) -> str:
    if label is None or (isinstance(label, float) and str(label) == "nan"):
        return ""
    return SOURCE_TO_T2_COUNTRY.get(str(label).strip(), str(label).strip())


def to_reporting_month(dates: pd.Series) -> pd.Series:
    parsed = pd.to_datetime(dates, errors="coerce")
    aligned = parsed.dt.to_period("M").dt.to_timestamp()
    month_end = parsed.dt.is_month_end.fillna(False)
    if month_end.any():
        shifted = (parsed.loc[month_end] + pd.offsets.MonthBegin(1)).dt.normalize()
        aligned = aligned.mask(month_end, shifted)
    return aligned


def _truncate_sheet_key(name: str, max_len: int = 80) -> str:
    s = str(name).strip()
    return s if len(s) <= max_len else s[: max_len - 3] + "..."


def _infer_category(sheet_name: str) -> str:
    s = sheet_name.strip()
    return s.split("_")[0].title() if "_" in s else "Econ"


def _should_flip(sheet_name: str) -> bool:
    return str(sheet_name).strip() in ECON_INVERT_SHEETS


def _infer_panel_frequency(wide: pd.DataFrame) -> str:
    if wide.empty:
        return "sparse"
    observed = wide.sort_index()
    has_data = observed.notna().any(axis=1)
    dates = pd.Series(observed.index[has_data]).dropna().sort_values()
    if len(dates) < 3:
        return "sparse"
    gaps = dates.diff().dropna().dt.days
    if gaps.empty:
        return "sparse"
    median_gap = float(gaps.median())
    if median_gap <= 45:
        return "monthly"
    if median_gap <= 140:
        return "quarterly"
    if median_gap <= 430:
        return "annual"
    return "sparse"


def _expand_to_monthly_causal(wide: pd.DataFrame) -> Tuple[pd.DataFrame, str, int, int]:
    if wide.empty:
        return wide.copy(), "sparse", 0, 0
    wide = wide.sort_index()
    freq = _infer_panel_frequency(wide)
    limit = MONTHLY_FILL_LIMITS[freq]
    if limit <= 0:
        return wide, freq, len(wide), len(wide)
    monthly_index = pd.date_range(wide.index.min(), wide.index.max(), freq="MS")
    expanded = wide.reindex(monthly_index).ffill(limit=limit).dropna(how="all")
    expanded.index.name = wide.index.name
    return expanded, freq, len(wide), len(expanded)


def _has_country_dispersion(wide: pd.DataFrame) -> bool:
    numeric = wide.apply(pd.to_numeric, errors="coerce")
    return bool((numeric.nunique(axis=1, dropna=True) > 1).any())


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


def _calendar_delta(df: pd.DataFrame, months: int = 12) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    wide = df.sort_index()
    full_index = pd.date_range(wide.index.min(), wide.index.max(), freq="MS")
    expanded = wide.reindex(full_index)
    out = (expanded - expanded.shift(months)).reindex(wide.index)
    out.index.name = wide.index.name
    return out


def _sheet_to_long_variants(sheet_name: str, df_raw: pd.DataFrame) -> List[pd.DataFrame]:
    key = _truncate_sheet_key(sheet_name)
    parts: List[pd.DataFrame] = []
    variant_sources = {key: df_raw}
    if sheet_name in ECON_CHANGE_12M_SHEETS:
        variant_sources[f"{key}_D12"] = _calendar_delta(df_raw, months=12)
    for variant_key, source_wide in variant_sources.items():
        for suffix, wide in {"CS": _cs_normalize(source_wide), "TS": _ts_normalize(source_wide)}.items():
            tidy = wide.reset_index().rename(columns={wide.reset_index().columns[0]: "date"})
            tidy = tidy.melt(id_vars=["date"], var_name="country", value_name="value")
            tidy["variable"] = f"{variant_key}_{suffix}"
            parts.append(tidy[["date", "country", "variable", "value"]])
    return parts


def _load_1mret_long(work_dir: Path) -> pd.DataFrame:
    csv = pd.read_csv(work_dir / NORMALIZED_T2_CSV)
    lower = {c.lower(): c for c in csv.columns}
    csv = csv.rename(columns={lower.get("date", "date"): "date"})
    csv["date"] = pd.to_datetime(csv["date"], errors="coerce")
    ret = csv[csv["variable"] == "1MRet"][["date", "country", "variable", "value"]].copy()
    ret["country"] = ret["country"].astype(str)
    ret["date"] = to_reporting_month(ret["date"])
    return ret


# ── Analysis-window helpers (inlined from Step T2_Econ_analysis_window.py) ────
def _window_from_panel(df: pd.DataFrame) -> Tuple[pd.Timestamp, pd.Timestamp]:
    dates = to_reporting_month(df.iloc[:, 0])
    country_block = df.iloc[:, 1:].apply(pd.to_numeric, errors="coerce")
    has_data = country_block.notna().any(axis=1) & dates.notna()
    if not has_data.any():
        raise ValueError("no row has any non-missing country values.")
    return pd.Timestamp(dates.loc[has_data].min()).normalize(), pd.Timestamp(dates.loc[has_data].max()).normalize()


def get_econ_analysis_window(econ_path: Path) -> Tuple[pd.Timestamp, pd.Timestamp]:
    xl = pd.ExcelFile(str(econ_path), engine="openpyxl")
    try:
        if WINDOW_ANCHOR_SHEET in xl.sheet_names:
            return _window_from_panel(pd.read_excel(xl, sheet_name=WINDOW_ANCHOR_SHEET, engine="openpyxl"))
        starts, ends = [], []
        for sheet_name in xl.sheet_names:
            if sheet_name in SKIP_WINDOW_SHEETS:
                continue
            df = pd.read_excel(xl, sheet_name=sheet_name, engine="openpyxl")
            if df.empty or df.shape[1] < 2:
                continue
            try:
                s, e = _window_from_panel(df)
            except ValueError:
                continue
            starts.append(s)
            ends.append(e)
        if not starts:
            raise ValueError("no wide date x country panel sheets found.")
        return min(starts), max(ends)
    finally:
        xl.close()


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
        if sn in ECON_CHANGE_12M_SHEETS:
            rows.append({"Factor Name": f"{key}_D12_CS", "Category": cat, "Max": 1.0})
            rows.append({"Factor Name": f"{key}_D12_TS", "Category": cat, "Max": 1.0})
    cat_path = work_dir / T2_CATEGORIES_PATH
    if not cat_path.exists():
        logger.warning("Missing %s — skipping categories workbook.", cat_path)
        return
    asset = pd.read_excel(str(cat_path), sheet_name="Asset Class", engine="openpyxl")
    with pd.ExcelWriter(str(work_dir / OUTPUT_CATEGORIES), engine="openpyxl", mode="w") as w:
        pd.DataFrame(rows).to_excel(w, sheet_name="Factor Categories", index=False)
        asset.to_excel(w, sheet_name="Asset Class", index=False)


def normalize_econ(work_dir: Path) -> Path:
    src = work_dir / "Econ.xlsx"
    if not src.exists():
        raise FileNotFoundError(src)
    xl = pd.ExcelFile(str(src), engine="openpyxl")
    data_sheets = [s for s in xl.sheet_names if s not in SOURCE_SKIP_SHEETS]
    all_parts, sheets_loaded = [], []
    for sheet in data_sheets:
        df = pd.read_excel(xl, sheet_name=sheet, engine="openpyxl")
        if df.empty or df.shape[1] < 2:
            continue
        df = df.rename(columns={df.columns[0]: "date"})
        df["date"] = to_reporting_month(df["date"])
        df = df.dropna(subset=["date"])
        df = df.rename(columns={c: map_country_label(c) for c in df.columns if c != "date"})
        wide = df.set_index("date")
        wide.index.name = "date"
        wide = wide.apply(pd.to_numeric, errors="coerce")
        if not _has_country_dispersion(wide):
            continue
        wide, _, _, _ = _expand_to_monthly_causal(wide)
        if SOURCE_SIGNAL_LAG_MONTHS:
            wide.index = wide.index + pd.DateOffset(months=SOURCE_SIGNAL_LAG_MONTHS)
        if _should_flip(sheet):
            wide = wide * -1.0
        all_parts.extend(_sheet_to_long_variants(sheet, wide))
        sheets_loaded.append(sheet)
    if not all_parts:
        raise ValueError("No Econ sheets produced tidy data.")
    factors_long = pd.concat(all_parts, ignore_index=True)
    ret_long = _load_1mret_long(work_dir)
    combined = pd.concat([factors_long, ret_long], ignore_index=True)

    raw_s, raw_e = get_econ_analysis_window(src)
    src_s = raw_s + pd.DateOffset(months=SOURCE_SIGNAL_LAG_MONTHS)
    src_e = raw_e + pd.DateOffset(months=SOURCE_SIGNAL_LAG_MONTHS)
    ret_dates = pd.to_datetime(ret_long["date"], errors="coerce").dropna()
    win_s = max(src_s, pd.Timestamp(ret_dates.min()).normalize())
    win_e = min(src_e, pd.Timestamp(ret_dates.max()).normalize())
    if win_s > win_e:
        raise ValueError(f"No overlap: Econ {src_s.date()}..{src_e.date()} vs returns.")
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
    ap.add_argument("--dir", type=Path, default=T2_ECON_DIR)
    args = ap.parse_args()
    normalize_econ(args.dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
