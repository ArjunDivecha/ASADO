# ASADO Data Dictionary

Human-facing reference for what is in the ASADO database, where it lives, and how to access it safely.

This document is meant for analysts, developers, and future agents who need to understand the current live ASADO data model without reverse-engineering the codebase.

## Purpose

ASADO combines:

- T2 factor data (monthly + daily)
- free-source macro / risk / structural data
- IMF datasets
- GDELT country news signals (monthly + daily)
- macrostructure / sticky-capital / central-bank-footprint / policy-backstop signals
- World Bank Pink Sheet commodity prices, indices, and derived features
- Bloomberg sovereign and ETF passive-flow data
- bilateral portfolio ownership
- daily optimizer factor returns (T2 + GDELT)
- prediction-market snapshots and curated event log
- a Neo4j knowledge graph for network relationships

The three most important access surfaces are:

1. DuckDB for time-series and factor analytics (monthly + daily)
2. Neo4j for relationship and network questions
3. MCP tools (`event_window`, `daily_factor_series`, return tools, commodity tools) for event studies and interactive analysis

## Canonical Access Points

### DuckDB

- File: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb`
- Best default view: `feature_panel`
- Raw warehouse view: `unified_panel`
- Canonical normalized table: `normalized_panel`
- Preferred programmatic entrypoint: `scripts.db_bridge.AsadoDB.query_panel()`

### Neo4j

- URI: `bolt://localhost:7687`
- Preferred programmatic entrypoint: `scripts.db_bridge.AsadoDB.query_graph()`
- Used for trade, banking, portfolio, crisis-history, central-bank, and factor-node relationship questions

### Python Bridge

- Module: [scripts/db_bridge.py](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/scripts/db_bridge.py)
- Main class: `AsadoDB`

Example:

```python
from scripts.db_bridge import AsadoDB

with AsadoDB() as db:
    df = db.query_panel(
        """
        SELECT country, value, date
        FROM unified_panel
        WHERE variable = 'BIS_Credit_GDP_Gap'
        ORDER BY date DESC
        LIMIT 10
        """
    )
```

### Natural-Language Query Layer

- Script: [scripts/query_assistant.py](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/scripts/query_assistant.py)
- Schema cache directory: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/cache/query_assistant`

Example:

```bash
./venv/bin/python scripts/query_assistant.py \
  "Which countries have rising GDELT risk but low ETF passive distortion?"
```

## Machine-Readable Metadata

If you want the machine-readable source of truth, start here:

These files are generated locally under `Data/cache/query_assistant` by `scripts/build_schema_registry.py`. They are operational metadata, not hand-maintained documentation.

- [access_guide.json](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/cache/query_assistant/access_guide.json)
- [manifest.json](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/cache/query_assistant/manifest.json)
- [duckdb_schema.json](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/cache/query_assistant/duckdb_schema.json)
- [neo4j_schema.json](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/cache/query_assistant/neo4j_schema.json)
- [variable_catalog.json](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/cache/query_assistant/variable_catalog.json)

Panel-specific catalogs:

- [external_variable_catalog.csv](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/processed/external_variable_catalog.csv)
- [extended_variable_catalog.csv](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/processed/extended_variable_catalog.csv)
- [imf_variable_catalog.csv](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/processed/imf_variable_catalog.csv)
- [macrostructure_variable_catalog.csv](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/processed/macrostructure_variable_catalog.csv)
- [macrostructure_formula_catalog.json](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/processed/macrostructure_formula_catalog.json)
- [bloomberg_variable_catalog.csv](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/processed/bloomberg_variable_catalog.csv)
- [wb_commodity_variable_catalog.csv](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/processed/wb_commodity_variable_catalog.csv)
- [wb_commodity_manifest.json](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/processed/wb_commodity_manifest.json)

Refresh the schema cache with:

```bash
./venv/bin/python scripts/build_schema_registry.py
```

If you cloned the repo fresh and those cache files are missing, run that command first.

## Core DuckDB Model

### Standard Factor-Panel Shape

Most ASADO factor tables use the same tidy layout:

- `date`
- `country`
- `value`
- `variable`
- `source` (present in most non-T2 tables and in `unified_panel`)

This is the shape used by:

- `external_factors`
- `extended_factors`
- `gdelt_panel`
- `imf_factors`
- `macrostructure_factors`
- `bloomberg_factors`
- `wb_commodity_factor_panel`
- `unified_panel`
- `normalized_panel`
- `feature_panel`
- `t2_factors_daily`
- `t2_levels_daily`
- `gdelt_factors_daily`

Note: `factor_returns_daily` uses `(date, factor, value, source)` — same shape as the monthly `factor_returns` table.

### DuckDB Tables And Views

#### Monthly Tables

| Table / View | Rows | Date Range | Primary Use |
| --- | ---: | --- | --- |
| `t2_master` | 1,192,584 | 2000-02-01 → 2026-05-01 | Canonical normalized T2 panel |
| `t2_raw` | 485,582 | 2000-02-01 → 2026-05-01 | Raw T2 factor levels from the workbook |
| `country_reference` | generated monthly | n/a | Canonical ISO3 -> ASADO country mapping surface for bilateral joins |
| `external_factors` | 112,677 | 1985-01-01 → 2026-03-01 | Program 1 free-source macro / risk / structural panel |
| `extended_factors` | 96,658 | 1990-12-01 → 2026-05-01 | Program 2 extended free-source panel |
| `gdelt_panel` | 5,622,818 | 2015-09-01 → 2026-03-01 | Country-level media / tone / risk signals from GDELT |
| `imf_factors` | 107,538 | 1980-12-01 → 2031-12-01 | IMF CPI, WEO, BOP, FX, labor, trade, and FSI-derived series |
| `macrostructure_factors` | 75,407 | 1995-03-01 → 2026-05-01 | Bank fragility, debt structure, ownership, sticky-capital, central-bank footprint, policy-backstop |
| `bloomberg_factors` | 98,541 | 1975-12-01 → 2026-05-01 | Bloomberg sovereign rates/credit/macro plus ETF passive-flow layer |
| `wb_commodity_factor_panel` | 9,600,274 | 1960-01-01 → 2026-04-01 | Selected World Bank commodity variables broadcast to ASADO countries |
| `normalized_panel` | 14,192,623 | 1960-01-01 → 2031-12-01 | Canonical `_CS` and `_TS` normalized feature layer |
| `feature_panel` | 31,584,702 | 1960-01-01 → 2031-12-01 | Query-facing union of raw + normalized factor rows |
| `bilateral_portfolio_matrix` | 56,786 | 1997-12-01 → 2026-02-01 | Reporter-counterparty portfolio ownership matrix |
| `factor_returns` | 277,116 | 2000-02-01 → 2026-04-01 | Monthly optimizer factor portfolio returns |
| `factor_top20_membership` | 2,104,980 | 2000-02-01 → 2026-05-01 | Sparse country membership in each factor's top-20 bucket |
| `unified_panel` | 17,392,079 | 1960-01-01 → 2031-12-01 | Primary raw cross-source analytical view |

#### World Bank Commodity Tables (added 2026-05-16)

| Table | Rows | Date Range | Primary Use |
| --- | ---: | --- | --- |
| `wb_commodity_prices` | 50,099 | 1960-01-01 → 2026-04-01 | Canonical World Bank Pink Sheet monthly nominal USD commodity prices |
| `wb_commodity_indices` | 12,736 | 1960-01-01 → 2026-04-01 | World Bank commodity price indices, 2010=100 |
| `wb_commodity_features` | 435,618 | 1960-01-01 → 2026-04-01 | Commodity-axis trailing features: `level`, `mom_pct`, `yoy_pct`, `ret_3m_pct`, `ret_12m_pct`, `vol_12m`, `z_36m` |
| `wb_commodity_meta` | 87 | n/a | Price/index metadata, category, unit, and projection flag |

The commodity-axis tables are not country-keyed. `wb_commodity_factor_panel` is the controlled country-panel projection. These variables have `source='wb_commodity'` and are global explanatory context; do not use them as returns or optimizer outputs.

#### Daily Tables (added 2026-05-08)

| Table / View | Rows | Date Range | Primary Use |
| --- | ---: | --- | --- |
| `t2_factors_daily` | 32,340,392 | 2000-01-01 → 2026-05-07 | 109 normalized _CS/_TS daily factors, 34 countries |
| `t2_levels_daily` | 13,698,294 | 2000-01-01 → 2026-04-21 | 47 raw factor levels (PX_LAST, MCAP, RSI14, REER, etc.) |
| `gdelt_factors_daily` | 10,085,794 | 2015-06-24 → 2026-05-08 | 75 normalized GDELT daily factors, 34 countries |
| `gdelt_raw_daily` | 943,652 | 2015-02-18 → 2026-05-07 | 249-country raw GDELT (off-universe entity bridge) |
| `factor_returns_daily` | 1,293,492 | 2000-01-01 → 2026-05-07 | 178 optimizer factor returns (T2 + GDELT) |
| `variable_meta` | 654 | n/a | Variable metadata: frequency, category, optimizer-selected flag, commodity freshness |
| `daily_calendar` | 327,216 | 2000-01-01 → 2026-05-07 | Per-country trading day calendar |
| `t2_factors_monthly_from_daily` (view) | — | — | Last-trading-day-of-month snapshot for validation |

#### Prediction-Market And Event Tables

| Table | Rows | Date Range | Primary Use |
| --- | ---: | --- | --- |
| `predmkt_daily` | 30 | 2026-05-17 | Daily implied probabilities, book fields, liquidity, stale/resolution flags |
| `predmkt_market_meta` | 15 | n/a | Curated market metadata and ASADO category mapping |
| `predmkt_outcome_meta` | 30 | n/a | Outcome labels and scalar thresholds |
| `predmkt_country_spillover` | 49 | n/a | Curated spillover bridge to 18 T2 countries |
| `predmkt_resolutions` | 0 | n/a | Resolution archive, empty until tracked markets resolve |
| `predmkt_signals_daily` | 42 | 2026-05-17 | 14 derived country/global prediction-market signals |
| `event_log` | 146 | 1997-07-02 → 2026-05-01 | Curated dated event registry for event-window workflows |

### Which Surface Should I Use?

- Use `feature_panel` for most country-factor questions.
- Use `unified_panel` when you explicitly want the raw warehouse with no ASADO-generated normalized variants.
- Use `normalized_panel` when you need explicit normalization metadata such as `base_variable`, `normalization`, or rolling-window settings.
- Use `country_reference` whenever you need to map `reporter_iso3` or `counterpart_iso3` from bilateral tables onto ASADO country names.
- Use `gdelt_panel` when the question is specifically about GDELT-only features or partial-month GDELT labels.
- Use `bloomberg_factors` when you want only Bloomberg-native or Bloomberg-derived fields.
- Use `wb_commodity_features` when you want commodity-axis history without a country broadcast.
- Use `wb_commodity_factor_panel` or `source='wb_commodity'` in `feature_panel` when you want selected commodity context aligned to ASADO countries.
- Use `macrostructure_factors` when you want the ownership / fragility / central-bank-footprint / policy-backstop layer in isolation.
- Use `bilateral_portfolio_matrix` for reporter-counterparty portfolio ownership, not `unified_panel`.
- Use `t2_factors_daily` / `gdelt_factors_daily` for daily-frequency analysis, event windows, or intramonth behavior.
- Use `t2_levels_daily` when you need raw (un-normalized) daily price/fundamental levels.
- Use `factor_returns_daily` for daily optimizer portfolio returns (strategy P&L analysis).
- Use `variable_meta` to discover which variables are optimizer-selected, their category, and monthly equivalents.
- Use `daily_calendar` to identify trading vs. non-trading days per country (handles Saudi Sun-Thu, China holidays, etc.)
- Use `predmkt_*` for market-implied probabilities and curated off-universe spillovers.
- Use `event_log` / `events_in_window` for dated event lookup before running `event_window`.
- Use the MCP `event_window` tool for quick daily event studies instead of writing SQL from scratch.

## Special Table: `bilateral_portfolio_matrix`

This table is not in the standard factor-panel shape.

Columns:

- `date`
- `reporter_iso3`
- `counterpart_iso3`
- `instrument_type`
- `amount_usd`
- `share_of_reporter_portfolio_pct`
- `share_of_counterpart_inbound_pct`
- `source`
- `frequency`
- `is_official_sector`

Exact categorical values currently present:

- `instrument_type`: `debt_long`, `debt_long_corp`, `debt_long_govt`, `debt_short`, `equity`, `equity_fund_shares`
- `source`: `imf_pip`, `us_tic`
- `frequency`: `annual`, `monthly`

Use this table for questions like:

- "Which countries hold the most Brazilian long-term debt?"
- "How large is U.S. exposure to Mexican equities?"
- "Who are the top holders of South African debt_long_govt?"

To map `reporter_iso3` / `counterpart_iso3` into ASADO factor-country names, join through `country_reference`.

## Source Families In `unified_panel`

Representative `source` values currently present in `unified_panel` include:

- `bis_credit`
- `bis_debt_service`
- `bis_policy_rate`
- `bis_property`
- `bis_reer`
- `bloomberg`
- `ecb_fx`
- `eia`
- `epu`
- `faostat`
- `fred`
- `gdelt`
- `gpr`
- `ilostat`
- `imf_bop`
- `imf_cpi`
- `imf_er`
- `imf_fsi`
- `imf_itg`
- `imf_ls`
- `imf_mfs_cbs`
- `macrostructure_derived`

If you want the exact live set, inspect `duckdb_schema.json` or run:

```sql
SELECT DISTINCT source
FROM unified_panel
ORDER BY source;
```

## Variable Discovery

### Best Master Variable Dictionary

The best variable-level reference is:

- [variable_catalog.json](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/cache/query_assistant/variable_catalog.json)

For each variable it includes:

- `source`
- `row_count`
- `country_count`
- `first_date`
- `last_date`
- `frequency`
- `freshness_days`
- `is_stale`
- `is_sparse`
- `is_forecast`
- `normalization`
- `series_scope`

### Example Variables

| Variable | Source | Meaning |
| --- | --- | --- |
| `BIS_Credit_GDP_Gap` | `bis_credit` | BIS credit-to-GDP gap signal |
| `country_news_risk_CS` | `gdelt` | GDELT country news risk, cross-sectional normalized |
| `MS_CentralBank_BalanceSheet_GDP` | `imf_mfs_cbs` | Central-bank total assets scaled by same-year nominal GDP |
| `MS_CentralBank_SovDebt_Share` | `macrostructure_derived` | Proxy for the central-bank share of sovereign debt outstanding |
| `MS_Policy_Backstop` | `macrostructure_derived` | Derived policy-backstop composite |
| `BBG_CDS_5Y` | `bloomberg` | Bloomberg sovereign 5Y CDS level |
| `MS_Passive_Flow_Distortion` | `bloomberg` | Derived ETF passive/mechanical-flow distortion signal |

### Naming Conventions

Common patterns:

- `BBG_*` = Bloomberg variables
- `IMF_*` = IMF variables
- `WB_*` = World Bank variables
- `WB_CMDTY_*` = World Bank Pink Sheet commodity variables projected into ASADO's factor-panel shape
- `MS_*` = macrostructure or market-structure variables
- `_CS` = cross-sectional normalized form
- `_TS` = time-series normalized form
- no suffix = usually raw level

### Canonical ASADO-Generated Normalization Layer

For eligible raw variables, ASADO now creates:

- `_CS`: same-date cross-sectional z-score across countries
- `_TS`: rolling within-country z-score using frequency-aware observation windows

The generated rows live in `normalized_panel`, while `feature_panel` exposes both raw and normalized rows together for assistant/query use.

Current normalization boundary:

- raw IMF MFS central-bank footprint variables such as `MS_CentralBank_BalanceSheet_GDP` and `MS_CentralBank_Claims_on_Government_Pct_GDP` do receive `_CS` and `_TS` variants
- `macrostructure_derived` rows such as `MS_CentralBank_SovDebt_Share`, `MS_Reserve_Adequacy`, `MS_Swap_Line_Access`, and `MS_Policy_Backstop` currently remain raw-only unless the normalization policy is widened in code

## GDELT Convention

GDELT is a special case.

The canonical upstream source is:

- `/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 GDELT/GDELT_Factors_MasterCSV.csv`

ASADO does not run a GDELT collector during `monthly_update.py`. Instead:

- the external GDELT file is refreshed outside ASADO
- `setup_duckdb.py` ingests it during the DuckDB rebuild

If you only updated the external GDELT file, the right command is:

```bash
./venv/bin/python scripts/monthly_update.py --db-only
```

### Partial-Month Label Rule

ASADO currently supports the convention where the current partial month can be labeled with the first day of the next month.

Interpretation:

- a GDELT row labeled with the first day of the next month may be the current partial-month observed label
- it should not be treated as a forecast just because it is later than `CURRENT_DATE`
- this rule applies to GDELT-specific latest/current questions, not to all future-dated rows in the warehouse

## Bloomberg ETF Passive Layer

The Bloomberg panel now includes a market-structure / ETF-passive family:

- `MS_Country_ETF_AUM_USD`
- `MS_Country_ETF_NetFlow_USD`
- `MS_ETF_Creation_Fee_USD`
- `MS_ETF_Creation_Unit_Size_Shares`
- `MS_ETF_NetCreation_Shares`
- `MS_ETF_NetFlow_to_MarketCap`
- `MS_ETF_Redemption_Fee_USD`
- `MS_Index_Weight`
- `MS_Index_Weight_Change`
- `MS_Passive_AUM_to_MarketCap`
- `MS_Passive_Flow_Distortion`

These live in `bloomberg_factors` and also appear in `unified_panel`.

## World Bank Commodity Intelligence

ASADO's commodity layer uses the official World Bank Commodity Markets Pink Sheet workbook as the canonical source. The Kaggle mirror is not used as an upstream dependency.

Collector:

```bash
./venv/bin/python scripts/collect_wb_commodity_prices.py --force
./venv/bin/python scripts/collect_wb_commodity_prices.py --check
```

Monthly updater:

```bash
./venv/bin/python scripts/monthly_update.py --commodity-only
./venv/bin/python scripts/monthly_update.py --skip-wb-commodity
```

Current source label: `Updated on May 04, 2026`. Latest observation in the live DB: `2026-04-01`.

Canonical table grain:

- `wb_commodity_prices`: `(date, commodity_code)` with nominal USD price and unit.
- `wb_commodity_indices`: `(date, index_code)` with 2010=100 nominal index level.
- `wb_commodity_features`: `(date, series_code, feature)` for derived trailing features.
- `wb_commodity_factor_panel`: `(date, country, variable)` after selected global commodity series are broadcast to the 34 ASADO countries.

Selected broadcast variable examples:

- `WB_CMDTY_CRUDE_BRENT_LEVEL`
- `WB_CMDTY_CRUDE_BRENT_RET_12M`
- `WB_CMDTY_COPPER_YOY`
- `WB_CMDTY_IENERGY_LEVEL`
- `WB_CMDTY_IFERTILIZERS_Z_36M`

Commodity variables are explanatory context. For questions like "who benefited from higher oil?" or "did copper help Chile?", first inspect the commodity series, then anchor the answer on country/factor returns.

## Macrostructure Central-Bank Footprint Layer

The macrostructure panel now includes a transparent Phase 3 central-bank footprint block:

- `MS_CentralBank_BalanceSheet_GDP`
  Central-bank total assets from IMF `MFS_CBS` scaled by same-year WEO nominal GDP in USD.
- `MS_CentralBank_Claims_on_Government_Pct_GDP`
  Central-bank claims on central government from IMF `MFS_CBS` scaled by same-year WEO nominal GDP in USD.
- `MS_CentralBank_SovDebt_Share`
  Transparent proxy for the central-bank share of sovereign debt. Numerator is `MS_CentralBank_Claims_on_Government_Pct_GDP`; denominator prefers `MS_Public_Debt_Total_Pct_GDP` from QPSD and falls back to annual WEO debt/GDP when QPSD is missing.

Current live macrostructure table: 75,407 rows, 26 variables, 34 countries, 1995-03-01 through 2026-05-01.

## Neo4j Graph Model

### Node Labels

Current labels:

- `Country`
- `Factor`
- `CentralBank`
- `DataSource`
- `CrisisEvent`
- `SanctionsProgram`
- `Commodity`

### Relationship Types

Current relationship types:

- `DATA_AVAILABLE_FROM`
- `EXPORT_EXPOSED_TO`
- `HAS_BANKING_EXPOSURE_TO`
- `HAS_CENTRAL_BANK`
- `HAS_CRISIS_HISTORY`
- `HAS_FACTOR_EXPOSURE`
- `HOLDS_PORTFOLIO`
- `SUBJECT_TO`
- `TRADES_WITH`

### Factor Node Daily Properties (added 2026-05-08)

178 optimizer factors have daily returns in DuckDB. The Neo4j graph stores daily performance properties on the Factor nodes that are created from the current graph build:

- `daily_return_latest`, `daily_return_date`
- `daily_vol_30d`, `daily_vol_252d` (annualized)
- `daily_sharpe_252d` (annualized)
- `daily_max_drawdown_252d`
- `daily_cum_return_30d`, `daily_cum_return_252d`
- `daily_return_source` (`t2_optimizer_daily` or `gdelt_optimizer_daily`)
- `is_optimizer_selected` (`true` for the 8 live strategy factors)

These are refreshed on every `setup_neo4j.py` rebuild (automatic in monthly_update.py).

### When Neo4j Is Better Than DuckDB

Prefer Neo4j for:

- trade-network questions
- banking-exposure network questions
- portfolio-ownership graph traversals
- crisis-history lookups
- central-bank relationship queries
- factor-node relationship exploration
- **factor performance ranking** (daily Sharpe, vol, drawdown via `daily_*` properties)
- **"which factors connected to country X have the best daily Sharpe?"**

Prefer DuckDB for:

- ranking countries by factor values
- time-series history
- latest cross-sectional snapshots
- cross-source factor joins and filters
- daily event-window analysis (use MCP `event_window` tool)

## Concrete Query Examples

### DuckDB SQL

Latest macrostructure snapshot:

```sql
SELECT country, value, date
FROM unified_panel
WHERE variable = 'MS_Policy_Backstop'
ORDER BY date DESC, country
LIMIT 50;
```

Latest GDELT-only risk values:

```sql
SELECT country, value, date
FROM gdelt_panel
WHERE variable = 'country_news_risk_CS'
  AND date = (SELECT MAX(date) FROM gdelt_panel WHERE variable = 'country_news_risk_CS')
ORDER BY value DESC;
```

### Neo4j Cypher

Top bilateral trade links:

```cypher
MATCH (c:Country)-[r:TRADES_WITH]->(p:Country)
RETURN c.t2_name AS country, p.t2_name AS partner, r.total_trade_usd
ORDER BY r.total_trade_usd DESC
LIMIT 25
```

### Python Bridge

```python
from scripts.db_bridge import AsadoDB

with AsadoDB() as db:
    snapshot = db.factor_snapshot("MS_Passive_Flow_Distortion")
```

### Query Assistant

```bash
./venv/bin/python scripts/query_assistant.py \
  "Which countries have rising GDELT risk but low ETF passive distortion?"
```

## Refresh And Maintenance

Refresh schema metadata:

```bash
./venv/bin/python scripts/build_schema_registry.py
```

Rebuild databases only:

```bash
./venv/bin/python scripts/monthly_update.py --db-only
```

Run the full monthly pipeline:

```bash
./venv/bin/python scripts/monthly_update.py
```

## Daily Extension (added 2026-05-08)

The daily extension adds ~58M rows of daily-frequency data to the same `asado.duckdb` file. Built by `scripts/build_daily_panels.py`.

### Key Concepts

- **Normalized vs raw**: `t2_factors_daily` contains cross-sectional (`_CS`) and time-series (`_TS`) z-scored factors. `t2_levels_daily` contains the raw underlying values (prices, RSI14 level, REER level, etc.)
- **Optimizer-selected factors**: 8 key factors that drive the strategy portfolio — queryable via `variable_meta.is_optimizer_selected`
- **Factor returns**: `factor_returns_daily` contains daily portfolio returns for 178 factors, sourced from the T2 and GDELT optimizers. `source` is `t2_optimizer_daily` or `gdelt_optimizer_daily`.
- **Trading calendar**: Not all countries trade on the same days (Saudi Arabia is Sun-Thu, China has Golden Week, etc.). `daily_calendar` provides per-country trading-day flags.
- **Off-universe GDELT**: `gdelt_raw_daily` covers 249 countries (including Iran, North Korea, etc.) — useful as an entity bridge beyond the 34-country T2 universe.

### Example Daily Queries

Event study — Turkey 2018 lira crisis:

```sql
SELECT date, variable, value
FROM t2_factors_daily
WHERE country = 'Turkey'
  AND date BETWEEN DATE '2018-08-08' AND DATE '2018-08-18'
  AND variable IN (SELECT variable FROM variable_meta WHERE is_optimizer_selected)
ORDER BY variable, date;
```

Factor return performance:

```sql
SELECT date, factor, value
FROM factor_returns_daily
WHERE factor = 'RSI14_CS'
  AND source = 't2_optimizer_daily'
  AND date >= DATE '2026-01-01'
ORDER BY date;
```

GDELT off-universe lookup (Iran):

```sql
SELECT date, tone_mean, country_news_risk, country_news_sentiment
FROM gdelt_raw_daily
WHERE country_iso3 = 'IRN'
ORDER BY date DESC
LIMIT 20;
```

### MCP Tools for Daily Data

| Tool | Use Case |
|------|----------|
| `event_window(country, date, days_before, days_after)` | Quick event studies — returns T2 factors, GDELT, factor returns, calendar, and return summary |
| `daily_factor_series(country, variables, start_date, end_date, source)` | General daily time-series extraction from any daily table |
| `country_returns(...)` | Deterministic T2 country returns, monthly or daily |
| `factor_return_series(...)` | Monthly/daily optimizer factor portfolio returns |
| `country_factor_attribution(...)` | Monthly top-20 bucket contribution by country/factor |
| `return_leaders(...)` | Country or factor return leaderboards |
| `commodity_price_series(commodity, feature, ...)` | World Bank Pink Sheet commodity/index series and derived features |
| `predmkt_snapshot(...)`, `country_signal_now(...)`, `event_market_set(...)` | Prediction-market snapshot, spillover, and search tools |

### Rebuild

```bash
python scripts/build_daily_panels.py --rebuild --no-backup   # full rebuild (~105s)
python scripts/build_daily_panels.py --check                 # health check
```

Full implementation details: [`docs/DAILY_EXTENSION_STATUS.md`](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/docs/DAILY_EXTENSION_STATUS.md)

## Returns Source Of Truth

Returns are ASADO's outcome layer. Performance, event, and explanation questions should anchor on the return surfaces below by default.

### Country Returns (one canonical source — T2, 34 countries)

| Frequency | Table | Filter | Horizons |
|---|---|---|---|
| Monthly | `feature_panel` / `unified_panel` | `source = 't2'` | `1MRet`, `3MRet`, `6MRet`, `9MRet`, `12MRet` |
| Daily | `t2_factors_daily` | — | `1DRet`, `5DRet`, `20DRet`, `60DRet`, `120DRet` |

The `1MRet` rows under `source = 'gdelt'` in `feature_panel` and the `1DRet` rows in `gdelt_factors_daily` are **bit-exact aliases** of the T2 country returns. They are copied into the GDELT panel as the dependent variable for the GDELT optimizer pipeline. **Do not treat them as a second country return source.** (Verified 2026-05-12: 135,014/135,014 daily rows identical to T2; monthly identical to 6 decimal places.)

### Factor Portfolio Returns

| Frequency | Table | Sources |
|---|---|---|
| Monthly | `factor_returns` | `econ_optimizer`, `t2_optimizer`, `gdelt_optimizer` |
| Daily | `factor_returns_daily` | `t2_optimizer_daily`, `gdelt_optimizer_daily` |

These are top-20%-of-countries portfolio returns from the ASADO optimizer pipelines — **factor portfolio returns, not raw factor levels.**

### Country-Factor Attribution

- `factor_top20_membership`: sparse country membership in each factor's top-20% bucket (`weight = 1/N`).
- `country_factor_attribution`: `factor_top20_membership ⨝ factor_returns` on `(date, factor, source)` giving `contribution = weight × factor_return`. This is top-20% bucket attribution, not a full portfolio decomposition.

### Cycle Guardrail

`factor_returns`, `factor_returns_daily`, `factor_top20_membership`, and `country_factor_attribution` must **never** be unioned into `feature_panel` or `unified_panel`. Those views are the explanatory/input surfaces the optimizer pipelines consume; mixing optimizer outputs back in creates a modeling cycle.

Regression: `scripts/qa/validate_returns_first.py` enforces this guardrail and checks every surface above.

### MCP Tools

Use the deterministic return tools before writing ad hoc SQL: `country_returns`, `factor_return_series`, `country_factor_attribution`, `return_leaders`; `event_window` returns a `return_summary` block.

## Guardrails

- Prefer read-only access.
- Use `unified_panel` by default for monthly questions unless a panel-specific table is clearly more appropriate.
- Use daily tables (`t2_factors_daily`, `gdelt_factors_daily`) for intramonth or event-study questions.
- For performance, event, winner/loser, attribution, or "what happened" questions, anchor on a return surface from "Returns Source Of Truth" above.
- Use `gdelt_panel` for GDELT-specific latest/current questions if the date-label convention matters.
- Do not assume `bilateral_portfolio_matrix` has `country`, `variable`, and `value`; it does not.
- For human discovery, start with this file.
- For agent discovery, start with [access_guide.json](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/cache/query_assistant/access_guide.json) and [returns_catalog.json](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/cache/query_assistant/returns_catalog.json).
