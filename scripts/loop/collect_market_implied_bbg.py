#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/collect_market_implied_bbg.py
=============================================================================

INPUT FILES:
- Bloomberg Terminal via OpusBloomberg (network source, no local input file).
    Three families of daily market-implied series, every ticker verified
    with a live 1-security test pull (2026-06-11 for the v1.0 set,
    2026-06-12 for the v1.1 additions) before first batch use:
      1. FX options surfaces — for 24 T2 currency pairs (majors, LatAm,
         CEEMEA, NDF Asia, and the HKD/SAR pegs):
           1M ATM implied vol      [PAIR]V1M Curncy
           1W ATM implied vol      [PAIR]V1W Curncy    (v1.1)
           3M ATM implied vol      [PAIR]V3M Curncy    (v1.1)
           25-delta 1M risk rev.   [PAIR]25R1M Curncy
           25-delta 1M butterfly   [PAIR]25B1M Curncy  (v1.1)
      2. FX 3M forwards + spot (v1.2) — outright forward tickers
         ([ROOT]3M Curncy, e.g. BCN3M = USDBRL NDF, KWN3M = USDKRW NDF)
         plus the spot pair, for 25 pairs (the 24 vol pairs + USDDKK:
         Denmark has no options surface but has a liquid forward).
         Verified live 2026-06-12: PX_LAST on these tickers is the
         OUTRIGHT forward rate, not points.
      3. Global risk dashboard — VIX, VIX3M, MOVE, US HY OAS (LF98OAS),
         US IG OAS (LUACOAS), DXY, BBDXY.
      4. Commodity futures curve — generic 1st and 2nd contracts for WTI
         (CL), Brent (CO), copper (HG), gold (GC), US natgas (NG).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/market_implied_daily.parquet
    Tidy panel (date, country, value, variable, source='bloomberg').
    FX rows carry the mapped T2 country (EUR pairs broadcast to France,
    Germany, Italy, Netherlands, Spain; USDCNH to ChinaA+ChinaH); risk
    dashboard and commodity rows carry country='GLOBAL'. Variables:
      FX_IMPVOL_1M_PCT     1M ATM implied vol, annualized %
      FX_IMPVOL_1W_PCT     1W ATM implied vol (v1.1) — with 3M gives the
                           vol TERM SLOPE: 1W >> 3M = stress priced NOW
      FX_IMPVOL_3M_PCT     3M ATM implied vol (v1.1)
      FX_RR25_1M_PCT       25-delta 1M risk reversal, vol points,
                           SIGN-NORMALIZED so positive = options market
                           paying a premium for LOCAL-currency depreciation
                           (USD-base pairs keep raw sign; XXXUSD pairs are
                           flipped). USD itself has no pair (numeraire).
      FX_BF25_1M_PCT       25-delta 1M butterfly, vol points (v1.1) — the
                           tail/kurtosis premium; symmetric, NO sign flip
      FX_CARRY_3M_PCT      forward-implied carry, annualized % (v1.2):
                           (fwd/spot - 1) * 4 * 100, SIGN-NORMALIZED so
                           positive = LOCAL short rates above USD (the
                           classic carry-trade long leg). NDF-implied for
                           capital-controlled currencies (KRW, TWD, INR,
                           IDR, MYR, PHP, BRL, CLP) — the offshore-implied
                           rate, which is exactly what a foreign investor
                           can actually capture.
      RISK_<NAME>          VIX / VIX3M / MOVE / HY_OAS / IG_OAS / DXY / BBDXY
      CMD_<ROOT><1|2>      commodity generic 1st/2nd contract settle
    New rows win on (date, country, variable). This script does NOT touch
    DuckDB (no duckdb in the OpusBloomberg env) — see
    scripts/loop/load_market_implied.py for the loop-DB rebuild.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/bbg_quota_log.csv
    Append-only quota log (timestamp, script, operation, est_hits, rows,
    elapsed_s, status) per the bloomberg-skill mandatory pattern.

VERSION: 1.2
LAST UPDATED: 2026-06-12
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop)

DESCRIPTION:
Market-implied stress layer. The warehouse already has REALIZED currency
vol (T2 daily) and monthly FX levels (ECB), but nothing forward-looking:
no options-implied vol, no risk reversals (the market price of currency
crash protection — the cleanest daily read on devaluation fear, including
the HKD and SAR peg-stress trades), no daily VIX term structure, no rates
vol (MOVE), no daily credit OAS, no futures-curve shape. All of these are
classic dislocation inputs: a country whose RR spikes while its equity
market and CDS are quiet is exactly the cross-asset incoherence the loop's
D4 detector hunts for.

Quota economics (see bloomberg-skill limits.md): the v1.0 65 series were
first-pulled 2026-06-11, the v1.1 additions (72 series: 24 pairs x
butterfly/1W vol/3M vol) on 2026-06-12 — all FREE against the monthly
unique-ID counter from then on. A nightly 15-day incremental run costs
~137 hits (~0.03% of the daily cap); a full backfill is also 1 hit per
series because HistoricalDataRequest cost ignores date range.

DEPENDENCIES:
- OpusBloomberg conda env: blpapi, pandas, pyarrow (NOT the project venv)

USAGE:
  conda run -p "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv" \
      python scripts/loop/collect_market_implied_bbg.py             # last 15 days
  ... collect_market_implied_bbg.py --backfill                      # full 2006+ history

NOTES:
- Bloomberg Terminal must be logged in on the Parallels VM.
- Sanity guards: implied vol in (0, 200], |RR| <= 50 vol pts, OAS in
  (0, 50], VIX/MOVE in (0, 400], commodity prices > 0. Isolated bad prints
  are dropped and logged; if >5% of a series is out of range the run aborts
  and the parquet is left untouched (FAIL-IS-FAIL).
- Denmark (DKK pegged to EUR, no liquid surface) and Vietnam (managed VND,
  no reliable surface) have no FX vol coverage — structural, not a bug.
  U.S./NASDAQ/US SmallCap are the USD numeraire — dollar stress lives in
  the GLOBAL rows (DXY/BBDXY).
=============================================================================
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg")
from bbg import BBG, bloomberg_setup  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PANEL_PATH = BASE_DIR / "Data" / "work" / "loop" / "market_implied_daily.parquet"
QUOTA_LOG = BASE_DIR / "Data" / "work" / "loop" / "bbg_quota_log.csv"

HISTORY_START = "20060101"

# FX pair -> (T2 countries it maps to, flip_rr_sign)
# flip_rr_sign: RR is quoted call-vol minus put-vol on the BASE currency.
# For USDXXX pairs a positive RR = USD calls bid = local-ccy DEPRECIATION
# premium (keep sign). For XXXUSD pairs a positive RR = local-ccy calls bid
# = appreciation premium, so we FLIP so that positive always means local
# crash risk.
FX_PAIRS: dict[str, tuple[list[str], bool]] = {
    "EURUSD": (["France", "Germany", "Italy", "Netherlands", "Spain"], True),
    "GBPUSD": (["U.K."], True),
    "AUDUSD": (["Australia"], True),
    "USDJPY": (["Japan"], False),
    "USDCAD": (["Canada"], False),
    "USDCHF": (["Switzerland"], False),
    "USDSEK": (["Sweden"], False),
    "USDBRL": (["Brazil"], False),
    "USDCLP": (["Chile"], False),
    "USDMXN": (["Mexico"], False),
    "USDCNH": (["ChinaA", "ChinaH"], False),
    "USDHKD": (["Hong Kong"], False),
    "USDINR": (["India"], False),
    "USDIDR": (["Indonesia"], False),
    "USDKRW": (["Korea"], False),
    "USDMYR": (["Malaysia"], False),
    "USDPHP": (["Philippines"], False),
    "USDSGD": (["Singapore"], False),
    "USDTWD": (["Taiwan"], False),
    "USDTHB": (["Thailand"], False),
    "USDPLN": (["Poland"], False),
    "USDZAR": (["South Africa"], False),
    "USDTRY": (["Turkey"], False),
    "USDSAR": (["Saudi Arabia"], False),
}

# FX 3M forward roots (outright forward = "[ROOT]3M Curncy", spot = pair).
# NDF roots for capital-controlled currencies per the findatapy grid +
# live verification 2026-06-12. USDDKK has forwards but no options surface.
FWD_3M_ROOTS: dict[str, str] = {
    "EURUSD": "EUR", "GBPUSD": "GBP", "AUDUSD": "AUD", "USDJPY": "JPY",
    "USDCAD": "CAD", "USDCHF": "CHF", "USDSEK": "SEK", "USDBRL": "BCN",
    "USDCLP": "CHN", "USDMXN": "MXN", "USDCNH": "CNH", "USDHKD": "HKD",
    "USDINR": "IRN", "USDIDR": "IHN", "USDKRW": "KWN", "USDMYR": "MRN",
    "USDPHP": "PPN", "USDSGD": "SGD", "USDTWD": "NTN", "USDTHB": "THB",
    "USDPLN": "PLN", "USDZAR": "ZAR", "USDTRY": "TRY", "USDSAR": "SAR",
    "USDDKK": "DKK",
}

# forward-only pairs (no options surface): pair -> (countries, flip)
FWD_EXTRA_PAIRS: dict[str, tuple[list[str], bool]] = {
    "USDDKK": (["Denmark"], False),
}

RISK_TICKERS: dict[str, str] = {
    "VIX Index": "RISK_VIX",
    "VIX3M Index": "RISK_VIX3M",
    "MOVE Index": "RISK_MOVE",
    "LF98OAS Index": "RISK_HY_OAS",
    "LUACOAS Index": "RISK_IG_OAS",
    "DXY Curncy": "RISK_DXY",
    "BBDXY Index": "RISK_BBDXY",
}

COMMODITY_ROOTS = ["CL", "CO", "HG", "GC", "NG"]

# variable prefix -> (lo, hi) sanity bounds (value must be in (lo, hi])
SANITY: dict[str, tuple[float, float]] = {
    "FX_IMPVOL_1M_PCT": (0.0, 200.0),
    "FX_IMPVOL_1W_PCT": (0.0, 300.0),   # 1W vol spikes harder than 1M
    "FX_IMPVOL_3M_PCT": (0.0, 200.0),
    "FX_RR25_1M_PCT": (-50.0, 50.0),
    "FX_BF25_1M_PCT": (-10.0, 30.0),    # butterflies are small and >= ~0
    # carry: TRY printed >100% annualized in 2023-24; deeply negative only
    # on broken data, allow modest negatives (DM funding currencies)
    "FX_CARRY_3M_PCT": (-100.0, 500.0),

    "RISK_VIX": (0.0, 400.0),
    "RISK_VIX3M": (0.0, 400.0),
    "RISK_MOVE": (0.0, 400.0),
    "RISK_HY_OAS": (0.0, 50.0),
    "RISK_IG_OAS": (0.0, 50.0),
    "RISK_DXY": (0.0, 500.0),
    "RISK_BBDXY": (0.0, 5000.0),
    # commodities: positive price only (NG can print < 1, CL went negative
    # in Apr-2020 — keep a wide floor so the famous print survives)
    "CMD_": (-100.0, 100000.0),
}


def log_quota(operation: str, est_hits: int, rows: int, elapsed: float, status: str) -> None:
    QUOTA_LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not QUOTA_LOG.exists()
    with QUOTA_LOG.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "script", "operation", "est_hits", "rows", "elapsed_s", "status"])
        w.writerow([datetime.now().isoformat(timespec="seconds"),
                    "collect_market_implied_bbg", operation, est_hits, rows,
                    f"{elapsed:.1f}", status])


def bounds_for(variable: str) -> tuple[float, float]:
    for prefix, b in SANITY.items():
        if variable.startswith(prefix):
            return b
    raise KeyError(f"no sanity bounds for variable {variable}")


def sanity_filter(s: pd.Series, variable: str, label: str) -> pd.Series:
    """Drop out-of-range observations (logged loudly); abort the run if >5%
    of a series is out of range — that is a unit error, not a bad print."""
    if s.empty:
        return s
    lo, hi = bounds_for(variable)
    bad = (s <= lo) | (s > hi)
    if bad.any():
        frac = bad.mean()
        if frac > 0.05:
            raise RuntimeError(
                f"{label}: {bad.sum()}/{len(s)} obs outside ({lo}, {hi}] — looks like a unit error, refusing to write")
        print(f"  WARNING {label}: dropping {bad.sum()}/{len(s)} out-of-range obs")
        s = s[~bad]
    return s


def batch_to_series(raw: dict[str, list[dict]], field: str = "PX_LAST") -> dict[str, pd.Series]:
    out: dict[str, pd.Series] = {}
    for ticker, rows in raw.items():
        vals = {pd.Timestamp(r["date"]): float(r[field])
                for r in rows if r.get(field) not in (None, "")}
        out[ticker] = pd.Series(vals).sort_index() if vals else pd.Series(dtype=float)
    return out


def collect(start: str, end: str) -> pd.DataFrame:
    bloomberg_setup(verbose=False)

    fx_tickers = []
    for pair in FX_PAIRS:
        fx_tickers += [f"{pair}V1M Curncy", f"{pair}25R1M Curncy",
                       f"{pair}V1W Curncy", f"{pair}V3M Curncy",
                       f"{pair}25B1M Curncy"]
    fwd_tickers = []
    for pair, root in FWD_3M_ROOTS.items():
        fwd_tickers += [f"{root}3M Curncy", f"{pair} Curncy"]
    cmd_tickers = [f"{root}{n} Comdty" for root in COMMODITY_ROOTS for n in (1, 2)]
    all_tickers = fx_tickers + fwd_tickers + list(RISK_TICKERS) + cmd_tickers

    t0 = time.time()
    with BBG() as bbg:
        if not bbg.ping():
            raise RuntimeError("Bloomberg ping failed — terminal not reachable")
        raw = bbg.hist_batch(all_tickers, "PX_LAST", start, end)
    series = batch_to_series(raw)
    elapsed = time.time() - t0

    frames: list[pd.DataFrame] = []
    n_ok = n_empty = 0

    def emit(s: pd.Series, country: str, variable: str, label: str) -> None:
        nonlocal n_ok, n_empty
        s = sanity_filter(s, variable, label)
        if s.empty:
            n_empty += 1
            print(f"  WARNING {label}: no data")
            return
        frames.append(pd.DataFrame(
            {"date": s.index, "country": country, "value": s.values, "variable": variable}))
        n_ok += 1

    for pair, (countries, flip_rr) in FX_PAIRS.items():
        vol = series.get(f"{pair}V1M Curncy", pd.Series(dtype=float))
        vol1w = series.get(f"{pair}V1W Curncy", pd.Series(dtype=float))
        vol3m = series.get(f"{pair}V3M Curncy", pd.Series(dtype=float))
        rr = series.get(f"{pair}25R1M Curncy", pd.Series(dtype=float))
        bf = series.get(f"{pair}25B1M Curncy", pd.Series(dtype=float))
        if flip_rr and not rr.empty:
            rr = -rr   # butterflies are symmetric — never flipped
        for c in countries:
            emit(vol, c, "FX_IMPVOL_1M_PCT", f"{pair} vol -> {c}")
            emit(vol1w, c, "FX_IMPVOL_1W_PCT", f"{pair} 1W vol -> {c}")
            emit(vol3m, c, "FX_IMPVOL_3M_PCT", f"{pair} 3M vol -> {c}")
            emit(rr, c, "FX_RR25_1M_PCT", f"{pair} RR -> {c}")
            emit(bf, c, "FX_BF25_1M_PCT", f"{pair} BF -> {c}")

    # ---- forward-implied carry (annualized %, local-minus-USD sign) ---------
    for pair, root in FWD_3M_ROOTS.items():
        countries, flip = (FX_PAIRS.get(pair) or FWD_EXTRA_PAIRS[pair])
        fwd = series.get(f"{root}3M Curncy", pd.Series(dtype=float))
        spot = series.get(f"{pair} Curncy", pd.Series(dtype=float))
        if fwd.empty or spot.empty:
            for c in countries:
                emit(pd.Series(dtype=float), c, "FX_CARRY_3M_PCT", f"{pair} carry -> {c}")
            continue
        both = pd.concat([fwd.rename("f"), spot.rename("s")], axis=1, sort=True).dropna()
        both = both[(both["f"] > 0) & (both["s"] > 0)]
        if flip:
            # XXXUSD quote: forward premium on the pair = USD rates BELOW
            # local; invert the ratio so positive = local rates above USD
            carry = (both["s"] / both["f"] - 1.0) * 4.0 * 100.0
        else:
            carry = (both["f"] / both["s"] - 1.0) * 4.0 * 100.0
        for c in countries:
            emit(carry, c, "FX_CARRY_3M_PCT", f"{pair} carry -> {c}")

    for ticker, variable in RISK_TICKERS.items():
        emit(series.get(ticker, pd.Series(dtype=float)), "GLOBAL", variable, ticker)

    for root in COMMODITY_ROOTS:
        for n in (1, 2):
            emit(series.get(f"{root}{n} Comdty", pd.Series(dtype=float)),
                 "GLOBAL", f"CMD_{root}{n}", f"{root}{n} Comdty")

    if not frames:
        log_quota(f"hist_batch {start}->{end}", len(all_tickers), 0, elapsed, "EMPTY")
        raise RuntimeError("no market-implied data collected at all")

    out = pd.concat(frames, ignore_index=True)
    out["source"] = "bloomberg"
    log_quota(f"hist_batch {start}->{end}", len(all_tickers), len(out), elapsed, "OK")
    print(f"collected: {n_ok} series mapped ({n_empty} empty), {len(out):,} rows, "
          f"{len(all_tickers)} tickers, {elapsed:.1f}s")
    return out[["date", "country", "value", "variable", "source"]]


def merge_and_save(new: pd.DataFrame) -> None:
    panel = pd.read_parquet(PANEL_PATH) if PANEL_PATH.exists() else pd.DataFrame(
        columns=["date", "country", "value", "variable", "source"])
    merged = pd.concat([panel, new], ignore_index=True)
    merged["date"] = pd.to_datetime(merged["date"])
    merged = merged.drop_duplicates(subset=["date", "country", "variable"], keep="last")
    merged = merged.sort_values(["country", "variable", "date"]).reset_index(drop=True)
    PANEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PANEL_PATH.with_suffix(".parquet.tmp")
    merged.to_parquet(tmp, index=False)
    tmp.replace(PANEL_PATH)
    print(f"panel: {len(merged):,} rows, {merged['date'].min().date()} -> {merged['date'].max().date()}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bloomberg daily market-implied stress layer (FX vol/RR, risk dashboard, commodity curve).")
    parser.add_argument("--backfill", action="store_true", help="full history from 2006")
    parser.add_argument("--start", default=None, metavar="YYYY-MM-DD")
    args = parser.parse_args()

    end = date.today().strftime("%Y%m%d")
    start = (HISTORY_START if args.backfill
             else args.start.replace("-", "") if args.start
             else (date.today() - timedelta(days=15)).strftime("%Y%m%d"))
    print(f"Pulling market-implied layer {start} -> {end}")
    try:
        new = collect(start, end)
    except Exception as e:
        print(f"MARKET-IMPLIED PULL FAILED: {e} — existing parquet untouched")
        return 1
    merge_and_save(new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
