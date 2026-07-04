"""
=============================================================================
SCRIPT NAME: pull_overnight_equity_bars.py
=============================================================================

INPUT FILES:
- Bloomberg Terminal via OpusBloomberg BBG wrapper (live BLPAPI connection,
  no local input file)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/predmkt_equity/markets.parquet
  (read only to derive the ticker list; falls back to the hardcoded list
  below if absent)

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/predmkt_equity/equity_bars.parquet
  Daily OHLC bars per ticker: date, ticker, px_open, px_last. Used to label
  realized overnight gaps (open_d+1 vs close_d) and open->close continuation
  returns for the M5 backtest.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/predmkt_equity/bbg_backups/{ts}/equity_bars.parquet
  Timestamped backup of any existing bars file before overwrite (Bloomberg
  data preservation rule).

VERSION: 1.0
LAST UPDATED: 2026-07-03
AUTHOR: Claude Code (for Arjun Divecha)

DESCRIPTION:
Milestone M5b of the Tier 1 overnight prediction-market -> equity signal.
Pulls daily open and close prices from Bloomberg for every US ticker in the
Polymarket firm-market universe, from 2026-03-20 to today. The overnight gap
r_gap = log(open_{d+1} / close_d) and the continuation return
r_cont = log(close_{d+1} / open_{d+1}) are computed downstream in
backtest_overnight_signal.py.

DEPENDENCIES:
- OpusBloomberg conda env (blpapi, pandas, pyarrow)

USAGE:
  conda run -p "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv" \
    python scripts/pull_overnight_equity_bars.py

NOTES:
- Bloomberg Terminal must be logged in on the Parallels VM.
- All tickers are US-listed (single names + ETFs SPY/QQQ/EWY/SPCX).
- Appends to the shared BBG quota log convention is not needed here (this is
  a tiny one-off pull: ~19 tickers x 2 fields x ~70 days).
=============================================================================
"""

from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg")
from bbg import BBG, bloomberg_setup  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent
WORK_DIR = BASE_DIR / "Data" / "work" / "predmkt_equity"
MARKETS_PATH = WORK_DIR / "markets.parquet"
OUT_PATH = WORK_DIR / "equity_bars.parquet"
BACKUP_DIR = WORK_DIR / "bbg_backups"

START = "20260320"
END = datetime.now().strftime("%Y%m%d")

FALLBACK_TICKERS = [
    "AAPL", "AMZN", "GOOGL", "META", "MSFT", "NVDA", "TSLA", "MU", "PLTR",
    "NFLX", "OPEN", "SPCX", "SPY", "ABNB", "COIN", "EWY", "HOOD", "RKLB", "MSTR",
]


def get_tickers() -> list[str]:
    if MARKETS_PATH.exists():
        tickers = sorted(pd.read_parquet(MARKETS_PATH)["ticker"].dropna().unique())
        if tickers:
            return list(tickers)
    return FALLBACK_TICKERS


def main() -> int:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    if OUT_PATH.exists():
        ts = datetime.now().strftime("%Y_%m_%d_%H%M%S")
        bdir = BACKUP_DIR / ts
        bdir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(OUT_PATH, bdir / OUT_PATH.name)
        print(f"Backed up existing bars to {bdir}")

    tickers = get_tickers()
    print(f"Pulling daily open/close for {len(tickers)} tickers, {START}->{END}")

    bloomberg_setup()
    frames: list[pd.DataFrame] = []
    failures: list[str] = []
    with BBG() as bbg:
        for ticker in tickers:
            sec = f"{ticker} US Equity"
            try:
                rows = bbg.hist(sec, ["PX_OPEN", "PX_LAST"], START, END)
            except Exception as exc:  # per-source isolation, house style
                print(f"  ❌ {sec}: {exc}")
                failures.append(ticker)
                continue
            if not rows:
                print(f"  ❌ {sec}: empty history")
                failures.append(ticker)
                continue
            df = pd.DataFrame(rows)
            df = df.rename(columns={"PX_OPEN": "px_open", "PX_LAST": "px_last"})
            for col in ("px_open", "px_last"):
                if col not in df.columns:
                    df[col] = pd.NA
                df[col] = pd.to_numeric(df[col], errors="coerce")
            df["ticker"] = ticker
            frames.append(df[["date", "ticker", "px_open", "px_last"]])
            print(f"  ✓ {sec}: {len(df)} days")

    if not frames:
        print("❌ No equity bars pulled — aborting without writing.")
        return 1
    out = pd.concat(frames, ignore_index=True)
    out["date"] = pd.to_datetime(out["date"])
    out = out.sort_values(["ticker", "date"]).reset_index(drop=True)
    out.to_parquet(OUT_PATH, index=False)
    print(f"Wrote {len(out)} rows for {out['ticker'].nunique()} tickers -> {OUT_PATH}")
    if failures:
        print(f"⚠️  failed tickers: {failures}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
