#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: tests/test_review_audit_monitor.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-ic-monitor/family_ic_monitor.spec.md
  The contract. Read to parse scope.in / scope.forbid from its YAML frontmatter
  (the audit checks the diff against the CONTRACT's own scope, not a hardcoded copy).
- Git metadata of the worktree (via `git diff` / `git status`) to enumerate the
  changed paths on this branch.

OUTPUT FILES:
- None (pure asserts).

VERSION: 1.0
LAST UPDATED: 2026-07-14
AUTHOR: Arjun Divecha (built by agent session, contract FAMILY-IC-MONITOR-001)

DESCRIPTION:
The contract's `review.command` (mode: required). Codex/human review is
substituted with a DETERMINISTIC audit that asserts:

  (a) every changed path on this branch is inside a scope.in pattern;
  (b) no changed path matches a scope.forbid pattern;
  (c) every unit invariant id (INV1..INV6) is covered by at least one collected
      pytest test in tests/test_family_ic_monitor.py.

Path matching mirrors run_codex_loop.py exactly: PurePosixPath.full_match, and
the contract's own spec file is excluded from the changed set (the runner does
the same, because the loop rewrites the spec's ledger). implementation-notes-
monitor.md is likewise excluded -- it is untracked Build-Mode bookkeeping the
contract process itself mandates, never a deliverable. Everything else must
land in scope. INV4's live known-answer is gate G3 (permissioned); its
comparison LOGIC is additionally unit-tested here as INV4, so it appears in the
coverage set too.

DEPENDENCIES:
- pytest, pyyaml (project venv); git.

USAGE:
  venv/bin/python -m pytest tests/test_review_audit_monitor.py -q
=============================================================================
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path, PurePosixPath

import pytest
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
SPEC_PATH = BASE_DIR / "family_ic_monitor.spec.md"
# Build-Mode meta files excluded from the scope diff (see module docstring).
META_EXCLUSIONS = {"family_ic_monitor.spec.md", "implementation-notes-monitor.md"}
INVARIANT_IDS = [f"inv{i}" for i in range(1, 7)]  # inv1..inv6


def _run(cmd: list[str]) -> str:
    return subprocess.run(cmd, cwd=str(BASE_DIR), capture_output=True, text=True).stdout


def _load_scope() -> dict:
    text = SPEC_PATH.read_text()
    assert text.startswith("---"), "spec must start with YAML frontmatter"
    fm = text.split("---", 2)[1]
    data = yaml.safe_load(fm)
    return data["scope"]


def _changed_paths() -> list[str]:
    """Union of committed (main...HEAD) and uncommitted (status) changed paths,
    minus the Build-Mode meta files."""
    paths: set[str] = set()
    for line in _run(["git", "diff", "--name-only", "main...HEAD"]).splitlines():
        if line.strip():
            paths.add(line.strip())
    porcelain = subprocess.run(["git", "status", "--porcelain"], cwd=str(BASE_DIR),
                               capture_output=True, text=True).stdout
    for line in porcelain.splitlines():
        if not line.strip():
            continue
        entry = line[3:] if len(line) > 3 else line
        if " -> " in entry:
            old, new = entry.split(" -> ", 1)
            paths.update({old.strip().strip('"'), new.strip().strip('"')})
        else:
            paths.add(entry.strip().strip('"'))
    return sorted(p for p in paths if p and p not in META_EXCLUSIONS)


def test_review_all_changed_paths_are_in_scope():
    # Post-merge lifecycle guard: once exp/family-ic-monitor is merged and HEAD
    # IS main, there is no contract-branch diff left to audit (the scope check
    # did its job pre-merge). During the build HEAD != main, so the audit RUNS
    # and genuinely enforces scope on the committed + uncommitted changes.
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(BASE_DIR), text=True).strip()
    main = subprocess.check_output(["git", "rev-parse", "main"], cwd=str(BASE_DIR), text=True).strip()
    if head == main:
        pytest.skip("post-merge: HEAD is main -- no contract branch diff to scope-audit")
    scope = _load_scope()
    allowed = [p for p in scope.get("in", []) if isinstance(p, str)]
    changed = _changed_paths()
    assert changed, "no changed paths detected -- nothing to review (did the branch diverge from main?)"
    out_of_scope = [p for p in changed
                    if not any(PurePosixPath(p).full_match(pat) for pat in allowed)]
    assert not out_of_scope, f"changed paths outside scope.in: {out_of_scope} (scope.in={allowed})"


def test_review_no_forbidden_path_touched():
    scope = _load_scope()
    forbidden = [p for p in scope.get("forbid", []) if isinstance(p, str)]
    changed = _changed_paths()
    violations = [f"{p} matches forbid {pat!r}"
                  for p in changed for pat in forbidden
                  if PurePosixPath(p).full_match(pat)]
    assert not violations, f"scope.forbid touched: {violations}"


def test_review_all_invariants_are_covered_by_tests():
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-p", "no:cacheprovider", "tests/test_family_ic_monitor.py"],
        cwd=str(BASE_DIR), capture_output=True, text=True)
    node_ids = res.stdout.lower()
    assert res.returncode == 0, f"collection failed:\n{res.stdout}\n{res.stderr}"
    missing = [inv for inv in INVARIANT_IDS if inv not in node_ids]
    assert not missing, f"invariants with no covering test: {missing}"
