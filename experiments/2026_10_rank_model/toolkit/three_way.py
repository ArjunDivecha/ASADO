#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/toolkit/three_way.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/walk_*_default_s{0,1000,2000}/predictions_oos.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/walk_*_mt05_s{0,1000,2000}/predictions_oos.parquet
    out-of-sample nn_mse scores: the rolling-60 default and the multi-task net (lambda 0.5)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v3_clean/feature_panel_v3_clean.parquet
    fwd_ret (country return over the next month), bench_ret (equal-weight 34), fwd_excess

OUTPUT FILES (in /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/three_way_<YYYYMMDD_HHMMSS>/):
- monthly.parquet          per month: basket return, benchmark return, excess, names changed, for each portfolio
- three_way.xlsx           summary, windows (Full/5y/3y/1y), periods, by-year, monthly
- report.html (light mode), charts.pdf, summary.json, run.log

VERSION: 1.1 (--second / --no-blend)   LAST UPDATED: 2026-10-08   AUTHOR: Claude for Arjun Divecha

DESCRIPTION:
Side-by-side statistics for three portfolios, each a pooled three-draw ensemble
under the default basket rule (top 8 equal weight, hold while ranked <= 16), gross,
monthly rebalance, 2005-02 -> 2026-09:
  1. the rolling-60 default;
  2. the multi-task net, lambda 0.5;
  3. a 50/50 combination: the two pooled scores each standardised within month,
     averaged, then the same basket rule. (Descriptive, requested by Arjun;
     not a pre-registered test.)
Plus the equal-weight benchmark for reference. Reports annualised return, annualised
standard deviation, maximum drawdown and turnover, on both total-return and
excess-over-equal-weight bases, over Full / 5y / 3y / 1y and calendar periods.

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model"
  .venv/bin/python toolkit/three_way.py
=============================================================================
"""
from __future__ import annotations

import base64
import io
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

EXP_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(EXP_DIR))
from hysteresis import DEFAULT_BUFFER, build_baskets  # noqa: E402

RESULTS = EXP_DIR / "results"
PANEL = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v3_clean/feature_panel_v3_clean.parquet")
SEEDS = ("s0", "s1000", "s2000"); K, M = 8, DEFAULT_BUFFER
NAMES = {"default": "Default (rolling 60)", "mt05": "Multi-task λ 0.5", "blend": "50/50 combination", "ew": "Equal-weight 34"}
PERIODS = {"2005–07": ("2005", "2007"), "2008–09": ("2008", "2009"), "2010–14": ("2010", "2014"), "2015–19": ("2015", "2019"),
           "2020–22": ("2020", "2022"), "2023–26": ("2023", "2026")}


def pooled(tag: str) -> pd.Series:
    fr = []
    for s in SEEDS:
        run = [r for r in sorted(RESULTS.glob(f"walk_*_{tag}_{s}")) if (r / "predictions_oos.parquet").exists()][-1]
        d = pd.read_parquet(run / "predictions_oos.parquet"); d = d[d["model"] == "nn_mse"]; d["date"] = pd.to_datetime(d["date"])
        fr.append(d.set_index(["date", "country"])["score"].rename(s))
    return pd.concat(fr, axis=1).mean(axis=1)


def zs(x: pd.Series) -> pd.Series:
    return (x - x.mean()) / x.std(ddof=0)


def ann_ret(r: pd.Series) -> float:          # geometric, % a year
    return float(((1 + r).prod() ** (12 / len(r)) - 1) * 100) if len(r) else np.nan


def ann_sd(r: pd.Series) -> float:
    return float(r.std(ddof=1) * np.sqrt(12) * 100) if len(r) > 2 else np.nan


def max_dd(r: pd.Series) -> float:
    w = (1 + r).cumprod(); w = pd.concat([pd.Series([1.0]), w.reset_index(drop=True)]); return float((w / w.cummax() - 1).min() * 100)


def rel_dd(b: pd.Series, e: pd.Series) -> float:
    rel = (1 + b).cumprod() / (1 + e).cumprod(); rel = pd.concat([pd.Series([1.0]), rel.reset_index(drop=True)]); return float((rel / rel.cummax() - 1).min() * 100)


def block(mo: dict, sl) -> pd.DataFrame:
    rows = []
    for k in ("default", "mt05", "blend", "ew"):
        x = mo[k].loc[sl] if k != "ew" else mo["default"].loc[sl]
        r = x["bench_ret"] if k == "ew" else x["basket_ret"]; e = x["bench_ret"]
        row = {"portfolio": NAMES[k], "months": len(x), "ann_return_pct": ann_ret(r), "ann_sd_pct": ann_sd(r), "max_drawdown_pct": max_dd(r),
               "excess_ann_pct": np.nan if k == "ew" else float((r - e).mean() * 1200), "excess_sd_pct": np.nan if k == "ew" else ann_sd(r - e),
               "max_rel_drawdown_pct": np.nan if k == "ew" else rel_dd(r, e),
               "turnover_oneway_pct_yr": np.nan if k == "ew" else float(x["names_changed"].iloc[1:].mean() / K * 1200) if len(x) > 1 else np.nan}
        rows.append(row)
    return pd.DataFrame(rows)


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--second", default="mt05", help="tag of the second arm (walk_*_<tag>_s*)")
    ap.add_argument("--second-label", default="Multi-task λ 0.5")
    ap.add_argument("--no-blend", action="store_true", help="omit the 50/50 score combination")
    ap.add_argument("--prefix", default="three_way")
    a = ap.parse_args()
    NAMES["mt05"] = a.second_label
    ts = datetime.now().strftime("%Y%m%d_%H%M%S"); run_dir = RESULTS / f"{a.prefix}_{ts}"; run_dir.mkdir(parents=True)
    panel = pd.read_parquet(PANEL, columns=["date", "country", "fwd_ret", "bench_ret", "fwd_excess"]); panel["date"] = pd.to_datetime(panel["date"])
    sd, sm = pooled("default"), pooled(a.second)
    S = pd.concat([sd.rename("default"), sm.rename("mt05")], axis=1).dropna()
    S["blend"] = 0.5 * S.groupby(level="date")["default"].transform(zs) + 0.5 * S.groupby(level="date")["mt05"].transform(zs)
    mo = {}
    ARMS_ = ("default", "mt05") if a.no_blend else ("default", "mt05", "blend")
    for k in ARMS_:
        d = S[k].rename("score").reset_index().merge(panel, on=["date", "country"])
        mo[k] = build_baskets(d, K, M).set_index("date")
    end = mo["default"].index.max()
    windows = {"Full": slice(None, None), "5y": slice(end - pd.DateOffset(months=59), None), "3y": slice(end - pd.DateOffset(months=35), None),
               "1y": slice(end - pd.DateOffset(months=11), None)}
    if a.no_blend:
        mo["blend"] = mo["mt05"]   # placeholder so block() runs; blend rows dropped below
    win = pd.concat([block(mo, sl).assign(window=w) for w, sl in windows.items()], ignore_index=True)
    per = pd.concat([block(mo, slice(a, b)).assign(window=lab) for lab, (a, b) in PERIODS.items()], ignore_index=True)
    if a.no_blend:
        win = win[win["portfolio"] != NAMES["blend"]]; per = per[per["portfolio"] != NAMES["blend"]]
    yrs = sorted(set(mo["default"].index.year))
    by_year = pd.DataFrame({NAMES[k]: [ann_ret(mo[k].loc[str(y), "basket_ret"]) for y in yrs] for k in ARMS_} | {NAMES["ew"]: [ann_ret(mo["default"].loc[str(y), "bench_ret"]) for y in yrs]}, index=yrs)
    by_year.index.name = "year"
    # overlap of the blend with each parent
    def sets(k):
        return None
    allm = pd.concat({k: v.add_prefix(f"{k}_") for k, v in mo.items() if k in ARMS_}, axis=1); allm.columns = [c[1] for c in allm.columns]
    allm.to_parquet(run_dir / "monthly.parquet")
    with pd.ExcelWriter(run_dir / "three_way.xlsx") as xw:
        win.to_excel(xw, sheet_name="Full_5y_3y_1y", index=False); per.to_excel(xw, sheet_name="periods", index=False)
        by_year.to_excel(xw, sheet_name="by_year"); allm.reset_index().to_excel(xw, sheet_name="monthly", index=False)
    summ = {"run_ts": ts, "first": str(mo["default"].index.min().date()), "last": str(end.date()), "months": int(len(mo["default"])),
            "full": win[win["window"] == "Full"].to_dict("records"), "note": "50/50 is descriptive, not pre-registered"}
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2, default=str))

    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    cols = {"default": "#888888", "mt05": "#1f4e79", "blend": "#b8860b", "ew": "#cccccc"}; imgs = []
    def b64(fig):
        b = io.BytesIO(); fig.savefig(b, format="png", dpi=130, bbox_inches="tight"); return base64.b64encode(b.getvalue()).decode()
    with PdfPages(run_dir / "charts.pdf") as pdf:
        fig, ax = plt.subplots(figsize=(10, 4.6))
        for k in ARMS_:
            ax.plot(mo[k].index, (1 + mo[k]["basket_ret"]).cumprod(), color=cols[k], lw=2, label=NAMES[k])
        ax.plot(mo["default"].index, (1 + mo["default"]["bench_ret"]).cumprod(), color=cols["ew"], lw=1.6, ls="--", label=NAMES["ew"])
        ax.set_yscale("log"); ax.set_title("Growth of $1, gross, monthly rebalance (log scale)"); ax.legend(frameon=False); ax.grid(alpha=.25)
        pdf.savefig(fig); imgs.append(b64(fig)); plt.close(fig)
        fig, ax = plt.subplots(figsize=(10, 4.6))
        for k in ARMS_:
            rel = (1 + mo[k]["basket_ret"]).cumprod() / (1 + mo[k]["bench_ret"]).cumprod(); ax.plot(rel.index, (rel / rel.cummax() - 1) * 100, color=cols[k], lw=1.6, label=NAMES[k])
        ax.set_title("Drawdown relative to the equal-weight benchmark, %"); ax.legend(frameon=False); ax.grid(alpha=.25)
        pdf.savefig(fig); imgs.append(b64(fig)); plt.close(fig)
        pp = per.pivot_table(index="window", columns="portfolio", values="ann_return_pct", sort=False)[[NAMES[k] for k in ARMS_ + ("ew",)]]
        fig, ax = plt.subplots(figsize=(10, 4.6)); pp.plot(kind="bar", ax=ax, color=[cols[k] for k in ARMS_ + ("ew",)], edgecolor="white")
        ax.axhline(0, color="k", lw=.5); ax.set_ylabel("% a year"); ax.set_title("Annualised return by period"); plt.xticks(rotation=0); ax.legend(frameon=False); ax.grid(axis="y", alpha=.25)
        pdf.savefig(fig); imgs.append(b64(fig)); plt.close(fig)

    def tbl(df, cols_, fmt):
        return "<table><thead><tr>" + "".join(f"<th>{c}</th>" for c in cols_) + "</tr></thead><tbody>" + "".join(
            "<tr>" + "".join(f"<td>{('—' if (isinstance(r[c], float) and np.isnan(r[c])) else (fmt[c].format(r[c]) if c in fmt else r[c]))}</td>" for c in cols_) + "</tr>" for _, r in df.iterrows()) + "</tbody></table>"
    hdr = {"portfolio": "Portfolio", "ann_return_pct": "Annualised return %", "ann_sd_pct": "Annualised std %", "max_drawdown_pct": "Max drawdown %",
           "turnover_oneway_pct_yr": "Turnover % a year (one-way)", "excess_ann_pct": "Excess over EW % a year", "excess_sd_pct": "Tracking error %", "max_rel_drawdown_pct": "Max drawdown vs EW %"}
    f = {"ann_return_pct": "{:.2f}", "ann_sd_pct": "{:.2f}", "max_drawdown_pct": "{:.1f}", "turnover_oneway_pct_yr": "{:.0f}", "excess_ann_pct": "{:+.2f}", "excess_sd_pct": "{:.2f}", "max_rel_drawdown_pct": "{:.1f}"}
    show = ["portfolio", "ann_return_pct", "ann_sd_pct", "max_drawdown_pct", "turnover_oneway_pct_yr", "excess_ann_pct", "excess_sd_pct", "max_rel_drawdown_pct"]
    def section(df, title):
        h = ""
        for w in df["window"].unique():
            x = df[df["window"] == w].rename(columns=hdr); h += f"<h3>{title} {w} ({int(df[df['window'] == w]['months'].iloc[0])} months)</h3>" + tbl(x, [hdr[c] for c in show], {hdr[k]: v for k, v in f.items()})
        return h
    pr = per.pivot_table(index="window", columns="portfolio", values="ann_return_pct", sort=False)[[NAMES[k] for k in ARMS_ + ("ew",)]].reset_index().rename(columns={"window": "Period"})
    pe = per[per["portfolio"] != NAMES["ew"]].pivot_table(index="window", columns="portfolio", values="excess_ann_pct", sort=False)[[NAMES[k] for k in ARMS_]].reset_index().rename(columns={"window": "Period"})
    yr_t = by_year.reset_index().rename(columns={"year": "Year"})
    html = f"""<!DOCTYPE html><html lang="en" data-theme="light"><head><meta charset="utf-8"><title>{' vs '.join(NAMES[k] for k in ARMS_)}</title>
<style>:root{{color-scheme:light}} body{{font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#222;background:#fff;line-height:1.55}}
h1{{font-size:1.5rem}} h2{{font-size:1.15rem;margin-top:2rem;border-bottom:1px solid #ddd}} h3{{font-size:1rem;margin:1.2rem 0 .3rem}} table{{border-collapse:collapse;font-size:.86rem;margin:.4rem 0}} th,td{{border:1px solid #ddd;padding:.3rem .55rem;text-align:right}} td:first-child,th:first-child{{text-align:left}}
.note{{background:#f6f8fa;border-left:4px solid #1f4e79;padding:.6rem .9rem;margin:.8rem 0}} img{{max-width:100%;border:1px solid #eee;margin:.4rem 0}}</style></head><body>
<h1>{', '.join(NAMES[k] for k in ARMS_)}</h1>
<p>Each portfolio: pooled three-draw ensemble, top 8 equal weight, hold while ranked ≤ 16, monthly, gross of costs, {summ['first']} → {summ['last']} ({summ['months']} months). {'' if a.no_blend else 'The 50/50 averages the two scores after standardising each within month, then applies the same rule. It is a descriptive look, not a pre-registered test. '}Returns are geometric annualised; drawdowns are peak to trough of cumulative wealth; turnover is one-way, names replaced ÷ 8, annualised.</p>
<img src="data:image/png;base64,{imgs[0]}">
<h2>Full, 5-year, 3-year, 1-year</h2>{section(win, '')}
<h2>Annualised return by period</h2><img src="data:image/png;base64,{imgs[2]}">
<h3>Total return, % a year</h3>{tbl(pr, list(pr.columns), {c: '{:.2f}' for c in pr.columns if c != 'Period'})}
<h3>Excess over equal weight, % a year</h3>{tbl(pe, list(pe.columns), {c: '{:+.2f}' for c in pe.columns if c != 'Period'})}
<h2>All statistics by period</h2>{section(per, '')}
<h2>Drawdown against the benchmark</h2><img src="data:image/png;base64,{imgs[1]}">
<h2>Calendar years, total return %</h2>{tbl(yr_t, list(yr_t.columns), {c: '{:.1f}' for c in yr_t.columns if c != 'Year'})}
<p style="color:#666;font-size:.85rem">Files: <code>{run_dir}</code></p></body></html>"""
    (run_dir / "report.html").write_text(html)
    pd.set_option("display.width", 220)
    for w in ("Full", "5y", "3y", "1y"):
        print(f"--- {w}"); print(win[win["window"] == w][["portfolio", "months", "ann_return_pct", "ann_sd_pct", "max_drawdown_pct", "turnover_oneway_pct_yr", "excess_ann_pct", "max_rel_drawdown_pct"]].round(2).to_string(index=False))
    print("--- periods, total return"); print(pr.round(2).to_string(index=False)); print("--- periods, excess"); print(pe.round(2).to_string(index=False))
    print("--- periods, sd / maxdd / turnover"); print(per.pivot_table(index="window", columns="portfolio", values=["ann_sd_pct", "max_drawdown_pct", "turnover_oneway_pct_yr"], sort=False).round(1).to_string())
    print(run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
