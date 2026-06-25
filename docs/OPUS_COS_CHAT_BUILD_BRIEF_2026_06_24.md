# Opus Review Brief - ASADO Chief-of-Staff LLM Chat Build

Date: 2026-06-24

## User Request

The user has the ASADO Chief-of-Staff cockpit open at:

`http://localhost:8787/cockpit_live.html`

They asked whether LLM answers have been built into the Chief-of-Staff chat. The current answer is no: the live cockpit still uses a scripted JavaScript router in `cos_mockups/cockpit_live.html`.

The user then said: "yes do it - use opus 4.8 exta high".

Treat this as a high-rigor Opus-style review of the implementation approach before Codex edits the repo.

## Goal

Build real LLM-backed Chief-of-Staff answers into the current ASADO cockpit without breaking the existing static cockpit:

- Keep `http://localhost:8787/cockpit_live.html` as the user-facing URL.
- Replace the scripted-only chat path with an API-backed `/api/cos/chat` path.
- Preserve deterministic UI focus behavior: ask "Brazil" -> country panel, "top gaps" -> gap panel, "weak signals" -> signal registry/detail.
- Use existing ASADO data surfaces before model synthesis.
- Use a heavy Anthropic model by default for broad answers.
- Avoid exposing API keys in browser JS.
- Keep the system read-only by default.

## Current State

Relevant files:

- `cos_mockups/cockpit_live.html`: current live cockpit; chat uses `ask(t)` -> `route(t)` keyword matching.
- `cos_mockups/make_live_cockpit.py`: generator/template source with matching scripted router.
- `cos_mockups/cockpit_data.json/js`: live cockpit payload built from loop DB.
- `scripts/query_assistant.py`: existing schema-aware LLM query assistant over DuckDB + Neo4j; provider choices `auto`, `openai`, `anthropic`.
- `scripts/asado_mcp_server.py`: existing MCP-style deterministic tools, including `ask_asado`, read-only SQL/Cypher tools, country/profile/event/returns helpers.
- `frontend/app.py`: Streamlit Ask ASADO tab already uses `ASADOQueryAssistant`, but this is not wired to the cockpit.
- `docs/PRD_Chief_Of_Staff_Deep_Chat_2026_06_24.md`: desired long-term architecture.

Current cockpit server:

`python -m http.server 8787 --directory cos_mockups`

This cannot handle `/api/cos/chat`, so implementation likely needs a small FastAPI server that serves the static files and handles the API on the same port.

## Proposed Minimal Build

1. Add `cos_mockups/cos_chat_service.py`
   - FastAPI app.
   - `/api/cos/chat` POST endpoint.
   - Serves `cos_mockups/` static files at `/`.
   - Loads `cockpit_data.json` for deterministic status/gap/country/signal answers.
   - Has B0 deterministic answers for:
     - today / what should I care about,
     - governance,
     - top gaps / price not absorbed,
     - country names,
     - signal/weak/registry questions,
     - source freshness/GDELT questions.
   - Falls back to `ASADOQueryAssistant` for arbitrary ASADO research questions when API keys are available.
   - Returns structured JSON:
     - `answer_html`
     - `mode_used`
     - `model`
     - `citations`
     - `ui_actions`
     - `freshness`
     - `fallback`

2. Update `cos_mockups/cockpit_live.html`
   - Replace `ask(t){ pushMsg("you",t); route(t) }` with async API call.
   - Keep scripted router as local fallback if the API fails.
   - Apply `ui_actions` from the API: `focus_country`, `focus_gap`, `focus_signal`, `focus_view`, `set_layer`.
   - Render `answer_html` into the chat bubble.

3. Update `cos_mockups/make_live_cockpit.py`
   - Keep generator/template aligned with `cockpit_live.html`.

4. Add tests
   - FastAPI TestClient tests for deterministic endpoint behavior.
   - Existing cockpit selection tests still pass.

5. Runtime
   - Stop the old `http.server` process on port 8787.
   - Start:
     `oprun Anthropic,OpenAI -- env ASADO_COS_PROVIDER=anthropic ASADO_COS_PREFER_OPUS=1 venv/bin/python -m uvicorn cos_mockups.cos_chat_service:app --host 127.0.0.1 --port 8787`

## Questions For Opus

1. Is this minimal build safe and aligned with the ASADO architecture?
2. What are the highest-risk mistakes in wiring the cockpit to LLM answers?
3. Should the first version call `ASADOQueryAssistant` for fallback, or should it only provide deterministic B0/B1-lite answers until a fuller CoS orchestrator exists?
4. How should Codex honor "Opus 4.8 extra high" given the local skill script resolves the latest flagship model dynamically and this repo currently has the query assistant defaulting to older Sonnet unless overridden?
5. What acceptance tests are mandatory before telling the user it is done?

End with `RECOMMENDATION: PROCEED|REVISE|NEED_MORE_INFO`.
