"""
=============================================================================
SCRIPT NAME: scripts/discovery_triage/lab_session.py
=============================================================================

DESCRIPTION:
The quarantined Discovery Lab (FuguPRD §9). A real current Claude model is given
a TOOL-ENFORCED outcome-blind snapshot (loaded via surface_loader from the loop DB,
read-only) and asked to emit DRAFTS ONLY — cross-surface contradictions / detector
drafts / mechanism graphs — each carrying a falsification block and a self-
falsification block. The Lab never sees forward returns, harness verdicts, PnL, or
the combiner; the snapshot is built by the code-level allowlist, not a prompt.

Discipline enforced here:
- A research LOOK is recorded (what surfaces were seen, model id/cutoff) BEFORE drafts.
- Every draft links to that source_look_id (no draft without a look).
- The model's output passes a language gate (no validation vocab, FuguPRD §24).
- Every card is tagged with its certification route from the provenance classifier;
  with a null model cutoff, historical ideas route prospective-only (the safe default).

The Anthropic client and the snapshot are INJECTABLE so the Lab is unit-tested
offline (no API spend, no DB). The real run builds both from the environment.

INPUT FILES:
- config/discovery_triage.yaml (per-search allowed_surfaces)
- config/model_registry.yaml   (model training cutoff)
- Data/loop/asado_loop.duckdb  (read-only) for the outcome-blind snapshot
- SAKANA/ANTHROPIC key: env ANTHROPIC_API_KEY, else AAA Backup/.env.txt
OUTPUT FILES (append-only):
- .../journal/looks/research_looks.jsonl
- .../journal/drafts/detector_drafts.jsonl + per-object <DRAFT_ID>.yaml

VERSION: 1.0 (PR-5)
LAST UPDATED: 2026-06-25
AUTHOR: Arjun Divecha (built with Claude Code)

DEPENDENCIES: anthropic>=0.40, pyyaml, duckdb (only for the real snapshot)
=============================================================================
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Optional

import yaml

from . import schemas
from .classify_provenance import classify
from .jsonl_store import append_with_minted_id, now_iso
from .paths import DETECTOR_DRAFTS, DISCOVERY_CONFIG, DRAFTS_DIR, RESEARCH_LOOKS
from .record_look import record_look
from .surface_loader import check_surface, load_country_snapshot

DEFAULT_MODEL = "claude-opus-4-8"

# FuguPRD §24 forbidden vocabulary — the Lab emits drafts, never validation claims.
_FORBIDDEN = re.compile(
    r"validated alpha|proven signal|promoted by mythos|trade recommendation|"
    r"high[- ]confidence opportunity|clean historical certification", re.IGNORECASE
)

SYSTEM_PROMPT = (
    "You are a quarantined research physicist inside ASADO's Discovery Lab. You are shown an "
    "OUTCOME-BLIND, point-in-time snapshot of cross-country state surfaces. You DO NOT see "
    "forward returns, PnL, harness verdicts, optimizer outputs, or any realized outcome.\n\n"
    "Your job is to emit DRAFTS ONLY — non-obvious, falsifiable hypotheses about where price may "
    "not yet reflect what the data shows. You may NOT claim anything is validated, proven, a trade "
    "recommendation, or a high-confidence opportunity. Every card MUST include a concrete "
    "falsification block and a self-falsification block (your strongest objection, the easiest way "
    "this is leakage, the first probe to run, and the condition under which you would abandon it).\n\n"
    "Emit 1-6 cards via the emit_discovery_cards tool. Be specific and cite the snapshot."
)

CARD_TOOL = {
    "name": "emit_discovery_cards",
    "description": "Emit 1-6 outcome-blind discovery drafts (never validated claims).",
    "input_schema": {
        "type": "object",
        "properties": {
            "cards": {
                "type": "array", "minItems": 1, "maxItems": 6,
                "items": {
                    "type": "object",
                    "properties": {
                        "object_type": {"type": "string",
                                        "enum": ["contradiction_card", "detector_family_draft", "mechanism_graph"]},
                        "entity": {"type": "string", "description": "country or family name"},
                        "summary": {"type": "string", "description": "the non-obvious observation/idea"},
                        "falsification": {
                            "type": "object",
                            "properties": {"near_term": {"type": "array", "items": {"type": "string"}},
                                           "structural": {"type": "array", "items": {"type": "string"}},
                                           "data_quality": {"type": "array", "items": {"type": "string"}}},
                            "required": ["near_term"],
                        },
                        "mythos_self_falsification": {
                            "type": "object",
                            "properties": {"strongest_objection": {"type": "string"},
                                           "easiest_way_this_is_leakage": {"type": "string"},
                                           "first_probe_to_run": {"type": "string"},
                                           "condition_under_which_i_would_abandon_this": {"type": "string"}},
                            "required": ["strongest_objection", "easiest_way_this_is_leakage",
                                         "first_probe_to_run", "condition_under_which_i_would_abandon_this"],
                        },
                    },
                    "required": ["object_type", "entity", "summary", "falsification", "mythos_self_falsification"],
                },
            }
        },
        "required": ["cards"],
    },
}


def _searches() -> dict[str, dict[str, Any]]:
    cfg = yaml.safe_load(DISCOVERY_CONFIG.read_text()) or {}
    return {s["id"]: s for s in cfg.get("discovery_searches", [])}


def _load_key() -> str:
    # 1) explicit override always wins.
    if os.environ.get("ASADO_ANTHROPIC_KEY"):
        return os.environ["ASADO_ANTHROPIC_KEY"].strip()
    # 2) the project key file is preferred over ambient env: a stale shell
    #    ANTHROPIC_API_KEY has caused failures in ASADO/Opus runs before (Codex review).
    for p in (Path("/Users/arjundivecha/Dropbox/AAA Backup/.env.txt"),):
        if p.exists():
            for line in p.read_text().splitlines():
                if line.strip().startswith("ANTHROPIC_API_KEY") and "=" in line:
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    # 3) fall back to ambient env.
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"].strip()
    raise RuntimeError(
        "No Anthropic key found (ASADO_ANTHROPIC_KEY, project .env.txt, or env) — FAIL IS FAIL."
    )


def _build_client():
    import anthropic
    return anthropic.Anthropic(api_key=_load_key())


def _extract_cards(response: Any) -> list[dict[str, Any]]:
    """Pull the emit_discovery_cards tool input from a messages.create response."""
    for block in getattr(response, "content", []) or []:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == "emit_discovery_cards":
            cards = (block.input or {}).get("cards", [])
            if isinstance(cards, str):  # defensive: model occasionally stringifies the array
                try:
                    cards = json.loads(cards)
                except json.JSONDecodeError:
                    return []
            return [c for c in cards if isinstance(c, dict)] if isinstance(cards, list) else []
    return []


def _round(v: Any) -> Any:
    try:
        return round(float(v), 4)
    except (TypeError, ValueError):
        return v


def compact_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Shrink the raw snapshot to a compact, model-friendly per-country view.
    Tidy (variable,value) surfaces become {country: {variable: value}}; wide
    surfaces become {country: {field: value}} with *_json fields parsed."""
    out: dict[str, Any] = {}
    for table, rows in snapshot.items():
        if rows and "variable" in rows[0] and "value" in rows[0]:
            by: dict[str, Any] = {}
            for r in rows:
                by.setdefault(r.get("country"), {})[r.get("variable")] = _round(r.get("value"))
            out[table] = by
        else:
            by = {}
            for r in rows:
                rec: dict[str, Any] = {}
                for k, v in r.items():
                    if k in ("date", "country"):
                        continue
                    if isinstance(v, str) and k.endswith("_json"):
                        try:
                            v = json.loads(v)
                        except json.JSONDecodeError:
                            pass
                    rec[k] = v
                by[r.get("country")] = rec
            out[table] = by
    return out


def run_lab_session(
    search_id: str,
    as_of: str,
    *,
    client: Any = None,
    snapshot: Optional[dict[str, Any]] = None,
    con: Any = None,
    model_id: str = DEFAULT_MODEL,
    model_cutoff: Optional[str] = None,
    max_tokens: int = 8000,
    looks_path: Path = RESEARCH_LOOKS,
    drafts_path: Path = DETECTOR_DRAFTS,
    drafts_dir: Path = DRAFTS_DIR,
) -> dict[str, Any]:
    """Run one outcome-blind discovery search; record a look, emit + persist drafts.
    Returns {look_id, drafts, dropped}. `client`/`snapshot` are injectable for tests."""
    searches = _searches()
    if search_id not in searches:
        raise ValueError(f"unknown search {search_id!r}; known: {sorted(searches)}")
    allowed = list(searches[search_id].get("allowed_surfaces", []))
    for s in allowed:
        check_surface(s)  # belt-and-suspenders: the search's surfaces must all be allowed

    # 1) outcome-blind snapshot (tool-enforced; never forward returns)
    if snapshot is None:
        snapshot = load_country_snapshot(as_of, allowed, con=con)

    # 2) record the LOOK before any draft exists
    look_id, _ = record_look(
        actor=model_id, purpose=search_id, visibility_mode="tool_outcome_blind",
        model={"model_id": model_id, "training_cutoff": model_cutoff},
        surfaces_seen=allowed,
        surfaces_forbidden=["forward_returns", "harness_results", "factor_returns_daily",
                            "combiner_scores_daily"],
        looks_path=looks_path,
    )

    # 3) call the model behind the outcome-blind context
    client = client or _build_client()
    compact = compact_snapshot(snapshot)
    user = (f"Discovery search: {searches[search_id].get('label', search_id)}\n"
            f"as_of: {as_of}\nallowed_surfaces: {allowed}\n\n"
            f"OUTCOME-BLIND SNAPSHOT (latest per country, date <= as_of):\n"
            f"{json.dumps(compact, default=str)[:45000]}")
    response = client.messages.create(
        model=model_id, max_tokens=max_tokens, system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user}],
        tools=[CARD_TOOL], tool_choice={"type": "tool", "name": "emit_discovery_cards"},
    )
    cards = _extract_cards(response)
    _u = getattr(response, "usage", None)
    usage = {"input_tokens": getattr(_u, "input_tokens", None),
             "output_tokens": getattr(_u, "output_tokens", None)} if _u else None

    # 4) provenance route for these LLM ideas (forward window => prospective-only by default)
    route = classify(generator_type="llm", visibility_mode="tool_outcome_blind",
                     model_id=model_id, certification_window_start=as_of,
                     tool_enforced_outcome_blind=True)["certification_route"]
    epistemic = ["unvalidated", "tool_outcome_blind", route]

    drafts: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for card in cards:
        text = f"{card.get('summary', '')} {json.dumps(card.get('falsification', {}))}"
        if _FORBIDDEN.search(text):
            dropped.append({"reason": "forbidden_vocabulary", "entity": card.get("entity")})
            continue
        if not card.get("falsification") or not card.get("mythos_self_falsification"):
            dropped.append({"reason": "missing_falsification_block", "entity": card.get("entity")})
            continue

        def build(draft_id: str, _card=card) -> dict[str, Any]:
            return {
                "object_type": "detector_family_draft",  # the journal draft envelope
                "card_type": _card.get("object_type"),    # the card's semantic type
                "draft_id": draft_id,
                "family_name": _card.get("entity", "unknown"),
                "members": [_card.get("summary", "")[:240]],
                "source_look_id": look_id,
                "certification_route": route,
                "epistemic_status": epistemic,
                "falsification": _card.get("falsification"),
                "mythos_self_falsification": _card.get("mythos_self_falsification"),
                "card": _card,  # keep the full card for the docket/cockpit
            }

        draft_id, record = append_with_minted_id(
            drafts_path, "DRAFT", "draft_id", build,
            validate=schemas.validator_for("detector_draft"),
        )
        drafts_dir.mkdir(parents=True, exist_ok=True)
        (drafts_dir / f"{draft_id}.yaml").write_text(yaml.safe_dump(record, sort_keys=False),
                                                     encoding="utf-8")
        drafts.append(record)

    return {"look_id": look_id, "drafts": drafts, "dropped": dropped,
            "route": route, "n_cards": len(cards), "usage": usage}
