#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: build_governance_scorecard.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/governance_contract.yaml
  (the SINGLE source of truth for dimensions_expected — A1)
- Data/loop/governance/run_manifest.json (A1), heartbeat.json (A2),
  cross_source_status.json (A7)  [each may be absent -> that dimension is BLIND]
- config/family_registry.yaml (A5), config/pit_proof_registry.yaml (A6)
- Data/loop/asado_loop.duckdb (read-only; ledger_integrity)

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/governance/governance_scorecard.json
- a GOVERNANCE-SCORECARD markdown block prepended to the newest
  Data/dislocations/brief_*.md (light mode).

VERSION: 1.0
LAST UPDATED: 2026-06-17
AUTHOR: Arjun Divecha (built by agent session, Governance Layer PRD v1.2, item A8)

DESCRIPTION:
A8 — the keystone. Collapses every governance check into ONE scorecard the
Chief-of-Staff agent reads and the human sees atop the brief. The dimensions
are read from the A1 contract (NOT a separate hand list) so the two trust
lists cannot drift; the contract hash + repo SHA + dirty flag are stamped.

Two non-negotiable rules (the "knows what it doesn't know" property):
  - any expected dimension not computed -> BLIND (amber/red per its severity),
    NEVER green.
  - any partial-coverage dimension (cross_source_minimal) -> AMBER, never green
    in Phase A; so overall caps at amber until the Phase-C full sweep.
  - CONFIG GUARD: an uncommitted/dirty trust-root YAML -> config_guard RED.

DEPENDENCIES:
- duckdb, pyyaml (project venv)

USAGE:
  python scripts/loop/build_governance_scorecard.py
=============================================================================
"""

from __future__ import annotations

import glob as globmod
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.loop.loopdb import BASE_DIR, BRIEF_DIR, LOOP_DB, LOOP_DIR

GOV_DIR = LOOP_DIR / "governance"
CONTRACT_PATH = BASE_DIR / "config" / "governance_contract.yaml"
SCORECARD_PATH = GOV_DIR / "governance_scorecard.json"
TRUST_ROOTS = ["config/governance_contract.yaml", "config/family_registry.yaml",
               "config/pit_proof_registry.yaml", "config/cross_source.yaml"]
MARK_START = "<!-- GOVERNANCE_SCORECARD_START -->"
MARK_END = "<!-- GOVERNANCE_SCORECARD_END -->"
GLYPH = {"green": "🟢", "amber": "🟡", "red": "🔴", "blind": "⚪"}


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=str(BASE_DIR),
                              capture_output=True, text=True).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def _read_json(p: Path) -> "dict | None":
    return json.loads(p.read_text()) if p.exists() else None


# ── per-dimension checks: return (status, evidence, detail) ──────────────────

def _dim_run_manifest():
    m = _read_json(GOV_DIR / "run_manifest.json")
    if m is None:
        return "blind", "run_manifest.json", "manifest not written"
    if m.get("fail_steps") or m.get("stale_steps") or m.get("unknown_steps"):
        return "red", "run_manifest.json", f"fail={m.get('fail_steps')} stale={m.get('stale_steps')}"
    return "green", "run_manifest.json", "all steps ok/fresh"


def _dim_liveness():
    hb = _read_json(GOV_DIR / "heartbeat.json")
    if hb is None:
        return "blind", "heartbeat.json", "heartbeat not written"
    return ("green" if hb.get("healthy") else "red"), "heartbeat.json", "; ".join(hb.get("reasons", [])) or "healthy"


def _dim_ledger_integrity():
    if not LOOP_DB.exists():
        return "blind", "asado_loop.duckdb", "loop DB absent"
    try:
        import duckdb
        con = duckdb.connect(str(LOOP_DB), read_only=True)
        bad = con.execute("SELECT count(*) FROM live_signals WHERE status IN ('retired','rejected')").fetchone()[0]
        resurrected = con.execute("SELECT count(*) FROM live_signals WHERE hypothesis_id='H_20260610_001'").fetchone()[0]
        con.close()
    except Exception as exc:  # noqa: BLE001
        return "blind", "live_signals", f"check failed: {exc}"
    if bad or resurrected:
        return "red", "live_signals", f"retired/rejected leak={bad}, H_20260610_001 present={resurrected}"
    return "green", "live_signals", "no retired/rejected in live_signals"


def _dim_family_registry():
    try:
        from scripts.loop import ledgers
        from scripts.loop.family_registry import resolve_family, UnclassifiedVariableError
        unclassified = []
        for h in ledgers.fold_hypotheses().values():
            var = (h.get("signal_spec") or {}).get("variable", "")
            try:
                resolve_family(var)
            except UnclassifiedVariableError:
                unclassified.append(var)
    except Exception as exc:  # noqa: BLE001
        return "blind", "family_registry.yaml", f"check failed: {exc}"
    if unclassified:
        return "red", "family_registry.yaml", f"unclassified variables: {sorted(set(unclassified))}"
    return "green", "family_registry.yaml", "every hypothesis variable classifies"


def _dim_pit_lag_proof():
    p = BASE_DIR / "config" / "pit_proof_registry.yaml"
    if not p.exists():
        return "blind", "pit_proof_registry.yaml", "registry absent"
    reg = yaml.safe_load(p.read_text()) or {}
    unbacked = [v for v, pr in (reg.get("proofs") or {}).items()
                if pr.get("status") == "passing" and int(pr.get("entitled_lag_days", 0)) == 0]
    if unbacked:
        return "red", "pit_proof_registry.yaml", f"unbacked lag-0 proofs: {unbacked}"
    return "green", "pit_proof_registry.yaml", "no unbacked lag-0 claims; daily defaults fail closed"


def _dim_cross_source_minimal():
    st = _read_json(GOV_DIR / "cross_source_status.json")
    if st is None:
        return "blind", "cross_source_status.json", "not run"
    if st.get("hard_breach") or st.get("pair_breach"):
        return "red", "cross_source_status.json", f"hard={st.get('hard_breach')} pair={st.get('pair_breach')}"
    # AMBER BY DESIGN — minimal coverage, never green in Phase A.
    return "amber", "cross_source_status.json", f"checks pass; coverage={st.get('coverage_fraction')} (partial by design)"


def _dim_config_guard():
    dirty = [tr for tr in TRUST_ROOTS if _git("status", "--porcelain", "--", tr)]
    if dirty:
        return "red", "git", f"uncommitted/dirty trust-roots: {dirty}"
    return "green", "git", "all trust-root YAMLs committed"


CHECKS = {
    "run_manifest": _dim_run_manifest,
    "liveness": _dim_liveness,
    "ledger_integrity": _dim_ledger_integrity,
    "family_registry": _dim_family_registry,
    "pit_lag_proof": _dim_pit_lag_proof,
    "cross_source_minimal": _dim_cross_source_minimal,
    "config_guard": _dim_config_guard,
}

_RANK = {"green": 0, "amber": 1, "blind": 2, "red": 3}


def build_scorecard() -> dict:
    raw = CONTRACT_PATH.read_bytes()
    contract = yaml.safe_load(raw)
    contract_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
    expected = contract.get("scorecard_dimensions", [])
    repo_dirty = bool(_git("status", "--porcelain"))

    dims = []
    for spec in expected:
        name = spec["name"]
        severity = spec.get("severity", "red")
        amber_by_design = bool(spec.get("amber_by_design"))
        check = CHECKS.get(name)
        if check is None:
            status, evidence, detail = "blind", "(no check)", "no check implemented"
        else:
            status, evidence, detail = check()
        # A BLIND dimension takes its severity colour (never green): the
        # scorecard knows what it failed to check.
        if status == "blind":
            effective = "red" if severity == "red" else "amber"
        else:
            effective = status
        dims.append({"name": name, "owner_item": spec.get("owner_item"),
                     "severity": severity, "amber_by_design": amber_by_design,
                     "status": status, "effective": effective,
                     "evidence": evidence, "detail": detail})

    computed = [d["name"] for d in dims if d["status"] != "blind"]
    worst = max((_RANK[d["effective"]] for d in dims), default=0)
    overall = {0: "green", 1: "amber", 2: "amber", 3: "red"}[worst]
    return {
        "schema_version": 1,
        "producer_version": "build_governance_scorecard.py 1.0",
        "as_of": datetime.now().isoformat(timespec="seconds"),
        "contract_version": str(contract.get("contract_version", "")),
        "contract_hash": contract_hash,
        "repo_sha": _git("rev-parse", "HEAD"),
        "repo_dirty": repo_dirty,
        "overall": overall,
        "dimensions_expected": [s["name"] for s in expected],
        "dimensions_computed": computed,
        "dimensions": dims,
    }


def render_markdown(sc: dict) -> str:
    lines = [MARK_START,
             f"## 🛡️ Governance scorecard — **{sc['overall'].upper()}**  ({sc['as_of']})",
             f"_contract {sc['contract_hash'][:18]}… · repo {sc['repo_sha'][:8]}"
             + ("  ⚠️ DIRTY WORKING TREE" if sc["repo_dirty"] else "") + "_",
             "",
             "| Dim | Status | Detail |", "|---|---|---|"]
    for d in sc["dimensions"]:
        blind = " (blind)" if d["status"] == "blind" else ""
        lines.append(f"| {d['name']} | {GLYPH[d['effective']]} {d['effective']}{blind} | {d['detail']} |")
    miss = set(sc["dimensions_expected"]) - set(sc["dimensions_computed"])
    if miss:
        lines.append(f"\n> ⚪ Not computed (blind): {sorted(miss)}")
    lines += ["", "_Green ⇒ trust the warehouse; amber/red ⇒ a check failed or coverage is partial._",
              MARK_END, "", ""]
    return "\n".join(lines)


def _prepend_to_brief(md: str) -> "str | None":
    briefs = [Path(p) for p in globmod.glob(str(BRIEF_DIR / "brief_*.md"))
              if os.path.isfile(p)]
    if not briefs:
        return None
    brief = max(briefs, key=lambda p: p.stat().st_mtime)
    body = brief.read_text()
    if MARK_START in body and MARK_END in body:  # idempotent: replace old block
        pre, rest = body.split(MARK_START, 1)
        _, post = rest.split(MARK_END, 1)
        body = pre + post.lstrip("\n")
    brief.write_text(md + body)
    return str(brief)


def main() -> int:
    sc = build_scorecard()
    GOV_DIR.mkdir(parents=True, exist_ok=True)
    tmp = SCORECARD_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(sc, indent=2, default=str))
    os.replace(tmp, SCORECARD_PATH)
    brief = _prepend_to_brief(render_markdown(sc))
    print(f"governance scorecard: {sc['overall'].upper()}  "
          f"({len(sc['dimensions_computed'])}/{len(sc['dimensions_expected'])} computed)")
    for d in sc["dimensions"]:
        print(f"  {GLYPH[d['effective']]} {d['name']:22} {d['effective']:6} {d['detail']}")
    print(f"Wrote {SCORECARD_PATH}" + (f"; prepended {brief}" if brief else "; no brief found"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
