#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: diagnose_signflip.py
=============================================================================

WHY THIS EXISTS
---------------
run_replication.py produced a SIGN FLIP that PREREGISTRATION.md pre-declared as
"a finding, not a bug": the paper's own construction replicates both headline
claims, while the pre-registered PRIMARY (peer-relative) construction gives the
OPPOSITE sign, significantly.

That comparison is CONFOUNDED. The two arms differ in two ways at once:
  (i)  normalization  - trailing 10y min/max of a 12m MA  vs  cross-sectional pct
  (ii) sample         - 18 countries from 2010-12         vs  23 from 2001-02
A flip could be caused by either. This script separates them:

  ARM 1  paper-exact,     paper sample          (the replication)
  ARM 2  peer-relative,   SAME rows as ARM 1    <- isolates NORMALIZATION
  ARM 3  peer-relative,   full sample           (the primary)
  ARM 4  paper-exact,     full sample where available
ARM 1 vs ARM 2 is the normalization effect holding sample fixed.
ARM 2 vs ARM 3 is the sample effect holding normalization fixed.

It also upgrades the standard errors. Month-clustering handles contemporaneous
cross-country correlation but NOT the serial correlation induced by overlapping
12-month forward returns - and on this data it produced LARGER t-stats than
NW-12, i.e. it flatters the result. Driscoll-Kraay (statsmodels 'hac-groupsum',
lag 12) handles BOTH and is reported here as the honest headline. No new
packages are installed; this stays in the project venv read-only.

INPUT FILES:
- .../experiments/2026_08_boundaries_tsm/results/tsmom_index.parquet

OUTPUT FILES:
- .../experiments/2026_08_boundaries_tsm/results/signflip_diagnosis.xlsx
- .../experiments/2026_08_boundaries_tsm/results/signflip_diagnosis.json

VERSION: 1.0
LAST UPDATED: 2026-08-08
AUTHOR: Claude Code (for Arjun Divecha)
DEPENDENCIES: pandas, numpy, statsmodels, openpyxl (project venv).
USAGE:
  ./venv/bin/python experiments/2026_08_boundaries_tsm/diagnose_signflip.py
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
PAPER, PEER = "boundaries_10y2y_cape", "boundaries_peer_10y2y_cape"


def fit(y, X, d, label):
    X = sm.add_constant(X, has_constant="add")
    m = sm.OLS(y, X, missing="drop").fit()
    idx = m.model.data.row_labels
    cl = m.get_robustcov_results(cov_type="cluster", groups=d["date"].loc[idx])
    # Driscoll-Kraay: handles cross-sectional AND serial dependence.
    tg = pd.factorize(d["date"].loc[idx])[0]
    try:
        dk = m.get_robustcov_results(cov_type="hac-groupsum", time=tg, maxlags=12)
        dk_t = dk.tvalues
    except Exception as exc:  # noqa: BLE001
        print(f"    (DK unavailable: {exc.__class__.__name__})")
        dk_t = [np.nan] * len(X.columns)
    return [{"arm": label, "term": n, "coef": cl.params[i],
             "t_clustered": cl.tvalues[i], "t_driscoll_kraay": dk_t[i],
             "n": int(m.nobs), "countries": int(d["country"].loc[idx].nunique())}
            for i, n in enumerate(X.columns)]


def specs(d, col, label, rows):
    rows += fit(d["fwd12_tsmom"], d[[col]].rename(columns={col: "Boundaries"}), d, f"A | {label}")
    Xb = pd.DataFrame({"past12": d["mom_12m_usd"], "Boundaries": d[col],
                       "past12_x_Boundaries": d["mom_12m_usd"] * d[col]}, index=d.index)
    rows += fit(d["fwd12_mkt_ex"], Xb, d, f"B | {label}")


def main() -> int:
    p = pd.read_parquet(OUT / "tsmom_index.parquet")
    need = ["fwd12_tsmom", "fwd12_mkt_ex", "mom_12m_usd"]

    paper_rows = p.dropna(subset=need + [PAPER]).copy()
    peer_rows = p.dropna(subset=need + [PEER]).copy()
    # ARM 2: peer-relative restricted to EXACTLY the paper arm's country-dates
    keys = set(zip(paper_rows.country, paper_rows.date))
    matched = peer_rows[[k in keys for k in zip(peer_rows.country, peer_rows.date)]].copy()

    print(f"ARM1 paper-exact  : {len(paper_rows):5,} obs, {paper_rows.country.nunique()} countries, "
          f"{paper_rows.date.min().date()} -> {paper_rows.date.max().date()}")
    print(f"ARM2 peer@paper   : {len(matched):5,} obs, {matched.country.nunique()} countries, "
          f"{matched.date.min().date()} -> {matched.date.max().date()}")
    print(f"ARM3 peer full    : {len(peer_rows):5,} obs, {peer_rows.country.nunique()} countries, "
          f"{peer_rows.date.min().date()} -> {peer_rows.date.max().date()}")

    rows = []
    specs(paper_rows, PAPER, "ARM1 paper-exact @ paper sample", rows)
    specs(matched, PEER, "ARM2 peer-relative @ SAME sample", rows)
    specs(peer_rows, PEER, "ARM3 peer-relative @ full sample", rows)

    # correlation of the two Boundaries measures on shared rows
    both = p.dropna(subset=[PAPER, PEER])
    corr = both[PAPER].corr(both[PEER])
    print(f"\ncorr(paper Boundaries, peer Boundaries) on {len(both):,} shared rows = {corr:.4f}")

    res = pd.DataFrame(rows)
    show = res[res.term != "const"]
    print()
    for arm in show.arm.unique():
        print(f"--- {arm}")
        for _, r in show[show.arm == arm].iterrows():
            print(f"     {r['term']:22s} coef {r['coef']:+.5f}  t_clust {r['t_clustered']:+6.2f}  "
                  f"t_DK {r['t_driscoll_kraay']:+6.2f}   (n={r['n']:,})")

    with pd.ExcelWriter(OUT / "signflip_diagnosis.xlsx", engine="openpyxl") as xw:
        res.to_excel(xw, sheet_name="arms", index=False)
    (OUT / "signflip_diagnosis.json").write_text(json.dumps(
        {"corr_paper_vs_peer_boundaries": float(corr),
         "rows": res.to_dict("records")}, indent=2, default=str))
    print(f"\nwrote: {OUT/'signflip_diagnosis.xlsx'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
