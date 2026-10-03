#!/usr/bin/env python3
"""
verify_e1_split_and_gap_outcomes.py — reproducibility script for the 2026-09-23 review
"What does the data know that the price doesn't?"

What it does
------------
Re-derives, from files already on disk, the two load-bearing numbers in the review memo:

  1. The E1 network-spillover capture curve (experiments/2026_08_network_spillover_capture),
     split by period (full / 2000-23 / 2024+ / 2024 / 2025 / 2026) for each expression
     (local index, six-market futures, US ETF close-to-close, US ETF open-to-close) and
     hold horizon (1/5/21 days). Gross rows only (cost_bps is NaN). Reports annualized mean
     of `active` (top-7 vs equal-weight) and `ls` (top minus bottom) with a Newey-West t
     using lag = hold_days + 4.

  2. The honest forward scorer on ASADO's live Price-Discovery Gap Engine calls
     (gap_outcomes / outcome_attribution / gap_episodes), summarized by role
     (promoted / control / fable_claim), gap class, direction and selection month,
     with the index_information vs etf_capture split. Read from a parquet snapshot
     taken with scripts/snapshot_for_experiment.py on 2026-09-23 — this script never
     opens the live DuckDB files.

Inputs (absolute paths)
-----------------------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_08_network_spillover_capture/results/daily_series.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/review_data_vs_price_2026_09_23/snapshot_2026_09_23/gap_outcomes.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/review_data_vs_price_2026_09_23/snapshot_2026_09_23/outcome_attribution.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/review_data_vs_price_2026_09_23/snapshot_2026_09_23/gap_episodes.parquet

Outputs (absolute paths)
------------------------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/docs/review_data_vs_price_2026_09_23/verification_tables.xlsx
      sheets: e1_active, e1_ls, gap_by_role, gap_by_class, gap_by_direction, gap_by_month,
              attribution_headline, attribution_price_response, attribution_timing
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/docs/review_data_vs_price_2026_09_23/verification_tables.parquet
      (long-form union of the same tables; parquet is canonical)

Usage
-----
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO" && ./venv/bin/python docs/review_data_vs_price_2026_09_23/verify_e1_split_and_gap_outcomes.py

Notes
-----
- gap_outcomes t-statistics assume independent observations; the 21-day windows over a
  two-month sample overlap heavily, so they overstate significance badly. The memo says so.
- The E1 futures rows are top-2 of 6 roots (CF, GX, HI, NK, Z, ES) — a narrow basket, not
  comparable in breadth to the 34-market local-index / ETF rows.
- Version 1.0, 2026-09-23. Dependencies: pandas, numpy, openpyxl (project venv).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ROOT = "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
E1 = f"{ROOT}/experiments/2026_08_network_spillover_capture/results/daily_series.parquet"
SNAP = f"{ROOT}/Data/work/experiments/review_data_vs_price_2026_09_23/snapshot_2026_09_23"
OUT_DIR = f"{ROOT}/docs/review_data_vs_price_2026_09_23"
OUT_XLSX = f"{OUT_DIR}/verification_tables.xlsx"
OUT_PQ = f"{OUT_DIR}/verification_tables.parquet"

PERIODS = {"full": (2000, 2026), "2000-2023": (2000, 2023), "2024+": (2024, 2026),
           "2024": (2024, 2024), "2025": (2025, 2025), "2026": (2026, 2026)}


def nw_t(x: pd.Series, lag: int) -> tuple[float, int]:
    """Newey-West t-stat of the mean with Bartlett weights up to `lag`."""
    a = np.asarray(x, float)
    a = a[~np.isnan(a)]
    n = len(a)
    if n < 30:
        return np.nan, n
    e = a - a.mean()
    s = np.sum(e * e) / n
    for k in range(1, lag + 1):
        s += 2 * (1 - k / (lag + 1)) * np.sum(e[k:] * e[:-k]) / n
    return float(a.mean() / np.sqrt(s / n)), n


def e1_split() -> dict[str, pd.DataFrame]:
    df = pd.read_parquet(E1)
    g = df[df.cost_bps.isna()].copy()
    g["year"] = g.date.dt.year
    rows = []
    for (ex, h), sub in g.groupby(["expression", "hold_days"]):
        for pn, (a, b) in PERIODS.items():
            s = sub[(sub.year >= a) & (sub.year <= b)]
            for col in ("active", "ls"):
                t, n = nw_t(s[col], h + 4)
                rows.append(dict(expression=ex, hold_days=h, period=pn, metric=col,
                                 ann_pct=s[col].mean() * 252 * 100, nw_t=t, n_days=n))
    out = pd.DataFrame(rows)
    sheets = {}
    for col in ("active", "ls"):
        piv = out[out.metric == col].pivot_table(index=["expression", "hold_days"], columns="period",
                                                 values=["ann_pct", "nw_t"])
        piv = piv.reindex(columns=list(PERIODS), level=1).round(2)
        sheets[f"e1_{col}"] = piv
    return sheets, out


def _t(x: pd.Series) -> float:
    x = x.dropna()
    return float(x.mean() / x.std() * np.sqrt(len(x))) if len(x) > 2 else np.nan


def _summ(df: pd.DataFrame, by) -> pd.DataFrame:
    rows = []
    for k, s in df.groupby(by, dropna=False):
        rows.append(dict(key=str(k), n=len(s),
                         gross_active_pct=s.gross_active.mean() * 100, ga_median_pct=s.gross_active.median() * 100,
                         hit=(s.gross_active > 0).mean(), ga_t_iid=_t(s.gross_active),
                         index_info_pct=s.index_information.mean() * 100, ii_t_iid=_t(s.index_information),
                         etf_capture_pct=s.etf_capture.mean() * 100, ec_t_iid=_t(s.etf_capture)))
    return pd.DataFrame(rows).round(3)


def gap_outcomes() -> dict[str, pd.DataFrame]:
    go = pd.read_parquet(f"{SNAP}/gap_outcomes.parquet")
    ep = pd.read_parquet(f"{SNAP}/gap_episodes.parquet")
    at = pd.read_parquet(f"{SNAP}/outcome_attribution.parquet")
    go = go.merge(ep[["gap_id", "gap_class", "tension_score_at_open"]], on="gap_id", how="left")
    go["ym"] = pd.to_datetime(go.selection_date.astype(str), errors="coerce").dt.to_period("M").astype(str)
    nc = go[go.role != "control"]
    return {
        "gap_by_role": _summ(go, "role"),
        "gap_by_class": _summ(nc, "gap_class"),
        "gap_by_direction": _summ(nc, "direction"),
        "gap_by_month": _summ(go, ["role", "ym"]),
        "attribution_headline": pd.crosstab(at.role, at.headline_class),
        "attribution_price_response": pd.crosstab(at.role, at.price_response),
        "attribution_timing": pd.crosstab(at.role, at.timing),
    }


def main() -> None:
    e1_sheets, e1_long = e1_split()
    gap_sheets = gap_outcomes()
    with pd.ExcelWriter(OUT_XLSX) as xw:
        for name, df in {**e1_sheets, **gap_sheets}.items():
            df.to_excel(xw, sheet_name=name)
    longs = [e1_long.assign(table="e1")]
    for name, df in gap_sheets.items():
        longs.append(df.reset_index().astype(str).assign(table=name))
    pd.concat(longs, ignore_index=True).astype(str).to_parquet(OUT_PQ, index=False)
    print("wrote", OUT_XLSX)
    print("wrote", OUT_PQ)
    print(e1_sheets["e1_active"].to_string())
    print(gap_sheets["gap_by_role"].to_string(index=False))


if __name__ == "__main__":
    main()
