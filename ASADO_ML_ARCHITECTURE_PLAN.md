# ASADO Deep Learning Research Platform — Architecture Plan

**Milestone:** 0
**Plan date:** 2026-08-11
**Status:** Research architecture mapped to the live repository; implementation intentionally not started
**Governing rule:** Complexity is earned only through identical-sample, point-in-time, out-of-sample improvement.

## Executive decision

ASADO is suitable for the proposed research, subject to a strict sequencing decision:

> Build the canonical PIT substrate and walk-forward engine first. Do not train the preferred neural architecture directly from `feature_panel_t2`.

The exact 12-month total-return target is already available and validated. The 34-token cross-country geometry is computationally attractive, and the loop DB contains unusually useful PIT graph vintages. The binding constraint is not compute; it is the small number of statistically independent labels and incomplete historical availability metadata.

The first research release should therefore be a compact, auditable platform with a narrow feature allowlist, strong linear/tree hurdles, native dense cross-country operations, and saved predictions/checkpoints. The proposed 1–5 million-parameter temporal attention model is a later candidate, not the starting benchmark.

## 1. Repository placement and production isolation

The main checkout is production and must remain on its current branch. Model-platform implementation should use:

```text
../ASADO-exp-deep-learning/                 # git worktree, branch exp/deep-learning
experiments/2026_08_asado_deep_learning/   # committed code/configs/small reports
Data/work/experiments/asado_deep_learning/ # frozen snapshots, tensors, checkpoints, large outputs
```

Rules:

- use `scripts/snapshot_for_experiment.py` to export required main/loop tables to Parquet and close DB connections immediately;
- record source DB path, table/view SQL, row count, schema, as-of time, file hash, and pipeline run ID in one immutable snapshot manifest;
- use a per-experiment `uv` environment; never add deep-learning packages to `ASADO/venv`;
- write no experiment output to `Data/processed`, `Data/loop`, shared pipeline work directories, `config`, or `ledgers` except through the existing approved harness/registry front door;
- do not change production launchd, daily update, loop job, or Fable consumers during research;
- merge only milestone code that passes its acceptance gate.

## 2. Canonical data contracts

### 2.1 Observation store

The canonical long-form record should contain:

| Field | Meaning |
|---|---|
| `decision_date` | Historical forecast date at which the legal information set is assembled |
| `country` | One of the 34 canonical market tokens |
| `feature_id` | Stable source-qualified feature identifier |
| `value` | Raw legal value before fold-specific preprocessing |
| `observation_date` | Period/date the value describes |
| `available_at` | First timestamp/date at which the value could be used |
| `vintage_id` | Release/file/source vintage where applicable |
| `source` / `family` / `frequency` | Provenance and taxonomy |
| `is_observed`, `is_carried`, `is_forecast` | Mutually documented state flags |
| `age_days` | Time since the source observation/release |
| `pit_class` | A, B, C, or Q admission status |
| `lineage_version` | Code/config version that produced the row |

The store must remain raw and narrow. Model-specific ranks, z-scores, clipping, imputation, and tensors are downstream, versioned transforms.

### 2.2 Target store

Targets are physically separate and keyed by `(decision_date, country)`:

- `target_start_date` and `target_end_date`;
- raw forward 12M total return;
- contemporaneous eligible-universe relative return;
- percentile rank;
- quantile class;
- label availability date;
- eligibility flag/reason.

`t2_master.12MRet` is the authoritative first implementation. `country_returns_monthly` is the independent formula/check source.

### 2.3 Universe store

Create a decision-date × market table with:

- configured membership;
- return-label availability;
- feature eligibility;
- investability/membership evidence if later reconstructed;
- macro identity (`ChinaH → ChinaA`, `NASDAQ/US SmallCap → U.S.`) while preserving separate equity tokens;
- DM/EM, region, commodity and other static groups with source/version.

The model receives an eligibility mask. It must not interpret pre-inception padding as observed zero.

### 2.4 Feature catalog

Each admitted feature requires:

- stable identifier and aliases;
- source table/column/variable;
- economic family and units;
- observation frequency;
- point-in-time/revision rule;
- publication lag or release-time source;
- legal carry/staleness limit;
- transform sign and formula;
- missingness semantics;
- forecast eligibility;
- PIT class and test evidence.

The existing variable registry should be extended or wrapped, not trusted without correction. Admission remains deny-by-default.

## 3. Date and label alignment

T2 month-end data is shifted to the first of the following month. For a row labeled `2015-06-01`:

- features must have `available_at` no later than that decision boundary;
- the return target begins in June 2015 and ends 12 months later;
- the label is unavailable for training until its complete return window has elapsed.

Every fold must enforce:

```text
feature.available_at <= decision_date
train.target_end_date <= train_information_cutoff
validation/test labels never influence fitted preprocessing or selection
```

Use a 12-month purge/embargo at validation/test boundaries. Retain monthly economic predictions, but evaluate inference through Newey–West/block methods and 12 annual-offset non-overlapping cohorts.

## 4. Initial PIT feature policy

### First headline set

Begin narrowly with source histories whose causality can be demonstrated:

1. causally rebuilt market levels and trailing return/volatility/change transforms;
2. dated GDELT histories, subject to source-age and transformation tests;
3. WEO vintage/revision rows selected by `vintage_date`;
4. `graph_edge_vintages` and `graph_features_pit_daily` only when the graph milestone begins;
5. loop market/consensus/release/flow families promoted individually after an explicit availability contract.

### Excluded at launch

- every `NMRet`/`NDRet` target or alias as an input;
- existing monthly T2 factors affected by future-aware cleaning;
- latest-vintage macro histories without reconstructable release state;
- projections treated as realized data;
- `graph_features_daily` and current Neo4j relationships for historical training;
- optimizer, combiner, family-rank, harness, and other trained outputs without PIT lineage;
- future-dated factor membership and production output surfaces.

Feature breadth should expand only after variable-level contracts and tests pass.

## 5. Walk-forward design

### 5.1 Research partitions

Subject to a formal freeze in Milestone 2, the provisional partition is:

| Role | Dates | Use |
|---|---|---|
| Burn-in/early training | 2000-02 to 2009-12 | Initial fitting and pipeline development; coverage varies |
| Walk-forward development OOS | 2010-01 to 2019-12 | Nested validation, architecture and objective selection |
| Final lockbox | 2020-01 to 2025-08 | One-time final comparison after the decision tree is frozen |

The lockbox must not be repeatedly inspected. If prior ASADO research already exposed these years for the same model-selection question, that use must be logged and the report must downgrade “untouched” to “held-out evaluation.”

### 5.2 Fold mechanics

Support:

- expanding training windows;
- rolling 10-, 15-, and 20-year windows where history permits;
- inner validation confined to the historical training information set;
- monthly predictions;
- annual full retraining initially;
- a separately labeled warm-start/fine-tuning arm;
- saved predictions for every date, including failed/abstained forecasts;
- multiple deterministic seeds for material neural models.

Full retraining and continuation from prior weights are distinct experiment dimensions. They may share evaluation dates but never be conflated.

### 5.3 Small-sample discipline

The effective sample is far smaller than 10,181 independent observations. Use:

- shared weights across countries;
- modest capacity and aggressive regularization;
- feature-family compression before broad attention;
- no country-specific model per market;
- seed distributions, decade/subset breakdowns, and country contribution;
- stable-coverage sensitivity and leave-one-country-out tests;
- model-size scaling only after a smaller model earns continuation.

## 6. Model and milestone sequence

The Section 56 fifteen-step development sequence in the PRD is the canonical naming scheme; later shortened milestone numbering should be treated as phase acceptance tests, not a conflicting reorder.

### Milestone 0 — Audit

Deliver these three documents. No model code. Record the live daily-build blocker and the PIT gaps.

### Milestone 1 — Canonical PIT dataset

Build observation, target, universe, and feature catalogs; snapshot manifests; availability joins; legal carry/masks/age; and the full leakage red-team suite.

**Validation experiment:** retrieve the exact legal 60-month history for all eligible markets on several hand-picked dates, including 2008, 2015, and a recent date, then independently verify source rows and release cutoffs.

### Milestone 2 — Walk-forward engine

Config-driven folds, 12M purge, fold-local transforms, reproducible seeds, checkpoint/prediction persistence, experiment manifests, and failure recovery.

**Validation experiment:** historical-mean and deterministic dummy-ranker runs across the full eligible history without manual steps.

### Milestone 3 — Simple and linear baselines

Equal score, historical mean, trailing-return/valuation ranks where legally available, existing ASADO methodology as a separately reconstructed comparator, OLS/ridge/lasso/elastic net, pooled panel and monthly cross-sectional models.

### Milestone 4 — Tree baselines

LightGBM and CatBoost are preferred first; add XGBoost only if it provides a concrete comparison. Use identical fold-local data and score outputs.

### Milestone 5 — Static neural network

A small feature-family MLP using the current legal snapshot. Start well below one million parameters; test larger only on a declared scaling grid. This isolates generic nonlinearity from history and country interaction.

### Milestone 6 — Temporal dataset and encoder

Create tensors shaped approximately `[date, 34, lookback, features]` plus observation, age, and eligibility masks. Test 12/24/36/60-month lookbacks. Begin with temporal convolution or GRU; add LSTM/temporal transformer only if the simpler encoder leaves a specific hypothesis unresolved.

### Milestone 7 — Cross-country attention

Use a shared country temporal state, small country embedding, optional global token, and dense self-attention across 34 tokens. Required comparison: own-country only vs pooled/no interaction vs attention.

### Milestone 8 — Explicit graph model

Build date-specific dense adjacency tensors from `graph_edge_vintages`. At 34 nodes, native dense PyTorch message passing is simpler and more auditable than requiring PyTorch Geometric initially. Compare no graph, real PIT graph, permuted graph, static graph sensitivity, and learned attention.

### Milestone 9 — Hybrid temporal graph architecture

Combine only components that independently earned retention. The first serious candidate may target 1–5 million parameters; 20 million is an experimental ceiling, not a goal.

### Milestone 10 — Self-supervised pretraining

Masked reconstruction, next-state prediction, cross-country reconstruction, or contrastive learning. Compare identical downstream architectures from random and pretrained initialization.

### Milestone 11 — Ranking objectives

Compare MSE, Huber, pairwise ranking, differentiable rank surrogate where stable, quantile classification, and a preregistered hybrid. Pair sampling and country eligibility must be fold-local.

### Milestone 12 — Portfolio layer

Keep scores immutable and separate from portfolio rules. Test equal-weight top-N, score/rank weights, long-only, long-short, volatility adjustment, caps, implementation lag, and turnover diagnostics. Report gross evidence first; costs remain implementation diagnostics under current ASADO research-verdict policy.

### Milestone 13 — Stationarity and drift

Save vintage models and produce training-vintage × evaluation-period matrices, IC/alpha half-life, expanding-vs-rolling comparisons, feature-family attribution through time, source→target country influence, aligned embedding drift, and unsupervised latent-regime diagnostics.

### Milestone 14 — Robustness, ablation, and scaling

Remove temporal history, external countries, graph, global token, feature families, country embeddings, and pretraining; run multiple seeds, leave-one-country-out, country subsets, decades, parameter scaling, and training-data scaling.

### Milestone 15 — Candidate production model

Only after a fixed model wins the predefined scorecard. Lock dependencies, features, training policy, monitoring, failure handling, and versioning. Research never writes production scores automatically.

## 7. First candidate neural architecture

The PRD's preferred candidate maps cleanly to the verified data geometry:

```text
legal values + masks + age
  -> per-family projections
  -> shared country temporal encoder (60 months)
  -> small learned market embedding
  -> 1-2 cross-country attention blocks over 34 tokens
  -> optional global-regime token
  -> shared country scoring head
  -> 34 scores and optional raw-return estimates
```

Recommended initial constraints:

- hidden dimension 96–192;
- one or two temporal/attention blocks;
- four or fewer attention heads;
- small market embeddings;
- dropout, weight decay, feature-family dropout, stochastic masking, and early stopping;
- 1–5 million parameters only after the static/temporal comparisons justify it;
- no per-country output network beyond a shared head plus market embedding.

The global token, graph exchange, and pretraining are individually removable modules, not inseparable design choices.

## 8. Objectives and outputs

Every model emits one scalar ranking score per eligible market. It may also emit a raw-return estimate or quantile probabilities.

Supported losses:

- MSE and Huber for raw/relative return;
- pairwise ranking over eligible same-date pairs;
- quantile classification;
- a preregistered hybrid whose weights are selected only inside nested validation.

Save raw outputs before any portfolio translation:

```text
experiment_id, model_vintage, decision_date, country,
eligibility, score, return_estimate, class_probabilities,
seed, checkpoint_id, data_manifest_id
```

## 9. Evaluation and promotion scorecard

### Prediction and ranking

- Pearson and Spearman correlation;
- monthly cross-sectional IC and rank IC;
- MAE/RMSE and directional hit rate;
- score-bucket monotonicity;
- top and bottom bucket returns and spread.

### Portfolio translation

- annualized return/volatility, Sharpe, Sortino, drawdown;
- turnover and implementation-lag sensitivity;
- concentration, effective number of markets, and market-level P&L contribution;
- DM/EM, region, decade, regime, and stable-coverage breakdowns.

### Statistical dependence

- Newey–West/block inference appropriate to 12M overlap;
- 12 non-overlapping annual-offset cohorts;
- seed mean, dispersion, best and worst seed;
- country/block bootstrap only where its dependence assumptions are explicit.

### Promotion

Predeclare an incumbent and require improvement on an aggregate scorecard including rank IC, gross top-minus-bottom performance, drawdown, period/seed robustness, concentration, and complexity. A small gain with materially greater fragility or cost may be rejected. No single historical Sharpe promotes a model.

## 10. Reproducibility and registry

Each run needs a machine-readable manifest containing:

- experiment and parent IDs, hypothesis, status, and conclusion;
- Git commit and dirty-tree status;
- snapshot/data manifest IDs and file hashes;
- feature-catalog and universe versions;
- target definition and fold dates;
- architecture, parameter count, optimizer, learning rate, epochs, early stopping;
- preprocessing graph and fitted-state hashes;
- seed, deterministic settings, hardware/backend, package lock;
- predictions, checkpoints, logs, plots, metrics, and report paths.

Use append-only JSONL for custody and Parquet/DuckDB snapshots for analysis. Integrate conclusions with the existing ASADO hypothesis/methodology ledgers rather than create a disconnected success registry. Failed experiments remain recorded.

Every major run renders the PRD template: Objective, Implementation, Data Used, Validation, Results, Comparison, Problems, Decision.

## 11. Technology plan

Live hardware is an Apple M4 Max with 128 GB unified memory. The production venv is Python 3.14 and currently contains scikit-learn but not PyTorch or the requested boosting/graph stacks.

Recommended isolated stack:

- Python version supported by the selected stable PyTorch release;
- PyTorch with MPS for neural training;
- NumPy/Pandas/Polars or DuckDB/Arrow for deterministic dataset preparation;
- scikit-learn for linear baselines/preprocessing;
- LightGBM and CatBoost for tree baselines;
- native dense PyTorch graph operations at 34 nodes;
- YAML/Pydantic-style immutable configs and Parquet/JSONL artifacts;
- existing ASADO ledger/report conventions before adding a hosted experiment tracker.

Package versions must be locked in the experiment directory. MPS numerical reproducibility should be tested rather than assumed; material models also need a CPU determinism smoke test.

## 12. Automated test plan

### Data/PIT

- exact 34-name configured universe and time-varying eligibility;
- date ordering, expected grain, duplicates, and target formula;
- source availability, publication lag, vintage, projection, carry, staleness, and prefix invariance;
- target/input physical separation and lineage blacklist;
- masks and feature age.

### Walk-forward/reproducibility

- no feature availability or training target after cutoff;
- 12M purge boundaries;
- train-only fitted preprocessing;
- identical fold IDs/config/data hashes;
- same seed gives materially identical predictions on the supported backend;
- interrupted runs resume without duplicating predictions.

### Models/tensors

- `[batch, country, time, feature]` shapes;
- country/feature/time masks;
- all-missing family behavior;
- padding invariance for ineligible countries;
- permutation-equivariance tests where country identity is intentionally absent;
- graph adjacency vintage and shape tests.

### Portfolio/reports

- weights sum and caps;
- implementation lag and return alignment;
- turnover and contribution reconciliation;
- gross cumulative return arithmetic;
- all leaderboard models use identical eligible rows;
- plots regenerate from saved predictions, never hand-entered sheets.

## 13. Milestone 1 implementation package

The next authorized milestone should produce:

```text
experiments/2026_08_asado_deep_learning/
  README.md
  configs/
    features_v1.yaml
    availability_rules_v1.yaml
    universe_v1.yaml
  src/asado_ml/
    snapshot.py
    catalog.py
    targets.py
    universe.py
    point_in_time.py
    dataset.py
  tests/
    fixtures/
    test_targets.py
    test_availability.py
    test_prefix_invariance.py
    test_leakage_red_team.py
    test_universe.py
  reports/MILESTONE_1_*.md
```

Large Parquet snapshots, tensors, and diagnostics remain under `Data/work/experiments/asado_deep_learning/`.

### Milestone 1 exit gate

Proceed to the walk-forward engine only when:

1. the current daily-build failure is repaired and the required source snapshot is internally consistent;
2. targets and inputs are physically separate;
3. every admitted feature has an explicit PIT contract;
4. all critical leakage red-team tests pass;
5. arbitrary-date reconstruction is independently checked on several historical dates;
6. adding later source data cannot change earlier canonical rows;
7. the snapshot and dataset rebuild reproducibly from committed code/config plus immutable manifests.

## 14. Open decisions to freeze in Milestones 1–2

- exact first-feature allowlist after source-level availability proof;
- formal lockbox dates and whether prior ASADO research makes them previously observed;
- conservative release-lag policy for non-vintage macro sources;
- stable-coverage headline universe versus dynamic eligible universe as primary;
- annual model-refit month and prediction timestamp;
- incumbent ASADO production-methodology reconstruction;
- primary promotion scorecard weights;
- package/Python versions after an isolated Apple-Silicon compatibility smoke test.

These choices affect evidence, not merely software style, so they must be versioned before model comparison.

## 15. Final Milestone 0 decision

The research should proceed, but only to canonical-dataset construction next. ASADO's target, country geometry, historical depth, and PIT relationship vintages justify the program. Its current feature view and semantic metadata do not justify a neural-network result yet.

The shortest rigorous path is:

```text
repair/verify daily source state
  -> freeze immutable snapshots
  -> build/test legal PIT dataset
  -> run identical-sample baselines
  -> add temporal history
  -> add cross-country interaction
  -> add graph/pretraining only when each earns retention
  -> use saved vintage models to answer stationarity
```
