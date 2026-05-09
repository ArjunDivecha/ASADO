# PRD: Event Log — Date-Anchored Event Study Layer
## ASADO Daily Extension — Phase 1.5

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Date** | 2026-05-08 |
| **Author** | Arjun Divecha (with Claude) |
| **Status** | Draft for review |
| **Depends on** | Stage 1 daily extension (`build_daily_panels.py`, `event_window` MCP tool) |
| **Companion to** | `PRD_Stage2_Prediction_Markets.md` |
| **Estimated effort** | 1–2 days |

---

## 1. Context and Motivation

The Stage 1 daily extension shipped `event_window(country, date, days_before, days_after, ...)` as the canonical event-study primitive. It works — but it requires the *user* to supply the date.

The May 8 Iran-war analysis exposed the gap. Asking "show me Saudi Arabia around the last OPEC cut" requires the analyst to first remember (or look up) the OPEC cut date, then call `event_window`. Asking "compare country reactions to FOMC pivots in 2019, 2022, and 2024" requires knowing six specific dates. Asking "how did EM equities move around major Iran-Israel escalations?" requires knowing every escalation date. Without a structured event registry, this two-step pattern (know-the-date, then study) blocks every interesting historical-analog question.

The unlock is a small, hand-curated `event_log` table containing ~200 dated events tagged with category, severity, and affected countries, plus a single MCP tool `events_in_window` that returns matching events. Combined, the agent layer can answer "show me X around Y" without the user knowing the date — the planner finds the date(s), the existing `event_window` does the study.

This is also infrastructure for the Stage 2 prediction-markets work: prediction markets resolve on events, and an event_log gives the join target for "which prediction markets were live around this event" queries.

---

## 2. Goals and Non-Goals

### Goals

- **G1.** Build a single `event_log` table in `asado.duckdb` containing ~200 hand-curated events spanning 2000–present (with selective coverage of 1990s landmark events), each tagged with category, severity, affected T2 countries, and source URL.

- **G2.** Add one MCP tool: `events_in_window(start_date, end_date, category=None, country=None, severity=None)` returning matching events, designed for clean chaining with the existing `event_window` tool.

- **G3.** Migrate the 9 existing Neo4j `CrisisEvent` nodes into `event_log` and make Neo4j's `CrisisEvent`/`HAS_CRISIS_HISTORY` derived from `event_log` on graph rebuild — single source of truth.

- **G4.** Update `ask_asado` planner prompt so two-step queries ("show me X around the last Y") naturally route through `events_in_window` → `event_window` chain.

- **G5.** Document the curation policy and source URLs so the registry is auditable and extensible.

### Non-Goals

- **NG1.** Forecasting future events. The event_log records past events with confirmed dates. Upcoming-event scheduling (next FOMC, next CPI release) is a separate concern that prediction markets handle in Stage 2.
- **NG2.** Automated event detection. No NLP-driven event extraction from GDELT or news feeds. Curation is manual.
- **NG3.** Sub-daily event timing. Events are date-grain; intraday timing (Fed announcement at 14:00 ET vs. 14:30 ET) is out of scope.
- **NG4.** Event impact estimation. The table records *what happened and when*; downstream tools (`event_window`, factor regressions, prediction markets) measure impact.
- **NG5.** Comprehensive coverage. Two hundred events is enough to unlock the chaining pattern; we are not trying to build a Bloomberg ECO-equivalent.

---

## 3. Schema Design

### 3.1 `event_log` Table

```sql
CREATE TABLE event_log (
    event_id            VARCHAR PRIMARY KEY,   -- stable slug, e.g. 'fomc_2020_03_15_emergency_cut'
    event_date          DATE NOT NULL,         -- canonical event date (start, if multi-day)
    end_date            DATE,                  -- NULL for point events; populated for ranges
    label               VARCHAR NOT NULL,      -- short human-readable name
    description         VARCHAR,               -- 1-3 sentence context
    category            VARCHAR NOT NULL,      -- constrained vocabulary, see §3.2
    subcategory         VARCHAR,               -- optional finer tag
    severity            VARCHAR NOT NULL,      -- 'high' | 'medium' | 'low'
    countries_affected  VARCHAR,               -- comma-separated T2 names; NULL = global
    is_global           BOOLEAN NOT NULL,      -- TRUE if affects all 34 T2 countries materially
    source_url          VARCHAR,               -- canonical reference URL
    tags                VARCHAR,               -- comma-separated freeform tags for search
    notes               VARCHAR,               -- optional long-form context
    added_date          DATE NOT NULL DEFAULT CURRENT_DATE,
    added_by            VARCHAR DEFAULT 'manual'
);

CREATE INDEX idx_event_log_date ON event_log(event_date);
CREATE INDEX idx_event_log_category ON event_log(category);
CREATE INDEX idx_event_log_severity ON event_log(severity);
```

Volume: ~200 rows in V1, expanding to ~500 over 12 months. Trivial scale.

### 3.2 Category Vocabulary

Constrained to keep filters tractable. Eight categories:

| Category | Description | Example |
|---|---|---|
| `central_bank` | FOMC, ECB, BoJ, BoE, EM central bank decisions and pivots | FOMC March 2020 emergency cut, ECB whatever-it-takes |
| `macro_release` | Surprise CPI, NFP, GDP prints that materially moved markets | August 2022 CPI surprise, hot Q4 2023 GDP |
| `oil_supply` | OPEC decisions, supply disruptions, embargoes, infrastructure attacks | Saudi Aramco Abqaiq attack, OPEC+ formation |
| `geopolitical` | Wars, conflicts, sanctions, regime changes, terrorism | 9/11, Russia-Ukraine invasion, Iran-Israel direct strikes |
| `financial_crisis` | Banking crises, sovereign defaults, currency crises, market dislocations | Lehman, SVB collapse, UK gilt crisis |
| `trade_policy` | Tariff announcements, trade-war escalations, deal signings | Trump-China trade war start, Phase 1 deal, USMCA |
| `election` | National elections with material market impact | Brexit referendum, 2016/2024 US elections, Argentina 2023 |
| `regulatory` | Major regulatory rulings, antitrust, sanctions decisions, court actions | IEEPA tariff ruling, EU Big Tech rulings |

The `subcategory` field is freeform and captures finer detail (e.g., `fomc_pivot`, `opec_cut`, `direct_strike`, `bank_failure`).

### 3.3 Severity Definitions

Severity is a curation-time judgment, documented per event in `notes`:

- **high** — Materially moved global risk-on/off, ≥3% S&P move within 5 trading days, or category-defining (Lehman, COVID, Russia invasion)
- **medium** — Material for affected region or asset class, but not global risk-on/off (single-country election, mid-tier OPEC adjustment, ECB pivot in non-crisis period)
- **low** — Notable but contained (single-country election with stable result, scheduled CB meeting with no surprise)

`events_in_window` defaults to `severity='high'` when called without filter; agents can drop the filter for fuller coverage.

### 3.4 Countries Affected

Three modes:

- `is_global=TRUE`, `countries_affected=NULL` — global event, applies to all 34 T2 countries (FOMC, oil shock, COVID)
- `is_global=FALSE`, `countries_affected='Turkey'` — single-country event (2018 Turkey lira crisis)
- `is_global=FALSE`, `countries_affected='India,Pakistan,China'` — regional event (Pulwama, India-Pakistan Kashmir)

Off-universe entities (Iran, Russia, Israel) appear in `tags` but not `countries_affected` — that field is restricted to the 34 T2 names. Iran-related geopolitical events get `tags='iran,middle_east'`.

---

## 4. Curation Plan and Initial Seed

### 4.1 Curation Workflow

1. Build a YAML registry at `config/event_log_seed.yaml`
2. Each entry hand-written with source URL for verification
3. Loaded into `event_log` by `build_event_log.py` (idempotent rebuild)
4. Quarterly review to add new events as they occur

YAML structure mirrors the schema:

```yaml
- event_id: fomc_2020_03_15_emergency_cut
  event_date: 2020-03-15
  label: "FOMC emergency cut to zero, Sunday announcement"
  description: "Fed cuts target to 0-0.25% in unscheduled Sunday meeting; QE restart; coordinated with five global central banks."
  category: central_bank
  subcategory: fomc_pivot
  severity: high
  is_global: true
  source_url: "https://www.federalreserve.gov/newsevents/pressreleases/monetary20200315a.htm"
  tags: "covid,emergency_cut,qe,coordinated"

- event_id: turkey_lira_2018_08_10
  event_date: 2018-08-10
  label: "Turkey lira crisis — 'Black Friday'"
  description: "TRY falls 14% in a single session as Trump tariffs on steel/aluminum compound currency stress; spillover to EM FX."
  category: financial_crisis
  subcategory: currency_crisis
  severity: high
  is_global: false
  countries_affected: "Turkey"
  source_url: "https://www.reuters.com/article/us-turkey-currency/..."
  tags: "em_contagion,currency,trade_dispute"
```

### 4.2 Initial Seed Composition (~200 events)

Approximate breakdown. Exact list curated during build phase.

**Central bank (≈55 events)**
- FOMC: every meeting where rate changed 2008–present, plus meetings with material guidance shifts (Yellen taper-tantrum 2013-05-22, Powell Dec 2018 pivot, Powell Jul 2022 first 75bp hike, Dec 2023 dovish pivot, etc.)
- ECB: Draghi whatever-it-takes (2012-07-26), QE launches, 2022 rate hike cycle starts
- BoJ: YCC adjustment 2022-12-20, rate hike 2024-03-19, end of NIRP
- BoE: 2022 mini-budget intervention, rate cycle peaks
- SNB unpeg (2015-01-15)
- EM CB: Turkey rate decisions (Erdogan-driven), Brazil aggressive cycles, India RBI pivots

**Geopolitical (≈40 events)**
- 9/11 (2001-09-11), Iraq war (2003-03-19, 2003-05-01)
- Crimea annexation (2014-03-18), Russia-Ukraine invasion (2022-02-24)
- Brexit referendum (2016-06-23), Brexit official (2020-01-31)
- COVID WHO pandemic declaration (2020-03-11)
- Capitol attack (2021-01-06)
- Israel Oct 7 (2023-10-07), Iran-Israel direct strikes (2024-04-13, 2024-10-01, 2026 escalations)
- Hong Kong protests start (2019-06-09)
- Pakistan-India Pulwama (2019-02-14), Balakot (2019-02-26)

**Oil supply (≈30 events)**
- 2014-11-27 OPEC no-cut decision (Saudi flood)
- 2016-11-30 OPEC+ formation
- 2019-09-14 Saudi Aramco Abqaiq attack
- 2020-03-09 Saudi-Russia oil price war
- 2020-04-20 negative oil futures
- 2022-03-08 Biden Russian oil ban
- 2022-12-05 G7 Russia oil price cap
- Major OPEC+ cut/extend decisions 2020–present
- Hormuz tanker incidents, Houthi Red Sea attacks

**Financial crises (≈25 events)**
- 1997-07-02 Thai baht float (Asian crisis trigger)
- 1998-08-17 Russia default / LTCM
- 2008-09-15 Lehman, 2008-09-16 AIG, 2008-10-03 TARP
- 2010-05-09 EU-IMF Greece bailout, 2011-08-05 S&P US downgrade
- 2013-03-16 Cyprus bail-in
- 2015-08-11 China yuan devaluation
- 2018-08-10 Turkey lira crisis, 2021-12-16 Turkey lira phase 2
- 2022-09-23 UK Truss mini-budget, 2022-09-28 BoE gilt intervention
- 2023-03-10 SVB collapse, 2023-03-19 Credit Suisse rescue

**Trade policy (≈25 events)**
- 2017-01-23 TPP withdrawal
- 2018-03-22 Trump-China trade war Section 301
- 2018-07-06 first US-China tariff round
- 2020-01-15 Phase 1 deal
- 2020-07-01 USMCA enters force
- 2022-08-09 CHIPS Act
- 2025–2026 Trump tariff cycle (multiple events)
- 2026-02-20 IEEPA tariff Supreme Court ruling
- China rare-earth/critical-minerals policy shifts

**Elections (≈20 events)**
- US: 2008, 2012, 2016, 2020, 2024 presidential
- UK: 2016 Brexit, 2019, 2024
- France: 2017, 2022 (both rounds)
- Italy: 2018, 2022, 2024
- Brazil: 2018 Bolsonaro, 2022 Lula
- Mexico: 2018, 2024
- India: 2014, 2019, 2024
- Turkey: 2018, 2023
- Argentina: 2023 Milei
- Taiwan: 2020, 2024

**Regulatory / other (≈10 events)**
- Major SEC/CFTC rulings affecting markets
- EU Big Tech antitrust milestones
- China regulatory crackdowns (Ant, Didi, education sector)
- Major central bank governance changes

### 4.3 Off-Universe Entity Coverage

Critical: Iran, Russia, Israel, Saudi Arabia (as off-universe-equivalent for sovereign-risk purposes), and Ukraine appear in `tags`, never in `countries_affected`. Use Iran-Israel direct strikes (2024-04-13) as the canonical example — `countries_affected=NULL`, `is_global=FALSE`, `tags='iran,israel,middle_east,direct_strike'`. Agents querying "events affecting Iran" use a tag filter; agents querying "events affecting Saudi Arabia" use the countries_affected filter.

### 4.4 Source Standards

Every event has a `source_url`. Acceptable sources, ranked:

1. Primary central bank or government announcement (Fed press release, BoE statement, BLS release)
2. Reuters, AP, FT, WSJ contemporaneous coverage
3. Wikipedia (acceptable for well-documented historical events; not for recent contested events)
4. ASADO internal research notes (only when no public source captures the event well)

---

## 5. MCP Tool: `events_in_window`

### 5.1 Signature

```python
def events_in_window(
    start_date: str,           # ISO date 'YYYY-MM-DD'
    end_date: str,             # ISO date 'YYYY-MM-DD'
    category: str = None,      # filter to one category from §3.2 vocabulary
    country: str = None,       # T2 country name; matches countries_affected OR is_global
    severity: str = "high",    # 'high' | 'medium' | 'low' | 'all'; default 'high'
    tag_filter: str = None,    # comma-separated tags; ANY match
    max_results: int = 50,
) -> dict:
    """
    Return events from event_log matching filters, sorted by date descending.
    Designed for chaining with event_window: planner finds events, then loops
    event_window per event for the country of interest.
    """
```

### 5.2 Return Shape

```json
{
  "row_count": 8,
  "columns": ["event_id", "event_date", "label", "category",
              "severity", "countries_affected", "is_global", "tags"],
  "rows": [
    {
      "event_id": "fomc_2024_12_18_dovish_pivot",
      "event_date": "2024-12-18",
      "label": "FOMC December 2024 dovish dot-plot pivot",
      "category": "central_bank",
      "severity": "high",
      "countries_affected": null,
      "is_global": true,
      "tags": "fomc,pivot,dovish"
    },
    ...
  ]
}
```

### 5.3 Chaining Example

The natural agent-side pattern, in pseudocode:

```python
# "Show me Saudi Arabia around the last 3 OPEC cuts"
events = events_in_window(
    start_date="2022-01-01",
    end_date="2026-05-08",
    category="oil_supply",
    tag_filter="opec_cut",
    max_results=3,
)
results = []
for ev in events["rows"]:
    window = event_window(
        country="Saudi Arabia",
        date=ev["event_date"],
        days_before=5,
        days_after=10,
    )
    results.append({"event": ev, "study": window})
return results
```

### 5.4 Country Filter Semantics

When `country` is supplied, the tool returns events where:
- `country` is in `countries_affected` (CSV match), OR
- `is_global=TRUE`

This means asking for "events affecting Brazil 2018" returns both Brazil-specific events (election, currency stress) and global events (FOMC pivots, COVID, oil shocks) that would have moved Brazilian equities. That is the correct default — global events affect all countries.

To get strictly country-specific events, agents pass `country='Brazil'` AND filter the result client-side on `is_global=FALSE`. Optional convenience flag `strict_country=True` to push this server-side; deferred to V2.

---

## 6. Neo4j Integration

### 6.1 Migrate Existing CrisisEvent Nodes

The current `setup_neo4j.py` creates 9 hand-curated `CrisisEvent` nodes with `HAS_CRISIS_HISTORY` edges. Migrate these to `event_log` rows with `category='financial_crisis'`. Existing 9 nodes:

(Per the README — exact list to be enumerated during migration; expected to include 1997 Asian crisis, 1998 Russia/LTCM, 2008 GFC, 2010-12 EU sovereign, 2013 taper tantrum, 2015 China devaluation, 2018 Turkey lira, 2020 COVID, 2023 SVB.)

### 6.2 Derived CrisisEvent Nodes

Modify `setup_neo4j.py` so `CrisisEvent` nodes and `HAS_CRISIS_HISTORY` edges are *derived* from `event_log` on graph rebuild:

```python
# In setup_neo4j.py, after country and factor nodes:
for event in db.query("""
    SELECT event_id, event_date, end_date, label, severity, countries_affected, tags
    FROM event_log
    WHERE category = 'financial_crisis' AND severity IN ('high', 'medium')
"""):
    # MERGE CrisisEvent node, MERGE HAS_CRISIS_HISTORY edges to affected countries
    ...
```

This means adding a new financial-crisis row to `event_log` and rebuilding the graph automatically updates Neo4j. Single source of truth.

### 6.3 Optional: Generic Event Nodes

Open question whether to mirror *all* event_log entries as Neo4j `Event` nodes (broader than `CrisisEvent`). Argument for: enables Cypher queries like "for each Country, list events in 2024 ranked by severity, with factor exposure changes around each." Argument against: more graph clutter, most use cases are served by the DuckDB-side `events_in_window` + `event_window` chain.

Recommendation: defer to V2. V1 does only `CrisisEvent` migration to avoid breaking existing graph consumers.

---

## 7. ask_asado Planner Integration

The planner prompt in `asado_mcp_server.py` gets a small addition recognizing two-step event-anchored queries.

Trigger phrases the planner should recognize and route through `events_in_window` first:

- "around the last X" / "around recent X"
- "during the X crisis"
- "around major X events"
- "compare reactions to X"
- "show me X across [historical period]"
- "how did Y move during Z"

Pattern: when the user references an event by description rather than date, planner first calls `events_in_window` with appropriate filters, then loops `event_window` per matched event for the country (or countries) of interest. Synthesizes results across events.

If `events_in_window` returns zero matches, planner falls back to asking the user for the date or directly querying GDELT for unstructured event signals.

---

## 8. Build Plan (1–2 days)

### Day 1: Schema, Curation, Loader

**Morning (3–4h)**
- Create `scripts/build_event_log.py` skeleton, mirroring `build_daily_panels.py` patterns: idempotency, backup, mtime guards, failure handling
- Define schema and indexes
- Hand-curate the macro / central bank / oil-supply seed (≈85 events) — these have well-documented dates and clear severity classifications
- Smoke-test: load YAML → DuckDB → verify count, date range, category distribution

**Afternoon (3–4h)**
- Curate geopolitical, financial_crisis, election, trade_policy, regulatory seeds (≈115 events)
- Verify source URLs for each; flag any without primary source
- Run validation: every event has unique `event_id`, valid category, valid severity, parseable date
- Migrate the 9 existing `CrisisEvent` nodes' content into the YAML

### Day 2: MCP, Neo4j, Integration

**Morning (3–4h)**
- Add `events_in_window` to `asado_mcp_server.py`
- Smoke-test all filter combinations (date range, category, country, severity, tags)
- Verify chain works: `events_in_window` → `event_window` per result
- Update `asado_mcp_server.py` planner prompt with two-step event pattern

**Afternoon (2–3h)**
- Modify `setup_neo4j.py` to derive `CrisisEvent` nodes from `event_log`
- Rebuild graph; verify `HAS_CRISIS_HISTORY` edge counts unchanged or improved
- Add `build_event_log.py` step to `monthly_update.py` orchestrator (early — between data collection and DuckDB rebuild)
- Update `README.md` with new tool documentation
- Run end-to-end: `monthly_update.py` rebuilds DuckDB + event_log + Neo4j, MCP server picks up new tool

### Acceptance Criteria

1. `event_log` table populated with ≥180 events, all categories represented, all severities represented
2. Every row has a non-NULL `source_url` or explicit ASADO-research provenance in `notes`
3. `events_in_window` returns correct results for at least 10 hand-tested filter combinations
4. Chaining `events_in_window` → `event_window` runs end-to-end on three canonical queries: (a) Saudi around last 3 OPEC cuts, (b) Turkey around 2018 + 2021 lira crises, (c) all 34 countries around 2024-04-13 Iran-Israel strike
5. Neo4j `CrisisEvent` nodes are populated from `event_log`, edge count ≥ existing 123
6. `monthly_update.py` runs cleanly with the new step inserted
7. README updated with `events_in_window` tool documentation

---

## 9. Open Questions

1. **Recurring vs. instance modeling.** FOMC happens 8x/year. Each meeting is a separate `event_log` row with its own `event_id`. For a query like "all FOMC meetings 2023," `category='central_bank'` + `subcategory='fomc'` filter does the job. Recommendation: stick with one row per occurrence, no template/instance duality.

2. **Event ranges.** Some events have meaningful end dates (Russia-Ukraine war ongoing, COVID lockdowns 2020-03-11 to 2022-03-11). For `events_in_window`, do we match events that *overlap* the requested window, or events whose `event_date` falls in it? Recommendation: overlap. An ongoing-conflict event with `end_date=NULL` and start before the window matches if it's still active. Implement as `event_date <= window.end AND (end_date IS NULL OR end_date >= window.start)`.

3. **Severity calibration.** "High" is the default; if too inclusive we miss specificity, if too exclusive we miss events. Recommendation: start with strict definitions (S&P ±3% within 5d), expect to refine after first month of usage.

4. **Inclusion threshold for 1990s events.** Only landmark events (1997 Asian crisis, 1998 Russia/LTCM, 1992 Black Wednesday, 1994 Mexico tequila) go that far back. Recommendation: ~10 pre-2000 events, all `severity='high'`.

5. **Off-universe entity normalization.** The `tags` field is freeform. Recommendation: maintain a small `tag_vocabulary` constant in the loader script enumerating canonical tags (`iran`, `russia`, `israel`, `ukraine`, `saudi_arabia` for off-universe, plus thematic tags like `opec_cut`, `fomc_pivot`, `currency_crisis`). New tags require explicit addition.

6. **Auto-detected events from GDELT.** Long-term, the GDELT `event_goldstein_mean_z` spike-detection could surface candidate events for human review. Out of scope for V1; logged as future enhancement.

7. **Prediction-market resolution linkage.** Stage 2 prediction markets resolve on events. Should `event_log.event_id` become a foreign key target for `predmkt_market_meta.resolves_on_event_id`? Recommendation: yes, when Stage 2 ships. V1 doesn't need this column; add it during Stage 2 build.

8. **Curation refresh cadence.** New events occur. Recommendation: monthly review during `monthly_update.py` runs — log when last curation review happened, alert if >60 days stale. The actual curation is hand-done.

---

## 10. Future Extensions (Post-V1)

- **GDELT-suggested events.** Nightly job that surfaces dates with extreme `event_goldstein_mean_z` or `country_news_risk_TS` for human review and inclusion.

- **Prediction-market integration.** When Stage 2 ships, link prediction markets to `event_log` resolutions for "what did the market price into this event before/after" analysis.

- **Generic Event nodes in Neo4j.** Mirror all event_log rows (not just financial_crisis) as Neo4j Event nodes with category-specific edges (`AFFECTED_BY`, `OCCURRED_DURING`, etc.).

- **Severity recalibration based on realized factor returns.** Once we have ≥6 months of `events_in_window` → `event_window` chained queries, regress realized factor moves on event severity to validate the hand-assigned severity labels. Update hand assignments where evidence overwhelms judgment.

- **Event clusters.** Some events are episodes within a larger story (multiple OPEC meetings during a single oil cycle, multiple FOMC meetings in a single hike cycle). Optional `cluster_id` field linking related events.

- **Multi-day event detail.** For multi-day events (G20 summits, OPEC technical committees), capture sub-events with parent-event linkage. Out of V1 scope.

---

## 11. References

- Existing Stage 1 daily extension (`build_daily_panels.py`, `event_window` MCP tool)
- ASADO Daily Extension Status (`docs/DAILY_EXTENSION_STATUS.md`)
- Stage 2 Prediction Markets PRD — `event_log` is the join target for prediction-market resolutions
- Neo4j `CrisisEvent` schema (current 9 hand-curated nodes — see `setup_neo4j.py`)
- May 8 Iran-war analysis discussion — original motivating use case

---

*End of PRD*
