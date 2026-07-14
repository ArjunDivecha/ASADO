#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: check_convention_labels.py
=============================================================================

INPUT FILES:
- A reverdict output directory produced by scripts/harness/reverdict_v4.py, e.g.
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/harness_runs/reverdict_v4_<date>/
  Specifically its manifest.json (lists the fresh per-run result JSON paths) and
  every result JSON it references, e.g.
  /Users/arjundivecha/.../Data/loop/harness_runs/{hypothesis_id}_{ts}.json
  If no directory is given, the newest Data/loop/harness_runs/reverdict_v4_* is used.

OUTPUT FILES:
- None. This is a read-only checker; it communicates only via exit code and stdout.

VERSION: 1.0
LAST UPDATED: 2026-07-14
AUTHOR: Arjun Divecha (built by agent session, HARNESS-V4-HONEST-LEDGER-001)

DESCRIPTION:
The standalone convention-labeling gate (contract gate G4 / INV7). It verifies
that every result JSON produced by the G3 re-verdict sweep is self-describing:
each must carry an `execution_convention` block with the fields
{lag_days_effective, window_open_rule, frequency, harness_version} and valid
values (harness_version >= 4; frequency in {daily, monthly}; window_open_rule a
non-empty string; for a daily run lag_days_effective an int >= 1; for a monthly
run lag_days_effective present, may be null).

Exit codes (FAIL-IS-FAIL):
  0  all scanned result JSONs carry a valid execution_convention block.
  1  at least one JSON is missing a field / has an invalid value (offenders listed).
  2  the reverdict output directory (or its manifest) is absent -> prints
     'G3 not yet run' (the sweep has not been executed).

A 10th grader's version: after the re-grading is done, this walks every graded
paper and checks each one stamped WHICH stopwatch it used. If the sweep hasn't
run yet, it says so out loud instead of pretending everything is fine.

DEPENDENCIES:
- Python standard library only.

USAGE:
  python scripts/harness/check_convention_labels.py                 # newest reverdict dir
  python scripts/harness/check_convention_labels.py <reverdict_dir> # a specific dir
=============================================================================
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

REQUIRED_FIELDS = ("lag_days_effective", "window_open_rule", "frequency", "harness_version")


def validate_convention(result: dict[str, Any]) -> list[str]:
    """Return a list of problems with a result dict's execution_convention block.
    Empty list == valid. Used by both this checker and the G4 negative-fixture test."""
    problems: list[str] = []
    conv = result.get("execution_convention")
    if not isinstance(conv, dict):
        return ["missing execution_convention block"]
    for f in REQUIRED_FIELDS:
        if f not in conv:
            problems.append(f"missing field: {f}")
    if problems:
        return problems
    hv = conv.get("harness_version")
    if not isinstance(hv, int) or hv < 4:
        problems.append(f"harness_version must be int >= 4, got {hv!r}")
    freq = conv.get("frequency")
    if freq not in ("daily", "monthly"):
        problems.append(f"frequency must be daily|monthly, got {freq!r}")
    rule = conv.get("window_open_rule")
    if not isinstance(rule, str) or not rule.strip():
        problems.append("window_open_rule must be a non-empty string")
    lag = conv.get("lag_days_effective")
    if freq == "daily":
        if not isinstance(lag, int) or lag < 1:
            problems.append(f"daily lag_days_effective must be int >= 1 (INV1), got {lag!r}")
    # monthly: lag_days_effective present (may be None) — presence checked above.
    return problems


def _newest_reverdict_dir() -> Optional[Path]:
    from scripts.loop.loopdb import LOOP_DIR
    base = LOOP_DIR / "harness_runs"
    if not base.exists():
        return None
    dirs = sorted(base.glob("reverdict_v4_*"))
    return dirs[-1] if dirs else None


def _result_json_paths(out_dir: Path) -> list[Path]:
    """Prefer the manifest's recorded result_files; fall back to any *.json that
    looks like a per-run result (has an execution_convention) in the dir tree."""
    manifest = out_dir / "manifest.json"
    if manifest.exists():
        data = json.loads(manifest.read_text())
        paths = [Path(p) for p in data.get("result_files", []) if p]
        if paths:
            return paths
    # fallback: scan the dir (excludes summary.* and manifest.json)
    return [p for p in out_dir.glob("*.json") if p.name != "manifest.json"]


def main(argv: Optional[list[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out_dir = Path(argv[0]) if argv else _newest_reverdict_dir()

    if out_dir is None or not Path(out_dir).exists():
        print("G3 not yet run (no reverdict_v4 output directory found): "
              f"{out_dir if out_dir else 'Data/loop/harness_runs/reverdict_v4_*'}")
        return 2
    out_dir = Path(out_dir)
    if not (out_dir / "manifest.json").exists() and not list(out_dir.glob("*.json")):
        print(f"G3 not yet run (no result JSONs / manifest in {out_dir})")
        return 2

    paths = _result_json_paths(out_dir)
    if not paths:
        print(f"G3 not yet run (manifest lists no result_files in {out_dir})")
        return 2

    offenders: list[str] = []
    checked = 0
    for p in paths:
        if not p.exists():
            offenders.append(f"{p}: result JSON missing")
            continue
        checked += 1
        problems = validate_convention(json.loads(p.read_text()))
        if problems:
            offenders.append(f"{p.name}: {'; '.join(problems)}")

    if offenders:
        print(f"CONVENTION CHECK FAILED ({len(offenders)}/{len(paths)} offenders):")
        for o in offenders:
            print(f"  - {o}")
        return 1
    print(f"CONVENTION CHECK PASSED: {checked} result JSON(s) carry a valid "
          "execution_convention block (INV7).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
