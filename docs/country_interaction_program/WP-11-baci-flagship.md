# WP-11 — BACI + the flagship: two-sided transmission test  [Phase 3 | SONNET builds; design is fixed here]

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

## CANCELLATION JOINT (read first)
This WP embeds the standing G2 gate from Research-Agenda-2026-07-v2: build the
orthogonalized-IC test FIRST (Step 2). If the orthogonal IC ≈ 0 (pooled t < 2), the
diffusion territory DOWNGRADES: report, mark WP-11 CANCELLED in the index, and do NOT
proceed to Steps 3–4. That outcome is a success of the program, not a failure of the session.

## Step 1 — BACI collector (new collector = allowed addition)
`scripts/collect_baci.py`: CEPII BACI bulk ZIP (open license), product-level (HS6) bilateral
trade. Download once into `Data/raw/baci/`; build (a) yearly signed bilateral totals
(cross-check vs IMTS totals — print reconciliation), (b) per-pair product-overlap measures:
COMPLEMENTARITY (i exports what j imports, cosine of i's export vector vs j's import vector)
and COMPETITION (i and j export the same products to third markets, cosine of export vectors
to common destinations). Write `baci_edge_vintages` (availability = year-end + 24 months —
BACI's real lag; verify from the release notes and record).
## Step 2 — the G2 orthogonalization gate (the go/no-go)
For the EXISTING trade-gap signal: partner-weighted 1m returns minus own + global + regional
momentum (regress cross-sectionally per month, expanding), pooled IC t-stat on the residual
predictor, 2000→present, monthly. Pooled t ≥ 2 → proceed. Else CANCEL per above.
## Step 3 — two-sided transmission test (#15; only after Step 2 passes)
For horizons {5d, 21d, 63d} × eras {2003-13, 2014-23, 2024-26}: sign and magnitude of the
neighbor-gap → return relation (convergence vs continuation), per edge family
(trade/bank/holder), yearly IC table + regime split by the WP-06 GSTATE columns. Output:
`experiments/flagship_transmission/results/RESULTS.md` — a MAP, not a trial (no new
registrations from this step without opus review).
## Step 4 — edge-composition hypothesis (#16)
Split the trade-gap signal by BACI edge type: does transmission differ across
COMPLEMENTARITY vs COMPETITION edges? If the split separates (|ΔIC| ≥ 0.02, both n
sufficient), ONE registration `H_COMP_001` (family network_spillover), direction from the
split, embargo ≥1d, pre-committed kill: OOS interaction gain < 0.01.

## SONNET/OPUS boundary
All builds and computations Sonnet; Step 3's interpretation and any Step 4 verdict are
OPUS-REQUIRED. Steps 3–4 reports go to Arjun before anything else is built on them.

## Gate
Per step: BACI totals vs IMTS reconciliation printed (correlation of log totals ≥ 0.9
expected); Step 2 pooled t printed with its window count; RESULTS.md complete with computed
numbers only. Baseline tests.

## Commit template
`WP-11: BACI edges + flagship transmission map — G2 gate {passed t=X|failed, territory downgraded}`
