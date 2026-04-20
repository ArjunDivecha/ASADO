# ASADO Data Dictionary

Human-facing reference for what is in the ASADO database, where it lives, and how to access it safely.

This document is meant for analysts, developers, and future agents who need to understand the current live ASADO data model without reverse-engineering the codebase.

## Purpose

ASADO combines:

- T2 factor data
- free-source macro / risk / structural data
- IMF datasets
- GDELT country news signals
- macrostructure / sticky-capital / central-bank-footprint / policy-backstop signals
- Bloomberg sovereign and ETF passive-flow data
- bilateral portfolio ownership
- a Neo4j knowledge graph for network relationships

The two most important access surfaces are:

1. DuckDB for time-series and factor analytics
2. Neo4j for relationship and network questions

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

### DuckDB Tables And Views

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

### Which Surface Should I Use?

- Use `feature_panel` for most country-factor questions.
- Use `unified_panel` when you explicitly want the raw warehouse with no ASADO-generated normalized variants.
- Use `normalized_panel` when you need explicit normalization metadata such as `base_variable`, `normalization`, or rolling-window settings.
- Use `country_reference` whenever you need to map `reporter_iso3` or `counterpart_iso3` from bilateral tables onto ASADO country names.
- Use `gdelt_panel` when the question is specifically about GDELT-only features or partial-month GDELT labels.
- Use `bloomberg_factors` when you want only Bloomberg-native or Bloomberg-derived fields.
- Use `macrostructure_factors` when you want the ownership / fragility / central-bank-footprint / policy-backstop layer in isolation.
- Use `bilateral_portfolio_matrix` for reporter-counterparty portfolio ownership, not `unified_panel`.

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

### When Neo4j Is Better Than DuckDB

Prefer Neo4j for:

- trade-network questions
- banking-exposure network questions
- portfolio-ownership graph traversals
- crisis-history lookups
- central-bank relationship queries
- factor-node relationship exploration

Prefer DuckDB for:

- ranking countries by factor values
- time-series history
- latest cross-sectional snapshots
- cross-source factor joins and filters

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

## Guardrails

- Prefer read-only access.
- Use `unified_panel` by default unless a panel-specific table is clearly more appropriate.
- Use `gdelt_panel` for GDELT-specific latest/current questions if the date-label convention matters.
- Do not assume `bilateral_portfolio_matrix` has `country`, `variable`, and `value`; it does not.
- For human discovery, start with this file.
- For agent discovery, start with [access_guide.json](/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/cache/query_assistant/access_guide.json).
