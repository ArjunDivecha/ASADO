#!/usr/bin/env python
"""
==============================================================================
SCRIPT NAME: etf_reversal_volscaled.py
VERSION:     1.0  (2026-10-05)
==============================================================================

DESCRIPTION
-----------
Head-to-head of two ways to pick the losers in the one-day country-ETF
reversal trade (see etf_reversal_1d.py / etf_reversal_sweep.py):

  RAW      rank on the day's raw return; buy the N biggest losers
  VOLSCALED rank on (return - cross-sectional mean) / own trailing-60d daily
           std; buy the N names that underperformed the group by the most
           in units of their own normal volatility

The ONLY difference between the two is dividing by each ETF's own volatility
(subtracting the cross-sectional mean does not change a ranking).  Books are
long-only, equal weight among the N picks, held to the next close, judged
against the equal-weight benchmark of the 34 house ETFs.  N = 1, 2, 3 (the
concentrated books where the choice matters) plus 7 (baseline breadth).

Datasets
  E1  idealised: signal = close-to-close return on day T, trade at that close,
      2000-2026
  E5  implementable: signal = yesterday's close -> 15:30 ET price, trade MOC,
      2023-11 -> 2026-10 (Yahoo 60-minute bars)

Outputs: house scorecard (Full/5y/3y/1y on monthly returns: strategy,
benchmark, net ann., IR, net drawdown, turnover), sub-period Sharpes, paired
difference tests (Newey-West t on the daily return difference; stationary-
bootstrap CI of the Sharpe difference), years won, which ETFs each method
picks and how volatile they are, and a multi-page PDF of charts.

INPUT FILES
-----------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_ohlcv_34.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_hourly.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_daily_unadj.parquet
  (all written by earlier scripts in this experiment; loaded via
   etf_reversal_sweep.load())

OUTPUT FILES
------------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/runs/volscaled_<timestamp>/
      volscaled_report.pdf       charts (one page per topic)
      volscaled_report-<n>.png   PNG renders of each page
      volscaled_results.xlsx     scorecards, sub-periods, paired tests, picks
      daily_active.parquet       daily active returns of every book
      summary.json, log.txt

DEPENDENCIES
------------
  pandas, numpy, statsmodels, matplotlib, openpyxl; pdftoppm for PNG renders

USAGE
-----
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
  venv/bin/python experiments/2026_10_etf_gap_fill/etf_reversal_volscaled.py

NOTES
-----
  Gross returns, no cost/turnover penalty (house rule); turnover reported as
  information.  Trailing std uses data through T-1.
==============================================================================
"""
import json
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

EXP = sw.EXP
NS = [1, 2, 3, 7]
PERIODS = [('2000', '2004'), ('2005', '2009'), ('2010', '2014'), ('2015', '2019'), ('2020', '2022'), ('2023', '2026')]
RNG = np.random.default_rng(7)
BLUE, GREY, RED = '#1f5fa8', '#9a9a9a', '#c0504d'


class Tee(sw.Tee):
    pass


def book(ds, kind, n):
    ret, fwd, sd = ds['sig'], ds['fwd'], ds['sd']
    ok = ret.notna() & sd.notna()   # eligibility known at T (no future-availability filter)
    ret, fwd, sd = ret.where(ok), fwd.where(ok), sd.where(ok)
    valid = ok.sum(axis=1) >= 10
    rank_m, size_m = sw.measure(ret, sd, 'raw' if kind == 'RAW' else 'z_rel')
    w, cnt = sw.select(rank_m, size_m, 0, n, -1)
    f = fwd.fillna(0.0)
    ew = fwd.mean(axis=1)
    strat = (w * f).sum(axis=1)
    out = pd.DataFrame({'strat': strat, 'ew': ew, 'active': strat - ew})[valid]
    turn = w.diff().abs().sum(axis=1)[valid]
    picks = w[valid].gt(0)
    pick_vol = (sd.where(picks)).stack().mean() * np.sqrt(252)
    univ_vol = sd[valid].stack().mean() * np.sqrt(252)
    return out, turn, picks, pick_vol, univ_vol


def nw_t(x):
    x = pd.Series(x).dropna()
    return sm.OLS(x.values, np.ones(len(x))).fit(cov_type='HAC', cov_kwds={'maxlags': 5}).tvalues[0]


def sharpe(x):
    return x.mean() / x.std() * np.sqrt(252)


def boot_sharpe_diff(a, b, reps=2000, block=10):
    n = len(a)
    A, B = a.values, b.values
    diffs = np.empty(reps)
    for r in range(reps):
        # stationary bootstrap indices, vectorised
        starts = RNG.integers(0, n, size=n)
        new = RNG.random(n) < 1.0 / block
        new[0] = True
        seg = np.cumsum(new) - 1
        seg_start = np.flatnonzero(new)
        offs = np.arange(n) - seg_start[seg]
        idx = (starts[seg_start][seg] + offs) % n
        diffs[r] = A[idx].mean() / A[idx].std() * np.sqrt(252) - B[idx].mean() / B[idx].std() * np.sqrt(252)
    return np.percentile(diffs, [2.5, 97.5]), (diffs <= 0).mean()


def scorecard(out, turn, label):
    ms = (1 + out['strat']).groupby(out.index.to_period('M')).prod() - 1
    mb = (1 + out['ew']).groupby(out.index.to_period('M')).prod() - 1
    rows = []
    for w, n in [('Full', None), ('5y', 60), ('3y', 36), ('1y', 12)]:
        s = ms if n is None else ms.iloc[-n:]
        b = mb.loc[s.index]
        if len(s) < n if n else False:
            continue
        a = s - b
        k = len(s)
        sa, ba = (1 + s).prod() ** (12 / k) - 1, (1 + b).prod() ** (12 / k) - 1
        gap = pd.concat([pd.Series([0.0]), ((1 + s).cumprod() - (1 + b).cumprod()).reset_index(drop=True)])
        rows.append({'book': label, 'window': w, 'months': k, 'strategy_ann': sa, 'benchmark_ann': ba,
                     'net_ann': sa - ba, 'IR_monthly': a.mean() / a.std() * np.sqrt(12),
                     'net_drawdown': (gap.cummax() - gap).max(),
                     'turnover_2sided_ann': turn.mean() * 252})
    return rows


def main():
    run = EXP / 'runs' / ('volscaled_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    run.mkdir(parents=True)
    sys.stdout = Tee(run / 'log.txt')
    print(f"Run dir: {run}")
    e1, e5 = sw.load()

    books, sc, picks_tab, vol_tab = {}, [], [], []
    for ename, ds in [('E1', e1), ('E5', e5)]:
        for n in NS:
            for kind in ['RAW', 'VOLSCALED']:
                out, turn, picks, pv, uv = book(ds, kind, n)
                books[(ename, kind, n)] = out
                sc += [dict(r, dataset=ename) for r in scorecard(out, turn, f'{kind} N={n}')]
                vol_tab.append({'dataset': ename, 'method': kind, 'N': n,
                                'avg_ann_vol_of_picks': pv, 'avg_ann_vol_universe': uv})
                if n == 1:
                    for w, sl in [('Full', slice(None)), ('last 5y', slice(out.index.max() - pd.DateOffset(years=5), None))]:
                        p = picks.loc[sl]
                        freq = p.sum() / len(p)
                        for t, v in freq.items():
                            picks_tab.append({'dataset': ename, 'window': w, 'method': kind, 'ticker': t, 'pick_share': v})
    sc = pd.DataFrame(sc)
    vol = pd.DataFrame(vol_tab)
    picks = pd.DataFrame(picks_tab)

    pd.set_option('display.width', 250)
    print("\n=== HOUSE SCORECARD (long-only vs equal-weight, gross) ===")
    print(sc[sc.dataset == 'E1'].round(3).to_string(index=False))
    print("\nE5 (15:30 signal, MOC; ~2y so only 1y and Full windows are meaningful):")
    print(sc[(sc.dataset == 'E5') & sc.window.isin(['Full', '1y'])].round(3).to_string(index=False))

    # sub-period Sharpes + paired tests
    sub, pair = [], []
    for n in NS:
        r, v = books[('E1', 'RAW', n)]['active'], books[('E1', 'VOLSCALED', n)]['active']
        d = v - r
        row = {'N': n}
        for a, b in PERIODS:
            row[f'RAW {a}-{b[2:]}'] = sharpe(r[a:b])
            row[f'VOL {a}-{b[2:]}'] = sharpe(v[a:b])
        r5, v5 = books[('E5', 'RAW', n)]['active'], books[('E5', 'VOLSCALED', n)]['active']
        row['RAW E5'], row['VOL E5'] = sharpe(r5), sharpe(v5)
        sub.append(row)
        yrs = d.groupby(d.index.year).sum()
        for lab, aa, bb in [('E1 Full', v, r), ('E1 last 5y', v[v.index > v.index.max() - pd.DateOffset(years=5)],
                                                  r[r.index > r.index.max() - pd.DateOffset(years=5)]),
                            ('E1 2000-09', v['2000':'2009'], r['2000':'2009']),
                            ('E1 2010-19', v['2010':'2019'], r['2010':'2019']),
                            ('E5 2y', v5, r5)]:
            ci, p = boot_sharpe_diff(aa, bb)
            pair.append({'N': n, 'sample': lab, 'sharpe_RAW': sharpe(bb), 'sharpe_VOL': sharpe(aa),
                         'sharpe_diff': sharpe(aa) - sharpe(bb), 'boot_CI95_lo': ci[0], 'boot_CI95_hi': ci[1],
                         'boot_p_diff<=0': p, 'ann_ret_diff': (aa - bb).mean() * 252, 'nw_t_ret_diff': nw_t(aa - bb),
                         'vol_RAW': bb.std() * np.sqrt(252), 'vol_VOL': aa.std() * np.sqrt(252),
                         'corr': aa.corr(bb),
                         'years_VOL_won': f"{int((yrs > 0).sum())}/{len(yrs)}" if lab == 'E1 Full' else ''})
    sub, pair = pd.DataFrame(sub), pd.DataFrame(pair)
    print("\n=== SUB-PERIOD ACTIVE SHARPE (E1) and E5 ===")
    for n in NS:
        r = sub[sub.N == n].iloc[0]
        line = '  '.join(f"{a}-{b[2:]}: {r[f'RAW {a}-{b[2:]}']:.2f}->{r[f'VOL {a}-{b[2:]}']:.2f}" for a, b in PERIODS)
        print(f"N={n}  RAW->VOLSCALED  {line}  E5: {r['RAW E5']:.2f}->{r['VOL E5']:.2f}")
    print("\n=== PAIRED COMPARISON (VOLSCALED minus RAW) ===")
    print(pair.round(3).to_string(index=False))
    print("\n=== VOLATILITY OF WHAT GETS PICKED (annualised own vol) ===")
    print(vol.round(3).to_string(index=False))
    for ename in ['E1', 'E5']:
        for w in ['Full', 'last 5y']:
            p = picks[(picks.dataset == ename) & (picks.window == w)]
            if p.empty or (ename == 'E5' and w == 'last 5y'):
                continue
            t = p.pivot(index='ticker', columns='method', values='pick_share').sort_values('RAW', ascending=False)
            print(f"\nN=1 pick share by ticker, {ename} {w} (top 10 by RAW):\n{t.head(10).round(3).to_string()}")
            print(f"Top-5 concentration: RAW {t['RAW'].nlargest(5).sum():.2f}, VOLSCALED {t['VOLSCALED'].nlargest(5).sum():.2f}")

    # ------------------------------------------------------------------ charts
    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False,
                         'figure.facecolor': 'white', 'axes.facecolor': 'white'})
    pdfp = run / 'volscaled_report.pdf'
    with PdfPages(pdfp) as pdf:
        # page 1: cumulative active, E1, N=1,2,3,7
        fig, axes = plt.subplots(2, 2, figsize=(11, 8), sharex=True)
        for ax, n in zip(axes.flat, NS):
            for kind, col in [('RAW', GREY), ('VOLSCALED', BLUE)]:
                o = books[('E1', kind, n)]
                rel = np.log((1 + o['strat']).cumprod() / (1 + o['ew']).cumprod())
                ax.plot(rel.index, rel, color=col, lw=1.1,
                        label=f"{'raw move' if kind == 'RAW' else 'vol-scaled relative move'}  (Sharpe {sharpe(o['active']):.2f})")
            ax.axhline(0, color='black', lw=0.4)
            ax.set_title(f'Buy the {n} biggest loser{"s" if n > 1 else ""}', loc='left')
            ax.legend(frameon=False, fontsize=8, loc='upper left')
            ax.set_ylabel('log wealth vs equal-weight')
        fig.suptitle('E1 (idealised close signal), 2000-2026: cumulative net return vs equal-weight, gross', x=0.01, ha='left')
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # page 2: cumulative DIFFERENCE vol-scaled minus raw, with period shading
        fig, ax = plt.subplots(figsize=(11, 5))
        for n, col in zip(NS, ['#08306b', '#2171b5', '#6baed6', '#bdbdbd']):
            d = books[('E1', 'VOLSCALED', n)]['active'] - books[('E1', 'RAW', n)]['active']
            ax.plot(d.index, d.cumsum(), color=col, lw=1.3 if n < 7 else 1.0, label=f'N={n}')
        for i, (a, b) in enumerate(PERIODS):
            if i % 2 == 0:
                ax.axvspan(pd.Timestamp(a), pd.Timestamp(f'{b}-12-31'), color='#f2f2f2', zorder=0)
        ax.axhline(0, color='black', lw=0.4)
        ax.set_title('Vol-scaled minus raw: cumulative difference in daily active return (rising = vol-scaled ahead)', loc='left')
        ax.legend(frameon=False)
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # page 3: sub-period Sharpe bars, N=1,2,3
        fig, axes = plt.subplots(1, 3, figsize=(12, 4.5), sharey=True)
        labels = [f'{a}-{b[2:]}' for a, b in PERIODS] + ['E5 2y\n(MOC)']
        x = np.arange(len(labels))
        for ax, n in zip(axes, [1, 2, 3]):
            r = sub[sub.N == n].iloc[0]
            rv = [r[f'RAW {l}'] for l in labels[:-1]] + [r['RAW E5']]
            vv = [r[f'VOL {l}'] for l in labels[:-1]] + [r['VOL E5']]
            ax.bar(x - 0.2, rv, 0.4, color=GREY, label='raw move')
            ax.bar(x + 0.2, vv, 0.4, color=BLUE, label='vol-scaled relative')
            ax.axhline(0, color='black', lw=0.4)
            ax.set_xticks(x, labels, fontsize=7, rotation=45)
            ax.set_title(f'N={n}: active Sharpe by period', loc='left')
        axes[0].legend(frameon=False, fontsize=8)
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # page 4: E5 implementable, cumulative active N=1,2,3
        fig, axes = plt.subplots(1, 3, figsize=(12, 4.2), sharey=True)
        for ax, n in zip(axes, [1, 2, 3]):
            for kind, col in [('RAW', GREY), ('VOLSCALED', BLUE)]:
                o = books[('E5', kind, n)]
                rel = np.log((1 + o['strat']).cumprod() / (1 + o['ew']).cumprod())
                ax.plot(rel.index, rel, color=col, lw=1.2, label=f"{'raw' if kind == 'RAW' else 'vol-scaled'} (Sharpe {sharpe(o['active']):.2f})")
            ax.axhline(0, color='black', lw=0.4)
            ax.set_title(f'E5 15:30 signal, MOC: N={n}', loc='left')
            ax.legend(frameon=False, fontsize=8)
            ax.tick_params(axis='x', rotation=45)
        axes[0].set_ylabel('log wealth vs equal-weight')
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # page 5: which ETFs get picked (N=1, E1 last 5y) + vol of picks
        fig, axes = plt.subplots(1, 2, figsize=(12, 5.5), gridspec_kw={'width_ratios': [2, 1]})
        p = picks[(picks.dataset == 'E1') & (picks.window == 'last 5y')].pivot(index='ticker', columns='method', values='pick_share')
        p = p.sort_values('RAW', ascending=False)
        xx = np.arange(len(p))
        axes[0].bar(xx - 0.2, p['RAW'], 0.4, color=GREY, label='raw move')
        axes[0].bar(xx + 0.2, p['VOLSCALED'], 0.4, color=BLUE, label='vol-scaled relative')
        axes[0].axhline(1 / 34, color=RED, lw=0.8, ls='--', label='1/34 (even)')
        axes[0].set_xticks(xx, p.index, rotation=90, fontsize=7)
        axes[0].set_title('N=1: share of days each ETF is the pick (E1, last 5y)', loc='left')
        axes[0].legend(frameon=False, fontsize=8)
        v = vol[vol.dataset == 'E1'].pivot(index='N', columns='method', values='avg_ann_vol_of_picks')
        uv = vol[vol.dataset == 'E1']['avg_ann_vol_universe'].iloc[0]
        xx = np.arange(len(v))
        axes[1].bar(xx - 0.2, v['RAW'], 0.4, color=GREY, label='raw')
        axes[1].bar(xx + 0.2, v['VOLSCALED'], 0.4, color=BLUE, label='vol-scaled')
        axes[1].axhline(uv, color=RED, lw=0.8, ls='--', label='universe average')
        axes[1].set_xticks(xx, [f'N={n}' for n in v.index])
        axes[1].set_title('Average own volatility of picked ETFs (E1, full)', loc='left')
        axes[1].legend(frameon=False, fontsize=8)
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        # page 6: rolling 2y Sharpe, N=1
        fig, ax = plt.subplots(figsize=(11, 4.5))
        for kind, col in [('RAW', GREY), ('VOLSCALED', BLUE)]:
            a = books[('E1', kind, 1)]['active']
            ax.plot(a.index, a.rolling(504).mean() / a.rolling(504).std() * np.sqrt(252), color=col, lw=1.1,
                    label='raw move' if kind == 'RAW' else 'vol-scaled relative')
        ax.axhline(0, color='black', lw=0.4)
        ax.set_title('N=1: rolling 2-year active Sharpe (E1)', loc='left')
        ax.legend(frameon=False)
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

    subprocess.run(['pdftoppm', '-png', '-r', '100', str(pdfp), str(run / 'volscaled_report')], check=True)

    daily = pd.DataFrame({f'{e}_{k}_N{n}': o['active'] for (e, k, n), o in books.items()})
    daily.to_parquet(run / 'daily_active.parquet')
    with pd.ExcelWriter(run / 'volscaled_results.xlsx') as w:
        sc.to_excel(w, sheet_name='scorecard', index=False)
        sub.to_excel(w, sheet_name='subperiod_sharpe', index=False)
        pair.to_excel(w, sheet_name='paired_tests', index=False)
        vol.to_excel(w, sheet_name='vol_of_picks', index=False)
        picks.to_excel(w, sheet_name='pick_shares', index=False)
    json.dump({'run_dir': str(run), 'paired': pair.round(4).to_dict(orient='records')},
              open(run / 'summary.json', 'w'), indent=2, default=str)
    print(f"\nDone. {run}")


if __name__ == '__main__':
    main()
