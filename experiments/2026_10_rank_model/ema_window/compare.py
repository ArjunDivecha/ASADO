#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/ema_window/compare.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/walk_*_<arm>_s{0,1000,2000}/predictions_oos.parquet
    arms: default (rolling 60, the comparator), exp (expanding, equal weights), ema24/36/60/120 (expanding,
    recency-weighted). Model nn_mse. Each a 30-net ensemble per fold; three independent seed draws per arm.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v3_clean/feature_panel_v3_clean.parquet

OUTPUT FILES (in /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/ema_compare_<YYYYMMDD_HHMMSS>/):
- arms.parquet / arms.xlsx   per arm and member (pooled, each draw): excess %/yr, t, IR, turnover, paired vs pooled rolling-60, by decade
- monthly.parquet            per arm/member/month: basket excess
- summary.json, charts.pdf, report.html (light mode), run.log

VERSION: 1.1 (generic --arms/--since)   LAST UPDATED: 2026-10-08   AUTHOR: Claude for Arjun Divecha

DESCRIPTION:
Pre-registered comparison (ema_window/PREREG.md): rolling five-year training window versus
all-history with exponential recency weights. Baskets under the default rule (top 8, hold while
ranked <= 16) from the saved out-of-sample scores; nothing is retrained. Decision: the default
changes only if an arm beats rolling-60 by paired t >= 2 on the pooled comparison and leads in
each of the three draws.

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model"
  .venv/bin/python ema_window/compare.py
=============================================================================
"""
from __future__ import annotations
import base64, io, json, logging, sys, time
from datetime import datetime
from pathlib import Path
import numpy as np, pandas as pd

EXP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP_DIR))
from hysteresis import DEFAULT_BUFFER, build_baskets, stats  # noqa: E402

RESULTS = EXP_DIR / "results"
PANEL = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v3_clean/feature_panel_v3_clean.parquet")
ARMS = {"rolling60": "default", "exp": "exp", "ema24": "ema24", "ema36": "ema36", "ema60": "ema60", "ema120": "ema120"}
SEEDS = ("s0", "s1000", "s2000"); K, M = 8, DEFAULT_BUFFER
log = logging.getLogger("compare")


def tstat(x):
    x = pd.Series(x).dropna(); return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 else np.nan


def load(tag: str) -> pd.DataFrame | None:
    runs = sorted(RESULTS.glob(f"walk_*_{tag}"))
    runs = [r for r in runs if (r / "predictions_oos.parquet").exists()]
    if not runs:
        return None
    d = pd.read_parquet(runs[-1] / "predictions_oos.parquet"); d = d[d["model"] == "nn_mse"][["date", "country", "score"]]
    d["date"] = pd.to_datetime(d["date"]); return d.set_index(["date", "country"])["score"]


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", default=None, help="comma list name=tag, e.g. rolling60=default,heads=heads ; default: the EMA grid")
    ap.add_argument("--since", default=None, help="restrict the comparison to months >= this date (YYYY-MM-DD)")
    ap.add_argument("--prefix", default="ema_compare")
    a = ap.parse_args()
    global ARMS
    if a.arms:
        ARMS = dict(kv.split("=") for kv in a.arms.split(","))
    ts = datetime.now().strftime("%Y%m%d_%H%M%S"); run_dir = RESULTS / f"{a.prefix}_{ts}"; run_dir.mkdir(parents=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", handlers=[logging.StreamHandler(), logging.FileHandler(run_dir / "run.log")])
    t0 = time.time()
    panel = pd.read_parquet(PANEL, columns=["date", "country", "fwd_ret", "bench_ret", "fwd_excess"]); panel["date"] = pd.to_datetime(panel["date"])
    monthly, rows = [], []
    series = {}
    for arm, tag in ARMS.items():
        draws = {s: load(f"{tag}_{s}") for s in SEEDS}; draws = {s: v for s, v in draws.items() if v is not None}
        if not draws:
            log.warning("arm %s: no runs found", arm); continue
        sc = pd.concat(draws, axis=1); sc["pooled"] = sc.mean(axis=1)
        for member in list(draws) + ["pooled"]:
            d = sc[member].rename("score").reset_index().merge(panel, on=["date", "country"]).dropna(subset=["score"])
            if a.since:
                d = d[d["date"] >= pd.Timestamp(a.since)]
            mo = build_baskets(d, K, M); st = stats(mo, K)
            series[(arm, member)] = mo.set_index("date")["excess"]
            rows.append({"arm": arm, "member": member, **st}); monthly.append(mo.assign(arm=arm, member=member))
        log.info("arm %s: %d draws, pooled %.2f%%/yr t %.2f", arm, len(draws), rows[-1]["excess_ann_pct"], rows[-1]["excess_t"])
    arms = pd.DataFrame(rows); monthly = pd.concat(monthly, ignore_index=True)
    base = series[("rolling60", "pooled")]
    # paired vs pooled rolling-60 (and per-draw vs the same-seed rolling draw)
    paired = []
    for (arm, member), s in series.items():
        comp = base if member == "pooled" else series.get(("rolling60", member), base)
        j = pd.concat([s.rename("a"), comp.rename("b")], axis=1).dropna(); d = j["a"] - j["b"]
        paired.append({"arm": arm, "member": member, "paired_ann_pct": float(d.mean() * 1200), "paired_t": tstat(d), "paired_hit": float((d > 0).mean()),
                       "corr_with_rolling": float(j["a"].corr(j["b"])), "months": int(len(j))})
    arms = arms.merge(pd.DataFrame(paired), on=["arm", "member"])
    arms.to_parquet(run_dir / "arms.parquet", index=False); monthly.to_parquet(run_dir / "monthly.parquet", index=False)
    with pd.ExcelWriter(run_dir / "arms.xlsx") as xw:
        arms.to_excel(xw, sheet_name="arms", index=False); monthly.to_excel(xw, sheet_name="monthly", index=False)

    # decision per arm
    dec = {}
    for arm in ARMS:
        if arm == "rolling60" or arm not in set(arms["arm"]): continue
        P = arms[(arms["arm"] == arm) & (arms["member"] == "pooled")].iloc[0]
        per_draw = arms[(arms["arm"] == arm) & (arms["member"] != "pooled")]
        dec[arm] = {"pooled_paired_ann_pct": float(P["paired_ann_pct"]), "pooled_paired_t": float(P["paired_t"]),
                    "draws_ahead": int((per_draw["paired_ann_pct"] > 0).sum()), "n_draws": int(len(per_draw)),
                    "passes": bool(P["paired_t"] >= 2.0 and (per_draw["paired_ann_pct"] > 0).all())}
    winners = [a for a, v in dec.items() if v["passes"]]
    best = max(dec, key=lambda a: dec[a]["pooled_paired_t"])
    verdict = f"CHANGE DEFAULT to {', '.join(winners)}" if winners else "KEEP rolling-60"
    summ = {"run_ts": ts, "verdict": verdict, "best_arm": best, "decisions": dec, "elapsed_s": time.time() - t0,
            "rolling60_pooled": arms[(arms["arm"] == "rolling60") & (arms["member"] == "pooled")].iloc[0].to_dict()}
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2, default=str))

    # charts
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    palette = ["#222222", "#b22222", "#1f4e79", "#2e8b57", "#b8860b", "#999999", "#6a3d9a"]
    cols = {arm: palette[i % len(palette)] for i, arm in enumerate(ARMS)}
    imgs = []
    def b64(fig):
        b = io.BytesIO(); fig.savefig(b, format="png", dpi=130, bbox_inches="tight"); return base64.b64encode(b.getvalue()).decode()
    with PdfPages(run_dir / "charts.pdf") as pdf:
        fig, ax = plt.subplots(figsize=(9.5, 4.6))
        for arm in ARMS:
            if (arm, "pooled") in series:
                s = series[(arm, "pooled")]; ax.plot(s.index, s.cumsum() * 100, color=cols[arm], lw=2.2 if arm == "rolling60" else 1.5, label=arm)
        ax.axhline(0, color="k", lw=.5); ax.set_title("Cumulative out-of-sample excess over equal weight, pooled 3 draws, default basket rule"); ax.set_ylabel("cumulative % points"); ax.legend(frameon=False, ncol=3); ax.grid(alpha=.25)
        pdf.savefig(fig); imgs.append(b64(fig)); plt.close(fig)
        fig, ax = plt.subplots(figsize=(9.5, 4.6))
        for arm in ARMS:
            if arm == "rolling60" or (arm, "pooled") not in series: continue
            d = (series[(arm, "pooled")] - base).dropna(); ax.plot(d.index, d.cumsum() * 100, color=cols[arm], lw=1.6, label=f"{arm} minus rolling60")
        ax.axhline(0, color="k", lw=.5); ax.set_title("Paired: each arm minus the rolling-60 default (pooled), cumulative % points"); ax.legend(frameon=False, ncol=3); ax.grid(alpha=.25)
        pdf.savefig(fig); imgs.append(b64(fig)); plt.close(fig)
        fig, ax = plt.subplots(figsize=(9.5, 4.6))
        pv = arms.pivot_table(index="arm", columns="member", values="excess_ann_pct").reindex(list(ARMS))
        pv[[c for c in pv.columns if c != "pooled"]].plot(kind="bar", ax=ax, color=["#9fb8d8", "#5a7fa8", "#1f4e79"], edgecolor="white")
        ax.scatter(range(len(pv)), pv["pooled"], color="#b22222", zorder=5, label="pooled"); ax.set_ylabel("% a year excess"); ax.set_title("Each seed draw and the pooled ensemble, by arm"); ax.legend(frameon=False); plt.xticks(rotation=0); ax.grid(axis="y", alpha=.25)
        pdf.savefig(fig); imgs.append(b64(fig)); plt.close(fig)
        fig, ax = plt.subplots(figsize=(9.5, 4.6))
        dec_cols = ["excess_ann_pct_2005_09", "excess_ann_pct_2010_19", "excess_ann_pct_2020_26"]
        pv = arms[arms["member"] == "pooled"].set_index("arm")[dec_cols].reindex(list(ARMS)); pv.columns = ["2005-09", "2010-19", "2020-26"]
        pv.plot(kind="bar", ax=ax, color=["#9fb8d8", "#5a7fa8", "#1f4e79"], edgecolor="white"); ax.set_ylabel("% a year excess"); ax.set_title("Pooled excess by period"); plt.xticks(rotation=0); ax.grid(axis="y", alpha=.25); ax.legend(frameon=False)
        pdf.savefig(fig); imgs.append(b64(fig)); plt.close(fig)

    show = ["arm", "member", "excess_ann_pct", "excess_t", "info_ratio", "hit_rate", "names_changed_per_month", "max_rel_drawdown_pct", "paired_ann_pct", "paired_t", "paired_hit", "corr_with_rolling", "excess_ann_pct_2005_09", "excess_ann_pct_2010_19", "excess_ann_pct_2020_26"]
    fmt = {c: "{:+.2f}" for c in show if c not in ("arm", "member", "hit_rate", "paired_hit")} | {"hit_rate": "{:.0%}", "paired_hit": "{:.0%}"}
    order = {a: i for i, a in enumerate(ARMS)}; tab = arms.assign(o=arms["arm"].map(order), p=(arms["member"] != "pooled")).sort_values(["o", "p", "member"])
    def tbl(df):
        return "<table><thead><tr>" + "".join(f"<th>{c.replace('excess_ann_pct_', '')}</th>" for c in show) + "</tr></thead><tbody>" + "".join(
            "<tr" + (' style="font-weight:600;background:#f6f8fa"' if r["member"] == "pooled" else "") + ">" + "".join(f"<td>{fmt[c].format(r[c]) if c in fmt else r[c]}</td>" for c in show) + "</tr>" for _, r in df.iterrows()) + "</tbody></table>"
    dec_rows = "".join(f"<li><b>{a}</b>: pooled {v['pooled_paired_ann_pct']:+.2f}% a year vs rolling-60, paired t {v['pooled_paired_t']:+.2f}; ahead in {v['draws_ahead']} of {v['n_draws']} draws → {'PASS' if v['passes'] else 'no'}</li>" for a, v in dec.items())
    html = f"""<!DOCTYPE html><html lang="en" data-theme="light"><head><meta charset="utf-8"><title>Rolling vs recency-weighted — results</title>
<style>:root{{color-scheme:light}} body{{font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:1150px;margin:2rem auto;padding:0 1rem;color:#222;background:#fff;line-height:1.5}}
h1{{font-size:1.5rem}} h2{{font-size:1.15rem;margin-top:2rem;border-bottom:1px solid #ddd}} table{{border-collapse:collapse;font-size:.82rem}} th,td{{border:1px solid #ddd;padding:.25rem .45rem;text-align:right}} td:nth-child(-n+2),th:nth-child(-n+2){{text-align:left}}
.verdict{{display:inline-block;padding:.3rem .8rem;border-radius:.4rem;color:#fff;font-weight:600;background:{'#1e7b34' if winners else '#1f4e79'}}} .note{{background:#f6f8fa;border-left:4px solid #1f4e79;padding:.6rem .9rem;margin:.8rem 0}} img{{max-width:100%;border:1px solid #eee;margin:.4rem 0}}</style></head><body>
<h1>Rolling five-year window versus all-history with recency weights</h1>
<p>Pre-registered in <code>ema_window/PREREG.md</code>; run {ts}. Out-of-sample 2005-02 → 2026-09, default basket rule (top 8, hold while ranked ≤ 16), gross, versus the equal-weight 34. Each arm: 30 nets per fold, three independent seed draws (s0, s1000, s2000) and their pooled ensemble.</p>
<p><span class="verdict">{verdict}</span></p>
<div class="note"><b>Decision rule:</b> change only if an arm beats rolling-60 by paired t ≥ 2 on the pooled comparison and leads in all three draws.<ul>{dec_rows}</ul></div>
<img src="data:image/png;base64,{imgs[0]}"><img src="data:image/png;base64,{imgs[1]}"><img src="data:image/png;base64,{imgs[2]}"><img src="data:image/png;base64,{imgs[3]}">
<h2>All arms and members</h2><p>"paired" columns compare each row with the rolling-60 default (pooled rows against the pooled default; each draw against the rolling draw with the same seed). Period columns are % a year.</p>{tbl(tab)}
<p style="color:#666;font-size:.85rem">Files: <code>{run_dir}</code></p></body></html>"""
    (run_dir / "report.html").write_text(html)
    log.info("VERDICT %s | best arm %s | %.0fs", verdict, best, time.time() - t0)
    print(json.dumps({"run_dir": str(run_dir), "verdict": verdict, "decisions": dec}, indent=1))
    pd.set_option("display.width", 250); print(arms[arms["member"] == "pooled"][["arm", "excess_ann_pct", "excess_t", "info_ratio", "names_changed_per_month", "max_rel_drawdown_pct", "paired_ann_pct", "paired_t", "excess_ann_pct_2005_09", "excess_ann_pct_2010_19", "excess_ann_pct_2020_26"]].round(2).to_string(index=False))
    print(arms[arms["member"] != "pooled"].pivot_table(index="arm", columns="member", values="excess_ann_pct").round(2).reindex(list(ARMS)).to_string())
    return 0


if __name__ == "__main__":
    sys.exit(main())
