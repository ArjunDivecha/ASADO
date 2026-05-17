# PRD: Tracked-Handle Social Event Detection
## ASADO — Stage 3 (Layer 1 of Social Signals)

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Date** | 2026-05-09 |
| **Author** | Arjun Divecha (with Claude) |
| **Status** | Draft for review |
| **Depends on** | Event log shipped (`event_log` table, `events_in_window` MCP tool), Stage 2 Prediction Markets shipped, daily panels shipped |
| **Companion to** | `PRD_Event_Log.md`, `PRD_Stage2_Prediction_Markets.md` |
| **Estimated effort** | ~5 days (1 working week) |
| **Estimated ongoing cost** | ~$145/mo (X API Basic tier $100 + LLM classification ~$45) |

---

## 1. Context and Motivation

ASADO has three freshness layers today:
- **Daily T2 + GDELT panels** — quantitative factor and sentiment, updated daily, with ~15-minute lag on GDELT and end-of-day on T2.
- **Prediction markets** — 18 curated Kalshi/Polymarket markets, daily snapshot, forward-looking probabilities.
- **Event log** — 146 hand-curated dated events, 8 categories, manually maintained.

The gap: **primary-source signals from named officials and decision-makers**. When a central bank governor, finance minister, trade official, or major-exporter CEO posts on X, that signal exists *before* it shows up in GDELT (which sources from media coverage of the post) and is more authoritative than aggregated press commentary.

The May 8 Iran-war analysis surfaced this gap implicitly: asking "what is the market saying about regional escalation" relied on retrospective GDELT tone signals plus prediction-market probabilities. There was no surface that captured "what did the Saudi finance minister actually say in the last 48 hours" or "did anyone with material decision authority comment on tariff policy this week."

The Twitter/X exploration on 2026-05-09 also surfaced a critical failure mode: an existing Grok-based script at `/Users/arjundivecha/Dropbox/AAA Backup/A Working/Grok/Grok.py` produces JSON files of "tweets" that are actually LLM-generated synthesis rather than real X posts (verified by sequential placeholder post IDs that repeat across markets). Any X integration must come in with the same standard the rest of ASADO holds — verifiable sources, traceable IDs, hand-curated entity lists, and human review before anything auto-merges into active surfaces.

This PRD specifies a focused, narrowly-scoped tracked-handle event detection layer that:
1. Pulls tweets only from a hand-curated list of ~100 high-signal accounts via the official X API v2
2. Verifies authenticity (real snowflake post IDs, real engagement counts)
3. Classifies each tweet for ASADO event-log relevance using LLM with structured output
4. Surfaces high-relevance tweets through a curation queue (mirroring the prediction-markets pattern)
5. Allows human-approved tweets to flow into `event_log` as auto-detected events with social-source provenance

This is **Layer 1** of the broader social-signals exploration. **Layer 2** (general local-language sentiment overlay to GDELT) is explicitly out of scope and would only be considered after Layer 1 demonstrates value over 4–6 weeks of operation.

---

## 2. Goals and Non-Goals

### Goals

- **G1.** Curated registry of 50–100 high-signal X accounts spanning central bankers, finance ministers, trade officials, major-exporter CEOs, and top-tier financial journalists across the 34 T2 countries.
- **G2.** Daily ingestion of tweets from these accounts via the official X API v2, with verifiable snowflake post IDs, real engagement counts, and reproducible URLs.
- **G3.** LLM-based event classification per tweet: relevance score (0–1), matched ASADO event-log categories, suggested event_log label, rationale.
- **G4.** Curation-queue handoff for high-relevance tweets — they appear as candidates for `event_log` promotion but require human review before becoming active events.
- **G5.** New DuckDB table `social_events` storing all pulled tweets with classification metadata; new MCP tools `recent_social_signals` and `handle_event_history` for downstream queries.
- **G6.** Multilingual support — classifier must work on Mandarin, Korean, Hindi, Turkish, Portuguese, Arabic, Spanish, etc. without translation as an intermediate step.
- **G7.** Containment of failure modes: hallucinated content, account compromise, classifier errors, API outages all degrade gracefully without polluting `event_log`.

### Non-Goals

- **NG1.** General-purpose Twitter sentiment scoring (Layer 2; out of scope).
- **NG2.** Daily LLM tweet feeds across all T2 countries (the existing Grok script's pattern; explicitly rejected).
- **NG3.** Automatic promotion of tweets to `event_log` without human review.
- **NG4.** Real-time streaming or sub-daily polling. Daily polling is sufficient for monthly factor rotation context.
- **NG5.** Reply-thread or quoted-tweet recursive expansion. Each tweet is treated as standalone.
- **NG6.** Trading on tweet content. Read-only ingestion only.
- **NG7.** X API enterprise tier. Basic tier ($100/mo) is sufficient for 100 handles at daily polling cadence.
- **NG8.** Bot-like X account behavior detection or coordinated-inauthentic-behavior surfacing. The handle whitelist obviates this concern by definition.

---

## 3. Data Source

### 3.1 X API v2 (Basic tier)

**Endpoint base**: `https://api.twitter.com/2/`

**Auth**: OAuth 2.0 Bearer Token. Stored in env as `X_BEARER_TOKEN`, loaded from `~/Dropbox/AAA Backup/.env.txt` consistent with `FRED_API_KEY` / `EIA_API_KEY` / `KALSHI_API_KEY_ID` patterns.

**Pricing**: Basic tier $100/month. Includes:
- 10,000 post reads per month (333/day average)
- 50,000 post writes (irrelevant — read-only)
- Tweets-by-user endpoint, search recent endpoint, user lookup endpoint

**Endpoints we use**:
- `GET /2/users/by/username/{handle}` — resolve handle to user_id (one-time per handle)
- `GET /2/users/{id}/tweets` — get user's recent tweets with pagination, engagement metrics, language metadata
- `GET /2/tweets?ids=...` — batch tweet lookup for verification

**Rate limits**:
- Tweets-by-user: 1500/15min for Basic (more than enough)
- Search recent: 300/15min for Basic

**Read budget**: 100 handles polled daily at avg 3 tweets/day = ~300/day = ~9000/month. Comfortable margin within 10K limit. Higher-importance handles can be polled twice daily without breaching.

### 3.2 Why Not the Existing Grok Script

The existing Grok integration at `/Users/arjundivecha/Dropbox/AAA Backup/A Working/Grok/Grok.py` was evaluated and rejected as a foundation:

- The script makes a vanilla chat completion to `grok-4.3` (a model that doesn't appear in xAI's public catalog) with no `search_parameters` or tool-use enabled. The model lacks live X access in this configuration and fabricates plausible-looking tweet content with placeholder snowflake IDs (verifiable: `1923456789012345678` through `...82` recur identically across multiple markets in the May 8 output).
- LLM-synthesized "tweet content" is downstream of the model's training distribution, not the actual X corpus. It carries the same correctness risk that produced the "Rihanna album before GTA VI" Polymarket failure.
- Even with Grok's Live Search properly enabled (`search_parameters={"mode": "on", "sources": [{"type": "x"}]}`), output is filtered through Grok's interpretation layer. Direct X API access is more verifiable and more reproducible.

Direct X API integration is non-negotiable for this layer.

---

## 4. Curated Handle Registry

### 4.1 Registry File: `config/social_handles.yaml`

Hand-maintained YAML, parallel to `predmkt_curated.yaml` and `event_log_seed.yaml`. Single source of truth for which accounts ASADO tracks.

Schema:

```yaml
- handle: jeromehpowell
  user_id: ""                    # populated by the puller on first resolve, then cached
  full_name: "Jerome H. Powell"
  country: "U.S."                # T2 country name; off-universe accounts use null + tags
  tags: ["fed", "monetary_policy"]
  role: central_bank             # see role taxonomy §4.3
  importance: high               # high | medium | low
  language: en                   # primary language ISO 639-1
  active_since: "2018-02-05"     # role start; useful for backfill scope
  notes: "Fed Chair. Tweets are rare but pivotal. Track for FOMC pivot signals."
  poll_frequency: daily          # daily | weekly | monthly (ties to read budget)
  is_active: true
```

### 4.2 Initial Seed (~95 handles)

Composition by role:

| Role | Count | Notes |
|---|---|---|
| `central_bank` | 25 | Fed (Powell + 4 regional), ECB (Lagarde + DE/FR/IT/NL governors), BoE, BoJ, PBoC, RBI, BCB, Banxico, CBRT, BoK, RBA, BoC, BI, SNB, SAMA |
| `finance_minister` | 15 | US Treasury Secretary, UK Chancellor, Eurozone finmins, Japan, China, India, Brazil, Mexico, Turkey, Saudi finance ministers |
| `trade_official` | 8 | USTR, EU Trade Commissioner, China Commerce, India Commerce, Mexico SE, Brazil MDIC |
| `journalist_macro` | 20 | Bloomberg/Reuters/FT/WSJ macro and rates correspondents per region (US, EU, Asia, EM) |
| `journalist_local` | 12 | Caixin (China), Nikkei (Japan), Reforma (Mexico), Folha (Brazil), Hurriyet (Turkey), Times of India, Korea Herald — local-language journalists who break stories before international wires |
| `ceo_exporter` | 10 | Saudi Aramco, Petrobras, Vale, BHP, Rio Tinto, TSMC, Samsung Electronics, Hyundai, Maersk, Toyota leadership where active on X |
| `analyst_macro` | 5 | Named market-moving analysts whose calls are tradeable signal |

### 4.3 Role Taxonomy

Constrained vocabulary, enforced at YAML load:

| Role | Description |
|---|---|
| `central_bank` | Central bank governors, deputy governors, chief economists, regional Fed presidents |
| `finance_minister` | Finance/Treasury ministers and their press offices, Treasury Secretary, deputy/assistant secretaries with public mandate |
| `trade_official` | USTR, trade commissioners, commerce/industry ministers, customs officials |
| `political_executive` | Heads of state and finance/economy advisors when they tweet on policy (e.g., White House CEA chair) |
| `journalist_macro` | International macro/rates/EM correspondents at Bloomberg, Reuters, FT, WSJ, Nikkei Asia |
| `journalist_local` | Local-language financial journalists at major regional outlets |
| `ceo_exporter` | CEOs / chairmen of major exporters or market-moving companies in T2 country indices |
| `analyst_macro` | Named market analysts whose published calls have demonstrated market impact |
| `regulator` | SEC chair, CFTC chair, ESMA, regulatory bodies that move markets |

Roles outside this list require explicit registry update.

### 4.4 Importance Tiers

Importance drives polling cadence and LLM-classification confidence weighting:

| Tier | Polling | Read budget |
|---|---|---|
| `high` | Daily | ~30 handles × 5 tweets/day = 150/day |
| `medium` | Every 2 days | ~50 handles × 3 tweets every 2 days = ~75/day |
| `low` | Weekly | ~15 handles × 2 tweets/week = ~5/day |

Total: ~230/day = ~6900/month. Comfortable within Basic tier 10K/month with 30% headroom.

### 4.5 Country Coverage Discipline

Hard requirement: every T2 country must have ≥1 tracked handle. Off-universe entities (Iran, Russia, Israel, Pakistan, Argentina) should have ≥1 tracked journalist or political-executive handle each. The registry validation script enforces this.

The "≥30% non-English-language source" requirement is also enforced — preventing the registry from drifting into an English-only echo chamber.

---

## 5. Schema Design

### 5.1 Fact Table: `social_events`

One row per ingested tweet. The single most-queried table in this layer.

```sql
CREATE TABLE social_events (
    tweet_id              VARCHAR PRIMARY KEY,    -- X snowflake ID, verified 18-19 digit
    handle                VARCHAR NOT NULL,
    handle_country        VARCHAR,                -- T2 country or null for off-universe
    handle_role           VARCHAR NOT NULL,       -- from role taxonomy §4.3
    handle_importance     VARCHAR NOT NULL,       -- high | medium | low
    posted_ts             TIMESTAMP NOT NULL,
    posted_date           DATE NOT NULL,          -- denorm for indexing
    text                  VARCHAR NOT NULL,       -- raw tweet text (may be non-English)
    language              VARCHAR,                -- ISO 639-1, from X metadata
    likes                 INTEGER,
    retweets              INTEGER,
    replies               INTEGER,
    impressions           INTEGER,                -- when available
    url                   VARCHAR NOT NULL,       -- canonical https://x.com/<handle>/status/<id>
    is_quote              BOOLEAN DEFAULT FALSE,
    quoted_tweet_id       VARCHAR,                -- if is_quote = true
    is_reply              BOOLEAN DEFAULT FALSE,
    in_reply_to_handle    VARCHAR,
    
    -- Classification (LLM-derived; nullable until classified)
    relevance_score       DOUBLE,                 -- 0..1
    matched_categories    VARCHAR,                -- JSON array of event_log category strings
    matched_subcategories VARCHAR,                -- JSON array of subcategory hints
    suggested_label       VARCHAR,                -- 1-line event_log label proposal
    suggested_severity    VARCHAR,                -- 'high' | 'medium' | 'low'
    classification_rationale VARCHAR,             -- 1-2 sentences
    classifier_model      VARCHAR,                -- e.g., 'claude-haiku-4-5-20251001'
    classified_ts         TIMESTAMP,
    
    -- Promotion lifecycle
    queue_status          VARCHAR DEFAULT 'unclassified',
                                                  -- 'unclassified' | 'pending_review'
                                                  -- | 'queued' | 'promoted' | 'rejected' | 'noise'
    promoted_event_id     VARCHAR,                -- FK to event_log.event_id when accepted
    rejected_reason       VARCHAR,                -- for analytics on classifier accuracy
    reviewed_by           VARCHAR,                -- 'manual' | 'auto'
    reviewed_ts           TIMESTAMP,
    
    -- Provenance
    pulled_ts             TIMESTAMP NOT NULL,
    pull_source           VARCHAR DEFAULT 'x_api_v2'
);

CREATE INDEX idx_social_posted_date ON social_events(posted_date);
CREATE INDEX idx_social_handle ON social_events(handle);
CREATE INDEX idx_social_relevance ON social_events(relevance_score) WHERE relevance_score IS NOT NULL;
CREATE INDEX idx_social_queue_status ON social_events(queue_status);
```

Volume: 230 tweets/day × 365 days = 84K rows/year. Trivial scale.

### 5.2 Handle Dimension: `social_handles`

Materialized from YAML on each puller run. Loaded by the puller for fast handle-lookup; a join target for downstream analytics.

```sql
CREATE TABLE social_handles (
    handle                VARCHAR PRIMARY KEY,
    user_id               VARCHAR,                -- X-side user ID (cached after first resolve)
    full_name             VARCHAR,
    country               VARCHAR,
    role                  VARCHAR NOT NULL,
    importance            VARCHAR NOT NULL,
    language              VARCHAR,
    active_since          DATE,
    poll_frequency        VARCHAR DEFAULT 'daily',
    is_active             BOOLEAN DEFAULT TRUE,
    last_polled_ts        TIMESTAMP,
    last_tweet_ts         TIMESTAMP,
    tweets_pulled_total   INTEGER DEFAULT 0,
    tweets_promoted_total INTEGER DEFAULT 0,
    notes                 VARCHAR,
    tags                  VARCHAR                 -- JSON array
);
```

The `tweets_promoted_total / tweets_pulled_total` ratio gives a per-handle signal-quality metric over time. Handles consistently producing zero promoted events get flagged for registry review (probably false starts in the seed list).

### 5.3 Event Log Integration

When a tweet is promoted to `event_log`, the new event row carries:

- `event_id`: derived as `social_<role>_<handle>_<YYYYMMDD>_<short-hash>` (e.g., `social_central_bank_jeromehpowell_20260605_a3f2`)
- `event_date`: the tweet's `posted_date`
- `category`: from `matched_categories` (curator confirms)
- `subcategory`: from `matched_subcategories` (curator confirms)
- `severity`: from `suggested_severity` (curator confirms)
- `description`: 1–3 sentence curator-edited summary
- `source_url`: the tweet URL — directly verifiable
- `tags`: comma-separated, includes `social_signal,via_x,handle_<handle>` plus any topical tags
- `added_by`: `social_promoted` (distinct from `manual` so analytics can separate sources)

This means `events_in_window` queries naturally surface social-promoted events alongside hand-curated ones, and `event_window` event-study queries pick them up automatically.

---

## 6. Tweet Classification

### 6.1 Classifier Architecture

LLM-based per-tweet classifier. Single API call per tweet; no batching for V1 (simplicity > throughput at 230 tweets/day).

**Model choice**: Claude Haiku 4.5 (`claude-haiku-4-5-20251001`). Rationale:
- Cheap (~$0.001 per classification at typical tweet length)
- Fast (sub-second response)
- Strong multilingual capability — handles Mandarin, Korean, Turkish, Portuguese, Arabic, Spanish, Hindi without translation
- Structured-output reliability with JSON schema

Estimated cost: 230 tweets/day × $0.001 = $0.23/day = ~$7/month. Combined with X API Basic ($100/month) = ~$107/month. (Padded the original ~$145 estimate; actual is closer to ~$110.)

### 6.2 Classifier Prompt Structure

```
You are an event classifier for a country-rotation research platform.

Given:
- Handle: {handle}
- Handle role: {role} ({full_name}, {country})
- Tweet posted: {posted_ts}
- Tweet text: {text}
- Language: {language}

Determine whether this tweet announces or signals a market-moving event 
in any of these ASADO event categories:
{enumerated_categories_with_subcategories}

Subcategory list per category:
{enumerated_subcategories}

Return JSON with:
{
  "relevance_score": 0.0 to 1.0,
  "matched_categories": [list of category strings, may be empty],
  "matched_subcategories": [list of subcategory strings, may be empty],
  "suggested_label": "1-line event_log label, or empty string if no match",
  "suggested_severity": "high" | "medium" | "low",
  "rationale": "1-2 sentence explanation"
}

Calibration guidance:
- 0.9-1.0: Direct, definitive policy/decision announcement from a 
  decision-maker. Example: Powell announcing a rate cut.
- 0.7-0.9: Strong signal of imminent decision or material policy 
  guidance shift. Example: Lagarde signaling ECB stance change.
- 0.5-0.7: Notable commentary that could shift expectations but is 
  not itself an event. Example: Treasury Secretary commenting on dollar policy.
- 0.3-0.5: Topical commentary on existing situation. Example: journalist
  reporting on yesterday's CPI print.
- 0.0-0.3: Personal, off-topic, retweet of unrelated content, or noise.

Bias toward UNDER-classification. False negatives (missed events) are 
recoverable; false positives (noise promoted to event_log) corrupt 
downstream analytics.

If the tweet is in a non-English language, classify based on translated 
meaning but include the original text in your reasoning. Do not require 
translation — analyze in source language.
```

### 6.3 Promotion Thresholds

Classifier output is interpreted via fixed thresholds:

| Score | Queue Status | Action |
|---|---|---|
| ≥ 0.8 | `queued` | Auto-add to curation queue for human review |
| 0.5–0.8 | `pending_review` | Stored, surfaced via MCP `recent_social_signals` but not in active queue |
| < 0.5 | `noise` | Stored for analytics but not surfaced |

Curators promote queued tweets to `event_log` via a small CLI helper (described in §7.3).

### 6.4 Classifier Calibration Loop

Every 30 days, run a classifier-quality review:
- Sample 50 tweets across the relevance-score distribution
- Curator labels each as "would I promote this to event_log?"
- Compare labels to classifier scores
- Compute precision/recall at the 0.8 threshold
- Adjust threshold or refine prompt if precision <70% or recall <60%

This is the same calibration pattern as `predmkt_resolutions` — empirical refinement once enough labeled data exists.

---

## 7. Pipeline and Tools

### 7.1 Daily Puller Script: `scripts/build_social_events.py`

Daily cadence. Idempotent. Mtime-guarded. Backup-restore on failure (mirrors `build_predmkt_panel.py` patterns).

Workflow:

1. **Load registry** from `config/social_handles.yaml`. Validate against role taxonomy and country list.
2. **Resolve handles** to user_ids on first run (cached in `social_handles.user_id`).
3. **Determine polling targets** — only handles whose `last_polled_ts + poll_frequency_interval < now`.
4. **Pull tweets** — for each target handle, GET `/2/users/{id}/tweets` with `tweet.fields=created_at,public_metrics,lang,referenced_tweets`, `max_results=10`, paginated as needed.
5. **Filter to new** — tweets with `tweet_id` not already in `social_events`.
6. **Classify** — for each new tweet, invoke Claude Haiku classifier. Store result in `social_events` with `queue_status` set per §6.3.
7. **Update handles** — increment `tweets_pulled_total`, set `last_polled_ts`, `last_tweet_ts`.
8. **Write curation queue** — for tweets newly entering `queue_status='queued'`, append to `Data/curation_queue/social_events_<date>.json` for the curator.

CLI flags following the existing pattern:

```bash
python scripts/build_social_events.py              # daily run
python scripts/build_social_events.py --check      # validate registry, no API calls
python scripts/build_social_events.py --validate-only  # resolve all handles to user_ids, no pulls
python scripts/build_social_events.py --dry-run    # pull, classify, but no DB writes
python scripts/build_social_events.py --rebuild    # drop and recreate tables (dev only)
python scripts/build_social_events.py --no-backup
```

### 7.2 Wired into `monthly_update.py`

Insert as a new step **after** the daily panel build and **before** the prediction-markets build. The ordering reflects dependency direction: social_events references `event_log` categories but doesn't yet cross-reference `predmkt_*`, so it can run before predmkt_panel.

### 7.3 Curation CLI: `scripts/review_social_queue.py`

Small interactive helper for the curator. Walks the daily curation queue and prompts for accept/edit/reject per tweet. Approved tweets:
- Receive a generated `event_id`
- Get inserted into `event_log` with the metadata mapped per §5.3
- Get their `social_events.queue_status` updated to `promoted`
- Get their `social_events.promoted_event_id` populated

Rejected tweets:
- Get `queue_status` set to `rejected` with `rejected_reason` recorded

This script is a 1–2 hour build. It's the human-review surface that gates social → event_log promotion.

Expected daily review burden: 5–10 tweets at the 0.8 threshold = ~5 minutes/day. Acceptable for a high-leverage pipeline.

---

## 8. MCP Server Integration

Two new tools in `scripts/asado_mcp_server.py`:

### 8.1 `recent_social_signals(country=None, role=None, days_back=7, min_relevance=0.5, max_results=50)`

Surfaces recent classified tweets for downstream agent queries.

```python
@mcp.tool(description=(
    "Return recent tweets from tracked X handles that match ASADO event "
    "categories. Optional filters by country, role, recency, and minimum "
    "relevance. Includes tweets pending or queued for event_log promotion "
    "as well as already-promoted ones."
))
def recent_social_signals(
    country: str = None,
    role: str = None,
    days_back: int = 7,
    min_relevance: float = 0.5,
    max_results: int = 50,
) -> dict:
    ...
```

Returns: list of social_events rows with handle context, classification, promotion status.

### 8.2 `handle_event_history(handle, days_back=90, min_relevance=0.0, max_results=100)`

Returns the recent tweet history for a single handle. Useful for "what has the Saudi finance minister said in the last 90 days."

### 8.3 Schema Summary Update

`get_schema_summary` adds:
- The new `social_events` and `social_handles` tables with row counts and date ranges
- A note that promoted social events appear in `event_log` with `tags LIKE '%social_signal%'`

### 8.4 Planner Awareness

The `ask_asado` planner prompt is updated to recognize:
- Queries about specific named officials → route to `handle_event_history` first
- Queries about "what is X saying recently" → route to `recent_social_signals` with appropriate filters
- Queries about events triggered by specific people → join `event_log` filtered on `tags LIKE '%handle_<x>%'` with `event_window`

---

## 9. Failure Modes and Containment

| Risk | Mode | Containment |
|---|---|---|
| Hallucinated tweets | LLM generates fake content (Grok-script failure mode) | Direct X API only. Verify post IDs are 18-19 digit snowflakes. Reject any without an HTTPS-verified URL. |
| Account compromise | Tracked handle hacked, posts garbage | All promotions go through human review (curation queue). Auto-promotion is explicitly disabled in V1. Compromised tweet would be rejected at review. |
| Bot/coordinated inauthentic | Not applicable | Whitelist of known accounts obviates this. Any drift in registry curation requires explicit YAML edits. |
| Classifier false positives | LLM scores irrelevant tweets ≥0.8 | Human review at curation queue catches. Calibration loop §6.4 refines threshold over time. |
| Classifier false negatives | LLM misses real events | Stored in social_events at lower scores; curator can promote retroactively via `promote_event_id` MCP tool (V1.5 enhancement) or directly in DB. Less harmful than false positives. |
| X API outage | Daily run fails | Idempotent puller — next day's run catches up. Alert if any handle hasn't been polled in >7 days. |
| X API tier exhaustion | Read budget exceeded | Daily counter logged. Alert at 80% of monthly limit. Auto-throttle low-importance polling if approaching limit. |
| Cost overrun | Spend grows unexpectedly | Monthly cost monitor; cap LLM classification spend at $50/month with hard stop. |
| Registry bias | Drift toward English-only sources | Validation requires ≥30% non-English handles. ≥1 handle per T2 country mandatory. |
| Multilingual classifier degradation | Haiku misclassifies non-English | Calibration loop §6.4 stratified by language; if non-English precision drops below 60% at threshold, escalate to Sonnet for those languages. |
| event_log drift | Social signals dilute hand-curated event_log quality | `added_by='social_promoted'` flag separates sources. Filters available on every query. Quarterly review of social-promoted events for quality. |

---

## 10. Build Plan (~5 working days)

### Day 1: Foundations

- Schema for `social_events` and `social_handles` tables, with indexes
- Skeleton `scripts/build_social_events.py` with idempotency, backup, failure handling
- Registry YAML schema and validation logic
- X API auth helper (`scripts/_x_auth.py`) handling Bearer Token from env

### Day 2: Curation Registry

- Hand-curate the ~95-handle seed across roles, importance, country coverage
- Verify each handle exists on X via `/2/users/by/username/{handle}` resolve
- Document language, role, country per entry
- Run validation: ≥1 handle per T2 country, ≥30% non-English

This is the real intellectual work — same pattern as the prediction-markets curation. Expect 1 full day of focused effort.

### Day 3: Puller + Classifier

- X API puller: pagination, rate-limit handling, dedup by tweet_id
- Claude Haiku classifier with structured-output prompt
- Per-tweet classification flow with score/categories/severity
- Curation queue file format and write logic
- End-to-end test: pull 10 tweets, classify, write queue file

### Day 4: MCP Tools + Curation CLI

- `recent_social_signals` and `handle_event_history` MCP tools
- `scripts/review_social_queue.py` interactive curation helper
- `event_log` insertion logic with proper `added_by`, `source_url`, `tags`
- Schema summary update
- `ask_asado` planner prompt update

### Day 5: Integration + Testing

- Wire into `monthly_update.py` orchestrator
- Smoke tests: 7-day end-to-end run with all tracked handles
- Update README with new tables, tools, scripts, env vars
- Update CLAUDE.md / AGENTS.md with social-events planning patterns
- First curation review session — confirm queue surfaces sensible events

### Acceptance Criteria

1. Registry has ≥50 handles with ≥1 per T2 country and ≥30% non-English-language sources.
2. Daily puller runs cleanly for 7 consecutive days without manual intervention.
3. Every row in `social_events` has a verifiable URL that loads to a real X post (sample-checked, not API-verified at insert time).
4. Classifier produces non-degenerate scores — distribution spans 0.0–1.0, not bimodal at extremes.
5. Curation queue surfaces 3–10 tweets/day at the 0.8 threshold over a 7-day average.
6. ≥1 curator review session results in ≥1 promotion to `event_log`, with the promoted event correctly findable via `events_in_window` and `event_window` chains.
7. New MCP tools `recent_social_signals` and `handle_event_history` return expected results for tested queries.
8. README updated; env var `X_BEARER_TOKEN` documented; secret never committed.

---

## 11. Open Questions

1. **Should we backfill?** X API allows historical pulls within recent windows (typically ~1 week for free, longer for paid tiers). Recommendation: **no backfill in V1**. Start ingestion on Day 5; let history accumulate forward. Rationale: backfill complicates the puller's idempotency, and 4–6 weeks of forward history is enough to validate the layer.

2. **Auto-promotion for highest-importance handles?** A tweet from Powell saying "we will continue to be patient" arguably *is* the event — could it skip human review? Recommendation: **no auto-promotion in V1**. The 5-minute review burden is small; the protection against compromised accounts and classifier surprises is large. Revisit after 3 months of operation if review backlog becomes consistently noisy.

3. **What about Truth Social, Bluesky, Threads?** Trump posts on Truth Social; some EU officials post on Bluesky. Recommendation: **X-only for V1**. Add other platforms only after Layer 1 is operational and value is demonstrated. The architecture (handle registry + per-platform puller + shared classifier + shared queue) extends naturally.

4. **Should `social_events` link to `predmkt_market_meta`?** A Treasury Secretary tweet about tariffs is relevant to the curated tariff-escalation prediction markets. Recommendation: **not in V1**. Adding cross-references requires another curation surface. In V2, consider a `tags` field linking social events to predmkt market_ids when they bear on the same outcome.

5. **What about retweets of tracked accounts?** If Yellen retweets the BLS jobs report, is that itself an event? Recommendation: **track but downweight in V1**. Mark `is_retweet=true` on the row; classifier sees this and tends to score lower. Don't spend time on retweet-thread-expansion.

6. **Sentiment scoring on top of event classification?** Some tweets have direction (hawkish/dovish, supportive/critical) beyond their event-detection signal. Recommendation: **out of scope for V1**. The event_log doesn't carry sentiment; adding it here breaks abstraction. If valuable, build as Layer 2 separate signal.

7. **Multilingual classifier reliability**. Specifically Mandarin, Korean, Hindi, Turkish, Arabic, Portuguese — does Haiku 4.5 actually classify these well? Recommendation: **calibrate empirically per language in week 4**. If reliability is bad for any language, escalate to Sonnet for that language only (factor of ~10 cost difference, still affordable at this volume).

8. **Cost discipline if X raises Basic tier price**. X has a history of pricing changes. Recommendation: **monthly review of read-budget vs. tier**. If pricing forces a tier change, downgrade to a smaller, higher-quality handle list (~30 handles polled daily) before paying enterprise.

9. **Curation refresh cadence**. The 95-handle list will rot — people change roles, leave organizations, become less relevant. Recommendation: **quarterly curation review** alongside the existing event_log curation pass. Add `last_validated_date` field to `social_handles` and surface stale entries.

---

## 12. Out of Scope (Explicit)

- General Twitter/X sentiment scoring (Layer 2 — separate PRD if pursued)
- Daily LLM-generated tweet summaries per market (the Grok script's pattern; explicitly rejected)
- Bot detection and coordinated-inauthentic-behavior surfacing
- Real-time streaming or sub-daily polling
- Trading on tweet content
- Reply-thread expansion beyond first-level
- Cross-platform expansion (Truth Social, Bluesky, Threads) before V1 is operational
- Translation as a separate intermediate step (LLM classifier handles multilingual natively)
- Auto-promotion of tweets to event_log without human review

---

## 13. References

- `PRD_Event_Log.md` — event_log spec; this layer feeds into it
- `PRD_Stage2_Prediction_Markets.md` — the curation-queue + human-in-the-loop pattern this PRD mirrors
- `PRD_Event_Log_Quality_Pass.md` — the discipline of source-URL requirements; same standard applied here
- `/Users/arjundivecha/Dropbox/AAA Backup/A Working/Grok/Grok.py` — the existing Grok script; rejected as a foundation per §3.2
- May 9 2026 conversation — origin of the failure-mode analysis and the Layer 1 / Layer 2 split

---

*End of PRD*
