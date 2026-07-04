"""
=============================================================================
SCRIPT NAME: snapshot_for_experiment.py
=============================================================================

Freezes tables from the live ASADO databases into a parquet snapshot so
experiments never hold connections to the production DBs (DuckDB is
one-writer OR many-readers — even an idle read-only connection blocks the
nightly pipeline; see the 2026-07-03 lock-guard incident). Opens the source
DB read-only, exports the requested tables, closes within seconds, and
writes a manifest recording exactly what was frozen and when.

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb        (--db main, read-only)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb (--db loop, read-only)

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/<name>/snapshot_<YYYY_MM_DD>/<table>.parquet
  (one parquet per exported table)
- .../snapshot_<YYYY_MM_DD>/MANIFEST.json (source DB, tables, row counts, timestamp)

VERSION: 1.0
LAST UPDATED: 2026-07-04
AUTHOR: Fable (Claude) for Arjun Divecha

DESCRIPTION:
Experiment sandboxing helper (rule 2 in experiments/README.md). Copies data
OUT of the live warehouse so experiment code runs against frozen, reproducible
inputs and the nightly jobs never contend with an experiment for the DB lock.

DEPENDENCIES: duckdb (uses the ASADO venv)

USAGE:
  venv/bin/python scripts/snapshot_for_experiment.py \
      --db loop --tables combiner_scores_daily,dislocation_daily --name my_exp
  venv/bin/python scripts/snapshot_for_experiment.py --db loop --list   # show tables

NOTES:
- SQL views can be exported too (they materialize into parquet).
- Re-running on the same day overwrites that day's snapshot (idempotent).
- This script never writes to any database; the connection is read-only and
  closed in a finally block.
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import duckdb

BASE_DIR = Path(__file__).resolve().parent.parent
DBS = {
    "main": BASE_DIR / "Data" / "asado.duckdb",
    "loop": BASE_DIR / "Data" / "loop" / "asado_loop.duckdb",
}
SCRATCH = BASE_DIR / "Data" / "work" / "experiments"
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def main() -> int:
    ap = argparse.ArgumentParser(description="Freeze live-DB tables to parquet for an experiment")
    ap.add_argument("--db", choices=["main", "loop"], required=True)
    ap.add_argument("--tables", help="comma-separated table/view names")
    ap.add_argument("--name", help="experiment name (dest: Data/work/experiments/<name>/)")
    ap.add_argument("--list", action="store_true", help="list available tables and exit")
    args = ap.parse_args()

    con = duckdb.connect(str(DBS[args.db]), read_only=True)
    try:
        if args.list:
            rows = con.execute(
                "SELECT table_name, table_type FROM information_schema.tables "
                "WHERE table_schema='main' ORDER BY 1").fetchall()
            for name, typ in rows:
                print(f"{name}  ({typ})")
            return 0

        if not args.tables or not args.name:
            ap.error("--tables and --name are required unless --list")
        tables = [t.strip() for t in args.tables.split(",") if t.strip()]
        bad = [t for t in tables if not IDENT.match(t)]
        if bad:
            raise SystemExit(f"Invalid table names: {bad}")

        dest = SCRATCH / args.name / f"snapshot_{datetime.now():%Y_%m_%d}"
        dest.mkdir(parents=True, exist_ok=True)
        manifest = {"source_db": str(DBS[args.db]), "frozen_at": datetime.now().isoformat(),
                    "tables": {}}
        for t in tables:
            out = dest / f"{t}.parquet"
            con.execute(f"COPY (SELECT * FROM {t}) TO '{out}' (FORMAT PARQUET)")
            n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            manifest["tables"][t] = {"rows": int(n), "file": str(out)}
            print(f"froze {t}: {n:,} rows -> {out}")
        (dest / "MANIFEST.json").write_text(json.dumps(manifest, indent=2))
        print(f"\nSnapshot complete: {dest}")
        print(f"Manifest: {dest / 'MANIFEST.json'}")
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())
