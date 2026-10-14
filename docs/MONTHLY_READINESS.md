# ASADO monthly readiness and NN acceptance

Installed job: `com.arjundivecha.asado-monthly`. launchd runs the readiness checker hourly and at login/load. The checker uses Pacific calendar months, so DST and missed wakeups do not determine the data month. It creates one durable ticket for the current trade month and coalesces missed checks. It reports intervening unaccepted months and never replays them.

Canonical program: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/scripts/monthly_readiness.py`.
Configuration: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/monthly_readiness.json`.
Plist source: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/launchd/com.arjundivecha.asado-monthly.plist`.
Installed plist: `/Users/arjundivecha/Library/LaunchAgents/com.arjundivecha.asado-monthly.plist`.

## Monthly contract

Trade month M uses completed observation month M-1. T2 and GDELT already carry M+1 availability labels, so their required label is M. The 29 selected Bloomberg inputs carry observation labels, so they require M-1. September observations therefore feed October NN. Realized 1MRet requires M-1 for all 34 NN countries. The 238-factor list and producer definitions are hash-pinned; changing them requires reviewing this contract and its bounded request scope.

The existing NN 90% trailing-12 source coverage gate remains. T2 contains sparse/annual/quarterly features; missing individual T2 cells warn, and source aggregate failure blocks readiness. Empty Bloomberg or GDELT selected inputs block readiness even if an aggregate could hide the gap. Every missing/thin input reports its exact required month, latest month, coverage and historically present missing countries. No interpolation or forward fill is performed. Slow sources warn. A month can be accepted with warnings: this is never full coverage.

October 2026 was independently validated and published October 13, 16:53:37 PDT. Its original acceptance receipt is adopted without repeating collectors or NN. All 29 Bloomberg inputs reach September, but the two CPI variants have 9 countries versus trailing mean 18.3. Eight T2 variants (GDP, Budget Def, Current Account, Bloom Country Risk) have no October label; 26 slow-source inputs also lag. These warnings remain visible despite the NN's aggregate gate passing.

## Artifacts and alerts

`/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/monthly/status.json` and `status.md` carry the current independent monthly status. The durable directory also contains `tickets/YYYY-MM.json`, exclusive-create `accepted/YYYY-MM.json`, append-only `events.jsonl` and `alerts.jsonl`, deduplicated `alert_state.json`, and launchd stdout/stderr logs. Preserve accepted receipts through warehouse rebuilds; this state lives outside DuckDB.

A native macOS notification is requested when the alert set changes. Delivery depends on macOS notification settings; durable alerts are authoritative. XO's `/Users/arjundivecha/Dropbox/AAA Backup/A Working/NightWatch/overseer/asado_monthly_health.py` reads this receipt independently of daily green. It returns WARN for accepted partial coverage, unavailable evidence or unaccepted work, and STALE when hourly evidence is over 2 hours old. Registry flags disable producer reruns and fixers. A full XO controller pass was not run for testing. Subsequent read-only inspection confirmed the new criterion in the live XO actions ledger at October 13, 17:35:04 PDT, reporting WARN with the input gaps; full-coverage OK has not occurred.

## Quota and exclusion

This checker never calls Bloomberg or imports a producer. Quota preflight reads local ledgers only and does not reserve quota. The pinned NN-core preview is T2 352 names/1109 security-field-currency pairs plus Bloomberg 186 names/254 security-field pairs, and an AAPL setup allowance of 3 hits: union 521 names, 1366 estimated hits. This is not the larger full monthly_update command. Actual collection must remain bounded to an independently reviewed manifest and retain every original hard-stop/gated-send check.

October ASADO usage includes both ASADO and recovery_collect.py: 64+45=109/150 at installation. The accounting files are never edited. November projected initial nonrecurring names are 109 using September/October recurrence; this is a preview, not a vendor-certified allowance. Hard-stop/global/day/caller limits all stop readiness for collection; no retries or automatic clearing. Missing/corrupt quota evidence fails closed.

The checker takes its own singleton plus the existing pipeline, loop and repair locks. It uses a guarded read-only, one-thread warehouse query, closes within seconds and never kills holders. Overlap defers the check and preserves the accepted ledger. No production full run, VM startup/login, credential/access change, trade or third-party message is part of this schedule.

## Operator workflow

Read status.md. For an unaccepted month, perform a separately bounded source refresh only for the named missing inputs, retain rollback backups and immutable request receipts, validate the NN in a separate sandbox and publish its verified result. The readiness schedule does not execute collection or NN production; it makes due work and its precise gates visible. Attaching the broad destructive monthly_update command is outside this readiness deployment.

After independent publication, adopt a receipt with `NN_month`, aware `accepted_at`, `NN_scores_match_sandbox: true` and its canonical `NN_manifest` (including snapshot path/hash and run_dir):

```sh
'/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/venv/bin/python' \
  '/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/scripts/monthly_readiness.py' \
  --adopt-receipt '/absolute/path/to/verified_publication_receipt.json'
```

The checker verifies current freshness, pinned definitions, contract/state agreement and snapshot hash before exclusive acceptance. Changed accepted contracts/evidence trigger reconciliation; an accepted month is never silently replaced or rerun. Exit 0 means the check produced a truthful report, not that the month completed. Consumers must read `state`, `accepted`, `inputs_ready`, `full_coverage`, problems and warnings.

Next eligibility after October: November 1, 2026, 00:00 PDT. The first hourly check after that time (or login/wake) creates November's ticket; it may wait on source publication or quota. It does not claim observations exist at midnight.

## Verification and rollback

Isolated tests cover exact month semantics, sparse/partial inputs, missing/changed artifacts, quota stops without ledger writes, duplicate acceptance/checks, competing producer locks, Pacific rollover/DST, missed months, successful acceptance and released DB connections. Production verification adopts only the already completed October receipt and evaluates the XO criterion directly; no producer is run.

To disable only this readiness job:

```sh
launchctl bootout gui/501/com.arjundivecha.asado-monthly
```

Remove its installed plist only after disabling it. Preserve `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/monthly/` for evidence. The deployment backup in `/Users/arjundivecha/Documents/Codex/2026-10-13/task/prevention_deployment/` contains exact original NightWatch controller/manifest and hashes. Restore those only if still unchanged by other work; otherwise remove just this registry entry, loader and dispatch branch. Do not restore the old warehouse or NN merely to roll back monitoring. Retain the recovery rollback backup separately.
