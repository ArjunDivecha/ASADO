"""
=============================================================================
SCRIPT NAME: build_benchmark_rets.py
=============================================================================

DESCRIPTION:
    ASADO-internal port of "Step Two Point Five Create Benchmark Rets.py".
    Builds the benchmark / country-returns workbook (Portfolio_Data.xlsx) that
    the optimizer (t2_optimizer.py) reads to compute net-of-benchmark factor
    returns. WITHOUT a fresh Portfolio_Data.xlsx the optimizer clips every
    factor's returns to the last month the benchmark covers — which is exactly
    why GDELT factor returns were stuck at 2026-03 while exposures ran to July.

    The canonical T2 Master is itself generated from the Bloomberg source file
    (Country Bloomberg Data Master T.xlsx) by build_t2_master.py, so this script
    roots the benchmark in the original Bloomberg data, one hop removed.

    Three benchmarks are produced:
      - equal_weight : simple mean of the 34 country monthly returns
      - mcap_weight  : market-cap weighted sum of country returns
      - us_market    : the 'U.S.' column (reference)

INPUT FILES:
    --master  (default: /Users/arjundivecha/Dropbox/AAA Backup/A Complete/
               T2 Factor Timing Fuzzy/T2 Master.xlsx)
        Sheet '1MRet'        : monthly returns per country (date index x 34 cols)
        Sheet 'Mcap Weights' : market-cap weights per country
        (T2 Master.xlsx is produced by build_t2_master.py from the Bloomberg
         dump Country Bloomberg Data Master T.xlsx.)

OUTPUT FILES:
    --output  (default: <master dir>/Portfolio_Data.xlsx)
        Sheet 'Returns'    : the 1MRet data, aligned
        Sheet 'Weights'    : the mcap weights, aligned to the returns index
        Sheet 'Benchmarks' : equal_weight, mcap_weight, us_market series

VERSION: 1.0
LAST UPDATED: 2026-06-07
AUTHOR: Arjun Divecha (ported by Claude Code)

DEPENDENCIES:
    - pandas, numpy, openpyxl

USAGE:
    python scripts/build_benchmark_rets.py
    python scripts/build_benchmark_rets.py --master "/path/T2 Master.xlsx" \
        --output "/path/Portfolio_Data.xlsx"

NOTES:
    - The benchmark math is preserved bit-for-bit from the original Step Two
      Point Five (mean / mcap-weighted / U.S.), including the all-NaN-last-row
      handling that keeps the most recent (incomplete) month as NaN.
    - Uses the openpyxl engine (ASADO venv) instead of xlsxwriter; date cells
      are written as datetimes, read back via pandas index_col=0 + to_datetime.
=============================================================================
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, Tuple

import numpy as np
import pandas as pd

T2_FUZZY_DIR = Path(
    "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/t2"
)
DEFAULT_MASTER = T2_FUZZY_DIR / "T2 Master.xlsx"


def read_data(master_path: Path, return_sheet: str = "1MRet"
              ) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Read monthly returns + mcap weights from the T2 Master workbook."""
    print(f"Reading data from {master_path} ...")
    returns = pd.read_excel(master_path, sheet_name=return_sheet, index_col=0)
    returns.index = pd.to_datetime(returns.index)
    print(f"  {return_sheet}: shape={returns.shape} range={returns.index[0].date()}..{returns.index[-1].date()}")

    weights_raw = pd.read_excel(master_path, sheet_name="Mcap Weights", index_col=0)
    # Re-index weights onto the returns index (rows assumed in the same order),
    # padding/truncating to match — preserved from the original script.
    if len(weights_raw) != len(returns):
        print(f"  WARNING: weights rows ({len(weights_raw)}) != returns rows ({len(returns)})")
        if len(weights_raw) < len(returns):
            missing = len(returns) - len(weights_raw)
            padding = pd.DataFrame(0, index=returns.index[-missing:], columns=weights_raw.columns)
            weights = pd.DataFrame(weights_raw.values, index=returns.index[:-missing], columns=weights_raw.columns)
            weights = pd.concat([weights, padding])
        else:
            weights = pd.DataFrame(weights_raw.iloc[:len(returns)].values, index=returns.index, columns=weights_raw.columns)
    else:
        weights = pd.DataFrame(weights_raw.values, index=returns.index, columns=weights_raw.columns)

    common = returns.columns.intersection(weights.columns)
    if len(common) == 0:
        print("ERROR: no common assets between returns and weights", file=sys.stderr)
        sys.exit(1)
    returns = returns.loc[:, common]
    weights = weights.loc[:, common]
    print(f"  aligned: {len(common)} common assets, {len(returns)} rows")
    return returns, weights


def prepare_benchmark_data(returns: pd.DataFrame, weights: pd.DataFrame) -> Dict[str, pd.Series]:
    """Equal-weight / mcap-weight / US-market benchmark series."""
    has_nan_last = bool(returns.iloc[-1].isna().all())
    calc_r = returns[:-1] if has_nan_last else returns
    calc_w = weights[:-1] if has_nan_last else weights

    equal_weight = calc_r.mean(axis=1)
    mcap_weight = (calc_r * calc_w).sum(axis=1)
    if "U.S." in calc_r.columns:
        us_market = calc_r["U.S."]
    elif "SPX" in calc_r.columns:
        us_market = calc_r["SPX"]
    else:
        us_market = calc_r.iloc[:, 0]
        print(f"  WARNING: 'U.S.' not found; using {calc_r.columns[0]!r} as US proxy")

    benchmarks = {"equal_weight": equal_weight, "mcap_weight": mcap_weight, "us_market": us_market}
    if has_nan_last:
        last_date = returns.index[-1]
        for k in benchmarks:
            benchmarks[k] = pd.concat([benchmarks[k], pd.Series([np.nan], index=[last_date])])

    for name, s in benchmarks.items():
        clean = s.dropna()
        print(f"  {name}: mean={clean.mean():.4%} ann={(1+clean.mean())**12-1:.4%} last={s.dropna().index[-1].date()}")
    return benchmarks


def save_data(returns: pd.DataFrame, weights: pd.DataFrame,
              benchmarks: Dict[str, pd.Series], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        returns.to_excel(writer, sheet_name="Returns")
        weights.to_excel(writer, sheet_name="Weights")
        pd.DataFrame(benchmarks).to_excel(writer, sheet_name="Benchmarks")
    print(f"  saved {output_path} (returns {returns.index[0].date()}..{returns.index[-1].date()}, {len(returns)} rows)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Build Portfolio_Data.xlsx (benchmark returns) from T2 Master.")
    ap.add_argument("--master", default=str(DEFAULT_MASTER),
                    help="Path to T2 Master.xlsx (default: T2 Factor Timing Fuzzy/T2 Master.xlsx).")
    ap.add_argument("--output", default="",
                    help="Output Portfolio_Data.xlsx path (default: <master dir>/Portfolio_Data.xlsx).")
    ap.add_argument("--return-sheet", default="1MRet")
    args = ap.parse_args()

    master_path = Path(args.master).expanduser()
    if not master_path.exists():
        print(f"ERROR: T2 Master not found: {master_path}", file=sys.stderr)
        return 1
    output_path = Path(args.output).expanduser() if args.output else master_path.parent / "Portfolio_Data.xlsx"

    returns, weights = read_data(master_path, args.return_sheet)
    benchmarks = prepare_benchmark_data(returns, weights)
    save_data(returns, weights, benchmarks, output_path)
    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
