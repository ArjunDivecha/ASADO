# PRD: Event Log Quality Pass + Cleanup
## ASADO — Quiet-Period Tightening

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Date** | 2026-05-08 |
| **Author** | Arjun Divecha (with Claude) |
| **Status** | Draft for review |
| **Depends on** | `event_log` table (shipped 2026-05-08), `events_in_window` MCP tool with subcategory filter |
| **Companion to** | `PRD_Event_Log.md`, `PRD_Stage2_Prediction_Markets.md` |
| **Estimated effort** | ~1 day total (3 discrete items) |

---

## 1. Context

The Stage 1.5 event_log layer shipped on schedule with 124 hand-curated events, the `events_in_window` MCP tool, the `subcategory` filter, and the Neo4j CrisisEvent migration. Two minor gaps and one piece of dead code remain. None block usage; all are tightening passes that improve agent-query quality and reduce code surface before Stage 2 (prediction markets) starts.

Three items in scope:

- **A — Curation pass.** Two categories are too thin for the agent layer to surface useful matches: `macro_release` (5 events) and `regulatory` (7 events). Target ~15–20 events each.
- **B — Drop the `CRISIS_EVENTS` fallback** in `setup_neo4j.py`. Originally added for safety when `event_log` didn't exist; now redundant and risks silent stale data.
- **C — Add `strict_country=True` flag** to `events_in_window`. Optional one-parameter addition for the rare case where an agent wants country-specific events without global noise.

Total estimated effort: ~1 day. None of these unlock fundamentally new capabilities — they remove rough edges from a working system before the next major build.

---

## 2. Goals and Non-Goals

### Goals

- **G1.** Expand `event_log.macro_release` from 5 events to ≥15 events with proper source URLs and severity classification.
- **G2.** Expand `event_log.regulatory` from 7 events to ≥15 events with proper source URLs and severity classification.
- **G3.** Remove the hardcoded `CRISIS_EVENTS` constant from `setup_neo4j.py`. Replace with a hard failure if `event_log` is missing or returns zero financial-crisis rows.
- **G4.** Add `strict_country: bool = False` parameter to `events_in_window` so agents can request country-specific events excluding global ones.

### Non-Goals

- **NG1.** Bulk expansion across other categories. `central_bank` (34), `geopolitical` (21), `oil_supply` (14), `financial_crisis` (15), `election` (15), `trade_policy` (13) are all dense enough.
- **NG2.** Schema changes to `event_log`. The 14-column schema is sufficient.
- **NG3.** New MCP tools. Only the `strict_country` parameter on the existing tool.
- **NG4.** Automated event extraction from GDELT or news. Curation remains manual.
- **NG5.** Recurating existing events. The existing 124 events are good as-is; the work is purely additive.

---

## 3. Item A — Curation Pass

### 3.1 Selection criteria (mirrors PRD_Event_Log §4)

For both categories, the inclusion test:

- **High severity**: surprise versus consensus by ≥2 standard deviations of the previous 12-month consensus dispersion, OR single-day market move ≥1.5% in S&P 500 / ≥10 bps in 10Y UST attributable to the announcement, OR category-defining event (e.g., first Bitcoin spot ETF, Google antitrust ruling).
- **Medium severity**: material for the affected sector or asset class but not S&P-moving (specific sector regulatory action, mid-tier macro release with directional surprise but no full repricing).
- **Excluded**: scheduled releases that printed close to consensus, sector regulatory actions affecting a single small company, routine SEC enforcement.

### 3.2 `macro_release` candidate seed list

Curator picks at least 10 from this list, adds others from their own knowledge, target ≥15 total. Every entry needs a primary source URL (BLS, BEA, Fed, Bloomberg/Reuters coverage).

| Date | Event | Severity | Notes |
|---|---|---|---|
| 2022-07-13 | June CPI 9.1% YoY peak | high | Highest since 1981; cycle peak |
| 2022-08-10 | July CPI 8.5% downside surprise | high | First inflection; S&P +2.1% |
| 2022-08-26 | Powell Jackson Hole "pain" speech | high | Hawkish; S&P −3.4% same day |
| 2022-11-10 | October CPI 7.7% downside surprise | high | S&P +5.5%, biggest one-day rally in 2+ years |
| 2023-02-03 | January NFP 517K vs 187K consensus | high | Nearly 3x consensus; rate-cut pricing reversed |
| 2023-08-25 | Powell Jackson Hole "higher for longer" | high | Repricing of cuts |
| 2024-01-25 | Q4 2023 GDP 3.3% advance estimate | high | Hot vs 2.0% consensus |
| 2024-02-02 | January NFP 353K | high | Hot; 10Y +14 bps |
| 2024-02-13 | January CPI 3.1% upside surprise | high | S&P −1.4%, biggest miss in months |
| 2024-04-10 | March CPI 3.5% upside surprise | high | 10Y +20 bps; cuts pushed out |
| 2024-08-02 | July NFP 114K + Sahm Rule trigger | high | Recession-rule activation; risk-off |
| 2024-08-21 | BLS QCEW −818K benchmark revision | high | Largest preliminary downward revision since 2009 |
| 2024-09-06 | August NFP + 50bp Fed pricing | high | Set up first cut of cycle |
| 2024-12-06 | November NFP rebound from Boeing/hurricanes | medium | Cleaner read |
| 2025-Q1 | Various 2025 prints — curator to fill | — | Fill from CPI/NFP/PCE calendar |
| 2025-Q4 | Various 2025 prints — curator to fill | — | Recent activity |

If the curator is short on time, the 10 highest-leverage entries are: 2022-07-13, 2022-08-10, 2022-11-10, 2023-02-03, 2024-01-25, 2024-02-13, 2024-04-10, 2024-08-02, 2024-08-21, plus one 2025 print of choice.

### 3.3 `regulatory` candidate seed list

| Date | Event | Severity | Notes |
|---|---|---|---|
| 2020-11-03 | Ant Financial IPO suspended | high | Largest IPO ever, halted day before; China tech rerating |
| 2021-07-02 | China cybersecurity probe of DiDi | high | 2 days after NYSE IPO; KWEB −10% in days |
| 2021-07-23 | China after-school tutoring effectively banned | high | TAL/EDU/GOTU −70% in 3 days |
| 2021-08-03 | China gaming "spiritual opium" attack | high | Tencent/NetEase / sector-wide hit |
| 2023-06-05 | SEC sues Binance + Coinbase same week | high | Crypto-broad selloff; defined enforcement era |
| 2023-08-23 | DOJ–Big Tech antitrust escalation | medium | Several ongoing actions |
| 2024-01-10 | Bitcoin spot ETF approvals (10 issuers) | high | $50B+ inflow over 2024; structural shift |
| 2024-04-24 | TikTok divestment law signed | high | China-tech tension; ByteDance equity rerating |
| 2024-05-23 | Ether spot ETF approvals | medium | Smaller flows than BTC but structural |
| 2024-08-01 | EU AI Act enters force | medium | Global compliance template |
| 2024-08-05 | DOJ Google search antitrust ruling | high | Illegal monopoly verdict; first major Big Tech break ruling |
| 2025-Q1+ | Curator to fill from 2025 activity | — | Various |

If short on time, the 10 highest-leverage entries are: 2020-11-03, 2021-07-02, 2021-07-23, 2021-08-03, 2023-06-05, 2024-01-10, 2024-04-24, 2024-08-05, plus two 2025+ entries of choice.

### 3.4 Country-affected discipline

Both categories tend to have global effects but with country-specific concentrations:

- China regulatory actions (DiDi, tutoring, gaming, Ant) → `is_global=FALSE`, `countries_affected='ChinaA,ChinaH'` (and add `'Hong Kong'` where relevant for the H-share linkage).
- US macro releases → `is_global=TRUE` (broadly affect all 34 T2 countries via USD/risk channels).
- Bitcoin/Ether ETF approvals → `is_global=FALSE`, `countries_affected='U.S.,NASDAQ'` (US-listed product). Add `tags='crypto,bitcoin,etf'`.
- Google antitrust → `is_global=FALSE`, `countries_affected='U.S.,NASDAQ'`. Add `tags='antitrust,big_tech,doj'`.
- TikTok divestment → `is_global=FALSE`, `countries_affected='U.S.,ChinaA,ChinaH,NASDAQ'`. Add `tags='china,bytedance,tech_decoupling'`.

### 3.5 Validation steps

After adding entries to `config/event_log_seed.yaml`:

1. Run `python scripts/build_event_log.py --check` — must pass (no validation errors).
2. Run `python scripts/build_event_log.py` — rebuilds the table.
3. Spot-check counts:
   ```sql
   SELECT category, COUNT(*) FROM event_log
   WHERE category IN ('macro_release','regulatory')
   GROUP BY category;
   ```
   Expected: ≥15 each.
4. Confirm every new entry has a non-NULL `source_url`:
   ```sql
   SELECT event_id FROM event_log
   WHERE category IN ('macro_release','regulatory')
     AND source_url IS NULL;
   ```
   Expected: zero rows.
5. End-to-end test through MCP layer:
   ```python
   events_in_window(start_date='2022-01-01', end_date='2025-12-31',
                    category='macro_release', max_results=20)
   # Should return ≥10 high-severity events
   events_in_window(start_date='2020-01-01', end_date='2025-12-31',
                    category='regulatory', max_results=20)
   # Should return ≥10 events
   ```

---

## 4. Item B — Drop `CRISIS_EVENTS` Fallback

### 4.1 Current state

`setup_neo4j.py` contains a `CRISIS_EVENTS` constant (~9 entries) used as a fallback when `event_log` doesn't exist. The fallback was useful during the migration cycle; now that `monthly_update.py` always builds `event_log` before Neo4j, the fallback is dead code that:

- Increases code surface
- Creates a silent failure mode: if `event_log` accidentally becomes empty (table dropped, build script bug), Neo4j would still get the stale hardcoded list and nothing would alert
- Disagrees with `event_log` if the hand-curated list is updated but `CRISIS_EVENTS` isn't

### 4.2 Target state

Replace the fallback with hard-fail logic:

```python
def _load_crisis_events_from_db(con):
    rows = con.execute("""
        SELECT event_id, event_date, end_date, label, description,
               severity, countries_affected, is_global, tags
        FROM event_log
        WHERE category = 'financial_crisis'
          AND severity IN ('high', 'medium')
        ORDER BY event_date
    """).fetchall()
    if not rows:
        raise ValueError(
            "event_log has no financial_crisis events. "
            "Run scripts/build_event_log.py before setup_neo4j.py. "
            "If you intend to skip CrisisEvent nodes, pass --skip-crisis-events."
        )
    return rows
```

Also add an opt-out flag for legitimate cases where someone wants to rebuild Neo4j without crisis nodes (e.g., during pure-graph-experimentation):

```bash
python scripts/setup_neo4j.py --skip-crisis-events
```

### 4.3 Code changes

1. Remove the `CRISIS_EVENTS = [...]` block from `setup_neo4j.py`.
2. Remove the `try/except` fallback path that selects between DB query and hardcoded list.
3. Replace with single-source query above.
4. Add `--skip-crisis-events` argparse flag.
5. Update inline docstring/header to reflect that `event_log` is now a required upstream.

### 4.4 Validation

1. Run `python scripts/setup_neo4j.py --check` against current DB — should produce identical CrisisEvent count to current state.
2. Manually drop `event_log` table: `DROP TABLE event_log;` in DuckDB.
3. Run `python scripts/setup_neo4j.py` — should fail with the clear ValueError above, not silently use stale data.
4. Restore `event_log` via `python scripts/build_event_log.py` and re-run `setup_neo4j.py` — should succeed.
5. Run with `--skip-crisis-events` against a database with no `event_log` — should succeed (and skip CrisisEvent nodes).

### 4.5 Risk and mitigation

**Risk**: a future scripted environment runs `setup_neo4j.py` without first running `build_event_log.py`, hitting the new hard failure.

**Mitigation**: `monthly_update.py` already orders these correctly. The error message tells the user exactly what to do. The opt-out flag handles intentional skips.

---

## 5. Item C — `strict_country` Flag

### 5.1 Current behavior

`events_in_window(country='Brazil', ...)` matches:

```sql
WHERE (is_global = TRUE OR countries_affected LIKE '%Brazil%')
```

This returns global events (FOMC, COVID, oil shocks) plus Brazil-specific events. That's the right default — global events do affect Brazil — but occasionally an analyst wants only Brazil-specific events (BCB surprise hike, election, fiscal-package risk) without global noise.

### 5.2 Target behavior

Add `strict_country: bool = False` parameter:

- `strict_country=False` (default): current behavior — returns events where country is in `countries_affected` OR `is_global=TRUE`.
- `strict_country=True`: returns only events where the country is explicitly in `countries_affected` AND `is_global=FALSE`.

### 5.3 Code change

In `events_in_window`, the country filter clause becomes:

```python
if country:
    if strict_country:
        conditions.append(
            "(is_global = FALSE AND countries_affected LIKE ?)"
        )
    else:
        conditions.append(
            "(is_global = TRUE OR countries_affected LIKE ?)"
        )
    params.append(f"%{country}%")
```

### 5.4 Docstring update

Add to the existing docstring under `Args:`:

```
strict_country: When False (default), country filter matches both
    country-specific events (countries_affected contains country) and
    global events (is_global=TRUE). When True, returns only events
    explicitly tagged with this country and not marked global.
    Use True for "country-specific events only" queries; False for
    "all events that would have moved this country."

    Example:
        events_in_window(country='Brazil', strict_country=False)
            → returns FOMC + Brazil election + global oil shocks
        events_in_window(country='Brazil', strict_country=True)
            → returns only Brazil-specific (BCB, election, fiscal-package)
```

### 5.5 Validation

1. `events_in_window(start_date='2018-01-01', end_date='2024-12-31', country='Turkey', strict_country=False)` — returns Turkey lira events plus global events of the period.
2. `events_in_window(...same..., strict_country=True)` — returns only Turkey lira events.
3. `events_in_window(...same..., country=None, strict_country=True)` — `strict_country` ignored when no country supplied. Confirm no error.
4. Existing call sites (no `strict_country` argument) continue to work unchanged.

---

## 6. Build Plan

| Block | Item | Time | Validation |
|---|---|---|---|
| AM | A — macro_release curation (≥10 entries) | 2 hours | YAML loads, count ≥15 after load |
| AM | A — regulatory curation (≥10 entries) | 2 hours | YAML loads, count ≥15 after load |
| Lunch | — | — | — |
| PM | B — Drop CRISIS_EVENTS, add hard-fail | 1 hour | setup_neo4j.py succeeds with event_log, fails clearly without |
| PM | B — Add `--skip-crisis-events` flag | 30 min | Flag-based opt-out works |
| PM | C — Add `strict_country` parameter | 30 min | Both branches return expected results |
| PM | C — Update docstring + smoke test | 30 min | MCP tool surfaces new parameter; existing calls unaffected |
| PM | End-to-end: rebuild DuckDB → Neo4j → MCP | 1 hour | `monthly_update.py --db-only` clean |

Total: ~7.5 working hours, fits in one focused day.

---

## 7. Acceptance Criteria

1. `event_log` has ≥15 `macro_release` events and ≥15 `regulatory` events. All new entries have non-NULL `source_url`. All severity values are `high` or `medium`.
2. `setup_neo4j.py` no longer references the hardcoded `CRISIS_EVENTS` constant. `setup_neo4j.py --check` confirms the same CrisisEvent count as before. Dropping `event_log` and re-running `setup_neo4j.py` raises a clear ValueError instead of silently using stale data.
3. `events_in_window` accepts `strict_country: bool = False`. Existing call sites continue to work unchanged. New parameter behaves per §5.2.
4. End-to-end smoke test: `monthly_update.py --db-only` runs cleanly with no errors. The `events_in_window` MCP tool returns expected results for both new categories.
5. `README.md` updated in two small places: the `events_in_window` docstring/description references the new parameter; the setup_neo4j description notes that `event_log` is now a required upstream.

---

## 8. Open Questions

1. **Subcategory taxonomy for new entries.** The existing `event_log` has 68 well-considered subcategories. New `macro_release` entries should use existing subcategories where possible: `cpi_surprise`, `jobs_report`, `gdp_print`, `fed_speech_jh` (Jackson Hole), `data_revision`. New `regulatory` entries: `china_crackdown` (DiDi/tutoring/gaming), `crypto_etf_approval`, `crypto_enforcement` (SEC v Binance), `antitrust_ruling`, `ai_regulation`, `export_controls`. Recommendation: use existing subcategories where they fit; introduce new ones only when no existing subcategory captures it. Document new subcategories in the loader's vocabulary check.

2. **Whether to backfill 2025 events.** The candidate lists include both 2024 events (well-documented in retrospect) and 2025 entries marked "curator to fill." The curator has fresher knowledge for 2025+ than what's in any external source. Recommendation: add ≥3 2025 entries per category from direct knowledge, and extend during quarterly review.

3. **`strict_country` and tag filter interaction.** Currently `tag_filter` is independent of `country`. With `strict_country=True`, should tag filter still allow matches via `is_global=TRUE` events that have the tag? Recommendation: yes — `strict_country` only affects the country dimension, not tag matching. An agent wanting to find "global events tagged with `iran` that affected Brazil" can use `tag_filter='iran'` without `strict_country`.

4. **Whether to deprecate the CRISIS_EVENTS constant gracefully or remove outright.** Going outright is cleaner but means a single point of failure for one cycle. Recommendation: remove outright. The hard-fail is the correct behavior; gradual deprecation just delays the failure mode without making it less serious.

5. **Adding a `severity='medium' OR 'high'` shorthand.** Right now an agent has to call twice or pass `severity='all'` (which includes `low` if it ever exists). Worth a `severity='material'` shorthand that maps to `IN ('high','medium')`? Probably yes, but defer to a follow-on PR — not in scope here.

---

## 9. References

- `PRD_Event_Log.md` (this directory) — original event_log PRD
- `config/event_log_seed.yaml` — current 124-entry registry
- `scripts/build_event_log.py` — loader and validator
- `scripts/asado_mcp_server.py` — `events_in_window` tool implementation
- `scripts/setup_neo4j.py` — current CRISIS_EVENTS fallback location
- May 8 2026 verification thread — context for these three follow-ups

---

*End of PRD*
