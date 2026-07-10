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

## Not done / next (all need review before landing)
- Wire `score_gap_outcomes` into `loop_daily_job.py` after `build_country_returns`, writing
  the append-only `gap_outcomes` table in the loop DB (currently sandbox parquet).
- Stage 1b–1e production changes (autopsy honesty, brief hygiene, mechanism clustering) — separate reviewed edits.
- Real outcomes begin maturing ~2026-07-22 (21d); the 80-episode gate is quarters out.

## Files
- `score_gap_outcomes.py` — the scorer
- `test_score_gap_outcomes.py` — arithmetic validation
- `gap_outcomes.parquet` — current scored output (append-only)
- `score_run_report.json` — honest run summary
