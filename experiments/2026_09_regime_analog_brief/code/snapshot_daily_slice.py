"""
=============================================================================
SCRIPT NAME: snapshot_daily_slice.py
=============================================================================
Freezes a FILTERED slice of the big daily ASADO tables to parquet so the
regime-analog brief runs against frozen inputs and never holds a connection to
the production warehouse (DuckDB is one-writer/many-readers).

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb  (read-only, opened and closed in seconds)

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_09_regime_analog_brief/snapshot_2026_09_02/t2_levels_daily_slice.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_09_regime_analog_brief/snapshot_2026_09_02/factor_returns_daily.parquet

VERSION: 1.0
LAST UPDATED: 2026-09-02
AUTHOR: Claude (for Arjun Divecha)
DEPENDENCIES: duckdb (ASADO venv)
USAGE: venv/bin/python experiments/2026_09_regime_analog_brief/code/snapshot_daily_slice.py
NOTES: t2_levels_daily is 15.2M rows; only the ~10 variables the brief needs
       are exported. Connection is read-only and closed in a finally block.
=============================================================================
"""
from pathlib import Path
import duckdb

DB = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb")
DEST = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_09_regime_analog_brief/snapshot_2026_09_02")
KEEP = ("Tot Return Index", "PX_LAST", "10Yr Bond", "Oil", "Gold", "Copper",
        "Currency", "20 Day Vol", "360 Day Vol", "Advance Decline", "Mcap Weights",
        "Best PE", "Earnings Yield", "Trailing PE")

DEST.mkdir(parents=True, exist_ok=True)
con = duckdb.connect(str(DB), read_only=True)
try:
    vlist = ",".join("'" + v.replace("'", "''") + "'" for v in KEEP)
    out = DEST / "t2_levels_daily_slice.parquet"
    con.execute(f"COPY (SELECT * FROM t2_levels_daily WHERE variable IN ({vlist})) TO '{out}' (FORMAT PARQUET)")
    print("froze t2_levels_daily slice ->", out)
    out2 = DEST / "factor_returns_daily.parquet"
    con.execute(f"COPY (SELECT * FROM factor_returns_daily) TO '{out2}' (FORMAT PARQUET)")
    print("froze factor_returns_daily ->", out2)
finally:
    con.close()
