---
type: "Reference"
title: "Loop and research workflows"
description: "ASADO's nightly alpha-hunting loop: dislocation engine, ledgers, harness verdicts, calibration reports, Triptych priors, graph features, and the canonical nightly brief."
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
- cockpit data refresh inputs

## Main research layers

### Dislocation engine
`scripts/loop/build_dislocations.py` is the nightly scan for places where ASADO subsystems disagree. The docstring is specific about the detector set and the rule that detector rows are classified by status across days.

Important ideas:
- Every detector encodes a trade archetype.
- Freshness checks matter; stale surfaces are excluded loudly.
- The brief is the Layer 2 reasoning input, not a generic report dump.
- D1, D2, D3, D4, D5, D7, D8, D9, D10 are the live detectors named in the docstring.

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

### JST risk report and long-cycle context
`build_jst_risk_report.py` and `docs/JST_MACROHISTORY_CALIBRATION.md` show another important distinction: JST macrohistory is an isolated calibration corpus, not a factor feed. The docs in `AGENTS.md` reinforce that it should never be merged into the normal factor panels.

## Discovery Triage in the nightly chain

The nightly loop job wires ASADO's quarantined LLM-native Discovery Lab near the end of the run, after `build_country_returns` (the return surface it reads) and before the cockpit refresh. `scripts/loop/loop_daily_job.py` runs two steps:

1. `discovery_forward_track` — `python -m scripts.discovery_triage.forward_track`, which appends forward readouts to the incubator/graveyard rosters (optional + no-op until claims are routed).
2. `discovery_docket` — `python -m scripts.discovery_triage.daily_docket --nightly`, gated so it no-ops unless `ASADO_RUN_DISCOVERY_LAB=1` (the nightly job never auto-spends on the Anthropic API).

Discovery Triage is a separate custody track, not another detector: it emits drafts, never signals, and writes only to the JSONL/YAML `journal/` ledgers. Its full design, invariants, and source map are documented in [Discovery Triage](discovery-triage.md).

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

- `scripts/loop/loop_daily_job.py`
- `scripts/loop/build_dislocations.py`
- `scripts/loop/ledgers.py`
- `scripts/loop/triptych_kernel.py`
- `tests/loop/test_harness_pit.py`
- `tests/loop/test_triptych.py`
- `PRD_Alpha_Hunting_Loop.md`
- `docs/TRIPTYCH_PREDICTION_WORKFLOW_2026_06_12.md`
- `docs/JST_MACROHISTORY_CALIBRATION.md`

## Where to go next

- [Architecture overview](architecture.md)
- [Operations and runbooks](operations.md)
- [Discovery Triage](discovery-triage.md)
- [Frontend and cockpit](frontend-and-cockpit.md)
