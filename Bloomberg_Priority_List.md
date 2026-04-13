# Bloomberg Data Priority List — Gap Analysis vs. ASADO Current Holdings

**Purpose:** Cross-references the Bloomberg Country Data Catalog against everything ASADO already collects, and ranks Bloomberg additions by incremental value.

**Date:** April 2026

---

## Current ASADO Data Inventory (What We Already Have)

### From Bloomberg (T2 Master — 53 factors)
- **Returns:** 1M, 3M, 6M, 9M, 12M forward returns
- **Momentum:** 1M, 3M, 12M, 12-1M trailing returns
- **Commodities:** Gold, Copper, Oil, Agriculture (levels + 12M returns)
- **Macro:** Currency (level, 12M return, vol), 10Y Bond (yield + 12M return), Budget Deficit, Debt/GDP, REER, GDP growth, Current Account, CPI Inflation, Bloomberg Country Risk
- **Valuation:** Best PE, Trailing PE, Positive PE, Shiller PE, Best PBK, Best Price/Sales, EV/EBITDA, Earnings Yield
- **Quality:** Best Cash Flow, Best Div Yield, BEST EPS, Trailing EPS, Trailing EPS 36, LT Growth, Best ROE, Operating Margin, Debt/EV
- **Technical:** 120MA Signal, 120MA, RSI14, Advance/Decline, 360D Vol, 20D Vol, P2P, PX_LAST
- **Market Cap:** MCAP, MCAP Adj, Mcap Weights, Tot Return Index

### From Free Sources (collect_external.py — 35 variables)
- **Risk:** EPU, GPR (country + 3 global variants)
- **Credit:** BIS Credit-to-GDP Gap
- **Property:** BIS Property Price
- **Leading:** OECD CLI
- **FX:** BIS REER
- **World Bank (27):** GDP growth, inflation, unemployment, current account/GDP, FDI/GDP, govt debt/GDP, domestic credit/GDP, market cap/GDP, FX reserves, import cover months, external debt/GNI, trade openness, population (total + growth), old-age dependency, labor force, female LFP, female labor share, CO2/capita, renewable energy share, 6 governance indicators (corruption, govt effectiveness, political stability, regulatory quality, rule of law, voice & accountability)

### From Free Sources (collect_extended.py — 51 variables)
- **Monetary:** BIS Policy Rate
- **Credit:** BIS Debt Service Ratio (private)
- **Sentiment:** OECD BCI, OECD CCI
- **FX:** ECB cross-rates (25 pairs)
- **Climate/ESG:** ND-GAIN (score, vulnerability, readiness), EIA petroleum consumption
- **Labor:** ILO unemployment, ILO labor force participation
- **Development:** UNDP HDI, IHDI, GDI, GII
- **Governance:** OFAC sanctions count
- **Agriculture/Trade:** FAO (import dependency, self-sufficiency, trade openness, terms of trade, ag export share)
- **US/Global macro:** FRED VIX, UST 10Y, UST 2Y, yield curve 10Y-2Y, USD broad index, HY OAS

### From IMF (collect_imf.py — ~26 variables)
- **Inflation:** CPI index, CPI YoY
- **Macro forecasts:** WEO GDP growth, inflation, CA/GDP, debt/GDP, unemployment, population
- **BoP:** Current account, goods & services (credit/debit), FDI net, portfolio investment net, financial account
- **Rates:** Money market rate, discount rate, govt bond yield, T-bill rate
- **FX:** Exchange rate LCU/USD
- **Labor:** Unemployment rate, employment index
- **Trade:** Exports, imports, trade balance, trade openness, export/import price indices, YoY changes

### From GDELT (93 variables)
- News sentiment, attention, risk, dispersion, regime signals (monthly)

### From Bilateral Data (collect_bilateral.py)
- IMF bilateral trade matrices
- BIS cross-border banking claims

**TOTAL: ~328 distinct variables in unified_panel (as of April 2026)**

---

## Gap Analysis: What Bloomberg Has That ASADO Does NOT

Below is every category of Bloomberg country data, mapped against existing holdings, with a gap assessment.

### ALREADY WELL COVERED (Low/No Bloomberg Value-Add)

| Bloomberg Data | Already Have From | Assessment |
|---|---|---|
| GDP growth | T2 (GDP), WB, IMF WEO | **Covered 3x** |
| CPI inflation | T2 (Inflation), WB, IMF CPI | **Covered 3x** |
| Unemployment rate | WB, ILO, IMF | **Covered 3x** |
| Current account/GDP | T2 (Current Account), WB, IMF WEO+BOP | **Covered 3x** |
| Govt debt/GDP | T2 (Debt to GDP), WB, IMF WEO | **Covered 3x** |
| Budget deficit | T2 (Budget Def) | **Covered** |
| REER | T2 (REER), BIS REER | **Covered 2x** |
| FX rates | ECB cross-rates, IMF exchange rate | **Covered 2x** |
| 10Y bond yield | T2 (10Yr Bond), IMF govt bond yield | **Covered 2x** |
| Governance indicators | WB 6 indicators, OFAC sanctions | **Covered well** |
| FDI flows | WB FDI/GDP, IMF BOP FDI net | **Covered 2x** |
| Trade data | IMF trade (exports, imports, balance), FAO, bilateral matrices | **Covered extensively** |
| Population/demographics | WB (pop, growth, old-age dep, labor force), IMF WEO pop | **Covered 2x** |
| Commodity prices | T2 (Gold, Oil, Copper, Agriculture) | **Covered** |
| VIX / volatility | FRED VIX, T2 (20D Vol, 360D Vol, Currency Vol) | **Covered** |
| Country risk score | T2 (Bloom Country Risk) | **Already from Bloomberg** |
| Policy rate | BIS Policy Rate, IMF discount rate | **Covered 2x** |
| Credit/GDP | WB domestic credit/GDP, BIS credit-to-GDP gap | **Covered 2x** |
| Property prices | BIS Property Price | **Covered** |
| Leading indicators | OECD CLI | **Covered** |
| EPU / geopolitical risk | EPU, GPR (4 variants) | **Covered** |
| Business/consumer confidence | OECD BCI, OECD CCI | **Covered** |

---

## PRIORITIZED BLOOMBERG ADDITIONS

### TIER 1 — HIGH VALUE: Unique to Bloomberg, No Free Substitute

These are data series that Bloomberg provides uniquely and that would add genuinely new signal dimensions to ASADO.

| # | Data | Bloomberg Source | Frequency | Why It's Unique | Status |
|---|---|---|---|---|---|
| **1** | **Sovereign 5Y CDS Spreads** | SOVR / CDS tickers | Daily→Monthly | Real-time, market-implied sovereign default risk. | **DONE** — `BBG_CDS_5Y` (15 countries) |
| **2** | **SRSK Model Scores** (1Y default prob + factor decomposition) | SRSK | Monthly | Bloomberg's proprietary sovereign risk model. | **NOT AVAILABLE** via BLPAPI — terminal only |
| **3** | **Inflation Breakevens** (market-implied inflation) | ILBE / bond tickers | Daily→Monthly | Forward-looking inflation expectations from bond markets. | **DONE** — `BBG_Breakeven_10Y` (6 countries) |
| **4** | **Yield Curve Shape** (2Y, 5Y, 10Y, 30Y yields by country) | Generic govt bond tickers | Daily→Monthly | Full curve shape adds term structure signal. | **DONE** — `BBG_Govt_Bond_{2Y,5Y,10Y,30Y}` (26 countries) + `BBG_Yield_Curve_10Y2Y` derived |
| **5** | **Central Bank Rate Change Probability** | WIRP | Daily→Monthly | Market-implied odds of rate hikes/cuts. | **DONE** — `BBG_WIRP_ImpliedRate` (25 countries) |
| **6** | **Consensus Economic Forecasts** (GDP, CPI) | ECFC | Monthly | Forward-looking analyst consensus. | **DONE** — `BBG_ECFC_GDP`, `BBG_ECFC_CPI` (20 countries) |
| **7** | **Sovereign Credit Rating History** (S&P, Moody's, Fitch) | CSDR / BDP fields | Event-driven | Rating level + trajectory. | **PARTIAL** — collector built, some tickers need terminal-side verification |

### TIER 2 — MEDIUM VALUE: Better Quality or Frequency Than Free Alternatives

These overlap with existing data but Bloomberg versions are materially higher quality, higher frequency, or more complete.

| # | Data | Bloomberg Source | Frequency | What We Already Have | Why Bloomberg Is Better |
|---|---|---|---|---|---|
| **8** | **PMI Data** (Manufacturing + Services + Composite) | ECST / tickers | Monthly | OECD BCI/CCI (sentiment, not PMI) | PMI is the global standard leading indicator. BCI/CCI are different surveys with less market impact. PMI drives markets. |
| **9** | **Money Supply Growth** (M2 YoY) | ECST > Monetary | Monthly | Nothing — only have BIS policy rate | Monetary aggregate growth is a key liquidity signal for equity markets. |
| **10** | **Private Sector Credit Growth** (YoY) | ECST > Monetary | Monthly | BIS credit-to-GDP GAP (level, not growth rate) | Credit growth rate is different from the credit gap. Growth measures flow; gap measures deviation from trend. |
| **11** | **Govt Debt Maturity Profile / Avg Maturity** | DDIS / WCDM | Monthly | Debt/GDP level only | Rollover risk: a country with 3Y avg maturity is far more vulnerable than one with 15Y avg maturity at the same debt level. |
| **12** | **FX Consensus Forecasts** | FXFC | Monthly | Spot rates only (ECB, IMF) | Forward-looking consensus. The gap between forecast and spot = expected return / risk. |
| **13** | **Bond Yield Forecasts** | BYFC | Monthly | Current yields only (T2, IMF) | Consensus rate direction. Rising/falling rate expectations affect equity returns via duration. |

### TIER 3 — LOWER VALUE: Incremental / Nice-to-Have

These would add some signal but overlap substantially with existing data or are less impactful for sovereign risk analysis.

| # | Data | Bloomberg Source | Frequency | Assessment |
|---|---|---|---|---|
| **14** | House Price Indices (Bloomberg version) | ECST > Prices | Monthly | Already have BIS Property Price (quarterly). Bloomberg may offer monthly, but marginal improvement. |
| **15** | Industrial Production (by country) | ECST > Activity | Monthly | Partially captured by OECD CLI and PMI would be better. |
| **16** | Retail Sales (by country) | ECST > Activity | Monthly | Consumption signal partly in GDP; lower priority. |
| **17** | Banking NPL Ratios | ECST > Financial | Quarterly | Useful for financial stability, but lagging indicator. |
| **18** | Banking Capital Adequacy | ECST > Financial | Quarterly | Same — useful but lagging. |
| **19** | Vehicle Sales | ECST > Activity | Monthly | Niche; overlaps with consumer sentiment. |
| **20** | Capacity Utilization | ECST > Activity | Monthly | Useful but covered indirectly by IP and PMI. |
| **21** | Terms of Trade (Bloomberg) | ECST > External | Monthly | Have IMF export/import price indices; can compute. Already have FAO terms of trade. |
| **22** | International Investment Position | ECST > External | Quarterly | Low-frequency structural data; external debt/GNI captures most of this. |

---

## Implementation Recommendation

### Phase 1 — Pull First (Highest ROI, ~7 tickers per country)

```
Ticker families to implement:
1. Sovereign 5Y CDS spreads      → 1 ticker × 34 countries = 34 tickers
2. Govt bond yields 2Y, 5Y, 10Y  → 3 tickers × 34 countries = 102 tickers  
3. Inflation breakevens           → 1 ticker × ~20 countries = ~20 tickers
   (subset; only countries with inflation-linked bonds)
```

**Why first:** These are all daily market data. One `bdh()` call per ticker. High signal value. Can be pulled in a single batch run.

### Phase 2 — Pull Second (Requires ECST navigation, ~7 series per country)

```
Series to implement:
4. Sovereign credit ratings (S&P, Moody's, Fitch)  → 6 fields × 34 = 204 lookups
5. PMI Manufacturing + Services                     → 2 series × ~30 countries
6. M2 money supply growth                           → 1 series × 34 countries
7. Private credit growth                            → 1 series × 34 countries
```

**Why second:** These require discovering the exact ticker for each country via ECST. One-time ticker discovery, then automated pulls.

### Phase 3 — Pull Third (Bloomberg-Proprietary Models)

```
8. SRSK sovereign risk model scores    → SRSK function, country by country
9. WIRP rate change probabilities      → WIRP, requires per-central-bank setup
10. ECFC consensus forecasts           → ECFC, multiple indicators × countries
11. FXFC / BYFC forward-looking        → Forecast endpoints
```

**Why third:** These are model/consensus outputs that may require more complex API calls (BDS rather than BDH). Some may need manual ticker discovery.

### Phase 4 — Pull Last (Nice-to-haves)

```
12. Govt debt avg maturity / rollover  → DDIS/WCDM
13. Bond/FX forecast consensus         → BYFC/FXFC
```

---

## Summary Score Card

| # | Data | Unique? | Signal Value | Ease of Pull | Priority | Status |
|---|---|---|---|---|---|---|
| 1 | Sovereign CDS 5Y | Yes | Very High | Easy (bdh) | **P1** | **DONE** |
| 2 | Yield Curve (2Y, 5Y, 10Y, 30Y) | Partial gap | Very High | Easy (bdh) | **P1** | **DONE** |
| 3 | Inflation Breakevens | Yes | High | Easy (bdh) | **P1** | **DONE** |
| 4 | Sovereign Credit Ratings | Yes | Very High | Medium (bdp) | **P2** | Partial |
| 5 | PMI (Mfg + Services) | Yes (vs BCI/CCI) | Very High | Medium (tickers) | **P2** | Planned |
| 6 | SRSK Default Probability | Yes | Very High | Medium (SRSK) | **P2** | Not available via BLPAPI |
| 7 | Consensus Forecasts (GDP, CPI) | Yes | High | Hard (ECFC/BDS) | **P3** | **DONE** |
| 8 | M2 Money Supply Growth | Yes | High | Medium (tickers) | **P2** | Planned |
| 9 | Private Credit Growth | Partial gap | Medium-High | Medium (tickers) | **P2** | Planned |
| 10 | WIRP Rate Probabilities | Yes | High | Hard (per-CB) | **P3** | **DONE** |
| 11 | FX/Bond Forecasts | Yes | Medium | Medium (FXFC/BYFC) | **P3** | Planned |
| 12 | Debt Maturity Profile | Yes | Medium | Hard (DDIS) | **P4** | Collector built, tickers need terminal discovery |
| 13 | House Prices (monthly) | Marginal | Low | Easy (bdh) | **P4** | Planned |
| 14-22 | IP, Retail, NPL, etc. | No (overlaps) | Low | Medium | **P4** | Low priority |

---

## Net New Variables Added by Priority Tier

| Tier | New Variables | New Signal Dimensions |
|---|---|---|
| **P1** (3 items) | ~5 per country (CDS 5Y, 2Y yield, 5Y yield, 30Y yield, breakeven) | Market-implied risk, term structure, inflation expectations |
| **P2** (5 items) | ~12 per country (3 ratings × 2 agencies, PMI mfg, PMI svc, SRSK score, M2, credit growth) | Credit trajectory, activity leading indicators, default models, monetary conditions |
| **P3** (3 items) | ~8 per country (GDP forecast, CPI forecast, rate prob, FX forecast, bond forecast) | Forward-looking consensus, surprise potential |
| **P4** (remainder) | ~5 per country | Marginal additions |
| **TOTAL** | **~30 new variables per country** | |

As of April 2026, Bloomberg has brought ASADO from **~315 to ~328 variables** in `unified_panel`, with **13 Bloomberg variables** adding the critical **market-implied forward-looking data** (CDS, breakevens, ECFC forecasts, WIRP rates, OIS/Z-spreads, MIPD default probability) that was previously absent from the database. Additional Tier 2/3 items remain planned for future phases.
