#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/gdelt_veto/veto_test.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/walk_*_default_s*/predictions_oos.parquet
    Out-of-sample scores (date, country, score, fwd_excess, model) from the three
    independent default-model draws. Model "nn_mse" is the default.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/default_20261007_155223/monthly.parquet
    The saved default run; used only to check that the reconstructed basket matches it.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v3_clean/feature_panel_v3_clean.parquet
    fwd_ret / bench_ret / fwd_excess per (date, country).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/GDELT/data/panels/country_signal_daily.parquet
    Live nightly GDELT store: daily n_articles, tone_mean, tone_dispersion,
    country_news_risk_raw per country (primary news source).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/GDELT/Deep/data/features/country_signal_daily_deep.parquet
    Retired deep file (to 2026-04): theme shares, gcam_lm_uncertainty_mean,
    event_goldstein_mean, event_root_protest_n (exploratory arm; skipped with --no-deep).

OUTPUT FILES (in /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/gdelt_veto_<YYYYMMDD_HHMMSS>/):
- shocks.parquet        per (date, country, window, component): shock z-score (matched and stale)
- holdings.parquet      per (date, country): pooled score, rank, held flag, fwd_excess
- monthly.parquet       per (arm, window, component, date): flagged country, flagged minus others, swap gain
- arms.parquet / arms.xlsx   one row per arm × window × component: mean diff, t, n, Spearman, swap gain, etc.
- shuffle_null.parquet  the 500 shuffled-control t-statistics for the primary
- summary.json          decision, primary numbers, controls, power, correctness check
- charts.pdf            cumulative flagged-minus-others, shuffled null vs matched, per-window bars
- report.html           self-contained light-mode report of everything above
- run.log

VERSION: 1.0
LAST UPDATED: 2026-10-07
AUTHOR: Claude for Arjun Divecha

DESCRIPTION:
Pre-registered test (see PREREG.md beside this script) of whether a GDELT news
shock in the w days before rebalance identifies which of the default model's
eight holdings will lag the other seven next month. Primary: composite shock,
w = 14, flag the most-shocked holding, flagged minus others (%/month), t.
Controls: stale news (three months earlier) and 500 country-shuffled
permutations. Decision rule fixed in PREREG.md. Gross returns; nothing is
retrained. Within-month differences are non-overlapping, so plain t.

DEPENDENCIES: pandas, numpy, pyarrow, scipy, matplotlib, xlsxwriter (experiment .venv)

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model"
  .venv/bin/python gdelt_veto/veto_test.py                       # full run
  .venv/bin/python gdelt_veto/veto_test.py --max-month 2018-02-01 --n-shuffle 50 --tag smoke
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
from scipy import stats as sps

EXP_DIR = Path(__file__).resolve().parent.parent  # experiments/2026_10_rank_model
sys.path.insert(0, str(EXP_DIR))
from hysteresis import DEFAULT_BUFFER  # noqa: E402

RESULTS = EXP_DIR / "results"
PANEL = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v3_clean/feature_panel_v3_clean.parquet")
LIVE = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/GDELT/data/panels/country_signal_daily.parquet")
DEEP = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/GDELT/Deep/data/features/country_signal_daily_deep.parquet")
DEFAULT_RUN = RESULTS / "default_20261007_155223" / "monthly.parquet"

# bucket -> ISO3, copied from A Working/GDELT/scripts/build_country_return_panel.py PRICE_BUCKETS
BUCKET_ISO = {
    "Singapore": "SGP", "Australia": "AUS", "Canada": "CAN", "Germany": "DEU", "Japan": "JPN",
    "Switzerland": "CHE", "U.K.": "GBR", "NASDAQ": "USA", "U.S.": "USA", "France": "FRA",
    "Netherlands": "NLD", "Sweden": "SWE", "Italy": "ITA", "ChinaA": "CHN", "Chile": "CHL",
    "Indonesia": "IDN", "Philippines": "PHL", "Poland": "POL", "US SmallCap": "USA", "Malaysia": "MYS",
    "Taiwan": "TWN", "Mexico": "MEX", "Korea": "KOR", "Brazil": "BRA", "South Africa": "ZAF",
    "Denmark": "DNK", "India": "IND", "ChinaH": "CHN", "Hong Kong": "HKG", "Thailand": "THA",
    "Turkey": "TUR", "Spain": "ESP", "Vietnam": "VNM", "Saudi Arabia": "SAU",
}
K, M = 8, DEFAULT_BUFFER
WINDOWS = (7, 14, 30)
PRIMARY_W, PRIMARY_COMP = 14, "composite"
BASELINE_DAYS, STALE_SHIFT = 365, 90
FIRST_MONTH = pd.Timestamp("2016-03-01")
# live-store components: column -> sign (+1 = higher is worse news)
LIVE_COMPONENTS = {"attention": ("n_articles", +1), "tone": ("tone_mean", -1),
                   "dispersion": ("tone_dispersion", +1), "risk": ("country_news_risk_raw", +1)}
DEEP_COMPONENTS = {"uncertainty": ("gcam_lm_uncertainty_mean", +1), "goldstein": ("event_goldstein_mean", -1),
                   "protest": ("event_root_protest_n", +1)}

log = logging.getLogger("veto")


def tstat(x) -> float:
    x = pd.Series(x).dropna()
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 and x.std(ddof=1) > 0 else float("nan")


# --------------------------------------------------------------------------------------- holdings
def load_scores() -> tuple[pd.DataFrame, list[str]]:
    runs = sorted(p for p in RESULTS.glob("walk_*_default_s*") if (p / "predictions_oos.parquet").exists())
    if len(runs) < 1:
        raise FileNotFoundError("no default draws found")
    frames = []
    for p in runs:
        d = pd.read_parquet(p / "predictions_oos.parquet")
        d = d[d["model"] == "nn_mse"][["date", "country", "score"]].rename(columns={"score": p.name})
        frames.append(d.set_index(["date", "country"]))
    sc = pd.concat(frames, axis=1)
    draws = [p.name for p in runs]
    sc["pooled"] = sc[draws].mean(axis=1)
    sc = sc.reset_index()
    sc["date"] = pd.to_datetime(sc["date"])
    return sc, draws


def holdings_for(sc: pd.DataFrame, col: str, panel: pd.DataFrame) -> pd.DataFrame:
    """Reproduce hysteresis.build_baskets (k=K, m=M) but return per-(date,country) rows with held flag."""
    d = sc[["date", "country", col]].rename(columns={col: "score"}).merge(
        panel[["date", "country", "fwd_ret", "bench_ret", "fwd_excess"]], on=["date", "country"], how="inner")
    d = d.dropna(subset=["score"])
    out, held = [], set()
    for dt, g in d.sort_values(["date", "score"], ascending=[True, False]).groupby("date", sort=True):
        ranked = list(g["country"])
        rank_of = {c: i + 1 for i, c in enumerate(ranked)}
        keep = [c for c in ranked if c in held and rank_of[c] <= M]
        fill = [c for c in ranked if c not in held][: max(0, K - len(keep))]
        new = set(keep[:K] + fill)
        held = new
        g = g.assign(rank=g["country"].map(rank_of), held=g["country"].isin(new))
        out.append(g)
    return pd.concat(out, ignore_index=True)


# ---------------------------------------------------------------------------------------- shocks
def shock_table(daily: pd.DataFrame, components: dict[str, tuple[str, int]], windows=WINDOWS,
                stale_shift: int = STALE_SHIFT) -> pd.DataFrame:
    """daily: (date, iso3, <cols>). Returns rows (date=rebalance D, iso3, window, component, z, z_stale)
    for every first-of-month D. The w-day window ends the day before D; the baseline is the trailing
    365 days of rolling means ending at D - w."""
    cal = pd.date_range(daily["date"].min(), daily["date"].max(), freq="D")
    rebal = pd.date_range(FIRST_MONTH, cal[-1] + pd.Timedelta(days=1), freq="MS")
    rows = []
    for iso, g in daily.groupby("iso3"):
        g = g.set_index("date").reindex(cal)
        for comp, (col, sign) in components.items():
            s = g[col].astype(float)
            if comp == "attention":
                s = np.log1p(s)
            s = s * sign
            for w in windows:
                rm = s.rolling(w, min_periods=max(2, w // 2)).mean()
                base_mu = rm.shift(w).rolling(BASELINE_DAYS, min_periods=BASELINE_DAYS // 2).mean()
                base_sd = rm.shift(w).rolling(BASELINE_DAYS, min_periods=BASELINE_DAYS // 2).std(ddof=1)
                z = (rm - base_mu) / base_sd.replace(0, np.nan)
                # value "at D" uses the window ending D-1 -> index D-1
                idx = rebal - pd.Timedelta(days=1)
                idx_st = idx - pd.Timedelta(days=stale_shift)
                zz = z.reindex(idx).to_numpy()
                zs = z.reindex(idx_st).to_numpy()
                rows.append(pd.DataFrame({"date": rebal, "iso3": iso, "window": w, "component": comp, "z": zz, "z_stale": zs}))
    t = pd.concat(rows, ignore_index=True)
    return t


def theme_surge(deep: pd.DataFrame, windows=WINDOWS, thresh: float = 3.0) -> pd.DataFrame:
    """Exploratory: count of theme shares whose w-day rolling mean z (vs trailing year) exceeds thresh."""
    theme_cols = [c for c in deep.columns if c.startswith("theme_") and c.endswith("_share")]
    cal = pd.date_range(deep["date"].min(), deep["date"].max(), freq="D")
    rebal = pd.date_range(FIRST_MONTH, cal[-1] + pd.Timedelta(days=1), freq="MS")
    idx = rebal - pd.Timedelta(days=1)
    idx_st = idx - pd.Timedelta(days=STALE_SHIFT)
    rows = []
    for iso, g in deep.groupby("iso3"):
        X = g.set_index("date")[theme_cols].astype(float).reindex(cal)
        for w in windows:
            rm = X.rolling(w, min_periods=max(2, w // 2)).mean()
            sh = rm.shift(w)
            mu = sh.rolling(BASELINE_DAYS, min_periods=BASELINE_DAYS // 2).mean()
            sd = sh.rolling(BASELINE_DAYS, min_periods=BASELINE_DAYS // 2).std(ddof=1)
            z = (rm - mu) / sd.replace(0, np.nan)
            cnt = (z > thresh).sum(axis=1).where(z.notna().sum(axis=1) > 0)
            rows.append(pd.DataFrame({"date": rebal, "iso3": iso, "window": w, "component": "theme_surge",
                                      "z": cnt.reindex(idx).to_numpy(), "z_stale": cnt.reindex(idx_st).to_numpy()}))
    return pd.concat(rows, ignore_index=True)


def add_composite(sh: pd.DataFrame, comps: list[str], name: str = "composite") -> pd.DataFrame:
    c = sh[sh["component"].isin(comps)].groupby(["date", "iso3", "window"], as_index=False)[["z", "z_stale"]].mean()
    c["component"] = name
    return pd.concat([sh, c], ignore_index=True)


# -------------------------------------------------------------------------------------- the test
def month_stats(H: pd.DataFrame, shock: pd.Series, gate: float | None = None) -> dict | None:
    """H: one month's 34 rows (country, score, rank, held, fwd_excess). shock: country -> z.
    Returns the flagged holding's excess minus the others', and the swap gain."""
    held = H[H["held"]].copy()
    held["shock"] = held["country"].map(shock)
    held = held.dropna(subset=["shock"])
    if len(held) < 4:
        return None
    f = held.sort_values("shock", ascending=False).iloc[0]
    if gate is not None and f["shock"] < gate:
        return {"flagged": None, "diff": np.nan, "swap_gain": np.nan, "spearman": np.nan, "n_held": len(held)}
    others = held[held["country"] != f["country"]]["fwd_excess"].mean()
    diff = f["fwd_excess"] - others
    best_out = H[~H["held"]].sort_values("score", ascending=False).iloc[0]
    swap_gain = (best_out["fwd_excess"] - f["fwd_excess"]) / K   # change in the 8-name basket's excess
    rho = sps.spearmanr(held["shock"], held["fwd_excess"]).statistic if len(held) >= 5 else np.nan
    return {"flagged": f["country"], "flag_shock": float(f["shock"]), "diff": float(diff),
            "swap_gain": float(swap_gain), "spearman": float(rho), "n_held": int(len(held))}


def run_arm(hold: pd.DataFrame, sh: pd.DataFrame, window: int, component: str, use_stale: bool = False,
            gate: float | None = None, perm_map: dict | None = None) -> pd.DataFrame:
    """One arm: per-month statistics. perm_map: date -> {iso3: iso3'} for shuffled control."""
    s = sh[(sh["window"] == window) & (sh["component"] == component)]
    col = "z_stale" if use_stale else "z"
    rows = []
    for dt, H in hold.groupby("date", sort=True):
        z = s[s["date"] == dt].set_index("iso3")[col]
        if perm_map is not None:
            z = z.rename(index=perm_map[dt])
        shock = H["country"].map(lambda c: z.get(BUCKET_ISO[c], np.nan))
        shock.index = H["country"].values
        r = month_stats(H, shock, gate)
        if r is None:
            continue
        r["date"] = dt
        rows.append(r)
    return pd.DataFrame(rows)


def summarise(mo: pd.DataFrame) -> dict:
    d = mo["diff"].dropna()
    out = {"months": int(len(d)), "mean_diff_pct_mo": float(d.mean() * 100) if len(d) else np.nan,
           "t": tstat(d), "hit_neg": float((d < 0).mean()) if len(d) else np.nan,
           "spearman_mean": float(mo["spearman"].mean()), "spearman_t": tstat(mo["spearman"]),
           "swap_gain_ann_pct": float(mo["swap_gain"].dropna().mean() * 1200) if mo["swap_gain"].notna().any() else np.nan,
           "swap_gain_t": tstat(mo["swap_gain"]), "flag_months": int(mo["flagged"].notna().sum())}
    return out


def context_ic(hold: pd.DataFrame, sh: pd.DataFrame, window: int, component: str) -> dict:
    s = sh[(sh["window"] == window) & (sh["component"] == component)]
    ics = []
    for dt, H in hold.groupby("date"):
        z = s[s["date"] == dt].set_index("iso3")["z"]
        x = H["country"].map(lambda c: z.get(BUCKET_ISO[c], np.nan))
        ok = x.notna()
        if ok.sum() >= 20:
            ics.append(sps.spearmanr(x[ok], H["fwd_excess"][ok]).statistic)
    ics = pd.Series(ics)
    return {"months": int(len(ics)), "mean_rank_ic": float(ics.mean()), "t": tstat(ics)}


# ---------------------------------------------------------------------------------------- report
def fig_to_b64(fig) -> str:
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=130, bbox_inches="tight"); return base64.b64encode(buf.getvalue()).decode()


def charts(run_dir: Path, primary: pd.DataFrame, stale: pd.DataFrame, null_t: np.ndarray, t_matched: float,
           arms: pd.DataFrame) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    imgs = []
    with PdfPages(run_dir / "charts.pdf") as pdf:
        fig, ax = plt.subplots(figsize=(9, 4.2))
        ax.plot(primary["date"], primary["diff"].cumsum() * 100, color="#1f4e79", lw=2, label="matched news")
        ax.plot(stale["date"], stale["diff"].cumsum() * 100, color="#999999", lw=1.6, ls="--", label="stale news (3 months earlier)")
        ax.axhline(0, color="black", lw=0.6)
        ax.set_title("Cumulative: most-shocked holding minus the other seven (% points)")
        ax.set_ylabel("cumulative %"); ax.legend(frameon=False); ax.grid(alpha=0.25)
        pdf.savefig(fig); imgs.append(fig_to_b64(fig)); plt.close(fig)

        fig, ax = plt.subplots(figsize=(9, 4.2))
        ax.hist(null_t, bins=40, color="#c9d6e8", edgecolor="white")
        ax.axvline(t_matched, color="#b22222", lw=2, label=f"matched t = {t_matched:.2f}")
        ax.axvline(np.percentile(null_t, 5), color="#1f4e79", lw=1.2, ls=":", label="5th percentile of shuffled")
        ax.set_title("Country-shuffled news: t-statistics under the null (500 permutations)")
        ax.set_xlabel("t of flagged minus others"); ax.legend(frameon=False)
        pdf.savefig(fig); imgs.append(fig_to_b64(fig)); plt.close(fig)

        a = arms[(arms["arm"] == "matched") & (arms["gate"].isna())]
        piv = a.pivot_table(index="component", columns="window", values="t")
        fig, ax = plt.subplots(figsize=(9, 4.2))
        piv.plot(kind="bar", ax=ax, color=["#9fb8d8", "#1f4e79", "#5a7fa8"], edgecolor="white")
        ax.axhline(-2, color="#b22222", lw=0.8, ls="--"); ax.axhline(2, color="#b22222", lw=0.8, ls="--"); ax.axhline(0, color="black", lw=0.6)
        ax.set_title("t-statistic of flagged minus others, by component and window (negative = veto works)")
        ax.set_ylabel("t"); ax.legend(title="window (days)", frameon=False); ax.grid(axis="y", alpha=0.25)
        plt.xticks(rotation=0)
        pdf.savefig(fig); imgs.append(fig_to_b64(fig)); plt.close(fig)
    return imgs


def write_report(run_dir: Path, summ: dict, arms: pd.DataFrame, primary: pd.DataFrame, imgs: list[str]) -> None:
    def tbl(df: pd.DataFrame, cols: list[str], fmt: dict) -> str:
        h = "".join(f"<th>{c}</th>" for c in cols)
        body = ""
        for _, r in df.iterrows():
            cells = ""
            for c in cols:
                v = r[c]
                if isinstance(v, float) and np.isnan(v):
                    cells += "<td>—</td>"
                elif c in fmt and isinstance(v, (float, int, np.floating, np.integer)):
                    cells += f"<td>{fmt[c].format(v)}</td>"
                else:
                    cells += f"<td>{v}</td>"
            body += f"<tr>{cells}</tr>"
        return f"<table><thead><tr>{h}</tr></thead><tbody>{body}</tbody></table>"

    p = summ["primary"]; st = summ["stale"]; sh = summ["shuffle"]; dec = summ["decision"]
    verdict_colour = {"PASS": "#1e7b34", "FAIL": "#b22222", "INCONCLUSIVE": "#b8860b"}[dec["verdict"]]
    a_main = arms[(arms["gate"].isna()) & (arms["draw"] == "pooled")].sort_values(["arm", "component", "window"])
    a_gate = arms[(arms["gate"].notna()) & (arms["draw"] == "pooled")]
    a_draw = arms[(arms["gate"].isna()) & (arms["arm"] == "matched") & (arms["window"] == PRIMARY_W) & (arms["component"] == PRIMARY_COMP)]
    fmt = {"mean_diff_pct_mo": "{:+.2f}", "t": "{:+.2f}", "hit_neg": "{:.0%}", "spearman_mean": "{:+.3f}", "spearman_t": "{:+.2f}",
           "swap_gain_ann_pct": "{:+.2f}", "swap_gain_t": "{:+.2f}", "months": "{:d}", "flag_months": "{:d}", "window": "{:d}"}
    cols = ["arm", "component", "window", "months", "mean_diff_pct_mo", "t", "hit_neg", "spearman_mean", "spearman_t", "swap_gain_ann_pct", "swap_gain_t"]
    recent = primary.sort_values("date").tail(24)
    html = f"""<!DOCTYPE html><html lang="en" data-theme="light"><head><meta charset="utf-8">
<title>GDELT veto test — results</title>
<style>
:root{{color-scheme:light}} body{{font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:1000px;margin:2rem auto;padding:0 1rem;color:#222;background:#fff;line-height:1.5}}
h1{{font-size:1.6rem}} h2{{font-size:1.2rem;margin-top:2rem;border-bottom:1px solid #ddd;padding-bottom:.2rem}}
table{{border-collapse:collapse;font-size:.88rem;margin:.6rem 0}} th,td{{border:1px solid #ddd;padding:.3rem .55rem;text-align:right}} th:first-child,td:first-child,td:nth-child(2),th:nth-child(2){{text-align:left}}
.verdict{{display:inline-block;padding:.3rem .8rem;border-radius:.4rem;color:#fff;font-weight:600;background:{verdict_colour}}}
.note{{background:#f6f8fa;border-left:4px solid #1f4e79;padding:.6rem .9rem;margin:.8rem 0}} img{{max-width:100%;border:1px solid #eee;margin:.4rem 0}}
code{{background:#f3f3f3;padding:0 .25rem}}
</style></head><body>
<h1>Does a pre-rebalance news shock flag the default model's weakest holding?</h1>
<p>Pre-registered test (<code>gdelt_veto/PREREG.md</code>), run {summ['run_ts']}. Months {summ['first_month']} to {summ['last_month']} ({p['months']} months).</p>
<p><span class="verdict">{dec['verdict']}</span></p>
<div class="note"><b>Bottom line.</b> {dec['sentence']}</div>

<h2>The primary result</h2>
<p>Each month the holding with the largest composite news shock over the prior {PRIMARY_W} days is flagged. Its next-month excess return minus the mean of the other seven holdings:</p>
<ul>
<li><b>Matched news:</b> {p['mean_diff_pct_mo']:+.2f}% per month, t = {p['t']:+.2f}, flagged name lagged in {p['hit_neg']:.0%} of months.</li>
<li><b>Stale news</b> (same measure, three months earlier): {st['mean_diff_pct_mo']:+.2f}% per month, t = {st['t']:+.2f}.</li>
<li><b>Country-shuffled news</b> (500 permutations): 5th percentile of t = {sh['p05']:+.2f}, median {sh['p50']:+.2f}; the matched t sits at the {sh['pct_rank_of_matched']:.0f}th percentile of the null.</li>
<li><b>Swapping the flagged name for the best non-holding</b> would have changed the basket's excess return by {p['swap_gain_ann_pct']:+.2f}% a year (t = {p['swap_gain_t']:+.2f}).</li>
<li><b>Power:</b> with the realised month-to-month spread of {summ['power']['sd_diff_pct_mo']:.2f}% on the difference, the effect detectable at 80% power over {p['months']} months is {summ['power']['detectable_pct_mo']:.2f}% per month on the flagged name, which is about {summ['power']['detectable_basket_ann_pct']:.2f}% a year on the basket if acted on every month.</li>
</ul>
<p>Decision rule checks: t ≤ −2: <b>{dec['c1']}</b>; below the shuffled 5th percentile: <b>{dec['c2']}</b>; stale not significant and matched stronger than stale: <b>{dec['c3']}</b>.</p>
<img src="data:image/png;base64,{imgs[0]}"><img src="data:image/png;base64,{imgs[1]}">

<h2>Secondary: every component and window (pooled scores, always flag)</h2>
<p>Negative t means the shocked holding lagged. "theme_surge", "uncertainty", "goldstein", "protest" and "deep_composite" come from the retired deep file and end 2026-04.</p>
<img src="data:image/png;base64,{imgs[2]}">
{tbl(a_main, cols, fmt)}

<h2>Secondary: act only on a real shock (composite ≥ 1.0)</h2>
{tbl(a_gate, cols + ["flag_months"], fmt)}

<h2>Secondary: each seed draw separately (primary arm)</h2>
{tbl(a_draw, ["draw"] + cols[2:], fmt)}

<h2>Context: GDELT as a ranking signal over all 34 (the question already answered DEAD)</h2>
<p>Cross-sectional rank correlation of the composite shock (w = {PRIMARY_W}) with next-month excess return over all 34 countries: mean {summ['context_ic']['mean_rank_ic']:+.3f}, t = {summ['context_ic']['t']:+.2f} over {summ['context_ic']['months']} months.</p>

<h2>Correctness check</h2>
<p>Reconstructed pooled basket vs saved default run (same rule): max absolute monthly excess difference {summ['check']['max_abs_diff']:.2e} over {summ['check']['months_compared']} months; annualised excess {summ['check']['excess_ann_pct']:.2f}% vs saved {summ['check']['saved_excess_ann_pct']:.2f}%.</p>

<h2>Last 24 months, primary arm</h2>
{tbl(recent, ["date", "flagged", "flag_shock", "diff", "swap_gain"], {"flag_shock": "{:+.2f}", "diff": "{:+.4f}", "swap_gain": "{:+.4f}"})}
<p style="color:#666;font-size:.85rem">Files: <code>{run_dir}</code></p>
</body></html>"""
    (run_dir / "report.html").write_text(html)


# ------------------------------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-month", default=None)
    ap.add_argument("--n-shuffle", type=int, default=500)
    ap.add_argument("--no-deep", action="store_true")
    ap.add_argument("--tag", default=None)
    ap.add_argument("--seed", type=int, default=20261007)
    a = ap.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = RESULTS / (f"gdelt_veto_{ts}" + (f"_{a.tag}" if a.tag else ""))
    run_dir.mkdir(parents=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(run_dir / "run.log")])
    t0 = time.time()
    log.info("run dir %s", run_dir)

    # --- holdings
    panel = pd.read_parquet(PANEL, columns=["date", "country", "fwd_ret", "bench_ret", "fwd_excess"])
    panel["date"] = pd.to_datetime(panel["date"])
    sc, draws = load_scores()
    log.info("draws: %s", draws)
    hold_all = {c: holdings_for(sc, c, panel) for c in draws + ["pooled"]}
    # correctness: pooled basket vs saved default
    pooled_mo = hold_all["pooled"][hold_all["pooled"]["held"]].groupby("date")["fwd_excess"].mean()
    saved = pd.read_parquet(DEFAULT_RUN)
    sv = saved[(saved["model"] == "nn_mse") & (saved["rule"] == "buffer_M16") & (saved["member"].str.contains("pool", case=False))]
    if sv.empty:
        sv = saved[(saved["model"] == "nn_mse") & (saved["rule"] == "buffer_M16")]
        log.warning("no pooled member in saved run; members: %s", saved["member"].unique().tolist())
    sv = sv.set_index(pd.to_datetime(sv["date"]))["excess"]
    j = pd.concat([pooled_mo.rename("mine"), sv.rename("saved")], axis=1).dropna()
    check = {"months_compared": int(len(j)), "max_abs_diff": float((j["mine"] - j["saved"]).abs().max()),
             "excess_ann_pct": float(j["mine"].mean() * 1200), "saved_excess_ann_pct": float(j["saved"].mean() * 1200),
             "saved_member_used": sv.name if hasattr(sv, "name") else None}
    log.info("correctness check: %s", check)

    # --- shocks from the live store
    iso_set = sorted(set(BUCKET_ISO.values()))
    live = pd.read_parquet(LIVE, columns=["date", "country_iso3", "n_articles", "tone_mean", "tone_dispersion", "country_news_risk_raw"])
    live = live[live["country_iso3"].isin(iso_set)].rename(columns={"country_iso3": "iso3"})
    live["date"] = pd.to_datetime(live["date"])
    sh = shock_table(live, LIVE_COMPONENTS)
    sh = add_composite(sh, list(LIVE_COMPONENTS), "composite")
    log.info("live shocks: %d rows, %.0fs", len(sh), time.time() - t0)

    # --- exploratory deep arm
    if not a.no_deep and DEEP.exists():
        cols = ["date", "country_iso3"] + [v[0] for v in DEEP_COMPONENTS.values()]
        import pyarrow.parquet as pq
        theme_cols = [c for c in pq.read_schema(DEEP).names if c.startswith("theme_") and c.endswith("_share")]
        deep = pd.read_parquet(DEEP, columns=cols + theme_cols)
        deep = deep[deep["country_iso3"].isin(iso_set)].rename(columns={"country_iso3": "iso3"})
        deep["date"] = pd.to_datetime(deep["date"])
        shd = shock_table(deep[["date", "iso3"] + [v[0] for v in DEEP_COMPONENTS.values()]], DEEP_COMPONENTS)
        shd = add_composite(shd, list(DEEP_COMPONENTS), "deep_composite")
        sht = theme_surge(deep[["date", "iso3"] + theme_cols])
        sh = pd.concat([sh, shd, sht], ignore_index=True)
        log.info("deep shocks added (%d themes), %.0fs", len(theme_cols), time.time() - t0)

    last = pd.Timestamp(a.max_month) if a.max_month else hold_all["pooled"]["date"].max()
    hold = {k: v[(v["date"] >= FIRST_MONTH) & (v["date"] <= last)] for k, v in hold_all.items()}
    sh = sh[(sh["date"] >= FIRST_MONTH) & (sh["date"] <= last)]
    sh.to_parquet(run_dir / "shocks.parquet", index=False)
    hold["pooled"].to_parquet(run_dir / "holdings.parquet", index=False)

    # --- arms
    arm_rows, monthly = [], []
    comps = sorted(sh["component"].unique())
    for comp in comps:
        for w in WINDOWS:
            for arm, stale in (("matched", False), ("stale", True)):
                mo = run_arm(hold["pooled"], sh, w, comp, use_stale=stale)
                if mo.empty:
                    continue
                r = summarise(mo); r.update(arm=arm, component=comp, window=w, gate=np.nan, draw="pooled"); arm_rows.append(r)
                mo = mo.assign(arm=arm, component=comp, window=w, gate=np.nan, draw="pooled"); monthly.append(mo)
    # gated variant on composites
    for comp in [c for c in comps if "composite" in c]:
        for w in WINDOWS:
            mo = run_arm(hold["pooled"], sh, w, comp, gate=1.0)
            r = summarise(mo); r.update(arm="matched", component=comp, window=w, gate=1.0, draw="pooled"); arm_rows.append(r)
            monthly.append(mo.assign(arm="matched", component=comp, window=w, gate=1.0, draw="pooled"))
    # per-draw robustness on the primary
    for dcol in draws:
        mo = run_arm(hold[dcol], sh, PRIMARY_W, PRIMARY_COMP)
        r = summarise(mo); r.update(arm="matched", component=PRIMARY_COMP, window=PRIMARY_W, gate=np.nan, draw=dcol); arm_rows.append(r)
    arms = pd.DataFrame(arm_rows)
    monthly = pd.concat(monthly, ignore_index=True)
    arms.to_parquet(run_dir / "arms.parquet", index=False); monthly.to_parquet(run_dir / "monthly.parquet", index=False)
    with pd.ExcelWriter(run_dir / "arms.xlsx") as xw:
        arms.to_excel(xw, "arms", index=False); monthly.to_excel(xw, "monthly", index=False)
    log.info("arms done, %.0fs", time.time() - t0)

    primary = monthly[(monthly["arm"] == "matched") & (monthly["component"] == PRIMARY_COMP) & (monthly["window"] == PRIMARY_W) & monthly["gate"].isna() & (monthly["draw"] == "pooled")]
    stale = monthly[(monthly["arm"] == "stale") & (monthly["component"] == PRIMARY_COMP) & (monthly["window"] == PRIMARY_W) & monthly["gate"].isna()]
    p_sum, st_sum = summarise(primary), summarise(stale)

    # --- shuffled control on the primary
    rng = np.random.default_rng(a.seed)
    dates = sorted(hold["pooled"]["date"].unique())
    null_t = []
    for i in range(a.n_shuffle):
        perm_map = {}
        for dt in dates:
            others = iso_set.copy()
            perm = rng.permutation(len(others))
            # derangement-ish: ensure no country keeps its own news
            for _ in range(20):
                if all(others[j] != others[perm[j]] for j in range(len(others))):
                    break
                perm = rng.permutation(len(others))
            perm_map[dt] = {others[j]: others[perm[j]] for j in range(len(others))}
        # perm_map maps iso -> iso'; we need z renamed so that holding iso looks up iso' : rename index iso' -> iso
        inv = {dt: {v: k for k, v in m.items()} for dt, m in perm_map.items()}
        mo = run_arm(hold["pooled"], sh, PRIMARY_W, PRIMARY_COMP, perm_map=inv)
        null_t.append(tstat(mo["diff"]))
        if (i + 1) % 50 == 0:
            log.info("shuffle %d/%d, %.0fs", i + 1, a.n_shuffle, time.time() - t0)
    null_t = np.array(null_t)
    pd.DataFrame({"t": null_t}).to_parquet(run_dir / "shuffle_null.parquet", index=False)
    sh_sum = {"n": int(len(null_t)), "p05": float(np.percentile(null_t, 5)), "p50": float(np.percentile(null_t, 50)),
              "p95": float(np.percentile(null_t, 95)), "pct_rank_of_matched": float((null_t < p_sum["t"]).mean() * 100)}

    # --- power
    d = primary["diff"].dropna() * 100
    sd = float(d.std(ddof=1)); n = len(d)
    detectable = 2.8 * sd / np.sqrt(n)   # (z_0.975 + z_0.80) * se
    power = {"sd_diff_pct_mo": sd, "detectable_pct_mo": detectable, "detectable_basket_ann_pct": detectable / K * 12}

    # --- decision
    c1 = p_sum["t"] <= -2.0
    c2 = p_sum["t"] < sh_sum["p05"]
    c3 = (st_sum["t"] > -2.0) and (p_sum["t"] < st_sum["t"])
    if c1 and c2 and c3:
        verdict = "PASS"
        sentence = (f"The most-shocked holding lagged the other seven by {abs(p_sum['mean_diff_pct_mo']):.2f}% a month (t {p_sum['t']:+.2f}), "
                    f"beating both the stale-news and country-shuffled controls.")
    else:
        ci_lo = p_sum["mean_diff_pct_mo"] - 1.96 * sd / np.sqrt(n)
        useful = -detectable  # a useful veto effect would be at least this negative
        verdict = "INCONCLUSIVE" if (ci_lo < useful and p_sum["t"] < 0) else "FAIL"
        direction = "lagged" if p_sum["mean_diff_pct_mo"] < 0 else "beat"
        sentence = (f"The most-shocked holding {direction} the other seven by {abs(p_sum['mean_diff_pct_mo']):.2f}% a month on average (t {p_sum['t']:+.2f}), "
                    f"which is {'not ' if not c1 else ''}significant and {'does' if c2 else 'does not'} beat the country-shuffled control. "
                    f"Stale news gave t {st_sum['t']:+.2f}. "
                    + ("The confidence interval still admits a useful effect, so the result is inconclusive rather than a clean kill."
                       if verdict == "INCONCLUSIVE" else "Pre-rebalance GDELT shocks do not identify the weak holding."))
    decision = {"verdict": verdict, "c1": bool(c1), "c2": bool(c2), "c3": bool(c3), "sentence": sentence}
    ctx = context_ic(hold["pooled"], sh, PRIMARY_W, PRIMARY_COMP)

    summ = {"run_ts": ts, "first_month": str(primary["date"].min().date()), "last_month": str(primary["date"].max().date()),
            "primary": p_sum, "stale": st_sum, "shuffle": sh_sum, "power": power, "decision": decision,
            "context_ic": ctx, "check": check, "draws": draws, "n_shuffle": a.n_shuffle, "max_month": a.max_month,
            "deep_included": not a.no_deep, "elapsed_s": time.time() - t0}
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2, default=lambda o: None if (isinstance(o, float) and np.isnan(o)) else str(o)))
    imgs = charts(run_dir, primary, stale, null_t, p_sum["t"], arms)
    write_report(run_dir, summ, arms, primary, imgs)
    log.info("VERDICT %s | primary %+.2f%%/mo t %+.2f | stale t %+.2f | shuffled p05 %+.2f | %.0fs",
             verdict, p_sum["mean_diff_pct_mo"], p_sum["t"], st_sum["t"], sh_sum["p05"], time.time() - t0)
    print(json.dumps({"run_dir": str(run_dir), "verdict": verdict, "primary": p_sum, "stale_t": st_sum["t"], "shuffle": sh_sum, "check": check}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
