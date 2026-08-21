# Economic Surprise Lab Ingestion Report

**Date:** 2026-08-13  
**Author:** Arjun Divecha (Alpha-Hunting Loop)  
**Status:** Completed & Verified  

---

## 1. Summary

The complete point-in-time dataset from the **Economic Surprise Lab (ESL Phase R2)** has been ingested into ASADO and wired into the Alpha-Hunting Loop and Event-Study engine.

Unlike ASADO's previous economic surprise table (`eco_surprise_monthly`), which timestamped records to monthly observation reference periods (e.g. `2026-05-31`), this newly ingested layer retains the **exact Bloomberg announcement timestamp** (`release_date`) and **first knowable/tradeable timestamp** (`signal_date`), unlocking true `anchor=next_day` event studies and short-horizon dislocation tracking.

---

## 2. Ingested Data Profile

* **Source File:** `Data/work/loop/release_events.parquet` (424 KB, snapshot from Economic Surprise Lab)
* **Underlying Universe:** 31 countries, 213 Bloomberg ECO release tickers, 1996-11-01 to 2026-07-10
* **Event Volume:** 41,349 unique point-in-time release events
* **Macro Concepts Covered (10 families):**
  1. `cpi`: 8,984 events (31 countries)
  2. `core_cpi`: 2,797 events (17 countries)
  3. `ppi`: 4,235 events (20 countries)
  4. `gdp`: 1,785 events (17 countries)
  5. `unemp`: 4,562 events (22 countries)
  6. `employment`: 1,756 events (11 countries)
  7. `pmi`: 3,146 events (28 countries)
  8. `ip`: 4,831 events (22 countries)
  9. `retail_sales`: 5,007 events (21 countries)
  10. `consumer_confidence`: 4,246 events (20 countries)

---

## 3. Database Schema & Tables

All data is loaded into `Data/loop/asado_loop.duckdb`:

### `release_events_daily` (47,990 rows)
Full point-in-time event log broadcast across the 34 T2 equity country universe (United States broadcast to `['U.S.', 'NASDAQ', 'US SmallCap']`; China broadcast to `['ChinaA', 'ChinaH']`).

| Column | Type | Description |
|---|---|---|
| `release_date` | DATE | Exact public announcement date (`ECO_RELEASE_DT`) |
| `signal_date` | DATE | First tradeable date strictly $\ge$ release date |
| `reference_period` | DATE | Macro statistical observation end date |
| `country` | VARCHAR | T2 equity bucket name |
| `macro_country` | VARCHAR | Sovereign country name |
| `concept` | VARCHAR | Macro concept category |
| `ticker` | VARCHAR | Bloomberg ECO release ticker |
| `actual_first_print` | DOUBLE | Released statistic |
| `bn_survey_median` | DOUBLE | Pre-release economist survey median |
| `surprise` | DOUBLE | `actual_first_print - bn_survey_median` |
| `surprise_z` | DOUBLE | Winsorized ($\pm 3\sigma$) expanding-window $z$-score (min 12 obs) |
| `release_date_source`| VARCHAR | Provenance (`ECO_RELEASE_DT`, etc.) |

### `release_events_signals` (61,782 rows)
Tidy daily signal panel (`date`, `country`, `value`, `variable`, `source='derived'`) containing:
* `RELEASE_CPI_SURPRISE_Z`
* `RELEASE_CORE_CPI_SURPRISE_Z`
* `RELEASE_PPI_SURPRISE_Z`
* `RELEASE_GDP_SURPRISE_Z`
* `RELEASE_UNEMP_SURPRISE_Z`
* `RELEASE_EMPLOYMENT_SURPRISE_Z`
* `RELEASE_PMI_SURPRISE_Z`
* `RELEASE_IP_SURPRISE_Z`
* `RELEASE_RETAIL_SURPRISE_Z`
* `RELEASE_SENTIMENT_SURPRISE_Z`
* `RELEASE_GROWTH_SURPRISE_Z` (Directional growth composite)
* `RELEASE_INFL_SURPRISE_Z` (Inflation composite)

---

## 4. Pipeline & Analysis Integration

1. **Loader Script:** `scripts/loop/load_release_events.py`
   * Added as step `load_release_events` in `scripts/loop/loop_daily_job.py`.
   * Enforced in `config/governance_contract.yaml` and verified by `scripts/qa/check_loop_schema.py`.
2. **Family Registry:**
   * Prefix `RELEASE_` mapped to family `eco_surprise` in `config/family_registry.yaml`.
3. **Event-Study Presets (`scripts/loop/event_study.py`):**
   * `release_growth_hot` / `release_growth_cold` (`anchor=next_day`)
   * `release_inflation_hot` / `release_inflation_cold` (`anchor=next_day`)
   * `release_gdp_hot` / `release_gdp_cold` (`anchor=next_day`)
   * `release_sentiment_hot` / `release_sentiment_cold` (`anchor=next_day`)
   * `release_pmi_hot` / `release_pmi_cold` (`anchor=next_day`)
   * `release_cpi_hot` / `release_cpi_cold` (`anchor=next_day`)
4. **Automated Testing:**
   * Added `tests/loop/test_release_events.py` covering table existence, non-emptiness, PIT invariants (`signal_date >= release_date`), T2 country validity, and preset query execution.

---

## 5. Artifact Links

* Loader: [load_release_events.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/loop/load_release_events.py)
* Test Suite: [test_release_events.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/tests/loop/test_release_events.py)
* Parquet Source: [release_events.parquet](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/work/loop/release_events.parquet)
