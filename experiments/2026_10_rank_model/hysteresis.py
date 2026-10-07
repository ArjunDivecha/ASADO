#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/hysteresis.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/walk_<run>/predictions_oos.parquet
    Out-of-sample scores per (model, date, country) from walk_forward.py, with the
    realised fwd_excess. Default: the newest untagged walk_* run with a summary.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_<version>/feature_panel_<version>.parquet
    (the panel named in that run's summary.json) for fwd_ret and bench_ret.

OUTPUT FILES (written INTO the walk run directory, next to the scores they derive from):
- hysteresis_sweep.parquet / .xlsx   one row per (model, buffer M): turnover, excess, t, IR, hit,
                                     relative drawdown, longest underwater, by-era excess
- hysteresis_monthly.parquet         per (model, M, date): basket return, excess, names changed
- hysteresis_summary.json

VERSION: 1.0
LAST UPDATED: 2026-10-07
AUTHOR: Claude (Fable 5.1) for Arjun Divecha

DESCRIPTION:
Turnover control for the top-8 basket by a rank buffer (hysteresis). At each
monthly rebalance a name already held stays in the basket as long as the model
still ranks it in the top M (M >= 8); only names that have fallen below rank M
are sold, and each is replaced by the highest-ranked name not already held. M = 8
is the plain top-8 rule used everywhere else in this project. The model's scores
are untouched, so this is purely an implementation rule, applied to genuinely
out-of-sample scores.

Reported per model and M: names changed per month and one-way turnover (%/yr),
annualised excess over the equal-weight average with its t-stat, information
ratio, hit rate, maximum relative drawdown (basket wealth / benchmark wealth)
and longest underwater stretch, and excess by era. Gross of costs; turnover is
information, not a penalty.

DEPENDENCIES: pandas, numpy, pyarrow, xlsxwriter (experiment .venv)

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model"
  .venv/bin/python hysteresis.py
  .venv/bin/python hysteresis.py --walk-run results/walk_20261007_130906 --buffers 8,10,12,14,16,20
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

EXP_DIR = Path(__file__).resolve().parent  # this script's own folder: works from the exp/NN worktree or the main checkout
RESULTS = EXP_DIR / "results"
# The project default (Arjun, 2026-10-07): hold a name while the model still ranks it in the top 16
# of 34 — "still in the top half" — replace only names that fall below. Chosen a priori from a
# flat sweep over M = 12..16 on the clean walk-forward; walk_forward.py uses it as its headline rule.
DEFAULT_BUFFER = 16


def latest_walk() -> Path:
    pat = re.compile(r"^walk_\d{8}_\d{6}$")
    runs = sorted(p for p in RESULTS.glob("walk_*") if p.is_dir() and pat.match(p.name) and (p / "summary.json").exists())
    if not runs:
        raise FileNotFoundError("no completed untagged walk_* run")
    return runs[-1]


def build_baskets(d: pd.DataFrame, k: int, m: int) -> pd.DataFrame:
    """d: one model's rows (date, country, score, fwd_ret, bench_ret). Returns per-date basket stats."""
    rows, held = [], set()
    for dt, g in d.sort_values(["date", "score"], ascending=[True, False]).groupby("date", sort=True):
        ranked = list(g["country"])
        rank_of = {c: i + 1 for i, c in enumerate(ranked)}
        keep = [c for c in ranked if c in held and rank_of[c] <= m]          # survivors, in rank order
        fill = [c for c in ranked if c not in held][: max(0, k - len(keep))]  # best newcomers
        new = set(keep[:k] + fill)
        changed = len(new - held) if held else 0
        held = new
        sel = g[g["country"].isin(new)]
        rows.append({"date": dt, "basket_ret": sel["fwd_ret"].mean(), "bench_ret": g["bench_ret"].iloc[0],
                     "excess": sel["fwd_excess"].mean(), "names_changed": changed, "n_held": len(new)})
    return pd.DataFrame(rows)


def stats(mo: pd.DataFrame, k: int) -> dict:
    exc = mo["excess"]
    wb, wbm = (1 + mo["basket_ret"]).cumprod(), (1 + mo["bench_ret"]).cumprod()
    rel = (wb / wbm); peak = rel.cummax(); dd = rel / peak - 1
    under = (rel < peak).to_numpy(); longest = run = 0
    for u in under:
        run = run + 1 if u else 0; longest = max(longest, run)
    changed = mo["names_changed"].iloc[1:]
    out = {"names_changed_per_month": float(changed.mean()), "turnover_oneway_pct_yr": float(changed.mean() / k * 1200),
           "excess_ann_pct": float(exc.mean() * 1200), "excess_t": float(exc.mean() / (exc.std(ddof=1) / np.sqrt(len(exc)))),
           "info_ratio": float(exc.mean() / exc.std(ddof=1) * np.sqrt(12)), "hit_rate": float((exc > 0).mean()),
           "max_rel_drawdown_pct": float(dd.min() * 100), "longest_underwater_months": int(longest),
           "basket_cagr_pct": float((wb.iloc[-1] ** (12 / len(wb)) - 1) * 100), "months": int(len(mo))}
    yrs = mo["date"].dt.year
    for lab, (a, b) in {"2005_09": (2005, 2009), "2010_19": (2010, 2019), "2020_26": (2020, 2026)}.items():
        x = exc[(yrs >= a) & (yrs <= b)]
        out[f"excess_ann_pct_{lab}"] = float(x.mean() * 1200) if len(x) else np.nan
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--walk-run", type=Path, default=None)
    ap.add_argument("--buffers", default="8,10,12,14,16,20")
    ap.add_argument("--models", default="nn_mse,ridge,nn_soft_top8")
    ap.add_argument("--k", type=int, default=8)
    args = ap.parse_args()
    run = args.walk_run or latest_walk()
    s = json.load(open(run / "summary.json"))
    pr = pd.read_parquet(run / "predictions_oos.parquet")
    pnl = pd.read_parquet(Path(s["panel"]), columns=["date", "country", "fwd_ret", "bench_ret"])
    pr = pr.merge(pnl, on=["date", "country"])
    buffers = [int(b) for b in args.buffers.split(",")]
    models = [m for m in args.models.split(",") if m in pr.model.values]
    sweep, monthly = [], []
    for model in models:
        d = pr[pr.model == model]
        for m in buffers:
            mo = build_baskets(d, args.k, m)
            st = stats(mo, args.k); st.update({"model": model, "buffer_M": m}); sweep.append(st)
            mo.insert(0, "buffer_M", m); mo.insert(0, "model", model); monthly.append(mo)
    sw = pd.DataFrame(sweep)
    cols = ["model", "buffer_M", "names_changed_per_month", "turnover_oneway_pct_yr", "excess_ann_pct", "excess_t", "info_ratio",
            "hit_rate", "max_rel_drawdown_pct", "longest_underwater_months", "basket_cagr_pct",
            "excess_ann_pct_2005_09", "excess_ann_pct_2010_19", "excess_ann_pct_2020_26", "months"]
    sw = sw[cols]
    sw.to_parquet(run / "hysteresis_sweep.parquet", index=False)
    pd.concat(monthly, ignore_index=True).to_parquet(run / "hysteresis_monthly.parquet", index=False)
    with pd.ExcelWriter(run / "hysteresis_sweep.xlsx", engine="xlsxwriter") as xw:
        sw.to_excel(xw, sheet_name="sweep", index=False, na_rep="—")
    (run / "hysteresis_summary.json").write_text(json.dumps({"walk_run": str(run), "k": args.k, "buffers": buffers, "models": models,
                                                               "rule": "hold while ranked <= M; replace with best non-held",
                                                               "sweep": sw.to_dict("records")}, indent=2, default=str))
    pd.set_option("display.width", 220)
    print(f"walk run: {run}")
    print(sw.round(2).to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
