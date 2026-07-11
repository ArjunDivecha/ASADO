#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: attribute_outcomes.py  (Learning Loop — Stage 2 attribution)
=============================================================================

WHAT THIS DOES (plain language)
-------------------------------
Once the outcome scorer (score_gap_outcomes.py) has graded a matured
recommendation, this step explains WHY it worked or failed. It is the
"learn from the mistake" half of the loop. Two strictly separated layers:

  1. DETERMINISTIC CLASSIFIER (this file, no LLM): scores six independent axes
     from the frozen outcome row + the detector's own z-trajectory, and derives
     a headline outcome class. Code assigns the class — never the model.
  2. FABLE-XHIGH LESSON (gated, one call per matured claim): explains the
     mechanism WITHIN the code-assigned axes and proposes a generalizable
     adjustment. Appends to ledgers/lesson_ledger.jsonl with full provenance.
     GATED behind ASADO_RUN_ATTRIBUTION_LLM=1 so it never auto-spends.

The six axes (each independent — a headline class is DERIVED from them):
  data_validity  : confirmed / revised_away / unknown   (detector z persisted vs reverted)
  price_response : with_thesis / against_thesis / unresolved
  timing         : tradable / pre_absorbed / no_absorption
  expression     : captured / basis_failure / unknown
  economics      : positive_net / negative_net
  horizon_fit    : on_time / late / unresolved

INPUT (loop DB, read):  gap_outcomes (scored rows), gap_episodes (source
  dislocations), dislocation_daily (detector z-trajectory), the main warehouse
  is NOT needed here.
OUTPUT (loop DB, append-only): outcome_attribution (the deterministic axes +
  headline per outcome_id).
OUTPUT (ledger, append-only): ledgers/lesson_ledger.jsonl (Fable lessons, gated).

VERSION: 1.0  LAST UPDATED: 2026-07-10  AUTHOR: Claude (Opus 4.8)

NOTES
  * As of 2026-07-10 NO outcome is scored yet (first maturity ~2026-07-16), so a
    correct run attributes 0 rows. The classifier is validated on synthetic
    matured rows in experiments/learning_loop/test_attribute_outcomes.py.
  * data_validity is the Stage 0b LIGHTWEIGHT heuristic (Arjun 2026-07-10):
    |detector z| at exit vs open. Full per-detector confirmation_spec is the
    upgrade path. Falls back to 'unknown' when the z-trajectory is unresolvable.
  * --loop-db PATH overrides the loop DB for testing on a copy.
=============================================================================
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR))
from scripts.loop.loopdb import loop_connection, MAIN_DB  # noqa: E402

LEDGER = BASE_DIR / "ledgers" / "lesson_ledger.jsonl"
ATTRIBUTION_VERSION = "1.0"
NEUTRAL_BAND = 0.005   # 50 bp dead-band for "unresolved" price response
Z_REVERT_FRAC = 0.5    # |z_exit| < 0.5*|z_open| => the data reverted (revised_away)
MAX_LESSONS_PER_RUN = 5


def log(msg: str) -> None:
    print(f"[attribute_outcomes] {msg}", flush=True)


def open_conn(loop_db_override: str | None):
    if not loop_db_override:
        return loop_connection(read_only=False)
    con = duckdb.connect(loop_db_override)
    try:
        con.execute(f"ATTACH '{MAIN_DB}' AS asado (READ_ONLY)")
    except duckdb.Error as exc:
        if "already attached" not in str(exc).lower():
            raise
    return con


# ----------------------------------------------------------------------------
# DETERMINISTIC CLASSIFIER (pure — the testable core; code assigns the class)
# ----------------------------------------------------------------------------
def classify_axes(o: dict, data_validity: str = "unknown") -> dict:
    """Six independent axes from one scored gap_outcomes row + data_validity."""
    gross = o.get("gross_active")
    net = o.get("net_active")
    idx_info = o.get("index_information")
    capture = o.get("etf_capture")
    dec = o.get("decision_available_at")
    absorbed = o.get("absorbed_at")
    exit_ts = o.get("exit_ts")

    if gross is None:
        price_response = "unresolved"
    elif gross > NEUTRAL_BAND:
        price_response = "with_thesis"
    elif gross < -NEUTRAL_BAND:
        price_response = "against_thesis"
    else:
        price_response = "unresolved"

    if absorbed is None:
        timing = "no_absorption"
    elif dec is not None and pd.Timestamp(absorbed) <= pd.Timestamp(dec):
        timing = "pre_absorbed"
    else:
        timing = "tradable"

    if idx_info is None or capture is None:
        expression = "unknown"
    elif idx_info > NEUTRAL_BAND and capture < -NEUTRAL_BAND:
        expression = "basis_failure"
    else:
        expression = "captured"

    economics = "positive_net" if (net is not None and net > 0) else "negative_net"

    if absorbed is None:
        horizon_fit = "unresolved"
    elif exit_ts is not None and pd.Timestamp(absorbed) <= pd.Timestamp(exit_ts):
        horizon_fit = "on_time"
    else:
        horizon_fit = "late"

    return {
        "data_validity": data_validity, "price_response": price_response,
        "timing": timing, "expression": expression, "economics": economics,
        "horizon_fit": horizon_fit,
    }


def headline_class(ax: dict) -> str:
    """Derived headline — a VIEW over the axes, for reporting. Priority cascade."""
    dv, pr = ax["data_validity"], ax["price_response"]
    tm, ex, ec = ax["timing"], ax["expression"], ax["economics"]
    if pr == "unresolved":
        return "UNRESOLVED"
    if pr == "against_thesis" or dv == "revised_away":
        return "DATA_WRONG"
    # price moved with the thesis from here on
    if tm == "pre_absorbed":
        return "DATA_RIGHT_ALREADY_ABSORBED"
    if ec == "positive_net" and tm == "tradable":
        return "DATA_RIGHT_CAPTURED"
    if ec == "negative_net" and ex == "basis_failure":
        return "DATA_RIGHT_NOT_CAPTURABLE"
    if ec == "negative_net":
        return "DATA_RIGHT_NOT_CAPTURABLE"
    return "DATA_RIGHT_CAPTURED"


# ----------------------------------------------------------------------------
# data_validity heuristic (Stage 0b): detector |z| at exit vs open
# ----------------------------------------------------------------------------
def _nearest_severity(disloc: pd.DataFrame, entity: str, when) -> float | None:
    """Signed detector z (severity) for `entity` at the row nearest `when`."""
    sub = disloc[disloc["entity"] == entity]
    if sub.empty:
        return None
    when = pd.Timestamp(when)
    idx = (sub["date"] - when).abs().idxmin()
    return float(sub.loc[idx, "severity"])


def data_validity_for(disloc: pd.DataFrame, entity: str, open_dt, exit_dt) -> str:
    """confirmed if the detector signal persisted; revised_away if it reverted
    toward neutral; unknown if unresolvable. Lightweight — magnitude-based."""
    if disloc.empty or open_dt is None or exit_dt is None:
        return "unknown"
    z0 = _nearest_severity(disloc, entity, open_dt)
    z1 = _nearest_severity(disloc, entity, exit_dt)
    if z0 is None or z1 is None or abs(z0) < 1e-9:
        return "unknown"
    if abs(z1) < Z_REVERT_FRAC * abs(z0):
        return "revised_away"
    return "confirmed"


# ----------------------------------------------------------------------------
# Autopsy packet (deterministic; the evidence Fable explains within)
# ----------------------------------------------------------------------------
def build_packet(o: dict, ax: dict, headline: str) -> dict:
    return {
        "outcome_id": o["outcome_id"], "role": o.get("role"),
        "entity": o.get("entity"), "direction": o.get("direction"),
        "horizon_days": o.get("evaluation_horizon"),
        "the_claim": {
            "ticker": o.get("preferred_ticker"),
            "data_known_at": str(o.get("data_known_at")),
            "decision_available_at": str(o.get("decision_available_at")),
        },
        "what_price_did": {
            "net_active": o.get("net_active"), "gross_active": o.get("gross_active"),
            "index_information": o.get("index_information"),
            "etf_capture": o.get("etf_capture"), "absorbed_at": str(o.get("absorbed_at")),
        },
        "axes": ax, "headline_class": headline,
    }


# ----------------------------------------------------------------------------
# Fable-xhigh lesson (GATED — never auto-spends)
# ----------------------------------------------------------------------------
def generate_lesson(packet: dict) -> dict | None:
    """One Fable-xhigh call; explains WITHIN the code-assigned axes and proposes a
    generalizable adjustment. Returns the lesson dict, or None on any failure."""
    import hashlib
    import requests
    key = _load_api_key()
    if not key:
        log("  no API key — skipping lesson (gated).")
        return None
    tool = {
        "name": "record_lesson",
        "description": "Explain this outcome within its code-assigned axes and propose an adjustment.",
        "input_schema": {
            "type": "object",
            "required": ["diagnosis", "generalizable", "confidence"],
            "properties": {
                "diagnosis": {"type": "string", "maxLength": 900},
                "generalizable": {"type": "boolean"},
                "proposed_adjustment": {"type": "string"},
                "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
            },
        },
    }
    system = (
        "You are ASADO's post-mortem analyst. You are given a matured recommendation with "
        "its outcome ALREADY CLASSIFIED deterministically along six axes and a headline class. "
        "Do NOT re-judge whether it worked — the code decided that. Explain the MECHANISM: why "
        "did the data lead or not, why did the ETF expression capture or lose it, what is the "
        "generalizable lesson by mechanism cluster, and one concrete adjustment. 3-5 sentences. "
        "Record it by calling the record_lesson tool.")
    body = {
        "model": _resolve_fable_model(key), "max_tokens": 8000,
        # Claude 5 effort API: adaptive thinking + xhigh effort. Forced tool_choice
        # is incompatible with thinking, so use auto and instruct the tool call.
        "thinking": {"type": "adaptive"}, "output_config": {"effort": "xhigh"},
        "system": system, "tools": [tool], "tool_choice": {"type": "auto"},
        "messages": [{"role": "user", "content": json.dumps(packet, default=str)}],
    }
    try:
        r = requests.post("https://api.anthropic.com/v1/messages",
                          headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                                   "content-type": "application/json"},
                          json=body, timeout=300)
        r.raise_for_status()
        resp = r.json()
        blocks = [b for b in resp.get("content", []) if b.get("type") == "tool_use"]
        if not blocks:
            return None
        out = blocks[0]["input"]
        out["provenance"] = {
            "model_id": body["model"], "effort": "xhigh",
            "packet_hash": hashlib.sha256(json.dumps(packet, sort_keys=True, default=str).encode()).hexdigest(),
            "attribution_schema_version": ATTRIBUTION_VERSION,
            "usage": resp.get("usage", {}),
        }
        return out
    except Exception as exc:  # noqa: BLE001
        log(f"  lesson call failed (non-fatal): {exc}")
        return None


def _load_api_key() -> str | None:
    env = Path.home() / "Dropbox" / "AAA Backup" / ".env.txt"
    if os.getenv("ANTHROPIC_API_KEY"):
        return os.getenv("ANTHROPIC_API_KEY")
    if env.exists():
        for line in env.read_text().splitlines():
            if "ANTHROPIC_API_KEY" in line and "=" in line:
                return line.split("=", 1)[1].strip().strip('"')
    return None


def _resolve_fable_model(key: str) -> str:
    import requests
    try:
        r = requests.get("https://api.anthropic.com/v1/models",
                         headers={"x-api-key": key, "anthropic-version": "2023-06-01"}, timeout=30)
        models = [m["id"] for m in r.json().get("data", []) if m.get("id", "").startswith("claude-fable-")]
        return sorted(models)[-1] if models else "claude-fable-5"
    except Exception:  # noqa: BLE001
        return "claude-fable-5"


def append_lesson(record: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a") as fh:
        fh.write(json.dumps(record, default=str) + "\n")


# ----------------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------------
ATTR_DDL = """
CREATE TABLE IF NOT EXISTS outcome_attribution (
  outcome_id VARCHAR, gap_id VARCHAR, role VARCHAR, entity VARCHAR,
  data_validity VARCHAR, price_response VARCHAR, timing VARCHAR,
  expression VARCHAR, economics VARCHAR, horizon_fit VARCHAR,
  headline_class VARCHAR, attributed_at TIMESTAMP,
  attribution_version VARCHAR, lesson_id VARCHAR
)
"""


def run(loop_db_override: str | None, run_llm: bool) -> int:
    con = open_conn(loop_db_override)
    try:
        con.execute(ATTR_DDL)
        # scored outcomes not yet attributed (this version)
        scored = con.execute("""
            SELECT * FROM gap_outcomes
            WHERE unscoreable_reason IS NULL
              AND outcome_id NOT IN (
                SELECT outcome_id FROM outcome_attribution
                WHERE attribution_version = ?)
        """, [ATTRIBUTION_VERSION]).fetchdf()
        disloc = con.execute(
            "SELECT date, entity, detector, severity FROM dislocation_daily"
        ).fetchdf()
        if not disloc.empty:
            disloc["date"] = pd.to_datetime(disloc["date"])

        n_attr, n_lessons = 0, 0
        attr_rows = []
        for o in scored.to_dict("records"):
            dv = data_validity_for(disloc, o.get("entity"),
                                   o.get("data_known_at"), o.get("exit_ts"))
            ax = classify_axes(o, dv)
            headline = headline_class(ax)
            lesson_id = None
            if run_llm and n_lessons < MAX_LESSONS_PER_RUN:
                packet = build_packet(o, ax, headline)
                lesson = generate_lesson(packet)
                if lesson:
                    lesson_id = f"L_{o['outcome_id']}"
                    append_lesson({
                        "event": "lesson", "lesson_id": lesson_id,
                        "outcome_id": o["outcome_id"], "entity": o.get("entity"),
                        "headline_class": headline, "axes": ax, **lesson,
                        "created_ts": datetime.now().isoformat(timespec="seconds"),
                    })
                    n_lessons += 1
            attr_rows.append({
                "outcome_id": o["outcome_id"], "gap_id": o.get("gap_id"),
                "role": o.get("role"), "entity": o.get("entity"), **ax,
                "headline_class": headline, "attributed_at": datetime.now(),
                "attribution_version": ATTRIBUTION_VERSION, "lesson_id": lesson_id,
            })
            n_attr += 1

        if attr_rows:
            df = pd.DataFrame(attr_rows)
            con.register("attr_new", df)
            con.execute("INSERT INTO outcome_attribution BY NAME SELECT * FROM attr_new")
            con.unregister("attr_new")
        log(f"attributed {n_attr} matured outcome(s); {n_lessons} lesson(s) written "
            f"(llm={'on' if run_llm else 'off'})")
        return 0
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Attribute matured outcomes (deterministic axes + gated Fable lessons).")
    ap.add_argument("--loop-db", default=None)
    ap.add_argument("--llm", action="store_true",
                    help="generate Fable lessons (also honored via ASADO_RUN_ATTRIBUTION_LLM=1)")
    args = ap.parse_args()
    run_llm = args.llm or os.getenv("ASADO_RUN_ATTRIBUTION_LLM") == "1"
    return run(args.loop_db, run_llm)


if __name__ == "__main__":
    raise SystemExit(main())
