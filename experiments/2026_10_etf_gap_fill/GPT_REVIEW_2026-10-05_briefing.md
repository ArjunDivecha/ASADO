# Adversarial vet request: one-day country-ETF reversal (gross, research stage)

You are a skeptical quant reviewer. Try to BREAK these results. Read the code (read-only) in:
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/
Files: README.md (summary of all four studies), etf_gap_fill.py, etf_gap_fill_intraday.py,
etf_reversal_1d.py, etf_reversal_sweep.py, etf_reversal_volscaled.py.
Cached data is in /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/ (parquet) and run outputs in /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/runs/ (log.txt, summary.json, xlsx)
-- you may open them with python/pandas read-only to check things.

## Context
- Universe: 34 US-listed country ETFs (EWS EWA EWC EWG EWJ EWL EWU QQQ SPY EWQ EWN EWD EWI ASHR ECH
  EIDO EPHE EPOL IWM EWM EWT EWW EWY EWZ EZA EDEN INDA MCHI EWH THD TUR EWP VNM KSA).
- Prices from Yahoo via yfinance: daily auto_adjust=True OHLCV since 1999-12; 60-minute bars
  (period='730d', prepost=False) whose index is converted to America/New_York; we take the OPEN of
  the bar stamped 15:30 as "price at 15:30 ET". Daily unadjusted closes + dividends for the
  intraday test.
- House rules: gross returns, no cost/turnover penalty in research (costs are an
  implementation-time question, but tell us honestly whether the edge is harvestable).

## Claims to attack
1. T2 '1DRet' in the warehouse is a FORWARD return (row dated D = return realised next trading
   day; e.g. row dated Sun 2024-08-04 holds Japan's -10% of Mon 2024-08-05), so a previous
   session's "ETF lags local" analysis was void. We realign: realised local return on calendar
   day d = 1DRet dated d-1, compounded over each US ETF close-to-close interval.
2. With correct alignment, the local-minus-ETF gap predicts next-day ETF return (Fama-MacBeth
   slope ~0.14, t~23 full sample) but the LOCAL leg decayed to ~0 (2023-26 coef 0.03, t 2.0);
   what survives is plain one-day cross-sectional reversal of the ETFs' own returns.
3. Reversal edge is overnight: long losers quintile / short winners quintile, signal at close T:
   close->close Sharpe 2.17 full / 1.22 last 5y; enter next open (open->open) only 0.95 / 0.61;
   overnight leg alone Sharpe 2.29. Overnight contribution comes from Asia and Europe ETFs,
   ~zero from Americas. The whole thing earned ~0 in 2010-2019.
4. Implementable version: signal = yesterday close -> 15:30 ET price, enter MOC, exit next close.
   Over 2023-11-06..2026-10-05 (723 days): long-short Sharpe 1.63 (NW t 3.0) vs oracle
   close-signal 1.96; long-only 7 losers vs EW Sharpe 1.99.
5. 147-cell sweep (3 measures x 7 sigma thresholds x 7 name caps): size thresholds don't help;
   1 name ranked by (r - cross-sectional mean)/own trailing-60d std ("vol-scaled") has the best
   recent Sharpe (2.63 vs 2.15 raw on the 15:30 test); full-history (close-signal) Sharpe
   1.53 vs 1.19, stationary-bootstrap CI of the diff [0.07, 0.61], p 0.006; but at 7 names vol-
   scaling is worse (15:30 test 1.99 -> 1.14). Rank corr of cell Sharpes full-history vs last-5y
   = 0.06 (unstable surface). White-style reality check: best recent cell p 0.004 vs zero.

## Specifically hunt for
- Look-ahead anywhere: rolling std shift, signal/return row alignment in run_book/run_cell/
  quantile_weights (note E3 uses O.shift(-2)/O.shift(-1)), dividend add-back on ex-date in both
  signal and forward return in the intraday scripts, the 15:30 bar: is Yahoo's 60m bar stamped at
  its START (so OPEN of the 15:30 bar = 15:30 price) and does tz conversion/DST break this? Is
  there any chance the "15:30 price" actually leaks the close?
- Yahoo data quality: auto-adjusted opens (stale opens = prev close ~2% of days recently, 6% in
  2000-07), bad prints, holidays, ETFs with no trading, early ETF illiquidity (2000-04 numbers).
- Survivorship: universe is today's 34 tickers (RSX etc. not included); does it matter?
- Bid-ask bounce / closing-print noise inflating close->close reversal; does the 15:30 test
  actually remove it?
- Statistical: overlapping evidence (E5 window is inside the E1 5y window), best-of-147 selection,
  bootstrap implementation in etf_reversal_volscaled.py boot_sharpe_diff, the reality-check code
  in etf_reversal_sweep.py (studentisation, recentring).
- Harvestability: 7-name long-short trades ~3.2x capital/day for ~6.5bp/day gross (~2bp per
  dollar traded); 1-name long-only ~21bp/day gross active, ~1.9x turnover/day (~11bp per dollar).
  Thin funds dominate picks (TUR, VNM, EPHE, EIDO, KSA, EWZ). Closing-auction spreads/impact,
  MOC cutoffs (Arca vs Nasdaq), borrow for shorts. Is anything left?

## Deliverable
A verdict (does this survive? which claims are solid, which are fragile, which are wrong), each
finding with file:line references, and the 3 most important checks/tests we should run next.
Don't hedge.
