"""Post-result missingness-only diagnostic. No macro values used as regressors."""
from pathlib import Path
import argparse,hashlib,json,sys
import numpy as np
import pandas as pd
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'stage3'))
import run as linear
HERE=Path(__file__).resolve().parent


def raw_design(frame):
    return np.column_stack([frame[linear.CONTROLS].to_numpy(float),
                            (~np.isfinite(frame[linear.MACRO].to_numpy(float))).astype(float)])


def fit(train):
    w=linear.row_weights(train);x=raw_design(train)
    mean,std=linear.weighted_scaler(x,w);x=(x-mean)/std
    y=train.relative_target.to_numpy(float);intercept=w@y
    beta=np.linalg.solve(x.T@(w[:,None]*x)+np.eye(x.shape[1]),x.T@(w*(y-intercept)))
    return mean,std,beta,intercept


def predict(frame,model):
    mean,std,beta,intercept=model
    return ((raw_design(frame)-mean)/std)@beta+intercept


def run(prepared,out):
    out.mkdir(parents=True,exist_ok=True)
    reg=json.loads((HERE/'registration.json').read_text());assert hashlib.sha256((HERE/'protocol.json').read_bytes()).hexdigest()==reg['protocol_sha256']
    p,r=linear.load_panel(prepared);saved=pd.read_csv(HERE.parent/'stage3/results/predictions.csv',parse_dates=['date'])
    fits=pd.read_csv(HERE.parent/'stage3/results/fit_log.csv',parse_dates=['fit_date']);fit_dates=set(fits.fit_date)
    predictions=[];model=None
    for date,g in p.groupby('date',sort=True):
        if date not in set(saved.date):continue
        if date in fit_dates:model=fit(linear.training_for(p,date))
        g=g[g.eligible];o=g[['date','country','macro_identity']].copy();o['market_masks']=predict(g,model)
        o['value_momentum']=(g.cheap_pb.rank(pct=True).to_numpy()+g.momentum_12_1.rank(pct=True).to_numpy())/2;predictions.append(o)
    pred=pd.concat(predictions,ignore_index=True)
    assert list(zip(pred.date,pred.country))==list(zip(saved.date,saved.country))
    pred.to_csv(out/'predictions.csv',index=False)
    first=linear.training_for(p,fits.fit_date.min());probe=first.copy()
    for f in linear.MACRO:probe.loc[probe[f].notna(),f]=1e12
    np.testing.assert_allclose(raw_design(first),raw_design(probe))
    np.testing.assert_allclose(predict(first,fit(first)),predict(probe,fit(probe)),rtol=0,atol=1e-12)
    scorecard,_=linear.evaluate(pred,p,r,out,arms=['market_masks'])
    (out/'validation.json').write_text(json.dumps({'same_sample':True,'macro_value_perturbation_invariant':True,'experiment_id':reg['experiment_id']},indent=2))
    print(scorecard[['arm','hold_months','annualized_return','benchmark_annualized_return']].to_string(index=False))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--prepared',type=Path,required=True);a.add_argument('--out',type=Path,required=True);x=a.parse_args();run(x.prepared,x.out)
