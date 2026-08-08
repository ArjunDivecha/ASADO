#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: run_replication.py
=============================================================================

WHAT THIS PROGRAM DOES (for someone with zero prior context)
-------------------------------------------------------------
Sequencing step 1 of the Boundaries-of-TSM program: replicate the two headline
claims of Suominen & Hjalmarsson ("Boundaries of Time Series Momentum") on
ASADO's 34-country universe, exactly as pre-registered in PREREGISTRATION.md
(committed BEFORE this script was first executed).

  Spec A - TSMOM predictability (paper Table 4/5 analog)
      fwd12_tsmom ~ Boundaries                      paper's claim: b < 0
  Spec B - reversal at boundaries (paper Table 6 analog)
      fwd12_mkt_excess ~ past12 + Boundaries + past12 x Boundaries
                                                    paper's claim: b3 < 0

DEPENDENT VARIABLE - the MOP (2012) 25-strategy TSMOM index, per country:
  monthly market excess r_ex = tri_usd pct change - US rf/1200
  lookbacks L in {1,3,6,9,12} x holding H in {1,3,6,9,12} = 25 strategies
  strategy return (MOP form) = sign(cum r_ex over the L months ending t-1-j)
                               * r_ex[t], averaged over vintages j=0..H-1
  index = equal-weighted mean of all 25.  NO volatility scaling.

STANDARD ERRORS: month-clustered OLS (headline). Newey-West 12 is deliberately
NOT the headline - the paper's own Hodrick(1992)/IVX tables show it overstates
significance on overlapping 12-month returns. NW-12 is reported alongside ONLY
to quantify that overstatement.

TWO CONSTRUCTIONS ARE RUN, AND THEY ARE NOT EQUALS:
  peer-relative  = PRIMARY (23 countries from 2001-02)
  paper-exact    = sign-and-shape check only (18 countries from 2010-12).
                   Attenuated t-stats there are PRE-DECLARED as expected and are
                   a statement about our warehouse sample, not about the paper.

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_08_boundaries_tsm/results/boundaries_panel.parquet
    (frozen; md5 asserted at runtime against the pre-registration)

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_08_boundaries_tsm/results/replication_results.xlsx
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_08_boundaries_tsm/results/replication_results.json
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_08_boundaries_tsm/results/tsmom_index.parquet

VERSION: 1.0
LAST UPDATED: 2026-08-08
AUTHOR: Claude Code (for Arjun Divecha)

DEPENDENCIES: pandas, numpy, statsmodels, openpyxl (project venv - no new packages).

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
  ./venv/bin/python experiments/2026_08_boundaries_tsm/run_replication.py
=============================================================================
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

BASE = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
OUT = BASE / "experiments" / "2026_08_boundaries_tsm" / "results"
PANEL = OUT / "boundaries_panel.parquet"
PREREG_MD5 = "ecf8d8149f30ed8868547464b25fae0d"

LOOKBACKS = [1, 3, 6, 9, 12]
HOLDINGS = [1, 3, 6, 9, 12]
FWD = 12


def assert_frozen_input():
    md5 = hashlib.md5(PANEL.read_bytes()).hexdigest()
    if md5 != PREREG_MD5:
        raise SystemExit(
            f"REFUSING TO RUN: panel md5 {md5} != pre-registered {PREREG_MD5}.\n"
            "The frozen input changed; re-register before running.")
    print(f"frozen input verified: md5 {md5}")


def build_tsmom(df: pd.DataFrame) -> pd.DataFrame:
    """MOP 25-strategy TSMOM index per country, from tri_usd and the US rf."""
    df = df.sort_values(["country", "date"]).copy()
    g = df.groupby("country", group_keys=False)
    df["mkt_ret"] = g["tri_usd"].pct_change()
    df["r_ex"] = df["mkt_ret"] - df["rf_m"]

    out = []
    for c, gg in df.groupby("country"):
        gg = gg.sort_values("date").reset_index(drop=True)
        r = gg["r_ex"]
        # cumulative excess over each lookback, as known at t-1 (shifted).
        sig = {}
        for L in LOOKBACKS:
            cum = r.rolling(L, min_periods=L).sum()
            sig[L] = np.sign(cum)
        strat = []
        for L in LOOKBACKS:
            for H in HOLDINGS:
                # vintages: signal formed at t-1-j, applied to r[t]
                acc = None
                for j in range(H):
                    s = sig[L].shift(1 + j)
                    v = s * r
                    acc = v if acc is None else acc.add(v, fill_value=np.nan)
                strat.append(acc / H)
        gg["tsmom"] = pd.concat(strat, axis=1).mean(axis=1)
        out.append(gg)
    return pd.concat(out, ignore_index=True)


def fwd_compound(s: pd.Series, k: int) -> pd.Series:
    """Compounded return over t+1..t+k (strictly forward; no contemporaneous term)."""
    return (1 + s).shift(-1).rolling(k, min_periods=k).apply(np.prod, raw=True).shift(-(k - 1)) - 1


def cluster_ols(y, X, groups, label):
    X = sm.add_constant(X, has_constant="add")
    m = sm.OLS(y, X, missing="drop").fit()
    cl = m.get_robustcov_results(cov_type="cluster", groups=groups.loc[m.model.data.row_labels])
    nw = m.get_robustcov_results(cov_type="HAC", maxlags=12)
    rows = []
    for i, nm in enumerate(X.columns):
        rows.append({"spec": label, "term": nm, "coef": cl.params[i],
                     "t_clustered": cl.tvalues[i], "p_clustered": cl.pvalues[i],
                     "t_NW12": nw.tvalues[i]})
    return rows, {"n": int(m.nobs), "adj_r2": float(m.rsquared_adj)}


def main() -> int:
    assert_frozen_input()
    p = pd.read_parquet(PANEL)

    rf = (p[p.country == "U.S."][["date", "short_rate"]]
          .rename(columns={"short_rate": "rf_ann"}))
    p = p.merge(rf, on="date", how="left")
    p["rf_m"] = p["rf_ann"] / 1200.0

    p = build_tsmom(p)

    # forward variables, strictly t+1..t+12
    p = p.sort_values(["country", "date"])
    g = p.groupby("country", group_keys=False)
    p["fwd12_tsmom"] = g["tsmom"].apply(lambda s: fwd_compound(s, FWD))
    p["fwd12_mkt_ex"] = g["r_ex"].apply(lambda s: fwd_compound(s, FWD))

    # ---- hand-check the alignment on one country before trusting the panel ---
    jp = p[p.country == "Japan"].sort_values("date").reset_index(drop=True)
    i = jp.index[(jp.date == "2015-01-01")][0]
    manual = (1 + jp["r_ex"].iloc[i + 1:i + 1 + FWD]).prod() - 1
    auto = jp["fwd12_mkt_ex"].iloc[i]
    print(f"alignment hand-check (Japan 2015-01): manual {manual:.6f} vs computed {auto:.6f} "
          f"-> {'OK' if abs(manual - auto) < 1e-9 else 'MISMATCH'}")
    if not abs(manual - auto) < 1e-9:
        raise SystemExit("REFUSING TO RUN: forward-return alignment failed its hand-check.")

    p.to_parquet(OUT / "tsmom_index.parquet", index=False)

    CONSTRUCTIONS = {
        "peer_relative (PRIMARY)": "boundaries_peer_10y2y_cape",
        "paper_exact (shape check)": "boundaries_10y2y_cape",
    }
    all_rows, meta = [], {}
    for lab, col in CONSTRUCTIONS.items():
        d = p.dropna(subset=[col, "fwd12_tsmom", "fwd12_mkt_ex", "mom_12m_usd"]).copy()
        if d.empty:
            print(f"  {lab}: no observations"); continue
        d["month"] = d["date"]
        # Spec A
        rA, mA = cluster_ols(d["fwd12_tsmom"], d[[col]].rename(columns={col: "Boundaries"}),
                             d["month"], f"A | {lab}")
        # Spec B
        Xb = pd.DataFrame({"past12": d["mom_12m_usd"], "Boundaries": d[col],
                           "past12_x_Boundaries": d["mom_12m_usd"] * d[col]}, index=d.index)
        rB, mB = cluster_ols(d["fwd12_mkt_ex"], Xb, d["month"], f"B | {lab}")
        all_rows += rA + rB
        meta[lab] = {"col": col, "countries": int(d.country.nunique()),
                     "date_min": str(d.date.min().date()), "date_max": str(d.date.max().date()),
                     "specA": mA, "specB": mB}
        print(f"\n=== {lab}  ({d.country.nunique()} countries, {d.date.min().date()} -> {d.date.max().date()}) ===")
        for r in rA + rB:
            if r["term"] == "const":
                continue
            print(f"  {r['spec']:34s} {r['term']:22s} coef {r['coef']:+.5f}  "
                  f"t_clustered {r['t_clustered']:+6.2f}  (t_NW12 {r['t_NW12']:+6.2f})")

    res = pd.DataFrame(all_rows)
    with pd.ExcelWriter(OUT / "replication_results.xlsx", engine="openpyxl") as xw:
        res.to_excel(xw, sheet_name="regressions", index=False)
        pd.DataFrame(meta).T.to_excel(xw, sheet_name="meta")
    (OUT / "replication_results.json").write_text(
        json.dumps({"generated": pd.Timestamp.now().isoformat(timespec="seconds"),
                    "panel_md5": PREREG_MD5, "meta": meta,
                    "rows": res.to_dict("records")}, indent=2, default=str))
    print(f"\nwrote: {OUT/'replication_results.xlsx'}")
    print(f"wrote: {OUT/'replication_results.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
