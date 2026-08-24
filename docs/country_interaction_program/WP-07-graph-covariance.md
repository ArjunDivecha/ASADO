# WP-07 — Graph-target covariance shrinkage  [Phase 1 | SONNET-SAFE | methodology ledger]

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
Methodology experiment (NOT a signal; NOT a family trial): does a Ledoit-Wolf shrinkage
TARGET built from graph edge intensity beat the constant-correlation target for the 34-country
covariance? Pays sign-agnostically (paper-book construction, severity normalization).

## Design (fixed)
- Experiment dir: `experiments/graph_cov_shrinkage/` (all writes stay inside).
- Returns: monthly, from the loop DB / T2 surface (1MRet realized panel), 2000→present.
- Targets compared: (a) LW constant-correlation (baseline), (b) graph target: correlation
  proportional to normalized symmetric trade+bank edge weight as-of each estimation date
  (PIT via `graph_edge_intervals`), shrunk LW-optimally, (c) 50/50 blend.
- Protocol: expanding window, min 60 months; each month t estimate Σ on data ≤ t, score on
  month t+1: (i) log-likelihood of realized cross-section, (ii) realized volatility of the
  minimum-variance portfolio (long-only, w ≥ 0, monthly rebalance, GROSS — no cost penalties
  ever), (iii) Frobenius distance to next-12m realized Σ.
- Output: `experiments/graph_cov_shrinkage/results/RESULTS.md` with the three metrics ×
  three targets, full period + 2008 + 2020 subwindows, plus a one-line verdict template:
  "graph target {beats|ties|loses to} constant-correlation on {k}/3 metrics."

## Verdict handling (SONNET boundary)
Sonnet computes and reports the table; it does NOT write the methodology-ledger entry.
STOP after RESULTS.md and flag for opus/Arjun review — the ledger entry and any adoption
decision are OPUS-REQUIRED.

## Gate
`results/RESULTS.md` exists with all 9 cells filled from computed numbers (no placeholders);
the run log shows every window scored; baseline tests untouched (no production files edited).

## Commit template
`WP-07: graph-target covariance shrinkage experiment — results only, no adoption`
