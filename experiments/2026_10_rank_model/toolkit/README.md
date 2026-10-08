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
