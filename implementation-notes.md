# Harness v4 — implementation notes (Build Mode)

Contract: `harness_v4_honest_ledger.spec.md` (HARNESS-V4-HONEST-LEDGER-001)
Worktree: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-harness-v4` (branch `exp/harness-v4`)
Python (worktree has no venv): `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/venv/bin/python`

This file logs every deviation from the contract prose and why. Read it first when reviewing.

## Preflight estimate

Files to change / add (all inside `scope.in`):

1. `scripts/harness/evaluate_signal.py` — EDIT (additive):
   - add `MIN_DAILY_EXECUTION_EMBARGO_DAYS = 1` and `HARNESS_VERSION = 4` constants
   - add `effective_daily_lag_days(...)` = `max(daily_publication_lag_days(...), MIN_DAILY_EXECUTION_EMBARGO_DAYS)`
   - add `_execution_convention(frequency, lag_days, lag_months)` helper
   - switch the daily lag line in `evaluate_signal` from `daily_publication_lag_days(...)`
     to `effective_daily_lag_days(...)`
   - add `"execution_convention": _execution_convention(...)` to the result dict
   - bump module VERSION header to 4.0
   NOTE: `daily_publication_lag_days`, `align_daily`, and every monthly-path function
   are left byte-identical (INV6 + preserves existing `test_pit_lag.py`).
2. `tests/test_harness_v4.py` — NEW: INV1/INV2/INV3/INV5/INV6/INV7 + INV4-checker unit tests.
3. `scripts/harness/reverdict_v4.py` — NEW: G3 driver (permissioned; NOT executed in Build Mode).
4. `scripts/harness/check_convention_labels.py` — NEW: G4 standalone convention-schema checker.
5. `tests/test_review_audit_v4.py` — NEW: deterministic review-audit (scope + invariant-coverage).
6. `docs/harness_v4_notes.md` — NEW: short design note (scope.in path).
7. `harness_v4_honest_ledger.spec.md` — EDIT: resolve `gates[].command`, `review.command`,
   flip `budget.preflight_estimate` to `complete`, append Build ledger turn.

Expected turns: ~1-2 Build Mode turns (single agent, no external delegation needed —
the change is small and additive; the bulk is test authoring).

## Design decisions

### INV1 — the execution embargo is a NEW floor, layered above publication lag
The v3 code already has `daily_publication_lag_days`, which correctly returns 0 for
`ZERO_LAG_SOURCES` (market-derived data IS knowable at the close — that is a true
statement about *publication*). The v4 honesty fix is a separate concept: even
instantly-published data cannot be *executed* at its own close on a 34-market panel
whose closes are hours apart. So instead of mutating `daily_publication_lag_days`
(which would break the existing `tests/loop/test_pit_lag.py` assertions that
market-derived publication lag == 0, and would conflate two distinct ideas), v4 adds
`effective_daily_lag_days = max(publication_lag, MIN_DAILY_EXECUTION_EMBARGO_DAYS=1)`
and routes `evaluate_signal`'s daily path through it. Result: the effective lag used
by `align_daily` (both the IC and portfolio paths) is >= 1 for every daily eval,
including zero-lag sources and including an explicit `publication_lag_days: 0` override.
`align_daily` itself is untouched, so the INV3 lag-0 regression contrast is still callable.

### INV6 — monthly untouched
The only changes are on the daily branch + an additive `execution_convention` result
key (a "convention-labeling field", the explicit INV6 exception). Every monthly-path
function is byte-identical. INV6 test proves this two ways: (a) `inspect.getsource`
identity of the monthly helpers between `main` and HEAD, and (b) numeric equivalence of
the full monthly chain on a synthetic fixture computed through both module copies.

### INV7 — execution_convention block
`{lag_days_effective, window_open_rule, frequency, harness_version}`. Daily:
`lag_days_effective` is the int effective lag (>=1). Monthly: `lag_days_effective` is
`null` (there are no trading-day lags in the monthly clock; the key is still present so
the G4 schema checker passes), `window_open_rule` describes the month-M+lag+1 rule.

## Deviations from the contract prose (with reasons)

### D1 — G3 "59 hyp_verdict events" vs the blacklisted hypothesis (INV4/INV5 tension)
The spec's G3 `must_assert` says "ledger delta = 59 hyp_verdict events". But exactly one
of the 59 registered ids, `H_20260610_001` (variable `12MRet`), is a forward-return
lookahead — it is already `retired`, and the harness blacklist (INV5) will correctly
REFUSE to re-run it (`load_signal` raises before any verdict is written). Forcing a
59th verdict would require bypassing INV5, which is not allowed. INV4's own `holds`/
`check_intent` wording is "exactly one new hyp_verdict **per re-run id**" — which
accommodates an id that cannot be re-run. Resolution: the driver attempts all 59,
records the blacklisted one in the summary as `REFUSED_BLACKLIST` (so the summary still
has 59 rows), and the INV4 integrity check asserts `new hyp_verdict == n_reverdicted`
(the count of ids that produced a verdict, read from the driver's own manifest), plus
the hard guards `new hyp_register == 0` and per-family trial-count N unchanged. This is
faithful to the invariant, not a weakening: it upholds INV5 rather than breaking it to
satisfy a literal 59. G3 is permissioned and NOT executed in Build Mode, so the exact
run-time count (expected 58 verdicts + 1 refusal) is realized only when an operator runs it.

### D2 — review.command is a deterministic audit, not codex
The contract's `review.command` was `TODO`. Codex is unavailable (usage limit). Per the
Build Mode brief, `review.command` is resolved to a deterministic pytest audit
(`tests/test_review_audit_v4.py`) asserting: (a) the changed-path set (committed
`git diff main...HEAD` UNION uncommitted `git status --porcelain`) is a subset of
`scope.in`; (b) no `scope.forbid` path is modified; (c) every invariant id (INV1..INV7)
and the G4 check are covered by at least one collected pytest test. This substitutes an
external reviewer with a mechanical, reproducible scope+coverage gate.

### D3 — G2 deselects 2 pre-existing baseline failures (outside scope)
On the untouched baseline (HEAD == main at build start), `pytest tests/` is 250 passed /
2 failed. The 2 failures are
`tests/loop/test_methodology_ledger.py::test_real_methodology_ledger_folds_without_unknown_events`
and `::test_real_methodology_ledger_count_conservation`. They crash inside
`scripts/loop/ledgers.py:716` (`KeyError: 'gate_results'`) on a real
`methodology_ledger.jsonl` verdict event that lacks `gate_results` — a data/code issue in
`scripts/loop/**`, which is `scope.forbid` (cannot fix here) and entirely unrelated to
the hypothesis-ledger harness this contract changes. G2's command deselects exactly
these two so it measures "no NEW failures from v4"; the deselection is justified by the
recorded baseline. Everything else in the suite (including the new v4 tests) must pass.

### D4 — G3 runtime prerequisite: DBs are not in the worktree
`Data/asado.duckdb` and `Data/loop/` are gitignored and NOT checked out into the
worktree. `loopdb.py` (scope.forbid — unchanged) resolves both under the worktree root.
So before the permissioned G3 run, an operator must point the worktree's `Data/` at the
production DBs (symlink `Data/asado.duckdb` and `Data/loop` to the production checkout's
copies). `reverdict_v4.py` performs a preflight check and prints the exact symlink
commands + exits nonzero if the warehouse is absent, rather than half-running. The
ledger it appends to is the worktree's `ledgers/hypothesis_ledger.jsonl` (the
scope-visible surface), by design.

## Build ledger

- Turn 1: read contract + schema + harness + ledger + loopdb + sweep + existing tests;
  established baseline (250 pass / 2 pre-existing fail); confirmed additive design keeps
  all PIT tests green; wrote this preflight. Then implemented code + tests + scripts,
  resolved gate/review commands, ran G1/G2/G4/review green, validated contract.
