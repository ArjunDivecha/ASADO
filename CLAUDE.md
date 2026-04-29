# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**ASADO** is a hybrid data collection and research platform for a 34-country macro universe. It:

- Collects **data from 26 free external sources** (EPU, GPR, BIS, OECD, World Bank, IMF, ECB, FRED, EIA, FAOSTAT, UNDP, ILOSTAT, ND-GAIN, OFAC, etc.)
- Integrates **17 Bloomberg Terminal variables** (sovereign bonds, CDS, OIS, breakevens, WIRP, ECFC, PMI, M2, ETF passive flows)
- Stores everything in **hybrid DuckDB + Neo4j** (analytical warehouse + knowledge graph)
- Builds **bilateral trade/banking/portfolio networks** from IMF IMTS, BIS LBS, IMF PIP/TIC
- Produces a **canonical normalized feature layer** (_CS / _TS variations + factor_panel view)
- Outputs **1.9M+ rows, 332 variables** across multiple panels

Core reference docs: `README.md`, `CLAUDE_CODE_BRIEF.md`, `Phase1_Data_Collection_Plan.md`

---

## Architecture & Key Concepts

### Four-Layer Data Model

1. **Raw Collectors** (scripts/collect_*.py) — Download from each data source, cache 24h, source-level merge
2. **Panel Assembly** (Data/processed/) — Tidy-format parquet panels per collector (external, extended, IMF, bilateral, macrostructure, bloomberg)
3. **Analytical Store** (DuckDB, Data/asado.duckdb) — Columns: date, country, value, variable, source; includes t2_master, unified_panel, feature_panel views
4. **Knowledge Graph** (Neo4j, bolt://localhost:7687) — Entity relationships: countries, factors, central banks, data sources, crises, sanctions; bilateral edges for trade/banking/portfolio; vector embeddings

### The 34-Country T2 Universe (Exact Names Required)

```
Australia, Brazil, Canada, Chile, ChinaA, ChinaH, Denmark, France, Germany,
Hong Kong, India, Indonesia, Italy, Japan, Korea, Malaysia, Mexico, NASDAQ,
Netherlands, Philippines, Poland, Saudi Arabia, Singapore, South Africa,
Spain, Sweden, Switzerland, Taiwan, Thailand, Turkey, U.K., U.S.,
US SmallCap, Vietnam
```

**Critical mapping rules:**
- "China" data → assign to **both ChinaA AND ChinaH**
- "United States" data → assign to **U.S., NASDAQ, AND US SmallCap**
- `config/country_mapping.json` has all source-specific codes (ISO-2, ISO-3, OECD, BIS, WB, EPU, GPR)

### Panel Format (Tidy — Long Format)

All output panels (and DuckDB feature tables) use this identical schema:

| Column | Type | Example |
|--------|------|---------|
| date | datetime | 2020-01-01 (first-of-month) |
| country | string | "Brazil" (T2 name exactly) |
| value | float64 | 189.37 (raw, NOT normalized) |
| variable | string | "EPU" or "BIS_Credit_GDP_Gap" |
| source | string | "epu" or "bis_credit" (lowercase) |

### Data Resilience Pattern

All collectors follow this safe-monthly-update flow:

1. **Load existing panel** from Data/processed/ (or create empty)
2. **Try to fetch fresh data** from each source (wrapped in try/except)
3. **Source-level merge** — for each source that succeeds, replace old data with fresh; for sources that fail, keep existing data unchanged
4. **Backup** the previous panel to Data/backups/{timestamp}/ before overwriting
5. **Record metadata** in Data/processed/run_history.json (last 24 runs)
6. **Print delta report** showing row count changes and date range extensions

This ensures **no data loss** even if multiple sources are temporarily unavailable.

### Bloomberg Prerequisites

- Bloomberg Terminal must be **logged in on Windows Parallels VM**
- Use the **OpusBloomberg conda env**: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv`
- Connection auto-detects Parallels IP, starts bbcomm, configures port forwarding → bbcomm.exe → Bloomberg Terminal
- Run Bloomberg scripts with: `conda run -p "...OpusBloomberg/.venv" python scripts/collect_bloomberg.py`
- If Bloomberg unavailable, use `--skip-bloomberg` flag in monthly_update.py

### Neo4j Prerequisites

- Must be running locally: `brew services start neo4j`
- Credentials: `neo4j` / `mythos2026`
- Accessible at: bolt://localhost:7687, web UI at http://localhost:7474
- Vector index on Country nodes: 34-dimensional cosine similarity index (state_embedding)

### MCP Server (Query Surface for Claude Desktop / Other Agents)

`scripts/asado_mcp_server.py` is a stdio MCP server that exposes the warehouse to MCP-speaking clients (primarily Claude Desktop). When the user references "use ASADO" or "ask the warehouse", this is the surface to reach for.

**Tools exposed:**

| Tool | Signature | Notes |
|---|---|---|
| `ask_asado(question)` | NL Q&A | Calls Anthropic Claude under the hood; needs `ANTHROPIC_API_KEY` in env. |
| `get_schema_summary(refresh_schema=False)` | DuckDB + Neo4j schema | Reads from `Data/cache/query_assistant/`. `refresh=True` forces rebuild. |
| `run_duckdb_sql(sql, max_rows=100)` | Read-only SQL | DuckDB connection opened read-only. |
| `run_neo4j_cypher(cypher, max_rows=100)` | Cypher | Not driver-level read-only — convention is read-only. |
| `get_country_profile(country)` | Bundled snapshot | Pass exact T2 names (`Brazil`, `ChinaA`, `U.S.`). |

**Setup is documented in `README.md` → "MCP Server — Query ASADO from Claude Desktop"** (config file location, JSON shape, example prompts, troubleshooting). Do not duplicate that here.

**For agent sessions writing code that touches the warehouse:** prefer `db_bridge.AsadoDB` for direct programmatic access (it's faster than going through MCP, and the MCP is for chat-driven use). The MCP is the right tool when the user is interactively asking questions in Claude Desktop, not when an agent is running a script.

**For agent sessions that need to know what's IN the warehouse:** read `docs/factor_reference.md`. It is auto-regenerated each monthly update from the schema cache and lists every DuckDB table, every variable per source (with frequency, country count, date range, normalization variants), and the full Neo4j graph map (every label, every relationship type, every index). This is the canonical "what does ASADO know" doc — designed to be parseable end-to-end.

**Cycle protection (matters for any new collector or builder):** the MCP and `db_bridge` both read from views like `feature_panel` and `unified_panel`. Optimizer outputs ingested by `collect_optimizer_returns.py` (factor_returns, factor_top20_membership, country_factor_attribution) are deliberately NOT unioned into those views — that's a structural guarantee against the optimizer-input/output cycle. If you find yourself adding `factor_returns` to `unified_panel` or `feature_panel`, stop and revisit — `Step Zero Build Econ.py` and `Step Zero Build GDELT.py` rely on the cycle being broken.

---

## Common Commands

### Monthly Update (Single Command — Runs Everything)

```bash
cd ASADO
source venv/bin/activate

# Full pipeline: collect all data, rebuild DuckDB, rebuild Neo4j, refresh query assistant
python scripts/monthly_update.py

# With options:
python scripts/monthly_update.py --skip-neo4j       # skip graph rebuild
python scripts/monthly_update.py --skip-bloomberg   # skip Bloomberg collection
python scripts/monthly_update.py --collectors-only  # data collection only, no DB rebuild
python scripts/monthly_update.py --db-only          # rebuild DBs from existing panels
python scripts/monthly_update.py --dry-run          # preview, no writes
```

**Total runtime: 6-8 minutes.** Log saved to `Data/logs/monthly_update_YYYY_MM_DD.log`.

### Individual Collectors

```bash
# Program 1: 7 core sources (EPU, GPR, BIS, OECD, World Bank, REER)
python scripts/collect_external.py               # normal run
python scripts/collect_external.py --force       # bypass 24h cache
python scripts/collect_external.py --dry-run     # preview

# Program 2: 12 extended sources (BIS rates, OECD BCI/CCI, ECB FX, ND-GAIN, ILOSTAT, etc.)
python scripts/collect_extended.py --force

# Program 3: 7 IMF datasets (CPI, WEO, BOP, rates, FX, labor, trade)
python scripts/collect_imf.py --force

# Program 4: Bilateral matrices (trade, banking, portfolio ownership)
python scripts/collect_bilateral.py                  # all three matrices
python scripts/collect_bilateral.py --trade-only    # trade only
python scripts/collect_bilateral.py --bank-only     # banking only

# Program 5: Macrostructure layer (fragility, debt-structure, ownership, backstop)
python scripts/collect_macrostructure.py --force

# Program 6: Bloomberg Terminal (requires OpusBloomberg env + Parallels)
conda run -p ".../OpusBloomberg/.venv" python scripts/collect_bloomberg.py
conda run -p ".../OpusBloomberg/.venv" python scripts/collect_bloomberg.py --force

# Database rebuilds:
python scripts/setup_duckdb.py                  # rebuild DuckDB from panels
python scripts/setup_duckdb.py --check          # verify existing DB
python scripts/build_normalized_panel.py        # rebuild normalized_panel + feature_panel
python scripts/setup_neo4j.py                   # rebuild Neo4j graph + edges
python scripts/setup_neo4j.py --check           # verify existing graph
python scripts/build_embeddings.py              # rebuild country-state vectors
python scripts/build_embeddings.py --dims 64   # use 64-d instead of default 128
python scripts/build_schema_registry.py         # refresh query-assistant schema cache
```

### Testing

```bash
# Test Bloomberg connectivity (uses OpusBloomberg env)
conda run -p ".../OpusBloomberg/.venv" python scripts/test_bloomberg_connection.py

# Check if Neo4j is running
brew services list | grep neo4j
```

---

## Code Patterns & Conventions

### Script Structure

Every collector/utility script follows this header format:

```python
"""
=============================================================================
SCRIPT NAME: [filename.py]
=============================================================================

INPUT FILES:
- [file]: [description]

OUTPUT FILES:
- [file]: [description]

VERSION: [version]
LAST UPDATED: YYYY-MM-DD
AUTHOR: [Author Name]

DESCRIPTION:
[2-3 sentences about what the script does]

DEPENDENCIES:
- [package list from requirements.txt]

USAGE:
  python scripts/[name].py              [normal run]
  python scripts/[name].py --force      [cache bypass / full refresh]
  python scripts/[name].py --dry-run    [preview, no writes]

NOTES:
- [Important implementation details, runtime, data notes]
=============================================================================
"""
```

This is **mandatory** for all new/modified scripts. Use it as context for future readers.

### Import Organization

```python
# Standard library
import argparse, json, logging, os, subprocess, sys, time, shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Third-party
import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Local
from scripts.db_bridge import AsadoDB  # if needed
```

### Path Management

All paths relative to BASE_DIR (repo root):

```python
BASE_DIR = Path(__file__).resolve().parent.parent  # for scripts/ scripts
DATA_DIR = BASE_DIR / "Data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
CONFIG_DIR = BASE_DIR / "config"
CACHE_DIR = DATA_DIR / "cache"

# Auto-create directories:
for d in [RAW_DIR, CACHE_DIR, PROCESSED_DIR]:
    d.mkdir(parents=True, exist_ok=True)
```

### Logging Setup

```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(CACHE_DIR / f"collection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger(__name__)
```

### Error Handling (Per-Source Try/Except)

Every collector has **try/except around each source**, never around the entire pipeline:

```python
def collect_source_x():
    try:
        # fetch data
        df = fetch_from_api(url)
        # transform, validate
        return df
    except requests.RequestException as e:
        logger.error(f"[Source X] Network error: {e}")
        return None  # or empty DataFrame
    except Exception as e:
        logger.error(f"[Source X] Unexpected error: {e}")
        return None

# In main:
for source in sources:
    df = collect_source_x()
    if df is not None and not df.empty:
        panel = merge_source(panel, df)
    else:
        logger.warning(f"[Source X] Skipped — will preserve existing data")
```

This ensures **one source failure never breaks the entire run**.

### Caching & Timestamping

- **Raw downloads**: Data/raw/ with 24h expiry (check file mtime)
- **3 retries** on download failure, then log and continue
- **Timestamped backups** before every panel overwrite: Data/backups/{YYYY_MM_DD_HHMMSS}/
- **Run history**: Data/processed/run_history.json (keeps last 24 runs)

```python
def cache_is_fresh(filepath, hours=24):
    if not filepath.exists():
        return False
    return (datetime.now() - datetime.fromtimestamp(filepath.stat().st_mtime)).total_seconds() < hours * 3600

# Backup before overwrite:
import shutil
from datetime import datetime
timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
backup_dir = DATA_DIR / "backups" / timestamp
shutil.copytree(PROCESSED_DIR, backup_dir, dirs_exist_ok=True)
```

### Date Alignment Rules

All data converted to **first-of-month** format before storage:

| Original Frequency | Conversion | Example |
|---|---|---|
| Daily | Last business day of month | 2020-01-31 → 2020-01-01 |
| Monthly | First day of month | 2020-01-15 → 2020-01-01 |
| Quarterly | First day of quarter-end month | Q1 2020 → 2020-03-01 |
| Annual | December 1 of year | 2020 → 2020-12-01 |

```python
from pandas.tseries.offsets import MonthBegin
df['date'] = pd.to_datetime(df['date']).dt.to_period('M').dt.to_timestamp()
# or for first-of-month:
df['date'] = df['date'].dt.to_period('M').dt.to_timestamp()
```

### Database Bridge (Unified Query Interface)

Import and use AsadoDB for DuckDB + Neo4j queries:

```python
from scripts.db_bridge import AsadoDB

with AsadoDB() as db:
    # SQL on DuckDB (returns DataFrame)
    df = db.query_panel("SELECT * FROM feature_panel WHERE country = 'Brazil'")
    
    # Cypher on Neo4j (returns list of dicts)
    records = db.query_graph("MATCH (c:Country {t2_name: 'Turkey'}) RETURN c.t2_name, c.state_embedding")
    
    # Country profile (all factors + relationships)
    profile = db.country_profile("Brazil")
    
    # Factor snapshot (all countries at one date)
    snapshot = db.factor_snapshot("BIS_Credit_GDP_Gap")
```

---

## Dependencies & Virtual Environment

```bash
# Create/activate venv (already exists in repo)
python3 -m venv venv
source venv/bin/activate

# Install from requirements.txt
pip install -r requirements.txt
```

**Key packages:**
- `pandas, numpy` — data manipulation
- `requests, openpyxl, xlrd` — downloading/parsing APIs, Excel
- `wbgapi` — World Bank data
- `sdmx1` — SDMX API client (OECD, BIS, IMF, ECB, ILO)
- `duckdb` — analytical database
- `neo4j` — knowledge graph client
- `scikit-learn` — PCA for embeddings
- `pyarrow` — parquet I/O
- `fastapi, uvicorn, sse-starlette` — MCP server for query assistant
- `mcp[cli]` — MCP framework

**Bloomberg (separate env):**
```bash
conda run -p "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv" python scripts/collect_bloomberg.py
```
Includes: `blpapi, pandas, pyarrow, numpy` pre-installed.

---

## Database Schema Overview

### DuckDB Tables (Data/asado.duckdb)

Core surfaces all use tidy schema: `(date DATE, country VARCHAR, value DOUBLE, variable VARCHAR, source VARCHAR)`

| Table | Rows | Updated | Purpose |
|-------|------|---------|---------|
| `external_factors` | 112K | Monthly | Program 1 output (EPU, GPR, BIS, OECD, WB, REER) |
| `extended_factors` | 96K | Monthly | Program 2 output (rates, BCI/CCI, FX, ND-GAIN, etc.) |
| `imf_factors` | 107K | Monthly | Program 3 output (CPI, WEO, BOP, trade, etc.) |
| `gdelt_panel` | 407K | Monthly | GDELT news/tone/risk signals |
| `macrostructure_factors` | 55K | Monthly | Program 5 (fragility, debt, ownership, backstop) |
| `bloomberg_factors` | 98K | Monthly | Program 6 (bonds, CDS, OIS, PMI, etc.) |
| `normalized_panel` | Generated | Monthly | Canonical _CS / _TS normalized features |
| `feature_panel` | Generated | Monthly | Query-facing union (most commonly queried) |
| `unified_panel` | 2.5M | Generated | Raw cross-source analytical warehouse |
| `bilateral_portfolio_matrix` | 56K | Quarterly | Portfolio ownership (reporter-counterparty) |
| `t2_master` | 1.1M | On request | T2 Master canonical panel |
| `country_reference` | 34 | Monthly | ISO3 → ASADO country mapping |

**Vector index:**
- `countryStateIndex` (Neo4j) — 34-dimensional cosine similarity on Country.state_embedding

### Neo4j Node Types & Edge Types

**Nodes:**
- **Country** (34) — t2_name, iso3, dm_em, region, currency_code, state_embedding (34d)
- **Factor** (332) — name, category, source
- **CentralBank** (31), **DataSource** (30), **CrisisEvent** (9), **SanctionsProgram** (6), **Commodity** (4)

**Edges:**
- **HAS_FACTOR_EXPOSURE** (3.7K) — Country → Factor (latest values)
- **TRADES_WITH** (1.0K) — Country → Country (>$100M bilateral trade)
- **HAS_BANKING_EXPOSURE_TO** (0.7K) — Country → Country (cross-border claims)
- **HAS_CRISIS_HISTORY** (123), **SUBJECT_TO** (34), **HAS_CENTRAL_BANK** (34), **EXPORT_EXPOSED_TO** (31)

---

## Configuration

### Country Mapping (config/country_mapping.json)

Central Rosetta Stone mapping 34 T2 countries to source-specific codes:

```json
{
  "t2_countries": [
    {
      "t2_name": "Brazil",
      "iso3": "BRA",
      "iso2": "BR",
      "oecd": "BRA",
      "bis": "BR",
      "wb": "BRA",
      "epu_col": "Brazil",
      "gpr": "BR",
      ...
    },
    ...
  ]
}
```

Used by **all collectors** for mapping source codes to T2 country names. Always check/update when adding new sources.

### Environment Variables (API Keys)

Read from env vars or `~/.../AAA Backup/.env.txt`:

```
FRED_API_KEY=your_key_from_fred.stlouisfed.org
EIA_API_KEY=your_key_from_eia.gov
```

If missing, sources are skipped gracefully (no hard failure).

---

## Testing & Verification

### Quick Verifications

```bash
# Test Bloomberg (if Parallels available)
conda run -p ".../OpusBloomberg/.venv" python scripts/test_bloomberg_connection.py

# Verify DuckDB integrity
python scripts/setup_duckdb.py --check

# Verify Neo4j integrity
python scripts/setup_neo4j.py --check

# Dry-run any collector
python scripts/collect_external.py --dry-run
```

### Data Quality Checks (Built Into Collectors)

Each collector runs post-collection checks:

1. All 34 countries present (logs missing coverage)
2. No duplicate (date, country, variable) rows
3. Date range sanity (e.g., EPU before 2005, BIS before 2010)
4. No values >10x historical std dev
5. Coverage matrix printed to log

---

## Workflows & Scenarios

### Scenario: Monthly Update Routine
```bash
source venv/bin/activate
python scripts/monthly_update.py
# Runs all 11 stages, logs to Data/logs/monthly_update_YYYY_MM_DD.log
# Total time: 6-8 minutes
```

### Scenario: One Source Failed, Need to Rerun Just That Source
```bash
source venv/bin/activate
python scripts/collect_external.py --force    # bypass cache, re-fetch all
# Or just:
python scripts/collect_external.py            # use cache if fresh
# Old data for that source is replaced only if new fetch succeeds
```

### Scenario: Rebuild DuckDB Without Collecting New Data
```bash
python scripts/setup_duckdb.py           # reload existing panels
python scripts/build_normalized_panel.py # refresh normalized features
```

### Scenario: Rebuild Neo4j Without Collecting New Data
```bash
python scripts/setup_neo4j.py    # reload from existing DuckDB
python scripts/build_embeddings.py
```

### Scenario: Bloomberg Not Available, Skip It
```bash
python scripts/monthly_update.py --skip-bloomberg
# All other stages run normally; existing Bloomberg data preserved
```

---

## Important Rules

1. **Always use first-of-month dates** in output (2020-01-01, not 2020-01-15)
2. **Always use exact T2 country names** (Brazil, not "BR" or "BRA")
3. **Never silently drop data** — log why and preserve what you can
4. **Wrap each source in try/except**, never the whole pipeline
5. **Always backup before overwrite** — Data/backups/{timestamp}/
6. **Document all scripts** with the mandatory header format (INPUT/OUTPUT/VERSION/DEPENDENCIES/USAGE/NOTES)
7. **Use tidy/long format** for all panels: (date, country, value, variable, source)
8. **Test Bloomberg connection** before assuming it works in monthly_update.py
9. **Neo4j must be running** (brew services start neo4j) before running graph-related scripts
10. **Preserve data resilience** — one source failure must not break the month's run

---

## Key Files to Know

| File | Purpose |
|------|---------|
| `scripts/monthly_update.py` | Single-command orchestrator — run this for monthly updates |
| `scripts/db_bridge.py` | AsadoDB class — unified query interface for DuckDB + Neo4j |
| `config/country_mapping.json` | 34-country code mappings (ISO, OECD, BIS, WB, EPU, GPR, etc.) |
| `README.md` | Full project documentation with data specs, sources, schemas |
| `CLAUDE_CODE_BRIEF.md` | Quick-reference implementation spec |
| `Phase1_Data_Collection_Plan.md` | Comprehensive PRD with all 22 sources + database design |
| `Data/processed/run_history.json` | Metadata log of last 24 runs (success/failure per source) |
| `Data/logs/` | Timestamped logs from each run |

---

**Last Updated:** 2026-04-19  
**Architecture:** 34-country macro universe, 26 free sources + 17 Bloomberg variables, hybrid DuckDB + Neo4j  
**Total Data:** 1.9M+ rows, 332 variables, monthly update cycle ~6-8 minutes
