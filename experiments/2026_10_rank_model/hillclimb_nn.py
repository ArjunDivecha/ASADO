#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/hillclimb_nn.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v1/feature_panel_v1.parquet
    Model-ready panel (build_panel.py), the ORIGINAL full factor set.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/factor_set_v1.json
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/floor_<latest>/per_split.parquet
    Ridge rows for the same splits (paired comparison). Optional.
- experiments/2026_10_rank_model/train_nn.py   (imported: train_one, _init_worker —
    the exact training loop of stage 5)
- experiments/2026_10_rank_model/train_floor.py (imported: month_metrics, aggregate)

OUTPUT FILES (inside
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/hill_<YYYYMMDD_HHMMSS>/ ):
- per_split.parquet / per_split.xlsx   one row per (config, split, train|eval) for the 5-seed ensembles
- configs.parquet                       the sweep: per config, eval mean/sd, paired diff vs base, t, wins, blocks, train fit
- seed_curve.parquet                    base config: eval top-8 excess of an ensemble of the first n seeds, n = 1..20
- runs.parquet                          one row per trained net
- summary.json, heartbeat.json, run.log

VERSION: 1.0
LAST UPDATED: 2026-10-07
AUTHOR: Claude (Fable 5.1) for Arjun Divecha

DESCRIPTION:
The hill-climb on the stage-5 network, on the original full panel. Two levers:

1. Regularisation / width / learning-rate sweep. One ingredient changed at a
   time from the base config (64/32 hidden, dropout 0.15, weight decay 0.01,
   lr 1e-3), plus two "heavy" combinations. Objective: predict-then-select
   (mse) — the fastest to train and the best of the three on contiguous blocks.
   Every config: 5 seeds -> ensemble, on the same 30 random splits and 5
   blocks as every other stage; judged paired against the base config and
   against ridge.

2. Seed curve. The base config with 20 seeds; the ensemble of the first n
   seeds for n = 1, 2, 3, 5, 8, 10, 15, 20 says where averaging saturates.

The base config rerun here must reproduce stage 5 (same seeds, deterministic
CPU training) — that is checked and logged.

DEPENDENCIES: torch, pandas, numpy, scipy, pyarrow, xlsxwriter (experiment .venv)

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model"
  .venv/bin/python hillclimb_nn.py --workers 14
  .venv/bin/python hillclimb_nn.py --n-random 2 --n-blocks 2 --seeds 1 --curve-seeds 3 --workers 2   # smoke
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

import numpy as np
import pandas as pd

EXP_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model")
sys.path.insert(0, str(EXP_DIR))
from train_floor import PANEL, FACTOR_SET, RESULTS_ROOT, aggregate, month_metrics  # noqa: E402
from train_nn import _init_worker, train_one  # noqa: E402

BASE = {"hidden": [64, 32], "dropout": 0.15, "weight_decay": 1e-2, "lr": 1e-3}
# one ingredient at a time from BASE, plus two heavy combinations
CONFIGS = {
    "base":            {},
    "dropout_0.30":    {"dropout": 0.30},
    "dropout_0.50":    {"dropout": 0.50},
    "wd_0.1":          {"weight_decay": 0.1},
    "wd_1.0":          {"weight_decay": 1.0},
    "width_32_16":     {"hidden": [32, 16]},
    "width_128_64":    {"hidden": [128, 64]},
    "width_256_128":   {"hidden": [256, 128]},
    "lr_3e-4":         {"lr": 3e-4},
    "heavy_small":     {"hidden": [32, 16], "dropout": 0.30, "weight_decay": 0.1},
    "heavy_wide":      {"hidden": [128, 64], "dropout": 0.50, "weight_decay": 0.1},
}
CURVE_NS = [1, 2, 3, 5, 8, 10, 15, 20]
log = logging.getLogger("hillclimb_nn")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", type=Path, default=PANEL)
    ap.add_argument("--factor-set", type=Path, default=FACTOR_SET)
    ap.add_argument("--n-random", type=int, default=30)
    ap.add_argument("--eval-frac", type=float, default=0.20)
    ap.add_argument("--n-blocks", type=int, default=5)
    ap.add_argument("--seeds", type=int, default=5, help="seeds per config in the sweep")
    ap.add_argument("--curve-seeds", type=int, default=20, help="seeds for the base-config seed curve")
    ap.add_argument("--objective", default="mse")
    ap.add_argument("--configs", default=",".join(CONFIGS), help="subset of config names")
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--tau", type=float, default=0.5)
    ap.add_argument("--batch-months", type=int, default=32)
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--patience", type=int, default=30)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    configs = {n: CONFIGS[n] for n in args.configs.split(",") if n}

    t0 = time.time()
    run_dir = RESULTS_ROOT / f"hill_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=False)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    log.setLevel(logging.INFO)
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler(run_dir / "run.log")):
        h.setFormatter(fmt)
        log.addHandler(h)
    log.info("run dir: %s", run_dir)

    # ── data: mirrors train_nn.py exactly ───────────────────────────────────
    fs = json.load(open(args.factor_set))
    feats = [f["variable"] for f in fs["factors"]]
    src_of = {f["variable"]: f["source"] for f in fs["factors"]}
    panel = pd.read_parquet(args.panel).sort_values(["date", "country"]).reset_index(drop=True)
    months = np.sort(panel["date"].unique())
    countries = sorted(panel["country"].unique())
    mi = {m: i for i, m in enumerate(months)}
    ci = {c: i for i, c in enumerate(countries)}
    sources = sorted(set(src_of.values()))
    present = np.stack([panel[[v for v in feats if src_of[v] == s]].notna().mean(axis=1).to_numpy() for s in sources], axis=1)
    Xrows = np.hstack([np.nan_to_num(np.clip(panel[feats].to_numpy(float), -5, 5), nan=0.0), present]).astype(np.float32)
    F = Xrows.shape[1]
    X = np.zeros((len(months), len(countries), F), np.float32)
    Y = np.zeros((len(months), len(countries)), np.float32)
    M = np.zeros((len(months), len(countries)), bool)
    r_m = panel["date"].map(mi).to_numpy()
    r_c = panel["country"].map(ci).to_numpy()
    X[r_m, r_c] = Xrows
    Y[r_m, r_c] = panel["fwd_excess"].to_numpy(np.float32)
    M[r_m, r_c] = True
    y_rows = panel["fwd_excess"].to_numpy(float)

    splits = []
    n_eval = int(round(args.eval_frac * len(months)))
    for i in range(args.n_random):
        perm = np.random.default_rng(args.seed + i).permutation(len(months))
        ev = np.zeros(len(months), bool); ev[perm[:n_eval]] = True
        splits.append((f"random_{i}", "random", ev))
    edges = np.linspace(0, len(months), args.n_blocks + 1).astype(int)
    for b in range(args.n_blocks):
        ev = np.zeros(len(months), bool); ev[edges[b]:edges[b + 1]] = True
        splits.append((f"block_{b}", "blocked", ev))

    def inner_split(train_months, seed):
        rng = np.random.default_rng(seed + 1000)
        val = rng.permutation(train_months)[: max(3, int(round(0.12 * len(train_months))))]
        return np.setdiff1d(train_months, val), np.sort(val)

    common = {"k": args.k, "tau": args.tau, "batch_months": args.batch_months, "epochs": args.epochs,
              "patience": args.patience, "objective": args.objective}

    # ── jobs: sweep (seeds 0..seeds-1) + seed curve for base (seeds 0..curve_seeds-1) ──
    jobs = []
    for split_name, split_type, ev in splits:
        tr_all = np.flatnonzero(~ev)
        sseed = args.seed + int(split_name.split("_")[1]) + (100 if split_type == "blocked" else 0)
        fit_m, val_m = inner_split(tr_all, sseed)
        for cname, over in configs.items():
            n_seeds = max(args.seeds, args.curve_seeds) if cname == "base" else args.seeds
            for s in range(n_seeds):
                jobs.append(common | BASE | over | {"split": split_name, "seed": sseed * 10 + s, "tag": cname,
                                                    "tr_months": fit_m, "va_months": val_m})
    log.info("jobs: %d (%d splits; %d configs x %d seeds; base with %d seeds for the curve); workers=%d",
             len(jobs), len(splits), len(configs), args.seeds, args.curve_seeds, args.workers)

    results, done = [], 0
    def heartbeat(last):
        el = time.time() - t0
        (run_dir / "heartbeat.json").write_text(json.dumps({
            "last": last, "runs_done": done, "runs_total": len(jobs), "elapsed_s": round(el),
            "eta_s": round(el / done * (len(jobs) - done)) if done else None,
            "updated": datetime.now().isoformat(timespec="seconds")}, indent=2))
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker, initargs=(X, Y, M)) as pool:
        futs = [pool.submit(train_one, j) for j in jobs]
        for fut in as_completed(futs):
            r = fut.result(); results.append(r); done += 1
            if done % 50 == 0 or done == len(jobs):
                heartbeat(f'{r["split"]}/{r["tag"]}/seed{r["seed"]}')
                log.info("  %d/%d runs (%.0fs)", done, len(jobs), time.time() - t0)

    # ── score ensembles per (config, split) ─────────────────────────────────
    ev_of = {n: e for n, _, e in splits}
    type_of = {n: t for n, t, _ in splits}
    by_key: dict[tuple, list] = {}
    for r in results:
        by_key.setdefault((r["tag"], r["split"]), []).append(r)
    per_split, curve_rows = [], []

    def metrics(split, scores_rows, set_name):
        ev = ev_of[split][r_m]
        mask = ev if set_name == "eval" else ~ev
        return aggregate(month_metrics(scores_rows[mask], y_rows[mask], r_m[mask], args.k))

    for (cname, split), rs in by_key.items():
        rs = sorted(rs, key=lambda r: r["seed"])
        scores = [r["scores"][r_m, r_c] for r in rs]
        ens = np.mean(scores[:args.seeds], axis=0)
        for set_name in ("train", "eval"):
            a = metrics(split, ens, set_name)
            a.update({"config": cname, "split": split, "split_type": type_of[split], "set": set_name,
                      "n_seeds": min(len(scores), args.seeds),
                      "mean_best_epoch": float(np.mean([r["best_epoch"] for r in rs[:args.seeds]]))})
            per_split.append(a)
        if cname == "base" and len(scores) >= 2:
            for n in [n for n in CURVE_NS if n <= len(scores)]:
                a = metrics(split, np.mean(scores[:n], axis=0), "eval")
                curve_rows.append({"split": split, "split_type": type_of[split], "n_seeds": n,
                                   "top8_excess_ann_pct": a["top8_excess_ann_pct"], "rank_ic": a["rank_ic"],
                                   "top8_hit_rate": a["top8_hit_rate"]})
            # single-seed average (what one net does on average), for the curve's n=1 point
            singles = [metrics(split, sc, "eval")["top8_excess_ann_pct"] for sc in scores[:args.curve_seeds]]
            curve_rows.append({"split": split, "split_type": type_of[split], "n_seeds": 0,
                               "top8_excess_ann_pct": float(np.mean(singles)), "rank_ic": np.nan, "top8_hit_rate": np.nan})

    ps = pd.DataFrame(per_split)
    curve = pd.DataFrame(curve_rows)

    # ── paired comparison vs base and vs ridge ──────────────────────────────
    ev = ps[(ps.set == "eval") & (ps.split_type == "random")].pivot(index="split", columns="config", values="top8_excess_ann_pct")
    bl = ps[(ps.set == "eval") & (ps.split_type == "blocked")].groupby("config")["top8_excess_ann_pct"].mean()
    tr = ps[(ps.set == "train") & (ps.split_type == "random")].groupby("config")["top8_excess_ann_pct"].mean()
    ridge = None
    floor = sorted(p for p in RESULTS_ROOT.glob("floor_*") if p.is_dir() and (p / "summary.json").exists()
                   and len(p.name) == len("floor_20261007_110654"))
    if floor:
        fl = pd.read_parquet(floor[-1] / "per_split.parquet")
        ridge = fl[(fl.model == "ridge") & (fl.set == "eval") & (fl.split_type == "random")].set_index("split")["top8_excess_ann_pct"]
    rows = []
    for cname in configs:
        if cname not in ev.columns:
            continue
        d = ev[cname] - ev["base"]
        row = {"config": cname, **{k: v for k, v in (BASE | configs[cname]).items()},
               "eval_top8_ann_pct": ev[cname].mean(), "eval_sd_splits": ev[cname].std(),
               "vs_base_pct": d.mean(), "vs_base_t": d.mean() / (d.std() / np.sqrt(len(d))) if d.std() > 0 else np.nan,
               "wins_vs_base": int((d > 0).sum()), "n_splits": len(d),
               "blocked_top8_ann_pct": bl.get(cname, np.nan), "train_top8_ann_pct": tr.get(cname, np.nan),
               "eval_hit_rate": ps[(ps.config == cname) & (ps.set == "eval") & (ps.split_type == "random")]["top8_hit_rate"].mean(),
               "eval_rank_ic": ps[(ps.config == cname) & (ps.set == "eval") & (ps.split_type == "random")]["rank_ic"].mean(),
               "mean_best_epoch": ps[(ps.config == cname) & (ps.set == "eval")]["mean_best_epoch"].mean()}
        if ridge is not None:
            dr = ev[cname].reindex(ridge.index) - ridge
            row.update({"vs_ridge_pct": dr.mean(), "vs_ridge_t": dr.mean() / (dr.std() / np.sqrt(len(dr))), "wins_vs_ridge": int((dr > 0).sum())})
        row["hidden"] = "/".join(map(str, row["hidden"]))
        rows.append(row)
    cfg_tbl = pd.DataFrame(rows).sort_values("eval_top8_ann_pct", ascending=False).reset_index(drop=True)

    # reproducibility check vs the stage-5 run (base config, mse, same seeds)
    repro = None
    nn_runs = sorted(p for p in RESULTS_ROOT.glob("nn_*") if p.is_dir() and (p / "summary.json").exists()
                     and len(p.name) == len("nn_20261007_112400"))
    if nn_runs:
        prev = pd.read_parquet(nn_runs[-1] / "per_split.parquet")
        prev = prev[(prev.model == "nn_mse") & (prev.member == "ensemble") & (prev.set == "eval")].set_index("split")["top8_excess_ann_pct"]
        here = ps[(ps.config == "base") & (ps.set == "eval")].set_index("split")["top8_excess_ann_pct"]
        common_idx = prev.index.intersection(here.index)
        if len(common_idx) and args.seeds == 5:
            repro = float((prev[common_idx] - here[common_idx]).abs().max())
            log.info("reproducibility vs %s (base/mse, %d splits): max |diff| = %.4f %%/yr", nn_runs[-1].name, len(common_idx), repro)

    # ── write ───────────────────────────────────────────────────────────────
    ps.to_parquet(run_dir / "per_split.parquet", index=False)
    cfg_tbl.to_parquet(run_dir / "configs.parquet", index=False)
    curve.to_parquet(run_dir / "seed_curve.parquet", index=False)
    pd.DataFrame([{k: v for k, v in r.items() if k != "scores"} for r in results]).to_parquet(run_dir / "runs.parquet", index=False)
    with pd.ExcelWriter(run_dir / "per_split.xlsx", engine="xlsxwriter") as xw:
        cfg_tbl.to_excel(xw, sheet_name="configs", index=False, na_rep="—")
        ps.to_excel(xw, sheet_name="per_split", index=False, na_rep="—")
        curve.to_excel(xw, sheet_name="seed_curve", index=False, na_rep="—")
    curve_summary = (curve[curve.split_type == "random"].groupby("n_seeds")["top8_excess_ann_pct"].agg(["mean", "std"]).round(2)
                     .rename(index={0: "single-seed avg"}).to_dict("index"))
    summary = {
        "run_dir": str(run_dir), "panel": str(args.panel), "objective": args.objective, "base": BASE | {"hidden": "64/32"},
        "configs": {k: v for k, v in configs.items()}, "n_runs": len(jobs), "n_splits": len(splits),
        "seeds_sweep": args.seeds, "seeds_curve": args.curve_seeds,
        "config_table": cfg_tbl.to_dict("records"), "seed_curve_random_eval": curve_summary,
        "reproducibility_max_abs_diff_vs_stage5": repro, "elapsed_s": round(time.time() - t0, 1),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    heartbeat("done")
    log.info("sweep (random eval, ensembles of %d):\n%s", args.seeds,
             cfg_tbl[["config", "eval_top8_ann_pct", "vs_base_pct", "vs_base_t", "wins_vs_base", "blocked_top8_ann_pct", "train_top8_ann_pct"]].round(2).to_string(index=False))
    log.info("seed curve (random eval): %s", curve_summary)
    log.info("done in %.1f min", (time.time() - t0) / 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
