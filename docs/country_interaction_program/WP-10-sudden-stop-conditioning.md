# WP-10 — Sudden-stop partner conditioning  [Phase 2 | SONNET-SAFE, one gated trial]

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
Forbes-Warnock episode logic as a CONDITIONING column: flag countries whose largest
trade/bank partners are currently in a gross-inflow stop episode. Context tier first;
exactly one registered interaction trial, and only if the conditional split separates.

## Steps
1. `scripts/loop/build_sudden_stop_flags.py`: episode definition (Forbes-Warnock standard):
   partner H is in a STOP when its 4q rolling gross inflow (use the existing external/flow
   surfaces — BIS inbound claims delta from `graph_edge_intervals` bank edges as the
   available proxy; document the proxy choice in the header) falls > 1 std below its 5y
   mean for ≥ 2 consecutive quarters. Output loop table
   `sudden_stop_daily(date, country, value)` where value = PIT-weighted share of C's top-5
   partners currently in STOP (weights as-of via intervals).
2. Context wiring: add the column to the brief context section and make it citable by
   Layer 2. NO combiner, NO detector yet.
3. **The one trial (gated)**: compute the unconditional IC of the EXISTING
   `GRAPHP_TRADE_NBR_RET_GAP_21D` (5d horizon) split by `sudden_stop_daily > 0.4` vs below.
   If |IC_high − IC_low| ≥ 0.02 with both n ≥ 500 days: register interaction hypothesis
   `H_NS_INTERACT_001` (family: network_spillover — it conditions a diffusion signal;
   charges the N), direction per the split's sign, embargo ≥1d, kill: interaction IC gain
   < 0.01 out-of-sample. If the split does NOT separate: record the numbers in the WP report
   and STOP — no registration, no trial charge.

## Gate
Episode flags: 2008-Q4/2009 and 2020-Q1/Q2 must show elevated STOP share (print top
episodes); series spans 2003+; split table printed with n, IC, t per side. Baseline tests.

## Commit template
`WP-10: sudden-stop partner exposure — context column; interaction trial {registered|not warranted}`
