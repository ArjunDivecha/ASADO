#!/usr/bin/env python
"""
==============================================================================
SCRIPT NAME: etf_reversal_sizing.py
VERSION:     1.0  (2026-10-07)
==============================================================================

DESCRIPTION
-----------
Does sizing positions by the SIZE OF THE MOVE improve the one-day country-ETF
reversal trade?  Every earlier test used fixed sizes (one name = 100% of the
book; seven names = 1/7 each).  Signal throughout is the relative-vol measure
z = (r - cross-sectional mean of r) / own trailing-60d daily std (more
negative = bigger relative loser).  Long-only, judged against the equal-weight
benchmark of the 34 house ETFs; any capital not allocated to picks sits in
the benchmark (contributes zero active return).

Variants (fixed before results were seen, 2026-10-07):
  Diagnostic   next-day active return of the pick by |z| quintile (does the
               payoff grow with the size of the move?)
  Baselines    raw7  : 7 biggest raw losers, 1/7 each
               zrel7 : 7 most negative z, 1/7 each
               zrel1 : single most negative z, 100%
  1. Signal-weighted across names
               zrel7_sigw : 7 most negative z, weight proportional to -z
               allneg_sigw: every name with z < 0, weight proportional to -z
  2. One-name sized by extremeness (trailing thresholds, no look-ahead)
               zrel1_scaled: size = min(1, |z| / trailing-252d 80th pct of |z_pick|)
               zrel1_tier  : size = 1 if |z| >= trailing-252d median |z_pick|, else 0.5
  3. Risk-equalised
               zrel1_invvol: size = min(1, universe median own-vol / pick's own vol)
               zrel7_invvol: 7 most negative z, weight proportional to 1/own vol

Datasets: E1 (close-to-close, idealised, 2000-2026: Full and last 5y, gross)
and E5 (15:30 Yahoo signal, MOC, 2023-11..2026-10: gross and NET of the
measured half pre-close spread + $0.0035/share commission from
auction_cost_analysis.py v1.1).  Paired comparison of each variant against
its baseline: Sharpe difference with stationary-bootstrap 95% CI.

INPUT FILES
-----------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_ohlcv_34.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_hourly.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_daily_unadj.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/bbg_auction/daily.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/runs/costs_20261006_003528/cost_results.xlsx
      (sheet etf_liquidity: per-ETF pre-close/TWAS spread ratio)

OUTPUT FILES
------------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/runs/sizing_<timestamp>/
      sizing_results.xlsx, sizing_report.pdf (+ PNG renders), daily_active.parquet,
      summary.json, log.txt

DEPENDENCIES
------------
  pandas, numpy, statsmodels, matplotlib, openpyxl (project venv); pdftoppm

USAGE
-----
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
  venv/bin/python experiments/2026_10_etf_gap_fill/etf_reversal_sizing.py
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
import etf_reversal_volscaled as vs  # noqa: E402

EXP = sw.EXP
TICK = sw.UNIVERSE
COMM = 0.0035
COST_RUN = EXP / 'runs/costs_20261006_003528/cost_results.xlsx'
BASE_OF = {'raw7': None, 'zrel7': None, 'zrel1': None,
           'zrel7_sigw': 'zrel7', 'allneg_sigw': 'zrel7', 'zrel7_invvol': 'zrel7',
           'zrel1_scaled': 'zrel1', 'zrel1_tier': 'zrel1', 'zrel1_invvol': 'zrel1'}


def prep(ds):
    ret, fwd, sd = ds['sig'], ds['fwd'], ds['sd']
    ok = ret.notna() & sd.notna()                 # eligibility known at T
    ret, sd = ret.where(ok), sd.where(ok)
    valid = ok.sum(axis=1) >= 10
    z = ret.sub(ret.mean(axis=1), axis=0) / sd
    return ret[valid], fwd[valid], sd[valid], z[valid]


def lowest_n(m, n):
    r = m.rank(axis=1, method='first', ascending=True)
    return (r <= n)


def weights(ret, sd, z):
    W = {}
    sel7r = lowest_n(ret, 7)
    W['raw7'] = sel7r.astype(float) / 7
    sel7 = lowest_n(z, 7)
    W['zrel7'] = sel7.astype(float) / 7
    sel1 = lowest_n(z, 1)
    W['zrel1'] = sel1.astype(float)
    s = (-z).clip(lower=0).where(sel7, 0.0)
    W['zrel7_sigw'] = s.div(s.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    s = (-z).clip(lower=0).fillna(0.0)
    W['allneg_sigw'] = s.div(s.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    zpick = (-z).where(sel1).max(axis=1)                      # |z| of the single pick (positive)
    q80 = zpick.rolling(252, min_periods=126).quantile(0.8).shift(1)
    med = zpick.rolling(252, min_periods=126).median().shift(1)
    size_scaled = (zpick / q80).clip(upper=1.0)
    size_tier = np.where(zpick >= med, 1.0, 0.5)
    size_tier = pd.Series(size_tier, index=zpick.index).where(med.notna())
    W['zrel1_scaled'] = sel1.astype(float).mul(size_scaled, axis=0)
    W['zrel1_tier'] = sel1.astype(float).mul(size_tier, axis=0)
    sd_pick = sd.where(sel1).max(axis=1)
    size_iv = (sd.median(axis=1) / sd_pick).clip(upper=1.0)
    W['zrel1_invvol'] = sel1.astype(float).mul(size_iv, axis=0)
    iv = (1 / sd).where(sel7, 0.0)
    W['zrel7_invvol'] = iv.div(iv.sum(axis=1).replace(0, np.nan), axis=0).fillna(0.0)
    # sizing rules need 126 days of trailing history: start every book on the same day
    start = q80.first_valid_index()
    return {k: v.loc[start:].fillna(0.0) for k, v in W.items()}, zpick.loc[start:]


def active_of(W, fwd):
    f = fwd.reindex(W.index)
    ew = f.mean(axis=1)
    return (W * f.sub(ew, axis=0).fillna(0.0)).sum(axis=1)


def stats(x):
    x = x.dropna()
    t = sm.OLS(x.values, np.ones(len(x))).fit(cov_type='HAC', cov_kwds={'maxlags': 5}).tvalues[0]
    return x.mean() * 252, x.mean() / x.std() * np.sqrt(252), t


def main():
    run = EXP / 'runs' / ('sizing_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    run.mkdir(parents=True)
    sys.stdout = sw.Tee(run / 'log.txt')
    print(f"Run dir: {run}")
    e1, e5 = sw.load()

    # cost matrix for E5 (half pre-close spread + commission, bp per $ traded)
    d = pd.read_parquet(EXP / 'data/bbg_auction/daily.parquet')
    d['date'] = pd.to_datetime(d['date'])
    twas = d[d.field == 'TIME_WAVG_BID_ASK_SPREAD_PCT'].pivot(index='date', columns='ticker', values='value').reindex(columns=TICK) * 100
    pxb = d[d.field == 'PX_LAST'].pivot(index='date', columns='ticker', values='value').reindex(columns=TICK)
    liq = pd.read_excel(COST_RUN, sheet_name='etf_liquidity').set_index('ticker')
    ratio = liq['ratio_used'].reindex(TICK)

    rows, pair, buckets, daily_out, books = [], [], [], {}, {}
    for ename, ds in [('E1', e1), ('E5', e5)]:
        ret, fwd, sd, z = prep(ds)
        W, zpick = weights(ret, sd, z)
        days = W['zrel1'].index
        cost_bp = None
        if ename == 'E5':
            hs = (0.5 * twas.reindex(days).ffill() * ratio)
            cost_bp = hs.fillna(hs.median().median()) + (COMM / pxb.reindex(days).ffill() * 1e4).fillna(1.0)
        # diagnostic: pick payoff by |z| quintile
        a1 = active_of(W['zrel1'], fwd)
        for win, sl in ([('Full', slice(None)), ('last 5y', slice(days.max() - pd.DateOffset(years=5), None))]
                        if ename == 'E1' else [('2.9y', slice(None))]):
            zz, aa = zpick.loc[sl], a1.loc[sl]
            q = pd.qcut(zz.rank(method='first'), 5, labels=['Q1 mildest', 'Q2', 'Q3', 'Q4', 'Q5 most extreme'])
            g = aa.groupby(q)
            for lab, x in g:
                buckets.append({'dataset': ename, 'window': win, 'abs_z_quintile': lab,
                                'median_abs_z': zz[q == lab].median(), 'mean_next_day_active_bp': x.mean() * 1e4,
                                't': x.mean() / x.std() * np.sqrt(len(x)), 'days': len(x)})
        for name, w in W.items():
            act = active_of(w, fwd)
            dw = w.diff().abs().fillna(w.abs())
            expo = w.sum(axis=1)
            wins = ([('Full', None), ('last 5y', 5)] if ename == 'E1' else [('2.9y', None)])
            for win, yrs in wins:
                sl = slice(None) if yrs is None else slice(days.max() - pd.DateOffset(years=yrs), None)
                x = act.loc[sl]
                a, s, t = stats(x)
                r = {'dataset': ename, 'window': win, 'book': name, 'ann_active_gross': a, 'sharpe_gross': s,
                     'nw_t_gross': t, 'avg_exposure': expo.loc[sl].mean(),
                     'active_per_unit_exposure': a / expo.loc[sl].mean(),
                     'turnover_per_day': dw.loc[sl].sum(axis=1).mean()}
                if cost_bp is not None:
                    c = (dw * cost_bp / 1e4).sum(axis=1).loc[sl]
                    an, sn, tn = stats(x - c)
                    r.update({'ann_active_net': an, 'sharpe_net': sn, 'cost_bp_per_dollar': c.sum() / dw.loc[sl].sum(axis=1).sum() * 1e4,
                              'breakeven_bp_per_dollar': x.sum() / dw.loc[sl].sum(axis=1).sum() * 1e4})
                    daily_out[f'{ename}_{name}_net'] = x - c
                rows.append(r)
                books[(ename, win, name)] = x if cost_bp is None else (x, x - c)
            daily_out[f'{ename}_{name}_gross'] = act
        for name, base in BASE_OF.items():
            if base is None:
                continue
            for win, yrs in ([('Full', None), ('last 5y', 5)] if ename == 'E1' else [('2.9y', None)]):
                xv = books[(ename, win, name)]
                xb = books[(ename, win, base)]
                for kind, iv, ib in ([('gross', xv, xb)] if ename == 'E1' else
                                     [('gross', xv[0], xb[0]), ('net', xv[1], xb[1])]):
                    ci, p = vs.boot_sharpe_diff(iv, ib)
                    pair.append({'dataset': ename, 'window': win, 'basis': kind, 'variant': name, 'baseline': base,
                                 'sharpe_variant': vs.sharpe(iv), 'sharpe_baseline': vs.sharpe(ib),
                                 'sharpe_diff': vs.sharpe(iv) - vs.sharpe(ib), 'CI95_lo': ci[0], 'CI95_hi': ci[1],
                                 'boot_p_diff<=0': p})
    res, pair, bk = pd.DataFrame(rows), pd.DataFrame(pair), pd.DataFrame(buckets)
    pd.set_option('display.width', 250)
    print("\n=== DIAGNOSTIC: next-day active return of the 1-name pick by how extreme its move was ===")
    print(bk.round(2).to_string(index=False))
    print("\n=== ALL BOOKS ===")
    print(res.round(3).to_string(index=False))
    print("\n=== PAIRED vs BASELINE (Sharpe difference, stationary-bootstrap 95% CI) ===")
    print(pair.round(3).to_string(index=False))

    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False})
    pdfp = run / 'sizing_report.pdf'
    with PdfPages(pdfp) as pdf:
        fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), sharey=False)
        for ax, (en, win) in zip(axes, [('E1', 'Full'), ('E1', 'last 5y'), ('E5', '2.9y')]):
            s = bk[(bk.dataset == en) & (bk.window == win)]
            ax.bar(range(5), s.mean_next_day_active_bp, color='#1f5fa8')
            ax.set_xticks(range(5), [f"{q}\n|z|~{m:.1f}" for q, m in zip(s.abs_z_quintile, s.median_abs_z)], fontsize=7)
            ax.axhline(0, color='black', lw=0.5)
            ax.set_title(f'{en} {win}', loc='left')
        axes[0].set_ylabel('next-day active return of the pick (bp)')
        fig.suptitle('Does the payoff grow with the size of the move? (1-name relative-vol pick, by |z| quintile)', x=0.01, ha='left')
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        fig, axes = plt.subplots(1, 2, figsize=(13, 4.5))
        for ax, group in zip(axes, [['zrel1', 'zrel1_scaled', 'zrel1_tier', 'zrel1_invvol'],
                                    ['raw7', 'zrel7', 'zrel7_sigw', 'allneg_sigw', 'zrel7_invvol']]):
            for nm in group:
                x = daily_out[f'E1_{nm}_gross']
                ax.plot(x.index, x.cumsum(), lw=1.0 if nm not in ('zrel1', 'zrel7') else 1.6, label=nm)
            ax.axhline(0, color='black', lw=0.4)
            ax.legend(frameon=False, fontsize=8)
            ax.set_title('E1 2000-2026: cumulative active return (sum of daily), gross', loc='left')
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(12, 4.5))
        s = res[res.dataset == 'E5']
        x = np.arange(len(s))
        ax.bar(x - 0.2, s.ann_active_gross, 0.4, color='#9a9a9a', label='gross')
        ax.bar(x + 0.2, s.ann_active_net, 0.4, color='#1f5fa8', label='net of half spread + commission')
        ax.set_xticks(x, s.book, rotation=30, fontsize=8)
        ax.axhline(0, color='black', lw=0.5)
        ax.set_ylabel('annual active return vs EW')
        ax.set_title('E5 (15:30 signal, MOC, 2023-11 to 2026-10): gross vs net by sizing scheme', loc='left')
        ax.legend(frameon=False)
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)
    subprocess.run(['pdftoppm', '-png', '-r', '100', str(pdfp), str(run / 'sizing_report')], check=True)

    pd.DataFrame(daily_out).to_parquet(run / 'daily_active.parquet')
    with pd.ExcelWriter(run / 'sizing_results.xlsx') as w:
        res.to_excel(w, sheet_name='books', index=False)
        pair.to_excel(w, sheet_name='paired_vs_baseline', index=False)
        bk.to_excel(w, sheet_name='payoff_by_abs_z', index=False)
    json.dump({'run_dir': str(run), 'books': res.round(4).to_dict(orient='records'),
               'paired': pair.round(4).to_dict(orient='records'), 'buckets': bk.round(3).to_dict(orient='records')},
              open(run / 'summary.json', 'w'), indent=2, default=str)
    print(f"\nDone. {run}")


if __name__ == '__main__':
    main()
