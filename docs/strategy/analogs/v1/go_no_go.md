# Strategy #1 — World-State Analog Country Selection (v1 MVP)
## Phase 1 Go / No-Go Memo

**Decision:** **NO-GO for v1 as specified.**
**Date:** 2026-04-19
**Author:** Arjun Divecha (with Claude)
**Model version:** `v1-mvp-2026-04`

---

## 1. Hurdle and headline result

Per user direction (2026-04-19), the hurdle is:

> `analog_ann_return − equal_weight_ann_return ≥ 6.00% / yr`, gross of costs,
> evaluated over the analog-traded window (long-only top-7, monthly rebalance).

Backtest window: **2008-12-01 → 2026-03-01** (208 realized months).
Common comparison window for both strategies (analog skips ~10 months at the
start while its analog library fills to k=10).

| Strategy            | Ann. return | Ann. vol | Sharpe | n months |
|---------------------|------------:|---------:|-------:|---------:|
| analog_top7         |    **9.42%**|   18.54% |   0.51 |      208 |
| equal_weight (aligned) |    9.61% |   16.78% |   0.57 |      208 |
| **excess vs EW**    |   **−0.19%**|        — |      — |        — |
| **target excess**   |    **+6.00%** |       — |      — |        — |
| **verdict**         |   **FAIL**  |        — |      — |        — |

The analog strategy did not beat equal-weight at all on this window, let alone
clear the +6% hurdle.

---

## 2. Subperiod breakdown

| Window     | Analog ann | EW ann | Excess  | Months |
|-----------|----------:|-------:|--------:|------:|
| 2008-2012 |    +26.19% | +19.51%| **+6.68%** |     49 |
| 2013-2017 |     +7.44% |  +6.59%|  +0.85% |     60 |
| 2018-2022 |     −1.11% |  +1.58%|  −2.69% |     60 |
| 2023-2026 |     +9.90% | +15.37%|  −5.47% |     39 |

Story: the analog strategy nailed the GFC era (2008-2012) — exactly the period
its training library has the most relevant precedents for. After that the
edge collapses and reverses; in the most recent four years it has been a
material drag versus the simple benchmark.

---

## 3. PIT discipline

All eight automated PIT and structural tests pass
(`pytest scripts/strategy/analogs/tests/test_pit.py`):

- No forecast variables (`IMF_WEO_*`, `BBG_ECFC_*`) leaked into the worldstate.
- No variable with >40% missingness leaked into the worldstate.
- Every analog precedes its decision date by ≥ MIN_LAG_MONTHS = 12 months.
- No analog match has `analog_date ≥ decision_date`.
- Each decision date has all 34 country rows; ranks 1..34 present where scored.
- Softmax weights sum to 1.0 within each decision date.
- Decision dates respect `BACKTEST_START = 2008-01-31`.

PIT audit summary: 229 `_CS` variables → 142 admitted, 87 excluded
(8 forecast, 79 high-missingness). Year-lag caveat on 4 (HDI / ND-GAIN);
GDELT partial-month caveat on 46.

---

## 4. Face-validity spot checks

Top-7 holdings and top analog dates at ten reference dates. The analog set
generally maps to plausible regimes — the issue is forward-return value, not
the worldstate itself.

| Decision  | Top-7 (long-only)                                           | Top-3 analog dates (similarity)               |
|-----------|-------------------------------------------------------------|-----------------------------------------------|
| 2009-03   | ChinaA, ChinaH, Denmark, Brazil, Canada, Thailand, Spain     | 2008-01 (.38), 2007-12 (.27), 2007-09 (.25)   |
| 2011-09   | ChinaA, ChinaH, Poland, Australia, Brazil, Thailand, Germany | 2007-05 (.80), 2007-12 (.69), 2007-10 (.66)   |
| 2014-12   | Australia, Netherlands, Germany, U.K., Korea, Thailand, Spain| 2012-07 (.72), 2007-01 (.71), 2012-12 (.64)   |
| 2016-02   | Brazil, Turkey, Poland, Indonesia, Thailand, Singapore, Malaysia | 2007-04 (.86), 2011-10 (.76), 2007-02 (.74)|
| 2018-12   | Poland, Turkey, Denmark, Chile, Singapore, ChinaA, ChinaH    | 2007-02 (.79), 2010-03 (.77), 2017-04 (.75)   |
| 2020-03   | NASDAQ, US SmallCap, ChinaA, ChinaH, Brazil, Philippines, U.S. | **2008-10 (.88), 2008-11 (.82), 2008-12 (.60)** — clean GFC match |
| 2020-04   | Philippines, Mexico, Sweden, US SmallCap, U.S., NASDAQ, Singapore | 2010-03 (.92), 2018-06 (.85), 2018-07 (.83) |
| 2022-03   | Saudi Arabia, Mexico, US SmallCap, NASDAQ, Australia, Hong Kong, Denmark | 2012-12 (.84), 2008-03 (.79), 2008-02 (.77) |
| 2023-03   | Brazil, Philippines, Taiwan, ChinaA, Saudi Arabia, ChinaH, Indonesia | 2020-10 (.78), 2008-10 (.75), 2011-11 (.75) |
| 2024-08   | Philippines, Brazil, Thailand, US SmallCap, Canada, NASDAQ, U.S. | 2007-04 (.85), 2010-01 (.81), 2011-11 (.79) |

Mean top-k cosine similarity across the run: **0.669** (median 0.715, range
−0.68 → 0.95). The library finds genuinely similar regimes.

---

## 5. Diagnostics (other)

- Mean monthly turnover: **48.6%** (median 42.9%, max 100%). High but not
  unreasonable for a 7-name long-only book reshuffled monthly. Costs are out
  of scope per user direction; if a future phase adds them, this turnover
  multiplied by ~10–30 bps would erase another ~3–10% / yr easily.
- Score coverage: 98.4% of (date, country) cells have a score
  (analogs occasionally lack a forward return for a specific country).

---

## 6. Why v1 falls short — hypotheses (not fixes yet)

The strategy passes every PIT and structural test; the worldstate finds
sensible analogs; the failure is in the *forecasting power of the analog set*,
not in the plumbing. Candidate causes worth exploring before any v2:

1. **Equal-weight is a strong benchmark for 34 names**, especially with
   double-counting of China (A+H) and U.S. (broad + NASDAQ + smallcap)
   pulling the EW basket toward whatever regime is winning. The +6% hurdle
   over EW gross is a *very* high bar.
2. **Forward 1-month return is mostly noise** at the country level. The
   similarity-weighted *median* is robust to outliers but probably also
   washes out the signal. Worth comparing to weighted mean and to a
   3-/6-month forward window.
3. **Top-7 is a quintile cut** — at 34 countries it concentrates too much.
   Top-10 or top-13 (third) may both diversify away the noise and come
   closer to EW (which is itself part of the problem).
4. **Library is too small** in early years (10 analogs only by ~Nov 2008).
   The decline from 2018 onward could partly reflect the worldstate drifting
   into regimes the library has never seen (post-COVID liquidity, US tech
   concentration, AI-era multiples) — i.e. the analog premise breaks when
   "this time is different" is actually true.
5. **No forecast-revision-safe macro variables.** All forecast (`IMF_WEO_*`,
   `BBG_ECFC_*`) variables were excluded as PIT-unsafe. A vintage archive
   would let those back in and likely sharpen state discrimination.

None of these are committed work — they are the agenda for a v2 conversation.

---

## 7. Recommendation

- **Do not promote v1 as-is.** It does not clear the hurdle.
- **Keep all artifacts** — `Country_Forecasts.xlsx`, the parquet trail, the
  audit, and the PDF — as the baseline for any v2 comparison.
- **Decide explicitly with the user** before sweeping parameters; the v1 PRD
  was scoped as "build the harness, run it once, see what we get." That has
  been done. The next step is a *strategy* conversation, not an
  *engineering* one.

---

## 8. Artifact index

All under `Data/strategy/analogs/v1/`:

| File                     | Rows | Purpose                                   |
|--------------------------|-----:|-------------------------------------------|
| `pit_audit.csv`          |  229 | Per-variable PIT classification           |
| `worldstates.parquet`    |  257 | PCA-reduced worldstate vectors per date   |
| `analog_matches.parquet` | 2110 | Top-10 analogs per decision (211 dates)   |
| `signals.parquet`        | 7174 | Score & rank per (date, country)          |
| `baselines.parquet`      |  314 | Equal-weight benchmark monthly returns    |
| `backtest.parquet`       |  208 | Long-only top-7 monthly P&L               |
| `Country_Forecasts.xlsx` |    — | T2_Optimizer-style wide forecast workbook |
| `diagnostics.pdf`        |    — | Cumulative curves, rolling excess, similarity timeline |
