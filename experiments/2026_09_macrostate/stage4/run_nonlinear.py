"""Four frozen nonlinear arms. Uses existing sklearn; no search or new data.
Same Stage3 dates, raw preparation, training labels and portfolio accounting.
Outputs isolated stage4 results; no live DB or production model deployment.
"""
from pathlib import Path
import argparse, hashlib, json, sys, warnings
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.neural_network import MLPRegressor
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'stage3'))
import run as linear
HERE=Path(__file__).resolve().parent
P=json.loads((HERE/'protocol.json').read_text());ARMS=P['arms']


def fit_one(train,arm):
    w=linear.row_weights(train)
    means,std=linear.weighted_scaler(train[linear.FEATURES].to_numpy(float),w)
    z,m=linear.transform_raw(train[linear.FEATURES].to_numpy(float),means,std)
    representation='primitives' if arm.endswith('primitives') else 'states'
    x,names=linear.design(z,m,representation)
    center,scale=linear.weighted_scaler(x,w);x=(x-center)/scale
    y=train.relative_target.to_numpy(float);ym=float(w@y);ys=max(float(np.sqrt(w@((y-ym)**2))),1e-8)
    params=dict(P['trees'] if arm.startswith('trees') else P['neural']);params.pop('class')
    if 'hidden_layer_sizes' in params:params['hidden_layer_sizes']=tuple(params['hidden_layer_sizes'])
    model=HistGradientBoostingRegressor(**params) if arm.startswith('trees') else MLPRegressor(**params)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter('always');model.fit(x,(y-ym)/ys,sample_weight=w*len(w))
    return {'model':model,'raw_mean':means,'raw_std':std,'center':center,'scale':scale,'target_mean':ym,'target_std':ys,
            'representation':representation,'warnings':[str(v.message) for v in caught],
            'iterations':int(model.n_iter_),'loss':float(model.loss_) if hasattr(model,'loss_') else None}


def predict(frame,model):
    z,m=linear.transform_raw(frame[linear.FEATURES].to_numpy(float),model['raw_mean'],model['raw_std'])
    x,_=linear.design(z,m,model['representation']);x=(x-model['center'])/model['scale']
    return model['model'].predict(x)*model['target_std']+model['target_mean']


def forecasts(panel,end):
    output=[];fits=[];models=None;last=None
    for date,g in panel.groupby('date',sort=True):
        if date>end:break
        if models is None or date>=last+pd.offsets.MonthBegin(12):
            train=linear.training_for(panel,date)
            if train is None:continue
            models={}
            for arm in ARMS:
                model=fit_one(train,arm);models[arm]=model
                fits.append({'fit_date':date,'arm':arm,'training_first':train.date.min(),'training_last':train.date.max(),
                             'latest_label_available':train.label_available_at.max(),'training_origins':train.date.nunique(),
                             'training_rows':len(train),'iterations':model['iterations'],'loss':model['loss'],
                             'warnings':' | '.join(model['warnings'])})
                print(f'{date.date()} {arm}: {len(train)} rows, {model["iterations"]} iterations',flush=True)
            last=date
        g=g[g.eligible]
        out=g[['date','country','macro_identity']].copy()
        for arm,model in models.items():out[arm]=predict(g,model)
        out['value_momentum']=(g.cheap_pb.rank(pct=True).to_numpy()+g.momentum_12_1.rank(pct=True).to_numpy())/2
        output.append(out)
    return pd.concat(output,ignore_index=True),pd.DataFrame(fits)


def run(prepared,out):
    out.mkdir(parents=True,exist_ok=True)
    registration=json.loads((HERE/'registration.json').read_text())
    assert hashlib.sha256((HERE/'protocol.json').read_bytes()).hexdigest()==registration['protocol_sha256']
    panel,returns=linear.load_panel(prepared);pred,fit=forecasts(panel,returns.index.max())
    prior=pd.read_csv(HERE.parent/'stage3/results/predictions.csv',parse_dates=['date'])
    if list(zip(pred.date,pred.country))!=list(zip(prior.date,prior.country)):
        raise AssertionError('Nonlinear prediction sample differs from Stage3')
    np.testing.assert_allclose(pred.value_momentum,prior.value_momentum)
    pred.to_csv(out/'predictions.csv',index=False);fit.to_csv(out/'fit_log.csv',index=False)
    scorecard,curves=linear.evaluate(pred,panel,returns,out,arms=ARMS)
    result={'experiment_id':registration['experiment_id'],'same_sample_as_stage3':True,
            'forecast_months':pred.date.nunique(),'rows':len(pred),'fits':len(fit),
            'protocol_sha256':registration['protocol_sha256'],'statistical_gate':False,
            'warnings_count':int(fit.warnings.fillna('').ne('').sum())}
    (out/'run_manifest.json').write_text(json.dumps(result,indent=2))
    print(scorecard[['arm','hold_months','annualized_return','benchmark_annualized_return','max_drawdown']].to_string(index=False),flush=True)
    return result

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--prepared',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();run(a.prepared,a.out)
