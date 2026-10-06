# ETF gap-fill — corrected test (2026-10-05)

**Question.** When a country's local index and its US-listed ETF move by different
amounts on the same day, does the ETF catch up over the next days?

**Answer.** On the next day it partly does, but the part that comes from the local
market has decayed to almost nothing. What survives today is a one-day,
cross-sectional reversal of country ETFs. It needs no local data. It is still
tradeable with a 15:30 ET signal over the last two years (gross long-short
Sharpe about 1.5, t about 2.8).

## Why the earlier result (`scripts/analysis/etf_lag_*`, `Data/analysis/etf_lag*`) is void
1. T2 `1DRet` is a **forward** return. The row dated D holds the next trading day's
   return, e.g. the row dated Sun 2024-08-04 holds Japan's −10% of Mon 08-05. The
   "same-day gap" therefore compared tomorrow's local move with today's ETF move.
2. T+1 and T+5 were computed after filtering to big-move days only, so "next day"
   meant the next big-move day.
3. "Gap closes 74%" counted an ETF move in either direction as closing.
4. Wrong tickers: EPP (Pacific ex-Japan) for Spain, FXI for ChinaA, and 'UK' instead
   of 'U.K.', which dropped Britain.

## Findings (daily panel, 31 countries, 2000-2026; run `runs/20261005_200625`)
- **Which side lags?** The ETF leads the local market (corr(ETF_t, local_t+1) is
  about 0.25 for Asia). The local market does not lead the ETF (about −0.01).
- **The gap predicts next-day ETF returns** (Fama-MacBeth slope 0.14, t 23). The
  local and ETF legs carry equal and opposite weight, so in the full sample it is
  a genuine gap effect. All 31 countries have a positive slope.
- **It is a one-day effect.** Entering at the T+1 close earns roughly zero over
  the last five years.
- **The local leg has decayed.** Its coefficient fell from 0.31 (2000-04) to 0.10
  (2015-19) to 0.03 (2023-26, t 2.0). The ETF-reversal leg decayed less, from −0.31
  to −0.06.
- **The long-short book** (top minus bottom gap quintile, held one day, gross) went
  from Sharpe 5.1 over the full period to 1.7 over the last five years and 2.1 over
  the last three. Pure ETF reversal matches it over the last three years (2.0).

## Implementability (15:30 ET signal, 2023-11 to 2026-10; run `runs/intraday_20261005_201055`)
| Signal (long-short, gross)              | Sharpe | NW t |
|---|---|---|
| Gap, ETF close (oracle, not tradeable)  | 1.74 | 3.1 |
| Gap @15:30, enter at close              | 1.21 | 2.1 |
| Pure ETF reversal @15:30, enter at close| 1.55 | 2.8 |
| Pure ETF reversal @15:30, enter @15:30  | 1.71 | 3.1 |
| Local return only                       | −1.02 | −1.8 |

Over this window, once the ETF move is controlled for, the local leg is
insignificant (t 0.8).

## Caveats / next steps
- Two years of intraday data only, and the full-sample statistics are dominated
  by the stale-pricing era (2000-04).
- T2's FX fixing time is undocumented. The pure-reversal variants do not use T2
  data and are immune to it.
- Turnover is very high (daily quintile rebalance). Per house rules this is not a
  research gate, but an implementation-time check of closing-auction spreads on the
  thin ETFs (EPHE, TUR, KSA, VNM, THD) is the obvious next step.
- Prior art: short-term reversal in country ETFs is HOLDS_BOTH in our Quantpedia
  screen (#0013, #0382) at weekly or monthly horizons. QP #1070 (FXI overnight
  comovement) has decayed out of sample.
