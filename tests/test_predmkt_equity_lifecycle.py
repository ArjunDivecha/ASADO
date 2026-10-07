"""No network/production writes: clock, discovery, book requests and output directory isolated."""
import sys,json
from pathlib import Path
from datetime import datetime,timezone
import pytest,requests
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import poll_predmkt_intraday as poll
import discover_predmkt_equity_universe as discovery
from predmkt_equity_common import polling_ineligibility,parse_stock_market
NOW=datetime(2026,10,7,22,tzinfo=timezone.utc)
def record(**kw):
    r={'platform':'polymarket','market_id':'future','ticker':'EWI','contract_class':'close_above_daily',
       'yes_token_id':'token','yes_rises_with_stock':True,'is_active':True,'active':True,'closed':False,
       'accepting_orders':True,'enable_order_book':True,'resolve_date':'2026-10-08T20:00:00Z'}
    return dict(r,**kw)
@pytest.mark.parametrize('kw',[{'closed':True},{'active':False},{'accepting_orders':False},
 {'enable_order_book':None},{'resolve_date':'2026-09-03T20:00:00Z'},
 {'resolve_date':NOW.isoformat()},{'resolve_date':None},{'resolve_date':'2026-10-08'}])
def test_lifecycle_fail_closed(kw): assert polling_ineligibility(record(**kw),NOW)
def test_eligible_keeps_identity():
    r=record();t,excluded=poll.eligible_targets([r],NOW)
    assert t==[r] and t[0]['market_id']=='future' and not excluded

def test_closed_child_in_active_parent_retained_but_not_polled(monkeypatch):
    market={'question':'Will Italy (EWI) close above $55 on October 8?','conditionId':'x',
      'clobTokenIds':['a','b'],'volumeNum':500,'active':True,'closed':True,
      'enableOrderBook':True,'acceptingOrders':False,'endDate':'2099-10-08T20:00:00Z'}
    monkeypatch.setattr(discovery,'_fetch_events',lambda *a,**k:[{'active':True,'markets':[market]}])
    records,_=discovery.discover(None)
    assert len(records)==1 and records[0]['is_active'] # preserve history record
    assert not poll.eligible_targets(records,NOW)[0]

@pytest.fixture
def run_env(tmp_path,monkeypatch):
    import yaml
    path=tmp_path/'universe.yaml';path.write_text(yaml.safe_dump([record(resolve_date='2026-09-03T20:00:00Z')]))
    monkeypatch.setattr(poll,'UNIVERSE_PATH',path);monkeypatch.setattr(poll,'OUT_DIR',tmp_path/'out')
    class Clock:
        @staticmethod
        def now(tz): return NOW
    monkeypatch.setattr(poll,'datetime',Clock)
    monkeypatch.setattr(sys,'argv',['poller'])
    monkeypatch.setattr(poll.time,'sleep',lambda x:None)
    return tmp_path/'out'
def test_no_coverage_is_explicit(run_env,monkeypatch):
    monkeypatch.setattr(poll,'discover',lambda s:([],0))
    monkeypatch.setattr(poll,'poll_market',lambda *a:pytest.fail('no expired request'))
    assert poll.main()==1
    receipts=list(run_env.glob('coverage_*.json'));assert len(receipts)==1
    assert json.loads(receipts[0].read_text())['status']=='no_coverage'
    assert not list(run_env.glob('*.parquet'))
def test_expired_cache_refreshes_without_rewriting_yaml(run_env,monkeypatch):
    before=poll.UNIVERSE_PATH.read_bytes()
    monkeypatch.setattr(poll,'discover',lambda s:([record()],0))
    monkeypatch.setattr(poll,'poll_market',lambda *a:{'market_id':'future','is_stale':False})
    assert poll.main()==0 and poll.UNIVERSE_PATH.read_bytes()==before
    assert json.loads(next(run_env.glob('coverage_*.json')).read_text())['eligible_markets']==['future']
def test_404_is_not_a_price():
    class Response:
        status_code=404
        def raise_for_status(self): raise requests.HTTPError('No orderbook exists')
    class Session:
        def get(self,*a,**kw):return Response()
    failures=[]
    assert poll.poll_market(Session(),record(),failures) is None
    assert failures[0]['http_status']==404

def test_discovery_outage_is_no_coverage(run_env,monkeypatch):
    def fail(s):raise requests.Timeout('timeout')
    monkeypatch.setattr(poll,'discover',fail)
    assert poll.main()==1
    assert json.loads(next(run_env.glob('coverage_*.json')).read_text())['discovery_error']=='timeout'
