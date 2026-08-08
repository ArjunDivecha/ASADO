#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: run_d1_olympics.py
=============================================================================

WHAT THIS PROGRAM DOES (for someone with zero prior context)
-------------------------------------------------------------
D1, the "boundary olympics", exactly as pre-registered in PREREGISTRATION.md.

The replication (RESULTS.md) tested ONE guess about where the boundaries of
momentum sit: the paper's guess, valuation (CAPE) plus the yield-curve slope.
It came out with the right sign but no significance, and - the decisive part -
only 8 of 16 countries showed it at all.

D1 asks the obvious follow-up: was the PREMISE wrong, or just the CHOICE of
variable? Instead of assuming valuation marks the boundary, it runs the same
test across candidate state variables and asks which - if any - actually marks
where trends break. Arjun's stated prior is that REER and the credit gap beat
valuation.

TEST (per state variable), the handoff's "past 12m return x proximity-to-own-extreme":
    extremeness = |own-history percentile - 0.5| x 2      (0 = at its median,
                                                           1 = at its own extreme)
    fwd12_mkt_excess ~ past12 + extremeness + past12 x extremeness
The pre-registered KILL CRITERION is on the interaction term: if NO state
variable reaches |t| >= 2 there, the "extremes break trend" premise dies for
this universe.

HOLDOUT DISCIPLINE (pre-registered, enforced in code):
  - the last 5 years (from 2021-08-01) are EXCLUDED
  - ChinaA, India, Brazil, Poland are EXCLUDED entirely
This script asserts the exclusion and will not run without it.

MULTIPLE TESTING: three variables were registered (REER, credit_gap, CAPE).
Those are the PRIMARY test and a Bonferroni threshold for 3 tests is reported
alongside. Everything else in the panel is run too but is labelled EXPLORATORY
and must not be promoted without its own registration.

PER-COUNTRY CONSISTENCY is reported for every variable, because the pooled
average is exactly what concealed the coin-flip in the replication.

INPUT FILES:
- .../experiments/2026_08_boundaries_tsm/results/tsmom_index.parquet

OUTPUT FILES:
- .../experiments/2026_08_boundaries_tsm/results/d1_olympics.xlsx
- .../experiments/2026_08_boundaries_tsm/results/d1_olympics.json

VERSION: 1.0
LAST UPDATED: 2026-08-08
AUTHOR: Claude Code (for Arjun Divecha)
DEPENDENCIES: pandas, numpy, statsmodels, openpyxl (project venv).
USAGE:
  ./venv/bin/python experiments/2026_08_boundaries_tsm/run_d1_olympics.py
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

HOLDOUT_FROM = pd.Timestamp("2021-08-01")
HOLDOUT_COUNTRIES = {"ChinaA", "India", "Brazil", "Poland"}

REGISTERED = ["reer", "credit_gap", "cape"]
EXPLORATORY = ["current_account", "fx_reserves", "property_price", "oecd_cli",
               "epu", "term_spread_10y2y", "term_spread_10y3m",
               "earnings_yield", "trailing_pe", "div_yield"]


def dk_fit(y, X, dates):
    X = sm.add_constant(X, has_constant="add")
    m = sm.OLS(y, X, missing="drop").fit()
    idx = m.model.data.row_labels
    tg = pd.factorize(dates.loc[idx])[0]
    try:
        r = m.get_robustcov_results(cov_type="hac-groupsum", time=tg, maxlags=12)
        t = list(r.tvalues)
    except Exception:  # noqa: BLE001
        t = [np.nan] * len(X.columns)
    return m, X.columns, list(m.params), t


def main() -> int:
    p = pd.read_parquet(OUT / "tsmom_index.parquet")
    p["date"] = pd.to_datetime(p["date"])

    n0, c0 = len(p), p.country.nunique()
    ins = p[(p.date < HOLDOUT_FROM) & (~p.country.isin(HOLDOUT_COUNTRIES))].copy()
    assert ins.date.max() < HOLDOUT_FROM, "holdout period leaked"
    assert not (set(ins.country) & HOLDOUT_COUNTRIES), "holdout countries leaked"
    print(f"HOLDOUT ENFORCED: {n0:,} rows/{c0} countries -> in-sample "
          f"{len(ins):,} rows/{ins.country.nunique()} countries, "
          f"ending {ins.date.max().date()}")
    print(f"  excluded: dates >= {HOLDOUT_FROM.date()}, countries {sorted(HOLDOUT_COUNTRIES)}\n")

    rows, percountry = [], []
    for tier, varlist in (("REGISTERED", REGISTERED), ("EXPLORATORY", EXPLORATORY)):
        for v in varlist:
            col = f"{v}__own_pct"
            if col not in ins.columns:
                continue
            d = ins.dropna(subset=[col, "fwd12_mkt_ex", "fwd12_tsmom", "mom_12m_usd"]).copy()
            if len(d) < 300:
                print(f"  -- {v}: only {len(d)} obs, skipped")
                continue
            d["extremeness"] = (d[col] - 0.5).abs() * 2

            X = pd.DataFrame({"past12": d["mom_12m_usd"], "extremeness": d["extremeness"],
                              "past12_x_extremeness": d["mom_12m_usd"] * d["extremeness"]},
                             index=d.index)
            _, names, coefs, ts = dk_fit(d["fwd12_mkt_ex"], X, d["date"])
            hit = dict(zip(names, zip(coefs, ts)))
            c_i, t_i = hit["past12_x_extremeness"]

            # Spec A analog: does extremeness predict trend-following returns?
            _, nA, cA, tA = dk_fit(d["fwd12_tsmom"], d[["extremeness"]], d["date"])
            cA_e, tA_e = dict(zip(nA, zip(cA, tA)))["extremeness"]

            # per-country consistency of the interaction sign
            signs = []
            for c, gg in d.groupby("country"):
                if len(gg) < 60:
                    continue
                Xg = sm.add_constant(pd.DataFrame(
                    {"past12": gg["mom_12m_usd"], "extremeness": gg["extremeness"],
                     "past12_x_extremeness": gg["mom_12m_usd"] * gg["extremeness"]},
                    index=gg.index), has_constant="add")
                try:
                    mg = sm.OLS(gg["fwd12_mkt_ex"], Xg, missing="drop").fit()
                    signs.append(np.sign(mg.params["past12_x_extremeness"]))
                except Exception:  # noqa: BLE001
                    pass
            neg = int(sum(1 for s in signs if s < 0)); tot = len(signs)
            rows.append({"tier": tier, "state_var": v, "n": len(d),
                         "countries": int(d.country.nunique()),
                         "interaction_coef": c_i, "interaction_t_DK": t_i,
                         "specA_extremeness_coef": cA_e, "specA_t_DK": tA_e,
                         "countries_with_paper_sign": neg, "countries_tested": tot,
                         "pct_paper_sign": (neg / tot if tot else np.nan)})
            percountry.append({"state_var": v, "neg": neg, "tot": tot})

    res = pd.DataFrame(rows).sort_values(["tier", "interaction_t_DK"])
    BONF = 2.39   # two-sided 5% Bonferroni for 3 registered tests
    print(f"KILL CRITERION: no state variable reaches |t_DK| >= 2 on the interaction.")
    print(f"(Bonferroni threshold for the 3 registered tests: |t| >= {BONF})\n")
    print(f"{'tier':<12}{'state_var':<20}{'inter.coef':>11}{'t_DK':>8}{'|t|>=2':>8}"
          f"{'ctry w/ paper sign':>20}")
    for _, r in res.iterrows():
        flag = "YES" if abs(r.interaction_t_DK) >= 2 else "no"
        print(f"{r.tier:<12}{r.state_var:<20}{r.interaction_coef:>11.4f}"
              f"{r.interaction_t_DK:>8.2f}{flag:>8}"
              f"{f'{r.countries_with_paper_sign}/{r.countries_tested}':>20}")

    reg = res[res.tier == "REGISTERED"]
    passed = reg[reg.interaction_t_DK.abs() >= 2]
    verdict = ("DEAD - kill criterion met: no registered state variable reached |t_DK| >= 2"
               if passed.empty else
               f"SURVIVES - {list(passed.state_var)} reached |t_DK| >= 2 in-sample")
    print(f"\nVERDICT (registered tier): {verdict}")

    with pd.ExcelWriter(OUT / "d1_olympics.xlsx", engine="openpyxl") as xw:
        res.to_excel(xw, sheet_name="olympics", index=False)
    (OUT / "d1_olympics.json").write_text(json.dumps(
        {"holdout_from": str(HOLDOUT_FROM.date()),
         "holdout_countries": sorted(HOLDOUT_COUNTRIES),
         "in_sample_rows": int(len(ins)), "verdict": verdict,
         "bonferroni_3tests": BONF,
         "rows": res.to_dict("records")}, indent=2, default=str))
    print(f"\nwrote: {OUT/'d1_olympics.xlsx'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
