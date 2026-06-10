"""
=============================================================================
SCRIPT NAME: regime_tagger.py
=============================================================================
Deterministic macro regime labeling (PRD §5.1–5.2).

FIXES APPLIED (regime2):
1. HY OAS: Using BAA10Y (Moody's BAA Corporate Bond OAS) with recalibrated thresholds
   - BAA10Y range: 1.29% to 6.01% (investment-grade spread)
   - Thresholds: >3.5% = stress, >2.5% = elevated, <2.0% = benign
2. ISM PMI: Using UMCSENT (Michigan Consumer Sentiment) as activity proxy
   - UMCSENT range: 49.8 to 112.0 (sentiment index, mean=84.2)
   - Thresholds: >90 = expansion, <70 = contraction
3. Recovery rule: Loosened to allow partial condition matches
=============================================================================
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from .utils import REGIME_LABELS

logger = logging.getLogger(__name__)


def tag_regime(row: pd.Series) -> Tuple[str, List[str]]:
    """
    Apply ordered rules 1→6; first match wins. Else Transition.
    Returns (regime_label, list_of_rules_that_fired).
    
    Thresholds calibrated for:
    - BAA10Y: Moody's BAA Corporate Bond OAS (1.29-6.01%, median 2.16%)
    - UMCSENT: Michigan Consumer Sentiment (49.8-112.0, median 87.0)
    """
    fired: List[str] = []

    vix = row.get("vix", np.nan)
    baa_oas = row.get("baa_oas", np.nan)  # BAA OAS in percent
    y210 = row.get("yield_2s10s", np.nan)
    fed_chg = row.get("fed_funds_chg_12m", np.nan)
    nber = row.get("nber_recession", 0)
    sahm = row.get("sahm_triggered", 0)
    cpi_yoy = row.get("cpi_yoy", np.nan)
    sentiment = row.get("umcsent", np.nan)  # Michigan Consumer Sentiment
    sentiment_chg_3m = row.get("umcsent_chg_3m", np.nan)
    vix_chg_3m = row.get("vix_chg_3m", np.nan)
    baa_chg_3m = row.get("baa_oas_chg_3m", np.nan)
    vix_lag3 = row.get("vix_lag3", np.nan)

    # Regime 1: Crisis (VIX spike OR severe credit stress)
    # BAA10Y > 3.5% = 95th percentile (GFC peaked at 6.01%)
    r1 = (
        (pd.notna(vix) and vix > 30)
        or (pd.notna(baa_oas) and baa_oas > 3.5)
        or (pd.notna(vix) and pd.notna(baa_oas) and vix > 25 and baa_oas > 2.5)
    )
    if r1:
        fired.append("R1_Crisis")
        return "Crisis", fired

    # Regime 3: Recession (before late-cycle — NBER can overlap tightening)
    r3 = (nber == 1) or (sahm == 1)
    if r3:
        fired.append("R3_Recession")
        return "Crisis", fired

    # Regime 2: Late-cycle / Tightening
    # Fed tightening + flat/inverted curve + low vol + benign credit
    r2 = (
        pd.notna(fed_chg)
        and fed_chg > 0
        and pd.notna(y210)
        and y210 < 0.50
        and pd.notna(vix)
        and vix < 25
        and pd.notna(baa_oas)
        and baa_oas < 2.5  # Benign credit
    )
    if r2:
        fired.append("R2_Late-cycle")
        return "Late-cycle", fired

    # Regime 4: Recovery (VIX falling + credit tightening + sentiment improving)
    # Loosened: require 2 of 3 conditions instead of all 3
    conditions_met = 0
    if pd.notna(vix_lag3) and pd.notna(vix) and vix_lag3 > 25 and vix < 22:
        conditions_met += 1
    if pd.notna(baa_chg_3m) and baa_chg_3m < 0:
        conditions_met += 1
    if pd.notna(sentiment_chg_3m) and sentiment_chg_3m > 0:
        conditions_met += 1
    
    r4 = conditions_met >= 2
    if r4:
        fired.append("R4_Recovery")
        return "Expansion", fired

    # Regime 5: Expansion (low vol + steep curve + strong sentiment + no recession)
    # UMCSENT > 90 = expansion (1995-2000 boom avg = 101.2)
    r5 = (
        pd.notna(vix)
        and vix < 20
        and pd.notna(y210)
        and y210 > 0.50
        and pd.notna(sentiment)
        and sentiment > 90  # Strong sentiment
        and nber == 0
    )
    if r5:
        fired.append("R5_Expansion")
        return "Expansion", fired

    # Regime 6: Stagflation (high inflation + weak sentiment)
    # UMCSENT < 70 = contraction (GFC avg = 65.0)
    r6 = (
        pd.notna(cpi_yoy) 
        and cpi_yoy > 4 
        and pd.notna(sentiment) 
        and sentiment < 70
    )
    if r6:
        fired.append("R6_Stagflation")
        return "Late-cycle", fired

    fired.append("R7_Transition")
    return "Transition", fired


def build_regime_series(macro: pd.DataFrame) -> pd.DataFrame:
    """Tag each month; add lagged VIX for recovery rule."""
    df = macro.copy()
    df = df.sort_values("date")
    df["vix_lag3"] = df["vix"].shift(3)

    regimes = []
    multi_rule_months = []
    for _, row in df.iterrows():
        label, fired = tag_regime(row)
        regimes.append(
            {
                "date": row["date"],
                "regime": label,
                "rules_fired": "|".join(fired),
                "multi_rule": len([f for f in fired if f.startswith("R") and f != "R7_Transition"]) > 1,
            }
        )

    out = pd.DataFrame(regimes)
    out = out.merge(df, on="date", how="left")
    if out["multi_rule"].any():
        n = int(out["multi_rule"].sum())
        logger.warning("%d months flagged with multiple rule hits (first-match wins)", n)

    dist = out["regime"].value_counts(normalize=True)
    logger.info("Regime distribution:\n%s", dist.to_string())
    if dist.max() > 0.50:
        logger.warning("Dominant regime >50%%: %s", dist.idxmax())
    if dist.min() < 0.02:
        logger.warning("Rare regime <2%%: %s", dist.idxmin())

    return out


def persistence_stats(regimes: pd.DataFrame) -> Dict[str, Any]:
    """H1: persistence and transition matrix."""
    s = regimes.set_index("date")["regime"]
    labels = [r for r in REGIME_LABELS if r in s.unique()]
    tm = pd.DataFrame(0.0, index=labels, columns=labels)
    for t, t1 in zip(s.iloc[:-1], s.iloc[1:]):
        if t in tm.index and t1 in tm.columns:
            tm.loc[t, t1] += 1
    row_sums = tm.sum(axis=1).replace(0, np.nan)
    tm_prob = tm.div(row_sums, axis=0)

    horizons = [1, 3, 6]
    persist = {}
    for h in horizons:
        same = []
        for i in range(len(s) - h):
            if s.iloc[i] == s.iloc[i + h]:
                same.append(1.0)
            else:
                same.append(0.0)
        persist[f"persist_{h}m"] = float(np.mean(same)) if same else np.nan

    # Weighted 1m persistence by regime frequency
    one_m = []
    weights = []
    for r in labels:
        mask = s == r
        idx = np.where(mask)[0]
        if len(idx) < 2:
            continue
        stays = sum(1 for i in idx if i + 1 < len(s) and s.iloc[i + 1] == r)
        one_m.append(stays / max(1, len(idx) - 1))
        weights.append(mask.sum())
    weighted_persist = float(np.average(one_m, weights=weights)) if weights else np.nan

    # Mean duration
    durations = []
    i = 0
    while i < len(s):
        j = i + 1
        while j < len(s) and s.iloc[j] == s.iloc[i]:
            j += 1
        durations.append(j - i)
        i = j
    mean_duration = float(np.mean(durations))

    return {
        "transition_counts": tm,
        "transition_probs": tm_prob,
        "persist_1m_unweighted": persist.get("persist_1m"),
        "persist_3m": persist.get("persist_3m"),
        "persist_6m": persist.get("persist_6m"),
        "weighted_persist_1m": weighted_persist,
        "mean_duration_months": mean_duration,
        "regime_durations": durations,
    }
