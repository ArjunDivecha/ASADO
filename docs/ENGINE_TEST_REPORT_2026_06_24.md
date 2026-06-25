# ASADO Engine Test Report - 2026-06-24

## Scope

Ran the underlying daily engines behind the Price-Discovery Gap Engine and re-tested the fresh warehouse/loop outputs for data as-of 2026-06-23.

## Engine Run

- Ran `venv/bin/python scripts/daily_update.py --resume`.
- First full run completed all upstream T2/GDELT/DB/Neo4j stages but loop failed in `build_valuation_block.py`.
- Fixed valuation logging so empty/non-datetime panels log safely instead of crashing.
- Reran `daily_update.py --resume`; loop completed with `ALL STEPS OK`.

## Upstream Freshness Recovery

- News repo refresh:
  - Ran `/Users/arjundivecha/Dropbox/AAA Backup/A Working/News/report/main.py --no-llm --non-interactive`.
  - News prices updated through 2026-06-24.
  - Broker holdings fell back to stale snapshot but ASADO bridge now has a 2026-06-24 holdings row flagged stale.
  - Rebuilt ASADO `collect_news_bridge`, `build_price_state`, `build_gap_episodes`, and brief rendering.

- GDELT refresh:
  - Found stale GDELT `masterfilelist.txt` ending 2026-05-08.
  - Refreshed the GDELT support master list; it then reached 2026-06-24 14:00 UTC.
  - Backfilled `2026-05-08..2026-06-23` country-day parquets with full expected GKG file coverage.
  - Rebuilt GDELT signal panel: `954,614` rows, `4,059` dates, `249` countries.
  - Exported fresh ASADO `Data/gdelt/spreadsheet/GDELT_DAILY.xlsx`.
  - Patched ASADO GDELT normalizer to support exported workbooks without `daily_metronome` and with Excel serial dates.
  - Rebuilt ASADO GDELT normalized daily factors: `5,109,112` rows, `37` variables, through 2026-06-23.
  - Rebuilt GDELT optimizer: `36` factors, `4,059` daily dates.
  - Rebuilt ASADO daily panels.

## Current Output State

- `asado.gdelt_factors_daily`: max date `2026-06-23`, `5,109,112` rows.
- `asado.factor_returns_daily`: max date `2026-06-24`, `784,542` rows.
- `asado.t2_levels_daily`: max date `2026-06-24`, `9,104,758` rows.
- `etf_prices_daily`: max date `2026-06-24`, `209,332` rows.
- `portfolio_holdings_daily`: max date `2026-06-24`, `694` rows.
- `price_state_daily`: `34` rows for 2026-06-23.
- `gap_episodes`: `24` rows.
- `gap_episode_marks`: `27` rows at 2026-06-23.
- `gap_holdout_daily`: `169` rows at 2026-06-23.
- Latest brief: `Data/dislocations/brief_2026_06_23.md`.

## Tests

- `venv/bin/python -m pytest tests/loop/test_gap_engine.py tests/loop/test_run_manifest.py -q`
  - PASS: `22 passed`.

- `venv/bin/python scripts/loop/build_price_state.py --check`
  - PASS: `price_state_daily` and `price_state_surface` present at 2026-06-23.

- `venv/bin/python scripts/loop/build_gap_episodes.py --check`
  - PASS: gap tables present and populated.

- `venv/bin/python tests/loop/test_daily_pipeline.py --date 2026-06-23`
  - PASS after validator repair: `24 passed, 0 failed`.
  - The previous `open theses: 2` failure was a stale validator assumption. The ledger has 3 total seed theses, with 2 open and 1 deliberately killed at review as a measurement artifact.
  - I did not fabricate a new thesis to satisfy the old policy check.

## Notes

- The Price-Discovery Gap Engine itself is passing.
- The engine/data freshness failures from the first validator run are fixed.
- The daily validator is now clean; the ledger check validates seed thesis history instead of requiring all seed theses to remain open forever.

## Follow-Up Fix: Parquet-Only GDELT Daily Path

After the initial recovery, the daily GDELT process was made durable:

- Added `scripts/refresh_gdelt_daily.py`.
  - Refreshes the official GDELT masterfile list.
  - Builds missing upstream `country_day/*.parquet` files through the target date.
  - Rebuilds and verifies `/Users/arjundivecha/Dropbox/AAA Backup/A Working/GDELT/data/panels/country_signal_daily.parquet`.
- Changed `scripts/t2_normalize_daily.py` to emit `normalized_t2_master.parquet` alongside the legacy T2 CSV so GDELT can consume T2 `1DRet` without reading CSV.
- Changed `scripts/gdelt_normalize_daily.py` to read `country_signal_daily.parquet` plus `normalized_t2_master.parquet` and write `gdelt_factors_daily.parquet`.
- Changed `scripts/gdelt_optimizer_daily.py` to read `gdelt_factors_daily.parquet`, write `gdelt_optimizer_returns.parquet`, and compute the equal-weight benchmark from the merged `1DRet` rows.
- Changed `scripts/build_daily_panels.py` to load GDELT optimizer returns from parquet.
- Changed `scripts/daily_update.py` to run `refresh_gdelt_daily.py` before GDELT normalization.

There is now no Excel or CSV read/write in the daily GDELT update path.

Validation after the fix:

- `scripts/refresh_gdelt_daily.py --target-date 2026-06-23`: PASS.
- `scripts/gdelt_normalize_daily.py`: PASS, parquet output, `5,103,672` rows, `37` variables, `34` countries, max date `2026-06-23`.
- `scripts/gdelt_optimizer_daily.py`: PASS, parquet output, `146,124` rows, `36` factors.
- `scripts/build_daily_panels.py --rebuild --no-backup`: PASS.
- `pytest tests/test_gdelt_daily_parquet.py tests/loop/test_gap_engine.py tests/loop/test_run_manifest.py -q`: PASS, `26 passed`.
- `tests/loop/test_daily_pipeline.py --date 2026-06-23`: PASS, `24 passed, 0 failed`.
