# Full monthly worker activated — October 14, 2026

The approved recurring collection-through-NN-publication path is deployed and active. There is no remaining activation blocker. The readiness-only service has been replaced under the existing `com.arjundivecha.asado-monthly` label.

## Verified production state

- ASADO production `main`: `492b01f1d0ff580a526138ed2fec991cd873e017`.
- NN production `master`: `98895c3` adds serialization and existing-model-only flags; `7862de5a951c2ce52aecbf1021001775854d74f5` ignores the runtime lock.
- Installed and loaded plist invokes canonical ASADO `venv/bin/python scripts/monthly_service.py`, every 3600 seconds and at load/login. Actual first run completed with exit 0 and printed `ACCEPTED_NOOP` between its readiness checks. The label remains loaded and idle awaiting its next tick.
- October remains `ACCEPTED_WITH_WARNINGS`, inputs_ready=true, zero problems, 44 known coverage warnings, full_coverage=false. No October or November attempt was created. XO's read-only monthly classifier returns WARN independently of daily status. Notification deduplication state is unchanged.
- Final fingerprints confirm unchanged warehouse SHA, October NN workbooks/contracts/holdings, saved model files, accepted receipt and local Bloomberg ledgers. Existing unrelated dirty files are preserved. Operator logs received verified append-only handoffs, with original bytes backed up.

The next eligible trade month is **November 2026**, using completed **October observations**. The first hourly tick after **November 1, 00:00 Pacific**, or a later login/wake, can start the one gated attempt. A read-only deployed November preflight verified all 43 source pins, runtimes, saved model allowlist, prior accepted state and current local quota without creating a claim, invoking a provider or running NN. The November quota preview projects 109 nonrecurring names within the current 150 allowance; it is a preview, not a reservation or guarantee of future source availability.

## What will execute

The service checks readiness, dispatches the worker and refreshes readiness. The worker holds monthly/pipeline/loop/repair/NN locks; verifies backups; collects the bounded T2/P2P/GDELT/Bloomberg NN-core scope; stages builders and warehouse changes; preserves original observations; validates source and per-input gates; runs two independent existing-model NN sandboxes; compares all 34 scores and eight holdings; packages the native workbook; journal-publishes verified canonical files; then atomically records acceptance.

Bloomberg uses the original gated shared runtime, 521-name union, 1363 historical security-field/currency hits plus at most 10 setup/ping hits. All original hard stops and per-request limits remain. There is no VM startup/login/access change, quota clearing, fallback collection, automatic training or trade placement. Daily panels, loop data, graph/optimizer runs and slow-source collectors are outside this bounded NN-core profile.

One durable claim prevents hourly recollection. Failure or interruption stops and alerts, with rollback of known replaced bytes; later-writer conflicts require reconciliation. Accepted months are producer no-ops. Starts from 04:00–08:30 Pacific defer; work has a two-hour maximum and must finish before 06:00 or month rollover. The worker does not promise observations are published at midnight. A failed first attempt requires explicit reconciliation and will not automatically retry.

Existing model semantics are unchanged. Eight sparse T2 dimensions remain zero-imputed when absent; 26 lagging slow-source inputs and two thin CPI variants remain visible warnings. Legacy Fill=P and cached annual denominator lineage are exposed. Only validated fold2026-02 model hashes are allowlisted: February2027 will stop before collection until a separately validated model is authorized.

All task-local paths below are relative to `/Users/arjundivecha/Documents/Codex/2026-10-13/task/`.

## Validation and evidence

- `monthly_worker_evidence/unit_tests.txt`: **71 passed**, including concurrency, scope/quota refusal, missing prerequisites, stale/missing inputs, month rollover, stage/score failure, interrupted publication, rollback, later-writer conflicts, duplicate acceptance and acceptance-write failure.
- `monthly_worker_evidence/replay/OFFLINE_REPLAY_PASSED.json`: real offline source builders and warehouse validation, two saved-model NN sandboxes, all36 tables' original observations preserved, October34 scores/eight holdings match the actual accepted publication. Journaled publication occurred only inside task-local fixture roots. Persisted transport fixtures were used; no provider call.
- `monthly_worker_deployment/ACTIVATION_VERIFIED.json`, `launchctl_after.txt`, `activation_launchd.out.log`, `activation_launchd.err.log`: actual loaded full-worker path, interval3600, first exit0, October ACCEPTED_NOOP and empty new error log.
- `monthly_worker_deployment/november_preflight.json`: deployed read-only prerequisite/source/model/quota checks and future local quota projection.
- `monthly_worker_deployment/canonical_unchanged.json`: final canonical/dirty-file preservation, with separately verified operator-log appends.
- `monthly_worker_deployment/XO_monthly_after.json`: honest WARN classification.
- `monthly_worker_deployment/source_backup_manifest.json`, `backup/`, `operator_context_appends.json`: pre-deployment source/plist/status backups and exact original operator-log bytes. Original October recovery backups remain retained.

## Operator references and rollback

Canonical runbook: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/docs/MONTHLY_READINESS.md`. Configuration: canonical ASADO `config/monthly_worker.json` and `config/monthly_readiness.json`. Runtime attempts, receipts, backups and publication journals: canonical ASADO `Data/monthly/`.

To disable only this monthly service: `launchctl bootout gui/501/com.arjundivecha.asado-monthly`. Preserve all monthly/recovery evidence. Restore consistent backed-up source/plist versions only if no later changes conflict. Do not restore an old warehouse or NN output just to disable scheduling. Never delete a failed attempt marker to induce recollection; reconcile its retained receipts and journal first.

No production collection, NN execution, model training or trade was performed to test deployment. No pushes, PRs or third-party messages were sent.
