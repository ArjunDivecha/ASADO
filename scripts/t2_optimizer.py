"""
=============================================================================
SCRIPT NAME: scripts/t2_optimizer.py
=============================================================================

INPUT FILES (default: T2 Factor Timing Fuzzy dir):
- Normalized_T2_MasterCSV.csv  (from t2_normalize.py)
- Portfolio_Data.xlsx (sheet "Benchmarks": equal_weight benchmark returns)
- Step Tcost.xlsx (sheet "jjunk": per-country trading costs)

OUTPUT FILES (same dir):
- T2_Top_20_Exposure.csv   (monthly country weights per factor)  [Step Three]
- T2_Optimizer.xlsx        (sheet Monthly_Net_Returns)           [Step Four]
- T60.xlsx                 (60M trailing averages)               [Step Four]

VERSION: 1.0
LAST UPDATED: 2026-06-04
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
ASADO-internal port of the T2 Fuzzy optimizer ("Step Three Top20 Portfolios
Fast.py" + "Step Four Create Monthly Top20 Returns FAST.py") — makes ASADO
standalone for the T2 strategy (no external Step Three/Four run). The fuzzy
soft 15-25% band portfolio logic and the per-step exclusion lists are copied
faithfully so outputs match the external T2_Top_20_Exposure.csv and
T2_Optimizer.xlsx. The non-consumed PDF charts / perf table are omitted.

ASADO's collect_optimizer_returns.py reads T2_Optimizer.xlsx +
T2_Top_20_Exposure.csv from this dir.

DEPENDENCIES: pandas, numpy, xlsxwriter, openpyxl

USAGE:
  python scripts/t2_optimizer.py                 # default Fuzzy dir
  python scripts/t2_optimizer.py --dir DIR       # custom working dir
  python scripts/t2_optimizer.py --step three    # only exposure
  python scripts/t2_optimizer.py --step four     # only optimizer returns
=============================================================================
"""
from __future__ import annotations

import argparse
import logging
import warnings
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

T2_FUZZY_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/t2")
T2_GDELT_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/gdelt")
T2_ECON_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/econ")
RETURN_SERIES = ["1MRet", "3MRet", "6MRet", "9MRet", "12MRet"]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

SOFT_BAND_TOP = 0.15     # 15% => full weight
SOFT_BAND_CUTOFF = 0.25  # 25% => zero weight


def _load_benchmark(benchmark_path: Path) -> pd.Series:
    bench = pd.read_excel(str(benchmark_path), sheet_name="Benchmarks", index_col=0)
    bench.index = pd.to_datetime(bench.index).to_period("M").to_timestamp()
    return bench["equal_weight"]


# =============================================================================
# STEP THREE — exposure (country weights) → T2_Top_20_Exposure.csv
# =============================================================================
STEP3_SKIP = [
    "1MRet", "3MRet", "6MRet", "9MRet", "12MRet",
    "120MA_CS", "129MA_TS", "Agriculture_TS", "Agriculture_CS",
    "Copper_TS", "Copper_CS", "Gold_CS", "Gold_TS",
    "Oil_CS", "Oil_TS", "MCAP Adj_CS", "MCAP Adj_TS",
    "MCAP_CS", "MCAP_TS", "PX_LAST_CS", "PX_LAST_TS",
    "Tot Return Index_CS", "Tot Return Index_TS",
    "Currency_CS", "Currency_TS", "BEST EPS_CS", "BEST EPS_TS",
    "Trailing EPS_CS", "Trailing EPS_TS",
]


def _step3_holdings(data: pd.DataFrame, features: list, benchmark_returns: pd.Series
                    ) -> Dict[str, pd.DataFrame]:
    dates = sorted(data["date"].unique())
    countries = sorted(data["country"].unique())
    country_to_idx = {c: i for i, c in enumerate(countries)}
    n_countries, n_dates = len(countries), len(dates)

    returns_data = (data[data["variable"] == "1MRet"]
                    .assign(date=lambda df: pd.to_datetime(df["date"])).sort_values("date"))
    returns_lookup = {(row.date, row.country): row.value
                      for row in returns_data.itertuples(index=False)}

    feature_data_cache: Dict[str, dict] = {}
    for feature in features:
        feat_df = (data[data["variable"] == feature]
                   .assign(date=lambda df: pd.to_datetime(df["date"])).sort_values("date"))
        valid_dates_mask = feat_df.groupby("date")["value"].apply(lambda x: x.notna().any())
        valid_dates = valid_dates_mask[valid_dates_mask].index.tolist()
        feat_df = feat_df[feat_df["date"].isin(valid_dates)].sort_values("date")
        feature_data_cache[feature] = {}
        for date, group in feat_df.groupby("date"):
            factor_only = group[["country", "value"]].dropna(subset=["value"])
            if not factor_only.empty:
                factor_only = factor_only.sort_values("value", ascending=False).reset_index(drop=True)
                feature_data_cache[feature][date] = (factor_only["country"].values,
                                                     factor_only["value"].values)

    monthly_holdings: Dict[str, pd.DataFrame] = {}
    for feature in features:
        feat_by_date = feature_data_cache[feature]
        holdings_arr = np.zeros((n_dates, n_countries))
        for date_idx, date in enumerate(dates):
            if date not in feat_by_date:
                continue
            countries_arr, values_arr = feat_by_date[date]
            n = len(countries_arr)
            if n == 0:
                continue
            rank_pct = (np.arange(n) + 1) / n
            weights = np.zeros(n)
            weights[rank_pct < SOFT_BAND_TOP] = 1.0
            in_band = (rank_pct >= SOFT_BAND_TOP) & (rank_pct <= SOFT_BAND_CUTOFF)
            weights[in_band] = 1.0 - (rank_pct[in_band] - SOFT_BAND_TOP) / (SOFT_BAND_CUTOFF - SOFT_BAND_TOP)
            nonzero_mask = weights > 0
            if not nonzero_mask.any():
                continue
            wf = weights[nonzero_mask]
            cf = countries_arr[nonzero_mask]
            wf = wf / wf.sum()
            for c, w in zip(cf, wf):
                holdings_arr[date_idx, country_to_idx[c]] = w
        monthly_holdings[feature] = pd.DataFrame(
            holdings_arr, index=pd.Index(dates, name="date"),
            columns=pd.Index(countries, name="country"))
    return monthly_holdings


def run_step_three(work_dir: Path, cfg: dict | None = None) -> Path:
    cfg = cfg or PIPELINES["t2"]
    data = pd.read_csv(work_dir / cfg["csv"])
    data["date"] = pd.to_datetime(data["date"]).dt.to_period("M").dt.to_timestamp()
    benchmark_returns = _load_benchmark(work_dir / "Portfolio_Data.xlsx")
    features = sorted(v for v in data["variable"].unique() if v not in cfg["step3_skip"])
    logger.info("Step Three: %d factors (soft 15-25%% band)", len(features))
    monthly_holdings = _step3_holdings(data, features, benchmark_returns)

    exposure_rows = []
    all_dates = sorted({d for df in monthly_holdings.values() for d in df.index})
    all_countries = sorted({c for df in monthly_holdings.values() for c in df.columns})
    for date in all_dates:
        for country in all_countries:
            row = [date.strftime("%Y-%m-%d"), country]
            for factor in features:
                w = monthly_holdings[factor].get(country, pd.Series()).get(date, 0.0)
                row.append(round(float(w), 6))
            exposure_rows.append(row)
    exposure_df = pd.DataFrame(exposure_rows, columns=["Date", "Country"] + features)
    out = work_dir / cfg["exposure_out"]
    exposure_df.to_csv(out, index=False)
    logger.info("Wrote %s (%d rows)", out, len(exposure_df))
    return out


# =============================================================================
# STEP FOUR — net returns → T2_Optimizer.xlsx (Monthly_Net_Returns) + T60.xlsx
# =============================================================================
STEP4_EXCL = [
    "3MRet", "6MRet", "9MRet", "12MRet",
    "120MA_CS", "120MA_TS", "12MTR_CS", "12MTR_TS",
    "Agriculture_CS", "Agriculture 12_CS", "Copper_CS", "Copper 12_CS",
    "Gold_CS", "Gold 12_CS", "Oil_CS", "Oil 12_CS", "BEST EPS_CS",
    "Currency_CS", "MCAP_CS", "MCAP_TS", "MCAP Adj_CS", "MCAP Adj_TS",
    "PX_LAST_CS", "PX_LAST_TS", "Tot Return Index _CS", "Tot Return Index _TS",
    "Trailing EPS_CS", "Trailing EPS_TS",
]


def _step4_net_returns(data: pd.DataFrame, features: list, benchmark_returns: pd.Series,
                       trading_costs: pd.Series) -> Dict[str, pd.Series]:
    returns_data = data[data["variable"] == "1MRet"].copy()
    returns_data["value"] = pd.to_numeric(returns_data["value"], errors="coerce")
    returns_data = returns_data.rename(columns={"value": "return_value"})
    returns_by_date = {date: group[["country", "return_value"]].copy()
                       for date, group in returns_data.groupby("date")}

    feature_merged_cache: Dict[str, dict] = {}
    for feature in features:
        fd = data[data["variable"] == feature].copy()
        if fd.empty:
            continue
        fd["value"] = pd.to_numeric(fd["value"], errors="coerce")
        fd = fd.dropna(subset=["value"])
        if fd.empty:
            continue
        fd = fd.rename(columns={"value": "factor_value"})
        feature_merged_cache[feature] = {}
        for date, group in fd.groupby("date"):
            if date not in returns_by_date:
                continue
            merged = pd.merge(group[["country", "factor_value"]], returns_by_date[date], on="country")
            merged = merged.dropna(subset=["factor_value", "return_value"])
            if merged.empty:
                continue
            merged = merged.sort_values("factor_value", ascending=False).reset_index(drop=True)
            feature_merged_cache[feature][date] = (
                merged["country"].values, merged["factor_value"].values, merged["return_value"].values)

    monthly_net_returns: Dict[str, pd.Series] = {}
    for feature in features:
        if feature not in feature_merged_cache:
            continue
        feat_by_date = feature_merged_cache[feature]
        feature_dates = sorted(feat_by_date.keys())
        if not feature_dates:
            continue
        portfolio_returns = pd.Series(index=feature_dates, dtype=float)
        for date in feature_dates:
            data_countries, factor_values, return_values = feat_by_date[date]
            n = len(factor_values)
            if n == 0:
                continue
            rank_pct = (np.arange(n) + 1) / n
            weights = np.zeros(n)
            weights[rank_pct < SOFT_BAND_TOP] = 1.0
            in_band = (rank_pct >= SOFT_BAND_TOP) & (rank_pct <= SOFT_BAND_CUTOFF)
            weights[in_band] = 1.0 - (rank_pct[in_band] - SOFT_BAND_TOP) / (SOFT_BAND_CUTOFF - SOFT_BAND_TOP)
            nonzero_mask = weights > 0
            if not nonzero_mask.any():
                continue
            wf = weights[nonzero_mask]
            rf = return_values[nonzero_mask]
            wf = wf / wf.sum()
            portfolio_returns[date] = np.dot(wf, rf)
        portfolio_returns = portfolio_returns.dropna()
        if portfolio_returns.empty:
            continue
        aligned_benchmark = benchmark_returns.reindex(portfolio_returns.index)
        valid_idx = aligned_benchmark.notna()
        if any(valid_idx):
            monthly_net_returns[feature] = portfolio_returns[valid_idx] - aligned_benchmark[valid_idx]
    return monthly_net_returns


def run_step_four(work_dir: Path, cfg: dict | None = None) -> Path:
    cfg = cfg or PIPELINES["t2"]
    data = pd.read_csv(work_dir / cfg["csv"])
    data["date"] = pd.to_datetime(data["date"]).dt.to_period("M").dt.to_timestamp()
    benchmark_returns = _load_benchmark(work_dir / "Portfolio_Data.xlsx")

    tcost_df = pd.read_excel(str(work_dir / "Step Tcost.xlsx"), sheet_name="jjunk")
    trading_costs = pd.Series(
        pd.to_numeric(tcost_df["Trading Cost"], errors="coerce").values, index=tcost_df["Country"])
    trading_costs = trading_costs[~trading_costs.index.duplicated(keep="first")]

    features = sorted(set(data["variable"]) - {"1MRet"})
    logger.info("Step Four: %d factors", len(features))
    net_returns = _step4_net_returns(data, features, benchmark_returns, trading_costs)

    net_df = pd.DataFrame(net_returns)
    net_df = net_df[[c for c in net_df.columns if c not in cfg["step4_excl"]]]

    # T60.xlsx (60M trailing averages) — same construction as the external step
    filled = net_df.apply(lambda row: row.fillna(row.mean()), axis=1)
    next_month = filled.index[-1] + pd.DateOffset(months=1)
    filled.loc[next_month] = np.nan
    t60 = filled.shift(1).rolling(60, min_periods=1).mean() * 100
    with pd.ExcelWriter(str(work_dir / "T60.xlsx"), engine="xlsxwriter") as writer:
        t60.to_excel(writer, sheet_name="T60", index_label="Date")
        wb, ws = writer.book, writer.sheets["T60"]
        ws.set_column(0, 0, 15, wb.add_format({"num_format": "dd-mmm-yyyy"}))
        ws.set_column(1, len(t60.columns), 12, wb.add_format({"num_format": "0.0000"}))

    net_df = net_df.apply(lambda row: row.fillna(row.mean()), axis=1) * 100
    net_df.sort_index(inplace=True)
    out = work_dir / cfg["optimizer_out"]
    net_df.to_excel(str(out), sheet_name="Monthly_Net_Returns", index_label="Date")
    logger.info("Wrote %s (%d rows x %d factors)", out, net_df.shape[0], net_df.shape[1])
    return out


# Per-pipeline config. Core fuzzy logic is shared; only inputs/skip/excl/outputs
# and the working dir differ. T2 uses big skip/excl lists; GDELT/Econ skip only
# the return series and exclude nothing (faithful to their external steps).
PIPELINES: dict[str, dict] = {
    "t2": {
        "dir": T2_FUZZY_DIR, "csv": "Normalized_T2_MasterCSV.csv",
        "step3_skip": STEP3_SKIP, "step4_excl": STEP4_EXCL,
        "exposure_out": "T2_Top_20_Exposure.csv", "optimizer_out": "T2_Optimizer.xlsx",
    },
    "gdelt": {
        "dir": T2_GDELT_DIR, "csv": "GDELT_Factors_MasterCSV.csv",
        "step3_skip": RETURN_SERIES, "step4_excl": [],
        "exposure_out": "GDELT_Top_20_Exposure.csv", "optimizer_out": "GDELT_Optimizer.xlsx",
    },
    "econ": {
        "dir": T2_ECON_DIR, "csv": "Econ_Factors_MasterCSV.csv",
        "step3_skip": RETURN_SERIES, "step4_excl": [],
        "exposure_out": "Econ_Top_20_Exposure.csv", "optimizer_out": "Econ_Optimizer.xlsx",
    },
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pipeline", choices=list(PIPELINES), default="t2",
                    help="Which factor pipeline (t2 / gdelt / econ)")
    ap.add_argument("--dir", type=Path, default=None, help="Override working dir")
    ap.add_argument("--step", choices=["three", "four", "both"], default="both")
    args = ap.parse_args()
    cfg = PIPELINES[args.pipeline]
    work_dir = args.dir or cfg["dir"]
    if args.step in ("three", "both"):
        run_step_three(work_dir, cfg)
    if args.step in ("four", "both"):
        run_step_four(work_dir, cfg)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
