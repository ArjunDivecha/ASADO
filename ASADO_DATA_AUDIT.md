# ASADO Deep Learning Research Platform — Data Audit

**Milestone:** 0
**Audit date:** 2026-08-11
**Status:** Complete for planning; conditional go for Milestone 1
**Scope:** Live repository, `Data/asado.duckdb`, `Data/loop/asado_loop.duckdb`, Neo4j, pipeline code, generated references, tests, and current run logs. All database inspection was read-only and short-lived.

## Executive verdict

ASADO has a strong target and a rich research substrate, but it does **not yet have a canonical point-in-time ML feature store**.

The requested target already exists: `t2_master.variable='12MRet'` is a forward 12-month **total return** derived from Bloomberg total-return indices. It contains 10,181 usable country-month labels across 307 prediction months. It is exactly equal, to floating-point precision, to compounding the next 12 rows of the canonical one-month return table. The target must remain physically separate from model inputs.

The feature side is less ready. The current `feature_panel_t2` view has 3,322,573 rows, 726 distinct variables, and the correct 34 market names, but:

- it has no universal `available_at` or first-knowable timestamp;
- all 1,440 semantic-registry rows have blank publication-lag, revision, and vintage fields;
- many macro histories are latest-vintage/reference-period data;
- monthly T2 raw factors were cleaned with full-sample winsorization and a symmetric past/future outlier window;
- forward-return targets are physically present in the same query-facing feature view;
- current/future projections extend to 2031 and 2100;
- current-weight graph features coexist with the valid PIT graph surface.

Therefore:

> **GO** for building Milestone 1's strict canonical dataset. **NO-GO** for training or publishing a headline model directly from the existing wide `feature_panel_t2` view.

The first model-ready dataset must use a PIT allowlist, create `available_at` explicitly, preserve observation masks and age, and quarantine everything whose historical knowability is not proven.

## 1. Authoritative stores and rebuild behavior

| Store | Live state on audit date | Role | Persistence rule |
|---|---:|---|---|
| `Data/asado.duckdb` | 3.2 GB; 43 tables/views | Rebuildable analytical warehouse | `scripts/setup_duckdb.py` recreates it. Never add durable experiment tables here. |
| `Data/loop/asado_loop.duckdb` | 177 MB; 66 tables/views | Persistent research, signals, graph vintages, ledgers, outcomes | Durable loop state, generally parquet-first. Experiments still snapshot rather than hold a connection. |
| Neo4j | running; 7 node labels, 11 relationship types | Current graph/explainability surface | Current graph is not a historical PIT feature store. |
| `Data/work/experiments/<name>/` | gitignored | Frozen snapshots and large run artifacts | Required scratch location for this research. |
| `experiments/<YYYY_MM>_<name>/` | committed | Code, configs, small reports, reproducibility manifests | Required keepable experiment location. |

The generated references are useful but can lag live state. `docs/factor_reference.md` was generated on 2026-08-09; this audit found a material 2026-08-11 daily-build failure after that generation. Live database state and current logs take precedence over generated counts.

## 2. Main warehouse map

### 2.1 Canonical country-feature surfaces

| Object | Type | Live rows | Date range | Countries | Variables | Intended grain |
|---|---|---:|---|---:|---:|---|
| `t2_master` | table | 1,085,246 | 2000-02 to 2026-08 | 34 | 111 | date × market × variable; includes normalized T2 features and forward-return labels |
| `t2_raw` | table | 477,965 | 2000-02 to 2026-08 | 34 | 53 | date × market × raw T2 variable; null rows omitted |
| `external_factors` | table | 138,042 | 1985-01 to 2026-07 | 43 | 35 | date × country × variable × source |
| `extended_factors` | table | 115,881 | 1990-12 to 2026-12 | 43 | 53 | date × country × variable × source |
| `imf_factors` | table | 125,474 | 1980-12 to 2031-12 | 43 | 26 | date × country × variable × source; includes forecasts |
| `macrostructure_factors` | table | 97,105 | 1995-03 to 2026-08 | 43 | 26 | date × country × variable × source |
| `bloomberg_factors` | table | 106,600 | 1975-12 to 2026-08 | 34 | 31 | date × country × variable × source |
| `gdelt_panel` | table | 420,512 | 2015-09 to 2026-09 | 34 | 93 | month × market × variable; includes a return alias |
| `normalized_panel` | table | 964,935 | 1950-12 to 2100-12 | 43 | 299 | raw source rows transformed to `_CS`/`_TS`; includes normalization provenance |
| `unified_panel` | view | 2,586,851 | 1950-12 to 2100-12 | 43 | 431 | raw union; includes non-T2 countries and future projections |
| `feature_panel` | view | 3,551,786 | 1950-12 to 2100-12 | 43 | 730 | `unified_panel UNION ALL normalized_panel` |
| `feature_panel_t2` | view | 3,322,573 | 1950-12 to 2100-12 | **34** | **726** | T2-filtered query view; default discovery surface, not yet a PIT ML contract |

All expected-grain duplicate checks returned zero for the tables above. `feature_panel_t2` also has zero duplicates at `(date, country, variable, source)`.

### 2.2 Daily surfaces

| Object | Live rows | Date range | Markets/variables | Notes |
|---|---:|---|---|---|
| `t2_factors_daily` | 21,275,024 | 2000-01-01 to 2026-08-11 | 34 / 65 | Current partial daily rebuild; 4,045,184 stored null values. |
| `t2_levels_daily` | 15,441,474 | 2000-01-01 to 2026-08-10 | 34 / 48 | Raw daily levels; backward-looking rolling cleaning in the daily builder. |
| `gdelt_factors_daily` | 5,164,056 | 2015-02-18 to 2026-08-10 | 34 / 37 | Daily GDELT factors. |
| `gdelt_raw_daily` | 965,756 | 2015-02-18 to 2026-08-10 | 249 ISO3 entities / wide schema | News bridge, not directly tensor-ready. |
| `daily_calendar` | 330,446 | 2000-01-01 onward | 34 | Date × market trading-day mask. |
| `factor_returns_daily` | **0** | — | — | Current live failure, described in Section 10. |

### 2.3 Returns and optimizer outputs

| Object | Live rows | Role | Input eligibility |
|---|---:|---|---|
| `factor_returns` | 106,816 | Monthly top-bucket factor-portfolio returns; 390 factors, 3 sources | Benchmark/outcome only; excluded from feature union to prevent cycles |
| `factor_returns_daily` | 0 currently | Daily factor-portfolio returns | Benchmark/outcome only |
| `factor_top20_membership` | 748,446 | Sparse monthly long-bucket membership; dates reach 2026-09 | Baseline reconstruction only, never unrestricted model input |
| `country_factor_attribution` | view | Membership × factor return | Descriptive/output surface, not causal input |
| `country_returns_monthly` (loop DB) | 10,555 | Canonical realized one-month total returns | Outcome/target construction only |

### 2.4 Isolated and auxiliary main-DB surfaces

- `ff_factors`: 542,125 region-keyed Fama-French rows, 8 regions, monthly/daily. It must remain isolated and be joined by date/region for spanning tests.
- `jst_macrohistory`: 83,725 rows for 13 developed markets, 1870–2020. Calibration/context only; never tile it into the T2 panel.
- World Bank commodity tables and `commodity_panel`: global date-keyed series, not country observations. Join once by date rather than repeating them as 34 independent rows.
- `bilateral_portfolio_matrix`: 92,079 reporter–counterparty–instrument rows, 1997–2026. It is relationship data, not a simple country feature panel.
- `predmkt_*`: isolated snapshot/metadata/spillover tables. `predmkt_resolutions` is empty.
- `event_log`: 146 curated events and the only main analytical table besides registry/prediction-market dimensions with a primary key.
- `variable_registry`, `variable_registry_facts`, `variable_registry_full`, `variable_meta`: semantic and structural metadata; incomplete for PIT use as described below.

### 2.5 Column, date, and key conventions

The dominant main-warehouse schema is long form:

```text
date DATE, country VARCHAR, value DOUBLE, variable VARCHAR[, source VARCHAR]
```

`t2_master` and `t2_raw` omit `source`; their table identity supplies provenance. `normalized_panel` adds `normalization`, `base_variable`, `normalization_origin`, `lookback_observations`, and `min_observations`. `feature_panel_t2` projects the common five-column schema.

Important alternative schemas are:

| Object | Columns defining its grain/date semantics |
|---|---|
| `factor_returns` | `date, factor, value, source` |
| `factor_top20_membership` | `date, country, factor, weight, source` |
| `bilateral_portfolio_matrix` | `date, reporter_iso3, counterpart_iso3, instrument_type, amount_usd, shares, source, frequency, is_official_sector` |
| `country_returns_monthly` | `date TIMESTAMP, country, return_1m` |
| `graph_edge_vintages` | `edge_type, vintage_end, applies_from, focal, neighbor, weight` |
| `weo_vintages` | `vintage, vintage_date, country, target_year, variable, value, source` |
| `consensus_daily` | `date, country, target_year, value, variable, source` |

Most analytical fact tables declare nullable columns and no database primary key or check constraint; uniqueness is enforced in build code/tests and was independently checked at the expected grains during this audit. `variable_registry.variable` is a declared primary key. `event_log` and prediction-market/registry dimensions also have declared keys. The canonical ML layer must not infer integrity from DuckDB constraints alone; it must assert grain, nullability, date order, and referential membership on every build.

The generic `date` field is not semantically uniform: it may mean shifted market month, economic reference period, release/observation day, factor-return period, or snapshot date. Only specialized tables such as `weo_vintages` and `graph_edge_vintages` currently expose an explicit vintage/availability field. Milestone 1 must normalize these meanings into separate `observation_date`, `available_at`, `decision_date`, and target-window fields.

## 3. Loop database map

The 66 live objects fall into these ML-relevant families:

| Family | Tables/views | Main grain and use |
|---|---|---|
| Canonical outcome | `country_returns_monthly` | month × market × realized 1M total return |
| Market implied | `market_implied_daily`, `market_implied_signals` | day × market × variable; FX vol/RR/carry and global stress |
| Sovereign | `sovereign_daily`, `sovereign_signals`, `sov_ratings_monthly`, `sov_rating_changes` | day/month × market × variable or dated rating event |
| Consensus/macro surprise | `consensus_daily`, `consensus_revisions`, `consensus_signals`, `eco_surprise_monthly`, `eco_surprise_signals` | dated vintage-like consensus paths and realized release surprises |
| Flows/positioning | `etf_flows`, `etf_flow_signals`, `foreign_flows_daily`, `cot_weekly`, `cot_signals` | day/week × market or commodity × variable |
| Valuation | `valuation_monthly` | month × market × variable; derived from T2/sovereign inputs |
| WEO vintages | `weo_vintages`, `weo_revisions` | vintage date × country × target year × variable |
| PIT relationships | `graph_edge_vintages`, `graph_features_pit_daily` | published edge vintage with `applies_from`; day × market PIT graph feature |
| Non-PIT/current relationships | `graph_edge_snapshots`, `graph_features_daily` | current/snapshot edges projected over history; quarantine for headline ML |
| Learned research outputs | `combiner_scores*`, `combiner_weights`, `similarity_features_daily`, `leadlag_features_daily`, `family_ranks_daily`, `triptych_*` | trained or discovered outputs; comparators/ablation evidence, not raw features by default |
| Harness/registry | `hypothesis_ledger`, `methodology_ledger`, `harness_results`, `harness_ic_series`, `live_signals` | experiment custody and measured verdicts |
| Gap/dislocation system | `dislocation_daily`, `gap_*`, `price_state_*`, `outcome_attribution`, `fable_claims` | prospective research state and outcome tracking |
| Operational/context | portfolio, ETF price, calendar, evidence, Brier Gate, thesis, and review tables | supporting context, not a single homogeneous training panel |

Most loop signal tables use `(date, country, value, variable, source)`. Exceptions include event rows, ledgers, JSON state, edge lists, target-year consensus/WEO rows, and commodity-level COT rows.

`loop_variable_meta` has only seven rows, all for legacy graph variables. It does not provide a complete semantic contract for the loop's signal-bearing families.

## 4. Country universe audit

### 4.1 The model universe is 34 equity markets, not 34 sovereigns

The canonical list is `scripts/loop/loopdb.py::T2_UNIVERSE`, also embedded in `feature_panel_t2`:

Australia, Brazil, Canada, Chile, ChinaA, ChinaH, Denmark, France, Germany, Hong Kong, India, Indonesia, Italy, Japan, Korea, Malaysia, Mexico, NASDAQ, Netherlands, Philippines, Poland, Saudi Arabia, Singapore, South Africa, Spain, Sweden, Switzerland, Taiwan, Thailand, Turkey, U.K., U.S., US SmallCap, Vietnam.

Three entries are market sleeves rather than separate sovereigns:

- ChinaH shares ChinaA's CHN macro identity.
- NASDAQ and US SmallCap share the U.S. macro identity.

`country_reference` has 40 rows: 31 T2 sovereign/proxy rows plus nine auxiliary countries used by broader sources. It deliberately does not add separate reference rows for the three sleeves.

### 4.2 The mapping file is not the universe

`config/country_mapping.json` contains 43 entries: the 34 T2 market names plus Austria, Belgium, Finland, Greece, Ireland, New Zealand, Norway, Portugal, and Russian Federation. Code that treats this file's keys as the investable universe is wrong. The 34-name loop constant is authoritative.

### 4.3 Historical eligibility changes even though the configured list is fixed

Usable `12MRet` label history is:

| Markets | First usable label | Last usable label on audit date |
|---|---|---|
| 32 markets | 2000-02 | 2025-08 |
| Vietnam | 2006-12 | 2025-08 |
| Saudi Arabia | 2014-09 | 2025-08 |

Thus the configured universe is fixed but the **eligible labeled cross-section is time-varying: 32 → 33 → 34**. There is no historical membership table proving that all currently selected markets/sleeves would have been chosen in 2000. This is a survivorship-bias limitation, not merely missing data.

## 5. Target-return audit

### 5.1 Source and formula

`scripts/build_t2_master.py` reads the Bloomberg `Tot Return Index` sheet and calculates:

```text
12MRet[c, t] = TRI[c, t+12] / TRI[c, t] - 1
```

Dates are shifted from Bloomberg month-end to the first day of the next month. A row dated `YYYY-MM-01` is therefore the label for the 12-month holding window starting in that month, using information/features observed through the prior month-end.

### 5.2 Live target statistics

| Property | Live value |
|---|---:|
| Stored rows including unavailable tail | 10,846 |
| Usable non-null labels | **10,181** |
| Prediction months | **307** (`2000-02` through `2025-08`) |
| Markets with at least one label | 34 |
| Minimum / maximum return | -69.33% / +270.35% |
| Missing stored labels | 665: final 12 months for every market, plus pre-history for Saudi Arabia and Vietnam |
| Duplicate `(date,country)` labels | 0 |

The target was independently reconciled against `country_returns_monthly`: compounding the next 12 one-month rows reproduced all 10,181 usable `12MRet` values with maximum absolute error `1.56e-15`.

### 5.3 Required target representations

Milestone 1 should materialize, from the same raw label rows:

- `return_12m_raw`;
- `return_12m_relative` = raw return minus the contemporaneous eligible-country mean;
- `return_12m_rank_pct` among eligible markets;
- top/middle/bottom or quintile labels;
- `target_start_date`, `target_end_date`, and `label_available_at`;
- an eligibility mask and reason.

The primary investment target should be relative/rank. Raw return remains useful for calibration and error diagnostics.

### 5.4 Target overlap

Monthly 12M labels create 307 economic prediction dates but only 25–26 observations in each non-overlapping calendar-month subset. The 10,181 country rows are not 10,181 independent samples: countries share global shocks and adjacent monthly targets share 11 of 12 return months.

Headline inference must use 12-month-aware Newey–West/block methods and separately report the 12 non-overlapping annual-offset cohorts.

## 6. Feature inventory and taxonomy

The current `feature_panel` registry classifies 726 T2-view variables roughly as:

| Registry concept | Variables |
|---|---:|
| Structural | 191 |
| External/unclassified external | 169 |
| Unset concept | 99 |
| Monetary | 82 |
| Growth | 50 |
| Sentiment | 36 |
| Valuation | 33 |
| Commodity | 27 |
| Technical | 27 |
| Momentum | 16 |

By native frequency the registry reports 503 monthly, 159 annual, 65 quarterly, and 3 daily variables. The separate daily tables contain many more daily variables and are not fully represented in this count.

Actual model families should follow economic and provenance boundaries:

1. market/trailing return and technical;
2. valuation/fundamentals;
3. macro growth/inflation/fiscal/external balance;
4. rates/credit/currency;
5. commodities/global markets;
6. flows/positioning;
7. news/sentiment/policy;
8. explicit country relationships;
9. static country/market identity;
10. global regime context.

The source, not merely the variable name, must remain part of the feature key.

## 7. Missingness and coverage

The long tables often omit missing rows, so stored-column `NULL%` is not the correct completeness statistic. Coverage must be measured against the expected date × market grid.

Across the 307 usable target dates and 34 markets:

- T2 normalized variables average 80.5% raw-grid coverage; only 44 of 111 exceed 95%.
- T2 raw variables average 82.8%; 24 of 53 exceed 95%.
- GDELT variables average 39.1% because history begins in 2015.
- Bloomberg feature-panel variables average 37.5% and have unequal country/start-date coverage.
- Annual World Bank variables average 7.0% before any legal carry-forward.
- IMF CPI is relatively dense at 86.6%; many annual/quarterly families are sparse on the raw monthly grid.

The canonical dataset must distinguish:

- observed now;
- legally carried from an earlier release;
- not yet released;
- structurally unavailable for this market;
- forecast/projection;
- source failure/staleness.

Required tensor auxiliaries are an observation mask, carried-value mask, feature age/time-since-observation, and country eligibility mask. Imputation values must be fitted inside each training fold only.

## 8. Normalization audit

There are two normalization systems:

1. `scripts/t2_normalize.py` creates T2 `_CS` and expanding `_TS` scores and flips selected variables so higher generally means more attractive.
2. `scripts/build_normalized_panel.py` creates same-date `_CS` and trailing-window `_TS` scores for non-T2 sources. Windows are 252 daily, 60 monthly, 20 quarterly, or 10 annual observations, with corresponding minimum-history rules.

The second system computes cross-sectional scores **before** `feature_panel_t2` filters to the 34 T2 markets. Some macro `_CS` values therefore use up to 43 countries, not the target universe. This is not future leakage, but it is a universe-definition mismatch and should not be silently mixed with T2-only `_CS` values.

For ML, raw legally available values should enter the canonical store first. Model-specific cross-sectional ranks/z-scores and time-series transforms should be generated by the dataset builder with a versioned rule and fold-safe parameters.

## 9. Relationship and graph data

### 9.1 Current Neo4j graph

Live nodes: 43 Country, 673 Factor, 38 DataSource, 31 CentralBank, 15 CrisisEvent, 6 SanctionsProgram, and 4 Commodity nodes.

Live relationship counts include 1,540 `TRADES_WITH`, 933 `HAS_BANKING_EXPOSURE_TO`, 3,149 `HOLDS_PORTFOLIO`, 170 `SIMILAR_TO`, 210 `LEADS`, and 13,759 `HAS_FACTOR_EXPOSURE` edges.

This graph is excellent for current exploration but is not itself a historical adjacency archive.

### 9.2 PIT edge store

`graph_edge_vintages` is the valid temporal relationship source:

| Edge type | Rows | Vintages | Focal coverage | Vintage range | `applies_from` rule |
|---|---:|---:|---:|---|---|
| Bank | 51,434 | 109 | 21 | 1999-Q1 to 2026-Q1 | publication lag embedded |
| Holder | 18,078 | 25 | 31 | 1997 to 2024 | nine-month lag embedded |
| Trade | 24,288 | 27 | 30 | 1999 to 2025 | four-month lag embedded |

`graph_features_pit_daily` contains ten PIT variables. The parallel `graph_features_daily` table uses non-PIT/current relationships and must be quarantined from headline historical ML.

## 10. Current operational/data-health findings

### Critical — daily return table was destructively emptied by a failed build

On 2026-08-11, `scripts/build_daily_panels.py` dropped and recreated `factor_returns_daily`, then failed before inserting rows because the `Monthly_Net_Returns` sheet in `Data/work/t2_daily/T2_Optimizer.xlsx` now exposes `Unnamed: 0`, while the loader requires a column named `Date`.

Evidence:

- three build attempts failed with `KeyError: 'Date'`;
- the generated 2026-08-09 reference reported 1,177,710 rows;
- the live table now has 0 rows;
- the failure occurred after other daily tables were replaced, so the main DB is a partial-build state;
- the daily progress file stops before the DB/loop stages.

This does not corrupt the monthly `12MRet` target, but it invalidates any assumption that all daily baselines are currently available. It must be repaired and revalidated before Milestone 1 snapshots any daily input.

### High — generated references are stale relative to the live DB

`docs/factor_reference.md` still reports the pre-failure daily tables. Snapshot manifests must record live counts, and automated health checks should reject a zero-row canonical return table.

### Medium — semantic registry contains a target-definition error

`variable_registry_full` describes `12MRet` as a trailing 12-month **price** return. Source code and exact reconciliation prove it is a forward 12-month **total** return. The ML target contract must use source-code semantics, and the registry entry needs correction before it can certify the dataset.

## 11. Existing reusable research infrastructure

- `scripts/harness/evaluate_signal.py`: forward-return blacklist, PIT lag logic, rank IC, Newey–West statistics, gross portfolio scorecard, and family trial accounting.
- `scripts/loop/build_combiner.py`: expanding-window ridge pattern and historical refits.
- `scripts/snapshot_for_experiment.py`: safe main/loop parquet snapshots with manifests.
- `scripts/loop/build_country_returns.py`: canonical 1M outcome materialization and quality gates.
- `scripts/loop/build_graph_features_pit.py`: PIT relationship-feature pattern.
- `scripts/harness/ff_spanning.py`: style-spanning diagnostics.
- `regime/`, `regime_factor_selection/`, `scripts/loop/event_study.py`, and Triptych: existing time/regime/robustness research components.
- append-only hypothesis/methodology ledgers and family registry: promotion custody chain.

There is no general nested walk-forward ML engine, no tensor dataset layer, no neural-model registry, and no installed PyTorch/LightGBM/XGBoost/CatBoost stack in the production venv. Those should be built in an isolated experiment environment rather than added to the nightly environment.

## 12. Point-in-time readiness classification

| Class | Meaning | Current examples | Milestone 1 action |
|---|---|---|---|
| A — proven/derivable | Historical value and availability rule can be reconstructed | `12MRet` target; trailing returns from TRI; daily market histories with causal cleaning; GDELT dated history; `graph_edge_vintages`; WEO vintage tables | Allow after automated PIT tests |
| B — usable after explicit contract | Plausibly historical but publication/revision semantics need a documented conservative rule | FRED/BIS/OECD market/economic rows; Bloomberg consensus/release surfaces; loop flows/ratings | Require source-specific `available_at`, revision policy, and test |
| C — non-headline/latest-vintage | Historical reconstruction is not currently possible from stored data | World Bank/IMF/reference-period histories without vintages; current `imf_weo`; demographics projections | Exclude from headline experiments; descriptive/sensitivity only |
| Q — quarantine | Known contamination or trained/future output | `NMRet`/`NDRet` as features; monthly T2 full-sample-cleaned factors; non-PIT graph; optimizer outputs; current/future rows | Block mechanically |

## 13. Milestone 0 acceptance assessment

This audit answers:

- **What observations exist?** The warehouse/loop/graph inventory and generated variable references provide the map.
- **At what dates and for which markets?** Live ranges and the 32→33→34 label eligibility are documented.
- **When was each value known?** For many sources, the answer is currently **not encoded**; that is a blocking finding, not an assumption.
- **What is the target?** Forward 12M total return from TRI, aligned to the prediction-start month and independently reconciled.
- **Which features are legal?** Only the Class A allowlist today; Class B after explicit contracts; Classes C/Q excluded from headline work.

**Decision:** proceed to Milestone 1 only after fixing the current partial daily build and implementing the PIT contracts specified in `ASADO_ML_ARCHITECTURE_PLAN.md`.

## 14. Reproduction queries

All checks were run with `./venv/bin/python` and `duckdb.connect(..., read_only=True)`.

```sql
-- Live objects and schemas
SELECT table_type, table_name
FROM information_schema.tables
WHERE table_schema='main'
ORDER BY table_type, table_name;

-- Exact target inventory
SELECT count(*) FILTER (WHERE value IS NOT NULL) AS usable_labels,
       count(DISTINCT date) FILTER (WHERE value IS NOT NULL) AS prediction_months,
       count(DISTINCT country) FILTER (WHERE value IS NOT NULL) AS markets,
       min(date) FILTER (WHERE value IS NOT NULL) AS first_date,
       max(date) FILTER (WHERE value IS NOT NULL) AS last_date
FROM t2_master
WHERE variable='12MRet';

-- Expected-grain duplicates
SELECT count(*) - count(DISTINCT (date,country,variable,source)) AS duplicate_rows
FROM feature_panel_t2;

-- Registry PIT completeness
SELECT count(*) AS registry_rows,
       sum(nullif(trim(publication_lag),'') IS NOT NULL) AS lag_filled,
       sum(revision_prone IS NOT NULL) AS revision_filled,
       sum(nullif(trim(vintage_available),'') IS NOT NULL) AS vintage_filled
FROM variable_registry;

-- Forbidden forward labels physically present in the discovery view
SELECT source, variable, count(*)
FROM feature_panel_t2
WHERE variable IN ('1MRet','3MRet','6MRet','9MRet','12MRet')
GROUP BY source, variable;
```
