#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/build_report.py
=============================================================================

INPUT FILES (all resolved to the NEWEST run of each kind under
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/ ):
- results/corr_*/summary.json, factor_correlation_matrix.xlsx (sheets Clusters,
  CS_vs_TS), factor_correlation_heatmap.pdf        (stage 1, factor_correlation.py)
- results/screen_*/summary.json, factor_screen.parquet (stage 2, factor_screen.py)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/factor_set_v1.json
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v1/panel_manifest.json
                                                     (stage 3, build_panel.py)
- results/floor_*/summary.json, per_split.parquet, monthly.parquet,
  lgbm_importance.parquet, ridge_alpha_grid.parquet (stage 4, train_floor.py; optional)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/report_commentary.md
  Hand-written "what this means" text per stage (## stage1 .. ## stage5 headings),
  written after the numbers are seen, so the narrative never runs ahead of results.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/report.html
  One self-contained page (charts embedded as PNG) that can be opened in any browser.

VERSION: 1.0
LAST UPDATED: 2026-10-07
AUTHOR: Claude (Fable 5.1) for Arjun Divecha

DESCRIPTION:
Assembles the running report for the country top-8 ranking-model project: one
section per stage, each with the key numbers as tiles, a plain-English
explanation of what was done and how to read it, charts, sortable tables,
Arjun-facing commentary, and links to every underlying file. Re-run it after
any stage to refresh the page; stages whose artifacts do not exist yet are
shown as pending. Light mode only.

DEPENDENCIES: pandas, numpy, matplotlib, openpyxl, pyarrow (experiment .venv); pdftoppm (poppler)

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model"
  .venv/bin/python build_report.py && open results/report.html
=============================================================================
"""

from __future__ import annotations

import base64
import html
import io
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

EXP_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model")
RESULTS = EXP_DIR / "results"
PANEL_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v1")
SNAPSHOT = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/snapshot_2026_10_07/feature_panel_observed.parquet")
COMMENTARY = EXP_DIR / "report_commentary.md"
OUT = RESULTS / "report.html"

PALETTE = ["#1F77B4", "#D62728", "#2CA02C", "#9467BD", "#FF7F0E", "#8C564B", "#E377C2",
           "#17BECF", "#BCBD22", "#7F7F7F", "#AEC7E8", "#FFBB78", "#98DF8A", "#FF9896",
           "#C5B0D5", "#C49C94", "#F7B6D2", "#DBDB8D", "#9EDAE5"]
MODEL_LABEL = {
    "reference_REER_CS": "Reference: single best factor (REER)",
    "ridge": "Ridge regression",
    "lgbm_regression": "LightGBM — regression",
    "lgbm_top8_classifier": "LightGBM — top-8 classifier",
    "lgbm_lambdarank": "LightGBM — lambdarank@8",
    "ridge_shuffled": "Ridge, shuffled labels (control)",
    "lgbm_regression_shuffled": "LightGBM regression, shuffled labels (control)",
}
MODEL_ORDER = list(MODEL_LABEL)


# ── helpers ──────────────────────────────────────────────────────────────────
def latest(prefix: str) -> Path | None:
    runs = sorted(p for p in RESULTS.glob(f"{prefix}_*") if p.is_dir())
    return runs[-1] if runs else None


def flink(p: Path | str, label: str | None = None) -> str:
    p = Path(p)
    return f'<a class="file" href="file://{quote(str(p))}">{html.escape(label or p.name)}</a>'


def fig_to_b64(fig, dpi=120) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, facecolor="white", bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def img(b64: str, caption: str, width: str = "100%") -> str:
    return (f'<figure><img src="data:image/png;base64,{b64}" style="width:{width}" alt="{html.escape(caption)}">'
            f'<figcaption>{caption}</figcaption></figure>')


def pdf_to_b64(pdf: Path, dpi: int = 28) -> str:
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        prefix = Path(td) / "page"
        subprocess.run(["pdftoppm", "-png", "-r", str(dpi), "-singlefile", str(pdf), str(prefix)],
                       capture_output=True, check=True)
        return base64.b64encode((Path(td) / "page.png").read_bytes()).decode()


def kpis(items: list[tuple[str, str, str]]) -> str:
    return '<div class="kpis">' + "".join(
        f'<div class="kpi"><div class="v">{v}</div><div class="l">{l}</div><div class="s">{s}</div></div>'
        for v, l, s in items) + "</div>"


def table(df: pd.DataFrame, fmt: dict | None = None, max_rows: int | None = None, cls: str = "tbl") -> str:
    fmt = fmt or {}
    d = df if max_rows is None else df.head(max_rows)
    head = "".join(f"<th>{html.escape(str(c))}</th>" for c in d.columns)
    rows = []
    for _, r in d.iterrows():
        cells = []
        for c in d.columns:
            v = r[c]
            if isinstance(v, float) and np.isnan(v):
                cells.append('<td class="num">—</td>')
            elif isinstance(v, (float, np.floating)):
                cells.append(f'<td class="num">{fmt.get(c, "{:.2f}").format(v)}</td>')
            elif isinstance(v, (int, np.integer)):
                cells.append(f'<td class="num">{v:,}</td>')
            else:
                cells.append(f"<td>{html.escape(str(v))}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f'<table class="{cls} sortable"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>'


def md_to_html(text: str) -> str:
    """Tiny markdown: paragraphs, **bold**, `code`, '- ' lists."""
    out, para, in_list = [], [], False

    def flush():
        nonlocal para
        if para:
            out.append("<p>" + inline(" ".join(para)) + "</p>")
            para = []

    def inline(s):
        s = html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"`(.+?)`", r"<code>\1</code>", s)
        return s

    for line in text.splitlines():
        if line.startswith("- "):
            flush()
            if not in_list:
                out.append("<ul>"); in_list = True
            out.append("<li>" + inline(line[2:]) + "</li>")
            continue
        if in_list:
            out.append("</ul>"); in_list = False
        if not line.strip():
            flush()
        else:
            para.append(line.strip())
    flush()
    if in_list:
        out.append("</ul>")
    return "\n".join(out)


def load_commentary() -> dict[str, str]:
    if not COMMENTARY.exists():
        return {}
    text = COMMENTARY.read_text()
    parts = re.split(r"^## (\w+)\s*$", text, flags=re.M)
    return {parts[i]: md_to_html(parts[i + 1].strip()) for i in range(1, len(parts) - 1, 2)}


def commentary_block(c: dict, key: str) -> str:
    body = c.get(key)
    if not body:
        return '<div class="note pending">Commentary for this stage is written once the numbers are in.</div>'
    return f'<div class="note"><div class="note-title">What this means</div>{body}</div>'


# ── stage 1: factor universe ─────────────────────────────────────────────────
def stage1(c: dict) -> tuple[str, str]:
    run = latest("corr")
    if run is None:
        return "pending", '<div class="note pending">Not run yet.</div>'
    s = json.load(open(run / "summary.json"))
    xl = pd.ExcelFile(run / "factor_correlation_matrix.xlsx")
    cl = xl.parse("Clusters")
    ct = xl.parse("CS_vs_TS")
    for col in ("rho_cs_ts", "abs_rho"):   # em-dash = undefined in the workbook
        ct[col] = pd.to_numeric(ct[col], errors="coerce")
    norm = s["n_variables_included_by_normalization"]
    k = kpis([
        (f'{s["n_variables_included"]}', "z-scored factors in the matrix", f'{norm.get("CS",0)} cross-sectional + {norm.get("TS",0)} time-series'),
        (f'{s["n_pairs_abs_rho_ge_0.9"]}', "pairs correlated above 0.9", f'{s["n_pairs_abs_rho_ge_0.8"]} above 0.8, {s["n_pairs_abs_rho_ge_0.7"]} above 0.7'),
        (f'{s["clusters"]["0.90"]}', "distinct groups at the 0.9 cut", f'down from {s["n_variables_included"]} variables'),
        (f'{ct["abs_rho"].median():.2f}', "median |ρ| between a factor's CS and TS", f'{int((ct["abs_rho"] >= 0.8).sum())} of {len(ct)} factors above 0.8'),
    ])
    heat = img(pdf_to_b64(run / "factor_correlation_heatmap.pdf", 30),
               "Pairwise correlation of all z-scored factors, rows and columns ordered so that near-duplicates sit together. "
               "Red = move together, blue = move opposite, grey = too little overlapping history to say. "
               "Label colour = data source. The large block top-left is the GDELT news family.")
    big = cl[(cl["threshold_abs_rho"] == 0.9) & (cl["n_members"] >= 3)].sort_values("n_members", ascending=False)
    big = big[["n_members", "min_abs_rho_within", "sources", "members"]].rename(columns={
        "n_members": "members", "min_abs_rho_within": "weakest pair |ρ|", "sources": "sources", "members": "variables in the group"})
    ct_top = ct.head(10)[["base_variable", "source", "rho_cs_ts", "overlap_n"]].rename(columns={
        "base_variable": "factor", "rho_cs_ts": "ρ (CS vs TS)", "overlap_n": "country-months"})
    body = f"""
<p class="lead">Before picking inputs for a model we need to know which of the warehouse's monthly factors are
really the same thing wearing different names. Every factor exists in two normalised forms: a
<strong>cross-sectional z-score (CS)</strong> — how a country looks against the other 33 <em>this month</em> —
and a <strong>time-series z-score (TS)</strong> — how a country looks against <em>its own history</em>.
This stage correlates all of them, pooled over every country-month, and clusters the result.</p>
{k}
{heat}
<h4>The largest duplicate groups (members correlated 0.9 or better)</h4>
{table(big, {"weakest pair |ρ|": "{:.2f}"}, max_rows=14)}
<h4>Where a factor's CS and TS versions are nearly the same thing</h4>
<p>If the two versions correlate above 0.8 you only need one of them. For most factors they are genuinely
different views (median 0.37), which is why both are kept for the model.</p>
{table(ct_top, {"ρ (CS vs TS)": "{:.2f}"})}
{commentary_block(c, "stage1")}
<div class="files"><div class="files-title">Files</div>
{flink(run / "factor_correlation_matrix.xlsx", "Correlation workbook (Correlation, Overlap_N, Variables, Top_Pairs, Clusters, CS_vs_TS)")}
{flink(run / "factor_correlation_heatmap.pdf", "Clustered heatmap (PDF, zoomable)")}
{flink(run / "factor_correlation_matrix.parquet", "Matrix (parquet)")} · {flink(run / "summary.json")} · {flink(run / "run.log")}
· {flink(EXP_DIR / "factor_correlation.py", "script")}</div>"""
    return "done", body


# ── stage 2: univariate screen ───────────────────────────────────────────────
def stage2(c: dict) -> tuple[str, str]:
    run = latest("screen")
    if run is None:
        return "pending", '<div class="note pending">Not run yet.</div>'
    s = json.load(open(run / "summary.json"))
    sc = pd.read_parquet(run / "factor_screen.parquet")
    ok = sc.dropna(subset=["fm_t"]).copy()
    best = ok.sort_values("top8_t", ascending=False).iloc[0]
    k = kpis([
        (f'{s["n_factors_reported"]}', "factors with enough history to score", f'of {s["n_factors"]} in the matrix'),
        (f'{s["n_abs_t_gt_1_96"]}', "clear |t| = 1.96", f'about {s["expected_by_chance"]:.0f} would by chance'),
        (f'{s["n_bh_q_lt_0_10"]}', "survive a false-discovery cut (q < 0.10)", "Benjamini–Hochberg across all factors"),
        (f'{best["top8_excess_ann_pct"]:.1f}%', "best top-8 basket, per year over the average", f'{best["variable"]} · hit rate {best["top8_hit_rate"]:.2f}'),
    ])
    # chart: histogram + top-30 bars
    sources = sorted(ok["source"].unique())
    col = {sname: PALETTE[i % len(PALETTE)] for i, sname in enumerate(sources)}
    fig = plt.figure(figsize=(13, 7.5), facecolor="white")
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.35], wspace=0.45)
    ax0 = fig.add_subplot(gs[0, 0])
    ax0.hist(ok["fm_t"], bins=36, color="#1F77B4", alpha=0.85, edgecolor="white")
    for x in (-1.96, 1.96):
        ax0.axvline(x, color="#D62728", ls="--", lw=1)
    ax0.set_xlabel("t-statistic of the factor's monthly slope on next-month excess return")
    ax0.set_ylabel("number of factors")
    ax0.set_title("Most factors sit inside the noise band", fontsize=11)
    ax1 = fig.add_subplot(gs[0, 1])
    top = ok.reindex(ok["fm_t"].abs().sort_values(ascending=False).index).head(30).iloc[::-1]
    ax1.barh(range(len(top)), top["fm_t"], color=[col[x] for x in top["source"]], height=0.72)
    ax1.set_yticks(range(len(top)))
    ax1.set_yticklabels(top["variable"], fontsize=7.5)
    ax1.axvline(0, color="#444", lw=0.8)
    for x in (-1.96, 1.96):
        ax1.axvline(x, color="#D62728", ls="--", lw=0.8)
    ax1.set_xlabel("t-statistic (sign = direction)")
    ax1.set_title("Top 30 by |t|", fontsize=11)
    handles = [plt.Line2D([], [], marker="s", ls="", color=col[x], label=x) for x in sources]
    ax1.legend(handles=handles, loc="lower right", fontsize=7, frameon=False, title="source", title_fontsize=8)
    for ax in (ax0, ax1):
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    chart = img(fig_to_b64(fig), "Left: the spread of t-statistics across all scored factors; the dashed lines are the ±1.96 noise band. "
                                 "Right: the thirty strongest. For T2 factors the sign already reflects the 'lower is better' convention; "
                                 "for other sources a negative bar simply means the factor works inverted.")
    cols = ["rank_by_abs_t", "variable", "source", "lag_months", "n_months", "fm_t", "rank_ic_mean",
            "top8_excess_ann_pct", "top8_t", "top8_hit_rate", "ls_spread_ann_pct", "fm_q_bh"]
    t25 = ok.head(25)[cols].rename(columns={
        "rank_by_abs_t": "#", "variable": "factor", "lag_months": "lag (m)", "n_months": "months", "fm_t": "t-stat",
        "rank_ic_mean": "rank IC", "top8_excess_ann_pct": "top-8 excess %/yr", "top8_t": "top-8 t",
        "top8_hit_rate": "hit rate", "ls_spread_ann_pct": "top−bottom %/yr", "fm_q_bh": "q-value"})
    body = f"""
<p class="lead">Each factor on its own: does a high score this month go with a high return next month?
For every factor and every month we run a regression across the 34 countries of next month's excess return
(country minus the equal-weight average) on the factor, then average the slope over all months and ask whether
it is reliably different from zero — the <strong>t-statistic</strong>. We also build the thing you actually trade:
the equal-weight <strong>top-8 basket</strong> by that factor, and measure what it made over the average, per year,
and how often it won. Slow sources (IMF, FRED, BIS, OECD) are lagged a month so the factor was really knowable in time.</p>
{k}
{chart}
<h4>The 25 strongest factors</h4>
<p>Columns: <em>t-stat</em> of the monthly slope; <em>rank IC</em> = average within-month rank correlation with next-month return;
<em>top-8 excess</em> = what the top-8 basket by this factor made over the equal-weight average, annualised;
<em>hit rate</em> = share of months that basket beat the average; <em>q-value</em> = false-discovery-adjusted significance.
Click a header to sort.</p>
{table(t25, {"t-stat": "{:.2f}", "rank IC": "{:.3f}", "top-8 excess %/yr": "{:.1f}", "top-8 t": "{:.2f}", "hit rate": "{:.2f}", "top−bottom %/yr": "{:.1f}", "q-value": "{:.2f}"})}
{commentary_block(c, "stage2")}
<div class="files"><div class="files-title">Files</div>
{flink(run / "factor_screen.xlsx", "Screen workbook (Screen, Clusters_Ranked, Notes)")} ·
{flink(run / "factor_screen_chart.pdf", "chart (PDF)")} · {flink(run / "factor_screen.parquet", "table (parquet)")} ·
{flink(run / "monthly_top8_excess.parquet", "monthly top-8 excess per factor")} · {flink(run / "monthly_rank_ic.parquet", "monthly rank IC per factor")} ·
{flink(run / "summary.json")} · {flink(run / "run.log")} · {flink(EXP_DIR / "factor_screen.py", "script")}</div>"""
    return "done", body


# ── stage 3: factor set & panel ──────────────────────────────────────────────
def stage3(c: dict) -> tuple[str, str]:
    fsp = EXP_DIR / "factor_set_v1.json"
    man = PANEL_DIR / "panel_manifest.json"
    if not (fsp.exists() and man.exists()):
        return "pending", '<div class="note pending">Not built yet.</div>'
    fs = json.load(open(fsp))
    m = json.load(open(man))
    k = kpis([
        (f'{fs["n_factors"]}', "factors in the model set", f'{fs["by_normalization"].get("CS",0)} CS + {fs["by_normalization"].get("TS",0)} TS'),
        (f'{m["rows"]:,}', "country-month rows", f'{m["date_min"]} → {m["date_max"]}'),
        (f'{len(m["countries"])}', "countries", "the T2 universe"),
        (f'{fs["by_lag_months"].get("1",0)}', "factors lagged one month", "slow sources, so nothing is used before it was published"),
    ])
    by_year = pd.Series(m["mean_features_present_by_year"]).astype(float)
    fig, ax = plt.subplots(figsize=(11, 3.6), facecolor="white")
    ax.bar(by_year.index.astype(int), by_year.values, color="#1F77B4", width=0.8)
    ax.axhline(fs["n_factors"], color="#D62728", ls="--", lw=1, label=f'all {fs["n_factors"]} factors')
    ax.set_ylabel("factors present per row (avg)")
    ax.set_title("How many of the 256 factors a typical country-month actually has", fontsize=11)
    ax.legend(frameon=False, fontsize=9)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    cov = img(fig_to_b64(fig), "Coverage builds through the 2000s as sources start, and jumps in 2015–16 when the GDELT news block begins. "
                               "Early rows have about half the factors; the models have to cope with that missingness rather than drop the rows.")
    src = pd.DataFrame({"source": list(fs["by_source"]), "factors": list(fs["by_source"].values())}).sort_values("factors", ascending=False)
    body = f"""
<p class="lead">Your selection rule: keep every factor the screen could score, then drop the price-level and market-cap
series (<code>PX_LAST</code>, <code>MCAP</code>, <code>MCAP Adj</code>) in both normalisations, keeping <code>Mcap Weights</code>.
That list is frozen to a config file, and the warehouse snapshot is turned into one modelling table: a row per
country-month, the {fs["n_factors"]} factors as columns with publication lags already applied, and the target —
next month's return minus the equal-weight average of all countries.</p>
{k}
{cov}
<div class="two-col">
<div><h4>Factors by source</h4>{table(src)}</div>
<div><h4>Dropped by rule</h4><ul>{"".join(f"<li><code>{html.escape(v)}</code></li>" for v in fs["dropped"])}</ul>
<h4>The lag convention</h4><p>A row dated D holds, for every factor, the value that was available at D. T2 and GDELT are
knowable at month-end and used as stored; everything else is shifted forward one month. The target for row D is the
return over the month after D. So every row reads "information at D → return after D" and nothing downstream has to
think about timing again.</p></div></div>
{commentary_block(c, "stage3")}
<div class="files"><div class="files-title">Files</div>
{flink(fsp, "factor_set_v1.json (the frozen list, committed)")} · {flink(PANEL_DIR / "factor_set_v1.xlsx", "factor list (xlsx)")} ·
{flink(PANEL_DIR / "feature_panel_v1.parquet", "modelling panel (parquet)")} · {flink(man, "panel_manifest.json")} ·
{flink(PANEL_DIR / "build.log", "build.log")} · {flink(EXP_DIR / "build_panel.py", "script")}</div>"""
    return "done", body


# ── stage 4: floor models ────────────────────────────────────────────────────
def stage4(c: dict) -> tuple[str, str]:
    run = latest("floor")
    if run is None or not (run / "summary.json").exists():
        hb = None
        if run is not None and (run / "heartbeat.json").exists():
            hb = json.load(open(run / "heartbeat.json"))
        msg = ("Running now — " + f'{hb["fits_done"]} of {hb["fits_total"]} model fits done, {hb["elapsed_s"]//60} min elapsed'
               if hb else "Not run yet.")
        return "running" if hb else "pending", f'<div class="note pending">{msg}</div>'
    s = json.load(open(run / "summary.json"))
    ps = pd.read_parquet(run / "per_split.parquet")
    mo = pd.read_parquet(run / "monthly.parquet")
    imp = pd.read_parquet(run / "lgbm_importance.parquet")
    grid = pd.read_parquet(run / "ridge_alpha_grid.parquet")
    se = s["noise_floor"]["se_ann_pct_random_split"]
    n_rand = s["config"]["n_random"]

    ev = ps[(ps.set == "eval") & (ps.split_type == "random")]
    tr = ps[(ps.set == "train") & (ps.split_type == "random")]
    bl = ps[(ps.set == "eval") & (ps.split_type == "blocked")]
    agg = ev.groupby("model").agg(mean=("top8_excess_ann_pct", "mean"), sd=("top8_excess_ann_pct", "std"),
                                  hit=("top8_hit_rate", "mean"), prec=("precision8", "mean"), ic=("rank_ic", "mean"),
                                  soft=("soft_excess_ann_pct_tau0.25", "mean"), soft1=("soft_excess_ann_pct_tau1.0", "mean"),
                                  neff1=("neff_tau1.0", "mean"), n=("split", "size"))
    agg_tr = tr.groupby("model")["top8_excess_ann_pct"].mean()
    agg_bl = bl.groupby("model").agg(mean=("top8_excess_ann_pct", "mean"), sd=("top8_excess_ann_pct", "std"))
    order = [m for m in MODEL_ORDER if m in agg.index]
    real = [m for m in order if "shuffled" not in m and not m.startswith("reference")]
    best = agg.loc[real, "mean"].idxmax()
    k = kpis([
        (f'{agg.loc[best, "mean"]:+.1f}%', "best model's top-8 excess, per year (eval months)", f'{MODEL_LABEL[best]} · hit rate {agg.loc[best, "hit"]:.2f}'),
        (f'±{se:.1f}%', "noise on any single split", f"standard error of one split's annual figure; {n_rand} splits average it down"),
        (f'{agg.loc["reference_REER_CS", "mean"]:+.1f}%', "single best factor, same months", "the bar the models must clear"),
        (f'{agg_tr[best]:+.1f}%', "the same model on its training months", "the gap to eval is how much is memorised"),
    ])

    # chart A: strip plot of eval top-8 excess per model (random splits), with blocked means
    fig, ax = plt.subplots(figsize=(12, 5.2), facecolor="white")
    for i, m in enumerate(order):
        v = ev[ev.model == m]["top8_excess_ann_pct"].to_numpy()
        jit = (np.random.default_rng(i).random(len(v)) - 0.5) * 0.35
        colr = "#9E9E9E" if "shuffled" in m else ("#FF7F0E" if m.startswith("reference") else "#1F77B4")
        ax.scatter(np.full(len(v), i) + jit, v, s=22, color=colr, alpha=0.6, edgecolor="white", lw=0.5)
        ax.plot([i - 0.3, i + 0.3], [v.mean()] * 2, color="#000", lw=2.2)
        if m in agg_bl.index:
            ax.scatter([i + 0.42], [agg_bl.loc[m, "mean"]], marker="D", s=46, color="#D62728", zorder=5)
    ax.axhline(0, color="#444", lw=0.8)
    ax.axhspan(-2 * se, 2 * se, color="#D62728", alpha=0.06, lw=0)
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([MODEL_LABEL[m].replace(" — ", "\n").replace(" (control)", "\n(control)") for m in order], fontsize=8.5)
    ax.set_ylabel("top-8 basket excess over the average, % per year")
    ax.set_title(f"Evaluation months only: each dot is one of {n_rand} random splits; black bar = mean; "
                 "red diamond = mean over the 5 contiguous blocks; pink band = ±2 standard errors of a single split", fontsize=10)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    chartA = img(fig_to_b64(fig), "What each model's top-8 basket made over the equal-weight average on months it had not seen, "
                                  "across all the random re-partitions. Grey = the shuffled-label controls, which should sit at zero.")

    # chart B: train vs eval
    fig, ax = plt.subplots(figsize=(10, 4.2), facecolor="white")
    x = np.arange(len(real))
    ax.bar(x - 0.18, [agg_tr[m] for m in real], width=0.36, color="#AEC7E8", label="training months (fit)")
    ax.bar(x + 0.18, [agg.loc[m, "mean"] for m in real], width=0.36, color="#1F77B4", label="evaluation months")
    ax.axhline(0, color="#444", lw=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels([MODEL_LABEL[m].replace(" — ", "\n") for m in real], fontsize=9)
    ax.set_ylabel("top-8 excess, % per year")
    ax.legend(frameon=False, fontsize=9)
    ax.set_title("How much each model memorises: training-month fit versus evaluation-month result", fontsize=10.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    chartB = img(fig_to_b64(fig), "Trees can fit the training months almost perfectly; what matters is the right-hand bar.")

    # chart C: cumulative monthly eval excess, averaged by month across splits, best model vs reference vs shuffled
    def monthly_avg(model):
        d = mo[(mo.model == model) & (mo.set == "eval") & (mo.split.str.startswith("random"))]
        return d.groupby("date")["top8_excess"].mean().sort_index()
    fig, ax = plt.subplots(figsize=(12, 4.4), facecolor="white")
    for m, colr, lw in ((best, "#1F77B4", 2.2), ("reference_REER_CS", "#FF7F0E", 1.6),
                        ("ridge", "#2CA02C", 1.4), ("lgbm_regression", "#9467BD", 1.4)):
        if m in agg.index and (m == best or m not in (best,)):
            ser = monthly_avg(m)
            ax.plot(ser.index, (ser.cumsum() * 100), color=colr, lw=lw, label=MODEL_LABEL[m])
    for m in ("ridge_shuffled",):
        if m in agg.index:
            ser = monthly_avg(m)
            ax.plot(ser.index, ser.cumsum() * 100, color="#9E9E9E", lw=1.2, ls="--", label=MODEL_LABEL[m])
    ax.axhline(0, color="#444", lw=0.8)
    ax.set_ylabel("cumulative excess, % (simple sum)")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title("Where the excess came from over time (each month's figure averaged over the splits in which it was an evaluation month)", fontsize=10)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    chartC = img(fig_to_b64(fig), "A steadily rising line means the edge is spread across the history; a line made by one or two jumps means it is a few months.")

    # chart D: importance top 20 + ridge alpha sensitivity
    fig = plt.figure(figsize=(13, 5.4), facecolor="white")
    gs = fig.add_gridspec(1, 2, width_ratios=[1.4, 1], wspace=0.5)
    ax0 = fig.add_subplot(gs[0, 0])
    top = imp.head(20).iloc[::-1]
    ax0.barh(range(len(top)), top["gain_share"] * 100, color="#1F77B4", height=0.72)
    ax0.set_yticks(range(len(top)))
    ax0.set_yticklabels(top["feature"], fontsize=8)
    ax0.set_xlabel("share of the trees' total gain, %")
    ax0.set_title("What the LightGBM regression leaned on (top 20, averaged over splits)", fontsize=10)
    ax1 = fig.add_subplot(gs[0, 1])
    g = grid.groupby("alpha")["inner_top8_excess_ann_pct"].agg(["mean", "std"])
    ax1.errorbar(np.log10(g.index), g["mean"], yerr=g["std"], marker="o", color="#2CA02C", capsize=3)
    ax1.set_xlabel("ridge penalty, log10(alpha)")
    ax1.set_ylabel("inner-CV top-8 excess, % per year")
    ax1.set_title("Ridge: how much the penalty matters", fontsize=10)
    for ax in (ax0, ax1):
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
    chartD = img(fig_to_b64(fig), "Left: the factors the tree model used most. Right: the ridge penalty chosen inside the training months; "
                                  "a flat curve means the result does not hinge on this choice.")

    # tables
    def tbl(df_src, label):
        rows = []
        for m in order:
            if m not in df_src.model.values:
                continue
            d = df_src[df_src.model == m]
            rows.append({"model": MODEL_LABEL[m], "top-8 excess %/yr": d["top8_excess_ann_pct"].mean(),
                         "± across splits": d["top8_excess_ann_pct"].std(), "hit rate": d["top8_hit_rate"].mean(),
                         "caught of true top 8": d["precision8"].mean() * 8, "rank IC": d["rank_ic"].mean(),
                         "soft-k excess %/yr (sharp)": d["soft_excess_ann_pct_tau0.25"].mean(),
                         "soft-k excess %/yr (soft)": d["soft_excess_ann_pct_tau1.0"].mean(),
                         "effective holdings (soft)": d["neff_tau1.0"].mean(), "splits": len(d)})
        f = {"top-8 excess %/yr": "{:+.1f}", "± across splits": "{:.1f}", "hit rate": "{:.2f}", "caught of true top 8": "{:.2f}",
             "rank IC": "{:.3f}", "soft-k excess %/yr (sharp)": "{:+.1f}", "soft-k excess %/yr (soft)": "{:+.1f}", "effective holdings (soft)": "{:.1f}"}
        return f"<h4>{label}</h4>" + table(pd.DataFrame(rows), f)
    tables = tbl(ev, f"Evaluation months, {n_rand} random splits (the headline)") + \
             tbl(bl, "Evaluation months, 5 contiguous blocks (temporal-proximity check)") + \
             tbl(tr, "Training months (fit, not performance)")

    body = f"""
<p class="lead">The floor: how well do a regularised linear model and gradient-boosted trees do on your objective before
any neural network is tried. Every later model has to beat these. The objective is the equal-weight <strong>top-8 basket
by model score versus the equal-weight average of all countries</strong>, next month, reported per year.
Since eight need not be rigid, every model is also pushed through the same <strong>soft top-k</strong> allocation
(memberships that sum to 8, no country above 12.5%) at a sharp and a soft setting.</p>
<div class="two-col"><div>
<h4>The models</h4>
<ul>
<li><strong>Reference</strong> — no model: rank countries by the single best factor from the screen (REER). The bar to clear.</li>
<li><strong>Ridge regression</strong> — a weighted sum of the factors, with the weight-shrinkage penalty chosen inside the training months.</li>
<li><strong>LightGBM regression</strong> — boosted trees predicting next-month excess return; pick the top 8 predictions.</li>
<li><strong>LightGBM top-8 classifier</strong> — trees predicting "will this country finish in the top 8"; pick the 8 highest probabilities.</li>
<li><strong>LightGBM lambdarank</strong> — trees trained directly on the ordering within each month, caring most about the top of the list.</li>
</ul></div><div>
<h4>How they are judged</h4>
<ul>
<li>Months are split <strong>80/20 at random, {n_rand} different ways</strong> (all 34 countries of a month on the same side). Each model is trained on the 80% and scored on the 20%, and the headline is the mean and spread across the {n_rand} re-partitions.</li>
<li><strong>5 contiguous blocks</strong> are also held out one at a time. If the random-month score is much higher than the blocked score, part of it is temporal proximity — neighbouring months leaking across the split.</li>
<li><strong>Shuffled-label controls</strong>: ridge and the tree regression refit with next-month returns scrambled across countries inside each training month. Their evaluation score should be zero; if it is not, the pipeline is leaking.</li>
<li>Trees stop early on a slice of <em>training</em> months; evaluation months are never used for stopping or tuning.</li>
</ul></div></div>
<div class="note warn"><div class="note-title">Read the numbers against the noise</div>
<p>A random 8-country pick has a monthly standard deviation of about {s["noise_floor"]["monthly_sd_top8_excess"]*100:.1f}% against the average.
Over one split's {s["n_eval_months_random"]} evaluation months that makes the annualised figure uncertain by about <strong>±{se:.1f}% per year</strong>
(one standard error). Any single split within ±{2*se:.0f}% of zero is noise; the mean over {n_rand} splits is what to read, and even that is a
statement about stability on this history, not about the future.</p></div>
{k}
{chartA}
{tables}
{chartB}
{chartC}
{chartD}
{commentary_block(c, "stage4")}
<div class="files"><div class="files-title">Files</div>
{flink(run / "per_split.xlsx", "per-split results (xlsx)")} · {flink(run / "per_split.parquet", "per-split (parquet)")} ·
{flink(run / "monthly.parquet", "monthly series per split/model")} · {flink(run / "predictions_eval.parquet", "evaluation-month scores per country")} ·
{flink(run / "lgbm_importance.parquet", "tree feature importance")} · {flink(run / "ridge_alpha_grid.parquet", "ridge penalty grid")} ·
{flink(run / "summary.json")} · {flink(run / "run.log")} · {flink(EXP_DIR / "train_floor.py", "script")}</div>"""
    return "done", body


# ── page ─────────────────────────────────────────────────────────────────────
CSS = """
:root{--bg:#ffffff;--fg:#1a1a1a;--muted:#5f6368;--line:#e4e7eb;--card:#f7f8fa;--accent:#1F77B4;--warn:#fff4e5;--warnb:#f0b35c;--ok:#2CA02C;--pend:#9E9E9E}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif}
.wrap{max-width:1140px;margin:0 auto;padding:0 20px 60px}
header.top{position:sticky;top:0;background:rgba(255,255,255,.96);backdrop-filter:blur(6px);border-bottom:1px solid var(--line);z-index:5}
header.top .wrap{display:flex;align-items:center;gap:18px;padding:10px 20px;flex-wrap:wrap}
header.top .title{font-weight:700;font-size:16px;margin-right:auto}
nav a{color:var(--muted);text-decoration:none;font-size:13px;padding:4px 8px;border-radius:6px}nav a:hover{background:var(--card);color:var(--fg)}
.badge{display:inline-block;font-size:11px;padding:1px 7px;border-radius:10px;margin-left:4px;color:#fff;vertical-align:middle}
.badge.done{background:var(--ok)}.badge.running{background:#FF7F0E}.badge.pending{background:var(--pend)}
h1{font-size:28px;margin:28px 0 6px}h2{font-size:22px;margin:40px 0 10px;padding-top:12px;border-top:2px solid var(--line)}h4{margin:22px 0 8px;font-size:15px}
.sub{color:var(--muted);margin:0 0 14px}
p.lead{font-size:16px;color:#333}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin:18px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.kpi .v{font-size:26px;font-weight:700;color:var(--accent)}.kpi .l{font-size:13px;margin-top:2px}.kpi .s{font-size:12px;color:var(--muted);margin-top:4px}
figure{margin:18px 0}figure img{max-width:100%;border:1px solid var(--line);border-radius:8px;background:#fff}figcaption{font-size:12.5px;color:var(--muted);margin-top:6px}
table.tbl{border-collapse:collapse;width:100%;font-size:13px;margin:8px 0 16px}table.tbl th,table.tbl td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}
table.tbl th{background:var(--card);cursor:pointer;user-select:none;position:sticky;top:48px}table.tbl td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
table.tbl tbody tr:nth-child(even){background:#fbfbfc}
.note{background:var(--card);border-left:4px solid var(--accent);border-radius:8px;padding:12px 16px;margin:18px 0}.note.warn{background:var(--warn);border-left-color:var(--warnb)}
.note.pending{border-left-color:var(--pend);color:var(--muted)}.note-title{font-weight:700;margin-bottom:4px}
.files{font-size:13px;color:var(--muted);margin-top:14px;line-height:1.9}.files-title{font-weight:700;color:var(--fg)}a.file{color:var(--accent);text-decoration:none}a.file:hover{text-decoration:underline}
.two-col{display:grid;grid-template-columns:1fr 1fr;gap:28px}@media(max-width:800px){.two-col{grid-template-columns:1fr}}
.flow{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0}.flow .step{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px;flex:1;min-width:180px;font-size:13px}
.flow .step b{display:block;font-size:13.5px;margin-bottom:3px}
code{background:#eef1f4;padding:1px 5px;border-radius:4px;font-size:12.5px}
.glossary dt{font-weight:700;margin-top:10px}.glossary dd{margin:2px 0 0 0;color:#333}
footer{color:var(--muted);font-size:12.5px;margin-top:40px}
"""
JS = """
document.querySelectorAll('table.sortable th').forEach((th,idx)=>{th.addEventListener('click',()=>{
 const t=th.closest('table'),tb=t.tBodies[0],rows=[...tb.rows],asc=!(th.dataset.asc==='1');
 t.querySelectorAll('th').forEach(h=>delete h.dataset.asc);th.dataset.asc=asc?'1':'0';
 const num=s=>{const v=parseFloat(s.replace(/[,%+]/g,''));return isNaN(v)?null:v};
 rows.sort((a,b)=>{const x=a.cells[idx].innerText,y=b.cells[idx].innerText,nx=num(x),ny=num(y);
  if(nx!==null&&ny!==null)return asc?nx-ny:ny-nx;return asc?x.localeCompare(y):y.localeCompare(x)});
 rows.forEach(r=>tb.appendChild(r));});});
"""


def main() -> int:
    c = load_commentary()
    stages = [
        ("stage1", "1 · Factor universe & duplication", stage1),
        ("stage2", "2 · Each factor on its own", stage2),
        ("stage3", "3 · Your factor set & the modelling panel", stage3),
        ("stage4", "4 · The floor: linear model & trees", stage4),
    ]
    rendered = []
    for key, title, fn in stages:
        status, body = fn(c)
        rendered.append((key, title, status, body))
    nav = "".join(f'<a href="#{k}">{t.split(" · ")[0]}<span class="badge {s}">{s}</span></a>' for k, t, s, _ in rendered)
    sections = "".join(f'<section id="{k}"><h2>{html.escape(t)} <span class="badge {s}">{s}</span></h2>{b}</section>'
                       for k, t, s, b in rendered)
    overview_c = c.get("overview", "")
    next_c = c.get("next", "")
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    page = f"""<!doctype html><html lang="en" data-theme="light"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Country Top-8 Model — running report</title>
<style>{CSS}</style></head><body>
<header class="top"><div class="wrap"><span class="title">Country top-8 ranking model</span><nav>{nav}<a href="#next">Next</a><a href="#glossary">Glossary</a></nav></div></header>
<div class="wrap">
<h1>Can a model pick the eight best countries next month?</h1>
<p class="sub">Running report · branch <code>exp/NN</code> · regenerated {now} · every number on this page comes from a file linked under its section</p>
<p class="lead">The question: using roughly 250 monthly factors per country, can a trained model choose an equal-weight basket of
eight countries out of 34 that beats the equal-weight average of all of them over the following month — and by how much?
This page follows the work stage by stage. Each stage says what was done, shows the key numbers, explains how to read them,
and links the files.</p>
<div class="flow">
<div class="step"><b>1 · Which factors are duplicates?</b>Correlate every z-scored factor with every other; cluster.</div>
<div class="step"><b>2 · Which factors predict anything alone?</b>Regress each on next-month return; top-8 baskets.</div>
<div class="step"><b>3 · Freeze the inputs</b>Your pick, lags applied, one modelling table.</div>
<div class="step"><b>4 · The floor</b>Ridge and boosted trees on the top-8 objective, many random splits.</div>
<div class="step"><b>5 · Neural net (next)</b>Shared net with a soft-top-8 loss; then cross-country attention.</div>
</div>
{('<div class="note"><div class="note-title">Where things stand</div>' + overview_c + '</div>') if overview_c else ''}
{sections}
<section id="next"><h2>What comes next</h2>{next_c or '<p class="sub">To be written as stages complete.</p>'}</section>
<section id="glossary"><h2>Glossary</h2><dl class="glossary">
<dt>Cross-sectional z-score (CS)</dt><dd>A factor rescaled within one month across the 34 countries: zero is the average country that month, +1 is one standard deviation above it. Answers "how does this country look against its peers right now".</dd>
<dt>Time-series z-score (TS)</dt><dd>A factor rescaled within one country across its own history: zero is that country's long-run norm. Answers "how does this country look against its own past".</dd>
<dt>Excess return</dt><dd>A country's next-month return minus the equal-weight average of all countries that month. The thing every model is trying to rank.</dd>
<dt>Top-8 excess</dt><dd>Average excess return of the eight countries the model (or factor) ranks highest, equal-weighted. Reported per year (monthly mean × 12).</dd>
<dt>Soft top-k</dt><dd>Instead of exactly eight equal positions, memberships between 0 and 1 that sum to 8 (so no country exceeds 12.5%), with countries near the cut-off held fractionally. "Sharp" is close to a hard eight; "soft" spreads further. Effective holdings = 1 / Σ weight².</dd>
<dt>Hit rate</dt><dd>Share of months in which the top-8 basket beat the average.</dd>
<dt>t-statistic</dt><dd>The average monthly effect divided by its uncertainty. Beyond ±1.96 is conventionally "significant", but with hundreds of factors tested about 5% land there by chance.</dd>
<dt>Rank IC</dt><dd>Within-month rank correlation between a score and next-month return; +1 perfect ordering, 0 none.</dd>
<dt>Random-month split</dt><dd>80% of months for training, 20% for evaluation, chosen at random with all countries of a month on the same side. Repeated with different random draws. Tests whether a fitted relationship transfers to other months of the same history — not a forecast of the future.</dd>
<dt>Contiguous-block split</dt><dd>Hold out ~64 consecutive months at a time. Compared with the random split it shows how much of the score is neighbouring months leaking across.</dd>
<dt>Shuffled-label control</dt><dd>Refit with next-month returns scrambled across countries inside each training month. Should score zero on evaluation; if it does not, something is leaking.</dd>
<dt>Publication lag</dt><dd>Slow data (IMF, FRED, BIS, OECD) is only known a month after the period it describes, so it is shifted forward one month. T2 and GDELT are knowable at month-end.</dd>
</dl></section>
<footer>Generated by <code>build_report.py</code> from the newest run of each stage. Light mode only.</footer>
</div><script>{JS}</script></body></html>"""
    OUT.write_text(page)
    print(f"wrote {OUT} ({OUT.stat().st_size/1e6:.1f} MB); stages: " + ", ".join(f"{k}={s}" for k, _, s, _ in rendered))
    return 0


if __name__ == "__main__":
    sys.exit(main())
