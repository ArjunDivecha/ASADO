#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/collect_foreign_flows_bbg.py
=============================================================================

INPUT FILES:
- Bloomberg Terminal via OpusBloomberg (network source, no local input file)
    Exchange-sourced daily foreign investor flow indices, discovered and
    verified 2026-06-10 via //blp/instruments + history pulls:

      Korea       KPCPNTFR Index  KOSPI foreign net buy value (KRW mn, 2005+)
                  KQCPNTFR Index  KOSDAQ foreign net buy value (KRW mn, 2005+)
      Taiwan      TAFINET Index   TWSE foreign total equity net (TWD mn, 2005+)
                  TAFIBUY Index / TAFISELL Index  gross (TWD mn)
      Thailand    THIVNET$ Index  SET foreign net flows (USD mn, 2005+)
      Philippines VUPHBNET Index  PSE net foreign investment (USD mn, 2005+)
      Indonesia   JASXFIBA Index / JASXFISA Index  IDX foreign buy/sell
                  value (IDR mn, 2005+); net = buy - sell
      FX          USDKRW / USDTWD / USDIDR Curncy  for USD conversion

- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/foreign_flows.parquet
    Existing tidy flows panel (read for merge; NSDL India rows live here too).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/foreign_flows.parquet
    Same panel, merged: (date, country, value, variable, source). Bloomberg
    rows carry source='bloomberg'. New rows win on (date, country, variable).
    NOTE: this script does NOT write DuckDB (the OpusBloomberg env has no
    duckdb). scripts/loop/collect_foreign_flows.py — which runs right after
    it in loop_daily_job.py — rebuilds the loop-DB table from this parquet.

VERSION: 1.0
LAST UPDATED: 2026-06-10
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 3)

DESCRIPTION:
Foreign investor flows for the markets whose exchange websites geo-block
this network (Korea, Taiwan, Thailand, Indonesia, Philippines) — pulled
from Bloomberg instead, which carries the exchanges' own published series.
Cross-validated against India: Bloomberg FIINNET$ on 2026-06-09 = -406.3
USD mn, identical to NSDL's 10-Jun reporting-date row (-406.29), confirming
Bloomberg uses TRADE dates (NSDL reports T+1). India itself stays with the
NSDL collector (depository-confirmed, no Terminal dependency); Bloomberg
covers the other markets.

Harmonized variables per country (USD million):
    FOREIGN_EQUITY_NET_USD_MN          all five markets
    FOREIGN_EQUITY_GROSS_BUY_USD_MN    Taiwan, Indonesia
    FOREIGN_EQUITY_GROSS_SELL_USD_MN   Taiwan, Indonesia

KRW/TWD/IDR series are converted with same-day Bloomberg FX closes
(forward-filled over local FX holidays). Unit sanity guard: any implied
single-day |net| > USD 20bn aborts the run (units changed upstream).

DEPENDENCIES:
- OpusBloomberg conda env: blpapi, pandas, pyarrow (NOT the project venv)

USAGE:
  conda run -p "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv" \
      python scripts/loop/collect_foreign_flows_bbg.py              # last 15 days
  ... collect_foreign_flows_bbg.py --backfill                       # full 2005+ history
  ... collect_foreign_flows_bbg.py --start 2024-01-01               # custom window

NOTES:
- Bloomberg Terminal must be logged in on the Parallels VM.
- FAIL-IS-FAIL: connection or pull errors abort with a clear message; the
  existing parquet is never touched on failure.
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
PANEL_PATH = BASE_DIR / "Data" / "work" / "loop" / "foreign_flows.parquet"

HISTORY_START = "20050101"
SANITY_MAX_USD_MN = 20_000.0  # no real market has a $20bn single-day foreign net flow

# market spec: country -> (net tickers to sum, gross buy, gross sell, fx ticker or None)
MARKETS = {
    "Korea": {
        "net": ["KPCPNTFR Index", "KQCPNTFR Index"],  # KOSPI + KOSDAQ, KRW mn
        "buy": None, "sell": None, "fx": "USDKRW Curncy",
    },
    "Taiwan": {
        "net": ["TAFINET Index"],                      # TWD mn
        "buy": "TAFIBUY Index", "sell": "TAFISELL Index", "fx": "USDTWD Curncy",
    },
    "Thailand": {
        "net": ["THIVNET$ Index"],                     # already USD mn
        "buy": None, "sell": None, "fx": None,
    },
    "Philippines": {
        "net": ["VUPHBNET Index"],                     # already USD mn
        "buy": None, "sell": None, "fx": None,
    },
    "Indonesia": {
        "net": None,                                   # net = buy - sell, IDR mn
        "buy": "JASXFIBA Index", "sell": "JASXFISA Index", "fx": "USDIDR Curncy",
    },
}


def hist_series(bbg: BBG, ticker: str, start: str, end: str) -> pd.Series:
    """One ticker's PX_LAST history as a float Series indexed by date."""
    rows = bbg.hist(ticker, "PX_LAST", start, end)
    if not rows:
        return pd.Series(dtype=float)
    s = pd.Series(
        {pd.Timestamp(r["date"]): float(r["PX_LAST"]) for r in rows if r.get("PX_LAST") not in (None, "")}
    ).sort_index()
    s.name = ticker
    return s


def collect(start: str, end: str) -> pd.DataFrame:
    """Pull all markets, harmonize to USD mn, return tidy DataFrame."""
    bloomberg_setup(verbose=False)
    records: list[pd.DataFrame] = []
    with BBG() as bbg:
        # FX first (shared across markets)
        fx: dict[str, pd.Series] = {}
        for spec in MARKETS.values():
            t = spec["fx"]
            if t and t not in fx:
                fx[t] = hist_series(bbg, t, start, end)
                if fx[t].empty:
                    raise RuntimeError(f"FX pull returned no data for {t} — aborting (cannot convert)")

        for country, spec in MARKETS.items():
            buy = hist_series(bbg, spec["buy"], start, end) if spec["buy"] else None
            sell = hist_series(bbg, spec["sell"], start, end) if spec["sell"] else None
            if spec["net"]:
                parts = [hist_series(bbg, t, start, end) for t in spec["net"]]
                net = pd.concat(parts, axis=1).sum(axis=1, min_count=1).dropna()
            else:
                net = (buy - sell).dropna()

            if net.empty:
                raise RuntimeError(f"{country}: net flow pull returned no data — aborting")

            out = pd.DataFrame({"FOREIGN_EQUITY_NET_USD_MN": net})
            if buy is not None and sell is not None:
                out["FOREIGN_EQUITY_GROSS_BUY_USD_MN"] = buy
                out["FOREIGN_EQUITY_GROSS_SELL_USD_MN"] = sell

            if spec["fx"]:
                rate = fx[spec["fx"]].reindex(
                    out.index.union(fx[spec["fx"]].index)
                ).ffill().reindex(out.index)
                out = out.div(rate, axis=0)
            out = out.dropna(how="all")

            worst = out["FOREIGN_EQUITY_NET_USD_MN"].abs().max()
            if worst > SANITY_MAX_USD_MN:
                raise RuntimeError(
                    f"{country}: implied |net| max {worst:,.0f} USD mn exceeds sanity cap "
                    f"{SANITY_MAX_USD_MN:,.0f} — upstream units changed, refusing to write"
                )

            tidy = out.reset_index(names="date").melt(
                id_vars="date", var_name="variable", value_name="value"
            ).dropna(subset=["value"])
            tidy["country"] = country
            tidy["source"] = "bloomberg"
            records.append(tidy[["date", "country", "value", "variable", "source"]])
            print(f"  {country:<12} {len(out):>5} days  {out.index.min().date()} -> {out.index.max().date()}  "
                  f"last net {out['FOREIGN_EQUITY_NET_USD_MN'].iloc[-1]:+,.0f} USD mn")

    return pd.concat(records, ignore_index=True)


def merge_and_save(new: pd.DataFrame) -> None:
    panel = pd.read_parquet(PANEL_PATH) if PANEL_PATH.exists() else pd.DataFrame(
        columns=["date", "country", "value", "variable", "source"])
    merged = pd.concat([panel, new], ignore_index=True)
    merged["date"] = pd.to_datetime(merged["date"])
    merged = merged.drop_duplicates(subset=["date", "country", "variable"], keep="last")
    merged = merged.sort_values(["country", "date", "variable"]).reset_index(drop=True)
    PANEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PANEL_PATH.with_suffix(".parquet.tmp")
    merged.to_parquet(tmp, index=False)
    tmp.replace(PANEL_PATH)
    print(f"panel: {len(merged)} rows, {merged['date'].min().date()} -> {merged['date'].max().date()}, "
          f"{merged['country'].nunique()} countries")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bloomberg foreign investor flows (KR/TW/TH/PH/ID).")
    parser.add_argument("--backfill", action="store_true", help="full history from 2005")
    parser.add_argument("--start", default=None, metavar="YYYY-MM-DD", help="custom start date")
    args = parser.parse_args()

    end = date.today().strftime("%Y%m%d")
    if args.backfill:
        start = HISTORY_START
    elif args.start:
        start = args.start.replace("-", "")
    else:
        start = (date.today() - timedelta(days=15)).strftime("%Y%m%d")

    print(f"Pulling foreign flows {start} -> {end} for {', '.join(MARKETS)}")
    try:
        new = collect(start, end)
    except Exception as e:
        print(f"BLOOMBERG FLOWS FAILED: {e} — existing parquet untouched")
        return 1
    merge_and_save(new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
