---
type: "Reference"
title: "OpenWiki quickstart"
description: "Entry point for ASADO's OpenWiki knowledge base — a hybrid macro/research/trading platform for a 34-country universe with DuckDB, Neo4j, daily/monthly pipelines, an alpha-hunting loop, prediction-market experiments, and a Chief-of-Staff cockpit."
---

# OpenWiki quickstart

ASADO is a hybrid macro / research / trading platform for a 34-country universe. It combines a DuckDB analytical warehouse, a Neo4j graph, daily and monthly data pipelines, a loop database for the alpha-hunting system, prediction-market experiments, and a Chief-of-Staff cockpit for surfacing signals and governance.

If you are a new human or agent, start here and then follow the links below.

## What this repo does

- Collects and normalizes macro, market, news, commodity, prediction-market, and graph data for the T2 country universe.
- Runs two main cadences:
  - `scripts/monthly_update.py` for the full warehouse / graph refresh.
  - `scripts/daily_update.py` for the daily T2 + GDELT metronome, with the loop job chained last.
- Maintains a separate loop database (`Data/loop/asado_loop.duckdb`) for the alpha-hunting layer, dislocation engine, ledgers, harness verdicts, and derived research surfaces.
- Exposes the warehouse to interactive clients through `scripts/asado_mcp_server.py` and the cockpit payload in `cos_mockups/`.
- Runs focused experiments such as Brier Gate prediction-market scoring and the Triptych prior layer.

## Start here

1. [Architecture overview](architecture.md) — the warehouse, graph, loop DB, cadences, and major subsystems.
2. [Operations and runbooks](operations.md) — how to run the pipelines safely, prerequisites, and failure modes.
3. [Loop and research workflows](loop-and-research.md) — dislocations, ledgers, harnesses, and nightly outputs.
4. [Discovery Triage](discovery-triage.md) — the quarantined LLM-native Discovery Lab and chain-of-custody Court: outcome-blind snapshots, model-cutoff provenance, blind rulings, and prospective forward tracking.
5. [Prediction markets and Brier Gate](prediction-markets.md) — corpus building, context packs, live shadow, and related surfaces.
6. [Frontend and cockpit](frontend-and-cockpit.md) — the live cockpit payload contract and Phase 2 binding logic.

## Canonical source docs worth knowing

- `README.md` — high-level platform overview and the current operational state.
- `CLAUDE.md` — coding conventions, architecture notes, and important system behavior.
- `AGENTS.md` — durable learned facts and operational guardrails.
- `docs/README.md` — documentation index that classifies canonical specs, generated docs, and snapshots.
- `docs/factor_reference.md` — canonical inventory of warehouse tables, variables, and graph structure.

## Major source areas

- `scripts/` — collectors, builders, orchestrators, QA checks, and harnesses.
- `scripts/loop/` — the alpha-hunting loop and nightly dislocation engine.
- `scripts/discovery_triage/` — the quarantined LLM Discovery Lab, provenance classifier, blind rulings, and forward-tracking Court.
- `scripts/brier_gate/` — prediction-market corpus, context pack, scoring, and live shadow workflow.
- `cos_mockups/` — Chief-of-Staff cockpit payload generation and UI bindings.
- `tests/loop/` — invariants for the loop, harness, frontend, and PIT behavior.
- `tests/discovery_triage/` — offline invariants for the Discovery Lab, provenance, blind rulings, and forward tracking.
- `docs/` — canonical specs, audits, and dated reports.
- `config/` — registries and contract files that shape the live pipelines.

## Editing guidance for future agents

- Prefer the loop DB and generated docs when reasoning about nightly behavior; do not infer from stale reports alone.
- Never treat forward-return variables such as `1MRet` as signals; they are targets and are explicitly blacklisted in the research layer.
- Be careful with point-in-time discipline: several systems enforce date cutoffs, publication lags, or vintage-aware queries.
- If you change cockpit fields, update the producer, consumer, and the contract together.
- If you change a pipeline stage, check whether the daily resume fingerprint or lock-guard behavior also needs to be updated.

## Linked pages

- [Architecture overview](architecture.md)
- [Operations and runbooks](operations.md)
- [Loop and research workflows](loop-and-research.md)
- [Discovery Triage](discovery-triage.md)
- [Prediction markets and Brier Gate](prediction-markets.md)
- [Frontend and cockpit](frontend-and-cockpit.md)

## Backlog

- `scripts/strategy/analogs/` (Strategy #1 — World-State Analogs) is a documented **no-go** experiment (PCA-stacked cross-section analog strategy showed no edge outside the 2008–2012 GFC window). Reusable primitives (`build_returns.py`, `pit_audit.py`, `baselines.py`, `config.py`, `tests/test_pit.py`) are kept; the core methodology scripts were removed. Not wired into the nightly loop. Source: `scripts/strategy/analogs/README.md`, `docs/strategy/analogs/v1/go_no_go.md`. No dedicated page yet because the strategy is retired; revisit if a v2 analog strategy is started.
