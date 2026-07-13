"""
=============================================================================
SCRIPT NAME: a4_crowding.py
=============================================================================

WHAT THIS PROGRAM DOES:
Step (iii) of the G1 flip autopsy (PRD section 6): crowding forensics on the
network_spillover family's OWN portfolios. Builds the family composite score
(equal-weight mean of the 16 roster signals' cross-sectional z-scores,
sign-aligned so higher = "buy"), forms monthly top-7 / bottom-7 country
portfolios, and asks whether the countries the signal was BUYING absorbed
abnormal ETF inflows during 2021-2023 that reversed in 2024-26 (the
pre-registered crowding signature), plus the split-half test: are the family's
2024-26 losses concentrated in the previously-high-inflow half of the top
portfolio?

Pre-registered signature for verdict (a) — BOTH must hold (PRD section 6):
  S1  top-portfolio abnormal inflow z >= +1 sustained over 2021-2023, with
      reversal in 2024-26;
  S2  2024-26 long-leg underperformance concentrated in the previously-high-
      inflow half of the top portfolio (split by trailing 24m cumulative
      abnormal flow-to-mcap).

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13/graph_features_daily.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13/graph_features_pit_daily.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13/leadlag_features_daily.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13/similarity_features_daily.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13/bloomberg_factors.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13/country_returns_monthly.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/harness_runs/*.json (roster + directions)

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/a4_crowding.xlsx
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/a4_summary.json
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/figures/a4_crowding.pdf

VERSION: 1.0  |  LAST UPDATED: 2026-07-13  |  AUTHOR: Claude (G1 flip autopsy)
DEPENDENCIES: pandas, numpy, matplotlib, openpyxl (production venv). No DB.
USAGE: venv/bin/python experiments/2026_07_flip_autopsy/a4_crowding.py
NOTES: flow data (MS_*) begins 2015-01 -> the crowding window is fully covered.
=============================================================================
"""
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
SNAP = ROOT / "Data/work/experiments/flip_autopsy/snapshot_2026_07_13"
RES = ROOT / "experiments/2026_07_flip_autopsy/results"
FIG = RES / "figures"
RUNS = ROOT / "Data/loop/harness_runs"

# roster + directions (same rule as a2)
rows = []
for f in sorted(RUNS.glob("H_*.json")):
    o = json.loads(f.read_text())
    var = (o.get("signal_spec") or {}).get("variable", "")
    if re.match(r"^(GRAPH|LL_|SIM_)", var):
        rows.append({"hypothesis_id": o["hypothesis_id"], "variable": var,
                     "table": (o.get("signal_spec") or {}).get("table"),
                     "direction": o.get("direction"), "run_ts": o.get("run_ts"),
                     "verdict": o.get("verdict")})
js = pd.DataFrame(rows).sort_values("run_ts").groupby("hypothesis_id", as_index=False).tail(1)
roster = (js[js["verdict"].isin(["WEAK", "WATCH"])]
          .sort_values("run_ts").groupby("variable", as_index=False).tail(1))

TABLES = {t: pd.read_parquet(SNAP / f"{t}.parquet") for t in
          ["graph_features_daily", "graph_features_pit_daily",
           "leadlag_features_daily", "similarity_features_daily"]}
for v in TABLES.values():
    v["date"] = pd.to_datetime(v["date"])

# family composite: per (date,country), mean of sign-aligned cross-sectional z
parts = []
for _, r in roster.iterrows():
    tab = TABLES[r["table"]]
    s = tab[tab["variable"] == r["variable"]][["date", "country", "value"]].dropna()
    sign = -1.0 if r["direction"] == "lower_is_better" else 1.0
    z = s.groupby("date")["value"].transform(lambda g: (g - g.mean()) / (g.std() or np.nan))
    s = s.assign(z=sign * z)[["date", "country", "z"]]
    parts.append(s)
comp = (pd.concat(parts).groupby(["date", "country"])["z"].mean()
        .rename("score").reset_index())
comp["month"] = comp["date"].dt.to_period("M").dt.to_timestamp()
comp_m = comp.groupby(["month", "country"])["score"].mean().reset_index()

# flows
bbg = pd.read_parquet(SNAP / "bloomberg_factors.parquet")
bbg["date"] = pd.to_datetime(bbg["date"])
fl = bbg[bbg["variable"] == "MS_ETF_NetFlow_to_MarketCap"].copy()
fl["month"] = fl["date"].dt.to_period("M").dt.to_timestamp()
fl = fl.groupby(["month", "country"])["value"].mean().rename("flow").reset_index()
xmean = fl.groupby("month")["flow"].transform("mean")
fl["abn_flow"] = fl["flow"] - xmean   # abnormal vs 34-country mean

# returns
crm = pd.read_parquet(SNAP / "country_returns_monthly.parquet")
crm["month"] = pd.to_datetime(crm["date"]).dt.to_period("M").dt.to_timestamp()
ew = crm.groupby("month")["return_1m"].mean().rename("ew")

# top/bottom membership per month
def top_bottom(g, n=7):
    g = g.sort_values("score")
    return pd.Series({"top": set(g.tail(n)["country"]), "bot": set(g.head(n)["country"])})
tb = comp_m.groupby("month").apply(top_bottom, include_groups=False)

# S1: abnormal flow into the top portfolio over time
m_rows = []
for month, r in tb.iterrows():
    f_m = fl[fl["month"] == month]
    top_f = f_m[f_m["country"].isin(r["top"])]["abn_flow"].mean()
    bot_f = f_m[f_m["country"].isin(r["bot"])]["abn_flow"].mean()
    m_rows.append({"month": month, "top_abn_flow": top_f, "bot_abn_flow": bot_f})
tf = pd.DataFrame(m_rows).dropna().set_index("month").sort_index()
mu, sd = tf["top_abn_flow"].mean(), tf["top_abn_flow"].std()
tf["top_flow_z"] = (tf["top_abn_flow"] - mu) / sd
z_2123 = float(tf.loc["2021-01-01":"2023-12-31", "top_flow_z"].mean())
z_2426 = float(tf.loc["2024-01-01":, "top_flow_z"].mean())
S1 = bool(z_2123 >= 1.0 and z_2426 < z_2123 - 0.5)

# S2: split-half of the top portfolio by trailing 24m cumulative abnormal flow
fl_c = fl.pivot(index="month", columns="country", values="abn_flow").sort_index()
cum24 = fl_c.rolling(24, min_periods=12).sum()
ret_p = crm.pivot_table(index="month", columns="country", values="return_1m")
half_rows = []
for month, r in tb.iterrows():
    if month < pd.Timestamp("2024-01-01") or month not in cum24.index:
        continue
    # composite aggregated within month m; trade at m's end -> NEXT month's return
    # (same-month returns are mechanically negative for gap signals, which buy laggards)
    nxt = month + pd.offsets.MonthBegin(1)
    members = [c for c in r["top"] if c in cum24.columns and not np.isnan(cum24.loc[month, c])]
    if len(members) < 4 or nxt not in ret_p.index:
        continue
    ranked = sorted(members, key=lambda c: cum24.loc[month, c])
    lo, hi = ranked[:len(ranked)//2], ranked[len(ranked)//2:]
    ew_m = ret_p.loc[nxt].mean()
    half_rows.append({"month": month,
                      "hi_inflow_half_exret": ret_p.loc[nxt, hi].mean() - ew_m,
                      "lo_inflow_half_exret": ret_p.loc[nxt, lo].mean() - ew_m})
halves = pd.DataFrame(half_rows).set_index("month")
hi_mean = float(halves["hi_inflow_half_exret"].mean())
lo_mean = float(halves["lo_inflow_half_exret"].mean())
S2 = bool(hi_mean < lo_mean and hi_mean < 0)

summary = {
    "S1_top_flow_z_2021_23": round(z_2123, 3),
    "S1_top_flow_z_2024_26": round(z_2426, 3),
    "S1_pass": S1,
    "S2_hi_inflow_half_exret_2024_26_monthly": round(hi_mean, 5),
    "S2_lo_inflow_half_exret_2024_26_monthly": round(lo_mean, 5),
    "S2_n_months": int(len(halves)),
    "S2_pass": S2,
    "verdict_a_crowding": "CONFIRMED" if (S1 and S2) else
                          ("PARTIAL" if (S1 or S2) else "REJECTED"),
    "note": "flows observable 2015+; abnormal = country flow-to-mcap minus 34-country mean",
}
(RES / "a4_summary.json").write_text(json.dumps(summary, indent=2))

with pd.ExcelWriter(RES / "a4_crowding.xlsx") as xw:
    tf.to_excel(xw, sheet_name="top_bottom_abn_flow")
    halves.to_excel(xw, sheet_name="split_half_2024_26")

fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
axes[0].plot(tf.index, tf["top_flow_z"].rolling(6).mean(), color="#1a6faf", lw=1.6,
             label="top-7 abnormal flow z (6m sm.)")
axes[0].plot(tf.index, tf["bot_abn_flow"].rolling(6).mean() / sd, color="#999", lw=1.2,
             label="bottom-7 (same scale)")
axes[0].axhline(1.0, color="#c0392b", ls=":", lw=1)
axes[0].axhline(0, color="#888", lw=0.8)
axes[0].legend(frameon=False); axes[0].set_title("Abnormal ETF flow into the family's own portfolios")
cum = (halves + 0).cumsum()
axes[1].plot(cum.index, cum["hi_inflow_half_exret"], color="#c0392b", lw=1.6,
             label="top-7, previously HIGH-inflow half (cum. excess ret)")
axes[1].plot(cum.index, cum["lo_inflow_half_exret"], color="#27ae60", lw=1.6,
             label="top-7, previously LOW-inflow half")
axes[1].axhline(0, color="#888", lw=0.8)
axes[1].legend(frameon=False); axes[1].set_title("2024-26: where do the long-leg losses sit?")
for ax in axes:
    ax.set_facecolor("white")
fig.patch.set_facecolor("white")
fig.tight_layout(); fig.savefig(FIG / "a4_crowding.pdf")

print("=== STEP (iii) CROWDING ===")
print(f"S1 top-portfolio abnormal-flow z: 2021-23 = {z_2123:+.2f}, 2024-26 = {z_2426:+.2f}  -> S1={'PASS' if S1 else 'FAIL'}")
print(f"S2 2024-26 monthly excess return: high-inflow half {hi_mean:+.4f} vs low-inflow half {lo_mean:+.4f} "
      f"(n={len(halves)})  -> S2={'PASS' if S2 else 'FAIL'}")
print(f"verdict (a) crowding: {summary['verdict_a_crowding']}")
print("Done. Outputs in", RES)
