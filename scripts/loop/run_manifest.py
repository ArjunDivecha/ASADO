#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: run_manifest.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/governance_contract.yaml
  The single source of truth: every nightly step + its expected output(s).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
  Read-ONLY: checked for loop_db_table existence/non-emptiness only.
- (runtime) the per-step status records passed in from loop_daily_job.py
  [{name, rc, started_ts, ended_ts}, ...].

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/governance/run_manifest.json
  Per-step {status ok|fail|stale|partial|skipped, started_ts, ended_ts,
  expected_outputs[], output_checks[]} + the contract content-hash. This file
  is GIT-IGNORED (Data/loop/ is ignored) — it is an ephemeral runtime artifact,
  not a trust root. It NEVER writes to Data/asado.duckdb.

VERSION: 1.0
LAST UPDATED: 2026-06-17
AUTHOR: Arjun Divecha (built by agent session, Governance Layer PRD v1.2, item A1)

DESCRIPTION:
A1 — the run manifest. Turns the governance contract + the loop's per-step
return codes/timestamps into one machine-readable record of what actually ran
and whether each step produced fresh output. The point is to catch the
"stale-but-green" failure: a step that exits 0 while yesterday's artifact
lingers (or the brief is missing) is classified fail/stale here, so A2's
heartbeat can push and A8's scorecard can red — exactly the drift that let the
06-12 -> 06-16 brief gap hide in a clean log.

Design split (deliberate): this WRITER is fail-soft — a bug here must never
change the nightly job's exit code (it is observability). A2/A8 are the
fail-loud READERS that turn the manifest's contents into a hard gate.

STALENESS: file outputs with staleness=mtime must be rewritten this run
(mtime advanced past the step's started_ts); staleness=existence files and all
loop_db_table outputs are checked for existence/non-emptiness only (the shared
loop DB file's mtime advances on every write, so it cannot tell which step
refreshed — see config/governance_contract.yaml header).

DEPENDENCIES:
- pyyaml, duckdb (project venv)

USAGE:
  # imported by loop_daily_job.py:
  from scripts.loop import run_manifest
  run_manifest.write_manifest(records)        # records = [{name, rc, started_ts, ended_ts}]

  # standalone:
  python scripts/loop/run_manifest.py --check                 # print latest manifest + non-ok
  python scripts/loop/run_manifest.py --from-status recs.json # replay records from a file
=============================================================================
"""

from __future__ import annotations

import argparse
import glob as globmod
import hashlib
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.loop.loopdb import BASE_DIR, LOOP_DB, LOOP_DIR  # noqa: E402

CONTRACT_PATH = BASE_DIR / "config" / "governance_contract.yaml"
GOV_DIR = LOOP_DIR / "governance"
MANIFEST_PATH = GOV_DIR / "run_manifest.json"
PRODUCER_VERSION = "run_manifest.py 1.0"

_DATE_TOKEN = re.compile(r"\{date:([^}]+)\}")


def load_contract(path: Path = CONTRACT_PATH) -> tuple[dict[str, Any], str]:
    """Return (contract dict, sha256 hex of the raw bytes)."""
    raw = path.read_bytes()
    contract = yaml.safe_load(raw)
    contract_hash = hashlib.sha256(raw).hexdigest()
    return contract, contract_hash


def resolve_template(template: str, run_date: date) -> str:
    """Substitute {date:%Y_%m_%d}-style tokens with run_date.strftime(...)."""
    return _DATE_TOKEN.sub(lambda m: run_date.strftime(m.group(1)), template)


def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _file_result(rel: str, kind: str, full: Path, staleness: str,
                 started: Optional[datetime]) -> dict[str, Any]:
    if not full.exists() or full.stat().st_size == 0:
        return {"output": rel, "kind": kind, "result": "missing", "mtime": None}
    mtime = datetime.fromtimestamp(full.stat().st_mtime)
    if staleness == "mtime" and started is not None and mtime < started:
        return {"output": rel, "kind": kind, "result": "stale", "mtime": mtime.isoformat(timespec="seconds")}
    return {"output": rel, "kind": kind, "result": "ok", "mtime": mtime.isoformat(timespec="seconds")}


def _check_file(out: dict[str, Any], run_date: date,
                started: Optional[datetime]) -> dict[str, Any]:
    """Check a file output. Two forms:

    - path_template: an exact path (date tokens = run_date). Use when the output
      filename is wall-clock dated (e.g. the monthly calibration report).
    - glob: a glob pattern; the NEWEST matching file is checked. Use when the
      filename is DATA-AS-OF dated and lags wall-clock (the daily brief is
      brief_<latest-return-date>.md, not brief_<today>.md, so requiring today's
      date would false-fail a successful run). 'Did the newest brief get
      rewritten this run?' is the honest staleness question.
    """
    staleness = out.get("staleness", "existence")
    if "glob" in out:
        pattern = resolve_template(out["glob"], run_date)
        abspat = pattern if os.path.isabs(pattern) else str(BASE_DIR / pattern)
        matches = [Path(p) for p in globmod.glob(abspat)
                   if os.path.isfile(p) and os.path.getsize(p) > 0]
        if not matches:
            return {"output": pattern, "kind": "file_glob", "result": "missing", "mtime": None}
        newest = max(matches, key=lambda p: p.stat().st_mtime)
        try:
            rel = str(newest.relative_to(BASE_DIR))
        except ValueError:
            rel = str(newest)
        return _file_result(rel, "file_glob", newest, staleness, started)
    rel = resolve_template(out["path_template"], run_date)
    return _file_result(rel, "file", BASE_DIR / rel, staleness, started)


def _check_table(table: str, table_count: Optional[Callable[[str], Optional[int]]]) -> dict[str, Any]:
    if table_count is None:
        return {"output": f"loop_db:{table}", "kind": "loop_db_table", "result": "unknown", "rows": None}
    try:
        n = table_count(table)
    except Exception:  # noqa: BLE001 — a missing table / DB error = the table is not there
        n = None
    if n is None or n <= 0:
        return {"output": f"loop_db:{table}", "kind": "loop_db_table", "result": "missing", "rows": n}
    return {"output": f"loop_db:{table}", "kind": "loop_db_table", "result": "ok", "rows": int(n)}


def classify_step(step: dict[str, Any], rec: Optional[dict[str, Any]], run_date: date,
                  table_count: Optional[Callable[[str], Optional[int]]]) -> dict[str, Any]:
    """Classify one contract step. Status precedence: fail > stale > partial > ok.

    A missing/empty expected output AFTER a clean (rc==0) exit is the
    stale-but-green catch: it classifies fail, not ok.
    """
    name = step["name"]
    if rec is None:
        # Step not executed this run (e.g. --only subset). Not a failure.
        return {"step": name, "status": "skipped", "started_ts": None, "ended_ts": None,
                "governance": bool(step.get("governance")), "optional": bool(step.get("optional")),
                "output_checks": []}

    rc = rec.get("rc")
    started = _parse_ts(rec.get("started_ts"))
    base = {"step": name, "started_ts": rec.get("started_ts"), "ended_ts": rec.get("ended_ts"),
            "rc": rc, "governance": bool(step.get("governance")), "optional": bool(step.get("optional"))}

    # rc-driven terminal states first.
    if rc == 127 or (rc not in (0, 2)):
        return {**base, "status": "fail", "output_checks": []}
    if rc == 2:
        return {**base, "status": "partial", "output_checks": []}

    # rc == 0: verify the step actually produced its declared outputs.
    checks: list[dict[str, Any]] = []
    for out in step.get("expected_outputs", []) or []:
        if out.get("kind") == "file":
            checks.append(_check_file(out, run_date, started))
        elif out.get("kind") == "loop_db_table":
            checks.append(_check_table(out["table"], table_count))

    results = {c["result"] for c in checks}
    soft = bool(step.get("optional"))
    if "missing" in results:
        # H4 (red-team 2026-06-26): honor `optional`. An OPTIONAL step that exits 0
        # but produced no declared output is a legitimate soft skip — e.g. the nightly
        # discovery docket no-ops when ASADO_RUN_DISCOVERY_LAB is unset, leaving only a
        # 0-byte .gitkeep, and build_cockpit_data runs only when the docket does. It must
        # NOT red governance (REQ-NIGHT-002). A REQUIRED step missing its output stays the
        # stale-but-green fail. The `optional` flag was recorded but never consulted before.
        status = "optional_missing" if soft else "fail"
    elif "stale" in results:
        status = "optional_stale" if soft else "stale"
    else:
        status = "ok"        # 'unknown' table checks (DB unavailable) do not fail
    return {**base, "status": status, "output_checks": checks}


def _loop_table_counter() -> Optional[Callable[[str], Optional[int]]]:
    """Return a read-only row-counter over the loop DB, or None if unavailable."""
    if not LOOP_DB.exists():
        return None
    try:
        from scripts.duckdb_lock_guard import guarded_connect
        # Short wait budget keeps this diagnostic snappy (it degrades to
        # "no table checks" on failure) while still clearing killable
        # ~/.claude-science lock squatters via the shared guard.
        con = guarded_connect(LOOP_DB, read_only=True, wait_budget_s=20)
        known = {r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'").fetchall()}
    except Exception:  # noqa: BLE001 — DB locked/absent: degrade to no table checks
        return None

    def counter(table: str) -> Optional[int]:
        if table not in known:
            return None
        return con.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]

    return counter


def build_manifest(records: list[dict[str, Any]], run_date: Optional[date] = None,
                   contract_path: Path = CONTRACT_PATH,
                   table_count: Optional[Callable[[str], Optional[int]]] = "__auto__") -> dict[str, Any]:
    """Pure builder (no file write) — used directly by tests."""
    run_date = run_date or date.today()
    contract, contract_hash = load_contract(contract_path)
    if table_count == "__auto__":
        table_count = _loop_table_counter()
    by_name = {r["name"]: r for r in records}
    steps_out = [classify_step(step, by_name.get(step["name"]), run_date, table_count)
                 for step in contract.get("steps", [])]
    fail = [s["step"] for s in steps_out if s["status"] == "fail"]
    stale = [s["step"] for s in steps_out if s["status"] == "stale"]
    # A step the loop ran but the contract does not know about (drift the other way).
    contract_names = {step["name"] for step in contract.get("steps", [])}
    unknown_steps = [r["name"] for r in records if r["name"] not in contract_names]
    return {
        "schema_version": int(contract.get("schema_version", 1)),
        "producer_version": PRODUCER_VERSION,
        "as_of": datetime.now().isoformat(timespec="seconds"),
        "run_date": run_date.isoformat(),
        "contract_version": str(contract.get("contract_version", "")),
        "contract_hash": f"sha256:{contract_hash}",
        "overall_ok": (not fail and not stale and not unknown_steps),
        "fail_steps": fail,
        "stale_steps": stale,
        "unknown_steps": unknown_steps,
        "steps": steps_out,
    }


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2))
    os.replace(tmp, path)


def write_manifest(records: list[dict[str, Any]], run_date: Optional[date] = None,
                   out_path: Path = MANIFEST_PATH, contract_path: Path = CONTRACT_PATH,
                   table_count: Optional[Callable[[str], Optional[int]]] = "__auto__") -> dict[str, Any]:
    """Build + write the manifest. Importable entrypoint for loop_daily_job.py."""
    manifest = build_manifest(records, run_date=run_date, contract_path=contract_path,
                              table_count=table_count)
    _atomic_write_json(out_path, manifest)
    return manifest


def _print_check(path: Path = MANIFEST_PATH) -> int:
    if not path.exists():
        print(f"No manifest at {path}")
        return 1
    m = json.loads(path.read_text())
    print(f"run_manifest {m['run_date']}  as_of={m['as_of']}  contract={m['contract_hash'][:18]}…")
    print(f"  overall_ok={m['overall_ok']}  fail={m['fail_steps']}  stale={m['stale_steps']}"
          + (f"  unknown={m['unknown_steps']}" if m.get("unknown_steps") else ""))
    for s in m["steps"]:
        if s["status"] not in ("ok", "skipped"):
            print(f"  [{s['status'].upper():7}] {s['step']}"
                  + (f"  outputs={[c['result'] for c in s.get('output_checks', [])]}" if s.get("output_checks") else ""))
    return 0 if m["overall_ok"] else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Governance run manifest (A1).")
    ap.add_argument("--check", action="store_true", help="Print the latest manifest + non-ok steps.")
    ap.add_argument("--from-status", default=None, help="JSON file of [{name,rc,started_ts,ended_ts}] to replay.")
    ap.add_argument("--run-date", default=None, help="YYYY-MM-DD override (default: today).")
    args = ap.parse_args()
    if args.check:
        return _print_check()
    if args.from_status:
        records = json.loads(Path(args.from_status).read_text())
        rd = date.fromisoformat(args.run_date) if args.run_date else None
        m = write_manifest(records, run_date=rd)
        print(json.dumps(m, indent=2))
        return 0 if m["overall_ok"] else 1
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
