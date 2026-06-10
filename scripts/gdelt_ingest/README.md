# GDELT Country Sentiment Pipeline

A multi-stage data pipeline that ingests raw [GDELT Global Knowledge Graph (GKG v2)](https://www.gdeltproject.org/) data and produces country-level news sentiment signals at daily and monthly frequencies. The final output is an Excel workbook mapping composite indicators across 34 country buckets over the full available history (2015–present).

---

## Program Documentation

This repository contains 9 Python programs organized into a 4-stage pipeline:

### Stage 1: Data Fetching & Aggregation
- **`stream_build_country_day.py`** - Fetches and processes GDELT GKG data for a single date

**Purpose**: Downloads 15-minute GKG ZIP files for a specified date from GDELT, parses article-level data, resolves source countries, and aggregates tone/attention metrics per country. Outputs a parquet file and manifest JSON for each processed date.

**Key Features**:
- Parallel downloading of GKG ZIP files (configurable workers)
- Country resolution using GDELT country codes, GeoNames, and domain-to-country mapping
- Tone analysis including sentiment, polarity, and dispersion metrics
- Source attribution (local vs foreign media)
- Theme extraction and top-K theme retention
- Deduplication by document identifier
- Comprehensive manifest generation with fetch coverage metadata

**Inputs**:
- GDELT masterfilelist (auto-downloaded if stale)
- GKG ZIP files from data.gdeltproject.org
- Country lookup tables (GDELT, GeoNames, domain mappings)

**Outputs**:
- `data/country_day/{date}.parquet` - Country-day aggregated metrics
- `data/manifests/country_day/{date}.json` - Fetch coverage and processing metadata

**Usage**:
```bash
python3 scripts/stream_build_country_day.py --date 2025-03-15
```

**Key Parameters**:
- `--date` (required): Date in YYYY-MM-DD format
- `--fetch-workers`: Parallel threads for intra-day downloads (default: 8)
- `--top-k-themes`: Number of top themes to retain per country-day (default: 0)
- `--strict-fetch`: Fail if any GKG ZIP cannot be fetched
- `--overwrite`: Overwrite existing parquet file

### Stage 2: Daily Signal Panel Construction
- **`build_country_signals.py`** - Builds daily country-level signal panel from aggregated data

**Purpose**: Loads all daily country-day parquet files, expands each country's timeline to a full calendar grid, and computes trailing z-scored features using a configurable rolling window. Creates the foundation daily signal panel with raw components and composite indicators.

**Key Features**:
- Calendar-aware timeline expansion (fills missing dates per country)
- Trailing z-score computation with shift-1 to avoid look-ahead bias
- Configurable window size and minimum history requirements
- Support for both calendar-day and observation-based windows
- Integration with manifest coverage metadata
- Composite indicator construction (metronome, risk, defensive)

**Inputs**:
- `data/country_day/*.parquet` - Daily country aggregated metrics from Stage 1
- `data/manifests/country_day/*.json` - Optional fetch coverage metadata

**Outputs**:
- `data/panels/country_signal_daily.csv` - Combined daily signal panel
- `data/panels/country_signal_daily.parquet` - Combined daily signal panel (parquet format)

**Usage**:
```bash
python3 scripts/build_country_signals.py
```

**Key Parameters**:
- `--window`: Trailing lookback window in days (default: 30)
- `--min-history`: Minimum observations before emitting z-scores (default: 10)
- `--observation-windows`: Use trailing observed rows instead of calendar-day windows

**Computed Features**:
- Raw signals: sentiment, risk, attention, local/foreign tone
- Trailing z-scores: all raw signals with configurable windows
- Composite indicators: metronome, risk, defensive scores
- Cross-sectional features: attention shock, sentiment-attention interaction

- **`build_daily_metronome.py`** - Creates daily metronome decision layer with EWMA smoothing

**Purpose**: Daily analog of build_monthly_metronome.py. Retains every calendar day (instead of month-end snapshots) and applies EWMA smoothing with trailing z-scores over a 504-day window (~24 months). Provides daily-frequency decision layer with methodologically identical composites to the monthly version.

**Key Features**:
- Identical EWMA spans and composite formulae as monthly version
- Trailing z-scores over 504 calendar-day window instead of 24 months
- Retains all calendar days (no month-end snapshot filtering)
- Cross-sectional ranking within each day
- Methodological consistency between daily and monthly signals

**Inputs**:
- `data/panels/country_signal_daily.parquet` - Daily signal panel from Stage 2

**Outputs**:
- `data/panels/country_signal_daily_metronome.csv` - Daily metronome panel
- `data/panels/country_signal_daily_metronome.parquet` - Daily metronome panel (parquet format)

**Usage**:
```bash
python3 scripts/build_daily_metronome.py
```

**Key Parameters**:
- `--fast-span`: EWMA span for fast features (default: 5 days)
- `--slow-span`: EWMA span for slow features (default: 20 days)
- `--risk-span`: EWMA span for risk/dispersion features (default: 10 days)
- `--z-window-days`: Trailing window in calendar days (default: 504)
- `--min-history-days`: Minimum days before emitting z-scores (default: 126)

**Computed Features**:
- EWMA blocks: identical structure to monthly version
- Trailing z-scores: 504-day window instead of 24-month window
- Daily composites: daily_metronome, daily_risk, daily_defensive
- Cross-sectional ranks: daily percentile ranks across countries

### Stage 3: Monthly Signal Panel Construction
- **`build_monthly_metronome.py`** - Creates monthly metronome decision layer with EWMA smoothing

**Purpose**: Takes the daily signal panel and builds month-end snapshots of EWMA-smoothed features, then z-scores them within-country over a trailing 24-month window. Creates the monthly decision layer with composite indicators for systematic rebalancing.

**Key Features**:
- EWMA smoothing with configurable spans (fast/slow/risk blocks)
- Month-end snapshot selection (last observation per month)
- Within-country z-scoring over trailing monthly window
- Observation share calculation (data quality metric)
- Integration with daily status and fetch coverage metadata
- Composite indicator construction with standardized weights

**Inputs**:
- `data/panels/country_signal_daily.parquet` - Daily signal panel from Stage 2

**Outputs**:
- `data/panels/country_signal_monthly.csv` - Monthly signal panel
- `data/panels/country_signal_monthly.parquet` - Monthly signal panel (parquet format)

**Usage**:
```bash
python3 scripts/build_monthly_metronome.py
```

**Key Parameters**:
- `--fast-span`: EWMA span for fast features (default: 5 months)
- `--slow-span`: EWMA span for slow features (default: 20 months)
- `--risk-span`: EWMA span for risk/dispersion features (default: 10 months)
- `--z-window-months`: Trailing z-score window in months (default: 24)
- `--min-history-months`: Minimum months before emitting z-scores (default: 6)

**Computed Features**:
- EWMA blocks: sentiment (fast/slow/trend), attention (fast/slow/trend), risk/dispersion
- Within-country z-scores: all EWMA features over trailing window
- Monthly composites: metronome, risk, defensive
- Quality metrics: observation share, day status, fetch coverage

### Stage 4: Excel Workbook Export
- **`export_country_sentiment_workbook.py`** - Exports monthly panel to Excel workbook

**Purpose**: Pivots the monthly signal panel into a styled multi-sheet Excel workbook with one sheet per indicator. Includes comprehensive documentation sheets (README and variable dictionary) and supports country bucket aliases for ETF mapping.

**Key Features**:
- Multi-sheet workbook with dates down column A, countries across row 1
- Country bucket aliases (U.S., U.S. NASDAQ, US SmallCap → USA; China A, China H → CHN)
- 34 predefined country buckets matching ETF universe
- Comprehensive README sheet with architecture overview
- Variable dictionary sheet with definitions and formulae
- Optional template workbook support for styling
- Cross-sectional rank percentiles for composite indicators

**Inputs**:
- `data/panels/country_signal_monthly.parquet` - Monthly signal panel from Stage 3

**Outputs**:
- `output/spreadsheet/GDELT.xlsx` - Multi-sheet Excel workbook (default)

**Usage**:
```bash
python3 scripts/export_country_sentiment_workbook.py --panel-parquet data/panels/country_signal_monthly.parquet
```

**Key Parameters**:
- `--panel-parquet`: Input monthly parquet path
- `--output`: Output Excel workbook path
- `--template-xlsx`: Optional template workbook for styling

**Workbook Structure**:
- README sheet: Architecture overview, coverage, feature families
- README_VARIABLES sheet: Variable definitions, formulae, and sources
- Indicator sheets: One per indicator (45+ sheets) with country bucket columns
- **`export_daily_workbook.py`** - Exports daily panel to Excel workbook

**Purpose**: Daily analog of export_country_sentiment_workbook.py. Exports the daily metronome panel into a multi-sheet Excel workbook with identical layout and country bucket mapping. Provides daily-frequency signals in the same format as monthly outputs.

**Key Features**:
- Identical layout to monthly exporter (dates × countries)
- Same country bucket aliases and mapping
- Daily-frequency indicator sheets
- Comprehensive README with daily-specific parameters
- Variable dictionary with daily definitions
- Reuses styling and infrastructure from monthly exporter
- Z-score window: 504 calendar days (~24 months) vs 24 months for monthly

**Inputs**:
- `data/panels/country_signal_daily_metronome.parquet` - Daily metronome panel

**Outputs**:
- `output/spreadsheet/GDELT_DAILY.xlsx` - Daily multi-sheet Excel workbook (default)

**Usage**:
```bash
python3 scripts/export_daily_workbook.py --panel-parquet data/panels/country_signal_daily_metronome.parquet
```

**Key Parameters**:
- `--panel-parquet`: Input daily metronome parquet path
- `--output`: Output Excel workbook path
- `--template-xlsx`: Optional template workbook for styling

**Workbook Structure**:
- README sheet: Daily-specific coverage and parameters
- README_VARIABLES sheet: Daily variable definitions
- Indicator sheets: Same structure as monthly, daily frequency
- **`export_deep_workbook.py`** - Exports extended monthly panel with deep features to Excel

**Purpose**: Extended version of export_country_sentiment_workbook.py that handles monthly panels with deep features (themes, GCAM emotions, event aggregates). Enforces GDELT keep-list from ASADO repo to ensure consistency across pipelines. Provides comprehensive documentation of four feature families.

**Key Features**:
- Feature family classification (core, theme, GCAM, event)
- GDELT keep-list enforcement from ASADO repo (hard-fail if unavailable)
- Comprehensive README with four-family architecture overview
- Variable dictionary with family-level organization
- Theme attention share and delta features
- GCAM emotional dimensions (40 dictionaries across 4 sub-blocks)
- Event aggregates (Goldstein scores, quad class, root codes)
- Template styling support

**Inputs**:
- `data/panels/country_signal_monthly_deep.parquet` - Extended monthly panel with deep features

**Outputs**:
- `output/spreadsheet/GDELT.xlsx` - Extended multi-sheet Excel workbook (default)

**Usage**:
```bash
python3 scripts/export_deep_workbook.py --panel-parquet data/panels/country_signal_monthly_deep.parquet
```

**Key Parameters**:
- `--panel-parquet`: Input extended monthly parquet path
- `--output`: Output Excel workbook path
- `--template-xlsx`: Optional template workbook for styling

**Feature Families**:
- Core Tone Signals (~45 variables): EWMA decompositions, z-scores, composites
- Theme Attention (~568 variables): 284 GDELT themes with share and delta
- GCAM Emotional Dimensions (~300 variables): 40 sentiment dictionaries
- Event Aggregates (~72 variables): CAMEO events with Goldstein scores

### Unified Pipeline & Support
- **`build_fullhistory_workbook.py`** - Unified pipeline that runs all stages in one command

**Purpose**: Single-command unified pipeline that orchestrates all four stages from GDELT data fetching to final Excel workbook export. Handles incremental fetching (skips cached dates), parallel downloads, and optional daily workbook generation. The only persistent cache is country-day parquet files.

**Key Features**:
- Incremental fetching: only downloads missing dates from GDELT
- Masterfilelist auto-refresh (stale >12 hours)
- Parallel day fetching with configurable workers
- In-memory pipeline computation (no intermediate panel files required)
- Optional daily workbook generation alongside monthly
- Optional intermediate panel file saving
- Template workbook support for styling
- Comprehensive progress reporting and error handling

**Inputs**:
- GDELT masterfilelist (auto-downloaded)
- GKG ZIP files from data.gdeltproject.org (fetched incrementally)
- Cached country-day parquet files (data/country_day/*.parquet)

**Outputs**:
- `output/spreadsheet/GDELT.xlsx` - Monthly workbook (default)
- `output/spreadsheet/GDELT_DAILY.xlsx` - Daily workbook (with --daily flag)
- `data/panels/country_signal_daily.*` - Optional daily panel (with --save-panels)
- `data/panels/country_signal_monthly.*` - Optional monthly panel (with --save-panels)

**Usage**:
```bash
# Full pipeline from scratch
python3 scripts/build_fullhistory_workbook.py

# With date range and parallel workers
python3 scripts/build_fullhistory_workbook.py --start-date 2020-01-01 --workers 8

# Skip fetching, rebuild from cache
python3 scripts/build_fullhistory_workbook.py --skip-fetch

# Include daily workbook and save intermediate panels
python3 scripts/build_fullhistory_workbook.py --daily --save-panels
```

**Key Parameters**:
- `--start-date`: Earliest date to fetch (default: 2015-02-18)
- `--end-date`: Latest date to fetch (default: yesterday)
- `--workers`: Parallel workers for day fetching (default: 4)
- `--fetch-workers`: Intra-day parallel threads (default: 8)
- `--skip-fetch`: Skip GDELT fetch, rebuild from cache
- `--save-panels`: Save intermediate panel files
- `--daily`: Also produce daily workbook
- `--template-xlsx`: Template workbook for styling
- **`gdelt_support.py`** - Support utilities and helper functions

**Purpose**: Shared utility module providing core functions for GDELT data processing, country resolution, tone analysis, and file operations. Used by all pipeline stages for common functionality including data fetching, parsing, and lookup management.

**Key Features**:
- GDELT data fetching with retry logic and timeout handling
- Country code resolution (GDELT FIPS → ISO3 mapping)
- Domain normalization and country inference
- GKG field parsing (tone, locations, themes)
- Statistical utilities (quantile, standard deviation, weighted average)
- Text cleaning and safe type conversion
- Masterfilelist and lookup file management
- ZIP file streaming and CSV parsing with large field support

**Core Functions**:
- `fetch_bytes()`: HTTP GET with retry logic and exponential backoff
- `ensure_support_files()`: Download and cache lookup files
- `load_gdelt_country_lookup()`: Parse GDELT country mapping
- `load_geonames_fips_lookup()`: Parse GeoNames FIPS→ISO3 mapping
- `load_domain_country_lookup()`: Parse domain-to-country mapping
- `infer_source_country_code()`: Resolve source country from domain
- `tone_parts()`: Parse GKG V2Tone field into components
- `parse_v2location_item()`: Parse GKG location entries
- `parse_v2theme_item()`: Parse GKG theme entries
- `iter_gkg_rows_from_zip_bytes()`: Stream GKG records from ZIP
- `normalize_domain()`: Clean and normalize domain names
- `enrich_country()`: Add ISO3 and country name to GDELT codes

**Data Sources**:
- GDELT masterfilelist: http://data.gdeltproject.org/gdeltv2/masterfilelist.txt
- GDELT country lookup: http://data.gdeltproject.org/api/v2/guides/LOOKUP-COUNTRIES.TXT
- GeoNames country info: https://download.geonames.org/export/dump/countryInfo.txt
- Domain-country mapping: GDELT blog outlet dataset (2015-2021)

**Usage**:
Imported by all pipeline scripts. Not run directly as a standalone program.

---

## Pipeline Overview

```
GDELT GKG v2 Feeds
       │
       ▼
┌──────────────────────────┐
│ 1. stream_build_country_ │   Fetches 15-minute GKG ZIP files for a date,
│    day.py                │   parses articles, resolves source countries,
│                          │   aggregates tone/attention per country.
│         ➜ Parquet        │   Outputs: data/country_day/{date}.parquet
│         ➜ Manifest JSON  │   Outputs: data/manifests/country_day/{date}.json
└──────────────────────────┘
       │
       ▼
┌──────────────────────────┐
│ 2. build_country_        │   Loads all daily parquet files, computes
│    signals.py            │   trailing z-scored features per country:
│                          │   sentiment, risk, attention shock, etc.
│         ➜ CSV + Parquet  │   Outputs: data/panels/country_signal_daily.*
└──────────────────────────┘
       │
       ▼
┌──────────────────────────┐
│ 3. build_monthly_        │   Snapshots EWMA-smoothed daily features at
│    metronome.py          │   month-end, then z-scores within country
│                          │   over a trailing 24-month window.
│         ➜ CSV + Parquet  │   Outputs: data/panels/country_signal_monthly.*
└──────────────────────────┘
       │
       ▼
┌──────────────────────────┐
│ 4. export_country_       │   Pivots the monthly panel into a multi-sheet
│    sentiment_            │   Excel workbook with one sheet per indicator.
│    workbook.py           │   Includes README + variable dictionary sheets.
│         ➜ XLSX           │   Outputs: output/spreadsheet/*.xlsx
└──────────────────────────┘
```

**Unified shortcut:** `build_fullhistory_workbook.py` runs all four stages in a single command with incremental fetching and parallel downloads.

---

## Quick Start

### Prerequisites

- Python 3.9+
- Internet access (fetches GKG data from `data.gdeltproject.org`)

### Install Dependencies

```bash
pip install -r requirements.txt
```

Dependencies: `pandas`, `pyarrow`, `openpyxl`

### One-Command Full Pipeline

```bash
python3 scripts/build_fullhistory_workbook.py
```

This will:
1. Download/refresh the GDELT masterfilelist
2. Incrementally fetch all missing daily GKG data (default: 2015-02-18 onward)
3. Compute daily and monthly signal panels in memory
4. Export the final workbook to `output/spreadsheet/gdelt_country_signals_monthly_fullhistory.xlsx`

### Common Options

```bash
# Limit date range
python3 scripts/build_fullhistory_workbook.py --start-date 2020-01-01 --end-date 2025-12-31

# Increase parallel download workers
python3 scripts/build_fullhistory_workbook.py --workers 8

# Skip fetching (rebuild from cached parquet only)
python3 scripts/build_fullhistory_workbook.py --skip-fetch

# Also save intermediate daily + monthly panel files
python3 scripts/build_fullhistory_workbook.py --save-panels

# Use a template workbook for Excel styling
python3 scripts/build_fullhistory_workbook.py --template-xlsx path/to/template.xlsx
```

---

## Running Individual Stages

### Stage 1 — Fetch & Aggregate a Single Day

```bash
python3 scripts/stream_build_country_day.py --date 2025-03-15
```

Downloads all 15-minute GKG ZIP archives for the given date from GDELT, parses each article's tone, locations, themes, and source domain, then aggregates statistics per country. Outputs a parquet file and a manifest JSON.

| Flag | Default | Description |
|---|---|---|
| `--date` | *(required)* | Date in `YYYY-MM-DD` format |
| `--lookups-dir` | `data/lookups` | Directory for masterfilelist and lookup files |
| `--output-dir` | `data/country_day` | Output directory for daily parquet |
| `--manifest-dir` | `data/manifests/country_day` | Output directory for manifest JSON |
| `--top-k-themes` | `0` | Number of top themes to retain per country-day |
| `--overwrite` | `false` | Overwrite existing parquet for the date |
| `--strict-fetch` | `false` | Fail if any GKG ZIP cannot be fetched |

### Stage 2 — Build Daily Signal Panel

```bash
python3 scripts/build_country_signals.py
```

Reads all `data/country_day/*.parquet` files, expands each country's timeline to a full calendar grid, and computes trailing z-scored features using a 30-day rolling window (shift-1 to avoid look-ahead).

| Flag | Default | Description |
|---|---|---|
| `--country-day-dir` | `data/country_day` | Input directory of daily parquet files |
| `--manifest-dir` | `data/manifests/country_day` | Manifest directory for fetch coverage metadata |
| `--output-csv` | `data/panels/country_signal_daily.csv` | Output CSV path |
| `--output-parquet` | `data/panels/country_signal_daily.parquet` | Output parquet path |
| `--window` | `30` | Trailing lookback window in days |
| `--min-history` | `10` | Minimum observations before emitting a z-score |

### Stage 3 — Build Monthly Metronome

```bash
python3 scripts/build_monthly_metronome.py
```

Takes the daily signal panel and builds month-end snapshots of EWMA-smoothed features, then z-scores them within-country over a 24-month trailing window.

| Flag | Default | Description |
|---|---|---|
| `--daily-panel-parquet` | `data/panels/country_signal_daily.parquet` | Input daily parquet |
| `--output-parquet` | `data/panels/country_signal_monthly.parquet` | Output parquet |
| `--output-csv` | `data/panels/country_signal_monthly.csv` | Output CSV |
| `--fast-span` | `5` | EWMA span for fast features |
| `--slow-span` | `20` | EWMA span for slow features |
| `--risk-span` | `10` | EWMA span for risk/dispersion features |
| `--z-window-months` | `24` | Trailing z-score window in months |
| `--min-history-months` | `6` | Minimum months before emitting monthly z-scores |

### Stage 4 — Export Excel Workbook

```bash
python3 scripts/export_country_sentiment_workbook.py --panel-parquet data/panels/country_signal_monthly.parquet
```

Pivots the monthly panel into a styled multi-sheet Excel workbook.

---

## Key Signals & Composite Indicators

### Monthly Composites

| Signal | Formula | Description |
|---|---|---|
| **monthly_metronome** | `0.35·sent_fast_z + 0.20·sent_slow_z + 0.20·sent_trend_z + 0.15·attn_fast_z − 0.10·risk_fast_z` | Primary composite — higher = more positive outlook |
| **monthly_risk** | `0.45·risk_fast_z + 0.30·disp_fast_z − 0.15·sent_fast_z − 0.10·foreign_tone_fast_z` | Risk composite — higher = more risk-off |
| **monthly_defensive** | `−1.0 × monthly_risk` | Defensive positioning score |

### Monthly Feature Blocks

- **Sentiment fast/slow/trend** — EWMA-smoothed sentiment levels and their momentum
- **Attention fast/slow/trend** — EWMA-smoothed local attention share and momentum
- **Risk fast / Dispersion fast** — EWMA-smoothed risk and tone disagreement
- **Local/Foreign tone fast** — Sentiment from local vs. foreign media sources
- **Local-foreign gap** — Divergence between local and foreign coverage tone
- All raw monthly features are z-scored within country over a trailing 24-month window

### Daily Features (inputs to monthly)

- **country_news_sentiment_raw** — Local tone (fallback: word-count-weighted tone)
- **country_news_risk_raw** — `−sentiment + 0.5 × dispersion`
- **country_news_attention** — `log(1 + local_n_articles)`
- **local_attention_share** — `local_n_articles / local_source_total_articles`
- **attention_shock** — Trailing z-score of attention
- **local_tone / foreign_tone** — Average tone split by source origin

---

## Project Structure

```
GDELT/
├── requirements.txt                # Python dependencies
├── README.md                       # This file
├── scripts/
│   ├── gdelt_support.py            # Shared utilities: parsing, lookups, fetching
│   ├── stream_build_country_day.py # Stage 1: daily GKG → country-day parquet
│   ├── build_country_signals.py    # Stage 2: daily → signal panel
│   ├── build_monthly_metronome.py  # Stage 3: daily → monthly metronome
│   ├── export_country_sentiment_workbook.py  # Stage 4: panel → Excel workbook
│   └── build_fullhistory_workbook.py         # Unified pipeline (all stages)
├── data/
│   ├── lookups/                    # Auto-downloaded reference files
│   │   ├── masterfilelist.txt      # GDELT GKG v2 file index
│   │   ├── COUNTRY-GEO-LOOKUP.TXT # GDELT country code → name mapping
│   │   ├── geonames_countryInfo.txt        # FIPS → ISO country code mapping
│   │   └── gdelt_domains_by_country_2015_2021.csv  # Domain → country lookup
│   ├── country_day/                # Cached daily parquet files (one per date)
│   ├── manifests/country_day/      # Per-day fetch status manifests (JSON)
│   └── panels/                     # Intermediate signal panels (CSV + Parquet)
└── output/
    └── spreadsheet/                # Final Excel workbook output
```

---

## Country Buckets

The workbook exports data for 34 country buckets covering major equity markets. Note that some buckets share the same ISO3 code (e.g. "U.S.", "U.S. NASDAQ", and "US SmallCap" all map to `USA`; "China A" and "China H" both map to `CHN`).

| Bucket | ISO3 | | Bucket | ISO3 |
|---|---|---|---|---|
| Singapore | SGP | | Malaysia | MYS |
| Australia | AUS | | Taiwan | TWN |
| Canada | CAN | | Mexico | MEX |
| Germany | DEU | | Korea | KOR |
| Japan | JPN | | Brazil | BRA |
| Switzerland | CHE | | South Africa | ZAF |
| U.K. | GBR | | Denmark | DNK |
| U.S. / NASDAQ / SmallCap | USA | | India | IND |
| France | FRA | | China A/H | CHN |
| Netherlands | NLD | | Hong Kong | HKG |
| Sweden | SWE | | Thailand | THA |
| Italy | ITA | | Turkey | TUR |
| Chile | CHL | | Spain | ESP |
| Indonesia | IDN | | Vietnam | VNM |
| Philippines | PHL | | Saudi Arabia | SAU |
| Poland | POL | | | |

---

## Source Country Resolution

Each article is attributed to a source country using a domain-based lookup. The pipeline:

1. Normalizes the article's `source_common_name` and `document_identifier` into candidate domain strings
2. Matches candidates against the GDELT domain→country CSV (~2015–2021 outlet census)
3. Classifies each country-mention's tone contribution as **local** (source country = mentioned country) or **foreign**

This enables the local/foreign tone split and the `local_attention_share` feature.

---

## Incremental Updates

The unified pipeline (`build_fullhistory_workbook.py`) is designed for incremental runs:

- **Daily parquet files are the cache** — dates already in `data/country_day/` are skipped
- **Masterfilelist auto-refreshes** if older than 12 hours
- Run the same command daily/weekly to append only new dates, then rebuild the workbook

---

## Data Sources

| File | Source URL | Purpose |
|---|---|---|
| masterfilelist.txt | `http://data.gdeltproject.org/gdeltv2/masterfilelist.txt` | Index of all GKG v2 ZIP archives |
| COUNTRY-GEO-LOOKUP.TXT | `http://data.gdeltproject.org/api/v2/guides/LOOKUP-COUNTRIES.TXT` | GDELT country code ↔ name mapping |
| geonames_countryInfo.txt | `https://download.geonames.org/export/dump/countryInfo.txt` | FIPS ↔ ISO2/ISO3 mapping |
| Domain-country CSV | `https://blog.gdeltproject.org/wp-content/uploads/...` | ~11.8M-row domain → country census |
