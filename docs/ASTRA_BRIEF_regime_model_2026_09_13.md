# Research brief for Astra — using the ASADO dataset to model regimes and forward country returns

*Written 2026-09-13 for an outside researcher with Astra Pro. Paste everything below the line into Astra. The repository is public at https://github.com/ArjunDivecha/ASADO and current as of 2026-09-13. Astra can read the schema, inventory, documentation, experiment results and the research record; it cannot read the data files themselves, which are not in the repository.*

---

## Your role

You are a senior quantitative researcher asked to design — not run — a research program. The question is: **given the ASADO dataset, how could one train a model to identify regimes and predict forward country equity returns, and what would make that attempt succeed where five prior attempts failed?**

Everything you propose must be grounded in what the repository actually contains and must clear the record of what has already been tested and killed. This project's stated product is *trustworthy falsification*: most candidate signals are expected to die, and the discipline that kills them honestly is the asset. Treat that as the standard you are designing to.

## Read these first, in this order

1. `README.md` — the **Project status** section near the top, then **Warehouse contents**, then **The loop database**. This is the front door and its numbers were verified against the live databases on 2026-09-13.
2. `docs/DB_INVENTORY_2026_09_13.md` — every table and view in both databases plus the Neo4j graph, grouped by subsystem, with row counts, date ranges, variable counts and country coverage. Also the list of known stale surfaces.
3. `docs/factor_reference.md` — per-variable reference for the main warehouse (it does not cover the loop database; the inventory does).
4. `.claude/skills/asado-graveyard/SKILL.md` — the record of every research battle already settled. **Read this before proposing anything.**
5. The five prior regime experiments and their verdicts: `regime2.md`, `regime/results/regime_test_summary.md`, `regime_ew/results/RESULTS.md`, `regime_factor_selection/results/RESULTS.md`, `momentum_fragility/results/RESULTS.md`, and `docs/strategy/lessons.md`.
6. `.claude/skills/asado-research-protocol/SKILL.md` — how experiments are pre-registered, gated and recorded here.
7. `ledgers/hypothesis_ledger.jsonl` — the append-only ledger of every hypothesis registered and its verdict.

## What the dataset is

A 34-country equity universe (the "T2" universe: Australia, Brazil, Canada, Chile, ChinaA, ChinaH, France, Germany, Hong Kong, India, Indonesia, Italy, Japan, Korea, Malaysia, Mexico, Netherlands, Philippines, Poland, Saudi Arabia, Singapore, South Africa, Spain, Sweden, Switzerland, Taiwan, Thailand, Turkey, U.K., U.S., NASDAQ, US SmallCap, Vietnam, Denmark) held in two DuckDB databases and a Neo4j graph.

**The warehouse** (`Data/asado.duckdb`, 44 objects, ~79.5M rows): monthly macro, governance, risk, valuation and market factors from ~38 sources since 2000 (some series back to 1870), a daily extension of 111 T2 factors and 48 raw levels since 2000, GDELT news signals since 2015, World Bank commodities, Fama-French regional factors, JST macrohistory, IMF/BIS/OECD blocks, and the return surfaces.

**The loop database** (`Data/loop/asado_loop.duckdb`, 68 objects, ~13.6M rows): everything the nightly research engine collects and derives — daily sovereign 2Y/10Y yields and 1Y/5Y CDS (2005→), FX options-implied vol, risk reversals, butterflies and carry (2006→), country-ETF flows and short interest (2010→), Bloomberg ECFC consensus GDP/CPI with daily revision history (2007→), foreign equity flows for six markets, CFTC positioning, sovereign ratings history, economic-release surprises, IMF WEO vintages, point-in-time graph features from trade/banking/portfolio networks, lead-lag and fundamental-twin features, a walk-forward ridge combiner, and the full research record: hypothesis ledger, harness results, IC series, thesis marks.

**The graph** (Neo4j, 810 nodes, 21,486 edges): countries, factors, central banks, data sources, crisis events, sanctions programs, commodities; relationships for trade, banking exposure, portfolio holdings, crisis history, and nightly-written `LEADS` and `SIMILAR_TO` edges.

**Returns are the outcome source of truth.** Country returns (T2 total return index, daily and monthly) and factor-portfolio returns are the only thing a claim can be judged against. Every other layer is explanatory until joined back to returns.

## What has already been killed — do not re-propose these

Regime research is the single most-tested and most-killed family in this repository. Five directory-sized experiments and one branch are dead:

| Experiment | Question | Verdict | Why it died |
|---|---|---|---|
| `regime/` v2 | Do factor ICs vary across *global macro* regimes enough to condition on? | DEAD | Persistence 0.729 (needed ≥0.75); **0 of 52** factors significant after FDR; Sharpe Δ +0.078 with only 7% of 5-year windows beating baseline. Global macro regimes cannot reorder the cross-sectional country ranking. |
| `regime_loop/` | Let an optimizer tune a regime scheme until it passes. | DEAD (self-defeating) | Zero honest successes. An optimizer pointed at the pass/fail metric games the metric. |
| `regime_ew/` | Per-country HMM regime as an early-warning signal with walk-forward own-country return lead. | DEAD (Gate 3) | Full-sample fit looked significant; walk-forward showed **17 of 34** countries negative (needed ≥23), median ρ −0.003. The in-sample result was a look-ahead artifact. |
| `regime_factor_selection/` | Conditioned on each country's own IP regime, does any factor's rank-IC differ by regime? | DEAD (clean null) | **0 of 74** factors clear FDR at α=0.10; shuffled-label placebo collapses raw hits 18→8, confirming the machinery is calibrated. Pre-registered, placebo-confirmed. |
| `momentum_fragility/` | Within hot-momentum names, does fragility predict lower forward return? | DEAD (both variants) | ρ = −0.0135 core, **+0.03 (wrong sign)** full; needed ≤ −0.10. |
| Regime-knowledge branch (EF/HMM clustering) | Global stress probability as next-month alpha forecaster. | DEAD as forecaster | AUC for next-month negative return **0.46–0.47 — below random**. The surviving use is descriptive: same-month stress classification, next-month volatility and drawdown, rebound behaviour inside constructive regimes. |
| PCA-stacked cross-section analogs | Worldstate → PCA → analog → aggregate → backtest. | DEAD (NO-GO) | ~2,900-dim flat feature vector ≫ samples; sticky basis; IC ≈ 0. |

Also dead at the signal level: 12-1 cross-sectional country momentum (deflated Sharpe −0.13); four valuation-percentile signals (CAPE, ERP, dividend yield, earnings yield); nine first-order Bloomberg macro/FX signals (carry level and change, implied vol level and term, risk reversal, butterfly, 2s10s slope, growth and inflation surprise); ETF-flow positioning; consensus-revision momentum; and a ridge combiner built only from prior survivors (a combiner of survivors inherits their in-sample selection ceiling).

**The bar:** any regime proposal you make must state, explicitly, what axis of data or what structural choice differs from every entry in that table. "A better HMM on returns" or "macro fundamentals with a different clustering" does not clear the bar. What the dead five all share: they used macro fundamentals or return-series latent states as the regime axis, and asked the regime to condition or reorder factor returns.

## Two earned laws that govern every proposal here

1. **Distrust a searched pass.** Any result an optimization or tuning loop *found* is presumed false until re-derived from pre-registered, corrected inputs. A green metric a search process optimized toward is the thing the search was gaming.
2. **The second-order law.** First-order macro signals die in the harness (31 DEAD, disproportionately first-order). What has survived is *delayed second-order propagation*: a neighbour's return moving before the endpoint reprices — graph spillover, lead-lag, fundamental twins. This family carries an **unexplained sign flip in 2024–26**. That flip is a genuine open frontier; a proposal that explains or exploits it is welcome.

## Data facts you must design around

These are verified, not folklore. Designing around fictions is the fastest way to a fake result.

- **Forward returns are blacklisted as features.** `1DRet/5DRet/20DRet/60DRet/120DRet` and `1MRet/3MRet/6MRet/9MRet/12MRet` are optimizer *targets* labelled at window start. Using one as a predictor is look-ahead. Trailing momentum is the `*DTR_CS/_TS` family.
- **`1DRet` is a literal `0.0` on all 106,339 non-trading-day rows.** The T2 daily tables sit on a seven-day calendar grid with forward-fill on weekends. Any return or volatility statistic must first join `daily_calendar` on trading days.
- **`daily_calendar` lags one day by construction** — it is derived from a forward return, so the newest trading day always reads non-trading. A live feature vector built by joining the calendar silently drops today.
- **A third of the "daily" T2 variables are monthly content on a daily grid.** Measured on trading days over the last three years: `GDP` changes once a year, `Current Account` four times, `Bloom Country Risk` three times, `Inflation` ten, `REER` twelve — and the commodity *levels* `Oil`, `Gold`, `Copper`, `Agriculture` step only twelve times a year. Real daily commodity series are `market_implied_daily` `CMD_CL/CO/GC/HG/NG`, global not per-country. Valuation ratios move daily only because the price numerator does.
- **Genuinely fresh daily information that is orthogonal to the local equity price** (correlation of daily innovation with same-day local return, measured 2015→): Bloomberg ECFC consensus GDP and CPI revisions (+0.013 / −0.013; ~25 and ~23 revision events per country per year — an event-arrival series, not a continuous one); sovereign 10Y and 2Y yields (−0.06 / −0.05); FX 3M carry (−0.015); ETF 21-day flow z-score (+0.04). FX implied vol, risk reversals and CDS co-move with equity economically (−0.14 to −0.26) but still carry their own information. Graph, lead-lag and similarity features are 21/63-day *return gaps* and correlate with returns by construction (−0.4 to +0.5).
- **Sample size is the binding constraint on architecture.** A panel with all core daily features complete has **28 countries × ~4,063 trading dates from 2010-07** (94k country-days). The cross-section is correlated, so treat ~4,063 as the count of independent time points. Against a 20-day forward target that is ~200 non-overlapping windows in 16 years; against a 3-month horizon, ~64. Dropping ETF flows moves the start to 2006/07 with the same countries. Excluded from the complete panel: U.S., NASDAQ, US SmallCap (no USD carry), Vietnam, Hong Kong, Denmark.
- **Point-in-time.** The loop database's market data is market data — no restatement mechanism by nature — and the consensus series is Bloomberg's stored revision history. The monthly macro panel is subject to revision and there is a WEO vintage table for the IMF series. `graph_features_pit_daily` is the point-in-time graph surface; the v1 `graph_features_daily` was retired 2026-08-21 and should not be used.
- **Cost and turnover penalties are retired.** The old 25bp one-way cost law was retracted 2026-07-13. Judge signal quality gross. Do not propose killing or gating anything on cost or turnover. This matters for the record: **57 hypotheses sit at the WEAK tier**, and any whose only failing gate was the retired cost gate deserves a re-run under the gross gates.
- **Known stale surfaces:** `predmkt_resolutions` is empty; `release_events_*` stop 2026-07-10; `tariff_intensity_by_country` dead since 2026-07-01; prediction-market history began 2026-06-10 and is too short to backtest; 81 prediction markets have price history with no metadata row.

## An idea seed that is not in the repository — the Macro State Model

The owner has a design seed (in files not yet committed) inspired by the Macrosynergy note on gold and macro factors. The architecture, not the gold application, is the interest:

> many noisy raw variables → ~50–80 economically selected primitives → ~14–15 economic concepts (growth cycle level/momentum/expectations gap; monetary policy impulse; credit conditions; external vulnerability; valuation; flows and positioning; political/sovereign risk; …) → ~5–7 higher-level country states → one shared cross-country model with country-specific exposures → 3M/6M/12M expected country excess return or rank.

The hypothesis is that an explicit economic state layer, built first and then fed to a flexible model, beats a flat regularized model over hundreds of raw variables — because of lower effective dimensionality, economic inductive bias, better out-of-sample stability, interpretability, and the ability to learn interactions among meaningful states. **It may be wrong:** a flat regularized model may already extract everything. The design requirement is that the state model must *earn* its complexity against a flat baseline on identical samples and point-in-time-safe data. Treat this as one candidate program among those you propose, and critique it.

## What I want from you

Produce a written research design with these numbered sections. Be concrete: name tables and variables from the inventory; give numbers where a number decides something.

1. **Operational definitions of "regime."** Three to five candidates. For each: global or per-country; latent or observable; the exact data axis it uses; the horizon over which it is meant to be persistent; and **one paragraph on why it is not one of the seven dead entries above.** Steer toward the axes the dead ones never used: options-implied stress (`market_implied_*`), sovereign curve and CDS shape (`sovereign_*`), flows and positioning (`etf_flow_*`, `foreign_flows_daily`, `cot_*`), consensus revision arrival (`consensus_*`), graph topology and neighbour propagation (`graph_features_pit_daily`, `leadlag_*`, `similarity_*`). Say which candidates are meant as *predictors* and which are honestly *descriptive* (risk, volatility, drawdown) given the regime-knowledge branch's finding.
2. **Targets and horizons.** What exactly is predicted — return, rank, sign, volatility, drawdown, regime-transition — at what horizon, and the count of non-overlapping windows each gives on this panel.
3. **Model classes that fit 64–200 independent observations**, and what is ruled out by the sample-size fact. Address the Macro State Model hierarchy directly: what the flat baseline is, how the state layer is built without leakage, and what evidence would make it earn its complexity.
4. **Point-in-time and leakage risks specific to this dataset**, beyond the generic ones — the calendar lag, the forward-return family, the monthly-on-daily-grid variables, the revised macro panel, and any the inventory reveals to you that I have not listed.
5. **A pre-registered plan per candidate**: the gates, the kill criteria stated before any result is seen, the placebo or shuffled-label control, and which of the 57 WEAK entries you would re-run under gross gates first and why.
6. **What data is missing** that would materially change the answer, and whether it is obtainable at all.
7. **Your honest prior.** Given the record, what probability do you put on any of these producing a signal that clears WATCH, and which single candidate would you run first if only one could be run?

Do not flatter the dataset. If the right answer is "this record says regime prediction is dead on this universe and the effort belongs elsewhere," say that and say where.
