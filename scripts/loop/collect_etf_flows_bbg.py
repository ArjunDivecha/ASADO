#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/collect_etf_flows_bbg.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/etf_t2_map.json
    Curated T2 country -> primary US-listed country ETF (34 ETFs).
- Bloomberg Terminal via OpusBloomberg (network source):
    Per ETF, daily history of EQY_SH_OUT (shares outstanding, millions),
    FUND_NET_ASSET_VAL (NAV per share, USD), FUND_TOTAL_ASSETS (AUM, USD mn),
    plus semi-monthly SHORT_INT (shares short) and SHORT_INT_RATIO
    (days-to-cover) on FINRA settlement dates.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/etf_flows.parquet
    Tidy panel (date, country, etf, value, variable, source='bloomberg'):
      ETF_SHARES_OUT_MN   shares outstanding, millions
      ETF_NAV_USD         NAV per share, USD
      ETF_AUM_USD_MN      total fund assets, USD millions
      ETF_SHORT_INT_SH    shares short (semi-monthly FINRA settle dates)
      ETF_SHORT_INT_DTC   short interest days-to-cover (semi-monthly)
    New rows win on (date, country, variable). This script does NOT touch
    DuckDB (no duckdb in the OpusBloomberg env) — see
    scripts/loop/load_etf_flows.py for the loop-DB rebuild + derived flows.

VERSION: 1.0
LAST UPDATED: 2026-06-11
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 3)

DESCRIPTION:
PRD Priority 11 (positioning layer), ETF share-count flows: for US-listed
country ETFs, daily creations/redemptions ARE the foreign-positioning tape —
when US investors pile into EWZ, the share count rises the same day. The
derived flow (computed in the loader) is dShares x NAV, in USD millions.
Covers all 34 countries — including Brazil, where no live exchange-level
foreign-flow series exists on Bloomberg (B3 monthly series died 2021-08,
BM&F futures positioning family stale since 2025-10).

Validation: EWZ 2026-06-10 — 269.15M shares x $33.83 NAV = $9,106M = AUM. ✓

DEPENDENCIES:
- OpusBloomberg conda env: blpapi, pandas, pyarrow (NOT the project venv)

USAGE:
  conda run -p "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv" \
      python scripts/loop/collect_etf_flows_bbg.py              # last 15 days
  ... collect_etf_flows_bbg.py --backfill                       # full 2010+ history

NOTES:
- Bloomberg Terminal must be logged in on the Parallels VM.
- Younger ETFs (EDEN 2012, INDA 2012, ASHR 2013) simply start later.
- Per-ticker isolation: one failing ETF never kills the run; logged loudly.
- Sanity guard: shares/NAV/AUM must be positive; a series with >5% bad
  observations aborts the run (FAIL-IS-FAIL), isolated bad prints dropped.
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg")
from bbg import BBG, bloomberg_setup  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PANEL_PATH = BASE_DIR / "Data" / "work" / "loop" / "etf_flows.parquet"
ETF_MAP_PATH = BASE_DIR / "config" / "etf_t2_map.json"

HISTORY_START = "20100101"

FIELDS = {
    "EQY_SH_OUT": "ETF_SHARES_OUT_MN",
    "FUND_NET_ASSET_VAL": "ETF_NAV_USD",
    "FUND_TOTAL_ASSETS": "ETF_AUM_USD_MN",
    # Short interest (FINRA via Bloomberg, semi-monthly settle dates only):
    "SHORT_INT": "ETF_SHORT_INT_SH",        # shares short, absolute
    "SHORT_INT_RATIO": "ETF_SHORT_INT_DTC",  # days-to-cover
}


def log(msg: str) -> None:
    print(f"[etf_flows] {msg}", flush=True)


def etf_map() -> dict[str, str]:
    m = json.loads(ETF_MAP_PATH.read_text())["map"]
    return {country: spec["primary"] for country, spec in m.items()}


def hist_series(bbg: BBG, ticker: str, field: str, start: str, end: str) -> pd.Series:
    rows = bbg.hist(ticker, field, start, end)
    if not rows:
        return pd.Series(dtype=float)
    return pd.Series(
        {pd.Timestamp(r["date"]): float(r[field]) for r in rows if r.get(field) not in (None, "")}
    ).sort_index()


def sanity_filter(s: pd.Series, label: str) -> pd.Series:
    if s.empty:
        return s
    bad = s <= 0
    if bad.any():
        if bad.mean() > 0.05:
            raise RuntimeError(f"{label}: {bad.sum()}/{len(s)} non-positive obs — refusing to write")
        log(f"  WARNING {label}: dropping {bad.sum()}/{len(s)} non-positive obs")
        s = s[~bad]
    return s


def collect(start: str, end: str) -> pd.DataFrame:
    bloomberg_setup(verbose=False)
    mapping = etf_map()
    frames: list[pd.DataFrame] = []
    n_ok = 0
    with BBG() as bbg:
        for country, etf in mapping.items():
            ticker = f"{etf} US Equity"
            got_any = False
            for field, var in FIELDS.items():
                try:
                    s = sanity_filter(hist_series(bbg, ticker, field, start, end),
                                      f"{country}/{etf} {field}")
                except Exception as e:
                    log(f"  TICKER FAILED {ticker} {field}: {e}")
                    continue
                if s.empty:
                    log(f"  WARNING {country}/{etf}: {field} returned no data")
                    continue
                frames.append(pd.DataFrame({
                    "date": s.index, "value": s.values,
                    "variable": var, "country": country, "etf": etf,
                }))
                got_any = True
            if got_any:
                n_ok += 1
    if not frames:
        raise RuntimeError("no ETF flow data collected at all")
    out = pd.concat(frames, ignore_index=True)
    out["source"] = "bloomberg"
    log(f"collected: {n_ok}/{len(mapping)} ETFs, {len(out):,} rows")
    return out[["date", "country", "etf", "value", "variable", "source"]]


def merge_and_save(new: pd.DataFrame) -> None:
    panel = pd.read_parquet(PANEL_PATH) if PANEL_PATH.exists() else pd.DataFrame(
        columns=["date", "country", "etf", "value", "variable", "source"])
    merged = pd.concat([panel, new], ignore_index=True)
    merged["date"] = pd.to_datetime(merged["date"])
    merged = merged.drop_duplicates(subset=["date", "country", "variable"], keep="last")
    merged = merged.sort_values(["country", "variable", "date"]).reset_index(drop=True)
    PANEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PANEL_PATH.with_suffix(".parquet.tmp")
    merged.to_parquet(tmp, index=False)
    tmp.replace(PANEL_PATH)
    log(f"panel: {len(merged):,} rows, {merged['date'].min().date()} -> {merged['date'].max().date()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bloomberg ETF share-count flows (loop, PRD P11).")
    parser.add_argument("--backfill", action="store_true", help="full history from 2010")
    parser.add_argument("--start", default=None, metavar="YYYY-MM-DD")
    args = parser.parse_args()

    end = date.today().strftime("%Y%m%d")
    start = (HISTORY_START if args.backfill
             else args.start.replace("-", "") if args.start
             else (date.today() - timedelta(days=15)).strftime("%Y%m%d"))
    log(f"pulling ETF shares/NAV/AUM {start} -> {end}")
    try:
        new = collect(start, end)
    except Exception as e:
        log(f"ETF FLOW PULL FAILED: {e} — existing parquet untouched")
        return 1
    merge_and_save(new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
