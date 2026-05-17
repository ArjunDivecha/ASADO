# PRD: World Bank Commodity Price Intelligence Import
## ASADO Commodity Shock And Return Attribution Layer

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Date** | 2026-05-16 |
| **Author** | Codex, from Arjun's product direction |
| **Status** | Draft for implementation |
| **Depends on** | Existing DuckDB monthly panels, daily panel builder, monthly updater, returns-first MCP layer, ASADO event-window tooling |
| **Companion to** | `PRD_Returns_First_Source_Of_Truth.md`, `PRD_Event_Log.md`, `PRD_Stage2_Prediction_Markets.md`, `DATA_DICTIONARY.md` |
| **Estimated effort** | 2-4 implementation days for V1 |

---

## 1. Purpose

Add a canonical commodity-price intelligence layer to ASADO using the World Bank Commodity Price Data, commonly called the Pink Sheet.

ASADO already has commodity proxies in T2:

- `Oil`, `Oil 12`
- `Copper`, `Copper 12`
- `Gold`, `Gold 12`
- `Agriculture`, `Agriculture 12`

Those are useful, but they are coarse. The World Bank commodity dataset expands the commodity surface to 71 monthly benchmark prices plus 16 aggregate commodity indices, starting in 1960. This lets ASADO answer sharper questions:

- Which countries benefited when fertilizer prices surged?
- Did copper exporters outperform copper importers around a copper shock?
- Which T2 factors historically perform best during grain-price spikes?
- Are current country returns aligned with their oil, gas, metals, precious-metals, or agriculture exposures?
- Did prediction-market oil-shock probabilities correctly anticipate realized commodity-price moves?

The import must preserve ASADO's core analytical principle:

> Commodity prices are explanatory inputs. Country and factor returns remain the outcome source of truth.

Commodity data should enrich the explanatory and event context around returns, not replace returns as the answer layer.

---

## 2. Audit Summary

### 2.1 Candidate Sources Audited

| Source | URL | Status | Audit Result |
|---|---|---|---|
| Official World Bank Commodity Markets page | https://www.worldbank.org/en/research/commodity-markets | Use as canonical source discovery page | Lists current Pink Sheet publications, monthly prices XLS, annual prices XLS, reports, terms of use, and next update date. Verified 2026-05-16. |
| Official World Bank monthly XLS | `CMO-Historical-Data-Monthly.xlsx` linked from the World Bank Commodity Markets page | Use as canonical V1 source | Direct workbook with structured sheets: `Monthly Prices`, `Monthly Indices`, `Description`, `Index Weights`. Latest file inspected was updated 2026-05-04 and covers 1960M01 through 2026M04. |
| Kaggle: World Bank Commodity Price Intelligence 1960-2026 | https://www.kaggle.com/datasets/kanchana1990/world-bank-commodity-price-intelligence-19602026 | Do not use as canonical | Convenient enriched CSV, but less current than official XLS and has metadata defects: only 34 non-null commodity codes for 71 names, and several category assignments are wrong or ambiguous. Useful as a reference for derived-column ideas only. |
| Hugging Face datasets | Hub search for `World Bank Commodity Price Intelligence` and `world bank commodity prices pink sheet` | No matching canonical mirror found | No direct HF dataset found. No HF dependency needed for this import. |

### 2.2 Official Workbook Facts

Verified from the official `CMO-Historical-Data-Monthly.xlsx` linked by the World Bank page on 2026-05-16:

| Sheet | Contents | Observed Shape |
|---|---|---|
| `Monthly Prices` | Monthly nominal USD commodity prices | 71 commodity price series, 796 monthly observations, 1960M01 to 2026M04 |
| `Monthly Indices` | Monthly nominal USD commodity indices, 2010=100 | 16 index series, 796 monthly observations, 1960M01 to 2026M04 |
| `Description` | Series descriptions and source methodology | 400+ rows of source descriptions |
| `Index Weights` | Commodity index weights | Weight table for aggregate index construction |

Example `Monthly Prices` series:

- `CRUDE_PETRO` - Crude oil, average
- `CRUDE_BRENT` - Crude oil, Brent
- `CRUDE_DUBAI` - Crude oil, Dubai
- `CRUDE_WTI` - Crude oil, WTI
- `COAL_AUS` - Coal, Australian
- `NGAS_US` - Natural gas, US
- `NGAS_EUR` - Natural gas, Europe
- `COCOA`, `COFFEE_ARABIC`, `COFFEE_ROBUS`
- `MAIZE`, `WHEAT_US_HRW`, `WHEAT_US_SRW`
- `PALM_OIL`, `SOYBEANS`, `SOYBEAN_OIL`
- `ALUMINUM`, `IRON_ORE`, `COPPER`, `NICKEL`, `ZINC`
- `GOLD`, `PLATINUM`, `SILVER`

Example `Monthly Indices` series:

- `iOVERALL`
- `iENERGY`
- `iNONFUEL`
- `iAGRICULTURE`
- `iBEVERAGES`
- `iFOOD`
- `iFATS_OILS`
- `iGRAINS`
- `iFERTILIZERS`
- `iMETMIN`
- `iBASEMET`
- `iPRECIOUSMET`

### 2.3 Kaggle Dataset Facts

Downloaded via the public Kaggle dataset endpoint on 2026-05-16:

| Field | Observed Value |
|---|---|
| Kaggle ref | `kanchana1990/world-bank-commodity-price-intelligence-19602026` |
| File | `wb_commodity_price_intelligence_1960_2026.csv` |
| Uncompressed size | ~18.4 MB |
| Rows | 49,093 |
| Columns | 29 |
| Date range | 1960-01-01 to 2026-02-01 |
| Commodity names | 71 |
| Non-null commodity codes | 34 |
| Data sources in file | World Bank Pink Sheet plus 80 FRED extension rows |
| Retrieved date in file | 2026-03-16 |

Useful columns:

- `date`
- `commodity_name`
- `price_nominal_usd`
- `unit`
- `category`
- `source_desc`
- `data_source`
- `price_mom_pct`
- `price_yoy_pct`
- `price_3m_avg`
- `price_12m_avg`
- `price_60m_avg`
- `price_12m_volatility`
- `price_index_2000_base`
- `is_all_time_high`
- `is_all_time_low`
- `price_regime_mom`
- `commodity_code`

Problems found:

- Some commodity names have missing `commodity_code`.
- Some category mappings are wrong. Example: `Aluminum`, `Copper`, and `Iron ore` appear under `Fertilizers`; `Rice, Thai 5%` appears under `Energy`.
- Kaggle version is older than the official World Bank workbook available at audit time.
- The FRED extensions are useful but should be reproduced internally if needed, not trusted as a black-box merge.

Decision: **do not build the ASADO pipeline from Kaggle.** Use official World Bank XLS as canonical; optionally recreate a subset of Kaggle-style derived features from canonical raw data.

---

## 3. Current ASADO Coverage

Live DuckDB audit on 2026-05-16:

| Surface | Current Coverage | Gap |
|---|---|---|
| `t2_raw` / `feature_panel` | `Gold`, `Copper`, `Oil`, `Agriculture`, and 12M variants for all 34 countries; 2000-02-01 through 2026-05-01 | Only 4 broad commodity proxies; no gas, coal, iron ore, fertilizers, grains, coffee, cocoa, rice, palm oil, nickel, zinc, etc. |
| `extended_factors` / FAOSTAT | Annual agriculture exposure indicators: import dependency, self-sufficiency, ag trade openness, ag export share, terms of trade | Exposure layer exists but price shocks are coarse and annual. |
| `extended_factors` / EIA | Petroleum consumption through 2019 | Useful oil-import proxy but stale and oil-only. |
| Neo4j `Commodity` nodes | 4 commodity nodes: Oil, Copper, Gold, Agriculture | Too coarse for questions about gas, coal, fertilizer, grains, food, base metals, precious metals, or soft commodities. |
| `event_log` | Oil-supply events and broad commodity shock events | Lacks realized commodity-price context for event studies. |
| `predmkt_signals_daily` | Oil shock / commodity-related prediction-market probabilities | Needs realized price series to compare priced probability vs realized commodity moves. |

This import fills the broad commodity-price gap without disturbing the existing T2 return pipeline.

---

## 4. Product Goals

### G1. Add Canonical World Bank Commodity Price Tables

Create first-class DuckDB tables for official World Bank monthly commodity prices, indices, descriptions, and index weights.

### G2. Add ASADO-Compatible Commodity Factor Panel

Materialize selected commodity price and return features into the existing ASADO long schema:

```text
date, country, value, variable, source
```

Global commodity features should be broadcast across the 34 T2 countries only when they are intended as country-level explanatory factors. The canonical commodity-axis tables should remain unbroadcasted to preserve the commodity dimension.

### G3. Preserve Returns-First Behavior

Commodity questions should answer in this order:

1. Identify the relevant commodity price move.
2. Identify affected countries via exposure mapping.
3. Show country returns and/or factor returns over the relevant window.
4. Explain the commodity channel and caveats.

### G4. Improve Commodity Shock Event Studies

Allow `event_window`-style workflows to include realized commodity moves around oil, gas, metal, food, fertilizer, and agricultural shock dates.

### G5. Improve Country Exposure Granularity

Expand the graph and country metadata from 4 broad commodities to a richer commodity taxonomy with export/import channels.

---

## 5. Non-Goals

- **NG1.** Do not replace T2 `Oil`, `Copper`, `Gold`, or `Agriculture` immediately. They remain legacy factors until a validation pass confirms a safe migration.
- **NG2.** Do not use Kaggle as the canonical source.
- **NG3.** Do not add commodity features to optimizer output tables. This is an input/explanatory layer only.
- **NG4.** Do not build a daily commodity futures database in V1. The Pink Sheet is monthly; daily commodity data can be a later Bloomberg/FRED/Quandl-style project.
- **NG5.** Do not attempt full country-level trade exposure by commodity in V1. V1 starts with static curated exporter/importer mappings plus existing FAO/EIA exposures.
- **NG6.** Do not make causal claims from simple commodity-return correlations. The MCP should frame results as historical association or event-window evidence.

---

## 6. Data Model

### 6.1 Raw Tables

Create three canonical tables in DuckDB.

```sql
CREATE TABLE wb_commodity_prices (
    date DATE NOT NULL,
    commodity_code VARCHAR NOT NULL,
    commodity_name VARCHAR NOT NULL,
    unit VARCHAR,
    nominal_price_usd DOUBLE,
    category VARCHAR NOT NULL,
    source_sheet VARCHAR DEFAULT 'Monthly Prices',
    source_file_date DATE,
    source_url VARCHAR,
    last_loaded_at TIMESTAMP,
    PRIMARY KEY (date, commodity_code)
);
```

```sql
CREATE TABLE wb_commodity_indices (
    date DATE NOT NULL,
    index_code VARCHAR NOT NULL,
    index_name VARCHAR NOT NULL,
    nominal_index_2010_100 DOUBLE,
    category VARCHAR,
    source_sheet VARCHAR DEFAULT 'Monthly Indices',
    source_file_date DATE,
    source_url VARCHAR,
    last_loaded_at TIMESTAMP,
    PRIMARY KEY (date, index_code)
);
```

```sql
CREATE TABLE wb_commodity_meta (
    series_code VARCHAR PRIMARY KEY,
    series_type VARCHAR NOT NULL, -- price | index
    display_name VARCHAR NOT NULL,
    category VARCHAR NOT NULL,
    unit VARCHAR,
    source_description VARCHAR,
    canonical_source VARCHAR DEFAULT 'World Bank Pink Sheet',
    import_status VARCHAR DEFAULT 'active'
);
```

Optional V2:

```sql
CREATE TABLE wb_commodity_index_weights (
    index_code VARCHAR,
    component_code VARCHAR,
    component_name VARCHAR,
    weight_pct DOUBLE,
    weight_basis VARCHAR,
    source_file_date DATE,
    PRIMARY KEY (index_code, component_code)
);
```

### 6.2 Derived Commodity Features

Create a derived table that keeps the commodity axis:

```sql
CREATE TABLE wb_commodity_features (
    date DATE NOT NULL,
    series_code VARCHAR NOT NULL,
    series_type VARCHAR NOT NULL, -- price | index
    feature VARCHAR NOT NULL,     -- level, mom_pct, yoy_pct, ret_3m_pct, ret_12m_pct, vol_12m
    value DOUBLE,
    source VARCHAR DEFAULT 'wb_commodity',
    PRIMARY KEY (date, series_code, feature)
);
```

Recommended V1 features:

| Feature | Definition | Reason |
|---|---|---|
| `level` | Raw nominal USD price or 2010=100 index | Direct inspection and charting |
| `mom_pct` | Month-over-month percentage change | Short-horizon shock detection |
| `yoy_pct` | Year-over-year percentage change | Inflation and terms-of-trade pressure |
| `ret_3m_pct` | 3-month percentage change | Near-term country return studies |
| `ret_12m_pct` | 12-month percentage change | Matches existing T2 commodity 12M convention |
| `vol_12m` | Trailing 12-month standard deviation of monthly returns | Commodity volatility regime |
| `z_36m` | 36-month trailing z-score of `level` or `yoy_pct` | Shock/regime classification |

Use trailing windows only. Shifted windows are not required for a historical descriptive feature, but any predictive/optimizer-facing variant must be point-in-time safe and must not use future data.

### 6.3 ASADO Feature Panel Projection

V1 should project a controlled subset into the existing long-format factor panel:

```text
date, country, value, variable, source
```

Source should be:

```text
wb_commodity
```

Variable naming:

```text
WB_CMDTY_{CODE}_{FEATURE}
```

Examples:

- `WB_CMDTY_CRUDE_BRENT_LEVEL`
- `WB_CMDTY_CRUDE_BRENT_RET_12M`
- `WB_CMDTY_COPPER_YOY`
- `WB_CMDTY_IENERGY_LEVEL`
- `WB_CMDTY_IFERTILIZERS_YOY`
- `WB_CMDTY_ICOCOA_RET_3M`

Projection rules:

1. Raw canonical commodity tables keep their commodity axis and do not carry a country column.
2. The ASADO feature projection broadcasts selected global commodity features to all 34 T2 countries, matching how some global FRED variables are handled.
3. Do not broadcast every derived feature blindly in V1. Start with:
   - all 16 aggregate indices, all V1 features;
   - 20-30 high-signal benchmark prices, all V1 features;
   - full 71-price universe in the canonical commodity tables.
4. Add a metadata flag to distinguish broadcast global commodity variables from country-native variables.

### 6.4 Suggested V1 Feature Projection Set

Mandatory:

- Crude oil: `CRUDE_PETRO`, `CRUDE_BRENT`, `CRUDE_DUBAI`, `CRUDE_WTI`
- Natural gas: `NGAS_US`, `NGAS_EUR`, `NGAS_JP`, `iNATGAS`
- Coal: `COAL_AUS`, `COAL_SAFRICA`
- Precious metals: `GOLD`, `SILVER`, `PLATINUM`
- Base metals: `COPPER`, `ALUMINUM`, `IRON_ORE`, `NICKEL`, `Zinc`, `LEAD`, `Tin`
- Fertilizers: `DAP`, `UREA_EE_BULK`, `PHOSROCK`, `POTASH`, `TSP`
- Grains: `MAIZE`, `WHEAT_US_HRW`, `WHEAT_US_SRW`, `RICE_05`, `BARLEY`
- Softs / food stress: `COCOA`, `COFFEE_ARABIC`, `COFFEE_ROBUS`, `SUGAR_WLD`, `PALM_OIL`, `SOYBEANS`, `SOYBEAN_OIL`
- Aggregate indices: all 16 index series

Optional V1 if low effort:

- Tea, bananas, beef, chicken, lamb, cotton, rubber, timber

---

## 7. Country Exposure Mapping

### 7.1 Current State

`setup_neo4j.py` currently defines 4 commodity nodes:

```text
Oil, Copper, Gold, Agriculture
```

with static exporter edges.

### 7.2 V1 Expansion

Create a curated config:

```text
config/commodity_exposure_map.yaml
```

Example:

```yaml
commodities:
  CRUDE_BRENT:
    display_name: Crude oil, Brent
    category: energy
    channels:
      oil_export:
        positive_countries: [Saudi Arabia, Canada, Brazil, Mexico, Indonesia, Malaysia, Vietnam, U.K.]
      oil_import_dependency:
        negative_countries: [India, Korea, Taiwan, Thailand, Philippines, Turkey, Poland]
  COPPER:
    display_name: Copper
    category: base_metals
    channels:
      commodity_export:
        positive_countries: [Chile, Australia, Mexico, Brazil, South Africa, Poland]
      manufacturing_input_cost:
        negative_countries: [Korea, Taiwan, ChinaA, ChinaH, Germany, Japan]
  GOLD:
    display_name: Gold
    category: precious_metals
    channels:
      commodity_export:
        positive_countries: [Australia, South Africa, Canada, Brazil, Mexico, ChinaA]
      safe_haven_risk:
        global: true
```

V1 exposure fields:

| Field | Meaning |
|---|---|
| `commodity_code` | World Bank commodity code |
| `country` | T2 country name |
| `channel` | Transmission channel |
| `direction` | `positive`, `negative`, or `mixed` |
| `strength` | 1-5 curated strength score |
| `basis` | `static_curated`, `fao`, `eia`, `trade_matrix`, `future_baci` |
| `notes` | Short rationale |

### 7.3 Neo4j Expansion

Add `Commodity` nodes for all mandatory V1 commodities and update edges:

```text
(Country)-[:EXPORT_EXPOSED_TO {strength, basis}]->(Commodity)
(Country)-[:IMPORT_EXPOSED_TO {strength, basis}]->(Commodity)
(Country)-[:INPUT_COST_EXPOSED_TO {strength, basis}]->(Commodity)
```

Existing broad nodes (`Oil`, `Copper`, `Gold`, `Agriculture`) should remain as parent/legacy nodes in V1. Add optional hierarchy:

```text
(Commodity)-[:PART_OF]->(CommodityGroup)
```

Examples:

- Brent, WTI, Dubai -> Oil
- Cocoa, Coffee, Sugar -> Softs
- Wheat, Maize, Rice -> Grains
- DAP, Urea, TSP -> Fertilizers

---

## 8. Pipeline Design

### 8.1 New Collector

Create:

```text
scripts/collect_wb_commodity_prices.py
```

Responsibilities:

1. Download the latest official monthly workbook from the World Bank Commodity Markets page or configured direct URL.
2. Save raw file under:

```text
Data/raw/wb_commodity_prices/CMO-Historical-Data-Monthly_YYYYMMDD.xlsx
```

3. Parse `Monthly Prices` into long format.
4. Parse `Monthly Indices` into long format.
5. Parse `Description` into `wb_commodity_meta`.
6. Compute derived trailing features.
7. Write processed parquet files:

```text
Data/processed/wb_commodity_prices.parquet
Data/processed/wb_commodity_indices.parquet
Data/processed/wb_commodity_meta.parquet
Data/processed/wb_commodity_features.parquet
Data/processed/wb_commodity_factor_panel.parquet
```

8. Validate row counts, date ranges, duplicate keys, and category coverage.

### 8.2 Source URL Handling

The official page exposes document links that may change over time. Implement source discovery in this order:

1. Config override:

```text
WB_COMMODITY_MONTHLY_XLS_URL
```

2. Known stable document link from current audit:

```text
https://thedocs.worldbank.org/.../CMO-Historical-Data-Monthly.xlsx
```

3. Scrape the World Bank Commodity Markets page for the `Monthly prices` XLS link.

The collector should fail closed if it cannot find a valid workbook. Do not silently fall back to Kaggle.

### 8.3 Idempotency And Caching

The collector should:

- cache the raw workbook by source update date or response ETag if available;
- skip parsing if the raw workbook hash matches the latest processed manifest;
- write a manifest:

```text
Data/processed/wb_commodity_manifest.json
```

with:

```json
{
  "source_url": "...",
  "downloaded_at": "2026-05-16T...",
  "source_updated_label": "Updated on May 04, 2026",
  "workbook_sha256": "...",
  "price_series_count": 71,
  "index_series_count": 16,
  "min_date": "1960-01-01",
  "max_date": "2026-04-01"
}
```

### 8.4 Integration Into DuckDB

Modify `scripts/setup_duckdb.py`:

- add constants for the new processed parquet files;
- load canonical commodity tables if files exist;
- create empty tables if absent so MCP schema is stable;
- add `wb_commodity_factor_panel` to `unified_panel` and, if appropriate, to `feature_panel`;
- index:

```sql
CREATE INDEX idx_wb_commodity_prices_code_date ON wb_commodity_prices(commodity_code, date);
CREATE INDEX idx_wb_commodity_features_code_feature_date ON wb_commodity_features(series_code, feature, date);
CREATE INDEX idx_wb_commodity_factor_panel_ctry_date ON wb_commodity_factor_panel(country, date);
CREATE INDEX idx_wb_commodity_factor_panel_var ON wb_commodity_factor_panel(variable);
```

Do not add any commodity-derived data to `factor_returns`, `factor_returns_daily`, `factor_top20_membership`, or `country_factor_attribution`.

### 8.5 Daily And Monthly Update Orchestration

The commodity source is monthly, but it must be incorporated into both ASADO update paths:

1. The monthly updater must refresh the commodity source when ASADO performs a full monthly rebuild.
2. The daily panel updater must preserve, health-check, and expose the latest monthly commodity context for daily/event workflows.
3. Neither updater may silently drop commodity tables or let stale commodity data disappear from MCP/schema surfaces.

#### 8.5.1 Monthly updater contract

Modify `scripts/monthly_update.py`:

1. Run `collect_wb_commodity_prices.py --force` after `collect_extended.py` and before the first `setup_duckdb.py` pass.
2. Rebuild DuckDB with commodity tables loaded before `build_normalized_panel.py`, `build_daily_panels.py`, `setup_neo4j.py`, `build_embeddings.py`, and `build_schema_registry.py`.
3. Continue on collector failure using source-level preservation behavior:
   - if prior processed parquet exists, keep using it;
   - if no prior processed parquet exists, create empty tables and mark source unavailable.
4. Include commodity row counts, distinct series counts, official workbook update label, latest observation date, and staleness warning in the monthly report.
5. Add a monthly-update stage name visible in logs and the operator UI:

```text
collect_wb_commodity_prices.py
```

6. Add flags:

```text
--skip-wb-commodity       # skip commodity collection, preserve prior processed parquets
--commodity-only          # run commodity collector + DuckDB/schema refresh only
```

The `--db-only` path must load commodity parquets into DuckDB if they already exist.

#### 8.5.2 Daily updater contract

Modify `scripts/build_daily_panels.py`:

1. Do not download or rebuild the World Bank monthly workbook by default. This source is monthly; the daily updater should not create a noisy daily external dependency.
2. When rebuilding daily tables, preserve all `wb_commodity_*` tables already loaded in `Data/asado.duckdb`.
3. Add a `--check` health line for commodity context:

```text
wb_commodity_prices: 71 series, latest=YYYY-MM-01, age_days=N, status=ok|stale|missing
```

4. Add `variable_meta` rows for commodity-broadcast variables, with:

```text
native_frequency = 'monthly'
source_table = 'wb_commodity_factor_panel'
category = 'commodity'
freshness_expectation = 'monthly'
```

5. If `event_window` or future daily tools request commodity context, join to the most recent prior monthly commodity observation rather than forward-looking to a later monthly print.
6. Add a guardrail test that `build_daily_panels.py --rebuild --no-backup` does not drop or overwrite canonical commodity tables.

#### 8.5.3 Daily refresh option

If a future scheduled daily update wrapper exists, it may call:

```text
collect_wb_commodity_prices.py --check
```

but it should only download and parse when the official workbook has changed or when the latest commodity observation is stale beyond the configured threshold. The default stale threshold is 75 days.

---

## 9. MCP And Query Assistant Requirements

### 9.1 New MCP Tool: `commodity_price_series`

```python
def commodity_price_series(
    commodity: str,
    feature: str = "level",
    start_date: str | None = None,
    end_date: str | None = None,
    max_rows: int = 500,
) -> dict:
    ...
```

Inputs:

- `commodity`: code or fuzzy display name, e.g. `brent`, `CRUDE_BRENT`, `copper`, `fertilizer`, `iENERGY`
- `feature`: `level`, `mom_pct`, `yoy_pct`, `ret_3m_pct`, `ret_12m_pct`, `vol_12m`, `z_36m`

Returns:

- matched commodity metadata;
- time series rows;
- source caveat;
- latest value summary.

### 9.2 New MCP Tool: `commodity_shock_context`

```python
def commodity_shock_context(
    commodity: str,
    date: str,
    months_before: int = 12,
    months_after: int = 6,
    countries: str = "mapped",
    include_returns: bool = True,
    include_factor_returns: bool = True,
) -> dict:
    ...
```

Workflow:

1. Pull commodity move around the date.
2. Map affected countries via `commodity_exposure_map`.
3. Pull country returns for affected countries using `country_returns`.
4. Pull factor return leaders using `factor_return_series` / `return_leaders`.
5. Return an event-style summary.

### 9.3 Query Assistant Rules

Update planner prompt:

- For questions about oil, gas, copper, gold, grains, fertilizers, food, metals, or commodity shocks, first identify the relevant World Bank commodity series.
- If the question asks "who benefits" or "who is hurt", use commodity exposure mapping and then return country returns.
- If the question asks "what happened around X", use `commodity_shock_context` or `events_in_window` -> `event_window`.
- If the question asks "what factors worked during commodity shocks", use `factor_return_series` / `return_leaders`.
- Do not answer commodity shock questions solely with commodity price charts.

### 9.4 Schema Registry

Update `scripts/build_schema_registry.py`:

- add `wb_commodity_prices`, `wb_commodity_indices`, `wb_commodity_features`, and `wb_commodity_factor_panel`;
- add commodity aliases:
  - oil -> `CRUDE_PETRO`, `CRUDE_BRENT`, `CRUDE_WTI`
  - brent -> `CRUDE_BRENT`
  - wti -> `CRUDE_WTI`
  - copper -> `COPPER`
  - gold -> `GOLD`
  - fertilizer -> `iFERTILIZERS`, `DAP`, `UREA_EE_BULK`, `TSP`, `POTASH`, `PHOSROCK`
  - food -> `iFOOD`
  - grains -> `iGRAINS`, `MAIZE`, `WHEAT_US_HRW`, `WHEAT_US_SRW`, `RICE_05`
  - natural gas -> `NGAS_US`, `NGAS_EUR`, `NGAS_JP`, `iNATGAS`
- mark `wb_commodity_factor_panel` variables as global-broadcast explanatory features.

---

## 10. Validation Requirements

### 10.1 Collector Validation

`collect_wb_commodity_prices.py --check` must assert:

- raw workbook exists;
- `Monthly Prices` has at least 65 commodity series;
- `Monthly Indices` has at least 12 index series;
- latest date is within 75 days of current date unless `--allow-stale`;
- no duplicate `(date, commodity_code)` rows;
- no duplicate `(date, index_code)` rows;
- all mandatory V1 commodities are present;
- category mapping is internally owned, not copied blindly from Kaggle;
- derived features use only current and prior observations.

### 10.2 DuckDB Validation

After `setup_duckdb.py`:

```sql
SELECT COUNT(*), COUNT(DISTINCT commodity_code), MIN(date), MAX(date)
FROM wb_commodity_prices;
```

Expected V1:

- row count around `71 * 796 = 56,516` for the May 2026 workbook, less missing historical series;
- 71 distinct commodity codes;
- min date `1960-01-01`;
- max date at least `2026-04-01` for current audit file.

```sql
SELECT COUNT(*), COUNT(DISTINCT index_code), MIN(date), MAX(date)
FROM wb_commodity_indices;
```

Expected V1:

- 16 index codes;
- min date `1960-01-01`;
- max date at least `2026-04-01`.

### 10.3 Returns-First Behavioral Tests

Add query-assistant test cases:

1. "Which countries benefited most from the 2022 oil spike?"
   - Must use commodity context and country returns.
2. "Show factor return leaders during copper price rallies."
   - Must use commodity series plus factor returns.
3. "Did fertilizer shocks hurt India?"
   - Must use fertilizer price series, India country returns, and caveat about import exposure.
4. "What happened around the 2020 negative oil futures episode?"
   - Must use `event_window` or commodity shock context plus returns.
5. "Show me latest commodity moves."
   - May answer with commodity features, but should not claim return impact without returning country/factor returns.

### 10.4 Graph Validation

After `setup_neo4j.py`:

```cypher
MATCH (c:Commodity) RETURN count(c);
```

Expected:

- existing 4 broad nodes still present;
- mandatory V1 commodity nodes added.

```cypher
MATCH (:Country)-[r]->(:Commodity)
WHERE type(r) IN ['EXPORT_EXPOSED_TO', 'IMPORT_EXPOSED_TO', 'INPUT_COST_EXPOSED_TO']
RETURN type(r), count(r);
```

Expected:

- at least existing 28 `EXPORT_EXPOSED_TO` edges retained;
- new import/input-cost edges present for oil, gas, fertilizer, grains, and metals.

---

## 11. Implementation Plan

### Phase A - Source Parser And Audit Harness

Files:

- `scripts/collect_wb_commodity_prices.py`
- `tests` or `scripts/qa/validate_wb_commodity_prices.py`

Tasks:

1. Download official monthly workbook.
2. Parse `Monthly Prices`.
3. Parse `Monthly Indices`.
4. Build internal category map.
5. Write raw canonical parquets and manifest.
6. Add `--check`.

Exit criteria:

- canonical parquet files created;
- parser reports 71 price series and 16 index series on the audited workbook;
- latest date at least 2026-04-01 using the May 2026 file.

### Phase B - Derived Features And ASADO Projection

Files:

- `scripts/collect_wb_commodity_prices.py`
- `scripts/setup_duckdb.py`
- `scripts/build_normalized_panel.py` if needed

Tasks:

1. Compute V1 derived features.
2. Build `wb_commodity_features.parquet`.
3. Build `wb_commodity_factor_panel.parquet` for selected broadcast features.
4. Load tables into DuckDB.
5. Add factor-panel projection to `unified_panel` / `feature_panel`.

Exit criteria:

- commodity factor variables are queryable from DuckDB;
- no optimizer-output tables are touched;
- schema registry exposes the new variables.

### Phase C - Exposure Mapping And Graph

Files:

- `config/commodity_exposure_map.yaml`
- `scripts/setup_neo4j.py`
- `scripts/build_schema_registry.py`

Tasks:

1. Expand commodity node taxonomy.
2. Add curated country exposure channels.
3. Preserve legacy broad commodity edges.
4. Add query-assistant aliases.

Exit criteria:

- Neo4j contains expanded commodity nodes and channel-specific exposure edges;
- existing commodity tests still pass.

### Phase D - MCP Tools And Query Tests

Files:

- `scripts/asado_mcp_server.py`
- `scripts/query_assistant.py`
- `scripts/run_query_assistant_suite.py`

Tasks:

1. Add `commodity_price_series`.
2. Add `commodity_shock_context`.
3. Update planner prompts and return-surface rules.
4. Add behavioral tests.

Exit criteria:

- commodity questions route through commodity data and then returns;
- "who benefits" questions use country returns;
- event questions use commodity shock context or event windows.

### Phase E - Daily And Monthly Orchestration

Files:

- `scripts/monthly_update.py`
- `scripts/build_daily_panels.py`
- `scripts/update_server.py`
- `DATA_DICTIONARY.md`
- `docs/factor_reference.md` generated via existing script

Tasks:

1. Add collector to full monthly update before DuckDB rebuild.
2. Add `--skip-wb-commodity` and `--commodity-only` flags.
3. Ensure `--db-only` loads existing commodity parquets.
4. Ensure daily panel rebuilds preserve commodity tables.
5. Add daily `--check` commodity staleness reporting.
6. Add commodity metadata to `variable_meta`.
7. Add report row counts and latest dates.
8. Update operator UI stage labels if `scripts/update_server.py` parses monthly-update stages.
9. Update docs and source registry.
10. Run full validation.

Exit criteria:

- `python scripts/monthly_update.py --dry-run` includes commodity stage;
- `python scripts/monthly_update.py --commodity-only` rebuilds commodity parquets, DuckDB commodity tables, schema cache, and docs without running unrelated collectors;
- `python scripts/monthly_update.py --db-only` loads existing commodity parquets;
- `python scripts/build_daily_panels.py --check` reports commodity context health;
- `python scripts/build_daily_panels.py --rebuild --no-backup` preserves `wb_commodity_*` tables;
- full monthly update can rebuild DuckDB with commodity tables;
- docs identify World Bank Pink Sheet as canonical commodity source.

---

## 12. Acceptance Criteria

### Data

- `wb_commodity_prices` exists in DuckDB with 65+ commodity price series.
- `wb_commodity_indices` exists with 12+ index series.
- `wb_commodity_features` exists with V1 derived features.
- `wb_commodity_factor_panel` exists with selected broadcast variables for all 34 T2 countries.
- Latest official workbook date and latest data date are written to manifest.
- Kaggle is not required for a successful build.
- Full monthly update incorporates the commodity collector before DuckDB/schema rebuild.
- Daily panel rebuilds preserve commodity tables and report commodity freshness.

### Product

- User can ask for a commodity series directly and receive source-aware time series.
- User can ask "which countries benefit from X commodity spike?" and receive country-return evidence.
- User can ask "which factors work during X commodity rallies?" and receive factor-return evidence.
- User can ask event-window questions around oil, gas, metals, food, and fertilizer shocks.

### Safety

- Returns remain the analytical source of truth.
- Commodity data is labeled as explanatory/global-broadcast data.
- The optimizer cycle guard is preserved.
- No silent fallback from official source to Kaggle.
- All local files stay under the ASADO workspace root.

---

## 13. Risks And Mitigations

| Risk | Mitigation |
|---|---|
| World Bank document links change | Discover current monthly XLS from the Commodity Markets page and allow env override. |
| Official workbook structure changes | Validate header rows, required sheets, and minimum series counts before writing processed outputs. |
| Kaggle categories tempt shortcut usage | Document Kaggle audit defects and keep the pipeline official-source-only. |
| Feature-panel bloat | Canonical tables keep all series; broadcast only selected high-signal variables in V1. |
| Country exposure mapping is subjective | Store curated exposure config with `basis`, `strength`, and `notes`; upgrade later with BACI/Comtrade product-level trade data. |
| Commodity price moves are global, not country-specific | Mark broadcast variables explicitly and require return-surface evidence for country claims. |
| Lookahead leakage in derived features | Use only trailing windows and add QA checks for feature dates. |

---

## 14. Open Questions

1. Should V1 broadcast all 71 commodity price series, or only the mandatory high-signal set?
   - Recommendation: canonical all 71; broadcast mandatory high-signal set only.

2. Should World Bank monthly indices be treated as separate variables or metadata over prices?
   - Recommendation: separate variables. They are useful for broad factor regimes.

3. Should Kaggle-derived fields like `era` and `price_regime_mom` be reproduced?
   - Recommendation: reproduce only objective derived features in V1. Avoid narrative regime labels until ASADO has its own rules.

4. Should daily commodity data be added from Bloomberg/FRED later?
   - Recommendation: yes, but only after monthly Pink Sheet import ships and validates usefulness.

5. Should commodity exposures be included in optimizer inputs immediately?
   - Recommendation: only after a PIT audit and backtest. Start queryable/explanatory first.

---

## 15. Source Notes

- World Bank Commodity Markets page: https://www.worldbank.org/en/research/commodity-markets
- Official World Bank Pink Sheet document page: https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/world-bank-commodities-price-data-the-pink-sheet
- Official monthly workbook audited: https://thedocs.worldbank.org/en/doc/74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/CMO-Historical-Data-Monthly.xlsx
- Kaggle audited mirror: https://www.kaggle.com/datasets/kanchana1990/world-bank-commodity-price-intelligence-19602026
- ASADO current commodity coverage audited from `Data/asado.duckdb` on 2026-05-16.
