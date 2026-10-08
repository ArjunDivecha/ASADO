#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/blend.py
=============================================================================

INPUT FILES:
- <this folder>/results/walk_<ts>_default_s<N>/predictions_oos.parquet and summary.json
    The independent draws of the default model (walk_forward.py: rolling 60-month
    window, 30 nets per fold, cleaned v3 panel). Each holds out-of-sample scores for
    nn_mse (30-net ensemble) and ridge per (date, country). In the worktree:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/
- The panel named in summary.json (fwd_ret, bench_ret):
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v3_clean/feature_panel_v3_clean.parquet

OUTPUT FILES (in <this folder>/results/blend_<YYYYMMDD_HHMMSS>/):
- blend.parquet / blend.xlsx   per (member, model, rule): OOS excess %/yr, t, IR, hit, turnover,
                               max relative drawdown, first/second half, by decade
- monthly.parquet              per (member, model, rule, date): basket return, benchmark, excess, names changed
- summary.json, run.log

VERSION: 1.0
LAST UPDATED: 2026-10-07
AUTHOR: Claude for Arjun Divecha

DESCRIPTION:
Tests whether combining the default net and ridge beats either alone. The net
and ridge agree on only about 4 of their 8 picks, and their monthly excess
returns correlate 0.58, so a blend should diversify.

The blend is fixed in advance, not searched: within each month, each model's
scores are z-scored across the countries that month, and the blend score is
0.5 x z(net) + 0.5 x z(ridge). Baskets are formed with the default hysteresis
rule (hold while ranked <= 16) and the plain top-8 rule. Reported per draw,
as the mean of the draws (draws' baskets held in equal thirds), and paired
against the net alone and ridge alone on the same months.

Nothing is retrained; all scores are the saved out-of-sample ones. Gross of costs.

DEPENDENCIES: pandas, numpy, pyarrow, xlsxwriter (experiment .venv); imports hysteresis, pool_draws

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model"
  .venv/bin/python blend.py
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

EXP_DIR = Path(__file__).resolve().parent  # this script's own folder: works from the exp/NN worktree or the main checkout
sys.path.insert(0, str(EXP_DIR))
from hysteresis import DEFAULT_BUFFER, build_baskets  # noqa: E402
from pool_draws import stats  # noqa: E402

RESULTS = EXP_DIR / "results"
WEIGHTS = {"nn_mse": 0.5, "ridge": 0.5}     # fixed a priori
K = 8
log = logging.getLogger("blend")


def tstat(x: pd.Series) -> float:
    x = x.dropna()
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 else float("nan")


def month_z(df: pd.DataFrame, col: str) -> pd.Series:
    g = df.groupby("date")[col]
    return (df[col] - g.transform("mean")) / g.transform("std").replace(0, np.nan)


def main() -> int:
    t0 = time.time()
    run_dir = RESULTS / f"blend_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=False)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    log.setLevel(logging.INFO)
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler(run_dir / "run.log")):
        h.setFormatter(fmt); log.addHandler(h)

    pat = re.compile(r"^walk_\d{8}_\d{6}_default_s(\d+)$")
    draws = {int(m.group(1)): p for p in sorted(RESULTS.glob("walk_*")) if (m := pat.match(p.name)) and (p / "summary.json").exists()}
    if not draws:
        log.error("no default draws found under %s", RESULTS)
        return 1
    s0 = json.load(open(next(iter(draws.values())) / "summary.json"))
    pnl = pd.read_parquet(Path(s0["panel"]), columns=["date", "country", "fwd_ret", "bench_ret"])
    rules = {"plain_top8": K, f"buffer_M{DEFAULT_BUFFER}": DEFAULT_BUFFER}
    log.info("draws: %s; weights %s (fixed a priori)", {s: p.name for s, p in draws.items()}, WEIGHTS)

    rows, monthly, decade_rows = [], [], []
    per_draw = {}
    for s, p in sorted(draws.items()):
        pr = pd.read_parquet(p / "predictions_oos.parquet")
        w = pr.pivot_table(index=["date", "country"], columns="model", values="score").reset_index()
        ex = pr[pr.model == "ridge"][["date", "country", "fwd_excess"]]
        w = w.merge(ex, on=["date", "country"]).merge(pnl, on=["date", "country"])
        w["z_nn_mse"] = month_z(w, "nn_mse"); w["z_ridge"] = month_z(w, "ridge")
        w["blend"] = sum(wt * w[f"z_{m}"] for m, wt in WEIGHTS.items())
        # score correlation diagnostics
        ic = w.groupby("date").apply(lambda d: d["nn_mse"].rank().corr(d["ridge"].rank()))
        log.info("draw s%d: within-month rank corr(net, ridge) = %.2f", s, ic.mean())
        for model, col in (("blend", "blend"), ("nn_mse", "nn_mse"), ("ridge", "ridge")):
            d = w[["date", "country", "fwd_excess", "fwd_ret", "bench_ret"]].assign(score=w[col])
            for rule, M in rules.items():
                b = build_baskets(d, K, M)
                per_draw[(s, model, rule)] = b
    # per draw rows (ridge identical across draws -> once), and mean of draws
    for model in ["blend", "nn_mse", "ridge"]:
        for rule in rules:
            members = {f"draw s{s}": per_draw[(s, model, rule)] for s in sorted(draws)} if model != "ridge" else {"deterministic": per_draw[(min(draws), model, rule)]}
            for mem, b in members.items():
                st = stats(b, K); st.update({"member": mem, "model": model, "rule": rule}); rows.append(st)
                bb = b.copy(); bb.insert(0, "rule", rule); bb.insert(0, "model", model); bb.insert(0, "member", mem); monthly.append(bb)
            if model != "ridge":
                bs = [per_draw[(s, model, rule)].set_index("date") for s in sorted(draws)]
                mb = pd.DataFrame({"basket_ret": pd.concat([b["basket_ret"] for b in bs], axis=1).mean(axis=1), "bench_ret": bs[0]["bench_ret"],
                                   "excess": pd.concat([b["excess"] for b in bs], axis=1).mean(axis=1),
                                   "names_changed": pd.concat([b["names_changed"] for b in bs], axis=1).mean(axis=1),
                                   "n_held": bs[0]["n_held"]}).reset_index()
                st = stats(mb, K); st.update({"member": "mean of draws", "model": model, "rule": rule}); rows.append(st)
                mb.insert(0, "rule", rule); mb.insert(0, "model", model); mb.insert(0, "member", "mean of draws"); monthly.append(mb)
    res = pd.DataFrame(rows)
    mo = pd.concat(monthly, ignore_index=True)
    mo["date"] = pd.to_datetime(mo["date"])

    def series(model, rule, member):
        return mo[(mo.model == model) & (mo.rule == rule) & (mo.member == member)].set_index("date")["excess"].sort_index()
    paired, corr, decades = {}, {}, {}
    for rule in rules:
        bl = series("blend", rule, "mean of draws"); nn = series("nn_mse", rule, "mean of draws"); rg = series("ridge", rule, "deterministic")
        for name, other in (("net", nn), ("ridge", rg)):
            d = bl - other.reindex(bl.index)
            paired[f"{rule}/blend - {name}"] = {"ann_pct": float(d.mean() * 1200), "t": tstat(d), "months_ahead_frac": float((d > 0).mean())}
        corr[rule] = {"blend~net": float(bl.corr(nn)), "blend~ridge": float(bl.corr(rg)), "net~ridge": float(nn.corr(rg))}
        for name, ser in (("blend", bl), ("net", nn), ("ridge", rg)):
            decades[f"{rule}/{name}"] = {f"{a}-{b}": float(ser[(ser.index.year >= a) & (ser.index.year <= b)].mean() * 1200)
                                         for a, b in [(2005, 2009), (2010, 2019), (2020, 2026)]}
        spread = res[(res.model == "blend") & (res.rule == rule) & res.member.str.startswith("draw")]["excess_ann_pct"]
        paired[f"{rule}/blend draw range"] = {"min": float(spread.min()), "max": float(spread.max())}

    res.to_parquet(run_dir / "blend.parquet", index=False)
    mo.to_parquet(run_dir / "monthly.parquet", index=False)
    with pd.ExcelWriter(run_dir / "blend.xlsx", engine="xlsxwriter") as xw:
        res.to_excel(xw, sheet_name="blend", index=False, na_rep="—")
    summary = {"draws": {str(s): str(p) for s, p in draws.items()}, "weights": WEIGHTS, "rules": list(rules),
               "default_rule": f"buffer_M{DEFAULT_BUFFER}", "paired": paired, "correlations": corr, "by_decade": decades,
               "elapsed_s": round(time.time() - t0, 1)}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    pd.set_option("display.width", 250)
    log.info("\n%s", res[["member", "model", "rule", "excess_ann_pct", "t", "info_ratio", "hit_rate", "names_changed_per_month",
                          "first_half_ann_pct", "second_half_ann_pct", "second_half_t", "max_rel_drawdown_pct"]].round(2).to_string(index=False))
    log.info("paired: %s", {k: (f'{v["ann_pct"]:+.2f} t={v["t"]:.2f}' if "ann_pct" in v else v) for k, v in paired.items()})
    log.info("correlations: %s", {k: {kk: round(vv, 2) for kk, vv in v.items()} for k, v in corr.items()})
    log.info("by decade: %s", {k: {kk: round(vv, 1) for kk, vv in v.items()} for k, v in decades.items()})
    log.info("wrote %s", run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
