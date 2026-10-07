#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/pool_draws.py
=============================================================================

INPUT FILES (walk_forward.py runs that differ only in --seed; each saved its
10-net ensemble scores in predictions_oos.parquet):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/walk_20261007_140136/            (expanding, seed 0)
- .../results/walk_*_exp_s1000/, walk_*_exp_s2000/                                              (expanding, seeds 1000, 2000)
- .../results/walk_*_roll60_s0/, walk_*_roll60_s1000/, walk_*_roll60_s2000/                     (rolling 60 months)
- the panel named in each run's summary.json (for fwd_ret, bench_ret)

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/pooled_<YYYYMMDD_HHMMSS>/
    pooled_summary.parquet / .xlsx   per (window, model, rule, member): OOS excess, t, IR, hit, turnover,
                                      max relative drawdown, first/second half
    pooled_monthly.parquet           per (window, model, rule, member, date): basket excess
    summary.json, run.log

VERSION: 1.0
LAST UPDATED: 2026-10-07
AUTHOR: Claude for Arjun Divecha

DESCRIPTION:
Stage 10 found that the net's walk-forward result moves by about three points a
year between seed draws (each draw = 10 nets per fold plus its own early-stopping
slice). This script measures what pooling the draws buys: per window (expanding,
rolling 60), it averages the three draws' 10-net ensemble scores into one 30-net
ensemble per fold, forms baskets with the plain top-8 rule and the default
hysteresis rule (hold while ranked <= 16), and reports them next to each single
draw. Ridge is deterministic, so its three draws are identical and it appears once.

Nothing is retrained; the pooled ensemble is the mean of saved out-of-sample
scores, so it remains genuinely out of sample.

DEPENDENCIES: pandas, numpy, pyarrow, xlsxwriter (experiment .venv); imports hysteresis.build_baskets

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model"
  .venv/bin/python pool_draws.py
=============================================================================
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

EXP_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model")
sys.path.insert(0, str(EXP_DIR))
from hysteresis import DEFAULT_BUFFER, build_baskets  # noqa: E402

RESULTS = EXP_DIR / "results"
SPLIT = pd.Timestamp("2013-06-01")
log = logging.getLogger("pool_draws")


def find_runs() -> dict[tuple[str, int], Path]:
    runs = {}
    base = RESULTS / "walk_20261007_140136"
    if (base / "summary.json").exists():
        runs[("expanding", 0)] = base
    for p in RESULTS.glob("walk_*"):
        m = re.match(r"^walk_\d{8}_\d{6}_(roll60|exp)_s(\d+)$", p.name)
        if m and (p / "summary.json").exists():
            runs[("rolling 60" if m.group(1) == "roll60" else "expanding", int(m.group(2)))] = p
    return runs


def stats(mo: pd.DataFrame, k: int) -> dict:
    exc = mo["excess"]
    wb, wbm = (1 + mo["basket_ret"]).cumprod(), (1 + mo["bench_ret"]).cumprod()
    rel = wb / wbm
    ch = mo["names_changed"].iloc[1:]
    first, second = exc[mo["date"] < SPLIT], exc[mo["date"] >= SPLIT]
    t = lambda x: float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))
    return {"excess_ann_pct": float(exc.mean() * 1200), "t": t(exc), "info_ratio": float(exc.mean() / exc.std(ddof=1) * np.sqrt(12)),
            "hit_rate": float((exc > 0).mean()), "names_changed_per_month": float(ch.mean()),
            "turnover_oneway_pct_yr": float(ch.mean() / k * 1200), "max_rel_drawdown_pct": float((rel / rel.cummax() - 1).min() * 100),
            "first_half_ann_pct": float(first.mean() * 1200), "first_half_t": t(first),
            "second_half_ann_pct": float(second.mean() * 1200), "second_half_t": t(second), "months": int(len(mo))}


def main() -> int:
    t0 = time.time()
    run_dir = RESULTS / f"pooled_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=False)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    log.setLevel(logging.INFO)
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler(run_dir / "run.log")):
        h.setFormatter(fmt); log.addHandler(h)
    runs = find_runs()
    log.info("runs: %s", {f"{w}/s{s}": p.name for (w, s), p in sorted(runs.items())})
    k = 8
    rules = {"plain_top8": k, f"buffer_M{DEFAULT_BUFFER}": DEFAULT_BUFFER}
    rows, monthly = [], []
    for window in sorted({w for w, _ in runs}):
        draws = {s: p for (w, s), p in runs.items() if w == window}
        s0 = json.load(open(next(iter(draws.values())) / "summary.json"))
        pnl = pd.read_parquet(Path(s0["panel"]), columns=["date", "country", "fwd_ret", "bench_ret"])
        preds = {s: pd.read_parquet(p / "predictions_oos.parquet").merge(pnl, on=["date", "country"]) for s, p in draws.items()}
        for model in ["nn_mse", "nn_soft_top8", "ridge"]:
            members = {}
            for s, pr in sorted(preds.items()):
                members[f"draw s{s}"] = pr[pr.model == model]
                if model == "ridge":
                    break                       # deterministic: one draw is all of them
            if model != "ridge" and len(preds) > 1:
                base = members[next(iter(members))][["date", "country", "fwd_excess", "fwd_ret", "bench_ret"]].reset_index(drop=True)
                sc = [m_.set_index(["date", "country"])["score"] for m_ in members.values()]
                pooled = pd.concat(sc, axis=1).mean(axis=1).rename("score").reset_index()
                members[f"pooled {10 * len(preds)} nets"] = base.merge(pooled, on=["date", "country"])
            for mem, d in members.items():
                for rule, M in rules.items():
                    b = build_baskets(d, k, M)
                    st = stats(b, k); st.update({"window": window, "model": model, "rule": rule, "member": mem}); rows.append(st)
                    b.insert(0, "member", mem); b.insert(0, "rule", rule); b.insert(0, "model", model); b.insert(0, "window", window)
                    monthly.append(b)
    sm = pd.DataFrame(rows)
    mo = pd.concat(monthly, ignore_index=True)
    # run-to-run correlation of the net's monthly basket excess between single draws
    corr = {}
    for (window, model, rule), g in mo[mo.member.str.startswith("draw")].groupby(["window", "model", "rule"]):
        piv = g.pivot(index="date", columns="member", values="excess")
        if piv.shape[1] >= 2:
            M_ = piv.corr().values; off = M_[np.triu_indices_from(M_, k=1)]
            corr[f"{window}/{model}/{rule}"] = round(float(off.mean()), 3)
    # paired: pooled net minus ridge; pooled rolling minus pooled expanding
    paired = {}
    def series(window, model, rule, member):
        g = mo[(mo.window == window) & (mo.model == model) & (mo.rule == rule) & (mo.member == member)]
        return g.set_index("date")["excess"]
    for window in sorted({w for w, _ in runs}):
        for rule in rules:
            pm = [m for m in mo[(mo.window == window) & (mo.model == "nn_mse")].member.unique() if m.startswith("pooled")]
            if not pm:
                continue
            d = series(window, "nn_mse", rule, pm[0]) - series(window, "ridge", rule, "draw s0")
            paired[f"{window}/{rule}/pooled net - ridge"] = {"ann_pct": float(d.mean() * 1200), "t": float(d.mean() / (d.std() / np.sqrt(len(d))))}
    for rule in rules:
        for model, mem_e, mem_r in [("nn_mse", None, None), ("ridge", "draw s0", "draw s0")]:
            if model == "nn_mse":
                pe = [m for m in mo[(mo.window == "expanding") & (mo.model == model)].member.unique() if m.startswith("pooled")]
                pr_ = [m for m in mo[(mo.window == "rolling 60") & (mo.model == model)].member.unique() if m.startswith("pooled")]
                if not pe or not pr_:
                    continue
                mem_e, mem_r = pe[0], pr_[0]
            d = series("rolling 60", model, rule, mem_r) - series("expanding", model, rule, mem_e)
            paired[f"{rule}/{model}/rolling - expanding"] = {"ann_pct": float(d.mean() * 1200), "t": float(d.mean() / (d.std() / np.sqrt(len(d))))}
    sm.to_parquet(run_dir / "pooled_summary.parquet", index=False)
    mo.to_parquet(run_dir / "pooled_monthly.parquet", index=False)
    with pd.ExcelWriter(run_dir / "pooled_summary.xlsx", engine="xlsxwriter") as xw:
        sm.to_excel(xw, sheet_name="summary", index=False, na_rep="—")
    (run_dir / "summary.json").write_text(json.dumps({"runs": {f"{w}/s{s}": str(p) for (w, s), p in runs.items()}, "rules": list(rules),
                                                       "split": str(SPLIT.date()), "run_to_run_corr": corr, "paired": paired,
                                                       "elapsed_s": round(time.time() - t0, 1)}, indent=2))
    pd.set_option("display.width", 250)
    log.info("\n%s", sm[["window", "model", "rule", "member", "excess_ann_pct", "t", "info_ratio", "names_changed_per_month",
                         "first_half_ann_pct", "second_half_ann_pct", "second_half_t", "max_rel_drawdown_pct"]].round(2).to_string(index=False))
    log.info("run-to-run correlation (single draws): %s", corr)
    log.info("paired: %s", {k_: f'{v["ann_pct"]:+.2f} t={v["t"]:.2f}' for k_, v in paired.items()})
    log.info("wrote %s", run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
