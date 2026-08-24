# WP-02 — v1 feature retirement + gate-roster v2  [Phase 0 | SONNET-SAFE with a hard STOP branch]

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
Retire the look-ahead v1 graph feature surface and move the family-IC gate onto the PIT
surface — WITHOUT silently changing the R-A gate state that authorizes live sizing.

Background a fresh session needs: `graph_features_daily` (v1) is built nightly by
`scripts/loop/build_graph_features.py` from CURRENT Neo4j edges; its pre-2026-06 history
applies a 2026 snapshot backward (acknowledged look-ahead L-05). The PIT replacement
`graph_features_pit_daily` exists and is built by `build_graph_features_pit.py`. The
family-IC monitor's GATE roster (`scripts/loop/family_ic_roster_v1.json`, frozen 2026-07-14,
roster `book_2026_07_14`, role=gate) has exactly ONE member on the v1 table:
`GRAPH_BANK_NBR_RET_GAP_21D`. Its PIT twin is `GRAPHP_BANK_NBR_RET_GAP_21D`
(measured ρ 0.983–0.994 by era). The OTHER roster (`ref16_frozen`, role=inv4_reference) also
references v1 variables — that roster is a frozen known-answer reference and MUST NOT be edited.

## Steps
1. **Unwire v1 from the nightly**: in `scripts/loop/loop_daily_job.py`, remove the step
   tuple anchored by `("build_graph_features", [PY, "scripts/loop/build_graph_features.py"])`
   (count must be 1). Do NOT delete `build_graph_features.py` itself; add a docstring line
   at its top: `RETIRED from the nightly 2026-08-24 (WP-02): v1 look-ahead surface. Kept for
   the frozen ref16 reference roster only.` Keep the v1 TABLE in the DB (the frozen reference
   roster reads it).
2. **Roster v2**: copy `family_ic_roster_v1.json` → `family_ic_roster_v2.json`. In v2, in
   family `network_spillover`, roster `book_2026_07_14` ONLY, change the one member with
   `"table": "graph_features_daily"` to `"variable": "GRAPHP_BANK_NBR_RET_GAP_21D",
   "table": "graph_features_pit_daily"`. Update `version` to `v2`, set `frozen_as_of` to
   today, and add a `provenance` note: `v2 2026-08-24: gate roster repointed to the PIT bank
   feature (WP-02); ref16_frozen untouched by design`. Leave `ref16_frozen` byte-identical.
3. **Point the monitor at v2**: find where `build_family_ic_monitor.py` loads the roster
   (grep `family_ic_roster_v1`); repoint to v2. If the loader hardcodes v1 in more than one
   place, anchor-replace each.
4. **Re-derive the gate history on the PIT surface**: read the header of
   `scripts/harness/backfill_ic_series.py` and use its documented interface to rebuild the
   family-IC series for `network_spillover` under roster v2 into a PARALLEL output (its
   docs will say how; if it cannot write to a parallel table/file without overwriting the
   live one, STOP-AND-REPORT — do not overwrite `family_ic_nightly`).
5. **Compare gate trajectories**: write `Data/work/experiments/wp02_roster_v2/compare_gates.py`
   producing, for v1-surface vs v2-surface: month-end family IC series, the derived
   parked/re-armed state per month (the monitor's rule: re-arm after 2 consecutive positive
   month-ends), and specifically the CURRENT state as of the latest month-end.

## THE STOP BRANCH (this is the point of the WP)
- If v2's current state == re-armed (matches v1): proceed, commit everything, note the
  trajectory diff count in the commit body.
- If v2's current state != re-armed: **STOP-AND-REPORT to Arjun.** Commit ONLY the comparison
  evidence (the experiment dir), NOT the roster switch or the monitor repoint. The live gate
  that authorized sizing was derived on a look-ahead surface and does not survive the honest
  one — that changes the Phase-2/3 sizing posture and is Arjun's decision, not a splice.

## Gate
`compare_gates.py` exit 0 iff both series computed over the full history AND the final-state
comparison printed. Tests at baseline. Nightly dry check: run
`./venv/bin/python scripts/loop/loop_daily_job.py --help` (or documented dry mode) to confirm
the step list parses without build_graph_features.

## Rollback
`git restore scripts/loop/loop_daily_job.py scripts/loop/build_family_ic_monitor.py`;
delete `family_ic_roster_v2.json`.

## Commit template
`WP-02: retire v1 graph surface from the nightly; gate roster v2 on the PIT table`
— body MUST include: v1-vs-v2 gate trajectory diff (months differing / total), current-state
comparison, and the sentence "ref16_frozen reference roster untouched."
