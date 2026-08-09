#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: run_step5_conditional_risk.py
=============================================================================

WHAT THIS PROGRAM DOES (for someone with zero prior context)
-------------------------------------------------------------
Conditions the RISK inside Step Five of the T2 Factor Timing Fuzzy optimizer on
the Early Warning System state, so that the size of the ACTIVE BET shifts with
the regime - without ever changing total exposure.

WHY THIS IS THE RIGHT LEVER (and the previous idea was not)
------------------------------------------------------------
The earlier EWS overlay simply multiplied the whole book by 0.5 in alarm months.
That was proven to be PURE BETA TIMING: the same rule delivered essentially the
same improvement to the T2 book (dSharpe +0.24), to the equal-weight benchmark
(+0.20) and to a plain S&P 500 long-only book (+0.22). It had nothing to do with
the strategy.

Step Five cannot have that problem. Its constraints are

    w >= 0,   w <= max_weights,   sum(w) == 1

so the book is ALWAYS fully invested. Total exposure is fixed at 1 by
construction, and nothing done here can be a market-timing bet. The only thing
that can change is WHICH factors are held and HOW CONCENTRATED the bet is.

THE INTERVENTION
----------------
Step Five's objective is

    maximize  w'mu  -  HHI * ||w||^2  -  KAPPA * sum( tc .* |w - w_prev| )

The HHI term is an anti-concentration penalty (production value 0.001). Raising
it pushes weights toward equal-weight across the 82 factors, i.e. a SMALLER
active bet; lowering it concentrates on the highest-mu factors, i.e. a BIGGER
active bet. So we make HHI regime-dependent:

    HHI_t = HHI_BASE                     when the EWS is calm
    HHI_t = HHI_BASE * MULT              when the EWS is in alarm

The hypothesis: take less factor-concentration risk when the environment is
unstable, more when it is calm.

Because only a handful of distinct HHI values occur, one CVXPY problem is
compiled per value and reused - identical solver, identical constraints,
identical cost treatment to production, so the comparison is apples to apples.

RETURNS: the factor returns in T2_Optimizer.xlsx are already NET (active) factor
returns, so the strategy return computed here is an ACTIVE return - there is no
market exposure in it at all. This is why the result cannot be beta in disguise.
The KAPPA cost penalty is left at the production value so the baseline reproduces
production; no additional cost gate is applied (25bp law retracted 2026-07-13).

SAFETY: reads the T2 production inputs READ-ONLY and writes ONLY into this
experiment directory. It never touches T2_rolling_window_weights.xlsx,
T2_strategy_statistics.xlsx or any other production output.

INPUT FILES (read-only):
- /Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/T2_Optimizer.xlsx
- /Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/Step Factor Categories.xlsx
- /Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/T2_Trading_Cost.xlsx
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/Early Warning/outputs/run_20260803_080233/signals_panel.parquet

OUTPUT FILES:
- .../experiments/2026_08_boundaries_tsm/results/step5_conditional_risk.xlsx
- .../experiments/2026_08_boundaries_tsm/results/step5_conditional_risk.json

VERSION: 1.0
LAST UPDATED: 2026-08-08
AUTHOR: Claude Code (for Arjun Divecha)
DEPENDENCIES: pandas, numpy, cvxpy (CLARABEL), openpyxl (project venv).
USAGE:
  ./venv/bin/python experiments/2026_08_boundaries_tsm/run_step5_conditional_risk.py
=============================================================================
"""
from __future__ import annotations

import json
from pathlib import Path

import cvxpy as cp
import numpy as np
import pandas as pd

T2 = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy")
EWS = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/Early Warning/"
           "outputs/run_20260803_080233/signals_panel.parquet")
OUT = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/"
           "experiments/2026_08_boundaries_tsm/results")

HHI_BASE = 0.001      # production value
KAPPA = 2.0           # production value
WINDOW = 60
ALARM_RULE = ("diffusion", 0.30)
MULTIPLIERS = [1.0, 5.0, 10.0, 25.0, 50.0, 100.0]


def build(n, maxw, hhi):
    w = cp.Variable(n)
    mu = cp.Parameter(n); tc = cp.Parameter(n, nonneg=True); wp = cp.Parameter(n)
    obj = cp.Maximize(w @ mu - hhi * cp.sum_squares(w)
                      - KAPPA * cp.sum(cp.multiply(tc, cp.abs(w - wp))))
    prob = cp.Problem(obj, [w >= 0, w <= maxw, cp.sum(w) == 1])
    return {"w": w, "mu": mu, "tc": tc, "wp": wp, "prob": prob}


def solve(o, mu, tc, wp, maxw):
    o["mu"].value = mu; o["tc"].value = tc; o["wp"].value = wp
    o["prob"].solve(solver=cp.CLARABEL, warm_start=True, verbose=False)
    if o["prob"].status not in (cp.OPTIMAL, cp.OPTIMAL_INACCURATE):
        raise RuntimeError(f"solver failed: {o['prob'].status}")   # FAIL IS FAIL
    out = np.maximum(o["w"].value, 0); s = out.sum()
    if abs(s - 1) > 1e-6:
        sc = out / s
        if not np.any(sc > maxw + 1e-8):
            out = sc
    return out


def load():
    r = pd.read_excel(T2 / "T2_Optimizer.xlsx", index_col=0)
    r.index = pd.to_datetime(r.index)
    r = r.apply(pd.to_numeric, errors="coerce") / 100.0
    if "Monthly Return_CS" in r.columns:
        r = r.drop(columns=["Monthly Return_CS"])
    r = r.loc[~r.isna().all(axis=1)]
    cats = pd.read_excel(T2 / "Step Factor Categories.xlsx")
    mw = dict(zip(cats["Factor Name"], cats["Max"]))
    tc = pd.read_excel(T2 / "T2_Trading_Cost.xlsx", sheet_name="Trading_Costs")
    tc["Date"] = pd.to_datetime(tc["Date"]); tc = tc.set_index("Date")
    tc = tc.reindex(index=r.index, columns=r.columns)
    tc = tc.apply(lambda c: c.fillna(tc.mean(axis=1)))
    return r, mw, tc / 1e4


def ews_alarm(dates):
    e = pd.read_parquet(EWS); e.index = pd.to_datetime(e.index)
    col, thr = ALARM_RULE
    s = e[[col]].copy()
    s["date"] = (s.index.to_period("M") + 1).to_timestamp()   # known at decision date
    s = s.set_index("date")[col].reindex(dates)
    return (s >= thr).fillna(False)


def backtest(returns, mw, tcost, alarm, mult):
    names = list(returns.columns); n = len(names)
    maxw = np.array([mw.get(x, 1.0) for x in names])
    opts = {HHI_BASE: build(n, maxw, HHI_BASE)}
    if mult != 1.0:
        opts[HHI_BASE * mult] = build(n, maxw, HHI_BASE * mult)
    dates = list(returns.index[1:])
    W = pd.DataFrame(index=dates, columns=names, dtype=float)
    mean_tc = float(tcost.stack().mean())
    prev = np.ones(n) / n
    for i, dt in enumerate(dates, start=1):
        win = returns.iloc[:i] if i <= WINDOW else returns.iloc[i - WINDOW:i]
        mu = np.nan_to_num(8.0 * win.mean(axis=0).to_numpy(float), nan=-9e9)
        tv = np.nan_to_num(tcost.loc[dt].to_numpy(float), nan=mean_tc)
        hhi = HHI_BASE * mult if bool(alarm.get(dt, False)) else HHI_BASE
        prev = solve(opts[hhi], mu, tv, prev, maxw)
        W.loc[dt] = prev
    rets, idx = [], []
    for dt in W.index:
        j = returns.index.get_loc(dt) + 1
        if j < len(returns.index):
            nd = returns.index[j]
            rets.append(np.nansum(W.loc[dt].to_numpy(float)
                                  * np.nan_to_num(returns.loc[nd].to_numpy(float))))
            idx.append(nd)
    s = pd.Series(rets, index=idx)
    turn = W.diff().abs().sum(axis=1) / 2
    eff_n = 1.0 / (W ** 2).sum(axis=1)          # effective number of factors held
    return s, turn, eff_n, W


def stats(s):
    ann = (1 + s.mean()) ** 12 - 1
    vol = s.std() * np.sqrt(12)
    c = (1 + s).cumprod()
    dd = ((c - c.expanding().max()) / c.expanding().max()).min()
    return ann, vol, ann / vol, dd


def main() -> int:
    returns, mw, tcost = load()
    dates = list(returns.index[1:])
    alarm = ews_alarm(dates)
    print(f"factors: {returns.shape[1]}, months: {returns.shape[0]}, "
          f"{returns.index.min().date()} -> {returns.index.max().date()}")
    print(f"alarm rule: {ALARM_RULE[0]} >= {ALARM_RULE[1]}  -> "
          f"{alarm.sum()}/{len(alarm)} months ({alarm.mean():.0%})\n")

    rows, series = [], {}
    for m in MULTIPLIERS:
        s, turn, eff, W = backtest(returns, mw, tcost, alarm, m)
        a, v, sh, dd = stats(s)
        ea = eff[alarm.reindex(eff.index).fillna(False)].mean()
        ec = eff[~alarm.reindex(eff.index).fillna(False)].mean()
        rows.append({"hhi_multiplier": m, "ann_return": a, "ann_vol": v, "IR": sh,
                     "max_dd": dd, "turnover_pm": turn.mean(),
                     "eff_factors_calm": ec, "eff_factors_alarm": ea})
        series[m] = s
        tag = "BASELINE (production)" if m == 1.0 else f"alarm HHI x{m:g}"
        print(f"  {tag:24s} ann {a*100:5.2f}%  vol {v*100:5.2f}%  IR {sh:.3f}  "
              f"maxDD {dd*100:6.1f}%  turn {turn.mean()*100:4.1f}%/mo  "
              f"eff factors calm {ec:.1f} / alarm {ea:.1f}")

    res = pd.DataFrame(rows)
    base = res[res.hhi_multiplier == 1.0].iloc[0]
    res["d_IR"] = res["IR"] - base["IR"]
    res["d_maxdd_pp"] = (res["max_dd"] - base["max_dd"]) * 100
    print(f"\n{'multiplier':>12}{'dIR':>9}{'d maxDD':>10}")
    for _, r in res.iterrows():
        print(f"{r.hhi_multiplier:>12g}{r.d_IR:>+9.3f}{r.d_maxdd_pp:>+9.1f}pp")

    best = res.loc[res.IR.idxmax()]
    print(f"\nbest IR: multiplier {best.hhi_multiplier:g} -> IR {best.IR:.3f} "
          f"vs baseline {base.IR:.3f} ({best.IR-base.IR:+.3f})")

    sdf = pd.DataFrame(series)
    with pd.ExcelWriter(OUT / "step5_conditional_risk.xlsx", engine="openpyxl") as xw:
        res.to_excel(xw, sheet_name="summary", index=False)
        sdf.to_excel(xw, sheet_name="monthly_returns")
        alarm.rename("alarm").to_frame().to_excel(xw, sheet_name="alarm_flag")
    (OUT / "step5_conditional_risk.json").write_text(json.dumps(
        {"hhi_base": HHI_BASE, "kappa": KAPPA, "alarm_rule": list(ALARM_RULE),
         "alarm_frac": float(alarm.mean()), "rows": res.to_dict("records")},
        indent=2, default=str))
    print(f"\nwrote: {OUT/'step5_conditional_risk.xlsx'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
