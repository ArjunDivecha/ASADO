# WP-03 — Neo4j hygiene: forecast dates, SUBJECT_TO, snapshot labels  [Phase 0 | SONNET-SAFE]

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
Three known defects in the current Neo4j graph (built nightly by `scripts/setup_neo4j.py`,
connection `bolt://localhost:7687`, auth in that script):

1. **25.6% of `HAS_FACTOR_EXPOSURE` edges are future-dated** (3,523 of 13,759; stamps
   2026-09-01 [benign next-month T2 convention], 2026-12-01, 2031-12-01 [IMF WEO
   projections], 2100-12-01 [DIP demographics]). Any `MAX(date)` traversal answers from 2100.
2. **`SUBJECT_TO` maps every country to "Iran Sanctions"** — a `collect(s)[0]` arbitrary-
   first-element bug in `setup_neo4j.py` (search anchor: `collect(s)[0]` — the deep-dive
   places it near line 1040; anchor by content, count must be 1).
3. **`LEADS` / `SIMILAR_TO` / `TRADES_WITH` / `HAS_BANKING_EXPOSURE_TO` are single-stamp
   snapshots** (as_of 2026-08 / year 2025 / 2026-Q1) with nothing marking them as
   current-only.

## The one chosen fix per defect (no alternatives)
1. In `setup_neo4j.py`, locate the query/loader that creates `HAS_FACTOR_EXPOSURE` edges.
   Filter out rows where the variable name starts with a forecast prefix AND the date is
   > the run date. Use EXACTLY the prefix tuple from the established precedent:
   `FORECAST_VARIABLE_PREFIXES = ("IMF_WEO_", "DIP_")` in
   `scripts/build_normalized_panel.py` (import it or mirror it with a comment citing that
   source). The 2026-09-01 next-month stamps are the T2 date convention — KEEP those.
2. Fix the SUBJECT_TO match so each country joins its OWN sanction program node(s). Read the
   surrounding loader first; the correct form matches per-country rather than taking
   `collect(s)[0]`. If after reading you cannot determine the intended per-country mapping
   from the source data, STOP-AND-REPORT (do not invent a mapping).
3. Add a property `pit: false` and `note: "current snapshot only — for history use
   graph_edge_vintages (DuckDB) or the *_PIT edges (WP-04)"` on the four snapshot edge
   types at load time.

## Gate — `Data/work/experiments/wp03_neo4j_hygiene/verify.py`
After re-running `setup_neo4j.py` (it is safe to run standalone; it rebuilds the graph):
- Cypher: count `HAS_FACTOR_EXPOSURE` edges with `toString(r.date) > <today>` AND variable
  prefix in the forecast set → must be 0; edges dated 2026-09-01 (next-month convention)
  must still exist (>3,000).
- Cypher: `MATCH (c:Country)-[:SUBJECT_TO]->(s) RETURN s.name, count(c)` → "Iran Sanctions"
  no longer has count 31; distribution printed into the gate output.
- Cypher: the four snapshot edge types all carry `pit: false`.
- Regression: node count and non-SUBJECT_TO edge counts within 1% of pre-change (print both).
Tests at baseline.

## Rollback
`git restore scripts/setup_neo4j.py` and re-run it once to restore the old graph.

## Commit template
`WP-03: Neo4j hygiene — no future-dated factor edges, per-country SUBJECT_TO, snapshot labels`
