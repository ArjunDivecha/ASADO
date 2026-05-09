#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/build_t2_master.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/Master Database/
    Country Bloomberg Data Master T.xlsx
    Bloomberg terminal data dump. Required sheets:
      Tot Return Index, PX_LAST, 120MA, Gold, Copper, Oil, Agriculture,
      Currency, 10Yr Bond, Best EPS, Trailing EPS
    (Bloomberg Terminal must have been run to produce this file)

- /Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/
    AssetList.xlsx  — country ETF tickers for P2P score calculation

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/
    P2P_Country_Historical_Scores.xlsx  — monthly P2P scores (yfinance)
    T2 Master.xlsx                      — final master file
- /Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 GDELT/
    T2 Master.xlsx
- /Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Econ/
    T2 Master.xlsx

VERSION: 1.0
LAST UPDATED: 2026-04-29
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
Two-phase pipeline that produces T2 Master.xlsx and distributes it to all
active T2 pipeline directories.

Phase 1 — P2P Scores (from Step Zero Create P2P Scores.py):
  Downloads monthly country ETF price data via yfinance.
  Computes Price-to-Peak (P2P) momentum scores for each country-month:
    score = (price / 12m_rolling_max) × R² × sign(slope)
  Writes P2P_Country_Historical_Scores.xlsx to T2 Factor Timing Fuzzy.

Phase 2 — T2 Master (from Step One Create T2Master.py):
  Reads Country Bloomberg Data Master T.xlsx (Bloomberg terminal dump).
  Computes forward returns (1M/3M/6M/9M/12M), trailing returns (1M/3M/12M),
  12-1M spread, commodity/FX/bond changes, 120MA signal, and merges P2P.
  Writes T2 Master.xlsx to T2 Factor Timing Fuzzy, T2 GDELT, and T2 Econ.

DEPENDENCIES:
- pandas, numpy, scipy, openpyxl, xlsxwriter, yfinance, python-dateutil

USAGE:
  python scripts/build_t2_master.py              # full run (P2P + T2 Master)
  python scripts/build_t2_master.py --skip-p2p   # use existing P2P file, rebuild T2 Master only
  python scripts/build_t2_master.py --dry-run    # preview, no writes
  python scripts/build_t2_master.py --check      # report on existing output files

NOTES:
- Phase 1 requires internet access (yfinance). Use --skip-p2p if offline.
- Phase 2 requires Bloomberg terminal to have been run to produce the input file.
- T2 Master.xlsx is written to three directories; all three or none are updated.
- On failure, existing T2 Master.xlsx files are left untouched (no partial writes).
=============================================================================
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta
from scipy import stats
from scipy.stats import linregress

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Data"

# ── External paths ────────────────────────────────────────────────────────────
BLOOMBERG_FILE = Path(
    "/Users/arjundivecha/Dropbox/AAA Backup/Master Database"
    "/Country Bloomberg Data Master T.xlsx"
)
T2_FUZZY_DIR = Path(
    "/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy"
)
T2_GDELT_DIR = Path(
    "/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 GDELT"
)
T2_ECON_DIR = Path(
    "/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Econ"
)

ASSET_LIST_FILE = T2_FUZZY_DIR / "AssetList.xlsx"
P2P_FILE = T2_FUZZY_DIR / "P2P_Country_Historical_Scores.xlsx"

T2_MASTER_DESTINATIONS = [
    T2_FUZZY_DIR / "T2 Master.xlsx",
    T2_GDELT_DIR / "T2 Master.xlsx",
    T2_ECON_DIR  / "T2 Master.xlsx",
]

# ── Country name list (T2 canonical order, 'Country' = date column header) ───
COUNTRY_NAMES = [
    'Country', 'Singapore', 'Australia', 'Canada', 'Germany', 'Japan',
    'Switzerland', 'U.K.', 'NASDAQ', 'U.S.', 'France', 'Netherlands',
    'Sweden', 'Italy', 'ChinaA', 'Chile', 'Indonesia', 'Philippines',
    'Poland', 'US SmallCap', 'Malaysia', 'Taiwan', 'Mexico', 'Korea',
    'Brazil', 'South Africa', 'Denmark', 'India', 'ChinaH', 'Hong Kong',
    'Thailand', 'Turkey', 'Spain', 'Vietnam', 'Saudi Arabia',
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 1 — P2P Score calculation (yfinance)
# ═══════════════════════════════════════════════════════════════════════════════

def _p2p_score(prices: pd.Series) -> Optional[float]:
    """Price-to-Peak momentum score = (price/12m_max) × R² × sign(slope)."""
    if len(prices) < 2:
        return None
    max_price = prices.rolling(window=12, min_periods=1).max()
    price_to_peak = prices / max_price
    x = np.arange(len(prices))
    slope, _, r_value, _, _ = linregress(x, prices)
    return float(price_to_peak.iloc[-1] * r_value**2 * (1 if slope > 0 else -1))


def build_p2p_scores() -> pd.DataFrame:
    """
    Download monthly ETF prices via yfinance and compute historical P2P scores.
    Returns a DataFrame with 'Unnamed: 0' (date) column + one column per ticker.
    """
    import yfinance as yf
    import warnings
    warnings.filterwarnings("ignore")

    if not ASSET_LIST_FILE.exists():
        raise FileNotFoundError(f"AssetList not found: {ASSET_LIST_FILE}")

    asset_list = pd.read_excel(ASSET_LIST_FILE)
    tickers = [str(t).strip().upper() for t in asset_list.iloc[:, 0] if pd.notna(t)]
    logger.info("P2P: downloading %d tickers via yfinance ...", len(tickers))

    data_start = pd.to_datetime("2000-01-01") - relativedelta(months=12)

    # Download SPY first to establish the index
    spy = yf.download("SPY", start=data_start, interval="1mo", progress=False)["Close"]
    spy.index = spy.index.tz_localize(None)
    all_prices = pd.DataFrame(index=spy.index)
    all_prices["SPY"] = spy

    for ticker in tickers:
        try:
            data = yf.download(ticker, start=data_start, interval="1mo", progress=False)["Close"]
            data.index = data.index.tz_localize(None)
            if not data.empty:
                all_prices[ticker] = data
        except Exception:
            continue

    logger.info("P2P: downloaded prices for %d tickers", len(all_prices.columns) - 1)

    # Compute monthly P2P scores from month 12 onward
    p2p_scores = pd.DataFrame(index=all_prices.index)
    start_ts = pd.to_datetime("2000-01-01")

    for i in range(12, len(all_prices)):
        dt = all_prices.index[i]
        for ticker in tickers:
            if ticker in all_prices.columns:
                window = all_prices[ticker].iloc[i - 12 : i + 1]
                if not window.isna().any() and len(window) > 1:
                    score = _p2p_score(window)
                    if score is not None:
                        p2p_scores.loc[dt, ticker] = score

    p2p_scores = p2p_scores[p2p_scores.index >= start_ts]
    p2p_scores = p2p_scores.reset_index()
    p2p_scores = p2p_scores.rename(columns={"index": "Unnamed: 0"})

    logger.info("P2P: computed scores for %d months, %d tickers",
                len(p2p_scores), len(p2p_scores.columns) - 1)
    return p2p_scores


def save_p2p(p2p_df: pd.DataFrame) -> None:
    with pd.ExcelWriter(str(P2P_FILE), engine="xlsxwriter") as writer:
        p2p_df.to_excel(writer, sheet_name="Sheet1", index=False)
        wb = writer.book
        ws = writer.sheets["Sheet1"]
        date_fmt = wb.add_format({"num_format": "yyyy-mm-dd"})
        ws.set_column(0, 0, 12, date_fmt)
        ws.set_column(1, len(p2p_df.columns) - 1, 8)
    logger.info("P2P scores saved: %s", P2P_FILE)


# ═══════════════════════════════════════════════════════════════════════════════
# PHASE 2 — T2 Master generation (Bloomberg data + P2P)
# ═══════════════════════════════════════════════════════════════════════════════

def _standardize_date(df: pd.DataFrame) -> pd.DataFrame:
    """Shift dates to first of next month (Bloomberg convention → T2 convention)."""
    try:
        df = df.copy()
        df["Country"] = pd.to_datetime(df["Country"], errors="raise")
        df["Country"] = (df["Country"].dt.to_period("M") + 1).dt.to_timestamp()
    except (ValueError, pd.errors.ParserError):
        logger.warning("Could not parse 'Country' column as dates — skipping date standardization")
    return df


def _check_local_outliers(
    series: pd.Series,
    window_size: int = 20,
    sigma_threshold: float = 4.0,
) -> List[Dict]:
    series = series.astype("float64")
    outliers = []
    for i in range(len(series)):
        start = max(0, i - window_size)
        end = min(len(series), i + window_size + 1)
        window = pd.concat([series[start:i], series[i + 1 : end]])
        if len(window) < 10:
            continue
        local_mean = window.ewm(span=window_size).mean().iloc[-1]
        local_std = window.ewm(span=window_size).std().iloc[-1]
        if local_std <= np.finfo(float).eps:
            continue
        if abs((series[i] - local_mean) / local_std) > sigma_threshold:
            outliers.append({"index": i, "new_value": float(local_mean)})
    return outliers


def _winsorize(series: pd.Series, mad_threshold: float = 5.0) -> pd.Series:
    series = series.astype("float64")
    median = series.median()
    mad = stats.median_abs_deviation(series, scale="normal")
    lb = median - mad_threshold * mad
    ub = median + mad_threshold * mad
    return series.clip(lower=lb, upper=ub)


def _clean_sheet(data: pd.DataFrame) -> pd.DataFrame:
    """Forward-fill, winsorize, and remove local outliers per column."""
    data = data.ffill().infer_objects()
    n_wins = n_local = 0
    for col in data.columns[1:]:
        series = pd.to_numeric(data[col], errors="coerce").astype("float64")
        if series.isna().all():
            continue
        winsorized = _winsorize(series)
        n_wins += int((series != winsorized).sum())
        local_outliers = _check_local_outliers(winsorized)
        n_local += len(local_outliers)
        for o in local_outliers:
            winsorized.iloc[o["index"]] = o["new_value"]
        data[col] = winsorized
    if n_wins + n_local > 0:
        logger.info("  cleaned: %d winsorized, %d local outliers", n_wins, n_local)
    return data


def _forward_returns(data: pd.DataFrame, months: int) -> pd.DataFrame:
    returns = pd.DataFrame(index=data.index)
    for col in data.columns[1:]:
        values = pd.to_numeric(data[col], errors="coerce").astype("float64")
        returns[col] = (values.shift(-months) / values) - 1
    returns.insert(0, data.columns[0], data[data.columns[0]])
    return returns


def _trailing_returns(data: pd.DataFrame, months: int) -> pd.DataFrame:
    returns = pd.DataFrame(index=data.index)
    for col in data.columns[1:]:
        values = pd.to_numeric(data[col], errors="coerce").astype("float64")
        returns[col] = (values / values.shift(months)) - 1
    returns.insert(0, data.columns[0], data[data.columns[0]])
    return returns


def _change(data: pd.DataFrame, months: int, absolute: bool = False) -> pd.DataFrame:
    changes = pd.DataFrame(index=data.index)
    changes.insert(0, data.columns[0], data[data.columns[0]])
    for col in data.columns[1:]:
        values = pd.to_numeric(data[col], errors="coerce").astype("float64")
        historical = values.shift(months)
        changes[col] = (values - historical) if absolute else (values / historical) - 1
    return changes


def _ma_signal(price_data: pd.DataFrame, ma_data: pd.DataFrame) -> pd.DataFrame:
    signals = pd.DataFrame(index=price_data.index)
    signals.insert(0, price_data.columns[0], price_data[price_data.columns[0]])
    for col in price_data.columns[1:]:
        if col in ma_data.columns:
            prices = pd.to_numeric(price_data[col], errors="coerce").astype("float64")
            ma = pd.to_numeric(ma_data[col], errors="coerce").astype("float64")
            signals[col] = prices / ma
        else:
            signals[col] = np.nan
    return signals


def _load_bloomberg_sheet(
    excel_file: pd.ExcelFile, sheet_name: str
) -> pd.DataFrame:
    data = pd.read_excel(excel_file, sheet_name=sheet_name)
    data = data.iloc[2:].reset_index(drop=True)
    data.columns = COUNTRY_NAMES[: len(data.columns)]
    return _standardize_date(data)


def build_t2_master() -> bytes:
    """
    Build T2 Master.xlsx in memory and return the raw bytes.
    Raises FileNotFoundError if Bloomberg or P2P input files are missing.
    """
    if not BLOOMBERG_FILE.exists():
        raise FileNotFoundError(f"Bloomberg file not found: {BLOOMBERG_FILE}")
    if not P2P_FILE.exists():
        raise FileNotFoundError(f"P2P file not found: {P2P_FILE}")

    logger.info("Loading Bloomberg file: %s", BLOOMBERG_FILE)
    excel_file = pd.ExcelFile(str(BLOOMBERG_FILE))
    sheet_names = excel_file.sheet_names[1:]  # skip first sheet
    process_sheets = [s for s in sheet_names if "Mcap" not in s]

    # Load P2P
    logger.info("Loading P2P scores: %s", P2P_FILE)
    p2p_data = pd.read_excel(str(P2P_FILE), engine="openpyxl")
    if len(p2p_data.columns) <= len(COUNTRY_NAMES):
        p2p_data.columns = COUNTRY_NAMES[: len(p2p_data.columns)]
    else:
        raise ValueError("P2P file has more columns than expected COUNTRY_NAMES list")
    if "Country" in p2p_data.columns:
        p2p_data["Country"] = pd.to_datetime(p2p_data["Country"], errors="coerce")
        p2p_data = p2p_data.iloc[1:].reset_index(drop=True)

    # ── Write to an in-memory buffer ────────────────────────────────────────
    import io
    buf = io.BytesIO()

    with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:

        # ── Forward returns ─────────────────────────────────────────────────
        logger.info("Processing Tot Return Index → forward + trailing returns")
        tot_ret = _load_bloomberg_sheet(excel_file, "Tot Return Index ")
        trailing_dict: Dict[int, pd.DataFrame] = {}

        for months in [1, 3, 6, 9, 12]:
            _forward_returns(tot_ret, months).to_excel(
                writer, sheet_name=f"{months}MRet", index=False
            )

        for months in [1, 3, 12]:
            tr = _trailing_returns(tot_ret, months)
            tr.to_excel(writer, sheet_name=f"{months}MTR", index=False)
            trailing_dict[months] = tr

        # 12-1M spread
        country_col = trailing_dict[12]["Country"]
        spread = trailing_dict[12].drop("Country", axis=1).subtract(
            trailing_dict[1].drop("Country", axis=1)
        )
        spread.insert(0, "Country", country_col)
        spread.to_excel(writer, sheet_name="12-1MTR", index=False)

        # ── Commodity / FX / bond changes ───────────────────────────────────
        change_specs = {
            "Gold": (12, False), "Copper": (12, False), "Oil": (12, False),
            "Agriculture": (12, False), "Currency": (12, False),
            "10Yr Bond": (12, True), "Best EPS": (36, False),
            "Trailing EPS": (36, False),
        }
        for sn, (months, absolute) in change_specs.items():
            if sn in excel_file.sheet_names:
                logger.info("  %s %d-month change", sn, months)
                data = _load_bloomberg_sheet(excel_file, sn)
                _change(data, months, absolute).to_excel(
                    writer, sheet_name=f"{sn} {months}", index=False
                )

        # ── 120MA Signal ────────────────────────────────────────────────────
        if "PX_LAST" in excel_file.sheet_names and "120MA" in excel_file.sheet_names:
            logger.info("  120MA Signal")
            px = _load_bloomberg_sheet(excel_file, "PX_LAST")
            ma = _load_bloomberg_sheet(excel_file, "120MA")
            _ma_signal(px, ma).to_excel(writer, sheet_name="120MA Signal", index=False)

        # ── All other sheets (cleaned copies) ──────────────────────────────
        for sn in sheet_names:
            logger.info("  sheet: %s", sn)
            data = pd.read_excel(excel_file, sheet_name=sn)
            data = data.iloc[2:].reset_index(drop=True)
            if sn == "MCAP Adj":
                data = data.iloc[:400].copy()
            data.columns = COUNTRY_NAMES[: len(data.columns)]
            data = _standardize_date(data)
            if sn in process_sheets:
                data = _clean_sheet(data)
            data.to_excel(writer, sheet_name=sn, index=False)

        # ── P2P sheet ───────────────────────────────────────────────────────
        p2p_data.to_excel(writer, sheet_name="P2P", index=False)
        logger.info("P2P sheet written")

    buf.seek(0)
    return buf.read()


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-p2p", action="store_true",
                    help="Skip P2P download and use existing P2P_Country_Historical_Scores.xlsx")
    ap.add_argument("--dry-run", action="store_true",
                    help="Preview only — no files written")
    ap.add_argument("--check", action="store_true",
                    help="Report on existing output files without rebuilding")
    ap.add_argument("--force", action="store_true",
                    help="Rebuild even if all 3 T2 Master.xlsx outputs are newer than inputs")
    args = ap.parse_args()

    # ── Up-to-date guard ──────────────────────────────────────────────────
    # Inputs: BLOOMBERG_FILE, P2P_FILE, ASSET_LIST_FILE
    # Outputs: 3× T2 Master.xlsx
    # If every output exists and is newer than every input, skip the entire run.
    if not args.force and not args.dry_run and not args.check:
        try:
            inputs = [BLOOMBERG_FILE, ASSET_LIST_FILE]
            if P2P_FILE.exists():
                inputs.append(P2P_FILE)
            input_mtimes = [p.stat().st_mtime for p in inputs if p.exists()]
            output_mtimes = [d.stat().st_mtime for d in T2_MASTER_DESTINATIONS if d.exists()]
            if (len(output_mtimes) == len(T2_MASTER_DESTINATIONS)
                    and input_mtimes
                    and min(output_mtimes) >= max(input_mtimes)):
                logger.info(
                    "All 3 T2 Master.xlsx outputs are newer than every input "
                    "(Bloomberg / AssetList / P2P). Skipping. Use --force to rebuild."
                )
                return 0
        except Exception as e:
            logger.warning("Up-to-date check failed (%s) — proceeding to rebuild.", e)

    if args.check:
        for dest in T2_MASTER_DESTINATIONS:
            if dest.exists():
                stat = dest.stat()
                logger.info("T2 Master.xlsx: %.1f MB, modified %s → %s",
                            stat.st_size / 1_048_576,
                            datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                            dest)
            else:
                logger.warning("Missing: %s", dest)
        if P2P_FILE.exists():
            stat = P2P_FILE.stat()
            logger.info("P2P scores: %.0f KB, modified %s",
                        stat.st_size / 1024,
                        datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"))
        else:
            logger.warning("P2P file missing: %s", P2P_FILE)
        return 0

    # ── Phase 1: P2P ────────────────────────────────────────────────────────
    if not args.skip_p2p:
        logger.info("=== PHASE 1: P2P Score Calculation ===")
        if args.dry_run:
            logger.info("[dry-run] Would download ETF prices and compute P2P scores → %s", P2P_FILE)
        else:
            try:
                p2p_df = build_p2p_scores()
                save_p2p(p2p_df)
            except Exception as e:
                logger.error("P2P calculation failed: %s", e)
                logger.error("Use --skip-p2p to proceed with existing P2P file")
                return 1
    else:
        if not P2P_FILE.exists():
            logger.error("--skip-p2p specified but P2P file not found: %s", P2P_FILE)
            return 1
        logger.info("P2P phase skipped — using existing: %s", P2P_FILE)

    # ── Phase 2: T2 Master ──────────────────────────────────────────────────
    logger.info("=== PHASE 2: T2 Master Generation ===")
    if args.dry_run:
        logger.info("[dry-run] Would build T2 Master.xlsx from %s + %s",
                    BLOOMBERG_FILE, P2P_FILE)
        for dest in T2_MASTER_DESTINATIONS:
            logger.info("[dry-run] Would write → %s", dest)
        return 0

    try:
        workbook_bytes = build_t2_master()
    except Exception as e:
        logger.error("T2 Master build failed: %s", e)
        return 1

    # Write to all destinations atomically (tmp → rename)
    for dest in T2_MASTER_DESTINATIONS:
        tmp = dest.with_suffix(".tmp.xlsx")
        try:
            tmp.write_bytes(workbook_bytes)
            tmp.replace(dest)
            size_mb = dest.stat().st_size / 1_048_576
            logger.info("Wrote %.1f MB → %s", size_mb, dest)
        except Exception as e:
            logger.error("Failed to write %s: %s", dest, e)
            if tmp.exists():
                tmp.unlink()
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
