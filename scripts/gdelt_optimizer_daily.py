#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/gdelt_optimizer_daily.py
=============================================================================

DESCRIPTION:
    ASADO-internal port of "Step Four GDELT Create Daily Top20 Returns.py"
    (A Complete/GDELT Factor Timing Fuzzy Daily/T2-Factor-Timing-Daily). Builds
    daily GDELT factor portfolios (fuzzy soft 15-25% taper) and writes their
    daily net (excess-vs-benchmark) returns.

    IMPORTANT — this is NOT the same as the T2 daily optimizer:
      * The return paid to weights(T) is the `1DRet` series MERGED INTO THE CSV,
        SAME DATE (no .shift). 1DRet already = TRI(T+1)/TRI(T)-1, so the forward
        step is baked in; shifting again (as T2 Step Four does) is wrong here.
      * Only dates present in the CSV (factor ∩ 1DRet) are evaluated — no reindex
        to a full calendar grid, so no weekend / out-of-window rows.
      * NaNs are filled with the per-date cross-sectional mean (across factors)
        before scaling x100.

INPUT FILES:
    - --csv  Data/work/gdelt_daily/GDELT_Factors_MasterCSV.csv  (GDELT _CS/_TS + 1DRet)
    - --portfolio  Data/work/t2_daily/Portfolio_Data.xlsx       (Benchmarks: equal_weight)

OUTPUT FILES:
    - --out  Data/work/gdelt_daily/GDELT_Optimizer.xlsx  (sheet Monthly_Net_Returns = DAILY net %)

VERSION: 1.0
LAST UPDATED: 2026-06-09
AUTHOR: Arjun Divecha (ported by Claude Code)

DEPENDENCIES: pandas, numpy, openpyxl

USAGE: python scripts/gdelt_optimizer_daily.py
=============================================================================
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
GDELT_DAILY_DIR = BASE_DIR / "Data" / "work" / "gdelt_daily"
DEFAULT_CSV = GDELT_DAILY_DIR / "GDELT_Factors_MasterCSV.csv"
DEFAULT_PORTFOLIO = BASE_DIR / "Data" / "work" / "t2_daily" / "Portfolio_Data.xlsx"
DEFAULT_OUT = GDELT_DAILY_DIR / "GDELT_Optimizer.xlsx"

SOFT_BAND_TOP = 0.15
SOFT_BAND_CUTOFF = 0.25


def analyze(data: pd.DataFrame, features, benchmark_returns):
    rd = data[data["variable"] == "1DRet"].copy()
    rd["value"] = pd.to_numeric(rd["value"], errors="coerce")
    rd = rd.rename(columns={"value": "return_value"})
    returns_by_date = {d: g[["country", "return_value"]] for d, g in rd.groupby("date")}

    net = {}
    for feature in features:
        fd = data[data["variable"] == feature].copy()
        if fd.empty:
            continue
        fd["value"] = pd.to_numeric(fd["value"], errors="coerce")
        fd = fd.dropna(subset=["value"]).rename(columns={"value": "factor_value"})
        if fd.empty:
            continue
        port = {}
        for date, g in fd.groupby("date"):
            if date not in returns_by_date:
                continue
            m = pd.merge(g[["country", "factor_value"]], returns_by_date[date], on="country")
            m = m.dropna(subset=["factor_value", "return_value"])
            if m.empty:
                continue
            m = m.sort_values("factor_value", ascending=False).reset_index(drop=True)
            n = len(m)
            rank_pct = (np.arange(n) + 1) / n
            w = np.zeros(n)
            w[rank_pct < SOFT_BAND_TOP] = 1.0
            band = (rank_pct >= SOFT_BAND_TOP) & (rank_pct <= SOFT_BAND_CUTOFF)
            w[band] = 1.0 - (rank_pct[band] - SOFT_BAND_TOP) / (SOFT_BAND_CUTOFF - SOFT_BAND_TOP)
            nz = w > 0
            if not nz.any():
                continue
            wf = w[nz] / w[nz].sum()
            port[date] = float(np.dot(wf, m["return_value"].values[nz]))
        if not port:
            continue
        ps = pd.Series(port).sort_index()
        ab = benchmark_returns.reindex(ps.index)
        valid = ab.notna()
        if valid.any():
            net[feature] = ps[valid] - ab[valid]
    return net


def main() -> int:
    ap = argparse.ArgumentParser(description="Daily GDELT factor returns (Step Four GDELT port).")
    ap.add_argument("--csv", default=str(DEFAULT_CSV))
    ap.add_argument("--portfolio", default=str(DEFAULT_PORTFOLIO))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    csv_path, port_path = Path(args.csv), Path(args.portfolio)
    if not csv_path.exists() or not port_path.exists():
        logger.error("Missing input(s): %s / %s", csv_path, port_path)
        return 1

    logger.info("Loading GDELT factor CSV: %s", csv_path)
    data = pd.read_csv(csv_path)
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    data["value"] = pd.to_numeric(data["value"], errors="coerce")
    data = data.dropna(subset=["value"])
    data = data.groupby(["date", "country", "variable"], as_index=False).last()

    returns_df = pd.read_excel(str(port_path), sheet_name="Returns", index_col=0)
    returns_df.index = pd.to_datetime(returns_df.index, errors="coerce")
    bench = pd.read_excel(str(port_path), sheet_name="Benchmarks", index_col=0)
    bench.index = pd.to_datetime(bench.index, errors="coerce")
    benchmark_returns = pd.to_numeric(bench["equal_weight"], errors="coerce").reindex(returns_df.index)

    features = sorted(set(data["variable"]) - {"1DRet"})
    logger.info("Analyzing %d GDELT factor portfolios ...", len(features))
    net = analyze(data, features, benchmark_returns)

    net_df = pd.DataFrame(net).sort_index()
    filled = net_df.apply(lambda row: row.fillna(row.mean()), axis=1)   # cross-sectional fill
    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(str(out), engine="openpyxl") as wr:
        (filled * 100).to_excel(wr, sheet_name="Monthly_Net_Returns", index_label="Date")
    logger.info("Wrote %s (%d factors, %d daily dates)", out, filled.shape[1], filled.shape[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
