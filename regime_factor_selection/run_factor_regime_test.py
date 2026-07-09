#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: run_factor_regime_test.py
=============================================================================

DESCRIPTION:
    Implements PRD section 3 -- the decisive statistical test of Objective B
    for the "Regime-Conditional Factor Selection" module:

        "Conditioned on each country's OWN regime state, does any of T2's
         ~83 factors show a significantly different return-predictive
         relationship (IC) depending on regime?"

    Pipeline (PRIMARY = Industrial-Production classifier; GDP = exploratory):

      1. Build the factor panel with the 83 curated T2 factors listed in
         "Step Factor Categories.xlsx" (both _CS and _TS variants, exactly
         as named there; all 83 confirmed present in t2_master). We DO NOT
         reuse list_t2_factor_variables()'s 52 "_CS"-only filter -- the PRD
         (section 2.3) requires the full 83-factor curated set. Factor
         values, country returns, and forward returns come from the clean,
         un-tainted primitives in regime/src/data_loader.py
         (load_factor_panel, load_country_returns, build_forward_returns).

      2. Lag each (country, factor) signal by one month and inner-join to the
         same-month forward 1M return -- the T2 dating convention (no
         look-ahead; identical plumbing to prepare_ic_panel, reproduced
         inline so we import nothing from the tainted ic_analysis.py beyond
         its within-date ranking IDEA).

      3. Within-date rank transform (PRD section 3): for each (factor, date)
         cross-section, rank BOTH signal and forward return across that
         date's countries (pandas .rank(method='average'), numerically
         identical to scipy.stats.rankdata that spearman_ic uses), then
         standardize each within-date rank vector to mean 0 / unit std so
         cross-sections of different country counts are comparable in a
         pooled OLS. This is the same within-date ranking idea used by
         regime/src/ic_analysis.py::spearman_ic, reused (not reimplemented
         differently).

      4. Inner-join each (country, date) row to that country's OWN regime
         label from regime_labels_ip.parquet (warm-up/None rows drop out
         naturally).

      5. Per factor, fit:
            rank_ret ~ 1 + rank_signal
                         + rank_signal:Growth + rank_signal:Recession
         (Neutral = omitted baseline). Test the JOINT significance of the two
         interaction coefficients with an F-test (restriction: both = 0).

      6. Inference via a WILD CLUSTER BOOTSTRAP over countries
         (Cameron-Gelbach-Miller / "wild cluster restricted"; the
         `wildboottest` package is NOT cleanly installable in this
         PEP-668 externally-managed system Python without
         --break-system-packages, which we will not do without permission,
         so the manual CGM procedure specified in the task is implemented):
           (a) fit the NULL model  rank_ret ~ 1 + rank_signal;
           (b) take null-model fitted values + residuals;
           (c) for B=999 iterations, multiply each COUNTRY's residuals by an
               independent Rademacher (+/-1) weight (one weight per country
               per iteration), form y* = null_fitted + weighted_resid, refit
               the FULL model, and record the joint F-stat;
           (d) bootstrap p = (1 + #{F* >= F_obs}) / (1 + B)  -- the standard
               Davidson-MacKinnon finite-sample form of the task's
               "fraction of F* >= observed" (the +1/+1 continuity correction
               avoids a literal p=0 and keeps FDR/logs well-defined; flagged
               here as the only deviation from the task's bare "count/B").
         Fixed seed (42) => fully reproducible.

      7. Minimum cell size: a factor is INCLUDED in the test only if all
         three regime buckets have >= 20 real (post-rank) country-month
         observations. Factors failing this are reported (not silently
         dropped) with their actual cell sizes and excluded from the FDR
         family.

      8. Multiple testing: Benjamini-Hochberg FDR at alpha=0.10 (FROZEN per
         PRD section 3) across the INCLUDED factors' bootstrap p-values.

      9. EXPLORATORY GDP branch (clearly labeled, NEVER pooled into the IP
         FDR family per PRD section 2.1): repeats 3-8 using
         regime_labels_gdp.parquet. GDP labels are annual (dated Jul-1, the
         +6-month point-in-time stamp); they are forward-filled across the
         following 12 months per country (Jul-Y label applies Jul-Y..Jun-Y+1,
         point-in-time safe) so the branch is a comparable monthly
         conditional-IC test. Its p-values get their OWN separate
         multipletests() call.

INPUT FILES:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
        (read-only) t2_master -- factor values, country returns. Accessed via
        regime/src/data_loader.py primitives.
    /Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/Step Factor Categories.xlsx
        Sheet "Factor Categories": the 83 curated T2 factor names (authoritative factor list).
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection/results/regime_labels_ip.parquet
        PRIMARY per-country monthly regime labels (date, country, regime, ...).
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection/results/regime_labels_gdp.parquet
        EXPLORATORY per-country annual regime labels (date, country, regime, ...).

OUTPUT FILES:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection/results/factor_test_results.parquet
        PRIMARY (IP) per-factor results: factor, n_obs_growth, n_obs_recession,
        n_obs_neutral, interaction_growth_coef, interaction_recession_coef,
        joint_f_stat, bootstrap_pvalue, fdr_adjusted_pvalue, passes_fdr
        (+ n_obs_total, n_countries, n_dates, included, exclude_reason).
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection/results/factor_test_results_gdp_exploratory.parquet
        EXPLORATORY (GDP) per-factor results, same schema.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection/results/factor_regime_test.log
        Run log.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection/results/figures/pvalue_histogram_ip.pdf
        Histogram of the IP branch's bootstrap joint-test p-values.

VERSION: 1.0
LAST UPDATED: 2026-07-05
AUTHOR: Arjun Divecha (built with Claude Code)

DEPENDENCIES:
    duckdb, numpy, pandas, scipy, statsmodels, matplotlib, openpyxl

USAGE:
    python "run_factor_regime_test.py"

NOTES:
    - Read-only DuckDB (enforced by the data_loader primitives).
    - FAIL IS FAIL: no silent fallbacks, no simulated data. If an input is
      missing the script raises and stops.
    - Frozen thresholds (do NOT tune post-hoc): FDR alpha=0.10, min cell 20,
      B=999, seed=42, regime split 30/40/30 (baked into the classifier stage).
=============================================================================
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.stats.multitest import multipletests

# ---------------------------------------------------------------------------
# Paths / imports
# ---------------------------------------------------------------------------
MODULE_ROOT = Path(__file__).resolve().parent
ASADO_ROOT = MODULE_ROOT.parent
RESULTS_DIR = MODULE_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
FACTOR_CATEGORIES_XLSX = Path(
    "/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/Step Factor Categories.xlsx"
)
IP_LABELS = RESULTS_DIR / "regime_labels_ip.parquet"
GDP_LABELS = RESULTS_DIR / "regime_labels_gdp.parquet"
OUT_IP = RESULTS_DIR / "factor_test_results.parquet"
OUT_GDP = RESULTS_DIR / "factor_test_results_gdp_exploratory.parquet"
LOG_PATH = RESULTS_DIR / "factor_regime_test.log"

sys.path.insert(0, str(ASADO_ROOT))
from regime.src.data_loader import (  # noqa: E402
    build_forward_returns,
    load_country_returns,
    load_factor_panel,
)

# ---------------------------------------------------------------------------
# Frozen constants (PRD section 3 -- do NOT tune after seeing results)
# ---------------------------------------------------------------------------
FDR_ALPHA = 0.10          # FROZEN
MIN_CELL = 20             # FROZEN: >=20 country-months per regime bucket
N_BOOT = 999              # FROZEN
SEED = 42                 # FROZEN
MIN_XSEC = 8              # min countries per date cross-section to rank
                          # (matches spearman_ic's mask.sum()<8 guard)


def setup_logging() -> logging.Logger:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(LOG_PATH, mode="w")],
        force=True,
    )
    return logging.getLogger("factor_regime_test")


log = setup_logging()


# ---------------------------------------------------------------------------
# Step 1: factor list + panel
# ---------------------------------------------------------------------------
def load_curated_factor_names() -> list[str]:
    """The 83 curated T2 factor names from Step Factor Categories.xlsx."""
    if not FACTOR_CATEGORIES_XLSX.exists():
        raise FileNotFoundError(f"Missing factor categories file: {FACTOR_CATEGORIES_XLSX}")
    xl = pd.read_excel(FACTOR_CATEGORIES_XLSX, sheet_name="Factor Categories")
    names = [str(n).strip() for n in xl["Factor Name"].dropna().tolist()]
    return names


def build_signal_return_panel(factor_names: list[str]) -> pd.DataFrame:
    """
    date, country, factor, signal, ret  -- factor lagged 1 month, joined to
    same-month forward 1M return. Reproduces prepare_ic_panel plumbing inline.
    """
    fp = load_factor_panel(factor_names)              # date, country, factor, value
    present = sorted(fp["factor"].unique())
    missing = [f for f in factor_names if f not in set(present)]
    if missing:
        log.warning("%d curated factors not found in t2_master: %s", len(missing), missing)
    rets = load_country_returns()
    fwd = build_forward_returns(rets, "1MRet")         # date, country, fwd_ret

    f = fp.sort_values(["country", "factor", "date"]).copy()
    f["signal"] = f.groupby(["country", "factor"])["value"].shift(1)
    f = f.dropna(subset=["signal"])
    merged = f.merge(fwd, on=["date", "country"], how="inner")
    merged = merged.rename(columns={"fwd_ret": "ret"})
    return merged[["date", "country", "factor", "signal", "ret"]]


# ---------------------------------------------------------------------------
# Step 3: within-date rank + standardize
# ---------------------------------------------------------------------------
def add_within_date_ranks(panel: pd.DataFrame) -> pd.DataFrame:
    """
    For each (factor, date) cross-section rank signal & ret across countries
    (pandas .rank == scipy.stats.rankdata, average ties -- the spearman_ic
    idea), then z-standardize each rank vector within the date so different
    cross-section sizes are comparable in the pooled OLS. Drops dates with
    < MIN_XSEC countries or zero within-date variance.
    """
    df = panel.dropna(subset=["signal", "ret"]).copy()
    grp = df.groupby(["factor", "date"])
    df["_n"] = grp["signal"].transform("size")
    df = df[df["_n"] >= MIN_XSEC].copy()

    grp = df.groupby(["factor", "date"])
    df["rs"] = grp["signal"].rank(method="average")
    df["rr"] = grp["ret"].rank(method="average")
    grp = df.groupby(["factor", "date"])
    rs_mean = grp["rs"].transform("mean")
    rs_std = grp["rs"].transform("std")
    rr_mean = grp["rr"].transform("mean")
    rr_std = grp["rr"].transform("std")
    df["rank_signal"] = (df["rs"] - rs_mean) / rs_std
    df["rank_ret"] = (df["rr"] - rr_mean) / rr_std
    # zero-variance date cross-sections -> std 0 -> NaN -> drop
    df = df.dropna(subset=["rank_signal", "rank_ret"])
    return df[["date", "country", "factor", "rank_signal", "rank_ret"]]


# ---------------------------------------------------------------------------
# Steps 5-6: per-factor joint F-test + wild cluster bootstrap
# ---------------------------------------------------------------------------
def _joint_f(y: np.ndarray, Xu: np.ndarray, Xr: np.ndarray, q: int) -> float:
    """Joint F-stat for the q restrictions taking Xu (full) down to Xr (null)."""
    n, k = Xu.shape
    beta_u, _, _, _ = np.linalg.lstsq(Xu, y, rcond=None)
    resid_u = y - Xu @ beta_u
    rss_u = float(resid_u @ resid_u)
    beta_r, _, _, _ = np.linalg.lstsq(Xr, y, rcond=None)
    resid_r = y - Xr @ beta_r
    rss_r = float(resid_r @ resid_r)
    dof = n - k
    if dof <= 0 or rss_u <= 0:
        return np.nan
    return ((rss_r - rss_u) / q) / (rss_u / dof)


def test_one_factor(fdf: pd.DataFrame, rng: np.random.Generator) -> dict:
    """
    fdf: rows for ONE factor with columns rank_signal, rank_ret, regime, country.
    Returns coefs, joint F, wild-cluster-bootstrap p, cell sizes.
    """
    growth = (fdf["regime"] == "Growth").to_numpy(dtype=float)
    recession = (fdf["regime"] == "Recession").to_numpy(dtype=float)
    neutral = (fdf["regime"] == "Neutral").to_numpy(dtype=float)

    n_g = int(growth.sum())
    n_r = int(recession.sum())
    n_n = int(neutral.sum())

    res = {
        "n_obs_growth": n_g,
        "n_obs_recession": n_r,
        "n_obs_neutral": n_n,
        "n_obs_total": len(fdf),
        "n_countries": int(fdf["country"].nunique()),
        "n_dates": int(fdf["date"].nunique()),
        "interaction_growth_coef": np.nan,
        "interaction_recession_coef": np.nan,
        "joint_f_stat": np.nan,
        "bootstrap_pvalue": np.nan,
        "included": False,
        "exclude_reason": "",
    }

    # Only three recognised regimes should be present after the label merge.
    if min(n_g, n_r, n_n) < MIN_CELL:
        res["exclude_reason"] = (
            f"min cell < {MIN_CELL} (G={n_g}, R={n_r}, N={n_n})"
        )
        return res

    rs = fdf["rank_signal"].to_numpy(dtype=float)
    y = fdf["rank_ret"].to_numpy(dtype=float)
    ones = np.ones_like(rs)
    # Full design: const, rank_signal, rs:Growth, rs:Recession  (Neutral baseline)
    Xu = np.column_stack([ones, rs, rs * growth, rs * recession])
    # Null design: const, rank_signal
    Xr = np.column_stack([ones, rs])
    q = 2

    # Observed coefficients + F
    beta_u, _, _, _ = np.linalg.lstsq(Xu, y, rcond=None)
    res["interaction_growth_coef"] = float(beta_u[2])
    res["interaction_recession_coef"] = float(beta_u[3])
    f_obs = _joint_f(y, Xu, Xr, q)
    res["joint_f_stat"] = f_obs
    if not np.isfinite(f_obs):
        res["exclude_reason"] = "non-finite observed F (degenerate design)"
        return res

    # ---- Wild cluster bootstrap (CGM), vectorised over B ----
    # Null-model fit on real y (impose H0: interactions = 0).
    beta_r, _, _, _ = np.linalg.lstsq(Xr, y, rcond=None)
    null_fitted = Xr @ beta_r
    null_resid = y - null_fitted

    codes = fdf["country"].astype("category").cat.codes.to_numpy()
    n_clusters = codes.max() + 1
    # Rademacher weights: one per (country, bootstrap iteration).
    rad = rng.choice(np.array([-1.0, 1.0]), size=(n_clusters, N_BOOT))
    W = rad[codes, :]                                   # (n, B)
    Yb = null_fitted[:, None] + null_resid[:, None] * W  # (n, B)

    n, k = Xu.shape
    dof = n - k
    # Precompute projections (X fixed across iterations).
    Mu = np.linalg.pinv(Xu)                             # (4, n)
    Mr = np.linalg.pinv(Xr)                             # (2, n)
    resid_u = Yb - Xu @ (Mu @ Yb)                       # (n, B)
    resid_r = Yb - Xr @ (Mr @ Yb)                       # (n, B)
    rss_u = np.einsum("ij,ij->j", resid_u, resid_u)     # (B,)
    rss_r = np.einsum("ij,ij->j", resid_r, resid_r)     # (B,)
    with np.errstate(divide="ignore", invalid="ignore"):
        f_boot = ((rss_r - rss_u) / q) / (rss_u / dof)
    f_boot = f_boot[np.isfinite(f_boot)]

    p_boot = (1 + int(np.sum(f_boot >= f_obs))) / (1 + len(f_boot))
    res["bootstrap_pvalue"] = float(p_boot)
    res["included"] = True
    return res


# ---------------------------------------------------------------------------
# Orchestration for one classifier branch
# ---------------------------------------------------------------------------
def run_branch(
    ranked_panel: pd.DataFrame,
    regime_labels: pd.DataFrame,
    factor_names: list[str],
    branch_name: str,
    empty_reason: dict[str, str] | None = None,
) -> pd.DataFrame:
    """ranked_panel: date,country,factor,rank_signal,rank_ret (all factors)."""
    empty_reason = empty_reason or {}
    reg = regime_labels[["date", "country", "regime"]].dropna(subset=["regime"])
    reg = reg[reg["regime"].isin(["Growth", "Recession", "Neutral"])]
    merged = ranked_panel.merge(reg, on=["date", "country"], how="inner")
    log.info("[%s] panel after regime inner join: %d rows, %d factors",
             branch_name, len(merged), merged["factor"].nunique())

    rng = np.random.default_rng(SEED)
    rows = []
    for factor in factor_names:
        fdf = merged[merged["factor"] == factor]
        if len(fdf) == 0:
            rows.append({
                "factor": factor, "n_obs_growth": 0, "n_obs_recession": 0,
                "n_obs_neutral": 0, "n_obs_total": 0, "n_countries": 0,
                "n_dates": 0, "interaction_growth_coef": np.nan,
                "interaction_recession_coef": np.nan, "joint_f_stat": np.nan,
                "bootstrap_pvalue": np.nan, "included": False,
                "exclude_reason": empty_reason.get(
                    factor, "no observations after regime merge"),
            })
            continue
        r = test_one_factor(fdf, rng)
        r["factor"] = factor
        rows.append(r)

    df = pd.DataFrame(rows)

    # FDR across INCLUDED factors only.
    df["fdr_adjusted_pvalue"] = np.nan
    df["passes_fdr"] = False
    inc = df["included"] & df["bootstrap_pvalue"].notna()
    if inc.sum() > 0:
        reject, p_adj, _, _ = multipletests(
            df.loc[inc, "bootstrap_pvalue"].to_numpy(),
            alpha=FDR_ALPHA, method="fdr_bh",
        )
        df.loc[inc, "fdr_adjusted_pvalue"] = p_adj
        df.loc[inc, "passes_fdr"] = reject

    cols = [
        "factor", "n_obs_growth", "n_obs_recession", "n_obs_neutral",
        "interaction_growth_coef", "interaction_recession_coef",
        "joint_f_stat", "bootstrap_pvalue", "fdr_adjusted_pvalue",
        "passes_fdr", "n_obs_total", "n_countries", "n_dates",
        "included", "exclude_reason",
    ]
    df = df[cols].sort_values("bootstrap_pvalue", na_position="last").reset_index(drop=True)
    n_inc = int(inc.sum())
    n_excl = int((~df["included"]).sum())
    n_pass = int(df["passes_fdr"].sum())
    log.info("[%s] included=%d excluded=%d  ->  %d factors pass FDR(alpha=%.2f)",
             branch_name, n_inc, n_excl, n_pass, FDR_ALPHA)
    return df


def forward_fill_annual_regime(gdp_labels: pd.DataFrame, panel_dates: pd.Series) -> pd.DataFrame:
    """
    GDP labels are annual (Jul-1, +6mo PIT stamp). Forward-fill each country's
    label across the following 12 months so the exploratory branch is a
    comparable monthly conditional-IC test. Point-in-time safe: a Jul-Y label
    is applied only to months >= Jul-Y (until the next annual label).
    """
    all_months = pd.DataFrame({"date": sorted(panel_dates.unique())})
    out = []
    g = gdp_labels.dropna(subset=["regime"]).copy()
    for country, cdf in g.groupby("country"):
        cdf = cdf.sort_values("date")[["date", "regime"]]
        merged = pd.merge_asof(
            all_months.sort_values("date"), cdf,
            on="date", direction="backward",
        )
        merged["country"] = country
        out.append(merged)
    ff = pd.concat(out, ignore_index=True).dropna(subset=["regime"])
    return ff[["date", "country", "regime"]]


def plot_pvalue_hist(df: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    p = df.loc[df["included"], "bootstrap_pvalue"].dropna().to_numpy()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.hist(p, bins=20, range=(0, 1), color="#3b6fb0", edgecolor="white")
    ax.axvline(FDR_ALPHA, color="#c0392b", linestyle="--",
               label=f"alpha = {FDR_ALPHA}")
    ax.set_xlabel("Wild-cluster bootstrap joint-test p-value")
    ax.set_ylabel("Number of factors")
    ax.set_title(f"IP branch: joint interaction-test p-values (n={len(p)} factors)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main() -> None:
    log.info("=" * 70)
    log.info("Regime-conditional factor-selection test (PRD section 3)")
    log.info("Frozen: FDR alpha=%.2f, min cell=%d, B=%d, seed=%d",
             FDR_ALPHA, MIN_CELL, N_BOOT, SEED)

    for pth in (IP_LABELS, GDP_LABELS):
        if not pth.exists():
            raise FileNotFoundError(f"Required classifier output missing: {pth}")

    factor_names = load_curated_factor_names()
    log.info("Curated factor list: %d factors", len(factor_names))

    panel = build_signal_return_panel(factor_names)
    log.info("Signal/return panel: %d rows, %d factors, %s..%s",
             len(panel), panel["factor"].nunique(),
             panel["date"].min().date(), panel["date"].max().date())

    ranked = add_within_date_ranks(panel)
    log.info("Ranked panel: %d rows (after within-date rank + MIN_XSEC=%d filter)",
             len(ranked), MIN_XSEC)

    # Accurate exclusion reason for factors that survive with 0 ranked rows.
    # Root cause is almost always ZERO cross-sectional dispersion (a global
    # commodity signal broadcast identically to every country), which makes a
    # within-date cross-sectional rank-IC test structurally undefined.
    raw_factors = set(panel["factor"].unique())
    ranked_factors = set(ranked["factor"].unique())
    empty_reason: dict[str, str] = {}
    for fac in raw_factors - ranked_factors:
        cs_std = panel[panel["factor"] == fac].groupby("date")["signal"].std()
        if float((cs_std > 1e-9).mean()) == 0.0:
            empty_reason[fac] = (
                "no cross-sectional dispersion (constant across countries "
                "each date -> within-date rank test undefined)")
        else:
            empty_reason[fac] = "cross-section too thin (< MIN_XSEC countries per date)"
    for fac in set(factor_names) - raw_factors:
        empty_reason[fac] = "no signal/return data in t2_master panel"
    if empty_reason:
        log.info("Structurally excluded factors (%d): %s",
                 len(empty_reason), sorted(empty_reason))

    # ---------- PRIMARY: IP ----------
    ip_labels = pd.read_parquet(IP_LABELS)
    ip_res = run_branch(ranked, ip_labels, factor_names, "IP-PRIMARY", empty_reason)
    ip_res.to_parquet(OUT_IP, index=False)
    plot_pvalue_hist(ip_res, FIGURES_DIR / "pvalue_histogram_ip.pdf")

    # ---------- EXPLORATORY: GDP (separate FDR family) ----------
    gdp_labels_raw = pd.read_parquet(GDP_LABELS)
    gdp_labels_ff = forward_fill_annual_regime(gdp_labels_raw, ranked["date"])
    gdp_res = run_branch(ranked, gdp_labels_ff, factor_names, "GDP-EXPLORATORY", empty_reason)
    gdp_res.to_parquet(OUT_GDP, index=False)

    # ---------- Summary ----------
    ip_pass = ip_res[ip_res["passes_fdr"]]["factor"].tolist()
    gdp_pass = gdp_res[gdp_res["passes_fdr"]]["factor"].tolist()
    ip_inc = int(ip_res["included"].sum())
    gdp_inc = int(gdp_res["included"].sum())

    log.info("=" * 70)
    log.info("PRIMARY (IP): %d/%d included factors pass FDR at alpha=%.2f",
             len(ip_pass), ip_inc, FDR_ALPHA)
    if ip_pass:
        log.info("  IP passing factors: %s", ip_pass)
    log.info("EXPLORATORY (GDP): %d/%d included factors pass FDR (separate family)",
             len(gdp_pass), gdp_inc)
    if gdp_pass:
        log.info("  GDP passing factors: %s", gdp_pass)

    verdict = ("POTENTIAL SIGNAL (>=8) -> run placebo next"
               if len(ip_pass) >= 8
               else "LEANING NULL (<8) -> placebo still required per PRD section 4")
    log.info("PRD section 6 verdict (IP primary): %s", verdict)

    summary = {
        "ip_included": ip_inc,
        "ip_pass_fdr": len(ip_pass),
        "ip_passing_factors": ip_pass,
        "gdp_included": gdp_inc,
        "gdp_pass_fdr": len(gdp_pass),
        "gdp_passing_factors": gdp_pass,
        "fdr_alpha": FDR_ALPHA,
        "min_cell": MIN_CELL,
        "n_boot": N_BOOT,
        "seed": SEED,
        "verdict": verdict,
    }
    (RESULTS_DIR / "factor_test_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
