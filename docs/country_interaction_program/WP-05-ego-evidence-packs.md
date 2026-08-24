# WP-05 — Ego-network evidence packs  [Phase 1 | SONNET-SAFE]

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
`scripts/loop/build_evidence_packs.py` writes one JSON pack per (run date, dislocated
country) — trigger rows + headlines — and joins ZERO neighbor context. Add a
`neighborhood` section to every pack. This is Layer-2 context: no trials, no family
charges, no predictions.

## Design (fixed)
For the pack's country C, read the three 34×34 matrices
(`Data/processed/bilateral_trade_matrix.parquet`, `bilateral_banking_matrix.parquet`,
`bilateral_portfolio_matrix.parquet` — NOT Neo4j) and the loop DB, and add:
```json
"neighborhood": {
  "as_of": "<run date>",
  "top_trade_partners":  [{"country","weight_share","ret21d","active_dislocations":[...]}]  // top 5
  "top_bank_creditors":  [...same, top 5...],
  "top_portfolio_holders":[...same, top 5...],
  "edge_deltas": {"note":"latest vintage vs prior vintage, from graph_edge_vintages",
                   "largest_changes":[{"edge_type","counterparty","old_w","new_w"}]},   // top 5 by |Δ|
  "neighbor_summary": "<one TEMPLATED sentence, e.g. '3 of 5 top trade partners are themselves dislocated'>"
}
```
- `ret21d` from the same return surface the pack already uses (or `t2_factors_daily`
  `1DRet` compounded 21d — read-only, guarded).
- `active_dislocations` from `dislocation_daily` for the same run date.
- Templated strings only — NO LLM calls in this builder (constitutional: text generation
  belongs to Layer 2, the pack is evidence).
- If a matrix or table is unavailable: write `"neighborhood": {"degraded": "<reason>"}` and
  log loudly — never silently omit the key. Missing values inside follow the house rule
  (last-available flagged `*`, or em-dash semantics — never invented).

## Files touched
`scripts/loop/build_evidence_packs.py` only (extend `write_pack` and its callers).
Pack schema is additive — existing keys unchanged (Layer-2 readers parse them).

## Gate — `Data/work/experiments/wp05_ego_packs/verify.py`
- Run the builder in its check/dry mode if the header documents one; otherwise run for the
  latest run date into a TEMP output dir (builder has `--out`-style override? read header;
  if it can only write the production packs dir, run it for real — packs are additive and
  permanent, that is acceptable — but back up the day's dir first per rule 5).
- Assert: every pack written today has `neighborhood` with all 5 subkeys; every neighbor
  country name is in the 34-country universe; shares sum ≤ 1.0 + eps; JSON parses; a pack
  for a country with no matrix coverage carries `degraded` rather than fabricated zeros.
- Baseline tests.

## Rollback
`git restore scripts/loop/build_evidence_packs.py`; restore the backed-up packs dir.

## Commit template
`WP-05: evidence packs carry the dislocated country's ego network`
