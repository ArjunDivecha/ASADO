from pathlib import Path
import sys
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import p2p_monthly as p
import t2_optimizer as opt
from t2_normalize import normalize_data


def prices():
    dates=pd.date_range('1999-01-01','2001-03-01',freq='MS')
    return pd.DataFrame({'AAA':np.linspace(10,50,len(dates)), 'BBB':np.linspace(50,10,len(dates))},index=dates)

@pytest.mark.parametrize('asof,latest',[('2000-02-01','2000-02-01'),('2000-02-29','2000-02-01'),('2000-03-01','2000-03-01'),('2000-12-31','2000-12-01'),('2001-01-01','2001-01-01')])
def test_only_completed_months_with_next_month_label(asof,latest):
    result=p.compute_scores(prices(),['AAA','BBB'],asof)
    assert result.date.max()==pd.Timestamp(latest)
    first=prices().AAA.iloc[:13]
    assert result.iloc[0].AAA==pytest.approx(p.score_window(first))
    assert result.iloc[0].date==pd.Timestamp('2000-02-01')


def test_future_and_partial_prices_cannot_change_past_scores():
    a=prices();b=a.copy();b.loc['2000-02-01':]*=1000
    pd.testing.assert_frame_equal(p.compute_scores(a,['AAA','BBB'],'2000-02-29'),p.compute_scores(b,['AAA','BBB'],'2000-02-29'))


def test_missing_month_not_compressed_into_regression():
    a=prices().drop(pd.Timestamp('2000-12-01'))
    with pytest.raises(ValueError,match='Insufficient'):p.compute_scores(a,['AAA','BBB'],'2001-03-01')


def test_missing_latest_prices_fails():
    a=prices();a.loc['2001-02-01','BBB']=np.nan
    with pytest.raises(ValueError,match='Missing latest'):p.compute_scores(a,['AAA','BBB'],'2001-03-01')


def test_cache_contract_maps_tickers_not_column_order(tmp_path,monkeypatch):
    monkeypatch.setattr(p,'country_etfs',lambda:{'One':'AAA','Two':'BBB'})
    scores=p.compute_scores(prices(),['BBB','AAA'],'2001-03-01');path=tmp_path/'scores.xlsx';p.save_scores(scores,path)
    loaded=p.load_scores(path,'2001-03-01')
    np.testing.assert_allclose(loaded.One,scores.AAA)
    np.testing.assert_allclose(loaded.Two,scores.BBB)
    assert loaded.Country.equals(scores.date)
    with pytest.raises(ValueError,match='stale'):p.load_scores(path,'2001-04-01')


def test_legacy_cache_rejected(tmp_path):
    path=tmp_path/'old.xlsx';prices().to_excel(path)
    with pytest.raises(ValueError,match='Legacy'):p.load_scores(path,'2001-03-01')


def test_normalization_keeps_availability_label_and_prefix(tmp_path):
    def normal(frame,path):
        master=path/'master.xlsx';path.mkdir();frame.to_excel(master,sheet_name='P2P',index=False)
        return pd.read_csv(normalize_data(master,path,write_xlsx=False))
    a=pd.DataFrame({'Country':pd.to_datetime(['2000-02-01','2000-03-01']),'One':[.2,.3],'Two':[.8,.7]})
    x=normal(a,tmp_path/'short');b=pd.concat([a,pd.DataFrame({'Country':[pd.Timestamp('2000-04-01')],'One':[100.],'Two':[-100.]})],ignore_index=True);y=normal(b,tmp_path/'long')
    pd.testing.assert_frame_equal(x,y.loc[y.date<'2000-04-01'].reset_index(drop=True))
    assert set(x.date)=={'2000-02-01','2000-03-01'}


def sample():
    rows=[]
    for i in range(10):
        for variable,value in [('P2P_CS',10-i),('1MRet',i/100)]:rows.append({'date':pd.Timestamp('2000-02-01'),'country':str(i),'variable':variable,'value':value})
    return pd.DataFrame(rows)


def test_optimizer_selects_without_future_target_availability():
    d=sample();benchmark=pd.Series([0.],index=[pd.Timestamp('2000-02-01')]);base=opt._step3_holdings(d,['P2P_CS'],benchmark)['P2P_CS']
    d.loc[(d.country=='0')&(d.variable=='1MRet'),'value']=np.nan
    pd.testing.assert_frame_equal(base,opt._step3_holdings(d,['P2P_CS'],benchmark)['P2P_CS'])
    assert opt._p2p_net_returns(d,'P2P_CS',benchmark).empty
    d=sample();d.loc[(d.country=='9')&(d.variable=='1MRet'),'value']=np.nan
    assert len(opt._p2p_net_returns(d,'P2P_CS',benchmark))==1


def test_missing_p2p_return_not_imputed_from_other_factors():
    frame=pd.DataFrame({'P2P_CS':[np.nan,.1],'other':[.5,np.nan]})
    result=opt._fill_non_p2p_missing(frame)
    assert pd.isna(result.P2P_CS.iloc[0])
    assert result.other.iloc[1]==.1


def test_formula_preserved_against_original_implementation():
    from build_t2_master import _p2p_score
    window=pd.Series([10,11,9,12,13,15,14,12,16,17,18,16,19],dtype=float)
    assert p.score_window(window)==pytest.approx(_p2p_score(window),abs=1e-15)


def test_availability_label_joins_next_observation_month_return():
    from build_t2_master import _standardize_date,_forward_returns
    levels=pd.DataFrame({'Country':pd.to_datetime(['1999-12-31','2000-01-31','2000-02-29']), 'One':[100.,110.,132.]})
    targets=_forward_returns(_standardize_date(levels),1).set_index('Country')
    score=p.compute_scores(prices(),['AAA','BBB'],'2000-02-01').iloc[-1]
    assert score.date==pd.Timestamp('2000-02-01')
    assert targets.loc[score.date,'One']==pytest.approx(.2)
    assert pd.isna(targets.iloc[-1].One)
