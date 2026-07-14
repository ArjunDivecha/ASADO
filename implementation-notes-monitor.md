# implementation-notes-monitor.md (Build Mode bookkeeping — NOT a deliverable)

Contract: FAMILY-IC-MONITOR-001. Branch: exp/family-ic-monitor. Worktree has no
venv; all commands use the absolute production venv python
`/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/venv/bin/python`.

## Preflight estimate (presented before flipping budget.preflight_estimate)

- Module + roster + tests + review audit + docs: ~1,000 lines new code, ~0
  external deps (imports harness + loopdb helpers already in venv).
- Build gates G1/G2/review are synthetic-only → seconds to run, no live DB, no
  network, quiet window (06:00–08:30 PT) untouched automatically.
- G3/G4 are permissioned, operator-run against production Data/ (symlinked per
  reverdict_v4 pattern); I resolve their commands and prove well-formedness via
  --dry-run + --help only (never executed here).
- Risk items surfaced to team-lead (below); none block the build gates.
- Estimate: COMPLETE within the 30-turn / 3-consecutive-failure budget on the
  first build turn.

## AUTHOR AMENDMENTS (applied verbatim per team-lead ruling, 2026-07-14)

**AUTHOR AMENDMENT 1 (2026-07-14) — amended INV4 + two-roster design.** Rationale
(author): the +/-0.005 per-year tolerance was authored without validating
achievability, and the a6 generator was never committed (author defect; logged as
the contract lesson "reference artifacts must be committed WITH their generating
script"). INV4 now has four binding clauses on the FROZEN 16-member roster
(ref16_frozen): (i) corr>=0.95 vs a2 monthly; (ii) per-year +/-0.012 vs a6;
(iii) 2012-2023 mean +/-0.001 of a6's +0.0123; (iv) post-2024 mean<0. bet.observable
and G3.must_assert updated to match. Two-roster design added to Context: each family
stores series under a `roster` column -- `book_2026_07_14` (role=gate; the Alpha Book
WATCH tier the R-A gate runs on) and `ref16_frozen` (role=inv4_reference; a6's 16, INV4
only). The gate/INV5 code runs on the book roster; INV4 runs on ref16_frozen. Applied to
spec INV4.holds/check_intent, bet.observable, G3, Context; roster JSON restructured;
module + tests updated.

**AUTHOR AMENDMENT 2 (2026-07-14) — governance_contract.yaml in scope.** Rationale
(author): a loop step unregistered in the governance contract degrades governance
observability; registration belongs to the same go-live as the wiring. Added
`config/governance_contract.yaml` to scope.in; registered the family_ic_monitor step
(exactly one entry, optional: true); dropped G2 deselect #1 (test_run_manifest now green).
The review audit asserts the yaml change is a single-entry addition. Deselects #2/#3
(harness-v4's merged review audit) stay -- author is fixing those branch-aware on main.
This contract's OWN review audit is branch-scoped from the start (skips off
exp/family-ic-monitor). CONTRACT LESSON added: "contract review audits must be
branch-scoped or they haunt every later contract's G2."

## Deviations / decisions logged

**D1 — a6 known-answer reference reproducibility (surfaced to team-lead).**
The a6 generating script was never committed (commit cdcd9a4 added only
a6_lag1_family_ic.json + a USER_FIX_LIST note). Read-only reconstruction from
the committed a2 machinery + frozen snapshot (Data/work/experiments/flip_autopsy/
snapshot_2026_07_13, main checkout) established: a6 is lag-1; the faithful
construction (equal-weight mean of per-member sign-aligned monthly rank-ICs,
harness-v4 honest clock, per-member 5d, member universes) matches a6's pre-2024
mean to 5dp (0.01231 vs 0.01228) and corr 0.9517 vs a2 monthly, but per-year
worst |delta| vs a6 ~0.011 (≈12/27 yrs > 0.005) EVEN on the identical snapshot.
Decision: ship the faithful construction; implement INV4 with the contract's
literal thresholds as documented module constants; print full diagnostics; do
NOT weaken silently. Recommended author-side fix (msg sent): relax per-year tol
to ~0.012, or make the binding check corr≥0.95 vs the reproducible a2 series.

**D2 — roster frozen to the pre-v4 16, not the live 12 (surfaced).** The live
post-harness-v4 ledger lists 12 WEAK/WATCH GRAPH/LL/SIM variables; a6 used 16
(v4 demoted 4 to DEAD on 2026-07-14). To reproduce a6 the v1 roster is FROZEN to
those 16 in scripts/loop/family_ic_roster_v1.json (documented `provenance`).

**D3 — governance_contract.yaml scope gap + G2 deselects (surfaced, decision
pending).** tests/loop/test_run_manifest.py::test_real_contract_loads_and_matches_steps
requires every loop_daily_job STEPS name to be in config/governance_contract.yaml.
Adding the required `family_ic_monitor` step breaks it, but config/governance_
contract.yaml is not in scope.in and editing it violates the Divecha subset check.
G2 therefore deselects that node (go-live config change, out of scope) plus the
two failing tests/test_review_audit_v4.py nodes (harness-v4's own merged review
command; its scope.forbid lists scripts/loop/** so it flags my in-scope files;
its post-merge skip doesn't fire in a sibling worktree because production
advanced main by a nightly-brief commit after branch-cut). Recommended: add
config/governance_contract.yaml to scope.in to drop deselect #1. With deselects:
309 passed, 2 skipped, exit 0.

**D4 — fail-soft exit code.** nightly_step catches all exceptions, logs loudly,
returns exit 2 (PARTIAL) never exit 1, so the loop treats a monitor crash as a
warning (INV2). This holds even though config/governance_contract.yaml can't be
edited to mark the step optional — the exit-2 discipline is self-contained.

**D5 — no main-DB attach needed for compute, but daily returns require it.**
Member signal tables + country_returns_monthly are loop-owned; daily marking
returns come from asado.t2_factors_daily (main, attached read-only by
loop_connection). So the live path uses loop_connection(); tests inject
synthetic loaders + a temp DuckDB and never open real DBs.

## Read-only reconstruction scripts (scratchpad, not committed)
- /private/tmp/.../scratchpad/recon_a6.py, frozen_roster.json — a6 methodology
  reconstruction + roster extraction. Never wrote to any repo DB.

## Turn 3 — merged main; G2 now zero deselects
Merged main (b358d50), which branch-scoped the harness-v4 review audit to
exp/harness-v4 (skips here). With that + the AMENDMENT 2 step registration, G2 is
the FULL suite with ZERO deselects. My own review audit remains branch-scoped to
exp/family-ic-monitor.

## Gate/verification results (final)
- G1: tests/test_family_ic_monitor.py → 35 passed.
- G2: full suite, ZERO deselects → 314 passed, 4 skipped (2 harness-v4 + 2 pre-existing), exit 0.
- review: tests/test_review_audit_monitor.py → 4 passed (scope, forbid, single-entry yaml, invariant coverage).
- validator: DIVECHA_CONTRACT_VALID mode=build.
- G3/G4: --dry-run (backfill + verify-idempotent) exit 0, --help exit 0 — well-formed, not executed.
