#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: run_placebo_test.py
=============================================================================

DESCRIPTION:
    Implements the PRD section 4 PLACEBO robustness check for the
    "Regime-Conditional Factor Selection" module.

    The logic of the placebo: the decisive test (run_factor_regime_test.py)
    asks whether a factor's within-date rank-IC slope differs by a country's
    OWN regime state. If that pipeline is well-calibrated, then DESTROYING the
    true date-alignment between a country's regime labels and its factor
    signals -- while preserving every other structural feature of the data
    (the factor panel, the within-date ranking, the interaction regression,
    the wild-cluster bootstrap, the FDR machinery, and each country's own
    marginal Growth/Recession/Neutral frequencies) -- must make the number of
    factors clearing FDR collapse toward the false-discovery rate itself
    (~ alpha * n_included ~ 0.10 * 74 by chance). If instead the placebo
    "passes" roughly as many factors as the real test, the real result would
    be a pipeline artifact rather than a genuine effect, and that placebo
    outcome OVERRIDES any apparent PASS from the real test.

    PLACEBO CONSTRUCTION (exactly as PRD section 4 specifies):
      For each country independently, take that country's sequence of monthly
      IP regime labels (from regime_labels_ip.parquet) and RANDOMLY PERMUTE
      the label values across that country's dates. This preserves the
      country's exact marginal count of Growth / Recession / Neutral months
      (so cell sizes and the min-cell filter behave the same way) while
      breaking the true date alignment between regime state and factor signal.
      The (date, country) pairs themselves are untouched, so the merge with
      the ranked factor panel yields the same per-country observation counts.

    Then it re-runs the EXACT same steps 1-7 of the Factor Test stage by
    importing and calling the very same functions from
    run_factor_regime_test.py (build_signal_return_panel,
    add_within_date_ranks, run_branch -> test_one_factor -> the wild-cluster
    bootstrap at seed 42, FDR-BH at alpha=0.10, min cell 20). Nothing about
    the statistical machinery changes; ONLY the regime column is shuffled.

    A separate frozen seed (PLACEBO_SEED = 20260705) drives the label
    permutation so the placebo is exactly reproducible; the bootstrap inside
    run_branch keeps its own frozen SEED=42 so the two randomness sources are
    independent and both deterministic.

    NOTE on the primary run's log: importing run_factor_regime_test.py has a
    module-level side effect (it opens factor_regime_test.log in mode="w").
    To avoid clobbering the PRIMARY run's log, this script (a) backs up
    factor_regime_test.log before the import, (b) redirects all logging to its
    own placebo_test.log, and (c) restores the primary log from the backup at
    the end. FAIL IS FAIL: nothing here silently overwrites a prior artifact.

INPUT FILES:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
        (read-only) t2_master -- factor values & country returns, reached only
        through the un-tainted regime/src/data_loader.py primitives that
        run_factor_regime_test.py already imports.
    /Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/Step Factor Categories.xlsx
        Sheet "Factor Categories": the 83 curated T2 factor names.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection/results/regime_labels_ip.parquet
        PRIMARY per-country monthly IP regime labels -- the labels that get
        shuffled here.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection/results/factor_test_results.parquet
        The REAL IP-branch results (read only, to build the real-vs-placebo
        p-value comparison figure and manifest deltas).

OUTPUT FILES:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection/results/placebo_results.parquet
        Per-factor placebo results, identical schema to
        factor_test_results.parquet.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection/results/placebo_summary.json
        Machine-readable placebo summary (pass count, smallest p, seed, etc.).
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection/results/placebo_test.log
        Placebo run log.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_factor_selection/results/figures/pvalue_histogram_real_vs_placebo.pdf
        Overlaid histogram of the IP branch's real vs placebo joint-test
        bootstrap p-values (PRD section 5 figure).

VERSION: 1.0
LAST UPDATED: 2026-07-05
AUTHOR: Arjun Divecha (built with Claude Code)

DEPENDENCIES:
    duckdb, numpy, pandas, statsmodels, matplotlib, openpyxl
    (all inherited via run_factor_regime_test.py)

USAGE:
    python "run_placebo_test.py"

NOTES:
    - Read-only DuckDB (enforced by the data_loader primitives).
    - FAIL IS FAIL: no silent fallbacks, no simulated data.
    - Frozen: PLACEBO_SEED=20260705 (label shuffle), plus the inherited frozen
      FDR alpha=0.10, min cell=20, bootstrap B=999, bootstrap seed=42.
=============================================================================
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
MODULE_ROOT = Path(__file__).resolve().parent
ASADO_ROOT = MODULE_ROOT.parent
RESULTS_DIR = MODULE_ROOT / "results"
FIGURES_DIR = RESULTS_DIR / "figures"
IP_LABELS = RESULTS_DIR / "regime_labels_ip.parquet"
REAL_IP_RESULTS = RESULTS_DIR / "factor_test_results.parquet"
OUT_PLACEBO = RESULTS_DIR / "placebo_results.parquet"
OUT_PLACEBO_JSON = RESULTS_DIR / "placebo_summary.json"
PRIMARY_LOG = RESULTS_DIR / "factor_regime_test.log"
PLACEBO_LOG = RESULTS_DIR / "placebo_test.log"

# Frozen placebo seed (label shuffle). Distinct from the bootstrap seed (42).
PLACEBO_SEED = 20260705

# ---------------------------------------------------------------------------
# Preserve the PRIMARY run's log BEFORE importing run_factor_regime_test.py,
# whose module-level setup_logging() opens factor_regime_test.log in mode "w".
# ---------------------------------------------------------------------------
_PRIMARY_LOG_BACKUP: bytes | None = None
if PRIMARY_LOG.exists():
    _PRIMARY_LOG_BACKUP = PRIMARY_LOG.read_bytes()

sys.path.insert(0, str(ASADO_ROOT))
# The import below truncates factor_regime_test.log (restored at the end).
from run_factor_regime_test import (  # noqa: E402
    FDR_ALPHA,
    MIN_CELL,
    N_BOOT,
    SEED,
    add_within_date_ranks,
    build_signal_return_panel,
    load_curated_factor_names,
    run_branch,
)

# Redirect all logging to the placebo log (so we don't pollute the primary
# log while run_branch emits its own log.info lines).
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(PLACEBO_LOG, mode="w")],
    force=True,
)
log = logging.getLogger("placebo_test")


def build_empty_reason(panel: pd.DataFrame, ranked: pd.DataFrame,
                       factor_names: list[str]) -> dict[str, str]:
    """Identical structural-exclusion accounting to run_factor_regime_test.main()."""
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
    return empty_reason


def shuffle_regime_labels(ip_labels: pd.DataFrame, seed: int) -> pd.DataFrame:
    """
    Permute each country's regime-label SEQUENCE independently, preserving that
    country's marginal Growth/Recession/Neutral frequency but breaking the true
    date alignment. (date, country) pairs are untouched.
    """
    rng = np.random.default_rng(seed)
    lab = ip_labels.dropna(subset=["regime"]).copy()
    lab = lab[lab["regime"].isin(["Growth", "Recession", "Neutral"])]
    out = []
    for country, cdf in lab.groupby("country"):
        cdf = cdf.sort_values("date")[["date", "country", "regime"]].copy()
        cdf["regime"] = rng.permutation(cdf["regime"].to_numpy())
        out.append(cdf)
    return pd.concat(out, ignore_index=True)


def plot_real_vs_placebo(real: pd.DataFrame, placebo: pd.DataFrame, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    p_real = real.loc[real["included"], "bootstrap_pvalue"].dropna().to_numpy()
    p_plac = placebo.loc[placebo["included"], "bootstrap_pvalue"].dropna().to_numpy()
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    bins = np.linspace(0, 1, 21)
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    ax.hist(p_real, bins=bins, alpha=0.55, color="#3b6fb0",
            edgecolor="white", label=f"Real IP (n={len(p_real)})")
    ax.hist(p_plac, bins=bins, alpha=0.55, color="#c0392b",
            edgecolor="white", label=f"Placebo (n={len(p_plac)})")
    ax.axvline(FDR_ALPHA, color="black", linestyle="--", linewidth=1,
               label=f"alpha = {FDR_ALPHA}")
    ax.set_xlabel("Wild-cluster bootstrap joint-test p-value")
    ax.set_ylabel("Number of factors")
    ax.set_title("Real vs placebo: joint interaction-test p-values (IP branch)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main() -> None:
    log.info("=" * 70)
    log.info("PLACEBO robustness check (PRD section 4)")
    log.info("Placebo label-shuffle seed=%d ; inherited bootstrap seed=%d, "
             "B=%d, min cell=%d, FDR alpha=%.2f",
             PLACEBO_SEED, SEED, N_BOOT, MIN_CELL, FDR_ALPHA)

    for pth in (IP_LABELS, REAL_IP_RESULTS):
        if not pth.exists():
            raise FileNotFoundError(f"Required input missing: {pth}")

    # ---- Rebuild the EXACT same factor panel + within-date ranks ----
    factor_names = load_curated_factor_names()
    panel = build_signal_return_panel(factor_names)
    ranked = add_within_date_ranks(panel)
    empty_reason = build_empty_reason(panel, ranked, factor_names)
    log.info("Panel rebuilt: %d ranked rows, %d factors; %d structurally excluded",
             len(ranked), ranked["factor"].nunique(), len(empty_reason))

    # ---- Shuffle regime labels (the ONLY change from the real test) ----
    ip_labels = pd.read_parquet(IP_LABELS)
    shuffled = shuffle_regime_labels(ip_labels, PLACEBO_SEED)
    # Sanity: marginals preserved per country.
    real_marg = (ip_labels.dropna(subset=["regime"])
                 .groupby(["country", "regime"]).size().sort_index())
    plac_marg = shuffled.groupby(["country", "regime"]).size().sort_index()
    if not real_marg.equals(plac_marg):
        raise RuntimeError("Placebo shuffle changed a country's regime marginals -- "
                           "this must never happen (would confound the check).")
    log.info("Per-country regime marginals verified identical to real labels.")

    # ---- Rerun the identical test on the shuffled labels ----
    placebo_res = run_branch(ranked, shuffled, factor_names, "IP-PLACEBO", empty_reason)
    placebo_res.to_parquet(OUT_PLACEBO, index=False)

    # ---- Compare to the real IP result ----
    real = pd.read_parquet(REAL_IP_RESULTS)
    plot_real_vs_placebo(real, placebo_res, FIGURES_DIR / "pvalue_histogram_real_vs_placebo.pdf")

    plac_inc = int(placebo_res["included"].sum())
    plac_pass = placebo_res[placebo_res["passes_fdr"]]["factor"].tolist()
    real_inc = int(real["included"].sum())
    real_pass = real[real["passes_fdr"]]["factor"].tolist()

    plac_raw = placebo_res.loc[placebo_res["included"], "bootstrap_pvalue"]
    real_raw = real.loc[real["included"], "bootstrap_pvalue"]
    expected_by_chance = round(FDR_ALPHA * plac_inc, 1)

    log.info("=" * 70)
    log.info("REAL  IP: %d/%d included factors pass FDR (alpha=%.2f)",
             len(real_pass), real_inc, FDR_ALPHA)
    log.info("PLACEBO : %d/%d included factors pass FDR (alpha=%.2f) "
             "[expected ~%.1f by chance]",
             len(plac_pass), plac_inc, FDR_ALPHA, expected_by_chance)
    log.info("PLACEBO smallest bootstrap p=%.4f ; raw p<0.10 count=%d",
             float(plac_raw.min()), int((plac_raw < 0.10).sum()))
    log.info("REAL    smallest bootstrap p=%.4f ; raw p<0.10 count=%d",
             float(real_raw.min()), int((real_raw < 0.10).sum()))

    summary = {
        "placebo_seed": PLACEBO_SEED,
        "bootstrap_seed": SEED,
        "n_boot": N_BOOT,
        "min_cell": MIN_CELL,
        "fdr_alpha": FDR_ALPHA,
        "placebo_included": plac_inc,
        "placebo_pass_fdr": len(plac_pass),
        "placebo_passing_factors": plac_pass,
        "placebo_min_bootstrap_p": float(plac_raw.min()),
        "placebo_raw_p_lt_010": int((plac_raw < 0.10).sum()),
        "real_included": real_inc,
        "real_pass_fdr": len(real_pass),
        "real_passing_factors": real_pass,
        "real_min_bootstrap_p": float(real_raw.min()),
        "real_raw_p_lt_010": int((real_raw < 0.10).sum()),
        "expected_passes_by_chance": expected_by_chance,
        "placebo_invalidates_real": (
            len(plac_pass) >= max(1, len(real_pass)) and len(real_pass) >= 8
        ),
    }
    OUT_PLACEBO_JSON.write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    try:
        main()
    finally:
        # Restore the PRIMARY run's log we backed up before the import truncated it.
        if _PRIMARY_LOG_BACKUP is not None:
            PRIMARY_LOG.write_bytes(_PRIMARY_LOG_BACKUP)
