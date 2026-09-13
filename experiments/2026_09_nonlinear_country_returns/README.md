# ASADO Nonlinear Country-Return Study

**Spec:** `ASADO_NL_20260913_V1` (vendored agent pack under `spec/`; MANIFEST.sha256 PASS)
**Branch:** `exp/Nonlinear` (worktree `ASADO-exp-Nonlinear`, base `a8a8699`)

## Question

Does a pre-specified, pooled nonlinear model (depth-2/≤4-leaf histogram boosting on a
fixed 16-input economic representation) predict **20-local-session** forward country
equity returns better than independently tuned ridge baselines — using exactly the same
point-in-time-safe observations?

## Status

- [x] P00 repository & governance reconciliation — `governance/reconciliation.md` (PASS)
- [ ] P01 data readiness & source snapshot
- [ ] P02–P13 per `spec/implementation_backlog.json` (P12/P13 optional)

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
