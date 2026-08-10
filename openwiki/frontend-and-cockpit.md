---
type: "Reference"
title: "Frontend and cockpit"
description: "ASADO's user-facing surfaces: the Chief-of-Staff cockpit payload contract and producer, the Streamlit research dashboard, the Perspective Lab workbench, and the monthly-update SSE backend — plus the distinction between verified signals and conjecture."
---

# Frontend and cockpit

ASADO's Chief-of-Staff cockpit is a data product, not just a UI. The cockpit payload is built from loop-DB state, governance artifacts, research surfaces, and a small number of curated pointers into nightly reports.

## The payload contract

`cos_mockups/COCKPIT_DATA_CONTRACT.md` is the canonical field contract for `cockpit_data.json`. It says the payload top-level keys are `meta`, `governance`, `signals`, `dislocations`, `combiner`, `returns`, `theses`, `countries`, `drawdowns`, `brief`, `map`, `today`, `gap_engine`, and `research_desk`.

It also states that missing values are sanitized to `null`, returns are stored as percent, and on producer failure an extra `error` string key (e.g. `"loop DB unavailable"`) is present — the UI must surface producer errors rather than render a silent empty state.

The `gap_engine` block is the cockpit surface for the Price-Discovery Gap Engine (gap-first map layer, Known Gaps feed, gap detail view, `config_version`/`config_hash` provenance); the engine itself and its promotion/holdout gates are documented in [Loop and research workflows](loop-and-research.md). The `research_desk` block is the Discovery Triage Court surface (see below).

## Payload generation

`cos_mockups/build_cockpit_data.py` is the producer. Its docstring is valuable because it tells you exactly what the cockpit is reading and why:
- dislocation rows from the loop DB,
- harness verdict summaries,
- combiner and family-rank surfaces,
- governance scorecards,
- thesis ledgers,
- Triptych priors,
- optional ETF tail context,
- and the latest brief pointer.

The producer is intentionally resilient: each source is wrapped in error handling so one failure does not blank the whole cockpit.

One top-level section, `research_desk`, is the cockpit surface for the Discovery Triage Court: `cos_mockups/build_cockpit_data.py::read_research_desk()` reads the JSONL `journal/` ledgers (discovery lab, analog shelf, under-triage, blind rulings, prospective, graveyard) and never fabricates rows when a ledger is absent. See [Discovery Triage](discovery-triage.md) for what those ledgers contain.

## Frontend binding logic

The cockpit redesign work in `docs/PRD_Frontend_Alpha_Rethink_2026_07_01.md` and the tests in `tests/loop/test_phase2_frontend.py` show the binding logic is not trivial presentation glue. The current Phase 2 concepts include:
- family rank orientation,
- consensus voting rules,
- Edge Board selection logic,
- Fable connections relabelled as conjecture,
- and deterministic chat intents that route to new views.

## Interactive frontends (distinct from the cockpit)

ASADO has three independent user-facing surfaces. The Chief-of-Staff cockpit in `cos_mockups/` is one of them; the other two live in `frontend/` and are separate analyst/operator tools, not cockpit mirrors. `docs/PRD_Gap_Engine_Frontend_Binding_2026_06_24.md` states this explicitly: `frontend/perspective_lab/` "is a separate analyst workbench. It builds successfully, but it is not the Chief-of-Staff cockpit."

### Streamlit research dashboard
`frontend/app.py` is the older Streamlit country-research dashboard (`streamlit run frontend/app.py`, default port 8501). It reads directly from the DuckDB warehouse and Neo4j via `scripts/db_bridge.py::AsadoDB` and exposes eight tabs: Monthly Update, Dashboard, Trade, Banking, Similarity, Factors, Ask ASADO, and Free Query. The "Ask ASADO" tab calls `scripts/query_assistant.py::ASADOQueryAssistant` — the same natural-language query layer the MCP server exposes. The Monthly Update tab embeds `frontend/monthly_update.html`, a React/Babel single-page operator UI that drives `scripts/monthly_update.py` through `scripts/update_server.py` (FastAPI + SSE on port 7821) for stage-by-stage run control, live logs, and run history.

Operational hazard: the Streamlit app holds a process-wide cached DuckDB connection (`get_db()` is `@st.cache_resource`, `frontend/app.py:132`). Run it briefly and Ctrl-C — **never leave it running overnight**, because the cached read connection blocks the nightly DuckDB writers. This is a hard rule in `AGENTS.md` and the asado-operations skill. `streamlit` is installed in the repo venv but is not listed in `requirements.txt`.

### Perspective Lab
`frontend/perspective_lab/` is a Vite/React workbench built on Perspective's pivotable datagrid (`@perspective-dev/viewer` + `@perspective-dev/viewer-datagrid`). It is served by `scripts/perspective_lab_server.py`, a read-only FastAPI backend that exposes focused DuckDB slices instead of the whole warehouse: daily country returns (`t2_factors_daily`), daily optimizer factor returns (`factor_returns_daily`), monthly factor payoffs (`factor_returns`), country-factor attribution, prediction-market signals, World Bank commodity features, warehouse freshness, and the Strategy #1 analog artifacts under `Data/strategy/analogs/v1/`. Run the backend (`./venv/bin/python scripts/perspective_lab_server.py`, served at `http://127.0.0.1:7832` when built, or dev Vite at `http://127.0.0.1:5174`). See `docs/PERSPECTIVE_LAB.md` for the full run/build guide and data contract. The lab is an analyst/operator UI layer, not an alpha engine or replacement for the MCP/query assistant.

### Three-surface distinction
- `cos_mockups/` — the Chief-of-Staff cockpit: a generated `cockpit_data.json` payload consumed by static HTML, aggregating loop-DB state, governance, and research surfaces. Documented above.
- `frontend/app.py` — the Streamlit research/operator dashboard over the warehouse, including the monthly-update operator UI.
- `frontend/perspective_lab/` — the Perspective datagrid workbench over curated read-only DuckDB slices.

All three are read-only over the warehouse / loop DB; none write to DuckDB. They are distinct from the MCP server (`scripts/asado_mcp_server.py`), which exposes the same query layer to MCP-speaking clients such as Claude Desktop.

## Why this matters

The cockpit is where multiple research layers converge. Future changes should preserve the distinction between:
- verified signals vs conjecture,
- country-level rows vs structural rows,
- governance exception items vs ranked signal feeds,
- and live data vs dated brief pointers.

## Source references

- `cos_mockups/COCKPIT_DATA_CONTRACT.md`
- `cos_mockups/build_cockpit_data.py`
- `cos_mockups/cos_chat_service.py`
- `cos_mockups/make_live_cockpit.py`
- `cos_mockups/cockpit_live.html`
- `frontend/app.py` — Streamlit research dashboard.
- `frontend/monthly_update.html` — embedded monthly-update operator UI.
- `frontend/perspective_lab/` — Perspective Lab Vite/React workbench.
- `scripts/perspective_lab_server.py` — Perspective Lab read-only FastAPI backend.
- `scripts/update_server.py` — monthly-update FastAPI + SSE backend.
- `scripts/db_bridge.py` — `AsadoDB`, the warehouse access layer the Streamlit app uses.
- `scripts/query_assistant.py` — `ASADOQueryAssistant`, used by the Streamlit "Ask ASADO" tab and the MCP server.
- `tests/loop/test_phase2_frontend.py`
- `docs/PRD_Frontend_Alpha_Rethink_2026_07_01.md`
- `docs/PRD_Gap_Engine_Frontend_Binding_2026_06_24.md`
- `docs/PERSPECTIVE_LAB.md`
- `docs/AUDIT_FRONTEND_2026_07_01.md`

## Where to go next

- [Architecture overview](architecture.md)
- [Loop and research workflows](loop-and-research.md)
- [Discovery Triage](discovery-triage.md)
- [Prediction markets and Brier Gate](prediction-markets.md)
