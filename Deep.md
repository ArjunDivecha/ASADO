# Deep — GDELT Country News Modality Features

**1,222 monthly country-level factors** built from GDELT GKG v2, GCAM emotional dictionaries, and CAMEO event data. Designed to plug directly into the ASADO DuckDB warehouse and Neo4j knowledge graph alongside the existing 92 GDELT tone signals.

---

## What this adds to ASADO

| | Current GDELT (92 vars) | Deep (1,222 vars) |
|---|---|---|
| **Source** | GKG V2Tone (one field) | GKG V2Themes + GCAM + CAMEO Events |
| **What it captures** | *How* the news sounds (tone) | *What* the news is about (themes), *emotional framing* (GCAM), *geopolitical activity* (events) |
| **Feature families** | 1 (tone-derived) | 4 (tone + theme + GCAM + event) |
| **Treatment** | EWMA fast/slow/trend + z-scores | Same treatment applied to all families |

The Deep features are **orthogonal** to tone — they measure topic attention, emotional framing dimensions, and actual geopolitical events, not just sentiment polarity.

---

## Data Location

All data lives in the GDELT working repo:

```
/Users/arjundivecha/Dropbox/AAA Backup/A Working/GDELT/Deep/
├── data/features/
│   ├── article_themes_daily/        # Per-day article × theme indicator parquet (4,064 files)
│   ├── article_gcam_daily/          # Per-day article × GCAM dimension parquet
│   ├── country_themes_daily.parquet # Country-day theme shares + deltas
│   ├── country_gcam_daily.parquet   # Country-day GCAM means
│   ├── country_events_daily.parquet # Country-day event aggregates
│   ├── country_news_modality.parquet          # Final merged daily panel (122,729 rows × 720 cols)
│   ├── country_signal_daily_deep.parquet      # Daily panel joined with existing signals
│   ├── country_signal_monthly_deep.parquet    # Monthly metronome with raw Deep features
│   └── country_signal_monthly_deep_treated.parquet  # ★ MONTHLY WITH EWMA/Z-SCORES — USE THIS
└── scripts/
    └── schema/
        ├── gcam_dimensions.yaml      # 75 curated GCAM dictionary keys with names and blocks
        ├── gdelt_themes.yaml         # 300 curated GDELT THEMES with frequency counts
        └── cameo_codes.yaml          # CAMEO event code → QuadClass mappings + country overrides
```

**Primary ingestion target:** `country_signal_monthly_deep_treated.parquet` — 32,067 rows × 1,221 columns, calendar-monthly, dates aligned to month-end.

---

## Feature Families

### Family 1: Core Tone Signals (83 variables) — unchanged from existing

The 8 base tone measurements and their derived EWMA/z-score/rank treatments. Already in ASADO via `gdelt_panel`. Included in the treated panel for completeness.

### Family 2: Theme Attention (568 variables)

**Source:** GKG V2Themes — 284 pre-curated themes from the GDELT THEMES taxonomy (top 300 of 59,315 by cumulative article frequency 2015–2026).

**What it measures:** Per country-month, the share of news articles mentioning each theme, plus month-over-month deltas.

| Naming pattern | Count | Description |
|---|---|---|
| `theme_<NAME>_share` | 284 | Fraction of articles mentioning theme `<NAME>` |
| `theme_<NAME>_share_delta` | 284 | Month-over-month change in share (the signal) |

The delta is the key signal — a sudden spike in PROTEST, ARMEDCONFLICT, or EPU_POLICY coverage is what predicts, not the level.

**Schema reference:** `gdelt_themes.yaml` — each theme name, GDELT frequency count, and taxonomy category.

### Family 3: GCAM Emotional Dimensions (450 variables)

**Source:** GKG GCAM field — 40 sentiment dictionaries applied to every article by GDELT, parsed and density-normalized, then aggregated to country-day means.

**Four sub-blocks:**

| Block | Dictionary | # Dims | Example variables |
|---|---|---|---|
| A — Loughran-McDonald | Financial text sentiment | 6 | `lm_negative`, `lm_positive`, `lm_uncertainty`, `lm_litigious` |
| B — WordNet-Affect 1.0 | High-level affective categories | 11 | `wna_emotion`, `wna_mood`, `wna_cognitive_state`, `wna_physical_state` |
| C — Harvard IV-4 GI | Power/strength/affect axes | 18 | `gi_strng`/`gi_weak`, `gi_actv`/`gi_psv`, `gi_pleasure`/`gi_pain`, `gi_virtue`/`gi_vice` |
| D — Value-based | Continuous sentiment scores | 40 | `swn_positive`/`swn_negative` (SentiWordNet), `anew_valence`/`anew_arousal` (ANEW), `vader_valence` (VADER), `mfd_care` (Moral Foundations) |

**Treatment per dimension:**

| Suffix | Count per dim | Formula |
|---|---|---|
| `gcam_<DIM>` (raw) | 75 | Month-end snapshot of country-day mean |
| `gcam_<DIM>_fast` | 75 | EWMA(span=5) |
| `gcam_<DIM>_slow` | 75 | EWMA(span=20) |
| `gcam_<DIM>_trend` | 75 | fast − slow |
| `gcam_<DIM>_z` | 75 | Trailing within-country z-score (24-month window, min 6) |
| `gcam_<DIM>_fast_z` | 75 | Trailing z-score of `_fast` |

Total: 75 × 6 = 450 columns.

**Schema reference:** `gcam_dimensions.yaml` — each GCAM key (`c6.4`, `v10.1`, etc.), human-readable name, type (count vs value), and dictionary block.

### Family 4: Event Aggregates (120 variables)

**Source:** GDELT CAMEO EVENTS + EVENTMENTIONS — structured actor-action-target event records. Country attribution via `ActionGeo_CountryCode` (FIPS → ISO3 mapped). Historical backfill via BigQuery (`gdelt-bq.gdeltv2.events_partitioned`), daily updates via HTTP.

**Base features (24):**

| Feature | Description |
|---|---|
| `event_n_total` | Total distinct mention rows per country-month |
| `event_n_quad[1-4]` | Count by QuadClass: 1=VerbalCoop, 2=MaterialCoop, 3=VerbalConflict, 4=MaterialConflict |
| `event_goldstein_{mean,min}` | Goldstein cooperation/conflict score (−10 to +10) |
| `event_avgtone_mean` | Mean tone of articles mentioning events |
| `event_root_<CODE>_n` | Counts by curated EventRootCode (12 codes: assault, fight, protest, threaten, express_cooperate, etc.) |
| `event_persistence_{3d,7d}` | Mentions today of events from 1-3 or 4-7 days ago (news-cycle inertia) |
| `event_n_low_confidence` | Count of mentions with Confidence < 50 (quality flag) |

**Treatment per feature:**

| Suffix | Count per feature | Formula |
|---|---|---|
| `event_<FEAT>` (raw) | 24 | Month-end snapshot |
| `event_<FEAT>_fast` | 24 | EWMA(span=5) |
| `event_<FEAT>_trend` | 24 | fast − lagged raw |
| `event_<FEAT>_z` | 24 | Trailing z-score (24-month window) |
| `event_<FEAT>_fast_z` | 24 | Trailing z-score of `_fast` |

Total: 24 × 5 = 120 columns.

**Schema reference:** `cameo_codes.yaml` — EventRootCode → QuadClass mapping and CAMEO→ISO3 country overrides.

---

## No Look-Ahead Guarantee

Every feature for month M is computable from data published on or before the last calendar day of month M:

- **GKG features** (theme, GCAM): Each daily GKG file is timestamped to its publication date. Features for date D only use that day's file.
- **Event features**: Attribution uses `MentionTimeDate` (when the article was published), not `EventTimeDate` (when the event occurred). An event from 2018 mentioned in a 2024 article counts as a 2024 data point — because that's when the information became available.
- **Z-scores**: Use trailing windows shifted by 1 month. The z-score for month M uses only months < M for mean/std computation.
- **EWMA**: Standard exponential weighting — only observations ≤ month M contribute to the smoothed value.
- **Month-end snapshots**: Use the last calendar day of the month. No intra-month forward-peeking.

---

## Ingestion into ASADO

### Step 1: Load the treated monthly panel

```python
import pandas as pd
from pathlib import Path

DEEP_PARQUET = Path(
    "/Users/arjundivecha/Dropbox/AAA Backup/A Working/GDELT/"
    "Deep/data/features/country_signal_monthly_deep_treated.parquet"
)

df = pd.read_parquet(DEEP_PARQUET)
# Columns: date, country_iso3, country_name, signal_month, ... (1,221 feature columns)
```

### Step 2: Map ISO3 → T2 country names

The panel uses 3-letter ISO3 codes. Map to ASADO's 34-country T2 universe:

```python
from config.country_mapping import T2_COUNTRIES  # or load from country_mapping.json

ISO3_TO_T2 = {
    "USA": ["U.S.", "U.S. NASDAQ", "US SmallCap"],
    "CHN": ["China A", "China H"],
    "GBR": "U.K.",  "DEU": "Germany",  "JPN": "Japan",
    "FRA": "France", "ITA": "Italy",   "ESP": "Spain",
    "CAN": "Canada", "AUS": "Australia", "BRA": "Brazil",
    "CHE": "Switzerland", "SWE": "Sweden", "NLD": "Netherlands",
    "DNK": "Denmark",  "KOR": "Korea",   "IND": "India",
    "MEX": "Mexico",   "IDN": "Indonesia", "TUR": "Turkey",
    "ZAF": "South Africa", "SAU": "Saudi Arabia",
    "SGP": "Singapore", "HKG": "Hong Kong", "TWN": "Taiwan",
    "THA": "Thailand", "MYS": "Malaysia", "PHL": "Philippines",
    "POL": "Poland",   "CHL": "Chile",  "VNM": "Vietnam",
}

def iso3_to_t2(iso3: str) -> list[str]:
    """Map ISO3 code to T2 country name(s). USA and CHN expand to multiple buckets."""
    result = ISO3_TO_T2.get(iso3, [iso3])
    if isinstance(result, str):
        return [result]
    return result
```

### Step 3: Convert to ASADO tidy format

```python
import pandas as pd

def deep_to_tidy(parquet_path, iso3_to_t2) -> pd.DataFrame:
    """Convert wide Deep panel to ASADO tidy format: (date, country, value, variable, source)."""
    df = pd.read_parquet(parquet_path)

    # Use month-end dates (first-of-month for ASADO alignment)
    if "signal_month_end_date" in df.columns:
        df["date"] = pd.to_datetime(df["signal_month_end_date"])
    else:
        df["date"] = pd.to_datetime(df["date"])
    df["date"] = df["date"].dt.to_period("M").dt.to_timestamp()  # first-of-month

    # Identify feature columns (exclude metadata)
    meta_cols = {"date", "country_iso3", "country_name", "country_code_gdelt",
                 "signal_month", "signal_month_end_date", "month_end_date_used",
                 "month_obs_count", "month_calendar_days", "month_obs_share",
                 "month_day_status_worst", "month_gkg_fetch_share_mean",
                 "month_gkg_fetch_share_min"}
    feature_cols = [c for c in df.columns if c not in meta_cols]

    # Melt to tidy format
    tidy = df.melt(
        id_vars=["date", "country_iso3"],
        value_vars=feature_cols,
        var_name="variable",
        value_name="value"
    )

    # Map to T2 country names
    tidy["country"] = tidy["country_iso3"].map(
        lambda x: iso3_to_t2(x)[0]  # primary mapping
    )
    tidy = tidy.dropna(subset=["country", "value"])

    # Add source tag
    def assign_source(variable: str) -> str:
        if variable.startswith("theme_"):    return "gdelt_deep_theme"
        if variable.startswith("gcam_"):     return "gdelt_deep_gcam"
        if variable.startswith("event_"):    return "gdelt_deep_event"
        return "gdelt_core"

    tidy["source"] = tidy["variable"].apply(assign_source)

    return tidy[["date", "country", "value", "variable", "source"]]
```

### Step 4: Load into DuckDB

```python
from scripts.db_bridge import AsadoDB

tidy = deep_to_tidy(DEEP_PARQUET, ISO3_TO_T2)

with AsadoDB() as db:
    # Create new table
    db.conn.execute("""
        CREATE OR REPLACE TABLE gdelt_deep_panel AS
        SELECT * FROM tidy
    """)

    # Or merge into existing gdelt_panel
    db.conn.execute("""
        INSERT INTO gdelt_panel
        SELECT * FROM tidy
        WHERE variable NOT IN (SELECT DISTINCT variable FROM gdelt_panel)
    """)

    # Add to feature_panel view
    db.conn.execute("""
        CREATE OR REPLACE VIEW feature_panel AS
        SELECT * FROM external_factors
        UNION ALL SELECT * FROM extended_factors
        UNION ALL SELECT * FROM imf_factors
        UNION ALL SELECT * FROM gdelt_panel       -- includes Deep vars now
        UNION ALL SELECT * FROM macrostructure_factors
        UNION ALL SELECT * FROM bloomberg_factors
        UNION ALL SELECT * FROM normalized_panel
    """)
```

### Step 5: Create Neo4j Factor nodes

```python
from scripts.db_bridge import AsadoDB
from neo4j import GraphDatabase

DRIVER = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "mythos2026"))

# Define factor metadata for each Deep family
DEEP_FACTOR_FAMILIES = {
    "THEME ATTENTION": {
        "category": "gdelt_deep_theme",
        "description": "News article theme attention share — from GKG V2Themes",
        "variable_count": 568,
    },
    "GCAM EMOTIONAL DIMENSIONS": {
        "category": "gdelt_deep_gcam",
        "description": "Curated GCAM emotional/sentiment dictionary dimensions — from GKG GCAM field",
        "variable_count": 450,
    },
    "EVENT AGGREGATES": {
        "category": "gdelt_deep_event",
        "description": "CAMEO-coded geopolitical event aggregates — from GDELT EVENTS + EVENTMENTIONS",
        "variable_count": 120,
    },
}

with AsadoDB() as db:
    variables = db.conn.execute(
        "SELECT DISTINCT variable, source FROM gdelt_deep_panel"
    ).fetchall()

with DRIVER.session() as session:
    for variable, source in variables:
        family = {
            "gdelt_deep_theme": "THEME ATTENTION",
            "gdelt_deep_gcam": "GCAM EMOTIONAL DIMENSIONS",
            "gdelt_deep_event": "EVENT AGGREGATES",
        }.get(source, "GDELT DEEP")

        session.run("""
            MERGE (f:Factor {name: $name})
            SET f.category = $category,
                f.source = $source,
                f.family = $family
        """, name=variable, category=source, source="gdelt_deep", family=family)

    # Create edges from countries to their latest deep factor values
    session.run("""
        MATCH (c:Country)
        MATCH (f:Factor)
        WHERE f.source IN ['gdelt_deep_theme', 'gdelt_deep_gcam', 'gdelt_deep_event']
          AND f.category IS NOT NULL
        MERGE (c)-[:HAS_DEEP_FACTOR]->(f)
    """)
```

### Step 6: Rebuild embeddings with Deep features

The country-state PCA embeddings (`state_embedding` on Country nodes) currently use 332 variables. To incorporate Deep features, append them to the feature matrix before PCA:

```python
# In build_embeddings.py or a new script:
import pandas as pd
from sklearn.decomposition import PCA

# Load existing feature matrix + Deep tidy
existing = db.query_panel("SELECT * FROM feature_panel WHERE variable NOT LIKE 'gdelt_deep_%'")
deep = db.query_panel("SELECT * FROM gdelt_deep_panel")

# Pivot both to wide (countries × variables)
existing_wide = existing.pivot(index="country", columns="variable", values="value")
deep_wide = deep.pivot(index="country", columns="variable", values="value")

# Join
combined_wide = existing_wide.join(deep_wide, how="left")

# Re-run PCA
pca = PCA(n_components=34)  # or 64, 128
embeddings = pca.fit_transform(combined_wide.fillna(combined_wide.mean()))

# Store back to Neo4j Country.state_embedding
```

---

## Pipeline Summary (How It Was Built)

```
GDELT GKG v2 (daily 15-min ZIPs, 4,064 days)
  │
  ├─→ build_article_daily.py        # Extract per-article themes + GCAM + country
  │     ├─→ article_themes_daily/   # 4,064 parquet files (binary theme indicators)
  │     └─→ article_gcam_daily/     # 4,064 parquet files (density-normalized GCAM)
  │
  ├─→ build_theme_features.py       # Aggregate: articles → country-day theme shares
  │     └─→ country_themes_daily.parquet (724 rows × 572 cols in test)
  │
  ├─→ build_gcam_features.py        # Aggregate: articles → country-day GCAM means
  │     └─→ country_gcam_daily.parquet (725 rows × 78 cols in test)
  │
  ├─→ fetch_events.py               # BigQuery backfill + HTTP daily for CAMEO events
  ├─→ normalize_events.py           # Parse TSVs, join events+mentions, FIPS→ISO3
  ├─→ build_event_features.py       # Aggregate to country-day (24 event features)
  │     └─→ country_events_daily.parquet
  │
  ├─→ merge_news_modality.py        # LEFT JOIN all families onto base panel
  │     └─→ country_news_modality.parquet (122,729 rows × 720 cols)
  │
  ├─→ join_to_daily_panel.py        # Join Deep features onto existing daily signal panel
  │     └─→ country_signal_daily_deep.parquet
  │
  ├─→ build_monthly_metronome.py    # Month-end snapshots + core metronome composites
  │     └─→ country_signal_monthly_deep.parquet
  │
  └─→ build_monthly_deep_treatments.py  # EWMA fast/slow/trend + z-scores for all Deep families
        └─→ country_signal_monthly_deep_treated.parquet  ★ (32,067 × 1,221)
```

**Backfill status:** Running (16 workers, ~55% complete as of 2026-04-27). Once complete, the full pipeline runs as a single sequence of commands documented in the GDELT repo's `Deep/` directory.

---

## Variable Reference

For the complete variable-level documentation, consult these schema files:

| File | Contents |
|---|---|
| `GDELT/Deep/scripts/schema/gdelt_themes.yaml` | All 300 theme names with GDELT cumulative frequency counts |
| `GDELT/Deep/scripts/schema/gcam_dimensions.yaml` | All 75 GCAM dictionary keys (c6.x, v10.x, etc.), human-readable names, types (count/value), and dictionary blocks |
| `GDELT/Deep/scripts/schema/cameo_codes.yaml` | CAMEO EventRootCode → QuadClass mapping, EventRootCode labels, CAMEO→ISO3 country code overrides |
| `GDELT/Deep/data/features/GDELT_Deep.xlsx` | Full Excel workbook — **README** sheet (architecture overview), **README_VARIABLES** sheet (1,222 rows with sheet name, pipeline column, family, stage, and definition for every variable) |

The GDELT_Deep.xlsx **README_VARIABLES** sheet is the definitive reference — it documents every variable with its exact pipeline column name, feature family, pipeline stage, and formula/definition.

---

## Key Differences from Existing GDELT Signals

| Aspect | Existing GDELT (gdelt_panel) | Deep |
|---|---|---|
| **Frequency** | Monthly | Daily → monthly (same cadence after aggregation) |
| **Row count** | 407,864 | ~400,000 (when added to tidy format) |
| **Variable count** | 92 | +1,130 new (1,222 total including existing) |
| **Feature families** | 1 | 4 |
| **Data source in tidy** | `source = "gdelt"` | `source = "gdelt_deep_theme"`, `"gdelt_deep_gcam"`, `"gdelt_deep_event"` |
| **Country mapping** | T2 names directly | ISO3 → T2 names (via mapping dict) |
| **Look-ahead protection** | Z-scores shifted by 1 | Same convention |
| **Neo4j node label** | Factor | Factor (with `source = "gdelt_deep"` and `family` property) |

---

## Quick Start (Once Backfill Complete)

```bash
# In GDELT repo:
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/GDELT"

# 1. Join Deep onto daily panel
python3 Deep/scripts/join_to_daily_panel.py \
  --daily-panel data/panels/country_signal_daily.parquet \
  --themes Deep/data/features/country_themes_daily.parquet \
  --gcam Deep/data/features/country_gcam_daily.parquet \
  --events Deep/data/features/country_events_daily.parquet \
  --output data/panels/country_signal_daily_deep.parquet

# 2. Build monthly (in Complete/GDELT repo)
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Complete/GDELT"
python3 scripts/build_monthly_metronome.py \
  --daily-panel-parquet "../A Working/GDELT/data/panels/country_signal_daily_deep.parquet"

# 3. Add treatments (EWMA + z-scores)
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/GDELT"
python3 Deep/scripts/build_monthly_deep_treatments.py \
  --monthly-panel <monthly_from_step2>.parquet \
  --output Deep/data/features/country_signal_monthly_deep_treated.parquet

# 4. Ingest into ASADO (see Ingestion section above)
```

---

**Last Updated:** 2026-04-27  
**Repo:** `AAA Backup/A Working/GDELT/Deep/`  
**Documentation:** `GDELT_Deep.xlsx` README + README_VARIABLES sheets (1,222 variables documented)  
**Schema YAMLs:** `gcam_dimensions.yaml`, `gdelt_themes.yaml`, `cameo_codes.yaml`
