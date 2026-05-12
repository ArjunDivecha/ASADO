# ASADO — Country Data Collection & Research Platform

Collects macro/governance/risk/climate/trade data from **26 free external sources** (including 7 IMF datasets) **plus 28 Bloomberg Terminal variables** (sovereign bonds, CDS, breakevens, OIS, WIRP, ECFC, PMI, M2, ETF passive-flow, and related derived signals), aligns to the 34-country T2 Master universe, and stores everything in a **hybrid DuckDB + Neo4j database** with a **raw warehouse, canonical normalized feature layer, bilateral trade/banking/portfolio edges, daily-frequency factor panels (58M+ rows),** and **country-state vector embeddings** for similarity search.

## Project Structure

```
ASADO/
├── Data/
│   ├── [T2 Master.xlsx]                  # Read from .../A Complete/T2 Factor Timing Fuzzy/
│   ├── [Normalized_T2_MasterCSV.csv]     # Read from .../A Complete/T2 Factor Timing Fuzzy/
│   ├── [GDELT_Factors_MasterCSV.csv]     # Preferred external source from .../A Complete/T2 GDELT/
│   ├── asado.duckdb                      # DuckDB analytical database (~4 GB with daily extension)
│   ├── raw/                              # Cached downloads (24h expiry)
│   ├── processed/                        # Output panels + catalogs + run history
│   │   ├── external_factors_panel.parquet # Program 1 output (112K rows, 35 vars)
│   │   ├── extended_factors_panel.parquet # Program 2 output (97K rows, 51 vars)
│   │   ├── imf_factors_panel.parquet     # Program 3 output (107K rows, 26 vars)
│   │   ├── gdelt_panel_snapshot.parquet  # Repo-local fallback when external GDELT CSV is absent
│   │   ├── macrostructure_panel.parquet  # Program 5 output (75K rows, fragility/sticky-capital/central-bank/backstop layer)
│   │   ├── bilateral_trade_matrix.parquet  # Program 4 output (899 trade pairs)
│   │   ├── bilateral_banking_matrix.parquet # Program 4 output (582 banking pairs)
│   │   ├── bilateral_portfolio_matrix.parquet # Program 4 output (historical portfolio ownership matrix)
│   │   ├── bloomberg_factors_panel.parquet # Program 6 output (98K rows incl. ETF passive layer)
│   │   └── ...catalogs, CSV copies, run history
│   ├── backups/                          # Timestamped backups before overwrites
│   └── cache/                            # Log files
├── scripts/
│   ├── monthly_update.py                 # ONE-COMMAND monthly update (runs everything below)
│   ├── collect_external.py               # Program 1 — 7 core sources
│   ├── collect_extended.py               # Program 2 — 12 extended sources
│   ├── collect_imf.py                    # Program 3 — 7 IMF datasets
│   ├── collect_bilateral.py              # Program 4 — bilateral trade + banking + portfolio ownership
│   ├── collect_macrostructure.py         # Program 5 — macrostructure / fragility / central-bank footprint / backstop panel
│   ├── collect_bloomberg.py              # Program 6 — Bloomberg Terminal (bonds, CDS, OIS, WIRP, ECFC, PMI, M2)
│   ├── setup_duckdb.py                   # DuckDB raw warehouse loader (monthly)
│   ├── build_daily_panels.py             # Daily extension: T2 + GDELT + optimizer returns (58M rows)
│   ├── build_event_log.py                # Event registry: YAML → event_log table (124 curated events)
│   ├── build_normalized_panel.py         # Canonical _CS/_TS feature layer + feature_panel view
│   ├── setup_neo4j.py                    # Neo4j knowledge graph builder
│   ├── build_embeddings.py               # Country-state PCA vectors + Neo4j vector index
│   ├── build_schema_registry.py          # Query-assistant schema cache / access guide
│   └── db_bridge.py                      # AsadoDB unified query interface
├── docs/
│   └── DAILY_EXTENSION_STATUS.md         # Daily extension implementation status + test guide
├── config/
│   ├── country_mapping.json              # 34-country Rosetta Stone (ISO codes, etc.)
│   └── event_log_seed.yaml              # Hand-curated event registry (124 dated events)
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

# Full monthly update — collects all data, rebuilds DuckDB + normalization layer + Neo4j
python scripts/monthly_update.py
```

This single command runs the entire pipeline:

| Stage | Script | What it does | Runtime |
|-------|--------|-------------|---------|
| 1 | `collect_external.py --force` | 7 core sources (EPU, GPR, BIS, OECD, World Bank) | ~25s |
| 2 | `collect_extended.py --force` | 12 extended sources (BIS rates, OECD BCI/CCI, ECB, ILOSTAT, FRED, EIA) | ~45s |
| 3 | `collect_imf.py --force` | 7 IMF datasets (CPI, WEO, BOP, rates, FX, labor, trade) | ~70s |
| 4 | `collect_bilateral.py` | Bilateral trade + banking + portfolio ownership matrices | ~120s |
| 5 | `collect_macrostructure.py --force` | Macrostructure fragility, debt-structure, sticky-capital, central-bank footprint, and backstop layer | ~60s |
| 6 | `collect_bloomberg.py` | Bloomberg Terminal data (bonds, CDS, OIS, WIRP, ECFC, PMI, M2, ETF passive layer) | ~140s |
| 7 | `setup_duckdb.py` | Rebuild the raw DuckDB analytical warehouse | ~3s |
| 8 | `build_normalized_panel.py` | Build canonical `_CS` / `_TS` features and `feature_panel` | ~12s |
| 8b | `build_daily_panels.py` | Load daily T2 + GDELT + optimizer returns (58M rows) | ~105s |
| 8c | `build_predmkt_panel.py` | Build Stage 2 prediction-market layer (Kalshi + Polymarket snapshots + composites) | ~5-30s |
| 8d | `build_event_log.py` | Load curated event registry (146 events, 8 categories) | <1s |
| 9 | `setup_neo4j.py` | Rebuild Neo4j knowledge graph + trade/banking/portfolio edges (requires event_log) | ~9s |
| 10 | `build_embeddings.py` | Country-state PCA vectors + Neo4j vector index | ~3s |
| 11 | `build_schema_registry.py` | Refresh schema cache + access guide for the query assistant | ~1s |

**Total runtime: ~8-10 minutes** (including daily panels). Log file saved to `Data/logs/monthly_update_YYYY_MM_DD.log`.

> **Bloomberg prerequisite:** Stage 6 requires Bloomberg Terminal running on the Parallels Windows 11 VM. If Bloomberg is not available, add `--skip-bloomberg` to skip it — all other stages run normally.

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
python scripts/collect_bilateral.py           # Program 4 (trade + banking + portfolio ownership)
python scripts/collect_bilateral.py --trade-only   # trade matrix only
python scripts/collect_bilateral.py --bank-only    # banking matrix only

# Program 6 — Bloomberg (requires Bloomberg Terminal on Parallels VM)
conda run -p ".../OpusBloomberg/.venv" python scripts/collect_bloomberg.py
conda run -p ".../OpusBloomberg/.venv" python scripts/collect_bloomberg.py --force

python scripts/setup_duckdb.py                # rebuild DuckDB
python scripts/setup_duckdb.py --check        # verify existing database
python scripts/build_daily_panels.py          # full daily extension rebuild (~105s)
python scripts/build_daily_panels.py --skip-levels  # fast daily build (skip raw xlsx, ~45s)
python scripts/build_daily_panels.py --check  # verify daily tables
python scripts/build_predmkt_panel.py         # Stage 2 prediction-market build
python scripts/build_predmkt_panel.py --check # validate registry + inspect predmkt tables
python scripts/build_predmkt_panel.py --stats # print predmkt table counts/date ranges
python scripts/build_event_log.py             # rebuild event_log table from YAML
python scripts/build_event_log.py --check     # validate YAML without writing
python scripts/build_event_log.py --stats     # show category/severity breakdown
python scripts/build_normalized_panel.py      # rebuild normalized_panel + feature_panel
python scripts/build_normalized_panel.py --check
python scripts/setup_neo4j.py                 # rebuild Neo4j graph
python scripts/setup_neo4j.py --check         # verify existing graph
python scripts/build_embeddings.py            # rebuild country-state vectors
python scripts/build_embeddings.py --dims 64  # use 64-d instead of 128
python scripts/build_schema_registry.py       # refresh query-assistant schema cache
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

**Total: 107,298 rows, 26 variables, 34 countries, 7/7 datasets OK**

API: SDMX 3.0 REST at `api.imf.org` — no API key required.

### Program 6: Bloomberg Terminal (collect_bloomberg.py)

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

**Total: 98,129 rows, 28 variables, 34 countries, 12/13 categories OK**

The 28 Bloomberg variables include the ETF passive-flow / creation-redemption family:

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

Bloomberg connection: macOS Python → TCP:8194 → Parallels Windows 11 VM → bbcomm.exe → Bloomberg Terminal. Uses the OpusBloomberg library at `/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg`.

### Warehouse Snapshot (2026-04-19 rebuild)

- `macrostructure_panel`: 75,120 rows, 26 variables
- `unified_panel`: 2,561,094 raw factor rows across 421 variables
- `normalized_panel`: 778,984 normalized rows across 285 generated variables
- `feature_panel`: 3,340,078 total rows across 706 raw + normalized variables

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
| `Data/processed/macrostructure_panel.parquet` | Program 5 — 75K rows, 26 macrostructure variables |
| `Data/processed/macrostructure_panel.csv` | Program 5 CSV copy |
| `Data/processed/macrostructure_variable_catalog.csv` | Program 5 variable metadata |
| `Data/processed/macrostructure_formula_catalog.json` | Program 5 formula metadata |
| `Data/processed/bloomberg_factors_panel.parquet` | Program 6 — 98K rows, 28 Bloomberg variables |
| `Data/processed/bloomberg_factors_panel.csv` | Program 6 CSV copy |
| `Data/processed/bloomberg_variable_catalog.csv` | Program 6 variable metadata |
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

## Variable Families

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

### Program 5: Macrostructure Panel (26 variables)

Includes IMF FSI bank-fragility indicators, World Bank QPSD debt-structure mix, OECD institutional-depth and sticky-capital proxies, portfolio-context variables, and transparent derived policy / official-sector measures such as `MS_CentralBank_BalanceSheet_GDP`, `MS_CentralBank_Claims_on_Government_Pct_GDP`, `MS_CentralBank_SovDebt_Share`, `MS_Reserve_Adequacy`, `MS_Swap_Line_Access`, `MS_Policy_Backstop`, and `MS_Investor_Base_Fragility`.

### Program 6: Bloomberg Terminal (28 variables)

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
- Macrostructure Program 5 now includes an IMF MFS_CBS-based central-bank footprint layer: total assets / GDP, claims on government / GDP, and a transparent sovereign-debt-share proxy that prefers QPSD debt coverage and falls back to WEO debt / GDP when needed.

## Database Architecture (Phase 1B)

### DuckDB — Analytical Store (`Data/asado.duckdb`, ~4 GB)

Columnar database for fast time-series analytics. Core surfaces currently include:

#### Monthly Tables

| Table / View | Rows | Date Range | Primary Use |
|-------|------|------------|------------|
| `t2_master` | 1,188,810 | 2000-02-01 → 2026-04-01 | Canonical normalized T2 panel |
| `t2_raw` | 474,636 | 2000-02-01 → 2026-04-01 | Raw T2 factor levels from the workbook |
| `country_reference` | generated monthly | n/a | Canonical ISO3 -> ASADO country mapping surface for bilateral joins |
| `external_factors` | 112,633 | 1985-01-01 → 2026-03-01 | Program 1 free-source macro / risk / structural panel |
| `extended_factors` | 96,604 | 1990-12-01 → 2026-04-01 | Program 2 extended free-source panel |
| `gdelt_panel` | 407,864 | 2015-09-01 → 2026-05-01 | Country-level media / tone / risk panel, including partial current month labels |
| `imf_factors` | 107,298 | 1980-12-01 → 2031-12-01 | IMF CPI, WEO, BOP, FX, labor, trade, and FSI-derived series |
| `macrostructure_factors` | 75,120 | 1995-03-01 → 2026-04-01 | Fragility, debt-structure, ownership, sticky-capital, central-bank footprint, and policy-backstop layer |
| `bloomberg_factors` | 98,129 | 1975-12-01 → 2026-04-01 | Bloomberg sovereign rates/credit/macro plus ETF passive-flow layer |
| `normalized_panel` | 778,984 | 1990-12-01 → 2026-04-01 | Canonical `_CS` / `_TS` normalized feature layer |
| `feature_panel` (view) | 3,340,078 | 1975-12-01 → 2031-12-01 | Primary query-facing union of raw + normalized factor rows |
| `bilateral_portfolio_matrix` | 56,786 | 1997-12-01 → 2026-02-01 | Reporter-counterparty portfolio ownership matrix |
| **`unified_panel`** (view) | **2,561,094** | **1975-12-01 → 2031-12-01** | **Raw cross-source analytical warehouse** |

#### Daily Tables (added 2026-05-08 via `build_daily_panels.py`)

| Table / View | Rows | Date Range | Primary Use |
|-------|------|------------|------------|
| `t2_factors_daily` | 32,340,392 | 2000-01-01 → 2026-05-07 | 109 normalized _CS/_TS daily factors, 34 countries |
| `t2_levels_daily` | 13,698,294 | 2000-01-01 → 2026-04-21 | 47 raw factor levels (PX_LAST, MCAP, RSI14, REER, etc.) |
| `gdelt_factors_daily` | 10,085,794 | 2015-06-24 → 2026-05-08 | 75 normalized GDELT daily factors, 34 countries |
| `gdelt_raw_daily` | 955,473 | 2015-02-18 → 2026-04-19 | 249-country raw GDELT signals (off-universe bridge) |
| `factor_returns_daily` | 1,085,412 | 2000-01-01 → 2026-05-07 | 157 optimizer factor returns (T2 + GDELT) |
| `variable_meta` | 269 | n/a | Variable metadata: frequency, category, optimizer-selected |
| `daily_calendar` | 327,216 | 2000-01-01 → 2026-05-07 | Per-country trading day calendar |
| `t2_factors_monthly_from_daily` (view) | — | — | Last-trading-day-of-month snapshot for validation |

#### Prediction-Market Tables (added 2026-05-08 via `build_predmkt_panel.py`)

| Table | Primary Grain | Primary Use |
|-------|---------------|-------------|
| `predmkt_daily` | `(snapshot_date, platform, market_id, outcome_id)` | Daily implied probabilities + liquidity + stale/resolution flags |
| `predmkt_market_meta` | `(platform, market_id)` | Curated category tags + rules/resolution metadata |
| `predmkt_outcome_meta` | `(platform, market_id, outcome_id)` | Outcome labels and scalar threshold metadata |
| `predmkt_country_spillover` | `(platform, market_id, country, channel)` | Off-universe spillover bridge with elasticity/channel/confidence |
| `predmkt_resolutions` | `(platform, market_id)` | Resolution archive for calibration tracking |
| `predmkt_signals_daily` | `(snapshot_date, signal_name, country)` | Derived daily composites (macro + geopolitical + country spillovers) |

Factor tables and views (`t2_master`, source panels, `unified_panel`, `normalized_panel`, `feature_panel`) share the tidy schema `(date DATE, country VARCHAR, value DOUBLE, variable VARCHAR)`. Daily tables follow the same schema. `country_reference` and `bilateral_portfolio_matrix` are helper surfaces used for ISO mapping and ownership joins. Indexes cover factor tables plus `country_reference` and the main bilateral ownership keys.

### Neo4j — Knowledge Graph (bolt://localhost:7687)

Graph database representing entity relationships with bilateral trade/banking networks and vector embeddings. **446 nodes, 6,522 edges.**

**Node types:**
| Label | Count | Key Properties |
|-------|-------|----------------|
| Country | 34 | t2_name, iso3, dm_em, region, currency_code, state_embedding (34d vector) |
| Factor | 1,651 | name, category, source, daily_sharpe_252d, daily_vol_252d, daily_cum_return_252d, is_optimizer_selected |
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
    df = db.query_panel("SELECT * FROM feature_panel WHERE country = 'Brazil' LIMIT 10")

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

## Factor Catalog & Graph Map

For comprehensive per-variable detail (every variable in every panel, with frequency, country count, date range, normalization variants) plus the full Neo4j graph map (every node label, every relationship, every property, every index), see:

**→ [`docs/factor_reference.md`](docs/factor_reference.md)** *(auto-regenerated each monthly update from `Data/cache/query_assistant/`)*

That file is intended to be read end-to-end by an AI agent that needs to know what the warehouse is capable of answering. The summary below covers shape and counts; the reference covers every variable.

### Snapshot

- **DuckDB tables / views:** 14 (8 raw factor panels + 6 derived views/aux tables)
- **Distinct variables in `unified_panel`:** 2,641 (raw 223 · `_CS` 1,209 · `_TS` 1,209)
- **Country universe:** 34 (T2 names — see [`config/country_mapping.json`](config/country_mapping.json))
- **Neo4j:** 7 node labels (`Country` 34, `Factor` 2929, `CentralBank` 31, `DataSource` 37, `Commodity` 4, `CrisisEvent` 9, `SanctionsProgram` 6) · 9 relationship types (`HAS_FACTOR_EXPOSURE`, `TRADES_WITH`, `HAS_BANKING_EXPOSURE_TO`, `HAS_CRISIS_HISTORY`, `SUBJECT_TO`, `HAS_CENTRAL_BANK`, `EXPORT_EXPOSED_TO`, `DATA_AVAILABLE_FROM`, `HOLDS_PORTFOLIO_OF`)

### Data families covered

| Family | Source tables | Examples |
|---|---|---|
| **Equity factors** (Bloomberg-driven, T2 pipeline) | `t2_master`, `t2_raw` | Best PE, Trailing PE, Earnings Yield, Best ROE, BEST EPS, MCAP, 120MA Signal, RSI14, 360 Day Vol, momentum series |
| **External macro** | `external_factors` | EPU, GPR/Global GPR, BIS Credit/GDP Gap, BIS Property Price, BIS REER, OECD CLI, World Bank governance + structural |
| **Extended macro** | `extended_factors` | BIS policy/debt-service rates, ECB FX (24 pairs), FRED (UST 2Y/10Y, VIX, USD index, HY OAS), ND-GAIN climate, OFAC sanctions, UNDP HDI/IHDI/GII, ILO labor, EIA energy, FAO trade, OECD BCI/CCI |
| **IMF** | `imf_factors` | CPI, WEO macro projections, balance of payments, exchange rates, trade flows, money market and discount rates, employment |
| **Macrostructure** | `macrostructure_factors` | Bank capital adequacy / liquidity / NPLs, public-debt structure (creditor / currency / maturity buckets), sticky-capital pension/insurance/household, central-bank balance-sheet metrics, swap-line access |
| **Bloomberg market** | `bloomberg_factors` | Sovereign bonds, CDS, OIS, breakevens, WIRP implied policy rates, ECFC consensus, PMI, M2, ETF passive layer (`MS_*`) |
| **GDELT news / sentiment** | `gdelt_panel` (2,313 vars) | Theme attention (~516), GCAM emotional dimensions (~450), event aggregates (~120), core tone signals (metronome / risk / sentiment / attention), all monthly |
| **Optimizer outputs** (added 2026-04-29) | `factor_returns`, `factor_top20_membership`, `country_factor_attribution` | Top-20% portfolio monthly returns per factor (Econ, T2 Style, GDELT optimizers) + country-level membership + joinable attribution view |
| **Bilateral networks** | `bilateral_portfolio_matrix` | Reporter-counterparty portfolio holdings (IMF PIP + U.S. TIC). Trade and banking edges live in Neo4j as `[:TRADES_WITH]` / `[:HAS_BANKING_EXPOSURE_TO]`. |

### How to use the catalog

- **Programmatic** — read `Data/cache/query_assistant/variable_catalog.json` directly. It has `variable_metadata`, `variable_aliases`, frequency, freshness, normalization tags, and forecast/sparse flags for every variable.
- **From an agent (Claude Desktop)** — call `get_schema_summary` via the MCP server (next section) to get the same payload.
- **Human-readable** — `docs/factor_reference.md` rendered as markdown.

---

## Returns Source Of Truth

Returns are ASADO's outcome layer. Performance, event, winner/loser, attribution, and "what happened" questions should anchor on these surfaces.

**Country returns — one canonical source (T2, 34 countries):**

- Monthly: `feature_panel` rows where `source = 't2'`, variables `1MRet`, `3MRet`, `6MRet`, `9MRet`, `12MRet`.
- Daily: `t2_factors_daily`, variables `1DRet`, `5DRet`, `20DRet`, `60DRet`, `120DRet`.

The `1MRet` rows under `source = 'gdelt'` in `feature_panel`, and the `1DRet` rows in `gdelt_factors_daily`, are **bit-exact duplicates** of the T2 returns copied into the GDELT panel as the dependent variable for the GDELT optimizer. They are aliases — not a second country return source.

**Factor portfolio returns** (top-20%-of-countries returns from the optimizer pipelines — these are portfolio returns, not raw factor levels):

- Monthly: `factor_returns` with sources `econ_optimizer`, `t2_optimizer`, `gdelt_optimizer`.
- Daily: `factor_returns_daily` with sources `t2_optimizer_daily`, `gdelt_optimizer_daily`.

**Country-factor attribution:** `country_factor_attribution` joins `factor_top20_membership ⨝ factor_returns` and gives `contribution = weight × factor_return` per (country, factor, month). This is top-20% bucket attribution, not a full portfolio decomposition.

**Cycle guardrail:** Optimizer return outputs (`factor_returns`, `factor_returns_daily`, `factor_top20_membership`, `country_factor_attribution`) must never be unioned into `feature_panel` or `unified_panel` — those are explanatory/input surfaces the optimizer consumes. `scripts/qa/validate_returns_first.py` enforces this.

**Catalog:** `Data/cache/query_assistant/returns_catalog.json` (regenerated by `scripts/build_schema_registry.py`).

**Tools:** Use the deterministic MCP tools below (`country_returns`, `factor_return_series`, `country_factor_attribution`, `return_leaders`, plus `event_window` with `return_summary`) before writing ad hoc SQL.

---

## MCP Server — Query ASADO from Claude Desktop

`scripts/asado_mcp_server.py` is a stdio MCP server that exposes the ASADO warehouse to Claude Desktop (and any other MCP-speaking client) as a small read-only tool surface. Once registered, you can ask Claude things like *"What's the latest BIS credit-gap reading for Brazil?"* and it will run the query against the live DuckDB / Neo4j stack and answer.

### What it exposes

| Tool | Purpose |
|---|---|
| `ask_asado(question)` | Natural-language Q&A over the warehouse. Calls Anthropic Claude under the hood (requires `ANTHROPIC_API_KEY` in env); plans the SQL/Cypher and returns the answer with cited rows. |
| `get_schema_summary(refresh_schema=False)` | Returns the cached DuckDB + Neo4j schema (table descriptions, sample variables, label/relationship counts). Set `refresh_schema=True` to force a rebuild via `build_schema_registry.py`. |
| `run_duckdb_sql(sql, max_rows=100)` | Executes a read-only SQL query against `Data/asado.duckdb` and returns the result as a frame payload. The DuckDB connection is opened read-only — writes will fail. |
| `run_neo4j_cypher(cypher, max_rows=100)` | Executes a Cypher query against the local Neo4j (bolt://localhost:7687). |
| `get_country_profile(country)` | Bundled per-country snapshot: latest factor values + all graph relationships (trade, banking, central bank, sanctions, crises). Pass exact T2 country names, e.g., `"Brazil"`, `"ChinaA"`, `"U.S."`. |
| `event_window(country, date, ...)` | Daily event-study: returns T2 optimizer factors, GDELT signals, factor returns, trading calendar, and a `return_summary` block (pre/post/window country return + factor return leaders/laggards) around any date. |
| `events_in_window(start_date, end_date, ...)` | Search the curated event registry (146 events) by date range, category, subcategory, country, severity, or tags. Supports `strict_country=True` for country-specific-only events. Chain with `event_window` for date-anchored studies. |
| `daily_factor_series(country, variables, start_date, end_date, source)` | General daily time-series extraction. Sources: `t2`, `t2_levels`, `gdelt`, `gdelt_raw`, plus return surfaces `t2_returns`, `gdelt_returns`, `factor_returns_daily`. |
| `country_returns(countries, frequency, horizon, ...)` | Deterministic country return rows (T2 canonical, 34 countries). Monthly horizons: 1/3/6/9/12 MRet; daily: 1/5/20/60/120 DRet. Supports `rank='best'/'worst'`. |
| `factor_return_series(factors, frequency, source, ...)` | Factor portfolio return series from optimizer pipelines. Monthly sources: `econ_optimizer` / `t2_optimizer` / `gdelt_optimizer`. Daily: `t2_optimizer_daily` / `gdelt_optimizer_daily`. |
| `country_factor_attribution(country, source, date, ...)` | Per-country top-20%-bucket attribution (weight × factor_return) for one month. |
| `return_leaders(scope, frequency, direction, ...)` | Leaderboard wrapper: `scope='country'` or `'factor'`, `direction='best'/'worst'`. |
| `predmkt_snapshot(category, date=today)` | Prediction-market snapshot for one category with probabilities, liquidity, and rules metadata. |
| `country_signal_now(country, channels=None, date=today)` | Country-level prediction-market risk/opportunity decomposition through spillover channels. |
| `event_market_set(keyword)` | Keyword search over curated prediction markets ranked by recent liquidity. |

### Setup — register in Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` and add an entry under `mcpServers`. Use the absolute path to ASADO's venv Python so the server has `duckdb`, `neo4j`, `mcp`, and `pandas` available:

```json
{
  "mcpServers": {
    "asado": {
      "command": "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/venv/bin/python",
      "args": [
        "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/scripts/asado_mcp_server.py"
      ],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

`ANTHROPIC_API_KEY` is only required if you want to call `ask_asado`; the four other tools (`run_duckdb_sql`, `run_neo4j_cypher`, `get_schema_summary`, `get_country_profile`) work without it. Then **fully quit and relaunch Claude Desktop** — it spawns the MCP server as a subprocess on launch.

ChatGPT Desktop is **not** supported as a connector for this server: ChatGPT's MCP integration only accepts remote HTTPS endpoints (SSE transport with OAuth), and `asado_mcp_server.py` runs over stdio. Stick with Claude Desktop unless you decide to expose an SSE transport via Cloudflare Tunnel — out of scope for the current build.

### Example prompts

```
Use the ASADO connector. Run this SQL:
  SELECT factor, value FROM factor_returns
  WHERE date='2026-03-01' AND source='econ_optimizer'
  ORDER BY value DESC LIMIT 5
```

```
Which countries were in the top-20 bucket for BIS_Credit_GDP_Gap_CS in 2025-10?
```

```
Pull a country profile for Indonesia: latest factor exposures plus its top
trade and banking edges. Format as a markdown one-pager.
```

```
For factors in factor_returns whose 12-month rolling Sharpe is in the top decile
this month, sum country contributions from country_factor_attribution and
return the 10 most-contributing countries.
```

```
Find the 5 countries most similar to Turkey by state embedding (Cypher),
then for each return the latest BIS_Credit_GDP_Gap and IMF_CPI_Inflation_YoY.
```

### Surfaces unlocked by the optimizer-returns layer (2026-04-29)

- `factor_returns(date, factor, value, source)` — monthly net returns of top-20% portfolios across the Econ / T2 / GDELT optimizer pipelines (~402K rows). Factor names retain their `_CS` / `_TS` suffix.
- `factor_top20_membership(date, country, factor, weight, source)` — sparse country-level membership in each factor's top-20% bucket (~3.08M rows).
- `country_factor_attribution` (view) — `factor_top20_membership ⨝ factor_returns` on `(date, factor, source)`. Joinable for "which countries earned the bucket return this month" attribution.
- Neo4j `Factor` nodes carry `latest_return_1m`, `latest_return_12m`, `sharpe_60m`, `latest_return_date`, `return_source` — useful for ranking factors directly via Cypher.

### Limits

- DuckDB connection is read-only — `run_duckdb_sql` cannot mutate the warehouse.
- Neo4j connection is **not** wrapped read-only at the driver level; treat `run_neo4j_cypher` as conventionally read-only and avoid `MERGE` / `CREATE` / `DELETE` from Claude Desktop. (If you ever expose this server to a non-trusted client, add a write-guard before doing so.)
- The server uses stdio transport; one Claude Desktop launch spawns one subprocess. Two clients can connect simultaneously (each gets its own subprocess) without coordination since the underlying DBs handle concurrent readers.
- Returned frames are capped at `max_rows` (default 100). Bump it explicitly for larger pulls; very large results will fail Claude Desktop's tool-result size budget anyway.

### Troubleshooting

```bash
# Verify the server boots cleanly outside Claude Desktop
./venv/bin/python -c "from mcp.server.fastmcp import FastMCP; print('mcp ok')"
./venv/bin/python scripts/asado_mcp_server.py < /dev/null   # should print stdio handshake then exit cleanly on EOF

# Refresh the schema cache (so ask_asado / get_schema_summary see new tables)
./venv/bin/python scripts/build_schema_registry.py

# Confirm Neo4j is up before running cypher
nc -z localhost 7687 && echo "neo4j reachable" || brew services start neo4j
```

If Claude Desktop reports "MCP server failed to start", check `~/Library/Logs/Claude/mcp*.log` for the subprocess stderr — the most common causes are (a) wrong venv path in `command`, (b) missing `ANTHROPIC_API_KEY` when something tries to call `ask_asado`, (c) Neo4j down for Cypher tools.

---

## Skipped Sources (April 2026)

The following sources from the original PRD were evaluated and intentionally skipped due to access blockers. Existing data from other sources provides adequate coverage for each gap.

| Source | What it would add | Why skipped | Covered by |
|--------|-------------------|-------------|------------|
| UN Comtrade | Bilateral trade flows | API key registration broken (email never arrives) | IMF IMTS bilateral trade (899 pairs in Neo4j), IMF ITG aggregate trade |
| ACLED | Armed conflict events & fatalities | Requires API key + email registration | GPR index (geopolitical risk), GDELT sentiment (news-based conflict signals) |
| IPU Parline | Parliamentary/election calendar data | API returning 403 Forbidden (April 2026) | OFAC sanctions data, WGI governance indicators |
| WITS | Tariff rates & non-tariff barriers | API returning 403 Forbidden (April 2026) | IMF trade data, World Bank trade openness, BIS REER (competitiveness) |
