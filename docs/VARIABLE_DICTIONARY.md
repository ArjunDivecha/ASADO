# ASADO Variable Dictionary

**Generated:** 2026-06-11 15:28 — by `scripts/build_variable_registry.py`. DO NOT EDIT BY HAND: this file is rendered from the variable registry (`variable_registry` ⨝ `variable_registry_facts` in `Data/asado.duckdb`). Edit semantics in `config/variable_registry_seed.yaml` and re-run the build.

**Coverage:** 1440 live variables across 8 surfaces. Registry rows: 1440 (0 verified, 1300 drafted/needs-review, 140 pending semantics).

**Sign convention:** `higher_is_better` / `lower_is_better` from the live flip lists; `unknown` = not yet established (never guessed). t2/gdelt `_CS`/`_TS` variants are flipped during construction; econ-block `_CS`/`_TS` are NOT and inherit the raw sign.

## feature_panel  (731 variables)

| variable | source | freq | sign | role | countries | range | fresh(d) | definition |
|---|---|---|---|---|---|---|---|---|
| BIS_Credit_GDP_Gap | bis_credit | Q | ↓ |  | 40 | 2000-03-01→2025-09-01 | 283 ⚠STALE | Credit-to-GDP gap — deviation of the private credit/GDP ratio from its one-sided |
| BIS_Credit_GDP_Gap_CS | bis_credit | Q | ↓ |  | 40 | 2000-03-01→2025-09-01 | 283 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Credit-to-GDP gap — de |
| BIS_Credit_GDP_Gap_TS | bis_credit | Q | ↓ |  | 40 | 2001-12-01→2025-09-01 | 283 ⚠STALE | Time-series z-score (vs own trailing history) of: Credit-to-GDP gap — deviation  |
| BIS_DSR_Private | bis_debt_service | Q | ↓ |  | 33 | 2000-03-01→2025-09-01 | 283 ⚠STALE | Private non-financial sector debt service ratio — debt payments as percent of in |
| BIS_DSR_Private_CS | bis_debt_service | Q | ↓ |  | 33 | 2000-03-01→2025-09-01 | 283 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Private non-financial  |
| BIS_DSR_Private_TS | bis_debt_service | Q | ↓ |  | 33 | 2001-12-01→2025-09-01 | 283 ⚠STALE | Time-series z-score (vs own trailing history) of: Private non-financial sector d |
| BIS_Policy_Rate | bis_policy_rate | D | ? |  | 30 | 2000-01-01→2026-06-01 | 10 | Central bank policy rate (BIS), in percent. |
| BIS_Policy_Rate_CS | bis_policy_rate | D | ? |  | 30 | 2000-01-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Central bank policy ra |
| BIS_Policy_Rate_TS | bis_policy_rate | D | ? |  | 29 | 2005-03-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Central bank policy rate (BIS) |
| BIS_Property_Price | bis_property | Q | ↓ |  | 40 | 2000-03-01→2025-12-01 | 192 | Residential property price index (BIS, typically 2010=100). |
| BIS_Property_Price_CS | bis_property | Q | ↓ |  | 40 | 2000-03-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Residential property p |
| BIS_Property_Price_TS | bis_property | Q | ↓ |  | 40 | 2001-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Residential property price ind |
| BIS_REER | bis_reer | M | ↓ |  | 42 | 2000-01-01→2026-04-01 | 71 | BIS real effective exchange rate index (2020=100). |
| BIS_REER_CS | bis_reer | M | ↓ |  | 42 | 2000-01-01→2026-04-01 | 71 | Cross-sectional z-score (across the 34-country panel) of: BIS real effective exc |
| BIS_REER_TS | bis_reer | M | ↓ |  | 42 | 2001-12-01→2026-04-01 | 71 | Time-series z-score (vs own trailing history) of: BIS real effective exchange ra |
| BBG_Breakeven_10Y | bloomberg | M | ? |  | 6 | 2000-01-01→2026-05-01 | 41 | 10-year breakeven inflation rate from inflation-linked vs nominal bonds, in perc |
| BBG_Breakeven_10Y_CS | bloomberg | M | ? |  | 6 | 2000-01-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: 10-year breakeven infl |
| BBG_Breakeven_10Y_TS | bloomberg | M | ? |  | 6 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: 10-year breakeven inflation ra |
| BBG_CDS_5Y | bloomberg | M | ? |  | 20 | 2000-10-01→2026-05-01 | 41 | 5-year sovereign credit default swap spread, in basis points. |
| BBG_CDS_5Y_CS | bloomberg | M | ? |  | 20 | 2000-10-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: 5-year sovereign credi |
| BBG_CDS_5Y_TS | bloomberg | M | ? |  | 20 | 2002-09-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: 5-year sovereign credit defaul |
| BBG_Debt_GDP_Ratio | bloomberg | M | ? |  | 1 | 2011-03-01→2026-03-01 | 102 | Government debt as a percent of GDP (Bloomberg-sourced). |
| BBG_Debt_GDP_Ratio_TS | bloomberg | M | ? |  | 1 | 2016-12-01→2026-03-01 | 102 | Time-series z-score (vs own trailing history) of: Government debt as a percent o |
| BBG_ECFC_CPI | bloomberg | M | ? |  | 21 | 2010-01-01→2026-05-01 | 41 | Bloomberg consensus economist forecast for CPI inflation, in percent. |
| BBG_ECFC_CPI_CS | bloomberg | M | ? |  | 21 | 2010-01-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: Bloomberg consensus ec |
| BBG_ECFC_CPI_TS | bloomberg | M | ? |  | 21 | 2011-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: Bloomberg consensus economist  |
| BBG_ECFC_GDP | bloomberg | M | ? |  | 29 | 2010-12-01→2025-12-01 | 192 ⚠STALE | Bloomberg consensus economist forecast for real GDP growth, in percent. |
| BBG_ECFC_GDP_CS | bloomberg | M | ? |  | 27 | 2010-12-01→2025-12-01 | 192 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Bloomberg consensus ec |
| BBG_Govt_Bond_10Y | bloomberg | M | ? |  | 32 | 2000-01-01→2026-05-01 | 41 | 10-year government bond yield, in percent. |
| BBG_Govt_Bond_10Y_CS | bloomberg | M | ? |  | 32 | 2000-01-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: 10-year government bon |
| BBG_Govt_Bond_10Y_TS | bloomberg | M | ? |  | 32 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: 10-year government bond yield, |
| BBG_Govt_Bond_2Y | bloomberg | M | ? |  | 26 | 2000-01-01→2026-05-01 | 41 | 2-year government bond yield, in percent. |
| BBG_Govt_Bond_2Y_CS | bloomberg | M | ? |  | 26 | 2000-01-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: 2-year government bond |
| BBG_Govt_Bond_2Y_TS | bloomberg | M | ? |  | 26 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: 2-year government bond yield,  |
| BBG_Govt_Bond_30Y | bloomberg | M | ? |  | 17 | 2000-01-01→2026-05-01 | 41 | 30-year government bond yield, in percent. |
| BBG_Govt_Bond_30Y_CS | bloomberg | M | ? |  | 17 | 2000-01-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: 30-year government bon |
| BBG_Govt_Bond_30Y_TS | bloomberg | M | ? |  | 17 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: 30-year government bond yield, |
| BBG_Govt_Bond_5Y | bloomberg | M | ? |  | 29 | 2000-01-01→2026-05-01 | 41 | 5-year government bond yield, in percent. |
| BBG_Govt_Bond_5Y_CS | bloomberg | M | ? |  | 29 | 2000-01-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: 5-year government bond |
| BBG_Govt_Bond_5Y_TS | bloomberg | M | ? |  | 29 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: 5-year government bond yield,  |
| BBG_M2_YoY | bloomberg | M | ? |  | 13 | 2000-01-01→2026-05-01 | 41 | Broad money (M2) growth, year over year, in percent. |
| BBG_M2_YoY_CS | bloomberg | M | ? |  | 13 | 2000-01-01→2026-04-01 | 71 | Cross-sectional z-score (across the 34-country panel) of: Broad money (M2) growt |
| BBG_M2_YoY_TS | bloomberg | M | ? |  | 13 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: Broad money (M2) growth, year  |
| BBG_MIPD_5Y | bloomberg | M | ? |  | 20 | 2000-10-01→2026-05-01 | 41 | Bloomberg market-implied probability of sovereign default over 5 years, derived  |
| BBG_MIPD_5Y_CS | bloomberg | M | ? |  | 20 | 2000-10-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: Bloomberg market-impli |
| BBG_MIPD_5Y_TS | bloomberg | M | ? |  | 20 | 2002-09-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: Bloomberg market-implied proba |
| BBG_OIS_10Y | bloomberg | M | ? |  | 17 | 2000-01-01→2026-05-01 | 41 | 10-year overnight indexed swap rate, in percent. |
| BBG_OIS_10Y_CS | bloomberg | M | ? |  | 17 | 2000-01-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: 10-year overnight inde |
| BBG_OIS_10Y_TS | bloomberg | M | ? |  | 17 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: 10-year overnight indexed swap |
| BBG_PMI_Manufacturing | bloomberg | M | ? |  | 23 | 2023-06-01→2026-05-01 | 41 | Manufacturing Purchasing Managers Index (50 = expansion threshold). |
| BBG_PMI_Manufacturing_CS | bloomberg | M | ? |  | 23 | 2023-06-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: Manufacturing Purchasi |
| BBG_PMI_Manufacturing_TS | bloomberg | M | ? |  | 23 | 2025-05-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: Manufacturing Purchasing Manag |
| BBG_PMI_Services | bloomberg | M | ? |  | 13 | 2020-10-01→2026-05-01 | 41 | Services Purchasing Managers Index (50 = expansion threshold). |
| BBG_PMI_Services_CS | bloomberg | M | ? |  | 13 | 2023-06-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: Services Purchasing Ma |
| BBG_PMI_Services_TS | bloomberg | M | ? |  | 13 | 2022-09-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: Services Purchasing Managers I |
| BBG_Rating_Fitch_LC | bloomberg | M | ? |  | 32 | 2026-06-01→2026-06-01 | 10 |  |
| BBG_Rating_Fitch_LC_CS | bloomberg | M | ? |  | 32 | 2026-06-01→2026-06-01 | 10 |  |
| BBG_Rating_SP_FC | bloomberg | M | ? |  | 31 | 2026-06-01→2026-06-01 | 10 |  |
| BBG_Rating_SP_FC_CS | bloomberg | M | ? |  | 31 | 2026-06-01→2026-06-01 | 10 |  |
| BBG_Rating_SP_LC | bloomberg | M | ? |  | 31 | 2026-06-01→2026-06-01 | 10 |  |
| BBG_Rating_SP_LC_CS | bloomberg | M | ? |  | 31 | 2026-06-01→2026-06-01 | 10 |  |
| BBG_WIRP_ImpliedRate | bloomberg | M | ? |  | 25 | 2000-01-01→2026-05-01 | 41 | Policy rate implied by interest-rate futures/swaps for upcoming central bank mee |
| BBG_WIRP_ImpliedRate_CS | bloomberg | M | ? |  | 25 | 2000-01-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: Policy rate implied by |
| BBG_WIRP_ImpliedRate_TS | bloomberg | M | ? |  | 25 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: Policy rate implied by interes |
| BBG_Yield_Curve_10Y2Y | bloomberg | M | ? |  | 26 | 2000-01-01→2026-05-01 | 41 | 10-year minus 2-year government bond yield spread, in percentage points. |
| BBG_Yield_Curve_10Y2Y_CS | bloomberg | M | ? |  | 26 | 2000-01-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: 10-year minus 2-year g |
| BBG_Yield_Curve_10Y2Y_TS | bloomberg | M | ? |  | 26 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: 10-year minus 2-year governmen |
| BBG_ZSpread_OIS_10Y | bloomberg | M | ? |  | 17 | 2000-01-01→2026-05-01 | 41 | 10-year government bond yield minus the 10-year OIS rate, in basis points (sover |
| BBG_ZSpread_OIS_10Y_CS | bloomberg | M | ? |  | 17 | 2000-01-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: 10-year government bon |
| BBG_ZSpread_OIS_10Y_TS | bloomberg | M | ? |  | 17 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: 10-year government bond yield  |
| MS_Country_ETF_AUM_USD | bloomberg | M | ? |  | 34 | 2015-01-01→2026-05-01 | 41 | Total assets under management of US-listed single-country ETFs tracking this mar |
| MS_Country_ETF_AUM_USD_CS | bloomberg | M | ? |  | 34 | 2015-01-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: Total assets under man |
| MS_Country_ETF_AUM_USD_TS | bloomberg | M | ? |  | 34 | 2016-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: Total assets under management  |
| MS_Country_ETF_NetFlow_USD | bloomberg | M | ? |  | 34 | 2015-01-01→2026-05-01 | 41 | Net creations minus redemptions of US-listed country ETFs, in USD. |
| MS_Country_ETF_NetFlow_USD_CS | bloomberg | M | ? |  | 34 | 2015-01-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: Net creations minus re |
| MS_Country_ETF_NetFlow_USD_TS | bloomberg | M | ? |  | 34 | 2016-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: Net creations minus redemption |
| MS_ETF_Creation_Fee_USD | bloomberg | M | ? |  | 34 | 2026-06-01→2026-06-01 | 10 | Creation fee for the country's primary US-listed ETF, in USD. |
| MS_ETF_Creation_Fee_USD_CS | bloomberg | M | ? |  | 34 | 2026-06-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Creation fee for the c |
| MS_ETF_Creation_Unit_Size_Shares | bloomberg | M | ? |  | 34 | 2026-06-01→2026-06-01 | 10 | ETF creation unit size for the country's primary US-listed ETF, in shares. |
| MS_ETF_Creation_Unit_Size_Shares_CS | bloomberg | M | ? |  | 34 | 2026-06-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: ETF creation unit size |
| MS_ETF_NetCreation_Shares | bloomberg | M | ? |  | 34 | 2015-02-01→2026-05-01 | 41 | Net ETF shares created minus redeemed for the country's US-listed ETFs. |
| MS_ETF_NetCreation_Shares_CS | bloomberg | M | ? |  | 34 | 2015-02-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: Net ETF shares created |
| MS_ETF_NetCreation_Shares_TS | bloomberg | M | ? |  | 34 | 2017-01-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: Net ETF shares created minus r |
| MS_ETF_NetFlow_to_MarketCap | bloomberg | M | ? |  | 33 | 2015-01-01→2026-05-01 | 41 | Country ETF net flow scaled by the market's total capitalization. |
| MS_ETF_NetFlow_to_MarketCap_CS | bloomberg | M | ? |  | 33 | 2015-01-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: Country ETF net flow s |
| MS_ETF_NetFlow_to_MarketCap_TS | bloomberg | M | ? |  | 33 | 2016-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: Country ETF net flow scaled by |
| MS_ETF_Redemption_Fee_USD | bloomberg | M | ? |  | 33 | 2026-06-01→2026-06-01 | 10 | Redemption fee for the country's primary US-listed ETF, in USD. |
| MS_Index_Weight | bloomberg | M | ? |  | 33 | 1975-12-01→2025-12-01 | 192 ⚠STALE | Country weight in the relevant MSCI benchmark index, in percent. |
| MS_Index_Weight_CS | bloomberg | M | ? |  | 33 | 1975-12-01→2025-12-01 | 192 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Country weight in the  |
| MS_Index_Weight_Change | bloomberg | M | ? |  | 33 | 1976-12-01→2025-12-01 | 192 ⚠STALE | Change in the country's MSCI benchmark weight, in percentage points. |
| MS_Index_Weight_Change_CS | bloomberg | M | ? |  | 33 | 1976-12-01→2025-12-01 | 192 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Change in the country' |
| MS_Index_Weight_Change_TS | bloomberg | M | ? |  | 29 | 1999-12-01→2025-12-01 | 192 ⚠STALE | Time-series z-score (vs own trailing history) of: Change in the country's MSCI b |
| MS_Index_Weight_TS | bloomberg | M | ? |  | 29 | 1998-12-01→2025-12-01 | 192 ⚠STALE | Time-series z-score (vs own trailing history) of: Country weight in the relevant |
| MS_Passive_AUM_to_MarketCap | bloomberg | M | ? |  | 33 | 2015-01-01→2026-05-01 | 41 | Passive (ETF) assets tracking the market as a share of its total capitalization. |
| MS_Passive_AUM_to_MarketCap_CS | bloomberg | M | ? |  | 33 | 2015-01-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: Passive (ETF) assets t |
| MS_Passive_AUM_to_MarketCap_TS | bloomberg | M | ? |  | 33 | 2016-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: Passive (ETF) assets tracking  |
| MS_Passive_Flow_Distortion | bloomberg | M | ↓ |  | 33 | 1976-12-01→2026-05-01 | 41 | ASADO-derived measure of price pressure attributable to passive flows (flow inte |
| MS_Passive_Flow_Distortion_CS | bloomberg | M | ↓ |  | 33 | 1976-12-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: ASADO-derived measure  |
| MS_Passive_Flow_Distortion_TS | bloomberg | M | ↓ |  | 33 | 1999-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ASADO-derived measure of price |
| DIP_abs | demographics_dip | M | ? |  | 34 | 1950-12-01→2100-12-01 | -27201 | Demographic Inflation Pressure, absolute — the inflation pressure (in CPI percen |
| DIP_abs_CS | demographics_dip | M | ? |  | 34 | 1950-12-01→2100-12-01 | -27201 | Cross-sectional z-score (across the 34-country panel) of: Demographic Inflation  |
| DIP_abs_TS | demographics_dip | M | ? |  | 34 | 1973-12-01→2100-12-01 | -27201 | Time-series z-score (vs own trailing history) of: Demographic Inflation Pressure |
| DIP_rel | demographics_dip | M | ? |  | 34 | 1950-12-01→2100-12-01 | -27201 | Demographic Inflation Pressure relative to the 34-country panel mean each year,  |
| DIP_rel_CS | demographics_dip | M | ? |  | 34 | 1950-12-01→2100-12-01 | -27201 | Cross-sectional z-score (across the 34-country panel) of: Demographic Inflation  |
| DIP_rel_TS | demographics_dip | M | ? |  | 34 | 1973-12-01→2100-12-01 | -27201 | Time-series z-score (vs own trailing history) of: Demographic Inflation Pressure |
| DIP_rel_chg_10y | demographics_dip | M | ? |  | 34 | 1960-12-01→2100-12-01 | -27201 | 10-year change in DIP_rel. |
| DIP_rel_chg_10y_CS | demographics_dip | M | ? |  | 34 | 1960-12-01→2100-12-01 | -27201 | Cross-sectional z-score (across the 34-country panel) of: 10-year change in DIP_ |
| DIP_rel_chg_10y_TS | demographics_dip | M | ? |  | 34 | 1983-12-01→2100-12-01 | -27201 | Time-series z-score (vs own trailing history) of: 10-year change in DIP_rel. |
| DIP_rel_chg_5y | demographics_dip | M | ? |  | 34 | 1955-12-01→2100-12-01 | -27201 | 5-year change in DIP_rel — how fast the country's relative demographic inflation |
| DIP_rel_chg_5y_CS | demographics_dip | M | ? |  | 34 | 1955-12-01→2100-12-01 | -27201 | Cross-sectional z-score (across the 34-country panel) of: 5-year change in DIP_r |
| DIP_rel_chg_5y_TS | demographics_dip | M | ? |  | 34 | 1978-12-01→2100-12-01 | -27201 | Time-series z-score (vs own trailing history) of: 5-year change in DIP_rel — how |
| ECB_FX_AUD_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: Australian dollar (AUD) per 1 euro. |
| ECB_FX_AUD_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_BRL_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: Brazilian real (BRL) per 1 euro. |
| ECB_FX_BRL_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_CAD_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: Canadian dollar (CAD) per 1 euro. |
| ECB_FX_CAD_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_CHF_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: Swiss franc (CHF) per 1 euro. |
| ECB_FX_CHF_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_CNY_EUR | ecb_fx | M | ? |  | 2 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: Chinese yuan (CNY) per 1 euro. |
| ECB_FX_CNY_EUR_TS | ecb_fx | M | ? |  | 2 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_DKK_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: Danish krone (DKK) per 1 euro. |
| ECB_FX_DKK_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_EUR_EUR | ecb_fx | M | ? |  | 5 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: euro (EUR) per 1 euro. |
| ECB_FX_GBP_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: British pound (GBP) per 1 euro. |
| ECB_FX_GBP_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_HKD_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: Hong Kong dollar (HKD) per 1 euro. |
| ECB_FX_HKD_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_IDR_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: Indonesian rupiah (IDR) per 1 euro. |
| ECB_FX_IDR_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_INR_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: Indian rupee (INR) per 1 euro. |
| ECB_FX_INR_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_JPY_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: Japanese yen (JPY) per 1 euro. |
| ECB_FX_JPY_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_KRW_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: Korean won (KRW) per 1 euro. |
| ECB_FX_KRW_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_MXN_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: Mexican peso (MXN) per 1 euro. |
| ECB_FX_MXN_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_MYR_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: Malaysian ringgit (MYR) per 1 euro. |
| ECB_FX_MYR_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_NOK_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: Norwegian krone (NOK) per 1 euro. |
| ECB_FX_NOK_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_NZD_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: New Zealand dollar (NZD) per 1 euro. |
| ECB_FX_NZD_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_PHP_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: Philippine peso (PHP) per 1 euro. |
| ECB_FX_PHP_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_PLN_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: Polish zloty (PLN) per 1 euro. |
| ECB_FX_PLN_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_SEK_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: Swedish krona (SEK) per 1 euro. |
| ECB_FX_SEK_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_SGD_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: Singapore dollar (SGD) per 1 euro. |
| ECB_FX_SGD_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_THB_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: Thai baht (THB) per 1 euro. |
| ECB_FX_THB_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_TRY_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: Turkish lira (TRY) per 1 euro. |
| ECB_FX_TRY_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_TWD_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2020-10-01 | 2079 ⚠STALE | ECB daily reference exchange rate: New Taiwan dollar (TWD) per 1 euro. |
| ECB_FX_TWD_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2020-10-01 | 2079 ⚠STALE | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_USD_EUR | ecb_fx | M | ? |  | 3 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: US dollar (USD) per 1 euro. |
| ECB_FX_USD_EUR_CS | ecb_fx | M | ? |  | 3 | 2000-04-01→2014-06-01 | 4393 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: ECB daily reference ex |
| ECB_FX_USD_EUR_TS | ecb_fx | M | ? |  | 3 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| ECB_FX_ZAR_EUR | ecb_fx | M | ? |  | 1 | 2000-01-01→2026-05-01 | 41 | ECB daily reference exchange rate: South African rand (ZAR) per 1 euro. |
| ECB_FX_ZAR_EUR_TS | ecb_fx | M | ? |  | 1 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ECB daily reference exchange r |
| EIA_Petroleum_Consumption_TBPD | eia | A | ? |  | 43 | 2000-12-01→2025-12-01 | 192 | Petroleum consumption in thousand barrels per day (EIA). |
| EIA_Petroleum_Consumption_TBPD_CS | eia | A | ? |  | 43 | 2000-12-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Petroleum consumption  |
| EIA_Petroleum_Consumption_TBPD_TS | eia | A | ? |  | 43 | 2004-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Petroleum consumption in thous |
| EPU | epu | M | ? |  | 22 | 1985-01-01→2025-11-01 | 222 ⚠STALE | Economic Policy Uncertainty index — newspaper-based frequency of policy-uncertai |
| EPU_CS | epu | M | ? |  | 22 | 1985-01-01→2025-11-01 | 222 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Economic Policy Uncert |
| EPU_TS | epu | M | ? |  | 22 | 1986-12-01→2025-11-01 | 222 ⚠STALE | Time-series z-score (vs own trailing history) of: Economic Policy Uncertainty in |
| FAO_AgExport_GDP_Share | faostat | A | ? |  | 32 | 2010-12-01→2024-12-01 | 557 ⚠STALE | Agricultural exports as a share of GDP (FAO). |
| FAO_AgExport_GDP_Share_CS | faostat | A | ? |  | 32 | 2010-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Agricultural exports a |
| FAO_AgExport_GDP_Share_TS | faostat | A | ? |  | 32 | 2014-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Agricultural exports as a shar |
| FAO_Import_Dependency | faostat | A | ↓ |  | 33 | 2010-12-01→2024-12-01 | 557 ⚠STALE | Food import dependency ratio — imports relative to domestic supply (FAO). |
| FAO_Import_Dependency_CS | faostat | A | ↓ |  | 33 | 2010-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Food import dependency |
| FAO_Import_Dependency_TS | faostat | A | ↓ |  | 31 | 2014-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Food import dependency ratio — |
| FAO_Self_Sufficiency | faostat | A | ? |  | 33 | 2010-12-01→2024-12-01 | 557 ⚠STALE | Food self-sufficiency ratio — domestic production relative to consumption (FAO). |
| FAO_Self_Sufficiency_CS | faostat | A | ? |  | 33 | 2010-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Food self-sufficiency  |
| FAO_Self_Sufficiency_TS | faostat | A | ? |  | 31 | 2014-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Food self-sufficiency ratio —  |
| FAO_Terms_of_Trade | faostat | A | ? |  | 33 | 2010-12-01→2024-12-01 | 557 ⚠STALE | Agricultural terms of trade — export vs import price relation for food (FAO). |
| FAO_Terms_of_Trade_CS | faostat | A | ? |  | 33 | 2010-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Agricultural terms of  |
| FAO_Terms_of_Trade_TS | faostat | A | ? |  | 33 | 2014-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Agricultural terms of trade —  |
| FAO_Trade_Openness | faostat | A | ? |  | 32 | 2010-12-01→2024-12-01 | 557 ⚠STALE | Agricultural trade openness — food trade flows relative to GDP (FAO). |
| FAO_Trade_Openness_CS | faostat | A | ? |  | 32 | 2010-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Agricultural trade ope |
| FAO_Trade_Openness_TS | faostat | A | ? |  | 30 | 2014-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Agricultural trade openness —  |
| FRED_HY_OAS | fred | M | ? |  | 34 | 2023-07-01→2026-05-01 | 41 | ICE BofA US High Yield option-adjusted spread, in basis points (global broadcast |
| FRED_HY_OAS_CS | fred | M | ? |  | 34 | 2023-07-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: ICE BofA US High Yield |
| FRED_HY_OAS_TS | fred | M | ? |  | 34 | 2025-06-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: ICE BofA US High Yield option- |
| FRED_USD_Broad_Index | fred | M | ↓ |  | 34 | 2006-01-01→2026-05-01 | 41 | Federal Reserve broad trade-weighted US dollar index (global broadcast). |
| FRED_USD_Broad_Index_CS | fred | M | ↓ |  | 34 | 2006-02-01→2026-04-01 | 71 | Cross-sectional z-score (across the 34-country panel) of: Federal Reserve broad  |
| FRED_USD_Broad_Index_TS | fred | M | ↓ |  | 34 | 2007-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: Federal Reserve broad trade-we |
| FRED_UST_10Y | fred | M | ? |  | 43 | 2000-01-01→2026-05-01 | 41 | US 10-year Treasury yield, in percent (global broadcast). |
| FRED_UST_10Y_CS | fred | M | ? |  | 43 | 2000-01-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: US 10-year Treasury yi |
| FRED_UST_10Y_TS | fred | M | ? |  | 43 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: US 10-year Treasury yield, in  |
| FRED_UST_2Y | fred | M | ? |  | 43 | 2000-01-01→2026-05-01 | 41 | US 2-year Treasury yield, in percent (global broadcast). |
| FRED_UST_2Y_CS | fred | M | ? |  | 43 | 2000-02-01→2026-04-01 | 71 | Cross-sectional z-score (across the 34-country panel) of: US 2-year Treasury yie |
| FRED_UST_2Y_TS | fred | M | ? |  | 43 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: US 2-year Treasury yield, in p |
| FRED_VIX | fred | M | ? |  | 34 | 2000-01-01→2026-05-01 | 41 | CBOE VIX index — 30-day implied volatility of S&P 500 options (global broadcast) |
| FRED_VIX_CS | fred | M | ? |  | 34 | 2000-01-01→2026-04-01 | 71 | Cross-sectional z-score (across the 34-country panel) of: CBOE VIX index — 30-da |
| FRED_VIX_TS | fred | M | ? |  | 34 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: CBOE VIX index — 30-day implie |
| FRED_Yield_Curve_10Y2Y | fred | M | ? |  | 43 | 2000-01-01→2026-05-01 | 41 | US 10-year minus 2-year Treasury spread, in percentage points (global broadcast) |
| FRED_Yield_Curve_10Y2Y_CS | fred | M | ? |  | 43 | 2000-01-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: US 10-year minus 2-yea |
| FRED_Yield_Curve_10Y2Y_TS | fred | M | ? |  | 43 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: US 10-year minus 2-year Treasu |
| 1MRet | gdelt | M | ↑ | RET-ALIAS | 34 | 2015-09-01→2026-06-01 | 10 |  |
| attention_fast_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| attention_fast_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| attention_fast_z_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| attention_fast_z_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| attention_shock_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| attention_shock_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| attention_slow_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| attention_slow_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| attention_slow_z_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| attention_slow_z_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| attention_trend_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| attention_trend_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| attention_trend_z_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| attention_trend_z_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| country_news_attention_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| country_news_attention_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| country_news_risk_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| country_news_risk_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| country_news_risk_raw_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| country_news_risk_raw_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| country_news_sentiment_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| country_news_sentiment_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| country_news_sentiment_raw_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| country_news_sentiment_raw_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| defensive_rank_pct_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| defensive_rank_pct_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| dispersion_fast_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| dispersion_fast_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| dispersion_fast_z_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| dispersion_fast_z_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| foreign_tone_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| foreign_tone_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| foreign_tone_fast_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| foreign_tone_fast_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| foreign_tone_fast_z_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| foreign_tone_fast_z_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| lf_gap_z_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| lf_gap_z_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| local_attention_share_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| local_attention_share_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| local_foreign_gap_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| local_foreign_gap_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| local_tone_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| local_tone_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| local_tone_fast_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| local_tone_fast_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| local_tone_fast_z_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| local_tone_fast_z_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| metronome_rank_pct_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| metronome_rank_pct_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| monthly_defensive_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| monthly_defensive_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| monthly_metronome_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| monthly_metronome_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| monthly_risk_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| monthly_risk_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| n_articles_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| n_articles_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| negative_mean_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| negative_mean_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| polarity_mean_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| polarity_mean_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| positive_mean_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| positive_mean_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| risk_fast_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| risk_fast_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| risk_fast_z_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| risk_fast_z_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| risk_rank_pct_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| risk_rank_pct_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| sentiment_fast_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| sentiment_fast_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| sentiment_fast_z_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| sentiment_fast_z_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| sentiment_slow_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| sentiment_slow_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| sentiment_slow_z_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| sentiment_slow_z_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| sentiment_trend_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| sentiment_trend_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| sentiment_trend_z_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| sentiment_trend_z_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| sentiment_x_attention_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| sentiment_x_attention_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| tone_dispersion_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| tone_dispersion_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| tone_mean_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| tone_mean_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| tone_p50_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| tone_p50_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| tone_wavg_wordcount_CS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| tone_wavg_wordcount_TS | gdelt | M | ↑ |  | 34 | 2015-09-01→2026-07-01 | -20 |  |
| GPR | gpr | M | ? |  | 23 | 1985-01-01→2026-05-01 | 41 | Country-level Geopolitical Risk index — share of news articles mentioning geopol |
| GPR_CS | gpr | M | ? |  | 23 | 1985-01-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: Country-level Geopolit |
| GPR_TS | gpr | M | ? |  | 23 | 1986-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: Country-level Geopolitical Ris |
| Global_GPR | gpr | M | ↓ |  | 43 | 1985-01-01→2026-05-01 | 41 | Global Geopolitical Risk index (broadcast to all countries). |
| Global_GPR_Act | gpr | M | ↓ |  | 43 | 1985-01-01→2026-05-01 | 41 | Global GPR acts sub-index — realized geopolitical events (wars, attacks) as oppo |
| Global_GPR_Act_TS | gpr | M | ↓ |  | 43 | 1986-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: Global GPR acts sub-index — re |
| Global_GPR_TS | gpr | M | ↓ |  | 43 | 1986-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: Global Geopolitical Risk index |
| Global_GPR_Threat | gpr | M | ↓ |  | 43 | 1985-01-01→2026-05-01 | 41 | Global GPR threats sub-index — threatened/anticipated geopolitical tensions. |
| Global_GPR_Threat_TS | gpr | M | ↓ |  | 43 | 1986-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: Global GPR threats sub-index — |
| ILO_LFP_Rate | ilostat | A | ? |  | 43 | 2000-12-01→2025-12-01 | 192 | Labor force participation rate from ILOSTAT, in percent. |
| ILO_LFP_Rate_CS | ilostat | A | ? |  | 43 | 2000-12-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Labor force participat |
| ILO_LFP_Rate_TS | ilostat | A | ? |  | 43 | 2004-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Labor force participation rate |
| ILO_Unemployment_Rate | ilostat | A | ↓ |  | 43 | 2000-12-01→2025-12-01 | 192 | Unemployment rate from ILOSTAT modeled estimates, in percent. |
| ILO_Unemployment_Rate_CS | ilostat | A | ↓ |  | 43 | 2000-12-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Unemployment rate from |
| ILO_Unemployment_Rate_TS | ilostat | A | ↓ |  | 43 | 2004-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Unemployment rate from ILOSTAT |
| IMF_BOP_Current_Account | imf_bop | A | ? |  | 43 | 2005-12-01→2024-12-01 | 557 ⚠STALE | Current account balance from IMF Balance of Payments statistics, in USD. |
| IMF_BOP_Current_Account_CS | imf_bop | A | ? |  | 43 | 2005-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Current account balanc |
| IMF_BOP_Current_Account_TS | imf_bop | A | ? |  | 43 | 2009-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Current account balance from I |
| IMF_BOP_Direct_Investment_Net | imf_bop | A | ? |  | 42 | 2005-12-01→2024-12-01 | 557 ⚠STALE | Net foreign direct investment from IMF BOP, in USD. |
| IMF_BOP_Direct_Investment_Net_CS | imf_bop | A | ? |  | 42 | 2005-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Net foreign direct inv |
| IMF_BOP_Direct_Investment_Net_TS | imf_bop | A | ? |  | 42 | 2009-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Net foreign direct investment  |
| IMF_BOP_Financial_Account_Bal | imf_bop | A | ? |  | 43 | 2005-12-01→2024-12-01 | 557 ⚠STALE | Financial account balance from IMF BOP, in USD. |
| IMF_BOP_Financial_Account_Bal_CS | imf_bop | A | ? |  | 43 | 2005-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Financial account bala |
| IMF_BOP_Financial_Account_Bal_TS | imf_bop | A | ? |  | 43 | 2009-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Financial account balance from |
| IMF_BOP_Portfolio_Investment_Net | imf_bop | A | ? |  | 42 | 2005-12-01→2024-12-01 | 557 ⚠STALE | Net portfolio investment from IMF BOP, in USD. |
| IMF_BOP_Portfolio_Investment_Net_CS | imf_bop | A | ? |  | 42 | 2005-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Net portfolio investme |
| IMF_BOP_Portfolio_Investment_Net_TS | imf_bop | A | ? |  | 42 | 2009-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Net portfolio investment from  |
| IMF_CPI_Index | imf_cpi | M | ? |  | 41 | 2000-01-01→2026-04-01 | 71 | Consumer price index level (IMF IFS). |
| IMF_CPI_Index_CS | imf_cpi | M | ? |  | 41 | 2000-01-01→2026-04-01 | 71 | Cross-sectional z-score (across the 34-country panel) of: Consumer price index l |
| IMF_CPI_Index_TS | imf_cpi | M | ? |  | 41 | 2001-12-01→2026-04-01 | 71 | Time-series z-score (vs own trailing history) of: Consumer price index level (IM |
| IMF_CPI_Inflation_YoY | imf_cpi | M | ? |  | 41 | 2001-01-01→2026-04-01 | 71 | Consumer price inflation, year over year, from IMF IFS, in percent. |
| IMF_CPI_Inflation_YoY_CS | imf_cpi | M | ? |  | 41 | 2001-01-01→2026-04-01 | 71 | Cross-sectional z-score (across the 34-country panel) of: Consumer price inflati |
| IMF_CPI_Inflation_YoY_TS | imf_cpi | M | ? |  | 40 | 2002-12-01→2026-04-01 | 71 | Time-series z-score (vs own trailing history) of: Consumer price inflation, year |
| IMF_XRate_LCU_per_USD | imf_er | M | ? |  | 33 | 2000-01-01→2026-05-01 | 41 | Exchange rate in local currency units per USD (IMF IFS, period average). |
| IMF_XRate_LCU_per_USD_CS | imf_er | M | ? |  | 33 | 2000-01-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: Exchange rate in local |
| IMF_XRate_LCU_per_USD_TS | imf_er | M | ? |  | 28 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: Exchange rate in local currenc |
| MS_Bank_Capital_Adequacy | imf_fsi | Q | ? |  | 41 | 2001-03-01→2025-12-01 | 192 | Bank regulatory capital to risk-weighted assets (IMF Financial Soundness Indicat |
| MS_Bank_Capital_Adequacy_CS | imf_fsi | Q | ? |  | 41 | 2005-03-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Bank regulatory capita |
| MS_Bank_Capital_Adequacy_TS | imf_fsi | Q | ? |  | 41 | 2002-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Bank regulatory capital to ris |
| MS_Bank_Liquidity_Coverage_Ratio | imf_fsi | Q | ? |  | 31 | 2015-03-01→2025-12-01 | 192 | Bank liquidity coverage ratio (high-quality liquid assets vs 30-day stressed out |
| MS_Bank_Liquidity_Coverage_Ratio_CS | imf_fsi | Q | ? |  | 31 | 2015-06-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Bank liquidity coverag |
| MS_Bank_Liquidity_Coverage_Ratio_TS | imf_fsi | Q | ? |  | 30 | 2016-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Bank liquidity coverage ratio  |
| MS_Bank_Liquidity_Ratio | imf_fsi | Q | ? |  | 39 | 2001-03-01→2025-12-01 | 192 | Bank liquid assets to total assets (IMF FSI), in percent. |
| MS_Bank_Liquidity_Ratio_CS | imf_fsi | Q | ? |  | 39 | 2005-03-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Bank liquid assets to  |
| MS_Bank_Liquidity_Ratio_TS | imf_fsi | Q | ? |  | 39 | 2002-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Bank liquid assets to total as |
| MS_Bank_Net_Stable_Funding_Ratio | imf_fsi | Q | ? |  | 25 | 2018-03-01→2025-12-01 | 192 | Bank net stable funding ratio (available vs required stable funding, IMF FSI), i |
| MS_Bank_Net_Stable_Funding_Ratio_CS | imf_fsi | Q | ? |  | 25 | 2018-03-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Bank net stable fundin |
| MS_Bank_Net_Stable_Funding_Ratio_TS | imf_fsi | Q | ? |  | 23 | 2019-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Bank net stable funding ratio  |
| MS_NPL_Net_Provisions_to_Capital_Pct | imf_fsi | Q | ? |  | 41 | 2001-03-01→2025-12-01 | 192 | NPLs net of provisions as a percent of bank capital (IMF FSI). |
| MS_NPL_Net_Provisions_to_Capital_Pct_CS | imf_fsi | Q | ? |  | 41 | 2005-03-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: NPLs net of provisions |
| MS_NPL_Net_Provisions_to_Capital_Pct_TS | imf_fsi | Q | ? |  | 41 | 2002-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: NPLs net of provisions as a pe |
| MS_NPL_Ratio | imf_fsi | Q | ↓ |  | 41 | 2001-03-01→2025-12-01 | 192 | Non-performing loans to total gross loans (IMF FSI), in percent. |
| MS_NPL_Ratio_CS | imf_fsi | Q | ↓ |  | 41 | 2005-03-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Non-performing loans t |
| MS_NPL_Ratio_TS | imf_fsi | Q | ↓ |  | 41 | 2002-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Non-performing loans to total  |
| IMF_Export_Price_Index | imf_itg | M | ? |  | 21 | 2000-01-01→2025-12-01 | 192 ⚠STALE | Export price index (IMF IFS). |
| IMF_Export_Price_Index_CS | imf_itg | M | ? |  | 21 | 2000-01-01→2025-10-01 | 253 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Export price index (IM |
| IMF_Export_Price_Index_TS | imf_itg | M | ? |  | 21 | 2001-12-01→2025-12-01 | 192 ⚠STALE | Time-series z-score (vs own trailing history) of: Export price index (IMF IFS). |
| IMF_Exports_USD | imf_itg | M | ? |  | 43 | 2000-01-01→2026-03-01 | 102 | Merchandise exports in USD (IMF IFS/DOTS). |
| IMF_Exports_USD_CS | imf_itg | M | ? |  | 43 | 2005-01-01→2026-03-01 | 102 | Cross-sectional z-score (across the 34-country panel) of: Merchandise exports in |
| IMF_Exports_USD_TS | imf_itg | M | ? |  | 43 | 2001-12-01→2026-03-01 | 102 | Time-series z-score (vs own trailing history) of: Merchandise exports in USD (IM |
| IMF_Exports_YoY | imf_itg | M | ? |  | 28 | 2000-01-01→2026-02-01 | 130 ⚠STALE | Merchandise export growth, year over year, in percent. |
| IMF_Exports_YoY_CS | imf_itg | M | ? |  | 28 | 2007-01-01→2024-04-01 | 801 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Merchandise export gro |
| IMF_Exports_YoY_TS | imf_itg | M | ? |  | 25 | 2001-12-01→2026-02-01 | 130 ⚠STALE | Time-series z-score (vs own trailing history) of: Merchandise export growth, yea |
| IMF_Import_Price_Index | imf_itg | M | ? |  | 26 | 2000-01-01→2026-03-01 | 102 | Import price index (IMF IFS). |
| IMF_Import_Price_Index_CS | imf_itg | M | ? |  | 26 | 2000-01-01→2026-03-01 | 102 | Cross-sectional z-score (across the 34-country panel) of: Import price index (IM |
| IMF_Import_Price_Index_TS | imf_itg | M | ? |  | 26 | 2001-12-01→2026-03-01 | 102 | Time-series z-score (vs own trailing history) of: Import price index (IMF IFS). |
| IMF_Imports_USD | imf_itg | M | ? |  | 41 | 2000-01-01→2026-03-01 | 102 | Merchandise imports in USD (IMF IFS/DOTS). |
| IMF_Imports_USD_CS | imf_itg | M | ? |  | 41 | 2005-01-01→2026-03-01 | 102 | Cross-sectional z-score (across the 34-country panel) of: Merchandise imports in |
| IMF_Imports_USD_TS | imf_itg | M | ? |  | 41 | 2001-12-01→2026-03-01 | 102 | Time-series z-score (vs own trailing history) of: Merchandise imports in USD (IM |
| IMF_Imports_YoY | imf_itg | M | ? |  | 27 | 2000-01-01→2026-02-01 | 130 ⚠STALE | Merchandise import growth, year over year, in percent. |
| IMF_Imports_YoY_CS | imf_itg | M | ? |  | 27 | 2007-01-01→2024-04-01 | 801 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Merchandise import gro |
| IMF_Imports_YoY_TS | imf_itg | M | ? |  | 24 | 2001-12-01→2026-02-01 | 130 ⚠STALE | Time-series z-score (vs own trailing history) of: Merchandise import growth, yea |
| IMF_Trade_Balance_USD | imf_itg | M | ? |  | 41 | 2000-01-01→2026-03-01 | 102 | Merchandise trade balance (exports minus imports), in USD. |
| IMF_Trade_Balance_USD_CS | imf_itg | M | ? |  | 41 | 2005-01-01→2026-03-01 | 102 | Cross-sectional z-score (across the 34-country panel) of: Merchandise trade bala |
| IMF_Trade_Balance_USD_TS | imf_itg | M | ? |  | 41 | 2001-12-01→2026-03-01 | 102 | Time-series z-score (vs own trailing history) of: Merchandise trade balance (exp |
| IMF_Trade_Openness_USD | imf_itg | M | ? |  | 41 | 2000-01-01→2026-03-01 | 102 | Exports plus imports in USD (gross trade flows). |
| IMF_Trade_Openness_USD_CS | imf_itg | M | ? |  | 41 | 2005-01-01→2026-03-01 | 102 | Cross-sectional z-score (across the 34-country panel) of: Exports plus imports i |
| IMF_Trade_Openness_USD_TS | imf_itg | M | ? |  | 41 | 2001-12-01→2026-03-01 | 102 | Time-series z-score (vs own trailing history) of: Exports plus imports in USD (g |
| IMF_Employment_Index | imf_ls | M | ? |  | 13 | 2000-01-01→2026-03-01 | 102 | Employment index from IMF IFS (base period = 100). |
| IMF_Employment_Index_CS | imf_ls | M | ? |  | 13 | 2000-01-01→2026-02-01 | 130 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Employment index from  |
| IMF_Employment_Index_TS | imf_ls | M | ? |  | 13 | 2001-12-01→2026-03-01 | 102 | Time-series z-score (vs own trailing history) of: Employment index from IMF IFS  |
| MS_CentralBank_BalanceSheet_GDP | imf_mfs_cbs | M | ? |  | 24 | 1997-12-01→2026-04-01 | 71 | Central bank balance sheet size as percent of GDP. |
| MS_CentralBank_BalanceSheet_GDP_CS | imf_mfs_cbs | M | ? |  | 24 | 2001-01-01→2026-04-01 | 71 | Cross-sectional z-score (across the 34-country panel) of: Central bank balance s |
| MS_CentralBank_BalanceSheet_GDP_TS | imf_mfs_cbs | M | ? |  | 24 | 1999-11-01→2026-04-01 | 71 | Time-series z-score (vs own trailing history) of: Central bank balance sheet siz |
| MS_CentralBank_Claims_on_Government_Pct_GDP | imf_mfs_cbs | M | ? |  | 35 | 1997-12-01→2026-04-01 | 71 | Central bank claims on central government as percent of GDP. |
| MS_CentralBank_Claims_on_Government_Pct_GDP_CS | imf_mfs_cbs | M | ? |  | 35 | 2000-12-01→2026-04-01 | 71 | Cross-sectional z-score (across the 34-country panel) of: Central bank claims on |
| MS_CentralBank_Claims_on_Government_Pct_GDP_TS | imf_mfs_cbs | M | ? |  | 33 | 1999-11-01→2026-04-01 | 71 | Time-series z-score (vs own trailing history) of: Central bank claims on central |
| IMF_Discount_Rate | imf_mfs_ir | M | ? |  | 10 | 2000-01-01→2026-04-01 | 71 | Central bank discount/policy rate from IMF IFS, in percent. |
| IMF_Discount_Rate_CS | imf_mfs_ir | M | ? |  | 10 | 2000-01-01→2026-04-01 | 71 | Cross-sectional z-score (across the 34-country panel) of: Central bank discount/ |
| IMF_Discount_Rate_TS | imf_mfs_ir | M | ? |  | 10 | 2001-12-01→2026-04-01 | 71 | Time-series z-score (vs own trailing history) of: Central bank discount/policy r |
| IMF_Govt_Bond_Yield | imf_mfs_ir | M | ? |  | 29 | 2000-01-01→2026-04-01 | 71 | Long-term government bond yield from IMF IFS, in percent. |
| IMF_Govt_Bond_Yield_CS | imf_mfs_ir | M | ? |  | 29 | 2000-01-01→2026-04-01 | 71 | Cross-sectional z-score (across the 34-country panel) of: Long-term government b |
| IMF_Govt_Bond_Yield_TS | imf_mfs_ir | M | ? |  | 29 | 2001-12-01→2026-04-01 | 71 | Time-series z-score (vs own trailing history) of: Long-term government bond yiel |
| IMF_Money_Market_Rate | imf_mfs_ir | M | ↓ |  | 26 | 2000-01-01→2026-04-01 | 71 | Short-term interbank money market rate from IMF IFS, in percent. |
| IMF_Money_Market_Rate_CS | imf_mfs_ir | M | ↓ |  | 26 | 2000-01-01→2026-04-01 | 71 | Cross-sectional z-score (across the 34-country panel) of: Short-term interbank m |
| IMF_Money_Market_Rate_TS | imf_mfs_ir | M | ↓ |  | 26 | 2001-12-01→2026-04-01 | 71 | Time-series z-score (vs own trailing history) of: Short-term interbank money mar |
| IMF_TBill_Rate | imf_mfs_ir | M | ? |  | 20 | 2000-01-01→2026-04-01 | 71 | Treasury bill rate from IMF IFS, in percent. |
| IMF_TBill_Rate_CS | imf_mfs_ir | M | ? |  | 20 | 2000-01-01→2026-04-01 | 71 | Cross-sectional z-score (across the 34-country panel) of: Treasury bill rate fro |
| IMF_TBill_Rate_TS | imf_mfs_ir | M | ? |  | 20 | 2001-12-01→2026-04-01 | 71 | Time-series z-score (vs own trailing history) of: Treasury bill rate from IMF IF |
| IMF_WEO_CA_GDP | imf_weo | A | ? |  | 43 | 1980-12-01→2031-12-01 | -1999 | IMF WEO current account balance as percent of GDP. |
| IMF_WEO_CA_GDP_CS | imf_weo | A | ? |  | 43 | 1980-12-01→2031-12-01 | -1999 | Cross-sectional z-score (across the 34-country panel) of: IMF WEO current accoun |
| IMF_WEO_CA_GDP_TS | imf_weo | A | ? |  | 43 | 1984-12-01→2031-12-01 | -1999 | Time-series z-score (vs own trailing history) of: IMF WEO current account balanc |
| IMF_WEO_Debt_GDP | imf_weo | A | ↓ |  | 43 | 1980-12-01→2031-12-01 | -1999 | IMF WEO general government gross debt as percent of GDP. |
| IMF_WEO_Debt_GDP_CS | imf_weo | A | ↓ |  | 43 | 1980-12-01→2031-12-01 | -1999 | Cross-sectional z-score (across the 34-country panel) of: IMF WEO general govern |
| IMF_WEO_Debt_GDP_TS | imf_weo | A | ↓ |  | 43 | 1984-12-01→2031-12-01 | -1999 | Time-series z-score (vs own trailing history) of: IMF WEO general government gro |
| IMF_WEO_GDP_Growth | imf_weo | A | ? |  | 43 | 1980-12-01→2031-12-01 | -1999 | IMF World Economic Outlook real GDP growth (history + forecast vintages), in per |
| IMF_WEO_GDP_Growth_CS | imf_weo | A | ? |  | 43 | 1980-12-01→2031-12-01 | -1999 | Cross-sectional z-score (across the 34-country panel) of: IMF World Economic Out |
| IMF_WEO_GDP_Growth_TS | imf_weo | A | ? |  | 43 | 1984-12-01→2031-12-01 | -1999 | Time-series z-score (vs own trailing history) of: IMF World Economic Outlook rea |
| IMF_WEO_Inflation | imf_weo | A | ? |  | 43 | 1980-12-01→2031-12-01 | -1999 | IMF WEO consumer price inflation (history + forecast vintages), in percent. |
| IMF_WEO_Inflation_CS | imf_weo | A | ? |  | 43 | 1980-12-01→2031-12-01 | -1999 | Cross-sectional z-score (across the 34-country panel) of: IMF WEO consumer price |
| IMF_WEO_Inflation_TS | imf_weo | A | ? |  | 43 | 1984-12-01→2031-12-01 | -1999 | Time-series z-score (vs own trailing history) of: IMF WEO consumer price inflati |
| IMF_WEO_Population | imf_weo | A | ? |  | 43 | 1980-12-01→2031-12-01 | -1999 | IMF WEO total population, in millions. |
| IMF_WEO_Population_CS | imf_weo | A | ? |  | 43 | 1980-12-01→2031-12-01 | -1999 | Cross-sectional z-score (across the 34-country panel) of: IMF WEO total populati |
| IMF_WEO_Population_TS | imf_weo | A | ? |  | 43 | 1984-12-01→2031-12-01 | -1999 | Time-series z-score (vs own trailing history) of: IMF WEO total population, in m |
| IMF_WEO_Unemployment | imf_weo | A | ↓ |  | 43 | 1980-12-01→2031-12-01 | -1999 | IMF WEO unemployment rate, in percent. |
| IMF_WEO_Unemployment_CS | imf_weo | A | ↓ |  | 43 | 1980-12-01→2031-12-01 | -1999 | Cross-sectional z-score (across the 34-country panel) of: IMF WEO unemployment r |
| IMF_WEO_Unemployment_TS | imf_weo | A | ↓ |  | 43 | 1984-12-01→2031-12-01 | -1999 | Time-series z-score (vs own trailing history) of: IMF WEO unemployment rate, in  |
| MS_CentralBank_SovDebt_Share | macrostructure_derived | Q | ? |  | 35 | 1997-12-01→2026-04-01 | 71 | Central bank claims on central government as a share of total public debt (trans |
| MS_Investor_Base_Fragility | macrostructure_derived | Q | ↓ |  | 40 | 2001-03-01→2025-12-01 | 192 | Transparent percentile composite of investor-base fragility (foreign ownership,  |
| MS_Policy_Backstop | macrostructure_derived | Q | ? |  | 43 | 2000-01-01→2026-06-01 | 10 | Composite of MS_Reserve_Adequacy and MS_Swap_Line_Access — total external liquid |
| MS_Reserve_Adequacy | macrostructure_derived | Q | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Blend of import-cover strength and inverse external-debt burden (import-cover co |
| MS_Swap_Line_Access | macrostructure_derived | Q | ? |  | 43 | 2000-01-01→2026-06-01 | 10 | Policy-support proxy from Federal Reserve standing/temporary USD swap line acces |
| NDGAIN_Readiness | ndgain | A | ? |  | 41 | 1995-12-01→2023-12-01 | 923 ⚠STALE | ND-GAIN readiness sub-score — economic, governance, and social capacity to deplo |
| NDGAIN_Readiness_CS | ndgain | A | ? |  | 41 | 1995-12-01→2023-12-01 | 923 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: ND-GAIN readiness sub- |
| NDGAIN_Readiness_TS | ndgain | A | ? |  | 41 | 1999-12-01→2023-12-01 | 923 ⚠STALE | Time-series z-score (vs own trailing history) of: ND-GAIN readiness sub-score —  |
| NDGAIN_Score | ndgain | A | ? |  | 41 | 1995-12-01→2023-12-01 | 923 ⚠STALE | Notre Dame Global Adaptation Index composite — readiness minus vulnerability to  |
| NDGAIN_Score_CS | ndgain | A | ? |  | 41 | 1995-12-01→2023-12-01 | 923 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Notre Dame Global Adap |
| NDGAIN_Score_TS | ndgain | A | ? |  | 41 | 1999-12-01→2023-12-01 | 923 ⚠STALE | Time-series z-score (vs own trailing history) of: Notre Dame Global Adaptation I |
| NDGAIN_Vulnerability | ndgain | A | ↓ |  | 41 | 1995-12-01→2023-12-01 | 923 ⚠STALE | ND-GAIN vulnerability sub-score — exposure and sensitivity to climate disruption |
| NDGAIN_Vulnerability_CS | ndgain | A | ↓ |  | 41 | 1995-12-01→2023-12-01 | 923 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: ND-GAIN vulnerability  |
| NDGAIN_Vulnerability_TS | ndgain | A | ↓ |  | 41 | 1999-12-01→2023-12-01 | 923 ⚠STALE | Time-series z-score (vs own trailing history) of: ND-GAIN vulnerability sub-scor |
| OECD_CLI | oecd | M | ? |  | 20 | 2000-01-01→2026-05-01 | 41 | OECD Composite Leading Indicator (amplitude-adjusted, 100 = trend). |
| OECD_CLI_CS | oecd | M | ? |  | 20 | 2000-01-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: OECD Composite Leading |
| OECD_CLI_TS | oecd | M | ? |  | 20 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: OECD Composite Leading Indicat |
| OECD_BCI | oecd_bci | M | ? |  | 27 | 2000-01-01→2026-05-01 | 41 | OECD Business Confidence Indicator (100 = long-term average). |
| OECD_BCI_CS | oecd_bci | M | ? |  | 27 | 2000-01-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: OECD Business Confiden |
| OECD_BCI_TS | oecd_bci | M | ? |  | 27 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: OECD Business Confidence Indic |
| OECD_CCI | oecd_cci | M | ? |  | 28 | 2000-01-01→2026-05-01 | 41 | OECD Consumer Confidence Indicator (100 = long-term average). |
| OECD_CCI_CS | oecd_cci | M | ? |  | 28 | 2000-01-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: OECD Consumer Confiden |
| OECD_CCI_TS | oecd_cci | M | ? |  | 28 | 2001-12-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: OECD Consumer Confidence Indic |
| MS_Household_Direct_Equity_Share | oecd_household_dashboard | A | ? |  | 28 | 2010-12-01→2025-12-01 | 192 | Share of household financial assets held directly in equities, in percent (OECD  |
| MS_Household_Direct_Equity_Share_CS | oecd_household_dashboard | A | ? |  | 28 | 2010-12-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Share of household fin |
| MS_Household_Direct_Equity_Share_TS | oecd_household_dashboard | A | ? |  | 28 | 2014-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Share of household financial a |
| MS_Insurance_Assets_GDP | oecd_institutional_investors | Q | ? |  | 28 | 2010-03-01→2025-12-01 | 192 | Insurance company assets as percent of GDP (OECD). |
| MS_Insurance_Assets_GDP_CS | oecd_institutional_investors | Q | ? |  | 28 | 2010-03-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Insurance company asse |
| MS_Insurance_Assets_GDP_TS | oecd_institutional_investors | Q | ? |  | 27 | 2011-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Insurance company assets as pe |
| MS_Pension_Assets_GDP | oecd_institutional_investors | Q | ? |  | 28 | 2010-03-01→2025-12-01 | 192 | Pension fund assets as percent of GDP (OECD). |
| MS_Pension_Assets_GDP_CS | oecd_institutional_investors | Q | ? |  | 28 | 2010-03-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Pension fund assets as |
| MS_Pension_Assets_GDP_TS | oecd_institutional_investors | Q | ? |  | 28 | 2011-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Pension fund assets as percent |
| OFAC_Sanctioned | ofac | M | ? |  | 34 | 2026-06-01→2026-06-01 | 10 | Binary flag — country is associated with an active OFAC sanctions program (SDN a |
| OFAC_Sanctions_Count | ofac | M | ? |  | 34 | 2026-06-01→2026-06-01 | 10 | Count of OFAC sanctions programs associated with the country (SDN association da |
| OFAC_Sanctions_Count_CS | ofac | M | ? |  | 34 | 2026-06-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Count of OFAC sanction |
| MS_US_Holder_Share_Pct | portfolio_ownership | A | ? |  | 34 | 1997-12-01→2024-12-01 | 557 ⚠STALE | Share of the country's portfolio securities held by US investors, in percent (IM |
| MS_US_Holder_Share_Pct_CS | portfolio_ownership | A | ? |  | 34 | 1997-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Share of the country's |
| MS_US_Holder_Share_Pct_TS | portfolio_ownership | A | ? |  | 31 | 2004-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Share of the country's portfol |
| MS_Public_Debt_Domestic_Creditors_Pct_GDP | qpsd | Q | ? |  | 28 | 1995-03-01→2025-12-01 | 192 | Public debt held by domestic creditors as percent of GDP (QPSD). |
| MS_Public_Debt_Domestic_Creditors_Pct_GDP_CS | qpsd | Q | ? |  | 28 | 1995-03-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Public debt held by do |
| MS_Public_Debt_Domestic_Creditors_Pct_GDP_TS | qpsd | Q | ? |  | 28 | 1996-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Public debt held by domestic c |
| MS_Public_Debt_Domestic_Currency_Pct_GDP | qpsd | Q | ? |  | 29 | 1995-03-01→2025-12-01 | 192 | Domestic-currency public debt as percent of GDP (QPSD). |
| MS_Public_Debt_Domestic_Currency_Pct_GDP_CS | qpsd | Q | ? |  | 29 | 1995-03-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Domestic-currency publ |
| MS_Public_Debt_Domestic_Currency_Pct_GDP_TS | qpsd | Q | ? |  | 29 | 1996-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Domestic-currency public debt  |
| MS_Public_Debt_External_Creditors_Pct_GDP | qpsd | Q | ? |  | 29 | 1995-03-01→2025-12-01 | 192 | Public debt held by external creditors as percent of GDP (QPSD). |
| MS_Public_Debt_External_Creditors_Pct_GDP_CS | qpsd | Q | ? |  | 29 | 1995-03-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Public debt held by ex |
| MS_Public_Debt_External_Creditors_Pct_GDP_TS | qpsd | Q | ? |  | 29 | 1996-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Public debt held by external c |
| MS_Public_Debt_Foreign_Currency_Pct_GDP | qpsd | Q | ? |  | 28 | 1995-03-01→2025-12-01 | 192 | Foreign-currency-denominated public debt as percent of GDP (QPSD). |
| MS_Public_Debt_Foreign_Currency_Pct_GDP_CS | qpsd | Q | ? |  | 28 | 1995-03-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Foreign-currency-denom |
| MS_Public_Debt_Foreign_Currency_Pct_GDP_TS | qpsd | Q | ? |  | 27 | 1996-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Foreign-currency-denominated p |
| MS_Public_Debt_Foreign_Held_Pct | qpsd | Q | ↓ |  | 29 | 1995-03-01→2025-12-01 | 192 | Share of public debt held by foreign investors, in percent (QPSD). |
| MS_Public_Debt_Foreign_Held_Pct_CS | qpsd | Q | ↓ |  | 29 | 1995-03-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Share of public debt h |
| MS_Public_Debt_Foreign_Held_Pct_TS | qpsd | Q | ↓ |  | 29 | 1996-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Share of public debt held by f |
| MS_Public_Debt_Local_Currency_Pct | qpsd | Q | ? |  | 29 | 1995-03-01→2025-12-01 | 192 | Share of public debt denominated in local currency, in percent (QPSD). |
| MS_Public_Debt_Local_Currency_Pct_CS | qpsd | Q | ? |  | 29 | 1995-03-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Share of public debt d |
| MS_Public_Debt_Local_Currency_Pct_TS | qpsd | Q | ? |  | 27 | 1996-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Share of public debt denominat |
| MS_Public_Debt_Short_Maturity_Pct | qpsd | Q | ? |  | 36 | 1995-03-01→2025-12-01 | 192 | Share of public debt with short residual maturity, in percent (QPSD). |
| MS_Public_Debt_Short_Maturity_Pct_CS | qpsd | Q | ? |  | 36 | 1995-03-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Share of public debt w |
| MS_Public_Debt_Short_Maturity_Pct_TS | qpsd | Q | ? |  | 35 | 1996-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Share of public debt with shor |
| MS_Public_Debt_Short_Term_Pct_GDP | qpsd | Q | ? |  | 36 | 1995-03-01→2025-12-01 | 192 | Short-term public debt as percent of GDP (QPSD). |
| MS_Public_Debt_Short_Term_Pct_GDP_CS | qpsd | Q | ? |  | 36 | 1995-03-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Short-term public debt |
| MS_Public_Debt_Short_Term_Pct_GDP_TS | qpsd | Q | ? |  | 35 | 1996-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Short-term public debt as perc |
| MS_Public_Debt_Total_Pct_GDP | qpsd | Q | ↓ |  | 38 | 1995-03-01→2025-12-01 | 192 | Total general government debt as percent of GDP (World Bank Quarterly Public Sec |
| MS_Public_Debt_Total_Pct_GDP_CS | qpsd | Q | ↓ |  | 38 | 1995-03-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Total general governme |
| MS_Public_Debt_Total_Pct_GDP_TS | qpsd | Q | ↓ |  | 38 | 1996-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Total general government debt  |
| 10Yr Bond 12_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: 12-period percent chan |
| 10Yr Bond 12_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: 12-period percent change in th |
| 10Yr Bond_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: 10-year government bon |
| 10Yr Bond_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: 10-year government bond yield, |
| 12-1MTR_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: 12-month total return  |
| 12-1MTR_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: 12-month total return minus th |
| 120MA Signal_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Country equity index p |
| 120MA Signal_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Country equity index price rel |
| 120MA_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: 120-period moving aver |
| 120MA_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: 120-period moving average of t |
| 12MRet | t2 | M | ↑ | RETURN | 34 | 2000-02-01→2026-06-01 | 10 | Trailing 12-month price return of the country equity index. |
| 12MTR_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Trailing 12-month tota |
| 12MTR_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Trailing 12-month total return |
| 1MRet | t2 | M | ↑ | RETURN | 34 | 2000-02-01→2026-06-01 | 10 |  |
| 1MTR_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Trailing 1-month total |
| 1MTR_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Trailing 1-month total return  |
| 20 Day Vol_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Realized volatility of |
| 20 Day Vol_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Realized volatility of daily i |
| 360 Day Vol_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Realized volatility of |
| 360 Day Vol_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Realized volatility of daily i |
| 3MRet | t2 | M | ↑ | RETURN | 34 | 2000-02-01→2026-06-01 | 10 | Trailing 3-month price return of the country equity index. |
| 3MTR_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Trailing 3-month total |
| 3MTR_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Trailing 3-month total return  |
| 6MRet | t2 | M | ↑ | RETURN | 34 | 2000-02-01→2026-06-01 | 10 | Trailing 6-month price return of the country equity index. |
| 9MRet | t2 | M | ↑ | RETURN | 34 | 2000-02-01→2026-06-01 | 10 | Trailing 9-month price return of the country equity index. |
| Advance Decline_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Net advancing minus de |
| Advance Decline_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Net advancing minus declining  |
| Agriculture 12_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: 12-period percent chan |
| Agriculture 12_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: 12-period percent change in th |
| Agriculture_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Global agriculture com |
| Agriculture_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Global agriculture commodity p |
| BEST EPS_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Bloomberg BEst consens |
| BEST EPS_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Bloomberg BEst consensus forwa |
| Best Cash Flow_CS | t2 | M | ↑ |  | 34 | 2005-05-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Bloomberg BEst consens |
| Best Cash Flow_TS | t2 | M | ↑ |  | 34 | 2005-05-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Bloomberg BEst consensus cash- |
| Best Div Yield_CS | t2 | M | ↑ |  | 34 | 2005-05-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Bloomberg BEst consens |
| Best Div Yield_TS | t2 | M | ↑ |  | 34 | 2005-05-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Bloomberg BEst consensus forwa |
| Best PBK_CS | t2 | M | ↑ |  | 34 | 2005-04-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Country index price di |
| Best PBK_TS | t2 | M | ↑ |  | 34 | 2005-04-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Country index price divided by |
| Best PE _CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Country index price di |
| Best PE _TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Country index price divided by |
| Best Price Sales_CS | t2 | M | ↑ |  | 34 | 2000-03-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Country index price di |
| Best Price Sales_TS | t2 | M | ↑ |  | 34 | 2000-03-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Country index price divided by |
| Best ROE_CS | t2 | M | ↑ |  | 34 | 2005-09-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Bloomberg BEst consens |
| Best ROE_TS | t2 | M | ↑ |  | 34 | 2005-09-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Bloomberg BEst consensus forwa |
| Bloom Country Risk_CS | t2 | M | ↑ |  | 34 | 2009-07-01→2025-10-01 | 253 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Bloomberg composite co |
| Bloom Country Risk_TS | t2 | M | ↑ |  | 34 | 2009-07-01→2025-10-01 | 253 ⚠STALE | Time-series z-score (vs own trailing history) of: Bloomberg composite country ri |
| Budget Def_CS | t2 | M | ↑ |  | 34 | 2001-01-01→2026-01-01 | 161 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: General government bud |
| Budget Def_TS | t2 | M | ↑ |  | 34 | 2001-01-01→2026-01-01 | 161 ⚠STALE | Time-series z-score (vs own trailing history) of: General government budget bala |
| Copper 12_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: 12-period percent chan |
| Copper 12_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: 12-period percent change in th |
| Copper_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Copper spot price in U |
| Copper_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Copper spot price in USD per m |
| Currency 12_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: 12-period percent chan |
| Currency 12_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: 12-period percent change in th |
| Currency Vol_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Realized volatility of |
| Currency Vol_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Realized volatility of the LCU |
| Currency_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Spot exchange rate in  |
| Currency_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Spot exchange rate in local cu |
| Current Account_CS | t2 | M | ↑ |  | 34 | 2000-04-01→2026-04-01 | 71 | Cross-sectional z-score (across the 34-country panel) of: Current account balanc |
| Current Account_TS | t2 | M | ↑ |  | 34 | 2000-04-01→2026-04-01 | 71 | Time-series z-score (vs own trailing history) of: Current account balance as a p |
| Debt to EV_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Aggregate debt divided |
| Debt to EV_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Aggregate debt divided by ente |
| Debt to GDP_CS | t2 | M | ↑ |  | 34 | 2001-01-01→2016-01-01 | 3814 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Government debt as a p |
| Debt to GDP_TS | t2 | M | ↑ |  | 34 | 2001-01-01→2016-01-01 | 3814 ⚠STALE | Time-series z-score (vs own trailing history) of: Government debt as a percent o |
| EV to EBITDA_CS | t2 | M | ↑ |  | 34 | 2005-07-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Aggregate enterprise v |
| EV to EBITDA_TS | t2 | M | ↑ |  | 34 | 2005-07-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Aggregate enterprise value div |
| Earnings Yield_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Trailing aggregate ear |
| Earnings Yield_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Trailing aggregate earnings di |
| GDP_CS | t2 | M | ↑ |  | 34 | 2001-01-01→2026-01-01 | 161 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Real GDP growth rate,  |
| GDP_TS | t2 | M | ↑ |  | 34 | 2001-01-01→2026-01-01 | 161 ⚠STALE | Time-series z-score (vs own trailing history) of: Real GDP growth rate, year ove |
| Gold 12_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: 12-period percent chan |
| Gold 12_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: 12-period percent change in th |
| Gold_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Gold spot price in USD |
| Gold_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Gold spot price in USD per tro |
| Inflation_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Consumer price inflati |
| Inflation_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Consumer price inflation, year |
| LT Growth_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Bloomberg consensus lo |
| LT Growth_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Bloomberg consensus long-term  |
| MCAP Adj_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Float/index-adjusted e |
| MCAP Adj_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Float/index-adjusted equity ma |
| MCAP_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Total equity market ca |
| MCAP_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Total equity market capitaliza |
| Mcap Weights_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Country share of total |
| Mcap Weights_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Country share of total market  |
| Oil 12_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: 12-period percent chan |
| Oil 12_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: 12-period percent change in th |
| Oil_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Crude oil spot price i |
| Oil_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Crude oil spot price in USD pe |
| Operating Margin_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Aggregate operating in |
| Operating Margin_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Aggregate operating income as  |
| P2P_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Bounded price-position |
| P2P_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Bounded price-position measure |
| PX_LAST_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Country equity index p |
| PX_LAST_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Country equity index price lev |
| Positive PE _CS | t2 | M | ↑ |  | 34 | 2005-05-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Country index P/E comp |
| Positive PE _TS | t2 | M | ↑ |  | 34 | 2005-05-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Country index P/E computed res |
| REER_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-05-01 | 41 | Cross-sectional z-score (across the 34-country panel) of: Real effective exchang |
| REER_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-05-01 | 41 | Time-series z-score (vs own trailing history) of: Real effective exchange rate i |
| RSI14_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: 14-period Relative Str |
| RSI14_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: 14-period Relative Strength In |
| Shiller PE_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Cyclically-adjusted pr |
| Shiller PE_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Cyclically-adjusted price-to-e |
| Tot Return Index _CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Country equity total r |
| Tot Return Index _TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Country equity total return in |
| Trailing EPS 36_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Change in trailing 12- |
| Trailing EPS 36_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Change in trailing 12-month EP |
| Trailing EPS_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Trailing 12-month aggr |
| Trailing EPS_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Trailing 12-month aggregate ea |
| Trailing PE_CS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Cross-sectional z-score (across the 34-country panel) of: Country index price di |
| Trailing PE_TS | t2 | M | ↑ |  | 34 | 2000-02-01→2026-06-01 | 10 | Time-series z-score (vs own trailing history) of: Country index price divided by |
| 10Yr Bond | t2_raw | M | ? |  | 33 | 2000-02-01→2026-06-01 | 10 | 10-year government bond yield, in percent. |
| 10Yr Bond 12 | t2_raw | M | ↓ |  | 33 | 2001-02-01→2026-06-01 | 10 | 12-period percent change in the 10-year government bond yield (months on the mon |
| 12-1MTR | t2_raw | M | ? |  | 34 | 2001-02-01→2026-06-01 | 10 | 12-month total return minus the most recent 1-month total return (momentum exclu |
| 120MA | t2_raw | M | ? |  | 34 | 2000-02-01→2026-06-01 | 10 | 120-period moving average of the country equity index price (months on the month |
| 120MA Signal | t2_raw | M | ↓ |  | 34 | 2000-02-01→2026-06-01 | 10 | Country equity index price relative to its 120-period moving average (continuous |
| 12MTR | t2_raw | M | ? |  | 34 | 2001-02-01→2026-06-01 | 10 | Trailing 12-month total return of the country equity index. |
| 1MTR | t2_raw | M | ↓ |  | 34 | 2000-03-01→2026-06-01 | 10 | Trailing 1-month total return (dividends reinvested) of the country equity index |
| 20 Day Vol | t2_raw | M | ? |  | 34 | 2000-02-01→2026-06-01 | 10 | Realized volatility of daily index returns over the trailing 20 trading days. |
| 360 Day Vol | t2_raw | M | ? |  | 34 | 2000-02-01→2026-06-01 | 10 | Realized volatility of daily index returns over the trailing 360 trading days. |
| 3MTR | t2_raw | M | ↓ |  | 34 | 2000-05-01→2026-06-01 | 10 | Trailing 3-month total return of the country equity index. |
| Advance Decline | t2_raw | M | ↓ |  | 34 | 2000-02-01→2026-06-01 | 10 | Net advancing minus declining issues in the country market (market breadth count |
| Agriculture | t2_raw | M | ? |  | 34 | 2000-02-01→2026-06-01 | 10 | Global agriculture commodity price index level (broadcast to all countries). |
| Agriculture 12 | t2_raw | M | ? |  | 34 | 2001-02-01→2026-06-01 | 10 | 12-period percent change in the agriculture commodity index. |
| BEST EPS | t2_raw | M | ? |  | 34 | 2000-02-01→2026-06-01 | 10 | Bloomberg BEst consensus forward earnings per share for the country index (index |
| Best Cash Flow | t2_raw | M | ↓ |  | 34 | 2005-05-01→2026-06-01 | 10 | Bloomberg BEst consensus cash-flow-based valuation measure for the country index |
| Best Div Yield | t2_raw | M | ? |  | 34 | 2005-05-01→2026-06-01 | 10 | Bloomberg BEst consensus forward dividend yield for the country index, in percen |
| Best PBK | t2_raw | M | ↓ |  | 34 | 2005-04-01→2026-06-01 | 10 | Country index price divided by Bloomberg BEst consensus book value per share. |
| Best PE | t2_raw | M | ↓ |  | 34 | 2000-02-01→2026-06-01 | 10 | Country index price divided by Bloomberg BEst consensus forward earnings per sha |
| Best Price Sales | t2_raw | M | ↓ |  | 34 | 2000-03-01→2026-06-01 | 10 | Country index price divided by Bloomberg BEst consensus sales per share. |
| Best ROE | t2_raw | M | ? |  | 34 | 2005-09-01→2026-06-01 | 10 | Bloomberg BEst consensus forward return on equity for the country index, in perc |
| Bloom Country Risk | t2_raw | M | ↓ |  | 34 | 2009-07-01→2025-10-01 | 253 ⚠STALE | Bloomberg composite country risk score (observed range 7-99; scale orientation u |
| Budget Def | t2_raw | M | ? |  | 32 | 2001-01-01→2026-01-01 | 161 ⚠STALE | General government budget balance as a percent of GDP (negative = deficit). |
| Copper | t2_raw | M | ? |  | 34 | 2000-02-01→2026-06-01 | 10 | Copper spot price in USD per metric ton (global series broadcast to all countrie |
| Copper 12 | t2_raw | M | ? |  | 34 | 2001-02-01→2026-06-01 | 10 | 12-period percent change in the copper price. |
| Currency | t2_raw | M | ? |  | 34 | 2000-02-01→2026-06-01 | 10 | Spot exchange rate in local currency units per USD (U.S. = 1.0). |
| Currency 12 | t2_raw | M | ? |  | 34 | 2001-02-01→2026-06-01 | 10 | 12-period percent change in the LCU/USD exchange rate (positive = depreciation v |
| Currency Vol | t2_raw | M | ? |  | 34 | 2000-02-01→2026-06-01 | 10 | Realized volatility of the LCU/USD exchange rate (0 for the USD-based sleeves). |
| Current Account | t2_raw | M | ? |  | 33 | 2000-04-01→2026-04-01 | 71 | Current account balance as a percent of GDP. |
| Debt to EV | t2_raw | M | ? |  | 34 | 2000-02-01→2026-06-01 | 10 | Aggregate debt divided by enterprise value for the country index. |
| Debt to GDP | t2_raw | M | ↓ |  | 34 | 2001-01-01→2016-01-01 | 3814 ⚠STALE | Government debt as a percent of GDP. |
| EV to EBITDA | t2_raw | M | ↓ |  | 34 | 2005-07-01→2026-06-01 | 10 | Aggregate enterprise value divided by EBITDA for the country index. |
| Earnings Yield | t2_raw | M | ? |  | 34 | 2000-02-01→2026-06-01 | 10 | Trailing aggregate earnings divided by price for the country index (inverse of P |
| GDP | t2_raw | M | ? |  | 34 | 2001-01-01→2026-01-01 | 161 ⚠STALE | Real GDP growth rate, year over year, in percent. |
| Gold | t2_raw | M | ? |  | 34 | 2000-02-01→2026-06-01 | 10 | Gold spot price in USD per troy ounce (global series broadcast to all countries) |
| Gold 12 | t2_raw | M | ? |  | 34 | 2001-02-01→2026-06-01 | 10 | 12-period percent change in the gold price (verified against recomputed 12-month |
| Inflation | t2_raw | M | ? |  | 34 | 2000-02-01→2026-06-01 | 10 | Consumer price inflation, year over year, in percent. |
| LT Growth | t2_raw | M | ? |  | 34 | 2000-02-01→2026-06-01 | 10 | Bloomberg consensus long-term EPS growth estimate for the country index, in perc |
| MCAP | t2_raw | M | ? |  | 34 | 2000-02-01→2026-06-01 | 10 | Total equity market capitalization of the country index, in USD millions. |
| MCAP Adj | t2_raw | M | ? |  | 34 | 2000-02-01→2026-06-01 | 10 | Float/index-adjusted equity market capitalization of the country index, in USD m |
| Mcap Weights | t2_raw | M | ↓ |  | 34 | 2000-02-01→2026-06-01 | 10 | Country share of total market capitalization across the 34-country universe (wei |
| Oil | t2_raw | M | ? |  | 34 | 2000-02-01→2026-06-01 | 10 | Crude oil spot price in USD per barrel (global series broadcast to all countries |
| Oil 12 | t2_raw | M | ? |  | 34 | 2001-02-01→2026-06-01 | 10 | 12-period percent change in the crude oil price. |
| Operating Margin | t2_raw | M | ? |  | 34 | 2000-02-01→2026-06-01 | 10 | Aggregate operating income as a percent of sales for the country index. |
| P2P | t2_raw | M | ? |  | 34 | 2000-02-01→2026-06-01 | 10 | Bounded price-position measure related to the index's standing versus its traili |
| PX_LAST | t2_raw | M | ? |  | 34 | 2000-02-01→2026-06-01 | 10 | Country equity index price level in local currency (Bloomberg PX_LAST). |
| Positive PE | t2_raw | M | ↓ |  | 34 | 2005-05-01→2026-06-01 | 10 | Country index P/E computed restricting to positive-earnings constituents (avoids |
| REER | t2_raw | M | ↓ |  | 34 | 2000-02-01→2026-05-01 | 41 | Real effective exchange rate index (trade-weighted, inflation-adjusted; ~100 = b |
| RSI14 | t2_raw | M | ↓ |  | 34 | 2000-02-01→2026-06-01 | 10 | 14-period Relative Strength Index of the country equity index (bounded 0-100). |
| Shiller PE | t2_raw | M | ↓ |  | 27 | 2000-02-01→2026-06-01 | 10 | Cyclically-adjusted price-to-earnings ratio — price divided by a multi-year aver |
| Tot Return Index | t2_raw | M | ? |  | 34 | 2000-02-01→2026-06-01 | 10 | Country equity total return index level (price plus reinvested dividends) in loc |
| Trailing EPS | t2_raw | M | ? |  | 34 | 2000-02-01→2026-06-01 | 10 | Trailing 12-month aggregate earnings per share for the country index (local curr |
| Trailing EPS 36 | t2_raw | M | ? |  | 34 | 2003-02-01→2026-06-01 | 10 | Change in trailing 12-month EPS over the trailing 36 periods (months on the mont |
| Trailing PE | t2_raw | M | ↓ |  | 34 | 2000-02-01→2026-06-01 | 10 | Country index price divided by trailing 12-month aggregate earnings per share. |
| UNDP_GDI | undp_hdi | A | ? |  | 42 | 1990-12-01→2023-12-01 | 923 ⚠STALE | Gender Development Index — ratio of female to male HDI (UNDP). |
| UNDP_GDI_CS | undp_hdi | A | ? |  | 42 | 1990-12-01→2023-12-01 | 923 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Gender Development Ind |
| UNDP_GDI_TS | undp_hdi | A | ? |  | 42 | 1994-12-01→2023-12-01 | 923 ⚠STALE | Time-series z-score (vs own trailing history) of: Gender Development Index — rat |
| UNDP_GII | undp_hdi | A | ↓ |  | 41 | 1990-12-01→2023-12-01 | 923 ⚠STALE | Gender Inequality Index (0 = equality, 1 = maximum inequality; UNDP). |
| UNDP_GII_CS | undp_hdi | A | ↓ |  | 41 | 1990-12-01→2023-12-01 | 923 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Gender Inequality Inde |
| UNDP_GII_TS | undp_hdi | A | ↓ |  | 41 | 1994-12-01→2023-12-01 | 923 ⚠STALE | Time-series z-score (vs own trailing history) of: Gender Inequality Index (0 = e |
| UNDP_HDI | undp_hdi | A | ? |  | 42 | 1990-12-01→2023-12-01 | 923 ⚠STALE | Human Development Index — composite of life expectancy, education, and income (0 |
| UNDP_HDI_CS | undp_hdi | A | ? |  | 42 | 1990-12-01→2023-12-01 | 923 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Human Development Inde |
| UNDP_HDI_TS | undp_hdi | A | ? |  | 42 | 1994-12-01→2023-12-01 | 923 ⚠STALE | Time-series z-score (vs own trailing history) of: Human Development Index — comp |
| UNDP_IHDI | undp_hdi | A | ? |  | 41 | 2010-12-01→2023-12-01 | 923 ⚠STALE | Inequality-adjusted Human Development Index (0-1 scale). |
| UNDP_IHDI_CS | undp_hdi | A | ? |  | 41 | 2010-12-01→2023-12-01 | 923 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Inequality-adjusted Hu |
| UNDP_IHDI_TS | undp_hdi | A | ? |  | 41 | 2014-12-01→2023-12-01 | 923 ⚠STALE | Time-series z-score (vs own trailing history) of: Inequality-adjusted Human Deve |
| WB_CO2_Per_Capita | worldbank | A | ↓ |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | CO2 emissions per capita, in metric tons (WDI). |
| WB_CO2_Per_Capita_CS | worldbank | A | ↓ |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: CO2 emissions per capi |
| WB_CO2_Per_Capita_TS | worldbank | A | ↓ |  | 42 | 2004-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: CO2 emissions per capita, in m |
| WB_Control_Corruption | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Worldwide Governance Indicators control-of-corruption score (approx -2.5 to +2.5 |
| WB_Control_Corruption_CS | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Worldwide Governance I |
| WB_Control_Corruption_TS | worldbank | A | ? |  | 42 | 2005-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Worldwide Governance Indicator |
| WB_Current_Account_GDP | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Current account balance as percent of GDP (WDI). |
| WB_Current_Account_GDP_CS | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Current account balanc |
| WB_Current_Account_GDP_TS | worldbank | A | ? |  | 42 | 2004-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Current account balance as per |
| WB_Domestic_Credit_GDP | worldbank | A | ↓ |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Domestic credit to private sector as percent of GDP (WDI). |
| WB_Domestic_Credit_GDP_CS | worldbank | A | ↓ |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Domestic credit to pri |
| WB_Domestic_Credit_GDP_TS | worldbank | A | ↓ |  | 42 | 2004-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Domestic credit to private sec |
| WB_External_Debt_GNI | worldbank | A | ? |  | 12 | 2000-12-01→2024-12-01 | 557 ⚠STALE | External debt stock as percent of gross national income (WDI). |
| WB_External_Debt_GNI_CS | worldbank | A | ? |  | 12 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: External debt stock as |
| WB_External_Debt_GNI_TS | worldbank | A | ? |  | 12 | 2004-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: External debt stock as percent |
| WB_FDI_Inflows_GDP | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Foreign direct investment net inflows as percent of GDP (WDI). |
| WB_FDI_Inflows_GDP_CS | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Foreign direct investm |
| WB_FDI_Inflows_GDP_TS | worldbank | A | ? |  | 42 | 2004-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Foreign direct investment net  |
| WB_FX_Reserves | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Total foreign exchange reserves including gold, in USD (WDI). |
| WB_FX_Reserves_CS | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Total foreign exchange |
| WB_FX_Reserves_TS | worldbank | A | ? |  | 42 | 2004-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Total foreign exchange reserve |
| WB_Female_LFP | worldbank | A | ? |  | 42 | 2000-12-01→2025-12-01 | 192 | Female labor force participation rate (WDI), in percent. |
| WB_Female_LFP_CS | worldbank | A | ? |  | 42 | 2000-12-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Female labor force par |
| WB_Female_LFP_TS | worldbank | A | ? |  | 42 | 2004-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Female labor force participati |
| WB_Female_Labor_Share | worldbank | A | ? |  | 42 | 2000-12-01→2025-12-01 | 192 | Female share of the total labor force (WDI), in percent. |
| WB_Female_Labor_Share_CS | worldbank | A | ? |  | 42 | 2000-12-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Female share of the to |
| WB_Female_Labor_Share_TS | worldbank | A | ? |  | 42 | 2004-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Female share of the total labo |
| WB_GDP_Growth_Real | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Real GDP growth from World Bank WDI, year over year, in percent. |
| WB_GDP_Growth_Real_CS | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Real GDP growth from W |
| WB_GDP_Growth_Real_TS | worldbank | A | ? |  | 42 | 2004-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Real GDP growth from World Ban |
| WB_Govt_Debt_GDP | worldbank | A | ↓ |  | 22 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Central government debt as percent of GDP (WDI). |
| WB_Govt_Debt_GDP_CS | worldbank | A | ↓ |  | 22 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Central government deb |
| WB_Govt_Debt_GDP_TS | worldbank | A | ↓ |  | 20 | 2004-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Central government debt as per |
| WB_Govt_Effectiveness | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | WGI government effectiveness score (approx -2.5 to +2.5). |
| WB_Govt_Effectiveness_CS | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: WGI government effecti |
| WB_Govt_Effectiveness_TS | worldbank | A | ? |  | 42 | 2005-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: WGI government effectiveness s |
| WB_Import_Cover_Months | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | FX reserves expressed as months of import cover (WDI). |
| WB_Import_Cover_Months_CS | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: FX reserves expressed  |
| WB_Import_Cover_Months_TS | worldbank | A | ? |  | 42 | 2004-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: FX reserves expressed as month |
| WB_Inflation_CPI | worldbank | A | ↓ |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | CPI inflation from World Bank WDI, in percent. |
| WB_Inflation_CPI_CS | worldbank | A | ↓ |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: CPI inflation from Wor |
| WB_Inflation_CPI_TS | worldbank | A | ↓ |  | 42 | 2004-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: CPI inflation from World Bank  |
| WB_Labor_Force | worldbank | A | ? |  | 42 | 2000-12-01→2025-12-01 | 192 | Total labor force (WDI). |
| WB_Labor_Force_CS | worldbank | A | ? |  | 42 | 2000-12-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Total labor force (WDI |
| WB_Labor_Force_TS | worldbank | A | ? |  | 42 | 2004-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Total labor force (WDI). |
| WB_Market_Cap_GDP | worldbank | A | ↓ |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Stock market capitalization as percent of GDP (WDI). |
| WB_Market_Cap_GDP_CS | worldbank | A | ↓ |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Stock market capitaliz |
| WB_Market_Cap_GDP_TS | worldbank | A | ↓ |  | 41 | 2004-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Stock market capitalization as |
| WB_OldAge_Dependency | worldbank | A | ↓ |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Old-age dependency ratio — population 65+ as percent of working-age population ( |
| WB_OldAge_Dependency_CS | worldbank | A | ↓ |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Old-age dependency rat |
| WB_OldAge_Dependency_TS | worldbank | A | ↓ |  | 42 | 2004-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Old-age dependency ratio — pop |
| WB_Political_Stability | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | WGI political stability and absence of violence score (approx -2.5 to +2.5). |
| WB_Political_Stability_CS | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: WGI political stabilit |
| WB_Political_Stability_TS | worldbank | A | ? |  | 42 | 2005-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: WGI political stability and ab |
| WB_Population | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Total population (WDI). |
| WB_Population_CS | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Total population (WDI) |
| WB_Population_Growth | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Population growth rate (WDI), in percent. |
| WB_Population_Growth_CS | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Population growth rate |
| WB_Population_Growth_TS | worldbank | A | ? |  | 42 | 2004-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Population growth rate (WDI),  |
| WB_Population_TS | worldbank | A | ? |  | 42 | 2004-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Total population (WDI). |
| WB_Regulatory_Quality | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | WGI regulatory quality score (approx -2.5 to +2.5). |
| WB_Regulatory_Quality_CS | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: WGI regulatory quality |
| WB_Regulatory_Quality_TS | worldbank | A | ? |  | 42 | 2005-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: WGI regulatory quality score ( |
| WB_Renewable_Energy_Share | worldbank | A | ? |  | 42 | 2000-12-01→2021-12-01 | 1653 ⚠STALE | Renewable energy as percent of total final energy consumption (WDI). |
| WB_Renewable_Energy_Share_CS | worldbank | A | ? |  | 42 | 2000-12-01→2021-12-01 | 1653 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Renewable energy as pe |
| WB_Renewable_Energy_Share_TS | worldbank | A | ? |  | 42 | 2004-12-01→2021-12-01 | 1653 ⚠STALE | Time-series z-score (vs own trailing history) of: Renewable energy as percent of |
| WB_Rule_of_Law | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | WGI rule of law score (approx -2.5 to +2.5). |
| WB_Rule_of_Law_CS | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: WGI rule of law score  |
| WB_Rule_of_Law_TS | worldbank | A | ? |  | 42 | 2005-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: WGI rule of law score (approx  |
| WB_Trade_Openness | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Exports plus imports as percent of GDP (WDI). |
| WB_Trade_Openness_CS | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Exports plus imports a |
| WB_Trade_Openness_TS | worldbank | A | ? |  | 42 | 2004-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: Exports plus imports as percen |
| WB_Unemployment | worldbank | A | ↓ |  | 42 | 2000-12-01→2025-12-01 | 192 | Unemployment rate (ILO-modeled estimate, WDI), in percent. |
| WB_Unemployment_CS | worldbank | A | ↓ |  | 42 | 2000-12-01→2025-12-01 | 192 | Cross-sectional z-score (across the 34-country panel) of: Unemployment rate (ILO |
| WB_Unemployment_TS | worldbank | A | ↓ |  | 42 | 2004-12-01→2025-12-01 | 192 | Time-series z-score (vs own trailing history) of: Unemployment rate (ILO-modeled |
| WB_Voice_Accountability | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | WGI voice and accountability score (approx -2.5 to +2.5). |
| WB_Voice_Accountability_CS | worldbank | A | ? |  | 42 | 2000-12-01→2024-12-01 | 557 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: WGI voice and accounta |
| WB_Voice_Accountability_TS | worldbank | A | ? |  | 42 | 2005-12-01→2024-12-01 | 557 ⚠STALE | Time-series z-score (vs own trailing history) of: WGI voice and accountability s |

## t2_factors_daily  (111 variables)

| variable | source | freq | sign | role | countries | range | fresh(d) | definition |
|---|---|---|---|---|---|---|---|---|
| 10Yr Bond 120_CS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: 120-period percent cha |
| 10Yr Bond 120_TS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: 120-period percent change in t |
| 10Yr Bond_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: 10-year government bon |
| 10Yr Bond_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: 10-year government bond yield, |
| 120-5DTR_CS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: 120-trading-day total  |
| 120-5DTR_TS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: 120-trading-day total return m |
| 120DRet | t2_daily | D | ↑ | RETURN | 34 | 2000-01-01→2026-06-11 | 0 | Trailing 120-trading-day (~6 month) price return of the country equity index. |
| 120DTR_CS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Trailing 120-trading-d |
| 120DTR_TS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Trailing 120-trading-day total |
| 120MA Signal_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Country equity index p |
| 120MA Signal_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Country equity index price rel |
| 120MA_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: 120-period moving aver |
| 120MA_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: 120-period moving average of t |
| 1DRet | t2_daily | D | ↑ | RETURN | 34 | 2000-01-01→2026-06-11 | 0 | 1-day price return of the country equity index. |
| 1DTR_CS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: 1-trading-day total re |
| 1DTR_TS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: 1-trading-day total return of  |
| 20 Day Vol_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Realized volatility of |
| 20 Day Vol_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Realized volatility of daily i |
| 20DRet | t2_daily | D | ↑ | RETURN | 34 | 2000-01-01→2026-06-11 | 0 | Trailing 20-trading-day (~1 month) price return of the country equity index. |
| 20DTR_CS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Trailing 20-trading-da |
| 20DTR_TS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Trailing 20-trading-day total  |
| 360 Day Vol_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Realized volatility of |
| 360 Day Vol_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Realized volatility of daily i |
| 5DRet | t2_daily | D | ↑ | RETURN | 34 | 2000-01-01→2026-06-11 | 0 | Trailing 5-trading-day price return of the country equity index. |
| 5DTR_CS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Trailing 5-trading-day |
| 5DTR_TS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Trailing 5-trading-day total r |
| 60DRet | t2_daily | D | ↑ | RETURN | 34 | 2000-01-01→2026-06-11 | 0 | Trailing 60-trading-day (~3 month) price return of the country equity index. |
| Advance Decline_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Net advancing minus de |
| Advance Decline_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Net advancing minus declining  |
| Agriculture 120_CS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: 120-period percent cha |
| Agriculture 120_TS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: 120-period percent change in t |
| Agriculture_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Global agriculture com |
| Agriculture_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Global agriculture commodity p |
| BEST EPS_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Bloomberg BEst consens |
| BEST EPS_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Bloomberg BEst consensus forwa |
| Best Cash Flow_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Bloomberg BEst consens |
| Best Cash Flow_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Bloomberg BEst consensus cash- |
| Best Div Yield_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Bloomberg BEst consens |
| Best Div Yield_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Bloomberg BEst consensus forwa |
| Best EPS 252_CS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Change in Bloomberg BE |
| Best EPS 252_TS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Change in Bloomberg BEst conse |
| Best PBK_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Country index price di |
| Best PBK_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Country index price divided by |
| Best PE _CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Country index price di |
| Best PE _TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Country index price divided by |
| Best Price Sales_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Country index price di |
| Best Price Sales_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Country index price divided by |
| Best ROE_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Bloomberg BEst consens |
| Best ROE_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Bloomberg BEst consensus forwa |
| Bloom Country Risk_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Bloomberg composite co |
| Bloom Country Risk_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Bloomberg composite country ri |
| Copper 120_CS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: 120-period percent cha |
| Copper 120_TS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: 120-period percent change in t |
| Copper_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Copper spot price in U |
| Copper_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Copper spot price in USD per m |
| Currency 120_CS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: 120-period percent cha |
| Currency 120_TS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: 120-period percent change in t |
| Currency Vol_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Realized volatility of |
| Currency Vol_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Realized volatility of the LCU |
| Currency_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Spot exchange rate in  |
| Currency_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Spot exchange rate in local cu |
| Current Account_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Current account balanc |
| Current Account_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Current account balance as a p |
| Debt to EV_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Aggregate debt divided |
| Debt to EV_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Aggregate debt divided by ente |
| EV to EBITDA_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Aggregate enterprise v |
| EV to EBITDA_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Aggregate enterprise value div |
| Earnings Yield_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Trailing aggregate ear |
| Earnings Yield_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Trailing aggregate earnings di |
| GDP_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Real GDP growth rate,  |
| GDP_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Real GDP growth rate, year ove |
| Gold 120_CS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: 120-period percent cha |
| Gold 120_TS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: 120-period percent change in t |
| Gold_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Gold spot price in USD |
| Gold_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Gold spot price in USD per tro |
| Inflation_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Consumer price inflati |
| Inflation_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Consumer price inflation, year |
| LT Growth_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Bloomberg consensus lo |
| LT Growth_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Bloomberg consensus long-term  |
| MCAP Adj_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2001-02-02 | 9260 ⚠STALE | Cross-sectional z-score (across the 34-country panel) of: Float/index-adjusted e |
| MCAP Adj_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2001-02-02 | 9260 ⚠STALE | Time-series z-score (vs own trailing history) of: Float/index-adjusted equity ma |
| MCAP_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Total equity market ca |
| MCAP_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Total equity market capitaliza |
| Mcap Weights_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Country share of total |
| Mcap Weights_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Country share of total market  |
| Oil 120_CS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: 120-period percent cha |
| Oil 120_TS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: 120-period percent change in t |
| Oil_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Crude oil spot price i |
| Oil_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Crude oil spot price in USD pe |
| Operating Margin_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Aggregate operating in |
| Operating Margin_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Aggregate operating income as  |
| P2P_CS | t2_daily | M | ↑ |  | 34 | 2000-01-04→2026-06-03 | 8 | Cross-sectional z-score (across the 34-country panel) of: Bounded price-position |
| P2P_TS | t2_daily | M | ↑ |  | 34 | 2000-01-04→2026-06-03 | 8 | Time-series z-score (vs own trailing history) of: Bounded price-position measure |
| PX_LAST_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Country equity index p |
| PX_LAST_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Country equity index price lev |
| Positive PE _CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Country index P/E comp |
| Positive PE _TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Country index P/E computed res |
| REER_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Real effective exchang |
| REER_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Real effective exchange rate i |
| RSI14_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: 14-period Relative Str |
| RSI14_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: 14-period Relative Strength In |
| Shiller PE_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Cyclically-adjusted pr |
| Shiller PE_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Cyclically-adjusted price-to-e |
| Tot Return Index _CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Country equity total r |
| Tot Return Index _TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Country equity total return in |
| Trailing EPS 252_CS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Change in trailing 12- |
| Trailing EPS 252_TS | t2_daily | D | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Change in trailing 12-month EP |
| Trailing EPS_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Trailing 12-month aggr |
| Trailing EPS_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Trailing 12-month aggregate ea |
| Trailing PE_CS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cross-sectional z-score (across the 34-country panel) of: Country index price di |
| Trailing PE_TS | t2_daily | M | ↑ |  | 34 | 2000-01-01→2026-06-11 | 0 | Time-series z-score (vs own trailing history) of: Country index price divided by |

## t2_levels_daily  (48 variables)

| variable | source | freq | sign | role | countries | range | fresh(d) | definition |
|---|---|---|---|---|---|---|---|---|
| 10Yr Bond | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | 10-year government bond yield, in percent. |
| 10Yr Bond 120 | t2_levels | D | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | 120-period percent change in the 10-year government bond yield. |
| 120MA | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | 120-period moving average of the country equity index price (months on the month |
| 120MA Signal | t2_levels | M | ↓ |  | 34 | 2000-01-01→2026-06-11 | 0 | Country equity index price relative to its 120-period moving average (continuous |
| 20 Day Vol | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Realized volatility of daily index returns over the trailing 20 trading days. |
| 360 Day Vol | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Realized volatility of daily index returns over the trailing 360 trading days. |
| Advance Decline | t2_levels | M | ↓ |  | 34 | 2000-01-01→2026-06-11 | 0 | Net advancing minus declining issues in the country market (market breadth count |
| Agriculture | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Global agriculture commodity price index level (broadcast to all countries). |
| Agriculture 120 | t2_levels | D | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | 120-period percent change in the agriculture commodity index. |
| BEST EPS | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Bloomberg BEst consensus forward earnings per share for the country index (index |
| Best Cash Flow | t2_levels | M | ↓ |  | 34 | 2000-01-01→2026-06-11 | 0 | Bloomberg BEst consensus cash-flow-based valuation measure for the country index |
| Best Div Yield | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Bloomberg BEst consensus forward dividend yield for the country index, in percen |
| Best EPS 252 | t2_levels | D | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Change in Bloomberg BEst consensus forward EPS over the trailing 252 trading day |
| Best PBK | t2_levels | M | ↓ |  | 34 | 2000-01-01→2026-06-11 | 0 | Country index price divided by Bloomberg BEst consensus book value per share. |
| Best PE | t2_levels | M | ↓ |  | 34 | 2000-01-01→2026-06-11 | 0 | Country index price divided by Bloomberg BEst consensus forward earnings per sha |
| Best Price Sales | t2_levels | M | ↓ |  | 34 | 2000-01-01→2026-06-11 | 0 | Country index price divided by Bloomberg BEst consensus sales per share. |
| Best ROE | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Bloomberg BEst consensus forward return on equity for the country index, in perc |
| Bloom Country Risk | t2_levels | M | ↓ |  | 34 | 2000-01-01→2026-06-11 | 0 | Bloomberg composite country risk score (observed range 7-99; scale orientation u |
| Copper | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Copper spot price in USD per metric ton (global series broadcast to all countrie |
| Copper 120 | t2_levels | D | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | 120-period percent change in the copper price. |
| Currency | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Spot exchange rate in local currency units per USD (U.S. = 1.0). |
| Currency 120 | t2_levels | D | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | 120-period percent change in the LCU/USD exchange rate (positive = depreciation  |
| Currency Vol | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Realized volatility of the LCU/USD exchange rate (0 for the USD-based sleeves). |
| Current Account | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Current account balance as a percent of GDP. |
| Debt to EV | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Aggregate debt divided by enterprise value for the country index. |
| EV to EBITDA | t2_levels | M | ↓ |  | 34 | 2000-01-01→2026-06-11 | 0 | Aggregate enterprise value divided by EBITDA for the country index. |
| Earnings Yield | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Trailing aggregate earnings divided by price for the country index (inverse of P |
| GDP | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Real GDP growth rate, year over year, in percent. |
| Gold | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Gold spot price in USD per troy ounce (global series broadcast to all countries) |
| Gold 120 | t2_levels | D | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | 120-period percent change in the gold price (verified on the daily surface, corr |
| Inflation | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Consumer price inflation, year over year, in percent. |
| LT Growth | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Bloomberg consensus long-term EPS growth estimate for the country index, in perc |
| MCAP | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Total equity market capitalization of the country index, in USD millions. |
| MCAP Adj | t2_levels | M | ? |  | 34 | 2000-01-01→2001-02-02 | 9260 ⚠STALE | Float/index-adjusted equity market capitalization of the country index, in USD m |
| Mcap Weights | t2_levels | M | ↓ |  | 34 | 2000-01-01→2026-06-11 | 0 | Country share of total market capitalization across the 34-country universe (wei |
| Oil | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Crude oil spot price in USD per barrel (global series broadcast to all countries |
| Oil 120 | t2_levels | D | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | 120-period percent change in the crude oil price. |
| Operating Margin | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Aggregate operating income as a percent of sales for the country index. |
| P2P | t2_levels | M | ? |  | 34 | 2000-01-04→2026-06-03 | 8 | Bounded price-position measure related to the index's standing versus its traili |
| PX_LAST | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Country equity index price level in local currency (Bloomberg PX_LAST). |
| Positive PE | t2_levels | M | ↓ |  | 34 | 2000-01-01→2026-06-11 | 0 | Country index P/E computed restricting to positive-earnings constituents (avoids |
| REER | t2_levels | M | ↓ |  | 34 | 2000-01-01→2026-06-11 | 0 | Real effective exchange rate index (trade-weighted, inflation-adjusted; ~100 = b |
| RSI14 | t2_levels | M | ↓ |  | 34 | 2000-01-01→2026-06-11 | 0 | 14-period Relative Strength Index of the country equity index (bounded 0-100). |
| Shiller PE | t2_levels | M | ↓ |  | 34 | 2000-01-01→2026-06-11 | 0 | Cyclically-adjusted price-to-earnings ratio — price divided by a multi-year aver |
| Tot Return Index | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Country equity total return index level (price plus reinvested dividends) in loc |
| Trailing EPS | t2_levels | M | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Trailing 12-month aggregate earnings per share for the country index (local curr |
| Trailing EPS 252 | t2_levels | D | ? |  | 34 | 2000-01-01→2026-06-11 | 0 | Change in trailing 12-month EPS over the trailing 252 trading days (realized ear |
| Trailing PE | t2_levels | M | ↓ |  | 34 | 2000-01-01→2026-06-11 | 0 | Country index price divided by trailing 12-month aggregate earnings per share. |

## gdelt_factors_daily  (75 variables)

| variable | source | freq | sign | role | countries | range | fresh(d) | definition |
|---|---|---|---|---|---|---|---|---|
| 1DRet | gdelt_daily | D | ↑ | RET-ALIAS | 34 | 2015-06-24→2026-06-09 | 2 | 1-day price return of the country equity index. |
| attention_fast_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| attention_fast_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| attention_fast_z_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| attention_fast_z_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| attention_shock_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| attention_shock_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| attention_slow_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| attention_slow_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| attention_slow_z_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| attention_slow_z_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| attention_trend_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| attention_trend_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| attention_trend_z_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| attention_trend_z_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| country_news_attention_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| country_news_attention_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| country_news_risk_raw_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| country_news_risk_raw_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| country_news_sentiment_raw_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| country_news_sentiment_raw_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| daily_defensive_CS | gdelt_daily | D | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| daily_defensive_TS | gdelt_daily | D | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| daily_metronome_CS | gdelt_daily | D | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| daily_metronome_TS | gdelt_daily | D | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| daily_risk_CS | gdelt_daily | D | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| daily_risk_TS | gdelt_daily | D | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| defensive_rank_pct_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| defensive_rank_pct_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| dispersion_fast_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| dispersion_fast_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| dispersion_fast_z_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| dispersion_fast_z_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| foreign_tone_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| foreign_tone_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| foreign_tone_fast_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| foreign_tone_fast_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| foreign_tone_fast_z_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| foreign_tone_fast_z_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| lf_gap_z_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| lf_gap_z_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| local_attention_share_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| local_attention_share_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| local_foreign_gap_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| local_foreign_gap_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| local_tone_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| local_tone_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| local_tone_fast_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| local_tone_fast_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| local_tone_fast_z_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| local_tone_fast_z_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| metronome_rank_pct_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| metronome_rank_pct_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| n_articles_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| n_articles_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| risk_fast_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| risk_fast_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| risk_fast_z_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| risk_fast_z_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| risk_rank_pct_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| risk_rank_pct_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| sentiment_fast_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| sentiment_fast_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| sentiment_fast_z_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| sentiment_fast_z_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| sentiment_slow_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| sentiment_slow_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| sentiment_slow_z_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| sentiment_slow_z_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| sentiment_trend_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| sentiment_trend_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| sentiment_trend_z_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| sentiment_trend_z_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| tone_dispersion_CS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |
| tone_dispersion_TS | gdelt_daily | M | ↑ |  | 34 | 2015-06-24→2026-06-09 | 2 |  |

## commodity_panel  (609 variables)

| variable | source | freq | sign | role | countries | range | fresh(d) | definition |
|---|---|---|---|---|---|---|---|---|
| WB_CMDTY_ALUMINUM_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | aluminum price level (World Bank Pink Sheet, monthly, global series broadcast to |
| WB_CMDTY_ALUMINUM_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the aluminum price (Pink Sheet). |
| WB_CMDTY_ALUMINUM_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the aluminum price (Pink Sheet). |
| WB_CMDTY_ALUMINUM_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the aluminum price (Pink Sheet). |
| WB_CMDTY_ALUMINUM_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly aluminum price returns (Pink Sheet). |
| WB_CMDTY_ALUMINUM_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the aluminum price (Pink Sheet). |
| WB_CMDTY_ALUMINUM_Z_36M | wb_commodity | M | ? |  | 0 | 1962-02-01→2026-05-01 | 41 | Z-score of the aluminum price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_BANANA_EU_LEVEL | wb_commodity | M | ? |  | 0 | 1997-01-01→2026-05-01 | 41 | banana (EU) price level (World Bank Pink Sheet, monthly, global series broadcast |
| WB_CMDTY_BANANA_EU_MOM_PCT | wb_commodity | M | ? |  | 0 | 1997-02-01→2026-05-01 | 41 | Month-over-month percent change in the banana (EU) price (Pink Sheet). |
| WB_CMDTY_BANANA_EU_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1998-01-01→2026-05-01 | 41 | 12-month percent return of the banana (EU) price (Pink Sheet). |
| WB_CMDTY_BANANA_EU_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1997-04-01→2026-05-01 | 41 | 3-month percent return of the banana (EU) price (Pink Sheet). |
| WB_CMDTY_BANANA_EU_VOL_12M | wb_commodity | M | ? |  | 0 | 1997-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly banana (EU) price returns (Pink Sheet). |
| WB_CMDTY_BANANA_EU_YOY_PCT | wb_commodity | M | ? |  | 0 | 1998-01-01→2026-05-01 | 41 | Year-over-year percent change in the banana (EU) price (Pink Sheet). |
| WB_CMDTY_BANANA_EU_Z_36M | wb_commodity | M | ? |  | 0 | 1997-12-01→2026-05-01 | 41 | Z-score of the banana (EU) price versus its trailing 36-month history (Pink Shee |
| WB_CMDTY_BANANA_US_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | banana (US) price level (World Bank Pink Sheet, monthly, global series broadcast |
| WB_CMDTY_BANANA_US_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the banana (US) price (Pink Sheet). |
| WB_CMDTY_BANANA_US_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the banana (US) price (Pink Sheet). |
| WB_CMDTY_BANANA_US_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the banana (US) price (Pink Sheet). |
| WB_CMDTY_BANANA_US_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly banana (US) price returns (Pink Sheet). |
| WB_CMDTY_BANANA_US_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the banana (US) price (Pink Sheet). |
| WB_CMDTY_BANANA_US_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the banana (US) price versus its trailing 36-month history (Pink Shee |
| WB_CMDTY_BARLEY_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2020-08-01 | 2140 ⚠STALE | barley price level (World Bank Pink Sheet, monthly, global series broadcast to a |
| WB_CMDTY_BARLEY_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2020-08-01 | 2140 ⚠STALE | Month-over-month percent change in the barley price (Pink Sheet). |
| WB_CMDTY_BARLEY_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2020-08-01 | 2140 ⚠STALE | 12-month percent return of the barley price (Pink Sheet). |
| WB_CMDTY_BARLEY_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2020-08-01 | 2140 ⚠STALE | 3-month percent return of the barley price (Pink Sheet). |
| WB_CMDTY_BARLEY_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2020-08-01 | 2140 ⚠STALE | 12-month rolling volatility of monthly barley price returns (Pink Sheet). |
| WB_CMDTY_BARLEY_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2020-08-01 | 2140 ⚠STALE | Year-over-year percent change in the barley price (Pink Sheet). |
| WB_CMDTY_BARLEY_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2020-08-01 | 2140 ⚠STALE | Z-score of the barley price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_BEEF_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | beef price level (World Bank Pink Sheet, monthly, global series broadcast to all |
| WB_CMDTY_BEEF_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the beef price (Pink Sheet). |
| WB_CMDTY_BEEF_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the beef price (Pink Sheet). |
| WB_CMDTY_BEEF_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the beef price (Pink Sheet). |
| WB_CMDTY_BEEF_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly beef price returns (Pink Sheet). |
| WB_CMDTY_BEEF_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the beef price (Pink Sheet). |
| WB_CMDTY_BEEF_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the beef price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_CHICKEN_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | chicken price level (World Bank Pink Sheet, monthly, global series broadcast to  |
| WB_CMDTY_CHICKEN_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the chicken price (Pink Sheet). |
| WB_CMDTY_CHICKEN_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the chicken price (Pink Sheet). |
| WB_CMDTY_CHICKEN_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the chicken price (Pink Sheet). |
| WB_CMDTY_CHICKEN_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly chicken price returns (Pink Sheet). |
| WB_CMDTY_CHICKEN_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the chicken price (Pink Sheet). |
| WB_CMDTY_CHICKEN_Z_36M | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Z-score of the chicken price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_COAL_AUS_LEVEL | wb_commodity | M | ? |  | 0 | 1970-01-01→2026-05-01 | 41 | coal aus price level (World Bank Pink Sheet, monthly, global series broadcast to |
| WB_CMDTY_COAL_AUS_MOM_PCT | wb_commodity | M | ? |  | 0 | 1970-02-01→2026-05-01 | 41 | Month-over-month percent change in the coal aus price (Pink Sheet). |
| WB_CMDTY_COAL_AUS_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1971-01-01→2026-05-01 | 41 | 12-month percent return of the coal aus price (Pink Sheet). |
| WB_CMDTY_COAL_AUS_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1970-04-01→2026-05-01 | 41 | 3-month percent return of the coal aus price (Pink Sheet). |
| WB_CMDTY_COAL_AUS_VOL_12M | wb_commodity | M | ? |  | 0 | 1970-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly coal aus price returns (Pink Sheet). |
| WB_CMDTY_COAL_AUS_YOY_PCT | wb_commodity | M | ? |  | 0 | 1971-01-01→2026-05-01 | 41 | Year-over-year percent change in the coal aus price (Pink Sheet). |
| WB_CMDTY_COAL_AUS_Z_36M | wb_commodity | M | ? |  | 0 | 1971-01-01→2026-05-01 | 41 | Z-score of the coal aus price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_COAL_SAFRICA_LEVEL | wb_commodity | M | ? |  | 0 | 1984-01-01→2026-05-01 | 41 | coal safrica price level (World Bank Pink Sheet, monthly, global series broadcas |
| WB_CMDTY_COAL_SAFRICA_MOM_PCT | wb_commodity | M | ? |  | 0 | 1984-02-01→2026-05-01 | 41 | Month-over-month percent change in the coal safrica price (Pink Sheet). |
| WB_CMDTY_COAL_SAFRICA_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1985-01-01→2026-05-01 | 41 | 12-month percent return of the coal safrica price (Pink Sheet). |
| WB_CMDTY_COAL_SAFRICA_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1984-04-01→2026-05-01 | 41 | 3-month percent return of the coal safrica price (Pink Sheet). |
| WB_CMDTY_COAL_SAFRICA_VOL_12M | wb_commodity | M | ? |  | 0 | 1984-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly coal safrica price returns (Pink Sheet). |
| WB_CMDTY_COAL_SAFRICA_YOY_PCT | wb_commodity | M | ? |  | 0 | 1985-01-01→2026-05-01 | 41 | Year-over-year percent change in the coal safrica price (Pink Sheet). |
| WB_CMDTY_COAL_SAFRICA_Z_36M | wb_commodity | M | ? |  | 0 | 1984-12-01→2026-05-01 | 41 | Z-score of the coal safrica price versus its trailing 36-month history (Pink She |
| WB_CMDTY_COCOA_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | cocoa price level (World Bank Pink Sheet, monthly, global series broadcast to al |
| WB_CMDTY_COCOA_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the cocoa price (Pink Sheet). |
| WB_CMDTY_COCOA_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the cocoa price (Pink Sheet). |
| WB_CMDTY_COCOA_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the cocoa price (Pink Sheet). |
| WB_CMDTY_COCOA_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly cocoa price returns (Pink Sheet). |
| WB_CMDTY_COCOA_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the cocoa price (Pink Sheet). |
| WB_CMDTY_COCOA_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the cocoa price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_COCONUT_OIL_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | coconut oil price level (World Bank Pink Sheet, monthly, global series broadcast |
| WB_CMDTY_COCONUT_OIL_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the coconut oil price (Pink Sheet). |
| WB_CMDTY_COCONUT_OIL_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the coconut oil price (Pink Sheet). |
| WB_CMDTY_COCONUT_OIL_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the coconut oil price (Pink Sheet). |
| WB_CMDTY_COCONUT_OIL_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly coconut oil price returns (Pink Sheet). |
| WB_CMDTY_COCONUT_OIL_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the coconut oil price (Pink Sheet). |
| WB_CMDTY_COCONUT_OIL_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the coconut oil price versus its trailing 36-month history (Pink Shee |
| WB_CMDTY_COFFEE_ARABIC_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | coffee arabic price level (World Bank Pink Sheet, monthly, global series broadca |
| WB_CMDTY_COFFEE_ARABIC_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the coffee arabic price (Pink Sheet). |
| WB_CMDTY_COFFEE_ARABIC_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the coffee arabic price (Pink Sheet). |
| WB_CMDTY_COFFEE_ARABIC_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the coffee arabic price (Pink Sheet). |
| WB_CMDTY_COFFEE_ARABIC_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly coffee arabic price returns (Pink Sheet). |
| WB_CMDTY_COFFEE_ARABIC_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the coffee arabic price (Pink Sheet). |
| WB_CMDTY_COFFEE_ARABIC_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the coffee arabic price versus its trailing 36-month history (Pink Sh |
| WB_CMDTY_COFFEE_ROBUS_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | coffee robus price level (World Bank Pink Sheet, monthly, global series broadcas |
| WB_CMDTY_COFFEE_ROBUS_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the coffee robus price (Pink Sheet). |
| WB_CMDTY_COFFEE_ROBUS_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the coffee robus price (Pink Sheet). |
| WB_CMDTY_COFFEE_ROBUS_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the coffee robus price (Pink Sheet). |
| WB_CMDTY_COFFEE_ROBUS_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly coffee robus price returns (Pink Sheet). |
| WB_CMDTY_COFFEE_ROBUS_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the coffee robus price (Pink Sheet). |
| WB_CMDTY_COFFEE_ROBUS_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the coffee robus price versus its trailing 36-month history (Pink She |
| WB_CMDTY_COPPER_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | copper price level (World Bank Pink Sheet, monthly, global series broadcast to a |
| WB_CMDTY_COPPER_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the copper price (Pink Sheet). |
| WB_CMDTY_COPPER_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the copper price (Pink Sheet). |
| WB_CMDTY_COPPER_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the copper price (Pink Sheet). |
| WB_CMDTY_COPPER_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly copper price returns (Pink Sheet). |
| WB_CMDTY_COPPER_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the copper price (Pink Sheet). |
| WB_CMDTY_COPPER_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the copper price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_COTTON_A_INDX_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | cotton a indx price level (World Bank Pink Sheet, monthly, global series broadca |
| WB_CMDTY_COTTON_A_INDX_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the cotton a indx price (Pink Sheet). |
| WB_CMDTY_COTTON_A_INDX_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the cotton a indx price (Pink Sheet). |
| WB_CMDTY_COTTON_A_INDX_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the cotton a indx price (Pink Sheet). |
| WB_CMDTY_COTTON_A_INDX_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly cotton a indx price returns (Pink Sheet). |
| WB_CMDTY_COTTON_A_INDX_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the cotton a indx price (Pink Sheet). |
| WB_CMDTY_COTTON_A_INDX_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the cotton a indx price versus its trailing 36-month history (Pink Sh |
| WB_CMDTY_CRUDE_BRENT_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | crude brent price level (World Bank Pink Sheet, monthly, global series broadcast |
| WB_CMDTY_CRUDE_BRENT_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the crude brent price (Pink Sheet). |
| WB_CMDTY_CRUDE_BRENT_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the crude brent price (Pink Sheet). |
| WB_CMDTY_CRUDE_BRENT_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the crude brent price (Pink Sheet). |
| WB_CMDTY_CRUDE_BRENT_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly crude brent price returns (Pink Sheet). |
| WB_CMDTY_CRUDE_BRENT_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the crude brent price (Pink Sheet). |
| WB_CMDTY_CRUDE_BRENT_Z_36M | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Z-score of the crude brent price versus its trailing 36-month history (Pink Shee |
| WB_CMDTY_CRUDE_DUBAI_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | crude dubai price level (World Bank Pink Sheet, monthly, global series broadcast |
| WB_CMDTY_CRUDE_DUBAI_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the crude dubai price (Pink Sheet). |
| WB_CMDTY_CRUDE_DUBAI_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the crude dubai price (Pink Sheet). |
| WB_CMDTY_CRUDE_DUBAI_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the crude dubai price (Pink Sheet). |
| WB_CMDTY_CRUDE_DUBAI_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly crude dubai price returns (Pink Sheet). |
| WB_CMDTY_CRUDE_DUBAI_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the crude dubai price (Pink Sheet). |
| WB_CMDTY_CRUDE_DUBAI_Z_36M | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Z-score of the crude dubai price versus its trailing 36-month history (Pink Shee |
| WB_CMDTY_CRUDE_PETRO_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | crude petro price level (World Bank Pink Sheet, monthly, global series broadcast |
| WB_CMDTY_CRUDE_PETRO_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the crude petro price (Pink Sheet). |
| WB_CMDTY_CRUDE_PETRO_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the crude petro price (Pink Sheet). |
| WB_CMDTY_CRUDE_PETRO_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the crude petro price (Pink Sheet). |
| WB_CMDTY_CRUDE_PETRO_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly crude petro price returns (Pink Sheet). |
| WB_CMDTY_CRUDE_PETRO_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the crude petro price (Pink Sheet). |
| WB_CMDTY_CRUDE_PETRO_Z_36M | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Z-score of the crude petro price versus its trailing 36-month history (Pink Shee |
| WB_CMDTY_CRUDE_WTI_LEVEL | wb_commodity | M | ? |  | 0 | 1982-01-01→2026-05-01 | 41 | crude WTI price level (World Bank Pink Sheet, monthly, global series broadcast t |
| WB_CMDTY_CRUDE_WTI_MOM_PCT | wb_commodity | M | ? |  | 0 | 1982-02-01→2026-05-01 | 41 | Month-over-month percent change in the crude WTI price (Pink Sheet). |
| WB_CMDTY_CRUDE_WTI_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1983-01-01→2026-05-01 | 41 | 12-month percent return of the crude WTI price (Pink Sheet). |
| WB_CMDTY_CRUDE_WTI_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1982-04-01→2026-05-01 | 41 | 3-month percent return of the crude WTI price (Pink Sheet). |
| WB_CMDTY_CRUDE_WTI_VOL_12M | wb_commodity | M | ? |  | 0 | 1982-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly crude WTI price returns (Pink Sheet). |
| WB_CMDTY_CRUDE_WTI_YOY_PCT | wb_commodity | M | ? |  | 0 | 1983-01-01→2026-05-01 | 41 | Year-over-year percent change in the crude WTI price (Pink Sheet). |
| WB_CMDTY_CRUDE_WTI_Z_36M | wb_commodity | M | ? |  | 0 | 1982-12-01→2026-05-01 | 41 | Z-score of the crude WTI price versus its trailing 36-month history (Pink Sheet) |
| WB_CMDTY_DAP_LEVEL | wb_commodity | M | ? |  | 0 | 1967-01-01→2026-05-01 | 41 | DAP price level (World Bank Pink Sheet, monthly, global series broadcast to all  |
| WB_CMDTY_DAP_MOM_PCT | wb_commodity | M | ? |  | 0 | 1967-02-01→2026-05-01 | 41 | Month-over-month percent change in the DAP price (Pink Sheet). |
| WB_CMDTY_DAP_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1968-01-01→2026-05-01 | 41 | 12-month percent return of the DAP price (Pink Sheet). |
| WB_CMDTY_DAP_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1967-04-01→2026-05-01 | 41 | 3-month percent return of the DAP price (Pink Sheet). |
| WB_CMDTY_DAP_VOL_12M | wb_commodity | M | ? |  | 0 | 1967-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly DAP price returns (Pink Sheet). |
| WB_CMDTY_DAP_YOY_PCT | wb_commodity | M | ? |  | 0 | 1968-01-01→2026-05-01 | 41 | Year-over-year percent change in the DAP price (Pink Sheet). |
| WB_CMDTY_DAP_Z_36M | wb_commodity | M | ? |  | 0 | 1968-01-01→2026-05-01 | 41 | Z-score of the DAP price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_FISH_MEAL_LEVEL | wb_commodity | M | ? |  | 0 | 1979-01-01→2026-05-01 | 41 | fish meal price level (World Bank Pink Sheet, monthly, global series broadcast t |
| WB_CMDTY_FISH_MEAL_MOM_PCT | wb_commodity | M | ? |  | 0 | 1979-02-01→2026-05-01 | 41 | Month-over-month percent change in the fish meal price (Pink Sheet). |
| WB_CMDTY_FISH_MEAL_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1980-01-01→2026-05-01 | 41 | 12-month percent return of the fish meal price (Pink Sheet). |
| WB_CMDTY_FISH_MEAL_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1979-04-01→2026-05-01 | 41 | 3-month percent return of the fish meal price (Pink Sheet). |
| WB_CMDTY_FISH_MEAL_VOL_12M | wb_commodity | M | ? |  | 0 | 1979-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly fish meal price returns (Pink Sheet). |
| WB_CMDTY_FISH_MEAL_YOY_PCT | wb_commodity | M | ? |  | 0 | 1980-01-01→2026-05-01 | 41 | Year-over-year percent change in the fish meal price (Pink Sheet). |
| WB_CMDTY_FISH_MEAL_Z_36M | wb_commodity | M | ? |  | 0 | 1979-12-01→2026-05-01 | 41 | Z-score of the fish meal price versus its trailing 36-month history (Pink Sheet) |
| WB_CMDTY_GOLD_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | gold price level (World Bank Pink Sheet, monthly, global series broadcast to all |
| WB_CMDTY_GOLD_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the gold price (Pink Sheet). |
| WB_CMDTY_GOLD_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the gold price (Pink Sheet). |
| WB_CMDTY_GOLD_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the gold price (Pink Sheet). |
| WB_CMDTY_GOLD_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly gold price returns (Pink Sheet). |
| WB_CMDTY_GOLD_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the gold price (Pink Sheet). |
| WB_CMDTY_GOLD_Z_36M | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Z-score of the gold price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_GRNUT_LEVEL | wb_commodity | M | ? |  | 0 | 1980-01-01→2026-05-01 | 41 | grnut price level (World Bank Pink Sheet, monthly, global series broadcast to al |
| WB_CMDTY_GRNUT_MOM_PCT | wb_commodity | M | ? |  | 0 | 1980-02-01→2026-05-01 | 41 | Month-over-month percent change in the grnut price (Pink Sheet). |
| WB_CMDTY_GRNUT_OIL_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | grnut oil price level (World Bank Pink Sheet, monthly, global series broadcast t |
| WB_CMDTY_GRNUT_OIL_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the grnut oil price (Pink Sheet). |
| WB_CMDTY_GRNUT_OIL_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the grnut oil price (Pink Sheet). |
| WB_CMDTY_GRNUT_OIL_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the grnut oil price (Pink Sheet). |
| WB_CMDTY_GRNUT_OIL_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly grnut oil price returns (Pink Sheet). |
| WB_CMDTY_GRNUT_OIL_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the grnut oil price (Pink Sheet). |
| WB_CMDTY_GRNUT_OIL_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the grnut oil price versus its trailing 36-month history (Pink Sheet) |
| WB_CMDTY_GRNUT_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1981-01-01→2026-05-01 | 41 | 12-month percent return of the grnut price (Pink Sheet). |
| WB_CMDTY_GRNUT_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1980-04-01→2026-05-01 | 41 | 3-month percent return of the grnut price (Pink Sheet). |
| WB_CMDTY_GRNUT_VOL_12M | wb_commodity | M | ? |  | 0 | 1980-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly grnut price returns (Pink Sheet). |
| WB_CMDTY_GRNUT_YOY_PCT | wb_commodity | M | ? |  | 0 | 1981-01-01→2026-05-01 | 41 | Year-over-year percent change in the grnut price (Pink Sheet). |
| WB_CMDTY_GRNUT_Z_36M | wb_commodity | M | ? |  | 0 | 1980-12-01→2026-05-01 | 41 | Z-score of the grnut price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_IAGRICULTURE_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | iagriculture price level (World Bank Pink Sheet, monthly, global series broadcas |
| WB_CMDTY_IAGRICULTURE_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the iagriculture price (Pink Sheet). |
| WB_CMDTY_IAGRICULTURE_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the iagriculture price (Pink Sheet). |
| WB_CMDTY_IAGRICULTURE_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the iagriculture price (Pink Sheet). |
| WB_CMDTY_IAGRICULTURE_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly iagriculture price returns (Pink Sheet). |
| WB_CMDTY_IAGRICULTURE_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the iagriculture price (Pink Sheet). |
| WB_CMDTY_IAGRICULTURE_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the iagriculture price versus its trailing 36-month history (Pink She |
| WB_CMDTY_IBASEMET_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | ibasemet price level (World Bank Pink Sheet, monthly, global series broadcast to |
| WB_CMDTY_IBASEMET_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the ibasemet price (Pink Sheet). |
| WB_CMDTY_IBASEMET_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the ibasemet price (Pink Sheet). |
| WB_CMDTY_IBASEMET_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the ibasemet price (Pink Sheet). |
| WB_CMDTY_IBASEMET_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly ibasemet price returns (Pink Sheet). |
| WB_CMDTY_IBASEMET_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the ibasemet price (Pink Sheet). |
| WB_CMDTY_IBASEMET_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the ibasemet price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_IBEVERAGES_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | ibeverages price level (World Bank Pink Sheet, monthly, global series broadcast  |
| WB_CMDTY_IBEVERAGES_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the ibeverages price (Pink Sheet). |
| WB_CMDTY_IBEVERAGES_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the ibeverages price (Pink Sheet). |
| WB_CMDTY_IBEVERAGES_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the ibeverages price (Pink Sheet). |
| WB_CMDTY_IBEVERAGES_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly ibeverages price returns (Pink Sheet). |
| WB_CMDTY_IBEVERAGES_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the ibeverages price (Pink Sheet). |
| WB_CMDTY_IBEVERAGES_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the ibeverages price versus its trailing 36-month history (Pink Sheet |
| WB_CMDTY_IENERGY_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | ienergy price level (World Bank Pink Sheet, monthly, global series broadcast to  |
| WB_CMDTY_IENERGY_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the ienergy price (Pink Sheet). |
| WB_CMDTY_IENERGY_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the ienergy price (Pink Sheet). |
| WB_CMDTY_IENERGY_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the ienergy price (Pink Sheet). |
| WB_CMDTY_IENERGY_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly ienergy price returns (Pink Sheet). |
| WB_CMDTY_IENERGY_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the ienergy price (Pink Sheet). |
| WB_CMDTY_IENERGY_Z_36M | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Z-score of the ienergy price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_IFATS_OILS_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | ifats oils price level (World Bank Pink Sheet, monthly, global series broadcast  |
| WB_CMDTY_IFATS_OILS_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the ifats oils price (Pink Sheet). |
| WB_CMDTY_IFATS_OILS_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the ifats oils price (Pink Sheet). |
| WB_CMDTY_IFATS_OILS_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the ifats oils price (Pink Sheet). |
| WB_CMDTY_IFATS_OILS_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly ifats oils price returns (Pink Sheet). |
| WB_CMDTY_IFATS_OILS_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the ifats oils price (Pink Sheet). |
| WB_CMDTY_IFATS_OILS_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the ifats oils price versus its trailing 36-month history (Pink Sheet |
| WB_CMDTY_IFERTILIZERS_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | ifertilizers price level (World Bank Pink Sheet, monthly, global series broadcas |
| WB_CMDTY_IFERTILIZERS_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the ifertilizers price (Pink Sheet). |
| WB_CMDTY_IFERTILIZERS_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the ifertilizers price (Pink Sheet). |
| WB_CMDTY_IFERTILIZERS_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the ifertilizers price (Pink Sheet). |
| WB_CMDTY_IFERTILIZERS_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly ifertilizers price returns (Pink Sheet). |
| WB_CMDTY_IFERTILIZERS_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the ifertilizers price (Pink Sheet). |
| WB_CMDTY_IFERTILIZERS_Z_36M | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Z-score of the ifertilizers price versus its trailing 36-month history (Pink She |
| WB_CMDTY_IFOOD_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | ifood price level (World Bank Pink Sheet, monthly, global series broadcast to al |
| WB_CMDTY_IFOOD_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the ifood price (Pink Sheet). |
| WB_CMDTY_IFOOD_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the ifood price (Pink Sheet). |
| WB_CMDTY_IFOOD_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the ifood price (Pink Sheet). |
| WB_CMDTY_IFOOD_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly ifood price returns (Pink Sheet). |
| WB_CMDTY_IFOOD_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the ifood price (Pink Sheet). |
| WB_CMDTY_IFOOD_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the ifood price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_IGRAINS_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | igrains price level (World Bank Pink Sheet, monthly, global series broadcast to  |
| WB_CMDTY_IGRAINS_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the igrains price (Pink Sheet). |
| WB_CMDTY_IGRAINS_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the igrains price (Pink Sheet). |
| WB_CMDTY_IGRAINS_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the igrains price (Pink Sheet). |
| WB_CMDTY_IGRAINS_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly igrains price returns (Pink Sheet). |
| WB_CMDTY_IGRAINS_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the igrains price (Pink Sheet). |
| WB_CMDTY_IGRAINS_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the igrains price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_IMETMIN_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | imetmin price level (World Bank Pink Sheet, monthly, global series broadcast to  |
| WB_CMDTY_IMETMIN_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the imetmin price (Pink Sheet). |
| WB_CMDTY_IMETMIN_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the imetmin price (Pink Sheet). |
| WB_CMDTY_IMETMIN_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the imetmin price (Pink Sheet). |
| WB_CMDTY_IMETMIN_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly imetmin price returns (Pink Sheet). |
| WB_CMDTY_IMETMIN_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the imetmin price (Pink Sheet). |
| WB_CMDTY_IMETMIN_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the imetmin price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_INATGAS_LEVEL | wb_commodity | M | ? |  | 0 | 1977-01-01→2026-05-01 | 41 | inatgas price level (World Bank Pink Sheet, monthly, global series broadcast to  |
| WB_CMDTY_INATGAS_MOM_PCT | wb_commodity | M | ? |  | 0 | 1977-02-01→2026-05-01 | 41 | Month-over-month percent change in the inatgas price (Pink Sheet). |
| WB_CMDTY_INATGAS_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1978-01-01→2026-05-01 | 41 | 12-month percent return of the inatgas price (Pink Sheet). |
| WB_CMDTY_INATGAS_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1977-04-01→2026-05-01 | 41 | 3-month percent return of the inatgas price (Pink Sheet). |
| WB_CMDTY_INATGAS_VOL_12M | wb_commodity | M | ? |  | 0 | 1977-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly inatgas price returns (Pink Sheet). |
| WB_CMDTY_INATGAS_YOY_PCT | wb_commodity | M | ? |  | 0 | 1978-01-01→2026-05-01 | 41 | Year-over-year percent change in the inatgas price (Pink Sheet). |
| WB_CMDTY_INATGAS_Z_36M | wb_commodity | M | ? |  | 0 | 1977-12-01→2026-05-01 | 41 | Z-score of the inatgas price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_INONFUEL_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | inonfuel price level (World Bank Pink Sheet, monthly, global series broadcast to |
| WB_CMDTY_INONFUEL_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the inonfuel price (Pink Sheet). |
| WB_CMDTY_INONFUEL_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the inonfuel price (Pink Sheet). |
| WB_CMDTY_INONFUEL_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the inonfuel price (Pink Sheet). |
| WB_CMDTY_INONFUEL_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly inonfuel price returns (Pink Sheet). |
| WB_CMDTY_INONFUEL_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the inonfuel price (Pink Sheet). |
| WB_CMDTY_INONFUEL_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the inonfuel price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_IOTHERFOOD_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | iotherfood price level (World Bank Pink Sheet, monthly, global series broadcast  |
| WB_CMDTY_IOTHERFOOD_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the iotherfood price (Pink Sheet). |
| WB_CMDTY_IOTHERFOOD_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the iotherfood price (Pink Sheet). |
| WB_CMDTY_IOTHERFOOD_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the iotherfood price (Pink Sheet). |
| WB_CMDTY_IOTHERFOOD_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly iotherfood price returns (Pink Sheet). |
| WB_CMDTY_IOTHERFOOD_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the iotherfood price (Pink Sheet). |
| WB_CMDTY_IOTHERFOOD_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the iotherfood price versus its trailing 36-month history (Pink Sheet |
| WB_CMDTY_IOTHERRAWMAT_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | iotherrawmat price level (World Bank Pink Sheet, monthly, global series broadcas |
| WB_CMDTY_IOTHERRAWMAT_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the iotherrawmat price (Pink Sheet). |
| WB_CMDTY_IOTHERRAWMAT_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the iotherrawmat price (Pink Sheet). |
| WB_CMDTY_IOTHERRAWMAT_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the iotherrawmat price (Pink Sheet). |
| WB_CMDTY_IOTHERRAWMAT_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly iotherrawmat price returns (Pink Sheet). |
| WB_CMDTY_IOTHERRAWMAT_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the iotherrawmat price (Pink Sheet). |
| WB_CMDTY_IOTHERRAWMAT_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the iotherrawmat price versus its trailing 36-month history (Pink She |
| WB_CMDTY_IOVERALL_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | ioverall price level (World Bank Pink Sheet, monthly, global series broadcast to |
| WB_CMDTY_IOVERALL_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the ioverall price (Pink Sheet). |
| WB_CMDTY_IOVERALL_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the ioverall price (Pink Sheet). |
| WB_CMDTY_IOVERALL_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the ioverall price (Pink Sheet). |
| WB_CMDTY_IOVERALL_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly ioverall price returns (Pink Sheet). |
| WB_CMDTY_IOVERALL_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the ioverall price (Pink Sheet). |
| WB_CMDTY_IOVERALL_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the ioverall price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_IPRECIOUSMET_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | ipreciousmet price level (World Bank Pink Sheet, monthly, global series broadcas |
| WB_CMDTY_IPRECIOUSMET_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the ipreciousmet price (Pink Sheet). |
| WB_CMDTY_IPRECIOUSMET_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the ipreciousmet price (Pink Sheet). |
| WB_CMDTY_IPRECIOUSMET_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the ipreciousmet price (Pink Sheet). |
| WB_CMDTY_IPRECIOUSMET_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly ipreciousmet price returns (Pink Sheet). |
| WB_CMDTY_IPRECIOUSMET_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the ipreciousmet price (Pink Sheet). |
| WB_CMDTY_IPRECIOUSMET_Z_36M | wb_commodity | M | ? |  | 0 | 1961-11-01→2026-05-01 | 41 | Z-score of the ipreciousmet price versus its trailing 36-month history (Pink She |
| WB_CMDTY_IRAW_MATERIAL_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | iraw material price level (World Bank Pink Sheet, monthly, global series broadca |
| WB_CMDTY_IRAW_MATERIAL_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the iraw material price (Pink Sheet). |
| WB_CMDTY_IRAW_MATERIAL_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the iraw material price (Pink Sheet). |
| WB_CMDTY_IRAW_MATERIAL_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the iraw material price (Pink Sheet). |
| WB_CMDTY_IRAW_MATERIAL_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly iraw material price returns (Pink Sheet). |
| WB_CMDTY_IRAW_MATERIAL_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the iraw material price (Pink Sheet). |
| WB_CMDTY_IRAW_MATERIAL_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the iraw material price versus its trailing 36-month history (Pink Sh |
| WB_CMDTY_IRON_ORE_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | iron ore price level (World Bank Pink Sheet, monthly, global series broadcast to |
| WB_CMDTY_IRON_ORE_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the iron ore price (Pink Sheet). |
| WB_CMDTY_IRON_ORE_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the iron ore price (Pink Sheet). |
| WB_CMDTY_IRON_ORE_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the iron ore price (Pink Sheet). |
| WB_CMDTY_IRON_ORE_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly iron ore price returns (Pink Sheet). |
| WB_CMDTY_IRON_ORE_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the iron ore price (Pink Sheet). |
| WB_CMDTY_IRON_ORE_Z_36M | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Z-score of the iron ore price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_ITIMBER_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | itimber price level (World Bank Pink Sheet, monthly, global series broadcast to  |
| WB_CMDTY_ITIMBER_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the itimber price (Pink Sheet). |
| WB_CMDTY_ITIMBER_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the itimber price (Pink Sheet). |
| WB_CMDTY_ITIMBER_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the itimber price (Pink Sheet). |
| WB_CMDTY_ITIMBER_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly itimber price returns (Pink Sheet). |
| WB_CMDTY_ITIMBER_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the itimber price (Pink Sheet). |
| WB_CMDTY_ITIMBER_Z_36M | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Z-score of the itimber price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_LAMB_LEVEL | wb_commodity | M | ? |  | 0 | 1971-01-01→2026-05-01 | 41 | lamb price level (World Bank Pink Sheet, monthly, global series broadcast to all |
| WB_CMDTY_LAMB_MOM_PCT | wb_commodity | M | ? |  | 0 | 1971-02-01→2026-05-01 | 41 | Month-over-month percent change in the lamb price (Pink Sheet). |
| WB_CMDTY_LAMB_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1972-01-01→2026-05-01 | 41 | 12-month percent return of the lamb price (Pink Sheet). |
| WB_CMDTY_LAMB_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1971-04-01→2026-05-01 | 41 | 3-month percent return of the lamb price (Pink Sheet). |
| WB_CMDTY_LAMB_VOL_12M | wb_commodity | M | ? |  | 0 | 1971-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly lamb price returns (Pink Sheet). |
| WB_CMDTY_LAMB_YOY_PCT | wb_commodity | M | ? |  | 0 | 1972-01-01→2026-05-01 | 41 | Year-over-year percent change in the lamb price (Pink Sheet). |
| WB_CMDTY_LAMB_Z_36M | wb_commodity | M | ? |  | 0 | 1971-12-01→2026-05-01 | 41 | Z-score of the lamb price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_LEAD_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | lead price level (World Bank Pink Sheet, monthly, global series broadcast to all |
| WB_CMDTY_LEAD_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the lead price (Pink Sheet). |
| WB_CMDTY_LEAD_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the lead price (Pink Sheet). |
| WB_CMDTY_LEAD_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the lead price (Pink Sheet). |
| WB_CMDTY_LEAD_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly lead price returns (Pink Sheet). |
| WB_CMDTY_LEAD_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the lead price (Pink Sheet). |
| WB_CMDTY_LEAD_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the lead price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_LOGS_CMR_LEVEL | wb_commodity | M | ? |  | 0 | 1970-01-01→2026-05-01 | 41 | logs cmr price level (World Bank Pink Sheet, monthly, global series broadcast to |
| WB_CMDTY_LOGS_CMR_MOM_PCT | wb_commodity | M | ? |  | 0 | 1970-02-01→2026-05-01 | 41 | Month-over-month percent change in the logs cmr price (Pink Sheet). |
| WB_CMDTY_LOGS_CMR_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1971-01-01→2026-05-01 | 41 | 12-month percent return of the logs cmr price (Pink Sheet). |
| WB_CMDTY_LOGS_CMR_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1970-04-01→2026-05-01 | 41 | 3-month percent return of the logs cmr price (Pink Sheet). |
| WB_CMDTY_LOGS_CMR_VOL_12M | wb_commodity | M | ? |  | 0 | 1970-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly logs cmr price returns (Pink Sheet). |
| WB_CMDTY_LOGS_CMR_YOY_PCT | wb_commodity | M | ? |  | 0 | 1971-01-01→2026-05-01 | 41 | Year-over-year percent change in the logs cmr price (Pink Sheet). |
| WB_CMDTY_LOGS_CMR_Z_36M | wb_commodity | M | ? |  | 0 | 1971-01-01→2026-05-01 | 41 | Z-score of the logs cmr price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_LOGS_MYS_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | logs mys price level (World Bank Pink Sheet, monthly, global series broadcast to |
| WB_CMDTY_LOGS_MYS_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the logs mys price (Pink Sheet). |
| WB_CMDTY_LOGS_MYS_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the logs mys price (Pink Sheet). |
| WB_CMDTY_LOGS_MYS_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the logs mys price (Pink Sheet). |
| WB_CMDTY_LOGS_MYS_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly logs mys price returns (Pink Sheet). |
| WB_CMDTY_LOGS_MYS_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the logs mys price (Pink Sheet). |
| WB_CMDTY_LOGS_MYS_Z_36M | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Z-score of the logs mys price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_MAIZE_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | maize price level (World Bank Pink Sheet, monthly, global series broadcast to al |
| WB_CMDTY_MAIZE_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the maize price (Pink Sheet). |
| WB_CMDTY_MAIZE_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the maize price (Pink Sheet). |
| WB_CMDTY_MAIZE_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the maize price (Pink Sheet). |
| WB_CMDTY_MAIZE_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly maize price returns (Pink Sheet). |
| WB_CMDTY_MAIZE_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the maize price (Pink Sheet). |
| WB_CMDTY_MAIZE_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the maize price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_NGAS_EUR_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | ngas eur price level (World Bank Pink Sheet, monthly, global series broadcast to |
| WB_CMDTY_NGAS_EUR_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the ngas eur price (Pink Sheet). |
| WB_CMDTY_NGAS_EUR_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the ngas eur price (Pink Sheet). |
| WB_CMDTY_NGAS_EUR_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the ngas eur price (Pink Sheet). |
| WB_CMDTY_NGAS_EUR_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly ngas eur price returns (Pink Sheet). |
| WB_CMDTY_NGAS_EUR_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the ngas eur price (Pink Sheet). |
| WB_CMDTY_NGAS_EUR_Z_36M | wb_commodity | M | ? |  | 0 | 1963-01-01→2026-05-01 | 41 | Z-score of the ngas eur price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_NGAS_JP_LEVEL | wb_commodity | M | ? |  | 0 | 1977-01-01→2026-05-01 | 41 | ngas jp price level (World Bank Pink Sheet, monthly, global series broadcast to  |
| WB_CMDTY_NGAS_JP_MOM_PCT | wb_commodity | M | ? |  | 0 | 1977-02-01→2026-05-01 | 41 | Month-over-month percent change in the ngas jp price (Pink Sheet). |
| WB_CMDTY_NGAS_JP_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1978-01-01→2026-05-01 | 41 | 12-month percent return of the ngas jp price (Pink Sheet). |
| WB_CMDTY_NGAS_JP_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1977-04-01→2026-05-01 | 41 | 3-month percent return of the ngas jp price (Pink Sheet). |
| WB_CMDTY_NGAS_JP_VOL_12M | wb_commodity | M | ? |  | 0 | 1977-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly ngas jp price returns (Pink Sheet). |
| WB_CMDTY_NGAS_JP_YOY_PCT | wb_commodity | M | ? |  | 0 | 1978-01-01→2026-05-01 | 41 | Year-over-year percent change in the ngas jp price (Pink Sheet). |
| WB_CMDTY_NGAS_JP_Z_36M | wb_commodity | M | ? |  | 0 | 1978-01-01→2026-05-01 | 41 | Z-score of the ngas jp price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_NGAS_US_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | ngas (US) price level (World Bank Pink Sheet, monthly, global series broadcast t |
| WB_CMDTY_NGAS_US_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the ngas (US) price (Pink Sheet). |
| WB_CMDTY_NGAS_US_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the ngas (US) price (Pink Sheet). |
| WB_CMDTY_NGAS_US_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the ngas (US) price (Pink Sheet). |
| WB_CMDTY_NGAS_US_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly ngas (US) price returns (Pink Sheet). |
| WB_CMDTY_NGAS_US_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the ngas (US) price (Pink Sheet). |
| WB_CMDTY_NGAS_US_Z_36M | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Z-score of the ngas (US) price versus its trailing 36-month history (Pink Sheet) |
| WB_CMDTY_NICKEL_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | nickel price level (World Bank Pink Sheet, monthly, global series broadcast to a |
| WB_CMDTY_NICKEL_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the nickel price (Pink Sheet). |
| WB_CMDTY_NICKEL_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the nickel price (Pink Sheet). |
| WB_CMDTY_NICKEL_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the nickel price (Pink Sheet). |
| WB_CMDTY_NICKEL_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly nickel price returns (Pink Sheet). |
| WB_CMDTY_NICKEL_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the nickel price (Pink Sheet). |
| WB_CMDTY_NICKEL_Z_36M | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Z-score of the nickel price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_ORANGE_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | orange price level (World Bank Pink Sheet, monthly, global series broadcast to a |
| WB_CMDTY_ORANGE_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the orange price (Pink Sheet). |
| WB_CMDTY_ORANGE_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the orange price (Pink Sheet). |
| WB_CMDTY_ORANGE_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the orange price (Pink Sheet). |
| WB_CMDTY_ORANGE_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly orange price returns (Pink Sheet). |
| WB_CMDTY_ORANGE_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the orange price (Pink Sheet). |
| WB_CMDTY_ORANGE_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the orange price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_PALM_OIL_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | palm oil price level (World Bank Pink Sheet, monthly, global series broadcast to |
| WB_CMDTY_PALM_OIL_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the palm oil price (Pink Sheet). |
| WB_CMDTY_PALM_OIL_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the palm oil price (Pink Sheet). |
| WB_CMDTY_PALM_OIL_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the palm oil price (Pink Sheet). |
| WB_CMDTY_PALM_OIL_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly palm oil price returns (Pink Sheet). |
| WB_CMDTY_PALM_OIL_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the palm oil price (Pink Sheet). |
| WB_CMDTY_PALM_OIL_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the palm oil price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_PHOSROCK_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | phosrock price level (World Bank Pink Sheet, monthly, global series broadcast to |
| WB_CMDTY_PHOSROCK_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the phosrock price (Pink Sheet). |
| WB_CMDTY_PHOSROCK_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the phosrock price (Pink Sheet). |
| WB_CMDTY_PHOSROCK_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the phosrock price (Pink Sheet). |
| WB_CMDTY_PHOSROCK_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly phosrock price returns (Pink Sheet). |
| WB_CMDTY_PHOSROCK_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the phosrock price (Pink Sheet). |
| WB_CMDTY_PHOSROCK_Z_36M | wb_commodity | M | ? |  | 0 | 1962-01-01→2026-05-01 | 41 | Z-score of the phosrock price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_PLATINUM_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | platinum price level (World Bank Pink Sheet, monthly, global series broadcast to |
| WB_CMDTY_PLATINUM_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the platinum price (Pink Sheet). |
| WB_CMDTY_PLATINUM_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the platinum price (Pink Sheet). |
| WB_CMDTY_PLATINUM_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the platinum price (Pink Sheet). |
| WB_CMDTY_PLATINUM_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly platinum price returns (Pink Sheet). |
| WB_CMDTY_PLATINUM_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the platinum price (Pink Sheet). |
| WB_CMDTY_PLATINUM_Z_36M | wb_commodity | M | ? |  | 0 | 1963-04-01→2026-05-01 | 41 | Z-score of the platinum price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_PLMKRNL_OIL_LEVEL | wb_commodity | M | ? |  | 0 | 1996-01-01→2026-05-01 | 41 | plmkrnl oil price level (World Bank Pink Sheet, monthly, global series broadcast |
| WB_CMDTY_PLMKRNL_OIL_MOM_PCT | wb_commodity | M | ? |  | 0 | 1996-02-01→2026-05-01 | 41 | Month-over-month percent change in the plmkrnl oil price (Pink Sheet). |
| WB_CMDTY_PLMKRNL_OIL_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1997-01-01→2026-05-01 | 41 | 12-month percent return of the plmkrnl oil price (Pink Sheet). |
| WB_CMDTY_PLMKRNL_OIL_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1996-04-01→2026-05-01 | 41 | 3-month percent return of the plmkrnl oil price (Pink Sheet). |
| WB_CMDTY_PLMKRNL_OIL_VOL_12M | wb_commodity | M | ? |  | 0 | 1996-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly plmkrnl oil price returns (Pink Sheet). |
| WB_CMDTY_PLMKRNL_OIL_YOY_PCT | wb_commodity | M | ? |  | 0 | 1997-01-01→2026-05-01 | 41 | Year-over-year percent change in the plmkrnl oil price (Pink Sheet). |
| WB_CMDTY_PLMKRNL_OIL_Z_36M | wb_commodity | M | ? |  | 0 | 1996-12-01→2026-05-01 | 41 | Z-score of the plmkrnl oil price versus its trailing 36-month history (Pink Shee |
| WB_CMDTY_PLYWOOD_LEVEL | wb_commodity | M | ? |  | 0 | 1979-01-01→2026-05-01 | 41 | plywood price level (World Bank Pink Sheet, monthly, global series broadcast to  |
| WB_CMDTY_PLYWOOD_MOM_PCT | wb_commodity | M | ? |  | 0 | 1979-02-01→2026-05-01 | 41 | Month-over-month percent change in the plywood price (Pink Sheet). |
| WB_CMDTY_PLYWOOD_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1980-01-01→2026-05-01 | 41 | 12-month percent return of the plywood price (Pink Sheet). |
| WB_CMDTY_PLYWOOD_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1979-04-01→2026-05-01 | 41 | 3-month percent return of the plywood price (Pink Sheet). |
| WB_CMDTY_PLYWOOD_VOL_12M | wb_commodity | M | ? |  | 0 | 1979-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly plywood price returns (Pink Sheet). |
| WB_CMDTY_PLYWOOD_YOY_PCT | wb_commodity | M | ? |  | 0 | 1980-01-01→2026-05-01 | 41 | Year-over-year percent change in the plywood price (Pink Sheet). |
| WB_CMDTY_PLYWOOD_Z_36M | wb_commodity | M | ? |  | 0 | 1979-12-01→2026-05-01 | 41 | Z-score of the plywood price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_POTASH_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | potash price level (World Bank Pink Sheet, monthly, global series broadcast to a |
| WB_CMDTY_POTASH_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the potash price (Pink Sheet). |
| WB_CMDTY_POTASH_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the potash price (Pink Sheet). |
| WB_CMDTY_POTASH_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the potash price (Pink Sheet). |
| WB_CMDTY_POTASH_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly potash price returns (Pink Sheet). |
| WB_CMDTY_POTASH_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the potash price (Pink Sheet). |
| WB_CMDTY_POTASH_Z_36M | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Z-score of the potash price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_RAPESEED_OIL_LEVEL | wb_commodity | M | ? |  | 0 | 2002-02-01→2026-05-01 | 41 | rapeseed oil price level (World Bank Pink Sheet, monthly, global series broadcas |
| WB_CMDTY_RAPESEED_OIL_MOM_PCT | wb_commodity | M | ? |  | 0 | 2002-03-01→2026-05-01 | 41 | Month-over-month percent change in the rapeseed oil price (Pink Sheet). |
| WB_CMDTY_RAPESEED_OIL_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 2003-02-01→2026-05-01 | 41 | 12-month percent return of the rapeseed oil price (Pink Sheet). |
| WB_CMDTY_RAPESEED_OIL_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 2002-05-01→2026-05-01 | 41 | 3-month percent return of the rapeseed oil price (Pink Sheet). |
| WB_CMDTY_RAPESEED_OIL_VOL_12M | wb_commodity | M | ? |  | 0 | 2002-08-01→2026-05-01 | 41 | 12-month rolling volatility of monthly rapeseed oil price returns (Pink Sheet). |
| WB_CMDTY_RAPESEED_OIL_YOY_PCT | wb_commodity | M | ? |  | 0 | 2003-02-01→2026-05-01 | 41 | Year-over-year percent change in the rapeseed oil price (Pink Sheet). |
| WB_CMDTY_RAPESEED_OIL_Z_36M | wb_commodity | M | ? |  | 0 | 2003-01-01→2026-05-01 | 41 | Z-score of the rapeseed oil price versus its trailing 36-month history (Pink She |
| WB_CMDTY_RICE_05_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | rice 05 price level (World Bank Pink Sheet, monthly, global series broadcast to  |
| WB_CMDTY_RICE_05_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the rice 05 price (Pink Sheet). |
| WB_CMDTY_RICE_05_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the rice 05 price (Pink Sheet). |
| WB_CMDTY_RICE_05_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the rice 05 price (Pink Sheet). |
| WB_CMDTY_RICE_05_VNM_LEVEL | wb_commodity | M | ? |  | 0 | 2003-12-01→2026-05-01 | 41 | rice 05 vnm price level (World Bank Pink Sheet, monthly, global series broadcast |
| WB_CMDTY_RICE_05_VNM_MOM_PCT | wb_commodity | M | ? |  | 0 | 2004-01-01→2026-05-01 | 41 | Month-over-month percent change in the rice 05 vnm price (Pink Sheet). |
| WB_CMDTY_RICE_05_VNM_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 2004-12-01→2026-05-01 | 41 | 12-month percent return of the rice 05 vnm price (Pink Sheet). |
| WB_CMDTY_RICE_05_VNM_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 2004-03-01→2026-05-01 | 41 | 3-month percent return of the rice 05 vnm price (Pink Sheet). |
| WB_CMDTY_RICE_05_VNM_VOL_12M | wb_commodity | M | ? |  | 0 | 2004-06-01→2026-05-01 | 41 | 12-month rolling volatility of monthly rice 05 vnm price returns (Pink Sheet). |
| WB_CMDTY_RICE_05_VNM_YOY_PCT | wb_commodity | M | ? |  | 0 | 2004-12-01→2026-05-01 | 41 | Year-over-year percent change in the rice 05 vnm price (Pink Sheet). |
| WB_CMDTY_RICE_05_VNM_Z_36M | wb_commodity | M | ? |  | 0 | 2004-11-01→2026-05-01 | 41 | Z-score of the rice 05 vnm price versus its trailing 36-month history (Pink Shee |
| WB_CMDTY_RICE_05_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly rice 05 price returns (Pink Sheet). |
| WB_CMDTY_RICE_05_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the rice 05 price (Pink Sheet). |
| WB_CMDTY_RICE_05_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the rice 05 price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_RICE_25_LEVEL | wb_commodity | M | ? |  | 0 | 1986-01-01→2026-05-01 | 41 | rice 25 price level (World Bank Pink Sheet, monthly, global series broadcast to  |
| WB_CMDTY_RICE_25_MOM_PCT | wb_commodity | M | ? |  | 0 | 1986-02-01→2026-05-01 | 41 | Month-over-month percent change in the rice 25 price (Pink Sheet). |
| WB_CMDTY_RICE_25_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1987-01-01→2026-05-01 | 41 | 12-month percent return of the rice 25 price (Pink Sheet). |
| WB_CMDTY_RICE_25_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1986-04-01→2026-05-01 | 41 | 3-month percent return of the rice 25 price (Pink Sheet). |
| WB_CMDTY_RICE_25_VOL_12M | wb_commodity | M | ? |  | 0 | 1986-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly rice 25 price returns (Pink Sheet). |
| WB_CMDTY_RICE_25_YOY_PCT | wb_commodity | M | ? |  | 0 | 1987-01-01→2026-05-01 | 41 | Year-over-year percent change in the rice 25 price (Pink Sheet). |
| WB_CMDTY_RICE_25_Z_36M | wb_commodity | M | ? |  | 0 | 1986-12-01→2026-05-01 | 41 | Z-score of the rice 25 price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_RICE_A1_LEVEL | wb_commodity | M | ? |  | 0 | 1986-01-01→2026-05-01 | 41 | rice a1 price level (World Bank Pink Sheet, monthly, global series broadcast to  |
| WB_CMDTY_RICE_A1_MOM_PCT | wb_commodity | M | ? |  | 0 | 1986-02-01→2026-05-01 | 41 | Month-over-month percent change in the rice a1 price (Pink Sheet). |
| WB_CMDTY_RICE_A1_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1987-01-01→2026-05-01 | 41 | 12-month percent return of the rice a1 price (Pink Sheet). |
| WB_CMDTY_RICE_A1_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1986-04-01→2026-05-01 | 41 | 3-month percent return of the rice a1 price (Pink Sheet). |
| WB_CMDTY_RICE_A1_VOL_12M | wb_commodity | M | ? |  | 0 | 1986-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly rice a1 price returns (Pink Sheet). |
| WB_CMDTY_RICE_A1_YOY_PCT | wb_commodity | M | ? |  | 0 | 1987-01-01→2026-05-01 | 41 | Year-over-year percent change in the rice a1 price (Pink Sheet). |
| WB_CMDTY_RICE_A1_Z_36M | wb_commodity | M | ? |  | 0 | 1986-12-01→2026-05-01 | 41 | Z-score of the rice a1 price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_RUBBER1_MYSG_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | rubber1 mysg price level (World Bank Pink Sheet, monthly, global series broadcas |
| WB_CMDTY_RUBBER1_MYSG_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the rubber1 mysg price (Pink Sheet). |
| WB_CMDTY_RUBBER1_MYSG_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the rubber1 mysg price (Pink Sheet). |
| WB_CMDTY_RUBBER1_MYSG_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the rubber1 mysg price (Pink Sheet). |
| WB_CMDTY_RUBBER1_MYSG_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly rubber1 mysg price returns (Pink Sheet). |
| WB_CMDTY_RUBBER1_MYSG_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the rubber1 mysg price (Pink Sheet). |
| WB_CMDTY_RUBBER1_MYSG_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the rubber1 mysg price versus its trailing 36-month history (Pink She |
| WB_CMDTY_RUBBER_TSR20_LEVEL | wb_commodity | M | ? |  | 0 | 1999-01-01→2026-05-01 | 41 | rubber tsr20 price level (World Bank Pink Sheet, monthly, global series broadcas |
| WB_CMDTY_RUBBER_TSR20_MOM_PCT | wb_commodity | M | ? |  | 0 | 1999-02-01→2026-05-01 | 41 | Month-over-month percent change in the rubber tsr20 price (Pink Sheet). |
| WB_CMDTY_RUBBER_TSR20_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 2000-01-01→2026-05-01 | 41 | 12-month percent return of the rubber tsr20 price (Pink Sheet). |
| WB_CMDTY_RUBBER_TSR20_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1999-04-01→2026-05-01 | 41 | 3-month percent return of the rubber tsr20 price (Pink Sheet). |
| WB_CMDTY_RUBBER_TSR20_VOL_12M | wb_commodity | M | ? |  | 0 | 1999-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly rubber tsr20 price returns (Pink Sheet). |
| WB_CMDTY_RUBBER_TSR20_YOY_PCT | wb_commodity | M | ? |  | 0 | 2000-01-01→2026-05-01 | 41 | Year-over-year percent change in the rubber tsr20 price (Pink Sheet). |
| WB_CMDTY_RUBBER_TSR20_Z_36M | wb_commodity | M | ? |  | 0 | 1999-12-01→2026-05-01 | 41 | Z-score of the rubber tsr20 price versus its trailing 36-month history (Pink She |
| WB_CMDTY_SAWNWD_CMR_LEVEL | wb_commodity | M | ? |  | 0 | 1970-01-01→2026-05-01 | 41 | sawnwd cmr price level (World Bank Pink Sheet, monthly, global series broadcast  |
| WB_CMDTY_SAWNWD_CMR_MOM_PCT | wb_commodity | M | ? |  | 0 | 1970-02-01→2026-05-01 | 41 | Month-over-month percent change in the sawnwd cmr price (Pink Sheet). |
| WB_CMDTY_SAWNWD_CMR_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1980-01-01→2026-05-01 | 41 | 12-month percent return of the sawnwd cmr price (Pink Sheet). |
| WB_CMDTY_SAWNWD_CMR_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1970-04-01→2026-05-01 | 41 | 3-month percent return of the sawnwd cmr price (Pink Sheet). |
| WB_CMDTY_SAWNWD_CMR_VOL_12M | wb_commodity | M | ? |  | 0 | 1970-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly sawnwd cmr price returns (Pink Sheet). |
| WB_CMDTY_SAWNWD_CMR_YOY_PCT | wb_commodity | M | ? |  | 0 | 1980-01-01→2026-05-01 | 41 | Year-over-year percent change in the sawnwd cmr price (Pink Sheet). |
| WB_CMDTY_SAWNWD_CMR_Z_36M | wb_commodity | M | ? |  | 0 | 1980-01-01→2026-05-01 | 41 | Z-score of the sawnwd cmr price versus its trailing 36-month history (Pink Sheet |
| WB_CMDTY_SAWNWD_MYS_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | sawnwd mys price level (World Bank Pink Sheet, monthly, global series broadcast  |
| WB_CMDTY_SAWNWD_MYS_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the sawnwd mys price (Pink Sheet). |
| WB_CMDTY_SAWNWD_MYS_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the sawnwd mys price (Pink Sheet). |
| WB_CMDTY_SAWNWD_MYS_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the sawnwd mys price (Pink Sheet). |
| WB_CMDTY_SAWNWD_MYS_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly sawnwd mys price returns (Pink Sheet). |
| WB_CMDTY_SAWNWD_MYS_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the sawnwd mys price (Pink Sheet). |
| WB_CMDTY_SAWNWD_MYS_Z_36M | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Z-score of the sawnwd mys price versus its trailing 36-month history (Pink Sheet |
| WB_CMDTY_SHRIMP_MEX_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2023-10-01 | 984 ⚠STALE | shrimp mex price level (World Bank Pink Sheet, monthly, global series broadcast  |
| WB_CMDTY_SHRIMP_MEX_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2023-10-01 | 984 ⚠STALE | Month-over-month percent change in the shrimp mex price (Pink Sheet). |
| WB_CMDTY_SHRIMP_MEX_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2023-10-01 | 984 ⚠STALE | 12-month percent return of the shrimp mex price (Pink Sheet). |
| WB_CMDTY_SHRIMP_MEX_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2023-10-01 | 984 ⚠STALE | 3-month percent return of the shrimp mex price (Pink Sheet). |
| WB_CMDTY_SHRIMP_MEX_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2023-10-01 | 984 ⚠STALE | 12-month rolling volatility of monthly shrimp mex price returns (Pink Sheet). |
| WB_CMDTY_SHRIMP_MEX_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2023-10-01 | 984 ⚠STALE | Year-over-year percent change in the shrimp mex price (Pink Sheet). |
| WB_CMDTY_SHRIMP_MEX_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2023-10-01 | 984 ⚠STALE | Z-score of the shrimp mex price versus its trailing 36-month history (Pink Sheet |
| WB_CMDTY_SILVER_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | silver price level (World Bank Pink Sheet, monthly, global series broadcast to a |
| WB_CMDTY_SILVER_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the silver price (Pink Sheet). |
| WB_CMDTY_SILVER_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the silver price (Pink Sheet). |
| WB_CMDTY_SILVER_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the silver price (Pink Sheet). |
| WB_CMDTY_SILVER_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly silver price returns (Pink Sheet). |
| WB_CMDTY_SILVER_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the silver price (Pink Sheet). |
| WB_CMDTY_SILVER_Z_36M | wb_commodity | M | ? |  | 0 | 1961-11-01→2026-05-01 | 41 | Z-score of the silver price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_SORGHUM_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2020-08-01 | 2140 ⚠STALE | sorghum price level (World Bank Pink Sheet, monthly, global series broadcast to  |
| WB_CMDTY_SORGHUM_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2020-08-01 | 2140 ⚠STALE | Month-over-month percent change in the sorghum price (Pink Sheet). |
| WB_CMDTY_SORGHUM_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2020-08-01 | 2140 ⚠STALE | 12-month percent return of the sorghum price (Pink Sheet). |
| WB_CMDTY_SORGHUM_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2020-08-01 | 2140 ⚠STALE | 3-month percent return of the sorghum price (Pink Sheet). |
| WB_CMDTY_SORGHUM_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2020-08-01 | 2140 ⚠STALE | 12-month rolling volatility of monthly sorghum price returns (Pink Sheet). |
| WB_CMDTY_SORGHUM_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2020-08-01 | 2140 ⚠STALE | Year-over-year percent change in the sorghum price (Pink Sheet). |
| WB_CMDTY_SORGHUM_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2020-08-01 | 2140 ⚠STALE | Z-score of the sorghum price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_SOYBEANS_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | soybeans price level (World Bank Pink Sheet, monthly, global series broadcast to |
| WB_CMDTY_SOYBEANS_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the soybeans price (Pink Sheet). |
| WB_CMDTY_SOYBEANS_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the soybeans price (Pink Sheet). |
| WB_CMDTY_SOYBEANS_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the soybeans price (Pink Sheet). |
| WB_CMDTY_SOYBEANS_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly soybeans price returns (Pink Sheet). |
| WB_CMDTY_SOYBEANS_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the soybeans price (Pink Sheet). |
| WB_CMDTY_SOYBEANS_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the soybeans price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_SOYBEAN_MEAL_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | soybean meal price level (World Bank Pink Sheet, monthly, global series broadcas |
| WB_CMDTY_SOYBEAN_MEAL_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the soybean meal price (Pink Sheet). |
| WB_CMDTY_SOYBEAN_MEAL_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the soybean meal price (Pink Sheet). |
| WB_CMDTY_SOYBEAN_MEAL_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the soybean meal price (Pink Sheet). |
| WB_CMDTY_SOYBEAN_MEAL_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly soybean meal price returns (Pink Sheet). |
| WB_CMDTY_SOYBEAN_MEAL_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the soybean meal price (Pink Sheet). |
| WB_CMDTY_SOYBEAN_MEAL_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the soybean meal price versus its trailing 36-month history (Pink She |
| WB_CMDTY_SOYBEAN_OIL_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | soybean oil price level (World Bank Pink Sheet, monthly, global series broadcast |
| WB_CMDTY_SOYBEAN_OIL_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the soybean oil price (Pink Sheet). |
| WB_CMDTY_SOYBEAN_OIL_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the soybean oil price (Pink Sheet). |
| WB_CMDTY_SOYBEAN_OIL_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the soybean oil price (Pink Sheet). |
| WB_CMDTY_SOYBEAN_OIL_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly soybean oil price returns (Pink Sheet). |
| WB_CMDTY_SOYBEAN_OIL_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the soybean oil price (Pink Sheet). |
| WB_CMDTY_SOYBEAN_OIL_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the soybean oil price versus its trailing 36-month history (Pink Shee |
| WB_CMDTY_SUGAR_EU_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | sugar (EU) price level (World Bank Pink Sheet, monthly, global series broadcast  |
| WB_CMDTY_SUGAR_EU_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the sugar (EU) price (Pink Sheet). |
| WB_CMDTY_SUGAR_EU_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the sugar (EU) price (Pink Sheet). |
| WB_CMDTY_SUGAR_EU_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the sugar (EU) price (Pink Sheet). |
| WB_CMDTY_SUGAR_EU_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly sugar (EU) price returns (Pink Sheet). |
| WB_CMDTY_SUGAR_EU_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the sugar (EU) price (Pink Sheet). |
| WB_CMDTY_SUGAR_EU_Z_36M | wb_commodity | M | ? |  | 0 | 1962-01-01→2026-05-01 | 41 | Z-score of the sugar (EU) price versus its trailing 36-month history (Pink Sheet |
| WB_CMDTY_SUGAR_US_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | sugar (US) price level (World Bank Pink Sheet, monthly, global series broadcast  |
| WB_CMDTY_SUGAR_US_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the sugar (US) price (Pink Sheet). |
| WB_CMDTY_SUGAR_US_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the sugar (US) price (Pink Sheet). |
| WB_CMDTY_SUGAR_US_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the sugar (US) price (Pink Sheet). |
| WB_CMDTY_SUGAR_US_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly sugar (US) price returns (Pink Sheet). |
| WB_CMDTY_SUGAR_US_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the sugar (US) price (Pink Sheet). |
| WB_CMDTY_SUGAR_US_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the sugar (US) price versus its trailing 36-month history (Pink Sheet |
| WB_CMDTY_SUGAR_WLD_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | sugar wld price level (World Bank Pink Sheet, monthly, global series broadcast t |
| WB_CMDTY_SUGAR_WLD_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the sugar wld price (Pink Sheet). |
| WB_CMDTY_SUGAR_WLD_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the sugar wld price (Pink Sheet). |
| WB_CMDTY_SUGAR_WLD_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the sugar wld price (Pink Sheet). |
| WB_CMDTY_SUGAR_WLD_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly sugar wld price returns (Pink Sheet). |
| WB_CMDTY_SUGAR_WLD_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the sugar wld price (Pink Sheet). |
| WB_CMDTY_SUGAR_WLD_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the sugar wld price versus its trailing 36-month history (Pink Sheet) |
| WB_CMDTY_SUNFLOWER_OIL_LEVEL | wb_commodity | M | ? |  | 0 | 2002-02-01→2026-05-01 | 41 | sunflower oil price level (World Bank Pink Sheet, monthly, global series broadca |
| WB_CMDTY_SUNFLOWER_OIL_MOM_PCT | wb_commodity | M | ? |  | 0 | 2002-03-01→2026-05-01 | 41 | Month-over-month percent change in the sunflower oil price (Pink Sheet). |
| WB_CMDTY_SUNFLOWER_OIL_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 2003-07-01→2026-05-01 | 41 | 12-month percent return of the sunflower oil price (Pink Sheet). |
| WB_CMDTY_SUNFLOWER_OIL_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 2002-05-01→2026-05-01 | 41 | 3-month percent return of the sunflower oil price (Pink Sheet). |
| WB_CMDTY_SUNFLOWER_OIL_VOL_12M | wb_commodity | M | ? |  | 0 | 2003-01-01→2026-05-01 | 41 | 12-month rolling volatility of monthly sunflower oil price returns (Pink Sheet). |
| WB_CMDTY_SUNFLOWER_OIL_YOY_PCT | wb_commodity | M | ? |  | 0 | 2003-07-01→2026-05-01 | 41 | Year-over-year percent change in the sunflower oil price (Pink Sheet). |
| WB_CMDTY_SUNFLOWER_OIL_Z_36M | wb_commodity | M | ? |  | 0 | 2003-06-01→2026-05-01 | 41 | Z-score of the sunflower oil price versus its trailing 36-month history (Pink Sh |
| WB_CMDTY_TEA_AVG_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | tea avg price level (World Bank Pink Sheet, monthly, global series broadcast to  |
| WB_CMDTY_TEA_AVG_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the tea avg price (Pink Sheet). |
| WB_CMDTY_TEA_AVG_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the tea avg price (Pink Sheet). |
| WB_CMDTY_TEA_AVG_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the tea avg price (Pink Sheet). |
| WB_CMDTY_TEA_AVG_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly tea avg price returns (Pink Sheet). |
| WB_CMDTY_TEA_AVG_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the tea avg price (Pink Sheet). |
| WB_CMDTY_TEA_AVG_Z_36M | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Z-score of the tea avg price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_TEA_COLOMBO_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | tea colombo price level (World Bank Pink Sheet, monthly, global series broadcast |
| WB_CMDTY_TEA_COLOMBO_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the tea colombo price (Pink Sheet). |
| WB_CMDTY_TEA_COLOMBO_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the tea colombo price (Pink Sheet). |
| WB_CMDTY_TEA_COLOMBO_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the tea colombo price (Pink Sheet). |
| WB_CMDTY_TEA_COLOMBO_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly tea colombo price returns (Pink Sheet). |
| WB_CMDTY_TEA_COLOMBO_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the tea colombo price (Pink Sheet). |
| WB_CMDTY_TEA_COLOMBO_Z_36M | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Z-score of the tea colombo price versus its trailing 36-month history (Pink Shee |
| WB_CMDTY_TEA_KOLKATA_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | tea kolkata price level (World Bank Pink Sheet, monthly, global series broadcast |
| WB_CMDTY_TEA_KOLKATA_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the tea kolkata price (Pink Sheet). |
| WB_CMDTY_TEA_KOLKATA_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the tea kolkata price (Pink Sheet). |
| WB_CMDTY_TEA_KOLKATA_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the tea kolkata price (Pink Sheet). |
| WB_CMDTY_TEA_KOLKATA_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly tea kolkata price returns (Pink Sheet). |
| WB_CMDTY_TEA_KOLKATA_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the tea kolkata price (Pink Sheet). |
| WB_CMDTY_TEA_KOLKATA_Z_36M | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Z-score of the tea kolkata price versus its trailing 36-month history (Pink Shee |
| WB_CMDTY_TEA_MOMBASA_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | tea mombasa price level (World Bank Pink Sheet, monthly, global series broadcast |
| WB_CMDTY_TEA_MOMBASA_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the tea mombasa price (Pink Sheet). |
| WB_CMDTY_TEA_MOMBASA_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the tea mombasa price (Pink Sheet). |
| WB_CMDTY_TEA_MOMBASA_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the tea mombasa price (Pink Sheet). |
| WB_CMDTY_TEA_MOMBASA_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly tea mombasa price returns (Pink Sheet). |
| WB_CMDTY_TEA_MOMBASA_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the tea mombasa price (Pink Sheet). |
| WB_CMDTY_TEA_MOMBASA_Z_36M | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Z-score of the tea mombasa price versus its trailing 36-month history (Pink Shee |
| WB_CMDTY_TIN_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | tin price level (World Bank Pink Sheet, monthly, global series broadcast to all  |
| WB_CMDTY_TIN_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the tin price (Pink Sheet). |
| WB_CMDTY_TIN_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the tin price (Pink Sheet). |
| WB_CMDTY_TIN_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the tin price (Pink Sheet). |
| WB_CMDTY_TIN_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly tin price returns (Pink Sheet). |
| WB_CMDTY_TIN_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the tin price (Pink Sheet). |
| WB_CMDTY_TIN_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the tin price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_TOBAC_US_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-03-01 | 102 | tobac (US) price level (World Bank Pink Sheet, monthly, global series broadcast  |
| WB_CMDTY_TOBAC_US_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-03-01 | 102 | Month-over-month percent change in the tobac (US) price (Pink Sheet). |
| WB_CMDTY_TOBAC_US_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-03-01 | 102 | 12-month percent return of the tobac (US) price (Pink Sheet). |
| WB_CMDTY_TOBAC_US_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-03-01 | 102 | 3-month percent return of the tobac (US) price (Pink Sheet). |
| WB_CMDTY_TOBAC_US_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-03-01 | 102 | 12-month rolling volatility of monthly tobac (US) price returns (Pink Sheet). |
| WB_CMDTY_TOBAC_US_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-03-01 | 102 | Year-over-year percent change in the tobac (US) price (Pink Sheet). |
| WB_CMDTY_TOBAC_US_Z_36M | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-03-01 | 102 | Z-score of the tobac (US) price versus its trailing 36-month history (Pink Sheet |
| WB_CMDTY_TSP_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | TSP price level (World Bank Pink Sheet, monthly, global series broadcast to all  |
| WB_CMDTY_TSP_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the TSP price (Pink Sheet). |
| WB_CMDTY_TSP_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the TSP price (Pink Sheet). |
| WB_CMDTY_TSP_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the TSP price (Pink Sheet). |
| WB_CMDTY_TSP_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly TSP price returns (Pink Sheet). |
| WB_CMDTY_TSP_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the TSP price (Pink Sheet). |
| WB_CMDTY_TSP_Z_36M | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Z-score of the TSP price versus its trailing 36-month history (Pink Sheet). |
| WB_CMDTY_UREA_EE_BULK_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | urea ee bulk price level (World Bank Pink Sheet, monthly, global series broadcas |
| WB_CMDTY_UREA_EE_BULK_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the urea ee bulk price (Pink Sheet). |
| WB_CMDTY_UREA_EE_BULK_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the urea ee bulk price (Pink Sheet). |
| WB_CMDTY_UREA_EE_BULK_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the urea ee bulk price (Pink Sheet). |
| WB_CMDTY_UREA_EE_BULK_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly urea ee bulk price returns (Pink Sheet). |
| WB_CMDTY_UREA_EE_BULK_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the urea ee bulk price (Pink Sheet). |
| WB_CMDTY_UREA_EE_BULK_Z_36M | wb_commodity | M | ? |  | 0 | 1964-01-01→2026-05-01 | 41 | Z-score of the urea ee bulk price versus its trailing 36-month history (Pink She |
| WB_CMDTY_WHEAT_US_HRW_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | wheat (US) hrw price level (World Bank Pink Sheet, monthly, global series broadc |
| WB_CMDTY_WHEAT_US_HRW_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the wheat (US) hrw price (Pink Sheet). |
| WB_CMDTY_WHEAT_US_HRW_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the wheat (US) hrw price (Pink Sheet). |
| WB_CMDTY_WHEAT_US_HRW_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the wheat (US) hrw price (Pink Sheet). |
| WB_CMDTY_WHEAT_US_HRW_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly wheat (US) hrw price returns (Pink Sheet) |
| WB_CMDTY_WHEAT_US_HRW_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the wheat (US) hrw price (Pink Sheet). |
| WB_CMDTY_WHEAT_US_HRW_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the wheat (US) hrw price versus its trailing 36-month history (Pink S |
| WB_CMDTY_WHEAT_US_SRW_LEVEL | wb_commodity | M | ? |  | 0 | 1979-01-01→2026-05-01 | 41 | wheat (US) srw price level (World Bank Pink Sheet, monthly, global series broadc |
| WB_CMDTY_WHEAT_US_SRW_MOM_PCT | wb_commodity | M | ? |  | 0 | 1979-02-01→2026-05-01 | 41 | Month-over-month percent change in the wheat (US) srw price (Pink Sheet). |
| WB_CMDTY_WHEAT_US_SRW_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1980-01-01→2026-05-01 | 41 | 12-month percent return of the wheat (US) srw price (Pink Sheet). |
| WB_CMDTY_WHEAT_US_SRW_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1979-04-01→2026-05-01 | 41 | 3-month percent return of the wheat (US) srw price (Pink Sheet). |
| WB_CMDTY_WHEAT_US_SRW_VOL_12M | wb_commodity | M | ? |  | 0 | 1979-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly wheat (US) srw price returns (Pink Sheet) |
| WB_CMDTY_WHEAT_US_SRW_YOY_PCT | wb_commodity | M | ? |  | 0 | 1980-01-01→2026-05-01 | 41 | Year-over-year percent change in the wheat (US) srw price (Pink Sheet). |
| WB_CMDTY_WHEAT_US_SRW_Z_36M | wb_commodity | M | ? |  | 0 | 1979-12-01→2026-05-01 | 41 | Z-score of the wheat (US) srw price versus its trailing 36-month history (Pink S |
| WB_CMDTY_ZINC_LEVEL | wb_commodity | M | ? |  | 0 | 1960-01-01→2026-05-01 | 41 | zinc price level (World Bank Pink Sheet, monthly, global series broadcast to all |
| WB_CMDTY_ZINC_MOM_PCT | wb_commodity | M | ? |  | 0 | 1960-02-01→2026-05-01 | 41 | Month-over-month percent change in the zinc price (Pink Sheet). |
| WB_CMDTY_ZINC_RET_12M_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | 12-month percent return of the zinc price (Pink Sheet). |
| WB_CMDTY_ZINC_RET_3M_PCT | wb_commodity | M | ? |  | 0 | 1960-04-01→2026-05-01 | 41 | 3-month percent return of the zinc price (Pink Sheet). |
| WB_CMDTY_ZINC_VOL_12M | wb_commodity | M | ? |  | 0 | 1960-07-01→2026-05-01 | 41 | 12-month rolling volatility of monthly zinc price returns (Pink Sheet). |
| WB_CMDTY_ZINC_YOY_PCT | wb_commodity | M | ? |  | 0 | 1961-01-01→2026-05-01 | 41 | Year-over-year percent change in the zinc price (Pink Sheet). |
| WB_CMDTY_ZINC_Z_36M | wb_commodity | M | ? |  | 0 | 1960-12-01→2026-05-01 | 41 | Z-score of the zinc price versus its trailing 36-month history (Pink Sheet). |

## predmkt_signals_daily  (14 variables)

| variable | source | freq | sign | role | countries | range | fresh(d) | definition |
|---|---|---|---|---|---|---|---|---|
| cpi_nowcast_core_next | predmkt_signal | D | ? |  | 1 | 2026-06-11→2026-06-11 | 0 | Prediction-market implied nowcast of the next US core CPI print. |
| cpi_nowcast_yoy_next | predmkt_signal | D | ? |  | 1 | 2026-06-11→2026-06-11 | 0 | Prediction-market implied nowcast of the next US CPI YoY print. |
| fed_cut_count_expectation | predmkt_signal | D | ? |  | 1 | 2026-06-11→2026-06-11 | 0 | Prediction-market implied expected number of Fed rate cuts over the contract hor |
| fed_decision_distribution_next | predmkt_signal | D | ? |  | 1 | 2026-06-11→2026-06-11 | 0 | Prediction-market implied distribution over the next FOMC decision (cut/hold/hik |
| hormuz_disruption_prob_90d | predmkt_signal | D | ? |  | 1 | 2026-06-11→2026-06-11 | 0 | Prediction-market implied probability of a Strait of Hormuz shipping disruption  |
| oil_shock_prob_30d | predmkt_signal | D | ? |  | 1 | 2026-06-11→2026-06-11 | 0 | Prediction-market implied probability of an oil price shock within 30 days. |
| predmkt_country_opportunity_composite | predmkt_signal | D | ? |  | 19 | 2026-06-11→2026-06-11 | 0 | ASADO composite of prediction-market signals mapped to country upside (>0 = impl |
| predmkt_country_risk_composite | predmkt_signal | D | ? |  | 19 | 2026-06-11→2026-06-11 | 0 | ASADO composite of prediction-market signals mapped to country downside risk (>0 |
| recession_prob_12m | predmkt_signal | D | ? |  | 1 | 2026-06-11→2026-06-11 | 0 | Prediction-market implied probability of a US recession within 12 months. |
| regional_conflict_premium_eastern_europe | predmkt_signal | D | ? |  | 1 | 2026-06-11→2026-06-11 | 0 | Composite prediction-market conflict premium for Eastern Europe. |
| regional_conflict_premium_middle_east | predmkt_signal | D | ? |  | 1 | 2026-06-11→2026-06-11 | 0 | Composite prediction-market conflict premium for the Middle East region. |
| regional_conflict_premium_pacific | predmkt_signal | D | ? |  | 1 | 2026-06-11→2026-06-11 | 0 | Composite prediction-market conflict premium for the Pacific region (Taiwan-stra |
| tariff_intensity_by_country | predmkt_signal | D | ? |  | 3 | 2026-06-11→2026-06-11 | 0 | Prediction-market implied tariff/trade-restriction intensity mapped to countries |
| unemployment_nowcast_next | predmkt_signal | D | ? |  | 1 | 2026-06-11→2026-06-11 | 0 | Prediction-market implied nowcast of the next US unemployment rate print. |

## graph_features_daily  (7 variables)

| variable | source | freq | sign | role | countries | range | fresh(d) | definition |
|---|---|---|---|---|---|---|---|---|
| GRAPH_BANK_NBR_RET_GAP_21D | graph | D | ? |  | 21 | 2000-01-31→2026-06-10 | 1 | Banking-exposure-weighted neighbor 21-day return minus own 21-day return (HAS_BA |
| GRAPH_BANK_NBR_RET_GAP_63D | graph | D | ? |  | 21 | 2000-03-29→2026-06-10 | 1 | Banking-exposure-weighted neighbor 63-day return minus own 63-day return. |
| GRAPH_NBR_DRAWDOWN_COUNT | graph | D | ? |  | 31 | 2000-03-24→2026-06-10 | 1 | Edge-weighted count of neighbor countries in greater than 10 percent drawdown (c |
| GRAPH_PORT_HOLDER_STRESS_21D | graph | D | ? |  | 31 | 2000-03-24→2026-06-10 | 1 | HOLDS_PORTFOLIO-weighted holder-country drawdown over 21 days — stress among the |
| GRAPH_TRADE_NBR_RET_GAP_21D | graph | D | ? |  | 31 | 2000-01-31→2026-06-10 | 1 | Trade-weighted neighbor 21-day return minus own 21-day return (TRADES_WITH edge  |
| GRAPH_TRADE_NBR_RET_GAP_63D | graph | D | ? |  | 31 | 2000-03-29→2026-06-10 | 1 | Trade-weighted neighbor 63-day return minus own 63-day return. |
| GRAPH_TWOHOP_TRADE_GAP_21D | graph | D | ? |  | 31 | 2000-01-31→2026-06-10 | 1 | Two-hop trade propagation gap — middle trading partner repriced (/z/>1) while th |

## gdelt_raw_daily  (35 variables)

| variable | source | freq | sign | role | countries | range | fresh(d) | definition |
|---|---|---|---|---|---|---|---|---|
| attention_shock | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| country_location_mentions | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| country_news_attention | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| country_news_risk | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| country_news_risk_raw | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| country_news_sentiment | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| country_news_sentiment_raw | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| country_news_sentiment_x_attention | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| days_since_prior_observation | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| foreign_n_articles | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| foreign_tone | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| foreign_tone_z | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| gkg_fetch_share | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| local_attention_share | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| local_attention_share_z | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| local_n_articles | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| local_source_total_articles | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| local_tone | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| local_tone_z | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| n_articles | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| negative_mean | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| polarity_mean | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| positive_mean | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| sentiment_x_attention_raw | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| source_resolution_rate | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| tone_dispersion | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| tone_dispersion_z | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| tone_mean | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| tone_p10 | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| tone_p50 | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| tone_p90 | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| tone_wavg_wordcount | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| total_theme_mentions | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| total_word_count | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
| unknown_source_n_articles | gdelt_raw | D | ? |  | 249 | 2015-02-18→2026-06-11 | 0 |  |
