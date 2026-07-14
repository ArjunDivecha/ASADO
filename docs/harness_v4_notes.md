# Harness v4 — honest daily execution clock

Contract: `HARNESS-V4-HONEST-LEDGER-001`. Status: built in worktree
`ASADO-exp-harness-v4` (branch `exp/harness-v4`); awaiting old-vs-new verdict
review + Arjun's merge approval before it becomes the honest ledger baseline.

## What changed and why

**Problem (v3).** For DAILY signals from `ZERO_LAG_SOURCES` (`t2`, `gdelt`,
`graph`, the three optimizer sources) the forward-return window opened at the
signal's own close (`align_daily` with `lag_days=0`). On 34 markets whose
closes are hours apart, that convention embeds same-close execution plus a
timezone echo. With the cost gate retracted (v3, 2026-07-13), nothing suppressed
echo-inflated daily signals from reaching WATCH — measured family IC roughly
halved when the window instead opened one close later.

**Fix (v4).** A minimum **1-trading-day execution embargo** now applies to every
daily-frequency evaluation, including zero-lag sources. Publication lag (when
the data is knowable) and execution embargo (the earliest close you can trade)
are distinct; instantaneous publication does not make same-close execution real.

- `daily_publication_lag_days(...)` is **unchanged** — it still reports the true
  publication lag (0 for market-derived sources). The existing PIT tests
  (`tests/loop/test_pit_lag.py`) that assert this stay green.
- New `effective_daily_lag_days(...)` = `max(publication_lag,
  MIN_DAILY_EXECUTION_EMBARGO_DAYS=1)`. `evaluate_signal`'s daily path (both the
  IC alignment and the portfolio path) now uses this. The effective lag is
  therefore `>= 1` for every daily eval, even for an explicit
  `publication_lag_days: 0` override.
- `align_daily` is **unchanged** (so the legacy lag-0 window remains callable for
  the regression contrast). Monthly logic is entirely untouched.

**Self-describing results (INV7).** Every result JSON now carries an
`execution_convention` block: `{lag_days_effective, window_open_rule, frequency,
harness_version}`. Archived runs are no longer ambiguous about the clock they
were measured on.

## Re-verdict

`scripts/harness/reverdict_v4.py` re-evaluates all 59 pre-registered hypotheses
through the `evaluate_signal` front door with their existing ids (never
`sweep_signals --force`, never a new registration), preserving each family's
deflated-Sharpe trial count `N`. It writes an old-vs-new verdict table
(`summary.parquet` + `.xlsx`) and a manifest under
`Data/loop/harness_runs/reverdict_v4_<date>/`, and runs an INV4 ledger-integrity
check. It is the contract's permissioned gate (G3) — run by an operator after
approval, outside the 06:00–08:30 PT nightly window. `H_20260610_001` (`12MRet`,
a forward-return lookahead) is correctly refused by the blacklist and recorded
as `REFUSED_BLACKLIST`.

`scripts/harness/check_convention_labels.py` (gate G4) verifies every result JSON
from the sweep carries a valid `execution_convention` block, and reports
"G3 not yet run" when the sweep output is absent.

## What this does NOT prove

Passing the gates proves the measurement is now honest and the re-verdicts
completed with ledger integrity. It does **not** prove any signal is good or that
the new verdict tier contains tradeable alpha — that is a human judgment on the
old-vs-new table, and ultimately on whether decisions made on the v4 ledger stop
being retracted.
