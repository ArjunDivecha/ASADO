"""Top-quintile versus equal-weight portfolio accounting, monthly USD index proxy.
Consumes frozen score/universe/realized-return frames. No fitting or database writes.
Twelve-month sleeves recycle their own NAV; missing held outcomes fail closed.
Version 1, 2026-09-06. Outputs isolated experiment CSV/JSON/PNG artifacts.
"""
import argparse, json, math
from pathlib import Path
import numpy as np
import pandas as pd


def validate(scores, universe, returns):
    for name, frame in [('scores', scores), ('universe', universe), ('returns', returns)]:
        if frame.index.has_duplicates or frame.columns.has_duplicates:
            raise ValueError(f'Duplicate {name} keys')
        if not frame.index.is_monotonic_increasing:
            raise ValueError(f'Unsorted {name}')
    if not scores.index.equals(universe.index) or not scores.columns.equals(universe.columns):
        raise ValueError('Scores and universe must align exactly')
    if universe.isna().any().any():
        raise ValueError('Missing eligibility')
    if not scores.index.isin(returns.index).all() or not scores.columns.isin(returns.columns).all():
        raise ValueError('Missing return dates or countries')
    expected = pd.date_range(scores.index.min(), scores.index.max(), freq='MS')
    if not scores.index.equals(expected):
        raise ValueError('Missing calendar month')
    if not np.isfinite(scores.to_numpy(dtype=float)[universe.to_numpy(dtype=bool)]).all():
        raise ValueError('Missing/nonfinite score for eligible market')
    if universe.sum(axis=1).eq(0).any():
        raise ValueError('Empty universe')


def picks(row, eligible, fraction=0.2):
    if not 0 < fraction <= 1:
        raise ValueError('fraction must be in (0,1]')
    names = list(eligible.index[eligible])
    if not names or not np.isfinite(row.loc[names]).all():
        raise ValueError('Missing eligible score')
    names.sort(key=lambda c: (-float(row[c]), c))
    return names[:math.ceil(len(names) * fraction)]


def simulate(scores, universe, returns, hold_months=1, select=True, fraction=0.2):
    validate(scores, universe, returns)
    if hold_months not in (1, 12):
        raise ValueError('Supported holds are 1 or 12 months')
    columns = scores.columns
    assets = np.zeros((hold_months, len(columns)))
    cash = np.ones(hold_months) / hold_months
    history, contributions, selections = [], [], []
    for j, date in enumerate(scores.index):
        before = float(assets.sum() + cash.sum())
        slot = j % hold_months
        nav = float(assets[slot].sum() + cash[slot])
        assets[slot] = 0
        cash[slot] = 0
        eligible = universe.loc[date]
        chosen = picks(scores.loc[date], eligible, fraction) if select else list(columns[eligible])
        ids = columns.get_indexer(chosen)
        assets[slot, ids] = nav / len(ids)
        for c in chosen:
            selections.append({'date': date, 'country': c, 'sleeve': slot, 'new_allocation': nav/len(ids),
                               'eligible_count': int(eligible.sum())})
        r = returns.loc[date, columns].to_numpy(dtype=float)
        held = assets.sum(axis=0) > 0
        if not np.isfinite(r[held]).all() or (r[held] < -1).any():
            raise ValueError(f'Missing/invalid held return at {date}: {list(columns[held & (~np.isfinite(r) | (r < -1))])}')
        pnl = assets * np.where(held, r, 0)[None, :]
        assets += pnl
        after = float(assets.sum()+cash.sum())
        if before <= 0:
            raise ValueError('Portfolio capital exhausted')
        for k, c in enumerate(columns):
            contributions.append({'date':date, 'country':c, 'pnl':float(pnl[:,k].sum())})
        history.append({'date':date, 'nav':after, 'return':after/before-1,
                        'cash_weight_start':float(cash.sum()/before),
                        'eligible_count':int(eligible.sum()), 'new_selection_count':len(chosen)})
    h, c, s = pd.DataFrame(history).set_index('date'), pd.DataFrame(contributions), pd.DataFrame(selections)
    if not np.isclose(c.pnl.sum(), h.nav.iloc[-1]-1, atol=1e-10):
        raise AssertionError('Contribution reconciliation failed')
    return h, c, s


def metrics(strategy, benchmark):
    if not strategy.index.equals(benchmark.index):
        raise ValueError('Metric sample mismatch')
    a = np.r_[1., strategy.nav.to_numpy()]
    b = np.r_[1., benchmark.nav.to_numpy()]
    months = len(strategy)
    # Initial NAV=1 is part of drawdown history.
    out = {'months':months, 'cumulative_return':float(a[-1]-1),
           'benchmark_cumulative_return':float(b[-1]-1),
           'annualized_return':float(a[-1]**(12/months)-1),
           'benchmark_annualized_return':float(b[-1]**(12/months)-1),
           'max_drawdown':float(np.min(a/np.maximum.accumulate(a)-1)),
           'benchmark_max_drawdown':float(np.min(b/np.maximum.accumulate(b)-1)),
           'monthly_outperformance_rate':float((strategy['return']>benchmark['return']).mean()),
           'cumulative_wealth_difference':float(a[-1]-b[-1])}
    out['annualized_return_difference'] = out['annualized_return']-out['benchmark_annualized_return']
    out['rolling_12m_outperformance_rate'] = float(np.mean(a[12:]/a[:-12] > b[12:]/b[:-12])) if months>=12 else None
    return out


def run_demo(prepared, output):
    output.mkdir(parents=True, exist_ok=True)
    panel = pd.read_parquet(prepared/'features.parquet')
    returns = pd.read_parquet(prepared/'returns.parquet')
    fields = {k:panel.pivot(index='date',columns='country',values=k).reindex(columns=returns.columns)
              for k in ['cheap_pb','momentum_12_1','scored_eligible','market_eligible']}
    mask = fields['scored_eligible'].astype(bool)
    cheap = fields['cheap_pb'].where(mask).rank(axis=1,pct=True)
    momentum = fields['momentum_12_1'].where(mask).rank(axis=1,pct=True)
    scores = (cheap+momentum)/2
    # Start rule uses only input coverage. Never choose the start by profitability.
    first = mask.index[mask.sum(axis=1)>=10].min()
    dates = pd.date_range(first, returns.index.max(), freq='MS')
    scores, universe = scores.loc[dates], mask.loc[dates]
    if (universe.sum(axis=1)<10).any():
        raise ValueError('Coverage fell below fixed operational minimum')
    broad = fields['market_eligible'].loc[dates].astype(bool)
    summary = {}
    combined = {}
    for hold in [1,12]:
        s, contribution, selected = simulate(scores,universe,returns,hold,True)
        b, bc, _ = simulate(scores,universe,returns,hold,False)
        # All eligible price histories, including names without available valuation.
        zero = pd.DataFrame(0., index=dates, columns=scores.columns)
        all_b, _, _ = simulate(zero,broad,returns,hold,False)
        summary[str(hold)] = {'matched_universe':metrics(s,b), 'broad_universe':metrics(s,all_b),
                             'minimum_scored_markets':int(universe.sum(axis=1).min()),
                             'maximum_scored_markets':int(universe.sum(axis=1).max())}
        curves=pd.DataFrame({'selection':s.nav,'matched_equal_weight':b.nav,'broad_equal_weight':all_b.nav})
        curves.to_csv(output/f'curves_{hold}m.csv')
        selected.to_csv(output/f'selections_{hold}m.csv',index=False)
        contrib=contribution.merge(bc,on=['date','country'],suffixes=('_selection','_benchmark'))
        contrib['active_pnl']=contrib.pnl_selection-contrib.pnl_benchmark
        contrib.to_csv(output/f'contributions_{hold}m.csv',index=False)
        grouped=contrib.groupby('country').active_pnl.sum().sort_values(ascending=False)
        grouped.to_csv(output/f'country_active_pnl_{hold}m.csv')
        summary[str(hold)]['positive_contributing_markets']=int((grouped>0).sum())
        summary[str(hold)]['active_contribution_reconciles']=bool(np.isclose(grouped.sum(),s.nav.iloc[-1]-b.nav.iloc[-1]))
        if hold==12 and len(s)>12:
            # Exclude the 11 partial-investment months, retaining first fully invested month.
            ss=s.iloc[11:].copy();bb=b.iloc[11:].copy()
            ss['nav']/=s.nav.iloc[10];bb['nav']/=b.nav.iloc[10]
            summary[str(hold)]['fully_invested_period']=metrics(ss,bb)
        combined[hold]=curves
    result={'status':'EVALUATOR_BASELINE_DEMONSTRATION_NOT_MACROSTATE_RESULT',
            'start':str(dates.min().date()), 'end':str(dates.max().date()),
            'execution':'monthly index-return proxy, not executable fills',
            'rules':'fixed half value rank / half momentum rank; no model fitted or parameters searched',
            'statistical_significance_gate':False,'portfolios':summary}
    (output/'baseline_demonstration.json').write_text(json.dumps(result,indent=2))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes=plt.subplots(2,1,figsize=(11,8),layout='constrained')
    for ax, (hold, curves) in zip(axes, combined.items()):
        curves.plot(ax=ax,logy=True)
        ax.set_title(f'Fixed value + momentum baseline check | {hold}-month holdings')
        ax.set_ylabel('Wealth from $1 (log scale)');ax.set_xlabel('');ax.grid(alpha=.2)
    fig.suptitle('Evaluator validation — not a MacroState forecast result\nGross monthly index-return proxy; matched and broader equal-weight benchmarks')
    fig.savefig(output/'baseline_demonstration.png',dpi=150);plt.close(fig)
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--prepared',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();print(json.dumps(run_demo(a.prepared,a.output),indent=2))
