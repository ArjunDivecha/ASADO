---
schema_version: 1
spec_id: FAMILY-IC-MONITOR-001
status: draft
target_agent: either

scope:
  in:
    - scripts/loop/**
    - tests/**
    - docs/family_ic_monitor_notes.md
    - config/governance_contract.yaml   # AUTHOR AMENDMENT 2 (2026-07-14): register the loop step (exactly one entry)
  out:
    - cos_mockups/**
    - experiments/**
  forbid:
    - scripts/harness/**
    - config/family_registry.yaml
    - config/country_mapping.json
    - config/sweeps/**
    - ledgers/**
    - Data/processed/**
    - scripts/monthly_update.py
    - scripts/daily_update.py
    - scripts/collect_*.py
    - venv/**
    - "**/.env*"
    - "**/CLAUDE.md"
    - .claude/**

bet:
  if: "per-family honest-clock ICs are computed nightly into a durable loop-DB table with an R-A price-gate state machine, and the backfill independently reproduces the flip-autopsy reference history"
  then: "family-level decay or re-arming becomes visible within one nightly cycle instead of going unmeasured for months, and the Alpha Book's parked/re-armed states are machine-maintained"
  observable: "on the FROZEN 16-member June-2026 roster (ref16_frozen), the backfilled network_spillover monthly family IC (i) correlates >= 0.95 with the committed a2 monthly series, (ii) has per-year means within +/-0.012 IC of a6, (iii) has a 2012-2023 mean within +/-0.001 of a6's +0.0123, and (iv) has a post-2024 mean < 0 (the flip reproduces); the gate state machine passes an exhaustive synthetic truth table; as of the 2026-06 month-end the network_spillover gate (on the book_2026_07_14 roster) is 'parked' with 0 consecutive positive month-ends"

invariants:
  - id: INV1
    holds: "monitor ICs use the harness-v4 honest clock: daily signals aligned with effective lag >= 1 trading day (window opens strictly after the signal date), monthly signals with their v4 publication embargo; conventions imported from or proven equivalent to scripts/harness/evaluate_signal.py, never reimplemented divergently"
    check_intent: "fixture test runs the monitor's alignment on the harness-v4 known-answer fixtures: planted-echo signal must score |IC| < 0.005, planted-IC signal recovered within +/-20% (INV1)"
  - id: INV2
    holds: "fail-soft: a monitor failure (missing table, poisoned input, empty panel) never raises out of the nightly step wrapper - the loop's remaining steps run and the failure is logged loudly"
    check_intent: "unit test invokes the step entry point with a broken input environment and asserts no exception propagates while an error record/log line is produced (INV2)"
  - id: INV3
    holds: "durability + idempotence: one row per (family, date) in a table in the DURABLE loop DB (never the recreated main DB); re-running the same night upserts rather than duplicates; writes go through guarded_connect with no held connections"
    check_intent: "unit test runs the writer twice on the same synthetic night and asserts row count is unchanged and values updated (INV3); code inspection test asserts the module never references the main DB path for writes"
  - id: INV4
    holds: "known-answer backfill (AUTHOR AMENDMENT 1, 2026-07-14): the monitor's independently-implemented backfill reproduces the flip-autopsy reference on the FROZEN 16-member June-2026 roster (ref16_frozen): (i) monthly correlation >= 0.95 vs the committed a2 monthly series; (ii) per-year means within +/-0.012 IC of a6 (measured independent-reconstruction noise, not authored precision); (iii) pre-2024 (2012-2023) mean within +/-0.001 of a6's +0.0123; (iv) post-2024 mean negative - the flip must reproduce. All four binding."
    check_intent: "backfill gate computes all four clauses against the committed reference JSON/parquet, prints the full per-year table, and exits nonzero naming the failing clauses / offending years (INV4); the four-clause comparison LOGIC is additionally unit-tested on synthetic references"
  - id: INV5
    holds: "R-A gate state machine is correct: state 'parked' until two CONSECUTIVE positive family IC month-ends occur, then 're-armed'; any non-positive month-end resets the consecutive counter; state transitions are persisted with their evidence months"
    check_intent: "exhaustive unit truth-table over synthetic month-end sequences including edge cases - alternating signs, exactly-zero months (non-positive), gaps/missing months (reset), re-park after re-arm (INV5)"
  - id: INV6
    holds: "the monitor writes ONLY to the durable loop DB and Data/work/loop/ status artifacts; it never writes ledgers/, config/, Data/processed/, or the main DB"
    check_intent: "test statically scans the monitor module for write targets and dynamically verifies a full synthetic run leaves only the allowed surfaces changed (INV6)"

gates:
  - id: G1
    intent: "monitor unit + fixture suite passes: INV1 honest-clock equivalence on known-answer fixtures, INV2 fail-soft, INV3 idempotent durable writes, INV5 gate truth table, INV6 write-surface confinement"
    must_assert: "pytest exits 0 with named tests covering INV1, INV2, INV3, INV5, INV6"
    command: '"/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/venv/bin/python" -m pytest tests/test_family_ic_monitor.py -q -p no:cacheprovider'
    requires_permission: false
  - id: G2
    intent: "existing repo test suite stays green (no regression to loop, harness, or ledger behavior)"
    must_assert: "full pytest run exits 0"
    # ZERO deselects. After merging main (b358d50) the harness-v4 review audit is
    # branch-scoped to exp/harness-v4 (skips here), and this contract's step is
    # registered in config/governance_contract.yaml (AMENDMENT 2) so
    # test_run_manifest is green. This contract's OWN review audit is likewise
    # branch-scoped (skips off exp/family-ic-monitor) so it never leaks into a
    # later contract's G2. The full suite exits 0 with no exclusions.
    command: '"/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/venv/bin/python" -m pytest tests/ -q -p no:cacheprovider'
    requires_permission: false
  - id: G3
    intent: "the historical backfill runs against the live DBs and the four-clause INV4 known-answer comparison passes on the ref16_frozen roster; the book_2026_07_14 gate state initializes with network_spillover 'parked' at 0 consecutive positive month-ends as of 2026-06"
    must_assert: "backfill driver exits 0; all four INV4 clauses pass (corr>=0.95 vs a2, per-year +/-0.012 vs a6, pre-2024 mean +/-0.001 of a6, post-2024 mean<0); family_ic_nightly populated for every (family, roster); gate-state artifact written with network_spillover parked/0"
    # PERMISSIONED, operator-run outside the 06:00-08:30 PT quiet window, with the
    # worktree Data/ symlinked to production (reverdict_v4.py runtime-prerequisite
    # pattern). Build Mode verified well-formedness only, via:
    #   "<venv>/python" scripts/loop/build_family_ic_monitor.py --backfill --dry-run
    command: '"/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/venv/bin/python" scripts/loop/build_family_ic_monitor.py --backfill'
    requires_permission: true
  - id: G4
    intent: "one standalone nightly-style incremental run (the exact entry point the loop will call) completes against the live DBs, upserting the latest night idempotently (INV3) and refreshing the status artifact"
    must_assert: "step entry point exits 0 run twice back-to-back; second run changes no row counts; status JSON timestamp refreshed"
    # PERMISSIONED, operator-run (same runtime prerequisites as G3). The
    # --verify-idempotent mode runs the exact nightly step twice and asserts equal
    # row counts + a refreshed status timestamp. Build Mode verified well-formedness
    # only, via:
    #   "<venv>/python" scripts/loop/build_family_ic_monitor.py --verify-idempotent --dry-run
    command: '"/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/venv/bin/python" scripts/loop/build_family_ic_monitor.py --verify-idempotent'
    requires_permission: true

review:
  mode: required
  command: '"/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/venv/bin/python" -m pytest tests/test_review_audit_monitor.py -q -p no:cacheprovider'
  sees:
    - diff
    - invariants
    - scope

budget:
  max_turns: 30
  max_consecutive_failures: 3
  preflight_estimate: complete

kill:
  after_turns: 15
  gate: G1

graduate: "gates green AND review pass AND scope clean; then Arjun approves the loop_daily_job step wiring going live, first real nightly run is watched, and the brief-surface integration (reading the status JSON into the nightly brief) is authorized as a follow-up 10-line change"
scale: "graduated AND two weeks of clean nightly rows AND the Alpha Book v2 parked/re-armed states are read from this table instead of being hand-maintained"

ledger:
  turns: 3
  consecutive_failures: 0
  blockers: []
  lessons:
    - "Turn 3: merged main (b358d50), which branch-scoped the harness-v4 review audit to exp/harness-v4 (it now skips here). Combined with AMENDMENT 2's step registration, G2 is now the FULL suite with ZERO deselects (314 passed / 4 skipped, exit 0). This contract's own review audit stays branch-scoped to exp/family-ic-monitor."
    - "AUTHOR AMENDMENT 1 (2026-07-14): the a6 generating script was never committed (commit cdcd9a4 shipped only the JSON), so the original +/-0.005 per-year INV4 clause was unachievable from a faithful reconstruction (worst ~0.011). INV4 amended to four measured clauses: corr>=0.95 vs a2, per-year +/-0.012 vs a6, pre-2024 mean +/-0.001 of a6's +0.0123, post-2024 mean<0. CONTRACT LESSON: reference artifacts must be committed WITH their generating script."
    - "AUTHOR AMENDMENT 2 (2026-07-14): config/governance_contract.yaml added to scope.in so the required family_ic_monitor loop step is registered (exactly one entry); test_run_manifest stays green and G2 deselect #1 is dropped. A loop step unregistered in the governance contract degrades governance observability, so registration belongs to the same go-live as the wiring."
    - "Roster design: each family carries named rosters in the table's `roster` column. role='gate' (book_2026_07_14, the Alpha Book WATCH tier frozen at Book publication) is what the R-A gate runs on; role='inv4_reference' (ref16_frozen, a6's exact 16) is used ONLY for the INV4 known-answer. Rosters change only on a deliberate Book re-issue, never on live re-verdicts, so the monitored series is continuous."
    - "CONTRACT LESSON: contract review audits must be branch-scoped (skip unless on their own contract branch / merge-base diff empty) or they haunt every later contract's G2. This contract's review audit is branch-scoped from the start; the 2 remaining G2 deselects target harness-v4's not-yet-branch-scoped merged audit (author fixing on main)."
    - "Build gates green: G1 pytest tests/test_family_ic_monitor.py; G2 full suite with 2 documented deselects, exit 0; review branch-scoped audit. G3/G4 permissioned commands resolved and proven well-formed via --dry-run/--help, NOT executed."
---

## Context

Repo: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO` — macro research platform, 34 country markets. **The main checkout is production**: launchd runs the nightly loop (`scripts/loop/loop_daily_job.py`, fail-soft multi-step model, ~06:00–08:30 PT quiet window) from this tree. All build work happens in a git worktree (`git worktree add "../ASADO-exp-ic-monitor" -b exp/family-ic-monitor`); permissioned gates run outside the quiet window. DuckDB is one-writer/many-readers: writes go through `scripts/duckdb_lock_guard.py::guarded_connect()`, connections are never held (this caused the 2026-07-02/03 outage). Durable state lives in `Data/loop/asado_loop.duckdb`; the main `Data/asado.duckdb` is DESTROYED and recreated on every rebuild — nothing durable may be written there.

WHY this monitor exists: the network_spillover signal family (GRAPH*/LL_*/SIM_* variables in loop-DB tables `graph_features_daily`, `graph_features_pit_daily`, `leadlag_features_daily`, `similarity_features_daily`, plus `combiner_scores_daily` and the monthly `ECO_*` surfaces) decayed from ~April 2024 and NOBODY MEASURED IT for ~15 months, because family IC was only ever computed by on-demand harness runs (June 2026 was the first). The decay was documented by the G1 flip autopsy (`experiments/2026_07_flip_autopsy/results/RESULTS.md`) and the harness-v4 re-verdict (2026-07-14, `Data/loop/harness_runs/reverdict_v4_2026-07-14/`). The Alpha Book v2 (`docs/alpha_book_2026_07_14/ALPHA_BOOK_2026_07_14.md`) parked every WATCH mechanism behind an "R-A price gate": a family re-arms after two consecutive positive family-IC month-ends. This contract builds the thing that computes those ICs nightly and maintains those gate states.

Key conventions the build agent must respect: (a) the honest clock is defined by harness v4 (`scripts/harness/evaluate_signal.py`: `effective_daily_lag_days` = max(publication lag, 1); `align_daily`; known-answer fixtures in `tests/test_harness_v4.py` — REUSE these fixtures for INV1 rather than inventing new ones; import shared alignment helpers rather than duplicating logic — but note `scripts/harness/**` is scope.forbid: IMPORT from it, never edit it); (b) family membership resolves from `config/family_registry.yaml` prefixes (GRAPH/LL_/SIM_ → network_spillover; ECO_ → eco_surprise; combiner variables → ml_combiner) via `scripts/loop/family_registry.py::resolve_family` — read-only; (c) daily country returns come from `scripts/loop/loopdb.py::daily_country_returns` (backward-shift + placeholder-drop convention); (d) the reference series for INV4 is committed at `experiments/2026_07_flip_autopsy/results/a6_lag1_family_ic.json` (per-year lag-1 family IC) and `experiments/2026_07_flip_autopsy/results/a2_family_ic_monthly_recomputed.parquet` — wait: a2 is the lag-0 series; the a6 JSON is the lag-1 reference — compare against a6 per-year values and reconstruct the monthly comparison from the monitor's own backfill honestly (the correlation clause applies to overlapping monthly series where a monthly reference exists; the per-year clause applies against a6); (e) the loop's step model: steps are wrapped fail-soft — the new step must follow the same pattern as existing steps in `loop_daily_job.py` (inspect it; the wiring is one entry in its step list, and the entry must be added so a monitor crash cannot take down the loop); (f) monitored families for v1 of the monitor: `network_spillover` (daily, 5d horizon, equal-weight sign-aligned member ICs — WEAK/WATCH roster members per the ledger's final verdicts), `eco_surprise` (monthly, 1m horizon), `ml_combiner` (daily combiner score, 5d); the roster resolution must be deterministic and documented in the module docstring.

**Roster design (AUTHOR AMENDMENT 1, 2026-07-14).** Each family carries one or more named rosters, persisted in the durable table's `roster` column, so a family's monitored series is continuous and changes ONLY on a deliberate re-issue (not on every live re-verdict, which would make the series discontinuous). Two roles: (1) `book_2026_07_14` — the Alpha Book v2 WATCH-tier variables frozen at Book publication (network_spillover: `GRAPH_BANK_NBR_RET_GAP_21D`, `GRAPHP_TRADE_NBR_RET_GAP_21D`, `GRAPHP_KATZ_TRADE_GAP_21D`, `SIM_NBR_RET_GAP_21D`, `LL_LEADER_GAP_5D`; eco_surprise: `ECO_INFL_SURPRISE_Z`; ml_combiner: `COMBINER_RIDGE_DAILY_V1`) — this is the `role: gate` series the R-A state machine (INV5) runs on and the status artifact reports; (2) `ref16_frozen` — a6's exact 16 members (network_spillover only), `role: inv4_reference`, used ONLY for the INV4 known-answer comparison. Rosters are the committed data file `scripts/loop/family_ic_roster_v1.json`; ref16 is frozen to the pre-harness-v4 WEAK/WATCH set (the live post-v4 ledger lists only 12) so the backfill reproduces a6.

## Build Loop vs Product Loop

The build loop proves with machine gates: the monitor's clock equals the harness's honest clock on known-answer fixtures (INV1), it cannot take down the nightly loop (INV2), its writes are durable/idempotent/confined (INV3, INV6), its gate state machine is correct on an exhaustive truth table (INV5), and its backfill reproduces the independently-derived flip-autopsy history (INV4). Passing gates does NOT prove the product bet — that decay/re-arm events will be noticed and acted on within a day. That is evaluated after shipping: the first real re-arm or decay event must show up in the table (and later the brief) when it happens, and the Alpha Book's states must stop being hand-maintained. The build agent may not claim the product bet from gate success, and may not claim any signal is alive/dead from monitor output — the monitor measures; the harness verdicts.

## Verification Narrative

From the worktree root, a fresh agent verifies: (1) `pytest tests/test_family_ic_monitor.py -q` (exact name resolved in Build Mode) — green suite covering the five unit invariants, including the reuse of harness-v4 planted-IC and planted-echo fixtures for INV1 and the exhaustive INV5 truth table; (2) full `pytest tests/ -q` — no regressions; (3) [permissioned, outside 06:00–08:30 PT, with the worktree's Data/ pointed at production per the reverdict_v4 runtime-prerequisite pattern] run the backfill entry point — it populates the durable family-IC table from the earliest common signal date, prints the INV4 comparison (correlation and per-year deltas vs `a6_lag1_family_ic.json`), writes the gate-state artifact, and exits 0 only if INV4 holds and network_spillover reads 'parked/0-consecutive-positive' at 2026-06; (4) [permissioned] run the nightly step entry point twice back-to-back — second run is a no-op upsert (identical row counts, refreshed status timestamp `Data/work/loop/family_ic_status.json`); (5) inspect `loop_daily_job.py`'s step list to confirm the wiring follows the existing fail-soft pattern and sits late in the step order (after signal panels and combiner are built). Scope check: `git status --porcelain` shows changes only under `scope.in`.
