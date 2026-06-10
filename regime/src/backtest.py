"""
=============================================================================
SCRIPT NAME: backtest.py
=============================================================================
Quintile L/S backtest with regime-conditional factor weights (PRD §5.5).
=============================================================================
"""

from __future__ import annotations

import logging
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

from .ic_analysis import prepare_ic_panel, spearman_ic
from .utils import (
    IN_SAMPLE_END,
    OOS_START,
    annualized_sharpe,
    max_drawdown,
    sortino_ratio,
)

logger = logging.getLogger(__name__)


def compute_factor_weights(
    panel: pd.DataFrame,
    regimes: pd.DataFrame,
    in_sample_end=IN_SAMPLE_END,
    shrinkage: float = 0.0,
) -> Dict[Tuple[str, str], float]:
    """
    In-sample mean IC by (factor, regime). Returns dict (factor, regime) -> weight.
    shrinkage: w = (1-s)*cond + s*uncond, then clip negative to 0 and normalize per regime.
    """
    reg = regimes[["date", "regime"]]
    m = panel.merge(reg, on="date", how="left")
    m = m[m["date"] <= in_sample_end]

    ic_rows = []
    for (dt, fac), g in m.groupby(["date", "factor"]):
        ic_rows.append(
            {
                "date": dt,
                "factor": fac,
                "regime": g["regime"].iloc[0],
                "ic": spearman_ic(g["signal"].values, g["ret"].values),
            }
        )
    ic_df = pd.DataFrame(ic_rows)
    cond_mean = ic_df.groupby(["factor", "regime"])["ic"].mean()
    uncond_mean = ic_df.groupby("factor")["ic"].mean()

    weights = {}
    for (fac, regime), c_ic in cond_mean.items():
        u_ic = uncond_mean.get(fac, 0.0)
        w_ic = (1 - shrinkage) * c_ic + shrinkage * u_ic
        weights[(fac, regime)] = max(w_ic, 0.0)

    # Normalize per regime
    for regime in ic_df["regime"].dropna().unique():
        keys = [k for k in weights if k[1] == regime]
        s = sum(weights[k] for k in keys)
        if s > 0:
            for k in keys:
                weights[k] /= s
        else:
            n = len(keys)
            for k in keys:
                weights[k] = 1.0 / n if n else 0.0
    return weights


def composite_score(
    panel: pd.DataFrame,
    date: pd.Timestamp,
    factor_weights: Dict[str, float],
) -> pd.Series:
    """Country composite = sum_f w_f * signal_{c,f} at date."""
    g = panel[panel["date"] == date]
    if g.empty:
        return pd.Series(dtype=float)
    wide = g.pivot(index="country", columns="factor", values="signal")
    w = pd.Series({f: factor_weights.get(f, 0.0) for f in wide.columns})
    if w.sum() == 0:
        w = pd.Series(1.0 / len(wide.columns), index=wide.columns)
    else:
        w = w / w.sum()
    return wide.fillna(0).mul(w, axis=1).sum(axis=1)


def quintile_ls_returns(
    scores: pd.Series,
    fwd_ret: pd.DataFrame,
    date: pd.Timestamp,
) -> float:
    """Long top quintile, short bottom quintile, equal weight."""
    r = fwd_ret[fwd_ret["date"] == date].set_index("country")["fwd_ret"]
    common = scores.index.intersection(r.index)
    if len(common) < 10:
        return np.nan
    s = scores.loc[common]
    ret = r.loc[common]
    try:
        q = pd.qcut(s.rank(method="first"), 5, labels=False)
    except ValueError:
        return np.nan
    long_m = ret[q == 4].mean()
    short_m = ret[q == 0].mean()
    return float(long_m - short_m)


def run_backtest(
    panel: pd.DataFrame,
    fwd_returns: pd.DataFrame,
    regimes: pd.DataFrame,
    weights_cond: Dict[Tuple[str, str], float],
    weights_uncond: Dict[Tuple[str, str], float],
    oos_start=OOS_START,
) -> pd.DataFrame:
    """Monthly strategy returns OOS."""
    reg = regimes.set_index("date")["regime"]
    dates = sorted(panel["date"].unique())
    dates = [d for d in dates if d >= oos_start]

    rows = []
    for dt in dates:
        regime = reg.get(dt, "Transition")
        w_cond = {f: weights_cond.get((f, regime), 0.0) for f in panel["factor"].unique()}
        w_base = {f: weights_uncond.get((f, "__all__"), 0.0) for f in panel["factor"].unique()}

        sc_cond = composite_score(panel, dt, w_cond)
        sc_base = composite_score(panel, dt, w_base)

        rows.append(
            {
                "date": dt,
                "regime": regime,
                "ret_treatment": quintile_ls_returns(sc_cond, fwd_returns, dt),
                "ret_baseline": quintile_ls_returns(sc_base, fwd_returns, dt),
            }
        )
    return pd.DataFrame(rows)


def uncond_weights(panel: pd.DataFrame, in_sample_end=IN_SAMPLE_END) -> Dict[Tuple[str, str], float]:
    m = panel[panel["date"] <= in_sample_end]
    ic_rows = []
    for (dt, fac), g in m.groupby(["date", "factor"]):
        ic_rows.append({"factor": fac, "ic": spearman_ic(g["signal"].values, g["ret"].values)})
    ic_df = pd.DataFrame(ic_rows)
    mean_ic = ic_df.groupby("factor")["ic"].mean()
    pos = mean_ic.clip(lower=0)
    if pos.sum() == 0:
        pos = pd.Series(1.0 / len(mean_ic), index=mean_ic.index)
    else:
        pos = pos / pos.sum()
    return {(f, "__all__"): pos[f] for f in pos.index}


def performance_metrics(returns: pd.Series) -> Dict[str, float]:
    r = returns.dropna()
    if r.empty:
        return {}
    cum = r.cumsum()
    return {
        "ann_return": float(r.mean() * 12),
        "ann_vol": float(r.std() * np.sqrt(12)),
        "sharpe": annualized_sharpe(r),
        "sortino": sortino_ratio(r),
        "max_dd": max_drawdown(r),
        "hit_rate": float((r > 0).mean()),
        "avg_win": float(r[r > 0].mean()) if (r > 0).any() else np.nan,
        "avg_loss": float(r[r < 0].mean()) if (r < 0).any() else np.nan,
        "worst_month": float(r.min()),
        "calmar": float(r.mean() * 12 / abs(max_drawdown(r))) if max_drawdown(r) != 0 else np.nan,
    }


def rolling_5y_sharpe(returns: pd.DataFrame, col: str, window: int = 60) -> pd.Series:
    r = returns.set_index("date")[col]
    return r.rolling(window, min_periods=36).apply(
        lambda x: annualized_sharpe(pd.Series(x)), raw=False
    )
