# Sakana Fugu Ultra Brief: ASADO As A Price-Discovery Gap Machine

## Problem Statement

The user's clarified north-star question is:

> What does the data know that the price has not yet figured out?

They want a high-level but deep conceptual review of the entire ASADO repo and better ideas for leveraging the formidable database and daily update they have built. The request is not "add more data" in the abstract. The request is: how should ASADO turn its already-large live database, daily loop, graphs, market-implied surfaces, ledgers, and governance layer into an epistemic machine that detects the gap between observable world-state and prices.

This is finance/research design, not investment advice. Keep human judgment in the loop, do not propose live trade execution, and distinguish validated evidence from hypotheses.

## Current ASADO Shape

Repo root: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO`

ASADO is a 34-country country-equity macro research platform. It has crossed from "data collection project" into "small research institution":

- Main warehouse: `Data/asado.duckdb`, currently about 3.8 GB, 36 tables and 6 views.
- Persistent loop/research DB: `Data/loop/asado_loop.duckdb`, currently about 103 MB, 44 tables and 1 view.
- Monthly cadence: `scripts/monthly_update.py` collects/rebuilds the warehouse/graph/docs.
- Daily cadence: `scripts/daily_update.py` and `scripts/loop/loop_daily_job.py` update T2/GDELT daily returns, Bloomberg-derived surfaces, graph features, dislocations, ledgers, evidence packs, calibration, governance.
- The warehouse is rebuildable. Persistent alpha/research surfaces belong in `Data/loop/asado_loop.duckdb` and parquet-first `Data/loop` / `Data/work/loop` artifacts.
- Returns are the outcome source of truth. Explanatory data must be joined back to country/factor return surfaces before performance claims.

## Live Surfaces Checked

Main DB key stats from the current environment:

- `feature_panel`: 3,543,793 rows, 730 variables, dates 1950-12-01 to 2100-12-01, 43 countries/sleeves.
- `unified_panel`: 2,572,927 rows, 431 variables.
- `normalized_panel`: 970,866 rows, 299 variables.
- `t2_factors_daily`: 35,640,126 rows, 111 variables, 34 countries, through 2026-06-17.
- `t2_levels_daily`: 15,355,488 rows, 48 variables, through 2026-06-17.
- `gdelt_factors_daily`: 10,172,528 rows, 75 variables, through 2026-06-11.
- `factor_returns`: 106,036 rows, monthly factor portfolios through 2026-05.
- `factor_returns_daily`: 1,319,782 rows, daily factor portfolios through 2026-06-17.
- `ff_factors`: 539,920 rows, isolated regional Fama-French benchmark surface.
- `jst_macrohistory`: 83,725 rows, isolated long-cycle calibration corpus.
- `predmkt_daily`: 2,372 rows; `predmkt_signals_daily`: 566 rows.
- `event_log`: 146 curated events.

Loop DB key stats:

- `country_returns_monthly`: 10,487 rows, 34 countries, 2000-02 through 2026-05.
- `dislocation_daily`: 454 rows, 2026-06-09 through 2026-06-16.
- `graph_features_daily`: 1,325,281 rows, 7 variables, 31 countries, through 2026-06-16.
- `graph_features_pit_daily`: 1,840,757 rows, 10 variables, 31 countries, through 2026-06-16.
- `similarity_features_daily`: 451,987 rows, 2 variables, 34 countries.
- `leadlag_features_daily`: 357,228 rows, 2 variables, 34 countries.
- `combiner_scores_daily`: 166,701 rows, 1 live score, 31 countries, from 2005-01-03 through 2026-06-16.
- `market_implied_daily`: 987,566 rows, 23 variables, 31 countries, through 2026-06-19.
- `market_implied_signals`: 981,079 rows, 24 variables, 31 countries, through 2026-06-19.
- `sovereign_daily`: 453,822 rows, 4 variables, 33 countries, through 2026-06-19.
- `sovereign_signals`: 372,072 rows, 4 variables, 31 countries, through 2026-06-19.
- `valuation_monthly`: 128,472 rows, 12 variables, 34 countries, through 2026-06-30.
- `consensus_daily`: 922,233 rows, 2 variables, 34 countries.
- `consensus_signals`: 14,057 rows, 2 variables, 34 countries.
- `eco_surprise_monthly`: 33,153 rows, 8 variables, 34 countries.
- `eco_surprise_signals`: 27,955 rows, 6 variables, 33 countries.
- `etf_flows` / `etf_flow_signals`: 415k / 545k rows, through 2026-06-19.
- `cot_weekly` / `cot_signals`: 38k / 12.5k rows.
- `foreign_flows_daily`: 57,926 rows, 6 countries.
- `tot_trade_shares`: 204 rows, all 34 countries.
- `weo_revisions`: 15,163 rows.
- `harness_results`: 88 rows.
- `hypothesis_ledger`: 58 rows.
- `thesis_ledger`: 3 theses; `thesis_marks`: 26 marks.

## Current Nightly Loop

`scripts/loop/loop_daily_job.py` currently orchestrates 33 steps:

1. holdings/news bridge
2. thesis marks
3. country returns
4. terms-of-trade shares
5. graph features
6. forward calendar
7. foreign flows
8. sovereign daily
9. valuation block
10. WEO vintages
11. ETF flows
12. ECFC consensus
13. COT
14. market-implied stress
15. BQL sovereign ratings
16. economic surprise
17. PIT graph features
18. fundamental twins
19. lead-lag features
20. ridge combiner
21. Neo4j graph write-back
22. dislocation engine
23. cross-source consistency check
24. GDELT evidence packs
25. ledgers fold
26. calibration report
27. JST tail-risk report

The actual script has the full 33 item list and includes bounded subprocesses, a singleton flock to prevent self-collision, and governance tail steps.

Latest governance scorecard checked:

- As of `2026-06-21T13:34:58`
- Overall: GREEN
- Dimensions green: run_manifest, liveness, ledger_integrity, family_registry, pit_lag_proof, cross_source_minimal, config_guard.
- Note: the repo worktree is dirty from unrelated work, but trust-root YAMLs are committed and config_guard is green.

Latest run manifest checked: all 34 listed steps were status `ok`.

## Existing Conceptual Architecture

ASADO's existing PRD frames the model's edge as five things the optimizer cannot see:

1. Conjunctions across subsystems.
2. Conditionality by regime.
3. Propagation across graph edges before endpoint prices react.
4. Discrete events mapped to mechanism and analog history.
5. The gap between what data knows and what markets have priced.

It has seven archetypes:

- A1 terms-of-trade impulse without repricing.
- A2 two-hop graph propagation.
- A3 revision momentum quadrants.
- A4 cross-asset incoherence.
- A5 attention without resolution.
- A6 prediction-market vs sovereign-market disagreement.
- A7 factor crowding.

The loop produces `dislocation_daily` and the nightly brief. Layer 2 reasoning is supposed to see the compact dislocation table/brief, not raw panels. Layer 3 validation is the skeptic harness plus append-only ledgers.

The governance/Chief-of-Staff PRD says: pipeline as constitution, agent as colleague. The deterministic substrate owns adjudication; the conversational agent explains, synthesizes, prioritizes, and routes work.

## Current Brief Evidence

Latest brief file checked: `Data/dislocations/brief_2026_06_16.md`

It contains:

- Governance scorecard.
- Regime context.
- 81 dislocation rows across D1, D2, D3, D4, D5, D7, D8, D9, D10.
- D6 prediction-market disagreement is still blocked/accumulating.
- New examples:
  - D7 crowded factor flags: Best EPS 252_CS, 10Yr Bond_CS, MCAP_CS.
  - D2 graph propagation shorts: Korea, Taiwan.
- Persisting examples:
  - D1 ToT deteriorating and not repriced: Mexico, U.K., Germany, Turkey.
  - D1 ToT improving and not repriced: Saudi Arabia, Canada, NASDAQ, U.S., Australia.
  - D2 graph propagation longs: Malaysia, Hong Kong, Vietnam.
  - D3 WEO/revision long: Vietnam.
- D8 now maps live holdings and open paper theses to country risk/stewardship.
- Forward calendar, market-implied stress, sovereign curves/ratings/macro surprises, foreign flows, ETF positioning, short interest, COT, prediction-market sections, JST tail context.

This already looks like an institutional morning brief; the problem is deciding what deserves human attention and what is truly unpriced.

## Harness State

`harness_results` verdict counts:

- WATCH: 2
- WEAK: 39
- DEAD: 31
- INSUFFICIENT_COVERAGE: 16

Strong but still trial-penalized daily families:

- `ml_combiner_2026_06`: mean IC about 0.057, NW-t about 10.7, still WEAK because deflated Sharpe is negative and components were selected in-sample.
- `leadlag_2026_06`: mean IC about 0.057, NW-t about 8.5, WEAK.
- `graph_trade_gap`: multiple WEAK results; PIT variants survive with NW-t around 4 to 5+.
- `fund_similarity_2026_06`: WEAK around NW-t 5.6 for some variants.

Known caution:

- The old momentum sanity WATCH is not necessarily a live alpha idea; it is a diagnostic/cautionary artifact around forward-return traps and ledger state.
- Nothing survives 25 bps one-way costs; a few daily signals clear at 10 bps or 5 bps in prior cost-model work. Execution costs and hold period are central.

## Fresh Regime Thread

A new contrarian regime strategy report (2026-06-21) found that raw cross-sectional posterior ranks lose money, while within-country own-history calibration works:

- Best tested: `TS_Q25_LS_P`, long countries with high `P_adverse` relative to their own prior 24-month history and short bottom quartile.
- Gross annualized about 5.4%, Sharpe about 0.72, net 10 bps Sharpe about 0.62.
- Conceptual reading: this is a bad-news-priced-in / rebound overlay, not an early-warning risk-off system.

This suggests ASADO should often ask: "Is this country unusual relative to itself, and has price not absorbed that state?" not merely "which country ranks highest cross-sectionally?"

## Existing Tools / Interfaces

- `scripts/asado_mcp_server.py` exposes MCP tools: `ask_asado`, schema summary, read-only SQL, Neo4j Cypher, country profile, event window, daily factor series, country returns, factor return series, commodity prices, prediction-market snapshots, country signal now, event market set, FF factor series.
- `scripts/db_bridge.py` gives programmatic access.
- Streamlit app and Perspective lab exist.
- `cos_mockups/` contains a Chief-of-Staff cockpit concept and live data builder:
  - persistent left: map, live signals, dislocations.
  - dynamic focus panel: overview, country letter, signal registry, single-signal IC, brief, governance, long-cycle tail.
  - chat footer as conversation surface.
  - selection intelligence rules rank what gets shown.

## What We Need From Fugu Ultra

Please do ensemble-style work. Generate independent conceptual hypotheses first, then converge.

Specific question:

**Given ASADO's current architecture and live data surfaces, what is the best conceptualization of "what the data knows that price has not yet figured out," and how should ASADO be organized to detect, score, explain, and learn from that gap?**

Please cover:

1. A crisp conceptual model for the repo: what ASADO is trying to become.
2. The most valuable "unpriced knowledge" classes ASADO can mine from existing surfaces.
3. New and better ideas for leveraging the daily update and database without just adding generic feeds.
4. How to rank daily situations for human attention.
5. How to turn dislocations into hypotheses/theses without letting models HARK or overfit.
6. What dashboards/agent workflows are most natural given the Chief-of-Staff cockpit direction.
7. Missing loops: where the current machinery fails to learn from outcomes, costs, or price absorption.
8. Concrete next builds, grouped by high leverage / medium / speculative.
9. Risks, hidden assumptions, and failure modes.
10. A validation plan that would prove the next layer works.

Please avoid:

- Generic "use ML/LLMs" advice.
- Generic "add more data" advice unless it directly fills a known price-knowledge gap.
- Live trading/order-routing suggestions.
- Treating model commentary as evidence.
- Treating GDELT or prediction markets as truth without return-surface validation.

End with `RECOMMENDATION: PROCEED|REVISE|NEED_MORE_INFO`.
