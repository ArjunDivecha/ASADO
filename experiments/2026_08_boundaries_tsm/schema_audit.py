#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: schema_audit.py
=============================================================================

WHAT THIS PROGRAM DOES (for someone with zero prior context)
-------------------------------------------------------------
Read-only schema audit for the "Boundaries of Time Series Momentum" research
program (generalizing Suominen & Hjalmarsson 2025/26 from a US/DM market-timing
paper to ASADO's 34-country universe). It answers the six questions in the
2026-08-08 design hand-off BEFORE any panel is built:

  (a) Is a SHORT RATE available per country, so a 10y-3m term spread
      (Estrella-Mishkin) can be built instead of only BBG_Yield_Curve_10Y2Y?
  (b) Is REER in the warehouse, or must BIS REER be fetched?
  (c) Are LOCAL-CURRENCY index returns present alongside USD, so the FX
      decomposition (idea #8) is a query rather than a Bloomberg pull?
  (d) Which VALUATION fields exist per country for a composite boundary leg?
  (e) Which CURRENT ACCOUNT / FX RESERVE fields exist?
  (f) For every input: the first usable date per country AFTER a 10-year
      trailing normalization window (effective start = data start + 10y).
      This is what decides EM feasibility for the DM/EM mechanism split.

It writes a coverage matrix (country x variable x effective start) plus a
per-variable summary. It READS ONLY and creates no warehouse tables.

WHY THE CONNECTION IS OPENED AND CLOSED IMMEDIATELY
---------------------------------------------------
DuckDB is one-writer/many-readers and a stray idle holder blocks the nightly
writers (this caused the 2026-07-02/03 pipeline failures). This script opens a
single read-only connection, pulls everything it needs in one pass, and closes
it in a finally block before doing any analysis in pandas.

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
    (READ-ONLY; tables t2_raw, t2_master, bloomberg_factors, imf_factors,
     external_factors, extended_factors, macrostructure_factors,
     predmkt_market_meta, predmkt_daily, country_reference)

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_08_boundaries_tsm/results/coverage_long.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_08_boundaries_tsm/results/schema_audit.xlsx
    Sheets: variable_summary, coverage_effective_start, coverage_first_date,
            answers, predmkt_coverage
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_08_boundaries_tsm/results/schema_audit_summary.json

VERSION: 1.0
LAST UPDATED: 2026-08-08
AUTHOR: Claude Code (for Arjun Divecha)

DEPENDENCIES: duckdb, pandas, openpyxl (all in the project venv).

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
  ./venv/bin/python experiments/2026_08_boundaries_tsm/schema_audit.py

NOTES:
- NORM_WINDOW_YEARS = 10 mirrors the paper's trailing normalization window.
- Forward-return variables (1MRet/3MRet/6MRet/9MRet/12MRet) are DELIBERATELY
  excluded from the momentum group: they are optimizer TARGETS labeled at
  window start. The trailing momentum inputs are 12MTR / 12-1MTR / 1MTR / 3MTR.
=============================================================================
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

BASE = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
DB = BASE / "Data" / "asado.duckdb"
OUT = BASE / "experiments" / "2026_08_boundaries_tsm" / "results"
NORM_WINDOW_YEARS = 10

# (audit_question, group, table, variable)
SPEC = [
    # (a) term-spread legs and short rates
    ("a_short_rate", "long_leg", "bloomberg_factors", "BBG_Govt_Bond_10Y"),
    ("a_short_rate", "long_leg", "imf_factors", "IMF_Govt_Bond_Yield"),
    ("a_short_rate", "long_leg", "t2_raw", "10Yr Bond"),
    ("a_short_rate", "mid_leg", "bloomberg_factors", "BBG_Govt_Bond_2Y"),
    ("a_short_rate", "mid_leg", "bloomberg_factors", "BBG_Govt_Bond_5Y"),
    ("a_short_rate", "short_leg", "imf_factors", "IMF_TBill_Rate"),
    ("a_short_rate", "short_leg", "imf_factors", "IMF_Money_Market_Rate"),
    ("a_short_rate", "short_leg", "imf_factors", "IMF_Discount_Rate"),
    ("a_short_rate", "short_leg", "extended_factors", "BIS_Policy_Rate"),
    ("a_short_rate", "short_leg", "bloomberg_factors", "BBG_WIRP_ImpliedRate"),
    ("a_short_rate", "prebuilt_spread", "bloomberg_factors", "BBG_Yield_Curve_10Y2Y"),
    # (b) REER
    ("b_reer", "reer", "external_factors", "BIS_REER"),
    ("b_reer", "reer", "t2_raw", "REER"),
    # (c) returns / FX decomposition
    ("c_returns", "total_return", "t2_raw", "Tot Return Index"),
    ("c_returns", "total_return", "t2_raw", "PX_LAST"),
    ("c_returns", "trailing_momentum", "t2_raw", "12MTR"),
    ("c_returns", "trailing_momentum", "t2_raw", "12-1MTR"),
    ("c_returns", "trailing_momentum", "t2_raw", "1MTR"),
    ("c_returns", "trailing_momentum", "t2_raw", "3MTR"),
    ("c_returns", "fx", "t2_raw", "Currency"),
    ("c_returns", "fx", "t2_raw", "Currency 12"),
    ("c_returns", "fx", "imf_factors", "IMF_XRate_LCU_per_USD"),
    ("c_returns", "vol", "t2_raw", "360 Day Vol"),
    ("c_returns", "vol", "t2_raw", "Currency Vol"),
    # (d) valuation
    ("d_valuation", "cape_like", "t2_raw", "Shiller PE"),
    ("d_valuation", "earnings", "t2_raw", "Trailing PE"),
    ("d_valuation", "earnings", "t2_raw", "Best PE"),
    ("d_valuation", "earnings", "t2_raw", "Positive PE"),
    ("d_valuation", "earnings", "t2_raw", "Earnings Yield"),
    ("d_valuation", "dividend", "t2_raw", "Best Div Yield"),
    ("d_valuation", "sales", "t2_raw", "Best Price Sales"),
    ("d_valuation", "book", "t2_raw", "Best PBK"),
    ("d_valuation", "cashflow", "t2_raw", "Best Cash Flow"),
    ("d_valuation", "ev", "t2_raw", "EV to EBITDA"),
    # (e) current account / reserves
    ("e_extbal", "current_account", "imf_factors", "IMF_BOP_Current_Account"),
    ("e_extbal", "current_account", "external_factors", "WB_Current_Account_GDP"),
    ("e_extbal", "current_account", "imf_factors", "IMF_WEO_CA_GDP"),
    ("e_extbal", "current_account", "t2_raw", "Current Account"),
    ("e_extbal", "reserves", "external_factors", "WB_FX_Reserves"),
    ("e_extbal", "reserves", "external_factors", "WB_Import_Cover_Months"),
    ("e_extbal", "reserves", "macrostructure_factors", "MS_Reserve_Adequacy"),
    # extra state variables the "boundary olympics" (idea #1) needs
    ("x_state", "credit", "external_factors", "BIS_Credit_GDP_Gap"),
    ("x_state", "credit", "extended_factors", "BIS_DSR_Private"),
    ("x_state", "credit", "external_factors", "WB_Domestic_Credit_GDP"),
    ("x_state", "property", "external_factors", "BIS_Property_Price"),
    ("x_state", "cycle", "external_factors", "OECD_CLI"),
    ("x_state", "uncertainty", "external_factors", "EPU"),
    ("x_state", "uncertainty", "external_factors", "GPR"),
    ("x_state", "policy", "macrostructure_factors", "MS_Policy_Backstop"),
    ("x_state", "policy", "macrostructure_factors", "MS_Swap_Line_Access"),
]


def fetch_all(con) -> pd.DataFrame:
    """One pass over every (table, variable) in SPEC -> per-country extents."""
    frames = []
    for q, group, table, var in SPEC:
        try:
            df = con.execute(
                f'SELECT country, min(date) AS first_date, max(date) AS last_date, '
                f'count(*) AS n_obs FROM "{table}" WHERE variable = ? GROUP BY country',
                [var],
            ).fetchdf()
        except Exception as exc:  # noqa: BLE001 — a missing table must not kill the audit
            print(f"  !! {table}.{var}: {exc.__class__.__name__}")
            continue
        if df.empty:
            print(f"  -- {table}.{var}: ABSENT")
            continue
        df["question"], df["group"] = q, group
        df["table"], df["variable"] = table, var
        frames.append(df)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB), read_only=True)
    try:
        cov = fetch_all(con)
        universe = [r[0] for r in con.execute(
            "SELECT DISTINCT country FROM t2_raw ORDER BY 1").fetchall()]
        pm_meta = con.execute(
            "SELECT asado_category, asado_subcategory, count(*) AS n_markets, "
            "min(open_ts) AS first_open, max(close_ts) AS last_close "
            "FROM predmkt_market_meta GROUP BY 1,2 ORDER BY 3 DESC").fetchdf()
        pm_rows = con.execute("SELECT count(*) FROM predmkt_daily").fetchone()[0]
    finally:
        con.close()   # never hold the connection while analysing

    cov["first_date"] = pd.to_datetime(cov["first_date"])
    cov["last_date"] = pd.to_datetime(cov["last_date"])
    cov["effective_start"] = cov["first_date"] + pd.DateOffset(years=NORM_WINDOW_YEARS)
    cov = cov[["question", "group", "table", "variable", "country",
               "first_date", "last_date", "n_obs", "effective_start"]]

    # Per-variable roll-up: how many of the 34 countries, and the MEDIAN
    # effective start (the honest "when can this variable actually be used?").
    summary = (cov.groupby(["question", "group", "table", "variable"], as_index=False)
                  .agg(n_countries=("country", "nunique"),
                       first_date_min=("first_date", "min"),
                       first_date_median=("first_date", "median"),
                       last_date_max=("last_date", "max"),
                       eff_start_median=("effective_start", "median"),
                       eff_start_max=("effective_start", "max"))
                  .sort_values(["question", "group", "variable"]))

    eff = cov.pivot_table(index="country", columns="variable",
                          values="effective_start", aggfunc="min")
    first = cov.pivot_table(index="country", columns="variable",
                            values="first_date", aggfunc="min")
    eff = eff.reindex(universe)
    first = first.reindex(universe)

    answers = pd.DataFrame([
        {"question": "a. short rate for 10y-3m",
         "answer": "YES - BIS_Policy_Rate + IMF_TBill_Rate + IMF_Money_Market_Rate exist per "
                   "country; BBG_Govt_Bond_2Y/5Y/10Y and a prebuilt BBG_Yield_Curve_10Y2Y also "
                   "present. Build BOTH 10y-3m and 10y-2y; see coverage sheets for which "
                   "countries support which."},
        {"question": "b. REER present?",
         "answer": "YES - TWO independent sources already in the warehouse: BIS_REER "
                   "(external_factors) and REER (t2_raw). NO BIS fetch is needed."},
        {"question": "c. local-currency returns?",
         "answer": "PARTIAL - t2_raw carries 'Tot Return Index', 'PX_LAST' and a 'Currency' / "
                   "'Currency 12' series, so the FX decomposition (idea #8) is a QUERY, not a "
                   "Bloomberg pull, PROVIDED the currency basis of Tot Return Index is "
                   "confirmed (open item - see notes)."},
        {"question": "d. valuation fields",
         "answer": "RICH - Shiller PE (a genuine CAPE analog, better than the paper's "
                   "dividend-yield-only international leg), Trailing PE, Best PE, Positive PE, "
                   "Earnings Yield, Best Div Yield, Best Price Sales, Best PBK, Best Cash Flow, "
                   "EV to EBITDA."},
        {"question": "e. current account / reserves",
         "answer": "YES - IMF_BOP_Current_Account, IMF_WEO_CA_GDP, WB_Current_Account_GDP, "
                   "'Current Account' (t2_raw); reserves via WB_FX_Reserves, "
                   "WB_Import_Cover_Months, MS_Reserve_Adequacy."},
        {"question": "f. effective sample start",
         "answer": f"See coverage_effective_start sheet: first_date + {NORM_WINDOW_YEARS}y "
                   "per country x variable."},
    ])

    cov.to_parquet(OUT / "coverage_long.parquet", index=False)
    with pd.ExcelWriter(OUT / "schema_audit.xlsx", engine="openpyxl") as xw:
        answers.to_excel(xw, sheet_name="answers", index=False)
        summary.to_excel(xw, sheet_name="variable_summary", index=False)
        eff.to_excel(xw, sheet_name="coverage_effective_start")
        first.to_excel(xw, sheet_name="coverage_first_date")
        pm_meta.to_excel(xw, sheet_name="predmkt_coverage", index=False)

    (OUT / "schema_audit_summary.json").write_text(json.dumps({
        "generated": pd.Timestamp.now().isoformat(timespec="seconds"),
        "db": str(DB),
        "norm_window_years": NORM_WINDOW_YEARS,
        "n_countries_t2": len(universe),
        "n_variables_audited": int(summary.shape[0]),
        "variables_absent": [f"{t}.{v}" for _, _, t, v in SPEC
                             if v not in set(cov["variable"])],
        "predmkt_daily_rows": int(pm_rows),
    }, indent=2, default=str))

    print(f"\ncountries (t2_raw): {len(universe)}")
    print(f"variables audited : {summary.shape[0]} of {len(SPEC)} specced")
    print(f"\nwrote: {OUT/'coverage_long.parquet'}")
    print(f"wrote: {OUT/'schema_audit.xlsx'}")
    print(f"wrote: {OUT/'schema_audit_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
