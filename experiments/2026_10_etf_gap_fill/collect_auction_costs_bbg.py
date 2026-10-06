#!/usr/bin/env python
"""
==============================================================================
SCRIPT NAME: collect_auction_costs_bbg.py
VERSION:     1.0  (2026-10-05)
==============================================================================

DESCRIPTION
-----------
Bloomberg pull for the closing-auction cost study of the one-day country-ETF
reversal trade (see etf_reversal_1d.py and the README in this folder).

Pulls, for the 34 house country ETFs:
  1. DAILY history 2023-10-01 -> today (one batched HistoricalDataRequest per
     field): PX_LAST, PX_VOLUME, TURNOVER (USD value traded), PX_BID, PX_ASK
     (closing quote), TIME_WAVG_BID_ASK_SPREAD_PCT (time-weighted average
     quoted spread over the day, in percent).
  2. REFERENCE snapshot: ETF_MEDN_BID_ASK_SPREAD, BID_ASK_SPREAD_RATIO,
     PRIMARY_EXCHANGE_NAME, FUND_TOTAL_ASSETS.
  3. INTRADAY 1-minute bars (TRADE, BID, ASK) for the last-35-minutes window
     of each US session, 2026-04-06 -> 2026-10-02 (intraday retention on this
     seat is ~6 months).  All dates in this window are US daylight time, so
     the window 19:25-20:05 UTC = 15:25-16:05 ET (covers a true 15:29 signal
     price, a 15:45-16:00 TWAP/VWAP execution, and the closing auction).  One request per security
     per event type spanning the whole date range; rows outside the window are
     dropped after download.

Runs ONLY under the OpusBloomberg env (budget gate + quota guard apply).
The 34 ETFs are already counted this month (budget_gate estimate: 0 new).
Incremental and resumable: each security's intraday result is written to its
own parquet atomically; existing files are skipped.

INPUT FILES
-----------
  none (Bloomberg Terminal via DAPI; connection per
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/bbg.py)

OUTPUT FILES
------------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/bbg_auction/daily.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/bbg_auction/ref.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/bbg_auction/intraday/<TICKER>_<EVENT>.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/bbg_auction/collect_log.txt
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/bbg_auction/progress.json

DEPENDENCIES
------------
  OpusBloomberg .venv (blpapi, pandas, pyarrow)

USAGE
-----
  "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv/bin/python" \
     "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/collect_auction_costs_bbg.py"

NOTES
-----
  * Bloomberg data is precious: outputs are never overwritten in place; an
    existing daily/ref file is moved to a timestamped backup first.
  * A BloombergQuotaError / budget refusal stops the run (no retry).
==============================================================================
"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, '/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg')
from bbg import BBG, bloomberg_setup  # noqa: E402

OUT = Path('/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/bbg_auction')
INTRA = OUT / 'intraday'
TICKERS = ('EWS EWA EWC EWG EWJ EWL EWU QQQ SPY EWQ EWN EWD EWI ASHR ECH EIDO EPHE EPOL IWM '
           'EWM EWT EWW EWY EWZ EZA EDEN INDA MCHI EWH THD TUR EWP VNM KSA').split()
DAILY_FIELDS = ['PX_LAST', 'PX_VOLUME', 'TURNOVER', 'PX_BID', 'PX_ASK', 'TIME_WAVG_BID_ASK_SPREAD_PCT']
REF_FIELDS = ['ETF_MEDN_BID_ASK_SPREAD', 'BID_ASK_SPREAD_RATIO', 'PRIMARY_EXCHANGE_NAME', 'FUND_TOTAL_ASSETS']
INTRA_START, INTRA_END = '2026-04-06 13:30:00', '2026-10-02 20:10:00'
WIN = ('19:25', '20:05')   # UTC, = 15:25-16:05 EDT
# Ultra-liquid US ETFs: BID/ASK 1-minute bars are prohibitively slow (QQQ BID took 20 min
# via per-day windows) and their spread is ~0.3bp, so the analysis uses TRADE prices as mid.
SKIP_QUOTES = {'QQQ', 'SPY', 'IWM'}


def log(msg):
    line = f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {msg}"
    print(line, flush=True)
    with open(OUT / 'collect_log.txt', 'a') as f:
        f.write(line + '\n')


def atomic_parquet(df, path):
    tmp = path.with_suffix('.tmp')
    df.to_parquet(tmp)
    tmp.rename(path)


def backup_if_exists(path):
    if path.exists():
        bk = path.with_name(f"{path.stem}_backup_{datetime.now():%Y%m%d_%H%M%S}{path.suffix}")
        path.rename(bk)
        log(f"backed up {path.name} -> {bk.name}")


def progress(**kw):
    p = OUT / 'progress.json'
    d = json.loads(p.read_text()) if p.exists() else {}
    d.update(kw, updated=datetime.now().isoformat(timespec='seconds'))
    p.write_text(json.dumps(d, indent=2))


def main():
    INTRA.mkdir(parents=True, exist_ok=True)
    secs = [f'{t} US Equity' for t in TICKERS]
    bloomberg_setup()
    with BBG() as bbg:
        # 1. daily
        dpath = OUT / 'daily.parquet'
        if not dpath.exists():
            frames = []
            for fld in DAILY_FIELDS:
                res = bbg.hist_batch(secs, fld, '20231001', datetime.now().strftime('%Y%m%d'))
                for s, rows in res.items():
                    if rows:
                        df = pd.DataFrame(rows)
                        df['ticker'] = s.split()[0]
                        df = df.rename(columns={fld: 'value'})
                        df['field'] = fld
                        frames.append(df[['date', 'ticker', 'field', 'value']])
                log(f"daily {fld}: {sum(1 for v in res.values() if v)}/{len(secs)} securities returned")
            daily = pd.concat(frames, ignore_index=True)
            daily['value'] = pd.to_numeric(daily['value'], errors='coerce')
            atomic_parquet(daily, dpath)
            progress(daily_rows=len(daily))
        else:
            log("daily.parquet exists, skipping")

        # 2. reference (skip if already pulled this session)
        rpath = OUT / 'ref.parquet'
        if not rpath.exists():
            ref = bbg.ref_batch(secs, REF_FIELDS)
            rdf = pd.DataFrame(ref).T.reset_index().rename(columns={'index': 'security'})
            rdf['ticker'] = rdf['security'].str.split().str[0]
            atomic_parquet(rdf.astype(str), rpath)
            log(f"ref: {len(rdf)} rows")
        else:
            log("ref.parquet exists, skipping")

    # 3. intraday - one session per security/event so a timeout cannot poison the rest
    daily = pd.read_parquet(OUT / 'daily.parquet')
    done = 0
    for t in TICKERS:
        tdays = sorted(pd.to_datetime(daily[(daily.ticker == t) & (daily.field == 'PX_LAST')]['date']).unique())
        tdays = [d for d in tdays if pd.Timestamp(INTRA_START[:10]) <= d <= pd.Timestamp(INTRA_END[:10])]
        for ev in ['TRADE', 'BID', 'ASK']:
            p = INTRA / f'{t}_{ev}.parquet'
            if p.exists() or (t in SKIP_QUOTES and ev != 'TRADE'):
                done += 1
                continue
            t0 = time.time()
            mode = 'monthly'
            bars = []
            try:
                # monthly chunks: a single 6-month request on EWJ BID exceeded the 90s timeout
                edges = list(pd.date_range(INTRA_START[:10], INTRA_END[:10], freq='MS')) + [pd.Timestamp(INTRA_END[:10]) + pd.Timedelta(days=1)]
                edges = [pd.Timestamp(INTRA_START[:10])] + [e for e in edges if e > pd.Timestamp(INTRA_START[:10])]
                with BBG() as bbg:
                    for a, b in zip(edges[:-1], edges[1:]):
                        bars += bbg.bdib(f'{t} US Equity', f'{a:%Y-%m-%d} 13:30:00',
                                         f'{b - pd.Timedelta(days=1):%Y-%m-%d} 20:10:00', ev, 1)
            except TimeoutError:
                # very heavily quoted names (QQQ BID even monthly): fetch only the
                # 19:25-20:05 UTC window, one trading day per request, fresh session
                mode = 'per-day window'
                log(f"intraday {t} {ev}: monthly request timed out; falling back to per-day windows ({len(tdays)} days)")
                bars = []
                with BBG() as bbg:
                    for d in tdays:
                        bars += bbg.bdib(f'{t} US Equity', f'{d:%Y-%m-%d} {WIN[0]}:00', f'{d:%Y-%m-%d} {WIN[1]}:00', ev, 1)
            df = pd.DataFrame(bars)
            if not df.empty:
                df['time'] = pd.to_datetime(df['time'])
                hm = df['time'].dt.strftime('%H:%M')
                df = df[(hm >= WIN[0]) & (hm <= WIN[1])].copy()
                for c in ['open', 'high', 'low', 'close', 'volume', 'numEvents', 'value']:
                    if c in df:
                        df[c] = pd.to_numeric(df[c], errors='coerce')
            df['ticker'], df['event'] = t, ev
            atomic_parquet(df, p)
            done += 1
            log(f"intraday {t} {ev}: {len(bars)} bars downloaded ({mode}), {len(df)} kept in window ({time.time()-t0:.1f}s)")
            progress(intraday_done=done, intraday_total=len(TICKERS) * 3, last=f'{t}_{ev}')
    log("COLLECTION COMPLETE")


if __name__ == '__main__':
    main()
