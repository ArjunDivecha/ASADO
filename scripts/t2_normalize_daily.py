#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/t2_normalize_daily.py
=============================================================================

DESCRIPTION:
    DAILY analog of t2_normalize.py — ASADO-internal port of the reference
    "Step Two Create Normalized Tidy.py" (T2 Factor Timing Fuzzy Daily).

    Reads the daily T2 Master workbook and produces the tidy normalized factor
    tidy outputs: the 5 daily forward-return sheets are kept RAW; every other sheet gets
    a cross-sectional (_CS) and a time-series (_TS) z-score variant, with the
    "lower is better" sheets sign-flipped. Mirrors the monthly normalize except
    the metronome (daily) and the raw-passthrough set (*DRet vs *MRet).

INPUT FILES:
    - Data/work/t2_daily/T2 Master Daily.xlsx  (build_t2_master_daily.py)

OUTPUT FILES:
    - Data/work/t2_daily/Normalized_T2_MasterCSV.csv   (tidy: date,country,value,variable)
    - Data/work/t2_daily/normalized_t2_master.parquet  (same tidy rows, parquet)

VERSION: 1.0
LAST UPDATED: 2026-06-09
AUTHOR: Arjun Divecha (ported by Claude Code)

DEPENDENCIES:
    - pandas, numpy

USAGE:
    python scripts/t2_normalize_daily.py
    python scripts/t2_normalize_daily.py --master PATH --out PATH

NOTES:
    - _CS: per-date z across countries (std ddof=1), no clip.
    - _TS: per-country expanding(min_periods=252) z (std ddof=1), std==0 -> 0.
    - Sign-flip set keyed on EXACT sheet names (several entries inert by design).
    - No ffill/fillna — NaN propagates (faithful to the reference).
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
DEFAULT_OUT = T2_DAILY_DIR / "Normalized_T2_MasterCSV.csv"
DEFAULT_OUT_PARQUET = T2_DAILY_DIR / "normalized_t2_master.parquet"

SKIP_SHEETS = ["README", "Sheet1"]
COPY_DIRECT = ["1DRet", "5DRet", "20DRet", "60DRet", "120DRet"]   # kept raw

# "lower is better" sheets — sign-flipped after z-scoring. Verbatim from the
# reference invert_norm (some names are inert: they don't match Step One outputs).
INVERT_NORM = {
    'Best Cash Flow', 'Best PBK', 'Best PE ', 'Best Price Sales', 'EV to EBITDA',
    'Shiller PE', 'Trailing PE', 'Positive PE ', 'Currency Change', 'Debt to GDP',
    'REER', 'RSI14', '10Yr Bond 12', 'Advance Decline', 'Advance_Decline_15',
    'Debt To EV', 'Bloom Country Risk', 'Bond Yield Change', '120MA Signal', 'Mcap Weights',
}


# FIX 2026-08-21: cross-sectional dispersion at or below this is treated as NO
# dispersion. Not an arbitrary tolerance -- a globally broadcast series has 34
# byte-identical values, so `value - mean` is float rounding residue (~1e-16)
# rather than exactly 0, and `std` is ~0. Dividing gave +/-inf with essentially
# random sign (the observed ~50/50 split).
CS_DISPERSION_EPS = 1e-12


def cs_zscore(df: pd.DataFrame, label: str = "") -> pd.DataFrame:
    """Per-date cross-sectional z-score across countries.

    Rows with no cross-sectional dispersion yield NaN (undefined), never +/-inf.

    Why this guard exists: `ts_zscore` below has always guarded `std == 0`; this
    function did not. Commodity sheets (Copper, Agriculture, Oil, Gold) are ONE
    global price replicated across all 34 countries, so their cross-sectional std
    is zero on EVERY date -- which is why the infinities were concentrated there
    (Copper_CS 148,546 rows, Agriculture_CS 144,364 as of 2026-08-21; 1,126,590
    infinities across t2_factors_daily in total, 3.14% of the table).

    NaN rather than 0.0 is deliberate: +/-inf poisons min/max/mean wherever these
    values are aggregated, which was the actual harm. NaN is skipped by pandas /
    SQL aggregates, whereas 0.0 would silently bias means toward zero and let a
    variable with no cross-sectional information masquerade as a real neutral
    score in factor screens.
    """
    means = df.mean(axis=1)
    stds = df.std(axis=1)   # ddof=1
    z = df.sub(means, axis=0).div(stds, axis=0)

    degenerate = ~np.isfinite(stds) | (stds.abs() <= CS_DISPERSION_EPS)
    n_bad = int(degenerate.sum())
    if n_bad:
        z.loc[degenerate, :] = np.nan
        logger.info(
            "  %s: %d of %d dates had zero cross-sectional dispersion -> _CS set NaN "
            "(globally-broadcast series carry no cross-sectional signal)",
            label or "cs_zscore", n_bad, len(stds),
        )
    return z


def ts_zscore(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index, columns=df.columns, dtype=float)
    for col in df.columns:
        s = df[col]
        mean = s.expanding(min_periods=252).mean()
        std = s.expanding(min_periods=252).std()   # ddof=1
        out[col] = np.where(std == 0, 0.0, (s - mean) / std)
    return out


def tidy(df: pd.DataFrame, variable: str) -> pd.DataFrame:
    m = df.reset_index().melt(id_vars="date", var_name="country", value_name="value")
    m["variable"] = variable
    return m[["date", "country", "value", "variable"]]


def main() -> int:
    ap = argparse.ArgumentParser(description="Daily normalize: T2 Master Daily -> tidy normalized outputs.")
    ap.add_argument("--master", default=str(DEFAULT_MASTER))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--out-parquet", default=str(DEFAULT_OUT_PARQUET))
    args = ap.parse_args()

    master = Path(args.master)
    if not master.exists():
        logger.error("Daily T2 Master not found: %s", master)
        return 1
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_parquet = Path(args.out_parquet)
    out_parquet.parent.mkdir(parents=True, exist_ok=True)

    xl = pd.ExcelFile(str(master))
    parts: list[pd.DataFrame] = []
    for sheet in xl.sheet_names:
        if sheet in SKIP_SHEETS:
            continue
        df = pd.read_excel(xl, sheet_name=sheet)
        df = df.rename(columns={df.columns[0]: "date"})
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).set_index("date")
        df.index = df.index.normalize()
        df = df.apply(pd.to_numeric, errors="coerce")
        # Deterministic _TS: the expanding (min_periods=252) z-score is
        # order-sensitive, so sort chronologically (stable) before normalizing.
        # A no-op when the daily master is already monotonic-by-date (verified),
        # but guarantees reproducible output if any sheet ever arrives unsorted.
        df = df.sort_index(kind="stable")

        if sheet in COPY_DIRECT:
            parts.append(tidy(df, sheet))
            continue
        cs = cs_zscore(df, label=sheet)
        ts = ts_zscore(df)
        if sheet in INVERT_NORM:
            cs = -cs
            ts = -ts
        parts.append(tidy(cs, f"{sheet}_CS"))
        parts.append(tidy(ts, f"{sheet}_TS"))
        logger.info("  normalized %s -> _CS/_TS", sheet)

    result = pd.concat(parts, ignore_index=True)
    result.to_csv(out_path, index=False)
    result.to_parquet(out_parquet, index=False)
    logger.info("Wrote %s and %s (%d rows, %d variables)",
                out_path, out_parquet, len(result), result["variable"].nunique())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
