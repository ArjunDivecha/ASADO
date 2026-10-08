#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/walk_forward.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v1/feature_panel_v1.parquet
    (or any panel from build_panel.py via --panel / --factor-set)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/factor_set_v1.json
- experiments/2026_10_rank_model/train_nn.py    (imported: train_one, _init_worker — the MLP trainer)
- experiments/2026_10_rank_model/train_floor.py (imported: fit_ridge, month_metrics, aggregate)

OUTPUT FILES (inside
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/walk_<YYYYMMDD_HHMMSS>[_<tag>]/ ):
- monthly_oos.parquet        per (model, rule, month): out-of-sample basket excess, basket and
                             benchmark return, names changed, plus score-based precision@8, rank IC,
                             soft-k excess. rule = plain_top8 or buffer_M<--buffer> (the default headline)
- per_fold.parquet / .xlsx   per (model, rule, fold): the same, aggregated over that fold's 12 months
- by_year.parquet            per (model, rule, year): annualized OOS excess, hit rate
- predictions_oos.parquet    per (model, date, country): score, realized excess
- summary.json, heartbeat.json, run.log

VERSION: 1.0
LAST UPDATED: 2026-10-07
AUTHOR: Claude (Fable 5.1) for Arjun Divecha

DESCRIPTION:
The test this project deliberately postponed: a walk-forward through time.
Train on everything before a cut-off, score the next twelve months out of
sample, roll the cut-off forward a year, repeat. Nothing after the cut-off
touches training, early stopping or model selection.

Folds: the first cut-off is --first-train-months (default 60: five years of
history, so the out-of-sample record runs from 2005; Arjun's choice,
2026-10-07); each fold scores 12 months; the training window expands from
there, or with --window N rolls (each fold trains only on the trailing N
months before its cut-off; ridge's penalty CV and the net's early-stopping
slice are drawn from that window too).

PROJECT DEFAULT (2026-10-07, Arjun): rolling 60-month window, 30 nets per
fold, hysteresis basket (hold while ranked <= 16). Pass --window 0 for the
expanding window and --seeds 10 to reproduce the earlier runs. Because single
walk-forwards proved seed-sensitive, headline figures are reported across
several independent --seed draws (see default_model.py). The first folds train on very little (about 2,000 rows), which the
per-fold table shows honestly. Models per fold:
  ridge        alpha by 5-fold month-grouped CV inside the training window
  nn_mse       the post-hill-climb MLP (256/128, dropout 0.15, wd 0.01), N seeds
               averaged, early-stopped on a 12% slice of the training months
  nn_soft_top8 same net on the soft top-8 objective
  reference    REER_CS alone (no fitting), when present in the panel

Basket rule (project default since 2026-10-07, see hysteresis.py): hold a
name while the model still ranks it in the top --buffer (16) of the
universe; replace only names that fall below, with the best-ranked names not
held. The plain re-pick-the-top-8 rule is reported alongside. Both are formed
from the same out-of-sample scores.

Reported per rule: mean monthly OOS excess of the basket (x12), its t-stat over
OOS months, hit rate, information ratio, turnover, maximum relative drawdown,
precision@8, rank IC; by year; paired net-minus-ridge over OOS months; and the
cumulative series for the chart.

DEPENDENCIES: torch, pandas, numpy, scipy, scikit-learn, pyarrow, xlsxwriter (experiment .venv)

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model"
  .venv/bin/python walk_forward.py --workers 14 --seed 0 --tag default_s0          # project default
  .venv/bin/python walk_forward.py --window 0 --seeds 10 --workers 14              # earlier expanding runs
  .venv/bin/python walk_forward.py --first-train-months 280 --seeds 1 --workers 2 --tag smoke
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

EXP_DIR = Path(__file__).resolve().parent  # this script's own folder: works from the exp/NN worktree or the main checkout
sys.path.insert(0, str(EXP_DIR))
from train_floor import PANEL, FACTOR_SET, RESULTS_ROOT, REFERENCE_FACTOR, SOFT_TAUS, aggregate, fit_ridge, month_metrics, tstat  # noqa: E402
from train_nn import _init_worker, train_one  # noqa: E402
from hysteresis import DEFAULT_BUFFER, build_baskets  # noqa: E402

log = logging.getLogger("walk_forward")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", type=Path, default=PANEL)
    ap.add_argument("--factor-set", type=Path, default=FACTOR_SET)
    ap.add_argument("--first-train-months", type=int, default=60,
                    help="training months before the first out-of-sample fold (Arjun 2026-10-07: five years, then expanding)")
    ap.add_argument("--step-months", type=int, default=12)
    ap.add_argument("--seeds", type=int, default=30,
                    help="nets averaged per fold (default 30 since 2026-10-07: ten-net ensembles proved seed-sensitive in walk-forward)")
    ap.add_argument("--objectives", default="mse,soft_top8")
    ap.add_argument("--hidden", default="256,128")
    ap.add_argument("--dropout", type=float, default=0.15)
    ap.add_argument("--weight-decay", type=float, default=1e-2)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--tau", type=float, default=0.5)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--tag", default="")
    ap.add_argument("--no-presence", action="store_true")
    ap.add_argument("--buffer", type=int, default=DEFAULT_BUFFER,
                    help="hysteresis rank buffer M for the headline basket: hold a name while ranked <= M (default 16; 8 = plain top-8)")
    ap.add_argument("--max-month", type=int, default=0,
                    help="use only the first N months of the panel (design holdout: select on the first half); 0 = all")
    ap.add_argument("--aux-lambda", type=float, default=0.0,
                    help="multi-task (toolkit/PREREG.md B2b): weight on auxiliary heads forecasting next-month changes in --aux-targets; 0 = off")
    ap.add_argument("--aux-warmup", type=int, default=0, help="epochs of auxiliary-only training before the return objective (curriculum)")
    ap.add_argument("--aux-targets", default="Trailing EPS_TS,BEST EPS_TS,Best ROE_TS,IMF_CPI_Inflation_YoY_TS,20 Day Vol_TS,BBG_Govt_Bond_10Y_TS")
    ap.add_argument("--half-life", type=float, default=0.0,
                    help="months; >0 weights each training month by 0.5**(age/half_life) (age = months before the fold cut-off), "
                         "normalised to mean 1. Use with --window 0 (expanding) for the 'all history, recency-weighted' variant.")
    ap.add_argument("--window", type=int, default=60,
                    help="rolling training window in months: train only on the trailing N months before each cut-off "
                         "(default 60 — Arjun 2026-10-07: 'the world changes'); 0 = expanding")
    args = ap.parse_args()
    hidden = [int(h) for h in args.hidden.split(",")]
    objectives = [o for o in args.objectives.split(",") if o]

    t0 = time.time()
    run_dir = RESULTS_ROOT / (f"walk_{datetime.now().strftime('%Y%m%d_%H%M%S')}" + (f"_{args.tag}" if args.tag else ""))
    run_dir.mkdir(parents=True, exist_ok=False)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    log.setLevel(logging.INFO)
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler(run_dir / "run.log")):
        h.setFormatter(fmt); log.addHandler(h)
    log.info("run dir: %s", run_dir)

    # ── data (mirrors train_nn.py / train_floor.py) ─────────────────────────
    fs = json.load(open(args.factor_set))
    feats = [f["variable"] for f in fs["factors"]]
    src_of = {f["variable"]: f["source"] for f in fs["factors"]}
    panel = pd.read_parquet(args.panel).sort_values(["date", "country"]).reset_index(drop=True)
    if args.max_month:
        cutoff = np.sort(panel["date"].unique())[args.max_month - 1]
        panel = panel[panel["date"] <= cutoff].reset_index(drop=True)
        log.info("design holdout: panel restricted to the first %d months (through %s)", args.max_month, pd.Timestamp(cutoff).strftime("%Y-%m"))
    months = pd.DatetimeIndex(np.sort(panel["date"].unique())); countries = sorted(panel["country"].unique())
    mi = {m: i for i, m in enumerate(months)}; ci = {c: i for i, c in enumerate(countries)}
    sources = [] if args.no_presence else sorted(set(src_of.values()))
    present = np.stack([panel[[v for v in feats if src_of[v] == s]].notna().mean(axis=1).to_numpy() for s in sources], axis=1) \
        if sources else np.zeros((len(panel), 0))
    Xrows = np.hstack([np.nan_to_num(np.clip(panel[feats].to_numpy(float), -5, 5), nan=0.0), present]).astype(np.float32)
    F = Xrows.shape[1]
    X = np.zeros((len(months), len(countries), F), np.float32); Y = np.zeros((len(months), len(countries)), np.float32)
    M = np.zeros((len(months), len(countries)), bool)
    r_m = pd.DatetimeIndex(panel["date"]).map(mi).to_numpy(); r_c = panel["country"].map(ci).to_numpy()
    X[r_m, r_c] = Xrows; Y[r_m, r_c] = panel["fwd_excess"].to_numpy(np.float32); M[r_m, r_c] = True
    y_rows = panel["fwd_excess"].to_numpy(float)
    # auxiliary targets for the multi-task net: next month's change in each named column, per country (NaN where missing)
    Y_aux = M_aux = None
    if args.aux_lambda > 0:
        aux_cols = [c for c in args.aux_targets.split(",") if c]
        missing = [c for c in aux_cols if c not in panel.columns]
        if missing:
            raise SystemExit(f"--aux-targets not in panel: {missing}")
        Y_aux = np.full((len(months), len(countries), len(aux_cols)), np.nan, np.float32)
        for j, c in enumerate(aux_cols):
            nxt = panel.groupby("country")[c].shift(-1) - panel[c]
            Y_aux[r_m, r_c, j] = nxt.to_numpy(np.float32)
        M_aux = np.isfinite(Y_aux); Y_aux = np.nan_to_num(Y_aux, nan=0.0)
        log.info("MULTI-TASK: lambda %.2f, warm-up %d epochs, %d auxiliary targets (%s); target coverage %.1f%%",
                 args.aux_lambda, args.aux_warmup, len(aux_cols), ", ".join(aux_cols), 100 * M_aux[M].mean())
    X_ridge = Xrows.astype(float)
    has_ref = REFERENCE_FACTOR in panel.columns
    ref_rows = panel[REFERENCE_FACTOR].fillna(0.0).to_numpy(float) if has_ref else None

    # ── folds ───────────────────────────────────────────────────────────────
    folds = []
    t = args.first_train_months
    while t < len(months):
        folds.append((len(folds), t, min(t + args.step_months, len(months))))
        t += args.step_months
    log.info("panel: %d months, %d inputs; %d folds from %s (train on %d months, score %d, expanding)",
             len(months), F, len(folds), months[args.first_train_months].strftime("%Y-%m"), args.first_train_months, args.step_months)

    def inner_split(train_months, seed):
        rng = np.random.default_rng(seed + 1000)
        val = rng.permutation(train_months)[: max(3, int(round(0.12 * len(train_months))))]
        return np.setdiff1d(train_months, val), np.sort(val)

    # ── ridge + reference per fold (fast, in-process) ───────────────────────
    scores: dict[str, np.ndarray] = {}        # model -> scores for every row (only OOS rows are used)
    scores["ridge"] = np.full(len(panel), np.nan)
    if has_ref:
        scores["reference_REER_CS"] = ref_rows.copy()
    alphas = {}
    def train_start(t_start: int) -> int:
        return max(0, t_start - args.window) if args.window else 0
    if args.window:
        log.info("ROLLING window: each fold trains only on the trailing %d months before its cut-off", args.window)
    def month_weights(t_start: int):
        """Exponential recency weights over the fold's training months (mean 1); None when --half-life is 0."""
        if not args.half_life:
            return None
        w = np.zeros(len(months), np.float32)
        tr_m = np.arange(train_start(t_start), t_start)
        age = (t_start - 1) - tr_m
        w[tr_m] = 0.5 ** (age / args.half_life)
        w[tr_m] /= w[tr_m].mean()
        return w.tolist()
    if args.half_life:
        log.info("RECENCY WEIGHTS: half-life %.0f months (weight of the oldest month in the first fold = %.3f of mean)",
                 args.half_life, 0.5 ** ((args.first_train_months - 1) / args.half_life))
    for fi, t_start, t_end in folds:
        tr = (r_m < t_start) & (r_m >= train_start(t_start)); oos = (r_m >= t_start) & (r_m < t_end)
        _, s_ev, info = fit_ridge(X_ridge[tr], y_rows[tr], r_m[tr], X_ridge[oos], args.k, args.seed + fi)
        scores["ridge"][oos] = s_ev; alphas[fi] = info["alpha"]
    log.info("ridge done for %d folds; alphas chosen: %s", len(folds), pd.Series(alphas).value_counts().to_dict())

    # ── nets per fold (process pool) ────────────────────────────────────────
    base = {"k": args.k, "tau": args.tau, "hidden": hidden, "dropout": args.dropout, "lr": args.lr,
            "weight_decay": args.weight_decay, "batch_months": 32, "epochs": 300, "patience": 30,
            "aux_lambda": args.aux_lambda, "aux_warmup": args.aux_warmup}
    jobs = []
    for fi, t_start, t_end in folds:
        fit_m, val_m = inner_split(np.arange(train_start(t_start), t_start), args.seed + fi)
        mw = month_weights(t_start)
        for obj in objectives:
            for s in range(args.seeds):
                jobs.append(base | {"split": f"fold_{fi}", "objective": obj, "seed": (args.seed + fi) * 100 + s, "tag": "real",
                                    "tr_months": fit_m, "va_months": val_m, "_fold": fi, "month_weights": mw})
    log.info("net jobs: %d (%d folds x %d objectives x %d seeds); workers=%d", len(jobs), len(folds), len(objectives), args.seeds, args.workers)
    results, done = [], 0
    def heartbeat(last):
        el = time.time() - t0
        (run_dir / "heartbeat.json").write_text(json.dumps({"last": last, "runs_done": done, "runs_total": len(jobs),
            "elapsed_s": round(el), "eta_s": round(el / done * (len(jobs) - done)) if done else None,
            "updated": datetime.now().isoformat(timespec="seconds")}, indent=2))
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker, initargs=(X, Y, M, Y_aux, M_aux)) as pool:
        futs = {pool.submit(train_one, j): j for j in jobs}
        for fut in as_completed(futs):
            r = fut.result(); j = futs[fut]; r["_fold"] = j["_fold"]; results.append(r); done += 1
            if done % 25 == 0 or done == len(jobs):
                heartbeat(f'{r["split"]}/{r["objective"]}/seed{r["seed"]}'); log.info("  %d/%d nets (%.0fs)", done, len(jobs), time.time() - t0)
    for obj in objectives:
        scores[f"nn_{obj}"] = np.full(len(panel), np.nan)
    for fi, t_start, t_end in folds:
        oos = (r_m >= t_start) & (r_m < t_end)
        for obj in objectives:
            rs = [r for r in results if r["_fold"] == fi and r["objective"] == obj]
            ens = np.mean([r["scores"][r_m, r_c] for r in rs], axis=0)
            scores[f"nn_{obj}"][oos] = ens[oos]

    # ── OOS scoring: plain top-8 and the hysteresis-buffered basket (the headline) ──
    # The scores are the same; the rules differ only in how the basket is formed from them.
    # Score-based diagnostics (precision@8, rank IC, bottom-8, soft-k) come from the plain
    # month_metrics and are carried unchanged onto the buffered rows.
    oos_all = r_m >= folds[0][1]
    rules = {"plain_top8": args.k}
    if args.buffer and args.buffer > args.k:
        rules[f"buffer_M{args.buffer}"] = args.buffer
    default_rule = f"buffer_M{args.buffer}" if args.buffer and args.buffer > args.k else "plain_top8"
    score_cols = ["precision8", "rank_ic", "bottom8_excess"] + [c for c in
                 [f"soft_excess_tau{t}" for t in SOFT_TAUS] + [f"neff_tau{t}" for t in SOFT_TAUS]]
    monthly, per_fold, preds = [], [], []
    for model, sc in scores.items():
        mm_plain = month_metrics(sc[oos_all], y_rows[oos_all], r_m[oos_all], args.k)
        mm_plain["date"] = months[mm_plain["month_id"].to_numpy()]
        d = pd.DataFrame({"date": panel["date"][oos_all].to_numpy(), "country": panel["country"][oos_all].to_numpy(),
                          "score": sc[oos_all], "fwd_excess": y_rows[oos_all],
                          "fwd_ret": panel["fwd_ret"][oos_all].to_numpy(), "bench_ret": panel["bench_ret"][oos_all].to_numpy()})
        preds.append(d[["date", "country", "score", "fwd_excess"]].assign(model=model))
        for rule, M in rules.items():
            b = build_baskets(d, args.k, M).rename(columns={"excess": "top8_excess"})
            mm = b.merge(mm_plain[["date", "month_id", "n"] + score_cols], on="date", how="left")
            mm.insert(0, "rule", rule); mm.insert(0, "model", model)
            mm["fold"] = [next(fi for fi, a, bb in folds if a <= m < bb) for m in mm["month_id"]]
            monthly.append(mm)
            for fi, g in mm.groupby("fold"):
                a = aggregate(g.drop(columns=["model", "rule", "date", "fold", "basket_ret", "bench_ret", "names_changed", "n_held"]))
                a.update({"model": model, "rule": rule, "fold": fi, "oos_start": months[folds[fi][1]].strftime("%Y-%m"),
                          "train_months": folds[fi][1], "names_changed_per_month": float(g["names_changed"].mean())})
                per_fold.append(a)
    mo = pd.concat(monthly, ignore_index=True)
    pf = pd.DataFrame(per_fold)
    by_year = (mo.assign(year=mo["date"].dt.year).groupby(["model", "rule", "year"])
               .agg(top8_excess_ann_pct=("top8_excess", lambda x: x.mean() * 1200), hit_rate=("top8_excess", lambda x: (x > 0).mean()),
                    months=("top8_excess", "size")).reset_index())
    overall, paired = {}, {}
    for rule in rules:
        overall[rule], paired[rule] = {}, {}
        mr = mo[mo.rule == rule]
        for model, g in mr.groupby("model"):
            a = aggregate(g.drop(columns=["model", "rule", "date", "fold", "basket_ret", "bench_ret", "names_changed", "n_held"]))
            ch = g["names_changed"].iloc[1:]
            wb, wbm = (1 + g["basket_ret"]).cumprod(), (1 + g["bench_ret"]).cumprod(); rel = wb / wbm
            dd = (rel / rel.cummax() - 1)
            a.update({"names_changed_per_month": float(ch.mean()), "turnover_oneway_pct_yr": float(ch.mean() / args.k * 1200),
                      "info_ratio": float(g["top8_excess"].mean() / g["top8_excess"].std(ddof=1) * np.sqrt(12)),
                      "excess_vol_pct_yr": float(g["top8_excess"].std(ddof=1) * np.sqrt(12) * 100),
                      "max_rel_drawdown_pct": float(dd.min() * 100), "basket_cagr_pct": float((wb.iloc[-1] ** (12 / len(wb)) - 1) * 100),
                      "bench_cagr_pct": float((wbm.iloc[-1] ** (12 / len(wbm)) - 1) * 100)})
            overall[rule][model] = a
        rid = mr[mr.model == "ridge"].set_index("date")["top8_excess"]
        for model in scores:
            if model == "ridge":
                continue
            dd_ = mr[mr.model == model].set_index("date")["top8_excess"].reindex(rid.index) - rid
            paired[rule][model] = {"minus_ridge_ann_pct": float(dd_.mean() * 1200), "t": tstat(dd_), "months": int(dd_.notna().sum()),
                                   "wins_frac": float((dd_ > 0).mean())}

    mo.to_parquet(run_dir / "monthly_oos.parquet", index=False)
    pf.to_parquet(run_dir / "per_fold.parquet", index=False)
    by_year.to_parquet(run_dir / "by_year.parquet", index=False)
    pd.concat(preds, ignore_index=True).to_parquet(run_dir / "predictions_oos.parquet", index=False)
    with pd.ExcelWriter(run_dir / "per_fold.xlsx", engine="xlsxwriter") as xw:
        pf.to_excel(xw, sheet_name="per_fold", index=False, na_rep="—")
        by_year.to_excel(xw, sheet_name="by_year", index=False, na_rep="—")
        pd.concat({r: pd.DataFrame(o).T for r, o in overall.items()}, names=["rule", "model"]).to_excel(xw, sheet_name="overall", na_rep="—")
    runs = pd.DataFrame([{k: v for k, v in r.items() if k != "scores"} for r in results])
    summary = {"run_dir": str(run_dir), "panel": str(args.panel), "factor_set": str(args.factor_set), "tag": args.tag,
               "config": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()} | {"hidden": hidden},
               "n_folds": len(folds), "oos_start": months[folds[0][1]].strftime("%Y-%m"), "oos_end": months[-1].strftime("%Y-%m"),
               "oos_months": int(mo[(mo.model == "ridge") & (mo.rule == default_rule)].shape[0]),
               "rules": list(rules), "default_rule": default_rule,
               "overall": overall, "paired_vs_ridge": paired,
               "ridge_alphas": {str(k): v for k, v in alphas.items()},
               "net_runs_stats": runs.groupby("objective")[["best_epoch", "seconds"]].mean().round(1).to_dict("index") if len(runs) else {},
               "elapsed_s": round(time.time() - t0, 1)}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    heartbeat("done")
    for rule in rules:
        log.info("OUT-OF-SAMPLE [%s]%s (%s -> %s, %d months): %s", rule, " (default)" if rule == default_rule else "",
                 summary["oos_start"], summary["oos_end"], summary["oos_months"],
                 {m: f'{a["top8_excess_ann_pct"]:+.2f}%/yr t={a["top8_t"]:.2f} hit={a["top8_hit_rate"]:.2f} turnover={a["turnover_oneway_pct_yr"]:.0f}%'
                  for m, a in overall[rule].items()})
        log.info("  paired vs ridge: %s", {m: f'{p["minus_ridge_ann_pct"]:+.2f} t={p["t"]:.2f}' for m, p in paired[rule].items()})
    log.info("done in %.1f min", (time.time() - t0) / 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
