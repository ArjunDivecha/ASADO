# STRATEGY #1 — WORLD-STATE ANALOG COUNTRY SELECTION (v1 MVP)
## Product Requirements Document v1.0

**Project:** Country Equity Autoresearch — Strategy #1
**Author:** Arjun Divecha (drafted with Claude)
**Date:** April 2026
**Status:** Ready for implementation
**Runtime:** Any machine with Python 3.9+ and the existing ASADO venv. No Bloomberg required for v1.
**Depends on:** `asado.duckdb` (`feature_panel`, `normalized_panel`, `t2_master`), `AsadoDB` bridge, existing Almgren-Chriss transaction-cost utilities.

---

## 1. PURPOSE

Build a country-selection signal generator that, at every month-end *t* from a backtest start date through the live present, represents the joint state of the 34-country system as a single high-dimensional vector, finds the *k* most similar historical months from the library of dates strictly earlier than *t*, and produces an expected-return score and rank for each of the 34 countries based on the similarity-weighted median of those historical analogs' next-month MSCI total returns in USD. The output is a Parquet signal file suitable for handoff to a downstream portfolio-construction layer.

The thesis: **if the world's joint factor + regime state at t looks like it did at t′ in history, the cross-sectional distribution of country returns over t → t+1 should resemble the one observed at t′ → t′+1.** The bet is that this analog-based predictor adds value over — or is at least orthogonal to — the existing trailing-60-month factor-momentum baseline at ~6.5% annualized.

v1 delivers a Phase 0 + Phase 1 MVP: baselines, PIT audit, one fully walk-forward backtest, an IR read versus the 60-month factor-momentum benchmark, and a written go/no-go memo. v1 is explicitly not production-ready and does not yet exploit the Neo4j bilateral-edge layer — that is Phase 5 and deferred.

---

## 2. WHY THIS STRATEGY NOW

Three things have changed that make this worth building:

**The data surface exists.** ASADO's `feature_panel` view unifies 332 variables across 26 free sources plus Bloomberg into a single tidy panel with ~2.5M rows from 1975-12 through 2031-12. The normalized `_CS` / `_TS` feature layer gives you cross-sectionally z-scored inputs that are the right form for building state vectors. Before ASADO, assembling the world-state at any historical date required an afternoon per date.

**The graph layer gives an edge others don't have.** Even though v1 uses only country-level factors, the bilateral trade, banking, and portfolio-ownership edges are ready for Phase 5. Most published analog-forecasting work is pure factor-vector matching and cannot express "these two periods were structurally similar in how the countries were connected."

**The baseline to beat is weak-to-moderate.** Trailing 60-month factor momentum at ~6.5% annualized is a real number but not a dominant one. There is headroom for a complementary signal that is orthogonal in construction.

Academic support: Ehsani & Linnainmaa (2022) on factor momentum, Zaremba et al. (2022) on cross-country ML, BBVA and Macrosynergy on systematic country selection. Historical-analog forecasting has a long tradition in macro (Shiller's analogs, IMF scenario work) but is under-applied at the country-equity-selection layer.

---

## 3. EXISTING INFRASTRUCTURE REUSED

### 3.1 Data

**DuckDB (`Data/asado.duckdb`).** Core inputs:

- `feature_panel` (view) — raw + normalized factor rows, schema `(date DATE, country VARCHAR, value DOUBLE, variable VARCHAR)`.
- `normalized_panel` — `_CS` (cross-sectional z-score) and `_TS` (time-series z-score) versions of every factor. v1 uses `_CS` columns as the inputs to state-vector construction.
- `t2_master` — canonical normalized T2 factor panel, used for baseline factor-momentum benchmark.
- Supporting: `external_factors`, `extended_factors`, `imf_factors`, `bloomberg_factors`, `macrostructure_factors`, `gdelt_panel`. Not accessed directly in v1 — consumed via `feature_panel`.

**T2 monthly country total returns.** The dependent variable is MSCI country total return in USD. Source path: the existing T2 Master workbook at `.../A Complete/T2 Factor Timing Fuzzy/T2 Master.xlsx` or its `Normalized_T2_MasterCSV.csv` equivalent. One of the first Phase 0 tasks is to confirm the exact sheet and column that carries monthly MSCI country TR USD and mirror it into DuckDB as `country_returns_monthly(date, country, mtd_return_usd)`.

### 3.2 Code

- `scripts/db_bridge.py::AsadoDB` — unified query interface. v1 uses `db.query_panel()` for all DuckDB reads.
- Existing Almgren-Chriss transaction cost utilities (path to be confirmed during Phase 0). v1 takes the model as a black box and reports both pre-cost and post-cost results.
- Existing venv at `ASADO/venv/`. No new dependencies expected beyond `scikit-learn` (already installed for PCA) and `pyarrow` (already installed).

### 3.3 Not used in v1

- Neo4j knowledge graph and `countryStateIndex` — deferred to Phase 5 in the roadmap.
- Bilateral trade / banking / portfolio matrices — deferred to Phase 5.
- IBKR MCP server — v1 is signal-only; no order routing.

---

## 4. OUTPUT SPECIFICATION

### 4.1 Primary signal file

**Path:** `Data/strategy/analogs/v1/signals.parquet`

**Schema (one row per `(date, country)` decision):**

| Column | Type | Description |
|---|---|---|
| `date` | DATE | Decision date *t* (month-end) |
| `country` | VARCHAR | One of the 34 T2 countries |
| `score` | DOUBLE | Similarity-weighted median of analog forward 1m returns (the expected-return estimate, in decimal units, e.g. 0.023 = +2.3%) |
| `rank` | INTEGER | 1 = highest expected return, 34 = lowest, within (date) group |
| `similarity_mean` | DOUBLE | Mean cosine similarity of the top-k analog set — a confidence proxy |
| `analog_dispersion` | DOUBLE | Interquartile range of the analog forward-return set for this country at this date |
| `n_features_used` | INTEGER | Number of PIT-safe variables present in `worldstate_t` (varies over time by design) |
| `n_analogs` | INTEGER | k actually used (defaults to 10, may degrade early) |
| `model_version` | VARCHAR | e.g. `"v1-mvp-2026-04"` |

### 4.2 Supporting files

**Analog audit trail:** `Data/strategy/analogs/v1/analog_matches.parquet`
For each decision date, the top-k analog dates with their similarity scores. One row per `(date, analog_date)`, columns: `date`, `analog_date`, `cosine_similarity`, `softmax_weight`, `rank_in_topk`. This is what face-validity checks read.

**Backtest results:** `Data/strategy/analogs/v1/backtest.parquet`
Monthly realized PnL of the long-short quintile portfolio derived from the rank column, one row per month, columns: `date`, `ls_return_gross`, `ls_return_net`, `turnover`, `long_return`, `short_return`, `n_names_long`, `n_names_short`, plus the 60-month factor-momentum benchmark's return for the same month.

**Baselines:** `Data/strategy/analogs/v1/baselines.parquet`
Benchmark returns: equal-weight, 60-month factor momentum, naive current-snapshot factor rank (no analogs). Same schema as backtest.

**PIT audit:** `Data/strategy/analogs/v1/pit_audit.csv`
One row per variable in `feature_panel`, columns: `variable`, `source`, `first_available_date`, `vintage_safe` (bool), `notes`. Variables flagged `vintage_safe = false` are excluded from state-vector construction in v1.

### 4.3 Diagnostics memo

**Path:** `docs/strategy/analogs/v1/go_no_go.md`

A written memo (1-2 pages) that reports:
- Cumulative return and IR of the analog strategy vs all three baselines, 2008-01 through the backtest end.
- Subperiod table: pre-GFC (2008 only, partial), GFC (2008-2010), post-GFC (2011-2019), COVID (2020-2022), recent (2023-2026).
- Ten hand-picked decision dates with the strategy's top-3 analogs listed and a one-line economic plausibility read per match.
- Go / No-go recommendation for Phase 2.

---

## 5. THE 34 TARGET COUNTRIES

The v1 universe is the full T2 Master country list, unchanged. No investability filters in v1. Russia, Egypt, and similar special cases are kept in the universe throughout history — the backtest will report whether their inclusion distorts results, and an investability overlay is a Phase 3 concern. Canonical country names come from `country_reference` (ISO3 ↔ T2 name mapping).

---

## 6. STATE REPRESENTATION SPECIFICATION

### 6.1 World-state vector `worldstate_t`

At decision date *t* (month-end):

1. Query `feature_panel` for all `(date, country, variable, value)` rows where `date <= t` AND `variable LIKE '%_CS'` (cross-sectional z-scores only, for within-date comparability).
2. Apply the **time-varying feature set** rule: include variable *v* only if it has ≥ 60 monthly non-null observations strictly before *t*. This expands the usable feature set as time passes — 2008 starts with the ~70-80 variables that have 5+ years of history; by 2020 roughly ~150-180 are eligible; by 2026 the full PIT-safe ~200.
3. For each eligible variable *v*, extract the 34-country cross-section at date *t*. If a country is missing at *t* for variable *v*, fill with 0 (since inputs are cross-sectional z-scores, 0 means "neutral, at the cross-sectional mean"). Record which cells were filled in a companion sparsity matrix.
4. Concatenate the 34-country cross-sections into a single flat vector of length `n_features_t × 34`.
5. Standardize: re-scale to zero mean, unit variance using statistics fit on the flat vectors of all dates strictly before *t*.
6. Reduce dimensionality with PCA fit on `{worldstate_{t′} : t′ < t}`. Retain enough components to explain ≥ 80% of variance (cap at 30 components; expect ~15-25 in practice).
7. Output: `worldstate_t ∈ ℝ^d` where `d` is the month's retained PCA dimension count.

**Default parameters:**

| Parameter | Default | Range to sweep later |
|---|---|---|
| `min_feature_history_months` | 60 | 36, 48, 60, 84 |
| `pca_variance_target` | 0.80 | 0.70, 0.80, 0.90 |
| `pca_max_components` | 30 | 20, 30, 50 |
| `feature_prefix` | `_CS` | `_CS`, `_TS`, both |

### 6.2 No graph features in v1

Bilateral edges are deliberately excluded from `worldstate_t` in v1 — the MVP tests whether the pure factor-panel analog signal has any predictive power before adding complexity. Phase 5 introduces graph-derived features (trade-weighted neighbour factor means, banking concentration, network centrality) as an additive layer.

### 6.3 Variables explicitly excluded from v1

Automatic exclusion rules applied during PIT audit:

- **Forecast variables** (`IMF_WEO_*`, `BBG_ECFC_*`, any variable where the value at date *t* can be revised by data vintage after *t*): excluded unless the audit confirms a point-in-time archive exists.
- **Annual-only variables** with long reporting lag (e.g. UNDP HDI, ND-GAIN): allowed only if lagged by a full year (use the previous year's value as the known-at-*t* observation).
- **Variables with > 40% missingness** over their stated coverage window: excluded.
- Anything flagged `vintage_safe = false` in `pit_audit.csv`.

---

## 7. BACKTEST PROTOCOL (NON-NEGOTIABLE)

This is the operating rule. Any code path that violates it is a bug.

At every decision date *t*:

1. **Analog library:** all `worldstate_{t′}` for `t′ < t − min_lag`. Default `min_lag = 12 months`.
2. **All transforms fit on `< t` data only.** Scaler means/stds, PCA components, any regime clustering — re-fit at each *t*. Caching allowed; cache key is *t*.
3. **Similarity search:** cosine similarity between `worldstate_t` and every `worldstate_{t′}` in the library. Retain top-k (default `k = 10`).
4. **Aggregation:** for each country *c*, collect the set `{r_{t′+1}(c) : t′ ∈ top_k(t)}` where `r_{t′+1}(c)` is country *c*'s MSCI USD TR over the month following the analog date. Compute `score_c = similarity-weighted median` of this set (softmax temperature `τ = 1.0` default).
5. **Rank** countries by `score_c` descending; 1 = highest expected return.
6. **Long-short portfolio (for evaluation only):** long the top 7 (≈ quintile), short the bottom 7, equal-weighted within each bucket, held through month *t+1*. Turnover and returns logged.
7. **Realised return:** `r_{t+1}` is observed **after** the model commits. It enters the backtest as a realised P&L, never as a fitting input.

### 7.1 Worked timeline

| Decision *t* | Library range | k | Action |
|---|---|---|---|
| 2008-01-31 | 2000-01 → 2006-12 (84 dates) | 10 | Fit PCA on 84 points, query top-10, score 34 countries, commit positions, earn `r(2008-02)` |
| 2008-02-29 | 2000-01 → 2007-01 (85 dates) | 10 | Refit PCA, requery, recommit, earn `r(2008-03)` |
| … | library grows one month per step | | |
| 2026-03-31 | 2000-01 → 2025-03 (303 dates) | 10 | Refit, query, commit, observe live going forward |

### 7.2 Burn-in choice

Backtest start: **2008-01-31**. Library at first decision: 84 candidates. Rationale: top-10 out of 84 is a ~12% fraction, not catastrophically thin, and starting at 2008 captures the GFC as an observation rather than burn-in. Sensitivity alternatives (2005 / 2010 start) are Phase 2 sweep items.

---

## 8. IMPLEMENTATION REQUIREMENTS

### 8.1 File layout

```
ASADO/
├── scripts/
│   └── strategy/
│       └── analogs/
│           ├── __init__.py
│           ├── config.py              # all defaults, paths
│           ├── pit_audit.py           # Phase 0 — variable audit
│           ├── build_returns.py       # Phase 0 — cache MSCI country returns into DuckDB
│           ├── baselines.py           # Phase 0 — benchmark backtests (EW, 60m mom, naive rank)
│           ├── build_worldstate.py    # Phase 1 — compute worldstate_t for all dates
│           ├── analog_search.py       # Phase 1 — top-k search, softmax weights
│           ├── aggregate.py           # Phase 1 — similarity-weighted median scoring
│           ├── backtest.py            # Phase 1 — walk-forward harness
│           ├── report.py              # Phase 1 — plots + summary tables
│           └── run_v1.py              # orchestrator — runs entire v1 pipeline end-to-end
├── Data/
│   └── strategy/
│       └── analogs/
│           └── v1/
│               ├── signals.parquet
│               ├── analog_matches.parquet
│               ├── backtest.parquet
│               ├── baselines.parquet
│               ├── pit_audit.csv
│               └── worldstates.parquet  # cached PCA-reduced vectors
└── docs/
    └── strategy/
        └── analogs/
            └── v1/
                └── go_no_go.md
```

### 8.2 Entry point

```bash
cd ASADO
source venv/bin/activate
python scripts/strategy/analogs/run_v1.py           # full pipeline, end to end
python scripts/strategy/analogs/run_v1.py --stage 0 # PIT audit + returns cache only
python scripts/strategy/analogs/run_v1.py --stage 1 # worldstates + backtest + report
python scripts/strategy/analogs/run_v1.py --dry-run # preview, no writes
```

Re-runs are idempotent: each stage reads from DuckDB, writes to Parquet, replaces prior output. Backtest re-runs cache `worldstates.parquet` keyed on decision date.

### 8.3 Configuration

All parameters live in `config.py`:

```python
BACKTEST_START = "2008-01-31"
MIN_LAG_MONTHS = 12
K_ANALOGS = 10
SOFTMAX_TAU = 1.0
MIN_FEATURE_HISTORY_MONTHS = 60
PCA_VARIANCE_TARGET = 0.80
PCA_MAX_COMPONENTS = 30
FEATURE_PREFIX = "_CS"
LS_BUCKET_SIZE = 7                   # top / bottom N for evaluation portfolio
FORWARD_HORIZON_MONTHS = 1
```

No parameter tuning in v1 — these defaults are fixed for the MVP. Phase 2 is where the sweep happens.

### 8.4 Logging

Every run writes to `Data/strategy/analogs/v1/logs/run_YYYYMMDD_HHMMSS.log` with per-stage timing, row counts, and any PIT-violation warnings. Non-fatal warnings are collected and surfaced in the go/no-go memo.

### 8.5 Reproducibility

Deterministic: fix `numpy` and `sklearn` random seeds to 42. The PCA fit at each *t* is deterministic given seed + data. A full run should produce byte-identical `signals.parquet` across machines with the same ASADO database.

---

## 9. QUALITY CHECKS (must pass before go/no-go memo)

The memo cannot claim a result without these checks clean:

1. **No forward peeking:** automated test — for each decision date *t*, confirm that the PCA model, scaler stats, and any cached statistic were fit on data strictly earlier than *t*. Red test if any violation.
2. **Library monotonicity:** analog library size at *t* is strictly non-decreasing in *t*.
3. **Min-lag respected:** no analog date in `top_k(t)` has `date >= t − 12m`.
4. **Return series sanity:** the 60-month factor-momentum benchmark in `baselines.parquet` matches your historical production figure for ≥ 95% of months in an overlap period. If it doesn't, the MSCI-TR input is wrong and everything else is garbage.
5. **Cross-section completeness:** every decision date has exactly 34 ranks.
6. **PIT audit coverage:** every variable used in `worldstate_t` appears in `pit_audit.csv` with `vintage_safe = true`.

---

## 10. SUCCESS CRITERIA

v1 is considered a **positive read** (proceed to Phase 2) if ALL of the following hold on the 2008-01 through current walk-forward:

1. **Annualized net return ≥ 6.5%** (the 60-month factor-momentum baseline), net of Almgren-Chriss transaction costs.
2. **Information ratio ≥ 0.5 net** relative to equal-weight, AND IR of the analog strategy ≥ IR of the 60-month momentum baseline (so it wins head-to-head).
3. **At least 3 of 5 subperiods** (pre-GFC partial / GFC / post-GFC / COVID / recent) produce non-catastrophic returns (no subperiod worse than −15% cumulative).
4. **Analog face-validity:** of 10 hand-picked decision dates reviewed manually, ≥ 7 have at least one economically defensible top-3 analog.

v1 is a **negative read** (stop or pivot) if:

- Net annualized return < 2%, OR
- IR worse than equal-weight, OR
- Face-validity check ≤ 3/10 (suggests the similarity metric is not capturing anything meaningful).

**In-between results (positive but not dominant) trigger Phase 2 with specific hypotheses** — the go/no-go memo names which of {similarity metric, k, min_lag, PCA dimensionality, regime conditioning} is most likely the lever, and Phase 2 targets that lever first.

---

## 11. WHAT THIS PROJECT DOES NOT DO

- **No graph features.** Bilateral trade / banking / portfolio edges are Phase 5.
- **No regime conditioning.** All analog matches are in a single global space. Phase 3.
- **No similarity-metric sweep.** Cosine only. Phase 2.
- **No multi-horizon prediction.** 1-month forward only. Phase 7 extension.
- **No portfolio optimization.** Output is a ranked signal file; downstream layer handles weights, constraints, risk targeting.
- **No order routing.** No IBKR, no live trading, no paper portfolio integration. Signal file only.
- **No Mythos dependency.** Entire v1 runs on current infrastructure with current models.
- **No native-language news, no central bank PDFs, no satellite data.** All Mythos Ideas document extensions are post-v1.
- **No new data collection.** v1 uses only data already in `asado.duckdb`.

---

## 12. OPEN QUESTIONS FOR THE IMPLEMENTER TO CONFIRM DURING PHASE 0

These are known unknowns that Phase 0 must resolve before Phase 1 starts:

1. **MSCI country TR USD source.** Confirm exact T2 workbook sheet / column, or substitute. Current assumption: `T2 Master.xlsx` contains a monthly return sheet; verify.
2. **Almgren-Chriss cost function path.** Where does the existing transaction-cost code live? Import or reimplement.
3. **60-month factor momentum benchmark formula.** Exact construction — equal-weight top-quintile minus bottom-quintile over which factor set? Document in `baselines.py`.
4. **PIT status of `_CS` variables.** Most `_CS` columns should be PIT-safe since they're computed from `feature_panel` at each historical date, but confirm: does `build_normalized_panel.py` use any future data in its z-score denominators?
5. **GDELT partial-month labels.** `gdelt_panel` includes partial current-month labels per the README. Exclude incomplete-month rows in v1's worldstate construction.

---

## 13. AFTER v1 — PREVIEW OF PHASES 2–7 (for context, not scope)

This PRD is v1 only, but the code should be structured so that these follow-ups are additive, not rewrites:

- **Phase 2** — similarity / k / min_lag / PCA dim sweep, deflated Sharpe ratio.
- **Phase 3** — regime-conditional analog pools, augmented distance metric.
- **Phase 4** — full rigorous walk-forward with subperiod breakdown, bootstrap CIs, benchmark orthogonality test.
- **Phase 5** — graph-aware `worldstate_t` via bilateral edge statistics and/or GNN-pooled graph embedding.
- **Phase 6** — analog face-validity automation, attribution (which features drive matches?), drawdown forensics.
- **Phase 7** — ensemble with T2 factor momentum, multi-horizon stacking, Mythos-assisted extensions.

The v1 code structure (`build_worldstate.py`, `analog_search.py`, `aggregate.py`, `backtest.py`) anticipates these: each phase adds a new module or replaces the contents of one module, with the orchestrator staying stable.

---

*End of PRD v1.0.*
