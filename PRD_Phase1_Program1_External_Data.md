# PHASE 1 — PROGRAM 1: EXTERNAL DATA ACQUISITION
## Product Requirements Document v1.0

**Project:** Country Equity Autoresearch  
**Author:** Arjun Divecha  
**Date:** March 2026  
**Status:** Ready for implementation  
**Runtime:** Any machine with Python 3.9+ and internet access (no Bloomberg required)

---

## 1. PURPOSE

Build a single Python script (`collect_external.py`) that downloads, parses, and caches data from seven free external sources, aligns everything to the existing 34-country T2 Master universe, and outputs a tidy-format panel file. This program runs independently of Bloomberg.

---

## 2. WHY THESE SPECIFIC SOURCES

The literature survey (Asness/Moskowitz/Pedersen 2013, Zaremba 2019, Caldara/Iacoviello 2022, Macrosynergy 2024) identified these as the highest-value free data sources NOT already captured in the existing 53-factor T2 system:

| Source | Academic Evidence | Why It's Missing from T2 |
|--------|------------------|--------------------------|
| BIS credit-to-GDP gap | Best single crisis predictor per Basel III (Drehmann et al. 2011) | Financial cycle variable, not a standard Bloomberg field |
| EPU indices | Policy uncertainty predicts 1.5% market decline per 1-std shock (Brogaard/Detzel 2015) | News-based index, constructed from newspaper text |
| GPR index | Orthogonal to both EPU and VIX (Caldara/Iacoviello 2022, AER) | Geopolitical risk, different methodology from EPU |
| OECD CLIs | 1.43%/mo top-bottom quintile spread (Zaremba et al. 2022) | Leading indicator composite, partially overlaps with GDP but leads by 6-9 months |
| BIS property prices | Amplifies credit gap signal for crisis prediction (Aldasoro 2018) | Housing cycle variable not in Bloomberg equity data |
| BIS REER | Cross-check for existing REER factor; BIS methodology differs from Bloomberg | Different basket weights and calculation method |
| World Bank governance | Governance quality predicts country equity returns (Journal of Banking & Finance) | Annual structural indicators, too slow-moving for Bloomberg |

---

## 3. EXISTING INFRASTRUCTURE

### 3.1 T2 Master Dataset
- **Location:** `/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/`
- **Normalized CSV:** `Normalized_T2_MasterCSV.csv` — 1,185,036 rows, tidy format (date, country, value, variable)
- **Raw Excel:** `T2 Master.xlsx` — 58 sheets, wide format (dates × 34 countries)
- **Optimizer:** `T2_Optimizer.xlsx` — 82 columns of monthly top-20% quintile net returns
- **Date range:** February 2000 – March 2026 (314 months)
- **Countries:** 34 (see Section 5 for full list)
- **Variables:** 111 (53 factors × 2 normalizations + 5 raw returns)

### 3.2 Country Mapping Config
- **Location:** `/Users/arjundivecha/Dropbox/AAA Backup/A Working/Country-Autoresearch/config/country_mapping.json`
- **Contents:** Maps each of the 34 T2 country names to ISO-2, ISO-3, IMF, OECD, BIS, World Bank, FRED/EPU, and GPR codes
- **Status:** Already created

### 3.3 Project Directory
- **Location:** `/Users/arjundivecha/Dropbox/AAA Backup/A Working/Country-Autoresearch/`
- **Structure:** `data/raw/`, `data/processed/`, `data/cache/`, `scripts/`, `config/`

---

## 4. OUTPUT SPECIFICATION

### 4.1 Primary Output
**File:** `data/processed/external_factors_panel.parquet` (and `.csv`)

**Format:** Tidy (long) format, identical structure to T2 Master CSV:

| Column | Type | Description |
|--------|------|-------------|
| date | datetime | First day of month (e.g., 2020-01-01) |
| country | string | T2 country name exactly as in T2 Master (e.g., "U.S.", "U.K.", "ChinaA") |
| value | float64 | Raw value (not normalized — normalization happens in Phase 2) |
| variable | string | Descriptive name (e.g., "EPU", "BIS_Credit_GDP_Gap", "OECD_CLI") |
| source | string | Data provenance (e.g., "epu", "bis_credit", "worldbank") |

### 4.2 Secondary Output
**File:** `data/processed/external_variable_catalog.csv`

**Contents:** One row per (source, variable) with: n_countries, n_observations, date_min, date_max, mean, std, pct_missing

### 4.3 Date Alignment Rules
- All dates must be first-of-month (e.g., 2020-01-01 for January 2020)
- Quarterly data (BIS): assign to the first day of the quarter-end month (e.g., Q1 2020 → 2020-03-01)
- Annual data (World Bank): assign to December 1 of the year (e.g., 2020 → 2020-12-01)
- Monthly data: assign to the first of that month
- Daily source data: take the last available value on or before the last business day of each month

---

## 5. THE 34 TARGET COUNTRIES

The output must use these exact country names to match the T2 Master:

Australia, Brazil, Canada, Chile, ChinaA, ChinaH, Denmark, France, Germany, Hong Kong, India, Indonesia, Italy, Japan, Korea, Malaysia, Mexico, NASDAQ, Netherlands, Philippines, Poland, Saudi Arabia, Singapore, South Africa, Spain, Sweden, Switzerland, Taiwan, Thailand, Turkey, U.K., U.S., US SmallCap, Vietnam

**Important:** ChinaA, ChinaH, NASDAQ, U.S., US SmallCap all map to the same macro country but are separate entries in the T2 system. When a source provides data for "China," assign it to BOTH ChinaA and ChinaH. When a source provides data for "United States," assign it to U.S., NASDAQ, AND US SmallCap.

---

## 6. DATA SOURCE SPECIFICATIONS

### 6.1 Economic Policy Uncertainty (EPU)

**URL:** `https://www.policyuncertainty.com/media/All_Country_Data.xlsx`

**Description:** Monthly news-based policy uncertainty index. Higher values = more uncertainty. Constructed from newspaper article counts containing terms related to economy, policy, and uncertainty.

**Expected format:** Excel with Year and Month columns plus one column per country (country names as column headers).

**Output variable:** `EPU`

**Coverage:** ~22 countries, monthly, from ~1997 to present. Not all 34 T2 countries are covered — map what's available, skip the rest.

**Country mapping:** Use the `epu_col` field in `country_mapping.json`. Match column headers case-insensitively and with fuzzy substring matching (e.g., "United States" matches the EPU column).

**Gotchas:** Some months may have "." or blank cells instead of numbers. Convert to NaN and drop.

---

### 6.2 Geopolitical Risk Index (GPR)

**URL:** `https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls`

**Description:** Monthly index measuring geopolitical risk from newspaper text. Orthogonal to EPU — does NOT move during purely economic/financial distress or elections.

**Expected format:** Excel with date column (first column) and multiple columns with patterns like `GPRC_BRA` (country GPR), `GPR` (global), `GPRT` (threats), `GPRA` (acts).

**Output variables:**
- `GPR` — Country-specific geopolitical risk (from GPRC_XXX columns)
- `Global_GPR` — Global GPR index (same value for all 34 countries each month)
- `Global_GPR_Threat` — Global threat component (same for all)
- `Global_GPR_Act` — Global acts component (same for all)

**Country mapping:** Use `gpr` field in `country_mapping.json`. Try column patterns: `GPRC_{iso3}`, `GPRC_{iso2}`, `GPR_{iso3}`, `GPR_{iso2}`.

**Coverage:** ~18 countries with country-specific data; global index covers all months from 1985+.

---

### 6.3 BIS Credit-to-GDP Gap

**URL:** `https://data.bis.org/static/bulk/WS_CREDIT_GAP.csv`

**Description:** Quarterly. Deviation of credit-to-GDP ratio from its long-term HP-filtered trend (lambda=400,000). Positive values indicate excessive credit growth. This is the Basel III countercyclical capital buffer indicator. The single best early-warning indicator for banking crises.

**Expected format:** BIS bulk CSV with columns including `REF_AREA` (ISO-2 country code), `TIME_PERIOD` (date), `OBS_VALUE` (the gap value in percentage points).

**Output variable:** `BIS_Credit_GDP_Gap`

**Country mapping:** Use `bis` field (or `iso2` fallback) in `country_mapping.json` to match `REF_AREA`.

**Coverage:** ~44 economies, quarterly, from ~1961 to recent quarter.

**Processing notes:** The CSV may contain multiple series per country (different borrower sectors, different credit measures). If a column like `TC_BORROWERS` or `BORROWERS_CTY` exists, filter for `P` (private non-financial sector) or the broadest available measure. If multiple series exist per country-date, take the first and log a warning.

---

### 6.4 BIS Residential Property Prices

**URL:** `https://data.bis.org/static/bulk/WS_SPP.csv`

**Description:** Quarterly/monthly residential property price indices by country. Real and nominal versions available.

**Expected format:** Same BIS bulk CSV structure as credit gap.

**Output variable:** `BIS_Property_Price`

**Country mapping:** Same as credit gap (BIS/ISO-2 codes).

**Processing notes:** If a `UNIT_MEASURE` or `VALUE` column distinguishes real vs nominal, prefer real prices. If multiple series per country-date exist, take the first. Deduplicate on (date, country).

**Coverage:** ~60 economies, quarterly, from ~1970s to recent.

---

### 6.5 OECD Composite Leading Indicators (CLIs)

**Primary method:** SDMX API via `sdmx1` Python package

```python
import sdmx
oecd = sdmx.Client('OECD')
data = oecd.data('MEI_CLI', key='{country_codes}.LOLITOAA.STSA.M')
```

Where `{country_codes}` is a `+`-separated list of OECD 3-letter codes from `country_mapping.json`.

**Fallback URL:** `https://sdmx.oecd.org/public/rest/data/OECD.SDD.STES,DSD_KEI@DF_KEI,4.0/{codes}.M.LI.LOLITOAA.AA..?startPeriod=2000-01&format=csvfilewithlabels`

**Description:** Monthly composite leading indicator, amplitude-adjusted, designed to lead GDP turning points by 6-9 months. Value of 100 = long-term trend; above 100 = expansion; below 100 = contraction.

**Output variable:** `OECD_CLI`

**Country mapping:** Use `oecd` field in `country_mapping.json`. Only ~20 of the 34 T2 countries have OECD CLI data.

**Coverage:** G20 + selected others, monthly, from ~1960 to recent.

---

### 6.6 World Bank Indicators

**Method:** `wbgapi` Python package (no API key required)

```python
import wbgapi as wb
data = wb.data.DataFrame(indicator_code, economy=country_codes, time=range(2000, 2026))
```

**Indicators to pull:**

| WB Code | Output Variable | Description |
|---------|----------------|-------------|
| CC.EST | WB_Control_Corruption | Governance: control of corruption (-2.5 to +2.5) |
| GE.EST | WB_Govt_Effectiveness | Governance: government effectiveness |
| PV.EST | WB_Political_Stability | Governance: political stability / no violence |
| RQ.EST | WB_Regulatory_Quality | Governance: regulatory quality |
| RL.EST | WB_Rule_of_Law | Governance: rule of law |
| VA.EST | WB_Voice_Accountability | Governance: voice and accountability |
| NY.GDP.MKTP.KD.ZG | WB_GDP_Growth_Real | Real GDP growth (%) |
| FP.CPI.TOTL.ZG | WB_Inflation_CPI | CPI inflation (%) |
| FS.AST.PRVT.GD.ZS | WB_Domestic_Credit_GDP | Domestic credit to private sector (% of GDP) |
| CM.MKT.LCAP.GD.ZS | WB_Market_Cap_GDP | Stock market cap (% of GDP) |
| BN.CAB.XOKA.GD.ZS | WB_Current_Account_GDP | Current account (% of GDP) |
| BX.KLT.DINV.WD.GD.ZS | WB_FDI_Inflows_GDP | FDI inflows (% of GDP) |
| GC.DOD.TOTL.GD.ZS | WB_Govt_Debt_GDP | Government debt (% of GDP) |
| SL.UEM.TOTL.ZS | WB_Unemployment | Unemployment rate (%) |

**Country mapping:** Use `wb` field in `country_mapping.json` (ISO-3 codes). Note: Taiwan (`TWN`) is not in the World Bank database — skip it.

**Coverage:** Annual, 200+ countries, from 1960 to ~2023 (1-2 year lag on most recent data). Governance indicators available from 1996.

---

### 6.7 BIS Effective Exchange Rates (REER)

**URL:** `https://data.bis.org/static/bulk/WS_EER.csv`

**Description:** Monthly real and nominal effective exchange rates (trade-weighted). Broad basket (64 economies). Index base = 2020. A rising REER means the currency is appreciating in real terms.

**Expected format:** Same BIS bulk CSV structure. May have an `EER_TYPE` or `EER_BASKET_TYPE` column to distinguish real vs nominal and broad vs narrow.

**Output variable:** `BIS_REER`

**Processing notes:** Filter for real (not nominal) effective exchange rates. If an `EER_TYPE` column exists, look for values containing "R" or "Real". If a `EER_BASKET_TYPE` column exists, prefer "B" (broad). Deduplicate on (date, country).

**Country mapping:** Same as other BIS sources.

---

## 7. IMPLEMENTATION REQUIREMENTS

### 7.1 Dependencies
```
pandas
numpy
requests
openpyxl
pyarrow
wbgapi
sdmx1
```

### 7.2 Caching
- All raw downloads cached in `data/raw/` with 24-hour expiry
- Check file modification time before re-downloading
- If a download fails after 3 retries, log the error and continue with other sources
- Never fail the entire pipeline because one source is down

### 7.3 Error Handling
- Each source collection function must be wrapped in try/except
- Log all errors with source name, URL, and exception message
- If a source fails, the pipeline continues with remaining sources
- The final output should include a summary of which sources succeeded and which failed

### 7.4 Logging
- Print progress to stdout: `[1/7] Economic Policy Uncertainty indices...`
- For each source, print: number of observations, number of countries matched, date range
- At the end, print a summary table showing all variables, their coverage, and any gaps

### 7.5 Idempotency
- Running the script twice in 24 hours should produce identical output (cached downloads)
- Running after 24 hours should re-download fresh data
- Never append to existing output files — always overwrite

---

## 8. QUALITY CHECKS

The script must verify and print the following after assembly:

1. **All 34 countries present** (or explicitly log which are missing from each source)
2. **No duplicate (date, country, variable) rows**
3. **Date range sanity:** EPU/GPR/OECD should start before 2005; BIS before 2010; World Bank before 2005
4. **Value sanity:** No values exceeding 10x the historical standard deviation (likely parse errors)
5. **Coverage matrix:** Print a countries × sources matrix showing the number of observations per cell

---

## 9. SUCCESS CRITERIA

The program is complete when:

1. `external_factors_panel.parquet` exists and contains data from at least 5 of 7 sources
2. At least 25 of 34 countries have EPU data
3. At least 20 of 34 countries have BIS credit gap data
4. The variable catalog shows the expected date ranges and reasonable statistics
5. The panel merges cleanly with `Normalized_T2_MasterCSV.csv` on (date, country) without key conflicts
6. Total runtime is under 10 minutes (mostly download time)

---

## 10. WHAT THIS PROGRAM DOES NOT DO

- Does NOT normalize or z-score the data (that's Phase 2)
- Does NOT pull Bloomberg data (that's Program 2)
- Does NOT compute derived signals like "credit gap change" or "EPU z-score" (that's Phase 2)
- Does NOT merge with the T2 Master (that's Phase 2)
- Does NOT run any backtests or models (that's Phase 3+)
