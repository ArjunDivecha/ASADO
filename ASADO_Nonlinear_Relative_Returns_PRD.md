# ASADO: Nonlinear Relative Country Returns
## Product requirements document and coding-agent implementation contract

**Version:** 1.0  
**Prepared:** September 14, 2026  
**Owner:** Arjun Divecha  
**Implementation agent:** Luna, Extra High  
**Repository:** `ArjunDivecha/ASADO`  
**Status:** Specification only. The study has not been implemented or run as part of this document. Public repository source definitions were inspected; the owner's live databases were not queried.

---

## 0. Instructions to the implementation agent

Implement this study end to end inside the existing ASADO repository. Deliver working code, tests, configuration, an audited feature panel, reproducible walk-forward predictions, and a results report when the local source data permit it.

Start de novo from the databases. Do not read previous experiment results, research verdicts, learned signals, portfolios, or hypothesis ledgers to choose this study's variables, methods, or settings. Existing schema definitions, data collectors, ingestion code, instrument metadata, and date-semantics documentation may be inspected for engineering purposes. Follow repository instructions concerning security and coding conventions, without importing old research conclusions into this experiment.

**The dependent variable is continuous three-month RELATIVE return, not absolute return, a return decile, a probability, or a classification.** The features are country characteristics, not factor-portfolio returns.

Implement the fixed design below. Do not expand into a general research platform, search additional horizons, add factors, or keep tuning until the result becomes positive. A negative or inconclusive scientific result can be a completely successful implementation.

Resolve ordinary implementation details from the repository and its metadata. If a source is unavailable, preserve the design, finish the implementation and synthetic tests, and produce a precise blocked-data report. Never invent observations, silently substitute variables, or claim a real-data backtest was run when it was not.

Normative language: **MUST** means an acceptance requirement; **SHOULD** means the default unless a documented technical constraint prevents it. All numerical model and study settings below are proposed experimental choices, not previously established optimal values.

## 1. Research objective and hypothesis

### 1.1 Objective

Test whether a small number of nonlinear interactions between country characteristics improves out-of-sample country-equity rankings beyond the same characteristics used linearly or nonlinearly without interactions.

### 1.2 Hypothesis

Relative valuation, changing economic expectations, financial conditions, and the global environment may jointly contain predictive information even when their individual average effects are weak.

The principal comparison is:

`Model C: nonlinear additive + pairwise interactions`

versus:

`Model B: nonlinear additive, no interactions`.

Model A, regularized linear regression, provides context. C beating A alone is insufficient evidence that interactions add value: the improvement could come entirely from individual nonlinear feature effects.

### 1.3 Interpretation boundary

The experiment can establish evidence for this particular historical forecasting specification. It cannot prove causality, guarantee future profitability, or establish that all nonlinear models work or fail. It is historical walk-forward evaluation of a frozen recipe, not a claim that these years have never been examined by anyone previously.

## 2. Scope and frozen design

| Item | Required v1 choice |
|---|---|
| Observation | One eligible country market at one month-end |
| Pooling | One shared model across countries and dates |
| Base universe | 31 representative markets, specified in Section 4 |
| Features | Exactly the 14 numerical inputs in Section 6 |
| Target | Next-three-month USD total return minus the equal-weight eligible-universe three-month return |
| Target representation | Continuous decimal return; `0.03` means three percentage points of outperformance |
| Prediction frequency | Monthly |
| Refit frequency | Annually, using expanding history and completed labels only |
| Models | Ridge; additive EBM; matched EBM with five pairwise interactions |
| Initial training origins | January 2008 onward, subject to maturity and data gates |
| Development outcome window | January 2013 through December 2015 |
| Primary evaluation outcome window | January 2016 through December 2025 |
| Subperiods | 2016-2020 and 2021-2025, defined by complete outcome windows |
| Primary comparison | Mean monthly rank IC of C minus B |
| Uncertainty | Paired circular time-block bootstrap, block length 12 months, 2,000 draws |
| Portfolio illustration | Quarterly top six versus bottom six; secondary and explicitly hypothetical |
| Source access | Read-only; no writes to either production DuckDB file |
| New data collection | Out of scope; use existing databases and approved local source artifacts |

Do not add country identifiers, country dummies, dates, year/month indicators, previous research scores, or precomputed interactions as predictors. No graph model, neural network, PCA, feature-selection sweep, rolling-window sweep, direct ranking loss, target discretization, or Sharpe optimization in v1.

## 3. Repository integration and source safety

### 3.1 Verified source entry points

The public inventory identifies two separate databases: `Data/asado.duckdb` and `Data/loop/asado_loop.duckdb`. It lists raw-factor, consensus, and country-return surfaces. These are candidate inputs, not proof of their usable joint coverage or historical availability. [S1]

Use these source contracts as the initial mapping, then verify the actual local schema:

| Required input | Candidate source | Required checks |
|---|---|---|
| Raw valuation, yields, FX | Warehouse `t2_raw(date, country, value, variable)` | Units, observation-date convention, instrument definition, duplicate keys, historical availability |
| Raw consensus | Loop `consensus_daily(date, country, target_year, value, variable, source)` | Target-year semantics, observation-date availability, source vintage properties |
| Country monthly returns | Loop `country_returns_monthly(date, country, return_1m)` | USD versus local currency, total versus price return, period labeling, completed periods |
| Universe | `scripts/loop/loopdb.py::T2_UNIVERSE` | Exact names, exclusions, one representative per economy |
| Metadata | Existing variable registry, source collectors, and instrument definitions | Provenance and field interpretation only; no research-performance filtering |

The table definitions above are supported by the ingestion and return-builder code. [S2][S3][S4] A source table's existence does not certify that its values are point-in-time safe.

### 3.2 Non-destructive execution

Open source databases with read-only connections. Never invoke warehouse setup, rebuild, collector, or loader scripts merely to run this study. The repository inventory warns that warehouse setup recreates the warehouse; study artifacts therefore MUST live outside the production database. [S1]

Do not change existing database tables, views, collectors, scheduled jobs, configurations, or previous study outputs. Do not write this study into the existing loop database either. Only new study code, tests, a study config, documentation, and a scoped ignore rule may be added.

Read only the necessary variables, countries, and date ranges. Export immutable, filtered Parquet snapshots into the new run directory. Record source file metadata and extraction hashes. If a source is being rebuilt or cannot be opened safely, exit with a source-access blocker. Do not copy a live database file while it is being written, kill a database-owning process, or disable locks.

No data, fitted artifacts containing restricted data, credentials, or detailed proprietary observations may be committed or transmitted to an external service. Reports and data stay local unless separately authorized.

### 3.3 Data access is not assumed

The coding agent must discover the actual repository root rather than hard-code a user's home-directory or Dropbox path. The two source DB paths are configurable and default to repository-relative paths above.

If neither live data nor an approved local snapshot is accessible, deliver the complete code and synthetic-test suite, plus `BLOCKED_DATA.md`. Do not present fixture results as economic findings.

## 4. Universe, membership, and coverage

### 4.1 Base registry

The repository's canonical list contains 34 market labels. Its mapping associates ChinaA and ChinaH with one economy and the three U.S. sleeves with one economy. [S5][S6]

For this study, exclude exactly `ChinaA`, `NASDAQ`, and `US SmallCap`. Retain these 31 labels, in this order:

```text
Australia, Brazil, Canada, Chile, ChinaH, Denmark, France, Germany,
Hong Kong, India, Indonesia, Italy, Japan, Korea, Malaysia, Mexico,
Netherlands, Philippines, Poland, Saudi Arabia, Singapore,
South Africa, Spain, Sweden, Switzerland, Taiwan, Thailand,
Turkey, U.K., U.S., Vietnam
```

Verify these names against the local source. Additional entries in a country-mapping file are not permission to enlarge the universe. Store explicit aliases separately; ambiguous aliases are errors.

The use of a present-day base registry is a limitation. Report inception dates and unavailable histories; do not claim this is a survivor-free reconstruction of every historically investable country.

### 4.2 Monthly eligibility

For each signal month `t`, construct a preliminary country set `C_t` using information available at that forecast cutoff only. A country qualifies when all local raw ingredients for features 1-11 exist, pass source-quality rules, and have the required historical lookbacks. Membership must not depend on a future return being present or favorable.

Compute valuation ranks and the relative-momentum benchmark within `C_t`. The global features are constructed separately as described in Section 6. If all three global features are available and `len(C_t) >= 20`, set `U_t = C_t`; otherwise the month fails the primary coverage gate.

All three models use the exact same `U_t` and feature rows. Do not select a smaller full-history complete-case country universe. Do not repeatedly rerank after joining future labels.

### 4.3 Coverage gates

Primary evaluation requires:

- At least 20 eligible countries for every scheduled development and evaluation signal month.
- At least 48 eligible historical signal months and 1,000 training rows at the first development fit, with outcomes already complete.
- Complete, verified target returns for every member of each evaluation `U_t`.
- An uninterrupted global-return history for every required feature window.

Audit these gates before performance analysis. They are proposed pilot thresholds, not estimates of statistical power. If a gate fails, do not silently change the date range, remove a feature, or weaken the threshold. Finish the software and report the exact country/month/field gaps. An explicit exploratory mode may produce a qualified report on available data, but it must be labeled `EXPLORATORY`, show every excluded month, and cannot produce the primary success verdict.

## 5. Information timing, provenance, and returns audit

### 5.1 Four different dates

The implementation must distinguish:

1. `source_date`: the date recorded by the source.
2. `observation_period_end`: the period the number describes.
3. `available_at`: when the historical observation could have been known.
4. `ingested_at`: when ASADO obtained the record locally.

A 2026 download can contain a legitimate historical market series; the ingestion date alone does not invalidate it. Conversely, an old observation date does not establish that today's revised value was available then.

### 5.2 Forecast convention

`signal_month` is a calendar-month period. `forecast_date` is its calendar month-end. Define the logical forecast cutoff as 12:00 UTC on the following calendar day, after the signal month's global market closes.

An input must have `observation_period_end <= forecast_date` and `available_at <= forecast_cutoff`. The additional time allowance does not authorize using any new-month economic observation or price. For date-only sources with verified historical date semantics, use the conservative convention `available_at = source observation date + one day at 12:00 UTC`; preserve that convention in the mapping. If actual publication times are later, use those instead.

The primary label is a calendar-month close-to-close research target. It is not a claim of executable trading at a closing price after seeing that same close. The quarterly illustration must carry this limitation. A later execution study requires actual tradable instruments and post-cutoff entry prices.

### 5.3 Point-in-time status

Every primitive source mapping must receive one of these statuses:

| Status | Meaning | Treatment |
|---|---|---|
| `VERIFIED_HISTORICAL_ASOF` | Historical value and availability convention are documented; vintages or provider historical-as-of semantics support the claim | Eligible for primary, with evidence recorded |
| `RECONSTRUCTED_NOT_VINTAGE_VERIFIED` | Historical dates exist, but revision/backfill behavior is not established | Exploratory only; cannot be silently promoted |
| `UNKNOWN_OR_FORWARD_CONTAMINATED` | Timing is unknown or future information is embedded | Reject |

Verification can come from the source's data-generation contract, contemporaneous snapshots, or documented provider field semantics. An arbitrary lag does not repair a revised-history problem. The normalized observed-panel view is not, by its name alone, a historical-vintage guarantee; its implementation filters certain families and dates rather than establishing each value's past availability. [S7]

Do not require all sources to have an original local ingestion timestamp in 2008. Require evidence for what their historical records represent. Distinguish a defensible provider history from an unsupported point-in-time claim.

### 5.4 Raw-feature timing audit

The monthly raw-factor date convention must be established independently from the return table's date convention. A date displayed as the first of a month might label a snapshot at the start or end of a period; do not assume which. Reconcile against approved daily levels or the original raw-workbook extraction logic when available. If unresolved, mark the source blocked rather than choose whichever shift improves performance.

Reject unknown units, invalid ratios, duplicated keys with conflicting values, nonfinite numbers, and silent mixing of different instruments or conventions. De-duplicate exact duplicates only under a documented policy, retaining a count. Never average conflicting duplicates.

### 5.5 Return-source audit

The return builder documents first-of-month labels for the month in which the return was earned and decimal units. [S4] Normalize internally to explicit `return_month`, `period_start`, `period_end`, and `available_at`.

Verify that the chosen series represents broad-market **USD total returns**, with consistent dividend treatment across markets. Reconcile a deterministic sample across countries, periods, and year boundaries against total-return index levels or other approved source records. Suggested sample: every country with usable evidence, in an early year, a middle year, and a recent year. Never select checks based on model performance.

If the underlying total-return series is local-currency and an approved FX series exists, convert explicitly:

`1 + r_USD = (1 + r_local) * (FX_end / FX_start)`,

where FX is USD per unit of the index's local currency. Never convert a USD series again. Never assume a market index's quote currency equals its economy's currency; ChinaH is an important case to audit.

Do not silently substitute a price-return index. Do not winsorize or clip labels. A return below -100% is invalid; an unusually large positive return triggers a units/source check, not automatic clipping. Preserve genuinely flat returns. If daily data are used for reconciliation, use verified trading calendars rather than deleting all zero-return observations.

## 6. Exact feature specification

### 6.1 Shared notation and preprocessing rules

`t` denotes the signal calendar month. `t-3` means three calendar months earlier, not three previously observed rows. Reindex to an explicit monthly calendar before computing lags. All rolling windows require every constituent month; never bridge a gap by shortening a window.

The raw-factor reference lists candidate fields including `Earnings Yield`, `Best PBK`, `Best Div Yield`, `10Yr Bond`, and `Currency`. These names do not settle their vendor definitions or units. [S8]

No extra features, missingness indicators, country IDs, interactions, or bin labels are added. Features remain float64; targets remain float64.

For market snapshots, require a valid observation in the requested calendar month. Do not forward-fill across missing months. A last-trading-day observation may precede calendar month-end by up to seven calendar days; longer gaps require a documented market-calendar explanation and otherwise fail.

For consensus, use the last observation available by each endpoint, for the correct target year, with a maximum observation age of 93 calendar days at that endpoint. Unchanged forecast values are not inherently stale. Do not backfill from a future observation.

### 6.2 Feature dictionary

| ID | Canonical feature name | Exact construction | Units |
|---|---|---|---|
| F01 | `earnings_yield_cs_pct` | Cross-sectional midrank percentile of audited raw earnings yield in `C_t` | 0-1 |
| F02 | `book_to_price_cs_pct` | Reciprocal of valid positive price-to-book, then cross-sectional midrank percentile in `C_t` | 0-1 |
| F03 | `dividend_yield_cs_pct` | Cross-sectional midrank percentile of audited dividend yield in `C_t` | 0-1 |
| F04 | `gdp_consensus_cy_pp` | Latest GDP-growth consensus for target year `year(t)` available at `t` | Percentage points |
| F05 | `gdp_revision_3m_pp` | Current GDP forecast minus the forecast available at `t-3`, both for `year(t)` | Percentage points |
| F06 | `cpi_consensus_cy_pp` | Latest inflation consensus for target year `year(t)` available at `t` | Percentage points |
| F07 | `cpi_revision_3m_pp` | Current inflation forecast minus the forecast available at `t-3`, both for `year(t)` | Percentage points |
| F08 | `govt_10y_yield_pp` | Last available ten-year local-currency government-bond yield in month `t` | Percentage points |
| F09 | `govt_10y_yield_change_3m_pp` | Yield at `t` minus yield at `t-3` | Percentage points |
| F10 | `fx_vol_12m_ann` | Sample standard deviation of 12 monthly FX log changes ending at `t`, times sqrt(12) | Annualized decimal volatility |
| F11 | `relative_momentum_12_1` | Compounded country USD total return over months `t-11` through `t-1`, minus the mean of those country cumulative returns in `C_t` | Decimal return |
| F12 | `global_equity_return_3m` | Compound the global monthly series `G_m` over `t-2, t-1, t` | Decimal return |
| F13 | `global_equity_vol_12m_ann` | Sample standard deviation of `G_m` over `t-11` through `t`, times sqrt(12) | Annualized decimal volatility |
| F14 | `us_10y_yield_change_3m_pp` | Audited U.S. ten-year yield at `t` minus its yield at `t-3`, broadcast identically to all countries | Percentage points |

The ordering above is the model input order and is part of the frozen contract.

### 6.3 Valuation details

For `n = len(C_t)`, use `(average_rank - 1) / (n - 1)` with ascending ranks. Higher values therefore mean cheaper valuation or higher yield. Ties receive average ranks; an entirely tied cross-section maps to 0.5.

Negative earnings yield is permissible when it genuinely represents negative aggregate earnings. Do not replace it with zero. Price-to-book must be positive to use its reciprocal in this specification. Dividend yield must be nonnegative. Treat vendor sentinel values as missing according to verified metadata, not value guessing.

Record whether earnings yield, book value, and dividend yield are trailing or forecast measures. A field prefixed `Best` must not automatically be described as a realized accounting measure. Mixed definitions across countries are a data gate, not a modeling opportunity.

### 6.4 Consensus details

Use raw `CONS_GDP_PCT` and `CONS_CPI_PCT`, with `target_year` retained. The collector's raw layout supplies these fields. [S6] Do not use existing consensus signal tables or a previously constructed blended forecast feature.

Example: at March 2018 month-end, compare the March 2018 forecast for 2018 with the December 2017 forecast for 2018. Both endpoints use target year 2018. A same-target forecast may have been called "next year" at the earlier endpoint; that is valid.

A forecast of 3.2% is stored as `3.2` in percentage-point units; a revision from 3.2% to 3.5% is `0.3`, not `0.003` and not a 9.375% relative change.

Current-year forecasts have a changing forecast horizon through the calendar year. This is a declared v1 limitation, not a reason to silently substitute a constant-horizon blend. Report availability by month of year as a data diagnostic; do not add calendar features.

### 6.5 Bond and FX details

A yield changing from 4.2% to 4.7% has a change of `0.5` percentage points. Valid negative government-bond yields remain valid. Different sovereign yield definitions or tenor substitutions require a new mapping approval; do not substitute a two-year yield for a missing ten-year yield.

For F10, normalize FX to USD per unit of the economy's domestic currency. Use 13 consecutive month-end levels to produce 12 log changes, `log(FX_m / FX_(m-1))`, with sample standard deviation `ddof=1`. The U.S. domestic-currency-versus-USD series is identically one and its volatility is exactly zero. Do not replace it with a dollar index. Record the economy-currency mapping separately from the currency used to convert the equity index return.

### 6.6 Global feature series

Define a separate historically rebalanced equal-weight reference series. For each return month `m`, fix its reference membership `H_m` using only the base registry, documented market availability, and information known at the preceding month-end. Require a valid preceding-month return to establish an active history; do not include a market before its known availability.

Set `G_m = mean(r_j,m for j in H_m)` with equal weights fixed at the preceding month-end. At least 20 members are required. If a subsequently earned return is missing for a member, flag that reference month incomplete; do not quietly remove the member and renormalize. Store `H_m` and the weights.

This global series depends only on return-source membership, not on consensus coverage or the model's future outcomes. Its construction therefore does not depend circularly on F12/F13 or `C_t`.

The global series is a study-specific equal-weight proxy, not ACWI. It is a different benchmark from the target benchmark in Section 7: the former is monthly rebalanced, while the latter averages the eligible countries' complete three-month buy-and-hold returns.

All three global feature values must be identical across countries for each forecast date. Additive global terms cannot change the within-date prediction ordering; interactions with country-varying inputs can.

## 7. Target construction and label maturity

### 7.1 Target formula

For each `i` in the pre-established `U_t`:

```text
country_return_3m[i,t] = product(1 + r[i,t+k], k=1..3) - 1
benchmark_return_3m[t] = mean(country_return_3m[j,t], j in U_t)
target_relative_3m[i,t] = country_return_3m[i,t] - benchmark_return_3m[t]
```

Do not sum monthly returns, compound monthly excess returns, or average a different universe for each country. The benchmark includes the country itself. Do not divide relative returns by volatility or beta.

Example: `country_return_3m=0.08` and `benchmark_return_3m=0.05` produces `target_relative_3m=0.03`. A country losing 10% against a benchmark losing 15% has a target of `0.05`.

The arithmetic average target within each complete `U_t` must equal zero to numerical tolerance. Subtracting the same benchmark preserves the countries' realized ordering. These are benchmark-relative, not necessarily beta-neutral, outcomes.

### 7.2 Missing outcomes

Eligibility and predictions are fixed before labels are attached. If a future outcome is missing for an eligible country, keep the prediction and emit a label-integrity error for the entire affected cohort. Do not silently drop that country, recompute the benchmark among survivors, or fabricate a zero return.

A verified suspension, closure, or liquidation requires an explicit source-based treatment. Until resolved, it is a primary-evaluation blocker. Missing terminal months outside the fixed evaluation horizon are censored, not errors.

### 7.3 Label availability

Store `label_start`, `label_end`, and `label_available_at`. The latter is the latest availability time among all returns used to construct the cohort target, and no earlier than the logical cutoff following the last outcome month.

A row enters training only when `label_available_at <= fit_cutoff` and its forecast origin precedes the fit's new predictions. Do not merely check whether `forecast_date < fit_cutoff`.

In a January 2018 annual fit, a September 2017 signal with October-December 2017 outcomes may qualify if those data are available. An October 2017 signal with November 2017-January 2018 outcomes cannot.

## 8. Chronological development and evaluation

### 8.1 Define periods by their complete outcome windows

Use these exact schedules, before any data-driven exclusions:

| Phase | Permitted outcome months | Corresponding signal months |
|---|---|---|
| Initial training | Matured historical labels from origins starting January 2008 | Selected by fit cutoff; never force incomplete labels into training |
| Development | January 2013-December 2015 | December 2012-September 2015: 34 origins |
| Primary evaluation | January 2016-December 2025 | December 2015-September 2025: 118 origins |
| Test block 1 | January 2016-December 2020 | December 2015-September 2020: 58 origins |
| Test block 2 | January 2021-December 2025 | December 2020-September 2025: 58 origins |

The October and November 2020 origins have outcome windows crossing the subperiod boundary. Include them in the contiguous overall evaluation, but exclude them from both block-specific summaries. Thus `58 + 58` is intentionally two fewer than `118`.

This convention avoids ambiguous claims that an October 2025 signal has a fully observed three-month outcome within 2025. No 2026 outcomes are needed for this study.

### 8.2 Annual refit convention

`model_year Y` is fitted using the cutoff immediately after December month-end of `Y-1`. It predicts signal months December `Y-1` through November `Y`, as applicable to the phase.

At each annual refit:

1. Select all eligible training origins starting January 2008 whose cohort labels are available by the fit cutoff.
2. Select all countries for a date together; never split a month's country rows between training and validation/test.
3. Fit preprocessing from this training set only.
4. Fit the specified models using their locked settings.
5. Predict the applicable monthly cross-sections without using their labels.
6. Save models, preprocessing, exact training-row IDs, timestamps, and predictions.

The December 2015 signal is the first forecast for the January-March 2016 outcome window and uses the 2016 annual model. Development settings must have been locked before this forecast is evaluated.

### 8.3 Walk-forward is not a permanently static holdout

During the test period, earlier test observations may enter later annual training sets after their complete outcomes become available. This is the prespecified updating rule, not leakage. It does not authorize selecting new features, changing settings, or choosing the refit frequency after looking at test performance.

The two test blocks are temporal stability checks, not statistically independent replications. Later models can have trained on matured earlier-block observations.

Use a custom calendar- and maturity-aware splitter. A row-count gap in a generic time splitter is not sufficient for this panel. General time-series split documentation supports chronological ordering, but does not implement this study's country grouping and three-month label rules automatically. [S9]

### 8.4 Expanding history only

Do not test rolling windows in v1. At later refits, retain all eligible history from the frozen start. A different training start or forgetting rule requires a separately registered experiment, not a quiet adjustment to this one.

## 9. Models, preprocessing, and limited tuning

### 9.1 Shared numerical contract

Use float64 matrices, the same 14 columns, and identical row ordering across models. For `N` training rows across `T` training months, assign:

`sample_weight[i,t] = N / (T * n_t)`.

Each month then has the same total weight and the average row weight is one. Do not treat countries on a date as independent time periods in evaluation.

Fit one weighted `StandardScaler` on each annual training set and apply it to every model and prediction row for that fit. It must never see development/test features at fitting time. Reuse the same fitted scaler across A/B/C. Zero-variance features retain their columns, with the standard scale-one convention. Invert scaling for explanation axes. Weighted scaling and ridge weighting are supported by their APIs. [S10][S11]

Do not impute missing inputs in the primary design: use the same complete eligible rows for all models. Do not winsorize features or targets in v1. Source validation and EBM binning are not permission to alter extreme but valid observations.

### 9.2 Model A: ridge regression

Use `sklearn.linear_model.Ridge`, `fit_intercept=True`, deterministic `solver="svd"`. Minimize weighted squared error plus an L2 penalty. [S11]

Tune normalized penalty `lambda` over exactly `[0.01, 0.1, 1.0]`. Set the estimator's `alpha = lambda * N` for each fit, so the intended regularization remains on the same average-loss scale as the training sample expands.

Choose lambda by average development monthly rank IC across the chronological development predictions. Ties within `1e-6` select the larger penalty. No other ridge settings are tuned.

### 9.3 Models B and C: Explainable Boosting Machines

Use `interpret.glassbox.ExplainableBoostingRegressor`. B contains only single-feature terms. C adds five automatically selected two-feature terms. The EBM API distinguishes integer `interactions=5` from string `"5x"`; they must not be confused. Disable internal random validation. [S12]

Shared requested settings:

```python
feature_types = ["continuous"] * 14
objective = "rmse"
max_bins = 32
max_interaction_bins = 8
learning_rate = 0.02
max_leaves = 4
min_samples_leaf = 100
validation_size = 0
outer_bags = 1
inner_bags = 0
early_stopping_rounds = 0
greedy_ratio = 0.0
cyclic_progress = True
smoothing_rounds = 0
interaction_smoothing_rounds = 0
reg_alpha = 0.0
reg_lambda = 0.0
random_state = 1729
n_jobs = 1
```

Verify parameter names against the installed, pinned version. Explicitly record all effective parameters, including defaults. If a required option is unsupported, do not silently drop it; use a compatible pinned version or report an implementation blocker.

B uses `interactions=0`. C uses `interactions=5`, with global-global candidate pairs excluded: `(F12,F13)`, `(F12,F14)`, `(F13,F14)`. Their within-date contributions cannot distinguish countries. Use feature-index tuples matching the frozen feature order, and test the installed API's exclusion behavior.

Permit at most five selected pair terms; if the library cannot select five valid terms, report the actual count. No pair can contain country identity, a label, or more than two variables. Pair selection must occur within each annual training fit, never once on the full history.

### 9.4 Shared EBM budget: deliberately conservative controlled comparison

Tune `max_rounds` over exactly `[250, 750, 1500]` using **Model B's** average development rank IC. Ties within `1e-6` select fewer rounds. Apply that selected round budget unchanged to both B and C.

Model C receives no separate hyperparameter search. Its only substantive design change is enabling the limited pairwise terms. This intentionally favors a well-tuned additive baseline over giving the interaction model extra search opportunities. C naturally has an additional interaction stage; log its effective terms and fitting work rather than claim equal total parameter counts.

Generate development predictions for C using the selected shared settings for reporting, but do not use them to choose new settings. Do not fit a grid on any test period.

### 9.5 Predictions and cross-sectional centering

Save both `prediction_raw` and:

`prediction_relative = prediction_raw - mean(prediction_raw across U_t)`.

Center using predicted values only, before attaching outcomes. This enforces a zero-mean relative forecast without changing rankings. Use the centered value for return-calibration metrics and portfolio ranking. Do not subtract the subsequently realized benchmark from a prediction.

### 9.6 Determinism and environment

Pin the full study dependency environment and record Python, package, platform, thread, and seed settings. Use CPU execution and no external model API. Model fitting is a local numerical computation; the implementation agent's language model does not generate return forecasts.

Repeated runs on the same frozen snapshot and environment must reproduce predictions within a specified numerical tolerance, recommended `1e-10` absolute error. Never choose a seed based on performance.

## 10. Primary evaluation and uncertainty

### 10.1 Monthly rank IC

For each model and signal month, compute Spearman correlation across the common `U_t` between its prediction and `target_relative_3m`. Use average ranks for ties. Spearman correlation assesses monotonic ranking, not return-scale calibration. [S13]

If every prediction is tied, record `constant_prediction=true` and assign the prespecified operational score `IC=0` rather than dropping an inconvenient date. This is a study convention: mathematical Spearman correlation is undefined for a constant input. If every realized target is tied, flag a target-degeneracy data issue and do not silently score it.

Do not use a row-pooled correlation as the main metric. Average the monthly ICs equally.

### 10.2 Primary statistic

Compute paired monthly differences:

`delta_ic_cb[t] = ic_C[t] - ic_B[t]`.

The primary estimate is their arithmetic mean across all 118 scheduled origins when the primary data gates pass. Also report C minus A and B minus A as secondary comparisons.

### 10.3 Confidence interval

Use a circular moving-block bootstrap over the **calendar-ordered monthly metric vectors**, not country rows. Choose a uniformly random start month, take 12 consecutive monthly indices with circular wrap, append independently sampled blocks until at least 118 months are obtained, and truncate to 118. Repeat 2,000 times with seed 271828.

Use the same sampled indices for all model IC series and their differences. Report the 2.5th and 97.5th percentiles of bootstrap means for C's IC and C-minus-B. Standard time-series bootstrap implementations provide circular-block methods; an explicit tested implementation is also acceptable. [S14]

Do not report an IID country-month standard error or multiply the sample size by the number of countries to claim independent evidence. The interval is an approximate forecast-comparison uncertainty estimate conditional on this frozen procedure and historical sample; it does not undo past research selection or establish stationarity.

Keep block length and repetitions fixed. No search over block lengths to obtain significance. Exploratory data with missing calendar months must not be compressed into an apparently contiguous series for this test; the primary verdict is disabled until coverage is resolved.

### 10.4 Supporting statistics

Report, without using them for model selection:

- Mean and median monthly IC, fraction of positive-IC months, and the two block means.
- Equal-month-weighted MSE and MAE of centered relative predictions; MSE of a zero-relative-return baseline; `1 - model_MSE / zero_baseline_MSE` when the denominator is positive.
- Prediction dispersion and mean realized relative return by five predicted-rank groups; grouping is an evaluation display only.
- Number of months, unique countries, country-month rows, and coverage by month.

Do not call `mean(IC)/std(IC)*sqrt(12)` a portfolio Sharpe ratio. No standalone significance claims for dozens of individual interaction surfaces.

### 10.5 Scientific verdict

Store individual evidence flags before deriving a verdict:

`C_positive_ic`, `C_ic_ci_above_zero`, `CB_delta_ci_above_zero`, `C_beats_A_mean`, `CB_positive_block1`, `CB_positive_block2`, `primary_data_valid`.

`SUPPORTS_PILOT_HYPOTHESIS` requires all of them to be true. Describe the result as evidence for this pilot specification, not proof.

If data are valid but the C-minus-B interval overlaps zero, use `INCONCLUSIVE_INTERACTION_GAIN`. If its upper bound is at or below zero, use `NO_DEMONSTRATED_INTERACTION_GAIN`. If interaction improvement is established but C still lacks positive useful ranking evidence, use `INTERACTION_GAIN_WITHOUT_ESTABLISHED_USEFUL_SIGNAL`. If stability or the linear comparison fails despite an overall positive difference, use `MIXED_EVIDENCE`.

Data or timing failures yield `BLOCKED_DATA` or `INVALID_PRIMARY_EVALUATION`, never a positive scientific verdict. Software acceptance must not require the hypothesis to be supported.

## 11. Secondary quarterly portfolio illustration

Use signals at December, March, June, and September month-ends, selecting those whose next three calendar months lie within the evaluation window. There are 40 scheduled quarterly cohorts across 2016-2025 before data failures.

For each model, take the six highest centered predictions and six lowest predictions. Break boundary ties by a frozen alphabetical country-key order, and report tie counts. Long-leg return is the mean of the six country three-month returns; short-basket return is the mean of the bottom six. The research spread is `long_leg_return - short_basket_return`.

Use absolute country returns to account for the two legs. Using relative outcomes would give the same spread because the common benchmark cancels; training nevertheless remains on the relative target.

Report mean and median quarterly spread, fraction of positive quarters, the two subperiod means, country selection frequencies, and concentration. Do not optimize the number six, the rebalancing rule, or the ranking cutoff.

For a simple, clearly labeled cost sensitivity, define target weights `+1/6` and `-1/6`, and compute `target_weight_turnover_proxy = sum(abs(w_q - w_(q-1)))`. Initial prior weights are zero. Separately report terminal liquidation turnover. Show one-way cost scenarios of 0, 10, and 25 basis points times this turnover proxy. State that this ignores between-rebalance weight drift, financing, borrow, taxes, market impact, and instrument constraints; these are illustrative deductions, not executable net returns.

Do not compound these independent quarterly spread observations into a strategy CAGR or call them a funded long-short portfolio without specifying cash, collateral, leverage, weight drift, and rebalancing accounting. No production strategy or trading recommendation is an output of v1.

## 12. Interpretation without post-hoc storytelling

Save every selected interaction and its source annual fit. Report selection frequency across annual models, along with sign/shape changes where meaningful. Do not refit on the full 2016-2025 data to explain historical predictions.

For the final annual model, choose up to three interaction displays using training-only contribution magnitude. Display their surfaces in original feature units alongside support counts and the number of distinct supporting training months. Distinguish an empirically supported region from a sparse extrapolation region.

A two-dimensional surface need not be a pure interaction: it can contain additive components. Include a simple nonadditivity diagnostic, such as rectangular differences `g(a,c) - g(a,d) - g(b,c) + g(b,d)`, on adequately supported grid cells. If these are essentially zero, do not describe the surface as strong evidence of conditional behavior. Do not alter predictions while doing this diagnostic.

Describe findings as learned conditional associations, not mechanisms proved by the model. Do not choose a particularly attractive crisis episode or pair after evaluating its investment performance and present it as prespecified.

## 13. Artifacts and data contracts

### 13.1 Run directory

All generated outputs go beneath:

```text
Data/studies/nonlinear_country_returns/v1/<run_id>/
```

Use a unique run ID containing a UTC creation time and a short effective-config hash. Never overwrite another run. A resume operation must validate all frozen hashes.

Required outputs:

```text
manifest.json
config.effective.yaml
source_mapping.json
source_audit.md
coverage_by_month.csv
coverage_by_country.csv
exclusions.parquet
snapshots/raw_factors.parquet
snapshots/consensus.parquet
snapshots/returns.parquet
feature_provenance.parquet
reference_membership.parquet
features.parquet
labels.parquet
panel.parquet
splits.parquet
development_results.csv
lock.json
models/<model_year>/<model_id>/...
predictions.parquet
monthly_metrics.csv
bootstrap_summary.json
quarterly_spreads.csv
interaction_registry.csv
report.md
report.html
figures/...
execution_log.jsonl
```

An unavailable stage must have a specific status and blocker artifact, not an empty file masquerading as a result.

### 13.2 Features and provenance

`features.parquet` has one row per `(forecast_date, country)` with:

- `signal_month`, `forecast_date`, `forecast_cutoff`, `country`, `economy_code`, `universe_id`, `eligible`, and `eligibility_reason`.
- The 14 canonical float64 feature columns, in their frozen order.
- `feature_available_at_max`, `pit_status`, and `feature_snapshot_id`.

Country/date metadata must not be automatically included in the estimator matrix. Select the feature columns from an explicit allowlist.

`feature_provenance.parquet` is long-form, keyed by `(forecast_date, country, feature_name, primitive_role)`, and includes source table, source variable, source country, source row key, observation period, available time, target year when relevant, units, transformation version, and PIT evidence reference. Rolling features may reference a separately hashed list of constituent source rows rather than duplicating large payloads.

### 13.3 Label contract

`labels.parquet` includes the pre-established `universe_id`, `country_return_3m`, `benchmark_return_3m`, `target_relative_3m`, `label_start`, `label_end`, `label_available_at`, `label_complete`, and source-return provenance.

`panel.parquet` is a derived audit join, not the input to an unrestricted automatic feature-selection routine. Development and fitting loaders must explicitly restrict both features and labels by permitted periods and maturity.

### 13.4 Prediction contract

`predictions.parquet` includes `run_id`, `model_id`, `model_year`, `fit_cutoff`, `forecast_date`, `forecast_cutoff`, `country`, `universe_id`, `training_last_origin`, `training_label_available_max`, `n_train_rows`, `n_train_months`, `prediction_raw`, `prediction_relative`, `predicted_rank`, model/scaler hash, and `phase`.

Use uniqueness key `(run_id, model_id, forecast_date, country)`. Store predictions before evaluating their labels. Every model-year fit must retain exact training-row IDs.

### 13.5 Manifest and lock

Record repository commit, dirty-tree status, PRD version/hash, effective config/hash, feature specification hash, source extraction hashes, dependency lock/hash, numerical environment, seeds, source access modes, study status, and all deviations.

After development, `lock.json` fixes the source snapshot, selected lambda, selected shared EBM rounds, model settings, universe rules, target, chronology, metrics, bootstrap settings, and code version. It must be written before test performance is computed or displayed.

Re-running reporting on frozen predictions is permitted. Retuning after seeing test results creates a new experiment ID and cannot replace this run's primary result. Bug fixes require an explicit issue and before/after provenance, not selective omission of an unfavorable run.

## 14. Implementation architecture and command-line interface

### 14.1 Suggested scoped file structure

```text
config/nonlinear_country_study_v1.yaml
scripts/nonlinear_country_study/
    __init__.py
    __main__.py
    cli.py
    config.py
    sources.py
    audit.py
    features.py
    labels.py
    splits.py
    models.py
    experiment.py
    evaluation.py
    reporting.py
    artifacts.py
tests/nonlinear_country_study/
docs/NONLINEAR_COUNTRY_STUDY_V1.md
requirements-nonlinear-country-study.lock
```

Use existing project conventions where appropriate without importing old research logic. The module list is organizational guidance; equivalent clear separation is acceptable. The data contracts, boundaries, and tests are mandatory.

### 14.2 Dependencies

Use the repository's compatible Python environment and add a separately pinned study environment if needed. Expected packages: numpy, pandas, pyarrow, duckdb, scipy, scikit-learn, interpret-core or interpret, PyYAML, pytest, and matplotlib. `arch` is optional if the circular bootstrap is implemented and tested explicitly. A basic HTML renderer is sufficient; a web application is not required.

Resolve compatible versions during implementation, pin them, and test actual signatures. Do not put guessed package versions into the lock. Avoid upgrading unrelated project dependencies.

### 14.3 Required CLI contract

These commands are requirements for the software to be built, not claims that they already exist:

```bash
python -m scripts.nonlinear_country_study audit --config config/nonlinear_country_study_v1.yaml
python -m scripts.nonlinear_country_study build-panel --config config/nonlinear_country_study_v1.yaml --run-dir <RUN>
python -m scripts.nonlinear_country_study develop --run-dir <RUN>
python -m scripts.nonlinear_country_study freeze --run-dir <RUN>
python -m scripts.nonlinear_country_study backtest --run-dir <RUN>
python -m scripts.nonlinear_country_study report --run-dir <RUN>
python -m scripts.nonlinear_country_study run --config config/nonlinear_country_study_v1.yaml
python -m scripts.nonlinear_country_study smoke-test --synthetic --output-dir <TEMP>
python -m pytest tests/nonlinear_country_study -q
```

`run` executes the full staged process in order, with automatic local locking after development and before test evaluation. No user intervention is needed for a normal valid-data run. `audit` prints the created run directory and does not examine predictive performance. `backtest` refuses to run without a valid lock.

CLI requirements: helpful errors; structured progress logs; optional `--resume`; dry-run configuration validation; no interactive prompts; no silent network calls; no overwrite of completed outputs; bounded CPU use. Unknown config keys are errors.

Use exit code 0 for a completed software run regardless of scientific outcome; 2 for inaccessible/missing sources; 3 for primary data-quality gates; 4 for config/hash integrity failures; 5 for unexpected runtime errors. Always write a machine-readable stage status when a run directory can be created.

## 15. Tests and acceptance criteria

### 15.1 Core test matrix

| Area | Required assertion |
|---|---|
| Universe | Exactly the specified base labels; no duplicate U.S. or China sleeves; aliases cannot add a new member |
| Read-only safety | Source connections reject mutation; study execution does not modify source files or invoke rebuild scripts |
| Unknown schema | A missing required table/column yields an actionable blocker, not an empty successful panel |
| Date semantics | An April return labeled April 1 is recognized as earned in April, not available at the start of April |
| Calendar lags | A missing February record cannot turn a nominal three-month change into a four-month comparison |
| Availability | A source observation available after cutoff is excluded; its original observation date cannot bypass the rule |
| Future perturbation | Changing every observation and outcome after a historical cutoff leaves that cutoff's features, eligibility, scaler, pair selection, and predictions unchanged |
| Same-target revisions | January/December rollover uses the same target year at both comparison endpoints |
| Consensus staleness | A future backfill is forbidden; an unchanged but valid historical quote is not rejected solely because its value is unchanged |
| Valuation ranks | Ties, all-equal values, negative valid earnings yields, and invalid price-to-book are handled as specified |
| Yield units | 4.2% to 4.7% yields `+0.5` percentage points |
| FX | F10 needs 13 levels; quotation inversion is handled; U.S. F10 is zero; missing months are not bridged |
| Momentum | Exactly months t-11 through t-1 enter; month t and all future months are excluded |
| Global series | Membership is known before its return month; missing member returns do not cause silent renormalization |
| Global broadcasting | F12-F14 are identical across all countries on a date |
| Compounding | Monthly returns compound multiplicatively; for +10%, -10%, 0%, the three-month result is -1%, not zero |
| Relative target | Target means are zero within the original complete U_t; a +8% versus +5% example gives +3 percentage points |
| Missing future labels | Predictions survive, but an incomplete cohort triggers a label error rather than survivor reranking |
| Training maturity | January annual fit cannot use an October-origin three-month label ending in January |
| Fold sizes | Ideal synthetic coverage produces 34 development origins, 118 overall test origins, 58 per block, and 40 quarterly cohorts |
| Shared matrix | A/B/C receive identical country/date rows, feature order, scaler, and sample weights |
| Equal-month weights | Each month's total training weight is equal and the overall mean weight is one |
| Scaling | Test-set feature changes cannot alter a fitted scaler; constant columns are retained |
| Ridge penalty | Effective alpha equals selected normalized lambda times current training-row count |
| EBM settings | B has no pair terms; C has at most five pairs, no higher-order terms or global-global pairs; no random internal validation |
| Locked tuning | Test performance cannot change features, lambda, EBM rounds, seeds, or any primary setting |
| Prediction centering | Centering uses predictions only, sums to zero, and leaves ranks unchanged |
| IC | Ties agree with expected average-rank calculations; constant prediction gets flagged and scored zero |
| Paired bootstrap | Both models use identical sampled calendar indices; an identical model pair has exactly zero difference in every draw |
| Cost illustration | Turnover is explicitly the target-weight proxy and not described as realized implementation turnover |
| Determinism | Repeating a frozen run reproduces numerical predictions within tolerance |
| Reporting | Blocked or synthetic-only runs cannot emit a primary positive scientific verdict |

### 15.2 Synthetic end-to-end checks

Provide a small deterministic fixture for fast CI and a larger synthetic panel for model-path verification. Include:

- A known additive data-generating process with no injected interactions, to check the model and metric pipeline without requiring a particular significance outcome.
- A strong pairwise-interaction process such as `y_raw = x1*x2 + small_noise`, demeaned within each simulated date, with balanced feature support. Verify that C can represent genuinely nonadditive structure and that the implementation is not accidentally fitting an additive-only model. Use a fixed fixture and document a reasonable prediction-error tolerance rather than a flaky requirement about random p-values.
- Injected timing errors, duplicate rows, missing source histories, unavailable future labels, and a changed lock hash; each must fail at the intended stage.

Do not require every random null simulation to produce a nonsignificant result. Do not use synthetic results as evidence about actual country returns.

### 15.3 Engineering acceptance

A successful implementation has a tested CLI; no source mutations; documented mappings and timing; correct targets and splits; reproducible model training; an immutable experiment lock; complete artifacts; and an honest final report. Performance sign is not an acceptance criterion.

## 16. Phased implementation plan

### Phase 1 - Scoped integration and data audit

Inspect local repo instructions, source schemas, and timing/units definitions. Add config validation, read-only adapters, base-universe mapping, provenance structure, and audit commands. Produce availability and ambiguity reports. Do not calculate predictive correlations or inspect previous results.

**Exit:** Source mappings verified or precisely blocked; production databases unchanged; source safety tests pass.

### Phase 2 - Deterministic features and targets

Implement monthly calendars, historical-as-of joins, local eligibility, ranks, consensus revisions, return-derived features, global-reference membership, target construction, and label availability. Add the full provenance chain and future-perturbation tests.

**Exit:** Synthetic fixtures pass; eligible cohorts and feature/target contracts validate; an audited real panel exists when source gates permit.

### Phase 3 - Chronological development and model lock

Implement equal-month weighting, shared preprocessing, ridge candidates, additive EBM candidates, matched interaction model, annual maturity-aware fits, and development scoring. Write selected settings and the lock before test evaluation.

**Exit:** Development predictions are reproducible; model structures verified; no test metrics used; experiment lock validates.

### Phase 4 - Frozen walk-forward evaluation

Generate all prescribed test predictions, respecting annual updates and label maturity. Evaluate paired IC improvements and bootstrap intervals. Produce the two block summaries and quarterly illustrative spreads.

**Exit:** Prediction and metric keys are complete; test counts reconcile; no lock drift; negative or inconclusive outcomes retained without redesign.

### Phase 5 - Report and handoff

Generate self-contained Markdown and HTML reports, interaction diagnostics, source limitations, environment instructions, and a concise implementation summary. Run the complete test suite and one full frozen-data reproduction when possible.

**Exit:** Another agent can reproduce the study from the documented command and the same approved local snapshots. Any blocked real-data work is explicitly separated from completed code and tests.

## 17. Required report structure

Start with the scientific verdict and the data-validity status, not an attractive interaction plot. Include:

1. Actual observation dates, universe coverage, and provenance qualification.
2. The A/B/C comparison table: mean rank IC, calibration errors, block means, and quarterly spread.
3. The primary C-minus-B mean IC difference with its 95% block-bootstrap interval, and C's absolute ranking evidence.
4. Locked settings, training/refit schedule, and the number of independent calendar decision dates versus country rows.
5. Secondary portfolio illustration and all execution/cost limitations.
6. Training-selected interaction surfaces with support counts and nonadditivity checks.
7. Exclusions, source ambiguities, invalid cohorts, changed assumptions, and all failed gates.
8. Reproduction commands, hashes, dependency versions, and implementation-test results.

Explicitly state that a historical fit or appealing surface is not proof of a tradable effect. If the interaction model does not improve rankings, say so plainly. Do not replace the research question with a favorable alternative after seeing the data.

## 18. Definition of done and final agent response

The final agent response must state what was implemented, which tests ran, whether real databases were accessed, whether the frozen experiment actually completed, where the artifacts reside, and the scientific result or exact blockers.

Separate these categories:

- **Engineering completion:** implemented, tested, reproducible, or blocked.
- **Data validity:** historical-as-of verified, qualified exploratory, or invalid.
- **Scientific evidence:** supports the pilot, mixed, inconclusive, or no demonstrated gain.

No fabricated backtest values. No claims of database validation from reading documentation alone. No production deployment, live trading, or automatic continuation into a larger research program.

The central question remains:

> Do a few pairwise interactions improve out-of-sample forecasts of three-month relative country-equity returns beyond the same inputs used nonlinearly but separately?

---

## Appendix A. Source references and what they establish

These references support repository and API facts only. The feature choices, horizons, thresholds, tuning restrictions, and acceptance criteria are original study-design decisions in this PRD. Repository sources were inspected on September 14, 2026; the implementation must record the actual checked-out commit and audit live data separately.

**[S1] ASADO database inventory, September 13, 2026.** Database separation, candidate surfaces, and warehouse rebuild warning.  
`https://raw.githubusercontent.com/ArjunDivecha/ASADO/main/docs/DB_INVENTORY_2026_09_13.md`

**[S2] ASADO warehouse setup source.** Raw-factor table schema and unified view mapping; do not execute it for this study.  
`https://raw.githubusercontent.com/ArjunDivecha/ASADO/main/scripts/setup_duckdb.py`

**[S3] ASADO consensus loader.** Raw consensus table schema. Existing derived signal formulas are not adopted.  
`https://raw.githubusercontent.com/ArjunDivecha/ASADO/main/scripts/loop/load_consensus.py`

**[S4] ASADO monthly country-return builder.** Documented monthly labeling, decimal units, and canonical extraction. USD/total-return status still requires independent metadata verification.  
`https://raw.githubusercontent.com/ArjunDivecha/ASADO/main/scripts/loop/build_country_returns.py`

**[S5] ASADO loop database helpers.** Canonical T2 market labels. Do not inherit previous research logic or blindly reuse daily-return filtering.  
`https://raw.githubusercontent.com/ArjunDivecha/ASADO/main/scripts/loop/loopdb.py`

**[S6] ASADO consensus collector.** Country/economy mapping, target-year data, and consensus variable identifiers.  
`https://raw.githubusercontent.com/ArjunDivecha/ASADO/main/scripts/loop/collect_consensus_bbg.py`

**[S7] ASADO normalization builder.** Observed-view implementation and the distinction between filtering dates and establishing historical availability.  
`https://raw.githubusercontent.com/ArjunDivecha/ASADO/main/scripts/build_normalized_panel.py`

**[S8] ASADO factor reference.** Candidate raw-factor names.  
`https://raw.githubusercontent.com/ArjunDivecha/ASADO/main/docs/factor_reference.md`

**[S9] scikit-learn TimeSeriesSplit.** Chronological-split concepts, not a drop-in panel/maturity splitter.  
`https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html`

**[S10] scikit-learn StandardScaler.** Train-fitted scaling and sample-weight support.  
`https://scikit-learn.org/stable/modules/generated/sklearn.preprocessing.StandardScaler.html`

**[S11] scikit-learn Ridge.** Squared-error regression with L2 regularization and sample weights.  
`https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html`

**[S12] InterpretML ExplainableBoostingRegressor.** Single-feature and interaction-term controls, weighting, fit settings, and validation behavior. Confirm compatibility against the pinned implementation.  
`https://interpret.ml/docs/python/api/ExplainableBoostingRegressor.html`

**[S13] SciPy spearmanr.** Rank-correlation definition and constant-input behavior.  
`https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html`

**[S14] arch time-series bootstraps.** Circular/block resampling methods.  
`https://bashtage.github.io/arch/bootstrap/timeseries-bootstraps.html`

## Appendix B. Compact handoff instruction

```text
Implement the attached ASADO_Nonlinear_Relative_Returns_PRD.md in
ArjunDivecha/ASADO. Use the companion YAML as the initial configuration.

Read the PRD fully before coding. Start de novo from source measurements;
do not import previous research conclusions. Keep source databases read-only.
The target is continuous three-month USD total return relative to the
eligible equal-weight country universe, never absolute return or deciles.

Implement all phases, tests, CLI commands, provenance, and reports. Keep
B/C settings matched and select interactions inside each annual training
fit only. Enforce label maturity and freeze settings before test evaluation.

Run the real-data experiment when the available local sources pass the
specified gates. If data are unavailable or timing cannot be established,
finish the code and synthetic tests and produce a precise blocked-data
report. Do not fabricate results or silently change the study. A null
finding is an acceptable completed result.
```
