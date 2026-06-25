# PRD - ASADO Chief-of-Staff Deep Chat

| Field | Value |
|---|---|
| Project | ASADO |
| Feature | Chief-of-Staff deep chat |
| Created | 2026-06-24 |
| Owner | Arjun Divecha |
| Status | Design ready for implementation |
| Primary question | What does ASADO know that price has not yet figured out? |
| Primary surfaces | CoS cockpit, future Electron/React front end, MCP/query layer |
| Related docs | `PRD_Governance_And_Chief_Of_Staff.md`, `docs/PRD_Gap_Engine_Frontend_Binding_2026_06_24.md`, `cos_mockups/COCKPIT_DATA_CONTRACT.md`, `PRD_ASADO_Natural_Language_Query_Layer.md` |

---

## 1. Executive Summary

The Chief-of-Staff chat should become ASADO's conversational control plane: the place where the user can ask any question about the system, the data, the daily run, the gap engine, signals, countries, history, source freshness, portfolio exposure, or the research process, and receive a grounded answer with citations, caveats, and UI actions.

It should not be a generic SQL chatbot bolted into the footer. It should be a governed analyst interface over ASADO's deterministic machinery.

The current cockpit chat is a useful prototype, but it is scripted. The current Streamlit "Ask ASADO" tab is a useful research assistant, but it is not integrated with the cockpit or governance model. The new CoS chat should combine them:

- the cockpit's persistent context and focus-panel routing,
- the query assistant's schema-aware read-only planning,
- the MCP server's deterministic tools,
- the governance PRD's B0/B1 mode separation,
- and the gap engine's ranked answer to "what has price not absorbed?"

The target behavior is simple:

> Ask a question in plain English. The CoS decides which ASADO surface owns the answer, calls the right tool, shows its evidence, moves the cockpit if useful, and says FACT / INFERENCE / UNKNOWN clearly.

---

## 2. Current State

### 2.1 Cockpit Chat

The live cockpit footer currently routes through JavaScript functions in `cos_mockups/cockpit_live.html`:

- `ask(t)` pushes a user message.
- `route(t)` lowercases the text and matches keywords.
- matched phrases focus the cockpit on overview, governance, Brazil, weak signals, gap, downside, pressure, and similar scripted views.
- unmatched text falls back to a canned "prototype: scripted" answer.

This is a good UI proof, but it cannot answer arbitrary questions. It does not call an LLM, DuckDB, Neo4j, the loop DB, evidence packs, docs, or the schema registry.

### 2.2 Streamlit Ask ASADO

`frontend/app.py` already has an "Ask ASADO" tab that calls `scripts/query_assistant.py`.

That stack already provides:

- natural-language to structured query planning,
- DuckDB SQL execution,
- Neo4j Cypher execution,
- limited hybrid orchestration,
- read-only validation,
- result interpretation,
- schema cache awareness,
- return-surface guardrails,
- provider selection for OpenAI or Anthropic.

This is useful, but it is still a research workbench, not a Chief-of-Staff cockpit. It exposes the generated query and table, but does not know how to drive the cockpit, route to gap cards, cite governance artifacts, or keep B0 status answers separate from B1 raw research.

### 2.3 MCP Server

`scripts/asado_mcp_server.py` already exposes the right kind of deterministic tool surface:

- `ask_asado`
- `get_schema_summary`
- `run_duckdb_sql`
- `run_neo4j_cypher`
- `get_country_profile`
- `event_window`
- `events_in_window`
- `predmkt_snapshot`
- `country_signal_now`
- `event_market_set`
- `commodity_price_series`
- `daily_factor_series`
- `country_returns`
- `factor_return_series`
- `country_factor_attribution`
- `return_leaders`
- `country_news`
- `register_hypothesis`
- `evaluate_signal`
- `open_thesis`

The CoS should reuse this tool vocabulary, but not expose every action equally in the front-end chat. Read tools can be available in B1 research mode. Write/research-registration tools should require explicit structured confirmation and should not be part of the initial cockpit chat.

### 2.4 Data Substrate

The current ASADO warehouse is wide enough for a true deep chat:

- main warehouse: `Data/asado.duckdb`
- loop warehouse: `Data/loop/asado_loop.duckdb`
- graph: Neo4j
- cockpit payload: `cos_mockups/cockpit_data.json`
- gap engine tables: `gap_episodes`, `gap_episode_marks`, `price_state_daily`, `price_state_surface`, `gap_episode_expression`, `gap_holdout_daily`
- governance artifacts: `Data/loop/governance/`
- dislocation briefs: `Data/dislocations/brief_YYYY_MM_DD.md`
- ledgers and harness outputs
- evidence packs and recent GDELT articles
- docs and PRDs describing the system itself

The problem is not lack of data. The problem is routing the question to the correct surface without letting the LLM invent glue.

---

## 3. Product Thesis

ASADO's CoS chat should answer questions on any aspect of ASADO by using a hierarchy of truth:

1. Deterministic surfaces first.
2. Pre-rendered governance/status artifacts before raw DB reads.
3. Gap-engine objects before raw dislocation rows when the question is about "what matters now."
4. Return surfaces before explanatory factors when the question is about whether something worked.
5. Schema registry before generated SQL.
6. Read-only validated SQL/Cypher only when no narrower tool owns the question.
7. LLM synthesis only after evidence has been collected.

This keeps the CoS broad, but not magical. The LLM should choose, explain, and synthesize. It should not become the source of truth.

---

## 4. User Stories

### US1. Morning Triage

As Arjun, I want to ask "what should I care about today?" and get a concise answer that names governance state, top price-discovery gaps, live signal changes, and fresh risks.

Acceptance:

- answer leads with governance if red or amber,
- promotes current gap-engine rows before raw dislocations,
- cites the cockpit payload, governance scorecard, and latest brief,
- emits UI focus actions for the top card.

### US2. Price-Discovery Gap Drilldown

As Arjun, I want to ask "what does the data know that price has not figured out in Brazil?" and get the current gap, absorption state, ETF expression, evidence, and invalidation rule.

Acceptance:

- answer uses `gap_episodes`, `gap_episode_marks`, and `price_state_surface`,
- includes preferred ETF/proxy and expression quality,
- explains FACT vs INFERENCE,
- says UNKNOWN/STALE if gap marks are stale or missing,
- can focus the cockpit to the relevant country or gap detail.

### US3. Signal And Harness Questions

As Arjun, I want to ask "why is this signal WEAK?" or "show me the IC path for graph bank gap" and get the harness-owned verdict, IC series, cost/holding-period context, and caveats.

Acceptance:

- answer never upgrades or downgrades a signal verdict,
- verdict is always attributed to the harness,
- IC chart/table comes from persisted `harness_ic_series`,
- if no IC series exists, answer says UNKNOWN/STALE rather than showing only the latest run.

### US4. Country Letter

As Arjun, I want to ask "give me the Japan letter" and get a structured country answer: current returns, active gaps, sovereign/FX stress, flows, valuation, consensus revisions, prediction markets, relevant news, and current theses.

Acceptance:

- answer uses a country-snapshot tool rather than ad hoc SQL,
- every row has freshness,
- answer distinguishes market price moves from explanatory evidence,
- cockpit focuses the country tile and detail panel.

### US5. System And Pipeline Questions

As Arjun, I want to ask "why did GDELT not update?" or "where does ToT come from?" and get source lineage, last successful run, involved scripts, failure logs, and current freshness.

Acceptance:

- answer can inspect run manifests, logs, source freshness tables, and docs,
- shows script names and artifact paths,
- identifies whether the issue is upstream, pipeline, schema, or UI binding,
- avoids proposing Excel/CSV paths where they have been removed.

### US6. Historical Research

As Arjun, I want to ask "what happened to country returns after rating downgrades?" or "which analogs match Turkey now?" and get return-surface anchored event windows or similarity outputs.

Acceptance:

- return questions route to return surfaces first,
- event questions use `events_in_window` and `event_window`,
- analog questions state whether the similarity is fundamental, graph, lead-lag, or text/news based,
- output includes raw table/chart artifact if appropriate.

### US7. Safe Research Actions

As Arjun, I want the CoS to propose hypotheses or tests, but not quietly mutate the research record.

Acceptance:

- proposed research directions are stamped NON-GOVERNING,
- registering a hypothesis or opening a thesis requires explicit confirmation,
- agenda-control logs are written before any research write,
- the CoS cannot write verdicts.

---

## 5. Non-Goals

- Do not make the CoS a trading/order-entry system.
- Do not let the CoS adjudicate signal verdicts.
- Do not let raw SQL be the first-line path for common questions.
- Do not let B0 status mode read raw ledgers or arbitrary DB tables.
- Do not hide stale data behind a fluent answer.
- Do not rebuild the front end around the chat before the data contract is stable.
- Do not make local-model cost savings the primary design driver.
- Do not require Excel or CSV anywhere in the CoS path.

---

## 6. Operating Modes

### 6.1 B0 Status Mode

B0 is the morning-brief / state-of-system mode.

It answers:

- what should I care about today?
- is governance red?
- did the daily run complete?
- what changed overnight?
- what are the top gaps?
- which signals are live?
- is a surface stale?

Allowed surfaces:

- `cos_mockups/cockpit_data.json`
- `Data/loop/governance/*`
- latest `Data/dislocations/brief_*.md`
- pre-rendered calibration/report artifacts
- selected `live_signals` and cockpit snapshots through a narrow status tool

Not allowed:

- arbitrary SQL,
- arbitrary shell,
- raw ledgers,
- write tools,
- hypothesis registration,
- model-generated conclusions that are not tied to an artifact.

### 6.2 B1 Research Mode

B1 is the deep analyst mode.

It answers:

- what explains this country?
- what analogs exist?
- what did returns do around an event?
- what source table owns a variable?
- what does the warehouse know about this macro question?
- which data surfaces disagree?

Allowed surfaces:

- deterministic MCP/read tools,
- query assistant,
- read-only DuckDB and Neo4j through validators,
- docs and schema registry,
- loop DB read-only surfaces,
- evidence packs,
- logs through whitelisted readers.

Required behavior:

- all raw reads pass through a proxy logger,
- every answer is stamped NON-GOVERNING when it uses raw research surfaces,
- proposed tests or research actions are logged as intents,
- repeated dead-trial retests are blocked unless explicitly overridden.

### 6.3 B2 Action Mode

B2 is future. It covers:

- register hypothesis,
- evaluate signal,
- open paper thesis,
- schedule a deeper research run,
- create a report artifact.

Initial build should not enable B2 directly inside chat. The CoS can propose an action and produce a confirmation object, but the UI should require an explicit click/confirm before mutation.

---

## 7. Model Policy: Heavy LLM vs Local Model

Use both, with strict task boundaries.

### 7.1 Default

Use a heavy frontier LLM for final synthesis, ambiguous questions, and broad ASADO reasoning.

Reason:

- ASADO questions are multi-hop and finance-specific.
- The hard problem is not SQL generation. It is deciding which substrate owns the answer.
- The answer often needs caveats across governance, staleness, harness verdicts, market absorption, and data lineage.
- A fluent but underpowered local model is more dangerous than a slower expensive model when it turns uncertainty into confidence.

### 7.2 Local Model Uses

A local model is appropriate for:

- intent classification,
- country/entity extraction,
- variable alias matching,
- summarizing already-retrieved rows,
- doc chunk retrieval/reranking,
- producing short UI labels,
- deciding whether a question needs clarification,
- offline batch indexing of docs,
- fallback drafts when API keys are unavailable.

Local output must be treated as intermediate. It should not be the final source of investment-facing synthesis unless the answer is trivial and evidence is deterministic.

### 7.3 Heavy Model Uses

A heavy model is required for:

- final answer composition,
- ambiguous "what matters" questions,
- cross-surface synthesis,
- research-mode interpretation,
- comparing data vs price absorption,
- identifying caveats and failure modes,
- explaining why a signal is or is not usable,
- drafting research plans,
- deciding when to refuse or narrow a question.

### 7.4 Escalation Rule

Start cheap only when the task is narrow. Escalate to the heavy model if any of these are true:

- the question asks for judgment,
- the answer will influence research direction or portfolio attention,
- more than one data surface is needed,
- governance is red/amber for a relevant surface,
- the local model confidence is low,
- generated SQL/Cypher fails validation,
- the question asks "why", "what matters", "what is not priced", "should", "compare", or "what changed."

### 7.5 Recommended Model Tiers

The front end should expose an internal model policy, not a prominent model selector:

- `fast`: local classifier plus deterministic tools; no final deep synthesis.
- `standard`: heavy model final answer with bounded tool calls.
- `deep`: heavy model with multi-step tool planning, doc retrieval, and richer answer artifacts.

Default: `standard`.

The user can later add a visible "Deep" toggle. The default cockpit experience should feel like a competent colleague, not a model-selection lab.

---

## 8. Architecture

```text
User
  |
  v
Front end chat component
  |
  | POST /api/cos/chat  or SSE stream
  v
CoS Chat Service
  |
  +-- Context Assembler
  |     - active view
  |     - selected country/gap/signal
  |     - latest cockpit payload
  |     - governance status
  |
  +-- Intent Router
  |     - status vs research vs action
  |     - country/gap/signal/event/source/schema/governance/portfolio
  |
  +-- Tool Planner
  |     - deterministic tool first
  |     - validated SQL/Cypher fallback
  |     - doc retrieval fallback
  |
  +-- Evidence Ledger
  |     - tool calls
  |     - rows/charts/docs used
  |     - freshness/staleness
  |     - citations
  |
  +-- Answer Composer
  |     - FACT / INFERENCE / UNKNOWN
  |     - citations
  |     - caveats
  |     - suggested follow-ups
  |
  +-- UI Action Planner
        - focus country
        - open gap detail
        - show signal IC chart
        - render table/chart
        - update map layer
```

The service can initially be a Python FastAPI app in the ASADO repo. It should be deployable locally for the Electron/React front end and callable from the static cockpit during development.

Suggested package:

```text
cos_service/
  __init__.py
  app.py
  models.py
  orchestrator.py
  context.py
  intent.py
  tools.py
  evidence.py
  answer.py
  local_provider.py
  llm_provider.py
  prompts/
    router.md
    answer_status.md
    answer_research.md
```

---

## 9. API Contract

### 9.1 Request

```jsonc
{
  "thread_id": "optional-stable-thread-id",
  "message": "what does the data know about Brazil that price has not figured out?",
  "mode": "auto",
  "model_tier": "standard",
  "context": {
    "active_view": "overview",
    "selected_country": "Brazil",
    "selected_gap_id": null,
    "selected_signal_id": null,
    "map_layer": "gap",
    "as_of": "2026-06-24"
  }
}
```

Mode values:

- `auto`
- `status`
- `research`
- `action_preview`

Model tier values:

- `fast`
- `standard`
- `deep`

### 9.2 Stream Events

The chat should stream events so the front end can show tool progress without waiting for a full answer.

```jsonc
{ "type": "tool.start", "tool": "gap_detail", "label": "Reading Brazil gap marks" }
{ "type": "tool.result", "tool": "gap_detail", "rows": 3, "freshness": "fresh" }
{ "type": "artifact.table", "artifact_id": "tbl_123", "title": "Brazil active gaps" }
{ "type": "artifact.chart", "artifact_id": "ch_123", "title": "IC path" }
{ "type": "ui.focus", "view": "gap", "country": "Brazil", "gap_id": "..." }
{ "type": "assistant.delta", "text": "Brazil has one active short gap..." }
{ "type": "final", "answer": "...", "citations": [], "epistemic_tags": [] }
```

### 9.3 Final Response Shape

```jsonc
{
  "answer": "Brazil has an active short gap, but the price absorption read is partial...",
  "mode_used": "research",
  "non_governing": true,
  "confidence": "medium",
  "epistemic_tags": ["FACT", "INFERENCE"],
  "citations": [
    {
      "label": "gap_episode_marks",
      "path": "Data/loop/asado_loop.duckdb",
      "table": "gap_episode_marks",
      "date": "2026-06-23"
    }
  ],
  "freshness": {
    "overall": "fresh",
    "as_of": "2026-06-23",
    "warnings": []
  },
  "artifacts": [
    { "type": "table", "artifact_id": "tbl_123" },
    { "type": "chart", "artifact_id": "ch_123" }
  ],
  "ui_actions": [
    { "type": "focus_gap", "country": "Brazil", "gap_id": "..." }
  ],
  "suggested_questions": [
    "What would invalidate this gap?",
    "Show Brazil's ETF-vs-T2 basis.",
    "What did similar gaps do historically?"
  ]
}
```

---

## 10. Tool Catalog

### 10.1 Reuse Existing Tools

The CoS service should wrap or directly reuse:

- `ASADOQueryAssistant.ask`
- `ASADOQueryAssistant.plan`
- `ASADOQueryAssistant._validate_sql`
- `ASADOQueryAssistant._validate_cypher`
- `AsadoDB.query_panel`
- `AsadoDB.query_graph`
- MCP-style deterministic functions from `scripts/asado_mcp_server.py`

### 10.2 New CoS Tools

Add narrow tools that are safer and more cockpit-aware than generic SQL.

#### `cos_today_snapshot`

Purpose: answer morning triage.

Sources:

- `cos_mockups/cockpit_data.json`
- governance scorecard
- latest brief

Returns:

- governance summary,
- top gap,
- live signal summary,
- stale/missing surfaces,
- UI routes.

#### `cos_gap_snapshot`

Purpose: answer "what has price not absorbed?"

Sources:

- `gap_episode_marks`
- `gap_episodes`
- `gap_episode_expression`
- `price_state_surface`
- `gap_holdout_daily`
- latest brief

Returns:

- top current gaps,
- absorption state,
- expression quality,
- evidence rows,
- invalidation rule,
- holdout state.

#### `cos_country_snapshot`

Purpose: answer country-letter questions.

Sources:

- country reference,
- latest returns,
- active gaps,
- sovereign signals,
- market-implied signals,
- ETF flows and short interest,
- foreign flows,
- valuation,
- consensus revisions,
- WEO revisions,
- prediction-market composites,
- GDELT evidence packs,
- open theses.

Returns:

- structured country letter JSON,
- top facts and caveats,
- charts/tables to render.

#### `cos_signal_detail`

Purpose: answer signal/harness questions.

Sources:

- `live_signals`
- `harness_results`
- `harness_ic_series`
- cost/hold-period metrics,
- ledgers for mechanism text.

Returns:

- harness verdict,
- IC path,
- NW-t, IC, DSR,
- cost/hold grid,
- stale/missing warning,
- no CoS adjudication.

#### `cos_source_freshness`

Purpose: answer "did this update?" and "is this stale?"

Sources:

- run manifest,
- source freshness fields,
- table max dates,
- artifact mtimes,
- daily pipeline validation.

Returns:

- per-source freshness,
- expected vs actual date,
- owning scripts,
- last error if available.

#### `cos_doc_search`

Purpose: answer ASADO design and lineage questions.

Sources:

- PRDs,
- README,
- AGENTS,
- variable dictionary,
- user fix list,
- daily reports,
- cockpit contract.

Returns:

- chunks with file paths,
- concise cited summaries,
- no raw repo guessing.

#### `cos_artifact_renderer`

Purpose: turn tool outputs into front-end objects.

Returns:

- table specs,
- line charts,
- bar charts,
- map focus payloads,
- country/gap/signal cards.

---

## 11. Intent Taxonomy

| User asks | Mode | Primary tool | Fallback |
|---|---|---|---|
| What should I care about today? | B0 | `cos_today_snapshot` | latest brief |
| Why is governance red? | B0 | governance scorecard | run manifest |
| Where is price not absorbing data? | B0/B1 | `cos_gap_snapshot` | gap SQL |
| Explain Brazil | B1 | `cos_country_snapshot` | query assistant |
| Why is this signal WEAK? | B1 | `cos_signal_detail` | harness SQL |
| Show IC path | B1 | `cos_signal_detail` | `harness_ic_series` |
| Who led returns? | B1 | `return_leaders` | return SQL |
| What happened around event X? | B1 | `events_in_window` + `event_window` | daily returns SQL |
| What do prediction markets imply? | B1 | `predmkt_snapshot` / `country_signal_now` | predmkt SQL |
| What data owns variable X? | B1 | schema/variable registry | doc search |
| Why did GDELT not update? | B0/B1 | `cos_source_freshness` | logs |
| Open a thesis | B2 | action preview | explicit confirm |
| Mark signal good/dead | Reject | none | explain harness boundary |

---

## 12. Front-End Behavior

The chat should become a section in the new front end, and also the persistent footer in the cockpit.

### 12.1 Persistent Chat Rail

Keep the current design idea:

- map and live signals stay visible,
- chat input sits in the persistent left/bottom rail,
- answers can update the focus panel on the right.

### 12.2 Focus Events

The chat does not just answer. It drives the interface.

Examples:

- ask "Brazil" -> focus country tile and open country letter,
- ask "weak signals" -> open signal registry filtered to WEAK,
- ask "show IC for graph bank" -> open signal detail with IC chart,
- ask "top gaps" -> open price-discovery gap panel,
- ask "why stale?" -> open governance/run status panel.

### 12.3 Artifact Cards

Answers can include:

- table preview,
- chart,
- source citation card,
- freshness warning,
- "open detail" button,
- "run deeper" action preview.

### 12.4 Do Not Show Internals By Default

The Streamlit tab currently shows generated SQL and plan JSON. That is good for research mode, but the cockpit should hide it by default.

The front end should provide an "evidence" or "show work" expander with:

- tool calls,
- executed SQL/Cypher if any,
- cited rows,
- freshness,
- answer trace.

---

## 13. Answer Style Contract

Every answer should be short first, then expandable.

Default shape:

1. Direct answer.
2. Evidence bullets.
3. Caveat/freshness line.
4. Suggested next questions.

Example:

```text
Brazil has an active short price-discovery gap, but I would treat it as partially absorbed rather than ignored.

FACT: The latest gap mark shows a short Brazil gap with 61% unabsorbed fraction and EWZ as the preferred expression.
INFERENCE: The data is saying the macro/flow stress is not fully in the ETF yet, but the move has started.
UNKNOWN/STALE: I do not see a completed holdout window yet, so this is not a proven payoff pattern.
```

Rules:

- Never say "this is a trade."
- Never override harness verdicts.
- Never imply stale data is current.
- Never claim a source was checked unless it was actually read in the turn.
- For broad answers, include at least one concrete citation.
- For "what should I care about" answers, lead with red/amber governance.

---

## 14. Storage And Logging

The CoS should be auditable.

Suggested durable tables in `Data/loop/asado_loop.duckdb` or JSONL under `Data/logs/cos_chat/`:

### `cos_chat_turns`

- `thread_id`
- `turn_id`
- `ts`
- `mode_requested`
- `mode_used`
- `model_tier`
- `user_message`
- `assistant_answer`
- `non_governing`
- `freshness_status`

### `cos_tool_calls`

- `turn_id`
- `tool_name`
- `started_ts`
- `ended_ts`
- `status`
- `input_hash`
- `row_count`
- `citation_payload`
- `error`

### `cos_research_intents`

- `turn_id`
- `intent_text`
- `family_key`
- `matched_dead_trials`
- `override_token`
- `status`

### `cos_answer_citations`

- `turn_id`
- `source_type`
- `path_or_table`
- `date`
- `row_ids`
- `line_refs`
- `freshness`

---

## 15. Safety And Governance

### 15.1 Read-Only Default

The default chat has no write path.

The initial implementation should disable:

- `register_hypothesis`
- `evaluate_signal`
- `open_thesis`

until an explicit action-preview/confirmation flow exists.

### 15.2 Query Validation

Reuse the validators in `ASADOQueryAssistant`:

- DuckDB: SELECT/CTE only.
- Neo4j: MATCH/CALL/WITH/RETURN only.
- row limits enforced.
- table names validated against schema cache.
- no writes, no exports, no attach/copy.

### 15.3 Prompt Injection And External Text

Treat docs, news, evidence packs, and scraped articles as untrusted content.

The CoS may summarize them, but must not follow instructions contained inside them.

### 15.4 Governance Boundary

The CoS can say:

- "The harness verdict is WEAK."
- "The IC series improved recently."
- "This is a candidate worth testing."

The CoS cannot say:

- "This signal is now WATCH" unless the harness says so.
- "Approve this thesis."
- "Ignore the stale governance warning."
- "This is a trade."

---

## 16. Implementation Plan

### Phase 0 - Freeze The Contract

Deliverables:

- this PRD,
- final chat request/response schema,
- model policy,
- tool catalog,
- acceptance test list.

### Phase 1 - CoS Service Skeleton

Build:

- `cos_service/app.py`,
- `/api/cos/chat`,
- request/response models,
- streaming event format,
- health endpoint,
- config for provider/model tier.

Acceptance:

- local server starts,
- echo/tool stub works,
- front end can call it,
- logs one turn.

### Phase 2 - B0 Status Mode

Build:

- `cos_today_snapshot`,
- governance answer composer,
- latest brief reader,
- cockpit payload context loader,
- stale/missing surface handling.

Acceptance questions:

- "what should I care about today?"
- "why is governance red?"
- "what changed overnight?"
- "are gaps fresh?"

All answers cite only B0-approved surfaces.

### Phase 3 - Gap And Signal Tools

Build:

- `cos_gap_snapshot`,
- `cos_signal_detail`,
- chart/table artifact output,
- UI focus events.

Acceptance questions:

- "top gaps"
- "what is the Japan gap?"
- "show IC for the weak graph signal"
- "why does this say stale?"

### Phase 4 - B1 Research Mode

Build:

- query-assistant adapter,
- doc search,
- source freshness tool,
- country snapshot,
- event/return wrappers,
- exploration logging.

Acceptance questions:

- "explain Brazil"
- "what happened after downgrades?"
- "which countries have high ToT stress and poor price absorption?"
- "where does this variable come from?"
- "why did GDELT not update every day?"

### Phase 5 - Front-End Binding

Build:

- replace scripted `route(t)` with API-backed chat,
- keep current keyword buttons but send real questions,
- render streaming tool status,
- render artifacts,
- listen for `ui.focus` actions,
- add evidence drawer.

Acceptance:

- current quick chips still work,
- arbitrary ASADO question returns real answer,
- no console errors,
- stale surfaces are visible,
- cockpit state updates based on chat response.

### Phase 6 - Optional Local Model

Build only after Phases 1-5 are stable:

- `local` provider in query assistant / CoS service,
- structured-output validation,
- router/entity extraction first,
- escalation to heavy model on uncertainty.

Acceptance:

- local model handles narrow routing/entity extraction,
- failed or low-confidence local output escalates,
- final answers for broad questions still use heavy model by default.

---

## 17. Test Plan

### 17.1 Unit Tests

- intent classifier routes known prompts correctly,
- B0 tool cannot call raw DB,
- SQL validator rejects writes,
- Cypher validator rejects writes,
- local-model output parser rejects invalid JSON,
- citation builder requires source metadata,
- stale data produces UNKNOWN/STALE.

### 17.2 Integration Tests

- `POST /api/cos/chat` returns final answer for B0 prompt,
- gap prompt returns gap artifact and focus event,
- signal prompt returns IC chart if persisted,
- country prompt returns country snapshot,
- source-freshness prompt identifies table max dates,
- doc question returns cited doc chunks.

### 17.3 Browser Tests

- chat opens and sends,
- streaming events render,
- top-gap prompt focuses gap panel,
- signal prompt opens signal detail,
- evidence drawer shows tool calls,
- mobile/narrow viewport does not overlap text,
- no console errors.

### 17.4 Golden Questions

These should be run as a regression suite:

1. "What should I care about today?"
2. "Where is price not absorbing the data?"
3. "Explain Brazil."
4. "Why is this signal WEAK?"
5. "Show the IC path for the graph bank gap."
6. "What happened after rating downgrades?"
7. "Why did GDELT not update every day?"
8. "Where does ToT come from?"
9. "What is stale right now?"
10. "Mark this signal WATCH."

Expected behavior for question 10: refuse adjudication and cite harness boundary.

---

## 18. Build Recommendation

Do not replace the existing ASADO system. Enhance it.

The CoS chat should sit above the current deterministic layers:

- daily update,
- loop job,
- governance scorecard,
- gap engine,
- harness,
- ledgers,
- query assistant,
- MCP tools,
- cockpit data contract.

The first production version should use a heavy model for final answers and ship with the local-model seam prepared but disabled for final synthesis. Once the API, evidence contract, and front-end behavior are stable, add local routing/extraction for speed.

The implementation order should be:

1. service skeleton,
2. B0 status mode,
3. gap/signal tools,
4. B1 research mode,
5. cockpit/front-end binding,
6. optional local provider.

That gets the real value live quickly: a true deep chat that can answer ASADO questions, move the cockpit, and still respect the rule that the pipeline is the constitution and the agent is the colleague.
