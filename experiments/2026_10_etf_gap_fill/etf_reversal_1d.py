#!/usr/bin/env python
"""
==============================================================================
SCRIPT NAME: etf_reversal_1d.py
VERSION:     1.0  (2026-10-05)
==============================================================================

DESCRIPTION
-----------
Stand-alone test of ONE-DAY CROSS-SECTIONAL REVERSAL in the 34 country ETFs
(house backtest universe).  Follow-on to etf_gap_fill.py, which found that the
local-vs-ETF "gap-fill" effect has decayed and what survives is plain
next-day reversal of the ETFs' own returns.

Each US trading day T, rank the ETFs by their return on day T.  Buy the
biggest losers (bottom quantile), short the biggest winners (top quantile),
equal weight within legs.  Also a long-only book (losers only) judged against
the equal-weight benchmark of the same universe (house convention).

PRE-REGISTERED PRIMARY SPEC (fixed before results were seen)
  lookback 1 day, hold 1 day, quintiles, raw returns,
  execution E3 = signal from close T, enter at OPEN T+1, exit at OPEN T+2.
  Reported gross, vs equal-weight, Full / 5y / 3y / 1y, monthly-return metrics
  per the backtest skill (Strategy, Benchmark, Net ann. return, IR on monthly
  active returns, Net drawdown, two-sided turnover).

EXECUTION VARIANTS
  E1 close->close   signal and entry on the same close print (ORACLE: not
                    tradeable, inflated by closing-print bounce)
  E2 open->close    enter open T+1, exit close T+1 (intraday only)
  E3 open->open     enter open T+1, exit open T+1+H  (PRIMARY)
  E4 skip-day       enter close T+1, exit close T+1+H
  (E5, a 15:30 ET signal entered at the close, runs in a separate 2-year
   section using Yahoo 60-minute bars cached by etf_gap_fill_intraday.py)

ROBUSTNESS GRID
  lookback L in {1,2,3,5,10} days, hold H in {1,2,5} days (overlapping
  tranches), quantile in {tercile, quintile, decile}, signal raw vs residual
  (minus rolling-120d beta x equal-weight universe return), execution E1/E3/E4.
  Plus: sub-periods, region split, liquid vs thin ETFs, ex-US ETFs,
  leave-one-ETF-out jackknife, by-year table.

INPUT FILES
-----------
  Yahoo Finance (network, via yfinance): daily OHLCV, auto-adjusted, for the
      34 ETFs, cached to the parquet below
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_hourly.parquet
      (60-minute bars, written by etf_gap_fill_intraday.py; E5 only)
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_daily_unadj.parquet
      (unadjusted closes + dividends, written by etf_gap_fill_intraday.py; E5 only)

OUTPUT FILES
------------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_ohlcv_34.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/runs/reversal_<timestamp>/
      reversal_report.pdf    headline: cumulative net return vs equal-weight
      reversal_results.xlsx  scorecards, grid, jackknife, by-year, data quality
      daily_returns.parquet  primary-spec daily series
      summary.json           headline numbers
      log.txt                stdout copy

DEPENDENCIES
------------
  pandas, numpy, yfinance, statsmodels, matplotlib, openpyxl (project venv)

USAGE
-----
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
  venv/bin/python experiments/2026_10_etf_gap_fill/etf_reversal_1d.py [--refresh]

NOTES
-----
  * Gross returns, no cost/turnover penalty (25bp law retracted 2026-07-13).
    Turnover is reported as information only.
  * ETF-days with zero volume or a missing/non-positive open are excluded from
    the signal and from execution (stale prints would fake reversal/momentum).
==============================================================================
"""
import argparse
import itertools
import json
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path('/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO')
EXP = ROOT / 'experiments/2026_10_etf_gap_fill'
DATA = EXP / 'data'

UNIVERSE = ('EWS EWA EWC EWG EWJ EWL EWU QQQ SPY EWQ EWN EWD EWI ASHR ECH EIDO EPHE EPOL IWM '
            'EWM EWT EWW EWY EWZ EZA EDEN INDA MCHI EWH THD TUR EWP VNM KSA').split()
US = {'SPY', 'QQQ', 'IWM'}
ASIA = {'EWS', 'EWA', 'EWJ', 'ASHR', 'EIDO', 'EPHE', 'EWM', 'EWT', 'EWY', 'INDA', 'MCHI', 'EWH', 'THD', 'VNM'}
AMER = {'EWC', 'ECH', 'EWW', 'EWZ'} | US
LIQUID = {'SPY', 'QQQ', 'IWM', 'EWJ', 'EWZ', 'EWG', 'EWT', 'EWY', 'MCHI', 'INDA', 'EWU', 'EWC',
          'EWA', 'EWH', 'EWW', 'EWQ', 'EWL', 'ASHR'}


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


# ----------------------------------------------------------------------------- data
def load_ohlcv(refresh):
    p = DATA / 'etf_ohlcv_34.parquet'
    if p.exists() and not refresh:
        return pd.read_parquet(p)
    import yfinance as yf
    d = yf.download(UNIVERSE, start='1999-12-01', auto_adjust=True, progress=False, group_by='column')
    out = pd.concat({k: d[k] for k in ['Open', 'High', 'Low', 'Close', 'Volume']}, axis=1)
    out.index = pd.to_datetime(out.index).tz_localize(None)
    tmp = p.with_suffix('.tmp')
    out.to_parquet(tmp)
    tmp.rename(p)
    return out


def data_quality(O, C, V):
    rows = []
    for t in C.columns:
        c = C[t].dropna()
        if c.empty:
            continue
        o, v = O[t].reindex(c.index), V[t].reindex(c.index)
        for era, (a, b) in {'2000-07': ('2000', '2007'), '2008-15': ('2008', '2015'),
                            '2016-26': ('2016', '2026')}.items():
            sl = slice(a, b + '-12-31')
            cc, oo, vv = c[sl], o[sl], v[sl]
            if len(cc) == 0:
                continue
            rows.append({'ticker': t, 'era': era, 'days': len(cc),
                         'pct_zero_volume': (vv <= 0).mean(),
                         'pct_open_eq_prevclose': (np.isclose(oo, cc.shift(1), rtol=1e-6)).mean(),
                         'pct_open_eq_close': (np.isclose(oo, cc, rtol=1e-6)).mean(),
                         'pct_close_unchanged': (cc.pct_change() == 0).mean()})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- engine
def quantile_weights(sig, q):
    """sig: DataFrame dates x tickers (higher = buy). Returns long-short and long-only weights."""
    n = sig.notna().sum(axis=1)
    r = sig.rank(axis=1, pct=True)
    lo = (r > 1 - q).astype(float)
    sh = (r <= q).astype(float)
    ok = n >= 10
    lo = lo.div(lo.sum(axis=1).replace(0, np.nan), axis=0).where(ok, 0.0).fillna(0.0)
    sh = sh.div(sh.sum(axis=1).replace(0, np.nan), axis=0).where(ok, 0.0).fillna(0.0)
    ew = sig.notna().astype(float)
    ew = ew.div(ew.sum(axis=1).replace(0, np.nan), axis=0).where(ok, 0.0).fillna(0.0)
    return lo, sh, ew


def run_book(sig, R, q, H):
    """Weights formed on signal day t are applied to R row t (R is already
    aligned so row t = return of the holding period that starts after signal t).
    H>1: overlapping tranches, each 1/H, tranche k uses row t of R shifted."""
    lo, sh, ew = quantile_weights(sig, q)
    Rf = R.fillna(0.0)
    avail = R.notna()
    pl = sum(lo.shift(k).fillna(0.0) for k in range(H)) / H
    ps = sum(sh.shift(k).fillna(0.0) for k in range(H)) / H
    pe = sum(ew.shift(k).fillna(0.0) for k in range(H)) / H
    # positions on names with no return in a period earn 0 (delisted/holiday): mask
    pl, ps, pe = pl.where(avail, 0.0), ps.where(avail, 0.0), pe.where(avail, 0.0)
    long_ret = (pl * Rf).sum(axis=1)
    short_ret = (ps * Rf).sum(axis=1)
    ew_ret = (pe * Rf).sum(axis=1)
    started = (lo.sum(axis=1) > 0).cummax()
    out = pd.DataFrame({'long_only': long_ret, 'short_leg': short_ret, 'ew': ew_ret,
                        'long_short': long_ret - short_ret})[started]
    turn_lo = pl.diff().abs().sum(axis=1)[started].mean() * 252
    turn_ls = (pl - ps).diff().abs().sum(axis=1)[started].mean() * 252
    return out, turn_lo, turn_ls


def monthly(daily):
    return (1 + daily).groupby(daily.index.to_period('M')).prod() - 1


def scorecard(daily, label, turn):
    """House six metrics on monthly returns, plus daily Sharpe / NW t."""
    ms, mb = monthly(daily['strat']), monthly(daily['bench'])
    end = ms.index.max()
    rows = []
    for w, n in [('Full', None), ('5y', 60), ('3y', 36), ('1y', 12)]:
        s = ms if n is None else ms.iloc[-n:]
        b = mb.loc[s.index]
        a = s - b
        k = len(s)
        sa = (1 + s).prod() ** (12 / k) - 1
        ba = (1 + b).prod() ** (12 / k) - 1
        gap = (1 + s).cumprod() - (1 + b).cumprod()
        gap = pd.concat([pd.Series([0.0]), gap.reset_index(drop=True)])
        ndd = (gap.cummax() - gap).max()
        dd = daily.loc[str(s.index.min().start_time.date()):]
        x = dd['strat'] - dd['bench']
        nw = sm.OLS(x.values, np.ones(len(x))).fit(cov_type='HAC', cov_kwds={'maxlags': 5}).tvalues[0]
        rows.append({'book': label, 'window': w, 'start': str(s.index.min()), 'months': k,
                     'strategy_ann': sa, 'benchmark_ann': ba, 'net_ann': sa - ba,
                     'IR_monthly': a.mean() / a.std() * np.sqrt(12) if a.std() > 0 else np.nan,
                     'net_drawdown': ndd, 'turnover_2sided_ann': turn,
                     'daily_active_sharpe': x.mean() / x.std() * np.sqrt(252), 'daily_nw_t': nw})
    return rows


def ls_stats(x):
    x = x.dropna()
    nw = sm.OLS(x.values, np.ones(len(x))).fit(cov_type='HAC', cov_kwds={'maxlags': 5}).tvalues[0]
    return x.mean() * 252, x.std() * np.sqrt(252), x.mean() / x.std() * np.sqrt(252), nw


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--refresh', action='store_true')
    args = ap.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    run = EXP / 'runs' / ('reversal_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    run.mkdir(parents=True)
    sys.stdout = Tee(run / 'log.txt')
    print(f"Run dir: {run}")

    px = load_ohlcv(args.refresh)
    O, C, V = px['Open'][UNIVERSE], px['Close'][UNIVERSE], px['Volume'][UNIVERSE]
    print(f"OHLCV {C.index.min().date()} -> {C.index.max().date()}, tickers with data: {C.notna().any().sum()}/34")
    dq = data_quality(O, C, V)
    print("\nData quality (median across tickers by era):")
    print(dq.groupby('era')[['pct_zero_volume', 'pct_open_eq_prevclose', 'pct_open_eq_close', 'pct_close_unchanged']].median().round(4).to_string())
    worst = dq[dq.era == '2000-07'].sort_values('pct_open_eq_prevclose', ascending=False).head(8)
    print("Worst opens 2000-07:\n", worst[['ticker', 'pct_zero_volume', 'pct_open_eq_prevclose', 'pct_close_unchanged']].round(3).to_string(index=False))

    good = (V > 0) & C.notna() & (O > 0)
    Cg, Og = C.where(good), O.where(good)
    rc = Cg / Cg.shift(1) - 1                           # close-to-close return on day t
    bad = rc.abs() > 0.4
    print(f"Masking {int(bad.sum().sum())} ETF-days with |return| > 40%")
    rc = rc.where(~bad)

    # execution return matrices, row t = holding-period return after signal at close t
    R = {
        'E1_close_close': rc.shift(-1),
        'E2_open_close': (Cg.shift(-1) / Og.shift(-1) - 1),
        'E3_open_open': (Og.shift(-2) / Og.shift(-1) - 1),
        'E4_skipday': rc.shift(-2),
    }
    for k in R:
        R[k] = R[k].where(R[k].abs() < 0.4)

    ewret = rc.mean(axis=1)

    def signal(L, resid):
        r = (np.log1p(rc)).rolling(L, min_periods=L).sum()
        r = np.expm1(r)
        if resid:
            cov = rc.rolling(120, min_periods=60).cov(ewret)
            var = ewret.rolling(120, min_periods=60).var()
            beta = cov.div(var, axis=0).shift(1)
            mkt = np.expm1(np.log1p(ewret).rolling(L).sum())
            r = r - beta.mul(mkt, axis=0)
        return -r          # higher = bigger loser = buy

    xl = {}
    # ---------------------------------------------------------------- primary
    print("\n=== PRIMARY (pre-registered): L=1, H=1, quintile, raw, E3 open->open ===")
    sig1 = signal(1, False)
    book, tlo, tls = run_book(sig1, R['E3_open_open'], 0.2, 1)
    book.to_parquet(run / 'daily_returns.parquet')
    sc = scorecard(pd.DataFrame({'strat': book['long_only'], 'bench': book['ew']}), 'PRIMARY long-only losers vs EW', tlo)
    sc += scorecard(pd.DataFrame({'strat': book['long_short'], 'bench': 0 * book['ew']}), 'PRIMARY long-short (vs 0)', tls)
    sc = pd.DataFrame(sc)
    print(sc.drop(columns=['start']).round(3).to_string(index=False))
    xl['primary_scorecard'] = sc

    # ---------------------------------------------------------------- execution comparison
    print("\n=== EXECUTION VARIANTS (L=1,H=1,quintile,raw) long-short, gross ===")
    ex = []
    books = {}
    for k, Rk in R.items():
        b, _, _ = run_book(sig1, Rk, 0.2, 1)
        books[k] = b
        for w, start in [('Full', None), ('5y', 5), ('3y', 3), ('1y', 1)]:
            x = b['long_short'] if start is None else b['long_short'][b.index > b.index.max() - pd.DateOffset(years=start)]
            a, v, s, t = ls_stats(x)
            y = (b['long_only'] - b['ew'])
            y = y if start is None else y[y.index > y.index.max() - pd.DateOffset(years=start)]
            _, _, s2, t2 = ls_stats(y)
            ex.append({'execution': k, 'window': w, 'ls_ann': a, 'ls_vol': v, 'ls_sharpe': s, 'ls_nw_t': t,
                       'longonly_minus_ew_sharpe': s2, 'longonly_minus_ew_t': t2})
    ex = pd.DataFrame(ex)
    print(ex.round(3).to_string(index=False))
    xl['execution'] = ex

    # overnight vs intraday decomposition of E3
    on = (Og.shift(-1) / Cg - 1)  # close t -> open t+1 (what E1 gets but E3 doesn't)
    b_on, _, _ = run_book(sig1, on.where(on.abs() < 0.4), 0.2, 1)
    a, v, s, t = ls_stats(b_on['long_short'])
    print(f"\nOvernight leg only (close T -> open T+1, NOT capturable after seeing close): "
          f"ann {a:.3f}, Sharpe {s:.2f}, t {t:.1f}")

    # ---------------------------------------------------------------- by year
    yr = pd.DataFrame({k: b['long_short'].groupby(b.index.year).sum() for k, b in books.items()})
    print("\nLong-short sum of daily returns by year:\n", yr.round(3).to_string())
    xl['by_year_ls'] = yr

    # ---------------------------------------------------------------- grid
    print("\n=== ROBUSTNESS GRID (long-short Sharpe; Full / last 5y) ===")
    grid = []
    for L, H, q, resid, ek in itertools.product([1, 2, 3, 5, 10], [1, 2, 5], [1 / 3, 0.2, 0.1], [False, True],
                                                ['E1_close_close', 'E3_open_open', 'E4_skipday']):
        s_ = signal(L, resid)
        b, tlo_, tls_ = run_book(s_, R[ek], q, H)
        x = b['long_short']
        x5 = x[x.index > x.index.max() - pd.DateOffset(years=5)]
        y = b['long_only'] - b['ew']
        y5 = y[y.index > y.index.max() - pd.DateOffset(years=5)]
        grid.append({'L': L, 'H': H, 'q': round(q, 3), 'resid': resid, 'exec': ek,
                     'ls_sharpe_full': ls_stats(x)[2], 'ls_t_full': ls_stats(x)[3],
                     'ls_sharpe_5y': ls_stats(x5)[2], 'ls_t_5y': ls_stats(x5)[3],
                     'lo_ew_sharpe_full': ls_stats(y)[2], 'lo_ew_sharpe_5y': ls_stats(y5)[2],
                     'ls_ann_full': x.mean() * 252, 'ls_ann_5y': x5.mean() * 252, 'turnover_ls': tls_})
    grid = pd.DataFrame(grid)
    xl['grid'] = grid
    e3 = grid[grid['exec'] == 'E3_open_open']
    print("E3 open->open, quintile: LS Sharpe by lookback x hold (raw | resid), Full then 5y")
    for col in ['ls_sharpe_full', 'ls_sharpe_5y']:
        t = e3[e3.q == 0.2].pivot_table(index='L', columns=['resid', 'H'], values=col)
        print(f"-- {col}\n{t.round(2).to_string()}")
    print("\nQuantile breadth (L=1,H=1,raw):")
    print(grid[(grid.L == 1) & (grid.H == 1) & (~grid.resid)][['q', 'exec', 'ls_sharpe_full', 'ls_sharpe_5y', 'ls_ann_5y']].round(3).to_string(index=False))

    # ---------------------------------------------------------------- subsets
    print("\n=== SUBSETS (L=1,H=1,quintile,raw,E3) ===")
    sub = []
    sets = {'ALL': UNIVERSE, 'ex-US': [t for t in UNIVERSE if t not in US],
            'Asia': sorted(ASIA), 'Europe/Africa/ME': [t for t in UNIVERSE if t not in ASIA | AMER],
            'Americas': sorted(AMER), 'Liquid18': sorted(LIQUID), 'Thin16': [t for t in UNIVERSE if t not in LIQUID]}
    for nm, tk in sets.items():
        qq = 0.2 if len(tk) >= 15 else 1 / 3
        s_ = sig1[tk]
        lo, sh, ew = quantile_weights(s_, qq)
        # relax min names for small sets
        n = s_.notna().sum(axis=1)
        r = s_.rank(axis=1, pct=True)
        lo = (r > 1 - qq).astype(float); sh = (r <= qq).astype(float)
        ok = n >= 5
        lo = lo.div(lo.sum(axis=1).replace(0, np.nan), axis=0).where(ok, 0).fillna(0)
        sh = sh.div(sh.sum(axis=1).replace(0, np.nan), axis=0).where(ok, 0).fillna(0)
        Rk = R['E3_open_open'][tk]
        x = ((lo - sh) * Rk.fillna(0)).sum(axis=1)[ok.cummax()]
        for w, yrs in [('Full', None), ('5y', 5), ('3y', 3)]:
            xx = x if yrs is None else x[x.index > x.index.max() - pd.DateOffset(years=yrs)]
            a, v, s, t = ls_stats(xx)
            sub.append({'subset': nm, 'n_tickers': len(tk), 'quantile': round(qq, 3), 'window': w,
                        'ls_ann': a, 'ls_sharpe': s, 'nw_t': t})
    sub = pd.DataFrame(sub)
    print(sub.round(3).to_string(index=False))
    xl['subsets'] = sub

    # ---------------------------------------------------------------- jackknife
    print("\n=== LEAVE-ONE-ETF-OUT (primary LS, E3) ===")
    jk = []
    for t in UNIVERSE:
        tk = [u for u in UNIVERSE if u != t]
        b, _, _ = run_book(sig1[tk], R['E3_open_open'][tk], 0.2, 1)
        x = b['long_short']
        x5 = x[x.index > x.index.max() - pd.DateOffset(years=5)]
        jk.append({'dropped': t, 'ls_sharpe_full': ls_stats(x)[2], 'ls_sharpe_5y': ls_stats(x5)[2]})
    jk = pd.DataFrame(jk).sort_values('ls_sharpe_5y')
    print(jk.round(3).head(6).to_string(index=False))
    print(f"Range 5y Sharpe across drops: {jk.ls_sharpe_5y.min():.2f} .. {jk.ls_sharpe_5y.max():.2f}")
    xl['jackknife'] = jk

    # ---------------------------------------------------------------- E5: 15:30 signal (2y)
    print("\n=== E5: 15:30 ET signal, enter at close / at 15:30 (last ~2y) ===")
    e5 = None
    try:
        hourly = pd.read_parquet(DATA / 'etf_hourly.parquet')
        du = pd.read_parquet(DATA / 'etf_daily_unadj.parquet')
        need = [t for t in UNIVERSE if t not in hourly.columns]
        if need:
            import yfinance as yf
            h = yf.download(need, period='730d', interval='60m', auto_adjust=False, progress=False, group_by='column')['Open']
            if isinstance(h, pd.Series):
                h = h.to_frame(need[0])
            idx = pd.to_datetime(h.index)
            h.index = idx.tz_convert('America/New_York').tz_localize(None) if idx.tz is not None else idx
            hourly = hourly.join(h, how='outer')
            d = yf.download(need, start='2023-06-01', auto_adjust=False, actions=True, progress=False, group_by='column')
            cl, dv = d['Close'], d['Dividends'].fillna(0.0)
            if isinstance(cl, pd.Series):
                cl, dv = cl.to_frame(need[0]), dv.to_frame(need[0])
            cl.index = dv.index = pd.to_datetime(cl.index).tz_localize(None)
            du = pd.concat({'close': du['close'].join(cl, how='outer'), 'div': du['div'].join(dv, how='outer')}, axis=1)
            hourly.to_parquet(DATA / 'etf_hourly.parquet')
            du.to_parquet(DATA / 'etf_daily_unadj.parquet')
        cu, dv = du['close'][UNIVERSE], du['div'][UNIVERSE].fillna(0.0)
        p1530 = hourly[hourly.index.time == pd.Timestamp('15:30').time()][UNIVERSE].copy()
        p1530.index = p1530.index.normalize()
        days = cu.index.intersection(p1530.index)
        cu_, dv_, p_ = cu.reindex(days), dv.reindex(days), p1530.reindex(days)
        prev = cu.shift(1).reindex(days)
        r1530 = (p_ + dv_) / prev - 1
        rclose = (cu_ + dv_) / prev - 1
        nxt = (cu.shift(-1).reindex(days) + dv.shift(-1).reindex(days)) / cu_ - 1
        nxt1530 = (cu.shift(-1).reindex(days) + dv.shift(-1).reindex(days)) / p_ - 1  # entry after ex-date: no same-day dividend (fixed 2026-10-05, GPT review)
        for m in [r1530, rclose, nxt, nxt1530]:
            m[m.abs() > 0.3] = np.nan
        e5 = []
        for nm, sg, fw in [('ORACLE close signal -> close', -rclose, nxt),
                           ('15:30 signal -> enter close (MOC)', -r1530, nxt),
                           ('15:30 signal -> enter 15:30', -r1530, nxt1530)]:
            b, _, _ = run_book(sg, fw, 0.2, 1)
            a, v, s, t = ls_stats(b['long_short'])
            _, _, s2, t2 = ls_stats(b['long_only'] - b['ew'])
            e5.append({'variant': nm, 'days': len(b), 'ls_ann': a, 'ls_sharpe': s, 'ls_nw_t': t,
                       'longonly_minus_ew_sharpe': s2, 'longonly_minus_ew_t': t2})
        # same window, E3 daily-data version for comparison
        b3 = books['E3_open_open'].loc[days.min():days.max()]
        a, v, s, t = ls_stats(b3['long_short'])
        _, _, s2, t2 = ls_stats(b3['long_only'] - b3['ew'])
        e5.append({'variant': 'E3 close signal -> open/open (same window)', 'days': len(b3), 'ls_ann': a,
                   'ls_sharpe': s, 'ls_nw_t': t, 'longonly_minus_ew_sharpe': s2, 'longonly_minus_ew_t': t2})
        e5 = pd.DataFrame(e5)
        print(f"Window {days.min().date()} -> {days.max().date()}")
        print(e5.round(3).to_string(index=False))
        xl['E5_1530'] = e5
    except Exception as exc:  # report, never fake
        print(f"E5 FAILED: {exc!r}")

    # ---------------------------------------------------------------- report
    xl['data_quality'] = dq
    with pd.ExcelWriter(run / 'reversal_results.xlsx') as w:
        for k, v in xl.items():
            v.to_excel(w, sheet_name=k[:31], index=(k == 'by_year_ls'))

    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(3, 1, figsize=(10, 11))
    for k, col, lab in [('E3_open_open', '#1f5fa8', 'PRIMARY: enter next open (E3)'),
                        ('E1_close_close', '#b0b0b0', 'enter at signal close (E1, ~ 15:30-signal MOC)')]:
        b = books[k]
        rel = np.log((1 + b['long_only']).cumprod() / (1 + b['ew']).cumprod())
        axes[0].plot(rel.index, rel.values, color=col, lw=1.2, label=lab)
    axes[0].axhline(0, color='grey', lw=0.6)
    axes[0].set_title('Long-only losers quintile vs equal-weight — cumulative net (log wealth ratio), gross', loc='left')
    axes[0].legend(frameon=False, fontsize=8)
    for k, col in [('E1_close_close', '#b0b0b0'), ('E3_open_open', '#1f5fa8'), ('E4_skipday', '#c0504d'),
                   ('E2_open_close', '#7a9a01')]:
        x = books[k]['long_short']
        axes[1].plot(x.index, np.log1p(x).cumsum(), label=k, color=col, lw=1.1)
    axes[1].set_title('Long-short, cumulative log return by execution timing', loc='left')
    axes[1].legend(frameon=False, fontsize=8)
    for k, col in [('E3_open_open', '#1f5fa8'), ('E1_close_close', '#b0b0b0')]:
        x = books[k]['long_short']
        roll = x.rolling(504).mean() / x.rolling(504).std() * np.sqrt(252)
        axes[2].plot(roll.index, roll, label=k, color=col, lw=1.1)
    axes[2].axhline(0, color='grey', lw=0.6)
    axes[2].set_title('Rolling 2-year Sharpe of the long-short book', loc='left')
    axes[2].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(run / 'reversal_report.pdf')

    summary = {'run_dir': str(run), 'primary': sc.round(4).to_dict(orient='records'),
               'execution': ex.round(4).to_dict(orient='records'),
               'E5': None if e5 is None else e5.round(4).to_dict(orient='records')}
    json.dump(summary, open(run / 'summary.json', 'w'), indent=2, default=str)
    print(f"\nDone. {run}")


if __name__ == '__main__':
    main()
