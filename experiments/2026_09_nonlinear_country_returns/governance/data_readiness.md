# P01 Data Readiness — VERDICT: BLOCKED_DATA

**Study:** ASADO_NL_20260913_V1 · **Date:** 2026-09-13 · **Snapshot:** `snapshot_2026_09_13` (8 tables, sha256-indexed in `audit/snapshot_manifest.json`)

## The blocking fact

The spec requires **all 24 primitives non-missing per (origin, market) row** and **≥20 eligible markets per scored origin**. Measured from the frozen snapshot:

- **Only 15 markets can ever satisfy all 24 primitives**: Australia, Brazil, Canada, France, Germany, Italy, Japan, Korea, Mexico, Netherlands, South Africa, Spain, Sweden, Switzerland, U.K.
- The binding constraint is `graph_edge_vintages` `edge_type='bank'` (P07/P08): **21 focal markets ever**, with staggered focal entry (Italy 2015-04, Spain 2012-10, South Africa 2010-01, Canada 2008-01).
- All 15 survivors are simultaneously eligible only from **2015-04-01** (Italy's first bank vintage).
- Therefore **no origin ever reaches the 20-market floor**. This is `BLOCKED_DATA` under spec §229, not a marginal shortfall.

Per the spec: *"If these requirements fail, deliver the measured feasible panel and the exact source limitations… Return BLOCKED_DATA or INSUFFICIENT_EVIDENCE; propose a clearly versioned amendment without evaluating the amended model."* — that is what this document is.

## Sequential coverage losses (waterfall)

Measured per (primitive, market) in `audit/coverage_by_feature_market.parquet`; aggregate in `audit/coverage_waterfall.json`:

| Stage | Markets lost | Survivors |
|---|---|---|
| T2 TRI (P01–P04) | — | 34 |
| Trade edges, focal (P05–P06) | ChinaH, NASDAQ, Taiwan, US SmallCap | 30 |
| Bank edges, focal (P07–P08) | + ChinaA, India, Indonesia, Malaysia, Poland, Saudi Arabia, Singapore, Thailand, Turkey (US complex already out) | 21 |
| FX options surface (P09–P11) | + Denmark (US complex, Vietnam already out) | 19* |
| FX carry (P12) | no additional loss (Denmark covered via USDDKK forward) | 19* |
| SOV 2Y / curve / Δ2Y (P13, P15, P16) | + Chile, Hong Kong, Philippines, Taiwan already out | 15 |
| SOV 10Y (P14) | no additional loss | 15 |
| Consensus GDP/CPI (P17–P20) | none structurally; per-market late starts apply | 15 |
| Globals (P21–P24) | none (market-invariant) | 15 |

*P11's specified **3M** tenor is missing entirely (see below); the 19 figure uses the existing 1M RR only as a coverage placeholder, not a bound feature.

## Secondary blocker: P11 tenor

The PRD specifies a **3M** 25-delta risk reversal. The collector (`collect_market_implied_bbg.py`) pulls only `[PAIR]25R1M` — no 3M RR exists anywhere. `FX_RR25_1M_PCT` (29 markets, sign convention already "positive = local depreciation premium") is the nearest real series and is a different tenor. Options: amend tenor to 1M, or add a 3M RR collection (new Bloomberg series — owner decision, and history would need a one-time backfill pull).

## What IS verified ready

- **T2 TRI levels** (`t2_levels_daily` `Tot Return Index`): all 34 markets, 2000-01-01→2026-09-11 — own-return features and labels are fully resourced.
- **FX options surface**: 1W/1M/3M ATM IV + 1M RR + 1M BF + 3M forward carry, 29–30 markets, 2006-01→.
- **Sovereign yields**: 2Y (27 mkts), 10Y (32 mkts), 2005-01→.
- **Consensus**: `CONS_GDP_PCT`/`CONS_CPI_PCT` with `target_year`, 34 markets, 2007-10→; year-specific ECFC tickers store full revision paths (unchanged vs missing distinguishable).
- **Graph edge vintages**: `vintage_end`/`applies_from` structure is genuinely PIT (publication-lagged); trade 30 focals / bank 21 / holder 31.
- **Globals**: VIX, MOVE, DXY, Brent generics (CO1/CO2), 2006-01→.
- `weo_vintages` exists as the repo's only true-vintage macro table (not needed by current primitives).

## Measured amendment scenarios (NOT evaluated, NOT endorsed — for owner decision)

| Amendment | Markets ever eligible | First date ≥20 | Notes |
|---|---|---|---|
| **A1** — drop P07/P08 (bank-neighbor primitives; S loses C05 → 15 inputs) | 22 | 2010-07-01 | Cleanest data-wise; changes the 24/16 design to 22/15 and drops a concept family. |
| **A2** — substitute `holder` (inbound-ownership) edges for `bank` in P07/P08 | 22 | 2010-07-01 | Preserves 24 inputs and a network-neighbor channel, but changes its economic meaning (ownership vs banking claims). |
| **A3** — extend bank edges to more countries | unknown | — | Requires new data collection; BIS-style banking-claims coverage is structurally limited to reporting countries — likely cannot fill China/India/etc. historically. |
| **A4** — reduce the 20-market floor to ≤15 | 15 | never ≥20 | Keeps all 24 primitives but weakens the cross-sectional breadth the study was designed around; panel would also be DM-heavy and start ~2015 (all-15 from 2015-04) → only ~3y of outer origins. |

Every path also needs the **P11 tenor amendment** (3M→1M, or a new collection).

## Timing / staleness contracts observed

- Loop tables are batch-refreshed nightly; snapshot watermark = data through 2026-09-11 (last completed nightly before the Sunday freeze).
- Graph edge vintages are quarterly (`vintage_end` at quarter ends; `applies_from` = publication lag).
- `consensus_daily` rows are daily per (country, target_year); "unchanged" is distinguishable from "missing" because unchanged values are restated daily.
- `market_implied_daily`/`sovereign_daily` dates are observation dates (Bloomberg daily series); the 23:59-UTC origin mapping + freshness limits (≤1 missed source session, ≤4 calendar days) are P02 contract work.
- `daily_calendar` exists in the main DB as a cross-check, but the study builds **independent** per-market session calendars from TRI marks per P02.

## What P01 did NOT do (by design)

- No return correlations, IC, or any predictive-strength measurement on real data.
- No feature was substituted, filled, or dropped to improve coverage or returns.
- No amendment was evaluated. The owner picks a path; only then does the manifest get re-bound and P02 proceed.
