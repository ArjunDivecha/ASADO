# ASADO World Bank Commodity Extension - Implementation Status

**Date:** 2026-05-16  
**Status:** Implemented, loaded into DuckDB, exposed through schema cache, factor reference, query assistant guidance, monthly updater, daily metadata, and MCP.

## What Was Built

### Collector

- `scripts/collect_wb_commodity_prices.py`
  - Downloads the official World Bank Commodity Markets Pink Sheet workbook.
  - Uses the official workbook as canonical source; Kaggle mirrors are not dependencies.
  - Saves raw workbooks under `Data/raw/wb_commodity_prices/`.
  - Writes processed parquets and a manifest under `Data/processed/`.
  - Supports:
    - `--force`
    - `--check`
    - `--allow-stale`
    - `--url`

### Processed Outputs

| File | Purpose |
|---|---|
| `Data/processed/wb_commodity_prices.parquet` | Canonical monthly nominal USD commodity prices |
| `Data/processed/wb_commodity_indices.parquet` | Canonical World Bank commodity price indices, 2010=100 |
| `Data/processed/wb_commodity_features.parquet` | Derived trailing features on the commodity/index axis |
| `Data/processed/wb_commodity_meta.parquet` | Series metadata, categories, units, and projection flags |
| `Data/processed/wb_commodity_factor_panel.parquet` | Selected global commodity features broadcast to ASADO countries |
| `Data/processed/wb_commodity_variable_catalog.csv` | Human-inspectable projected variable catalog |
| `Data/processed/wb_commodity_manifest.json` | Source URL, update label, workbook hash, counts, and guardrail note |

### DuckDB Tables

| Table | Rows | Date Range | Notes |
|---|---:|---|---|
| `wb_commodity_prices` | 50,099 | 1960-01-01 -> 2026-04-01 | 71 price series |
| `wb_commodity_indices` | 12,736 | 1960-01-01 -> 2026-04-01 | 16 index series |
| `wb_commodity_features` | 435,618 | 1960-01-01 -> 2026-04-01 | 87 series x 7 derived features where available |
| `wb_commodity_meta` | 87 | n/a | Price/index metadata |
| `wb_commodity_factor_panel` | 9,600,274 | 1960-01-01 -> 2026-04-01 | 371 projected variables x 34 countries |

Current source label: `Updated on May 04, 2026`.

## Feature Definitions

`wb_commodity_features` contains:

- `level`
- `mom_pct`
- `yoy_pct`
- `ret_3m_pct`
- `ret_12m_pct`
- `vol_12m`
- `z_36m`

All rolling features use current and prior observations only.

## Projection Into ASADO Panels

`wb_commodity_factor_panel` uses standard ASADO factor-panel shape:

```text
date, country, value, variable, source
```

with:

```text
source = 'wb_commodity'
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
- `WB_CMDTY_IFERTILIZERS_Z_36M`

These rows are included in `unified_panel`, then flow through `build_normalized_panel.py` into `feature_panel` and generated `_CS` / `_TS` variants where eligible.

## Updater Integration

Monthly updater:

```bash
./venv/bin/python scripts/monthly_update.py
```

Runs `collect_wb_commodity_prices.py --force` during the collection stage.

Commodity-only path:

```bash
./venv/bin/python scripts/monthly_update.py --commodity-only
```

This runs the commodity collector, clean DuckDB rebuild, normalization, daily panel restore, schema refresh, and factor reference refresh.

Skip commodity collection while preserving prior processed files:

```bash
./venv/bin/python scripts/monthly_update.py --skip-wb-commodity
```

Daily builder:

- `build_daily_panels.py --check` reports commodity freshness.
- `variable_meta` includes commodity broadcast variables with:
  - `source_table='wb_commodity_factor_panel'`
  - `category='commodity'`
  - `native_frequency='monthly'`
  - `freshness_expectation='monthly'`

## MCP / Query Surfaces

New MCP tool:

```python
commodity_price_series(
    commodity: str,
    feature: str = "level",
    start_date: str | None = None,
    end_date: str | None = None,
    max_rows: int = 500,
)
```

Accepted feature aliases include `ret_12m` -> `ret_12m_pct` and `yoy` -> `yoy_pct`.

## Guardrails

- Commodity variables are explanatory global context, not returns.
- Do not add commodity data to:
  - `factor_returns`
  - `factor_returns_daily`
  - `factor_top20_membership`
  - `country_factor_attribution`
- For country/factor impact claims, use commodity context plus the Returns Source Of Truth surfaces (`country_returns`, `factor_return_series`, `country_factor_attribution`, `return_leaders`).

## Validation

Latest validation commands:

```bash
./venv/bin/python scripts/collect_wb_commodity_prices.py --check
./venv/bin/python scripts/monthly_update.py --commodity-only --skip-wb-commodity
./venv/bin/python scripts/build_daily_panels.py --check
./venv/bin/python scripts/build_schema_registry.py --duck-only
./venv/bin/python scripts/build_factor_reference.py
```

Latest live checks:

- `wb_commodity_prices`: 71 series, latest `2026-04-01`, status `ok`
- `wb_commodity_indices`: 16 series
- `wb_commodity_factor_panel`: 371 variables x 34 countries
- `variable_meta`: commodity rows present with monthly freshness expectation
