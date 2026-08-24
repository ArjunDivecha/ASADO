# WP-12 — UNGA ideal-point dyad edges  [Phase 1–2 | SONNET-SAFE | context tier]

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
Geopolitical-alignment edges from Bailey-Strezhnev-Voeten (CC0, Harvard Dataverse, v39
2026-07-30, dyadic file pre-built: `IdealPointDyads1946-2025.tab`, ~73MB). Context/regime
tier only — the return test stays open; no registration in this WP.

## Steps
1. `scripts/collect_unga_dyads.py`: download via the Dataverse API into
   `Data/raw/unga/`; map country names via `config/country_mapping.json`; keep 34×34 pairs;
   write `unga_dyad_vintages(year, focal, neighbor, ideal_distance, applies_from)` with
   availability = session end + 6 months (UN sessions end ~December; distances knowable the
   following year — record the convention in the header).
2. Derived context column in `graph_state_country_daily` (WP-06's table):
   `GSTATE_GEOPOL_TRADE_TENSION` = PIT trade-share-weighted mean ideal-point distance to
   top-5 partners (rising = trading with increasingly non-aligned partners).
3. Add the pair distance to WP-05's `neighborhood` pack section (one field per listed
   neighbor: `ideal_distance`).

## Gate
Sanity anchors printed: US–UK distance small and stable; US–China distance large and rising
post-2018; 30+ of 34 countries mapped (pseudo-countries NASDAQ / US SmallCap / ChinaH map to
parent or are excluded — document which). Coverage per year printed. Baseline tests.

## Commit template
`WP-12: UNGA ideal-point dyads — alignment edges + geopolitical trade-tension context`
