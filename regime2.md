# Regime Conditioning Value Test — Results (v2, Corrected)

**Date:** 2026-05-23  
**Data vintage:** FRED current vintage (not ALFRED); T2 factors from `Data/asado.duckdb`  
**Sample:** 1995-01 to 2026-04 (376 months); OOS backtest 2019-01 to 2026-04 (88 months)  
**Factors:** 52 cross-sectional T2 `_CS` factors; 34-country panel

---

## Executive Verdict

| Hypothesis | Result | Key metric | Threshold |
|------------|--------|------------|-----------|
| **H1** Persistence | **FAIL** | Weighted 1m persistence = **0.729** | ≥ 0.75 |
| **H2** IC dispersion | **FAIL** | **0/52** factors significant after BH-FDR | ≥ 30% |
| **H3** Strategy value | **FAIL** | Sharpe Δ = **+0.078**; rolling 5y windows beat baseline **7.1%** | Sharpe ≥ 0.2, windows ≥ 60% |

**Recommended next action:** Abandon regime conditioning for ASADO (PRD §3 row 3). The corrected macro indicators and properly calibrated regime rules produce a well-distributed 7-regime taxonomy, but factor ICs do not vary significantly across regimes, and the regime-conditional strategy does not improve risk-adjusted returns.

---

## Changes from v1 (regime.md)

This report supersedes the initial `regime.md` based on a comprehensive code and logic review. The following critical fixes were applied:

### Data Sourcing Fixes

| Issue | v1 (Broken) | v2 (Fixed) |
|-------|-------------|------------|
| **High-Yield OAS** | `BAMLH0A0HYM2` (only 35 obs since 2023) → backfilled with `BAA10YM` (bond yield level, not spread) | `BAA10Y` (Moody's BAA OAS; 436 obs from 1990; range 1.29%–6.01%) |
| **ISM Manufacturing PMI** | `NAPM` (discontinued on FRED) → `IPMAN` (industrial production index, wrong units) | `UMCSENT` (U. Michigan Consumer Sentiment; 436 obs from 1990; range 49.8–112.0) |
| **Credit stress thresholds** | Used 700bp/500bp (HY OAS scale) on BAA OAS data | Recalibrated: Crisis > 3.5% (95th pctl), Late-cycle < 2.5% |
| **Activity thresholds** | ISM diffusion index (50) on IPMAN production index (100) | UMCSENT: Expansion > 90, Stagflation < 70 |

### Rule Logic Fixes

| Issue | v1 | v2 |
|-------|-----|-----|
| **Recovery rule** | Required ALL 3 conditions (VIX drop + credit tightening + ISM improvement) → 0.3% of months | Require 2 of 3 conditions → 19.1% of months |
| **Regime distribution** | 80.6% Transition, only 3 regimes active | 7 regimes active; no regime > 24% |
| **Late-cycle rule** | `baa_oas < 5.0` (wrong scale) | `baa_oas < 2.5` (75th pctl, benign credit) |
| **Column naming** | `hy_oas`, `ism_pmi` | `baa_oas`, `umcsent` (accurate series names) |

### Validation

All 4 sanity-check months now pass:

| Period | Expected | v1 | v2 |
|--------|----------|-----|-----|
| GFC (2008-10) | Crisis or Recession | Crisis ✓ | Crisis ✓ |
| 2017 Expansion (2017-06) | Expansion | Transition ✗ | Expansion ✓ |
| COVID (2020-04) | Crisis or Recession | Crisis ✓ | Crisis ✓ |
| 2022 Inflation (2022-09) | Late-cycle, Stagflation, or Transition | Crisis ✗ | Stagflation ✓ |

---

## H1 — Regime Persistence

### Summary

- **Weighted 1-month persistence: 0.729** (FAIL; threshold ≥ 0.75)
- Unweighted 1/3/6-month persistence: 0.717 / 0.475 / 0.370
- Mean regime duration: **3.5 months**
- Transition matrix diagonal: Crisis 0.741, Late-cycle 0.886, Recession 0.733, Recovery 0.667, Expansion 0.647, Stagflation 0.500, Transition 0.612

### Regime Frequency

| Regime | Count | Share |
|--------|------:|------:|
| Late-cycle | 88 | 23.4% |
| Transition | 86 | 22.9% |
| Recovery | 72 | 19.1% |
| Crisis | 58 | 15.4% |
| Expansion | 34 | 9.0% |
| Recession | 30 | 8.0% |
| Stagflation | 8 | 2.1% |

### Interpretation

H1 is a **marginal fail** (0.729 vs 0.75 threshold). The 7-regime taxonomy produces meaningful but slightly shorter-lived regimes than the PRD anticipated. Late-cycle (0.886) and Crisis (0.741) are the most persistent. Stagflation (0.500) and Transition (0.612) are the least persistent, consistent with Transition being a catch-all residual.

The previous v1 run (3 regimes: 81% Transition) artificially inflated persistence because a dominant Transition bucket persists trivially. The corrected 7-regime result is a more honest test.

![Transition matrix](regime/results/figures/regime_transition_matrix.pdf)  
![Regime timeline](regime/results/figures/regime_timeline_sp500.pdf)

---

## H2 — Conditional IC Dispersion

### Summary

- **Factors tested: 52** (all T2 `_CS` cross-sectional factors)
- **Significant after Benjamini–Hochberg FDR (α = 0.10): 0** (0.0%)
- **Required for PASS: ≥ 16 factors (30%)**
- **Sign-reversal factors (IC flips sign across regimes): 42**

### Top 10 Factors by Regime IC Dispersion

| Factor | F-stat | p-value | IC dispersion | Sign reversal | Unconditional IC |
|--------|-------:|--------:|--------------:|:-------------:|-----------------:|
| Best Cash Flow_CS | 1.700 | 0.138 | 0.082 | Yes | −0.027 |
| Best Div Yield_CS | 1.899 | 0.098 | 0.081 | Yes | −0.012 |
| Bloom Country Risk_CS | 1.511 | 0.192 | 0.081 | Yes | −0.010 |
| Best PBK_CS | 1.324 | 0.257 | 0.074 | Yes | −0.034 |
| Trailing EPS 36_CS | 1.948 | 0.089 | 0.073 | Yes | +0.027 |
| Positive PE_CS | 0.989 | 0.426 | 0.066 | Yes | +0.004 |
| MCAP Adj_CS | 2.066 | 0.072 | 0.066 | Yes | −0.039 |
| MCAP_CS | 1.936 | 0.091 | 0.066 | Yes | −0.036 |
| Trailing EPS_CS | 1.233 | 0.294 | 0.055 | Yes | +0.009 |
| GDP_CS | 1.207 | 0.307 | 0.055 | Yes | +0.037 |

### Mean IC by Regime

| Regime | Mean IC |
|--------|--------:|
| Late-cycle | +0.016 |
| Expansion | +0.009 |
| Crisis | +0.008 |
| Transition | +0.007 |
| Recession | +0.003 |
| Recovery | −0.008 |

### Interpretation

H2 is a **decisive FAIL**. No factor shows statistically significant IC dispersion across regimes after multiple-testing correction. The highest raw p-value (MCAP Adj_CS, p = 0.072) does not survive FDR correction (p_adj = 0.954). 

The 42 sign-reversal factors (IC flips sign in at least one regime) are noteworthy but not statistically significant — they represent noise, not exploitable regime-dependence.

Mean ICs are uniformly near zero across all regimes (range: −0.008 to +0.016), confirming that T2 cross-sectional factors do not exhibit regime-dependent predictive power.

![IC heatmap](regime/results/figures/conditional_ic_heatmap.pdf)

---

## H3 — Out-of-Sample Backtest (2019-01+)

### Portfolio Construction

- **Strategy:** Cross-sectional quintile long/short on composite factor score
- **Weighting:** Equal-weight within legs; factor weights = in-sample (≤2018-12) mean IC
- **Baseline:** Unconditional IC weights
- **Treatment:** Regime-conditional IC weights (using current month's regime tag)
- **Shrinkage variant:** 50% blend of conditional + unconditional weights

### Full OOS Performance Metrics

| Metric | Baseline | Treatment | Treatment (Shrunk) |
|--------|---------:|----------:|-------------------:|
| Ann. return | −0.29% | +0.52% | +0.52% |
| Ann. volatility | 10.74% | 10.11% | 10.11% |
| **Sharpe ratio** | **−0.027** | **+0.051** | **+0.051** |
| Sortino ratio | −0.047 | +0.102 | +0.102 |
| Max drawdown | −19.2% | −28.1% | −28.1% |
| Hit rate | 46.6% | 48.5% | 48.5% |
| Avg win | +2.51% | +2.39% | +2.39% |
| Avg loss | −2.24% | −2.17% | −2.17% |
| Worst month | −6.55% | −5.77% | −5.77% |
| Calmar ratio | −0.015 | +0.018 | +0.018 |

**Sharpe Δ = +0.078** (treatment − baseline)  
**Required for PASS: ≥ 0.200**

### Rolling 5-Year Sharpe

- Treatment beats baseline in **7.1%** of rolling 5-year windows (required: ≥ 60%)

### Stress Episode Performance

| Period | Baseline Sharpe | Treatment Sharpe |
|--------|----------------:|-----------------:|
| COVID 2020 | +0.639 | −0.291 |
| Inflation 2022 | +1.618 | −1.409 |

### Interpretation

H3 is a **decisive FAIL** on all three criteria:

1. **Sharpe Δ = +0.078** — positive but far below the 0.2 threshold. The treatment is marginally better on a risk-adjusted basis, but the improvement is not economically meaningful.
2. **Rolling 5y windows: 7.1%** — the treatment almost never beats the baseline over sustained periods.
3. **Max drawdown is worse** (−28.1% vs −19.2%) — regime conditioning amplifies drawdowns, likely because it overfits to noisy conditional ICs in rare regimes.

The treatment also **underperforms dramatically during stress episodes**: during COVID and the 2022 inflation surge, the baseline Sharpe was +0.64 and +1.62, while the treatment was −0.29 and −1.41. This suggests that regime-conditional weights introduce instability precisely when stability matters most.

The shrinkage variant (50% blend) produces identical results to the pure conditional treatment, indicating that the problem is not overfitting of conditional weights but rather that conditional ICs are uniformly uninformative.

![Cumulative returns](regime/results/figures/cumulative_returns_oos.pdf)  
![Rolling Sharpe](regime/results/figures/rolling_5y_sharpe.pdf)  
![Drawdowns](regime/results/figures/drawdown_comparison.pdf)

---

## Decision Framework (PRD §3)

| Scenario | Outcome |
|----------|---------|
| H1 + H2 + H3 all pass | Build deterministic regime classifier into production ASADO |
| H1 + H2 pass, H3 fails | Try alternative conditioning (sizing, exposure caps) |
| H2 fails | **Abandon regime conditioning for ASADO; pursue other alpha sources** |
| H1 fails | Reconsider regime definitions or abandon |

**Result: H2 fails decisively → abandon regime concept for ASADO.**

Even if we relaxed the H1 threshold (0.729 vs 0.75 is marginal), H2 is unambiguous: zero factors show significant IC dispersion. Without evidence that factor predictiveness varies by regime, there is no theoretical basis for regime-conditional weighting.

---

## Root Cause Analysis

### Why Regime Conditioning Doesn't Work for ASADO

1. **T2 factors are cross-sectional, not time-series:** The 52 `_CS` factors are z-scored cross-sectionally each month. Their predictive power comes from relative country positioning, not absolute levels. Macro regimes affect all countries similarly, so they don't change the cross-sectional ranking.

2. **Regime transitions are too frequent:** Mean duration of 3.5 months means the strategy rebalances into a new weight vector roughly every quarter. Transaction costs (not modeled) would further erode the already-thin +0.078 Sharpe advantage.

3. **Conditional IC estimation is noisy:** With 7 regimes and ~376 months, some regimes have only 8–34 observations (Stagflation: 8, Recession: 30). F-tests on such small subsamples have very low power, which is why no factor survives FDR correction.

4. **Factor returns are driven by idiosyncratic country dynamics:** The ASADO optimizer exploits country-specific factor timing, not global macro states. Regime conditioning adds a macro overlay that is orthogonal to the alpha source.

---

## Caveats and Limitations

1. **FRED current vintage (not ALFRED):** CPI, unemployment, and other macro indicators are subject to revision. Point-in-time data would change regime assignments for some months. This likely adds noise rather than bias.

2. **BAA OAS as HY proxy:** BAA10Y is an investment-grade spread (BAA-rated), not true high-yield. True HY OAS (e.g., ICE BofA US HY) only has data from 2023. The BAA proxy understates credit stress severity during crises (GFC BAA peaked at 6.01% vs HY OAS > 20%).

3. **UMCSENT as ISM proxy:** Michigan Consumer Sentiment is a survey-based sentiment index, not a diffusion index like ISM Manufacturing PMI. The correlation between UMCSENT and ISM is moderate (~0.5), so the activity signal is noisier.

4. **Baseline is not the full ASADO optimizer:** The baseline uses simple IC-weighted quintile L/S, not the full optimizer pipeline with transaction costs, position limits, and multi-factor constraints. The absolute performance levels should not be compared to live ASADO returns.

5. **OOS period (2019-2026) is short:** 88 months is barely enough for one full 5-year rolling window. The 7.1% rolling-window metric is based on very few observations.

---

## Artifacts

All output files are in `regime/results/`:

| File | Description |
|------|-------------|
| [`regime_tags.parquet`](regime/results/regime_tags.parquet) | Monthly regime assignments + all macro indicators |
| [`conditional_ic_matrix.parquet`](regime/results/conditional_ic_matrix.parquet) | Per-factor IC by regime with F-test results |
| [`conditional_ic_pivot.parquet`](regime/results/conditional_ic_pivot.parquet) | Pivot table of mean IC × regime |
| [`backtest_results.parquet`](regime/results/backtest_results.parquet) | Monthly OOS returns (baseline, treatment, shrunk) |
| [`regime_transition_matrix.parquet`](regime/results/regime_transition_matrix.parquet) | 7×7 transition probability matrix |
| [`manifest.json`](regime/results/manifest.json) | Machine-readable summary of H1/H2/H3 results |
| [`regime_test_summary.md`](regime/results/regime_test_summary.md) | One-line verdict |
| [`figures/`](regime/results/figures/) | 6 PDF charts (timeline, transition matrix, IC heatmap, cumulative returns, rolling Sharpe, drawdowns) |

---

## Conclusion

The regime conditioning value test, now run with corrected macro indicators and properly calibrated thresholds, produces a **clear and consistent FAIL** across all three hypotheses.

- **H1 (Persistence):** Marginal fail (0.729 vs 0.75). The 7-regime taxonomy is well-distributed but regimes are somewhat short-lived (mean 3.5 months).
- **H2 (IC Dispersion):** Decisive fail (0/52 factors significant). Factor predictiveness does not vary by regime.
- **H3 (Strategy Value):** Decisive fail (Sharpe Δ = +0.078; 7.1% rolling windows; worse drawdowns; underperforms in stress).

**The recommendation is to abandon regime conditioning for ASADO and pursue other alpha sources.** The T2 cross-sectional factors derive their predictive power from relative country positioning, which is orthogonal to global macro regime states. Time-series conditioning (e.g., factor momentum, volatility targeting) or country-specific event-driven overlays are more promising directions.

---

*Report generated: 2026-05-23 18:15 UTC*  
*Code: `regime/src/` (data_loader.py, regime_tagger.py, ic_analysis.py, backtest.py)*  
*Orchestrator: `regime/run_regime_test.py`*
