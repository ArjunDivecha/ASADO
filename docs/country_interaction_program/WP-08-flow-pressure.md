# WP-08 — `flow_pressure` family: registry, TIC monthly edge, JLR signal  [Phase 2 | SONNET builds, OPUS interprets]

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
First trial of the forced-flow mechanism (Jotikasthira-Lundblad-Ramadorai, JF 2012): when a
HOLDER country is stressed, its funds are forced sellers in the countries they own —
pressure, then reversal. Economically distinct from return diffusion (predicts
pressure-then-REVERSAL, not drift). New canonical family.

## Step 1 — family registry (change-control; this WP is the approval record)
`config/family_registry.yaml` is a git-tracked trust root (dirty = scorecard RED, so edit
and commit in ONE session). Add after the `network_spillover` block (anchor on its
`variable_prefixes: ["GRAPH", "LL_", "SIM_"]` line, count==1):
```yaml
  flow_pressure:
    description: "Forced-flow pressure through common holders (JLR 2012): holder-country stress x ownership weights predicts pressure then reversal in the held country. Mechanism distinct from network_spillover (flows, not information diffusion)."
    variable_prefixes: ["FLOWP_"]
```
Also append to the file's header comment block: `Standing rule (2026-08-24): any
diffusion-flavored variant ("neighbors moved, endpoint reprices") charges network_spillover
regardless of construction; flow_pressure and external_balance are reserved for genuinely
distinct mechanisms.` Then run whatever registry validation exists
(`scripts/qa/validate_variable_registry.py` and the scorecard check) before committing.

## Step 2 — TIC monthly holder edge (near-free; data already on disk)
`Data/processed/bilateral_portfolio_matrix.parquet` already contains monthly US TIC rows
(excluded from the PIT holder vintages, which keep only imf_pip). New script
`scripts/loop/build_tic_holder_edge.py`: extract the US→country monthly holdings series,
stamp availability = month-end + 45 days (TIC publication lag — verify against the raw file
dates in `Data/raw/bilateral/us_tic` and RECORD the measured lag in the header), write loop
table `tic_holder_edges(date, available_at, holder, country, amount_usd, share)`.

## Step 3 — the signal, pre-registered EXACTLY as follows (Sonnet copies, never adjusts)
Variable `FLOWP_PUSH_63D`, monthly, per country C:
  FLOWP_PUSH_63D(C, m) = Σ over holder countries H of
      [ z(H's 63d equity return, 3y window, NEGATED — stress is positive) ]
      × [ holder weight H→C from `graph_edge_intervals` (holder edges), as-of month m ]
  normalized cross-sectionally (z across the 34 countries, guard zero-dispersion → NaN).
Registration (via the pre-registration path `evaluate_signal.py` enforces — read its header
for the exact mechanism; hypothesis IDs `H_FLOWP_001a/b`):
- family `flow_pressure`; universe: the 31-country harness set; embargo ≥ 1 trading day.
- **H_FLOWP_001a (pressure leg)**: direction higher_is_worse (high push exposure → negative
  return), horizons 5d and 21d.
- **H_FLOWP_001b (reversal leg)**: direction higher_is_better at 63d AFTER a 21d formation
  lag (the JLR reversal window).
- Kill criteria (pre-committed): |IC| < 0.01 or nw_t < 2 at ALL horizons on both legs → DEAD;
  spanned by `ETF_FLOW_21D_Z` (existing contrarian flow signal — run the spanning check in
  `scripts/harness/ff_spanning.py` style against it) → DEAD regardless of IC.

## SONNET/OPUS boundary
Sonnet: registry edit, TIC builder, signal builder (`scripts/loop/build_flow_pressure.py`,
writes `flow_pressure_monthly`), registration, harness run. Then STOP. The verdict, its
ledger entry, and any combiner/book decision are OPUS-REQUIRED.

## Gate
Registry validation green + scorecard not RED from this change; TIC edge table row counts
and lag printed; signal table: ≥ 25 countries covered from 2005+, zero infinities, NaN only
where holder coverage genuinely absent; harness run completes and writes its JSON.
Baseline tests.

## Commit template
`WP-08: flow_pressure family — TIC monthly edge, JLR push signal, pre-registered trials`
