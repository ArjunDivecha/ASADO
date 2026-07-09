#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: tests/loop/test_methodology_ledger.py
=============================================================================

INPUT FILES: none at runtime for the fabricated-event tests (fold functions
are fed fabricated event lists via the `events=` param). The register/verdict/
backfill round-trip tests write to a `tmp_path` file via a monkeypatched
METHODOLOGY_PATH — never the real ledgers/methodology_ledger.jsonl. One
conservation test reads the REAL ledgers/methodology_ledger.jsonl (read-only,
never mutated) if it exists; the file need not exist yet.

OUTPUT FILES: none (pure assertions; the monkeypatched writes go to pytest's
tmp_path, which pytest deletes after the run).

VERSION: 1.0
LAST UPDATED: 2026-07-09
AUTHOR: Arjun Divecha (built by agent session — methodology ledger extension)

DESCRIPTION:
Acceptance tests for the methodology ledger (scripts/loop/ledgers.py's third
ledger, for directory-experiment / whole-methodology verdicts that the
single-variable hypothesis ledger cannot represent):
  - unknown event type raises (FAIL-IS-FAIL, same discipline as the
    hypothesis/thesis ledgers, but scoped to METHODOLOGY_EVENTS only — proves
    the new ledger is fully isolated from HYP_EVENTS/THESIS_EVENTS)
  - register -> verdict folds correctly; a verdict with no prior registration
    is silently ignored (mirrors hyp_verdict's `and hid in state` guard)
  - backfill folds as a single combined event, correctly flagged
    pre_registered=False
  - validation: hypothesis_text word count, gate_ladder shape, died_at_gate
    must be a real gate in the ladder, verdict vocabulary, experiment_dir
    must exist
  - a real end-to-end register -> attach_verdict round trip against an
    isolated tmp_path ledger file (METHODOLOGY_PATH monkeypatched — never
    touches the real ledgers/ directory)
  - the real (possibly empty/nonexistent) methodology_ledger.jsonl folds
    without raising

USAGE:
  venv/bin/python -m pytest tests/loop/test_methodology_ledger.py -q
=============================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
from scripts.loop import ledgers  # noqa: E402

GATE_LADDER = [
    {"gate": 1, "description": "states are persistent"},
    {"gate": 2, "description": "states are not just a volatility proxy"},
    {"gate": 3, "description": "states lead own-country returns walk-forward OOS"},
]
HYPOTHESIS_TEXT = (
    "Per-country regime states derived from an HMM should lead subsequent "
    "own-country returns out of sample, tested walk-forward across all 34 "
    "T2 countries before any result is inspected."
)


# ── FAIL-IS-FAIL: unknown events raise, scoped to this ledger only ─────────

def test_unknown_methodology_event_raises():
    events = [
        {"event": "methodology_register", "experiment_id": "M1", "author": "a",
         "experiment_name": "regime_ew", "experiment_dir": "regime_ew",
         "hypothesis_text": HYPOTHESIS_TEXT, "gate_ladder": GATE_LADDER,
         "prd_path": "", "pre_registered": True, "status": "registered"},
        {"event": "methodology_bogus", "experiment_id": "M1"},
    ]
    with pytest.raises(ValueError, match="unknown methodology event"):
        ledgers.fold_methodology_experiments(events)


def test_hyp_event_types_do_not_leak_into_methodology_fold():
    """Proves the two ledgers are fully isolated: a hyp_register event is
    just as 'unknown' to fold_methodology_experiments as a bogus one — this
    ledger cannot be corrupted by code that accidentally points at the wrong
    constant."""
    events = [{"event": "hyp_register", "hypothesis_id": "H1"}]
    with pytest.raises(ValueError, match="unknown methodology event"):
        ledgers.fold_methodology_experiments(events)


# ── register -> verdict folds; verdict with no registration is ignored ─────

def test_register_then_verdict_folds():
    events = [
        {"event": "methodology_register", "experiment_id": "M1", "author": "a",
         "experiment_name": "regime_ew", "experiment_dir": "regime_ew",
         "hypothesis_text": HYPOTHESIS_TEXT, "gate_ladder": GATE_LADDER,
         "prd_path": "", "pre_registered": True, "status": "registered"},
        {"event": "methodology_verdict", "experiment_id": "M1", "verdict": "DEAD",
         "died_at_gate": 3, "gate_results": [], "evidence_path": "regime_ew/results/RESULTS.md:5-11",
         "lesson": "Full-sample fit looked significant; walk-forward killed it.",
         "verdict_date": "2026-06-21", "status": "dead"},
    ]
    state = ledgers.fold_methodology_experiments(events)
    assert state["M1"]["verdict"] == "DEAD"
    assert state["M1"]["died_at_gate"] == 3
    assert state["M1"]["status"] == "dead"
    assert state["M1"]["pre_registered"] is True


def test_verdict_without_registration_is_ignored_not_crashed():
    events = [
        {"event": "methodology_verdict", "experiment_id": "M_GHOST", "verdict": "DEAD",
         "died_at_gate": 1, "gate_results": [], "evidence_path": "x", "lesson": "irrelevant orphan event",
         "verdict_date": "2026-06-21", "status": "dead"},
    ]
    state = ledgers.fold_methodology_experiments(events)
    assert state == {}


# ── backfill folds as one combined event, correctly flagged ────────────────

def test_backfill_folds_with_pre_registered_false():
    events = [
        {"event": "methodology_backfill", "experiment_id": "M2", "author": "a",
         "experiment_name": "momentum_fragility", "experiment_dir": "momentum_fragility",
         "hypothesis_text": HYPOTHESIS_TEXT, "gate_ladder": GATE_LADDER, "prd_path": "",
         "pre_registered": False, "verdict": "DEAD", "died_at_gate": 3, "gate_results": [],
         "evidence_path": "momentum_fragility/results/RESULTS.md:5-13",
         "lesson": "Fragility-conditioned reversal doesn't exist at monthly horizon.",
         "verdict_date": "2026-07-05", "status": "dead"},
    ]
    state = ledgers.fold_methodology_experiments(events)
    assert state["M2"]["pre_registered"] is False
    assert state["M2"]["verdict"] == "DEAD"


# ── validation on the real functions (against an isolated tmp ledger) ──────

@pytest.fixture
def isolated_methodology_path(tmp_path, monkeypatch):
    p = tmp_path / "methodology_ledger.jsonl"
    monkeypatch.setattr(ledgers, "METHODOLOGY_PATH", p)
    return p


def test_register_requires_real_directory(isolated_methodology_path):
    with pytest.raises(ValueError, match="existing directory"):
        ledgers.register_methodology_experiment(
            "fake_experiment", "this_directory_does_not_exist_12345",
            HYPOTHESIS_TEXT, GATE_LADDER)


def test_register_requires_15_word_hypothesis(isolated_methodology_path):
    with pytest.raises(ValueError, match="15 words"):
        ledgers.register_methodology_experiment(
            "regime_ew", str(BASE_DIR / "regime_ew"), "too short", GATE_LADDER)


def test_register_requires_nonempty_gate_ladder(isolated_methodology_path):
    with pytest.raises(ValueError, match="gate_ladder"):
        ledgers.register_methodology_experiment(
            "regime_ew", str(BASE_DIR / "regime_ew"), HYPOTHESIS_TEXT, [])


def test_register_then_attach_round_trip(isolated_methodology_path):
    exp_id = ledgers.register_methodology_experiment(
        "regime_ew", str(BASE_DIR / "regime_ew"), HYPOTHESIS_TEXT, GATE_LADDER,
        prd_path="PRD Regime Early Warning.md", author="test",
    )
    assert exp_id.startswith("M_")
    exp = ledgers.get_methodology_experiment(exp_id)
    assert exp["status"] == "registered"
    assert exp["pre_registered"] is True

    ledgers.attach_methodology_verdict(
        exp_id, "DEAD", died_at_gate=3,
        evidence_path="regime_ew/results/RESULTS.md:5-11",
        lesson="Walk-forward own-country lead failed; full-sample fit was look-ahead.",
        verdict_date="2026-06-21",
    )
    exp = ledgers.get_methodology_experiment(exp_id)
    assert exp["verdict"] == "DEAD"
    assert exp["status"] == "dead"
    assert exp["died_at_gate"] == 3


def test_attach_verdict_rejects_unregistered_id(isolated_methodology_path):
    with pytest.raises(KeyError, match="not registered"):
        ledgers.attach_methodology_verdict(
            "M_NOPE", "DEAD", died_at_gate=1, evidence_path="x",
            lesson="this experiment id was never registered here")


def test_attach_verdict_rejects_gate_not_in_ladder(isolated_methodology_path):
    exp_id = ledgers.register_methodology_experiment(
        "regime_ew", str(BASE_DIR / "regime_ew"), HYPOTHESIS_TEXT, GATE_LADDER)
    with pytest.raises(ValueError, match="not in this experiment's registered ladder"):
        ledgers.attach_methodology_verdict(
            exp_id, "DEAD", died_at_gate=99,
            evidence_path="x", lesson="died at a gate number that was never registered")


def test_attach_verdict_rejects_invalid_verdict(isolated_methodology_path):
    exp_id = ledgers.register_methodology_experiment(
        "regime_ew", str(BASE_DIR / "regime_ew"), HYPOTHESIS_TEXT, GATE_LADDER)
    with pytest.raises(ValueError, match="verdict must be one of"):
        ledgers.attach_methodology_verdict(
            exp_id, "MAYBE", died_at_gate=None,
            evidence_path="x", lesson="an invalid verdict string should be rejected")


def test_backfill_stamps_pre_registered_false(isolated_methodology_path):
    exp_id = ledgers.backfill_methodology_verdict(
        experiment_name="momentum_fragility",
        experiment_dir=str(BASE_DIR / "momentum_fragility"),
        hypothesis_text=HYPOTHESIS_TEXT,
        gate_ladder=GATE_LADDER,
        verdict="DEAD",
        died_at_gate=3,
        evidence_path="momentum_fragility/results/RESULTS.md:5-13",
        lesson="Fragility-conditioned reversal doesn't exist at monthly horizon.",
        verdict_date="2026-07-05",
    )
    exp = ledgers.get_methodology_experiment(exp_id)
    assert exp["pre_registered"] is False
    assert exp["verdict"] == "DEAD"
    assert exp["verdict_date"] == "2026-07-05"


def test_backfill_requires_explicit_verdict_date(isolated_methodology_path):
    with pytest.raises(ValueError, match="verdict_date required"):
        ledgers.backfill_methodology_verdict(
            experiment_name="momentum_fragility",
            experiment_dir=str(BASE_DIR / "momentum_fragility"),
            hypothesis_text=HYPOTHESIS_TEXT,
            gate_ladder=GATE_LADDER,
            verdict="DEAD",
            died_at_gate=3,
            evidence_path="x",
            lesson="a backfill without a historical date should be rejected",
            verdict_date="",
        )


# ── conservation on the REAL ledger (read-only; file may not exist yet) ────

def test_real_methodology_ledger_folds_without_unknown_events():
    """The shipped methodology_ledger.jsonl (if any events exist yet)
    contains only known event types."""
    ledgers.fold_methodology_experiments(ledgers._read_events(ledgers.METHODOLOGY_PATH))


def test_real_methodology_ledger_count_conservation():
    events = ledgers._read_events(ledgers.METHODOLOGY_PATH)
    registered_or_backfilled = {
        e["experiment_id"] for e in events
        if e.get("event") in ("methodology_register", "methodology_backfill")
    }
    folded = ledgers.fold_methodology_experiments(events)
    assert set(folded) == registered_or_backfilled, "every registered/backfilled experiment must fold exactly once"
