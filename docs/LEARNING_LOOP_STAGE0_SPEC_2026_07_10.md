# ASADO Learning Loop — Stage 0 Frozen Spec (metric + schema)

**Date:** 2026-07-10
**Status:** DRAFT for Arjun's review — this document IS the gate. No scorer code
is written until the return formula, control rules, and price source below are
approved. (Design context: `LEARNING_LOOP_DESIGN_2026_07_10.md`.)
**Author:** Claude (Opus 4.8), grounded in a live-repo audit (three explorer
passes, 2026-07-10; all file:line and table refs verified on disk).

> **DECISIONS FROZEN (Arjun, 2026-07-10):**
> 1. **Price source = yfinance adjusted close** (`auto_adjust=True`), option (B) below — not Bloomberg. Free, matches the FDT `etf_prices_full.parquet` precedent. Accept the small cross-vendor dividend-timing noise in the `etf_capture` decomposition.
> 2. **Long-only BOOK, but score BOTH directions for LEARNING** (refined 2026-07-10 after the scorer showed 82% of promoted episodes are short — long-only scoring would have discarded ~78% of the learning population and slowed the 80-episode gate ~5x). A short episode is scored as a *paper* bet (we still learn whether the data led price); the book constraint is carried as a separate boolean `tradable_long_only`, and realizable lift is measured on the `tradable_long_only=True` subset. Borrow cost is not modeled for paper shorts; trading costs are charged symmetrically at 25 bp/side.
> 3. **Benchmark = per-episode window EW-34** (§3), not the FDT month-end-rebalanced EW.
> These three are now binding; the prose below is kept for reasoning but the boxed decisions govern where they differ.

---

## Why this document exists

The v2 design review's central criticism: it "describes the learning
intelligence better than it specifies the measurement substrate." This spec
fixes that. It freezes exactly how an episode outcome is computed, from which
price series, with which conventions, so the number is reproducible and can
never be quietly redefined. Everything downstream (attribution, lessons,
priors) consumes these numbers; if they are wrong, the whole loop learns
garbage.

**Files this spec governs (once code is written):**
- New loop-DB tables `gap_outcomes`, `etf_total_return_daily` (both in
  `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb`).
- New loop step `score_gap_outcomes` in `scripts/loop/`.
- Reads (never writes) the main warehouse `asado.*` (country TRI returns) and
  the existing `gap_episodes` / `gap_holdout_daily` tables.

---

## 1. The unit of measurement: the EPISODE, entered once

**Decision (was underspecified in v2):** the scored unit is a **gap episode**,
entered a single time at its open, held to its declared horizon. It is NOT the
candidate-date row and NOT each daily re-promotion.

Evidence forcing this (live loop DB, `build_gap_episodes.py`):
- `gap_holdout_daily`: 843 rows, but only **200 distinct `candidate_signature`**
  and **32 distinct promoted episodes** — a live episode is re-promoted every
  day it survives (one `gap_id` promoted on up to 10 consecutive dates).
- `candidate_id` is date-scoped (`stable_hash(date|episode_key|signature)`,
  `build_gap_episodes.py:303`); `candidate_signature` is the durable cross-day
  identity (`:200-217`); `gap_id` is the episode row identity
  (populated on holdout rows only when promoted, 79 non-null → 32 episodes).

**Entry rule.** An episode is entered **once**, at `entry_ts` = the first
tradable ETF-calendar close strictly after `opened_at` (the gap engine scores
after the daily close, so the earliest actionable price is the next session's
close — a real one-day lag, matching the FDT PIT guard at
`experiments/fdt_mech_backtest/backtest_fdt_layers.py:125`). Subsequent daily
re-promotions of the same `gap_id` create **no new entry**.

**Controls** (see §5) are entered on the same `entry_ts` as the promoted
cohort of that selection date, so promoted-vs-control is a clean same-window
comparison.

**Independence.** Because each episode is one entry, overlapping-window
dependence is bounded by episode count, not row count. Inference still clusters
by selection date and country (§5).

---

## 2. Price substrate — the unresolved decision that needs your call

**Problem.** The two return legs are on different bases today:

| Leg | Source | Basis | Evidence |
|---|---|---|---|
| Country index return | `asado.feature_panel` / `t2_factors_daily`, T2 `1MRet`/`1DRet` | **Total return** (Bloomberg `TOT_RETURN_INDEX_GROSS_DVDS`, dividend-reinvested) | `build_t2_master.py:417`, `scripts/config/t2_bbg_manifest_daily.json` |
| ETF return (loop) | `etf_prices_daily.close` from the News-repo bridge | **Unknown** dividend adjustment; simple `pct_change` | `collect_news_bridge.py:118`, `build_dislocations.py:712` |

A net-of-cost active return that mixes a total-return country leg with a
possibly-price-return ETF leg is not trustworthy — and the whole point of this
loop is trustworthy measurement. The `etf_capture = ETF − country_index`
decomposition is only meaningful if both are total-return.

**Options (need one approved):**

- **(A) Bloomberg ETF total-return index** (`TOT_RETURN_INDEX_GROSS_DVDS` for
  each of the ~34 primary ETF tickers). *Pro:* identical basis to the country
  leg — the decomposition is exact; most authoritative. *Con:* uses Bloomberg
  quota nightly (small — ~34 tickers × 1 field), needs the OpusBloomberg env.
- **(B) yfinance adjusted close, `auto_adjust=True`** (split + dividend
  adjusted), fetched nightly into a durable append-only
  `etf_total_return_daily` table with provenance stamps. *Pro:* free, matches
  the FDT precedent (`etf_prices_full.parquet`). *Con:* a hair less
  authoritative; a different vendor's dividend timing than the Bloomberg
  country leg (small residual basis noise in the capture decomposition).
- **(C) Reuse the News-bridge `close`.** Rejected: unknown adjustment = silent
  basis error. FAIL-IS-FAIL forbids it for a measurement of record.

**My recommendation: (A) Bloomberg**, precisely because `index_information` vs
`etf_capture` requires both legs on one basis, and Bloomberg gives that
exactly. Fall back to (B) only with your approval. Either way the scorer owns a
**dedicated, append-only, provenance-stamped `etf_total_return_daily` table** —
it never scores off the News bridge. The `preferred_ticker` is frozen at open
(already stored in `gap_episodes.preferred_ticker`, `build_gap_episodes.py:345`)
so a later mapping change can't rewrite an entry.

---

## 3. The frozen return formula

For an episode (or control) with `direction ∈ {long:+1, short:−1}`, primary
ETF total return `R_etf` over `[entry_ts, exit_ts]`, country-index total
return `R_idx` over the same window, and equal-weight benchmark `R_ew`:

```
gross_active = dir × (R_etf − R_ew)
net_active   = gross_active − entry_cost − exit_cost − borrow_cost
```

Reported alongside (never folded into net_active):

```
index_information = dir × (R_idx  − R_ew)     # did the world-state view pay in index space
etf_capture       = dir × (R_etf − R_idx)     # FX + basis: what the ETF wrapper kept/lost
```

Note `net_active` uses the **ETF** leg (the tradable expression), while
`index_information` isolates the pure-signal leg. The gap between them is the
Alpha-Book failure mode made measurable per episode.

**Frozen conventions:**

| Item | Rule |
|---|---|
| Window returns | Compound daily total returns from `entry_ts` (exclusive — entered at that close) to `exit_ts` (inclusive). Buy-and-hold, no intra-window rebalance. |
| `exit_ts` | `entry_ts` + `horizon_days` trading days on the **ETF (NYSE) calendar**; `horizon_days` frozen at open (`gap_episodes.horizon_days`). |
| Benchmark `R_ew` | Equal-weight buy-and-hold over **the same `[entry_ts, exit_ts]` window** across all primary ETFs with a valid price at both endpoints; `1/N` at entry, no rebalance. (Per-episode window EW, not the FDT month-end-rebalanced EW — the two coincide only for month-aligned windows.) |
| Costs | **25 bp per side**, charged at both entry and exit (= 50 bp round-trip). Constant `COST_1WAY = 0.0025`, matching the house law at `backtest_fdt_layers.py:59`. |
| Borrow | Shorts (`dir = −1`) charge a per-ticker annualized borrow rate × (horizon_days/252), from a small documented table; default conservative estimate where unknown, flagged `borrow_estimated=true`. |
| ETF expense | **NOT deducted.** With a dividend-adjusted `R_etf`, the expense ratio is already in realized performance. `etf_ownership_drag_bps` stays an ex-ante expression-quality input only (fixes the v1 double-count; `build_gap_episodes.py:373` is ex-ante and untouched). |
| Currency | No separate FX term. FX lives inside `R_etf` (USD-denominated ETF) vs `R_idx` (local TRI) — i.e. it shows up in `etf_capture`, which is the honest place for it. |

---

## 4. Edge cases (all fail-loud, never silent — CLAUDE.md)

- **Holiday / no-print at an endpoint:** carry the last prior ETF-calendar
  close; set `stale_price=true` on the outcome row. Never interpolate.
- **Delisted / no price over window** (e.g. an ETF mapping change): write the
  outcome row with `net_active=NULL`, `unscoreable_reason='no_price_history'`.
  Do not drop, do not zero-fill. An unscoreable episode is a recorded fact.
- **`gap_holdout_daily` duplicate rows:** 33 of 810 `candidate_id`s have two
  identical same-date rows (no PK on the table, `build_gap_episodes.py:130`).
  The scorer keys on **episode `gap_id`** (unique) and de-dups defensively with
  an explicit assertion. The underlying duplication is a `build_gap_episodes.py`
  bug — flagged here, **not** fixed by the scorer (pipeline change ⇒ needs its
  own approval per change-control).
- **`preferred_ticker` NULL at open** (`proxy_type='none'` — dormant today, all
  34 entities have a primary): outcome `unscoreable_reason='no_expression'`.
- **ChinaA/ChinaH, U.S./NASDAQ/US SmallCap:** scored independently, each by its
  own frozen `preferred_ticker` (`ASHR`/`MCHI`, `SPY`/`QQQ`/`IWM`); no merging.
  `config/etf_t2_map.json` is the canonical map.

---

## 5. Control matching & inference (frozen)

For each promoted episode entered on selection date `d`, the **eligible-control
pool** = `gap_holdout_daily` rows on `d` with `eligible=true AND promoted=false`
(live: 52 such rows vs 79 promoted; `reason_not_promoted='below_threshold_or_ineligible'`).
Each control is scored with the **identical** §3 formula and the same
`entry_ts`, using its own entity's frozen ticker and direction.

**Matching keys** (in priority order, matched as availability allows):
selection date `d` → `horizon_bucket` → `mechanism_cluster` (via the
`family_ranks.yaml` mechanism field, §Stage-1 of design) → region
(`config/ff_region_map.json` / `country_mapping.json`) → `direction` →
`liquidity_tier_at_open` (`gap_episodes`) → expression availability. Matching
is used for stratification/weighting in the lift estimate, not to discard
unmatched controls (they remain in the pool, flagged).

**Sample-size gate (governing):** the pre-registered
`config/gap_engine.yaml` requirement — **≥80 closed promoted episodes with ≥3
matched controls each** — governs before any lift claim or prior activation.
(This supersedes my earlier "126 trading days" gate, which was weaker.)

**Inference:** the statistical unit is the **episode**. Standard errors cluster
two-way by **selection date** and **country**; where cell counts are thin,
block-bootstrap by selection date. Promoted-vs-control lift is the headline
learning signal; the frozen `random_shadow_score` in `gap_holdout_daily` is the
null baseline.

---

## 6. `gap_outcomes` schema (append-only)

```sql
CREATE TABLE IF NOT EXISTS gap_outcomes (
  outcome_id            VARCHAR,      -- stable_hash(gap_id|role|horizon|scoring_version)
  gap_id                VARCHAR,      -- episode id (NULL-safe join to gap_episodes)
  candidate_signature   VARCHAR,      -- durable cross-day identity (controls have no gap_id)
  role                  VARCHAR,      -- 'promoted' | 'control'
  selection_date        DATE,
  entity                VARCHAR,
  direction             INTEGER,      -- +1 long / -1 short
  preferred_ticker      VARCHAR,      -- frozen at open
  benchmark             VARCHAR,      -- 'EW34_window'
  evaluation_horizon    INTEGER,      -- trading days, frozen at open
  entry_ts              TIMESTAMP,
  exit_ts               TIMESTAMP,
  r_etf                 DOUBLE,       -- total return over window
  r_idx                 DOUBLE,       -- country TRI over window
  r_ew                  DOUBLE,       -- benchmark over window
  gross_active          DOUBLE,
  index_information     DOUBLE,
  etf_capture           DOUBLE,
  entry_cost            DOUBLE,
  exit_cost             DOUBLE,
  borrow_cost           DOUBLE,
  net_active            DOUBLE,       -- the headline; NULL if unscoreable
  tradable_long_only    BOOLEAN,      -- TRUE for long expressions; realizable-lift subset
  stale_price           BOOLEAN,
  borrow_estimated      BOOLEAN,
  unscoreable_reason    VARCHAR,      -- NULL when scored
  scoring_version       VARCHAR,      -- bump on any formula change
  scored_at             TIMESTAMP,
  price_source          VARCHAR,      -- 'bbg_tri' | 'yf_adj' — provenance
  correction_of         VARCHAR,      -- prior outcome_id this supersedes; NULL normally
  -- Capture clock (Stage 1c) — placed here, not on gap_episodes, to avoid a
  -- durable-schema migration; attribution reads gap_outcomes anyway.
  data_known_at         TIMESTAMP,    -- when the world-state datum was knowable (v1 proxy: as_of_date_open)
  decision_available_at TIMESTAMP,    -- first tradable close after open (= entry_ts)
  absorbed_at           TIMESTAMP     -- first mark date price reached absorption_state='absorbed'
);
-- absorbed_at < decision_available_at  =>  price had it before we could act (not capturable).
```

**Append-only discipline:** a matured episode is scored once and frozen. A data
correction appends a **new** row with `correction_of` set and a bumped
`scoring_version` — history is never overwritten, and a value is never forced
to stand once known wrong. `gap_holdout_daily` stays immutable (the
`future_return_21d/63d` columns there become vestigial; the scorer does not
write them — they are superseded by `gap_outcomes`).

---

## 7. Loop wiring & maturation

- New step `score_gap_outcomes` runs after `build_country_returns` in
  `loop_daily_job.py`. Each night it: (1) refreshes `etf_total_return_daily`
  for the ~34 primary tickers; (2) finds every promoted episode and eligible
  control whose `exit_ts` has passed and has no non-corrected `gap_outcomes`
  row at that horizon; (3) appends scored rows. Idempotent, append-only,
  fail-loud on missing price.
- Fail-soft at the orchestrator level like every loop step: a scorer failure
  logs and continues; nothing else depends on it synchronously.
- **First maturities:** 21-day outcomes ≈ 1 month after deploy; the 63-day
  secondary ≈ 3 months. The 80-episode gate is quarters away. This is inherent
  to forward-only learning, not a defect.

---

## 8. What I need from you to unfreeze coding

1. **Price source: (A) Bloomberg TRI [recommended] or (B) yfinance adj-close?**
   This is the one decision I won't make unilaterally — it sets the basis for
   every number.
2. **Costs:** confirm 25 bp/side (50 bp round-trip) and confirm shorts are in
   scope at all (if the book is long-only in ETF space, drop `borrow_cost` and
   the `dir=−1` path simplifies).
3. **Benchmark:** confirm per-episode-window EW-34 (§3) rather than the
   month-end-rebalanced FDT EW — I believe window-EW is correct for discrete
   episodes, but it differs from the existing experiment and you should bless
   the difference.
4. **The `gap_holdout_daily` duplicate-row bug:** confirm the scorer should
   defend against it and I log the underlying bug for separate approval (vs.
   you wanting it fixed now as part of this work).

On your answers I'll build Stage 1 in the approved order (scorer + append-only
outcomes + autopsy honesty + brief hygiene + mechanism clustering), then the
Stage 1.5 shadow-audit month before anything consumes the numbers.
