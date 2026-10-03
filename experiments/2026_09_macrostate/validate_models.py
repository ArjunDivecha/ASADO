"""Repeat the frozen model runs and check dates, artifacts and future-data canaries."""
from pathlib import Path
import argparse, hashlib, json, subprocess, sys
import numpy as np
import pandas as pd

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--prepared',type=Path,required=True);a=ap.parse_args()
    here=Path(__file__).resolve().parent;prepared=a.prepared.resolve()
    checks={};counts=0
    for folder in [here,here/'stage3',here/'stage4']:
        import re
        test=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(folder),'-p','test_*.py','-v'],capture_output=True,text=True)
        (folder/'results').mkdir(exist_ok=True)
        (folder/'results/model_tests.log').write_text(test.stdout+test.stderr)
        if test.returncode:raise RuntimeError(f'Tests failed: {folder}')
        counts+=int(re.search(r'Ran (\d+) tests',test.stderr).group(1))
    # Re-run frozen specifications; compare all saved predictions to the first results.
    for stage,script in [('stage3','run.py'),('stage4','run_nonlinear.py')]:
        path=here/stage/'results/predictions.csv';prior=pd.read_csv(path)
        cmd=[sys.executable,str(here/stage/script),'--prepared',str(prepared),'--out',str(here/stage/'results')]
        p=subprocess.run(cmd,capture_output=True,text=True)
        (here/stage/'results/run.log').write_text(p.stdout+p.stderr)
        if p.returncode:raise RuntimeError(f'Run failed: {stage}')
        current=pd.read_csv(path)
        pd.testing.assert_frame_equal(prior,current,check_exact=False,rtol=1e-11,atol=1e-12)
        checks[stage+'_reproduces_saved_predictions']=True
        f=pd.read_csv(here/stage/'results/fit_log.csv',parse_dates=['fit_date','latest_label_available'])
        checks[stage+'_labels_known_at_fit']=bool((f.latest_label_available<=f.fit_date).all())
        checks[stage+'_minimum_60_training_origins']=bool((f.training_origins>=60).all())
    sys.path.insert(0,str(here/'stage3'));import run as linear
    panel,returns=linear.load_panel(prepared)
    first=pd.Timestamp('2018-07-01');train=linear.training_for(panel,first)
    forecast=panel[panel.date.eq(first)&panel.eligible].copy()
    altered=panel.copy();altered.loc[altered.label_available_at>first,'relative_target']=1e9
    for arm in linear.ARMS:
        old=linear.predict(forecast,linear.fit_one(train,arm),arm)
        new=linear.predict(forecast,linear.fit_one(linear.training_for(altered,first),arm),arm)
        checks[arm+'_real_future_target_canary']=bool(np.allclose(old,new,atol=1e-12))
    p3=pd.read_csv(here/'stage3/results/predictions.csv');p4=pd.read_csv(here/'stage4/results/predictions.csv')
    checks['all_arms_identical_date_country_rows']=p3[['date','country']].equals(p4[['date','country']])
    checks['same_value_momentum_baseline']=bool(np.allclose(p3.value_momentum,p4.value_momentum))
    for hold in [1,12]:
        x=pd.read_csv(here/f'stage3/results/curves_{hold}m.csv');y=pd.read_csv(here/f'stage4/results/curves_{hold}m.csv')
        checks[f'{hold}m_identical_benchmarks']=bool(np.allclose(x[['equal_weight','broad_equal_weight']],y[['equal_weight','broad_equal_weight']]))
    code={str(p.relative_to(here)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [here/'evaluator.py',here/'prepare.py',here/'stage3/run.py',here/'stage4/run_nonlinear.py',Path(__file__)]}
    result={'unit_tests_passed':counts,'checks':checks,'all_passed':all(checks.values()),'code_sha256':code,
            'prepared_inputs':str(prepared),'no_parameter_search':True,'statistical_gate':False}
    (here/'MODEL_VALIDATION.json').write_text(json.dumps(result,indent=2))
    if not result['all_passed']:raise AssertionError('Model validation failed')
    print(json.dumps(result,indent=2))
