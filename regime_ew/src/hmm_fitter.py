"""
=============================================================================
SCRIPT NAME: regime_ew/src/hmm_fitter.py
=============================================================================

DESCRIPTION:
    Per-country Gaussian HMM fitting (hmmlearn) with BIC-based K selection
    (K ∈ {2, 3}), adverse-state identification, and walk-forward expanding-
    window OOS posterior computation per the PRD §3.

    Walk-forward logic:
      - Min training window: 60 months
      - Annual refit (every 12 months)
      - OOS posteriors are batch-predicted per refit window (smoothed within window)
      - Adverse state labeled from training data only (PIT-clean)
      - Adverse = state with lowest mean contemporaneous return in training window
        (contemp return = 1MRet shifted 1 period: return DURING month t, not t+1)

    Full-sample mode (--full-sample-only flag in orchestrator):
      - Fits on all data, returns smoothed posteriors over full history
      - Adverse state labeled on full data
      - Gate 3/4 results from full-sample are diagnostic only (in-sample)

VERSION: 1.0
LAST UPDATED: 2026-06-21
AUTHOR: Arjun Divecha (built by agent session)
=============================================================================
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

EW_ROOT = Path(__file__).resolve().parents[1]   # regime_ew/
HMM_PARAMS_DIR = EW_ROOT / "results" / "hmm_params"

MIN_TRAIN_MONTHS = 60
REFIT_FREQ = 12          # annual refit
K_CANDIDATES = [2, 3]
HMM_SEED = 0
HMM_N_ITER = 200


# ---------------------------------------------------------------------------
# BIC calculation
# ---------------------------------------------------------------------------

def _n_params(k: int, d: int) -> int:
    """Free params for GaussianHMM(diag) with k states and d features."""
    # k*d means + k*d diag variances + k*(k-1) transition probs + (k-1) init probs
    return 2 * k * d + k * (k - 1) + (k - 1)


def _bic(model, X: np.ndarray) -> float:
    n, d = X.shape
    k = model.n_components
    log_lik_total = model.score(X) * n   # score() is per-sample log-prob
    return -2 * log_lik_total + _n_params(k, d) * np.log(n)


# ---------------------------------------------------------------------------
# Fitting helpers
# ---------------------------------------------------------------------------

def _fit_single(X: np.ndarray, k: int) -> object:
    """Fit GaussianHMM; raises on failure."""
    from hmmlearn import hmm
    model = hmm.GaussianHMM(
        n_components=k,
        covariance_type="diag",
        n_iter=HMM_N_ITER,
        random_state=HMM_SEED,
        tol=1e-4,
    )
    model.fit(X)
    return model


def _select_k(X: np.ndarray) -> tuple:
    """Fit K ∈ {2,3}, pick by BIC. Returns (model, k, bic_dict)."""
    best_bic = np.inf
    best_model = None
    best_k = None
    bic_dict: dict[int, float] = {}

    for k in K_CANDIDATES:
        if X.shape[0] < k * 5:   # need meaningful obs per state
            continue
        try:
            m = _fit_single(X, k)
            b = _bic(m, X)
        except Exception as exc:
            logger.debug("K=%d fit failed: %s", k, exc)
            continue
        bic_dict[k] = b
        if b < best_bic:
            best_bic = b
            best_model = m
            best_k = k

    return best_model, best_k, bic_dict


def _clean_X(feat_df: pd.DataFrame, slice_end: int | None = None) -> tuple:
    """
    Return (X_clean, dates_clean) for HMM fitting.
    Drops rows where ALL features are NaN (completely empty months).
    Fills residual NaN values with 0 (valid because features are already z-scored,
    so 0 = cross-sectional mean — neutral imputation for 1-2 missing features
    that passed the ≤2-NaN filter in feature_builder).
    """
    df = feat_df.iloc[:slice_end] if slice_end is not None else feat_df
    X = df.values.astype(float)
    # Drop only fully-empty rows (all features NaN)
    valid = ~np.all(np.isnan(X), axis=1)
    X = X[valid]
    dates = df.index[valid]
    # Zero-fill remaining NaNs (neutral imputation for ≤2 missing features per row)
    X = np.where(np.isfinite(X), X, 0.0)
    return X, dates


# ---------------------------------------------------------------------------
# Adverse-state identification
# ---------------------------------------------------------------------------

def _identify_adverse_state(
    model,
    X_train: np.ndarray,
    dates_train: pd.DatetimeIndex,
    country_fwd_returns: pd.Series,
) -> int:
    """
    Label adverse state as the one with the lowest mean *contemporaneous*
    return in the training window.

    Contemporaneous return at date t = return EARNED DURING month t.
    In t2_master convention: 1MRet@t = return during t+1 (forward).
    So contemporaneous return during t = 1MRet@(t-1) = fwd_returns.shift(1).

    This avoids circularity with Gate 3, which tests P_adverse(t) vs 1MRet@t.
    """
    contemp = country_fwd_returns.shift(1)   # contemporaneous during month t
    posteriors = model.predict_proba(X_train)
    state_seq = posteriors.argmax(axis=1)

    state_mean: dict[int, float] = {}
    for s in range(model.n_components):
        state_dates = dates_train[state_seq == s]
        rets = contemp.reindex(state_dates).dropna()
        state_mean[s] = float(rets.mean()) if len(rets) >= 3 else np.nan

    valid = {s: v for s, v in state_mean.items() if not np.isnan(v)}
    if not valid:
        return 0
    return min(valid, key=valid.__getitem__)


# ---------------------------------------------------------------------------
# Walk-forward OOS posteriors
# ---------------------------------------------------------------------------

def walk_forward_posteriors(
    feat_matrix: pd.DataFrame,
    country_fwd_returns: pd.Series,
    country: str,
) -> pd.DataFrame:
    """
    Expanding-window annual refit walk-forward.
    Returns OOS-only DataFrame: date, country, P_adverse, dP_adverse, state, K.
    """
    feat_matrix = feat_matrix.sort_index()
    n = len(feat_matrix)

    if n < MIN_TRAIN_MONTHS + 1:
        logger.warning("%s: %d rows < min %d, skip", country, n, MIN_TRAIN_MONTHS + 1)
        return pd.DataFrame()

    oos_rows: list[dict] = []
    cutoffs = list(range(MIN_TRAIN_MONTHS - 1, n - 1, REFIT_FREQ))

    for ci in cutoffs:
        X_train, dates_train = _clean_X(feat_matrix, ci + 1)
        if len(X_train) < MIN_TRAIN_MONTHS:
            continue

        model, k, bic_d = _select_k(X_train)
        if model is None:
            logger.warning("%s: HMM fit failed at cutoff %d, skipping window", country, ci)
            continue

        adv_state = _identify_adverse_state(model, X_train, dates_train, country_fwd_returns)

        # OOS window: next REFIT_FREQ months
        oos_start = ci + 1
        oos_end = min(oos_start + REFIT_FREQ, n)
        X_oos_full = feat_matrix.iloc[oos_start:oos_end].values.astype(float)
        oos_dates = feat_matrix.index[oos_start:oos_end]

        valid_mask = np.isfinite(X_oos_full).all(axis=1)
        X_oos = X_oos_full[valid_mask]
        oos_dates_clean = oos_dates[valid_mask]

        if len(X_oos) == 0:
            continue

        try:
            posteriors = model.predict_proba(X_oos)  # (n_oos, k) — smoothed within window
        except Exception as exc:
            logger.warning("%s: predict_proba failed at cutoff %d: %s", country, ci, exc)
            continue

        for i, dt in enumerate(oos_dates_clean):
            oos_rows.append({
                "date": dt,
                "country": country,
                "P_adverse": float(posteriors[i, adv_state]),
                "state": int(posteriors[i].argmax()),
                "K": k,
            })

        # Save params from this fit (last successful write wins)
        _save_params(country, k, bic_d, adv_state, {})

    if not oos_rows:
        return pd.DataFrame()

    df = pd.DataFrame(oos_rows).sort_values("date").reset_index(drop=True)
    df["dP_adverse"] = df["P_adverse"].diff()
    df.loc[df.index[0], "dP_adverse"] = np.nan

    logger.info("%s: %d OOS months", country, len(df))
    return df


# ---------------------------------------------------------------------------
# Full-sample mode (diagnostic only — --full-sample-only flag)
# ---------------------------------------------------------------------------

def full_sample_posteriors(
    feat_matrix: pd.DataFrame,
    country_fwd_returns: pd.Series,
    country: str,
) -> pd.DataFrame:
    """
    Fit on all available data. Returns smoothed posteriors over full history.
    Diagnostic only — in-sample, not used for Gate 3/4.
    """
    feat_matrix = feat_matrix.sort_index()
    X, dates = _clean_X(feat_matrix)

    if len(X) < MIN_TRAIN_MONTHS:
        logger.warning("%s: only %d clean rows, skip", country, len(X))
        return pd.DataFrame()

    model, k, bic_d = _select_k(X)
    if model is None:
        logger.warning("%s: HMM fit failed (full-sample)", country)
        return pd.DataFrame()

    adv_state = _identify_adverse_state(model, X, dates, country_fwd_returns)

    try:
        posteriors = model.predict_proba(X)
    except Exception as exc:
        logger.warning("%s: predict_proba failed (full-sample): %s", country, exc)
        return pd.DataFrame()

    df = pd.DataFrame({
        "date": dates,
        "country": country,
        "P_adverse": posteriors[:, adv_state].astype(float),
        "state": posteriors.argmax(axis=1),
        "K": k,
    }).sort_values("date").reset_index(drop=True)
    df["dP_adverse"] = df["P_adverse"].diff()
    df.loc[df.index[0], "dP_adverse"] = np.nan

    _save_params(country, k, bic_d, adv_state, {})
    return df


# ---------------------------------------------------------------------------
# Persist fitted params
# ---------------------------------------------------------------------------

def _save_params(country: str, k: int, bic_d: dict, adv_state: int, extras: dict) -> None:
    HMM_PARAMS_DIR.mkdir(parents=True, exist_ok=True)
    out = {
        "country": country,
        "K_selected": k,
        "BIC": {str(kk): round(float(v), 2) for kk, v in bic_d.items()},
        "adverse_state_index": adv_state,
        **extras,
    }
    path = HMM_PARAMS_DIR / f"{country.replace(' ', '_').replace('.', '')}.json"
    path.write_text(json.dumps(out, indent=2))
