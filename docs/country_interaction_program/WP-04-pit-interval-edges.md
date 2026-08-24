# WP-04 — PIT interval edges: `applies_to` + Neo4j as-of load  [Phase 1 | SONNET-SAFE]

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
Make the vintage store a complete interval model and load it into Neo4j so any as-of date is
queryable. Measured facts driving the design: topology is near-static (consecutive-vintage
Jaccard: trade 1.000, bank 0.974, holder 0.923) so month-end slice materialization would
store ~670k edges to represent the 93,800 interval rows — intervals win.

## Steps
1. **`applies_to` column**: new script `scripts/loop/build_edge_intervals.py` (doc header
   mandatory) that reads `graph_edge_vintages` (loop DB; schema
   `edge_type, vintage_end, applies_from, focal, neighbor, weight`) and writes table
   `graph_edge_intervals` = same rows + `applies_to` = the next vintage's `applies_from`
   for that (edge_type, focal, neighbor), NULL for the newest vintage. Write to the LOOP DB
   (durable store) via a WRITE connection — schedule outside the nightly windows in rule 2,
   and never leave the connection open.
2. **Neo4j load**: extend `setup_neo4j.py` with a loader for three new relationship types
   `TRADES_WITH_PIT`, `HAS_BANKING_EXPOSURE_TO_PIT`, `HOLDS_PORTFOLIO_PIT` from
   `graph_edge_intervals`, properties `{applies_from, applies_to, weight, vintage_end,
   pit: true}`. Current (un-suffixed) edges stay untouched. ~94k edges total — batch the
   load (UNWIND batches of ~5k).
3. **Canonical as-of query** documented at the top of the loader:
   ```
   MATCH (a:Country)-[r:TRADES_WITH_PIT]->(b:Country)
   WHERE r.applies_from <= $asof AND (r.applies_to IS NULL OR $asof < r.applies_to)
   ```

## Gate — `Data/work/experiments/wp04_intervals/verify.py`
- Interval integrity: per (edge_type, focal, neighbor), intervals are non-overlapping and
  ordered; exactly one open (NULL) interval per key that exists in the newest vintage; 0 rows
  with applies_to <= applies_from.
- Round-trip: for 5 probe dates (2003-06-15, 2008-10-01, 2015-03-10, 2020-06-15, latest),
  the as-of Cypher edge set for `trade` EXACTLY equals the DuckDB query
  `select focal, neighbor, weight from graph_edge_intervals where edge_type='trade' and
  applies_from <= ? and (applies_to is null or ? < applies_to)`. Same for bank on 2 dates.
- PIT spot check: as-of 2008-10-01 must use the vintage whose `vintage_end` ≤ 2008-07
  (publication lag preserved), never the 2008-Q3 vintage itself.
Tests at baseline.

## Rollback
Drop `graph_edge_intervals`; `git restore scripts/setup_neo4j.py`; delete the new script.

## Commit template
`WP-04: interval-stamped PIT edges in DuckDB and Neo4j (any-as-of-date queries)`
