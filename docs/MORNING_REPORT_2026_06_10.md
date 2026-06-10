# Morning Report — Alpha-Hunting Loop Overnight Build

**Date:** 2026-06-10, built overnight 01:00–02:15
**Scope:** Phase 0 complete, Phase 1 complete, Phase 2 complete, first live hunt done.
**Spec:** `PRD_Alpha_Hunting_Loop.md`

---

## What now runs automatically every morning

| Time | Job (launchd) | What it does |
|---|---|---|
| 06:30 | `com.arjundivecha.asado-predmkt-daily` | Prediction markets: restore archive → collect → re-archive (rebuild-proof) |
| 06:45 | `com.arjundivecha.asado-loop-daily` | News bridge → thesis marking → country returns → graph features → **dislocation engine + daily brief** → ledger fold |

Your daily reading is one file: **`Data/dislocations/brief_YYYY_MM_DD.md`** — the ~50-row
dislocation table, open theses, and live book exposures. Today's first brief:
`Data/dislocations/brief_2026_06_09.md`.

Both jobs verified end-to-end tonight (full sequence runs in ~4s, all steps OK, idempotent on rerun).

---

## What was built (by phase)

### Phase 0 — foundations
- **Predmkt daily job** (`scripts/predmkt_daily_job.py`): wraps the collector in a
  restore→collect→archive cycle so monthly DB rebuilds can never destroy accumulated history.
  Archives to `Data/loop/predmkt_archive/`.
- **Vintage snapshotting** (`scripts/snapshot_vintages.py`): monthly copy of `Data/processed` to
  `Data/vintages/{YYYY_MM}/` with SHA256 manifest. First vintage (2026_06) saved; wired into
  `monthly_update.py`. Unlocks point-in-time research (detector D3) from next month forward.
- **`country_returns_monthly`** in the loop DB: 10,487 rows, 34 countries, 2000→present — the
  canonical marking/backtest surface.
- **`country_news` MCP tool** (`scripts/loop/country_news.py`): live GDELT DOC 2.0 headlines per
  country/day. Works (tested earlier tonight) but GDELT rate-limited our IP aggressively after
  repeated calls — tool fails loudly per FAIL-IS-FAIL and recovers when the block lifts.
- **News bridge** (`scripts/loop/collect_news_bridge.py`): your live book (70 holdings),
  portfolio summary, and 800-ticker ETF closes accumulate daily into
  `portfolio_holdings_daily` / `portfolio_summary_daily` / `etf_prices_daily` (199K rows),
  plus a curated `etf_t2_map` (34 countries → primary ETF). All archived to parquet.
- **Separate loop database**: everything above lives in `Data/loop/asado_loop.duckdb` with the
  main warehouse attached read-only — monthly rebuilds of `asado.duckdb` cannot touch loop state.

### Phase 1 — the skeptic (validation infrastructure)
- **Hypothesis ledger** (`ledgers/hypothesis_ledger.jsonl`, git-tracked, append-only):
  pre-registration with mechanism text hashed BEFORE results; per-family trial counting.
- **Thesis ledger** (`ledgers/thesis_ledger.jsonl`): frozen entry thesis, probability,
  invalidation level; auto-marked daily from T2 returns; mechanical close on invalidation/expiry;
  Brier calibration accumulates as theses resolve. Paper by default.
- **Evaluation harness** (`scripts/harness/evaluate_signal.py` + MCP `evaluate_signal`):
  PIT embargo enforced inside the harness, rank IC + Newey–West t-stats, top-7 vs EW with costs,
  sub-period stability, deflated Sharpe vs the family trial count, verdict auto-attached to the
  ledger. **Forward-return variables (`1MRet`, `12MRet`, …) are hard-blacklisted as signals** —
  this caught a real lookahead bug during the build (see "Errors caught" below).
- **PIT unit tests** (`tests/loop/test_harness_pit.py`): alignment lag-0/lag-1, horizon
  compounding, lookahead canaries (perfect-foresight IC=1, contemporaneous ≈ 0), NW-t, DSR. All pass.
- **MCP tools added**: `register_hypothesis`, `evaluate_signal`, `open_thesis`, `country_news`.

### Phase 2 — the eyes (Layer 1 deterministic assembly)
- **Graph feature factory** (`scripts/loop/build_graph_features.py`): Neo4j edges
  (TRADES_WITH, HAS_BANKING_EXPOSURE_TO, HOLDS_PORTFOLIO) × T2 daily returns →
  `graph_features_daily` (1.89M rows, 7 variables, 2008→present): trade/banking
  neighbor-return gaps (21d/63d), holder-stress, two-hop propagation.
- **Dislocation engine** (`scripts/loop/build_dislocations.py`): detectors live tonight —
  D2 (graph propagation), D4 (cross-asset incoherence), D5 (attention w/o resolution),
  D7 (factor crowding), D8 (stewardship: open theses + live book), D9 (index-vs-ETF gap).
  Blocked pending data: D1 (Comtrade ToT shares), D3 (needs ≥2 vintages), D6 (predmkt history
  accumulating from today). Status lifecycle (new/persisting/resolved) + severity z-scores +
  markdown brief, all idempotent.

---

## First hunt (from tonight's brief)

Market context: heavy Asia selloff June 3–7 (Korea −18% peak-to-trough), sharp bounce June 8 (+9% Korea).
The brief correctly surfaced post-crash network dispersion. Three **paper** theses opened, frozen at entry:

| ID | Position | Horizon | p | Invalidation | Mechanism (short) |
|---|---|---|---|---|---|
| T_20260610_001 | **Long Indonesia** | 42d | 0.58 | −7% | Trade partners repriced +12pp vs Indonesia (z +1.73); own 21d at −2.1z; propagation closes endpoint-ward. Book already long EIDO. |
| T_20260610_002 | **Long Hong Kong** | 42d | 0.55 | −7% | Partners outran HK by 6.1pp (z +2.09); own at −1.7z; HK is high-beta conduit for its network. |
| T_20260610_003 | **Short Taiwan** | 21d | 0.52 | −5% | Taiwan outran partners by 13.3pp (z −2.28) through the crash; relative leg vs the HK long. |

These auto-mark daily from T2 returns starting tomorrow; they close mechanically on invalidation or expiry.

**And one registered factor hypothesis put through the harness honestly:**

- `H_20260610_003` (family `graph_trade_gap`, archetype A2): trade-weighted neighbor 21d return gap
  → forward country returns. Daily cross-sectional rank IC 2008→present:
  **IC 0.019–0.034 across 5/21/63d horizons, NW-t 5.0–7.1, 79% positive years → verdict WATCH.**
  Honest caveats before any excitement: (a) graph weights are *today's* edges applied historically
  (not PIT — slow-moving but real); (b) daily mode is IC-only, no costs yet; (c) one family,
  trial #1 — deflated Sharpe discipline applies as the family grows.

---

## Errors caught and fixed overnight (the system working as designed)

1. **Lookahead caught by sanity check:** `12MRet`/`1MRet` in `feature_panel` are *forward* returns
   (optimizer targets), not trailing momentum. A naive momentum test produced IC 0.25 / Sharpe 2.9 —
   flagged as too-good, verified empirically, variables hard-blacklisted in the harness,
   hypothesis retired as DEAD in the ledger. The harness now refuses these as signals.
2. **D9 (index vs ETF gap) is window-misaligned in v1:** T2 daily carries weekend placeholder rows,
   so "last 5 rows" spans different economic days than NYSE-calendar ETF windows. Today's
   Korea/Indonesia D9 flags are this artifact, not signal (both surfaces saw the same crash+bounce).
   Brief already labels D9 as noisy; proper fix (calendar-aligned common-date windows) is a v1.1 item.
3. **`t2_levels_daily` staleness:** PX_LAST/Currency/10Yr Bond only register changes on the latest
   date; REER last changed 2026-04-30. This forced D4 (cross-asset incoherence) to return zero rows.
   Needs investigation in the T2 levels pipeline — flagged, not silently worked around.
4. **GDELT DOC API rate-limiting (investigated 04:40–05:40):** our IP is in an **extended penalty
   box** from the overnight testing — still HTTP 429 after a 25-minute fully-quiet period followed
   by a single request. Bisection ruled out User-Agent and individual query params. The danger
   pattern is that retries/probes appear to extend the block, so probing has been STOPPED entirely.
   `country_news.py` hardened: self-enforced 5s pacing between requests, fewer retries with
   60s/180s waits, and the error now instructs callers to stop for 15+ minutes. The tool worked
   correctly earlier in the night (returned real articles before the hammering), so expect it to
   recover on its own after hours of zero traffic — first real use later today is the test.
   If it still 429s tonight, options: route via a different egress IP, or fall back to the GKG
   raw files (`data.gdeltproject.org` bulk downloads, no rate limit) for headline URLs.

---

## Where everything lives

- Loop DB: `Data/loop/asado_loop.duckdb` (12 tables; holdings, ETF prices, graph features,
  dislocations, ledgers, harness results, country returns)
- Daily brief: `Data/dislocations/brief_2026_06_09.md`
- Ledgers (git-tracked): `ledgers/hypothesis_ledger.jsonl`, `ledgers/thesis_ledger.jsonl`
- Harness runs: `Data/loop/harness_runs/*.json`
- First vintage: `Data/vintages/2026_06/`
- Launchd jobs: `~/Library/LaunchAgents/com.arjundivecha.asado-{predmkt,loop}-daily.plist`
- Logs: `Data/logs/loop_daily_launchd.log`, `Data/logs/predmkt_daily_launchd.log`
- Tests: `tests/loop/test_harness_pit.py`

## Suggested next steps (your call, in rough priority order)

1. **Review the 3 paper theses** — they're frozen; agree/disagree/kill is itself calibration data.
2. **Fix `t2_levels_daily` staleness** (unblocks D4, the cross-asset detector).
3. **D9 v1.1**: calendar-aligned windows (turns the noisiest detector into a real one).
4. **Export-weighted ToT impulse (D1)**: needs bilateral trade shares by commodity — the
   archetype you ranked #1; IMF IMTS + Pink Sheet can approximate without Comtrade.
5. **Daily harness v2**: cost model + portfolio construction for daily signals, then re-run
   `graph_trade_gap` with full gates.
6. **PIT graph weights**: store monthly edge snapshots from IMTS/LBS vintages so graph features
   become honestly point-in-time.
