#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/default_model.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/walk_<ts>_default_s<N>/
    Independent walk_forward.py draws of the project default (rolling 60-month
    window, 30 nets per fold, cleaned v3 panel), differing only in --seed. Each
    holds predictions_oos.parquet (30-net ensemble scores per model, date,
    country) and summary.json (which names the panel).
- The panel named in summary.json, for fwd_ret and bench_ret:
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v3_clean/feature_panel_v3_clean.parquet

OUTPUT FILES (in /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/default_<YYYYMMDD_HHMMSS>/):
- draws.parquet / draws.xlsx   per (member, model, rule): OOS excess %/yr, t, IR, hit, turnover,
                               max relative drawdown, first/second half; member = each draw,
                               "mean of draws" (monthly excess averaged across draws), and the pooled
                               ensemble of all draws' nets
- monthly.parquet              per (member, model, rule, date): basket return, benchmark, excess, names changed
- by_year.parquet              per (member, model, rule, year): annualised excess
- summary.json, run.log

VERSION: 1.0
LAST UPDATED: 2026-10-07
AUTHOR: Claude for Arjun Divecha

DESCRIPTION:
Produces the project's headline numbers for the default model with a range
instead of a single run. For each independent draw it forms baskets from the
saved out-of-sample scores under the plain top-8 rule and the default
hysteresis rule (hold while ranked <= 16), and reports every draw, the mean of
the draws, the spread between them, and the pooled ensemble of all draws'
nets (score average). Ridge is deterministic, so its draws are identical and
it appears once. Paired net-minus-ridge comparisons and the run-to-run
correlation between draws are recorded in summary.json.

Nothing is retrained; all figures are formed from genuinely out-of-sample
scores. Gross of costs; turnover is reported as information.

DEPENDENCIES: pandas, numpy, pyarrow, xlsxwriter (experiment .venv); imports hysteresis, pool_draws

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model"
  .venv/bin/python default_model.py
  .venv/bin/python default_model.py --tag-prefix default_s
=============================================================================
"""

from __future__ import annotations

import argparse
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
from pool_draws import SPLIT, stats  # noqa: E402

RESULTS = EXP_DIR / "results"
log = logging.getLogger("default_model")


def tstat(x: pd.Series) -> float:
    x = x.dropna()
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 and x.std(ddof=1) > 0 else float("nan")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag-prefix", default="default_s")
    ap.add_argument("--k", type=int, default=8)
    args = ap.parse_args()
    t0 = time.time()
    run_dir = RESULTS / f"default_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=False)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    log.setLevel(logging.INFO)
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler(run_dir / "run.log")):
        h.setFormatter(fmt); log.addHandler(h)

    pat = re.compile(rf"^walk_\d{{8}}_\d{{6}}_{re.escape(args.tag_prefix)}(\d+)$")
    draws = {}
    for p in sorted(RESULTS.glob("walk_*")):
        m = pat.match(p.name)
        if m and (p / "summary.json").exists():
            draws[int(m.group(1))] = p
    if len(draws) < 2:
        log.error("need at least two completed draws matching %s*; found %s", args.tag_prefix, list(draws))
        return 1
    s0 = json.load(open(next(iter(draws.values())) / "summary.json"))
    cfg = s0["config"]
    log.info("draws: %s; window=%s seeds/fold=%s buffer=%s", {s: p.name for s, p in draws.items()}, cfg.get("window"), cfg.get("seeds"), cfg.get("buffer"))
    pnl = pd.read_parquet(Path(s0["panel"]), columns=["date", "country", "fwd_ret", "bench_ret"])
    preds = {s: pd.read_parquet(p / "predictions_oos.parquet").merge(pnl, on=["date", "country"]) for s, p in sorted(draws.items())}
    rules = {"plain_top8": args.k, f"buffer_M{DEFAULT_BUFFER}": DEFAULT_BUFFER}
    nets = [m for m in ["nn_mse", "nn_soft_top8"] if m in next(iter(preds.values())).model.values]

    rows, monthly = [], []
    def add(member, model, rule, b):
        st = stats(b, args.k); st.update({"member": member, "model": model, "rule": rule}); rows.append(st)
        bb = b.copy(); bb.insert(0, "rule", rule); bb.insert(0, "model", model); bb.insert(0, "member", member); monthly.append(bb)

    for model in nets + ["ridge"]:
        per_draw = {}
        for s, pr in preds.items():
            d = pr[pr.model == model]
            for rule, M in rules.items():
                b = build_baskets(d, args.k, M)
                per_draw[(s, rule)] = b
                if model == "ridge" and s != min(preds):
                    continue
                add(f"draw s{s}" if model != "ridge" else "deterministic", model, rule, b)
            if model == "ridge":
                break
        if model == "ridge":
            continue
        # mean of draws: hold the draws' baskets in equal thirds (average monthly basket/benchmark returns)
        for rule in rules:
            bs = [per_draw[(s, rule)].set_index("date") for s in preds]
            mean_b = pd.DataFrame({"basket_ret": pd.concat([b["basket_ret"] for b in bs], axis=1).mean(axis=1),
                                   "bench_ret": bs[0]["bench_ret"],
                                   "excess": pd.concat([b["excess"] for b in bs], axis=1).mean(axis=1),
                                   "names_changed": pd.concat([b["names_changed"] for b in bs], axis=1).mean(axis=1),
                                   "n_held": bs[0]["n_held"]}).reset_index()
            add("mean of draws", model, rule, mean_b)
        # pooled ensemble of all draws' nets
        base = preds[min(preds)][preds[min(preds)].model == model][["date", "country", "fwd_excess", "fwd_ret", "bench_ret"]]
        sc = pd.concat([pr[pr.model == model].set_index(["date", "country"])["score"] for pr in preds.values()], axis=1).mean(axis=1).rename("score")
        pooled = base.merge(sc.reset_index(), on=["date", "country"])
        n_nets = int(cfg.get("seeds", 30)) * len(preds)
        for rule, M in rules.items():
            add(f"pooled {n_nets} nets", model, rule, build_baskets(pooled, args.k, M))

    dr = pd.DataFrame(rows)
    mo = pd.concat(monthly, ignore_index=True)
    by_year = (mo.assign(year=pd.to_datetime(mo["date"]).dt.year).groupby(["member", "model", "rule", "year"])["excess"]
               .agg(lambda x: x.mean() * 1200).rename("excess_ann_pct").reset_index())

    # spread across draws, paired comparisons, run-to-run correlation
    spread, paired, corr = {}, {}, {}
    ridge = {rule: mo[(mo.model == "ridge") & (mo.rule == rule)].set_index("date")["excess"] for rule in rules}
    for model in nets:
        for rule in rules:
            g = dr[(dr.model == model) & (dr.rule == rule) & dr.member.str.startswith("draw")]
            spread[f"{model}/{rule}"] = {"min": float(g.excess_ann_pct.min()), "max": float(g.excess_ann_pct.max()),
                                         "mean": float(g.excess_ann_pct.mean()), "sd": float(g.excess_ann_pct.std(ddof=1))}
            for member in ["mean of draws"] + [m for m in dr.member.unique() if m.startswith("pooled")]:
                ser = mo[(mo.model == model) & (mo.rule == rule) & (mo.member == member)].set_index("date")["excess"]
                d = ser - ridge[rule].reindex(ser.index)
                paired[f"{model}/{rule}/{member} - ridge"] = {"ann_pct": float(d.mean() * 1200), "t": tstat(d),
                                                             "months_ahead_frac": float((d > 0).mean())}
            piv = mo[(mo.model == model) & (mo.rule == rule) & mo.member.str.startswith("draw")].pivot(index="date", columns="member", values="excess")
            if piv.shape[1] >= 2:
                M_ = piv.corr().values; off = M_[np.triu_indices_from(M_, k=1)]
                corr[f"{model}/{rule}"] = {"mean": float(off.mean()), "min": float(off.min()), "max": float(off.max())}

    dr.to_parquet(run_dir / "draws.parquet", index=False)
    mo.to_parquet(run_dir / "monthly.parquet", index=False)
    by_year.to_parquet(run_dir / "by_year.parquet", index=False)
    with pd.ExcelWriter(run_dir / "draws.xlsx", engine="xlsxwriter") as xw:
        dr.to_excel(xw, sheet_name="draws", index=False, na_rep="—")
        by_year.pivot_table(index=["member", "model", "rule"], columns="year", values="excess_ann_pct").to_excel(xw, sheet_name="by_year", na_rep="—")
    oos = mo[(mo.model == "ridge")]
    summary = {"draws": {str(s): str(p) for s, p in draws.items()}, "config": {k: cfg.get(k) for k in ("window", "seeds", "buffer", "hidden", "dropout",
               "weight_decay", "lr", "first_train_months", "objectives", "panel", "factor_set")} | {"panel": s0["panel"], "factor_set": s0.get("factor_set")},
               "oos_start": str(pd.to_datetime(oos["date"]).min().date()), "oos_end": str(pd.to_datetime(oos["date"]).max().date()),
               "oos_months": int(oos[oos.rule == "plain_top8"].shape[0]), "rules": list(rules), "default_rule": f"buffer_M{DEFAULT_BUFFER}",
               "spread_across_draws": spread, "paired_vs_ridge": paired, "run_to_run_corr": corr, "split": str(SPLIT.date()),
               "elapsed_s": round(time.time() - t0, 1)}
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    pd.set_option("display.width", 250)
    log.info("\n%s", dr[["member", "model", "rule", "excess_ann_pct", "t", "info_ratio", "hit_rate", "names_changed_per_month",
                         "first_half_ann_pct", "second_half_ann_pct", "second_half_t", "max_rel_drawdown_pct"]].round(2).to_string(index=False))
    log.info("spread across draws: %s", {k: f'{v["mean"]:+.2f} [{v["min"]:+.2f}, {v["max"]:+.2f}]' for k, v in spread.items()})
    log.info("paired vs ridge: %s", {k: f'{v["ann_pct"]:+.2f} t={v["t"]:.2f}' for k, v in paired.items()})
    log.info("run-to-run corr: %s", {k: round(v["mean"], 2) for k, v in corr.items()})
    log.info("wrote %s", run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
