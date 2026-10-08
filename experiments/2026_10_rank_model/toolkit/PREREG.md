# Pre-registration: rung B — the fundamental-forecast toolkit and its mechanical comparator

Written 2026-10-08 00:20, before any head or comparator was fitted. Amendments go at the bottom, dated.

## Why (one paragraph)

The default model learns a direct line from today's factors to next month's return, and that line is nearly all noise
(signal-to-noise about 0.13 a month). Next-month *changes* in fundamentals are five to twenty times more learnable from
the same inputs. Rung B splits the job: heads forecast the predictable changes; a small second-stage model asks whether
the market has priced them. The hindsight ceiling (`results/ceiling_20261008_001652/`) shows the action space is not the
constraint: one perfect swap a month would add 23% a year, 11% even confined to the names around the cut-off, so a rule
with about 4% of perfect skill adds 1% a year. The question is purely whether the heads carry information the default
does not already use.

## Data and window

Cleaned v3 panel (238 factors, 34 countries, 2000-02 → 2026-09), first-of-month dates, `fwd_excess` target as in the
default. Rolling 60-month training window throughout (tested 2026-10-07; recency-weighted all-history was no better and
far less stable). Nothing from the GDELT family is a target.

## Stage 1 — the heads

**Targets.** For each variable v, the next-month change in its time-series z-score as stored in the panel:
`y_v(D) = z_TS(v)(D+1) − z_TS(v)(D)`. Variables (the panel's names): `Trailing EPS_TS`, `BEST EPS_TS`, `LT Growth_TS`,
`Best ROE_TS`, `IMF_CPI_Inflation_YoY_TS`, `20 Day Vol_TS`, `BBG_Govt_Bond_10Y_TS`. Seven heads. (Cross-sectional
z versions are reported as a secondary target form where the panel has them.)

**Model.** Rolling-60 ridge with month-grouped cross-validated alpha on all 238 factors, exactly the `fit_ridge` used
by the default's comparator, one head per target. Deterministic, so one draw. (A seed-ensemble MLP head is a
possible stage-1b if the ridge heads survive; not part of this registration.)

**Baselines each head must beat** (same walk-forward, same months): (a) zero change; (b) persistence, `y_v(D−1)`;
(c) AR(1) on the variable's own last twelve changes. Score: out-of-sample cross-sectional rank IC between forecast and
realised change, averaged over months, with a paired t against the best baseline.

**Survival rule.** A head survives if its mean OOS rank IC exceeds the best baseline's by at least 0.05 with a paired
t ≥ 2.0 over the OOS months. Heads that do not survive are dropped from stage 2. If no head survives, rung B stops and
the result is reported as such.

## Stage 2 — the comparator

**Inputs.** The default model's pooled out-of-sample score (three draws averaged, available 2005-02 onward) and the
surviving heads' out-of-sample forecasts. Nothing else.

**Model.** Rolling-60 ridge on the inputs with target `fwd_excess`, month-grouped CV alpha, trained only on months
where the default score is itself out of sample, so the comparator's OOS record starts 2010-02 (about 200 months).

**Rules.** *Primary:* **full re-rank** — form the basket from the comparator's score with the default rule (top 8, hold
while ranked ≤ 16). *Secondary:* one-swap and two-swap variants — start from the default basket and make at most k
swaps where the comparator's ranking disagrees most. Also a heads-only comparator (without the default score) to show
whether the toolkit ranks on its own.

**Comparison.** Paired monthly excess of B minus A (the default, same months 2010-02 → 2026-09), annualised, with its t;
on the pooled scores and on each of the three draws separately (comparator refitted per draw). Also IR, turnover,
by-period excess, and the correlation of B's and A's monthly excess.

**Controls.** (i) Shuffled heads: permute each head's forecasts across countries within each month, 200 times, rerun
stage 2 → null distribution of the paired t. (ii) Default-score-only comparator (ridge on the default score alone) to
confirm the second stage adds nothing by itself.

## Decision

B replaces A as the default only if the primary (full re-rank, pooled) beats A by paired t ≥ 2.0, is ahead in all
three draws, and its t exceeds the 95th percentile of the shuffled-heads null. Otherwise A stays; the result is
reported with the realised interval, and "inconclusive" is used only when the interval still admits +1% a year.

## Not allowed afterwards

No new targets, head models, rules or windows after seeing results; secondaries cannot rescue the primary; no cost or
turnover gating. Head survival is judged before stage 2 is run, and the surviving set is written to the run log.

## Amendments

(none)
