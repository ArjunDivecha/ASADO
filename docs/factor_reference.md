# ASADO Factor Reference

_Generated: 2026-06-09 20:42:33_
_Source of truth: `Data/cache/query_assistant/` — refreshed by `scripts/build_schema_registry.py` on every monthly update._

This document is intended to be read end-to-end by an AI agent (or human) who needs to understand exactly what the ASADO warehouse contains, what each surface means, and how to compose queries against it. Keep prose minimal; lean on tables.

Authoritative companion docs:
- `README.md` — operational entry point (commands, monthly update, MCP setup)
- `CLAUDE.md` — agent-facing project conventions
- `docs/factor_reference.md` (this file) — full DB + variable + graph reference

## At a glance

- **DuckDB tables / views:** 37
- **Distinct variables in `feature_panel` catalog:** 738
  - Raw: 244 · `_CS` cross-sectional: 235 · `_TS` time-series: 259
- **Neo4j node labels:** 7
- **Neo4j relationship types:** 9
- **Country universe:** 43 (T2 names)

## DuckDB Tables

Every analytical surface in `Data/asado.duckdb`. The `t2_master`/`t2_raw` tables are sourced from `T2 Master.xlsx` (separate Bloomberg-driven pipeline); everything else is built by ASADO collectors.

| Table | Type | Rows | Date range | Description |
| --- | --- | --- | --- | --- |
| `bilateral_portfolio_matrix` | BASE TABLE | 56,870 | 1997-12-01 → 2026-03-01 | Historical portfolio ownership matrix combining IMF PIP annual benchmarks and the U.S. TIC supplement. Common instrument_type values include equity_fund_shares, debt_long, debt_short, equity, debt_long_govt, and debt_… |
| `bloomberg_factors` | BASE TABLE | 98,969 | 1975-12-01 → 2026-06-01 | Bloomberg market-implied, macro, and ETF passive-flow data collected via OpusBloomberg. |
| `commodity_panel` | VIEW | 436,196 | 1960-01-01 → 2026-05-01 | GLOBAL commodity series (date x series, NOT country-keyed): level/MOM/YOY/3M/12M-return/vol/z per World Bank Pink Sheet commodity. Join to country returns on date as explanatory context. (Replaces the deprecated count… |
| `country_factor_attribution` | VIEW | 726,353 | 2000-02-01 → 2026-05-01 | View joining factor_top20_membership ⨝ factor_returns on (date, factor, source). Columns: (date, country, factor, weight, factor_return, contribution, source). contribution = weight × factor_return is the country's mo… |
| `country_reference` | BASE TABLE | 40 | — | Canonical ISO-to-ASADO country mapping surface. Use this to join bilateral tables that store reporter_iso3/counterpart_iso3 onto ASADO factor surfaces that use country names. |
| `daily_calendar` | BASE TABLE | 328,338 | 2000-01-01 → 2026-06-09 |  |
| `demographics_dip` | BASE TABLE | 20,026 | 1950-12-01 → 2100-12-01 |  |
| `event_log` | BASE TABLE | 146 | — |  |
| `extended_factors` | BASE TABLE | 115,224 | 1990-12-01 → 2026-06-01 | Extended country dataset built from additional free sources. |
| `external_factors` | BASE TABLE | 137,322 | 1985-01-01 → 2026-05-01 | Free-source external macro, risk, and structural data. |
| `factor_returns` | BASE TABLE | 106,036 | 2000-02-01 → 2026-05-01 | Monthly net returns of top-20%-of-countries portfolios per factor, sourced from the Econ / T2 Style / GDELT optimizer pipelines. Tidy long format with columns (date, factor, value, source). Factor names retain their _… |
| `factor_returns_daily` | BASE TABLE | 1,318,786 | 1999-12-31 → 2026-06-09 |  |
| `factor_top20_membership` | BASE TABLE | 744,154 | 2000-02-01 → 2026-07-01 | Sparse country-level membership in each factor's top-20% bucket per month. Columns: (date, country, factor, weight, source). weight = 1/N within the bucket (equal-weight); rows are present only when the country is in … |
| `feature_panel` | VIEW | 3,526,055 | 1950-12-01 → 2100-12-01 | Query-facing union of unified_panel (raw warehouse) plus normalized_panel for analytics, assistants, and feature discovery. |
| `gdelt_factors_daily` | BASE TABLE | 10,167,428 | 2015-06-24 → 2026-06-09 |  |
| `gdelt_panel` | BASE TABLE | 414,188 | 2015-09-01 → 2026-07-01 | Country-level GDELT-derived media, tone, and risk signals. |
| `gdelt_raw_daily` | BASE TABLE | 967,364 | 2015-02-18T00:00:00 → 2026-06-09T00:00:00 |  |
| `imf_factors` | BASE TABLE | 132,010 | 1980-12-01 → 2031-12-01 | IMF datasets normalized into the ASADO tidy panel shape. |
| `macrostructure_factors` | BASE TABLE | 96,120 | 1995-03-01 → 2026-06-01 | Macrostructure panel spanning bank fragility, debt structure, institutional depth, sticky-capital proxies, and transparent derived signals. |
| `normalized_panel` | BASE TABLE | 958,883 | 1950-12-01 → 2100-12-01 | Canonical ASADO-generated normalized factors. Contains _CS same-date cross-sectional z-scores and _TS rolling time-series z-scores for eligible raw source variables. |
| `predmkt_country_spillover` | BASE TABLE | 49 | — | Hand-curated market-to-country spillover edges with elasticity, channel taxonomy, and confidence level. Used for off-universe entity bridge and country composites. |
| `predmkt_daily` | BASE TABLE | 20 | — | Prediction-market daily snapshots from curated Kalshi and Polymarket markets. One row per (snapshot_date, platform, market_id, outcome_id) with probability, book fields, liquidity metrics, stale flag, and resolution s… |
| `predmkt_market_meta` | BASE TABLE | 10 | — | Prediction-market metadata registry keyed by (platform, market_id). Includes ASADO category tags, resolution clarity, and contract windows. |
| `predmkt_outcome_meta` | BASE TABLE | 20 | — | Outcome-level metadata keyed by (platform, market_id, outcome_id), including labels and scalar thresholds for distribution-style contracts. |
| `predmkt_resolutions` | BASE TABLE | 0 | — | Resolved-market calibration archive: realized outcome and probabilities captured 24h/1h before resolution. |
| `predmkt_signals_daily` | BASE TABLE | 32 | — | Derived prediction-market composite signals by date (and optionally country), including confidence scores and constituent market trace. |
| `t2_factors_daily` | BASE TABLE | 35,611,022 | 2000-01-01 → 2026-06-09 |  |
| `t2_factors_monthly_from_daily` | VIEW | 1,147,821 | 2000-01-01T00:00:00 → 2026-06-01T00:00:00 |  |
| `t2_levels_daily` | BASE TABLE | 15,342,976 | 2000-01-01 → 2026-06-09 |  |
| `t2_master` | BASE TABLE | 1,078,310 | 2000-02-01 → 2026-06-01 | Original T2 monthly factor panel. |
| `t2_raw` | BASE TABLE | 475,003 | 2000-02-01 → 2026-06-01 | Raw T2 factor levels from the authoritative T2 Master workbook. |
| `unified_panel` | VIEW | 2,567,172 | 1950-12-01 → 2100-12-01 | Unified analytic view across all ASADO factor tables. |
| `variable_meta` | BASE TABLE | 286 | — |  |
| `wb_commodity_features` | BASE TABLE | 436,196 | 1960-01-01 → 2026-05-01 | Derived trailing commodity features such as level, MOM, YOY, 3M/12M return, volatility, and z-score, keyed by series_code and feature. |
| `wb_commodity_indices` | BASE TABLE | 12,752 | 1960-01-01 → 2026-05-01 | Canonical World Bank Pink Sheet monthly commodity price indices, 2010=100, keyed by index_code. |
| `wb_commodity_meta` | BASE TABLE | 87 | — |  |
| `wb_commodity_prices` | BASE TABLE | 50,167 | 1960-01-01 → 2026-05-01 | Canonical World Bank Pink Sheet monthly nominal U.S. dollar commodity prices, keyed by commodity_code. |

## A note on `_CS` / `_TS` variants

Many raw variables are accompanied by two normalized variants in the `normalized_panel` view:

- **`_CS` (cross-sectional)** — z-score within the same date across countries. Removes global trends; high values = country looks attractive *vs. peers this month*.
- **`_TS` (time-series)** — rolling z-score within the same country across time. Removes country-specific levels; high values = country looks attractive *vs. its own history*.

The optimizer pipelines (T2 Econ, T2 GDELT) construct factor returns separately for each variant — they're treated as distinct variables, not interchangeable views of one another. `factor_returns.factor` retains the suffix for this reason.

## Variables by source

Variables in this section are listed at the *raw* level (no `_CS`/`_TS` suffix). For each raw variable, the `normalized_panel` may also expose `_CS` and `_TS` variants — see explainer above.

### `t2`

**Total variables:** 4

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `12MRet` | t2 | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `3MRet` | t2 | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `6MRet` | t2 | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `9MRet` | t2 | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |

### `t2_raw`

**Total variables:** 53

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `10Yr Bond` | t2_raw | monthly | 33 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `10Yr Bond 12` | t2_raw | monthly | 33 | 2001-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `12-1MTR` | t2_raw | monthly | 34 | 2001-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `120MA` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `120MA Signal` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `12MTR` | t2_raw | monthly | 34 | 2001-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `1MTR` | t2_raw | monthly | 34 | 2000-03-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `20 Day Vol` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `360 Day Vol` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `3MTR` | t2_raw | monthly | 34 | 2000-05-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Advance Decline` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Agriculture` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Agriculture 12` | t2_raw | monthly | 34 | 2001-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `BEST EPS` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Best Cash Flow` | t2_raw | monthly | 34 | 2005-05-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Best Div Yield` | t2_raw | monthly | 34 | 2005-05-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Best PBK` | t2_raw | monthly | 34 | 2005-04-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Best PE` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Best Price Sales` | t2_raw | monthly | 34 | 2000-03-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Best ROE` | t2_raw | monthly | 34 | 2005-09-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Bloom Country Risk` | t2_raw | monthly | 34 | 2009-07-01T00:00:00 → 2025-10-01T00:00:00 | raw |  |  |
| `Budget Def` | t2_raw | monthly | 32 | 2001-01-01T00:00:00 → 2026-01-01T00:00:00 | raw |  |  |
| `Copper` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Copper 12` | t2_raw | monthly | 34 | 2001-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Currency` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Currency 12` | t2_raw | monthly | 34 | 2001-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Currency Vol` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Current Account` | t2_raw | monthly | 33 | 2000-04-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `Debt to EV` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Debt to GDP` | t2_raw | monthly | 34 | 2001-01-01T00:00:00 → 2016-01-01T00:00:00 | raw |  |  |
| `EV to EBITDA` | t2_raw | monthly | 34 | 2005-07-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Earnings Yield` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `GDP` | t2_raw | monthly | 34 | 2001-01-01T00:00:00 → 2026-01-01T00:00:00 | raw |  |  |
| `Gold` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Gold 12` | t2_raw | monthly | 34 | 2001-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Inflation` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `LT Growth` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `MCAP` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `MCAP Adj` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Mcap Weights` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Oil` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Oil 12` | t2_raw | monthly | 34 | 2001-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Operating Margin` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `P2P` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `PX_LAST` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Positive PE` | t2_raw | monthly | 34 | 2005-05-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `REER` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `RSI14` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Shiller PE` | t2_raw | monthly | 27 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Tot Return Index` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Trailing EPS` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Trailing EPS 36` | t2_raw | monthly | 34 | 2003-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `Trailing PE` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |

### `epu`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `EPU` | epu | monthly | 22 | 1985-01-01T00:00:00 → 2025-11-01T00:00:00 | raw |  |  |

### `gpr`

**Total variables:** 4

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GPR` | gpr | monthly | 23 | 1985-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Global_GPR` | gpr | monthly | 43 | 1985-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Global_GPR_Act` | gpr | monthly | 43 | 1985-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Global_GPR_Threat` | gpr | monthly | 43 | 1985-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |

### `bis_credit`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `BIS_Credit_GDP_Gap` | bis_credit | quarterly | 40 | 2000-03-01T00:00:00 → 2025-09-01T00:00:00 | raw |  |  |

### `bis_property`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `BIS_Property_Price` | bis_property | quarterly | 40 | 2000-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |

### `bis_reer`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `BIS_REER` | bis_reer | monthly | 42 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |

### `oecd`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `OECD_CLI` | oecd | monthly | 20 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |

### `worldbank`

**Total variables:** 26

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `WB_CO2_Per_Capita` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Control_Corruption` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Current_Account_GDP` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Domestic_Credit_GDP` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_External_Debt_GNI` | worldbank | annual | 12 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_FDI_Inflows_GDP` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_FX_Reserves` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Female_LFP` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `WB_Female_Labor_Share` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `WB_GDP_Growth_Real` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Govt_Debt_GDP` | worldbank | annual | 22 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Govt_Effectiveness` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Import_Cover_Months` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Inflation_CPI` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Labor_Force` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `WB_Market_Cap_GDP` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_OldAge_Dependency` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Political_Stability` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Population` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Population_Growth` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Regulatory_Quality` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Renewable_Energy_Share` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2021-12-01T00:00:00 | raw |  |  |
| `WB_Rule_of_Law` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Trade_Openness` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Unemployment` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `WB_Voice_Accountability` | worldbank | annual | 42 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |

### `bis_policy_rate`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `BIS_Policy_Rate` | bis_policy_rate | daily | 30 | 2000-01-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |

### `bis_debt_service`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `BIS_DSR_Private` | bis_debt_service | quarterly | 33 | 2000-03-01T00:00:00 → 2025-09-01T00:00:00 | raw |  |  |

### `ecb_fx`

**Total variables:** 26

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `ECB_FX_AUD_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_BRL_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_CAD_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_CHF_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_CNY_EUR` | ecb_fx | monthly | 2 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_DKK_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_EUR_EUR` | ecb_fx | monthly | 5 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `ECB_FX_GBP_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_HKD_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_IDR_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_INR_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_JPY_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_KRW_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_MXN_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_MYR_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_NOK_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_NZD_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_PHP_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_PLN_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_SEK_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_SGD_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_THB_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_TRY_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_TWD_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2020-10-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_USD_EUR` | ecb_fx | monthly | 3 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `ECB_FX_ZAR_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw | ✓ |  |

### `fred`

**Total variables:** 6

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `FRED_HY_OAS` | fred | monthly | 34 | 2023-07-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `FRED_USD_Broad_Index` | fred | monthly | 34 | 2006-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `FRED_UST_10Y` | fred | monthly | 43 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `FRED_UST_2Y` | fred | monthly | 43 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `FRED_VIX` | fred | monthly | 34 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `FRED_Yield_Curve_10Y2Y` | fred | monthly | 43 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |

### `ndgain`

**Total variables:** 3

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `NDGAIN_Readiness` | ndgain | annual | 41 | 1995-12-01T00:00:00 → 2023-12-01T00:00:00 | raw |  |  |
| `NDGAIN_Score` | ndgain | annual | 41 | 1995-12-01T00:00:00 → 2023-12-01T00:00:00 | raw |  |  |
| `NDGAIN_Vulnerability` | ndgain | annual | 41 | 1995-12-01T00:00:00 → 2023-12-01T00:00:00 | raw |  |  |

### `ofac`

**Total variables:** 2

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `OFAC_Sanctioned` | ofac | event-driven | 34 | 2026-06-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `OFAC_Sanctions_Count` | ofac | event-driven | 34 | 2026-06-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |

### `undp_hdi`

**Total variables:** 4

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `UNDP_GDI` | undp_hdi | annual | 42 | 1990-12-01T00:00:00 → 2023-12-01T00:00:00 | raw |  |  |
| `UNDP_GII` | undp_hdi | annual | 41 | 1990-12-01T00:00:00 → 2023-12-01T00:00:00 | raw |  |  |
| `UNDP_HDI` | undp_hdi | annual | 42 | 1990-12-01T00:00:00 → 2023-12-01T00:00:00 | raw |  |  |
| `UNDP_IHDI` | undp_hdi | annual | 41 | 2010-12-01T00:00:00 → 2023-12-01T00:00:00 | raw |  |  |

### `ilostat`

**Total variables:** 2

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `ILO_LFP_Rate` | ilostat | annual | 43 | 2000-12-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `ILO_Unemployment_Rate` | ilostat | annual | 43 | 2000-12-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |

### `eia`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `EIA_Petroleum_Consumption_TBPD` | eia | annual | 43 | 2000-12-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |

### `faostat`

**Total variables:** 5

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `FAO_AgExport_GDP_Share` | faostat | annual | 32 | 2010-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `FAO_Import_Dependency` | faostat | annual | 33 | 2010-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `FAO_Self_Sufficiency` | faostat | annual | 33 | 2010-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `FAO_Terms_of_Trade` | faostat | annual | 33 | 2010-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `FAO_Trade_Openness` | faostat | annual | 32 | 2010-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |

### `oecd_bci`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `OECD_BCI` | oecd_bci | monthly | 27 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |

### `oecd_cci`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `OECD_CCI` | oecd_cci | monthly | 28 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |

### `oecd_household_dashboard`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `MS_Household_Direct_Equity_Share` | oecd_household_dashboard | annual | 28 | 2010-12-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |

### `oecd_institutional_investors`

**Total variables:** 2

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `MS_Insurance_Assets_GDP` | oecd_institutional_investors | quarterly | 28 | 2010-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Pension_Assets_GDP` | oecd_institutional_investors | quarterly | 28 | 2010-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |

### `imf_cpi`

**Total variables:** 2

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `IMF_CPI_Index` | imf_cpi | monthly | 41 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `IMF_CPI_Inflation_YoY` | imf_cpi | monthly | 41 | 2001-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |

### `imf_weo`

**Total variables:** 6

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `IMF_WEO_CA_GDP` | imf_weo | annual | 43 | 1980-12-01T00:00:00 → 2031-12-01T00:00:00 | raw |  | ✓ |
| `IMF_WEO_Debt_GDP` | imf_weo | annual | 43 | 1980-12-01T00:00:00 → 2031-12-01T00:00:00 | raw |  | ✓ |
| `IMF_WEO_GDP_Growth` | imf_weo | annual | 43 | 1980-12-01T00:00:00 → 2031-12-01T00:00:00 | raw |  | ✓ |
| `IMF_WEO_Inflation` | imf_weo | annual | 43 | 1980-12-01T00:00:00 → 2031-12-01T00:00:00 | raw |  | ✓ |
| `IMF_WEO_Population` | imf_weo | annual | 43 | 1980-12-01T00:00:00 → 2031-12-01T00:00:00 | raw |  | ✓ |
| `IMF_WEO_Unemployment` | imf_weo | annual | 43 | 1980-12-01T00:00:00 → 2031-12-01T00:00:00 | raw |  | ✓ |

### `imf_bop`

**Total variables:** 4

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `IMF_BOP_Current_Account` | imf_bop | annual | 43 | 2005-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `IMF_BOP_Direct_Investment_Net` | imf_bop | annual | 42 | 2005-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `IMF_BOP_Financial_Account_Bal` | imf_bop | annual | 43 | 2005-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `IMF_BOP_Portfolio_Investment_Net` | imf_bop | annual | 42 | 2005-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |

### `imf_er`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `IMF_XRate_LCU_per_USD` | imf_er | monthly | 33 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |

### `imf_itg`

**Total variables:** 8

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `IMF_Export_Price_Index` | imf_itg | monthly | 21 | 2000-01-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `IMF_Exports_USD` | imf_itg | monthly | 43 | 2000-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |
| `IMF_Exports_YoY` | imf_itg | monthly | 28 | 2000-01-01T00:00:00 → 2026-02-01T00:00:00 | raw |  |  |
| `IMF_Import_Price_Index` | imf_itg | monthly | 26 | 2000-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |
| `IMF_Imports_USD` | imf_itg | monthly | 41 | 2000-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |
| `IMF_Imports_YoY` | imf_itg | monthly | 27 | 2000-01-01T00:00:00 → 2026-02-01T00:00:00 | raw |  |  |
| `IMF_Trade_Balance_USD` | imf_itg | monthly | 41 | 2000-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |
| `IMF_Trade_Openness_USD` | imf_itg | monthly | 41 | 2000-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |

### `imf_ls`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `IMF_Employment_Index` | imf_ls | monthly | 13 | 2000-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |

### `imf_mfs_ir`

**Total variables:** 4

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `IMF_Discount_Rate` | imf_mfs_ir | monthly | 10 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `IMF_Govt_Bond_Yield` | imf_mfs_ir | monthly | 29 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `IMF_Money_Market_Rate` | imf_mfs_ir | monthly | 26 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `IMF_TBill_Rate` | imf_mfs_ir | monthly | 20 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |

### `imf_fsi`

**Total variables:** 6

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `MS_Bank_Capital_Adequacy` | imf_fsi | quarterly | 41 | 2001-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Bank_Liquidity_Coverage_Ratio` | imf_fsi | quarterly | 31 | 2015-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Bank_Liquidity_Ratio` | imf_fsi | quarterly | 39 | 2001-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Bank_Net_Stable_Funding_Ratio` | imf_fsi | quarterly | 25 | 2018-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_NPL_Net_Provisions_to_Capital_Pct` | imf_fsi | quarterly | 41 | 2001-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_NPL_Ratio` | imf_fsi | quarterly | 41 | 2001-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |

### `macrostructure_derived`

**Total variables:** 5

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `MS_CentralBank_SovDebt_Share` | macrostructure_derived | quarterly | 35 | 1997-12-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `MS_Investor_Base_Fragility` | macrostructure_derived | quarterly | 40 | 2001-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Policy_Backstop` | macrostructure_derived | quarterly | 43 | 2000-01-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `MS_Reserve_Adequacy` | macrostructure_derived | quarterly | 42 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `MS_Swap_Line_Access` | macrostructure_derived | quarterly | 43 | 2000-01-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |

### `qpsd`

**Total variables:** 9

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `MS_Public_Debt_Domestic_Creditors_Pct_GDP` | qpsd | quarterly | 28 | 1995-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Public_Debt_Domestic_Currency_Pct_GDP` | qpsd | quarterly | 29 | 1995-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Public_Debt_External_Creditors_Pct_GDP` | qpsd | quarterly | 29 | 1995-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Public_Debt_Foreign_Currency_Pct_GDP` | qpsd | quarterly | 28 | 1995-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Public_Debt_Foreign_Held_Pct` | qpsd | quarterly | 29 | 1995-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Public_Debt_Local_Currency_Pct` | qpsd | quarterly | 29 | 1995-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Public_Debt_Short_Maturity_Pct` | qpsd | quarterly | 36 | 1995-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Public_Debt_Short_Term_Pct_GDP` | qpsd | quarterly | 36 | 1995-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Public_Debt_Total_Pct_GDP` | qpsd | quarterly | 38 | 1995-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |

### `portfolio_ownership`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `MS_US_Holder_Share_Pct` | portfolio_ownership | annual | 34 | 1997-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |

### `bloomberg`

**Total variables:** 28

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `BBG_Breakeven_10Y` | bloomberg | monthly | 6 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `BBG_CDS_5Y` | bloomberg | monthly | 15 | 2000-10-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `BBG_Debt_GDP_Ratio` | bloomberg | monthly | 1 | 2011-03-01T00:00:00 → 2026-03-01T00:00:00 | raw | ✓ |  |
| `BBG_ECFC_CPI` | bloomberg | monthly | 21 | 2010-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  | ✓ |
| `BBG_ECFC_GDP` | bloomberg | monthly | 29 | 2010-12-01T00:00:00 → 2025-12-01T00:00:00 | raw |  | ✓ |
| `BBG_Govt_Bond_10Y` | bloomberg | monthly | 25 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `BBG_Govt_Bond_2Y` | bloomberg | monthly | 24 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `BBG_Govt_Bond_30Y` | bloomberg | monthly | 17 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `BBG_Govt_Bond_5Y` | bloomberg | monthly | 25 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `BBG_M2_YoY` | bloomberg | monthly | 13 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `BBG_MIPD_5Y` | bloomberg | monthly | 15 | 2000-10-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `BBG_OIS_10Y` | bloomberg | monthly | 17 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `BBG_PMI_Manufacturing` | bloomberg | monthly | 23 | 2023-06-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `BBG_PMI_Services` | bloomberg | monthly | 13 | 2020-10-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `BBG_WIRP_ImpliedRate` | bloomberg | monthly | 25 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `BBG_Yield_Curve_10Y2Y` | bloomberg | monthly | 23 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `BBG_ZSpread_OIS_10Y` | bloomberg | monthly | 16 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `MS_Country_ETF_AUM_USD` | bloomberg | monthly | 34 | 2015-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `MS_Country_ETF_NetFlow_USD` | bloomberg | monthly | 34 | 2015-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `MS_ETF_Creation_Fee_USD` | bloomberg | monthly | 34 | 2026-06-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `MS_ETF_Creation_Unit_Size_Shares` | bloomberg | monthly | 34 | 2026-06-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `MS_ETF_NetCreation_Shares` | bloomberg | monthly | 34 | 2015-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `MS_ETF_NetFlow_to_MarketCap` | bloomberg | monthly | 33 | 2015-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `MS_ETF_Redemption_Fee_USD` | bloomberg | monthly | 33 | 2026-06-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |
| `MS_Index_Weight` | bloomberg | monthly | 33 | 1975-12-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Index_Weight_Change` | bloomberg | monthly | 33 | 1976-12-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Passive_AUM_to_MarketCap` | bloomberg | monthly | 33 | 2015-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `MS_Passive_Flow_Distortion` | bloomberg | monthly | 33 | 1976-12-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |

### `gdelt`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `1MRet` | gdelt | monthly | 34 | 2000-02-01T00:00:00 → 2026-06-01T00:00:00 | raw |  |  |

### `demographics_dip`

**Total variables:** 4

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `DIP_abs` | demographics_dip | monthly | 34 | 1950-12-01T00:00:00 → 2100-12-01T00:00:00 | raw |  |  |
| `DIP_rel` | demographics_dip | monthly | 34 | 1950-12-01T00:00:00 → 2100-12-01T00:00:00 | raw |  |  |
| `DIP_rel_chg_10y` | demographics_dip | monthly | 34 | 1960-12-01T00:00:00 → 2100-12-01T00:00:00 | raw |  |  |
| `DIP_rel_chg_5y` | demographics_dip | monthly | 34 | 1955-12-01T00:00:00 → 2100-12-01T00:00:00 | raw |  |  |

### `imf_mfs_cbs`

**Total variables:** 2

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `MS_CentralBank_BalanceSheet_GDP` | imf_mfs_cbs | monthly | 24 | 1997-12-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `MS_CentralBank_Claims_on_Government_Pct_GDP` | imf_mfs_cbs | monthly | 35 | 1997-12-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |

### `predmkt_signal`

**Total variables:** 14

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `cpi_nowcast_core_next` | predmkt_signal | daily | 1 | 2026-06-10T00:00:00 → 2026-06-10T00:00:00 | raw | ✓ |  |
| `cpi_nowcast_yoy_next` | predmkt_signal | daily | 1 | 2026-06-10T00:00:00 → 2026-06-10T00:00:00 | raw | ✓ |  |
| `fed_cut_count_expectation` | predmkt_signal | daily | 1 | 2026-06-10T00:00:00 → 2026-06-10T00:00:00 | raw | ✓ |  |
| `fed_decision_distribution_next` | predmkt_signal | daily | 1 | 2026-06-10T00:00:00 → 2026-06-10T00:00:00 | raw | ✓ |  |
| `hormuz_disruption_prob_90d` | predmkt_signal | daily | 1 | 2026-06-10T00:00:00 → 2026-06-10T00:00:00 | raw | ✓ |  |
| `oil_shock_prob_30d` | predmkt_signal | daily | 1 | 2026-06-10T00:00:00 → 2026-06-10T00:00:00 | raw | ✓ |  |
| `predmkt_country_opportunity_composite` | predmkt_signal | daily | 9 | 2026-06-10T00:00:00 → 2026-06-10T00:00:00 | raw |  |  |
| `predmkt_country_risk_composite` | predmkt_signal | daily | 9 | 2026-06-10T00:00:00 → 2026-06-10T00:00:00 | raw |  |  |
| `recession_prob_12m` | predmkt_signal | daily | 1 | 2026-06-10T00:00:00 → 2026-06-10T00:00:00 | raw | ✓ |  |
| `regional_conflict_premium_eastern_europe` | predmkt_signal | daily | 1 | 2026-06-10T00:00:00 → 2026-06-10T00:00:00 | raw | ✓ |  |
| `regional_conflict_premium_middle_east` | predmkt_signal | daily | 1 | 2026-06-10T00:00:00 → 2026-06-10T00:00:00 | raw | ✓ |  |
| `regional_conflict_premium_pacific` | predmkt_signal | daily | 1 | 2026-06-10T00:00:00 → 2026-06-10T00:00:00 | raw | ✓ |  |
| `tariff_intensity_by_country` | predmkt_signal | daily | 3 | 2026-06-10T00:00:00 → 2026-06-10T00:00:00 | raw |  |  |
| `unemployment_nowcast_next` | predmkt_signal | daily | 1 | 2026-06-10T00:00:00 → 2026-06-10T00:00:00 | raw | ✓ |  |

## Neo4j Knowledge Graph

**URI:** `bolt://localhost:7687`

### Node labels (7)

#### `:CentralBank` — 31 nodes

Central bank entity linked to a country.

Properties:
- `country_iso3`
- `name`

#### `:Commodity` — 4 nodes

Commodity node used for export exposure edges.

Properties:
- `category`
- `name`

#### `:Country` — 43 nodes

Tracked T2 universe member with metadata. The graph_role property distinguishes sovereign nodes, sovereign proxies, and market-sleeve nodes.

Properties:
- `currency_code`
- `dm_em`
- `embedding_date`
- `embedding_dims`
- `graph_role`
- `iso2`
- `iso3`
- `name`
- `region`
- `state_embedding`
- `t2_name`

#### `:CrisisEvent` — 15 nodes

Historical crisis event linked to affected countries.

Properties:
- `end_date`
- `event_id`
- `name`
- `severity`
- `start_date`
- `type`

#### `:DataSource` — 38 nodes

Upstream source system or dataset.

Properties:
- `api_type`
- `country_count`
- `display_name`
- `first_date`
- `frequency`
- `freshness_days`
- `last_date`
- `name`
- `row_count`
- `source_key`
- `status`
- `url`
- `variable_count`

#### `:Factor` — 676 nodes

ASADO factor/variable node aligned to the unified panel variable catalog.

Properties:
- `name`
- `category`
- `source`
- `latest_return_12m`
- `latest_return_1m`
- `latest_return_date`
- `return_source`
- `sharpe_60m`
- `daily_cum_return_252d`
- `daily_cum_return_30d`
- `daily_max_drawdown_252d`
- `daily_return_date`
- `daily_return_latest`
- `daily_return_source`
- `daily_sharpe_252d`
- `daily_vol_252d`
- `daily_vol_30d`
- `is_optimizer_selected`

#### `:SanctionsProgram` — 6 nodes

Sanctions-related node used for OFAC/SDN association queries.

Properties:
- `active`
- `name`

### Relationship types (9)

| Relationship | Count | From → To | Description |
| --- | --- | --- | --- |
| `[:DATA_AVAILABLE_FROM]` | 1,240 | Country → DataSource | Country coverage edge to an upstream source. |
| `[:EXPORT_EXPOSED_TO]` | 28 | Country → Commodity | Country linked to major commodity exposure. |
| `[:HAS_BANKING_EXPOSURE_TO]` | 584 | Country → Country | Directed bilateral banking claims relationship. |
| `[:HAS_CENTRAL_BANK]` | 31 | Country → CentralBank | Country linked to its central bank node. |
| `[:HAS_CRISIS_HISTORY]` | 378 | Country → CrisisEvent | Country linked to historical crisis events. |
| `[:HAS_FACTOR_EXPOSURE]` | 13,658 | Country → Factor | Latest non-null factor exposure edge per country and variable, built from DuckDB. |
| `[:HOLDS_PORTFOLIO]` | 1,960 | Country → Country |  |
| `[:SUBJECT_TO]` | 31 | Country → SanctionsProgram | Country linked to OFAC/SDN-associated sanctions exposure. This is not a clean sovereign sanctions-target registry. |
| `[:TRADES_WITH]` | 928 | Country → Country | Directed bilateral trade relationship. |

### Indexes (10)

| Name | Type | Label | Properties |
| --- | --- | --- | --- |
| `constraint_121f6647` | RANGE |  | name |
| `constraint_138e31a6` | RANGE |  | name |
| `constraint_40e612f4` | RANGE |  | name |
| `constraint_67f88619` | RANGE |  | name |
| `constraint_90b51235` | RANGE |  | name |
| `constraint_bdf7e5b4` | RANGE |  | t2_name |
| `constraint_e10e73b` | RANGE |  | name |
| `countryStateIndex` | VECTOR |  | state_embedding |
| `index_1b9dcc97` | LOOKUP |  |  |
| `index_460996c0` | LOOKUP |  |  |

## DuckDB Indexes

| Index | Table | Expression |
| --- | --- | --- |
| `idx_bilateral_portfolio_matrix_rep_cp_date` | `bilateral_portfolio_matrix` | [reporter_iso3, counterpart_iso3, date] |
| `idx_bloomberg_factors_ctry_date` | `bloomberg_factors` | [country, date] |
| `idx_bloomberg_factors_var` | `bloomberg_factors` | ['"variable"'] |
| `idx_country_reference_country` | `country_reference` | [country] |
| `idx_country_reference_iso3` | `country_reference` | [iso3] |
| `idx_daily_cal_ctry_date` | `daily_calendar` | [country, date] |
| `idx_demographics_dip_ctry_date` | `demographics_dip` | [country, date] |
| `idx_demographics_dip_var` | `demographics_dip` | ['"variable"'] |
| `idx_event_log_category` | `event_log` | [category] |
| `idx_event_log_date` | `event_log` | [event_date] |
| `idx_event_log_severity` | `event_log` | [severity] |
| `idx_extended_factors_ctry_date` | `extended_factors` | [country, date] |
| `idx_extended_factors_var` | `extended_factors` | ['"variable"'] |
| `idx_external_factors_ctry_date` | `external_factors` | [country, date] |
| `idx_external_factors_var` | `external_factors` | ['"variable"'] |
| `idx_factor_returns_date_factor` | `factor_returns` | [date, factor] |
| `idx_factor_returns_source` | `factor_returns` | ['"source"'] |
| `idx_factor_ret_daily_date_factor` | `factor_returns_daily` | [date, factor] |
| `idx_factor_ret_daily_source` | `factor_returns_daily` | ['"source"'] |
| `idx_factor_top20_membership_date_country` | `factor_top20_membership` | [date, country] |
| `idx_factor_top20_membership_factor` | `factor_top20_membership` | [factor, date] |
| `idx_gdelt_factors_daily_ctry_date` | `gdelt_factors_daily` | [country, date] |
| `idx_gdelt_factors_daily_var` | `gdelt_factors_daily` | ['"variable"'] |
| `idx_gdelt_panel_ctry_date` | `gdelt_panel` | [country, date] |
| `idx_gdelt_panel_var` | `gdelt_panel` | ['"variable"'] |
| `idx_gdelt_raw_iso3_date` | `gdelt_raw_daily` | [country_iso3, date] |
| `idx_imf_factors_ctry_date` | `imf_factors` | [country, date] |
| `idx_imf_factors_var` | `imf_factors` | ['"variable"'] |
| `idx_macrostructure_factors_ctry_date` | `macrostructure_factors` | [country, date] |
| `idx_macrostructure_factors_var` | `macrostructure_factors` | ['"variable"'] |
| `idx_normalized_panel_base_norm` | `normalized_panel` | [base_variable, normalization, date] |
| `idx_normalized_panel_ctry_date` | `normalized_panel` | [country, date] |
| `idx_normalized_panel_var` | `normalized_panel` | ['"variable"'] |
| `idx_predmkt_spill_country` | `predmkt_country_spillover` | [country] |
| `idx_predmkt_daily_market` | `predmkt_daily` | [platform, market_id] |
| `idx_predmkt_daily_snapshot_date` | `predmkt_daily` | [snapshot_date] |
| `idx_predmkt_meta_category` | `predmkt_market_meta` | [asado_category] |
| `idx_predmkt_signal_name_date` | `predmkt_signals_daily` | [signal_name, snapshot_date] |
| `idx_t2_factors_daily_ctry_date` | `t2_factors_daily` | [country, date] |
| `idx_t2_factors_daily_var` | `t2_factors_daily` | ['"variable"'] |
| `idx_t2_levels_daily_ctry_date` | `t2_levels_daily` | [country, date] |
| `idx_t2_levels_daily_var` | `t2_levels_daily` | ['"variable"'] |
| `idx_t2_master_ctry_date` | `t2_master` | [country, date] |
| `idx_t2_master_var` | `t2_master` | ['"variable"'] |
| `idx_t2_raw_ctry_date` | `t2_raw` | [country, date] |
| `idx_t2_raw_var` | `t2_raw` | ['"variable"'] |
| `idx_var_meta_var` | `variable_meta` | ['"variable"'] |
| `idx_wb_commodity_features_code_feature_date` | `wb_commodity_features` | [series_code, feature, date] |
| `idx_wb_commodity_indices_code_date` | `wb_commodity_indices` | [index_code, date] |
| `idx_wb_commodity_prices_code_date` | `wb_commodity_prices` | [commodity_code, date] |
