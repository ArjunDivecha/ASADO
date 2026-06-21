#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: regime_ew/run_ew_test.py
=============================================================================

INPUT FILES:
- regime/data/processed/t2_factors_cs.parquet  (via regime.src.data_loader)
- regime/data/processed/country_returns.parquet (via regime.src.data_loader)

OUTPUT FILES:
- regime_ew/results/ew_signals.parquet          (OOS walk-forward posteriors)
- regime_ew/results/gate1_persistence.parquet
- regime_ew/results/gate3_lead.parquet
- regime_ew/results/manifest.json               (machine-readable PASS/FAIL)
- regime_ew/results/RESULTS.md                  (human verdict)
- regime_ew/results/hmm_params/*.json           (per-country HMM params)

VERSION: 1.0
LAST UPDATED: 2026-06-21
AUTHOR: Arjun Divecha (built by agent session, PRD Per Country Regime EarlyWarning.md)

DESCRIPTION:
Orchestrates the full per-country regime early-warning test:
  load → discover features → build feature matrices → walk-forward HMM →
  Gate 1 (persistence) → Gate 2 (vol check) → Gate 3 (lead test) →
  Gate 4 (placebo + subsample) → write RESULTS.md.

Any gate failure short-circuits the run (partial results still written).

USAGE:
  python regime_ew/run_ew_test.py                    # walk-forward (default)
  python regime_ew/run_ew_test.py --full-sample-only # diagnostic, skip Gate 3/4
  python regime_ew/run_ew_test.py --countries Brazil India Turkey  # subset

NOTES:
- Requires hmmlearn (pip install hmmlearn).
- Uses cached parquets in regime/data/processed/ — no DB query needed.
- Gate 3/4 results from --full-sample-only are in-sample and omitted.
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# ── path setup ────────────────────────────────────────────────────────────────
ASADO_ROOT = Path(__file__).resolve().parents[1]
EW_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ASADO_ROOT))

from regime.src.data_loader import build_forward_returns, load_country_returns, load_factor_panel
from regime.src.utils import T2_COUNTRIES, setup_logging
from regime_ew.src.feature_builder import build_country_feature_matrix, discover_features
from regime_ew.src.gates import (
    gate1_check,
    gate2_check,
    gate3_check,
    gate4_check,
    per_country_persistence,
)
from regime_ew.src.hmm_fitter import full_sample_posteriors, walk_forward_posteriors

RESULTS_DIR = EW_ROOT / "results"


# ── JSON serialisation helper (numpy / pandas types) ─────────────────────────

def _jsonable(obj):
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    if isinstance(obj, pd.Timestamp):
        return str(obj.date())
    return obj


# ── Results markdown writer ───────────────────────────────────────────────────

def _write_results_md(
    g1: dict | None,
    g2: dict | None,
    g3: dict | None,
    g4: dict | None,
    lead_df: pd.DataFrame | None,
    persist_df: pd.DataFrame | None,
    features: list[str],
    n_countries: int,
) -> None:
    lines = ["# Per-Country Regime Early-Warning Test — Results\n"]
    lines.append(f"**Features used ({len(features)}):** {', '.join(features)}\n")
    lines.append(f"**Countries:** {n_countries}\n")

    # Gate summary table
    def _gate_row(name, metrics, threshold_note):
        if metrics is None:
            return f"| {name} | skipped | — | — |\n"
        passed = metrics.get("PASS", "—")
        tag = "**PASS**" if passed is True else ("**FAIL**" if passed is False else "—")
        return f"| {name} | {tag} | {threshold_note} |\n"

    lines.append("\n## Gate Summary\n")
    lines.append("| Gate | Result | Threshold | Notes |\n")
    lines.append("|------|--------|-----------|-------|\n")

    if g1:
        g1_note = (f"median persist={g1['median_persist_1m']:.3f} (≥0.75); "
                   f"frac_dur_3m={g1['frac_countries_mean_adv_duration_ge3m']:.2f} (≥0.60)")
        lines.append(f"| Gate 1 Persistence | {'**PASS**' if g1['PASS'] else '**FAIL**'} | "
                     f"persist≥0.75 + 60% dur≥3m | {g1_note} |\n")
    else:
        lines.append("| Gate 1 Persistence | skipped | — | — |\n")

    if g2:
        g2_note = f"median |corr|={g2['median_abs_corr_P_adverse_vol6m']:.3f}"
        g2_tag = "FLAG" if g2["IS_VOL_SIGNAL_FLAG"] else "OK"
        lines.append(f"| Gate 2 Vol check | **{g2_tag}** | |r|<0.70 | {g2_note} |\n")
    else:
        lines.append("| Gate 2 Vol check | skipped | — | — |\n")

    if g3:
        g3_note = (
            f"sign={g3['sign_test_P_adverse']['n_negative']}/{g3['sign_test_P_adverse']['n_total']} "
            f"p={g3['sign_test_P_adverse']['binom_pval']:.4f}; "
            f"med_rho_P={g3['median_rho_P_adverse_1MRet']:.3f} "
            f"med_rho_dP={g3['median_rho_dP_adverse_1MRet']:.3f}; "
            f"spread={g3['economic_spread_pct_per_month']:.2f}%/mo"
        )
        lines.append(f"| Gate 3 Lead test | {'**PASS**' if g3['PASS'] else '**FAIL**'} | "
                     f"sign≥23 + med_rho≤−0.10 + spread≥0.50% | {g3_note} |\n")
    else:
        lines.append("| Gate 3 Lead test | skipped | — | — |\n")

    if g4:
        g4_note = (
            f"placebo_null={g4['placebo']['placebo_is_null']}; "
            f"subsample_stable={g4['subsample']['subsample_stable']}"
        )
        lines.append(f"| Gate 4 Artifact | {'**PASS**' if g4['PASS'] else '**FAIL**'} | "
                     f"placebo null + subsample stable | {g4_note} |\n")
    else:
        lines.append("| Gate 4 Artifact | skipped | — | — |\n")

    # Per-country persistence
    if persist_df is not None and not persist_df.empty:
        lines.append("\n## Per-Country Persistence (Gate 1)\n")
        lines.append("| Country | persist_1m | mean_adv_dur_months | n_months |\n")
        lines.append("|---------|-----------|---------------------|----------|\n")
        for _, row in persist_df.sort_values("persist_1m").iterrows():
            lines.append(
                f"| {row['country']} | {row['persist_1m']:.3f} | "
                f"{row['mean_adv_duration_months']:.1f} | {int(row['n_months'])} |\n"
            )

    # Per-country Gate 3 correlations
    if lead_df is not None and not lead_df.empty:
        lines.append("\n## Per-Country Lead Correlations (Gate 3)\n")
        lines.append("| Country | rho_P | rho_dP | n_months |\n")
        lines.append("|---------|-------|--------|----------|\n")
        for _, row in lead_df.sort_values("rho_P", ascending=True).iterrows():
            lines.append(
                f"| {row['country']} | {row.get('rho_P', float('nan')):.3f} | "
                f"{row.get('rho_dP', float('nan')):.3f} | "
                f"{int(row.get('n_months', 0))} |\n"
            )

    # Interpretation
    lines.append("\n## Interpretation\n")
    all_gates = [g1, g3, g4]
    all_pass = all(g is not None and g.get("PASS") for g in all_gates)
    if all_pass:
        lines.append(
            "All four gates pass. Per-country HMM adverse-state probability leads "
            "own-country forward returns out-of-sample. The signal is robust to "
            "placebo and subsample checks. **Recommend productionizing as a country-level "
            "timing overlay in the ASADO loop.**\n"
        )
    elif g1 is not None and not g1["PASS"]:
        lines.append(
            "**Gate 1 failed.** Adverse-state transitions are too fast to serve as "
            "early warning. The HMM latent states at monthly frequency are noisy — "
            "consider quarterly resampling or a coarser feature set. Stop here.\n"
        )
    elif g3 is not None and not g3["PASS"]:
        conds = []
        if not g3["condition_sign_ok"]:
            conds.append(f"sign test ({g3['sign_test_P_adverse']['n_negative']}/{g3['sign_test_P_adverse']['n_total']} < 23)")
        if not g3["condition_rho_ok"]:
            conds.append(
                f"median Spearman (P: {g3['median_rho_P_adverse_1MRet']:.3f}, "
                f"dP: {g3['median_rho_dP_adverse_1MRet']:.3f}) not ≤ −0.10"
            )
        if not g3["condition_spread_ok"]:
            conds.append(f"spread ({g3['economic_spread_pct_per_month']:.2f}% < 0.50%/mo)")
        med_rho = g3["median_rho_P_adverse_1MRet"]
        reversion_note = ""
        if med_rho > 0.03:
            reversion_note = (
                " The median Spearman is **positive** (+{:.3f}), meaning the adverse state "
                "(labeled by worst contemporaneous return) is systematically followed by "
                "rebounding returns — short-term within-country mean reversion dominates. "
                "The adverse state captures \"already bad\" months, not \"about-to-be-bad\" "
                "months. This is a structural limitation of contemporaneous adverse-state "
                "labeling at monthly frequency, not a data error."
            ).format(med_rho)
        vol_note = " If Gate 2 flagged vol, consider repurposing as a risk/vol overlay." if g2 and g2["IS_VOL_SIGNAL_FLAG"] else ""
        lines.append(
            f"**Gate 3 failed** ({'; '.join(conds)}). States persist but do not lead returns.{reversion_note}{vol_note} "
            "Stop as a return overlay.\n\n"
            "**Structural diagnosis:** The adversely-labeled HMM state reliably captures periods of "
            "poor own-country performance *in the contemporaneous month*, but those periods are followed "
            "by mean reversion, not continuation. This is the opposite of what an early-warning signal "
            "needs. Potential next directions (separate PRDs): (a) relabel the adverse state by *forward* "
            "return within the walk-forward training window (accepting the in-training-window circularity "
            "as a necessary design trade-off); (b) test at quarterly frequency where momentum effects "
            "dominate reversal; (c) pivot to a different labeling criterion such as volatility regime "
            "or CDS spread regime.\n"
        )
    elif g4 is not None and not g4["PASS"]:
        lines.append(
            "**Gate 4 failed.** The apparent lead did not survive robustness checks — "
            "likely a pipeline artifact (v1-trap). "
            f"Placebo null: {g4['placebo']['placebo_is_null']}. "
            f"Subsample stable: {g4['subsample']['subsample_stable']}. Stop.\n"
        )
    else:
        lines.append("Partial results — gates not fully evaluated.\n")

    (RESULTS_DIR / "RESULTS.md").write_text("".join(lines))


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Per-country regime early-warning test")
    parser.add_argument(
        "--full-sample-only", action="store_true",
        help="Diagnostic mode: fit on full history, skip Gate 3/4",
    )
    parser.add_argument(
        "--countries", nargs="+", default=None,
        help="Subset of T2 countries (default: all 34)",
    )
    args = parser.parse_args()

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "hmm_params").mkdir(exist_ok=True)

    logger = setup_logging("regime_ew_test")
    logger.info("=== Per-Country Regime Early-Warning Test ===")
    logger.info("Mode: %s", "full-sample (diagnostic)" if args.full_sample_only else "walk-forward OOS")

    # ── 1. Load data ──────────────────────────────────────────────────────────
    logger.info("Loading factor panel ...")
    factor_panel = load_factor_panel()

    logger.info("Loading country returns ...")
    returns_raw = load_country_returns(horizons=("1MRet",))
    fwd_returns = build_forward_returns(returns_raw, "1MRet")

    # ── 2. Feature discovery ─────────────────────────────────────────────────
    available = factor_panel["factor"].unique().tolist()
    features = discover_features(available)
    logger.info("Features (%d): %s", len(features), features)
    if len(features) < 3:
        logger.error("Too few features (%d). Aborting.", len(features))
        sys.exit(1)

    # ── 3. Build per-country feature matrices ────────────────────────────────
    target_countries = args.countries or T2_COUNTRIES
    feat_matrices = build_country_feature_matrix(factor_panel, features)
    feat_matrices = {c: v for c, v in feat_matrices.items() if c in target_countries}
    logger.info("Feature matrices: %d countries", len(feat_matrices))

    # ── 4. Walk-forward or full-sample posteriors ────────────────────────────
    all_signals: list[pd.DataFrame] = []
    for country in sorted(feat_matrices):
        fm = feat_matrices[country]
        country_fwd = (
            fwd_returns[fwd_returns["country"] == country]
            .set_index("date")["fwd_ret"]
            .sort_index()
        )
        if args.full_sample_only:
            sig = full_sample_posteriors(fm, country_fwd, country)
        else:
            sig = walk_forward_posteriors(fm, country_fwd, country)
        if not sig.empty:
            all_signals.append(sig)

    if not all_signals:
        logger.error("No signals produced. Check data and feature availability.")
        sys.exit(1)

    signals = pd.concat(all_signals, ignore_index=True).sort_values(["country", "date"])
    out_name = "ew_signals_fullsample.parquet" if args.full_sample_only else "ew_signals.parquet"
    signals.to_parquet(RESULTS_DIR / out_name, index=False)
    logger.info("Saved %s: %d rows, %d countries",
                out_name, len(signals), signals["country"].nunique())

    g1 = g2 = g3 = g4 = None
    lead_df: pd.DataFrame | None = None
    persist_df: pd.DataFrame | None = None

    # ── 5. Gate 1 — Persistence ──────────────────────────────────────────────
    persist_df = per_country_persistence(signals)
    persist_df.to_parquet(RESULTS_DIR / "gate1_persistence.parquet", index=False)
    g1_pass, g1 = gate1_check(persist_df)

    if not g1_pass:
        logger.info("GATE 1 FAILED — writing partial results, stopping.")
        (RESULTS_DIR / "manifest.json").write_text(
            json.dumps(_jsonable({"gate1": g1, "gate2": None, "gate3": None, "gate4": None}), indent=2)
        )
        _write_results_md(g1, g2, g3, g4, lead_df, persist_df, features, len(feat_matrices))
        return

    # ── 6. Gate 2 — Vol disguise ─────────────────────────────────────────────
    _, g2 = gate2_check(signals, fwd_returns)

    if args.full_sample_only:
        logger.info("Full-sample mode: Gates 3/4 skipped (in-sample, biased).")
        (RESULTS_DIR / "manifest.json").write_text(
            json.dumps(_jsonable({"gate1": g1, "gate2": g2,
                                  "gate3": "skipped_fullsample", "gate4": "skipped_fullsample"}), indent=2)
        )
        _write_results_md(g1, g2, None, None, None, persist_df, features, len(feat_matrices))
        return

    # ── 7. Gate 3 — Lead test ────────────────────────────────────────────────
    g3_pass, g3, lead_df = gate3_check(signals, fwd_returns)
    lead_df.to_parquet(RESULTS_DIR / "gate3_lead.parquet", index=False)

    if not g3_pass:
        logger.info("GATE 3 FAILED — writing results, stopping.")
        (RESULTS_DIR / "manifest.json").write_text(
            json.dumps(_jsonable({"gate1": g1, "gate2": g2, "gate3": g3, "gate4": None}), indent=2)
        )
        _write_results_md(g1, g2, g3, None, lead_df, persist_df, features, len(feat_matrices))
        return

    # ── 8. Gate 4 — Artifact checks ──────────────────────────────────────────
    _, g4 = gate4_check(signals, fwd_returns)

    # ── 9. Write final manifest and RESULTS.md ───────────────────────────────
    manifest = {"gate1": g1, "gate2": g2, "gate3": g3, "gate4": g4}
    (RESULTS_DIR / "manifest.json").write_text(
        json.dumps(_jsonable(manifest), indent=2)
    )
    _write_results_md(g1, g2, g3, g4, lead_df, persist_df, features, len(feat_matrices))

    overall = g1["PASS"] and g3["PASS"] and g4["PASS"]
    logger.info("=== FINAL: %s ===", "ALL GATES PASS" if overall else "ONE OR MORE GATES FAILED")
    logger.info("See regime_ew/results/RESULTS.md for the full verdict.")


if __name__ == "__main__":
    main()
