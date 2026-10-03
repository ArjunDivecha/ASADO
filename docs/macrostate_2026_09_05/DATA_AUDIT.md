# MacroState existing-data audit

Observed 5 September 2026; synthesis and saved-snapshot checks completed 6 September. No additional feeds were collected. Production tables were inspected with short-lived read-only connections; subsequent checks used the saved CSVs. This is an admission audit, not a feature-performance screen.

## What exists

The schema snapshots contain 44 warehouse objects and 68 loop objects. The broad tidy-table inventory has 3,829 table/source/variable entries. These include repeated and derived surfaces; they are not 3,829 independent predictors. The warehouse feature surface contains 3,322,573 rows, 726 distinct variables, and 34 market tokens. Its date span extends from December 1950 to December 2100: the future end includes projections and cannot represent realized history.

The candidate catalog maps **361 concept entries to 339 distinct table/source/variable combinations**, covering all sixteen seed concepts. Mapping is an economic triage aid, not a finalized machine-readable feature contract. Broad name-based mappings and proposed orientations must be checked against units and definitions before admission. A variable mapped to two concepts is one measurement, not two independent observations.

| Concept | Candidate mapping entries |
|---|---:|
| Growth cycle | 47 |
| Monetary policy impulse | 13 |
| Real monetary tightness | 8 |
| Inflation regime | 21 |
| Private credit cycle | 4 |
| External vulnerability | 32 |
| Sovereign fiscal stress | 36 |
| Banking fragility | 6 |
| Policy backstop capacity | 12 |
| Capital flows / positioning | 33 |
| Global risk | 26 |
| Terms of trade / commodity impulse | 34 |
| Valuation / expected return | 28 |
| Market trend / fragility | 16 |
| Institutional / structural capacity | 35 |
| Cross-country contagion | 10 |

All catalog entries are marked `certified_for_historical_ml=False`. That means the required replay certification was not performed in this planning assignment; it does not mean every source is unusable. The catalog's detailed `pit_candidate_class` is preliminary triage. The final plan's VERIFIED_REPLAY / CONDITIONAL_REPLAY / NOT_ADMITTED labels apply only after the proposed admission checks.

There are 174 latest-vintage quarantine mappings, 66 conditional market-history mappings, 64 conditional source-replay mappings, and 57 other conditional mappings. These counts include cross-concept duplication.

## Coverage is not admission

Year-specific ECFC raw forecasts cover 34 market tokens (31 macro identities), from 4 October 2007 through 4 September 2026: 470,792 GDP and 458,822 CPI observations. The fixed-horizon GDP revision surface has 7,198 stored observations and CPI 7,058. These are promising growth/inflation candidates, but daily vendor observation dates do not prove immutable first-publication histories.

Daily sovereign 2Y yields cover 27 market tokens, not 34; US/China duplication reduces that to 24 macro identities. The FX-options surface covers 29 tokens. Their intersection with every other proposed block has not been established. In particular, the proposed broad-universe floor of 28 markets cannot be met by requiring 2Y yields for every market. Existing policy-rate alternatives can be investigated; the plan must not silently substitute them based on predictive results.

Missingness has two different denominators. `stored_missing_or_nonfinite_pct` measures absent/nonfinite values **among stored rows**. Omitted rows and manufactured zeros can make that number deceptively low. A decision-grid coverage measure must use a predeclared country-month universe, observed masks, source ages and legal availability dates. No fully admitted common-sample coverage figure is claimed here.

For illustration only, the inventory counts finite occupied country-month cells from February 2000 through September 2025 (308 months). Against a fixed 34 × 308 = 10,472-cell grid, GDP revisions occupy 6,795 cells (64.9%), CPI revisions 6,657 (63.6%), and the 2Y–10Y slope 6,337 (60.5%). These are individual raw-presence measures, not their intersection, not a live forecast sample, and not availability-adjusted coverage. The interval includes months beyond the last fully mature 12M label in the saved return snapshot. Complete-case deletion after looking at outcomes is prohibited.

## Findings that change the research design

| Surface | Finding | Required treatment using existing files |
|---|---|---|
| Monthly T2 transforms | Current builder has removed full-sample winsorization and uses a causal prior-data spike guard. | Verify the stored panel was regenerated from that version; rebuild/prefix-test transformations from existing raw files if necessary. Code repair alone does not certify stored history. |
| Daily T2 levels | The cleaner still fills missing values with zero. In the saved audit, Vietnam Shiller PE has 9,745 zero rows; Saudi total-return index has 5,354 and Vietnam 2,525. | Recover original observed masks from existing workbook/raw artifacts. Zero is not a valid missing-value substitute for valuation or total-return levels. Do not infer availability from finite counts. |
| Consensus derived monthly rows | Latest row is stamped 30 September 2026 although raw observations stop 4 September. Current/next target-year blend requires both legs. | Reconstruct from raw dated forecasts at the completed decision cutoff; enforce contiguous-month differences and target-year identity. Do not ingest an unfinished month as its completed month-end. |
| WEO archives | Actual named forecast vintages exist, but the collector assigns day 15 of the nominal vintage month. | Verify release date from existing archive evidence or use a separately justified conservative boundary; do not certify the synthetic date. |
| Release-event archive | Release/signal dates and named first-print fields exist; some US events are broadcast to all markets. | Verify ticker geography, survey timing and original-print provenance. Count a shared event once; do not describe broadcasts as independent local releases. |
| Monthly economic surprises | Reference-period stamps differ from announcement dates. | Do not use them as release-date surprises. Prefer the existing release archive if it passes checks. |
| Graph edges | Historical reference periods plus assumed trade/bank/holder publication lags are stored. | These are not automatically first-release vintages. Revised historical API values and current-weight substitutes remain distinct. |
| Valuation / ERP | Depends on daily T2 levels; ERP also includes inflation inputs. | Correct masks and timing; assess restatement/vintage risk. ERP is not automatically admitted because its market-price component is dated. |
| Commodity exposure | Current trade composition and generic commodity names can obscure actual country exposure. | Verify historical exposure dates and whether a field is a price, return or estimated beta. Missing legal exposure history makes that interaction not testable. |
| Flows / short interest | Trading, reporting and publication dates differ; national flows and ETF flows have different denominators. | Apply source-specific availability; keep distinct measures and split corrections. No indiscriminate composite. |
| Structural projections | Some series extend through 2100. | Preserve forecast vintage and target date; never backfill today's projections as historical knowledge. |

The previously empty daily factor-return surface is now populated: **1,181,792 rows through 5 September 2026**. Older empty-table descriptions are stale. This recovery does not resolve the independent daily-level zero-fill issue.

## Target arithmetic check performed

The saved forward-target extract contains 10,846 market-month rows over 319 dates, February 2000–August 2026. The realized-return extract contains 10,555 rows over 318 dates, February 2000–July 2026. Neither has duplicate country-month keys.

All **10,181 nonempty 12M targets** reconcile to the product of the corresponding twelve consecutive monthly gross returns minus one, with maximum absolute error **1.56 × 10⁻¹⁵**. The remaining 665 target rows are empty; they were not converted to zeros or included in the comparison. See `target_reconciliation.json`.

This verifies internal compounding and window alignment of the two saved surfaces. It does not independently establish their Bloomberg security mapping, currency basis, publication availability, historical missing-outcome treatment, or production transformation lineage. Both surfaces may share upstream inputs. Those remain Stage 1–2 checks, not completed validation.

## Feasibility verdict and next contract

Existing ASADO data are economically comprehensive enough for the requested exercise. The unresolved feasibility is **how much jointly available, replayable history remains** after timing, masks, source definitions, training windows and 12M label maturity are enforced.

Prioritize raw market controls, dated GDP/CPI forecasts, policy histories and stress prices. Choose 12–24 underlying primitives by provenance rather than target correlations. Four blocks are a candidate design, not a requirement to fabricate complete coverage. Produce the legal country-month intersection before committing to the 120-month initial training and 96-month OOS aspirations. Shorter lawful history leads to a narrower or insufficient-evidence verdict, not relaxed PIT claims or new data purchases.

Audit support: `warehouse_schema.json`, `loop_schema.json`, `universe_inventory.csv`, `candidate_catalog.csv`, `registry.csv`, `query_timings.json`, and the named CSV extracts. `audit_inventory.py` and `build_catalog.py` preserve the inventory/mapping logic. The catalog is not a loader specification: source paths can identify upstream inputs for derived features, and exact column lineage must still be frozen.
