#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/toolkit/swap_ceiling.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/walk_*_default_s*/predictions_oos.parquet
    the three default draws' out-of-sample nn_mse scores, pooled per (date, country), 2005-02 → 2026-09
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v3_clean/feature_panel_v3_clean.parquet
    fwd_ret / bench_ret / fwd_excess. Holdings follow the default rule via veto_test.holdings_for (matches the saved default run to 1e-18).

OUTPUT FILES (in /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/ceiling_<YYYYMMDD_HHMMSS>/):
- monthly.parquet   per month: default excess, perfect-top-8 excess, best/random/near-cut-off gain for 1, 2, 3 swaps
- summary.json, summary.xlsx, report.html (light mode), run.log

VERSION: 1.1 (full 2005-2026 history)   LAST UPDATED: 2026-10-08   AUTHOR: Claude for Arjun Divecha

DESCRIPTION:
The economic action ceiling (Sakana; rung-B phase 0). With hindsight, how much could
replacing k of the default basket's eight names add per year, for k = 1, 2, 3? Reports
the best possible set of up to k swaps (upper bound), the expected random k-swap (what noise buys),
the best swap confined to the cut-off (ranks 6-8 out, 9-11 in), and the perfect top-8
for context. Gross excess vs equal weight. Nothing is predicted; this bounds what any
toolkit, rule or LLM acting through k swaps could achieve.

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model"
  .venv/bin/python toolkit/swap_ceiling.py
=============================================================================
"""
from __future__ import annotations
import json, logging, sys
from datetime import datetime
from pathlib import Path
import numpy as np, pandas as pd

EXP_DIR = Path(__file__).resolve().parent.parent; RESULTS = EXP_DIR / "results"
sys.path.insert(0, str(EXP_DIR / "gdelt_veto"))
from veto_test import load_scores, holdings_for, PANEL  # noqa: E402
K = 8; KS = (1, 2, 3)
log = logging.getLogger("ceiling")


def main() -> int:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S"); run_dir = RESULTS / f"ceiling_{ts}"; run_dir.mkdir(parents=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", handlers=[logging.StreamHandler(), logging.FileHandler(run_dir / "run.log")])
    panel = pd.read_parquet(PANEL, columns=["date", "country", "fwd_ret", "bench_ret", "fwd_excess"]); panel["date"] = pd.to_datetime(panel["date"])
    sc, draws = load_scores(); h = holdings_for(sc, "pooled", panel); h.to_parquet(run_dir / "holdings_full.parquet", index=False)
    log.info("holdings rebuilt from %d draws: %d months", len(draws), h["date"].nunique())
    rows = []
    for dt, g in h.groupby("date", sort=True):
        held = g[g["held"]].sort_values("fwd_excess"); out = g[~g["held"]].sort_values("fwd_excess", ascending=False)
        base = held["fwd_excess"].mean(); r = {"date": dt, "default": base, "perfect_top8": g["fwd_excess"].nlargest(K).mean()}
        m_in, m_out = out["fwd_excess"].mean(), held["fwd_excess"].mean()
        # near cut-off candidate sets by model rank
        lo = g[g["held"] & (g["rank"] >= 6)].sort_values("fwd_excess"); hi = g[(~g["held"]) & (g["rank"] <= 11)].sort_values("fwd_excess", ascending=False)
        def best_upto(ins, outs, k):   # best of UP TO k swaps: pair best-in with worst-out, keep only pairs that gain
            kk = min(k, len(ins), len(outs)); pairs = ins.iloc[:kk].to_numpy() - outs.iloc[:kk].to_numpy()
            return float(np.clip(pairs, 0, None).sum() / K) if kk else 0.0
        for k in KS:
            r[f"best_{k}"] = best_upto(out["fwd_excess"], held["fwd_excess"], k)
            r[f"random_{k}"] = k * (m_in - m_out) / K
            r[f"cutoff_{k}"] = best_upto(hi["fwd_excess"], lo["fwd_excess"], k)
        rows.append(r)
    mo = pd.DataFrame(rows).set_index("date"); mo.to_parquet(run_dir / "monthly.parquet")
    ann = (mo.mean() * 1200).round(2); sd = (mo.std(ddof=1) * 100).round(2)
    summ = {"months": int(len(mo)), "default_ann_pct": float(ann["default"]), "perfect_top8_ann_pct": float(ann["perfect_top8"]),
            "swaps": {k: {"best_ann_pct": float(ann[f"best_{k}"]), "random_ann_pct": float(ann[f"random_{k}"]), "cutoff_ann_pct": float(ann[f"cutoff_{k}"]),
                          "best_sd_pct_mo": float(sd[f"best_{k}"]), "share_months_best_gt_1pct_mo": float((mo[f"best_{k}"] > 0.01).mean())} for k in KS},
            # what a rule must achieve: fraction of the best-swap gain needed to add 1%/yr and 2%/yr
            "skill_needed": {k: {"share_of_best_for_1pct_yr": float(1 / ann[f"best_{k}"]), "share_of_best_for_2pct_yr": float(2 / ann[f"best_{k}"])} for k in KS},
            "run_ts": ts}
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2))
    tab = pd.DataFrame({"best possible (%/yr)": [ann[f"best_{k}"] for k in KS], "random swap (%/yr)": [ann[f"random_{k}"] for k in KS],
                        "best within ranks 6-8 ↔ 9-11 (%/yr)": [ann[f"cutoff_{k}"] for k in KS],
                        "months where best swap > 1%/mo": [f"{(mo[f'best_{k}'] > 0.01).mean():.0%}" for k in KS]}, index=[f"{k} swap" + ("s" if k > 1 else "") for k in KS])
    with pd.ExcelWriter(run_dir / "summary.xlsx") as xw:
        tab.to_excel(xw, sheet_name="ceiling"); mo.to_excel(xw, sheet_name="monthly")
    html = f"""<!DOCTYPE html><html lang="en" data-theme="light"><head><meta charset="utf-8"><title>One-swap ceiling</title>
<style>:root{{color-scheme:light}} body{{font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#222;background:#fff;line-height:1.5}}
table{{border-collapse:collapse}} th,td{{border:1px solid #ddd;padding:.3rem .6rem;text-align:right}} th:first-child,td:first-child{{text-align:left}} .note{{background:#f6f8fa;border-left:4px solid #1f4e79;padding:.6rem .9rem}}</style></head><body>
<h1>How much can replacing a few names add? The hindsight ceiling</h1>
<p>Default basket (pooled scores, hold while ranked ≤ 16), {len(mo)} months {mo.index.min().date()} → {mo.index.max().date()}. Default excess {ann['default']:.2f}% a year; the perfect top-8 would make {ann['perfect_top8']:.2f}%.</p>
{tab.to_html()}
<div class="note">A rule acting through one swap a month needs to capture about {100/ann['best_1']:.0f}% of the best possible swap's value to add 1% a year, and {200/ann['best_1']:.0f}% to add 2%. The random-swap row is what noise alone does: the non-holdings are {'worse' if ann['random_1'] < 0 else 'better'} than the holdings on average, so an uninformed swap {'costs' if ann['random_1'] < 0 else 'adds'} {abs(ann['random_1']):.2f}% a year.</div>
<p style="color:#666;font-size:.85rem">Files: <code>{run_dir}</code></p></body></html>"""
    (run_dir / "report.html").write_text(html)
    log.info("default %.2f | perfect top-8 %.2f | best 1/2/3 swaps %.2f / %.2f / %.2f | random %.2f / %.2f / %.2f | cutoff %.2f / %.2f / %.2f (%%/yr)",
             ann["default"], ann["perfect_top8"], *[ann[f"best_{k}"] for k in KS], *[ann[f"random_{k}"] for k in KS], *[ann[f"cutoff_{k}"] for k in KS])
    print(tab.to_string()); print(json.dumps(summ["skill_needed"], indent=1)); print(run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
