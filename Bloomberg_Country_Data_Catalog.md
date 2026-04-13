# Bloomberg Country-Level Data Catalog for ASADO

**Purpose:** Comprehensive reference of all country-level data available on the Bloomberg Terminal, organized for sovereign risk analysis and the ASADO database enrichment project.

**Date:** April 2026  
**Coverage:** 34 ASADO countries (see `config/country_mapping.json`)

---

## Table of Contents

1. [Key Bloomberg Functions for Country Data](#1-key-bloomberg-functions)
2. [ECST Category Tree (All Country-Level Indicators)](#2-ecst-category-tree)
3. [Sovereign Risk & Credit](#3-sovereign-risk--credit)
4. [Government Bonds & Yield Curves](#4-government-bonds--yield-curves)
5. [Foreign Exchange & Reserves](#5-foreign-exchange--reserves)
6. [Trade & Balance of Payments](#6-trade--balance-of-payments)
7. [ESG & Governance](#7-esg--governance)
8. [Bloomberg Ticker Naming Conventions](#8-ticker-naming-conventions)
9. [BLPAPI/Python Programmatic Access](#9-blpapipython-programmatic-access)
10. [Recommended Data to Add to ASADO](#10-recommended-data-to-add-to-asado)

---

## 1. Key Bloomberg Functions

These are the **non-security functions** (no ticker needed) that provide country-level data:

### 1A. Core Economics Functions


| Function | Name                      | What It Does                                                                                                                                                                          |
| -------- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **ECST** | World Economic Statistics | **Primary entry point.** Browse tens of thousands of economic indicators organized by country and category (GDP, CPI, employment, monetary, fiscal, external, etc.). Export to Excel. |
| **ECFC** | Economic Forecasts        | Consensus forecasts for GDP, CPI, unemployment, interest rates, etc. by country. Shows median, high, low, and individual analyst estimates.                                           |
| **ECO**  | Economic Calendar         | Upcoming economic releases by country. Shows prior, survey median, and actual values. Importance rating.                                                                              |
| **ECMX** | Global Economic Matrix    | Compare a single indicator across multiple countries for a selected date. Side-by-side comparison.                                                                                    |
| **ECWB** | Economic Workbench        | Chart and manipulate economic data. Apply transformations (YoY, moving averages, lead/lag, aggregation).                                                                              |
| **ECAN** | Economic Analysis         | Break economic data into its components.                                                                                                                                              |
| **ECOD** | Economic Release Details  | Drill into a specific economic release with historical values and related news.                                                                                                       |
| **ECOS** | Economic Estimates        | View economic estimates and consensus.                                                                                                                                                |
| **ECOF** | Economic Indicators       | Overview of key economic indicators by country.                                                                                                                                       |
| **ECTR** | Trade Flow                | Interactive map of import/export values between a country and its trading partners. Data back to 1980.                                                                                |


### 1B. Country Overview & Sovereign Functions


| Function | Name                           | What It Does                                                                      |
| -------- | ------------------------------ | --------------------------------------------------------------------------------- |
| **COUN** | Country/Region Guide           | Comprehensive overview: financial markets, news, key data for a selected country. |
| **CBQ**  | Country Directory              | Choose from 46+ countries for overview.                                           |
| **BTMM** | Treasury & Money Markets       | All major rates, securities, and economic releases for a selected country.        |
| **SOVM** | Sovereign Debt Market Overview | Overview of an individual country's sovereign debt market.                        |
| **WCDM** | World Country Debt Monitor     | Cross-country comparison of government debt metrics.                              |
| **DEBT** | Government Debt Ownership      | Who holds the debt of a given country.                                            |
| **DDIS** | Debt Distribution              | Maturity distribution of outstanding debt for an issuer (country or company).     |
| **BUDG** | Government Spending            | Plot government spending (primarily US, but available for some countries).        |


### 1C. Sovereign Risk & Credit Functions


| Function | Name                      | What It Does                                                                                                              |
| -------- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| **SRSK** | Sovereign Risk Model      | Bloomberg's quantitative model: 1-year default probability, 5-year CDS spread estimate. Transparent factor decomposition. |
| **SOVR** | Sovereign CDS Monitor     | Real-time sovereign CDS spreads for all countries. Sort by spread. Historical charting.                                   |
| **CSDR** | Sovereign Ratings         | Table of short/long-term credit ratings from all major agencies (S&P, Moody's, Fitch). Highlights recent changes.         |
| **RATC** | Rating Revisions Monitor  | Credit rating changes across issuers (filter to sovereigns).                                                              |
| **RATD** | Ratings Definitions       | Credit rating scales, definitions, and comparisons across agencies.                                                       |
| **CRP**  | Country Risk Premium      | Country risk premium estimates.                                                                                           |
| **DRSK** | Bloomberg Rating Model    | Bloomberg's proprietary credit rating model.                                                                              |
| **CDSW** | CDS Implied Probabilities | Calculate implied default probabilities from CDS spreads.                                                                 |
| **WCDS** | World CDS Pricing         | CDS pricing across all entities.                                                                                          |


### 1D. Fixed Income & Yield Curves


| Function | Name                      | What It Does                                                                           |
| -------- | ------------------------- | -------------------------------------------------------------------------------------- |
| **WB**   | World Bond Markets        | Sovereign bond yields, spreads, and performance across countries. Multiple maturities. |
| **WBF**  | World Bond Futures        | Government bond futures.                                                               |
| **GC**   | Graph Curves              | Chart yield curves. Compare across countries and over time.                            |
| **GC3D** | 3D Yield Curve            | 3-dimensional yield curve evolution over time.                                         |
| **GCT**  | Graph Curve Tenors        | Historical yield for a specific maturity point on the curve.                           |
| **CRVF** | Curve Finder              | Search for yield curves by asset class, country, sector.                               |
| **FIT**  | Fixed Income Trading      | Electronic trading platform for sovereign debt.                                        |
| **SRCH** | Bond Search               | Search government, corporate, and convert bonds.                                       |
| **ILBE** | Inflation Breakevens      | World inflation breakeven rates.                                                       |
| **BRMM** | World Interest Rates      | Global interest rate monitor.                                                          |
| **WIRP** | Interest Rate Probability | Implied probability of central bank rate moves.                                        |
| **FMCI** | Fair Market Curve Indices | Fair value curve indices.                                                              |
| **BYFC** | Bond Yield Forecast       | Consensus bond yield forecasts.                                                        |


### 1E. Foreign Exchange & Currency


| Function | Name                         | What It Does                                                    |
| -------- | ---------------------------- | --------------------------------------------------------------- |
| **FXC**  | Currency Rates Matrix        | Cross currency spot, forward, and fixing rates.                 |
| **WCRS** | World Currency Ranker        | Rank currencies by returns, interest rates, PPP, etc.           |
| **FXFC** | FX Forecasts                 | Composite FX forecasts by contributor.                          |
| **FXFM** | FX Rate Forecast Model       | Bloomberg's FX forecast model.                                  |
| **FXIP** | FX Information Portal        | Spot rates, forwards, options, and forecasts.                   |
| **WIRA** | International Reserve Assets | Track international reserve assets and growth rates by country. |
| **BFIX** | Currency Fixing Rates        | Official currency fixing rates.                                 |


### 1F. Inflation & Prices


| Function | Name                 | What It Does                                                                          |
| -------- | -------------------- | ------------------------------------------------------------------------------------- |
| **IFMO** | Inflation Monitor    | Inflation data for countries worldwide. Rates, targets, forecasts. Visual comparison. |
| **ILBE** | Inflation Breakevens | Market-implied inflation expectations from bond markets.                              |


### 1G. Macro Movers & Emerging Markets


| Function | Name                 | What It Does                                   |
| -------- | -------------------- | ---------------------------------------------- |
| **GMM**  | Global Macro Movers  | Biggest moves of the day across asset classes. |
| **GEW**  | Global Economy Watch | Real-time economic monitoring dashboard.       |
| **EMKT** | Emerging Markets     | EM-specific portal.                            |
| **EMMV** | EM Market View       | Emerging markets overview.                     |
| **EMEQ** | EM Equity Indices    | Emerging market equity index monitor.          |
| **OTC**  | EM Real-Time Monitor | Real-time emerging markets data.               |


---

## 2. ECST Category Tree

The **ECST** function is the single most important Bloomberg function for country macro data. When you select a country, the left sidebar presents a hierarchical category tree. Below is the **complete category structure** (categories may vary slightly by country based on data availability):

### 2A. National Accounts (GDP)

- **Real GDP by Expenditure** — GDP = C + I + G + (X - M)
  - Gross Domestic Product (real, nominal, per capita)
  - Personal Consumption Expenditure
  - Government Consumption
  - Gross Fixed Capital Formation
  - Exports of Goods & Services
  - Imports of Goods & Services
  - Net Exports
  - Change in Inventories
- **Nominal GDP by Expenditure** — Same breakdown in current prices
- **Real GDP by Industry/Sector** — Agriculture, Industry, Services, Manufacturing, Construction, Mining
- **Savings & Investment Rates** — Gross national savings, investment as % of GDP

### 2B. Inflation & Prices

- **Consumer Price Index (CPI)** — Headline, Core (ex food & energy), by component (food, energy, housing, transport, healthcare, education, apparel)
- **Producer Price Index (PPI)** — Input prices, output prices, by stage of processing
- **GDP Deflator**
- **Import/Export Prices**
- **House Price Indices** — Where available
- **Commodity Prices** — Country-specific commodity price impacts
- **Wage Price Index**

### 2C. Labor Market & Employment

- **Unemployment Rate** — Total, by age group, by gender
- **Employment** — Total employed, employment by sector
- **Labor Force** — Total labor force, participation rate
- **Non-farm Payrolls** (US) / equivalent measures by country
- **Average Weekly Hours**
- **Wages & Earnings** — Average hourly/weekly earnings, unit labor costs, productivity
- **Job Vacancies / Job Openings**
- **Initial Jobless Claims** / equivalent

### 2D. Monetary Sector

- **Central Bank Policy Rate** — Key interest rate
- **Money Supply** — M0, M1, M2, M3
- **Credit Growth** — Private sector credit, bank lending
- **Interbank Rates** — SOFR, EURIBOR, TIBOR, etc.
- **Central Bank Balance Sheet** — Total assets, reserves
- **Interest Rates** — Short-term, long-term, repo rates
- **Bank Reserves**

### 2E. Fiscal Sector / Government Finance

- **Government Revenue** — Tax revenue, total revenue, as % of GDP
- **Government Expenditure** — Total spending, as % of GDP
- **Budget Balance** — Fiscal deficit/surplus, as % of GDP
- **Government Debt** — Total debt, as % of GDP, external vs domestic
- **Primary Balance** — Budget balance excluding interest payments
- **Interest Payments** — Government debt servicing costs
- **Government Debt Maturity Profile** — Average maturity, rollover schedule

### 2F. External Sector / Balance of Payments

- **Current Account Balance** — as % of GDP, in USD
- **Trade Balance** — Goods balance, services balance
- **Exports** — Total, by commodity, by partner country
- **Imports** — Total, by commodity, by partner country
- **Foreign Direct Investment (FDI)** — Inflows, outflows, net
- **Portfolio Investment** — Inflows, outflows
- **International Investment Position (IIP)**
- **External Debt** — Total, short-term, long-term, as % of GDP, as % of exports
- **Foreign Exchange Reserves** — Total, excluding gold, gold holdings
- **Terms of Trade**
- **Real Effective Exchange Rate (REER)**
- **Current Account Components** — Primary income, secondary income

### 2G. Industrial Production & Activity

- **Industrial Production Index** — Total, manufacturing, mining, utilities
- **Manufacturing PMI** — Markit/S&P Global
- **Services PMI**
- **Composite PMI**
- **Capacity Utilization**
- **Factory Orders**
- **Retail Sales** — Total, ex-autos, by category
- **Consumer Confidence** — Various survey-based indices
- **Business Confidence** — Various survey-based indices
- **Building Permits / Housing Starts**
- **Vehicle Sales / Registrations**

### 2H. Financial Markets

- **Equity Index Levels** — Major domestic indices
- **Equity Market Capitalization** — Total market cap, as % of GDP
- **Bond Yields** — 2Y, 5Y, 10Y, 30Y government bond yields
- **Yield Curve Spread** — 10Y-2Y, 10Y-3M
- **Credit Spreads** — Investment grade, high yield
- **Stock Market Volatility**
- **Banking Sector Indicators** — NPL ratios, capital adequacy, ROE

### 2I. Demographics & Population

- **Total Population** — Mid-year estimate
- **Population Growth Rate**
- **Urban Population** — % urban, urbanization rate
- **Age Structure** — Working age population, dependency ratio
- **Life Expectancy**
- **Fertility Rate**
- **Migration** — Net migration

### 2J. Other / Country-Specific

- **Energy** — Oil production, consumption, reserves (for commodity exporters)
- **Agriculture** — Crop production (for agricultural economies)
- **Tourism** — Arrivals, receipts
- **Remittances** — Workers' remittances

---

## 3. Sovereign Risk & Credit

### 3A. SRSK — Bloomberg Sovereign Risk Model

Bloomberg's proprietary model provides:

- **1-Year Default Probability** — Quantitative estimate
- **5-Year CDS Spread Estimate** — Model-implied fair value
- **Factor Decomposition:**
  - Government debt/GDP
  - External debt/GDP
  - Current account/GDP
  - GDP growth
  - Inflation
  - Corruption/governance
  - Foreign reserves adequacy
  - Fiscal balance
  - Terms of trade volatility

**BLPAPI Access:** `SRSK` data can be pulled via BDP/BDH using the sovereign security ticker.

### 3B. Sovereign CDS Tickers (SOVR)

CDS spreads are available for most ASADO countries. The Bloomberg ticker convention for sovereign CDS:


| Maturity | Ticker Pattern                      | Example (Brazil)                 |
| -------- | ----------------------------------- | -------------------------------- |
| 1Y       | `[COUNTRY] CDS USD SR 1Y D14 Corp`  | `BRAZIL CDS USD SR 1Y D14 Corp`  |
| 5Y       | `[COUNTRY] CDS USD SR 5Y D14 Corp`  | `BRAZIL CDS USD SR 5Y D14 Corp`  |
| 10Y      | `[COUNTRY] CDS USD SR 10Y D14 Corp` | `BRAZIL CDS USD SR 10Y D14 Corp` |


Alternative ticker format: `CBRZ1U5 Curncy` (Brazil 5Y CDS)

### 3C. Sovereign Credit Ratings (CSDR)

Available ratings agencies on Bloomberg:

- S&P Global Ratings (long-term, short-term, outlook)
- Moody's Investors Service (long-term, short-term, outlook)
- Fitch Ratings (long-term, short-term, outlook)
- DBRS Morningstar
- Rating & Investment (R&I)
- Japan Credit Rating Agency (JCR)

**Fields for BDP/BDH:**

- `RTG_SP_LT_LC_ISSUER_CREDIT` — S&P long-term local currency rating
- `RTG_SP_LT_FC_ISSUER_CREDIT` — S&P long-term foreign currency rating
- `RTG_MOODY_LT_LC_DEBT_RATING` — Moody's long-term local currency
- `RTG_MOODY_LT_FC_DEBT_RATING` — Moody's long-term foreign currency
- `RTG_FITCH_LT_LC_ISSUER_DEFAULT` — Fitch long-term local currency
- `RTG_FITCH_LT_FC_ISSUER_DEFAULT` — Fitch long-term foreign currency
- `RTG_SP_OUTLOOK` — S&P outlook
- `RTG_MOODY_OUTLOOK` — Moody's outlook

---

## 4. Government Bonds & Yield Curves

### 4A. Benchmark Government Bond Tickers

Bloomberg uses "Generic" government bond tickers for benchmark yields:


| Country   | 2Y              | 5Y              | 10Y              | 30Y              |
| --------- | --------------- | --------------- | ---------------- | ---------------- |
| Australia | `GACGB2 Index`  | `GACGB5 Index`  | `GACGB10 Index`  | `GACGB30 Index`  |
| Brazil    | `GEBR2Y Index`  | `GEBR5Y Index`  | `GEBR10Y Index`  | —                |
| Canada    | `GCAN2YR Index` | `GCAN5YR Index` | `GCAN10YR Index` | `GCAN30YR Index` |
| China     | `GCNY2YR Index` | `GCNY5YR Index` | `GCNY10YR Index` | `GCNY30YR Index` |
| France    | `GFRN2 Index`   | `GFRN5 Index`   | `GFRN10 Index`   | `GFRN30 Index`   |
| Germany   | `GDBR2 Index`   | `GDBR5 Index`   | `GDBR10 Index`   | `GDBR30 Index`   |
| India     | `GIND2YR Index` | `GIND5YR Index` | `GIND10YR Index` | —                |
| Italy     | `GBTPGR2 Index` | `GBTPGR5 Index` | `GBTPGR10 Index` | `GBTPGR30 Index` |
| Japan     | `GJGB2 Index`   | `GJGB5 Index`   | `GJGB10 Index`   | `GJGB30 Index`   |
| Korea     | `GVSK2YR Index` | `GVSK5YR Index` | `GVSK10YR Index` | —                |
| Mexico    | `GMXN2YR Index` | `GMXN5YR Index` | `GMXN10YR Index` | `GMXN30YR Index` |
| U.K.      | `GUKG2 Index`   | `GUKG5 Index`   | `GUKG10 Index`   | `GUKG30 Index`   |
| U.S.      | `USGG2YR Index` | `USGG5YR Index` | `USGG10YR Index` | `USGG30YR Index` |


**Pattern:** `G[CountryCode][Maturity] Index` — Search `TK` on the terminal for the exact tickers for each country.

### 4B. Yield Curve Data

- Use **CRVF** to find yield curves by country
- Key curve types: Sovereign, Swap, Inflation-linked
- Historical curve data via **GC** with date overlays

### 4C. Key Bond Fields (BDP/BDH)

- `PX_LAST` — Last price / yield
- `YLD_YTM_MID` — Yield to maturity (mid)
- `DUR_ADJ_MID` — Modified duration
- `SPREAD_TO_BENCHMARK` — Spread vs benchmark

---

## 5. Foreign Exchange & Reserves

### 5A. Currency Tickers

Bloomberg currency tickers follow: `[CCY1][CCY2] Curncy`


| Country   | Ticker                                          | Example       |
| --------- | ----------------------------------------------- | ------------- |
| Australia | `AUDUSD Curncy`                                 | AUD per 1 USD |
| Brazil    | `USDBRL Curncy`                                 | BRL per 1 USD |
| India     | `USDINR Curncy`                                 | INR per 1 USD |
| Japan     | `USDJPY Curncy`                                 | JPY per 1 USD |
| U.K.      | `GBPUSD Curncy`                                 | GBP per 1 USD |
| etc.      | Pattern: `USD[CCY] Curncy` or `[CCY]USD Curncy` |               |


### 5B. FX-Related Economic Indicators

- **REER** (Real Effective Exchange Rate) — Available via ECST
- **NEER** (Nominal Effective Exchange Rate)
- **FX Reserves** — Total reserves, months of import cover
- **Capital Flow Data** — Via ECST > External Sector

### 5C. FX Forecast & Analytics

- **FXFC** — Consensus FX forecasts
- **WCRS** — Currency ranking by total return, carry, PPP valuation
- **FXFM** — Bloomberg's FX forecast model

---

## 6. Trade & Balance of Payments

### 6A. Trade Data (ECTR)

- Bilateral trade flows for all country pairs
- Import/export values by commodity (HS code level)
- Data back to 1980 for most countries
- Interactive map visualization

### 6B. BoP Components (via ECST > External Sector)

- Current Account: goods, services, primary income, secondary income
- Capital Account
- Financial Account: FDI, portfolio, other investment, reserves
- Net IIP (International Investment Position)

### 6C. Relevant Tickers

Economic indicator tickers for trade data follow the pattern: `[MNEMONIC] Index`

Examples:

- US Trade Balance: `USTBTOT Index`
- US Current Account: `USCABAL Index`

---

## 7. ESG & Governance

### 7A. Bloomberg ESG Scores (Corporate-focused, some sovereign)

Bloomberg has comprehensive ESG scoring primarily for **corporate** issuers (15,500+ companies). For **sovereign** ESG:

- Bloomberg does **not** have a dedicated sovereign ESG score
- However, Bloomberg **aggregates** third-party sovereign ESG data:
  - World Bank Governance Indicators (via ECST)
  - UN Human Development Index
  - Transparency International CPI (corruption)
  - World Bank ESG Data Portal indicators

### 7B. Governance Indicators Available via Bloomberg

Through ECST and related functions, these governance/institutional quality measures are accessible:

- **Corruption Perception Index** (Transparency International)
- **World Bank Governance Indicators:**
  - Voice & Accountability
  - Political Stability & Absence of Violence
  - Government Effectiveness
  - Regulatory Quality
  - Rule of Law
  - Control of Corruption
- **Press Freedom Index**
- **Ease of Doing Business** rankings

### 7C. Bloomberg MSCI ESG Indices

For fixed income sovereign analysis:

- **Bloomberg MSCI Global Treasury ESG Weighted Index** — Weights sovereign bonds by MSCI ESG government ratings
- **Bloomberg Government Climate Bond Indices** — Climate-aligned sovereign bond indices

---

## 8. Ticker Naming Conventions

### 8A. Economic Indicator Tickers

Bloomberg economic indicator tickers generally follow this pattern:

```
[PREFIX][COUNTRY_CODE][SUFFIX] Index
```

Where:

- **PREFIX** = Indicator type (e.g., `EHGD` for GDP, `ECPI` for CPI)
- **COUNTRY_CODE** = Bloomberg's 2-letter country abbreviation
- **SUFFIX** = Transformation (e.g., `Y` for YoY, `Q` for QoQ)

**Examples:**


| Indicator             | US Ticker        | Japan Ticker     | UK Ticker        |
| --------------------- | ---------------- | ---------------- | ---------------- |
| Real GDP YoY          | `EHGDUSY Index`  | `EHGDJNY Index`  | `EHGDGBY Index`  |
| CPI YoY               | `CPI YOY Index`  | `JNCPIYOY Index` | `UKRPCJYR Index` |
| Unemployment Rate     | `USURTOT Index`  | `JNUE Index`     | `UKUEILOR Index` |
| Industrial Production | `IP CHNG Index`  | `JNIPYOY Index`  | `UKIPIYOY Index` |
| Retail Sales          | `RSTAMOM Index`  | `JNRSYOY Index`  | `GBRLYOY Index`  |
| PMI Manufacturing     | `MPMIUSMA Index` | `MPMIJAMA Index` | `MPMIGBMA Index` |


**Note:** Ticker patterns are NOT perfectly uniform across countries. The safest way to find the exact ticker is:

1. Use **ECST** and navigate to the indicator
2. Note the ticker shown in the detail view
3. Or use **FLDS** to search for fields by keyword

### 8B. Bloomberg Country Codes (commonly used in tickers)


| Country   | BBG Code | Country      | BBG Code |
| --------- | -------- | ------------ | -------- |
| Australia | AU       | Korea        | KO       |
| Brazil    | BZ       | Malaysia     | MA       |
| Canada    | CA       | Mexico       | MX       |
| Chile     | CL       | Netherlands  | NE       |
| China     | CH       | Philippines  | PH       |
| Denmark   | DK       | Poland       | PO       |
| France    | FR       | Saudi Arabia | SA       |
| Germany   | GE       | Singapore    | SI       |
| Hong Kong | HK       | South Africa | SA       |
| India     | IN       | Spain        | SP       |
| Indonesia | ID       | Sweden       | SD       |
| Italy     | IT       | Switzerland  | SW       |
| Japan     | JN       | Taiwan       | TA       |
|           |          | Thailand     | TH       |
|           |          | Turkey       | TU       |
|           |          | U.K.         | GB       |
|           |          | U.S.         | US       |
|           |          | Vietnam      | VN       |


### 8C. Yellow Keys (Market Sector Keys)

- `Index` (F10) — For economic indices and indicators
- `Govt` (F2) — For government bonds
- `Curncy` (F11) — For currencies
- `Corp` (F3) — For corporate bonds / CDS
- `Equity` (F8) — For equities

---

## 9. BLPAPI/Python Programmatic Access

### 9A. Libraries


| Library  | Description                             | Install              |
| -------- | --------------------------------------- | -------------------- |
| `blpapi` | Official Bloomberg Python SDK           | `pip install blpapi` |
| `xbbg`   | Intuitive wrapper (Rust backend, async) | `pip install xbbg`   |
| `pdblp`  | Pandas-friendly wrapper                 | `pip install pdblp`  |
| `blp`    | Simple wrapper                          | `pip install blp`    |


**Prerequisite:** Requires a Bloomberg Terminal running on the same machine or a B-PIPE connection.

### 9B. Key API Functions

```python
# Using xbbg (recommended)
from xbbg import blp

# BDP — Bloomberg Data Point (current snapshot)
df = blp.bdp(tickers='USGG10YR Index', flds=['PX_LAST'])

# BDH — Bloomberg Data History (time series)
df = blp.bdh(
    tickers='USGG10YR Index',
    flds=['PX_LAST'],
    start_date='2020-01-01',
    end_date='2024-12-31'
)

# BDS — Bloomberg Data Set (bulk data)
df = blp.bds(tickers='US Govt', flds=['GOVT_BENCHMARK_BONDS'])

# Multiple tickers at once
tickers = ['USGG10YR Index', 'GDBR10 Index', 'GJGB10 Index']
df = blp.bdh(tickers=tickers, flds=['PX_LAST'], start_date='2020-01-01')
```

### 9C. Example: Pull Country Macro Data

```python
from xbbg import blp
import pandas as pd

# GDP Growth — multiple countries
gdp_tickers = {
    'US': 'EHGDUSY Index',
    'JP': 'EHGDJNY Index',
    'GB': 'EHGDGBY Index',
    'DE': 'EHGDGEY Index',
    'CN': 'EHGDCHY Index',
    'BR': 'EHGDBZY Index',
    'IN': 'EHGDINY Index',
}

gdp = blp.bdh(
    tickers=list(gdp_tickers.values()),
    flds=['PX_LAST'],
    start_date='2000-01-01'
)

# Sovereign CDS spreads
cds_tickers = [
    'BRAZIL CDS USD SR 5Y D14 Corp',
    'TURKEY CDS USD SR 5Y D14 Corp',
    'MEXICO CDS USD SR 5Y D14 Corp',
    'SAFRIC CDS USD SR 5Y D14 Corp',
]
cds = blp.bdh(tickers=cds_tickers, flds=['PX_LAST'], start_date='2020-01-01')

# Government bond yields — all ASADO countries
bond_tickers = [
    'USGG10YR Index',   # US
    'GDBR10 Index',     # Germany
    'GJGB10 Index',     # Japan
    'GUKG10 Index',     # UK
    'GFRN10 Index',     # France
    'GACGB10 Index',    # Australia
    'GCAN10YR Index',   # Canada
]
yields = blp.bdh(tickers=bond_tickers, flds=['PX_LAST'], start_date='2000-01-01')
```

### 9D. Finding Tickers Programmatically

On the Bloomberg Terminal, use these approaches:

1. **ECST** → Navigate to the indicator → Note the ticker displayed
2. **FLDS** → Search by keyword → Get field mnemonics
3. **SECF** → Security Finder → Search by asset class + country
4. **TK** → Ticker lookup for specific security types
5. In Excel: Bloomberg tab → Find Fields icon

---

## 10. Recommended Data to Add to ASADO

Based on this catalog, the following Bloomberg data would significantly enhance the ASADO database beyond what's already collected from free sources:

### 10A. HIGH-PRIORITY — Unique to Bloomberg / Hard to get elsewhere


| Category                      | Specific Data                        | Bloomberg Source      | Frequency    | Why Valuable                                         |
| ----------------------------- | ------------------------------------ | --------------------- | ------------ | ---------------------------------------------------- |
| **Sovereign CDS**             | 5Y CDS spreads for all 34 countries  | SOVR / tickers        | Daily        | Real-time market-implied default risk                |
| **SRSK Model**                | 1Y default probability, model scores | SRSK                  | Monthly      | Bloomberg's proprietary sovereign risk decomposition |
| **Government Bond Yields**    | 2Y, 5Y, 10Y benchmark yields         | Generic govt tickers  | Daily        | Yield curve shape, term premium                      |
| **Yield Curve Slope**         | 10Y-2Y spread by country             | Calculated from above | Daily        | Recession/growth signal                              |
| **Inflation Breakevens**      | Market-implied inflation             | ILBE                  | Daily        | Forward-looking inflation expectations               |
| **Interest Rate Probability** | Central bank rate move odds          | WIRP                  | Daily        | Market expectations for policy                       |
| **FX Forecasts**              | Consensus FX forecasts               | FXFC                  | Monthly      | Forward-looking currency expectations                |
| **Bond Yield Forecasts**      | Consensus rate forecasts             | BYFC                  | Monthly      | Rate direction expectations                          |
| **Credit Rating History**     | Full rating history all agencies     | CSDR / BDP fields     | Event-driven | Rating trajectory analysis                           |


### 10B. MEDIUM-PRIORITY — Available elsewhere but better quality on Bloomberg


| Category                     | Specific Data                   | Bloomberg Source | Frequency         | Why Valuable                      |
| ---------------------------- | ------------------------------- | ---------------- | ----------------- | --------------------------------- |
| **Private Sector Credit**    | Bank lending, credit growth     | ECST > Monetary  | Monthly           | Financial system leverage         |
| **Money Supply**             | M2 growth by country            | ECST > Monetary  | Monthly           | Monetary conditions               |
| **PMI Data**                 | Manufacturing + Services PMI    | ECST > Activity  | Monthly           | Leading indicator, high frequency |
| **Consumer Confidence**      | Survey-based indices            | ECST > Surveys   | Monthly           | Leading indicator for consumption |
| **Business Confidence**      | Survey-based indices            | ECST > Surveys   | Monthly           | Leading indicator for investment  |
| **House Prices**             | National house price indices    | ECST > Prices    | Monthly/Quarterly | Asset bubble / wealth effects     |
| **Government Debt Maturity** | Average maturity, rollover risk | DDIS / WCDM      | Monthly           | Refinancing risk                  |
| **FDI Flows**                | Net FDI by country              | ECST > External  | Quarterly         | Capital flow vulnerability        |


### 10C. LOWER-PRIORITY — Nice to have


| Category                            | Specific Data    | Bloomberg Source | Frequency |
| ----------------------------------- | ---------------- | ---------------- | --------- |
| Real Effective Exchange Rate (REER) | ECST > External  | Monthly          |           |
| Terms of Trade                      | ECST > External  | Monthly          |           |
| Capacity Utilization                | ECST > Activity  | Monthly          |           |
| Vehicle Sales                       | ECST > Activity  | Monthly          |           |
| Banking NPL Ratios                  | ECST > Financial | Quarterly        |           |
| Capital Adequacy Ratios             | ECST > Financial | Quarterly        |           |
| International Investment Position   | ECST > External  | Quarterly        |           |


### 10D. Implementation Notes

1. **Data limits:** Bloomberg Terminal has daily download limits. Plan batch pulls carefully.
2. **Compliance:** Bloomberg data license generally restricts redistribution. Store locally, don't publish raw Bloomberg data.
3. **Caching strategy:** Pull daily/weekly data in small batches; monthly/quarterly data in monthly sweeps.
4. **Ticker discovery:** The most reliable approach is to use ECST on the terminal, navigate to each country × indicator, and record the exact ticker. This one-time exercise produces the definitive ticker mapping.
5. **xbbg caching:** The xbbg library has built-in caching that avoids redundant API calls.
6. **ASADO integration:** Bloomberg data should flow into the DuckDB database alongside existing free-source data. Use a new table `bloomberg_factors` or merge into existing `external_factors` / `extended_factors`.

---

## Appendix A: Bloomberg Terminal Functions Quick Reference

```
ECONOMICS:          ECST, ECFC, ECO, ECMX, ECWB, ECAN, ECOD, ECOS, ECOF, ECTR
COUNTRY OVERVIEW:   COUN, CBQ, BTMM, SOVM
SOVEREIGN RISK:     SRSK, SOVR, CSDR, RATC, CRP, DRSK, CDSW, WCDS
GOVT DEBT:          WCDM, DEBT, DDIS, BUDG
BONDS:              WB, WBF, GC, GC3D, GCT, CRVF, FIT, SRCH, ILBE, BRMM, WIRP, BYFC
FX:                 FXC, WCRS, FXFC, FXFM, FXIP, WIRA, BFIX
INFLATION:          IFMO, ILBE
MACRO MONITORS:     GMM, GEW, EMKT, EMMV, EMEQ
NEWS/INTELLIGENCE:  TOP, BI, BRIE, FIRS
DATA TOOLS:         FLDS, XLTP, DAPI, DATA, SECF
```

## Appendix B: Key Bloomberg Fields for BDP/BDH

```
PRICE/YIELD:        PX_LAST, PX_OPEN, PX_HIGH, PX_LOW, PX_VOLUME
                    YLD_YTM_MID, YLD_YTM_BID, YLD_YTM_ASK
BONDS:              DUR_ADJ_MID, SPREAD_TO_BENCHMARK, OAS_SPREAD_MID
RATINGS:            RTG_SP_LT_LC_ISSUER_CREDIT, RTG_SP_LT_FC_ISSUER_CREDIT
                    RTG_MOODY_LT_LC_DEBT_RATING, RTG_MOODY_LT_FC_DEBT_RATING
                    RTG_FITCH_LT_LC_ISSUER_DEFAULT, RTG_FITCH_LT_FC_ISSUER_DEFAULT
                    RTG_SP_OUTLOOK, RTG_MOODY_OUTLOOK, RTG_FITCH_OUTLOOK
ECONOMIC:           ACTUAL_RELEASE, BN_SURVEY_MEDIAN, BN_SURVEY_HIGH, BN_SURVEY_LOW
                    ECO_FUTURE_RELEASE_DT, LAST_UPDATE_DT
DESCRIPTION:        SECURITY_NAME, COUNTRY_ISO, CNTRY_OF_RISK
```

---

*This catalog was compiled from Bloomberg official documentation, university library guides (Michigan, Cornell, Columbia, Duke, Delaware, Pace, NYU, Ljubljana), CFI resources, Bloomberg cheat sheets, BLPAPI documentation, and multiple web sources. Ticker examples should be verified on the terminal as Bloomberg occasionally changes conventions.*