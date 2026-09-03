"""
=============================================================================
SCRIPT NAME: part6_report.py
=============================================================================
Assembles the deliverables for the 2026-09 regime-analog context brief: a
timestamped run directory holding every result parquet, a light-mode matplotlib
PDF chart pack, an xlsx workbook for eyeballing, and a JSON run summary.

INPUT FILES (absolute) - all parquets written by parts 1-5 in:
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/

OUTPUT FILES (absolute):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/run_<ts>/  (all parquets copied)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/run_<ts>/charts.pdf
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/run_<ts>/regime_analog_brief.xlsx
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/run_<ts>/run_summary.json

VERSION: 1.0
LAST UPDATED: 2026-09-02
AUTHOR: Claude (for Arjun Divecha)
DEPENDENCIES: pandas, numpy, matplotlib, xlsxwriter (ASADO venv)
USAGE: venv/bin/python experiments/2026_09_regime_analog_brief/code/part6_report.py
NOTES: Light mode only, charts as PDF, per house conventions.
=============================================================================
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd

plt.rcParams.update({"figure.facecolor": "white", "axes.facecolor": "white",
                     "savefig.facecolor": "white", "axes.grid": True,
                     "grid.color": "#DDDDDD", "grid.linewidth": 0.6,
                     "axes.edgecolor": "#444444", "font.size": 9})

ROOT = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
RES = ROOT / "experiments/2026_09_regime_analog_brief/results"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
RUN = RES / f"run_{TS}"
RUN.mkdir(parents=True, exist_ok=True)
for p in sorted(RES.glob("*.parquet")):
    shutil.copy2(p, RUN / p.name)
shutil.copy2(RES / "panel_build_log.json", RUN / "panel_build_log.json")
shutil.copy2(RES / "part2_summary.json", RUN / "part2_summary.json")

ctry = pd.read_parquet(RES / "part1_country_returns.parquet").set_index("country")
sc = pd.read_parquet(RES / "part1_narrative_scorecard.parquet").set_index("metric")
roll = pd.read_parquet(RES / "part1_rolling.parquet").set_index("date")
inv = pd.read_parquet(RES / "part3_inversion_history.parquet").rename(columns={"index": "date"}).set_index("date")
rob = pd.read_parquet(RES / "part5_robustness.parquet")
det = pd.read_parquet(RES / "part5_episode_detail.parquet")
sig = pd.read_parquet(RES / "part4_significance.parquet")
fo = pd.read_parquet(RES / "forward_outcomes.parquet")
st = pd.read_parquet(RES / "state_vector.parquet").set_index("date")

ANCHOR = pd.Timestamp("2026-08-31")

with PdfPages(RUN / "charts.pdf") as pdf:
    # 1 leadership inversion scatter
    fig, ax = plt.subplots(figsize=(9, 6.5))
    d = ctry.dropna(subset=["rank_H1"])
    ax.scatter(100 * d["ret_2026H1"], 100 * d["ret_since_Jul1"], s=34, color="#1f4e79", zorder=3)
    for c, r in d.iterrows():
        ax.annotate(c, (100 * r["ret_2026H1"], 100 * r["ret_since_Jul1"]), fontsize=7,
                    xytext=(3, 3), textcoords="offset points", color="#333333")
    ax.axhline(0, color="#888888", lw=0.8); ax.axvline(0, color="#888888", lw=0.8)
    ax.set_xlabel("2026 H1 total return (%)"); ax.set_ylabel("2026-07-01 to 2026-09-02 total return (%)")
    rho = d["ret_2026H1"].corr(d["ret_since_Jul1"], method="spearman")
    ax.set_title(f"Leadership inverted after 1 July 2026\nSpearman rank correlation = {rho:.2f} (32-country universe)")
    pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)

    # 2 inversion history
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(inv.index, inv["RC"], color="#1f4e79", lw=1.0)
    ax.axhline(-0.40, color="#c00000", ls="--", lw=1.0, label="severe inversion threshold (-0.40)")
    ax.axhline(0, color="#888888", lw=0.8)
    ax.scatter([ANCHOR], [inv.loc[ANCHOR, "RC"]], color="#c00000", s=55, zorder=5,
               label=f"2026-08-31 = {inv.loc[ANCHOR,'RC']:.2f} ({100*inv.loc[ANCHOR,'RC_pctile']:.0f}th pctile)")
    ax.set_ylabel("rank corr: prior-6m vs last-2m country returns")
    ax.set_title("Country-leadership inversion index, 2000-2026")
    ax.legend(fontsize=8, loc="lower left")
    pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)

    # 3 correlation / vol / dispersion
    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    for a, (col, lab) in zip(axes, [("avg_pair_corr_63d", "avg pairwise country correlation (63d)"),
                                    ("vol_mean", "mean 20-day country volatility"),
                                    ("disp_63d", "cross-sectional dispersion of daily returns (63d mean)")]):
        s = roll[col].dropna()
        a.plot(s.index, s.values, color="#1f4e79", lw=0.9)
        a.axvline(pd.Timestamp("2026-07-01"), color="#c00000", ls="--", lw=1.0)
        a.set_ylabel(lab, fontsize=8)
        a.annotate(f"latest {s.iloc[-1]:.3f}\n({100*(s < s.iloc[-1]).mean():.0f}th pctile)",
                   xy=(0.995, 0.9), xycoords="axes fraction", ha="right", fontsize=8, color="#c00000")
    axes[0].set_title("What actually changed after 1 July 2026 (red line)")
    pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)

    # 4 F1 per-episode
    fig, ax = plt.subplots(figsize=(9, 5))
    d6 = det[det.horizon_m == 6].copy()
    d6["lab"] = d6["episode_start"].dt.strftime("%Y-%m")
    colors = ["#1f4e79" if v > 0 else "#c00000" for v in d6["revival_rankcorr"]]
    ax.bar(d6["lab"], d6["revival_rankcorr"], color=colors)
    med = float(np.median(d6["revival_rankcorr"]))
    ax.axhline(med, color="#1f4e79", ls="--", lw=1.2, label=f"episode median {med:.2f}")
    ax.axhline(0.048, color="#888888", ls=":", lw=1.2, label="unconditional median 0.05")
    ax.set_ylabel("rank corr: pre-inversion leadership vs next 6m returns")
    ax.set_title("After a SEVERE leadership inversion, the OLD leadership tends to come back\n"
                 "21 episodes, 2000-2026; red = the 5 failures (2008, 2009, 2016, 2022)")
    plt.setp(ax.get_xticklabels(), rotation=60, ha="right", fontsize=7)
    ax.legend(fontsize=8)
    pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)

    # 5 robustness
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    sw = rob[rob.test.str.startswith("R4") & (rob.horizon_m == 6)].copy()
    sw["thr"] = sw["test"].str.extract(r"RC<=(-?\d+\.?\d*)").astype(float)
    sw = sw.sort_values("thr")
    axes[0].plot(sw["thr"], sw["value"], marker="o", color="#1f4e79")
    axes[0].axhline(0.048, color="#888888", ls=":", label="unconditional")
    axes[0].set_xlabel("inversion threshold (RC <=)"); axes[0].set_ylabel("6m revival rank corr")
    axes[0].set_title("Dose-response: effect lives in the tail"); axes[0].legend(fontsize=8)
    sub = rob[rob.test.isin(["R0 headline", "R1 jackknife min", "R1 jackknife max", "R2 2000-2012",
                             "R2 2013-2026", "R3 ex-crisis", "R5 placebo null 95pct"])]
    piv = sub.pivot_table(index="test", columns="horizon_m", values="value", sort=False)
    piv.plot(kind="barh", ax=axes[1], color=["#8db3d9", "#1f4e79", "#0d2b45"])
    axes[1].axvline(0, color="#888888", lw=0.8)
    axes[1].set_xlabel("revival rank corr"); axes[1].set_title("Robustness (bars = 3m / 6m / 12m)")
    axes[1].legend(title="horizon (m)", fontsize=8)
    plt.setp(axes[1].get_yticklabels(), fontsize=7)
    pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)

    # 6 pre-registered analog screens null
    fig, ax = plt.subplots(figsize=(9, 4.6))
    h = fo[fo.outcome.isin(["EW", "EW_minus_CW", "NASDAQ_minus_EW", "Momentum_LS"])]
    ax.scatter(h["unconditional_median"], h["episode_median"], c=np.where(h["boot_p"] < 0.05, "#c00000", "#1f4e79"), s=30)
    lim = [min(h["unconditional_median"].min(), h["episode_median"].min()) - 0.02,
           max(h["unconditional_median"].max(), h["episode_median"].max()) + 0.02]
    ax.plot(lim, lim, color="#888888", ls="--", lw=1)
    ax.set_xlabel("unconditional median forward outcome"); ax.set_ylabel("analog-episode median forward outcome")
    ax.set_title("Pre-registered state-vector analogs add nothing\n"
                 f"{len(h)} screen x outcome x horizon cells; {int((h['boot_p']<0.05).sum())} at p<0.05 "
                 f"(chance alone gives ~{0.05*len(h):.0f})")
    pdf.savefig(fig, bbox_inches="tight"); plt.close(fig)

# ---------------- xlsx
with pd.ExcelWriter(RUN / "regime_analog_brief.xlsx", engine="xlsxwriter") as xl:
    sc.to_excel(xl, sheet_name="1_narrative_scorecard")
    ctry.to_excel(xl, sheet_name="1_country_returns")
    st.tail(24).to_excel(xl, sheet_name="1_state_vector_recent")
    pd.read_parquet(RES / "analog_episodes.parquet").to_excel(xl, sheet_name="2_analog_episodes", index=False)
    fo.to_excel(xl, sheet_name="2_forward_outcomes", index=False)
    pd.read_parquet(RES / "forward_country_table.parquet").to_excel(xl, sheet_name="2_forward_by_country", index=False)
    pd.read_parquet(RES / "part3_rotation_persistence.parquet").to_excel(xl, sheet_name="3_rotation_persistence", index=False)
    pd.read_parquet(RES / "part3_lowcorr.parquet").to_excel(xl, sheet_name="3_low_correlation", index=False)
    sig.to_excel(xl, sheet_name="4_significance", index=False)
    rob.to_excel(xl, sheet_name="5_robustness", index=False)
    det.to_excel(xl, sheet_name="5_episode_detail", index=False)
    inv.to_excel(xl, sheet_name="5_inversion_history")

summary = {
    "run_dir": str(RUN), "run_ts": TS,
    "data_as_of": {"daily_t2": "2026-09-02", "monthly_t2_panel": "2026-08-01",
                   "wb_brent": "2026-07 (stale, flagged *)", "factor_returns": "2026-07-01"},
    "part1": {"spearman_H1_vs_sinceJul1": float(ctry.dropna(subset=["rank_H1"])["ret_2026H1"]
                                                .corr(ctry.dropna(subset=["rank_H1"])["ret_since_Jul1"], method="spearman")),
              "avg_pair_corr_H1": float(sc.loc["avg_pairwise_corr", "2026_H1"]),
              "avg_pair_corr_since_Jul1": float(sc.loc["avg_pairwise_corr", "since_Jul1"]),
              "US10Y_chg_bp_since_Jul1": float(sc.loc["US10Y_chg_bp", "since_Jul1"])},
    "part2_verdict": "NULL - pre-registered state-vector analogs indistinguishable from unconditional",
    "part4_F2_verdict": "DEAD under episode clustering (p 0.27-0.98)",
    "part5_F1": {"6m_revival_rankcorr": 0.2656, "12m_revival_rankcorr": 0.2107,
                 "econ_spread_6m": 0.0585, "n_episodes": 21, "hit_rate": 0.762,
                 "status": "POST-HOC, survives jackknife/placebo/ex-crisis; 12m fails post-2013"},
}
(RUN / "run_summary.json").write_text(json.dumps(summary, indent=2))
print("RUN DIR:", RUN)
for f in sorted(RUN.iterdir()):
    print("  ", f.name)
