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
- Bloomberg sovereign and ETF passive-flow data
- bilateral portfolio ownership
- daily optimizer factor returns (T2 + GDELT)
- a Neo4j knowledge graph for network relationships

The three most important access surfaces are:

1. DuckDB for time-series and factor analytics (monthly + daily)
2. Neo4j for relationship and network questions
3. MCP tools (`event_window`, `daily_factor_series`) for daily event studies

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
| `t2_master` | 1,188,810 | 2000-02-01 → 2026-04-01 | Canonical normalized T2 panel |
| `t2_raw` | 474,636 | 2000-02-01 → 2026-04-01 | Raw T2 factor levels from the workbook |
| `country_reference` | generated monthly | n/a | Canonical ISO3 -> ASADO country mapping surface for bilateral joins |
| `external_factors` | 112,633 | 1985-01-01 → 2026-03-01 | Program 1 free-source macro / risk / structural panel |
| `extended_factors` | 96,604 | 1990-12-01 → 2026-04-01 | Program 2 extended free-source panel |
| `gdelt_panel` | 407,864 | 2015-09-01 → 2026-05-01 | Country-level media / tone / risk signals from GDELT |
| `imf_factors` | 107,298 | 1980-12-01 → 2031-12-01 | IMF CPI, WEO, BOP, FX, labor, trade, and FSI-derived series |
| `macrostructure_factors` | 75,120 | 1995-03-01 → 2026-04-01 | Bank fragility, debt structure, ownership, sticky-capital, central-bank footprint, policy-backstop |
| `bloomberg_factors` | 98,129 | 1975-12-01 → 2026-04-01 | Bloomberg sovereign rates/credit/macro plus ETF passive-flow layer |
| `normalized_panel` | 778,984 | 1990-12-01 → 2026-04-01 | Canonical `_CS` and `_TS` normalized feature layer |
| `feature_panel` | 3,340,078 | 1975-12-01 → 2031-12-01 | Query-facing union of raw + normalized factor rows |
| `bilateral_portfolio_matrix` | 56,786 | 1997-12-01 → 2026-02-01 | Reporter-counterparty portfolio ownership matrix |
| `unified_panel` | 2,561,094 | 1975-12-01 → 2031-12-01 | Primary cross-source analytical view |

#### Daily Tables (added 2026-05-08)

| Table / View | Rows | Date Range | Primary Use |
| --- | ---: | --- | --- |
| `t2_factors_daily` | 32,340,392 | 2000-01-01 → 2026-05-07 | 109 normalized _CS/_TS daily factors, 34 countries |
| `t2_levels_daily` | 13,698,294 | 2000-01-01 → 2026-04-21 | 47 raw factor levels (PX_LAST, MCAP, RSI14, REER, etc.) |
| `gdelt_factors_daily` | 10,085,794 | 2015-06-24 → 2026-05-08 | 75 normalized GDELT daily factors, 34 countries |
| `gdelt_raw_daily` | 955,473 | 2015-02-18 → 2026-04-19 | 249-country raw GDELT (off-universe entity bridge) |
| `factor_returns_daily` | 1,085,412 | 2000-01-01 → 2026-05-07 | 157 optimizer factor returns (T2 + GDELT) |
| `variable_meta` | 269 | n/a | Variable metadata: frequency, category, optimizer-selected flag |
| `daily_calendar` | 327,216 | 2000-01-01 → 2026-05-07 | Per-country trading day calendar |
| `t2_factors_monthly_from_daily` (view) | — | — | Last-trading-day-of-month snapshot for validation |

### Which Surface Should I Use?

- Use `feature_panel` for most country-factor questions.
- Use `unified_panel` when you explicitly want the raw warehouse with no ASADO-generated normalized variants.
- Use `normalized_panel` when you need explicit normalization metadata such as `base_variable`, `normalization`, or rolling-window settings.
- Use `country_reference` whenever you need to map `reporter_iso3` or `counterpart_iso3` from bilateral tables onto ASADO country names.
- Use `gdelt_panel` when the question is specifically about GDELT-only features or partial-month GDELT labels.
- Use `bloomberg_factors` when you want only Bloomberg-native or Bloomberg-derived fields.
- Use `macrostructure_factors` when you want the ownership / fragility / central-bank-footprint / policy-backstop layer in isolation.
- Use `bilateral_portfolio_matrix` for reporter-counterparty portfolio ownership, not `unified_panel`.
- Use `t2_factors_daily` / `gdelt_factors_daily` for daily-frequency analysis, event windows, or intramonth behavior.
- Use `t2_levels_daily` when you need raw (un-normalized) daily price/fundamental levels.
- Use `factor_returns_daily` for daily optimizer portfolio returns (strategy P&L analysis).
- Use `variable_meta` to discover which variables are optimizer-selected, their category, and monthly equivalents.
- Use `daily_calendar` to identify trading vs. non-trading days per country (handles Saudi Sun-Thu, China holidays, etc.)
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

Current live example:

- `CURRENT_DATE`: `2026-04-19`
- current partial-month GDELT label: `2026-05-01`

Interpretation:

- for GDELT, `2026-05-01` is treated as the current partial-month observed label
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

## Macrostructure Central-Bank Footprint Layer

The macrostructure panel now includes a transparent Phase 3 central-bank footprint block:

- `MS_CentralBank_BalanceSheet_GDP`
  Central-bank total assets from IMF `MFS_CBS` scaled by same-year WEO nominal GDP in USD.
- `MS_CentralBank_Claims_on_Government_Pct_GDP`
  Central-bank claims on central government from IMF `MFS_CBS` scaled by same-year WEO nominal GDP in USD.
- `MS_CentralBank_SovDebt_Share`
  Transparent proxy for the central-bank share of sovereign debt. Numerator is `MS_CentralBank_Claims_on_Government_Pct_GDP`; denominator prefers `MS_Public_Debt_Total_Pct_GDP` from QPSD and falls back to annual WEO debt/GDP when QPSD is missing.

Current live coverage from the 2026-04-19 rebuild:

- `MS_CentralBank_BalanceSheet_GDP`: 5,754 rows, 21 countries, 1997-12-01 through 2026-03-01
- `MS_CentralBank_Claims_on_Government_Pct_GDP`: 7,157 rows, 26 countries, 1997-12-01 through 2026-03-01
- `MS_CentralBank_SovDebt_Share`: 7,091 rows, 26 countries, 1997-12-01 through 2026-03-01

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

157 Factor nodes (those with daily optimizer returns) carry daily performance stats:

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
- **Factor returns**: `factor_returns_daily` contains daily portfolio returns for 157 factors, sourced from the T2 and GDELT optimizers. `source` is `t2_optimizer_daily` or `gdelt_optimizer_daily`.
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
| `event_window(country, date, days_before, days_after)` | Quick event studies — returns T2 factors, GDELT, factor returns, and calendar in one call |
| `daily_factor_series(country, variables, start_date, end_date, source)` | General daily time-series extraction from any daily table |

### Rebuild

```bash
python scripts/build_daily_panels.py --rebuild --no-backup   # full rebuild (~105s)
python scripts/build_daily_panels.py --check                 # health check
```

Full implementation details: [`docs/DAILY_EXTENSION_STATUS.md`](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/docs/DAILY_EXTENSION_STATUS.md)

## Guardrails

- Prefer read-only access.
- Use `unified_panel` by default for monthly questions unless a panel-specific table is clearly more appropriate.
- Use daily tables (`t2_factors_daily`, `gdelt_factors_daily`) for intramonth or event-study questions.
- Use `gdelt_panel` for GDELT-specific latest/current questions if the date-label convention matters.
- Do not assume `bilateral_portfolio_matrix` has `country`, `variable`, and `value`; it does not.
- For human discovery, start with this file.
- For agent discovery, start with [access_guide.json](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/cache/query_assistant/access_guide.json).
