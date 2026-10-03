# MacroState: prior research, falsification design, and harness fit

Research/design review dated 2026-09-05. Source checkout inspected at `773ae16b5f66a9e5c9b136080d28a03d44a0a571`. No experiments, backtests, database connections, new data collection, registrations, or production changes were performed for this review. Numerical results below are read from existing ledgers/results, not newly reproduced. Scope: existing ASADO inputs, monthly country selection, 12-month USD total-return ranking primary; 6 and 3 months secondary.

## Conclusion

MacroState is not already refuted by ASADO's graveyard. It does face strong adverse priors against discrete regime taxonomies, broad unconstrained searches, and the assumption that economically intuitive states necessarily forecast returns. Its distinctive, falsifiable claim is narrower: **economic compression and predetermined exposure transformations improve a shared model's out-of-sample country ordering relative to the same legal information in an equally well-tuned primitive model.**

Do not impose a standalone-predictiveness gate on every interaction component. The existing research contains a direct counterexample to that screening logic: CAPE extremeness had weak standalone evidence but a stronger interaction with past momentum. This is development evidence worth testing, not a confirmed MacroState signal. Equally, do not use that exception to open all pairwise interactions. Specify a small mechanism-based slate before looking at return outcomes.

The current single-signal harness supplies useful alignment and bookkeeping pieces but is **not by itself a sufficient 12-month pooled-model research evaluator**. It lacks nested, label-maturity-aware fitting and model-selection controls, and its monthly portfolio/Sharpe block measures monthly-rebalanced next-month returns even when the IC horizon is 12 months. A separate frozen research evaluator specification is necessary before running the research ladder.

## What was checked

The graveyard protocol was followed across all five source categories: `.agents/skills/asado-graveyard/SKILL.md`; complete hypothesis and methodology JSONL ledgers folded by latest event; discovery and review of experiment `RESULTS.md` files plus `regime2.md`, `regime_loop/output/state.json`, and `docs/strategy/lessons.md`; and the external Investment Learnings `INDEX.md` and governing `Research-Agenda-2026-07-v2.md`. The relevant Boundaries of Time Series Momentum learning was followed to actual ASADO JSON results. The corpus inventory contains ten `RESULTS.md` paths, including the political capacity/signalling scratch experiment and the learning-loop prototype. These latter reports do not constitute tests of MacroState.

Source hierarchy matters: current ledger events supersede the skill's July counts; actual experiment artifacts supersede summary prose for the scope of a result; the July 13 cost-law retraction supersedes older cost-based language. Existing results were inspected, not certified by rerunning their engines.

### Current ledger state

| Measure | Current result |
|---|---:|
| Registered hypothesis IDs | 64 |
| IDs with at least one verdict | 63 |
| Latest stored verdict: WATCH | 10 |
| Latest stored verdict: DEAD | 26 |
| Latest stored verdict: WEAK | 11 |
| Latest stored verdict: INSUFFICIENT_COVERAGE | 16 |
| Latest verdict primary: 5 trading days | 40 |
| Latest verdict primary: 1 month | 23 |
| Latest verdict primary: 12 months | 0 |

One of the ten stored WATCH rows, `H_20260610_001`, is explicitly **retired with invalid verdict** because `12MRet` was a forward label used as a predictor (`ledgers/hypothesis_ledger.jsonl:1-3`). Thus nine non-retired stored WATCH IDs remain; neither ten nor nine means validated independent live strategies. Two WATCH lead-lag entries also have identical displayed results and must not be interpreted as independent confirmations. The fold's semantics preserve status separately from verdict (`scripts/loop/ledgers.py:332-350`).

The methodology ledger has two registered experiments: flip autopsy **INCONCLUSIVE**, and dispersion throttle **DEAD** (`ledgers/methodology_ledger.jsonl:1-4`). An old skill statement that it contains zero is stale. Several directory experiments still have no corresponding methodology entry; an empty search in one ledger is never evidence of an untested mechanism.

The horizon tally describes the latest **primary verdict** only. Monthly harness runs may also report 3/6-month diagnostics, and the separate Boundaries experiment explicitly studies 12-month outcomes. Therefore “no primary 12-month ledger verdict” is not “ASADO has never examined a 12-month outcome.”

## Which earlier findings bear on this idea?

| Prior experiment | Actual finding and evidence | What it constrains | What it does not establish |
|---|---|---|---|
| Global regime conditioning | Corrected 7-state taxonomy: persistence 0.729, 0/52 factor IC-dispersion FDR passes; OOS Sharpe improvement 0.078 and worse drawdown (`regime2.md:3-18`, `:145-211`). Uses current-vintage FRED; explicit caveat later in report. | Do not revive the same classifier or assume global labels improve country sorting. Avoid rare-regime coefficient tables with tiny cells. | Does not refute continuous state interactions, predetermined country exposures, or a primary 12-month pooled forecast. Report's universal “global macro cannot reorder countries” explanation is broader than the experiment proves. |
| Regime search loop | `regime_loop/output/state.json`: best honest all-pass=0, primary=0, status=error, despite appealing partial metrics. | Search until PASS is not scientific confirmation. | Does not imply every continuous model fails. The often-repeated “13 attempts” count was not verified here. |
| Country HMM early warning | Walk-forward `dP_adverse`: 17/34 negative, median rho −0.003, spread −0.682%/month; full-sample diagnostic spread +0.667% (`regime_ew/results/RESULTS.md:5-11`, `:24-43`). | Reject this early-warning/risk-off formulation; full-sample state fit is not OOS evidence. | Not a test of a shared supervised 12-month model; a separate contrarian claim must retain separate registration/provenance. |
| Country IP-regime factor conditioning | 0/74 pass FDR; real raw hits 18, shuffled-label hits 8. Script explicitly uses forward 1M returns (`regime_factor_selection/results/RESULTS.md:5-13`, `:21-50`; `run_factor_regime_test.py:26-49`). | Strong adverse prior for discrete IP-regime slope switching of the same factor set. | Does not close continuous joint valuation/growth/financial-condition models at 12 months. Placebo used independent sequence permutations; do not copy it as a dependence-valid annual-horizon null. |
| Momentum fragility | Two fixed composites fail conditional 1M reversal among hot momentum names; core rho −0.0135, full +0.0301 (`momentum_fragility/results/RESULTS.md:8-28`). | Keep these composites out of launch scope; do not rename them MacroState fragility. | Does not establish that all stress interactions at all horizons fail. |
| PCA world-state analogs | Roughly 2,900 columns vs 257 prior dates; 73% of nearest analogs concentrated in 2007–2013; overall Pearson IC −0.030 (`docs/strategy/lessons.md:17-66`). | No flattened country×feature vector, global PCA regime manifold, or high-dimensional analog engine. | Named, fixed low-dimensional country concepts are a different representation and a possible response to that failure. |
| First-order macro/valuation/flow ledger trials | Mainly 1M or 5d primary, several real gross/statistical failures; others insufficient. Latest monthly ridge-combiner DEAD; daily combiner WATCH (`hypothesis_ledger.jsonl:150-207`). | Simple baselines must include these prior formulations; do not sell standalone revival as novelty. | A first-order death does not logically refute interaction value or changed primary horizon. No free reset of family trial accounting. |
| Flip autopsy | Original four macro axes do not explain network-family decay; later EWS addendum finds some state dependence, without explaining the flip (`experiments/2026_07_flip_autopsy/results/RESULTS.md:9-16`, `:54-76`). | Do not cherry-pick the July headline as proof that every state interaction is useless; do not claim current-weight graph scores are clean generic raw factors. | Does not validate 12M macro transmission. “State-independent” is bounded to the tested axes and original experiment. |
| Network capture | August re-verdict: 6 WATCH/8 WEAK/5 DEAD/4 insufficient; next-session ETF open→close gross returns negative, ETF close→close positive but much smaller than local indices (`experiments/2026_08_network_spillover_capture/RESULTS.md:19-57`). | Clock and instrument must be explicit; a local-index win is not automatically ETF alpha. | Fast transmission failure is not a veto on monthly-decision annual-horizon selection. Cost diagnostic failures are not research kills. |
| 12M Boundaries replication | Month-clustered t −2.54/−2.62 becomes Driscoll–Kraay −1.05/−1.67; 8/16 countries support, 8 oppose (`experiments/2026_08_boundaries_tsm/RESULTS.md:11-58`). | Dependence-robust inference and country breadth are indispensable. | Does not refute all valuation interactions; the aggregate construction may dilute a better constituent. |

### The positive, bounded prior that changes the sequence

`experiments/2026_08_boundaries_tsm/results/d1_olympics.json` records a registered CAPE interaction coefficient −0.3472, t_DK −2.8777, above the three-test Bonferroni bar 2.39; 14/21 tested countries have the paper's sign. Standalone extremeness t_DK is only −0.8485. REER and credit-gap interactions fail. These are actual stored JSON numbers, not a claim copied only from the external index.

This directly shows why “each concept must pass alone before interactions” is an invalid design rule. It does **not** show confirmed OOS investability: JSON labels the finding in-sample, reserves history from 2021-08 and Brazil/ChinaA/India/Poland, and the companion learning reports the holdout untouched. This review did not open those holdout outcomes. The candidate is now known development evidence and cannot be described as a new prediction after this report.

The same experiment reports correlation 0.0279 between own-history and peer-relative “Boundaries,” with sign changes on identical rows (`RESULTS.md:72-104`). Thus time-series unusualness and cross-sectional cheapness are separate economic variables. Treating them as interchangeable normalizations can silently switch hypotheses.

### Cross-project lessons that transfer, with their limits

The external `Investment Learnings/INDEX.md:15` records a source-date mismatch that inflated a 600-factor ElasticNet by 5.1 percentage points/year before correction. This is a strong concrete warning: provenance applies to the primitive observation, not merely a source name. A reference-period date, availability timestamp, and decision timestamp are distinct. A delayed current-vintage observation is not magically a historical vintage.

`INDEX.md:18` records factor-return residualization destroying the T2 strategy. It does not prohibit diagnostic spanning regressions or adding price controls. **Keep the agreed USD excess-return target; compare controlled and uncontrolled forecasts.** Do not silently replace the target with globally residualized returns and then kill useful systematic return selection because it contains beta or style exposure.

`INDEX.md:21` records next-month factor-ranker flexible models failing against trailing means; `:24` records a Macrosynergy economic-surprise replication failing gross with survey surprises rather than the paper's proprietary vintage states. These are adverse priors about estimator variance and signal-definition fidelity. Neither says a gold macro paper can be faithfully replicated using convenient substitutes, nor refutes the distinct MacroState equity hypothesis. The plan should clearly state it is inspired by the paper, not a gold replication.

Cost gates are withdrawn by the governing external agenda §0.3 item 1 and by current harness code (`scripts/harness/evaluate_signal.py:602-604`). Evaluate research gross. Earlier gross-positive/net-negative deaths count as untested on research merit; do not restore turnover or transaction-cost kill criteria from the seed or old summaries.

## Current harness: reuse, limits, and pre-experiment requirements

| Area | Verified source behavior | Required MacroState specification |
|---|---|---|
| Horizon | Monthly defaults `[1,3,6]`, daily `[5,21,63]` (`evaluate_signal.py:164-165`). `align_monthly` accepts arbitrary integer horizon (`:199-241`); registered primary is enforced when supplied (`:859-870`). | Explicitly register 12 primary, secondary 6/3; do not reorder horizons after inspection. |
| Label arithmetic | Cumulative log differences compound return months M+1+lag through M+lag+h (`:205-234`). | Validate complete interior monthly paths, unique country-months, and all h returns. Static review finds endpoint checks but no interior-count assertion; an internal missing month could create a short effective window. This is a source-level concern, not a runtime-reproduced bug. |
| Availability vs clock | Daily minimum execution embargo one day (`:171-179`); source publication lag machinery distinct. Monthly zero execution-lag convention remains (`:811-815`). | Define month-end global information cutoff and first executable entry. A next-month label alone does not prove all month-end global closes were simultaneously available. Use existing daily return data for a one-session delayed robustness route if available. |
| Fitting | Evaluator loads an already-built signal, then computes IC (`:778-839`). No nested fitting, purged CV, feature selection, or train-only transforms in this function. | Freeze outer temporal folds; fit only examples whose full forward label is known by training cutoff. Fit scaling, imputation, concept weights, feature selection, exposure estimation and all hyperparameters inside nested matured training data. |
| Inference | One IC per date; Bartlett NW with `max_lag=h` (`:256-272`, `:847-850`). | Useful diagnostic, not sole annual-horizon gate. Paired time-block bootstrap of full cross-sections for model differences; prespecify 12/24/36-month block sensitivity. Do not shuffle country-month rows independently. |
| Portfolio horizon | Monthly branch always calls 1M alignment (`:893-897`), regardless of IC primary. | State whether the portfolio is reranked monthly on 12M predictions, or a 12-tranche 12M holding portfolio. They answer different questions. Primary forecast metric and primary portfolio convention must both be frozen. Never compound overlapping annual labels as monthly returns. |
| DSR | `SR_period − E[max SR_N]`; PSR-style probability also returned; trial noise SE scales with raw n (`:540-576`). | Retain family accounting, but do not label positive stored DSR a 95% probability of skill. No serial-dependence adjustment appears in this block. Use paired block uncertainty/max-statistic controls for selection over model arms. |
| History gate | Monthly minimum 60 aligned dates, regardless of forecast horizon (`:880-885`). | Sixty overlapping annual forecasts are not sixty independent annual experiments. Report actual date span, mature evaluation windows, broad cycles and block-bootstrap uncertainty; call insufficient evidence when intervals are too wide. |
| Trial counting | Canonical family counts resist relabeling (`scripts/loop/ledgers.py:310-329`). | One research program with explicit constituent trial charges. Nested tuning budget disclosed. A model trying ten interaction sets cannot masquerade as one unsearched trial. |

These are design requirements for an isolated research evaluator, not authorization to patch the production harness now. Do not invoke the existing evaluator just to inspect it: it opens loop storage and writes results/verdicts. This review used source and static artifacts only.

## Concrete falsification controls

1. **Information-equivalent comparison.** Primitive ridge, concept ridge and primitive+concept ridge receive the same legal primitives, rows, missingness fields and tuning effort. Linear deterministic concepts add no new information to primitives; improvement would represent regularization/parameterization or handling of missingness. A matched group-penalty primitive model is a particularly strong control. Compare a nonlinear primitive model against nonlinear concept models before crediting hierarchy itself.

2. **Separate compression from transmission.** Freeze a small concept map first, then add a separate short slate of exposure×global-shock interactions. Include both shock and exposure main terms, center using training-only statistics, and preserve structural exposure direction. Compare actual exposures with neutral exposure and static training-estimated country effects. Permuting exposure assignments within plausible macro groups is a destructive diagnostic, not automatically a formal valid p-value: countries are not exchangeable.

3. **Country identity is not macro identity.** US, NASDAQ and US SmallCap share macro releases; ChinaA/ChinaH share many national observations (`regime_factor_selection/results/RESULTS.md:17`; `config/country_mapping.json`). Keep separate asset returns/valuation/market state but one macro identity. Use macro-identity-balanced training as a preregistered primary or sensitivity; report both conventional EW-eligible-market benchmark and identity-balanced sensitivity. Group related sleeves in country holdouts and contribution analysis. Do not count copies of a US release as three independent macro shocks. This is a statistical correction, not a user-unapproved change of investment universe.

4. **Price and macro confounding.** Give momentum, value, trailing volatility, observed FX and country/region effects a strong common baseline. Report incremental return-ranking skill from non-price macro alone, price-derived financial conditions alone, and their union. Hold the return target fixed. Diagnose output correlation and gross P&L spanning against the baseline; a shared beta does not itself prove redundancy. No future realized beta or future sector weights in features.

5. **Global-state identifiability.** A global scalar is identical across countries on a date and cannot alone change a linear cross-sectional ranking. It can matter via country exposures or state-dependent local slopes. A date-demeaned ranking target naturally removes common level prediction. This makes global×transmission interactions a necessary modeling question, not optional ornament. Country dummies identify historical means, not economic transmission; test whether structural exposures beat shrinkage country effects.

6. **Temporal dependence and scarce cycles.** Bootstrap contiguous time blocks while preserving the entire cross-section and paired forecasts. Use the same resamples for treatment and baseline, primary endpoint difference and max-statistic over the frozen model slate. With only a few broad cycles, a nominal small p-value is fragile; report bandwidth/block sensitivity and leave-period-out results. A 12M prediction refreshed monthly creates overlapping targets even if the traded portfolio's monthly P&L is non-overlapping.

7. **Construct-preserving nulls.** Use synchronous block/circular shifts of the whole macro-state panel relative to outcomes, avoiding shifts within the 12M label overlap and excluding wraparound joins from formal comparisons. These preserve much more dependence than iid label shuffles. Test fitted interactions against main-effect-only models and shuffled-state diagnostics. Permutation feature importance with correlated concepts is descriptive only; group ablations with full nested refitting provide stronger evidence.

8. **Survivorship and eligibility.** A fixed contemporary T2 universe supports a statement about these current markets, not all historical investable countries. Membership and observation eligibility at each decision must be independent of future 12M survival. Missing terminal returns, suspended markets and short histories cannot be dropped after outcomes are seen. Record coverage/eligibility attrition and compare all arms on one common eligible set. A complete-case sample selected from future return availability needs explicit disclosure and stress checks.

9. **Attribution breadth.** Report market and macro-identity contribution to active P&L, top-1/top-3 shares, positive-contribution count, leave-US-complex-out and leave-largest-contributor-out results, plus period/regime breadth. Country sign counts alone are insufficient and need not all agree under a heterogeneous-transmission theory. Explain prespecified subgroup sign differences; do not discover a subgroup after failure and claim that as the original success.

10. **No retrospective clean lockbox claim.** Recent years have appeared repeatedly in earlier ASADO research. Declare a least-touched historical confirmation interval conditional on prior project exposure, not absolutely virgin history. Freeze the final model before opening it; if any choices change, record a new hypothesis and require new confirmation. Forward shadow beginning after the freeze is the only clearly unobserved future. A reserved holdout in a prior experiment is not automatically available as a virgin MacroState lockbox across all other projects.

## Recommended research decision tree

Proceed to a **data-legality and sample-feasibility stage**, not training. Enumerate existing legal primitives by concept and audit their actual availability/revision lineage. If the surviving data cannot furnish enough mature 12M OOS time blocks, conclude “not identifiable from existing ASADO history,” rather than substituting latest-vintage macro or silently making 1M the primary.

Then preregister the smallest additive concept model and a small, fixed interaction slate concurrently. Standalone screens are descriptive mechanism diagnostics and redundancy checks, not permission gates for interaction inputs. Compare to matched primitive ridge, value+momentum and equal-weight baselines under nested label-maturity-aware folds. Test partially pooled structural slopes only after a pooled model shows incremental skill; 34 independent country models and learned embeddings are expensive controls/extensions, not launch necessities.

A failure of concept-only compression should kill that compression choice, not automatically every transmission interaction. A failure of the final richer model against matched primitives should stop architectural escalation. A gain attributable entirely to momentum/valuation should be described as improved expression of those inputs, not new macro information. A statistically uncertain but positive estimate earns “inconclusive,” not “DEAD” or “proven.” Gross-negative or robustly non-incremental results end the relevant preregistered branch. No cost/turnover research gate applies.

## Evidence boundaries

This report establishes what the local research record says and what the inspected evaluator does. It does not establish MacroState predictive value, historical PIT legality of every seed factor, or future investability. Prior performance artifacts were not rerun. The external agenda's old numerical counts and universal “laws” are contextual prior judgments; current artifacts and exact hypothesis scope take precedence. No original seed, shared skill, ledger, database, production script or external Investment Learnings file was modified.

## Additional prior-art lane: existing Quantpedia mirror

Ran the `quantpedia-prior-art` skill's read-only local script with three lexical queries and six results each: `macroeconomic country equity`, `economic regime`, and `conditional valuation`. No mirror resync or new data acquisition was performed. The inspected mirror reports **1,312 strategies**, 603 with a Quantpedia OOS Sharpe and 534 downloaded daily histories, **synced 2026-08-04**. This is a month-old snapshot as of this report, not freshly verified vendor performance. Eighteen distinct returned entries include five numerical country-screen classifications (2 OURS_ONLY, 2 ADAPTATION_KILLED, 1 HOLDS_BOTH), two feasibility triage records and eleven UNSCREENED entries. No DIES_BOTH result appeared in these limited lexical queries.

| Most relevant catalog hit | Exact local classification | Scope and implication |
|---|---|---|
| #0996 Macroeconomic Momentum in the Cross-Sectional Equity Market Indices | **NOT TESTED (triaged out)**; custom data import | Closest concept match: Zhang/Kappou/Urquhart's economic momentum; no tracked Quantpedia OOS. This is not an ASADO negative result. Its headline paper Sharpe is prior-art metadata, not independently audited evidence. |
| #0987 Economic Trend in Futures | **UNSCREENED** | Economic/price trend complementarity; different multi-asset task, no tracked native OOS in mirror. Supports a question, not the MacroState hierarchy. |
| #1046 Dynamic Asset Allocation with Asset-Specific Regime Forecasts | **UNSCREENED** | Asset-specific regime forecasting exists in prior art; multi-asset allocation and daily clock differ. No tracked native OOS. |
| #1160 Geo-Informed Equity Signals | **UNSCREENED** | Country-structure-aware ML is not conceptually novel; catalog says 2021–24 backtest, no native OOS series. Especially weak as validation for a 12M model. |
| #0922 Price-Based Quantitative Strategy for Country Valuation | **ADAPTATION_KILLED** | Native OOS Sharpe 0.55 vs country adaptation −0.96 percentage points/year relative to EW in the stored Full comparison. It is an expression/implementation-specific adverse prior, not a death of all valuation interactions. |
| #0015 Momentum Factor Effect in Country Equity Indexes | **OURS_ONLY** | Country adaptation +1.02pp/year relative to EW; native inception Sharpe prints 0.30 at the classification boundary. Treat boundary category softly and keep simple momentum as a control. |
| #0404 Alpha Momentum in Country and Industry Equity Indexes | **OURS_ONLY** | Comparison file says +2.35pp/year, screening table says +1.47pp/year: different stored runs/specifications, not two replications to average. Strong reason to benchmark exact local construction, not lift a convenient published number. |
| #0143 Momentum and Trend-following in Country Equity Indexes | **ADAPTATION_KILLED** | Native inception Sharpe 0.50; local full active −7.31pp/year. The adaptation can fail while a native method works. |
| #0266 Skewness Effect in Country Equity Indexes | **HOLDS_BOTH** | Stored full-period classification positive, but local three-year active −6.91pp/year. A Full-window label can conceal recent deterioration. Not a requested new factor. |
| #0244 Long-Term PB Ratio Effect in Stocks Combined with Momentum | **NOT TESTED (triaged out)** | Fundamental stock-universe data requirement; no local country-expression verdict. Native valuation-plus-momentum record is not directly the proposed concept model. |
| #0494 Pro-Cyclical Stocks and Expected Future Economic Conditions | **UNSCREENED** | Native OOS inception Sharpe −0.27 despite positive paper metadata; stocks, not country indices. Illustrates adverse publication-to-tracking evidence. |

Other query results are more distant FX, factor-allocation, BAB and options strategies. Lexical search is not a full semantic literature review. The two named screen inputs are `Quantconnect/report/qp_vs_our_screen/run_*/comparison.xlsx` (latest directory chosen by script) and `Quantconnect/report/screening_report.xlsx`; source catalog is `Quantconnect/quantpedia/mirror/strategy_master.parquet`. **“Net” in these screen tables means excess over the equal-weight benchmark, not transaction costs.** These gross-active adaptation failures are therefore not vacated by the cost-law retraction.

## Independent design debate on the plan draft

This review is an independent reasoning pass over `RESEARCH_PLAN.md` sections 6–10, not a substitute claiming to be Sakana output. The parent reported Sakana unavailable due to exhausted service credits; no Sakana conclusion is inferred.

### Strongest argument for rejecting the preferred architecture

The hierarchy may be an interpretability prior that loses precisely the information needed for returns. Economic health and stock returns have different signs at different valuations; an equal-weight growth concept can cancel a survey revision that matters against a lagged hard-data level that does not. Country exposure mappings can be right for domestic GDP but wrong for listed exporters and multinationals. Partial pooling can then use country slope deviations to repair errors created by the concept map, giving a misleading impression that the elaborate hierarchy was necessary. With few independent cycles, apparent economic coherence is an especially persuasive way to overfit.

A **flat primitive model with honest structured shrinkage and exactly the same predeclared interaction columns** is therefore the strongest challenger, not a deliberately underpowered plain linear straw man. If it matches or beats the hierarchy, the correct outcome is a flat forecast model plus descriptive concept summaries. If neither beats value/momentum, decline the forecasting project even if the macro-state story is attractive. No priori theorem favors the named concepts.

### Five concrete draft changes requested

1. **Remove comparator-selection ambiguity.** “Strongest prespecified primitive baseline” must mean either a fixed B2 primary with B3 secondary, or a completely specified recursively selected baseline using only matured inner folds at every outer refit. Selecting B2/B3 by the aggregate development-OOS performance and then reporting a selected pair's naive confidence interval is not selection-adjusted. Predeclare all tested candidate–baseline comparisons and the multiplicity family.

2. **Make 0.01-IC and noninferiority rules operational.** A reasonable superiority rule is selection-adjusted lower confidence bound above zero **and** point improvement at least 0.01; it differs from requiring the lower bound above 0.01, which establishes a stronger minimum-gain claim. Noninferiority requires the appropriately adjusted lower bound above −0.01, not a point difference within the margin or a non-significant loss. If uncertainty spans meaningful gain and meaningful loss, call inconclusive.

3. **Resolve nested-sample arithmetic before promising floors.** A 24-month inner validation block contains only approximately two annual spans under 12M labels. Specify a minimum inner training history, number of mature inner blocks and exact calendar feasibility. Initial 120 mature outer origins and 96 outer forecasts do not by themselves ensure that inner model selection has enough usable history. If the data cannot support nested tuning, prefer a predeclared fixed penalty and a narrower claim to opportunistically shortening inner folds. The annual refit/maturity rule itself is sensible: labels must be known by refit, with origin/interval checks at every inner boundary.

4. **Choose the economic horizon explicitly.** Requiring positive monthly-refreshed top-quintile active improvement can reject a model with genuine delayed 12M information and a positive 12-vintage portfolio. Conversely, a 12M-hold portfolio can conceal a useful monthly-refreshed selection effect. Choose one primary economic expression before outcomes; make the other a diagnostic unless both are explicitly necessary for the user's decision. For the stated horizon hypothesis the vintage portfolio is the more direct economic companion; monthly refreshed remains an especially relevant practical comparator.

5. **Account for adaptive later stages.** H1/nonlinear stages selected after development results are later, adaptively motivated trials, not independent confirmation of the initial eight-arm contest. Freeze their limited budget and prerequisites now, use nested selection for a procedural claim, and use historical confirmation once for the finally frozen comparison. Reused development-OOS rows are development evidence. The finite interaction slate should remain runnable even when marginals fail; otherwise this plan could accidentally prohibit its core hypothesis.

Other draft strengths should remain: global additive state cancels from linear cross-sectional ranks; fixed linear C=XA does not add information; shared macro identities constrain replicated US/China observations; all inner return months must exist; whole-cross-section time blocks preserve global dependence; and gross rather than cost-based research decisions follow current user policy.
