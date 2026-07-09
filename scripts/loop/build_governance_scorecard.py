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
  - cross_source_minimal is STATUS-DRIVEN: green when all configured cross-source
    checks pass AND coverage is substantially complete (>=90% of critical mapped
    series); amber on partial coverage or a soft pair discrepancy; red on a hard
    sentinel breach. (Phase-C widens the check set; it does not gate green.)
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


def _git(*args: str) -> "str | None":
    """Run git, returning stripped stdout on success or None on ANY failure
    (non-zero exit, missing binary, timeout, held index.lock). None is
    distinct from '' (a clean/empty-but-successful result) so callers can tell
    'git said nothing' apart from 'git could not run' — the latter must never
    read as a clean tree (gov-git-empty-on-failure-silent)."""
    try:
        r = subprocess.run(["git", *args], cwd=str(BASE_DIR),
                           capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout.strip() if r.returncode == 0 else None


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
    from scripts.duckdb_lock_guard import guarded_connect
    # Acquire via the shared lock guard: it clears killable ~/.claude-science
    # squatters and waits out legitimate holders, raising only if still locked
    # at the (deliberately short) budget — this is a fast scorecard dimension.
    con = None
    try:
        con = guarded_connect(LOOP_DB, read_only=True, wait_budget_s=20)
    except Exception as exc:  # noqa: BLE001 — could not acquire: transient lock/IO
        # Could not verify — don't false-red a possible ledger leak, don't hang.
        return "amber", "live_signals", f"could not verify (transient lock/IO): {exc}"
    try:
        bad = con.execute("SELECT count(*) FROM live_signals WHERE status IN ('retired','rejected')").fetchone()[0]
        resurrected = con.execute("SELECT count(*) FROM live_signals WHERE hypothesis_id='H_20260610_001'").fetchone()[0]
    except Exception as exc:  # noqa: BLE001
        # schema drift / query error — a real problem, not transient lock.
        # FAIL-IS-FAIL: do NOT downgrade a possible ledger leak to amber.
        return "red", "live_signals", f"ledger check error: {exc}"
    finally:
        try:
            con.close()
        except Exception:  # noqa: BLE001
            pass
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


# Fraction of critical mapped series that must be cross-checked to earn GREEN.
# Below this the dimension is AMBER (partial coverage), not because coverage is
# "minimal by design" but because we genuinely haven't validated enough series.
CROSS_SOURCE_GREEN_COVERAGE = 0.90


def _dim_cross_source_minimal():
    """STATUS-DRIVEN (no longer amber-by-design):
      red    -> a hard sentinel breach (two sources disagree on a critical price)
      amber  -> a soft pair discrepancy, OR coverage below the green threshold
      green  -> all configured cross-source checks pass AND coverage is
                substantially complete (>= CROSS_SOURCE_GREEN_COVERAGE)
      blind  -> the check did not run
    Phase-C will widen the *set* of checks; it does not gate green here. Green
    means 'everything I currently cross-check agrees and I checked enough of it.'
    """
    st = _read_json(GOV_DIR / "cross_source_status.json")
    if st is None:
        return "blind", "cross_source_status.json", "not run"
    cov = float(st.get("coverage_fraction") or 0.0)
    n, tot = st.get("n_checked", 0), st.get("critical_series_count", 0)
    if st.get("hard_breach"):
        return "red", "cross_source_status.json", f"hard sentinel breach: {st.get('sentinel_breaches')}"
    if st.get("pair_breach"):
        return "amber", "cross_source_status.json", f"pair discrepancy flagged; coverage {n}/{tot}"
    if cov < CROSS_SOURCE_GREEN_COVERAGE:
        return "amber", "cross_source_status.json", \
            f"partial coverage {n}/{tot} ({cov:.0%} < {CROSS_SOURCE_GREEN_COVERAGE:.0%} needed for green)"
    return "green", "cross_source_status.json", \
        f"all cross-source checks pass; coverage {n}/{tot} ({cov:.0%})"


def _dim_config_guard():
    dirty = []
    for tr in TRUST_ROOTS:
        out = _git("status", "--porcelain", "--", tr)
        if out is None:
            # git itself could not run — we have NOT verified the trust roots;
            # honour the BLIND-never-green invariant and red the dimension.
            return "red", "git", "config guard could not run (git unavailable / index.lock)"
        if out:
            dirty.append(tr)
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


def _degraded_scorecard(reason: str) -> dict:
    """Schema-valid RED scorecard emitted when the contract itself cannot be
    trusted (missing/truncated/malformed, or it fails to cover the checks we
    know how to run). Forcing RED — never green — preserves the 'knows what it
    doesn't know' invariant: if the contract is unreadable we have verified
    NOTHING, and must not report a confident green."""
    return {
        "schema_version": 1,
        "producer_version": "build_governance_scorecard.py 1.0",
        "as_of": datetime.now().isoformat(timespec="seconds"),
        "contract_version": "",
        "contract_hash": "",
        "repo_sha": _git("rev-parse", "HEAD") or "",
        "repo_dirty": bool(_git("status", "--porcelain")),
        "overall": "red",
        "dimensions_expected": sorted(CHECKS),
        "dimensions_computed": [],
        "dimensions": [{
            "name": "contract_degraded", "owner_item": "A8",
            "severity": "red", "amber_by_design": False,
            "status": "red", "effective": "red",
            "evidence": "governance_contract.yaml", "detail": reason,
        }],
    }


def build_scorecard() -> dict:
    # CRITICAL (gov-empty-contract-green): a truncated/malformed/empty contract
    # must NOT green the board. Read defensively and validate coverage against
    # the CHECKS dict (the floor is derived from code, not a second literal, so
    # the two cannot silently drift).
    try:
        raw = CONTRACT_PATH.read_bytes()
        contract = yaml.safe_load(raw) or {}
    except (OSError, yaml.YAMLError) as e:
        return _degraded_scorecard(f"contract unreadable/malformed: {e}")
    expected = contract.get("scorecard_dimensions") or []
    expected_names = {s.get("name") for s in expected if isinstance(s, dict)}
    if not expected or not expected_names.issuperset(CHECKS):
        missing = sorted(set(CHECKS) - expected_names)
        return _degraded_scorecard(
            f"contract does not cover known checks {missing or 'ALL'} "
            "— refusing to report green on an incomplete contract")
    contract_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
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
        "repo_sha": _git("rev-parse", "HEAD") or "",
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
    import re
    briefs = [Path(p) for p in globmod.glob(str(BRIEF_DIR / "brief_*.md"))
              if os.path.isfile(p) and "conflicted copy" not in p.lower()]
    if not briefs:
        return None
    brief = max(briefs, key=lambda p: p.stat().st_mtime)
    body = brief.read_text()
    # Idempotent + self-healing: strip any well-formed prior block, THEN strip
    # any orphan marker left by an interrupted prepend (the START-without-END
    # corruption case the old paired-split could not remove and would stack on).
    body = re.sub(re.escape(MARK_START) + r".*?" + re.escape(MARK_END), "",
                  body, flags=re.DOTALL)
    body = body.replace(MARK_START, "").replace(MARK_END, "").lstrip("\n")
    # Atomic write (temp + rename in the same dir), mirroring the JSON write so a
    # kill mid-write cannot truncate the git-tracked brief.
    tmp = brief.with_suffix(".md.tmp")
    tmp.write_text(md + body)
    os.replace(tmp, brief)
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
