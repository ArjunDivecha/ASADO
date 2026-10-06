#!/usr/bin/env python
"""
==============================================================================
SCRIPT NAME: etf_gap_fill_intraday.py
VERSION:     1.0  (2026-10-05)
==============================================================================

DESCRIPTION
-----------
Implementability check for the ETF gap-fill signal found by etf_gap_fill.py.
That script measured the gap with the ETF's CLOSING print and then "traded"
at the same close, which nobody can do.  Here the ETF leg of the gap is
measured at 15:30 ET (open of Yahoo's last 60-minute bar), when the local
market has long closed for Asia-Pacific and Europe/Africa/ME, and the trade is
entered at that day's close (MOC) or at the 15:30 price, held to the next
close.  Americas are excluded (local close is simultaneous with US close, so
the local return is not known at 15:30).

Also runs, on the same recent window, a sub-period decomposition (Fama-MacBeth
of next-day ETF return on local and ETF same-day returns) to see whether the
LOCAL leg still adds information beyond plain one-day ETF reversal.

Signals compared (each: long top quintile minus bottom quintile, and top
quintile minus equal-weight, hold to next close, gross):
  ORACLE_close_gap      gap with ETF close (what etf_gap_fill.py did)
  gap1530_enter_close   gap with ETF @15:30, enter at close
  gap1530_enter_1530    gap with ETF @15:30, enter at 15:30 price
  rev1530_enter_close   pure ETF reversal (-ETF return to 15:30), enter at close
  ORACLE_close_rev      pure reversal with ETF close

INPUT FILES
-----------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/local_1dret.parquet
      (T2 1DRet cache written by etf_gap_fill.py)
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/etf_t2_map.json
  Yahoo Finance (network): 60-minute bars (last 730 days), daily unadjusted
      closes and dividends for each ETF

OUTPUT FILES
------------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_hourly.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_daily_unadj.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/runs/intraday_<timestamp>/
      intraday_panel.parquet, intraday_strategy.xlsx, intraday_summary.json, log.txt

DEPENDENCIES
------------
  pandas, numpy, yfinance, statsmodels, openpyxl (project venv)

USAGE
-----
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
  venv/bin/python experiments/2026_10_etf_gap_fill/etf_gap_fill_intraday.py [--refresh]

NOTES
-----
  * Gross returns, no costs (house rule).  ~2 years of data only: t-stats
    will be modest; the comparison between ORACLE and 15:30 variants on the
    SAME days is the point.
  * T2 local returns are USD; the FX fixing time inside T2 is not documented.
    If it is later than 15:30 ET the local leg carries a little look-ahead;
    the pure-reversal variants do not use local data and are immune.
==============================================================================
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path('/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO')
EXP = ROOT / 'experiments/2026_10_etf_gap_fill'
DATA = EXP / 'data'
MAP = ROOT / 'config/etf_t2_map.json'
EXCLUDE = {'U.S.', 'NASDAQ', 'US SmallCap', 'Brazil', 'Canada', 'Chile', 'Mexico'}
ASIA = {'Australia', 'ChinaA', 'ChinaH', 'Hong Kong', 'India', 'Indonesia', 'Japan', 'Korea',
        'Malaysia', 'Philippines', 'Singapore', 'Taiwan', 'Thailand', 'Vietnam'}


class Tee:
    def __init__(self, path):
        self.f = open(path, 'w')
        self.out = sys.stdout

    def write(self, s):
        self.f.write(s)
        self.out.write(s)

    def flush(self):
        self.f.flush()
        self.out.flush()


def fetch(tickers, refresh):
    ph, pd_ = DATA / 'etf_hourly.parquet', DATA / 'etf_daily_unadj.parquet'
    if ph.exists() and pd_.exists() and not refresh:
        return pd.read_parquet(ph), pd.read_parquet(pd_)
    import yfinance as yf
    h = yf.download(tickers, period='730d', interval='60m', auto_adjust=False, progress=False,
                    group_by='column', prepost=False)
    hourly = h['Open'].copy()
    idx = pd.to_datetime(hourly.index)
    if idx.tz is not None:
        idx = idx.tz_convert('America/New_York').tz_localize(None)
    hourly.index = idx
    d = yf.download(tickers, start='2023-06-01', auto_adjust=False, actions=True, progress=False,
                    group_by='column')
    daily = pd.concat({'close': d['Close'], 'div': d['Dividends'].fillna(0.0)}, axis=1)
    daily.index = pd.to_datetime(daily.index).tz_localize(None)
    hourly.to_parquet(ph)
    daily.to_parquet(pd_)
    return hourly, daily


def nw_t(x, lags=5):
    x = pd.Series(x).dropna()
    m = sm.OLS(x.values, np.ones(len(x))).fit(cov_type='HAC', cov_kwds={'maxlags': lags})
    return m.params[0], m.tvalues[0], len(x)


def qs(g, sig, fwd):
    q = g[sig].rank(pct=True)
    top, bot = g[q > 0.8], g[q <= 0.2]
    return top[fwd].mean() - bot[fwd].mean(), top[fwd].mean() - g[fwd].mean()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--refresh', action='store_true')
    args = ap.parse_args()
    run = EXP / 'runs' / ('intraday_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    run.mkdir(parents=True)
    sys.stdout = Tee(run / 'log.txt')
    print(f"Run dir: {run}")

    cmap = {k: v['primary'] for k, v in json.load(open(MAP))['map'].items() if k not in EXCLUDE}
    hourly, daily = fetch(sorted(set(cmap.values())), args.refresh)
    close, div = daily['close'], daily['div']
    # price at 15:30 ET = open of the 15:30 bar
    p1530 = hourly[hourly.index.time == pd.Timestamp('15:30').time()].copy()
    p1530.index = p1530.index.normalize()
    print(f"Hourly bars {hourly.index.min()} -> {hourly.index.max()}; 15:30 prices on {len(p1530)} days")

    local = pd.read_parquet(DATA / 'local_1dret.parquet')
    loc = local.pivot(index='date', columns='country', values='value').sort_index()
    loc.index = loc.index + pd.Timedelta(days=1)
    cum = np.log1p(loc.fillna(0.0)).cumsum()

    rows = []
    for c, t in cmap.items():
        if t not in close.columns or t not in p1530.columns or c not in cum.columns:
            continue
        cl = close[t].dropna()
        dates = cl.index[cl.index.isin(p1530.index)]
        dates = dates[dates <= cum.index[-1]]
        cl_prev = cl.shift(1).reindex(dates)
        d = pd.DataFrame(index=dates)
        d['country'], d['etf_ticker'] = c, t
        d['region'] = 'Asia-Pacific' if c in ASIA else 'Europe/Africa/ME'
        dv = div[t].reindex(dates).fillna(0.0)
        d['etf_close_ret'] = (cl.reindex(dates) + dv) / cl_prev - 1
        d['etf_1530_ret'] = (p1530[t].reindex(dates) + dv) / cl_prev - 1
        lc = cum[c].reindex(cl.index, method='ffill')
        d['local'] = np.expm1(lc.diff()).reindex(dates)
        nxt_close = cl.shift(-1).reindex(dates)
        nxt_div = div[t].shift(-1).reindex(dates).fillna(0.0)
        d['fwd_close'] = (nxt_close + nxt_div) / cl.reindex(dates) - 1
        d['fwd_from_1530'] = (nxt_close + nxt_div) / p1530[t].reindex(dates) - 1  # no same-day dividend after ex-date (fixed 2026-10-05)
        rows.append(d.reset_index(names='date'))
    p = pd.concat(rows, ignore_index=True)
    p = p[(p['local'].abs() > 1e-12)].dropna(subset=['etf_close_ret', 'etf_1530_ret', 'fwd_close', 'fwd_from_1530'])
    bad = (p[['etf_close_ret', 'etf_1530_ret', 'fwd_close', 'fwd_from_1530', 'local']].abs() > 0.3).any(axis=1)
    print(f"Dropping {bad.sum()} rows with a |return| > 30% (bad print)")
    p = p[~bad]
    p['gap_close'] = p['local'] - p['etf_close_ret']
    p['gap_1530'] = p['local'] - p['etf_1530_ret']
    p['rev_close'] = -p['etf_close_ret']
    p['rev_1530'] = -p['etf_1530_ret']
    p.to_parquet(run / 'intraday_panel.parquet')
    print(f"Panel {len(p):,} rows, {p.country.nunique()} countries, {p.date.min().date()} -> {p.date.max().date()}")
    print("Median |ETF close - 15:30| move:", round((p.etf_close_ret - p.etf_1530_ret).abs().median() * 1e4, 1), "bp")

    variants = {
        'ORACLE_close_gap': ('gap_close', 'fwd_close'),
        'gap1530_enter_close': ('gap_1530', 'fwd_close'),
        'gap1530_enter_1530': ('gap_1530', 'fwd_from_1530'),
        'ORACLE_close_rev': ('rev_close', 'fwd_close'),
        'rev1530_enter_close': ('rev_1530', 'fwd_close'),
        'rev1530_enter_1530': ('rev_1530', 'fwd_from_1530'),
        'local_only_enter_close': ('local', 'fwd_close'),
    }
    daily_ret = {}
    for nm, (sig, fwd) in variants.items():
        ls, lx = {}, {}
        for dt, g in p.groupby('date'):
            if len(g) < 10:
                continue
            ls[dt], lx[dt] = qs(g, sig, fwd)
        daily_ret[f'{nm}:long_short'] = pd.Series(ls)
        daily_ret[f'{nm}:long_minus_ew'] = pd.Series(lx)
    dr = pd.DataFrame(daily_ret)
    st = []
    for col in dr:
        x = dr[col].dropna()
        ann, vol = x.mean() * 252, x.std() * np.sqrt(252)
        _, t, n = nw_t(x)
        st.append({'series': col, 'ann_return': ann, 'ann_vol': vol, 'sharpe': ann / vol, 'nw_t': t, 'days': n})
    st = pd.DataFrame(st)
    print("\n=== Same ~2y window: oracle close-signal vs implementable 15:30 signal ===")
    print(st.round(3).to_string(index=False))

    # Fama-MacBeth decomposition on the same window and on 15:30 signal
    print("\n=== FM decomposition, fwd_close on [local, ETF move] ===")
    dec = []
    for etfcol in ['etf_close_ret', 'etf_1530_ret']:
        co = []
        for dt, g in p.groupby('date'):
            g = g[['fwd_close', 'local', etfcol]].dropna()
            if len(g) < 12:
                continue
            X = (g[['local', etfcol]] - g[['local', etfcol]].mean()).values
            co.append(np.linalg.lstsq(X, (g['fwd_close'] - g['fwd_close'].mean()).values, rcond=None)[0])
        co = np.array(co)
        bl, tl, n = nw_t(co[:, 0])
        be, te, _ = nw_t(co[:, 1])
        dec.append({'etf_leg': etfcol, 'b_local': bl, 't_local': tl, 'b_etf': be, 't_etf': te, 'days': n})
    dec = pd.DataFrame(dec)
    print(dec.round(4).to_string(index=False))

    with pd.ExcelWriter(run / 'intraday_strategy.xlsx') as w:
        st.to_excel(w, sheet_name='stats', index=False)
        dec.to_excel(w, sheet_name='decomposition', index=False)
        dr.to_excel(w, sheet_name='daily_returns')
    json.dump({'stats': st.round(4).to_dict(orient='records'), 'decomposition': dec.round(5).to_dict(orient='records'),
               'window': [str(p.date.min().date()), str(p.date.max().date())]},
              open(run / 'intraday_summary.json', 'w'), indent=2)
    print(f"\nDone. {run}")


if __name__ == '__main__':
    main()
