"""Isolated monthly worker/transaction/transport-scope regressions.

All mutable files are temporary fixtures. No live DB/provider/model/notification
calls. Production code paths are exercised with injected stage failures/results.
"""
import calendar
from datetime import datetime
import fcntl
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
import monthly_publish as P
import monthly_worker as W
import monthly_collect as C
import monthly_stage as S
import monthly_nn as NN
from monthly_readiness import atomic,read,sha,freshness


class Transaction(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.dest=self.root/'canonical';self.dest.mkdir();self.stage=self.root/'stage';self.stage.mkdir()
  self.a=self.dest/'a';self.a.write_bytes(b'old-a');self.b=self.dest/'b'
  self.sa=self.stage/'a';self.sa.write_bytes(b'new-a');self.sb=self.stage/'b';self.sb.write_bytes(b'new-b')
  self.originals=P.backup([self.a,self.b],self.root/'backup',[self.dest])
  self.plan=[dict(source=str(s),destination=str(d),sha256=sha(s)) for s,d in [(self.sa,self.a),(self.sb,self.b)]]
  self.journal=self.root/'publication.jsonl'
 def test_success(self):
  P.publish(self.plan,self.originals,self.journal,[self.dest]);self.assertEqual(self.a.read_bytes(),b'new-a');self.assertEqual(self.b.read_bytes(),b'new-b')
 def test_failure_before_first_replacement_no_change(self):
  def fail(when,i):
   if when=='before_replace':raise RuntimeError('stop')
  with self.assertRaises(RuntimeError):P.publish(self.plan,self.originals,self.journal,[self.dest],fail)
  self.assertEqual(self.a.read_bytes(),b'old-a');self.assertFalse(self.b.exists())
 def test_failure_mid_publication_rolls_everything_back(self):
  def fail(when,i):
   if when=='after_replace' and i==1:raise RuntimeError('stop')
  with self.assertRaises(RuntimeError):P.publish(self.plan,self.originals,self.journal,[self.dest],fail)
  self.assertEqual(self.a.read_bytes(),b'old-a');self.assertFalse(self.b.exists())
 def test_interrupted_after_rename_before_receipt_inferred_from_hash(self):
  row=dict(event='PREPARED',**self.plan[0],**{k:self.originals[str(self.a)][k] for k in ('existed','before_sha256','backup')})
  self.journal.write_text(json.dumps(row)+'\n');self.a.write_bytes(b'new-a')
  P.rollback(self.journal,[self.dest]);self.assertEqual(self.a.read_bytes(),b'old-a')
 def test_rollback_never_overwrites_later_writer(self):
  P.publish(self.plan,self.originals,self.journal,[self.dest]);self.a.write_bytes(b'someone-else')
  with self.assertRaisesRegex(RuntimeError,'later writer'):P.rollback(self.journal,[self.dest])
  self.assertEqual(self.a.read_bytes(),b'someone-else');self.assertEqual(self.b.read_bytes(),b'new-b')
 def test_changed_stage_fails_before_any_publication(self):
  self.sb.write_bytes(b'wrong')
  with self.assertRaises(RuntimeError):P.publish(self.plan,self.originals,self.journal,[self.dest])
  self.assertEqual(self.a.read_bytes(),b'old-a')
 def test_changed_canonical_stops_before_write(self):
  self.a.write_bytes(b'later')
  with self.assertRaises(RuntimeError):P.publish(self.plan,self.originals,self.journal,[self.dest])
  self.assertEqual(self.a.read_bytes(),b'later')
 def test_no_duplicate_target(self):
  with self.assertRaises(RuntimeError):P.publish(self.plan+[self.plan[0]],self.originals,self.journal,[self.dest])
 def test_outside_target_and_symlink_refused(self):
  bad=self.root/'outside'
  with self.assertRaises(RuntimeError):P.allowed(bad,[self.dest])
  link=self.dest/'link';link.symlink_to(self.a)
  with self.assertRaises(RuntimeError):P.allowed(link,[self.dest])


class Worker(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)/'ASADO';self.root.mkdir()
  self.nn=self.root.parent/'NN';(self.nn/'production').mkdir(parents=True)
  (self.root/'Data').mkdir();(self.root/'Data/asado.duckdb').write_bytes(b'original-data')
  self.cfg=dict(nn_root=str(self.nn),bbg_root=str(self.root.parent/'BBG'),first_trade_month='2026-11',max_runtime_seconds=7200,data_targets=['Data/asado.duckdb'])
  self.clock=datetime.fromisoformat('2026-11-01T00:05:00-07:00');self.calls=[]
  self.notify=patch.object(W,'alert_event');self.notify.start();self.addCleanup(self.notify.stop)
 def execute(self,c,cfg,stage,*_):
  self.calls.append(stage)
  if stage=='nn':
   run=Path(c['run']);src=run/'new-data';src.write_bytes(b'new-data')
   rec=run/'new-receipt';atomic(rec,dict(NN_scores_match_sandbox=True))
   plan=[dict(source=str(src),destination=str(self.root/'Data/asado.duckdb'),sha256=sha(src)),dict(source=str(rec),destination=str(Path(c['nn_run_destination'])/'monthly_acceptance.json'),sha256=sha(rec))]
   atomic(run/'publication_plan.json',plan)
 def final(self,c,cfg):
  atomic(self.root/f"Data/monthly/accepted/{c['month']}.json",dict(month=c['month']))
 def run(self,*a,**kw):
  # unittest's own run method must remain callable.
  return super().run(*a,**kw)
 def tick(self,**kw):return W.run_once(self.root,self.cfg,clock=self.clock,executor=self.execute,before=lambda *_:None,final=self.final,**kw)
 def test_success_and_duplicate_no_publication_again(self):
  self.assertEqual(self.tick(),'ACCEPTED');self.assertEqual(self.calls,['collect','stage','nn']);before=(self.root/'Data/asado.duckdb').stat().st_mtime_ns
  self.assertEqual(self.tick(),'ACCEPTED_NOOP');self.assertEqual(len(self.calls),3);self.assertEqual((self.root/'Data/asado.duckdb').stat().st_mtime_ns,before)
 def test_accepted_october_no_provider_or_backup(self):
  self.clock=datetime.fromisoformat('2026-10-14T00:35:00-07:00')
  self.assertEqual(self.tick(),'ACCEPTED_NOOP');self.assertFalse(self.calls);self.assertFalse((self.root/'Data/monthly/attempts').exists())
 def test_phase_failure_stops_forever_no_hourly_repeat(self):
  def fail(c,cfg,stage,*_):self.calls.append(stage);raise RuntimeError('provider failed')
  result=W.run_once(self.root,self.cfg,clock=self.clock,executor=fail,before=lambda *_:None,final=self.final)
  self.assertEqual(result,'FAILED_STOPPED');self.assertEqual(self.tick(),'STOPPED_NO_RETRY');self.assertEqual(self.calls,['collect']);self.assertEqual((self.root/'Data/asado.duckdb').read_bytes(),b'original-data')
 def test_quota_exhaustion_consumes_attempt_without_collection(self):
  def stop(*_):raise W.StopAttempt('quota exhausted')
  self.assertEqual(W.run_once(self.root,self.cfg,clock=self.clock,executor=self.execute,before=stop,final=self.final),'FAILED_STOPPED')
  self.assertEqual(self.tick(),'STOPPED_NO_RETRY');self.assertFalse(self.calls)
 def test_missing_interpreter_stops_before_database_or_collection(self):
  cfg=dict(self.cfg,enabled=True,pinned_sources={},asado_python=str(self.root/'missing-python'))
  with self.assertRaisesRegex(W.StopAttempt,'interpreter unavailable'):
   W.preflight(dict(root=str(self.root),nn_root=str(self.nn),month='2026-11'),cfg)
 def test_missing_raw_cache_stops_before_database_or_collection(self):
  cfg=dict(self.cfg,enabled=True,pinned_sources={},factor_set_sha256='fixture',required_inputs=['Data/raw/bloomberg/missing.parquet'],**{k:sys.executable for k in ('asado_python','bbg_python','nn_python')})
  atomic(self.root/'Data/monthly/accepted/2026-10.json',{'fixture':True})
  atomic(self.nn/'production/state/holdings.json',{'months':{'2026-10':{'source':'live'}}})
  with patch('monthly_readiness.consumer',return_value={'passed':True}):
   with self.assertRaisesRegex(W.StopAttempt,'Required source input absent'):
    W.preflight(dict(root=str(self.root),nn_root=str(self.nn),month='2026-11'),cfg)
 def test_failure_after_publication_before_acceptance_rolls_back(self):
  def fail(*_):raise RuntimeError('final parity failed')
  self.assertEqual(W.run_once(self.root,self.cfg,clock=self.clock,executor=self.execute,before=lambda *_:None,final=fail),'FAILED_STOPPED')
  self.assertEqual((self.root/'Data/asado.duckdb').read_bytes(),b'original-data');self.assertEqual(self.tick(),'STOPPED_NO_RETRY')
 def test_competing_worker_lock_prevents_claim(self):
  lock=self.root/'Data/monthly/.worker.lock';lock.parent.mkdir(parents=True);h=lock.open('a');self.addCleanup(h.close);fcntl.flock(h,fcntl.LOCK_EX|fcntl.LOCK_NB)
  self.assertEqual(self.tick(),'DEFERRED_OTHER_WORKER');self.assertFalse(self.calls);self.assertFalse((lock.parent/'attempts/2026-11.json').exists())
 def test_interrupted_claim_never_repeats_collection(self):
  atomic(self.root/'Data/monthly/attempts/2026-11.json',dict(state='RUNNING',month='2026-11',run=str(self.root/'lost-run')))
  self.assertEqual(self.tick(),'STOPPED_NO_RETRY');self.assertFalse(self.calls);self.assertEqual(read(self.root/'Data/monthly/attempts/2026-11.json')['state'],'FAILED_STOPPED')
 def test_interrupted_publication_rolls_back_and_does_not_collect(self):
  oldrun=self.root/'Data/monthly/runs/interrupted';oldrun.mkdir(parents=True)
  original=self.root/'Data/asado.duckdb';backup=oldrun/'original';backup.write_bytes(original.read_bytes());new=oldrun/'new';new.write_bytes(b'partially-published')
  row=dict(event='PREPARED',source=str(new),destination=str(original),sha256=sha(new),existed=True,before_sha256=sha(backup),backup=str(backup))
  (oldrun/'publication.jsonl').write_text(json.dumps(row)+'\n');original.write_bytes(new.read_bytes())
  atomic(self.root/'Data/monthly/attempts/2026-11.json',dict(state='PUBLISHING',month='2026-11',run=str(oldrun)))
  self.assertEqual(self.tick(),'STOPPED_NO_RETRY');self.assertEqual(original.read_bytes(),b'original-data');self.assertFalse(self.calls)
 def test_concurrent_start_in_another_process_cannot_claim(self):
  import subprocess,time
  marker=self.root/'held'
  code="import fcntl,time;from pathlib import Path; p=Path(__import__('sys').argv[1]);p.parent.mkdir(parents=True,exist_ok=True); h=p.open('a');fcntl.flock(h,fcntl.LOCK_EX);Path(__import__('sys').argv[2]).touch();time.sleep(2)"
  p=subprocess.Popen([sys.executable,'-c',code,str(self.root/'Data/monthly/.worker.lock'),str(marker)])
  try:
   for _ in range(100):
    if marker.exists():break
    time.sleep(.01)
   self.assertTrue(marker.exists());self.assertEqual(self.tick(),'DEFERRED_OTHER_WORKER');self.assertFalse(self.calls)
  finally:p.wait(timeout=5)
 def test_quiet_window_defers_before_claim(self):
  self.clock=datetime.fromisoformat('2026-11-01T06:30:00-08:00');self.assertEqual(self.tick(),'DEFERRED_QUIET_WINDOW');self.assertFalse(self.calls)
 def test_new_month_has_independent_single_claim(self):
  self.assertEqual(self.tick(),'ACCEPTED');self.clock=datetime.fromisoformat('2026-12-01T00:10:00-08:00');self.assertEqual(self.tick(),'ACCEPTED');self.assertEqual(len(self.calls),6)


class Elem:
 def __init__(self,d):self.d=d
 def getElement(self,k):return Values(self.d[k])
 def getElementAsString(self,k):return self.d[k]
class Values:
 def __init__(self,d):self.d=d
 def numValues(self):return len(self.d)
 def getValueAsString(self,i):return self.d[i]
class Req:
 def __init__(self,**d):self.d=d
 def asElement(self):return Elem(self.d)
class Ledger:
 @staticmethod
 def _extract_request_type(r):return r.d['type']
 @staticmethod
 def _extract_securities(r):return r.d['securities']


class Scope(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.journal=Path(self.tmp.name)/'wire.jsonl'
  self.plan=[dict(id='1',securities=['X'],fields=['PX_LAST'],start='20260901',end='20261031',periodicity='MONTHLY',currency='USD')]
  self.guard=C.RequestGuard(self.plan,3,self.journal,None,Ledger)
 def req(self,**kw):return Req(type='HistoricalDataRequest',securities=['X'],fields=['PX_LAST'],startDate='20260901',endDate='20261031',periodicitySelection='MONTHLY',currency=kw.get('currency','USD'))
 def test_exact_request_accepted_once(self):
  self.guard.check(self.req());self.assertEqual(self.guard.sent,{'1'})
  with self.assertRaises(C.ScopeStop):self.guard.check(self.req())
 def test_currency_change_refused(self):
  with self.assertRaises(C.ScopeStop):self.guard.check(self.req(currency='EUR'))
 def test_date_or_security_expansion_refused(self):
  r=self.req();r.d['startDate']='19990101'
  with self.assertRaises(C.ScopeStop):self.guard.check(r)
 def test_probe_limit(self):
  r=Req(type='ReferenceDataRequest',securities=['AAPL US Equity'],fields=['PX_LAST','NAME'])
  self.guard.check(r)
  with self.assertRaises(C.ScopeStop):self.guard.check(r)
 def test_infrastructure_changes_blocked_before_command(self):
  calls=[];run=C.forbid_infrastructure_changes(lambda a,**kw:calls.append(a))
  with self.assertRaises(C.ScopeStop):run(['prlctl','start','Windows 11'])
  with self.assertRaises(C.ScopeStop):run(['prlctl','exec','Windows 11','netsh','advfirewall','set','allprofiles','state','off'])
  self.assertFalse(calls);run(['prlctl','list','-a']);self.assertEqual(len(calls),1)
 def test_real_static_scope_and_completed_month_dates(self):
  root=SCRIPTS.parent;cfg=read(root/'config/monthly_worker.json');plan=C.requests_for(dict(root=str(root),observation_month='2026-10'),cfg)
  self.assertEqual(sum(len(r['securities'])*len(r['fields']) for r in plan),1363)
  self.assertTrue(all(r['start']=='20260901' and r['end']=='20261031' and r['periodicity']=='MONTHLY' for r in plan))
 def test_recovery_alias_cannot_receive_second_allowance(self):
  class Budget:
   month_key=staticmethod(lambda:'2026-10')
   load_usage=staticmethod(lambda key:{'free':{'ASADO':64,'recovery_collect.py':45}})
   _touched=staticmethod(lambda key:set())
   recurring_set=staticmethod(lambda key:set())
   load_config=staticmethod(lambda:{'free_new_per_caller_month':150})
  cfg={'quota_associations':[{'month':'2026-10','caller':'recovery_collect.py'}]}
  C.associated_budget(Budget,[str(i) for i in range(41)],cfg)
  with self.assertRaises(C.ScopeStop):C.associated_budget(Budget,[str(i) for i in range(42)],cfg)


class Preservation(unittest.TestCase):
 def frame(self,vals):return pd.DataFrame(vals,columns=['date','country','value','variable'])
 def test_historical_inputs_preserved_return_null_only_realized(self):
  old=self.frame([['2026-09-01','A',1.,'Feature'],['2026-09-01','A',None,'1MRet']])
  new=self.frame([['2026-09-01','A',999.,'Feature'],['2026-09-01','A',.1,'1MRet'],['2026-10-01','A',2.,'Feature']])
  out=S.merge_tidy(old,new,'2026-10-01',allow_returns=True)
  self.assertEqual(out.loc[(out.date==pd.Timestamp('2026-09-01'))&(out.variable=='Feature'),'value'].iloc[0],1)
  self.assertEqual(out.loc[out.variable=='1MRet','value'].iloc[0],.1)
 def test_conflicting_current_input_stops(self):
  old=self.frame([['2026-10-01','A',1.,'Feature']]);new=self.frame([['2026-10-01','A',2.,'Feature']])
  with self.assertRaises(RuntimeError):S.merge_tidy(old,new,'2026-10-01')
 def test_missing_source_still_blocks(self):
  fs=[dict(source='bloomberg',variable='B',lag_months=1)]
  fr=freshness([('bloomberg','B','2026-08',['A']),('t2','1MRet','2026-09',['A'])],fs,['A'],'2026-10');self.assertFalse(fr['passed'])
 def test_future_input_cannot_replace_required_label(self):
  fs=[dict(source='bloomberg',variable='B',lag_months=1)]
  fr=freshness([('bloomberg','B','2026-10',['A']),('t2','1MRet','2026-09',['A'])],fs,['A'],'2026-10');self.assertFalse(fr['passed'])
 def test_changed_nn_scores_fail_parity(self):
  a=pd.DataFrame(dict(date=[pd.Timestamp('2026-11-01')]*34,country=[str(i) for i in range(34)],ticker=[str(i) for i in range(34)],rank=range(1,35),held_prev=[False]*34,weight=[.125]*8+[0]*26,action=['HOLD']*34,score=np.arange(34.)))
  b=a.copy();NN.same_scores(a,b);b.loc[0,'score']+=.01
  with self.assertRaises(RuntimeError):NN.same_scores(a,b)


class Owner(unittest.TestCase):
 def test_orphaned_or_stopped_claim_refuses_network(self):
  import monthly_owner as O,os
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);c=dict(root=d,month='2026-10',run=str(root/'run'))
   with patch.dict(os.environ,{'ASADO_MONTHLY_LOCK_OWNER':str(os.getpid())}):
    atomic(root/'Data/monthly/attempts/2026-10.json',dict(pid=os.getpid(),state='FAILED_STOPPED',run=c['run']))
    with self.assertRaises(RuntimeError):O.assert_owner(c)
 def test_daily_and_loop_outputs_are_outside_profile(self):
  cfg=read(SCRIPTS.parent/'config/monthly_worker.json')
  self.assertFalse(any('/loop/' in p or 'daily' in Path(p).name.lower() for p in cfg['data_targets']))


if __name__=='__main__':unittest.main()
