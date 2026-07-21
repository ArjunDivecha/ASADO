---
type: "Reference"
title: "Architecture overview"
description: "ASADO's layered architecture: source collection, DuckDB warehouse, Neo4j graph, daily/monthly cadences, the separate loop database, and the cockpit/MCP query surface."
---

# Architecture overview

ASADO is organized around a few stable layers:

1. a source-specific collection layer under `scripts/`,
2. a monthly warehouse rebuild in DuckDB,
3. a daily extension for fast-moving surfaces,
4. a separate loop database for the alpha-hunting system,
5. a Neo4j graph for relational / explainability surfaces, and
6. a cockpit + MCP query surface for humans and agents.

## Core warehouse model

The main repository README describes the platform as a hybrid **DuckDB + Neo4j** stack for a 34-country universe. `README.md` and `CLAUDE.md` both emphasize that the main analytical store is the source of truth for explanatory context, while **returns are the outcome source of truth**.

Important source references:
- `README.md` — overall platform description and the monthly/daily split.
- `CLAUDE.md` — four-layer data model, T2 universe rules, and the warehouse / graph contract.
- `docs/factor_reference.md` — generated inventory of tables, variables, frequencies, and graph labels.

## The two cadences

### Monthly
`scripts/monthly_update.py` is the full rebuild orchestrator. Its docstring lists the collection stages, panel builders, DuckDB rebuild, Neo4j rebuild, schema registry refresh, and generated docs refresh.

What matters architecturally:
- It orchestrates collection from free sources, Bloomberg, GDELT Deep, optimizer returns, and commodity data.
- It regenerates the canonical DuckDB warehouse and the graph.
- It is safe to re-run because collectors preserve prior data if a source fails.

### Daily
`scripts/daily_update.py` is the daily metronome for the two fast-moving domains: T2 prices and GDELT news.

The daily pipeline is distinct because:
- T2 prices come directly from Bloomberg, not from hand-maintained spreadsheets.
- GDELT is refreshed at daily cadence.
- Econ is intentionally skipped because it has no daily factors.
- The loop job runs last so downstream detectors see fresh upstream data.
- Resume logic uses a script-content + argv fingerprint so a changed stage is re-run.

## Major stores and surfaces

### DuckDB warehouse
The main DB is `Data/asado.duckdb`. It contains the canonical normalized panels and daily extensions. `README.md` and `CLAUDE.md` both warn against creating persistent tables directly in this DB because `setup_duckdb.py` deletes and recreates it during rebuilds.

### Loop database
The loop system uses `Data/loop/asado_loop.duckdb`, which is separate from the main warehouse and holds:
- dislocations,
- ledgers,
- harness results,
- calibration reports,
- governance artifacts,
- Triptych priors,
- Brier Gate live shadow tables,
- and other nightly research outputs.

### Neo4j graph
`setup_neo4j.py` maintains the graph surface. The graph is used for explainability, bilateral relationships, similarity, lead-lag, and MCP browsing. `CLAUDE.md` notes that graph features are derived from the warehouse and that vector embeddings are part of the graph layer.

### MCP server and bridge
- `scripts/asado_mcp_server.py` exposes read-oriented query tools to MCP-speaking clients.
- `scripts/db_bridge.py` is the direct programmatic access layer for code that needs warehouse access.

## Major code domains

### Warehouse builders
The warehouse builders live at the top level of `scripts/`:
- `collect_external.py`, `collect_extended.py`, `collect_imf.py`, `collect_bilateral.py`, `collect_macrostructure.py`
- `collect_bloomberg.py`, `collect_t2_bloomberg.py`
- `build_t2_master.py`, `build_normalized_panel.py`, `build_daily_panels.py`, `build_schema_registry.py`, `build_factor_reference.py`
- `build_embeddings.py`, `setup_duckdb.py`, `setup_neo4j.py`

### Daily extension
`README.md`, `CLAUDE.md`, and `scripts/daily_update.py` show the daily extension is focused on T2 and GDELT, with daily return surfaces, optimizer outputs, and graph refreshes.

### Loop / research stack
The loop architecture is split into `scripts/loop/` plus `tests/loop/` and the dated briefs in `Data/dislocations/`. This is documented separately in [Loop and research workflows](loop-and-research.md).

### Prediction-market experiments
The Brier Gate code under `scripts/brier_gate/` is an isolated experiment pipeline that reads the warehouse in a PIT-safe way and scores forecast quality against market prices.

### Frontend / cockpit
`cos_mockups/` contains the generated cockpit payload and the UI-facing contract. The cockpit aggregates state from the loop DB, governance artifacts, and curated research outputs.

## Architectural guardrails

- Keep the main warehouse and the loop DB conceptually separate.
- Treat return surfaces as the outcome truth and all other data as explanatory unless explicitly joined back to returns.
- Preserve PIT discipline when building research surfaces.
- Do not let optimizer outputs create cycles inside the warehouse views.

## Where to go next

- [Operations and runbooks](operations.md)
- [Loop and research workflows](loop-and-research.md)
- [Prediction markets and Brier Gate](prediction-markets.md)
- [Frontend and cockpit](frontend-and-cockpit.md)
