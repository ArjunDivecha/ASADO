<!--
=============================================================================
FILE: docs/PRD_Update_Pipeline_Correctness_Efficiency_2026_07_01.md
=============================================================================
PURPOSE:
  Complete audit of the DAILY and MONTHLY update procedures plus a PRD for
  the changes needed for correctness and efficiency. Successor to
  docs/UPDATE_PIPELINE_AUDIT_2026_06_24.md (whose GDELT fixes landed; its
  P0 resume-fingerprint item did NOT land and is re-raised here with new
  evidence).

INPUT FILES (read-only; nothing was modified):
  - scripts/daily_update.py, scripts/run_asado_daily.sh
  - scripts/monthly_update.py
  - scripts/loop/loop_daily_job.py, scripts/loop/{run_manifest,heartbeat,
    build_governance_scorecard,procutil}.py
  - scripts/qa/check_source_alignment.py
  - config/governance_contract.yaml
  - ~/Library/LaunchAgents/com.arjundivecha.asado-{daily,loop-daily,
    loop-heartbeat,predmkt-daily}.plist  (schedules read live)
  - Data/logs/ (asado_daily_runner.log, daily_update_*.log,
    monthly_update_2026_07_01_130226.log, loop_daily_launchd.log)
  - Data/work/loop/bbg_quota_log.csv
  - Data/loop/governance/run_manifest.json

OUTPUT FILES:
  - This document.

VERSION: 1.0    LAST UPDATED: 2026-07-01    AUTHOR: Claude (Fable 5) session
=============================================================================
-->

# Update Pipeline Audit + PRD — 2026-07-01

## Part I — What actually runs (verified against plists and logs)

### Schedule (from the live LaunchAgents, not the docs)

| Time | Job | Command |
|---|---|---|
| 04:30* | predmkt | `predmkt_daily_job.py` (writes main DB read-write) |
| 05:30* weekdays | daily pipeline | `run_asado_daily.sh` → BBG preflight (retry until 11:00) → `daily_update.py --resume` → chained loop as final stage |
| 06:45 | loop standalone | `loop_daily_job.py` (flock-guarded vs the chained run) |
| 12:45 | heartbeat watchdog | `heartbeat.py --watchdog` |
| every 30 min | neo4j guard | keeps Neo4j alive |

\*Docs say 06:30/07:30 — the observed log timestamps are 04:30/05:30. Either
the plists were changed without updating README/AGENTS.md or the docs were
always aspirational. Either way, **the documentation and the machine
disagree**, and the loop README still says "33 steps" when the job now has
**41** (discovery docket, forward-track, price state, gap episodes, brief
renderer, cockpit data + live page were all added since Jun 22).

### Daily flow (11 stages, fail-fast, ~25 min observed on 2026-07-01)

T2 BBG pull (conda, 269s) → T2 master (135s) → normalize (81s) → benchmarks
(6s) → T2 returns (37s) → GDELT refresh (105s) → GDELT normalize (3s) →
GDELT optimizer (138s) → daily DB rebuild (69s) → Neo4j full rebuild (14s) →
**chained loop (664s)**. First failure aborts the rest; `--resume` skips
stages recorded "OK" today by name.

### Monthly flow (continue-on-failure, 2671s = 44.5 min observed 2026-07-01)

Stage 1 collectors (external, extended, WB commodity, IMF, bilateral, PIT
edges, macrostructure, FF, Bloomberg×2 conda, T2 master, vintage snapshot) →
DuckDB pass 1 + normalization → workbook exports → T2/GDELT/Econ normalize +
optimizers → optimizer ingest → **DuckDB pass 2** + normalization + daily
panels + predmkt + event log + registry → Neo4j + embeddings + schema cache +
factor reference.

### Nightly loop (41 steps, per-step 1800s bound, retries ×2, flock)

Non-optional failure → keep going, exit 1 at the end. `optional: true` steps
(most BBG collectors per `config/governance_contract.yaml`) → warning, exit 0.
Governance was GREEN 7/7 on 2026-07-01.

---

## Part II — Findings

### A. Correctness defects (ranked)

**C1 — The chained loop gets a 1200s budget but needs more. (Observed kill.)**
`daily_update.py:97` defaults non-conda stages to 1200s; the loop is chained
as a normal stage. The loop internally allows **1800s per step** and has 41
steps; on 2026-06-26 the chained loop was killed at 1200s (exit 124,
`daily_update_2026_06_26_091630.log:413-417`). It took 664s on a good day —
one slow GDELT throttle or BBG retry blows the budget. The flock means the
kill isn't data-corrupting, but the daily run then reports FAIL and the
06:45 standalone may silently skip if the lock lingers.

**C2 — `--resume` trusts yesterday's stage names, not the code.**
`daily_update.py:184-193` skips any stage recorded "OK" today; the progress
file stores only the name. After an intra-day code fix, rerunning with
`--resume` silently skips the fixed stage. This was the Jun-24 audit's #1
item and is still open. (Same file, same lines.)

**C3 — The monthly orchestrator cannot fail.**
`monthly_update.py:240-246` runs steps with bare `subprocess.run` and **no
timeout**; `main()` ends with `print_summary` and **never sets a non-zero
exit code** regardless of failed steps (`:1078-1082`). A hung collector
blocks forever; a half-failed month looks like success to any scheduler,
wrapper, or human checking `$?`. The `--skip-bloomberg` stale-master abort
also `return`s with exit 0 (`:506-512`).

**C4 — Triple Bloomberg pull on the same day. (Observed, quota waste + drift window.)**
`bbg_quota_log.csv` for 2026-07-01 shows the full market-implied/ratings/eco
batch at **05:47, 09:33, and 13:53** (187+99+190 hits × 3). The chained loop,
the standalone loop, and a manual/full run each re-collected because nothing
gates a collector on "already fresh today." Cost: ~3× nightly BBG quota, and
the loop tables can change mid-day under an open cockpit.

**C5 — Optional-step semantics can hide stale data.**
Most `collect_*_bbg` steps are `optional: true` in the governance contract;
on failure the loader silently rebuilds from the **prior** parquet (by
design, e.g. `collect_foreign_flows_bbg.py:217`). Freshness is only visible
if the cross-source/liveness checks catch it. A per-table max-date freshness
strip in the manifest (and on the cockpit) would make staleness loud instead
of silent.

**C6 — Two writers own the same brief file.**
`build_dislocations.py:1025` writes the brief; `render_dislocation_brief.py`
rewrites it later in the same job (`loop_daily_job.py:261-268`). If the
renderer fails mid-write the brief is left in its pre-gap state with no
marker. Single-writer (or renderer writes to temp + atomic replace, which it
partially does) should be asserted by a post-step check.

**C7 — `setup_duckdb.py` deletes the main DB with no coordination.**
`DB_PATH.unlink()` (`setup_duckdb.py:1129-1131`) while predmkt (04:30,
read-write) and every loop step (read-only ATTACH) use the same file. Today
this is sequenced by luck of the clock. A run-today monthly at 13:02 (as
happened) overlaps the 13:53 loop run's ATTACH window. DuckDB will error one
side; the retry machinery usually absorbs it — but it is a race, not a
design.

**C8 — `check_source_alignment.py` is built but not wired.**
It checks country naming, date grain, sleeve resolution, and cross-source
sentinels, exits non-zero on FAIL — and nothing calls it (repo grep: only
self-references). It also reads legacy paths (`Data/T2 Master.xlsx`,
`check_source_alignment.py:81-82`) rather than the canonical
`Data/work/t2/` files.

**C9 — Lock-skip exits 0 with no alert.**
If the 06:45 standalone loop finds the chained run's flock held, it exits 0
(`loop_daily_job.py:367-369`). Correct behavior, but the only trace is a log
line; if the chained run then dies, nobody re-runs. The heartbeat watchdog
(12:45) partially covers this — it should explicitly check "manifest
present for today" rather than process liveness only.

**C10 — Docs drift.** README (33 steps, 06:45), monthly header (2026-04-29,
references retired GDELT-Deep stages), schedule times — all out of date.
For a system whose brand is epistemic honesty, the runbook should be
generated, not remembered (see F6).

### B. Efficiency findings (ranked by minutes saved × risk removed)

**E1 — Excel/CSV plumbing still in the hot daily path.** The Jun-24 audit's
biggest item, still open: `build_t2_master_daily.py` (Excel in/out, 135s),
benchmarks → `Portfolio_Data.xlsx`, optimizer → `T2_Optimizer.xlsx`,
`build_daily_panels.py` parsing `T2 Master Daily.xlsx` for levels (~25s).
Parquet-first (Excel as optional human export) is worth ~2–3 min/day and
removes the fragile workbook parse.

**E2 — GDELT optimizer at 138s** (`gdelt_optimizer_daily.py`) — the per-
factor per-date loop flagged in June; vectorizing the rank/taper math is a
~120s/day saving.

**E3 — 7 separate conda sessions per loop run.** Each `collect_*_bbg` pays
conda startup + BLPAPI session setup (`loop_daily_job.py:198-241`). A single
batched runner (one session, sequential collectors, per-source manifest
statuses preserved) removes ~1–2 min and most BBG reconnect flakiness.

**E4 — Same-day duplicate loop work** (see C4) — a freshness gate is both a
correctness and an efficiency fix; it converts the 09:33/13:53 runs into
no-op skips within seconds.

**E5 — Full rebuilds where increments would do:** daily DB `--rebuild`
(69s), Neo4j full wipe+rebuild daily (14s, but leaves an empty-graph window
on failure — C-risk too), monthly runs `setup_duckdb.py` twice by design
(acceptable; document why pass 2 exists).

---

## Part III — PRD: the changes

### Goals
1. A failed or half-fresh pipeline can never look like a healthy one (to a
   scheduler, the governance scorecard, or the cockpit).
2. No same-day duplicate collection; no stage killed by its parent's clock.
3. Daily wall time trimmed ~4–6 min by removing Excel plumbing and the
   GDELT loop; nightly BBG quota back to ~1× per day.
4. Docs regenerate from code.

### Non-goals
- No re-architecture of the collector/loader split (it works).
- No change to the safety-net double-schedule concept — only its dedup.
- No incremental-DB project this round (keep `--rebuild`; revisit after E1).

### Work items

**W1 — Fix the chained-loop budget. (C1, XS)**
In `daily_update.py`, give the loop stage an explicit timeout ≥ 5400s (it is
already the final stage; a generous bound costs nothing) or run it with
`timeout=None` and rely on the loop's own per-step bounds.

**W2 — Resume fingerprints. (C2, S)**
Progress entries become `{status, script_mtime, script_sha1[:12], argv}`;
`--resume` skips only on full match. One helper in `daily_update.py`,
mirrors the Jun-24 recommendation verbatim.

**W3 — Monthly gets bounded steps and a real exit code. (C3, S)**
`run_step` → `procutil.run_bounded` with a per-step timeout column (collector
defaults 3600s, Bloomberg 5400s); `main()` returns
`1 if any(failed and not optional)`; the `--skip-bloomberg` stale-master
abort exits 2. Update the wrapper/docs accordingly.

**W4 — Same-day freshness gate for loop collectors. (C4/E4, S)**
Each `collect_*` step consults its own parquet max-date/mtime (they already
compute it) via a shared `--if-stale` convention or an orchestrator-level
gate: skip with status FRESH if the artifact is already dated today. The
11:30/standalone runs then cost seconds. Manual `--force` preserved.

**W5 — Freshness strip in the manifest + scorecard. (C5, S)**
`run_manifest.py` records, per declared output, the artifact max-date (not
just existence/size). `build_governance_scorecard.py` liveness dimension
ambers when any non-optional surface's max-date < today−1. This is also the
cockpit's "audit drawer" data source (the front-end PRD consumes it).

**W6 — Single-writer brief + post-write assert. (C6, XS)**
`build_dislocations.py` writes the body only; the renderer owns final
assembly; the loop job asserts the gap markers exist after the render step.

**W7 — DB-rebuild coordination sentinel. (C7, S)**
`setup_duckdb.py` takes the loop flock (or its own `Data/.duckdb_rebuild.lock`)
before unlinking; predmkt and `loopdb` retry-connect already handle brief
locks. Blocks the monthly-vs-loop race without new machinery.

**W8 — Wire `check_source_alignment.py`. (C8, XS)**
Point it at the canonical `Data/work/t2/` paths, then add it as an optional
post-DB step in both orchestrators (warning-level for two weeks, then
FAIL-gating once quiet).

**W9 — Parquet-first T2 daily. (E1, M)**
As specified in the Jun-24 audit: master/benchmarks/optimizer emit parquet,
Excel becomes an export flag, `build_daily_panels.py` reads only parquet.
Measured targets: master 135s→<40s, levels parse 25s→<3s.

**W10 — Vectorize the GDELT optimizer. (E2, S)**
Pivot once, rank row-wise, taper row-wise, matrix-multiply. Target 138s→<15s
with unchanged outputs (assert equality on one historical day before
switching).

**W11 — Batched BBG session runner. (E3, M)**
`scripts/loop/run_bbg_batch.py` opens one session and runs the 7 collectors
sequentially; per-collector try/except keeps per-source manifest rows.
Orchestrator uses it; individual scripts remain runnable standalone.

**W12 — Generated runbook. (C10, XS)**
`loop_daily_job.py --list-steps --json` + a docs builder that regenerates the
README schedule/step table (same pattern as `build_factor_reference.py`).

### Sequencing

| Phase | Items | Rationale |
|---|---|---|
| 1 (this week) | W1, W2, W3, W6, W8 | pure correctness, each ≤ a morning |
| 2 | W4, W5, W7 | freshness + coordination (needs a couple of clean nights to validate) |
| 3 | W9, W10, W11 | speed; W9 first since W10/W11 measurements shift after it |
| 4 | W12 | after the step list stabilizes |

### Acceptance
- A deliberately-failed collector produces: non-zero orchestrator exit,
  amber/red scorecard with a stale max-date, and a visible cockpit freshness
  flag — all three, same night.
- Two full loop invocations in one day: second completes in <60s with all
  collector steps FRESH-skipped; BBG quota log shows one batch.
- Chained loop never killed by the parent (30 clean nights).
- Daily wall time ≤ 20 min with Bloomberg up (from ~25).
- `--resume` after touching a stage script re-runs that stage.

---

## Part IV — What was checked and found healthy

- Fail-fast ordering in the daily is correct and well-commented (loop
  chained last so detectors see fresh tables).
- `procutil.run_bounded` process-group kills work; no orphaned bbcomm
  observed in recent logs.
- Flock semantics prevented every observed double-run collision; the June-20
  hardening (atomic brief writes, git-silent-green fix, predmkt by-name
  restore) is holding.
- Governance scorecard verified GREEN 7/7 on 2026-07-01 with an honest
  basis; heartbeat and manifest present and current.
- The 2026-07-01 monthly full run: 100% steps OK in 44.5 min.
