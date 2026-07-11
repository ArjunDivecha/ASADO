# Learning Loop — Stage 1a outcome scorer (prototype)

**Date:** 2026-07-10 · **Status:** prototype validated; NOT wired into the production loop.

## What this is
The deterministic outcome scorer from `docs/LEARNING_LOOP_STAGE0_SPEC_2026_07_10.md`
— the missing "did the recommendation pay off, net of costs, vs the benchmark"
measurement that the 2026-07-10 GPT-5.6 review flagged as the #1 gap. Sandbox
only: reads the loop DB and main warehouse **read-only** (open→read→close), writes
to this experiment dir. Nothing in `scripts/loop/` or the production DBs is touched.

## Frozen conventions (Arjun, 2026-07-10)
- Price basis: **yfinance adjusted close** (total return), seeded from the FDT parquet.
- **Score both directions for learning**, flag `tradable_long_only` for the long-only book.
- Benchmark: **per-episode window EW-34** (1/N buy-and-hold over the episode's own window).
- Costs: **25 bp/side** (50 bp round-trip); ETF expense NOT re-deducted (already in adj close).
- Entry: first ETF-calendar close strictly after `opened_at` (1-day PIT lag); exit: +horizon trading days.
- Country leg: backward-labeled, 0.0-dropped TRI returns (replica of `loopdb.daily_country_returns`).

## Validation
`test_score_gap_outcomes.py` — **7/7 arithmetic checks pass**: window return vs manual
p1/p0−1, strict-after entry, +21-trading-day exit, EW = mean of per-ticker returns,
decomposition identity `index_information + etf_capture = gross_active`, cost = gross − 50bp,
future window correctly pending, missing price → None (never fabricated).

## Live run (2026-07-10, last price 2026-07-09)
| metric | value |
|---|---|
| rows (promoted + control) | 87 (38 + 49) |
| **scored** | **0** — nothing has matured yet (earliest 21d exit ≈ 2026-07-22). Correct, not a failure. |
| pending | 86 |
| unscoreable | 1 (Vietnam control selected on the last price date → no post-open trading day) |
| long / short | 30 / 57 |
| tradable_long_only | 30 |

**Key finding:** 82% of promoted episodes are short-direction (25 of 32). This is what
forced the "score both directions, flag tradability" refinement — strict long-only would
have discarded ~78% of the learning population and slowed the pre-registered 80-episode
gate ~5x.

## Stage 1 — LANDED in the nightly loop (2026-07-10)
- **1a scorer wired** (commit f2e21c9): `score_gap_outcomes` runs after `build_country_returns`;
  writes append-only `gap_outcomes` + maintains `etf_total_return_daily` (yfinance auto_adjust,
  fail-soft nightly top-up) in the loop DB. Optional step, never red-lights the job.
- **1d brief hygiene** (117f312): `repriced_against` gaps excluded from Top Gaps, moved to a
  "Rejected by price / awaiting autopsy" section. Verified read-only.
- **1e mechanism clustering** (d32d87b): `mechanism` field in `family_ranks.yaml`; cockpit votes
  by mechanism (diffusion collapses 4→1), `has_nonprice_confirmation` flag, edge-based map arrow.
  Browser-verified, 0 console errors.
- **1b autopsy honesty** (7260bb9): `net_return_after_etf_drag` direction-adjusted; falsified
  (`repriced_against`) gaps now close as explicit failures at max_age instead of lingering open.

## Also landed 2026-07-10 (post-Stage-1 hardening + #1/#2)
- **Decisions settled:** holdout dedup at source (build_gap_episodes), FDT backtest
  registered (`experiments/fdt_mech_backtest/RESULTS.md`), CPI PIT-date routed to
  USER_FIX_LIST item 5, Stage 0b attribution = lightweight z-trajectory heuristic.
- **#2 Capture clock (Stage 1c):** `data_known_at` / `decision_available_at` /
  `absorbed_at` on `gap_outcomes` (idempotent ALTER; absorbed_at < decision => not
  capturable). Verified on a matured test row.
- **#1 Fable claim contract:** `build_fable_connections` emits an optional structured
  `claim`; `write_claims` → append-only `fable_claims` loop table; `score_gap_outcomes`
  adapter 2 grades Fable's own directional calls through the same engine. Tested
  without a paid call; live claim quality is exercised by the nightly Fable pass.

## Next (Stage 2+, once outcomes mature ~2026-07-22)
- Deterministic multi-axis attribution classifier (z-trajectory heuristic for
  data_validity) + Fable-xhigh lesson generation → `lesson_ledger.jsonl`.
- `mechanism_priors` (shadow) + counterfactual static-vs-learned logging.
- Add `gap_outcomes` + `fable_claims` to `config/loop_schema_contract.yaml` (optional
  entries) alongside the first attribution consumer.
- The 80-closed-promoted-episode evidence gate is quarters out — the loop earns its evidence forward.

## Files
- `score_gap_outcomes.py` — the scorer
- `test_score_gap_outcomes.py` — arithmetic validation
- `gap_outcomes.parquet` — current scored output (append-only)
- `score_run_report.json` — honest run summary
