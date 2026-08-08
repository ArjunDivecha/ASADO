#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: run_t2_timing.py
=============================================================================

WHAT THIS PROGRAM DOES (for someone with zero prior context)
-------------------------------------------------------------
Asks Arjun's question directly: does Shiller-PE EXTREMENESS have any timing
power over the LIVE T2 Factor Timing Fuzzy strategy's returns? If it does -
specifically if returns are worse or volatility is higher when markets sit at
valuation extremes - then exposure can be scaled down in those months.

This is a different and more actionable question than the Boundaries programme
so far, which asked whether extremeness predicts COUNTRY MOMENTUM. Here the
dependent variable is the actual strategy's monthly P&L.

THREE EXTREMENESS MEASURES (all built from Shiller PE own-history percentiles):
  us_ext      - the U.S. alone (the global valuation anchor)
  mean_ext    - average extremeness across all countries that month
  breadth_ext - FRACTION of countries sitting in the top/bottom decile of their
                own 10-year history (how widespread are extremes?)

DEPENDENT VARIABLES (from T2_Final_Portfolio_Returns.xlsx):
  portfolio   - the strategy's total monthly return
  equal_wt    - the equal-weight benchmark (house benchmark convention)
  net         - active return, portfolio minus equal-weight (the alpha)

LOOK-AHEAD DISCIPLINE
---------------------
The signal is LAGGED ONE MONTH relative to the return it predicts, so a signal
formed from month m data predicts month m+1's P&L with a clear gap. The
unlagged version is reported alongside ONLY as a sensitivity - it is NOT the
headline, because T2 stamping conventions differ between the panel and the
returns workbook and an unlagged merge cannot be proven safe. (An alignment
error of exactly this kind already occurred once in this project.)

Returns are GROSS. No transaction-cost or turnover penalty is applied anywhere -
the 25bp one-way cost law was retracted 2026-07-13.

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/T2_Final_Portfolio_Returns.xlsx
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_08_boundaries_tsm/results/boundaries_panel.parquet

OUTPUT FILES:
- .../experiments/2026_08_boundaries_tsm/results/t2_timing.xlsx
- .../experiments/2026_08_boundaries_tsm/results/t2_timing.json

VERSION: 1.0
LAST UPDATED: 2026-08-08
AUTHOR: Claude Code (for Arjun Divecha)
DEPENDENCIES: pandas, numpy, statsmodels, openpyxl (project venv).
USAGE:
  ./venv/bin/python experiments/2026_08_boundaries_tsm/run_t2_timing.py
=============================================================================
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

BASE = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
OUT = BASE / "experiments" / "2026_08_boundaries_tsm" / "results"
T2X = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/"
           "T2_Final_Portfolio_Returns.xlsx")


def main() -> int:
    r = pd.read_excel(T2X, sheet_name="Monthly Returns").rename(
        columns={"Unnamed: 0": "date", "Portfolio": "portfolio",
                 "Equal Weight": "equal_wt", "Net Return": "net"})
    r["date"] = pd.to_datetime(r["date"])
    r = r[["date", "portfolio", "equal_wt", "net"]].sort_values("date")
    print(f"strategy returns: {len(r)} months, {r.date.min().date()} -> {r.date.max().date()}")

    p = pd.read_parquet(OUT / "boundaries_panel.parquet")
    p["date"] = pd.to_datetime(p["date"])
    p = p.dropna(subset=["cape__own_pct"]).copy()
    p["ext"] = (p["cape__own_pct"] - 0.5).abs() * 2
    p["is_extreme"] = ((p["cape__own_pct"] >= 0.9) | (p["cape__own_pct"] <= 0.1)).astype(float)

    agg = (p.groupby("date")
             .agg(mean_ext=("ext", "mean"),
                  breadth_ext=("is_extreme", "mean"),
                  n_ctry=("ext", "size")).reset_index())
    us = (p[p.country == "U.S."][["date", "ext"]].rename(columns={"ext": "us_ext"}))
    sig = agg.merge(us, on="date", how="left")
    sig = sig[sig.n_ctry >= 10]
    print(f"signals available: {len(sig)} months, {sig.date.min().date()} -> {sig.date.max().date()}")

    # LAG ONE MONTH: signal from month m predicts month m+1.
    sig_lag = sig.copy()
    sig_lag["date"] = sig_lag["date"] + pd.DateOffset(months=1)
    d = r.merge(sig_lag, on="date", how="inner")
    d_nolag = r.merge(sig, on="date", how="inner")
    print(f"merged (lagged, headline): {len(d)} months, {d.date.min().date()} -> {d.date.max().date()}\n")

    SIGNALS = ["us_ext", "mean_ext", "breadth_ext"]
    TARGETS = ["portfolio", "net", "equal_wt"]
    rows = []
    for s in SIGNALS:
        for tgt in TARGETS:
            dd = d.dropna(subset=[s, tgt])
            X = sm.add_constant(dd[[s]], has_constant="add")
            m = sm.OLS(dd[tgt], X).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
            nl = d_nolag.dropna(subset=[s, tgt])
            Xn = sm.add_constant(nl[[s]], has_constant="add")
            mn = sm.OLS(nl[tgt], Xn).fit(cov_type="HAC", cov_kwds={"maxlags": 6})
            # tercile means and volatility - the vol-scaling question
            q = dd[s].quantile([1/3, 2/3]).values
            lo = dd[dd[s] <= q[0]][tgt]; hi = dd[dd[s] >= q[1]][tgt]
            rows.append({"signal": s, "target": tgt, "n": len(dd),
                         "slope": m.params[s], "t_lagged": m.tvalues[s],
                         "t_unlagged_sensitivity": mn.tvalues[s],
                         "low_ext_mean_ann": lo.mean() * 12, "high_ext_mean_ann": hi.mean() * 12,
                         "low_ext_vol_ann": lo.std() * np.sqrt(12),
                         "high_ext_vol_ann": hi.std() * np.sqrt(12)})

    res = pd.DataFrame(rows)
    print(f"{'signal':<13}{'target':<11}{'slope':>9}{'t':>7}{'(unlag)':>9}"
          f"{'lowExt ret':>11}{'highExt ret':>12}{'lowExt vol':>11}{'highExt vol':>12}")
    for _, x in res.iterrows():
        print(f"{x.signal:<13}{x.target:<11}{x.slope:>9.4f}{x.t_lagged:>7.2f}"
              f"{x.t_unlagged_sensitivity:>9.2f}{x.low_ext_mean_ann*100:>10.1f}%"
              f"{x.high_ext_mean_ann*100:>11.1f}%{x.low_ext_vol_ann*100:>10.1f}%"
              f"{x.high_ext_vol_ann*100:>11.1f}%")

    # ---- does a simple de-risking rule help? (gross, no cost penalty) --------
    print("\nSIMPLE EXPOSURE RULE — scale to 50% in the top tercile of extremeness:")
    out = []
    for s in SIGNALS:
        dd = d.dropna(subset=[s, "portfolio"]).copy()
        thr = dd[s].quantile(2/3)
        w = np.where(dd[s] >= thr, 0.5, 1.0)
        for tgt in ["portfolio", "net"]:
            base, scaled = dd[tgt], dd[tgt] * w
            def stats(x):
                return x.mean() * 12, x.std() * np.sqrt(12), (x.mean() * 12) / (x.std() * np.sqrt(12))
            b, sc = stats(base), stats(scaled)
            out.append({"signal": s, "target": tgt,
                        "base_ann": b[0], "base_vol": b[1], "base_sharpe": b[2],
                        "scaled_ann": sc[0], "scaled_vol": sc[1], "scaled_sharpe": sc[2],
                        "sharpe_delta": sc[2] - b[2]})
            print(f"  {s:<13}{tgt:<10} base {b[0]*100:5.1f}%/{b[1]*100:4.1f}% Sh {b[2]:.2f}"
                  f"   ->  scaled {sc[0]*100:5.1f}%/{sc[1]*100:4.1f}% Sh {sc[2]:.2f}"
                  f"   delta {sc[2]-b[2]:+.3f}")
    rule = pd.DataFrame(out)

    with pd.ExcelWriter(OUT / "t2_timing.xlsx", engine="openpyxl") as xw:
        res.to_excel(xw, sheet_name="regressions", index=False)
        rule.to_excel(xw, sheet_name="exposure_rule", index=False)
        d.to_excel(xw, sheet_name="merged_lagged", index=False)
    (OUT / "t2_timing.json").write_text(json.dumps(
        {"note": "signal lagged 1m; returns GROSS, no cost penalty (25bp law retracted)",
         "regressions": res.to_dict("records"), "exposure_rule": rule.to_dict("records")},
        indent=2, default=str))
    print(f"\nwrote: {OUT/'t2_timing.xlsx'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
