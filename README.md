# ASADO — Country Data Collection & Research Platform

Collects macro/governance/risk/climate/trade data from **26 free external sources** (including 7 IMF datasets) **plus 17 Bloomberg Terminal variables** (sovereign bonds, CDS, breakevens, OIS rates, WIRP, ECFC, PMI, M2, MIPD), aligns to the 34-country T2 Master universe, stores everything in a **hybrid DuckDB + Neo4j database** with **bilateral trade/banking network edges** and **country-state vector embeddings** for similarity search.

## Project Structure

```
ASADO/
├── Data/
│   ├── [T2 Master.xlsx]                  # Read from .../AAA Backup/Transformer/
│   ├── [Normalized_T2_MasterCSV.csv]     # Read from .../AAA Backup/Transformer/
│   ├── [GDELT_Factors_MasterCSV.csv]     # Read from .../A Complete/T2 GDELT/
│   ├── asado.duckdb                      # DuckDB analytical database (75.5 MB)
│   ├── raw/                              # Cached downloads (24h expiry)
│   ├── processed/                        # Output panels + catalogs + run history
│   │   ├── external_factors_panel.parquet # Program 1 output (112K rows, 35 vars)
│   │   ├── extended_factors_panel.parquet # Program 2 output (77K rows, 51 vars)
│   │   ├── imf_factors_panel.parquet     # Program 3 output (107K rows, 26 vars)
│   │   ├── bilateral_trade_matrix.parquet  # Program 4 output (899 trade pairs)
│   │   ├── bilateral_banking_matrix.parquet # Program 4 output (582 banking pairs)
│   │   ├── bloomberg_factors_panel.parquet # Program 5 output (67K rows, 17 vars)
│   │   └── ...catalogs, CSV copies, run history
│   ├── backups/                          # Timestamped backups before overwrites
│   └── cache/                            # Log files
├── scripts/
│   ├── monthly_update.py                 # ONE-COMMAND monthly update (runs everything below)
│   ├── collect_external.py               # Program 1 — 7 core sources
│   ├── collect_extended.py               # Program 2 — 12 extended sources
│   ├── collect_imf.py                    # Program 3 — 7 IMF datasets
│   ├── collect_bilateral.py              # Program 4 — bilateral trade + banking matrices
│   ├── collect_bloomberg.py              # Program 5 — Bloomberg Terminal (bonds, CDS, OIS, WIRP, ECFC, PMI, M2)
│   ├── setup_duckdb.py                   # DuckDB schema + data loader
│   ├── setup_neo4j.py                    # Neo4j knowledge graph builder
│   ├── build_embeddings.py               # Country-state PCA vectors + Neo4j vector index
│   └── db_bridge.py                      # AsadoDB unified query interface
├── config/
│   └── country_mapping.json              # 34-country Rosetta Stone (ISO codes, etc.)
├── venv/                                 # Python virtual environment
├── requirements.txt
├── Bloomberg_Country_Data_Catalog.md      # Complete Bloomberg country data reference
├── Bloomberg_Priority_List.md            # Gap analysis + prioritization for Bloomberg data
├── Phase1_Data_Collection_Plan.md        # Full PRD with all 19 sources + database plan
├── PRD_Phase1_Program1_External_Data.md  # Original PRD for Program 1
├── T2.Readme.md                          # T2 Master documentation
├── GDelt Readme.md                       # GDELT pipeline documentation
└── factor-timing-lit-review.md           # Academic literature survey
```

## Quick Start — Monthly Update (One Command)

```bash
cd ASADO
source venv/bin/activate

# Full monthly update — collects all data, rebuilds DuckDB + Neo4j
python scripts/monthly_update.py
```

This single command runs the entire pipeline:

| Stage | Script | What it does | Runtime |
|-------|--------|-------------|---------|
| 1 | `collect_external.py --force` | 7 core sources (EPU, GPR, BIS, OECD, World Bank) | ~25s |
| 2 | `collect_extended.py --force` | 12 extended sources (BIS rates, OECD BCI/CCI, ECB, ILOSTAT, FRED, EIA) | ~45s |
| 3 | `collect_imf.py --force` | 7 IMF datasets (CPI, WEO, BOP, rates, FX, labor, trade) | ~70s |
| 4 | `collect_bilateral.py` | Bilateral trade (IMF IMTS) + banking claims (BIS LBS) | ~120s |
| 5 | `collect_bloomberg.py` | Bloomberg Terminal data (bonds, CDS, OIS, WIRP, ECFC, PMI, M2, breakevens) | ~140s |
| 6 | `setup_duckdb.py` | Rebuild DuckDB analytical database | ~2s |
| 7 | `setup_neo4j.py` | Rebuild Neo4j knowledge graph + trade/banking edges | ~9s |
| 8 | `build_embeddings.py` | Country-state PCA vectors + Neo4j vector index | ~3s |

**Total runtime: ~6 minutes.** Log file saved to `Data/logs/monthly_update_YYYY_MM_DD.log`.

> **Bloomberg prerequisite:** Stage 5 requires Bloomberg Terminal running on the Parallels Windows 11 VM. If Bloomberg is not available, add `--skip-bloomberg` to skip it — all other stages run normally.

### Options

```bash
python scripts/monthly_update.py --skip-neo4j      # skip Neo4j + embeddings if not running
python scripts/monthly_update.py --skip-bloomberg   # skip Bloomberg (no terminal access)
python scripts/monthly_update.py --collectors-only  # data collection only, no DB rebuild
python scripts/monthly_update.py --db-only          # rebuild DBs from existing panels
python scripts/monthly_update.py --dry-run          # preview, no writes
```

### Running Individual Scripts

```bash
python scripts/collect_external.py --force    # Program 1 only
python scripts/collect_extended.py --force    # Program 2 only
python scripts/collect_imf.py --force         # Program 3 only
python scripts/collect_bilateral.py           # Program 4 (trade + banking)
python scripts/collect_bilateral.py --trade-only   # trade matrix only
python scripts/collect_bilateral.py --bank-only    # banking matrix only

# Program 5 — Bloomberg (requires Bloomberg Terminal on Parallels VM)
conda run -p ".../OpusBloomberg/.venv" python scripts/collect_bloomberg.py
conda run -p ".../OpusBloomberg/.venv" python scripts/collect_bloomberg.py --force

python scripts/setup_duckdb.py                # rebuild DuckDB
python scripts/setup_duckdb.py --check        # verify existing database
python scripts/setup_neo4j.py                 # rebuild Neo4j graph
python scripts/setup_neo4j.py --check         # verify existing graph
python scripts/build_embeddings.py            # rebuild country-state vectors
python scripts/build_embeddings.py --dims 64  # use 64-d instead of 128
```

## Data Resilience

All collectors are designed for safe monthly re-runs:

1. **Loads existing panel** from `Data/processed/`
2. **Fetches fresh data** from all sources
3. **Source-level merge** — for each source that succeeds, its old data is replaced with fresh data. For any source that fails (e.g., server down), the existing data for that source is **preserved unchanged**.
4. **Backs up** the previous panel to `Data/backups/` with a timestamp before overwriting
5. **Records run metadata** in run history JSON (keeps last 24 runs)
6. **Prints a delta report** showing row count changes and date range extensions

## Latest Run Results (2026-04-13)

### Program 1: Core Sources (collect_external.py)

| Source | Status | Countries | Variables | Date Range |
|--------|--------|-----------|-----------|------------|
| EPU | OK | 21/34 | 1 | 1985-01 → 2025-11 |
| GPR | OK | 34/34 | 4 | 1985-01 → 2026-03 |
| BIS Credit Gap | OK | 31/34 | 1 | 2000-03 → 2025-09 |
| BIS Property | OK | 31/34 | 1 | 2000-03 → 2025-12 |
| OECD CLI | OK | 20/34 | 1 | 2000-01 → 2026-03 |
| World Bank | OK | 33/34 | 26 | 2000-12 → 2025-12 |
| BIS REER | OK | 33/34 | 1 | 2000-01 → 2026-02 |

**Total: 112,633 rows, 35 variables, 34 countries, 7/7 sources OK**

### Program 2: Extended Sources (collect_extended.py)

| Source | Status | Countries | Variables | Date Range |
|--------|--------|-----------|-----------|------------|
| BIS Policy Rates | OK | 26/34 | 1 | 2000-01 → 2026-04 |
| BIS Debt Service | OK | 28/34 | 1 | 2000-03 → 2025-09 |
| OECD BCI | OK | 20/34 | 1 | 2000-01 → 2026-03 |
| OECD CCI | OK | 22/34 | 1 | 2000-01 → 2026-03 |
| ECB FX | OK | 31/34 | 24 | 2000-01 → 2026-03 |
| ND-GAIN | OK | 32/34 | 3 | 1995-12 → 2023-12 |
| ILOSTAT | OK | 34/34 | 2 | 2000-12 → 2025-12 |
| UNDP HDI | OK | 33/34 | 4 | 1990-12 → 2023-12 |
| OFAC Sanctions | OK | 34/34 | 2 | 2026-04 (snapshot) |
| FAOSTAT | OK | 33/34 | 5 | 2010-12 → 2024-12 |
| FRED | OK | 34/34 | 6 | 2000-01 → 2026-03 |
| EIA | OK | 34/34 | 1 | 2000-12 → 2019-12 |

**Total: 77,123 rows, 51 variables, 34 countries, 12/12 sources OK**

### Program 3: IMF Datasets (collect_imf.py)

| Dataset | Status | Countries | Variables | Date Range |
|---------|--------|-----------|-----------|------------|
| CPI | OK | 33/34 | 2 | 2000-01 → 2026-03 |
| WEO | OK | 34/34 | 6 | 1980-12 → 2030-12 |
| BOP_AGG | OK | 34/34 | 4 | 2005-12 → 2024-12 |
| MFS_IR (Interest Rates) | OK | 25/34 | 4 | 2000-01 → 2026-03 |
| ER (Exchange Rates) | OK | 29/34 | 1 | 2000-01 → 2026-03 |
| LS (Labor Stats) | OK | 12/34 | 1 | 2000-01 → 2026-01 |
| ITG (Trade in Goods) | OK | 34/34 | 8 | 2000-01 → 2026-01 |

**Total: 106,989 rows, 26 variables, 34 countries, 7/7 datasets OK**

API: SDMX 3.0 REST at `api.imf.org` — no API key required.

### Program 5: Bloomberg Terminal (collect_bloomberg.py)

| Category | Status | Countries | Variables | Date Range |
|----------|--------|-----------|-----------|------------|
| Bond Yields (2Y, 5Y, 10Y, 30Y) | OK | 26/34 | 4 | 2000-01 → 2026-03 |
| CDS Spreads (5Y) | OK | 15/34 | 1 | 2000-10 → 2026-03 |
| Breakevens (10Y) | OK | 6/34 | 1 | 2000-01 → 2026-03 |
| OIS 10Y Swap Rates | OK | 17/34 | 1 | 2000-01 → 2026-03 |
| WIRP Implied Rates | OK | 25/34 | 1 | 2000-01 → 2026-03 |
| ECFC Consensus (GDP, CPI) | OK | 26/34 | 2 | 2010-01 → 2026-03 |
| PMI (Manufacturing, Services) | OK | 19/34 | 2 | 2020-10 → 2026-03 |
| M2 Money Supply YoY | OK | 13/34 | 1 | 2000-01 → 2026-03 |
| DDIS Debt/GDP | OK | 1/34 | 1 | 2011-03 → 2025-12 |
| Yield Curve Slope (derived) | OK | 23/34 | 1 | 2000-01 → 2026-03 |
| MIPD Default Prob (derived) | OK | 15/34 | 1 | 2000-10 → 2026-03 |
| Z-Spread vs OIS (derived) | OK | 16/34 | 1 | 2000-01 → 2026-03 |

**Total: 66,656 rows, 17 variables, 34 countries, 12/13 categories OK**

Bloomberg connection: macOS Python → TCP:8194 → Parallels Windows 11 VM → bbcomm.exe → Bloomberg Terminal. Uses the OpusBloomberg library at `/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg`.

### Combined Total: 1,910,775 rows, 332 variables across 26 free sources + Bloomberg Terminal

## Output Files

| File | Description |
|------|-------------|
| `Data/processed/external_factors_panel.parquet` | Program 1 — core 7 sources |
| `Data/processed/external_factors_panel.csv` | Program 1 CSV copy |
| `Data/processed/extended_factors_panel.parquet` | Program 2 — extended 12 sources |
| `Data/processed/extended_factors_panel.csv` | Program 2 CSV copy |
| `Data/processed/imf_factors_panel.parquet` | Program 3 — 7 IMF datasets |
| `Data/processed/imf_factors_panel.csv` | Program 3 CSV copy |
| `Data/processed/bilateral_trade_matrix.parquet` | Program 4 — 899 bilateral trade pairs |
| `Data/processed/bilateral_banking_matrix.parquet` | Program 4 — 582 banking exposure pairs |
| `Data/processed/bloomberg_factors_panel.parquet` | Program 5 — 67K rows, 17 Bloomberg variables |
| `Data/processed/bloomberg_factors_panel.csv` | Program 5 CSV copy |
| `Data/processed/bloomberg_variable_catalog.csv` | Program 5 variable metadata |
| `Data/processed/external_variable_catalog.csv` | Program 1 variable metadata |
| `Data/processed/extended_variable_catalog.csv` | Program 2 variable metadata |
| `Data/processed/imf_variable_catalog.csv` | Program 3 variable metadata |

## Panel Format (matches T2 Master CSV)

| Column | Type | Example |
|--------|------|---------|
| date | datetime | 2020-01-01 |
| country | string | U.S. |
| value | float64 | 189.37 |
| variable | string | EPU |
| source | string | epu |

## Variables Collected (332 total)

### Program 1: Core Sources (35 variables)

**EPU (1):** `EPU`
**GPR (4):** `GPR`, `Global_GPR`, `Global_GPR_Threat`, `Global_GPR_Act`
**BIS (3):** `BIS_Credit_GDP_Gap`, `BIS_Property_Price`, `BIS_REER`
**OECD (1):** `OECD_CLI`
**World Bank (26):** Governance (6), Macro (8), Demographics (6), Reserves (3), Climate (2), Structural (1)

### Program 2: Extended Sources (51 variables)

**BIS Additional (2):** `BIS_Policy_Rate` (central bank rates), `BIS_DSR_Private` (debt service ratio)
**OECD Sentiment (2):** `OECD_BCI` (business confidence), `OECD_CCI` (consumer confidence)
**ECB FX (24):** `ECB_FX_{CCY}_EUR` — exchange rates vs EUR for 22 currencies + EUR=1 for eurozone
**ND-GAIN (3):** `NDGAIN_Score`, `NDGAIN_Vulnerability`, `NDGAIN_Readiness`
**ILOSTAT (2):** `ILO_Unemployment_Rate`, `ILO_LFP_Rate`
**UNDP HDI (4):** `UNDP_HDI`, `UNDP_IHDI` (inequality-adjusted), `UNDP_GDI` (gender development), `UNDP_GII` (gender inequality)
**OFAC (2):** `OFAC_Sanctions_Count`, `OFAC_Sanctioned` (binary flag)
**FAOSTAT (5):** `FAO_Import_Dependency`, `FAO_Self_Sufficiency`, `FAO_Trade_Openness`, `FAO_Terms_of_Trade`, `FAO_AgExport_GDP_Share`
**FRED (6):** `FRED_VIX`, `FRED_UST_10Y`, `FRED_UST_2Y`, `FRED_Yield_Curve_10Y2Y`, `FRED_USD_Broad_Index`, `FRED_HY_OAS`
**EIA (1):** `EIA_Petroleum_Consumption_TBPD`

### Program 3: IMF Datasets (26 variables)

**CPI (2):** `IMF_CPI_Index` (monthly level), `IMF_CPI_Inflation_YoY` (computed year-over-year %)
**WEO Forecasts (6):** `IMF_WEO_GDP_Growth`, `IMF_WEO_Inflation`, `IMF_WEO_CA_GDP`, `IMF_WEO_Debt_GDP`, `IMF_WEO_Unemployment`, `IMF_WEO_Population`
**BOP Aggregates (4):** `IMF_BOP_Current_Account`, `IMF_BOP_Direct_Investment_Net`, `IMF_BOP_Portfolio_Investment_Net`, `IMF_BOP_Financial_Account_Bal`
**Interest Rates (4):** `IMF_Money_Market_Rate`, `IMF_Discount_Rate`, `IMF_Govt_Bond_Yield`, `IMF_TBill_Rate`
**Exchange Rates (1):** `IMF_XRate_LCU_per_USD`
**Labor (1):** `IMF_Employment_Index`
**Trade (8):** `IMF_Exports_USD`, `IMF_Imports_USD`, `IMF_Trade_Balance_USD` (computed), `IMF_Trade_Openness_USD` (computed), `IMF_Export_Price_Index`, `IMF_Import_Price_Index`, `IMF_Exports_YoY`, `IMF_Imports_YoY`

### Program 5: Bloomberg Terminal (17 variables)

**Sovereign Bonds (4):** `BBG_Govt_Bond_2Y`, `BBG_Govt_Bond_5Y`, `BBG_Govt_Bond_10Y`, `BBG_Govt_Bond_30Y`
**CDS (1):** `BBG_CDS_5Y`
**Inflation (1):** `BBG_Breakeven_10Y`
**Rates (2):** `BBG_OIS_10Y`, `BBG_ZSpread_OIS_10Y` (derived: bond yield minus OIS rate)
**Monetary Policy (2):** `BBG_WIRP_ImpliedRate` (central bank implied policy rate), `BBG_M2_YoY` (M2 money supply growth)
**Activity (2):** `BBG_PMI_Manufacturing`, `BBG_PMI_Services` (S&P Global/Markit PMI)
**Consensus Forecasts (2):** `BBG_ECFC_GDP` (with fallback to actual GDP YoY), `BBG_ECFC_CPI` (survey consensus)
**Fiscal (1):** `BBG_Debt_GDP_Ratio` (sovereign debt-to-GDP)
**Sovereign Risk (1):** `BBG_MIPD_5Y` (derived: market-implied default probability from CDS)
**Yield Curve (1):** `BBG_Yield_Curve_10Y2Y` (derived: 10Y-2Y slope)

## Country Coverage Notes

- **Taiwan** — missing from World Bank (not a WB member), ND-GAIN
- **Vietnam** — missing from BIS REER
- **Hong Kong** — missing from ND-GAIN (not indexed as sovereign)
- **EPU** — 21/34 countries (dataset only publishes ~22 countries)
- **OECD CLI/BCI/CCI** — OECD members + key partners only (~20-22/34)
- **BIS Policy Rates** — 26/34 (not all central banks publish through BIS)
- **FRED/EIA** — global indicators broadcast to all 34 countries; US-specific yields mapped to US/NASDAQ/US SmallCap

## Caching & Resilience

- Raw downloads cached in `Data/raw/` with 24-hour expiry (`--force` bypasses)
- BIS SDMX queries are re-fetched each run (no local cache for API responses)
- Re-running within 24h reuses cached EPU/GPR Excel files
- If a source is down, existing data for that source is preserved (source-level merge)
- Timestamped backups saved before every overwrite in `Data/backups/`
- Run history tracked in `Data/processed/run_history.json` (last 24 runs)

## API Keys

Program 2 uses API keys for FRED and EIA (read from env vars or `/Users/arjundivecha/Dropbox/AAA Backup/.env.txt`):

| Key | Source | Get it at |
|-----|--------|-----------|
| `FRED_API_KEY` | FRED (St. Louis Fed) | https://fred.stlouisfed.org/docs/api/api_key.html |
| `EIA_API_KEY` | EIA (US Energy Info) | https://www.eia.gov/opendata/register.php |

If a key is missing, that source is skipped gracefully — all other sources still run.

## Dependencies

```
pandas numpy requests openpyxl pyarrow wbgapi sdmx1 xlrd tqdm duckdb neo4j scikit-learn
```

Bloomberg requires the separate OpusBloomberg conda environment with `blpapi` installed:
```
blpapi pandas pyarrow numpy  # in OpusBloomberg/.venv
```

## Architecture Notes

- BIS data uses SDMX API (bulk CSV URLs at data.bis.org/static/bulk/ return 404 as of April 2026)
- OECD BCI/CCI use the new `sdmx.oecd.org` REST endpoint with `csvfilewithlabels` format
- ECB FX uses per-currency SDMX queries via `data-api.ecb.europa.eu`
- ND-GAIN provides a ZIP archive with gain/vulnerability/readiness CSVs
- ILOSTAT uses SDMX CSV endpoints at `sdmx.ilostat.org`
- UNDP HDI is a bulk CSV download from `hdr.undp.org`
- FAOSTAT uses bulk ZIP download of Trade_CropsLivestockIndicators
- WB governance indicators use source 3 (WGI database) with `GOV_WGI_` prefix codes
- WB CO2 per capita uses EDGAR-based `EN.GHG.CO2.PC.CE.AR5` (old IEA-based code `EN.ATM.CO2E.PC` retired)
- WB Ease of Business (`IC.BUS.EASE.XQ`) discontinued 2021 — removed
- IPU, WITS skipped — APIs blocked or require complex authentication (April 2026)
- IMF data uses the SDMX 3.0 REST API at `api.imf.org/external/sdmx/3.0/` — no API key required
- IMF WEO includes forward-looking forecasts through 2030
- IMF IMTS (formerly DOTS) provides bilateral merchandise trade via SDMX 3.0 — 30/31 reporters covered
- BIS Locational Banking Statistics (LBS) provides cross-border banking claims via CSV API at stats.bis.org — 21/31 reporting countries
- Country-state embeddings use PCA-compressed z-scored factor values (34d vectors from 332 variables) stored on Neo4j Country nodes with a cosine similarity vector index
- Bloomberg data uses the OpusBloomberg library for BLPAPI access via macOS → Parallels → Windows VM → Bloomberg Terminal. Runs in a dedicated conda environment (`OpusBloomberg/.venv`) with `blpapi`. Connection auto-detects VM IP, starts bbcomm, configures port forwarding and firewall rules.
- Bloomberg collector outputs both pulled data (bond yields, CDS, OIS, breakevens, WIRP, ECFC, PMI, M2) and derived signals (MIPD from CDS via hazard rate model, Z-spread = bond yield minus OIS rate, yield curve slope = 10Y minus 2Y). ECFC GDP uses a fallback strategy: tries consensus forecast tickers first (`ECGD[CC]`), falls back to actual GDP YoY (`EHGD[CC]Y`) if consensus ticker fails.

## Database Architecture (Phase 1B)

### DuckDB — Analytical Store (`Data/asado.duckdb`, 72.5 MB)

Columnar database for fast time-series analytics. Contains six tables + one unified view:

| Table | Rows | Variables | Countries | Date Range |
|-------|------|-----------|-----------|------------|
| `t2_master` | 1,142,672 | 111 | 34 | 2000-02 → 2026-04 |
| `external_factors` | 112,633 | 35 | 34 | 1985-01 → 2026-03 |
| `extended_factors` | 77,123 | 51 | 34 | 1990-12 → 2026-04 |
| `gdelt_panel` | 404,702 | 93 | 34 | 2015-09 → 2026-04 |
| `imf_factors` | 106,989 | 26 | 34 | 1980-12 → 2030-12 |
| `bloomberg_factors` | 66,656 | 17 | 34 | 2000-01 → 2026-03 |
| **`unified_panel`** (view) | **1,910,775** | **332** | 34 | 1980-12 → 2030-12 |

All tables share the tidy schema `(date DATE, country VARCHAR, value DOUBLE, variable VARCHAR)`. Indexes on `(country, date)` and `(variable)`.

### Neo4j — Knowledge Graph (bolt://localhost:7687)

Graph database representing entity relationships with bilateral trade/banking networks and vector embeddings. **446 nodes, 6,522 edges.**

**Node types:**
| Label | Count | Key Properties |
|-------|-------|----------------|
| Country | 34 | t2_name, iso3, dm_em, region, currency_code, state_embedding (34d vector) |
| Factor | 332 | name, category, source |
| CentralBank | 31 | name, country_iso3 |
| DataSource | 30 | name, url, frequency, api_type |
| CrisisEvent | 9 | name, start_date, end_date, type |
| SanctionsProgram | 6 | name, active |
| Commodity | 4 | name, category |

Bloomberg factors are categorized as: `rates` (bonds, OIS, Z-spread, yield curve), `sovereign_risk` (CDS, MIPD), `inflation` (breakevens), `monetary_policy` (WIRP, M2), `macro_forecast` (ECFC GDP/CPI), `activity` (PMI Manufacturing/Services), `fiscal` (Debt/GDP).

**Edge types:**
| Relationship | Count | Description |
|-------------|-------|-------------|
| HAS_FACTOR_EXPOSURE | 3,752 | Country → Factor (latest values) |
| TRADES_WITH | 1,079 | Country → Country (bilateral trade >$100M, IMF IMTS) |
| DATA_AVAILABLE_FROM | 765 | Country → DataSource (coverage) |
| HAS_BANKING_EXPOSURE_TO | 704 | Country → Country (cross-border claims, BIS LBS) |
| HAS_CRISIS_HISTORY | 123 | Country → CrisisEvent |
| SUBJECT_TO | 34 | Country → SanctionsProgram |
| HAS_CENTRAL_BANK | 34 | Country → CentralBank |
| EXPORT_EXPOSED_TO | 31 | Country → Commodity |

**Vector Index:**
| Index | Dimensions | Similarity | Purpose |
|-------|-----------|------------|---------|
| countryStateIndex | 34 | cosine | Country-state similarity search |

### Python Bridge (`scripts/db_bridge.py`)

Unified query interface — import `AsadoDB` in any script:

```python
from scripts.db_bridge import AsadoDB

with AsadoDB() as db:
    # SQL queries on DuckDB (returns DataFrame)
    df = db.query_panel("SELECT * FROM unified_panel WHERE country = 'Brazil' LIMIT 10")

    # Cypher queries on Neo4j (returns list of dicts)
    records = db.query_graph("MATCH (c:Country)-[:HAS_CRISIS_HISTORY]->(e) RETURN c.t2_name, e.name")

    # Country profile (all factors + all graph relationships)
    profile = db.country_profile("Turkey")

    # Cross-sectional factor snapshot (all countries at one date)
    snapshot = db.factor_snapshot("BIS_Credit_GDP_Gap")

    # Refresh factor exposure edges from latest DuckDB data
    db.refresh_factor_edges()

    # Find countries most similar to Turkey (vector search)
    similar = db.query_graph("""
        MATCH (c:Country {t2_name: 'Turkey'})
        CALL db.index.vector.queryNodes('countryStateIndex', 6, c.state_embedding)
        YIELD node, score WHERE node <> c
        RETURN node.t2_name AS country, score ORDER BY score DESC
    """)

    # Top trading partners of Brazil
    partners = db.query_graph("""
        MATCH (c:Country {t2_name: 'Brazil'})-[t:TRADES_WITH]->(p)
        RETURN p.t2_name AS partner, t.exports_usd, t.imports_usd, t.trade_share_pct
        ORDER BY t.total_trade_usd DESC LIMIT 10
    """)

    # Banking exposure network for a country
    exposure = db.query_graph("""
        MATCH (c:Country {t2_name: 'U.K.'})-[b:HAS_BANKING_EXPOSURE_TO]->(p)
        RETURN p.t2_name AS counterparty, b.claims_usd_millions, b.share_of_total_claims_pct
        ORDER BY b.claims_usd_millions DESC LIMIT 10
    """)
```

### Neo4j Prerequisites

Neo4j must be running locally (installed via Homebrew):
```bash
brew services start neo4j      # start service (bolt://localhost:7687, web UI at http://localhost:7474)
brew services stop neo4j       # stop service
```
Credentials: `neo4j` / `mythos2026`

## Skipped Sources (April 2026)

The following sources from the original PRD were evaluated and intentionally skipped due to access blockers. Existing data from other sources provides adequate coverage for each gap.

| Source | What it would add | Why skipped | Covered by |
|--------|-------------------|-------------|------------|
| UN Comtrade | Bilateral trade flows | API key registration broken (email never arrives) | IMF IMTS bilateral trade (899 pairs in Neo4j), IMF ITG aggregate trade |
| ACLED | Armed conflict events & fatalities | Requires API key + email registration | GPR index (geopolitical risk), GDELT sentiment (news-based conflict signals) |
| IPU Parline | Parliamentary/election calendar data | API returning 403 Forbidden (April 2026) | OFAC sanctions data, WGI governance indicators |
| WITS | Tariff rates & non-tariff barriers | API returning 403 Forbidden (April 2026) | IMF trade data, World Bank trade openness, BIS REER (competitiveness) |
