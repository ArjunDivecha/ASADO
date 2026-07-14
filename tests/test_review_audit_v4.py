#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: tests/test_review_audit_v4.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-harness-v4/harness_v4_honest_ledger.spec.md
  The contract. Read to parse scope.in / scope.forbid from its YAML frontmatter
  (the audit checks the diff against the CONTRACT's own scope, not a hardcoded copy).
- Git metadata of the worktree (via `git diff` / `git status`) to enumerate the
  changed paths on this branch.

OUTPUT FILES:
- None (pure asserts).

VERSION: 1.0
LAST UPDATED: 2026-07-14
AUTHOR: Arjun Divecha (built by agent session, HARNESS-V4-HONEST-LEDGER-001)

DESCRIPTION:
The contract's `review.command` (mode: required). Codex was unavailable (usage
limit), so per the Build Mode brief the human/codex reviewer is substituted with
a DETERMINISTIC audit that asserts:

  (a) every changed path on this branch is inside a scope.in pattern;
  (b) no changed path matches a scope.forbid pattern;
  (c) every invariant id (INV1..INV7) and the G4 convention check is covered by
      at least one collected pytest test.

Path matching mirrors run_codex_loop.py exactly: PurePosixPath.full_match, and
the contract's own spec file is excluded from the changed set (the runner does
the same, because the loop rewrites the spec's ledger). implementation-notes.md
is likewise excluded — it is untracked Build-Mode bookkeeping the contract
process itself mandates, never a deliverable (same rationale as the spec
exclusion). Everything else must land in scope.

DEPENDENCIES:
- pytest, pyyaml (project venv); git.

USAGE:
  venv/bin/python -m pytest tests/test_review_audit_v4.py -q
=============================================================================
"""

from __future__ import annotations

import subprocess
import sys

import pytest
from pathlib import Path, PurePosixPath

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
SPEC_PATH = BASE_DIR / "harness_v4_honest_ledger.spec.md"
# Build-Mode meta files excluded from the scope diff (see module docstring).
META_EXCLUSIONS = {"harness_v4_honest_ledger.spec.md", "implementation-notes.md"}
INVARIANT_IDS = [f"inv{i}" for i in range(1, 8)]  # inv1..inv7


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
    # committed diff vs the merge-base with main
    for line in _run(["git", "diff", "--name-only", "main...HEAD"]).splitlines():
        if line.strip():
            paths.add(line.strip())
    # uncommitted: staged, unstaged, untracked (porcelain)
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



def _on_contract_branch() -> bool:
    """These two scope-audit tests belong to contract HARNESS-V4-HONEST-LEDGER-001
    and are only meaningful on its build branch: they diff the working tree
    against main under THAT contract's scope rules. On any other branch or
    worktree (including main post-merge, and sibling contract branches whose
    own scopes legitimately differ) they must skip - a contract's review audit
    must never leak into the global suite (lesson, 2026-07-14)."""
    import subprocess as _sp
    try:
        branch = _sp.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                  text=True).strip()
    except Exception:
        return False
    return branch == "exp/harness-v4"

def test_review_all_changed_paths_are_in_scope():
    if not _on_contract_branch():
        pytest.skip("HARNESS-V4 contract audit: only runs on exp/harness-v4")
    import subprocess as _sp
    head = _sp.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    base = _sp.check_output(["git", "merge-base", "HEAD", "main"], text=True).strip()
    main = _sp.check_output(["git", "rev-parse", "main"], text=True).strip()
    if base == main and head != main or head == main:
        # post-merge lifecycle: HEAD is main (or contains it) - there is no
        # contract branch diff left to audit, and git status picks up unrelated
        # working-tree state. The scope audit did its job pre-merge (contract
        # ledger, 2026-07-14).
        pytest.skip("post-merge: no contract branch diff to scope-audit")
    scope = _load_scope()
    allowed = [p for p in scope.get("in", []) if isinstance(p, str)]
    changed = _changed_paths()
    assert changed, "no changed paths detected — nothing to review (did the branch diverge from main?)"
    out_of_scope = [p for p in changed
                    if not any(PurePosixPath(p).full_match(pat) for pat in allowed)]
    assert not out_of_scope, f"changed paths outside scope.in: {out_of_scope} (scope.in={allowed})"


def test_review_no_forbidden_path_touched():
    if not _on_contract_branch():
        pytest.skip("HARNESS-V4 contract audit: only runs on exp/harness-v4")
    scope = _load_scope()
    forbidden = [p for p in scope.get("forbid", []) if isinstance(p, str)]
    changed = _changed_paths()
    violations = [f"{p} matches forbid {pat!r}"
                  for p in changed for pat in forbidden
                  if PurePosixPath(p).full_match(pat)]
    assert not violations, f"scope.forbid touched: {violations}"


def test_review_all_invariants_and_g4_are_covered_by_tests():
    # Collect the v4 suite and assert each invariant id + the G4 check appears in
    # at least one collected test node id.
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q",
         "-p", "no:cacheprovider", "tests/test_harness_v4.py"],
        cwd=str(BASE_DIR), capture_output=True, text=True)
    node_ids = res.stdout.lower()
    assert res.returncode == 0, f"collection failed:\n{res.stdout}\n{res.stderr}"
    missing = [inv for inv in INVARIANT_IDS if inv not in node_ids]
    assert not missing, f"invariants with no covering test: {missing}"
    assert "g4" in node_ids, "the G4 convention check has no covering test"
