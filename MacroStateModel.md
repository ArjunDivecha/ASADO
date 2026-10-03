# Macro State Model — Idea Seed for Astra

**Status:** IDEA SEED — intentionally incomplete, unvalidated, and not an implementation specification  
**Purpose:** Preserve the ideas developed in discussion so that Astra can challenge, expand, formalize, and research them before any coding or production integration.  
**Project:** ASADO  
**Research posture:** Treat every claim below as a hypothesis or design option, not as an established fact.

---

## 1. Origin of the idea

The immediate inspiration is the Macrosynergy research note on gold and macro factors. The most interesting aspect is not the gold application itself, but the architecture:

> many noisy raw variables → economically coherent concepts → higher-level macro states → return forecast

Instead of asking a model to infer economic structure directly from hundreds of raw fields, construct a smaller set of interpretable economic concepts first, then test whether those concepts improve country-return prediction on their own and as inputs to more flexible models.

ASADO is especially suited to this because it already contains a broad set of country-level macro, market, valuation, flow, political-risk, commodity, banking, sovereign, and network data.

The central idea is therefore:

> Build an explicit economic state layer over ASADO's raw data, preserving the statistical benefits of one cross-country model while allowing the economic transmission mechanism to differ by country.

This should be researched as an extension/new research family, not assumed to replace the existing ASADO architecture.

---

## 2. Core hypothesis

The working hypothesis is that ASADO may predict medium-horizon country equity returns better if it represents the world through a compact set of economically meaningful state variables rather than relying exclusively on a large flat variable matrix.

Potential advantages:

1. **Lower effective dimensionality.** Hundreds of correlated measurements can be compressed into a smaller number of concepts.
2. **Economic inductive bias.** The model starts with a vocabulary corresponding to monetary policy, credit, external vulnerability, valuation, flows, etc.
3. **Better out-of-sample stability.** Concept scores may be less sensitive to changing data availability and individual-series noise.
4. **Interpretability.** Country forecasts can be attributed to economic states rather than opaque feature importance.
5. **Better nonlinear learning.** A nonlinear model can learn interactions among meaningful states rather than being forced to discover both the concepts and their interactions from raw variables.
6. **Country individualization without 34 independent models.** Common concepts can be transformed through country-specific exposures and learned sensitivities.

The hypothesis could be wrong. A flat regularized model may already extract all useful information. The research must make the Macro State Model earn its complexity on identical samples and point-in-time-safe data.

---

## 3. Proposed hierarchy

A possible hierarchy is:

**ASADO raw data universe**  
↓  
**~50–80 economically selected primitive signals**  
↓  
**~14–15 economic concepts**  
↓  
**~5–7 higher-level country states**  
↓  
**shared cross-country prediction model**  
↓  
**3M / 6M / 12M expected country excess return or rank**

The counts are placeholders for research, not design commitments.

The important feature is hierarchical compression, not the exact number of variables.

---

## 4. Candidate economic concepts

The first concept list to investigate:

### 4.1 Growth Cycle

Question: **Is economic activity strong or weak, and is it accelerating or decelerating?**

Candidate inputs include:

- OECD CLI
- OECD BCI
- OECD CCI
- manufacturing PMI
- services PMI
- consensus GDP growth
- realized GDP growth
- employment indices
- unemployment measures
- exports/imports growth where relevant

Potential derived states:

- `Growth_Cycle_Level`
- `Growth_Cycle_Momentum`
- `Growth_Expectations_Gap`

An important research question is whether acceleration/deceleration matters more than level.

---

### 4.2 Monetary Policy Impulse

Question: **Is monetary policy becoming more or less supportive?**

Potential inputs:

- policy rate
- money-market rate
- T-bill rate
- 2Y sovereign yield
- OIS
- WIRP/implied future policy rate
- yield-curve slope

Possible sub-states:

- current policy direction
- expected policy direction
- front-end easing/tightening
- surprise relative to growth/inflation conditions

The state should likely be directional rather than simply the level of rates.

---

### 4.3 Real Monetary Tightness / Policy-Growth Mismatch

Question: **How tight is policy relative to the country's inflation and growth conditions?**

Potential constructs:

- nominal policy rate minus inflation
- real 2Y yield
- policy rate relative to trailing country history
- monetary tightness minus growth-cycle strength

The same policy rate may mean something entirely different in a weak economy than in a booming economy.

A particularly interesting concept is:

> `Policy_Growth_Mismatch = Monetary_Tightness − Economic_Strength`

Research whether this is more predictive than policy rates themselves.

---

### 4.4 Inflation Regime

Question: **Are inflation pressures high/low and rising/falling?**

Potential inputs:

- CPI inflation YoY
- consensus CPI
- breakeven inflation
- import price inflation
- commodity inflation relevant to the country
- inflation surprise/revision signals where PIT histories exist

Potential dimensions:

- inflation level
- inflation momentum
- inflation expectations
- inflation surprise

---

### 4.5 Private Credit Cycle

Question: **Is leverage currently supporting growth or creating future vulnerability?**

Potential inputs:

- BIS credit/GDP gap
- BIS debt service ratio
- domestic credit/GDP
- property prices
- monetary-policy tightening

This may need two concepts rather than one:

**Credit Boom** — expansion that can be supportive in the near term.  
**Credit Fragility** — leverage that creates medium-term downside risk.

The important idea is that high credit growth can be simultaneously positive for current demand and negative for future stability.

---

### 4.6 External Vulnerability

Question: **How vulnerable is the country to a sudden stop or external-funding shock?**

Potential inputs:

- current account/GDP
- FX reserves
- reserve adequacy
- import cover
- REER over/undervaluation
- FX depreciation
- BOP financial account
- portfolio investment flows
- FDI
- foreign-currency government debt
- foreign-held government debt
- external creditor share
- short-term external funding where available

Possible high-level construct:

> current-account weakness + reserve weakness + currency overvaluation + FX stress + foreign-currency debt + capital outflow pressure

This is likely especially important for EM markets but should be estimated in the shared model rather than hard-coded as an EM-only factor.

---

### 4.7 Sovereign / Fiscal Stress

Question: **Is sovereign credit quality deteriorating?**

Potential inputs:

- CDS
- sovereign yields
- government bond/OIS spreads
- debt/GDP
- short-maturity debt
- foreign-currency debt
- ratings changes
- fiscal balance/debt trajectory if PIT-safe data can be constructed

Keep this concept distinct from external vulnerability initially so that the research can test whether they contain different information.

---

### 4.8 Banking Fragility

Question: **How vulnerable is the domestic banking system?**

Potential inputs:

- NPL ratio
- NPL net of provisions relative to capital
- capital adequacy
- liquidity ratio
- LCR
- NSFR
- credit cycle variables

Likely useful dimensions:

- fragility level
- deterioration/improvement

Changes may matter more than structural levels.

---

### 4.9 Policy Backstop Capacity

Question: **How much capacity exists to absorb a domestic or external shock?**

Potential inputs:

- central-bank balance sheet/GDP
- reserve adequacy
- swap-line access
- domestic-currency debt share
- domestic creditor base
- central-bank holdings of sovereign debt
- policy-backstop measures already in ASADO

A promising interaction is:

> `Stress / Backstop Capacity`

or an equivalent state combining shock intensity with the ability to absorb it.

---

### 4.10 Capital-Flow Pressure / Positioning

Question: **Is foreign or passive capital moving into or out of the market, and how crowded is positioning?**

Potential inputs:

- country ETF net flows
- ETF flows relative to market capitalization
- net creation shares
- passive AUM relative to market capitalization
- index-weight changes
- foreign flows
- portfolio-account flows
- relevant COT or market-positioning measures

Potential concepts:

- `Capital_Flow_Impulse`
- `Foreign_Positioning_Extreme`
- `Passive_Flow_Distortion`

A particularly interesting interaction is valuation × flow inflection:

> cheap + outflows slowing may differ materially from cheap + accelerating capital flight.

---

### 4.11 Global Risk / Doom

Question: **Is the global environment becoming more risk-seeking or risk-averse?**

Potential inputs:

- VIX
- HY OAS
- broad USD
- Global GPR
- GPR Threat
- GPR Act
- EPU
- GDELT risk/tone measures
- global financial-condition proxies

The raw global state may be less useful than its transmission into each country.

Potential interaction:

> `Global_Risk × Country_Fragility`

---

### 4.12 Terms of Trade / Commodity Impulse

Question: **Are global commodity-price movements helping or hurting this country's economy?**

Do not simply broadcast identical commodity prices across countries.

Instead construct something like:

> `Country Commodity Impulse = Σ(Global commodity move × country structural exposure)`

Possible exposures:

- net oil exporter/importer
- natural gas
- metals
- copper
- iron ore
- agriculture/food
- other economically material commodities

This should use ASADO trade/export structures and the global World Bank commodity surface.

The same oil shock should have different signs and magnitudes for Saudi Arabia, Brazil, India, Korea, etc.

This is one of the most promising areas for research because it converts a global series into a country-specific macro transmission signal.

---

### 4.13 Valuation / Expected Return

Question: **How much good or bad news is already reflected in prices?**

Potential inputs:

- CAPE / Shiller PE
- trailing PE
- forward/best PE
- price/book
- dividend yield
- earnings yield
- ERP
- valuation percentiles relative to each country's own history
- cross-sectional valuation rank
- earnings revisions

Valuation should probably remain a distinct expected-return family rather than being folded into the macro state.

---

### 4.14 Market Trend and Fragility

Question: **What is the equity market itself saying about the state of the country?**

Potential inputs:

- 1/3/6/9/12M momentum
- 12–1 momentum
- P2P / drawdown from peak
- 120MA signal
- RSI
- breadth / advance-decline
- short- and long-horizon volatility
- momentum-fragility measures

This remains an essential family because the market can aggregate information faster than macro releases.

---

### 4.15 Institutional Resilience / Structural Capacity

Question: **How resilient is the country's institutional and domestic-capital structure?**

Potential inputs:

- governance quality
- corruption control
- rule of law
- regulatory quality
- political stability
- pension assets/GDP
- insurance assets/GDP
- household direct equity ownership
- domestic creditor share
- demographic variables

These should probably not be treated as monthly timing variables. Instead they may act as slow-moving country priors or interaction variables that modify the transmission of shocks.

Potential derived concepts:

- `Institutional_Resilience`
- `Domestic_Capital_Depth`
- `Demographic_Tailwind`

---

### 4.16 Cross-Country Contagion / Network Vulnerability

Possible later concept rather than launch requirement.

Question: **How exposed is the country to shocks originating elsewhere?**

Potential sources:

- bilateral trade
- bilateral banking
- bilateral portfolio ownership
- PIT graph vintages
- country similarity/lead-lag structures only where their research lineage is valid

Potential construct:

> weighted exposure to stressed neighbors/counterparties

This may become especially valuable once the simpler standalone blocks have earned continuation.

---

## 5. Higher-level meta-states

After the individual concepts are validated, Astra should investigate whether further compression helps.

Possible higher-level states:

1. **Economic Momentum**
2. **Financial Conditions**
3. **Balance-Sheet Vulnerability**
4. **Capital-Flow Regime**
5. **Risk / Contagion Exposure**
6. **Expected-Return Attractiveness**

These are not necessarily inputs to the final model. They may instead be interpretability summaries or alternative low-dimensional models.

Research should compare:

- primitive-only
- concept-only
- meta-state-only
- primitive + concepts
- primitive + concepts + meta-states

---

## 6. Shared model versus country-specific models

The preferred starting architecture is **one shared cross-country model**, not 34 independent country models.

Reasons:

- ASADO has limited independent time history.
- A shared model pools statistical information across countries.
- Many economic relationships are likely common in sign or structure even when their magnitudes differ.
- Separate models would dramatically increase the number of parameters and researcher degrees of freedom.

However, a shared model should **not** imply that the exact same raw variables have identical economic meaning in every country.

The better formulation is:

> **common economic vocabulary + country-specific transmission + shared learning**

---

## 7. How country individualization could work

### 7.1 Structural exposure transformations

Where economics clearly requires country-specific exposure, transform global shocks before they enter the model.

Examples:

- commodity prices × country commodity exposure
- China growth/risk × country China trade exposure
- U.S. rates/USD × country's external funding dependence
- global risk × foreign-capital dependence
- global financial stress × FX-debt exposure

These transformations should be economically defined and PIT-safe, not optimized ad hoc country by country.

---

### 7.2 Availability masks

A missing series should remain missing.

The model should receive explicit masks/age/coverage information rather than fabricated values or unrestricted historical backfilling.

Country-specific data coverage is therefore part of the information set.

---

### 7.3 Country embeddings

A later nonlinear model could include a small learned country embedding.

The embedding should not become a substitute for economic structure. Its purpose is to allow the shared model to learn persistent differences in how countries transmit common shocks.

Examples:

- USD tightening may affect Brazil differently from Switzerland.
- commodity inflation may affect Saudi Arabia differently from India.
- rising global risk may matter differently depending on domestic investor depth and external funding structure.

The embedding must be small and strongly regularized so it does not create 34 hidden independent models.

---

### 7.4 Learned concept gating

A further extension is a country-dependent gate over macro concepts.

Conceptually, the model might learn that:

- commodities and external funding matter more for some countries
- monetary policy and FX matter more for others
- global risk and domestic capital depth matter more elsewhere

The gate should be learned from the pooled sample and regularized toward common weights.

This is preferable to manually selecting a different variable list for every country.

---

## 8. Preferred conceptual architecture

A useful high-level decomposition may be:

### Global State

- USD
- U.S. rates
- VIX / credit spreads
- global growth
- global inflation
- commodities
- geopolitics

↓

### Country Transmission Layer

- trade exposure
- commodity exposure
- foreign capital dependence
- foreign-currency debt
- banking exposure
- portfolio ownership
- domestic investor base
- institutional resilience

↓

### Country-Specific External Shock

Examples:

- country financial tightening
- terms-of-trade shock
- foreign-funding shock
- China shock
- commodity shock
- contagion shock

↓

### Local Country State

- growth
- inflation
- monetary policy
- credit
- sovereign stress
- banking fragility
- valuation
- flows
- momentum

↓

### Expected Return / Rank

- 3M
- 6M
- 12M

This global-state → transmission → local-state architecture may be more economically coherent than a flat country × variable tensor, but that must be tested rather than assumed.

---

## 9. Construction philosophy for concept scores

The first version of each concept should be deliberately simple.

Suggested principles:

1. Pre-specify the expected economic sign of each component where possible.
2. Standardize using PIT-safe, fold-local or trailing transforms.
3. Use equal weights initially.
4. Require minimum component coverage.
5. Preserve component-level diagnostics.
6. Do not optimize component weights until the unoptimized concept has been evaluated.

Why:

If an equal-weight economically signed concept has no predictive value, an optimized version may simply be manufacturing an in-sample result.

Only after the concept itself earns continuation should Astra investigate:

- ridge weights
- elastic-net weights
- Bayesian/hierarchical weights
- learned nonlinear concept encoders

---

## 10. Interactions may be more important than the concepts themselves

A core hypothesis is that the largest incremental value may come from interactions among states.

Candidate examples:

- **Cheap × Improving Growth × Easing Financial Conditions**
- **Cheap × Collapsing Growth × Capital Flight**
- **Global Risk × External Vulnerability**
- **Credit Boom × Monetary Tightening**
- **Commodity Shock × Country Exposure**
- **Sovereign Stress × Weak Policy Backstop**
- **Flow Reversal × Extreme Valuation**
- **Global USD Tightening × FX Debt Exposure**
- **Bank Fragility × Credit Contraction**
- **Growth Deterioration × High Valuation**

The conceptual layer supplies the economic vocabulary; a nonlinear model may then learn the grammar.

A key research objective is to determine whether nonlinear interactions add genuine OOS value beyond additive concept scores.

---

## 11. Forecast horizons

The original motivation is strongest for **medium-horizon** prediction.

Primary candidate:

- next 12M country excess return / rank

Secondary:

- next 6M
- next 3M

Potential research question:

> Do slow-moving macro-state concepts become stronger as the forecast horizon lengthens, while market/flow signals dominate shorter horizons?

This should be tested explicitly rather than using a single arbitrary horizon.

The target definition must remain separate from the feature store and use ASADO's canonical return surfaces.

---

## 12. Point-in-time and leakage constraint

This is the most important practical issue.

ASADO contains many economically attractive series that are not yet proven historically point-in-time. The current broad feature surface must therefore not be treated as an unrestricted historical training matrix.

Astra should divide candidate variables into at least two groups:

### Economically Relevant

Variables that conceptually belong in the model.

### Historically Legal / PIT-Safe

Variables whose value, publication timing, vintage, revision behavior, and cleaning process can be demonstrated as knowable at each historical decision date.

Research rules:

- deny by default for historical model input
- explicit `available_at`
- publication lag documented
- revision/vintage rule documented
- no future-aware transforms
- no forward-return aliases
- no future projections treated as realized observations
- no current graph relationships projected into history
- no optimizer/combiner outputs reused as raw predictors without clean lineage

A very successful result that depends on latest-vintage macro histories is not a valid result.

The existing ASADO ML architecture principle should govern this project:

> complexity is earned only through identical-sample, point-in-time, out-of-sample improvement.

---

## 13. Initial model comparison sequence

Astra should refine this, but a useful first research ladder is:

### Model A — Primitive Ridge

Use the same PIT-safe primitive signals that feed the concept layer.

Purpose: determine how much information is already captured by a standard regularized linear model.

### Model B — Concept-Only

Use only the economic concept scores.

Purpose: determine whether compression itself preserves or improves predictive information.

### Model C — Primitive + Concepts

Use raw/legal primitives plus concept scores.

Purpose: test whether economic inductive bias adds value while allowing the model to use exceptions and residual information.

### Model D — Nonlinear Shared Model

Use primitives + concepts + country-specific exposures, eventually including temporal encoding, country embeddings, concept gating, or cross-country attention.

Purpose: test whether nonlinear interactions and heterogeneous transmission add genuine OOS value.

All models should be compared on identical samples whenever possible.

---

## 14. Research sequence before implementation

The Macro State Model should not go directly from this note to code.

Suggested sequence:

### Stage 1 — Astra critique

Astra should challenge the entire idea.

Questions:

- Is conceptual compression supported by empirical asset-pricing and macro-finance literature?
- Which proposed concepts are redundant?
- Which concepts are missing?
- Which interactions have theoretical or empirical support?
- Does hierarchical country pooling outperform per-country estimation in comparable research?
- Are there known frameworks already very close to this architecture?
- Which parts are likely to be over-engineering?

### Stage 2 — Literature research

Review evidence on:

- macro predictors of international equity returns
- global versus local return predictors
- hierarchical/multitask country models
- country-specific macro transmission
- financial conditions
- external vulnerability
- credit cycles
- terms-of-trade shocks
- capital flows
- valuation × macro interactions
- macro momentum / regime persistence
- regime-dependent factor returns
- country network contagion

The goal is not to find papers supporting the idea; actively seek evidence that would falsify it.

### Stage 3 — ASADO variable mapping

Map every proposed concept to actual ASADO variables and sources.

For each primitive candidate record:

- variable name
- source/table
- countries covered
- frequency
- start/end date
- economic sign
- transform
- publication lag
- revision policy
- PIT classification
- missingness
- whether currently allowed for historical ML

### Stage 4 — Redundancy and availability audit

Identify duplicate or near-duplicate measurements across sources.

Prefer a small number of defensible primitives rather than allowing one economic concept to receive 15 correlated versions of the same signal.

### Stage 5 — Cheap standalone screens

Before interactions or neural models, test each concept independently.

Possible diagnostics:

- monthly cross-sectional rank IC
- Pearson IC
- 3M / 6M / 12M forward excess returns
- top-minus-bottom portfolio
- monotonicity by score bucket
- decade stability
- DM versus EM
- country contribution
- crisis/non-crisis behavior
- sensitivity to data coverage

### Stage 6 — Combined linear model

Test equal-weight and regularized combinations.

### Stage 7 — Country transmission layer

Add commodity/trade/funding/global-risk exposure transforms individually and test incremental contribution.

### Stage 8 — Interactions

Only then test economically pre-specified interactions.

### Stage 9 — Nonlinear shared model

Only after simpler blocks demonstrate useful signal.

### Stage 10 — Lockbox / promotion decision

No parameter changes after lockbox opening. Record failures as well as successes.

---

## 15. Questions Astra should answer before a PRD is written

1. What is the strongest evidence that macro variables can forecast medium-horizon cross-country equity returns?
2. Is the return signal primarily cross-sectional or time-series?
3. Do concepts improve stability relative to raw variables?
4. Which concepts have the longest reliable PIT histories in ASADO?
5. Which attractive concepts are currently unusable because vintage information is missing?
6. How should concept scores be normalized: within-country history, cross-sectional rank, or both?
7. Should level and momentum be separate fields for every concept?
8. Should all concepts be represented at multiple horizons?
9. How should country exposures be estimated without introducing lookahead?
10. Should commodity exposures come from static trade structure, rolling trade data, or both?
11. Should country embeddings be allowed at all in the first nonlinear experiment?
12. What regularization would prevent concept gating from degenerating into 34 independent models?
13. Does a hierarchical Bayesian or multitask model provide a cleaner first heterogeneity test than a neural embedding?
14. How much additional statistical information really comes from 34 countries given strong global correlation?
15. Should sleeves such as ChinaA/ChinaH and U.S./NASDAQ/US SmallCap share macro identities but retain separate market-state variables?
16. Which global shocks deserve explicit transmission layers?
17. Can bilateral trade/banking/portfolio data materially improve transmission estimates?
18. Is `stress ÷ backstop capacity` useful or merely a convenient narrative?
19. Are the most promising effects additive, interactive, or regime dependent?
20. Does the concept architecture improve forecasting after controlling for momentum, valuation, and existing ASADO baselines?

---

## 16. Possible kill criteria

Astra should formalize these, but the idea should be abandoned or sharply simplified if:

- concept-only models materially underperform primitive regularized baselines
- concept construction adds instability rather than reducing it
- improvements disappear on identical PIT-safe samples
- most apparent performance depends on revision-prone/latest-vintage macro data
- country-specific transmission does not add OOS information
- learned heterogeneity is unstable across folds or seeds
- nonlinear models do not beat simpler models after complexity penalties
- performance is driven by a few countries or one historical regime
- predictive gains disappear after controlling for momentum/value/global beta
- turnover or implementability destroys portfolio relevance

Failure should be recorded as useful evidence rather than rebranded into another hypothesis.

---

## 17. What would constitute a successful result?

The strongest possible outcome is not necessarily the most complicated model.

A successful result could be as simple as:

> a small set of transparent macro-state scores produces stable, incremental cross-sectional return information beyond momentum and valuation.

A stronger result would show:

> concept scores + country-specific transmission improve OOS performance beyond the same raw variables alone.

The strongest version would show:

> a shared nonlinear model using economic concepts, country exposures, and a small amount of learned heterogeneity produces robust incremental performance across periods, countries, and regimes without relying on data leakage or unstable parameterization.

---

## 18. Astra research mandate

Astra should treat this document as a starting hypothesis document, not instructions to implement the proposed architecture.

Its job should be to:

1. Critique the economic logic.
2. Search for prior academic and practitioner work that supports or contradicts it.
3. Find missing concepts and unnecessary concepts.
4. Determine which effects have credible theoretical transmission mechanisms.
5. Map the complete ASADO database into candidate primitive signals.
6. Identify PIT-safe versus non-PIT-safe candidates.
7. Propose the smallest viable concept set.
8. Design a staged empirical research program.
9. Specify falsification tests and kill criteria.
10. Recommend whether the final architecture should use:
   - flat raw variables,
   - concept scores,
   - hierarchical linear models,
   - tree models,
   - nonlinear shared models,
   - or some combination.
11. Compare a single pooled model, partially pooled hierarchical model, and country-specific alternatives on statistical grounds.
12. Produce a research plan before any implementation PRD is written.

Astra should be encouraged to reject major parts of this proposal if the evidence does not support them.

---

## 19. Working summary

The idea can be summarized as:

> **ASADO should consider learning country returns through an explicit macro-state representation rather than relying only on a flat feature matrix.**

The likely preferred architecture is:

> **common economic concepts + country-specific exposure transformations + shared cross-country model + tightly regularized learned heterogeneity.**

The main potential edge is not any single macro indicator. It is the ability to represent economically coherent state interactions such as:

- cheap + improving growth + easing financial conditions
- global risk + weak external balance sheet
- credit boom + tightening policy
- commodity shock × country exposure
- capital-flow reversal × valuation
- sovereign stress × weak policy backstop

The concept layer provides the economic vocabulary. The model then learns how that vocabulary combines differently across countries and regimes.

This remains an idea to be developed, researched, falsified, and only then turned into a formal ASADO research specification.
