Here’s the right way to think about it: build a **country data spine** first, not a giant grab bag.

For your use case, the best free sources are the ones that are:

1. official or durable,
2. country-level,
3. machine-readable by API or predictable downloads,
4. updated on a known cadence,
5. broad enough to cover most of your 34-country universe.

I would **exclude** sources that are paywalled, approval-gated, or likely to break constantly. That means I would **not** make subscription-only sources like IMF AREAER part of the core automated stack, and I would not rely on alpha/approval-gated products like the Google Trends API as a core dependency. 

## **What to build around**

Use a 4-layer ingestion model:

**Layer 1: canonical country master**

- ISO3 country code
- country name variants
- region / subregion
- income bucket
- DM/EM tag
- currency code
- ETF/index proxy mapping
- trading partners
- central bank ID
- election/parliament source mapping

**Layer 2: raw source collectors**

Each source lands into raw files with:

- source_name
- source_series_id
- country_iso3
- date
- frequency
- value
- unit
- as_of_timestamp
- vintage_timestamp
- download_url/hash

**Layer 3: standardized fact tables**

Normalize everything into a few buckets:

- macro_monthly
- macro_annual
- trade_monthly
- flows_quarterly
- market_daily
- events_daily
- politics_structural
- commodities_daily_monthly

**Layer 4: graph edges**

Examples:

- COUNTRY -> HAS_CENTRAL_BANK -> CENTRAL_BANK
- COUNTRY -> TRADES_WITH -> COUNTRY
- COUNTRY -> EXPORT_EXPOSED_TO -> COMMODITY
- COUNTRY -> SUBJECT_TO -> SANCTIONS_PROGRAM
- COUNTRY -> HAS_FACTOR_EXPOSURE -> FACTOR
- COUNTRY -> HAS_RISK_EVENT -> EVENT_CLUSTER
- COUNTRY -> REPRESENTED_BY -> ETF_PROXY

That architecture is stable no matter what model sits on top.

# **Best free country-level data sources to automate**

## **A. Core macro and structural sources**

### **1. World Bank Indicators API**

This is one of your foundation sources. The World Bank says its Indicators API provides programmatic access to **nearly 16,000 time series indicators** across **45+ databases**. It is excellent for annual and some monthly country-level series: GDP, inflation, current account, debt, demographics, governance-linked indicators, education, energy, poverty, and development structure. 

Use it for:

- annual fundamentals
- demographic context
- debt / external balance context
- development and structural variables
- governance-related series available through World Bank data products

Cadence:

- mostly annual
- some quarterly/monthly depending on database

Access:

- official API
- easy JSON/XML pulls
- stable and well documented

### **2. IMF Data API (SDMX 2.1 / 3.0)**

This should be another core source. IMF states that its data are available through **SDMX 2.1 and 3.0 APIs**. This gives you programmatic access to datasets on inflation, unemployment, balance of payments, fiscal indicators, trade, WEO projections, and portfolio investment datasets. 

Use it for:

- CPI / inflation
- unemployment
- balance of payments
- fiscal indicators
- WEO forecast fields
- CPIS / portfolio positions
- external sector series

Cadence:

- monthly, quarterly, annual depending on dataset

Access:

- official SDMX API
- broad country coverage
- strong metadata, but more work than World Bank to map series cleanly

### **3. OECD Data API**

OECD’s Data Explorer supports programmatic retrieval through an API. It is very useful for OECD members and major partners where you want cleaner monthly business-cycle and sentiment data than many other public sources. 

Use it for:

- monthly leading indicators
- business tendency / confidence data
- labor and price data
- national accounts and sector indicators
- selected weekly tracker data context

Cadence:

- monthly, quarterly, annual

Access:

- official API
- especially strong for DM coverage
- not global enough to be your only source

### **4. BIS SDMX API**

BIS explicitly offers an SDMX API for its statistics portal. This is a very strong source for country-level financial conditions that most people underuse. BIS covers effective exchange rates, bilateral exchange rates, credit to the non-financial sector, credit-to-GDP gaps, debt service ratios, residential property prices, central bank assets, policy rates, and banking statistics. 

Use it for:

- REER / NEER
- policy rates
- credit-to-GDP
- debt service burden
- property price signals
- banking exposure / cross-border credit context
- central bank balance-sheet scale

Cadence:

- daily, monthly, quarterly depending on series

Access:

- official API
- excellent for financial regime mapping

### **5. FRED API**

FRED’s API is programmatic and FRED’s international category covers a very large number of country series. It is not the original publisher for all those datasets, but it is often the easiest access layer. 

Use it for:

- quick prototyping
- country macro series where you want a simpler pull than SDMX
- release/vintage work if you later care about backtest realism

Cadence:

- varies by series

Access:

- official API
- convenient, but source lineage must be preserved because FRED is often an aggregator

## **B. Trade, partner exposure, and external dependence**

### **6. UN Comtrade API**

UN Comtrade is one of the highest-value sources for your graph. The UN says the database aggregates detailed global **annual and monthly** trade statistics by product and trading partner, and the developer portal offers a free API key with stated rate limits. 

Use it for:

- bilateral trade edges
- export concentration
- import dependence
- sector export mix
- commodity export exposure
- partner dependency graphs

Cadence:

- monthly and annual

Access:

- official API
- free key available
- one of the best inputs for COUNTRY -> TRADES_WITH -> COUNTRY edges

### **7. World Bank WITS API**

WITS provides a REST API, and World Bank says it exposes aggregate trade and tariff data plus related development indicators. It also exposes UNCTAD TRAINS data through the API layer. 

Use it for:

- tariff levels
- trade concentration metrics
- trade competitiveness indicators
- partner/product breadth
- non-tariff and tariff regime context

Cadence:

- mostly annual / period-based, sometimes monthly depending on series

Access:

- official API
- very useful for policy and tariff edges in the graph

### **8. UNCTAD Data Hub**

UNCTAD Data Hub provides 150+ indicators and time series across economies. It is a good supplement for trade-and-development framing, FDI, maritime exposure, and structural trade context. I am less confident using it as a primary automated API because the public documentation surfaced more as a data hub/documentation layer than a clear general-purpose API. I’d treat it as **easy export / scrape supplement**, not a first-tier API dependency. 

Use it for:

- trade and development context
- FDI and structural openness
- supporting graph enrichment

Cadence:

- annual, some higher-frequency datasets

Access:

- good for exports/downloads
- weaker than World Bank/IMF/BIS for direct API-first engineering

## **C. Labor, agriculture, food, energy**

### **9. ILOSTAT SDMX API**

ILOSTAT is the ILO’s official labor statistics platform and provides SDMX-based programmatic access. It is the right place for unemployment, labor force participation, wages, labor underutilization, and employment structure. 

Use it for:

- labor stress
- employment composition
- wage and participation context
- labor-market regime edges

Cadence:

- monthly, quarterly, annual depending on series

Access:

- official SDMX
- strong for labor-side regime classification

### **10. FAOSTAT API**

FAOSTAT provides free access to food and agriculture data for 245+ countries and, as of March 2026, launched a developer portal/API to make programmatic access easier. 

Use it for:

- agricultural production
- food balance context
- fertilizer/land/use variables
- agricultural export dependence
- food inflation transmission context

Cadence:

- mostly annual, some monthly depending on domain

Access:

- official API / developer portal
- valuable for EM food and commodity exposure modeling

### **11. U.S. EIA Open Data API**

EIA’s open data program provides a free API, including international energy data organized by country. This is strong for oil/gas production, consumption, imports, exports, electricity, and fuel balances. 

Use it for:

- energy importer/exporter classification
- energy shock sensitivity
- power generation mix
- oil/gas dependence
- energy trade exposure

Cadence:

- annual, monthly, some quarterly depending on dataset

Access:

- official API
- strong for commodity-exposure edges

## **D. Daily / near-real-time event and narrative sources**

### **12. GDELT**

GDELT is still core for you. GDELT describes itself as a real-time open data global graph over news media, and says the entire database is free and open for raw downloads and large-scale analysis. It also has DOC, GEO, and Context APIs, and its map/search layers update at high frequency. 

Use it for:

- daily country event counts
- tone / dispersion
- topic attention
- foreign vs domestic narrative splits
- conflict and sanctions narrative tracking
- media-source network edges

Cadence:

- near-real-time / 15-minute style updates in parts of the system

Access:

- raw file downloads
- APIs
- BigQuery route if you want scale later

### **13. ACLED API**

ACLED offers an API and documents country/date filtering. This is a strong complement to GDELT when you care about higher-fidelity conflict and political violence event data rather than broad media-coded narrative flow. 

Use it for:

- conflict intensity
- protest risk
- political violence escalation
- event-type severity scoring
- geographic crisis spillover edges

Cadence:

- frequent updates

Access:

- official API
- very useful for COUNTRY -> HAS_RISK_EVENT -> EVENT_CLUSTER edges

### **14. OFAC Sanctions List Service**

OFAC’s Sanctions List Service provides downloadable, up-to-date sanctions list data and exposes an API/service layer. It is not a clean country-level panel by itself, but it is excellent for building sanctions-program and named-entity exposure edges. 

Use it for:

- sanctions regime tagging
- sanctioned entity counts by country
- sanctions-program exposure
- event flags for changes in sanctions environment

Cadence:

- as updated by OFAC

Access:

- official download/service
- easy automation for sanctions-state enrichment

## **E. Politics, institutions, and parliament structure**

### **15. IPU Parline API**

IPU Parline provides an API covering country, parliament, chamber, and election entities. This is one of the few global political/institutional sources that is free and machine-readable enough to be useful in a knowledge graph. 

Use it for:

- parliamentary election dates
- legislature structure
- chamber details
- ruling-coalition/parliament formation context
- women-in-parliament / institutional structure metadata

Cadence:

- event-driven / structural updates

Access:

- official API
- strong for the parliamentary side of political-calendar modeling

### **16. World Bank Worldwide Governance Indicators**

WGI is annual, not high-frequency, but it is useful as a structural layer for your graph. World Bank describes it as annual composite indicators across six governance dimensions for 200+ economies. 

Use it for:

- governance quality priors
- institutional fragility
- corruption / rule-of-law structural context
- slow-moving country risk priors

Cadence:

- annual

Access:

- downloadable / World Bank ecosystem
- good as graph context, not tactical timing

## **F. Currency, rates, and financial conditions**

### **17. ECB Data Portal API**

ECB’s Data Portal has an SDMX REST API and covers exchange rates, interest rates, money/credit, prices, and external-sector data. ECB specifically notes that exchange rates are usually updated around 16:00 CET on working days. 

Use it for:

- daily FX reference rates
- euro-linked cross rates
- euro-area and European country monetary/financial indicators
- external-sector and price data

Cadence:

- daily, monthly, quarterly depending on dataset

Access:

- official API
- especially useful if your country universe includes Europe heavily

### **18. BIS Effective and Bilateral Exchange Rates**

This is worth calling out separately even though it sits inside BIS. BIS effective exchange rates are explicitly described as long time series of nominal and real effective exchange rates useful for competitiveness and transmission-of-shock analysis. 

Use it for:

- REER competitiveness
- FX over/undervaluation context
- external shock transmission
- currency-regime stress overlays

Cadence:

- monthly/daily depending on series

Access:

- through BIS API

## **G. SDG / broad country benchmark layer**

### **19. UNSD SDG API**

UNSD exposes an SDG API and explicitly notes data extraction and availability APIs. This is a broad, official country-level benchmark layer across social, environmental, infrastructure, and development indicators. 

Use it for:

- country development baselines
- infrastructure and sustainability context
- slow-moving structural country descriptors

Cadence:

- mostly annual

Access:

- official API
- useful as a metadata/enrichment layer, not a tactical alpha layer

# **What I would classify by frequency**

## **Daily / near-real-time**

Best choices:

- GDELT 
- ACLED 
- ECB exchange rates 
- selected BIS FX / policy datasets 
- OFAC sanctions service

## **Monthly**

Best choices:

- IMF IFS-style datasets via IMF API 
- OECD indicators 
- BIS financial conditions / property / credit series 
- UN Comtrade monthly trade 
- EIA international energy data where monthly available

## **Quarterly / annual**

Best choices:

- World Bank Indicators API 
- WITS tariff/trade policy data 
- FAOSTAT 
- ILOSTAT annual/quarterly labor detail 
- UNSD SDG API 
- WGI / governance context 
- IMF CPIS / portfolio positions

# **My recommended “minimum viable country graph” source stack**

If you want the smallest set that still gives you real coverage, use these first:

1. **World Bank API** for structural and annual macro.
2. **IMF API** for macro, external sector, forecasts, and financial flows.
3. **BIS API** for financial conditions, FX, credit, banking, and rates.
4. **UN Comtrade API** for partner trade edges and export/import structure.
5. **WITS API** for tariffs and trade-policy structure.
6. **GDELT** for daily events, tone, themes, and narrative flow.
7. **ACLED** for conflict/protest/political violence precision.
8. **IPU Parline API** for parliamentary/election structure.
9. **OFAC SLS** for sanctions exposure.
10. **EIA API** for energy dependence/exposure.

That is enough to build a serious first version.

# **What I would not make core dependencies**

I would keep these out of the core spine for now:

- **IMF AREAER**, because it is positioned as a subscription product. 
- **IEA Energy Data Centre**, because while authoritative, it is not framed as a fully open/free API-first source the way EIA is. 
- **Google Trends API alpha**, because it exists but is approval-gated. 
- commercial election/calendar APIs, because you asked for no-fee sources.

# **Practical pull schedule**

Run:

- **daily**: GDELT, ACLED, ECB FX, BIS daily-rate/FX series, OFAC, ETF/index proxy prices from your market-data source
- **monthly**: IMF monthly series, OECD, BIS monthly series, UN Comtrade monthly, EIA monthly, selected ILOSTAT
- **quarterly/annual refresh**: World Bank, WGI, SDG, FAOSTAT, WITS, CPIS, deeper governance/institutional tables

That gives you a stable automated system without depending on fragile scraping for everything.

# **Blunt recommendation**

Do **not** start by trying to ingest every possible source.

Start with:

- World Bank
- IMF
- BIS
- UN Comtrade
- GDELT
- ACLED
- IPU
- OFAC

Those eight already cover:

- macro
- financial conditions
- trade network
- event risk
- conflict risk
- institutional politics
- sanctions

That is enough to make the graph actually useful.

Next step should be turning this into a **source-by-source build spec** with:

- endpoint type
- key fields
- frequency
- country coverage
- graph entities created
- graph edges created
- recommended refresh cadence
- data quality caveats

I can do that next and make it concrete enough for you to hand to a coder.