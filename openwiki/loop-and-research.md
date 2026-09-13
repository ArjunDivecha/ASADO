---
type: "Reference"
title: "Loop and research workflows"
description: "ASADO's nightly alpha-hunting loop: dislocation engine, Price-Discovery Gap Engine, ledgers, harness verdicts, calibration reports, Triptych priors, graph features, the Learning Loop (gap-outcome scoring + attribution + Fable claims), and the canonical nightly brief."
tags: [loop, gap-engine, learning-loop, triptych, harness, dislocations]
openwiki:
  roles: [architecture, domain, workflow, testing]
  change_kinds: [lifecycle, public-api]
  source_paths:
    - scripts/loop/loop_daily_job.py
    - scripts/loop/build_dislocations.py
    - scripts/loop/build_price_state.py
    - scripts/loop/build_gap_episodes.py
    - scripts/loop/render_dislocation_brief.py
    - scripts/loop/score_gap_outcomes.py
    - scripts/loop/attribute_outcomes.py
    - scripts/loop/build_fable_connections.py
    - config/gap_engine.yaml
    - config/loop_schema_contract.yaml
    - config/governance_contract.yaml
  symbols:
    - STEPS
    - _load_optional_steps
    - _acquire_singleton_lock
    - score_gap_outcomes
    - attribute_outcomes
    - write_claims
    - render_top_gaps
  test_paths:
    - tests/loop/
    - experiments/learning_loop/test_score_gap_outcomes.py
    - experiments/learning_loop/test_attribute_outcomes.py
  invariants:
    - Learning Loop steps are optional; a failure never red-lights the nightly job.
    - gap_outcomes is append-only (first-write-wins per outcome_id); pending episodes are not persisted until they mature.
    - Attribution code assigns the class, never the model; the Fable-xhigh lesson layer is gated behind ASADO_RUN_ATTRIBUTION_LLM=1.
    - Open-time gap promotion scoring is frozen across v1/v2 so holdout rows stay comparable.
  validation_commands:
    - "python -m pytest tests/loop -q"
    - "python -m pytest experiments/learning_loop -q"
---

# Loop and research workflows

The loop system is ASADO's nightly research and validation stack. It is separate from the main warehouse and is designed to generate dislocations, ledgers, harness verdicts, calibration reports, and briefings without contaminating the core analytical store.

## What the loop does

The loop job is described in `scripts/loop/loop_daily_job.py` and summarized in `README.md` / `CLAUDE.md`.

Its outputs include:
- `Data/loop/asado_loop.duckdb`
- `Data/dislocations/brief_YYYY_MM_DD.md`
- governance and run-manifest artifacts
- evidence packs and calibration reports
- research-ledger folds and thesis state
- Triptych priors and related surfaces
- Price-Discovery Gap Engine episodes, holdout rows, and Top Gaps marks
- Learning-Loop `gap_outcomes`, `outcome_attribution`, and `fable_claims` rows
- cockpit data refresh inputs (an early refresh after the Discovery docket and a final refresh as the true last step)

## Main research layers

### Dislocation engine
`scripts/loop/build_dislocations.py` is the nightly scan for places where ASADO subsystems disagree. The docstring is specific about the detector set and the rule that detector rows are classified by status across days.

Important ideas:
- Every detector encodes a trade archetype.
- Freshness checks matter; stale surfaces are excluded loudly.
- The brief is the Layer 2 reasoning input, not a generic report dump.
- D1, D2, D3, D4, D5, D7, D8, D9, D10 are the live detectors named in the docstring.

### Price-Discovery Gap Engine
The Gap Engine (`PRD_Price_Discovery_Gap_Engine.md`) is an enhancement layer over `dislocation_daily`, run after `build_dislocations`. It is an additive, feature-flagged pipeline configured by `config/gap_engine.yaml` (current `config_version: gap_engine_v2_2026_07_01`); disabling the `render_top_gaps` flag restores the original brief path, so the plain brief always exists before render runs.

The three nightly steps are:
- `build_price_state.py` — per-country world-state vs price tension marks.
- `build_gap_episodes.py` — promotes tension into ranked gap episodes (classes G1–G5 ranked; G6–G8 diagnostic; D8 never ranked), with holdout dedup at the source.
- `render_dislocation_brief.py` — renders the "Top Gaps" section into the nightly brief; `repriced_against` episodes are hard-capped below `promotion.min_tension_score` (via `mark_scoring.repriced_against_cap`) and excluded from Top Gaps, moved to a "Rejected by price / awaiting autopsy" section.

What matters:
- Open-time promotion scoring is frozen across v1/v2 so holdout rows stay comparable; the v2 change re-scores `tension_score_current` live at mark time rather than copying the open-time score forward.
- The holdout gate (`config/gap_engine.yaml::holdout`) requires **80 closed promoted episodes** with ≥3 controls each and Newey–West t-proceed/fail thresholds (`random_shadow_seed: shadow_v1`) before the gap engine is evidence-validated — this is quarters out, so the loop earns its evidence forward.
- The Gap Engine produces the `gap_episodes` and `gap_holdout_daily` tables that the Learning Loop scores; see the [Learning Loop](#learning-loop) section.

### Ledgers and harness
`AGENTS.md` and `README.md` point to the alpha-hunting loop discipline:
- hypotheses and theses are tracked in append-only JSONL ledgers under `ledgers/`,
- the skeptic harness evaluates signals with PIT embargo and Newey–West / deflated-Sharpe style gates,
- verdicts drive what survives into the cockpit and related surfaces.

The loop also has calibration reporting and cost / holding-period measurement logic referenced in the repo notes.

### Graph features and discovery
Several `scripts/loop/` modules produce explainability features or discovery surfaces:
- `build_graph_features.py`
- `build_graph_features_pit.py`
- `build_similarity_features.py`
- `build_leadlag_features.py`
- `build_combiner.py`
- `write_graph_discoveries.py`
- `build_family_ranks.py`
- `build_fable_connections.py`

The repo history and docstrings make a useful distinction between:
- PIT-vetted graph features,
- similarity / lead-lag features,
- the combiner surface,
- and non-deterministic Fable connection discovery.

### Triptych prior layer
`docs/TRIPTYCH_PREDICTION_WORKFLOW_2026_06_12.md`, `tests/loop/test_triptych.py`, and `scripts/loop/triptych_kernel.py` describe the Triptych prior workflow.

Key points:
- `triptych_kernel.py` is a pure analytics module ported from the visual tool.
- The ASADO scan is PIT disciplined and uses only approved scan inputs.
- Full-sample rows are descriptive-only and should not be treated as priors.
- The review queue is a triage surface, not evidence of return alpha.

### Release-date stamped economic surprise layer & event studies
`scripts/loop/load_release_events.py` and `scripts/loop/event_study.py` manage point-in-time macro release surprises:
- Ingests 41,349 release events across 10 concepts (CPI, Core CPI, PPI, GDP, Unemployment, Employment, PMI, IP, Retail Sales, Consumer Confidence) and 31 countries (1996-2026).
- Preserves exact announcement date (`release_date`) and tradeable date (`signal_date`), stored in `release_events_daily` and `release_events_signals`.
- Enables true daily event studies (`anchor=next_day`) in `event_study.py` across release presets (`release_growth_hot/cold`, `release_inflation_hot/cold`, `release_gdp_hot/cold`, `release_sentiment_hot/cold`, `release_pmi_hot/cold`, `release_cpi_hot/cold`).

### JST risk report and long-cycle context
`build_jst_risk_report.py` and `docs/JST_MACROHISTORY_CALIBRATION.md` show another important distinction: JST macrohistory is an isolated calibration corpus, not a factor feed. The docs in `AGENTS.md` reinforce that it should never be merged into the normal factor panels.

### Learning Loop
The Learning Loop is the "did the recommendation pay off, net of costs, vs the benchmark" measurement that the nightly loop previously lacked. It landed in the nightly job on 2026-07-10 as a set of **optional** steps (declared in `config/loop_schema_contract.yaml` and `config/governance_contract.yaml`); a failure is a warning and never red-lights the nightly run. Canonical design: `docs/LEARNING_LOOP_DESIGN_2026_07_10.md` and `docs/LEARNING_LOOP_STAGE0_SPEC_2026_07_10.md`; prototype status and run results in `experiments/learning_loop/RESULTS.md`.

It has four landed stages, all writing to the loop DB / ledgers and never to the main warehouse:

1. **Stage 1a — outcome scorer** (`scripts/loop/score_gap_outcomes.py`, runs after `build_country_returns`). For every promoted [gap episode](#price-discovery-gap-engine) and every eligible-but-not-promoted control, once it has been alive for its full declared horizon, it computes the honest, net-of-cost active return of the tradable ETF expression versus a per-episode window EW-34 (1/N buy-and-hold) benchmark, plus a decomposition into index-space information content and ETF capture. Writes the **append-only** `gap_outcomes` table (first-write-wins per `outcome_id`) and maintains `etf_total_return_daily` (yfinance adjusted-close total return; seeded from the FDT parquet, fail-soft nightly top-up that never fabricates a price). **Frozen conventions:** 25 bp/side (50 bp round-trip), entry = first ETF-calendar close strictly after `opened_at` (1-day PIT lag), exit = entry + horizon trading days; both directions scored for learning with a `tradable_long_only` flag for the long-only book. Reads the main warehouse **read-only** (attached as `asado`).

2. **Stage 2 — attribution** (`scripts/loop/attribute_outcomes.py`, runs after the scorer). A deterministic six-axis classifier — `data_validity`, `price_response`, `timing`, `expression`, `economics`, `horizon_fit` — scores each matured outcome and derives a headline class; **code assigns the class, never the model.** Writes append-only `outcome_attribution`. The Fable-xhigh lesson layer (explains the mechanism *within* the code-assigned axes and proposes a generalizable adjustment, appended to `ledgers/lesson_ledger.jsonl` with full provenance) is **gated** behind `ASADO_RUN_ATTRIBUTION_LLM=1` so it never auto-spends — the same cost-gate pattern the Discovery Lab uses.

3. **Stage 1c — capture clock.** `data_known_at` / `decision_available_at` / `absorbed_at` columns on `gap_outcomes` (idempotent ALTER); a gap with `absorbed_at < decision_available_at` is marked not capturable.

4. **Stage 3a — lessons digest.** The nightly Fable packet now carries `prior_lessons` (10 recent + 10 high-confidence) with a prompt rule to weigh them, so learning feeds back into the conjecture generator.

The Fable connections step (`build_fable_connections.py`) is the one deliberately non-deterministic loop step: it emits an optional structured `claim` per connection, which `write_claims` appends to the **append-only** `fable_claims` loop table (the "adapter 2" of the claim contract). `score_gap_outcomes` adapter 2 then grades Fable's own directional calls through the same outcome engine, so Fable conjectures are scored identically to gap-engine promotions. This is the bridge between the [Discovery / conjecture layer](discovery-triage.md) and the Learning Loop.

Honest current state (per `experiments/learning_loop/RESULTS.md`, last price 2026-07-09): no episode had matured yet at first landing (earliest 21d exit ≈ 2026-07-22), so a correct run inserts **0** scored rows and reports the pending backlog — this is the honest state, not a failure. The 80-closed-promoted-episode evidence gate is quarters out.

What to watch out for:
- `score_gap_outcomes` and `attribute_outcomes` are **optional** loop steps; do not make them red-light the nightly job when adding rows.
- The Fable lesson layer and the Discovery Lab are separately gated cost switches (`ASADO_RUN_ATTRIBUTION_LLM=1` and `ASADO_RUN_DISCOVERY_LAB=1`); never enable either in the nightly run unless you intend to spend.
- The outcome scorer reads `gap_episodes` / `gap_holdout_daily` from the [Gap Engine](#price-discovery-gap-engine); changes to gap-episode promotion or holdout dedup flow through to outcomes.
- `net_return_after_etf_drag` and the autopsy are direction-adjusted; falsified (`repriced_against`) gaps now close as explicit failures at `max_age` instead of lingering open.

## Discovery Triage in the nightly chain

The nightly loop job wires ASADO's quarantined LLM-native Discovery Lab near the end of the run, after `build_country_returns` (the return surface it reads) and before the cockpit refresh. `scripts/loop/loop_daily_job.py` runs two steps:

1. `discovery_forward_track` — `python -m scripts.discovery_triage.forward_track`, which appends forward readouts to the incubator/graveyard rosters (optional + no-op until claims are routed).
2. `discovery_docket` — `python -m scripts.discovery_triage.daily_docket --nightly`, gated so it no-ops unless `ASADO_RUN_DISCOVERY_LAB=1` (the nightly job never auto-spends on the Anthropic API).

Discovery Triage is a separate custody track, not another detector: it emits drafts, never signals, and writes only to the JSONL/YAML `journal/` ledgers. Its full design, invariants, and source map are documented in [Discovery Triage](discovery-triage.md).

## Nightly step ordering

The ordered `STEPS` chain in `scripts/loop/loop_daily_job.py` is the authoritative nightly sequence; the runbook for running it is in [Operations and runbooks](operations.md). The ordering that matters for correctness:

1. `collect_news_bridge` → `mark_theses` → `build_country_returns` (the return surface every downstream reader needs).
2. Learning Loop Stage 1a/2: `score_gap_outcomes` → `attribute_outcomes` (both optional; see [Learning Loop](#learning-loop)).
3. Discovery Triage: `discovery_forward_track` → `discovery_docket` (module invocations; cost-gated).
4. Early cockpit refresh (`build_cockpit_data` / `make_live_cockpit`) so the morning read is fast, *before* tonight's full output is ready.
5. Bloomberg flow loaders with the conda/venv split (foreign flows, sovereign CDS/10Y, ETF flows, consensus, COT, market-implied, sovereign ratings, eco surprise) — each BBG step appends a parquet that the next venv step merges and loads into the loop DB.
6. Graph machine: `build_graph_features_pit` → `build_similarity_features` → `build_leadlag_features` → `build_combiner` → `build_family_ranks` → `write_graph_discoveries` (the combiner depends on the three feature builders *and* the flow loaders).
7. `build_dislocations` → Gap Engine (`build_price_state` → `build_gap_episodes` → `render_dislocation_brief`) → `build_triptych_scan`.
8. `check_cross_source` (sentinel hard-stop + redundant-pair agreement) → `build_evidence_packs` (must run after dislocations).
9. `fold_ledgers` → `check_loop_schema` (consumer-column contract QA, `config/loop_schema_contract.yaml`) → `calibration_report` → `build_jst_risk_report` → `build_fable_connections` (the one non-deterministic step; `ASADO_SKIP_FABLE=1` or missing key → exit 2 PARTIAL).
10. Final cockpit refresh (`refresh_cockpit_data` / `refresh_live_cockpit`) as the true last step so the payload reflects everything this run produced; the browser's stale-tab poll picks the refresh up automatically.

A singleton `fcntl.flock` (`Data/loop/.loop_daily.lock`) guards against the 07:30 chained run and the 11:30 launchd safety-net rebuilding the loop DB concurrently. Which steps are optional (warning-only) is declared in `config/governance_contract.yaml` and loaded by `loop_daily_job.py::_load_optional_steps`.

## Nightly outputs and briefs

The dislocation brief is the canonical nightly artifact for human review. It is linked from the cockpit payload and is generated from the loop engine rather than hand-curated.

Related files:
- `Data/dislocations/brief_YYYY_MM_DD.md`
- `Data/loop/harness_runs/`
- `Data/loop/calibration/`
- `Data/loop/risk_reports/`
- `Data/loop/evidence_packs/`

## What to watch out for

- Do not use forward-return variables as signals; the repo explicitly blacklists them.
- Preserve point-in-time and vintage-aware rules in any new research surface.
- Keep the loop DB separate from the main warehouse.
- Treat detector freshness as part of correctness, not just performance.
- Be careful not to promote descriptive-only surfaces into alpha signals.

## Source references

- `scripts/loop/loop_daily_job.py` — ordered `STEPS` chain, singleton lock, optional-step loader.
- `scripts/loop/build_dislocations.py` — D1–D10 detectors.
- `scripts/loop/gap_engine_common.py`, `scripts/loop/build_price_state.py`, `scripts/loop/build_gap_episodes.py`, `scripts/loop/render_dislocation_brief.py` — Price-Discovery Gap Engine.
- `scripts/loop/score_gap_outcomes.py`, `scripts/loop/attribute_outcomes.py`, `scripts/loop/build_fable_connections.py` — Learning Loop stages 1a, 2, and the Fable-claim bridge.
- `config/gap_engine.yaml` — Gap Engine pre-registration (config version, promotion, holdout gate).
- `config/loop_schema_contract.yaml` — `gap_outcomes` / `fable_claims` / `outcome_attribution` optional columns.
- `config/governance_contract.yaml` — which loop steps are optional.
- `scripts/loop/ledgers.py`
- `scripts/loop/triptych_kernel.py`
- `tests/loop/test_harness_pit.py`, `tests/loop/test_triptych.py`, `tests/loop/test_gap_engine.py`, `tests/loop/test_ledger_integrity.py`, `tests/loop/test_run_manifest.py`, `tests/loop/test_methodology_ledger.py`, `tests/loop/test_pit_lag.py`
- `experiments/learning_loop/test_score_gap_outcomes.py`, `experiments/learning_loop/test_attribute_outcomes.py` — Learning Loop arithmetic/attribution validation.
- `PRD_Alpha_Hunting_Loop.md`, `PRD_Price_Discovery_Gap_Engine.md`
- `docs/TRIPTYCH_PREDICTION_WORKFLOW_2026_06_12.md`, `docs/JST_MACROHISTORY_CALIBRATION.md`
- `docs/LEARNING_LOOP_DESIGN_2026_07_10.md`, `docs/LEARNING_LOOP_STAGE0_SPEC_2026_07_10.md`

## Where to go next

- [Architecture overview](architecture.md)
- [Operations and runbooks](operations.md)
- [Discovery Triage](discovery-triage.md)
- [Frontend and cockpit](frontend-and-cockpit.md)
