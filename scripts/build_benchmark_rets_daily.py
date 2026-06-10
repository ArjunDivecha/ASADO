#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/build_benchmark_rets_daily.py
=============================================================================

DESCRIPTION:
    DAILY analog of build_benchmark_rets.py — ASADO-internal port of the
    reference "Step Two Point Five Create Benchmark Rets.py" (daily).
    Reads the daily T2 Master (1DRet + Mcap Weights/MCAP) and writes
    Portfolio_Data.xlsx with daily Returns / Weights / Benchmarks
    (equal_weight, mcap_weight, us_market). Feeds the daily optimizer.

INPUT FILES:
    - Data/work/t2_daily/T2 Master Daily.xlsx  (sheets 1DRet, Mcap Weights or MCAP)

OUTPUT FILES:
    - Data/work/t2_daily/Portfolio_Data.xlsx   (Returns / Weights / Benchmarks)

VERSION: 1.0
LAST UPDATED: 2026-06-09
AUTHOR: Arjun Divecha (ported by Claude Code)

DEPENDENCIES: pandas, numpy, openpyxl

USAGE: python scripts/build_benchmark_rets_daily.py
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
DEFAULT_MASTER = T2_DAILY_DIR / "T2 Master Daily.xlsx"
DEFAULT_OUT = T2_DAILY_DIR / "Portfolio_Data.xlsx"


def _read_sheet(xl, sheet):
    df = pd.read_excel(xl, sheet_name=sheet, index_col=0)
    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df[~df.index.isna()].sort_index()
    return df.apply(pd.to_numeric, errors="coerce")


def main() -> int:
    ap = argparse.ArgumentParser(description="Daily benchmarks -> Portfolio_Data.xlsx")
    ap.add_argument("--master", default=str(DEFAULT_MASTER))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    master = Path(args.master)
    if not master.exists():
        logger.error("Daily T2 Master not found: %s", master)
        return 1
    xl = pd.ExcelFile(str(master))

    returns = _read_sheet(xl, "1DRet")
    returns = returns[sorted(returns.columns)]   # alphabetical (reference)

    # weights: prefer Mcap Weights, else MCAP — row-normalize either way
    if "Mcap Weights" in xl.sheet_names:
        w = _read_sheet(xl, "Mcap Weights")
    else:
        w = _read_sheet(xl, "MCAP")
    w = w.reindex(columns=[c for c in w.columns if c in returns.columns])
    w = w.reindex(returns.index)
    rowsum = w.sum(axis=1)
    w = w.div(rowsum.where(rowsum != 0), axis=0)
    w = w.ffill().bfill().fillna(0.0)

    common = returns.columns.intersection(w.columns)
    returns = returns[common]; w = w[common]

    has_nan_last = bool(returns.iloc[-1].isna().all())
    cr = returns[:-1] if has_nan_last else returns
    cw = w[:-1] if has_nan_last else w
    equal = cr.mean(axis=1)
    mcap = (cr * cw).sum(axis=1)
    if "U.S." in cr.columns:
        us = cr["U.S."]
    elif "SPX" in cr.columns:
        us = cr["SPX"]
    else:
        us = cr.iloc[:, 0]
    bench = {"equal_weight": equal, "mcap_weight": mcap, "us_market": us}
    if has_nan_last:
        last = returns.index[-1]
        for k in bench:
            bench[k] = pd.concat([bench[k], pd.Series([np.nan], index=[last])])

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(str(out), engine="openpyxl") as wr:
        returns.to_excel(wr, sheet_name="Returns")
        w.to_excel(wr, sheet_name="Weights")
        pd.DataFrame(bench).to_excel(wr, sheet_name="Benchmarks")
    logger.info("Wrote %s (returns %s..%s, %d rows)", out,
                returns.index[0].date(), returns.index[-1].date(), len(returns))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
