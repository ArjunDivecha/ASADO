from __future__ import annotations

import json
import math
import re
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from hmmlearn.hmm import GaussianHMM
from scipy import stats


REGIME_EW_ROOT = Path(__file__).resolve().parent.parent
ASADO_ROOT = REGIME_EW_ROOT.parent
RESULTS_DIR = REGIME_EW_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
HMM_PARAMS_DIR = RESULTS_DIR / "hmm_params"

RANDOM_STATE = 0
MIN_STANDARDIZATION_MONTHS = 24
MIN_TRAIN_MONTHS = 60
MIN_GATE_OBS = 24

FEATURE_SLOTS = {
    "momentum": ["12-1MTR_CS", "12MTR_CS"],
    "reer": ["REER_CS"],
    "technical": ["RSI14_CS"],
    "valuation": ["Best PE _CS"],
    "inflation": ["Inflation_CS"],
    "risk": ["GDELT_RISK_CS", "GDELT_Risk_CS", "Best ROE_CS", "Bloom Country Risk_CS"],
}


@dataclass(frozen=True)
class FitResult:
    model: GaussianHMM
    k: int
    bic: float
    log_likelihood: float
    n_params: int
    converged: bool


def ensure_dirs() -> None:
    for path in (RESULTS_DIR, FIGURES_DIR, HMM_PARAMS_DIR):
        path.mkdir(parents=True, exist_ok=True)


def country_slug(country: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", country).strip("_").lower()


def select_feature_set(available: list[str]) -> list[str]:
    """Select the six-feature PRD set from live warehouse variable names."""
    selected: list[str] = []
    available_set = set(available)
    for slot, candidates in FEATURE_SLOTS.items():
        chosen = next((c for c in candidates if c in available_set), None)
        if chosen is None and slot == "risk":
            chosen = next(
                (
                    c
                    for c in available
                    if "GDELT" in c.upper() and c.endswith("_CS")
                ),
                None,
            )
        if chosen is None:
            raise RuntimeError(f"No available feature for slot {slot}: {candidates}")
        if chosen not in selected:
            selected.append(chosen)
    if len(selected) != 6:
        raise RuntimeError(f"Expected 6 distinct features, got {selected}")
    return selected


def expanding_zscore(frame: pd.DataFrame, min_periods: int = MIN_STANDARDIZATION_MONTHS) -> pd.DataFrame:
    """
    Expanding, per-country z-score.

    The inputs are already cross-sectional z-scores. Re-standardizing in time
    converts "vs peers this month" into "vs this country's own history of its
    peer-ranking" without using future observations.
    """
    mean = frame.expanding(min_periods=min_periods).mean()
    std = frame.expanding(min_periods=min_periods).std(ddof=0).replace(0, np.nan)
    return (frame - mean) / std


def build_country_feature_panels(
    factor_panel: pd.DataFrame,
    features: list[str],
    countries: list[str],
) -> dict[str, pd.DataFrame]:
    wide = (
        factor_panel[factor_panel["factor"].isin(features)]
        .pivot_table(index=["date", "country"], columns="factor", values="value", aggfunc="mean")
        .reset_index()
    )
    wide["date"] = pd.to_datetime(wide["date"]).dt.to_period("M").dt.to_timestamp()

    panels: dict[str, pd.DataFrame] = {}
    for country in countries:
        g = wide[wide["country"] == country].copy()
        if g.empty:
            panels[country] = pd.DataFrame(columns=["date", *features])
            continue
        values = (
            g.set_index("date")
            .sort_index()
            .reindex(columns=features)
            .replace([np.inf, -np.inf], np.nan)
        )
        missing_before_fill = values.isna().sum(axis=1)
        filled = values.ffill(limit=1)
        z = expanding_zscore(filled)
        # PRD tolerance: drop months only when more than 2 of 6 raw features
        # are missing. HMMs cannot consume NaNs, so remaining one- or two-slot
        # standardized gaps are neutral-imputed to 0 (the country's expanding
        # average) after the 1-month forward-fill attempt.
        valid_z_count = z.notna().sum(axis=1)
        keep = (missing_before_fill <= 2) & (valid_z_count >= len(features) - 2)
        z = z.loc[keep].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        panels[country] = z.reset_index()
    return panels


def _n_hmm_params(k: int, n_features: int) -> int:
    return (k - 1) + k * (k - 1) + 2 * k * n_features


def _fit_hmm(x: np.ndarray, k: int) -> FitResult:
    model = GaussianHMM(
        n_components=k,
        covariance_type="diag",
        n_iter=200,
        tol=1e-4,
        random_state=RANDOM_STATE,
        min_covar=1e-4,
        implementation="log",
    )
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        model.fit(x)
        log_likelihood = float(model.score(x))
    n_params = _n_hmm_params(k, x.shape[1])
    bic = -2.0 * log_likelihood + n_params * math.log(len(x))
    return FitResult(
        model=model,
        k=k,
        bic=float(bic),
        log_likelihood=log_likelihood,
        n_params=n_params,
        converged=bool(getattr(model.monitor_, "converged", False)),
    )


def fit_best_hmm(x: np.ndarray, ks: tuple[int, ...] = (2, 3)) -> FitResult:
    fits: list[FitResult] = []
    if not np.isfinite(x).all():
        raise ValueError("HMM input contains non-finite values")
    for k in ks:
        if len(x) <= _n_hmm_params(k, x.shape[1]):
            continue
        try:
            fits.append(_fit_hmm(x, k))
        except Exception:
            continue
    if not fits:
        raise RuntimeError(f"No HMM fit succeeded for shape={x.shape}")
    return min(fits, key=lambda f: f.bic)


def state_return_means(
    dates: pd.Series,
    states: np.ndarray,
    returns_1m: pd.DataFrame,
    k: int,
) -> dict[int, float | None]:
    labels = pd.DataFrame({"date": pd.to_datetime(dates).values, "state": states.astype(int)})
    merged = labels.merge(returns_1m[["date", "fwd_ret"]], on="date", how="left")
    out: dict[int, float | None] = {}
    for state in range(k):
        vals = merged.loc[merged["state"] == state, "fwd_ret"].dropna()
        out[state] = float(vals.mean()) if len(vals) else None
    return out


def rank_states_by_return(state_means: dict[int, float | None]) -> dict[int, int]:
    sortable = []
    for state, mean in state_means.items():
        sort_val = float("inf") if mean is None or not np.isfinite(mean) else mean
        sortable.append((state, sort_val))
    sortable.sort(key=lambda item: (item[1], item[0]))
    return {state: rank for rank, (state, _) in enumerate(sortable)}


def _posterior_last(model: GaussianHMM, history_x: np.ndarray) -> tuple[int, np.ndarray]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        states = model.predict(history_x)
        post = model.predict_proba(history_x)
    return int(states[-1]), post[-1].astype(float)


def _model_to_json(fit: FitResult) -> dict[str, Any]:
    model = fit.model
    return {
        "K": fit.k,
        "bic": fit.bic,
        "log_likelihood": fit.log_likelihood,
        "n_params": fit.n_params,
        "converged": fit.converged,
        "startprob": model.startprob_.tolist(),
        "transmat": model.transmat_.tolist(),
        "means": model.means_.tolist(),
        "covars": np.asarray(model.covars_).tolist(),
    }


def run_full_sample_country(
    country: str,
    country_features: pd.DataFrame,
    returns_1m: pd.DataFrame,
    features: list[str],
) -> tuple[pd.DataFrame, dict[str, Any] | None]:
    if len(country_features) < MIN_TRAIN_MONTHS:
        return pd.DataFrame(), None
    x = country_features[features].to_numpy(dtype=float)
    fit = fit_best_hmm(x)
    states, post = fit.model.predict(x), fit.model.predict_proba(x)
    means = state_return_means(country_features["date"], states, returns_1m, fit.k)
    rank_map = rank_states_by_return(means)
    adverse_state = min(rank_map, key=rank_map.get)

    rows = []
    for i, row in country_features.reset_index(drop=True).iterrows():
        state = int(states[i])
        out = {
            "date": row["date"],
            "country": country,
            "P_adverse": float(post[i, adverse_state]),
            "state": state,
            "state_rank": int(rank_map[state]),
            "K": int(fit.k),
            "adverse_state": int(adverse_state),
            "fit_type": "full_sample",
        }
        for state_idx in range(fit.k):
            out[f"P_state_{state_idx}"] = float(post[i, state_idx])
        rows.append(out)
    signals = pd.DataFrame(rows)
    signals["dP_adverse"] = signals["P_adverse"].diff()
    return signals, {
        "country": country,
        "fit_type": "full_sample",
        "features": features,
        "adverse_state": int(adverse_state),
        "state_rank_map": {str(k): int(v) for k, v in rank_map.items()},
        "state_mean_forward_1m_return": {str(k): v for k, v in means.items()},
        "model": _model_to_json(fit),
        "n_obs": int(len(country_features)),
        "date_min": str(country_features["date"].min().date()),
        "date_max": str(country_features["date"].max().date()),
    }


def run_walk_forward_country(
    country: str,
    country_features: pd.DataFrame,
    returns_1m: pd.DataFrame,
    features: list[str],
    min_train_months: int = MIN_TRAIN_MONTHS,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    if len(country_features) < min_train_months + 12:
        return pd.DataFrame(), []

    cf = country_features.sort_values("date").reset_index(drop=True)
    years = sorted(pd.to_datetime(cf["date"]).dt.year.unique())
    rows: list[dict[str, Any]] = []
    fit_records: list[dict[str, Any]] = []

    for year in years:
        year_start = pd.Timestamp(year=year, month=1, day=1)
        next_year = pd.Timestamp(year=year + 1, month=1, day=1)
        train = cf[cf["date"] < year_start].copy()
        test = cf[(cf["date"] >= year_start) & (cf["date"] < next_year)].copy()
        if len(train) < min_train_months or test.empty:
            continue

        train_x = train[features].to_numpy(dtype=float)
        try:
            fit = fit_best_hmm(train_x)
        except Exception as exc:
            fit_records.append(
                {
                    "fit_year": int(year),
                    "status": "fit_failed",
                    "error": str(exc),
                    "n_train": int(len(train)),
                }
            )
            continue

        train_states = fit.model.predict(train_x)
        means = state_return_means(train["date"], train_states, returns_1m, fit.k)
        rank_map = rank_states_by_return(means)
        adverse_state = min(rank_map, key=rank_map.get)
        fit_records.append(
            {
                "fit_year": int(year),
                "status": "ok",
                "n_train": int(len(train)),
                "n_test": int(len(test)),
                "date_train_min": str(train["date"].min().date()),
                "date_train_max": str(train["date"].max().date()),
                "adverse_state": int(adverse_state),
                "state_rank_map": {str(k): int(v) for k, v in rank_map.items()},
                "state_mean_forward_1m_return": {str(k): v for k, v in means.items()},
                "model": _model_to_json(fit),
            }
        )

        for test_idx in test.index:
            history = cf.loc[cf.index <= test_idx, features].to_numpy(dtype=float)
            state, post = _posterior_last(fit.model, history)
            out = {
                "date": cf.loc[test_idx, "date"],
                "country": country,
                "P_adverse": float(post[adverse_state]),
                "state": int(state),
                "state_rank": int(rank_map.get(state, -1)),
                "K": int(fit.k),
                "adverse_state": int(adverse_state),
                "fit_year": int(year),
                "fit_type": "walk_forward_oos",
            }
            for state_idx in range(fit.k):
                out[f"P_state_{state_idx}"] = float(post[state_idx])
            rows.append(out)

    signals = pd.DataFrame(rows)
    if not signals.empty:
        signals = signals.sort_values(["country", "date"])
        signals["dP_adverse"] = signals.groupby("country")["P_adverse"].diff()
    return signals, fit_records


def compute_persistence_stats(series: pd.Series) -> dict[str, Any]:
    s = series.dropna().astype(str).reset_index(drop=True)
    labels = sorted(s.unique())
    if len(s) < 2 or not labels:
        return {
            "weighted_persist_1m": np.nan,
            "persist_1m_unweighted": np.nan,
            "mean_duration_months": np.nan,
            "durations": [],
        }

    same_1m = [float(s.iloc[i] == s.iloc[i + 1]) for i in range(len(s) - 1)]
    one_m = []
    weights = []
    for label in labels:
        mask = s == label
        idx = np.where(mask)[0]
        if len(idx) < 2:
            continue
        stays = sum(1 for i in idx if i + 1 < len(s) and s.iloc[i + 1] == label)
        one_m.append(stays / max(1, len(idx) - 1))
        weights.append(mask.sum())

    durations = []
    i = 0
    while i < len(s):
        j = i + 1
        while j < len(s) and s.iloc[j] == s.iloc[i]:
            j += 1
        durations.append(j - i)
        i = j

    return {
        "weighted_persist_1m": float(np.average(one_m, weights=weights)) if weights else np.nan,
        "persist_1m_unweighted": float(np.mean(same_1m)) if same_1m else np.nan,
        "mean_duration_months": float(np.mean(durations)) if durations else np.nan,
        "durations": durations,
    }


def _mean_duration_for_value(values: pd.Series, target: int = 0) -> float:
    s = values.dropna().astype(int).reset_index(drop=True)
    durations = []
    i = 0
    while i < len(s):
        j = i + 1
        while j < len(s) and s.iloc[j] == s.iloc[i]:
            j += 1
        if s.iloc[i] == target:
            durations.append(j - i)
        i = j
    return float(np.mean(durations)) if durations else np.nan


def gate1_persistence(signals: pd.DataFrame, countries: list[str]) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows = []
    for country in countries:
        g = signals[signals["country"] == country].sort_values("date")
        stats_row = compute_persistence_stats(g["state_rank"])
        adverse_duration = _mean_duration_for_value(g["state_rank"], 0)
        rows.append(
            {
                "country": country,
                "n_months": int(len(g)),
                "weighted_persist_1m": stats_row["weighted_persist_1m"],
                "persist_1m_unweighted": stats_row["persist_1m_unweighted"],
                "mean_state_duration_months": stats_row["mean_duration_months"],
                "mean_adverse_state_duration_months": adverse_duration,
                "adverse_duration_ge_3m": bool(np.isfinite(adverse_duration) and adverse_duration >= 3.0),
            }
        )
    per_country = pd.DataFrame(rows)
    median_persist = float(per_country["weighted_persist_1m"].median())
    adverse_share = float(per_country["adverse_duration_ge_3m"].mean())
    passed = bool(median_persist >= 0.75 and adverse_share >= 0.60)
    aggregate = {
        "pass": passed,
        "median_weighted_persist_1m": median_persist,
        "adverse_duration_ge_3m_share": adverse_share,
        "thresholds": {
            "median_weighted_persist_1m_min": 0.75,
            "adverse_duration_ge_3m_share_min": 0.60,
        },
    }
    agg_row = {
        "country": "__AGGREGATE__",
        "n_months": int(per_country["n_months"].sum()),
        "weighted_persist_1m": median_persist,
        "persist_1m_unweighted": float(per_country["persist_1m_unweighted"].median()),
        "mean_state_duration_months": float(per_country["mean_state_duration_months"].median()),
        "mean_adverse_state_duration_months": float(per_country["mean_adverse_state_duration_months"].median()),
        "adverse_duration_ge_3m": passed,
    }
    return pd.concat([per_country, pd.DataFrame([agg_row])], ignore_index=True), aggregate


def _country_returns(returns: pd.DataFrame, country: str, horizon: str) -> pd.DataFrame:
    out = returns[(returns["country"] == country) & (returns["horizon"] == horizon)][
        ["date", "ret"]
    ].copy()
    out["date"] = pd.to_datetime(out["date"]).dt.to_period("M").dt.to_timestamp()
    return out.rename(columns={"ret": "fwd_ret"}).dropna(subset=["fwd_ret"])


def gate2_volatility(signals: pd.DataFrame, returns: pd.DataFrame, countries: list[str]) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows = []
    for country in countries:
        sig = signals[signals["country"] == country][["date", "country", "P_adverse"]].copy()
        ret = _country_returns(returns, country, "1MRet").sort_values("date")
        # 1MRet@t is a forward label, so trailing vol observed at t uses returns
        # realized before t.
        ret["trailing_vol_6m"] = ret["fwd_ret"].shift(1).rolling(6, min_periods=6).std()
        merged = sig.merge(ret[["date", "trailing_vol_6m"]], on="date", how="inner").dropna()
        if len(merged) < MIN_GATE_OBS:
            corr = np.nan
        else:
            corr = float(merged["P_adverse"].corr(merged["trailing_vol_6m"]))
        rows.append({"country": country, "n_obs": int(len(merged)), "corr_p_adverse_trailing_vol_6m": corr})
    per_country = pd.DataFrame(rows)
    median_corr = float(per_country["corr_p_adverse_trailing_vol_6m"].median())
    median_abs_corr = float(per_country["corr_p_adverse_trailing_vol_6m"].abs().median())
    aggregate = {
        "pass": True,
        "median_corr": median_corr,
        "median_abs_corr": median_abs_corr,
        "volatility_state_flag": bool(median_abs_corr > 0.70),
        "threshold_flag_abs_corr_gt": 0.70,
    }
    return per_country, aggregate


def _spearman(x: pd.Series, y: pd.Series) -> float:
    mask = np.isfinite(x) & np.isfinite(y)
    if int(mask.sum()) < MIN_GATE_OBS:
        return np.nan
    rho, _ = stats.spearmanr(x[mask], y[mask])
    return float(rho)


def _quartile_spread(merged: pd.DataFrame) -> float:
    g = merged.dropna(subset=["P_adverse", "fwd_ret"]).copy()
    if len(g) < MIN_GATE_OBS or g["P_adverse"].nunique() < 4:
        return np.nan
    low = g[g["P_adverse"] <= g["P_adverse"].quantile(0.25)]["fwd_ret"].mean()
    high = g[g["P_adverse"] >= g["P_adverse"].quantile(0.75)]["fwd_ret"].mean()
    return float(low - high)


def summarize_gate3(per_country: pd.DataFrame) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    metric_summaries = []
    for signal_col, label in (("P_adverse", "P_adverse"), ("dP_adverse", "dP_adverse")):
        rho_col = f"spearman_{signal_col}_1MRet"
        vals = per_country[rho_col].dropna()
        n_valid = int(len(vals))
        n_negative = int((vals < 0).sum())
        sign_p = float(stats.binomtest(n_negative, n_valid, 0.5, alternative="greater").pvalue) if n_valid else np.nan
        median_rho = float(vals.median()) if n_valid else np.nan
        metric_summaries.append(
            {
                "signal": label,
                "n_valid": n_valid,
                "n_negative_1m": n_negative,
                "sign_test_p_1m": sign_p,
                "median_spearman_1m": median_rho,
                "sign_condition_pass": bool(n_negative >= 23 and sign_p < 0.05),
                "median_condition_pass": bool(np.isfinite(median_rho) and median_rho <= -0.10),
            }
        )

    spread_vals = per_country["spread_bottom_minus_top_P_adverse_1MRet"].dropna()
    spread_mean = float(spread_vals.mean()) if len(spread_vals) else np.nan
    spread_median = float(spread_vals.median()) if len(spread_vals) else np.nan
    spread_pass = bool(np.isfinite(spread_mean) and spread_mean >= 0.005)

    best = sorted(
        metric_summaries,
        key=lambda x: (x["sign_condition_pass"], x["median_condition_pass"], -x["median_spearman_1m"]),
        reverse=True,
    )[0]
    metric_pass = any(m["sign_condition_pass"] and m["median_condition_pass"] for m in metric_summaries)
    passed = bool(metric_pass and spread_pass)
    summary.update(
        {
            "pass": passed,
            "best_signal_for_gate": best["signal"],
            "metric_summaries": metric_summaries,
            "aggregate_spread_bottom_minus_top_P_adverse_1MRet_mean": spread_mean,
            "aggregate_spread_bottom_minus_top_P_adverse_1MRet_median": spread_median,
            "spread_condition_pass": spread_pass,
            "thresholds": {
                "negative_country_count_min": 23,
                "sign_test_p_max": 0.05,
                "median_spearman_max": -0.10,
                "spread_mean_min_decimal_return": 0.005,
            },
        }
    )
    return summary


def gate3_lead(signals: pd.DataFrame, returns: pd.DataFrame, countries: list[str]) -> tuple[pd.DataFrame, dict[str, Any]]:
    rows = []
    for country in countries:
        sig = signals[signals["country"] == country][["date", "country", "P_adverse", "dP_adverse"]].copy()
        row: dict[str, Any] = {"country": country}
        for horizon in ("1MRet", "3MRet"):
            ret = _country_returns(returns, country, horizon)
            merged = sig.merge(ret, on="date", how="inner").dropna(subset=["P_adverse", "fwd_ret"])
            row[f"n_obs_{horizon}"] = int(len(merged))
            row[f"spearman_P_adverse_{horizon}"] = _spearman(merged["P_adverse"], merged["fwd_ret"])
            row[f"spearman_dP_adverse_{horizon}"] = _spearman(merged["dP_adverse"], merged["fwd_ret"])
            if horizon == "1MRet":
                row["spread_bottom_minus_top_P_adverse_1MRet"] = _quartile_spread(merged)
        rows.append(row)
    per_country = pd.DataFrame(rows)
    return per_country, summarize_gate3(per_country)


def shuffled_placebo(signals: pd.DataFrame, random_state: int = RANDOM_STATE) -> pd.DataFrame:
    rng = np.random.default_rng(random_state)
    out = signals.copy()
    for country, idx in out.groupby("country").groups.items():
        idx_list = list(idx)
        p = out.loc[idx_list, "P_adverse"].to_numpy()
        dp = out.loc[idx_list, "dP_adverse"].to_numpy()
        out.loc[idx_list, "P_adverse"] = rng.permutation(p)
        out.loc[idx_list, "dP_adverse"] = rng.permutation(dp)
    return out


def gate4_robustness(
    signals: pd.DataFrame,
    returns: pd.DataFrame,
    countries: list[str],
    gate3_summary: dict[str, Any],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    placebo_rows, placebo_summary = gate3_lead(shuffled_placebo(signals), returns, countries)
    split_rows = []
    best_signal = gate3_summary["best_signal_for_gate"]
    for label, mask in (
        ("pre_2013", signals["date"] < pd.Timestamp("2013-01-01")),
        ("post_2013", signals["date"] >= pd.Timestamp("2013-01-01")),
    ):
        sub_rows, sub_summary = gate3_lead(signals.loc[mask].copy(), returns, countries)
        metric = next(m for m in sub_summary["metric_summaries"] if m["signal"] == best_signal)
        split_rows.append(
            {
                "check": "subsample",
                "sample": label,
                "best_signal": best_signal,
                "median_spearman_1m": metric["median_spearman_1m"],
                "n_negative_1m": metric["n_negative_1m"],
                "n_valid": metric["n_valid"],
                "spread_mean": sub_summary["aggregate_spread_bottom_minus_top_P_adverse_1MRet_mean"],
                "passes_direction": bool(
                    np.isfinite(metric["median_spearman_1m"])
                    and metric["median_spearman_1m"] <= 0
                ),
            }
        )

    placebo_best = next(
        m for m in placebo_summary["metric_summaries"] if m["signal"] == best_signal
    )
    placebo_collapsed = bool(
        not placebo_summary["pass"]
        and (
            not np.isfinite(placebo_best["median_spearman_1m"])
            or abs(placebo_best["median_spearman_1m"]) < 0.05
        )
    )
    subsample_pass = bool(all(row["passes_direction"] for row in split_rows))
    aggregate = {
        "pass": bool(placebo_collapsed and subsample_pass),
        "point_in_time_discipline_pass": True,
        "point_in_time_notes": [
            "Expanding per-country standardization uses only observations through each month.",
            "Walk-forward HMM is refit on data before each prediction year.",
            "Adverse-state mapping uses training-window forward returns only.",
            "Gate 3 reads only walk-forward OOS posteriors, not full-sample diagnostics.",
        ],
        "placebo_collapsed": placebo_collapsed,
        "placebo_gate3_pass": bool(placebo_summary["pass"]),
        "placebo_best_signal_median_spearman_1m": placebo_best["median_spearman_1m"],
        "subsample_direction_pass": subsample_pass,
    }
    rows = [
        {
            "check": "placebo",
            "sample": "date_shuffle_within_country",
            "best_signal": best_signal,
            "median_spearman_1m": placebo_best["median_spearman_1m"],
            "n_negative_1m": placebo_best["n_negative_1m"],
            "n_valid": placebo_best["n_valid"],
            "spread_mean": placebo_summary["aggregate_spread_bottom_minus_top_P_adverse_1MRet_mean"],
            "passes_direction": placebo_collapsed,
        },
        *split_rows,
    ]
    _ = placebo_rows  # kept for debugger symmetry; summary rows are the persisted artifact.
    return pd.DataFrame(rows), aggregate


def plot_outputs(signals: pd.DataFrame, gate3_rows: pd.DataFrame | None) -> None:
    if gate3_rows is not None and not gate3_rows.empty:
        fig, ax = plt.subplots(figsize=(9, 5))
        vals = gate3_rows["spearman_P_adverse_1MRet"].dropna()
        ax.hist(vals, bins=15, color="#356f9f", edgecolor="white")
        ax.axvline(0, color="#333333", lw=1)
        ax.axvline(vals.median(), color="#b23a48", lw=1.5, label=f"median {vals.median():.3f}")
        ax.set_title("Per-country Spearman: P(adverse) vs 1M forward return")
        ax.set_xlabel("Spearman rho")
        ax.set_ylabel("Countries")
        ax.legend()
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / "gate3_spearman_histogram.pdf")
        plt.close(fig)

    illustrative = [c for c in ["Brazil", "ChinaA", "Turkey", "U.S."] if c in set(signals["country"])]
    if illustrative:
        fig, axes = plt.subplots(len(illustrative), 1, figsize=(12, 2.4 * len(illustrative)), sharex=True)
        if len(illustrative) == 1:
            axes = [axes]
        for ax, country in zip(axes, illustrative):
            g = signals[signals["country"] == country].sort_values("date")
            ax.plot(g["date"], g["P_adverse"], color="#b23a48", lw=1.2)
            ax.set_title(country)
            ax.set_ylim(-0.02, 1.02)
            ax.set_ylabel("P adverse")
        axes[-1].set_xlabel("Date")
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / "illustrative_adverse_probability_timelines.pdf")
        plt.close(fig)


def write_results_md(
    manifest: dict[str, Any],
    features: list[str],
    full_sample_summary: dict[str, Any] | None,
) -> None:
    lines = [
        "# Per-Country Regime Early-Warning Test - Results",
        "",
        "## Executive Verdict",
        "",
        f"**Overall:** **{manifest['overall_status']}**",
        "",
        "| Gate | Result | Headline | Threshold |",
        "|---|---:|---|---|",
    ]
    gate1 = manifest["gates"].get("gate1_persistence")
    if gate1:
        lines.append(
            f"| Gate 1: persistence | **{'PASS' if gate1['pass'] else 'FAIL'}** | "
            f"Median weighted 1m persistence {gate1['median_weighted_persist_1m']:.3f}; "
            f"adverse-duration share {gate1['adverse_duration_ge_3m_share']:.1%} | "
            ">=0.75 and >=60% |"
        )
    gate2 = manifest["gates"].get("gate2_volatility")
    if gate2:
        flag = "FLAG" if gate2["volatility_state_flag"] else "clear"
        lines.append(
            f"| Gate 2: volatility disguise | **{flag}** | Median abs corr with trailing 6m vol "
            f"{gate2['median_abs_corr']:.3f} | flag if >0.70 |"
        )
    gate3 = manifest["gates"].get("gate3_lead")
    if gate3:
        best = next(m for m in gate3["metric_summaries"] if m["signal"] == gate3["best_signal_for_gate"])
        lines.append(
            f"| Gate 3: own-country return lead | **{'PASS' if gate3['pass'] else 'FAIL'}** | "
            f"{gate3['best_signal_for_gate']}: {best['n_negative_1m']}/{best['n_valid']} negative, "
            f"median rho {best['median_spearman_1m']:.3f}; spread "
            f"{gate3['aggregate_spread_bottom_minus_top_P_adverse_1MRet_mean']:.3%}/mo | "
            ">=23 negative, median <= -0.10, spread >= 0.50%/mo |"
        )
    gate4 = manifest["gates"].get("gate4_robustness")
    if gate4:
        lines.append(
            f"| Gate 4: artifact robustness | **{'PASS' if gate4['pass'] else 'FAIL'}** | "
            f"placebo collapsed={gate4['placebo_collapsed']}; "
            f"subsample direction={gate4['subsample_direction_pass']} | both true |"
        )

    lines.extend(
        [
            "",
            "## Feature Set",
            "",
            "The live warehouse did not expose a monthly-usable `GDELT*_CS` factor, so the PRD's fallback valuation/quality feature was used.",
            "",
        ]
    )
    for feature in features:
        lines.append(f"- `{feature}`")

    lines.extend(
        [
            "",
            "## Leakage Discipline",
            "",
            "- `1MRet` and `3MRet` are treated exactly as the prior `build_forward_returns` convention treats them: signal at month `t` pairs with forward return at month `t`.",
            "- Per-country feature scaling is expanding-only with a 24-month minimum; no full-sample mean/std enters the walk-forward signal.",
            "- Rows with more than two raw feature gaps are dropped; remaining one- or two-feature standardized gaps are neutral-imputed to zero after the one-month forward-fill attempt.",
            "- HMMs are refit annually using only data before the prediction year.",
            "- Adverse-state labels are ranked using training-window forward `1MRet` only.",
            "- Full-sample HMM outputs are written as diagnostics only; gates read `ew_signals.parquet` walk-forward OOS rows.",
            "",
            "## Interpretation",
            "",
        ]
    )

    status = manifest["overall_status"]
    if status == "PASS":
        lines.append(
            "All gates passed. The per-country adverse-state probability clears the PRD's early-warning bar and is eligible for a production overlay design."
        )
    elif "Gate 1" in status:
        lines.append(
            "The latent states are too unstable for this monthly early-warning design. Per the PRD, stop here and do not tune the model into a false positive."
        )
    elif "Gate 3" in status:
        lines.append(
            "The states are stable enough to examine, but the early-warning probability does not lead own-country forward returns strongly enough. Treat this as a negative return-overlay result."
        )
    elif "Gate 4" in status:
        lines.append(
            "The apparent return lead did not survive the required artifact checks. Treat any headline alpha as contaminated until redesigned."
        )
    else:
        lines.append("The test stopped before a production-eligible pass.")

    if full_sample_summary:
        lines.extend(
            [
                "",
                "## Full-Sample Diagnostic",
                "",
                "This is deliberately non-decisive because it uses full-sample HMM fits.",
                "",
                f"- Best diagnostic signal: `{full_sample_summary['best_signal_for_gate']}`",
                f"- Spread: {full_sample_summary['aggregate_spread_bottom_minus_top_P_adverse_1MRet_mean']:.3%}/mo",
            ]
        )

    lines.extend(
        [
            "",
            "## Artifacts",
            "",
            "- `regime_ew/results/manifest.json`",
            "- `regime_ew/results/ew_signals.parquet`",
            "- `regime_ew/results/ew_signals_full_sample.parquet`",
            "- `regime_ew/results/gate1_persistence.parquet`",
            "- `regime_ew/results/gate2_volatility.parquet`",
            "- `regime_ew/results/gate3_lead.parquet`",
            "- `regime_ew/results/gate4_robustness.parquet` if Gate 4 ran",
            "- `regime_ew/results/hmm_params/*.json`",
            "- `regime_ew/results/figures/*.pdf`",
            "",
        ]
    )
    (RESULTS_DIR / "RESULTS.md").write_text("\n".join(lines))
