# WP-01 — D2 detector fix batch  [Phase 0 | SONNET-SAFE]

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
The nightly dislocation detector D2 (`scripts/loop/build_dislocations.py`, function
`d2_graph_propagation`) currently reads the QUARANTINED look-ahead table
`graph_features_daily` and has two known defects. Fix all three:
1. Repoint to the PIT table `graph_features_pit_daily` (variables `GRAPHP_TRADE_NBR_RET_GAP_21D`,
   `GRAPHP_TWOHOP_TRADE_GAP_21D` — measured ρ vs v1: 0.983–1.000, so verdict drift is expected
   to be near-zero; the gate below MEASURES it rather than assumes it).
2. Add a freshness guard: if the newest date in `graph_features_pit_daily` is more than
   5 calendar days older than the run date, emit a `degraded_row("D2", ...)` (copy the exact
   pattern used at the end of `d1` — search anchor `degraded_row("D1", "A1", "share_coverage"`)
   and SKIP the z-scoring. A stale feed must be loud, never silent.
3. Branch 1 (the `gap` loop) fires on the gap z alone. Add the own-price gate branch 2
   already has: require `abs(own_z) < 0.5` (own_z is ALREADY COMPUTED in branch 1 —
   variable `own_z` — it is just never checked).

## Files touched
- `scripts/loop/build_dislocations.py` (function `d2_graph_propagation` only)
## Files forbidden
- Everything else in `scripts/loop/`. Do not touch d1, d3–d10, the brief renderer, or
  `loop_daily_job.py` (that is WP-02).

## Content anchors (verify count==1 before replacing)
- `gap = pivot_var(con, "graph_features_daily", "GRAPH_TRADE_NBR_RET_GAP_21D", qualified=False)`
- `twohop = pivot_var(con, "graph_features_daily", "GRAPH_TWOHOP_TRADE_GAP_21D", qualified=False)`
- In branch 1, the anchor for the gating insert is the block beginning
  `own_z = zscore_last(ret21[c]) if c in ret21 else np.nan` inside the `else:` — restructure so
  the row is appended ONLY when `not np.isnan(own_z) and abs(own_z) < 0.5` (mirror branch 2's
  condition). Keep the component keys IDENTICAL (`trade_nbr_gap_21d`, `gap_z_3y`,
  `own_ret21_z`, `reading`) — the brief and cockpit parse them.

## AMENDED 2026-08-24 (Arjun: "fix this issue") — gate v2
The original gate below ("<5% of days differ") FAILED at 98.4% (commit 3c1b359,
STOP-AND-REPORT) and was retired as MISCALIBRATED: old D2 fires ~5.75 rows/day on 98% of
days, so per-day set equality diverges even when the change is exactly as intended. The
replacement gate v2 (shadow_d2.py v2.0) asks the correct question — is every differing row
attributable to exactly the two intended mechanisms (own-price gate, PIT threshold), with
zero unexplained rows, and is the new detector non-degenerate (fires >=20% of days, more
selective than old, never noisier). Result: PASS — 1,132 differing rows = 1,111 own_gate
+ 21 pit_threshold + 0 UNEXPLAINED; new D2 fires 1.28 rows/day on 39% of days (was
5.75/day on 98%). The volume drop is the fix working: the ungated branch was the
documented "global wobble lights up 34 countries" defect (ox-graph-deep-dive I.4).

## Gate v1 (RETIRED — kept for the record; write to `Data/work/experiments/wp01_d2_shadow/`)
Write `shadow_d2.py` (with full doc header) that, over the LAST 250 trading days:
1. Replicates old-D2 logic (v1 table, no own-price gate on branch 1) and new-D2 logic
   (PIT table, gate on) side by side, per day, using `guarded_connect` read-only.
2. Reports: (a) days where the fired (country, direction) set differs — expect < 5% of days;
   (b) count of branch-1 rows the own-price gate suppresses, total and per country;
   (c) any day where NEW fires and OLD doesn't (should be rare; list them all).
3. Exit 0 iff (a) < 5% of days differ AND the suppressed rows all have `abs(own_z) >= 0.5`.
If the diff exceeds 5%: STOP-AND-REPORT with the full table — do not commit. This is a
behavior change to a live detector; Arjun sees the numbers first.
Then: `./venv/bin/python -m pytest tests/ -q` at baseline, and run
`./venv/bin/python scripts/loop/build_dislocations.py --help` (or its documented check mode
if the header shows one) to confirm it still imports and parses.

## Rollback
`git restore scripts/loop/build_dislocations.py`

## Commit template
`WP-01: D2 reads the PIT graph table; freshness guard; own-price gate on branch 1`
— body: the three fixes, the shadow-run numbers (days compared, % differing, rows suppressed),
and the sentence "Component keys unchanged; brief/cockpit parsing unaffected."
