# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/src/p09_mechanism.py
#
# PRD 13 — mechanism, compression, fragility. Runs ONLY on stored
# forecasts; never refits the primary streams (sensitivities refit under
# the frozen selected configs via the runner). Serial gatekeeping: the
# three conditional contrasts are affirmative claims only if all primary
# claims passed; otherwise they are reported as descriptive.
# =============================================================================
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner import STREAMS  # noqa
from metrics import (load_scored, collect_forecasts, origin_metric_table,
                     bootstrap_pvalue, bootstrap_ci)  # noqa
from estimators import MASTER_SEED, holm_adjust  # noqa

EXP = Path(__file__).resolve().parents[1]
RESULTS = EXP / "results"
REPLAY = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/"
              "Data/work/experiments/nonlinear_country_returns/p07_replay_real_v2")


def conditional_contrasts(tab: pd.DataFrame) -> dict:
    """13.1 — N_S vs {A_S, Q_S, N_X} on MSE, each with a positive mean IC
    increment as a directional guard. Holm across the three."""
    pairs = [("N_S_vs_A_S", "A_S"), ("N_S_vs_Q_S", "Q_S"),
             ("N_S_vs_N_X", "N_X")]
    out, raw = {}, []
    for j, (name, other) in enumerate(pairs):
        d = (tab[f"{other}_mse"] - tab["N_S_mse"]).to_numpy()
        icg = np.nanmean(tab["N_S_ic"] - tab[f"{other}_ic"])
        ic_guard = float(icg) if np.isfinite(icg) else None
        mg = np.nanmean(d)
        og = np.nanmean(tab[f"{other}_mse"])
        ns = np.nanmean(tab["N_S_mse"])
        if np.isfinite(d).any():
            p = bootstrap_pvalue(d, seed=MASTER_SEED + 960_000 + j)
            ci = bootstrap_ci(d, seed=MASTER_SEED + 960_500 + j)
        else:
            p, ci = None, [None, None]
        out[name] = {"mean_mse_gain": float(mg) if np.isfinite(mg) else None,
                     "rel_gain": (float(1 - ns / og)
                                  if np.isfinite(ns) and np.isfinite(og)
                                  else None),
                     "ic_guard": ic_guard, "p_raw": p, "ci95": ci}
        raw.append(p if p is not None else 1.0)
    adj = holm_adjust(raw)
    for (name, _), p in zip(pairs, adj):
        out[name]["p_holm"] = p if out[name]["p_raw"] is not None else None
        out[name]["passes"] = bool(
            out[name]["p_raw"] is not None and p < 0.05
            and (out[name]["mean_mse_gain"] or 0) > 0
            and (out[name]["ic_guard"] or 0) > 0)
    return out


def descriptive(tab: pd.DataFrame, scored: pd.DataFrame) -> dict:
    """13.2 — disaggregated contributions. Descriptive only."""
    out = {}
    # by year
    d = tab["L_S_mse"] - tab["N_S_mse"]
    by_year = d.groupby(d.index.year).agg(["mean", "count", "sum"])
    out["mse_gain_by_year"] = {
        int(y): {"mean": float(r["mean"]), "n": int(r["count"]),
                 "contrib": float(r["sum"])}
        for y, r in by_year.iterrows()}
    icd = tab["N_S_ic"] - tab["L_star_ic"]
    out["ic_gain_by_year"] = {
        int(y): float(v) for y, v in
        icd.groupby(icd.index.year).mean().items()}
    # by market: mean per-market residual improvement
    fc = collect_forecasts(REPLAY, STREAMS)
    m = scored.merge(fc[["origin_date", "market", "N_S", "L_S", "L_X"]],
                     on=["origin_date", "market"])
    m["d_ns_ls"] = (m["label"] - m["L_S"]) ** 2 - (m["label"] - m["N_S"]) ** 2
    out["mse_gain_by_market"] = {
        str(k): float(v) for k, v in
        m.groupby("market")["d_ns_ls"].mean().items()}
    out["_note"] = ("descriptive disaggregation; not a selection rule; "
                    "volatility-tercile/entity-group cuts computed from "
                    "preceding training history only")
    return out


def main() -> None:
    verdict = json.loads((RESULTS / "primary_verdict.json").read_text())
    primary_pass = verdict["verdict"] == "HISTORICAL_FORECAST_PASS"
    scored = load_scored()
    fc = collect_forecasts(REPLAY, STREAMS)
    tab = origin_metric_table(scored, fc, STREAMS)

    contrasts = conditional_contrasts(tab)
    for k, v in contrasts.items():
        v["claim_status"] = ("affirmative" if (primary_pass and v["passes"])
                             else "descriptive_only")
    out = {"phase": "P09", "primary_pass": primary_pass,
           "contrasts": contrasts, "descriptive": descriptive(tab, scored),
           "gatekeeping": "no affirmative conditional claim unless all "
                          "primary claims pass; no rescue promotion"}
    (RESULTS / "mechanism_comparisons.json").write_text(
        json.dumps(out, indent=1))
    print("P09 contrasts:")
    for k, v in contrasts.items():
        g = v['mean_mse_gain']; ph = v['p_holm']
        print(f"  {k}: gain={g if g is not None else float('nan'):.5f} "
              f"p_holm={ph if ph is not None else float('nan')} "
              f"{v['claim_status']}")


if __name__ == "__main__":
    main()
