#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: heartbeat.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/governance/run_manifest.json
  (A1; may be absent — heartbeat ships before/independent of a manifest write)
- the newest /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/dislocations/brief_*.md

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/governance/heartbeat.json
  Liveness marker {loop_exit_code, manifest_present, fail/stale steps, brief
  present/committed, push_fired, push_reason}. Git-ignored runtime artifact.

VERSION: 1.0
LAST UPDATED: 2026-06-17
AUTHOR: Arjun Divecha (built by agent session, Governance Layer PRD v1.2, item A2)

DESCRIPTION:
A2 — the listener the nightly log never had. A non-zero loop exit, a fail/stale
run-manifest, or a missing/uncommitted brief used to be byte-identical to a
clean run until a human opened a log (the 06-12 -> 06-16 brief gap was caught
by eye). This fires an iMessage push (the proven house channel — NightWatch /
AA pipeline / BloombergGPT all use osascript->Messages; there is NO Telegram
sender wired into this loop) on any such condition, and writes a heartbeat.json
a --watchdog run can check to catch the loop dying entirely.

PUSH SAFETY: actual sending is gated. It fires ONLY in a real run; pass
--no-push (or set ASADO_PUSH_DISABLE=1) to compute + record the decision
without sending — used by every build/verification path so we never spam.

DEPENDENCIES:
- stdlib only (osascript for the push).

USAGE:
  python scripts/loop/heartbeat.py --exit-code 0          # nightly (pushes on trouble)
  python scripts/loop/heartbeat.py --exit-code 0 --no-push # verification (no send)
  python scripts/loop/heartbeat.py --watchdog --no-push    # ~12:30 safety net
=============================================================================
"""

from __future__ import annotations

import argparse
import glob as globmod
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.loop.loopdb import BASE_DIR, BRIEF_DIR, LOOP_DIR

GOV_DIR = LOOP_DIR / "governance"
MANIFEST_PATH = GOV_DIR / "run_manifest.json"
HEARTBEAT_PATH = GOV_DIR / "heartbeat.json"
PUSH_RECIPIENT = "+15104212111"
PUSH_CHANNEL = "imessage"
WATCHDOG_STALE_HOURS = 2


def send_push(text: str, recipient: str = PUSH_RECIPIENT) -> bool:
    """Fire-and-forget iMessage via osascript (house pattern). Never raises."""
    try:
        safe = text.replace("\\", "\\\\").replace('"', '\\"')
        script = (f'tell application "Messages" to send "{safe}" to '
                  f'buddy "{recipient}" of (service 1 whose service type is iMessage)')
        subprocess.Popen(["osascript", "-e", script], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception as exc:  # noqa: BLE001 — a push failure must never red the loop
        print(f"!!! heartbeat push failed (non-fatal): {exc}", flush=True)
        return False


def _newest_brief() -> "Path | None":
    briefs = [Path(p) for p in globmod.glob(str(BRIEF_DIR / "brief_*.md"))
              if os.path.isfile(p) and os.path.getsize(p) > 0]
    return max(briefs, key=lambda p: p.stat().st_mtime) if briefs else None


def _brief_committed(path: Path) -> bool:
    """Path-scoped: tracked at HEAD AND no uncommitted diff. Never `git status`
    on the whole tree (a dirty repo elsewhere must not false-red)."""
    rel = str(path)
    try:
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", rel],
                                 cwd=str(BASE_DIR), capture_output=True).returncode == 0
        if not tracked:
            return False
        clean = subprocess.run(["git", "diff", "--quiet", "HEAD", "--", rel],
                               cwd=str(BASE_DIR)).returncode == 0
        return clean
    except Exception:  # noqa: BLE001
        return False


def compute_health(exit_code: int) -> dict:
    manifest_present = MANIFEST_PATH.exists()
    fail_steps, stale_steps = [], []
    if manifest_present:
        m = json.loads(MANIFEST_PATH.read_text())
        fail_steps, stale_steps = m.get("fail_steps", []), m.get("stale_steps", [])
    brief = _newest_brief()
    brief_present = brief is not None
    brief_committed = _brief_committed(brief) if brief else False

    reasons = []
    if exit_code != 0:
        reasons.append(f"loop exit {exit_code}")
    if not manifest_present:
        reasons.append("run_manifest missing")
    if fail_steps:
        reasons.append(f"steps failed: {fail_steps}")
    if stale_steps:
        reasons.append(f"steps stale: {stale_steps}")
    if not brief_present:
        reasons.append("brief missing")
    elif not brief_committed:
        reasons.append("brief uncommitted")
    return {
        "schema_version": 1,
        "producer_version": "heartbeat.py 1.0",
        "as_of": datetime.now().isoformat(timespec="seconds"),
        "loop_exit_code": exit_code,
        "manifest_present": manifest_present,
        "manifest_fail_steps": fail_steps,
        "manifest_stale_steps": stale_steps,
        "brief_path": str(brief) if brief else None,
        "brief_present": brief_present,
        "brief_committed": brief_committed,
        "healthy": not reasons,
        "reasons": reasons,
        "pushed_channel": PUSH_CHANNEL,
    }


def _write(hb: dict) -> None:
    GOV_DIR.mkdir(parents=True, exist_ok=True)
    tmp = HEARTBEAT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(hb, indent=2, default=str))
    os.replace(tmp, HEARTBEAT_PATH)


def _push_enabled(no_push: bool) -> bool:
    return not no_push and os.environ.get("ASADO_PUSH_DISABLE") != "1"


def run_watchdog(no_push: bool) -> int:
    """Catch the loop dying entirely: heartbeat.json missing or stale."""
    stale = True
    if HEARTBEAT_PATH.exists():
        hb = json.loads(HEARTBEAT_PATH.read_text())
        try:
            age = datetime.now() - datetime.fromisoformat(hb["as_of"])
            stale = age > timedelta(hours=WATCHDOG_STALE_HOURS)
        except Exception:  # noqa: BLE001
            stale = True
    if stale:
        msg = "ASADO loop watchdog: heartbeat missing/stale — the nightly loop did not run."
        print(msg, flush=True)
        if _push_enabled(no_push):
            send_push(msg)
        return 1
    print("ASADO watchdog: heartbeat fresh, loop ran.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Governance liveness heartbeat (A2).")
    ap.add_argument("--exit-code", type=int, default=0, help="The loop's exit code.")
    ap.add_argument("--no-push", action="store_true", help="Compute + record but never send.")
    ap.add_argument("--watchdog", action="store_true", help="Safety-net: push if heartbeat is stale.")
    args = ap.parse_args()
    if args.watchdog:
        return run_watchdog(args.no_push)

    hb = compute_health(args.exit_code)
    if not hb["healthy"] and _push_enabled(args.no_push):
        hb["push_fired"] = send_push("ASADO loop: " + "; ".join(hb["reasons"]))
        hb["push_reason"] = "; ".join(hb["reasons"])
    else:
        hb["push_fired"] = False
        hb["push_reason"] = None if hb["healthy"] else "; ".join(hb["reasons"]) + " (push suppressed)"
    _write(hb)
    state = "HEALTHY" if hb["healthy"] else "UNHEALTHY"
    print(f"heartbeat: {state}  exit={hb['loop_exit_code']}  brief_committed={hb['brief_committed']}"
          + (f"  reasons={hb['reasons']}" if hb["reasons"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
