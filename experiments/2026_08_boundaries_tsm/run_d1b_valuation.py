#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: run_d1b_valuation.py
=============================================================================

WHAT THIS PROGRAM DOES (for someone with zero prior context)
-------------------------------------------------------------
D1b - a follow-up to the D1 boundary olympics, prompted by Arjun pointing at
"/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/T2 Top20.xlsx",
which ranks 85 factors by information ratio in this exact country universe and
shows that Shiller PE (the paper's CAPE analog, and what D1 used) is a POOR
factor here: rank 19/85 full sample, 49/85 trailing-1y, 63/85 trailing-3y.
Trailing PE ranks 2nd, Earnings Yield 6th, EV to EBITDA 8th.

The question: is there a better VALUATION variable for the boundary test?

WHY THIS IS NOT A SIMPLE SWAP - the two rankings measure different jobs:
  * T2 Top20 ranks a factor as a DIRECTIONAL signal (cheap -> outperforms).
  * The boundary test uses a variable as an EXTREMENESS marker (how far is this
    market from its own normal range, in EITHER direction?).
D1 already ran Trailing PE (t_DK -0.00) and Earnings Yield (t_DK -0.45) as
boundary markers and both were useless, while Shiller PE scored -2.88. REER is
the #1 directional factor (IR 0.62) and also failed as a boundary marker (+1.46,
wrong sign). Two independent examples of the same inversion.

A plausible reason: CAPE smooths earnings over 10 years. That sluggishness is a
handicap for ranking cheap-vs-expensive right now, but an ASSET for asking "is
this market at a historic extreme?" - which is exactly what a boundary needs.

So this script tests the valuation metrics that have NOT yet been tried as
boundary markers - EV to EBITDA, Best PE, Positive PE, Best Cash Flow, Best PBK -
plus Price-to-Book, against the incumbent Shiller PE.

STATUS: EXPLORATORY. These variables were selected on evidence EXTERNAL to the
D1 outcome (the T2 Top20 ranking), which is legitimate variable selection rather
than mining the outcome - but they were not pre-registered, so nothing here may
be promoted without its own registration and a holdout test.

HOLDOUT: enforced identically to D1 - dates >= 2021-08-01 and
ChinaA/India/Brazil/Poland excluded. Still untouched.

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb (READ-ONLY)
- .../experiments/2026_08_boundaries_tsm/results/tsmom_index.parquet

OUTPUT FILES:
- .../experiments/2026_08_boundaries_tsm/results/d1b_valuation.xlsx
- .../experiments/2026_08_boundaries_tsm/results/d1b_valuation.json

VERSION: 1.0
LAST UPDATED: 2026-08-08
AUTHOR: Claude Code (for Arjun Divecha)
DEPENDENCIES: duckdb, pandas, numpy, statsmodels, openpyxl (project venv).
USAGE:
  ./venv/bin/python experiments/2026_08_boundaries_tsm/run_d1b_valuation.py
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
WINDOW_M = 120
HOLDOUT_FROM = pd.Timestamp("2021-08-01")
HOLDOUT_COUNTRIES = {"ChinaA", "India", "Brazil", "Poland"}

# T2 Top20 full-sample rank (of 85) for context in the output.
NEW_VALUATION = {
    "EV to EBITDA": ("ev_ebitda", 8),
    "Best PE": ("best_pe", 15),
    "Positive PE": ("positive_pe", 23),
    "Best Cash Flow": ("best_cashflow", 45),
    "Best PBK": ("best_pbk", 62),
    "Best Price Sales": ("best_psales", 71),
}


def own_pct(s):
    return s.rolling(WINDOW_M, min_periods=WINDOW_M).apply(
        lambda w: (w[:-1] < w[-1]).mean(), raw=True)


def dk_t(y, X, dates):
    X = sm.add_constant(X, has_constant="add")
    m = sm.OLS(y, X, missing="drop").fit()
    idx = m.model.data.row_labels
    tg = pd.factorize(dates.loc[idx])[0]
    try:
        r = m.get_robustcov_results(cov_type="hac-groupsum", time=tg, maxlags=12)
        return dict(zip(X.columns, zip(m.params, r.tvalues)))
    except Exception:  # noqa: BLE001
        return dict(zip(X.columns, zip(m.params, [np.nan] * len(X.columns))))


def main() -> int:
    base = pd.read_parquet(OUT / "tsmom_index.parquet")
    base["date"] = pd.to_datetime(base["date"])
    universe = sorted(base.country.unique())

    con = duckdb.connect(str(BASE / "Data" / "asado.duckdb"), read_only=True)
    try:
        frames = []
        for var, (name, _) in NEW_VALUATION.items():
            d = con.execute('SELECT date,country,value FROM t2_raw WHERE variable = ?',
                            [var]).fetchdf()
            if d.empty:
                print(f"  -- {var}: ABSENT"); continue
            d = d[d.country.isin(universe)]
            d["date"] = pd.to_datetime(d["date"])
            d["field"] = name
            frames.append(d)
            print(f"  ok {var:20s} -> {name:14s} n={len(d):,}")
    finally:
        con.close()

    add = pd.concat(frames).pivot_table(index=["country", "date"], columns="field",
                                        values="value", aggfunc="last")
    p = base.set_index(["country", "date"]).join(add, how="left").reset_index()
    p = p.sort_values(["country", "date"])

    names = [n for n, _ in NEW_VALUATION.values() if n in p.columns]
    for n in names:
        p[f"{n}__own_pct"] = p.groupby("country")[n].transform(own_pct)

    ins = p[(p.date < HOLDOUT_FROM) & (~p.country.isin(HOLDOUT_COUNTRIES))].copy()
    assert ins.date.max() < HOLDOUT_FROM and not (set(ins.country) & HOLDOUT_COUNTRIES)
    print(f"\nHOLDOUT ENFORCED: in-sample {len(ins):,} rows, {ins.country.nunique()} countries, "
          f"ending {ins.date.max().date()}\n")

    rows = []
    TESTS = [(n, r) for (n, r) in
             [(v[0], v[1]) for v in NEW_VALUATION.values()] if n in names]
    TESTS += [("cape", 19), ("trailing_pe", 2), ("earnings_yield", 6)]  # incumbents for contrast
    for n, rank in TESTS:
        col = f"{n}__own_pct"
        if col not in ins.columns:
            continue
        d = ins.dropna(subset=[col, "fwd12_mkt_ex", "mom_12m_usd"]).copy()
        if len(d) < 300:
            print(f"  -- {n}: only {len(d)} obs, skipped"); continue
        d["ext"] = (d[col] - 0.5).abs() * 2
        X = pd.DataFrame({"past12": d["mom_12m_usd"], "ext": d["ext"],
                          "past12_x_ext": d["mom_12m_usd"] * d["ext"]}, index=d.index)
        res = dk_t(d["fwd12_mkt_ex"], X, d["date"])
        c, t = res["past12_x_ext"]
        signs = []
        for cc, gg in d.groupby("country"):
            if len(gg) < 60:
                continue
            Xg = sm.add_constant(pd.DataFrame(
                {"past12": gg["mom_12m_usd"], "ext": gg["ext"],
                 "past12_x_ext": gg["mom_12m_usd"] * gg["ext"]}, index=gg.index),
                has_constant="add")
            try:
                signs.append(np.sign(sm.OLS(gg["fwd12_mkt_ex"], Xg, missing="drop")
                                     .fit().params["past12_x_ext"]))
            except Exception:  # noqa: BLE001
                pass
        neg, tot = int(sum(1 for s in signs if s < 0)), len(signs)
        rows.append({"valuation_var": n, "t2top20_rank_of_85": rank, "n": len(d),
                     "countries": int(d.country.nunique()), "interaction_coef": c,
                     "interaction_t_DK": t, "ctry_paper_sign": neg, "ctry_tested": tot})

    res = pd.DataFrame(rows).sort_values("interaction_t_DK")
    print(f"{'valuation var':<18}{'T2rank':>8}{'coef':>10}{'t_DK':>8}{'|t|>=2':>8}{'countries':>12}")
    for _, r in res.iterrows():
        print(f"{r.valuation_var:<18}{r.t2top20_rank_of_85:>8}{r.interaction_coef:>10.4f}"
              f"{r.interaction_t_DK:>8.2f}{('YES' if abs(r.interaction_t_DK)>=2 else 'no'):>8}"
              f"{f'{r.ctry_paper_sign}/{r.ctry_tested}':>12}")

    corr = res[["t2top20_rank_of_85", "interaction_t_DK"]].corr(method="spearman").iloc[0, 1]
    print(f"\nSpearman corr(T2 directional rank, boundary t-stat) = {corr:+.2f}")
    print("(a POSITIVE value means better directional factors are WORSE boundary markers,")
    print(" because a better boundary marker has a more NEGATIVE t)")

    with pd.ExcelWriter(OUT / "d1b_valuation.xlsx", engine="openpyxl") as xw:
        res.to_excel(xw, sheet_name="valuation_boundary", index=False)
    (OUT / "d1b_valuation.json").write_text(json.dumps(
        {"status": "EXPLORATORY - not pre-registered", "holdout_intact": True,
         "spearman_rank_vs_t": float(corr), "rows": res.to_dict("records")},
        indent=2, default=str))
    print(f"\nwrote: {OUT/'d1b_valuation.xlsx'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
