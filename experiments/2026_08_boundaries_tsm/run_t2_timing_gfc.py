#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: run_t2_timing_gfc.py
=============================================================================

WHY THIS EXISTS
---------------
run_t2_timing.py used a 10-YEAR normalization window for Shiller-PE extremeness.
That silently deleted the only events the question is about: the tested window
started 2010-02, but the T2 strategy's -62.7% max drawdown troughed 2009-02, and
FIVE of its six worst months (2008-10 -28.4%, 2008-09, 2008-01, 2001-09,
2008-03) fell outside it. Only 2020-03 was inside. A de-risking rule cannot be
evaluated on a sample containing no crash - the first run was uninformative for
Arjun's actual purpose, whatever its t-statistics said.

This rebuilds extremeness on a 60-MONTH (5-year) window, which pulls coverage
back to ~2005 and puts the GFC in sample, and then asks the question properly:

  1. Does Shiller extremeness predict the strategy's returns / volatility?
  2. WHAT DID IT SAY IN 2008? Would de-risking on it have helped in the one
     episode that matters?
  3. Does a 50%-exposure rule improve Sharpe or drawdown, now that the sample
     contains the drawdown?

The 5-year window is a genuine trade-off, stated rather than hidden: a shorter
lookback is a noisier definition of "extreme", but a definition that can only be
computed after the crash is useless for avoiding one.

Returns are GROSS - no cost or turnover penalty (25bp law retracted 2026-07-13).
Signal is LAGGED ONE MONTH against the return it predicts.

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb (READ-ONLY)
- /Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/T2_Final_Portfolio_Returns.xlsx

OUTPUT FILES:
- .../experiments/2026_08_boundaries_tsm/results/t2_timing_gfc.xlsx
- .../experiments/2026_08_boundaries_tsm/results/t2_timing_gfc.json

VERSION: 1.0
LAST UPDATED: 2026-08-08
AUTHOR: Claude Code (for Arjun Divecha)
DEPENDENCIES: duckdb, pandas, numpy, statsmodels, openpyxl (project venv).
USAGE:
  ./venv/bin/python experiments/2026_08_boundaries_tsm/run_t2_timing_gfc.py
=============================================================================
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm

BASE = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
OUT = BASE / "experiments" / "2026_08_boundaries_tsm" / "results"
T2X = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/"
           "T2_Final_Portfolio_Returns.xlsx")
WIN = 60   # 5 years - deliberately shorter so the GFC is in sample


def main() -> int:
    con = duckdb.connect(str(BASE / "Data" / "asado.duckdb"), read_only=True)
    try:
        s = con.execute("SELECT date,country,value FROM t2_raw WHERE variable='Shiller PE'").fetchdf()
    finally:
        con.close()
    s["date"] = pd.to_datetime(s["date"])
    s = s.sort_values(["country", "date"])
    s["pct"] = (s.groupby("country")["value"]
                 .transform(lambda x: x.rolling(WIN, min_periods=WIN)
                            .apply(lambda w: (w[:-1] < w[-1]).mean(), raw=True)))
    s = s.dropna(subset=["pct"])
    s["ext"] = (s["pct"] - 0.5).abs() * 2
    s["is_ext"] = ((s["pct"] >= 0.9) | (s["pct"] <= 0.1)).astype(float)

    agg = (s.groupby("date").agg(mean_ext=("ext", "mean"), breadth_ext=("is_ext", "mean"),
                                 n=("ext", "size")).reset_index())
    us = s[s.country == "U.S."][["date", "ext"]].rename(columns={"ext": "us_ext"})
    sig = agg.merge(us, on="date", how="left")
    sig = sig[sig.n >= 10]
    sig["date"] = sig["date"] + pd.DateOffset(months=1)      # lag one month

    r = pd.read_excel(T2X, sheet_name="Monthly Returns")
    r.columns = ["date", "portfolio", "equal_wt", "net"]
    r["date"] = pd.to_datetime(r["date"])
    d = r.merge(sig, on="date", how="inner").sort_values("date")
    print(f"tested window: {d.date.min().date()} -> {d.date.max().date()}  ({len(d)} months)")
    gfc = d[(d.date >= "2008-01-01") & (d.date <= "2009-06-01")]
    print(f"GFC months now in sample: {len(gfc)}  "
          f"(worst {d.portfolio.min()*100:.1f}% on {d.loc[d.portfolio.idxmin(),'date'].date()})\n")

    SIG = ["us_ext", "mean_ext", "breadth_ext"]
    rows = []
    for sg in SIG:
        for tgt in ["portfolio", "net"]:
            dd = d.dropna(subset=[sg, tgt])
            X = sm.add_constant(dd[[sg]], has_constant="add")
            m = sm.OLS(dd[tgt], X).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
            q = dd[sg].quantile([1/3, 2/3]).values
            lo, hi = dd[dd[sg] <= q[0]][tgt], dd[dd[sg] >= q[1]][tgt]
            rows.append({"signal": sg, "target": tgt, "n": len(dd), "slope": m.params[sg],
                         "t": m.tvalues[sg],
                         "lo_ret": lo.mean()*12, "hi_ret": hi.mean()*12,
                         "lo_vol": lo.std()*np.sqrt(12), "hi_vol": hi.std()*np.sqrt(12)})
    res = pd.DataFrame(rows)
    print(f"{'signal':<13}{'target':<11}{'slope':>9}{'t':>7}{'lowExt ret':>12}{'highExt ret':>12}"
          f"{'lowExt vol':>12}{'highExt vol':>12}")
    for _, x in res.iterrows():
        print(f"{x.signal:<13}{x.target:<11}{x.slope:>9.4f}{x.t:>7.2f}{x.lo_ret*100:>11.1f}%"
              f"{x.hi_ret*100:>11.1f}%{x.lo_vol*100:>11.1f}%{x.hi_vol*100:>11.1f}%")

    # ---- THE question: what did the signal say going INTO the crash? --------
    print("\nWHAT DID IT SAY BEFORE THE CRASH? (extremeness percentile within this sample)")
    for lbl, dt in [("2007-10 (pre-GFC peak)", "2007-10-01"), ("2008-06", "2008-06-01"),
                    ("2008-09 (Lehman)", "2008-09-01"), ("2020-02 (pre-COVID)", "2020-02-01")]:
        row = d[d.date == dt]
        if row.empty:
            print(f"  {lbl:26s} not in sample"); continue
        parts = []
        for sg in SIG:
            v = row[sg].iloc[0]
            pctile = (d[sg] < v).mean()
            parts.append(f"{sg} {v:.2f} ({pctile:.0%}ile)")
        print(f"  {lbl:26s} " + "  ".join(parts))

    # ---- de-risking rule, now including the crash ---------------------------
    print("\nEXPOSURE RULE — 50% weight in the top tercile of extremeness (GFC in sample):")
    out = []
    for sg in SIG:
        dd = d.dropna(subset=[sg, "portfolio"]).copy()
        thr = dd[sg].quantile(2/3)
        w = np.where(dd[sg] >= thr, 0.5, 1.0)
        for tgt in ["portfolio", "net"]:
            base, scal = dd[tgt].values, dd[tgt].values * w
            def st(x):
                c = np.cumprod(1+x); ddn = (c/np.maximum.accumulate(c)-1).min()
                return x.mean()*12, x.std()*np.sqrt(12), x.mean()*12/(x.std()*np.sqrt(12)), ddn
            b, sc = st(base), st(scal)
            out.append({"signal": sg, "target": tgt, "base_sharpe": b[2], "scaled_sharpe": sc[2],
                        "base_maxdd": b[3], "scaled_maxdd": sc[3],
                        "sharpe_delta": sc[2]-b[2], "maxdd_delta": sc[3]-b[3]})
            print(f"  {sg:<13}{tgt:<10} Sharpe {b[2]:.2f} -> {sc[2]:.2f} ({sc[2]-b[2]:+.3f})   "
                  f"maxDD {b[3]*100:6.1f}% -> {sc[3]*100:6.1f}% ({(sc[3]-b[3])*100:+.1f}pp)")
    rule = pd.DataFrame(out)

    with pd.ExcelWriter(OUT / "t2_timing_gfc.xlsx", engine="openpyxl") as xw:
        res.to_excel(xw, sheet_name="regressions", index=False)
        rule.to_excel(xw, sheet_name="exposure_rule", index=False)
        d.to_excel(xw, sheet_name="merged", index=False)
    (OUT / "t2_timing_gfc.json").write_text(json.dumps(
        {"window_months": WIN, "n_months": int(len(d)),
         "regressions": res.to_dict("records"), "rule": rule.to_dict("records")},
        indent=2, default=str))
    print(f"\nwrote: {OUT/'t2_timing_gfc.xlsx'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
