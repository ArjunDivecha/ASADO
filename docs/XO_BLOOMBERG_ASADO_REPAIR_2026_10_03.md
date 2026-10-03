# XO Bloomberg / ASADO repair — 2026-10-03

## Outcome

Published a bounded monthly T2/GDELT repair. Canonical source-alignment QA now exits 0; the historical September 1 mismatch is gone. Daily data was already recovered at 00:40 PDT and was not rerun. Bloomberg keepalive remains intentionally disabled.

## Bloomberg

The archived clearance record `OpusBloomberg/outputs/quota_incidents/cleared-20260915T025819.408808Z.json` records Arjun's direction to clear the incident after disabling the metronomic BloombergGPT poller whose GOOGL poll triggered the September 14 quota event. The launchd plist remains `.disabled-20260914`; no service is loaded. Restarting this retired polling mechanism is inappropriate. Scheduled producer preflight and genuine data outputs are the useful health evidence.

The authorized monthly pull used existing guarded Bloomberg connectivity, no credentials or session takeover. Setup passed at 07:55:14 PDT. Security-rule mutations were blocked by the repair wrapper. 353 securities were planned; 64 new names were consumed. 25 historical batches covered 1,109 ticker-field hits; setup/probes bring the observed ledger increase to 1,112 hits. Final status: 920 / 3,800 monthly names, 3,052 / 450,000 daily hits, no options, no active hard stop.

## Root causes and changes

- Monthly T2 inputs had not refreshed since August. The daily pipeline refreshes a different set of surfaces.
- The September 2 collector guard imposed a daily 1,000-row minimum on monthly sheets, which legitimately have as few as 17 observations. The guard now preserves the daily threshold and requires monthly prior row counts and every prior observation date, with a floor for new sheets.
- Quota and budget exceptions now abort both USD and local-currency batches immediately. The collector no longer adds an outer retry around shared setup.
- GDELT's September 1 row represented partial August observations, not September data. Both producers shift observation month M to label M+1. The production monthly GDELT builder now offers and uses `--completed-months-only`; incomplete October observations are retained in staging but excluded from published monthly predictors.
- The external GDELT cache has empty historical files for November–December 2023. ASADO's existing files contain real observations. The rebuild preserves every ASADO historical file and adds only 54 external days, August 10–October 2. All new files are nonempty, correctly dated and contiguous. This rebuild reproduces all previously completed monthly_metronome values exactly (maximum difference 0).
- A shared inherited flock now protects the daily wrapper, direct daily/monthly entry points and repair publication. It does not change schedules or stop producers. The existing loop lock was held during warehouse staging/publication.
- QA now explains the monthly-source failure correctly and explicitly warns about preserved stale P2P.

## Published data and validation

- T2 workbook: 321 month labels, 2000-02-01 through 2026-10-01.
- GDELT workbook: 140 month labels, 2015-03-01 through 2026-10-01; full date overlap with T2.
- Warehouse: t2_master 1,091,978 rows; t2_raw 472,406; gdelt_panel 423,708. All have 34 countries and latest label 2026-10-01.
- Latest 1M forward return remains NULL; GDELT return aliases agree including NULL semantics (CSV serialization difference below 1e-16, tested at 1e-12 tolerance).
- Monthly tables and their normalized feature layer were updated in a cloned warehouse. Unrelated tables were preserved. Counts and per-column checksums for the five daily tables matched before/after.
- 121 files published under shared producer, loop and repair locks; no active producer found and canonical warehouse version rechecked immediately before publication. Every replaced file was backed up; staged sibling replacements had rollback handling.
- Canonical full source-alignment QA: exit 0, no FAIL entries. Genuine warnings remain, including stale P2P, differing sleeve labels/resolution and older unrelated sources.
- Regression suite: `venv/bin/python -m pytest tests/test_monthly_refresh_safety.py -q -p no:cacheprovider` — 10 passed. Shell syntax and changed-file whitespace checks passed.

## Remaining limitations / decisions

P2P is **not repaired or declared fresh**. Its producer indexes yfinance monthly closing-bar calculations by observation-month start, unlike the Bloomberg M+1 convention, and fetched partial October values. Publishing those values as completed predictors would be unsafe. The exact historical 319-row P2P sheet through 2026-08-01 was preserved, no later P2P rows were introduced, and new P2P outputs remain quarantined in staging. A separate semantic correction should drop unfinished observation months and shift completed scores to M+1, with a full historical effect review before changing model inputs. No strategy input was silently relabeled or removed.

This was a scoped monthly source/warehouse refresh, not the full monthly orchestrator. Optimizer returns, the loop database and downstream trading outputs were not rebuilt. No trading, paid LLM jobs, external communications or new schedules occurred. No monthly launchd producer was found; recurring monthly scheduling needs a separate decision. The external GDELT historical cache issue remains outside this repair; ASADO's retained historical sources are intact.

## Evidence and recovery

`Data/work/xo_monthly_repair_20261003/` contains `bloomberg.log`, `gdelt_union.log`, `gdelt_input_provenance.json`, `alignment_after.md`, `canonical_alignment.md`, `warehouse_validation.json`, `daily_preservation.json`, `publication_manifest.json`, `publication.log`, `VALIDATED`, and `PUBLISHED`.

`backups/` contains all replaced data. `code_backups/` preserves original source files, including the pre-existing local QA edit. `repair_scripts/` records the bounded staging/validation/publication helpers. No commits were created and unrelated edits were preserved.


## Follow-up: permanent P2P repair

The user subsequently authorized the P2P semantic repair. The temporary quarantine above is superseded by [P2P monthly v2 migration](P2P_TIMING_MIGRATION_2026_10_03.md), which documents the historical reconstruction, country-mapping correction, affected artifacts and verification. This report remains the record of the earlier repair stage.
