#!/usr/bin/env python
"""
==============================================================================
SCRIPT NAME: etf_reversal_double_top.py
VERSION:     1.0  (2026-10-07)
==============================================================================

DESCRIPTION
-----------
Pre-cost backtest of the one-name relative-vol reversal rule with DOUBLE
weight on the most extreme days, as Arjun asked on 2026-10-07:
  - each day pick the single country ETF with the most negative
    z = (r - cross-sectional mean of r) / own trailing-60d daily std
  - position = 200% of capital if the pick's |z| is in the top quintile,
    otherwise 100%; held to the next close; judged vs the equal-weight
    benchmark of the 34 house ETFs.  Active return = position x (pick's
    next-day return - EW return), i.e. the 200% days double the active bet.
Top-quintile cutoff:
  TRAILING (main, tradeable): 80th percentile of |z_pick| over the previous
           252 trading days (needs 126 days of history; known at T)
  IN-SAMPLE (upper bound, NOT tradeable): 80th percentile over the whole
           sample of each dataset
Compared with the plain 100%-every-day rule on the same days.

Datasets: E1 = idealised close-to-close (signal and trade at the same close),
2000-2026; E5 = 15:30 ET Yahoo signal, trade at the close, 2023-11..2026-10.
GROSS of all costs (house research convention); doubling also doubles the
traded size on the most extreme days, when spreads are widest - see
auction_cost_analysis.py for costs.

Reported per window (Full / 5y / 3y / 1y, house metrics on monthly returns):
strategy ann. return, benchmark ann. return, net (active) ann. return, IR,
plus daily active Sharpe, active vol, max drawdown of the cumulative active
log return, average exposure, share of days doubled, and a paired
stationary-bootstrap CI on the Sharpe difference vs the 100% rule.

INPUT FILES
-----------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_ohlcv_34.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_hourly.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_daily_unadj.parquet

OUTPUT FILES
------------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/runs/double_top_<timestamp>/
      double_top_results.xlsx, double_top_report.pdf (+ PNG renders),
      daily_active.parquet, summary.json, log.txt

DEPENDENCIES
------------
  pandas, numpy, matplotlib, openpyxl (project venv); pdftoppm

USAGE
-----
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
  venv/bin/python experiments/2026_10_etf_gap_fill/etf_reversal_double_top.py
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

sys.path.insert(0, str(Path(__file__).parent))
import etf_reversal_sweep as sw  # noqa: E402
import etf_reversal_volscaled as vs  # noqa: E402
import etf_reversal_sizing as sz  # noqa: E402

EXP = sw.EXP


def books_for(ds):
    ret, fwd, sd, z = sz.prep(ds)
    sel1 = sz.lowest_n(z, 1)
    zpick = (-z).where(sel1).max(axis=1)
    f = fwd.reindex(z.index)
    ew = f.mean(axis=1)
    pick_rel = (f.sub(ew, axis=0)).where(sel1).sum(axis=1, min_count=1).fillna(0.0)
    q80_trail = zpick.rolling(252, min_periods=126).quantile(0.8).shift(1)
    start = q80_trail.first_valid_index()
    q80_ins = zpick.loc[start:].quantile(0.8)
    out = pd.DataFrame({'ew': ew, 'pick_rel': pick_rel, 'zpick': zpick, 'cut_trailing': q80_trail}).loc[start:]
    out['size_base'] = 1.0
    out['size_double_trailing'] = np.where(out.zpick >= out.cut_trailing, 2.0, 1.0)
    out['size_double_insample'] = np.where(out.zpick >= q80_ins, 2.0, 1.0)
    for k in ['base', 'double_trailing', 'double_insample']:
        out[f'active_{k}'] = out[f'size_{k}'] * out['pick_rel']
        out[f'strat_{k}'] = out['ew'] + out[f'active_{k}']
    return out.iloc[:-1]          # last row has no next-day return


def scorecard(o, k, label):
    ms = (1 + o[f'strat_{k}']).groupby(o.index.to_period('M')).prod() - 1
    mb = (1 + o['ew']).groupby(o.index.to_period('M')).prod() - 1
    rows = []
    end = o.index.max()
    for w, n in [('Full', None), ('5y', 60), ('3y', 36), ('1y', 12)]:
        if n and len(ms) < n:
            continue
        s = ms if n is None else ms.iloc[-n:]
        b = mb.loc[s.index]
        a = s - b
        kk = len(s)
        sa, ba = (1 + s).prod() ** (12 / kk) - 1, (1 + b).prod() ** (12 / kk) - 1
        dd = o.loc[str(s.index.min().start_time.date()):]
        x = dd[f'active_{k}']
        cum = np.log1p(dd[f'strat_{k}']).cumsum() - np.log1p(dd['ew']).cumsum()
        rows.append({'book': label, 'window': w, 'start': str(s.index.min()), 'strategy_ann': sa, 'benchmark_ann': ba,
                     'net_ann': sa - ba, 'IR_monthly': a.mean() / a.std() * np.sqrt(12),
                     'daily_active_sharpe': x.mean() / x.std() * np.sqrt(252), 'active_vol_ann': x.std() * np.sqrt(252),
                     'max_dd_active_log': (cum.cummax() - cum).max(), 'avg_exposure': dd[f'size_{k}'].mean(),
                     'pct_days_doubled': (dd[f'size_{k}'] > 1).mean(), 'worst_day_active': x.min()})
    return rows


def main():
    run = EXP / 'runs' / ('double_top_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    run.mkdir(parents=True)
    sys.stdout = sw.Tee(run / 'log.txt')
    print(f"Run dir: {run}")
    e1, e5 = sw.load()
    allrows, pair, daily = [], [], {}
    for ename, ds in [('E1 idealised close, 2000-2026', e1), ('E5 15:30 signal MOC, 2023-11..2026-10', e5)]:
        o = books_for(ds)
        tag = ename.split()[0]
        for k, lab in [('base', '100% every day'), ('double_trailing', '200% on top-quintile days (trailing cutoff)'),
                       ('double_insample', '200% on top-quintile days (in-sample cutoff, upper bound)')]:
            allrows += [dict(r, dataset=ename) for r in scorecard(o, k, lab)]
            daily[f'{tag}_{k}'] = o[f'active_{k}']
        for k in ['double_trailing', 'double_insample']:
            for w, yrs in [('Full', None), ('5y', 5)] if tag == 'E1' else [('Full', None)]:
                a, b = o[f'active_{k}'], o['active_base']
                if yrs:
                    a, b = a[a.index > a.index.max() - pd.DateOffset(years=yrs)], b[b.index > b.index.max() - pd.DateOffset(years=yrs)]
                ci, p = vs.boot_sharpe_diff(a, b)
                pair.append({'dataset': ename, 'window': w, 'variant': k, 'sharpe_variant': vs.sharpe(a),
                             'sharpe_100pct': vs.sharpe(b), 'diff': vs.sharpe(a) - vs.sharpe(b),
                             'CI95_lo': ci[0], 'CI95_hi': ci[1], 'boot_p_diff<=0': p})
        daily[f'{tag}_ew'] = o['ew']
        daily[f'{tag}_size_trailing'] = o['size_double_trailing']
    res, pair = pd.DataFrame(allrows), pd.DataFrame(pair)
    pd.set_option('display.width', 260)
    cols = ['dataset', 'book', 'window', 'strategy_ann', 'benchmark_ann', 'net_ann', 'IR_monthly', 'daily_active_sharpe',
            'active_vol_ann', 'max_dd_active_log', 'avg_exposure', 'pct_days_doubled', 'worst_day_active']
    print("\n=== PRE-COST BACKTEST: one-name relative-vol rule, 100% vs 200% on top-quintile days ===")
    print(res[cols].round(3).to_string(index=False))
    print("\n=== Paired Sharpe difference vs 100% rule (stationary bootstrap 95% CI) ===")
    print(pair.round(3).to_string(index=False))

    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False})
    pdfp = run / 'double_top_report.pdf'
    with PdfPages(pdfp) as pdf:
        for tag, title in [('E1', 'E1 idealised close signal, 2000-2026'), ('E5', 'E5 15:30 signal, MOC, 2023-11 to 2026-10')]:
            fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True, gridspec_kw={'height_ratios': [2, 1]})
            for k, col, lab in [('base', '#9a9a9a', '100% every day'), ('double_trailing', '#1f5fa8', '200% on top-quintile days (trailing cutoff)'),
                                ('double_insample', '#c0504d', '200% on top-quintile days (in-sample cutoff)')]:
                a = daily[f'{tag}_{k}']
                ew = daily[f'{tag}_ew']
                rel = np.log1p(ew + a).cumsum() - np.log1p(ew).cumsum()
                axes[0].plot(rel.index, rel, color=col, lw=1.2 if k != 'double_insample' else 0.9,
                             ls='-' if k != 'double_insample' else '--', label=f'{lab} (Sharpe {vs.sharpe(a):.2f})')
                axes[1].plot(rel.index, rel - rel.cummax(), color=col, lw=0.9, ls='-' if k != 'double_insample' else '--')
            axes[0].axhline(0, color='black', lw=0.4)
            axes[0].set_ylabel('log wealth vs equal-weight')
            axes[0].legend(frameon=False, fontsize=8)
            axes[0].set_title(f'{title}: cumulative net return vs equal-weight, gross', loc='left')
            axes[1].set_ylabel('drawdown (log)')
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)
    subprocess.run(['pdftoppm', '-png', '-r', '100', str(pdfp), str(run / 'double_top_report')], check=True)

    pd.DataFrame(daily).to_parquet(run / 'daily_active.parquet')
    with pd.ExcelWriter(run / 'double_top_results.xlsx') as w:
        res.to_excel(w, sheet_name='scorecard', index=False)
        pair.to_excel(w, sheet_name='paired_vs_100pct', index=False)
    json.dump({'run_dir': str(run), 'scorecard': res.round(4).to_dict(orient='records'),
               'paired': pair.round(4).to_dict(orient='records')}, open(run / 'summary.json', 'w'), indent=2, default=str)
    print(f"\nDone. {run}")


if __name__ == '__main__':
    main()
