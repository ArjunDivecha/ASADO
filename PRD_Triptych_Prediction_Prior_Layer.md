# PRD - Triptych Prediction Prior Layer
## Incorporating Triptych Into ASADO's Main Prediction Flow

| Field | Value |
|-------|-------|
| **Project** | ASADO country equity research platform |
| **System name** | Triptych Prediction Prior Layer |
| **Short name** | `triptych_prior_v1` |
| **Version** | 1.0 |
| **Date** | 2026-06-15 |
| **Owner** | Arjun Divecha |
| **Executor** | Codex / frontier model agent sessions |
| **Status** | Draft for implementation |
| **Primary dependency** | Triptych tool at `https://triptych-one.vercel.app` plus ASADO T2 return/factor surfaces |
| **Primary output** | Triptych review queue, Triptych prior table, daily brief section, and MCP/tool links |

---

## 0. One-Paragraph Summary

Triptych should enter ASADO as a **factor-diagnostic and prediction-prior layer**, not as a database, a replacement frontend, or a final trading signal. Its job is to answer a question ASADO repeatedly faces before formal validation: for a given country/factor pair, has this factor historically mattered for this market, in this direction, at this horizon, and is today's reading in a historically meaningful bucket? The India / REER example shows the value: when India's REER is very cheap versus its own history, Triptych shows Indian equities historically did very well over the next 12 months relative to the all-country average. ASADO should harvest that as a structured prior, expose it in the daily brief, and then use the existing harness, event-study engine, ledgers, and forward calibration to decide whether the prior improves actual predictions.

---

## 1. Product Thesis

ASADO already has the return spine and the skeptic:

1. `country_returns_monthly` and daily country returns.
2. `factor_returns` and `factor_returns_daily`.
3. `country_factor_attribution`.
4. Dislocation detectors and the daily brief.
5. The pre-registered harness, event-study engine, thesis ledger, and calibration report.

Triptych adds a missing middle layer:

> It makes country-specific conditional factor relationships visible before ASADO spends a formal trial or opens a thesis.

This is especially valuable for relationships that are real but not naturally expressed as a cross-sectional all-country signal. Cheap India REER predicting strong India-relative 12M returns is the motivating example: a single-country conditional pattern that can guide a thesis even if it is not yet a global factor.

---

## 2. Goals

### G1. Make Triptych A First-Class Review Tool

Every relevant ASADO candidate should have an "Open in Triptych" URL with consistent defaults:

- point-in-time thresholds
- expanding z-score versus own history
- relative return versus all-country average
- 12M horizon default for monthly macro/fundamental factors
- 10Y and all-history views available

### G2. Convert Triptych Visuals Into Structured Priors

Port the Triptych analytics kernel into ASADO so the system can compute:

- current bucket
- current signal z-score
- bucket average forward return by horizon
- hit rate
- observation count
- top-minus-bottom spread
- Spearman IC and overlap-adjusted t-stat
- confidence score
- Triptych URL

### G3. Put Triptych In The Daily Reasoning Flow

The daily dislocation brief should contain a compact Triptych review queue:

- high-value country/factor pairs
- why each pair was selected
- expected direction and horizon
- prior strength and caveats
- direct Triptych link

### G4. Test Whether Triptych Improves Predictions

Before adding Triptych features to the ridge combiner, run a formal ablation:

- existing ASADO candidate score alone
- plus Triptych prior
- plus Triptych prior and confidence/horizon features

Promotion requires out-of-sample improvement after costs, trial penalties, and subperiod checks.

### G5. Preserve The Human Tool

Triptych remains useful because it is visual. ASADO should launch/feed it; ASADO should not swallow it into a hidden table and lose the analyst-facing behavior.

---

## 3. Non-Goals

- Do not treat Triptych as a new data source.
- Do not create persistent tables directly in `Data/asado.duckdb`.
- Do not replace ASADO's Streamlit app, Perspective Lab, MCP tools, or query assistant.
- Do not bypass `evaluate_signal`, `event_study.py`, the hypothesis ledger, or thesis calibration.
- Do not use forward-return variables (`1MRet`, `3MRet`, `6MRet`, `9MRet`, `12MRet`, daily return analogs) as signals.
- Do not let full-sample Triptych views count as predictive evidence. They are descriptive only.
- Do not add Triptych features to `build_combiner.py` until the ablation passes.
- Do not build an order router or live trading recommendation engine.

---

## 4. Current State

### 4.1 Triptych Tool

Triptych is a local/cloud visual factor-timing workbench. It consumes the T2 workbook shape: factor sheets x countries x dates. Its Deep-Dive view exposes:

- factor signal through time
- cumulative country return, absolute or relative
- forward-return bucket analysis
- point-in-time versus full-sample bucket thresholds
- bucket x horizon matrix
- cross-market current-bucket snapshot
- exports and shareable URLs

Verified representative view:

```text
https://triptych-one.vercel.app/triptych.html?tab=triptych&tf=REER&tc=India&tn=history_z&tm=relative&th=12&tr=10y&td=pit&tb=10
```

The India / REER check showed a positive 12M India-relative prior when REER is very cheap. All-history PIT evidence was directionally strong; latest 10Y PIT evidence agreed but had a small current-bucket sample.

### 4.2 ASADO Main Flow

The nightly loop currently runs:

1. source collectors/loaders
2. graph, similarity, lead-lag, and combiner feature builders
3. `build_dislocations.py`
4. `build_evidence_packs.py`
5. ledger fold
6. calibration report

The right initial insertion point is **after `build_dislocations.py` and before evidence packs / Layer-2 reading**, because Triptych should help triage and interpret candidate ideas. The right later insertion point is **before `build_combiner.py` only after the ablation proves predictive value**.

### 4.3 Storage Boundary

`Data/asado.duckdb` is the rebuildable warehouse. `Data/loop/asado_loop.duckdb` is the alpha/research system. Triptych additions belong in the loop DB and `Data/loop/` artifacts.

---

## 5. User Stories

### U1. Daily Brief Reader

As Arjun, I want the daily brief to show which dislocations have useful Triptych context, so I can quickly see whether history supports the implied country/factor thesis.

### U2. Hypothesis Author

As an agent writing a hypothesis, I want a Triptych prior and URL in the evidence section, so the mechanism and horizon are grounded before I spend a harness trial.

### U3. Query Assistant User

As a user asking "why India?" or "what supports Brazil?", I want ASADO to return a Triptych link for the relevant factor/country pair, plus the prior stats.

### U4. Combiner Researcher

As a researcher, I want to test whether Triptych priors improve country ranking out-of-sample before they become production features.

---

## 6. System Architecture

```text
Layer A - Tool Launcher
  scripts/triptych_tool_link.py
  MCP: triptych_link(country, factor, horizon, ...)

Layer B - Review Queue
  scripts/loop/build_triptych_review_queue.py
  inputs: dislocation_daily, combiner_scores_daily, country_factor_attribution,
          factor_returns_daily, variable_registry_full
  outputs: Data/loop/triptych_review_queue.parquet
           loop DB table triptych_review_queue
           daily brief section

Layer C - Analytics Kernel
  scripts/loop/triptych_kernel.py
  pure functions mirroring Triptych PIT bucket logic

Layer D - Prior Builder
  scripts/loop/build_triptych_priors.py
  inputs: candidate queue + T2 monthly factor/return surfaces
  outputs: Data/loop/triptych_priors.parquet
           loop DB table triptych_priors

Layer E - Validation / Promotion
  scripts/loop/triptych_ablation.py
  tests Triptych features against returns and existing ASADO scores
  only if PASS: selected features become combiner candidates
```

---

## 7. Data Contracts

### 7.1 `triptych_review_queue`

Loop-owned table. One row per candidate pair per run.

| Column | Type | Notes |
|---|---|---|
| `date` | DATE | run date |
| `country` | VARCHAR | T2 country name |
| `factor` | VARCHAR | Triptych/ASADO factor name |
| `source_reason` | VARCHAR | `dislocation`, `combiner`, `attribution`, `factor_return`, `manual` |
| `source_id` | VARCHAR | dislocation id, factor name, or other provenance |
| `priority` | DOUBLE | sort key |
| `default_horizon` | INTEGER | usually 12 for monthly |
| `triptych_url` | VARCHAR | shareable URL |
| `notes` | VARCHAR | short machine-readable context |

### 7.2 `triptych_priors`

Loop-owned table. One row per candidate pair per horizon per as-of date.

| Column | Type | Notes |
|---|---|---|
| `date` | DATE | as-of date |
| `country` | VARCHAR | T2 country |
| `factor` | VARCHAR | signal variable |
| `normalization` | VARCHAR | `history_z`, `raw`, `cross_var_pct` |
| `return_mode` | VARCHAR | `relative` or `absolute` |
| `threshold_mode` | VARCHAR | `pit` or `full`; predictive rows must be `pit` |
| `bucket_count` | INTEGER | 10, 5, or 3 |
| `horizon_months` | INTEGER | 1, 3, 6, 12, 24, 36 |
| `signal_value` | DOUBLE | raw or normalized current value |
| `current_bucket` | INTEGER | 1 = lowest, k = highest |
| `bucket_obs` | INTEGER | observations in current bucket |
| `bucket_avg_fwd_return` | DOUBLE | conditional forward return |
| `bucket_hit_rate` | DOUBLE | share of positive forward returns |
| `bucket_t_stat` | DOUBLE | overlap-adjusted |
| `ic_spearman` | DOUBLE | signal vs forward return |
| `ic_t_stat` | DOUBLE | overlap-adjusted |
| `top_minus_bottom_spread` | DOUBLE | high bucket minus low bucket |
| `implied_direction` | VARCHAR | `long`, `short`, `neutral`, `insufficient` |
| `confidence_score` | DOUBLE | 0-1 prior strength, not evidence |
| `confidence_notes` | VARCHAR | sample/horizon caveats |
| `triptych_url` | VARCHAR | exact tool view |

### 7.3 Confidence Score

Initial deterministic score:

```text
directional_alignment =
  sign(bucket_avg_fwd_return) agrees with IC/spread direction

sample_score =
  min(1.0, bucket_obs / 20)

ic_score =
  min(1.0, abs(ic_t_stat) / 2.5)

hit_score =
  abs(bucket_hit_rate - 0.5) * 2

horizon_score =
  share of neighboring horizons with same implied direction

confidence_score =
  0 if threshold_mode != "pit"
  else average(sample_score, ic_score, hit_score, horizon_score)
       * directional_alignment_flag
```

The score is a triage prior. It is not a verdict.

---

## 8. Candidate Selection

Start with at most 25 daily candidates to keep the brief useful.

### 8.1 Dislocation Candidates

From latest `dislocation_daily`, include active rows where:

- status in `new`, `intensifying`, `persisting`
- detector maps to a T2 factor name or factor family
- severity is high enough to matter

Examples:

- D1 terms-of-trade rows -> `Oil`, `Copper`, `Gold`, commodity factors where available.
- D4/D10 cross-asset rows -> `Currency`, `Currency Vol`, `10Yr Bond`, `REER`.
- D7 factor crowding rows -> the crowded factor.
- D5 GDELT attention rows -> only if a known factor is attached; otherwise Triptych link is omitted.

### 8.2 Combiner Candidates

From latest `combiner_scores_daily`, include:

- top 5 countries
- bottom 5 countries
- countries whose rank changed materially

Map each country to the strongest explanatory factors using latest `country_factor_attribution`.

### 8.3 Attribution Candidates

From latest `country_factor_attribution`, include large absolute contributions:

- top positive country/factor rows
- top negative country/factor rows

### 8.4 Manual / Query Candidates

Allow direct calls:

```bash
python scripts/triptych_tool_link.py --country India --factor REER --horizon 12
```

MCP should expose the same as `triptych_link`.

---

## 9. Implementation Plan

### Phase 0 - Move Exploration Artifact Into Main

Files:

- add `scripts/triptych_tool_link.py`
- add this PRD

Acceptance:

- CLI prints the expected Triptych URL.
- invalid horizon/threshold inputs fail clearly.

Validation:

```bash
python -m py_compile scripts/triptych_tool_link.py
python scripts/triptych_tool_link.py --factor REER --country India --markdown
```

### Phase 1 - Brief-Level Tool Integration

Files:

- add `scripts/loop/build_triptych_review_queue.py`
- modify `scripts/loop/loop_daily_job.py`
- modify `scripts/loop/build_dislocations.py`
- add tests under `tests/loop/test_triptych_review_queue.py`

Behavior:

- Build a queue from latest dislocations, combiner ranks, and attribution rows.
- Write `Data/loop/triptych_review_queue.parquet`.
- Rebuild `triptych_review_queue` table in loop DB.
- Add a "Triptych Review Queue" section to the daily brief.
- Add the step after `build_dislocations` and before `build_evidence_packs`.

Acceptance:

- `python scripts/loop/build_triptych_review_queue.py --check` reports latest queue.
- `python scripts/loop/loop_daily_job.py --only build_triptych_review_queue` succeeds.
- Daily brief includes valid Triptych links.
- No data is written to `Data/asado.duckdb`.

### Phase 2 - Analytics Kernel

Files:

- add `scripts/loop/triptych_kernel.py`
- add `tests/loop/test_triptych_kernel.py`

Pure functions:

- expanding z-score
- cross-sectional z-score
- forward returns from return index levels
- point-in-time thresholds
- bucket assignment
- bucket stats
- Spearman IC
- horizon matrix

Acceptance:

- Synthetic tests prove PIT thresholds never use future observations.
- Forward-return variables are refused as signals.
- India / REER fixture approximately reproduces live Triptych stats for all-history PIT.

### Phase 3 - Prior Builder

Files:

- add `scripts/loop/build_triptych_priors.py`
- update `scripts/loop/loop_daily_job.py`
- add tests under `tests/loop/test_triptych_priors.py`

Behavior:

- Read latest queue.
- Pull factor/return data from ASADO T2 monthly surfaces.
- Compute priors for 1/3/6/12/24/36M horizons.
- Write `Data/loop/triptych_priors.parquet`.
- Rebuild loop DB table `triptych_priors`.
- Add prior stats to the brief queue section.

Acceptance:

- `triptych_priors` has rows for India / REER.
- Rows are all `threshold_mode='pit'` for predictive use.
- confidence score shrinks small samples.
- no forward-return variables appear as factors.

### Phase 4 - MCP And Query Assistant Surface

Files:

- modify `scripts/asado_mcp_server.py`
- optionally modify `scripts/query_assistant.py`

Tools:

```text
triptych_link(country, factor, horizon=12, range="10y", threshold_mode="pit")
triptych_prior_snapshot(country, factor, date="latest")
triptych_review_queue(date="latest")
```

Acceptance:

- MCP returns URL and latest prior stats.
- Query assistant can include Triptych links for country/factor questions.
- No tool claims Triptych output is final evidence.

### Phase 5 - Ablation

Files:

- add `scripts/loop/triptych_ablation.py`
- add dated report under `docs/` or `Data/loop/reports/`

Tests:

- baseline dislocation/combiner score
- baseline + Triptych prior
- baseline + prior confidence/horizon features

Metrics:

- rank IC
- top/bottom country returns
- long-short with costs where applicable
- subperiod stability
- calibration of opened theses

Acceptance:

- Promote only if the Triptych features improve out-of-sample metrics.
- If not, keep Triptych as a review/prior tool only.

### Phase 6 - Optional Combiner Promotion

Only after Phase 5 passes:

- add selected Triptych features to `build_combiner.py`
- pre-register the combiner variant as a fresh family/trial
- report feature weights separately from existing graph/market-derived features

---

## 10. Validation Rules

### Point-In-Time

- `pit` bucket thresholds at date `t` use only observations strictly before or at `t`, depending on the matching Triptych semantics.
- The current bucket can use history through today; historical bucketed forward returns must not use future thresholds.
- `full` threshold rows may be computed for display but cannot be used for confidence or promotion.

### Return Alignment

- Monthly forward return at `t` uses return index level at `t` and `t+h`, with tolerance matching Triptych where necessary.
- Relative return subtracts equal-weight all-country forward return at the same date.
- No forward-return sheet can be used as a signal.

### Evidence Hierarchy

1. Triptych visual: useful clue.
2. `triptych_priors`: structured prior.
3. event study or harness: evidence.
4. ledger/calibration: live forward truth.

---

## 11. Example - India / REER

Current Triptych interpretation:

```text
Country: India
Factor: REER
State: REER very cheap versus own history
Implied direction: long India relative equity
Primary horizon: 12M
Secondary horizon: 24M
All-history PIT evidence: D1 around +25.5% 12M relative forward return,
  100% hit rate, 20 observations, IC around -0.41, D10-D1 around -27.3%.
10Y PIT evidence: D1 around +23.6% 12M relative forward return,
  100% hit rate, 2 observations.
Confidence: positive but shrink for latest-window sample size.
```

Expected `triptych_priors` row:

```text
date=latest
country=India
factor=REER
horizon_months=12
threshold_mode=pit
current_bucket=1
implied_direction=long
confidence_score>0
confidence_notes="all-history strong; latest 10Y current-bucket sample small"
```

Layer-2 use:

> "India's cheap REER has historically been a strong 12M relative-return setup. Check whether today's other ASADO signals confirm or contradict it, and only open a thesis if catalyst/risk framing is adequate."

---

## 12. Risks And Mitigations

| Risk | Mitigation |
|---|---|
| Triptych becomes treated as proof | Label output as prior; harness/event-study remains evidence |
| Small bucket samples overstate signal | sample-size shrinkage and visible `bucket_obs` |
| Full-sample lookahead sneaks into prediction | predictive tables require `threshold_mode='pit'` |
| Country-specific insight fails cross-sectional harness | support event-study / conditional-return validation path |
| Too many links clutter the brief | cap queue at 25 and rank by priority |
| Factor name drift between Triptych and ASADO | explicit mapping layer with validation |
| Main DB polluted with research artifacts | write only to loop DB and `Data/loop/` |
| Combiner overfits to attractive priors | ablation and fresh registration before promotion |

---

## 13. Test Plan

### Unit Tests

- URL builder encodes spaces and punctuation correctly.
- PIT bucket assignment excludes future thresholds.
- expanding z-score matches known hand examples.
- forward-return calculation matches known return-index examples.
- forward-return variables are rejected as signals.
- confidence score shrinks low observation counts.

### Integration Tests

- Build review queue from a small synthetic dislocation table.
- Build priors for a fixed India / REER fixture.
- Render daily brief section without malformed Markdown.
- MCP tools return JSON-serializable payloads.

### End-To-End Smoke

```bash
python scripts/triptych_tool_link.py --factor REER --country India --markdown
python scripts/loop/build_triptych_review_queue.py --check
python scripts/loop/build_triptych_priors.py --country India --factor REER --check
python -m pytest tests/loop/test_triptych_kernel.py tests/loop/test_triptych_review_queue.py
```

Success means the tool can be used in the main reasoning flow. It does not mean the prior has been promoted into the prediction model.

---

## 14. Open Questions

1. Should `triptych_priors` compute all T2 factor/country pairs nightly, or only the review queue?
   - Recommendation: queue-only for v1; all-pairs later if performance is fine.
2. Should relative return always be the default?
   - Recommendation: yes for country selection; absolute can be an alternate view.
3. Should country-specific Triptych signals be validated through harness or event-study?
   - Recommendation: broad all-country factors use harness; one-country conditional setups use event-study/conditional-return validation.
4. Should Triptych links point to the cloud app or local app?
   - Recommendation: cloud app for shareability, local app fallback if cloud data vintage lags.
5. Should Triptych prior confidence enter thesis probability directly?
   - Recommendation: no in v1. It informs the narrative and candidate queue; thesis probabilities remain explicit human/agent judgments until calibrated.

---

## 15. Build Order Summary

```text
Phase 0  URL builder + PRD
Phase 1  Review queue + daily brief links
Phase 2  Triptych analytics kernel
Phase 3  triptych_priors table
Phase 4  MCP/query surfaces
Phase 5  ablation report
Phase 6  optional combiner promotion
```

The correct first shipped version is small: a daily brief section with good links and clear priors. That gives ASADO the benefit of Triptych immediately while keeping the prediction machinery honest.
