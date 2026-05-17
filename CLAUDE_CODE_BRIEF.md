# ASADO Historical Phase 1 — Implementation Brief For Claude Code

**What this is:** A historical implementation brief for the original external-data build. The live ASADO warehouse is now broader than this Phase 1 scope. For current operational truth, start with `README.md`, `DATA_DICTIONARY.md`, `CLAUDE.md`, and `docs/factor_reference.md`.

**Project directory:** `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/`
**Config:** `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/country_mapping.json`
**T2 Master CSV:** `/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/Normalized_T2_MasterCSV.csv`
**GDELT monthly source:** `/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 GDELT/GDELT_Factors_MasterCSV.csv`
**World Bank commodity source:** Official World Bank Pink Sheet workbook, collected by `scripts/collect_wb_commodity_prices.py`.

## Current Reality Snapshot

ASADO now has one analytical warehouse in `Data/asado.duckdb` with monthly panels, daily T2/GDELT panels, optimizer return surfaces, prediction-market snapshots, an event log, bilateral portfolio holdings, macrostructure signals, Bloomberg signals, and World Bank commodity intelligence.

The return surfaces are the ultimate source of truth for performance questions:

- monthly returns: `factor_returns`
- daily returns: `factor_returns_daily`
- country/factor memberships: `factor_top20_membership`
- MCP access: `country_returns`, `factor_return_series`, `daily_factor_series`, `event_window`, `commodity_price_series`

Commodity updates are part of the monthly updater:

```bash
./venv/bin/python scripts/monthly_update.py
./venv/bin/python scripts/monthly_update.py --commodity-only
./venv/bin/python scripts/monthly_update.py --skip-wb-commodity
```

---

## Build Order

### Step 1: collect_external.py (the PRD's 7 sources)

Build a single Python script that downloads, parses, and caches data from 7 free sources, aligns to the 34-country T2 universe, and outputs a tidy panel. Full PRD is in `PRD_Phase1_Program1_External_Data.md` in this directory — it has every detail. Summary below.

### Step 2: collect_extended.py (sources 8-22)

Extend to the remaining 15 sources. Same output format, same caching/error handling patterns. Specs in `Phase1_Data_Collection_Plan.md` Sections 3 and 10.

### Step 3: Database setup (DuckDB + Neo4j)

Load all panels into DuckDB. Stand up Neo4j and populate the knowledge graph. Spec in `Phase1_Data_Collection_Plan.md` Section 5.

---

## Critical Context

### The 34 Countries (use these EXACT names in output)

```
Australia, Brazil, Canada, Chile, ChinaA, ChinaH, Denmark, France, Germany,
Hong Kong, India, Indonesia, Italy, Japan, Korea, Malaysia, Mexico, NASDAQ,
Netherlands, Philippines, Poland, Saudi Arabia, Singapore, South Africa,
Spain, Sweden, Switzerland, Taiwan, Thailand, Turkey, U.K., U.S.,
US SmallCap, Vietnam
```

**Mapping rules:**
- "China" data → assign to BOTH ChinaA AND ChinaH
- "United States" data → assign to U.S., NASDAQ, AND US SmallCap
- country_mapping.json has all code mappings (ISO-2, ISO-3, IMF, OECD, BIS, World Bank, EPU, GPR)

### Output Format

Tidy (long) format, identical to T2 Master CSV:

| Column | Type | Description |
|---|---|---|
| date | datetime | First day of month (e.g., 2020-01-01) |
| country | string | T2 country name exactly as above |
| value | float64 | Raw value (NOT normalized) |
| variable | string | Descriptive name (e.g., "EPU", "BIS_Credit_GDP_Gap") |
| source | string | Data provenance (e.g., "epu", "bis_credit") |

### Date Alignment Rules

- All dates → first-of-month (e.g., 2020-01-01 for January 2020)
- Quarterly data → first day of quarter-end month (Q1 2020 → 2020-03-01)
- Annual data → December 1 of year (2020 → 2020-12-01)
- Daily data → last available value on or before last business day of month

### File Outputs

```
data/processed/external_factors_panel.parquet  (primary)
data/processed/external_factors_panel.csv      (secondary)
data/processed/external_variable_catalog.csv   (metadata)
```

---

## Source-by-Source Quick Spec (Step 1: The 7 PRD Sources)

### 1. EPU — Economic Policy Uncertainty
```
URL:      https://www.policyuncertainty.com/media/All_Country_Data.xlsx
Variable: EPU
Method:   Download Excel. Year + Month columns + country columns as headers.
Mapping:  country_mapping.json → "epu_col" field. Case-insensitive fuzzy match.
Gotchas:  "." or blank cells → NaN → drop.
Coverage: ~22 of 34 countries.
```

### 2. GPR — Geopolitical Risk
```
URL:      https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls
Variables: GPR (country-specific from GPRC_XXX columns),
           Global_GPR, Global_GPR_Threat, Global_GPR_Act (same for all countries)
Method:   Download Excel. First column = date. Match GPRC_{iso3} or GPRC_{iso2}.
Mapping:  country_mapping.json → "gpr" field.
Coverage: ~18 country-specific + global for all 34.
```

### 3. BIS Credit-to-GDP Gap
```
URL:      https://data.bis.org/static/bulk/WS_CREDIT_GAP.csv
Variable: BIS_Credit_GDP_Gap
Method:   BIS bulk CSV. Columns: REF_AREA (ISO-2), TIME_PERIOD, OBS_VALUE.
          Filter for private non-financial sector: TC_BORROWERS = "P" or broadest.
          Quarterly → first of quarter-end month.
Mapping:  country_mapping.json → "bis" or "iso2" field → match REF_AREA.
Coverage: 30+ of 34.
```

### 4. BIS Property Prices
```
URL:      https://data.bis.org/static/bulk/WS_SPP.csv
Variable: BIS_Property_Price
Method:   Same BIS CSV structure. Prefer real over nominal (UNIT_MEASURE).
          Deduplicate on (date, country).
Coverage: 30+ of 34.
```

### 5. OECD CLI
```
Method:   SDMX via sdmx1 package:
          import sdmx; oecd = sdmx.Client('OECD')
          data = oecd.data('MEI_CLI', key='{codes}.LOLITOAA.STSA.M')
Fallback: https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_KEI@DF_KEI,4.0/{codes}.M.LI.LOLITOAA.AA..?startPeriod=2000-01&format=csvfilewithlabels
Variable: OECD_CLI
Mapping:  country_mapping.json → "oecd" field (3-letter OECD codes).
Coverage: ~20 of 34 (OECD members + partners only).
```

### 6. World Bank (28 indicators)
```
Method:   wbgapi package (no API key):
          import wbgapi as wb
          wb.data.DataFrame(indicator, economy=codes, time=range(2000, 2026))
Mapping:  country_mapping.json → "wb" field (ISO-3). Taiwan (TWN) not in WB — skip.
Coverage: 33 of 34 (missing Taiwan).
Frequency: Annual. Date → December 1 of year.
```

**Full indicator list (original 14 + 14 additions for demographics/climate/reserves):**

```python
WORLD_BANK_INDICATORS = {
    # Original 14 (from PRD)
    'CC.EST':               'WB_Control_Corruption',
    'GE.EST':               'WB_Govt_Effectiveness',
    'PV.EST':               'WB_Political_Stability',
    'RQ.EST':               'WB_Regulatory_Quality',
    'RL.EST':               'WB_Rule_of_Law',
    'VA.EST':               'WB_Voice_Accountability',
    'NY.GDP.MKTP.KD.ZG':    'WB_GDP_Growth_Real',
    'FP.CPI.TOTL.ZG':       'WB_Inflation_CPI',
    'FS.AST.PRVT.GD.ZS':    'WB_Domestic_Credit_GDP',
    'CM.MKT.LCAP.GD.ZS':    'WB_Market_Cap_GDP',
    'BN.CAB.XOKA.GD.ZS':    'WB_Current_Account_GDP',
    'BX.KLT.DINV.WD.GD.ZS': 'WB_FDI_Inflows_GDP',
    'GC.DOD.TOTL.GD.ZS':    'WB_Govt_Debt_GDP',
    'SL.UEM.TOTL.ZS':       'WB_Unemployment',

    # Demographics (for "New Normal" Dimension 2)
    'SP.POP.TOTL':           'WB_Population',
    'SP.POP.GROW':           'WB_Population_Growth',
    'SP.POP.DPND.OL':        'WB_OldAge_Dependency',
    'SL.TLF.TOTL.IN':        'WB_Labor_Force',
    'SL.TLF.CACT.FE.ZS':    'WB_Female_LFP',
    'SL.TLF.TOTL.FE.ZS':    'WB_Female_Labor_Share',

    # Macro risk (reserves + external debt)
    'FI.RES.TOTL.CD':        'WB_FX_Reserves',
    'FI.RES.TOTL.MO':        'WB_Import_Cover_Months',
    'DT.DOD.DECT.GN.ZS':     'WB_External_Debt_GNI',

    # Climate
    'EN.ATM.CO2E.PC':        'WB_CO2_Per_Capita',
    'EG.FEC.RNEW.ZS':        'WB_Renewable_Energy_Share',
    'EN.CLC.MDAT.ZS':        'WB_Climate_Disaster_Affected',

    # Additional structural
    'NE.TRD.GNFS.ZS':        'WB_Trade_Openness',
    'IC.BUS.EASE.XQ':         'WB_Ease_of_Business',
}
```

### 7. BIS REER
```
URL:      https://data.bis.org/static/bulk/WS_EER.csv
Variable: BIS_REER
Method:   Filter for real (not nominal) effective exchange rates.
          Prefer broad basket (EER_BASKET_TYPE = "B").
          Monthly. Deduplicate on (date, country).
Coverage: 32+ of 34.
```

---

## Engineering Requirements

### Dependencies
```
pip install pandas numpy requests openpyxl pyarrow wbgapi sdmx1 tqdm python-dotenv
```

### Caching
- Raw downloads → `data/raw/` with 24-hour expiry
- Check file mtime before re-downloading
- 3 retries on download failure, then log error and continue
- Never fail entire pipeline because one source is down

### Error Handling
- Each source collector in try/except
- Log: source name, URL, exception message
- Pipeline continues with remaining sources on any failure
- Final summary of successes and failures

### Logging
```
[1/7] Economic Policy Uncertainty indices...
      → 22 countries, 324 months, 1997-01 to 2026-03
[2/7] Geopolitical Risk indices...
      → 18 country-specific + 34 global, 492 months, 1985-01 to 2026-03
...
```

### Quality Checks (run after assembly)
1. All 34 countries present (or log which missing from each source)
2. No duplicate (date, country, variable) rows
3. Date range sanity: EPU/GPR/OECD before 2005; BIS before 2010; WB before 2005
4. No values > 10x historical std dev
5. Print countries × sources coverage matrix

### Success Criteria
1. `external_factors_panel.parquet` exists with data from ≥5 of 7 sources
2. ≥25 countries have EPU data
3. ≥20 countries have BIS credit gap data
4. Variable catalog shows expected date ranges
5. Panel merges cleanly with T2 Master CSV on (date, country)
6. Runtime under 10 minutes

---

## Extended Sources Quick Reference (Step 2)

Sources 8-22 are detailed in `Phase1_Data_Collection_Plan.md`. Key access methods:

| # | Source | Access | Key/Auth | Priority |
|---|---|---|---|---|
| 8 | IMF API | SDMX 2.1/3.0 | No key | High |
| 9 | UN Comtrade | REST API | Free key (comtradeplus.un.org) | High |
| 10 | ACLED | REST API | Free key (acleddata.com) | High |
| 11 | OFAC | Download XML/CSV | No key | High |
| 12 | IPU Parline | REST API | No key | High |
| 13 | BIS Additional | SDMX (same as #3/#4/#7) | No key | Medium |
| 14 | EIA | REST API | Free key (eia.gov) | Medium |
| 15 | FRED | REST API | Free key (fred.stlouisfed.org) | Medium |
| 16 | OECD Additional | SDMX (same as #5) | No key | Medium |
| 17 | WITS | REST API | No key | Medium |
| 18 | ILOSTAT | SDMX | No key | Medium |
| 19 | ECB | SDMX REST | No key | Medium |
| 20 | ND-GAIN (climate) | CSV download | No key | High (15% dimension weight) |
| 21 | FAOSTAT | REST API | No key | Medium |
| 22 | UNDP HDI | CSV download | No key | Medium |

---

## Database Setup (Step 3)

### DuckDB
```bash
pip install duckdb
```
Load all parquet files. DuckDB reads parquet natively — no ETL needed:
```python
import duckdb
con = duckdb.connect('mythos.duckdb')
con.execute("CREATE TABLE t2 AS SELECT * FROM 'Normalized_T2_MasterCSV.csv'")
con.execute("CREATE TABLE external AS SELECT * FROM 'data/processed/external_factors_panel.parquet'")
con.execute("CREATE TABLE gdelt AS SELECT * FROM 'path/to/country_signal_monthly.parquet'")
```

### Neo4j Community Edition
```bash
docker run -d --name neo4j -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/mythos2026 \
  -v $HOME/neo4j/data:/data \
  neo4j:5-community
```
```bash
pip install neo4j
```

Graph schema (nodes and edges) is fully specified in `Phase1_Data_Collection_Plan.md` Section 5.

---

## Reference Documents (all in this directory)

| File | What it contains |
|---|---|
| `PRD_Phase1_Program1_External_Data.md` | Detailed PRD for the 7-source collector — the primary build spec for Step 1 |
| `Phase1_Data_Collection_Plan.md` | Full 22-source plan with database architecture, graph schema, gap analysis |
| `T2.Readme.md` | T2 Master database structure — 58 sheets, normalization methods, output format |
| `GDelt Readme.md` | GDELT pipeline documentation — stages, signals, project structure |
| `factor-timing-lit-review.md` | Academic evidence on what drives factor returns — context for signal design |
| `Mythos Claude.md` | Mythos model capabilities and 20 research ideas — future architecture context |
| `Mythos ChatGPT.md` | ChatGPT's additions: knowledge graph proposal, factor autopsy, 15 more ideas |
| `GraphDatabase ChatGPT.md` | 19-source data stack proposal, 4-layer architecture, pull schedule |
