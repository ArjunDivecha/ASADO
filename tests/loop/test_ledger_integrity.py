#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: tests/loop/test_ledger_integrity.py
=============================================================================

INPUT FILES: none at runtime — fold functions are fed fabricated event lists
(the new `events=` param). The real ledgers/*.jsonl are read only by the two
conservation tests (count-in == count-out), never mutated.

OUTPUT FILES: none (pure assertions).

VERSION: 1.0
LAST UPDATED: 2026-06-17
AUTHOR: Arjun Divecha (built by agent session, Governance Layer PRD v1.2, item A3)

DESCRIPTION:
A3 acceptance tests for the ledger fold (FAIL-IS-FAIL on the reader):
  - unknown event type raises (never silently dropped)
  - thesis_review events fold (no longer dropped)
  - killed_review -> outcome_label='void' (auditable, not silently null)
  - retired/rejected -> effective_verdict NULL (no WATCH resurrection)
  - count-in == count-out on the real ledgers (no drop/dup)

USAGE:
  venv/bin/python -m pytest tests/loop/test_ledger_integrity.py -q
=============================================================================
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
from scripts.loop import ledgers  # noqa: E402


# ── FAIL-IS-FAIL: unknown events raise ──────────────────────────────────────

def test_unknown_thesis_event_raises():
    events = [
        {"event": "thesis_open", "thesis_id": "T1", "author": "a", "entity": "Brazil",
         "direction": "long", "horizon_days": 21, "entry_thesis_text": "x", "probability": 0.5,
         "invalidation_level": -0.07, "open_date": "2026-06-10", "status": "open"},
        {"event": "thesis_bogus", "thesis_id": "T1"},
    ]
    with pytest.raises(ValueError, match="unknown thesis event"):
        ledgers.fold_theses(events)


def test_unknown_hypothesis_event_raises():
    events = [
        {"event": "hyp_register", "hypothesis_id": "H1", "author": "a", "archetype": "A1",
         "family_key": "f", "mechanism_text": "m", "signal_spec": {}, "signal_spec_hash": "h",
         "trial_index": 1, "status": "registered"},
        {"event": "hyp_bogus", "hypothesis_id": "H1"},
    ]
    with pytest.raises(ValueError, match="unknown hypothesis event"):
        ledgers.fold_hypotheses(events)


# ── thesis_review folds (no longer dropped) ─────────────────────────────────

def test_thesis_review_folds():
    events = [
        {"event": "thesis_open", "thesis_id": "T1", "author": "a", "entity": "Brazil",
         "direction": "long", "horizon_days": 21, "entry_thesis_text": "x", "probability": 0.5,
         "invalidation_level": -0.07, "open_date": "2026-06-10", "status": "open"},
        {"event": "thesis_review", "thesis_id": "T1", "review_date": "2026-06-11",
         "reviewer": "agent", "verdict": "agree", "note": "still holds"},
        {"event": "thesis_review", "thesis_id": "T1", "review_date": "2026-06-12",
         "reviewer": "agent", "verdict": "kill", "note": "artifact"},
    ]
    state = ledgers.fold_theses(events)
    assert len(state["T1"]["reviews"]) == 2
    assert state["T1"]["reviews"][-1]["verdict"] == "kill"


# ── killed_review -> void (auditable, not silently null) ─────────────────────

def test_killed_review_is_void_label():
    events = [
        {"event": "thesis_open", "thesis_id": "T1", "author": "a", "entity": "Taiwan",
         "direction": "short", "horizon_days": 21, "entry_thesis_text": "x", "probability": 0.5,
         "invalidation_level": -0.07, "open_date": "2026-06-10", "status": "open"},
        {"event": "thesis_close", "thesis_id": "T1", "status": "killed_review",
         "close_date": "2026-06-10", "realized_return": 0.0, "outcome": None,
         "brier_contribution": None, "close_note": "killed at review"},
    ]
    state = ledgers.fold_theses(events)
    assert state["T1"]["outcome_label"] == "void"
    assert state["T1"]["outcome"] is None  # still no Brier contribution
    # And a normal close keeps its real label:
    assert ledgers._outcome_label("hit") == "hit"
    assert ledgers._outcome_label("invalidated") == "invalidated"


# ── retired/rejected -> effective_verdict NULL (no resurrection) ─────────────

def test_effective_verdict_nulls_retired_and_rejected():
    assert ledgers.effective_verdict("retired", "WATCH") is None
    assert ledgers.effective_verdict("rejected", "WEAK") is None
    assert ledgers.effective_verdict("watch", "WATCH") == "WATCH"
    assert ledgers.effective_verdict("registered", None) is None


def test_retired_hypothesis_folds_status_retired_verdict_watch():
    """The H_20260610_001 shape: verdict WATCH then status retired."""
    events = [
        {"event": "hyp_register", "hypothesis_id": "H1", "author": "a", "archetype": "A1",
         "family_key": "f", "mechanism_text": "m", "signal_spec": {}, "signal_spec_hash": "h",
         "trial_index": 1, "status": "registered"},
        {"event": "hyp_verdict", "hypothesis_id": "H1", "verdict": "WATCH",
         "verdict_json": {}, "status": "watch"},
        {"event": "hyp_status", "hypothesis_id": "H1", "status": "retired"},
    ]
    state = ledgers.fold_hypotheses(events)
    assert state["H1"]["status"] == "retired"
    assert state["H1"]["verdict"] == "WATCH"  # raw verdict preserved (history)
    assert ledgers.effective_verdict(state["H1"]["status"], state["H1"]["verdict"]) is None


# ── conservation on the REAL ledgers: count-in == count-out ─────────────────

def test_real_thesis_count_conservation():
    events = ledgers._read_events(ledgers.THESIS_PATH)
    opened = {e["thesis_id"] for e in events if e.get("event") == "thesis_open"}
    folded = ledgers.fold_theses(events)
    assert set(folded) == opened, "every opened thesis must fold exactly once"


def test_real_hypothesis_count_conservation():
    events = ledgers._read_events(ledgers.HYP_PATH)
    registered = {e["hypothesis_id"] for e in events if e.get("event") == "hyp_register"}
    folded = ledgers.fold_hypotheses(events)
    assert set(folded) == registered, "every registered hypothesis must fold exactly once"


def test_real_ledgers_fold_without_unknown_events():
    """The shipped ledgers contain only known event types (raise-on-unknown
    would otherwise break the nightly fold)."""
    ledgers.fold_theses(ledgers._read_events(ledgers.THESIS_PATH))
    ledgers.fold_hypotheses(ledgers._read_events(ledgers.HYP_PATH))
