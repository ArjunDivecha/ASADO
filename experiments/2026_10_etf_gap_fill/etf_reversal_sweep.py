#!/usr/bin/env python
"""
==============================================================================
SCRIPT NAME: etf_reversal_sweep.py
VERSION:     1.0  (2026-10-05)
==============================================================================

DESCRIPTION
-----------
Parameter sweep of the one-day country-ETF reversal trade found in
etf_reversal_1d.py.  Baseline rule: each day buy the 7 biggest losers of the
34 house ETFs (and short the 6-7 biggest gainers), hold to the next close.
This sweep asks whether picking FEWER names, or only trading when the move is
LARGE (beyond k standard deviations), does better.

Grid (147 cells per execution dataset):
  measure  'raw'     rank on the day's raw return; size test = move vs the
                     day's cross-section, (r - mean) / cross-sectional std
           'z_own'   rank and size test on r / own trailing-60d daily std
                     (an absolute move of k own-sigmas)
           'z_rel'   rank and size test on (r - cross-sectional mean) / own
                     trailing-60d std (underperformed the group by k sigmas)
  k        0, 0.5, 1, 1.5, 2, 2.5, 3    losers need measure <= -k,
                                         gainers (short side) >= +k
  cap N    1, 2, 3, 5, 7, 10, all       most extreme N qualifiers per side
  Selected names are equal-weighted.  Days with no qualifier: long-only
  book sits in the equal-weight benchmark (active return 0); short leg idle.

Books per cell
  long_only_active  mean(next-day return of selected losers) - EW return
  long_short        long_only_active + (EW return - mean(selected gainers))
                    (= losers minus gainers when both sides trade)

Execution datasets
  E1  signal = close-to-close return on day T, trade at the same close,
      exit next close (idealised; 2000-2026 so we can see long history;
      windows Full / 5y / 3y)
  E5  signal = return from yesterday's close to the 15:30 ET price, trade
      market-on-close, exit next close (implementable; Yahoo 60-min bars,
      ~2023-11 -> 2026-10 only)

Multiple-testing control (stationary bootstrap, mean block 10 days, 2000
reps, studentised max statistic in the style of White's Reality Check /
Hansen SPA):
  RC_any       is the best cell's mean active return > 0 beyond luck?
  RC_vs_base   does the best cell beat the baseline cell (raw, k=0, N=7)?

INPUT FILES
-----------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_ohlcv_34.parquet
      (daily auto-adjusted OHLCV, written by etf_reversal_1d.py)
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_hourly.parquet
      (60-minute bar opens, written by etf_gap_fill_intraday.py / etf_reversal_1d.py)
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_daily_unadj.parquet
      (unadjusted closes + dividends, same provenance)

OUTPUT FILES
------------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/runs/sweep_<timestamp>/
      sweep_results.xlsx    every cell x book x window; reality checks
      sweep_heatmaps.pdf    active-Sharpe heatmaps (cap x k) per measure
      summary.json          headline numbers
      log.txt               stdout copy

DEPENDENCIES
------------
  pandas, numpy, statsmodels, matplotlib, openpyxl (project venv)

USAGE
-----
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
  venv/bin/python experiments/2026_10_etf_gap_fill/etf_reversal_sweep.py

NOTES
-----
  * Gross returns; no cost or turnover penalty (house rule).  Turnover and
    gross edge per dollar traded are reported as information only.
  * Trailing std uses returns up to and including day T-1 (known at T).
==============================================================================
"""
import itertools
import json
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

ROOT = Path('/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO')
EXP = ROOT / 'experiments/2026_10_etf_gap_fill'
DATA = EXP / 'data'
UNIVERSE = ('EWS EWA EWC EWG EWJ EWL EWU QQQ SPY EWQ EWN EWD EWI ASHR ECH EIDO EPHE EPOL IWM '
            'EWM EWT EWW EWY EWZ EZA EDEN INDA MCHI EWH THD TUR EWP VNM KSA').split()
MEASURES = ['raw', 'z_own', 'z_rel']
KS = [0, 0.5, 1, 1.5, 2, 2.5, 3]
CAPS = [1, 2, 3, 5, 7, 10, 99]
BASE = ('raw', 0, 7)
RNG = np.random.default_rng(20261005)


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


def load():
    px = pd.read_parquet(DATA / 'etf_ohlcv_34.parquet')
    O, C, V = px['Open'][UNIVERSE], px['Close'][UNIVERSE], px['Volume'][UNIVERSE]
    good = (V > 0) & C.notna() & (O > 0)
    Cg = C.where(good)
    rc = Cg / Cg.shift(1) - 1
    rc = rc.where(rc.abs() < 0.4)
    sd = rc.rolling(60, min_periods=40).std().shift(1)

    e1 = {'sig': rc, 'fwd': rc.shift(-1), 'sd': sd}

    hourly = pd.read_parquet(DATA / 'etf_hourly.parquet')
    du = pd.read_parquet(DATA / 'etf_daily_unadj.parquet')
    cu, dv = du['close'][UNIVERSE], du['div'][UNIVERSE].fillna(0.0)
    p1530 = hourly[hourly.index.time == pd.Timestamp('15:30').time()][UNIVERSE].copy()
    p1530.index = p1530.index.normalize()
    days = cu.index.intersection(p1530.index)
    prev = cu.shift(1).reindex(days)
    r1530 = (p1530.reindex(days) + dv.reindex(days)) / prev - 1
    nxt = (cu.shift(-1).reindex(days) + dv.shift(-1).reindex(days)) / cu.reindex(days) - 1
    r1530 = r1530.where(r1530.abs() < 0.3)
    nxt = nxt.where(nxt.abs() < 0.3)
    e5 = {'sig': r1530, 'fwd': nxt, 'sd': sd.reindex(days)}
    return e1, e5


def measure(ret, sd, kind):
    mu = ret.mean(axis=1)
    if kind == 'raw':
        rank_m = ret
        size_m = ret.sub(mu, axis=0).div(ret.std(axis=1), axis=0)
    elif kind == 'z_own':
        rank_m = size_m = ret / sd
    else:
        rank_m = size_m = ret.sub(mu, axis=0) / sd
    return rank_m, size_m


def select(rank_m, size_m, k, cap, side):
    """side=-1 losers, +1 gainers. Returns equal-weight selection matrix."""
    if side < 0:
        cand = size_m <= -k if k > 0 else size_m.notna()
        r = rank_m.where(cand).rank(axis=1, method='first', ascending=True)
    else:
        cand = size_m >= k if k > 0 else size_m.notna()
        r = rank_m.where(cand).rank(axis=1, method='first', ascending=False)
    sel = (r <= cap).astype(float)
    cnt = sel.sum(axis=1)
    return sel.div(cnt.replace(0, np.nan), axis=0).fillna(0.0), cnt


def run_cell(ds, kind, k, cap):
    ret, fwd, sd = ds['sig'], ds['fwd'], ds['sd']
    ok = ret.notna() & fwd.notna() & sd.notna()
    ret, fwd, sd = ret.where(ok), fwd.where(ok), sd.where(ok)
    nday = ok.sum(axis=1)
    valid = nday >= 10
    rank_m, size_m = measure(ret, sd, kind)
    wl, cl = select(rank_m, size_m, k, cap, -1)
    ws, cs = select(rank_m, size_m, k, cap, +1)
    f = fwd.fillna(0.0)
    ew = fwd.mean(axis=1)
    lo = (wl * f).sum(axis=1)
    sh = (ws * f).sum(axis=1)
    lo_act = (lo - ew).where(cl > 0, 0.0)
    sh_act = (ew - sh).where(cs > 0, 0.0)
    out = pd.DataFrame({'lo_act': lo_act, 'ls': lo_act + sh_act, 'n_long': cl, 'n_short': cs})[valid]
    turn = wl.diff().abs().sum(axis=1)[valid]
    return out, turn


def stats(x, turn=None, active_days=None):
    x = x.dropna()
    sdv = x.std()
    t = sm.OLS(x.values, np.ones(len(x))).fit(cov_type='HAC', cov_kwds={'maxlags': 5}).tvalues[0] if sdv > 0 else np.nan
    d = {'ann_active': x.mean() * 252, 'active_sharpe': x.mean() / sdv * np.sqrt(252) if sdv > 0 else np.nan,
         'nw_t': t, 'days': len(x)}
    if turn is not None:
        tr = turn.reindex(x.index).mean()
        d['turnover_2sided_ann'] = tr * 252
        d['gross_bp_per_dollar_traded'] = (x.mean() / tr * 1e4) if tr > 0 else np.nan
    return d


def boot_idx(n, reps, block=10):
    p = 1.0 / block
    idx = np.empty((reps, n), dtype=np.int64)
    for r in range(reps):
        i = RNG.integers(n)
        for j in range(n):
            if j > 0 and RNG.random() > p:
                i = (i + 1) % n
            else:
                i = RNG.integers(n) if j > 0 else i
            idx[r, j] = i
    return idx


def reality_check(M, idx):
    """M: days x cells. Studentised max test of H0: all means <= 0."""
    n = M.shape[0]
    mu = M.mean(axis=0)
    se = M.std(axis=0, ddof=1) / np.sqrt(n)
    se[se == 0] = np.nan
    T = np.nanmax(mu / se)
    Mc = M - mu
    bmax = np.array([np.nanmax(Mc[ix].mean(axis=0) / se) for ix in idx])
    return float(T), float((bmax >= T).mean())


def main():
    run = EXP / 'runs' / ('sweep_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    run.mkdir(parents=True)
    sys.stdout = Tee(run / 'log.txt')
    print(f"Run dir: {run}")
    e1, e5 = load()
    print(f"E1 {e1['sig'].index.min().date()} -> {e1['sig'].index.max().date()}; "
          f"E5 {e5['sig'].index.min().date()} -> {e5['sig'].index.max().date()} ({len(e5['sig'])} days)")

    cells = list(itertools.product(MEASURES, KS, CAPS))
    rows, series = [], {}
    for ename, ds in [('E1', e1), ('E5', e5)]:
        for (kind, k, cap) in cells:
            out, turn = run_cell(ds, kind, k, cap)
            series[(ename, kind, k, cap)] = out
            end = out.index.max()
            wins = [('Full', None), ('5y', 5), ('3y', 3)] if ename == 'E1' else [('2y', None)]
            for w, yrs in wins:
                o = out if yrs is None else out[out.index > end - pd.DateOffset(years=yrs)]
                for book in ['lo_act', 'ls']:
                    d = stats(o[book], turn if book == 'lo_act' else None)
                    d.update({'exec': ename, 'window': w, 'book': book, 'measure': kind, 'k': k,
                              'cap': 'all' if cap == 99 else cap,
                              'pct_days_long': (o['n_long'] > 0).mean(),
                              'avg_names_long_when_on': o.loc[o['n_long'] > 0, 'n_long'].mean()})
                    rows.append(d)
    res = pd.DataFrame(rows)
    cols = ['exec', 'window', 'book', 'measure', 'k', 'cap', 'ann_active', 'active_sharpe', 'nw_t', 'days',
            'pct_days_long', 'avg_names_long_when_on', 'turnover_2sided_ann', 'gross_bp_per_dollar_traded']
    res = res[cols]

    def show(ex, win, book, title):
        print(f"\n=== {title} ===")
        sub = res[(res['exec'] == ex) & (res.window == win) & (res.book == book)]
        base = sub[(sub.measure == 'raw') & (sub.k == 0) & (sub.cap == 7)].iloc[0]
        print(f"Baseline (raw, k=0, 7 names): Sharpe {base.active_sharpe:.2f}, ann {base.ann_active:.3f}, t {base.nw_t:.1f}")
        for m in MEASURES:
            t = sub[sub.measure == m].pivot_table(index='cap', columns='k', values='active_sharpe', sort=False)
            t = t.reindex([1, 2, 3, 5, 7, 10, 'all'])
            print(f"-- measure={m}: active Sharpe (rows = max names, cols = k sigma)\n{t.round(2).to_string()}")
        top = sub.sort_values('active_sharpe', ascending=False).head(8)
        print("Top 8 cells:\n", top[['measure', 'k', 'cap', 'ann_active', 'active_sharpe', 'nw_t', 'pct_days_long',
                                     'avg_names_long_when_on']].round(3).to_string(index=False))

    show('E5', '2y', 'lo_act', 'E5 (15:30 signal, MOC, ~2y) LONG-ONLY losers vs EW')
    show('E5', '2y', 'ls', 'E5 (15:30 signal, MOC, ~2y) LONG-SHORT')
    show('E1', '5y', 'lo_act', 'E1 (idealised close signal) last 5y LONG-ONLY vs EW')
    show('E1', 'Full', 'lo_act', 'E1 (idealised close signal) 2000-2026 LONG-ONLY vs EW')
    show('E1', '5y', 'ls', 'E1 last 5y LONG-SHORT')

    # cross-dataset agreement: does the E1 5y surface rank cells like E5?
    a = res[(res['exec'] == 'E1') & (res.window == '5y') & (res.book == 'lo_act')].set_index(['measure', 'k', 'cap'])['active_sharpe']
    b = res[(res['exec'] == 'E5') & (res.book == 'lo_act')].set_index(['measure', 'k', 'cap'])['active_sharpe']
    c = res[(res['exec'] == 'E1') & (res.window == 'Full') & (res.book == 'lo_act')].set_index(['measure', 'k', 'cap'])['active_sharpe']
    print(f"\nRank correlation of cell Sharpes: E1-5y vs E5 {a.corr(b, method='spearman'):.2f}; "
          f"E1-Full vs E1-5y {c.corr(a, method='spearman'):.2f}")

    # reality checks
    print("\n=== REALITY CHECKS (stationary bootstrap, 2000 reps, block 10) ===")
    rc_rows = []
    for ex, win, yrs in [('E5', '2y', None), ('E1', '5y', 5), ('E1', 'Full', None)]:
        for book in ['lo_act', 'ls']:
            mats = []
            for cell in cells:
                s = series[(ex,) + cell][book]
                if yrs:
                    s = s[s.index > s.index.max() - pd.DateOffset(years=yrs)]
                mats.append(s)
            M = pd.concat(mats, axis=1).fillna(0.0).values
            bi = cells.index(BASE)
            D = M - M[:, [bi]]
            D = np.delete(D, bi, axis=1)
            idx = boot_idx(M.shape[0], 2000)
            T_any, p_any = reality_check(M, idx)
            T_vb, p_vb = reality_check(D, idx)
            best = cells[int(np.nanargmax(M.mean(axis=0) / M.std(axis=0)))]
            bestd = [c for c in cells if c != BASE][int(np.nanargmax(D.mean(axis=0) / D.std(axis=0)))]
            rc_rows.append({'exec': ex, 'window': win, 'book': book, 'n_cells': len(cells),
                            'best_cell': str(best), 'max_t_any': T_any, 'p_RC_any': p_any,
                            'best_vs_base_cell': str(bestd), 'max_t_vs_base': T_vb, 'p_RC_vs_base': p_vb})
            print(f"{ex} {win} {book:6s}: best {best} t={T_any:.2f} p_any={p_any:.3f} | "
                  f"best-vs-baseline {bestd} t={T_vb:.2f} p={p_vb:.3f}")
    rc = pd.DataFrame(rc_rows)

    with pd.ExcelWriter(run / 'sweep_results.xlsx') as w:
        res.to_excel(w, sheet_name='all_cells', index=False)
        rc.to_excel(w, sheet_name='reality_checks', index=False)
        for ex, win in [('E5', '2y'), ('E1', '5y'), ('E1', 'Full')]:
            for book in ['lo_act', 'ls']:
                sub = res[(res['exec'] == ex) & (res.window == win) & (res.book == book)]
                sub.sort_values('active_sharpe', ascending=False).to_excel(w, sheet_name=f'{ex}_{win}_{book}'[:31], index=False)

    # heatmaps
    with PdfPages(run / 'sweep_heatmaps.pdf') as pdf:
        for book, bname in [('lo_act', 'Long-only losers vs equal-weight'), ('ls', 'Long-short')]:
            fig, axes = plt.subplots(3, 3, figsize=(13, 11))
            for i, (ex, win, lab) in enumerate([('E5', '2y', 'E5: 15:30 signal, MOC (2023-11 to 2026-10)'),
                                                ('E1', '5y', 'E1: idealised close signal, last 5y'),
                                                ('E1', 'Full', 'E1: idealised close signal, 2000-2026')]):
                sub = res[(res['exec'] == ex) & (res.window == win) & (res.book == book)]
                vmax = np.nanmax(np.abs(sub.active_sharpe))
                for j, m in enumerate(MEASURES):
                    t = sub[sub.measure == m].pivot_table(index='cap', columns='k', values='active_sharpe', sort=False)
                    t = t.reindex([1, 2, 3, 5, 7, 10, 'all'])
                    ax = axes[i, j]
                    ax.imshow(t.values, cmap='RdBu', vmin=-vmax, vmax=vmax, aspect='auto')
                    for (r, c), v in np.ndenumerate(t.values):
                        ax.text(c, r, f'{v:.2f}', ha='center', va='center', fontsize=7)
                    ax.set_xticks(range(len(t.columns)), [str(x) for x in t.columns], fontsize=7)
                    ax.set_yticks(range(len(t.index)), [str(x) for x in t.index], fontsize=7)
                    ax.set_xlabel('k (sigma threshold)', fontsize=7)
                    ax.set_ylabel('max names', fontsize=7)
                    ax.set_title(f'{lab}\nmeasure = {m}', fontsize=8, loc='left')
            fig.suptitle(f'{bname}: active Sharpe by max names x size threshold (gross)', fontsize=10)
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)

    json.dump({'run_dir': str(run), 'reality_checks': rc.to_dict(orient='records')},
              open(run / 'summary.json', 'w'), indent=2, default=str)
    print(f"\nDone. {run}")


if __name__ == '__main__':
    main()
