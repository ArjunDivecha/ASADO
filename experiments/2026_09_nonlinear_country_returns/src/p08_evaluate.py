# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/src/p08_evaluate.py
#
# PRD 12 — primary forecast comparison on the frozen real-label replay.
# Reads stored forecasts only; never refits. Produces:
#   results/origin_metrics.parquet
#   results/primary_comparisons.json   (3 tests, Holm-adjusted, CIs)
#   results/bootstrap_manifest.json    (seeds + block sizes per test)
#   results/coverage.json              (coverage/degeneracy counts)
#   results/primary_verdict.json       (registered gate ladder)
#   results/stability.json             (halves + favorable-year-omission)
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
                     primary_tests, bootstrap_pvalue, bootstrap_ci)  # noqa
from estimators import MASTER_SEED, moving_block_bootstrap  # noqa

EXP = Path(__file__).resolve().parents[1]
RESULTS = EXP / "results"
REPLAY = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/"
              "Data/work/experiments/nonlinear_country_returns/p07_replay_real_v2")


def year_bucket(o):  # calendar-year bucket of an origin
    return pd.Timestamp(o).year


def stability(tab: pd.DataFrame, tests) -> dict:
    """12.4: fixed halves at the calendar midpoint + drop-most-favorable-
    year. Each primary mean increment must stay positive in both halves and
    after dropping its most favorable year bucket."""
    out = {}
    diffs = {
        "mse_gain_vs_L_X": tab["L_X_mse"] - tab["N_S_mse"],
        "mse_gain_vs_L_S": tab["L_S_mse"] - tab["N_S_mse"],
        "ic_gain_vs_L_star": tab["N_S_ic"] - tab["L_star_ic"],
    }
    mid = tab.index[len(tab) // 2]
    for name, d in diffs.items():
        d = d.dropna()
        if d.empty:
            out[name] = {"mean_full": None, "halves_positive": False,
                         "drop_fav_positive": False,
                         "reason": "no paired observations (blocked stream)"}
            continue
        half1 = d[d.index < mid].mean()
        half2 = d[d.index >= mid].mean()
        by_year = d.groupby(d.index.map(year_bucket))
        contrib = by_year.sum()
        fav = contrib.idxmax()
        rest = d[d.index.map(year_bucket) != fav]
        out[name] = {
            "mean_full": float(d.mean()),
            "mean_first_half": float(half1),
            "mean_second_half": float(half2),
            "halves_positive": bool(half1 > 0 and half2 > 0),
            "most_favorable_year": int(fav),
            "mean_without_fav_year": float(rest.mean()),
            "drop_fav_positive": bool(rest.mean() > 0),
            "partial_endpoint_years": sorted(
                set(int(y) for y in d.index.map(year_bucket))),
        }
    return out


def block126_sensitivity(tests_tab: pd.DataFrame) -> dict:
    out = {}
    for name, dcol in (("mse_gain_vs_L_X", ("L_X_mse", "N_S_mse")),
                       ("mse_gain_vs_L_S", ("L_S_mse", "N_S_mse")),
                       ("ic_gain_vs_L_star", ("N_S_ic", "L_star_ic"))):
        d = (tests_tab[dcol[0]] - tests_tab[dcol[1]]
             if "mse" in name else
             tests_tab[dcol[0]] - tests_tab[dcol[1]]).to_numpy()
        out[name] = {"p_block126": bootstrap_pvalue(
            d, block=126, seed=MASTER_SEED + 950_000)}
    return out


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    scored = load_scored()
    fc = collect_forecasts(REPLAY, STREAMS)
    tab = origin_metric_table(scored, fc, STREAMS)
    tab.to_parquet(RESULTS / "origin_metrics.parquet")

    tests = primary_tests(tab)
    comparisons = {"tests": tests,
                   "absolute": {
                       "N_S_mse": float(np.nanmean(tab["N_S_mse"])),
                       "B0_mse": float(np.nanmean(tab["B0_mse"])),
                       "L_star_mse": float(np.nanmean(tab["L_star_mse"])),
                       "N_S_mean_ic": float(np.nanmean(tab["N_S_ic"]))},
                   "bootstrap": {"block": 63, "draws": 5000,
                                 "seed_base": MASTER_SEED + 900_000,
                                 "note": "pointwise 95% intervals; Holm "
                                         "familywise at 0.05 over the "
                                         "three tests"}}
    (RESULTS / "primary_comparisons.json").write_text(
        json.dumps(comparisons, indent=1))

    stab = stability(tab, tests)
    stab["sensitivity_block126"] = block126_sensitivity(tab)
    (RESULTS / "stability.json").write_text(json.dumps(stab, indent=1))

    # coverage / degeneracy
    n_orig = len(tab)
    cov = {
        "n_scored_origins": int(n_orig),
        "n_scored_rows": int(len(scored)),
        "stream_coverage": {m: int((tab[f"{m}_n"] > 0).sum())
                            for m in STREAMS},
        "stream_nan_origins": {m: int(tab[f"{m}_mse"].isna().sum())
                               for m in STREAMS},
        "constant_ic_count": int(sum(
            (tab[f"{m}_ic"] == 0).sum() for m in STREAMS)),
    }
    (RESULTS / "coverage.json").write_text(json.dumps(cov, indent=1))

    # ---- registered gate ladder (12.2) -----------------------------------
    ns_ok = not np.isnan(tab["N_S_mse"]).all()
    m_pair = tab["N_S_mse"].notna()  # paired absolute-usefulness set
    t = {x["name"]: x for x in tests}
    def gte(v, thr):
        return v is not None and v >= thr
    def lt(v, thr):
        return v is not None and v < thr
    gates = {
        "validity": True,  # prior phase gates all PASS
        "mse_vs_LX": (gte(t["mse_gain_vs_L_X"]["rel_gain"], 0.001)
                      and lt(t["mse_gain_vs_L_X"]["p_holm"], 0.05)),
        "mse_vs_LS": (gte(t["mse_gain_vs_L_S"]["rel_gain"], 0.001)
                      and lt(t["mse_gain_vs_L_S"]["p_holm"], 0.05)),
        "ic_vs_Lstar": (gte(t["ic_gain_vs_L_star"]["point"], 0.01)
                        and lt(t["ic_gain_vs_L_star"]["p_holm"], 0.05)),
        "absolute": bool(
            ns_ok and
            tab.loc[m_pair, "N_S_mse"].mean() <
            tab.loc[m_pair, "B0_mse"].mean() and
            tab.loc[m_pair, "N_S_mse"].mean() <
            tab.loc[m_pair, "L_star_mse"].mean() and
            tab.loc[m_pair, "N_S_ic"].mean() > 0),
        "stability": all(stability(tab, tests)[k]["halves_positive"]
                         and stability(tab, tests)[k]["drop_fav_positive"]
                         for k in ("mse_gain_vs_L_X", "mse_gain_vs_L_S",
                                   "ic_gain_vs_L_star")),
        "coverage": ns_ok and cov["stream_coverage"]["N_S"] == n_orig,
    }
    if not ns_ok or cov["stream_coverage"]["N_S"] < n_orig:
        verdict = "INCOMPLETE_REGISTERED_PROCEDURE"
    elif all(gates.values()):
        verdict = "HISTORICAL_FORECAST_PASS"
    else:
        verdict = "NO_ADVANTAGE_DEMONSTRATED"
    v = {"phase": "P08", "verdict": verdict, "gates": gates,
         "note": "gross-only; a valid negative is a successful delivery; "
                 "no rescue promotion, horizon change, or model swap"}
    (RESULTS / "primary_verdict.json").write_text(json.dumps(v, indent=1))
    print("P08 verdict:", verdict)
    for k, g in gates.items():
        print(f"  {k}: {g}")


if __name__ == "__main__":
    main()
