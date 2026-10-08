#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/toolkit/deep_dive.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/walk_*_<arm>_s{0,1000,2000}/predictions_oos.parquet
    out-of-sample nn_mse scores for the candidate arm (default: mt05 = multi-task, lambda 0.5) and the rolling-60 default
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v3_clean/feature_panel_v3_clean.parquet

OUTPUT FILES (in /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/deep_dive_<arm>_<YYYYMMDD_HHMMSS>/):
- monthly.parquet      per month: candidate and default basket excess (pooled and each draw), difference, names in common
- by_year.parquet      per year: both baskets' excess, difference, months ahead
- by_country.parquet   per country: holding frequency in each basket, contribution of the holding difference to the gap
- summary.json, deep_dive.xlsx, charts.pdf, report.html (light mode), run.log

VERSION: 1.0   LAST UPDATED: 2026-10-08   AUTHOR: Claude for Arjun Divecha

DESCRIPTION:
A close look at one candidate arm against the rolling-60 default, both as pooled
three-draw ensembles under the default basket rule (top 8, hold while ranked <= 16),
gross excess over the equal-weight 34, 2005-02 -> 2026-09. Where the gain comes from
in time (year by year, rolling three-year, with and without the 2008-09 crisis, how
concentrated in a few months), in names (which countries it holds more or less often
and what that contributed), and in robustness (each draw by period, overlap with the
default, drawdowns). Nothing is retrained.

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model"
  .venv/bin/python toolkit/deep_dive.py [--arm mt05] [--label "multi-task, lambda 0.5"]
=============================================================================
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

EXP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP_DIR))
from hysteresis import DEFAULT_BUFFER  # noqa: E402

RESULTS = EXP_DIR / "results"
PANEL = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v3_clean/feature_panel_v3_clean.parquet")
SEEDS = ("s0", "s1000", "s2000"); K, M = 8, DEFAULT_BUFFER
log = logging.getLogger("deep_dive")


def tstat(x):
    x = pd.Series(x).dropna(); return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 and x.std(ddof=1) > 0 else np.nan


def load(tag):
    runs = [r for r in sorted(RESULTS.glob(f"walk_*_{tag}")) if (r / "predictions_oos.parquet").exists()]
    d = pd.read_parquet(runs[-1] / "predictions_oos.parquet"); d = d[d["model"] == "nn_mse"]; d["date"] = pd.to_datetime(d["date"])
    return d.set_index(["date", "country"])["score"]


def holdings(score: pd.Series, panel: pd.DataFrame) -> pd.DataFrame:
    """Default rule; returns (date, country, held, fwd_excess) for every scored row."""
    d = score.rename("score").reset_index().merge(panel, on=["date", "country"]).dropna(subset=["score"])
    out, held = [], set()
    for dt, g in d.sort_values(["date", "score"], ascending=[True, False]).groupby("date", sort=True):
        ranked = list(g["country"]); rank_of = {c: i + 1 for i, c in enumerate(ranked)}
        keep = [c for c in ranked if c in held and rank_of[c] <= M]; fill = [c for c in ranked if c not in held][: max(0, K - len(keep))]
        held = set(keep[:K] + fill); out.append(g.assign(held=g["country"].isin(held)))
    return pd.concat(out, ignore_index=True)


def basket(h: pd.DataFrame) -> pd.Series:
    return h[h["held"]].groupby("date")["fwd_excess"].mean()


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--arm", default="mt05"); ap.add_argument("--label", default="multi-task, λ = 0.5"); ap.add_argument("--base", default="default")
    a = ap.parse_args()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S"); run_dir = RESULTS / f"deep_dive_{a.arm}_{ts}"; run_dir.mkdir(parents=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", handlers=[logging.StreamHandler(), logging.FileHandler(run_dir / "run.log")])
    panel = pd.read_parquet(PANEL, columns=["date", "country", "fwd_ret", "bench_ret", "fwd_excess"]); panel["date"] = pd.to_datetime(panel["date"])

    S = {}
    for arm in (a.arm, a.base):
        sc = pd.concat({s: load(f"{arm}_{s}") for s in SEEDS}, axis=1); sc["pooled"] = sc[list(SEEDS)].mean(axis=1); S[arm] = sc
    H = {(arm, m): holdings(S[arm][m], panel) for arm in S for m in list(SEEDS) + ["pooled"]}
    B = {k: basket(v) for k, v in H.items()}
    cand, base = B[(a.arm, "pooled")], B[(a.base, "pooled")]
    mo = pd.concat([cand.rename("cand"), base.rename("base")], axis=1).dropna(); mo["diff"] = mo["cand"] - mo["base"]
    for s in SEEDS:
        mo[f"cand_{s}"] = B[(a.arm, s)]; mo[f"base_{s}"] = B[(a.base, s)]
    hc, hb = H[(a.arm, "pooled")], H[(a.base, "pooled")]
    sets_c = hc[hc["held"]].groupby("date")["country"].apply(set); sets_b = hb[hb["held"]].groupby("date")["country"].apply(set)
    mo["names_in_common"] = [len(sets_c.get(d, set()) & sets_b.get(d, set())) for d in mo.index]
    chg = lambda sets: pd.Series([len(sets.iloc[i] - sets.iloc[i - 1]) if i else 0 for i in range(len(sets))], index=sets.index)
    mo["cand_changed"] = chg(sets_c); mo["base_changed"] = chg(sets_b)
    mo.to_parquet(run_dir / "monthly.parquet")

    # ---- time
    yr = mo.groupby(mo.index.year).agg(cand=("cand", lambda x: x.mean() * 1200), base=("base", lambda x: x.mean() * 1200), diff=("diff", lambda x: x.mean() * 1200),
                                        months=("diff", "size"), months_ahead=("diff", lambda x: int((x > 0).sum())), common=("names_in_common", "mean"))
    yr.index.name = "year"; yr.to_parquet(run_dir / "by_year.parquet")
    ex_gfc = mo[(mo.index < "2008-01-01") | (mo.index >= "2010-01-01")]
    periods = {"2005–07": ("2005", "2007"), "2008–09 (crisis)": ("2008", "2009"), "2010–14": ("2010", "2014"), "2015–19": ("2015", "2019"), "2020–22": ("2020", "2022"), "2023–26": ("2023", "2026")}
    per = []
    for lab, (s0, s1) in periods.items():
        x = mo.loc[s0:s1]
        row = {"period": lab, "months": len(x), "cand": x["cand"].mean() * 1200, "base": x["base"].mean() * 1200, "diff": x["diff"].mean() * 1200, "diff_t": tstat(x["diff"])}
        for s in SEEDS:
            row[f"diff_{s}"] = (x[f"cand_{s}"] - x[f"base_{s}"]).mean() * 1200
        per.append(row)
    per = pd.DataFrame(per)
    d_sorted = mo["diff"].sort_values(ascending=False); total = mo["diff"].sum()
    conc = {"top5_share": float(d_sorted.iloc[:5].sum() / total) if total else np.nan, "top10_share": float(d_sorted.iloc[:10].sum() / total) if total else np.nan,
            "diff_ann_ex_top5": float((mo["diff"].sum() - d_sorted.iloc[:5].sum()) / len(mo) * 1200), "best_months": [(str(i.date()), round(v * 100, 2)) for i, v in d_sorted.iloc[:8].items()],
            "worst_months": [(str(i.date()), round(v * 100, 2)) for i, v in d_sorted.iloc[-5:].items()]}

    # ---- names
    rows = []
    for c in sorted(hc["country"].unique()):
        x = hc[hc["country"] == c].set_index("date"); y = hb[hb["country"] == c].set_index("date")
        j = pd.concat([x["held"].rename("hc"), y["held"].rename("hb"), x["fwd_excess"].rename("r")], axis=1).dropna()
        # contribution of holding difference to the basket gap: (held_c - held_b) * r / 8, summed, annualised
        contrib = ((j["hc"].astype(int) - j["hb"].astype(int)) * j["r"] / K).sum() / len(mo) * 1200
        only_c = j[j["hc"] & ~j["hb"]]["r"]; only_b = j[~j["hc"] & j["hb"]]["r"]
        rows.append({"country": c, "held_pct_cand": float(j["hc"].mean() * 100), "held_pct_base": float(j["hb"].mean() * 100),
                     "held_pct_diff": float((j["hc"].mean() - j["hb"].mean()) * 100), "contribution_ann_pct": float(contrib),
                     "months_only_cand": int(len(only_c)), "mean_excess_when_only_cand_pct": float(only_c.mean() * 100) if len(only_c) else np.nan,
                     "months_only_base": int(len(only_b)), "mean_excess_when_only_base_pct": float(only_b.mean() * 100) if len(only_b) else np.nan})
    bc = pd.DataFrame(rows).sort_values("contribution_ann_pct", ascending=False); bc.to_parquet(run_dir / "by_country.parquet", index=False)

    # ---- risk
    def dd(x):
        w = (1 + x).cumprod(); return float((w / w.cummax() - 1).min() * 100)
    rel = lambda c, b: ((1 + c).cumprod() / (1 + b).cumprod())
    risk = {"corr_monthly_excess": float(mo["cand"].corr(mo["base"])), "te_ann_pct_vs_default": float(mo["diff"].std(ddof=1) * np.sqrt(12) * 100),
            "cand_ir": float(mo["cand"].mean() / mo["cand"].std(ddof=1) * np.sqrt(12)), "base_ir": float(mo["base"].mean() / mo["base"].std(ddof=1) * np.sqrt(12)),
            "cand_maxdd_excess_cum_pct": dd(mo["cand"]), "base_maxdd_excess_cum_pct": dd(mo["base"]),
            "cand_hit": float((mo["cand"] > 0).mean()), "base_hit": float((mo["base"] > 0).mean()), "months_cand_ahead": float((mo["diff"] > 0).mean()),
            "mean_names_in_common": float(mo["names_in_common"].mean()), "cand_names_changed": float(mo["cand_changed"].iloc[1:].mean()), "base_names_changed": float(mo["base_changed"].iloc[1:].mean())}
    summ = {"arm": a.arm, "label": a.label, "months": int(len(mo)), "first": str(mo.index.min().date()), "last": str(mo.index.max().date()),
            "cand_ann_pct": float(mo["cand"].mean() * 1200), "base_ann_pct": float(mo["base"].mean() * 1200), "diff_ann_pct": float(mo["diff"].mean() * 1200), "diff_t": tstat(mo["diff"]),
            "diff_ann_pct_ex_2008_09": float(ex_gfc["diff"].mean() * 1200), "diff_t_ex_2008_09": tstat(ex_gfc["diff"]),
            "per_draw_full": {s: float((mo[f"cand_{s}"] - mo[f"base_{s}"]).mean() * 1200) for s in SEEDS},
            "per_draw_ex_2008_09": {s: float((ex_gfc[f"cand_{s}"] - ex_gfc[f"base_{s}"]).mean() * 1200) for s in SEEDS},
            "concentration": conc, "risk": risk, "periods": per.to_dict("records"), "run_ts": ts}
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2, default=str))
    with pd.ExcelWriter(run_dir / "deep_dive.xlsx") as xw:
        mo.reset_index().to_excel(xw, sheet_name="monthly", index=False); yr.reset_index().to_excel(xw, sheet_name="by_year", index=False)
        per.to_excel(xw, sheet_name="by_period", index=False); bc.to_excel(xw, sheet_name="by_country", index=False)

    # ---- charts
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    imgs = []
    def b64(fig):
        b = io.BytesIO(); fig.savefig(b, format="png", dpi=130, bbox_inches="tight"); return base64.b64encode(b.getvalue()).decode()
    C, Bc = "#1f4e79", "#999999"
    with PdfPages(run_dir / "charts.pdf") as pdf:
        fig, ax = plt.subplots(figsize=(10, 4.4))
        ax.plot(mo.index, ((1 + mo["cand"]).cumprod() - 1) * 100, color=C, lw=2, label=a.label); ax.plot(mo.index, ((1 + mo["base"]).cumprod() - 1) * 100, color=Bc, lw=2, label="rolling-60 default")
        ax.axvspan(pd.Timestamp("2008-01-01"), pd.Timestamp("2009-12-31"), color="#f2e6e6", zorder=0); ax.set_ylabel("cumulative excess over equal weight, %")
        ax.set_title("Cumulative excess return, pooled three-draw ensembles (shaded: 2008–09)"); ax.legend(frameon=False); ax.grid(alpha=.25)
        pdf.savefig(fig); imgs.append(b64(fig)); plt.close(fig)
        fig, ax = plt.subplots(figsize=(10, 4.4)); r = rel(mo["cand"], mo["base"])
        ax.plot(r.index, (r - 1) * 100, color=C, lw=2, label="pooled")
        for s, col in zip(SEEDS, ["#9fb8d8", "#5a7fa8", "#2e8b57"]):
            rr = rel(mo[f"cand_{s}"], mo[f"base_{s}"]); ax.plot(rr.index, (rr - 1) * 100, color=col, lw=1, label=f"draw {s}")
        ax.axhline(0, color="k", lw=.5); ax.axvspan(pd.Timestamp("2008-01-01"), pd.Timestamp("2009-12-31"), color="#f2e6e6", zorder=0)
        ax.set_title("Candidate relative to the default (cumulative, %): pooled and each draw against its same-seed default"); ax.legend(frameon=False, ncol=4); ax.grid(alpha=.25)
        pdf.savefig(fig); imgs.append(b64(fig)); plt.close(fig)
        fig, ax = plt.subplots(figsize=(10, 4.4))
        ax.bar(yr.index, yr["diff"], color=[C if v >= 0 else "#b22222" for v in yr["diff"]]); ax.axhline(0, color="k", lw=.5)
        ax.set_title("Year by year: candidate minus default, % (annualised within the year)"); ax.set_ylabel("% points"); ax.grid(axis="y", alpha=.25)
        pdf.savefig(fig); imgs.append(b64(fig)); plt.close(fig)
        fig, ax = plt.subplots(figsize=(10, 4.4)); roll = mo["diff"].rolling(36).mean() * 1200
        ax.plot(roll.index, roll, color=C, lw=2); ax.axhline(0, color="k", lw=.5); ax.set_title("Rolling three-year gain over the default, % a year"); ax.grid(alpha=.25)
        pdf.savefig(fig); imgs.append(b64(fig)); plt.close(fig)
        top = pd.concat([bc.head(6), bc.tail(6)])
        fig, ax = plt.subplots(figsize=(10, 4.6)); ax.barh(top["country"], top["contribution_ann_pct"], color=[C if v >= 0 else "#b22222" for v in top["contribution_ann_pct"]])
        ax.axvline(0, color="k", lw=.5); ax.invert_yaxis(); ax.set_title("Which names made the gap: contribution of holding differences, % a year (top and bottom six)"); ax.grid(axis="x", alpha=.25)
        pdf.savefig(fig); imgs.append(b64(fig)); plt.close(fig)

    # ---- report
    def tbl(df, fmt, first_left=1):
        cols = list(df.columns)
        return "<table><thead><tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead><tbody>" + "".join(
            "<tr>" + "".join(f"<td>{('—' if (isinstance(r[c], float) and np.isnan(r[c])) else (fmt[c].format(r[c]) if c in fmt else r[c]))}</td>" for c in cols) + "</tr>" for _, r in df.iterrows()) + "</tbody></table>"
    f2 = "{:+.2f}"
    per_t = per.rename(columns={"cand": a.arm, "base": "default", "diff": "gap", "diff_t": "gap t", "diff_s0": "gap s0", "diff_s1000": "gap s1000", "diff_s2000": "gap s2000"})
    yr_t = yr.reset_index().rename(columns={"cand": a.arm, "base": "default", "diff": "gap", "common": "names in common"})
    bc_t = bc[["country", "held_pct_cand", "held_pct_base", "held_pct_diff", "contribution_ann_pct", "months_only_cand", "mean_excess_when_only_cand_pct", "months_only_base", "mean_excess_when_only_base_pct"]]
    rk = risk
    html = f"""<!DOCTYPE html><html lang="en" data-theme="light"><head><meta charset="utf-8"><title>Multi-task net — a closer look</title>
<style>:root{{color-scheme:light}} body{{font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#222;background:#fff;line-height:1.55}}
h1{{font-size:1.55rem}} h2{{font-size:1.15rem;margin-top:2.2rem;border-bottom:1px solid #ddd;padding-bottom:.2rem}} table{{border-collapse:collapse;font-size:.84rem;margin:.6rem 0}} th,td{{border:1px solid #ddd;padding:.25rem .5rem;text-align:right}} td:first-child,th:first-child{{text-align:left}}
.note{{background:#f6f8fa;border-left:4px solid #1f4e79;padding:.7rem 1rem;margin:.8rem 0}} img{{max-width:100%;border:1px solid #eee;margin:.4rem 0}} code{{background:#f3f3f3;padding:0 .2rem}}</style></head><body>
<h1>The multi-task net ({a.label}) against the default — a closer look</h1>
<p>Pooled three-draw ensembles, default basket rule (top 8, hold while ranked ≤ 16), gross excess over the equal-weight 34, {summ['first']} → {summ['last']} ({summ['months']} months). Nothing retrained; same out-of-sample scores as the B2b comparison.</p>
<div class="note"><b>Headline.</b> {summ['cand_ann_pct']:.2f}% a year against {summ['base_ann_pct']:.2f}%: a gap of {summ['diff_ann_pct']:+.2f}% (t {summ['diff_t']:+.2f}). Leaving out 2008–09 the gap is {summ['diff_ann_pct_ex_2008_09']:+.2f}% (t {summ['diff_t_ex_2008_09']:+.2f}).
Per draw against its same-seed default: {', '.join(f"{k} {v:+.2f}" for k, v in summ['per_draw_full'].items())} (full); {', '.join(f"{k} {v:+.2f}" for k, v in summ['per_draw_ex_2008_09'].items())} (excluding 2008–09).</div>

<h2>When the gain arrived</h2>
<img src="data:image/png;base64,{imgs[0]}"><img src="data:image/png;base64,{imgs[1]}">
{tbl(per_t, {c: f2 for c in per_t.columns if c not in ('period', 'months')})}
<img src="data:image/png;base64,{imgs[2]}"><img src="data:image/png;base64,{imgs[3]}">
<p><b>How concentrated:</b> the five best months for the candidate relative to the default account for {conc['top5_share']:.0%} of the whole cumulative gap, the ten best for {conc['top10_share']:.0%}. Without its five best months the gap would be {conc['diff_ann_ex_top5']:+.2f}% a year.
Best months (gap, %): {', '.join(f'{d} {v:+.2f}' for d, v in conc['best_months'])}. Worst: {', '.join(f'{d} {v:+.2f}' for d, v in conc['worst_months'])}.</p>
{tbl(yr_t, {a.arm: f2, 'default': f2, 'gap': f2, 'names in common': '{:.1f}'})}

<h2>Which names</h2>
<p>How often each basket held each country, and what the difference contributed to the gap (the return of a name held by one basket and not the other, divided by eight, summed and annualised). On average the two baskets share {rk['mean_names_in_common']:.1f} of their 8 names.</p>
<img src="data:image/png;base64,{imgs[4]}">
{tbl(bc_t, {'held_pct_cand': '{:.0f}', 'held_pct_base': '{:.0f}', 'held_pct_diff': '{:+.0f}', 'contribution_ann_pct': '{:+.2f}', 'mean_excess_when_only_cand_pct': '{:+.2f}', 'mean_excess_when_only_base_pct': '{:+.2f}'})}

<h2>Risk and behaviour</h2>
<table><tbody>
<tr><td>Correlation of monthly excess with the default</td><td>{rk['corr_monthly_excess']:.2f}</td></tr>
<tr><td>Tracking error against the default, % a year</td><td>{rk['te_ann_pct_vs_default']:.2f}</td></tr>
<tr><td>Information ratio: candidate / default</td><td>{rk['cand_ir']:.2f} / {rk['base_ir']:.2f}</td></tr>
<tr><td>Worst drawdown of cumulative excess, %: candidate / default</td><td>{rk['cand_maxdd_excess_cum_pct']:.1f} / {rk['base_maxdd_excess_cum_pct']:.1f}</td></tr>
<tr><td>Months with positive excess: candidate / default</td><td>{rk['cand_hit']:.0%} / {rk['base_hit']:.0%}</td></tr>
<tr><td>Months the candidate beat the default</td><td>{rk['months_cand_ahead']:.0%}</td></tr>
<tr><td>Names changed per month: candidate / default</td><td>{rk['cand_names_changed']:.2f} / {rk['base_names_changed']:.2f}</td></tr>
</tbody></table>
<p style="color:#666;font-size:.85rem">Files: <code>{run_dir}</code></p></body></html>"""
    (run_dir / "report.html").write_text(html)
    print(json.dumps({k: summ[k] for k in ("cand_ann_pct", "base_ann_pct", "diff_ann_pct", "diff_t", "diff_ann_pct_ex_2008_09", "diff_t_ex_2008_09", "per_draw_full", "per_draw_ex_2008_09")}, indent=1, default=str))
    print(per.round(2).to_string(index=False)); print(json.dumps(conc, indent=1)); print(json.dumps(risk, indent=1))
    print(bc[["country", "held_pct_cand", "held_pct_base", "contribution_ann_pct", "months_only_cand", "mean_excess_when_only_cand_pct", "months_only_base", "mean_excess_when_only_base_pct"]].round(2).to_string(index=False))
    print(yr.round(2).to_string()); print(run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
