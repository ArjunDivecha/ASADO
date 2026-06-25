# Morning Report — Price-Discovery Gap Engine Build

Date: 2026-06-24

Scope: Implement the Opus/Sakana-vetted `PRD_Price_Discovery_Gap_Engine.md` as an additive pilot layer over the existing ASADO loop.

## Built

- Added `config/gap_engine.yaml`
  - v1 scoring weights and config version
  - promotion gates
  - liquidity thresholds
  - class-specific expected-move mapping
  - holdout proceed/fail/inconclusive thresholds
  - governance-dimension dependency mapping
  - detector-to-gap-class map and deterministic mechanism templates

- Added `config/etf_expression_overrides.yaml`
  - v1 ETF expression metadata
  - expense-ratio seed values
  - default `usd_unhedged_etf_vs_t2` currency basis

- Added `scripts/loop/gap_engine_common.py`
  - config/hash helpers
  - stable hashing
  - scoring math
  - expected-move and absorption-state helpers

- Added `scripts/loop/build_price_state.py`
  - writes `price_state_daily`
  - writes `price_state_surface`
  - derives ETF returns, T2 returns, ETF ADV, ETF-vs-T2 basis, liquidity tier, and source freshness
  - stores parquet artifacts under `Data/loop/gap_engine/`

- Added `scripts/loop/build_gap_episodes.py`
  - writes `gap_episodes`
  - writes `gap_episode_expression`
  - writes `gap_episode_marks`
  - writes `gap_episode_autopsy`
  - writes `gap_holdout_daily`
  - stores config hashes, score components, deterministic candidate IDs, random-shadow scores, and stable `gap_id_seed`

- Added `scripts/loop/render_dislocation_brief.py`
  - feature-flagged renderer for the pilot top section
  - inserts `Top Price-Discovery Gaps (pilot)` after governance and before the raw dislocation table
  - labels severity-mapped absorption as provisional
  - dedupes top slots by `entity|direction`

- Wired new steps into `scripts/loop/loop_daily_job.py`
  - `build_price_state`
  - `build_gap_episodes`
  - `render_dislocation_brief`

- Updated `config/governance_contract.yaml`
  - manifest now expects the new loop tables and parquet artifacts

- Added `tests/loop/test_gap_engine.py`
  - stable gap identity checks
  - absorption-state checks
  - renderer idempotence and governance insertion checks
  - entity/direction dedup check
  - live table/schema/JSON/hash checks when the loop DB exists

## Live Smoke Output

Latest data as-of: `2026-06-22`

Loop DB tables:

- `price_state_daily`: 34 rows, max date `2026-06-22`
- `price_state_surface`: 272 rows, max date `2026-06-22`
- `gap_episodes`: 8 open episodes
- `gap_episode_marks`: 8 rows, max date `2026-06-22`
- `gap_holdout_daily`: 87 rows, max date `2026-06-22`

Gap classes currently opened:

- `G3`: 5
- `G2`: 3

Rendered brief:

- `Data/dislocations/brief_2026_06_22.md`
- Top pilot gaps: Mexico short, Turkey short, Taiwan short, Saudi Arabia long, Hong Kong long

## Validation

Passed:

- `venv/bin/python -m py_compile scripts/loop/gap_engine_common.py scripts/loop/build_price_state.py scripts/loop/build_gap_episodes.py scripts/loop/render_dislocation_brief.py scripts/loop/loop_daily_job.py tests/loop/test_gap_engine.py`
- `venv/bin/python -m pytest tests/loop/test_gap_engine.py -q`
  - 6 passed
- `venv/bin/python -m pytest tests/loop/test_gap_engine.py tests/loop/test_run_manifest.py -q`
  - 22 passed
- `venv/bin/python scripts/loop/build_price_state.py`
  - 34 price-state rows, 272 surface rows
- `venv/bin/python scripts/loop/build_gap_episodes.py`
  - first run: 8 new episodes, 87 holdout rows, 8 marks
  - rerun: 0 new episodes, 87 holdout rows, 8 marks
- `venv/bin/python scripts/loop/render_dislocation_brief.py`
  - updated the 2026-06-22 brief
- `venv/bin/python scripts/loop/loop_daily_job.py --only build_price_state`
- `venv/bin/python scripts/loop/loop_daily_job.py --only build_gap_episodes`
- `venv/bin/python scripts/loop/loop_daily_job.py --only render_dislocation_brief`

Broader daily validation:

- `venv/bin/python tests/loop/test_daily_pipeline.py --date 2026-06-22`
  - 20 passed
  - 2 failed

The two failures are outside the new gap-engine path:

- `gdelt_factors_daily` max date is `2026-06-11`, expected at least `2026-06-21`
- open theses count is `2`, validator expects at least `3`

Resolved later on 2026-06-24:

- Daily GDELT now refreshes from the upstream parquet path and validates raw-vs-normalized freshness.
- The thesis validator now checks total seed-thesis history instead of requiring all three original seed theses to remain open after one was deliberately killed at review.
- `tests/loop/test_daily_pipeline.py --date 2026-06-23` now reports `24 passed, 0 failed`.

## Operational Notes

- The new engine is additive. It does not replace `dislocation_daily`, the raw detector table, the harness, or ledgers.
- `render_top_gaps: false` in `config/gap_engine.yaml` disables the pilot top section and removes it from the brief on the next render.
- Governance scorecard is currently red because trust-root config files are uncommitted/dirty, especially `config/governance_contract.yaml`. That is expected before committing this work.
- Absorption labels are intentionally marked provisional because v1 uses severity-mapped expected moves, not analog-calibrated episode history.
- ETF expression metadata is a v1 seed. Expense ratios should be reviewed before the first formal holdout window.

## Next Suggested Phase

Start Phase A hardening:

- review `config/gap_engine.yaml` v1 weights/floors as pre-registration;
- review `config/etf_expression_overrides.yaml` expense-ratio coverage;
- add a brief-renderer regression fixture comparing old brief output with gap rendering disabled;
- decide whether to address the unrelated stale GDELT and open-thesis validator failures before the next full nightly run.
