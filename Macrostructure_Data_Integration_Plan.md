# ASADO Macrostructure Data Integration Plan

## Goal

Extend ASADO from a "fundamentals + valuation" country research system into a
"fundamentals + valuation + macrostructure" system by adding data on:

- who owns a country's assets
- who sets marginal prices
- which investor bases are stable vs forced sellers
- where passive/mechanical flows matter
- where central-bank support changes market behavior

The design target is to keep ASADO's current architecture intact:

- DuckDB remains the source of truth for historical time series
- Neo4j remains a compact structural/network layer
- `db_bridge.py` remains the single query surface on top of both

## Working Principles

1. Do not turn Neo4j into a time-series warehouse.
   Historical ownership and fragility series should live in DuckDB as tidy
   panels. Neo4j should only hold the latest structural snapshot and graph
   relationships that are genuinely useful for network-style queries.

2. Reuse the existing collector idioms.
   ASADO already separates panel-like data and relationship-like data:
   `collect_imf.py` writes tidy panels, while `collect_bilateral.py` writes
   adjacency-matrix-style outputs for Neo4j. The new work should follow the
   same pattern.

3. Preserve the existing country mapping rules.
   `ChinaA` and `ChinaH` share `CHN`; `U.S.`, `NASDAQ`, and `US SmallCap`
   share `USA`. Market-sleeve duplication should stay in DuckDB where it is
   already handled consistently, while Neo4j ownership edges should continue to
   attach only to sovereign-proxy country nodes.

4. Start with free, durable, automatable sources.
   EPFR/Lipper-style fund-flow products are valuable, but Phase 1 should not
   depend on paid data or manual spreadsheets.

## What To Add

### A. Bilateral ownership data

These datasets answer "who owns whose assets?"

Phase-1 priority sources:

- IMF CPIS:
  bilateral portfolio holdings, split across equity/investment fund shares,
  long-term debt, and short-term debt.
- U.S. Treasury TIC:
  higher-frequency U.S.-specific holdings and flow detail for Treasuries,
  agencies, corporate debt, and equities.

Primary output:

- `Data/processed/bilateral_portfolio_matrix.parquet`

Suggested schema:

| column | meaning |
| --- | --- |
| `date` | observation date |
| `reporter_iso3` | holder country |
| `counterpart_iso3` | issuer country |
| `instrument_type` | `equity`, `fund_shares`, `debt_long`, `debt_short`, or a normalized TIC class |
| `amount_usd` | holdings amount in USD |
| `share_of_reporter_portfolio_pct` | reporter-side concentration |
| `share_of_counterpart_inbound_pct` | counterpart inbound ownership share when computable |
| `source` | `imf_cpis` or `us_tic` |
| `frequency` | `semiannual`, `monthly`, or `annual_benchmark` |
| `is_official_sector` | optional flag if later sources distinguish official holdings |

Neo4j snapshot edges derived from the latest available date:

- `(:Country)-[:HOLDS_PORTFOLIO]->(:Country)`

Relationship properties:

- `instrument_type`
- `amount_usd`
- `share_of_reporter_portfolio_pct`
- `share_of_counterpart_inbound_pct`
- `source`
- `date`

This should be the first new graph edge family. It is the cleanest way to make
the paper's investor-base logic visible inside ASADO.

### B. Country-level macrostructure panel

These datasets answer:

- how foreign-owned a market is
- how bank/intermediary-dependent it is
- how sticky the domestic investor base is
- how much passive/index support it receives
- how much policy backstop it has

Primary output:

- `Data/processed/macrostructure_panel.parquet`
- `Data/processed/macrostructure_panel.csv`
- `Data/processed/macrostructure_variable_catalog.csv`

Tidy schema should match the rest of ASADO:

| column | meaning |
| --- | --- |
| `date` | aligned period date |
| `country` | T2 country name |
| `value` | raw value |
| `variable` | descriptive variable name |
| `source` | source tag |

Suggested initial variable families:

- ownership mix
  - `MS_Foreign_Ownership_Equity_Pct`
  - `MS_Foreign_Ownership_Debt_Pct`
  - `MS_US_Holder_Share_Pct`
  - `MS_Domestic_Sticky_Capital_Pct`
- banking/intermediary fragility
  - `MS_Bank_Capital_Adequacy`
  - `MS_Bank_Liquidity_Ratio`
  - `MS_NPL_Ratio`
  - `MS_Bank_Funding_Fragility`
- debt-holder structure
  - `MS_Public_Debt_Foreign_Held_Pct`
  - `MS_Public_Debt_Local_Currency_Pct`
  - `MS_Public_Debt_Short_Maturity_Pct`
- passive/mechanical flow proxies
  - `MS_Index_Weight`
  - `MS_Index_Weight_Change`
  - `MS_Country_ETF_AUM_USD`
  - `MS_Passive_AUM_to_MarketCap`
- policy support / official-sector presence
  - `MS_CentralBank_BalanceSheet_GDP`
  - `MS_CentralBank_SovDebt_Share`
  - `MS_Reserve_Adequacy`
  - `MS_Swap_Line_Access`
- institutional depth
  - `MS_Pension_Assets_GDP`
  - `MS_Insurance_Assets_GDP`
  - `MS_Household_Direct_Equity_Share`

The first release does not need every one of these. It should land the
highest-signal variables with reliable coverage first.

## Dataset Priority And Sequence

### Phase 1: Highest-signal, lowest-friction additions

Target outcome:

- ownership edges in Neo4j
- foreign-ownership and banking-fragility signals in DuckDB
- new variables exposed automatically through `unified_panel`

Datasets:

1. IMF CPIS
   - Use for bilateral cross-country ownership edges.
   - Core signals:
     foreign-held equity, foreign-held debt, concentration by holder country.

2. U.S. Treasury TIC
   - Use as a U.S.-specific supplement, not a replacement for CPIS.
   - Core signals:
     higher-frequency U.S. inbound/outbound holdings and foreign flow stress.

3. IMF Financial Soundness Indicators
   - Use for bank-constraint and forced-seller risk metrics.
   - Core signals:
     capital adequacy, liquidity, NPLs, leverage, funding pressure.

4. Debt-holder structure source
   - Prefer a public debt composition source that gives residency/currency/maturity.
   - Candidate path:
     World Bank QPSD first, then country-specific debt management offices where
     QPSD coverage is thin.

Deliverables:

- bilateral portfolio matrix parquet
- macrostructure panel parquet with an initial fragility block
- Neo4j `HOLDS_PORTFOLIO` edges from the latest snapshot

### Phase 2: Mechanical flow and sticky-capital layer

Target outcome:

- passive-vs-active proxies
- institutional-depth metrics
- index-driven flow sensitivity

Datasets:

1. OECD pension assets / insurance assets
2. OECD household financial balance-sheet data
3. Country ETF holdings/AUM from public issuer data
4. Index weights and reclassification history from public methodology files

Deliverables:

- `MS_Pension_Assets_GDP`
- `MS_Insurance_Assets_GDP`
- `MS_Passive_AUM_to_MarketCap`
- `MS_Index_Weight`
- `MS_Index_Weight_Change`

### Phase 3: Policy-backstop and official-sector layer

Target outcome:

- explicit central-bank footprint
- official-sector support and reserve-credibility proxies

Datasets:

1. central-bank balance-sheet / holdings data by country
2. reserve adequacy metrics
3. official reserve composition support where usable
4. Fed swap-line access and similar backstop indicators

Deliverables:

- `MS_CentralBank_BalanceSheet_GDP`
- `MS_CentralBank_SovDebt_Share`
- `MS_Reserve_Adequacy`
- `MS_Swap_Line_Access`

### Phase 4: Premium enrichment if budget permits

Target outcome:

- better direct reads on fund behavior instead of only proxies

Datasets:

- EPFR or Lipper country allocations and country flows

Deliverables:

- `MS_Active_Fund_Flows`
- `MS_Passive_Fund_Flows`
- `MS_Retail_Flow_Share`
- `MS_Institutional_Flow_Share`

This phase is optional and should be treated as an accelerator, not a blocker.

## Recommended Repo Changes

### 1. Extend `scripts/collect_bilateral.py`

Add a new bilateral ownership collection path instead of creating a completely
separate graph-only script.

New outputs:

- `Data/processed/bilateral_portfolio_matrix.parquet`

Suggested command-line flags:

- `--portfolio-only`
- `--skip-portfolio`

New functions:

- `collect_portfolio_cpis(...)`
- `collect_portfolio_tic(...)`
- `normalize_portfolio_holdings(...)`

Why this belongs here:

- the script already handles graph-bound bilateral datasets
- the output shape mirrors trade and banking adjacency logic
- it keeps portfolio ownership close to existing country-to-country edge data

### 2. Add a new `scripts/collect_macrostructure.py`

This should be a tidy panel collector for country-level macrostructure factors
from mixed sources.

New outputs:

- `Data/processed/macrostructure_panel.parquet`
- `Data/processed/macrostructure_panel.csv`
- `Data/processed/macrostructure_variable_catalog.csv`

Initial source groups:

- IMF FSI
- debt-holder structure / public debt composition
- OECD pensions / insurance / household balance sheets
- ETF passive-share proxies
- index-weight series
- central-bank footprint metrics

Why a new script instead of growing `collect_imf.py` forever:

- the new panel is cross-source by design
- several important variables are not IMF-only
- it keeps the repo's source-family split readable

### 3. Update `scripts/setup_duckdb.py`

Add a new table:

- `macrostructure_factors`

Then extend `unified_panel`:

- `UNION ALL SELECT date, country, value, variable, source FROM macrostructure_factors`

Also create the standard indexes:

- `(country, date)`
- `(variable)`

### 4. Update `scripts/setup_neo4j.py`

Add:

- new `DataSource` entries for the new sources
- a `create_portfolio_edges(session)` function

Do not load full history into the graph. Only use the latest available
portfolio snapshot, just like the existing graph uses latest factor exposures.

Recommended new relationship:

- `HOLDS_PORTFOLIO`

Possible later expansion:

- `EXPOSED_TO_PASSIVE_FLOWS`
- `SUPPORTED_BY_OFFICIAL_SECTOR`

But Phase 1 should stop at `HOLDS_PORTFOLIO`.

### 5. Update `scripts/monthly_update.py`

Insert the new steps into the orchestrator:

1. `collect_external.py`
2. `collect_extended.py`
3. `collect_imf.py`
4. `collect_bilateral.py`
5. `collect_macrostructure.py`
6. `collect_bloomberg.py`
7. `setup_duckdb.py`
8. `setup_neo4j.py`
9. `build_embeddings.py`

If the implementation keeps portfolio collection inside `collect_bilateral.py`,
no extra orchestration step is needed for that sub-piece.

## Data Mapping Rules

### Date alignment

- monthly series: first day of month
- quarterly series: first day of quarter-end month
- semiannual series: first day of period-end month
- annual series: December 1 of year unless the source has a clearly better
  convention already used elsewhere in ASADO

### Country mapping

- use `config/country_mapping.json` as the only mapping authority
- convert source ISO codes to T2 names only at the final panel stage
- keep bilateral matrices in ISO3 form until the graph build
- continue to avoid multiplying Neo4j edges across `ChinaH`, `NASDAQ`, and
  `US SmallCap`; attach bilateral graph edges only to sovereign-proxy nodes

### Variable naming

Use an `MS_` prefix for all new country-level macrostructure variables so they
stay easy to isolate in queries and dashboards.

Examples:

- `MS_Foreign_Ownership_Debt_Pct`
- `MS_Bank_Liquidity_Ratio`
- `MS_Index_Weight`
- `MS_CentralBank_SovDebt_Share`

## Validation Plan

### Collector-level checks

For bilateral ownership data:

- no duplicate `(date, reporter_iso3, counterpart_iso3, instrument_type, source)` rows
- reporter-side ownership shares sum sensibly by period
- U.S. TIC subset reconciles directionally with CPIS where both exist
- country coverage report for the 34-country universe

For macrostructure panel data:

- no duplicate `(date, country, variable)` rows
- variable catalog includes date range and country count
- annual or semiannual series are clearly forward-filled only when intended
- values stay in plausible ranges for percentages and ratios

### Database checks

- `setup_duckdb.py --check` should show `macrostructure_factors`
- `unified_panel` should expose the new variables immediately
- query examples against `db_bridge.py` should retrieve macrostructure signals
  alongside fundamentals and valuation factors

### Graph checks

- `setup_neo4j.py --check` should show `HOLDS_PORTFOLIO`
- edge counts should be limited to sovereign-proxy countries
- the latest ownership date should be logged at build time

## Derived Scores To Build After Raw Data Lands

Do not begin with a black-box composite. First load raw variables, then add a
small number of transparent derived scores.

Recommended first derived scores:

1. `MS_Investor_Base_Fragility`
   - high foreign ownership
   - high bank/intermediary dependence
   - weak liquidity/capital buffers
   - low domestic sticky-capital depth

2. `MS_Policy_Backstop`
   - strong reserve adequacy
   - strong central-bank balance-sheet capacity
   - credible market-support footprint
   - swap-line access / reserve-currency protection where relevant

3. `MS_Passive_Flow_Distortion`
   - large index weight
   - rising index weight
   - high ETF/passive AUM relative to market size

4. `MS_Sudden_Stop_Risk`
   - high foreign-held debt share
   - short maturity structure
   - weak reserves / external buffers
   - fragile banking system

The first implementation should save both raw inputs and derived-score formulas
explicitly so the signal construction stays inspectable.

## Execution Order Recommendation

### Sprint 1

- add bilateral portfolio ingestion contract
- add `macrostructure_panel` contract
- wire both into DuckDB/Neo4j/monthly update

### Sprint 2

- land CPIS + TIC + IMF FSI
- validate coverage, dates, and graph edges

### Sprint 3

- land debt-holder structure and sticky-capital depth variables
- create the first transparent fragility composite

### Sprint 4

- add passive/index flow proxies
- expose macrostructure-aware query examples and dashboards

### Sprint 5

- evaluate whether paid fund-flow data materially improves the signals

## Required Credentials

Core Phase-1 sources should not require new API keys if we stick to the free
path above.

Optional later requirements:

- EPFR or Lipper credentials if you want direct fund-flow/investor-type data
- any premium index or market-structure vendor data if public proxies prove too
  weak

## Recommendation

Implement in this order:

1. bilateral ownership edges via CPIS
2. country fragility panel via IMF FSI + debt-holder structure
3. passive/index proxy layer
4. central-bank footprint layer
5. optional paid fund-flow enrichment

That sequence gets the paper's key insight into ASADO fastest:

"cheap vs expensive" becomes "cheap vs expensive, conditioned on who owns the
market and how constrained they are."
