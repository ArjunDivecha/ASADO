# ASADO Factor Reference

_Generated: 2026-05-16 23:18:36_
_Source of truth: `Data/cache/query_assistant/` — refreshed by `scripts/build_schema_registry.py` on every monthly update._

This document is intended to be read end-to-end by an AI agent (or human) who needs to understand exactly what the ASADO warehouse contains, what each surface means, and how to compose queries against it. Keep prose minimal; lean on tables.

Authoritative companion docs:
- `README.md` — operational entry point (commands, monthly update, MCP setup)
- `CLAUDE.md` — agent-facing project conventions
- `docs/factor_reference.md` (this file) — full DB + variable + graph reference

## At a glance

- **DuckDB tables / views:** 29
- **Distinct variables in `unified_panel`:** 3,048
  - Raw: 594 · `_CS` cross-sectional: 1,216 · `_TS` time-series: 1,238
- **Neo4j node labels:** 0
- **Neo4j relationship types:** 0
- **Country universe:** 34 (T2 names)

## DuckDB Tables

Every analytical surface in `Data/asado.duckdb`. The `t2_master`/`t2_raw` tables are sourced from `T2 Master.xlsx` (separate Bloomberg-driven pipeline); everything else is built by ASADO collectors.

| Table | Type | Rows | Date range | Description |
| --- | --- | --- | --- | --- |
| `bilateral_portfolio_matrix` | BASE TABLE | 56,786 | 1997-12-01 → 2026-02-01 | Historical portfolio ownership matrix combining IMF PIP annual benchmarks and the U.S. TIC supplement. Common instrument_type values include equity_fund_shares, debt_long, debt_short, equity, debt_long_govt, and debt_… |
| `bloomberg_factors` | BASE TABLE | 98,541 | 1975-12-01 → 2026-05-01 | Bloomberg market-implied, macro, and ETF passive-flow data collected via OpusBloomberg. |
| `country_factor_attribution` | VIEW | 2,087,921 | 2000-02-01 → 2026-04-01 | View joining factor_top20_membership ⨝ factor_returns on (date, factor, source). Columns: (date, country, factor, weight, factor_return, contribution, source). contribution = weight × factor_return is the country's mo… |
| `country_reference` | BASE TABLE | 31 | — | Canonical ISO-to-ASADO country mapping surface. Use this to join bilateral tables that store reporter_iso3/counterpart_iso3 onto ASADO factor surfaces that use country names. |
| `daily_calendar` | BASE TABLE | 327,216 | 2000-01-01 → 2026-05-07 |  |
| `extended_factors` | BASE TABLE | 96,658 | 1990-12-01 → 2026-05-01 | Extended country dataset built from additional free sources. |
| `external_factors` | BASE TABLE | 112,677 | 1985-01-01 → 2026-03-01 | Free-source external macro, risk, and structural data. |
| `factor_returns` | BASE TABLE | 277,116 | 2000-02-01 → 2026-04-01 | Monthly net returns of top-20%-of-countries portfolios per factor, sourced from the Econ / T2 Style / GDELT optimizer pipelines. Tidy long format with columns (date, factor, value, source). Factor names retain their _… |
| `factor_returns_daily` | BASE TABLE | 1,293,492 | 2000-01-01 → 2026-05-07 |  |
| `factor_top20_membership` | BASE TABLE | 2,104,980 | 2000-02-01 → 2026-05-01 | Sparse country-level membership in each factor's top-20% bucket per month. Columns: (date, country, factor, weight, source). weight = 1/N within the bucket (equal-weight); rows are present only when the country is in … |
| `feature_panel` | VIEW | 31,584,702 | 1960-01-01 → 2031-12-01 | Query-facing union of unified_panel (raw warehouse) plus normalized_panel for analytics, assistants, and feature discovery. |
| `gdelt_factors_daily` | BASE TABLE | 10,085,794 | 2015-06-24 → 2026-05-08 |  |
| `gdelt_panel` | BASE TABLE | 5,622,818 | 2015-09-01 → 2026-03-01 | Country-level GDELT-derived media, tone, and risk signals. |
| `gdelt_raw_daily` | BASE TABLE | 943,652 | 2015-02-18T00:00:00 → 2026-05-07T00:00:00 |  |
| `imf_factors` | BASE TABLE | 107,538 | 1980-12-01 → 2031-12-01 | IMF datasets normalized into the ASADO tidy panel shape. |
| `macrostructure_factors` | BASE TABLE | 75,407 | 1995-03-01 → 2026-05-01 | Macrostructure panel spanning bank fragility, debt structure, institutional depth, sticky-capital proxies, and transparent derived signals. |
| `normalized_panel` | BASE TABLE | 14,192,623 | 1960-01-01 → 2031-12-01 | Canonical ASADO-generated normalized factors. Contains _CS same-date cross-sectional z-scores and _TS rolling time-series z-scores for eligible raw source variables. |
| `t2_factors_daily` | BASE TABLE | 32,340,392 | 2000-01-01 → 2026-05-07 |  |
| `t2_factors_monthly_from_daily` | VIEW | 1,039,973 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 |  |
| `t2_levels_daily` | BASE TABLE | 13,698,294 | 2000-01-01 → 2026-04-21 |  |
| `t2_master` | BASE TABLE | 1,192,584 | 2000-02-01 → 2026-05-01 | Original T2 monthly factor panel. |
| `t2_raw` | BASE TABLE | 485,582 | 2000-02-01 → 2026-05-01 | Raw T2 factor levels from the authoritative T2 Master workbook. |
| `unified_panel` | VIEW | 17,392,079 | 1960-01-01 → 2031-12-01 | Unified analytic view across all ASADO factor tables. |
| `variable_meta` | BASE TABLE | 640 | — |  |
| `wb_commodity_factor_panel` | BASE TABLE | 9,600,274 | 1960-01-01 → 2026-04-01 | Selected global commodity features broadcast to the ASADO 34-country factor panel as explanatory inputs. |
| `wb_commodity_features` | BASE TABLE | 435,618 | 1960-01-01 → 2026-04-01 | Derived trailing commodity features such as level, MOM, YOY, 3M/12M return, volatility, and z-score, keyed by series_code and feature. |
| `wb_commodity_indices` | BASE TABLE | 12,736 | 1960-01-01 → 2026-04-01 | Canonical World Bank Pink Sheet monthly commodity price indices, 2010=100, keyed by index_code. |
| `wb_commodity_meta` | BASE TABLE | 87 | — |  |
| `wb_commodity_prices` | BASE TABLE | 50,099 | 1960-01-01 → 2026-04-01 | Canonical World Bank Pink Sheet monthly nominal U.S. dollar commodity prices, keyed by commodity_code. |

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
| `12MRet` | t2 | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `3MRet` | t2 | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `6MRet` | t2 | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `9MRet` | t2 | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |

### `t2_raw`

**Total variables:** 53

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `10Yr Bond` | t2_raw | monthly | 33 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `10Yr Bond 12` | t2_raw | monthly | 33 | 2001-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `12-1MTR` | t2_raw | monthly | 34 | 2001-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `120MA` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `120MA Signal` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `12MTR` | t2_raw | monthly | 34 | 2001-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `1MTR` | t2_raw | monthly | 34 | 2000-03-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `20 Day Vol` | t2_raw | monthly | 29 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `360 Day Vol` | t2_raw | monthly | 29 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `3MTR` | t2_raw | monthly | 34 | 2000-05-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Advance Decline` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Agriculture` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Agriculture 12` | t2_raw | monthly | 34 | 2001-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `BEST EPS` | t2_raw | monthly | 29 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Best Cash Flow` | t2_raw | monthly | 27 | 2005-04-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Best Div Yield` | t2_raw | monthly | 29 | 2005-04-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Best PBK` | t2_raw | monthly | 27 | 2005-03-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Best PE` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Best Price Sales` | t2_raw | monthly | 29 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Best ROE` | t2_raw | monthly | 27 | 2005-08-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Bloom Country Risk` | t2_raw | monthly | 34 | 2009-04-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Budget Def` | t2_raw | monthly | 32 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Copper` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Copper 12` | t2_raw | monthly | 34 | 2001-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Currency` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Currency 12` | t2_raw | monthly | 34 | 2001-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Currency Vol` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Current Account` | t2_raw | monthly | 33 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Debt to EV` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Debt to GDP` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `EV to EBITDA` | t2_raw | monthly | 34 | 2005-06-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Earnings Yield` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `GDP` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Gold` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Gold 12` | t2_raw | monthly | 34 | 2001-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Inflation` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `LT Growth` | t2_raw | monthly | 34 | 2005-08-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `MCAP` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `MCAP Adj` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Mcap Weights` | t2_raw | monthly | 34 | 2007-05-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Oil` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Oil 12` | t2_raw | monthly | 34 | 2001-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Operating Margin` | t2_raw | monthly | 29 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `P2P` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `PX_LAST` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Positive PE` | t2_raw | monthly | 29 | 2005-04-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `REER` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `RSI14` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Shiller PE` | t2_raw | monthly | 22 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Tot Return Index` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Trailing EPS` | t2_raw | monthly | 14 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Trailing EPS 36` | t2_raw | monthly | 14 | 2003-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `Trailing PE` | t2_raw | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |

### `epu`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `EPU` | epu | monthly | 21 | 1985-01-01T00:00:00 → 2025-11-01T00:00:00 | raw |  |  |

### `gpr`

**Total variables:** 4

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `GPR` | gpr | monthly | 22 | 1985-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |
| `Global_GPR` | gpr | monthly | 34 | 1985-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |
| `Global_GPR_Act` | gpr | monthly | 34 | 1985-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |
| `Global_GPR_Threat` | gpr | monthly | 34 | 1985-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |

### `bis_credit`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `BIS_Credit_GDP_Gap` | bis_credit | quarterly | 31 | 2000-03-01T00:00:00 → 2025-09-01T00:00:00 | raw |  |  |

### `bis_property`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `BIS_Property_Price` | bis_property | quarterly | 31 | 2000-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |

### `bis_reer`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `BIS_REER` | bis_reer | monthly | 33 | 2000-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |

### `oecd`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `OECD_CLI` | oecd | monthly | 20 | 2000-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |

### `worldbank`

**Total variables:** 26

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `WB_CO2_Per_Capita` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Control_Corruption` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Current_Account_GDP` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Domestic_Credit_GDP` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_External_Debt_GNI` | worldbank | annual | 11 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_FDI_Inflows_GDP` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_FX_Reserves` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Female_LFP` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `WB_Female_Labor_Share` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `WB_GDP_Growth_Real` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Govt_Debt_GDP` | worldbank | annual | 20 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Govt_Effectiveness` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Import_Cover_Months` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Inflation_CPI` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Labor_Force` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `WB_Market_Cap_GDP` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_OldAge_Dependency` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Political_Stability` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Population` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Population_Growth` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Regulatory_Quality` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Renewable_Energy_Share` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2021-12-01T00:00:00 | raw |  |  |
| `WB_Rule_of_Law` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Trade_Openness` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `WB_Unemployment` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `WB_Voice_Accountability` | worldbank | annual | 33 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |

### `bis_policy_rate`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `BIS_Policy_Rate` | bis_policy_rate | daily | 26 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |

### `bis_debt_service`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `BIS_DSR_Private` | bis_debt_service | quarterly | 28 | 2000-03-01T00:00:00 → 2025-09-01T00:00:00 | raw |  |  |

### `ecb_fx`

**Total variables:** 24

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `ECB_FX_AUD_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_BRL_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_CAD_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_CHF_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_CNY_EUR` | ecb_fx | monthly | 2 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_DKK_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_EUR_EUR` | ecb_fx | monthly | 5 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `ECB_FX_GBP_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_HKD_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_IDR_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_INR_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_JPY_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_KRW_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_MXN_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_MYR_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_PHP_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_PLN_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_SEK_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_SGD_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_THB_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_TRY_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_TWD_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2020-10-01T00:00:00 | raw | ✓ |  |
| `ECB_FX_USD_EUR` | ecb_fx | monthly | 3 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `ECB_FX_ZAR_EUR` | ecb_fx | monthly | 1 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw | ✓ |  |

### `fred`

**Total variables:** 6

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `FRED_HY_OAS` | fred | monthly | 34 | 2023-05-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `FRED_USD_Broad_Index` | fred | monthly | 34 | 2006-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `FRED_UST_10Y` | fred | monthly | 34 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `FRED_UST_2Y` | fred | monthly | 34 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `FRED_VIX` | fred | monthly | 34 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `FRED_Yield_Curve_10Y2Y` | fred | monthly | 34 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |

### `ndgain`

**Total variables:** 3

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `NDGAIN_Readiness` | ndgain | annual | 32 | 1995-12-01T00:00:00 → 2023-12-01T00:00:00 | raw |  |  |
| `NDGAIN_Score` | ndgain | annual | 32 | 1995-12-01T00:00:00 → 2023-12-01T00:00:00 | raw |  |  |
| `NDGAIN_Vulnerability` | ndgain | annual | 32 | 1995-12-01T00:00:00 → 2023-12-01T00:00:00 | raw |  |  |

### `ofac`

**Total variables:** 2

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `OFAC_Sanctioned` | ofac | event-driven | 34 | 2026-05-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `OFAC_Sanctions_Count` | ofac | event-driven | 34 | 2026-05-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |

### `undp_hdi`

**Total variables:** 4

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `UNDP_GDI` | undp_hdi | annual | 33 | 1990-12-01T00:00:00 → 2023-12-01T00:00:00 | raw |  |  |
| `UNDP_GII` | undp_hdi | annual | 32 | 1990-12-01T00:00:00 → 2023-12-01T00:00:00 | raw |  |  |
| `UNDP_HDI` | undp_hdi | annual | 33 | 1990-12-01T00:00:00 → 2023-12-01T00:00:00 | raw |  |  |
| `UNDP_IHDI` | undp_hdi | annual | 32 | 2010-12-01T00:00:00 → 2023-12-01T00:00:00 | raw |  |  |

### `ilostat`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `ILO_LFP_Rate` | ilostat | annual | 32 | 2000-12-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |

### `eia`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `EIA_Petroleum_Consumption_TBPD` | eia | annual | 34 | 2000-12-01T00:00:00 → 2019-12-01T00:00:00 | raw |  |  |

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
| `OECD_BCI` | oecd_bci | monthly | 20 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |

### `oecd_cci`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `OECD_CCI` | oecd_cci | monthly | 22 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |

### `oecd_household_dashboard`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `MS_Household_Direct_Equity_Share` | oecd_household_dashboard | annual | 21 | 2010-12-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |

### `oecd_institutional_investors`

**Total variables:** 2

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `MS_Insurance_Assets_GDP` | oecd_institutional_investors | quarterly | 20 | 2010-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Pension_Assets_GDP` | oecd_institutional_investors | quarterly | 20 | 2010-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |

### `imf_cpi`

**Total variables:** 2

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `IMF_CPI_Index` | imf_cpi | monthly | 33 | 2000-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |
| `IMF_CPI_Inflation_YoY` | imf_cpi | monthly | 33 | 2001-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |

### `imf_weo`

**Total variables:** 6

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `IMF_WEO_CA_GDP` | imf_weo | annual | 34 | 1980-12-01T00:00:00 → 2031-12-01T00:00:00 | raw |  | ✓ |
| `IMF_WEO_Debt_GDP` | imf_weo | annual | 34 | 1980-12-01T00:00:00 → 2031-12-01T00:00:00 | raw |  | ✓ |
| `IMF_WEO_GDP_Growth` | imf_weo | annual | 34 | 1980-12-01T00:00:00 → 2031-12-01T00:00:00 | raw |  | ✓ |
| `IMF_WEO_Inflation` | imf_weo | annual | 34 | 1980-12-01T00:00:00 → 2031-12-01T00:00:00 | raw |  | ✓ |
| `IMF_WEO_Population` | imf_weo | annual | 34 | 1980-12-01T00:00:00 → 2031-12-01T00:00:00 | raw |  | ✓ |
| `IMF_WEO_Unemployment` | imf_weo | annual | 34 | 1980-12-01T00:00:00 → 2031-12-01T00:00:00 | raw |  | ✓ |

### `imf_bop`

**Total variables:** 4

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `IMF_BOP_Current_Account` | imf_bop | annual | 34 | 2005-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `IMF_BOP_Direct_Investment_Net` | imf_bop | annual | 33 | 2005-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `IMF_BOP_Financial_Account_Bal` | imf_bop | annual | 34 | 2005-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `IMF_BOP_Portfolio_Investment_Net` | imf_bop | annual | 33 | 2005-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |

### `imf_er`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `IMF_XRate_LCU_per_USD` | imf_er | monthly | 29 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |

### `imf_itg`

**Total variables:** 8

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `IMF_Export_Price_Index` | imf_itg | monthly | 18 | 2000-01-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `IMF_Exports_USD` | imf_itg | monthly | 34 | 2000-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |
| `IMF_Exports_YoY` | imf_itg | monthly | 23 | 2000-01-01T00:00:00 → 2026-01-01T00:00:00 | raw |  |  |
| `IMF_Import_Price_Index` | imf_itg | monthly | 23 | 2000-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |
| `IMF_Imports_USD` | imf_itg | monthly | 33 | 2000-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |
| `IMF_Imports_YoY` | imf_itg | monthly | 22 | 2000-01-01T00:00:00 → 2026-01-01T00:00:00 | raw |  |  |
| `IMF_Trade_Balance_USD` | imf_itg | monthly | 33 | 2000-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |
| `IMF_Trade_Openness_USD` | imf_itg | monthly | 33 | 2000-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |

### `imf_ls`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `IMF_Employment_Index` | imf_ls | monthly | 12 | 2000-01-01T00:00:00 → 2026-02-01T00:00:00 | raw |  |  |

### `imf_mfs_ir`

**Total variables:** 4

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `IMF_Discount_Rate` | imf_mfs_ir | monthly | 10 | 2000-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |
| `IMF_Govt_Bond_Yield` | imf_mfs_ir | monthly | 20 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `IMF_Money_Market_Rate` | imf_mfs_ir | monthly | 21 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `IMF_TBill_Rate` | imf_mfs_ir | monthly | 17 | 2000-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |

### `imf_fsi`

**Total variables:** 6

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `MS_Bank_Capital_Adequacy` | imf_fsi | quarterly | 33 | 2001-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Bank_Liquidity_Coverage_Ratio` | imf_fsi | quarterly | 23 | 2015-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Bank_Liquidity_Ratio` | imf_fsi | quarterly | 31 | 2001-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Bank_Net_Stable_Funding_Ratio` | imf_fsi | quarterly | 17 | 2018-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_NPL_Net_Provisions_to_Capital_Pct` | imf_fsi | quarterly | 33 | 2001-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_NPL_Ratio` | imf_fsi | quarterly | 33 | 2001-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |

### `macrostructure_derived`

**Total variables:** 5

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `MS_CentralBank_SovDebt_Share` | macrostructure_derived | quarterly | 26 | 1997-12-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |
| `MS_Investor_Base_Fragility` | macrostructure_derived | quarterly | 32 | 2001-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Policy_Backstop` | macrostructure_derived | quarterly | 34 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `MS_Reserve_Adequacy` | macrostructure_derived | quarterly | 33 | 2000-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |
| `MS_Swap_Line_Access` | macrostructure_derived | quarterly | 34 | 2000-01-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |

### `qpsd`

**Total variables:** 9

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `MS_Public_Debt_Domestic_Creditors_Pct_GDP` | qpsd | quarterly | 23 | 1995-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Public_Debt_Domestic_Currency_Pct_GDP` | qpsd | quarterly | 24 | 1995-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Public_Debt_External_Creditors_Pct_GDP` | qpsd | quarterly | 24 | 1995-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Public_Debt_Foreign_Currency_Pct_GDP` | qpsd | quarterly | 23 | 1995-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Public_Debt_Foreign_Held_Pct` | qpsd | quarterly | 24 | 1995-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Public_Debt_Local_Currency_Pct` | qpsd | quarterly | 24 | 1995-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Public_Debt_Short_Maturity_Pct` | qpsd | quarterly | 27 | 1995-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Public_Debt_Short_Term_Pct_GDP` | qpsd | quarterly | 27 | 1995-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Public_Debt_Total_Pct_GDP` | qpsd | quarterly | 29 | 1995-03-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |

### `portfolio_ownership`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `MS_US_Holder_Share_Pct` | portfolio_ownership | annual | 34 | 1997-12-01T00:00:00 → 2024-12-01T00:00:00 | raw |  |  |

### `bloomberg`

**Total variables:** 28

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `BBG_Breakeven_10Y` | bloomberg | monthly | 6 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `BBG_CDS_5Y` | bloomberg | monthly | 15 | 2000-10-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `BBG_Debt_GDP_Ratio` | bloomberg | monthly | 1 | 2011-03-01T00:00:00 → 2025-12-01T00:00:00 | raw | ✓ |  |
| `BBG_ECFC_CPI` | bloomberg | monthly | 21 | 2010-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  | ✓ |
| `BBG_ECFC_GDP` | bloomberg | monthly | 29 | 2010-12-01T00:00:00 → 2025-12-01T00:00:00 | raw |  | ✓ |
| `BBG_Govt_Bond_10Y` | bloomberg | monthly | 25 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `BBG_Govt_Bond_2Y` | bloomberg | monthly | 24 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `BBG_Govt_Bond_30Y` | bloomberg | monthly | 17 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `BBG_Govt_Bond_5Y` | bloomberg | monthly | 25 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `BBG_M2_YoY` | bloomberg | monthly | 13 | 2000-01-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |
| `BBG_MIPD_5Y` | bloomberg | monthly | 15 | 2000-10-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `BBG_OIS_10Y` | bloomberg | monthly | 17 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `BBG_PMI_Manufacturing` | bloomberg | monthly | 23 | 2023-05-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `BBG_PMI_Services` | bloomberg | monthly | 13 | 2020-10-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `BBG_WIRP_ImpliedRate` | bloomberg | monthly | 25 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `BBG_Yield_Curve_10Y2Y` | bloomberg | monthly | 23 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `BBG_ZSpread_OIS_10Y` | bloomberg | monthly | 16 | 2000-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `MS_Country_ETF_AUM_USD` | bloomberg | monthly | 34 | 2015-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `MS_Country_ETF_NetFlow_USD` | bloomberg | monthly | 34 | 2015-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `MS_ETF_Creation_Fee_USD` | bloomberg | monthly | 34 | 2026-05-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `MS_ETF_Creation_Unit_Size_Shares` | bloomberg | monthly | 34 | 2026-05-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `MS_ETF_NetCreation_Shares` | bloomberg | monthly | 34 | 2015-02-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `MS_ETF_NetFlow_to_MarketCap` | bloomberg | monthly | 33 | 2015-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `MS_ETF_Redemption_Fee_USD` | bloomberg | monthly | 33 | 2026-05-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |
| `MS_Index_Weight` | bloomberg | monthly | 33 | 1975-12-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Index_Weight_Change` | bloomberg | monthly | 33 | 1976-12-01T00:00:00 → 2025-12-01T00:00:00 | raw |  |  |
| `MS_Passive_AUM_to_MarketCap` | bloomberg | monthly | 33 | 2015-01-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |
| `MS_Passive_Flow_Distortion` | bloomberg | monthly | 33 | 1976-12-01T00:00:00 → 2026-04-01T00:00:00 | raw |  |  |

### `gdelt`

**Total variables:** 1

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `1MRet` | gdelt | monthly | 34 | 2000-02-01T00:00:00 → 2026-05-01T00:00:00 | raw |  |  |

### `imf_mfs_cbs`

**Total variables:** 2

| Variable | Source | Frequency | Countries | Date range | Norm | Sparse | Forecast |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `MS_CentralBank_BalanceSheet_GDP` | imf_mfs_cbs | monthly | 21 | 1997-12-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |
| `MS_CentralBank_Claims_on_Government_Pct_GDP` | imf_mfs_cbs | monthly | 26 | 1997-12-01T00:00:00 → 2026-03-01T00:00:00 | raw |  |  |

### `wb_commodity`

**Total variables:** 371

**Other** — 371 variables
- Samples: `WB_CMDTY_ALUMINUM_LEVEL`, `WB_CMDTY_ALUMINUM_MOM`, `WB_CMDTY_ALUMINUM_RET_12M`, `WB_CMDTY_ALUMINUM_RET_3M`, `WB_CMDTY_ALUMINUM_VOL_12M`, `WB_CMDTY_ALUMINUM_YOY`, `WB_CMDTY_ALUMINUM_Z_36M`, `WB_CMDTY_BARLEY_LEVEL`, `WB_CMDTY_BARLEY_MOM`, `WB_CMDTY_BARLEY_RET_12M`, +361 more
- Frequency: monthly · Country coverage: up to 34 countries

## Neo4j Knowledge Graph

*Neo4j was unreachable when the schema cache was built — run `scripts/build_schema_registry.py` with Neo4j up to populate this section.*

## DuckDB Indexes

| Index | Table | Expression |
| --- | --- | --- |
| `idx_bilateral_portfolio_matrix_rep_cp_date` | `bilateral_portfolio_matrix` | [reporter_iso3, counterpart_iso3, date] |
| `idx_bloomberg_factors_ctry_date` | `bloomberg_factors` | [country, date] |
| `idx_bloomberg_factors_var` | `bloomberg_factors` | ['"variable"'] |
| `idx_country_reference_country` | `country_reference` | [country] |
| `idx_country_reference_iso3` | `country_reference` | [iso3] |
| `idx_daily_cal_ctry_date` | `daily_calendar` | [country, date] |
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
| `idx_t2_factors_daily_ctry_date` | `t2_factors_daily` | [country, date] |
| `idx_t2_factors_daily_var` | `t2_factors_daily` | ['"variable"'] |
| `idx_t2_levels_daily_ctry_date` | `t2_levels_daily` | [country, date] |
| `idx_t2_levels_daily_var` | `t2_levels_daily` | ['"variable"'] |
| `idx_t2_master_ctry_date` | `t2_master` | [country, date] |
| `idx_t2_master_var` | `t2_master` | ['"variable"'] |
| `idx_t2_raw_ctry_date` | `t2_raw` | [country, date] |
| `idx_t2_raw_var` | `t2_raw` | ['"variable"'] |
| `idx_var_meta_var` | `variable_meta` | ['"variable"'] |
| `idx_wb_commodity_factor_panel_ctry_date` | `wb_commodity_factor_panel` | [country, date] |
| `idx_wb_commodity_factor_panel_var` | `wb_commodity_factor_panel` | ['"variable"'] |
| `idx_wb_commodity_features_code_feature_date` | `wb_commodity_features` | [series_code, feature, date] |
| `idx_wb_commodity_indices_code_date` | `wb_commodity_indices` | [index_code, date] |
| `idx_wb_commodity_prices_code_date` | `wb_commodity_prices` | [commodity_code, date] |
