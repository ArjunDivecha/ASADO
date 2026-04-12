# GDELT Country Sentiment Pipeline

A multi-stage data pipeline that ingests raw [GDELT Global Knowledge Graph (GKG v2)](https://www.gdeltproject.org/) data and produces country-level news sentiment signals at daily and monthly frequencies. The final output is an Excel workbook mapping composite indicators across 34 country buckets over the full available history (2015–present).

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


| Flag             | Default                      | Description                                    |
| ---------------- | ---------------------------- | ---------------------------------------------- |
| `--date`         | *(required)*                 | Date in `YYYY-MM-DD` format                    |
| `--lookups-dir`  | `data/lookups`               | Directory for masterfilelist and lookup files  |
| `--output-dir`   | `data/country_day`           | Output directory for daily parquet             |
| `--manifest-dir` | `data/manifests/country_day` | Output directory for manifest JSON             |
| `--top-k-themes` | `0`                          | Number of top themes to retain per country-day |
| `--overwrite`    | `false`                      | Overwrite existing parquet for the date        |
| `--strict-fetch` | `false`                      | Fail if any GKG ZIP cannot be fetched          |


### Stage 2 — Build Daily Signal Panel

```bash
python3 scripts/build_country_signals.py
```

Reads all `data/country_day/*.parquet` files, expands each country's timeline to a full calendar grid, and computes trailing z-scored features using a 30-day rolling window (shift-1 to avoid look-ahead).


| Flag                | Default                                    | Description                                    |
| ------------------- | ------------------------------------------ | ---------------------------------------------- |
| `--country-day-dir` | `data/country_day`                         | Input directory of daily parquet files         |
| `--manifest-dir`    | `data/manifests/country_day`               | Manifest directory for fetch coverage metadata |
| `--output-csv`      | `data/panels/country_signal_daily.csv`     | Output CSV path                                |
| `--output-parquet`  | `data/panels/country_signal_daily.parquet` | Output parquet path                            |
| `--window`          | `30`                                       | Trailing lookback window in days               |
| `--min-history`     | `10`                                       | Minimum observations before emitting a z-score |


### Stage 3 — Build Monthly Metronome

```bash
python3 scripts/build_monthly_metronome.py
```

Takes the daily signal panel and builds month-end snapshots of EWMA-smoothed features, then z-scores them within-country over a 24-month trailing window.


| Flag                    | Default                                      | Description                                     |
| ----------------------- | -------------------------------------------- | ----------------------------------------------- |
| `--daily-panel-parquet` | `data/panels/country_signal_daily.parquet`   | Input daily parquet                             |
| `--output-parquet`      | `data/panels/country_signal_monthly.parquet` | Output parquet                                  |
| `--output-csv`          | `data/panels/country_signal_monthly.csv`     | Output CSV                                      |
| `--fast-span`           | `5`                                          | EWMA span for fast features                     |
| `--slow-span`           | `20`                                         | EWMA span for slow features                     |
| `--risk-span`           | `10`                                         | EWMA span for risk/dispersion features          |
| `--z-window-months`     | `24`                                         | Trailing z-score window in months               |
| `--min-history-months`  | `6`                                          | Minimum months before emitting monthly z-scores |


### Stage 4 — Export Excel Workbook

```bash
python3 scripts/export_country_sentiment_workbook.py --panel-parquet data/panels/country_signal_monthly.parquet
```

Pivots the monthly panel into a styled multi-sheet Excel workbook.

---

## Key Signals & Composite Indicators

### Monthly Composites


| Signal                | Formula                                                                                         | Description                                        |
| --------------------- | ----------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| **monthly_metronome** | `0.35·sent_fast_z + 0.20·sent_slow_z + 0.20·sent_trend_z + 0.15·attn_fast_z − 0.10·risk_fast_z` | Primary composite — higher = more positive outlook |
| **monthly_risk**      | `0.45·risk_fast_z + 0.30·disp_fast_z − 0.15·sent_fast_z − 0.10·foreign_tone_fast_z`             | Risk composite — higher = more risk-off            |
| **monthly_defensive** | `−1.0 × monthly_risk`                                                                           | Defensive positioning score                        |


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


| Bucket                   | ISO3 |     | Bucket       | ISO3 |
| ------------------------ | ---- | --- | ------------ | ---- |
| Singapore                | SGP  |     | Malaysia     | MYS  |
| Australia                | AUS  |     | Taiwan       | TWN  |
| Canada                   | CAN  |     | Mexico       | MEX  |
| Germany                  | DEU  |     | Korea        | KOR  |
| Japan                    | JPN  |     | Brazil       | BRA  |
| Switzerland              | CHE  |     | South Africa | ZAF  |
| U.K.                     | GBR  |     | Denmark      | DNK  |
| U.S. / NASDAQ / SmallCap | USA  |     | India        | IND  |
| France                   | FRA  |     | China A/H    | CHN  |
| Netherlands              | NLD  |     | Hong Kong    | HKG  |
| Sweden                   | SWE  |     | Thailand     | THA  |
| Italy                    | ITA  |     | Turkey       | TUR  |
| Chile                    | CHL  |     | Spain        | ESP  |
| Indonesia                | IDN  |     | Vietnam      | VNM  |
| Philippines              | PHL  |     | Saudi Arabia | SAU  |
| Poland                   | POL  |     |              |      |


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


| File                     | Source URL                                                        | Purpose                            |
| ------------------------ | ----------------------------------------------------------------- | ---------------------------------- |
| masterfilelist.txt       | `http://data.gdeltproject.org/gdeltv2/masterfilelist.txt`         | Index of all GKG v2 ZIP archives   |
| COUNTRY-GEO-LOOKUP.TXT   | `http://data.gdeltproject.org/api/v2/guides/LOOKUP-COUNTRIES.TXT` | GDELT country code ↔ name mapping  |
| geonames_countryInfo.txt | `https://download.geonames.org/export/dump/countryInfo.txt`       | FIPS ↔ ISO2/ISO3 mapping           |
| Domain-country CSV       | `https://blog.gdeltproject.org/wp-content/uploads/...`            | ~11.8M-row domain → country census |


