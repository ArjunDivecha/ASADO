"""
=============================================================================
SCRIPT NAME: r1_throttle_test.py
=============================================================================

WHAT THIS PROGRAM DOES:
Runs the R1 dispersion-throttle experiment exactly as pre-registered in
PRD.md (commit 8beeeea): builds the daily long-short combiner book (top-7 /
bottom-7 by COMBINER_RIDGE_DAILY_V1 score, 1-day implementation lag, gross),
then evaluates four arms — (a) unthrottled baseline, (b) dispersion throttle
g = clip(expanding_median(s)/s, 0.25, 1.0) on the EWMA-smoothed 21d cross-
sectional dispersion state, (c) an identical-shape vol-target control on the
book's own trailing 63d realized vol, and (d) a 500-draw circular-shift
placebo of the dispersion series. Reports the five pre-registered gates
(Sharpe delta >= +0.10, shallower MDD, skew loss <= 0.10, beats vol-target by
>= 0.05, beats 95% of placebo) plus subperiod honesty splits, and writes all
artifacts incrementally. All constants are the PRD's frozen values — there is
no parameter search in this script.

INPUT FILES (frozen snapshot, shared with the G1 autopsy; no DB access):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13/combiner_scores_daily.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13/t2_1dret_daily.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13/country_returns_monthly.parquet

OUTPUT FILES (all under the experiment's results dir):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_dispersion_throttle/results/r1_daily_book.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_dispersion_throttle/results/r1_metrics.xlsx
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_dispersion_throttle/results/r1_summary.json
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_dispersion_throttle/results/figures/r1_curves.pdf

VERSION: 1.0  |  LAST UPDATED: 2026-07-13  |  AUTHOR: Claude (R1)
DEPENDENCIES: pandas, numpy, scipy, matplotlib, openpyxl (production venv)
USAGE: venv/bin/python experiments/2026_07_dispersion_throttle/r1_throttle_test.py
NOTES: placebo seed 20260713 — deterministic. Gross returns only (PRD).
=============================================================================
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
SNAP = ROOT / "Data/work/experiments/flip_autopsy/snapshot_2026_07_13"
RES = ROOT / "experiments/2026_07_dispersion_throttle/results"
FIG = RES / "figures"
FIG.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(20260713)

START = "2005-01-01"
N_SIDE = 7
LAM = 0.8            # EWMA smoothing
G_LO, G_HI = 0.25, 1.00
MIN_EXP_DAYS = 756   # 3y expanding minimum
VOL_WIN = 63
DISP_WIN = 21

# ------------------------------------------------------------- daily returns
ret = pd.read_parquet(SNAP / "t2_1dret_daily.parquet")
ret["date"] = pd.to_datetime(ret["date"])
ret = ret.sort_values(["country", "date"]).reset_index(drop=True)
ret["r"] = ret.groupby("country")["value"].shift(1)
ret = ret.dropna(subset=["r"])
ret = ret[ret["r"] != 0.0]
rp = ret.pivot(index="date", columns="country", values="r").sort_index()

# ------------------------------------------------------------- combiner book
cs = pd.read_parquet(SNAP / "combiner_scores_daily.parquet")
cs["date"] = pd.to_datetime(cs["date"])
sp = cs.pivot_table(index="date", columns="country", values="value").sort_index()

book_rows = []
dates = rp.index
for i, d in enumerate(dates[:-1]):
    if d not in sp.index:
        continue
    row = sp.loc[d].dropna()
    if len(row) < 20:
        continue
    ranked = row.sort_values()
    top, bot = list(ranked.tail(N_SIDE).index), list(ranked.head(N_SIDE).index)
    nxt = dates[i + 1]
    r_next = rp.loc[nxt]
    lt, lb = r_next.reindex(top).dropna(), r_next.reindex(bot).dropna()
    if len(lt) < 4 or len(lb) < 4:
        continue
    book_rows.append({"date": nxt, "r_book": float(lt.mean() - lb.mean())})
book = pd.DataFrame(book_rows).set_index("date")["r_book"].sort_index()
book = book[book.index >= START]
print(f"book days: {len(book)}  ({book.index.min():%Y-%m-%d} .. {book.index.max():%Y-%m-%d})")

# ------------------------------------------------------------- states
# D1: cross-sectional std of trailing 21d returns, EWMA smoothed
r21 = rp.rolling(DISP_WIN).apply(lambda x: np.expm1(np.log1p(x).sum()), raw=True)
disp_raw = r21.std(axis=1)
disp = disp_raw.ewm(alpha=1 - LAM).mean()

# D2: monthly cross-sectional std, ffilled daily, same smoothing
crm = pd.read_parquet(SNAP / "country_returns_monthly.parquet")
crm["month"] = pd.to_datetime(crm["date"]).dt.to_period("M").dt.to_timestamp()
d2m = crm.groupby("month")["return_1m"].std()
d2 = d2m.reindex(pd.date_range(d2m.index.min(), rp.index.max(), freq="D")).ffill()
d2 = d2.reindex(rp.index).ffill().ewm(alpha=1 - LAM).mean()

# book own-vol (63d realized, annualized irrelevant - same units cancel)
book_vol = book.rolling(VOL_WIN).std()


def throttle(state: pd.Series, ref_index) -> pd.Series:
    s = state.reindex(ref_index).ffill()
    med = s.expanding(MIN_EXP_DAYS).median()
    g = (med / s).clip(G_LO, G_HI)
    return g


def apply_overlay(book: pd.Series, g: pd.Series) -> pd.Series:
    # g known end of day t -> applied to day t+1's book return (1-day lag)
    return (book * g.shift(1).reindex(book.index)).dropna()


def metrics(x: pd.Series) -> dict:
    x = x.dropna()
    ann = 252
    sharpe = float(x.mean() / x.std() * np.sqrt(ann)) if x.std() > 0 else np.nan
    cum = (1 + x).cumprod()
    mdd = float((cum / cum.cummax() - 1).min())
    years = len(x) / ann
    cagr = float(cum.iloc[-1] ** (1 / years) - 1) if years > 0 else np.nan
    m = x.groupby(x.index.to_period("M")).apply(lambda g: (1 + g).prod() - 1)
    from scipy import stats as sstats
    skew = float(sstats.skew(m.dropna())) if len(m) > 12 else np.nan
    return {"sharpe": round(sharpe, 3), "cagr": round(cagr, 4), "mdd": round(mdd, 4),
            "calmar": round(cagr / abs(mdd), 3) if mdd else np.nan,
            "skew_monthly": round(skew, 3), "n_days": len(x)}


g_d1 = throttle(disp, book.index)
g_d2 = throttle(d2, book.index)
g_vt = throttle(book_vol, book.index)

arm = {
    "a_baseline": book,
    "b_disp_D1": apply_overlay(book, g_d1),
    "b2_disp_D2": apply_overlay(book, g_d2),
    "c_voltarget": apply_overlay(book, g_vt),
}
# align all arms to the common index where D1 multiplier exists (post 3y warmup)
common = arm["b_disp_D1"].index.intersection(arm["c_voltarget"].index).intersection(
    arm["b2_disp_D2"].index)
arm = {k: v.reindex(common).dropna() for k, v in arm.items()}
common = arm["a_baseline"].index
print(f"evaluation days (post-warmup, common): {len(common)}  "
      f"({common.min():%Y-%m-%d} .. {common.max():%Y-%m-%d})")

full = {k: metrics(v) for k, v in arm.items()}
subs = {}
for name, lo, hi in [("2005_2015", "2005-01-01", "2015-12-31"),
                     ("2016_2023", "2016-01-01", "2023-12-31"),
                     ("2024_2026", "2024-01-01", "2027-01-01")]:
    subs[name] = {k: metrics(v[(v.index >= lo) & (v.index <= hi)]) for k, v in arm.items()}

# turnover of the multiplier (mean |dg| per month)
g_turn = float(g_d1.diff().abs().resample("ME").sum().mean())

# ------------------------------------------------------------- placebo
base_sharpe = full["a_baseline"]["sharpe"]
real_delta = full["b_disp_D1"]["sharpe"] - base_sharpe
disp_v = disp.reindex(book.index).ffill().values
deltas = []
for _ in range(500):
    off = int(RNG.integers(250, 4000))
    shifted = pd.Series(np.roll(disp_v, off), index=book.index)
    g_p = throttle(shifted, book.index)
    x = apply_overlay(book, g_p).reindex(common).dropna()
    if len(x) < 1000:
        continue
    deltas.append(metrics(x)["sharpe"] - base_sharpe)
deltas = np.array(deltas)
placebo_pct = float((real_delta > deltas).mean())

# ------------------------------------------------------------- gates
b, a, c = full["b_disp_D1"], full["a_baseline"], full["c_voltarget"]
G1 = bool(b["sharpe"] - a["sharpe"] >= 0.10)
G2 = bool(b["mdd"] > a["mdd"])          # mdd is negative; shallower = greater
G3 = bool(b["skew_monthly"] >= a["skew_monthly"] - 0.10)
G4 = bool(b["sharpe"] - c["sharpe"] >= 0.05)
G5 = bool(placebo_pct >= 0.95)
verdict = "ALIVE" if all([G1, G2, G3, G4, G5]) else "DEAD"
failing = [g for g, ok in zip(["G1_sharpe", "G2_mdd", "G3_skew", "G4_beats_voltarget",
                               "G5_placebo"], [G1, G2, G3, G4, G5]) if not ok]

summary = {
    "verdict": verdict, "failing_gates": failing,
    "full_sample": full, "subperiods": subs,
    "real_sharpe_delta_vs_baseline": round(real_delta, 3),
    "placebo_pct_beaten": round(placebo_pct, 3), "n_placebo": int(len(deltas)),
    "multiplier_mean_abs_dg_per_month": round(g_turn, 4),
    "mean_g_d1": round(float(g_d1.mean()), 3),
    "share_days_at_floor": round(float((g_d1 <= G_LO + 1e-9).mean()), 3),
    "prd_commit": "8beeeea", "seed": 20260713,
}
(RES / "r1_summary.json").write_text(json.dumps(summary, indent=2))

pd.DataFrame({"r_baseline": arm["a_baseline"], "r_disp_D1": arm["b_disp_D1"],
              "r_disp_D2": arm["b2_disp_D2"], "r_voltarget": arm["c_voltarget"],
              "g_d1": g_d1.reindex(common), "g_d2": g_d2.reindex(common),
              "g_vt": g_vt.reindex(common)}).to_parquet(RES / "r1_daily_book.parquet")

with pd.ExcelWriter(RES / "r1_metrics.xlsx") as xw:
    pd.DataFrame(full).T.to_excel(xw, sheet_name="full_sample")
    for k, v in subs.items():
        pd.DataFrame(v).T.to_excel(xw, sheet_name=k)
    pd.DataFrame({"placebo_sharpe_delta": deltas}).to_excel(xw, sheet_name="placebo", index=False)

fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True,
                         gridspec_kw={"height_ratios": [2.2, 1]})
for k, color in [("a_baseline", "#888"), ("b_disp_D1", "#1a6faf"),
                 ("c_voltarget", "#e67e22")]:
    cum = (1 + arm[k]).cumprod()
    axes[0].plot(cum.index, cum.values, lw=1.5, color=color, label=k)
axes[0].set_yscale("log"); axes[0].legend(frameon=False)
axes[0].set_title("Combiner LS book: baseline vs dispersion throttle vs vol-target control (gross)")
axes[1].plot(g_d1.index, g_d1.values, lw=1.0, color="#1a6faf", label="g (dispersion D1)")
axes[1].plot(g_vt.index, g_vt.values, lw=1.0, color="#e67e22", alpha=0.7, label="g (vol target)")
axes[1].set_ylim(0, 1.05); axes[1].legend(frameon=False)
for ax in axes:
    ax.set_facecolor("white")
fig.patch.set_facecolor("white")
fig.tight_layout(); fig.savefig(FIG / "r1_curves.pdf")

print("\n=== R1 FULL SAMPLE (gross) ===")
print(pd.DataFrame(full).T.to_string())
print(f"\nreal Sharpe delta vs baseline: {real_delta:+.3f} | placebo beaten: {placebo_pct:.1%} (n={len(deltas)})")
print(f"multiplier: mean g={summary['mean_g_d1']}, |dg|/month={g_turn:.4f}, days at floor={summary['share_days_at_floor']:.1%}")
print(f"\nGates: G1={G1} G2={G2} G3={G3} G4={G4} G5={G5}  ->  VERDICT: {verdict}"
      + (f"  (failed: {failing})" if failing else ""))
print("\n=== SUBPERIODS (Sharpe a/b/c) ===")
for k, v in subs.items():
    print(f"{k}: baseline {v[k2]['sharpe'] if (k2:='a_baseline') else ''} | disp {v['b_disp_D1']['sharpe']} | voltgt {v['c_voltarget']['sharpe']}")
print("\nDone. Outputs in", RES)
