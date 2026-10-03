"""Arithmetic, missing-data and temporal canaries for the isolated evaluator."""
import unittest
import numpy as np
import pandas as pd
from evaluator import picks, simulate, metrics
from prepare import forward_returns, prior_z, daily_monthly, consensus_features, mature_training_rows


class PortfolioTests(unittest.TestCase):
    def frames(self, n=5, periods=24, rate=.01):
        dates=pd.date_range('2001-01-01',periods=periods,freq='MS')
        cols=pd.Index([f'C{x:02d}' for x in range(n)])
        s=pd.DataFrame(np.tile(np.arange(n),(periods,1)),index=dates,columns=cols,dtype=float)
        return s,pd.DataFrame(True,index=dates,columns=cols),pd.DataFrame(rate,index=dates,columns=cols,dtype=float)

    def test_top20_rounding_34(self):
        s,u,r=self.frames(34)
        self.assertEqual(len(picks(s.iloc[0],u.iloc[0])),7)
        self.assertEqual(picks(s.iloc[0],u.iloc[0])[0],'C33')

    def test_ties_canonical(self):
        s,u,r=self.frames();s[:]=1
        self.assertEqual(picks(s.iloc[0],u.iloc[0]),['C00'])

    def test_one_month_arithmetic(self):
        s,u,r=self.frames(periods=2);r['C04']=[.1,-.1]
        a,c,_=simulate(s,u,r)
        self.assertAlmostEqual(a.nav.iloc[-1],.99)
        self.assertAlmostEqual(c.pnl.sum(),-.01)

    def test_equal_weight_hand_calculation(self):
        s,u,r=self.frames(periods=1);r.iloc[0]=[.1,.2,0,-.1,0]
        a,_,_=simulate(s,u,r,select=False)
        self.assertAlmostEqual(a.nav.iloc[0],1.04)

    def test_identical_returns_match(self):
        s,u,r=self.frames()
        for hold in [1,12]:
            a,_,_=simulate(s,u,r,hold,True);b,_,_=simulate(s,u,r,hold,False)
            np.testing.assert_allclose(a.nav,b.nav)

    def test_vintage_ramp(self):
        s,u,r=self.frames(periods=12,rate=.1)
        a,_,_=simulate(s,u,r,12)
        self.assertAlmostEqual(a.nav.iloc[0],1+.1/12)
        self.assertAlmostEqual(a.nav.iloc[-1],sum(1.1**k for k in range(1,13))/12)

    def test_vintage_holds_names_until_maturity(self):
        s,u,r=self.frames(periods=13,rate=0)
        s.iloc[1:,0]=99
        r.iloc[1,4]=.12
        a,_,sel=simulate(s,u,r,12)
        self.assertAlmostEqual(a.nav.iloc[1],1.01)
        self.assertAlmostEqual(sel.loc[sel.date.eq(s.index[12]),'new_allocation'].sum(),1.12/12)

    def test_missing_held_return_fails(self):
        s,u,r=self.frames();r.iloc[0,4]=np.nan
        with self.assertRaisesRegex(ValueError,'held return'):simulate(s,u,r)

    def test_delisting_not_silently_removed(self):
        s,u,r=self.frames();u.iloc[1:,4]=False;r.iloc[1,4]=np.nan
        with self.assertRaisesRegex(ValueError,'held return'):simulate(s,u,r,12)

    def test_missing_unheld_return_allowed(self):
        s,u,r=self.frames();u['C00']=False;r['C00']=np.nan
        simulate(s,u,r)

    def test_missing_score_fails(self):
        s,u,r=self.frames();s.iloc[0,0]=np.nan
        with self.assertRaisesRegex(ValueError,'score'):simulate(s,u,r)

    def test_skipped_month_fails(self):
        s,u,r=self.frames();s=s.drop(s.index[5]);u=u.loc[s.index]
        with self.assertRaisesRegex(ValueError,'calendar'):simulate(s,u,r)

    def test_duplicate_keys_fail(self):
        s,u,r=self.frames();s=pd.concat([s.iloc[:1],s])
        with self.assertRaisesRegex(ValueError,'Duplicate'):simulate(s,u,r)

    def test_drawdown_includes_initial_loss(self):
        s,u,r=self.frames(periods=1,rate=-.2)
        a,_,_=simulate(s,u,r)
        self.assertAlmostEqual(metrics(a,a)['max_drawdown'],-.2)

    def test_invalid_return_fails(self):
        s,u,r=self.frames();r.iloc[0,4]=-1.1
        with self.assertRaisesRegex(ValueError,'held return'):simulate(s,u,r)

    def test_future_scores_cannot_change_past(self):
        s,u,r=self.frames();a,_,_=simulate(s,u,r,12)
        s.iloc[12:]=s.iloc[12:]*-1
        b,_,_=simulate(s,u,r,12)
        np.testing.assert_allclose(a.nav.iloc[:12],b.nav.iloc[:12])


class TemporalTests(unittest.TestCase):
    def test_label_maturity_boundary(self):
        origins=pd.date_range("2020-01-01", periods=13, freq="MS")
        self.assertEqual(mature_training_rows(origins,"2021-01-01",12).tolist(),[True]+[False]*12)

    def test_target_full_window(self):
        r=pd.DataFrame({'A':[.1]*15})
        t=forward_returns(r,12)
        self.assertAlmostEqual(t.iloc[0,0],1.1**12-1)
        self.assertTrue(t.iloc[4:,0].isna().all())

    def test_target_missing_interior_not_dropped(self):
        r=pd.DataFrame({'A':[.1]*15});r.iloc[5]=np.nan
        self.assertTrue(pd.isna(forward_returns(r,12).iloc[0,0]))

    def test_normalization_prefix_invariant(self):
        f=pd.DataFrame({'A':np.arange(100.)})
        a=prior_z(f);f.iloc[80:]=1e9;b=prior_z(f)
        np.testing.assert_allclose(a.iloc[:80],b.iloc[:80],equal_nan=True)
        np.testing.assert_allclose(a.iloc[:60],prior_z(f.iloc[:60]),equal_nan=True)

    def test_daily_after_cutoff_excluded(self):
        d=pd.DataFrame({'date':pd.to_datetime(['2020-01-30','2020-02-01']),
                        'country':['A','A'],'variable':['V','V'],'value':[1.,99.]})
        dates=pd.date_range('2020-01-31',periods=1,freq='ME')
        v,_=daily_monthly(d,dates,['A'],'V');self.assertEqual(v.iloc[0,0],1)

    def test_stale_value_masked(self):
        d=pd.DataFrame({'date':pd.to_datetime(['2020-01-01']),
                        'country':['A'],'variable':['V'],'value':[1.]})
        dates=pd.date_range('2020-01-31',periods=1,freq='ME')
        v,a= daily_monthly(d,dates,['A'],'V');self.assertTrue(pd.isna(v.iloc[0,0]));self.assertEqual(a.iloc[0,0],30)

    def test_consensus_contiguous_months(self):
        dates=pd.date_range('2020-01-31',periods=5,freq='ME');rows=[]
        for y in [2020,2021]:
            for j,d in enumerate(dates):
                if j==1:continue
                rows.append({'date':d,'country':'A','target_year':y,'variable':'CONS_GDP_PCT','value':float(j)})
        f=consensus_features(pd.DataFrame(rows),dates,['A'])
        self.assertAlmostEqual(f['gdp_revision_3m'].iloc[3,0],3)
        self.assertTrue(pd.isna(f['gdp_revision_3m'].iloc[4,0]))

    def test_consensus_requires_both_target_years(self):
        dates=pd.date_range('2020-01-31',periods=4,freq='ME')
        d=pd.DataFrame({'date':dates,'country':'A','target_year':2020,'variable':'CONS_GDP_PCT','value':1.})
        self.assertTrue(consensus_features(d,dates,['A'])['gdp_expectation'].isna().all().all())

if __name__=='__main__':unittest.main()
