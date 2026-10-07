#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/train_attn.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v1/feature_panel_v1.parquet
    (or any panel_<version> from build_panel.py, via --panel / --factor-set)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/factor_set_v1.json
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/floor_<...>/per_split.parquet
    ridge rows for the paired comparison (untagged, or floor_*_<tag> when --tag is given)
- experiments/2026_10_rank_model/train_nn.py   (imported: make_soft_topk, month_zscore,
    _init_worker/_DATA — the stage-5 soft-top-k loss and worker data sharing)
- experiments/2026_10_rank_model/train_floor.py (imported: month_metrics, aggregate)

OUTPUT FILES (inside
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/nn_<YYYYMMDD_HHMMSS>[_<tag>]/ ):
  the same layout as train_nn.py (per_split.parquet/xlsx, monthly.parquet,
  predictions_eval.parquet, runs.parquet, summary.json, heartbeat.json, run.log),
  with model names attn_mse / attn_soft_top8 (and attn_soft_top8_shuffled).

VERSION: 1.0
LAST UPDATED: 2026-10-07
AUTHOR: Claude (Fable 5.1) for Arjun Divecha

DESCRIPTION:
The cross-country attention model: the first architecture where one country's
score can depend on what the other 33 look like that month.

Per month, the 34 countries are a set of tokens. Each token's inputs (the same
clipped z-scores and presence columns the MLP uses) are projected to d_model,
passed through n_layers of a pre-norm transformer encoder (multi-head
self-attention over the countries in that month, with a key-padding mask for
countries missing that month, then a feed-forward block), and read out to one
score per country. No positional encoding — the countries are an unordered
set, so permuting the rows permutes the outputs and nothing else. Objectives,
splits, seeds, early stopping, ensembling, shuffled-label control and metrics
are identical to train_nn.py so the comparison with the MLP is paired.

Default size: d_model 64, 2 layers, 4 heads, feed-forward 128, dropout 0.15.
Trained on CPU in a process pool like the MLP; at this size the GPU's launch
overhead costs more than it saves.

DEPENDENCIES: torch, pandas, numpy, scipy, pyarrow, xlsxwriter (experiment .venv)

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model"
  .venv/bin/python train_attn.py --seeds 5 --workers 14 --tag attn
  .venv/bin/python train_attn.py --n-random 1 --n-blocks 2 --seeds 1 --n-shuffle 0 --workers 2 --tag smoke
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
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
from train_floor import PANEL, FACTOR_SET, RESULTS_ROOT, SOFT_TAUS, aggregate, month_metrics  # noqa: E402
from train_nn import _DATA, _init_worker, make_soft_topk, month_zscore  # noqa: E402

OBJECTIVES = ["mse", "soft_top8"]
log = logging.getLogger("train_attn")


def _torch():
    import torch
    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass
    return torch


def build_attn(torch, n_in: int, d_model: int, n_layers: int, n_heads: int, d_ff: int, dropout: float):
    nn = torch.nn

    class AttnScorer(nn.Module):
        def __init__(self):
            super().__init__()
            self.embed = nn.Sequential(nn.Linear(n_in, d_model), nn.GELU(), nn.Dropout(dropout))
            layer = nn.TransformerEncoderLayer(d_model=d_model, nhead=n_heads, dim_feedforward=d_ff, dropout=dropout,
                                               activation="gelu", batch_first=True, norm_first=True)
            self.encoder = nn.TransformerEncoder(layer, num_layers=n_layers, enable_nested_tensor=False)
            self.head = nn.Sequential(nn.LayerNorm(d_model), nn.Linear(d_model, 1))

        def forward(self, x, mask):                 # x: (B, N, F); mask: (B, N) True = valid
            h = self.embed(x)
            h = self.encoder(h, src_key_padding_mask=~mask)
            return self.head(h).squeeze(-1)         # (B, N)
    return AttnScorer()


def train_one_attn(job: dict) -> dict:
    torch = _torch()
    torch.manual_seed(job["seed"])
    np.random.seed(job["seed"])
    soft_topk = make_soft_topk(torch)
    X, M = _DATA["X"], _DATA["M"]
    Y = job.get("Y_override", _DATA["Y"])
    tr_idx, va_idx = job["tr_months"], job["va_months"]
    k, tau = job["k"], job["tau"]
    Xt, Yt, Mt = torch.tensor(X), torch.tensor(Y), torch.tensor(M)
    model = build_attn(torch, X.shape[-1], job["d_model"], job["n_layers"], job["n_heads"], job["d_ff"], job["dropout"])
    opt = torch.optim.AdamW(model.parameters(), lr=job["lr"], weight_decay=job["weight_decay"])

    def loss_fn(s, y, m, objective):
        if objective == "mse":
            return ((((s - y) ** 2) * m).sum(dim=1) / m.sum(dim=1).clamp_min(1)).mean()
        z = month_zscore(torch, s, m)
        return -(((soft_topk(z, m, k, tau) / k) * y).sum(dim=1)).mean() * 100.0

    def val_score():
        model.eval()
        with torch.no_grad():
            s = model(Xt[va_idx], Mt[va_idx])
            z = month_zscore(torch, s, Mt[va_idx])
            v = float(((soft_topk(z, Mt[va_idx], k, 0.25) / k) * Yt[va_idx]).sum(dim=1).mean())
        model.train()
        return v

    best_state, best_val, best_epoch, bad, t0 = None, -1e9, 0, 0, time.time()
    rng = np.random.default_rng(job["seed"])
    for ep in range(job["epochs"]):
        perm = rng.permutation(tr_idx)
        for i in range(0, len(perm), job["batch_months"]):
            idx = perm[i:i + job["batch_months"]]
            s = model(Xt[idx], Mt[idx])
            loss = loss_fn(s, Yt[idx], Mt[idx], job["objective"])
            opt.zero_grad(); loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            opt.step()
        v = val_score()
        if v > best_val + 1e-6:
            best_val, best_epoch, bad = v, ep + 1, 0
            best_state = {kk: vv.detach().clone() for kk, vv in model.state_dict().items()}
        else:
            bad += 1
            if bad >= job["patience"]:
                break
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        s_all = model(Xt, Mt).numpy()
    return {"split": job["split"], "objective": job["objective"], "seed": job["seed"], "tag": job["tag"],
            "scores": s_all, "best_epoch": best_epoch, "epochs_run": ep + 1,
            "inner_val_soft_excess_pct_month": best_val * 100, "seconds": round(time.time() - t0, 1)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", type=Path, default=PANEL)
    ap.add_argument("--factor-set", type=Path, default=FACTOR_SET)
    ap.add_argument("--floor-run", type=Path, default=None)
    ap.add_argument("--n-random", type=int, default=30)
    ap.add_argument("--eval-frac", type=float, default=0.20)
    ap.add_argument("--n-blocks", type=int, default=5)
    ap.add_argument("--n-shuffle", type=int, default=10)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--objectives", default=",".join(OBJECTIVES))
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--tau", type=float, default=0.5)
    ap.add_argument("--d-model", type=int, default=64)
    ap.add_argument("--n-layers", type=int, default=2)
    ap.add_argument("--n-heads", type=int, default=4)
    ap.add_argument("--d-ff", type=int, default=128)
    ap.add_argument("--dropout", type=float, default=0.15)
    ap.add_argument("--lr", type=float, default=5e-4)
    ap.add_argument("--weight-decay", type=float, default=1e-2)
    ap.add_argument("--batch-months", type=int, default=32)
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--patience", type=int, default=30)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--tag", default="attn")
    ap.add_argument("--no-presence", action="store_true")
    args = ap.parse_args()
    objectives = [o for o in args.objectives.split(",") if o]

    t0 = time.time()
    run_dir = RESULTS_ROOT / (f"nn_{datetime.now().strftime('%Y%m%d_%H%M%S')}" + (f"_{args.tag}" if args.tag else ""))
    run_dir.mkdir(parents=True, exist_ok=False)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    log.setLevel(logging.INFO)
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler(run_dir / "run.log")):
        h.setFormatter(fmt); log.addHandler(h)
    log.info("run dir: %s", run_dir)

    # ── data (mirrors train_nn.py) ──────────────────────────────────────────
    fs = json.load(open(args.factor_set))
    feats = [f["variable"] for f in fs["factors"]]
    src_of = {f["variable"]: f["source"] for f in fs["factors"]}
    panel = pd.read_parquet(args.panel).sort_values(["date", "country"]).reset_index(drop=True)
    months = np.sort(panel["date"].unique()); countries = sorted(panel["country"].unique())
    mi = {m: i for i, m in enumerate(months)}; ci = {c: i for i, c in enumerate(countries)}
    sources = [] if args.no_presence else sorted(set(src_of.values()))
    present = np.stack([panel[[v for v in feats if src_of[v] == s]].notna().mean(axis=1).to_numpy() for s in sources], axis=1) \
        if sources else np.zeros((len(panel), 0))
    Xrows = np.hstack([np.nan_to_num(np.clip(panel[feats].to_numpy(float), -5, 5), nan=0.0), present]).astype(np.float32)
    F = Xrows.shape[1]
    X = np.zeros((len(months), len(countries), F), np.float32); Y = np.zeros((len(months), len(countries)), np.float32)
    M = np.zeros((len(months), len(countries)), bool)
    r_m = panel["date"].map(mi).to_numpy(); r_c = panel["country"].map(ci).to_numpy()
    X[r_m, r_c] = Xrows; Y[r_m, r_c] = panel["fwd_excess"].to_numpy(np.float32); M[r_m, r_c] = True
    y_rows = panel["fwd_excess"].to_numpy(float)
    log.info("tensor panel: %d months x %d countries x %d inputs; attention d_model=%d layers=%d heads=%d ff=%d",
             *X.shape, args.d_model, args.n_layers, args.n_heads, args.d_ff)

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

    base = {"k": args.k, "tau": args.tau, "d_model": args.d_model, "n_layers": args.n_layers, "n_heads": args.n_heads,
            "d_ff": args.d_ff, "dropout": args.dropout, "lr": args.lr, "weight_decay": args.weight_decay,
            "batch_months": args.batch_months, "epochs": args.epochs, "patience": args.patience}
    jobs = []
    for split_name, split_type, ev in splits:
        tr_all = np.flatnonzero(~ev)
        sseed = args.seed + int(split_name.split("_")[1]) + (100 if split_type == "blocked" else 0)
        fit_m, val_m = inner_split(tr_all, sseed)
        for obj in objectives:
            for s in range(args.seeds):
                jobs.append(base | {"split": split_name, "objective": obj, "seed": sseed * 10 + s, "tag": "real",
                                    "tr_months": fit_m, "va_months": val_m})
        if split_type == "random" and int(split_name.split("_")[1]) < args.n_shuffle and "soft_top8" in objectives:
            rng = np.random.default_rng(sseed + 7); Ysh = Y.copy()
            for m in tr_all:
                idx = np.flatnonzero(M[m]); Ysh[m, idx] = Ysh[m, rng.permutation(idx)]
            for s in range(args.seeds):
                jobs.append(base | {"Y_override": Ysh, "split": split_name, "objective": "soft_top8", "seed": sseed * 10 + s,
                                    "tag": "shuffled", "tr_months": fit_m, "va_months": val_m})
    log.info("jobs: %d (%d splits x %d objectives x %d seeds + %d shuffled); workers=%d", len(jobs), len(splits),
             len(objectives), args.seeds, sum(j["tag"] == "shuffled" for j in jobs), args.workers)

    results, done = [], 0
    def heartbeat(last):
        el = time.time() - t0
        (run_dir / "heartbeat.json").write_text(json.dumps({"last": last, "runs_done": done, "runs_total": len(jobs),
            "elapsed_s": round(el), "eta_s": round(el / done * (len(jobs) - done)) if done else None,
            "updated": datetime.now().isoformat(timespec="seconds")}, indent=2))
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker, initargs=(X, Y, M)) as pool:
        futs = [pool.submit(train_one_attn, j) for j in jobs]
        for fut in as_completed(futs):
            r = fut.result(); results.append(r); done += 1
            if done % 25 == 0 or done == len(jobs):
                heartbeat(f'{r["split"]}/{r["objective"]}/seed{r["seed"]}')
                log.info("  %d/%d runs (%.0fs)", done, len(jobs), time.time() - t0)

    # ── score (identical to train_nn.py, model names attn_*) ────────────────
    ev_of = {n: e for n, _, e in splits}; type_of = {n: t for n, t, _ in splits}
    per_split, monthly, preds, runs = [], [], [], [{k: v for k, v in r.items() if k != "scores"} for r in results]
    grouped: dict[tuple, list] = {}
    for r in results:
        grouped.setdefault((r["split"], r["objective"], r["tag"]), []).append(r)

    def rows_for(split, scores_rows, set_name):
        ev = ev_of[split][r_m]; mask = ev if set_name == "eval" else ~ev
        return month_metrics(scores_rows[mask], y_rows[mask], r_m[mask], args.k)

    for (split, obj, tag), rs in grouped.items():
        model_name = f"attn_{obj}" + ("_shuffled" if tag == "shuffled" else "")
        seed_scores = []
        for r in rs:
            sc = r["scores"][r_m, r_c]; seed_scores.append(sc)
            for set_name in ("train", "eval"):
                mm = rows_for(split, sc, set_name)
                if mm.empty:
                    continue
                a = aggregate(mm); a.update({"split": split, "split_type": type_of[split], "model": model_name, "seed": r["seed"],
                                             "member": "seed", "set": set_name, "best_epoch": r["best_epoch"]}); per_split.append(a)
        ens = np.mean(seed_scores, axis=0)
        for set_name in ("train", "eval"):
            mm = rows_for(split, ens, set_name)
            a = aggregate(mm); a.update({"split": split, "split_type": type_of[split], "model": model_name, "seed": -1,
                                         "member": "ensemble", "set": set_name}); per_split.append(a)
            mm.insert(0, "set", set_name); mm.insert(0, "model", model_name); mm.insert(0, "split", split)
            mm["date"] = months[mm["month_id"].to_numpy()]; monthly.append(mm)
        ev = ev_of[split][r_m]
        preds.append(pd.DataFrame({"split": split, "model": model_name, "date": panel["date"][ev].to_numpy(),
                                   "country": panel["country"][ev].to_numpy(), "score": ens[ev], "fwd_excess": y_rows[ev]}))

    ps = pd.DataFrame(per_split)
    pat = re.compile(r"^floor_\d{8}_\d{6}$")
    floor = args.floor_run or (sorted(p for p in RESULTS_ROOT.glob("floor_*") if p.is_dir() and pat.match(p.name)) or [None])[-1]
    if floor and (Path(floor) / "per_split.parquet").exists():
        fl = pd.read_parquet(Path(floor) / "per_split.parquet")
        fl = fl[fl.model.isin(["ridge", "reference_REER_CS", "lgbm_regression"])].copy(); fl["seed"], fl["member"] = -1, "floor"
        ps = pd.concat([ps, fl[[c for c in fl.columns if c in ps.columns]]], ignore_index=True)
    ps.to_parquet(run_dir / "per_split.parquet", index=False)
    with pd.ExcelWriter(run_dir / "per_split.xlsx", engine="xlsxwriter") as xw:
        ps.to_excel(xw, sheet_name="per_split", index=False, na_rep="—")
        pd.DataFrame(runs).to_excel(xw, sheet_name="runs", index=False, na_rep="—")
    pd.concat(monthly, ignore_index=True).to_parquet(run_dir / "monthly.parquet", index=False)
    pd.concat(preds, ignore_index=True).to_parquet(run_dir / "predictions_eval.parquet", index=False)
    pd.DataFrame(runs).to_parquet(run_dir / "runs.parquet", index=False)
    ens_ev = ps[(ps.set == "eval") & (ps.member != "seed")]
    tbl = ens_ev.groupby(["split_type", "model"])["top8_excess_ann_pct"].agg(["mean", "std", "count"]).round(2)
    summary = {"run_dir": str(run_dir), "panel": str(args.panel), "factor_set": str(args.factor_set), "floor_run": str(floor),
               "tag": args.tag, "arch": "attention", "config": {k: (str(v) if isinstance(v, Path) else v) for k, v in vars(args).items()},
               "n_months": int(len(months)), "n_inputs": int(F), "n_runs": len(jobs),
               "eval_top8_excess_by_split_type": {f"{a}/{b}": {"mean": float(r["mean"]), "std": float(r["std"]), "n": int(r["count"])}
                                                  for (a, b), r in tbl.iterrows()},
               "runs_stats": pd.DataFrame(runs).groupby("objective")[["best_epoch", "seconds"]].mean().round(1).to_dict("index"),
               "elapsed_s": round(time.time() - t0, 1)}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    heartbeat("done")
    log.info("EVAL top-8 excess %%/yr by split type and model:\n%s", tbl.to_string())
    log.info("done in %.1f min", (time.time() - t0) / 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
