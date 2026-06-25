# ASADO Update Pipeline Audit - 2026-06-24

## Purpose

Audit the daily/monthly update machinery for stale-data traps, pointless Excel/CSV handoffs, and speed bottlenecks. The guiding question is: what does the data know that price has not yet figured out, and what in the update chain prevents that answer from being fresh, reproducible, and fast?

## Executive Summary

The daily GDELT failure was not a mystery in the model layer. It was a pipeline-contract problem: ASADO normalized from a stale GDELT panel and then later loaded a different stale raw GDELT panel into DuckDB. That class of bug is now fixed for GDELT. The daily GDELT path is parquet-only, refreshes upstream GDELT before normalization, and both `gdelt_factors_daily` and `gdelt_raw_daily` now load from the same refreshed upstream parquet.

The next biggest problem is T2, not GDELT. T2 daily still round-trips through multiple Excel workbooks and a giant CSV before landing in DuckDB. This is slower than necessary and makes freshness harder to reason about. The warehouse load has now been partially corrected to read `normalized_t2_master.parquet`, which reduced the `t2_factors_daily` load from about 14 seconds to 0.6 seconds. But upstream T2 still writes/reads `T2 Master Daily.xlsx`, `Portfolio_Data.xlsx`, `T2_Optimizer.xlsx`, and the legacy `Normalized_T2_MasterCSV.csv`.

## Fixes Already Applied

1. Added `scripts/refresh_gdelt_daily.py`.
   - Refreshes the GDELT `masterfilelist.txt`.
   - Builds missing `country_day` parquets.
   - Rebuilds/verifies `GDELT/data/panels/country_signal_daily.parquet`.

2. Converted daily GDELT normalization to parquet-only.
   - `scripts/gdelt_normalize_daily.py` reads upstream `country_signal_daily.parquet`.
   - It reads T2 `1DRet` from `Data/work/t2_daily/normalized_t2_master.parquet`.
   - It writes `Data/work/gdelt_daily/gdelt_factors_daily.parquet`.

3. Converted daily GDELT optimizer to parquet-only.
   - `scripts/gdelt_optimizer_daily.py` reads `gdelt_factors_daily.parquet`.
   - It writes `gdelt_optimizer_returns.parquet`.

4. Fixed raw GDELT warehouse staleness.
   - `scripts/build_daily_panels.py` now loads `gdelt_raw_daily` from `/Users/arjundivecha/Dropbox/AAA Backup/A Working/GDELT/data/panels/country_signal_daily.parquet`, matching the normalizer.
   - Before this fix, `gdelt_factors_daily` was current to 2026-06-23 while `gdelt_raw_daily` was stuck at 2026-06-11.

5. Switched T2 daily factor warehouse load to parquet.
   - `scripts/build_daily_panels.py` now reads `Data/work/t2_daily/normalized_t2_master.parquet` instead of `Normalized_T2_MasterCSV.csv`.
   - Measured improvement: `t2_factors_daily` load fell from about 14.2s to 0.6s.

6. Added raw GDELT validator checks.
   - `tests/loop/test_daily_pipeline.py` now checks `gdelt_raw_daily` freshness.
   - It also checks raw-vs-normalized GDELT max-date agreement.

## Current Validation

Focused tests:

```text
26 passed in 0.36s
```

Freshness after rebuild:

```text
gdelt_factors_daily max date: 2026-06-23
gdelt_raw_daily max date:     2026-06-23
factor_returns_daily max:     2026-06-24
t2_factors_daily max:         2026-06-24
t2_levels_daily max:          2026-06-24
```

Daily pipeline validator:

```text
24 passed, 0 failed
```

The stale governance check was repaired. The validator now treats the thesis ledger correctly: 3 total seed theses, 2 still open, 1 deliberately killed at review after its entry signal proved to be a measurement artifact.

## Timing Evidence

Final full daily run with Bloomberg/Neo4j/loop skipped:

```text
T2 build daily master          84.8s
T2 normalize daily             51.3s
T2 daily benchmarks             4.5s
T2 daily factor returns        20.1s
GDELT refresh upstream parquet  3.3s
GDELT normalize daily           2.4s
GDELT daily factor returns    123.8s
DB build daily panels          55.1s
```

After the additional warehouse fixes:

```text
t2_factors_daily load           0.6s
gdelt_factors_daily load        0.2s
gdelt_raw_daily load            1.0s
factor_returns_daily load       1.8s
t2_levels_daily workbook parse 24.6s
full DB build                  39.4s
```

Earlier same-day baseline before GDELT parquet optimization:

```text
GDELT normalize daily          31.6s
GDELT daily factor returns    262.9s
DB build daily panels          66.1s
```

## Findings

### P0 - Resume Checkpoints Can Skip Changed Stage Semantics

`scripts/daily_update.py` checkpoints only stage names as `"OK"`. If code changes but the same stage name remains, `--resume` can skip a stage whose implementation changed. That is dangerous in exactly this kind of repair, because the operator can believe the new logic ran when it did not.

Recommended fix:

- Store a per-stage fingerprint in `daily_update_progress_YYYY_MM_DD.json`.
- Include script path, argv, mtime, and ideally a short content hash.
- On `--resume`, skip only if the previous fingerprint matches the current fingerprint.

### P0 - T2 Daily Still Uses Excel/CSV As Pipeline Plumbing

Remaining daily T2 handoffs:

- `build_t2_master_daily.py` reads `T2 Bloomberg Master Daily.xlsx` and writes `T2 Master Daily.xlsx`.
- `t2_normalize_daily.py` reads `T2 Master Daily.xlsx`, writes legacy `Normalized_T2_MasterCSV.csv`, and now also writes parquet.
- `build_benchmark_rets_daily.py` reads `T2 Master Daily.xlsx` and writes `Portfolio_Data.xlsx`.
- `t2_optimizer_daily.py` reads `Normalized_T2_MasterCSV.csv` and `Portfolio_Data.xlsx`, then writes `T2_Optimizer.xlsx`.
- `build_daily_panels.py` still reads `T2 Master Daily.xlsx` for raw levels and `T2_Optimizer.xlsx` for T2 factor returns.

Recommended fix:

- Make the Bloomberg collector emit a sheet-equivalent parquet dataset: `Data/work/t2_daily/master_sheets/*.parquet` or one tidy `t2_master_daily_long.parquet`.
- Make `build_t2_master_daily.py` write parquet-first outputs and optionally write Excel only as a human export.
- Make benchmarks a parquet table, not `Portfolio_Data.xlsx`.
- Make `t2_optimizer_daily.py` read parquet and write `t2_optimizer_returns.parquet`.
- Make `build_daily_panels.py` read only parquet for daily T2.

Expected speed impact:

- Eliminate repeated workbook parse/write overhead.
- Remove the remaining slow raw-level load from about 25s to low single digits.
- Remove T2 optimizer and factor-return Excel overhead.

### P1 - GDELT Optimizer Is Still Algorithmically Slow

`scripts/gdelt_optimizer_daily.py` is parquet-only now, but it loops over each factor and then each date, merging one day at a time. That is why it still takes about 124s.

Recommended fix:

- Pivot once to `date x country` returns.
- For each factor, pivot factor values once, rank row-wise, compute taper weights row-wise, then multiply against returns in vectorized pandas/numpy.
- Or push the ranking/weighting into DuckDB/Polars.

Expected speed impact:

- Likely 124s -> 5-20s without changing output semantics.

### P1 - Full Daily Rebuilds Are Simple But Wasteful

`daily_update.py` always calls `build_daily_panels.py --rebuild --no-backup`. Rebuild is reliable, but once all source artifacts are parquet, the DB step can append/replace only the affected date partitions.

Recommended fix:

- Keep full rebuild as `--rebuild`.
- Add default incremental mode:
  - delete/insert rows for dates >= latest source update window;
  - maintain a source manifest with input max dates and hashes;
  - fail if a source regresses.

Expected speed impact:

- DB update could become seconds even with raw levels loaded.

### P1 - Repeated Bloomberg Conda Startup In Loop Job

`scripts/loop/loop_daily_job.py` runs several Bloomberg collectors as independent `conda run -p ... python ...` calls. This is robust but pays repeated interpreter/env startup and repeated Bloomberg session setup.

Recommended fix:

- Keep each collector independently runnable.
- Add an optional batched Bloomberg loop runner that opens one Bloomberg session and runs market-implied, foreign flows, sovereign daily, ETF flows, consensus, ratings, and eco surprise collectors sequentially.
- Preserve per-source manifests and per-source failure statuses.

Expected speed impact:

- Mostly startup/session savings, but also fewer fragile Bloomberg reconnects.

### P1 - Monthly Update Still Documents And Runs Legacy Workbook/CSV Surfaces

`scripts/monthly_update.py` still describes and orchestrates monthly T2/GDELT/Econ workbook/CSV optimizer surfaces. Some of this is historical compatibility, but it should be explicitly separated into:

- machine pipeline artifacts: parquet/DuckDB only;
- human exports: optional Excel/PDF/report outputs.

Recommended fix:

- Update the monthly PRD/docs to stop treating Excel/CSV as canonical data stores.
- Convert monthly GDELT/T2/Econ optimizer outputs to parquet-first.
- Keep Excel only where it is a deliberate report product.

### P2 - Reporting Excel Is Fine, Pipeline Excel Is Not

Some loop outputs are intentionally human-facing workbooks:

- calibration report `.xlsx`
- JST risk report `.xlsx`
- event-study summary `.xlsx`
- sweep summary `.xlsx`

These are not pipeline plumbing and are less concerning. The rule should be:

- no Excel/CSV between pipeline stages;
- Excel allowed only as final human-readable exports;
- CSV allowed only for third-party ingestion/cache if the upstream source is CSV, immediately converted to parquet and not used as the next ASADO stage input.

### Fixed - The Validator Now Checks Raw GDELT Freshness Too

The daily validator checked normalized GDELT freshness but missed stale `gdelt_raw_daily`. That allowed a partially stale GDELT state to appear healthy.

Implemented fix:

- Added `gdelt_raw_daily max date >= target date` to `tests/loop/test_daily_pipeline.py`.
- Added a cross-table assertion: `gdelt_raw_daily.max(date) == gdelt_factors_daily.max(date)`.

### P2 - Cost Model Should Be ETF-Aware, Not Cost-Dominated

The update pipeline should feed the new front-end section with expression-aware outputs:

- ETF liquidity tier;
- spread estimate;
- expense ratio and ownership drag;
- tracking error/proxy risk;
- stale NAV / holiday mismatch;
- short interest/crowding;
- borrow/availability if shorting;
- “cheap to express” flag for liquid country ETFs.

This should be a trade-expression layer, not a reason to discard signals prematurely.

## Recommended Implementation Order

1. Add resume fingerprints to `daily_update.py`.
2. Convert T2 daily optimizer to parquet-first:
   - `portfolio_data.parquet`
   - `t2_optimizer_returns.parquet`
   - warehouse reads parquet.
3. Convert `T2 Master Daily.xlsx` into parquet sheet artifacts.
4. Vectorize `gdelt_optimizer_daily.py`.
5. Add daily incremental DB mode.
6. Batch loop Bloomberg collectors behind one optional runner.
7. Clean up monthly update docs/stages so machine artifacts are parquet-first and Excel is report-only.

## What The New Front End Should Show

The front end should not show raw pipeline plumbing. It should show a "Price Discovery Gap" section backed by these fresh artifacts:

- Freshness strip: max date per source and red/yellow/green source contract.
- Top gaps: country, direction, severity, supporting data, price disagreement, evidence pack.
- Why price may be wrong: graph spillover, consensus revision, GDELT/news, market-implied stress, flows/crowding.
- Expression layer: ETF candidate, liquidity tier, spread/expense/tracking notes, and whether the trade is cheap enough to express.
- Audit drawer: exact source dates and run manifest, so stale data cannot hide.
