# PRD: Returns-First Source Of Truth Layer
## ASADO MCP And Query Assistant Upgrade

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Date** | 2026-05-12 |
| **Author** | Codex, from Arjun's product direction |
| **Status** | Draft for implementation |
| **Depends on** | Existing DuckDB monthly/daily panels, optimizer return ingest, ASADO MCP server |
| **Companion to** | `PRD_ASADO_Natural_Language_Query_Layer.md`, `docs/DAILY_EXTENSION_STATUS.md`, `DATA_DICTIONARY.md` |
| **Estimated effort** | 3-5 implementation days for v1 |

---

## 1. Purpose

Make country and factor returns the dominant source of truth in ASADO's analytical answers.

ASADO now contains broad country state data: T2 factors, GDELT, Econ, Bloomberg, IMF, macrostructure, prediction markets, bilateral ownership, and Neo4j relationships. Those layers are useful because they help explain or anticipate outcomes. The outcome layer itself is returns.

The product requirement is:

> When a user asks the MCP or natural-language query assistant a country, factor, event, regime, signal, or performance question, the answer should usually route back to the relevant country-return and factor-return surfaces unless the user explicitly asks for non-return data only.

This PRD defines the returns-first access contract, MCP tools, schema metadata, planner rules, and validation suite needed to make that behavior reliable.

---

## 2. Current State

### 2.1 Live Verified Data Surfaces

Verified from `Data/asado.duckdb` on 2026-05-12:

| Surface | Rows | Coverage | Use |
|---------|-----:|----------|-----|
| `feature_panel` | 8,571,659 | 1,935 variables, 1975-12-01 to 2031-12-01 | Primary country-factor query surface |
| `unified_panel` | 7,791,805 | 1,651 variables, 1975-12-01 to 2031-12-01 | Raw warehouse |
| `t2_factors_daily` | 32,340,392 | 109 variables, 34 countries, 2000-01-01 to 2026-05-07 | Daily T2 country returns and factors |
| `gdelt_factors_daily` | 10,085,794 | 75 variables, 34 countries, 2015-06-24 to 2026-05-08 | Daily GDELT country return/signal layer |
| `factor_returns` | 277,116 | 1,678 factors, 3 sources, 2000-02-01 to 2026-04-01 | Monthly top-20% factor portfolio returns |
| `factor_returns_daily` | 1,293,492 | 178 factors, 2 sources, 2000-01-01 to 2026-05-07 | Daily optimizer factor returns |
| `factor_top20_membership` | 2,104,980 | 1,681 factors, 34 countries, 2000-02-01 to 2026-05-01 | Country membership in top-20% factor buckets |
| `country_factor_attribution` | 2,087,921 | 1,678 factors, 34 countries, 2000-02-01 to 2026-04-01 | Country-level attribution from factor bucket membership |

### 2.2 Existing Return Types

Country returns (one canonical set, 34 countries):

- Monthly T2 returns in `feature_panel` / `unified_panel` (source=`t2`): `1MRet`, `3MRet`, `6MRet`, `9MRet`, `12MRet`
- Daily T2 returns in `t2_factors_daily`: `1DRet`, `5DRet`, `20DRet`, `60DRet`, `120DRet`

The `1MRet` rows under source=`gdelt` in `feature_panel` and the `1DRet` rows in `gdelt_factors_daily` are **bit-exact duplicates** of the T2 country returns — copied into the GDELT panel as the dependent variable for the GDELT optimizer. They are aliases, not a second return measurement, and must not be treated as a separate country return source. Verified 2026-05-12: 135,014 / 135,014 daily rows identical to T2 1DRet; monthly Brazil 1MRet identical to 6 decimal places back to 2015.

Factor returns:

- Monthly optimizer returns in `factor_returns`
  - `econ_optimizer`
  - `t2_optimizer`
  - `gdelt_optimizer`
- Daily optimizer returns in `factor_returns_daily`
  - `t2_optimizer_daily`
  - `gdelt_optimizer_daily`
- Country-level top-20% factor contribution in `country_factor_attribution`

Graph enrichment:

- Neo4j `Factor` nodes carry daily performance stats sourced from `factor_returns_daily`
- `HAS_FACTOR_EXPOSURE` edges still reflect latest factor exposure, not return contribution

### 2.3 What Works Today

- The data exists in DuckDB.
- The schema cache exposes `factor_returns`, `factor_returns_daily`, `factor_top20_membership`, and `country_factor_attribution`.
- `ask_asado` correctly routes direct questions like:
  - "Which factors have had the best returns recently?" to `factor_returns`
  - "Which countries had the best returns last month?" to `feature_panel` with `1MRet`
- MCP tools can access returns through `run_duckdb_sql`.
- `event_window` returns T2 factors, GDELT factors, and daily factor returns around a dated event.
- `daily_factor_series` can return daily country return series.

### 2.4 What Does Not Work Yet

- Returns are available, but not treated as the primary answer spine.
- `get_schema_summary` lists returns, but does not elevate them as the core outcome layer.
- `daily_factor_series` does not expose `factor_returns_daily` as a first-class source.
- There are no deterministic MCP tools for:
  - country return leaders / laggards,
  - factor return leaders / laggards,
  - factor return time series,
  - country-factor attribution,
  - event return summaries.
- `ask_asado` can still route event/explanation questions to monthly `feature_panel` when a daily return/event-window answer would be more appropriate.
- The variable catalog does not connect a factor variable to its available optimizer-return series.
- There is no explicit test suite that asserts return-surface routing.

---

## 3. Product Principle

ASADO should distinguish between:

1. **Outcome surfaces**: country returns, factor returns, attribution, forward return windows.
2. **Explanatory surfaces**: factor levels, normalized signals, GDELT tone/risk, macro variables, graph relationships, prediction markets.

Most analytical answers should be structured as:

1. What happened in returns?
2. Which countries or factors led/lagged?
3. What explanatory signals, graph relationships, or events may help interpret it?
4. What caveats apply around data freshness, attribution, or causality?

This is not a request to collapse all data into one table. It is a request to make the return surfaces the default analytical anchor.

---

## 4. Goals

### G1. Make Returns First-Class In MCP

Expose deterministic MCP tools for common return questions so agents do not need to write ad hoc SQL for the most important workflows.

### G2. Make The Query Assistant Returns-Aware

Update planner prompts, schema cache, and guardrails so natural-language questions about performance, events, winners/losers, signals, analogs, beneficiaries, or "what happened" use return surfaces by default.

### G3. Preserve Optimizer Cycle Protection

Keep optimizer outputs out of `feature_panel` and `unified_panel`. Those views are input/explanatory surfaces. Optimizer returns and attribution remain separate output surfaces.

### G4. Connect Country Returns, Factor Returns, And Attribution

Support workflows that move from:

- country return leaderboards,
- to factor return leaderboards,
- to which countries were in the factor buckets,
- to country-factor contribution.

### G5. Improve Event And Regime Answers

For event questions, return the event-window evidence plus country/factor return impact, rather than only monthly factor snapshots.

### G6. Make Behavior Testable

Add smoke tests and planner assertions for the exact user-visible behavior.

---

## 5. Non-Goals

- No trading, order routing, or portfolio execution.
- No change to the upstream T2/GDELT/Econ optimizer math in this PRD.
- No attempt to union `factor_returns` or `factor_returns_daily` into `feature_panel` / `unified_panel`.
- No redefinition of ASADO countries or market sleeves.
- No replacement of DuckDB with Neo4j for time-series returns.
- No promise of causal explanation from return attribution alone.

---

## 6. Returns Access Contract

### 6.1 Canonical Return Surfaces

| Question Type | Preferred Surface |
|---------------|-------------------|
| Monthly country performance | `feature_panel` or `unified_panel` with `1MRet`, `3MRet`, `6MRet`, `9MRet`, `12MRet` (source=`t2`) |
| Daily country performance | `t2_factors_daily` with `1DRet`, `5DRet`, `20DRet`, `60DRet`, `120DRet` |
| Monthly factor portfolio performance | `factor_returns` |
| Daily factor portfolio performance | `factor_returns_daily` |
| Country membership in factor portfolios | `factor_top20_membership` |
| Country P&L contribution from factor portfolios | `country_factor_attribution` |
| Event-window factor behavior | `event_window` plus `factor_returns_daily` |
| Cross-sectional factor exposure | `feature_panel`, `normalized_panel`, or Neo4j `HAS_FACTOR_EXPOSURE` |

### 6.2 Source Semantics

Monthly factor return sources:

- `econ_optimizer`: factor returns from the Econ optimizer pipeline.
- `t2_optimizer`: factor returns from the T2 style optimizer pipeline.
- `gdelt_optimizer`: factor returns from the GDELT optimizer pipeline.

Daily factor return sources:

- `t2_optimizer_daily`: daily optimizer returns for T2 factor variants.
- `gdelt_optimizer_daily`: daily optimizer returns for GDELT factor variants.

Country return source semantics:

- T2 country returns are the **single** canonical country return source for the 34-country universe (monthly via `feature_panel` source=`t2`, daily via `t2_factors_daily`). There is no second country return measurement.
- The GDELT-labeled `1MRet` / `1DRet` rows are aliases of the T2 country returns (see §2.2) and exist only to support the GDELT optimizer pipeline.
- Econ currently contributes monthly factor returns through `econ_optimizer`; there is no daily Econ return surface in current state.

### 6.3 Cycle Guardrail

`factor_returns`, `factor_returns_daily`, `factor_top20_membership`, and `country_factor_attribution` must not be unioned into `feature_panel` or `unified_panel`.

Reason: `feature_panel` and `unified_panel` are explanatory/input surfaces used to construct optimizer outputs. Adding optimizer outputs back into them creates a modeling cycle and contaminates downstream factor selection.

Acceptance test:

```sql
SELECT COUNT(*)
FROM feature_panel
WHERE source IN ('econ_optimizer', 't2_optimizer', 'gdelt_optimizer',
                 't2_optimizer_daily', 'gdelt_optimizer_daily');
```

Expected: `0`.

---

## 7. MCP Requirements

### 7.1 New Tool: `country_returns`

Purpose: Return country return series or country return rankings.

Arguments:

| Argument | Type | Default | Notes |
|----------|------|---------|-------|
| `countries` | string | `"all"` | Comma-separated ASADO country names or `"all"` |
| `frequency` | enum | `"monthly"` | `"monthly"` or `"daily"` |
| `horizon` | string | `"1MRet"` monthly, `"1DRet"` daily | Monthly: `1MRet/3MRet/6MRet/9MRet/12MRet`; daily: `1DRet/5DRet/20DRet/60DRet/120DRet` |
| `start_date` | string/null | null | Optional inclusive start |
| `end_date` | string/null | null | Optional inclusive end |
| `latest_only` | boolean | true | If true, use latest available date on or before current date |
| `rank` | enum/null | null | `"best"`, `"worst"`, or null |
| `max_rows` | integer | 100 | Row cap |

Output:

- selected table,
- resolved date range,
- rows,
- caveats,
- freshness metadata.

Example questions:

- "Which countries had the best returns last month?"
- "Show Brazil's daily 1D returns since May 1."
- "Which EM countries had the worst 3MRet?"

### 7.2 New Tool: `factor_return_series`

Purpose: Return factor portfolio return time series.

Arguments:

| Argument | Type | Default | Notes |
|----------|------|---------|-------|
| `factors` | string | `"all"` | Comma-separated factor names or `"all"` |
| `frequency` | enum | `"monthly"` | `"monthly"` or `"daily"` |
| `source` | string | `"auto"` | Optimizer source; infer if possible |
| `start_date` | string/null | null | Optional inclusive start |
| `end_date` | string/null | null | Optional inclusive end |
| `metric` | enum | `"return"` | v1: return; v1.1: sharpe, vol, drawdown |
| `rank` | enum/null | null | `"best"`, `"worst"`, or null |
| `window` | string | `"latest"` | `"latest"`, `"1m"`, `"3m"`, `"12m"`, `"ytd"`, `"custom"` |
| `max_rows` | integer | 100 | Row cap |

Output:

- selected table,
- source,
- factor names,
- latest date or window,
- return rows or ranking,
- caveat that factor returns are top-20% portfolio returns, not raw factor levels.

Example questions:

- "Which factors have had the best returns recently?"
- "Show RSI14_CS daily optimizer returns."
- "Which GDELT factors worked best over the last year?"

### 7.3 New Tool: `country_factor_attribution`

Purpose: Explain which factor buckets contributed to a country's return or exposure in a month.

Arguments:

| Argument | Type | Default | Notes |
|----------|------|---------|-------|
| `country` | string | required | ASADO country name |
| `source` | string | `"auto"` | `econ_optimizer`, `t2_optimizer`, or `gdelt_optimizer` |
| `date` | string | `"latest"` | Latest or explicit month |
| `factors` | string | `"all"` | Optional filter |
| `rank` | enum | `"largest_abs"` | `"positive"`, `"negative"`, `"largest_abs"` |
| `max_rows` | integer | 50 | Row cap |

Output:

- factor,
- weight,
- factor return,
- contribution,
- source,
- date,
- caveat that this is top-20% bucket attribution, not a full country portfolio decomposition.

Example questions:

- "Why did Brazil benefit from the top GDELT factors last month?"
- "Which factor buckets contributed most to Turkey in the latest Econ optimizer?"

### 7.4 New Tool: `return_leaders`

Purpose: One deterministic tool for leaderboards.

Arguments:

| Argument | Type | Default | Notes |
|----------|------|---------|-------|
| `scope` | enum | required | `"country"` or `"factor"` |
| `frequency` | enum | `"monthly"` | `"monthly"` or `"daily"` |
| `source` | string | `"auto"` | Country or optimizer source |
| `horizon` | string/null | null | Country-return horizon |
| `window` | string | `"latest"` | Factor-return aggregation window |
| `date` | string | `"latest"` | Latest or explicit date |
| `direction` | enum | `"best"` | `"best"` or `"worst"` |
| `max_rows` | integer | 25 | Row cap |

This tool should call `country_returns` or `factor_return_series` internally.

### 7.5 Upgrade Existing Tool: `daily_factor_series`

Add supported sources:

- `factor_returns_daily`
- `t2_returns`
- `gdelt_returns`

Do not break existing values:

- `t2`
- `t2_levels`
- `gdelt`
- `gdelt_raw`

### 7.6 Upgrade Existing Tool: `event_window`

Add an explicit return summary block:

```json
{
  "return_summary": {
    "country_daily_returns": {...},
    "factor_return_leaders": {...},
    "factor_return_laggards": {...},
    "pre_event_return": ...,
    "post_event_return": ...,
    "event_window_return": ...
  }
}
```

The existing raw rows should remain available. The new summary makes event-window answers usable without requiring the agent to manually aggregate rows.

---

## 8. Query Assistant Requirements

### 8.1 Returns-First Routing Rules

Add these rules to `ASADOQueryAssistant._compact_schema_context()` and the planner prompt.

If the user asks about any of the following, the plan should include a return surface unless the user explicitly asks for non-return data only:

- returns,
- performance,
- winners / losers,
- leaders / laggards,
- best / worst,
- worked / did not work,
- helped / hurt,
- beneficiaries,
- who benefits,
- what happened around an event,
- event reaction,
- crisis impact,
- analog outcomes,
- which signal matters,
- did this factor work,
- payoff,
- P&L,
- attribution.

Routing defaults:

| Intent | Default Route |
|--------|---------------|
| "Which countries did best/worst?" | `country_returns` or SQL over `1MRet`/daily returns |
| "Which factors did best/worst?" | `factor_returns` / `factor_returns_daily` |
| "What happened around event X?" | `events_in_window` when date unknown, then `event_window`; include return summary |
| "Why did country X move?" | country returns plus `country_factor_attribution` plus explanatory factors |
| "Which signals worked?" | factor returns first, signal levels second |
| "Does this factor matter?" | factor return history plus exposure/coverage |
| "What should I watch?" | current explanatory signals plus recent country/factor returns |

### 8.2 Planner Output Contract

The plan JSON should add:

```json
{
  "return_surface_used": "country_returns | factor_returns | factor_returns_daily | country_factor_attribution | none",
  "return_surface_reason": "why this surface is or is not used"
}
```

If `return_surface_used = "none"` for a performance/event/explanation question, the plan must include a warning explaining why.

### 8.3 Candidate Variable Enhancement

The variable catalog should include return links where applicable:

```json
{
  "variable": "RSI14_CS",
  "available_return_surfaces": [
    {"table": "factor_returns", "source": "t2_optimizer"},
    {"table": "factor_returns_daily", "source": "t2_optimizer_daily"}
  ]
}
```

For country return variables:

```json
{
  "variable": "1MRet",
  "return_role": "country_return",
  "frequency": "monthly",
  "horizon": "1m"
}
```

### 8.4 Interpretation Rules

When interpreting return outputs:

- State the date and source.
- Distinguish country returns from factor portfolio returns.
- Distinguish factor levels/exposures from factor returns.
- Mention whether the return is daily or monthly.
- Mention when the answer uses top-20% bucket attribution.
- Avoid causal language unless the query actually tested causality.

---

## 9. Schema Cache And Documentation Requirements

### 9.1 New Generated Cache: `returns_catalog.json`

Path:

`Data/cache/query_assistant/returns_catalog.json`

Contents:

- country return variables by frequency, horizon, date range, row count (canonical T2 source only),
- explicit alias entry recording that GDELT-labeled `1MRet` / `1DRet` rows are bit-exact duplicates of the T2 country returns and must not be used as a second source,
- factor return sources by frequency, date range, factor count,
- factor-to-return-source availability map,
- attribution surface metadata,
- latest available return dates by source,
- examples of safe SQL patterns.

### 9.2 Update `access_guide.json`

Add a top-level section:

```json
"return_surfaces": {
  "principle": "Returns are ASADO's outcome layer...",
  "country_returns": {...},
  "factor_returns": {...},
  "attribution": {...},
  "cycle_guardrail": "Do not union optimizer outputs into feature_panel..."
}
```

### 9.3 Update `get_schema_summary`

Add notes that are visible through MCP:

- "Returns are the primary outcome layer."
- "Use country return variables for country performance questions."
- "Use factor_returns / factor_returns_daily for factor performance questions."
- "Use country_factor_attribution for country-level factor bucket contribution."
- "Do not add optimizer output tables to feature_panel/unified_panel."

### 9.4 Update Human Docs

Update:

- `DATA_DICTIONARY.md`
- `README.md`
- `docs/DAILY_EXTENSION_STATUS.md`

Minimum documentation section:

`## Returns Source Of Truth`

It should explain:

- country returns,
- factor returns,
- attribution,
- daily vs monthly,
- T2 vs GDELT vs Econ,
- cycle guardrail.

---

## 10. Implementation Plan

### Phase A: Returns Catalog

Files:

- `scripts/build_schema_registry.py`
- `Data/cache/query_assistant/returns_catalog.json`
- tests or QA script under `scripts/qa/`

Tasks:

1. Add a `build_returns_catalog()` function.
2. Introspect `factor_returns`, `factor_returns_daily`, `factor_top20_membership`, `country_factor_attribution`.
3. Detect country return variables in `feature_panel`, `t2_factors_daily`, `gdelt_factors_daily`.
4. Write `returns_catalog.json`.
5. Add the returns catalog path to `manifest.json`.
6. Include returns metadata in `access_guide.json`.

Validation:

- `returns_catalog.json` exists after `./venv/bin/python scripts/build_schema_registry.py`.
- Counts match live DuckDB within the current run.
- Latest dates are present for each return source.

### Phase B: Deterministic MCP Tools

Files:

- `scripts/asado_mcp_server.py`

Tasks:

1. Add `country_returns`.
2. Add `factor_return_series`.
3. Add `country_factor_attribution` tool.
4. Add `return_leaders`.
5. Extend `daily_factor_series` to support factor return sources.
6. Extend `event_window` with `return_summary`.
7. Add SQL helper functions that escape identifiers and values safely.

Validation:

- Direct Python calls to each MCP function return non-empty rows for known examples.
- `event_window("Turkey", "2018-08-13")` includes country returns and factor return summary.
- `return_leaders(scope="country", direction="best")` returns latest country return leaders.
- `return_leaders(scope="factor", direction="best")` returns latest factor return leaders.

### Phase C: Query Assistant Routing

Files:

- `scripts/query_assistant.py`
- `scripts/build_schema_registry.py`

Tasks:

1. Load returns catalog into planner context.
2. Add return-intent detection to `_question_traits()`.
3. Add `return_surface_used` and `return_surface_reason` to plan output.
4. Update prompt rules for performance/event/explanation questions.
5. Add post-plan guardrail: if return intent exists and no return surface is used, revise or warn.

Validation:

Preview-only plan checks:

```bash
./venv/bin/python scripts/query_assistant.py --preview-only \
  "Which factors have had the best returns recently?"

./venv/bin/python scripts/query_assistant.py --preview-only \
  "Which countries had the best returns last month?"

./venv/bin/python scripts/query_assistant.py --preview-only \
  "What happened to Turkey around the 2018 lira crisis?"

./venv/bin/python scripts/query_assistant.py --preview-only \
  "Which GDELT signals actually worked over the last year?"
```

Expected:

- Factors question uses `factor_returns` or `factor_returns_daily`.
- Countries question uses country return variables.
- Event question uses `event_window` or daily return surfaces, not only monthly `feature_panel`.
- "Signals worked" uses factor return history before signal levels.

### Phase D: QA And Regression Tests

Files:

- `scripts/qa/validate_returns_first.py`
- optional additions to `scripts/qa/step_validators.py`

Required checks:

1. Return tables exist and are non-empty.
2. Country return variables exist in monthly and daily tables.
3. `factor_returns` has all three monthly sources.
4. `factor_returns_daily` has both daily sources.
5. `country_factor_attribution` joins to `factor_returns`.
6. No optimizer return source appears in `feature_panel`.
7. MCP functions return expected non-empty outputs.
8. Query-assistant preview plans choose return surfaces for canonical prompts.

Command:

```bash
./venv/bin/python scripts/qa/validate_returns_first.py
```

Output:

- machine-readable JSON summary,
- nonzero exit code on failure.

### Phase E: Documentation And Frontend Follow-Up

Files:

- `DATA_DICTIONARY.md`
- `README.md`
- `docs/DAILY_EXTENSION_STATUS.md`
- optional `frontend/app.py`

Tasks:

1. Add "Returns Source Of Truth" docs.
2. Add query cookbook examples.
3. Optionally add a Streamlit "Returns" panel:
   - country leaderboard,
   - factor leaderboard,
   - country attribution,
   - event return window.

Frontend is useful but not required for v1 completion. MCP/query behavior is the primary acceptance surface.

---

## 11. Acceptance Criteria

The project is complete when all of the following are true.

### AC1. Returns Catalog Exists

`./venv/bin/python scripts/build_schema_registry.py` writes:

- `Data/cache/query_assistant/returns_catalog.json`
- updated `manifest.json`
- updated `access_guide.json`

### AC2. MCP Tools Work Directly

Direct imports from `scripts.asado_mcp_server` produce non-empty results:

- `country_returns(countries="all", horizon="1MRet", latest_only=True, rank="best")`
- `factor_return_series(factors="all", frequency="monthly", rank="best")`
- `factor_return_series(factors="all", frequency="daily", rank="best")`
- `country_factor_attribution(country="Brazil", date="latest")`
- `return_leaders(scope="country")`
- `return_leaders(scope="factor")`
- `event_window(country="Turkey", date="2018-08-13")` includes `return_summary`

### AC3. Query Assistant Routes Correctly

Preview-only plans route to return surfaces for:

- "Which factors have had the best returns recently?"
- "Which countries had the best returns last month?"
- "Which GDELT signals actually worked over the last year?"
- "What happened to Turkey around the 2018 lira crisis?"
- "Which countries benefited most from the last OPEC cut?"

### AC4. Cycle Guardrail Is Enforced

Validation script confirms optimizer-output sources are absent from `feature_panel` and `unified_panel`.

### AC5. Documentation Is Updated

`DATA_DICTIONARY.md` and `README.md` identify returns as the outcome/source-of-truth layer and explain the table selection rules.

### AC6. No False Success

Do not report `ITS_DONE_TESTED` until the exact MCP and query-assistant behaviors above are exercised in the current environment.

---

## 12. Example Answer Shapes

### 12.1 Country Return Question

User:

> Which countries had the best returns last month?

Answer should include:

- latest return date,
- return source and horizon,
- top countries by return,
- caveat on T2 34-country universe,
- optional explanatory factor snapshot only after return answer.

### 12.2 Factor Return Question

User:

> Which factors have worked recently?

Answer should include:

- factor-return source,
- monthly or daily window,
- top factor portfolios by return,
- distinction between factor return and factor level,
- optional factor coverage / country membership.

### 12.3 Event Question

User:

> What happened to Turkey around the 2018 lira crisis?

Answer should include:

- event date/window,
- Turkey daily country returns over the window,
- factor return leaders/laggards over the window,
- key GDELT/T2 factor changes,
- caveat that event-window evidence is descriptive unless separately tested.

### 12.4 Attribution Question

User:

> Why was Brazil exposed to the best Econ factor last month?

Answer should include:

- latest Econ factor return,
- whether Brazil was in the top-20% bucket,
- Brazil's weight,
- contribution,
- relevant explanatory factor value if needed.

---

## 13. Open Questions

1. Should monthly "recent factor returns" default to latest month or trailing 3/12-month aggregate?
   - Recommended: latest month for "last month"; trailing 12 months for "recently" unless user supplies a window.

2. Should country-factor attribution include only top-20 bucket membership or also current cross-sectional exposure?
   - Recommended: attribution tool returns bucket contribution; answer may separately query current exposure if explanation requires it.

3. Should `event_window` compute cumulative return using simple sum or compounded return?
   - Recommended: simple sum for factor-return compatibility in v1, with a field name that makes this explicit.

4. Should a daily unified returns view be materialized?
   - Recommended: no for v1. Prefer deterministic MCP tools and explicit tables. Revisit only if repeated SQL complexity justifies it.

---

## 14. Implementation Notes

### 14.1 Safe SQL Patterns

Latest monthly country returns:

```sql
WITH latest AS (
  SELECT MAX(date) AS date
  FROM feature_panel
  WHERE variable = '1MRet'
    AND source = 't2'
    AND date <= CURRENT_DATE
)
SELECT country, value AS return_value, date
FROM feature_panel
WHERE variable = '1MRet'
  AND source = 't2'
  AND date = (SELECT date FROM latest)
  AND value IS NOT NULL
ORDER BY return_value DESC;
```

Latest monthly factor returns:

```sql
WITH latest AS (
  SELECT MAX(date) AS date
  FROM factor_returns
  WHERE source = 't2_optimizer'
    AND date <= CURRENT_DATE
)
SELECT factor, value AS factor_return, source, date
FROM factor_returns
WHERE source = 't2_optimizer'
  AND date = (SELECT date FROM latest)
  AND value IS NOT NULL
ORDER BY factor_return DESC;
```

Country-factor attribution:

```sql
WITH latest AS (
  SELECT MAX(date) AS date
  FROM country_factor_attribution
  WHERE source = 'econ_optimizer'
    AND date <= CURRENT_DATE
)
SELECT country, factor, weight, factor_return, contribution, source, date
FROM country_factor_attribution
WHERE country = 'Brazil'
  AND source = 'econ_optimizer'
  AND date = (SELECT date FROM latest)
ORDER BY ABS(contribution) DESC;
```

### 14.2 Naming

Avoid ambiguous names like `returns` for tools or views. Use:

- `country_returns`
- `factor_return_series`
- `return_leaders`
- `country_factor_attribution`

### 14.3 UI Copy

Do not describe returns as "truth" in the user-facing UI in a way that implies certainty or causality. Better language:

- "Outcome layer"
- "Observed return surface"
- "Factor portfolio return"
- "Country return"
- "Attribution from top-20% bucket membership"

---

## 15. Risks

| Risk | Mitigation |
|------|------------|
| Planner overuses returns even for pure data-availability questions | Only trigger returns-first routing for performance/event/explanation intent |
| Factor returns confused with raw factor values | Tool output and interpretation must label factor portfolio returns clearly |
| Country attribution overread as causal | Add standard caveat; keep contribution definition explicit |
| Optimizer output leaks into input panel | Add regression test and schema guardrail |
| Date ranges differ by source | Return tools must report resolved latest date by source |
| GDELT monthly and daily date labels differ | Use existing GDELT partial-label note and source-specific caveats |
| Duplicated GDELT-labeled country returns misread as a second source | `returns_catalog.json` must flag `gdelt` 1MRet/1DRet rows as aliases of T2 country returns; `country_returns` exposes no `source` arg |

---

## 16. Definition Of Done

V1 is done when:

1. `returns_catalog.json` is generated from the live database.
2. MCP exposes deterministic return tools.
3. `ask_asado` routes canonical return/event/signal questions to return surfaces.
4. `event_window` includes a return summary.
5. Regression validation passes.
6. Documentation explains the returns-first contract.
7. The exact acceptance prompts are tested end to end in the current repo environment.

