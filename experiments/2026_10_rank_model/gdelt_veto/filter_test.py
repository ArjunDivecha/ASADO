#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/gdelt_veto/filter_test.py
=============================================================================

INPUT FILES (from a completed veto_test.py run, default: the 2026-10-07 21:42 run):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/gdelt_veto_20261007_214235/holdings.parquet
    per (date, country): pooled default-model score, rank, held flag, fwd_excess
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/gdelt_veto_20261007_214235/shocks.parquet
    per (date, iso3, window, component): shock z (matched) and z_stale

OUTPUT FILES (in /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/gdelt_filter_<YYYYMMDD_HHMMSS>/):
- arms.parquet / arms.xlsx   one row per (score, window, threshold, arm): paired excess vs default, t, dropped/month, basket stats
- monthly.parquet            per arm and month: filtered basket excess, default excess, names dropped
- shuffle_null.parquet       500 shuffled-control paired t for the primary
- summary.json, report.html (light mode), charts.pdf, run.log

VERSION: 1.0
LAST UPDATED: 2026-10-07
AUTHOR: Claude for Arjun Divecha

DESCRIPTION:
Test 2 in gdelt_veto/PREREG.md (Arjun's rule): run the default model normally,
but each month make any country with news score <= -1 ineligible (news score =
minus the pre-rebalance composite GDELT shock). A held name with bad news is
dropped and the next-ranked eligible name fills the slot. Primary: paired monthly
excess of the filtered basket minus the unfiltered default, annualised, t.
Controls: stale news, 500 country-shuffled permutations. Gross; nothing retrained.

DEPENDENCIES: pandas, numpy, pyarrow, scipy, matplotlib, xlsxwriter (experiment .venv)

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model"
  .venv/bin/python gdelt_veto/filter_test.py [--source results/gdelt_veto_20261007_214235] [--n-shuffle 500]
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
from hysteresis import DEFAULT_BUFFER  # noqa: E402
from veto_test import BUCKET_ISO, tstat  # noqa: E402

RESULTS = EXP_DIR / "results"
K, M = 8, DEFAULT_BUFFER
PRIMARY = {"score": "composite", "window": 14, "thr": -1.0}
THRESHOLDS = (-0.5, -1.0, -1.5)
WINDOWS = (7, 14, 30)
SCORES = ("composite", "composite_share", "tone")   # news score = -shock for each
log = logging.getLogger("filter")


def baskets(hold: pd.DataFrame, eligible: dict | None) -> pd.DataFrame:
    """Default rule (k=K, m=M) with an optional per-month eligibility set. Returns per-month excess and drops."""
    rows, held = [], set()
    for dt, g in hold.sort_values(["date", "score"], ascending=[True, False]).groupby("date", sort=True):
        ranked = list(g["country"]); rank_of = {c: i + 1 for i, c in enumerate(ranked)}
        elig = eligible[dt] if eligible is not None else set(ranked)
        keep = [c for c in ranked if c in held and rank_of[c] <= M and c in elig]
        fill = [c for c in ranked if c not in held and c in elig][: max(0, K - len(keep))]
        new = set(keep[:K] + fill)
        dropped_bad = len([c for c in held if c in ranked and rank_of[c] <= M and c not in elig])  # would have survived but for news
        changed = len(new - held) if held else 0
        held = new
        sel = g[g["country"].isin(new)]
        rows.append({"date": dt, "excess": sel["fwd_excess"].mean(), "n_held": len(new), "changed": changed,
                     "dropped_for_news": dropped_bad, "n_ineligible": len(set(ranked) - elig)})
    return pd.DataFrame(rows).set_index("date")


def eligibility(hold: pd.DataFrame, sh: pd.DataFrame, score: str, window: int, thr: float, col: str = "z",
                perm: dict | None = None) -> dict:
    s = sh[(sh["window"] == window) & (sh["component"] == score)]
    out = {}
    for dt, g in hold.groupby("date"):
        z = s[s["date"] == dt].set_index("iso3")[col]
        if perm is not None:
            z = z.rename(index=perm[dt])
        news = {c: -z.get(BUCKET_ISO[c], np.nan) for c in g["country"]}    # news score = minus shock
        out[dt] = {c for c, v in news.items() if not (v <= thr)}           # NaN stays eligible
    return out


def arm_stats(f: pd.DataFrame, base: pd.DataFrame) -> dict:
    j = f.join(base[["excess"]].rename(columns={"excess": "base"}), how="inner")
    d = j["excess"] - j["base"]
    return {"months": int(len(j)), "paired_ann_pct": float(d.mean() * 1200), "paired_t": tstat(d),
            "filtered_ann_pct": float(j["excess"].mean() * 1200), "filtered_t": tstat(j["excess"]),
            "filtered_ir": float(j["excess"].mean() / j["excess"].std(ddof=1) * np.sqrt(12)),
            "default_ann_pct": float(j["base"].mean() * 1200), "default_t": tstat(j["base"]),
            "ineligible_per_month": float(j["n_ineligible"].mean()), "dropped_for_news_per_month": float(j["dropped_for_news"].mean()),
            "months_with_a_drop": int((j["dropped_for_news"] > 0).sum()), "names_changed_per_month": float(j["changed"].iloc[1:].mean()),
            "hit_rate_vs_default": float((d > 0).mean()), "months_differing": int((d.abs() > 1e-12).sum())}


def fig_b64(fig) -> str:
    b = io.BytesIO(); fig.savefig(b, format="png", dpi=130, bbox_inches="tight"); return base64.b64encode(b.getvalue()).decode()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, default=RESULTS / "gdelt_veto_20261007_214235")
    ap.add_argument("--n-shuffle", type=int, default=500)
    ap.add_argument("--seed", type=int, default=20261007)
    a = ap.parse_args()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S"); run_dir = RESULTS / f"gdelt_filter_{ts}"; run_dir.mkdir(parents=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(run_dir / "run.log")])
    t0 = time.time()
    hold = pd.read_parquet(a.source / "holdings.parquet"); sh = pd.read_parquet(a.source / "shocks.parquet")
    hold["date"] = pd.to_datetime(hold["date"]); sh["date"] = pd.to_datetime(sh["date"])
    # the unfiltered default, formed from the same scores (must equal the saved default run; checked in test 1)
    base = baskets(hold, None)
    log.info("default over %d months: %.2f%%/yr t %.2f", len(base), base["excess"].mean() * 1200, tstat(base["excess"]))

    arms, monthly = [], []
    for score in SCORES:
        if score not in set(sh["component"]):
            continue
        for w in WINDOWS:
            for thr in THRESHOLDS:
                for arm, col in (("matched", "z"), ("stale", "z_stale")):
                    f = baskets(hold, eligibility(hold, sh, score, w, thr, col))
                    r = arm_stats(f, base); r.update(score=score, window=w, thr=thr, arm=arm); arms.append(r)
                    monthly.append(f.assign(score=score, window=w, thr=thr, arm=arm, default_excess=base["excess"]).reset_index())
    arms = pd.DataFrame(arms); monthly = pd.concat(monthly, ignore_index=True)
    arms.to_parquet(run_dir / "arms.parquet", index=False); monthly.to_parquet(run_dir / "monthly.parquet", index=False)
    with pd.ExcelWriter(run_dir / "arms.xlsx") as xw:
        arms.to_excel(xw, sheet_name="arms", index=False); monthly.to_excel(xw, sheet_name="monthly", index=False)
    log.info("arms done (%d), %.0fs", len(arms), time.time() - t0)

    P = arms[(arms["score"] == PRIMARY["score"]) & (arms["window"] == PRIMARY["window"]) & (arms["thr"] == PRIMARY["thr"])]
    prim = P[P["arm"] == "matched"].iloc[0].to_dict(); stale = P[P["arm"] == "stale"].iloc[0].to_dict()
    prim_mo = monthly[(monthly["score"] == PRIMARY["score"]) & (monthly["window"] == PRIMARY["window"]) & (monthly["thr"] == PRIMARY["thr"]) & (monthly["arm"] == "matched")].set_index("date")
    stale_mo = monthly[(monthly["score"] == PRIMARY["score"]) & (monthly["window"] == PRIMARY["window"]) & (monthly["thr"] == PRIMARY["thr"]) & (monthly["arm"] == "stale")].set_index("date")

    # shuffled control: permute which country gets which news score, each month
    rng = np.random.default_rng(a.seed); iso = sorted(set(BUCKET_ISO.values())); dates = sorted(hold["date"].unique())
    null = []
    for i in range(a.n_shuffle):
        perm = {}
        for dt in dates:
            p = rng.permutation(len(iso))
            perm[dt] = {iso[p[j]]: iso[j] for j in range(len(iso))}   # rename shock index so holding iso[j] reads iso[p[j]]'s news
        f = baskets(hold, eligibility(hold, sh, PRIMARY["score"], PRIMARY["window"], PRIMARY["thr"], "z", perm))
        null.append(arm_stats(f, base)["paired_t"])
        if (i + 1) % 100 == 0:
            log.info("shuffle %d/%d, %.0fs", i + 1, a.n_shuffle, time.time() - t0)
    null = np.array(null); pd.DataFrame({"t": null}).to_parquet(run_dir / "shuffle_null.parquet", index=False)
    shuf = {"n": int(len(null)), "p05": float(np.percentile(null, 5)), "p50": float(np.percentile(null, 50)),
            "p95": float(np.percentile(null, 95)), "pct_rank_of_matched": float((null < prim["paired_t"]).mean() * 100)}

    d = (prim_mo["excess"] - prim_mo["default_excess"]) * 1200
    se = d.std(ddof=1) / np.sqrt(len(d)); ci = (float(d.mean() - 1.96 * se), float(d.mean() + 1.96 * se))
    c1 = prim["paired_t"] >= 2.0; c2 = prim["paired_t"] > shuf["p95"]; c3 = (stale["paired_t"] < 2.0) and (prim["paired_t"] > stale["paired_t"])
    if c1 and c2 and c3:
        verdict = "PASS"
    else:
        verdict = "INCONCLUSIVE" if (ci[1] > 1.0 and prim["paired_t"] > 0) else "FAIL"
    sentence = (f"Dropping countries with a news score of {PRIMARY['thr']:.0f} or worse changed the default basket in {prim['months_differing']} of {prim['months']} months "
                f"(about {prim['ineligible_per_month']:.1f} countries ineligible and {prim['dropped_for_news_per_month']:.2f} holdings dropped per month) and "
                f"{'added' if prim['paired_ann_pct'] >= 0 else 'cost'} {abs(prim['paired_ann_pct']):.2f}% a year against the unfiltered default (t {prim['paired_t']:+.2f}). "
                f"Stale news gave {stale['paired_ann_pct']:+.2f}% (t {stale['paired_t']:+.2f}); the shuffled null's 95th percentile is t {shuf['p95']:+.2f}. "
                f"The 95% interval on the gain is {ci[0]:+.1f}% to {ci[1]:+.1f}% a year.")
    summ = {"run_ts": ts, "source": str(a.source), "primary": prim, "stale": stale, "shuffle": shuf, "ci_ann_pct": ci,
            "decision": {"verdict": verdict, "c1": bool(c1), "c2": bool(c2), "c3": bool(c3), "sentence": sentence},
            "default_ann_pct": float(base["excess"].mean() * 1200), "elapsed_s": time.time() - t0}
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2, default=str))

    # charts
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    imgs = []
    with PdfPages(run_dir / "charts.pdf") as pdf:
        fig, ax = plt.subplots(figsize=(9, 4.2))
        ax.plot(prim_mo.index, (prim_mo["excess"] - prim_mo["default_excess"]).cumsum() * 100, color="#1f4e79", lw=2, label="filtered minus default (matched news)")
        ax.plot(stale_mo.index, (stale_mo["excess"] - stale_mo["default_excess"]).cumsum() * 100, color="#999", lw=1.6, ls="--", label="stale news control")
        ax.axhline(0, color="k", lw=.6); ax.set_ylabel("cumulative % points"); ax.legend(frameon=False); ax.grid(alpha=.25)
        ax.set_title("Cumulative gain from excluding countries with news score ≤ −1")
        pdf.savefig(fig); imgs.append(fig_b64(fig)); plt.close(fig)
        fig, ax = plt.subplots(figsize=(9, 4.2))
        ax.hist(null, bins=40, color="#c9d6e8", edgecolor="white"); ax.axvline(prim["paired_t"], color="#b22222", lw=2, label=f"matched t = {prim['paired_t']:+.2f}")
        ax.axvline(shuf["p95"], color="#1f4e79", ls=":", label="95th percentile of shuffled"); ax.legend(frameon=False)
        ax.set_title("Country-shuffled news: paired t under the null (500 permutations)"); ax.set_xlabel("paired t, filtered minus default")
        pdf.savefig(fig); imgs.append(fig_b64(fig)); plt.close(fig)
        m = arms[(arms["arm"] == "matched") & (arms["score"] == "composite")].pivot_table(index="thr", columns="window", values="paired_ann_pct")
        fig, ax = plt.subplots(figsize=(9, 4.2)); m.plot(kind="bar", ax=ax, color=["#9fb8d8", "#1f4e79", "#5a7fa8"], edgecolor="white")
        ax.axhline(0, color="k", lw=.6); ax.set_ylabel("% a year vs default"); ax.set_xlabel("news-score threshold"); ax.legend(title="window (days)", frameon=False)
        ax.set_title("Paired gain by threshold and window (composite news score)"); plt.xticks(rotation=0); ax.grid(axis="y", alpha=.25)
        pdf.savefig(fig); imgs.append(fig_b64(fig)); plt.close(fig)

    # report
    colour = {"PASS": "#1e7b34", "FAIL": "#b22222", "INCONCLUSIVE": "#b8860b"}[verdict]
    cols = ["score", "window", "thr", "arm", "months", "paired_ann_pct", "paired_t", "hit_rate_vs_default", "months_differing", "ineligible_per_month",
            "dropped_for_news_per_month", "filtered_ann_pct", "filtered_t", "filtered_ir", "names_changed_per_month"]
    fmt = {"paired_ann_pct": "{:+.2f}", "paired_t": "{:+.2f}", "hit_rate_vs_default": "{:.0%}", "ineligible_per_month": "{:.1f}", "dropped_for_news_per_month": "{:.2f}",
           "filtered_ann_pct": "{:.2f}", "filtered_t": "{:.2f}", "filtered_ir": "{:.2f}", "names_changed_per_month": "{:.2f}", "thr": "{:+.1f}"}
    def tbl(df):
        h = "".join(f"<th>{c}</th>" for c in cols); body = ""
        for _, r in df.iterrows():
            body += "<tr>" + "".join(f"<td>{fmt[c].format(r[c]) if c in fmt else r[c]}</td>" for c in cols) + "</tr>"
        return f"<table><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table>"
    html = f"""<!DOCTYPE html><html lang="en" data-theme="light"><head><meta charset="utf-8"><title>GDELT exclusion filter — results</title>
<style>:root{{color-scheme:light}} body{{font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:1050px;margin:2rem auto;padding:0 1rem;color:#222;background:#fff;line-height:1.5}}
h1{{font-size:1.5rem}} h2{{font-size:1.15rem;margin-top:2rem;border-bottom:1px solid #ddd}} table{{border-collapse:collapse;font-size:.84rem}} th,td{{border:1px solid #ddd;padding:.25rem .5rem;text-align:right}}
td:first-child,th:first-child,td:nth-child(4),th:nth-child(4){{text-align:left}} .verdict{{display:inline-block;padding:.3rem .8rem;border-radius:.4rem;color:#fff;font-weight:600;background:{colour}}}
.note{{background:#f6f8fa;border-left:4px solid #1f4e79;padding:.6rem .9rem;margin:.8rem 0}} img{{max-width:100%;border:1px solid #eee;margin:.4rem 0}} code{{background:#f3f3f3}}</style></head><body>
<h1>Run the default model, but exclude countries with significantly negative news</h1>
<p>Test 2 in <code>gdelt_veto/PREREG.md</code> (Arjun's rule), run {ts}. {prim['months']} months, {str(prim_mo.index.min().date())} to {str(prim_mo.index.max().date())}. Default basket over the same months: {summ['default_ann_pct']:.2f}% a year.</p>
<p><span class="verdict">{verdict}</span></p><div class="note"><b>Bottom line.</b> {sentence}</div>
<p>Decision checks: paired t ≥ 2: <b>{c1}</b>; above shuffled 95th percentile: <b>{c2}</b>; stronger than stale and stale not significant: <b>{c3}</b>.</p>
<img src="data:image/png;base64,{imgs[0]}"><img src="data:image/png;base64,{imgs[1]}">
<h2>All thresholds, windows and scores</h2><p>"paired_ann_pct" is the filtered basket's excess minus the unfiltered default's, per year. "tone" uses the tone component alone as the news score; "composite_share" uses the attention-share composite.</p>
<img src="data:image/png;base64,{imgs[2]}">{tbl(arms.sort_values(["score", "window", "thr", "arm"]))}
<p style="color:#666;font-size:.85rem">Files: <code>{run_dir}</code></p></body></html>"""
    (run_dir / "report.html").write_text(html)
    log.info("VERDICT %s | paired %+.2f%%/yr t %+.2f | stale t %+.2f | shuffled p95 %+.2f | %.0fs", verdict, prim["paired_ann_pct"], prim["paired_t"], stale["paired_t"], shuf["p95"], time.time() - t0)
    print(json.dumps({"run_dir": str(run_dir), "verdict": verdict, "sentence": sentence}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
