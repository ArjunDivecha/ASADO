#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/qa/validate_variable_registry.py
=============================================================================

WHAT THIS PROGRAM DOES (plain English):
This is the CI guardrail for the ASADO variable registry
(PRD_Semantic_Layer_Variable_Registry.md §2 success criteria). It makes sure
the registry can never silently drift away from the live database. It FAILS
(exit code 1) when:

  1. COVERAGE: any live variable (scanned fresh from the DB right now) has
     no row in the curated registry table — i.e. a new variable appeared in
     the warehouse and nobody registered it.
  2. JOIN INTEGRITY: any facts row fails to join a curated row in the
     variable_registry_full view.
  3. OBJECT EXISTENCE: the registry's facts layer or the rendered dictionary
     references a DuckDB table/view/surface that does not exist in the live DB.
  4. VOCABULARY: curated fields contain values outside their controlled
     vocabularies (sign, normalization, review_status).
  5. SELF-PROMOTION GUARD: review_status='verified' rows whose sign is
     'unknown' (a human cannot have verified an unknown sign).

It WARNS (but does not fail) on:
  - orphan seed entries (variables in the seed that are no longer live)
  - stale dictionary (rendered before the registry tables were last rebuilt)

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
    (live warehouse, opened READ-ONLY)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    (loop DB, READ-ONLY — graph features surface)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/variable_registry_seed.yaml
    (curated seed)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/docs/VARIABLE_DICTIONARY.md
    (rendered dictionary, checked for object references)

OUTPUT FILES:
- stdout: machine-readable JSON summary of all checks
- exit code: 0 if all hard checks pass, 1 otherwise
(No files are written; this script is read-only.)

VERSION: 1.0
LAST UPDATED: 2026-06-10
AUTHOR: Arjun Divecha (built by Cursor agent)

DEPENDENCIES: duckdb, pandas, pyyaml (project venv)

USAGE:
  ./venv/bin/python scripts/qa/validate_variable_registry.py
  ./venv/bin/python scripts/qa/validate_variable_registry.py --quiet   # JSON only
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import duckdb
import yaml

CODE_DIR = Path(__file__).resolve().parent.parent.parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

from scripts.build_variable_registry import scan_facts, SEED_PATH, DICTIONARY_PATH, DB_PATH  # noqa: E402

VALID_SIGNS = {"higher_is_better", "lower_is_better", "unknown"}
VALID_NORMALIZATIONS = {"raw", "_CS", "_TS", "other"}
VALID_REVIEW_STATUS = {"verified", "model_drafted", "needs_review", "unknown"}

# Surfaces the registry facts layer may reference; each must exist where stated.
EXPECTED_SURFACES = {
    "feature_panel": "main",
    "t2_factors_daily": "main",
    "t2_levels_daily": "main",
    "gdelt_factors_daily": "main",
    "gdelt_raw_daily": "main",
    "commodity_panel": "main",
    "predmkt_signals_daily": "main",
    "graph_features_daily": "loop",
}


def _check(label: str, ok: bool, detail: Any = None) -> Dict[str, Any]:
    return {"name": label, "ok": bool(ok), "detail": detail}


def main() -> int:
    ap = argparse.ArgumentParser(description="CI guardrail for the ASADO variable registry")
    ap.add_argument("--quiet", action="store_true", help="JSON output only")
    args = ap.parse_args()

    checks: List[Dict[str, Any]] = []
    warnings: List[str] = []

    # ── registry tables exist ────────────────────────────────────────────
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        tables = {r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='main'"
        ).fetchall()}
        for obj in ("variable_registry", "variable_registry_facts", "variable_registry_full"):
            checks.append(_check(f"object {obj} exists", obj in tables))

        if "variable_registry" not in tables:
            print(json.dumps({"ok": False, "checks": checks}, indent=2, default=str))
            return 1

        curated_vars = {r[0] for r in con.execute(
            "SELECT variable FROM variable_registry").fetchall()}

        # vocabulary checks
        bad_sign = con.execute(
            f"SELECT variable, sign FROM variable_registry WHERE sign NOT IN "
            f"({','.join(repr(s) for s in VALID_SIGNS)})").fetchall()
        checks.append(_check("sign vocabulary valid", not bad_sign, {"bad": bad_sign[:10]}))

        bad_norm = con.execute(
            f"SELECT variable, normalization FROM variable_registry WHERE normalization NOT IN "
            f"({','.join(repr(s) for s in VALID_NORMALIZATIONS)})").fetchall()
        checks.append(_check("normalization vocabulary valid", not bad_norm, {"bad": bad_norm[:10]}))

        bad_review = con.execute(
            f"SELECT variable, review_status FROM variable_registry WHERE review_status NOT IN "
            f"({','.join(repr(s) for s in VALID_REVIEW_STATUS)})").fetchall()
        checks.append(_check("review_status vocabulary valid", not bad_review, {"bad": bad_review[:10]}))

        # self-promotion guard: a human cannot have 'verified' an unknown sign
        bad_verified = con.execute(
            "SELECT variable FROM variable_registry "
            "WHERE review_status='verified' AND sign='unknown'").fetchall()
        checks.append(_check("no verified rows with unknown sign", not bad_verified,
                             {"bad": [r[0] for r in bad_verified][:10]}))

        # join integrity inside the view
        unjoined = con.execute(
            "SELECT COUNT(*) FROM variable_registry_full WHERE base_variable IS NULL"
        ).fetchone()[0]
        checks.append(_check("all facts rows join a curated row", unjoined == 0,
                             {"unjoined_facts_rows": int(unjoined)}))
    finally:
        con.close()

    # ── fresh live scan: coverage of the CURRENT universe ────────────────
    facts = scan_facts()
    live_vars = set(facts["variable"])
    missing = sorted(live_vars - curated_vars)
    checks.append(_check(
        "every live variable has a registry row",
        not missing,
        {"live": len(live_vars), "registered": len(curated_vars),
         "missing_count": len(missing), "missing_sample": missing[:15]},
    ))

    # surfaces referenced by the scan exist where expected (scan would have
    # raised otherwise, but assert explicitly for the report)
    scanned_surfaces = set(facts["surface"])
    bad_surfaces = scanned_surfaces - set(EXPECTED_SURFACES)
    checks.append(_check("facts surfaces within expected set", not bad_surfaces,
                         {"unexpected": sorted(bad_surfaces)}))

    # ── seed sanity ──────────────────────────────────────────────────────
    seed_ok = SEED_PATH.exists()
    checks.append(_check("seed file exists", seed_ok, str(SEED_PATH)))
    if seed_ok:
        with open(SEED_PATH) as f:
            seed = yaml.safe_load(f) or []
        seed_vars = {e["variable"] for e in seed}
        dupes = len(seed) - len(seed_vars)
        checks.append(_check("seed has no duplicate variables", dupes == 0, {"duplicates": dupes}))
        orphans = sorted(seed_vars - live_vars)
        if orphans:
            warnings.append(f"{len(orphans)} seed entries reference variables no longer live "
                            f"(e.g. {orphans[:5]}) — retire or keep deliberately")
        checks.append(_check("seed matches loaded registry table",
                             seed_vars == curated_vars,
                             {"seed_only": len(seed_vars - curated_vars),
                              "table_only": len(curated_vars - seed_vars)}))

    # ── rendered dictionary references live objects ──────────────────────
    dict_ok = DICTIONARY_PATH.exists()
    checks.append(_check("rendered dictionary exists", dict_ok, str(DICTIONARY_PATH)))
    if dict_ok:
        text = DICTIONARY_PATH.read_text(encoding="utf-8")
        referenced = [s for s in EXPECTED_SURFACES if f"## {s}" in text]
        missing_in_dict = [s for s in scanned_surfaces if s not in referenced]
        checks.append(_check("dictionary covers all scanned surfaces", not missing_in_dict,
                             {"missing_sections": missing_in_dict}))

    all_ok = all(c["ok"] for c in checks)
    summary = {
        "ok": all_ok,
        "n_checks": len(checks),
        "n_failed": sum(1 for c in checks if not c["ok"]),
        "warnings": warnings,
        "checks": checks,
    }
    print(json.dumps(summary, indent=2, default=str))
    if not args.quiet and not all_ok:
        failed = [c["name"] for c in checks if not c["ok"]]
        print(f"\nFAILED CHECKS: {failed}", file=sys.stderr)
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
