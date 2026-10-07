#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/train_floor.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v1/feature_panel_v1.parquet
    Model-ready panel from build_panel.py: one row per (date, country), 256
    factor columns with publication lags applied, target fwd_excess =
    next-month return minus the equal-weight average of all countries.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/factor_set_v1.json
    The factor list (names, sources) that defines the feature columns.

OUTPUT FILES (inside
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/floor_<YYYYMMDD_HHMMSS>/ ):
- per_split.parquet / per_split.xlsx   one row per (split, model, train|eval) with every metric
- monthly.parquet                      per (split, model, set, month): top-8 excess, soft-k excess,
                                       precision@8, rank IC, effective N
- predictions_eval.parquet             per (split, model, date, country): score and realized excess
- ridge_alpha_grid.parquet             inner-CV objective for every alpha, per split
- lgbm_importance.parquet              gain importance of the regression model, averaged over splits
- summary.json                         aggregate results and the run configuration
- heartbeat.json                       progress (split / model / elapsed / ETA), rewritten after every fit
- run.log

VERSION: 1.0
LAST UPDATED: 2026-10-07
AUTHOR: Claude (Fable 5.1) for Arjun Divecha

DESCRIPTION:
The "floor" for the country top-8 ranking model: how well do a regularized
linear model and gradient-boosted trees do on Arjun's objective, before any
neural network is tried. Everything later has to beat these numbers.

Objective (Arjun, 2026-10-07): equal-weight top-8 countries by model score
versus the equal-weight average of all countries, next month. Reported as
annualized excess return (mean monthly excess x 12), its t-stat over months,
and the hit rate (share of months the basket beats the average). Because
Arjun said eight need not be rigid, every model is also scored through the
same soft top-k allocation (memberships in (0,1) summing to k via a sigmoid
threshold on within-month z-scored model scores, weights = membership / k, so
no country exceeds 1/k), at two softness settings, with the effective number
of holdings 1 / sum(w^2). Rank IC and precision@8 (how many of the realized
top 8 the model caught) are secondary diagnostics.

Models:
  ridge                 sklearn Ridge on clipped (+/-5) zero-imputed z-scores plus
                        per-source "fraction of block present" columns; alpha chosen
                        by 5-fold month-grouped CV inside the training months on
                        the top-8 objective.
  lgbm_regression       LightGBM L2 regression on fwd_excess (raw NaN handling).
  lgbm_top8_classifier  LightGBM binary: was the country in the realized top 8.
  lgbm_lambdarank       LightGBM lambdarank, one query per month, labels = within-
                        month deciles of fwd_excess, NDCG truncated at 8.
  The three LightGBM models early-stop on a 12% slice of TRAINING months; the
  evaluation months are never used for stopping or selection.

Evaluation protocol:
  - 30 random 80/20 month splits (all 34 countries of a month on the same
    side), seeds 0..29. Arjun's "many versions of the database" idea: the
    same months, re-partitioned; every model sees the same splits so model
    differences are paired.
  - 5 contiguous blocks (each ~64-month block held out once) as a diagnostic
    for how much of the random-month score is temporal proximity.
  - Shuffled-label control: ridge and lgbm_regression refit on the first 10
    random splits with fwd_excess permuted across countries within each
    training month; evaluation on true labels should sit at zero.
  - Reference: the best single factor from the screen (REER_CS) scored the
    same way on the same evaluation months.

Results are written incrementally after every split (checkpoint parquet and
heartbeat) so a crash loses at most one split.

DEPENDENCIES: pandas, numpy, scipy, scikit-learn, lightgbm, pyarrow, xlsxwriter (experiment .venv)

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model"
  .venv/bin/python train_floor.py
  .venv/bin/python train_floor.py --n-random 10 --n-blocks 5 --k 8 --threads 16
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy import stats as sstats
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold

EXP_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model")
PANEL = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v1/feature_panel_v1.parquet")
FACTOR_SET = EXP_DIR / "factor_set_v1.json"
RESULTS_ROOT = EXP_DIR / "results"
REFERENCE_FACTOR = "REER_CS"
RIDGE_ALPHAS = [1.0, 10.0, 100.0, 1000.0, 10000.0]
SOFT_TAUS = [0.25, 1.0]          # on within-month z-scored model scores; smaller = closer to hard top-k

log = logging.getLogger("train_floor")


# ── scoring ──────────────────────────────────────────────────────────────────
def soft_topk(z: np.ndarray, k: int, tau: float) -> np.ndarray:
    """Memberships in (0,1) summing to k: sigmoid((z - b)/tau) with b found by bisection."""
    lo, hi = z.min() - 20 * tau, z.max() + 20 * tau
    for _ in range(80):
        b = 0.5 * (lo + hi)
        s = 1.0 / (1.0 + np.exp(-(z - b) / tau))
        if s.sum() > k:
            lo = b
        else:
            hi = b
    return 1.0 / (1.0 + np.exp(-(z - 0.5 * (lo + hi)) / tau))


def month_metrics(scores: np.ndarray, y: np.ndarray, month_id: np.ndarray, k: int) -> pd.DataFrame:
    """Per-month metrics for one set of scores."""
    rows = []
    order_all = np.argsort(month_id, kind="stable")
    scores, y, month_id = scores[order_all], y[order_all], month_id[order_all]
    bounds = np.flatnonzero(np.diff(month_id)) + 1
    for s, e in zip(np.r_[0, bounds], np.r_[bounds, len(y)]):
        sc, yy = scores[s:e], y[s:e]
        n = len(yy)
        if n < 2 * k:
            continue
        top_pred = np.argsort(-sc, kind="stable")[:k]
        top_real = set(np.argsort(-yy, kind="stable")[:k])
        rec = {"month_id": int(month_id[s]), "n": n,
               "top8_excess": float(yy[top_pred].mean()),
               "bottom8_excess": float(yy[np.argsort(sc, kind="stable")[:k]].mean()),
               "precision8": len(set(top_pred) & top_real) / k,
               "rank_ic": float(sstats.spearmanr(sc, yy)[0]) if np.std(sc) > 0 else 0.0}
        sd = sc.std()
        z = (sc - sc.mean()) / sd if sd > 0 else np.zeros_like(sc)
        for tau in SOFT_TAUS:
            w = soft_topk(z, k, tau) / k
            rec[f"soft_excess_tau{tau}"] = float((w * yy).sum())
            rec[f"neff_tau{tau}"] = float(1.0 / (w ** 2).sum())
        rows.append(rec)
    return pd.DataFrame(rows)


def tstat(x: pd.Series) -> float:
    x = x.dropna()
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 and x.std(ddof=1) > 0 else float("nan")


def aggregate(mm: pd.DataFrame) -> dict:
    out = {"n_months": int(len(mm)),
           "top8_excess_ann_pct": float(mm["top8_excess"].mean() * 1200),
           "top8_t": tstat(mm["top8_excess"]),
           "top8_hit_rate": float((mm["top8_excess"] > 0).mean()),
           "bottom8_excess_ann_pct": float(mm["bottom8_excess"].mean() * 1200),
           "ls_spread_ann_pct": float((mm["top8_excess"] - mm["bottom8_excess"]).mean() * 1200),
           "precision8": float(mm["precision8"].mean()),
           "rank_ic": float(mm["rank_ic"].mean()),
           "rank_ic_t": tstat(mm["rank_ic"])}
    for tau in SOFT_TAUS:
        out[f"soft_excess_ann_pct_tau{tau}"] = float(mm[f"soft_excess_tau{tau}"].mean() * 1200)
        out[f"soft_t_tau{tau}"] = tstat(mm[f"soft_excess_tau{tau}"])
        out[f"neff_tau{tau}"] = float(mm[f"neff_tau{tau}"].mean())
    return out


# ── models ───────────────────────────────────────────────────────────────────
def fit_ridge(Xtr, ytr, mtr, Xev, k, seed, alphas=RIDGE_ALPHAS):
    """Alpha by 5-fold month-grouped CV on the top-8 objective, then refit on all training rows."""
    gkf = GroupKFold(n_splits=5)
    grid = []
    for a in alphas:
        vals = []
        for itr, iva in gkf.split(Xtr, ytr, groups=mtr):
            m = Ridge(alpha=a).fit(Xtr[itr], ytr[itr])
            mm = month_metrics(m.predict(Xtr[iva]), ytr[iva], mtr[iva], k)
            vals.append(mm["top8_excess"].mean())
        grid.append({"alpha": a, "inner_top8_excess_ann_pct": float(np.mean(vals) * 1200)})
    best = max(grid, key=lambda r: r["inner_top8_excess_ann_pct"])["alpha"]
    m = Ridge(alpha=best).fit(Xtr, ytr)
    return m.predict(Xtr), m.predict(Xev), {"alpha": best, "grid": grid, "coef": m.coef_}


def _inner_split(mtr: np.ndarray, frac: float, seed: int):
    months = np.unique(mtr)
    rng = np.random.default_rng(seed + 1000)
    val = set(rng.permutation(months)[: max(3, int(round(frac * len(months))))])
    isval = np.isin(mtr, list(val))
    return ~isval, isval


def _lgbm_params(objective: str, seed: int, threads: int) -> dict:
    p = {"objective": objective, "learning_rate": 0.03, "num_leaves": 15, "min_child_samples": 50,
         "feature_fraction": 0.5, "bagging_fraction": 0.7, "bagging_freq": 1, "lambda_l2": 10.0,
         "max_bin": 63, "verbose": -1, "num_threads": threads, "seed": seed, "deterministic": True}
    if objective == "lambdarank":
        p.update({"metric": "ndcg", "eval_at": [8], "lambdarank_truncation_level": 10})
    elif objective == "binary":
        p.update({"metric": "binary_logloss"})
    else:
        p.update({"metric": "l2"})
    return p


def fit_lgbm(kind, Xtr, ytr, mtr, Xev, feat_names, k, seed, threads, labels=None):
    """kind in {regression, binary, lambdarank}; labels overrides ytr for binary/lambdarank."""
    fit_mask, val_mask = _inner_split(mtr, 0.12, seed)
    target = ytr if labels is None else labels
    params = _lgbm_params(kind, seed, threads)
    kw = {}
    if kind == "lambdarank":
        g_fit = pd.Series(mtr[fit_mask]).groupby(mtr[fit_mask], sort=False).size().to_numpy()
        g_val = pd.Series(mtr[val_mask]).groupby(mtr[val_mask], sort=False).size().to_numpy()
        dtr = lgb.Dataset(Xtr[fit_mask], target[fit_mask], group=g_fit, feature_name=feat_names, free_raw_data=False)
        dva = lgb.Dataset(Xtr[val_mask], target[val_mask], group=g_val, reference=dtr, feature_name=feat_names)
    else:
        dtr = lgb.Dataset(Xtr[fit_mask], target[fit_mask], feature_name=feat_names, free_raw_data=False)
        dva = lgb.Dataset(Xtr[val_mask], target[val_mask], reference=dtr, feature_name=feat_names)
    booster = lgb.train(params, dtr, num_boost_round=3000, valid_sets=[dva],
                        callbacks=[lgb.early_stopping(100, verbose=False)], **kw)
    it = booster.best_iteration or booster.current_iteration()
    imp = pd.Series(booster.feature_importance("gain"), index=feat_names)
    return (booster.predict(Xtr, num_iteration=it), booster.predict(Xev, num_iteration=it),
            {"best_iteration": int(it), "importance": imp})


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", type=Path, default=PANEL)
    ap.add_argument("--factor-set", type=Path, default=FACTOR_SET)
    ap.add_argument("--n-random", type=int, default=30)
    ap.add_argument("--eval-frac", type=float, default=0.20)
    ap.add_argument("--n-blocks", type=int, default=5, help="contiguous blocks (>= 2; each held out once)")
    ap.add_argument("--n-shuffle", type=int, default=10, help="random splits on which to run the shuffled-label control")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--tag", default="", help="ablation tag; run dir becomes floor_<ts>_<tag> and the report lists it separately")
    ap.add_argument("--no-presence", action="store_true", help="drop the per-source 'fraction present' columns from every model")
    args = ap.parse_args()
    if args.n_blocks < 2:
        ap.error("--n-blocks must be >= 2 (one block would hold out every month)")

    t0 = time.time()
    run_dir = RESULTS_ROOT / (f"floor_{datetime.now().strftime('%Y%m%d_%H%M%S')}" + (f"_{args.tag}" if args.tag else ""))
    run_dir.mkdir(parents=True, exist_ok=False)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    log.setLevel(logging.INFO)
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler(run_dir / "run.log")):
        h.setFormatter(fmt)
        log.addHandler(h)
    log.info("run dir: %s", run_dir)

    # ── data ────────────────────────────────────────────────────────────────
    fs = json.load(open(args.factor_set))
    feats = [f["variable"] for f in fs["factors"]]
    src_of = {f["variable"]: f["source"] for f in fs["factors"]}
    panel = pd.read_parquet(args.panel).sort_values(["date", "country"]).reset_index(drop=True)
    months = np.sort(panel["date"].unique())
    month_id = panel["date"].map({m: i for i, m in enumerate(months)}).to_numpy()
    y = panel["fwd_excess"].to_numpy(float)

    sources = [] if args.no_presence else sorted(set(src_of.values()))
    present = pd.DataFrame({f"present_{s}": panel[[v for v in feats if src_of[v] == s]].notna().mean(axis=1)
                            for s in sources}, index=panel.index)
    X_raw = panel[feats].to_numpy(float)
    X_tree = np.hstack([X_raw, present.to_numpy(float)])
    X_ridge = np.hstack([np.nan_to_num(np.clip(X_raw, -5, 5), nan=0.0), present.to_numpy(float)])
    feat_names = [f"f{i}" for i in range(len(feats))] + list(present.columns)
    name_map = dict(zip(feat_names, feats + list(present.columns)))

    # realized labels for the classifier / ranker
    rank_desc = panel.groupby("date")["fwd_excess"].rank(ascending=False, method="first")
    n_in_month = panel.groupby("date")["fwd_excess"].transform("size")
    label_top8 = (rank_desc <= args.k).astype(int).to_numpy()
    label_decile = np.clip(np.floor((n_in_month - rank_desc) / n_in_month * 10), 0, 9).astype(int).to_numpy()
    has_ref = REFERENCE_FACTOR in panel.columns
    ref_score = panel[REFERENCE_FACTOR].fillna(0.0).to_numpy(float) if has_ref else None
    if not has_ref:
        log.warning("reference factor %s is not in this panel (ablation?) -- reference rows skipped", REFERENCE_FACTOR)

    log.info("panel: %d rows, %d months, %d features (+%d block-presence cols), target std %.4f",
             len(panel), len(months), len(feats), len(sources), y.std())

    # ── splits ──────────────────────────────────────────────────────────────
    splits = []
    n_eval = int(round(args.eval_frac * len(months)))
    for i in range(args.n_random):
        perm = np.random.default_rng(args.seed + i).permutation(len(months))
        ev = np.zeros(len(months), bool)
        ev[perm[:n_eval]] = True
        splits.append((f"random_{i}", "random", ev))
    edges = np.linspace(0, len(months), args.n_blocks + 1).astype(int)
    for b in range(args.n_blocks):
        ev = np.zeros(len(months), bool)
        ev[edges[b]:edges[b + 1]] = True
        splits.append((f"block_{b}", "blocked", ev))
    log.info("splits: %d random (%d eval months each) + %d blocked", args.n_random, n_eval, args.n_blocks)

    models = ["ridge", "lgbm_regression", "lgbm_top8_classifier", "lgbm_lambdarank"]
    total_fits = len(splits) * len(models) + args.n_shuffle * 2
    done = 0
    per_split, monthly, preds, alpha_grid, importances = [], [], [], [], []

    def heartbeat(split_name, model):
        el = time.time() - t0
        (run_dir / "heartbeat.json").write_text(json.dumps({
            "split": split_name, "model": model, "fits_done": done, "fits_total": total_fits,
            "elapsed_s": round(el), "eta_s": round(el / done * (total_fits - done)) if done else None,
            "updated": datetime.now().isoformat(timespec="seconds")}, indent=2))

    def record(split_name, split_type, model, s_tr, s_ev, tr, ev, info=None):
        for set_name, sc, mask in (("train", s_tr, tr), ("eval", s_ev, ev)):
            mm = month_metrics(sc, y[mask], month_id[mask], args.k)
            if mm.empty:
                log.warning("%s/%s/%s: no scorable months -- skipped", split_name, model, set_name)
                continue
            agg = aggregate(mm)
            agg.update({"split": split_name, "split_type": split_type, "model": model, "set": set_name})
            if info:
                agg.update({kk: vv for kk, vv in info.items() if kk in ("alpha", "best_iteration")})
            per_split.append(agg)
            mm.insert(0, "set", set_name); mm.insert(0, "model", model); mm.insert(0, "split", split_name)
            mm["date"] = months[mm["month_id"].to_numpy()]
            monthly.append(mm)
        preds.append(pd.DataFrame({"split": split_name, "model": model, "date": panel["date"][ev].to_numpy(),
                                   "country": panel["country"][ev].to_numpy(), "score": s_ev, "fwd_excess": y[ev]}))

    def checkpoint():
        pd.DataFrame(per_split).to_parquet(run_dir / "per_split.parquet", index=False)
        pd.concat(monthly, ignore_index=True).to_parquet(run_dir / "monthly.parquet", index=False)

    # ── main loop ───────────────────────────────────────────────────────────
    for split_name, split_type, ev_months in splits:
        ev = ev_months[month_id]
        tr = ~ev
        seed = args.seed + int(split_name.split("_")[1]) + (100 if split_type == "blocked" else 0)
        ts = time.time()

        # reference single factor, no fitting
        if has_ref:
            record(split_name, split_type, "reference_REER_CS", ref_score[tr], ref_score[ev], tr, ev)

        s_tr, s_ev, info = fit_ridge(X_ridge[tr], y[tr], month_id[tr], X_ridge[ev], args.k, seed)
        record(split_name, split_type, "ridge", s_tr, s_ev, tr, ev, info)
        alpha_grid.extend({"split": split_name, **g} for g in info["grid"])
        done += 1; heartbeat(split_name, "ridge")

        for model, kind, labels in (("lgbm_regression", "regression", None),
                                    ("lgbm_top8_classifier", "binary", label_top8),
                                    ("lgbm_lambdarank", "lambdarank", label_decile)):
            s_tr, s_ev, info = fit_lgbm(kind, X_tree[tr], y[tr], month_id[tr], X_tree[ev], feat_names,
                                        args.k, seed, args.threads, None if labels is None else labels[tr])
            record(split_name, split_type, model, s_tr, s_ev, tr, ev, info)
            if model == "lgbm_regression":
                importances.append(info["importance"].rename(split_name))
            done += 1; heartbeat(split_name, model)

        # shuffled-label control on the first n_shuffle random splits
        if split_type == "random" and int(split_name.split("_")[1]) < args.n_shuffle:
            rng = np.random.default_rng(seed + 7)
            y_sh = y.copy()
            for m in np.unique(month_id[tr]):
                idx = np.flatnonzero((month_id == m) & tr)
                y_sh[idx] = y_sh[rng.permutation(idx)]
            s_tr, s_ev, info = fit_ridge(X_ridge[tr], y_sh[tr], month_id[tr], X_ridge[ev], args.k, seed)
            record(split_name, split_type, "ridge_shuffled", s_tr, s_ev, tr, ev, info)
            done += 1; heartbeat(split_name, "ridge_shuffled")
            s_tr, s_ev, info = fit_lgbm("regression", X_tree[tr], y_sh[tr], month_id[tr], X_tree[ev],
                                        feat_names, args.k, seed, args.threads)
            record(split_name, split_type, "lgbm_regression_shuffled", s_tr, s_ev, tr, ev, info)
            done += 1; heartbeat(split_name, "lgbm_regression_shuffled")

        checkpoint()
        ev_rows = [r for r in per_split if r["split"] == split_name and r["set"] == "eval"]
        log.info("%-9s done in %5.1fs | eval top-8 excess %%/yr: %s", split_name, time.time() - ts,
                 ", ".join(f"{r['model']}={r['top8_excess_ann_pct']:+.1f}" for r in ev_rows))

    # ── outputs ─────────────────────────────────────────────────────────────
    ps = pd.DataFrame(per_split)
    ps.to_parquet(run_dir / "per_split.parquet", index=False)
    with pd.ExcelWriter(run_dir / "per_split.xlsx", engine="xlsxwriter") as xw:
        ps.to_excel(xw, sheet_name="per_split", index=False, na_rep="—")
        pd.DataFrame(alpha_grid).to_excel(xw, sheet_name="ridge_alpha_grid", index=False)
    pd.concat(monthly, ignore_index=True).to_parquet(run_dir / "monthly.parquet", index=False)
    pd.concat(preds, ignore_index=True).to_parquet(run_dir / "predictions_eval.parquet", index=False)
    pd.DataFrame(alpha_grid).to_parquet(run_dir / "ridge_alpha_grid.parquet", index=False)
    imp = pd.concat(importances, axis=1)
    imp_out = pd.DataFrame({"feature": [name_map[f] for f in imp.index],
                            "gain_mean": imp.mean(axis=1).to_numpy(), "gain_sd": imp.std(axis=1).to_numpy()})
    imp_out["gain_share"] = imp_out["gain_mean"] / imp_out["gain_mean"].sum()
    imp_out.sort_values("gain_mean", ascending=False).to_parquet(run_dir / "lgbm_importance.parquet", index=False)

    key = ["top8_excess_ann_pct", "top8_t", "top8_hit_rate", "precision8", "rank_ic",
           f"soft_excess_ann_pct_tau{SOFT_TAUS[0]}", f"soft_excess_ann_pct_tau{SOFT_TAUS[1]}",
           f"neff_tau{SOFT_TAUS[0]}", f"neff_tau{SOFT_TAUS[1]}"]
    summary_tbl = (ps.groupby(["split_type", "set", "model"])[key]
                   .agg(["mean", "std", "min", "max"]).round(4))
    summary_tbl.columns = ["_".join(c) for c in summary_tbl.columns]
    summary_tbl = summary_tbl.reset_index()

    # noise floor: SE of the mean monthly excess of an 8-pick basket over one eval set
    nf_model = "reference_REER_CS" if has_ref else "ridge"
    sd_month = pd.concat(monthly)[lambda d: (d.model == nf_model) & (d.set == "eval")]["top8_excess"].std()
    summary = {
        "run_dir": str(run_dir), "panel": str(args.panel), "factor_set": str(args.factor_set), "tag": args.tag,
        "config": vars(args) | {"ridge_alphas": RIDGE_ALPHAS, "soft_taus": SOFT_TAUS,
                                "reference_factor": REFERENCE_FACTOR if has_ref else None},
        "n_rows": int(len(panel)), "n_months": int(len(months)), "n_features": len(feats),
        "n_eval_months_random": n_eval, "models": models,
        "summary_table": summary_tbl.to_dict("records"),
        "noise_floor": {"monthly_sd_top8_excess": float(sd_month),
                        "se_ann_pct_random_split": float(sd_month / np.sqrt(n_eval) * 1200),
                        "note": "standard error of the annualized eval top-8 excess for one random split"},
        "ridge_alpha_chosen": ps[(ps.model == "ridge") & (ps.set == "eval")].groupby("split")["alpha"].first().to_dict(),
        "lgbm_best_iterations": ps[ps.model.str.startswith("lgbm") & (ps.set == "eval")]
                                  .groupby("model")["best_iteration"].agg(["mean", "min", "max"]).round(0).to_dict("index"),
        "elapsed_s": round(time.time() - t0, 1),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    heartbeat("done", "done")
    ev = ps[(ps.set == "eval") & (ps.split_type == "random")].groupby("model")["top8_excess_ann_pct"].agg(["mean", "std"]).round(2)
    log.info("random-split EVAL top-8 excess %%/yr (mean, sd over splits):\n%s", ev.to_string())
    log.info("done in %.1f min", (time.time() - t0) / 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
