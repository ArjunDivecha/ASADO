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

---

# One-day country-ETF reversal on its own (2026-10-05, `etf_reversal_1d.py`, run `runs/reversal_20261005_201709`)

**Setup.** The 34-ETF house universe. Each day, rank the ETFs by that day's return.
Buy the losers quintile and short the winners quintile, held one day, gross,
against the equal-weight benchmark. The pre-registered primary spec enters at the
next open (E3).

**Result.** The effect is real, but nearly all of it happens overnight: from day
T's close to the next morning's open (long-short Sharpe 2.3 on that leg alone). It
comes from the Asia-Pacific and Europe/Africa/ME ETFs. The Americas contribute
nothing overnight. The likely mechanism is that ETFs priced in US hours, while
their home market is shut, overshoot, and the next open, after the home market has
traded, corrects part of the move. Consequences:
- **Enter next open (primary E3):** Sharpe 0.95 full period, 0.61 over the last 5y
  (t 1.4). Long-only losers vs equal-weight: +7.7%/yr over the last 5y (IR 0.97).
  The edge is weak once the overnight leg is gone.
- **Enter at the close of the signal day (E1):** Sharpe 2.2 full, 1.2 over the last
  5y. The implementable form is a 15:30 ET signal executed at the close (MOC). Over
  2023-11 to 2026-10 that version kept a Sharpe of 1.63 (t 3.0) against 1.96 for
  the idealized version. Long-only losers vs equal-weight: Sharpe 1.99 (t 3.7).
- **A dead decade:** even the close-entry version earned about zero from 2010 to
  2019. Returns concentrate in high-volatility, high-dispersion periods (2000-09,
  2020-26). Part of that is mechanical, because high-dispersion days produce
  bigger spreads.
- **Robustness (close entry, last 5y):** the surface peaks at a one-day lookback and
  declines smoothly with longer lookbacks; a 1-2 day hold is best. Residualizing
  against the market hurts. Leave-one-ETF-out keeps the 5y Sharpe between 1.0 and
  1.4.
- **Turnover (information only, not a gate):** the long-short book trades about
  3.2x capital a day. Gross edge is about 2bp per dollar traded. Closing-auction
  spreads on the thin ETFs are the implementation question that decides whether
  this can be harvested.

---

# Sweep: fewer names, and size thresholds (2026-10-05, `etf_reversal_sweep.py`, run `runs/sweep_20261005_202512`)

147 cells: three measures (raw move; move in own trailing-60d sigma; move relative
to the group in own sigma), seven size thresholds (k = 0 to 3 sigma), and seven
name caps (1, 2, 3, 5, 7, 10, all). Each cell was run on E1 (idealized close
signal, 2000-2026) and E5 (15:30 signal executed MOC, 2 years). The bootstrap
reality checks are in the xlsx. The sub-period table is in `subperiod_check.txt`.

- **Size thresholds don't help.** Over the full history, Sharpe falls steadily as
  k rises. Recently it is flat. The trade works on ordinary days, not just on big
  moves.
- **Fewer names means more return, with proportionally more risk.** Recently, one
  name chosen by relative move in own sigma has the best Sharpe: 2.63 on E5 vs
  1.99 for the baseline, and 2.29 vs 1.89 on E1 2023-26. It earns about 44%/yr
  active over the last 5y vs 35% for the baseline levered to the same vol. Over
  2000-09, concentration was clearly worse (1.60-3.77 vs 2.93-5.54). The surface
  is unstable: the rank correlation of cell Sharpes between the full history and
  the last 5y is 0.06.
- **If concentrated, rank by vol-scaled relative move, not raw move.** That beats
  raw ranking at one name in 5 of 6 sub-periods and in E5.
- **No variant fixes 2010-2019.** Every rule is negative in 2010-14.
- **Reality check:** the best recent cell is real against zero (p 0.004). Its edge
  over the baseline in mean return (p 0.011) mostly reflects concentration buying
  return with risk. E5 and E1-5y overlap in time, so they are not independent
  confirmation.

---

# Raw vs vol-scaled loser selection (2026-10-05, `etf_reversal_volscaled.py`, run `runs/volscaled_20261005_203112`)

The only difference between the two methods is dividing each ETF's move by its
own trailing-60d volatility.
- **One name:** vol-scaled improves full-period Sharpe from 1.19 to 1.53
  (bootstrap CI of the difference 0.07 to 0.61, p 0.006). Over the last 5y it goes
  from 1.29 to 1.92 (CI 0.02 to 1.30). On E5 it goes from 2.15 to 2.63, but that
  is not significant (CI −0.46 to 1.38). The gain comes mostly from lower vol
  (23% vs 26%). Return improves only 3.6%/yr (t 1.0). There is no difference in
  2010-19, and raw was better over the most recent 12 months.
- **Two or three names:** a smaller version of the same gain over the full period
  (+0.26 Sharpe, p about 0.02). At three names it loses on E5.
- **Seven names:** no gain, and recently worse. E5 falls from 1.99 to 1.14, with
  the CI entirely below zero. Vol-scaling is only a refinement for concentrated
  books.
- **Mechanism confirmed:** raw single picks average 29% own vol vs 23% for the
  universe, led by EWZ, TUR, EZA and VNM (TUR and VNM top over the last 5y).
  Vol-scaled picks average universe vol but tilt toward normally calm funds (KSA,
  INDA, EWM, EPHE), where a modest drop counts as big.
- The house net-drawdown metric explodes (into the hundreds) at these return
  levels because the cumulative-gap measure compounds. Ignore it for these books.

---

# External review: GPT-5.6 Sol, high effort (2026-10-05) — `GPT_REVIEW_2026-10-05.md`

GPT's verdict: "keep the reversal as a credible research observation; reject the regional story and
the optimized-rule confidence; do not deploy it." It independently reproduced the `1DRet` fix, the
decay of the local leg, and the overnight concentration.

**Accepted and fixed:**
- **Look-ahead in eligibility.** The day-T universe was filtered on `fwd.notna()` in the sweep,
  vol-scaled and cost scripts. Removed. GPT measured an effect on fewer than 1% of days.
- **Dividend credited after the ex-date** in the "enter at 15:30" variants
  (`etf_gap_fill_intraday.py`, `etf_reversal_1d.py`). Fixed. GPT puts that variant at Sharpe about
  1.69, down from 1.86. The MOC result is unaffected.
- **Wrong claim** that vol-scaling differs from raw only by dividing by vol. Mean subtraction does
  change the ranking once each name is divided by its own vol. Docstring corrected.
- **"Pre-registered" overstated.** The spec was a comment in the script, not a frozen ledger entry.
- **The p = 0.006 for one-name vol-scaling is post-selection.** The rule was chosen from the
  147-cell sweep first, so it is not independent confirmation.
- **The Yahoo "15:30" price is the first trade anywhere in 15:30-16:00**, which for thin ETFs can
  be near the close. It is being rebuilt from Bloomberg 1-minute NBBO (15:29 midpoint):
  `intraday_execution.py`.
- **The full-history test uses today's surviving funds**, with 17-22 names before 2016 and no
  liquidated ETFs. Early Sharpes mix stale pricing, changing breadth and survivorship. Not yet
  fixed: it needs a point-in-time ETF list.

**Disputed:** GPT said the regional overnight split and the leave-one-out figure (1.0-1.4) were
never tested. Both were tested, ad hoc in session, and are now persisted in
`reversal_robustness_checks.py` (run `runs/robustness_20261005_233049`). The overnight leg comes
from Asia +16.0%/yr and Europe/Africa/ME +13.5%/yr, Americas −0.8%/yr. Leave-one-out 5y Sharpe is
1.00-1.38 for close entry and 0.43-0.70 for next-open entry.
