from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT.parent))

from regime_ew.src.ew_model import gate3_lead  # noqa: E402


def test_gate3_pairs_signal_t_with_forward_return_t():
    dates = pd.date_range("2020-01-01", periods=24, freq="MS")
    p_adverse = [i / 25 for i in range(1, 25)]
    returns_1m = [0.04 - p * 0.08 for p in p_adverse]
    signals = pd.DataFrame(
        {
            "date": dates,
            "country": ["A"] * len(dates),
            "P_adverse": p_adverse,
            "dP_adverse": pd.Series(p_adverse).diff(),
        }
    )
    returns = pd.DataFrame(
        {
            "date": dates,
            "country": ["A"] * len(dates),
            "horizon": ["1MRet"] * len(dates),
            "ret": returns_1m,
        }
    )
    rows, _ = gate3_lead(signals, returns, ["A"])
    assert rows.loc[0, "n_obs_1MRet"] == 24
    assert rows.loc[0, "spread_bottom_minus_top_P_adverse_1MRet"] > 0
