import unittest
import numpy as np
import pandas as pd
from run import FEATURES, ARMS, MACRO, row_weights, fit_one, predict, design, training_for, walk_forward


def fixture(months=85):
    rng=np.random.default_rng(187)
    dates=pd.date_range('2000-01-01',periods=months,freq='MS')
    rows=[]
    for date in dates:
        for c in range(8):
            x=rng.normal(size=len(FEATURES));r=dict(zip(FEATURES,x))
            r.update(date=date,country=f'C{c}',macro_identity='shared' if c<2 else f'M{c}',
                     eligible=True,relative_target=.03*x[0]-.01*x[-1],
                     label_available_at=date+pd.offsets.MonthBegin(12),cheap_pb=x[-3],momentum_12_1=x[-2])
            rows.append(r)
    return pd.DataFrame(rows)

class Models(unittest.TestCase):
    def test_weights_equal_dates_identities(self):
        d=fixture(2);d['w']=row_weights(d)
        np.testing.assert_allclose(d.groupby('date').w.sum(),.5)
        self.assertAlmostEqual(d.groupby(['date','macro_identity']).w.sum().max(),1/14)

    def test_maturity_exact_boundary(self):
        d=fixture();t=training_for(d,pd.Timestamp('2005-12-01'))
        self.assertEqual(t.date.nunique(),60)
        self.assertEqual(t.label_available_at.max(),pd.Timestamp('2005-12-01'))
        self.assertIsNone(training_for(d,pd.Timestamp('2005-11-01')))

    def test_missing_optional_features_finite(self):
        d=fixture();d.loc[::2,MACRO[4:]]=np.nan
        for arm in ARMS:
            model=fit_one(d,arm);self.assertTrue(np.isfinite(predict(d,model,arm)).all())

    def test_state_primitive_interactions_identical(self):
        rng=np.random.default_rng(11);z=rng.normal(size=(20,len(FEATURES)));mask=np.zeros_like(z)
        a,_=design(z,mask,'states_interactions');b,_=design(z,mask,'primitives_interactions')
        np.testing.assert_allclose(a[:,-2:],b[:,-2:])

    def test_future_target_changes_do_not_change_early_predictions(self):
        d=fixture();a,f,_=walk_forward(d,pd.Timestamp('2006-01-01'))
        d.loc[d.label_available_at>pd.Timestamp('2005-12-01'),'relative_target']=1e10
        b,_,_=walk_forward(d,pd.Timestamp('2006-01-01'))
        np.testing.assert_allclose(a[ARMS],b[ARMS])
        self.assertTrue((f.latest_label_available<=f.fit_date).all())

    def test_future_input_changes_do_not_change_past_predictions(self):
        d=fixture();a,_,_=walk_forward(d,pd.Timestamp('2006-01-01'))
        d.loc[d.date>pd.Timestamp('2006-01-01'),FEATURES]=999
        b,_,_=walk_forward(d,pd.Timestamp('2006-01-01'))
        np.testing.assert_allclose(a[ARMS],b[ARMS])

    def test_no_refit_between_annual_boundaries(self):
        d=fixture(96);_,f,_=walk_forward(d,pd.Timestamp('2007-12-01'))
        self.assertEqual(list(f.fit_date),list(pd.to_datetime(['2005-12-01','2006-12-01','2007-12-01'])))

    def test_zero_targets_zero_predictions(self):
        d=fixture();d['relative_target']=0.
        for arm in ARMS:np.testing.assert_allclose(predict(d,fit_one(d,arm),arm),0)

if __name__=='__main__':unittest.main()
