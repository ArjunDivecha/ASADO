"""
=============================================================================
SCRIPT NAME: regime_ew/src/gates.py
=============================================================================

DESCRIPTION:
    Gates 1–4 for the per-country regime EW test per the PRD §4.

    Gate 1: Persistence floor — states must be slow-moving enough to warn
    Gate 2: Vol-disguise check — flag if P_adverse is just a vol forecast
    Gate 3: Lead test — does signal(t) predict 1MRet(t) within country?
    Gate 4: Artifact checks — placebo shuffle + subsample stability (2013 split)

    Alignment convention (PRD §2 note):
      "signal at month t pairs with 1MRet@t directly (no extra shift)"
      1MRet@t is already the forward return (return earned during month t+1),
      so merging signal(t) with 1MRet(t) is a proper predictive test.

VERSION: 1.0
LAST UPDATED: 2026-06-21
AUTHOR: Arjun Divecha (built by agent session)
=============================================================================
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Gate 1 — Persistence
# ---------------------------------------------------------------------------

def per_country_persistence(signals: pd.DataFrame) -> pd.DataFrame:
    """
    Per-country weighted 1m persistence and mean adverse-state duration.
    'Adverse' is defined as P_adverse >= 0.5.
    """
    rows: list[dict] = []
    for country, g in signals.groupby("country"):
        g = g.sort_values("date")
        is_adv = (g["P_adverse"] >= 0.5).astype(int).values

        # 1-month persistence: fraction of consecutive months with same label
        persist_1m = float(np.mean(is_adv[1:] == is_adv[:-1])) if len(is_adv) > 1 else np.nan

        # Mean duration of adverse runs
        durations: list[int] = []
        i = 0
        while i < len(is_adv):
            if is_adv[i] == 1:
                j = i
                while j < len(is_adv) and is_adv[j] == 1:
                    j += 1
                durations.append(j - i)
                i = j
            else:
                i += 1
        mean_adv_dur = float(np.mean(durations)) if durations else np.nan

        rows.append({
            "country": country,
            "persist_1m": persist_1m,
            "mean_adv_duration_months": mean_adv_dur,
            "n_adverse_runs": len(durations),
            "n_months": len(g),
        })
    return pd.DataFrame(rows)


def gate1_check(persist_df: pd.DataFrame) -> tuple[bool, dict]:
    """
    PASS: median(persist_1m) >= 0.75 AND >= 60% of countries have
    mean adverse-state duration >= 3 months.
    """
    med = float(persist_df["persist_1m"].median())
    frac_3m = float((persist_df["mean_adv_duration_months"] >= 3).mean())
    passed = (med >= 0.75) and (frac_3m >= 0.60)
    tag = "PASS" if passed else "FAIL"
    logger.info("GATE 1 %s | median_persist=%.3f (≥0.75?) | frac_dur_3m=%.2f (≥0.60?)",
                tag, med, frac_3m)
    return passed, {
        "PASS": passed,
        "median_persist_1m": med,
        "frac_countries_mean_adv_duration_ge3m": frac_3m,
        "threshold_persist_1m": 0.75,
        "threshold_frac_duration": 0.60,
    }


# ---------------------------------------------------------------------------
# Gate 2 — Vol disguise
# ---------------------------------------------------------------------------

def gate2_check(signals: pd.DataFrame, returns_df: pd.DataFrame) -> tuple[bool, dict]:
    """
    Flag if median |Spearman(P_adverse, trailing_6m_vol)| > 0.70.
    Not an automatic fail — reframes the deliverable.
    """
    # Build trailing 6m vol per country from fwd_ret
    vol_rows: list[pd.DataFrame] = []
    for country, g in returns_df.groupby("country"):
        g = g.sort_values("date").copy()
        g["vol6m"] = g["fwd_ret"].rolling(6, min_periods=4).std()
        vol_rows.append(g[["date", "country", "vol6m"]])
    vol_df = pd.concat(vol_rows, ignore_index=True)

    merged = signals.merge(vol_df, on=["date", "country"], how="inner")

    corrs: list[float] = []
    for _, g in merged.groupby("country"):
        sub = g[["P_adverse", "vol6m"]].dropna()
        if len(sub) < 12:
            continue
        r, _ = stats.spearmanr(sub["P_adverse"], sub["vol6m"])
        corrs.append(abs(r))

    med_corr = float(np.median(corrs)) if corrs else np.nan
    is_vol_signal = bool(med_corr > 0.70)
    if is_vol_signal:
        logger.warning("GATE 2 FLAG: P_adverse ~ vol (|r|=%.2f > 0.70). "
                       "Signal may be a volatility forecast; Gate 3 interpretation changes.", med_corr)
    else:
        logger.info("GATE 2 OK | median |corr(P_adverse, vol6m)| = %.3f < 0.70", med_corr)
    return not is_vol_signal, {
        "IS_VOL_SIGNAL_FLAG": is_vol_signal,
        "median_abs_corr_P_adverse_vol6m": med_corr,
        "flag_threshold": 0.70,
        "n_countries": len(corrs),
    }


# ---------------------------------------------------------------------------
# Gate 3 — Signal leads own-country returns
# ---------------------------------------------------------------------------

def _within_country_corr(
    signals: pd.DataFrame,
    returns_df: pd.DataFrame,
    signal_col: str,
) -> pd.DataFrame:
    """
    Per-country Spearman(signal_col(t), fwd_ret(t)).
    PRD: signal(t) and 1MRet(t) are merged at the SAME date — no extra shift.
    """
    merged = (signals[["date", "country", signal_col]]
              .merge(returns_df[["date", "country", "fwd_ret"]], on=["date", "country"])
              .dropna(subset=[signal_col, "fwd_ret"]))

    rows: list[dict] = []
    for country, g in merged.groupby("country"):
        sub = g[[signal_col, "fwd_ret"]].dropna()
        if len(sub) < 12:
            continue
        rho, pval = stats.spearmanr(sub[signal_col], sub["fwd_ret"])
        rows.append({
            "country": country,
            "spearman_rho": float(rho),
            "spearman_pval": float(pval),
            "n_months": len(sub),
        })
    return pd.DataFrame(rows)


def _sign_test(corr_df: pd.DataFrame) -> dict:
    """Binomial test: how many countries show negative lead (P_adverse → low return)."""
    valid = corr_df.dropna(subset=["spearman_rho"])
    n_neg = int((valid["spearman_rho"] < 0).sum())
    n = len(valid)
    result = stats.binomtest(n_neg, n, 0.5, alternative="greater")
    return {
        "n_negative": n_neg,
        "n_total": n,
        "binom_pval": float(result.pvalue),
    }


def _economic_spread(signals: pd.DataFrame, returns_df: pd.DataFrame) -> float:
    """
    Within-country: mean(fwd_ret | P_adverse in bottom quartile)
                  - mean(fwd_ret | P_adverse in top quartile).
    Positive = low P_adverse months outperform high P_adverse months.
    """
    merged = (signals[["date", "country", "P_adverse"]]
              .merge(returns_df[["date", "country", "fwd_ret"]], on=["date", "country"]))
    spreads: list[float] = []
    for _, g in merged.groupby("country"):
        sub = g[["P_adverse", "fwd_ret"]].dropna()
        if len(sub) < 16:
            continue
        q25 = sub["P_adverse"].quantile(0.25)
        q75 = sub["P_adverse"].quantile(0.75)
        low = sub.loc[sub["P_adverse"] <= q25, "fwd_ret"].mean()
        high = sub.loc[sub["P_adverse"] >= q75, "fwd_ret"].mean()
        spreads.append(float(low - high))
    return float(np.mean(spreads)) if spreads else np.nan


def gate3_check(
    signals: pd.DataFrame,
    returns_df: pd.DataFrame,
) -> tuple[bool, dict, pd.DataFrame]:
    """
    Three conditions (all must hold):
    1. Sign test: ≥ 23 / n_countries negative, binomial p < 0.05
    2. Median per-country Spearman ≤ −0.10 on P_adverse or dP_adverse
    3. Economic spread ≥ 50 bp/month (0.50 in pct)
    """
    corr_P = _within_country_corr(signals, returns_df, "P_adverse")
    corr_dP = _within_country_corr(signals, returns_df, "dP_adverse")

    sign_P = _sign_test(corr_P)
    sign_dP = _sign_test(corr_dP)
    med_rho_P = float(corr_P["spearman_rho"].median())
    med_rho_dP = float(corr_dP["spearman_rho"].median())
    spread_pct = _economic_spread(signals, returns_df) * 100.0

    sign_ok = (sign_P["n_negative"] >= 23) and (sign_P["binom_pval"] < 0.05)
    rho_ok = (med_rho_P <= -0.10) or (med_rho_dP <= -0.10)
    spread_ok = (not np.isnan(spread_pct)) and (spread_pct >= 0.50)
    passed = sign_ok and rho_ok and spread_ok

    tag = "PASS" if passed else "FAIL"
    logger.info(
        "GATE 3 %s | sign=%d/%d p=%.4f | med_rho=P:%.3f dP:%.3f | spread=%.2f%%/mo",
        tag,
        sign_P["n_negative"], sign_P["n_total"], sign_P["binom_pval"],
        med_rho_P, med_rho_dP, spread_pct,
    )

    lead_df = corr_P.rename(columns={"spearman_rho": "rho_P", "spearman_pval": "pval_P"})
    corr_dP2 = corr_dP[["country", "spearman_rho", "spearman_pval"]].rename(
        columns={"spearman_rho": "rho_dP", "spearman_pval": "pval_dP"}
    )
    lead_df = lead_df.merge(corr_dP2, on="country", how="outer")

    metrics = {
        "PASS": passed,
        "sign_test_P_adverse": sign_P,
        "sign_test_dP_adverse": sign_dP,
        "median_rho_P_adverse_1MRet": med_rho_P,
        "median_rho_dP_adverse_1MRet": med_rho_dP,
        "economic_spread_pct_per_month": spread_pct,
        "condition_sign_ok": sign_ok,
        "condition_rho_ok": rho_ok,
        "condition_spread_ok": spread_ok,
    }
    return passed, metrics, lead_df


# ---------------------------------------------------------------------------
# Gate 4 — Artifact checks
# ---------------------------------------------------------------------------

def _gate4_placebo(
    signals: pd.DataFrame,
    returns_df: pd.DataFrame,
    seed: int = 42,
) -> dict:
    """
    Shuffle dates within each country, re-run Gate 3 sign test.
    Placebo 'passes' (null as expected) if shuffled sign test < 23 or p >= 0.05.
    """
    rng = np.random.default_rng(seed)
    shuffled_rows: list[pd.DataFrame] = []
    for country, g in signals.groupby("country"):
        g = g.copy()
        g["date"] = rng.permutation(g["date"].values)
        shuffled_rows.append(g)
    shuffled = pd.concat(shuffled_rows, ignore_index=True)

    corr_P = _within_country_corr(shuffled, returns_df, "P_adverse")
    sign_P = _sign_test(corr_P)
    placebo_null = (sign_P["n_negative"] < 23) or (sign_P["binom_pval"] >= 0.05)
    return {
        "n_correct_sign_shuffled": sign_P["n_negative"],
        "binom_pval_shuffled": sign_P["binom_pval"],
        "placebo_is_null": placebo_null,   # True = good
    }


def _gate4_subsample(
    signals: pd.DataFrame,
    returns_df: pd.DataFrame,
    split_date: str = "2013-01-01",
) -> dict:
    """
    Split at split_date. Sign of median Spearman must hold in both halves.
    Can weaken but must not flip.
    """
    split = pd.Timestamp(split_date)

    def _summary(sig_sub: pd.DataFrame) -> dict:
        if sig_sub.empty:
            return {"n_negative": 0, "n_total": 0, "binom_pval": np.nan, "median_rho": np.nan}
        corr = _within_country_corr(sig_sub, returns_df, "P_adverse").dropna(subset=["spearman_rho"])
        sign = _sign_test(corr)
        return {**sign, "median_rho": float(corr["spearman_rho"].median())}

    pre = _summary(signals[signals["date"] < split])
    post = _summary(signals[signals["date"] >= split])

    stable = (
        (not np.isnan(pre["median_rho"]) and pre["median_rho"] < 0)
        and (not np.isnan(post["median_rho"]) and post["median_rho"] < 0)
    )
    return {
        f"pre_{split.year}": pre,
        f"post_{split.year}": post,
        "subsample_stable": stable,
    }


def gate4_check(
    signals: pd.DataFrame,
    returns_df: pd.DataFrame,
) -> tuple[bool, dict]:
    """Gate 4: placebo null + subsample stability."""
    placebo = _gate4_placebo(signals, returns_df)
    subsample = _gate4_subsample(signals, returns_df)
    passed = placebo["placebo_is_null"] and subsample["subsample_stable"]
    tag = "PASS" if passed else "FAIL"
    logger.info("GATE 4 %s | placebo_null=%s | subsample_stable=%s",
                tag, placebo["placebo_is_null"], subsample["subsample_stable"])
    return passed, {
        "PASS": passed,
        "placebo": placebo,
        "subsample": subsample,
    }
