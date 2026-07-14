---
schema_version: 1
spec_id: HARNESS-V4-HONEST-LEDGER-001
status: draft
target_agent: either

scope:
  in:
    - scripts/harness/**
    - tests/**
    - ledgers/hypothesis_ledger.jsonl
    - docs/harness_v4_notes.md
  out:
    - scripts/loop/**
    - cos_mockups/**
    - experiments/**
  forbid:
    - config/family_registry.yaml
    - config/country_mapping.json
    - config/sweeps/**
    - Data/processed/**
    - scripts/loop/**
    - scripts/monthly_update.py
    - scripts/daily_update.py
    - venv/**
    - "**/.env*"
    - "**/CLAUDE.md"
    - .claude/**

bet:
  if: "the harness measures every DAILY signal with a minimum 1-trading-day execution embargo (zero-lag-source exemption removed for the forward-return window), proves its measurement layer on known-answer fixtures, and re-verdicts all 59 registered hypotheses through the front door with their existing ids"
  then: "the ledger's verdict tier is free of same-close/timezone-echo inflation and every result JSON is self-describing about its execution clock"
  observable: "a planted pure-echo fixture scores |IC| < 0.005 under v4 daily conventions while the same fixture scores > 0.015 under the v3 lag-0 convention (regression proof); a planted-IC fixture is recovered within tolerance; the ledger gains exactly one fresh hyp_verdict event per existing hypothesis id and zero hyp_register events"

invariants:
  - id: INV1
    holds: "no daily signal's forward-return window opens at the signal's own close: effective lag_days >= 1 for every daily-frequency evaluation regardless of source, including ZERO_LAG_SOURCES"
    check_intent: "unit test constructs a daily evaluation for a zero-lag source and asserts the resolved lag_days >= 1 and the aligned window start strictly exceeds the signal date position"
  - id: INV2
    holds: "known-answer recovery: a synthetic panel with a planted cross-sectional IC of known magnitude is recovered by the harness within +/-20% at the planted horizon"
    check_intent: "fixture generates returns and a signal correlated at a chosen rank-IC; harness IC estimate must land inside the tolerance band"
  - id: INV3
    holds: "echo exclusion: a signal equal to other-countries' same-day returns (pure timezone echo, no forward information) scores |mean IC| < 0.005 under v4 daily conventions"
    check_intent: "echo fixture built from lagged cross-market same-day returns; assert near-zero v4 IC AND assert the same fixture scores materially positive (> 0.015) when evaluated with the old lag-0 window, so the test proves the discrimination not just the null"
  - id: INV4
    holds: "ledger integrity: re-verdicting uses existing hypothesis ids only; hyp_register event count stays exactly 59; per-family trial counts N are unchanged so deflated-Sharpe accounting is preserved"
    check_intent: "checker script parses the ledger before/after the sweep: 0 new hyp_register events, exactly one new hyp_verdict per re-run id, family N unchanged"
  - id: INV5
    holds: "the forward-return blacklist still refuses NMRet/NDRet-family predictors"
    check_intent: "regression test registers nothing but attempts evaluation of a blacklisted variable and asserts the harness raises/refuses"
  - id: INV6
    holds: "monthly-frequency verdict behavior is byte-identical to v3 except for the new convention-labeling fields (monthly embargo logic untouched)"
    check_intent: "run one monthly hypothesis re-evaluation under v3 and v4 code on frozen inputs; IC/NW-t/verdict fields must match exactly"
  - id: INV7
    holds: "every result JSON written by v4 is self-describing: it contains execution_convention fields (lag_days_effective, window_open_rule, frequency, harness_version >= 4)"
    check_intent: "schema checker over newly written harness_runs JSONs exits nonzero if any convention field is missing"

gates:
  - id: G1
    intent: "measurement-layer known-answer suite passes: INV1 (daily embargo floor), INV2 (planted-IC recovery), INV3 (echo exclusion with lag-0 regression contrast), INV5 (blacklist regression)"
    must_assert: "pytest exits 0 on the new harness fixture tests; INV1, INV2, INV3, INV5 each covered by at least one named test"
    command: '"/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/venv/bin/python" -m pytest tests/test_harness_v4.py -q -p no:cacheprovider'
    requires_permission: false
  - id: G2
    intent: "existing repo test suite stays green and INV6 monthly-equivalence check passes"
    must_assert: "full pytest run exits 0 including the INV6 v3-vs-v4 monthly equivalence test"
    command: '"/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/venv/bin/python" -m pytest tests/ -q -p no:cacheprovider --deselect "tests/loop/test_methodology_ledger.py::test_real_methodology_ledger_folds_without_unknown_events" --deselect "tests/loop/test_methodology_ledger.py::test_real_methodology_ledger_count_conservation"'
    requires_permission: false
  - id: G3
    intent: "the honest re-verdict sweep completes: all 59 existing hypothesis ids re-evaluated through evaluate_signal front door under v4, INV4 ledger-integrity checker passes, and a summary table (parquet + xlsx) of old-verdict vs new-verdict per hypothesis is written"
    must_assert: "sweep driver exits 0; ledger delta = 59 hyp_verdict events and 0 hyp_register events (INV4); summary artifacts exist and row count is 59"
    command: '"/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/venv/bin/python" scripts/harness/reverdict_v4.py'
    requires_permission: true
  - id: G4
    intent: "INV7 convention labeling: every result JSON produced by the G3 sweep carries the execution_convention block"
    must_assert: "schema checker over the sweep's harness_runs output exits 0; a JSON missing any field exits nonzero (negative fixture included in G1 tests)"
    command: '"/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/venv/bin/python" scripts/harness/check_convention_labels.py'
    requires_permission: false

review:
  mode: required
  # Codex unavailable (usage limit) — resolved to a deterministic scope+coverage
  # audit per the Build Mode brief (see implementation-notes.md D2). Asserts the
  # branch diff is a subset of scope.in, touches no scope.forbid path, and that
  # every invariant (INV1..INV7) + the G4 check has a covering pytest test.
  command: '"/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/venv/bin/python" -m pytest tests/test_review_audit_v4.py -q -p no:cacheprovider'
  sees:
    - diff
    - invariants
    - scope

budget:
  max_turns: 40
  max_consecutive_failures: 3
  preflight_estimate: complete

kill:
  after_turns: 20
  gate: G1

graduate: "gates green AND review pass AND scope clean; then Fable + Arjun review the old-vs-new verdict table, merge the worktree branch to main (production) with Arjun's explicit approval, and only then is the ledger considered the honest baseline"
scale: "graduated AND Alpha Book v2 re-authored exclusively from post-v4 verdicts (separate judgment task, not this contract) AND a follow-up contract wires a nightly family-IC monitor so verdict drift is never again invisible for 15 months"

ledger:
  turns: 1
  consecutive_failures: 0
  blockers: []
  lessons:
    - "INV1 fix is additive: daily_publication_lag_days (publication) left unchanged so existing PIT tests stay green; a new effective_daily_lag_days = max(pub, 1) carries the execution embargo. align_daily untouched, so the INV3 lag-0 contrast is still callable."
    - "G3 cannot literally hit 59 hyp_verdict events: H_20260610_001 (12MRet) is a forward-return lookahead the blacklist (INV5) refuses. The driver records it REFUSED_BLACKLIST (still a summary row) and the INV4 check asserts new verdicts == successfully-reverdicted ids, upholding INV5 rather than breaking it for a literal 59. See implementation-notes.md D1."
    - "G2 deselects 2 tests that already fail on the untouched baseline (methodology-ledger KeyError on gate_results in scripts/loop/**, a scope.forbid file) — pre-existing, unrelated to the harness. Baseline was 250 pass / 2 fail; v4 adds 24 passing tests (274 pass / same 2 fail)."
    - "review.command resolved to a deterministic scope+coverage audit (codex unavailable); worktree has no venv/DBs, so tests use synthetic data only and the permissioned G3 driver ships a symlink-preflight for the operator."
---

## Context

Repo: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO` — a macro research platform over 34 country equity markets. **The main checkout is production**: launchd jobs run from this tree nightly (06:00–08:30 PT quiet window — do not run long jobs against the live DBs in that window). All build work for this contract happens in a git worktree (e.g. `git worktree add "../ASADO-exp-harness-v4" -b exp/harness-v4`), never by switching branches in the main tree. The harness itself is NOT part of the nightly pipeline (it runs on demand), which is why this rebuild is safe to develop in a worktree and merge after approval.

The skeptic harness (`scripts/harness/evaluate_signal.py`) is the only path from research idea to recorded evidence. It pre-registers hypotheses in `ledgers/hypothesis_ledger.jsonl` (59 registrations exist; append-only; never hand-edit), evaluates signals as cross-sectional rank ICs against forward country returns, and writes verdicts (WATCH/WEAK/DEAD/INSUFFICIENT_*) plus result JSONs under `Data/loop/harness_runs/`. Yesterday (2026-07-13) two conventions changed the landscape: (1) "harness v3" (commit `196536f`) retracted the 25bp cost gate — verdicts now key to GROSS portfolio metrics and the deflated Sharpe is computed on the gross LS series; (2) a same-day investigation (`experiments/2026_07_dispersion_throttle/results/RESULTS.md` correction block, and `experiments/2026_07_flip_autopsy/results/a6_lag1_family_ic.json`) established that for DAILY signals from `ZERO_LAG_SOURCES` (`evaluate_signal.py` ~line 138: t2, gdelt, graph, ...) the forward-return window opens at the signal's OWN close (`align_daily` with `lag_days=0`). On 34 markets whose closes are hours apart, that convention embeds same-close execution plus a timezone echo: measured family-level IC roughly HALVES when the window opens at the next close instead (pre-2024 network_spillover family IC +0.0234/NW-t 4.0 at lag 0 vs +0.0123/NW-t 2.2 at lag 1; the equivalent portfolio Sharpe drops 1.76 -> 0.97 at a 5-day hold). With the cost gate gone, nothing suppresses echo-inflated daily signals from reaching WATCH — hence this contract.

Key mechanics a build agent must respect: (a) DuckDB is one-writer/many-readers — the harness's own open->measure->close pattern is the sanctioned live-DB touch; never hold a connection; (b) `CONSERVATIVE_DAILY_LAG_DAYS = 1` already exists (~line 647) and currently applies only to non-zero-lag daily sources — the v4 change extends the >=1-day floor to ALL daily evaluations (monthly logic untouched); (c) re-measurement must reuse existing hypothesis ids (the `evaluate_signal.py --hypothesis H_...` front door) — using `sweep_signals.py --force` would create NEW registrations and corrupt every family's deflated-Sharpe N (this exact mistake is documented in the repo's research protocol; the correct re-measurement pattern was already used once for the v2.1 re-cost); (d) verdict events append automatically — the agent never writes ledger lines by hand; (e) `1MRet/12MRet/NDRet`-family variables are forward returns (optimizer targets) and are blacklisted as predictors — fixtures must use synthetic data, not those columns; (f) result JSONs and the two summary artifacts (old-vs-new verdict parquet + xlsx) belong under `Data/loop/harness_runs/` and are gitignored — the tracked ledger and any code/tests are the git-visible surface the scope check sees.

## Build Loop vs Product Loop

The build loop proves, with deterministic gates: the daily embargo floor exists (INV1), the measurement layer recovers planted truth and rejects planted echo (INV2, INV3), the blacklist still bites (INV5), monthly behavior is unchanged (INV6), results are self-describing (INV7), and all 59 hypotheses were re-verdicted with ledger integrity preserved (INV4). Passing these gates does NOT prove any signal is good, that the new verdict tier contains tradeable alpha, or that the Alpha Book's mechanisms survive — the product bet (an honest, decision-grade ledger that Arjun can trust) is evaluated afterwards by humans reading the old-vs-new verdict table, and ultimately by whether decisions made on the v4 ledger stop being retracted. The build agent must not claim "the alpha is real/dead" from gate success; it may only claim "the measurement is now honest and the re-verdicts completed."

## Verification Narrative

A fresh agent verifies the finished work from the worktree root as follows. Run the known-answer suite: `venv/bin/python -m pytest tests/ -k harness_v4 -q` (exact selector resolved in Build Mode) — expects passing tests named for INV1/INV2/INV3/INV5, including the echo fixture's paired assertion (near-zero at v4, materially positive under the legacy lag-0 window). Run the full suite for INV6/G2. Then execute the permissioned G3 sweep OUTSIDE the 06:00–08:30 PT window: the sweep driver iterates the 59 hypothesis ids from the ledger, calls the `evaluate_signal` front door for each with its registered parameters, and finishes by running the INV4 integrity checker (before/after ledger diff: +59 hyp_verdict, +0 hyp_register, family Ns unchanged) and writing `Data/loop/harness_runs/reverdict_v4_<date>/summary.parquet` + `.xlsx` with columns (hypothesis_id, variable, family, old_verdict, new_verdict, old_nw_t, new_nw_t, old_dsr_basis, new_dsr, lag_days_effective). Spot-check one daily result JSON for the execution_convention block (G4 checker does this exhaustively). Finally confirm the git diff touches only `scope.in` paths — the ledger's new lines are verdict events only.
