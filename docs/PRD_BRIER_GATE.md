# PRD — Brier Gate: Can ASADO + Claude Beat the Prediction-Market Price?

**Owner:** Arjun Divecha
**Status:** Draft v0.1
**Date:** 2026-07-03
**Motivation:** ACX "The AI Superforecasters Are Here" (FutureSearch, Preseen). Their claim, stripped of hype: a data-advantaged AI forecaster can beat *prediction-market prices* on thin macro books. ASADO's edge is exactly the data layer those generic scaffolds lack. This PRD specifies the cheap kill-criterion experiment that must pass before any capital or further build is committed — same gate-first structure as the Tier 1 overnight signal (which passed Gate 1, failed Gate 2, and was correctly not traded).

---

## 1. The question, precisely

At forecast time *t*, for a binary market *m* with market probability `p_mkt(m,t)` and eventual outcome `y(m) ∈ {0,1}`:

> Does a Claude forecast `p_ai(m,t)`, produced with **point-in-time ASADO warehouse context and no retrospective information**, achieve a lower Brier score than the market — by enough to survive the spread?

Three arms, so we learn *where* any edge comes from:

| Arm | Inputs at time t | Tests |
|---|---|---|
| A0 baseline | question + resolution rules only (no market price, no data) | raw model prior |
| A1 +warehouse | A0 + an ASADO context pack (relevant PIT series as-of t) | **the warehouse's incremental value — the core hypothesis** |
| A2 +market | A1 + the market price at t | whether the model knows when to defer vs. override |

Primary metric: mean Brier per arm vs. market Brier `(p_mkt − y)²`, paired by market, bootstrap CI clustered by event (strikes of one event share an outcome — they are NOT independent). Secondary: log-loss, calibration curve, and the **economic version**: hypothetical PnL of buying/selling at the market's bid/ask whenever `|p_ai − p_mkt| > θ` for a θ grid, net of the observed spread. Report PnL, hit rate, and max drawdown per house rules.

## 2. Why this is uncontaminated (the crux)

- Model training cutoff is **January 2026**; all evaluated markets resolve **June–July 2026**. Outcomes cannot be memorized.
- The forecaster gets **no web access** in retrospective mode — retrospective news search would leak outcomes. Context comes only from ASADO surfaces filtered to `date <= t` (the warehouse is PIT-disciplined already: WEO vintages, PIT edges, harness embargo conventions).
- The context-pack builder must be audited for lookahead the same way `evaluate_signal.py` treats embargo: any series joined into the pack is filtered `as_of <= t` **at the row level**, and the pack is hashed + logged per forecast.
- Residual risk (accepted, documented): monthly-frequency warehouse rows stamped first-of-month can embed intra-month revisions. Mitigation: prefer the daily-frequency tables and the loop DB's vintage-aware layers for the pack.

## 3. Corpus

**Retrospective (bootstrap, runs now):** closed Polymarket events in ASADO-relevant tags — `economy`, `geopolitics`, `fed-rates`, `inflation`, `oil`, `world` (measured 2026-07-03: ~400–700 markets/tag resolved in the trailing 30 days). Constraint discovered in Tier 1: **`/prices-history` purges after ~30 days**, so the retrospective window is exactly the trailing month — `p_mkt(t)` is recoverable only there. Outcomes (`outcomePrices`) persist indefinitely.

- Reuse `backtest_overnight_pull.py`'s enumeration + history-pull pattern with a tag list instead of `stocks`.
- Filters: binary contracts, volume ≥ $1,000, resolution_clarity screen (rules_text must name an objective source — reuse the `predmkt_curated.yaml` clarity convention), dedup near-identical strikes to ≤3 per event (keep most liquid), and **drop markets already effectively resolved at t** (`p_mkt` outside [0.05, 0.95]) — beating a 0.99 market by echoing it is not evidence.
- Forecast times: t = resolution − {7d, 3d, 1d}. Target ≈ 200–400 unique markets × 3 horizons after filters.
- **Exclusions:** sports, crypto price levels, pop culture — no ASADO edge is hypothesized there; including them dilutes the test of the actual hypothesis.

**Live shadow (gold standard, starts immediately):** every day, forecast all **active** markets in the same tags at the same horizons, write forecasts to the loop DB *before* resolution, score on resolution. Zero contamination by construction. The retrospective corpus decides whether to keep paying for the live loop; the live loop decides whether to trade.

## 4. The forecaster

- Models (a panel, `model` is a harness parameter):
  - `claude-sonnet-5` — primary fleet, full corpus, all 3 arms. (Sonnet 5 per Arjun 2026-07-03 — supersedes the sonnet-4-6 snapshot in CLAUDE.md; verify IDs via Context7 at build time.)
  - **DeepSeek V4 Pro** (via OpenRouter) — full corpus, all 3 arms: head-to-head vs Sonnet 5. Tests whether any edge is Claude-specific or generic frontier capability — i.e., whether the moat is the model or the warehouse.
  - `claude-fable-5` — 50-market subsample, measures the within-family model-quality gradient.
- Context pack (arm A1): built per market by keyword/category mapping from the market's question + tags to warehouse surfaces — e.g. an oil-strike market gets recent WTI/Brent levels + curve features + Hormuz-adjacent dislocations; a Fed market gets WIRP/OIS, CPI, eco-surprise series; a geopolitical market gets GPR, GDELT tone, event log. Cap ~4k tokens. The mapping table is versioned config (`config/brier_gate_context_map.yaml`).
- Prompt: forecast as a probability with a short rationale; **k=5 samples, median aggregated** (cheap ensemble); temperature 1.
- Cost envelope: ~1,000 market-horizon forecasts × 3 arms × 5 samples ≈ 15k calls per full-corpus model. Sonnet 5 ≈ $30–80; DeepSeek V4 Pro ≈ $5–15 (OpenRouter); Fable subsample ≈ +$40. Immaterial.

## 5. Outputs & infrastructure

- `scripts/brier_gate/` (new): `build_corpus.py` (enumerate + histories + outcomes → parquet), `build_context_packs.py`, `run_forecasts.py` (incremental JSONL writes per forecast — resumable, per house persistence rules), `score.py` (Brier/log-loss/calibration/PnL + xlsx + md report).
- Results → `Data/work/brier_gate/`; report → `docs/BRIER_GATE_RESULTS_{date}.md`; hypothesis registered in `ledgers/` per loop discipline.
- Live shadow: one table in **the loop DB** (`Data/loop/asado_loop.duckdb`, never the rebuilt main DB): `brier_gate_forecasts(forecast_ts, platform, market_id, horizon_days, arm, p_ai, p_mkt, bid, ask, context_hash, model, resolved_value, brier_ai, brier_mkt)`. Daily job step appended to `predmkt_equity_daily_job.py` or a sibling.

## 6. Gate criteria (decided before running)

**PASS** (proceed to sizing a real PM trading loop) requires ALL of:
1. Arm A1 mean Brier < market Brier on the retrospective corpus, bootstrap 95% CI excluding zero, clustered by event;
2. The edge survives economically: threshold-rule PnL > 0 **after crossing the observed spread**, at ≥1 (θ, horizon) cell that holds in both halves of a time-split;
3. A1 beats A0 (the warehouse adds value beyond the raw model — otherwise we're just reselling Claude and have no moat);
4. The result is not driven by one event cluster (leave-one-event-out).

**FAIL** → write it up, keep only the (near-free) live shadow logging, revisit when models or warehouse coverage improve.

**Ambiguous** (statistical edge, no economic edge) → extend live shadow 4–8 weeks before deciding; do not trade.

## 7. Risks & honesty notes

- **Thin-book PnL is partly fictional:** the "trade at bid/ask" simulation ignores our own impact on $2k-depth books, and quotes may be stale exactly when mispriced. Treat PnL as an upper bound; the live loop with real quotes (and eventually tiny real orders) is the only true test.
- **Self-selection:** markets that survive liquidity + clarity filters are the ones the crowd prices best — the residual edge may live in murkier contracts we screened out. Log the screened-out population size.
- **The startups' claims are unaudited.** This experiment does not assume they're right; it tests whether *our* specific edge exists.
- **30-day retrospective window is one macro regime.** A pass here is a green light for the live shadow, not for capital.
