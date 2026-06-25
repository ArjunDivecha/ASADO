# PRD — ASADO Price-Discovery Gap Engine
## Gap Episodes, ETF Expression Quality, Absorption Tracking, And Autopsy

| Field | Value |
|-------|-------|
| **Project** | ASADO country-equity macro research platform |
| **System name** | Price-Discovery Gap Engine |
| **Short name** | `gap_engine_v1` |
| **Version** | 1.3 (revised after final Opus pass) |
| **Created** | 2026-06-22 |
| **Owner** | Arjun Divecha |
| **Executor** | Frontier model agent sessions / Codex |
| **Status** | Draft for implementation after review revisions |
| **Reviewed by** | Opus consult + Sakana/Fugu via `codex-fugu`, 2026-06-22; final Opus pass, 2026-06-23 |
| **Related** | `PRD_Alpha_Hunting_Loop.md`, `PRD_Governance_And_Chief_Of_Staff.md`, `PRD_Triptych_Prediction_Prior_Layer.md`, `docs/ASADO_PRICE_DISCOVERY_GAP_MACHINE_2026_06_22.md`, `docs/PRICE_DISCOVERY_GAP_ENGINE_REVIEW_BRIEF_2026_06_22.md`, `cos_mockups/DESIGN_BRIEF.md` |
| **Primary output** | `price_state_daily`, `price_state_surface`, `gap_episodes`, `gap_episode_expression`, `gap_episode_marks`, `gap_episode_autopsy`, `gap_holdout_daily`, daily brief "Top Price-Discovery Gaps", CoS cockpit Today cards |

---

## 0. One-Paragraph Summary

ASADO's north-star question is: **what does the data know that price has not yet figured out?** The current Alpha-Hunting Loop already produces dislocations, evidence packs, ledgers, and a governed daily brief. This PRD adds the missing lifecycle object between a raw detector row and a thesis: the **gap episode**. A gap episode freezes a specific divergence between **world-state evidence** and **price-implied state**, records the cleanest ETF/proxy expression, tracks how much price has absorbed each day, and autopsies the result when it resolves. The goal is not to add more data or create a live trading engine. The goal is to make ASADO's daily update answer, every morning: here are the few places where the data appears to know something price has not absorbed, here is the ETF/proxy expression, here is what would prove us wrong, and here is how similar gaps ended.

Review result: the abstraction is right, but v1 must be explicit about lifecycle identity, ETF currency basis, data-source availability, immutable fields, point-in-time marks, score-component auditability, replay/config pinning, provisional absorption labeling, and the fact that ranking cannot be proven by the short existing `dislocation_daily` history. Those fixes are folded into this v1.3 PRD.

---

## 1. Product Thesis

ASADO has enough breadth. The binding constraint is now attention and judgment.

The current `dislocation_daily` table is useful, but it is too low-level to be the main reasoning object. It tells us something fired. It does not fully answer:

- what exactly does world-state know?
- what does price-state appear to know?
- is the gap new, stale, intensifying, or already absorbed?
- what ETF/proxy expresses the idea cleanly?
- is the expression crowded, drifting, or structurally poor?
- what horizon should the gap close over?
- what would invalidate the mechanism?
- how did prior episodes of this type end?

This PRD makes the **price-discovery gap** the primary unit of attention and learning.

```text
gap = per-class world-state evidence vs price-implied state
```

The shorthand above is conceptual, not a single arithmetic subtraction. Every gap class declares its own severity normalization and expected-move method. A terms-of-trade gap, graph-propagation gap, and prediction-market disagreement cannot share one raw scale.

The engine does not replace the skeptic harness, the hypothesis ledger, or the thesis ledger. It feeds them with structured, durable, pre-scored episodes.

---

## 2. Goals

### G1. Promote The Best Dislocations Into Durable Gap Episodes

Convert raw detector output into a smaller set of persistent episodes with mechanism, horizon, price-state comparison, ETF expression, and invalidation rule.

### G2. Make Price-State Explicit

Build a compact daily surface and a per-surface child table summarizing what markets appear to have absorbed: equity returns, ETF returns, FX/FX options, sovereign curves/CDS, valuation, ETF flows/short interest, prediction-market signals where available, and live signal standing.

### G3. Make ETF Expression First-Class

ASADO mostly expresses country views through ETFs and broad sleeves, not local baskets. Every gap episode must carry preferred ticker/proxy, alternate proxies, currency basis, ETF-vs-index/FX-decomposed basis, liquidity tier, ADV, ownership drag, and crowding indicators. Transaction costs are a sanity check, not the core thesis.

### G4. Track Absorption, Not Just Firing

Every open episode gets daily marks: realized ETF/proxy return, realized country return, expected move, price absorption index, unabsorbed fraction, current tension score, expression quality, crowding, source freshness, and status. The engine should know whether price has repriced with, repriced against, ignored, or overreacted to the world-state evidence.

### G5. Learn From Autopsies

When an episode closes, classify why: success, data revision, mechanism wrong, horizon too short, price already knew through another surface, poor ETF expression, FX/tracking basis, crowding, rational price inertia, or unresolved decay.

### G6. Rewire The Brief And CoS Around Tension

The daily brief and Chief-of-Staff cockpit should rank the top 3-5 price-discovery gaps, not raw z-scores or all dislocation rows. The cockpit's Today cards should be driven by `gap_episodes` and the latest `gap_episode_marks`.

### G7. Run A Frozen Holdout

Freeze v1 scoring and compare top-ranked gap episodes against ignored lower-ranked eligible dislocations over 90-180 days. Backfill is a plumbing smoke test only; ranking is proven or falsified forward.

---

## 3. Non-Goals

- Do not replace `dislocation_daily`; keep it as the detector substrate.
- Do not create persistent tables directly in `Data/asado.duckdb`; all new persistent objects live in `Data/loop/asado_loop.duckdb` and parquet-first `Data/loop` / `Data/work/loop` artifacts.
- Do not build an order router or live trading system.
- Do not let LLM commentary count as evidence.
- Do not turn every dislocation into a thesis.
- Do not treat GDELT, Triptych, prediction markets, or the combiner as truth surfaces without validation.
- Do not use forward-return variables (`1MRet`, `3MRet`, `6MRet`, `9MRet`, `12MRet` or daily analogs) as signals.
- Do not overemphasize punitive transaction costs. For the intended ETF universe, model ETF expression quality, expense drag, tracking/currency basis, liquidity, and crowding instead.
- Do not make bid/ask spread a v1 gate; the repo does not currently have a dependable bid/ask source. Use ADV-derived liquidity first.
- Do not add gap features to `build_combiner.py` until an ablation or holdout shows incremental value.
- Do not rank sparse prediction-market gaps in v1. G8 can be diagnostic/flag-only until coverage is proven.
- Do not re-point evidence packs to gap episodes in the critical path until the GDELT rate-limit behavior is explicitly handled.

---

## 4. Current State

Verified current surfaces as of 2026-06-22:

- Main warehouse: `Data/asado.duckdb`, about 3.8 GB, 36 tables and 6 views.
- Loop DB: `Data/loop/asado_loop.duckdb`, about 103 MB, 44 tables and 1 view.
- `dislocation_daily`: live, 454 rows from 2026-06-09 through 2026-06-16.
- Daily world-state surfaces: T2/GDELT daily factors, WEO revisions, ECFC consensus, economic surprises, ToT shares, graph/PIT graph/similarity/lead-lag, market-implied stress, sovereign signals, ETF flows, COT, foreign flows, prediction markets, evidence packs.
- Returns spine: `loopdb.daily_country_returns()` / `loopdb.returns_panel()` from backward-labeled `1DRet`, monthly `country_returns_monthly`, `factor_returns`, `factor_returns_daily`, and ETF prices from the News bridge (`etf_prices_daily`).
- ETF map: `config/etf_t2_map.json` contains primary and alternate ETF tickers, but not expense ratio, spread, or liquidity. v1 must add expression metadata or derive it.
- Governance: latest checked scorecard was GREEN across run_manifest, liveness, ledger_integrity, family_registry, pit_lag_proof, cross_source_minimal, and config_guard.
- Harness: current loop DB had 2 WATCH, 39 WEAK, 31 DEAD, and 16 INSUFFICIENT_COVERAGE verdicts.
- Existing brief: `Data/dislocations/brief_YYYY_MM_DD.md` already includes governance, dislocations, holdings stewardship, forward calendar, market-implied stress, sovereign curves/ratings, macro surprises, flows, ETF positioning, short interest, COT, prediction markets, and JST context.

The missing object is not another feed. It is a durable episode that says which rows matter, why, how the ETF/proxy expression works, and how the gap resolved.

---

## 5. Conceptual Model

### 5.1 World-State Vector

What the underlying reality says:

- terms-of-trade impulse,
- WEO and ECFC revision momentum,
- economic surprise path,
- graph-neighbor propagation,
- similarity-twin divergence,
- lead-lag diffusion,
- foreign investor flows,
- ETF positioning and short interest,
- COT commodity positioning,
- event calendar and evidence packs,
- JST long-cycle tail context,
- valuation and earnings fundamentals,
- Triptych-style country/factor priors where available.

### 5.2 Price-State Vector

What markets appear to have absorbed:

- T2 country return over 1d/5d/21d/63d/120d,
- ETF/proxy return over the same windows,
- ETF-vs-T2 basis with explicit currency basis,
- FX spot and FX-option stress,
- sovereign 2Y/10Y and CDS levels/slope,
- valuation percentile,
- ETF flow/short-interest crowding,
- prediction-market probabilities where available,
- live signal standing and combiner score.

### 5.3 Price-Discovery Gap

A gap exists when world-state is materially different from price-state and the difference is not stale, already absorbed, or explained by poor ETF expression.

The system should bias toward **own-history calibration** over raw cross-country ranking when measuring "unusual." The recent regime work showed that raw cross-country posterior ranks can fail while within-country time-series extremes work. This is the right default for gap detection.

### 5.4 ETF Currency-Basis Rule

Country ETFs are generally unhedged USD vehicles. The T2 country return surface may not be in the same currency basis. Therefore:

- every ETF-vs-T2 comparison must carry `currency_basis`;
- v1 must label raw ETF-vs-T2 basis as `usd_unhedged_etf_vs_t2` unless decomposed;
- raw `tracking_gap_*` must not be treated as pure expression quality until FX is decomposed;
- the validation plan must include an FX-decomposition check.

---

## 6. Gap Classes

| ID | Class | Existing substrate | V1 status | First use |
|---|---|---|---|---|
| G1 | Own-history extreme not absorbed | regime / valuation / macro / Triptych priors | Ranked | Country is extreme vs itself but ETF price has not moved |
| G2 | Terms-of-trade vs equity/FX inertia | D1, ToT shares, commodities, T2 returns, FX | Ranked | Commodity impulse not reflected in ETF/equity/FX |
| G3 | Graph propagation latency | D2, graph/PIT graph, lead-lag, similarity | Ranked | Neighbors/twins repriced, endpoint ETF did not |
| G4 | Consensus/revision acceleration vs price inertia | WEO, ECFC, eco surprise, T2 returns | Ranked if coverage passes | Forecasts or prints move before ETF price |
| G5 | Cross-asset incoherence | D4/D10, sovereign, FX options, equity | Ranked if key surfaces fresh | FX/credit/rates price stress while ETF does not, or inverse |
| G6 | ETF expression and crowding gap | D9, ETF prices, ETF flows, short interest | Diagnostic in v1 unless persistent | ETF diverges from intended country exposure or crowding explains gap |
| G7 | Event with no resolution | forward calendar, event log, evidence packs, GDELT | Diagnostic in v1 | Catalyst exists for an unresolved world-state gap |
| G8 | Prediction-market disagreement | predmkt surfaces | Diagnostic only in v1 | Market odds move but ETF/sovereign surfaces do not, or inverse |

---

## 7. Data Contracts

### 7.1 `price_state_daily`

Loop-owned compact table. One row per country/sleeve per date. Keep scalar fields queryable; JSON is allowed only for context bundles.

| Column | Type | Notes |
|---|---|---|
| `date` | DATE | As-of date |
| `country` | VARCHAR | Exact T2 name |
| `preferred_ticker` | VARCHAR | Primary ETF/proxy from `config/etf_t2_map.json` |
| `proxy_type` | VARCHAR | `single_country_etf`, `broad_sleeve`, `proxy`, `none` |
| `expense_ratio_bps` | DOUBLE | Annual ownership drag from `config/etf_expression_overrides.yaml`; nullable only before config is complete |
| `dollar_adv_21d` | DOUBLE | Derived from `etf_prices_daily.close * volume` |
| `liquidity_tier` | VARCHAR | Derived from ADV thresholds in `config/gap_engine.yaml` |
| `bid_ask_spread_bps` | DOUBLE | V2/optional only; never a v1 gate |
| `currency_basis` | VARCHAR | Example: `usd_unhedged_etf_vs_t2` |
| `etf_return_5d` | DOUBLE | ETF/proxy 5d return |
| `etf_return_21d` | DOUBLE | ETF/proxy 21d return |
| `country_return_5d` | DOUBLE | T2 country/sleeve return from `loopdb.returns_panel()` |
| `country_return_21d` | DOUBLE | T2 country/sleeve return from `loopdb.returns_panel()` |
| `basis_gap_5d` | DOUBLE | ETF minus T2 return in stated `currency_basis` |
| `basis_gap_21d` | DOUBLE | ETF minus T2 return in stated `currency_basis` |
| `basis_gap_z` | DOUBLE | Own-history z-score of basis gap |
| `fx_component_21d` | DOUBLE | FX contribution where measurable; nullable v1 |
| `fx_adjusted_basis_gap_21d` | DOUBLE | Basis after FX adjustment where measurable; nullable v1 |
| `equity_state_json` | JSON | Return z-scores and trend |
| `fx_options_state_json` | JSON | RR/vol/bfly/carry where available |
| `sovereign_state_json` | JSON | CDS/yield curve/rating where available |
| `flow_state_json` | JSON | ETF flow, short interest, foreign flows, COT |
| `valuation_state_json` | JSON | CAPE/PB/DY/EY/ERP percentiles |
| `predmkt_state_json` | JSON | Country composites where available |
| `price_state_summary` | VARCHAR | Compact human-readable sentence |
| `source_freshness_json` | JSON | Latest source dates and caveats |

### 7.2 `price_state_surface`

Loop-owned child table. One row per country/date/surface. This keeps cross-asset incoherence queryable without exploding `price_state_daily`.

| Column | Type | Notes |
|---|---|---|
| `date` | DATE | As-of date |
| `country` | VARCHAR | Exact T2 name |
| `surface` | VARCHAR | `equity`, `etf`, `fx_options`, `sovereign`, `valuation`, `flows`, `predmkt`, `live_signal` |
| `state_score` | DOUBLE | Surface-specific normalized score; nullable if informational only |
| `direction_hint` | VARCHAR | `long`, `short`, `stress`, `relief`, `neutral`, `unknown` |
| `freshness_date` | DATE | Latest source date |
| `lag_policy` | VARCHAR | Publication/as-of lag rule used |
| `state_json` | JSON | Surface-specific details |

### 7.3 `gap_episodes`

Loop-owned immutable claim table. One row per frozen episode. Claim fields are frozen after open except `status`, `closed_at`, and `close_reason`.

| Column | Type | Notes |
|---|---|---|
| `gap_id` | VARCHAR | Stable hash of `episode_key|first_seen_date|episode_instance`; **does not include run date/as_of_date** |
| `episode_key` | VARCHAR | Human-readable identity: `entity|gap_class|direction|horizon_bucket` |
| `episode_instance` | INT | Reopen sequence for this `episode_key`; starts at 1 and increments only after a prior episode closes |
| `gap_id_seed` | VARCHAR | Literal seed string used to hash `gap_id`, stored for audit |
| `opened_at` | TIMESTAMP | Wall-clock creation time |
| `first_seen_date` | DATE | First data date for the episode |
| `as_of_date_open` | DATE | Data as-of date at open |
| `entity` | VARCHAR | Country/sleeve/factor |
| `direction` | VARCHAR | `long`, `short`, `flag` |
| `gap_class` | VARCHAR | G1-G8 |
| `horizon_days` | INT | Frozen expected horizon |
| `horizon_bucket` | VARCHAR | `5d`, `21d`, `63d`, `126d` |
| `source_dislocation_ids` | JSON | Source `dislocation_daily` ids at open; survival logic must not require ids to appear in latest date |
| `related_gap_ids` | JSON | Cross-class collisions for same entity/direction |
| `world_state_json` | JSON | Frozen evidence and own-history z-scores |
| `price_state_json` | JSON | Frozen price-state snapshot |
| `mechanism_template_id` | VARCHAR | Deterministic template id; no free-form LLM mechanism in v1 |
| `mechanism_text` | VARCHAR | Template-generated from class + signal values; frozen |
| `validation_prior` | DOUBLE | Harness/event-study/prior support score with neutral floor |
| `scoring_config_version` | VARCHAR | Frozen scoring config version used at open |
| `scoring_config_hash` | VARCHAR | Hash of `config/gap_engine.yaml` scoring block used at open |
| `preferred_ticker` | VARCHAR | Primary ETF/proxy expression at open |
| `proxy_type` | VARCHAR | From price state |
| `expression_quality_at_open` | DOUBLE | 0-1 score |
| `liquidity_tier_at_open` | VARCHAR | High/medium/low/missing |
| `etf_ownership_drag_bps` | DOUBLE | Horizon-scaled expense drag |
| `currency_basis` | VARCHAR | Currency basis for ETF-vs-T2 comparison |
| `basis_gap_z_at_open` | DOUBLE | ETF vs T2 basis, labeled by currency basis |
| `crowding_score_at_open` | DOUBLE | ETF flows, short interest, COT, foreign-flow context |
| `severity_score_at_open` | DOUBLE | Normalized `[0, 1]` score component |
| `novelty_score_at_open` | DOUBLE | Normalized `[0, 1]` score component |
| `validation_prior_score_at_open` | DOUBLE | Normalized `[0, 1]` score component |
| `expression_quality_score_at_open` | DOUBLE | Normalized `[0, 1]` score component |
| `catalyst_nearness_score_at_open` | DOUBLE | Normalized `[0, 1]` score component |
| `etf_drag_score_at_open` | DOUBLE | Normalized `[0, 1]` penalty component |
| `crowding_penalty_score_at_open` | DOUBLE | Normalized `[0, 1]` penalty component |
| `staleness_penalty_score_at_open` | DOUBLE | Normalized `[0, 1]` penalty component |
| `data_quality_penalty_score_at_open` | DOUBLE | Normalized `[0, 1]` penalty component |
| `tension_score_at_open` | DOUBLE | Frozen ranking score |
| `tension_components_json` | JSON | Redundant frozen component values and weights for compact reporting; real component values also exist as scalar columns |
| `expected_absorption_path_json` | JSON | Frozen expected move / absorption path |
| `invalidation_rule` | VARCHAR | Template-bound concrete rule; frozen |
| `research_only` | BOOLEAN | Built but excluded from top-5 brief and never paper candidate |
| `paper_candidate` | BOOLEAN | Eligible for human/agent thesis review; false for `research_only` |
| `status` | VARCHAR | `open`, `closed`, `expired`, `invalidated`, `void` |
| `closed_at` | TIMESTAMP | Nullable |
| `close_reason` | VARCHAR | Nullable |

Immutable fields:

- `entity`, `direction`, `gap_class`, `horizon_days`, `horizon_bucket`,
- `episode_key`, `episode_instance`, `gap_id_seed`, `first_seen_date`,
- `world_state_json`, `price_state_json`,
- `mechanism_template_id`, `mechanism_text`,
- `validation_prior`, `scoring_config_version`, `scoring_config_hash`,
- all `*_score_at_open` and `*_penalty_score_at_open` columns,
- `tension_score_at_open`, `tension_components_json`,
- `expected_absorption_path_json`, `invalidation_rule`.

### 7.4 `gap_episode_expression`

Loop-owned child table. One row per candidate ETF/proxy per gap. This supports primary and alternate ETFs without rewriting the episode claim.

| Column | Type | Notes |
|---|---|---|
| `gap_id` | VARCHAR | Episode id |
| `ticker` | VARCHAR | ETF/proxy ticker |
| `is_primary` | BOOLEAN | Whether selected as primary expression |
| `proxy_type` | VARCHAR | `single_country_etf`, `broad_sleeve`, `alternate`, `manual_proxy` |
| `currency_basis` | VARCHAR | Currency basis of expression |
| `expense_ratio_bps` | DOUBLE | From overrides config |
| `dollar_adv_21d` | DOUBLE | Derived from ETF prices |
| `liquidity_tier` | VARCHAR | Derived |
| `basis_gap_21d` | DOUBLE | ETF-vs-T2 basis |
| `basis_gap_z` | DOUBLE | Own-history z |
| `fx_adjusted_basis_gap_21d` | DOUBLE | Nullable v1 |
| `expression_quality` | DOUBLE | 0-1 score |
| `reason` | VARCHAR | Why primary/alternate was chosen |

### 7.5 `gap_episode_marks`

One row per open gap per date per mark window.

Primary key: `(gap_id, date, mark_window)`.

| Column | Type | Notes |
|---|---|---|
| `gap_id` | VARCHAR | FK-like reference |
| `date` | DATE | Mark date |
| `mark_window` | VARCHAR | `since_open`, `5d`, `21d`, `63d` |
| `entity` | VARCHAR | Denormalized for easy querying |
| `preferred_ticker` | VARCHAR | Denormalized |
| `realized_etf_return` | DOUBLE | Window return |
| `realized_country_return` | DOUBLE | Window T2 return |
| `realized_move` | DOUBLE | Realized move in expected direction |
| `expected_move` | DOUBLE | Expected move used in denominator |
| `expected_move_source` | VARCHAR | `severity_mapping`, `event_study`, `triptych_prior`, `prior_episode`, `neutral_default` |
| `price_absorption_index` | DOUBLE | Capped/winsorized index |
| `unabsorbed_fraction` | DOUBLE | Bounded where possible |
| `absorption_state` | VARCHAR | `unabsorbed`, `partially_absorbed`, `absorbed`, `repriced_against`, `decayed`, `insufficient_signal` |
| `tension_score_current` | DOUBLE | Current weighted score |
| `days_active` | INT | Days since open |
| `expression_quality_current` | DOUBLE | Updated expression score |
| `crowding_penalty_current` | DOUBLE | Updated crowding score |
| `source_freshness_json` | JSON | Freshness/caveats and lag policies |
| `notes_json` | JSON | Machine-readable mark detail |

### 7.6 `gap_episode_autopsy`

One row per closed episode.

| Column | Type | Notes |
|---|---|---|
| `gap_id` | VARCHAR | FK-like reference |
| `closed_at` | TIMESTAMP | Close timestamp |
| `outcome` | VARCHAR | `success`, `miss`, `mixed`, `void` |
| `mechanism_verdict` | VARCHAR | `confirmed`, `wrong`, `unresolved`, `not_testable` |
| `price_absorbed` | BOOLEAN | Whether price-state moved in expected direction |
| `absorption_half_life_days` | DOUBLE | Estimated where applicable |
| `realized_etf_return` | DOUBLE | Since open |
| `realized_country_return` | DOUBLE | Since open |
| `net_return_after_etf_drag` | DOUBLE | Expense-adjusted if available |
| `failure_class` | VARCHAR | Controlled vocabulary below |
| `lessons` | VARCHAR | Short human-readable lesson |
| `created_by` | VARCHAR | `auto`, `agent`, or `arjun` |

Failure class vocabulary:

- `success_with_absorption`
- `data_revised_or_wrong`
- `price_already_knew`
- `mechanism_wrong`
- `horizon_too_short`
- `poor_etf_expression`
- `fx_or_currency_basis_explained_gap`
- `ownership_drag_mattered`
- `crowded_expression`
- `rational_price_inertia`
- `unresolved_decay`
- `void_data_quality`

### 7.7 `gap_holdout_daily`

One row per eligible candidate dislocation per date, including ignored controls and random-shadow ranking.

| Column | Type | Notes |
|---|---|---|
| `date` | DATE | As-of date |
| `candidate_id` | VARCHAR | Stable hash of `date|episode_key|candidate_signature` |
| `candidate_signature` | VARCHAR | Deterministic source signature; see rules below |
| `gap_id` | VARCHAR | Nullable; populated if promoted |
| `entity` | VARCHAR | Country/sleeve/factor |
| `gap_class` | VARCHAR | G1-G8 |
| `direction` | VARCHAR | long/short/flag |
| `horizon_bucket` | VARCHAR | `5d`, `21d`, `63d`, `126d` |
| `source_dislocation_ids` | JSON | Source rows used for this candidate, if available |
| `eligible` | BOOLEAN | Passed hard gates |
| `promoted` | BOOLEAN | Top ranked into gap episode |
| `scoring_config_version` | VARCHAR | Frozen scoring config version at selection |
| `scoring_config_hash` | VARCHAR | Hash of scoring block used at selection |
| `severity_score` | DOUBLE | Normalized score component |
| `novelty_score` | DOUBLE | Normalized score component |
| `validation_prior_score` | DOUBLE | Normalized score component |
| `expression_quality_score` | DOUBLE | Normalized score component |
| `catalyst_nearness_score` | DOUBLE | Normalized score component |
| `etf_drag_score` | DOUBLE | Normalized penalty component |
| `crowding_penalty_score` | DOUBLE | Normalized penalty component |
| `staleness_penalty_score` | DOUBLE | Normalized penalty component |
| `data_quality_penalty_score` | DOUBLE | Normalized penalty component |
| `tension_score_at_selection` | DOUBLE | Score used |
| `random_shadow_score` | DOUBLE | Fixed seeded random comparator |
| `reason_not_promoted` | VARCHAR | For controls |
| `future_return_21d` | DOUBLE | Filled later by holdout evaluator, not by builder |
| `future_return_63d` | DOUBLE | Filled later by holdout evaluator, not by builder |

Candidate identity rules:

- `episode_key = entity|gap_class|direction|horizon_bucket`, matching the episode layer.
- `candidate_signature` is the sorted source `dislocation_id` list when ids exist.
- If a detector row has no stable id, `candidate_signature = sha1(gap_class|entity|direction|horizon_bucket|source_surface|rounded_source_metric_values|source_freshness_date)`.
- `candidate_id = sha1(date|episode_key|candidate_signature)`.
- `candidate_id` does not include scoring weights or config hash; those are stored separately so old holdout rows remain comparable after a version bump.
- `random_shadow_score = deterministic_uniform(seed=sha1(candidate_id|scoring_config_hash|shadow_v1))`.

---

## 8. Tension Score V0

The first implementation should be transparent, additive, normalized, and frozen.

```text
tension_score =
    w_severity          * severity_score
  + w_novelty           * novelty_score
  + w_validation_prior  * validation_prior_score
  + w_expression        * expression_quality_score
  + w_catalyst          * catalyst_nearness_score
  - w_etf_drag          * etf_drag_score
  - w_crowding          * crowding_penalty_score
  - w_staleness         * staleness_penalty_score
  - w_data_quality      * data_quality_penalty_score
```

Rules:

- Every component is normalized to `[0, 1]`.
- `validation_prior_score` has a neutral floor, e.g. `0.5`, so untested episodes are not annihilated.
- `novelty_score` and `staleness_penalty_score` reuse existing detector `status` and `days_active` wherever possible.
- The formula shape, component definitions, signs, and v1 weights are frozen in `config/gap_engine.yaml` for the holdout.
- Thresholds such as minimum severity and ADV tier can be config values, but changes require a version bump.
- Every score component is stored in scalar columns for `gap_episodes` and `gap_holdout_daily`; `tension_components_json` is only a redundant compact payload for reporting.
- `scoring_config_version` and `scoring_config_hash` are stored for promoted episodes and ignored controls so holdout rows remain reproducible after v2 changes.

The score is a triage tool, not a verdict. It decides what earns attention, not what is true.

---

## 9. Price Absorption Index V0

For each episode mark, compute a bounded absorption state.

V1 is explicitly provisional. Because gap-episode history does not exist yet, the default expected move is a **class-specific severity mapping**, not an analog-calibrated estimate.

```text
price_absorption_index =
  capped(realized_move / max(abs(expected_move), expected_move_floor))
```

Rules:

- Store `realized_move`, `expected_move`, and `expected_move_source` separately.
- `expected_move_source` is usually `severity_mapping` in v1.
- If `expected_move` is below the floor, classify as `insufficient_signal`.
- Cap/winsorize the index, e.g. to `[-2, 2]`, to avoid denominator blow-ups.
- Prefer ETF/proxy return for expression absorption and T2 return for country-state absorption; store both.
- Run an FX-decomposition diagnostic before letting raw ETF-vs-T2 basis feed expression quality.

V1 `severity_mapping` must be explicit, versioned, and class-specific:

```text
expected_move =
  direction_sign
  * class_base_expected_move[gap_class][horizon_bucket]
  * clamp(abs(source_severity_z) / severity_unit_z, min_multiplier, max_multiplier)
```

Defaults live in `config/gap_engine.yaml` and must include `class_base_expected_move`, `severity_unit_z`, `expected_move_floor`, `min_multiplier`, and `max_multiplier`. The build report must print the active values. Until `expected_move_source` is no longer dominated by `severity_mapping` / `neutral_default`, absorption states are useful tracking labels, not calibrated probabilities.

Expected move sources, in v1 priority order:

1. `severity_mapping`,
2. `triptych_prior` if the Triptych layer is implemented and PIT-clean,
3. `event_study` only when enough pre-existing event history exists,
4. `prior_episode` only after meaningful episode history exists,
5. `neutral_default` for diagnostic-only rows.

Classifications:

| State | Rule of thumb |
|---|---|
| `unabsorbed` | price moved <25% of expected path and no invalidation |
| `partially_absorbed` | price moved 25-75% of expected path |
| `absorbed` | price moved >=75% of expected path |
| `repriced_against` | price moved materially opposite the expected path |
| `decayed` | world-state gap faded before price moved |
| `insufficient_signal` | expected move too small or denominator not meaningful |

All formulas must be visible in the PRD/build report and versioned.

---

## 10. Episode Promotion Rules

Each day, `build_gap_episodes.py` reads the latest dislocation rows and promotes only rows that clear hard gates and enough soft score.

### Hard gates

- Governance scorecard is not red. Amber can proceed only if `config/gap_engine.yaml.governance_dimension_dependencies` shows the amber dimension is unrelated to every input required by the candidate.
- `dislocation_daily` has current rows for the as-of date.
- The country/sleeve has a usable returns surface.
- Realized daily country returns are sourced through `scripts.loop.loopdb.daily_country_returns()` / `returns_panel()`; no reimplementation of the `1DRet` backward-label shift.
- Forward-return variables are banned as signal inputs. The only allowed use of daily `1DRet` is the existing backward-labeled realized-return transform in `loopdb`.
- The episode has a preferred ETF/proxy or is explicitly marked `research_only`.
- Mechanism text is generated from deterministic templates by `gap_class` and signal values, not free-form LLM prose in v1.
- The episode has an identity key and does not duplicate an existing open episode.

### Soft gates

- `abs(severity)` exceeds detector threshold or episode is new/intensifying.
- Own-history context supports that the state is unusual.
- Price-state does not already show full absorption.
- Expression quality is not poor.
- Crowding is not extreme unless the mechanism is explicitly "crowding unwind."
- Catalyst or plausible absorption horizon exists.

### Deduplication and lifecycle identity

Episode identity:

```text
episode_key = entity | gap_class | direction | horizon_bucket
episode_instance = 1 + count(prior closed/expired/invalidated/void episodes with same episode_key)
gap_id_seed = episode_key | first_seen_date | episode_instance
gap_id = sha1(gap_id_seed)
```

Rules:

- `as_of_date` is never part of `gap_id`.
- `first_seen_date` is the first data as-of date on which the current episode instance passed promotion gates, not the wall-clock run date.
- Backfills and replays must use the scoring config hash that was live on each historical as-of date. They must not recompute historical `first_seen_date` using the current config.
- One open episode per `episode_key`; a new row is created only after the prior episode with that key has closed, expired, been invalidated, or been voided.
- Reopened episodes get a new `episode_instance` and new `gap_id`, even if the same country/class/direction reappears later.
- If a rerun sees the same `episode_key` and an open row exists, it marks that row and must not create a new instance.
- Same entity/direction but different gap class creates distinct episodes linked via `related_gap_ids`, not one merged mega-episode.
- Existing open episode gets marked, not duplicated.
- Intensifying episode updates marks and can raise `tension_score_current`, but `tension_score_at_open` remains frozen.
- Source dislocation ids may disappear from the latest `dislocation_daily`; that is not an error. It can indicate decay, absorption, or condition cleared.
- Episode closes when absorbed, invalidated, expired, or manually voided.
- Staleness auto-closes after the configured max age with no fresh source input.

### D8 and stewardship separation

D8 holdings/thesis stewardship rows are not eligible for the top-5 price-discovery gap ranking by themselves. They can annotate a gap episode or appear in a separate stewardship section.

### Research-only default

Episodes with no clean ETF/proxy expression are still built for research but are:

- excluded from the top-5 brief,
- not `paper_candidate`,
- eligible for later review when a better expression is added.

---

## 11. System Architecture

```text
Layer 0: Existing surfaces
  Data/asado.duckdb + Data/loop/asado_loop.duckdb
  returns, dislocations, market-implied, sovereigns, flows, graph, evidence, governance

Layer 1: Price-state builder
  scripts/loop/build_price_state.py
  -> price_state_daily + price_state_surface

Layer 2: Gap episode builder
  scripts/loop/build_gap_episodes.py
  reads dislocation_daily + price_state_daily + price_state_surface + world-state surfaces
  -> gap_episodes + gap_episode_expression + gap_episode_marks + gap_holdout_daily

Layer 3: Brief renderer
  scripts/loop/render_dislocation_brief.py
  assembles governance + Top Price-Discovery Gaps + detector body + existing sections

Layer 4: CoS surfaces
  cos_mockups/build_cockpit_data.py uses gap episodes for Today cards

Layer 5: Learning and validation
  gap_episode_autopsy
  holdout comparison of top-ranked gaps vs ignored dislocations
  optional pre-registration into hypothesis_ledger / thesis_ledger
```

### Loop insertion point

Add these steps after `build_dislocations`:

```text
build_price_state
build_gap_episodes
render_dislocation_brief
```

Then continue with `build_evidence_packs` in v1.

Rationale:

- `build_dislocations` depends on raw detector substrates.
- `build_price_state` depends on surfaces already built earlier in `loop_daily_job.py`: valuation, sovereign signals, market-implied signals, ETF flow signals, combiner scores, and live signal standing.
- `build_gap_episodes` depends on both dislocations and price state.
- The brief cannot be fully rendered by `build_dislocations` if it needs gap episodes; therefore rendering must be separated.
- Evidence-pack re-pointing to gap episodes is deferred from the critical path until the GDELT rate-limit behavior is explicitly updated.

---

## 12. Daily Brief Changes

Add a section near the top, after governance and before the full dislocation table:

```text
## Top Price-Discovery Gaps

1. Saudi Arabia long — ToT impulse not absorbed by ETF/FX
   - World-state: ...
   - Price-state: ...
   - Expression: KSA, liquidity tier, ADV, currency basis ...
   - Absorption: unabsorbed, 6 days active, provisional severity-mapped denominator
   - What would prove this wrong: ...

2. ...
```

Rules:

- show top 3-5 non-`research_only` episodes by latest `tension_score_current`;
- apply an entity/direction deduplication pass before rendering the top 5: at most one headline slot per `entity|direction`, with related same-country episodes shown as sub-bullets unless the mechanisms are explicitly independent;
- include both FACT and INFERENCE labels where appropriate;
- show ETF/proxy expression;
- show currency basis;
- show absorption state;
- if `expected_move_source` is `severity_mapping` or `neutral_default`, label the absorption state as provisional in the brief and CoS;
- show invalidation rule;
- link to source dislocations and related gap ids;
- do not call anything a trade unless it is a `paper_candidate` or thesis.

The full dislocation table remains below for auditability.

---

## 13. Chief-of-Staff Cockpit Changes

The CoS Today cards should be driven by `gap_episodes`.

Default promotion order:

1. governance exception if any dimension is red/amber and relevant;
2. highest tension open non-`research_only` gap episode;
3. newest high-tension non-`research_only` episode;
4. major episode autopsy if one closed since last run;
5. open paper thesis requiring stewardship, shown in a separate stewardship lane.

Country letter changes:

- show active gap episodes for that country;
- show preferred ETF/proxy and expression quality;
- show currency basis and raw/FX-adjusted ETF-vs-T2 basis where available;
- show price absorption path;
- show "what would prove this wrong";
- show prior autopsies for the same gap class where available.

Single-signal view remains harness-owned. The CoS reports gap episodes; it does not adjudicate signal truth.

---

## 14. Interaction With Existing Ledgers

### Hypothesis ledger

Gap episodes are not automatically hypotheses. A gap episode can seed a `hyp_register` only when the user/agent proposes a generalized, testable signal rule.

Example:

- Gap episode: "Saudi ToT positive, ETF flat in stated currency basis, KSA expression clean."
- Hypothesis: "Countries with ToT z > 2 and ETF/T2 basis unabsorbed over 21d outperform over 21d/63d."

### Thesis ledger

Gap episodes are not automatically theses. A gap can become a paper thesis only when:

- it has a frozen direction and horizon,
- expression quality is acceptable,
- invalidation rule is concrete,
- expected absorption path is stated,
- and Arjun/agent explicitly opens a thesis.

### Calibration

Closed gap episodes should feed a separate calibration slice. They answer "did ASADO rank the right gaps?" even when no paper thesis was opened.

---

## 15. Validation Plan

### 15.1 Unit and schema tests

- `price_state_daily` schema validates.
- `price_state_surface` schema validates.
- `gap_episodes` schema validates.
- `gap_episode_expression` schema validates.
- JSON columns contain valid JSON.
- scalar ranking components are real columns in both `gap_episodes` and `gap_holdout_daily`, not buried only in JSON.
- duplicate detector rows collapse into one episode.
- `gap_id` does not change across daily marks for the same open episode.
- `episode_instance` increments on reopen after close, and reruns never increment while an open episode exists.
- `gap_id_seed` is stored and reproduces `gap_id`.
- `gap_holdout_daily.candidate_id` is reproducible from `date|episode_key|candidate_signature`.
- ignored controls carry the same scoring component columns and `scoring_config_hash` as promoted rows.
- stale input creates no green/valid episode.
- missing ETF mapping yields `research_only` and low expression quality.
- D9 ETF-vs-index basis appears in price state with `currency_basis`.
- forward-return variables are excluded as signal inputs except via `loopdb.daily_country_returns()` / `returns_panel()`.
- governance red prevents promotion unless explicitly allowed by test fixture.
- immutable claim fields cannot be rewritten after open.
- source dislocation no longer firing does not break open episode marks.
- D8 stewardship rows cannot occupy top-5 gap slots alone.

### 15.2 Plumbing smoke test

Backfill from existing `dislocation_daily` history beginning 2026-06-09. This is a plumbing test only, not ranking validation.

Assert:

- schemas valid;
- idempotent rerun per date;
- no duplicate storms;
- `gap_id` stable across dates;
- reopen fixtures create new `gap_id` only after close/expire/invalidate/void;
- already-resolved rows do not dominate;
- D8 holdings rows do not crowd out actual price-discovery gaps;
- expression fields populate from `config/etf_t2_map.json`, `config/etf_expression_overrides.yaml`, and `etf_prices_daily`;
- brief renders with no more than 5 top episodes.

### 15.3 FX decomposition check

Run a diagnostic on raw ETF-vs-T2 basis:

- regress `basis_gap_21d` on contemporaneous FX return or available currency series;
- if FX explains most of the basis, expression-quality scoring must use `fx_adjusted_basis_gap_21d` or label the raw basis as FX-driven;
- report this in the first `gap_engine_report`.

### 15.4 Absorption denominator audit

For the first 30 days:

- report distribution of `expected_move_source`;
- if most marks use `severity_mapping` or `neutral_default`, label absorption classifier provisional;
- do not claim analog-calibrated absorption until enough episode history exists.

### 15.5 Holdout trial

Freeze v1 scoring and run 90-180 days:

- each day write top 3-5 gap episodes;
- retain all eligible ignored dislocations as controls in `gap_holdout_daily`;
- freeze `candidate_id`, `candidate_signature`, score components, `scoring_config_version`, and `scoring_config_hash` for every promoted and control candidate;
- store a seeded `random_shadow_score`;
- score ETF/proxy returns and T2 country returns;
- track absorption half-life;
- compare top-ranked episodes to ignored controls and random shadow ranking.

Power expectation:

The first holdout will probably be thin. A 90-180 day window with 3-5 rendered gaps per day may create many daily marks, but overlapping horizons and repeated country episodes mean the effective independent sample is much smaller. The first formal verdict requires at least 80 closed promoted episodes at the evaluated horizon and at least 3x as many eligible control candidates. Before that threshold, reports can show diagnostics but must label the ranker `INCONCLUSIVE_SAMPLE`.

Pre-registered success criteria:

- top-quintile `tension_score_at_open` episodes show higher 21d/63d absorption in expected direction than eligible controls;
- ranking IC is positive with Newey-West t-stat > 2 over the holdout window or the closest feasible equivalent if sample remains thin;
- high `tension_score_at_open` predicts faster or larger absorption;
- autopsies show a meaningful share of `success_with_absorption`;
- poor expression/crowding/FX-basis flags explain a meaningful share of misses;
- CoS daily Today cards become more focused than raw dislocation ranking.

Failure criteria:

- top-ranked episodes do not outperform ignored controls;
- random shadow ranking absorbs as fast as `tension_score_at_open`;
- `tension_score_at_open` has no relationship to absorption;
- most autopsies are `price_already_knew`, `mechanism_wrong`, `rational_price_inertia`, or `fx_or_currency_basis_explained_gap`;
- ETF expression quality fields are too sparse or noisy to use.

Inconclusive criteria:

- fewer than 80 closed promoted episodes exist at the evaluated horizon;
- fewer than 3 eligible controls exist per closed promoted episode;
- ranking IC Newey-West t-stat is between -2 and +2 and random shadow is not clearly worse;
- expected-move sources remain dominated by `severity_mapping` / `neutral_default`.

If the holdout is inconclusive, the engine may continue rendering a clearly labeled **pilot** Top Price-Discovery Gaps section, but it must not claim validated ranking skill, use the ranker as a `paper_candidate` trigger, or feed `build_combiner.py`. A second frozen holdout window or an explicit v2 config bump is required before the ranker can be called validated.

Where possible, route holdout evaluation through the existing skeptic harness patterns (Newey-West, PIT, and explicit trial accounting) rather than inventing a separate scoreboard.

---

## 16. Implementation Plan

### Phase A — PRD and scaffolding

- Finalize this PRD.
- Add schema docs and tests for all new tables.
- Add `config/gap_engine.yaml` with score weights, thresholds, ADV tiers, severity-to-expected-move mapping, expected-move floors, index caps, max age, governance dimension dependencies, holdout power thresholds, and config version.
- Add required `config/etf_expression_overrides.yaml` with expense ratios, optional manual proxy notes, and any known expression caveats. Liquidity tiers are derived from ADV, not hand-entered.
- Add mechanism templates by `gap_class`.

### Phase B — Price-state builder

- Build `scripts/loop/build_price_state.py`.
- Populate `price_state_daily` and `price_state_surface` from T2 returns via `loopdb.returns_panel()`, ETF prices, market-implied signals, sovereign signals, valuation, flows, prediction markets, and live signal standing.
- Include currency-basis labels for ETF-vs-T2 basis.
- Derive ADV and liquidity tier.
- Add a `--check` mode and fixture tests.

### Phase C — Episode builder

- Build `scripts/loop/build_gap_episodes.py`.
- Promote from `dislocation_daily`.
- Mark existing open episodes.
- Enforce `episode_key` / `episode_instance` / `gap_id_seed` lifecycle semantics.
- Enforce historical config pinning on replay/backfill so `first_seen_date` and `gap_id` remain stable.
- Create expression rows for primary and alternate ETF/proxy choices.
- Create autopsies for resolved/expired episodes.
- Write `gap_holdout_daily` with reproducible `candidate_id`, `candidate_signature`, scalar score components, config hash, and random-shadow score.
- Write parquet artifacts under `Data/loop/gap_engine/`.

### Phase D — Brief rendering integration

- Change `build_dislocations.py` so it can persist detector output without being the final brief assembler, or have it write a detector-body artifact.
- Add `scripts/loop/render_dislocation_brief.py` after `build_gap_episodes`.
- The renderer assembles governance, Top Price-Discovery Gaps, the detector body, and existing brief sections.
- Apply entity/direction deduplication before the top-5 render, with related same-country episodes shown as sub-bullets.
- Render provisional absorption labels whenever `expected_move_source` is `severity_mapping` or `neutral_default`.
- Add expected outputs to `config/governance_contract.yaml`.
- Keep full dislocation section below the gap section.
- Keep evidence-pack selection unchanged in v1 unless a separate GDELT-rate-limit-safe change is made.

### Phase E — CoS cockpit integration

- Update `cos_mockups/build_cockpit_data.py` to select Today cards from gap episodes.
- Add focus fields for expression quality, currency basis, absorption, and invalidation.
- Keep D8/the thesis book in a stewardship lane.
- Keep harness verdicts harness-owned.

### Phase F — Holdout and calibration

- Freeze v1 weights and config hash.
- Start 90-180 day holdout.
- Add monthly `gap_engine_report_YYYY_MM.md` / `.xlsx`.
- Include FX decomposition, expected-move-source distribution, holdout power / closed-episode count, top-vs-control results, random-shadow comparison, inconclusive/proceed/fail verdict, and autopsy mix.
- Use autopsies to tune v2 only after the holdout window or explicit version bump.

---

## 17. Acceptance Criteria

The build is complete when:

1. `price_state_daily`, `price_state_surface`, `gap_episodes`, `gap_episode_expression`, `gap_episode_marks`, `gap_episode_autopsy`, and `gap_holdout_daily` exist in `Data/loop/asado_loop.duckdb`.
2. The loop can run end-to-end with the new steps.
3. Governance reports the new steps in the run manifest.
4. The daily brief is assembled by the new renderer and shows no more than 5 top price-discovery gaps above the full dislocation table, after entity/direction deduplication.
5. Each top gap includes world-state, price-state, ETF expression, currency basis, absorption state with provisional label when required, and invalidation rule.
6. Existing dislocation rows remain available and unmodified for auditability.
7. CoS cockpit Today cards can be driven from gap episodes.
8. A plumbing smoke backfill from current `dislocation_daily` produces plausible episodes and no duplicate storms.
9. Tests cover schema, gating, dedupe, stable `gap_id`, reopen sequencing, stored `gap_id_seed`, historical config replay pinning, missing ETF expression, red/amber governance dependency behavior, immutable fields, FX basis labeling, provisional absorption labels, top-5 entity/direction deduplication, and D8 separation.
10. A holdout plan is initialized with frozen v1 scoring metadata, reproducible `candidate_id`/`candidate_signature`, scalar component columns for promoted and control rows, random-shadow controls, and explicit proceed/fail/inconclusive thresholds.

---

## 18. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Episode layer becomes another unvalidated signal zoo | High | Freeze v1 scoring, holdout top gaps vs ignored controls, keep harness/ledger separate |
| `gap_id` creates daily duplicates instead of lifecycle episodes | High | Hash excludes as-of date; one open episode per `episode_key`; tests enforce stability |
| ETF-vs-T2 basis is really FX | High | Carry `currency_basis`, run FX decomposition, do not treat raw basis as expression quality until adjusted |
| Tension score hides too much judgment | High | Additive normalized components, frozen weights, component columns, config hash |
| Absorption denominator is fictional at launch | High | Store numerator/denominator/source, use severity mapping honestly, cap index, audit expected-move source |
| Inconclusive first holdout gets over-interpreted | High | Require minimum closed promoted/control counts; label pilot ranker until proceed/fail threshold clears |
| Replay with current config changes historical episode IDs | High | Store config hash and require historical config pinning in all replays/backfills |
| ETF expression metadata is incomplete | Medium | Add required overrides config; derive ADV/liquidity from ETF prices; bid/ask v2 only |
| Price-state vector overfits by using too many surfaces | Medium | Use compact scalar fields + per-surface child; no hidden trained composite in v1 |
| Episodes duplicate dislocations and create noise | Medium | Deduplicate by episode key; cap brief to top 5; entity/direction dedup in renderer; link cross-class collisions |
| Amber governance handling is subjective | Medium | Configure gap-input dependencies by governance dimension and test amber proceed/fail cases |
| D8 holdings stewardship crowds out gaps | Medium | Structural separation from top-5 gap ranking |
| Autopsy labels become subjective prose | Medium | Controlled vocabulary plus optional notes; auto-defaults where possible |
| CoS starts adjudicating truth | Medium | CoS reports episode state and harness verdicts; it never writes verdicts |
| Evidence packs exceed GDELT limits after re-pointing | Medium | Do not re-point in v1 critical path; preserve cap and abort behavior |
| Costs get over-modeled relative to ETF reality | Low/Medium | Treat costs as ETF expression drag and liquidity/crowding context, not dominant hurdle |

---

## 19. Settled Defaults And Open Questions

### Settled for v1

1. `research_only` episodes are built but excluded from the top-5 brief and never `paper_candidate`.
2. D9 ETF-vs-index gaps are price-state diagnostics in v1; standalone G6 ranked episodes require persistence and FX-basis review.
3. G8 prediction-market disagreement is diagnostic-only in v1.
4. Backfill is plumbing-only; ranking validation is forward holdout.
5. Brief rendering is a separate step after `build_gap_episodes`.
6. `bid_ask_spread_bps` is v2/optional and not a gate.

### Still open

1. What exact v1 weights should `config/gap_engine.yaml` use?
2. What ADV thresholds define high/medium/low ETF liquidity tiers?
3. What expected-move floors and caps should be used per gap class?
4. What is the minimum horizon set? Default: 5d, 21d, 63d, plus 126d for slow macro gaps.
5. Should Triptych priors enter `validation_prior` in v1? Default: optional if the Triptych PRD lands first; neutral otherwise.
6. Should autopsies be fully automatic in v1 or require human/agent review for the first month? Default: automatic label plus reviewable notes.

---

## 20. One-Line Summary

Build the layer that turns ASADO from "a brief full of dislocations" into "a governed register of price-discovery gaps": world-state vs price-state, ETF/proxy expression with explicit currency basis, absorption path, invalidation, holdout controls, and autopsy.
