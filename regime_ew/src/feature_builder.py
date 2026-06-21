"""
=============================================================================
SCRIPT NAME: regime_ew/src/feature_builder.py
=============================================================================

DESCRIPTION:
    Builds per-country feature matrices for the EW HMM test.
    Selects 6 economically distinct _CS factors, applies per-country
    expanding-window z-scoring (converts cross-sectional rank to own-history
    view), and enforces missing-data rules per the PRD §2.1.

INPUT FILES:
    regime/data/processed/t2_factors_cs.parquet (via load_factor_panel)

OUTPUT:
    Dict[country -> pd.DataFrame(date_index, feature_columns)]

VERSION: 1.0
LAST UPDATED: 2026-06-21
AUTHOR: Arjun Divecha (built by agent session)
=============================================================================
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from regime.src.utils import T2_COUNTRIES

logger = logging.getLogger(__name__)

# Ordered fallback lists for each of the 6 PRD feature slots.
# First available candidate in each slot wins.
FEATURE_CANDIDATES: list[list[str]] = [
    # 1. Longest-horizon momentum (12-1 MoM)
    ["12-1MTR_CS", "12MTR_CS", "6-1MTR_CS", "3MTR_CS", "1MTR_CS"],
    # 2. REER
    ["REER_CS"],
    # 3. RSI
    ["RSI14_CS"],
    # 4. Valuation
    ["Best PE _CS", "Shiller PE_CS", "Earnings Yield_CS"],
    # 5. Inflation
    ["Inflation_CS", "GDP_CS"],
    # 6. Quality / secondary valuation fallback
    ["Best ROE_CS", "Best Cash Flow_CS", "Operating Margin_CS"],
]

MIN_EXPANDING_OBS = 24   # minimum observations to compute expanding z-score
MAX_FFILL_MONTHS = 1     # forward-fill single gaps only


def discover_features(available: list[str]) -> list[str]:
    """Pick the first available candidate for each PRD feature slot."""
    av_set = set(available)
    chosen: list[str] = []
    for i, slot in enumerate(FEATURE_CANDIDATES):
        found = next((c for c in slot if c in av_set), None)
        if found:
            chosen.append(found)
            logger.debug("Feature slot %d: selected '%s'", i + 1, found)
        else:
            logger.warning("Feature slot %d: none of %s available", i + 1, slot)
    return chosen


def _expanding_zscore(s: pd.Series, min_obs: int = MIN_EXPANDING_OBS) -> pd.Series:
    """
    Z-score using strictly expanding window shifted by 1 period.
    Excludes the current value from its own baseline (PIT-clean).
    Note: _CS features are already cross-sectional z-scores; re-standardizing
    per-country in time converts "vs peers this month" to "vs this country's
    own history of its peer-ranking," which is what the HMM needs.
    """
    lagged = s.shift(1)
    mu = lagged.expanding(min_periods=min_obs).mean()
    sd = lagged.expanding(min_periods=min_obs).std()
    z = (s - mu) / sd
    return z.replace([np.inf, -np.inf], np.nan)


def build_country_feature_matrix(
    factor_panel: pd.DataFrame,
    features: list[str],
) -> dict[str, pd.DataFrame]:
    """
    For each T2 country:
      1. Pivot to (date × feature)
      2. Forward-fill single gaps (max 1 month) per feature
      3. Apply per-country expanding z-score
      4. Drop country-months where > 2 features are NaN
      5. Skip country if < 60 valid rows remain

    Returns {country -> DataFrame with date as index, feature columns}.
    """
    sub = factor_panel[factor_panel["factor"].isin(features)].copy()
    result: dict[str, pd.DataFrame] = {}

    for country in T2_COUNTRIES:
        csub = sub[sub["country"] == country]
        if csub.empty:
            logger.debug("%s: no data, skipping", country)
            continue

        piv = (csub
               .pivot_table(index="date", columns="factor", values="value")
               .sort_index()
               .reindex(columns=features))

        # Forward-fill single gaps
        piv = piv.ffill(limit=MAX_FFILL_MONTHS)

        # Per-country expanding z-score
        z_df = piv.apply(_expanding_zscore, axis=0)

        # Drop rows with > 2 missing features
        z_df = z_df[z_df.isna().sum(axis=1) <= 2]

        if len(z_df) < 60:
            logger.warning("%s: only %d valid rows after z-scoring, skipping", country, len(z_df))
            continue

        result[country] = z_df

    logger.info("Feature matrices built for %d / %d countries", len(result), len(T2_COUNTRIES))
    return result
