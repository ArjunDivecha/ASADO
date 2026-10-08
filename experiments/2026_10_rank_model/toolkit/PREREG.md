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

---

# B2a (2026-10-08 00:40, Arjun's choice): the head forecasts as six extra inputs to the default net

Written before any run. Motivation: stage 2 showed a fitted second stage hurts on its own, so the heads were not fairly
tested. Here there is no second stage: the default net is retrained exactly as it is, with the six surviving heads'
out-of-sample forecasts appended to its 238 inputs, and the net decides what they are worth.

**Panel.** `panel_v3_heads`: the cleaned v3 panel plus six columns `h_<head>` = the stage-1 head's out-of-sample
forecast (run `heads_20261008_001954`), cross-sectionally standardised within each month so they sit on the same scale
as the other inputs. Rows restricted to 2005-02-01 onward, the first month the forecasts exist, so every training
window sees real forecasts rather than zeros. The six columns carry source `heads`, so the net's presence feature
tracks them like any other source.

**Model.** `walk_forward.py` unchanged: rolling 60, 30 nets per fold, objectives mse and soft_top8, hold while ranked
≤ 16; three independent seed draws (0, 1000, 2000). Out of sample from 2010-02 (60 months after the panel starts),
about 200 months.

**Comparison.** Pooled three-draw ensemble, default basket rule, paired monthly excess against the pooled rolling-60
default over the same months 2010-02 → 2026-09, annualised, with t; each draw against the same-seed default draw.

**Decision.** Replace the default only if the pooled paired t ≥ 2.0 and all three draws are ahead. Otherwise the default
stays; report the interval. Secondary, for understanding only: the net's draw-to-draw spread, and the result with
the six columns shuffled across countries within month (one run, seed 0) as a placebo.

---

# B2b (2026-10-08 01:05, Arjun's design): one net, many heads — fundamentals as auxiliary losses

Written before any run. B2a showed that *inputs* carry a tax (six noise columns cost ~1.6% a year) and that the heads'
content is worth only a fraction of a point as inputs. This design adds no inputs: the default net keeps its 238 factors
and its return head; six extra output heads forecast next month's change in the six surviving fundamentals, and their
losses shape the shared trunk. Only the return head is used for ranking.

**Architecture.** Default trunk (256, 128, GELU, dropout 0.15) with 7 outputs: output 0 = return score (trained with the
default's objectives, mse and soft_top8, headline nn_mse); outputs 1–6 = next-month change in `Trailing EPS_TS`,
`BEST EPS_TS`, `Best ROE_TS`, `IMF_CPI_Inflation_YoY_TS`, `20 Day Vol_TS`, `BBG_Govt_Bond_10Y_TS`, each scaled by its
standard deviation over the fold's training rows, masked where missing.

**Loss.** L = L_return + λ · mean over the six heads of masked MSE. Early stopping unchanged: on the return objective over
the inner validation months, so the auxiliary losses act as a regulariser and can never be selected for.

**Arms (fixed in advance).** λ = 0.5; λ = 2; λ = 2 with a 30-epoch warm-up in which only the auxiliary losses train
("learn the economy first, then the market"). Three seed draws each (0, 1000, 2000). Panel: cleaned v3, 238 inputs,
rolling 60, 30 nets per fold, OOS 2005-02 → 2026-09 (260 months, the default's full record).

**Comparison and decision.** As before: pooled three-draw ensemble under the default basket rule, paired against the
pooled rolling-60 default; the default changes only if an arm has pooled paired t ≥ 2.0 and leads in all three draws.
Three arms are tested, so a single pass at that bar carries roughly three times the false-positive risk of one; a
pass must also be the best of the three arms and will be re-run with three fresh seeds before adoption. If no arm
passes, rung B is closed and the default stays.

## Amendments

(none)
