#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: family_migration.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/ledgers/hypothesis_ledger.jsonl
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/family_registry.yaml

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/governance/family_migration_diff.json
  Per-hypothesis old family_key -> canonical family, and old_N -> new_N per
  family. Analytical (NO backtest re-run): it documents exactly how the
  deflated-Sharpe trial count N changes under the canonical families.

VERSION: 1.0
LAST UPDATED: 2026-06-17
AUTHOR: Arjun Divecha (built by agent session, Governance Layer PRD v1.2, item A5)

DESCRIPTION:
A5 migration diff. Maps every existing hypothesis from its old free-text
family_key to the canonical, variable-derived family, and recomputes the
trial charge N for both. Charge is CONSERVED (every trial accounted for
exactly once) — the diff only RE-GROUPS trials, it never adds or drops them.
The actual in-place deflated-Sharpe RE-VERDICT (re-running the harness under
the corrected N) is a separate, heavier step intentionally NOT done here.

DEPENDENCIES:
- (project venv)

USAGE:
  python scripts/loop/family_migration.py            # write the diff + print summary
=============================================================================
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.loop import ledgers
from scripts.loop.family_registry import load_registry
from scripts.loop.loopdb import LOOP_DIR

OUT_PATH = LOOP_DIR / "governance" / "family_migration_diff.json"


def build_diff() -> dict:
    hyps = ledgers.fold_hypotheses()
    per_hyp = []
    old_charge: dict[str, float] = defaultdict(float)
    new_charge: dict[str, float] = defaultdict(float)
    mapping: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for h in hyps.values():
        old_fam = h.get("family_key", "?")
        new_fam = ledgers.canonical_family_of(h)
        charge = ledgers._trial_charge(h)
        var = (h.get("signal_spec") or {}).get("variable", "")
        per_hyp.append({
            "hypothesis_id": h["hypothesis_id"], "variable": var,
            "old_family": old_fam, "canonical_family": new_fam,
            "verdict": h.get("verdict"), "trial_charge": charge,
        })
        old_charge[old_fam] += charge
        new_charge[new_fam] += charge
        mapping[old_fam][new_fam] += 1

    def _n(d: dict[str, float]) -> dict[str, int]:
        return {k: max(1, int(round(v))) for k, v in sorted(d.items())}

    total_charge = sum(old_charge.values())
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "registry_version": str(load_registry().get("version")),
        "n_hypotheses": len(hyps),
        "total_trial_charge": round(total_charge, 1),
        "charge_conserved": round(sum(old_charge.values()), 6) == round(sum(new_charge.values()), 6),
        "old_family_N": _n(old_charge),
        "canonical_family_N": _n(new_charge),
        "family_mapping": {k: dict(v) for k, v in sorted(mapping.items())},
        "per_hypothesis": sorted(per_hyp, key=lambda r: r["hypothesis_id"]),
    }


def write_diff(out_path: Path = OUT_PATH) -> dict:
    diff = build_diff()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(diff, indent=2, default=str))
    os.replace(tmp, out_path)
    return diff


def main() -> int:
    d = write_diff()
    print(f"family migration: {d['n_hypotheses']} hypotheses, "
          f"charge_conserved={d['charge_conserved']} (total={d['total_trial_charge']})")
    print("  OLD family_key -> N        CANONICAL family -> N")
    print(f"  {'old':28} {'N':>4}    {'canonical':22} {'N':>4}")
    for fam, sub in d["family_mapping"].items():
        canon = ", ".join(f"{c}({n})" for c, n in sub.items())
        print(f"  {fam:28} {d['old_family_N'].get(fam, 0):>4}    -> {canon}")
    print("\n  Canonical N (the honest deflated-Sharpe denominators):")
    for c, n in d["canonical_family_N"].items():
        print(f"    {c:22} N={n}")
    print(f"\nWrote {OUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
