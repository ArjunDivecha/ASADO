# Mythos Phase 1: Country Data Collection & Database Plan

**Author:** Arjun Divecha / Claude  
**Date:** April 10, 2026  
**Status:** PHASE 1 DATA COLLECTION COMPLETE (April 12, 2026)  
**Scope:** Collect country-level data from free sources, build a hybrid DuckDB + Neo4j database to map relationships between factors that drive country equity returns across a 34-country universe.

### Completion Summary

**Built:** 26 sources across 3 collection programs (7 core + 12 extended + 7 IMF datasets).  
**Result:** 296,745 rows, 112 external variables + 111 T2 variables + 46 GDELT variables = 269 unified variables in DuckDB.  
**Skipped (5 sources):** UN Comtrade (API key broken), ACLED (needs registration), IPU Parline (403), WITS (403), BIS Banking Stats (graph enrichment only). Existing data provides adequate coverage for each gap.  
**Monthly update:** `python scripts/monthly_update.py` — single command refreshes everything.

---

## 1. What We Have Today

### Completed Data Assets

**T2 Master Dataset** — The core factor library. 58 sheets covering 53 factors across 34 countries, February 2000 to present. Normalized into both cross-sectional (CS) and time-series (TS) z-scores. Output: `Normalized_T2_MasterCSV.csv` (1.18M rows, tidy format). All Bloomberg-sourced. Covers valuation, momentum, macro, quality, technical, and commodity signals.

**GDELT Sentiment Pipeline** — Daily and monthly country-level news sentiment signals from the GDELT Global Knowledge Graph. Covers the same 34 countries from 2015 to present. Produces composite indicators (monthly_metronome, monthly_risk, monthly_defensive) plus granular features: local/foreign tone split, attention shocks, tone dispersion, and sentiment trend. Output: parquet + Excel workbook.

**Country Mapping Config** — A JSON file at `/config/country_mapping.json` that maps each of the 34 T2 country names to ISO-2, ISO-3, IMF, OECD, BIS, World Bank, FRED/EPU, and GPR codes. This is the Rosetta Stone for all source integration.

### The 34-Country Universe


| Developed Markets (17)                                                                                                                                    | Emerging Markets (17)                                                                                                                                        |
| --------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Australia, Canada, Denmark, France, Germany, Hong Kong, Italy, Japan, Netherlands, Singapore, Spain, Sweden, Switzerland, U.K., U.S., NASDAQ, US SmallCap | Brazil, Chile, ChinaA, ChinaH, India, Indonesia, Korea, Malaysia, Mexico, Philippines, Poland, Saudi Arabia, South Africa, Taiwan, Thailand, Turkey, Vietnam |


**Important mapping rules:** ChinaA and ChinaH both map to CHN. U.S., NASDAQ, and US SmallCap all map to USA. When a source provides "China" data, assign to both ChinaA and ChinaH. When a source provides "United States" data, assign to U.S., NASDAQ, and US SmallCap.

---

## 2. Architecture: The 4-Layer Ingestion Model

Every data source feeds into a consistent 4-layer architecture. This ensures the system is stable regardless of what model or analysis sits on top.

### Layer 1: Canonical Country Master

A static reference table that anchors everything. Fields: ISO3 code, country name variants, region/subregion, income bucket, DM/EM tag, currency code, ETF/index proxy mapping, major trading partners, central bank ID, election/parliament source mapping, T2 name (exact match to the T2 Master).

This already partially exists in `country_mapping.json`. Phase 1 enriches it into a full entity with graph relationships.

### Layer 2: Raw Source Collectors

Each source lands into raw files with a consistent schema:


| Field             | Description                                                  |
| ----------------- | ------------------------------------------------------------ |
| source_name       | e.g., "bis_credit", "imf_ifs", "acled"                       |
| source_series_id  | Original series identifier from the source                   |
| country_iso3      | ISO-3 country code                                           |
| date              | Observation date                                             |
| frequency         | daily / monthly / quarterly / annual                         |
| value             | Raw numeric value                                            |
| unit              | e.g., "percent", "index", "count"                            |
| as_of_timestamp   | When we downloaded this observation                          |
| vintage_timestamp | When the source last revised this observation (if available) |
| download_url_hash | For reproducibility and cache invalidation                   |


All raw downloads are cached in `data/raw/{source_name}/` with 24-hour expiry for daily sources, 7-day expiry for monthly, 30-day for quarterly/annual.

### Layer 3: Standardized Fact Tables

Raw data is normalized into frequency-aligned buckets:


| Bucket              | Frequency    | Date Convention            | Example Sources                     |
| ------------------- | ------------ | -------------------------- | ----------------------------------- |
| macro_monthly       | Monthly      | First of month             | OECD CLI, BIS REER, IMF IFS         |
| macro_quarterly     | Quarterly    | First of quarter-end month | BIS credit gap, BIS property prices |
| macro_annual        | Annual       | December 1 of year         | World Bank, WGI, FAOSTAT            |
| trade_monthly       | Monthly      | First of month             | UN Comtrade                         |
| flows_quarterly     | Quarterly    | First of quarter-end month | IMF CPIS                            |
| events_daily        | Daily        | Calendar date              | GDELT, ACLED                        |
| politics_structural | Event-driven | Date of event/update       | IPU Parline, OFAC                   |
| market_daily        | Daily        | Calendar date              | T2 prices, ECB FX                   |
| commodities_monthly | Monthly      | First of month             | EIA energy data                     |


All dates follow the T2 convention: first-of-month for monthly, first of quarter-end month for quarterly, December 1 for annual. This ensures clean merges with the existing T2 panel.

### Layer 4: Graph Edges

Relationships extracted from the data that power the knowledge graph. See Section 5 for the full schema.

---

## 3. The 19 Data Sources — Full Specification

Sources are organized into three tiers based on implementation priority.

### Tier 1: The PRD's 7 External Sources (Build First)

These are the highest-value free sources identified by the factor timing literature review. They fill specific gaps in the T2 system that are not available through Bloomberg.

---

#### Source 1: Economic Policy Uncertainty (EPU)


| Property                  | Value                                                                                                                                   |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| **URL**                   | `https://www.policyuncertainty.com/media/All_Country_Data.xlsx`                                                                         |
| **Frequency**             | Monthly                                                                                                                                 |
| **Coverage**              | ~22 countries, from ~1997                                                                                                               |
| **Output variable**       | `EPU`                                                                                                                                   |
| **Academic basis**        | Brogaard/Detzel 2015: policy uncertainty predicts 1.5% market decline per 1-std shock                                                   |
| **Why not in T2**         | News-based index, not a standard Bloomberg field                                                                                        |
| **Graph edges**           | COUNTRY → HAS_REGIME_SIGNAL → EPU_LEVEL                                                                                                 |
| **Implementation**        | Download Excel, parse Year/Month columns + country columns. Use `epu_col` from country_mapping.json. Handle "." and blank cells as NaN. |
| **Est. country coverage** | 22 of 34 (~65%)                                                                                                                         |


---

#### Source 2: Geopolitical Risk Index (GPR)


| Property                  | Value                                                                                                                  |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **URL**                   | `https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls`                                                       |
| **Frequency**             | Monthly                                                                                                                |
| **Coverage**              | ~18 countries with country-specific data; global index from 1985                                                       |
| **Output variables**      | `GPR` (country), `Global_GPR`, `Global_GPR_Threat`, `Global_GPR_Act`                                                   |
| **Academic basis**        | Caldara/Iacoviello 2022 (AER): orthogonal to both EPU and VIX                                                          |
| **Why not in T2**         | Different methodology from EPU, measures geopolitical risk specifically                                                |
| **Graph edges**           | COUNTRY → HAS_RISK_SIGNAL → GPR_LEVEL; COUNTRY → EXPOSED_TO → GEOPOLITICAL_EVENT_CLUSTER                               |
| **Implementation**        | Download Excel, match columns via `GPRC_{iso3}` or `GPRC_{iso2}` patterns. Global series assigned to all 34 countries. |
| **Est. country coverage** | 18 country-specific + 34 global (~53% specific, 100% global)                                                           |


---

#### Source 3: BIS Credit-to-GDP Gap


| Property                  | Value                                                                                                                                                                       |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **URL**                   | `https://data.bis.org/static/bulk/WS_CREDIT_GAP.csv`                                                                                                                        |
| **Frequency**             | Quarterly                                                                                                                                                                   |
| **Coverage**              | ~44 economies, from ~1961                                                                                                                                                   |
| **Output variable**       | `BIS_Credit_GDP_Gap`                                                                                                                                                        |
| **Academic basis**        | Drehmann et al. 2011: single best early-warning indicator for banking crises per Basel III                                                                                  |
| **Why not in T2**         | Financial cycle variable, not a standard Bloomberg field                                                                                                                    |
| **Graph edges**           | COUNTRY → HAS_CREDIT_CYCLE → CREDIT_GAP_STATE (expanding/contracting/extreme)                                                                                               |
| **Implementation**        | BIS bulk CSV with REF_AREA (ISO-2), TIME_PERIOD, OBS_VALUE. Filter for private non-financial sector (TC_BORROWERS = "P"). Quarterly → assign to first of quarter-end month. |
| **Est. country coverage** | 30+ of 34 (~88%)                                                                                                                                                            |


---

#### Source 4: BIS Residential Property Prices


| Property                  | Value                                                                                                                       |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------- |
| **URL**                   | `https://data.bis.org/static/bulk/WS_SPP.csv`                                                                               |
| **Frequency**             | Quarterly/Monthly                                                                                                           |
| **Coverage**              | ~60 economies, from ~1970s                                                                                                  |
| **Output variable**       | `BIS_Property_Price`                                                                                                        |
| **Academic basis**        | Aldasoro 2018: amplifies credit gap signal for crisis prediction                                                            |
| **Why not in T2**         | Housing cycle variable not in Bloomberg equity data                                                                         |
| **Graph edges**           | COUNTRY → HAS_PROPERTY_CYCLE → PROPERTY_PRICE_STATE                                                                         |
| **Implementation**        | Same BIS bulk CSV structure. Prefer real prices over nominal if UNIT_MEASURE column exists. Deduplicate on (date, country). |
| **Est. country coverage** | 30+ of 34 (~88%)                                                                                                            |


---

#### Source 5: OECD Composite Leading Indicators (CLIs)


| Property                  | Value                                                                                                                           |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| **URL**                   | SDMX API via `sdmx1` package, fallback CSV URL                                                                                  |
| **Frequency**             | Monthly                                                                                                                         |
| **Coverage**              | G20 + selected others, from ~1960                                                                                               |
| **Output variable**       | `OECD_CLI`                                                                                                                      |
| **Academic basis**        | Zaremba et al. 2022: 1.43%/mo top-bottom quintile spread                                                                        |
| **Why not in T2**         | Partially overlaps with GDP but leads by 6-9 months                                                                             |
| **Graph edges**           | COUNTRY → HAS_LEADING_INDICATOR → CLI_STATE (expanding/contracting/turning)                                                     |
| **Implementation**        | SDMX query for LOLITOAA.STSA.M series. Use `oecd` field from country_mapping.json. Only ~20 of 34 countries have OECD CLI data. |
| **Est. country coverage** | 20 of 34 (~59%)                                                                                                                 |


---

#### Source 6: World Bank Indicators (14 series)


| Property                  | Value                                                                                                                                                                                                                    |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **URL**                   | `wbgapi` Python package (no API key)                                                                                                                                                                                     |
| **Frequency**             | Annual (1-2 year lag)                                                                                                                                                                                                    |
| **Coverage**              | 200+ countries, from 1960                                                                                                                                                                                                |
| **Output variables**      | 14 series: 6 governance (CC.EST, GE.EST, PV.EST, RQ.EST, RL.EST, VA.EST), 8 macro/structural (GDP growth, CPI inflation, domestic credit/GDP, market cap/GDP, current account/GDP, FDI/GDP, govt debt/GDP, unemployment) |
| **Academic basis**        | Journal of Banking & Finance: governance quality predicts country equity returns                                                                                                                                         |
| **Why not in T2**         | Annual structural indicators, too slow-moving for Bloomberg                                                                                                                                                              |
| **Graph edges**           | COUNTRY → HAS_GOVERNANCE_PROFILE → GOVERNANCE_CLUSTER; COUNTRY → HAS_STRUCTURAL_RISK → RISK_BUCKET                                                                                                                       |
| **Implementation**        | Pull via wbgapi. Taiwan (TWN) not in World Bank — skip. Annual dates → December 1 of year.                                                                                                                               |
| **Est. country coverage** | 33 of 34 (~97%, missing Taiwan for most series)                                                                                                                                                                          |


---

#### Source 7: BIS Effective Exchange Rates (REER)


| Property                  | Value                                                                                                              |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **URL**                   | `https://data.bis.org/static/bulk/WS_EER.csv`                                                                      |
| **Frequency**             | Monthly                                                                                                            |
| **Coverage**              | 64 economies, from varies                                                                                          |
| **Output variable**       | `BIS_REER`                                                                                                         |
| **Academic basis**        | Cross-check for existing REER factor; BIS methodology (broad 64-economy basket) differs from Bloomberg             |
| **Why not in T2**         | Different basket weights and calculation method vs Bloomberg REER                                                  |
| **Graph edges**           | COUNTRY → HAS_FX_COMPETITIVENESS → REER_STATE                                                                      |
| **Implementation**        | Filter for real (not nominal) effective exchange rates. Prefer broad basket ("B"). Deduplicate on (date, country). |
| **Est. country coverage** | 32+ of 34 (~94%)                                                                                                   |


---

### Tier 2: High-Value Additions (Build Second)

These sources add dimensions the PRD sources don't cover: trade network structure, conflict precision, and higher-frequency macro.

---

#### Source 8: IMF Data API


| Property                  | Value                                                                                                                                                         |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Access**                | SDMX 2.1 / 3.0 API                                                                                                                                            |
| **Frequency**             | Monthly, quarterly, annual (varies by dataset)                                                                                                                |
| **Key datasets**          | IFS (International Financial Statistics), WEO (World Economic Outlook projections), BOP (Balance of Payments), CPIS (Coordinated Portfolio Investment Survey) |
| **Output variables**      | CPI inflation (monthly), unemployment (monthly), balance of payments components, WEO GDP/inflation forecasts, portfolio investment positions                  |
| **Why it matters**        | Higher-frequency macro than World Bank; WEO forecasts are consensus anchors for country views; CPIS gives cross-border investment flows                       |
| **Graph edges**           | COUNTRY → HAS_MACRO_REGIME → MACRO_STATE; COUNTRY → RECEIVES_PORTFOLIO_FLOWS_FROM → COUNTRY                                                                   |
| **Est. country coverage** | 34 of 34 (100%)                                                                                                                                               |


---

#### Source 9: UN Comtrade API


| Property                  | Value                                                                                                                                                                                                 |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Access**                | REST API (free key required)                                                                                                                                                                          |
| **Frequency**             | Monthly and annual                                                                                                                                                                                    |
| **Key data**              | Bilateral trade by product and partner                                                                                                                                                                |
| **Output variables**      | Export/import values by partner, export concentration (HHI), commodity export share, partner dependency ratios                                                                                        |
| **Why it matters**        | This is the single most important source for trade-network graph edges. Enables COUNTRY → TRADES_WITH → COUNTRY edges with weights. Critical for contagion modeling and commodity-shock transmission. |
| **Graph edges**           | COUNTRY → EXPORTS_TO → COUNTRY (weighted); COUNTRY → IMPORTS_FROM → COUNTRY (weighted); COUNTRY → EXPORT_EXPOSED_TO → COMMODITY_GROUP                                                                 |
| **Est. country coverage** | 34 of 34 (100%)                                                                                                                                                                                       |


---

#### Source 10: ACLED API


| Property                  | Value                                                                                                                                                            |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Access**                | REST API (free registration)                                                                                                                                     |
| **Frequency**             | Near-real-time (updated frequently)                                                                                                                              |
| **Key data**              | Conflict events, protests, political violence — geocoded with event types and fatality counts                                                                    |
| **Output variables**      | Monthly conflict event count, fatality count, protest intensity, political violence escalation score, event-type breakdown                                       |
| **Why it matters**        | Higher-fidelity conflict data than GDELT. GDELT tells you what the news *says* about a country; ACLED tells you what's actually *happening*. Orthogonal signals. |
| **Graph edges**           | COUNTRY → HAS_CONFLICT_EVENT → EVENT_CLUSTER; COUNTRY → CONFLICT_SPILLOVER_RISK → COUNTRY (via geographic proximity + shared border events)                      |
| **Est. country coverage** | 30+ of 34 (~88%, weaker for DM countries with low conflict)                                                                                                      |


---

#### Source 11: OFAC Sanctions List Service


| Property                  | Value                                                                                                                                               |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Access**                | Downloadable XML/CSV + API                                                                                                                          |
| **Frequency**             | As updated by OFAC                                                                                                                                  |
| **Key data**              | Sanctioned entities, sanctions programs, country exposures                                                                                          |
| **Output variables**      | Sanctions program flag per country, sanctioned entity count, sanctions-regime change events                                                         |
| **Why it matters**        | Sanctions state directly affects investability, capital flows, and risk premia. A binary "under sanctions" flag plus intensity measures.            |
| **Graph edges**           | COUNTRY → SUBJECT_TO → SANCTIONS_PROGRAM; COUNTRY → SANCTIONS_EXPOSURE_VIA → COUNTRY (for countries with heavy trade links to sanctioned countries) |
| **Est. country coverage** | 34 of 34 (100% — most countries simply have zero sanctions)                                                                                         |


---

#### Source 12: IPU Parline API


| Property                  | Value                                                                                                                                                 |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Access**                | REST API                                                                                                                                              |
| **Frequency**             | Event-driven (elections, parliament changes)                                                                                                          |
| **Key data**              | Parliamentary election dates, legislature structure, chamber details, ruling coalition context                                                        |
| **Output variables**      | Next election date, months to next election, parliament fragmentation index, recent election flag                                                     |
| **Why it matters**        | Political calendar is a first-order driver of country risk premia. Election proximity affects volatility, policy uncertainty, and reform probability. |
| **Graph edges**           | COUNTRY → HAS_PARLIAMENT → PARLIAMENT_ENTITY; COUNTRY → HAS_ELECTION_CALENDAR → NEXT_ELECTION_DATE                                                    |
| **Est. country coverage** | 32+ of 34 (~94%)                                                                                                                                      |


---

### Tier 3: Enrichment Sources (Build Third)

These sources add depth to specific dimensions — energy exposure, trade policy, labor markets, food/agriculture, FX, and development context.

---

#### Source 13: BIS Additional Series (Policy Rates, Debt Service, Banking Statistics)


| Property                  | Value                                                                                                                                                               |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Access**                | BIS SDMX API (same infrastructure as Tier 1 BIS sources)                                                                                                            |
| **Frequency**             | Daily (policy rates), quarterly (debt service, banking)                                                                                                             |
| **Output variables**      | Policy rate level, debt service ratio, cross-border banking claims/liabilities                                                                                      |
| **Why it matters**        | Policy rates are the core monetary policy instrument. Debt service ratios flag distress before CDS spreads move. Cross-border banking claims power contagion edges. |
| **Graph edges**           | COUNTRY → HAS_MONETARY_STANCE → RATE_REGIME; COUNTRY → HAS_BANKING_EXPOSURE_TO → COUNTRY                                                                            |
| **Est. country coverage** | 30+ of 34                                                                                                                                                           |


---

#### Source 14: U.S. EIA Open Data API


| Property                  | Value                                                                                                                                                                                                                                 |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Access**                | REST API (free key)                                                                                                                                                                                                                   |
| **Frequency**             | Monthly and annual                                                                                                                                                                                                                    |
| **Output variables**      | Oil/gas production and consumption, energy trade balance, electricity generation mix, energy import dependence ratio                                                                                                                  |
| **Why it matters**        | Energy exporter/importer classification is a first-order country characteristic for commodity-shock transmission. Chile (copper) and Saudi Arabia (oil) respond to commodity moves very differently from Japan and India (importers). |
| **Graph edges**           | COUNTRY → ENERGY_EXPORTER_OF → COMMODITY; COUNTRY → ENERGY_IMPORTER_OF → COMMODITY                                                                                                                                                    |
| **Est. country coverage** | 34 of 34 (100%)                                                                                                                                                                                                                       |


---

#### Source 15: FRED API


| Property                  | Value                                                                                                                                                          |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Access**                | REST API (free key)                                                                                                                                            |
| **Frequency**             | Varies by series                                                                                                                                               |
| **Output variables**      | Country-specific macro series where FRED provides the easiest access layer (e.g., sovereign CDS proxies, yield curves, credit spreads)                         |
| **Why it matters**        | Not an original publisher, but often the simplest access path for series that are hard to get from primary sources. Good for prototyping and cross-validation. |
| **Graph edges**           | Depends on series pulled                                                                                                                                       |
| **Est. country coverage** | Varies                                                                                                                                                         |


---

#### Source 16: OECD Additional Series (Business Confidence, Labor)


| Property                  | Value                                                                                                                  |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| **Access**                | OECD SDMX API (same infrastructure as CLI)                                                                             |
| **Frequency**             | Monthly                                                                                                                |
| **Output variables**      | Business confidence index (BCI), consumer confidence index (CCI), labor indicators                                     |
| **Why it matters**        | BCI and CCI are forward-looking sentiment measures from surveys, orthogonal to both GDELT news sentiment and OECD CLI. |
| **Graph edges**           | COUNTRY → HAS_SURVEY_SENTIMENT → CONFIDENCE_STATE                                                                      |
| **Est. country coverage** | 20 of 34 (~59%, OECD members + partners)                                                                               |


---

#### Source 17: World Bank WITS API


| Property                  | Value                                                                                                                                                               |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Access**                | REST API                                                                                                                                                            |
| **Frequency**             | Annual / period-based                                                                                                                                               |
| **Output variables**      | Tariff levels (simple/weighted average), trade concentration metrics, non-tariff barrier indicators                                                                 |
| **Why it matters**        | Tariff regime is a structural characteristic that affects trade sensitivity. Tariff escalation events are high-signal for country risk. Exposes UNCTAD TRAINS data. |
| **Graph edges**           | COUNTRY → HAS_TARIFF_REGIME → TARIFF_BUCKET; COUNTRY → TRADE_POLICY_EXPOSED_TO → COUNTRY                                                                            |
| **Est. country coverage** | 32+ of 34                                                                                                                                                           |


---

#### Source 18: ILOSTAT SDMX API


| Property                  | Value                                                                                                                                                                                                  |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Access**                | SDMX API                                                                                                                                                                                               |
| **Frequency**             | Monthly/quarterly/annual                                                                                                                                                                               |
| **Output variables**      | Unemployment rate (complementary to World Bank), labor force participation, employment composition, wage growth                                                                                        |
| **Why it matters**        | Labor market stress is a leading indicator of political instability and consumer spending. Employment composition (services vs. manufacturing vs. agriculture) is a structural country characteristic. |
| **Graph edges**           | COUNTRY → HAS_LABOR_REGIME → LABOR_STATE                                                                                                                                                               |
| **Est. country coverage** | 30+ of 34                                                                                                                                                                                              |


---

#### Source 19: ECB Data Portal API


| Property                  | Value                                                                                                                                                  |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **Access**                | SDMX REST API                                                                                                                                          |
| **Frequency**             | Daily (FX), monthly/quarterly (monetary)                                                                                                               |
| **Output variables**      | Daily FX reference rates, euro-area monetary aggregates, European country financial indicators                                                         |
| **Why it matters**        | High-quality daily FX data for European countries. Monetary aggregates provide a financial-conditions overlay for the European subset of the universe. |
| **Graph edges**           | COUNTRY → HAS_FX_REGIME → FX_STATE                                                                                                                     |
| **Est. country coverage** | 15-20 of 34 (European + major pairs)                                                                                                                   |


---

### Sources Explicitly Excluded (and Why)


| Source                   | Reason                                                                                                  |
| ------------------------ | ------------------------------------------------------------------------------------------------------- |
| IMF AREAER               | Subscription/approval-gated                                                                             |
| IEA Energy Data Centre   | Not fully open/free API                                                                                 |
| Google Trends API        | Approval-gated alpha program                                                                            |
| Commercial election APIs | Paywalled                                                                                               |
| FAOSTAT                  | Useful but lower priority for equity returns; add in Phase 2 if agricultural commodity exposure matters |
| UNCTAD Data Hub          | Weaker API layer; supplements World Bank/IMF rather than adds new dimensions                            |
| UNSD SDG API             | Useful as metadata enrichment but too slow-moving to affect equity returns directly                     |


---

## 4. Coverage Matrix: Sources × Countries

This matrix shows estimated coverage. A source covering "100%" means it has data for all unique ISO3 codes in the universe (not all 34 T2 names — recall that ChinaA/ChinaH share CHN, and U.S./NASDAQ/SmallCap share USA).


| Source          | DM Coverage     | EM Coverage | Overall | Key Gaps                                             |
| --------------- | --------------- | ----------- | ------- | ---------------------------------------------------- |
| EPU             | ~85%            | ~50%        | ~65%    | Vietnam, Philippines, Saudi Arabia, several small EM |
| GPR (country)   | ~70%            | ~40%        | ~53%    | Many EM; global index covers all                     |
| BIS Credit Gap  | ~95%            | ~80%        | ~88%    | Vietnam, Philippines potentially                     |
| BIS Property    | ~95%            | ~80%        | ~88%    | Similar to credit gap                                |
| OECD CLI        | ~90%            | ~35%        | ~59%    | Most non-OECD EM markets                             |
| World Bank      | ~100%           | ~95%        | ~97%    | Taiwan missing from most series                      |
| BIS REER        | ~100%           | ~88%        | ~94%    | Vietnam potentially                                  |
| IMF             | ~100%           | ~100%       | ~100%   | Best coverage                                        |
| UN Comtrade     | ~100%           | ~100%       | ~100%   | Best coverage                                        |
| ACLED           | ~50%            | ~95%        | ~88%    | Low conflict DM countries have sparse data           |
| OFAC            | ~100%           | ~100%       | ~100%   | Binary flag — all covered                            |
| IPU Parline     | ~95%            | ~95%        | ~94%    | Hong Kong (no parliament)                            |
| BIS Additional  | ~95%            | ~80%        | ~88%    | Similar to other BIS                                 |
| EIA             | ~100%           | ~100%       | ~100%   | Excellent coverage                                   |
| FRED            | varies          | varies      | varies  | Depends on series                                    |
| OECD Additional | ~90%            | ~35%        | ~59%    | Same as CLI                                          |
| WITS            | ~95%            | ~95%        | ~94%    | Generally excellent                                  |
| ILOSTAT         | ~95%            | ~85%        | ~88%    | Good                                                 |
| ECB             | ~80% (European) | ~20%        | ~50%    | Non-European countries sparse                        |


**Key insight:** Taiwan is the most systematically under-covered country across sources (excluded from World Bank, IMF political datasets). Vietnam and Philippines have gaps in financial-cycle data. These gaps are acceptable — the system should handle missing data gracefully, not require 100% coverage.

---

## 5. Database Architecture: Recommendation

### The Problem

You need a database that can:

1. Store time-series panel data (country × date × variable) efficiently for backtesting
2. Represent rich relationships between entities (countries, factors, commodities, institutions, events)
3. Support vector similarity search for finding analogous historical episodes
4. Handle mixed frequencies (daily through annual) without losing temporal alignment
5. Run on a single machine (no cloud cluster requirement for Phase 1)
6. Be queryable by Python code and, eventually, by LLM agents

### Evaluation of Options


| Criterion          | Neo4j + Vector         | FalkorDB             | Kuzu                 | DuckDB + NetworkX    | PostgreSQL + pgvector + Apache AGE |
| ------------------ | ---------------------- | -------------------- | -------------------- | -------------------- | ---------------------------------- |
| Graph queries      | Excellent (Cypher)     | Good (Cypher subset) | Good (Cypher subset) | Manual (NetworkX)    | Good (openCypher via AGE)          |
| Vector search      | Plugin (neo4j-vector)  | Built-in             | No                   | Requires extension   | pgvector excellent                 |
| Time-series perf   | Moderate               | Moderate             | Good                 | Excellent (DuckDB)   | Good                               |
| Ease of setup      | Docker or cloud        | Embedded             | Embedded             | pip install          | Docker                             |
| Python ecosystem   | Good (neo4j driver)    | Emerging             | Good                 | Excellent            | Excellent (psycopg2, SQLAlchemy)   |
| LLM agent friendly | Good (natural Cypher)  | Moderate             | Moderate             | Custom               | Moderate                           |
| Maturity           | Very mature            | Young                | Young                | Very mature (DuckDB) | Mature (PG), AGE maturing          |
| Cost               | Free Community Edition | Free                 | Free                 | Free                 | Free                               |
| Backup/portability | DB dumps               | Files                | Files                | Files                | pg_dump                            |


### Recommendation: Hybrid Architecture — DuckDB + Neo4j Community Edition

Use **two databases**, each doing what it's best at:

**DuckDB** for the time-series analytical layer. DuckDB is an embedded columnar database that is purpose-built for analytical queries on structured data. It reads and writes Parquet natively, handles the T2 tidy format perfectly, and runs complex window functions (rolling z-scores, expanding means) at extraordinary speed. Your existing panel data stays in Parquet files; DuckDB queries them in-place without loading everything into memory. This is your backtesting and factor computation engine.

**Neo4j Community Edition** for the knowledge graph layer. Neo4j is the most mature graph database, with the richest Cypher query language and the best tooling for visualization and LLM integration. The Community Edition is free and runs locally via Docker. Neo4j 5.x includes vector index support, which handles the embedding/similarity search requirement without a third tool. This is your relationship reasoning engine.

**The bridge:** A Python integration layer that:

- Writes panel data to Parquet files (queryable by DuckDB)
- Writes entity and relationship data to Neo4j
- Maintains a mapping table that links Neo4j entity IDs to DuckDB panel keys (country_iso3, date, variable)
- Provides a unified query interface for agents: "Give me all countries with BIS_Credit_GDP_Gap > 2 std AND TRADES_WITH any country currently under sanctions"

**Why not just one database?** Neo4j is not built for time-series analytics — running rolling z-scores across 1.2M rows in Cypher would be painful. DuckDB has no native graph traversal — finding "countries 2 hops from a crisis country in the trade network" requires manual coding. The hybrid approach plays to each tool's strengths.

**Vector embeddings:** Neo4j 5.x's vector index stores embeddings directly on nodes. Use this for: embedding country-month "state vectors" (concatenation of all normalized factors at that point in time) to enable similarity search ("find historical months most similar to Turkey's current factor profile"). Embedding model: a small local model (e.g., all-MiniLM-L6-v2 for text, or simply the raw factor vector for numeric similarity via cosine distance).

### Graph Schema

#### Node Types

```
(:Country {iso3, name, t2_name, region, income_bucket, dm_em, currency_code})
(:ETFProxy {ticker, name, country_iso3})
(:CentralBank {name, country_iso3, website})
(:Factor {name, category, t2_sheet_name, inversion_flag, description})
(:Commodity {name, category})  // oil, copper, gold, agriculture
(:SanctionsProgram {name, ofac_id, active})
(:Parliament {country_iso3, chamber_type, seats})
(:Election {country_iso3, date, type})  // parliamentary, presidential
(:CrisisEvent {name, start_date, end_date, type})  // Asian 97, GFC 08, etc.
(:DataSource {name, url, frequency, api_type})
(:RegimeState {name, type})  // risk-on, risk-off, tightening, easing, etc.
```

#### Edge Types

```
// Trade network (from UN Comtrade)
(:Country)-[:EXPORTS_TO {value_usd, share_of_total, year}]->(:Country)
(:Country)-[:IMPORTS_FROM {value_usd, share_of_total, year}]->(:Country)

// Commodity exposure (from EIA, trade data)
(:Country)-[:EXPORT_EXPOSED_TO {share_of_gdp}]->(:Commodity)
(:Country)-[:IMPORT_DEPENDENT_ON {share_of_gdp}]->(:Commodity)

// Financial linkages (from BIS banking statistics)
(:Country)-[:HAS_BANKING_EXPOSURE_TO {claims_usd, share}]->(:Country)

// Institutional structure
(:Country)-[:HAS_CENTRAL_BANK]->(:CentralBank)
(:Country)-[:HAS_PARLIAMENT]->(:Parliament)
(:Country)-[:REPRESENTED_BY]->(:ETFProxy)

// Risk and sanctions
(:Country)-[:SUBJECT_TO]->(:SanctionsProgram)
(:Country)-[:HAS_CRISIS_HISTORY]->(:CrisisEvent)

// Factor exposure (from T2 data — updated monthly)
(:Country)-[:HAS_FACTOR_EXPOSURE {date, cs_score, ts_score}]->(:Factor)

// Regime state (from regime detection — updated monthly)
(:Country)-[:IN_REGIME {date, probability}]->(:RegimeState)

// Contagion / spillover (derived from trade + banking + crisis history)
(:Country)-[:CONTAGION_RISK_FROM {weight, channel}]->(:Country)
```

#### Example Queries

"Which countries have credit gaps above 2 standard deviations AND export more than 10% of GDP to China?"

```cypher
MATCH (c:Country)-[:EXPORT_EXPOSED_TO]->(cn:Country {iso3: 'CHN'})
WHERE c.credit_gap_zscore > 2.0
RETURN c.name, c.credit_gap_zscore
```

"Find the 5 countries most similar to Turkey's current factor profile" — uses vector similarity on the country-month state embedding stored in Neo4j.

"Trace the contagion path from a China credit event to European markets" — graph traversal across trade and banking edges.

---

## 6. Implementation Sequence

### Phase 1A: PRD External Sources (Weeks 1-2)

**Goal:** Get `collect_external.py` working per the existing PRD specification.


| Step | Task                                                               | Dependencies               | Est. Time |
| ---- | ------------------------------------------------------------------ | -------------------------- | --------- |
| 1    | Validate `country_mapping.json` completeness for all 7 PRD sources | None                       | 2 hours   |
| 2    | Implement EPU collector                                            | country_mapping.json       | 3 hours   |
| 3    | Implement GPR collector                                            | country_mapping.json       | 3 hours   |
| 4    | Implement BIS Credit Gap collector                                 | country_mapping.json       | 4 hours   |
| 5    | Implement BIS Property Price collector                             | Step 4 (reuses BIS parser) | 2 hours   |
| 6    | Implement OECD CLI collector                                       | country_mapping.json       | 4 hours   |
| 7    | Implement World Bank collector (14 indicators)                     | country_mapping.json       | 4 hours   |
| 8    | Implement BIS REER collector                                       | Step 4 (reuses BIS parser) | 2 hours   |
| 9    | Assembly: merge all into `external_factors_panel.parquet`          | Steps 2-8                  | 4 hours   |
| 10   | Quality checks per PRD Section 8                                   | Step 9                     | 2 hours   |
| 11   | Generate `external_variable_catalog.csv`                           | Step 9                     | 1 hour    |


**Output:** `data/processed/external_factors_panel.parquet` + `.csv`, variable catalog.

**Success criteria (from PRD):** Data from at least 5 of 7 sources; 25+ countries with EPU; 20+ countries with BIS credit gap; merges cleanly with T2 Master on (date, country).

### Phase 1B: Database Setup (Weeks 2-3)


| Step | Task                                           | Dependencies          | Est. Time |
| ---- | ---------------------------------------------- | --------------------- | --------- |
| 12   | Set up DuckDB with T2 Master CSV loaded        | T2 Master CSV exists  | 3 hours   |
| 13   | Load external_factors_panel into DuckDB        | Step 9                | 2 hours   |
| 14   | Load GDELT monthly panel into DuckDB           | GDELT pipeline exists | 2 hours   |
| 15   | Install Neo4j Community Edition (Docker)       | Docker available      | 2 hours   |
| 16   | Create Country nodes from country_mapping.json | Step 15               | 2 hours   |
| 17   | Create Factor nodes from T2 sheet catalog      | Step 15               | 2 hours   |
| 18   | Create ETFProxy, Commodity, CentralBank nodes  | Step 15               | 3 hours   |
| 19   | Build Python bridge (DuckDB ↔ Neo4j mapping)   | Steps 12-18           | 6 hours   |


**Output:** Working DuckDB analytical store + Neo4j graph with base entity nodes.

### Phase 1C: Tier 2 Sources (Weeks 3-5)


| Step | Task                                                | Dependencies         | Est. Time |
| ---- | --------------------------------------------------- | -------------------- | --------- |
| 20   | Implement IMF API collector (IFS + WEO + BOP)       | country_mapping.json | 8 hours   |
| 21   | Implement UN Comtrade collector + trade edges       | Neo4j running        | 8 hours   |
| 22   | Implement ACLED collector                           | country_mapping.json | 4 hours   |
| 23   | Implement OFAC sanctions collector + edges          | Neo4j running        | 4 hours   |
| 24   | Implement IPU Parline collector + election calendar | Neo4j running        | 4 hours   |
| 25   | Load all Tier 2 data into DuckDB                    | Steps 20-24          | 3 hours   |
| 26   | Create trade network edges in Neo4j (from Comtrade) | Step 21              | 4 hours   |
| 27   | Create sanctions edges in Neo4j (from OFAC)         | Step 23              | 2 hours   |
| 28   | Create political calendar nodes/edges (from IPU)    | Step 24              | 2 hours   |


**Output:** Significantly enriched graph with trade network, conflict data, sanctions state, and political calendar.

### Phase 1D: Tier 3 Sources + Integration (Weeks 5-7)


| Step | Task                                                                  | Dependencies           | Est. Time |
| ---- | --------------------------------------------------------------------- | ---------------------- | --------- |
| 29   | Implement BIS additional series (policy rates, debt service, banking) | BIS parser exists      | 4 hours   |
| 30   | Implement EIA energy collector                                        | country_mapping.json   | 4 hours   |
| 31   | Implement FRED collector (selected series)                            | API key                | 3 hours   |
| 32   | Implement OECD additional (BCI, CCI)                                  | OECD parser exists     | 3 hours   |
| 33   | Implement WITS tariff collector                                       | country_mapping.json   | 4 hours   |
| 34   | Implement ILOSTAT labor collector                                     | country_mapping.json   | 4 hours   |
| 35   | Implement ECB FX/monetary collector                                   | country_mapping.json   | 3 hours   |
| 36   | Load all Tier 3 into DuckDB + Neo4j edges                             | Steps 29-35            | 4 hours   |
| 37   | Create banking exposure edges (BIS banking stats)                     | Step 29                | 3 hours   |
| 38   | Create energy exposure edges (EIA)                                    | Step 30                | 2 hours   |
| 39   | Build vector embeddings for country-month states                      | All DuckDB data loaded | 6 hours   |
| 40   | Store embeddings in Neo4j vector index                                | Step 39                | 3 hours   |


### Phase 1E: Validation & Automation (Week 7-8)


| Step | Task                                                              | Dependencies   | Est. Time |
| ---- | ----------------------------------------------------------------- | -------------- | --------- |
| 41   | Full pipeline integration test (all 19 sources)                   | All collectors | 8 hours   |
| 42   | Build automated refresh scheduler (daily/monthly/quarterly)       | Step 41        | 6 hours   |
| 43   | Coverage audit: final source × country matrix                     | Step 41        | 3 hours   |
| 44   | Build data quality monitoring dashboard                           | Step 41        | 4 hours   |
| 45   | Documentation: data dictionary for all variables                  | Step 41        | 4 hours   |
| 46   | Merge test: join external panel with T2 Master on (date, country) | Step 41        | 2 hours   |


---

## 7. Refresh Schedule


| Cadence          | Sources                                                                                                  | Method                                                              |
| ---------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| **Daily**        | GDELT, ACLED, ECB FX                                                                                     | Automated cron job                                                  |
| **Weekly**       | OFAC sanctions list                                                                                      | Automated check for updates                                         |
| **Monthly**      | EPU, GPR, OECD CLI, BIS REER, IMF IFS monthly, OECD BCI/CCI, EIA monthly, ILOSTAT monthly                | Automated on 5th business day of month (allows for publication lag) |
| **Quarterly**    | BIS credit gap, BIS property prices, BIS debt service, BIS banking stats, UN Comtrade quarterly, IMF BOP | Automated 45 days after quarter end                                 |
| **Annual**       | World Bank (all 14), WITS tariffs, IMF WEO (April + October vintages)                                    | Automated in January (covers prior year) + April/October for WEO    |
| **Event-driven** | IPU Parline elections                                                                                    | Monthly check for updates                                           |


---

## 8. Python Dependencies

```
# Core
pandas>=2.0.0
numpy>=1.24.0
pyarrow>=12.0.0

# File formats
openpyxl>=3.1.0
xlsxwriter

# Data sources
wbgapi                  # World Bank
sdmx1                   # OECD, IMF, ILOSTAT, ECB (SDMX protocol)
requests                # REST APIs (EPU, GPR, ACLED, Comtrade, OFAC, FRED, EIA)

# Database
duckdb>=0.9.0           # Analytical time-series store
neo4j>=5.0.0            # Graph database Python driver

# Vector embeddings
sentence-transformers   # For text embedding (narrative similarity)
scikit-learn            # For numeric vector similarity (cosine, PCA)

# Utilities
tqdm                    # Progress bars
python-dotenv           # API key management
```

---

## 9. API Keys Required


| Source      | Key Required?  | How to Get                      |
| ----------- | -------------- | ------------------------------- |
| EPU         | No             | Direct download                 |
| GPR         | No             | Direct download                 |
| BIS (all)   | No             | Bulk CSV download               |
| OECD        | No             | SDMX API, no key                |
| World Bank  | No             | wbgapi, no key                  |
| IMF         | No             | SDMX API, no key                |
| UN Comtrade | **Yes** (free) | Register at comtradeplus.un.org |
| ACLED       | **Yes** (free) | Register at acleddata.com       |
| OFAC        | No             | Direct download                 |
| IPU Parline | No             | Public API                      |
| EIA         | **Yes** (free) | Register at eia.gov             |
| FRED        | **Yes** (free) | Register at fred.stlouisfed.org |
| ECB         | No             | SDMX API, no key                |
| ILOSTAT     | No             | SDMX API, no key                |
| WITS        | No             | REST API, no key                |


**Total keys needed:** 4 (all free registration). Store in `.env` file, never commit to git.

---

## 10. Gap Analysis: "New Normal" 7-Dimension Framework

The "New Normal" portfolio framework weights countries across 7 dimensions. This section maps each dimension to our data sources and flags what's missing.

### Dimension 1: Predicted Growth (20% weight)

Indicators: ROE, 5-year EPS growth, past GDP growth, sustainable growth rates.


| Indicator                       | Source in Plan                                       | Status                                                               |
| ------------------------------- | ---------------------------------------------------- | -------------------------------------------------------------------- |
| ROE                             | T2 Master (Best ROE sheet)                           | **Covered**                                                          |
| 5-year EPS growth               | T2 Master (LT Growth, Trailing EPS, Trailing EPS 36) | **Covered**                                                          |
| Past GDP growth                 | World Bank (WB_GDP_Growth_Real) + IMF WEO            | **Covered**                                                          |
| Sustainable growth rate         | Derivable from ROE × retention ratio                 | **Derivable** — needs Bloomberg payout ratio (T2 has dividend yield) |
| GDP nowcast / leading indicator | OECD CLI                                             | **Covered** (but only ~20 of 34 countries)                           |


**Gaps:** None critical. OECD CLI coverage is limited for EM — IMF WEO forecasts (already in Tier 2) partially fill this.

---

### Dimension 2: Demographics (15% weight)

Indicators: Total population, old-age dependency ratio change, labor force expansion/contraction, female labor force participation.


| Indicator                        | Source in Plan                                | Status                                                                                                 |
| -------------------------------- | --------------------------------------------- | ------------------------------------------------------------------------------------------------------ |
| Total population                 | World Bank (not in current 14-indicator pull) | **GAP — must add**                                                                                     |
| Old-age dependency ratio         | World Bank (not in current pull)              | **GAP — must add**                                                                                     |
| Labor force size / growth        | World Bank or ILOSTAT                         | **Partially covered** — ILOSTAT is Tier 3, and WB unemployment is in pull, but labor force size is not |
| Female labor force participation | World Bank or ILOSTAT                         | **GAP — must add**                                                                                     |


**Required additions to World Bank pull:**


| WB Code              | Variable                 | Description                                  |
| -------------------- | ------------------------ | -------------------------------------------- |
| SP.POP.TOTL          | WB_Population            | Total population                             |
| SP.POP.GROW          | WB_Population_Growth     | Population growth (annual %)                 |
| SP.POP.DPND.OL       | WB_OldAge_Dependency     | Age dependency ratio, old (% of working-age) |
| SP.POP.DPND.OL.FE.ZS | WB_OldAge_Dependency_Chg | (Compute change from level)                  |
| SL.TLF.TOTL.IN       | WB_Labor_Force           | Total labor force                            |
| SL.TLF.CACT.FE.ZS    | WB_Female_LFP            | Female labor force participation rate (%)    |
| SL.TLF.TOTL.FE.ZS    | WB_Female_Labor_Share    | Female share of labor force (%)              |


**Impact:** 7 additional World Bank indicators. No new source — just expand the existing wbgapi pull. Annual frequency, same as other WB data.

---

### Dimension 3: Macroeconomic Risk (15% weight)

Indicators: Macro/fiscal/financial vulnerabilities, CAD/GDP, budget balances, reserve adequacy.


| Indicator             | Source in Plan                                                    | Status               |
| --------------------- | ----------------------------------------------------------------- | -------------------- |
| Current account / GDP | T2 Master (Current Account) + World Bank (WB_Current_Account_GDP) | **Covered**          |
| Budget balance / GDP  | T2 Master (Budget Def)                                            | **Covered**          |
| Government debt / GDP | T2 Master (Debt to GDP) + World Bank (WB_Govt_Debt_GDP)           | **Covered**          |
| Credit-to-GDP gap     | BIS Credit Gap (Source 3)                                         | **Covered**          |
| Debt service ratio    | BIS Additional (Source 13, Tier 3)                                | **Covered**          |
| FX reserve adequacy   | Not in plan                                                       | **GAP — must add**   |
| External debt / GNI   | Not in plan                                                       | **GAP — should add** |


**Required additions:**


| Source     | Code              | Variable                | Description                                 |
| ---------- | ----------------- | ----------------------- | ------------------------------------------- |
| World Bank | FI.RES.TOTL.CD    | WB_FX_Reserves          | Total reserves including gold (current USD) |
| World Bank | FI.RES.TOTL.MO    | WB_Import_Cover         | Total reserves in months of imports         |
| IMF IFS    | via SDMX          | IMF_FX_Reserves_Monthly | Higher-frequency reserves (monthly)         |
| World Bank | DT.DOD.DECT.GN.ZS | WB_External_Debt_GNI    | External debt stocks (% of GNI)             |


**Impact:** 3 additional World Bank indicators + 1 IMF monthly series. Reserve adequacy is a first-order EM risk indicator — this is a meaningful gap.

---

### Dimension 4: Climate Risk (15% weight)

Indicators: Climate vulnerability, adaptation capacity, sea level risk, resource capacity to respond.


| Indicator                               | Source in Plan | Status        |
| --------------------------------------- | -------------- | ------------- |
| Climate vulnerability index             | Not in plan    | **MAJOR GAP** |
| Climate readiness / adaptation capacity | Not in plan    | **MAJOR GAP** |
| CO2 emissions per capita                | Not in plan    | **GAP**       |
| Renewable energy share                  | Not in plan    | **GAP**       |


**This entire dimension is missing from the plan.** The best free source is:

**ND-GAIN (Notre Dame Global Adaptation Initiative)**

- URL: `https://gain.nd.edu/our-work/country-index/` (downloadable CSV)
- Provides: Vulnerability score, Readiness score, and composite ND-GAIN index for 181 countries
- Frequency: Annual
- Sub-components: food, water, health, ecosystem, habitat, infrastructure (vulnerability); economic, governance, social readiness
- Coverage: Excellent — covers all 34 T2 countries
- API: No formal API, but stable CSV download
- This is widely used in ESG and sovereign risk models

**Additional climate sources:**


| Source     | Variable          | Description                  | Access                                        |
| ---------- | ----------------- | ---------------------------- | --------------------------------------------- |
| World Bank | EN.ATM.CO2E.PC    | WB_CO2_Per_Capita            | CO2 emissions per capita                      |
| World Bank | EG.FEC.RNEW.ZS    | WB_Renewable_Energy_Share    | Renewable energy % of total                   |
| World Bank | EN.CLC.MDAT.ZS    | WB_Climate_Disaster_Affected | % of population affected by climate disasters |
| EIA        | (already in plan) | Energy mix data              | Derivable — fossil fuel dependence ratio      |


**Impact:** 1 new source (ND-GAIN, ~20th source) + 3 World Bank indicators. Given this dimension is 15% of the framework weight, this is the single biggest gap in the plan.

---

### Dimension 5: Domestic Policy Risk (15% weight)

Indicators: Human Development Index, expropriation risk, rule of law, government effectiveness, regulatory quality, control of corruption.


| Indicator                         | Source in Plan                           | Status               |
| --------------------------------- | ---------------------------------------- | -------------------- |
| Rule of law                       | World Bank WGI (RL.EST)                  | **Covered**          |
| Government effectiveness          | World Bank WGI (GE.EST)                  | **Covered**          |
| Regulatory quality                | World Bank WGI (RQ.EST)                  | **Covered**          |
| Control of corruption             | World Bank WGI (CC.EST)                  | **Covered**          |
| Political stability / no violence | World Bank WGI (PV.EST)                  | **Covered**          |
| Voice and accountability          | World Bank WGI (VA.EST)                  | **Covered**          |
| Human Development Index (HDI)     | Not in plan                              | **GAP — should add** |
| Expropriation risk                | Not directly available from free sources | **GAP — partial**    |


**Required additions:**

**UNDP Human Development Index**

- URL: `https://hdr.undp.org/data-center/human-development-index` (downloadable CSV)
- Provides: HDI composite (life expectancy, education, GNI per capita), plus sub-indices
- Frequency: Annual
- Coverage: 190+ countries — all 34 T2 countries covered
- API: No formal API, but stable CSV/Excel download

Expropriation risk is harder — the classic source is the old ICRG (International Country Risk Guide), which is commercial. The World Bank's WGI "rule of law" and "regulatory quality" are reasonable proxies. The Fraser Institute's Economic Freedom Index is free and includes "legal system and property rights" — this could serve as a proxy.

**Impact:** 1 new source (UNDP HDI) + possibly Fraser Institute EFI. Domestic policy risk is otherwise well-covered by the 6 WGI indicators already in the plan.

---

### Dimension 6: Geopolitical Risk (10% weight)

Indicators: Net food export dependence, net energy export dependence, % of global trade, trade growth, "New World Order" risk.


| Indicator          | Source in Plan         | Status                                            |
| ------------------ | ---------------------- | ------------------------------------------------- |
| GPR index          | Source 2 (GPR)         | **Covered**                                       |
| Net energy exports | EIA (Source 14)        | **Covered**                                       |
| % of global trade  | UN Comtrade (Source 9) | **Covered** — derivable from bilateral trade data |
| Trade growth       | UN Comtrade (Source 9) | **Covered** — YoY change in total trade           |
| Net food exports   | FAOSTAT                | **GAP — was excluded from plan**                  |


**Required change:** Reinstate FAOSTAT as a Tier 3 source. The "New Normal" framework explicitly uses net food export dependence as a geopolitical risk indicator. This changes the cost/benefit calculation — FAOSTAT is no longer optional enrichment, it's a required input for a core dimension.

**FAOSTAT addition:**


| Property      | Value                                                                   |
| ------------- | ----------------------------------------------------------------------- |
| Access        | REST API (developer portal launched March 2026)                         |
| Key variables | Food export value, food import value, net food trade balance by country |
| Frequency     | Annual (some monthly)                                                   |
| Coverage      | 245+ countries                                                          |
| Graph edges   | COUNTRY → FOOD_EXPORT_DEPENDENT, COUNTRY → FOOD_IMPORT_DEPENDENT        |


**Impact:** Reinstate 1 previously excluded source. Net food dependence is straightforward to compute from FAOSTAT export/import values.

---

### Dimension 7: Diversification (10% weight)

Indicators: Correlation with EM index.


| Indicator                    | Source in Plan                       | Status                           |
| ---------------------------- | ------------------------------------ | -------------------------------- |
| Correlation with EM index    | Derivable from T2 Master return data | **Covered** — no new data needed |
| Rolling correlation dynamics | Derivable from T2 Master             | **Covered**                      |


**Gaps:** None. This is a computed metric, not a collected one.

---

### Summary: What's Missing


| Gap                                   | Dimension(s) Affected      | Priority     | Source to Add                                     |
| ------------------------------------- | -------------------------- | ------------ | ------------------------------------------------- |
| **Climate vulnerability + readiness** | Climate Risk (15%)         | **CRITICAL** | ND-GAIN (new source #20)                          |
| **Demographics indicators**           | Demographics (15%)         | **HIGH**     | World Bank (expand existing pull by 7 indicators) |
| **FX reserve adequacy**               | Macroeconomic Risk (15%)   | **HIGH**     | World Bank (3 indicators) + IMF monthly           |
| **Net food export dependence**        | Geopolitical Risk (10%)    | **MEDIUM**   | FAOSTAT (reinstate as source #21)                 |
| **Human Development Index**           | Domestic Policy Risk (15%) | **MEDIUM**   | UNDP HDI (new source #22)                         |
| **External debt / GNI**               | Macroeconomic Risk (15%)   | **MEDIUM**   | World Bank (1 indicator)                          |
| **Climate-related WB indicators**     | Climate Risk (15%)         | **MEDIUM**   | World Bank (3 indicators)                         |


**Net result:** The plan needs to grow from 19 to 22 sources (add ND-GAIN, FAOSTAT, UNDP HDI), and the World Bank pull needs to expand from 14 to ~28 indicators. No additional API keys are required — all three new sources are free downloads.

The biggest blind spot was **Climate Risk** — an entire 15%-weight dimension with zero data coverage. Demographics was the second-largest gap, also at 15% weight.

---

## 11. Risk Register


| Risk                                 | Impact                                                        | Mitigation                                                                                                       |
| ------------------------------------ | ------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| Source URL changes or goes down      | Pipeline breaks for that source                               | 24-hour cache + fallback URLs where available + graceful degradation (pipeline continues with remaining sources) |
| BIS CSV format changes               | BIS parsers break                                             | Version-pin the parser; log column names on each download for drift detection                                    |
| SDMX schema changes (OECD, IMF, ECB) | API queries return empty                                      | Pin dataset/dimension codes; test queries monthly                                                                |
| UN Comtrade rate limits              | Slow or failed downloads                                      | Respect rate limits; cache aggressively; batch by country                                                        |
| Taiwan coverage gaps                 | Incomplete factor set for Taiwan                              | Accept gracefully; Taiwan has Bloomberg data via T2, so the gap is in external/structural factors only           |
| Neo4j resource usage                 | Memory/disk pressure                                          | Start with Community Edition limits (no clustering); 34 countries × ~200 edges each is small for Neo4j           |
| Data vintage/revision risk           | Backtests use revised data that wasn't available in real time | Track vintage_timestamp in Layer 2; for sources with revision history (IMF WEO), store multiple vintages         |


---

## 12. What This Plan Does NOT Cover (Phase 2+)

This plan covers **data collection and database construction** only. The following are explicitly deferred:

- Factor normalization and z-scoring of external data (Phase 2)
- Derived signals (e.g., "credit gap change", "EPU z-score", "narrative divergence") (Phase 2)
- Merging external data into the T2 factor library (Phase 2)
- Backtesting and model construction (Phase 3)
- LLM agent integration for autonomous research (Phase 3)
- Causal discovery and factor graphs (Phase 3)
- Local-language sentiment processing (Phase 3)
- Central bank document parsing (Phase 3)
- Real-time regime detection (Phase 4)
- Multi-agent debate systems (Phase 4)

---

## 13. Success Criteria for Phase 1


| #   | Criterion                                                                                     | Status                                                                                                                              |
| --- | --------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| 1   | All accessible sources have working collectors                                                | **DONE** — 26/26 accessible sources built + bilateral trade (IMF IMTS) + banking (BIS LBS). 4 sources skipped (API access blocked). |
| 2   | DuckDB contains a unified panel queryable across all sources and T2 Master                    | **DONE** — 1.84M rows, 315 variables in `unified_panel` view.                                                                       |
| 3   | Neo4j contains entity graph with sanctions, factor exposure, crisis, trade, and banking edges | **DONE** — 425 nodes, 6,547 edges including 1,079 TRADES_WITH and 704 HAS_BANKING_EXPOSURE_TO bilateral edges.                      |
| 4   | External panel merges cleanly with T2 Master CSV on (date, country)                           | **DONE** — identical tidy schema, shared country names.                                                                             |
| 5   | Refresh scheduler runs without manual intervention                                            | **DONE** — `monthly_update.py` runs full pipeline in one command (~5 min).                                                          |
| 6   | At least 30/34 countries have data from at least 10 sources                                   | **DONE** — all 34 countries represented, most have 20+ sources.                                                                     |
| 7   | Vector embeddings for country-month states                                                    | **DONE** — 34d PCA vectors on Country nodes with cosine similarity index (`countryStateIndex`).                                     |
| 8   | Total pipeline runtime under 30 minutes                                                       | **DONE** — ~5 minutes.                                                                                                              |
| 9   | Data quality monitoring                                                                       | **PARTIAL** — variable catalogs and run history exist; formal dashboard deferred to Phase 2.                                        |


### Skipped Sources (access blocked, April 2026)


| Source      | Blocker                            | Covered by                                                    |
| ----------- | ---------------------------------- | ------------------------------------------------------------- |
| UN Comtrade | API key registration broken        | IMF IMTS bilateral trade (899 pairs), IMF ITG aggregate trade |
| ACLED       | Needs API key + email registration | GPR index, GDELT conflict signals                             |
| IPU Parline | API returning 403                  | OFAC sanctions, WGI governance indicators                     |
| WITS        | API returning 403                  | IMF trade data, World Bank trade openness, BIS REER           |


---

*This plan synthesizes requirements from: the PRD (Phase 1, Program 1), the factor timing literature review, the Claude Mythos capabilities assessment, the ChatGPT data source recommendations, the ChatGPT graph database architecture proposal, the GDELT pipeline documentation, and the T2 Master database reference.*