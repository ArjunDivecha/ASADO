# ASADO Daily Extension — Implementation Status

**Date:** 2026-05-08  
**Status:** Stage A + B + C complete. All tables loaded, MCP tools live, orchestrator wired, Neo4j enriched with daily factor stats.

---

## What Was Built

### Database Tables (additive — existing monthly tables untouched)

| Table | Rows | Schema | Coverage |
|-------|------|--------|----------|
| `t2_factors_daily` | 32,340,392 | `(date, country, value, variable)` | 109 normalized _CS/_TS vars, 34 countries, 2000-01-01 → 2026-05-07 |
| `t2_levels_daily` | 13,698,294 | `(date, country, value, variable)` | 47 raw factor levels (PX_LAST, MCAP, RSI14 raw, REER raw, etc.), 34 countries, 2000-01-01 → 2026-04-21 |
| `gdelt_factors_daily` | 10,085,794 | `(date, country, value, variable)` | 75 normalized GDELT factors, 34 countries, 2015-06-24 → 2026-05-08 |
| `gdelt_raw_daily` | 955,473 | Wide (45 columns) | 249 ISO3 countries, 2015-02-18 → 2026-04-19. Off-universe entity bridge (Iran, Russia, etc.) |
| `factor_returns_daily` | 1,085,412 | `(date, factor, value, source)` | 157 factors from T2 + GDELT optimizers, 2 sources, 2000-01-01 → 2026-05-07 |
| `variable_meta` | 269 | See below | One row per variable across all daily tables |
| `daily_calendar` | 327,216 | `(date, country, is_trading_day)` | Derived from non-null `1DRet` observations. Handles Saudi Sun-Thu, China holidays, etc. |
| `t2_factors_monthly_from_daily` | VIEW | Same as t2_factors_daily | Last-trading-day-of-month snapshot for validation against `t2_master` |

### variable_meta Schema

```
variable, source_table, source_file, native_frequency, monthly_equivalent,
is_normalized (BOOLEAN), category, is_optimizer_selected (BOOLEAN)
```

- `monthly_equivalent`: maps daily names to monthly (e.g., `20DTR_CS` → `1MTR_CS`)
- `is_optimizer_selected`: 8 factors flagged: `120DTR_TS`, `120MA Signal_CS/TS`, `20DTR_CS/TS`, `REER_CS`, `RSI14_CS/TS`
- `category`: return, technical, volatility, valuation_fund, macro, commodity, fx, rates, size, risk, gdelt_signal, gdelt_raw, other

### MCP Tools Added (`asado_mcp_server.py`)

1. **`event_window(country, date, days_before=10, days_after=10, variables="optimizer", include_gdelt=True, include_factor_returns=True)`**
   - Daily event-study tool. Returns T2 factors, GDELT signals, factor returns, and trading calendar in a window around any date.
   - `variables` accepts: `"optimizer"` (8 factors), `"all"` (109), or comma-separated names.

2. **`daily_factor_series(country, variables, start_date, end_date, source="t2")`**
   - General time-series extraction. Sources: `t2`, `t2_levels`, `gdelt`, `gdelt_raw` (ISO3 for raw).

### Neo4j Factor Node Enrichment (`setup_neo4j.py`)

157 Factor nodes now carry daily performance properties (computed from `factor_returns_daily` during graph rebuild):

| Property | Meaning |
|----------|--------|
| `daily_return_latest` | Most recent daily return |
| `daily_return_date` | Date of that return |
| `daily_vol_30d` | Annualized vol (30-day window) |
| `daily_vol_252d` | Annualized vol (252-day window) |
| `daily_sharpe_252d` | Annualized Sharpe (252-day) |
| `daily_max_drawdown_252d` | Max drawdown over last 252 trading days |
| `daily_cum_return_30d` | Cumulative return (30-day) |
| `daily_cum_return_252d` | Cumulative return (1-year) |
| `daily_return_source` | `t2_optimizer_daily` or `gdelt_optimizer_daily` |
| `is_optimizer_selected` | `true` for the 8 strategy factors |

Example Cypher queries:

```cypher
// Top factors by daily Sharpe
MATCH (f:Factor)
WHERE f.daily_sharpe_252d IS NOT NULL
RETURN f.name, f.daily_sharpe_252d, f.daily_vol_252d, f.is_optimizer_selected
ORDER BY f.daily_sharpe_252d DESC LIMIT 10

// Factors connected to Turkey, ranked by Sharpe
MATCH (c:Country {t2_name: 'Turkey'})-[r:HAS_FACTOR_EXPOSURE]->(f:Factor)
WHERE f.daily_sharpe_252d IS NOT NULL
RETURN f.name, f.daily_sharpe_252d, r.value AS exposure, f.is_optimizer_selected
ORDER BY f.daily_sharpe_252d DESC LIMIT 10

// Optimizer-selected factors with their daily stats
MATCH (f:Factor)
WHERE f.is_optimizer_selected = true
RETURN f.name, f.daily_sharpe_252d, f.daily_vol_252d, f.daily_cum_return_252d
ORDER BY f.daily_sharpe_252d DESC
```

### Monthly Orchestrator

`build_daily_panels.py` is now wired into `monthly_update.py` as a step after DuckDB pass 2 + normalization. Runs with `--rebuild --no-backup`. The Neo4j graph rebuild (`setup_neo4j.py`) automatically picks up daily stats from `factor_returns_daily`.

---

## Source Files

| File | Size | Max Date |
|------|------|----------|
| `T2 Factor Timing Fuzzy Daily/Normalized_T2_MasterCSV.csv` | 1.6 GB | 2026-05-07 |
| `T2 Factor Timing Fuzzy Daily/T2MasterDaily.xlsx` | 116 MB | 2026-04-21 |
| `T2 Factor Timing Fuzzy Daily/T2_Optimizer.xlsx` | — | 2026-02-24 |
| `T2 Factor Timing Fuzzy Daily/T2_Optimizer_Top.xlsx` | 1.1 MB | 2026-02-22 |
| `GDELT Factor Timing Fuzzy Daily/T2-Factor-Timing-Daily/GDELT_Factors_MasterCSV.csv` | 556 MB | 2026-05-08 |
| `GDELT Factor Timing Fuzzy Daily/T2-Factor-Timing-Daily/GDELT_Optimizer.xlsx` | — | 2026-05-08 |
| `GDELT/data/panels/country_signal_daily.parquet` | 170 MB | 2026-04-19 |

---

## How to Test

### Quick health check

```bash
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
python scripts/build_daily_panels.py --check
```

### Query the daily tables directly (DuckDB)

```python
import duckdb
con = duckdb.connect('Data/asado.duckdb', read_only=True)

# Optimizer-selected factors for Brazil, last 5 days
con.execute("""
    SELECT t.date, t.variable, t.value
    FROM t2_factors_daily t
    WHERE t.country = 'Brazil'
      AND t.date >= DATE '2026-05-01'
      AND t.variable IN (SELECT variable FROM variable_meta WHERE is_optimizer_selected)
    ORDER BY t.variable, t.date
""").fetchdf()

# GDELT risk signals for Turkey around a specific event
con.execute("""
    SELECT date, variable, value
    FROM gdelt_factors_daily
    WHERE country = 'Turkey'
      AND date BETWEEN DATE '2018-08-08' AND DATE '2018-08-18'
      AND variable IN ('risk_fast_z_CS', 'sentiment_fast_z_CS', 'country_news_risk_raw_CS')
    ORDER BY variable, date
""").fetchdf()

# Daily factor returns — RSI14_CS portfolio performance
con.execute("""
    SELECT date, factor, value
    FROM factor_returns_daily
    WHERE factor = 'RSI14_CS' AND source = 't2_optimizer_daily'
      AND date >= DATE '2026-01-01'
    ORDER BY date
""").fetchdf()

# Variable metadata — what's optimizer-selected?
con.execute("SELECT * FROM variable_meta WHERE is_optimizer_selected").fetchdf()

# Trading calendar — Saudi Arabia (Sun-Thu)
con.execute("""
    SELECT date, is_trading_day
    FROM daily_calendar
    WHERE country = 'Saudi Arabia'
      AND date BETWEEN DATE '2024-01-01' AND DATE '2024-01-15'
    ORDER BY date
""").fetchdf()

# Off-universe entity: Iran GDELT signals
con.execute("""
    SELECT date, tone_mean, country_news_risk, country_news_sentiment
    FROM gdelt_raw_daily
    WHERE country_iso3 = 'IRN'
      AND date >= DATE '2024-01-01'
    ORDER BY date DESC
    LIMIT 20
""").fetchdf()

con.close()
```

### Test the MCP event_window tool (via Python)

```python
import sys
sys.path.insert(0, '/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO')
from scripts.asado_mcp_server import event_window, daily_factor_series

# Turkey 2018 lira crisis
result = event_window(country="Turkey", date="2018-08-13", days_before=5, days_after=5)
print(f"T2 factors: {result['t2_factors']['row_count']} rows")
print(f"GDELT factors: {result['gdelt_factors']['row_count']} rows")
print(f"Factor returns: {result['factor_returns']['row_count']} rows")
print(f"Trading days in window: {result['calendar']['trading_days']}")

# Daily series extraction
result2 = daily_factor_series(
    country="Saudi Arabia",
    variables="RSI14_CS,REER_CS",
    start_date="2024-01-01",
    end_date="2024-01-31",
    source="t2"
)
print(f"Series rows: {result2['result']['row_count']}")
```

### Rebuild from scratch

```bash
# Fast (skip xlsx levels): ~45s
python scripts/build_daily_panels.py --rebuild --no-backup --skip-levels

# Full (all tables including raw levels): ~105s
python scripts/build_daily_panels.py --rebuild --no-backup

# Validate daily-EOM vs monthly t2_master
python scripts/build_daily_panels.py --validate
```

---

## DB Size

| State | Size |
|-------|------|
| Before daily extension | 748 MB |
| After (full build) | 4.0 GB |

---

## Known Limitations / Not Yet Done

1. **`aggregation_rule` in variable_meta** — The plan mentioned tagging each variable with its monthly aggregation rule (last/mean/sum/first). Currently implicit in the `t2_factors_monthly_from_daily` view (uses last-trading-day).

2. **`freshness_expectation` in variable_meta** — How often each variable is expected to update. Nice-to-have metadata.

3. **`event_log` table** — Explicit timestamped geopolitical/macro events (FOMC, ECB, OPEC dates) for named-event lookups. Would pair with `event_window` to support queries like "show me Saudi around the last OPEC cut."

4. **`unified_panel_daily` view** — The monthly `unified_panel` is untouched. No daily equivalent created yet. Decision: should daily tables be unioned, or accessed individually via `event_window` / `daily_factor_series`?

5. **GDELT raw parquet stale** — `country_signal_daily.parquet` ends 2026-04-19 (needs upstream GDELT pipeline re-run to refresh).

6. **Daily country embeddings** — Country `state_embedding` still uses monthly z-scores. Could be recomputed from daily optimizer factors for intramonth similarity, but 8 factors may be too few dimensions.

---

## File Map

```
scripts/build_daily_panels.py    — Main build script (all daily table logic)
scripts/setup_neo4j.py           — Graph rebuild (now includes set_daily_factor_stats)
scripts/asado_mcp_server.py      — MCP server (event_window + daily_factor_series tools)
scripts/monthly_update.py        — Orchestrator (now includes daily panels step)
Data/asado.duckdb                — Single database (monthly + daily tables coexist)
Neo4j bolt://localhost:7687      — Factor nodes carry daily_* properties
```
