#!/usr/bin/env python3
"""FastAPI service for the ASADO Chief-of-Staff cockpit.

The service intentionally keeps deterministic cockpit answers in front of the
model. Opus is used as an external synthesis agent for open-ended questions,
with only bounded, read-only evidence passed into the prompt.
"""

from __future__ import annotations

import html
import json
import os
import re
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import requests
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


BASE_DIR = Path(__file__).resolve().parent.parent
HERE = Path(__file__).resolve().parent
DATA_PATH = HERE / "cockpit_data.json"
ENV_FILE = Path.home() / "Dropbox" / "AAA Backup" / ".env.txt"


class ChatContext(BaseModel):
    active_view: str | None = None
    selected_country: str | None = None
    selected_gap_id: str | None = None
    selected_signal_id: str | None = None
    map_layer: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    thread_id: str | None = None
    mode: Literal["auto", "status", "research"] = "auto"
    model_tier: Literal["fast", "standard", "deep"] = "standard"
    context: ChatContext = Field(default_factory=ChatContext)


class Citation(BaseModel):
    label: str
    source: str
    date: str | None = None


class UIAction(BaseModel):
    type: Literal["focus_view", "focus_country", "focus_gap", "focus_signal", "set_layer"]
    view: str | None = None
    country: str | None = None
    gap_id: str | None = None
    signal: str | None = None
    layer: str | None = None


class ChatResponse(BaseModel):
    answer_html: str
    answer_text: str
    mode_used: str
    model: str | None = None
    external_agent: str | None = None
    fallback: bool = False
    citations: list[Citation] = Field(default_factory=list)
    ui_actions: list[UIAction] = Field(default_factory=list)
    freshness: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int = 0


app = FastAPI(title="ASADO Chief-of-Staff Chat", version="0.1")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@lru_cache(maxsize=1)
def _load_cockpit_data_cached(mtime_ns: int) -> dict[str, Any]:
    del mtime_ns
    if not DATA_PATH.exists():
        return {}
    return json.loads(DATA_PATH.read_text())


def load_cockpit_data() -> dict[str, Any]:
    mtime_ns = DATA_PATH.stat().st_mtime_ns if DATA_PATH.exists() else 0
    return _load_cockpit_data_cached(mtime_ns)


def _esc(value: Any) -> str:
    if value is None:
        return "—"
    return html.escape(str(value), quote=True)


def _text_to_html(text: str) -> str:
    safe = html.escape(text or "", quote=True)
    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
    return "<br>".join(safe.splitlines())


def _plain(html_text: str) -> str:
    return re.sub(r"<[^>]+>", "", html_text or "").strip()


def _countries(data: dict[str, Any]) -> set[str]:
    names = set((data.get("countries") or {}).keys())
    for region in data.get("map") or []:
        for tile in region.get("tiles") or []:
            if tile.get("country"):
                names.add(tile["country"])
    return names


def _signal_names(data: dict[str, Any]) -> set[str]:
    return {row.get("name") for row in (data.get("signals") or {}).get("registry") or [] if row.get("name")}


def _gap_ids(data: dict[str, Any]) -> set[str]:
    gap = data.get("gap_engine") or {}
    ids = {row.get("gap_id") for row in gap.get("top") or [] if row.get("gap_id")}
    for bucket in (gap.get("by_country") or {}).values():
        primary = bucket.get("primary") or {}
        if primary.get("gap_id"):
            ids.add(primary["gap_id"])
        for row in bucket.get("all") or []:
            if row.get("gap_id"):
                ids.add(row["gap_id"])
    return ids


def _validate_actions(data: dict[str, Any], actions: list[UIAction]) -> list[UIAction]:
    valid_countries = _countries(data)
    valid_signals = _signal_names(data)
    valid_gaps = _gap_ids(data)
    valid_views = {"overview", "health", "signals", "signal", "country", "gap", "dislo", "tail",
                   "desk_discovery", "desk_analogs", "desk_triage", "desk_rulings",
                   "desk_prospective", "desk_graveyard"}
    valid_layers = {"gap", "return", "dislocation", "signal"}
    out: list[UIAction] = []
    for action in actions:
        if action.type == "focus_country" and action.country in valid_countries:
            out.append(action)
        elif action.type == "focus_gap" and action.gap_id in valid_gaps:
            out.append(action)
        elif action.type == "focus_signal" and action.signal in valid_signals:
            out.append(action)
        elif action.type == "focus_view" and action.view in valid_views:
            out.append(action)
        elif action.type == "set_layer" and action.layer in valid_layers:
            out.append(action)
    return out


def _citation(label: str, source: str, date: str | None = None) -> Citation:
    return Citation(label=label, source=source, date=date)


def _freshness(data: dict[str, Any]) -> dict[str, Any]:
    gap = data.get("gap_engine") or {}
    gov = data.get("governance") or {}
    return {
        "generated_ts": (data.get("meta") or {}).get("generated_ts"),
        "gap_status": gap.get("status", "missing"),
        "gap_as_of": gap.get("as_of"),
        "governance": gov.get("overall"),
        "governance_as_of": gov.get("as_of"),
    }


def _match_country(question: str, data: dict[str, Any]) -> str | None:
    q = question.lower()
    for country in sorted(_countries(data), key=len, reverse=True):
        if country.lower() in q:
            return country
    aliases = {"usa": "U.S.", "us": "U.S.", "uk": "U.K.", "south korea": "Korea"}
    for alias, country in aliases.items():
        if re.search(rf"\b{re.escape(alias)}\b", q) and country in _countries(data):
            return country
    return None


def _top_gap(data: dict[str, Any]) -> dict[str, Any] | None:
    rows = (data.get("gap_engine") or {}).get("top") or []
    return rows[0] if rows else None


def _country_gap(country: str, data: dict[str, Any]) -> dict[str, Any] | None:
    bucket = ((data.get("gap_engine") or {}).get("by_country") or {}).get(country) or {}
    return bucket.get("primary")


def deterministic_answer(question: str, data: dict[str, Any]) -> ChatResponse | None:
    q = question.lower()
    citations = [_citation("cockpit_data", "cos_mockups/cockpit_data.json", (data.get("gap_engine") or {}).get("as_of"))]
    start = time.time()

    if re.search(r"(what should i|care about|brief me|three things|priorit|matter|today|overview)", q):
        today = data.get("today") or []
        bits = []
        actions = [UIAction(type="focus_view", view="overview")]
        for row in today[:3]:
            headline = _esc(row.get("headline"))
            why = _esc(row.get("why"))
            bits.append(f"<b>{headline}</b><br>{why}")
        if not bits:
            bits.append("No promoted cockpit items are available in the current payload.")
        html_answer = "Today:<br><br>" + "<br><br>".join(bits)
        return ChatResponse(
            answer_html=html_answer,
            answer_text=_plain(html_answer),
            mode_used="status",
            citations=citations,
            ui_actions=_validate_actions(data, actions),
            freshness=_freshness(data),
            latency_ms=int((time.time() - start) * 1000),
        )

    if re.search(r"(health|scorecard|governance|amber|red)", q):
        gov = data.get("governance") or {}
        dims = gov.get("dimensions") or []
        worst = gov.get("overall", "unknown")
        problem = [d for d in dims if d.get("status") in {"red", "amber"}]
        rows = "<br>".join(
            f"<b>{_esc(d.get('name'))}</b>: {_esc(d.get('status'))} — {_esc(d.get('detail'))}"
            for d in problem[:6]
        ) or "No red/amber dimensions in the current scorecard."
        html_answer = f"Governance is <b>{_esc(str(worst).upper())}</b>.<br><br>{rows}"
        return ChatResponse(
            answer_html=html_answer,
            answer_text=_plain(html_answer),
            mode_used="status",
            citations=[_citation("governance_scorecard", "cockpit_data.governance", gov.get("as_of"))],
            ui_actions=[UIAction(type="focus_view", view="health")],
            freshness=_freshness(data),
            latency_ms=int((time.time() - start) * 1000),
        )

    if re.search(r"(gap|price discovery|unabsorbed|absorption|not absorbing|price not know|price has not|not figured out)", q):
        gap = _top_gap(data)
        if not gap:
            html_answer = "UNKNOWN/STALE: I do not see a fresh promoted price-discovery gap in the cockpit payload."
            return ChatResponse(
                answer_html=html_answer,
                answer_text=_plain(html_answer),
                mode_used="status",
                citations=citations,
                ui_actions=[UIAction(type="focus_view", view="dislo")],
                freshness=_freshness(data),
                latency_ms=int((time.time() - start) * 1000),
            )
        unabsorbed = gap.get("unabsorbed_fraction")
        unabsorbed_txt = "—" if unabsorbed is None else f"{round(float(unabsorbed) * 100)}%"
        html_answer = (
            f"The top current gap is <b>{_esc(gap.get('entity'))} {_esc(gap.get('direction'))}</b> "
            f"via <b>{_esc(gap.get('preferred_ticker'))}</b>.<br><br>"
            f"FACT: absorption state is <b>{_esc(gap.get('absorption_state'))}</b>; "
            f"unabsorbed fraction is <b>{unabsorbed_txt}</b>; "
            f"tension score is <b>{_esc(gap.get('tension_score_current'))}</b>.<br>"
            f"INFERENCE: {_esc(gap.get('mechanism_text') or 'world-state and price-state remain in tension')}"
        )
        return ChatResponse(
            answer_html=html_answer,
            answer_text=_plain(html_answer),
            mode_used="status",
            citations=[_citation("gap_episode_marks", "Data/loop/asado_loop.duckdb", gap.get("date"))],
            ui_actions=_validate_actions(data, [UIAction(type="focus_gap", gap_id=gap.get("gap_id"))]),
            freshness=_freshness(data),
            latency_ms=int((time.time() - start) * 1000),
        )

    # --- deterministic UI/navigation intents (mirror the browser router; never spend
    #     Opus on a control command). These MUST precede the country match so e.g.
    #     "Downside if Indonesia keeps falling?" opens the tail panel, not Indonesia. ---
    def _nav(view_or_actions: Any, msg: str, layer: str | None = None) -> ChatResponse:
        acts = [UIAction(type="focus_view", view=view_or_actions)]
        if layer:
            acts.append(UIAction(type="set_layer", layer=layer))
        return ChatResponse(
            answer_html=msg, answer_text=_plain(msg), mode_used="status",
            citations=citations, ui_actions=_validate_actions(data, acts),
            freshness=_freshness(data), latency_ms=int((time.time() - start) * 1000),
        )

    # ANCHORED (re.fullmatch) so an analytical question that merely MENTIONS "discovery
    # lab" / "downside" still falls through to Opus — only the short control command routes.
    qs = q.strip()
    if re.fullmatch(r"(research desk|discovery lab|analog shelf|under triage|blind rulings?|"
                    r"prospective( queue)?|graveyard)\??", qs):
        return _nav("desk_discovery", "Opening the <b>Research Desk</b> — chain-of-custody surfaces: "
                    "drafts, analogs, triage, blind rulings, prospective queue, graveyard controls.")
    if re.fullmatch(r"(downside( if .*)?|tail|drawdown|jst tail|the long[- ]cycle tail)\??", qs):
        return _nav("tail", "The long-cycle <b>tail</b>. Context only — a nominal drawdown mapped to a "
                    "DM-calibrated distribution; it must clear the harness before any sizing.")

    country = _match_country(question, data)
    if country:
        c = ((data.get("countries") or {}).get(country)) or {}
        gap = _country_gap(country, data)
        ret = ((data.get("returns") or {}).get("by_country") or {}).get(country)
        gap_line = ""
        if gap:
            gap_line = (
                f"<br>Active gap: <b>{_esc(gap.get('gap_class'))} {_esc(gap.get('direction'))}</b> "
                f"via <b>{_esc(gap.get('preferred_ticker'))}</b>; "
                f"absorption <b>{_esc(gap.get('absorption_state'))}</b>."
            )
        html_answer = (
            f"Opening <b>{_esc(country)}</b>.<br><br>"
            f"FACT: 10Y {_esc(c.get('y10'))}%, 5Y CDS {_esc(c.get('cds'))}bp, "
            f"2s10s {_esc(c.get('s210'))}, latest 1M return {_esc(ret)}%."
            f"{gap_line}"
        )
        return ChatResponse(
            answer_html=html_answer,
            answer_text=_plain(html_answer),
            mode_used="status",
            citations=citations,
            ui_actions=[UIAction(type="focus_country", country=country)],
            freshness=_freshness(data),
            latency_ms=int((time.time() - start) * 1000),
        )

    # brief / pressure come AFTER the country match (mirror the browser router order),
    # so "where is Brazil" opens Brazil but "where is pressure building" opens the map.
    # Anchored so analytical questions are not stolen from Opus.
    if re.fullmatch(r"(open the full brief|the brief|tonight'?s brief|the dislocations?|"
                    r"tonight'?s dislocations?)\??", qs):
        return _nav("dislo", "Opening tonight's <b>brief</b> — price-discovery gaps first when fresh; "
                    "raw detector firings remain the drilldown substrate.")
    if re.fullmatch(r"(where is pressure building|where'?s the pressure|where is the pressure|"
                    r"pressure|the map|world map)\??", qs):
        return _nav("overview", "Pressure shows on the <b>map</b> (dislocation layer). Click a country "
                    "to drill in.", layer="dislocation")

    if re.search(r"(weak|signals|registry|verdict|dead|watch|signal)", q):
        sig = data.get("signals") or {}
        tally = sig.get("tally") or {}
        html_answer = (
            "The live signal registry is harness-owned.<br><br>"
            f"FACT: WATCH {tally.get('WATCH', 0)} · WEAK {tally.get('WEAK', 0)} · "
            f"DEAD {tally.get('DEAD', 0)} · INSUFFICIENT {tally.get('INSUFFICIENT_COVERAGE', 0)}.<br>"
            "The Chief of Staff does not upgrade or downgrade verdicts."
        )
        return ChatResponse(
            answer_html=html_answer,
            answer_text=_plain(html_answer),
            mode_used="status",
            citations=[_citation("live_signals", "cockpit_data.signals", (data.get("meta") or {}).get("generated_ts"))],
            ui_actions=[UIAction(type="focus_view", view="signals")],
            freshness=_freshness(data),
            latency_ms=int((time.time() - start) * 1000),
        )

    if re.search(r"(gdelt|source freshness|stale|updated|update every day|pipeline)", q):
        freshness = _freshness(data)
        html_answer = (
            "Source freshness from the cockpit payload:<br><br>"
            f"Generated: <b>{_esc(freshness.get('generated_ts'))}</b><br>"
            f"Gap engine: <b>{_esc(freshness.get('gap_status'))}</b> as of {_esc(freshness.get('gap_as_of'))}<br>"
            f"Governance: <b>{_esc(freshness.get('governance'))}</b> as of {_esc(freshness.get('governance_as_of'))}<br><br>"
            "For a full pipeline root-cause answer, I will ask Opus with this freshness context."
        )
        return ChatResponse(
            answer_html=html_answer,
            answer_text=_plain(html_answer),
            mode_used="status",
            citations=citations,
            ui_actions=[UIAction(type="focus_view", view="health")],
            freshness=freshness,
            latency_ms=int((time.time() - start) * 1000),
        )

    return None


def _load_anthropic_api_key() -> str | None:
    env_key = os.getenv("ANTHROPIC_API_KEY")
    if not ENV_FILE.exists():
        return env_key
    pattern = re.compile(r"^ANTHROPIC_API_KEY=(.+)$")
    key = None
    for line in ENV_FILE.read_text(errors="ignore").splitlines():
        match = pattern.match(line.strip())
        if not match:
            continue
        value = match.group(1).strip()
        value = re.sub(r"\s+#.*$", "", value).strip().strip("\"'")
        if value.startswith("sk-ant-api"):
            key = value
    # Match the Opus skill behavior: prefer the configured file key so a stale
    # ambient shell key does not poison local app runs.
    return key or env_key


@lru_cache(maxsize=1)
def resolve_opus_model() -> str:
    requested = os.getenv("ASADO_COS_MODEL")
    if requested:
        return requested
    api_key = _load_anthropic_api_key()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY unavailable for Opus external agent.")
    response = requests.get(
        "https://api.anthropic.com/v1/models",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01"},
        timeout=20,
    )
    response.raise_for_status()
    models = response.json().get("data") or []
    opus = [m for m in models if re.match(r"^claude-opus-", m.get("id", ""))]
    if not opus:
        raise RuntimeError("No claude-opus-* model found in Anthropic Models API.")
    opus.sort(key=lambda m: m.get("created_at") or "")
    return opus[-1]["id"]


# C1 follow-up (red-team 2026-06-26): the COS evidence packet is built from
# cockpit_data.json, whose gap_engine price_state.source_freshness(_json) still
# carries the forbidden forward-return-fitted optimizer surface (combiner_scores_daily /
# COMBINER_RIDGE_DAILY_V1, factor_returns, forward-return vars). Scrub those keys out of
# the packet BEFORE it reaches Opus. This does NOT touch legitimate COS context (country
# returns, gaps, harness verdicts) — only the optimizer-output surfaces leak as raw values.
_FORBIDDEN_EVIDENCE_RE = re.compile(
    r"combiner|factor_returns|factor_top20|country_factor_attribution|gap_holdout"
    r"|(^|_)\d+[a-z]{0,2}ret($|_)|forward_return|_ret_lead|fwd_ret",
    re.IGNORECASE,
)


def _scrub_evidence(obj: Any) -> Any:
    """Recursively drop any forbidden optimizer-output key (and its subtree); sanitize
    the contents of nested *_json blob strings the same way."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if _FORBIDDEN_EVIDENCE_RE.search(str(k)):
                continue
            if isinstance(v, str) and str(k).endswith("_json"):
                v = _scrub_evidence_json_string(v)
            out[k] = _scrub_evidence(v)
        return out
    if isinstance(obj, list):
        return [_scrub_evidence(x) for x in obj]
    return obj


def _scrub_evidence_json_string(raw: str) -> str:
    try:
        parsed = json.loads(raw)
    except (ValueError, TypeError):
        return raw
    return json.dumps(_scrub_evidence(parsed))


def _evidence_packet(question: str, data: dict[str, Any]) -> dict[str, Any]:
    country = _match_country(question, data)
    brief = {}
    brief_info = data.get("brief") or {}
    brief_path = Path(brief_info.get("file") or "")
    if brief_path.exists():
        text = brief_path.read_text(errors="ignore")
        brief = {"file": str(brief_path), "excerpt": text[:5000]}
    packet = {
        "current_date": "2026-06-24",
        "question": question,
        "epistemic_contract": (data.get("meta") or {}).get("epistemic_contract"),
        "freshness": _freshness(data),
        "today": data.get("today") or [],
        "top_gaps": ((data.get("gap_engine") or {}).get("top") or [])[:5],
        "signal_tally": (data.get("signals") or {}).get("tally") or {},
        "top_signals": ((data.get("signals") or {}).get("registry") or [])[:8],
        "country": country,
        "country_snapshot": ((data.get("countries") or {}).get(country) if country else None),
        "country_gap": (_country_gap(country, data) if country else None),
        "latest_brief": brief,
    }
    return _scrub_evidence(packet)


def call_opus_agent(question: str, data: dict[str, Any], timeout: int = 90) -> tuple[str, str]:
    api_key = _load_anthropic_api_key()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY unavailable for Opus external agent.")
    model = resolve_opus_model()
    evidence = _evidence_packet(question, data)
    system = (
        "You are the ASADO Chief of Staff, using Opus as an external reasoning agent. "
        "Answer the user's ASADO question from the supplied evidence packet only. "
        "Use FACT for directly supplied evidence, INFERENCE for synthesis, and UNKNOWN/STALE "
        "when evidence is missing or stale. Do not give trade instructions. Do not invent tables, "
        "values, citations, or verdicts. Harness verdicts are owned by the harness, not by you. "
        "Keep the answer concise and useful for a portfolio/research cockpit. Return plain text only."
    )
    user = (
        "User question:\n"
        f"{question}\n\n"
        "Evidence packet (bounded JSON):\n"
        f"{json.dumps(evidence, ensure_ascii=True, default=str)[:30000]}"
    )
    payload: dict[str, Any] = {
        "model": model,
        "max_tokens": int(os.getenv("ASADO_COS_MAX_TOKENS", "1800")),
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    if not model.startswith("claude-opus-4-8"):
        payload["temperature"] = 0.1
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    content = response.json().get("content") or []
    text = "\n".join(block.get("text", "") for block in content if block.get("type") == "text").strip()
    if not text:
        raise RuntimeError("Opus returned an empty answer.")
    return text, model


@app.get("/api/cos/health")
def health() -> dict[str, Any]:
    model = None
    model_error = None
    if _load_anthropic_api_key():
        try:
            model = resolve_opus_model()
        except Exception as exc:  # pragma: no cover - network-dependent
            model_error = str(exc)
    return {
        "ok": True,
        "service": "asado-cos-chat",
        "ts": _now_iso(),
        "cockpit_data": DATA_PATH.exists(),
        "opus_available": bool(_load_anthropic_api_key()),
        "opus_model": model,
        "opus_model_error": model_error,
    }


@app.post("/api/cos/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    start = time.time()
    data = load_cockpit_data()
    deterministic = deterministic_answer(request.message, data)
    if deterministic and request.mode != "research":
        return deterministic

    actions: list[UIAction] = []
    country = _match_country(request.message, data)
    if country:
        actions.append(UIAction(type="focus_country", country=country))
    elif re.search(r"(gap|price discovery|unabsorbed|absorption|not absorbing)", request.message.lower()):
        gap = _top_gap(data)
        if gap:
            actions.append(UIAction(type="focus_gap", gap_id=gap.get("gap_id")))
    else:
        actions.append(UIAction(type="focus_view", view="overview"))

    try:
        text, model = call_opus_agent(request.message, data)
        answer_html = _text_to_html(text)
        return ChatResponse(
            answer_html=answer_html,
            answer_text=text,
            mode_used="research",
            model=model,
            external_agent="opus",
            fallback=True,
            citations=[
                _citation("opus_evidence_packet", "cockpit_data + latest brief", (data.get("gap_engine") or {}).get("as_of"))
            ],
            ui_actions=_validate_actions(data, actions),
            freshness=_freshness(data),
            latency_ms=int((time.time() - start) * 1000),
        )
    except Exception as exc:
        text = (
            "UNKNOWN/STALE: the Opus external agent is unavailable for this open-ended question. "
            f"Deterministic cockpit routing is still available. Error class: {type(exc).__name__}."
        )
        return ChatResponse(
            answer_html=_text_to_html(text),
            answer_text=text,
            mode_used="research",
            model=None,
            external_agent="opus",
            fallback=True,
            citations=[_citation("cockpit_data", "cos_mockups/cockpit_data.json", (data.get("gap_engine") or {}).get("as_of"))],
            ui_actions=_validate_actions(data, actions),
            freshness=_freshness(data),
            latency_ms=int((time.time() - start) * 1000),
        )


app.mount("/", StaticFiles(directory=HERE, html=True), name="static")
