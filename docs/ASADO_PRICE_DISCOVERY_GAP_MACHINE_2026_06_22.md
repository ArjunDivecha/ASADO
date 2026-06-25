# ASADO Price-Discovery Gap Machine

Date: 2026-06-22

Input: repo inspection plus Sakana Fugu Ultra consult on `docs/SAKANA_PRICE_DISCOVERY_BRIEF_2026_06_22.md`

Sakana usage: `fugu-ultra`, response `resp-730f3f06e833`, 7,542 input tokens, 4,063 output tokens, 56,335 total tokens including 32,386 orchestration input tokens and 12,344 orchestration output tokens.

## Executive Conclusion

The right north star is:

> What does the data know that price has not yet figured out?

That means ASADO is not mainly a data warehouse, dashboard, signal zoo, or generic agent cockpit. It is becoming a **price-discovery gap machine**: a system that detects, freezes, explains, tracks, and autopsies the delay between observable world-state and market absorption.

The atomic unit should no longer be a factor, dislocation row, model score, or daily brief line. The atomic unit should be the **gap episode**:

```text
gap = world-state evidence - price-implied state
```

A good gap episode says:

- what changed in the world,
- what price has or has not absorbed,
- why the gap exists,
- what direction and horizon would close it,
- how to express it through the ETF/proxy universe,
- how much has already been absorbed,
- what would prove the mechanism wrong,
- and how the episode ended.

ASADO already has most of the raw machinery for this. The next leverage is to make the gap episode a persistent lifecycle object that sits between `dislocation_daily` and the ledgers.

## What ASADO Already Knows

The current repo already has a formidable split:

- `Data/asado.duckdb`: rebuildable warehouse, about 3.8 GB, 36 tables and 6 views.
- `Data/loop/asado_loop.duckdb`: persistent research/alpha system, about 103 MB, 44 tables and 1 view.
- Daily country/factor returns, market-implied FX/credit/rates, sovereign curves, ETF flows and short interest, foreign flows, COT, WEO/ECFC revisions, economic surprises, graph propagation, similarity twins, lead-lag features, prediction markets, evidence packs, and governance.
- A skeptic harness that kills most ideas: 2 WATCH, 39 WEAK, 31 DEAD, 16 INSUFFICIENT_COVERAGE in the current loop DB.
- A daily brief that already combines dislocations, holdings, forward calendar, market-implied stress, flows, short interest, ratings, macro surprises, and JST tail context.

The important implication: ASADO does not need "more data" as its default move. It needs a sharper answer to "which gap deserves attention today?"

## The Price-State vs World-State Split

ASADO should explicitly maintain two conceptual vectors per country:

**World-State Vector**

What the underlying reality says:

- terms-of-trade impulse,
- WEO and ECFC revision momentum,
- economic surprise path,
- graph-neighbor propagation,
- similarity-twin divergence,
- foreign investor flows,
- ETF positioning and short interest,
- COT commodity positioning,
- event calendar and evidence packs,
- long-cycle JST tail context,
- valuation and earnings fundamentals.

**Price-Implied Vector**

What markets appear to have absorbed:

- equity return over 1d/5d/21d/63d/120d,
- FX spot and FX-option stress,
- sovereign 2Y/10Y and CDS levels/slope,
- ETF flow/short-interest crowding,
- valuation percentiles,
- prediction-market probabilities,
- combiner score and live signal standing.

The central question becomes:

```text
Where is world-state moving faster than price-state, and can the gap be expressed cleanly through the country ETF/proxy universe?
```

## Best Existing Gap Classes

1. **Own-History Extremes Not Absorbed**

The fresh regime result is important: raw cross-country posterior ranking lost money, while within-country own-history calibration worked. That suggests the system should often ask whether a country is extreme relative to itself, not merely high or low versus peers.

2. **Terms-of-Trade vs Equity/FX Inertia**

D1 already captures this shape. The next step is to measure how much of the commodity/import/export impulse has been absorbed by equity and FX, not just whether the detector fired.

3. **Graph Propagation Latency**

The strongest families are graph, lead-lag, similarity, and combiner. They are not clean capital-grade yet, but they repeatedly suggest that the repo's edge is delayed second-order propagation, not obvious first-order macro.

4. **Consensus/Revision Acceleration vs Price Inertia**

WEO, ECFC, and economic-surprise surfaces are ideal for "the analyst community is changing its mind, but price has not" episodes. These need careful horizon rules and own-history calibration.

5. **Cross-Asset Incoherence**

Equity, FX options, CDS, yield curves, valuation, flows, and prediction markets should be collapsed into a price-state summary. A true opportunity is not simply "macro says X"; it is "macro says X while price surfaces disagree or remain asleep."

6. **ETF Expression And Flow/Crowding Overlays**

ASADO's natural implementation surface is not a hard-to-trade local basket; it is liquid country ETFs and broad-market sleeves. That means cost should not dominate the design. The right use of the ETF layer is to answer: can this gap be expressed cleanly, is the ETF itself behaving differently from the T2 country index, and are flows/short interest telling us the expression is crowded or under-owned?

7. **Event With No Resolution**

The event calendar and evidence packs should not become raw news prediction. Their best role is to explain why an already-detected gap might close soon.

## The New Core Object: `gap_episodes`

Keep `dislocation_daily`. It is useful. But promote only the best dislocations into persistent gap episodes.

Proposed loop-owned tables:

### `gap_episodes`

One row per frozen episode.

```text
gap_id
opened_at
as_of_date
entity
direction
horizon_days
source_dislocation_ids
world_state_json
price_state_json
mechanism_text
validation_prior
estimated_cost_bps
expression_ticker
expression_type
expression_quality
etf_ownership_drag_bps
liquidity_tier
tension_score
absorption_state
expected_absorption_path_json
invalidation_rule
status
closed_at
close_reason
```

### `gap_episode_marks`

One row per gap per day.

```text
gap_id
date
realized_return
price_absorption_index
unabsorbed_fraction
days_active
current_cost_bps
expression_quality
crowding_penalty
notes_json
```

### `gap_episode_autopsy`

One row when an episode closes.

```text
gap_id
outcome
mechanism_verdict
price_absorbed
absorption_half_life_days
net_return_after_costs
net_return_after_etf_drag
failure_class
lessons
```

Failure classes should include:

- data was wrong or revised,
- data was right but price never cared,
- price already knew through another surface,
- mechanism wrong,
- horizon too short,
- ETF expression was poor or unexpectedly wide,
- ETF ownership drag mattered over the horizon,
- crowded expression,
- true gap but untradable,
- success with absorption.

## ETF-First Implementation Lens

The plan should assume ASADO is primarily trading and owning ETFs, not local securities. That changes the role of implementation costs:

- **Costs are a sanity check, not the thesis.** For liquid ETFs, the question is not "does this theoretical signal survive punitive friction?" but "is the gap large and persistent enough to matter in the ETF expression after normal ETF spread/ownership drag?"
- **Expression quality becomes first-class.** Every gap episode should know its preferred ticker, proxy type, liquidity tier, expense ratio/ownership drag, and whether the ETF historically tracks the T2 country return closely enough.
- **ETF-vs-index gaps are information.** D9 should be treated as a price-state diagnostic: if the country index and its ETF diverge, ASADO should decide whether that is a data issue, timezone issue, liquidity basis, or an actual investable expression gap.
- **Crowding matters more than raw cost.** ETF creations/redemptions, short interest, and foreign-flow proxies should say whether the ETF expression is already crowded, not merely whether it is expensive to trade.
- **Holding-period fit matters.** ETF ownership costs are small over days/weeks but matter over longer horizons; the episode should carry the expected holding period and ownership drag instead of a one-size-fits-all cost haircut.

## Price Absorption Index

The daily loop should stop asking only "did this fire?" and start asking:

```text
How much of the world-state move has price absorbed?
```

For each gap episode, compute:

- **initial gap severity** at open,
- **price response so far** at 1d/5d/21d/63d,
- **expected response path** from historical analogs,
- **unabsorbed fraction**,
- **absorption half-life**,
- **repriced_with / repriced_against / decayed / unresolved**.

This turns the daily update into a lifecycle monitor. It also prevents stale repeated rows from occupying attention after the price has already moved.

## Tension Score

Human attention should go to top-ranked tension, not raw z-score.

Proposed first-pass formula:

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

Where:

- `gap_severity`: own-history z or detector-normalized severity.
- `novelty`: new/intensifying episodes beat old persisting rows.
- `validation_prior`: harness family standing, event-study support, or calibrated historical prior.
- `expression_quality`: preferred ETF/proxy exists, tracks the country sleeve well, and is liquid enough for normal execution.
- `catalyst_nearness`: forward calendar or expected absorption half-life.
- `etf_drag_penalty`: modest penalty for spread/expense/ownership drag, scaled to holding horizon rather than treated as the central obstacle.
- `crowding_penalty`: ETF flows, short interest, COT, factor crowding.
- `staleness_penalty`: elapsed time without absorption.
- `data_quality_penalty`: governance/coverage/input caveats.

The Chief-of-Staff should show only the top 3-5 daily gap episodes unless the user asks for the full registry.

## How The Chief Of Staff Should Think

The CoS should not say "buy Brazil" or "this signal is true." Its recurring interrogation should be:

1. What does world-state know?
2. What does price-state imply?
3. Is the gap new, large, and unabsorbed?
4. Is there a catalyst or plausible half-life?
5. What ETF/proxy expresses it most cleanly, and is that expression crowded?
6. What would prove the gap was never real?
7. What happened to prior episodes of this type?

The cockpit should therefore become a **Tension Map**, not a dashboard:

- left: world-state pressures,
- right: price-state absorption,
- center: gap episode, tension score, absorption path, and autopsy history.

## What Not To Do

- Do not turn every dislocation into a thesis.
- Do not let LLM commentary become evidence.
- Do not promote GDELT, Triptych, or prediction markets into truth surfaces. They are scouts or priors until harnessed.
- Do not optimize a hidden composite without an episode ledger. The repo has already learned that trial accounting matters.
- Do not assume price is wrong. Sometimes price is rationally ignoring slow data, demanding a risk premium, or accounting for political risk the panel does not capture.
- Do not over-index on punitive cost assumptions. ASADO is mainly expressing country views through ETFs that are generally cheap to trade and own; implementation should be modeled as expression quality, spread/expense drag, and crowding, not as the dominant research bottleneck.

## Concrete Build Sequence

### Phase 1: Gap-Episode PRD And Schema

Write `PRD_Price_Discovery_Gap_Engine.md`.

Define:

- the `gap_episodes` lifecycle,
- episode promotion criteria from `dislocation_daily`,
- Tension Score v0,
- price absorption index v0,
- autopsy schema,
- how episodes interact with `hypothesis_ledger` and `thesis_ledger`.

Do not replace the current dislocation engine. Add the episode layer above it.

### Phase 2: Episode Builder

Create `scripts/loop/build_gap_episodes.py` after `build_dislocations.py` and before evidence packs.

Inputs:

- latest `dislocation_daily`,
- `live_signals`,
- harness family counts,
- country/factor returns,
- market-implied signals,
- sovereign signals,
- ETF/foreign/COT flows,
- forward calendar,
- governance scorecard.

Outputs:

- `gap_episodes`,
- `gap_episode_marks`,
- daily brief section: "Top Price-Discovery Gaps".

### Phase 3: Price-State Vector

Build a compact `price_state_daily` table:

```text
date
country
preferred_ticker
proxy_type
expense_ratio_bps
bid_ask_spread_bps
tracking_gap_21d
tracking_gap_z
liquidity_tier
equity_state_json
fx_options_state_json
sovereign_state_json
flow_state_json
valuation_state_json
predmkt_state_json
market_implied_summary
```

This does not need to be fancy. It just needs to give the gap engine a consistent "what price knows" comparator.

### Phase 4: Autopsy Loop

Extend the ledger close/mark machinery to classify why episodes worked or failed.

Every closed episode should answer:

- did price absorb the data?
- was the direction right?
- did the ETF/proxy expression track the intended country gap?
- did spread/expense drag matter over the holding period?
- did another price surface already know?
- was the episode too stale?
- did the data revise?

This is where ASADO learns which kinds of "price ignored it" are real and which are mirages.

### Phase 5: Holdout Validation

Freeze Tension Score v0 and run a 90-180 day holdout.

Daily:

- write top 3-5 gap episodes,
- track ignored lower-ranked dislocations as controls,
- score ETF/proxy returns after normal spread and ownership drag assumptions,
- measure absorption half-life,
- compare top-ranked episodes against ignored dislocations.

Falsification:

- top-ranked episodes do not outperform ignored dislocations in the chosen ETF/proxy expressions,
- net deflated Sharpe remains negative,
- high tension predicts no faster absorption,
- autopsies mostly classify as poor expression, crowding, or rational price inertia.

## Immediate Next Moves

1. Write the PRD for the gap episode layer.
2. Add a read-only prototype that derives top gap episodes from the latest `dislocation_daily` without changing ledgers.
3. Add the "Top Price-Discovery Gaps" section to the brief.
4. Wire the CoS cockpit's Today cards to tension-ranked gap episodes instead of raw dislocations.
5. Start the 90-180 day holdout with frozen scoring.

## Recommendation

Proceed.

The repo has enough data. The daily loop is now robust enough. The governance scorecard is green. The right next layer is not another data source; it is a durable price-discovery episode system that tells Arjun, each morning:

> Here are the few places where ASADO's data appears to know something price has not absorbed, here is why, here is the cost hurdle, here is what would prove us wrong, and here is how similar episodes ended.

Revised ETF-first version:

> Here are the few places where ASADO's data appears to know something price has not absorbed, here is the cleanest ETF/proxy expression, here is whether that expression is crowded or drifting from the index, here is what would prove us wrong, and here is how similar gaps resolved.
