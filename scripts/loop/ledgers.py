#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: ledgers.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/ledgers/hypothesis_ledger.jsonl
  Append-only event log of research hypotheses (pre-registrations, verdicts,
  status changes). Created on first registration.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/ledgers/thesis_ledger.jsonl
  Append-only event log of trade theses (opens, daily marks, closes).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/ledgers/methodology_ledger.jsonl
  Append-only event log of directory-experiment (whole-methodology, not
  single-variable) verdicts — regime/, regime_ew/, momentum_fragility/-style
  tests that live outside the single-variable harness because they're gated
  by their own PRD-defined ladder, not evaluate_signal.py. Created on first
  registration. A SEPARATE file from hypothesis_ledger.jsonl on purpose:
  fold_hypotheses() FAIL-IS-FAILs on any event type outside HYP_EVENTS, so a
  new event kind cannot be added into that file without either weakening that
  guard or crashing the nightly fold_ledgers step — this file has its own
  guard (METHODOLOGY_EVENTS) instead, isolated from the harness's
  trial-count/deflated-Sharpe machinery entirely.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb (read-only)
  t2_factors_daily 1DRet rows used for auto-marking open theses.

OUTPUT FILES:
- The three JSONL files above (append-only; nothing is ever rewritten or deleted).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
  Folded current-state tables rebuilt from the event logs on demand:
    hypothesis_ledger  - one row per hypothesis, latest state. Carries both the
                         raw `verdict` and `effective_verdict` (NULL once the
                         hypothesis is retired/rejected so a naive verdict query
                         cannot resurrect a killed hypothesis — A3).
    live_signals       - VIEW: hypothesis_ledger WHERE status NOT IN
                         ('retired','rejected'). The canonical "what is live"
                         surface (A3).
    thesis_ledger      - one row per thesis, latest state. `outcome_label` maps
                         a review-kill (killed_review) to 'void' (no Brier) so
                         the loser-prune path is auditable, never silently null.
    thesis_marks       - one row per (thesis, mark date)
    methodology_ledger - one row per directory-experiment, latest state
                         (register -> verdict, or a single backfill event for
                         a historical experiment that predates this ledger).
                         `pre_registered` is False for backfilled rows so a
                         consumer can tell genuine pre-registration proof from
                         a reconstructed historical record.

VERSION: 1.1
LAST UPDATED: 2026-07-09
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 1;
        methodology ledger added by agent session 2026-07-09)

DESCRIPTION:
The memory and honesty layer of the Alpha-Hunting Loop (PRD section 6).
Three append-only ledgers, stored as JSONL so git history is tamper evidence:

1. HYPOTHESIS LEDGER - every research idea must be pre-registered (mechanism
   written down BEFORE results are seen, hashed) and every test counts as a
   trial against its family. This is what makes the deflated Sharpe ratio
   honest: you cannot quietly test 50 variants and report the best one,
   because the ledger counted all 50.
2. THESIS LEDGER - every trade idea is opened with a frozen entry thesis,
   a stated probability, and a numeric invalidation level. A daily auto-marker
   computes cumulative return from T2 daily country returns and closes theses
   mechanically (invalidated / expired-hit / expired-miss). Stated probability
   vs outcome feeds Brier-score calibration. Hand-marking is impossible by
   construction - marks only come from the return data.
3. METHODOLOGY LEDGER - every directory-experiment (a whole modeling approach
   tested against its own PRD-defined gate ladder, not one harness variable)
   registers a hypothesis + gate ladder before results, then a verdict after.
   Extends the same pre-registration discipline as (1) to a class of research
   the hypothesis ledger structurally cannot represent (no single variable to
   resolve via family_registry.yaml). `register_methodology_experiment` /
   `attach_methodology_verdict` are for new experiments going forward;
   `backfill_methodology_verdict` is a distinct, explicitly-flagged path for
   recording a historical experiment that predates this ledger (see its
   docstring — it is NOT equivalent evidentiary weight to a real
   pre-registration and callers must not treat it as one).

Event-sourcing design: each JSONL line is an immutable event
({"event": "hyp_register" | "hyp_verdict" | "hyp_status" | "thesis_open" |
"thesis_mark" | "thesis_close" | "thesis_review" | "methodology_register" |
"methodology_verdict" | "methodology_backfill", ...}). Current state = fold
of all events. A 10th grader's version: it's a diary in pen, not pencil - you
can add new pages but never erase old ones, so your past claims stay
checkable.

DEPENDENCIES:
- duckdb, pandas (project venv)

USAGE:
 python scripts/loop/ledgers.py --rebuild       # fold JSONL -> DuckDB tables (all 3 ledgers)
 python scripts/loop/ledgers.py --list          # show current hypotheses + theses + methodology experiments
 python scripts/loop/ledgers.py --mark          # auto-mark open theses (daily job)
 # As a library:
 from scripts.loop.ledgers import register_hypothesis, open_thesis, ...

NOTES:
- IDs: H_YYYYMMDD_NNN / T_YYYYMMDD_NNN / M_YYYYMMDD_NNN, NNN increments within
  the day, independently per prefix.
- thesis direction: long / short. invalidation_level: adverse cumulative
  return in DECIMAL from entry (e.g. -0.07 = closed out if down 7% on a long).
- Outcome at close: hit=1 / miss=0; brier_contribution = (probability - outcome)^2.
- methodology verdict: DEAD / GRADUATED / WATCH / INSUFFICIENT.
  died_at_gate = the gate number it failed at, or None if it graduated (passed
  every gate in its registered ladder).
=============================================================================
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.loop.loopdb import LEDGER_DIR, T2_UNIVERSE, loop_connection
from scripts.loop.family_registry import resolve_family, UnclassifiedVariableError

HYP_PATH = LEDGER_DIR / "hypothesis_ledger.jsonl"
THESIS_PATH = LEDGER_DIR / "thesis_ledger.jsonl"
METHODOLOGY_PATH = LEDGER_DIR / "methodology_ledger.jsonl"

VALID_ARCHETYPES = {"A1", "A2", "A3", "A4", "A5", "A6", "A7", "other"}
VALID_DIRECTIONS = {"long", "short"}
VALID_METHODOLOGY_VERDICTS = {"DEAD", "GRADUATED", "WATCH", "INSUFFICIENT"}

# A3 — ledger integrity (FAIL-IS-FAIL on the reader). The fold refuses to
# silently drop an event type it does not understand.
HYP_EVENTS = {"hyp_register", "hyp_verdict", "hyp_status"}
THESIS_EVENTS = {"thesis_open", "thesis_mark", "thesis_close", "thesis_review"}
# Deliberately its OWN set, checked by its OWN fold function, in its OWN file.
# hyp_register/hyp_verdict live in hypothesis_ledger.jsonl, whose fold raises
# on anything outside HYP_EVENTS above — adding a new event kind there would
# either weaken that guard or crash the nightly fold_ledgers step the moment
# an unrecognized event appeared. Isolating this in its own file means it can
# evolve without touching the harness's trial-count/deflated-Sharpe path at all.
METHODOLOGY_EVENTS = {"methodology_register", "methodology_verdict", "methodology_backfill"}
# A hypothesis in one of these statuses is retired/rejected: its verdict must
# NOT read as "live" (the H_20260610_001 bug — a retired 12MRet look-ahead
# still folded to verdict='WATCH', so a `WHERE verdict='WATCH'` query
# resurrected it). The canonical "what is live" surface is the live_signals view.
TERMINAL_HYP_STATUSES = {"retired", "rejected"}


def effective_verdict(status: Optional[str], verdict: Optional[str]) -> Optional[str]:
    """The verdict a consumer should trust: NULL once retired/rejected so a
    naive verdict query cannot resurrect a killed hypothesis. The raw verdict
    stays in the ledger events (and family_trial_count's in-memory fold), so
    deflated-Sharpe trial accounting is unaffected."""
    return None if status in TERMINAL_HYP_STATUSES else verdict


def _outcome_label(status: Optional[str]) -> Optional[str]:
    """Auditable close label. killed_review -> 'void' (review-killed, no Brier)
    so the loser-prune path is visibly NOT a mechanical close, never silently
    null. Open theses (no close) have no label."""
    if status in ("killed_review", "void"):
        return "void"
    return status  # hit / miss / invalidated / expired / None(open)


def _session_stamp() -> dict[str, str]:
    """Who produced this entry. Stamped at register/open and IRREVERSIBLE — an
    unstamped entry is permanently un-attributable by model (A4). Under a
    rotating-frontier-model labor model, 'which model do I trust to size up?'
    is the most decision-relevant calibration axis. Agent sessions export
    ASADO_MODEL_ID / ASADO_MODEL_VERSION / ASADO_SESSION_ID; absent that,
    'unknown' (never a silent blank)."""
    return {
        "model_id": os.environ.get("ASADO_MODEL_ID", "unknown"),
        "model_version": os.environ.get("ASADO_MODEL_VERSION", "unknown"),
        "session_id": os.environ.get("ASADO_SESSION_ID", "unknown"),
    }


# ── low-level event I/O ─────────────────────────────────────────────────────

def _append_event(path: Path, event: dict[str, Any]) -> None:
    LEDGER_DIR.mkdir(parents=True, exist_ok=True)
    event = {"ts": datetime.now().isoformat(timespec="seconds"), **event}
    with path.open("a") as f:
        f.write(json.dumps(event, default=str) + "\n")


def _read_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events = []
    for i, line in enumerate(path.read_text().splitlines()):
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name} line {i + 1} is corrupt: {exc}") from exc
    return events


def _next_id(prefix: str, path: Path, key: str) -> str:
    today = date.today().strftime("%Y%m%d")
    stem = f"{prefix}_{today}_"
    existing = [
        e[key] for e in _read_events(path)
        if e.get(key, "").startswith(stem)
    ]
    nums = [int(x.rsplit("_", 1)[1]) for x in existing] or [0]
    return f"{stem}{max(nums) + 1:03d}"


# ── hypothesis ledger ───────────────────────────────────────────────────────

def register_hypothesis(
    archetype: str,
    family_key: str,
    mechanism_text: str,
    signal_spec: dict[str, Any],
    author: str = "agent",
    primary_horizon: Optional[int] = None,
) -> str:
    """Pre-register a hypothesis. Returns hypothesis_id.

    mechanism_text must be written BEFORE any results are seen - the sha256
    of (spec + mechanism) is the pre-registration proof.

    A5: the canonical family (which sets the deflated-Sharpe N) is derived from
    the signal VARIABLE via config/family_registry.yaml, not the caller's
    free-text family_key — and an unclassifiable variable RAISES. primary_horizon
    is frozen here so the verdict's gating horizon cannot be reordered later.
    """
    if archetype not in VALID_ARCHETYPES:
        raise ValueError(f"archetype must be one of {sorted(VALID_ARCHETYPES)}")
    if not mechanism_text or len(mechanism_text.split()) < 15:
        raise ValueError("mechanism_text must be a real paragraph (>= 15 words), written before results")
    if not family_key:
        raise ValueError("family_key required - it drives trial accounting")
    # A5: classify by variable (raises UnclassifiedVariableError if unknown).
    canonical_family = resolve_family(signal_spec.get("variable", ""))

    trial_index = 1 + sum(
        1 for e in _read_events(HYP_PATH)
        if e.get("event") == "hyp_register" and e.get("family_key") == family_key
    )
    hypothesis_id = _next_id("H", HYP_PATH, "hypothesis_id")
    spec_hash = hashlib.sha256(
        (json.dumps(signal_spec, sort_keys=True) + mechanism_text).encode()
    ).hexdigest()

    _append_event(HYP_PATH, {
        "event": "hyp_register",
        "hypothesis_id": hypothesis_id,
        "author": author,
        **_session_stamp(),
        "archetype": archetype,
        "family_key": family_key,
        "canonical_family": canonical_family,
        "primary_horizon": primary_horizon,
        "mechanism_text": mechanism_text,
        "signal_spec": signal_spec,
        "signal_spec_hash": spec_hash,
        "trial_index": trial_index,
        "status": "registered",
    })
    return hypothesis_id


def attach_verdict(hypothesis_id: str, verdict: str, verdict_json: dict[str, Any]) -> None:
    """Called by the harness ONLY. Appends the verdict event and status."""
    hyp = get_hypothesis(hypothesis_id)
    if hyp is None:
        raise KeyError(f"hypothesis {hypothesis_id} not registered")
    if verdict == "WATCH":
        status = "watch"
    elif verdict.startswith("INSUFFICIENT"):
        status = "tested"
    else:  # WEAK / DEAD
        status = "rejected"
    _append_event(HYP_PATH, {
        "event": "hyp_verdict",
        "hypothesis_id": hypothesis_id,
        "verdict": verdict,
        "verdict_json": verdict_json,
        "status": status,
    })


def get_hypothesis(hypothesis_id: str) -> Optional[dict[str, Any]]:
    state = fold_hypotheses()
    return state.get(hypothesis_id)


def _trial_charge(hyp: dict[str, Any]) -> float:
    """Deflated-Sharpe trial charge: 1.0 tested, 0.5 INSUFFICIENT_*, 0 untested."""
    verdict = hyp.get("verdict")
    if verdict is None:
        return 0.0
    return 0.5 if str(verdict).startswith("INSUFFICIENT") else 1.0


def canonical_family_of(hyp: dict[str, Any]) -> str:
    """The canonical family a hypothesis is charged against (A5). Variable-
    derived via config/family_registry.yaml; falls back to the raw family_key
    only for a legacy hypothesis whose variable is unclassifiable, so counting
    never crashes."""
    var = (hyp.get("signal_spec") or {}).get("variable", "")
    try:
        return resolve_family(var)
    except UnclassifiedVariableError:
        return hyp.get("family_key", "unclassified")


def family_trial_count(family: str) -> int:
    """Trials charged against a CANONICAL family (A5 — `family` is a canonical
    family name from canonical_family_of, NOT a free-text family_key). This is
    what makes the deflated-Sharpe N honest: it cannot be shrunk by splitting a
    mechanism across family_keys nor inflated by pooling distinct mechanisms."""
    count = sum(_trial_charge(h) for h in fold_hypotheses().values()
                if canonical_family_of(h) == family)
    return max(1, int(round(count)))


def fold_hypotheses(events: Optional[list[dict[str, Any]]] = None) -> dict[str, dict[str, Any]]:
    if events is None:
        events = _read_events(HYP_PATH)
    state: dict[str, dict[str, Any]] = {}
    for e in events:
        ev = e.get("event")
        if ev not in HYP_EVENTS:
            raise ValueError(
                f"unknown hypothesis event type {ev!r} (FAIL-IS-FAIL: the ledger "
                f"reader refuses to silently drop events it does not understand)")
        hid = e.get("hypothesis_id")
        if ev == "hyp_register":
            state[hid] = {k: v for k, v in e.items() if k != "event"}
        elif ev == "hyp_verdict" and hid in state:
            state[hid]["verdict"] = e["verdict"]
            state[hid]["verdict_json"] = e["verdict_json"]
            state[hid]["status"] = e["status"]
        elif ev == "hyp_status" and hid in state:
            state[hid]["status"] = e["status"]
    return state


# ── thesis ledger ───────────────────────────────────────────────────────────

def open_thesis(
    entity: str,
    direction: str,
    horizon_days: int,
    entry_thesis_text: str,
    probability: float,
    invalidation_level: float,
    catalyst: str = "",
    source_dislocation_id: str = "",
    author: str = "agent",
    paper: bool = True,
) -> str:
    """Open a thesis with a frozen entry. Returns thesis_id."""
    if entity not in T2_UNIVERSE:
        raise ValueError(f"entity must be an exact T2 country name, got {entity!r}")
    if direction not in VALID_DIRECTIONS:
        raise ValueError("direction must be long or short")
    if not (0.0 < probability < 1.0):
        raise ValueError("probability must be in (0, 1)")
    if invalidation_level >= 0:
        raise ValueError("invalidation_level is an ADVERSE cumulative return, must be negative (e.g. -0.07)")
    if not entry_thesis_text or len(entry_thesis_text.split()) < 15:
        raise ValueError("entry_thesis_text must state mechanism + what would make it wrong (>= 15 words)")

    thesis_id = _next_id("T", THESIS_PATH, "thesis_id")
    _append_event(THESIS_PATH, {
        "event": "thesis_open",
        "thesis_id": thesis_id,
        "author": author,
        **_session_stamp(),
        "paper": paper,
        "entity": entity,
        "direction": direction,
        "horizon_days": int(horizon_days),
        "entry_thesis_text": entry_thesis_text,
        "probability": float(probability),
        "invalidation_level": float(invalidation_level),
        "catalyst": catalyst,
        "source_dislocation_id": source_dislocation_id,
        "open_date": date.today().isoformat(),
        "status": "open",
    })
    return thesis_id


def fold_theses(events: Optional[list[dict[str, Any]]] = None) -> dict[str, dict[str, Any]]:
    if events is None:
        events = _read_events(THESIS_PATH)
    state: dict[str, dict[str, Any]] = {}
    for e in events:
        ev = e.get("event")
        if ev not in THESIS_EVENTS:
            raise ValueError(
                f"unknown thesis event type {ev!r} (FAIL-IS-FAIL: the ledger "
                f"reader refuses to silently drop events it does not understand)")
        tid = e.get("thesis_id")
        if ev == "thesis_open":
            state[tid] = {k: v for k, v in e.items() if k != "event"}
            state[tid]["marks"] = []
            state[tid]["reviews"] = []
        elif ev == "thesis_mark" and tid in state:
            state[tid]["marks"].append({
                "mark_date": e["mark_date"],
                "cum_return": e["cum_return"],
                "days_open": e["days_open"],
            })
        elif ev == "thesis_review" and tid in state:
            # Hand-written review note (agree/kill). Previously DROPPED silently
            # — folding it keeps the reasoning trail attached to the thesis.
            state[tid]["reviews"].append({
                "review_date": e.get("review_date"),
                "reviewer": e.get("reviewer"),
                "verdict": e.get("verdict"),
                "note": e.get("note", ""),
            })
        elif ev == "thesis_close" and tid in state:
            state[tid].update({
                "status": e["status"],
                "close_date": e["close_date"],
                "realized_return": e["realized_return"],
                "outcome": e["outcome"],
                "brier_contribution": e["brier_contribution"],
                "close_note": e.get("close_note", ""),
                "outcome_label": _outcome_label(e["status"]),
            })
    return state


def mark_open_theses(as_of: Optional[str] = None) -> list[dict[str, Any]]:
    """Auto-mark every open thesis from T2 daily returns; close mechanically.

    Returns a list of action dicts (for the daily brief). Marks are signed:
    a SHORT thesis profits when the country falls.
    """
    theses = fold_theses()
    open_ids = [t for t, v in theses.items() if v["status"] == "open"]
    if not open_ids:
        return []

    con = loop_connection(read_only=True)
    try:
        actions = []
        for tid in open_ids:
            t = theses[tid]
            df = con.execute(
                """
                SELECT date, value FROM asado.t2_factors_daily
                WHERE variable = '1DRet' AND country = ?
                  AND date > CAST(? AS DATE)
                  AND (? IS NULL OR date <= CAST(? AS DATE))
                  AND value IS NOT NULL
                ORDER BY date
                """,
                [t["entity"], t["open_date"], as_of, as_of],
            ).fetchdf()
            if df.empty:
                continue
            sign = 1.0 if t["direction"] == "long" else -1.0
            cum = float(((1 + sign * df["value"]).prod()) - 1.0)
            mark_date = str(df["date"].max().date())
            days_open = (pd.Timestamp(mark_date) - pd.Timestamp(t["open_date"])).days

            _append_event(THESIS_PATH, {
                "event": "thesis_mark",
                "thesis_id": tid,
                "mark_date": mark_date,
                "cum_return": round(cum, 6),
                "days_open": days_open,
            })
            action = {"thesis_id": tid, "entity": t["entity"], "direction": t["direction"],
                      "cum_return": round(cum, 4), "days_open": days_open,
                      "invalidation_level": t["invalidation_level"], "status": "open"}

            if cum <= t["invalidation_level"]:
                _close(tid, "invalidated", mark_date, cum, t["probability"],
                       note=f"cum_return {cum:.4f} breached invalidation {t['invalidation_level']}")
                action["status"] = "invalidated"
            elif days_open >= t["horizon_days"]:
                status = "hit" if cum > 0 else "miss"
                _close(tid, status, mark_date, cum, t["probability"],
                       note=f"horizon {t['horizon_days']}d reached")
                action["status"] = status
            actions.append(action)
        return actions
    finally:
        con.close()


def _close(thesis_id: str, status: str, close_date: str, realized: float,
           probability: float, note: str = "") -> None:
    outcome = 1.0 if status == "hit" else 0.0
    _append_event(THESIS_PATH, {
        "event": "thesis_close",
        "thesis_id": thesis_id,
        "status": status,
        "close_date": close_date,
        "realized_return": round(realized, 6),
        "outcome": outcome,
        "brier_contribution": round((probability - outcome) ** 2, 6),
        "close_note": note,
    })


# ── methodology ledger (directory-experiment verdicts) ─────────────────────
# Extends the hypothesis ledger's pre-registration discipline to
# whole-methodology tests (regime/, regime_ew/, momentum_fragility/-style
# directory experiments) that the harness's single-variable schema cannot
# represent — see the module docstring and METHODOLOGY_EVENTS above for why
# this is a separate file rather than a new event type in hypothesis_ledger.jsonl.

def _validate_gate_ladder(gate_ladder: list[dict[str, Any]]) -> None:
    if not gate_ladder or not isinstance(gate_ladder, list):
        raise ValueError("gate_ladder must be a non-empty list of {'gate': int, 'description': str}")
    for g in gate_ladder:
        if "gate" not in g or "description" not in g:
            raise ValueError(f"each gate_ladder entry needs 'gate' and 'description', got {g!r}")
        if not str(g["description"]).strip():
            raise ValueError(f"gate {g.get('gate')} description must be non-empty")


def register_methodology_experiment(
    experiment_name: str,
    experiment_dir: str,
    hypothesis_text: str,
    gate_ladder: list[dict[str, Any]],
    prd_path: str = "",
    author: str = "agent",
) -> str:
    """Pre-register a directory-experiment methodology test BEFORE running it.
    Returns experiment_id.

    hypothesis_text must be written BEFORE any results are seen (same
    discipline as register_hypothesis's mechanism_text) — this is what makes
    a later GRADUATED verdict meaningful rather than a post-hoc rationalization.
    gate_ladder is the experiment's OWN numbered pass/fail criteria (there is
    no universal ladder across experiments) — e.g.
    [{"gate": 1, "description": "regime states are persistent"},
     {"gate": 2, "description": "states are not just a volatility proxy"},
     {"gate": 3, "description": "states lead own-country returns walk-forward OOS"}].
    """
    if not experiment_name or not experiment_name.strip():
        raise ValueError("experiment_name required")
    if not experiment_dir or not (Path(experiment_dir.rstrip("/")).is_dir()):
        raise ValueError(f"experiment_dir must be an existing directory, got {experiment_dir!r}")
    if not hypothesis_text or len(hypothesis_text.split()) < 15:
        raise ValueError("hypothesis_text must be a real paragraph (>= 15 words), written before results")
    _validate_gate_ladder(gate_ladder)

    experiment_id = _next_id("M", METHODOLOGY_PATH, "experiment_id")
    _append_event(METHODOLOGY_PATH, {
        "event": "methodology_register",
        "experiment_id": experiment_id,
        "author": author,
        **_session_stamp(),
        "experiment_name": experiment_name,
        "experiment_dir": experiment_dir,
        "hypothesis_text": hypothesis_text,
        "gate_ladder": gate_ladder,
        "prd_path": prd_path,
        "pre_registered": True,
        "status": "registered",
    })
    return experiment_id


def attach_methodology_verdict(
    experiment_id: str,
    verdict: str,
    died_at_gate: Optional[int],
    evidence_path: str,
    lesson: str,
    gate_results: Optional[list[dict[str, Any]]] = None,
    verdict_date: Optional[str] = None,
) -> None:
    """Record the result of a pre-registered methodology experiment.

    died_at_gate = the gate number it failed at (must match a gate in the
    registered ladder), or None if it GRADUATED (passed every gate).
    evidence_path should point at the specific RESULTS.md (and line range if
    useful) backing the verdict — this ledger is a pointer + verdict, not a
    replacement for the experiment's own writeup.
    """
    exp = get_methodology_experiment(experiment_id)
    if exp is None:
        raise KeyError(f"methodology experiment {experiment_id} not registered")
    if verdict not in VALID_METHODOLOGY_VERDICTS:
        raise ValueError(f"verdict must be one of {sorted(VALID_METHODOLOGY_VERDICTS)}")
    valid_gates = {g["gate"] for g in exp["gate_ladder"]}
    if died_at_gate is not None and died_at_gate not in valid_gates:
        raise ValueError(f"died_at_gate {died_at_gate} is not in this experiment's registered ladder {sorted(valid_gates)}")
    if not evidence_path or not evidence_path.strip():
        raise ValueError("evidence_path required (e.g. 'regime_ew/results/RESULTS.md:5-11')")
    if not lesson or len(lesson.split()) < 5:
        raise ValueError("lesson must be a real one-liner (>= 5 words), not vacuous")

    status = {"DEAD": "dead", "GRADUATED": "graduated",
              "WATCH": "watch", "INSUFFICIENT": "insufficient"}[verdict]
    _append_event(METHODOLOGY_PATH, {
        "event": "methodology_verdict",
        "experiment_id": experiment_id,
        "verdict": verdict,
        "died_at_gate": died_at_gate,
        "gate_results": gate_results or [],
        "evidence_path": evidence_path,
        "lesson": lesson,
        "verdict_date": verdict_date or date.today().isoformat(),
        "status": status,
    })


def backfill_methodology_verdict(
    experiment_name: str,
    experiment_dir: str,
    hypothesis_text: str,
    gate_ladder: list[dict[str, Any]],
    verdict: str,
    died_at_gate: Optional[int],
    evidence_path: str,
    lesson: str,
    verdict_date: str,
    prd_path: str = "",
    author: str = "agent",
) -> str:
    """Record a HISTORICAL methodology experiment that predates this ledger,
    in one combined event (there is no real pre-registration moment to anchor
    a two-step register/verdict pair to). Returns experiment_id.

    IMPORTANT — epistemic honesty: this stamps pre_registered=False. A
    backfilled entry documents a real, already-verified kill (RESULTS.md is
    the primary evidence), but it does NOT carry the same evidentiary weight
    as a genuine pre-registration written before results were seen, and
    callers/readers must not conflate the two. Do not call this for a new
    experiment — use register_methodology_experiment + attach_methodology_verdict
    instead so the pre-registration proof is real.
    """
    if not experiment_name or not experiment_name.strip():
        raise ValueError("experiment_name required")
    if not experiment_dir or not (Path(experiment_dir.rstrip("/")).is_dir()):
        raise ValueError(f"experiment_dir must be an existing directory, got {experiment_dir!r}")
    if not hypothesis_text or len(hypothesis_text.split()) < 15:
        raise ValueError("hypothesis_text must be a real paragraph (>= 15 words)")
    _validate_gate_ladder(gate_ladder)
    if verdict not in VALID_METHODOLOGY_VERDICTS:
        raise ValueError(f"verdict must be one of {sorted(VALID_METHODOLOGY_VERDICTS)}")
    valid_gates = {g["gate"] for g in gate_ladder}
    if died_at_gate is not None and died_at_gate not in valid_gates:
        raise ValueError(f"died_at_gate {died_at_gate} is not in gate_ladder {sorted(valid_gates)}")
    if not evidence_path or not evidence_path.strip():
        raise ValueError("evidence_path required")
    if not lesson or len(lesson.split()) < 5:
        raise ValueError("lesson must be a real one-liner (>= 5 words), not vacuous")
    if not verdict_date:
        raise ValueError("verdict_date required for a backfill (the historical date, not today)")

    status = {"DEAD": "dead", "GRADUATED": "graduated",
              "WATCH": "watch", "INSUFFICIENT": "insufficient"}[verdict]
    experiment_id = _next_id("M", METHODOLOGY_PATH, "experiment_id")
    _append_event(METHODOLOGY_PATH, {
        "event": "methodology_backfill",
        "experiment_id": experiment_id,
        "author": author,
        **_session_stamp(),
        "experiment_name": experiment_name,
        "experiment_dir": experiment_dir,
        "hypothesis_text": hypothesis_text,
        "gate_ladder": gate_ladder,
        "prd_path": prd_path,
        "pre_registered": False,
        "verdict": verdict,
        "died_at_gate": died_at_gate,
        "gate_results": [],
        "evidence_path": evidence_path,
        "lesson": lesson,
        "verdict_date": verdict_date,
        "status": status,
    })
    return experiment_id


def get_methodology_experiment(experiment_id: str) -> Optional[dict[str, Any]]:
    state = fold_methodology_experiments()
    return state.get(experiment_id)


def fold_methodology_experiments(events: Optional[list[dict[str, Any]]] = None) -> dict[str, dict[str, Any]]:
    if events is None:
        events = _read_events(METHODOLOGY_PATH)
    state: dict[str, dict[str, Any]] = {}
    for e in events:
        ev = e.get("event")
        if ev not in METHODOLOGY_EVENTS:
            raise ValueError(
                f"unknown methodology event type {ev!r} (FAIL-IS-FAIL: the ledger "
                f"reader refuses to silently drop events it does not understand)")
        eid = e.get("experiment_id")
        if ev in ("methodology_register", "methodology_backfill"):
            state[eid] = {k: v for k, v in e.items() if k != "event"}
        elif ev == "methodology_verdict" and eid in state:
            state[eid]["verdict"] = e["verdict"]
            state[eid]["died_at_gate"] = e["died_at_gate"]
            state[eid]["gate_results"] = e["gate_results"]
            state[eid]["evidence_path"] = e["evidence_path"]
            state[eid]["lesson"] = e["lesson"]
            state[eid]["verdict_date"] = e["verdict_date"]
            state[eid]["status"] = e["status"]
    return state


# ── DuckDB folding ──────────────────────────────────────────────────────────

def rebuild_duckdb_tables() -> None:
    """Fold all three JSONL ledgers into loop-DB tables (idempotent full rebuild)."""
    hyps = fold_hypotheses()
    theses = fold_theses()
    methods = fold_methodology_experiments()

    hyp_rows = []
    for h in hyps.values():
        hyp_rows.append({
            "hypothesis_id": h["hypothesis_id"],
            "created_ts": h["ts"],
            "author": h["author"],
            "model_id": h.get("model_id") or "unknown_pre_20260617",
            "model_version": h.get("model_version") or "unknown_pre_20260617",
            "session_id": h.get("session_id") or "unknown_pre_20260617",
            "archetype": h["archetype"],
            "family_key": h["family_key"],
            "mechanism_text": h["mechanism_text"],
            "signal_spec_json": json.dumps(h["signal_spec"]),
            "signal_spec_hash": h["signal_spec_hash"],
            "trial_index": h["trial_index"],
            "status": h["status"],
            "verdict": h.get("verdict"),
            "effective_verdict": effective_verdict(h["status"], h.get("verdict")),
            "verdict_json": json.dumps(h.get("verdict_json")) if h.get("verdict_json") else None,
        })

    thesis_rows, mark_rows = [], []
    for t in theses.values():
        thesis_rows.append({
            "thesis_id": t["thesis_id"],
            "opened_ts": t["ts"],
            "author": t["author"],
            "model_id": t.get("model_id") or "unknown_pre_20260617",
            "model_version": t.get("model_version") or "unknown_pre_20260617",
            "session_id": t.get("session_id") or "unknown_pre_20260617",
            "paper": t.get("paper", True),
            "entity": t["entity"],
            "direction": t["direction"],
            "horizon_days": t["horizon_days"],
            "entry_thesis_text": t["entry_thesis_text"],
            "probability": t["probability"],
            "invalidation_level": t["invalidation_level"],
            "catalyst": t.get("catalyst", ""),
            "source_dislocation_id": t.get("source_dislocation_id", ""),
            "open_date": t["open_date"],
            "status": t["status"],
            "close_date": t.get("close_date"),
            "realized_return": t.get("realized_return"),
            "outcome": t.get("outcome"),
            "outcome_label": t.get("outcome_label"),
            "brier_contribution": t.get("brier_contribution"),
        })
        for m in t["marks"]:
            mark_rows.append({"thesis_id": t["thesis_id"], **m})

    method_rows = []
    for m in methods.values():
        method_rows.append({
            "experiment_id": m["experiment_id"],
            "created_ts": m["ts"],
            "author": m["author"],
            "model_id": m.get("model_id") or "unknown",
            "model_version": m.get("model_version") or "unknown",
            "session_id": m.get("session_id") or "unknown",
            "experiment_name": m["experiment_name"],
            "experiment_dir": m["experiment_dir"],
            "hypothesis_text": m["hypothesis_text"],
            "gate_ladder_json": json.dumps(m["gate_ladder"]),
            "prd_path": m.get("prd_path", ""),
            "pre_registered": m.get("pre_registered", True),
            "status": m["status"],
            "verdict": m.get("verdict"),
            "died_at_gate": m.get("died_at_gate"),
            "gate_results_json": json.dumps(m.get("gate_results") or []),
            "evidence_path": m.get("evidence_path"),
            "lesson": m.get("lesson"),
            "verdict_date": m.get("verdict_date"),
        })

    con = loop_connection()
    try:
        for name, rows, empty_cols in [
            ("hypothesis_ledger", hyp_rows,
             "hypothesis_id VARCHAR, created_ts VARCHAR, author VARCHAR, "
             "model_id VARCHAR, model_version VARCHAR, session_id VARCHAR, archetype VARCHAR, "
             "family_key VARCHAR, mechanism_text VARCHAR, signal_spec_json VARCHAR, "
             "signal_spec_hash VARCHAR, trial_index INT, status VARCHAR, verdict VARCHAR, "
             "effective_verdict VARCHAR, verdict_json VARCHAR"),
            ("thesis_ledger", thesis_rows,
             "thesis_id VARCHAR, opened_ts VARCHAR, author VARCHAR, "
             "model_id VARCHAR, model_version VARCHAR, session_id VARCHAR, paper BOOLEAN, entity VARCHAR, "
             "direction VARCHAR, horizon_days INT, entry_thesis_text VARCHAR, probability DOUBLE, "
             "invalidation_level DOUBLE, catalyst VARCHAR, source_dislocation_id VARCHAR, "
             "open_date VARCHAR, status VARCHAR, close_date VARCHAR, realized_return DOUBLE, "
             "outcome DOUBLE, outcome_label VARCHAR, brier_contribution DOUBLE"),
            ("thesis_marks", mark_rows,
             "thesis_id VARCHAR, mark_date VARCHAR, cum_return DOUBLE, days_open INT"),
            ("methodology_ledger", method_rows,
             "experiment_id VARCHAR, created_ts VARCHAR, author VARCHAR, "
             "model_id VARCHAR, model_version VARCHAR, session_id VARCHAR, "
             "experiment_name VARCHAR, experiment_dir VARCHAR, hypothesis_text VARCHAR, "
             "gate_ladder_json VARCHAR, prd_path VARCHAR, pre_registered BOOLEAN, status VARCHAR, "
             "verdict VARCHAR, died_at_gate INT, gate_results_json VARCHAR, "
             "evidence_path VARCHAR, lesson VARCHAR, verdict_date VARCHAR"),
        ]:
            con.execute(f"DROP TABLE IF EXISTS {name}")
            if rows:
                df = pd.DataFrame(rows)
                con.execute(f"CREATE TABLE {name} AS SELECT * FROM df")
            else:
                con.execute(f"CREATE TABLE {name} ({empty_cols})")
        # A3: canonical "what is live" surface. A consumer keying on this view
        # (instead of raw `verdict`) can never resurrect a retired/rejected
        # hypothesis — e.g. H_20260610_001, the retired 12MRet look-ahead that
        # still folds to verdict='WATCH'.
        con.execute(
            "CREATE OR REPLACE VIEW live_signals AS "
            "SELECT * FROM hypothesis_ledger WHERE status NOT IN ('retired', 'rejected')")
    finally:
        con.close()


# ── CLI ─────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Alpha-Hunting Loop ledgers.")
    parser.add_argument("--rebuild", action="store_true", help="Fold JSONL into loop-DB tables.")
    parser.add_argument("--list", action="store_true", help="Print current hypotheses, theses, and methodology experiments.")
    parser.add_argument("--mark", action="store_true", help="Auto-mark open theses from daily returns.")
    args = parser.parse_args()

    if args.mark:
        actions = mark_open_theses()
        for a in actions:
            print(json.dumps(a))
        print(f"{len(actions)} open thesis/theses marked.")
        rebuild_duckdb_tables()
        return 0
    if args.rebuild:
        rebuild_duckdb_tables()
        print("Ledger tables rebuilt in loop DB.")
        return 0
    if args.list:
        hyps, theses = fold_hypotheses(), fold_theses()
        methods = fold_methodology_experiments()
        print(f"── {len(hyps)} hypothesis(es) ──")
        for h in hyps.values():
            print(f"  {h['hypothesis_id']} [{h['status']:>10}] {h['archetype']} family={h['family_key']} "
                  f"trial#{h['trial_index']} verdict={h.get('verdict', '-')}")
        print(f"── {len(theses)} thesis(es) ──")
        for t in theses.values():
            last = t["marks"][-1]["cum_return"] if t["marks"] else None
            print(f"  {t['thesis_id']} [{t['status']:>11}] {t['direction']:>5} {t['entity']:<14} "
                  f"h={t['horizon_days']}d p={t['probability']} inv={t['invalidation_level']} mark={last}")
        print(f"── {len(methods)} methodology experiment(s) ──")
        for m in methods.values():
            reg = "backfill" if not m.get("pre_registered", True) else "pre-reg"
            print(f"  {m['experiment_id']} [{m['status']:>11}] {reg:>8} {m['experiment_name']:<24} "
                  f"verdict={m.get('verdict', '-')} died_at_gate={m.get('died_at_gate', '-')}")
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
