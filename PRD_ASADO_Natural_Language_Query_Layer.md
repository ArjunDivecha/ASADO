# ASADO Natural-Language Query Layer
## Product Requirements Document v1.0

**Project:** ASADO  
**Author:** Codex (refined from Arjun's architecture notes)  
**Date:** April 17, 2026  
**Status:** Draft - ready for implementation planning  
**Primary users:** Arjun, future ASADO research agents, and analyst-facing UI surfaces

---

## 1. Purpose

Build a natural-language query layer on top of the existing ASADO DuckDB + Neo4j stack so an analyst can ask plain-English research questions and get back:

1. a correct interpretation of the question,
2. the generated SQL, Cypher, or hybrid execution plan,
3. the executed results, and
4. a concise interpretation with caveats.

The core requirement is not "let the LLM freely read the database." The requirement is to give the LLM a safe, schema-aware, read-only abstraction over the database so it can reason accurately about the ASADO data model without hallucinating table names, factor names, or graph relationships.

---

## 2. Background And Current State

ASADO already has the core data infrastructure:

- DuckDB analytical store at `Data/asado.duckdb`
- Neo4j graph at `bolt://localhost:7687`
- Unified Python bridge in `scripts/db_bridge.py`
- Streamlit frontend in `frontend/app.py`
- Existing raw query surface in the "Free Query Playground" tab of the frontend

Current data footprint from the repo README:

- DuckDB `unified_panel`: 1,910,775 rows, 332 variables, 34 countries
- Neo4j: 446 nodes, 6,522 edges
- Vector index: `countryStateIndex` on `Country.state_embedding`

This means ASADO already supports:

- direct SQL against time-series panel data,
- direct Cypher against graph relationships,
- vector similarity search in Neo4j,
- convenience methods such as `country_profile()` and `factor_snapshot()`

What is missing is a semantic layer that lets an LLM use those capabilities reliably without requiring the user to manually write SQL/Cypher or remember the exact schema.

---

## 3. Problem Statement

Raw database access is useful for technical users but insufficient for the intended research workflow.

Current limitations:

- The user must know exact table names, variable names, and graph edge names.
- Multi-step questions require hand-written hybrid logic across DuckDB and Neo4j.
- There is no schema registry tailored for LLM consumption.
- There is no safe execution layer that validates or constrains LLM-generated queries.
- There is no analyst-friendly interface for "ask a question, inspect the plan, run it, explain it."

As a result, ASADO has strong data infrastructure but a weak analyst interface.

---

## 4. Product Vision

ASADO should expose a research copilot that answers questions such as:

- "Which countries look cheap on valuation but have worsening GDELT risk?"
- "Show me countries with high BIS credit gaps and heavy trade exposure to sanctioned economies."
- "Find the nearest analogs to Turkey's current factor state and show what happened next."
- "Which countries have improving PMI and falling inflation expectations at the same time?"

The user should not need to know whether the answer comes from DuckDB, Neo4j, or both. The system should route the query, execute it safely, and return both the evidence and the interpretation.

---

## 5. Goals

### 5.1 Primary Goals

1. Let users query ASADO in natural language.
2. Use the existing `AsadoDB` bridge as the execution backbone rather than building a separate database access stack.
3. Support DuckDB-only, Neo4j-only, and hybrid queries.
4. Make the execution plan transparent by always showing the generated SQL/Cypher before or alongside results.
5. Keep the system read-only in v1.
6. Minimize hallucinations through schema introspection, variable catalogs, and strict query validation.
7. Integrate into the current ASADO frontend so the capability is immediately usable.

### 5.2 Secondary Goals

1. Expose the same capability to scripts and future autonomous agents.
2. Log questions, generated plans, execution metadata, and failures for iterative improvement.
3. Make the system extensible to an MCP server or LoopPilot/Mythos workflow later.

---

## 6. Non-Goals For v1

1. No write access to DuckDB or Neo4j.
2. No autonomous trading, portfolio construction, or order generation.
3. No full research-agent loop that generates and tests hundreds of hypotheses automatically.
4. No generic BI tool replacement.
5. No attempt to let the LLM see raw full-table dumps by default.
6. No production multi-user auth layer unless the surface is later exposed beyond local use.

LoopPilot/Mythos integration is a future phase, not part of this first product boundary.

---

## 7. Recommended Product Shape

The recommended v1 product is a **schema-aware, read-only query assistant** layered on top of `scripts/db_bridge.py`, with three access surfaces:

1. **Frontend chat/query tab**
   - Analyst enters a natural-language question in the existing Streamlit app.
   - The app shows understanding, plan, generated query, results, and interpretation.

2. **Python entrypoint**
   - A script or module that can be called from notebooks, cron jobs, or future agents.

3. **Optional API surface**
   - A small local service endpoint if needed for decoupled UI access.

The important architectural point is that the LLM should generate a **structured execution plan**, not free-form opaque text.

---

## 8. User Stories

### 8.1 Human Analyst

- As an analyst, I want to ask a plain-English question and get the answer without writing SQL or Cypher myself.
- As an analyst, I want to inspect the generated query so I can trust or edit it.
- As an analyst, I want the system to warn me when my request is ambiguous or exceeds the safe query boundary.

### 8.2 Power User

- As a power user, I want to use the generated query as a starting point and then refine it manually.
- As a power user, I want saved query templates and schema search so I can move faster.

### 8.3 Future Research Agent

- As a future ASADO research agent, I want a programmatic interface that turns hypotheses into validated queries against the current ASADO schema.

---

## 9. Core Product Requirements

### 9.1 Schema Registry

The system must maintain an LLM-friendly schema registry generated from the live databases.

It must include:

- DuckDB table list
- column names and types
- row counts
- date ranges
- distinct country coverage
- factor/variable catalog
- sample rows
- Neo4j node labels
- relationship types
- key properties by label
- vector index metadata
- curated descriptions for important tables, node types, and relationships

Suggested output files:

- `Data/cache/query_assistant/duckdb_schema.json`
- `Data/cache/query_assistant/neo4j_schema.json`
- `Data/cache/query_assistant/variable_catalog.json`

The schema cache should be refreshable after monthly rebuilds.

### 9.2 Structured Query Planning

Given a user question, the LLM must return structured output with fields such as:

- `understanding`
- `intent_type`
- `data_sources_needed`
- `tables_or_labels`
- `filters`
- `date_range`
- `countries`
- `query_mode` (`duckdb`, `neo4j`, or `hybrid`)
- `duckdb_sql`
- `neo4j_cypher`
- `post_processing_steps`
- `expected_output`
- `confidence`
- `clarification_needed`

If confidence is low, the system should ask for clarification rather than guessing.

### 9.3 Read-Only Query Validation

Before execution, the system must validate generated queries.

Validation rules:

- read-only only
- no DDL or DML
- no file writes
- no unrestricted full-table scans unless row limits are explicit
- enforce default row limits for preview results
- reject unknown tables, labels, relationships, and columns when they do not appear in the schema registry
- require parameterized filters where possible
- apply execution timeout limits

The validator should fail closed.

### 9.4 Hybrid Query Orchestration

The system must support at least three query patterns:

1. **DuckDB only**
   - time-series, ranking, aggregation, factor comparisons, panel filtering

2. **Neo4j only**
   - network traversal, sanctions, crisis history, trade/banking relationships, similarity search

3. **Hybrid**
   - graph-first then panel filter
   - panel-first then graph enrich
   - vector similarity followed by DuckDB retrieval

Example hybrid flow:

1. find countries in Neo4j that trade heavily with sanctioned countries,
2. pass those country names into DuckDB,
3. retrieve current valuation and macro factors,
4. rank and summarize.

### 9.5 Result Interpretation

After execution, the system must interpret results in the context of the original question.

The answer should include:

- what the query actually measured,
- the main findings,
- relevant caveats,
- any missing coverage or schema limitations,
- suggested follow-up questions

Interpretation must stay grounded in the returned data and query plan.

### 9.6 Analyst UX In The Frontend

The Streamlit app should gain a new natural-language query experience, either as:

- a new "Ask ASADO" tab, or
- an expanded version of the current query playground

Minimum UI elements:

- question input box
- optional model/provider selector
- "understanding" panel
- generated SQL/Cypher preview
- execute button
- results table
- interpretation panel
- error and caveat display
- toggle to inspect raw plan JSON

The existing raw SQL/Cypher playground should remain for power users.

### 9.7 Programmatic Interface

The system must expose a reusable Python API, for example:

```python
response = assistant.ask(
    question="Which EM countries have rising inflation but improving PMI?",
    preview_only=False
)
```

Return object should include:

- question
- plan
- generated query or queries
- execution metadata
- result dataframe or records
- interpretation
- warnings

### 9.8 Logging And Audit Trail

The system must log:

- question text
- timestamp
- chosen query mode
- generated plan
- executed SQL/Cypher
- execution duration
- row count returned
- validation failures
- user edits to generated queries, if supported in UI

Suggested location:

- `Data/logs/query_assistant/`

This is important because LLM query quality will improve through observed failures and common patterns.

---

## 10. Functional Design

### 10.1 Proposed Components

#### A. Schema Builder

New script/module that inspects DuckDB and Neo4j and writes cached schema artifacts.

Suggested file:

- `scripts/build_schema_registry.py`

#### B. Query Assistant Engine

Core module that:

1. loads schema cache,
2. sends schema + question to the LLM,
3. receives structured plan output,
4. validates the plan,
5. executes through `AsadoDB`,
6. interprets results,
7. returns a structured response object

Suggested file:

- `scripts/query_assistant.py`

#### C. Frontend Integration

Extend `frontend/app.py` with natural-language query UX.

#### D. Optional Local Service Layer

If needed, wrap the assistant engine in FastAPI for local calls from UI or external tools.

Suggested file:

- `frontend/query_api.py` or `api/query_service.py`

### 10.2 Recommended Execution Backbone

The assistant must use `scripts/db_bridge.py` for actual database calls. That keeps all DB access centralized and avoids duplicate connection logic.

### 10.3 LLM Provider Boundary

The query assistant should be model-provider agnostic.

Supported v1 options:

- Anthropic API
- OpenAI API
- local model if a structured-output-capable local model is later preferred

Only one provider is required for v1, but the abstraction should not hardcode prompt logic to a single vendor.

---

## 11. Data And Query Safety Requirements

### 11.1 Read-Only Boundary

All generated queries must be read-only. This includes:

- no `CREATE`, `DROP`, `ALTER`, `INSERT`, `UPDATE`, `DELETE`, `COPY`, or export statements
- no Neo4j write clauses such as `CREATE`, `MERGE`, `SET`, `DELETE`, `REMOVE`

### 11.2 Size Controls

Default preview behavior:

- cap returned rows in UI
- summarize large result sets
- allow export only as an explicit user action

### 11.3 Ambiguity Handling

The system must ask for clarification when a question is underspecified, for example:

- "cheap" without a factor definition
- "recent" without a time window
- "risk" without specifying GDELT, sanctions, crisis history, CDS, or another risk family

### 11.4 Failure Behavior

On failure, the assistant must return:

- what it tried,
- why validation or execution failed,
- a corrected suggestion where possible

It must not silently fabricate an answer.

---

## 12. Example Query Types

### 12.1 Pure DuckDB

"Which countries have the lowest current `Best PE_CS` values and positive PMI momentum?"

### 12.2 Pure Neo4j

"Which countries have historical crisis exposure and active sanctions relationships?"

### 12.3 Hybrid

"Show countries with high BIS credit gaps that trade heavily with sanctioned countries."

### 12.4 Similarity Search

"Find the five countries most similar to Turkey's current factor state and summarize how they differ on inflation and growth."

### 12.5 Country Dossier

"Give me a current ASADO profile for Brazil covering valuation, macro, trade exposure, sanctions, and crisis history."

---

## 13. Success Metrics

The product will be considered successful when:

1. At least 80% of a curated benchmark set of natural-language questions compile to a valid plan on the first attempt.
2. At least 90% of validated plans execute successfully against the current ASADO stack.
3. The system routes correctly between DuckDB, Neo4j, and hybrid execution for benchmark queries.
4. Analysts prefer the natural-language assistant over writing raw queries for common exploratory questions.
5. The frontend supports end-to-end question -> plan -> execution -> interpretation without leaving the app.

Suggested benchmark set:

- 25 to 50 representative research questions spanning panel, graph, hybrid, and similarity queries

---

## 14. Implementation Plan

### Phase 1 - Schema Foundation

Build schema introspection and cache generation.

Deliverables:

- DuckDB schema extraction
- Neo4j schema extraction
- variable catalog export
- schema cache files under `Data/schema_cache/`

### Phase 2 - Query Planning And Validation

Build the natural-language planner and validation layer.

Deliverables:

- structured plan schema
- LLM prompt and parser
- query validator
- execution wrapper through `AsadoDB`

### Phase 3 - Frontend UX

Add natural-language query experience to Streamlit.

Deliverables:

- question input
- plan preview
- query preview
- result grid
- interpretation panel
- error handling

### Phase 4 - Benchmarking And Hardening

Test the assistant on a fixed question suite and refine prompts/validation.

Deliverables:

- benchmark question set
- pass/fail logs
- common failure taxonomy
- revised prompt and routing rules

### Phase 5 - Optional Agent Surface

Expose the same assistant to external agent tooling.

Candidate follow-ons:

- local FastAPI endpoint
- MCP server for external LLM clients
- LoopPilot/Mythos integration for hypothesis-driven research loops

---

## 15. Risks And Mitigations

### Risk 1: Schema hallucination

Mitigation:

- use live schema cache,
- validate all generated identifiers,
- fail closed on unknown names

### Risk 2: Wrong routing between DuckDB and Neo4j

Mitigation:

- include explicit query-mode classification,
- benchmark routing accuracy,
- add hybrid templates for common patterns

### Risk 3: Expensive or unbounded queries

Mitigation:

- default row caps,
- timeouts,
- mandatory preview mode for large scans

### Risk 4: Ambiguous analyst language

Mitigation:

- require clarification when confidence is low,
- support a factor glossary and query cookbook

### Risk 5: LLM interpretation drift

Mitigation:

- ground interpretation on returned rows and executed query,
- show the raw query and result preview to the user

---

## 16. Open Questions

1. Should v1 ship first inside the Streamlit frontend only, or should it also ship with a local API from day one?
2. Which provider should be the initial default for structured planning: Anthropic, OpenAI, or a local model?
3. Should users be able to edit generated SQL/Cypher before execution in the UI?
4. Should the assistant support chart generation in v1, or only table results plus narrative?
5. Should saved question templates be stored locally in the repo or per-user outside the repo?

---

## 17. Final Recommendation

The best way to "let an LLM read ASADO" is **not** to hand it raw unrestricted database access. The best way is to build a **schema-aware query assistant** that sits on top of the existing `AsadoDB` bridge, keeps execution read-only, shows its work, and supports DuckDB, Neo4j, and hybrid queries through one analyst-facing interface.

That gives ASADO:

- immediate usability for discretionary research,
- a reusable interface for future agents,
- far lower hallucination risk than direct raw prompting,
- and a clean path to later MCP or LoopPilot integration.
