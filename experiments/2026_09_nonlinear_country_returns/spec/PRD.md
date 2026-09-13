# ASADO Nonlinear Country-Return Study: Coding-Agent PRD

## 1. Product objective and decision

Build a reproducible research system that answers one question: **does a pre-specified, pooled nonlinear model predict 20-local-session forward country equity returns better than independently tuned regularized linear models, using exactly the same point-in-time-safe observations?**

The primary candidate is a shallow histogram gradient-boosted tree model over 16 fixed economic/context inputs. It must compete against raw-input ridge and state-input ridge, not against an untuned or deliberately weak baseline. Additive trees, quadratic ridge, and raw-input trees distinguish nonlinear main effects, interactions, and the usefulness of economic compression.

The product is a trustworthy experimental verdict and its reproducible evidence. A valid negative result is a successful delivery. Model promotion is not the coding agent's optimization objective.

### 1.1 Status and authority

This is the implementation specification, version 1.0, dated September 13, 2026. It develops the previously supplied `ASADO_Nonlinear_Training_Design.md` and draft registration into an end-to-end engineering plan. It is **not a registered experiment, executed backtest, repository patch, or certification that all proposed inputs exist**. Numerical choices below are design requirements for this ticket, not claims about current ASADO defaults or measured performance.

The original brief's exclusions, data facts, gross-only policy, and research governance continue to bind. The original brief and current repository protocol take precedence over an old report; this PRD controls implementation details left open by the earlier nonlinear design. Any material conflict must appear in a decision record before registration. Do not silently choose the version that produces better results. [R1, R2, R4, A1]

The public brief, README, inventory, factor reference, and graveyard were inspected. The active research-protocol file, complete ledgers, original experiment implementation/results files, and private DuckDB data were not successfully retrieved during this specification. Phase P00 requires local verification. The earlier conversational assurance that all needed raw data are available was too strong: documented source families do not establish field-level coverage, forecast-year identity, historical availability, or acceptable vintages.

### 1.2 Users and deliverables

The research owner needs an intelligible answer about nonlinear value and economic mechanism. The coding agent needs exact contracts, bounded choices, test fixtures, and stop rules. A skeptical reviewer must be able to reconstruct every prediction without trusting a notebook or narrative.

Deliver a versioned research package, a feature-availability report, a single common sample, immutable historical forecasts, a complete trial manifest, calibrated statistical comparisons, gross portfolio diagnostics, a verdict, and an opt-in prospective forecast logger. Do not place live trades or change production allocations.

### 1.3 Fixed research contract

| Item | Requirement |
|---|---|
| Primary horizon | 20 subsequent local exchange sessions after entry |
| Primary target | Simple USD total return from the audited T2 total-return index |
| Forecasting unit | Market at a common UTC information origin |
| Model structure | One shared cross-market model; no country embeddings or separate country models |
| Inputs | 24 specified primitives; fixed 16-input economic/context representation |
| Primary learner | `N_S`: histogram boosting, maximum depth 2, maximum 4 leaves per tree |
| Core baselines | `L_X` raw ridge; `L_S` state ridge; inner-selected `L_star`; pooled mean `B0` |
| Controls | Additive trees `A_S`, quadratic ridge `Q_S`, raw-input trees `N_X` |
| Training loss | Equal-origin-weighted squared error on unmodified forward returns |
| Estimation history | Eight calendar years, rolling |
| Parameter updates | Quarterly; hyperparameters retuned annually in July |
| Evaluation | Frozen chronological replay; paired origin-level inference |
| Signal quality | Gross; no cost or turnover promotion/kill gate |
| Data acquisition | Audit existing data first; no unapproved purchases, refreshes, or new providers |
| Production behavior | Research and paper forecasts only; no trades or automatic promotion |

### 1.4 Out of scope

Do not build a regime classifier, HMM, latent-state search, factor-selection-by-regime system, autonomous search-to-pass loop, survivor-only combiner, PCA analog engine, transformer, deep graph network, or reinforcement-learning portfolio optimizer. Do not add ETF flows, CDS, foreign flows, broad revised macro histories, news embeddings, learned lead-lag edges, or fundamental twins to this ticket after inspecting results. They require separately registered extensions.

Do not change target direction, horizon, normalization, universe, missingness policy, source tenor, portfolio rules, or thresholds to rescue a failed result. Do not reopen historical DEAD mechanisms merely by renaming their variables. Marginally unsuccessful variables may be conditioning inputs here because the registered hypothesis concerns their joint conditional relationship, not renewed standalone claims. [R1, R4]

## 2. Study workflow and authority boundaries

The implementation proceeds through the phases below. Phases are dependency gates, not deadlines. The agent may implement independent modules in parallel, but may not advance the actual experiment past an unmet gate.

| Phase | Objective | Main deliverable | Exit condition |
|---|---|---|---|
| P00 | Reconcile repository, research rules, and environment | `reconciliation.md`, source map, environment lock | Rules and compatible registration path verified |
| P01 | Audit field-level availability and snapshots | Bound feature manifest, coverage report, immutable snapshot | Required inputs have defensible PIT contracts |
| P02 | Build clocks, calendars, and target labels | Calendar and label service with fixtures | No outcome-derived timing; targets reconcile |
| P03 | Build causal primitives and economic representation | Feature builders and lineage store | Exact definitions and PIT canaries pass |
| P04 | Freeze common sample and split engine | Panel, masks, fold manifests | Matched rows and label-maturity assertions pass |
| P05 | Implement and test all estimators and inference | Model adapters, synthetic tests, benchmark profile | Deterministic fits, loss, support, and statistical tests verified |
| P06 | Finalize and register bounded experiment | Signed/hash-locked protocol and exposure log | No unresolved blocking bindings; registration recorded |
| P07 | Execute null/power controls and historical replay | Immutable predictions and full fit records | Complete planned runs; no outer-result-driven changes |
| P08 | Evaluate primary forecast superiority | Paired metric tables, intervals, primary verdict | All primary tests computed without model selection |
| P09 | Evaluate mechanism and fragility | Conditional contrasts, support-aware explanations | Claims limited to registered evidence |
| P10 | Evaluate gross economic relevance and reconcile harness | Daily marked P&L, harness evidence | Forecast and portfolio claims kept separate |
| P11 | Produce final verdict and reproducibility handoff | `RESULTS.md`, model card, audit archive | Reviewer reproduces reported numbers |
| P12 | Optional prospective shadow operation | Immutable live forecast/outcome stream | Owner approves schedule; no execution authority |
| P13 | Optional separately registered neural extension | Tiny skip-connected network study | New registration; not a failed-tree rescue |

### 2.1 Two types of approval

Routine implementation proceeds without repeatedly asking the owner to choose technical details already fixed here. Approval is required for material scientific amendments, external purchases, modifying production jobs, and signing the final registration. The agent must return a concrete blocker report rather than fill an unresolved input with a plausible guess.

P06 registration can be recorded by the repository's authorized mechanism. The implementing agent must not invent an independent-review approval. A separate reviewer or owner must attest to the locked protocol when local governance requires it.

### 2.2 Study state machine

Use append-only events with these states: `DRAFT`, `AUDITING`, `BLOCKED_DATA`, `BLOCKED_GOVERNANCE`, `ENGINEERING_READY`, `REGISTERED`, `RUNNING`, `BLOCKED_FIT_SUPPORT`, `INVALID`, `INSUFFICIENT_EVIDENCE`, `NO_ADVANTAGE_DEMONSTRATED`, `HISTORICAL_FORECAST_PASS`, `HISTORICAL_GROSS_PASS`, `SHADOW_ACTIVE`, and `ARCHIVED`.

State names describe this study; they are not replacements for ASADO's native ledger verdicts. Record a verified mapping to those verdicts in P00. A missing proof of provenance is not a negative alpha result. A failed statistical gate is not an implementation defect to repair by searching.

Every state transition records event time, actor, preceding event hash, reason, artifact hashes, and registration version. Amendments append; they never overwrite old specifications or erase failed configurations.

## 3. Repository architecture and operational safety

### 3.1 Proposed new paths

The paths below are proposed additions, not assertions that these modules exist. Reuse verified repository utilities when their contracts match; do not duplicate tested infrastructure needlessly.

```text
research/nonlinear_country_returns/
    README.md
    PRD.md
    cli.py
    contracts.py
    config.py
    sources.py
    snapshot.py
    calendars.py
    labels.py
    features.py
    graphs.py
    consensus.py
    concepts.py
    panel.py
    splits.py
    preprocessing.py
    models/
        baseline.py
        ridge.py
        hist_boosting.py
        leaf_support.py
        neural.py                 # disabled extension
    selection.py
    replay.py
    controls.py
    evaluation.py
    portfolios.py
    reporting.py
    shadow.py
    governance.py
    config/
        study.template.json
        feature_manifest.template.yaml
        schemas/
    tests/
        fixtures/
        unit/
        integration/
        property/
        regression/
    results/
        RESULTS.md                # sanitized summary, not licensed raw data

Data/work/nonlinear_country_returns/<study_id>/<run_id>/
    snapshot/
    manifests/
    raw_features/
    normalized_features/
    labels/
    panels/
    folds/
    fits/
    predictions/
    controls/
    evaluation/
    portfolios/
    reports/
    events.jsonl
    artifact_index.json
```

Use existing package conventions discovered in P00 for importability and test layout. Provide one command-line entry point; notebooks may illustrate results but cannot be the only implementation.

### 3.2 Data lifecycle

Open source databases read-only. Do not create permanent study tables in `Data/asado.duckdb`; the repository documents that its rebuild recreates that warehouse. Use a research-owned work directory and, only through an approved migration/adapter, namespaced metadata in the loop database. Preserve the current nightly loop. [R2]

Create consistent logical exports or coordinated checkpointed copies. Do not blindly copy a live DuckDB file while a writer is active. Establish an application-level collection watermark across the two databases: separate consistent database snapshots are not automatically a mutually consistent cross-database snapshot. Record each source's last completed batch and reject a snapshot taken midway through a required collection stage.

Use a dedicated output writer. Worker processes read immutable Parquet extracts, not live source databases. Outputs are written to temporary files and atomically renamed. A restart may reuse an artifact only when source, configuration, implementation, split, and environment hashes match.

### 3.3 Reproducibility and compute

Pin the actual compatible installed versions after local inspection; do not blindly upgrade production dependencies to a web documentation version. Record Python, scikit-learn, NumPy, SciPy, DuckDB, Arrow, compiler/BLAS, OS, and thread settings. Float64 is the default for features, labels, and statistical calculations. Persist random seeds and canonical row/column order.

Initial execution is CPU-first: one fit process, at most eight compute threads, and an explicit memory budget, initially 32 GiB if available. Benchmark one complete inner selection cycle and one synthetic control replication before approving an expanded resource budget. Record measured runtime and peak memory; do not promise unmeasured throughput or request cloud GPUs for this tree study.

Numerical reproducibility is defined as predictions equal to absolute tolerance `1e-10` on the pinned environment, and exactly matching row keys, selected configuration IDs, gate outcomes, and canonical data hashes. Cross-platform equality may use a separately documented tolerance; it cannot conceal different selected models.

No credentials, licensed raw data, machine-specific private paths, or trained models containing restricted data go to public Git. Do not install schedulers, run collectors, shut down existing services, or refresh Bloomberg data merely to make the audit green.

## 4. P00 - Repository and governance reconciliation

### Objective

Establish what the local repository actually requires and which components can be reused before adding code or conducting a model search.

### Required work

Read `README.md`, `CLAUDE.md`, `AGENTS.md`, `docs/README.md`, the original ASTRA brief, the database inventory, factor reference, research-protocol skill, graveyard, and relevant change-control instructions. Read the original results for `regime/`, `regime_ew/`, `regime_factor_selection/`, `momentum_fragility/`, and `docs/strategy/lessons.md`. Inspect ledgers and their event-folding implementation, including methodology records where present.

Pin the local commit, branch, dirty-diff hash, and repository root. Run the existing PIT smoke tests, including the documented `tests/loop/test_harness_pit.py`, if present. Record pre-existing failures separately from new failures. Inspect the actual harness's alignment, top/bottom membership, holding periods, Sharpe, Newey-West, DSR, family trial accounting, and gross-only logic.

Produce a side-by-side contract table: this PRD's requirement, current implementation behavior, evidence path/line or test, proposed adapter, and blocking status. Historical prose about transaction costs does not overrule the explicit retired-cost policy. Verify the implementation rather than declaring it compliant from a comment. [R1, R2, R4]

Do not infer research novelty solely from the single-variable hypothesis ledger. The graveyard explains that directory-level methodology experiments have not always fit that registration shape. Identify the supported methodology registration route and preserve inherited research history. [R4]

### Deliverables and acceptance

`reconciliation.md` identifies every required reading and actual status; `source_map.json` identifies reusable modules; `environment.lock` pins dependencies; `governance_binding.json` identifies registry, ledger, family accounting, and gross gate adapters. The working tree remains untouched except for explicitly listed study files. Missing mandatory governance yields `BLOCKED_GOVERNANCE`; synthetic engineering can continue, but real experimental evaluation cannot.

## 5. P01 - Data readiness, source binding, and snapshot

### Objective

Determine whether the proposed experiment is possible with existing ASADO data, without assuming that a table's date range means every field has that history.

### 5.1 Required source families

The inventory identifies the main daily T2 tables and loop sources such as `market_implied_daily`, `sovereign_daily`, `consensus_daily`, `consensus_revisions`, `graph_features_pit_daily`, and `graph_edge_vintages`. These are discovery targets, not pre-validated SQL selectors. Inspect schemas, collectors, source identifiers, units, countries, and update conventions locally. [R3, R5]

For every primitive P01-P24, populate a manifest with database, table/view, selector, value field, market/entity key, source series/ticker, quote/units, observation date, reference period, forecast year where relevant, historical availability rule, recorded/ingestion time, vintage/version policy, source calendar, freshness limit, and transformation lineage.

A field is not READY merely because its values are non-null. Distinguish `VERIFIED_HISTORICAL_AVAILABILITY`, `DOCUMENTED_CONSERVATIVE_AVAILABILITY`, `UNVERIFIED_TIMING`, `REVISED_WITHOUT_VINTAGES`, `MISSING`, and `INSUFFICIENT_COVERAGE`. Only the first two may enter a primary claim; the latter must carry its assumptions and prescribed additional-lag sensitivity.

### 5.2 Coverage audit

Report feature-by-market first and last eligible dates; non-null and usable observation counts; daily update frequency; maximum gaps; last observation age; historical vintage availability; join multiplicity; and provenance quality. Show the coverage lost sequentially to source absence, warm-up, freshness, zero scale, graph support, and the common 24-input mask.

Map the 34 intended T2 markets from the brief explicitly. Distinguish market, economic entity, sovereign, currency, exchange, time zone, and graph node. Do not insert zero USD carry to force U.S.-related markets into a universe for which that signal is undefined. Do not assume the eventual sample is exactly 28 markets or starts in July 2010. Those are prior planning facts, not the selection rule for this narrower manifest. [R1]

Determine the first eligible feature origin from the locked feature-only rules, then the first eligible July refit after eight calendar years. Do not select a start date by inspecting return predictability. Earlier warm-up observations are allowed and must be loaded.

### 5.3 Publication, observation, and recording times

Store `observation_at`, `reference_period`, `published_at`, `historically_available_at`, `captured_at`, `vintage_id`, and `availability_evidence` separately. An annual reference date is not a publication time. A historical vendor series retrieved today does not become historically unavailable merely because its present ingestion time is recent; its historical availability needs separate evidence. Conversely, a date-stamped latest revision is not an original vintage.

For documented market closing data without intraday publication time, use a conservative policy of availability at 23:59 UTC on the next UTC business day after the source observation date, unless a documented later source release requires more delay. For historical consensus dates, this conservative rule is admissible only when the vendor date is demonstrably the date the forecast was published/stored, not a backfilled period label. Bind the exact rule per source before registration.

A lag is not a repair for unknown macro revisions, unknown graph vintages, or an unidentified forecast target. Those remain blocked. For every inferred availability policy, run the pre-specified additional-one-source-session-lag sensitivity later; it cannot replace the primary clock.

### 5.4 Data-readiness decision

Required conditions: all 24 primitives have bound definitions; every admitted row has acceptable timing; at least 20 eligible markets per scored origin; sufficient initial history for the registered nested fits; at least 756 planned mature outer origins; and at least 80% of candidate origin dates retained in each full outer calendar year. These last two are engineering/evidence-floor choices, not estimates of statistical power.

If these requirements fail, deliver the measured feasible panel and the exact source limitations. Do not silently drop banking features, change options tenors, fill missing carry, select a smaller favorable period, or shorten the estimation window. Return `BLOCKED_DATA` or `INSUFFICIENT_EVIDENCE`; propose a clearly versioned amendment without evaluating the amended model. The owner can then decide whether to approve it.

### Deliverables and acceptance

Produce `feature_manifest.bound.yaml`, `availability_evidence.md`, `coverage_by_feature_market.parquet`, `coverage_waterfall.json`, `market_map.csv`, `snapshot_manifest.json`, and `data_readiness.md`. Snapshot hashes must reproduce; required source bindings must have no unresolved placeholders. This gate may pass with explicitly documented conservative timing, but cannot pass with unknown timing disguised as a lag.

## 6. P02 - Independent calendars, clocks, and labels

### 6.1 Origin calendar

Build an independent exchange-session calendar for each market, including historical holidays, exceptional closures, time zones, daylight-saving changes, and scheduled/actual close times. Validate against source index observations without using forward returns to decide whether a session existed.

Candidate origins are UTC dates on which at least 20 mapped markets have a scheduled local session whose close falls on that UTC date. Set the signal cutoff to `23:59:00 UTC`. A market's primary row additionally requires a scheduled local session on that origin date and an eligible latest index observation under its historical availability/freshness rule. A delayed source can therefore contribute the prior session's close. Do not use a record unavailable at the origin to determine eligibility. Holiday exclusions are established from the calendar, not from the future outcome.

The repository's outcome-derived `daily_calendar` may be used as a reconciliation diagnostic, not as the authoritative calendar for new labels or live features. It must not suppress the newest origin. [R1]

### 6.2 Entry and exit

For market i and origin t, `entry_at` is the first scheduled local exchange close strictly later than `origin_at`. Count entry as session zero. `exit_at` is the close after 20 additional local sessions. Store planned timestamps before observing returns and actual timestamps/quality separately.

Example: when Monday's local session has already closed by Monday 23:59 UTC and Tuesday is a normal session, entry is Tuesday's close. No Tuesday price can enter Monday's features. A local holiday moves entry to the next actual scheduled session; it does not create a zero-return trading day.

The primary label is `TRI_USD(exit) / TRI_USD(entry) - 1`. Verify index currency, dividend treatment, and any historical index substitution. For a local-currency index, use an audited, consistently aligned USD-per-local-currency series; never convert an already-USD index twice. The index and FX fixing conventions must be recorded. Do not equate this index-close measurement convention with a guaranteed executable ETF fill.

### 6.3 Label availability and unresolved outcomes

`label_available_at` is the latest historical availability of the two total-return marks and any required FX components. An origin may enter training only when the maximum label availability across all its included markets is strictly earlier than the fit cutoff.

Right-censor the recent evaluation tail using known planned horizons and a common conservative maturity boundary. Do not score only the faster-closing markets near the end of the dataset.

A subsequently missing endpoint, suspension, or terminated instrument must not retroactively remove a losing market from the prediction population. Retain the forecast record. Use a verified official published index mark or terminal cash/recovery value when the outcome contract supports it; do not invent a zero return or forward-fill an unpublished index. If a mature included outcome remains unresolved, primary inference is blocked until it is adjudicated. A last-observation sensitivity may be disclosed, but cannot silently become the target.

### 6.4 Diagnostic horizons

Construct 5- and 63-session labels using the identical clock machinery. In this core ticket, evaluate the **fixed 20-session model's score associations** with those outcomes descriptively. Do not fit or tune horizon-specific replacement models. Their different maturity masks cannot shrink the primary 20-session sample. A diagnostic association does not establish a calibrated 5- or 63-session return forecast.

### Deliverables and acceptance

Deliver calendar provenance, labels, label lineage, and a reconciliation report against existing return surfaces on genuinely matching conventions. Differences caused by the deliberate entry delay must be explained, not forcibly eliminated. Fixtures must cover weekends, market holidays, daylight-saving shifts, non-U.S. trading weeks, zero actual returns, index-currency conversion, terminal values, and the most recent origin. Every entry is strictly after its origin and every exit is exactly H subsequent local sessions later.

## 7. P03 - Primitive features and economic map

### 7.1 Primitive definitions

The IDs below are research aliases. They are not guaranteed literal warehouse columns. All trailing calculations end at the latest observation historically available by the origin and use valid source sessions, not seven-day forward-filled rows.

| ID | Definition | Construction requirements |
|---|---|---|
| P01 | Own trailing 5-session USD total return | Audited index levels and source calendar |
| P02 | Own trailing 21-session USD total return | Same convention as P01 |
| P03 | Own trailing 63-session USD total return | Same convention as P01 |
| P04 | Realized volatility over 21 one-session USD returns | Sample standard deviation, ddof=1; no annualization |
| P05 | Trade-neighbour trailing 21-session USD return | PIT outgoing economic-exposure weights; own entity excluded |
| P06 | Trade-neighbour trailing 63-session USD return | Same edge definition and vintages as P05 |
| P07 | Banking-neighbour trailing 21-session USD return | Audited claims direction and PIT weights |
| P08 | Banking-neighbour trailing 63-session USD return | Same edge definition and vintages as P07 |
| P09 | ATM 3M FX implied volatility | Decimal annualized volatility; exact tenor and quotation verified |
| P10 | ATM 1W implied volatility minus ATM 3M | Both same quote convention and comparable as-of observations |
| P11 | 3M 25-delta FX risk reversal | Signed so positive means local-depreciation insurance premium |
| P12 | 3M FX carry | Decimal, positive for documented local-currency carry; exact annualization bound |
| P13 | Sovereign 2Y yield | Decimal annualized yield; negative yields allowed |
| P14 | Sovereign 10Y yield | Same country/instrument convention as P13 |
| P15 | Sovereign 10Y minus 2Y yield | Matched dates/availability, not independent stale legs |
| P16 | 21-session change in sovereign 2Y yield | Yield difference, not percentage price return |
| P17 | 21-session GDP consensus revision | Next-calendar-year forecast, identical target year throughout window |
| P18 | 21-session CPI consensus revision | Same fixed-target rule as P17 |
| P19 | Count of distinct revision-arrival days in 21 sessions | GDP/CPI simultaneous updates count as one day |
| P20 | Sessions since latest GDP/CPI revision | Capped at 63; actual observed feed required |
| P21 | Global VIX level | Valid source observations; no country tiling before preprocessing |
| P22 | Global MOVE level | Same source-level treatment |
| P23 | Global trailing 21-source-session DXY return | Actual daily source; audited series identity |
| P24 | Global trailing 21-source-session Brent futures return | Fixed, PIT roll/chain convention; no future back-adjustment |

### 7.2 Graph impulse contract

Use `graph_features_pit_daily` only after auditing its formula, or rebuild from verified `graph_edge_vintages`. Never use the retired `graph_features_daily` or today's Neo4j adjacency as historical input. [R1, R3]

Resolve the graph's actual economic direction before registration. For a trade exposure, the default intended quantity is the endpoint's export exposure to destination j. For banking, it is the endpoint's claims exposure to counterparty j. If source tables encode a different direction, mark the binding unresolved rather than transpose or select the profitable orientation without disclosure.

For each endpoint, remove self-entity exposures, select one fixed representative market per source graph entity, retain nonnegative weights, and normalize the admissible outbound weights to one. Duplicate market representations of one economy must not create duplicate neighbour weights. Different equity markets can remain separate prediction outcomes.

Require at least three distinct source entities and at least 80% of the eligible pre-missingness network mass with usable neighbour returns. Renormalize only that observed mass and record the coverage fraction. These are fixed support rules, not performance-tuned thresholds. A legitimate source-currency group shared across markets does not become multiple independent shocks.

At an origin, use each neighbour's latest historically available return. Its source close must be no older than four calendar days and it must not be missing an expected published session under the bound source policy. Carry through scheduled holidays only within that rule. The weight version and every source return endpoint must predate the signal cutoff.

An existing neighbour-minus-own gap is not accepted as an external impulse unless its exact formula permits recovery of both legs. Keep P02/P03 separate from P05-P08 so own-market reversal cannot be mislabeled propagation.

### 7.3 Consensus events and slow state variables

At origin t, define target year F as the next calendar year. Compute changes for that same F at every comparison within the preceding 21 valid local sessions. Do not stitch rolling one-year labels across a year boundary. If the vendor history does not identify F, P17-P20 are blocked.

A revision is a change exceeding the source's documented reporting precision; bind that tolerance, units, and GDP/CPI definitions before registration. Sum signed changes for P17/P18. P19 counts distinct local session buckets to which the source publications first become available. P20 counts valid sessions from the last such event. Carrying an observed unchanged forecast is valid; missing source collection is not evidence of no revision.

A monthly, quarterly, or annual state may persist between releases and interact with daily impulses. It contributes no new release event on those carried days. Store age and publication metadata for audit without adding unregistered model features.

### 7.4 Freshness and PIT transformations

For daily market series, require the latest expected source observation under its bound availability rule, allowing at most one missed source session and at most four calendar days from the source observation. Consensus levels may persist, but there must be evidence the feed was observed within the preceding five local sessions. A retrospective event-only file without feed-observation evidence needs a documented vendor-completeness contract; otherwise zero-event inference is blocked. Graph weights use publication/vintage validity, not daily refresh requirements.

P24 must use a historical convention whose earlier return values do not change when future contracts are appended. A latest back-adjusted continuous series failing this test cannot be treated as PIT. If only a quoted generic-futures level is available, do not quietly relabel its roll jump as a chain-linked return; resolve the definition or amend before evaluation.

### 7.5 Causal normalization

For each primitive and its natural market/source calendar, compute a z-score from up to 252 prior valid observations, excluding the current value, requiring at least 126. Use the sample standard deviation with ddof=1 and clip z to [-3, 3]. Values carried from a genuinely observed slow source remain valid state observations; unknown feed intervals do not. If historical standard deviation is at most `1e-12`, declare that normalized observation unavailable under the primary mask. Do not create an infinite score or silently substitute a pooled scale.

Global inputs are normalized once on their own source histories and joined to countries afterward. Do not demean identical global values across countries. Live trailing normalization may use newly available, unlabeled observations; fold-fitted centering/scaling may not be refitted between model refits.

The term "linear baseline" means linear in these common normalized inputs. Causal clipping and normalization are shared preprocessing, not gains attributable to the tree learner.

### 7.6 Fixed 16-input economic representation

Let Z(P) denote the normalized primitive. Freeze this map without using return outcomes:

```text
C01 = Z(P02)                                      own one-month movement
C02 = Z(P03)                                      own three-month movement
C03 = Z(P04)                                      own volatility
C04 = Z(P05)                                      trade impulse
C05 = Z(P07)                                      banking impulse
C06 = (Z(P09) + Z(P10) + Z(P11)) / 3               options stress
C07 = Z(P12)                                      carry
C08 = Z(P15)                                      sovereign curve
C09 = Z(P16)                                      policy-rate movement
C10 = Z(P17)                                      growth-expectation revision
C11 = Z(P18)                                      inflation-expectation revision
C12 = (Z(P19) - Z(P20)) / 2                       information-arrival intensity
G01 = Z(P21) ; G02 = Z(P22)                       global risk levels
G03 = Z(P23) ; G04 = Z(P24)                       dollar and oil movements
```

The 24-dimensional representation X retains all P01-P24. S contains C01-C12 and G01-G04. GDP and CPI do not cancel in a single macro score. There is no learned state bottleneck. The map intentionally loses some details; N_X and L_X are mandatory controls for that loss.

### Deliverables and acceptance

Every feature cell has a lineage record or compact retrievable lineage identifier, value status, maximum source availability, and transformation version. Unit and property tests must show historical truncation equivalence, future-append invariance, delayed-publication behavior, same-target-year revisions, correct FX signs, graph direction, and no forward-return descendants in the feature dependency graph.

## 8. P04 - Common panel, preprocessing, and chronological splits

### 8.1 Separate features, forecasts, and outcomes

Persist a feature-only panel keyed by `(origin_at, market_id, feature_version)`. Persist labels in a separate outcome store keyed by origin, market, horizon, and label version. A live forecast record never contains an actual future return. An evaluator joins outcomes only after maturity.

Do not build eligibility by inner-joining features to whichever future prices happen to exist. First establish the ex-ante candidate and feature-ready row manifests. Then attach outcome status. A missing mature outcome is an adjudication issue, not permission to revise the forecast population.

The common primary mask requires all 24 normalized primitives, even though S uses only some of them. All eight forecast streams (`B0`, `L_X`, `L_S`, `L_star`, `A_S`, `Q_S`, `N_S`, `N_X`) must cover that same population. Only six learners are independently tuned: B0 is untuned and L_star is a selector. No model-specific imputation, native missing-value branch, or omitted difficult prediction is allowed.

### 8.2 Fold-fitted preprocessing

Fit date-weighted centering and scaling on each training slice only. For X and S, use the same fitted representation transformer for all learners consuming that representation. If a column is constant inside a fold, set its fold scale to one and preserve its zero-centered values; this differs from the upstream rolling z-score's unavailable-observation rule.

Quadratic ridge receives the 16 main effects, their 16 squares, and 120 distinct pairwise products, for 152 predictors before the intercept. Build products after the base S fold transform, then fit a training-only center/scale on all resulting columns. Do not count the intercept twice. Persist feature order and formulas.

Compute training row weights as `w_it = 1 / (T * n_t)`. They sum to one and give each origin equal aggregate weight. Use these weights for fitted centering/scaling as well as model loss. For trees, rescale model-fit weights to have mean one while preserving relative date weights; document the different regularization convention.

### 8.3 Outer schedule

Define model fit cutoffs at 00:00 UTC on the first candidate-origin date on or after January 1, April 1, July 1, and October 1. The first fit is the first eligible July cutoff after eight calendar years from the bound feature-panel start. The model issues forecasts at subsequent 23:59 UTC origins until the next scheduled fit.

At fit cutoff F, retain training origins in `[F minus eight calendar years, F)` for which all included labels are available strictly before F. At the first inner training fit require at least 1,260 usable origins; if the registered schedule cannot meet that requirement, stop rather than shorten the history requirement after seeing a score.

July fit cutoffs retune hyperparameters. Other quarterly fits reuse the previously selected configuration and refit coefficients/trees from scratch on the current matured rolling window. Refit from scratch, not by appending trees trained on a different sample.

### 8.4 Inner schedule

At an annual tuning cutoff, take the latest fully mature training origin as the right anchor. Define four consecutive six-calendar-month validation blocks ending at that anchor. Map boundaries deterministically to candidate origins. At each block start and three calendar months later, fit using only earlier mature labels and the fixed earliest date of the outer eight-year window. Thus each six-month block contains two three-month prediction segments; this matches the outer refit cadence, not necessarily its calendar phase.

Combine per-origin validation losses over all four blocks without giving a shorter block extra weight. Some earlier validation labels may enter training at a later simulated refit once they mature. That is legitimate sequential learning, not a random split.

For every fit, enforce `max(training label_available_at) < fit_cutoff`. Keep every market from an origin in the same role. A fixed 20-row embargo is not a substitute for this timestamp rule across different local calendars.

### 8.5 Visibility and leakage permissions

After registration, the replay runner may read prior matured labels exactly as a historical strategy could. It may not inspect outcomes of the next prediction segment before issuing its predictions. Analysts and agent progress reports may see timing, counts, configuration IDs, fit failures, and inner losses, but not aggregate real outer IC, Sharpe, return charts, or model rankings until all planned primary forecast streams are frozen.

Implement a `LabelStore.read_matured(fit_cutoff, row_manifest)` API rather than passing an unrestricted all-history target array to model selection. Record every label-read boundary. Ordinary file permissions are an additional safeguard, not a claim of cryptographic prevention against someone with full machine access.

### Deliverables and acceptance

Deliver `candidate_rows.parquet`, `eligible_rows.parquet`, `outcome_status.parquet`, X/S panels, preprocessing artifacts, and explicit train/validation/prediction fold manifests. Hash ordered row keys, labels, split memberships, feature versions, and scored outcomes independently. All compared models have the same row/label/split hashes. There must be no random country-day splitting and no future-dependent eligibility.

## 9. P05 - Estimator implementation, synthetic QA, and performance profiling

### 9.1 Models to implement

| ID | Representation | Estimator | Role |
|---|---|---|---|
| B0 | None | Date-weighted matured-training pooled mean | No-information reference |
| L_X | X, 24 inputs | Ridge with intercept | Raw-input linear baseline |
| L_S | S, 16 inputs | Ridge with intercept | State-input linear baseline |
| L_star | None additional | Annual inner-validation selection of L_X or L_S | Stronger procedural linear benchmark |
| A_S | S | Histogram boosting, depth 1, at most 2 leaves | Nonlinear additive control |
| Q_S | 152 quadratic predictors | Ridge with intercept | Explicit second-order interaction control |
| N_S | S | Histogram boosting, depth 2, at most 4 leaves | Sole primary nonlinear candidate |
| N_X | X | Same depth-2 procedure | Raw-input nonlinear control |

There are six independently tuned learners: L_X, L_S, A_S, Q_S, N_S, and N_X. B0 has no tuning; L_star selects an already fitted ridge procedure. No post-hoc ensemble of the outer winners is permitted.

### 9.2 Ridge contract

Minimize `sum(w * (y - intercept - X beta)^2) + lambda * ||beta||^2`, with weights summing to one and an unpenalized intercept. Use 12 logarithmically spaced lambda values from `1e-5` through `1e3`. Tune L_X, L_S, and Q_S independently. Verify the estimator's weight/penalty semantics against a hand-computed weighted closed-form solution. Do not pass an unchanged alpha after rescaling weights and claim it is the same optimization problem. [R7]

Use a numerically stable deterministic solver appropriate to the small dense matrices. Confirm that duplicated rows with halved weights reproduce coefficients and predictions. The no-information forecast is the equally date-weighted historical mean, not a country-row mean.

### 9.3 Histogram boosting contract

Use the verified, pinned scikit-learn implementation for the primary ticket. Its official documentation describes automatic early stopping and native missing-value handling; both require explicit control here. Set `early_stopping=False`, `categorical_features=None`, `warm_start=False`, and `max_features=1.0` when supported by the pinned API. Do not allow accidental categorical country IDs or internal random validation. [R6]

```text
loss                  = squared_error
learning_rate         = 0.03
max_bins              = 16
max_depth             = 2 for N_S/N_X; 1 for A_S
max_leaf_nodes        = 4 for N_S/N_X; 2 for A_S
max_iter              in {25, 50, 100}
leaf_fraction         in {0.025, 0.05}
min_samples_leaf      = max(256, ceil(leaf_fraction * N_training_rows))
l2_regularization     in {10, 100}
early_stopping        = False
random_state          = 20260913
```

Each tree learner has exactly 12 candidate configurations. No Bayesian optimization, random search, deeper trees, random feature subsampling, bagging search, or extra seed selection is permitted. The learner receives original return labels; it does not receive incumbent residuals as a substitute target. Gradient boosting's internal residual fitting is part of the estimator, not target residualization.

### 9.4 Leaf-support audit

After every candidate fit, inspect every terminal leaf of every tree on the actual training rows. Require at least 126 distinct origins, 12 distinct fixed 20-origin bins, three calendar years, and four markets per leaf. Define bins by the origin's index in the frozen base calendar, not by a different subset-specific numbering for each leaf. These are support constraints, not claims that the observations are independent.

Do not assume `HistGradientBoostingRegressor` offers a public `apply()` leaf API. Implement a version-locked read-only tree traversal or a verified supported exporter for the installed version. On fixtures, the sum of exported leaf contributions plus the initial prediction must reproduce `predict()` to `1e-10`. Assert thresholds, missing-routing behavior, shrinkage, and all node field semantics. Isolate any private-API dependency in one adapter and fail on an unknown version; do not silently switch estimator libraries.

A candidate failing support in any inner fit is ineligible for that annual selection. A selected configuration failing support in a later outer refit returns `BLOCKED_FIT_SUPPORT`. Do not drop that quarter, substitute a better-performing model, relax the support thresholds, or select a replacement using outer outcomes. This ticket deliberately specifies no automatic fit-support fallback. Preserve any already issued forecasts and report the incompleteness honestly.

### 9.5 Deterministic selection

For each model/grid candidate, aggregate inner origin-weighted MSE. Let the best admissible candidate have minimum mean loss. For every other candidate, compute its paired per-origin excess loss over the best. Estimate the standard error of that mean using 63-origin moving blocks, 1,000 draws, and a deterministic seed derived from the master seed and fit ID.

Include a candidate in the conservative one-standard-error set when its mean excess loss is no larger than its own block-estimated standard error; always include the minimum-loss candidate. Select the largest lambda for ridge. For trees, order by fewer stages, then larger leaf fraction, then larger L2, then canonical configuration ID. This is a fixed parsimony heuristic, not a hypothesis test.

Select L_star annually between the selected L_X and L_S using their combined inner MSE, with an exact numerical tie resolved in favor of L_X. Keep that selection until the next annual retune. No outer-loss information enters it.

### 9.6 Engineering fixtures

Before registration, exercise the entire software path on synthetic panels with multiple calendars, delayed releases, missing feeds, duplicate entities, sparse revision events, a known linear target, and a known interaction target. Include a fixture with at least eight years of synthetic origins so leaf support and nested chronology are tested, not bypassed.

Unit-test the statistics with deterministic arrays having known MSE, ranks, ties, loss differences, and Holm corrections. Test inference size on synthetic zero-mean dependent paired-loss processes separately from model fitting. A high rate of procedure wins in a linear-data-generating process is not automatically a size error: different finite-sample estimators can have different risks even when the conditional mean is linear.

### Deliverables and acceptance

Deliver adapters, synthetic fixtures, tests, measured fit/memory profiles, and a reusable model artifact format. No genuine outer result is used to debug or choose the grid. Every selected model and leaf audit is reproducible. Any undocumented estimator substitution requires a pre-registration amendment, not a casual engineering shortcut.

## 10. P06 - Registration, exposure log, and locked execution plan

### 10.1 Freeze contents

Freeze the complete feature/market manifests, timing policies, primary/diagnostic labels, panel start, first outer fit, final mature evaluation boundary, X/S formulas, fold schedule, sample mask, grids, parsimony rule, leaf rules, statistical tests, bootstrap seeds, portfolio rules, synthetic generators, sensitivity list, and output contracts.

Bind a source-code commit or commit plus explicit dirty-diff hash, dependency lock, data snapshot hash, registration hash, and approved native harness mapping. Null source selectors, unknown source timing, missing clock maps, and unresolved active gate definitions are blocking. The draft JSON delivered with this PRD is not itself a valid registered ASADO configuration.

Record historical exposure honestly: the project knows the 2024-26 reversal and the earlier failed families. Historical replay is not an untouched holdout merely because this implementation uses nested validation. [R1, R4]

### 10.2 Trial accounting

Record the six learner grids, all 72 configuration definitions, every inner/outer fit, and all fixed diagnostics in the study's trial manifest. Nested candidate fits are not automatically 72 independent final hypothesis claims; conversely, a single methodology label cannot erase the search they represent. Use the verified native family accounting rule for DSR and report the actual search inventory alongside it. Preserve parent-family history and count subsequent scientific amendments.

The retired cost-only WEAK re-adjudication is a separate research task. It must not select this study's predictors or become an extra survivor screen.

### 10.3 Execution authorization

Require a registration record with content hash and approval evidence before reading genuine outer evaluation summaries. Once registered, P07-P11 can execute in order without repeated owner approval for already fixed steps. A source or code correction after any result is exposed creates a new run/version and an exposure event. Re-running unchanged code after a transient I/O failure is not a new scientific specification, but the attempt is still logged.

### Deliverables and acceptance

`protocol.lock.json`, `registration_receipt.json`, `exposure_log.jsonl`, `trial_manifest.json`, `run_plan.json`, and a `validate-registration` command. Validation must reject every unresolved required binding, mismatched hash, forbidden feature lineage, changed threshold, or unapproved model family.

## 11. P07 - Controls and frozen historical replay

### 11.1 Statistical engine calibration

Use 100 fixed replications of synthetic, stationary, zero-mean paired-loss-difference processes with serial correlation, including an AR(1) coefficient of 0.5 and an overlapping-20-innovation construction. Test the one-sided block-bootstrap/Holm implementation with the same sample lengths and planned block sizes. Report empirical rejection rates and Wilson binomial intervals. A 95% Wilson lower bound above the nominal familywise 5% rate triggers `INVALID_INFERENCE_CALIBRATION`; do not use that inference engine for a primary claim until repaired and versioned.

Finite simulation is an engineering calibration, not an exact guarantee of bootstrap validity under ASADO's structural changes.

### 11.2 Linear-world and positive-control studies

Use the first eight-year pre-outer development window only to estimate calibration scales and a fixed linear mean. Do not estimate these quantities from real outer returns. Freeze all generator parameters at P06. It is permissible to use the real feature/missingness calendar as a fixed covariate design while keeping genuine outer labels inaccessible.

Construct pseudo-labels with `mu = a + X beta`, where beta is a fixed development-only raw-ridge fit. Add independently simulated common and idiosyncratic shocks, each with variance share 0.5; use stationary AR coefficients 0.8 and 0.3 respectively, form overlapping 20-session sums, and scale to the development residual standard deviation. Generate enough latent shock dates beyond the last origin for every label. Keep the genuine clock/maturity metadata and ex-ante masks.

For positive controls, use `h = C04 * C06` and subtract its development-only linear projection on `[1, X]`. Freeze the projection. Add `gamma * h` at population-design incremental variance shares q in `{0.001, 0.005, 0.01}` relative to noise, setting `gamma = sqrt(q/(1-q)) * sigma_noise / sd_development(h)`. Add a strong q=0.10 engineering case if the minimum-effect cases have low power. A degenerate h is a reported unsupported control, not permission to choose a different lucrative interaction.

Run at least 100 fixed replications at q=0 and each specified q using the same full nested selection procedure. Report the distributions of MSE/IC gains, primary declarations, interaction declarations, fit-support failures, and binomial uncertainty. Q_S recovering a quadratic effect is a successful control even when the tree is weaker.

These pseudo-labels are a conditional forecasting simulation, not a coherent simulated equity-price path: real price-derived covariates remain fixed. Do not compute investable synthetic P&L or claim that these controls reproduce all endogenous market feedback. A linear-world win can reflect regularization rather than real-world interactions. Low detection power at q=0.001 weakens a broad null interpretation, but does not license changing the registered model after viewing real results.

The optional development-residual block-wild diagnostic from the prior design may be implemented as a labeled additional calibration, using development residuals only. It is not the decisive inference-size gate and does not replace the fully specified controls above.

### 11.3 Historical replay

For every scheduled annual/quarterly fit, load the correct immutable source snapshot and mature rows, rebuild fold-fitted transformations, select only at the annual dates, fit, audit, and issue the full next segment's forecasts. No future labels or retrospectively corrected feature vintages are available through the runner's as-of API.

Persist each forecast before evaluation. When later labels mature they may enter subsequent scheduled training, but the earlier forecast is immutable. Save unsuccessful candidate fits and their support failures, not just selected winners.

A restart resumes from hash-matched checkpoints. Transient I/O retries are capped at two per operation; scientific validation errors are not retried with changed settings. Real outer performance must not be printed in progress logs while the replay is incomplete.

### Deliverables and acceptance

Deliver every fitted transformer/model, selected hyperparameter, trial event, calibration result, support audit, and forecast record. Complete prediction hashes for all mandatory streams must match on row keys. If any mandatory stream cannot finish, record an incomplete study; never evaluate a model-specific intersection that hides its failed quarters.

## 12. P08 - Primary forecast comparison

### 12.1 Metrics

At each scored origin, compute the equally weighted cross-market MSE for each forecast stream. The aggregate loss is the mean of these origin losses. For benchmark B, define `d_B(t) = MSE_B(t) - MSE_N_S(t)` and `relative_gain_B = 1 - mean(MSE_N_S) / mean(MSE_B)`.

Compute one Spearman rank correlation across the same markets at each origin, using average ranks for ties. An exactly constant forecast or constant outcome has IC zero by this study's declared scoring convention, with a flag and count; do not drop those origins. Do not use country-row standard errors or flatten all markets into a single pooled correlation.

### 12.2 Registered primary gates

All of the following are required for `HISTORICAL_FORECAST_PASS`:

| Gate | Requirement |
|---|---|
| Validity | All data, timing, support, mask, and inference-integrity checks pass |
| MSE versus L_X | Relative gain at least 0.001 and positive paired improvement after correction |
| MSE versus L_S | Relative gain at least 0.001 and positive paired improvement after correction |
| IC versus L_star | Mean IC increment at least 0.01 and positive paired improvement after correction |
| Absolute usefulness | N_S aggregate MSE lower than B0 and L_star; N_S mean IC strictly positive |
| Temporal stability | Each of the three primary mean increments is positive in both fixed halves and after deleting its most favorable evaluation-year bucket |
| Coverage | Registered evidence floor met; no model-specific omitted rows or incomplete mandatory stream |

The 0.001 relative MSE threshold means **0.1% lower MSE**, not 0.1 percentage points of return, 10 basis points of alpha, or a 0.1 increase in R-squared. It is a point-estimate materiality rule. A confidence bound above zero does not prove that the whole confidence interval exceeds the 0.001 margin.

A failed gate yields `NO_ADVANTAGE_DEMONSTRATED` or `INSUFFICIENT_EVIDENCE`, depending on coverage and precision. It does not trigger a different horizon, sign flip, normalization, or model as the new primary.

### 12.3 Block inference

Use moving blocks of 63 consecutive base-calendar origin positions, preserving all markets, outcomes, and model forecasts together. Keep ineligible origin positions as empty positions rather than compressing a long outage into adjacent days. Sample blocks with replacement until the original calendar span is covered, truncate to that length, and aggregate retained valid-origin tuples. Require enough valid origins in each resample; record and bound deterministic redraw attempts.

For a one-sided mean-improvement test, center the origin differences under a zero-mean null, bootstrap their mean, and calculate `p = (1 + count(null_mean_star >= observed_mean)) / (B + 1)`. Use 5,000 replications, master seed 20260913, and a reproducible seed derivation per test family. Implement independently checked fixtures; do not use the fraction of uncentered bootstrap estimates below zero as the primary p-value.

Report 95% pointwise intervals for mean differences and relative loss ratios, with their construction explicitly labeled. Apply Holm correction at familywise alpha 0.05 across the three primary tests. The decisions use the corrected p-values plus effect thresholds. Pointwise intervals are not simultaneous familywise confidence intervals.

Repeat the fixed calculation with 126-origin blocks as a disclosed sensitivity; it does not replace a failed primary p-value. Report HAC estimates and globally non-overlapping label cohorts as diagnostics, without selecting the most favorable one.

### 12.4 Stability definitions

Freeze early and late halves using the calendar midpoint of the planned scored interval, before reading gains. Compute full calendar-year buckets, labeling partial endpoint years. For each primary difference, identify its most favorable bucket by total contribution and report the mean after omitting it; require that mean to remain positive. This is an explicitly outcome-based robustness diagnostic, not selection of a preferred sample or a new significance test.

Report the known 2024-26 interval separately, without treating it as pristine. Explain sensitivity to concentrated events, repeated currencies, and a small number of macro episodes. Bootstrap assumptions cannot establish universal future superiority.

### Deliverables and acceptance

`origin_metrics.parquet`, `primary_comparisons.json`, bootstrap seed/index manifests, confidence intervals, adjusted p-values, coverage/degeneracy counts, and `primary_verdict.json`. A hand-built fixture and a second implementation of aggregate loss/rank calculations must reproduce headline values. Plot data must be exported alongside report charts.

## 13. P09 - Mechanism, compression, and fragility

### 13.1 Conditional scientific claims

Keep N_S as the primary candidate regardless of which control looks best. After all primary tests pass, test three conditional MSE contrasts, each with positive mean IC increment as a directional guard:

| Contrast | Supported claim if it passes |
|---|---|
| N_S versus A_S | Interactions add beyond curved univariate effects |
| N_S versus Q_S | Adaptive threshold partitions add beyond explicit quadratic interactions |
| N_S versus N_X | This fixed economic compression helps this learner |

Apply Holm correction at 0.05 across the three conditional contrasts using the same paired block procedure. This is a serial gatekeeping family: no affirmative conditional claim is made unless all primary claims first pass. Report the contrasts even after primary failure, but label them descriptive and prohibit rescue promotion.

A tree win over ridge alone does not establish interaction value. A Q_S win does not establish that adaptive trees are needed. A raw-tree win does not establish that economic compression helps. A favorable feature-importance plot is not causal evidence.

### 13.2 Required descriptive diagnostics

Produce out-of-sample error/IC contributions by market, economic entity, currency group, year, global-volatility tercile, and feature-data-quality category. Determine volatility tercile boundaries using the preceding training history, never full-sample thresholds. The disaggregation is descriptive and must not become a rule for selecting countries or states.

Inspect three pre-specified conditional pairs: trade impulse/options stress `(C04,C06)`, banking impulse/options stress `(C05,C06)`, and own return/options stress `(C01,C06)`. The third is the reversal control. Use response summaries within actual joint covariate support. Cells with fewer than 126 training rows, 30 distinct origins, four markets, or two calendar years are marked unsupported rather than smoothed into a convincing surface.

Compare the learned conditional patterns before and during 2024-26 using the models actually trained at those dates. Do not add a post-2024 dummy. A sign-change narrative is permitted only as an interpretation of genuinely prior-trained predictions, with uncertainty and competing own-return explanations retained.

### 13.3 Frozen sensitivity set

Run the following diagnostics without changing primary specifications: the additional-one-source-session lag for conservatively timed feeds; 126-origin inference blocks; fixed 5/63-session outcome associations; omission of one whole training year at a time with no retuning; and six leave-region-out refits under a region map frozen in P01. For year/region omission, retain the selected configuration and unchanged eligible evaluation rows, then report support failures explicitly.

Implement a network placebo using 20 fixed seeds that reassign the full eligible neighbour-weight vectors among compatible endpoint entities within pre-specified region/time-zone strata, preserving each vector's mass and support where possible. Remove self-entity legs and record any infeasible stratum; do not claim this is an exact graph-topology null. Rebuild only the affected graph primitives and refit at the same scheduled dates with the already selected hyperparameters. Report distributions, not the best seed. This is a diagnostic of network specificity, not a substitute primary significance test.

Do not interpret a failed robustness refit as permission to remove that region/year from the primary model. Any extension involving country identity, alternative tenors, additional features, or a different nonlinear family requires a new ticket.

### Deliverables and acceptance

`mechanism_comparisons.json`, `fragility_report.md`, support counts, full placebo/sensitivity run manifests, and machine-readable chart data. Each paragraph in the conclusions must be traceable to a primary test, a gated conditional test, or a clearly labeled diagnostic. No attribution plot alone can earn a mechanism label.

## 14. P10 - Gross portfolio construction and native harness integration

### 14.1 Separate forecasting from portfolio expression

Evaluate gross economic relevance using frozen predictions only. Do not optimize portfolio weights, trade thresholds, leverage, signal direction, holding period, or turnover. Transaction costs and turnover may be measured descriptively when the verified harness already emits them, but cannot be promotion or kill gates. [R1]

The study's primary statistical comparison uses returns/ranks. Its gross ranking portfolio and ASADO's native harness may use different portfolio definitions. Record both precisely. A native top-N-versus-equal-weight test must not be relabeled as this study's long-short test, or vice versa.

### 14.2 Ranking and ties

At an eligible origin with n markets, set `k = max(1, floor(0.2*n))`. Allocate 50% of cohort gross capital to the k highest forecasts and 50% short to the k lowest. Equal-weight within each side. For forecast ties at a selection boundary, split that rank group's fractional membership equally among all tied markets so the effective selected count is k. If every score is identical, long and short exposures cancel and no active position is opened.

Hold each selected market from its recorded entry close through its 20-session exit close. Do not use future realized returns for membership, ex-post risk normalization, or ranking tie-breaks.

### 14.3 Cohort capital and daily marks

Implement a capital-consistent reference portfolio with 20 sleeves, each initialized with 1/20 of a unit of capital. At an origin, open one new cohort in the next available sleeve; all models use the same sleeve opportunity calendar determined by the planned maximum exit across **all eligible markets**, not only their selected names. If all sleeves are occupied, skip that origin for every model's portfolio and log the skip; still score every model's statistical forecast at that origin.

Each sleeve compounds its own capital. At a new cohort, deploy 50% long and 50% short of that sleeve's current capital; unentered positions and inactive sleeves remain in cash with zero cash return for this gross reference. Fix units at the entry mark and hold them, including the audited dividend/total-return convention. Do not rebalance within the holding period to control realized volatility. Gross exposure may drift and the ramp-up may be underinvested; report both.

Mark positions daily at the latest legitimately published total-return/FX marks at the UTC portfolio valuation cutoff. Scheduled holidays can use the last legitimate mark with a freshness flag. Unexplained missing marks and actual suspension events follow the pre-registered outcome-marking policy. A later correction appends a revised outcome record; it does not overwrite issued forecasts.

Aggregate sleeve NAVs to portfolio NAV. Daily strategy return is `NAV_d / NAV_(d-1) - 1`; calculate portfolio Sharpe from this marked daily return series, not from the overlapping 20-session labels. Record bankruptcy or nonpositive sleeve NAV explicitly; never drop those paths from results. An independent simple ledger on toy price paths must reproduce the P&L engine.

This reference capital convention is deliberately explicit. An audited existing harness portfolio implementation may be used instead only if its different rules are resolved and frozen before registration; do not choose the more attractive portfolio after results.

### 14.4 Gross evidence and expression venue

Report gross annualized return, volatility, Sharpe, maximum drawdown, long/short contributions, realized exposures, active sleeve count, market contribution, and capacity-independent turnover diagnostics. State annualization and cash assumptions. Reconcile to native gross WATCH gates using the exact verified implementation and family trial convention.

For an ETF expression check, audit the historical venue, listing/closure changes, total-return history, local-index mapping, and actual synchronized entry clock before comparison. Do not substitute the short ETF-price history for a longer total-return series without acknowledging coverage. A smaller ETF comparison is a separate diagnostic population and cannot replace a failed matched index test. [R3]

If historical index forecasts pass but ETF execution clocks cannot be verified, record a forecast pass and `EXPRESSION_UNVERIFIED`. No live sleeve is authorized. If a native harness would recompute labels under an incompatible clock, add a tested frozen-prediction adapter or report native qualification as unresolved; do not claim WATCH from an incompatible run.

### Deliverables and acceptance

Deliver memberships, orders for the paper simulator only, position/cash ledgers, daily NAV/returns, native harness inputs/outputs, adapter tests, and a contract-difference report. Forecast and portfolio conclusions are separate. Nothing submits an order to a broker.

## 15. P11 - Final verdict, documentation, and independent reproduction

### 15.1 Required final report

`RESULTS.md` and its readable HTML rendering must answer, in order: was the experiment valid; what was the actual sample; did N_S beat the two ridge models and the selected linear procedure; did ranking improve; did interactions add beyond additive effects; did adaptive partitions beat quadratic ridge; did the state representation help; did gross portfolio gates pass; and what remains uncertain?

Include exact source/registration/data hashes, all selected configurations by fit date, all six learner grids, missing/failed fits, sample losses, null/power calibration, uncertainty assumptions, primary and secondary comparisons, every planned sensitivity, and the native ledger mapping. Report negative findings with the same prominence as positive ones.

Provide `model_card.md` covering target, universe, horizon, source vintage quality, likely failure modes, unsupported regions/states, known historical exposure, and prohibited production uses. Provide `REPRODUCE.md` with complete commands, artifact hashes, environment setup, and expected assertion outputs. Sanitized public reports must not expose licensed observations.

### 15.2 Decision table

| Result | Required conclusion | Next action |
|---|---|---|
| Timing, source, label, or sample invariant fails | Invalid or blocked experiment | Repair under a new recorded version; no alpha verdict |
| Mandatory model cannot fit under support rules | Incomplete registered procedure | Preserve failures; no quarter deletion or replacement winner |
| Primary comparison fails with adequate data | No nonlinear advantage demonstrated | Archive; do not expand search inside this ticket |
| Intervals are too wide or coverage floor fails | Insufficient evidence | Quantify uncertainty and power; no promotion |
| N_S beats ridge but not A_S | Nonlinear main effects may suffice | Do not claim interactions |
| N_S beats A_S but not Q_S | Explicit interactions may suffice | Adaptive tree complexity unearned |
| N_S loses to N_X | State compression not supported | Do not market the state layer as the source of value |
| Forecast pass, gross gates fail | Forecast evidence without gross qualification | No production allocation |
| Historical forecast and gross gates pass | Historical evidence for a frozen procedure | Optional prospective shadow operation |

A simpler control appearing best is useful scientific evidence, but promoting it requires its own properly registered claim; it does not retroactively become the original primary candidate. Historical success is not proof of permanent future superiority.

### 15.3 Independent reproduction acceptance

A fresh process on the frozen snapshot must regenerate all headline metrics from stored forecasts without training. A second run on at least two full fit segments must reproduce preprocessing, selected configurations, and forecasts within the specified tolerance. Run the complete test suite and compare source-database hashes before and after study execution.

Append the final study result through the verified native ledger route. Do not rewrite historical records, reset family trial counts, or mark a methodology WATCH without its required evidence. Archive every complete or failed run; remove only transient cache files that can be reconstructed.

## 16. P12 - Prospective shadow operation

### 16.1 Scope

Implement a disabled-by-default command that uses the frozen feature builders, eligibility rules, selected procedure, scheduled refits, and model artifacts to produce daily paper forecasts. Enabling any launchd/cron/nightly integration requires a separate explicit owner approval. The PRD does not authorize the assistant or coding agent to trade, alter portfolio allocations, or silently create a recurring external action.

The first genuine prospective origin is the first eligible origin after the registered pipeline is actually operational and its forecast is durably recorded before entry. Do not backdate forecasts from registration day if the model had not yet issued them. Real-time collection times now matter in addition to source historical-availability assumptions.

### 16.2 Immutable issuance

For each origin, freeze feature values, source watermarks, forecast values, model version, fit timestamp, eligibility decisions, and planned entry/exit. Write forecasts before outcome access. Maturing outcomes go to a separate append-only table; later revisions receive new versions. A missing feed suppresses only rows permitted by the pre-specified eligibility policy. If fewer than 20 markets remain, issue `NO_FORECAST_DATA_QUALITY` for the origin.

Distinguish a forecast produced on time from one reconstructed after entry. Late forecasts are operational failures and cannot be presented as prospective tradable predictions. Show forecast coverage and failures, not just successful days.

### 16.3 Prospective endpoint and monitoring

Before viewing prospective outcome comparisons, freeze one analysis endpoint. Estimate variance of paired historical loss differences, then use a dependence-aware block simulation to report power at the registered MSE and IC margins for candidate endpoint lengths. Choose the shortest whole-year endpoint attaining the pre-declared 80% power target within the owner's approved operating budget; otherwise freeze an owner-approved endpoint and label it underpowered. Record the decision before prospective inference begins.

This binding cannot be assigned an honest numerical date in this PRD without measured loss variance. It blocks a confirmatory prospective claim, not development of the shadow logger. Do not repeatedly stop at the first significant p-value. Operational monitoring may report data gaps, drift, and model failures; comparative performance inference waits for the fixed endpoint unless a separately specified valid sequential design is approved.

At each scheduled refit, reproduce the registered rolling/tuning process with newly matured outcomes. No new predictors or architecture are introduced into the same prospective ticket. Data distribution drift is a diagnostic and possible operational pause, not permission to silently alter the scientific specification.

### Deliverables and acceptance

`shadow.py`, a dry-run scheduler integration plan, on-time issuance tests, delayed-feed tests, model roll-forward tests, outcome append tests, a monitoring report, and a separately approved prospective protocol. All scheduler and trading integrations remain off by default.

## 17. P13 - Optional neural extension

This phase is disabled in the core study. It requires a separate registration before examining its own outer results and cannot be launched as an unrecorded rescue after N_S fails.

Use `f(S) = a + beta' S + v' tanh(W S + b)` with 16 inputs and eight hidden units: 161 scalar parameters. Initialize the skip branch from the corresponding matured-training state ridge and the nonlinear output weights at zero, with seeded nonzero hidden weights. Train every parameter jointly against the original date-weighted return target; the zero nonlinear output initialization does not justify training on incumbent residuals.

Use AdamW with learning rates `{0.001, 0.003}`, weight decays `{0.01, 0.1, 1.0}`, maximum 200 epochs, chronological validation patience 10, and batches of 16 entire origins. Preserve equal-origin loss weights in partial batches. Exclude intercepts/biases from decay and specify that choice in the extension protocol. Select epoch count in inner validation only; refit the outer training window for the selected count without looking at outer labels.

Average forecasts from seeds `{11, 29, 47, 71, 101}`; never select the best seed. No batch normalization, country embeddings, sequence windows, extra hidden layers, or auxiliary tasks. Use the same X/S construction, sample, target, maturity rules, baselines, and full trial accounting.

If considered after the tree's historical results are known, disclose that historical exposure and treat the additional test as a new searched-family member. Prefer a new prospective endpoint for confirmation. This phase's completion criterion is a separately valid comparison, not a requirement that the neural network outperform the trees.

## 18. Data contracts and module APIs

### 18.1 Core records

| Record | Required fields beyond primary ID |
|---|---|
| Source snapshot | Database/source batch IDs, source cutoff, export time, commit, content hashes, row counts, quality flags |
| Feature cell | Origin, market/entity, primitive ID, value, units, observation/reference times, historical availability, capture time, vintage ID, lineage ID, status |
| Ex-ante row | Origin, market, calendar version, feature-ready flag, exclusion reason, feature hash, planned entry/exit |
| Label | Origin, market, horizon, value/status, actual marks/timestamps, label availability, label version, source hash |
| Fold | Fit cutoff, role, ordered row IDs, maturity limit, window boundaries, preprocessing fit hash |
| Fit | Model/config IDs, data/fold/feature hashes, train origins, max label availability, seed, preprocessing/model path, leaf audit, status |
| Forecast | Origin, market, model ID, prediction, target/horizon, issued/model-fit times, feature hash, registration/fit IDs, forecast status; no actual outcome |
| Metric | Run/model/benchmark IDs, population hash, metric, estimate, interval, raw/adjusted p, method, validity flags |
| Study event | Event timestamp, actor, type, prior hash, payload hash, affected artifacts, reason |

All timestamps are timezone-aware UTC in persistent interchange formats. Preserve local session IDs and source time zones as metadata. Canonical float64 handling, explicit nulls, stable column ordering, and documented sort keys are required for hashes. Never use filesystem modification time as source publication time.

### 18.2 Proposed typed interfaces

These are implementation contracts, not existing repository APIs:

```python
snapshot_sources(spec: SourceSpec, cutoff: datetime) -> SnapshotManifest
bind_feature_sources(snapshot: SnapshotManifest) -> BoundFeatureManifest
build_calendars(market_map: MarketMap, interval: Interval) -> CalendarStore
build_features(snapshot: SnapshotManifest, origins: OriginSet,
               manifest: BoundFeatureManifest) -> FeatureStore
build_labels(snapshot: SnapshotManifest, rows: ExAnteRows,
             horizons: tuple[int, ...]) -> LabelStore
make_panel(features: FeatureStore, rows: ExAnteRows) -> PanelManifest
make_folds(panel: PanelManifest, labels: LabelStore,
           protocol: LockedProtocol) -> FoldManifest
select_config(model_id: str, folds: FoldManifest,
              protocol: LockedProtocol) -> SelectionResult
fit_model(model_id: str, train: MaturedTrainingSlice,
          selected: SelectedConfig) -> AuditedModelArtifact
issue_predictions(model: AuditedModelArtifact,
                  features: FeatureOnlySlice) -> ForecastBatch
evaluate_primary(forecasts: FrozenForecasts, outcomes: MaturedOutcomes,
                 protocol: LockedProtocol) -> PrimaryVerdict
simulate_gross_portfolio(forecasts: FrozenForecasts,
                         marks: PublishedMarkStore,
                         protocol: LockedProtocol) -> PortfolioEvidence
```

`MaturedTrainingSlice` construction validates its label-time invariant. `FeatureOnlySlice` cannot contain outcome columns. `FrozenForecasts` requires an issuance manifest and matching population hashes. Each returned artifact includes status and provenance; exceptions must identify the source/row/contract violated.

## 19. Acceptance-test catalogue

The coding agent must implement these tests or an explicitly equivalent test with a mapped ID. They are executable acceptance requirements, not merely checklist prose.

| ID | Test | Expected result |
|---|---|---|
| T01 | Read-only source run | Source tables/files unchanged |
| T02 | Mid-collection snapshot | Snapshot rejected or coordinated to one completed watermark |
| T03 | Unknown source selector | Registration/build blocked; no guessed substitute |
| T04 | Historical truncation | Features at t equal build using only available-at-t data |
| T05 | Future append | Earlier features and issued predictions unchanged |
| T06 | Mutated future target | Earlier features/masks/fits unaffected until that label can legitimately mature |
| T07 | Forward-target alias and renamed descendant | Both rejected by lineage allowlist/denylist |
| T08 | Weekend padded T2 data | No invented trading-session return observations |
| T09 | Newest independent calendar date | Latest valid session is retained without forward returns |
| T10 | Cross-market holiday | Entry and H-session exit move correctly |
| T11 | Daylight-saving/close mapping | UTC close changes correctly; entry strictly follows origin |
| T12 | USD index versus local index | Correct conversion once, never twice |
| T13 | Future/unknown terminal mark | No retroactive row deletion or zero-return fill |
| T14 | Delayed release | First eligible feature moves with release delay |
| T15 | Revised macro/edge without vintage | Primary feature blocked despite arbitrary lag |
| T16 | Next-calendar-year consensus rollover | No spurious revision from a different forecast year |
| T17 | Missing consensus feed | Missing is not zero revision or no-event evidence |
| T18 | Genuine unchanged consensus | Valid carried state; arrival count stays zero |
| T19 | Reversed FX quotation | Depreciation-premium and carry signs follow manifest |
| T20 | Graph self/duplicate entity | Excluded once; no double weighting |
| T21 | Missing graph mass | Fixed 80%/three-entity support rule enforced |
| T22 | Wrong graph direction | Contract mismatch detected before modelling |
| T23 | Future futures back-adjustment | Historical-return invariance failure blocks input |
| T24 | Global normalization | Global series normalized once and not demeaned to zero |
| T25 | Rolling zero scale | Common unavailable status, no infinity or model-specific fix |
| T26 | Fold preprocessing | Future validation/test values do not change fitted scaler |
| T27 | Target maturity across markets | Whole origin purged until its latest included label is available |
| T28 | Fold assignment | No market at one origin appears in multiple fold roles |
| T29 | Eight-year/quarterly boundary fixtures | Correct rolling dates, quarterly fits, annual selection |
| T30 | Row duplication with split weights | Ridge solution and weighted loss unchanged |
| T31 | Hand-derived ridge | Estimator matches weighted closed form |
| T32 | Quadratic expansion | Exactly 152 ordered predictors, no duplicate intercept |
| T33 | Automatic estimator early stopping | Disabled; actual n_iter matches selected count |
| T34 | Accidental country categorical column | Rejected by schema before fit |
| T35 | Exported tree prediction parity | Traversal reproduces estimator predictions to tolerance |
| T36 | Large row-count, short-episode leaf | Rejected despite satisfying min_samples_leaf |
| T37 | Unsupported outer refit | Study blocked; quarter not silently dropped |
| T38 | Parsimony rule tie | Deterministic pre-specified configuration wins |
| T39 | B0 and date weighting | Equal-origin mean reproduced on ragged panel |
| T40 | Constant forecasts/outcomes | IC=0 with flag, not omitted origin |
| T41 | Paired comparison sample | Row, label, and split hashes identical |
| T42 | Bootstrap null centering | Matches independently computed one-sided test fixture |
| T43 | Missing-origin bootstrap blocks | Time gaps preserved; no compressed outage |
| T44 | Holm correction | Known p-value fixture reproduced |
| T45 | Real outer visibility during replay | No performance summaries printed or consumed |
| T46 | Calibration labels | Genuine outer outcomes never read by pseudo-label generator |
| T47 | Known interaction injection | Signal scale and nonlinearity match frozen generator |
| T48 | Interrupted run and resume | Identical complete artifacts, no duplicated forecasts |
| T49 | Changed config on resume | Cached artifacts rejected by hash mismatch |
| T50 | Portfolio ties | Fractional tied membership; all-constant score has no active exposure |
| T51 | Overlapping cohorts | Capital, cash, entries/exits, and daily marks reconcile |
| T52 | Portfolio uses future labels as daily returns | Explicit failure; daily P&L must come from marked holdings |
| T53 | Native harness clock mismatch | Native qualification blocked, not relabeled |
| T54 | Live late forecast | Flagged late; never counted as on-time issuance |
| T55 | Forecast/outcome immutability | Outcomes appended separately; original forecasts unchanged |
| T56 | Default automation permissions | No scheduler activation, broker orders, or source refresh |
| T57 | Independent metrics reproduction | Stored predictions regenerate all headline statistics |
| T58 | Protocol amendment after exposure | New version/event required; old results preserved |
| T59 | Unknown installed tree internals | Adapter fails closed rather than inventing leaf assignments |
| T60 | Registration with unresolved values | Freeze command returns blocking errors |

## 20. Command-line workflow and exit behavior

The following names are proposed entry-point commands to implement, not commands already available in ASADO. Resolve package invocation in P00 and keep the final command surface consistent.

```bash
python -m research.nonlinear_country_returns.cli audit --config study.json
python -m research.nonlinear_country_returns.cli snapshot --config study.json
python -m research.nonlinear_country_returns.cli build --config study.json
python -m research.nonlinear_country_returns.cli test-contracts --config study.json
python -m research.nonlinear_country_returns.cli validate-registration --config study.json
python -m research.nonlinear_country_returns.cli register --config study.json --approval approval.json
python -m research.nonlinear_country_returns.cli controls --protocol protocol.lock.json
python -m research.nonlinear_country_returns.cli replay --protocol protocol.lock.json --resume
python -m research.nonlinear_country_returns.cli evaluate --protocol protocol.lock.json
python -m research.nonlinear_country_returns.cli mechanisms --protocol protocol.lock.json
python -m research.nonlinear_country_returns.cli portfolio --protocol protocol.lock.json
python -m research.nonlinear_country_returns.cli report --protocol protocol.lock.json
python -m research.nonlinear_country_returns.cli verify --run-id RUN_ID
python -m research.nonlinear_country_returns.cli shadow --protocol protocol.lock.json --dry-run
```

Every command accepts an output directory and emits a machine-readable status event. Dry-run commands must describe writes before performing them. Registration, source snapshot, and final report operations are idempotent by content hash; repeated invocation must not create duplicate trials or ledger entries.

Use exit codes: 0 completed; 10 governance/data binding blocked; 11 insufficient coverage; 12 PIT/data integrity invalid; 13 fit support blocked; 14 inference calibration invalid; 15 hash/reproducibility mismatch; 20 unexpected implementation failure. A valid scientific failure to beat ridge is a successfully executed evaluation with exit 0 and a negative verdict in the result JSON. Do not treat a negative result as a crash needing automatic retries.

## 21. Implementation milestones and definition of done

### Milestone M1 - Data-ready evidence, no real model result

Complete P00-P04. The owner receives measured coverage, source/vintage evidence, a concrete eligible universe/history, panel/fold hashes, leakage-test outcomes, and any blockers. No out-of-sample IC or portfolio chart is presented. Synthetic estimator/inference implementation may proceed independently.

### Milestone M2 - Locked research engine

Complete P05-P06. All model adapters, inference, portfolio fixtures, support audits, deterministic selection rules, and event records are tested. The protocol is registered with no unresolved source or harness requirements. This is the authorization boundary for real historical evaluation.

### Milestone M3 - Complete historical experiment

Complete P07-P10. All mandatory forecast streams, controls, comparisons, sensitivities, and gross evidence are computed. No winning alternate model, period, horizon, or normalization is substituted. Failures are first-class outputs.

### Milestone M4 - Reproduced verdict

Complete P11. A skeptical reader can independently calculate the claims from immutable forecasts and a clean process reproduces selected fits. The implementation remains compatible with existing repository tests and leaves source databases unchanged.

### Milestone M5 - Optional prospective operation

Complete P12 only after separate approval. On-time forecasts and later outcomes are appended under a frozen endpoint protocol. P13 remains an optional separate study.

**Definition of done:** the coding agent delivers a reproducible scientific decision under the registered contract, including an honest negative, blocked, or inconclusive decision. It does not merely deliver code that runs or a chart showing a profitable strategy.

## 22. Handoff instruction for the coding agent

Implement this PRD phase by phase in the existing ASADO repository. Begin with local instruction/protocol reconciliation and a read-only audit of the two databases. Reuse verified utilities, preserve the existing nightly system, and keep licensed data outside Git. Treat every source selector in the companion template as unbound until inspected.

Implement every phase's software, tests, manifests, and reporting requirements. Do not stop after a high-level architecture proposal. Execute real research phases only after their prerequisites and registration are satisfied. When blocked, finish independent synthetic/code work, return a concrete blocker report with evidence and a proposed versioned resolution, and do not fabricate data or a result.

N_S at 20 sessions remains the sole primary candidate. All compared models use the same PIT sample. No cost/turnover gates, searched rescue model, or automatic production deployment is authorized. A valid failure to beat ridge is an acceptable final outcome.

## 23. Source and decision register

These sources support repository facts and implementation API checks. The feature formulas, numerical thresholds, phase gates, and proposed new paths are design decisions in this PRD unless explicitly identified otherwise. Source references are not assertions that an unavailable local implementation was audited.

- **R1.** ASADO original research brief, September 13, 2026. [Repository brief](https://github.com/ArjunDivecha/ASADO/blob/main/docs/ASTRA_BRIEF_regime_model_2026_09_13.md). Basis for scope, exclusions, outcome-first evaluation, known calendar/vintage issues, and gross-only policy.
- **R2.** ASADO README, inspected September 13, 2026. [README](https://raw.githubusercontent.com/ArjunDivecha/ASADO/main/README.md). Basis for repository lifecycle, source databases, startup checks, and documented research infrastructure. Main was not pinned to a retrievable remote commit for this PRD.
- **R3.** ASADO database inventory, September 13, 2026. [Inventory](https://raw.githubusercontent.com/ArjunDivecha/ASADO/main/docs/DB_INVENTORY_2026_09_13.md). Basis for discovery table names and distinctions among source/derived/return surfaces; not field-level readiness certification.
- **R4.** ASADO graveyard skill. [Research record](https://raw.githubusercontent.com/ArjunDivecha/ASADO/main/.claude/skills/asado-graveyard/SKILL.md). Basis for prior-failure exclusions, searched-pass skepticism, and limitations of single-variable ledger coverage. Historical verification dates in that document remain relevant.
- **R5.** ASADO factor reference. [Factor reference](https://raw.githubusercontent.com/ArjunDivecha/ASADO/main/docs/factor_reference.md). Warehouse variable-discovery reference; loop coverage must be checked separately.
- **R6.** Scikit-learn, HistGradientBoostingRegressor official documentation, inspected September 13, 2026. [Estimator documentation](https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingRegressor.html). Basis for explicit early-stopping, missing-value, categorical, depth, leaf, and bin controls. Implement against a tested pinned local version.
- **R7.** Scikit-learn, Ridge official documentation, inspected September 13, 2026. [Estimator documentation](https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.Ridge.html). Basis for the weighted ridge API/objective audit; numerical choices are this study's specification.
- **A1.** `ASADO_Nonlinear_Training_Design.md`, supplied in the conversation, September 13, 2026. Prior design and companion `ASADO_Nonlinear_Preregistration_Draft.json`; read in full. This PRD resolves implementation details but does not claim those drafts were registered or run.

### 23.1 Clarifications relative to the prior draft

This PRD makes explicit the eight forecast streams versus six tuned learners; source timing and forecast-year blockers; label/outcome separation; exact origin and entry clocks; complete-case mask requirements; inner-block refit phase; the no-fallback policy for unsupported outer fits; a separately checked inference-size calibration; fixed positive-control strengths; diagnostic rather than separately optimized 5/63-session uses; capital-consistent marked portfolio cohorts; and a disabled-by-default shadow logger.

It adds a positive aggregate MSE check against the inner-selected linear procedure, without changing the three registered primary significance tests. It preserves the proposed 0.1% MSE and 0.01 IC point margins and labels them accurately. A prospective endpoint remains a required later binding because the needed empirical variance has not been measured.

### 23.2 Remaining local bindings

The implementation must resolve actual source selectors and units; historical publication/quote conventions; index currencies; calendar provider and exceptional closures; graph direction and market/entity maps; continuous-futures construction; event-feed completeness; exact eligible dates/universe; installed estimator versions and traversal semantics; native registration/harness/family accounting; and registration approval. These are concrete P00-P06 work items, not permission to improvise using out-of-sample performance.
