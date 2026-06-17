#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: family_registry.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/family_registry.yaml
  The canonical research families (variable-prefix -> family).

OUTPUT FILES: none (pure resolver library).

VERSION: 1.0
LAST UPDATED: 2026-06-17
AUTHOR: Arjun Divecha (built by agent session, Governance Layer PRD v1.2, item A5)

DESCRIPTION:
A5 — canonical family resolver. The family a hypothesis belongs to (and the
deflated-Sharpe trial count N it is charged against) is determined by its
SIGNAL VARIABLE, not a free-text family_key. resolve_family() matches the
variable against the longest registered prefix and RAISES if none matches, so
every new mechanism must be deliberately classified in the trust-root YAML.

DEPENDENCIES:
- pyyaml (project venv)

USAGE:
  from scripts.loop.family_registry import resolve_family
  resolve_family("GRAPHP_TRADE_NBR_RET_GAP_21D")  # -> "network_spillover"
  python scripts/loop/family_registry.py --list   # print the registry
=============================================================================
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
REGISTRY_PATH = BASE_DIR / "config" / "family_registry.yaml"

_CACHE: Optional[dict] = None


class UnclassifiedVariableError(ValueError):
    """A signal variable matches no registered family — classify it in
    config/family_registry.yaml before registering a hypothesis on it."""


def load_registry(path: Path = REGISTRY_PATH) -> dict:
    """Load + validate the registry. The default path is cached; an explicit
    path (tests) is read fresh each call."""
    global _CACHE
    if path == REGISTRY_PATH and _CACHE is not None:
        return _CACHE
    data = yaml.safe_load(path.read_text())
    if not data or "families" not in data:
        raise ValueError(f"{path} missing 'families'")
    if path == REGISTRY_PATH:
        _CACHE = data
    return data


def _prefix_map(registry: dict) -> list[tuple[str, str]]:
    """(prefix, family) pairs, longest prefix first so the match is unambiguous."""
    pairs = []
    for fam, spec in registry["families"].items():
        for pre in spec.get("variable_prefixes", []):
            pairs.append((pre, fam))
    return sorted(pairs, key=lambda p: -len(p[0]))


def resolve_family(variable: str, registry: Optional[dict] = None) -> str:
    """Return the canonical family for a signal variable. Raises
    UnclassifiedVariableError if no registered prefix matches."""
    reg = registry or load_registry()
    if not variable:
        raise UnclassifiedVariableError("empty signal variable cannot be classified")
    for prefix, family in _prefix_map(reg):
        if variable.startswith(prefix):
            return family
    raise UnclassifiedVariableError(
        f"signal variable {variable!r} matches no family in config/family_registry.yaml — "
        f"add a variable_prefix for it before registering (trial accounting depends on it)")


def main() -> int:
    ap = argparse.ArgumentParser(description="Canonical research family registry (A5).")
    ap.add_argument("--list", action="store_true", help="Print the registry.")
    ap.add_argument("--resolve", default=None, help="Resolve a single variable.")
    args = ap.parse_args()
    if args.resolve:
        print(resolve_family(args.resolve))
        return 0
    reg = load_registry()
    print(f"family_registry v{reg.get('version')} — {len(reg['families'])} families")
    for fam, spec in reg["families"].items():
        print(f"  {fam:22} <- {spec.get('variable_prefixes')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
