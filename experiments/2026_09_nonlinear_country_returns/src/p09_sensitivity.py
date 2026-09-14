# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/src/p09_sensitivity.py
#
# PRD 13.3 — frozen sensitivity set. Refits use the ALREADY-SELECTED
# configurations from the primary run (no retuning, no outer-outcome
# selection). Implemented here:
#   * leave-one-training-year-out refits (all streams that were selected)
#   * leave-one-region-out refits (P01 draft_region map)
#   * fixed 5/63-session outcome associations of the 20-session scores
#   * 126-origin inference blocks (already in p08 stability output)
#   * one-source-session lag: requires a P03 feature variant; recorded as a
#     manifest entry (built by p09_lag_variant.py when run)
#   * network placebo: manifest only — 20-seed neighbor-weight permutation
#     rebuild of P05/P06 (heavy; run separately via p09_placebo.py)
# =============================================================================
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from runner import ReplayRunner, STREAMS, feature_matrix, TREE_MODELS  # noqa
from metrics import (load_scored, collect_forecasts, origin_metric_table,
                     spearman_by_origin)  # noqa

EXP = Path(__file__).resolve().parents[1]
AUDIT = EXP / "audit"
RESULTS = EXP / "results"
REPLAY = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/"
              "Data/work/experiments/nonlinear_country_returns/"
              "p07_replay_real_v2")
SCRATCH = REPLAY.parent / "p09_sens"


def frozen_selections() -> dict:
    """The selected config per (fit, model) from the primary run."""
    out = {}
    for p in sorted(REPLAY.glob("fit_*.json")):
        rec = json.loads(p.read_text())
        out[rec["fit_cutoff"]] = rec["selected"]
    return out


def refit_with_filter(name: str, train_filter) -> pd.DataFrame:
    """Refit every scheduled fit with the frozen selected configs under the
    given training-row filter; return the combined forecast frame."""
    run_dir = SCRATCH / name
    run_dir.mkdir(parents=True, exist_ok=True)
    r = ReplayRunner(run_dir, tag=f"sens_{name}", quiet=True,
                     train_filter=train_filter)
    parts = []
    sels = frozen_selections()
    for fs in r.splits["outer_fits"]:
        c = fs["fit_cutoff"]
        sel = sels[c]
        try:
            rec = r.run_fit(fs, sel)
        except Exception as e:
            rec = {"fit_cutoff": c, "selected": {},
                   "support_failure": str(e), "forecasts": None}
            (run_dir / f"fit_{c}.json").write_text(json.dumps(
                {k: v for k, v in rec.items() if k != "forecasts"},
                indent=1, default=str))
            continue
        rec.pop("forecasts").to_parquet(run_dir / f"forecasts_{c}.parquet",
                                        index=False)
        (run_dir / f"fit_{c}.json").write_text(json.dumps(
            rec, indent=1, default=str))
        parts.append(pd.read_parquet(run_dir / f"forecasts_{c}.parquet"))
    if not parts:
        return pd.DataFrame()
    fc = pd.concat(parts, ignore_index=True)
    fc["origin_date"] = pd.to_datetime(fc["origin_date"])
    return fc


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    scored = load_scored()
    base_fc = collect_forecasts(REPLAY, STREAMS)
    base_tab = origin_metric_table(scored, base_fc, STREAMS)
    out = {"phase": "P09-13.3", "runs": {}}

    years = sorted(scored["origin_date"].dt.year.unique())
    mm = pd.read_csv(AUDIT / "market_map.csv")
    regions = sorted(mm["draft_region"].dropna().unique())
    reg_map = dict(zip(mm["market"], mm["draft_region"]))

    # ---- leave-one-training-year-out ------------------------------------
    train_years = list(range(2012, 2027))
    for y in train_years:
        fc = refit_with_filter(
            f"omit_year_{y}",
            lambda df, y=y: df["origin_date"].dt.year != y)
        if fc.empty:
            out["runs"][f"omit_year_{y}"] = {"status": "no_forecasts"}
            continue
        tab = origin_metric_table(scored, fc, STREAMS)
        out["runs"][f"omit_year_{y}"] = {
            "status": "ok",
            "delta_mse_LS": float(np.nanmean(tab["L_S_mse"]
                                             - base_tab["L_S_mse"])),
            "delta_ic_LS": float(np.nanmean(tab["L_S_ic"]
                                            - base_tab["L_S_ic"])),
        }
        print(f"omit {y}: dMSE(L_S)={out['runs'][f'omit_year_{y}']['delta_mse_LS']:+.2e}")

    # ---- leave-one-region-out -------------------------------------------
    for reg in regions:
        mkts = set(mm.loc[mm.draft_region == reg, "market"])
        fc = refit_with_filter(
            f"omit_region_{reg}",
            lambda df, mkts=mkts: ~df["market"].isin(mkts))
        if fc.empty:
            out["runs"][f"omit_region_{reg}"] = {"status": "no_forecasts"}
            continue
        tab = origin_metric_table(scored, fc, STREAMS)
        out["runs"][f"omit_region_{reg}"] = {
            "status": "ok",
            "delta_mse_LS": float(np.nanmean(tab["L_S_mse"]
                                             - base_tab["L_S_mse"])),
            "delta_ic_LS": float(np.nanmean(tab["L_S_ic"]
                                            - base_tab["L_S_ic"])),
        }
        print(f"omit region {reg}: dMSE(L_S)="
              f"{out['runs'][f'omit_region_{reg}']['delta_mse_LS']:+.2e}")

    # ---- fixed 5/63-session associations (descriptive) -------------------
    lab = pd.read_parquet(AUDIT / "labels.parquet")
    lab["origin_date"] = pd.to_datetime(lab["origin_date"])
    assoc = {}
    for hz in ("h5", "h63"):
        lh = lab[lab.horizon == hz][["origin_date", "market", "label"]]
        m = scored[["origin_date", "market"]].merge(
            base_fc[["origin_date", "market", "L_S", "L_X", "L_star"]],
            on=["origin_date", "market"]).merge(
            lh.rename(columns={"label": "label_h"}),
            on=["origin_date", "market"])
        assoc[hz] = {}
        for mdl in ("L_S", "L_X", "L_star"):
            assoc[hz][mdl] = float(spearman_by_origin(
                m.rename(columns={"label_h": "label"}), mdl).mean())
    out["horizon_diagnostics"] = assoc
    out["manifest_notes"] = {
        "one_source_session_lag": "requires lagged P03 feature rebuild; "
                                  "see p09_lag_variant.py",
        "network_placebo": "20-seed neighbor-weight permutation of P05/P06 "
                           "within region/time-zone strata; see "
                           "p09_placebo.py",
        "block126": "reported in results/stability.json",
    }
    (RESULTS / "sensitivity_runs.json").write_text(json.dumps(out, indent=1))
    print("P09 sensitivity complete ->", RESULTS / "sensitivity_runs.json")


if __name__ == "__main__":
    main()
