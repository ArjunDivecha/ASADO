---
type: "Reference"
title: "Prediction markets and Brier Gate"
description: "ASADO's prediction-market surfaces: the general predmkt pipeline and the Brier Gate experiment that tests whether the warehouse adds incremental forecasting value over market prices."
---

# Prediction markets and Brier Gate

ASADO has two related prediction-market surfaces:

1. the general prediction-market pipeline and nightly job, and
2. the dedicated Brier Gate experiment that asks whether ASADO + a model can beat the market price on resolved binary contracts.

## General prediction-market surface

`AGENTS.md` and the repository history show that prediction-market data is part of the broader loop / daily system. The relevant scripts include:
- `scripts/build_predmkt_panel.py`
- `scripts/predmkt_daily_job.py`
- `scripts/discover_predmkt_equity_universe.py`
- `scripts/poll_predmkt_intraday.py`
- `scripts/predmkt_equity_daily_job.py`
- `scripts/brier_gate/*`

The repo uses curated registries and careful sign conventions. The `AGENTS.md` notes about prediction markets emphasize that the registry and signs matter for country composites and that resolved markets remain in the registry for tracking.

## Brier Gate purpose

`docs/PRD_BRIER_GATE.md` is the canonical spec. It defines a gate-first experiment:
- A0 baseline: question + rules only
- A1 +warehouse: A0 plus a point-in-time ASADO context pack
- A2 +market: A1 plus the market price

The key question is whether the warehouse adds incremental value and whether the resulting forecasts outperform the market on Brier score and economically after spread.

## Brier Gate pipeline

The Brier Gate scripts form a small pipeline:

- `scripts/brier_gate/build_corpus.py`
  - builds the retrospective corpus from resolved Polymarket markets in specific macro tags,
  - uses a 30-day retention window,
  - screens out markets already effectively resolved at forecast time.

- `scripts/brier_gate/context_packs.py`
  - builds point-in-time ASADO context packs from the loop DB and warehouse,
  - applies a full-day embargo so a daily value becomes visible only the following day,
  - selectively includes risk, commodity, rates, and country context depending on the question.

- `scripts/brier_gate/run_forecasts.py`
  - runs the forecast jobs and persists the individual outputs.

- `scripts/brier_gate/score.py`
  - computes Brier / log-loss / calibration / threshold-rule PnL and writes reports.

- `scripts/brier_gate/live_shadow.py`
  - live validation mode; it writes forecasts before resolution, scores later, and explicitly does not place orders.

## Current status and business logic

The PRD and results docs show the experiment has already been executed and then moved into live shadow / hold status depending on the market venue constraint. For future work, the important thing is that the experiment is about **validation**, not production trading, unless the gate criteria are met.

## Important constraints

- The context pack must be PIT-safe.
- The market price is only one arm; the warehouse value must be separable from the market deferral effect.
- Thin-book PnL is an upper bound, not a guarantee of executable economics.
- The live shadow writes only to the loop DB and audit logs.

## Source references

- `docs/PRD_BRIER_GATE.md`
- `docs/BRIER_GATE_RESULTS_2026_07_04.md`
- `scripts/brier_gate/build_corpus.py`
- `scripts/brier_gate/context_packs.py`
- `scripts/brier_gate/run_forecasts.py`
- `scripts/brier_gate/score.py`
- `scripts/brier_gate/live_shadow.py`
- `scripts/build_predmkt_panel.py`
- `scripts/predmkt_daily_job.py`
- `scripts/discover_predmkt_equity_universe.py`
- `config/predmkt_equity_universe.yaml`

## Where to go next

- [Architecture overview](architecture.md)
- [Operations and runbooks](operations.md)
- [Frontend and cockpit](frontend-and-cockpit.md)
