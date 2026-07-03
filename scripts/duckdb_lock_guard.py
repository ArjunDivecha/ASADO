"""
=============================================================================
SCRIPT NAME: duckdb_lock_guard.py
=============================================================================

INPUT FILES:
- None directly (operates on whatever DuckDB path the caller passes, normally
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb)

OUTPUT FILES:
- None (log lines only, emitted through the caller's logger / stdout)

VERSION: 1.0
LAST UPDATED: 2026-07-03
AUTHOR: Claude (per Arjun's "the update must never fail" directive)

DESCRIPTION:
Shared helper that makes every ASADO pipeline connection to the main DuckDB
warehouse survive lock squatters. DuckDB allows either one read-write process
OR many read-only processes on a database file — so a single stray process
holding the file (even read-only) blocks every pipeline writer. In practice
the squatters are idle Claude Desktop analysis-sandbox kernels living under
~/.claude-science/ that open asado.duckdb and never close it (this killed the
nightly daily-panels build AND the predmkt job on 2026-07-02 and 2026-07-03).

guarded_connect() replaces bare duckdb.connect() in pipeline scripts:
  1. Try to connect. On a "Could not set lock / Conflicting lock" IOException,
     parse the holder's executable path and PID out of DuckDB's own error
     message ("Conflicting lock is held in <exe> (PID <n>)").
  2. If the holder's executable path AND its live `ps` command line both match
     a killable pattern (default: ".claude-science" — sandbox kernels only,
     never an ASADO pipeline process), SIGTERM it, escalate to SIGKILL after
     10s, and retry. Several squatters can hold read-only locks at once;
     DuckDB names them one at a time, so up to MAX_KILLS holders are cleared
     per call.
  3. If the holder is NOT killable (e.g. a legitimately overlapping ASADO job
     such as a monthly setup_duckdb rebuild), wait with backoff up to
     wait_budget_s (default 300s) for it to finish, then raise a loud,
     actionable error naming the holder. FAIL IS FAIL — no silent fallback.

Environment overrides:
- ASADO_LOCK_GUARD_KILL=0            disable killing entirely (wait-only)
- ASADO_LOCK_GUARD_KILLABLE=a,b,c    replace the killable substring patterns
- ASADO_LOCK_GUARD_WAIT_S=600        override the default wait budget

DEPENDENCIES:
- duckdb (stdlib otherwise: os, re, signal, subprocess, time)

USAGE:
    from scripts.duckdb_lock_guard import guarded_connect  # repo root on path
    # or, when scripts/ itself is sys.path[0] (python scripts/foo.py):
    from duckdb_lock_guard import guarded_connect

    con = guarded_connect(DB_PATH)                    # read-write
    con = guarded_connect(DB_PATH, read_only=True)    # read-only

NOTES:
- The kill decision requires the pattern to match BOTH the exe path DuckDB
  reported AND the process's current `ps` command line — this guards against
  PID reuse between the failed connect and the kill.
- Never kills its own process or parent, regardless of pattern.
- Everything the guard does (kills, waits, escalations) is logged loudly so
  NightWatch and the job logs show exactly what happened.
=============================================================================
"""

from __future__ import annotations

import logging
import os
import re
import signal
import subprocess
import time
from pathlib import Path
from typing import List, Optional, Tuple

import duckdb

# Substrings identifying processes that are safe to kill when they squat on
# the warehouse lock. Default: Claude Desktop analysis-sandbox kernels. These
# are interactive scratch kernels — killing one aborts a chat sandbox, never a
# pipeline. Extend via ASADO_LOCK_GUARD_KILLABLE if a new squatter appears.
DEFAULT_KILLABLE_PATTERNS = [".claude-science"]

# How many distinct squatters we will clear in one guarded_connect() call
# (several read-only holders can stack up; DuckDB names one per attempt).
MAX_KILLS = 5

DEFAULT_WAIT_BUDGET_S = 300.0

_LOCK_MARKERS = ("could not set lock", "conflicting lock")
_HOLDER_RE = re.compile(r"Conflicting lock is held in (.+?) \(PID (\d+)\)")

_log = logging.getLogger("duckdb_lock_guard")


def _killable_patterns() -> List[str]:
    env = os.environ.get("ASADO_LOCK_GUARD_KILLABLE")
    if env is not None:
        return [p for p in (s.strip() for s in env.split(",")) if p]
    return list(DEFAULT_KILLABLE_PATTERNS)


def _kill_enabled() -> bool:
    return os.environ.get("ASADO_LOCK_GUARD_KILL", "1") != "0"


def _wait_budget_default() -> float:
    try:
        return float(os.environ.get("ASADO_LOCK_GUARD_WAIT_S", DEFAULT_WAIT_BUDGET_S))
    except ValueError:
        return DEFAULT_WAIT_BUDGET_S


def _parse_holder(err_msg: str) -> Optional[Tuple[str, int]]:
    """Extract (exe_path, pid) from DuckDB's lock-conflict error message."""
    m = _HOLDER_RE.search(err_msg)
    if not m:
        return None
    return m.group(1), int(m.group(2))


def _live_command(pid: int) -> Optional[str]:
    """Return the process's current full command line, or None if it's gone."""
    try:
        out = subprocess.run(
            ["ps", "-o", "command=", "-p", str(pid)],
            capture_output=True, text=True, timeout=10,
        )
    except Exception:
        return None
    cmd = out.stdout.strip()
    return cmd or None


def _pids_holding_file(path: str) -> Optional[set]:
    """PIDs with the file open, via lsof (-w suppresses smbfs stat warnings).
    Returns None if lsof itself could not be run (caller falls back to a
    stricter name-only check)."""
    try:
        out = subprocess.run(
            ["lsof", "-w", "-t", "--", path],
            capture_output=True, text=True, timeout=15,
        )
    except Exception:
        return None
    return {int(tok) for tok in out.stdout.split() if tok.strip().isdigit()}


def _is_lock_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return any(marker in msg for marker in _LOCK_MARKERS)


def _process_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        pass
    # A zombie still answers signal 0 but holds no file locks — treat as gone.
    try:
        out = subprocess.run(
            ["ps", "-o", "state=", "-p", str(pid)],
            capture_output=True, text=True, timeout=10,
        )
        state = out.stdout.strip()
        if not state or state.startswith("Z"):
            return False
    except Exception:
        pass
    return True


def _terminate(pid: int, label: str) -> bool:
    """SIGTERM then SIGKILL a squatter. Returns True once the process is gone."""
    _log.warning("LOCK GUARD: killing lock squatter PID %d (%s) with SIGTERM", pid, label)
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    except PermissionError:
        _log.error("LOCK GUARD: no permission to kill PID %d", pid)
        return False
    deadline = time.time() + 10
    while time.time() < deadline:
        if not _process_alive(pid):
            return True
        time.sleep(0.5)
    _log.warning("LOCK GUARD: PID %d ignored SIGTERM after 10s, escalating to SIGKILL", pid)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    deadline = time.time() + 5
    while time.time() < deadline:
        if not _process_alive(pid):
            return True
        time.sleep(0.5)
    _log.error("LOCK GUARD: PID %d survived SIGKILL (?)", pid)
    return False


def guarded_connect(
    db_path,
    read_only: bool = False,
    wait_budget_s: Optional[float] = None,
    **connect_kwargs,
):
    """duckdb.connect() that clears killable lock squatters and waits out
    legitimate holders. Raises RuntimeError with an actionable message if the
    database is still locked when the wait budget runs out (FAIL IS FAIL)."""
    db_path = str(db_path)
    budget = _wait_budget_default() if wait_budget_s is None else float(wait_budget_s)
    deadline = time.time() + budget
    patterns = _killable_patterns()
    own_pids = {os.getpid(), os.getppid()}
    kills = 0
    attempt = 0
    last_holder: Optional[Tuple[str, int]] = None

    while True:
        attempt += 1
        try:
            return duckdb.connect(db_path, read_only=read_only, **connect_kwargs)
        except Exception as exc:  # noqa: BLE001 — filtered right below
            if not _is_lock_error(exc):
                raise
            holder = _parse_holder(str(exc))
            last_holder = holder or last_holder

            if holder is not None:
                exe_path, pid = holder
                live_cmd = _live_command(pid)
                exe_match = any(p in exe_path for p in patterns)
                cmd_match = live_cmd is not None and any(p in live_cmd for p in patterns)
                # DuckDB reports the RESOLVED executable (a venv symlink shows
                # as e.g. /opt/homebrew/.../Python), so accept a pattern match
                # on EITHER the reported exe or the live command line — but
                # only kill a PID that verifiably still holds the DB file open
                # (lsof), which is the real guard against PID reuse. If lsof
                # is unavailable, fall back to requiring both name matches.
                holding = _pids_holding_file(db_path)
                verified = (pid in holding) if holding is not None else (exe_match and cmd_match)
                if (
                    _kill_enabled()
                    and kills < MAX_KILLS
                    and pid not in own_pids
                    and (exe_match or cmd_match)
                    and verified
                ):
                    _log.warning(
                        "LOCK GUARD: %s is locked by killable squatter PID %d (%s)",
                        db_path, pid, live_cmd,
                    )
                    if _terminate(pid, exe_path):
                        kills += 1
                        time.sleep(1.0)  # let the OS release the file lock
                        continue
                if live_cmd is None:
                    # Holder already exited between our attempt and inspection —
                    # the lock should clear momentarily.
                    time.sleep(1.0)
                    continue
                _log.warning(
                    "LOCK GUARD: %s locked by non-killable PID %d (%s) — waiting "
                    "(%.0fs of budget left)",
                    db_path, pid, live_cmd, max(0.0, deadline - time.time()),
                )

            if time.time() >= deadline:
                holder_desc = (
                    f"PID {last_holder[1]} ({last_holder[0]})" if last_holder else "unknown process"
                )
                raise RuntimeError(
                    f"Database {db_path} is still locked by {holder_desc} after "
                    f"{budget:.0f}s. If this is a stray sandbox/notebook kernel, add "
                    f"its path to ASADO_LOCK_GUARD_KILLABLE (or scripts/"
                    f"duckdb_lock_guard.py DEFAULT_KILLABLE_PATTERNS) so the guard "
                    f"may clear it; if it is a legitimate ASADO job, let it finish "
                    f"and re-run."
                ) from exc
            time.sleep(min(15.0, 2.0 * attempt))
