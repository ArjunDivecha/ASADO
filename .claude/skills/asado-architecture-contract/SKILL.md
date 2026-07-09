---
name: asado-architecture-contract
description: >
  The load-bearing architectural decisions of the ASADO macro-research platform, each stated
  with its WHY plus the known weak points — so a change never violates an invariant out of
  ignorance. Read this BEFORE modifying any pipeline code, DB schema, panel builder, harness
  gate, loop step, locking, Neo4j coupling, or a cross-repo interface, and whenever you need to
  know "why is it built this way / what will break if I change it". Covers: the collectors →
  tidy-long parquet → destructive DuckDB rebuild → panels → loop-DB data-flow contract and its
  isolation rules; the two-DB split and the guarded_connect locking boundary; the loop's
  fail-soft 47-step model; the skeptic harness gate sequence; Neo4j soft coupling; and the
  cross-repo contracts (Fable Daily Trading, cockpit, Bloomberg env split). Do NOT use this to
  run, operate, or debug a live failure (route to asado-operations and asado-debugging-playbook),
  to learn the experiment→ledger research method (asado-research-protocol), to check whether an
  idea is already dead (asado-graveyard), or for the change-classification/gating workflow
  (asado-change-control). This skill is the "why it is shaped this way"; those are the "how to act".
---

# ASADO Architecture Contract

You are a zero-context Claude (or human) engineer about to touch ASADO. ASADO is a data-collection
+ research platform over a 34-country macro universe; its product is *trustworthy falsification*
(most signals are meant to die honestly). This document is the set of decisions that are load-bearing:
each one is stated with WHY it exists and WHAT breaks if you undo it. Treat every "HARD RULE" as a
stop condition — if you are about to violate one, STOP and report to the user instead.

Authoritative live docs this skill points to rather than restating (read them for operational
detail): `AGENTS.md` and `CLAUDE.md` at the repo root; `openwiki/quickstart.md` for navigation;
`docs/factor_reference.md` + `docs/VARIABLE_DICTIONARY.md` for current auto-generated schema truth.
Do NOT trust `llmchat.md`, `DATA_DICTIONARY.md`, or `ASADO_DATABASE_MAP.md` (stale).

All paths below are under the repo root
`/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO` (quote paths with spaces).

---

## 1. The data-flow contract

```
12 collect_*.py  ──►  Data/processed/*.parquet   (tidy-long: date, country, value, variable, source)
                          │
                          ▼
              scripts/setup_duckdb.py            ──►  Data/asado.duckdb  (~3.4 GB)
              (FULL DESTRUCTIVE rebuild)               unified_panel = UNION ALL of source tables
                          │                             (commodities / ff_factors / JST / optimizer EXCLUDED)
                          ▼
              scripts/build_normalized_panel.py  ──►  normalized_panel (_CS + _TS) ─► feature_panel ─► feature_panel_t2
                          │
                          ▼
              scripts/build_daily_panels.py      ──►  daily T2 / GDELT / optimizer-return tables (additive, idempotent)
                          │
                          ▼
              scripts/loop/*  (Alpha-Hunting Loop)  ──►  Data/loop/asado_loop.duckdb  (durable loop state)
```

**Destructive rebuild is a deliberate decision, not a bug.** `setup_duckdb.py:1134-1138` does
`if DB_PATH.exists(): DB_PATH.unlink()` and then `guarded_connect(DB_PATH)` to recreate from
scratch; every table is DROP/CREATE-from-parquet. WHY: idempotence — the warehouse is a pure
function of the parquet in `Data/processed/`, so any rebuild reproduces byte-identical structure
and there is no "half-migrated" state to reason about. CONSEQUENCE, and this is a HARD RULE:
**never persist anything you want to keep in `Data/asado.duckdb` — the next rebuild deletes it.**
Durable state lives in `Data/loop/asado_loop.duckdb` (the main DB is attached there read-only as
schema `asado`). This is documented in `CLAUDE.md` under "setup_duckdb.py deletes and recreates".

**Panel semantics** (`scripts/build_normalized_panel.py`):
- `_CS` = cross-sectional normalization (same-date, across countries).
- `_TS` = time-series normalization (rolling window, per country), window by frequency:
  daily 252/63, monthly 60/24, quarterly 20/8, annual 10/5 (`build_normalized_panel.py:102-149`).
- `feature_panel` = the union of normalized variants; `feature_panel_t2` = `feature_panel`
  restricted to the 34 T2 names.
- **No point-in-time (PIT) / lag logic lives in the builders.** WHY: PIT discipline is the
  harness's job (see §5). If you add a lag in a builder you double-lag or hide leakage from the
  gate. Keep builders naive; keep PIT in the harness.

`build_daily_panels.py` is additive and idempotent (mtime no-op skip; backup+restore around the
write), so re-running it mid-day is safe — unlike `setup_duckdb.py`, which is total.

---

## 2. Isolation rules (the leakage guards) and the 43-vs-34 trap

**HARD RULE — isolated tables. Never UNION these into `unified_panel` / `feature_panel`:**
`ff_factors`, `jst_macrohistory`, `factor_returns`, `factor_top20_membership`,
`country_factor_attribution`. The `unified_panel` view (`setup_duckdb.py:920-953`) deliberately
lists only the country-keyed source tables and stops.

Two distinct WHYs, both leakage classes:
- **Tiling / broadcast leakage.** FF factors and World Bank commodities are region- or
  world-level series (one value per date). Broadcasting one value identically across all
  countries manufactures fake cross-sectional signal and inflates the variable count with
  degenerate `_CS` variants. The code says so in a NOTE at `setup_duckdb.py:946-950`
  ("World Bank commodities are GLOBAL series, NOT country variables … that tiled one price
  identically across 34 countries"). Commodities live in `commodity_panel` (one value per date);
  join to returns on `date` only.
- **Optimizer input/output cycle.** `factor_returns`, `factor_top20_membership`, and
  `country_factor_attribution` are *outputs* of the optimizer. Feeding them back in as candidate
  inputs closes a loop where the model predicts its own product. Excluding them is a structural
  guard, not a preference.

**The 43-vs-34 country trap** (`build_normalized_panel.py:9-10,24-33,74-84`):
- `config/country_mapping.json` carries **43** entries and is NOT the universe.
- The canonical **34**-country T2 universe is `scripts/loop/loopdb.py::T2_UNIVERSE`.
- `feature_panel` therefore carries **43** distinct countries; `feature_panel_t2` is the
  34-name restriction and is the **documented analysis default**.
- HARD RULE: analysis and harness consumers must read `feature_panel_t2`, not `feature_panel`.
  Using the 43-name view silently pulls in non-T2 names (Austria, Greece, …) that have no return
  series in the T2 book and corrupts cross-sectional stats. If you write a new consumer, filter
  by `T2_UNIVERSE` or query `feature_panel_t2`.

---

## 3. The two-DB split and the locking boundary

Two live DuckDB files, **each single-writer / many-reader**:
- `Data/asado.duckdb` (~3.4 GB) — recreated every rebuild (§1).
- `Data/loop/asado_loop.duckdb` (durable) — loop state, ledger folds, prediction surfaces.

**HARD RULE — never hold a connection to either DB, not even an idle read-only one.** DuckDB
allows one read-write process OR many read-only processes; a single stray holder (a Claude
Desktop analysis-sandbox kernel under `~/.claude-science/` was the real culprit) blocks every
nightly writer. This caused the 2026-07-02 and 2026-07-03 pipeline failures — documented at
`duckdb_lock_guard.py:22-24`.

**`guarded_connect()`** (defined at `scripts/duckdb_lock_guard.py:206`; mechanism documented
in the module docstring at `:26-64`; called at the connect site, e.g. `setup_duckdb.py:1138`)
is the mitigation. It is a *reactive retry wrapper*, not a global
lock: on a DuckDB lock IOException it parses the holder's exe path + PID from DuckDB's own error
message, and (only if BOTH the exe path and the live `ps` command line match a killable pattern —
default `.claude-science`, `DEFAULT_KILLABLE_PATTERNS` at :84) SIGTERMs it, escalating to
SIGKILL after 10s, up to `MAX_KILLS = 5` squatters. If the holder is NOT killable (e.g. a
legitimate overlapping ASADO job), it waits with backoff up to 300s (`DEFAULT_WAIT_BUDGET_S`)
then raises a loud, actionable error — FAIL IS FAIL, no silent fallback. Overrides:
`ASADO_LOCK_GUARD_KILL=0`, `ASADO_LOCK_GUARD_KILLABLE=…`, `ASADO_LOCK_GUARD_WAIT_S=…`.

**Exact coverage boundary — who is guarded vs not** (verified by grepping `guarded_connect` usage):

GUARDED (11 files, ~23 call-sites) — the core builders and loop writers:
`setup_duckdb.py`, `build_normalized_panel.py`, `build_daily_panels.py`, `build_predmkt_panel.py`,
`build_event_log.py`, `build_variable_registry.py`, `predmkt_daily_job.py`, and loop-side
`loop/loopdb.py`, `loop/build_similarity_features.py`, `loop/run_manifest.py`,
`loop/build_governance_scorecard.py`.

UNGUARDED, and this is the weak point — bare `duckdb.connect(...)`:
- **Two writers inside the monthly pipeline (the real gap):**
  `load_gdelt_deep_to_duckdb.py:126` and `build_gdelt_deep_cs.py:142` open the main DB
  read-WRITE with no guard and no self-heal (monthly GDELT-deep steps). A squatter during those
  steps fails them with a raw lock exception.
- **Live read interfaces that can themselves become the squatter:** `db_bridge.py:42`
  (`AsadoDB`, read-only), `asado_mcp_server.py`, the Streamlit `frontend/`, `setup_neo4j.py`
  (reads), `build_embeddings.py`, `harness/ff_spanning.py`. These are unguarded reads — fine as
  long as they never hold the connection open across a nightly write window.

If you add a new pipeline writer to the main DB, use `guarded_connect`, not `duckdb.connect`.

---

## 4. The loop's fail-soft execution model

`scripts/loop/loop_daily_job.py` orchestrates the nightly Alpha-Hunting Loop. Its docstring's
step count is STALE — the real count is **47 steps**, matching the 47 entries in
`config/governance_contract.yaml` under `steps:` (verified count). Design:

- **47 steps, always all run.** Each step is its own subprocess; one failure does not stop the
  rest (`loop_daily_job.py:128-129`).
- **Optionality is data-driven.** `_load_optional_steps()` (`loop_daily_job.py:361-368`) reads
  `optional: true` from the governance contract. Of the 47 steps, **20 are `optional: false`
  (required) and 27 are `optional: true`** (verified count in `governance_contract.yaml` —
  NOTE: an older note that says "19 required" is off by one; it is 20).
- **PARTIAL semantics.** `_run_step()` retries up to `max_attempts=2` but treats exit code 2 as
  PARTIAL and does NOT retry it (`loop_daily_job.py:372-396`): the step kept its completed work
  and a downstream input was simply absent (e.g. a Bloomberg-fed table). PARTIAL and
  optional-step failures become warnings, not failures (`:436-447`).
- **Exit code.** `rc_final = 1 if failures else 0` (`:467`); the job returns 1 **iff** the
  `failures` list is non-empty (`:477-480`) — i.e. only a required, non-PARTIAL step failing
  reds the loop. The governance tail (manifest, brief auto-commit, heartbeat, scorecard) is all
  fail-soft and can never change the exit code (`:452-474`).
- **Singleton via flock.** A non-blocking exclusive `fcntl.flock` (`:179-190`) guarantees one
  loop instance; a second concurrent launch exits immediately rather than double-writing.

**Weak point — detector fragility (report, don't silently fix).** `scripts/loop/build_dislocations.py`
runs detectors D1–D10 (D6 is blocked on insufficient history; live set per `:67`:
D1 D2 D3 D4 D5 D7 D8 D9 D10). The dispatch loop at `build_dislocations.py:892-907` calls each
detector as a bare `got = fn()` with **no per-detector try/except**, and D2/D5/D7 have **no
internal exception handling**. `run()`'s only handler is a `finally:` at `:1019` (connection
cleanup, which re-raises). CONSEQUENCE: a single exception in one detector propagates out and
crashes the entire `build_dislocations` step plus the ≥4 downstream readers of
`dislocation_daily`. This is the loop's most brittle spot — it is not wrapped by the fail-soft
per-step model because the crash happens *inside* one step, not between steps.

---

## 5. The skeptic harness (the crown jewel) — gate sequence and why each exists

`scripts/harness/evaluate_signal.py` is the discipline that makes ASADO's falsification
trustworthy. A signal must pass an ordered gauntlet; each gate closes a specific way of fooling
yourself:

1. **Pre-registration (HARD GATE).** `evaluate_signal.py:718-724`: if the hypothesis is not
   already in the ledger, it raises `PermissionError` ("No anonymous backtests"). WHY: a
   mechanism written *after* seeing results is a story, not a hypothesis. Registration
   (`ledgers.py:register_hypothesis`, `:179`) demands a ≥15-word mechanism paragraph written
   before results (`:199-200`), sha256-hashed with the spec as the pre-registration proof.
2. **Family registry (HARD GATE).** `register_hypothesis` classifies the signal's *variable*
   (not the caller's free-text family) via `config/family_registry.yaml` using
   `resolve_family()`; an unmatched prefix raises `UnclassifiedVariableError`
   (`ledgers.py:203-204`, imported from `loop/family_registry.py`). WHY: the canonical family
   sets the trial count N that feeds the deflated Sharpe. If you could pick your own family you
   could reset your own multiple-testing penalty. So the family is derived, and an
   unclassifiable variable stops the run — you must add it to the registry first.
3. **Forward-return blacklist (HARD GATE).** `evaluate_signal.py:140-149` bans the `NMRet`
   family (`1MRet/3MRet/6MRet/9MRet/12MRet` + daily analogs `1DRet/5DRet/20DRet/60DRet/120DRet`).
   WHY: these are optimizer *targets* labeled at the START of their window — using one as a
   predictor is pure lookahead (empirically produced a fake IC of 0.25, `:140-145`). **Known P0
   risk:** this ban is *duplicated*, not shared — `triptych_kernel.py:84-91` re-derives it with
   a regex `^\s*\d+\s*[MD]\s*Ret\s*$`. Two independent definitions can drift; if you add a new
   forward-return variable you must update BOTH.
4. **PIT embargo, fails closed.** `evaluate_signal.py:660-679`: a daily signal gets same-day
   entitlement only if `config/pit_proof_registry.yaml` marks that variable `status: passing`;
   otherwise it FAILS CLOSED to the conservative lag. WHY: absence of a proof must cost you, not
   be free.
5. **Coverage floors + rank-IC / Newey-West t + cost grid** (5/10/25/50 bps + borrow).

**Verdict tiers:** DEAD / WEAK / WATCH (+ INSUFFICIENT_COVERAGE). `WATCH` — the strongest a
signal can currently earn — requires ALL of: NW-t ≥ 2.5, ≥ 60% positive-IC years, net-25bps
long-short Sharpe > 0, and deflated Sharpe > 0. (Ledger as of 2026-07-08: 59 hypotheses — 21
DEAD, 21 WEAK, 16 INSUFFICIENT_COVERAGE, 1 WATCH. See `asado-graveyard` / `asado-research-protocol`
for the ledger lifecycle.)

**`ff_spanning.py` is NOT wired into the loop** (verified: no reference in `loop_daily_job.py`
or `governance_contract.yaml`). It regresses a return series on regional Fama-French factors to
separate alpha from repackaged beta, but runs **manual CLI only**. WHY it matters: a "signal"
that survives the harness may still be repackaged FF beta, and the spanning check that would
catch that is not automatic — a human must run it. Do not assume a passing harness verdict has
been FF-spanned.

---

## 6. Neo4j: role and soft coupling

Neo4j (`bolt://localhost:7687`) holds the relational/graph layer: 7 node types, 9 edge types,
rebuilt by full clear-and-rebuild. The coupling to the rest of the pipeline is deliberately
**soft** (verified degradation paths):
- `monthly_update.py:353` `ensure_neo4j()` gates the Neo4j rebuild; `--skip-neo4j` and a
  `--duck-only` fallback (`:588,1096,1104`) let the warehouse rebuild fully even with Neo4j down.
- Daily and graph-feature builders probe for Neo4j and fall back (the daily loop's
  graph-feature step degrades to the last PIT snapshot rather than crashing).
- `neo4j-guard` (a launchd job) clears a stale Homebrew pidfile — added after a 2026-06-18
  outage where the pidfile guard existed in-repo but the plist was never installed. LESSON
  (see `asado-change-control`): deployed ≠ committed; verify `launchctl` state for ops fixes.

**HARD FACT — embeddings live ONLY in Neo4j.** The 128-d PCA state embeddings are stored solely
as `Country.state_embedding` with a cosine vector index (`build_embeddings.py:11-12,36-43`).
They are NOT in DuckDB. CONSEQUENCE: if Neo4j is down or wiped, similarity/embedding features
have no fallback source — they must be recomputed by re-running `build_embeddings.py` against a
live Neo4j. Do not assume you can reconstruct embeddings from the warehouse.

---

## 7. Cross-repo contracts

- **Fable Daily Trading (FDT) reads the loop DB — no handshake (WEAK POINT).** The sibling repo
  `A Complete/Fable Daily Trading` opens `Data/loop/asado_loop.duckdb` **read-only**
  (`src/data_access.py:42`, path from `config/book_config.yaml:20`) and its `fdt-decide` launchd
  job runs **12:20 PT on weekdays** (verified in `~/Library/LaunchAgents/
  com.arjundivecha.fdt-decide.plist`). There is **no completion handshake** with ASADO: if the
  ASADO loop is mid-run at 12:20, FDT reads the last-committed (internally consistent but possibly
  stale) snapshot and proceeds on staleness day-count alone. HARD RULE: any change to loop-DB
  table names, schemas, or the meaning of `combiner_scores_daily` is a cross-repo breaking change
  — check FDT's `src/data_access.py`, `decide.py`, `layers.py`, `desk.py` before renaming.
- **Cockpit static-JSON contract.** `cos_mockups/build_cockpit_data.py` emits a static
  `cockpit_data.json` consumed by the frontend; `COCKPIT_DATA_CONTRACT.md` requires that producer
  errors be *surfaced* in the JSON, not swallowed. Keep the contract's error-surfacing fields.
- **Bloomberg env split.** `collect_*_bbg.py` collectors run under the OpusBloomberg conda env
  (`/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv`) and write parquet only;
  paired `load_*.py` run in the project `venv` and rebuild loop tables idempotently. launchd's
  PATH has no `/opt/homebrew/bin`, so conda is invoked by absolute path. (For all Bloomberg
  connection specifics, defer to the global `bloomberg-skill` — do not restate it here.)
- **Hardcoded sibling-repo paths (WEAK POINT).** Absolute paths to OpusBloomberg, GDELT, the
  "T2 Factor Timing Fuzzy Daily" feed, and `.env.txt` (`collect_extended.py:139`) are hardcoded;
  moving or renaming any of those sibling directories breaks the collectors silently. There is no
  path-existence preflight.

---

## 8. Known weak points (honest inventory)

Each of these is real and load-bearing. Mention the relevant one when a change touches it; most
are "report, don't silently fix" (see the FAIL-IS-FAIL / USER_FIX_LIST rule in `asado-change-control`).

- **Forward-return ban duplicated**, not shared: `evaluate_signal.py:146-149` (explicit set) vs
  `triptych_kernel.py:84-91` (regex). Drift risk = leakage. **P0.**
- **Detector fragility:** `build_dislocations.py:892-907` dispatch has no per-detector guard;
  D2/D5/D7 have no internal try/except; `run()` only has a `finally` at `:1019`. One detector
  bug crashes the step + downstream `dislocation_daily` readers (§4).
- **Two unguarded monthly writers:** `load_gdelt_deep_to_duckdb.py:126`,
  `build_gdelt_deep_cs.py:142` open the main DB read-write with no lock guard (§3).
- **`ff_spanning.py` not wired** into the pipeline — alpha-vs-beta check is manual only (§5).
- **Embeddings single-homed in Neo4j** — no DuckDB fallback (§6).
- **FDT cross-repo read has no completion handshake** — staleness by day-count only (§7).
- **Hardcoded sibling-repo paths** — silent breakage if a sibling repo moves (§7).
- **launchd PATH / conda fallback hardcoded** in `loop_daily_job.py:160-164`,
  `daily_update.py:96-98`, `run_asado_daily.sh:61` — brittle to environment changes.
- **`run_asado_daily.sh` retry loop is bounded by an 11:00 wall-clock**, with no attempt cap
  (`:90-136`) — a persistently failing run retries until 11:00 rather than a fixed number of times.
- **Combiner is an in-sample ceiling, not an estimate.** `build_combiner.py:47-50,238-239`
  states its own HONESTY NOTE: the feature list was selected in-sample, there is no purge/embargo
  at the yearly refit boundary, so `combiner_scores_daily` (the live prediction surface) is a
  ceiling. Do not cite its harness verdict as an out-of-sample expectation.

---

## 9. When NOT to use this skill

This skill is the "why it is shaped this way" reference. Do NOT use it for:
- **Running, operating, or health-checking the platform** (schedules, manual runs, tests,
  frontends, MCP) → use **asado-operations**.
- **Diagnosing a live failure** (symptom → cause) → use **asado-debugging-playbook**.
- **The experiment → harness → ledger research method** at house standard →
  use **asado-research-protocol**.
- **Checking whether an idea is already dead before proposing it** → use **asado-graveyard**.
- **How a change is classified and gated here** (the house laws with their incidents) →
  use **asado-change-control**.
- **The P0 leakage-guard build campaign** → use **asado-leakage-guard-campaign**.
- **Orientation / doc-authority routing / current state** → use **asado-start-here**.

If you came here to *do* something rather than to understand an invariant, you are probably in
the wrong skill — pick from the list above.
