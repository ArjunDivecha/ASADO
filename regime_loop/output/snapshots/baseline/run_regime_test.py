#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: run_regime_test.py
=============================================================================
Orchestrates the full regime conditioning value test (PRD §5.2–5.6).
=============================================================================
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REGIME_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REGIME_ROOT))

from src.backtest import (  # noqa: E402
    compute_factor_weights,
    performance_metrics,
    rolling_5y_sharpe,
    run_backtest,
    uncond_weights,
)
from src.data_loader import (  # noqa: E402
    build_forward_returns,
    list_t2_factor_variables,
    load_country_returns,
    load_factor_panel,
    load_macro_panel,
)
from src.ic_analysis import (  # noqa: E402
    conditional_ic_table,
    monthly_ic,
    prepare_ic_panel,
    top_dispersion_factors,
)
from src.regime_tagger import build_regime_series, persistence_stats  # noqa: E402
from src.utils import (  # noqa: E402
    FIGURES_DIR,
    FULL_START,
    IN_SAMPLE_END,
    OOS_START,
    REGIME_LABELS,
    RESULTS_DIR,
    ensure_dirs,
    setup_logging,
)

logger = setup_logging()

SANITY_MONTHS = {
    "2008-10-01": {"allowed": {"Crisis", "Recession"}, "label": "GFC"},
    "2017-06-01": {"allowed": {"Expansion"}, "label": "2017 expansion"},
    "2020-04-01": {"allowed": {"Crisis", "Recession"}, "label": "COVID"},
    "2022-09-01": {"allowed": {"Late-cycle", "Stagflation", "Transition"}, "label": "2022 inflation"},
}


def _plot_regime_timeline(regimes: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(14, 5))
    sp = regimes.set_index("date")["sp500"]
    ax.plot(sp.index, sp.values, color="#333333", lw=1.2, label="S&P 500 (FRED)")
    colors = {
        "Crisis": "#c0392b",
        "Late-cycle": "#e67e22",
        "Recession": "#8e44ad",
        "Recovery": "#27ae60",
        "Expansion": "#2980b9",
        "Stagflation": "#d35400",
        "Transition": "#95a5a6",
    }
    for regime in REGIME_LABELS:
        mask = regimes["regime"] == regime
        if mask.any():
            ax.scatter(
                regimes.loc[mask, "date"],
                regimes.loc[mask, "sp500"],
                c=colors.get(regime, "#000"),
                s=12,
                label=regime,
                alpha=0.85,
            )
    ax.set_title("Macro regimes vs S&P 500 (monthly)")
    ax.legend(loc="upper left", ncol=4, fontsize=8)
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "regime_timeline_sp500.pdf")
    plt.close(fig)


def _plot_transition_matrix(tm_prob: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(8, 6))
    im = ax.imshow(tm_prob.values, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(tm_prob.columns)))
    ax.set_yticks(range(len(tm_prob.index)))
    ax.set_xticklabels(tm_prob.columns, rotation=45, ha="right")
    ax.set_yticklabels(tm_prob.index)
    for i in range(len(tm_prob.index)):
        for j in range(len(tm_prob.columns)):
            val = tm_prob.iloc[i, j]
            if pd.notna(val):
                ax.text(j, i, f"{val:.2f}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, ax=ax)
    ax.set_title("Regime transition probabilities (1-month)")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "regime_transition_matrix.pdf")
    plt.close(fig)


def _plot_ic_heatmap(cond_pivot: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(10, 14))
    data = cond_pivot.fillna(0).values
    im = ax.imshow(data, aspect="auto", cmap="RdBu_r", vmin=-0.1, vmax=0.1)
    ax.set_yticks(range(len(cond_pivot.index)))
    ax.set_yticklabels(cond_pivot.index, fontsize=6)
    ax.set_xticks(range(len(cond_pivot.columns)))
    ax.set_xticklabels(cond_pivot.columns, rotation=45, ha="right")
    fig.colorbar(im, ax=ax, label="Mean IC")
    ax.set_title("Regime-conditional mean IC (in-sample)")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "conditional_ic_heatmap.pdf")
    plt.close(fig)


def _plot_backtest(bt: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 5))
    b = bt.set_index("date")
    cum_b = (1 + b["ret_baseline"].fillna(0)).cumprod()
    cum_t = (1 + b["ret_treatment"].fillna(0)).cumprod()
    ax.plot(cum_b.index, cum_b, label="Baseline (unconditional IC weights)")
    ax.plot(cum_t.index, cum_t, label="Treatment (regime-conditional)")
    ax.set_title("Cumulative OOS returns (2019+)")
    ax.legend()
    ax.set_facecolor("white")
    fig.patch.set_facecolor("white")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "cumulative_returns_oos.pdf")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 4))
    rs = rolling_5y_sharpe(bt, "ret_baseline")
    rt = rolling_5y_sharpe(bt, "ret_treatment")
    ax.plot(rs.index, rs, label="Baseline 5y Sharpe")
    ax.plot(rt.index, rt, label="Treatment 5y Sharpe")
    ax.axhline(0, color="gray", lw=0.8)
    ax.legend()
    ax.set_title("Rolling 5-year Sharpe (OOS window)")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "rolling_5y_sharpe.pdf")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(12, 4))
    def dd(s):
        w = (1 + s.fillna(0)).cumprod()
        return w / w.cummax() - 1

    ax.fill_between(b.index, dd(b["ret_baseline"]), 0, alpha=0.4, label="Baseline DD")
    ax.fill_between(b.index, dd(b["ret_treatment"]), 0, alpha=0.4, label="Treatment DD")
    ax.legend()
    ax.set_title("Drawdown comparison")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "drawdown_comparison.pdf")
    plt.close(fig)


def sanity_checks(
    regimes: pd.DataFrame,
    tests: pd.DataFrame,
    bt: pd.DataFrame,
    panel: pd.DataFrame,
) -> dict:
    issues = []
    passed = []

    for dt_str, spec in SANITY_MONTHS.items():
        dt = pd.Timestamp(dt_str)
        row = regimes[regimes["date"] == pd.Timestamp(dt)]
        if row.empty:
            issues.append(f"Missing regime for {dt_str}")
            continue
        reg = row.iloc[0]["regime"]
        if reg not in spec["allowed"]:
            issues.append(f"{spec['label']} ({dt_str}): got {reg}, expected {spec['allowed']}")
        else:
            passed.append(f"{spec['label']}: {reg}")

    high_ic = tests[tests["ic_unconditional"].abs() > 0.15]
    if len(high_ic) > 0:
        issues.append(f"{len(high_ic)} factors with |IC|>0.15 in-sample (check data)")

    dist = regimes["regime"].value_counts(normalize=True)
    if dist.max() > 0.50:
        issues.append(f"Regime {dist.idxmax()} dominates {dist.max():.1%}")
    if dist.min() < 0.02:
        issues.append(f"Regime {dist.idxmin()} rare {dist.min():.1%}")

    oos_panel = panel[panel["date"] >= OOS_START]
    if oos_panel["date"].min() < IN_SAMPLE_END:
        issues.append("OOS panel overlaps in-sample IC window")

    return {"passed": passed, "issues": issues, "halt": len(issues) > 0 and any("GFC" in i or "overlap" in i for i in issues)}


def write_regime_md(
    h1: dict,
    h2: dict,
    h3: dict,
    sanity: dict,
    regimes: pd.DataFrame,
    tests: pd.DataFrame,
    bt: pd.DataFrame,
) -> None:
    path = REGIME_ROOT / "regime.md"
    n_factors = tests.shape[0]
    lines = [
        "# Regime Conditioning Value Test — Results",
        "",
        "## Executive verdict",
        "",
        f"| Hypothesis | Result | Key metric |",
        f"|------------|--------|------------|",
        f"| **H1** Persistence | **{'PASS' if h1['pass'] else 'FAIL'}** | Weighted 1m persistence = {h1['weighted_persist_1m']:.3f} (threshold ≥ 0.75) |",
        f"| **H2** IC dispersion | **{'PASS' if h2['pass'] else 'FAIL'}** | {h2['n_sig']}/{n_factors} factors significant after BH-FDR ({h2['pct']:.1%}, need ≥30%) |",
        f"| **H3** Strategy value | **{'PASS' if h3['pass'] else 'FAIL'}** | Sharpe Δ = {h3['sharpe_delta']:.3f} (need ≥0.2); rolling windows beat baseline {h3['pct_windows_win']:.1%} (need ≥60%) |",
        "",
        f"**Recommended next action:** {h3['decision']}",
        "",
        "## Decision framework (PRD §3)",
        "",
    ]
    if h1["pass"] and h2["pass"] and h3["pass"]:
        lines.append(
            "All three hypotheses hold → **build deterministic regime classifier into production ASADO**; ML enhancements optional later."
        )
    elif h1["pass"] and h2["pass"] and not h3["pass"]:
        lines.append(
            "H1+H2 hold, H3 fails → **try alternative conditioning** (sizing, exposure caps) before abandoning regimes."
        )
    elif not h2["pass"]:
        lines.append(
            "H2 fails → **abandon regime concept for ASADO**; pursue other alpha sources."
        )
    elif not h1["pass"]:
        lines.append(
            "H1 fails → **reconsider regime definitions** or abandon; regimes too unstable."
        )

    lines.extend(
        [
            "",
            "## H1 — Regime persistence",
            "",
            f"- Weighted average 1-month persistence: **{h1['weighted_persist_1m']:.3f}**",
            f"- Unweighted 1/3/6-month persistence: {h1['persist_1m']:.3f} / {h1['persist_3m']:.3f} / {h1['persist_6m']:.3f}",
            f"- Mean regime duration: **{h1['mean_duration']:.1f}** months",
            "",
            "![Transition matrix](results/figures/regime_transition_matrix.pdf)",
            "",
            "### Regime frequency",
            "",
            regimes["regime"].value_counts().to_markdown(),
            "",
            "## H2 — Conditional IC",
            "",
            f"- Factors tested: **{n_factors}** (T2 `_CS` cross-sectional factors; PRD cites 53, warehouse has {n_factors})",
            f"- Significant after Benjamini–Hochberg FDR (α=0.10): **{h2['n_sig']}** ({h2['pct']:.1%})",
            "",
            "![IC heatmap](results/figures/conditional_ic_heatmap.pdf)",
            "",
            "### Top 10 factors by regime IC dispersion",
            "",
            h2["top10"].to_markdown(),
            "",
            "### Sign-reversal factors (conditional IC flips sign)",
            "",
            f"Count: **{int(tests['sign_reversal'].sum())}** — highest-value candidates for regime weighting.",
            "",
            "## H3 — Out-of-sample backtest (2019-01+)",
            "",
            "Portfolio: cross-sectional **quintile long/short** on composite factor score, equal-weight within legs. "
            "Baseline uses in-sample (≤2018-12) unconditional mean IC weights; treatment uses regime-conditional IC weights.",
            "",
            "### Full OOS metrics",
            "",
            h3["metrics_table"],
            "",
            f"- Treatment also tested with **50% shrinkage** toward unconditional weights: Sharpe Δ = {h3.get('sharpe_delta_shrunk', float('nan')):.3f}",
            "",
            "![Cumulative returns](results/figures/cumulative_returns_oos.pdf)",
            "![Rolling Sharpe](results/figures/rolling_5y_sharpe.pdf)",
            "![Drawdowns](results/figures/drawdown_comparison.pdf)",
            "",
            "### Stress episodes",
            "",
            h3["stress_table"],
            "",
            "## Sanity checks (PRD §5.6, §8)",
            "",
        ]
    )
    for p in sanity["passed"]:
        lines.append(f"- ✓ {p}")
    for i in sanity["issues"]:
        lines.append(f"- ⚠ {i}")

    lines.extend(
        [
            "",
            "## Top 3 surprising findings",
            "",
        ]
        + [f"{i+1}. {x}" for i, x in enumerate(h3.get("surprises", [])[:3])]
        + [
            "",
            "## Top 3 caveats",
            "",
        ]
        + [f"{i+1}. {x}" for i, x in enumerate(h3.get("caveats", [])[:3])]
        + [
            "",
            "## Data sources",
            "",
            "- T2 factors & returns: `Data/asado.duckdb` → `t2_master`",
            "- Macro indicators: **FRED API** (current vintage; not ALFRED — revision risk on CPI/unemployment)",
            "- See `data/raw/fred_*.meta.json` per series",
            "",
            "## Artifacts",
            "",
            f"- Tags: [`results/regime_tags.parquet`](results/regime_tags.parquet)",
            f"- IC matrix: [`results/conditional_ic_matrix.parquet`](results/conditional_ic_matrix.parquet)",
            f"- Backtest: [`results/backtest_results.parquet`](results/backtest_results.parquet)",
            f"- Summary: [`results/regime_test_summary.md`](results/regime_test_summary.md)",
        ]
    )
    path.write_text("\n".join(lines))


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-output", action="store_true", help="Output metrics as JSON to stdout")
    args = parser.parse_args()
    
    ensure_dirs()
    logger.info("Starting regime conditioning value test")

    macro = load_macro_panel()
    macro = macro[macro["date"] >= FULL_START]
    regimes = build_regime_series(macro)
    regimes.to_parquet(RESULTS_DIR / "regime_tags.parquet", index=False)

    pers = persistence_stats(regimes)
    h1_pass = pers["weighted_persist_1m"] >= 0.75
    pers["transition_probs"].to_parquet(RESULTS_DIR / "regime_transition_matrix.parquet")

    factors_list = list_t2_factor_variables()
    factors = load_factor_panel(factors_list)
    factors = factors[factors["date"] >= FULL_START]
    returns = load_country_returns()
    fwd = build_forward_returns(returns, "3MRet")
    panel = prepare_ic_panel(factors, fwd)

    ic_m = monthly_ic(panel)
    cond_pivot, cond_long, tests = conditional_ic_table(ic_m, regimes)
    n_sig = int(tests.get("significant_fdr", pd.Series(dtype=bool)).fillna(False).sum())
    n_factors = len(tests)
    h2_pass = n_sig >= max(16, int(0.30 * n_factors))

    cond_out = cond_long.merge(
        tests.reset_index()[["factor", "p_value", "p_adj_fdr", "significant_fdr", "ic_unconditional"]],
        on="factor",
        how="left",
    )
    cond_out.to_parquet(RESULTS_DIR / "conditional_ic_matrix.parquet", index=False)
    cond_pivot.to_parquet(RESULTS_DIR / "conditional_ic_pivot.parquet")

    w_cond = compute_factor_weights(panel, regimes, shrinkage=0.0)
    w_cond_shrunk = compute_factor_weights(panel, regimes, shrinkage=0.5)
    w_base = uncond_weights(panel)

    bt = run_backtest(panel, fwd, regimes, w_cond, w_base)
    bt_shrunk = run_backtest(panel, fwd, regimes, w_cond_shrunk, w_base)
    bt["ret_treatment_shrunk"] = bt_shrunk["ret_treatment"]
    bt.to_parquet(RESULTS_DIR / "backtest_results.parquet", index=False)

    m_base = performance_metrics(bt["ret_baseline"])
    m_treat = performance_metrics(bt["ret_treatment"])
    m_treat_sh = performance_metrics(bt["ret_treatment_shrunk"])
    sharpe_delta = m_treat.get("sharpe", np.nan) - m_base.get("sharpe", np.nan)
    sharpe_delta_sh = m_treat_sh.get("sharpe", np.nan) - m_base.get("sharpe", np.nan)

    bt_full = run_backtest(panel, fwd, regimes, w_cond, w_base, oos_start=FULL_START)
    roll_b = rolling_5y_sharpe(bt_full, "ret_baseline")
    roll_t = rolling_5y_sharpe(bt_full, "ret_treatment")
    valid = roll_b.notna() & roll_t.notna()
    pct_win = float((roll_t[valid] > roll_b[valid]).mean()) if valid.any() else 0.0
    h3_pass = sharpe_delta >= 0.2 and pct_win >= 0.60

    stress_rows = []
    for label, start, end in [
        ("COVID 2020", "2020-01-01", "2020-12-01"),
        ("Inflation 2022", "2022-01-01", "2022-12-01"),
    ]:
        sub = bt[(bt["date"] >= start) & (bt["date"] <= end)]
        stress_rows.append(
            {
                "period": label,
                "baseline_sharpe": performance_metrics(sub["ret_baseline"]).get("sharpe"),
                "treatment_sharpe": performance_metrics(sub["ret_treatment"]).get("sharpe"),
            }
        )
    stress_df = pd.DataFrame(stress_rows)

    metrics_df = pd.DataFrame([m_base, m_treat, m_treat_sh], index=["baseline", "treatment", "treatment_shrunk"])
    metrics_md = metrics_df.round(4).to_markdown()

    if h1_pass and h2_pass and h3_pass:
        decision = "Proceed to production regime classifier (PRD §3 row 1)."
    elif h1_pass and h2_pass:
        decision = "Try alternative conditioning schemes before ML/CNN work (PRD §3 row 2)."
    elif not h2_pass:
        decision = "Abandon regime conditioning for ASADO (PRD §3 row 3)."
    else:
        decision = "Reconsider regime definitions or abandon (PRD §3 row 4)."

    sanity = sanity_checks(regimes, tests, bt, panel)

    _plot_regime_timeline(regimes)
    _plot_transition_matrix(pers["transition_probs"])
    _plot_ic_heatmap(cond_pivot)
    _plot_backtest(bt)

    h1 = {
        "pass": h1_pass,
        "weighted_persist_1m": pers["weighted_persist_1m"],
        "persist_1m": pers["persist_1m_unweighted"],
        "persist_3m": pers["persist_3m"],
        "persist_6m": pers["persist_6m"],
        "mean_duration": pers["mean_duration_months"],
    }
    h2 = {
        "pass": h2_pass,
        "n_sig": n_sig,
        "pct": n_sig / n_factors if n_factors else 0,
        "top10": top_dispersion_factors(tests),
    }
    h3 = {
        "pass": h3_pass,
        "sharpe_delta": sharpe_delta,
        "sharpe_delta_shrunk": sharpe_delta_sh,
        "pct_windows_win": pct_win,
        "decision": decision,
        "metrics_table": metrics_md,
        "stress_table": stress_df.round(3).to_markdown(index=False),
        "surprises": [
            f"Transition regime covers {regimes['regime'].eq('Transition').mean():.1%} of months — rules are strict.",
            f"Weighted persistence {pers['weighted_persist_1m']:.2f} vs unweighted {pers['persist_1m_unweighted']:.2f}.",
            f"Shrinkage variant Sharpe Δ = {sharpe_delta_sh:.3f} vs pure conditional {sharpe_delta:.3f}.",
        ],
        "caveats": [
            "FRED current vintage — not point-in-time ALFRED; CPI/unemployment subject to revision.",
            f"HY OAS history may start later than 1995 — early sample uses available FRED fields only.",
            "Baseline is IC-weighted quintile L/S, not full optimizer pipeline — compare magnitudes, not levels, to live ASADO.",
        ],
    }

    summary_path = RESULTS_DIR / "regime_test_summary.md"
    summary_path.write_text(
        f"# Regime test summary\n\n"
        f"H1: {'PASS' if h1_pass else 'FAIL'} | H2: {'PASS' if h2_pass else 'FAIL'} | H3: {'PASS' if h3_pass else 'FAIL'}\n\n"
        f"{decision}\n"
    )

    write_regime_md(h1, h2, h3, sanity, regimes, tests, bt)

    manifest = {"h1": h1, "h2": {"pass": h2_pass, "n_sig": n_sig}, "h3": {"pass": h3_pass, "sharpe_delta": sharpe_delta}}
    (RESULTS_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))

    logger.info("Complete. H1=%s H2=%s H3=%s", h1_pass, h2_pass, h3_pass)
    
    if args.json_output:
        json_metrics = {
            "h1_pass": int(h1_pass),
            "weighted_persist_1m": pers["weighted_persist_1m"],
            "n_sig_factors": n_sig,
            "sharpe_delta": sharpe_delta,
            "all_pass": int(h1_pass and h2_pass and h3_pass)
        }
        print(json.dumps(json_metrics))
        sys.stdout.flush()
    
    return 0 if not sanity.get("halt") else 1


if __name__ == "__main__":
    raise SystemExit(main())
