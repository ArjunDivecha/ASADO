# -PRD: Strategy #2 - Factor-Momentum Country Rotation
## Two-Week Research Sprint And Promotion Gate

| Field | Value |
|-------|-------|
| **Project** | ASADO country equity autoresearch |
| **Strategy name** | Factor-Momentum Country Rotation |
| **Short name** | `fmcr_v1` |
| **Version** | 1.0 |
| **Date** | 2026-05-23 |
| **Author** | Codex, from Arjun's product direction |
| **Status** | Draft for implementation |
| **Sprint length** | 10 business days |
| **Primary dependency** | `Data/asado.duckdb` return and factor-membership surfaces |
| **Primary output** | Walk-forward country scores, model portfolio, backtest, and go/no-go memo |

---

## 1. Purpose

Build a rigorous research implementation of factor-momentum country rotation.

At each monthly decision date, the strategy will estimate which ASADO factor portfolios have recently been getting paid, map those factor-payoff signals onto country exposures, rank the 34-country universe, and evaluate a disciplined long/short and long-only country rotation portfolio.

The sprint does **not** create a live trading system. It creates a reproducible evidence package that answers one question:

> Does factor payoff persistence inside ASADO translate into country allocation alpha after point-in-time controls, costs, turnover, and benchmark comparisons?

If the answer is no, the project keeps the primitives and stops. If the answer is yes, the next phase is paper trading, not live execution.

---

## 2. Product Thesis

ASADO's strongest current edge is not that it has many macro, news, commodity, graph, and prediction-market variables. The edge is that it has a returns-first spine:

1. Country returns.
2. Factor portfolio returns.
3. Country membership in factor portfolios.
4. Country-factor attribution.
5. Daily versions of country and factor returns.

The thesis is:

> Factor returns are smoother and more persistent than raw country returns. If the system can identify which factor portfolios are being rewarded, then country exposure to those rewarded factors should produce a better country-rotation signal than direct macro forecasting.

This deliberately follows the lesson from Strategy #1: do **not** predict country alpha from a large unsupervised world-state vector. Predict factor payoff first, then map factor payoff to country views.

---

## 3. Strategy #1 Lessons Applied

The PCA analog strategy failed the empirical gate. This PRD preserves the reusable parts and rejects the fragile parts.

Reusable:

- PIT discipline.
- Country-return cache patterns.
- Backtest artifact layout.
- Go/no-go memo habit.
- Equal-weight and country-momentum baselines.

Rejected:

- PCA over thousands of slow macro and signal features.
- Similarity matching as the primary alpha engine.
- Broad parameter sweeps before a fixed baseline is tested.
- Live-looking country lists as evidence of alpha.

New rule:

> `fmcr_v1` has one pre-registered primary model. Diagnostics can be reported, but only the primary model decides the go/no-go.

---

## 4. Current Repo State

Verified live from `Data/asado.duckdb` during PRD drafting:

| Surface | Current status | Use in `fmcr_v1` |
|---------|----------------|------------------|
| `factor_returns` | Present, 277,116 rows, 2000-02-01 to 2026-04-01 | Monthly factor payoff history |
| `factor_returns_daily` | Present, 1,293,492 rows, 2000-01-01 to 2026-05-07 | Freshness and daily payoff overlay |
| `factor_top20_membership` | Present, 2,104,980 rows, 2000-02-01 to 2026-05-01 | Country membership in rewarded factor buckets |
| `country_factor_attribution` | Present, 2,087,921 rows, 2000-02-01 to 2026-04-01 | Explanation and contribution audit |
| `t2_factors_daily` | Present, 32,340,392 rows, 2000-01-01 to 2026-05-07 | Daily country returns and T2 factor exposures |
| `unified_panel` | Present, 17,412,105 rows | Fallback explanatory panel |
| `country_returns_monthly` | Missing in current live DB | Must be rebuilt or derived in Stage 0 |
| `feature_panel` | Missing in current live DB | Must not be a hard dependency for v1 |
| `normalized_panel` | Missing in current live DB | Must not be a hard dependency for v1 |

Implementation implication:

`fmcr_v1` must run on the live return surfaces that exist now. If `feature_panel` or `normalized_panel` are restored later, the strategy may use them as higher-quality exposure sources, but the first sprint cannot require them.

---

## 5. Goals

### G1. Build A Fixed Factor-Momentum Signal

Compute point-in-time factor payoff momentum from monthly and daily optimizer factor returns.

### G2. Map Factor Payoffs To Country Scores

Translate factor payoff signals into country rankings using exposure and membership surfaces.

### G3. Run A Strict Walk-Forward Backtest

Evaluate the strategy from 2008 onward with no lookahead, realistic transaction-cost assumptions, benchmark comparisons, and subperiod diagnostics.

### G4. Produce A Go/No-Go Memo

Write a concise final memo that states whether the line of research deserves paper trading, needs revision, or should be stopped.

### G5. Create Reusable Strategy Primitives

Even if the strategy fails, keep the clean factor-momentum, exposure, scoring, and backtest artifacts for future research.

---

## 6. Non-Goals

- No live trading.
- No broker integration.
- No automatic order generation.
- No prediction-market, commodity, GDELT, Bloomberg, or graph alpha in the primary v1 model.
- No parameter mining across many windows, ranks, or portfolio sizes.
- No claim that current live top/bottom screens are validated recommendations.
- No dependency on missing `feature_panel` or `normalized_panel`.
- No unioning optimizer outputs into `feature_panel` or `unified_panel`.

---

## 7. Core Strategy

At each monthly rebalance date `t`:

1. Read factor portfolio returns available through `t`.
2. Compute a factor payoff momentum score for each `(source, factor)`.
3. Read country exposures or membership for each factor available through `t`.
4. Compute country score:

```text
country_score(c, t) =
    sum_over_factors(
        factor_payoff_score(f, t)
        * country_exposure(c, f, t)
        * source_weight(f)
        * confidence_weight(f, t)
    )
```

5. Rank countries by `country_score`.
6. Construct the primary research portfolio:
   - long top 7 countries,
   - short bottom 7 countries,
   - equal risk contribution within sides,
   - volatility target applied at portfolio level,
   - rebalance monthly.
7. Record a secondary long-only top-7 portfolio for users who cannot short.
8. Compare against pre-registered baselines.

The primary model is called:

```text
fmcr_v1_core_ls
```

Only `fmcr_v1_core_ls` decides the research go/no-go.

---

## 8. Input Data Contract

### 8.1 Country Universe

Use the canonical 34 ASADO countries from `config/country_mapping.json` and `country_reference`.

Do not silently drop countries. If a country is temporarily uninvestable or missing, write an explicit `investability_status` flag and keep it in diagnostics.

### 8.2 Country Returns

Primary dependent variable:

```text
country_returns_monthly(date, country, mtd_return_usd)
```

Current live DB does not contain this table. Stage 0 must either:

1. Rebuild it using the existing analog strategy return builder, or
2. Create a new builder that derives it from canonical T2 monthly returns.

The builder must emit:

- row count,
- date range,
- country count by date,
- unit convention,
- date-label semantics,
- duplicate country/sleeve notes.

### 8.3 Factor Payoff Returns

Monthly:

```text
factor_returns(date, factor, value, source)
```

Sources:

- `econ_optimizer`
- `t2_optimizer`
- `gdelt_optimizer`

Daily:

```text
factor_returns_daily(date, factor, value, source)
```

Sources:

- `t2_optimizer_daily`
- `gdelt_optimizer_daily`

The sprint must not assume whether `value` is stored as decimal return or percent return. Stage 0 must run a unit audit and write a conversion table:

```text
Data/strategy/factor_momentum_country_rotation/v1/factor_return_units.csv
```

Required columns:

| Column | Description |
|--------|-------------|
| `table_name` | `factor_returns` or `factor_returns_daily` |
| `source` | Optimizer source |
| `factor` | Factor name |
| `observations` | Non-null row count |
| `median_abs_value` | Unit diagnostic |
| `p99_abs_value` | Unit diagnostic |
| `unit_inferred` | `decimal`, `percent`, or `unknown` |
| `conversion_multiplier` | Applied multiplier to convert to decimal |
| `notes` | Caveats |

Any `unknown` unit blocks the backtest.

### 8.4 Country Exposure Matrix

Preferred exposure hierarchy:

1. **Restored normalized exposure panel**, if available:
   - `normalized_panel` with `_CS` or `_TS` variables.
2. **Live daily factor tables**, where factor names map cleanly:
   - `t2_factors_daily`
   - `gdelt_factors_daily`
3. **In-run z-scoring from `unified_panel`**, for monthly factor levels.
4. **Membership fallback**:
   - `factor_top20_membership`

The preferred exposure value is a winsorized cross-sectional z-score:

```text
country_exposure(c, f, t) = clamp(zscore(value(c, f, t)), -2.5, +2.5)
```

Membership fallback is allowed but marked lower confidence:

```text
country_exposure(c, f, t) = weight(c, f, t) if country in top bucket else 0
confidence_weight *= 0.50
```

Reason: top-20 membership can identify beneficiaries of winning factors, but it is weaker for short selection because it does not directly encode bottom exposure.

### 8.5 Explanatory Data Not In Core Model

The following can be joined into diagnostics and the final memo, but not into the primary v1 score:

- Prediction-market signals.
- World Bank commodities.
- Bloomberg CDS/WIRP/PMI/passive-flow variables.
- GDELT narrative variables, unless they enter through existing optimizer factor returns.
- Neo4j graph features.
- Event-log variables.

These are reserved for Phase 2 overlays after the factor-momentum core passes or fails cleanly.

---

## 9. Point-In-Time Rules

These rules are non-negotiable.

At decision date `t`:

1. Country forward return `r(t+1)` is not available to the model.
2. Factor returns used as inputs must have `date <= t`.
3. Country exposures used as inputs must have `date <= t`.
4. If a factor level is monthly and has uncertain release lag, use `date <= t - 1 month`.
5. If a factor level is annual, lag by 12 months unless a vintage source proves earlier availability.
6. Forecast variables are excluded from v1 unless there is a point-in-time vintage archive.
7. All normalization statistics are fit on data available at or before `t`.
8. All missingness decisions must be made using history available at or before `t`.
9. Daily returns near the current date must use latest non-null horizon logic, not the maximum table date blindly.
10. Date-label semantics must be documented before the first backtest run.

Any PIT violation is a hard failure, not a warning.

---

## 10. Factor Payoff Signal

### 10.1 Monthly Factor Momentum Features

For each `(source, factor)` and month `t`, compute:

| Feature | Definition |
|---------|------------|
| `ret_3m` | Sum or compounded return over prior 3 months, after unit conversion |
| `ret_6m` | Prior 6 months |
| `ret_12m` | Prior 12 months |
| `sharpe_12m` | Mean / volatility over prior 12 months |
| `hit_12m` | Share of positive months over prior 12 months |
| `drawdown_12m` | Worst peak-to-trough return over prior 12 months |
| `obs_12m` | Non-null observations in prior 12 months |
| `staleness_days` | Days since latest available observation |

Default monthly payoff score:

```text
monthly_factor_score =
    0.30 * z(ret_6m)
  + 0.25 * z(ret_12m)
  + 0.20 * z(sharpe_12m)
  + 0.15 * z(hit_12m)
  - 0.10 * z(abs(drawdown_12m))
```

All z-scores are cross-sectional within `(date, source)` after winsorization at the 2.5th and 97.5th percentiles.

Minimum coverage:

- At least 9 non-null monthly observations in the prior 12 months.
- At least 24 lifetime observations before a factor can enter the model.

### 10.2 Daily Payoff Overlay

Daily factor returns are a freshness overlay, not the primary signal.

For factors with a clean daily mapping:

| Feature | Definition |
|---------|------------|
| `daily_ret_20d` | Prior 20 trading-day return |
| `daily_ret_60d` | Prior 60 trading-day return |
| `daily_sharpe_60d` | Mean / volatility over prior 60 observations |
| `daily_hit_60d` | Share of positive days over prior 60 observations |

Daily overlay:

```text
daily_factor_score =
    0.35 * z(daily_ret_20d)
  + 0.35 * z(daily_ret_60d)
  + 0.20 * z(daily_sharpe_60d)
  + 0.10 * z(daily_hit_60d)
```

Combined factor score:

```text
factor_payoff_score =
    0.80 * monthly_factor_score
  + 0.20 * daily_factor_score
```

If no clean daily mapping exists:

```text
factor_payoff_score = monthly_factor_score
```

### 10.3 Source Weights

Default source weights:

| Source | Weight | Rationale |
|--------|-------:|-----------|
| `t2_optimizer` | 1.00 | Core T2 style factors |
| `t2_optimizer_daily` | 1.00 | Core daily style factors |
| `gdelt_optimizer` | 0.75 | Useful but noisier narrative signal |
| `gdelt_optimizer_daily` | 0.75 | Useful but noisier narrative signal |
| `econ_optimizer` | 0.75 | Monthly macro/econ source, no daily overlay |

These weights are fixed in v1 and not tuned.

---

## 11. Country Scoring

### 11.1 Primary Score

For each country `c` and decision date `t`:

```text
raw_country_score(c, t) =
    sum_f [
        factor_payoff_score(f, t)
        * exposure(c, f, t)
        * source_weight(f)
        * confidence_weight(f, t)
    ]
```

Normalize within each date:

```text
country_score(c, t) = zscore_cross_section(raw_country_score(c, t))
```

Winsorize final `country_score` to `[-3, +3]`.

### 11.2 Confidence Penalties

Apply multiplicative penalties:

| Condition | Penalty |
|-----------|--------:|
| Exposure source is membership fallback only | `0.50` |
| Factor return unit inferred from extreme heuristic, not explicit metadata | `0.75` |
| Factor has fewer than 36 lifetime observations | `0.50` |
| Latest factor return is stale by more than 45 calendar days | `0.75` |
| Factor has prior-12m volatility below floor | `0.50` |
| Country exposure missing and filled neutral | `0.00` for that factor-country cell |

### 11.3 Explanation Output

Every country score must be explainable by top contributors:

```text
Data/strategy/factor_momentum_country_rotation/v1/country_score_components.parquet
```

Schema:

| Column | Type | Description |
|--------|------|-------------|
| `date` | DATE | Decision date |
| `country` | VARCHAR | ASADO country |
| `source` | VARCHAR | Factor return source |
| `factor` | VARCHAR | Factor name |
| `factor_payoff_score` | DOUBLE | Standardized factor score |
| `exposure` | DOUBLE | Country exposure to factor |
| `source_weight` | DOUBLE | Fixed source weight |
| `confidence_weight` | DOUBLE | PIT confidence weight |
| `score_contribution` | DOUBLE | Contribution to raw country score |
| `exposure_source` | VARCHAR | `normalized_panel`, `daily_table`, `unified_panel_zscore`, or `membership_fallback` |

---

## 12. Portfolio Construction

### 12.1 Primary Research Portfolio

Name:

```text
fmcr_v1_core_ls
```

Rules:

- Rebalance monthly.
- Long top 7 countries by `country_score`.
- Short bottom 7 countries by `country_score`.
- Equal risk contribution within each side using trailing 12-month country return volatility.
- Gross exposure target: 150%.
- Net exposure target: 0%.
- Ex ante annualized volatility target: 10%.
- Maximum single-country absolute weight: 12%.
- Maximum region absolute exposure: 35%.
- Maximum sleeve cluster absolute exposure:
  - U.S. cluster (`U.S.`, `NASDAQ`, `US SmallCap`): 25%.
  - China cluster (`ChinaA`, `ChinaH`, Hong Kong if applicable): 25%.
- No trade if fewer than 28 countries have valid scores.

### 12.2 Secondary Diagnostic Portfolio

Name:

```text
fmcr_v1_top7_long_only
```

Rules:

- Long top 7 countries.
- Equal risk contribution.
- Fully invested.
- No short book.

This portfolio is reported for practicality but does not decide the go/no-go.

### 12.3 Instrument Mapping

Create:

```text
config/strategy_country_instruments.yaml
```

Required fields:

| Field | Description |
|-------|-------------|
| `country` | ASADO country name |
| `primary_etf` | Default ETF proxy if available |
| `index_future` | Default futures proxy if available |
| `currency_future` | Optional currency hedge or expression |
| `liquidity_tier` | `high`, `medium`, `low`, `unmapped` |
| `shortable_default` | Whether shorting is normally plausible |
| `notes` | Instrument caveats |

For v1 backtests, instrument mapping is used for cost/liquidity diagnostics only. Historical returns remain ASADO country returns.

---

## 13. Transaction Costs And Slippage

Report three cost cases:

| Case | One-way cost assumption |
|------|-------------------------|
| Low | 10 bps |
| Base | 25 bps |
| High | 50 bps |

Additional assumptions:

- Short borrow cost: 150 bps annualized for short side unless country is flagged `hard_to_borrow`.
- FX hedge cost: ignored in primary v1, reported as a missing-risk caveat.
- ETF tracking error: reported qualitatively in instrument diagnostics.

Turnover formula:

```text
turnover(t) = 0.5 * sum_c(abs(weight(c, t) - weight(c, t-1)))
```

Net return:

```text
net_return = gross_return - turnover * one_way_cost - borrow_cost
```

---

## 14. Backtest Protocol

### 14.1 Timeline

Backtest start:

```text
2008-01-01
```

Backtest end:

```text
latest month with complete country forward returns
```

At each decision month `t`:

1. Build factor payoff scores using data available through `t`.
2. Build country exposures using data available through `t`.
3. Score and rank countries.
4. Commit portfolio weights for `t+1`.
5. Observe country returns in `t+1`.
6. Log realized gross and net returns.

### 14.2 Baselines

Pre-registered baselines:

| Baseline | Description |
|----------|-------------|
| `equal_weight_34` | Equal-weight all 34 countries |
| `country_momentum_12_1_top7` | Long top 7 by trailing 12-1 month country return |
| `country_momentum_6_1_top7` | Long top 7 by trailing 6-1 month country return |
| `country_reversal_1m_top7` | Long worst prior month countries |
| `factor_membership_naive` | Long countries with most memberships in recently positive factor buckets |

The go/no-go comparison is against:

```text
max(equal_weight_34, country_momentum_12_1_top7)
```

### 14.3 Metrics

Report:

- Annualized return.
- Annualized volatility.
- Sharpe.
- Sortino.
- Max drawdown.
- Calmar.
- Hit rate.
- Monthly skew.
- Monthly kurtosis.
- Worst 1-month return.
- Turnover.
- Cost drag.
- Net exposure.
- Gross exposure.
- Correlation to equal-weight.
- Correlation to MSCI EM proxy if available.
- Rank IC: `country_score(t)` vs `return(t+1)`.
- Long-short spread return.
- Subperiod results:
  - 2008-2012.
  - 2013-2017.
  - 2018-2022.
  - 2023-latest.
  - COVID crash and rebound window.
  - 2022 inflation/rates window.

### 14.4 Statistical Discipline

Use:

- Newey-West adjusted t-stat for monthly returns.
- Block bootstrap confidence intervals for annualized excess return.
- Deflated Sharpe ratio or equivalent multiple-testing adjustment.
- Year-by-year score IC table.

No parameter sweep can be used to select the primary model. Any sweep belongs in an appendix and is not part of the promotion decision.

---

## 15. Promotion Gates

### Gate 0: Data Gate

Required to start backtest:

- `country_returns_monthly` exists or is rebuilt.
- Date-label semantics documented.
- Factor return units resolved with no `unknown` rows.
- At least 24 months of factor history before a factor enters the model.
- No PIT audit failures.
- Missing `feature_panel` and `normalized_panel` handled explicitly.

Failure status:

```text
NO-GO: DATA
```

### Gate 1: Research Gate

Required for paper-trade promotion:

| Metric | Minimum |
|--------|---------|
| Net Sharpe, base cost | `>= 0.70` |
| Excess annualized return vs comparison baseline | `>= +3.00%` |
| Rank IC | Positive overall and positive in at least 60% of years |
| Max drawdown | No worse than 1.25x comparison baseline drawdown |
| Cost drag | Less than 40% of gross alpha |
| 2023-latest excess return | Non-negative |
| Correlation to equal-weight | `< 0.85` |

Failure status:

```text
NO-GO: ALPHA
```

### Gate 2: Robustness Gate

Required for paper-trade promotion:

- Positive net result in at least 3 of 4 subperiods.
- No single country contributes more than 25% of total gross P&L.
- No single factor contributes more than 25% of total gross P&L.
- Strategy still works when U.S. cluster and China cluster are capped.
- Strategy still works under high cost case directionally, even if not at full hurdle.

Failure status:

```text
NO-GO: ROBUSTNESS
```

### Gate 3: Paper-Trade Gate

If Gates 0-2 pass, create a paper-trade packet. Live capital still requires a later PRD.

Required paper-trade artifacts:

- Latest portfolio with weights.
- Country score components.
- Risk report.
- Liquidity/instrument map.
- Daily monitoring checklist.
- Stop conditions.

Promotion status:

```text
PAPER-TRADE CANDIDATE
```

---

## 16. Output Specification

All strategy artifacts live under:

```text
Data/strategy/factor_momentum_country_rotation/v1/
```

### 16.1 Required Files

| File | Purpose |
|------|---------|
| `country_returns_monthly.parquet` | Rebuilt country return cache |
| `factor_return_units.csv` | Unit audit and conversion table |
| `factor_payoff_scores.parquet` | Monthly factor momentum scores |
| `country_exposures.parquet` | Country-factor exposure matrix |
| `country_score_components.parquet` | Decomposed country score |
| `country_scores.parquet` | Final country scores and ranks |
| `portfolio_weights.parquet` | Primary and diagnostic portfolio weights |
| `backtest_monthly.parquet` | Monthly realized returns and exposures |
| `baselines.parquet` | Benchmark returns |
| `diagnostics.json` | Metric summary |
| `run_manifest.json` | Reproducibility manifest |
| `plots.pdf` | Cumulative returns, drawdowns, IC, turnover, exposures |

### 16.2 Required Memo

```text
docs/strategy/factor_momentum_country_rotation/v1/go_no_go.md
```

The memo must include:

- Final verdict.
- Data gate result.
- Backtest headline table.
- Baseline comparison.
- Cost sensitivity.
- Subperiod table.
- Rank IC diagnostics.
- Factor and country contribution concentration.
- Current latest diagnostic portfolio clearly labeled as **unvalidated diagnostic output** unless paper-trade gates pass.
- Recommendation for stop, revise, or paper-trade.

---

## 17. Implementation Layout

```text
ASADO/
|-- config/
|   `-- strategy_country_instruments.yaml
|-- scripts/
|   `-- strategy/
|       `-- factor_momentum_country_rotation/
|           |-- __init__.py
|           |-- config.py
|           |-- audit_data.py
|           |-- build_country_returns.py
|           |-- build_factor_payoff.py
|           |-- build_country_exposures.py
|           |-- score_countries.py
|           |-- construct_portfolio.py
|           |-- backtest.py
|           |-- diagnostics.py
|           |-- report.py
|           |-- run_v1.py
|           `-- tests/
|               |-- test_pit.py
|               |-- test_units.py
|               |-- test_scores.py
|               `-- test_backtest.py
|-- Data/
|   `-- strategy/
|       `-- factor_momentum_country_rotation/
|           `-- v1/
`-- docs/
    `-- strategy/
        `-- factor_momentum_country_rotation/
            `-- v1/
                `-- go_no_go.md
```

### 17.1 CLI

```bash
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
./venv/bin/python scripts/strategy/factor_momentum_country_rotation/run_v1.py --stage audit
./venv/bin/python scripts/strategy/factor_momentum_country_rotation/run_v1.py --stage signals
./venv/bin/python scripts/strategy/factor_momentum_country_rotation/run_v1.py --stage backtest
./venv/bin/python scripts/strategy/factor_momentum_country_rotation/run_v1.py --stage report
./venv/bin/python scripts/strategy/factor_momentum_country_rotation/run_v1.py --all
```

### 17.2 Fixed v1 Config

```python
BACKTEST_START = "2008-01-01"
LONG_COUNT = 7
SHORT_COUNT = 7
TARGET_VOL_ANNUAL = 0.10
GROSS_EXPOSURE_TARGET = 1.50
NET_EXPOSURE_TARGET = 0.00
MAX_COUNTRY_ABS_WEIGHT = 0.12
MAX_REGION_ABS_WEIGHT = 0.35
MAX_CLUSTER_ABS_WEIGHT = 0.25
MONTHLY_WINDOWS = (3, 6, 12)
DAILY_WINDOWS = (20, 60)
SOURCE_WEIGHTS = {
    "t2_optimizer": 1.00,
    "t2_optimizer_daily": 1.00,
    "gdelt_optimizer": 0.75,
    "gdelt_optimizer_daily": 0.75,
    "econ_optimizer": 0.75,
}
ONE_WAY_COST_BPS = {
    "low": 10,
    "base": 25,
    "high": 50,
}
```

No config sweeps in v1.

---

## 18. Two-Week Sprint Plan

### Day 1: Repo And Data Preflight

- Confirm dirty worktree and avoid unrelated files.
- Verify live DuckDB surfaces.
- Rebuild or create `country_returns_monthly`.
- Write `date_semantics.md`.
- Run unit audit for factor returns.

Exit condition:

- Gate 0 blockers known.

### Day 2: PIT And Unit Tests

- Implement `audit_data.py`.
- Implement unit conversion and date alignment.
- Add tests for no future data, no unknown units, and complete country return coverage.

Exit condition:

- `test_pit.py` and `test_units.py` pass.

### Day 3: Factor Payoff Scores

- Implement monthly factor payoff.
- Implement daily overlay where mappings are clean.
- Write `factor_payoff_scores.parquet`.

Exit condition:

- Factor score coverage and staleness diagnostics pass.

### Day 4: Country Exposure Matrix

- Implement exposure hierarchy.
- Use normalized panel if restored, otherwise daily/unified z-scoring and membership fallback.
- Write `country_exposures.parquet`.

Exit condition:

- At least 28 countries have valid scores on at least 95% of decision dates.

### Day 5: Country Scoring And Explanation

- Implement country score aggregation.
- Write score components.
- Create latest diagnostic rankings with clear "not validated" label.

Exit condition:

- `country_scores.parquet` and `country_score_components.parquet` exist and pass structural tests.

### Day 6: Portfolio And Baselines

- Implement primary long/short portfolio.
- Implement secondary long-only portfolio.
- Implement pre-registered baselines.

Exit condition:

- Monthly weights sum correctly and respect risk caps.

### Day 7: Backtest

- Run full walk-forward backtest.
- Produce gross and net returns.
- Report cost sensitivity.

Exit condition:

- `backtest_monthly.parquet`, `baselines.parquet`, and `diagnostics.json` generated.

### Day 8: Robustness Diagnostics

- Subperiod analysis.
- Rank IC.
- Factor/country concentration.
- Correlation to equal-weight and country momentum.
- High-cost case.

Exit condition:

- Gate 1 and Gate 2 metrics available.

### Day 9: Report And Go/No-Go Draft

- Generate plots.
- Write draft `go_no_go.md`.
- Include current latest diagnostic portfolio only if labeled correctly.

Exit condition:

- Human-readable report complete.

### Day 10: Final Validation

- Re-run from clean artifacts.
- Run all tests.
- Confirm reproducibility manifest.
- Finalize go/no-go memo.

Exit condition:

- One of:
  - `NO-GO: DATA`
  - `NO-GO: ALPHA`
  - `NO-GO: ROBUSTNESS`
  - `PAPER-TRADE CANDIDATE`

---

## 19. Acceptance Tests

### 19.1 Data Tests

- `country_returns_monthly` has all 34 countries for >= 95% of months after 2000.
- No duplicate `(date, country)` rows.
- Factor return unit audit has no `unknown`.
- Factor return conversion is deterministic.
- Date semantics file exists.

### 19.2 PIT Tests

- No input row has `date > decision_date`.
- Monthly lag rules respected.
- Annual variables, if used, lagged by 12 months.
- Forward returns never appear in signal tables.
- Every backtest row records the exact input cutoff.

### 19.3 Scoring Tests

- Every decision date has rank 1 through N with no gaps for valid countries.
- Country scores are finite.
- Score components sum to raw country score within tolerance.
- Missing exposure fills are recorded.
- Membership fallback usage is reported.

### 19.4 Portfolio Tests

- Gross exposure within tolerance.
- Net exposure within tolerance.
- Country caps enforced.
- Region and cluster caps enforced.
- No trade generated when score coverage is below threshold.
- Turnover formula matches expected diff in weights.

### 19.5 Backtest Tests

- Realized returns use committed prior-month weights.
- Baselines share identical date windows.
- Cost cases are monotonic: high-cost return <= base-cost return <= low-cost return.
- Re-running the full pipeline produces identical metrics.

---

## 20. Reporting Template

The go/no-go memo must begin with:

```markdown
# Strategy #2 - Factor-Momentum Country Rotation
## v1 Go / No-Go Memo

**Decision:** ...
**Date:** ...
**Model:** `fmcr_v1_core_ls`
**Backtest window:** ...
**Primary comparison baseline:** ...
```

Headline table:

| Strategy | Ann return net | Ann vol | Sharpe | Max DD | Turnover | Excess vs baseline |
|----------|---------------:|--------:|-------:|-------:|---------:|-------------------:|
| `fmcr_v1_core_ls` | | | | | | |
| Comparison baseline | | | | | | |
| Equal-weight | | | | | | |
| Country momentum 12-1 | | | | | | |

Mandatory verdict language:

- If data gate fails: "Do not evaluate alpha. Data foundation failed."
- If alpha gate fails: "Do not paper trade. The signal does not clear the pre-registered hurdle."
- If robustness gate fails: "Do not paper trade. The signal may be a concentrated or regime-specific artifact."
- If gates pass: "Paper-trade candidate. Not approved for live trading."

---

## 21. Risk Register

| Risk | Severity | Mitigation |
|------|----------|------------|
| Date-label lookahead | High | Stage 0 date semantics audit blocks backtest |
| Return unit ambiguity | High | Unit audit blocks unknown units |
| Hidden global risk-on bet | High | Correlation, beta, region, and cluster diagnostics |
| Country ETF tracking error | Medium | Instrument map and liquidity tiers |
| Overfitting | High | One fixed model, no v1 sweeps |
| Membership fallback weak for shorts | Medium | Confidence penalty and fallback usage report |
| GDELT noise | Medium | Lower source weight and factor-level diagnostics |
| Turnover too high | High | Cost cases and turnover promotion gate |
| Single-country dependence | High | Contribution concentration gate |
| Single-factor dependence | High | Contribution concentration gate |
| Live DB/docs drift | Medium | Preflight verifies live tables before each run |

---

## 22. Future Extensions

Only after v1 has a clean verdict:

1. Regime-conditioned factor payoff.
2. Event-window risk overlays.
3. World Bank commodity transmission overlay.
4. Prediction-market risk throttle.
5. Bloomberg passive-flow distortion overlay.
6. Neo4j contagion and ownership hedge layer.
7. Longer-horizon 3-month and 6-month country rotation.
8. Currency-hedged and FX-expression variants.
9. Options overlays for short candidates where borrow/liquidity is poor.

These are explicitly outside v1.

---

## 23. Open Questions

1. Should U.S. sleeves (`U.S.`, `NASDAQ`, `US SmallCap`) be allowed to appear simultaneously in the long or short book, or should they be collapsed into one investable cluster before portfolio construction?
2. Should China A/H/Hong Kong be cluster-capped only, or mapped into one China complex for signal evaluation?
3. Should the primary research expression be country ETFs, index futures, or pure ASADO country return series?
4. What minimum paper-trade length should be required after a pass: 8 weeks, 12 weeks, or 6 months?
5. Should currency hedging be mandatory for developed markets and optional for EM, or omitted until Phase 2?

Default for v1:

- Keep all ASADO countries and sleeves in the signal universe.
- Apply cluster caps in portfolio construction.
- Use ASADO country returns for backtest truth.
- Use instrument mapping only for feasibility/cost diagnostics.
- Require a later paper-trading PRD before live use.
