#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/load_etf_flows.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/etf_flows.parquet
    Tidy panel from scripts/loop/collect_etf_flows_bbg.py:
    ETF_SHARES_OUT_MN / ETF_NAV_USD / ETF_AUM_USD_MN, 34 country ETFs, 2010+.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `etf_flows`       — raw tidy panel (idempotent rebuild from parquet).
    Table `etf_flow_signals` — derived daily positioning signals per country:
        ETF_FLOW_USD_MN      dShares x NAV (creations/redemptions, USD mn)
        ETF_FLOW_21D_USD_MN  21-day rolling net flow, USD mn
        ETF_FLOW_21D_PCT_AUM 21-day net flow as % of current AUM
        ETF_FLOW_21D_Z       21d flow z-scored vs its own trailing 252d
        ETF_SHORT_PCT_SHOUT  short interest as % of shares out (semi-monthly)
        ETF_SHORT_PCT_Z      SI%% z-scored vs own trailing ~2y (48 obs)
    Lives in the LOOP DB because setup_duckdb.py deletes the main warehouse
    monthly.

VERSION: 1.0
LAST UPDATED: 2026-06-11
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 3)

DESCRIPTION:
Loads the ETF share-count parquet into the loop DuckDB and derives the
positioning signals (PRD Priority 11). Daily share-count changes in US-listed
country ETFs are same-day evidence of US/foreign investor positioning per
country — the flow tape that B3/KRX-style exchange data would give, but
uniform across all 34 countries. Split from the collector because the
OpusBloomberg conda env has no duckdb (same split as load_sovereign_daily.py).

Share-split guard: dShares of >20% of shares outstanding in one day is
treated as a corporate action (split/reverse split), and the flow for that
day is set to NULL rather than a fake multi-billion-dollar flow.

DEPENDENCIES:
- duckdb, pandas, numpy (project venv)

USAGE:
  python scripts/loop/load_etf_flows.py            # rebuild both tables
  python scripts/loop/load_etf_flows.py --check    # verify only

NOTES:
- Fails loudly if the parquet is missing or empty (FAIL-IS-FAIL).
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
PANEL_PATH = BASE_DIR / "Data" / "work" / "loop" / "etf_flows.parquet"

SPLIT_GUARD = 0.20      # |dShares|/shares > 20% in one day -> corporate action
Z_WINDOW = 252
Z_MIN_OBS = 120


def derive_signals(raw: pd.DataFrame) -> pd.DataFrame:
    """Per-country daily flow signals from shares-out and NAV."""
    frames: list[pd.DataFrame] = []
    for country, grp in raw.groupby("country"):
        piv = grp.pivot_table(index="date", columns="variable", values="value", aggfunc="last").sort_index()
        if "ETF_SHARES_OUT_MN" not in piv.columns or "ETF_NAV_USD" not in piv.columns:
            print(f"  WARNING {country}: missing shares or NAV — no signals derived")
            continue
        sh, nav = piv["ETF_SHARES_OUT_MN"], piv["ETF_NAV_USD"]
        dsh = sh.diff()
        split = (dsh.abs() / sh.shift(1)) > SPLIT_GUARD
        if split.any():
            print(f"  {country}: {int(split.sum())} split-like days nulled "
                  f"({', '.join(str(d.date()) for d in split[split].index[:4])}...)")
        flow = (dsh * nav).where(~split)              # USD mn (shares in mn x USD)
        flow21 = flow.rolling(21, min_periods=15).sum()
        aum = piv.get("ETF_AUM_USD_MN", sh * nav)
        pct_aum = (flow21 / aum) * 100.0
        mu = flow21.rolling(Z_WINDOW, min_periods=Z_MIN_OBS).mean()
        sd = flow21.rolling(Z_WINDOW, min_periods=Z_MIN_OBS).std()
        z = (flow21 - mu) / sd.replace(0.0, np.nan)
        etf = grp["etf"].iloc[0]
        # Short interest (semi-monthly): % of shares outstanding + z vs ~2y
        si_pct = si_z = pd.Series(dtype=float)
        if "ETF_SHORT_INT_SH" in piv.columns:
            si = piv["ETF_SHORT_INT_SH"].dropna()
            if not si.empty:
                sh_at_si = sh.ffill().reindex(si.index)
                si_pct = (si / (sh_at_si * 1e6)) * 100.0
                mu_si = si_pct.rolling(48, min_periods=24).mean()
                sd_si = si_pct.rolling(48, min_periods=24).std()
                si_z = (si_pct - mu_si) / sd_si.replace(0.0, np.nan)
        for var, series in [("ETF_FLOW_USD_MN", flow), ("ETF_FLOW_21D_USD_MN", flow21),
                            ("ETF_FLOW_21D_PCT_AUM", pct_aum), ("ETF_FLOW_21D_Z", z),
                            ("ETF_SHORT_PCT_SHOUT", si_pct), ("ETF_SHORT_PCT_Z", si_z)]:
            s = series.dropna()
            if s.empty:
                continue
            frames.append(pd.DataFrame({
                "date": s.index, "country": country, "etf": etf,
                "value": s.values, "variable": var, "source": "bloomberg_derived",
            }))
    if not frames:
        raise RuntimeError("no ETF flow signals derived — refusing to continue")
    return pd.concat(frames, ignore_index=True)


def rebuild() -> None:
    if not PANEL_PATH.exists():
        raise FileNotFoundError(f"missing {PANEL_PATH} — run collect_etf_flows_bbg.py first")
    raw = pd.read_parquet(PANEL_PATH)
    if raw.empty:
        raise RuntimeError(f"{PANEL_PATH} is empty — refusing to continue")
    raw["date"] = pd.to_datetime(raw["date"])
    signals = derive_signals(raw)

    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS etf_flows")
        con.execute(f"""
            CREATE TABLE etf_flows AS
            SELECT CAST(date AS DATE) AS date, country, etf, value, variable, source
            FROM read_parquet('{PANEL_PATH}')
        """)
        con.execute("DROP TABLE IF EXISTS etf_flow_signals")
        con.register("signals_df", signals)
        con.execute("""
            CREATE TABLE etf_flow_signals AS
            SELECT CAST(date AS DATE) AS date, country, etf, value, variable, source
            FROM signals_df
        """)
        for tbl in ("etf_flows", "etf_flow_signals"):
            n, lo, hi, nc = con.execute(
                f"SELECT COUNT(*), MIN(date), MAX(date), COUNT(DISTINCT country) FROM {tbl}").fetchone()
            if not n:
                raise RuntimeError(f"{tbl} rebuilt empty — refusing to continue")
            print(f"{tbl}: {n:,} rows, {nc} countries, {lo} -> {hi}")
    finally:
        con.close()


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        rows = con.execute("""
            SELECT variable, COUNT(DISTINCT country) AS nc, MAX(date) AS last
            FROM etf_flow_signals GROUP BY 1 ORDER BY 1
        """).fetchall()
    finally:
        con.close()
    ok = bool(rows)
    for var, nc, last in rows:
        print(f"{var}: {nc} countries, last {last}")
        # SI coverage may legitimately be thinner than the flow layer
        if nc < 30 and not var.startswith("ETF_SHORT"):
            ok = False
    print("CHECK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Load ETF flows parquet + derive positioning signals.")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        return check()
    rebuild()
    return 0


if __name__ == "__main__":
    sys.exit(main())
