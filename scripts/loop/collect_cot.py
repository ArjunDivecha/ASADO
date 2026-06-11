#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/collect_cot.py
=============================================================================

INPUT FILES:
- (none on disk) Live HTTPS calls to the CFTC's public Socrata API
  (publicreporting.cftc.gov, dataset 6dca-aqww = "Legacy - Futures Only",
  weekly Commitments of Traders). Free, keyless, JSON.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/cot_weekly.parquet
    Tidy weekly panel (date, commodity, value, variable, source='cftc'):
      COT_NONCOMM_NET_CONTRACTS  speculator (non-commercial) net position
      COT_NONCOMM_NET_PCT_OI     net position as % of open interest
      COT_OPEN_INTEREST          total open interest, contracts
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `cot_weekly` (raw, idempotent rebuild from the parquet) and
    `cot_signals` (net %OI + 1y z-score per commodity, weekly).

VERSION: 1.0
LAST UPDATED: 2026-06-11
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 3)

DESCRIPTION:
PRD Priority 11 (positioning layer), COT leg: weekly speculator positioning
in the 12 commodity futures that drive the D1 terms-of-trade channel (energy,
metals, precious, agri). Speculator net length as % of open interest is the
classic crowding read: when specs are record-long copper and Chile hasn't
moved, the flow that COULD chase the ToT impulse is already positioned —
context the Layer 2 session should see next to D1 rows. A 10th grader's
version: every Friday the US regulator publishes who's betting how much on
each commodity; we keep the speculators' net bet and flag when it's extreme
vs its own last year.

This script does BOTH the pull and the DB load (single venv, no Bloomberg).

DEPENDENCIES:
- requests, pandas, duckdb (project venv)

USAGE:
  python scripts/loop/collect_cot.py              # incremental (last 120 days)
  python scripts/loop/collect_cot.py --backfill   # full history from 2006
  python scripts/loop/collect_cot.py --check      # verify tables

NOTES:
- Markets keyed by CFTC contract market code (stable across name changes);
  all 12 codes re-verified live 2026-06-11.
- Socrata is rate-limited without an app token but a dozen filtered queries
  per night is far below the limit.
- Per-market isolation: one failing market is logged loudly, others proceed.
=============================================================================
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.loop.loopdb import loop_connection  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PANEL_PATH = BASE_DIR / "Data" / "work" / "loop" / "cot_weekly.parquet"

API = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
BACKFILL_START = "2006-01-01"
INCREMENTAL_DAYS = 120

# CFTC legacy futures-only contract market codes (verified 2026-06-11).
MARKETS = {
    "067651": "WTI_CRUDE",
    "023651": "NATURAL_GAS",
    "088691": "GOLD",
    "084691": "SILVER",
    "085692": "COPPER",
    "076651": "PLATINUM",
    "002602": "CORN",
    "001602": "WHEAT_SRW",
    "005602": "SOYBEANS",
    "080732": "SUGAR_11",
    "083731": "COFFEE_C",
    "033661": "COTTON_2",
}

Z_WINDOW = 52
Z_MIN_OBS = 26


def log(msg: str) -> None:
    print(f"[cot] {msg}", flush=True)


def fetch_market(code: str, start: str) -> pd.DataFrame:
    params = {
        "$select": ("report_date_as_yyyy_mm_dd,noncomm_positions_long_all,"
                    "noncomm_positions_short_all,open_interest_all"),
        "$where": f"cftc_contract_market_code='{code}' AND report_date_as_yyyy_mm_dd>'{start}'",
        "$order": "report_date_as_yyyy_mm_dd",
        "$limit": 5000,
    }
    resp = requests.get(API, params=params, timeout=60)
    resp.raise_for_status()
    df = pd.DataFrame(resp.json())
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["report_date_as_yyyy_mm_dd"])
    for c in ("noncomm_positions_long_all", "noncomm_positions_short_all", "open_interest_all"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def collect(start: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    n_ok = 0
    for code, name in MARKETS.items():
        try:
            df = fetch_market(code, start)
        except Exception as e:
            log(f"  MARKET FAILED {name} ({code}): {e}")
            continue
        if df.empty:
            log(f"  WARNING {name}: no rows since {start}")
            continue
        net = df["noncomm_positions_long_all"] - df["noncomm_positions_short_all"]
        oi = df["open_interest_all"].replace(0.0, np.nan)
        for var, series in [("COT_NONCOMM_NET_CONTRACTS", net),
                            ("COT_NONCOMM_NET_PCT_OI", (net / oi) * 100.0),
                            ("COT_OPEN_INTEREST", df["open_interest_all"])]:
            frames.append(pd.DataFrame({
                "date": df["date"], "commodity": name,
                "value": series.values, "variable": var,
            }))
        n_ok += 1
    if not frames:
        raise RuntimeError("no COT data collected at all")
    out = pd.concat(frames, ignore_index=True).dropna(subset=["value"])
    out["source"] = "cftc"
    log(f"collected: {n_ok}/{len(MARKETS)} markets, {len(out):,} rows")
    return out[["date", "commodity", "value", "variable", "source"]]


def merge_and_save(new: pd.DataFrame) -> None:
    panel = pd.read_parquet(PANEL_PATH) if PANEL_PATH.exists() else pd.DataFrame(
        columns=["date", "commodity", "value", "variable", "source"])
    merged = pd.concat([panel, new], ignore_index=True)
    merged["date"] = pd.to_datetime(merged["date"])
    merged = merged.drop_duplicates(subset=["date", "commodity", "variable"], keep="last")
    merged = merged.sort_values(["commodity", "variable", "date"]).reset_index(drop=True)
    PANEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PANEL_PATH.with_suffix(".parquet.tmp")
    merged.to_parquet(tmp, index=False)
    tmp.replace(PANEL_PATH)
    log(f"panel: {len(merged):,} rows, {merged['date'].min().date()} -> {merged['date'].max().date()}")


def load_db() -> None:
    raw = pd.read_parquet(PANEL_PATH)
    raw["date"] = pd.to_datetime(raw["date"])
    pct = raw[raw["variable"] == "COT_NONCOMM_NET_PCT_OI"]
    frames = []
    for commodity, grp in pct.groupby("commodity"):
        s = grp.set_index("date")["value"].sort_index()
        mu = s.rolling(Z_WINDOW, min_periods=Z_MIN_OBS).mean()
        sd = s.rolling(Z_WINDOW, min_periods=Z_MIN_OBS).std()
        z = ((s - mu) / sd.replace(0.0, np.nan)).dropna()
        frames.append(pd.DataFrame({
            "date": z.index, "commodity": commodity, "net_pct_oi": s.reindex(z.index).values,
            "net_pct_oi_z52w": z.values,
        }))
    if not frames:
        raise RuntimeError("no COT signals derived — refusing to continue")
    signals = pd.concat(frames, ignore_index=True)

    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS cot_weekly")
        con.execute(f"""
            CREATE TABLE cot_weekly AS
            SELECT CAST(date AS DATE) AS date, commodity, value, variable, source
            FROM read_parquet('{PANEL_PATH}')
        """)
        con.execute("DROP TABLE IF EXISTS cot_signals")
        con.register("sig_df", signals)
        con.execute("""
            CREATE TABLE cot_signals AS
            SELECT CAST(date AS DATE) AS date, commodity, net_pct_oi, net_pct_oi_z52w
            FROM sig_df
        """)
        for tbl in ("cot_weekly", "cot_signals"):
            n, lo, hi, nc = con.execute(
                f"SELECT COUNT(*), MIN(date), MAX(date), COUNT(DISTINCT commodity) FROM {tbl}").fetchone()
            if not n:
                raise RuntimeError(f"{tbl} rebuilt empty — refusing to continue")
            log(f"{tbl}: {n:,} rows, {nc} commodities, {lo} -> {hi}")
    finally:
        con.close()


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        rows = con.execute("""
            SELECT commodity, MAX(date) AS last, COUNT(*) AS n FROM cot_signals
            GROUP BY 1 ORDER BY 1
        """).fetchall()
    finally:
        con.close()
    ok = len(rows) >= 10
    for c, last, n in rows:
        print(f"{c}: {n} weeks, last {last}")
    print("CHECK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="CFTC COT speculator positioning (loop, PRD P11).")
    parser.add_argument("--backfill", action="store_true", help=f"full history from {BACKFILL_START}")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        return check()

    start = BACKFILL_START if args.backfill else (
        date.today() - timedelta(days=INCREMENTAL_DAYS)).isoformat()
    log(f"pulling COT since {start}")
    try:
        new = collect(start)
    except Exception as e:
        log(f"COT PULL FAILED: {e} — existing parquet untouched")
        return 1
    merge_and_save(new)
    load_db()
    return 0


if __name__ == "__main__":
    sys.exit(main())
