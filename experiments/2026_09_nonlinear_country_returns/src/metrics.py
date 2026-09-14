# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/src/metrics.py
#
# PRD 12.1/12.3 — per-origin metrics and paired primary inference, shared
# verbatim by the P07 control studies and the P08 real evaluation.
# =============================================================================
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from estimators import MASTER_SEED, moving_block_bootstrap, holm_adjust

EXP = Path(__file__).resolve().parents[1]
AUDIT = EXP / "audit"


def load_scored(axis_only: bool = False) -> pd.DataFrame:
    """Scored population: frozen eligible rows whose h20 outcome is MATURE
    and whose origin is at/after the first outer fit cutoff."""
    el = pd.read_parquet(AUDIT / "eligible_rows.parquet")
    os_ = pd.read_parquet(AUDIT / "outcome_status.parquet")
    lab = pd.read_parquet(AUDIT / "labels.parquet")
    for df in (el, os_, lab):
        df["origin_date"] = pd.to_datetime(df["origin_date"])
    os_ = os_[os_["horizon"] == "h20"]
    lab = lab[lab["horizon"] == "h20"]
    df = (el.drop(columns=["outcome_status"], errors="ignore")
            .merge(os_[["origin_date", "market", "outcome_status"]],
                   on=["origin_date", "market"])
            .merge(lab[["origin_date", "market", "label"]],
                   on=["origin_date", "market"]))
    whole = (df.groupby("origin_date")["outcome_status"]
             .transform(lambda s: (s == "MATURE").all()))
    df = df[whole]
    splits = json.loads((AUDIT / "splits.json").read_text())
    first_fit = pd.Timestamp(splits["outer_fits"][0]["fit_cutoff"])
    return df[df["origin_date"] >= first_fit]


def spearman_by_origin(df: pd.DataFrame, score: str) -> pd.Series:
    """Per-origin cross-market Spearman IC. Exactly constant forecast or
    constant outcome -> IC = 0 with flag (declared convention, T40)."""
    def one(g):
        x, y = g[score].to_numpy(), g["label"].to_numpy()
        if np.all(x == x[0]) or np.all(y == y[0]):
            return 0.0
        rx, ry = rankdata(x), rankdata(y)
        return float(np.corrcoef(rx, ry)[0, 1])
    if df.empty:
        return pd.Series(dtype=float)
    return df.groupby("origin_date").apply(one, include_groups=False)


def per_origin_mse(df: pd.DataFrame, score: str) -> pd.Series:
    def one(g):
        return float(np.mean((g["label"].to_numpy()
                              - g[score].to_numpy()) ** 2))
    if df.empty:
        return pd.Series(dtype=float)
    return df.groupby("origin_date").apply(one, include_groups=False)


def merge_forecasts(scored: pd.DataFrame, forecasts: pd.DataFrame,
                    streams: list[str]) -> pd.DataFrame:
    """Attach forecast columns; scores restricted to the scored population
    (same row set for every stream — T41)."""
    return scored.merge(
        forecasts[["origin_date", "market"] + streams],
        on=["origin_date", "market"], how="left")


def collect_forecasts(run_dir: Path, streams: list[str]) -> pd.DataFrame:
    parts = []
    for p in sorted(run_dir.glob("forecasts_*.parquet")):
        parts.append(pd.read_parquet(p))
    fc = pd.concat(parts, ignore_index=True)
    fc["origin_date"] = pd.to_datetime(fc["origin_date"])
    return fc


def origin_metric_table(scored: pd.DataFrame, forecasts: pd.DataFrame,
                        streams: list[str]) -> pd.DataFrame:
    df = merge_forecasts(scored, forecasts, streams)
    axis = np.sort(df["origin_date"].unique())
    tab = pd.DataFrame(index=axis)
    for m in streams:
        sub = df.dropna(subset=[m])
        covered = sub.groupby("origin_date").size()
        mse = per_origin_mse(sub, m).reindex(axis)
        ic = spearman_by_origin(sub, m).reindex(axis)
        tab[f"{m}_mse"] = mse
        tab[f"{m}_ic"] = ic
        tab[f"{m}_n"] = covered.reindex(axis).fillna(0).astype(int)
    return tab


def bootstrap_pvalue(d: np.ndarray, block: int = 63, draws: int = 5000,
                     seed: int = 0) -> float:
    """One-sided improvement test (PRD 12.3): center under the zero-mean
    null, MBB the mean, p = (1 + count(null >= obs))/(B+1)."""
    d = np.asarray(d, dtype=float)
    d = d[np.isfinite(d)]
    obs = float(np.mean(d))
    centered = d - obs
    draws_ = moving_block_bootstrap(centered, block=block, draws=draws,
                                    seed=seed)
    return float((1 + np.sum(draws_ >= obs)) / (draws + 1))


def bootstrap_ci(d: np.ndarray, block: int = 63, draws: int = 5000,
                 seed: int = 1, alpha: float = 0.05):
    """95% pointwise interval for the mean difference (labeled pointwise,
    not simultaneous)."""
    d = np.asarray(d, dtype=float)
    d = d[np.isfinite(d)]
    dist = moving_block_bootstrap(d, block=block, draws=draws, seed=seed)
    return (float(np.nanpercentile(dist, 100 * alpha / 2)),
            float(np.nanpercentile(dist, 100 * (1 - alpha / 2))))


def primary_tests(tab: pd.DataFrame, seed_base: int = MASTER_SEED):
    """The three registered primary comparisons. Returns per-test dict and
    Holm-adjusted p-values."""
    mse_x = (tab["L_X_mse"] - tab["N_S_mse"]).to_numpy()
    mse_s = (tab["L_S_mse"] - tab["N_S_mse"]).to_numpy()
    ic_ls = (tab["N_S_ic"] - tab["L_star_ic"]).to_numpy()
    tests = [
        {"name": "mse_gain_vs_L_X", "d": mse_x,
         "point": float(np.nanmean(mse_x)),
         "rel_gain": float(1 - np.nanmean(tab["N_S_mse"]) /
                           np.nanmean(tab["L_X_mse"]))},
        {"name": "mse_gain_vs_L_S", "d": mse_s,
         "point": float(np.nanmean(mse_s)),
         "rel_gain": float(1 - np.nanmean(tab["N_S_mse"]) /
                           np.nanmean(tab["L_S_mse"]))},
        {"name": "ic_gain_vs_L_star", "d": ic_ls,
         "point": float(np.nanmean(ic_ls)),
         "rel_gain": None},
    ]
    def fin(v):
        return v if (v is not None and np.isfinite(v)) else None
    raw_p = []
    for j, t in enumerate(tests):
        seed = seed_base + 900_000 + j
        if np.isfinite(t["d"]).sum() < 30:
            t["p_raw"], t["ci95"] = None, None
            raw_p.append(1.0)
        else:
            t["p_raw"] = bootstrap_pvalue(t["d"], seed=seed)
            t["ci95"] = bootstrap_ci(t["d"], seed=seed + 1)
            raw_p.append(t["p_raw"])
        t["point"] = fin(t["point"]); t["rel_gain"] = fin(t["rel_gain"])
        t.pop("d")
    adj = holm_adjust(raw_p)
    for t, p in zip(tests, adj):
        t["p_holm"] = p
    return tests
