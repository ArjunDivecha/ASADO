#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/gdelt_veto/boost_test.py
=============================================================================

INPUT FILES (from the completed veto_test.py run):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/gdelt_veto_20261007_214235/holdings.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/gdelt_veto_20261007_214235/shocks.parquet

OUTPUT FILES (in /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/gdelt_boost_<YYYYMMDD_HHMMSS>/):
- arms.parquet / arms.xlsx, monthly.parquet, shuffle_null.parquet, summary.json, charts.pdf, report.html, run.log

VERSION: 1.0   LAST UPDATED: 2026-10-07   AUTHOR: Claude for Arjun Divecha

DESCRIPTION:
Test 3 in gdelt_veto/PREREG.md (Arjun's rule): run the default model normally,
but move any country with news score >= +1 (good news) up B places in the
model's ranking before the buffer rule. Primary B = 4. Mirror "contrarian" arm
boosts news score <= -1 instead (secondary). Paired against the unboosted
default; stale-news and 500 country-shuffled controls. Gross; nothing retrained.

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model"
  .venv/bin/python gdelt_veto/boost_test.py [--n-shuffle 500]
=============================================================================
"""
from __future__ import annotations
import argparse, base64, io, json, logging, sys, time
from datetime import datetime
from pathlib import Path
import numpy as np, pandas as pd

EXP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP_DIR)); sys.path.insert(0, str(EXP_DIR / "gdelt_veto"))
from hysteresis import DEFAULT_BUFFER  # noqa: E402
from veto_test import BUCKET_ISO, tstat  # noqa: E402

RESULTS = EXP_DIR / "results"; K, M = 8, DEFAULT_BUFFER
PRIMARY = {"score": "composite", "window": 14, "thr": 1.0, "boost": 4, "side": "good"}
THRESHOLDS = (0.5, 1.0, 1.5); BOOSTS = (2, 4, 8); WINDOWS = (7, 14, 30); SCORES = ("composite", "composite_share", "tone")
log = logging.getLogger("boost")


def news_scores(hold, sh, score, window, col="z", perm=None) -> dict:
    s = sh[(sh["window"] == window) & (sh["component"] == score)]; out = {}
    for dt, g in hold.groupby("date"):
        z = s[s["date"] == dt].set_index("iso3")[col]
        if perm is not None:
            z = z.rename(index=perm[dt])
        out[dt] = {c: -z.get(BUCKET_ISO[c], np.nan) for c in g["country"]}   # news score = minus shock
    return out


def baskets(hold, news: dict | None, thr: float, boost: int, side: str) -> pd.DataFrame:
    """Default rule on an adjusted ranking: qualifying countries move up `boost` places."""
    rows, held = [], set()
    for dt, g in hold.sort_values(["date", "score"], ascending=[True, False]).groupby("date", sort=True):
        g = g.copy(); g["rank0"] = np.arange(1, len(g) + 1)
        if news is not None:
            ns = g["country"].map(news[dt]).astype(float)
            q = (ns >= thr) if side == "good" else (ns <= -thr)
            g["adj"] = g["rank0"] - boost * q.fillna(False).astype(int)
        else:
            q = pd.Series(False, index=g.index); g["adj"] = g["rank0"]
        g = g.sort_values(["adj", "rank0"]); ranked = list(g["country"]); rank_of = {c: i + 1 for i, c in enumerate(ranked)}
        keep = [c for c in ranked if c in held and rank_of[c] <= M]
        fill = [c for c in ranked if c not in held][: max(0, K - len(keep))]
        new = set(keep[:K] + fill); changed = len(new - held) if held else 0; held = new
        sel = g[g["country"].isin(new)]
        rows.append({"date": dt, "excess": sel["fwd_excess"].mean(), "changed": changed, "n_boosted": int(q.sum()),
                     "boosted_held": int(sel["country"].isin(g.loc[q.values, "country"]).sum())})
    return pd.DataFrame(rows).set_index("date")


def arm_stats(f, base) -> dict:
    j = f.join(base[["excess"]].rename(columns={"excess": "base"}), how="inner"); d = j["excess"] - j["base"]
    return {"months": int(len(j)), "paired_ann_pct": float(d.mean() * 1200), "paired_t": tstat(d),
            "boosted_ann_pct": float(j["excess"].mean() * 1200), "boosted_t": tstat(j["excess"]),
            "boosted_ir": float(j["excess"].mean() / j["excess"].std(ddof=1) * np.sqrt(12)), "default_ann_pct": float(j["base"].mean() * 1200),
            "boosted_per_month": float(j["n_boosted"].mean()), "boosted_held_per_month": float(j["boosted_held"].mean()),
            "names_changed_per_month": float(j["changed"].iloc[1:].mean()), "hit_rate_vs_default": float((d > 0).mean()),
            "months_differing": int((d.abs() > 1e-12).sum())}


def fig_b64(fig):
    b = io.BytesIO(); fig.savefig(b, format="png", dpi=130, bbox_inches="tight"); return base64.b64encode(b.getvalue()).decode()


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--source", type=Path, default=RESULTS / "gdelt_veto_20261007_214235")
    ap.add_argument("--n-shuffle", type=int, default=500); ap.add_argument("--seed", type=int, default=20261007); a = ap.parse_args()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S"); run_dir = RESULTS / f"gdelt_boost_{ts}"; run_dir.mkdir(parents=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", handlers=[logging.StreamHandler(), logging.FileHandler(run_dir / "run.log")])
    t0 = time.time()
    hold = pd.read_parquet(a.source / "holdings.parquet"); sh = pd.read_parquet(a.source / "shocks.parquet")
    hold["date"] = pd.to_datetime(hold["date"]); sh["date"] = pd.to_datetime(sh["date"])
    base = baskets(hold, None, 0, 0, "good")
    log.info("default over %d months: %.2f%%/yr", len(base), base["excess"].mean() * 1200)

    arms, monthly = [], []
    for score in SCORES:
        if score not in set(sh["component"]): continue
        for w in WINDOWS:
            for arm, col in (("matched", "z"), ("stale", "z_stale")):
                ns = news_scores(hold, sh, score, w, col)
                for thr in THRESHOLDS:
                    for b in BOOSTS:
                        for side in ("good", "contrarian"):
                            if side == "contrarian" and (arm == "stale" or score != "composite"): continue
                            f = baskets(hold, ns, thr, b, side); r = arm_stats(f, base)
                            r.update(score=score, window=w, thr=thr, boost=b, side=side, arm=arm); arms.append(r)
                            monthly.append(f.assign(score=score, window=w, thr=thr, boost=b, side=side, arm=arm, default_excess=base["excess"]).reset_index())
    arms = pd.DataFrame(arms); monthly = pd.concat(monthly, ignore_index=True)
    arms.to_parquet(run_dir / "arms.parquet", index=False); monthly.to_parquet(run_dir / "monthly.parquet", index=False)
    with pd.ExcelWriter(run_dir / "arms.xlsx") as xw:
        arms.to_excel(xw, sheet_name="arms", index=False); monthly.to_excel(xw, sheet_name="monthly", index=False)
    log.info("arms done (%d), %.0fs", len(arms), time.time() - t0)

    sel = lambda df, arm, side: df[(df["score"] == PRIMARY["score"]) & (df["window"] == PRIMARY["window"]) & (df["thr"] == PRIMARY["thr"]) & (df["boost"] == PRIMARY["boost"]) & (df["side"] == side) & (df["arm"] == arm)]
    prim = sel(arms, "matched", "good").iloc[0].to_dict(); stale = sel(arms, "stale", "good").iloc[0].to_dict(); mirror = sel(arms, "matched", "contrarian").iloc[0].to_dict()
    prim_mo = sel(monthly, "matched", "good").set_index("date"); stale_mo = sel(monthly, "stale", "good").set_index("date"); mir_mo = sel(monthly, "matched", "contrarian").set_index("date")

    rng = np.random.default_rng(a.seed); iso = sorted(set(BUCKET_ISO.values())); dates = sorted(hold["date"].unique()); null = []
    for i in range(a.n_shuffle):
        perm = {}
        for dt in dates:
            p = rng.permutation(len(iso)); perm[dt] = {iso[p[j]]: iso[j] for j in range(len(iso))}
        f = baskets(hold, news_scores(hold, sh, PRIMARY["score"], PRIMARY["window"], "z", perm), PRIMARY["thr"], PRIMARY["boost"], "good")
        null.append(arm_stats(f, base)["paired_t"])
        if (i + 1) % 100 == 0: log.info("shuffle %d/%d, %.0fs", i + 1, a.n_shuffle, time.time() - t0)
    null = np.array(null); pd.DataFrame({"t": null}).to_parquet(run_dir / "shuffle_null.parquet", index=False)
    shuf = {"n": int(len(null)), "p05": float(np.percentile(null, 5)), "p50": float(np.percentile(null, 50)), "p95": float(np.percentile(null, 95)), "pct_rank_of_matched": float((null < prim["paired_t"]).mean() * 100)}

    d = (prim_mo["excess"] - prim_mo["default_excess"]) * 1200; se = d.std(ddof=1) / np.sqrt(len(d)); ci = (float(d.mean() - 1.96 * se), float(d.mean() + 1.96 * se))
    c1 = prim["paired_t"] >= 2.0; c2 = prim["paired_t"] > shuf["p95"]; c3 = (stale["paired_t"] < 2.0) and (prim["paired_t"] > stale["paired_t"])
    verdict = "PASS" if (c1 and c2 and c3) else ("INCONCLUSIVE" if (ci[1] > 1.0 and prim["paired_t"] > 0) else "FAIL")
    sentence = (f"Moving countries with a news score of +{PRIMARY['thr']:.0f} or better up {PRIMARY['boost']} places changed the basket in {prim['months_differing']} of {prim['months']} months "
                f"(about {prim['boosted_per_month']:.1f} countries boosted and {prim['boosted_held_per_month']:.2f} boosted names held per month) and "
                f"{'added' if prim['paired_ann_pct'] >= 0 else 'cost'} {abs(prim['paired_ann_pct']):.2f}% a year against the default (t {prim['paired_t']:+.2f}). "
                f"Stale news gave {stale['paired_ann_pct']:+.2f}% (t {stale['paired_t']:+.2f}); the shuffled null's 95th percentile is t {shuf['p95']:+.2f}. "
                f"The mirror (boost bad-news names) gave {mirror['paired_ann_pct']:+.2f}% a year (t {mirror['paired_t']:+.2f}). "
                f"95% interval on the primary gain: {ci[0]:+.1f}% to {ci[1]:+.1f}% a year.")
    summ = {"run_ts": ts, "primary": prim, "stale": stale, "mirror_contrarian": mirror, "shuffle": shuf, "ci_ann_pct": ci,
            "decision": {"verdict": verdict, "c1": bool(c1), "c2": bool(c2), "c3": bool(c3), "sentence": sentence}, "default_ann_pct": float(base["excess"].mean() * 1200), "elapsed_s": time.time() - t0}
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2, default=str))

    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    imgs = []
    with PdfPages(run_dir / "charts.pdf") as pdf:
        fig, ax = plt.subplots(figsize=(9, 4.2))
        ax.plot(prim_mo.index, (prim_mo["excess"] - prim_mo["default_excess"]).cumsum() * 100, color="#1f4e79", lw=2, label="boost good news (primary)")
        ax.plot(mir_mo.index, (mir_mo["excess"] - mir_mo["default_excess"]).cumsum() * 100, color="#b22222", lw=1.6, label="boost bad news (mirror, contrarian)")
        ax.plot(stale_mo.index, (stale_mo["excess"] - stale_mo["default_excess"]).cumsum() * 100, color="#999", lw=1.4, ls="--", label="stale news control (good)")
        ax.axhline(0, color="k", lw=.6); ax.set_ylabel("cumulative % points vs default"); ax.legend(frameon=False); ax.grid(alpha=.25); ax.set_title("Cumulative gain from the rank boost")
        pdf.savefig(fig); imgs.append(fig_b64(fig)); plt.close(fig)
        fig, ax = plt.subplots(figsize=(9, 4.2)); ax.hist(null, bins=40, color="#c9d6e8", edgecolor="white")
        ax.axvline(prim["paired_t"], color="#b22222", lw=2, label=f"matched t = {prim['paired_t']:+.2f}"); ax.axvline(shuf["p95"], color="#1f4e79", ls=":", label="95th pct of shuffled"); ax.legend(frameon=False)
        ax.set_title("Country-shuffled news: paired t under the null (500 permutations)"); pdf.savefig(fig); imgs.append(fig_b64(fig)); plt.close(fig)
        m = arms[(arms["arm"] == "matched") & (arms["score"] == "composite") & (arms["window"] == 14)].pivot_table(index=["side", "thr"], columns="boost", values="paired_ann_pct")
        fig, ax = plt.subplots(figsize=(9, 4.6)); m.plot(kind="bar", ax=ax, color=["#9fb8d8", "#1f4e79", "#5a7fa8"], edgecolor="white"); ax.axhline(0, color="k", lw=.6)
        ax.set_ylabel("% a year vs default"); ax.legend(title="boost (places)", frameon=False); ax.set_title("Paired gain by side, threshold and boost (composite, 14 days)"); plt.xticks(rotation=0); ax.grid(axis="y", alpha=.25)
        pdf.savefig(fig); imgs.append(fig_b64(fig)); plt.close(fig)

    colour = {"PASS": "#1e7b34", "FAIL": "#b22222", "INCONCLUSIVE": "#b8860b"}[verdict]
    cols = ["side", "score", "window", "thr", "boost", "arm", "months", "paired_ann_pct", "paired_t", "hit_rate_vs_default", "months_differing", "boosted_per_month", "boosted_held_per_month", "boosted_ann_pct", "boosted_ir", "names_changed_per_month"]
    fmt = {"paired_ann_pct": "{:+.2f}", "paired_t": "{:+.2f}", "hit_rate_vs_default": "{:.0%}", "boosted_per_month": "{:.1f}", "boosted_held_per_month": "{:.2f}", "boosted_ann_pct": "{:.2f}", "boosted_ir": "{:.2f}", "names_changed_per_month": "{:.2f}", "thr": "{:+.1f}"}
    def tbl(df):
        return "<table><thead><tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead><tbody>" + "".join(
            "<tr>" + "".join(f"<td>{fmt[c].format(r[c]) if c in fmt else r[c]}</td>" for c in cols) + "</tr>" for _, r in df.iterrows()) + "</tbody></table>"
    html = f"""<!DOCTYPE html><html lang="en" data-theme="light"><head><meta charset="utf-8"><title>GDELT rank boost — results</title>
<style>:root{{color-scheme:light}} body{{font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#222;background:#fff;line-height:1.5}}
h1{{font-size:1.5rem}} h2{{font-size:1.15rem;margin-top:2rem;border-bottom:1px solid #ddd}} table{{border-collapse:collapse;font-size:.82rem}} th,td{{border:1px solid #ddd;padding:.25rem .45rem;text-align:right}}
td:nth-child(-n+2),th:nth-child(-n+2),td:nth-child(6),th:nth-child(6){{text-align:left}} .verdict{{display:inline-block;padding:.3rem .8rem;border-radius:.4rem;color:#fff;font-weight:600;background:{colour}}}
.note{{background:#f6f8fa;border-left:4px solid #1f4e79;padding:.6rem .9rem;margin:.8rem 0}} img{{max-width:100%;border:1px solid #eee;margin:.4rem 0}} code{{background:#f3f3f3}}</style></head><body>
<h1>Run the default model, but boost countries with significantly positive news</h1>
<p>Test 3 in <code>gdelt_veto/PREREG.md</code> (Arjun's rule), run {ts}. {prim['months']} months, {prim_mo.index.min().date()} to {prim_mo.index.max().date()}. Default over the same months: {summ['default_ann_pct']:.2f}% a year.</p>
<p><span class="verdict">{verdict}</span></p><div class="note"><b>Bottom line.</b> {sentence}</div>
<p>Decision checks: paired t ≥ 2: <b>{c1}</b>; above shuffled 95th percentile: <b>{c2}</b>; stronger than stale and stale not significant: <b>{c3}</b>.</p>
<img src="data:image/png;base64,{imgs[0]}"><img src="data:image/png;base64,{imgs[1]}">
<h2>All sides, thresholds, boosts, windows and scores</h2><p>"good" boosts news score ≥ +thr (Arjun's rule); "contrarian" boosts news score ≤ −thr (mirror, secondary). "paired_ann_pct" is the boosted basket's excess minus the default's, per year.</p>
<img src="data:image/png;base64,{imgs[2]}">{tbl(arms.sort_values(["side", "score", "window", "thr", "boost", "arm"]))}
<p style="color:#666;font-size:.85rem">Files: <code>{run_dir}</code></p></body></html>"""
    (run_dir / "report.html").write_text(html)
    log.info("VERDICT %s | primary %+.2f%%/yr t %+.2f | stale t %+.2f | mirror %+.2f%%/yr t %+.2f | shuffled p95 %+.2f | %.0fs", verdict, prim["paired_ann_pct"], prim["paired_t"], stale["paired_t"], mirror["paired_ann_pct"], mirror["paired_t"], shuf["p95"], time.time() - t0)
    print(json.dumps({"run_dir": str(run_dir), "verdict": verdict, "sentence": sentence}, indent=1)); return 0


if __name__ == "__main__":
    sys.exit(main())
