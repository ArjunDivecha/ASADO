#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: build_fable_connections.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    (read-only) family_ranks_daily, dislocation_daily, gap_episodes +
    gap_episode_marks, sovereign_signals, sov_rating_changes,
    market_implied_signals, eco_surprise_signals, etf_flow_signals,
    forward_calendar, country_returns_monthly.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
    (attached read-only as `asado`) commodity_panel Pink Sheet 3m aggregates.
- Neo4j @ bolt://localhost:7687 (read-only queries; fail-soft if down):
    SIMILAR_TO fundamental twins, LEADS lead-lag edges, TRADES_WITH partners.
- /Users/arjundivecha/Dropbox/AAA Backup/.env.txt  (ANTHROPIC_API_KEY)

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/fable/connections_YYYY_MM_DD.json
    Dated (by DATA AS-OF, not wall-clock) connections artifact: the evidence
    packet hash, the model id, and 3-7 structured CONJECTURE connections.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/fable/connections_latest.json
    Copy of the newest artifact (what build_cockpit_data.py reads).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/fable/packet_YYYY_MM_DD.json
    The exact evidence packet sent (audit trail; also dated by data as-of).

VERSION: 1.0
LAST UPDATED: 2026-07-01
AUTHOR: Arjun Divecha (built by agent session, Frontend Alpha Rethink —
        "Fable's Desk" non-deterministic connection pass)

DESCRIPTION:
The one deliberately NON-deterministic step in the nightly loop. Everything
else in ASADO is a deterministic detector or a harness-verdicted signal;
this step hands a bounded, custody-scrubbed snapshot of tonight's warehouse
state — cross-family ranks, dislocations, open gaps, sovereign/vol/surprise
extremes, commodity impulses, and the Neo4j relationship graph (trade
partners, fundamental twins, lead-lag edges) — to Claude Fable and asks it
for the thing only a frontier model can do: find NON-OBVIOUS, cross-surface,
possibly nonlinear connections that no single detector encodes.

EPISTEMIC CONTRACT (non-negotiable):
- Every output is tagged CONJECTURE. It is NOT a signal, NOT a verdict,
  NOT a trade. The harness owns verdicts; the Lab owns claim custody.
- The packet is custody-scrubbed: NO combiner scores, NO optimizer factor
  returns, NO forward-return variables. Fable reasons over the same
  outcome-blind surfaces a human analyst would see, plus trailing returns.
- Each connection must cite the packet evidence it joins and propose a
  falsifiable check — the bridge into the existing Lab/harness custody path.

COST / GATING:
- One Anthropic API call per night (~25KB in, <=4K tokens out).
- Set ASADO_SKIP_FABLE=1 to disable in the nightly job (exit 2 = PARTIAL,
  the loop treats it as a warning). Missing API key also exits 2, loudly.
- Model: latest claude-fable-* from the Models API; override with
  ASADO_FABLE_MODEL.

DEPENDENCIES:
- duckdb, pandas, requests (project venv); neo4j optional (fail-soft)

USAGE:
 python scripts/loop/build_fable_connections.py          # nightly run
 python scripts/loop/build_fable_connections.py --check  # show latest artifact
 python scripts/loop/build_fable_connections.py --dry-run # build+print packet, no API call
=============================================================================
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.loop.loopdb import LOOP_DIR, T2_UNIVERSE, loop_connection

BASE_DIR = Path(__file__).resolve().parent.parent.parent
FABLE_DIR = LOOP_DIR / "fable"
ENV_FILE = Path.home() / "Dropbox" / "AAA Backup" / ".env.txt"

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "mythos2026")

MAX_OUTPUT_TOKENS = 12000   # 3-7 rich connections via tool use; truncation = empty input
API_TIMEOUT_S = 600

# Custody scrub: these key patterns must never reach the model (optimizer
# outputs / forward returns). Mirrors cos_chat_service._FORBIDDEN_EVIDENCE_RE.
_FORBIDDEN_RE = re.compile(
    r"combiner|factor_returns|factor_top20|country_factor_attribution"
    r"|(^|_)\d+[a-z]{0,2}ret($|_)|forward_return|_ret_lead|fwd_ret",
    re.IGNORECASE,
)

SYSTEM_PROMPT = """\
You are Fable, the connection-finding engine of the ASADO macro warehouse — \
34 country equity markets, a hybrid DuckDB + Neo4j system built for exactly \
one question: what does the data know that is NOT embedded in the price?

You receive tonight's bounded evidence packet: cross-family signal ranks, \
Triptych point-in-time conditional-history priors (which factor decile each \
country sits in and what that decile historically preceded — PRIORS, not \
evidence), detector dislocations, open price-discovery gaps, sovereign \
credit / FX-vol / macro-surprise extremes, commodity impulses, the forward \
event calendar, and the relationship graph (bilateral trade partners, \
fundamental twins, lead-lag edges). Deterministic detectors already scan \
each surface alone. Your job is \
the part they cannot do: find NON-OBVIOUS connections that only appear when \
you join surfaces — transmission chains through the trade/banking graph, \
second-order effects, tension between what different markets are pricing, \
nonlinear setups where two moderate readings compound into one large exposure.

Rules — these are hard constraints:
1. Every connection must JOIN at least two distinct surfaces or entities and
   cite the specific packet values it uses (numbers, not vibes).
2. Prefer surprising, structural, or chained mechanisms over restating what a
   single detector already flags. A good connection is one a careful human
   with one screen would miss.
3. Everything you produce is CONJECTURE. No trade instructions, no position
   sizes, no verdicts. The skeptic harness owns validation.
4. For each connection, propose one concrete falsifiable check that the
   existing harness or an event study could run.
5. If the packet genuinely contains no interesting cross-surface structure
   tonight, return fewer connections — never pad.
6. When — and only when — a connection is concrete enough to stand as a single-
   market, directional, tradable recommendation, attach a `claim` object: the one
   `entity` (from the 34-country universe), `direction` (long/short), horizon in
   trading days (`horizon_days` ∈ 5/21/63/126), the ETF you would express it
   through (`expression_ticker`), and a concrete `invalidation` level or
   condition. Omit `claim` for pure context, framing, or relative/multi-leg ideas
   that are not one clean directional bet. A claim is how a conjecture becomes
   something the outcome scorer can later grade — so attach one only if you would
   stand behind being measured on it.
7. The packet's `prior_lessons` are what the learning loop has already concluded
   from matured, net-of-cost outcomes. Weigh them: do NOT re-propose a mechanism
   already shown to lead in index space but fail to capture in ETF space, and
   prefer setups the lessons mark as capturable. Learning from prior failures is
   part of the job, not optional.

Record your 3-7 connections by calling the record_connections tool."""

# Structured output via forced tool use: the API returns parsed JSON matching
# this schema — no free-text JSON parsing (which broke on escaping in v1 tests).
CONNECTIONS_TOOL = {
    "name": "record_connections",
    "description": "Record tonight's cross-surface CONJECTURE connections.",
    "input_schema": {
        "type": "object",
        "required": ["connections"],
        "properties": {
            "connections": {
                "type": "array",
                "minItems": 1,
                "maxItems": 7,
                "items": {
                    "type": "object",
                    "required": ["title", "entities", "surfaces", "direction_hint",
                                 "mechanism", "why_non_obvious", "confidence",
                                 "falsifiable_check", "horizon"],
                    "properties": {
                        "title": {"type": "string", "maxLength": 90},
                        "entities": {"type": "array", "items": {"type": "string"}},
                        "surfaces": {
                            "type": "array",
                            "items": {"type": "string",
                                      "enum": ["families", "gaps", "sovereign", "fx_vol",
                                               "surprises", "commodities", "graph",
                                               "calendar", "flows", "returns",
                                               "dislocations", "triptych"]},
                        },
                        "direction_hint": {"type": "string",
                                           "enum": ["long", "short", "relative", "unclear"]},
                        "mechanism": {"type": "string"},
                        "why_non_obvious": {"type": "string"},
                        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                        "falsifiable_check": {"type": "string"},
                        "horizon": {"type": "string", "enum": ["days", "weeks", "months"]},
                        # Optional evaluable claim contract: present only when the
                        # connection is one clean directional, tradable bet. This is
                        # what lets the outcome scorer grade Fable's own calls.
                        "claim": {
                            "type": "object",
                            "required": ["entity", "direction", "horizon_days"],
                            "properties": {
                                "entity": {"type": "string"},
                                "direction": {"type": "string", "enum": ["long", "short"]},
                                "horizon_days": {"type": "integer", "enum": [5, 21, 63, 126]},
                                "expression_ticker": {"type": "string"},
                                "invalidation": {"type": "string"},
                            },
                        },
                    },
                },
            },
        },
    },
}


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} [fable] {msg}", flush=True)


def load_api_key() -> str | None:
    env_key = os.getenv("ANTHROPIC_API_KEY")
    if not ENV_FILE.exists():
        return env_key
    key = None
    for line in ENV_FILE.read_text(errors="ignore").splitlines():
        m = re.match(r"^ANTHROPIC_API_KEY=(.+)$", line.strip())
        if m:
            value = re.sub(r"\s+#.*$", "", m.group(1)).strip().strip("\"'")
            if value.startswith("sk-ant-api"):
                key = value
    return key or env_key


def resolve_fable_model(api_key: str) -> str:
    requested = os.getenv("ASADO_FABLE_MODEL")
    if requested:
        return requested
    r = requests.get("https://api.anthropic.com/v1/models",
                     headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
                     timeout=30)
    r.raise_for_status()
    models = [m for m in r.json().get("data", []) if m.get("id", "").startswith("claude-fable-")]
    if not models:
        raise RuntimeError("No claude-fable-* model in the Anthropic Models API "
                           "(set ASADO_FABLE_MODEL to override).")
    models.sort(key=lambda m: m.get("created_at") or "")
    return models[-1]["id"]


def _table_exists(con, name: str) -> bool:
    return bool(con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [name]
    ).fetchone()[0])


def _tidy_extremes(con, table: str, threshold: float, keep: int = 20) -> list[dict]:
    """Latest-date rows of a tidy z-score table with |value| >= threshold."""
    if not _table_exists(con, table):
        return []
    df = con.execute(f"""
        SELECT country, variable, round(value, 2) AS z FROM {table}
        WHERE date = (SELECT max(date) FROM {table})
          AND variable LIKE '%_Z%' AND abs(value) >= ?
        ORDER BY abs(value) DESC LIMIT ?
    """, [threshold, keep]).fetchdf()
    return df.to_dict("records")


# --------------------------------------------------------------------------- #
# Packet assembly (each block fail-soft: one missing surface never blanks it)
# --------------------------------------------------------------------------- #
def _block(fn, label, default):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        log(f"packet block {label} unavailable: {e}")
        return default


def packet_family_ranks(con) -> dict:
    """Latest cross-family ranks WITHOUT the combiner column (custody)."""
    if not _table_exists(con, "family_ranks_daily"):
        return {}
    df = con.execute("""
        WITH latest AS (SELECT family, max(date) d FROM family_ranks_daily GROUP BY family)
        SELECT f.family, f.country, f.rank, f.universe_n
        FROM family_ranks_daily f JOIN latest l ON f.family=l.family AND f.date=l.d
        WHERE f.family != 'combiner'
    """).fetchdf()
    out: dict[str, dict] = {}
    for r in df.itertuples(index=False):
        out.setdefault(r.country, {})[r.family] = f"{int(r.rank)}/{int(r.universe_n)}"
    return out


def packet_triptych(con) -> list[dict]:
    """Top Triptych PIT priors (2026-07-02). Conditional history, PRIOR only —
    the queue is already PIT-thresholded and custody-safe (no forward-return
    keys; bucket averages are historical conditional means, not live returns)."""
    if not _table_exists(con, "triptych_review_queue"):
        return []
    df = con.execute("""
        SELECT country, factor, normalization, return_mode, horizon_months,
               current_decile, implied_direction,
               round(confidence_score, 2) AS confidence,
               round(ic_t_stat, 1) AS ic_t,
               round(cur_bucket_hit_rate, 2) AS hist_hit_rate
        FROM triptych_review_queue
        WHERE threshold_mode = 'pit'
        ORDER BY priority DESC LIMIT 12
    """).fetchdf()
    return df.to_dict("records")


def packet_dislocations(con) -> list[dict]:
    df = con.execute("""
        SELECT detector, entity, direction, round(severity,2) AS severity,
               days_active, status, components_json
        FROM dislocation_daily
        WHERE date = (SELECT max(date) FROM dislocation_daily)
          AND archetype != 'degraded'
        ORDER BY abs(severity) DESC LIMIT 15
    """).fetchdf()
    rows = []
    for r in df.itertuples(index=False):
        reading = ""
        try:
            reading = (json.loads(r.components_json) or {}).get("reading", "")
        except Exception:  # noqa: BLE001
            pass
        rows.append({"detector": r.detector, "entity": r.entity, "direction": r.direction,
                     "severity": r.severity, "days_active": int(r.days_active or 0),
                     "status": r.status, "reading": reading})
    return rows


def packet_gaps(con) -> list[dict]:
    if not _table_exists(con, "gap_episode_marks"):
        return []
    df = con.execute("""
        SELECT m.entity, e.direction, e.gap_class, e.horizon_bucket,
               round(m.tension_score_current,3) AS tension,
               m.absorption_state, m.days_active, e.mechanism_text
        FROM gap_episode_marks m JOIN gap_episodes e ON m.gap_id=e.gap_id
        WHERE m.date = (SELECT max(date) FROM gap_episode_marks)
          AND COALESCE(e.status,'open')='open'
        ORDER BY m.tension_score_current DESC NULLS LAST LIMIT 10
    """).fetchdf()
    return df.to_dict("records")


def packet_sovereign(con) -> dict:
    out: dict = {}
    if _table_exists(con, "sov_rating_changes"):
        df = con.execute("""
            SELECT date, country, agency, delta FROM sov_rating_changes
            WHERE date >= current_date - INTERVAL 90 DAY ORDER BY date DESC
        """).fetchdf()
        out["rating_changes_90d"] = [
            {"date": str(r.date)[:10], "country": r.country, "agency": r.agency,
             "delta": int(r.delta)} for r in df.itertuples(index=False)]
    if _table_exists(con, "sovereign_signals"):
        df = con.execute("""
            SELECT country, variable, round(value,1) AS value FROM sovereign_signals
            WHERE date = (SELECT max(date) FROM sovereign_signals)
              AND ((variable='SOV_CDS_SLOPE_BP' AND value < 0)
                   OR (variable LIKE '%_Z252' AND abs(value) >= 2))
            ORDER BY variable, value LIMIT 25
        """).fetchdf()
        out["curve_and_z_extremes"] = df.to_dict("records")
    return out


def packet_calendar(con) -> list[dict]:
    if not _table_exists(con, "forward_calendar"):
        return []
    df = con.execute("""
        SELECT event_date, label, category, countries_affected FROM forward_calendar
        WHERE event_date BETWEEN current_date AND current_date + INTERVAL 14 DAY
        ORDER BY event_date LIMIT 20
    """).fetchdf()
    return [{"date": str(r.event_date)[:10], "label": r.label, "category": r.category,
             "countries": r.countries_affected} for r in df.itertuples(index=False)]


def packet_commodities(con) -> list[dict]:
    df = con.execute("""
        SELECT variable, round(value,1) AS ret_3m_pct FROM asado.commodity_panel
        WHERE variable LIKE 'WB_CMDTY_I%_RET_3M_PCT'
          AND date = (SELECT max(date) FROM asado.commodity_panel
                      WHERE variable LIKE 'WB_CMDTY_I%_RET_3M_PCT')
        ORDER BY abs(value) DESC LIMIT 12
    """).fetchdf()
    return df.to_dict("records")


def packet_returns(con) -> dict:
    df = con.execute("""
        SELECT country, round(return_1m*100,2) AS ret_1m_pct FROM country_returns_monthly
        WHERE date = (SELECT max(date) FROM country_returns_monthly)
    """).fetchdf()
    return {r.country: r.ret_1m_pct for r in df.itertuples(index=False)
            if r.country in T2_UNIVERSE}


def packet_graph() -> dict:
    """Neo4j relationship context (fail-soft — graph down = noted, not fatal)."""
    from neo4j import GraphDatabase
    driver = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH,
                                  connection_timeout=10)
    out: dict = {}
    try:
        with driver.session() as s:
            out["fundamental_twins"] = [
                dict(r) for r in s.run(
                    "MATCH (a:Country)-[e:SIMILAR_TO]->(b:Country) "
                    "RETURN a.t2_name AS country, b.t2_name AS twin, "
                    "round(e.sim, 3) AS cosine ORDER BY e.sim DESC LIMIT 20")]
            out["leadlag_edges"] = [
                dict(r) for r in s.run(
                    "MATCH (a:Country)-[e:LEADS]->(b:Country) "
                    "RETURN a.t2_name AS leader, b.t2_name AS follower, "
                    "round(e.corr, 3) AS lag1_corr ORDER BY e.corr DESC LIMIT 20")]
            out["top_trade_edges"] = [
                dict(r) for r in s.run(
                    "MATCH (a:Country)-[e:TRADES_WITH]->(b:Country) "
                    "WHERE e.total_trade_usd IS NOT NULL "
                    "RETURN a.t2_name AS reporter, b.t2_name AS partner, "
                    "round(e.total_trade_usd/1e9, 1) AS trade_bn "
                    "ORDER BY e.total_trade_usd DESC LIMIT 25")]
    finally:
        driver.close()
    return out


def scrub(obj):
    """Drop any custody-forbidden key subtree (defense in depth — the packet
    should never contain one, but a source column rename must not leak)."""
    if isinstance(obj, dict):
        return {k: scrub(v) for k, v in obj.items() if not _FORBIDDEN_RE.search(str(k))}
    if isinstance(obj, list):
        return [scrub(x) for x in obj]
    return obj


def packet_lessons() -> list[dict]:
    """Digest of prior learning-loop lessons (Stage 3a): the 10 most recent plus
    up to 10 high-confidence, deduped and compacted. Empty until the attribution
    step has written lessons. This is how tonight's conjecture learns from what
    has already failed net-of-cost."""
    ledger = BASE_DIR / "ledgers" / "lesson_ledger.jsonl"
    if not ledger.exists():
        return []
    recs = []
    for line in ledger.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:  # noqa: BLE001
            continue
        if r.get("event") == "lesson":
            recs.append(r)
    recent = recs[-10:]
    high = [r for r in recs if r.get("confidence") == "high"][-10:]
    seen, digest = set(), []
    for r in recent + high:
        lid = r.get("lesson_id")
        if lid in seen:
            continue
        seen.add(lid)
        digest.append({
            "entity": r.get("entity"), "headline_class": r.get("headline_class"),
            "mechanism_cluster": (r.get("axes") or {}).get("data_validity") and r.get("mechanism_cluster"),
            "diagnosis": str(r.get("diagnosis", ""))[:280],
            "proposed_adjustment": str(r.get("proposed_adjustment", ""))[:220],
            "confidence": r.get("confidence"),
        })
    return digest


def build_packet(con) -> dict:
    as_of = con.execute("SELECT max(date) FROM dislocation_daily").fetchone()[0]
    packet = {
        "as_of": str(as_of),
        "universe": T2_UNIVERSE,
        "family_ranks_note": "rank 1 = strongest LONG lean under each family's "
                             "registered direction; rank/N. Families: leadlag, "
                             "graph_twohop, graph_bank, twins, cpi_rev (monthly), "
                             "etf_contra (contrarian), tot_impulse (untested context).",
        "family_ranks": _block(lambda: packet_family_ranks(con), "family_ranks", {}),
        "triptych_priors_note": "PIT conditional-history priors from the nightly "
                                "factor-bucket sweep: current decile of each factor's "
                                "own point-in-time distribution + what that decile "
                                "historically preceded. PRIORS for triage, not evidence.",
        "triptych_priors": _block(lambda: packet_triptych(con), "triptych", []),
        "dislocations_tonight": _block(lambda: packet_dislocations(con), "dislocations", []),
        "open_gap_episodes": _block(lambda: packet_gaps(con), "gaps", []),
        "sovereign": _block(lambda: packet_sovereign(con), "sovereign", {}),
        "fx_vol_stress_z_extremes": _block(
            lambda: _tidy_extremes(con, "market_implied_signals", 2.0), "fx_vol", []),
        "eco_surprise_z_extremes": _block(
            lambda: _tidy_extremes(con, "eco_surprise_signals", 1.5), "surprises", []),
        "etf_flow_z_extremes": _block(
            lambda: _tidy_extremes(con, "etf_flow_signals", 2.0), "flows", []),
        "commodity_3m_returns_pct": _block(lambda: packet_commodities(con), "commodities", []),
        "country_returns_1m_pct": _block(lambda: packet_returns(con), "returns", {}),
        "forward_calendar_14d": _block(lambda: packet_calendar(con), "calendar", []),
        "graph": _block(packet_graph, "neo4j_graph", {"note": "Neo4j unavailable tonight"}),
        "prior_lessons_note": "What the learning loop has already concluded from matured, "
                              "net-of-cost outcomes. Weigh these: do not re-propose a "
                              "mechanism already shown to fail capture, and prefer setups "
                              "the lessons suggest are capturable.",
        "prior_lessons": _block(packet_lessons, "lessons", []),
    }
    return scrub(packet)


# --------------------------------------------------------------------------- #
def call_fable(packet: dict, api_key: str) -> tuple[list[dict], str]:
    model = resolve_fable_model(api_key)
    log(f"calling {model} ...")
    body = {
        "model": model,
        "max_tokens": MAX_OUTPUT_TOKENS,
        "system": SYSTEM_PROMPT,
        "tools": [CONNECTIONS_TOOL],
        "tool_choice": {"type": "tool", "name": "record_connections"},
        "messages": [{"role": "user", "content":
                      "Tonight's evidence packet (bounded JSON):\n"
                      + json.dumps(packet, ensure_ascii=True, default=str)[:60000]}],
    }
    r = requests.post("https://api.anthropic.com/v1/messages",
                      headers={"x-api-key": api_key,
                               "anthropic-version": "2023-06-01",
                               "content-type": "application/json"},
                      json=body, timeout=API_TIMEOUT_S)
    r.raise_for_status()
    resp = r.json()
    stop = resp.get("stop_reason")
    if stop == "max_tokens":
        raise RuntimeError(f"Fable output truncated at {MAX_OUTPUT_TOKENS} tokens — "
                           "raise MAX_OUTPUT_TOKENS.")
    tool_blocks = [b for b in resp.get("content", []) if b.get("type") == "tool_use"]
    if not tool_blocks:
        raise RuntimeError(f"Fable returned no record_connections tool call "
                           f"(stop_reason={stop}).")
    conns = (tool_blocks[0].get("input") or {}).get("connections")
    if not isinstance(conns, list) or not conns:
        raise RuntimeError(f"Fable tool call missing a non-empty 'connections' list "
                           f"(stop_reason={stop}, input_keys="
                           f"{sorted((tool_blocks[0].get('input') or {}).keys())}).")
    required = {"title", "entities", "surfaces", "mechanism", "confidence",
                "falsifiable_check"}
    for i, c in enumerate(conns):
        missing = required - set(c)
        if missing:
            raise RuntimeError(f"connection[{i}] missing fields: {sorted(missing)}")
        c["id"] = f"FC_{packet['as_of'].replace('-', '')}_{i + 1:02d}"
        c["epistemic_tag"] = "CONJECTURE"
    return conns, model


def write_artifacts(packet: dict, conns: list[dict], model: str) -> Path:
    FABLE_DIR.mkdir(parents=True, exist_ok=True)
    tag = packet["as_of"].replace("-", "_")
    packet_path = FABLE_DIR / f"packet_{tag}.json"
    packet_path.write_text(json.dumps(packet, indent=1, ensure_ascii=False, default=str))
    artifact = {
        "as_of": packet["as_of"],
        "generated_ts": datetime.now().isoformat(timespec="seconds"),
        "model": model,
        "packet_file": str(packet_path),
        "packet_sha256": hashlib.sha256(
            json.dumps(packet, sort_keys=True, default=str).encode()).hexdigest(),
        "connections": conns,
        "note": "Non-deterministic Fable synthesis over tonight's warehouse + graph. "
                "CONJECTURE only — the harness owns verdicts; nothing here is a trade.",
    }
    out = FABLE_DIR / f"connections_{tag}.json"
    out.write_text(json.dumps(artifact, indent=1, ensure_ascii=False, default=str))
    shutil.copyfile(out, FABLE_DIR / "connections_latest.json")
    return out


def _load_etf_map() -> dict:
    d = json.loads((BASE_DIR / "config" / "etf_t2_map.json").read_text())
    m = d.get("map", d)
    return {k: v["primary"] for k, v in m.items() if v.get("primary")}


def write_claims(conns: list[dict], packet: dict, model: str) -> int:
    """Append tonight's structured Fable CLAIMS to the loop-DB `fable_claims`
    table so the outcome scorer can later grade Fable's own directional calls
    (adapter 2 of the claim contract). Only connections carrying a well-formed
    `claim` are stored; a malformed claim is skipped with a warning — the
    connection still stands as a CONJECTURE in the JSON artifact. Idempotent per
    emitted_at (DELETE-by-date then insert). Fail-soft at the call site."""
    etf_map = _load_etf_map()
    as_of = packet["as_of"]
    packet_sha = hashlib.sha256(
        json.dumps(packet, sort_keys=True, default=str).encode()).hexdigest()
    rows = []
    for c in conns:
        claim = c.get("claim")
        if not isinstance(claim, dict):
            continue
        entity, direction, hd = claim.get("entity"), claim.get("direction"), claim.get("horizon_days")
        if entity not in T2_UNIVERSE or direction not in ("long", "short") or hd not in (5, 21, 63, 126):
            log(f"  skipping malformed claim on {c.get('id')}: "
                f"entity={entity} dir={direction} horizon_days={hd}")
            continue
        rows.append({
            "claim_id": f"{c['id']}_claim", "emitted_at": as_of,
            "connection_id": c["id"], "entity": entity, "direction": direction,
            "horizon_days": int(hd),
            "expression_ticker": claim.get("expression_ticker") or etf_map.get(entity),
            "invalidation": claim.get("invalidation"), "mechanism": c.get("mechanism"),
            "confidence": c.get("confidence"), "title": c.get("title"),
            "model": model, "packet_sha256": packet_sha, "created_ts": datetime.now(),
        })
    con = loop_connection(read_only=False)
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS fable_claims (
              claim_id VARCHAR, emitted_at DATE, connection_id VARCHAR, entity VARCHAR,
              direction VARCHAR, horizon_days INTEGER, expression_ticker VARCHAR,
              invalidation VARCHAR, mechanism VARCHAR, confidence VARCHAR, title VARCHAR,
              model VARCHAR, packet_sha256 VARCHAR, created_ts TIMESTAMP
            )
        """)
        con.execute("DELETE FROM fable_claims WHERE emitted_at = ?", [as_of])
        if rows:
            df = pd.DataFrame(rows)
            con.register("fc_new", df)
            con.execute("INSERT INTO fable_claims BY NAME SELECT * FROM fc_new")
            con.unregister("fc_new")
    finally:
        con.close()
    log(f"fable_claims: stored {len(rows)} evaluable claim(s) for {as_of}")
    return len(rows)


def check() -> int:
    latest = FABLE_DIR / "connections_latest.json"
    if not latest.exists():
        print("No Fable connections artifact yet.")
        return 1
    d = json.loads(latest.read_text())
    print(f"as_of={d.get('as_of')}  model={d.get('model')}  "
          f"connections={len(d.get('connections', []))}")
    for c in d.get("connections", []):
        print(f"  [{c.get('confidence', '?'):6s}] {c.get('title')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Nightly Fable connection-finding pass")
    ap.add_argument("--check", action="store_true", help="show the latest artifact")
    ap.add_argument("--dry-run", action="store_true",
                    help="assemble + print the packet, no API call, no writes")
    args = ap.parse_args()
    if args.check:
        return check()

    if os.getenv("ASADO_SKIP_FABLE") == "1":
        log("ASADO_SKIP_FABLE=1 — skipping (PARTIAL).")
        return 2

    con = loop_connection(read_only=True)
    try:
        packet = build_packet(con)
    finally:
        con.close()
    size_kb = len(json.dumps(packet, default=str)) // 1024
    log(f"packet assembled: as_of={packet['as_of']}, {size_kb} KB")

    if args.dry_run:
        print(json.dumps(packet, indent=1, ensure_ascii=False, default=str))
        return 0

    api_key = load_api_key()
    if not api_key:
        log("ANTHROPIC_API_KEY unavailable — skipping Fable pass (PARTIAL).")
        return 2

    conns, model = call_fable(packet, api_key)
    out = write_artifacts(packet, conns, model)
    log(f"{len(conns)} connections -> {out}")
    for c in conns:
        log(f"  [{c['confidence']:6s}] {c['title']}")
    # Persist the evaluable subset as claims (fail-soft: a claims-write failure
    # must not fail an otherwise-successful synthesis).
    try:
        write_claims(conns, packet, model)
    except Exception as exc:  # noqa: BLE001
        log(f"fable_claims write failed (non-fatal): {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
