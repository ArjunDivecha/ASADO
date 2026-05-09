# PRD: Prediction Markets Ingestion & Signal Layer
## ASADO Daily Panel Extension — Stage 2

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Date** | 2026-05-08 |
| **Author** | Arjun Divecha (with Claude) |
| **Status** | Draft for review |
| **Depends on** | `build_daily_panels.py` (Stage 1 — T2 + GDELT daily) |
| **Companion to** | `PRD_ASADO_Natural_Language_Query_Layer.md`, `PRD_Strategy_01_WorldState_Analogs.md`, country rotation autoresearch system |
| **Estimated effort** | 4–6 weeks |

---

## 1. Context and Motivation

ASADO currently aggregates 1,925+ factor variables across 34 countries from Bloomberg, IMF, BIS, OECD, FRED, and a 92-factor GDELT zoo. The Stage 1 daily extension adds T2 daily factors (109 normalized + 57 raw level series) and the 249-country GDELT raw signal panel. Every variable in this stack is **backward-looking** — observed prints with publication lags from one trading day (prices) to one quarter (BIS bilateral).

The Iran-war analysis exercise on 2026-05-08 surfaced four specific failures of this backward-looking architecture:

1. **No real-time conditional probability of the event itself.** When asking "who benefits from the Iran war," the system could only read consequences in equity returns and GDELT tone. There was no ability to read the market-priced probability of escalation, ceasefire, regime fall, or oil-supply disruption at any specific horizon at any specific moment.

2. **No off-universe entity coverage.** Iran is not in T2's 34-country panel. Russia, Israel, Egypt, Pakistan, Argentina aren't either. The off-universe-entity bridge needs a primary data source for non-T2 entities. Prediction markets are exactly that source for the most consequential off-universe events.

3. **No forward-looking macro distribution.** The current macro layer carries observed CPI, observed Fed funds rate, observed unemployment. It does not carry the market-implied distribution over the *next* CPI print, the *next* FOMC decision, or the *next* unemployment report. Bloomberg consensus is reproduced in this dataset; its continuously-updating prediction-market analog is not.

4. **No real-time policy / political-risk surface.** Tariff escalation, election outcomes, regime stability, sanctions decisions — historically reasoned about narratively. Continuously-priced binary and multi-outcome contracts on each give a quantitative time series usable as factor inputs.

The Federal Reserve has independently validated the macro use case. Their February 2026 staff working paper "Kalshi and the Rise of Macro Markets" (FEDS 2026-010) documents that Kalshi's federal-funds-rate distributions match professional forecaster mean absolute error 150 days out, achieve a perfect record on the day before each FOMC meeting, and provide continuously-updating *full distributions* — a feature the FRBNY Survey of Market Expectations cannot match. CPI and unemployment forecasts statistically tie Bloomberg consensus. This is the strongest external endorsement available for the data quality of the macro side.

The geopolitical side is less rigorously validated but materially significant: $382M of cumulative Polymarket volume on Iran markets alone, $9.7B 30-day Polymarket volume, $14.9M on a single WTI strike market, $284M on a single FOMC decision market. These are not toy markets.

This PRD specifies a Stage 2 extension to ASADO that ingests prediction-market data from Kalshi and Polymarket, normalizes it into the existing tidy-long schema, hand-curates a high-relevance market set with country-spillover mappings, and exposes derived composite signals through the ASADO MCP layer.

---

## 2. Goals and Non-Goals

### Goals

- **G1.** Ingest daily snapshots of curated Kalshi and Polymarket markets into `asado.duckdb` following the same `(date, country/entity, value, variable)` convention used by `t2_factors_daily` and `gdelt_factors_daily`.

- **G2.** Hand-curate ~150–250 markets across both platforms categorized by ASADO-native taxonomy (`oil_shock`, `fed_policy`, `cpi`, `recession`, `regional_conflict`, `tariff`, `regime_change`, `country_election`) with hand-mapped spillover-country elasticities for the off-universe-entity bridge.

- **G3.** Materialize 8–12 daily composite signals (e.g., `oil_shock_prob_30d`, `fed_cut_distribution_next`, `cpi_nowcast`, `regional_conflict_premium_middle_east`, `tariff_intensity_by_country`) usable as direct inputs to country rotation, the T2 factor timing system, and the LoopPilot autoresearch loop.

- **G4.** Expose the new layer through ASADO's MCP server with three new tools: `predmkt_snapshot`, `country_signal_now`, and `event_market_set`.

- **G5.** Build a calibration-tracking subsystem that logs every market resolution and computes ongoing accuracy by category. The signal layer is weighted by historical reliability rather than treated as uniformly trustworthy.

- **G6.** Maintain a hand-curated event log linking notable real-world events to the markets that priced them, for event-study replay (`event_window` tool from Stage 1 plus prediction-market context).

### Non-Goals

- **NG1.** Trading. Read-only data ingestion only. No Kalshi or Polymarket trading account.
- **NG2.** Sports markets. Despite being 87% of Kalshi March volume, irrelevant to country rotation or factor timing.
- **NG3.** Pop-culture, entertainment, and personality markets. Same reasoning.
- **NG4.** Crypto-asset price markets. Duplicate spot data already accessible from Bloomberg.
- **NG5.** Replacing existing macro sources. Prediction markets are *additive* to FRED, Bloomberg consensus, and the factor zoo — not substitutes.
- **NG6.** Execution-grade realtime feeds. Daily snapshots are sufficient for daily-cadence factor timing. An optional 5-min intraday subsystem is described in §11 as a Phase E enhancement.
- **NG7.** Internalizing the trading logic of these markets. We are consumers of the implied probabilities, not market microstructure researchers.

---

## 3. Data Sources

### 3.1 Kalshi

**Endpoint base**: `https://trading-api.kalshi.com/trade-api/v2/`

**Auth model**: Public read-only endpoints (`/markets`, `/events`, `/series`, `/markets/{ticker}/candlesticks`, `/markets/{ticker}/orderbook`) require **no authentication**. Only trading and account endpoints require credentials. ASADO ingestion is read-only and therefore unauthenticated.

**Rate limits**: ~10 req/s for unauthenticated traffic, no documented daily cap. Daily snapshot of ~1,000 active markets fits comfortably in <2 minutes.

**Data hierarchy**:
- **Series** (e.g., `KXFEDDECISION`) — a recurring contract template
- **Event** (e.g., `KXFEDDECISION-26APR`) — a specific instance
- **Market** (e.g., `KXFEDDECISION-26APR-T3.50`) — a specific strike or yes/no outcome under that event

**Stable identifiers**: `series_ticker`, `event_ticker`, `market_ticker`. These do not change across the market's lifetime.

**Time series**: `/markets/{ticker}/candlesticks` returns OHLC of price (in cents, 0–99) at 1-minute, 1-hour, 1-day resolution back to market open. Settled markets carry `settle_value` and `result`.

**Regulatory status**: CFTC-regulated DCM, FDIC insurance up to $250K. The "Kalshi is the regulated US event-contract exchange" framing is real and matters for institutional acceptance of the data.

**Coverage gaps**: Kalshi is shallower on geopolitical breadth than Polymarket — fewer Iran-specific markets, fewer regime-change markets. Strong on US macro, US politics, weather, and CFTC-approved economic series.

### 3.2 Polymarket

**Endpoints**: Two APIs that split the work.
- **Gamma API** at `https://gamma-api.polymarket.com/` — market metadata, slugs, categories, event groupings, descriptions, resolution rules
- **CLOB API** at `https://clob.polymarket.com/` — order books, prices, trades, the `prices-history` endpoint for time series

**Auth model**: Read endpoints are public, no key required. Trading requires Polygon wallet auth, out of scope for this PRD.

**Rate limits**: Soft. ~50 req/s comfortable. Polymarket also operates a public subgraph (The Graph) over Polygon for blockchain-backed historical state; useful as a backfill source.

**Stable identifiers**: `condition_id` (per market) and `token_id` (per outcome within a multi-outcome market). `slug` is human-readable but can change; do not rely on it for joins.

**Time series**: `prices-history` endpoint takes `(token_id, startTs, endTs, interval, fidelity)`. Native API only returns ~30 days of history at fine granularity; older history requires either the subgraph or a third-party archive.

**Coverage strength**: Geopolitics breadth. 569 active markets in Geopolitics, 741 in World Events, 188 in the Iran category alone. The 249-country regime/election coverage is the off-universe-entity bridge's primary substrate.

**Coverage gaps**: Resolution semantics on geopolitical markets are sometimes ambiguous ("ceasefire", "regime fall" definitions). Each market's rules section must be read once during curation; ambiguous-resolution markets are flagged for downweighting.

### 3.3 Optional Historical Archives

For backfilling Polymarket history beyond ~30 days, three options:

- **Dome** (YC W25, `polymarketdata.co` adjacent) — unified API across Polymarket and Kalshi, S3 bulk export, Python SDK. Pricing not public; suitable for institutional integration.
- **FinFeedAPI** — REST + JSON-RPC across Polymarket, Kalshi, Manifold, Myriad. OHLCV time series, order books. Has a free tier.
- **polymarketdata.co** — high-granularity Polymarket order-book and price archive, S3 + REST + Python SDK.

Recommendation: start live-only (no historical backfill) for V1, evaluate FinFeedAPI free tier in Phase B if backfill becomes critical for calibration analysis. Avoid paid third parties until use cases justify cost.

### 3.4 Comparison and Selection

| Dimension | Kalshi | Polymarket |
|---|---|---|
| Macro / Fed / CPI | **Strong** | Moderate |
| Geopolitics breadth | Moderate | **Strong** |
| Regulatory clarity | **CFTC** | Crypto-native |
| API ergonomics | Clean REST + FIX | Two-API split, subgraph |
| Volume in macro | $284M+ on FOMC | $112M+ on Fed Rates |
| Volume in geopolitics | Moderate | $382M+ on Iran alone |
| Auth for data | None | None |
| Historical depth | Full via candlesticks | ~30d via API; subgraph for more |
| Resolution rigor | High (CFTC-mandated) | Variable; review per market |

**Decision**: Ingest **both**. They are complementary, not substitutes.

---

## 4. Coverage Scope

### 4.1 Categories to Ingest

The ASADO-native category taxonomy below maps each market to a single primary category. Markets with multiple plausible categorizations (e.g., a tariff market that also touches a country election) carry one primary plus optional secondary tags.

| ASADO Category | Description | Example markets | Primary platform |
|---|---|---|---|
| `fed_policy` | Federal funds rate decisions, distributions, Fed Chair confirmation | Fed decision in April, How many cuts in 2026, Fed Chair confirmation | Both, Kalshi distributions richer |
| `cpi` | CPI MoM/YoY, Core CPI, PCE, Core PCE prints | KXCPI, KXACPI, KXPCECORE, monthly resolutions | Kalshi |
| `unemployment` | NFP, unemployment rate, jobless claims | KXUNEMP, KXNFP | Kalshi |
| `gdp_recession` | GDP growth, recession declaration | KXRECESSION, KXGDP, recession-by-year | Both |
| `oil_shock` | WTI/Brent strike markets, Strait of Hormuz traffic, oil cap | "Will WTI hit X by date", Hormuz returns to normal | Polymarket dominant |
| `commodity` | Gold, copper, silver, ag commodity strikes | Kalshi Commodities Hub, Polymarket COMEX silver | Both |
| `tariff` | US tariff impositions, tariff agreements, trade deals | Trump-China visit, tariff refund, deals with Mexico/Canada/India | Polymarket dominant |
| `trade_war` | Broader US-China-EU trade dynamics | Trump-Xi visit, China decoupling | Polymarket |
| `regional_conflict_me` | Iran/Israel/Hormuz/Saudi-related conflict markets | US x Iran ceasefire, Iran regime, Hormuz traffic | Polymarket |
| `regional_conflict_pacific` | China-Taiwan, China-Japan, Korean peninsula | China x Taiwan military clash before 2027 | Polymarket |
| `regional_conflict_eastern_europe` | Russia-Ukraine ceasefire, NATO escalation | Russia-Ukraine ceasefire, NATO Article 5 | Polymarket |
| `regime_change` | Specific leader exit, government collapse | Khamenei out by date, Maduro out, Venezuela leader | Polymarket |
| `country_election` | National election outcomes for non-US countries | Taiwan presidential, UK local, Brazil 2026, Canadian federal | Both |
| `us_politics` | Trump executive actions, US elections, court rulings | Tariff court ruling, Trump-China visit | Polymarket dominant |
| `crypto_macro` | Stablecoin regulation, Bitcoin ETF flows — only when policy-relevant | (selective) | Polymarket |

### 4.2 Curation Policy

Curation is a one-time hand-effort to identify the ~150–250 highest-relevance markets, plus a quarterly refresh.

**Inclusion criteria** (any one suffices):
1. ≥$50K cumulative volume **and** category in §4.1
2. Direct mapping to a T2 country (Taiwan election, Brazil election, India tariff deal)
3. Macro indicator with CFTC-approved resolution source (all Kalshi macro markets default qualify)
4. Off-universe-entity bridge value (any Iran/Russia/Israel/Ukraine market with ≥$10K volume)

**Exclusion criteria**:
1. Sports, entertainment, single-celebrity culture markets
2. Markets with ambiguous resolution ("X happens" with subjective definition) unless category is otherwise critical
3. Cumulative volume <$10K **and** no T2/off-universe linkage

**Curation deliverable**: a YAML or CSV registry checked into the ASADO repo:

```yaml
- market_id: "0x1234..."
  platform: polymarket
  asado_category: regional_conflict_me
  asado_subcategory: hormuz_disruption
  spillover_countries:
    - country: Saudi Arabia
      elasticity: +0.7   # signed, ~standardized to typical 1-month return-shock units
      channel: oil_export
      confidence: high
    - country: Japan
      elasticity: -0.4
      channel: oil_import_dependency
      confidence: high
    - country: Korea
      elasticity: -0.3
      channel: oil_import_dependency
      confidence: medium
  resolution_clarity: high
  notes: "Resolves on official IMO maritime traffic data."
```

This file is the source of truth for the spillover graph and is regenerated/updated quarterly.

### 4.3 Liquidity Gating

Two distinct liquidity treatments.

**Raw layer**: Daily mid-price recorded for every curated market regardless of liquidity. Stale markets (no trades in >24h or 24h volume <$1K Polymarket / <$500 Kalshi) flagged with `is_stale=TRUE`.

**Composite layer**: Composite signals (§7) are liquidity-weighted. Each constituent market contributes weight ∝ `min(24h_volume_usd, liquidity_usd)` capped at a category-specific ceiling. Stale markets contribute zero weight.

This avoids the failure mode where a $200-volume tail market dominates a composite during a low-traffic week.

---

## 5. Schema Design

Three layers — fact, dimension, derived — analogous to the Stage 1 daily panel structure.

### 5.1 Fact Table: `predmkt_daily`

The single most-queried table. One row per `(snapshot_date, market, outcome)`.

```sql
CREATE TABLE predmkt_daily (
    snapshot_ts          TIMESTAMP,        -- exact UTC capture time
    snapshot_date        DATE,             -- trading-day grain for joins
    platform             VARCHAR,          -- 'kalshi' | 'polymarket'
    market_id            VARCHAR,          -- platform-stable id
    outcome_id           VARCHAR,          -- token_id (Polymarket) / market_ticker (Kalshi)
    probability          DOUBLE,           -- mid-price 0..1
    bid                  DOUBLE,           -- best bid
    ask                  DOUBLE,           -- best ask
    spread_bps           DOUBLE,           -- (ask - bid) * 10000
    last_traded_price    DOUBLE,
    last_traded_ts       TIMESTAMP,
    volume_24h_usd       DOUBLE,
    volume_total_usd     DOUBLE,
    liquidity_usd        DOUBLE,
    open_interest_usd    DOUBLE,           -- Kalshi only; NULL for Polymarket
    is_stale             BOOLEAN,          -- flagged per §4.3
    is_resolved          BOOLEAN,
    resolution_value     DOUBLE,           -- 0 or 1 for binaries; NULL until resolved
    PRIMARY KEY (snapshot_date, platform, market_id, outcome_id)
);
CREATE INDEX idx_predmkt_daily_snapshot_date ON predmkt_daily(snapshot_date);
CREATE INDEX idx_predmkt_daily_market ON predmkt_daily(platform, market_id);
```

Daily volume estimate: ~250 markets × ~3 outcomes avg × 1 snapshot/day = ~750 rows/day = ~275K rows/year. Trivial scale.

### 5.2 Dimension Tables

**`predmkt_market_meta`** — one row per market, slowly changing.

```sql
CREATE TABLE predmkt_market_meta (
    market_id            VARCHAR,
    platform             VARCHAR,
    series_id            VARCHAR,          -- Kalshi series_ticker, Polymarket event_id
    title                VARCHAR,
    slug                 VARCHAR,
    rules_text           VARCHAR,          -- truncated to 4KB
    rules_url            VARCHAR,
    resolution_source    VARCHAR,          -- e.g., 'CME settlement', 'BLS CPI release'
    resolution_clarity   VARCHAR,          -- 'high' | 'medium' | 'low'
    asado_category       VARCHAR,
    asado_subcategory    VARCHAR,
    contract_type        VARCHAR,          -- 'binary' | 'scalar' | 'multi_outcome'
    open_ts              TIMESTAMP,
    close_ts             TIMESTAMP,
    resolved_ts          TIMESTAMP,
    last_updated_ts      TIMESTAMP,
    PRIMARY KEY (platform, market_id)
);
```

**`predmkt_outcome_meta`** — one row per outcome under a market.

```sql
CREATE TABLE predmkt_outcome_meta (
    platform             VARCHAR,
    market_id            VARCHAR,
    outcome_id           VARCHAR,
    label                VARCHAR,          -- 'Yes', 'No', '$80-$90', candidate name
    threshold_low        DOUBLE,           -- for scalar/range markets
    threshold_high       DOUBLE,
    sort_order           INTEGER,
    PRIMARY KEY (platform, market_id, outcome_id)
);
```

**`predmkt_country_spillover`** — the off-universe-entity bridge. Hand-curated.

```sql
CREATE TABLE predmkt_country_spillover (
    platform             VARCHAR,
    market_id            VARCHAR,
    country              VARCHAR,          -- T2 country name (canonical)
    elasticity           DOUBLE,           -- signed; expected sensitivity
    channel              VARCHAR,          -- see §5.3
    confidence           VARCHAR,          -- 'high' | 'medium' | 'low'
    notes                VARCHAR,
    PRIMARY KEY (platform, market_id, country, channel)
);
```

### 5.3 Spillover Channel Taxonomy

Each spillover edge is tagged with a channel describing the transmission mechanism. Channels are also useful as filters: "show me all oil-export-channel exposures for Saudi Arabia."

| Channel | Description |
|---|---|
| `oil_export` | Country is a net oil exporter; positive shock → positive equity move |
| `oil_import_dependency` | Country is heavy net oil importer; positive oil shock → negative |
| `regional_proximity` | Geographic proximity to conflict zone; ambiguous-signed risk |
| `trade_partner` | Direct trade relationship with sanctioned/affected entity |
| `usd_beta` | Country's equity has high USD-strength sensitivity |
| `em_beta` | Country is a generic EM proxy for risk-on/off |
| `tech_supply_chain` | Semiconductor or critical tech supply chain exposure |
| `commodity_export` | Non-oil commodity exporter (Brazil ag, Chile copper, Australia iron) |
| `safe_haven` | Defensive: JPY, CHF, gold-correlated |
| `regional_proxy` | Country trades as a proxy for the off-universe entity's region |

Elasticities are calibrated on first pass by judgment, then refined empirically once we have ≥6 months of paired prediction-market move and equity return data.

### 5.4 Resolved Markets Archive

When a market resolves, its row in `predmkt_market_meta` is updated with `resolved_ts` and a corresponding row is written to:

```sql
CREATE TABLE predmkt_resolutions (
    platform             VARCHAR,
    market_id            VARCHAR,
    resolved_ts          TIMESTAMP,
    resolution_value     DOUBLE,           -- 0 or 1 for binaries; for scalars, the realized strike
    final_probability_24h_before  DOUBLE, -- for calibration
    final_probability_1h_before   DOUBLE,
    notes                VARCHAR,
    PRIMARY KEY (platform, market_id)
);
```

This table powers the calibration subsystem (§10).

### 5.5 Derived Signals: `predmkt_signals_daily`

```sql
CREATE TABLE predmkt_signals_daily (
    snapshot_date        DATE,
    signal_name          VARCHAR,          -- e.g., 'oil_shock_prob_30d'
    country              VARCHAR,          -- nullable for global signals
    value                DOUBLE,           -- composite probability or expectation
    n_markets            INTEGER,          -- how many constituent markets
    total_liquidity_usd  DOUBLE,
    confidence_score     DOUBLE,           -- 0..1, factors in calibration history
    constituent_markets  VARCHAR,          -- JSON array of market_ids
    PRIMARY KEY (snapshot_date, signal_name, country)
);
```

### 5.6 Variable Meta Integration

The `variable_meta` table from Stage 1 gets new entries for each composite signal:

```sql
INSERT INTO variable_meta VALUES
    ('oil_shock_prob_30d',        'predmkt_signals_daily', 'derived',  'D', NULL,  TRUE,  'predmkt_macro',    FALSE),
    ('fed_cut_count_expectation', 'predmkt_signals_daily', 'derived',  'D', NULL,  TRUE,  'predmkt_fed',      FALSE),
    ('cpi_nowcast_yoy',           'predmkt_signals_daily', 'derived',  'D', NULL,  TRUE,  'predmkt_cpi',      FALSE),
    -- etc.
;
```

This means a query like "show me all FOMC-relevant variables" through the existing variable_meta-aware tools naturally surfaces both the observed Bloomberg consensus and the prediction-market-implied distributions.

---

## 6. Ingestion Architecture

### 6.1 Daily Snapshot Job

A single Python script `scripts/build_predmkt_panel.py` analogous in structure to `build_daily_panels.py`. Idempotent, mtime-guarded, with backup-restore on failure.

**Workflow per run**:

1. **Load curation registry** from `config/predmkt_curated.yaml`. Fail loudly if missing.
2. **Pull Kalshi markets** via REST. For each curated Kalshi market, fetch current order book, last 24h candlesticks, volume. Build `predmkt_daily` rows.
3. **Pull Polymarket markets** via Gamma + CLOB. Same pattern.
4. **Detect resolutions** since last run. Write `predmkt_resolutions` rows. Update `predmkt_market_meta.resolved_ts`.
5. **Compute composite signals** per §7. Write to `predmkt_signals_daily`.
6. **Update `variable_meta`** for new signals.
7. **Run liquidity gating** to set `is_stale` flags.
8. **Drop expired markets** from active polling (still readable in history).

**Cadence**: Run once per UTC day at 23:55. Optionally re-run at 13:00 UTC (post-CPI release window) and 20:00 UTC (post-FOMC announcement window) on event days.

**Runtime estimate**: <5 minutes for full daily refresh, dominated by network. Polymarket Gamma API is the slowest leg.

### 6.2 Backfill Strategy

**V1 (Phase A–C)**: live-only. The ingestion starts when this PRD is implemented; we accumulate history forward. By the time §10 calibration analysis is meaningful (~6 months of resolutions), we'll have it.

**V2 (Phase D, optional)**: Polymarket subgraph backfill for high-priority markets back to their inception. Most curated geopolitical markets launched 2024–2025 so this is tractable. Kalshi candlesticks back to market open are free via API.

**V3 (Phase E, optional)**: paid third-party archive (FinFeedAPI free tier first, Dome if needed) for cross-platform historical normalization.

### 6.3 Failure Handling

Mirrors `build_daily_panels.py`:

- DuckDB backed up to `asado.duckdb.backup` before write
- Each platform pull wrapped in try/except; if Kalshi fails, Polymarket still proceeds
- Per-market failures logged but do not abort the run
- On full-run failure, backup restored
- Stale alarms: if any curated market hasn't been seen in 7 days, alert (probably platform-side change of market_id or resolution we missed)

### 6.4 Hosting

Run from the same Mac M4 Max where the rest of ASADO lives, scheduled via `launchd` or `cron`. No cloud infrastructure required. Outputs land in `/Data/asado.duckdb`. The MCP server picks up changes automatically since it queries the file directly.

If we later want intraday resilience, the puller is pure Python with no Mac-specific dependencies and can move to a small EC2 / Cloudflare Workers Cron instance in <1 day.

---

## 7. Derived Signals Layer

The composite signals in `predmkt_signals_daily` are the primary integration surface for downstream analytics. Twelve initial signals follow.

### 7.1 Macro Signals (no country dimension)

**`fed_cut_count_expectation`** — Expected number of 25bp Fed cuts over the next 12 months. Computed from the Polymarket "How many Fed rate cuts in 202X" multi-outcome market: ∑(outcome_count × probability). Currently: 0.55×0 + 0.185×1 + ... = expected cuts.

**`fed_decision_distribution_next`** — Probability distribution over the next FOMC outcome (no change / -25bp / -50bp / +25bp / +50bp). Pulled directly from Kalshi KXFEDDECISION-{nextmtg} market. Stored as a JSON blob in the `value` column for this signal (one of the few non-scalar signals).

**`cpi_nowcast_yoy_next`** — Market-implied YoY CPI for the next print, from Kalshi KXCPI ladder. Computed as ∑(strike_midpoint × probability) over the strike distribution.

**`cpi_nowcast_core_next`** — Same but for KXACPI Core CPI.

**`unemployment_nowcast_next`** — Same but for KXUNEMP.

**`recession_prob_12m`** — Composite of Polymarket and Kalshi 12-month-ahead recession markets, liquidity-weighted.

### 7.2 Geopolitical Signals (with regional dimension)

**`oil_shock_prob_30d`** — Composite probability that WTI breaches a stress threshold ($95+) in the next 30 days. Constituent markets: WTI strike markets, Hormuz disruption, Iran ceasefire breakdown, regional escalation. Volume-weighted.

**`hormuz_disruption_prob_90d`** — Probability of Strait of Hormuz traffic disruption in the next 90 days. Direct from Polymarket Hormuz markets, plus inference from Iran ceasefire timing markets.

**`regional_conflict_premium_middle_east`** — Composite "intensity" score combining Iran-Israel, Iran-US, Hormuz, regime-fall markets. Range 0–1.

**`regional_conflict_premium_pacific`** — Same for China-Taiwan, China-Japan, Korean peninsula markets.

**`regional_conflict_premium_eastern_europe`** — Same for Russia-Ukraine, NATO escalation, Russia-NATO direct conflict.

### 7.3 Trade / Tariff Signals (with country dimension)

**`tariff_intensity_by_country`** — Per T2 country, the market-implied probability of significant tariff escalation in the next 6 months. Indexed against Polymarket per-country tariff and trade-deal markets. Country-specific signal: emits one row per (date, country).

### 7.4 Country-Level Signals (via spillover graph)

For every T2 country, two derived signals computed by joining `predmkt_country_spillover` with the underlying market probabilities:

**`predmkt_country_risk_composite`** — ∑(market_probability × elasticity × liquidity_weight) across all markets where this country appears in the spillover graph, weighted by `confidence`. Positive values = market pricing increases that hurt this country; negative = market pricing helps. Country dimension required.

**`predmkt_country_opportunity_composite`** — Inverse: same calculation with sign flipped to identify net-positive market exposure.

These are the equivalent of the GDELT `country_news_risk` factor but forward-looking instead of backward-looking.

### 7.5 Materialization Cadence

All signals materialized in the same daily snapshot job (§6.1). Signals depend only on `predmkt_daily` and `predmkt_country_spillover`, so recomputation is cheap (<10s for all 12 signals across 250 markets). No streaming needed.

---

## 8. MCP Server Integration

ASADO's existing MCP server (`scripts/asado_mcp_server.py`) gains three new tools and an updated schema summary.

### 8.1 New Tools

**`predmkt_snapshot(category, date=today)`**
- Returns: list of curated markets in the given ASADO category, with current probabilities, 24h volume, days-to-resolution, and resolution rules.
- Use case: "what is the market pricing for Fed policy right now?"

**`country_signal_now(country, channels=None)`**
- Returns: for one T2 country, all current prediction-market-implied risk/opportunity signals across the spillover graph, broken down by channel.
- Optional `channels` filter restricts to e.g. `['oil_export', 'oil_import_dependency']`.
- Use case: "what is the prediction-market-implied story for Saudi Arabia right now?"

**`event_market_set(keyword)`**
- Returns: all markets matching a keyword search across `title`, `rules_text`, and `slug`, ranked by 7-day volume.
- Use case: "find all markets related to 'Iran' or 'Hormuz'"; the agent then chains into `predmkt_snapshot` or detail lookups.

### 8.2 Schema Summary Updates

`get_schema_summary` adds a new section listing:
- The 5 new tables (`predmkt_daily`, `predmkt_market_meta`, `predmkt_outcome_meta`, `predmkt_country_spillover`, `predmkt_resolutions`, `predmkt_signals_daily`)
- The 12 derived signal names with brief descriptions
- The 10 spillover channels
- Coverage windows (from earliest snapshot through latest)

### 8.3 ask_asado Planner Awareness

When Stage 2 ships, the natural-language query layer's planner prompt is updated to include awareness of the prediction-market layer. The planner should:

1. For questions about the **future** ("will X happen", "probability of X", "what if Y"), preferentially route to `predmkt_snapshot` or `event_market_set`.
2. For questions about **off-universe entities** ("how does Iran affect..."), route to `country_signal_now` with the affected T2 country plus `event_market_set` for Iran-specific markets.
3. For questions about **macro indicators** (next CPI, next FOMC), preferentially use Kalshi-derived signals over Bloomberg consensus when freshness matters.

---

## 9. Use Cases

### 9.1 Replay of the May 2026 Iran-War Question

Original question: "Based on the latest changes over the past month, what countries are the biggest beneficiaries of the Iran war and who are the biggest losers?"

With Stage 2 in place, the agent's data tape now includes:

- All retrospective T2/GDELT data already used (unchanged)
- `regional_conflict_premium_middle_east` time series — the *probability* that regional conflict intensifies, traded daily
- `oil_shock_prob_30d` time series — what the market thought oil would do, day by day
- `hormuz_disruption_prob_90d` — the specific Hormuz channel
- `predmkt_country_risk_composite` for Saudi, Japan, Korea, India, Indonesia — forward-looking spillover
- Iran regime-fall, US-Iran ceasefire timing, Strait of Hormuz return-to-normal markets — all queryable via `event_market_set`

The answer becomes structurally different: not just "Korea +37%, Saudi -0.6%, Indonesia -7.4% in retrospect" but "the market is pricing X% probability of further escalation, Y% probability of ceasefire by August, and the Saudi underperformance is consistent with the implied de-escalation premium of ~Z." The forward-looking probability is the missing dimension.

### 9.2 Country Rotation Overlay Input

The country rotation autoresearch system currently uses Stage 1 factors as inputs. With Stage 2, `predmkt_country_risk_composite` and `predmkt_country_opportunity_composite` become eligible factors in the LoopPilot search space. Their daily cadence and forward-looking nature differentiate them from the existing GDELT and macro factors.

Hypothesis to test: prediction-market-implied risk leads realized factor returns by 5–20 days. If true, this is a high-IC factor that is unavailable to managers without MCP-grade integration.

### 9.3 CPI / FOMC Nowcast Feed for Macro Models

Existing macro regime classification uses observed CPI prints. Replace the "current CPI" feature with a hybrid: observed CPI (lagged 30d) + Kalshi-implied next-print distribution (current) + 12-month-forward Fed cut expectation (current). This is what professional rates traders already do; ASADO automating it is a clean win.

### 9.4 Off-Universe Entity Bridge for Russia, Israel, Iran, Pakistan

Today, asking "how is Russia doing" forces a manual workaround through GDELT raw daily (which has Russia ISO3) plus narrative reasoning. With Stage 2: `event_market_set('Russia')` returns the curated Russia-related markets (Russia-Ukraine ceasefire, Russia-NATO conflict, Putin out-by-date), and `country_signal_now('Germany')` plus `country_signal_now('Turkey')` returns the spillover-implied effect on the T2 universe.

### 9.5 Daily "What Changed" Digest

A new daily report component: top 10 markets with largest probability moves in the last 24h, filtered to ASADO-relevant categories, with their implied spillover effects on the T2 universe. This is the prediction-market analog to the "anomaly_digest" tool from the May 8 deep-improvements discussion.

### 9.6 Event Window Replay Integration

The `event_window` tool from Stage 1 (planned) takes `(country, date, halflife_days)` and returns the daily slice. Stage 2 augments this: when an event window is requested, the tool also surfaces which prediction markets were live and what their probabilities were across that window. Lets the agent reason about "the market saw this coming" vs. "the market was surprised" — dimension currently unavailable.

---

## 10. Validation and Quality Controls

### 10.1 Calibration Tracking

Every resolved market goes into `predmkt_resolutions` with the realized outcome and the prediction probabilities at 24h-before and 1h-before. A nightly job aggregates these into:

- **Per-category Brier score** — over the last 30, 90, 365 days
- **Calibration curve** — buckets of predicted probability vs. realized frequency
- **Time-to-resolution decay** — how does accuracy improve as markets approach close?

These metrics feed the `confidence_score` column on `predmkt_signals_daily`. Categories with poor historical calibration (e.g., long-horizon regime change) get downweighted in composites.

### 10.2 Stale-Market Detection

The `is_stale` flag in `predmkt_daily` is set when:
- 24h volume is below the platform threshold, OR
- No price update has occurred in >24h, OR
- Last traded price differs from mid by >5%

Stale markets contribute zero weight to composites but are kept in the raw layer for completeness.

### 10.3 Cross-Platform Consistency

Where Kalshi and Polymarket both list the same event (Fed decision, CPI print, major election), a daily reconciliation check logs the cross-platform spread. Persistent spreads >5% are investigated — usually they reflect platform-specific premiums (Kalshi has slight US-domestic bias, Polymarket has crypto-native bias) but occasionally they reflect a market making a real error worth flagging.

### 10.4 Resolution Rule Drift

Quarterly review verifies that no Polymarket curated market has had its rules section materially edited (which has happened historically). Any rule-edited market is re-curated or archived.

### 10.5 Spillover Calibration

The hand-assigned elasticities in `predmkt_country_spillover` are validated empirically every 6 months: regress realized country returns on the prediction-market-derived risk composite, compare implied beta vs. assigned elasticity, update the registry where evidence overwhelms judgment.

---

## 11. Build Plan

### Phase A — Foundations (week 1–2)

- Write `scripts/build_predmkt_panel.py` skeleton with idempotency, backup, failure handling
- Implement Kalshi puller: REST endpoints, candlestick fetching, market metadata
- Implement Polymarket puller: Gamma + CLOB, prices-history backfill where available
- Build initial schema: `predmkt_daily`, `predmkt_market_meta`, `predmkt_outcome_meta`, `predmkt_resolutions`
- Run with a tiny seed list (~20 markets) to validate end-to-end

### Phase B — Curation + Spillover (week 3–4)

- Hand-curate ~150–250 markets across both platforms; produce `config/predmkt_curated.yaml`
- Map every curated market to ASADO category, subcategory, resolution clarity
- Build the spillover graph: for each market that affects T2 countries, assign country/elasticity/channel/confidence — this is the real intellectual work, takes ~1 week of focused effort
- Document resolution semantics for ambiguous markets
- Schedule daily snapshot via launchd

### Phase C — Derived Signals (week 4–5)

- Implement the 12 composite signals from §7
- Add `predmkt_signals_daily` materialization to the daily job
- Update `variable_meta` with new signal entries
- Validate composites against external benchmarks: Kalshi-implied Fed expectation vs. CME FedWatch, Kalshi-implied CPI vs. Cleveland Fed nowcast
- Smoke test: query "what's the market saying about Iran today" and confirm sensible output

### Phase D — MCP Integration (week 5–6)

- Implement three new MCP tools (`predmkt_snapshot`, `country_signal_now`, `event_market_set`)
- Update `get_schema_summary` to surface new layer
- Update `ask_asado` planner prompt with prediction-market awareness
- Smoke-test by replaying the May 8 Iran-war query and a few canonical macro queries

### Phase E — Optional Enhancements (post-V1)

- 5-minute intraday snapshots for top-50 markets (event-day responsiveness)
- Polymarket subgraph backfill for ≥6 month history on high-priority markets
- Calibration-weighted signal confidence scoring (~3 months after launch when enough resolutions exist)
- Consider FinFeedAPI or Dome integration if cross-platform historical normalization becomes painful
- Automated curation registry refresh via LLM-assisted market scanning (low priority)

### Acceptance Criteria for V1 Ship

1. Daily ingestion runs successfully for 14 consecutive days without manual intervention
2. ≥150 curated markets in active polling
3. ≥120 markets with non-empty spillover graph entries
4. All 12 composite signals materialized daily
5. Three MCP tools live and tested via the existing query suite
6. The May 8 Iran-war query, when replayed, surfaces materially more useful information than the V0 answer

---

## 12. Open Questions

1. **Polling cadence on event days.** Default daily, but should we run 5-min snapshots on FOMC / CPI release days? Adds complexity; deferred to Phase E.

2. **Backfill via paid third-party.** FinFeedAPI free tier first; defer Dome/polymarketdata.co decisions until Phase E.

3. **Spillover elasticity calibration.** Hand-assigned vs. regression-fit on backtest. Recommendation: hand-assigned for V1, empirical refinement in Phase E once 6 months of resolved-market data exist.

4. **Storage for intraday history if added later.** DuckDB can handle the volume, but if we go to 5-min granularity for 250 markets that's ~26M rows/year, manageable but worth a partition strategy.

5. **Regime-change market sensitivity.** Polymarket lists markets like "Khamenei out by date." These have data value but are politically sensitive. Recommendation: include in raw ingestion, exclude from any external-facing reports without explicit toggle.

6. **Cross-platform deduplication for composite signals.** When the same event is listed on both platforms, do we average the probabilities or pick the more liquid one? Recommendation: liquidity-weighted average, with the spread tracked separately as a quality signal.

7. **Curation file format.** YAML is human-friendly; JSON simpler to parse. Recommendation: YAML for human curation, parsed to JSON for runtime.

8. **MCP tool naming.** `predmkt_*` prefix or `pm_*`? `predmkt_*` is unambiguous; `pm_*` collides with project management. Recommendation: `predmkt_*`.

9. **Regulatory and compliance sensitivity.** Pulling data from regulated and unregulated platforms. Recommendation: data-only, no trading; document the data-only nature in `CLAUDE.md` and `AGENTS.md`.

---

## 13. Out of Scope (Explicit)

- Trading on either platform
- Sports markets, entertainment, single-celebrity markets
- Crypto-asset price markets (BTC, ETH price strikes; only stablecoin regulation markets if policy-relevant)
- Manifold Markets (play-money), PredictIt (small-stakes), Metaculus (scientific) — not enough liquidity or relevance
- Real-time WebSocket feeds — only REST polling in V1
- Building a Polymarket or Kalshi clone or competing platform
- Automated trade-execution research

---

## 14. References

- "Kalshi and the Rise of Macro Markets," Federal Reserve Board working paper FEDS 2026-010, February 2026
- Cleveland Fed Inflation Nowcasting (https://www.clevelandfed.org/indicators-and-data/inflation-nowcasting) — independent benchmark for CPI nowcast quality
- Polymarket API documentation (https://docs.polymarket.com)
- Kalshi API documentation (https://trading-api.readme.io)
- ASADO Stage 1 daily extension PRD (this repository, May 2026)
- May 8 2026 deep-improvements discussion: off-universe entity bridge, plan-execute-critique loop, event window tool — this PRD operationalizes the prediction-market portion of those proposals

---

## Appendix A — Initial Curated Market Seed List (Illustrative)

Sketch only; the actual registry is built in Phase B. Each entry below would expand to a full YAML record with spillover graph.

**Macro / Fed**:
- Kalshi KXFEDDECISION-{next 4 meetings} ladder
- Kalshi KXCPI ladder for next 3 prints
- Kalshi KXACPI Core CPI ladder for next 3 prints
- Kalshi KXPCECORE
- Kalshi KXUNEMP, KXNFP
- Polymarket "How many Fed rate cuts in 2026"
- Polymarket "Fed decision in {month}" series
- Polymarket "US recession in 2026"

**Geopolitics — Middle East**:
- Polymarket "US x Iran permanent peace deal by..."
- Polymarket "Strait of Hormuz traffic returns to normal by..."
- Polymarket "Iran closes its airspace by..."
- Polymarket "Will the U.S. invade Iran before 2027"
- Polymarket "Will the Iranian regime fall by..."
- Polymarket "What will WTI Crude Oil hit in {month}"
- Polymarket "Will Crude Oil (CL) hit X by end of {month}"

**Geopolitics — Pacific**:
- Polymarket "China x Taiwan military clash before 2027"
- Polymarket "China x Japan military clash before 2027"

**Geopolitics — Eastern Europe**:
- Polymarket Russia-Ukraine ceasefire markets
- Polymarket Putin tenure markets

**Tariff / Trade**:
- Polymarket "Which countries will Trump make new trade deals with before 2027"
- Polymarket "Will the Court Force Trump to Refund Tariffs"
- Polymarket "Tariff increase on {country} in effect by..."
- Polymarket "Will Trump visit China by..."

**Country Elections (T2-relevant)**:
- Kalshi Taiwan presidential
- Polymarket UK local elections, Brazil 2026, Canada federal
- Polymarket "Venezuela leader end of 2026"

Approximately 150 markets in the V1 seed; expansion to 250 expected as ASADO usage drives demand for additional categories.

---

*End of PRD*
