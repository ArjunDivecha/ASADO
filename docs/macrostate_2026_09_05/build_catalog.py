"""Build source-qualified economic candidate map from the saved broad live audit.
No model fitting, no production writes, no newly collected data.
"""
import pandas as pd, pathlib, re, json
P=pathlib.Path(__file__).parent
x=pd.read_csv(P/'universe_inventory.csv').fillna('');reg=pd.read_csv(P/'registry.csv').fillna('').drop_duplicates('variable').set_index('variable')
target=pd.read_csv(P/'targets.csv');T2=set(target.country.unique())
families=['Growth cycle','Monetary policy impulse','Real monetary tightness','Inflation regime','Private credit cycle','External vulnerability','Sovereign fiscal stress','Banking fragility','Policy backstop capacity','Capital flows positioning','Global risk','Terms of trade commodity impulse','Valuation expected return','Market trend fragility','Institutional structural capacity','Cross-country contagion']
# Every source family was inventoried before this economic selection. Labels describe
# economic state direction; they do NOT pre-impose a return-predictive sign.
def map_family(t,v):
 if t=='t2_raw':
  if v in ['GDP','LT Growth']:return [1]
  if v=='Inflation':return [4,3]
  if v in ['10Yr Bond','10Yr Bond 12']:return [2,7]
  if v in ['Current Account','REER','Currency','Currency 12','Currency Vol']:return [6,14] if 'Currency' in v else [6]
  if v in ['Debt to GDP','Budget Def','Bloom Country Risk']:return [7]
  if v in ['Gold','Gold 12','Copper','Copper 12','Oil','Oil 12','Agriculture','Agriculture 12']:return [12]
  if v in ['1MTR','3MTR','12MTR','12-1MTR','P2P','120MA','120MA Signal','PX_LAST','RSI14','20 Day Vol','360 Day Vol','Advance Decline','Tot Return Index']:return [14]
  if v in ['Mcap Weights','MCAP','MCAP Adj']:return [10]
  return [13]
 if t=='external_factors':
  if 'GPR' in v or v=='EPU':return [11]
  if 'Credit' in v or 'Property' in v:return [5]
  if any(z in v for z in ['Current_Account','FX_Reserves','Import_Cover','External_Debt','FDI','REER']):return [6]
  if 'Inflation' in v:return [4]
  if 'Govt_Debt' in v:return [7]
  if v in ['OECD_CLI','WB_GDP_Growth_Real','WB_Unemployment']:return [1]
  return [15]
 if t=='extended_factors':
  if v.startswith('ECB_'):return [] # all 20 FX identities inventoried; t2 FX gives target basis
  if v.startswith('FRED_'):return [11]
  if v=='BIS_Policy_Rate':return [2,3]
  if v=='BIS_DSR_Private':return [5]
  if v.startswith('OECD_') or v.startswith('ILO_'):return [1]
  if v.startswith('FAO_') or v.startswith('EIA_'):return [12]
  return [15]
 if t=='imf_factors':
  if any(z in v for z in ['CPI','Import_Price','WEO_Inflation']):return [4]
  if any(z in v for z in ['Money_Market','TBill','Discount']):return [2,3]
  if 'Bond_Yield' in v:return [7]
  if 'Debt' in v:return [7]
  if any(z in v for z in ['BOP','CA_GDP','XRate']):return [6]
  if 'Population' in v:return [15]
  return [1]
 if t=='macrostructure_factors':
  if any(z in v for z in ['Bank_Liq','Bank_Net','NPL','Bank_Capital']):return [8]
  if any(z in v for z in ['Swap_Line','Policy_Backstop','CentralBank','Reserve_Adequacy']):return [9]
  if any(z in v for z in ['Pension','Insurance','Household','Investor_Base','US_Holder']):return [15]
  if any(z in v for z in ['Foreign','External']):return [6,7]
  return [7,9]
 if t=='bloomberg_factors':
  if any(z in v for z in ['PMI','ECFC_GDP','M2']):return [1]
  if 'ECFC_CPI' in v:return [4]
  if any(z in v for z in ['WIRP','OIS','Govt_Bond_2Y']):return [2]
  if v.startswith('MS_'):return [10]
  return [7]
 if t=='consensus_daily' or t=='consensus_signals' or t in ['weo_vintages','weo_revisions']:return [4] if 'CPI' in v else [1]
 if t in ['eco_surprise_monthly','eco_surprise_signals','release_events_signals']:return [4] if any(z in v for z in ['CPI','INFL','PPI']) else [1]
 if t in ['etf_flows','etf_flow_signals','foreign_flows_daily']:return [10]
 if t=='market_implied_daily' or t=='market_implied_signals':return [6] if v.startswith('FX') else [12] if v.startswith('CMD') else [11]
 if t=='sovereign_daily' or t=='sovereign_signals':return [2,3] if '2Y' in v or '2S10' in v else [7]
 if t in ['sov_ratings_monthly']:return [7]
 if t=='valuation_monthly':return [13]
 if t=='graph_features_pit_daily':return [16]
 if t=='demographics_dip':return [15]
 return []
paths={'t2_raw':'Data/work/t2/T2 Master.xlsx','external_factors':'Data/processed/external_factors_panel.parquet','extended_factors':'Data/processed/extended_factors_panel.parquet','imf_factors':'Data/processed/imf_factors_panel.parquet','macrostructure_factors':'Data/processed/macrostructure_panel.parquet','bloomberg_factors':'Data/processed/bloomberg_factors_panel.parquet','consensus_daily':'Data/work/loop/consensus_daily.parquet','consensus_signals':'Data/work/loop/consensus_daily.parquet','eco_surprise_monthly':'Data/work/loop/eco_surprise_monthly.parquet','eco_surprise_signals':'Data/work/loop/eco_surprise_monthly.parquet','release_events_signals':'Data/work/loop/release_events.parquet','etf_flows':'Data/work/loop/etf_flows.parquet','etf_flow_signals':'Data/work/loop/etf_flows.parquet','foreign_flows_daily':'Data/work/loop/foreign_flows.parquet','market_implied_daily':'Data/work/loop/market_implied_daily.parquet','market_implied_signals':'Data/work/loop/market_implied_daily.parquet','sovereign_daily':'Data/work/loop/sovereign_daily.parquet','sovereign_signals':'Data/work/loop/sovereign_daily.parquet','sov_ratings_monthly':'Data/work/loop/sov_ratings_monthly.parquet','valuation_monthly':'Data/work/loop/valuation_monthly.parquet','weo_vintages':'Data/work/loop/weo_vintages.parquet','weo_revisions':'Data/work/loop/weo_vintages.parquet','graph_features_pit_daily':'Data/loop/graph_edge_vintages.parquet','demographics_dip':'Data/asado.duckdb'}
rows=[]
for _,r in x.iterrows():
 t,v=r.table,r.variable;fs=map_family(t,v)
 if not fs:continue
 native=str(reg.loc[v,'native_frequency']) if v in reg.index else ''
 if not native:native='daily' if 'daily' in t or t in ['market_implied_signals','sovereign_signals','etf_flows','etf_flow_signals','release_events_signals'] else 'semiannual vintage' if t.startswith('weo') else 'monthly'
 pit='QUARANTINE_LATEST_VINTAGE';why='Reference-period latest histories; publication lag cannot undo revisions. Existing archives would need independent vintage evidence.';availability='Not established from current rows';revision='Latest values may overwrite history';clean='Rebuild raw-source transforms with cutoff and original missingness; do not admit normalized aliases automatically.'
 if t.startswith('consensus'):
  pit='CONDITIONAL_DATED_HISTORY';why='Year-specific ECFC historical daily forecasts preserve economic target-year identity. Vendor histories can be corrected; first-publication and immutable snapshot proof not yet tested.';availability='Daily vendor observation date + conservative next decision boundary; month-end derived rows include unfinished current month';revision='Collector keep-last dedupe can overwrite old dates; no immutable original-release flag';clean='Within target-year month-end last then 1m/3m differences; blend current and next target years at current month weights; both legs required; rebuild exact cutoff and contiguous-month lag.'
 elif t.startswith('weo'):
  pit='CONDITIONAL_VINTAGE_ARCHIVE';why='Actual named WEO vintage values exist, but vintage_date is assigned day 15, not actual release timestamp.';availability='Use existing archive evidence for release day or first following month; current hardcoded day15 not certified';revision='Named source vintages available; preserve vintage key and source';clean='As-of vintage join; target-year forecasts are allowed expectations, never realized inflation/GDP.'
 elif t=='release_events_signals':
  pit='CONDITIONAL_RELEASE_ARCHIVE';why='release_date/signal_date and first-print named fields exist; ticker-country identity and independent original-print/survey-vintage proof still required.';availability='Use signal_date after release cutoff, not reference_period';revision='actual_first_print column name is not proof of original print; survey timing and corrections must be traced';clean='Past-only expanding std shifted 1; z clipped ±3. Grouping currently macro-country/concept pools multiple tickers; same-date and geographic duplicate audit required.'
 elif t.startswith('eco_surprise'):
  why='Reference-period monthly release surprises cannot be treated as announcement-date surprises; prefer existing release_events archive.'
 elif t in ['market_implied_daily','market_implied_signals','sovereign_daily','sovereign_signals'] or (t=='extended_factors' and v.startswith('FRED_')) or (t=='extended_factors' and v=='BIS_Policy_Rate'):
  pit='CONDITIONAL_MARKET_HISTORY';why='Observed market/admin-rate history is plausible replay input; exact security/field, currency, availability, corrected-history policy and causal transforms need contract.';availability='Close/official change known by next decision cutoff; global source is one observation';revision='Vendor/corporate corrections possible; archive frozen input';clean='Recompute changes/rolling stats causally from raw levels; avoid live partially completed month.'
 elif t in ['etf_flows','etf_flow_signals','foreign_flows_daily']:
  pit='CONDITIONAL_FLOW_HISTORY';why='Historical observations exist; reporting vs trading date and publication latency unresolved per series; not all dollar flows comparable.';availability='NSDL India report date trade+1; other markets source-specific; short interest requires actual publication date not settlement date';revision='Vendor revisions/splits and NAV/share adjustments require frozen source contract';clean='Flow sign positive inflow; normalize to own lagged AUM/vol; keep share/NAV split guard and real timestamp; do not average ETF and national flows indiscriminately.'
 elif t=='sov_ratings_monthly':
  pit='CONDITIONAL_EVENT_HISTORY';why='Historical monthly issuer ratings exist; monthly observations are not precise announcement events.';availability='Use observed rating at next decision; verify event dates for changes';revision='Issuer/security mapping and original rating release unverified';clean='Higher 21-point score = better rating; negative change deterioration.'
 elif t=='t2_raw':
  pit='CONDITIONAL_SOURCE_REPLAY';why='Current builder has causal spike guard, but monthly warehouse has not been proven regenerated from that code. Raw workbook reread and mask recovery can use existing ASADO files.';availability='Monthly rows shifted first day next month; source date known at preceding close only for market fields';revision='Macro/financial-statement fields retain provider revision/restatement risk';clean='2026-08-21 full-sample winsorizer removed; strictly prior EWM spike clipping; reconcile workbook/build lineage and prefix tests.'
  if v in ['GDP','Inflation','Current Account','Debt to GDP','Budget Def','REER']:pit='QUARANTINE_LATEST_VINTAGE'
  if v in ['Gold','Gold 12','Copper','Copper 12','Oil','Oil 12','Agriculture','Agriculture 12']:why+=' Commodity names may represent exposure betas in transformed family; inspect raw workbook vs output, never infer price from variable name.'
 elif t=='valuation_monthly':
  pit='CONDITIONAL_SOURCE_REPLAY';why='Derived from T2 daily levels plus sovereign/CPI; daily zero-fill manufactures data coverage and unfinished month stamped month-end.';availability='Rebuild month-end at completed decision boundary with original observed masks';revision='CAPE/EPS/valuation vendor history may be restated; ERP includes latest-vintage CPI';clean='Valuation percentiles higher=rich incl inverted DY/EY/ERP; recompute raw controls under cutoff; ERP deferred if CPI illegal.'
 elif t=='graph_features_pit_daily':
  pit='CONDITIONAL_LAGGED_RELATIONSHIP';why='Historical reference weights + assumed lag are better than current weights but not proof of original release vintages.';availability='trade +4m; bank +4m; holder +9m assumed, actual revisions unresolved';revision='Current API historical periods may revise; edge vintage_end describes period not fetch vintage';clean='Use as-of legal edges only; no current graph/similarity/combiner substitute.'
 elif t=='macrostructure_factors' and v=='MS_Swap_Line_Access':
  pit='CONDITIONAL_EVENT_RULE';why='Dated rule uses 2013 standing and 2020-2021 temporary lines; structural proxy incomplete (e.g. earlier crisis facilities)';availability='Rule effective dates need event ledger evidence; month-start timing cannot anticipate announcement';revision='Frozen policy-rule series, not continuous measured capacity';clean='Keep policy access binary/category; numerical 100/75 scale is chosen proxy, not cardinal capacity.'
 if t=='demographics_dip':why='Extends 2100, realized and projected values not separable by date alone. Current projection vintage cannot be broadcast backward.'
 cs=sorted(T2.intersection(set(str(r.country_list).split('|'))))
 for f in fs:
  sign='Higher = '+{1:'stronger growth',2:'tighter nominal policy for levels; easing impulse defined as negative change',3:'tighter real policy',4:'higher inflation pressure',5:'more credit expansion or fragility (separate subscore)',6:'more vulnerability after component-specific orientation',7:'more sovereign stress after component-specific orientation',8:'more bank fragility after component-specific orientation',9:'more backstop capacity',10:'inflow/crowding (distinct impulse/extreme)',11:'more global risk after component-specific orientation',12:'country benefit after exposure sign; no uniform sign',13:'more expected-return attractiveness after component-specific orientation',14:'stronger trend or more fragility (separate)',15:'more resilience/capacity after component-specific orientation',16:'more exposure to stressed neighbors'}[f]
  transform='Keep level and one predeclared change separate; trailing/fold-local scale; sign into state, not assumed return direction.'
  rows.append(dict(family_id=f,family=families[f-1],variable=v,source=r.source,table=t,database=r.db,existing_path=paths[t],native_frequency=native,stored_rows=r.row_count,stored_nonnull=r.nonnull,stored_finite=r.finite,stored_missing_or_nonfinite_pct=round(100*(1-float(r.finite)/float(r.row_count)),4),raw_expected_grid_missingness='Not inferred from omitted rows; see DATA_AUDIT.md for denominator and selected matched coverage',all_country_count=r.countries,t2_market_count=len(cs),t2_countries='|'.join(cs),first_observation_date=r.first_date,last_observation_date=r.last_date,concept_orientation=sign,registry_sign=str(reg.loc[v,'sign']) if v in reg.index else '',proposed_transform=transform,publication_availability=availability,revision_policy=revision,cleaning_lineage=clean,pit_candidate_class=pit,certified_for_historical_ml=False,admission_reason=why))
c=pd.DataFrame(rows);c.to_csv(P/'candidate_catalog.csv',index=False)
print('catalog',len(c),'unique',c[['table','variable','source']].drop_duplicates().shape[0],'families',sorted(c.family_id.unique()));print(c.groupby('family').size().to_string())
