#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/toolkit/heads.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v3_clean/feature_panel_v3_clean.parquet
    cleaned panel: 238 factor z-scores per (date, country), 2000-02 → 2026-09
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/factor_set_v3_clean.json
    the 238 factor names used as inputs (same as the default model)

OUTPUT FILES (in /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model/results/heads_<YYYYMMDD_HHMMSS>/):
- forecasts_oos.parquet   per (head, date, country): out-of-sample forecast of next month's change, the realised change,
                          and the three baselines (zero, persistence, AR1)
- heads.parquet / heads.xlsx   per head: OOS rank IC vs each baseline, paired t, survival flag
- monthly_ic.parquet      per (head, date): monthly rank IC of head and baselines
- summary.json, report.html (light mode), run.log

VERSION: 1.0   LAST UPDATED: 2026-10-08   AUTHOR: Claude for Arjun Divecha

DESCRIPTION:
Rung B stage 1 (toolkit/PREREG.md). For each of seven fundamentals, a rolling-60
ridge forecasts next month's change in the variable's time-series z-score from all
238 factors, walk-forward, out of sample from 2005-02. Alpha is chosen by 5-fold
month-grouped CV on monthly rank IC of the change. Each head is scored against
three naive baselines and survives only if its mean OOS rank IC beats the best
baseline by >= 0.05 with paired t >= 2. The surviving set is written to the log
and is the only input stage 2 may use.

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/experiments/2026_10_rank_model"
  .venv/bin/python toolkit/heads.py [--window 60] [--first-train-months 60] [--step-months 12]
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
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold

EXP_DIR = Path(__file__).resolve().parent.parent
RESULTS = EXP_DIR / "results"
PANEL = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v3_clean/feature_panel_v3_clean.parquet")
FACTOR_SET = EXP_DIR / "factor_set_v3_clean.json"
TARGETS = {"trailing_eps": "Trailing EPS_TS", "best_eps": "BEST EPS_TS", "lt_growth": "LT Growth_TS", "roe": "Best ROE_TS",
           "inflation": "IMF_CPI_Inflation_YoY_TS", "vol20": "20 Day Vol_TS", "bond10y": "BBG_Govt_Bond_10Y_TS"}
ALPHAS = [1.0, 10.0, 100.0, 1000.0, 10000.0]
SURVIVE_IC_MARGIN, SURVIVE_T = 0.05, 2.0
log = logging.getLogger("heads")


def tstat(x) -> float:
    x = pd.Series(x).dropna(); return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))) if len(x) > 2 else np.nan


def monthly_ic(pred: np.ndarray, y: np.ndarray, month: np.ndarray) -> pd.Series:
    out = {}
    for m in np.unique(month):
        i = month == m
        if i.sum() >= 10 and np.std(pred[i]) > 0 and np.std(y[i]) > 0:
            out[m] = sps.spearmanr(pred[i], y[i]).statistic
    return pd.Series(out)


def fit_head_ridge(Xtr, ytr, mtr, Xev):
    """Alpha by 5-fold month-grouped CV on mean monthly rank IC of the forecast change; refit on all training rows."""
    gkf = GroupKFold(n_splits=5); best, best_ic = None, -9
    for a in ALPHAS:
        ics = []
        for itr, iva in gkf.split(Xtr, ytr, groups=mtr):
            m = Ridge(alpha=a).fit(Xtr[itr], ytr[itr]); ics.append(monthly_ic(m.predict(Xtr[iva]), ytr[iva], mtr[iva]).mean())
        if np.nanmean(ics) > best_ic:
            best, best_ic = a, float(np.nanmean(ics))
    m = Ridge(alpha=best).fit(Xtr, ytr)
    return m.predict(Xev), {"alpha": best, "cv_ic": best_ic}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--window", type=int, default=60); ap.add_argument("--first-train-months", type=int, default=60); ap.add_argument("--step-months", type=int, default=12)
    a = ap.parse_args()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S"); run_dir = RESULTS / f"heads_{ts}"; run_dir.mkdir(parents=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", handlers=[logging.StreamHandler(), logging.FileHandler(run_dir / "run.log")])
    t0 = time.time()
    feats = [f["variable"] for f in json.load(open(FACTOR_SET))["factors"]]
    panel = pd.read_parquet(PANEL); panel["date"] = pd.to_datetime(panel["date"]); panel = panel.sort_values(["country", "date"])
    missing = [v for v in TARGETS.values() if v not in panel.columns]
    if missing:
        raise SystemExit(f"target columns missing from panel: {missing}")
    # targets: next month's change in the variable's own z (per country); baselines from the past only
    for name, col in TARGETS.items():
        g = panel.groupby("country")[col]
        panel[f"y_{name}"] = g.shift(-1) - panel[col]                 # change over the coming month (realised at D+1)
        panel[f"b_persist_{name}"] = panel[col] - g.shift(1)           # last month's change
        # AR(1) on the last 12 changes: slope * last change
        d = panel[col] - g.shift(1); panel[f"_d_{name}"] = d
    months = pd.DatetimeIndex(np.sort(panel["date"].unique())); mi = {m: i for i, m in enumerate(months)}
    panel["m"] = panel["date"].map(mi).to_numpy()
    X = np.nan_to_num(np.clip(panel[feats].to_numpy(float), -5, 5), nan=0.0)
    folds = []; t = a.first_train_months
    while t < len(months):
        folds.append((t, min(t + a.step_months, len(months)))); t += a.step_months
    log.info("panel %d rows, %d months, %d features; %d folds; window %d", len(panel), len(months), X.shape[1], len(folds), a.window)

    fc_rows, ic_rows, head_rows = [], [], []
    for name, col in TARGETS.items():
        y = panel[f"y_{name}"].to_numpy(float); pred = np.full(len(panel), np.nan); ar1 = np.full(len(panel), np.nan)
        alphas = []
        for t_start, t_end in folds:
            tr = (panel["m"] >= max(0, t_start - a.window)) & (panel["m"] < t_start) & np.isfinite(y)
            ev = (panel["m"] >= t_start) & (panel["m"] < t_end)
            if tr.sum() < 200:
                continue
            p, info = fit_head_ridge(X[tr.to_numpy()], y[tr.to_numpy()], panel["m"].to_numpy()[tr.to_numpy()], X[ev.to_numpy()])
            pred[ev.to_numpy()] = p; alphas.append(info["alpha"])
        # AR(1) baseline: per country, slope of change on lagged change over the trailing 12 changes (past only)
        for c, g in panel.groupby("country", sort=False):
            d = g[f"_d_{name}"]; lag = d.shift(1)
            cov = (d * lag).rolling(12, min_periods=8).mean() - d.rolling(12, min_periods=8).mean() * lag.rolling(12, min_periods=8).mean()
            var = lag.rolling(12, min_periods=8).var(ddof=0)
            slope = (cov / var.replace(0, np.nan)).clip(-1, 1)
            ar1[g.index.to_numpy()] = (slope * d).to_numpy()   # forecast of next change = slope * last change
        ok = np.isfinite(pred) & np.isfinite(y)
        df = pd.DataFrame({"head": name, "date": panel["date"].to_numpy(), "country": panel["country"].to_numpy(), "forecast": pred, "realised": y,
                           "b_zero": 0.0, "b_persist": panel[f"b_persist_{name}"].to_numpy(), "b_ar1": ar1})[ok]
        fc_rows.append(df)
        m = df["date"].map(mi).to_numpy()
        ic_head = monthly_ic(df["forecast"].to_numpy(), df["realised"].to_numpy(), m)
        ic_p = monthly_ic(np.nan_to_num(df["b_persist"].to_numpy()), df["realised"].to_numpy(), m)
        ic_a = monthly_ic(np.nan_to_num(df["b_ar1"].to_numpy()), df["realised"].to_numpy(), m)
        ics = pd.DataFrame({"head": ic_head, "persist": ic_p, "ar1": ic_a}); ics["zero"] = 0.0
        ics.index = months[ics.index]; ics["name"] = name; ic_rows.append(ics.reset_index().rename(columns={"index": "date"}))
        best_base = max(["persist", "ar1", "zero"], key=lambda b: ics[b].mean())
        diff = ics["head"] - ics[best_base]
        row = {"head": name, "variable": col, "months": int(len(ics)), "ic_head": float(ics["head"].mean()), "ic_head_t": tstat(ics["head"]),
               "ic_persist": float(ics["persist"].mean()), "ic_ar1": float(ics["ar1"].mean()), "best_baseline": best_base,
               "ic_margin_vs_best_baseline": float(diff.mean()), "paired_t_vs_best_baseline": tstat(diff),
               "snr_per_month": float(ics["head"].mean() / ics["head"].std(ddof=1)), "alpha_mode": float(pd.Series(alphas).mode().iloc[0]) if alphas else np.nan}
        row["survives"] = bool(row["ic_margin_vs_best_baseline"] >= SURVIVE_IC_MARGIN and row["paired_t_vs_best_baseline"] >= SURVIVE_T)
        head_rows.append(row)
        log.info("%-12s IC %.3f (t %.1f) | persist %.3f | ar1 %.3f | margin vs %s %+.3f (paired t %.1f) | %s | %.0fs",
                 name, row["ic_head"], row["ic_head_t"], row["ic_persist"], row["ic_ar1"], best_base, row["ic_margin_vs_best_baseline"], row["paired_t_vs_best_baseline"],
                 "SURVIVES" if row["survives"] else "dropped", time.time() - t0)
    heads = pd.DataFrame(head_rows); fc = pd.concat(fc_rows, ignore_index=True); ics_all = pd.concat(ic_rows, ignore_index=True)
    fc.to_parquet(run_dir / "forecasts_oos.parquet", index=False); heads.to_parquet(run_dir / "heads.parquet", index=False); ics_all.to_parquet(run_dir / "monthly_ic.parquet", index=False)
    with pd.ExcelWriter(run_dir / "heads.xlsx") as xw:
        heads.to_excel(xw, sheet_name="heads", index=False); ics_all.to_excel(xw, sheet_name="monthly_ic", index=False)
    survivors = heads[heads["survives"]]["head"].tolist()
    summ = {"run_ts": ts, "window": a.window, "oos_start": str(fc["date"].min().date()), "oos_end": str(fc["date"].max().date()),
            "survivors": survivors, "rule": f"margin >= {SURVIVE_IC_MARGIN} and paired t >= {SURVIVE_T} vs best naive baseline", "heads": heads.to_dict("records"), "elapsed_s": time.time() - t0}
    (run_dir / "summary.json").write_text(json.dumps(summ, indent=2, default=str))

    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9.5, 4.6)); x = np.arange(len(heads)); w = 0.27
    ax.bar(x - w, heads["ic_head"], w, color="#1f4e79", label="head (ridge, rolling 60)"); ax.bar(x, heads["ic_persist"], w, color="#9fb8d8", label="persistence"); ax.bar(x + w, heads["ic_ar1"], w, color="#c9d6e8", label="AR(1)")
    ax.set_xticks(x); ax.set_xticklabels(heads["head"]); ax.axhline(0, color="k", lw=.6); ax.set_ylabel("mean OOS rank IC with realised next-month change"); ax.legend(frameon=False); ax.grid(axis="y", alpha=.25)
    ax.set_title("Can the factors forecast next month's change in each fundamental?")
    b = io.BytesIO(); fig.savefig(b, format="png", dpi=130, bbox_inches="tight"); img = base64.b64encode(b.getvalue()).decode(); fig.savefig(run_dir / "charts.pdf", bbox_inches="tight"); plt.close(fig)
    cols = ["head", "variable", "months", "ic_head", "ic_head_t", "snr_per_month", "ic_persist", "ic_ar1", "best_baseline", "ic_margin_vs_best_baseline", "paired_t_vs_best_baseline", "alpha_mode", "survives"]
    fmt = {c: "{:+.3f}" for c in ("ic_head", "ic_persist", "ic_ar1", "ic_margin_vs_best_baseline")} | {"ic_head_t": "{:+.1f}", "paired_t_vs_best_baseline": "{:+.1f}", "snr_per_month": "{:.2f}", "alpha_mode": "{:.0f}"}
    tbl = "<table><thead><tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr></thead><tbody>" + "".join(
        "<tr>" + "".join(f"<td>{fmt[c].format(r[c]) if c in fmt else r[c]}</td>" for c in cols) + "</tr>" for _, r in heads.iterrows()) + "</tbody></table>"
    html = f"""<!DOCTYPE html><html lang="en" data-theme="light"><head><meta charset="utf-8"><title>Rung B stage 1 — forecast heads</title>
<style>:root{{color-scheme:light}} body{{font-family:-apple-system,Helvetica,Arial,sans-serif;max-width:1050px;margin:2rem auto;padding:0 1rem;color:#222;background:#fff;line-height:1.5}} table{{border-collapse:collapse;font-size:.85rem}} th,td{{border:1px solid #ddd;padding:.3rem .5rem;text-align:right}} td:nth-child(-n+2),th:nth-child(-n+2){{text-align:left}} .note{{background:#f6f8fa;border-left:4px solid #1f4e79;padding:.6rem .9rem}} img{{max-width:100%;border:1px solid #eee}}</style></head><body>
<h1>Rung B, stage 1: can the factors forecast next month's fundamentals?</h1>
<p>Pre-registered in <code>toolkit/PREREG.md</code>; run {ts}. Rolling-{a.window} ridge on the 238 factors, out of sample {summ['oos_start']} → {summ['oos_end']}. Target: next month's change in each variable's time-series z-score. Survival: mean OOS rank IC at least {SURVIVE_IC_MARGIN} above the best naive baseline with paired t ≥ {SURVIVE_T}.</p>
<div class="note"><b>Survivors:</b> {', '.join(survivors) if survivors else 'none'}. Only these may enter stage 2.</div>
<img src="data:image/png;base64,{img}">{tbl}
<p style="color:#666;font-size:.85rem">Files: <code>{run_dir}</code></p></body></html>"""
    (run_dir / "report.html").write_text(html)
    log.info("SURVIVORS %s | %.0fs", survivors, time.time() - t0)
    print(heads[["head", "ic_head", "ic_head_t", "ic_persist", "ic_ar1", "best_baseline", "ic_margin_vs_best_baseline", "paired_t_vs_best_baseline", "survives"]].round(3).to_string(index=False)); print(run_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
