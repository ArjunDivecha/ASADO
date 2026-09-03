"""
=============================================================================
SCRIPT NAME: part3_rotation.py
=============================================================================
Part 3 of the 2026-09 regime-analog context brief. Part 1 found that the real
post-2026-07-01 change is a LEADERSHIP INVERSION plus a collapse in average
pairwise country correlation - not an inflation/volatility stress regime. This
script asks the two directly-answerable historical questions that follow:

  Q1  After a leadership inversion of this severity, does the NEW leadership
      persist, or does the OLD leadership come back?
  Q2  What has historically followed a collapse in average pairwise country
      correlation to this level?

Both are POST-HOC cuts motivated by Part 1 - they are not in SPEC.md's
pre-registration and are labelled as such wherever reported.

INPUT FILES (absolute):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/monthly_returns.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/part1_rolling.parquet

OUTPUT FILES (absolute):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/part3_rotation_persistence.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/part3_lowcorr.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/part3_inversion_history.parquet

VERSION: 1.0
LAST UPDATED: 2026-09-02
AUTHOR: Claude (for Arjun Divecha)
DEPENDENCIES: pandas, numpy, scipy (ASADO venv)
USAGE: venv/bin/python experiments/2026_09_regime_analog_brief/code/part3_rotation.py
NOTES: Trailing-only inputs; forward returns built from the monthly total-return
       panel, never from the T2 forward-return family.
=============================================================================
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(20260902)
ROOT = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
OUT = ROOT / "experiments/2026_09_regime_analog_brief/results"
EXCL = {"NASDAQ", "US SmallCap"}
ANCHOR = pd.Timestamp("2026-08-31")

rets = pd.read_parquet(OUT / "monthly_returns.parquet").set_index("date").sort_index().loc[:ANCHOR]
uni = [c for c in rets.columns if c not in EXCL]
R = rets[uni]
tri = (1 + R).cumprod()


def cum(n: int, lag: int = 0) -> pd.DataFrame:
    """Trailing n-month return ending `lag` months before t."""
    return tri.shift(lag) / tri.shift(lag + n) - 1


def fwd(n: int) -> pd.DataFrame:
    return tri.shift(-n) / tri - 1


def sp(a: pd.Series, b: pd.Series) -> float:
    ok = a.notna() & b.notna()
    return float(a[ok].rank().corr(b[ok].rank())) if ok.sum() > 10 else np.nan


# ---------------- Q1: leadership inversion ----------------------------------
# RC(t) = rank corr between the trailing 6m return through t-2 and the last 2m return.
old_lead = cum(6, lag=2)
new_lead = cum(2, lag=0)
RC = pd.Series({d: sp(old_lead.loc[d], new_lead.loc[d]) for d in R.index}, name="RC").sort_index()

hist = pd.DataFrame({"RC": RC})
hist["RC_pctile"] = RC.rank(pct=True)
hist.reset_index().to_parquet(OUT / "part3_inversion_history.parquet", index=False)

now_rc = RC.loc[ANCHOR]
now_pct = hist.loc[ANCHOR, "RC_pctile"]

rows = []
for h in (3, 6, 12):
    F = fwd(h)
    # persistence: does the NEW leadership keep leading?
    pers = pd.Series({d: sp(new_lead.loc[d], F.loc[d]) for d in R.index}, name=f"pers_{h}")
    # revival: does the OLD leadership come back?
    revi = pd.Series({d: sp(old_lead.loc[d], F.loc[d]) for d in R.index}, name=f"revi_{h}")
    for label, thresh in [("inversion RC<=-0.25", RC <= -0.25), ("severe RC<=-0.40", RC <= -0.40),
                          ("all months", pd.Series(True, index=RC.index))]:
        m = thresh & pers.notna()
        n = int(m.sum())
        if n < 5:
            continue
        rows.append({"question": "Q1_rotation_persistence", "condition": label, "horizon_m": h,
                     "n_months": n,
                     "median_persistence_rankcorr": float(pers[m].median()),
                     "median_revival_rankcorr": float(revi[m].median()),
                     "pct_persistence_pos": float((pers[m] > 0).mean()),
                     "uncond_median_persistence": float(pers.median()),
                     "uncond_median_revival": float(revi.median())})
q1 = pd.DataFrame(rows)
q1.to_parquet(OUT / "part3_rotation_persistence.parquet", index=False)

# ---------------- Q2: correlation collapse ----------------------------------
roll = pd.read_parquet(OUT / "part1_rolling.parquet").set_index("date").sort_index()
pc = roll["avg_pair_corr_63d"].dropna()
pc_m = pc.resample("ME").last().reindex(R.index)
now_pc = pc_m.loc[ANCHOR]
pc_pct = float((pc_m.dropna() < now_pc).mean())

ew = R.mean(axis=1)
lg = np.log1p(ew)
rows2 = []
for h in (1, 3, 6, 12):
    few = np.expm1(lg.shift(-1).rolling(h).sum().shift(-(h - 1)))
    fdisp = R.std(axis=1).shift(-1).rolling(h).mean().shift(-(h - 1))
    lo = pc_m <= pc_m.quantile(0.25)
    for label, m in [("low corr (bottom quartile)", lo & few.notna()),
                     ("all months", few.notna())]:
        rows2.append({"question": "Q2_low_correlation", "condition": label, "horizon_m": h,
                      "n_months": int(m.sum()),
                      "median_EW_fwd": float(few[m].median()),
                      "pct_positive": float((few[m] > 0).mean()),
                      "median_fwd_xsec_disp": float(fdisp[m].median()),
                      "median_fwd_pair_corr": float(pc_m.shift(-h)[m].median())})
q2 = pd.DataFrame(rows2)
q2.to_parquet(OUT / "part3_lowcorr.parquet", index=False)

pd.set_option("display.width", 220)
print(f"CURRENT leadership-inversion reading RC(2026-08-31) = {now_rc:.3f}  "
      f"(percentile {100*now_pct:.1f} of 2000-2026)")
print(f"most inverted months on record: \n{RC.nsmallest(8).round(3).to_string()}")
print(f"\nCURRENT avg pairwise 63d corr = {now_pc:.3f} (percentile {100*pc_pct:.1f})")
print("\n=== Q1 rotation persistence (POST-HOC) ===")
print(q1.round(3).to_string())
print("\n=== Q2 low-correlation regimes (POST-HOC) ===")
print(q2.round(4).to_string())
