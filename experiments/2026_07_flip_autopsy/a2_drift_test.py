"""
=============================================================================
SCRIPT NAME: a2_drift_test.py
=============================================================================

WHAT THIS PROGRAM DOES:
Step (i) of the G1 flip autopsy (PRD section 4, as amended): the construction-
drift test. Recomputes the network_spillover family's per-date cross-sectional
rank ICs from TODAY'S signal panels (the 2026-07-13 snapshot) using the
harness's exact daily conventions, then compares them month-by-month with the
FROZEN per-date IC series stored by the June-2026 harness runs. If today's
pipeline reproduces the frozen IC history (including the 2024-26 decay), the
flip is NOT a construction artifact of the last month of pipeline evolution.
Also runs the two decisive composition slices:
  - PIT (GRAPHP*, vintage edges) vs non-PIT (GRAPH*, today's edges applied
    historically) vs LL_* vs SIM_* sub-family per-year ICs: an edge-vintage
    artifact would show the flip only in one variant class.
  - Per-signal 2024-26 ICs: breadth of the flip across all roster signals.
Additionally estimates the single least-squares break date of the monthly
family IC (search window 2022-01..2026-01, PRD section 3).

Daily conventions replicated from the production code:
  - returns: t2_factors_daily 1DRet is FORWARD-labeled on a calendar grid with
    0.0 non-trading placeholders; per scripts/loop/loopdb.py::daily_country_returns
    each country's series is shifted one calendar row (backward labeling) and
    exact-0.0 rows are dropped.
  - alignment: per scripts/harness/evaluate_signal.py::align_daily, signal at
    trading day t predicts the compounded return over t+lag+1..t+lag+h on the
    country's own trading calendar; per-date IC = Spearman(value, fwd_return).
  - lag: computed at lag 0 and lag 1; per signal, the lag whose monthly IC
    series best matches the frozen June series is used (calibration to a
    frozen reference, reported per signal - not tuning toward a verdict).

INPUT FILES (all frozen snapshot / experiment outputs; no DB access):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13/graph_features_daily.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13/graph_features_pit_daily.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13/leadlag_features_daily.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13/similarity_features_daily.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13/t2_1dret_daily.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13/harness_results.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/a1_family_ic_monthly.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/harness_runs/*.json (roster metadata, read-only)

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/a2_recomputed_ic_daily.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/a2_family_ic_monthly_recomputed.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/a2_drift_comparison.xlsx
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/a2_summary.json

VERSION: 1.0  |  LAST UPDATED: 2026-07-13  |  AUTHOR: Claude (G1 flip autopsy)
DEPENDENCIES: pandas, numpy, scipy, openpyxl (production venv). No DB access.
USAGE: venv/bin/python experiments/2026_07_flip_autopsy/a2_drift_test.py
=============================================================================
"""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as sstats

ROOT = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
SNAP = ROOT / "Data/work/experiments/flip_autopsy/snapshot_2026_07_13"
RES = ROOT / "experiments/2026_07_flip_autopsy/results"
RUNS = ROOT / "Data/loop/harness_runs"

# ---------------------------------------------------------------- roster
rows = []
for f in sorted(RUNS.glob("H_*.json")):
    o = json.loads(f.read_text())
    var = (o.get("signal_spec") or {}).get("variable", "")
    if re.match(r"^(GRAPH|LL_|SIM_)", var):
        uni = o.get("universe")
        rows.append({"hypothesis_id": o["hypothesis_id"], "variable": var,
                     "table": (o.get("signal_spec") or {}).get("table"),
                     "direction": o.get("direction"), "run_ts": o.get("run_ts"),
                     "verdict": o.get("verdict"),
                     "universe": json.dumps(uni) if isinstance(uni, list) else None})
js = pd.DataFrame(rows).sort_values("run_ts").groupby("hypothesis_id", as_index=False).tail(1)
hr = pd.read_parquet(SNAP / "harness_results.parquet")
js = js.merge(hr[["hypothesis_id", "primary_horizon"]].drop_duplicates("hypothesis_id"),
              on="hypothesis_id", how="left")
roster = js[js["verdict"].isin(["WEAK", "WATCH"])].copy()
# one row per variable: keep the run with the best-covered (latest) test
roster = roster.sort_values("run_ts").groupby("variable", as_index=False).tail(1)
print(f"roster: {len(roster)} variables")

# ---------------------------------------------------------------- returns
ret = pd.read_parquet(SNAP / "t2_1dret_daily.parquet")
ret["date"] = pd.to_datetime(ret["date"])
ret = ret.sort_values(["country", "date"]).reset_index(drop=True)
# loopdb.daily_country_returns convention: shift one calendar row, drop 0.0
ret["ret_bwd"] = ret.groupby("country")["value"].shift(1)
ret = ret.dropna(subset=["ret_bwd"])
ret = ret[ret["ret_bwd"] != 0.0]
ret = ret.rename(columns={"ret_bwd": "return_1m"})[["date", "country", "return_1m"]]
print(f"daily returns after backward-shift + placeholder-drop: {len(ret):,}")

TABLES = {
    "graph_features_daily": pd.read_parquet(SNAP / "graph_features_daily.parquet"),
    "graph_features_pit_daily": pd.read_parquet(SNAP / "graph_features_pit_daily.parquet"),
    "leadlag_features_daily": pd.read_parquet(SNAP / "leadlag_features_daily.parquet"),
    "similarity_features_daily": pd.read_parquet(SNAP / "similarity_features_daily.parquet"),
}
for k, v in TABLES.items():
    v["date"] = pd.to_datetime(v["date"])


def align_daily(signal: pd.DataFrame, returns: pd.DataFrame, horizon_days: int,
                lag_days: int = 0) -> pd.DataFrame:
    """Replica of evaluate_signal.align_daily (see doc header)."""
    r = returns.sort_values(["country", "date"]).copy()
    r["log1p"] = np.log1p(r["return_1m"])
    frames = []
    for country, g in r.groupby("country"):
        sig_c = signal[signal["country"] == country]
        if sig_c.empty:
            continue
        g = g.reset_index(drop=True)
        cum = g["log1p"].cumsum()
        pos = pd.Series(g.index.values, index=g["date"])
        p = pos.reindex(sig_c["date"]).values
        valid = ~pd.isna(p)
        p = p[valid].astype(int)
        sig_v = sig_c.iloc[np.flatnonzero(valid)]
        start = p + lag_days
        end = p + lag_days + horizon_days
        ok = end < len(g)
        start, end = start[ok], end[ok]
        sig_v = sig_v.iloc[np.flatnonzero(ok)]
        fwd = np.expm1(cum.values[end] - cum.values[start])
        f = sig_v[["date", "country", "value"]].copy()
        f["fwd_return"] = fwd
        frames.append(f)
    if not frames:
        return pd.DataFrame(columns=["date", "country", "value", "fwd_return"])
    return pd.concat(frames, ignore_index=True).dropna(subset=["value", "fwd_return"])


def daily_ic(aligned: pd.DataFrame) -> pd.Series:
    def _ic(g):
        if g["value"].nunique() < 3 or len(g) < 8:
            return np.nan
        return sstats.spearmanr(g["value"], g["fwd_return"])[0]
    return aligned.groupby("date").apply(_ic, include_groups=False).dropna()


def nw_tstat(x, lags=6):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    n = len(x)
    if n < 12:
        return np.nan
    e = x - x.mean()
    s = e @ e / n
    for k in range(1, lags + 1):
        s += 2.0 * (1 - k / (lags + 1)) * (e[k:] @ e[:-k]) / n
    return float(x.mean() / np.sqrt(s / n))


# frozen June monthly series per signal, for lag calibration
ics_frozen = pd.read_parquet(SNAP / "harness_ic_series.parquet")
ics_frozen["date"] = pd.to_datetime(ics_frozen["date"])
ics_frozen["month"] = ics_frozen["date"].dt.to_period("M").dt.to_timestamp()

all_daily, sig_monthly, calib_rows = [], [], []
for _, r in roster.iterrows():
    tab = TABLES.get(r["table"])
    if tab is None:
        print(f"  !! table {r['table']} not in snapshot for {r['variable']} — SKIP")
        continue
    sig = tab[tab["variable"] == r["variable"]][["date", "country", "value"]].dropna()
    if isinstance(r.get("universe"), str):
        uni = set(json.loads(r["universe"]))
        if 0 < len(uni) < 34:
            sig = sig[sig["country"].isin(uni)]
    if sig.empty:
        print(f"  !! no rows for {r['variable']} — SKIP")
        continue
    h = int(re.sub(r"[^0-9]", "", str(r["primary_horizon"]) or "21") or 21)
    frozen = ics_frozen[(ics_frozen["hypothesis_id"] == r["hypothesis_id"])
                        & (ics_frozen["horizon"].astype(str) == str(r["primary_horizon"]))]
    frozen_m = frozen.groupby("month")["ic"].mean()

    best = None
    for lag in (0, 1):
        al = align_daily(sig, ret, h, lag)
        ic = daily_ic(al)
        icm = ic.groupby(ic.index.to_period("M").to_timestamp()).mean()
        ov = icm.index.intersection(frozen_m.index)
        match = icm.loc[ov].corr(frozen_m.loc[ov]) if len(ov) >= 24 else np.nan
        if best is None or (match == match and match > best[2]):
            best = (lag, ic, match, icm)
    lag, ic, match, icm = best
    sign = -1.0 if r["direction"] == "lower_is_better" else 1.0
    d = ic.rename("ic").reset_index()
    d["variable"], d["lag_used"], d["ic_aligned"] = r["variable"], lag, sign * d["ic"]
    all_daily.append(d)
    m = (sign * icm).rename("ic_aligned").reset_index()
    m.columns = ["month", "ic_aligned"]
    m["variable"] = r["variable"]
    sig_monthly.append(m)
    calib_rows.append({"variable": r["variable"], "hypothesis_id": r["hypothesis_id"],
                       "horizon_days": h, "lag_used": lag,
                       "match_corr_vs_frozen": round(float(match), 4) if match == match else None,
                       "n_overlap_months": int(len(icm.index.intersection(frozen_m.index)))})
    print(f"  {r['variable']:32} h={h:>2} lag={lag} match_corr={match:.3f}")

daily_df = pd.concat(all_daily, ignore_index=True)
daily_df.to_parquet(RES / "a2_recomputed_ic_daily.parquet", index=False)
sm = pd.concat(sig_monthly, ignore_index=True)
fam_m = sm.groupby("month")["ic_aligned"].mean().rename("family_ic")
fam_m.reset_index().to_parquet(RES / "a2_family_ic_monthly_recomputed.parquet", index=False)

# --------------------------------------------- comparison vs frozen family IC
frozen_fam = pd.read_parquet(RES / "a1_family_ic_monthly.parquet").set_index("month")["family_ic"]
ov = fam_m.index.intersection(frozen_fam.index)
fam_corr = float(fam_m.loc[ov].corr(frozen_fam.loc[ov]))
fam_mad = float((fam_m.loc[ov] - frozen_fam.loc[ov]).abs().median())

# --------------------------------------------- sub-family per-year slices
sm["year"] = pd.to_datetime(sm["month"]).dt.year
sm["subfam"] = np.select(
    [sm["variable"].str.startswith("GRAPHP"), sm["variable"].str.startswith("GRAPH"),
     sm["variable"].str.startswith("LL_"), sm["variable"].str.startswith("SIM_")],
    ["GRAPHP_pit", "GRAPH_nonpit", "LL", "SIM"], default="?")
subfam_year = sm.pivot_table(index="year", columns="subfam", values="ic_aligned", aggfunc="mean")
per_signal_2426 = (sm[sm["year"] >= 2024].groupby("variable")["ic_aligned"]
                   .agg(["mean", "count"]).sort_values("mean"))
per_signal_pre = (sm[(sm["year"] >= 2012) & (sm["year"] <= 2023)]
                  .groupby("variable")["ic_aligned"].mean().rename("pre_mean"))
breadth = per_signal_2426.join(per_signal_pre)

# --------------------------------------------- break-date (single LS break)
f = fam_m.dropna()
cands = [d for d in f.index if pd.Timestamp("2022-01-01") <= d <= pd.Timestamp("2026-01-01")]
best_bd, best_ssr = None, np.inf
for bd in cands:
    a, b = f[f.index < bd], f[f.index >= bd]
    if len(a) < 24 or len(b) < 6:
        continue
    ssr = ((a - a.mean()) ** 2).sum() + ((b - b.mean()) ** 2).sum()
    if ssr < best_ssr:
        best_ssr, best_bd = ssr, bd

pre = f[(f.index >= "2012-01-01") & (f.index < "2024-01-01")]
post = f[f.index >= "2024-01-01"]
summary = {
    "family_corr_recomputed_vs_frozen": round(fam_corr, 4),
    "family_median_abs_diff": round(fam_mad, 5),
    "drift_reading_prd": ("no material value drift" if fam_corr >= 0.95
                          else "INVESTIGATE: recomputed IC diverges from frozen"),
    "recomputed_pre_2012_2023_mean_ic": round(float(pre.mean()), 5),
    "recomputed_pre_nw_t": round(nw_tstat(pre.values), 2),
    "recomputed_post_2024_mean_ic": round(float(post.mean()), 5),
    "recomputed_post_nw_t": round(nw_tstat(post.values), 2),
    "break_date_ls": str(best_bd.date()) if best_bd is not None else None,
    "per_year_subfamily_ic": json.loads(subfam_year.round(4).to_json()),
    "lag_calibration": calib_rows,
}
(RES / "a2_summary.json").write_text(json.dumps(summary, indent=2))

with pd.ExcelWriter(RES / "a2_drift_comparison.xlsx") as xw:
    pd.DataFrame({"frozen_jun2026": frozen_fam.loc[ov], "recomputed_jul2026": fam_m.loc[ov]}
                 ).to_excel(xw, sheet_name="family_ic_monthly")
    subfam_year.round(4).to_excel(xw, sheet_name="subfamily_per_year")
    breadth.round(4).to_excel(xw, sheet_name="per_signal_2024_26")
    pd.DataFrame(calib_rows).to_excel(xw, sheet_name="lag_calibration", index=False)

print("\n=== DRIFT TEST (i-a): recomputed vs frozen family IC ===")
print(f"corr={fam_corr:.4f}  median_abs_diff={fam_mad:.5f}  -> {summary['drift_reading_prd']}")
print(f"\nrecomputed pre 2012-23 IC {summary['recomputed_pre_2012_2023_mean_ic']} "
      f"(NW-t {summary['recomputed_pre_nw_t']}); post-2024 {summary['recomputed_post_2024_mean_ic']} "
      f"(NW-t {summary['recomputed_post_nw_t']})")
print(f"break date (single LS): {summary['break_date_ls']}")
print("\n=== SUB-FAMILY PER-YEAR IC (recomputed, 2018+) ===")
print(subfam_year.loc[subfam_year.index >= 2018].round(4).to_string())
print("\n=== PER-SIGNAL 2024-26 vs pre (recomputed) ===")
print(breadth.round(4).to_string())
print("\nDone. Outputs in", RES)
