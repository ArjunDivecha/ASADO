# Regime Conditioning Value Test — Results

## Executive verdict

| Hypothesis | Result | Key metric |
|------------|--------|------------|
| **H1** Persistence | **PASS** | Weighted 1m persistence = 0.793 (threshold ≥ 0.75) |
| **H2** IC dispersion | **PASS** | 21/52 factors significant after BH-FDR (40.4%, need ≥30%) |
| **H3** Strategy value | **FAIL** | Sharpe Δ = 0.451 (need ≥0.2); rolling windows beat baseline 47.2% (need ≥60%) |

**Recommended next action:** Try alternative conditioning schemes before ML/CNN work (PRD §3 row 2).

## Decision framework (PRD §3)

H1+H2 hold, H3 fails → **try alternative conditioning** (sizing, exposure caps) before abandoning regimes.

## H1 — Regime persistence

- Weighted average 1-month persistence: **0.793**
- Unweighted 1/3/6-month persistence: 0.787 / 0.609 / 0.530
- Mean regime duration: **4.6** months

![Transition matrix](results/figures/regime_transition_matrix.pdf)

### Regime frequency

| regime     |   count |
|:-----------|--------:|
| Expansion  |     106 |
| Late-cycle |      96 |
| Crisis     |      88 |
| Transition |      86 |

## H2 — Conditional IC

- Factors tested: **52** (T2 `_CS` cross-sectional factors; PRD cites 53, warehouse has 52)
- Significant after Benjamini–Hochberg FDR (α=0.10): **21** (40.4%)

![IC heatmap](results/figures/conditional_ic_heatmap.pdf)

### Top 10 factors by regime IC dispersion

| factor                |   f_stat |     p_value |   ic_dispersion | sign_reversal   |   p_adj_fdr | significant_fdr   |   ic_unconditional |
|:----------------------|---------:|------------:|----------------:|:----------------|------------:|:------------------|-------------------:|
| MCAP Adj_CS           |  6.77901 | 0.000235843 |       0.118265  | True            |   0.0102722 | True              |        -0.0710072  |
| MCAP_CS               |  5.92752 | 0.00070792  |       0.11473   | True            |   0.0103828 | True              |        -0.0657817  |
| Bloom Country Risk_CS |  4.13432 | 0.00804489  |       0.0981943 | True            |   0.0442469 | True              |        -0.0232301  |
| Mcap Weights_CS       |  3.97947 | 0.0093871   |       0.088302  | True            |   0.0458925 | True              |        -0.00741333 |
| Best Cash Flow_CS     |  6.308   | 0.000466917 |       0.085635  | True            |   0.0102722 | True              |        -0.0326124  |
| Operating Margin_CS   |  4.59883 | 0.00382044  |       0.0832281 | True            |   0.0298665 | True              |         0.0595738  |
| Shiller PE_CS         |  3.44585 | 0.0175191   |       0.0776445 | True            |   0.0700763 | True              |         0.0821066  |
| Best Price Sales_CS   |  3.5906  | 0.0150952   |       0.0765209 | True            |   0.0664188 | True              |        -0.0548231  |
| Trailing EPS 36_CS    |  4.41137 | 0.00504576  |       0.0729882 | True            |   0.0317162 | True              |         0.0267206  |
| Best ROE_CS           |  3.12139 | 0.0278392   |       0.0720144 | True            |   0.0942249 | True              |         0.0341619  |

### Sign-reversal factors (conditional IC flips sign)

Count: **35** — highest-value candidates for regime weighting.

## H3 — Out-of-sample backtest (2019-01+)

Portfolio: cross-sectional **quintile long/short** on composite factor score, equal-weight within legs. Baseline uses in-sample (≤2018-12) unconditional mean IC weights; treatment uses regime-conditional IC weights.

### Full OOS metrics

|                  |   ann_return |   ann_vol |   sharpe |   sortino |   max_dd |   hit_rate |   avg_win |   avg_loss |   worst_month |   calmar |
|:-----------------|-------------:|----------:|---------:|----------:|---------:|-----------:|----------:|-----------:|--------------:|---------:|
| baseline         |      -0.0302 |    0.2047 |  -0.1476 |   -0.3248 |  -0.6155 |     0.3837 |    0.0551 |    -0.0384 |       -0.0988 |  -0.0491 |
| treatment        |       0.06   |    0.1979 |   0.3034 |    0.4945 |  -0.3703 |     0.5231 |    0.0475 |    -0.0416 |       -0.1144 |   0.1621 |
| treatment_shrunk |       0.06   |    0.1979 |   0.3034 |    0.4945 |  -0.3703 |     0.5231 |    0.0475 |    -0.0416 |       -0.1144 |   0.1621 |

- Treatment also tested with **50% shrinkage** toward unconditional weights: Sharpe Δ = 0.451

![Cumulative returns](results/figures/cumulative_returns_oos.pdf)
![Rolling Sharpe](results/figures/rolling_5y_sharpe.pdf)
![Drawdowns](results/figures/drawdown_comparison.pdf)

### Stress episodes

| period         |   baseline_sharpe |   treatment_sharpe |
|:---------------|------------------:|-------------------:|
| COVID 2020     |            -1.223 |             -2.284 |
| Inflation 2022 |             2.332 |             -1.45  |

## Sanity checks (PRD §5.6, §8)

- ✓ GFC: Crisis
- ✓ 2017 expansion: Expansion
- ✓ COVID: Crisis
- ✓ 2022 inflation: Late-cycle

## Top 3 surprising findings

1. Transition regime covers 22.9% of months — rules are strict.
2. Weighted persistence 0.79 vs unweighted 0.79.
3. Shrinkage variant Sharpe Δ = 0.451 vs pure conditional 0.451.

## Top 3 caveats

1. FRED current vintage — not point-in-time ALFRED; CPI/unemployment subject to revision.
2. HY OAS history may start later than 1995 — early sample uses available FRED fields only.
3. Baseline is IC-weighted quintile L/S, not full optimizer pipeline — compare magnitudes, not levels, to live ASADO.

## Data sources

- T2 factors & returns: `Data/asado.duckdb` → `t2_master`
- Macro indicators: **FRED API** (current vintage; not ALFRED — revision risk on CPI/unemployment)
- See `data/raw/fred_*.meta.json` per series

## Artifacts

- Tags: [`results/regime_tags.parquet`](results/regime_tags.parquet)
- IC matrix: [`results/conditional_ic_matrix.parquet`](results/conditional_ic_matrix.parquet)
- Backtest: [`results/backtest_results.parquet`](results/backtest_results.parquet)
- Summary: [`results/regime_test_summary.md`](results/regime_test_summary.md)