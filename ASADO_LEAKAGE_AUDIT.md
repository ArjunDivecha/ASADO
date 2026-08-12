# ASADO Deep Learning Research Platform — Leakage Audit

**Milestone:** 0
**Audit date:** 2026-08-11
**Status:** No-go for headline model training until the critical gates below pass
**Scope:** Forward 12-month country-equity prediction from the live ASADO warehouse, loop database, graph stores, and existing preprocessing code.

## Executive verdict

The requested research is viable, but the current `feature_panel_t2` view is a discovery surface, **not a point-in-time training set**. Training directly from it would permit several independent leakage paths.

The two most serious are already present in the live system:

1. Forward-return labels (`1MRet` through `12MRet`) are physically co-located with candidate features.
2. The monthly T2 builder cleans source histories using whole-history statistics and a window that includes future observations.

In addition, most macro rows lack a first-knowable date or vintage identifier, projections extend past the present, current graph weights coexist with PIT edges, and the registry currently mislabels `12MRet` as a trailing price return.

These findings do not invalidate the target or the ASADO database. They mean Milestone 1 must create a deliberately narrower legal dataset with mechanical allowlists, explicit availability timestamps, separate labels, and automated red-team tests.

## 1. Threat model

A historical prediction made at decision date `t` may use only:

- data observed or released no later than `t`;
- transformations computed only from values legally available by `t`;
- country and graph membership knowable by `t`;
- model, feature-selection, normalization, and hyperparameter state fitted without the forecast period or its labels;
- labels whose complete forward holding window ended before the applicable training cutoff.

The platform must defend against four forms of leakage:

1. **Direct label leakage:** future returns or functions of them enter the inputs.
2. **Temporal preprocessing leakage:** later observations affect earlier cleaning, scaling, imputation, feature selection, or graph construction.
3. **Vintage/revision leakage:** a value is dated by the period it describes rather than when it was first known.
4. **Research-process leakage:** final-test results influence architecture, universe, objective, or hyperparameters.

## 2. Findings and required controls

### L-01 — Forward returns are present in the feature view

**Severity:** Critical
**Evidence:** `feature_panel_t2` contains T2 `1MRet`, `3MRet`, `6MRet`, `9MRet`, and `12MRet`, plus a GDELT `1MRet` alias. `t2_master.12MRet` is the exact requested label.

**Risk:** A broad feature query, automatic feature discovery, correlation filter, or model matrix pivot can ingest the target or a shorter-horizon proxy directly.

**Control:** Build targets in a physically separate artifact. Use a deny-by-default feature manifest and reject any name, alias, lineage, or source role identified as a return label. The existing harness blacklist should be reused and expanded to lineage checks.

**Acceptance test:** Inject `12MRet`, a renamed copy, and a one-month-shifted copy into the candidate store. Dataset construction must fail before training.

### L-02 — Monthly T2 source cleaning uses future observations

**Severity:** Critical
**Evidence:** `scripts/build_t2_master.py::_clean_sheet` computes median/MAD using the complete series and evaluates local outliers using a window containing subsequent rows. The cleaned source sheets feed monthly T2 factors and their transformations.

**Risk:** An early historical feature can change when later history is appended. That makes the apparent historical information set dependent on the future.

**Scope nuance:** The forward-return sheets are derived directly from total-return indices before this cleaning pass, so the target reconciliation remains valid. The contamination affects monthly T2 input candidates.

**Control:** Quarantine the existing monthly T2 factor inputs for headline ML. Rebuild required market histories with expanding or trailing-only cleaning, version the causal rule, and prove prefix invariance. The daily T2 builder already provides a backward-looking rolling-cleaning pattern, but its current partial-build failure must first be repaired and revalidated.

**Acceptance test:** Rebuild the first `N` dates both alone and with later dates appended. All first-`N` cleaned values must be identical bit-for-bit or within a documented numerical tolerance.

### L-03 — Publication and revision metadata are absent

**Severity:** Critical
**Evidence:** All 1,440 rows in `variable_registry` have blank publication-lag, revision, and vintage fields. Most main-warehouse economic tables carry a reference date but no universal `available_at` or release timestamp.

**Risk:** Revised GDP, CPI, fiscal, trade, or annual World Bank values can appear at the period they describe, months before a researcher could have known them.

**Control:** Every feature requires a source-specific PIT contract: observation period, release calendar or conservative lag, vintage policy, allowable carry, staleness threshold, and revision treatment. Latest-vintage histories without reconstructable vintages are excluded from headline experiments.

**Acceptance test:** For each allowed source, sample historical rows and prove `available_at <= decision_date`; revision-prone sources must also prove that the selected vintage was the latest vintage available then.

### L-04 — Future forecasts and projections share the feature namespace

**Severity:** Critical
**Evidence:** `imf_factors` extends to 2031, demographics data to 2100, `extended_factors` to 2026-12, and `gdelt_panel` to 2026-09. A naïve “latest value” query can therefore return a future reference period.

**Risk:** A forecast or projection may be treated as a realized historical observation, or a future row may be forward-filled backward/selected as latest.

**Control:** Store `reference_date`, `available_at`, `vintage_date`, and `is_forecast` separately. A forecast may be used only as a forecast published by the decision date, never as subsequently realized history. Demographic projections are excluded from the first headline feature set.

**Acceptance test:** Inject rows with `reference_date > decision_date` under both forecast and non-forecast flags. Non-forecast rows must fail; forecast rows must pass only with a qualifying vintage and explicit allowlist rule.

### L-05 — Current and point-in-time graph features coexist

**Severity:** High
**Evidence:** `graph_edge_vintages` and `graph_features_pit_daily` encode historical vintages and `applies_from`. `graph_edge_snapshots` and `graph_features_daily` use current/snapshot relationships projected over historical returns.

**Risk:** Modern trade, bank, holder, correlation, similarity, or lead-lag relationships can leak into earlier dates.

**Control:** Only `graph_edge_vintages` may construct headline adjacency matrices. For each decision date select the most recent vintage with `applies_from <= decision_date`. Current graph features are sensitivity/placebo inputs only and must carry a quarantine status.

**Acceptance test:** Add an edge whose `applies_from` is one day after the decision date. It must not appear. Permuted-real-edge and no-edge graph placebos are mandatory in the graph milestone.

### L-06 — Overlapping 12-month labels can cross fold boundaries

**Severity:** High
**Evidence:** Adjacent monthly targets share 11 of 12 return months. A row dated near a validation/test boundary can have a target end after the forecast date even if its feature date is earlier.

**Risk:** Training labels can contain market returns from the validation or test period, and conventional significance statistics will overstate independence.

**Control:** A training example is eligible only when `target_end_date <= training_information_cutoff`. Apply a 12-month purge/embargo around validation and test boundaries. Report 12 non-overlapping annual-offset cohorts and autocorrelation-aware inference.

**Acceptance test:** Every fold must assert `max(train.target_end_date) <= train_information_cutoff < min(test.decision_date)` and zero target-window overlap across purged boundaries.

### L-07 — The configured universe is retrospectively fixed

**Severity:** High
**Evidence:** The canonical list contains 34 current equity markets/sleeves, while label eligibility evolves from 32 to 33 to 34. No stored historical selection-membership archive proves that this exact modern list would have been selected in 2000.

**Risk:** Results can contain survivorship or selection bias even when each return series is historically correct.

**Control:** Version an eligibility table by decision date and distinguish data eligibility from historically investable/selected membership. Headline reports must carry the “fixed current-universe” limitation until a PIT universe is reconstructed. Report stable-coverage, DM/EM, and leave-one-country-out sensitivity.

**Acceptance test:** Models must receive an eligibility mask, never silently impute a pre-inception country, and produce identical predictions for eligible countries when an ineligible padded country is added.

### L-08 — Full-history scaling, imputation, and selection remain easy to perform

**Severity:** High
**Evidence:** The repository has precomputed normalized panels, but no generic nested ML engine that binds all preprocessing to a training fold. Non-T2 cross-sectional normalization also uses up to 43 countries before the T2 view filters to 34.

**Risk:** Full-sample medians, z-scores, winsorization thresholds, feature selection, or category encodings can leak test-distribution information. Cross-sectional transforms can use an undisclosed universe.

**Control:** Persist raw legal values in the canonical store. Fit imputation, clipping, time-series scaling, dimensionality reduction, and feature selection inside each training fold. Same-date cross-sectional ranks must use the declared eligible universe for that date.

**Acceptance test:** Mutating test-period feature values must not change any training-period tensor or fitted preprocessing parameter.

### L-09 — Trained outputs can create circular predictors

**Severity:** High
**Evidence:** The loop DB contains combiner scores, family ranks, lead-lag/similarity discoveries, optimizer membership, harness results, dislocations, and other research outputs derived from historical outcomes or selected mechanisms.

**Risk:** A downstream model may ingest an output whose weights, family selection, or construction used its own evaluation period.

**Control:** Default-deny all trained/research output tables. Admit one only through a lineage manifest proving the producing model's training cutoff predates the consuming decision date. Existing production methodology should be a separately reconstructed benchmark, not a generic feature family.

**Acceptance test:** Dependency traversal must reject a feature whose upstream artifact has `fit_end_date >= decision_date` or whose lineage is missing.

### L-10 — Date semantics can be misinterpreted

**Severity:** High
**Evidence:** T2 moves Bloomberg month-end dates to the first day of the next month. `12MRet` dated June 2015 begins its holding window in June 2015; it is not a return already known on June 1. The registry incorrectly describes it as trailing.

**Risk:** An off-by-one month can move either features or labels across the decision boundary.

**Control:** Canonical records must carry `observation_date`, `available_at`, `decision_date`, `target_start_date`, and `target_end_date`. The month-start convention must be covered by a fixture with hand-calculated total-return-index values.

**Acceptance test:** A synthetic 14-month TRI path must produce exactly one expected 12M label at the documented decision/holding dates.

### L-11 — Missingness can silently become information from the future

**Severity:** High
**Evidence:** Long source tables often omit null rows; raw-grid coverage is highly unequal by source, country, and period. No canonical masks distinguish not-yet-released, structurally unavailable, stale, and forecast values.

**Risk:** Backfill uses a future first observation; unlimited forward-fill carries stale values; global imputation uses future distributions; zero conflates missing with an economic value.

**Control:** Never backward-fill. Use source-specific legal carry limits, train-fold-only imputation, observation/carried/missing/forecast masks, and age since observation. Preserve structural absence separately from temporary missingness.

**Acceptance test:** A value first released after `t` must remain missing at `t`; extending the dataset with later observations must not change earlier masks or imputations.

### L-12 — Semantic metadata gives a wrong target definition

**Severity:** High
**Evidence:** `variable_registry_full` says `12MRet` is a trailing 12-month price return. Code and exact reconciliation show it is a forward 12-month total return.

**Risk:** Automated role assignment could admit the target as momentum or misalign the training label.

**Control:** Correct and test the registry before it acts as an authoritative model contract. Until then, target roles derive from verified lineage and are hard-blocked as features.

**Acceptance test:** Registry validation must compare role/formula fixtures for all `NMRet` and `NDRet` variables and reject trailing/forward or price/total-return mismatches.

### L-13 — The live daily database is in a partial-build state

**Severity:** High data-quality blocker; not itself leakage
**Evidence:** The 2026-08-11 build recreated `factor_returns_daily` and then failed on `KeyError: 'Date'`, leaving zero rows while other daily tables had already been replaced.

**Risk:** A snapshot can combine different build vintages or treat a missing daily benchmark as a valid empty table.

**Control:** Snapshot only after a successful atomic build and health manifest. Require common run identifiers/as-of timestamps and nonzero expected tables. Do not use the current daily state for Milestone 1.

**Acceptance test:** Snapshot creation must abort when a required table is empty, row counts regress unexpectedly, or component run IDs differ.

## 3. Source admission matrix

| Status | Permitted in headline research? | Examples | Required action |
|---|---|---|---|
| A — proven/derivable PIT | Yes, after automated verification | Target/returns from TRI; causally rebuilt daily market history; GDELT dated observations; WEO vintages; `graph_edge_vintages` | Encode and test exact availability/lineage contract |
| B — contract required | Not yet | FRED/OECD/BIS economic series; Bloomberg consensus/releases; ratings, flows, sovereign and market-implied loop families | Establish conservative release/vintage/carry rules, then promote variable by variable |
| C — latest-vintage or projection | No headline use | Non-vintage World Bank/IMF histories, current WEO view, demographics projections | Descriptive or explicitly labeled sensitivity only |
| Q — quarantine | Never as ordinary inputs | Forward returns; monthly future-aware-cleaned T2 factors; current graph; optimizer/combiner/harness outputs without PIT lineage | Mechanical block |

Admission is by **variable × source × transformation version**, not by table name alone.

## 4. Required leakage red-team suite

Milestone 1 is not accepted until these tests fail safely:

1. direct `12MRet` feature injection;
2. renamed and source-aliased target injection;
3. future-shifted proxy injection;
4. append-future-data prefix-invariance test for cleaning;
5. full-history scaler/imputer contamination test;
6. revised-macro-vintage test;
7. future projection/reference-date test;
8. graph `applies_from` boundary test;
9. fold target-window/purge test;
10. trained-output lineage-cycle test;
11. first-observation/backfill test;
12. date-shift and target-formula fixture;
13. time-varying universe-mask test;
14. stale/partial snapshot rejection test.

The tests should operate on small synthetic fixtures as well as sampled real rows. A test that merely scans feature names is insufficient; lineage and date rules must also be exercised.

## 5. Research-process controls

- Freeze the final test interval before architecture work and do not inspect it for selection decisions.
- Use nested walk-forward validation; random splits are prohibited for headline results.
- Record every attempted experiment, including negative results, in an append-only registry.
- Predeclare the incumbent scorecard and promotion threshold.
- Use identical dates, eligible markets, labels, and portfolio translation when comparing models.
- Run multiple seeds for material neural architectures and report dispersion and worst seed.
- Distinguish gross research evidence from implementation-cost diagnostics. Transaction-cost gates are not research verdict gates under current ASADO harness policy.
- Keep prediction scores separate from portfolio construction.
- Never tune on the vintage-performance/stationarity matrix after designating it as final evidence.

## 6. Residual limitations after controls

Even a correctly engineered first version will retain limitations:

- the current 34-market list may embody survivorship/selection bias;
- many economic sources lack reconstructable real-time vintages and will be excluded;
- only 307 monthly target dates exist, with heavy 12-month overlap;
- countries share global shocks, so cross-sectional rows are not independent;
- late-start sources and markets reduce comparable sample depth;
- PIT graph coverage varies by relationship type and country.

These are reportable constraints, not reasons to relax PIT standards.

## 7. Milestone 0 decision

**No-go** for training on `feature_panel_t2` or the current daily database state.

**Go** for Milestone 1 after the daily build is repaired, using a narrow PIT allowlist and the red-team suite above. No model result should be promoted until every Critical finding is mechanically closed and every remaining High finding is either closed or disclosed in the experiment manifest.
