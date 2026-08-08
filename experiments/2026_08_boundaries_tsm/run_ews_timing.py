#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: run_ews_timing.py
=============================================================================

WHAT THIS PROGRAM DOES (for someone with zero prior context)
-------------------------------------------------------------
Tests whether Arjun's live Early Warning System signals - the COMPOSITE and the
DIFFUSION - have timing power over the live T2 Factor Timing Fuzzy strategy, and
whether scaling exposure on them improves risk-adjusted return or drawdown.

This supersedes the Shiller-extremeness attempt (RESULTS_T2_TIMING.md), which
failed for a structural reason: a 10-year valuation lookback started the sample
in 2010 and so contained NO crash, and even a 5-year window left only one. The
EWS panel is monthly back to 1964, so over the T2 strategy's life (2000-04
onward) it covers BOTH the dot-com bust AND the GFC AND COVID - three episodes
instead of one. That is the entire reason this test can answer the question and
the previous one could not.

SIGNALS (from the EWS signals panel, all point-in-time):
  composite         - the 12-signal composite level
  composite_pctile  - its expanding-window percentile. VERIFIED PIT: correlates
                      0.9998 with an expanding rank vs 0.9802 with a full-sample
                      rank, so it is not full-sample standardized.
  diffusion         - fraction of the 12 signals currently flagged
  state_best        - the PIT classifier state (IN / TRANSITION / OUT)
The `hindsight` column is DELIBERATELY NOT USED - it is the hindsight-labelled
state and is look-ahead by construction.

ALIGNMENT: the EWS panel is stamped MONTH-END; the T2 workbook is stamped
first-of-month and holds that month's return. So an EWS reading at the end of
month M is mapped to the T2 return of month M+1 - a genuine one-month gap, no
contemporaneous information.

Returns are GROSS. No transaction-cost or turnover penalty (25bp law retracted
2026-07-13).

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/Early Warning/outputs/run_20260803_080233/signals_panel.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/T2_Final_Portfolio_Returns.xlsx

OUTPUT FILES:
- .../experiments/2026_08_boundaries_tsm/results/ews_timing.xlsx
- .../experiments/2026_08_boundaries_tsm/results/ews_timing.json

VERSION: 1.0
LAST UPDATED: 2026-08-08
AUTHOR: Claude Code (for Arjun Divecha)
DEPENDENCIES: pandas, numpy, statsmodels, openpyxl (project venv).
USAGE:
  ./venv/bin/python experiments/2026_08_boundaries_tsm/run_ews_timing.py
=============================================================================
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

OUT = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/"
           "experiments/2026_08_boundaries_tsm/results")
EWS = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/Early Warning/"
           "outputs/run_20260803_080233/signals_panel.parquet")
T2X = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/"
           "T2_Final_Portfolio_Returns.xlsx")

EPISODES = {"dotcom 2000-02": ("2000-04-01", "2002-12-01"),
            "GFC 2008-09": ("2008-01-01", "2009-12-01"),
            "COVID 2020": ("2020-01-01", "2020-12-01")}


def stats(x):
    x = np.asarray(x, float)
    c = np.cumprod(1 + x)
    dd = (c / np.maximum.accumulate(c) - 1).min()
    ann, vol = x.mean() * 12, x.std() * np.sqrt(12)
    return ann, vol, (ann / vol if vol else np.nan), dd


def main() -> int:
    e = pd.read_parquet(EWS)
    e.index = pd.to_datetime(e.index)
    e = e[["composite", "composite_pctile", "diffusion", "state_best"]].copy()
    # month-end M -> first-of-month M+1 (the month whose return it predicts)
    e["date"] = (e.index.to_period("M") + 1).to_timestamp()
    e["ews_out"] = (e["state_best"] != "IN").astype(float)

    r = pd.read_excel(T2X, sheet_name="Monthly Returns")
    r.columns = ["date", "portfolio", "equal_wt", "net"]
    r["date"] = pd.to_datetime(r["date"])

    d = r.merge(e, on="date", how="inner").sort_values("date").reset_index(drop=True)
    print(f"merged: {len(d)} months, {d.date.min().date()} -> {d.date.max().date()}")
    for lab, (a, b) in EPISODES.items():
        n = ((d.date >= a) & (d.date <= b)).sum()
        print(f"  {lab:16s} in sample: {n} months")
    print()

    SIG = ["composite", "composite_pctile", "diffusion", "ews_out"]
    rows = []
    for s in SIG:
        for tgt in ["portfolio", "net", "equal_wt"]:
            dd = d.dropna(subset=[s, tgt])
            X = sm.add_constant(dd[[s]], has_constant="add")
            m = sm.OLS(dd[tgt], X).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
            q = dd[s].quantile([1/3, 2/3]).values
            lo, hi = dd[dd[s] <= q[0]][tgt], dd[dd[s] >= q[1]][tgt]
            rows.append({"signal": s, "target": tgt, "n": len(dd), "slope": m.params[s],
                         "t": m.tvalues[s], "lo_ret": lo.mean()*12, "hi_ret": hi.mean()*12,
                         "lo_vol": lo.std()*np.sqrt(12), "hi_vol": hi.std()*np.sqrt(12)})
    res = pd.DataFrame(rows)
    print(f"{'signal':<18}{'target':<11}{'slope':>9}{'t':>7}{'calm ret':>10}{'alarm ret':>11}"
          f"{'calm vol':>10}{'alarm vol':>11}")
    for _, x in res.iterrows():
        print(f"{x.signal:<18}{x.target:<11}{x.slope:>9.4f}{x.t:>7.2f}{x.lo_ret*100:>9.1f}%"
              f"{x.hi_ret*100:>10.1f}%{x.lo_vol*100:>9.1f}%{x.hi_vol*100:>10.1f}%")

    # ---- exposure rules -----------------------------------------------------
    print("\nEXPOSURE RULES (50% weight when the signal is in alarm):")
    RULES = {
        "composite_pctile >= 0.8": lambda x: np.where(x["composite_pctile"] >= 0.8, .5, 1.),
        "composite_pctile >= 0.67": lambda x: np.where(x["composite_pctile"] >= 0.67, .5, 1.),
        "diffusion >= 0.30": lambda x: np.where(x["diffusion"] >= 0.30, .5, 1.),
        "diffusion >= 0.20": lambda x: np.where(x["diffusion"] >= 0.20, .5, 1.),
        "state != IN": lambda x: np.where(x["ews_out"] > 0, .5, 1.),
    }
    out = []
    for name, fn in RULES.items():
        dd = d.dropna(subset=["composite_pctile", "diffusion", "portfolio"]).copy()
        w = fn(dd)
        for tgt in ["portfolio", "net"]:
            b, sc = stats(dd[tgt].values), stats(dd[tgt].values * w)
            out.append({"rule": name, "target": tgt, "months_derisked": float((w < 1).mean()),
                        "base_ann": b[0], "base_sharpe": b[2], "base_maxdd": b[3],
                        "scaled_ann": sc[0], "scaled_sharpe": sc[2], "scaled_maxdd": sc[3],
                        "sharpe_delta": sc[2]-b[2], "maxdd_delta": sc[3]-b[3]})
            print(f"  {name:<26}{tgt:<10} derisked {float((w<1).mean()):4.0%}  "
                  f"Sharpe {b[2]:.2f}->{sc[2]:.2f} ({sc[2]-b[2]:+.3f})  "
                  f"maxDD {b[3]*100:6.1f}%->{sc[3]*100:6.1f}% ({(sc[3]-b[3])*100:+.1f}pp)")
    rule = pd.DataFrame(out)

    # ---- did it warn BEFORE each episode? -----------------------------------
    print("\nDID IT WARN? (signal reading in the 3 months BEFORE each episode began)")
    for lab, (a, b) in EPISODES.items():
        pre = d[(d.date < a)].tail(3)
        if pre.empty:
            print(f"  {lab:16s} no pre-period in sample"); continue
        print(f"  {lab:16s} " + "  ".join(
            f"{r.date.date()}: pctile {r.composite_pctile:.2f} diff {r.diffusion:.2f} {r.state_best}"
            for _, r in pre.iterrows()))

    # ---- per-episode drawdown for the best rule -----------------------------
    print("\nPER-EPISODE max drawdown (rule: state != IN):")
    dd = d.dropna(subset=["portfolio"]).copy()
    w = np.where(dd["ews_out"] > 0, .5, 1.)
    dd["scaled"] = dd["portfolio"].values * w
    for lab, (a, b) in EPISODES.items():
        g = dd[(dd.date >= a) & (dd.date <= b)]
        if g.empty:
            continue
        print(f"  {lab:16s} base {stats(g.portfolio.values)[3]*100:6.1f}%  "
              f"scaled {stats(g.scaled.values)[3]*100:6.1f}%")
    rest = dd[~dd.date.between("2000-04-01", "2002-12-01")
              & ~dd.date.between("2008-01-01", "2009-12-01")
              & ~dd.date.between("2020-01-01", "2020-12-01")]
    print(f"  {'all other months':16s} base {stats(rest.portfolio.values)[3]*100:6.1f}%  "
          f"scaled {stats(rest.scaled.values)[3]*100:6.1f}%   (n={len(rest)})")

    with pd.ExcelWriter(OUT / "ews_timing.xlsx", engine="openpyxl") as xw:
        res.to_excel(xw, sheet_name="regressions", index=False)
        rule.to_excel(xw, sheet_name="exposure_rules", index=False)
        d.to_excel(xw, sheet_name="merged", index=False)
    (OUT / "ews_timing.json").write_text(json.dumps(
        {"n_months": int(len(d)), "regressions": res.to_dict("records"),
         "rules": rule.to_dict("records")}, indent=2, default=str))
    print(f"\nwrote: {OUT/'ews_timing.xlsx'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
