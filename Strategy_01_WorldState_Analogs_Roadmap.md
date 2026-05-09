# Strategy #1 — World-State Analogs for Country Selection

**Roadmap & experiment specifications**
**Author:** Arjun Divecha (with Claude)
**Created:** 2026-04-19
**Status:** Pre-build — design phase
**Depends on:** `asado.duckdb` (feature_panel, normalized_panel, bilateral_*), `Neo4j` knowledge graph, `countryStateIndex` vector index, `AsadoDB` Python bridge.

---

## 1. Thesis

At any date *t*, the joint state of the 34-country system — factor levels, bilateral trade and banking exposures, sentiment, regime variables — can be represented as a single high-dimensional object: a **world-state fingerprint**. History contains prior dates *t′* whose fingerprints are close to the one at *t*. The central bet is that **the forward return distribution following those historical analogs is informative about the forward return distribution following today**. Average the historical forwards, weight by analog similarity, and you get a cross-sectional ranking of countries that is grounded in mechanism rather than raw factor momentum.

The system you have already built is unusually well-suited to this: 332 variables × 34 countries × 25+ years of monthly data, plus a graph layer that most analog-forecasting setups never have. The ambition of this strategy is to exploit that graph layer — two world-states should only be called analogs if both their country-level factors *and* their bilateral network structure are similar.

The baseline to beat is your trailing 60-month factor momentum model at ~6.5% annualized. A successful analog strategy should produce information ratios competitive with or orthogonal to that benchmark.

---

## 2. Backtest protocol — the walk-forward discipline

This is the operating rule that everything else in the document serves. No step may be executed any other way.

At every decision date *t* in the backtest, the model is only permitted to see data with timestamp strictly less than *t*. Concretely:

1. **Analog library at *t*** = all world-state vectors `worldstate_{t′}` for `t′ < t − min_lag`, where `min_lag` is at least 1 month to avoid matching yourself and probably 12 months to keep an analog from being an autocorrelated neighbour.
2. **All transforms fit at *t*** — PCA components, scaler means/stds, any regime clustering, any graph embedding — are fit on data with timestamp `< t`. No transform that touched a future observation may be used.
3. **Forward-return computation uses the history the analogs lived through.** For analog date `t′`, the forward returns are `r_{t′+1}, r_{t′+3}, r_{t′+6}, r_{t′+12}` — these are known historically and it is correct to use them. The forbidden thing is using `r_{t+h}` (future returns from the decision date itself) anywhere in fitting or selection.
4. **Positions are formed at *t* and held** through the chosen horizon, with transaction costs on rebalance.
5. **Performance metrics** are computed strictly on the realised `r_{t+1}` series, *after* the model has committed.

### Worked timeline

Assume the library starts 2000-01 and the backtest starts 2005-01. Five years of burn-in is the minimum; eight years is safer.

| Decision date *t* | Analog library available | Top-k analog dates (illustrative) | Forward returns used for prediction | What we actually earn |
|---|---|---|---|---|
| 2005-01-31 | 2000-01 through 2004-01 (min_lag = 12m) | e.g. 2002-09, 2001-03, 2003-06 | 1m forward of each analog | Position held → realised `r(2005-02)` |
| 2005-02-28 | 2000-01 through 2004-02 | refit analogs | same | `r(2005-03)` |
| ... | library grows by one month each step | ... | ... | ... |
| 2020-03-31 | 2000-01 through 2019-03 | e.g. 2008-11, 2011-08, 2002-09 | same | `r(2020-04)` |
| 2026-03-31 | 2000-01 through 2025-03 | refit | same | `r(2026-04)` |

At no point does the search at *t* consider any date after `t − min_lag`. The library strictly grows with time. PCA, scaler, and any regime clustering are **re-fit** from scratch at each *t* on `< t` data — caching is fine, but the cache is keyed on *t*.

### Why the 12-month min_lag

A one-month lag is not enough. World-state vectors at adjacent dates are almost perfectly correlated by construction (most factors are slow-moving), so the nearest neighbour of *t* in an unconstrained search is almost always *t*−1. The effective "forward return" you'd be using is basically `r_t` itself, which is a look-ahead in disguise. A 12-month min_lag breaks autocorrelation for the macro block and most trade/banking statistics. Sensitivity to this choice (3m / 6m / 12m / 24m) is one of the Phase 2 sweep axes.

### Burn-in and library thickness

With `min_lag = 12m` and start = 2005-01, the first decision has ~48 months (≈ 48 candidates) of library. That's thin for top-10 matching. Options to handle this:

- Start the backtest at 2008-01 or 2010-01 with 96-120 candidates for the first decision.
- Or start at 2005-01 and explicitly degrade top-k to top-(N/5) early, reporting separate statistics for thin-library vs thick-library periods.
- Or accept that early-period performance will be noisy and report 2010+ as the headline number.

Which of these is right depends on whether Mythos's later expansion of the factor universe matters more (favouring a later start) or whether we want the 2008 crisis as an observation (favouring an earlier start). Default: start 2005-01, report 2005-2010 and 2010+ separately.

---

## 3. Conceptual framework

An end-to-end analog strategy has four moving parts, and each one is an experiment in its own right.

**(a) Representation.** How do we turn the world at time *t* into a vector (or a structured object) that captures what is actually relevant to forward returns? The naïve choice is to stack the 34-country × K-factor feature_panel into one long vector, but that throws away the graph structure and is too high-dimensional relative to ~300 monthly observations of history. Smarter choices compress the panel (PCA, autoencoder) or embed the whole graph (GNN pooling).

**(b) Similarity.** Given two world-state objects, how do we score "closeness"? Euclidean / cosine on a reduced vector is the starting point, but the graph layer lets you score structural similarity (Weisfeiler–Lehman kernel, graph embedding cosine) as a separate signal to combine.

**(c) Return extraction.** Once you have the top-k analogs for *t*, you compute forward country returns at each analog date and aggregate — typically a similarity-weighted mean or a full forward-return distribution per country. Choice of horizon (1m / 3m / 6m / 12m) matters a lot and should be an empirical question.

**(d) Portfolio construction and validation.** Turn expected returns (or rank scores) into weights, run through an Almgren-Chriss cost model, and backtest walk-forward from 2005 onward with strict point-in-time discipline — no leakage from factors that didn't exist or weren't normalized at decision time.

Everything below assumes monthly rebalancing on the same cadence as your existing T2 work, and the same 34-country universe.

---

## 4. Data surfaces you already have

The strategy is deliberately designed so that Phase 1 can be executed entirely against data that is already in your system.

`feature_panel` (DuckDB view) — the primary source: raw + normalized (`_CS`, `_TS`) factor rows from all six collectors. ~2.5M rows covering 1975-12 → 2031-12. At any historical date, filter by `date <= t` to guarantee no leakage.

`bilateral_trade_matrix`, `bilateral_banking_matrix`, `bilateral_portfolio_matrix` — edge weights for graph-based similarity. Trade is ~899 pairs monthly from IMF IMTS; banking is ~582 pairs from BIS LBS; portfolio is historical IIP from IMF CPIS. These are the raw material for Phase 5's graph similarity.

`Country.state_embedding` in Neo4j — the 34-d PCA embedding you already built per country. **Warning:** this is fit on the full panel and is therefore not point-in-time. Phase 1 uses it as a sanity check only; production runs require a walk-forward re-fit.

`countryStateIndex` — cosine vector index on country embeddings. Useful for country-level similarity now, but this strategy needs *world-state* similarity, which is a different object.

`HAS_CRISIS_HISTORY`, `SUBJECT_TO`, `EXPORT_EXPOSED_TO` — categorical graph edges. Phase 2 uses them for conditional analog filtering (e.g., "only match to analog dates where the same countries were under sanctions").

`t2_master` and the T2 factor system — historical country equity returns, which you will need as the dependent variable. Confirm this is indexed to the same month-end convention as `feature_panel` before Phase 4 starts.

---

## 5. Phased roadmap

Each phase produces an artifact — a notebook, a Parquet file, a short memo — that the next phase builds on. Phases 1-4 are the minimum viable backtest. Phases 5-7 are refinements that should only be attempted after the MVP has a verified positive out-of-sample result.

### Phase 0 — Baselines and leakage audit (1-2 days)

Before anything else, fix the target and the benchmark. Pull monthly total-return series for your 34-country universe from T2. Compute two benchmarks that the analog strategy must beat out-of-sample: (i) equal-weight rebalanced monthly, (ii) your existing 60-month trailing factor-momentum model. Also produce a naïve "cross-sectional factor rank today" model that uses no analogs, just the current normalized_panel snapshot; this isolates how much of the signal comes from analog matching versus the features themselves.

Separately, audit the point-in-time safety of every factor you plan to use. Many World Bank and IMF series are revised; forecast variables (`IMF_WEO_*`) are vintage-sensitive. For the MVP, restrict to variables whose values at historical date *t* are stable under later revisions. Flag the rest for Phase 6 treatment.

**Artifact:** `Data/strategy/analogs/baselines.parquet` with benchmark returns + `Data/strategy/analogs/PIT_audit.csv` listing factors as PIT-safe / PIT-unsafe / needs-lag.

### Phase 1 — Flat world-state vector and vanilla analog search (3-5 days)

Build the simplest possible version that can lose money. For each month *t*, construct a world-state vector by:

1. Pull the row from `normalized_panel` for all 34 countries at date *t*, keeping only the `_CS` columns (cross-sectional z-scores) to get within-date comparability.
2. Flatten to a (34 × K) vector, where K is the number of PIT-safe features.
3. Fit PCA on the history up to *t* only; take the top 20 components as `worldstate_t ∈ ℝ²⁰`.
4. Measure cosine similarity between `worldstate_t` and every `worldstate_t′` with t′ ≤ t − 12 months (the lag prevents matching to adjacent months that would leak).
5. Select top-k = 10 analogs, weight by `softmax(similarity / τ)` for some temperature τ.
6. For each country, compute the weighted average of forward 1/3/6/12-month returns across analog dates.
7. Rank countries, form quintile long-short, record returns.

Walk this forward month by month from 2005-01 through the most recent complete period. Plot cumulative returns, compute IR and Sharpe, compare to baselines.

This is the minimum viable backtest. Expect it to be mediocre on its own — the goal is to establish the pipeline and sanity-check every step (do the top analogs for March 2009 actually look like 2001-2002 or 1990? do they make sense?).

**Artifact:** `scripts/strategy/analog_mvp.py` + a run log showing one full walk-forward backtest + `docs/strategy/analog_mvp_results.md` with plots and interpretation.

### Phase 2 — Similarity metric sweep (2-3 days)

Holding the representation from Phase 1 fixed, sweep similarity metrics and aggregation choices. The variables to test are:

- **Metric:** cosine vs Euclidean vs Mahalanobis (the last requires estimating a covariance on the PCA components, which is cheap).
- **k:** 5, 10, 20, 50 analogs.
- **Weighting:** uniform, linear-in-rank, softmax, Gaussian kernel.
- **Temperature τ** for the softmax: sweep on a grid.
- **Minimum separation** between *t* and analog dates: 3m, 12m, 24m.
- **Horizon:** 1m, 3m, 6m, 12m for forward returns.

Report IR and turnover for each cell of the grid. The purpose is not to find the single best cell and declare victory (that's overfitting) but to understand which choices actually matter and which are second-order. The stable choices get locked in; the unstable ones become ensemble dimensions in Phase 7.

**Artifact:** `docs/strategy/similarity_sweep.md` with a heatmap of IR across the grid and a short commentary on which axes moved the metric.

### Phase 3 — Regime-conditional analogs (3-4 days)

The strongest objection to naïve analog matching is regime non-stationarity: 2006's world and 2024's world have such different monetary, geopolitical, and technological regimes that even if factor vectors look close, the forward return dynamics may be unrelated. Three ways to address this:

**3a. Regime filtering.** Use a coarse regime label per date (e.g., VIX-regime × Fed-cycle-regime × global-credit-regime → 3 × 2 × 3 = 18 buckets). Only allow analog matches within the same regime bucket. Check whether this improves OOS IR or just starves the model of matches.

**3b. Regime-adjusted distance.** Instead of filtering, augment `worldstate_t` with explicit regime variables (central bank policy rate z-score, VIX regime, USD index regime) given large weights in the distance metric. This softens the hard cut of 3a.

**3c. Conditional return distributions.** Rather than averaging forward returns across analogs, fit a conditional distribution `p(r_{t+h} | analogs)` and use quantile-based portfolio construction — go long countries where the 25th percentile of analog forward returns is positive, short where the 75th percentile is negative. This is robust to a few extreme analog matches and naturally expresses uncertainty.

**Artifact:** `docs/strategy/regime_analogs.md` with one-pager each on 3a/3b/3c and a recommendation on which to carry forward.

### Phase 4 — Proper walk-forward backtest with costs (3-5 days)

Lock in the winning choices from Phases 1-3 and run a rigorous walk-forward:

- PCA and any other transforms re-fit each month on `date <= t` data only.
- Transaction costs via the Almgren-Chriss model you already have, with VIX-regime conditioning.
- Subsample tests: pre-GFC (2005-2007), GFC (2008-2010), post-GFC (2011-2019), COVID (2020-2022), recent (2023-2026). A strategy that only works in one regime is not a strategy.
- Deflated Sharpe ratio (Bailey–López de Prado) to discount multiple testing across the Phase 2 grid. This is a **hard requirement** before claiming any positive result.
- Bootstrap confidence intervals on IR by resampling non-overlapping 12-month blocks.

If the deflated Sharpe is not significantly positive at this stage, stop. The remaining phases will not rescue a null result; they will just add degrees of freedom that inflate the in-sample number.

**Artifact:** `docs/strategy/phase4_oos_report.md` — the go/no-go document for Phases 5-7.

### Phase 5 — Graph-aware similarity (5-7 days)

Now bring in the asset you have that other analog investors don't: the Neo4j graph layer. Two concrete variants:

**5a. Structural kernel.** For each *t*, extract the bilateral trade and banking exposure matrices and summarize their structure via a Weisfeiler-Lehman graph kernel or a simple set of graph statistics (clustering coefficient, degree concentration, largest-cluster share, global trade intensity). Append these to `worldstate_t`. Re-run Phase 4.

**5b. Graph embedding.** Train a lightweight GNN (GraphSAGE or GAT) that takes the 34-country graph at time *t* (nodes = country factor vectors, edges = bilateral weights) and produces a graph-level embedding via pooling. The training target can be self-supervised (reconstruction) or directly supervised (predict 1-month-forward cross-sectional return rank). Use the embedding as `worldstate_t`.

5a is cheap and should be tried first. 5b is where the real capability jump is, and also where data-hunger bites (300 months is not much for a GNN). If 5b doesn't work, 5a probably captures most of the graph signal anyway.

**Artifact:** `scripts/strategy/graph_worldstate.py` + `docs/strategy/graph_vs_flat.md` comparing Phase 4 baseline to 5a and 5b.

### Phase 6 — Analog diagnostics and attribution (2-3 days)

Regardless of whether Phase 5 improved things, run diagnostic passes on whichever model won:

- **Analog face-validity.** For a handful of interesting dates (e.g., Jan 2008, March 2020, today), list the top-10 analogs and write one sentence each on whether the match is economically plausible. If Jan 2008's closest analog is 2003, something is wrong.
- **Feature attribution.** For a given analog match, which factors drove the similarity? Run a permutation importance pass on `worldstate_t` for each analog pair. Features that drive similarity in many analog pairs are the ones the strategy is actually betting on.
- **Country attribution.** Which countries' returns are driving the strategy's PnL? If the whole strategy is Turkey and Argentina, you have a concentration problem wrapped in an analog signal.
- **Drawdown forensics.** For the worst 5% of months, identify whether analogs were dense or sparse (low similarity → low confidence → positions should have been smaller). If drawdowns correlate with sparse-analog months, add a "similarity confidence" gate that cuts leverage when the closest analog is too far away.

**Artifact:** `docs/strategy/diagnostics.md` — for internal use, but also the basis for any investment-committee-style write-up.

### Phase 7 — Extensions and ensembling (open-ended)

If Phases 1-6 produce a live-grade signal, the following are candidate extensions, not a promised sequence:

- **Ensemble with your existing factor momentum.** If orthogonal, combine on the basis of predicted IRs.
- **Multi-horizon stacking.** Use 1/3/6/12m forward returns jointly via a small supervised model rather than picking one horizon.
- **Analog-based scenario generation.** The strategy naturally produces a set of historical scenarios; use them directly for stress testing and position sizing rather than just mean forecasting.
- **Country-specific analog weighting.** Some countries (Turkey, Argentina) may have more idiosyncratic dynamics where global analogs are less informative. Learn per-country analog weights.
- **Mythos-class extensions.** Once you have access, the obvious moves are: autonomous Phase 2 grid search, multi-agent debate on analog validity (a "skeptic" agent that argues why each proposed analog is wrong), and local-language central bank document embedding to enrich `worldstate_t`.

---

## 6. Risks and open research questions

The strategy is conceptually clean but there are specific ways it can fail that you should be watching for from day one.

**Sample size of analog library.** You have ~312 monthly observations since 2000. Top-10 analogs out of 312 is a non-trivial fraction of the history — the tails of "analog" get thin fast. Consider weekly observation frequency (~1,300 obs) if monthly proves too sparse.

**Graph time-indexing.** Bilateral trade and banking edges are reported with significant lag and are often restated. The graph at *t* as currently stored in Neo4j is the *most recent* snapshot, not a point-in-time snapshot. Phase 4's walk-forward requires rebuilding graph state at each historical *t* from the raw panels. Budget a full day for this.

**Factor-set drift.** Several Program 2/5 sources (Bloomberg, ND-GAIN, UNDP) either start late or have sparse early coverage. Your world-state vector for 2003 has materially fewer non-null features than the one for 2024. Either impute (with care), restrict `worldstate_t` to the common denominator of features (conservative), or weight analog similarity by how comparable the feature sets are.

**Regime breaks the model cannot see.** The world of 2000-2007 and the post-QE world are structurally different in ways no factor panel fully captures (zero rates, algorithmic trading, passive ETF flows). Phase 3 mitigates but doesn't solve this.

**Correlated signal decay.** If the strategy discovers that EM-crisis analogs predict EM underperformance, it is rediscovering momentum under a different name. Check orthogonality to trailing momentum and carry early — if the analog alpha dies once you residualize against momentum, you have not added anything.

**Survivor and definition bias.** The 34-country universe today is not the 34-country universe of 2003 (Russia's investability, Turkey's liquidity, UK in/out of EU). Document the universe definition carefully and stress-test by dropping countries individually from the backtest.

---

## 7. Success criteria

The strategy graduates from research to live evaluation only if it clears all four of these at the end of Phase 4:

1. **Deflated Sharpe ratio > 0 with t-stat > 2.0** after accounting for the Phase 2 grid size.
2. **Positive in at least 3 of the 5 subperiods** (pre-GFC / GFC / post-GFC / COVID / recent), none a severe loss.
3. **Information ratio of at least 0.3** above the better of equal-weight and 60-month factor momentum benchmarks, net of Almgren-Chriss costs.
4. **Face-valid top analogs** — when you inspect the analog set for a dozen hand-picked dates, at least 80% of the top-3 matches are economically defensible.

"Graduates" does not mean go-live. It means the signal earns a seat next to your existing factor-momentum model in a combined portfolio, with the final go-live decision gated on a separate 6-month paper trade.

---

## 8. First concrete week

The fastest path to a go/no-go read is a tight Phase 0 + Phase 1 MVP in the first week.

**Day 1-2.** Phase 0: baseline returns, PIT audit. One script, one CSV, one memo.

**Day 3-4.** Phase 1 Step 1-3: pull `feature_panel`, build the flat world-state vectors, fit point-in-time PCA, dump `worldstate_t` for every month 2000-01 through present to a Parquet file. Confirm shape, confirm non-leakage.

**Day 5-6.** Phase 1 Step 4-7: analog search, forward-return aggregation, cross-sectional portfolio, full walk-forward from 2005-01. One cumulative-return chart and one IR table is the deliverable.

**Day 7.** Read the chart. If the slope is remotely positive without any of the Phase 2-5 improvements, this is a live research program and Phase 2 starts Monday. If it is flat or negative, read the diagnostics, check for implementation bugs (most likely culprit), and either fix or write a short post-mortem on why the naïve version failed so the Phase 5 graph-aware version knows what problem it has to solve.

---

## 9. What Mythos changes (if and when you have access)

The design above assumes you are running this on Opus 4.6 or a similar tool-using model. If Mythos becomes available, the specific places in this roadmap where it shifts the cost-benefit math are:

- **Phase 2 grid search** becomes an autonomous multi-day campaign rather than a week of your time.
- **Phase 5b (GNN embedding)** becomes tractable as a multi-week autoresearch campaign in the spirit of Idea #2 from your Mythos notes.
- **Phase 6 diagnostics** — the "write one sentence on whether each analog match is economically plausible" task — is exactly the workload Mythos's multimodal + long-context capabilities are built for.
- **Phase 7 ensemble** with local-language central bank sentiment (Idea #4 from the Mythos notes) adds a feature dimension to `worldstate_t` that is invisible to any US/English-news-based analog library.

None of this is required for the MVP. Everything from Phase 0 through Phase 4 runs on current infrastructure.

---

*Next step: confirm this shape matches what you had in mind and I'll scaffold the Phase 0 baselines script against `AsadoDB` — or, if you want to re-scope first, we can adjust (different representation, different horizon, different universe).*
