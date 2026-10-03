"""Frozen MacroState first contest. Input: stage12 frozen prepared panels.
Output: isolated stage3 results. No downloads, production DB or parameter search.
Protocol registered before fitting; no significance/cost gate. Version 1, 2026-09-06.
"""
from pathlib import Path
import argparse, hashlib, json, sys
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from evaluator import simulate, metrics
from prepare import forward_returns

HERE=Path(__file__).resolve().parent
P=json.loads((HERE/'protocol.json').read_text())
GROUPS=P['macro_groups']; CONTROLS=P['market_controls']; ARMS=P['learned_arms']
MACRO=[c.lstrip('-') for group in GROUPS.values() for c in group]
FEATURES=MACRO+CONTROLS


def row_weights(frame):
    identities=frame.groupby('date').macro_identity.transform('nunique')
    token_count=frame.groupby(['date','macro_identity']).country.transform('size')
    w=1/(identities*token_count)
    return w.to_numpy()/w.sum()


def weighted_scaler(x,w):
    observed=np.isfinite(x)
    den=(observed*w[:,None]).sum(axis=0)
    means=np.divide((np.where(observed,x,0)*w[:,None]).sum(axis=0),den,
                    out=np.zeros(x.shape[1]),where=den>0)
    var=np.divide((np.where(observed,(x-means)**2,0)*w[:,None]).sum(axis=0),den,
                  out=np.zeros(x.shape[1]),where=den>0)
    std=np.sqrt(var);std[std<1e-10]=1
    return means,std


def transform_raw(raw,means,std):
    missing=~np.isfinite(raw)
    return np.where(missing,0,(raw-means)/std), missing.astype(float)


def design(standardized,missing,arm):
    nmacro=len(MACRO)
    controls=standardized[:,nmacro:]
    mask=missing[:,:nmacro]
    states=[]
    for group in GROUPS.values():
        states.append(sum(standardized[:,FEATURES.index(c.lstrip('-'))]*(-1 if c.startswith('-') else 1) for c in group)/len(group))
    states=np.column_stack(states)
    if arm=='market_only':return controls,CONTROLS
    if arm.startswith('primitives'):
        x=np.column_stack([standardized,mask]);names=FEATURES+['missing_'+f for f in MACRO]
    else:
        x=np.column_stack([states,controls,mask]);names=list(GROUPS)+CONTROLS+['missing_'+f for f in MACRO]
    if arm.endswith('interactions'):
        terms=np.column_stack([np.maximum(controls[:,0],0)*np.maximum(states[:,0],0),
                               np.maximum(-states[:,0],0)*np.maximum(states[:,2],0)])
        x=np.column_stack([x,terms]);names+=['cheap_x_growth','weak_growth_x_tight_policy']
    return x,names


def fit_one(train,arm):
    w=row_weights(train)
    raw=train[FEATURES].to_numpy(dtype=float)
    means,std=weighted_scaler(raw,w)
    z,m=transform_raw(raw,means,std)
    x,names=design(z,m,arm)
    center,scale=weighted_scaler(x,w)
    x=(x-center)/scale
    y=train.relative_target.to_numpy(dtype=float)
    ymean=float(w@y)
    beta=np.linalg.solve(x.T@(w[:,None]*x)+P['ridge_penalty']*np.eye(x.shape[1]), x.T@(w*(y-ymean)))
    return {'raw_mean':means,'raw_std':std,'center':center,'scale':scale,'beta':beta,'intercept':ymean,'names':names}


def predict(frame,model,arm):
    z,m=transform_raw(frame[FEATURES].to_numpy(dtype=float),model['raw_mean'],model['raw_std'])
    x,_=design(z,m,arm)
    return ((x-model['center'])/model['scale'])@model['beta']+model['intercept']


def load_panel(prepared):
    panel=pd.read_parquet(prepared/'features.parquet').sort_values(['date','country'])
    if panel.duplicated(['date','country']).any():raise ValueError('Duplicate feature rows')
    returns=pd.read_parquet(prepared/'returns.parquet')
    # Eligibility is fixed using inputs, before attaching any outcomes.
    core=['gdp_expectation_z','gdp_revision_3m_z','cpi_expectation_z','cpi_revision_3m_z']+CONTROLS
    panel['eligible']=panel.scored_eligible & np.isfinite(panel[core]).all(axis=1)
    counts=panel.groupby('date').eligible.sum()
    first=counts[counts>=20].index.min()
    panel=panel[panel.date>=first].copy()
    if (panel.groupby('date').eligible.sum()<20).any():raise ValueError('Common coverage falls below frozen floor')
    targets=forward_returns(returns,12).rename_axis('date').stack().rename('target').reset_index()
    targets.columns=['date','country','target']
    panel=panel.merge(targets,on=['date','country'],how='left',validate='one_to_one')
    # Missing mature outcomes must not silently change a date's relative target benchmark.
    panel['label_available_at']=panel.date+pd.offsets.MonthBegin(12)
    last_available=returns.index.max()+pd.offsets.MonthBegin(1)
    mature=panel.eligible & (panel.label_available_at<=last_available)
    if panel.loc[mature,'target'].isna().any():raise ValueError('Missing mature eligible target')
    panel['relative_target']=panel.target-panel.target.where(panel.eligible).groupby(panel.date).transform('mean')
    return panel,returns


def training_for(panel,fit_date):
    train=panel[panel.eligible & (panel.label_available_at<=fit_date)].copy()
    if train.relative_target.isna().any():raise ValueError('Missing mature training target')
    if train.date.nunique()<P['initial_training_origins']:return None
    return train


def walk_forward(panel,end):
    predictions=[];fits=[];coefficients=[];models=None;last_fit=None
    for date,g in panel.groupby('date',sort=True):
        if date>end:break
        if models is None or date>=last_fit+pd.offsets.MonthBegin(12):
            train=training_for(panel,date)
            if train is None:continue
            models={arm:fit_one(train,arm) for arm in ARMS};last_fit=date
            fits.append({'fit_date':date,'training_first':train.date.min(),'training_last':train.date.max(),
                         'latest_label_available':train.label_available_at.max(),
                         'training_origins':train.date.nunique(),'training_rows':len(train)})
            for arm,model in models.items():
                coefficients.extend({'fit_date':date,'arm':arm,'feature':name,'coefficient':float(coef)}
                                    for name,coef in zip(model['names'],model['beta']))
        eligible=g[g.eligible]
        out=eligible[['date','country','macro_identity']].copy()
        for arm,model in models.items():out[arm]=predict(eligible,model,arm)
        # Identical eligible set for the fixed baseline, not its previous 2006-wide run.
        out['value_momentum']=(eligible.cheap_pb.rank(pct=True).to_numpy()+eligible.momentum_12_1.rank(pct=True).to_numpy())/2
        predictions.append(out)
    if not predictions:raise ValueError('No eligible out-of-sample months')
    return pd.concat(predictions,ignore_index=True),pd.DataFrame(fits),pd.DataFrame(coefficients)


def calendar_returns(history):
    result={}
    for year,g in history.groupby(history.index.year):
        result[str(year)]={'return':float(np.prod(1+g['return'])-1),'months':len(g)}
    return result


def evaluate(predictions,panel,returns,out,arms=None):
    arms = ARMS if arms is None else arms
    dates=pd.DatetimeIndex(sorted(predictions.date.unique()))
    columns=returns.columns
    wide={arm:predictions.pivot(index='date',columns='country',values=arm).reindex(index=dates,columns=columns)
          for arm in arms+['value_momentum']}
    universe=wide[arms[0]].notna()
    broad=panel.pivot(index='date',columns='country',values='market_eligible').reindex(index=dates,columns=columns).astype(bool)
    zeros=pd.DataFrame(0.,index=dates,columns=columns)
    results=[];years=[];breadth=[];curves={}
    for hold in [1,12]:
        benchmark,bc,_=simulate(zeros,universe,returns,hold,False)
        broad_b,_,_=simulate(zeros,broad,returns,hold,False)
        curves[hold]=pd.DataFrame({'equal_weight':benchmark.nav,'broad_equal_weight':broad_b.nav})
        histories={'equal_weight':benchmark,'broad_equal_weight':broad_b}
        for arm,score in wide.items():
            h,c,s=simulate(score,universe,returns,hold,True);histories[arm]=h
            stat=metrics(h,benchmark);stat.update({'arm':arm,'hold_months':hold,
                'broad_equal_weight_cagr':metrics(h,broad_b)['benchmark_annualized_return']})
            curves[hold][arm]=h.nav
            s.to_csv(out/f'selections_{arm}_{hold}m.csv',index=False)
            merged=c.merge(bc,on=['date','country'],suffixes=('_strategy','_benchmark'))
            merged['active_pnl']=merged.pnl_strategy-merged.pnl_benchmark
            contribution=merged.groupby('country').active_pnl.sum().sort_values(ascending=False)
            if not np.isclose(contribution.sum(),h.nav.iloc[-1]-benchmark.nav.iloc[-1]):raise AssertionError('Active P&L reconciliation')
            contribution.to_csv(out/f'contribution_{arm}_{hold}m.csv')
            identity=contribution.groupby(lambda x:'US' if x in ['U.S.','NASDAQ','US SmallCap'] else 'China' if x in ['ChinaA','ChinaH'] else x).sum().sort_values(ascending=False)
            identity.to_csv(out/f'identity_contribution_{arm}_{hold}m.csv')
            positive=contribution[contribution>0]
            stat['positive_contribution_markets']=int((contribution>0).sum())
            stat['top3_share_of_positive_contributions']=float(positive.head(3).sum()/positive.sum()) if positive.sum()>0 else None
            stat['largest_contributor']=str(contribution.index[0])
            stat['active_pnl_excluding_largest_identity']=float(identity.sum()-identity.iloc[0])
            if hold==12:
                hh=h.iloc[11:].copy();bb=benchmark.iloc[11:].copy()
                hh['nav']/=h.nav.iloc[10];bb['nav']/=benchmark.nav.iloc[10]
                full=metrics(hh,bb);stat['fully_invested_cagr']=full['annualized_return'];stat['fully_invested_benchmark_cagr']=full['benchmark_annualized_return']
            results.append(stat)
        for name,h in histories.items():
            for year,detail in calendar_returns(h).items():years.append({'hold_months':hold,'arm':name,'year':year,**detail})
        curves[hold].to_csv(out/f'curves_{hold}m.csv')
    summary=pd.DataFrame(results);summary.to_csv(out/'scorecard.csv',index=False)
    pd.DataFrame(years).to_csv(out/'calendar_returns.csv',index=False)
    return summary,curves


def run(prepared,out):
    out.mkdir(parents=True,exist_ok=True)
    registration=json.loads((HERE/'registration.json').read_text())
    if hashlib.sha256((HERE/'protocol.json').read_bytes()).hexdigest()!=registration['protocol_sha256']:
        raise ValueError('Protocol changed after registration')
    panel,returns=load_panel(prepared)
    predictions,fits,coefficients=walk_forward(panel,returns.index.max())
    predictions.to_csv(out/'predictions.csv',index=False);fits.to_csv(out/'fit_log.csv',index=False);coefficients.to_csv(out/'coefficients.csv',index=False)
    scorecard,curves=evaluate(predictions,panel,returns,out)
    counts=predictions.groupby('date').country.nunique()
    result={'experiment_id':registration['experiment_id'],'first_forecast':str(predictions.date.min().date()),
            'last_forecast':str(predictions.date.max().date()),'forecast_months':predictions.date.nunique(),
            'minimum_markets':int(counts.min()),'maximum_markets':int(counts.max()),
            'fits':len(fits),'statistical_gate':False,'rows':len(predictions),
            'source_status':'conditional vendor-history reconstruction; monthly index-return proxy',
            'protocol_sha256':registration['protocol_sha256'],
            'input_hashes':{f:hashlib.sha256((prepared/f).read_bytes()).hexdigest() for f in ['features.parquet','returns.parquet']}}
    (out/'run_manifest.json').write_text(json.dumps(result,indent=2))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    colors={'equal_weight':'black','broad_equal_weight':'gray','value_momentum':'#b07520','market_only':'#839192','primitives':'#3663b0','states':'#13856b','states_interactions':'#8e44ad','primitives_interactions':'#cc5861'}
    fig,axes=plt.subplots(2,1,figsize=(12,9),layout='constrained')
    for ax,hold in zip(axes,[1,12]):
        for arm in ['equal_weight','value_momentum']+ARMS:
            ax.plot(curves[hold].index,curves[hold][arm],label=arm.replace('_',' '),color=colors[arm],linewidth=2 if arm=='equal_weight' else 1.4)
        ax.set_title(f'{hold}-month holdings');ax.set_ylabel('Wealth from $1');ax.grid(alpha=.2);ax.legend(ncol=3,fontsize=8)
    fig.suptitle('MacroState first contest: top 20% versus equal weight\nGross USD index returns; identical dates and eligible markets')
    fig.savefig(out/'comparison.png',dpi=160);plt.close(fig)
    print(json.dumps(result,indent=2));print(scorecard[['arm','hold_months','annualized_return','benchmark_annualized_return','max_drawdown']].to_string(index=False))
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--prepared',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();run(a.prepared,a.out)
