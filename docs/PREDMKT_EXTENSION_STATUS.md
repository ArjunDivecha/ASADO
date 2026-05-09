# ASADO Prediction-Market Extension — Implementation Status

**Date:** 2026-05-08  
**Status:** Stage 2 V1 implementation wired end-to-end (ingestion script, DuckDB tables, orchestrator integration, schema/query/MCP surfaces, docs).

---

## What Was Built

### New Config + Builder

- `config/predmkt_curated.yaml`
  - Hand-curated market registry (Kalshi + Polymarket) with:
    - category + subcategory tags
    - resolution clarity
    - spillover-country mappings with elasticity/channel/confidence
- `scripts/build_predmkt_panel.py`
  - Daily prediction-market snapshot puller
  - DuckDB backup/restore safety
  - Registry validation (platform ids, spillover taxonomy, country names)
  - Per-market failure isolation (single market failure does not abort run)
  - Derived signal materialization + variable_meta upsert

### New DuckDB Tables

| Table | Purpose |
|---|---|
| `predmkt_daily` | Daily implied probabilities, book fields, liquidity, stale flags, resolution state |
| `predmkt_market_meta` | Market metadata + ASADO category mapping |
| `predmkt_outcome_meta` | Outcome labels + scalar thresholds |
| `predmkt_country_spillover` | Hand-curated spillover bridge to T2 countries |
| `predmkt_resolutions` | Resolution archive for calibration tracking |
| `predmkt_signals_daily` | Derived composites and country-level prediction-market signals |

### Orchestration Wiring

- `scripts/monthly_update.py` now runs:
  - `build_predmkt_panel.py`
  - positioned after `build_daily_panels.py` and before schema refresh

### Metadata + Query-Surface Wiring

- `scripts/build_daily_panels.py`
  - `build_variable_meta()` now appends `predmkt_signals_daily` variables when present
- `scripts/build_schema_registry.py`
  - table descriptions include all prediction-market tables
  - source frequencies include `predmkt_signal`
  - variable catalog now appends `predmkt_signals_daily` signal names (not only `feature_panel`)
- `scripts/query_assistant.py`
  - planner context includes prediction-market guidance for future-probability and off-universe-entity questions
- `scripts/asado_mcp_server.py`
  - added:
    - `predmkt_snapshot(category, date=today, max_rows=200)`
    - `country_signal_now(country, channels=None, date=today, max_rows=200)`
    - `event_market_set(keyword, max_rows=100)`

### Validation Suite Updates

- `scripts/run_query_assistant_suite.py`
  - adds prediction-market NL cases when `predmkt_daily` + `predmkt_signals_daily` tables exist

---

## Current Build Snapshot (Local Verification)

Latest local run of `python scripts/build_predmkt_panel.py --stats` produced:

- `predmkt_daily`: 22 rows
- `predmkt_market_meta`: 11 rows
- `predmkt_outcome_meta`: 22 rows
- `predmkt_country_spillover`: 41 rows
- `predmkt_resolutions`: 0 rows
- `predmkt_signals_daily`: 45 rows
- distinct `signal_name`: 14

---

## Known Caveats

1. Kalshi requests currently return HTTP 401 from this environment, so Kalshi rows are not loading in current local runs.
2. Polymarket ingestion is active; resulting composites currently reflect available Polymarket coverage.
3. `predmkt_resolutions` populates as markets resolve over time; zero rows is expected at first build if no curated market resolves that day.

---

## Recommended Daily/Monthly Runbook

1. Validate registry quickly:
   - `python scripts/build_predmkt_panel.py --check`
2. Build prediction-market surfaces:
   - `python scripts/build_predmkt_panel.py --stats`
3. Refresh schema cache after structural changes:
   - `python scripts/build_schema_registry.py --duck-only`
4. Run full monthly orchestration when scheduled:
   - `python scripts/monthly_update.py`

