# ASADO monthly collection and NN publication

The installed `com.arjundivecha.asado-monthly` job runs `scripts/monthly_service.py` hourly and at load/login. The service checks readiness, dispatches one gated monthly worker, then refreshes readiness. This replaces the readiness-only deployment of October 13. User authorization: October 14, 2026, 00:28 PDT, Sentinel_4ce29c054d9c8191ac4d25006590362e, recurring collection through validated NN publication, with backups, duplicate protection, failure alerts and no automatic retry. Nothing places trades.

Canonical root: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO`.
NN root: `/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 NN`.
Configuration: `config/monthly_worker.json` and `config/monthly_readiness.json` under the canonical root. Plist source: `launchd/com.arjundivecha.asado-monthly.plist`; installed copy: `/Users/arjundivecha/Library/LaunchAgents/com.arjundivecha.asado-monthly.plist`.

## Trigger and month semantics

The first eligible trade month is November 2026. The first hourly tick after November 1, 00:00 Pacific, or a later login/wake, can claim that month. The schedule coalesces missed ticks and never automatically backfills intervening months. It starts no work between 04:00 and 08:30 Pacific; earlier work has a two-hour maximum and must finish before 06:00 or month rollover. An existing producer or NN lock defers before claiming.

Trade month M uses completed observation month M-1. T2/GDELT availability labels are M; the 29 selected Bloomberg inputs use observation label M-1. Realized 1MRet must reach M-1 for all 34 countries. November therefore needs October observations, and October's accepted September-observation result is an immediate producer no-op.

A tick does not prove that source observations exist at midnight. The first claimed attempt can stop on unavailable Bloomberg infrastructure, unpublished source data, quota refusal, validation failure or runtime deadline. It records the failure and alerts; later hourly ticks cannot repeat collection. Successful acceptance is also a durable no-op. Source pins, previous accepted holdings/output hashes, required input files, annual model allowlist and disk headroom must pass before providers.

## Bounded execution and coverage

The worker takes the monthly singleton and existing pipeline, loop, repair and NN publication locks. It verifies backups of every possible publication target before collection. It uses the shared gated OpusBloomberg `.venv/bin/python`, preserving the original hard-stop and request gates. The frozen scope is T2 352 names/1109 security-field-currency pairs plus Bloomberg 186 names/254 pairs: union 521 names including AAPL, 1363 historical hits plus at most 10 setup/ping hits. Dates are derived from completed observation months; historical blueprint dates are not request dates. There is no ticker discovery, fallback request or repeated history request. Local quota previews reserve nothing. October's ASADO accounting includes ASADO64 + recovery_collect.py45 =109/150; ledgers are never rewritten or cleared.

Bloomberg must already be available. The wrapper permits canonical read-only setup inspection and prevents VM startup, login, portproxy/firewall changes and failed-setup retries. T2/P2P/GDELT/Bloomberg outputs are staged below `Data/monthly/runs/<run>/`; GDELT requires every completed-month day at 96/96 GKG archives, with no HTTP retry. P2P uses the existing certified completed-month cache or a single monthly Yahoo download per mapped ETF. The controller terminates only its own child process group at the deadline.

Existing observed history is preserved. Current input labels are appended, and only previously NULL forward returns whose windows have completed may be realized. Every original warehouse table is checked; 31 unrelated tables receive no additions. No daily panels or loop database are publication targets. External/slow-source collectors, graph rebuilds and optimizers are outside this NN-core profile.

The existing NN source aggregate gate remains 90% of the trailing-12 observed-month mean. Empty selected Bloomberg/GDELT inputs block; sparse T2 variants warn. October has eight missing T2 dimensions (CS/TS GDP, Budget Def, Current Account and Bloom Country Risk), retained as zero by the existing NN preprocessing. The 26 lagging slow-source dimensions and two thin CPI variants remain explicit warnings. Existing T2 Fill=P cells and cached annual World Bank denominators are recorded as source lineage warnings; their availability labels do not certify fresh monthly underlying observations. Accepted-with-warnings never means full coverage. This worker does not alter lags, imputation, factors, network formulas or basket rules.

Two separate NN sandboxes score the same immutable snapshot using the same validated existing model cache and prior holdings. All 34 scores, eight weights and contract metadata must agree before native workbook packaging. `--existing-models-only` forbids training. Only the validated `fold_2026-02` model hashes are allowlisted; February 2027 will stop before collection until a separately validated model is authorized. Manual NN commands now honor the same production lock; sandbox commands use their own locks.

## Publication, receipts and alerts

Publication uses a closed destination list, verified original backup hashes, staged hashes, a PREPARED-before-rename journal, file fsync/atomic replacement and canonical hash checks. Complete exclusive acceptance is published only after all validation. A failure before acceptance rolls back known replaced bytes; a later writer's conflicting bytes are never overwritten. Interrupted attempts perform only rollback/reconciliation when locks become free, then stop without recollection. Completed acceptance is not undone for a later status/log failure.

Authoritative runtime evidence is under `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/monthly/`: `status.json`, `status.md`, `attempts/YYYY-MM.json`, `runs/<run>/`, `accepted/YYYY-MM.json`, `tickets/YYYY-MM.json`, append-only events/alerts, deduplication state and launchd stdout/stderr. Runs retain backup manifests, exact wire/reply receipts, stage/preservation gates, two sandbox logs, score parity, publication plan/journal and canonical NN receipt paths. Preserve this directory and the original recovery backup across warehouse rebuilds; there is no automatic deletion policy.

A changed failure/gap set requests a native macOS notification; durable alerts remain authoritative if macOS suppresses delivery. NightWatch's `overseer/asado_monthly_health.py` reads this monthly evidence independently of daily green, reports accepted gaps as WARN and old evidence as STALE, with fixer/rerun disabled. Exit 0 from a checker or no-op is not successful monthly publication. Read `state`, `accepted`, `inputs_ready`, `full_coverage`, problems and warnings.

## Operator reconciliation and disabling

For FAILED_STOPPED, preserve the claim, backups and source receipts. Inspect the stage log, wire journal and `publication.jsonl`; reconcile any partial publication or later-writer conflict before proposing repair. There is no force/retry/reset CLI. Do not remove the attempt marker or acceptance receipt to induce hourly recollection. A new collection or model/cache replacement requires a separately bounded, explicitly authorized reconciliation.

To disable this one owned monthly job, without disturbing daily jobs:

```sh
launchctl bootout gui/501/com.arjundivecha.asado-monthly
```

Keep its plist disabled until code/config versions are consistent. The exact pre-worker sources, installed plist, status, dirty-file hashes and canonical-data fingerprints are retained in `/Users/arjundivecha/Documents/Codex/2026-10-13/task/monthly_worker_deployment/`. Restore those source/plist versions only if no later work changed them, then bootstrap the restored readiness-only plist if desired. Do not restore an old warehouse or NN output merely to revert this schedule. For a failed actual publication, use the run's verified backup/journal with all producer/NN locks; refuse any later-writer conflict. Preserve accepted receipts and recovery evidence throughout.

## Validation

Isolated tests cover duplicate/concurrent starts, missing prerequisites, bounded wire scope, quota exhaustion, month rollover, stale/missing inputs, stage/score failure, publication crash/rollback, changed canonical bytes and acceptance failure. A full offline replay using persisted source fixtures ran native builders and two existing-model NN sandboxes, preserved all 36 warehouse tables' original observations, matched October's published 34 scores/eight holdings, and journal-published only into task-local fixture roots. Production activation is verified by loaded launchctl arguments, a read-only November preflight and an October ACCEPTED_NOOP with unchanged warehouse/NN/model/quota fingerprints. No production provider collection is used as a deployment test.

## 2026-10-14 model reconciliation (v3_clean → v4_pit_slow_ffill)

T2 NN commit `a36b9e8` replaced the production model: slow macro inputs are now carried forward at their true publication lags instead of entering as zeros, and the 2026-02 annual nets were retrained. Arjun authorized the reconciliation on 2026-10-14. The factor set is now named by the `factor_set` key in both `config/monthly_worker.json` and `config/monthly_readiness.json` (no longer hard-coded in `monthly_readiness.py`, `monthly_worker.py` and `monthly_stage.py`). `factor_set_sha256`, the pinned NN and ASADO sources and the `validated_model_hashes` 2026-02 entry were re-pinned to the new bytes. October's re-issued publication (`production/runs/2026-10_20261014_143358`) was re-scored twice in isolated existing-models-only sandboxes; both matched the published contract exactly, and its `reconciliation_acceptance.json` was adopted as the October receipt. The superseded receipt is kept in `Data/monthly/accepted_superseded/`. Backups, the two sandboxes and hashes: `Data/monthly/reconcile_v4_20261014_171341/`. After the change, 71 tests passed, readiness reported ACCEPTED_WITH_WARNINGS with no problems, and a read-only November preflight passed (no files written). February 2027 still needs a separately validated model.
