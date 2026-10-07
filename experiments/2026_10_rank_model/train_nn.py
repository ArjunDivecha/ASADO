#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/train_nn.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v1/feature_panel_v1.parquet
    Model-ready panel (build_panel.py): one row per (date, country), 256 factor
    columns with publication lags applied, target fwd_excess.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/factor_set_v1.json
    Feature list and sources (for the per-source presence columns).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/floor_<latest>/per_split.parquet
    The floor's per-split results, so ridge and the reference factor appear
    next to the nets on the SAME splits (paired comparison). Optional.
- experiments/2026_10_rank_model/train_floor.py  (imported: month_metrics,
    aggregate, soft_topk — the exact scoring used for the floor).

OUTPUT FILES (inside
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/nn_<YYYYMMDD_HHMMSS>/ ):
- per_split.parquet / per_split.xlsx   one row per (split, model, seed|ensemble, train|eval)
- monthly.parquet                      per (split, model, set, month) metrics for the seed-ensembles
- predictions_eval.parquet             ensemble scores per (split, model, date, country)
- runs.parquet                         one row per trained net: best epoch, inner-val score, seconds
- capacity_check.json                  can the net fit 24 months nearly perfectly?
- summary.json, heartbeat.json, run.log

VERSION: 1.0
LAST UPDATED: 2026-10-07
AUTHOR: Claude (Fable 5.1) for Arjun Divecha

DESCRIPTION:
Stage 5 of the country top-8 ranking model: a small neural network shared
across countries, scored on exactly the same 30 random month splits and 5
contiguous blocks as the floor (train_floor.py), with the same metrics.

Architecture: inputs (256 clipped, zero-imputed z-scores + 15 per-source
"fraction present" columns) -> hidden layers (default 64, 32; GELU, dropout)
-> one score per country-month. The same weights score every country, so a
pattern learned on Brazil applies to India.

Three training objectives, same network:
  mse        squared error on next-month excess return; pick the top 8 scores.
  soft_top8  the objective itself: within each month, z-score the 34 network
             outputs (so the net cannot sharpen the selection by scaling),
             turn them into memberships in (0,1) summing to 8 through a
             sigmoid threshold (exact gradient via the implicit-function
             theorem, in SoftTopK below), and maximise the membership-weighted
             next-month excess return, i.e. the expected excess of the basket.
             Linear in the selection, so no reinforcement learning is needed.
  mse_then_soft  warm-start on mse, then fine-tune on soft_top8 (Astra's
             suggestion; the comparison tells whether the direct objective
             adds anything over "predict then select").

Protocol (identical to the floor): per split, 12% of TRAINING months are held
back for early stopping on the soft-top-8 expected excess; evaluation months
never touch training, stopping or selection. Five seeds per (split, objective);
the seed-average of scores is the "ensemble" model and the headline; single-
seed results are kept to show the variance. Shuffled-label control on the
first 10 random splits for the soft objective. A fit-capacity check trains an
unregularised net on 24 months and reports how close to perfect it gets.

Runs are independent, so they are farmed over a process pool (CPU, one thread
per worker; these nets are far too small for the GPU to help).

DEPENDENCIES: torch, pandas, numpy, scipy, pyarrow, xlsxwriter (experiment .venv)

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model"
  .venv/bin/python train_nn.py
  .venv/bin/python train_nn.py --n-random 30 --n-blocks 5 --seeds 5 --hidden 64,32 --workers 14
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

# One BLAS/OpenMP thread per process: the nets are tiny and parallelism comes from the
# process pool. Without this each of the 14 workers spawned ~16 Accelerate/OpenMP threads
# and the first runs were ~3x slower than the per-net timings (load average 269 on 16
# cores, 2026-10-07). Must be set before torch/numpy are imported; spawned workers
# re-import this module so they inherit it.
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "OPENBLAS_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

EXP_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model")
sys.path.insert(0, str(EXP_DIR))
from train_floor import PANEL, FACTOR_SET, RESULTS_ROOT, SOFT_TAUS, aggregate, month_metrics  # noqa: E402

OBJECTIVES = ["mse", "soft_top8", "mse_then_soft"]
log = logging.getLogger("train_nn")


# ── torch pieces (imported inside workers too) ───────────────────────────────
def _torch():
    import torch
    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass  # already set once in this process
    return torch


def build_model(torch, n_in: int, hidden: list[int], dropout: float):
    nn = torch.nn
    layers, d = [], n_in
    for h in hidden:
        layers += [nn.Linear(d, h), nn.GELU(), nn.Dropout(dropout)]
        d = h
    layers += [nn.Linear(d, 1)]
    return nn.Sequential(*layers)


def make_soft_topk(torch):
    """Memberships m = sigmoid((z - b)/tau) with b s.t. sum(m) = k over the valid
    entries; exact gradient via the implicit-function theorem:
      dm_i/dz_j = (s_i/tau) * (delta_ij - s_j / sum(s)),  s_i = m_i (1 - m_i)."""
    class SoftTopK(torch.autograd.Function):
        @staticmethod
        def forward(ctx, z, mask, k, tau):
            # z: (B, N) z-scored scores; mask: (B, N) bool; bisection on b per row
            zm = torch.where(mask, z, torch.full_like(z, -1e4))
            lo = zm.min(dim=1, keepdim=True).values - 20 * tau
            hi = z.masked_fill(~mask, -1e4).max(dim=1, keepdim=True).values + 20 * tau
            for _ in range(60):
                b = 0.5 * (lo + hi)
                s = torch.sigmoid((z - b) / tau) * mask
                over = s.sum(dim=1, keepdim=True) > k
                lo = torch.where(over, b, lo)
                hi = torch.where(over, hi, b)
            b = 0.5 * (lo + hi)
            m = torch.sigmoid((z - b) / tau) * mask
            ctx.save_for_backward(m, mask)
            ctx.tau = tau
            return m

        @staticmethod
        def backward(ctx, g):
            m, mask = ctx.saved_tensors
            s = m * (1 - m) * mask                     # sigma'
            ssum = s.sum(dim=1, keepdim=True).clamp_min(1e-12)
            # (J^T g)_j = (s_j/tau) * (g_j - sum_i g_i s_i / sum s)
            gz = (s / ctx.tau) * (g - (g * s).sum(dim=1, keepdim=True) / ssum)
            return gz, None, None, None
    return SoftTopK.apply


def month_zscore(torch, s, mask):
    n = mask.sum(dim=1, keepdim=True).clamp_min(1)
    mu = (s * mask).sum(dim=1, keepdim=True) / n
    var = (((s - mu) * mask) ** 2).sum(dim=1, keepdim=True) / n
    return (s - mu) / (var.sqrt() + 1e-6)


_DATA: dict = {}


def _init_worker(X, Y, M):
    """Each pool worker receives the panel tensors once (not once per job)."""
    _DATA.update(X=X, Y=Y, M=M)


def train_one(job: dict) -> dict:
    """Train one net; returns scores for train/eval rows (ordered as given) plus run info."""
    torch = _torch()
    torch.manual_seed(job["seed"])
    np.random.seed(job["seed"])
    soft_topk = make_soft_topk(torch)
    X, M = _DATA["X"], _DATA["M"]                     # (months, N, F), (months, N) bool
    Y = job.get("Y_override", _DATA["Y"])             # shuffled-label jobs carry their own (small) Y
    tr_idx, va_idx = job["tr_months"], job["va_months"]
    k, tau, hidden = job["k"], job["tau"], job["hidden"]
    Xt = torch.tensor(X, dtype=torch.float32)
    Yt = torch.tensor(Y, dtype=torch.float32)
    Mt = torch.tensor(M, dtype=torch.bool)
    model = build_model(torch, X.shape[-1], hidden, job["dropout"])
    opt = torch.optim.AdamW(model.parameters(), lr=job["lr"], weight_decay=job["weight_decay"])

    def forward(idx):
        s = model(Xt[idx]).squeeze(-1)
        return s

    def loss_fn(s, y, m, objective):
        if objective == "mse":
            per_month = (((s - y) ** 2) * m).sum(dim=1) / m.sum(dim=1).clamp_min(1)
            return per_month.mean()
        z = month_zscore(torch, s, m)
        mem = soft_topk(z, m, k, tau)
        w = mem / k
        return -((w * y).sum(dim=1)).mean() * 100.0  # % per month, negated

    def val_score():
        model.eval()
        with torch.no_grad():
            s = forward(va_idx)
            z = month_zscore(torch, s, Mt[va_idx])
            mem = soft_topk(z, Mt[va_idx], k, 0.25)
            v = float(((mem / k) * Yt[va_idx]).sum(dim=1).mean())
        model.train()
        return v

    phases = [("mse", job["epochs"]), ("soft_top8", job["epochs"])] if job["objective"] == "mse_then_soft" \
        else [(job["objective"], job["epochs"])]
    best_state, best_val, best_epoch, epoch_counter, t0 = None, -1e9, 0, 0, time.time()
    rng = np.random.default_rng(job["seed"])
    for objective, n_epochs in phases:
        bad = 0
        for ep in range(n_epochs):
            perm = rng.permutation(tr_idx)
            for i in range(0, len(perm), job["batch_months"]):
                idx = perm[i:i + job["batch_months"]]
                s = forward(idx)
                loss = loss_fn(s, Yt[idx], Mt[idx], objective)
                opt.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(), 5.0)
                opt.step()
            epoch_counter += 1
            v = val_score()
            if v > best_val + 1e-6:
                best_val, best_epoch, bad = v, epoch_counter, 0
                best_state = {kk: vv.detach().clone() for kk, vv in model.state_dict().items()}
            else:
                bad += 1
                if bad >= job["patience"]:
                    break
    if best_state is not None:
        model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        s_all = model(Xt).squeeze(-1).numpy()
    return {"split": job["split"], "objective": job["objective"], "seed": job["seed"], "tag": job["tag"],
            "scores": s_all, "best_epoch": best_epoch, "epochs_run": epoch_counter,
            "inner_val_soft_excess_pct_month": best_val * 100, "seconds": round(time.time() - t0, 1)}


# ── main ─────────────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", type=Path, default=PANEL)
    ap.add_argument("--factor-set", type=Path, default=FACTOR_SET)
    ap.add_argument("--floor-run", type=Path, default=None, help="floor results dir for paired comparison (default newest)")
    ap.add_argument("--n-random", type=int, default=30)
    ap.add_argument("--eval-frac", type=float, default=0.20)
    ap.add_argument("--n-blocks", type=int, default=5)
    ap.add_argument("--n-shuffle", type=int, default=10)
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--objectives", default=",".join(OBJECTIVES))
    ap.add_argument("--k", type=int, default=8)
    ap.add_argument("--tau", type=float, default=0.5, help="soft-top-k temperature during training (on z-scored scores)")
    ap.add_argument("--hidden", default="64,32")
    ap.add_argument("--dropout", type=float, default=0.15)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--weight-decay", type=float, default=1e-2)
    ap.add_argument("--batch-months", type=int, default=32)
    ap.add_argument("--epochs", type=int, default=300)
    ap.add_argument("--patience", type=int, default=30)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 4) - 2))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--tag", default="", help="ablation tag; run dir becomes nn_<ts>_<tag>; floor rows joined from floor_*_<tag>")
    ap.add_argument("--no-presence", action="store_true", help="drop the per-source 'fraction present' input columns")
    args = ap.parse_args()
    hidden = [int(h) for h in args.hidden.split(",")]
    objectives = [o for o in args.objectives.split(",") if o]

    t0 = time.time()
    run_dir = RESULTS_ROOT / (f"nn_{datetime.now().strftime('%Y%m%d_%H%M%S')}" + (f"_{args.tag}" if args.tag else ""))
    run_dir.mkdir(parents=True, exist_ok=False)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    log.setLevel(logging.INFO)
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler(run_dir / "run.log")):
        h.setFormatter(fmt)
        log.addHandler(h)
    log.info("run dir: %s", run_dir)

    # ── data: (months, N, F) tensors with mask ──────────────────────────────
    fs = json.load(open(args.factor_set))
    feats = [f["variable"] for f in fs["factors"]]
    src_of = {f["variable"]: f["source"] for f in fs["factors"]}
    panel = pd.read_parquet(args.panel).sort_values(["date", "country"]).reset_index(drop=True)
    months = np.sort(panel["date"].unique())
    countries = sorted(panel["country"].unique())
    mi = {m: i for i, m in enumerate(months)}
    ci = {c: i for i, c in enumerate(countries)}
    sources = [] if args.no_presence else sorted(set(src_of.values()))
    present = np.stack([panel[[v for v in feats if src_of[v] == s]].notna().mean(axis=1).to_numpy() for s in sources], axis=1) \
        if sources else np.zeros((len(panel), 0))
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
    log.info("tensor panel: %d months x %d countries x %d inputs (%d factors + %d presence); %d valid rows",
             *X.shape, len(feats), len(sources), int(M.sum()))

    # ── splits: identical construction to train_floor.py ───────────────────
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

    def inner_split(train_months: np.ndarray, seed: int):
        rng = np.random.default_rng(seed + 1000)
        val = rng.permutation(train_months)[: max(3, int(round(0.12 * len(train_months))))]
        return np.setdiff1d(train_months, val), np.sort(val)

    base = {"k": args.k, "tau": args.tau, "hidden": hidden, "dropout": args.dropout,
            "lr": args.lr, "weight_decay": args.weight_decay, "batch_months": args.batch_months,
            "epochs": args.epochs, "patience": args.patience}

    # ── jobs ────────────────────────────────────────────────────────────────
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
            rng = np.random.default_rng(sseed + 7)
            Ysh = Y.copy()
            for m in tr_all:                       # permute realised returns across countries within each training month
                idx = np.flatnonzero(M[m]); Ysh[m, idx] = Ysh[m, rng.permutation(idx)]
            for s in range(args.seeds):
                jobs.append(base | {"Y_override": Ysh, "split": split_name, "objective": "soft_top8", "seed": sseed * 10 + s,
                                    "tag": "shuffled", "tr_months": fit_m, "va_months": val_m})
    # fit-capacity check: 24 months, no regularisation, fit until (nearly) perfect
    cap_months = np.random.default_rng(args.seed + 999).permutation(len(months))[:24]
    jobs.append(base | {"split": "capacity", "objective": "soft_top8", "seed": 12345, "tag": "capacity",
                        "tr_months": cap_months, "va_months": cap_months, "dropout": 0.0, "weight_decay": 0.0,
                        "epochs": 600, "patience": 600, "hidden": [128, 64]})
    log.info("jobs: %d (%d splits x %d objectives x %d seeds + %d shuffled + 1 capacity); workers=%d",
             len(jobs), len(splits), len(objectives), args.seeds,
             sum(j["tag"] == "shuffled" for j in jobs), args.workers)

    results, done = [], 0
    def heartbeat(last):
        el = time.time() - t0
        (run_dir / "heartbeat.json").write_text(json.dumps({
            "last": last, "runs_done": done, "runs_total": len(jobs), "elapsed_s": round(el),
            "eta_s": round(el / done * (len(jobs) - done)) if done else None,
            "updated": datetime.now().isoformat(timespec="seconds")}, indent=2))
    with ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker, initargs=(X, Y, M)) as pool:
        futs = {pool.submit(train_one, j): (j["split"], j["objective"], j["seed"], j["tag"]) for j in jobs}
        for fut in as_completed(futs):
            r = fut.result(); results.append(r); done += 1
            if done % 25 == 0 or done == len(jobs):
                heartbeat(f'{r["split"]}/{r["objective"]}/seed{r["seed"]}')
                log.info("  %d/%d runs (%.0fs)", done, len(jobs), time.time() - t0)

    # ── score: per seed and seed-ensemble, same metrics as the floor ────────
    ev_of = {name: ev for name, _, ev in splits}
    type_of = {name: t for name, t, _ in splits}
    per_split, monthly, preds, runs = [], [], [], []
    for r in results:
        runs.append({k: v for k, v in r.items() if k != "scores"})
    grouped: dict[tuple, list] = {}
    for r in results:
        if r["tag"] == "capacity":
            continue
        grouped.setdefault((r["split"], r["objective"], r["tag"]), []).append(r)

    def rows_for(split, scores_rows, set_name):
        ev = ev_of[split][r_m]
        mask = ev if set_name == "eval" else ~ev
        return month_metrics(scores_rows[mask], y_rows[mask], r_m[mask], args.k)

    for (split, obj, tag), rs in grouped.items():
        model_name = f"nn_{obj}" + ("_shuffled" if tag == "shuffled" else "")
        seed_scores = []
        for r in rs:
            sc_rows = r["scores"][r_m, r_c]
            seed_scores.append(sc_rows)
            for set_name in ("train", "eval"):
                mm = rows_for(split, sc_rows, set_name)
                agg = aggregate(mm); agg.update({"split": split, "split_type": type_of[split], "model": model_name,
                                                 "seed": r["seed"], "member": "seed", "set": set_name,
                                                 "best_epoch": r["best_epoch"]})
                per_split.append(agg)
        ens = np.mean(seed_scores, axis=0)
        for set_name in ("train", "eval"):
            mm = rows_for(split, ens, set_name)
            agg = aggregate(mm); agg.update({"split": split, "split_type": type_of[split], "model": model_name,
                                             "seed": -1, "member": "ensemble", "set": set_name})
            per_split.append(agg)
            mm.insert(0, "set", set_name); mm.insert(0, "model", model_name); mm.insert(0, "split", split)
            mm["date"] = months[mm["month_id"].to_numpy()]
            monthly.append(mm)
        ev = ev_of[split][r_m]
        preds.append(pd.DataFrame({"split": split, "model": model_name, "date": panel["date"][ev].to_numpy(),
                                   "country": panel["country"][ev].to_numpy(), "score": ens[ev], "fwd_excess": y_rows[ev]}))

    cap = next(r for r in results if r["tag"] == "capacity")
    cap_rows = np.isin(r_m, cap_months)
    cap_mm = month_metrics(cap["scores"][r_m, r_c][cap_rows], y_rows[cap_rows], r_m[cap_rows], args.k)
    perfect = month_metrics(y_rows[cap_rows], y_rows[cap_rows], r_m[cap_rows], args.k)
    capacity = {"months": 24, "hidden": [128, 64], "epochs_run": cap["epochs_run"],
                "fitted_top8_excess_pct_month": float(cap_mm["top8_excess"].mean() * 100),
                "perfect_foresight_top8_excess_pct_month": float(perfect["top8_excess"].mean() * 100),
                "fitted_precision8": float(cap_mm["precision8"].mean()), "fitted_rank_ic": float(cap_mm["rank_ic"].mean())}
    log.info("capacity check (24 months, no regularisation): fitted top-8 %.2f%%/month vs perfect %.2f%%/month, precision@8 %.2f, IC %.2f",
             capacity["fitted_top8_excess_pct_month"], capacity["perfect_foresight_top8_excess_pct_month"],
             capacity["fitted_precision8"], capacity["fitted_rank_ic"])

    ps = pd.DataFrame(per_split)
    # bring the floor's ridge / reference rows alongside (same split names)
    import re as _re
    pat = _re.compile(r"^floor_\d{8}_\d{6}" + (f"_{_re.escape(args.tag)}$" if args.tag else "$"))
    floor = args.floor_run or (sorted(p for p in RESULTS_ROOT.glob("floor_*") if p.is_dir() and pat.match(p.name)) or [None])[-1]
    if floor and (Path(floor) / "per_split.parquet").exists():
        fl = pd.read_parquet(Path(floor) / "per_split.parquet")
        fl = fl[fl.model.isin(["ridge", "reference_REER_CS", "lgbm_regression"])].copy()
        fl["seed"], fl["member"] = -1, "floor"
        ps = pd.concat([ps, fl[[c for c in fl.columns if c in ps.columns]]], ignore_index=True)
        log.info("joined floor rows from %s", floor)

    ps.to_parquet(run_dir / "per_split.parquet", index=False)
    with pd.ExcelWriter(run_dir / "per_split.xlsx", engine="xlsxwriter") as xw:
        ps.to_excel(xw, sheet_name="per_split", index=False, na_rep="—")
        pd.DataFrame(runs).to_excel(xw, sheet_name="runs", index=False, na_rep="—")
    pd.concat(monthly, ignore_index=True).to_parquet(run_dir / "monthly.parquet", index=False)
    pd.concat(preds, ignore_index=True).to_parquet(run_dir / "predictions_eval.parquet", index=False)
    pd.DataFrame(runs).to_parquet(run_dir / "runs.parquet", index=False)
    (run_dir / "capacity_check.json").write_text(json.dumps(capacity, indent=2))

    ens_ev = ps[(ps.set == "eval") & (ps.member != "seed")]
    tbl = ens_ev.groupby(["split_type", "model"])["top8_excess_ann_pct"].agg(["mean", "std", "count"]).round(2)
    summary = {
        "run_dir": str(run_dir), "panel": str(args.panel), "floor_run": str(floor), "tag": args.tag,
        "factor_set": str(args.factor_set),
        "config": {k: (v if not isinstance(v, Path) else str(v)) for k, v in vars(args).items()} | {"hidden": hidden, "soft_taus_eval": SOFT_TAUS},
        "n_months": int(len(months)), "n_inputs": int(F), "n_runs": len(jobs), "capacity_check": capacity,
        "eval_top8_excess_by_split_type": {f"{a}/{b}": {"mean": float(r["mean"]), "std": float(r["std"]), "n": int(r["count"])}
                                           for (a, b), r in tbl.iterrows()},
        "runs_stats": pd.DataFrame(runs).groupby("objective")[["best_epoch", "seconds"]].mean().round(1).to_dict("index"),
        "elapsed_s": round(time.time() - t0, 1),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    heartbeat("done")
    log.info("EVAL top-8 excess %%/yr by split type and model (ensembles + floor):\n%s", tbl.to_string())
    log.info("done in %.1f min", (time.time() - t0) / 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
