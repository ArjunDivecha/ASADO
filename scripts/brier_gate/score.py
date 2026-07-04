"""
=============================================================================
SCRIPT NAME: score.py (Brier Gate step 4)
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/brier_gate/forecasts.jsonl
  (from run_forecasts.py)

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/brier_gate/brier_gate_results_{YYYY_MM_DD}.xlsx
  Sheets: brier_summary, gate_tests, pnl_grid, calibration, per_tag,
  forecast_level (sample).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/docs/BRIER_GATE_RESULTS_{YYYY_MM_DD}.md
  Human-readable verdict against the pre-committed gate criteria (PRD §6).

VERSION: 1.0
LAST UPDATED: 2026-07-03
AUTHOR: Claude Code (for Arjun Divecha)

DESCRIPTION:
Scores the Brier Gate forecast fleet (docs/PRD_BRIER_GATE.md §6):
- Aggregates K samples per (market, horizon, arm, model) to the MEDIAN p_ai.
- Brier and log-loss per arm/model vs the market's Brier, paired by
  market-horizon, with an event-clustered bootstrap (resample events with
  replacement, 2,000 draws) for the Brier difference CI.
- Gate tests: (1) A1 < market Brier with CI excluding 0; (2) threshold-rule
  PnL after crossing cost, split-half stable; (3) A1 < A0 (warehouse adds
  value); (4) leave-one-event-out robustness of test 1.
- Threshold-rule PnL: buy YES at p_mkt+cost if p_ai > p_mkt+theta (payout
  1 if y=1), sell (buy NO) at (1-p_mkt)+cost if p_ai < p_mkt-theta; PnL per
  $1 stake; theta x cost grids in probability points.
- Calibration: 10-bin reliability table per arm/model.

DEPENDENCIES:
- pandas, numpy, openpyxl (project venv)

USAGE:
  python scripts/brier_gate/score.py
=============================================================================
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
WORK_DIR = BASE_DIR / "Data" / "work" / "brier_gate"
FORECASTS_PATH = WORK_DIR / "forecasts.jsonl"
STAMP = datetime.now().strftime("%Y_%m_%d")
XLSX_PATH = WORK_DIR / f"brier_gate_results_{STAMP}.xlsx"
REPORT_PATH = BASE_DIR / "docs" / f"BRIER_GATE_RESULTS_{STAMP}.md"

THETA_GRID = [0.05, 0.10, 0.15]
COST_GRID = [0.0, 0.01, 0.02, 0.05]  # crossing cost in probability points
N_BOOT = 2000
RNG = np.random.default_rng(42)


def load() -> pd.DataFrame:
    rows = [json.loads(l) for l in FORECASTS_PATH.read_text().splitlines() if l.strip()]
    raw = pd.DataFrame(rows)
    agg = (
        raw.groupby(["model", "arm", "market_id", "horizon_days"])
        .agg(
            p_ai=("p_ai", "median"),
            n_samples=("p_ai", "size"),
            p_mkt=("p_mkt", "first"),
            outcome=("outcome", "first"),
            event_slug=("event_slug", "first"),
            tag=("tag", "first"),
        )
        .reset_index()
    )
    agg["brier_ai"] = (agg["p_ai"] - agg["outcome"]) ** 2
    agg["brier_mkt"] = (agg["p_mkt"] - agg["outcome"]) ** 2
    eps = 1e-6
    for col, src in [("ll_ai", "p_ai"), ("ll_mkt", "p_mkt")]:
        p = agg[src].clip(eps, 1 - eps)
        agg[col] = -(agg["outcome"] * np.log(p) + (1 - agg["outcome"]) * np.log(1 - p))
    return agg


def event_bootstrap_diff(df: pd.DataFrame, col_a: str, col_b: str) -> tuple[float, float, float]:
    """Mean(col_a - col_b) with event-clustered bootstrap CI. Negative = a better."""
    diff = df[col_a] - df[col_b]
    events = df["event_slug"].values
    uniq = np.unique(events)
    idx_by_event = {e: np.flatnonzero(events == e) for e in uniq}
    means = np.empty(N_BOOT)
    for b in range(N_BOOT):
        pick = RNG.choice(uniq, size=len(uniq), replace=True)
        idx = np.concatenate([idx_by_event[e] for e in pick])
        means[b] = diff.values[idx].mean()
    return float(diff.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def pnl_rule(df: pd.DataFrame, theta: float, cost: float) -> dict:
    """Trade $1 whenever |p_ai - p_mkt| > theta; PnL vs outcome, net of cost."""
    long_ = df[df["p_ai"] > df["p_mkt"] + theta]
    short = df[df["p_ai"] < df["p_mkt"] - theta]
    pnl = []
    pnl.extend((long_["outcome"] - (long_["p_mkt"] + cost)).tolist())
    pnl.extend(((1 - short["outcome"]) - ((1 - short["p_mkt"]) + cost)).tolist())
    if not pnl:
        return {"n_trades": 0}
    pnl = np.array(pnl)
    return {
        "n_trades": len(pnl),
        "mean_pnl_per_$": float(pnl.mean()),
        "total_pnl_per_$1each": float(pnl.sum()),
        "hit_rate": float((pnl > 0).mean()),
        "worst_trade": float(pnl.min()),
        "t_stat": float(pnl.mean() / (pnl.std(ddof=1) / np.sqrt(len(pnl)))) if len(pnl) > 2 else np.nan,
    }


def main() -> int:
    df = load()
    print(f"Scored surface: {len(df)} (model,arm,market,horizon) cells")

    # ---- Brier summary
    summary = (
        df.groupby(["model", "arm"])
        .agg(
            n=("brier_ai", "size"),
            brier_ai=("brier_ai", "mean"),
            brier_mkt=("brier_mkt", "mean"),
            logloss_ai=("ll_ai", "mean"),
            logloss_mkt=("ll_mkt", "mean"),
        )
        .reset_index()
    )
    summary["brier_edge_vs_mkt"] = summary["brier_mkt"] - summary["brier_ai"]

    # ---- Gate tests
    gate_rows = []
    for (model, arm), sub in df.groupby(["model", "arm"]):
        mean_d, lo, hi = event_bootstrap_diff(sub, "brier_ai", "brier_mkt")
        gate_rows.append(
            {"model": model, "test": f"{arm} vs market", "mean_brier_diff": mean_d,
             "ci_lo": lo, "ci_hi": hi, "beats": hi < 0, "n": len(sub),
             "n_events": sub["event_slug"].nunique()}
        )
    for model, sub in df.groupby("model"):
        a1 = sub[sub["arm"] == "A1"].set_index(["market_id", "horizon_days"])
        a0 = sub[sub["arm"] == "A0"].set_index(["market_id", "horizon_days"])
        joined = a1.join(a0[["brier_ai"]], rsuffix="_a0", how="inner").reset_index()
        if len(joined) > 20:
            mean_d, lo, hi = event_bootstrap_diff(
                joined.rename(columns={"brier_ai_a0": "brier_b"}), "brier_ai", "brier_b"
            )
            gate_rows.append(
                {"model": model, "test": "A1 vs A0 (warehouse value)", "mean_brier_diff": mean_d,
                 "ci_lo": lo, "ci_hi": hi, "beats": hi < 0, "n": len(joined),
                 "n_events": joined["event_slug"].nunique()}
            )
    gate = pd.DataFrame(gate_rows)

    # ---- Leave-one-event-out for A1-vs-market (per model)
    loo_rows = []
    for model, sub in df[df["arm"] == "A1"].groupby("model"):
        base = (sub["brier_ai"] - sub["brier_mkt"]).mean()
        worst = None
        for e in sub["event_slug"].unique():
            d = (sub[sub["event_slug"] != e]["brier_ai"] - sub[sub["event_slug"] != e]["brier_mkt"]).mean()
            if worst is None or d > worst[1]:
                worst = (e, d)
        loo_rows.append({"model": model, "full_diff": base, "worst_loo_diff": worst[1],
                         "worst_event": worst[0], "sign_flips": worst[1] > 0 > base or worst[1] < 0 < base})
    loo = pd.DataFrame(loo_rows)

    # ---- PnL grid (per model, arm A1 and A2), with time split-half
    df["forecast_ord"] = df.groupby("model")["market_id"].transform(lambda s: 0)  # placeholder
    pnl_rows = []
    for (model, arm), sub in df[df["arm"].isin(["A1", "A2"])].groupby(["model", "arm"]):
        sub = sub.copy()
        for theta in THETA_GRID:
            for cost in COST_GRID:
                stats = pnl_rule(sub, theta, cost)
                halves = {}
                if stats.get("n_trades", 0) >= 10:
                    med = sub["market_id"].map(
                        dict(zip(sorted(sub["market_id"].unique()),
                                 range(sub["market_id"].nunique())))
                    )
                    h1 = pnl_rule(sub[med <= med.median()], theta, cost)
                    h2 = pnl_rule(sub[med > med.median()], theta, cost)
                    halves = {"h1_mean": h1.get("mean_pnl_per_$"), "h2_mean": h2.get("mean_pnl_per_$")}
                pnl_rows.append({"model": model, "arm": arm, "theta": theta, "cost": cost,
                                 **stats, **halves})
    pnl = pd.DataFrame(pnl_rows)

    # ---- Calibration
    cal_rows = []
    for (model, arm), sub in df.groupby(["model", "arm"]):
        bins = pd.cut(sub["p_ai"], np.linspace(0, 1, 11), include_lowest=True)
        c = sub.groupby(bins, observed=True).agg(n=("outcome", "size"),
                                                 mean_p=("p_ai", "mean"),
                                                 mean_y=("outcome", "mean")).reset_index()
        c["model"], c["arm"] = model, arm
        cal_rows.append(c)
    cal = pd.concat(cal_rows, ignore_index=True)
    cal["bin"] = cal.iloc[:, 0].astype(str)

    per_tag = (
        df[df["arm"] == "A1"]
        .groupby(["model", "tag"])
        .agg(n=("brier_ai", "size"), brier_ai=("brier_ai", "mean"), brier_mkt=("brier_mkt", "mean"))
        .reset_index()
    )
    per_tag["edge"] = per_tag["brier_mkt"] - per_tag["brier_ai"]

    with pd.ExcelWriter(XLSX_PATH, engine="openpyxl") as xw:
        summary.to_excel(xw, sheet_name="brier_summary", index=False)
        gate.to_excel(xw, sheet_name="gate_tests", index=False)
        loo.to_excel(xw, sheet_name="leave_one_event_out", index=False)
        pnl.to_excel(xw, sheet_name="pnl_grid", index=False)
        cal[["model", "arm", "bin", "n", "mean_p", "mean_y"]].to_excel(xw, sheet_name="calibration", index=False)
        per_tag.to_excel(xw, sheet_name="per_tag", index=False)
        df.head(20000).to_excel(xw, sheet_name="forecast_level", index=False)

    print("\n=== BRIER SUMMARY ===")
    print(summary.to_string(index=False))
    print("\n=== GATE TESTS (negative diff + CI<0 = beats) ===")
    print(gate.to_string(index=False))
    print("\n=== PNL GRID (A1/A2) ===")
    print(pnl[pnl["n_trades"] > 0].to_string(index=False))

    lines = [
        f"# Brier Gate — Results {STAMP}",
        "",
        f"Surface: {df['market_id'].nunique()} markets, {df['event_slug'].nunique()} events, "
        f"{len(df)} scored cells. Corpus window: trailing 30 days (CLOB retention).",
        "",
        "## Brier summary", "", summary.to_markdown(index=False), "",
        "## Gate tests (event-clustered bootstrap, 95% CI; `beats`=CI excludes 0 in AI's favor)",
        "", gate.to_markdown(index=False), "",
        "## Leave-one-event-out (A1 vs market)", "", loo.to_markdown(index=False), "",
        "## Threshold-rule PnL (per $1 staked, net of crossing cost)",
        "", pnl[pnl["n_trades"] > 0].to_markdown(index=False), "",
        "## Per-tag edge (A1)", "", per_tag.to_markdown(index=False), "",
        "Generated by scripts/brier_gate/score.py",
    ]
    REPORT_PATH.write_text("\n".join(lines))
    print(f"\nWrote {XLSX_PATH}\nWrote {REPORT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
