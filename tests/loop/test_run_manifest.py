#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: tests/loop/test_run_manifest.py
=============================================================================

INPUT FILES: none at runtime — every fixture (tmp contract YAML, tmp output
files, fabricated step records, stub table counter) is built in-test. The
real config/governance_contract.yaml and Data/loop/asado_loop.duckdb are
NEVER touched (table checks use a stub, file checks use tmp_path).

OUTPUT FILES: none (pure assertions).

VERSION: 1.0
LAST UPDATED: 2026-06-17
AUTHOR: Arjun Divecha (built by agent session, Governance Layer PRD v1.2, item A1)

DESCRIPTION:
A1 acceptance tests for scripts/loop/run_manifest.py. Proves the run manifest
catches the stale-but-green failure mode:
  - rc != 0                          -> fail
  - rc == 0 but expected output gone -> fail (the catch)
  - rc == 0 but file did not advance -> stale
  - fresh file                       -> ok
  - loop_db_table missing/empty      -> fail; present -> ok
  - step not run (--only subset)     -> skipped (never fail)
  - contract is the single source    -> manifest steps come from the contract;
                                        contract_hash present, hex, changes on edit
  - date templating resolves         -> {date:%Y_%m_%d} -> run_date.strftime

USAGE:
  venv/bin/python -m pytest tests/loop/test_run_manifest.py -q
=============================================================================
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
from scripts.loop import run_manifest  # noqa: E402


def _now_iso(offset_sec: int = 0) -> str:
    return (datetime.now() + timedelta(seconds=offset_sec)).isoformat(timespec="seconds")


def _contract(tmp_path: Path, steps: list[dict]) -> Path:
    c = {"schema_version": 1, "contract_version": "test", "steps": steps, "scorecard_dimensions": []}
    p = tmp_path / "contract.yaml"
    p.write_text(yaml.safe_dump(c))
    return p


def _status_of(manifest: dict, step_name: str) -> str:
    return next(s["status"] for s in manifest["steps"] if s["step"] == step_name)


def test_rc_nonzero_is_fail(tmp_path):
    contract = _contract(tmp_path, [{"name": "s1", "expected_outputs": []}])
    recs = [{"name": "s1", "rc": 1, "started_ts": _now_iso(), "ended_ts": _now_iso(1)}]
    m = run_manifest.build_manifest(recs, contract_path=contract, table_count=None)
    assert _status_of(m, "s1") == "fail"
    assert m["fail_steps"] == ["s1"] and not m["overall_ok"]


def test_rc127_binary_missing_is_fail(tmp_path):
    contract = _contract(tmp_path, [{"name": "s1", "expected_outputs": []}])
    recs = [{"name": "s1", "rc": 127, "started_ts": _now_iso(), "ended_ts": _now_iso(1)}]
    m = run_manifest.build_manifest(recs, contract_path=contract, table_count=None)
    assert _status_of(m, "s1") == "fail"


def test_partial_exit2_is_partial_not_fail(tmp_path):
    contract = _contract(tmp_path, [{"name": "s1", "optional": True, "expected_outputs": []}])
    recs = [{"name": "s1", "rc": 2, "started_ts": _now_iso(), "ended_ts": _now_iso(1)}]
    m = run_manifest.build_manifest(recs, contract_path=contract, table_count=None)
    assert _status_of(m, "s1") == "partial"
    assert m["overall_ok"]  # partial is not a fail/stale


def test_missing_output_after_clean_exit_is_fail(tmp_path):
    """The stale-but-green catch: exited 0 but the declared file is absent."""
    missing = tmp_path / "never_written.parquet"
    contract = _contract(tmp_path, [{"name": "s1", "expected_outputs": [
        {"kind": "file", "path_template": str(missing), "staleness": "existence"}]}])
    recs = [{"name": "s1", "rc": 0, "started_ts": _now_iso(), "ended_ts": _now_iso(1)}]
    m = run_manifest.build_manifest(recs, contract_path=contract, table_count=None)
    assert _status_of(m, "s1") == "fail"


def test_stale_mtime_after_clean_exit(tmp_path):
    """Exited 0 but the file is from a prior run (mtime < started_ts)."""
    f = tmp_path / "old.parquet"
    f.write_text("x")
    old = (datetime.now() - timedelta(days=1)).timestamp()
    os.utime(f, (old, old))
    contract = _contract(tmp_path, [{"name": "s1", "expected_outputs": [
        {"kind": "file", "path_template": str(f), "staleness": "mtime"}]}])
    recs = [{"name": "s1", "rc": 0, "started_ts": _now_iso(), "ended_ts": _now_iso(1)}]
    m = run_manifest.build_manifest(recs, contract_path=contract, table_count=None)
    assert _status_of(m, "s1") == "stale"
    assert m["stale_steps"] == ["s1"] and not m["overall_ok"]


def test_fresh_mtime_is_ok(tmp_path):
    f = tmp_path / "fresh.parquet"
    f.write_text("x")  # mtime ~ now
    contract = _contract(tmp_path, [{"name": "s1", "expected_outputs": [
        {"kind": "file", "path_template": str(f), "staleness": "mtime"}]}])
    recs = [{"name": "s1", "rc": 0, "started_ts": _now_iso(-60), "ended_ts": _now_iso()}]
    m = run_manifest.build_manifest(recs, contract_path=contract, table_count=None)
    assert _status_of(m, "s1") == "ok"
    assert m["overall_ok"]


def test_existence_file_does_not_require_freshness(tmp_path):
    """staleness=existence: an old-but-present file is ok (gated/monthly outputs)."""
    f = tmp_path / "gated.parquet"
    f.write_text("x")
    old = (datetime.now() - timedelta(days=30)).timestamp()
    os.utime(f, (old, old))
    contract = _contract(tmp_path, [{"name": "s1", "expected_outputs": [
        {"kind": "file", "path_template": str(f), "staleness": "existence"}]}])
    recs = [{"name": "s1", "rc": 0, "started_ts": _now_iso(), "ended_ts": _now_iso(1)}]
    m = run_manifest.build_manifest(recs, contract_path=contract, table_count=None)
    assert _status_of(m, "s1") == "ok"


def test_glob_newest_fresh_is_ok(tmp_path):
    """Data-as-of dated output (brief): newest match rewritten this run -> ok."""
    d = tmp_path / "briefs"
    d.mkdir()
    old = d / "brief_2026_06_15.md"
    old.write_text("x")
    t_old = (datetime.now() - timedelta(days=2)).timestamp()
    os.utime(old, (t_old, t_old))
    new = d / "brief_2026_06_16.md"   # data-as-of lags wall-clock; fresh ~now
    new.write_text("y")
    contract = _contract(tmp_path, [{"name": "s1", "expected_outputs": [
        {"kind": "file", "glob": str(d / "brief_*.md"), "staleness": "mtime"}]}])
    recs = [{"name": "s1", "rc": 0, "started_ts": _now_iso(-60), "ended_ts": _now_iso()}]
    m = run_manifest.build_manifest(recs, contract_path=contract, table_count=None)
    assert _status_of(m, "s1") == "ok"


def test_glob_newest_stale_is_stale(tmp_path):
    """No new brief written this run -> newest is from a prior run -> stale."""
    d = tmp_path / "briefs"
    d.mkdir()
    f = d / "brief_2026_06_15.md"
    f.write_text("x")
    t = (datetime.now() - timedelta(days=1)).timestamp()
    os.utime(f, (t, t))
    contract = _contract(tmp_path, [{"name": "s1", "expected_outputs": [
        {"kind": "file", "glob": str(d / "brief_*.md"), "staleness": "mtime"}]}])
    recs = [{"name": "s1", "rc": 0, "started_ts": _now_iso(), "ended_ts": _now_iso(1)}]
    m = run_manifest.build_manifest(recs, contract_path=contract, table_count=None)
    assert _status_of(m, "s1") == "stale"


def test_glob_no_match_is_fail(tmp_path):
    d = tmp_path / "briefs"
    d.mkdir()
    contract = _contract(tmp_path, [{"name": "s1", "expected_outputs": [
        {"kind": "file", "glob": str(d / "brief_*.md"), "staleness": "mtime"}]}])
    recs = [{"name": "s1", "rc": 0, "started_ts": _now_iso(), "ended_ts": _now_iso(1)}]
    m = run_manifest.build_manifest(recs, contract_path=contract, table_count=None)
    assert _status_of(m, "s1") == "fail"


def test_loop_db_table_missing_is_fail_present_is_ok(tmp_path):
    contract = _contract(tmp_path, [
        {"name": "good", "expected_outputs": [{"kind": "loop_db_table", "table": "present"}]},
        {"name": "bad", "expected_outputs": [{"kind": "loop_db_table", "table": "absent"}]},
    ])
    recs = [{"name": "good", "rc": 0, "started_ts": _now_iso(), "ended_ts": _now_iso(1)},
            {"name": "bad", "rc": 0, "started_ts": _now_iso(), "ended_ts": _now_iso(1)}]
    counts = {"present": 42, "absent": None}
    m = run_manifest.build_manifest(recs, contract_path=contract, table_count=counts.get)
    assert _status_of(m, "good") == "ok"
    assert _status_of(m, "bad") == "fail"


def test_unrun_step_is_skipped_not_fail(tmp_path):
    """--only / partial subset: absent steps must not be marked fail."""
    contract = _contract(tmp_path, [
        {"name": "ran", "expected_outputs": []},
        {"name": "not_run", "expected_outputs": [{"kind": "loop_db_table", "table": "whatever"}]},
    ])
    recs = [{"name": "ran", "rc": 0, "started_ts": _now_iso(), "ended_ts": _now_iso(1)}]
    m = run_manifest.build_manifest(recs, contract_path=contract, table_count=None)
    assert _status_of(m, "not_run") == "skipped"
    assert m["overall_ok"]  # a skipped step does not red the run


def test_single_source_and_contract_hash(tmp_path):
    """Manifest steps come from the contract; hash is hex and changes on edit."""
    contract = _contract(tmp_path, [{"name": "s1", "expected_outputs": []}])
    recs = [{"name": "s1", "rc": 0, "started_ts": _now_iso(), "ended_ts": _now_iso(1)}]
    m1 = run_manifest.build_manifest(recs, contract_path=contract, table_count=None)
    assert [s["step"] for s in m1["steps"]] == ["s1"]
    assert m1["contract_hash"].startswith("sha256:") and len(m1["contract_hash"]) == 7 + 64

    # Append a step -> the manifest reflects it (proves single source of truth).
    contract2 = _contract(tmp_path / "d2", [
        {"name": "s1", "expected_outputs": []},
        {"name": "s2", "expected_outputs": []},
    ]) if (tmp_path / "d2").mkdir(exist_ok=True) or True else None
    m2 = run_manifest.build_manifest(recs, contract_path=contract2, table_count=None)
    assert [s["step"] for s in m2["steps"]] == ["s1", "s2"]
    assert m2["contract_hash"] != m1["contract_hash"]


def test_unknown_step_reported(tmp_path):
    """A step the loop ran but the contract doesn't know about is flagged."""
    contract = _contract(tmp_path, [{"name": "s1", "expected_outputs": []}])
    recs = [{"name": "s1", "rc": 0, "started_ts": _now_iso(), "ended_ts": _now_iso(1)},
            {"name": "ghost", "rc": 0, "started_ts": _now_iso(), "ended_ts": _now_iso(1)}]
    m = run_manifest.build_manifest(recs, contract_path=contract, table_count=None)
    assert m["unknown_steps"] == ["ghost"] and not m["overall_ok"]


def test_date_template_resolves():
    assert run_manifest.resolve_template(
        "Data/dislocations/brief_{date:%Y_%m_%d}.md", date(2026, 6, 17)
    ) == "Data/dislocations/brief_2026_06_17.md"
    assert run_manifest.resolve_template(
        "Data/loop/calibration/calibration_{date:%Y_%m}.md", date(2026, 6, 17)
    ) == "Data/loop/calibration/calibration_2026_06.md"


def test_real_contract_loads_and_matches_steps():
    """The shipped contract parses and its step names match loop_daily_job STEPS."""
    contract, h = run_manifest.load_contract()
    assert h and len(h) == 64
    contract_names = {s["name"] for s in contract["steps"]}
    src = (BASE_DIR / "scripts" / "loop" / "loop_daily_job.py").read_text()
    import re
    step_names = set(re.findall(r'\(\s*"([a-z0-9_]+)",\s*\[', src))
    # The real STEPS names referenced as ("name", [ ... ]) must all be in the contract.
    missing = step_names - contract_names
    extra = contract_names - step_names
    assert not missing, f"contract missing steps: {missing}"
    assert not extra, f"contract has unknown steps: {extra}"
