#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: build_boundaries_panel.py
=============================================================================

WHAT THIS PROGRAM DOES (for someone with zero prior context)
-------------------------------------------------------------
Builds the shared country x month STATE-VARIABLE PANEL for the "Boundaries of
Time Series Momentum" research program (generalizing Suominen & Hjalmarsson
2025/26 to ASADO's 34-country universe). Every one of the program's 13 test
ideas is meant to become a query against this one table.

For each state variable it emits THREE normalizations side by side:

  1. own_pct    - own-history percentile rank over a trailing 10-year (120m)
                  window. The honest default; robust to outliers.
  2. peer_pct   - cross-sectional percentile across the 34 countries at each
                  date. Costs NO history, which is why it matters here: the
                  warehouse floors at 2000, so the own-history window burns the
                  sample down to ~2011+ while peer-relative starts ~2001.
  3. paper_pm1  - the PAPER'S EXACT method, for replication only: 12-month
                  moving average, then linearly scaled to [-1,+1] against the
                  trailing 10-year min/max. Fragile by construction (one outlier
                  redefines a decade) - use for replication, not as the default.

It then forms the paper's Boundaries variable in the paper's own normalization:

    Boundaries = norm(term spread)^2 + norm(CAPE)^2         (sum of squares)
    Boundaries_abs = |norm(term spread)| + |norm(CAPE)|     (paper's footnote 2 variant)

and carries BOTH return bases so the FX-decomposition test (idea #8) is a column
selection rather than a rebuild. NOTE THE DIRECTION: T2 returns are natively USD
(verified against the US-listed country ETFs), so the LOCAL leg is the
constructed one - the reverse of what the design hand-off assumed.

THREE SAFETY RULES ENCODED HERE (each from a real, documented incident)
-----------------------------------------------------------------------
1. NO FORWARD RETURNS. 1MRet/3MRet/6MRet/9MRet/12MRet are optimizer TARGETS
   labeled at window start; using one as "past return" is silent look-ahead.
   Trailing momentum here is 12MTR / 12-1MTR. evaluate_signal.py raises on the
   blacklisted names; this script never selects them.
2. NO IMF_WEO_* VARIABLES. They carry forward values to 2031-12-01 with no
   vintage tracking and are excluded outright per the ElasticNet PIT Audit.
   Verified still future-dated 2026-08-08.
3. ONE REER COPY ONLY, AND EVERY NON-T2 SOURCE IS LAGGED. T2/Bloomberg stamps
   first-of-NEXT-month (PIT-safe); BIS/IMF/OECD/WB/EPU stamp the REFERENCE
   period, so at a shared date the non-T2 copy is one month more current. That
   exact duplication (Australia REER in both conventions) fabricated +5.1%/yr
   and +0.28 Sharpe in a prior project. We take the T2 REER only and apply
   SOURCE_LAG_MONTHS to every non-T2 series.

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
    (READ-ONLY: t2_raw, bloomberg_factors, imf_factors, external_factors,
     extended_factors, macrostructure_factors)

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_08_boundaries_tsm/results/boundaries_panel.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_08_boundaries_tsm/results/boundaries_panel_coverage.xlsx
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_08_boundaries_tsm/results/boundaries_panel_summary.json

WHY THE OUTPUT IS PARQUET IN experiments/ AND NOT A WAREHOUSE TABLE
--------------------------------------------------------------------
The design hand-off asked for "boundaries_panel in asado.duckdb, strictly
additive". That is unsafe: setup_duckdb.py DELETES AND RECREATES
Data/asado.duckdb, so a persistent table there is destroyed on the next monthly
rebuild. Experiment-scoped parquet is the sanctioned location
(experiments/<name>/) and requires no change-control decision. Promoting this
to the warehouse is a separate, deliberate step.

VERSION: 1.0
LAST UPDATED: 2026-08-08
AUTHOR: Claude Code (for Arjun Divecha)

DEPENDENCIES: duckdb, pandas, numpy, openpyxl (project venv).

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
  ./venv/bin/python experiments/2026_08_boundaries_tsm/build_boundaries_panel.py

NOTES:
- The DIP-anchored ("moving anchor", hand-off idea #4) normalization is NOT
  built here: it needs a demographic fair-value model that does not yet exist.
  Building a placeholder would be worse than leaving it out. Recorded as open.
- min_periods for the 10-year window is the FULL 120 months. Shorter would
  quietly inflate the early sample.
=============================================================================
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

BASE = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
DB = BASE / "Data" / "asado.duckdb"
OUT = BASE / "experiments" / "2026_08_boundaries_tsm" / "results"

WINDOW_M = 120     # 10-year normalization window
MA_M = 12          # the paper's 12-month moving average

# Publication/convention lag in MONTHS, applied by shifting the date forward.
# T2/Bloomberg (t2_raw) is already stamped first-of-NEXT-month => 0.
SOURCE_LAG_MONTHS = {
    "t2_raw": 0,
    "bloomberg_factors": 1,          # BBG-direct: reference-period stamped
    "imf_factors": 3,
    "external_factors_bis": 3,
    "external_factors_wb": 5,
    "external_factors_epu": 2,
    "extended_factors": 3,
    "macrostructure_factors": 5,
}

# (table, variable, output_name, lag_key)
PULL = [
    # --- returns / momentum (USD natively — see CURRENCY BASIS note above) --
    ("t2_raw", "Tot Return Index", "tri_usd", "t2_raw"),
    ("t2_raw", "Currency", "fx_lcu_per_usd", "t2_raw"),
    ("t2_raw", "12MTR", "mom_12m_usd", "t2_raw"),
    ("t2_raw", "12-1MTR", "mom_12_1m_usd", "t2_raw"),
    # --- term-spread legs ---------------------------------------------------
    ("bloomberg_factors", "BBG_Govt_Bond_10Y", "y10", "bloomberg_factors"),
    ("bloomberg_factors", "BBG_Govt_Bond_2Y", "y2", "bloomberg_factors"),
    ("extended_factors", "BIS_Policy_Rate", "policy_rate", "extended_factors"),
    ("imf_factors", "IMF_TBill_Rate", "tbill", "imf_factors"),
    ("imf_factors", "IMF_Money_Market_Rate", "mmrate", "imf_factors"),
    # --- valuation ----------------------------------------------------------
    ("t2_raw", "Shiller PE", "cape", "t2_raw"),
    ("t2_raw", "Earnings Yield", "earnings_yield", "t2_raw"),
    ("t2_raw", "Trailing PE", "trailing_pe", "t2_raw"),
    ("t2_raw", "Best Div Yield", "div_yield", "t2_raw"),
    # --- candidate boundary state variables (idea #1 "boundary olympics") ---
    # REER: T2 COPY ONLY. Never also BIS_REER - see safety rule 3.
    ("t2_raw", "REER", "reer", "t2_raw"),
    ("t2_raw", "Current Account", "current_account", "t2_raw"),
    ("external_factors", "BIS_Credit_GDP_Gap", "credit_gap", "external_factors_bis"),
    ("external_factors", "BIS_Property_Price", "property_price", "external_factors_bis"),
    ("external_factors", "WB_FX_Reserves", "fx_reserves", "external_factors_wb"),
    ("external_factors", "OECD_CLI", "oecd_cli", "external_factors_bis"),
    ("external_factors", "EPU", "epu", "external_factors_epu"),
]

# Variables that get the full three-normalization treatment.
STATE_VARS = ["cape", "earnings_yield", "trailing_pe", "div_yield", "reer",
              "current_account", "credit_gap", "property_price", "fx_reserves",
              "oecd_cli", "epu", "term_spread_10y2y", "term_spread_10y3m"]

FORWARD_RETURN_BLACKLIST = {"1MRet", "3MRet", "6MRet", "9MRet", "12MRet",
                            "1DRet", "5DRet", "20DRet", "60DRet", "120DRet"}


def load_long() -> pd.DataFrame:
    """One read-only pass; connection closed before any analysis."""
    for _, var, _, _ in PULL:
        if var in FORWARD_RETURN_BLACKLIST:
            raise ValueError(f"{var} is a FORWARD return - refusing to build a look-ahead panel")
    con = duckdb.connect(str(DB), read_only=True)
    try:
        # The T2 universe IS the universe: it is the only source of returns, so a
        # country without it can never enter a momentum test. The macro tables
        # (WB/IMF/BIS) carry 40+ countries; keeping them would pad the panel with
        # rows that can never be used and inflate every coverage count.
        universe = [r[0] for r in con.execute(
            "SELECT DISTINCT country FROM t2_raw ORDER BY 1").fetchall()]
        print(f"  T2 universe: {len(universe)} countries")
        frames = []
        for table, var, name, lag_key in PULL:
            df = con.execute(
                f'SELECT date, country, value FROM "{table}" WHERE variable = ?', [var]
            ).fetchdf()
            if df.empty:
                print(f"  -- {table}.{var}: EMPTY, skipped")
                continue
            df = df[df["country"].isin(universe)]
            df["date"] = pd.to_datetime(df["date"])
            lag = SOURCE_LAG_MONTHS[lag_key]
            if lag:
                df["date"] = df["date"] + pd.DateOffset(months=lag)
            df["date"] = df["date"].values.astype("datetime64[M]").astype("datetime64[ns]")
            df["field"] = name
            frames.append(df[["date", "country", "field", "value"]])
            print(f"  ok {name:18s} <- {table}.{var:24s} lag={lag}m  n={len(df)}")
    finally:
        con.close()
    return pd.concat(frames, ignore_index=True)


def paper_pm1(s: pd.Series) -> pd.Series:
    """The paper's normalization: 12m MA, then scaled to [-1,+1] against the
    trailing 10-year min/max of that MA."""
    ma = s.rolling(MA_M, min_periods=MA_M).mean()
    lo = ma.rolling(WINDOW_M, min_periods=WINDOW_M).min()
    hi = ma.rolling(WINDOW_M, min_periods=WINDOW_M).max()
    rng = (hi - lo).replace(0, np.nan)
    return (2.0 * (ma - lo) / rng - 1.0).clip(-1, 1)


def own_pct(s: pd.Series) -> pd.Series:
    """Own-history percentile rank in the trailing 10y window (0..1)."""
    return s.rolling(WINDOW_M, min_periods=WINDOW_M).apply(
        lambda w: (w[:-1] < w[-1]).mean(), raw=True)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    print("loading (read-only) ...")
    long = load_long()

    wide = (long.pivot_table(index=["country", "date"], columns="field",
                             values="value", aggfunc="last")
                .sort_index())

    # --- derived legs -------------------------------------------------------
    wide["term_spread_10y2y"] = wide.get("y10") - wide.get("y2")
    short = wide.get("policy_rate")
    for alt in ("tbill", "mmrate"):
        if alt in wide:
            short = short.combine_first(wide[alt]) if short is not None else wide[alt]
    wide["short_rate"] = short
    wide["term_spread_10y3m"] = wide["y10"] - wide["short_rate"]

    # CURRENCY BASIS — T2 returns are USD (owner-confirmed 2026-08-08, then
    # verified against an independent source: T2 monthly returns vs the US-listed
    # country ETFs in FDT's fdt_prices.duckdb, after shifting T2 back one month
    # to undo its first-of-NEXT-month stamping. T2 as-is beat the de-FX'd version
    # in 5 of 6 countries (Brazil .9870 vs .9737, Mexico .9679 vs .9508, Japan
    # .9343 vs .9117, S.Africa .9351 vs .9280, Korea .8376 vs .8336; Turkey tied).
    #
    # So the LOCAL leg is the one that must be CONSTRUCTED, by putting the
    # currency move back in:  (1+r_usd) * (1+ d%FX in LCU per USD) - 1.
    # (An earlier version of this script had the conversion backwards. The trap:
    # variable_registry_full calls Tot Return Index "local currency", but its
    # review_status is "model_drafted" — LLM-written and never human-verified.)
    g = wide.groupby(level="country")
    fx12 = g["fx_lcu_per_usd"].pct_change(12)
    wide["fx_ret_12m"] = fx12
    wide["mom_12m_local"] = (1 + wide["mom_12m_usd"]) * (1 + fx12) - 1

    # --- carry lower-frequency series forward BEFORE normalizing ------------
    # BIS credit gap / property prices / OECD CLI are QUARTERLY and WB reserves
    # ANNUAL. On a monthly grid they are mostly NaN, so a 120-MONTH rolling
    # window never reaches min_periods and the variable silently yields ZERO
    # usable observations -- which is exactly what happened to credit_gap, one
    # of the program's two prior-favourite boundary variables, before this fix.
    # Forward-filling is also what a live user genuinely knows: last quarter's
    # published credit gap stands until the next print. Capped at 11 months so a
    # dead series cannot be carried indefinitely.
    LOWFREQ = ["credit_gap", "property_price", "fx_reserves", "oecd_cli",
               "current_account", "epu"]
    for v in LOWFREQ:
        if v in wide.columns:
            before = int(wide[v].notna().sum())
            wide[v] = wide.groupby(level="country")[v].ffill(limit=11)
            print(f"  ffill {v:16s} {before:,} -> {int(wide[v].notna().sum()):,} obs")

    # --- three normalizations per state variable ----------------------------
    print("\nnormalizing ...")
    out = wide.copy()
    for v in STATE_VARS:
        if v not in wide.columns:
            print(f"  -- {v}: absent, skipped")
            continue
        by = wide.groupby(level="country")[v]
        out[f"{v}__own_pct"] = by.transform(own_pct)
        out[f"{v}__paper_pm1"] = by.transform(paper_pm1)
        out[f"{v}__peer_pct"] = (wide.groupby(level="date")[v]
                                     .rank(pct=True, method="average"))
        print(f"  ok {v}")

    # --- the paper's Boundaries variable ------------------------------------
    for tag, ts in (("10y2y", "term_spread_10y2y"), ("10y3m", "term_spread_10y3m")):
        t, c = out.get(f"{ts}__paper_pm1"), out.get("cape__paper_pm1")
        out[f"boundaries_{tag}_cape"] = t**2 + c**2
        out[f"boundaries_abs_{tag}_cape"] = t.abs() + c.abs()
        d = out.get("div_yield__paper_pm1")
        out[f"boundaries_{tag}_dy"] = t**2 + d**2
    # peer-relative analogue (centred to [-1,1] so the square means the same thing)
    for tag, ts in (("10y2y", "term_spread_10y2y"), ("10y3m", "term_spread_10y3m")):
        t = (out.get(f"{ts}__peer_pct") - 0.5) * 2
        c = (out.get("cape__peer_pct") - 0.5) * 2
        out[f"boundaries_peer_{tag}_cape"] = t**2 + c**2

    panel = out.reset_index()
    panel.to_parquet(OUT / "boundaries_panel.parquet", index=False)

    # --- coverage report ----------------------------------------------------
    cov = []
    for c in panel.columns:
        if c in ("country", "date"):
            continue
        nn = panel[[c, "date", "country"]].dropna(subset=[c])
        cov.append({"column": c, "n_obs": len(nn),
                    "n_countries": nn["country"].nunique() if len(nn) else 0,
                    "first_date": nn["date"].min() if len(nn) else pd.NaT,
                    "last_date": nn["date"].max() if len(nn) else pd.NaT})
    cov = pd.DataFrame(cov).sort_values("column")
    with pd.ExcelWriter(OUT / "boundaries_panel_coverage.xlsx", engine="openpyxl") as xw:
        cov.to_excel(xw, sheet_name="coverage", index=False)
        panel.head(500).to_excel(xw, sheet_name="sample_head", index=False)

    key = "boundaries_10y2y_cape"
    kk = panel.dropna(subset=[key])
    (OUT / "boundaries_panel_summary.json").write_text(json.dumps({
        "generated": pd.Timestamp.now().isoformat(timespec="seconds"),
        "rows": int(len(panel)),
        "countries": int(panel["country"].nunique()),
        "date_min": str(panel["date"].min().date()),
        "date_max": str(panel["date"].max().date()),
        "normalizations": ["own_pct (10y)", "peer_pct (cross-section)", "paper_pm1 (12m MA, [-1,1] vs 10y min/max)"],
        "dip_anchored": "NOT BUILT - needs a demographic fair-value model (idea #4)",
        "boundaries_paper_first_date": str(kk["date"].min().date()) if len(kk) else None,
        "boundaries_paper_n_countries": int(kk["country"].nunique()) if len(kk) else 0,
        "source_lag_months": SOURCE_LAG_MONTHS,
        "currency_basis": "T2 returns are USD natively; mom_12m_local is CONSTRUCTED",
        "excluded_imf_weo": True,
        "reer_copies_used": ["t2_raw.REER"],
    }, indent=2, default=str))

    print(f"\npanel: {len(panel):,} rows x {panel.shape[1]} cols, "
          f"{panel['country'].nunique()} countries, "
          f"{panel['date'].min().date()} -> {panel['date'].max().date()}")
    if len(kk):
        print(f"paper Boundaries usable from {kk['date'].min().date()} "
              f"across {kk['country'].nunique()} countries ({len(kk):,} obs)")
    print(f"\nwrote: {OUT/'boundaries_panel.parquet'}")
    print(f"wrote: {OUT/'boundaries_panel_coverage.xlsx'}")
    print(f"wrote: {OUT/'boundaries_panel_summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
