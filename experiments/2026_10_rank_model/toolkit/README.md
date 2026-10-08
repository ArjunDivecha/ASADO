# Rung B — the toolkit

Pre-registration: `PREREG.md` (2026-10-08). Phase 0, the hindsight ceiling, is done: `swap_ceiling.py` →
`results/ceiling_20261008_001652/`. Over 260 months the default made 3.19% a year; a perfect top-8 would make 64%.
The best single swap a month, in hindsight, is worth 23.5% a year (11.4% confined to ranks 6–8 out / 9–11 in); the best
two and three swaps 37.7% and 47.7%. A random swap costs 0.5% a year, because the model's holdings beat its
non-holdings. So the one-swap action space is not binding — a rule with 4% of perfect skill adds 1% a year — and the
full re-rank is the primary rule in B anyway.

## Stage 1 — heads (`results/heads_20261008_001954/`)

Six of seven survive against their naive baselines (rolling-60 ridge on the 238 factors, OOS 2005-02 → 2026-09, target =
next month's change in the variable's TS z-score). Mean OOS rank IC with the realised change: realised vol 0.39
(persistence −0.36: vol mean-reverts and the factors anticipate it), trailing EPS 0.18, BEST EPS 0.17, ROE 0.14,
inflation 0.13, 10Y yield 0.06 — paired t against the best baseline from 2.3 to 30. LT growth dropped: the head's 0.21
equals persistence's 0.21.

## Stage 2 — comparator (`results/comparator_20261008_002153/`): **A STAYS**

Rolling-60 ridge on the default score plus the six head forecasts (each standardised within month), OOS 2010-02 → 2026-09,
200 months. Primary (full re-rank, pooled): **1.37% a year against the default's 3.46%** — a loss of 2.1% a year, paired
t −1.25, behind in all three draws (−2.2, −4.0, −2.5). Heads alone re-ranked: 0.31% a year. The swap variants, which keep
the default basket and override at most one or two names, lose less: −0.6% a year (t −1.0 / −0.6).

**The control exposes the design, not just the heads.** The score-only comparator — the default score passed through the
same rolling-60 ridge with nothing else — *also* loses 1.74% a year (t −1.6), and lags the default in 92% of months.
A second stage fitted on 60 months of out-of-sample scores is noisy enough to damage a score that is already good, so
the heads were never given a clean test: whatever they add has to overcome the harm the second stage does on its own.
The heads-only swap variant (2.96% a year, IR 0.58, −0.5% vs default, t −0.8) is the fairest read of what the heads
alone are worth through a one-name override: about the same as the default, not better.

Per the pre-registration this is a FAIL for B as designed; nothing changes the default. A fairer test needs a new
pre-registration with a second stage that cannot hurt by itself: fixed economic signs with equal small weights (no
fitting), or a long-window / expanding second stage justified by its tiny parameter count. Not run; the owner's call.

## B2a — head forecasts as six extra inputs to the default net (`results/b2a_compare_20261008_005156`): **default stays, and the forecasts hurt**

Default net unchanged, 244 inputs (238 factors + six CS-standardised OOS head forecasts), panel from 2005-02, three seed
draws, OOS 2010-02 → 2026-09 (200 months). Pre-registered as B2a in `PREREG.md` (commit `47cf18b`).

| | pooled | s0 | s1000 | s2000 |
|---|---|---|---|---|
| rolling-60 default | 3.46 | 2.62 | 3.87 | 3.08 |
| default + forecasts | **0.51** | 1.46 | 2.61 | 3.17 |

Pooled: −2.95% a year against the default, paired t −2.29; behind in all three draws. Information ratio 0.09 against
0.63; max relative drawdown −19.8% against −9.3%. By period the damage is concentrated in 2020–26 (−0.3% against +4.6%).
The pooled ensemble sits *below all three of its own draws* (the default's pooled 3.46 sits above its draws' mean). A
diagnostic shows this is not because the draws disagree more: within-month rank agreement between draws is 0.64 with the
forecasts against 0.67 without, and top-8 overlap 4.7 against 4.8 names. The pooled basket is a nonlinear function of the
averaged scores and simply landed badly; the per-draw figures (1.5 / 2.6 / 3.2 against 2.6 / 3.9 / 3.1) are the fairer
read, and they are behind in every draw.

Why the record starts in 2010: two stacked 60-month windows on a panel that begins 2000-02. The heads' first OOS forecast is
2005-02; the net then needs 60 months of forecast-bearing rows, so its first fold is 2010-02. Both arms are compared over
the same 200 months.

Why this can't have added information: each head is a ridge — a *linear function of the same 238 inputs* the net already
sees. Appending them gives the net nothing it could not form itself; it only adds a strong inductive bias toward the
directions that predict fundamental changes. The result says those are not the directions that predict returns, and
pushing the net toward them costs 3% a year. That is evidence against the multi-task version too, since it shapes the
representation toward the same directions, though through the loss rather than the inputs.

### B2a placebo: the same six columns shuffled across countries within month (three seeds; `results/b2a_compare_20261008_005609`)

| | pooled | s0 | s1000 | s2000 | paired vs default (pooled) |
|---|---|---|---|---|---|
| rolling-60 default | 3.46 | 2.62 | 3.87 | 3.08 | — |
| + real forecasts | 0.51 | 1.46 | 2.61 | 3.17 | −2.95%/yr, t −2.29 |
| + shuffled forecasts | 1.85 | 1.23 | 1.55 | 2.72 | −1.61%/yr, t −1.16 |

Two readings follow. First, **six columns of pure noise cost the net about 1.6% a year** on this window, below the
same-seed default in all three draws (−1.4, −2.3, −0.4). The default net is close to the edge of what 60 months of
data can support; adding inputs is not free, and anyone proposing more factors should expect this tax. Second, the
real forecasts beat the shuffled ones in every draw (by +0.2, +1.1, +0.5 points), so their content is worth roughly
half a point to a point a year — not nothing, but less than the tax on carrying them, and the pooled ensemble of the
real-forecast nets happened to land worst of all. **Verdict: the forecasts are not a useful input to the net.** The one
design not yet tried is the multi-task net (shared trunk, fundamentals as auxiliary losses, return head alone used for
ranking), which adds no inputs and so avoids the tax; after B2a the prior on it is low.
