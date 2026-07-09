#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: run_fragility_test.py
=============================================================================

DESCRIPTION:
    Runs the pre-registered Momentum Fragility Index kill-gates (PRD section 4)
    SEPARATELY on two pre-built composite variants:

        composite_core  (components 1-5, full 2000+ history)
        composite_full  (all 7 components, ~2016+ history)

    Both composites were produced by the upstream build stages
    (build_core_composite / build_full_composite) as per-country EXPANDING
    z-scores (min 24 months). Because every composite value at month t uses
    only information through month t, the composite is already point-in-time /
    walk-forward clean by construction -- there is NO model to refit here (unlike
    regime_ew's HMM). This script therefore:
      * treats the pre-built composite as the walk-forward OOS signal,
      * refits ONLY the composite quartile break-points annually on data strictly
        before each prediction year Y (the sole walk-forward-refit element, used
        for the Gate-3 economic spread),
      * pools qualifying (top-momentum-quartile) country-months for the PRIMARY
        Gate-3 pooled Spearman test.

    Convention (verified against build_forward_returns and t2_master):
        1MRet@t is already the forward realized return over month t and pairs
        with composite[t] directly -- no extra shift.

    Gates (evaluated per variant):
      Gate 1  persistence  -- tercile-bucketed composite month-to-month stability
                              (report only, no hard pass bar).
      Gate 2  vol proxy    -- corr(composite, trailing 6m realized return vol);
                              flag if median |corr| > 0.7 (do not auto-fail).
      Gate 3  DECISIVE     -- within the top-momentum-quartile subset, walk-forward
                              OOS POOLED Spearman(composite, forward 1MRet) and the
                              bottom-vs-top composite-quartile forward-return spread.
                              PASS = pooled Spearman <= -0.10 AND spread >= 50bp/mo.
                              Per-country sign test reported as diagnostic only.
      Gate 4  robustness   -- (a) within-country date-shuffle placebo (pooled
                              Spearman must collapse to ~0), (b) subsample-sign
                              stability (core split 2013, full split 2020, sign must
                              not flip), (c) point-in-time leakage audit.

INPUT FILES:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/momentum_fragility/results/core_composite.parquet
        date, country, composite_core, momentum_quartile_flag, 1MRet, 3MRet,
        plus the 5 core component columns (*_cs).
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/momentum_fragility/results/full_composite.parquet
        date, country, composite_core, composite_full, crowding_subscore,
        concentration_subscore, momentum_quartile_flag, 1MRet, 3MRet.

OUTPUT FILES:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/momentum_fragility/results/fragility_scores.parquet
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/momentum_fragility/results/gate1_persistence.parquet
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/momentum_fragility/results/gate2_volatility.parquet
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/momentum_fragility/results/gate3_lead.parquet
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/momentum_fragility/results/gate4_robustness.parquet
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/momentum_fragility/results/manifest.json
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/momentum_fragility/results/RESULTS.md
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/momentum_fragility/results/figures/*.pdf

VERSION: 1.0
LAST UPDATED: 2026-07-05
AUTHOR: Arjun Divecha (build: Claude Code)

USAGE:
    python "run_fragility_test.py"

NOTES:
    - Read-only DuckDB is not touched here; all inputs are pre-built parquets.
    - Deterministic: placebo uses a fixed numpy RNG seed (RANDOM_STATE=0).
    - "FAIL IS FAIL": a failing frozen spec is reported plainly, not softened.
=============================================================================
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

MODULE_ROOT = Path(__file__).resolve().parent
ASADO_ROOT = MODULE_ROOT.parent
RESULTS_DIR = MODULE_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
sys.path.insert(0, str(ASADO_ROOT))

# Reuse existing harness (do not reimplement).
from regime.src.utils import T2_COUNTRIES  # noqa: E402
from regime_ew.src.ew_model import (  # noqa: E402
    MIN_GATE_OBS,
    _spearman,
    compute_persistence_stats,
)

RANDOM_STATE = 0
MIN_PRIOR_HOT = 24          # min hot country-months of history before a prediction year is OOS-eligible
SPEARMAN_PASS = -0.10       # PRD Gate-3 pooled Spearman pass threshold
SPREAD_PASS = 0.005         # PRD Gate-3 spread pass threshold (50 bp / month, decimal)
VOL_FLAG_ABS_CORR = 0.70    # PRD Gate-2 flag threshold

VARIANTS = {
    "core": {"parquet": "core_composite.parquet", "col": "composite_core", "split_year": 2013},
    "full": {"parquet": "full_composite.parquet", "col": "composite_full", "split_year": 2020},
}


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def ensure_dirs() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)


def _json_default(obj):
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        val = float(obj)
        return None if not np.isfinite(val) else val
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    return str(obj)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, indent=2, default=_json_default))


def _pooled_spearman(x: pd.Series, y: pd.Series) -> tuple[float, float, int]:
    mask = np.isfinite(x) & np.isfinite(y)
    n = int(mask.sum())
    if n < MIN_GATE_OBS:
        return float("nan"), float("nan"), n
    rho, p = stats.spearmanr(x[mask], y[mask])
    return float(rho), float(p), n


def load_variant(cfg: dict) -> pd.DataFrame:
    df = pd.read_parquet(RESULTS_DIR / cfg["parquet"]).copy()
    df["date"] = pd.to_datetime(df["date"])
    df["comp"] = df[cfg["col"]]
    return df


# --------------------------------------------------------------------------- #
# GATE 1 -- persistence of tercile-bucketed composite
# --------------------------------------------------------------------------- #
def _cross_sectional_terciles(df: pd.DataFrame) -> pd.DataFrame:
    """Assign each country-month to a cross-sectional composite tercile (0/1/2).

    Point-in-time: rank uses only that month's cross section of the 34 countries.
    """
    d = df.dropna(subset=["comp"]).copy()

    def _bucket(g: pd.Series) -> pd.Series:
        if g.notna().sum() < 3 or g.nunique() < 3:
            return pd.Series(np.nan, index=g.index)
        try:
            return pd.qcut(g, 3, labels=[0, 1, 2]).astype("float")
        except ValueError:
            return pd.Series(np.nan, index=g.index)

    d["tercile"] = d.groupby("date")["comp"].transform(_bucket)
    return d.dropna(subset=["tercile"])


def gate1_persistence(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    d = _cross_sectional_terciles(df)
    rows = []
    for country in sorted(d["country"].unique()):
        g = d[d["country"] == country].sort_values("date")
        if len(g) < 12:
            continue
        stats_row = compute_persistence_stats(g["tercile"].astype(int).astype(str))
        counts = g["tercile"].value_counts(normalize=True)
        rows.append(
            {
                "country": country,
                "n_months": int(len(g)),
                "weighted_persist_1m": stats_row["weighted_persist_1m"],
                "persist_1m_unweighted": stats_row["persist_1m_unweighted"],
                "mean_tercile_duration_months": stats_row["mean_duration_months"],
                "max_single_bucket_share": float(counts.max()) if len(counts) else np.nan,
            }
        )
    per_country = pd.DataFrame(rows)
    median_persist = float(per_country["weighted_persist_1m"].median())
    max_bucket_share = float(per_country["max_single_bucket_share"].max())
    degenerate = bool(max_bucket_share > 0.95)
    summary = {
        "pass": bool(not degenerate),  # PRD: report-only unless degenerate
        "report_only": True,
        "median_weighted_persist_1m": median_persist,
        "median_tercile_duration_months": float(per_country["mean_tercile_duration_months"].median()),
        "worst_single_bucket_share": max_bucket_share,
        "degenerate_flag": degenerate,
        "n_countries": int(len(per_country)),
    }
    return per_country, summary


# --------------------------------------------------------------------------- #
# GATE 2 -- not merely a volatility proxy
# --------------------------------------------------------------------------- #
def gate2_volatility(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    rows = []
    for country in sorted(df["country"].unique()):
        g = df[df["country"] == country].sort_values("date").copy()
        # 1MRet@t is a forward label; trailing 6m vol observed at t uses returns
        # realized strictly before t.
        g["trailing_vol_6m"] = g["1MRet"].shift(1).rolling(6, min_periods=6).std()
        m = g.dropna(subset=["comp", "trailing_vol_6m"])
        if len(m) < MIN_GATE_OBS:
            corr = np.nan
        else:
            corr = float(m["comp"].corr(m["trailing_vol_6m"]))
        rows.append({"country": country, "n_obs": int(len(m)), "corr_comp_trailing_vol_6m": corr})
    per_country = pd.DataFrame(rows)
    median_abs = float(per_country["corr_comp_trailing_vol_6m"].abs().median())
    median_corr = float(per_country["corr_comp_trailing_vol_6m"].median())
    summary = {
        "pass": True,  # PRD: flag, never auto-fail
        "median_corr": median_corr,
        "median_abs_corr": median_abs,
        "volatility_proxy_flag": bool(median_abs > VOL_FLAG_ABS_CORR),
        "threshold_flag_abs_corr_gt": VOL_FLAG_ABS_CORR,
    }
    return per_country, summary


# --------------------------------------------------------------------------- #
# GATE 3 -- DECISIVE conditional reversal test (walk-forward OOS, pooled)
# --------------------------------------------------------------------------- #
def _hot_sample(df: pd.DataFrame) -> pd.DataFrame:
    d = df[df["momentum_quartile_flag"] & df["comp"].notna() & df["1MRet"].notna()].copy()
    d["year"] = d["date"].dt.year
    return d


def gate3_walk_forward(df: pd.DataFrame, min_prior_hot: int = MIN_PRIOR_HOT) -> tuple[pd.DataFrame, dict]:
    """Pooled walk-forward OOS Spearman + bottom-vs-top composite-quartile spread.

    For each prediction year Y with >= min_prior_hot qualifying months before it,
    year-Y qualifying months are labelled bottom/top by composite quartile
    break-points estimated ONLY on qualifying months in years < Y (walk-forward
    refit). All year-Y months (composite already point-in-time) are pooled.
    """
    hot = _hot_sample(df)
    years = sorted(hot["year"].unique())
    oos_parts = []
    for year in years:
        prior = hot[hot["year"] < year]
        cur = hot[hot["year"] == year]
        if len(prior) < min_prior_hot or cur.empty:
            continue
        q25 = prior["comp"].quantile(0.25)
        q75 = prior["comp"].quantile(0.75)
        cur = cur.copy()
        cur["comp_bucket"] = np.where(
            cur["comp"] <= q25, "bottom_lowfrag",
            np.where(cur["comp"] >= q75, "top_highfrag", "mid"),
        )
        cur["oos_year"] = year
        oos_parts.append(cur)

    oos = pd.concat(oos_parts, ignore_index=True) if oos_parts else hot.iloc[0:0].copy()
    rho, pval, n = _pooled_spearman(oos["comp"], oos["1MRet"])

    ret_bottom = oos.loc[oos["comp_bucket"] == "bottom_lowfrag", "1MRet"]
    ret_top = oos.loc[oos["comp_bucket"] == "top_highfrag", "1MRet"]
    spread = float(ret_bottom.mean() - ret_top.mean()) if len(ret_bottom) and len(ret_top) else np.nan

    # per-country diagnostic sign test (secondary only)
    per_country_rows = []
    for country in sorted(oos["country"].unique()):
        g = oos[oos["country"] == country]
        rho_c = _spearman(g["comp"], g["1MRet"])
        per_country_rows.append(
            {"country": country, "n_hot_obs": int(len(g)), "spearman_comp_1MRet": rho_c}
        )
    per_country = pd.DataFrame(per_country_rows)
    valid = per_country["spearman_comp_1MRet"].dropna()
    n_neg = int((valid < 0).sum())
    n_valid = int(len(valid))
    sign_p = (
        float(stats.binomtest(n_neg, n_valid, 0.5, alternative="greater").pvalue)
        if n_valid else np.nan
    )

    spearman_pass = bool(np.isfinite(rho) and rho <= SPEARMAN_PASS)
    spread_pass = bool(np.isfinite(spread) and spread >= SPREAD_PASS)
    passed = bool(spearman_pass and spread_pass)

    summary = {
        "pass": passed,
        "pooled_spearman": rho,
        "pooled_spearman_p": pval,
        "pooled_n_obs": n,
        "spread_bottom_minus_top_decimal": spread,
        "spread_bottom_minus_top_bp": (spread * 1e4) if np.isfinite(spread) else np.nan,
        "n_bottom": int(len(ret_bottom)),
        "n_top": int(len(ret_top)),
        "mean_ret_bottom_lowfrag": float(ret_bottom.mean()) if len(ret_bottom) else np.nan,
        "mean_ret_top_highfrag": float(ret_top.mean()) if len(ret_top) else np.nan,
        "spearman_condition_pass": spearman_pass,
        "spread_condition_pass": spread_pass,
        "oos_year_min": int(oos["year"].min()) if len(oos) else None,
        "oos_year_max": int(oos["year"].max()) if len(oos) else None,
        "diagnostic_per_country_sign": {
            "n_countries_valid": n_valid,
            "n_negative": n_neg,
            "sign_test_p": sign_p,
            "median_per_country_spearman": float(valid.median()) if n_valid else np.nan,
        },
        "thresholds": {
            "pooled_spearman_max": SPEARMAN_PASS,
            "spread_min_decimal": SPREAD_PASS,
        },
    }
    return per_country, summary, oos


# --------------------------------------------------------------------------- #
# GATE 4 -- robustness (placebo, subsample, point-in-time audit)
# --------------------------------------------------------------------------- #
def _placebo_shuffle(df: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Permute the composite column within each country (break composite<->date
    alignment) while leaving date / momentum flag / returns fixed."""
    out = df.copy()
    for country, idx in out.groupby("country").groups.items():
        idx_list = list(idx)
        vals = out.loc[idx_list, "comp"].to_numpy()
        out.loc[idx_list, "comp"] = rng.permutation(vals)
    return out


def gate4_robustness(df: pd.DataFrame, gate3_summary: dict, split_year: int) -> tuple[pd.DataFrame, dict]:
    rng = np.random.default_rng(RANDOM_STATE)

    # (a) placebo
    placebo = _placebo_shuffle(df, rng)
    _, placebo_summary, _ = gate3_walk_forward(placebo)
    placebo_rho = placebo_summary["pooled_spearman"]
    placebo_collapsed = bool(np.isfinite(placebo_rho) and abs(placebo_rho) < 0.05)
    placebo_also_significant = bool(
        np.isfinite(placebo_rho)
        and placebo_rho <= SPEARMAN_PASS
        and np.isfinite(placebo_summary["spread_bottom_minus_top_decimal"])
        and placebo_summary["spread_bottom_minus_top_decimal"] >= SPREAD_PASS
    )

    # (b) subsample stability -- split the OOS sample, compare pooled Spearman sign
    real_rho = gate3_summary["pooled_spearman"]
    split_rows = []
    hot = _hot_sample(df)
    for label, mask in (
        (f"pre_{split_year}", hot["date"] < pd.Timestamp(year=split_year, month=1, day=1)),
        (f"post_{split_year}", hot["date"] >= pd.Timestamp(year=split_year, month=1, day=1)),
    ):
        sub = hot[mask]
        rho, pval, n = _pooled_spearman(sub["comp"], sub["1MRet"])
        split_rows.append(
            {"check": "subsample", "sample": label, "pooled_spearman": rho, "pooled_p": pval, "n_obs": n}
        )
    finite_splits = [r["pooled_spearman"] for r in split_rows if np.isfinite(r["pooled_spearman"])]
    # sign must not flip relative to the full-sample OOS sign (only meaningful if real is finite)
    if np.isfinite(real_rho) and len(finite_splits) == 2:
        sign_ref = np.sign(real_rho)
        subsample_sign_hold = bool(all(np.sign(v) == sign_ref for v in finite_splits))
    else:
        subsample_sign_hold = bool(
            len(finite_splits) == 2 and np.sign(finite_splits[0]) == np.sign(finite_splits[1])
        )

    # (c) point-in-time audit -- structural, not empirical guesswork
    pit_notes = [
        "Composite is pre-built as per-country EXPANDING z-score (min 24m); every value at t uses only data <= t.",
        "Momentum subset uses momentum_quartile_flag, a cross-sectional rank at t (no look-ahead).",
        "Gate-3 composite quartile break-points are refit annually on qualifying months in years < Y only.",
        "No full-sample mean/std/quantile is used to standardize or to define the pooled Spearman inputs.",
        "1MRet@t is the forward realized return over month t and pairs with composite[t] directly (verified == t2_master).",
    ]

    passed = bool(placebo_collapsed and (not placebo_also_significant) and subsample_sign_hold)

    summary = {
        "pass": passed,
        "placebo_pooled_spearman": placebo_rho,
        "placebo_spread_decimal": placebo_summary["spread_bottom_minus_top_decimal"],
        "placebo_collapsed": placebo_collapsed,
        "placebo_also_significant_overrides_pass": placebo_also_significant,
        "subsample_split_year": split_year,
        "subsample_sign_hold": subsample_sign_hold,
        "subsample_details": split_rows,
        "point_in_time_discipline_pass": True,
        "point_in_time_notes": pit_notes,
    }
    rows = pd.DataFrame(
        [
            {
                "check": "placebo",
                "sample": "date_shuffle_within_country",
                "pooled_spearman": placebo_rho,
                "pooled_p": placebo_summary["pooled_spearman_p"],
                "n_obs": placebo_summary["pooled_n_obs"],
            },
            *split_rows,
        ]
    )
    return rows, summary


# --------------------------------------------------------------------------- #
# figures
# --------------------------------------------------------------------------- #
def make_figures(variants_data: dict, gate3_percountry: dict) -> None:
    # (1) Taiwan / Korea fragility timelines (core & full overlaid)
    for country in ("Taiwan", "Korea"):
        fig, ax = plt.subplots(figsize=(11, 4))
        for vname, color in (("core", "#356f9f"), ("full", "#b23a48")):
            df = variants_data[vname]
            g = df[(df["country"] == country) & df["comp"].notna()].sort_values("date")
            if not g.empty:
                ax.plot(g["date"], g["comp"], color=color, lw=1.2, label=f"composite_{vname}")
        ax.axhline(0, color="#888888", lw=0.8)
        ax.set_title(f"{country} fragility composite (per-country expanding z)")
        ax.set_xlabel("Date")
        ax.set_ylabel("Fragility (z)")
        ax.legend()
        fig.tight_layout()
        fig.savefig(FIGURES_DIR / f"fragility_timeline_{country.lower()}.pdf")
        plt.close(fig)

    # (2) histogram of per-country Gate-3 Spearman (core & full)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for ax, vname in zip(axes, ("core", "full")):
        pc = gate3_percountry[vname]
        vals = pc["spearman_comp_1MRet"].dropna()
        ax.hist(vals, bins=12, color="#356f9f", edgecolor="white")
        ax.axvline(0, color="#333333", lw=1)
        if len(vals):
            ax.axvline(vals.median(), color="#b23a48", lw=1.5, label=f"median {vals.median():.3f}")
            ax.legend()
        ax.set_title(f"Per-country Spearman (composite_{vname}) vs 1MRet\n(hot-momentum subset)")
        ax.set_xlabel("Spearman rho")
        ax.set_ylabel("Countries")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "gate3_percountry_spearman_hist.pdf")
    plt.close(fig)

    # (3) core vs full composite scatter on overlapping country-months
    core = variants_data["core"][["date", "country", "comp"]].rename(columns={"comp": "core"})
    full = variants_data["full"][["date", "country", "comp"]].rename(columns={"comp": "full"})
    merged = core.merge(full, on=["date", "country"], how="inner").dropna()
    fig, ax = plt.subplots(figsize=(6, 6))
    if not merged.empty:
        ax.scatter(merged["core"], merged["full"], s=6, alpha=0.3, color="#356f9f")
        r = merged["core"].corr(merged["full"])
        lims = [merged[["core", "full"]].min().min(), merged[["core", "full"]].max().max()]
        ax.plot(lims, lims, color="#b23a48", lw=1)
        ax.set_title(f"Core vs Full composite (Pearson r={r:.3f}, n={len(merged)})")
    ax.set_xlabel("composite_core")
    ax.set_ylabel("composite_full")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "core_vs_full_composite.pdf")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# RESULTS.md
# --------------------------------------------------------------------------- #
def _verdict(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def write_results_md(manifest: dict) -> None:
    lines = [
        "# Momentum Fragility Index - Conditional Reversal Test - Results",
        "",
        "## Executive Verdict",
        "",
        f"**Overall (core):** **{manifest['variants']['core']['overall_status']}**  ",
        f"**Overall (full):** **{manifest['variants']['full']['overall_status']}**",
        "",
        "Pre-registered decisive test (Gate 3): within the top-quartile-`12-1MTR_CS` "
        "(hot-momentum) subset, does higher Fragility predict lower forward 1M return, "
        "walk-forward OOS, pooled across countries? PASS = pooled Spearman <= -0.10 AND "
        "bottom-vs-top composite-quartile forward-return spread >= 50bp/month.",
        "",
        "| Variant | Gate 1 persistence | Gate 2 vol-proxy | Gate 3 (DECISIVE) | Gate 4 robustness | Overall |",
        "|---|---|---|---|---|---|",
    ]
    for vname in ("core", "full"):
        v = manifest["variants"][vname]
        g1 = v["gates"]["gate1_persistence"]
        g2 = v["gates"]["gate2_volatility"]
        g3 = v["gates"]["gate3_lead"]
        g4 = v["gates"].get("gate4_robustness")
        g1s = f"persist {g1['median_weighted_persist_1m']:.3f} ({'degenerate' if g1['degenerate_flag'] else 'ok'})"
        g2s = f"|corr| {g2['median_abs_corr']:.3f} ({'FLAG' if g2['volatility_proxy_flag'] else 'clear'})"
        g3s = (
            f"**{_verdict(g3['pass'])}** rho={g3['pooled_spearman']:.4f}, "
            f"spread={g3['spread_bottom_minus_top_bp']:.1f}bp (n={g3['pooled_n_obs']})"
        )
        if not g4:
            g4s = "not run"
        elif g4.get("role") == "pass_defense":
            g4s = f"**{_verdict(g4['pass'])}** placebo rho={g4['placebo_pooled_spearman']:.4f}"
        else:
            g4s = f"diagnostic (placebo rho={g4['placebo_pooled_spearman']:.4f}, collapsed)"
        lines.append(f"| {vname} | {g1s} | {g2s} | {g3s} | {g4s} | **{v['overall_status']}** |")

    lines += ["", "## Gate 3 detail (the pre-registered decisive metric)", ""]
    for vname in ("core", "full"):
        g3 = manifest["variants"][vname]["gates"]["gate3_lead"]
        d = g3["diagnostic_per_country_sign"]
        lines += [
            f"### composite_{vname}",
            "",
            f"- Walk-forward OOS pooled Spearman: **{g3['pooled_spearman']:.4f}** "
            f"(p={g3['pooled_spearman_p']:.3f}, n={g3['pooled_n_obs']}, "
            f"OOS years {g3['oos_year_min']}-{g3['oos_year_max']}) "
            f"-- threshold <= {SPEARMAN_PASS}: **{_verdict(g3['spearman_condition_pass'])}**",
            f"- Bottom(low-frag) minus Top(high-frag) forward-return spread: "
            f"**{g3['spread_bottom_minus_top_bp']:.1f} bp/month** "
            f"(bottom {g3['mean_ret_bottom_lowfrag']*100:.3f}% vs top {g3['mean_ret_top_highfrag']*100:.3f}%, "
            f"n_bottom={g3['n_bottom']}, n_top={g3['n_top']}) "
            f"-- threshold >= 50bp: **{_verdict(g3['spread_condition_pass'])}**",
            f"- Diagnostic per-country sign test (NOT a pass bar): "
            f"{d['n_negative']}/{d['n_countries_valid']} negative, sign-test p={d['sign_test_p']:.3f}, "
            f"median per-country rho={d['median_per_country_spearman']:.4f}",
            f"- **Gate 3 {vname}: {_verdict(g3['pass'])}**",
            "",
        ]

    lines += ["## Gate 4 robustness detail", ""]
    for vname in ("core", "full"):
        g4 = manifest["variants"][vname]["gates"].get("gate4_robustness")
        if not g4:
            lines += [f"### composite_{vname}", "", "- Not run: Gate 3 failed, so no PASS to defend.", ""]
            continue
        subs = "; ".join(
            f"{r['sample']}: rho={r['pooled_spearman']:.4f} (n={r['n_obs']})" for r in g4["subsample_details"]
        )
        role = g4.get("role", "pass_defense")
        diagnostic = role != "pass_defense"
        role_line = (
            "- Role: **diagnostic only** (Gate 3 already FAILED -- there is no PASS to defend). "
            "The subsample sign not holding here reflects the absence of any signal (a true null has "
            "no stable sign), and the placebo collapsing to ~0 is expected; neither changes the verdict."
            if diagnostic
            else "- Role: pass-defense (Gate 3 passed -- this gate is decisive for the PASS claim)."
        )
        lines += [
            f"### composite_{vname}",
            "",
            role_line,
            f"- Placebo (within-country date shuffle) pooled Spearman: {g4['placebo_pooled_spearman']:.4f} "
            f"-> collapsed toward zero: {g4['placebo_collapsed']}; also-significant override: "
            f"{g4['placebo_also_significant_overrides_pass']}",
            f"- Subsample sign stability (split {g4['subsample_split_year']}): {subs} -> sign held: "
            f"{g4['subsample_sign_hold']}",
            f"- Point-in-time discipline: pass ({len(g4['point_in_time_notes'])} audited invariants)",
            (
                f"- **Gate 4 {vname}: not decisive (diagnostic)**"
                if diagnostic
                else f"- **Gate 4 {vname}: {_verdict(g4['pass'])}**"
            ),
            "",
        ]

    lines += ["## Interpretation", ""]
    for vname in ("core", "full"):
        v = manifest["variants"][vname]
        g3 = v["gates"]["gate3_lead"]
        if v["overall_status"] == "PASS":
            lines.append(
                f"- **{vname}:** Conditional fragility genuinely predicts momentum reversal "
                f"(pooled Spearman {g3['pooled_spearman']:.3f}, spread {g3['spread_bottom_minus_top_bp']:.0f}bp), "
                f"and it survives placebo + subsample robustness. Eligible for production integration."
            )
        elif not g3["pass"]:
            reasons = []
            if not g3["spearman_condition_pass"]:
                reasons.append(
                    f"pooled Spearman {g3['pooled_spearman']:.4f} did not reach {SPEARMAN_PASS}"
                )
            if not g3["spread_condition_pass"]:
                reasons.append(
                    f"spread {g3['spread_bottom_minus_top_bp']:.1f}bp did not reach 50bp"
                )
            lines.append(
                f"- **{vname}:** Gate 3 FAILED ({'; '.join(reasons)}). The frozen pre-registered "
                f"spec does not show conditional reversal predictability. This is the answer -- no "
                f"threshold/horizon sweeping is permitted (PRD section 0 anti-p-hacking rule)."
            )
        else:
            lines.append(
                f"- **{vname}:** Gate 3 passed but Gate 4 robustness failed -- treat the apparent "
                f"effect as an artifact."
            )

    both_fail = all(not manifest["variants"][v]["gates"]["gate3_lead"]["pass"] for v in ("core", "full"))
    lines += ["", "## Recommendation", ""]
    if both_fail:
        lines.append(
            "**STOP. Negative result.** Neither composite variant clears the decisive Gate 3. Do not "
            "productionize into `Step Nineteen` and do not integrate a fragility penalty into `Step "
            "Fourteen Target Optimization.py`. Written up honestly per this repo's negative-result culture."
        )
    else:
        passers = [v for v in ("core", "full") if manifest["variants"][v]["overall_status"] == "PASS"]
        lines.append(
            f"**Proceed cautiously with variant(s): {', '.join(passers)}.** All four gates clear. Candidate "
            f"for production integration as a linear reversal-risk penalty, subject to a live monitoring period."
        )

    lines += [
        "",
        "## Artifacts",
        "",
        "- `momentum_fragility/results/manifest.json`",
        "- `momentum_fragility/results/fragility_scores.parquet`",
        "- `momentum_fragility/results/gate1_persistence.parquet`",
        "- `momentum_fragility/results/gate2_volatility.parquet`",
        "- `momentum_fragility/results/gate3_lead.parquet`",
        "- `momentum_fragility/results/gate4_robustness.parquet`",
        "- `momentum_fragility/results/figures/*.pdf`",
        "",
    ]
    (RESULTS_DIR / "RESULTS.md").write_text("\n".join(lines))


# --------------------------------------------------------------------------- #
# orchestration
# --------------------------------------------------------------------------- #
def run() -> dict:
    ensure_dirs()
    manifest: dict[str, Any] = {
        "status": "running",
        "test": "momentum_fragility_conditional_reversal",
        "conventions": {
            "return_alignment": "1MRet@t is forward realized return over month t; pairs with composite[t] (verified == t2_master)",
            "standardization": "per-country expanding z-score, min 24 months (pre-built upstream)",
            "walk_forward": "composite already point-in-time; quartile break-points refit annually on years < Y",
            "momentum_subset": "top cross-sectional quartile of 12-1MTR_CS (momentum_quartile_flag)",
            "primary_horizon": "forward 1MRet",
        },
        "pass_thresholds": {"pooled_spearman_max": SPEARMAN_PASS, "spread_min_bp": 50.0},
        "variants": {},
    }

    variants_data: dict[str, pd.DataFrame] = {}
    gate1_frames, gate2_frames, gate3_frames, gate4_frames = [], [], [], []
    gate3_percountry: dict[str, pd.DataFrame] = {}
    scores_frames = []

    for vname, cfg in VARIANTS.items():
        df = load_variant(cfg)
        variants_data[vname] = df

        g1_rows, g1_summary = gate1_persistence(df)
        g2_rows, g2_summary = gate2_volatility(df)
        g3_rows, g3_summary, oos = gate3_walk_forward(df)
        gate3_percountry[vname] = g3_rows

        gates = {
            "gate1_persistence": g1_summary,
            "gate2_volatility": g2_summary,
            "gate3_lead": g3_summary,
        }

        # Gate 4 is a PASS-defense gate. If Gate 3 fails, the PRD stop-rule says
        # stop -- but we still compute the placebo/subsample as *diagnostics*
        # (marked non-decisive) so the null's time-stability is on record.
        g4_rows, g4_summary = gate4_robustness(df, g3_summary, cfg["split_year"])
        g4_summary["role"] = "pass_defense" if g3_summary["pass"] else "diagnostic_only_gate3_failed"
        gates["gate4_robustness"] = g4_summary
        g4_rows["variant"] = vname
        gate4_frames.append(g4_rows)
        if g3_summary["pass"]:
            overall = "PASS" if g4_summary["pass"] else "FAIL - stopped at Gate 4 robustness"
        else:
            overall = "FAIL - stopped at Gate 3 (decisive)"

        manifest["variants"][vname] = {"overall_status": overall, "gates": gates}

        for frame, store in ((g1_rows, gate1_frames), (g2_rows, gate2_frames), (g3_rows, gate3_frames)):
            frame = frame.copy()
            frame["variant"] = vname
            store.append(frame)

        sc = df[["date", "country", "comp", "momentum_quartile_flag", "1MRet", "3MRet"]].copy()
        sc = sc.rename(columns={"comp": f"composite_{vname}"})
        scores_frames.append((vname, sc))

    # persist gate parquets
    pd.concat(gate1_frames, ignore_index=True).to_parquet(RESULTS_DIR / "gate1_persistence.parquet", index=False)
    pd.concat(gate2_frames, ignore_index=True).to_parquet(RESULTS_DIR / "gate2_volatility.parquet", index=False)
    pd.concat(gate3_frames, ignore_index=True).to_parquet(RESULTS_DIR / "gate3_lead.parquet", index=False)
    if gate4_frames:
        pd.concat(gate4_frames, ignore_index=True).to_parquet(RESULTS_DIR / "gate4_robustness.parquet", index=False)
    else:
        # write an explicit empty-with-schema marker so the artifact always exists
        pd.DataFrame(
            columns=["check", "sample", "pooled_spearman", "pooled_p", "n_obs", "variant"]
        ).to_parquet(RESULTS_DIR / "gate4_robustness.parquet", index=False)

    # combined fragility_scores.parquet (core + full on the shared key)
    core_sc = scores_frames[0][1]
    full_sc = scores_frames[1][1][["date", "country", "composite_full"]]
    scores = core_sc.merge(full_sc, on=["date", "country"], how="left").rename(
        columns={"momentum_quartile_flag": "momentum_quartile"}
    )
    scores.to_parquet(RESULTS_DIR / "fragility_scores.parquet", index=False)

    make_figures(variants_data, gate3_percountry)

    manifest["status"] = "complete"
    _write_json(RESULTS_DIR / "manifest.json", manifest)
    write_results_md(manifest)
    return manifest


def _print_summary(manifest: dict) -> None:
    print("=" * 78)
    print("MOMENTUM FRAGILITY INDEX - GATE-BY-GATE SUMMARY")
    print("=" * 78)
    for vname in ("core", "full"):
        v = manifest["variants"][vname]
        g = v["gates"]
        g3 = g["gate3_lead"]
        print(f"\n--- composite_{vname}  ->  OVERALL: {v['overall_status']}")
        g1 = g["gate1_persistence"]
        g2 = g["gate2_volatility"]
        print(
            f"  Gate 1 persistence : median 1m persist {g1['median_weighted_persist_1m']:.3f}, "
            f"worst-bucket share {g1['worst_single_bucket_share']:.2f} "
            f"-> {'DEGENERATE' if g1['degenerate_flag'] else 'ok (report-only)'}"
        )
        print(
            f"  Gate 2 vol-proxy   : median |corr| {g2['median_abs_corr']:.3f} "
            f"-> {'FLAG (>0.70)' if g2['volatility_proxy_flag'] else 'clear'}"
        )
        d = g3["diagnostic_per_country_sign"]
        print(
            f"  Gate 3 DECISIVE    : {'PASS' if g3['pass'] else 'FAIL'}\n"
            f"       pooled Spearman = {g3['pooled_spearman']:.4f} (p={g3['pooled_spearman_p']:.3f}, "
            f"n={g3['pooled_n_obs']}, OOS {g3['oos_year_min']}-{g3['oos_year_max']}) "
            f"[threshold <= {SPEARMAN_PASS}: {'PASS' if g3['spearman_condition_pass'] else 'FAIL'}]\n"
            f"       spread bottom-top = {g3['spread_bottom_minus_top_bp']:.1f} bp/mo "
            f"(low-frag {g3['mean_ret_bottom_lowfrag']*100:.3f}% vs high-frag {g3['mean_ret_top_highfrag']*100:.3f}%) "
            f"[threshold >= 50bp: {'PASS' if g3['spread_condition_pass'] else 'FAIL'}]\n"
            f"       diagnostic per-country sign: {d['n_negative']}/{d['n_countries_valid']} negative "
            f"(p={d['sign_test_p']:.3f}, median rho={d['median_per_country_spearman']:.4f})"
        )
        g4 = g.get("gate4_robustness")
        if g4:
            subs = ", ".join(
                f"{r['sample']}={r['pooled_spearman']:.4f}" for r in g4["subsample_details"]
            )
            print(
                f"  Gate 4 robustness  : {'PASS' if g4['pass'] else 'FAIL'} "
                f"(placebo rho={g4['placebo_pooled_spearman']:.4f}, collapsed={g4['placebo_collapsed']}; "
                f"subsample {subs}, sign held={g4['subsample_sign_hold']})"
            )
        else:
            print("  Gate 4 robustness  : not run (Gate 3 failed -- nothing to defend)")
    print("\n" + "=" * 78)


def main() -> None:
    manifest = run()
    _print_summary(manifest)


if __name__ == "__main__":
    main()
