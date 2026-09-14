# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/src/p06_freeze.py
#
# PRD 10 — P06 registration + execution lock.
#
# Freezes the P07 control-generator parameters from the FIRST EIGHT-YEAR
# PRE-OUTER DEVELOPMENT WINDOW ONLY (the first outer fit's training window,
# 2012-07-01..2020-06-30). This is the single permitted use of real
# development-window labels for calibration; genuine outer evaluation rows
# are never read. Emits:
#
#   governance/protocol.lock.json     frozen contract incl. generator params
#   governance/exposure_log.jsonl     prior-exposure record
#   governance/trial_manifest.json    72 candidate configs + fit schedule
#   governance/run_plan.json          P07-P11 execution order
#
# Registration itself is a separate explicit step (register_p06.py) that
# calls scripts/loop/ledgers.py::register_methodology_experiment and writes
# registration_receipt.json.
# =============================================================================
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from estimators import (MASTER_SEED, RIDGE_GRID, TREE_GRID, fit_ridge,
                        predict_ridge, row_weights, fit_fold_scaler,
                        apply_fold_scaler, one_se_select)
from label_store import LabelStore

EXP = Path(__file__).resolve().parents[1]
AUDIT = EXP / "audit"
GOV = EXP / "governance"
REPO = EXP.parents[1]

P_COLS = ["P01", "P02", "P03", "P04", "P05", "P06", "P09", "P10", "P12",
          "P13", "P14", "P15", "P16", "P17", "P18", "P19", "P20",
          "P21", "P22", "P23", "P24"]
S_COLS = ["C01", "C02", "C03", "C04", "C06", "C07", "C08", "C09",
          "C10", "C11", "C12", "G01", "G02", "G03", "G04"]


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_panel():
    X = pd.read_parquet(AUDIT / "features_X.parquet")
    S = pd.read_parquet(AUDIT / "features_S.parquet")
    el = pd.read_parquet(AUDIT / "eligible_rows.parquet")
    for df in (X, S, el):
        df["origin_date"] = pd.to_datetime(df["origin_date"])
    return X, S, el


def dev_frame(X, S, el, labels):
    """Eligible rows in the dev window with mature h20 labels at the first
    fit cutoff. Returns aligned X_raw / S / y / origin_date."""
    el = el[["origin_date", "market"]]
    df = (labels.merge(el, on=["origin_date", "market"], how="inner")
                .merge(X[["origin_date", "market"] + P_COLS],
                       on=["origin_date", "market"], how="left")
                .merge(S[["origin_date", "market"] + S_COLS],
                       on=["origin_date", "market"], how="left"))
    df = df.dropna(subset=P_COLS + S_COLS + ["label"])
    return df.sort_values(["origin_date", "market"]).reset_index(drop=True)


def inner_select_lambda(df, splits, store, el_manifest):
    """Registered L_X inner selection restricted to the first fit's inner
    blocks. Per-origin weighted MSE over the canonical validation origin
    axis; one-SE set; largest lambda."""
    fit0 = splits["outer_fits"][0]
    train_lo = pd.Timestamp(fit0["inner_blocks"][0]["train_lo"])
    origin_axis = np.sort(df["origin_date"].unique())
    oidx = {d: i for i, d in enumerate(origin_axis)}

    losses = {f"{lam:g}": np.full(len(origin_axis), np.nan)
              for lam in RIDGE_GRID}
    for blk in fit0["inner_blocks"]:
        fits = list(blk["inner_fits"])
        ends = fits[1:] + [blk["predict_end"]]
        for fit_d, seg_end in zip(fits, ends):
            fit_d, seg_end = pd.Timestamp(fit_d), pd.Timestamp(seg_end)
            tr = store.read_matured(fit_d, el_manifest, reader="p06_freeze")
            tr = tr[tr["origin_date"] >= train_lo]
            tr = tr.merge(el_manifest, on=["origin_date", "market"])
            trd = df.merge(tr[["origin_date", "market"]],
                           on=["origin_date", "market"])
            if len(trd) < 500:
                continue
            seg = df[(df["origin_date"] >= fit_d) &
                     (df["origin_date"] <= seg_end)]
            if seg.empty:
                continue
            Xtr_raw = trd[P_COLS].to_numpy()
            wtr = np.asarray(row_weights(trd["origin_date"]))
            mu, sd = fit_fold_scaler(Xtr_raw, wtr)
            Xtr = apply_fold_scaler(Xtr_raw, mu, sd)
            ytr = trd["label"].to_numpy()
            Xsg = apply_fold_scaler(seg[P_COLS].to_numpy(), mu, sd)
            ysg = seg["label"].to_numpy()
            og = seg["origin_date"].to_numpy()
            for lam in RIDGE_GRID:
                coef = fit_ridge(Xtr, ytr, wtr, lam)
                resid = ysg - predict_ridge(coef, Xsg)
                # per-origin mean loss over that origin's rows
                ldf = pd.DataFrame({"o": og, "r": resid ** 2})
                per_o = ldf.groupby("o")["r"].mean()
                for o, v in per_o.items():
                    losses[f"{lam:g}"][oidx[np.datetime64(o)]] = v
    sel = one_se_select(losses, set(losses), kind="ridge",
                        seed=MASTER_SEED + 600)
    return float(sel), {k: float(np.nanmean(v)) for k, v in losses.items()}


def main() -> None:
    splits = json.loads((AUDIT / "splits.json").read_text())
    fit0 = splits["outer_fits"][0]
    cutoff = pd.Timestamp(fit0["fit_cutoff"])
    train_lo = pd.Timestamp(fit0["inner_blocks"][0]["train_lo"])

    X, S, el = load_panel()
    store = LabelStore(AUDIT / "labels.parquet",
                       audit_log=AUDIT / "label_reads.jsonl")
    el_manifest = el[["origin_date", "market"]]
    dev_lab = store.read_matured(cutoff, el_manifest, reader="p06_freeze")
    dev_lab = dev_lab[dev_lab["origin_date"] >= train_lo]
    df = dev_frame(X, S, el_manifest, dev_lab)
    print(f"dev rows={len(df)} origins={df.origin_date.nunique()} "
          f"window=[{train_lo.date()},{cutoff.date()})")

    lam_sel, lam_losses = inner_select_lambda(df, splits, store, el_manifest)
    print(f"dev lambda selected: {lam_sel:g}")

    # --- fixed linear mean: full dev-window ridge at selected lambda ------
    X_raw = df[P_COLS].to_numpy()
    w = np.asarray(row_weights(df["origin_date"]))
    mu_s, sd_s = fit_fold_scaler(X_raw, w)
    Xs = apply_fold_scaler(X_raw, mu_s, sd_s)
    y = df["label"].to_numpy()
    coef = fit_ridge(Xs, y, w, lam_sel)
    resid = y - predict_ridge(coef, Xs)
    sigma_noise = float(np.sqrt((w / w.sum() * resid ** 2).sum()))
    # raw-X units: mu = a + X_raw . beta_raw
    beta_raw = coef[1:] / sd_s
    a_raw = float(coef[0] - (coef[1:] * mu_s / sd_s).sum())

    # --- positive-control interaction h = C04*C06, orthogonalized on [1,X]
    h = (df["C04"] * df["C06"]).to_numpy()
    Ah = np.column_stack([np.ones(len(df)), X_raw])
    proj = np.linalg.lstsq(Ah * np.sqrt(w)[:, None], h * np.sqrt(w),
                           rcond=None)[0]
    h_orth = h - Ah @ proj
    sd_h = float(np.sqrt((w / w.sum() * h_orth ** 2).sum()))

    lock = {
        "phase": "P06",
        "frozen_utc": pd.Timestamp.now("UTC").isoformat(),
        "code_commit": "fa7e51d072815abe32f22dd00af1e6334bc49a14",
        "code_integrity_rule": "git diff <code_commit> HEAD -- src/ tests/ spec/ config/ must be empty; P06+ adds governance/ and audit/ artifacts only",
        "amendment": "AM-1 (drop P07/P08 bank-neighbor + P11 fx_rr25_3m; 21 primitives, 15-input S, 22-market universe)",
        "data": {
            "snapshot_dir": "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/nonlinear_country_returns/snapshot_2026_09_13",
            "snapshot_manifest_sha256": sha256_file(AUDIT / "snapshot_manifest.json"),
            "panel_start": splits["panel_start"],
            "feature_panel_start": "2012-01-20",
            "first_outer_fit_cutoff": fit0["fit_cutoff"],
            "last_outer_fit_cutoff": splits["outer_fits"][-1]["fit_cutoff"],
            "last_mature_scored_origin": "2026-08-12",
            "n_outer_fits": splits["n_outer_fits"],
            "n_eligible_rows": 72872,
            "n_scored_origins": 3403,
        },
        "hashes": dict(json.loads((AUDIT / "P04_gate.json").read_text())["hashes"]),
        "file_hashes": {
            "environment_lock": sha256_file(GOV / "environment.lock"),
            "feature_manifest_bound": sha256_file(GOV / "feature_manifest.bound.yaml"),
            "calendar_manifest": sha256_file(AUDIT / "calendar_manifest.json"),
            "market_map": sha256_file(AUDIT / "market_map.csv"),
            "splits": sha256_file(AUDIT / "splits.json"),
            "study_v2_config": None,
        },
        "grids": {
            "ridge_lambdas": [float(x) for x in RIDGE_GRID],
            "tree_grid_max_iter_leaffrac_l2": [list(c) for c in TREE_GRID],
            "models": ["B0", "L_X", "L_S", "L_star", "A_S", "Q_S", "N_S", "N_X"],
            "primary_candidate": "N_S",
            "n_tuned_configs": 72,
        },
        "selection": {
            "rule": "one-SE set via 63-origin moving-block bootstrap, 1000 draws; ridge -> largest lambda; tree -> fewer stages, larger leaf fraction, larger l2, canonical id; L_star exact tie -> L_X",
            "master_seed": MASTER_SEED,
            "bootstrap_block_origins": 63,
            "bootstrap_draws": 1000,
        },
        "leaf_support": {"min_origins": 126, "min_20origin_bins": 12,
                         "min_years": 3, "min_markets": 4},
        "synthetic_generators": {
            "dev_window": [str(train_lo.date()), str(cutoff.date())],
            "dev_rows": int(len(df)),
            "dev_origins": int(df["origin_date"].nunique()),
            "ridge_lambda_selected": lam_sel,
            "ridge_lambda_inner_mean_losses": lam_losses,
            "linear_mean_scaler_mu": mu_s.tolist(),
            "linear_mean_scaler_sd": sd_s.tolist(),
            "linear_mean_coef_scaled": coef.tolist(),
            "linear_mean_beta_raw": beta_raw.tolist(),
            "linear_mean_intercept_raw": a_raw,
            "sigma_noise": sigma_noise,
            "h_definition": "h = C04*C06 (S columns), minus dev-only weighted linear projection on [1, X_raw]",
            "h_projection_coef": proj.tolist(),
            "h_orth_sd": sd_h,
            "ar_coef_common": 0.8, "ar_coef_idio": 0.3,
            "shock_variance_shares": {"common": 0.5, "idio": 0.5},
            "overlap_sum_sessions": 20,
            "q_grid": [0.0, 0.001, 0.005, 0.01, 0.10],
            "q_010_role": "engineering power case (not a primary claim)",
            "replications": 100,
            "inference_calibration_reps": 100,
            "inference_calibration_processes": ["AR(1) phi=0.5", "overlapping-20-innovation"],
            "wilson_gate": "95% lower bound of empirical FWER must be <= 5% nominal; else INVALID_INFERENCE_CALIBRATION",
        },
        "exposure_policy": "a source/code correction after any result exposure = new run/version + exposure event; transient I/O retry capped at 2, no setting changes",
        "status": "LOCKED_PENDING_REGISTRATION",
    }
    (GOV / "protocol.lock.json").write_text(json.dumps(lock, indent=1))
    print("wrote governance/protocol.lock.json")

    # --- exposure log -----------------------------------------------------
    exposure = [
        {"event": "prior_exposure", "id": "M_20260906_001/002/003",
         "what": "MacroState model contest + bounded tree & neural comparison + missingness control (monthly, 12M horizon). WATCH verdicts 2026-09-06.",
         "relation": "same idea family (economic-state compression + shallow interactions), different contract: monthly/12M vs daily/20-session, depth-3/7-leaf vs fixed depth-2/4-leaf grid, no nested PIT selection or formal inference. Not fresh confirmation.",
         "declared_at": "P00"},
        {"event": "prior_exposure", "id": "external:LLM-1M tabular arm",
         "what": "HGB on raw dossier fields, same-universe walk-forward, 1M horizon: OOS IC +0.027, DSR -0.093, WATCH.",
         "relation": "prior trees-on-raw-features evidence at a different horizon; informs N_X expectations.",
         "declared_at": "P00"},
        {"event": "prior_exposure", "id": "external:T2 IPCA factor timing",
         "what": "pooled cross-sectional country predictor; ridge L2 failed OOS, listwise ~0.2 Sharpe pre-DSR.",
         "relation": "prior pooled-model exposure consistent with the nonlinearity hypothesis.",
         "declared_at": "P00"},
        {"event": "prior_exposure", "id": "ledger:graveyard",
         "what": "individual primitives (FX_RR25, FX_CARRY, SOV_2S10S, valuation, consensus) are DEAD as standalone signals.",
         "relation": "study claims pooled NONLINEAR structure, not any single primitive.",
         "declared_at": "P00"},
        {"event": "amendment", "id": "AM-1",
         "what": "dropped P07/P08 (bank-neighbor, 21-market cap) and P11 (3M RR absent; only 1M exists). 21 primitives, 15-input S, 22-market universe, >=20 markets from 2010-07.",
         "relation": "owner-approved spec change before any result exposure; counted as scientific amendment #1.",
         "declared_at": "P01"},
        {"event": "registration", "id": "PENDING",
         "what": "methodology-ledger registration of the locked protocol.",
         "declared_at": "P06"},
    ]
    with open(GOV / "exposure_log.jsonl", "w") as f:
        for e in exposure:
            f.write(json.dumps(e) + "\n")
    print("wrote governance/exposure_log.jsonl")

    # --- trial manifest ---------------------------------------------------
    configs = []
    for name, cols in (("L_X", "X21"), ("L_S", "S15"), ("Q_S", "S135")):
        for lam in [float(x) for x in RIDGE_GRID]:
            configs.append({"model": name, "features": cols,
                            "kind": "ridge", "lambda": lam,
                            "config_id": f"{name}|lam={lam:g}"})
    for name, depth, leaves in (("A_S", 1, 2), ("N_S", 2, 4), ("N_X", 2, 4)):
        feats = "X21" if name == "N_X" else "S15"
        for it, lf, l2 in TREE_GRID:
            configs.append({"model": name, "features": feats, "kind": "tree",
                            "max_iter": it, "leaf_fraction": lf, "l2": l2,
                            "depth": depth, "max_leaf_nodes": leaves,
                            "config_id": f"{name}|it={it}|lf={lf}|l2={l2:g}"})
    assert len(configs) == 72
    manifest = {
        "phase": "P06",
        "learners": {"fixed": ["B0", "L_star"],
                     "tuned": ["L_X", "L_S", "Q_S", "A_S", "N_S", "N_X"]},
        "n_candidate_configs": len(configs),
        "configs": configs,
        "outer_fits": [{"fit_cutoff": f["fit_cutoff"], "retunes": f["retunes"],
                        "n_inner_fits": sum(len(b["inner_fits"])
                                          for b in f.get("inner_blocks", []))}
                       for f in splits["outer_fits"]],
        "planned_fits": "25 outer fits x (8 inner fits at annual retunes) x up to 72 configs; non-July fits reuse selected config",
        "accounting": "nested candidate fits are NOT 72 independent hypothesis claims; full search inventory reported alongside DSR; AM-1 counts as scientific amendment #1",
    }
    (GOV / "trial_manifest.json").write_text(json.dumps(manifest, indent=1))
    print(f"wrote governance/trial_manifest.json ({len(configs)} configs)")

    # --- run plan ----------------------------------------------------------
    plan = {
        "phase": "P06",
        "sequence": [
            {"phase": "P07", "what": "inference calibration (100 null reps, Wilson gate) + linear-world + positive controls (q grid) + historical replay runner (immutable forecast persistence, hash-matched restart, no outer metrics in logs)"},
            {"phase": "P08", "what": "primary outer evaluation on the frozen sample: all 8 streams, per-origin metrics, 63-origin MBB CIs, Holm over 3 primary tests"},
            {"phase": "P09", "what": "mechanism + fragility: horizon diagnostics (5/63 fixed scores), missingness/coverage, one-source-session-lag sensitivity, leaf composition"},
            {"phase": "P10", "what": "portfolio/harness binding: frozen-prediction adapter into native harness OR documented unresolved-native report; gross-only"},
            {"phase": "P11", "what": "final verdict (incl. valid negative), RESULTS.md, model card, REPRODUCE.md, reproduction bundle, methodology verdict via attach_methodology_verdict"},
        ],
        "hard_gates": [
            "no genuine outer metrics before registration receipt exists",
            "BLOCKED_FIT_SUPPORT -> report, never substitute or loosen",
            "INVALID_INFERENCE_CALIBRATION -> inference engine barred from primary claims until repaired and versioned",
            "any post-exposure source/code change = new version + exposure event",
        ],
    }
    (GOV / "run_plan.json").write_text(json.dumps(plan, indent=1))
    print("wrote governance/run_plan.json")
    print("P06 freeze complete — next: register via ledgers.py")


if __name__ == "__main__":
    main()
