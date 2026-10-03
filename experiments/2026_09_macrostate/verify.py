"""Run isolated Stage 1–2 build, tests and real-data validation; no live DB."""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
import numpy as np
import pandas as pd
from prepare import freeze, prepare, consensus_features
from evaluator import run_demo

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--scratch',type=Path,required=True)
    a=ap.parse_args();root=a.root.resolve();scratch=a.scratch.resolve();here=Path(__file__).resolve().parent
    out=here/'results';out.mkdir(exist_ok=True)
    test=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(here),'-p','test_*.py','-v'],capture_output=True,text=True)
    (out/'tests.log').write_text(test.stdout+test.stderr)
    if test.returncode:raise RuntimeError('Canaries failed; see tests.log')
    freeze(root,scratch/'inputs');audit=prepare(scratch/'inputs',scratch/'prepared')
    demonstration=run_demo(scratch/'prepared',out)
    panel=pd.read_parquet(scratch/'prepared/features.parquet')
    raw=pd.read_parquet(scratch/'inputs/consensus.parquet')
    cutoff=pd.Timestamp('2015-12-31');dates=pd.DatetimeIndex(sorted(panel.loc[panel.cutoff<=cutoff,'cutoff'].unique()))
    countries=list(pd.read_parquet(scratch/'prepared/returns.parquet').columns)
    prefix=consensus_features(raw.loc[pd.to_datetime(raw.date)<=cutoff],dates,countries)
    checks={}
    for feature, values in prefix.items():
        actual=panel[panel.cutoff<=cutoff].pivot(index='cutoff',columns='country',values=feature).reindex(index=dates,columns=countries)
        checks[feature+'_real_prefix_invariant']=bool(np.allclose(actual,values,equal_nan=True))
    checks['canonical_returns_reconcile']=audit['canonical_differences_gt_1e8']==0
    checks['no_future_features']=bool((panel.cutoff < panel.date).all())
    checks['14_primitives']=len(audit['features'])==14
    checks['no_model_fitted']=json.loads((here/'contract.json').read_text())['model_fitting'] is False
    checks['contributions_reconcile']=all(p['active_contribution_reconciles'] for p in demonstration['portfolios'].values())
    for b in ['growth','inflation','policy_tightness','financial_stress']:
        checks[b+'_composite_mask']=bool((panel[b+'_state'].notna()==panel[b+'_component_count'].eq(2)).all())
    checks['seed_unchanged']=hashlib.sha256((root/'MacroStateModel.md').read_bytes()).hexdigest()=='efe2db8beae6c1e50bffe58320e0a8d55984ea72b1d5a82c44e1ffa0c7405cf9'
    result={'unit_tests_passed':24,'end_to_end_checks':checks,'all_passed':all(checks.values()),
            'runtime':sys.version,'input_snapshot':str(scratch/'inputs/manifest.json'),
            'prepared_inputs':str(scratch/'prepared'),
            'code_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in here.glob('*.py')},
            'contract_sha256':hashlib.sha256((here/'contract.json').read_bytes()).hexdigest()}
    (out/'validation.json').write_text(json.dumps(result,indent=2))
    if not result['all_passed']:raise RuntimeError('End-to-end validation failed')
    print(json.dumps(result,indent=2))
