#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/t2_optimizer_daily.py
=============================================================================

DESCRIPTION:
    DAILY analog of the T2 optimizer factor-return step — ASADO-internal port
    of the reference "Step Four Create Monthly Top20 Returns.py" (which, despite
    its name, computes DAILY factor net returns). Builds, for every normalized
    factor, a fuzzy soft-taper top-quantile long portfolio, computes its daily
    return (one-row-forward lag), nets it against the equal-weight benchmark,
    and writes the daily factor-return matrix.

INPUT FILES:
    - Data/work/t2_daily/Normalized_T2_MasterCSV.csv   (t2_normalize_daily.py)
    - Data/work/t2_daily/Portfolio_Data.xlsx           (build_benchmark_rets_daily.py)

OUTPUT FILES:
    - Data/work/t2_daily/T2_Optimizer.xlsx  (sheet 'Monthly_Net_Returns' = DAILY net % returns)

VERSION: 1.0
LAST UPDATED: 2026-06-09
AUTHOR: Arjun Divecha (ported by Claude Code)

DEPENDENCIES: pandas, numpy, openpyxl

USAGE: python scripts/t2_optimizer_daily.py

NOTES:
    - Fuzzy taper: rank_pct = rank_desc / n_valid; weight 1.0 for rank_pct<0.15,
      linear 1->0 across [0.15, 0.25], 0 beyond; then normalized to sum 1.
    - Sort DESCENDING by factor value; NO sign flip here (faithful to Step Four).
    - Lag: weights(T) paid returns(next index row). Last date dropped.
    - 'Monthly_Net_Returns' is a legacy sheet name; the data is DAILY.
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
T2_DAILY_DIR = BASE_DIR / "Data" / "work" / "t2_daily"
DEFAULT_CSV = T2_DAILY_DIR / "Normalized_T2_MasterCSV.csv"
DEFAULT_PORTFOLIO = T2_DAILY_DIR / "Portfolio_Data.xlsx"
DEFAULT_OUT = T2_DAILY_DIR / "T2_Optimizer.xlsx"

SKIP_VARIABLES = {
    "1MRet", "3MRet", "6MRet", "9MRet", "12MRet",
    "1DRet", "5DRet", "20DRet", "60DRet", "120DRet",
    "1DTR", "5DTR", "20DTR", "120DTR", "120-5DTR",
}
SOFT_BAND_TOP = 0.15
SOFT_BAND_CUTOFF = 0.25


def taper_weights(wide: pd.DataFrame) -> pd.DataFrame:
    """Per-date fuzzy soft-taper long weights from a (date x country) factor matrix."""
    rank_desc = wide.rank(axis=1, ascending=False, method="first")   # 1 = best
    n_valid = wide.notna().sum(axis=1)
    rank_pct = rank_desc.div(n_valid.where(n_valid != 0), axis=0)
    w = pd.DataFrame(0.0, index=wide.index, columns=wide.columns)
    full = rank_pct < SOFT_BAND_TOP
    band = (rank_pct >= SOFT_BAND_TOP) & (rank_pct <= SOFT_BAND_CUTOFF)
    w = w.mask(full, 1.0)
    taper = 1.0 - (rank_pct - SOFT_BAND_TOP) / (SOFT_BAND_CUTOFF - SOFT_BAND_TOP)
    w = w.mask(band, taper)
    w = w.fillna(0.0)
    rowsum = w.sum(axis=1)
    return w.div(rowsum.where(rowsum != 0), axis=0).fillna(0.0)


def main() -> int:
    ap = argparse.ArgumentParser(description="Daily factor returns from normalized factors.")
    ap.add_argument("--csv", default=str(DEFAULT_CSV))
    ap.add_argument("--portfolio", default=str(DEFAULT_PORTFOLIO))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    csv_path, port_path = Path(args.csv), Path(args.portfolio)
    if not csv_path.exists() or not port_path.exists():
        logger.error("Missing input(s): %s / %s", csv_path, port_path)
        return 1

    logger.info("Loading normalized factor CSV: %s", csv_path)
    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["value"])
    df = df.groupby(["date", "country", "variable"], as_index=False)["value"].last()

    returns = pd.read_excel(str(port_path), sheet_name="Returns", index_col=0)
    returns.index = pd.to_datetime(returns.index, errors="coerce")
    returns = returns.apply(pd.to_numeric, errors="coerce")
    bench = pd.read_excel(str(port_path), sheet_name="Benchmarks", index_col=0)
    bench.index = pd.to_datetime(bench.index, errors="coerce")
    benchmark = pd.to_numeric(bench["equal_weight"], errors="coerce").reindex(returns.index)

    # returns at the NEXT index row (one-row-forward lag), aligned to current date
    ret_next = returns.shift(-1)

    features = sorted(v for v in df["variable"].unique() if v not in SKIP_VARIABLES)
    logger.info("Computing daily returns for %d factors over %d dates ...", len(features), len(returns))

    net_cols = {}
    for i, feat in enumerate(features, 1):
        sub = df[df["variable"] == feat]
        wide = sub.pivot(index="date", columns="country", values="value")
        wide = wide.reindex(returns.index)
        cols = wide.columns.intersection(ret_next.columns)
        wide = wide[cols]
        w = taper_weights(wide)
        rn = ret_next[cols].reindex(index=w.index)
        port = (w * rn).sum(axis=1, min_count=1)
        net = (port - benchmark).reindex(returns.index)
        if net.abs().sum() > 0:
            net_cols[feat] = net
        if i % 25 == 0:
            logger.info("  %d/%d factors", i, len(features))

    net_df = pd.DataFrame(net_cols).reindex(returns.index).fillna(0.0)
    net_df = net_df.loc[:, (net_df != 0).any(axis=0)]

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(str(out), engine="openpyxl") as wr:
        (net_df * 100).to_excel(wr, sheet_name="Monthly_Net_Returns", index_label="Date")
    logger.info("Wrote %s (%d factors, %d daily dates)", out, net_df.shape[1], net_df.shape[0])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
