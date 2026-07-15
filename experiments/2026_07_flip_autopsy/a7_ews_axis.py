"""
=============================================================================
SCRIPT NAME: a7_ews_axis.py
=============================================================================

WHAT THIS PROGRAM DOES:
Addendum A7 of the G1 flip autopsy (PRD, pre-registered 2026-07-15): tests
whether the network_spillover family's monthly IC is conditional on Arjun's
Early Warning System (EWS) US market state - a FIFTH regime axis, materially
different from the four originals (event-validated 12-signal confluence
classifier vs raw macro series). Axis: EWS `state_best` at month-end m-1
(IN vs NOT-IN, where NOT-IN = TRANSITION or OUT) conditions family IC of
month m. Outcomes: (a) the 16-roster recomputed family IC (a2), (b) the
book_2026_07_14 5-variable roster IC built from a2's per-signal daily ICs.
Tests per the pre-registration: conditional means with NW-t (lag 6) on the
IN-minus-NOTIN difference (pre-2024 primary, full-sample reported), decay
localization (2024-26 negative months by state), and a descriptive
second-moment check (IC dispersion by state). Criterion: |NW-t| >= 2.0
pre-2024 = state dependence; else the autopsy's state-independence
conclusion extends to this axis. No trading rule follows either way.

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/Early Warning/outputs/run_20260715_113935/signals_panel.parquet
  (EWS monthly panel; column state_best, 1960-01 .. 2026-05)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/a2_family_ic_monthly_recomputed.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/a2_recomputed_ic_daily.parquet

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/a7_summary.json
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/a7_ews_axis.xlsx

VERSION: 1.0  |  LAST UPDATED: 2026-07-15  |  AUTHOR: Claude (G1 autopsy A7)
DEPENDENCIES: pandas, numpy, openpyxl (ASADO venv). No DB access.
USAGE: venv/bin/python experiments/2026_07_flip_autopsy/a7_ews_axis.py
=============================================================================
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

EWS = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/Early Warning/outputs/run_20260715_113935/signals_panel.parquet")
RES = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results")

BOOK5 = ["GRAPH_BANK_NBR_RET_GAP_21D", "GRAPHP_TRADE_NBR_RET_GAP_21D",
         "GRAPHP_KATZ_TRADE_GAP_21D", "SIM_NBR_RET_GAP_21D", "LL_LEADER_GAP_5D"]


def nw_t_diff(x_a: pd.Series, x_b: pd.Series, lags: int = 6) -> float:
    """NW-t of mean(a) - mean(b) via a dummy regression on the pooled series."""
    df = pd.concat([
        pd.DataFrame({"y": x_a, "d": 1.0}),
        pd.DataFrame({"y": x_b, "d": 0.0}),
    ]).dropna().sort_index()
    X = np.column_stack([np.ones(len(df)), df["d"].values])
    y = df["y"].values
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ beta
    n = len(y)
    XtX_inv = np.linalg.inv(X.T @ X)
    S = (X * e[:, None]).T @ (X * e[:, None]) / n
    for l in range(1, lags + 1):
        w = 1 - l / (lags + 1)
        G = (X[l:] * e[l:, None]).T @ (X[:-l] * e[:-l, None]) / n
        S += w * (G + G.T)
    V = n * XtX_inv @ S @ XtX_inv
    return float(beta[1] / np.sqrt(V[1, 1]))


# EWS state, lagged one month (state at m-1 conditions IC of month m)
ews = pd.read_parquet(EWS)["state_best"].dropna()
ews.index = pd.to_datetime(ews.index).to_period("M").to_timestamp()
state = ews.shift(1).rename("ews_state")   # PIT: prior month-end state

# outcome (a): 16-roster family IC
fam = pd.read_parquet(RES / "a2_family_ic_monthly_recomputed.parquet")
fam["month"] = pd.to_datetime(fam["month"])
fam = fam.set_index("month")["family_ic"]

# outcome (b): book-5 roster from a2 per-signal daily ICs
d = pd.read_parquet(RES / "a2_recomputed_ic_daily.parquet")
d = d[d["variable"].isin(BOOK5)]
d["month"] = pd.to_datetime(d["date"]).dt.to_period("M").dt.to_timestamp()
sig_m = d.groupby(["variable", "month"])["ic_aligned"].mean().reset_index()
book = sig_m.groupby("month")["ic_aligned"].mean().rename("book_ic")

out = {}
rows = []
for name, series in [("roster16", fam), ("book5", book)]:
    df = pd.concat([series, state], axis=1).dropna()
    df["in_state"] = df["ews_state"].eq("IN")
    for period, lo, hi in [("pre2024", "1900-01-01", "2023-12-31"),
                           ("full", "1900-01-01", "2100-01-01"),
                           ("2024plus", "2024-01-01", "2100-01-01")]:
        sub = df[(df.index >= lo) & (df.index <= hi)]
        a, b = sub[sub["in_state"]].iloc[:, 0], sub[~sub["in_state"]].iloc[:, 0]
        t = nw_t_diff(a, b) if min(len(a), len(b)) >= 12 else np.nan
        rows.append({"outcome": name, "period": period,
                     "mean_IN": round(float(a.mean()), 5), "n_IN": len(a),
                     "mean_NOTIN": round(float(b.mean()), 5) if len(b) else None,
                     "n_NOTIN": len(b),
                     "std_IN": round(float(a.std()), 5),
                     "std_NOTIN": round(float(b.std()), 5) if len(b) > 2 else None,
                     "nw_t_diff": round(t, 2) if t == t else None})
    # decay localization: 2024+ negative months by state
    post = df[df.index >= "2024-01-01"]
    neg = post[post.iloc[:, 0] < 0]
    out[f"{name}_2024plus_neg_months_IN_share"] = (
        round(float(neg["in_state"].mean()), 3) if len(neg) else None)
    out[f"{name}_2024plus_months_IN_share"] = (
        round(float(post["in_state"].mean()), 3) if len(post) else None)

tab = pd.DataFrame(rows)
pre16 = tab[(tab.outcome == "roster16") & (tab.period == "pre2024")].iloc[0]
verdict = ("STATE-DEPENDENCE FOUND" if abs(pre16["nw_t_diff"] or 0) >= 2.0
           else "state-independence EXTENDS to the EWS axis")
out.update({"criterion": "|NW-t| >= 2.0 on pre-2024 roster16 IN-minus-NOTIN",
            "pre2024_roster16_nw_t": pre16["nw_t_diff"], "verdict": verdict,
            "ews_run": "run_20260715_113935", "table": tab.to_dict("records")})
(RES / "a7_summary.json").write_text(json.dumps(out, indent=2))
tab.to_excel(RES / "a7_ews_axis.xlsx", index=False)

print(tab.to_string(index=False))
print(f"\ndecay localization: 2024+ months IN-share {out['roster16_2024plus_months_IN_share']}, "
      f"negative-months IN-share {out['roster16_2024plus_neg_months_IN_share']}")
print(f"\nVERDICT: {verdict}  (pre-2024 roster16 NW-t = {pre16['nw_t_diff']})")
