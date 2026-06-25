#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/build_valuation_block.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
    t2_levels_daily (read-only, attached as `asado` by loopdb): Shiller PE,
    Best PBK, Best Div Yield, Earnings Yield, Trailing PE, Inflation.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    sovereign_daily: SOV_10Y_YIELD_PCT (direct Bloomberg pull). Used for the
    ERP real-yield leg instead of t2's "10Yr Bond", which carries at least
    one wrong series (Brazil prints 2.85 when the local 10Y is ~14.8).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/valuation_monthly.parquet
    Tidy month-end panel (date, country, value, variable, source='valuation_block').
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `valuation_monthly` (idempotent rebuild from the same frame).

VERSION: 1.0
LAST UPDATED: 2026-06-11
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 3)

DESCRIPTION:
PRD Priority 7 — the valuation block for the E5 "knowable vs priced" edge
and the Layer-2 monthly pass. For each country and month-end it computes:

  VAL_CAPE              Shiller PE level
  VAL_PB                Best price/book level
  VAL_DY_PCT            Best dividend yield, percent
  VAL_EY_PCT            Forward earnings yield, percent
  VAL_TRAIL_PE          Trailing PE level
  VAL_ERP_PCT           Equity risk premium = EY - (10Y nominal - CPI YoY)
  VAL_*_PCTILE_10Y      Each metric's percentile vs its own trailing 10y
                        (0 = cheapest decade reading, 100 = richest;
                        DY and EY are inverted so 100 = rich for all)

No new Bloomberg pull is needed: every input already lands daily via the T2
manifest; the 10Y comes from the P8 sovereign_daily pull. Monthly grid by
design (valuation is a slow variable; the monthly pass consumes it).

DEPENDENCIES:
- duckdb, pandas, numpy (project venv)

USAGE:
  python scripts/loop/build_valuation_block.py            # rebuild
  python scripts/loop/build_valuation_block.py --check    # latest snapshot

NOTES:
- Non-positive PE/PB/DY/EY observations are treated as missing (Brazil's
  Shiller PE prints exact 0.0 for stretches — upstream data gap, not data).
- ERP requires all three legs at the same month-end; missing legs -> NaN,
  coverage is reported, nothing is silently filled.
=============================================================================
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.loop.loopdb import loop_connection  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PANEL_PATH = BASE_DIR / "Data" / "work" / "loop" / "valuation_monthly.parquet"

T2_UNIVERSE = [
    "Australia", "Brazil", "Canada", "Chile", "ChinaA", "ChinaH", "Denmark",
    "France", "Germany", "Hong Kong", "India", "Indonesia", "Italy", "Japan",
    "Korea", "Malaysia", "Mexico", "NASDAQ", "Netherlands", "Philippines",
    "Poland", "Saudi Arabia", "Singapore", "South Africa", "Spain", "Sweden",
    "Switzerland", "Taiwan", "Thailand", "Turkey", "U.K.", "U.S.",
    "US SmallCap", "Vietnam",
]

# t2 variable -> (output variable, positive_only)
T2_METRICS = {
    "Shiller PE":     ("VAL_CAPE", True),
    "Best PBK":       ("VAL_PB", True),
    "Best Div Yield": ("VAL_DY_PCT", True),
    "Earnings Yield": ("VAL_EY_PCT", True),
    "Trailing PE":    ("VAL_TRAIL_PE", True),
    "Inflation":      ("_CPI_YOY_PCT", False),   # helper leg, not exported
}

PCTILE_WIN = 120   # months (~10y)
PCTILE_MIN = 36    # minimum history before a percentile is trusted
# 100 = rich for every metric: yields are cheap-when-high, so invert them
INVERT_FOR_RICHNESS = {"VAL_DY_PCT", "VAL_EY_PCT", "VAL_ERP_PCT"}


def log(msg: str) -> None:
    print(f"[valuation] {msg}", flush=True)


def log_panel_range(var: str, piv: pd.DataFrame) -> None:
    """Log a panel range without assuming the index is non-empty/datetime."""
    if piv.empty or len(piv.index) == 0:
        log(f"{var}: 0 countries, no observations")
        return
    idx = pd.to_datetime(piv.index, errors="coerce")
    idx = idx[~pd.isna(idx)]
    if len(idx) == 0:
        log(f"{var}: {piv.shape[1]} countries, date range unavailable")
        return
    log(f"{var}: {piv.shape[1]} countries, {idx.min().date()} -> {idx.max().date()}")


def month_end_panel(con, table: str, variable: str, qualified: bool) -> pd.DataFrame:
    """(month-end dates x countries) using each series' last real observation
    per month (carried-forward placeholder rows are compressed away first)."""
    qual = f"asado.{table}" if qualified else table
    df = con.execute(
        f"SELECT date, country, value FROM {qual} WHERE variable = ? AND value IS NOT NULL",
        [variable],
    ).fetchdf()
    if df.empty:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["country"].isin(T2_UNIVERSE)]
    piv = df.pivot_table(index="date", columns="country", values="value").sort_index()
    out = {}
    for c in piv.columns:
        s = piv[c].dropna()
        if s.empty:
            continue
        keep = s.ne(s.shift(1))
        keep.iloc[0] = True
        out[c] = s[keep].resample("ME").last()
    return pd.DataFrame(out)


def rolling_pctile(piv: pd.DataFrame) -> pd.DataFrame:
    """Each value's percentile (0-100) within its own trailing PCTILE_WIN months."""
    def pct(s: pd.Series) -> float:
        if pd.isna(s.iloc[-1]):        # no current reading -> no percentile
            return np.nan
        x = s.dropna()
        if len(x) < PCTILE_MIN:
            return np.nan
        return float((x <= x.iloc[-1]).mean() * 100.0)
    return piv.rolling(PCTILE_WIN, min_periods=PCTILE_MIN).apply(
        lambda w: pct(pd.Series(w)), raw=False)


def build() -> pd.DataFrame:
    con = loop_connection(read_only=True)
    try:
        panels: dict[str, pd.DataFrame] = {}
        for t2_var, (out_var, positive_only) in T2_METRICS.items():
            piv = month_end_panel(con, "t2_levels_daily", t2_var, qualified=True)
            if positive_only:
                piv = piv.where(piv > 0)
            panels[out_var] = piv
            log_panel_range(out_var, piv)
        y10 = month_end_panel(con, "sovereign_daily", "SOV_10Y_YIELD_PCT", qualified=False)
        log(f"10Y (sovereign_daily): {y10.shape[1]} countries")
    finally:
        con.close()

    # ERP = forward earnings yield - real 10Y (nominal - realized CPI YoY).
    # Legs publish on different calendars (CPI lands mid-next-month): align on
    # the union grid with a bounded 3-month forward-fill per leg — bounded so
    # a dead series cannot quietly keep producing ERP for months.
    ey, cpi = panels["VAL_EY_PCT"], panels.pop("_CPI_YOY_PCT")
    idx = ey.index.union(y10.index).union(cpi.index)
    cols = [c for c in T2_UNIVERSE if c in ey.columns and c in y10.columns and c in cpi.columns]
    ff = lambda piv: piv.reindex(idx)[cols].ffill(limit=3)
    erp = ff(ey) - (ff(y10) - ff(cpi))
    panels["VAL_ERP_PCT"] = erp
    log(f"VAL_ERP_PCT: {len(cols)} countries with all three legs "
        f"(missing: {sorted(set(T2_UNIVERSE) - set(cols))})")

    frames = []
    for var, piv in panels.items():
        long = piv.stack().rename("value").reset_index()
        long.columns = ["date", "country", "value"]
        long["variable"] = var
        frames.append(long)

        pc = rolling_pctile(piv if var not in INVERT_FOR_RICHNESS else -piv)
        lp = pc.stack().rename("value").reset_index()
        lp.columns = ["date", "country", "value"]
        lp["variable"] = f"{var}_PCTILE_10Y"
        frames.append(lp)

    out = pd.concat(frames, ignore_index=True)
    out["source"] = "valuation_block"
    out = out.sort_values(["variable", "country", "date"]).reset_index(drop=True)
    return out[["date", "country", "value", "variable", "source"]]


def save(out: pd.DataFrame) -> None:
    PANEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PANEL_PATH.with_suffix(".parquet.tmp")
    out.to_parquet(tmp, index=False)
    tmp.replace(PANEL_PATH)
    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS valuation_monthly")
        con.execute(
            f"""
            CREATE TABLE valuation_monthly AS
            SELECT CAST(date AS DATE) AS date, country, value, variable, source
            FROM read_parquet('{PANEL_PATH}')
            """
        )
        n, lo, hi = con.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM valuation_monthly").fetchone()
        if not n:
            raise RuntimeError("valuation_monthly rebuilt empty — refusing to continue")
        log(f"valuation_monthly: {n:,} rows, {lo} -> {hi}")
    finally:
        con.close()


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        snap = con.execute(
            """
            WITH latest AS (
              SELECT variable, MAX(date) AS d FROM valuation_monthly
              WHERE variable NOT LIKE '%_PCTILE_10Y' GROUP BY 1)
            SELECT v.variable, COUNT(*) AS n_countries, l.d AS asof
            FROM valuation_monthly v JOIN latest l
              ON v.variable = l.variable AND v.date = l.d
            GROUP BY 1, 3 ORDER BY 1
            """
        ).fetchall()
        print("latest month coverage:")
        ok = bool(snap)
        for var, nc, asof in snap:
            print(f"  {var:<16} {nc:>2} countries  asof {asof}")
            if nc < 25 and var != "VAL_ERP_PCT":
                ok = False
        rich = con.execute(
            """
            SELECT country, value FROM valuation_monthly
            WHERE variable = 'VAL_ERP_PCT_PCTILE_10Y'
              AND date = (SELECT MAX(date) FROM valuation_monthly
                          WHERE variable = 'VAL_ERP_PCT_PCTILE_10Y')
            ORDER BY value DESC LIMIT 5
            """
        ).fetchall()
        print("richest 5 by ERP percentile (100 = richest decade reading):")
        for c, v in rich:
            print(f"  {c:<14} {v:.0f}")
    finally:
        con.close()
    print("CHECK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the valuation block (PRD P7).")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        return check()
    out = build()
    save(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
