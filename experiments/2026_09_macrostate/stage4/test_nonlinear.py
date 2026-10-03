import unittest
import sys
from pathlib import Path
import numpy as np
from run_nonlinear import fit_one,predict,ARMS
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'stage3'))
from test_models import fixture

class NonlinearTests(unittest.TestCase):
    def test_fixed_seed_repeatable_all_arms(self):
        d=fixture(12)
        for arm in ARMS:
            a=fit_one(d,arm);b=fit_one(d,arm)
            np.testing.assert_allclose(predict(d,a),predict(d,b),rtol=0,atol=1e-12)

    def test_unused_future_targets_cannot_change_model(self):
        d=fixture(15);train=d[d.date<'2001-01-01'].copy()
        for arm in ARMS:
            a=fit_one(train,arm);d.loc[d.date>='2001-01-01','relative_target']=999
            b=fit_one(d[d.date<'2001-01-01'],arm)
            np.testing.assert_allclose(predict(train,a),predict(train,b),rtol=0,atol=1e-12)

    def test_missing_optional_inputs_supported(self):
        d=fixture(12)
        d.loc[::2,['cds_5y_z','fx_vol_1m_z']]=np.nan
        for arm in ARMS:self.assertTrue(np.isfinite(predict(d,fit_one(d,arm))).all())

    def test_fixed_iteration_budget(self):
        d=fixture(12)
        for arm in ARMS:self.assertEqual(fit_one(d,arm)['iterations'],200 if arm.startswith('trees') else 300)

if __name__=='__main__':unittest.main()
