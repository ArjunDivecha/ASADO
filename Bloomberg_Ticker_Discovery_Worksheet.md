# Bloomberg Terminal Ticker Discovery Worksheet

**Purpose:** Record tickers found during a manual Bloomberg Terminal session using `ECST <GO>` for each country. Once recorded here, the tickers can be added to `scripts/collect_bloomberg.py` for automated monthly pulls.

**Date created:** April 2026  
**How to use:** Open each country in ECST on the Bloomberg Terminal, navigate to the category, find the indicator, and record the ticker shown in the Bloomberg screen. The ticker format is typically `[MNEMONIC] Index`.

---

## How to Find Tickers on Bloomberg Terminal

1. Type `ECST <GO>` → Select country → Navigate to category (Monetary, Activity, etc.)
2. Click on the indicator row → The ticker appears in the top-left of the data screen
3. Record the full ticker including  `Index` suffix (e.g., `USPRCRDT Index`)
4. Alternatively: type the indicator keyword in `SECF <GO>` (Security Finder) filtered by country

---

## 1. Private Sector Credit Growth YoY (HIGH PRIORITY)

**What we need:** Domestic credit to private sector, year-over-year % change  
**ECST path:** Country → Monetary → Credit → Private Credit (or Domestic Credit)  
**Output variable:** `BBG_Private_Credit_YoY`  
**No uniform ticker pattern exists — every country uses a different mnemonic.**


| #   | Country      | ISO2 | BBG Code | Ticker Found       | Notes                                           |
| --- | ------------ | ---- | -------- | ------------------ | ----------------------------------------------- |
| 1   | Australia    | AU   | AU       | __________________ | ECST > Monetary > Credit                        |
| 2   | Brazil       | BR   | BZ       | __________________ | ECST > Monetary > Credit                        |
| 3   | Canada       | CA   | CA       | __________________ |                                                 |
| 4   | Chile        | CL   | CL       | __________________ |                                                 |
| 5   | China        | CN   | CH       | __________________ | May have multiple (total, household, corporate) |
| 6   | Denmark      | DK   | DK       | __________________ |                                                 |
| 7   | France       | FR   | FR       | __________________ | Eurozone aggregate may exist too                |
| 8   | Germany      | DE   | GE       | __________________ |                                                 |
| 9   | Hong Kong    | HK   | HK       | __________________ |                                                 |
| 10  | India        | IN   | IN       | __________________ | RBI reports credit data                         |
| 11  | Indonesia    | ID   | ID       | __________________ |                                                 |
| 12  | Italy        | IT   | IT       | __________________ |                                                 |
| 13  | Japan        | JP   | JN       | __________________ | BOJ reports, may use JN code                    |
| 14  | Korea        | KR   | KO       | __________________ |                                                 |
| 15  | Malaysia     | MY   | MY       | __________________ |                                                 |
| 16  | Mexico       | MX   | MX       | __________________ |                                                 |
| 17  | Netherlands  | NL   | NL       | __________________ |                                                 |
| 18  | Philippines  | PH   | PH       | __________________ |                                                 |
| 19  | Poland       | PL   | PL       | __________________ |                                                 |
| 20  | Saudi Arabia | SA   | SA       | __________________ |                                                 |
| 21  | Singapore    | SG   | SG       | __________________ |                                                 |
| 22  | South Africa | ZA   | ZA       | __________________ | SARB reports                                    |
| 23  | Spain        | ES   | ES       | __________________ |                                                 |
| 24  | Sweden       | SE   | SE       | __________________ |                                                 |
| 25  | Switzerland  | CH   | SW       | __________________ | **SW not CH** (CH = China in BBG)               |
| 26  | Taiwan       | TW   | TW       | __________________ |                                                 |
| 27  | Thailand     | TH   | TH       | __________________ |                                                 |
| 28  | Turkey       | TR   | TU       | __________________ | Note: TU not TR in some BBG tickers             |
| 29  | U.K.         | GB   | GB       | __________________ | BOE reports                                     |
| 30  | U.S.         | US   | US       | __________________ | Try `USPRCRDT Index` or ECST > Monetary         |
| 31  | Vietnam      | VN   | VN       | __________________ |                                                 |


---

## 2. Industrial Production YoY (MEDIUM PRIORITY)

**What we need:** Industrial production index, year-over-year % change  
**ECST path:** Country → Activity → Industrial Production  
**Output variable:** `BBG_IP_YoY`  
**Suspected pattern:** `[CC]IPYOY Index` or similar — verify on terminal.


| #   | Country      | ISO2 | BBG Code | Ticker Found       | Notes                                |
| --- | ------------ | ---- | -------- | ------------------ | ------------------------------------ |
| 1   | Australia    | AU   | AU       | __________________ |                                      |
| 2   | Brazil       | BR   | BZ       | __________________ |                                      |
| 3   | Canada       | CA   | CA       | __________________ |                                      |
| 4   | Chile        | CL   | CL       | __________________ |                                      |
| 5   | China        | CN   | CH       | __________________ | Try `CHVAIOY Index` (value-added IP) |
| 6   | Denmark      | DK   | DK       | __________________ |                                      |
| 7   | France       | FR   | FR       | __________________ |                                      |
| 8   | Germany      | DE   | GE       | __________________ |                                      |
| 9   | Hong Kong    | HK   | HK       | __________________ | May not publish IP                   |
| 10  | India        | IN   | IN       | __________________ |                                      |
| 11  | Indonesia    | ID   | ID       | __________________ |                                      |
| 12  | Italy        | IT   | IT       | __________________ |                                      |
| 13  | Japan        | JP   | JN       | __________________ |                                      |
| 14  | Korea        | KR   | KO       | __________________ |                                      |
| 15  | Malaysia     | MY   | MY       | __________________ |                                      |
| 16  | Mexico       | MX   | MX       | __________________ |                                      |
| 17  | Netherlands  | NL   | NL       | __________________ |                                      |
| 18  | Philippines  | PH   | PH       | __________________ |                                      |
| 19  | Poland       | PL   | PL       | __________________ |                                      |
| 20  | Saudi Arabia | SA   | SA       | __________________ | May not publish IP                   |
| 21  | Singapore    | SG   | SG       | __________________ |                                      |
| 22  | South Africa | ZA   | ZA       | __________________ |                                      |
| 23  | Spain        | ES   | ES       | __________________ |                                      |
| 24  | Sweden       | SE   | SE       | __________________ |                                      |
| 25  | Switzerland  | CH   | SW       | __________________ |                                      |
| 26  | Taiwan       | TW   | TW       | __________________ |                                      |
| 27  | Thailand     | TH   | TH       | __________________ |                                      |
| 28  | Turkey       | TR   | TU       | __________________ |                                      |
| 29  | U.K.         | GB   | GB       | __________________ |                                      |
| 30  | U.S.         | US   | US       | __________________ | Try `IP YOY Index`                   |
| 31  | Vietnam      | VN   | VN       | __________________ |                                      |


---

## 3. Fix Failed PMI Tickers (MEDIUM PRIORITY)

**Currently missing PMI Manufacturing for these countries.** The `MPMI[CC]MA Index` pattern failed. Check if the country uses a different PMI ticker or simply doesn't have one.


| #   | Country      | BBG Code | Tried              | Ticker Found       | Notes                                                  |
| --- | ------------ | -------- | ------------------ | ------------------ | ------------------------------------------------------ |
| 1   | Brazil       | BZ       | `MPMIBZMA Index` ❌ | __________________ | May not have S&P PMI                                   |
| 2   | China        | CH       | `MPMICHMA Index` ❌ | __________________ | Try `CPMINDX Index` (NBS official) or `CHPMINDX Index` |
| 3   | Hong Kong    | HK       | `MPMIHKMA Index` ❌ | __________________ | May not exist                                          |
| 4   | Japan        | JA       | `MPMIJAMA Index` ❌ | __________________ | Try `JPMIMFG Index` or `JIBMMAN Index`                 |
| 5   | Korea        | KO       | `MPMIKOMA Index` ❌ | __________________ | Try `KOPMIMFG Index`                                   |
| 6   | Saudi Arabia | SA       | `MPMISAMA Index` ❌ | __________________ | May not exist                                          |
| 7   | Singapore    | SG       | `MPMISGMA Index` ❌ | __________________ | Try `SIPMIMFG Index`                                   |
| 8   | South Africa | ZA       | `MPMIZAMA Index` ❌ | __________________ | Try `SAPMIMFG Index`                                   |
| 9   | Sweden       | SE       | `MPMISEMA Index` ❌ | __________________ | Try `SWPMIMFG Index`                                   |


**PMI Services — currently only 7 countries.** Many countries genuinely don't publish services PMI, but verify these larger economies:


| #   | Country   | BBG Code | Tried               | Ticker Found       | Notes                                                    |
| --- | --------- | -------- | ------------------- | ------------------ | -------------------------------------------------------- |
| 1   | Australia | AU       | `MPMIAUСА Index` ❌  | __________________ | Ticker had Cyrillic char — try `MPMIAUСА Index` re-typed |
| 2   | Japan     | JA       | `MPMIJASA Index` ❌  | __________________ | Try `JPMISVC Index`                                      |
| 3   | Korea     | KO       | —                   | __________________ |                                                          |
| 4   | Spain     | ES       | `MPMIIESSA Index` ❌ | __________________ | Typo — try `MPMIIESA Index` or `MPMIESSA Index`          |


---

## 4. Fix Failed M2 Money Supply Tickers (MEDIUM PRIORITY)

**Currently 13/31 unique countries have M2.** These countries returned no data for any candidate ticker. Look up M2 YoY (or broad money YoY) in ECST > Monetary.


| #   | Country      | BBG Code | Tried                  | Ticker Found       | Notes                              |
| --- | ------------ | -------- | ---------------------- | ------------------ | ---------------------------------- |
| 1   | Australia    | AU       | `AUM2YOY`, `AUMSM2Y` ❌ | __________________ | Try ECST > Monetary > Money Supply |
| 2   | Brazil       | BZ       | `BZM2YOY`, `BZMSM2Y` ❌ | __________________ |                                    |
| 3   | Canada       | CA       | `CAM2YOY`, `CAMSM2Y` ❌ | __________________ |                                    |
| 4   | Chile        | CL       | `CLM2YOY`, `CLMSM2Y` ❌ | __________________ |                                    |
| 5   | France       | FR       | `FRM2YOY`, `FRMSM2Y` ❌ | __________________ | Eurozone M2 may be the only option |
| 6   | Hong Kong    | HK       | `HKM2YOY`, `HKMSM2Y` ❌ | __________________ |                                    |
| 7   | India        | IN       | `INM2YOY`, `INMSM2Y` ❌ | __________________ |                                    |
| 8   | Italy        | IT       | `ITM2YOY`, `ITMSM2Y` ❌ | __________________ | Eurozone M2                        |
| 9   | Malaysia     | MY       | `MYM2YOY`, `MYMSM2Y` ❌ | __________________ |                                    |
| 10  | Netherlands  | NL       | `NLM2YOY`, `NLMSM2Y` ❌ | __________________ | Eurozone M2                        |
| 11  | Philippines  | PH       | `PHM2YOY`, `PHMSM2Y` ❌ | __________________ |                                    |
| 12  | Poland       | PL       | `PLM2YOY`, `PLMSM2Y` ❌ | __________________ |                                    |
| 13  | Saudi Arabia | SA       | `SAM2YOY`, `SAMSM2Y` ❌ | __________________ |                                    |
| 14  | Singapore    | SG       | `SGM2YOY`, `SGMSM2Y` ❌ | __________________ |                                    |
| 15  | South Africa | ZA       | `ZAM2YOY`, `ZAMSM2Y` ❌ | __________________ |                                    |
| 16  | Sweden       | SE       | `SEM2YOY`, `SEMSM2Y` ❌ | __________________ |                                    |
| 17  | Turkey       | TR       | `TRM2YOY`, `TRMSM2Y` ❌ | __________________ |                                    |
| 18  | U.K.         | GB       | `GBM2YOY`, `GBMSM2Y` ❌ | __________________ | Try BOE M4 instead                 |
| 19  | U.S.         | US       | `M2 YOY Index` ❌       | __________________ | Verify — this should exist         |


---

## 5. Fix Failed ECFC GDP Consensus Tickers (LOW PRIORITY)

**Currently 26/34 countries have GDP data (via fallback).** These countries had both consensus and fallback tickers fail. May not be available via BLPAPI.


| #   | Country     | BBG Code | Primary Tried | Fallback Tried | Ticker Found       | Notes                              |
| --- | ----------- | -------- | ------------- | -------------- | ------------------ | ---------------------------------- |
| 1   | Brazil      | BZ       | `ECGDBZ` ❌    | `EHGDBZY` ❌    | __________________ |                                    |
| 2   | Germany     | GE       | `ECGDDE` ❌    | `EHGDGEY` ❌    | __________________ | BBG code for Germany is DE, not GE |
| 3   | Japan       | JN       | `ECGDJN` ❌    | `EHGDJNY` ❌    | __________________ |                                    |
| 4   | Korea       | KO       | `ECGDKO` ❌    | `EHGDKOY` ❌    | __________________ |                                    |
| 5   | Switzerland | SW       | `ECGDSW` ❌    | `EHGDSWY` ❌    | __________________ |                                    |
| 6   | Turkey      | TU       | `ECGDTR` ❌    | `EHGDTUY` ❌    | __________________ |                                    |


---

## 6. Fix Failed Bond/CDS Tickers (LOW PRIORITY)

These countries are missing 10Y government bond yields. They use non-standard ticker patterns.


| #   | Country      | BBG Code | 10Y Tried           | Ticker Found       | Notes                           |
| --- | ------------ | -------- | ------------------- | ------------------ | ------------------------------- |
| 1   | Chile        | CL       | `CHILE10 Index` ❌   | __________________ |                                 |
| 2   | Malaysia     | MY       | `MALAY10Y Index` ❌  | __________________ | Try SECF > Govt Bond > Malaysia |
| 3   | Philippines  | PH       | `PHLGB10Y Index` ❌  | __________________ |                                 |
| 4   | South Africa | ZA       | `SAGB10Y Index` ❌   | __________________ | Try `GSAB10YR Index`            |
| 5   | Taiwan       | TW       | `TAIBON10 Index` ❌  | __________________ |                                 |
| 6   | Thailand     | TH       | `THAI10Y Index` ❌   | __________________ |                                 |
| 7   | Turkey       | TR       | `TURKBON10 Index` ❌ | __________________ |                                 |
| 8   | Vietnam      | VN       | —                   | __________________ | May not have liquid govt bonds  |


---

## 7. FX Consensus Forecasts — FXFC (FUTURE)

**ECST path:** Not in ECST — use `FXFC <GO>` on terminal  
**What we need:** Consensus 12-month forward FX rate for each currency vs USD  
**Output variable:** `BBG_FX_Forecast_12M`  

During the FXFC session, record the ticker for each currency's 12M consensus forecast.


| #   | Currency | Ticker Found       | Notes                     |
| --- | -------- | ------------------ | ------------------------- |
| 1   | AUD/USD  | __________________ |                           |
| 2   | BRL/USD  | __________________ |                           |
| 3   | CAD/USD  | __________________ |                           |
| 4   | CNY/USD  | __________________ |                           |
| 5   | EUR/USD  | __________________ | Covers FR, DE, IT, NL, ES |
| 6   | GBP/USD  | __________________ |                           |
| 7   | INR/USD  | __________________ |                           |
| 8   | JPY/USD  | __________________ |                           |
| 9   | KRW/USD  | __________________ |                           |
| 10  | MXN/USD  | __________________ |                           |
| 11  | TRY/USD  | __________________ |                           |
| 12  | ZAR/USD  | __________________ |                           |


---

## 8. Bond Yield Forecasts — BYFC (FUTURE)

**ECST path:** Not in ECST — use `BYFC <GO>` on terminal  
**What we need:** Consensus 12-month forward 10Y govt bond yield  
**Output variable:** `BBG_Bond_Forecast_10Y_12M`  


| #   | Country   | Ticker Found       | Notes              |
| --- | --------- | ------------------ | ------------------ |
| 1   | U.S.      | __________________ |                    |
| 2   | Germany   | __________________ | Eurozone benchmark |
| 3   | Japan     | __________________ |                    |
| 4   | U.K.      | __________________ |                    |
| 5   | Australia | __________________ |                    |
| 6   | Canada    | __________________ |                    |


---

## Quick Reference: Bloomberg Country Codes

These are the 2-letter codes Bloomberg uses in ECST tickers (different from ISO in some cases):


| T2 Country   | ISO2 | BBG Code | Notes                       |
| ------------ | ---- | -------- | --------------------------- |
| Australia    | AU   | AU       |                             |
| Brazil       | BR   | BZ       | **Not BR**                  |
| Canada       | CA   | CA       |                             |
| Chile        | CL   | CL       |                             |
| China        | CN   | CH       |                             |
| Denmark      | DK   | DK       |                             |
| France       | FR   | FR       |                             |
| Germany      | DE   | GE       | **Not DE** for some tickers |
| Hong Kong    | HK   | HK       |                             |
| India        | IN   | IN       |                             |
| Indonesia    | ID   | ID       |                             |
| Italy        | IT   | IT       |                             |
| Japan        | JP   | JN       | **Not JP**; PMI uses JA     |
| Korea        | KR   | KO       | **Not KR**                  |
| Malaysia     | MY   | MY       |                             |
| Mexico       | MX   | MX       |                             |
| Netherlands  | NL   | NL       |                             |
| Philippines  | PH   | PH       |                             |
| Poland       | PL   | PL       |                             |
| Saudi Arabia | SA   | SA       |                             |
| Singapore    | SG   | SG       |                             |
| South Africa | ZA   | ZA       |                             |
| Spain        | ES   | ES       |                             |
| Sweden       | SE   | SE       |                             |
| Switzerland  | CH   | **SW**   | **Not CH** (CH = China)     |
| Taiwan       | TW   | TW       |                             |
| Thailand     | TH   | TH       |                             |
| Turkey       | TR   | TU       | **Not TR** for some tickers |
| U.K.         | GB   | GB       |                             |
| U.S.         | US   | US       |                             |
| Vietnam      | VN   | VN       |                             |


---

## After the Terminal Session

Once you've filled in the tickers above, hand this file back and I will:

1. Add new ticker dictionaries to `scripts/collect_bloomberg.py`
2. Add new collector functions for each data category
3. Run the collector to pull all new data
4. Rebuild DuckDB + Neo4j with the expanded variable set
5. Update all documentation

  | Country        | Code | Bloomberg Ticker |
  | -------------- | ---- | ---------------- |
  | Armenia        | AM   | AMPIINDU Index   |
  | Argentina      | AR   | ARZZSAYO Index   |
  | Austria        | AT   | ATIPIYY Index    |
  | Australia      | AU   | AUIPTOLY Index   |
  | Azerbaijan     | AZ   | AZIN0ALY Index   |
  | Bulgaria       | BG   | BUIPYOY Index    |
  | Brazil         | BR   | BZIPYOY% Index   |
  | Belarus        | BY   | BYIPLY Index     |
  | Canada         | CA   | EHIUCA Index     |
  | Switzerland    | CH   | SZIPIYOY Index   |
  | Chile          | CL   | CHIPTOTY Index   |
  | China          | CN   | CHVAIOY Index    |
  | Colombia       | CO   | COOOINDY Index   |
  | Cyprus         | CY   | CYNPITQQ Index   |
  | Czech Republic | CZ   | CZIPITWY Index   |
  | Germany        | DE   | GEINYY Index     |
  | Denmark        | DK   | DEMFIPSY Index   |
  | Algeria        | DZ   | AIIPGEIY Index   |
  | Estonia        | EE   | ESISTWAY Index   |
  | Egypt          | EG   | EGPIPIY Index    |
  | Spain          | ES   | SPIOWAYY Index   |
  | Finland        | FI   | FIIPSAIY Index   |
  | France         | FR   | FPIPYOY Index    |
  | United Kingdom | GB   | UKIPIYOY Index   |
  | Greece         | GR   | GKIPISY Index    |
  | Hong Kong      | HK   | HKIPIYOY Index   |
  | Croatia        | HR   | CQIPTYOY Index   |
  | Hungary        | HU   | HUIPIYOY Index   |
  | Indonesia      | ID   | IDMPIYOY Index   |
  | Ireland        | IE   | IEIPIYOY Index   |
  | Israel         | IL   | ISSIMQOY Index   |
  | India          | IN   | INPIINDY Index   |
  | Italy          | IT   | ITPRWAY Index    |
  | Jordan         | JO   | JOIPIY Index     |
  | Japan          | JP   | JNIPSYOY Index   |
  | Kyrgyzstan     | KG   | KYPRIPMY Index   |
  | South Korea    | KR   | KOIPIYOY Index   |
  | Kazakhstan     | KZ   | KAIPYOYT Index   |
  | Sri Lanka      | LK   | SINPIPIY Index   |
  | Lithuania      | LT   | E6BD1LTY Index   |
  | Luxembourg     | LU   | E6BDFLUY Index   |
  | Latvia         | LV   | LAIOWDS Index    |
  | Moldova        | MD   | MDIPINDY Index   |
  | Malta          | MT   | MTINTWY Index    |
  | Mexico         | MX   | MXIPTYOY Index   |
  | Malaysia       | MY   | MAIPINDY Index   |
  | Netherlands    | NL   | NEIP20YY Index   |
  | Norway         | NO   | NOIPGSAY Index   |
  | Peru           | PE   | PEIPTOTO Index   |
  | Philippines    | PH   | VOPIMFGY Index   |
  | Pakistan       | PK   | PAMFGY Index     |
  | Portugal       | PT   | PTIPTOTY Index   |
  | Romania        | RO   | ROIOUYOY Index   |
  | Serbia         | RS   | SEIPYY Index     |
  | Russia         | RU   | RUIPRNYY Index   |
  | Saudi Arabia   | SA   | SRIPTY Index     |
  | Sweden         | SE   | SWIPIYOY Index   |
  | Singapore      | SG   | SIIPYOY% Index   |
  | Slovenia       | SI   | SVIPTYOY Index   |
  | Slovakia       | SK   | SLPRYOYA Index   |
  | Thailand       | TH   | THMPIN2Y Index   |
  | Tunisia        | TN   | TNIPIYOY Index   |
  | Turkey         | TR   | TUIOSAYY Index   |
  | Taiwan         | TW   | TWINDPIY Index   |
  | Ukraine        | UA   | UAIPYY Index     |
  | United States  | US   | IP YOY Index     |
  | Uruguay        | UY   | URMIIYOY Index   |
  | Vietnam        | VN   | VIPITYOY Index   |
  | South Africa   | ZA   | SFPMYOY Index    |


