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
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb (read-only)
  t2_factors_daily 1DRet rows used for auto-marking open theses.

OUTPUT FILES:
- The two JSONL files above (append-only; nothing is ever rewritten or deleted).
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

VERSION: 1.0
LAST UPDATED: 2026-06-10
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 1)

DESCRIPTION:
The memory and honesty layer of the Alpha-Hunting Loop (PRD section 6).
Two append-only ledgers, stored as JSONL so git history is tamper evidence:

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

Event-sourcing design: each JSONL line is an immutable event
({"event": "hyp_register" | "hyp_verdict" | "hyp_status" | "thesis_open" |
"thesis_mark" | "thesis_close", ...}). Current state = fold of all events.
A 10th grader's version: it's a diary in pen, not pencil - you can add new
pages but never erase old ones, so your past claims stay checkable.

DEPENDENCIES:
- duckdb, pandas (project venv)

USAGE:
 python scripts/loop/ledgers.py --rebuild       # fold JSONL -> DuckDB tables
 python scripts/loop/ledgers.py --list          # show current hypotheses + theses
 python scripts/loop/ledgers.py --mark          # auto-mark open theses (daily job)
 # As a library:
 from scripts.loop.ledgers import register_hypothesis, open_thesis, ...

NOTES:
- IDs: H_YYYYMMDD_NNN / T_YYYYMMDD_NNN, NNN increments within the day.
- thesis direction: long / short. invalidation_level: adverse cumulative
  return in DECIMAL from entry (e.g. -0.07 = closed out if down 7% on a long).
- Outcome at close: hit=1 / miss=0; brier_contribution = (probability - outcome)^2.
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

VALID_ARCHETYPES = {"A1", "A2", "A3", "A4", "A5", "A6", "A7", "other"}
VALID_DIRECTIONS = {"long", "short"}

# A3 — ledger integrity (FAIL-IS-FAIL on the reader). The fold refuses to
# silently drop an event type it does not understand.
HYP_EVENTS = {"hyp_register", "hyp_verdict", "hyp_status"}
THESIS_EVENTS = {"thesis_open", "thesis_mark", "thesis_close", "thesis_review"}
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


# ── DuckDB folding ──────────────────────────────────────────────────────────

def rebuild_duckdb_tables() -> None:
    """Fold both JSONL ledgers into loop-DB tables (idempotent full rebuild)."""
    hyps = fold_hypotheses()
    theses = fold_theses()

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
    parser.add_argument("--list", action="store_true", help="Print current hypotheses and theses.")
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
        print(f"── {len(hyps)} hypothesis(es) ──")
        for h in hyps.values():
            print(f"  {h['hypothesis_id']} [{h['status']:>10}] {h['archetype']} family={h['family_key']} "
                  f"trial#{h['trial_index']} verdict={h.get('verdict', '-')}")
        print(f"── {len(theses)} thesis(es) ──")
        for t in theses.values():
            last = t["marks"][-1]["cum_return"] if t["marks"] else None
            print(f"  {t['thesis_id']} [{t['status']:>11}] {t['direction']:>5} {t['entity']:<14} "
                  f"h={t['horizon_days']}d p={t['probability']} inv={t['invalidation_level']} mark={last}")
        return 0
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
