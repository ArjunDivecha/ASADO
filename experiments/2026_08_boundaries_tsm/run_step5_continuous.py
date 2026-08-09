#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: run_step5_continuous.py
=============================================================================
Continuous version of the Step Five conditional-risk experiment: instead of a
binary EWS alarm flag, the concentration penalty varies CONTINUOUSLY with the
diffusion reading.

    HHI_t = HHI_BASE * M ** (diffusion_t / D_REF)

so at diffusion 0 the penalty is the production value (full conviction, ~1
effective factor) and at diffusion = D_REF it reaches M x that value (a broader,
lower-conviction book). Between them it scales smoothly - no threshold, no cliff.

Motivation: the binary version (broaden when diffusion >= 0.30) beat both its own
inversion (IR 1.012 vs 0.647) and random same-frequency timing (88th pctile on
IR, 96th on drawdown), so the timing carries information. A continuous map should
use that information more efficiently than a single cut point, and removes an
arbitrary threshold.

sum(w)==1 throughout, so - as with the binary version - this cannot be beta
timing. Only the breadth of the active bet changes.

IMPLEMENTATION NOTE: cvxpy compiles one problem per distinct HHI value, so
continuous values are snapped to a 48-point log grid and the problems cached.
The grid step is ~10% in the penalty, far below the resolution at which results
change.

INPUT (read-only): T2_Optimizer.xlsx, Step Factor Categories.xlsx,
T2_Trading_Cost.xlsx, Early Warning signals_panel.parquet
OUTPUT: results/step5_continuous.xlsx / .json
VERSION 1.0 · 2026-08-08 · Claude Code for Arjun Divecha
RUN: "/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/venv/bin/python" \
     experiments/2026_08_boundaries_tsm/run_step5_continuous.py
=============================================================================
"""
import json, types
from pathlib import Path
import numpy as np, pandas as pd

OUT = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/"
           "experiments/2026_08_boundaries_tsm/results")
src = open("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/"
           "2026_08_boundaries_tsm/run_step5_conditional_risk.py").read().split('def main()')[0]
mod = types.ModuleType("m"); exec(compile(src, "m", "exec"), mod.__dict__)

D_REF = 0.40          # diffusion level at which the multiplier reaches M
GRID = np.unique(np.round(np.logspace(0, np.log10(2000), 48), 3))


def diffusion_series(dates):
    e = pd.read_parquet(mod.EWS); e.index = pd.to_datetime(e.index)
    s = e[["diffusion"]].copy()
    s["date"] = (s.index.to_period("M") + 1).to_timestamp()
    return s.set_index("date")["diffusion"].reindex(dates).ffill().fillna(0.0)


def backtest_continuous(returns, mw, tcost, diff, M):
    names = list(returns.columns); n = len(names)
    maxw = np.array([mw.get(x, 1.0) for x in names])
    cache, dates = {}, list(returns.index[1:])
    W = pd.DataFrame(index=dates, columns=names, dtype=float)
    mean_tc = float(tcost.stack().mean()); prev = np.ones(n) / n
    mults = []
    for i, dt in enumerate(dates, start=1):
        win = returns.iloc[:i] if i <= mod.WINDOW else returns.iloc[i - mod.WINDOW:i]
        mu = np.nan_to_num(8.0 * win.mean(axis=0).to_numpy(float), nan=-9e9)
        tv = np.nan_to_num(tcost.loc[dt].to_numpy(float), nan=mean_tc)
        raw = M ** (float(diff.get(dt, 0.0)) / D_REF)
        m = float(GRID[np.argmin(np.abs(GRID - raw))])      # snap to grid
        mults.append(m)
        hhi = mod.HHI_BASE * m
        if m not in cache:
            cache[m] = mod.build(n, maxw, hhi)
        prev = mod.solve(cache[m], mu, tv, prev, maxw)
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
    return s, W.diff().abs().sum(axis=1) / 2, 1.0 / (W ** 2).sum(axis=1), pd.Series(mults, index=dates)


def main():
    returns, mw, tcost = mod.load()
    dates = list(returns.index[1:]); diff = diffusion_series(dates)
    print(f"diffusion: min {diff.min():.2f} median {diff.median():.2f} max {diff.max():.2f}")
    print(f"continuous map: HHI = {mod.HHI_BASE} * M ** (diffusion / {D_REF})\n")
    base_s, _, base_eff, _ = backtest_continuous(returns, mw, tcost, diff * 0, 1.0)
    ba, bv, bir, bdd = mod.stats(base_s)
    print(f"{'setup':<26}{'ann':>8}{'vol':>8}{'IR':>8}{'maxDD':>9}{'turn':>8}{'effN lo/hi':>14}")
    print(f"{'baseline (production)':<26}{ba*100:>7.2f}%{bv*100:>7.2f}%{bir:>8.3f}{bdd*100:>8.1f}%"
          f"{'--':>8}{f'{base_eff.mean():.1f}':>14}")
    rows = [{"M": 1.0, "ann": ba, "vol": bv, "IR": bir, "maxdd": bdd}]
    series = {"baseline": base_s}
    for M in [5, 10, 25, 100, 400, 1000]:
        s, turn, eff, mult = backtest_continuous(returns, mw, tcost, diff, float(M))
        a, v, ir, dd = mod.stats(s)
        lo = eff[diff.reindex(eff.index).fillna(0) <= diff.quantile(.25)].mean()
        hi = eff[diff.reindex(eff.index).fillna(0) >= diff.quantile(.75)].mean()
        rows.append({"M": float(M), "ann": a, "vol": v, "IR": ir, "maxdd": dd,
                     "turn": turn.mean(), "effN_lowdiff": lo, "effN_highdiff": hi,
                     "mult_median": float(mult.median()), "mult_max": float(mult.max())})
        series[f"M={M}"] = s
        print(f"{'continuous M=' + str(M):<26}{a*100:>7.2f}%{v*100:>7.2f}%{ir:>8.3f}{dd*100:>8.1f}%"
              f"{turn.mean()*100:>7.1f}%{f'{lo:.1f} / {hi:.1f}':>14}")
    res = pd.DataFrame(rows)
    res["d_IR"] = res["IR"] - bir; res["d_maxdd_pp"] = (res["maxdd"] - bdd) * 100
    best = res.iloc[res.IR.idxmax()]
    print(f"\nbest: M={best.M:g}  IR {best.IR:.3f} ({best.IR-bir:+.3f})  "
          f"maxDD {best.maxdd*100:.1f}% ({(best.maxdd-bdd)*100:+.1f}pp)")
    with pd.ExcelWriter(OUT / "step5_continuous.xlsx", engine="openpyxl") as xw:
        res.to_excel(xw, sheet_name="summary", index=False)
        pd.DataFrame(series).to_excel(xw, sheet_name="monthly_returns")
    (OUT / "step5_continuous.json").write_text(json.dumps(
        {"d_ref": D_REF, "rows": res.to_dict("records")}, indent=2, default=str))
    print(f"\nwrote: {OUT/'step5_continuous.xlsx'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
