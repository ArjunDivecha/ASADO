#!/usr/bin/env python
"""
==============================================================================
SCRIPT NAME: etf_reversal_us_sectors.py
VERSION:     1.0  (2026-10-07)
==============================================================================

DESCRIPTION
-----------
Does the LIVE Daily Reversal rule, which trades 34 country ETFs, also work on
US sector and US industry ETFs?  The rule is applied exactly as specified by
the live code (Daily Reversal/dr/signal.py + config/strategy.json), with NO
per-universe retuning:

  r_i    = today's return (E1: adjusted close/close; E5: 15:30 ET price plus
           any ex-date dividend over the previous unadjusted close)
  sd_i   = std of the last 60 daily close-to-close returns through t-1
           (min 40 obs)
  z_i    = (r_i - cross-sectional mean r) / sd_i over names with valid data
  pick   = argmin z
  size   = $20,000 if |z_pick| >= 80th pct of the trailing 252 days' |z_pick|
           (min 126 obs; E1 uses its own E1 history, E5 its own E5 history as
           in etf_reversal_double_top.py), else $10,000
  hold   close t -> close t+1
  sleeve return = P&L$ / $20,000 (cash backed; $10k days are half invested)

Universe rules: a name joins once it has 60 days of price history (dynamic
membership; nothing removed in hindsight).  A day is tradeable only if at
least max(8, ceil(0.8 x names with any price that day)) names have a valid z.
Benchmark = equal-weight, daily-rebalanced basket of the universe's live
names (members with a next-day return).

Books (same signal):
  live      the live rule above (sleeve weight 0.5 or 1.0)
  one_name  one name, constant full size (no doubling)
  q5_long   long-only bottom quintile of z, equal weight
            (n = max(1, round(valid names / 5)))
Active return convention: idle sleeve capital is treated as sitting in the
equal-weight benchmark, i.e. active_t = weight_t x (pick return - EW return)
(the convention of etf_reversal_sizing.py / etf_reversal_double_top.py).
The sleeve's absolute stats (CAGR, vol, Sharpe, max drawdown) use the
cash-backed sleeve return with idle capital earning zero.

Universes:
  CONTROL                     34 country ETFs from config/strategy.json
  US_SECTORS                  11 SPDR sectors (XLRE/XLC enter when listed)
  US_INDUSTRIES               30 US industry ETFs (GDX, TAN, PBW hold
                              meaningful non-US assets)
  US_SECTORS_PLUS_INDUSTRIES  union of the two

Control reproduction: the rule is first run on the CACHED country data with
the reference conventions of etf_reversal_double_top.py (>= 10 valid names,
no 60-day entry rule, reference 100%/200% sizing) and compared cell by cell
with runs/double_top_20261007_003049/summary.json.  The run stops if the
reference reproduction misses by more than 0.02 Sharpe.

Mechanism decomposition: each held position's next-day return is split into
overnight (adjusted close t -> adjusted open t+1) and daytime (open t+1 ->
close t+1), active vs EW the same way.

GROSS returns only (house rule).  Turnover is reported as a fact, never as a
penalty.

INPUT FILES
-----------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/Daily Reversal/config/strategy.json   (read only)
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_ohlcv_34.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_hourly.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_daily_unadj.parquet
      (cached country data used for the reproduction check only)
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/runs/double_top_20261007_003049/summary.json
      (reference numbers)
  Yahoo Finance via yfinance (network), unless the caches below already exist

OUTPUT FILES
------------
  Price caches (new files; written once, reused afterwards; existing data/ files untouched):
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/us_sectors_ohlcv_adj_<YYYYMMDD>.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/us_sectors_hourly_<YYYYMMDD>.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/us_sectors_daily_unadj_<YYYYMMDD>.parquet
  Run directory:
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/runs/us_sectors_<YYYYMMDD_HHMMSS>/
      results.parquet            scorecard (every universe x dataset x book x window)
      daily.parquet              daily sleeve / active / overnight / daytime series
      us_sectors_results.xlsx    scorecard, reproduction, overnight_daytime, subperiods,
                                 bootstrap, E1_vs_E5_same_dates, pick_attribution, data_coverage
      us_sectors_report.pdf      charts (+ PNG renders via pdftoppm)
      summary.json, log.txt

DEPENDENCIES
------------
  pandas, numpy, statsmodels, matplotlib, openpyxl, yfinance (ASADO venv);
  pdftoppm (poppler) for PNG renders.
  Imports helpers from etf_reversal_sweep.py (Tee, load) and
  etf_reversal_volscaled.py (sharpe, boot_sharpe_diff) in this folder.

USAGE
-----
  "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/venv/bin/python" \
      "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/etf_reversal_us_sectors.py" [--refresh]

NOTES
-----
  * Sharpe ratios are mean/std x sqrt(252) with no risk-free deduction, as in
    the earlier scripts in this folder.
  * The ticker lists are today's survivors; a fund that closed before today
    is not in any universe.  None of the requested tickers is delisted.
  * Undefined table cells are written as an em dash in the xlsx.
==============================================================================
"""
import argparse
import json
import math
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).parent))
import etf_reversal_sweep as sw  # noqa: E402
import etf_reversal_volscaled as vs  # noqa: E402

EXP = sw.EXP
DATA = sw.DATA
STRATEGY_JSON = Path('/Users/arjundivecha/Dropbox/AAA Backup/A Working/Daily Reversal/config/strategy.json')
REF_SUMMARY = EXP / 'runs/double_top_20261007_003049/summary.json'
TODAY = datetime.now().strftime('%Y%m%d')

SECTORS = 'XLK XLF XLE XLV XLI XLY XLP XLU XLB XLRE XLC'.split()
INDUSTRIES = ('SMH SOXX IGV KRE KBE KIE XBI IBB IHI XHB ITB XRT XOP OIH XES GDX XME JETS ITA XAR IYT XTN '
              'IHF XPH XHE IYR CIBR SKYY TAN PBW').split()
NON_US_HEAVY = ['GDX', 'TAN', 'PBW']

LOOKBACK, MIN_OBS, ENTRY_DAYS = 60, 40, 60
CUT_LB, CUT_MIN, CUT_Q = 252, 126, 0.8
MIN_FLOOR, MIN_FRAC = 8, 0.8
SUBPERIODS = [('2000-09', '2000-01-01', '2009-12-31'), ('2010-19', '2010-01-01', '2019-12-31'),
              ('2020-26', '2020-01-01', '2026-12-31')]
RNG = np.random.default_rng(20261007)
COLORS = {'CONTROL': '#1f5fa8', 'US_SECTORS': '#c0504d', 'US_INDUSTRIES': '#d79b00',
          'US_SECTORS_PLUS_INDUSTRIES': '#4b8b3b'}


def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ----------------------------------------------------------------------------- data
def _norm_index(idx, to_ny=False):
    idx = pd.to_datetime(idx)
    if idx.tz is not None:
        idx = idx.tz_convert('America/New_York').tz_localize(None) if to_ny else idx.tz_localize(None)
    return idx


def _atomic_parquet(df, path):
    tmp = path.with_suffix('.tmp')
    df.to_parquet(tmp)
    tmp.rename(path)


def fetch_all(tickers, refresh):
    """Daily adjusted OHLCV (full history), 60-minute bars (730d), daily unadjusted close + dividends."""
    p_adj = DATA / f'us_sectors_ohlcv_adj_{TODAY}.parquet'
    p_h = DATA / f'us_sectors_hourly_{TODAY}.parquet'
    p_u = DATA / f'us_sectors_daily_unadj_{TODAY}.parquet'
    if all(p.exists() for p in (p_adj, p_h, p_u)) and not refresh:
        log(f"Using cached downloads: {p_adj.name}, {p_h.name}, {p_u.name}")
        return pd.read_parquet(p_adj), pd.read_parquet(p_h), pd.read_parquet(p_u), [p_adj, p_h, p_u]
    if refresh:
        for p in (p_adj, p_h, p_u):
            if p.exists():
                raise SystemExit(f"Refusing to overwrite existing cache {p}; delete it by hand if you really mean it")
    import yfinance as yf
    log(f"Downloading daily adjusted OHLCV for {len(tickers)} tickers from Yahoo ...")
    d = yf.download(tickers, start='1998-12-01', auto_adjust=True, progress=False, group_by='column', threads=True)
    adj = pd.concat({k: d[k] for k in ['Open', 'High', 'Low', 'Close', 'Volume']}, axis=1)
    adj.index = _norm_index(adj.index)
    log(f"Downloading 60-minute bars (730 days) ...")
    h = yf.download(tickers, period='730d', interval='60m', auto_adjust=False, progress=False, group_by='column',
                    prepost=False, threads=True)
    hourly = h['Open'].copy()
    hourly.index = _norm_index(hourly.index, to_ny=True)
    log(f"Downloading daily unadjusted closes and dividends since 2023-06-01 ...")
    u = yf.download(tickers, start='2023-06-01', auto_adjust=False, actions=True, progress=False, group_by='column',
                    threads=True)
    unadj = pd.concat({'close': u['Close'], 'div': u['Dividends'].fillna(0.0)}, axis=1)
    unadj.index = _norm_index(unadj.index)
    # drop a partial session if the download happened while the market was open
    now_et = pd.Timestamp.now(tz='America/New_York')
    if now_et.time() < pd.Timestamp('16:30').time():
        today = now_et.normalize().tz_localize(None)
        adj, unadj = adj[adj.index < today], unadj[unadj.index < today]
        hourly = hourly[hourly.index < today]
        log(f"Market not yet closed at download time ({now_et}); dropped rows dated {today.date()}")
    _atomic_parquet(adj, p_adj)
    _atomic_parquet(hourly, p_h)
    _atomic_parquet(unadj, p_u)
    log(f"Cached: {p_adj}\n        {p_h}\n        {p_u}")
    return adj, hourly, unadj, [p_adj, p_h, p_u]


def build_datasets(adj, hourly, unadj, tick):
    """E1 and E5 panels for one universe, mirroring etf_reversal_sweep.load() plus membership,
    any-price counts and the overnight/daytime split."""
    O, C, V = adj['Open'][tick], adj['Close'][tick], adj['Volume'][tick]
    keep = C.notna().any(axis=1)                      # this universe's own trading calendar
    O, C, V = O[keep], C[keep], V[keep]
    good = (V > 0) & C.notna() & (O > 0)
    Cg, Og = C.where(good), O.where(good)
    rc = Cg / Cg.shift(1) - 1
    rc = rc.where(rc.abs() < 0.4)
    sd = rc.rolling(LOOKBACK, min_periods=MIN_OBS).std().shift(1)
    # membership: >= 60 days with a price strictly before t
    member = C.notna().astype(int).cumsum().shift(1).fillna(0) >= ENTRY_DAYS
    n_any = C.notna().sum(axis=1)
    on = Og.shift(-1) / Cg - 1                         # close t -> open t+1 (adjusted)
    day = Cg.shift(-1) / Og.shift(-1) - 1              # open t+1 -> close t+1
    on, day = on.where(on.abs() < 0.4), day.where(day.abs() < 0.4)
    e1 = {'sig': rc, 'fwd': rc.shift(-1), 'sd': sd, 'member': member, 'n_any': n_any, 'on': on, 'day': day}

    cu, dv = unadj['close'].reindex(columns=tick), unadj['div'].reindex(columns=tick).fillna(0.0)
    cu = cu[cu.notna().any(axis=1)]
    dv = dv.reindex(cu.index).fillna(0.0)
    hh = hourly.reindex(columns=tick)
    p1530 = hh[hh.index.time == pd.Timestamp('15:30').time()].copy()
    p1530.index = p1530.index.normalize()
    days = cu.index.intersection(p1530.index)
    prev = cu.shift(1).reindex(days)
    r1530 = (p1530.reindex(days) + dv.reindex(days)) / prev - 1
    nxt = (cu.shift(-1).reindex(days) + dv.shift(-1).reindex(days)) / cu.reindex(days) - 1
    r1530, nxt = r1530.where(r1530.abs() < 0.3), nxt.where(nxt.abs() < 0.3)
    e5 = {'sig': r1530, 'fwd': nxt, 'sd': sd.reindex(days), 'member': member.reindex(days).fillna(False),
          'n_any': cu.reindex(days).notna().sum(axis=1), 'on': on.reindex(days), 'day': day.reindex(days)}
    return e1, e5


# ----------------------------------------------------------------------------- rule engine
def run_rule(ds, mode='spec', with_parts=True):
    """mode 'spec': 60-day entry, min valid names = max(8, ceil(0.8 x names priced)), EW over members.
       mode 'reference': etf_reversal_double_top.py conventions (>= 10 valid names, EW over all names)."""
    ret, fwd, sd = ds['sig'].copy(), ds['fwd'].copy(), ds['sd']
    if mode == 'spec':
        ret = ret.where(ds['member'])
        fwd = fwd.where(ds['member'])
    ok = ret.notna() & sd.notna() & (sd > 0)
    r, s = ret.where(ok), sd.where(ok)
    z = r.sub(r.mean(axis=1), axis=0) / s
    nval = ok.sum(axis=1)
    if mode == 'spec':
        need = np.maximum(MIN_FLOOR, np.ceil(MIN_FRAC * ds['n_any']))
        valid = nval >= need
    else:
        valid = nval >= 10
    zv = z[valid]
    pick = zv.idxmin(axis=1)
    zpick = -zv.min(axis=1)
    cut = zpick.rolling(CUT_LB, min_periods=CUT_MIN).quantile(CUT_Q).shift(1)
    start = cut.first_valid_index()
    idx = z.index[z.index >= start]
    if mode == 'reference':
        idx = idx[valid.reindex(idx).values]           # reference keeps valid days only
    idx = idx[:-1]                                     # last row has no next-day return
    valid_i = valid.reindex(idx)
    sel1 = pd.DataFrame(False, index=idx, columns=z.columns)
    pk = pick.reindex(idx)
    for t, p in pk.dropna().items():
        sel1.at[t, p] = True
    # bottom quintile of z
    nq = (nval.reindex(idx) / 5).round().clip(lower=1)
    rk = z.reindex(idx).rank(axis=1, method='first', ascending=True)
    selq = rk.le(nq, axis=0).mul(valid_i.astype(bool), axis=0).astype(bool)
    wq = selq.astype(float).div(selq.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)

    f = fwd.reindex(idx)
    ew = f.mean(axis=1)
    big = (zpick.reindex(idx) >= cut.reindex(idx))
    w_live = pd.Series(np.where(big, 1.0, 0.5), index=idx).where(valid_i, 0.0)
    w_one = pd.Series(1.0, index=idx).where(valid_i, 0.0)

    f_pick = f.where(sel1).sum(axis=1, min_count=1)
    pick_rel = (f_pick - ew).fillna(0.0)
    f_q = (wq * f.fillna(0.0)).sum(axis=1)
    out = pd.DataFrame({'ew': ew, 'valid': valid_i, 'pick': pk, 'zpick': zpick.reindex(idx), 'cut': cut.reindex(idx),
                        'w_live': w_live, 'n_valid': nval.reindex(idx), 'n_any': ds['n_any'].reindex(idx) if 'n_any' in ds else np.nan})
    out['sleeve_live'] = w_live * f_pick.fillna(0.0)
    out['active_live'] = w_live * pick_rel
    out['sleeve_one'] = w_one * f_pick.fillna(0.0)
    out['active_one'] = w_one * pick_rel
    out['sleeve_q5'] = f_q.where(valid_i, 0.0)
    out['active_q5'] = (f_q - ew).where(valid_i & (wq.sum(axis=1) > 0), 0.0)
    # reference-scale sizing (100% / 200%) for the reproduction check
    out['active_ref_base'] = pick_rel.where(valid_i, 0.0)
    out['active_ref_double'] = (2 * w_live) * pick_rel
    if with_parts:
        for part in ('on', 'day'):
            g = ds[part].reindex(idx).where(f.notna())   # same names as the EW basket
            g_ew = g.mean(axis=1)
            g_pick = g.where(sel1).sum(axis=1, min_count=1)
            rel = (g_pick - g_ew).fillna(0.0)
            out[f'active_live_{part}'] = w_live * rel
            out[f'active_one_{part}'] = w_one * rel
            gq = (wq * g.fillna(0.0)).sum(axis=1)
            out[f'active_q5_{part}'] = (gq - g_ew).where(valid_i & (wq.sum(axis=1) > 0), 0.0)
            out[f'ew_{part}'] = g_ew
    out = out[out['ew'].notna()]
    # turnover (fraction of the $20k sleeve, two-sided, ignoring intraday drift)
    wmat = sel1.astype(float).mul(w_live, axis=0).reindex(out.index)
    out['turnover_live'] = wmat.diff().abs().sum(axis=1).fillna(wmat.abs().sum(axis=1))
    out['turnover_q5'] = wq.reindex(out.index).diff().abs().sum(axis=1).fillna(1.0)
    return out


# ----------------------------------------------------------------------------- metrics
def nw_t(x):
    x = pd.Series(x).dropna()
    if len(x) < 20 or x.std() == 0:
        return np.nan
    return sm.OLS(x.values, np.ones(len(x))).fit(cov_type='HAC', cov_kwds={'maxlags': 5}).tvalues[0]


def sharpe(x):
    x = pd.Series(x).dropna()
    return x.mean() / x.std() * np.sqrt(252) if len(x) > 1 and x.std() > 0 else np.nan


def window_slices(o, windows):
    """Month-based windows exactly as etf_reversal_double_top.scorecard: last n calendar months."""
    months = o.index.to_period('M').unique()
    res = []
    for w, n in windows:
        if n and len(months) < n:
            continue
        m0 = months[0] if n is None else months[-n]
        res.append((w, o.loc[str(m0.start_time.date()):]))
    return res


def book_stats(dd, book):
    s, a, ew = dd[f'sleeve_{book}'], dd[f'active_{book}'], dd['ew']
    strat = ew + a                                             # idle capital in EW
    per = dd.index.to_period('M')
    ms, mb = (1 + strat).groupby(per).prod() - 1, (1 + ew).groupby(per).prod() - 1
    am = ms - mb
    k = len(ms)
    yrs = len(s) / 252
    wealth = (1 + s).cumprod()
    cum_act = np.log1p(strat).cumsum() - np.log1p(ew).cumsum()
    d = {'start': str(dd.index.min().date()), 'end': str(dd.index.max().date()), 'days': len(dd),
         'sleeve_CAGR': wealth.iloc[-1] ** (1 / yrs) - 1, 'sleeve_vol': s.std() * np.sqrt(252),
         'sleeve_sharpe': sharpe(s), 'sleeve_maxDD': (1 - wealth / wealth.cummax()).max(),
         'EW_CAGR': (1 + ew).prod() ** (1 / yrs) - 1, 'EW_sharpe': sharpe(ew),
         'active_CAGR': ((1 + ms).prod() ** (12 / k) - 1) - ((1 + mb).prod() ** (12 / k) - 1),
         'active_ann_arith': a.mean() * 252, 'active_vol': a.std() * np.sqrt(252),
         'active_sharpe_daily': sharpe(a), 'IR_monthly': am.mean() / am.std() * np.sqrt(12) if am.std() > 0 else np.nan,
         'active_nw_t': nw_t(a), 'active_maxDD_log': (cum_act.cummax() - cum_act).max(),
         'hit_rate_active': (a[dd['valid']] > 0).mean(), 'hit_rate_sleeve': (s[dd['valid']] > 0).mean(),
         'pct_days_traded': dd['valid'].mean()}
    if book == 'live':
        d['pct_days_20k'] = (dd['w_live'] == 1.0).mean()
        d['turnover_ann'] = dd['turnover_live'].mean() * 252
    elif book == 'q5':
        d['turnover_ann'] = dd['turnover_q5'].mean() * 252
    if f'active_{book}_on' in dd:
        d['active_on_ann'] = dd[f'active_{book}_on'].mean() * 252
        d['active_day_ann'] = dd[f'active_{book}_day'].mean() * 252
        d['active_on_t'] = nw_t(dd[f'active_{book}_on'])
        d['active_day_t'] = nw_t(dd[f'active_{book}_day'])
        tot = d['active_on_ann'] + d['active_day_ann']
        d['active_on_share'] = d['active_on_ann'] / tot if tot > 0 else np.nan   # undefined when no positive total
    return d


def boot_sharpe_zero(a, reps=2000, block=10):
    """One-sample stationary bootstrap of the annualised Sharpe (index scheme copied from
    etf_reversal_volscaled.boot_sharpe_diff).  Returns 95% CI and p = share of draws <= 0."""
    n = len(a)
    A = a.values
    out = np.empty(reps)
    for r in range(reps):
        starts = RNG.integers(0, n, size=n)
        new = RNG.random(n) < 1.0 / block
        new[0] = True
        seg = np.cumsum(new) - 1
        seg_start = np.flatnonzero(new)
        offs = np.arange(n) - seg_start[seg]
        idx = (starts[seg_start][seg] + offs) % n
        x = A[idx]
        out[r] = x.mean() / x.std() * np.sqrt(252)
    return np.percentile(out, [2.5, 97.5]), (out <= 0).mean()


def em_dash(df):
    return df.astype(object).where(df.notna(), '—')


# ----------------------------------------------------------------------------- reproduction
def reproduce_control(run):
    log("=== CONTROL REPRODUCTION on cached country data (reference conventions) ===")
    ref = json.load(open(REF_SUMMARY))['scorecard']
    e1c, e5c = sw.load()
    rows = []
    for tag, ds, wins in [('E1', e1c, [('Full', None), ('5y', 60), ('3y', 36), ('1y', 12)]),
                          ('E5', e5c, [('Full', None), ('1y', 12)])]:
        o_ref = run_rule(ds, 'reference', with_parts=False)
        ds_spec = dict(ds)
        if 'member' not in ds_spec:
            C = pd.read_parquet(DATA / 'etf_ohlcv_34.parquet')['Close'][sw.UNIVERSE]
            mem = C.notna().astype(int).cumsum().shift(1).fillna(0) >= ENTRY_DAYS
            ds_spec['member'] = mem.reindex(ds['sig'].index).fillna(False)
            if tag == 'E1':
                ds_spec['n_any'] = C.notna().sum(axis=1).reindex(ds['sig'].index)
            else:
                du = pd.read_parquet(DATA / 'etf_daily_unadj.parquet')['close'][sw.UNIVERSE]
                ds_spec['n_any'] = du.notna().sum(axis=1).reindex(ds['sig'].index)
        o_spec = run_rule(ds_spec, 'spec', with_parts=False)
        dsname = 'E1 idealised close, 2000-2026' if tag == 'E1' else 'E5 15:30 signal MOC, 2023-11..2026-10'
        for refbook, col in [('100% every day', 'active_ref_base'),
                             ('200% on top-quintile days (trailing cutoff)', 'active_ref_double')]:
            for w, n in wins:
                rr = [x for x in ref if x['dataset'] == dsname and x['book'] == refbook and x['window'] == w][0]
                row = {'dataset': tag, 'book': refbook, 'window': w,
                       'ref_net_ann': rr['net_ann'], 'ref_IR_monthly': rr['IR_monthly'],
                       'ref_daily_active_sharpe': rr['daily_active_sharpe']}
                for lab, o in [('repro', o_ref), ('spec', o_spec)]:
                    sl = dict(window_slices(o, [(w, n)])).get(w)
                    a, ew = sl[col], sl['ew']
                    strat = ew + a
                    per = sl.index.to_period('M')
                    ms, mb = (1 + strat).groupby(per).prod() - 1, (1 + ew).groupby(per).prod() - 1
                    k = len(ms)
                    am = ms - mb
                    row[f'{lab}_net_ann'] = ((1 + ms).prod() ** (12 / k) - 1) - ((1 + mb).prod() ** (12 / k) - 1)
                    row[f'{lab}_IR_monthly'] = am.mean() / am.std() * np.sqrt(12)
                    row[f'{lab}_daily_active_sharpe'] = sharpe(a)
                rows.append(row)
    rep = pd.DataFrame(rows)
    rep['repro_sharpe_gap'] = rep['repro_daily_active_sharpe'] - rep['ref_daily_active_sharpe']
    rep['spec_sharpe_gap'] = rep['spec_daily_active_sharpe'] - rep['ref_daily_active_sharpe']
    pd.set_option('display.width', 250)
    print(rep.round(3).to_string(index=False))
    worst = rep['repro_sharpe_gap'].abs().max()
    log(f"Largest |Sharpe gap| reference-convention reproduction: {worst:.4f}; "
        f"spec-convention: {rep['spec_sharpe_gap'].abs().max():.4f}")
    return rep, worst


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--refresh', action='store_true', help='re-download even if today\'s caches exist')
    args = ap.parse_args()
    t0 = datetime.now()
    run = EXP / 'runs' / ('us_sectors_' + t0.strftime('%Y%m%d_%H%M%S'))
    run.mkdir(parents=True)
    sys.stdout = sw.Tee(run / 'log.txt')
    log(f"Run dir: {run}")

    cfg = json.load(open(STRATEGY_JSON))
    control = list(cfg['universe'])
    assert set(control) == set(sw.UNIVERSE), 'strategy.json universe differs from the research universe'
    log(f"Live config: base ${cfg['base_usd']}, extreme ${cfg['extreme_usd']}, q {cfg['extreme_quantile']}, "
        f"vol {cfg['vol_lookback']}/{cfg['vol_min_obs']}, cutoff {cfg['cutoff_lookback']}/{cfg['cutoff_min_obs']}")
    assert (cfg['vol_lookback'], cfg['vol_min_obs'], cfg['cutoff_lookback'], cfg['cutoff_min_obs'],
            cfg['extreme_quantile']) == (LOOKBACK, MIN_OBS, CUT_LB, CUT_MIN, CUT_Q)

    # 1. control reproduction -------------------------------------------------
    rep, worst = reproduce_control(run)
    rep.to_parquet(run / 'reproduction.parquet')
    if worst > 0.02:
        log(f"STOP: reference reproduction misses by {worst:.3f} Sharpe (> 0.02). Not continuing.")
        json.dump({'status': 'STOPPED_REPRODUCTION_FAILED', 'worst_gap': worst,
                   'reproduction': rep.round(4).to_dict(orient='records')}, open(run / 'summary.json', 'w'), indent=2)
        sys.exit(1)

    # 2. data -------------------------------------------------------------------
    all_t = list(dict.fromkeys(control + SECTORS + INDUSTRIES))
    adj, hourly, unadj, cache_files = fetch_all(all_t, args.refresh)
    cov = []
    missing = []
    for t in all_t:
        c = adj['Close'][t].dropna() if t in adj['Close'] else pd.Series(dtype=float)
        hcol = hourly[t].dropna() if t in hourly else pd.Series(dtype=float)
        if c.empty:
            missing.append(t)
        v = adj['Volume'][t].reindex(c.index) if not c.empty else pd.Series(dtype=float)
        r = c.pct_change()
        cov.append({'ticker': t, 'group': 'CONTROL' if t in control else ('US_SECTORS' if t in SECTORS else 'US_INDUSTRIES'),
                    'first_date': str(c.index.min().date()) if not c.empty else None,
                    'last_date': str(c.index.max().date()) if not c.empty else None,
                    'daily_rows': len(c), 'zero_volume_days': int((v <= 0).sum()) if not c.empty else None,
                    'abs_ret_ge_40pct_dropped': int((r.abs() >= 0.4).sum()) if not c.empty else None,
                    'hourly_1530_bars': int((hcol.index.time == pd.Timestamp('15:30').time()).sum()) if not hcol.empty else 0,
                    'non_us_holdings_flag': t in NON_US_HEAVY})
    cov = pd.DataFrame(cov)
    print(cov.to_string(index=False))
    if missing:
        log(f"Tickers Yahoo could not serve (dropped): {missing}")
    universes = {'CONTROL': [t for t in control if t not in missing],
                 'US_SECTORS': [t for t in SECTORS if t not in missing],
                 'US_INDUSTRIES': [t for t in INDUSTRIES if t not in missing]}
    universes['US_SECTORS_PLUS_INDUSTRIES'] = universes['US_SECTORS'] + universes['US_INDUSTRIES']

    # 3. backtests --------------------------------------------------------------
    score, outs, attrib, sub_rows, boot_rows = [], {}, [], [], []
    for uname, tick in universes.items():
        e1, e5 = build_datasets(adj, hourly, unadj, tick)
        for tag, ds, wins in [('E1', e1, [('Full', None), ('5y', 60), ('3y', 36), ('1y', 12)]),
                              ('E5', e5, [('Full', None), ('1y', 12)])]:
            o = run_rule(ds, 'spec')
            outs[(uname, tag)] = o
            log(f"{uname} {tag}: {o.index.min().date()} -> {o.index.max().date()}, {len(o)} days, "
                f"traded {o['valid'].mean():.1%}, median valid names {o['n_valid'].median():.0f}")
            o.to_parquet(run / f'daily_{uname}_{tag}.parquet')        # incremental persistence
            for w, dd in window_slices(o, wins):
                for book in ['live', 'one', 'q5']:
                    score.append(dict(book_stats(dd, book), universe=uname, dataset=tag, window=w, book=book))
            # pick attribution (live rule, full sample)
            vv = o[o['valid']]
            for t, g in vv.groupby('pick'):
                attrib.append({'universe': uname, 'dataset': tag, 'ticker': t, 'pick_share': len(g) / len(vv),
                               'active_contrib_ann': g['active_live'].sum() / len(o) * 252,
                               'active_on_contrib_ann': g['active_live_on'].sum() / len(o) * 252,
                               'active_day_contrib_ann': g['active_live_day'].sum() / len(o) * 252,
                               'mean_active_bp_when_picked': g['active_live'].mean() * 1e4})
            if tag == 'E1':
                for lab, a_, b_ in SUBPERIODS:
                    dd = o.loc[a_:b_]
                    if len(dd) < 126:
                        continue
                    for book in ['live', 'one', 'q5']:
                        x = dd[f'active_{book}']
                        sub_rows.append({'universe': uname, 'subperiod': lab, 'book': book, 'start': str(dd.index.min().date()),
                                         'end': str(dd.index.max().date()), 'days': len(dd),
                                         'active_ann_arith': x.mean() * 252, 'active_sharpe_daily': sharpe(x),
                                         'active_nw_t': nw_t(x), 'active_on_ann': dd[f'active_{book}_on'].mean() * 252,
                                         'active_day_ann': dd[f'active_{book}_day'].mean() * 252,
                                         'sleeve_sharpe': sharpe(dd[f'sleeve_{book}'])})
                for book in ['one', 'live']:
                    a = o[f'active_{book}']
                    ci, p = boot_sharpe_zero(a)
                    br = {'universe': uname, 'book': book, 'test': 'Sharpe vs zero (full E1)', 'start': str(a.index.min().date()),
                          'sharpe': sharpe(a), 'CI95_lo': ci[0], 'CI95_hi': ci[1], 'boot_p_sharpe<=0': p}
                    boot_rows.append(br)
    # paired: each US universe vs control on common dates (E1, one name and live)
    for uname in ['US_SECTORS', 'US_INDUSTRIES', 'US_SECTORS_PLUS_INDUSTRIES']:
        for book in ['one', 'live']:
            a = outs[(uname, 'E1')][f'active_{book}']
            b = outs[('CONTROL', 'E1')][f'active_{book}']
            common = a.index.intersection(b.index)
            ci, p = vs.boot_sharpe_diff(a.loc[common], b.loc[common])
            boot_rows.append({'universe': uname, 'book': book, 'test': 'paired Sharpe difference vs CONTROL (common E1 dates)',
                              'start': str(common.min().date()), 'sharpe': sharpe(a.loc[common]) - sharpe(b.loc[common]),
                              'CI95_lo': ci[0], 'CI95_hi': ci[1], 'boot_p_sharpe<=0': p})

    # E1 vs E5 on identical dates (diagnostic added after run 1 showed E5 > E1 for US industries)
    same = []
    for uname in universes:
        a, b = outs[(uname, 'E1')], outs[(uname, 'E5')]
        c = a.index.intersection(b.index)
        a, b = a.loc[c], b.loc[c]
        dis = a['pick'] != b['pick']
        _, e5ds = build_datasets(adj, hourly, unadj, universes[uname])
        e1sig = build_datasets(adj, hourly, unadj, universes[uname])[0]['sig'].reindex(e5ds['sig'].index)
        late = (1 + e1sig) / (1 + e5ds['sig']) - 1                 # approx. 15:30 -> close move
        lp = lambda o: pd.Series([late.at[i, p] if isinstance(p, str) else np.nan for i, p in o['pick'].items()]).mean()
        for book in ['one', 'live']:
            ci, p = vs.boot_sharpe_diff(b[f'active_{book}'], a[f'active_{book}'])
            same.append({'universe': uname, 'book': book, 'start': str(c.min().date()), 'days': len(c),
                         'pick_agreement': 1 - dis.mean(), 'disagree_days': int(dis.sum()),
                         'E1_active_sharpe': sharpe(a[f'active_{book}']), 'E5_active_sharpe': sharpe(b[f'active_{book}']),
                         'E5_minus_E1_CI95_lo': ci[0], 'E5_minus_E1_CI95_hi': ci[1], 'boot_p_E5<=E1': p,
                         'E1_ann_active_disagree_days': a.loc[dis, f'active_{book}'].sum() / len(c) * 252,
                         'E5_ann_active_disagree_days': b.loc[dis, f'active_{book}'].sum() / len(c) * 252,
                         'E1_pick_last30min_move_bp': lp(a) * 1e4, 'E5_pick_last30min_move_bp': lp(b) * 1e4,
                         'corr_E1_E5_active': a[f'active_{book}'].corr(b[f'active_{book}'])})
    same = pd.DataFrame(same)

    res = pd.DataFrame(score)
    first = ['universe', 'dataset', 'book', 'window']
    res = res[first + [c for c in res.columns if c not in first]]
    sub, boot, att = pd.DataFrame(sub_rows), pd.DataFrame(boot_rows), pd.DataFrame(attrib)
    att = att.sort_values(['universe', 'dataset', 'active_contrib_ann'], ascending=[True, True, False])
    onday = res[['universe', 'dataset', 'book', 'window', 'active_ann_arith', 'active_on_ann', 'active_day_ann',
                 'active_on_t', 'active_day_t', 'active_on_share']].copy()

    pd.set_option('display.width', 260)
    pd.set_option('display.max_columns', 40)
    print("\n=== LIVE RULE scorecard ===")
    print(res[res.book == 'live'][first + ['start', 'sleeve_CAGR', 'sleeve_vol', 'sleeve_sharpe', 'sleeve_maxDD', 'active_CAGR',
                                           'active_sharpe_daily', 'IR_monthly', 'active_nw_t', 'hit_rate_active',
                                           'pct_days_20k', 'pct_days_traded']].round(3).to_string(index=False))
    print("\n=== ONE NAME constant size / Q5 long-only (active) ===")
    print(res[res.book != 'live'][first + ['active_CAGR', 'active_sharpe_daily', 'IR_monthly', 'active_nw_t',
                                           'sleeve_sharpe']].round(3).to_string(index=False))
    print("\n=== OVERNIGHT vs DAYTIME (annual active, arithmetic) ===")
    print(onday.round(3).to_string(index=False))
    print("\n=== E1 SUB-PERIODS ===")
    print(sub.round(3).to_string(index=False))
    print("\n=== BOOTSTRAP ===")
    print(boot.round(3).to_string(index=False))
    print("\n=== E1 vs E5 ON IDENTICAL DATES ===")
    print(same.round(3).to_string(index=False))
    print("\n=== PICK ATTRIBUTION (live rule, top 8 per universe/dataset) ===")
    print(att.groupby(['universe', 'dataset']).head(8).round(4).to_string(index=False))

    # 4. outputs ----------------------------------------------------------------
    res.to_parquet(run / 'results.parquet')
    daily = pd.concat({f'{u}_{t}': o[[c for c in o.columns if c.startswith(('sleeve_', 'active_', 'ew'))]]
                       for (u, t), o in outs.items()}, axis=1)
    daily.columns = ['|'.join(c) for c in daily.columns]
    daily.to_parquet(run / 'daily.parquet')
    for (u, t) in outs:
        (run / f'daily_{u}_{t}.parquet').unlink()                     # superseded by daily.parquet
    with pd.ExcelWriter(run / 'us_sectors_results.xlsx') as w:
        em_dash(res).to_excel(w, sheet_name='scorecard', index=False)
        em_dash(rep).to_excel(w, sheet_name='control_reproduction', index=False)
        em_dash(onday).to_excel(w, sheet_name='overnight_daytime', index=False)
        em_dash(sub).to_excel(w, sheet_name='subperiods_E1', index=False)
        em_dash(boot).to_excel(w, sheet_name='bootstrap', index=False)
        em_dash(same).to_excel(w, sheet_name='E1_vs_E5_same_dates', index=False)
        em_dash(att).to_excel(w, sheet_name='pick_attribution', index=False)
        em_dash(cov).to_excel(w, sheet_name='data_coverage', index=False)

    # charts (light mode, matplotlib)
    plt.style.use('default')
    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False,
                         'figure.facecolor': 'white', 'axes.facecolor': 'white'})
    pdfp = run / 'us_sectors_report.pdf'
    with PdfPages(pdfp) as pdf:
        for tag, title in [('E1', 'E1 idealised close signal, full history'), ('E5', 'E5 15:30 ET signal, market-on-close, last ~2 years')]:
            fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
            for ax, book, lab in [(axes[0], 'live', 'live rule ($10k / $20k on extreme days, sleeve = $20k)'),
                                  (axes[1], 'one', 'one name, constant full size')]:
                for u in universes:
                    o = outs[(u, tag)]
                    rel = np.log1p(o['ew'] + o[f'active_{book}']).cumsum() - np.log1p(o['ew']).cumsum()
                    ax.plot(rel.index, rel, color=COLORS[u], lw=1.1,
                            label=f"{u} (active Sharpe {sharpe(o[f'active_{book}']):.2f})")
                ax.axhline(0, color='black', lw=0.4)
                ax.set_ylabel('cumulative active log return vs EW')
                ax.set_title(f'{title}: {lab}', loc='left')
                ax.legend(frameon=False, fontsize=8, loc='upper left')
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)
        # overnight vs daytime bars
        fig, axes = plt.subplots(1, 3, figsize=(13, 4.8), sharey=False)
        for ax, (tag, w) in zip(axes, [('E1', 'Full'), ('E1', '5y'), ('E5', 'Full')]):
            s = onday[(onday.dataset == tag) & (onday.window == w) & (onday.book == 'live')].set_index('universe').reindex(list(universes))
            x = np.arange(len(s))
            ax.bar(x - 0.2, s['active_on_ann'] * 100, 0.4, color='#1f5fa8', label='overnight (close t to open t+1)')
            ax.bar(x + 0.2, s['active_day_ann'] * 100, 0.4, color='#d79b00', label='daytime (open t+1 to close t+1)')
            ax.set_xticks(x, [u.replace('US_SECTORS_PLUS_INDUSTRIES', 'SECT+IND').replace('US_', '') for u in s.index], fontsize=8)
            ax.axhline(0, color='black', lw=0.5)
            ax.set_title(f'{tag} {w}: live rule, annual active return (%)', loc='left', fontsize=9)
        axes[0].legend(frameon=False, fontsize=8)
        fig.suptitle('Where the reversal is earned: overnight vs daytime, active vs equal-weight (gross)', x=0.01, ha='left')
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)
        # sub-periods
        fig, ax = plt.subplots(figsize=(11, 4.5))
        s = sub[sub.book == 'live'].pivot(index='subperiod', columns='universe', values='active_sharpe_daily')
        s = s.reindex(columns=[u for u in universes if u in s.columns])
        x = np.arange(len(s))
        wdt = 0.8 / max(1, s.shape[1])
        for i, u in enumerate(s.columns):
            ax.bar(x + (i - (s.shape[1] - 1) / 2) * wdt, s[u], wdt, color=COLORS[u], label=u)
        ax.set_xticks(x, s.index)
        ax.axhline(0, color='black', lw=0.5)
        ax.set_ylabel('daily active Sharpe')
        ax.set_title('E1 live rule by sub-period (US industries 2000-09 bar covers 2005-11 to 2009 only)', loc='left')
        ax.legend(frameon=False, fontsize=8)
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)
    subprocess.run(['pdftoppm', '-png', '-r', '90', str(pdfp), str(run / 'us_sectors_report')], check=True)

    summary = {'run_dir': str(run), 'elapsed_sec': (datetime.now() - t0).total_seconds(),
               'cache_files': [str(p) for p in cache_files], 'dropped_tickers': missing,
               'universes': universes, 'reproduction_worst_sharpe_gap': worst,
               'reproduction': rep.round(4).to_dict(orient='records'),
               'live_scorecard': res[res.book == 'live'].round(4).to_dict(orient='records'),
               'overnight_daytime': onday.round(4).to_dict(orient='records'),
               'subperiods': sub.round(4).to_dict(orient='records'), 'bootstrap': boot.round(4).to_dict(orient='records'),
               'e1_vs_e5_same_dates': same.round(4).to_dict(orient='records')}
    json.dump(summary, open(run / 'summary.json', 'w'), indent=2, default=str)
    log(f"Done in {(datetime.now() - t0).total_seconds():.0f}s. {run}")


if __name__ == '__main__':
    main()
