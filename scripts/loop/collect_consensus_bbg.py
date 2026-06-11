#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/collect_consensus_bbg.py
=============================================================================

INPUT FILES:
- Bloomberg Terminal via OpusBloomberg (network source):
    Year-specific ECFC consensus tickers, daily history:
      ECGD{ISO2} {YY} Index — consensus GDP growth forecast for target year
      ECPI{ISO2} {YY} Index — consensus CPI inflation forecast for target year
    Verified 2026-06-11: this family uses ISO-2 codes (CN=China,
    CH=Switzerland, BR/JP/KR/TR), NOT the legacy 2-letter codes used by the
    monthly collector's rolling ECGD tickers (BZ/JN/KO/TU/SW).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/consensus_daily.parquet
    Tidy panel (date, country, target_year, value, variable, source):
      CONS_GDP_PCT — consensus real GDP growth forecast, %
      CONS_CPI_PCT — consensus CPI inflation forecast, %
    New rows win on (date, country, target_year, variable). No DuckDB here
    (no duckdb in the OpusBloomberg env) — scripts/loop/load_consensus.py
    rebuilds the loop-DB table.

VERSION: 1.0
LAST UPDATED: 2026-06-11
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 3)

DESCRIPTION:
PRD Priority 9 stretch — densify the surprise surface between WEO vintages.
IMF WEO gives 2 forecast snapshots per year; Bloomberg's ECFC consensus
updates DAILY as sell-side economists revise. The year-specific tickers
(e.g. ECGDUS 26 Index) store the full revision path for one target year,
so a single history pull rebuilds years of consensus-revision data — no
forward snapshot accumulation needed. A 10th grader's version: the IMF
publishes its class notes twice a year; Bloomberg's economist survey is the
group chat, updating every day. This pulls the group chat's full history.

DEPENDENCIES:
- OpusBloomberg conda env: blpapi, pandas, pyarrow (NOT the project venv)

USAGE:
  conda run -p "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv" \
      python scripts/loop/collect_consensus_bbg.py             # current + next target year, last 15d
  ... collect_consensus_bbg.py --backfill                      # target years 2008..next, full history

NOTES:
- 34 T2 countries collapse to 31 distinct economies (ChinaA/H share CN;
  U.S./NASDAQ/US SmallCap share US); the parquet stores all 34 names.
- Per-ticker isolation: a missing (country, year) combination is logged and
  skipped — old target years legitimately don't exist for some EMs.
- Backfill is ~1,200 hist calls (~7 min). Nightly incremental is ~120.
=============================================================================
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg")
from bbg import BBG, bloomberg_setup  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PANEL_PATH = BASE_DIR / "Data" / "work" / "loop" / "consensus_daily.parquet"

BACKFILL_FIRST_TARGET_YEAR = 2008

# T2 name -> ISO-2 code for the year-specific ECFC ticker family.
ISO2 = {
    "Australia": "AU", "Brazil": "BR", "Canada": "CA", "Chile": "CL",
    "ChinaA": "CN", "ChinaH": "CN", "Denmark": "DK", "France": "FR",
    "Germany": "DE", "Hong Kong": "HK", "India": "IN", "Indonesia": "ID",
    "Italy": "IT", "Japan": "JP", "Korea": "KR", "Malaysia": "MY",
    "Mexico": "MX", "NASDAQ": "US", "Netherlands": "NL", "Philippines": "PH",
    "Poland": "PL", "Saudi Arabia": "SA", "Singapore": "SG",
    "South Africa": "ZA", "Spain": "ES", "Sweden": "SE", "Switzerland": "CH",
    "Taiwan": "TW", "Thailand": "TH", "Turkey": "TR", "U.K.": "GB",
    "U.S.": "US", "US SmallCap": "US", "Vietnam": "VN",
}

METRICS = {"ECGD": "CONS_GDP_PCT", "ECPI": "CONS_CPI_PCT"}


def log(msg: str) -> None:
    print(f"[consensus] {msg}", flush=True)


def collect(target_years: list[int], start: str, end: str) -> pd.DataFrame:
    bloomberg_setup(verbose=False)
    frames: list[pd.DataFrame] = []
    n_hit = n_miss = 0
    codes = sorted(set(ISO2.values()))
    code_to_countries: dict[str, list[str]] = {}
    for country, cc in ISO2.items():
        code_to_countries.setdefault(cc, []).append(country)

    with BBG() as bbg:
        for cc in codes:
            for prefix, var in METRICS.items():
                for yr in target_years:
                    ticker = f"{prefix}{cc} {yr % 100:02d} Index"
                    try:
                        rows = bbg.hist(ticker, "PX_LAST", start, end)
                    except Exception as e:
                        log(f"  TICKER FAILED {ticker}: {e}")
                        n_miss += 1
                        continue
                    vals = [(pd.Timestamp(r["date"]), float(r["PX_LAST"]))
                            for r in rows if r.get("PX_LAST") not in (None, "")]
                    if not vals:
                        n_miss += 1
                        continue
                    n_hit += 1
                    dates, values = zip(*vals)
                    for country in code_to_countries[cc]:
                        frames.append(pd.DataFrame({
                            "date": dates, "country": country, "target_year": yr,
                            "value": values, "variable": var,
                        }))
    if not frames:
        raise RuntimeError("no consensus data collected at all")
    out = pd.concat(frames, ignore_index=True)
    out["source"] = "bloomberg_ecfc"
    log(f"collected: {n_hit} live series, {n_miss} empty/missing, {len(out):,} rows")
    return out


def merge_and_save(new: pd.DataFrame) -> None:
    panel = pd.read_parquet(PANEL_PATH) if PANEL_PATH.exists() else pd.DataFrame(
        columns=["date", "country", "target_year", "value", "variable", "source"])
    merged = pd.concat([panel, new], ignore_index=True)
    merged["date"] = pd.to_datetime(merged["date"])
    merged = merged.drop_duplicates(subset=["date", "country", "target_year", "variable"], keep="last")
    merged = merged.sort_values(["country", "variable", "target_year", "date"]).reset_index(drop=True)
    PANEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PANEL_PATH.with_suffix(".parquet.tmp")
    merged.to_parquet(tmp, index=False)
    tmp.replace(PANEL_PATH)
    log(f"panel: {len(merged):,} rows, {merged['date'].min().date()} -> {merged['date'].max().date()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bloomberg ECFC consensus forecast history (loop, PRD P9 stretch).")
    parser.add_argument("--backfill", action="store_true",
                        help=f"target years {BACKFILL_FIRST_TARGET_YEAR}..next, full history")
    args = parser.parse_args()

    this_year = date.today().year
    if args.backfill:
        target_years = list(range(BACKFILL_FIRST_TARGET_YEAR, this_year + 2))
        start = f"{BACKFILL_FIRST_TARGET_YEAR - 2}0101"
    else:
        target_years = [this_year, this_year + 1]
        start = (date.today() - timedelta(days=15)).strftime("%Y%m%d")
    end = date.today().strftime("%Y%m%d")

    log(f"target years {target_years[0]}..{target_years[-1]}, window {start} -> {end}")
    try:
        new = collect(target_years, start, end)
    except Exception as e:
        log(f"CONSENSUS PULL FAILED: {e} — existing parquet untouched")
        return 1
    merge_and_save(new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
