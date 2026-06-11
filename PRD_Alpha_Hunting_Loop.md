# PRD — ASADO Alpha-Hunting Loop
## Dislocation Engine + Evaluation Harness + Ledgers

| Field | Value |
|-------|-------|
| **Project** | ASADO country equity research platform |
| **System name** | Alpha-Hunting Loop |
| **Short name** | `ahl_v1` |
| **Version** | 1.0 (draft for discussion) |
| **Created** | 2026-06-09 |
| **Owner** | Arjun Divecha |
| **Executor** | Frontier model agent sessions (multi-session) |
| **Status** | Draft — open questions in §14 must be resolved before build |
| **Related** | `PRD_Semantic_Layer_Variable_Registry.md` (load-bearing dependency), `PRD_Strategy_02_Factor_Momentum_Country_Rotation.md` (PIT rules + gate style inherited), `regime/PRD.md` + `regime/results/regime_test_summary.md`, `PRD_Stage2_Prediction_Markets.md`, `docs/DATABASE_AUDIT_2026_06_09.md` |

---

## 0. One-paragraph summary

ASADO's optimizer owns the unconditional cross-section (top-7, monthly; the old "8 live factors" whitelist was identified 2026-06-10 as a stale Fuzzy Daily artifact and removed). This PRD builds the layer above it: a system whose job is to find the trades the optimizer structurally cannot see — conjunctions across subsystems, regime-conditional signal flips, shocks propagating along graph edges before prices move at the endpoints, discrete events mapped to mechanisms, and the explicit gap between what the data knows and what markets have priced. The design accepts one governing constraint: **a frontier model can generate hypotheses ~1000x faster than honest validation can process them**, so the validation harness and trial-counting ledger are built *first*, and every other component — the nightly dislocation engine, the graph-feature factory, the new data feeds — is a client of that skeptic, never a bypass of it.

---

## 1. Thesis and division of labor

### 1.1 What the optimizer owns (do not compete)
Ranking 34 countries on stationary, linear, univariate signals. Top-7 membership, monthly rebalance. `factor_returns` / `factor_returns_daily` are the outcome source of truth. (The "8 live factors" whitelist formerly referenced here was a stale Fuzzy Daily artifact — removed 2026-06-10.)

### 1.2 What the model owns (the five edges)

| # | Edge | Why the optimizer can't see it |
|---|------|-------------------------------|
| E1 | **Conjunctions** — 3+ subsystem joins (e.g. Chile when copper z>1 AND China credit impulse turning AND Chilean REER flat) | Grid search over conjunctions is combinatorially hopeless; economic priors prune the space |
| E2 | **Conditionality** — same signal, opposite meaning by regime (CDS widening in a crisis country vs a calm one) | Optimizer weights are unconditional. Regime test result: H1 PASS (regimes persist), H2 PASS (conditional IC dispersion is real), H3 FAIL (mechanical re-weighting didn't clear the Sharpe hurdle) → regime enters as *reasoning context*, not as a mechanical overlay |
| E3 | **Propagation** — shocks moving along TRADES_WITH / HAS_BANKING_EXPOSURE_TO / HOLDS_PORTFOLIO edges faster than endpoint prices | Graph features don't exist in the panel yet (fixed by Component D) |
| E4 | **Events** — discrete, unprecedented-ish events → mechanism → expected return path via historical analogs | `event_log` (146 events) is backward-only; needs the forward calendar (Tier 2) |
| E5 | **Knowable vs. priced** — data vs what consensus / prediction markets / CDS / valuations have absorbed | Requires the pricing layer as a first-class citizen (predmkt accumulation, valuation block, surprise surface) |

### 1.3 The seven trade archetypes (recurring shapes the system scans for)

| ID | Archetype | Edge | Buildable today? |
|----|-----------|------|------------------|
| A1 | Terms-of-trade impulse without repricing | E1 | **Partially** — see §4 D1 correction |
| A2 | Two-hop graph propagation | E3 | Yes (after Component D) |
| A3 | Revision-momentum quadrants (forecast revisions vs price momentum) | E5 | No — needs surprise surface (§8) |
| A4 | Cross-asset incoherence (equity / CDS / FX disagree, same country, same week) | E1/E5 | **Partially** — CDS is monthly-only in the DB (§4 D4) |
| A5 | Attention without resolution (GDELT attention shock, \|return\| small) | E4 | Yes |
| A6 | Prediction-market vs sovereign-market disagreement | E5 | No — predmkt has 1 live snapshot; needs daily accumulation (§8 Phase 0) |
| A7 | Factor-level crowding (dispersion compression across all T2 factor return series) | E2 | Yes |

---

## 2. System architecture — three layers

```text
Layer 1  DETERMINISTIC ASSEMBLY (nightly, no LLM)
         graph_features job + dislocation detectors
         → dislocation_daily table + rendered brief (≤100 rows)

Layer 2  REASONING PASS (model, daily + monthly)
         daily: steward open theses against frozen entries + triage new dislocations
         monthly: regime-conditional read on the 8 optimizer factors + independent theses
         emits: trade theses AND factor hypotheses

Layer 3  VALIDATION & MEMORY (the skeptic)
         evaluate_signal harness (PIT + embargo enforced inside)
         hypothesis_ledger (pre-registration, trial counting, deflated Sharpe)
         thesis_ledger (frozen entries, auto-marking, Brier calibration)
```

**Context-budget principle (non-negotiable):** Layer 2 never sees raw panels. It sees the dislocation table — the ~60–100 numbers that disagree with each other — plus open positions and the forward calendar. The model's context window is the scarce resource; Layer 1 exists to spend it well.

**Loop-closure principle:** every Layer-2 output is structured (registered hypothesis or ledgered thesis). Nothing the model says is allowed to evaporate; nothing it says is allowed to count as evidence until Layer 3 scores it.

---

## 3. Grounding — verified live DB state (2026-06-09)

Queried directly from `Data/asado.duckdb`; supersedes any stale doc claims.

| Surface | Status | Relevance |
|---|---|---|
| `feature_panel` / `normalized_panel` | **LIVE** (restored post commodity-split: ~720 / ~294 vars) — Strategy-02 PRD's "missing" claim is stale | Exposure source for harness |
| `commodity_panel` | LIVE — global view, 87 series × 7 features, date-keyed, **no country axis** (broadcast tiling removed) | D1 input |
| `t2_factors_daily` / `t2_levels_daily` | 35.6M / 15.3M rows, fresh through 2026-06-09 | D4, D5, A7 inputs |
| `factor_returns` (monthly) / `factor_returns_daily` | 390 factors → 2026-05 / 180 factors → 2026-06-09 | Outcome truth; A7 |
| `gdelt_factors_daily` | 10.2M rows → 2026-06-08 | D5 |
| `predmkt_*` | **One snapshot (2026-06-10), 15 markets, `predmkt_resolutions` EMPTY** — thin pilot, no time series | A6 blocked until accumulation |
| `event_log` | 146 curated events, backward-only | E4 analogs |
| Neo4j | 1,174 nodes / 30,366 edges: HAS_FACTOR_EXPOSURE 25,459 · HOLDS_PORTFOLIO 1,960 · TRADES_WITH 928 · HAS_BANKING_EXPOSURE_TO 584 · EXPORT_EXPOSED_TO 28 (only 4 Commodity nodes) | Component D inputs |
| `country_returns_monthly` | **Missing as a table** (logic exists in MCP `country_returns` tool) | Must be materialized, Phase 0 |
| `dislocation_daily`, `hypothesis_ledger`, `thesis_ledger`, `graph_features_daily` | Do not exist | This PRD builds them |
| Regime tags | `regime/results/regime_tags.parquet` exists; H1/H2 PASS, H3 FAIL | Context columns in dislocation table |

---

## 4. Component A — Dislocation Engine (Layer 1, nightly, deterministic)

A single orchestrated job (`scripts/build_dislocations.py`, runs after `build_daily_panels.py`) executing a family of detectors. **No LLM calls.** Pure pandas/DuckDB. Every detector emits rows into one table.

### 4.1 Output schema — `dislocation_daily`

| Column | Type | Notes |
|---|---|---|
| `date` | DATE | Run date |
| `dislocation_id` | VARCHAR | Stable hash of (detector, entity, first_seen) — persists across days |
| `detector` | VARCHAR | D1…D8 |
| `archetype` | VARCHAR | A1…A7 |
| `entity` | VARCHAR | Country (T2 exact name), factor, or country-pair |
| `direction` | VARCHAR | `long` / `short` / `flag` (informational) |
| `severity` | DOUBLE | Detector-specific z, normalized to comparable scale |
| `components_json` | JSON | The disagreeing inputs, with values and their own z-scores |
| `regime_context` | VARCHAR | Current regime tag(s) from `regime_tags.parquet` |
| `status` | VARCHAR | `new` / `persisting` / `intensifying` / `fading` / `resolved` |
| `first_seen` | DATE | |
| `days_active` | INT | |
| `resolution_note` | VARCHAR | Filled when resolved: `repriced_with` / `repriced_against` / `decayed` |

Resolved rows are kept (never deleted) — the resolution history is itself training data for "which dislocations resolve which way."

### 4.2 Detectors

**D1 — Terms-of-trade impulse without repricing (A1).**
*Correction to the original sketch:* the export-weighted commodity basket is **not** constructible from bilateral trade weights alone — those give *partner-country* weights, not *commodity composition* of exports. Two stages:
- **v0 (today):** crude basket from the existing 4 EXPORT_EXPOSED_TO commodity groups in Neo4j + the 16 Pink Sheet indices. Coarse but directionally usable.
- **v1 (Phase 3):** one-time static table of commodity export/import shares per country from UN Comtrade / WITS (SITC 2-digit, free, annual refresh) → proper per-country ToT basket: Σ (export share × commodity return) − Σ (import share × commodity return), from `commodity_panel`.
- Trigger: ToT basket z_36m > +1.5 (or < −1.5) AND |country 21d equity return z| < 0.5 AND |REER 3m change z| < 0.5.

**D2 — Two-hop graph propagation (A2).** Consumes Component D features. Trigger: exposure-weighted neighbor return gap (neighbor 21d return minus own 21d return, weighted by TRADES_WITH / HAS_BANKING_EXPOSURE_TO / HOLDS_PORTFOLIO edge weights) exceeds ±1.5z vs its own 3-year history; two-hop variant requires middle node repriced (|z|>1) and endpoint not (|z|<0.5).

**D3 — Revision-momentum quadrants (A3).** Blocked until surprise surface exists (§8). v0 from Phase 0 vintage snapshots: month-over-month change in `imf_weo` GDP/CPI forecasts (forward-only, PIT-clean from snapshot start) × 6m price momentum → four quadrants; flag "revised up + flat price" and "revised down + strong price."

**D4 — Cross-asset incoherence (A4).** v0 with what is daily today: country equity return (t2 daily), FX (t2 levels), 10Y where present. **CDS is monthly-only in `bloomberg_factors`** — daily CDS for 34 names is a small Bloomberg history pull (Phase 3) and is the highest-value single addition to this detector. Trigger: sign disagreement across ≥2 asset surfaces with each |z| > 1 within the same 5-day window.

**D5 — Attention without resolution (A5).** GDELT attention/tone z (gdelt_factors_daily) > +2 AND |5d country return| < 0.5σ. Components include the event-class tags so Layer 2 can pull `event_window` analogs. *GDELT enters only as a trigger to look, never as a mechanical trade signal.*

**D6 — Prediction-market vs sovereign-market disagreement (A6).** Blocked on predmkt daily accumulation (Phase 0 cron) + registry expansion. Trigger once live: Δprobability (5d) on a country-mapped market |>10pts| AND mapped sovereign surface (CDS / FX / equity) flat — or the inverse. Uses `predmkt_country_spillover` elasticities. Spillover covers only 18/34 countries; coverage gap reported, not silently dropped.

**D7 — Factor crowding (A7).** For every T2 factor with a live return series in `factor_returns_daily` (~106 factors; the old 8-factor whitelist was removed 2026-06-10 as a stale artifact): cross-sectional dispersion of the underlying characteristic (from `t2_factors_daily`), rolling z. Compression below −1.5z → `flag` row, capped at the 10 most-compressed factors per day. Also: average pairwise daily-return correlation spike across all factor return series (herding).

**D8 — Open-thesis stewardship rows.** For every open thesis in `thesis_ledger` — and, once the News-repo bridge (§8 priority 3) lands, every live position in `portfolio_holdings_daily` — current mark, distance to invalidation level, days to horizon, any new dislocation rows touching the same entity. Guarantees Layer 2 reviews positions against the *frozen* entry thesis, not a remembered one, and against the *actual* book, not an assumed one.

**D9 — Country index vs ETF gap (post News bridge).** T2 country return vs its primary ETF return (`etf_prices_daily`), rolling 5d/21d gap z-scored vs own history. A persistent gap means the investable expression and the index disagree — either a tradeable basis or a data problem; both are worth a row.

### 4.3 Rendered brief

`Data/dislocations/brief_YYYY_MM_DD.md` — capped at 100 rows, ordered by (status=new first, then severity), one line each + components. This file is what gets pasted/fed into the Layer 2 session. Format optimized for model consumption, not human prettiness.

---

## 5. Component B — Evaluation Harness (`evaluate_signal`)

A Python module (`scripts/harness/evaluate_signal.py`) wrapped as an MCP tool. The harness is the *only* path from "idea" to "evidence."

### 5.1 Input contract

```text
evaluate_signal(
  hypothesis_id,         # REQUIRED — must already exist in hypothesis_ledger (pre-registered)
  signal_spec,           # {table, variable} or SQL producing (date, country, value)
  direction,             # higher_is_better / lower_is_better
  frequency,             # monthly / daily
  horizons,              # monthly: [1m, 3m, 6m]; daily: [5d, 21d, 63d]
  universe="t2_34",      # default full universe; subsets allowed but logged
  start_date="2008-01-01"
)
```

A call with no pre-registered `hypothesis_id` **fails hard**. No anonymous backtests.

### 5.2 What it computes (all enforced inside — the model cannot cheat even accidentally)

1. **PIT enforcement:** publication-lag embargo per variable from the semantic registry (`variable_registry.publication_lag`); until the registry is populated, conservative defaults: monthly → 1-month embargo, quarterly → 1 quarter, annual → 12 months, forecast-flagged variables excluded. Inherits Strategy-02 §9 rules wholesale; any violation is a hard failure.
2. **Rank IC** (Spearman) by horizon, with Newey-West t-stats; year-by-year IC table.
3. **Portfolios:** top-7 long-only and top7/bottom7 LS vs pre-registered baselines (`equal_weight_34`, `country_momentum_12_1_top7`), 10/25/50 bps cost cases, turnover, borrow cost on shorts.
4. **Sub-period stability:** 2008–12, 2013–17, 2018–22, 2023–latest; COVID and 2022-inflation windows.
5. **Deflated Sharpe** against the **running trial count of the hypothesis family** (from the ledger) — not against N=1.
6. **Coverage gates:** ≥28 countries with valid values on ≥95% of dates, else verdict is `INSUFFICIENT_COVERAGE`, not a number.

### 5.3 Verdict (written back to the ledger automatically)

| Verdict | Criteria (proposed — Arjun to confirm, §14 Q3) |
|---|---|
| `WATCH` | NW-t(IC) ≥ 2.5 at primary horizon, IC positive in ≥60% of years, survives base costs, deflated Sharpe > 0 |
| `WEAK` | Some signal but fails ≥1 gate — archived, counts as a trial |
| `DEAD` | No signal — archived, counts as a trial |
| `INSUFFICIENT_*` | Coverage/history failures — counts as half a trial |

`WATCH` → eligible for paper allocation in Layer 2 reasoning and for Strategy-PRD promotion. Nothing goes from `WATCH` to live capital without a separate strategy PRD (Strategy-02 pattern).

---

## 6. Component C — Ledgers (Layer 3 memory)

Both ledgers are **append-only JSONL files in git** (`ledgers/hypothesis_ledger.jsonl`, `ledgers/thesis_ledger.jsonl`) loaded into DuckDB tables on each nightly run (mirrors the `event_log_seed.yaml` pattern). Git history = tamper evidence.

### 6.1 `hypothesis_ledger` — pre-registration and trial accounting

| Field | Notes |
|---|---|
| `hypothesis_id` | `H_YYYYMMDD_NNN` |
| `created_ts`, `author` | model session id or `arjun` |
| `archetype` | A1…A7 / `other` |
| `family_key` | Groups related trials for deflated-Sharpe N (e.g. all ToT-basket variants = one family) |
| `mechanism_text` | **Written before any results are seen.** One paragraph: why this should predict returns |
| `signal_spec_hash` | sha256 of spec + mechanism — pre-registration proof |
| `trial_index` | Auto-incremented within family |
| `status` | `registered` → `tested` → `watch` / `rejected` / `retired` |
| `verdict_json` | Harness output, attached by the harness, never by hand |

### 6.2 `thesis_ledger` — trades with frozen entries and auto-marking

| Field | Notes |
|---|---|
| `thesis_id` | `T_YYYYMMDD_NNN` |
| `opened_ts`, `author` | |
| `entity`, `direction`, `horizon_days` | Country (or factor overlay) |
| `entry_thesis_text` | **Frozen at open.** Mechanism + what would make it wrong |
| `probability` | Stated P(thesis right) at open — feeds Brier |
| `invalidation_level` | Numeric, checkable by D8 |
| `catalyst` | Link to event-calendar entry or dislocation_id |
| `source_dislocation_id` | Provenance |
| `status` | `open` / `hit` / `miss` / `invalidated` / `expired` |
| `marks` | Auto-appended daily from `country_returns` — never hand-marked |
| `realized_return`, `brier_contribution` | At close |

### 6.3 Calibration report (monthly, automatic)

Brier score and hit rate by archetype, by horizon, by regime-at-open. Overrides of optimizer output are logged as theses too — **overrides are calibration data**, resolving the override-feedback design tension. Survivor insights get distilled into the personal-knowledge system at quarter end.

---

## 7. Component D — Graph→Panel Feature Factory

Nightly job (`scripts/build_graph_features.py`) reading Neo4j edges + daily returns, writing `graph_features_daily` to DuckDB as **ordinary variables** registered in `variable_meta` (source=`graph`). Turns Neo4j from a lookup table into a feature factory. Every feature is subject to the harness gate before any trading use — no graph mystique.

v1 feature set (per country, per day):

| Variable | Definition |
|---|---|
| `GRAPH_TRADE_NBR_RET_GAP_21D` | Trade-weighted neighbor 21d return − own 21d return |
| `GRAPH_BANK_NBR_RET_GAP_21D` | Banking-exposure-weighted version |
| `GRAPH_PORT_HOLDER_STRESS_21D` | HOLDS_PORTFOLIO-weighted holder-country drawdown |
| `GRAPH_TWOHOP_TRADE_GAP_21D` | Two-hop propagation gap (middle node repriced, endpoint not) |
| `GRAPH_NBR_DRAWDOWN_COUNT` | # of neighbors in >10% drawdown, edge-weighted (contagion pressure) |

Plus 63d variants. Edge weights refresh with the monthly Neo4j rebuild; returns are daily.

---

## 8. Component E — New data (Tier 2), in priority order

| Priority | Dataset | Why | Effort | Unblocks |
|---|---|---|---|---|
| 1 | **Predmkt daily accumulation** (cron the existing collector; expand registry 15 → 100+ markets) | One snapshot is not a time series; resolutions table empty = no calibration | Trivial cron + curation hours | D6 / A6, E5 |
| 2 | **Vintage snapshotting** of every monthly pull, starting now | Trivial today, priceless in 3 years; v0 surprise surface | Trivial | D3 v0 |
| 3 | **News-repo bridge** — nightly copy of `portfolio_snapshots` / `portfolio_summary` from `News/data/report.db` (live Schwab + IBKR book, already solved there) into ASADO as `portfolio_holdings_daily`; ETF↔T2 mapping table; country-ETF + cross-asset daily price/volume subset (~100–150 of the 763 tickers) as `etf_prices_daily`, with a one-time deep yfinance backfill for the country ETFs | ASADO has zero portfolio surface — the live book powers D8 stewardship and thesis auto-marking; the ETF layer is the investable expression (Strategy-02 §12.3) and enables a free new detector: T2 country-index vs country-ETF return gap; volume → flow proxies; cross-asset block (HYG/TIP/VNQ/IWD-IWF/BCI) gives D4 a daily risk tape | Trivial–small (broker plumbing already exists in News; bridge + mapping ≈ 1 day) | D8 v1, thesis marking, ETF-gap detector, D4 upgrade |
| 4 | **GDELT article-level evidence layer** — v0: MCP tool `country_news(country, day)` hitting the GDELT DOC 2.0 API live (headlines + URLs + themes/tone metadata; no storage, no pipeline). v1: nightly `gdelt_articles_recent` table, 14-day rolling retention, wire-story dedup, top-N per country — plus **permanent evidence packs** frozen whenever a dislocation fires or an `event_log` entry is created. Full text scraped on demand only for trigger-attached articles. Embeddings only if later needed (DuckDB VSS column, no separate vector store) | Closes the aggregate→mechanism gap: D5 says "Indonesia attention z=+2.4" but aggregates destroy *what the news says* — "governor resigned" and "volcano erupted" are the same tone shock and opposite trades. **Layer 2 reading only, never a signal** (constitution §10.6). Evidence packs are the article-level analog of vintage snapshotting: news history survives exactly where it matters — around events | v0 trivial (an afternoon); v1 small | D5 explanation, E4 evidence packs, Phase 0 manual hunt |
| 5 | **Forward event calendar** (CB meeting dates, elections, MSCI semi-annual reviews, index rebalances) | Trades need catalysts; MSCI reclassifications (e.g. Vietnam EM watch) are the most tradeable scheduled events in country-land | Small collector + curated YAML | E4, thesis catalysts |
| 6 | **Foreign investor flows** — KRX, TWSE, NSDL/NSE, SET, IDX, PSE, B3 daily foreign buy/sell (free) | 7+ of 34 countries, exactly the EMs where flows matter; best dataset not yet owned | Medium (7 scrapers/APIs) | New archetype |
| 7 | **Valuation block** — CAPE, P/B, DY, ERP (earnings yield − real yield) | Mostly new Bloomberg fields, no new pipes | Small (Bloomberg collector extension) | E5, monthly pass |
| 8 | **Daily CDS + 10Y** for 34 sovereigns (Bloomberg history pull) | Upgrades D4 from partial to full | Small | D4 v1 |
| 9 | **Surprise surface** — WEO vintage backfill (public archives, semi-annual); ECFC consensus snapshots forward | Revision momentum becomes backfillable, not just forward | Medium | D3 v1 / A3 |
| 10 | **Commodity export/import shares** — UN Comtrade/WITS SITC 2-digit, one-time + annual | D1 v0 → v1 (the corrected ToT basket) | Small | D1 v1 |
| 11 | COT, ETF share-count flows (34 country ETFs), FINRA short interest | Positioning layer | Medium | Crowding detectors |

All collectors follow the existing resilience pattern (per-source try/except, source-level merge, 24h cache, timestamped backups, `country_mapping.json`).

---

## 9. Operating cadence

| When | What runs | Output |
|---|---|---|
| Nightly (after `build_daily_panels.py`) | Component D → Component A → ledger loaders → auto-marking | `dislocation_daily` rows, brief markdown, updated marks |
| Daily (model session) | Layer 2 daily pass: D8 stewardship rows first, then new dislocations | Updated/closed theses; new theses; harness calls for anything promotable |
| Monthly (aligned to optimizer rebalance) | Layer 2 monthly pass: regime-conditional confidence/veto on factor signals + independent valuation+catalyst theses + factor hypotheses | Monthly memo; registered hypotheses |
| Monthly (automatic) | Calibration report | Brier by archetype; ledger stats |
| Quarterly | Distillation: survivors → PKS; retired-hypothesis post-mortems | Knowledge updates |

---

## 10. Anti-overfitting constitution (non-negotiable)

1. **Pre-registration before results.** Mechanism text + spec hash exist in the ledger before the harness will run. No retroactive hypotheses.
2. **Every trial counts.** Harness refuses anonymous calls; deflated Sharpe uses the family trial count; `INSUFFICIENT_*` verdicts count half.
3. **PIT and embargo inside the harness**, not in caller discipline.
4. **One primary horizon per hypothesis**, declared at registration. Other horizons are diagnostics.
5. **Family-wise budgets:** a family that accumulates 20 trials without a `WATCH` is frozen for 6 months (configurable).
6. **GDELT and attention signals trigger looking, never mechanical trading.**
7. **The harness is the bottleneck, never the bypass.** Expected base rate: most conjunctions are noise; the edge compounds through few survivors plus event/graph trades where mechanism is strong.
8. **No silent fallbacks** (house rule): a detector whose inputs are missing emits a loud `DETECTOR_DEGRADED` row, never a quietly-narrower scan.

---

## 11. Roadmap

### Phase 0 — Switch-ons (~2–3 days)
- Cron predmkt collector daily; begin populating `predmkt_resolutions`.
- Vintage snapshotting of every monthly pull (copy panels to `Data/vintages/{YYYY_MM}/`).
- Materialize `country_returns_monthly` as a DuckDB table (reuse MCP tool logic).
- v0 `country_news(country, day)` MCP tool against the GDELT DOC 2.0 API (live, no storage) — gives the manual hunt readable evidence behind any attention spike.
- **Manual hunt in parallel:** find 2–3 current dislocations by hand with existing MCP tools — pressure-tests detector specs before they're coded, and seeds the first thesis_ledger entries.
- **Acceptance:** cron running 7 unattended days; first vintage saved; returns table live; ≥2 hand-found dislocations written up as proto-theses.

### Phase 1 — The skeptic (harness + ledgers) (~1 week)
Build Components B and C *before* any idea-generation tooling.
- **Acceptance:** harness rejects unregistered calls; PIT tests pass (Strategy-02 §19.2 suite reused); deflated Sharpe reads family counts; one end-to-end run on a known factor (e.g. 120DTR) reproduces sane IC; ledgers load nightly; auto-marking marks a dummy thesis correctly.

### Phase 2 — The engine (graph features + dislocation v1) (~1–2 weeks)
Component D, then Component A with D2, D4-v0, D5, D7, D8, D1-v0, D3-v0.
- **Acceptance:** nightly run < 10 min; brief renders ≤100 rows; dedup/status transitions correct across 5 consecutive days; every graph feature registered in `variable_meta`; ≥3 graph features pushed through the harness with verdicts recorded (whatever the verdicts are).

### Phase 3 — The data (Tier 2, priorities 3–8) (~2–4 weeks, parallelizable)
Forward calendar, foreign flows, valuation block, daily CDS, surprise surface, Comtrade shares → upgrade D1/D3/D4/D6 to v1.
- **Acceptance:** each new collector passes the standard resilience checks; D6 produces its first live disagreement row; D1 v1 basket validated against 3 known episodes (e.g. Chile/copper 2021, Saudi/oil 2020, Chile/copper 2024).

### Phase 4 — The loop (live cadence + calibration) (~ongoing)
Daily + monthly passes live; first monthly calibration report; first quarterly distillation.
- **Acceptance:** 4 consecutive weeks of daily passes; ≥10 closed theses with Brier scores; ≥1 hypothesis at `WATCH`; zero harness bypasses.

---

## 12. Non-goals

- **No replacement of the optimizer.** This system overlays, vetoes, and feeds it — Strategy-02 territory remains separate.
- **No live trading.** Theses are paper until a separate strategy PRD promotes anything (Strategy-02 gate pattern).
- **No mechanical GDELT/attention trading.**
- **No unioning of anything into `unified_panel`/`feature_panel` that breaks the optimizer cycle guard.** Graph features go in as inputs (allowed); optimizer outputs stay out (guarded). Likewise **portfolio holdings are positions, not explanatory variables** — `portfolio_holdings_daily` and `etf_prices_daily` stay out of the explanatory panels (standalone tables; ETF returns are the expression layer, T2 returns remain backtest truth).
- **No GDELT article text as signal input.** Articles are Layer-2 reading evidence only; nothing derived from headlines enters a detector or the harness without going through the normal aggregate pipeline first.
- **No semantic registry duplication.** Sign conventions, publication lags, mechanisms live in `variable_registry` (its own PRD); this system *consumes* them.
- **No new ML models in v1.** Detectors are deterministic; reasoning is the model in the loop; validation is classical statistics.

---

## 13. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Hypothesis flood overwhelms validation | High | Constitution §10: registration friction, family budgets, harness-as-bottleneck |
| Sign errors on REER/CDS-type variables | High | Semantic registry dependency; harness refuses variables with `sign=unknown` once registry is live |
| Dislocation table too noisy → model attends to garbage | Medium | Severity floors per detector, 100-row cap, status decay; tune thresholds in Phase 2 on 30 days of replayed history |
| Predmkt layer stays thin | Medium | Phase 0 cron + registry expansion; D6 ships dark until ≥60 days of snapshots |
| Calibration sample too small to mean anything for quarters | Medium | Accept it; report n alongside Brier; no confidence claims below n=20 per cell |
| Stale docs poison agent sessions | Medium | This PRD's §3 pattern: live-DB grounding at the top of every build session |
| Model marks its own homework | High | Auto-marking only; verdicts written only by the harness; frozen entry theses; git-tracked append-only ledgers |

---

## 14. Open questions (decide before Phase 1)

1. **Brief delivery surface** — where does the daily brief land: markdown file in repo (simplest), the dashboard, or pushed (email)? Recommend: markdown file + dashboard tab later.
2. **Paper-only confirmation** — thesis_ledger stays paper with no IBKR sizing suggestions until the first calibration report exists. Confirm.
3. **Verdict thresholds** (§5.3) — accept NW-t ≥ 2.5 / 60% positive years / base-cost survival, or tighten/loosen?
4. **PRD granularity** — execute from this master PRD, or split Components A and B into standalone PRDs for separate agent sessions? Recommend: master PRD + per-phase build briefs.
5. **Predmkt expansion scope** — the old Stage-2 target was ≥150 curated markets. Re-affirm that target, or set a smaller v1 (e.g. 60 markets covering elections + CB + commodities for the top-15 countries)?
6. **Daily pass trigger** — fully scheduled (cron + automated session) or Arjun-initiated each morning? v1 recommendation: Arjun-initiated, automate after Phase 4 acceptance.

---

**Last updated:** 2026-06-10 (v1.1 — added News-repo bridge and GDELT article-evidence layer to Tier 2; added D9 detector)
**One-line summary:** Build the skeptic first (harness + ledgers), then the nightly dislocation engine and graph-feature factory on top of the existing warehouse, then the seven-archetype hunt with new pricing-layer data — so the model's hypothesis firehose compounds into a small set of validated, calibrated, mechanism-backed trades instead of industrial-scale curve-fitting.
