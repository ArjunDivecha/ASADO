# ASADO Nonlinear Country-Return Study

**Spec:** `ASADO_NL_20260913_V1` (vendored agent pack under `spec/`; MANIFEST.sha256 PASS)
**Branch:** `exp/Nonlinear` (worktree `ASADO-exp-Nonlinear`, base `a8a8699`)

## Question

Does a pre-specified, pooled nonlinear model (depth-2/≤4-leaf histogram boosting on a
fixed 15-input economic representation, per amendment AM-1) predict **20-local-session** forward country
equity returns better than independently tuned ridge baselines — using exactly the same
point-in-time-safe observations?

## Status

- [x] P00 repository & governance reconciliation — `governance/reconciliation.md` (PASS)
- [x] P01 data readiness — `governance/data_readiness.md`; strict spec was
  BLOCKED_DATA (24-primitive ceiling = 15 markets < 20 floor). Owner-approved
  **amendment AM-1** (`governance/amendment_AM1.md`): drop P07/P08 bank-neighbor
  primitives + P11 (3M RR doesn't exist) → 21 primitives, 15-input S,
  22-market universe, ≥20 eligible from 2010-07.
- [x] P02 calendars & labels — `audit/P02_gate.json` (PASS). Independent
  session calendar from TRI mark changes (weekday sessions only; the
  warehouse `daily_calendar` is a presence flag and was rejected as session
  authority). 6,765 candidate origins (≥20 sessions), 148,830 h20 rows,
  440 CENSORED_TAIL preserved. Two-stage reconciliation vs harness `20DRet`:
  same TRI source (median diff 2.5e-7; 0.43% vintage tail, Indonesia Mar-2020),
  clock difference is structural (20 padded-grid-rows ≈ 14 sessions vs our
  20 sessions). Candidate origins are a *superset* — feature eligibility
  (≥20 markets) is enforced at P04.
- [x] P03 causal features + S — `audit/P03_gate.json` (PASS). 21 primitives
  on five natural axes (session / FX-source-day / GLOBAL / graph-daily /
  consensus-origin), trailing-z per §7.5 (252 obs excl. current, min 126,
  clip ±3). Graph impulse rebuilt from `graph_edge_vintages` over ALL 31
  trade neighbors (U.S. ~18% of outbound weight — truncating to the
  universe was found and fixed). Consensus target F = year(origin)+1, tol
  0.049pp; P20 uses full F-history (no-event rows are not dropped).
  89,616 complete rows; ≥20 eligible markets on 3,403 origins from
  2012-01-20 (P01's 2010-07 + z burn-in).
- [ ] P04–P13 per `spec/implementation_backlog.json` (P12/P13 optional)

## Layout

- `spec/` — the vendored agent pack (PRD, backlog, acceptance tests, templates). Read-only.
- `governance/` — P00 deliverables: `reconciliation.md`, `source_map.json`,
  `governance_binding.json`, `environment.lock`.
- `results/` — populated at P11 (verdict + reproduction bundle).
- Scratch/snapshots: `Data/work/experiments/nonlinear_country_returns/` in the **main**
  checkout (the worktree has no `Data/loop` or `Data/work` — see reconciliation §2.2).

## Non-negotiables

- No real outer IC/Sharpe/rankings before P06 registration (methodology ledger,
  `register_methodology_experiment`) and the execution lock.
- Labels are built independently from TRI levels — never from `20DRet`/`1DRet`
  (forward labels, blacklisted).
- A valid negative is a successful delivery. Failed fit-support gates block; nothing
  is silently substituted or shortened.
- Prior exposure declared: MacroState M_20260906_001–003 (WATCH) is the same idea
  family under a different contract — this study is neither its duplicate nor fresh
  confirmation of its numbers.
