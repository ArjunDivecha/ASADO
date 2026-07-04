# Overnight PM → Equity Signal — Status (Tier 1, M1 + M2 + M5)

**Date:** 2026-07-03 (M2 added same day)
**PRD:** Tier 1 Overnight Prediction-Market → Equity Signal (Li & Wang 2026 §5.2)
**Verdict so far:** Gate 1 (information content) **PASSES**. Gate 2 (realizable capture) **FAILS on the available sample** — the gap is fully priced by the US open. One month of data only; see "hard data constraint" below.

---

## What was built

| Component | File | Status |
|---|---|---|
| Shared parser / direction cleaning | `scripts/predmkt_equity_common.py` | ✅ 6 contract classes, validated on 11,418 markets (84% parsed; rest are non-directional buckets, excluded by design) |
| M1 universe discovery | `scripts/discover_predmkt_equity_universe.py` → `config/predmkt_equity_universe.yaml` | ✅ 854 directional markets, 19 tickers, 247 active by volume; `--validate-only` supported; regenerate weekly |
| M5a historical PM pull | `scripts/backtest_overnight_pull.py` → `Data/work/predmkt_equity/markets.parquet` + `history/*.parquet` | ✅ 9,112 closed directional markets enumerated; 8,221 histories pulled (10-min fidelity), 0 failures; resumable cache |
| M5b equity bars | `scripts/pull_overnight_equity_bars.py` → `Data/work/predmkt_equity/equity_bars.parquet` | ✅ Bloomberg daily open/close, 19 tickers, 2026-03-20 → 2026-07-03 |
| M5c event study + PnL | `scripts/backtest_overnight_signal.py` | ✅ Both windows run (paper 12:30–15:30 UTC; tradeable pre-13:30) |

Universe tickers: AAPL AMZN GOOGL META MSFT NVDA TSLA MU PLTR NFLX OPEN COIN HOOD ABNB RKLB MSTR + ETFs SPY QQQ EWY SPCX.

Contract classes: `hit_high` / `hit_low` (weekly+monthly touch barriers), `close_above_daily` ("close above $X on {date}"), `close_above_period`, `finish_week_above`, `up_or_down` (daily). Direction cleaning: only `hit_low` inverts (aligned p = 1 − p_yes).

## Hard data constraint discovered

**Polymarket's CLOB `/prices-history` retains only ~30 days.** April/May market tokens return empty for any parameter combination (`interval=max`, explicit `startTs/endTs`). The backtest sample is therefore **June 2026 only: 7,507 market-night pairs, 2,353 contracts, 19 trading days**.

Consequence: the M2 intraday poller is not just live-signal infrastructure — it is the **only** way to accumulate a longer backtest sample. Every week of delay loses a week of history forever.

## Gate 1 — event study (PASSES)

Regression: realized overnight gap `ln(open_{d+1}/close_d)` on aligned overnight PM move `Δp`, contract FE (ticker FE for one-shot daily contracts), SEs clustered by contract and by day. Paper window; pre-open window results are near-identical — **the signal is fully formed before 13:30 UTC**.

| Spec | γ | t (contract) | t (day) | R² | n |
|---|---|---|---|---|---|
| All contracts (FE) | 0.027 | 9.2 | 3.1 | 0.025 | 7,507 |
| Daily classes (ticker FE) | 0.042 | 11.7 | 5.9 | 0.196 | 1,007 |
| — up_or_down alone | 0.085 | 11.0 | 9.7 | 0.400 | 308 |
| Ex-weekend | 0.044 | 7.5 | 2.7 | 0.037 | 5,895 |
| **Placebo (next-night gap)** | −0.003 | −0.9 | −0.5 | 0.000 | 5,154 |

Paper's γ ≈ 0.076 with R² 7–10%. Our all-contract γ is smaller (weekly barrier contracts dilute), but the **daily contracts replicate at or above the paper's numbers**, and the placebo is cleanly null. The information lead is real on our own collected universe.

## Gate 2 — realizable PnL (FAILS so far)

Equal-weight sign(Δp) portfolios, one signal per ticker-day (volume-weighted across contracts), June 2026 (19 trading days — small!).

- **Gap leg (diagnostic, NOT tradeable):** Sharpe 15–19 gross across θ grid. Confirms information content; you cannot trade the prior close retroactively.
- **Open→close continuation (tradeable), paper window:** Sharpe 1.4 gross at θ=0 → **−0.1 at 5 bps one-way**. Negative at every θ ≥ 0.01 net.
- **Open→close, pre-open signal variant:** Sharpe 0.23 gross at θ=0, negative net everywhere. Max drawdowns −2% to −7% on the month.

**Interpretation:** identical to the Alpha Book diffusion finding — the edge dies at the tradeable moment. The overnight PM move predicts the gap, and the opening auction prints the entire move. There is no post-open continuation to harvest, net of even 2 bps, in June 2026 data.

## Artifacts

- `Data/work/predmkt_equity/backtest_results_2026_07_03_paperwindow.xlsx` / `_preopen.xlsx` — full regression + PnL grids + equity curves
- `docs/OVERNIGHT_SIGNAL_BACKTEST_2026_07_03_paperwindow.md` / `_preopen.md` — per-run auto-reports
- `Data/work/predmkt_equity/overnight_pairs_*.parquet` — the pair-level dataset

## M2 — data accumulation layer (BUILT & SCHEDULED, 2026-07-03)

Two scheduled jobs, both verified end-to-end:

| Job | Script | Schedule | What it does |
|---|---|---|---|
| Intraday poller | `scripts/poll_predmkt_intraday.py` | launchd `com.arjundivecha.asado-predmkt-equity-poller`, every 10 min (self-gates to weekday 19:30–23:30 & 12:30–15:30 UTC) | Polls CLOB books for active **daily-class** contracts (up_or_down, close_above_daily — the signal-bearing families); writes per-cycle parquet to `Data/work/predmkt_equity/intraday/` with aligned mid, bid/ask, spread, depth, staleness. `--all-classes` widens; `--force` overrides the gate. |
| Daily harvest | `scripts/predmkt_equity_daily_job.py` | launchd `com.arjundivecha.asado-predmkt-equity-harvest`, daily 16:45 local | (1) regenerates the universe YAML (market rotation), (2) `backtest_overnight_pull.py --refresh-active`: harvests newly-closed markets' histories AND merge-refreshes all active markets' histories before the ~30-day purge. **This is the history accumulator.** Logs: `Data/logs/predmkt_equity_daily.log`. |

First harvest run: 493 new closures pulled, 248 active histories merged, 0 failures.

## Recommendation / next steps

1. **Do not trade this yet.** Gate 2 fails on the available sample; the PRD's biggest stated risk materialized exactly as flagged.
2. ~~Build M2~~ **Done** — history is now accumulating daily; the 30-day purge no longer costs sample.
3. Re-run Gate 2 after 2–3 months of accumulated data with minute-bar equity data (Bloomberg IDH) to test finer capture windows (first 5/15/30 min), pre-open positioning in the PM contract itself, and MOO open-auction participation.
4. M3 (signal builder) and M4 (MCP surface) are deferred until a Gate 2 re-test justifies them.
