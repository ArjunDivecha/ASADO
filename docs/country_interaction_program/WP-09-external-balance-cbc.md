# WP-09 — `external_balance` family: trade-imbalance centrality (CBC)  [Phase 2 | SONNET builds, OPUS interprets]

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
First trial of Hou–Sarno–Ye (JFE 172, Oct 2025): centrality on the SIGNED trade-imbalance
network predicts currency excess returns. Mechanism: external-balance positioning, not
return diffusion → new family.

## Step 1 — family registry (same protocol as WP-08 Step 1; can share one commit if both run)
```yaml
  external_balance:
    description: "Signed trade-imbalance network centrality (Hou-Sarno-Ye JFE 2025): who runs deficits into whom predicts currency excess returns. External-balance positioning, not diffusion."
    variable_prefixes: ["XBAL_"]
```

## Step 2 — signed imbalance matrix WITHOUT touching any collector
The raw IMTS pull already keeps exports and imports separately
(`collect_bilateral.py` merges `exports_usd`/`imports_usd` per (reporter, counterpart,
year) — see its `XG_FOB_USD`/`MG_CIF_USD` handling). New script
`scripts/loop/build_imbalance_matrix.py`: rebuild the SIGNED matrix
A[i,j] = exports(i→j) − imports(i←j) per year from the same raw source the processed matrix
came from, vintage-stamp availability = year-end + 91 days (match the trade lag measured in
`graph_edge_vintages`), write loop table `imbalance_edge_vintages` (same schema as
graph_edge_vintages + signed weight). DO NOT modify `collect_bilateral.py` or
`collect_pit_edges.py` — extending the live collector is a flagged follow-up for Arjun
(USER_FIX_LIST protocol), not part of this WP.

## Step 3 — CBC, pre-registered EXACTLY
Per the paper's eq. 24 (Katz-Bonacich on the transposed imbalance matrix blended with the
return covariance): implement
  CBC = [wI + (1−w)V] (I − αA₀′)⁻¹ (A₀′ − A₀) ℓ
with FIXED parameters w = 0.52, α = 0.68 (the paper's calibration — do NOT tune; a tuned
version is a separate future trial), V = 60m FX/equity return correlation matrix (PIT,
expanding), A₀ = row-normalized signed imbalance as-of date, ℓ = ones.
Variables: `XBAL_CBC` (monthly, per country, cross-sectional z).
Registrations (IDs `H_XBAL_001a/b`):
- **H_XBAL_001a — FX leg (primary)**: target = 1M currency excess return vs USD (from the
  T2 Currency surface), direction: higher CBC → higher subsequent currency excess return
  (the paper's sign — verify against the paper's Table direction before running; if
  ambiguous in implementation, STOP and report rather than guess), horizon 21d, embargo ≥1d.
- **H_XBAL_001b — equity leg (secondary, runs ONLY if 001a is not DEAD)**: same signal,
  1MRet target.
- Kill: spanned by FX carry (`FXCRR`-derived surface) or the dollar factor → DEAD;
  |IC| < 0.01 everywhere → DEAD; IMTS imbalance coverage < 25 countries → INSUFFICIENT.

## SONNET/OPUS boundary
Sonnet builds and runs; verdict + ledger + any expression work are OPUS-REQUIRED. Note in
the report whether monthly IMTS (annual data, interpolation forbidden — step function only)
leaves enough signal variation; if XBAL_CBC changes value for < 10% of months, flag it.

## Gate
Imbalance matrix antisymmetry check (A[i,j] ≈ −A[j,i] where both reported; print the
reconciliation rate — IMTS mirror-data disagreement is expected, report it, median |diff|/level);
CBC series finite, 25+ countries, 2003+; harness JSONs written. Baseline tests.

## Commit template
`WP-09: external_balance family — signed imbalance vintages, CBC signal, FX-leg trial`
