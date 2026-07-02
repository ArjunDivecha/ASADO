#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: check_loop_schema.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/loop_schema_contract.yaml
    The consumer-column contract: per loop-DB table, the columns downstream
    consumers actually read, plus an optional flag for BBG-fed tables.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    The loop database (opened READ-ONLY).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/governance/loop_schema_status.json
    Machine-readable check result (per-table status + overall verdict),
    written atomically every run.

VERSION: 1.0
LAST UPDATED: 2026-07-01
AUTHOR: Arjun Divecha (agent session, data-structures audit R5 2026-07-01)

DESCRIPTION:
Loop-DB tables are DROP+CREATE per loader with no schema versioning, so a
loader edit can silently rename or drop a column that consumers
(build_dislocations, build_cockpit_data, the harness, event studies) rely on.
This nightly QA step asserts that every table declared in
config/loop_schema_contract.yaml exists and contains AT LEAST the declared
columns (additive columns are always fine). Intentional schema changes are
made visible by updating the contract in the same commit as the loader edit.

EXIT CODES (loop_daily_job.py semantics):
  0 = all declared tables/columns present
  2 = PARTIAL: only optional tables missing (BBG-down night / fresh machine)
  1 = FAIL: a required table is missing, or a declared column is missing on
      any present table (real consumer-contract drift)

DEPENDENCIES:
- duckdb, pyyaml (project venv)

USAGE:
  ./venv/bin/python scripts/qa/check_loop_schema.py
  ./venv/bin/python scripts/qa/check_loop_schema.py --contract path/to/alt.yaml
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import duckdb
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONTRACT_PATH = BASE_DIR / "config" / "loop_schema_contract.yaml"
LOOP_DB = BASE_DIR / "Data" / "loop" / "asado_loop.duckdb"
STATUS_PATH = BASE_DIR / "Data" / "loop" / "governance" / "loop_schema_status.json"


def atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str))
    os.replace(tmp, path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Loop-DB consumer-column QA check (audit R5)")
    parser.add_argument("--contract", default=str(CONTRACT_PATH), help="Schema contract YAML")
    parser.add_argument("--db", default=str(LOOP_DB), help="Loop DuckDB path")
    args = parser.parse_args()

    contract_path = Path(args.contract)
    db_path = Path(args.db)
    if not contract_path.exists():
        print(f"[FAIL] contract not found: {contract_path}")
        return 1
    if not db_path.exists():
        print(f"[FAIL] loop DB not found: {db_path}")
        return 1

    contract = yaml.safe_load(contract_path.read_text())
    declared: dict = contract.get("tables") or {}
    if not declared:
        print("[FAIL] contract declares no tables")
        return 1

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        actual_tables = {
            row[0]: None
            for row in con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
            ).fetchall()
        }
        results = []
        missing_required, missing_optional, column_drift = [], [], []
        for table, spec in sorted(declared.items()):
            if table.startswith("_"):
                continue  # yaml anchors helper keys
            optional = bool(spec.get("optional", False))
            want = list(spec.get("columns") or [])
            if table not in actual_tables:
                (missing_optional if optional else missing_required).append(table)
                results.append({"table": table, "status": "missing",
                                "optional": optional, "missing_columns": want})
                continue
            have = {row[1] for row in con.execute(f"PRAGMA table_info('{table}')").fetchall()}
            missing_cols = [c for c in want if c not in have]
            if missing_cols:
                column_drift.append((table, missing_cols))
                results.append({"table": table, "status": "column_drift",
                                "optional": optional, "missing_columns": missing_cols})
            else:
                results.append({"table": table, "status": "ok",
                                "optional": optional, "missing_columns": []})
    finally:
        con.close()

    if column_drift or missing_required:
        overall, rc = "FAIL", 1
    elif missing_optional:
        overall, rc = "PARTIAL", 2
    else:
        overall, rc = "OK", 0

    atomic_write_json(STATUS_PATH, {
        "checked_ts": datetime.now().isoformat(timespec="seconds"),
        "contract": str(contract_path),
        "contract_version": contract.get("contract_version"),
        "db": str(db_path),
        "overall": overall,
        "missing_required_tables": missing_required,
        "missing_optional_tables": missing_optional,
        "column_drift": [{"table": t, "missing_columns": c} for t, c in column_drift],
        "tables": results,
    })

    n_ok = sum(1 for r in results if r["status"] == "ok")
    print(f"[{overall}] loop schema check: {n_ok}/{len(results)} tables ok")
    for t in missing_required:
        print(f"  [FAIL] required table missing: {t}")
    for t in missing_optional:
        print(f"  [PARTIAL] optional table missing (BBG-down night / fresh machine): {t}")
    for t, cols in column_drift:
        print(f"  [FAIL] column drift in {t}: consumers expect {cols}")
    if rc == 1:
        print("  -> a loader changed a schema consumers rely on. Either restore the "
              "column(s) or update config/loop_schema_contract.yaml in the same commit.")
    print(f"  status: {STATUS_PATH}")
    return rc


if __name__ == "__main__":
    sys.exit(main())
