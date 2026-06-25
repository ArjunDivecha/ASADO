# Review Brief: ASADO Price-Discovery Gap Engine PRD

## Request

Review the implementation plan in `PRD_Price_Discovery_Gap_Engine.md` for ASADO.

The user's north-star question is:

> What does the data know that price has not yet figured out?

The plan reframes ASADO as a **price-discovery gap machine**. It adds a durable lifecycle object, the `gap_episode`, between raw daily dislocations and formal hypotheses/theses.

Please critique the plan, not just restate it. Look for hidden coupling, missed invariants, over/under-scoping, wrong build order, validation gaps, and data-model mistakes.

## Important User Constraint

Do **not** overemphasize transaction costs as the dominant bottleneck. The user is primarily trading liquid country ETFs and broad sleeves. Implementation should model:

- ETF/proxy expression quality,
- expense/ownership drag,
- bid-ask spread where available,
- ETF-vs-index tracking gap,
- liquidity tier,
- ETF flows and short-interest crowding,

but costs should be a sanity check, not the central thesis.

## Repo Context

ASADO is a 34-country country-equity macro research platform.

Current live shape:

- Main warehouse: `Data/asado.duckdb`, rebuildable, about 3.8 GB, 36 tables and 6 views.
- Loop DB: `Data/loop/asado_loop.duckdb`, persistent research/alpha system, about 103 MB, 44 tables and 1 view.
- `dislocation_daily`: live detector output, 454 rows from 2026-06-09 through 2026-06-16.
- Daily surfaces include T2/GDELT daily factors, WEO/ECFC revisions, economic surprises, terms-of-trade shares, graph/PIT graph/similarity/lead-lag, market-implied FX/credit/rates, sovereign signals, ETF flows, COT, foreign flows, prediction markets, evidence packs.
- Returns surfaces include `country_returns_monthly`, `factor_returns`, `factor_returns_daily`, T2 daily return variables, and ETF prices from the News bridge.
- Governance is already built: scorecard dimensions include run_manifest, liveness, ledger_integrity, family_registry, pit_lag_proof, cross_source_minimal, config_guard.
- Harness state is skeptical: current loop DB has 2 WATCH, 39 WEAK, 31 DEAD, and 16 INSUFFICIENT_COVERAGE verdicts.

Existing architecture:

- `PRD_Alpha_Hunting_Loop.md` defines detectors D1-D10, dislocation brief, hypothesis/thesis ledgers, and skeptic harness.
- `PRD_Governance_And_Chief_Of_Staff.md` defines deterministic governance first and CoS second.
- `cos_mockups/DESIGN_BRIEF.md` defines a Chief-of-Staff cockpit that should eventually show a ranked point of view, not a dashboard wall.

## Proposed PRD Summary

### New Core Object

The atomic unit becomes the **gap episode**:

```text
gap = world-state evidence - price-implied state
```

A gap episode freezes:

- what world-state knows,
- what price-state appears to know,
- the expected direction and horizon,
- the ETF/proxy expression,
- expression quality,
- absorption state,
- invalidation rule,
- and final autopsy.

### New Tables

#### `price_state_daily`

One row per country/sleeve/date.

Fields include:

- `date`, `country`,
- `preferred_ticker`, `proxy_type`,
- `expense_ratio_bps`, `bid_ask_spread_bps`, `liquidity_tier`,
- ETF and country returns,
- `tracking_gap_5d`, `tracking_gap_21d`, `tracking_gap_z`,
- JSON summaries for equity, FX options, sovereign, flows, valuation, prediction markets,
- `price_state_summary`,
- `source_freshness_json`.

#### `gap_episodes`

One row per frozen episode.

Fields include:

- `gap_id`, `opened_at`, `as_of_date`,
- `entity`, `direction`, `gap_class`, `horizon_days`,
- `source_dislocation_ids`,
- `world_state_json`, `price_state_json`,
- `mechanism_text`,
- `validation_prior`,
- `preferred_ticker`, `proxy_type`, `expression_quality`, `liquidity_tier`,
- `etf_ownership_drag_bps`, `tracking_gap_z`, `crowding_score`,
- `tension_score`,
- `absorption_state`,
- `expected_absorption_path_json`,
- `invalidation_rule`,
- `paper_candidate`,
- `status`, `closed_at`, `close_reason`.

#### `gap_episode_marks`

One row per open gap per day.

Fields include:

- `gap_id`, `date`, `entity`, `preferred_ticker`,
- `realized_etf_return`, `realized_country_return`, `mark_window`,
- `price_absorption_index`, `unabsorbed_fraction`,
- `days_active`, `expression_quality`, `crowding_penalty`,
- freshness and notes JSON.

#### `gap_episode_autopsy`

One row per closed episode.

Failure classes:

- `success_with_absorption`,
- `data_revised_or_wrong`,
- `price_already_knew`,
- `mechanism_wrong`,
- `horizon_too_short`,
- `poor_etf_expression`,
- `ownership_drag_mattered`,
- `crowded_expression`,
- `rational_price_inertia`,
- `unresolved_decay`,
- `void_data_quality`.

### Gap Classes

- G1 own-history extreme not absorbed.
- G2 terms-of-trade vs equity/FX inertia.
- G3 graph propagation latency.
- G4 consensus/revision acceleration vs price inertia.
- G5 cross-asset incoherence.
- G6 ETF expression and crowding gap.
- G7 event with no resolution.
- G8 prediction-market disagreement.

### Tension Score

The plan proposes a transparent v1 ranking score:

```text
tension_score =
    gap_severity
  * novelty
  * validation_prior
  * expression_quality
  * catalyst_nearness
  - etf_drag_penalty
  - crowding_penalty
  - staleness_penalty
  - data_quality_penalty
```

This score triages human attention. It is not a verdict.

### Price Absorption Index

For each episode:

```text
price_absorption_index =
  realized_price_move_in_expected_direction / expected_price_move_from_gap
```

Classifications:

- `unabsorbed`,
- `partially_absorbed`,
- `absorbed`,
- `repriced_against`,
- `decayed`.

### Promotion Rules

`build_gap_episodes.py` reads the latest `dislocation_daily` and promotes only rows passing:

Hard gates:

- governance not red,
- current dislocation rows exist,
- usable returns surface,
- preferred ETF/proxy or explicitly `research_only`,
- deterministic mechanism text,
- no forward-return target leakage.

Soft gates:

- threshold severity or new/intensifying,
- own-history support,
- price-state not already fully absorbed,
- expression quality not poor,
- crowding not extreme unless mechanism is crowding unwind,
- catalyst or plausible absorption horizon.

### Loop Insertion

Add two steps after `build_dislocations` and before `build_evidence_packs`:

```text
build_price_state
build_gap_episodes
```

Rationale: evidence packs should freeze context for promoted gap episodes, not just raw dislocations.

### Brief / CoS Changes

Daily brief gets a new top section: **Top Price-Discovery Gaps**.

CoS cockpit Today cards become gap-episode driven:

1. governance exception if relevant,
2. highest tension open gap,
3. newest high-tension gap,
4. open paper thesis needing stewardship,
5. major autopsy since last run.

### Validation

Unit/schema tests:

- schema validates,
- dedupe works,
- stale input does not create green/valid episode,
- missing ETF mapping yields `research_only` or low expression quality,
- D9 ETF-vs-index gap appears in price state,
- forward-return variables excluded,
- governance red prevents promotion unless fixture allows.

Backfill sanity:

- backfill from current `dislocation_daily` history,
- no duplicate storms,
- D8 stewardship does not crowd out actual gaps,
- ETF fields populate,
- brief renders <=5 top episodes.

Holdout:

- freeze v1 score,
- write top 3-5 gap episodes daily,
- track ignored lower-ranked dislocations as controls,
- score ETF/proxy returns and T2 returns,
- compare top gaps to ignored controls over 90-180 days.

## Specific Questions For Review

1. Is the `gap_episode` object the right abstraction, or should this remain inside `dislocation_daily` / thesis ledgers?
2. Is the proposed table design too wide, too JSON-heavy, or missing normalized child tables?
3. Is `price_state_daily` the right comparator, or should price-state be per surface rather than one compact row?
4. Is the Tension Score formula too arbitrary for v1? What should be frozen vs configurable?
5. Does the build order make sense: price_state -> gap_episodes -> evidence packs -> brief/CoS?
6. What invariants should be added to avoid HARKing, leakage, duplicated episodes, or stale repeated rows?
7. What validation would actually prove this layer works?
8. What should be cut from v1 to keep the build sharp?
9. What is missing from the ETF-expression lens?
10. What changes should be made to the PRD before implementation?

Please end with:

`RECOMMENDATION: PROCEED|REVISE|NEED_MORE_INFO`
