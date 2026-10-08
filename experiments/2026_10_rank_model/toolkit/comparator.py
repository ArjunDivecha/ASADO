#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/toolkit/comparator.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/walk_*_default_s*/predictions_oos.parquet
    the three default draws' out-of-sample nn_mse scores (pooled, and each draw)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/heads_<ts>/forecasts_oos.parquet + summary.json
    stage-1 out-of-sample head forecasts; only the heads listed as survivors are used
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v3_clean/feature_panel_v3_clean.parquet

OUTPUT FILES (in /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/comparator_<YYYYMMDD_HHMMSS>/):
- arms.parquet / arms.xlsx   per (member, variant, rule): excess %/yr, t, IR, turnover, paired vs the default (A), paired t
- monthly.parquet            per member/variant/rule/month: basket excess and the default's
- shuffle_null.parquet       200 shuffled-heads paired t for the primary
- summary.json, charts.pdf, report.html (light mode), run.log

VERSION: 1.0   LAST UPDATED: 2026-10-08   AUTHOR: Claude for Arjun Divecha

DESCRIPTION:
Rung B stage 2 (toolkit/PREREG.md). A rolling-60 ridge (alpha by month-grouped CV on
the top-8 objective, as in the default's ridge) takes the default model's out-of-sample
score plus the surviving heads' out-of-sample forecasts (each standardised within month)
and predicts next-month excess. Rules: full re-rank under the default basket rule
(primary); one- and two-swap overrides of the default basket (secondary). Variants:
full (score + heads), heads-only, score-only (control). Paired against the default
basket over the comparator's own out-of-sample months (from 2010-02), pooled and per
draw; 200 shuffled-heads permutations give the null for the primary. Gross; nothing in
the default is retrained.

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model"
  .venv/bin/python toolkit/comparator.py --heads results/heads_20261008_001954 [--n-shuffle 200]
=============================================================================
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

EXP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP_DIR)); sys.path.insert(0, str(EXP_DIR / "gdelt_veto"))
from hysteresis import DEFAULT_BUFFER, build_baskets, stats  # noqa: E402
from train_floor import fit_ridge  # noqa: E402
from veto_test import PANEL, load_scores, tstat  # noqa: E402

RESULTS = EXP_DIR / "results"; K, M = 8, DEFAULT_BUFFER
WINDOW, FIRST_TRAIN, STEP = 60, 60, 12
log = logging.getLogger("comparator")


def zs(s: pd.Series) -> pd.Series:
    sd = s.std(ddof=0); return (s - s.mean()) / sd if sd > 0 else s * 0


def walk_forward_ridge(d: pd.DataFrame, cols: list[str], seed: int = 0) -> np.ndarray:
    """d sorted by date; rolling-60 month ridge on cols -> fwd_excess; returns OOS score per row (NaN before first fold)."""
    months = pd.DatetimeIndex(np.sort(d["date"].unique())); mi = {m: i for i, m in enumerate(months)}
    m = d["date"].map(mi).to_numpy(); X = d[cols].to_numpy(float); y = d["fwd_excess"].to_numpy(float)
    out = np.full(len(d), np.nan); t = FIRST_TRAIN; fi = 0
    while t < len(months):
        tr = (m >= max(0, t - WINDOW)) & (m < t); ev = (m >= t) & (m < min(t + STEP, len(months)))
        if tr.sum() > 100 and ev.any():
            _, s_ev, _ = fit_ridge(X[tr], y[tr], m[tr], X[ev], K, seed + fi); out[ev] = s_ev
        t += STEP; fi += 1
    return out


def swap_baskets(d_default: pd.DataFrame, comp_score: pd.Series, k: int) -> pd.DataFrame:
    """Default basket (with hysteresis, from the default score) then up to k swaps where the comparator disagrees most.
    Overrides last one month; the hysteresis state follows the default basket, not the overridden one."""
    rows, held = [], set()
    d = d_default.assign(comp=comp_score.to_numpy())
    for dt, g in d.sort_values(["date", "score"], ascending=[True, False]).groupby("date", sort=True):
        ranked = list(g["country"]); rank_of = {c: i + 1 for i, c in enumerate(ranked)}
        keep = [c for c in ranked if c in held and rank_of[c] <= M]; fill = [c for c in ranked if c not in held][: max(0, K - len(keep))]
        new = set(keep[:K] + fill); held = new
        if g["comp"].isna().all():
            continue
        H = g[g["country"].isin(new)].sort_values("comp"); N = g[~g["country"].isin(new)].sort_values("comp", ascending=False)
        basket = set(new); swaps = 0
        for i in range(min(k, len(H), len(N))):
            if N["comp"].iloc[i] > H["comp"].iloc[i]:
                basket.discard(H["country"].iloc[i]); basket.add(N["country"].iloc[i]); swaps += 1
        sel = g[g["country"].isin(basket)]
        rows.append({"date": dt, "excess": sel["fwd_excess"].mean(), "swaps": swaps})
    return pd.DataFrame(rows).set_index("date")


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--heads", type=Path, required=True); ap.add_argument("--n-shuffle", type=int, default=200); ap.add_argument("--seed", type=int, default=20261008)
    a = ap.parse_args()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S"); run_dir = RESULTS / f"comparator_{ts}"; run_dir.mkdir(parents=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", handlers=[logging.StreamHandler(), logging.FileHandler(run_dir / "run.log")])
    t0 = time.time()
    hs = json.load(open(a.heads / "summary.json")); survivors = hs["survivors"]
    log.info("surviving heads from %s: %s", a.heads.name, survivors)
    fc = pd.read_parquet(a.heads / "forecasts_oos.parquet"); fc = fc[fc["head"].isin(survivors)]; fc["date"] = pd.to_datetime(fc["date"])
    F = fc.pivot_table(index=["date", "country"], columns="head", values="forecast"); F.columns = [f"h_{c}" for c in F.columns]
    panel = pd.read_parquet(PANEL, columns=["date", "country", "fwd_ret", "bench_ret", "fwd_excess"]); panel["date"] = pd.to_datetime(panel["date"])
    sc, draws = load_scores()
    hcols = list(F.columns)

    arms, monthly, series = [], [], {}
    for member in draws + ["pooled"]:
        d = sc[["date", "country", member]].rename(columns={member: "score"}).merge(panel, on=["date", "country"]).dropna(subset=["score"])
        d = d.merge(F.reset_index(), on=["date", "country"], how="left").sort_values(["date", "country"]).reset_index(drop=True)
        d[hcols] = d[hcols].fillna(0.0)
        # standardise inputs within month (so the ridge is not at the mercy of fold-to-fold score scale)
        for c in ["score"] + hcols:
            d[f"z_{c}"] = d.groupby("date")[c].transform(zs)
        base = build_baskets(d, K, M).set_index("date")["excess"]; series[(member, "default", "default")] = base
        variants = {"full": ["z_score"] + [f"z_{c}" for c in hcols], "heads_only": [f"z_{c}" for c in hcols], "score_only": ["z_score"]}
        comp_scores = {}
        for var, cols in variants.items():
            d["comp"] = walk_forward_ridge(d, cols, seed=0); comp_scores[var] = d["comp"].copy()
            dd = d.dropna(subset=["comp"])
            rr = build_baskets(dd.rename(columns={"score": "score_default", "comp": "score"}), K, M).set_index("date")["excess"]
            series[(member, var, "rerank")] = rr
            for k in (1, 2):
                series[(member, var, f"swap{k}")] = swap_baskets(d, d["comp"], k)["excess"]
        log.info("%s done, %.0fs", member, time.time() - t0)
        if member == "pooled":
            d_pooled, comp_pooled = d.copy(), comp_scores

    # stats, paired against the same member's default over the comparator's OOS months
    for (member, var, rule), s in series.items():
        if var == "default":
            continue
        base = series[(member, "default", "default")]; j = pd.concat([s.rename("b"), base.rename("a")], axis=1).dropna(); dlt = j["b"] - j["a"]
        mo = pd.DataFrame({"date": j.index, "excess": j["b"].to_numpy(), "basket_ret": np.nan, "bench_ret": np.nan, "names_changed": 0})
        row = {"member": member, "variant": var, "rule": rule, "months": int(len(j)), "excess_ann_pct": float(j["b"].mean() * 1200), "excess_t": tstat(j["b"]),
               "info_ratio": float(j["b"].mean() / j["b"].std(ddof=1) * np.sqrt(12)), "default_ann_pct": float(j["a"].mean() * 1200), "default_t": tstat(j["a"]),
               "paired_ann_pct": float(dlt.mean() * 1200), "paired_t": tstat(dlt), "paired_hit": float((dlt > 0).mean()), "corr_with_default": float(j["a"].corr(j["b"]))}
        arms.append(row); monthly.append(pd.DataFrame({"member": member, "variant": var, "rule": rule, "date": j.index, "excess": j["b"].to_numpy(), "default_excess": j["a"].to_numpy()}))
    arms = pd.DataFrame(arms); monthly = pd.concat(monthly, ignore_index=True)

    # shuffled-heads null for the primary (pooled, full, rerank): permute each head across countries within month
    rng = np.random.default_rng(a.seed); null = []
    base = series[("pooled", "default", "default")]
    for i in range(a.n_shuffle):
        d = d_pooled.copy()
        for c in hcols:
            d[f"z_{c}"] = d.groupby("date")[f"z_{c}"].transform(lambda x: x.to_numpy()[rng.permutation(len(x))])
        d["comp"] = walk_forward_ridge(d, ["z_score"] + [f"z_{c}" for c in hcols], seed=0); dd = d.dropna(subset=["comp"])
        rr = build_baskets(dd.rename(columns={"score": "score_default", "comp": "score"}), K, M).set_index("date")["excess"]
        j = pd.concat([rr.rename("b"), base.rename("a")], axis=1).dropna(); null.append(tstat(j["b"] - j["a"]))
        if (i + 1) % 25 == 0:
            log.info("shuffle %d/%d, %.0fs", i + 1, a.n_shuffle, time.time() - t0)
    null = np.array(null); pd.DataFrame({"t": null}).to_parquet(run_dir / "shuffle_null.parquet", index=False)
    shuf = {"n": int(len(null)), "p05": float(np.percentile(null, 5)), "p50": float(np.percentile(null, 50)), "p95": float(np.percentile(null, 95))}

    P = arms[(arms["member"] == "pooled") & (arms["variant"] == "full") & (arms["rule"] == "rerank")].iloc[0]
    per_draw = arms[(arms["member"] != "pooled") & (arms["variant"] == "full") & (arms["rule"] == "rerank")]
    c1 = P["paired_t"] >= 2.0; c2 = bool((per_draw["paired_ann_pct"] > 0).all()); c3 = P["paired_t"] > shuf["p95"]
    mo_p = monthly[(monthly["member"] == "pooled") & (monthly["variant"] == "full") & (monthly["rule"] == "rerank")]
    dlt = (mo_p["excess"] - mo_p["default_excess"]) * 1200; se = dlt.std(ddof=1) / np.sqrt(len(dlt)); ci = (float(dlt.mean() - 1.96 * se), float(dlt.mean() + 1.96 * se))
    verdict = "B REPLACES A" if (c1 and c2 and c3) else ("INCONCLUSIVE" if (ci[1] > 1.0 and P["paired_t"] > 0) else "A STAYS")
    arms.to_parquet(run_dir / "arms.parquet", index=False); monthly.to_parquet(run_dir / "monthly.parquet", index=False)
    with pd.ExcelWriter(run_dir / "arms.xlsx") as xw:
        arms.to_excel(xw, sheet_name="arms", index=False); monthly.to_excel(xw, sheet_name="monthly", index=False)
    sentence = (f"Re-ranking with the default score plus {len(survivors)} fundamental-forecast heads made {P['excess_ann_pct']:.2f}% a year against the default's {P['default_ann_pct']:.2f}% "
                f"over the same {P['months']} months ({P['paired_ann_pct']:+.2f}% a year, paired t {P['paired_t']:+.2f}; ahead in {int((per_draw['paired_ann_pct'] > 0).sum())} of 3 draws; "
                f"shuffled-heads 95th percentile t {shuf['p95']:+.2f}). 95% interval on the gain: {ci[0]:+.1f}% to {ci[1]:+.1f}% a year.")
    summ = {"run_ts": ts, "heads_run": str(a.heads), "survivors": survivors, "verdict": verdict, "sentence": sentence, "checks": {"paired_t_ge_2": bool(c1), "all_draws_ahead": c2, "above_shuffled_p95": bool(c3)},
            "primary": P.to_dict(), "ci_ann_pct": ci, "shuffle": shuf, "elapsed_s": time.time() - t0}
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2, default=str))

    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    imgs = []
    def b64(fig):
        b = io.BytesIO(); fig.savefig(b, format="png", dpi=130, bbox_inches="tight"); return base64.b64encode(b.getvalue()).decode()
    with PdfPages(run_dir / "charts.pdf") as pdf:
        fig, ax = plt.subplots(figsize=(9.5, 4.6))
        for (var, rule), col in {("full", "rerank"): "#1f4e79", ("heads_only", "rerank"): "#2e8b57", ("score_only", "rerank"): "#999999", ("full", "swap1"): "#b22222", ("full", "swap2"): "#b8860b"}.items():
            m = monthly[(monthly["member"] == "pooled") & (monthly["variant"] == var) & (monthly["rule"] == rule)]
            ax.plot(m["date"], (m["excess"] - m["default_excess"]).cumsum() * 100, color=col, lw=1.6, label=f"{var} / {rule}")
        ax.axhline(0, color="k", lw=.5); ax.set_title("Each comparator minus the default (A), cumulative % points, pooled scores"); ax.legend(frameon=False, ncol=2); ax.grid(alpha=.25)
        pdf.savefig(fig); imgs.append(b64(fig)); plt.close(fig)
        fig, ax = plt.subplots(figsize=(9.5, 4.2)); ax.hist(null, bins=30, color="#c9d6e8", edgecolor="white"); ax.axvline(P["paired_t"], color="#b22222", lw=2, label=f"matched t {P['paired_t']:+.2f}"); ax.axvline(shuf["p95"], color="#1f4e79", ls=":", label="95th pct of shuffled heads")
        ax.set_title("Shuffled-heads null for the primary (paired t)"); ax.legend(frameon=False); pdf.savefig(fig); imgs.append(b64(fig)); plt.close(fig)
    cols = ["member", "variant", "rule", "months", "excess_ann_pct", "excess_t", "info_ratio", "default_ann_pct", "paired_ann_pct", "paired_t", "paired_hit", "corr_with_default"]
    fmt = {c: "{:+.2f}" for c in cols if c not in ("member", "variant", "rule", "months", "paired_hit")} | {"paired_hit": "{:.0%}"}
    order = {"pooled": 0}; tab = arms.assign(o=arms["member"].map(lambda m: order.get(m, 1))).sort_values(["o", "member", "variant", "rule"])
    tbl = "<table><thead><tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead><tbody>" + "".join(
        "<tr" + (' style="font-weight:600;background:#f6f8fa"' if (r["member"] == "pooled" and r["variant"] == "full" and r["rule"] == "rerank") else "") + ">" + "".join(f"<td>{fmt[c].format(r[c]) if c in fmt else r[c]}</td>" for c in cols) + "</tr>" for _, r in tab.iterrows()) + "</tbody></table>"
    colour = {"B REPLACES A": "#1e7b34", "A STAYS": "#1f4e79", "INCONCLUSIVE": "#b8860b"}[verdict]
    html = f"""<!DOCTYPE html><html lang="en" data-theme="light"><head><meta charset="utf-8"><title>Rung B stage 2 — comparator</title>
<style>:root{{color-scheme:light}} body{{font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#222;background:#fff;line-height:1.5}} table{{border-collapse:collapse;font-size:.83rem}} th,td{{border:1px solid #ddd;padding:.25rem .45rem;text-align:right}} td:nth-child(-n+3),th:nth-child(-n+3){{text-align:left}}
.verdict{{display:inline-block;padding:.3rem .8rem;border-radius:.4rem;color:#fff;font-weight:600;background:{colour}}} .note{{background:#f6f8fa;border-left:4px solid #1f4e79;padding:.6rem .9rem}} img{{max-width:100%;border:1px solid #eee;margin:.4rem 0}}</style></head><body>
<h1>Rung B, stage 2: does the toolkit improve the basket?</h1>
<p>Pre-registered in <code>toolkit/PREREG.md</code>; run {ts}. Surviving heads: {', '.join(survivors)}. Rolling-60 ridge on the default score plus head forecasts, out of sample from {mo_p['date'].min().date()} to {mo_p['date'].max().date()}. Primary: full re-rank under the default basket rule, pooled scores, paired against the default over the same months.</p>
<p><span class="verdict">{verdict}</span></p><div class="note"><b>Bottom line.</b> {sentence}</div>
<p>Decision checks — paired t ≥ 2: <b>{bool(c1)}</b>; ahead in all three draws: <b>{c2}</b>; above the shuffled-heads 95th percentile: <b>{bool(c3)}</b>.</p>
<img src="data:image/png;base64,{imgs[0]}"><img src="data:image/png;base64,{imgs[1]}">
<h2>All members, variants and rules</h2><p>"full" = default score + heads; "heads_only" = heads alone; "score_only" = the default score through the same ridge (control). "rerank" forms the basket from the comparator's score; "swap1"/"swap2" override at most one or two names of the default basket.</p>{tbl}
<p style="color:#666;font-size:.85rem">Files: <code>{run_dir}</code></p></body></html>"""
    (run_dir / "report.html").write_text(html)
    log.info("VERDICT %s | %s | %.0fs", verdict, sentence, time.time() - t0)
    pd.set_option("display.width", 220); print(verdict); print(sentence)
    print(arms[arms["member"] == "pooled"][["variant", "rule", "months", "excess_ann_pct", "excess_t", "info_ratio", "paired_ann_pct", "paired_t", "paired_hit"]].round(2).to_string(index=False))
    print(arms[(arms["variant"] == "full") & (arms["rule"] == "rerank")][["member", "excess_ann_pct", "default_ann_pct", "paired_ann_pct", "paired_t"]].round(2).to_string(index=False)); print(run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
