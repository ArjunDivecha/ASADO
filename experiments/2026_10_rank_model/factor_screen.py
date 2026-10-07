#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/factor_screen.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/snapshot_2026_10_07/feature_panel_observed.parquet
    Frozen `feature_panel_observed` (34 T2 countries, forecasts excluded), tidy
    long (date, country, value, variable, source). Supplies both the factor
    z-scores (`_CS` / `_TS`) and the target: `1MRet` from source `t2`, which is
    the FORWARD one-month total return labeled at the window start (verified
    2026-10-07: 1MRet at date D == TotReturnIndex(D+1)/TotReturnIndex(D) - 1,
    correlation 1.000 over 320 months).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/cache/query_assistant/variable_catalog.json
    Variable metadata (source, frequency, base variable).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/corr_<latest>/factor_correlation_matrix.xlsx
    Sheet `Variables` of the latest factor_correlation.py run (newest corr_*
    directory by name): duplicate-group ids at |rho| >= 0.9 and 0.8, joined so
    each factor can be ranked within its group. Override with --corr-run.
- experiments/2026_10_rank_model/factor_correlation.py (imported for the
    shared variable-selection logic: load_variables).

OUTPUT FILES (inside
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/screen_<YYYYMMDD_HHMMSS>/ ):
- factor_screen.xlsx            sheets: Screen (one row per factor), Clusters_Ranked
                                (members of each duplicate group ranked by |t|), Notes
- factor_screen.parquet         the Screen table (canonical)
- monthly_top8_excess.parquet   date x variable: monthly excess return of the top-8
                                basket over the equal-weight average (harness lag)
- monthly_rank_ic.parquet       date x variable: monthly Spearman rank IC (harness lag)
- factor_screen_chart.pdf       t-stat histogram + top-40 bars (light mode)
- summary.json, run.log

VERSION: 1.0
LAST UPDATED: 2026-10-07
AUTHOR: Claude (Fable 5.1) for Arjun Divecha

DESCRIPTION:
Univariate screen of every monthly factor z-score against next month's country
return, as an aid to hand-picking the factor set for the top-8 ranking model.

For each factor and each month the cross-section of countries with both a
factor value and a forward return is scored four ways:
  1. Fama-MacBeth slope: OLS of next-month excess return on the z-score within
     the month; reported as the time-series mean (bp per month per 1 z) with a
     t-stat over months (non-overlapping monthly returns, so a plain t-stat).
  2. Spearman rank IC within the month; mean and t-stat.
  3. Top-8 basket: equal-weight mean next-month return of the 8 highest-scored
     countries minus the equal-weight average of ALL countries with a return
     that month (the real benchmark, not just the covered subset); annualized
     (x12), t-stat and hit rate. Bottom-8 and the top-minus-bottom spread too.
  4. The same at zero lag for every source, as a comparison column.

Alignment: factor at month D predicts 1MRet at month D + lag, where lag follows
the harness convention (scripts/harness/evaluate_signal.py infer_publication_lag):
0 for t2 and gdelt (knowable at month end), otherwise 1 month for monthly
series (3 / 12 for quarterly / annual, which are excluded here anyway).

Multiple comparisons: with ~340 factors and ~320 months, roughly 5% (~17) will
show |t| > 1.96 by chance. The sheet carries a two-sided p-value and a
Benjamini-Hochberg q-value across all factors.

This is an in-sample, full-history screen — Arjun's spec for this stage is
"forget out-of-sample"; it ranks factors, it does not validate them.

DEPENDENCIES: pandas, numpy, scipy, matplotlib, xlsxwriter, openpyxl, pyarrow (experiment .venv)

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model"
  .venv/bin/python factor_screen.py
  .venv/bin/python factor_screen.py --min-countries 20 --top-k 8

NOTES:
- Reads parquet/xlsx only; never opens asado.duckdb.
- Cells that cannot be computed (fewer than --min-months usable months) render
  as an em dash, never blank.
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sstats

EXP_DIR = Path(__file__).resolve().parent  # this script's own folder: works from the exp/NN worktree or the main checkout
sys.path.insert(0, str(EXP_DIR))
from factor_correlation import CATALOG, SNAPSHOT, load_variables  # noqa: E402

RESULTS_ROOT = EXP_DIR / "results"


def latest_run(prefix: str) -> Path:
    """Newest results/<prefix>_<timestamp>/ directory (timestamps sort lexically)."""
    runs = sorted(RESULTS_ROOT.glob(f"{prefix}_*"))
    if not runs:
        raise FileNotFoundError(f"no {prefix}_* run under {RESULTS_ROOT}")
    return runs[-1]

RETURN_VARIABLE = "1MRet"       # forward 1-month return, labeled at window start
RETURN_SOURCE = "t2"
ZERO_LAG_SOURCES = {"t2", "gdelt"}   # mirrors scripts/harness/evaluate_signal.py

log = logging.getLogger("factor_screen")


def setup_logging(run_dir: Path) -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    log.setLevel(logging.INFO)
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler(run_dir / "run.log")):
        h.setFormatter(fmt)
        log.addHandler(h)


def publication_lag_months(dates: pd.Series, countries: pd.Series, source: str) -> int:
    """Harness convention: 0 for market/news sources knowable at month end, else by native gap."""
    if source in ZERO_LAG_SOURCES:
        return 0
    g = pd.DataFrame({"country": countries, "date": dates}).sort_values(["country", "date"])
    gaps = g.groupby("country")["date"].diff().dt.days.dropna()
    med = float(gaps.median()) if len(gaps) else 31.0
    return 1 if med <= 45 else (3 if med <= 135 else 12)


def tstat(x: pd.Series) -> float:
    x = x.dropna()
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) >= 2 and x.std(ddof=1) > 0 else np.nan


def row_pearson(a: pd.DataFrame, b: pd.DataFrame) -> pd.Series:
    """Row-wise Pearson correlation of two aligned wide frames (NaN-aware, same mask)."""
    m = a.notna() & b.notna()
    a, b = a.where(m), b.where(m)
    n = m.sum(axis=1)
    am, bm = a.sub(a.mean(axis=1), axis=0), b.sub(b.mean(axis=1), axis=0)
    cov = (am * bm).sum(axis=1)
    return cov / np.sqrt((am ** 2).sum(axis=1) * (bm ** 2).sum(axis=1))


def row_slope(z: pd.DataFrame, e: pd.DataFrame) -> pd.Series:
    """Row-wise OLS slope of e on z (with intercept), NaN-aware."""
    m = z.notna() & e.notna()
    z, e = z.where(m), e.where(m)
    zm, em = z.sub(z.mean(axis=1), axis=0), e.sub(e.mean(axis=1), axis=0)
    return (zm * em).sum(axis=1) / (zm ** 2).sum(axis=1)


def screen_one(Z: pd.DataFrame, E: pd.DataFrame, lag: int, top_k: int, min_countries: int) -> dict:
    """Score one factor. Z, E are date x country on the same full monthly index.

    E is next-month return minus that month's all-country equal-weight average.
    Factor at date D is paired with E at D + lag months (row shift on a complete
    month-start index).
    """
    E_l = E.shift(-lag) if lag else E
    mask = Z.notna() & E_l.notna()
    n = mask.sum(axis=1)
    ok = n >= min_countries
    # need real cross-sectional variation in the factor
    ok &= Z.where(mask).nunique(axis=1) >= 3
    Zm, Em = Z.where(mask)[ok], E_l.where(mask)[ok]
    if len(Zm) == 0:
        return {"n_months": 0}

    slope = row_slope(Zm, Em)
    ic = row_pearson(Zm.rank(axis=1), Em.rank(axis=1))
    # top/bottom-k by factor score, ties broken by column order (stable)
    rk = Zm.rank(axis=1, ascending=False, method="first")
    top = Em.where(rk <= top_k).mean(axis=1)
    bot = Em.where(rk.gt(n[ok] - top_k, axis=0)).mean(axis=1)
    ls = top - bot

    return {
        "n_months": int(len(Zm)),
        "first_month": Zm.index.min().strftime("%Y-%m"),
        "last_month": Zm.index.max().strftime("%Y-%m"),
        "mean_n_countries": float(n[ok].mean()),
        "fm_slope_bp": float(slope.mean() * 1e4),
        "fm_t": tstat(slope),
        "rank_ic_mean": float(ic.mean()),
        "rank_ic_t": tstat(ic),
        "top8_excess_ann_pct": float(top.mean() * 12 * 100),
        "top8_t": tstat(top),
        "top8_hit_rate": float((top > 0).mean()),
        "bottom8_excess_ann_pct": float(bot.mean() * 12 * 100),
        "ls_spread_ann_pct": float(ls.mean() * 12 * 100),
        "ls_t": tstat(ls),
        "_top_series": top,
        "_ic_series": ic,
    }


def bh_qvalues(p: pd.Series) -> pd.Series:
    """Benjamini-Hochberg q-values; NaN p stays NaN."""
    q = pd.Series(np.nan, index=p.index)
    valid = p.dropna().sort_values()
    m = len(valid)
    if m == 0:
        return q
    ranked = valid.values * m / np.arange(1, m + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    q.loc[valid.index] = np.minimum(ranked, 1.0)
    return q


def write_chart(path: Path, screen: pd.DataFrame, top_n: int, expected_by_chance: float) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ok = screen.dropna(subset=["fm_t"])
    sources = sorted(ok["source"].unique())
    palette = ["#1F77B4", "#D62728", "#2CA02C", "#9467BD", "#FF7F0E", "#8C564B",
               "#E377C2", "#17BECF", "#BCBD22", "#7F7F7F", "#AEC7E8", "#FFBB78",
               "#98DF8A", "#FF9896", "#C5B0D5", "#C49C94", "#F7B6D2", "#DBDB8D", "#9EDAE5"]
    src_color = {s: palette[i % len(palette)] for i, s in enumerate(sources)}

    fig = plt.figure(figsize=(17, 11), facecolor="white")
    gs = fig.add_gridspec(1, 2, width_ratios=[1, 1.4], wspace=0.35)

    ax0 = fig.add_subplot(gs[0, 0])
    ax0.hist(ok["fm_t"], bins=40, color="#1F77B4", alpha=0.85, edgecolor="white")
    for x in (-1.96, 1.96):
        ax0.axvline(x, color="#D62728", linestyle="--", linewidth=1)
    n_sig = int((ok["fm_t"].abs() > 1.96).sum())
    ax0.set_title(f"Fama-MacBeth t-stat, {len(ok)} factors\n"
                  f"{n_sig} beyond ±1.96 (about {expected_by_chance:.0f} expected by chance)", fontsize=11)
    ax0.set_xlabel("t-stat of mean monthly slope (next-month excess return on z-score)")
    ax0.set_ylabel("factors")
    for s in ("top", "right"):
        ax0.spines[s].set_visible(False)

    ax1 = fig.add_subplot(gs[0, 1])
    top = ok.reindex(ok["fm_t"].abs().sort_values(ascending=False).index).head(top_n).iloc[::-1]
    colors = [src_color[s] for s in top["source"]]
    ax1.barh(range(len(top)), top["fm_t"], color=colors, height=0.75)
    ax1.set_yticks(range(len(top)))
    ax1.set_yticklabels(top["variable"], fontsize=7)
    ax1.axvline(0, color="#444444", linewidth=0.8)
    for x in (-1.96, 1.96):
        ax1.axvline(x, color="#D62728", linestyle="--", linewidth=0.8)
    ax1.set_xlabel("Fama-MacBeth t-stat (sign = direction; T2 lower-is-better factors already flipped)")
    ax1.set_title(f"Top {top_n} factors by |t|", fontsize=11)
    for s in ("top", "right"):
        ax1.spines[s].set_visible(False)
    handles = [plt.Line2D([], [], marker="s", linestyle="", color=src_color[s], label=s) for s in sources]
    ax1.legend(handles=handles, loc="lower right", fontsize=7, frameon=False, title="source", title_fontsize=8)

    fig.suptitle("Univariate factor screen vs next-month country return — 34 countries, harness publication lag",
                 fontsize=13, y=0.98)
    fig.savefig(path, format="pdf", facecolor="white", bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    ap.add_argument("--catalog", type=Path, default=CATALOG)
    ap.add_argument("--corr-run", type=Path, default=None,
                    help="factor_correlation_matrix.xlsx whose Variables sheet supplies cluster ids "
                         "(default: newest results/corr_*/)")
    ap.add_argument("--top-k", type=int, default=8)
    ap.add_argument("--min-countries", type=int, default=20,
                    help="countries needed in a month for that month to count (default 20)")
    ap.add_argument("--min-months", type=int, default=24,
                    help="months needed for a factor's statistics to be reported (default 24)")
    ap.add_argument("--chart-top-n", type=int, default=40)
    args = ap.parse_args()
    if args.corr_run is None:
        args.corr_run = latest_run("corr") / "factor_correlation_matrix.xlsx"

    t0 = time.time()
    run_dir = RESULTS_ROOT / f"screen_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    run_dir.mkdir(parents=True, exist_ok=False)
    setup_logging(run_dir)
    log.info("run dir: %s", run_dir)

    # ── factors (same selection as the correlation run) ─────────────────────
    kept, var_table = load_variables(args.snapshot, args.catalog)
    inc = var_table[var_table["status"] == "included"].set_index("variable")

    # ── target: forward 1-month return, all-country equal-weight benchmark ──
    df = pd.read_parquet(args.snapshot, columns=["date", "country", "value", "variable", "source"])
    df["date"] = pd.to_datetime(df["date"])
    ret = df[(df["variable"] == RETURN_VARIABLE) & (df["source"] == RETURN_SOURCE)]
    R = ret.pivot_table(index="date", columns="country", values="value").sort_index()
    full_idx = pd.date_range(R.index.min(), kept["date"].max(), freq="MS")
    R = R.reindex(full_idx)
    bench = R.mean(axis=1)
    E = R.sub(bench, axis=0)
    log.info("returns: %d months %s -> %s, %.1f countries/month; benchmark = EW mean of available countries",
             int(R.notna().any(axis=1).sum()), R.index.min().date(), R.index.max().date(),
             float(R.notna().sum(axis=1)[R.notna().any(axis=1)].mean()))

    # ── screen every factor at harness lag and at zero lag ─────────────────
    rows, top_series, ic_series = [], {}, {}
    for i, (v, g) in enumerate(kept.groupby("variable"), 1):
        src = inc.loc[v, "source"]
        lag = publication_lag_months(g["date"], g["country"], src)
        Z = g.pivot_table(index="date", columns="country", values="value").reindex(full_idx)
        Z = Z.reindex(columns=R.columns)
        res = screen_one(Z, E, lag, args.top_k, args.min_countries)
        res0 = screen_one(Z, E, 0, args.top_k, args.min_countries) if lag else res
        row = {"variable": v, "base_variable": inc.loc[v, "base_variable"],
               "normalization": inc.loc[v, "normalization"], "source": src, "lag_months": lag}
        row.update({k: val for k, val in res.items() if not k.startswith("_")})
        row["fm_t_lag0"] = res0.get("fm_t", np.nan)
        row["rank_ic_t_lag0"] = res0.get("rank_ic_t", np.nan)
        row["top8_excess_ann_pct_lag0"] = res0.get("top8_excess_ann_pct", np.nan)
        rows.append(row)
        if "_top_series" in res:
            top_series[v] = res["_top_series"]
            ic_series[v] = res["_ic_series"]
        if i % 50 == 0:
            log.info("  screened %d/%d", i, kept["variable"].nunique())

    screen = pd.DataFrame(rows)
    stat_cols = ["mean_n_countries", "fm_slope_bp", "fm_t", "rank_ic_mean", "rank_ic_t",
                 "top8_excess_ann_pct", "top8_t", "top8_hit_rate", "bottom8_excess_ann_pct",
                 "ls_spread_ann_pct", "ls_t", "fm_t_lag0", "rank_ic_t_lag0", "top8_excess_ann_pct_lag0"]
    thin = screen["n_months"] < args.min_months
    screen.loc[thin, stat_cols] = np.nan
    log.info("factors screened: %d; with >= %d usable months: %d", len(screen), args.min_months, int((~thin).sum()))

    screen["fm_p"] = 2 * sstats.t.sf(screen["fm_t"].abs(), df=screen["n_months"] - 1)
    screen["fm_q_bh"] = bh_qvalues(screen["fm_p"])
    screen["abs_fm_t"] = screen["fm_t"].abs()

    # ── join duplicate-group ids from the correlation run ─────────────────
    cl_cols = []
    if args.corr_run.exists():
        vt = pd.read_excel(args.corr_run, sheet_name="Variables")
        cl_cols = [c for c in vt.columns if c.startswith("cluster_abs_rho_ge_")]
        screen = screen.merge(vt[["variable"] + cl_cols], on="variable", how="left")
        log.info("joined cluster ids from %s", args.corr_run)
    else:
        log.warning("correlation run not found: %s (no cluster columns)", args.corr_run)

    screen = screen.sort_values("abs_fm_t", ascending=False, na_position="last").reset_index(drop=True)
    screen.insert(0, "rank_by_abs_t", np.arange(1, len(screen) + 1))

    # per-group ranking at the 0.80 cut
    ranked = pd.DataFrame()
    if cl_cols:
        col80 = next((c for c in cl_cols if c.endswith("0.80")), cl_cols[-1])
        screen["rank_in_cluster_080"] = screen.groupby(col80)["abs_fm_t"].rank(ascending=False, method="first")
        sizes = screen.groupby(col80)["variable"].transform("size")
        screen["cluster_080_size"] = sizes
        multi = screen[sizes > 1].copy()
        multi = multi.sort_values([col80, "abs_fm_t"], ascending=[True, False])
        ranked = multi[["variable", "normalization", "source", col80, "cluster_080_size", "rank_in_cluster_080",
                        "n_months", "fm_slope_bp", "fm_t", "rank_ic_t", "top8_excess_ann_pct", "top8_t",
                        "top8_hit_rate", "ls_spread_ann_pct"]]
        log.info("duplicate groups at 0.80 with >1 member: %d", int(multi[col80].nunique()))

    # ── write outputs ──────────────────────────────────────────────────────
    expected = 0.05 * int(screen["fm_t"].notna().sum())
    n_sig = int((screen["fm_t"].abs() > 1.96).sum())
    n_q10 = int((screen["fm_q_bh"] < 0.10).sum())
    log.info("|t| > 1.96: %d of %d (about %.0f expected by chance); BH q < 0.10: %d",
             n_sig, int(screen["fm_t"].notna().sum()), expected, n_q10)

    p_parq = run_dir / "factor_screen.parquet"
    p_xlsx = run_dir / "factor_screen.xlsx"
    p_pdf = run_dir / "factor_screen_chart.pdf"
    p_top = run_dir / "monthly_top8_excess.parquet"
    p_ic = run_dir / "monthly_rank_ic.parquet"

    screen.to_parquet(p_parq)
    pd.DataFrame(top_series).sort_index().to_parquet(p_top)
    pd.DataFrame(ic_series).sort_index().to_parquet(p_ic)

    notes = pd.DataFrame({"note": [
        f"Target: {RETURN_VARIABLE} (source {RETURN_SOURCE}) = forward 1-month total return labeled at window start; "
        f"factor at month D is paired with the return over the month after D + lag.",
        "Lag (months): 0 for t2 and gdelt; 1 for other monthly sources (harness convention, "
        "scripts/harness/evaluate_signal.py infer_publication_lag). *_lag0 columns use lag 0 for every source.",
        "Excess return = country next-month return minus the equal-weight average of ALL countries with a return that month.",
        f"A month counts only if >= {args.min_countries} countries have both a factor value and a forward return; "
        f"a factor reports statistics only with >= {args.min_months} such months (otherwise — ).",
        "fm_slope_bp: mean monthly OLS slope of excess return on the z-score, in bp per 1 z. fm_t: t-stat of that mean over months.",
        "rank_ic: within-month Spearman between z-score and next-month return.",
        f"top8_excess_ann_pct: mean monthly excess return of the equal-weight top-{args.top_k} basket by z-score, x12, in %. "
        f"bottom8 likewise for the lowest {args.top_k}; ls_spread = top minus bottom.",
        "Sign: T2 lower-is-better factors (PE, PBK, Debt/GDP, RSI14, 1MTR, 3MTR, ...) are already sign-flipped upstream, "
        "so a positive t means the T2 convention direction works. Other sources are unflipped; a negative t means invert.",
        f"Multiple comparisons: {int(screen['fm_t'].notna().sum())} factors tested; about {expected:.0f} expected beyond |t| 1.96 "
        f"by chance; {n_sig} observed; {n_q10} survive Benjamini-Hochberg q < 0.10. In-sample, full history.",
        "cluster_abs_rho_ge_* : duplicate-group ids from the correlation run; rank_in_cluster_080 ranks members by |fm_t|.",
    ]})

    with pd.ExcelWriter(p_xlsx, engine="xlsxwriter") as xw:
        wb = xw.book
        screen.to_excel(xw, sheet_name="Screen", index=False, na_rep="—")
        ws = xw.sheets["Screen"]
        f2 = wb.add_format({"num_format": "0.00"})
        f1 = wb.add_format({"num_format": "0.0"})
        f3 = wb.add_format({"num_format": "0.000"})
        cols = list(screen.columns)
        ws.set_column(cols.index("variable"), cols.index("variable"), 34)
        ws.set_column(cols.index("base_variable"), cols.index("base_variable"), 28)
        for c, fmt in [("mean_n_countries", f1), ("fm_slope_bp", f1), ("fm_t", f2), ("rank_ic_mean", f3),
                       ("rank_ic_t", f2), ("top8_excess_ann_pct", f1), ("top8_t", f2), ("top8_hit_rate", f2),
                       ("bottom8_excess_ann_pct", f1), ("ls_spread_ann_pct", f1), ("ls_t", f2),
                       ("fm_t_lag0", f2), ("rank_ic_t_lag0", f2), ("top8_excess_ann_pct_lag0", f1),
                       ("fm_p", f3), ("fm_q_bh", f3), ("abs_fm_t", f2)]:
            j = cols.index(c)
            ws.set_column(j, j, 11, fmt)
        ws.freeze_panes(1, 2)
        ws.autofilter(0, 0, len(screen), len(cols) - 1)
        j = cols.index("fm_t")
        ws.conditional_format(1, j, len(screen), j, {
            "type": "3_color_scale", "min_type": "num", "min_value": -4, "min_color": "#2166AC",
            "mid_type": "num", "mid_value": 0, "mid_color": "#FFFFFF",
            "max_type": "num", "max_value": 4, "max_color": "#B2182B"})
        if len(ranked):
            ranked.to_excel(xw, sheet_name="Clusters_Ranked", index=False, na_rep="—")
            ws2 = xw.sheets["Clusters_Ranked"]
            ws2.set_column(0, 0, 34)
            ws2.set_column(1, 13, 12)
            ws2.freeze_panes(1, 1)
            ws2.autofilter(0, 0, len(ranked), len(ranked.columns) - 1)
        notes.to_excel(xw, sheet_name="Notes", index=False)
        xw.sheets["Notes"].set_column(0, 0, 160)

    write_chart(p_pdf, screen, args.chart_top_n, expected)

    summary = {
        "run_dir": str(run_dir), "snapshot": str(args.snapshot), "corr_run": str(args.corr_run),
        "target": f"{RETURN_VARIABLE} ({RETURN_SOURCE})", "top_k": args.top_k,
        "min_countries": args.min_countries, "min_months": args.min_months,
        "n_factors": int(len(screen)), "n_factors_reported": int(screen["fm_t"].notna().sum()),
        "n_abs_t_gt_1_96": n_sig, "expected_by_chance": round(expected, 1), "n_bh_q_lt_0_10": n_q10,
        "top10_by_abs_t": screen.head(10)[["variable", "fm_t", "top8_excess_ann_pct", "lag_months"]].to_dict("records"),
        "outputs": [str(p) for p in (p_parq, p_xlsx, p_pdf, p_top, p_ic)],
        "elapsed_s": round(time.time() - t0, 1),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    log.info("wrote %s", p_xlsx)
    log.info("wrote %s", p_pdf)
    log.info("done in %.1fs", time.time() - t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
