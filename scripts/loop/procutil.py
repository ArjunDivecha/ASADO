#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: procutil.py
=============================================================================

INPUT FILES:  none
OUTPUT FILES: none (pure utility)

VERSION: 1.0
LAST UPDATED: 2026-06-20
AUTHOR: Arjun Divecha / Claude Code

DESCRIPTION:
Bounded subprocess execution for the ASADO loop. The nightly orchestrators
(daily_update.py, loop_daily_job.py) previously called subprocess.run with NO
timeout anywhere — a wedged Bloomberg pull, an up-but-unresponsive Neo4j bolt,
or a Dropbox filesystem stall would hang the entire pipeline indefinitely (the
foreground launchd wrapper never returns, the heartbeat never writes). This
module provides run_bounded(): a hard wall-clock timeout that kills the whole
PROCESS GROUP on expiry. The group teardown is essential because the hung
children are `conda run -> python -> bbcomm` wrappers whose grandchildren would
otherwise orphan and leak the Bloomberg session if only the direct child were
killed.

DEPENDENCIES: stdlib only (os, signal, subprocess)

USAGE:
  from scripts.loop.procutil import run_bounded, TIMEOUT_RC
  res = run_bounded(cmd, timeout=1800, cwd=..., env=...)
  if res.timed_out: ...
  res.returncode / res.stdout / res.stderr  # mirrors subprocess.CompletedProcess
=============================================================================
"""
from __future__ import annotations

import os
import signal
import subprocess
from typing import Optional, Sequence

# Conventional exit code for "killed by timeout" (matches GNU coreutils `timeout`).
TIMEOUT_RC = 124

# Sensible per-class budgets (seconds). Callers may override per step.
DEFAULT_TIMEOUTS = {
    "bbg": 1800,     # Bloomberg pulls can be slow (BQL rating history ~2min)
    "neo4j": 600,
    "db": 900,       # a DuckDB rebuild can take 8-12 min; callers needing that pass explicitly
    "loop": 1200,
    "default": 1200,
}


class BoundedResult:
    """Mirrors subprocess.CompletedProcess (.returncode/.stdout/.stderr) plus
    a .timed_out flag. On timeout, returncode == TIMEOUT_RC."""

    __slots__ = ("returncode", "stdout", "stderr", "timed_out")

    def __init__(self, returncode: int, stdout: str, stderr: str, timed_out: bool = False):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.timed_out = timed_out


def _kill_group(proc: subprocess.Popen) -> None:
    """SIGTERM the process group, give it 5s, then SIGKILL. No-op if already gone."""
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        return
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        proc.wait(timeout=5)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def run_bounded(cmd: Sequence[str], timeout: float, *,
                cwd: Optional[str] = None, env: Optional[dict] = None,
                text: bool = True, capture: bool = True) -> BoundedResult:
    """Run cmd with a hard wall-clock timeout; on expiry kill the whole process
    group (so conda/python/bbcomm grandchildren cannot orphan). Returns a
    BoundedResult. Never raises TimeoutExpired — a timeout is reported as
    returncode TIMEOUT_RC with timed_out=True so callers treat it like any
    other non-zero exit.

    start_new_session=True puts the child in its own process group, which is
    what makes os.killpg able to reap the entire subtree.
    """
    pipe = subprocess.PIPE if capture else None
    try:
        proc = subprocess.Popen(list(cmd), cwd=cwd, env=env, text=text,
                                stdout=pipe, stderr=pipe, start_new_session=True)
    except FileNotFoundError as e:
        # e.g. a missing `conda`/`git` binary — surface as a clean failure, not a crash.
        return BoundedResult(127, "", f"[run_bounded] command not found: {e}", False)
    try:
        out, err = proc.communicate(timeout=timeout)
        return BoundedResult(proc.returncode, out or "", err or "", False)
    except subprocess.TimeoutExpired:
        _kill_group(proc)
        try:
            out, err = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            out, err = "", ""
        msg = f"\n[run_bounded] TIMEOUT after {timeout:.0f}s — process group killed"
        return BoundedResult(TIMEOUT_RC, out or "", (err or "") + msg, True)
