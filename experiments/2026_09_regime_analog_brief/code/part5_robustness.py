"""
=============================================================================
SCRIPT NAME: part5_robustness.py
=============================================================================
Adversarial robustness on the single surviving finding (F1): after a SEVERE
country-leadership inversion (RC <= -0.40), the pre-inversion leadership
reasserts over the following 6-12 months.

Per the repo's "distrust a searched pass" law, this script tries to break the
finding four ways:
  R1  leave-one-episode-out jackknife (is it one or two episodes?)
  R2  subsample split 2000-2012 vs 2013-2026
  R3  crisis exclusion (drop 2008-2009 and 2020 COVID months)
  R4  threshold sensitivity sweep over RC cut-offs
  R5  shuffled-label placebo (random episodes of matched length)
Also reports the ECONOMIC size (long-old-leaders vs short-new-leaders spread),
because a rank correlation is not a return.

INPUT FILES (absolute):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/monthly_returns.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/part3_inversion_history.parquet

OUTPUT FILES (absolute):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/part5_robustness.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/part5_episode_detail.parquet

VERSION: 1.0
LAST UPDATED: 2026-09-02
AUTHOR: Claude (for Arjun Divecha)
DEPENDENCIES: pandas, numpy (ASADO venv)
USAGE: venv/bin/python experiments/2026_09_regime_analog_brief/code/part5_robustness.py
=============================================================================
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(777)
ROOT = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
OUT = ROOT / "experiments/2026_09_regime_analog_brief/results"
EXCL = {"NASDAQ", "US SmallCap"}
ANCHOR = pd.Timestamp("2026-08-31")

rets = pd.read_parquet(OUT / "monthly_returns.parquet").set_index("date").sort_index().loc[:ANCHOR]
uni = [c for c in rets.columns if c not in EXCL]
R = rets[uni]
tri = (1 + R).cumprod()
RC = pd.read_parquet(OUT / "part3_inversion_history.parquet").rename(columns={"index": "date"}).set_index("date")["RC"].sort_index()

old_lead = tri.shift(2) / tri.shift(8) - 1
new_lead = tri / tri.shift(2) - 1


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


REV = {h: pd.Series({d: sp(old_lead.loc[d], fwd(h).loc[d]) for d in R.index}).dropna() for h in (3, 6, 12)}
# economic size: EW of top-6 old leaders minus EW of top-6 new leaders, forward
SPREAD = {}
for h in (3, 6, 12):
    F = fwd(h)
    vals = {}
    for d in R.index:
        o, n_, f = old_lead.loc[d], new_lead.loc[d], F.loc[d]
        if o.notna().sum() < 20 or f.notna().sum() < 20:
            continue
        ot = o.nlargest(6).index; nt = n_.nlargest(6).index
        vals[d] = f[ot].mean() - f[nt].mean()
    SPREAD[h] = pd.Series(vals)

rows, detail = [], []
sev = RC[(RC <= -0.40) & (RC.index < ANCHOR)].index
eps_all = episodes(sev)

for h in (3, 6, 12):
    s = REV[h]
    eps = [[d for d in e if d in s.index] for e in eps_all]
    eps = [e for e in eps if e]
    base = float(np.median([s.loc[e].mean() for e in eps]))
    uncond = float(s.median())
    # R1 jackknife
    jk = [float(np.median([s.loc[e].mean() for k, e in enumerate(eps) if k != j])) for j in range(len(eps))]
    # R2 subsample
    e_early = [e for e in eps if e[-1] < pd.Timestamp("2013-01-01")]
    e_late = [e for e in eps if e[-1] >= pd.Timestamp("2013-01-01")]
    # R3 crisis exclusion
    def crisis(d): return (pd.Timestamp("2008-01-01") <= d <= pd.Timestamp("2009-12-31")) or (pd.Timestamp("2020-02-01") <= d <= pd.Timestamp("2020-12-31"))
    e_nc = [e for e in eps if not any(crisis(d) for d in e)]
    # R5 shuffled placebo
    arr = s.values; N = len(arr); L = [len(e) for e in eps]
    draws = np.array([np.median([arr[RNG.integers(0, N - l + 1):][:l].mean() for l in L]) for _ in range(5000)])
    rows.append({"test": "R0 headline", "horizon_m": h, "value": base, "n_episodes": len(eps), "unconditional": uncond})
    rows.append({"test": "R1 jackknife min", "horizon_m": h, "value": float(np.min(jk)), "n_episodes": len(eps), "unconditional": uncond})
    rows.append({"test": "R1 jackknife max", "horizon_m": h, "value": float(np.max(jk)), "n_episodes": len(eps), "unconditional": uncond})
    rows.append({"test": "R2 2000-2012", "horizon_m": h, "value": float(np.median([s.loc[e].mean() for e in e_early])), "n_episodes": len(e_early), "unconditional": uncond})
    rows.append({"test": "R2 2013-2026", "horizon_m": h, "value": float(np.median([s.loc[e].mean() for e in e_late])), "n_episodes": len(e_late), "unconditional": uncond})
    rows.append({"test": "R3 ex-crisis", "horizon_m": h, "value": float(np.median([s.loc[e].mean() for e in e_nc])), "n_episodes": len(e_nc), "unconditional": uncond})
    rows.append({"test": "R5 placebo null 95pct", "horizon_m": h, "value": float(np.percentile(draws, 95)), "n_episodes": len(eps), "unconditional": uncond})
    # economic size
    sp_ = SPREAD[h]
    eps_s = [[d for d in e if d in sp_.index] for e in eps_all]
    eps_s = [e for e in eps_s if e]
    rows.append({"test": "ECON old-minus-new top6 spread", "horizon_m": h,
                 "value": float(np.median([sp_.loc[e].mean() for e in eps_s])),
                 "n_episodes": len(eps_s), "unconditional": float(sp_.median())})
    for e in eps:
        detail.append({"horizon_m": h, "episode_start": e[0], "episode_end": e[-1],
                       "revival_rankcorr": float(s.loc[e].mean()),
                       "old_minus_new_spread": float(sp_.loc[[d for d in e if d in sp_.index]].mean()) if any(d in sp_.index for d in e) else np.nan})

# R4 threshold sweep
for thr in [-0.50, -0.45, -0.40, -0.35, -0.30, -0.25, -0.20]:
    sel = RC[(RC <= thr) & (RC.index < ANCHOR)].index
    for h in (6, 12):
        s = REV[h]
        eps = [[d for d in sel if d in s.index]]
        eps = episodes([d for d in sel if d in s.index])
        if not eps: continue
        rows.append({"test": f"R4 threshold RC<={thr}", "horizon_m": h,
                     "value": float(np.median([s.loc[e].mean() for e in eps])),
                     "n_episodes": len(eps), "unconditional": float(s.median())})

df = pd.DataFrame(rows)
df.to_parquet(OUT / "part5_robustness.parquet", index=False)
pd.DataFrame(detail).to_parquet(OUT / "part5_episode_detail.parquet", index=False)

pd.set_option("display.width", 200)
print(df.pivot_table(index="test", columns="horizon_m", values="value", sort=False).round(4).to_string())
print("\nn_episodes by test:")
print(df.pivot_table(index="test", columns="horizon_m", values="n_episodes", sort=False).to_string())
print("\n=== per-episode detail, h=6m ===")
d6 = pd.DataFrame(detail); d6 = d6[d6.horizon_m == 6]
print(d6.round(4).to_string(index=False))
