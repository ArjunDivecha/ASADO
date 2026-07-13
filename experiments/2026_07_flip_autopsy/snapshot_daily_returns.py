"""
=============================================================================
SCRIPT NAME: snapshot_daily_returns.py
=============================================================================

WHAT THIS PROGRAM DOES:
One-shot snapshot of the daily country return series needed by the G1 flip
autopsy. It opens the MAIN ASADO warehouse read-only for a few seconds
(open -> one SELECT -> close; never holds a connection, per repo lock rules),
pulls only the `1DRet` rows of `t2_factors_daily` for the 34-country T2
universe, and freezes them to parquet in the experiment's gitignored scratch
snapshot directory. All downstream autopsy analysis reads the parquet, never
the live DB. The raw rows are kept EXACTLY as stored (forward-labeled,
calendar-day grid with 0.0 non-trading placeholders); the backward-shift +
placeholder-drop convention of scripts/loop/loopdb.py::daily_country_returns
is applied later, in the analysis script, so both raw and adjusted views are
reproducible from this one frozen file.

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
  (read-only, seconds-long open: table t2_factors_daily, variable='1DRet')

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13/t2_1dret_daily.parquet
  (tidy: date, country, value=1DRet as stored)

VERSION: 1.0  |  LAST UPDATED: 2026-07-13  |  AUTHOR: Claude (G1 flip autopsy)
DEPENDENCIES: duckdb, pandas (production venv)
USAGE: venv/bin/python experiments/2026_07_flip_autopsy/snapshot_daily_returns.py
NOTES: Idempotent — re-running overwrites the same parquet.
=============================================================================
"""
import duckdb
import pandas as pd
from pathlib import Path

DB = "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb"
OUT_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13")
OUT = OUT_DIR / "t2_1dret_daily.parquet"

OUT_DIR.mkdir(parents=True, exist_ok=True)
con = duckdb.connect(DB, read_only=True)
try:
    df = con.execute(
        "SELECT date, country, value FROM t2_factors_daily WHERE variable = '1DRet'"
    ).fetch_df()
finally:
    con.close()

df.to_parquet(OUT, index=False)
print(f"froze {len(df):,} rows ({df['country'].nunique()} countries, "
      f"{df['date'].min()} -> {df['date'].max()}) -> {OUT}")
