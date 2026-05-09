# Strategy Lessons Learned

## Strategy #1: PCA-Stacked-Cross-Section Regime Analogs — Why It Failed

**Date:** 2026-05-08  
**Verdict:** NO-GO  
**Go/No-Go memo:** [`analogs/v1/go_no_go.md`](analogs/v1/go_no_go.md)

### Bottom line

The PCA-analog methodology has structural problems that the no-go memo
correctly identified empirically without naming the underlying causes. The
infrastructure (PIT discipline, country returns, baselines) is reusable; the
worldstate → analog → aggregate → backtest pipeline is not.

### Three concrete methodological problems

#### Problem 1: The PCA is fundamentally misspecified

The flat vector is roughly 2,900-dimensional (median 86 PIT-safe `_CS`
variables × 34 countries) and the PCA is fit on at most ~257 prior
observations. That's n_samples ≪ n_features by a factor of 11×.

In this regime, PCA is mathematically well-defined but the principal axes are
dominated by sample-specific variance — they capture the directions of largest
spread *in the specific 257 observations available*, not generalizable
structure. The 80% variance target gets hit at ~14 components, but those 14
components encode "what made these 257 dates differ from each other" rather
than "what regimes look like."

This isn't a hyperparameter issue. You can't fix it by changing PCA target
variance or component cap. The fundamental problem is that you're trying to
extract structure from data where you have ~12 features per observation in
feature-space — and the features are themselves noisy z-scores of slow-moving
macro variables. Modern shrinkage covariance estimators (Ledoit-Wolf, GLASSO)
would help marginally; they don't solve the underlying problem that there isn't
enough information in 257 cross-sections to reliably identify a 30-d regime
manifold.

#### Problem 2: The basis becomes "sticky" — almost every recent decision matches to 2007–2013

Of 211 decisions, **155 (73%) have their top-1 analog from 2007–2013**.
Decisions made in 2024–2026 still match to 2007–2013 dates. The mean top-1
cosine similarity climbs from 0.66 in 2009 to 0.85+ from 2020 onward.

That's the opposite of what you'd want. Rising similarity over time means the
model has lost discriminating power — once the PCA basis is dominated by
GFC-era variance (which is the largest in the available window), the projection
of every future worldstate onto that basis converges toward "this looks vaguely
like 2007–2013," and almost everything finds a high-cosine match.

This explains the subperiod pattern in the no-go memo precisely: 2008–2012
worked because matching GFC-shaped dates to GFC-forward-returns is what the
system actually does. Everywhere else, the analog set is essentially random
with respect to the actual current regime.

#### Problem 3: The information coefficient is zero

The empirical test of "does the score predict forward returns" is the IC:

- **Overall Pearson IC: −0.030**
- **Median yearly IC: −0.001**
- **9 of 19 years positive** — coin-flip
- **2008–2010**: IC of +0.27, +0.15, +0.12 (the GFC win)
- **2020**: IC of −0.37 (COVID was an unprecedented regime; the analog
  framework actively hurt)
- **Most other years**: in the −0.10 to +0.10 range, pure noise

For context, a working factor model in academic literature has IC of 0.03–0.07
with statistical significance. The PCA-analog signal has no edge except in
dates structurally similar to its training period. The 9.42% annualized return
is the long-only-holding-7-EM-heavy-baskets baseline plus the 2008–2012 alpha
wearing off over time — not predictive content.

### What was genuinely good

- **PIT discipline is excellent.** No lookahead, vintage_safe filter on
  forecast variables, 12-month minimum lag, 8 passing automated tests.
- **Code quality is high.** Headers, determinism (seed=42), idempotency,
  separation of concerns across stages.
- **Infrastructure is reusable.** `country_returns_monthly`, the PIT audit, the
  equal-weight baseline computation are useful primitives for any
  country-rotation research.
- **The negative result is informative.** "We tried PCA-stacked-cross-section
  analog matching; here's exactly how and why it failed" is genuinely valuable
  institutional knowledge.

### Structurally sounder approaches for future work

In order of recommended priority for a T2-style country rotation context:

1. **Hand-engineered regime descriptors** instead of PCA-of-everything. Define
   5–10 named regime axes: VIX regime, USD strength regime, oil regime, US–EM
   growth differential, yield curve shape, EM credit spread regime, China
   credit impulse, real-rates regime. Each axis is an interpretable scalar with
   clear semantics. Distance is L2 in this 5–10d space, no PCA pathology, and
   the analog matches are explainable. This is also what AQR / GMO /
   Bridgewater regime models actually use in practice.

2. **Predict regime-conditional factor returns, not country alpha.** Country
   monthly returns are 90%+ idiosyncratic noise. Factor returns are smoother
   and more analogous across regimes. Then map factor exposures ×
   regime-conditional factor returns → country views. That's how regime-aware
   factor models actually compose.

3. **Longer horizon (3-month or 6-month forward).** Idiosyncratic noise
   averages out. The same data with a 6-month horizon would have a much better
   shot — though the underlying PCA pathology would still be present.

4. **Predictive country embeddings learned from forward returns** (a supervised
   approach). Not PCA over features, but a small neural network or even ridge
   regression trained to map current state → forward return ranking. Lets the
   model learn what's predictive rather than what's variance-explanatory.
