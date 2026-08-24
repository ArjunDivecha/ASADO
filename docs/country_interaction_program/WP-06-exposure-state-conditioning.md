# WP-06 — Exposure-state conditioning package + divergence detector  [Phase 1 | SONNET-SAFE]

<!-- This block is duplicated VERBATIM at the top of every WP file. Source copy. -->
## Ground rules (verbatim in every WP — read before every session)

1. **Repo**: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO`. This checkout is
   PRODUCTION — launchd runs nightly jobs from it. NEVER switch branches. Before EVERY
   commit: `[ "$(git rev-parse --abbrev-ref HEAD)" = "main" ] || STOP`.
2. **DuckDB**: never hold a connection. Open via
   `sys.path.insert(0,'scripts'); from duckdb_lock_guard import guarded_connect`,
   `read_only=True` unless the WP says otherwise, and close in a `finally`. Avoid
   06:00–08:30 PT and 09:00–10:00 PT (nightly + morning runs).
3. **Edits to existing files**: content-anchored only. Pattern:
   `assert t.count(old)==1; t=t.replace(old,new)`. NEVER line numbers, NEVER regex-replace
   on code. If the anchor count is not exactly 1 → STOP and report; the file has drifted.
4. **New scripts**: standard ASADO doc header (script name, INPUT FILES / OUTPUT FILES with
   full absolute paths, VERSION, USAGE, NOTES). Copy the shape from any script in `scripts/`.
5. **Backups**: before any change that rewrites a production output or config, copy the
   file(s) to `Data/backups/<wp-id>_<YYYYMMDD_HHMMSS>/` first.
6. **Gates are executable**: every WP has a gate script. Gate exit 0 → commit. Gate fails →
   `git restore` the touched files, report the FULL failing output. NEVER commit on a failed
   gate, never describe a hoped-for result. Fail is fail.
7. **Tests**: `./venv/bin/python -m pytest tests/ -q` must stay at baseline
   (320 passed / 8 skipped / 0 failed as of 2026-08-24) after every WP. New failures → STOP.
8. **Tree clean at session end.** Never leave the tree dirty overnight — the nightly runs
   from this checkout. Commit (gate-passed) or restore, nothing in between.
9. **Forbidden always**: `setup_duckdb.py` persistent tables; forward-return variables
   (`1MRet`…`12MRet`, `1DRet`…`120DRet`) as signal inputs; edits to monthly-collector or
   T2-feed scripts; `experiments/` writes outside `experiments/<name>/` or
   `Data/work/experiments/<name>/`; citing pre-embargo t≈4 graph stats.
10. **STOP conditions are real.** Where a WP says STOP-AND-REPORT, end the session with a
    written report (file + chat) and do NOT proceed. Escalation is success, not failure.
11. **Commits**: one WP = one commit (plus its gate evidence), message per the WP template,
    ending with the standard Co-Authored-By/Claude-Session trailer.
12. **Model routing**: WPs are marked SONNET-SAFE or OPUS-REQUIRED. A Sonnet session must
    not attempt an OPUS-REQUIRED step; report back instead. Verdict interpretation always
    escalates.

---

## Goal
Context-tier graph-STATE variables (they gate/size, never trade — no family trials) plus one
new detector. Three deliverables:

### 6a. `scripts/loop/build_graph_state.py` → loop-DB table `graph_state_daily`
Tidy schema `(date, variable, value)` — GLOBAL scalars, not per-country. From
`graph_edge_intervals` (WP-04) as-of each month-end, forward-filled to daily with the PIT
stamp rule (state knowable only after the vintage's applies_from):
- `GSTATE_TRADE_DENSITY`, `GSTATE_BANK_DENSITY`, `GSTATE_HOLDER_DENSITY` (sum of weights /
  possible pairs)
- `GSTATE_BANK_ALGEBRAIC_CONNECTIVITY` (2nd-smallest Laplacian eigenvalue, holder + bank
  graphs; networkx)
- `GSTATE_BANK_CLAIMS_3Y_GROWTH` (BIS EWI: 3y growth of total inbound claims; per-country
  panel version `(date, country, value)` in table `graph_state_country_daily`)
- `GSTATE_HOLDER_FRAGMENTATION` (1 − size of largest connected component / N)
### 6b. Return-topology columns (honestly labeled COINCIDENT, never alpha):
- `GSTATE_RET_TREE_LENGTH` (normalized MST length on 63d return correlations),
  `GSTATE_ABSORPTION_RATIO` (top-eigenvalue share, 63d window), from `t2_factors_daily`
  1DRet pivot — read-only, guarded.
### 6c. Divergence detector D11 in `build_dislocations.py`:
Fires when the exposure graph is freezing/fragmenting while the return graph tightens:
`z(GSTATE_HOLDER_FRAGMENTATION) > 1.5 AND z(GSTATE_ABSORPTION_RATIO) > 1.5` (3y z's, same
`zscore_last` helper). Global row (entity "GLOBAL"), archetype `A11`, with a
`degraded_row` freshness guard from day one (the D2 lesson). Detector rows are CONTEXT — 
add to the brief's context section, not tradeable dislocation lists; follow how existing
global/degraded rows render.

## Constitutional notes for the builder
These are REGIME columns. Do NOT register them as harness hypotheses; do not add them to the
combiner. They may be cited by Layer 2 and by future interaction trials (WP-10). The
density-direction trap is real: exposure density and market-spillover density move OPPOSITE
in crises — never collapse them into one "connectedness" scalar.

## Gate — `Data/work/experiments/wp06_graph_state/verify.py`
- Full-history build completes; every GSTATE series spans ≥ 2003→present with no gaps > 45d;
  no NaN runs at the tail; PIT spot check (state at 2008-10-01 derives from vintages
  applies_from ≤ that date).
- D11 backtest count: fires on < 3% of days over history, and the top-10 firing dates
  printed (expect clusters at 2008-09, 2020-03; eyeball line in the report).
- Baseline tests; nightly wiring added to `loop_daily_job.py` AFTER gate passes (same
  commit), anchored insertion next to the other build steps.

## Rollback
Drop the two tables; `git restore` the touched scripts.

## Commit template
`WP-06: exposure-state conditioning columns + D11 exposure/return divergence detector`
