# Monthly P2P v2 migration — 2026-10-03

## Completed repair

The user authorized the permanent P2P semantic repair after the monthly-source recovery. Monthly P2P has now been recomputed from archived adjusted ETF monthly closes, validated, and published with its dependent P2P slices. This supersedes the temporary P2P quarantine described in `XO_BLOOMBERG_ASADO_REPAIR_2026_10_03.md`.

The migration did not add a schedule, invoke Bloomberg, place trades, change credentials/security settings, retrain strategies, or rewrite historical research records.

## Authoritative monthly timing and mapping contract

- Formula is unchanged: `(latest close / highest of the last 12 closes) × R² × sign(slope)`. R² and slope use the 13 monthly closes ending with the observation month, as the original implementation did.
- Only completed calendar observation months are eligible. On October 3, September is the latest completed observation month. October's partial bar is excluded from scores, even though it remains visible in the raw source snapshot for auditing.
- An observation month M is labeled **the first day of M+1**, its availability month. September observations produce the October 1 signal. This matches the Bloomberg-derived monthly factor convention.
- `1MRet` at label M+1 measures the ensuing month's return, not the signal's observation-month return. Normalization and optimizer joins use that availability label without shifting it again.
- Country identity comes from the explicit 34-country map in `config/p2p_country_etfs.json`, selecting columns by ticker name. The old producer inserted columns when an ETF first developed enough history, while the master renamed them positionally. **26 of 34 country assignments were wrong**, including SPY being assigned to NASDAQ. The map now correctly gives NASDAQ QQQ and U.S. SPY.
- Missing historical months are retained as missing calendar periods; they are never compressed into a shorter regression window or forward-filled. ETF pre-inception histories remain missing. Missing latest completed prices/scores fail the producer.

## Permanent producer and consumer changes

`p2p_monthly.py` owns deterministic completed-month calculation, explicit mapping, a versioned cache contract, and cache validation. `build_t2_master.py` downloads with explicit `auto_adjust=True`, snapshots the raw monthly Close data, and builds v2 scores. It no longer discards the first score row or renames ETF columns by position. The mtime shortcut first validates cache version and current availability month, so a month rollover cannot silently reuse stale data. Legacy `--skip-p2p` caches fail until regenerated from prices; no blind historical relabeling is accepted.

The workbook's `_P2P_contract` sheet records version, calculation time, source, adjustment basis, observation/availability convention, formula, raw snapshot path and SHA-256. The permanent monthly orchestrator calls this producer through its existing path; no new scheduler was installed.

The P2P optimizer now selects weights using signal availability **before** joining realized returns. A missing future return for a selected holding makes the portfolio return unavailable; it does not cause retrospective reselection. Missing P2P factor returns remain missing rather than being filled with other factors' mean return. Legacy behavior for other factors was left unchanged. The T60 trailing calculation uses these corrected P2P returns.

QA now checks the versioned cache against actual country values in the consumed master. Stale P2P or a failed timing/mapping contract is a FAIL. This replaces the temporary quarantine warning.

## Data provenance and reconstruction

Source snapshot: `Data/work/p2p_migration_20261003/t2/backups/p2p_raw_20261003_082621.parquet`.

SHA-256: `d2155c518d6813824a5b878da05022364f50437ae65b67a04eaaa0cb30f86d75`.

Source: Yahoo Finance through the installed yfinance client, adjusted monthly Close (`auto_adjust=True`), retrieved October 3 at approximately 08:26 PDT. These are a versioned downloaded snapshot, **not historical as-published vintages**; vendor revisions and adjustment history remain limitations. The migration repairs the demonstrable timing, mapping and target-selection defects; it does not certify every aspect of a historical investment backtest.

Scores were recomputed from prices and compared against the stored cache. Published monthly P2P contains 321 availability labels, February 2000 through October 2026, across 34 countries with natural pre-inception missing values. The latest realized optimizer-return label is September 1; October 1's forward return remains unknown.

## Rebuilt and published artifacts

Seventeen files were published under the shared producer and loop locks, after confirming no competing producer and rechecking the warehouse snapshot version. All replaced originals are retained in `Data/work/p2p_migration_20261003/backups/`; source backups are in `code_backups/`. The publication manifest records every source, destination and backup.

- Versioned P2P scores and raw adjusted-price cache.
- T2 Master workbooks and normalized CSVs in the T2, GDELT and Econ work directories.
- P2P sheets in the legacy wide normalized T2 workbook; all other sheets retained semantically unchanged.
- Updated T2 benchmark workbook.
- **P2P columns only** in T2 exposure, optimizer-return and T60 files. Other factor values were preserved exactly on their original indexes; newly added rows contain no fabricated observations for other factors.
- **P2P slices only** in the processed monthly factor-return and top-20 membership panels.
- Warehouse P2P raw/normalized inputs, derived normalized features, P2P return/membership slices, and P2P registry facts/semantics; regenerated variable dictionary.

Non-P2P master sheets, normalized CSV values, warehouse normalized features, other return/membership slices and all five daily tables passed exact semantic/checksum comparisons. The GDELT and Econ return optimizers were not recomputed because their return inputs did not change in this P2P migration.

## Historical interpretation and effects

Old monthly P2P performance is **superseded**, not a valid continuation of the new series. Timing, country identity, missing-target treatment and source-price vintage all contribute to the differences. The following compares old stored versus corrected benchmark-relative P2P returns over common observed months; it is a migration diagnostic, not a strategy promotion or full strategy revalidation. The existing optimizer's outputs are benchmark-relative; this migration makes no new transaction-cost or executable-performance claim.

| Diagnostic | P2P_CS | P2P_TS |
|---|---:|---:|
| Common months | 318 | 317 |
| Old/new monthly-return correlation | 0.119 | 0.201 |
| Mean absolute monthly-return difference | 1.96 percentage points | 1.90 percentage points |
| Old annualized mean/std ratio | 0.274 | 0.410 |
| Corrected annualized mean/std ratio | 0.267 | 0.122 |

Original performance files remain in backups. Registry notes explicitly identify the superseded semantics. No historical hypothesis/harness evidence was rewritten. Read-only searches found no P2P references in loop live signals, harness results, combiner weights, hypothesis ledger or loop-variable metadata.

## Verification

- `venv/bin/python -m pytest tests/test_p2p_timing.py tests/test_monthly_refresh_safety.py -q -p no:cacheprovider`: **25 passed**.
- Tests cover leap-year/month/year boundaries; excluding a still-open month; future-price perturbation invariance; missing calendar months; latest missing inputs; legacy/stale cache rejection; ticker-column reordering; normalization prefix invariance; unchanged formula; exact forward-return join; selection independent of future target availability; and missing-return preservation.
- Canonical full source-alignment QA exits **0** and reports PASS for P2P v2 completed-month timing and explicit country mapping. Genuine unrelated warnings remain.
- Before publication, canonical and staged unrelated data were compared, monthly lookahead boundaries checked, and the source raw/cache/master chain reproduced.

## Scope intentionally excluded

The external daily P2P producer, other T2-family repositories, historical research records, Neo4j's derived presentation state, existing briefs/reports and live trading systems were not rebuilt or certified by this **monthly** migration. Daily source tables were explicitly unchanged. No P2P strategy was re-promoted or retrained. Any historical external chart/cache based on old monthly P2P should be regenerated from v2 before use.

No monthly launchd producer was found. A reasonable proposed cadence is one run after the last completed month's data becomes available, with existing failure/QA gates; schedule selection remains a separate user decision. The permanent producer now enforces correct timing whenever invoked.

Evidence: `Data/work/p2p_migration_20261003/{stage.log,dependencies.log,effects.json,alignment_staged.md,canonical_alignment.md,unrelated_preservation.json,publication_manifest.json,publication.log,VALIDATED,PUBLISHED}`. Repair helpers and the source diff are retained alongside these artifacts.
