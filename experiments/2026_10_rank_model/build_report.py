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

SOFT_TAUS = [0.25, 1.0]   # soft top-k temperatures used by train_floor.py / train_nn.py (column suffixes in per_split)
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
    "nn_mse": "Neural net — predict excess return (MSE)",
    "nn_soft_top8": "Neural net — soft top-8 objective",
    "nn_mse_then_soft": "Neural net — MSE warm-start, then soft top-8",
    "nn_soft_top8_shuffled": "Neural net soft top-8, shuffled labels (control)",
    "attn_mse": "Cross-country attention — predict excess return (MSE)",
    "attn_soft_top8": "Cross-country attention — soft top-8 objective",
    "attn_soft_top8_shuffled": "Attention soft top-8, shuffled labels (control)",
}
MODEL_ORDER = list(MODEL_LABEL)
SHORT = {"reference_REER_CS": "Reference\n(REER alone)", "ridge": "Ridge\n(broad linear)", "lgbm_regression": "LightGBM\nregression",
         "lgbm_top8_classifier": "LightGBM\ntop-8 classifier", "lgbm_lambdarank": "LightGBM\nlambdarank@8",
         "ridge_shuffled": "Ridge\nshuffled (control)", "lgbm_regression_shuffled": "LightGBM reg.\nshuffled (control)",
         "nn_mse": "Net\nMSE", "nn_soft_top8": "Net\nsoft top-8", "nn_mse_then_soft": "Net\nMSE→soft top-8",
         "nn_soft_top8_shuffled": "Net soft top-8\nshuffled (control)",
         "attn_mse": "Attention\nMSE", "attn_soft_top8": "Attention\nsoft top-8", "attn_soft_top8_shuffled": "Attention\nshuffled (control)"}


def strip_chart(ev: pd.DataFrame, bl: pd.DataFrame, order: list[str], se: float, n_rand: int, title: str):
    """Dots = per-split eval top-8 excess; bar = mean; diamond = blocked mean; band = ±2 SE of one split."""
    fig, ax = plt.subplots(figsize=(12, 5.2), facecolor="white")
    bl_mean = bl.groupby("model")["top8_excess_ann_pct"].mean() if len(bl) else pd.Series(dtype=float)
    for i, m in enumerate(order):
        v = ev[ev.model == m]["top8_excess_ann_pct"].to_numpy()
        jit = (np.random.default_rng(i).random(len(v)) - 0.5) * 0.35
        colr = "#9E9E9E" if "shuffled" in m else ("#FF7F0E" if m.startswith("reference") else ("#2CA02C" if m == "ridge" else "#1F77B4"))
        ax.scatter(np.full(len(v), i) + jit, v, s=22, color=colr, alpha=0.6, edgecolor="white", lw=0.5)
        if len(v):
            ax.plot([i - 0.3, i + 0.3], [v.mean()] * 2, color="#000", lw=2.2)
        if m in bl_mean.index:
            ax.scatter([i + 0.42], [bl_mean[m]], marker="D", s=46, color="#D62728", zorder=5)
    ax.axhline(0, color="#444", lw=0.8)
    ax.axhspan(-2 * se, 2 * se, color="#D62728", alpha=0.06, lw=0)
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([SHORT.get(m, m) for m in order], fontsize=8.5)
    ax.set_ylabel("top-8 basket excess over the average, % per year")
    ax.set_title(title, fontsize=10)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    return fig


# ── helpers ──────────────────────────────────────────────────────────────────
def latest(prefix: str) -> Path | None:
    """Newest UNTAGGED run directory (<prefix>_<YYYYMMDD>_<HHMMSS>); tagged ablations are listed by tagged_runs()."""
    pat = re.compile(rf"^{prefix}_\d{{8}}_\d{{6}}$")
    runs = sorted(p for p in RESULTS.glob(f"{prefix}_*") if p.is_dir() and pat.match(p.name))
    done = [p for p in runs if (p / "summary.json").exists()]
    # prefer the newest COMPLETED run; an in-progress run (heartbeat, no summary) is returned only if nothing is complete
    return done[-1] if done else (runs[-1] if runs else None)


def tagged_runs(prefix: str) -> dict[str, Path]:
    """{tag: newest run dir} for <prefix>_<ts>_<tag> directories that completed (summary.json present)."""
    pat = re.compile(rf"^{prefix}_\d{{8}}_\d{{6}}_(.+)$")
    out: dict[str, Path] = {}
    for p in sorted(q for q in RESULTS.glob(f"{prefix}_*") if q.is_dir()):
        m = pat.match(p.name)
        if m and (p / "summary.json").exists():
            out[m.group(1)] = p
    return out


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
        s = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", s)
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
    has_ref = "reference_REER_CS" in agg.index
    third = ((f'{agg.loc["reference_REER_CS", "mean"]:+.1f}%', "single best factor, same months", "the bar the models must clear (retired after the REER audit)")
             if has_ref else
             (f'{agg.loc["ridge", "blocked_mean"]:+.1f}%' if "blocked_mean" in agg.columns else f'{agg_bl.loc["ridge", "mean"]:+.1f}%',
              "ridge on contiguous blocks", "no single-factor reference on the cleaned panel — REER was retired by the audit"))
    k = kpis([
        (f'{agg.loc[best, "mean"]:+.1f}%', "best model's top-8 excess, per year (eval months)", f'{MODEL_LABEL[best]} · hit rate {agg.loc[best, "hit"]:.2f}'),
        (f'±{se:.1f}%', "noise on any single split", f"standard error of one split's annual figure; {n_rand} splits average it down"),
        third,
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
    short = {"reference_REER_CS": "Reference\n(REER alone)", "ridge": "Ridge", "lgbm_regression": "LightGBM\nregression",
             "lgbm_top8_classifier": "LightGBM\ntop-8 classifier", "lgbm_lambdarank": "LightGBM\nlambdarank@8",
             "ridge_shuffled": "Ridge\nshuffled (control)", "lgbm_regression_shuffled": "LightGBM reg.\nshuffled (control)"}
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels([short.get(m, m) for m in order], fontsize=8.5)
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
    ax.set_xticklabels([short.get(m, m) for m in real], fontsize=9)
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


# ── stage 5: neural network ──────────────────────────────────────────────────
def stage5(c: dict) -> tuple[str, str]:
    run = latest("nn")
    if run is None or not (run / "summary.json").exists():
        hb = json.load(open(run / "heartbeat.json")) if run is not None and (run / "heartbeat.json").exists() else None
        msg = (f'Running now — {hb["runs_done"]} of {hb["runs_total"]} nets trained, {hb["elapsed_s"]//60} min elapsed'
               if hb else "Not run yet.")
        return ("running" if hb else "pending"), f'<div class="note pending">{msg}</div>'
    s = json.load(open(run / "summary.json"))
    ps = pd.read_parquet(run / "per_split.parquet")
    mo = pd.read_parquet(run / "monthly.parquet")
    runs = pd.read_parquet(run / "runs.parquet")
    cap = s["capacity_check"]
    floor_run = latest("floor")
    fs = json.load(open(floor_run / "summary.json")) if floor_run else None
    se = fs["noise_floor"]["se_ann_pct_random_split"] if fs else 2.9
    n_rand = s["config"]["n_random"]
    cfg = s["config"]

    ens = ps[ps.member != "seed"]
    ev = ens[(ens.set == "eval") & (ens.split_type == "random")]
    bl = ens[(ens.set == "eval") & (ens.split_type == "blocked")]
    tr = ens[(ens.set == "train") & (ens.split_type == "random")]
    seeds = ps[(ps.member == "seed") & (ps.set == "eval") & (ps.split_type == "random")]
    order = [m for m in ["ridge", "reference_REER_CS", "nn_mse", "nn_soft_top8", "nn_mse_then_soft", "nn_soft_top8_shuffled"] if m in ev.model.values]
    nets = [m for m in order if m.startswith("nn_") and "shuffled" not in m]
    agg = ev.groupby("model")["top8_excess_ann_pct"].agg(["mean", "std"])
    best = agg.loc[nets, "mean"].idxmax()
    piv = ev.pivot(index="split", columns="model", values="top8_excess_ann_pct")
    diff = piv[best] - piv["ridge"] if "ridge" in piv else None
    diff_t = float(diff.mean() / (diff.std() / np.sqrt(len(diff)))) if diff is not None else float("nan")
    bl_agg = bl.groupby("model")["top8_excess_ann_pct"].mean()
    k = kpis([
        (f'{agg.loc[best, "mean"]:+.1f}%', "best net's top-8 excess, per year (eval months)", f'{MODEL_LABEL[best]} · seed-ensemble'),
        (f'{agg.loc["ridge", "mean"]:+.1f}%' if "ridge" in agg.index else "—", "the broad linear model, same months", "the bar to clear"),
        (f'{diff.mean():+.1f}%' if diff is not None else "—", "net minus ridge, split by split", f'paired t-stat {diff_t:.1f} over {n_rand} splits'),
        (f'{bl_agg.get(best, float("nan")):+.1f}%', "best net on contiguous blocks", f'ridge {bl_agg.get("ridge", float("nan")):+.1f}% on the same blocks'),
    ])
    chartA = img(fig_to_b64(strip_chart(ev, bl, order, se, n_rand,
                 f"Evaluation months only: each dot is one of {n_rand} random splits (nets = 5-seed ensembles); black bar = mean; "
                 "red diamond = mean over the 5 contiguous blocks; pink band = ±2 SE of a single split")),
                 "The nets next to the broad linear model and the single-factor reference on exactly the same splits. Grey = shuffled-label control.")
    # paired differences vs ridge
    fig, ax = plt.subplots(figsize=(11, 3.8), facecolor="white")
    for j, m in enumerate(nets):
        d = (piv[m] - piv["ridge"]).sort_values().to_numpy()
        ax.plot(np.arange(len(d)) + j * 0.0, d, marker="o", ms=4, lw=1.2, label=SHORT[m].replace("\n", " "))
    ax.axhline(0, color="#444", lw=0.8)
    ax.set_xlabel(f"random splits, sorted by difference ({n_rand})")
    ax.set_ylabel("net minus ridge, % per year")
    ax.legend(frameon=False, fontsize=8.5)
    ax.set_title("Split by split: does the net beat the broad linear model on the same months?", fontsize=10.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    chartB = img(fig_to_b64(fig), "Each point is one split; above zero the net won that split. A line mostly above zero with a small spread is a real edge; "
                                  "a line straddling zero is a tie.")
    # cumulative
    def monthly_avg(df_m, model):
        d = df_m[(df_m.model == model) & (df_m.set == "eval") & (df_m.split.str.startswith("random"))]
        return d.groupby("date")["top8_excess"].mean().sort_index()
    fig, ax = plt.subplots(figsize=(12, 4.4), facecolor="white")
    ax.plot(monthly_avg(mo, best).index, monthly_avg(mo, best).cumsum() * 100, color="#1F77B4", lw=2.2, label=MODEL_LABEL[best])
    if floor_run and (floor_run / "monthly.parquet").exists():
        fm = pd.read_parquet(floor_run / "monthly.parquet")
        for m, colr in (("ridge", "#2CA02C"), ("reference_REER_CS", "#FF7F0E")):
            ser = monthly_avg(fm, m)
            ax.plot(ser.index, ser.cumsum() * 100, color=colr, lw=1.5, label=MODEL_LABEL[m])
    if "nn_soft_top8_shuffled" in mo.model.values:
        ser = monthly_avg(mo, "nn_soft_top8_shuffled")
        ax.plot(ser.index, ser.cumsum() * 100, color="#9E9E9E", lw=1.2, ls="--", label=MODEL_LABEL["nn_soft_top8_shuffled"])
    ax.axhline(0, color="#444", lw=0.8)
    ax.set_ylabel("cumulative excess, % (simple sum)")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title("Where the excess came from over time (evaluation months, averaged over the splits in which each month was held out)", fontsize=10)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    chartC = img(fig_to_b64(fig), "Compare the slopes rather than the end points: a model whose line keeps rising is earning its edge across the whole history.")

    def tbl(df_src, label, extra_seed_sd=False):
        rows = []
        for m in order:
            if m not in df_src.model.values:
                continue
            d = df_src[df_src.model == m]
            row = {"model": MODEL_LABEL[m], "top-8 excess %/yr": d["top8_excess_ann_pct"].mean(),
                   "± across splits": d["top8_excess_ann_pct"].std(), "hit rate": d["top8_hit_rate"].mean(),
                   "caught of true top 8": d["precision8"].mean() * 8, "rank IC": d["rank_ic"].mean(),
                   "soft-k excess %/yr (sharp)": d["soft_excess_ann_pct_tau0.25"].mean(),
                   "soft-k excess %/yr (soft)": d["soft_excess_ann_pct_tau1.0"].mean(), "splits": len(d)}
            if extra_seed_sd and m.startswith("nn_"):
                sd_seed = seeds[seeds.model == m].groupby("split")["top8_excess_ann_pct"].std().mean()
                row["± across seeds (within a split)"] = sd_seed
            rows.append(row)
        f = {"top-8 excess %/yr": "{:+.1f}", "± across splits": "{:.1f}", "hit rate": "{:.2f}", "caught of true top 8": "{:.2f}",
             "rank IC": "{:.3f}", "soft-k excess %/yr (sharp)": "{:+.1f}", "soft-k excess %/yr (soft)": "{:+.1f}",
             "± across seeds (within a split)": "{:.1f}"}
        return f"<h4>{label}</h4>" + table(pd.DataFrame(rows), f)
    tables = tbl(ev, f"Evaluation months, {n_rand} random splits (nets are 5-seed ensembles)", True) + \
             tbl(bl, "Evaluation months, 5 contiguous blocks") + tbl(tr, "Training months (fit, not performance)")
    rs = runs[runs.tag == "real"].groupby("objective")[["best_epoch", "seconds"]].mean().round(1)
    body = f"""
<p class="lead">The first neural network: one small network, shared across countries, scoring each country-month from the same
{s["n_inputs"]} inputs the linear model used ({cfg["hidden"][0]} and {cfg["hidden"][1]} hidden units, dropout {cfg["dropout"]},
weight decay {cfg["weight_decay"]}). It is judged on <strong>exactly the same {n_rand} random splits and 5 blocks</strong> as the floor,
with the same metrics, so every comparison with ridge is paired. The bar is the broad linear model, not the single factor.</p>
<div class="two-col"><div>
<h4>Three ways of training the same network</h4>
<ul>
<li><strong>Predict excess return (MSE)</strong> — regress on next-month excess return, then pick the 8 highest predictions. The "predict, then select" baseline.</li>
<li><strong>Soft top-8 objective</strong> — the objective itself. Within each month the network's 34 scores are z-scored (so it cannot sharpen the selection by scaling), turned into memberships that sum to 8 with no country above 12.5%, and the network is trained to maximise the membership-weighted next-month excess return — the expected return of the basket. The gradient through the selection is exact; no reinforcement learning is involved.</li>
<li><strong>MSE warm-start, then soft top-8</strong> — train on MSE first, then fine-tune on the objective, to see whether the direct objective adds anything once the network already predicts returns.</li>
</ul></div><div>
<h4>Discipline</h4>
<ul>
<li>Five seeds per split and objective; the <strong>seed-average of scores is the model</strong> ("ensemble"). Single-seed results are kept to show how much the nets wobble.</li>
<li>Early stopping on a 12% slice of <em>training</em> months, on the soft-top-8 expected excess; evaluation months never touch training, stopping or selection.</li>
<li>Shuffled-label control on the first {cfg["n_shuffle"]} random splits.</li>
<li>Fit-capacity check: an unregularised net on 24 months reached a top-8 excess of {cap["fitted_top8_excess_pct_month"]:.1f}% per month against
{cap["perfect_foresight_top8_excess_pct_month"]:.1f}% with perfect foresight (precision {cap["fitted_precision8"]:.2f}, rank IC {cap["fitted_rank_ic"]:.2f}) — the machinery can fit when asked to.</li>
<li>Typical run: {int(rs["best_epoch"].mean())} epochs to the best inner-validation score, {rs["seconds"].mean():.0f} s on one CPU core; {s["n_runs"]} nets in {s["elapsed_s"]/60:.0f} minutes.</li>
</ul></div></div>
{k}
{chartA}
{chartB}
{tables}
{chartC}
{commentary_block(c, "stage5")}
<div class="files"><div class="files-title">Files</div>
{flink(run / "per_split.xlsx", "per-split results (xlsx, with a runs sheet)")} · {flink(run / "per_split.parquet", "per-split (parquet)")} ·
{flink(run / "monthly.parquet", "monthly series per split/model")} · {flink(run / "predictions_eval.parquet", "evaluation-month scores per country")} ·
{flink(run / "runs.parquet", "one row per trained net")} · {flink(run / "capacity_check.json")} · {flink(run / "summary.json")} ·
{flink(run / "run.log")} · {flink(EXP_DIR / "train_nn.py", "script")}</div>"""
    return "done", body


# ── stage 6: ablations (tagged reruns of the floor and the net) ──────────────
ABLATION_TITLE = {
    "noreer": "Without REER (all four variants removed)",
    "base256": "New base after the hill-climb: 256/128 hidden, ten seeds (full panel)",
    "nogdelt": "Without the GDELT news block (92 factors removed) — on the new base",
    "nopresence": "Without the per-source presence columns — on the new base",
    "global": "With global context (VIX, Treasury yields and curve, broad dollar, global GPR) — on the new base",
    "attn": "Cross-country attention (64-dim, 2 layers, 4 heads; five seeds) — vs the new base",
}
ABLATION_ORDER = ["noreer", "base256", "nogdelt", "nopresence", "global", "attn"]
# which run the NETS of each ablation are compared against: a tag (floor_/nn_ *_<tag>) or an explicit
# nn_<ts> directory name. The v1 ablations are pinned to the v1 stage-5 run because the untagged
# headline runs moved to the cleaned v3 panel after the REER audit.
ABLATION_BASE = {"noreer": "nn_20261007_112400", "base256": "nn_20261007_112400", "nogdelt": "base256",
                 "nopresence": "base256", "global": "base256", "attn": "base256"}
ABLATION_FLOOR_BASE = "floor_20261007_110654"   # ridge/trees in the v1 ablations are compared against the v1 floor
# a tagged run whose models have different names than the base's: {ablation model: base model}
ABLATION_MODEL_MAP = {"attn": {"attn_mse": "nn_mse", "attn_soft_top8": "nn_soft_top8"}}


def _era_table(mo_base: pd.DataFrame, mo_abl: pd.DataFrame, ridge_mo: pd.DataFrame, model: str, abl_model: str | None = None) -> pd.DataFrame:
    """Eval top-8 excess by decade, pooled over months, for the net in the base run, in the ablation, and ridge."""
    def bym(df, m):
        e = df[(df.model == m) & (df.set == "eval") & (df.split.str.startswith("random"))]
        return e.groupby("date")["top8_excess"].mean()
    rows = []
    series = {"base": bym(mo_base, model), "ablation": bym(mo_abl, abl_model or model), "ridge (full panel)": bym(ridge_mo, "ridge")}
    for lab, (a, b) in {"2000–2009": (2000, 2009), "2010–2019": (2010, 2019), "2020–2026": (2020, 2026)}.items():
        row = {"era": lab}
        for k, s in series.items():
            x = s[(s.index.year >= a) & (s.index.year <= b)]
            row[k + " %/yr"] = float(x.mean() * 1200) if len(x) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def stage6(c: dict) -> tuple[str, str]:
    fl_tags, nn_tags = tagged_runs("floor"), tagged_runs("nn")
    tags = [t for t in ABLATION_ORDER if t in fl_tags or t in nn_tags] + sorted(set(fl_tags) | set(nn_tags) - set(ABLATION_ORDER))
    base_floor = RESULTS / ABLATION_FLOOR_BASE if (RESULTS / ABLATION_FLOOR_BASE).exists() else latest("floor")
    base_nn = latest("nn")
    if not tags or base_floor is None:
        return "pending", '<div class="note pending">No ablation runs yet. An ablation is a rerun of the floor and the net on a changed panel, tagged so it sits here instead of replacing the headline.</div>'
    fb = pd.read_parquet(base_floor / "per_split.parquet")
    floor_base = fb[fb.model.isin(["ridge", "lgbm_regression", "reference_REER_CS"])]
    ridge_mo = pd.read_parquet(base_floor / "monthly.parquet")

    def nn_rows(run):
        d = pd.read_parquet(run / "per_split.parquet")
        return d[d.member == "ensemble"]
    models = ["ridge", "lgbm_regression", "nn_mse", "nn_soft_top8", "nn_mse_then_soft"]
    parts = []
    for tag in tags:
        pieces = []
        if tag in fl_tags:
            d = pd.read_parquet(fl_tags[tag] / "per_split.parquet"); d = d[d.model.isin(["ridge", "lgbm_regression"])]; pieces.append(d)
        if tag in nn_tags:
            pieces.append(nn_rows(nn_tags[tag]))
        abl = pd.concat(pieces, ignore_index=True)
        # comparison base: nets vs the configured base run; ridge/trees vs the untagged floor
        nb_tag = ABLATION_BASE.get(tag)
        if nb_tag and (RESULTS / nb_tag).is_dir():
            nn_base_run, base_label = RESULTS / nb_tag, f"{nb_tag} (v1 stage-5 net, 64/32, five seeds)"
        elif nb_tag:
            nn_base_run, base_label = nn_tags.get(nb_tag), ABLATION_TITLE.get(nb_tag, nb_tag).split(":")[0]
        else:
            nn_base_run, base_label = base_nn, "the current headline net"
        nb = nn_rows(nn_base_run) if nn_base_run is not None else pd.DataFrame()
        base = pd.concat([floor_base, nb], ignore_index=True)
        mmap = ABLATION_MODEL_MAP.get(tag, {})
        rows, chart_rows = [], []
        for m in models + list(mmap):
            bm = mmap.get(m, m)                      # the base model this one is compared with
            if m not in abl.model.values or bm not in base.model.values:
                continue
            b_ev = base[(base.model == bm) & (base.set == "eval") & (base.split_type == "random")].set_index("split")["top8_excess_ann_pct"]
            a_ev = abl[(abl.model == m) & (abl.set == "eval") & (abl.split_type == "random")].set_index("split")["top8_excess_ann_pct"]
            common = b_ev.index.intersection(a_ev.index)
            d = (a_ev[common] - b_ev[common])
            b_bl = base[(base.model == bm) & (base.set == "eval") & (base.split_type == "blocked")]["top8_excess_ann_pct"].mean()
            a_bl = abl[(abl.model == m) & (abl.set == "eval") & (abl.split_type == "blocked")]["top8_excess_ann_pct"].mean()
            rows.append({"model": MODEL_LABEL[m] + (f" (vs {SHORT[bm].replace(chr(10), ' ')})" if bm != m else ""),
                         "base %/yr": b_ev[common].mean(), "ablation %/yr": a_ev[common].mean(),
                         "change %/yr": d.mean(), "paired t": d.mean() / (d.std() / np.sqrt(len(d))) if len(d) > 2 else float("nan"),
                         "splits where ablation is worse": int((d < 0).sum()), "splits": len(d),
                         "blocks: base": b_bl, "blocks: ablation": a_bl})
            chart_rows.append((SHORT[m].replace("\n", " "), d.mean(), d.std() / np.sqrt(len(d))))
        tbl = table(pd.DataFrame(rows), {"base %/yr": "{:+.1f}", "ablation %/yr": "{:+.1f}", "change %/yr": "{:+.2f}",
                                         "paired t": "{:.2f}", "blocks: base": "{:+.1f}", "blocks: ablation": "{:+.1f}"})
        fig, ax = plt.subplots(figsize=(9, 3.4), facecolor="white")
        ax.bar(range(len(chart_rows)), [r[1] for r in chart_rows], yerr=[2 * r[2] for r in chart_rows], color="#1F77B4", capsize=4, width=0.6)
        ax.axhline(0, color="#444", lw=0.8)
        ax.set_xticks(range(len(chart_rows))); ax.set_xticklabels([r[0] for r in chart_rows], fontsize=9)
        ax.set_ylabel("ablation minus full, % per year")
        ax.set_title(f"{ABLATION_TITLE.get(tag, tag).split(' — ')[0]}: change in evaluation top-8 excess vs its base, paired over the random splits (±2 SE)", fontsize=9.5)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        chart = img(fig_to_b64(fig), "Bars below zero mean the model lost edge when the inputs were removed; bars whose error range covers zero are ties.")
        fs_path = None
        for src in (nn_tags.get(tag), fl_tags.get(tag)):
            if src is not None:
                s = json.load(open(src / "summary.json"))
                fs_path = s.get("factor_set") or s.get("config", {}).get("factor_set")
                if fs_path:
                    break
        dropped = ""
        if fs_path and Path(fs_path).exists():
            fsj = json.load(open(fs_path))
            dropped = (f'<p>Factor set: <strong>{fsj["n_factors"]}</strong> factors. Removed by rule: '
                       + ", ".join(f"<code>{html.escape(v)}</code>" for v in fsj["dropped"]) + ".</p>")
        files = " · ".join(flink(p / "per_split.xlsx", f"{kind} per-split (xlsx)") + " · " + flink(p / "summary.json", f"{kind} summary")
                           for kind, p in (("floor", fl_tags.get(tag)), ("net", nn_tags.get(tag))) if p is not None)
        era = ""
        if tag in nn_tags and nn_base_run is not None and (nn_tags[tag] / "monthly.parquet").exists():
            em = _era_table(pd.read_parquet(nn_base_run / "monthly.parquet"), pd.read_parquet(nn_tags[tag] / "monthly.parquet"), ridge_mo,
                            "nn_mse", abl_model=next((k for k, v in mmap.items() if v == "nn_mse"), "nn_mse"))
            era = ("<h4>By era — predict-then-select net, evaluation months pooled</h4>"
                   + table(em, {k: "{:+.1f}" for k in em.columns if k != "era"}))
        parts.append(f"""<h3>{html.escape(ABLATION_TITLE.get(tag, tag))}</h3>
<p class="sub">Nets compared against: {html.escape(base_label)}. Ridge and trees compared against the full-panel floor.</p>{dropped}{tbl}{chart}{era}
{commentary_block(c, f"ablation_{tag}")}<div class="files"><div class="files-title">Files</div>{files}</div>""")
    body = f"""
<p class="lead">An ablation reruns the floor and the net on a changed panel — same {len(base[base.split_type=='random'].split.unique())} random splits,
same blocks, same seeds — so the only thing that moved is the inputs, and every comparison with the full-panel run is paired split by split.</p>
{''.join(parts)}"""
    return "done", body


# ── stage 7: hill-climb ──────────────────────────────────────────────────────
def stage7(c: dict) -> tuple[str, str]:
    run = latest("hill")
    if run is None or not (run / "summary.json").exists():
        hb = json.load(open(run / "heartbeat.json")) if run is not None and (run / "heartbeat.json").exists() else None
        msg = (f'Running now — {hb["runs_done"]} of {hb["runs_total"]} nets trained, {hb["elapsed_s"]//60} min elapsed'
               if hb else "Not run yet.")
        return ("running" if hb else "pending"), f'<div class="note pending">{msg}</div>'
    s = json.load(open(run / "summary.json"))
    cfg = pd.read_parquet(run / "configs.parquet")
    curve = pd.read_parquet(run / "seed_curve.parquet")
    ps = pd.read_parquet(run / "per_split.parquet")
    floor_run = latest("floor")
    se = json.load(open(floor_run / "summary.json"))["noise_floor"]["se_ann_pct_random_split"] if floor_run else 2.9
    base_row = cfg[cfg.config == "base"].iloc[0]
    best = cfg.iloc[0]
    k = kpis([
        (f'{best["eval_top8_ann_pct"]:+.1f}%', "best config, eval top-8 excess per year", f'{best["config"]} · {best["hidden"]} hidden, dropout {best["dropout"]}, wd {best["weight_decay"]}'),
        (f'{best["vs_base_pct"]:+.2f}%', "best minus base, paired", f'paired t {best["vs_base_t"]:.1f} · wins {int(best["wins_vs_base"])}/{int(best["n_splits"])}'),
        (f'{base_row["eval_top8_ann_pct"]:+.1f}%', "base config (stage 5 reproduced)", (f'max difference to stage 5: {s["reproducibility_max_abs_diff_vs_stage5"]:.3f}%' if s.get("reproducibility_max_abs_diff_vs_stage5") is not None else "")),
        (f'{best["train_top8_ann_pct"]:+.0f}%', "best config on its training months", f'base fits {base_row["train_top8_ann_pct"]:+.0f}%; the gap is memorisation'),
    ])
    # chart A: configs — eval (dot) with ±2SE paired vs base, train (faint), blocked (diamond)
    order = cfg.sort_values("eval_top8_ann_pct", ascending=True)
    fig, ax = plt.subplots(figsize=(11, 5.4), facecolor="white")
    y = np.arange(len(order))
    ax.barh(y, order["train_top8_ann_pct"], color="#E8EEF5", height=0.6, label="training months (fit)")
    ax.errorbar(order["eval_top8_ann_pct"], y, xerr=2 * order["eval_sd_splits"] / np.sqrt(order["n_splits"]), fmt="o", color="#1F77B4", capsize=3, label="evaluation months (±2 SE over splits)")
    ax.scatter(order["blocked_top8_ann_pct"], y, marker="D", color="#D62728", s=40, zorder=5, label="contiguous blocks")
    ax.axvline(base_row["eval_top8_ann_pct"], color="#2CA02C", ls="--", lw=1, label="base config, eval")
    ax.set_yticks(y); ax.set_yticklabels(order["config"], fontsize=9)
    ax.set_xlabel("top-8 excess over the average, % per year")
    ax.legend(frameon=False, fontsize=8.5, loc="lower right")
    ax.set_title("The sweep: each config as a 5-seed ensemble on the same 30 random splits and 5 blocks", fontsize=10.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    chartA = img(fig_to_b64(fig), "Read the blue dots against the green line (base) and the pink error bars; the faint bars show how hard each config fits its own training months.")
    # chart B: seed curve
    cr = curve[curve.split_type == "random"].groupby("n_seeds")["top8_excess_ann_pct"].agg(["mean", "std", "count"]).reset_index()
    single = cr[cr.n_seeds == 0]["mean"].iloc[0] if (cr.n_seeds == 0).any() else np.nan
    cr = cr[cr.n_seeds > 0]
    fig, ax = plt.subplots(figsize=(8.5, 3.8), facecolor="white")
    ax.errorbar(cr["n_seeds"], cr["mean"], yerr=2 * cr["std"] / np.sqrt(cr["count"]), marker="o", color="#1F77B4", capsize=3)
    if not np.isnan(single):
        ax.axhline(single, color="#9E9E9E", ls="--", lw=1, label=f"average single net ({single:+.1f}%)")
    ax.set_xscale("log"); ax.set_xticks(cr["n_seeds"]); ax.set_xticklabels(cr["n_seeds"].astype(int))
    ax.set_xlabel("nets averaged (seeds)"); ax.set_ylabel("eval top-8 excess, % per year")
    ax.set_title("Seed curve, base config: how much does averaging more nets buy?", fontsize=10.5)
    ax.legend(frameon=False, fontsize=8.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    chartB = img(fig_to_b64(fig), "Where the curve flattens is the ensemble size worth paying for.")
    show = cfg[["config", "hidden", "dropout", "weight_decay", "lr", "eval_top8_ann_pct", "eval_sd_splits", "vs_base_pct", "vs_base_t", "wins_vs_base",
                "vs_ridge_pct", "vs_ridge_t", "blocked_top8_ann_pct", "train_top8_ann_pct", "eval_hit_rate", "eval_rank_ic", "mean_best_epoch"]].rename(columns={
        "weight_decay": "wd", "eval_top8_ann_pct": "eval %/yr", "eval_sd_splits": "± splits", "vs_base_pct": "vs base", "vs_base_t": "t",
        "wins_vs_base": "wins/30", "vs_ridge_pct": "vs ridge", "vs_ridge_t": "t (ridge)", "blocked_top8_ann_pct": "blocks %/yr",
        "train_top8_ann_pct": "train %/yr", "eval_hit_rate": "hit", "eval_rank_ic": "rank IC", "mean_best_epoch": "epochs"})
    tbl = table(show, {"dropout": "{:.2f}", "wd": "{:.2f}", "lr": "{:.4f}", "eval %/yr": "{:+.1f}", "± splits": "{:.1f}", "vs base": "{:+.2f}", "t": "{:.1f}",
                       "vs ridge": "{:+.2f}", "t (ridge)": "{:.1f}", "blocks %/yr": "{:+.1f}", "train %/yr": "{:+.0f}", "hit": "{:.2f}", "rank IC": "{:.3f}", "epochs": "{:.0f}"})
    body = f"""
<p class="lead">The hill-climb: change one ingredient of the stage-5 network at a time — dropout, weight decay, width, learning rate, and two
"heavy" combinations — and keep what improves the evaluation months on the same {s["n_splits"]} splits. Objective: predict-then-select
({s["objective"]}), the fastest of the three and the best on contiguous blocks. Every config is a {s["seeds_sweep"]}-seed ensemble and every comparison
is paired against the base config and against ridge. Separately, the base config is trained with {s["seeds_curve"]} seeds to find where averaging saturates.
{s["n_runs"]} nets in {s["elapsed_s"]/60:.0f} minutes.</p>
{k}
{chartA}
<h4>All configs, sorted by evaluation result</h4>
{tbl}
{chartB}
{commentary_block(c, "stage7")}
<div class="files"><div class="files-title">Files</div>
{flink(run / "per_split.xlsx", "configs / per-split / seed-curve (xlsx)")} · {flink(run / "configs.parquet", "configs (parquet)")} ·
{flink(run / "seed_curve.parquet", "seed curve (parquet)")} · {flink(run / "per_split.parquet", "per-split (parquet)")} · {flink(run / "runs.parquet", "one row per net")} ·
{flink(run / "summary.json")} · {flink(run / "run.log")} · {flink(EXP_DIR / "hillclimb_nn.py", "script")}</div>"""
    return "done", body


# ── stage 8: walk-forward ────────────────────────────────────────────────────
def stage8(c: dict) -> tuple[str, str]:
    run = latest("walk")
    if run is None or not (run / "summary.json").exists():
        hb = json.load(open(run / "heartbeat.json")) if run is not None and (run / "heartbeat.json").exists() else None
        msg = (f'Running now — {hb["runs_done"]} of {hb["runs_total"]} nets trained, {hb["elapsed_s"]//60} min elapsed'
               if hb else "Not run yet.")
        return ("running" if hb else "pending"), f'<div class="note pending">{msg}</div>'
    s = json.load(open(run / "summary.json"))
    mo = pd.read_parquet(run / "monthly_oos.parquet")
    by = pd.read_parquet(run / "by_year.parquet")
    pf = pd.read_parquet(run / "per_fold.parquet")
    # rule-aware runs (walk_forward.py >= 2026-10-07 pm) nest overall/paired by rule; older runs are plain top-8 only
    rule_aware = "default_rule" in s
    default_rule = s.get("default_rule", "plain_top8")
    rule_label = {"plain_top8": "plain top-8 (re-pick every month)"}
    for r_ in s.get("rules", []):
        if r_.startswith("buffer_M"):
            rule_label[r_] = f"hysteresis: hold while ranked ≤ {r_[8:]} (the default)"
    if rule_aware:
        ov_all, pr_all = s["overall"], s["paired_vs_ridge"]
        ov, pr = ov_all[default_rule], pr_all[default_rule]
        mo_all, by_all, pf_all = mo, by, pf
        mo, by, pf = mo[mo.rule == default_rule], by[by.rule == default_rule], pf[pf.rule == default_rule]
    else:
        ov, pr = s["overall"], s["paired_vs_ridge"]
        ov_all, pr_all = {"plain_top8": ov}, {"plain_top8": pr}
        mo_all, by_all, pf_all = mo.assign(rule="plain_top8"), by.assign(rule="plain_top8"), pf.assign(rule="plain_top8")
    models = [m for m in ["ridge", "reference_REER_CS", "nn_mse", "nn_soft_top8"] if m in ov]
    nets = [m for m in models if m.startswith("nn_")]
    best = max(nets, key=lambda m: ov[m]["top8_excess_ann_pct"]) if nets else "ridge"
    n_oos = s["oos_months"]
    sd_m = mo[mo.model == "ridge"]["top8_excess"].std()
    se = float(sd_m / np.sqrt(n_oos) * 1200)
    turnover_note = (f' · {ov[best]["names_changed_per_month"]:.1f} names change / month ({ov[best]["turnover_oneway_pct_yr"]:.0f}% one-way / yr)'
                     if "names_changed_per_month" in ov[best] else "")
    k = kpis([
        (f'{ov[best]["top8_excess_ann_pct"]:+.1f}%', f"{MODEL_LABEL[best]}: out-of-sample basket excess per year ({rule_label.get(default_rule, default_rule).split(' (')[0]})",
         f'{s["oos_start"]} → {s["oos_end"]}, {n_oos} months never seen in training · t {ov[best]["top8_t"]:.1f} · hit {ov[best]["top8_hit_rate"]:.2f}{turnover_note}'),
        (f'{ov["ridge"]["top8_excess_ann_pct"]:+.1f}%', "ridge, same months, same rule", f't {ov["ridge"]["top8_t"]:.1f} · hit {ov["ridge"]["top8_hit_rate"]:.2f}'),
        (f'{pr[best]["minus_ridge_ann_pct"]:+.1f}%' if best in pr else "—", "net minus ridge, month by month", f't {pr[best]["t"]:.1f} · net ahead in {pr[best]["wins_frac"]*100:.0f}% of months' if best in pr else ""),
        (f'±{se:.1f}%', "noise on the whole out-of-sample figure", f"one standard error over {n_oos} months"),
    ])
    # chart A: cumulative OOS
    fig, ax = plt.subplots(figsize=(12, 4.6), facecolor="white")
    colr = {"ridge": "#2CA02C", "reference_REER_CS": "#FF7F0E", "nn_mse": "#1F77B4", "nn_soft_top8": "#9467BD"}
    for m in models:
        ser = mo[mo.model == m].set_index("date")["top8_excess"].sort_index()
        ax.plot(ser.index, ser.cumsum() * 100, color=colr.get(m, "#444"), lw=2.2 if m == best else 1.5, label=MODEL_LABEL[m])
    ax.axhline(0, color="#444", lw=0.8)
    ax.set_ylabel("cumulative out-of-sample excess, % (simple sum)")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    ax.set_title(f"Walk-forward: each year scored by a model that had seen only the years before it ({s['n_folds']} folds, expanding window)", fontsize=10.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    chartA = img(fig_to_b64(fig), "This is the only chart on the page where every point is a genuine forecast: nothing after a month was used to train the model that scored it.")
    # chart B: by year bars
    years = sorted(by["year"].unique())
    fig, ax = plt.subplots(figsize=(12, 4), facecolor="white")
    w = 0.8 / max(1, len(models))
    for j, m in enumerate(models):
        d = by[by.model == m].set_index("year").reindex(years)
        ax.bar(np.arange(len(years)) + (j - (len(models) - 1) / 2) * w, d["top8_excess_ann_pct"], width=w, color=colr.get(m, "#444"), label=SHORT.get(m, m).replace("\n", " "))
    ax.axhline(0, color="#444", lw=0.8)
    ax.set_xticks(range(len(years))); ax.set_xticklabels(years, fontsize=8.5)
    ax.set_ylabel("OOS top-8 excess, % per year")
    ax.legend(frameon=False, fontsize=8.5, ncol=len(models))
    ax.set_title("By calendar year", fontsize=10.5)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    chartB = img(fig_to_b64(fig), "Years above zero are years the basket beat the equal-weight average out of sample.")
    rows = []
    for rule_ in ([default_rule] + [r_ for r_ in ov_all if r_ != default_rule]):
        for m in models:
            if m not in ov_all[rule_]:
                continue
            a = ov_all[rule_][m]; p_ = pr_all[rule_]
            rows.append({"rule": rule_label.get(rule_, rule_), "model": MODEL_LABEL[m], "OOS excess %/yr": a["top8_excess_ann_pct"], "t": a["top8_t"],
                         "hit rate": a["top8_hit_rate"], "IR": a.get("info_ratio", np.nan), "names changed / month": a.get("names_changed_per_month", np.nan),
                         "max rel. DD %": a.get("max_rel_drawdown_pct", np.nan), "caught of true top 8": a["precision8"] * 8, "rank IC": a["rank_ic"],
                         "vs ridge %/yr": p_.get(m, {}).get("minus_ridge_ann_pct", np.nan), "t (vs ridge)": p_.get(m, {}).get("t", np.nan),
                         "L−S %/yr": a["ls_spread_ann_pct"]})
    tbl = table(pd.DataFrame(rows), {"OOS excess %/yr": "{:+.1f}", "t": "{:.2f}", "hit rate": "{:.2f}", "IR": "{:.2f}", "names changed / month": "{:.2f}",
                                     "max rel. DD %": "{:.1f}", "caught of true top 8": "{:.2f}", "rank IC": "{:.3f}", "vs ridge %/yr": "{:+.2f}",
                                     "t (vs ridge)": "{:.2f}", "L−S %/yr": "{:+.1f}"})
    # ── trading diagnostics: turnover, information ratio, drawdowns, per rule ──
    diag_html = ""
    try:
        pr_ = pd.read_parquet(run / "predictions_oos.parquet")
        pnl = pd.read_parquet(Path(s["panel"]), columns=["date", "country", "fwd_ret", "bench_ret"])
        pr_ = pr_.merge(pnl, on=["date", "country"])
        K = int(s["config"].get("k", 8))
        drows, under_series = [], {}
        rule_series = {}
        for rule_ in ([default_rule] + [r_ for r_ in ov_all if r_ != default_rule]):
            for m in models:
                mr = mo_all[(mo_all.rule == rule_) & (mo_all.model == m)].sort_values("date")
                if len(mr) and "basket_ret" in mr.columns:
                    bask = mr.set_index("date")["basket_ret"]; bench = mr.set_index("date")["bench_ret"]
                    changed = float(mr["names_changed"].iloc[1:].mean())
                else:  # older runs: rebuild the plain top-8 from the scores
                    d = pr_[pr_.model == m].sort_values(["date", "score"], ascending=[True, False])
                    top = d.groupby("date").head(K); hold = top.groupby("date")["country"].apply(set); dts = hold.index
                    changed = np.mean([len(hold[dts[i]] - hold[dts[i - 1]]) for i in range(1, len(dts))]) if len(dts) > 1 else np.nan
                    bask = top.groupby("date")["fwd_ret"].mean(); bench = top.groupby("date")["bench_ret"].first()
                rule_series[(rule_, m)] = (bask, bench, changed)
        for (rule_, m), (bask, bench, changed) in rule_series.items():
            exc = bask - bench
            wb, wbm = (1 + bask).cumprod(), (1 + bench).cumprod(); rel = wb / wbm
            def dd(wealth):
                peak = wealth.cummax(); dmin = (wealth / peak - 1)
                trough = dmin.idxmin(); pk = wealth.loc[:trough].idxmax()
                after = wealth.loc[trough:]; rec = after[after >= peak.loc[trough]].index.min()
                return float(dmin.min()), pk, trough, rec
            rd, rp, rt, rr = dd(rel); ad, ap, at, _ = dd(wb); bd, bp, bt, _ = dd(wbm)
            peak = rel.cummax(); under = (rel < peak); longest = 0; run_len = 0
            for u in under:
                run_len = run_len + 1 if u else 0; longest = max(longest, run_len)
            if rule_ == default_rule:
                under_series[m] = (rel / peak - 1) * 100
            yrs = len(wb) / 12
            drows.append({"rule": rule_label.get(rule_, rule_), "model": MODEL_LABEL[m], "names changed / month (of 8)": changed, "one-way turnover %/yr": changed / K * 1200,
                          "excess vol %/yr": exc.std() * np.sqrt(12) * 100, "information ratio": exc.mean() / exc.std() * np.sqrt(12),
                          "worst month %": exc.min() * 100, "max relative drawdown %": rd * 100,
                          "drawdown peak → trough": f"{rp:%Y-%m} → {rt:%Y-%m}" + ("" if pd.notna(rr) else " (not yet recovered)"),
                          "longest underwater (months)": longest, "basket CAGR %": (wb.iloc[-1] ** (1 / yrs) - 1) * 100,
                          "EW CAGR %": (wbm.iloc[-1] ** (1 / yrs) - 1) * 100, "basket max DD %": ad * 100, "EW max DD %": bd * 100})
        dtbl = table(pd.DataFrame(drows), {"names changed / month (of 8)": "{:.2f}", "one-way turnover %/yr": "{:.0f}", "excess vol %/yr": "{:.1f}",
                                           "information ratio": "{:.2f}", "worst month %": "{:+.1f}", "max relative drawdown %": "{:.1f}",
                                           "basket CAGR %": "{:.1f}", "EW CAGR %": "{:.1f}", "basket max DD %": "{:.1f}", "EW max DD %": "{:.1f}"})
        fig, ax = plt.subplots(figsize=(12, 3.6), facecolor="white")
        for m in [best, "ridge"]:
            if m in under_series:
                ax.fill_between(under_series[m].index, under_series[m].values, 0, color=colr.get(m, "#444"), alpha=0.25 if m == best else 0.15, lw=0)
                ax.plot(under_series[m].index, under_series[m].values, color=colr.get(m, "#444"), lw=1.2 if m == best else 0.9, label=MODEL_LABEL[m])
        ax.set_ylabel("below previous peak, % (basket ÷ EW)")
        ax.legend(frameon=False, fontsize=8.5, loc="lower left")
        ax.set_title(f"Underwater chart ({rule_label.get(default_rule, default_rule).split(' (')[0]}): how far the basket's wealth relative to the equal-weight average sits below its previous high", fontsize=10)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        under_img = img(fig_to_b64(fig), "Depth is the size of the relative drawdown; width is how long it took to get back. Absolute drawdowns (in the table) are dominated by 2008 for every long-only country basket.")
        diag_html = f"""<h4>Trading diagnostics</h4>
<p><em>Turnover</em> is how many of the eight names change at each monthly rebalance; <em>relative drawdown</em> is the fall in the basket's wealth divided by the
equal-weight average's wealth from its previous high — the drawdown of the <em>excess</em>, which is what the strategy is; the absolute columns show the basket and the
benchmark on their own. Gross of costs throughout: turnover is reported as information, not applied as a penalty.</p>
{dtbl}{under_img}"""
    except Exception as e:  # diagnostics are additive; never break the page
        diag_html = f'<div class="note pending">Trading diagnostics unavailable: {html.escape(str(e))}</div>'
    # ── hysteresis sweep (hysteresis.py writes into the walk run dir) ─────────
    if (run / "hysteresis_sweep.parquet").exists():
        hs = pd.read_parquet(run / "hysteresis_sweep.parquet")
        show_h = hs[hs.model.isin([best, "ridge"])].copy()
        show_h["model"] = show_h["model"].map(MODEL_LABEL)
        show_h = show_h.rename(columns={"buffer_M": "hold while ranked ≤ M", "names_changed_per_month": "names changed / month",
                                        "turnover_oneway_pct_yr": "one-way turnover %/yr", "excess_ann_pct": "OOS excess %/yr", "excess_t": "t",
                                        "info_ratio": "IR", "hit_rate": "hit", "max_rel_drawdown_pct": "max rel. DD %",
                                        "longest_underwater_months": "longest underwater (m)", "excess_ann_pct_2005_09": "2005–09 %/yr",
                                        "excess_ann_pct_2010_19": "2010–19 %/yr", "excess_ann_pct_2020_26": "2020–26 %/yr"})
        show_h = show_h[["model", "hold while ranked ≤ M", "names changed / month", "one-way turnover %/yr", "OOS excess %/yr", "t", "IR", "hit",
                         "max rel. DD %", "longest underwater (m)", "2005–09 %/yr", "2010–19 %/yr", "2020–26 %/yr"]]
        htbl = table(show_h, {"names changed / month": "{:.2f}", "one-way turnover %/yr": "{:.0f}", "OOS excess %/yr": "{:+.2f}", "t": "{:.2f}", "IR": "{:.2f}",
                              "hit": "{:.2f}", "max rel. DD %": "{:.1f}", "2005–09 %/yr": "{:+.1f}", "2010–19 %/yr": "{:+.1f}", "2020–26 %/yr": "{:+.1f}"})
        hb = hs[hs.model == best].sort_values("buffer_M")
        fig, ax = plt.subplots(figsize=(9, 3.6), facecolor="white")
        x = np.arange(len(hb))
        ax.bar(x, hb["excess_ann_pct"], width=0.55, color="#1F77B4", label="OOS excess, % per year (left)")
        ax.set_xticks(x); ax.set_xticklabels([f"M = {int(v)}" + (" (plain top-8)" if v == 8 else "") for v in hb["buffer_M"]], fontsize=9)
        ax.set_ylabel("OOS excess, % per year")
        for xi, (e, t) in enumerate(zip(hb["excess_ann_pct"], hb["excess_t"])):
            ax.text(xi, e + 0.08, f"t {t:.1f}", ha="center", fontsize=8, color="#333")
        ax2 = ax.twinx()
        ax2.plot(x, hb["turnover_oneway_pct_yr"], color="#D62728", marker="o", lw=1.6, label="one-way turnover, % per year (right)")
        ax2.set_ylabel("turnover, % per year", color="#D62728"); ax2.tick_params(axis="y", colors="#D62728")
        for a_ in (ax, ax2):
            for sp in ("top",):
                a_.spines[sp].set_visible(False)
        h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
        ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=8.5, loc="lower left")
        ax.set_title(f"{MODEL_LABEL[best]}: a rank buffer cuts turnover without costing excess", fontsize=10.5)
        hchart = img(fig_to_b64(fig), "Bars: out-of-sample excess over the equal-weight average for each buffer width (t-stat above each bar). Line: how often the basket turns over. "
                                      "The two axes carry different quantities and are labelled; this is a one-off exception to the one-axis rule because the trade-off is the point.")
        diag_html += f"""<h4>Hysteresis: hold a name until it drops out of the top M</h4>
<p>The model's scores are untouched. At each monthly rebalance a held name stays while the model still ranks it in the top M; only names that fall below M are
sold, each replaced by the best-ranked name not already held. M = 8 is the plain rule used everywhere else on this page. Applied to the genuinely out-of-sample
scores of the walk-forward.</p>{htbl}{hchart}"""
    pfs = pf.pivot(index="oos_start", columns="model", values="top8_excess_ann_pct")[[m for m in models if m in pf.model.values]]
    pfs.columns = [SHORT.get(m, m).replace("\n", " ") for m in pfs.columns]
    pfs = pfs.reset_index().rename(columns={"oos_start": "fold starts"})
    tbl2 = table(pfs, {c: "{:+.1f}" for c in pfs.columns if c != "fold starts"})
    cfg = s["config"]
    rule_para = (f'<div class="note"><div class="note-title">Basket rule</div><p>The headline figures use the project default since 7 October 2026: '
                 f'<strong>{html.escape(rule_label.get(default_rule, default_rule))}</strong>. A held name stays while the model still ranks it in the top '
                 f'{default_rule[8:] if default_rule.startswith("buffer_M") else "8"} of the universe; only names that fall below are replaced, by the best-ranked names not held. '
                 f'The plain rule — re-pick the top eight every month — is shown alongside in every table. Both are formed from the same out-of-sample scores; the '
                 f'random-split stages above use the plain rule because a path-dependent rule has no meaning on scattered months.</p></div>'
                 if rule_aware else "")
    body = f"""
<p class="lead">Everything before this section re-partitioned the same history at random, which tests whether a fitted relationship transfers to
other months of the <em>same</em> history. This section is the test that was deliberately left until the design settled: train on everything
before a cut-off, score the next twelve months, move the cut-off forward a year, repeat. The first cut-off is after {cfg["first_train_months"]} months
of history, so the out-of-sample record runs from {s["oos_start"]} to {s["oos_end"]} — {n_oos} months, {s["n_folds"]} folds, expanding window.
Models: ridge (penalty chosen inside each training window), the post-hill-climb net ({cfg["hidden"][0]}/{cfg["hidden"][1]}, {cfg["seeds"]} seeds
averaged, early-stopped inside the training window) on both objectives, and the single-factor reference.</p>
{rule_para}
{k}
{chartA}
{tbl}
{chartB}
{diag_html}
<h4>Each fold's twelve months</h4>
{tbl2}
{commentary_block(c, "stage8")}
<div class="files"><div class="files-title">Files</div>
{flink(run / "per_fold.xlsx", "per-fold / by-year / overall (xlsx)")} · {flink(run / "monthly_oos.parquet", "monthly OOS series")} ·
{flink(run / "by_year.parquet", "by year")} · {flink(run / "predictions_oos.parquet", "OOS scores per country")} · {flink(run / "summary.json")} ·
{flink(run / "run.log")} · {flink(EXP_DIR / "walk_forward.py", "script")}</div>"""
    return "done", body


# ── stage 9: design holdout ──────────────────────────────────────────────────
def stage9(c: dict) -> tuple[str, str]:
    hill = tagged_runs("hill").get("holdout")
    walks = tagged_runs("walk")
    w_hold, w_full = walks.get("holdout"), walks.get("holdout_fullhist")
    if hill is None and w_full is None:
        return "pending", '<div class="note pending">Not run yet.</div>'
    parts = []
    chosen = {}
    if hill is not None:
        hs = json.load(open(hill / "summary.json"))
        cfg = pd.read_parquet(hill / "configs.parquet")
        curve = pd.read_parquet(hill / "seed_curve.parquet")
        cr = curve[curve.split_type == "random"].groupby("n_seeds")["top8_excess_ann_pct"].agg(["mean", "std", "count"]).reset_index()
        cr = cr[cr.n_seeds > 0]
        best = cfg.iloc[0]
        chosen = {"config": best["config"], "hidden": best["hidden"], "dropout": float(best["dropout"]), "weight_decay": float(best["weight_decay"]),
                  "lr": float(best["lr"]), "eval": float(best["eval_top8_ann_pct"])}
        show = cfg[["config", "hidden", "dropout", "weight_decay", "lr", "eval_top8_ann_pct", "eval_sd_splits", "vs_base_pct", "vs_base_t", "wins_vs_base",
                    "blocked_top8_ann_pct", "train_top8_ann_pct"]].rename(columns={
            "weight_decay": "wd", "eval_top8_ann_pct": "first-half eval %/yr", "eval_sd_splits": "± splits", "vs_base_pct": "vs 64/32 base", "vs_base_t": "t",
            "wins_vs_base": "wins/30", "blocked_top8_ann_pct": "blocks %/yr", "train_top8_ann_pct": "train %/yr"})
        tbl = table(show, {"dropout": "{:.2f}", "wd": "{:.2f}", "lr": "{:.4f}", "first-half eval %/yr": "{:+.1f}", "± splits": "{:.1f}", "vs 64/32 base": "{:+.2f}",
                           "t": "{:.1f}", "blocks %/yr": "{:+.1f}", "train %/yr": "{:+.0f}"})
        fig, ax = plt.subplots(figsize=(8.5, 3.4), facecolor="white")
        ax.errorbar(cr["n_seeds"], cr["mean"], yerr=2 * cr["std"] / np.sqrt(cr["count"]), marker="o", color="#1F77B4", capsize=3)
        ax.set_xscale("log"); ax.set_xticks(cr["n_seeds"]); ax.set_xticklabels(cr["n_seeds"].astype(int))
        ax.set_xlabel("nets averaged (seeds)"); ax.set_ylabel("first-half eval top-8 excess, % per year")
        ax.set_title("Seed curve on the first half only", fontsize=10.5)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        curve_img = img(fig_to_b64(fig), "Where this flattens is the ensemble size chosen for the second-half test.")
        parts.append(f"""<h4>Step 1 — choose the design on the first half only (February 2000 to May 2013)</h4>
<p>The same sweep as stage 7, run on random splits drawn only from the first {hs["n_splits"]} splits' worth of the first-half months, on the cleaned panel: {hs["n_runs"]} nets.
The design is the top row.</p>{tbl}{curve_img}""")
    # second-half walk-forwards
    rows, charts = [], ""
    def wf_block(run, label):
        s = json.load(open(run / "summary.json")); dr = s["default_rule"]; ov = s["overall"][dr]; pr = s["paired_vs_ridge"][dr]
        out = []
        for m in ["nn_mse", "nn_soft_top8", "ridge"]:
            if m in ov:
                a = ov[m]
                out.append({"design": label, "model": MODEL_LABEL[m], "second-half OOS excess %/yr": a["top8_excess_ann_pct"], "t": a["top8_t"],
                            "hit rate": a["top8_hit_rate"], "IR": a.get("info_ratio", np.nan), "names changed / month": a.get("names_changed_per_month", np.nan),
                            "max rel. DD %": a.get("max_rel_drawdown_pct", np.nan), "vs ridge %/yr": pr.get(m, {}).get("minus_ridge_ann_pct", np.nan),
                            "t (vs ridge)": pr.get(m, {}).get("t", np.nan), "months": s["oos_months"], "rule": dr})
        return out, s
    series = {}
    if w_hold is not None:
        r_, s_h = wf_block(w_hold, "chosen on the first half"); rows += r_
        mo = pd.read_parquet(w_hold / "monthly_oos.parquet"); mo = mo[mo.rule == s_h["default_rule"]]
        series["holdout"] = (mo, s_h)
    if w_full is not None:
        r_, s_f = wf_block(w_full, "chosen on the full history (stage 7)"); rows += r_
        mo = pd.read_parquet(w_full / "monthly_oos.parquet"); mo = mo[mo.rule == s_f["default_rule"]]
        series["fullhist"] = (mo, s_f)
    if rows:
        rt = pd.DataFrame(rows)
        tbl2 = table(rt, {"second-half OOS excess %/yr": "{:+.1f}", "t": "{:.2f}", "hit rate": "{:.2f}", "IR": "{:.2f}", "names changed / month": "{:.2f}",
                          "max rel. DD %": "{:.1f}", "vs ridge %/yr": "{:+.2f}", "t (vs ridge)": "{:.2f}"})
        fig, ax = plt.subplots(figsize=(12, 4.4), facecolor="white")
        for key, colr, lab in (("holdout", "#1F77B4", "net, design chosen on the first half"), ("fullhist", "#9467BD", "net, design chosen on the full history")):
            if key in series:
                mo, _ = series[key]; ser = mo[mo.model == "nn_mse"].set_index("date")["top8_excess"].sort_index()
                ax.plot(ser.index, ser.cumsum() * 100, color=colr, lw=2.0, label=lab)
        key0 = "holdout" if "holdout" in series else "fullhist"
        mo, _ = series[key0]; ser = mo[mo.model == "ridge"].set_index("date")["top8_excess"].sort_index()
        ax.plot(ser.index, ser.cumsum() * 100, color="#2CA02C", lw=1.5, label="ridge")
        ax.axhline(0, color="#444", lw=0.8); ax.set_ylabel("cumulative OOS excess, % (simple sum)")
        ax.legend(frameon=False, fontsize=8.5, loc="upper left")
        ax.set_title("Second half of the history, out of sample for both the weights and (blue) the design", fontsize=10.5)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        charts = img(fig_to_b64(fig), "If the blue and purple lines track each other, choosing the design on the whole history did not flatter the result.")
        parts.append(f"""<h4>Step 2 — walk forward through the second half (June 2013 to September 2026)</h4>
<p>Expanding window from the first-half cut-off, twelve-month folds, the project's default basket rule chosen on first-half data. The purple comparison is the
stage-7 design, which was chosen with the second half in view.</p>{tbl2}{charts}""")
    chosen_txt = (f'<div class="note"><div class="note-title">Chosen on the first half</div><p>Network <strong>{chosen["hidden"]}</strong> hidden, dropout {chosen["dropout"]:.2f}, '
                  f'weight decay {chosen["weight_decay"]:.2f}, learning rate {chosen["lr"]:.4f} (config <code>{chosen["config"]}</code>), first-half random-split excess '
                  f'{chosen["eval"]:+.1f}% a year.</p></div>' if chosen else "")
    files = " · ".join(flink(p / "summary.json", f"{k} summary") for k, p in (("hill-climb", hill), ("holdout walk", w_hold), ("full-history-design walk", w_full)) if p is not None)
    body = f"""
<p class="lead">The walk-forward in stage 8 is out of sample for the weights the net learns each year, but its design — width, regularisation, learning rate,
ensemble size, basket rule — was chosen on random splits of the whole history, including the months later scored. This stage closes that gap: every design
choice is made on the first half of the history only, and the net then walks forward through the second half with nothing chosen on it. The full-history
design is walked over the same months for comparison.</p>
{chosen_txt}
{''.join(parts)}
{commentary_block(c, "stage9")}
<div class="files"><div class="files-title">Files</div>{files}</div>"""
    status = "done" if (w_hold is not None) else "running"
    return status, body


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
        ("stage5", "5 · The neural network", stage5),
        ("stage6", "6 · Ablations", stage6),
        ("stage7", "7 · Hill-climb", stage7),
        ("stage8", "8 · Walk-forward", stage8),
        ("stage9", "9 · Design holdout", stage9),
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
<div class="step"><b>5 · Neural net</b>Shared net, three objectives, same splits as the floor.</div>
<div class="step"><b>6 · Ablations</b>Rerun floor and net with inputs removed; what does the edge depend on?</div>
<div class="step"><b>7 · Hill-climb</b>Regularisation, width, learning rate, ensemble size — one at a time, paired.</div>
<div class="step"><b>8 · Walk-forward</b>Train on the past, score the next year, roll. The only genuine forecast test.</div>
<div class="step"><b>9 · Design holdout</b>Choose the design on the first half only; walk the second half blind.</div>
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
