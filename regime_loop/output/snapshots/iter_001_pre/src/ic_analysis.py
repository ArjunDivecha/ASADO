"""
=============================================================================
SCRIPT NAME: ic_analysis.py
=============================================================================
Regime-conditional cross-sectional IC (PRD §5.4).
=============================================================================
"""

from __future__ import annotations

import logging
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.stats.multitest import multipletests

from .utils import IN_SAMPLE_END, REGIME_LABELS

logger = logging.getLogger(__name__)


def spearman_ic(factor_vals: np.ndarray, returns: np.ndarray) -> float:
    mask = np.isfinite(factor_vals) & np.isfinite(returns)
    if mask.sum() < 8:
        return np.nan
    rho, _ = stats.spearmanr(factor_vals[mask], returns[mask])
    return float(rho)


def prepare_ic_panel(
    factors: pd.DataFrame,
    fwd_returns: pd.DataFrame,
) -> pd.DataFrame:
    """
    Cross-section at each date: lag factor 1 month vs contemporaneous forward return.
    """
    f = factors.copy()
    f = f.sort_values(["country", "date", "factor"])
    f["factor_lag"] = f.groupby(["country", "factor"])["value"].shift(1)
    f = f.dropna(subset=["factor_lag"])

    merged = f.merge(fwd_returns, on=["date", "country"], how="inner")
    merged = merged.rename(columns={"factor_lag": "signal", "fwd_ret": "ret"})
    return merged[["date", "country", "factor", "signal", "ret"]]


def monthly_ic(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (dt, fac), g in panel.groupby(["date", "factor"]):
        ic = spearman_ic(g["signal"].values, g["ret"].values)
        rows.append({"date": dt, "factor": fac, "ic": ic})
    return pd.DataFrame(rows)


def conditional_ic_table(
    ic_monthly: pd.DataFrame,
    regimes: pd.DataFrame,
    in_sample_end=IN_SAMPLE_END,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Mean IC by factor × regime; F-test; BH-FDR."""
    reg = regimes[["date", "regime"]].copy()
    m = ic_monthly.merge(reg, on="date", how="left")
    m = m[m["date"] <= in_sample_end]

    cond = (
        m.groupby(["factor", "regime"])["ic"]
        .agg(["mean", "std", "count"])
        .reset_index()
    )
    cond_pivot = cond.pivot(index="factor", columns="regime", values="mean")

    # Unconditional in-sample mean IC
    uncond = m.groupby("factor")["ic"].mean().rename("ic_unconditional")

    # F-test across regimes per factor
    test_rows = []
    for fac, g in m.groupby("factor"):
        groups = [grp["ic"].dropna().values for _, grp in g.groupby("regime") if len(grp) >= 3]
        groups = [x for x in groups if len(x) >= 5]
        if len(groups) < 2:
            pval = np.nan
            fstat = np.nan
        else:
            fstat, pval = stats.f_oneway(*groups)
        test_rows.append(
            {
                "factor": fac,
                "f_stat": fstat,
                "p_value": pval,
                "ic_dispersion": float(g.groupby("regime")["ic"].mean().std()),
                "sign_reversal": _sign_reversal(g),
            }
        )
    tests = pd.DataFrame(test_rows).set_index("factor")
    valid = tests["p_value"].notna()
    if valid.sum() > 0:
        reject, p_adj, _, _ = multipletests(
            tests.loc[valid, "p_value"], alpha=0.20, method="fdr_bh"
        )
        tests.loc[valid, "p_adj_fdr"] = p_adj
        tests.loc[valid, "significant_fdr"] = reject
    tests = tests.join(uncond)

    n_factors = tests.shape[0]
    n_sig = int(tests.get("significant_fdr", pd.Series(dtype=bool)).fillna(False).sum())
    logger.info("H2: %d / %d factors significant at FDR 10%%", n_sig, n_factors)

    return cond_pivot, cond, tests


def _sign_reversal(g: pd.DataFrame) -> bool:
    means = g.groupby("regime")["ic"].mean()
    if len(means) < 2:
        return False
    return (means.max() > 0) and (means.min() < 0)


def top_dispersion_factors(tests: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    return tests.sort_values("ic_dispersion", ascending=False).head(n)
