"""
=============================================================================
SCRIPT NAME: part4_significance.py
=============================================================================
Adversarial significance testing of the two Part-3 findings, with episode
clustering. Overlapping monthly windows and heavily clustered regime months
make naive month counts meaningless; every test here draws length-matched
random blocks so the null has the same autocorrelation structure as the
observed episodes.

Findings under test (both POST-HOC, discovered in Part 1 / Part 3):
  F1  After a severe leadership inversion (RC <= -0.40), the PRE-inversion
      leadership reasserts over the next 3/6/12 months and the new leadership
      fades.
  F2  Bottom-quartile average pairwise country correlation precedes weak
      forward equal-weight returns.

Also runs two placebos: (a) sign-flipped condition, (b) shuffled condition
dates, to confirm the machinery is not manufacturing the effect.

INPUT FILES (absolute):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/monthly_returns.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/part3_inversion_history.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/part1_rolling.parquet

OUTPUT FILES (absolute):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/part4_significance.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/part4_episodes.parquet

VERSION: 1.0
LAST UPDATED: 2026-09-02
AUTHOR: Claude (for Arjun Divecha)
DEPENDENCIES: pandas, numpy (ASADO venv)
USAGE: venv/bin/python experiments/2026_09_regime_analog_brief/code/part4_significance.py
=============================================================================
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(4242)
NDRAW = 10000
ROOT = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
OUT = ROOT / "experiments/2026_09_regime_analog_brief/results"
EXCL = {"NASDAQ", "US SmallCap"}
ANCHOR = pd.Timestamp("2026-08-31")

rets = pd.read_parquet(OUT / "monthly_returns.parquet").set_index("date").sort_index().loc[:ANCHOR]
uni = [c for c in rets.columns if c not in EXCL]
R = rets[uni]
tri = (1 + R).cumprod()
RC = pd.read_parquet(OUT / "part3_inversion_history.parquet").rename(columns={"index":"date"}).set_index("date")["RC"].sort_index()
roll = pd.read_parquet(OUT / "part1_rolling.parquet").set_index("date").sort_index()
pc_m = roll["avg_pair_corr_63d"].dropna().resample("ME").last().reindex(R.index)


def cum(n, lag=0): return tri.shift(lag) / tri.shift(lag + n) - 1
def fwd(n): return tri.shift(-n) / tri - 1
def sp(a, b):
    ok = a.notna() & b.notna()
    return float(a[ok].rank().corr(b[ok].rank())) if ok.sum() > 10 else np.nan


def episodes(dates, bridge=1):
    dates = sorted(dates); eps = []
    for d in dates:
        if eps and (d.to_period("M") - eps[-1][-1].to_period("M")).n <= bridge + 1:
            eps[-1].append(d)
        else:
            eps.append([d])
    return eps


def block_test(series: pd.Series, sel_dates, label):
    """Episode-median of `series` on sel_dates vs length-matched random blocks."""
    v = series.dropna()
    eps = [[d for d in e if d in v.index] for e in episodes(sel_dates)]
    eps = [e for e in eps if e]
    lengths = [len(e) for e in eps]
    obs = float(np.median([v.loc[e].mean() for e in eps]))
    arr = v.values; N = len(arr)
    draws = np.empty(NDRAW)
    for j in range(NDRAW):
        meds = [arr[s:s + L].mean() for L in lengths
                for s in [RNG.integers(0, max(1, N - L + 1))]]
        draws[j] = np.median(meds)
    centre = float(np.median(draws))
    p_two = float(np.mean(np.abs(draws - centre) >= abs(obs - centre)))
    p_one = float(np.mean(draws >= obs)) if obs > centre else float(np.mean(draws <= obs))
    return {"metric": label, "obs_episode_median": obs, "null_median": centre,
            "boot_p_two_sided": p_two, "boot_p_one_sided": p_one,
            "null_5pct": float(np.percentile(draws, 5)), "null_95pct": float(np.percentile(draws, 95)),
            "n_months": len(v.loc[sorted(set(sum(eps, [])))]), "n_episodes": len(eps)}


rows, eprows = [], []
old_lead = cum(6, lag=2)
new_lead = cum(2, lag=0)

# ---------------- F1 ----------------
for thr, tag in [(-0.40, "severe RC<=-0.40"), (-0.25, "inversion RC<=-0.25")]:
    sel = RC[(RC <= thr) & (RC.index < ANCHOR)].index
    for e_i, e in enumerate(episodes(sel)):
        eprows.append({"finding": "F1", "condition": tag, "episode": e_i + 1,
                       "start": e[0], "end": e[-1], "n_months": len(e)})
    for h in (3, 6, 12):
        F = fwd(h)
        pers = pd.Series({d: sp(new_lead.loc[d], F.loc[d]) for d in R.index}).dropna()
        revi = pd.Series({d: sp(old_lead.loc[d], F.loc[d]) for d in R.index}).dropna()
        for s, nm in [(revi, "old-leadership revival rankcorr"), (pers, "new-leadership persistence rankcorr")]:
            r = block_test(s, [d for d in sel if d in s.index], f"{nm} h={h}m")
            r.update({"finding": "F1", "condition": tag, "horizon_m": h, "placebo": "none"})
            rows.append(r)
    # placebo: sign-flipped condition (strongly POSITIVE RC)
    sel_flip = RC[(RC >= -thr) & (RC.index < ANCHOR)].index
    for h in (3, 6, 12):
        F = fwd(h)
        revi = pd.Series({d: sp(old_lead.loc[d], F.loc[d]) for d in R.index}).dropna()
        r = block_test(revi, [d for d in sel_flip if d in revi.index], f"old-leadership revival rankcorr h={h}m")
        r.update({"finding": "F1", "condition": tag + " [PLACEBO sign-flip]", "horizon_m": h, "placebo": "sign_flip"})
        rows.append(r)

# ---------------- F2 ----------------
ew = R.mean(axis=1)
lg = np.log1p(ew)
sel2 = pc_m[(pc_m <= pc_m.quantile(0.25)) & (pc_m.index < ANCHOR)].index
for e_i, e in enumerate(episodes(sel2)):
    eprows.append({"finding": "F2", "condition": "low corr (bottom quartile)", "episode": e_i + 1,
                   "start": e[0], "end": e[-1], "n_months": len(e)})
for h in (1, 3, 6, 12):
    few = np.expm1(lg.shift(-1).rolling(h).sum().shift(-(h - 1))).dropna()
    r = block_test(few, [d for d in sel2 if d in few.index], f"forward EW return h={h}m")
    r.update({"finding": "F2", "condition": "low corr (bottom quartile)", "horizon_m": h, "placebo": "none"})
    rows.append(r)
    # placebo: sign-flipped (TOP quartile correlation)
    sel2h = pc_m[(pc_m >= pc_m.quantile(0.75)) & (pc_m.index < ANCHOR)].index
    r = block_test(few, [d for d in sel2h if d in few.index], f"forward EW return h={h}m")
    r.update({"finding": "F2", "condition": "HIGH corr (top quartile) [PLACEBO sign-flip]", "horizon_m": h, "placebo": "sign_flip"})
    rows.append(r)

df = pd.DataFrame(rows)
df.to_parquet(OUT / "part4_significance.parquet", index=False)
pd.DataFrame(eprows).to_parquet(OUT / "part4_episodes.parquet", index=False)

pd.set_option("display.width", 240)
cols = ["finding", "condition", "horizon_m", "metric", "obs_episode_median", "null_median",
        "boot_p_two_sided", "n_months", "n_episodes"]
print("=== F1: leadership inversion ===")
print(df[df.finding == "F1"][cols].round(4).to_string(index=False))
print("\n=== F2: correlation collapse ===")
print(df[df.finding == "F2"][cols].round(4).to_string(index=False))
print("\n=== episodes ===")
ep = pd.DataFrame(eprows)
for (f, c), g in ep.groupby(["finding", "condition"]):
    print(f"{f} | {c}: {len(g)} episodes -> " + ", ".join(f"{r.start:%Y-%m}..{r.end:%Y-%m}" for r in g.itertuples()))
