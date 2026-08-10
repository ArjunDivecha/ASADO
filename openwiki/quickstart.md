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
  - `scripts/monthly_update.py` (also wrapped by the interactive `run.py` + `dashboard.py` launchers) for the full warehouse / graph refresh.
  - `scripts/daily_update.py` for the daily T2 + GDELT metronome, with the loop job chained last.
- Maintains a separate loop database (`Data/loop/asado_loop.duckdb`) for the alpha-hunting layer, the Price-Discovery Gap Engine, the Learning Loop (gap-outcome scoring + attribution + Fable claims), dislocation engine, ledgers, harness verdicts, and derived research surfaces.
- Exposes the warehouse to interactive clients through `scripts/asado_mcp_server.py` and the cockpit payload in `cos_mockups/`.
- Runs focused experiments such as Brier Gate prediction-market scoring and the Triptych prior layer.

## Start here

1. [Architecture overview](architecture.md) — the warehouse, graph, loop DB, cadences, and major subsystems.
2. [Operations and runbooks](operations.md) — how to run the pipelines safely, prerequisites, and failure modes.
3. [Loop and research workflows](loop-and-research.md) — dislocations, the Price-Discovery Gap Engine, the Learning Loop, ledgers, harnesses, graph features, and nightly outputs.
4. [Discovery Triage](discovery-triage.md) — the quarantined LLM-native Discovery Lab and chain-of-custody Court: outcome-blind snapshots, model-cutoff provenance, blind rulings, and prospective forward tracking.
5. [Prediction markets and Brier Gate](prediction-markets.md) — corpus building, context packs, live shadow, and related surfaces.
6. [Frontend and cockpit](frontend-and-cockpit.md) — the Chief-of-Staff cockpit payload contract, plus the Streamlit dashboard and Perspective Lab frontends that are distinct from it.

## Canonical source docs worth knowing

- `README.md` — high-level platform overview and the current operational state.
- `CLAUDE.md` — coding conventions, architecture notes, and important system behavior.
- `AGENTS.md` — durable learned facts and operational guardrails.
- `docs/README.md` — documentation index that classifies canonical specs, generated docs, and snapshots.
- `docs/factor_reference.md` — canonical inventory of warehouse tables, variables, and graph structure.

## Major source areas

- `scripts/` — collectors, builders, orchestrators, QA checks, and harnesses.
- `scripts/loop/` — the alpha-hunting loop, nightly dislocation engine, Price-Discovery Gap Engine, and Learning Loop (gap-outcome scoring + attribution + Fable claims).
- `scripts/discovery_triage/` — the quarantined LLM Discovery Lab, provenance classifier, blind rulings, and forward-tracking Court.
- `scripts/brier_gate/` — prediction-market corpus, context pack, scoring, and live shadow workflow.
- `cos_mockups/` — Chief-of-Staff cockpit payload generation and UI bindings.
- `frontend/` — Streamlit research dashboard (`app.py`) and Perspective Lab workbench; distinct from the cockpit.
- `experiments/` — sandboxed, read-only experiments and prototypes (e.g. the learning-loop outcome scorer and the FDT mechanical backtest) that are not wired into the production loop DBs unless explicitly landed.
- `regime_ew/`, `regime_factor_selection/`, `regime_loop/` — regime-conditioning experiments with documented null/no-go results; see the Backlog.
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
- Learning-Loop and Discovery-Lab steps are optional and cost-gated (`ASADO_RUN_ATTRIBUTION_LLM`, `ASADO_RUN_DISCOVERY_LAB`); they no-op by default and must never red-light the nightly job.
- Gap-episode promotion scoring is frozen across `gap_engine.yaml` config versions so holdout rows stay comparable; bump the config version rather than silently changing promotion scoring.

## Linked pages

- [Architecture overview](architecture.md)
- [Operations and runbooks](operations.md)
- [Loop and research workflows](loop-and-research.md)
- [Discovery Triage](discovery-triage.md)
- [Prediction markets and Brier Gate](prediction-markets.md)
- [Frontend and cockpit](frontend-and-cockpit.md)

## Backlog

- `scripts/strategy/analogs/` (Strategy #1 — World-State Analogs) is a documented **no-go** experiment (PCA-stacked cross-section analog strategy showed no edge outside the 2008–2012 GFC window). Reusable primitives (`build_returns.py`, `pit_audit.py`, `baselines.py`, `config.py`, `tests/test_pit.py`) are kept; the core methodology scripts were removed. Not wired into the nightly loop. Source: `scripts/strategy/analogs/README.md`, `docs/strategy/analogs/v1/go_no_go.md`. No dedicated page yet because the strategy is retired; revisit if a v2 analog strategy is started.
- `regime_ew/` (Per-Country Regime Early-Warning) is a documented **no-go** experiment: HMM early-warning probability failed Gate 3 own-country return lead (17/34 negative, median rho −0.003). The contrarian strategy under `regime_ew/src/contrarian_strategy.py` is a negative return-overlay result. Not wired into the nightly loop. Source: `regime_ew/results/RESULTS.md`, `regime_ew/run_ew_test.py`, `PRD Per Country Regime EarlyWarning.md`. No dedicated page because the test stopped at Gate 3; revisit if a v2 early-warning design is started.
- `regime_factor_selection/` (Regime-Conditional Factor Selection) is a documented **null** result: 0 of 74 factors clear FDR (α=0.10) under the IP-regime test, with a placebo confirming the machinery is calibrated. Pre-registered STOP decision; not wired into the nightly loop. Source: `regime_factor_selection/results/RESULTS.md`, `regime_factor_selection/run_factor_regime_test.py`, `PRD Regime-Conditional Factor Selection.md`. No dedicated page because the result is a clean null; revisit only if a new regime-conditioning hypothesis is pre-registered.
- `experiments/fdt_mech_backtest/` (FDT mechanical backtest) confirmed a **negative** result: ASADO's stored signals produce negative net-of-cost active return in US-listed ETF space at every horizon, corroborating the standing Alpha Book law ("diffusion dies at the ETF close"). This is the ex-ante motivation for the Learning Loop. Source: `experiments/fdt_mech_backtest/RESULTS.md`, `experiments/fdt_mech_backtest/backtest_fdt_layers.py`. No dedicated page because it is a one-off registered backtest; the Learning Loop section of [Loop and research workflows](loop-and-research.md) is its durable successor.
