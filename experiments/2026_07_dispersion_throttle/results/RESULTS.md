# R1 Dispersion Throttle — Results

**Experiment:** `experiments/2026_07_dispersion_throttle/` · **Run:** 2026-07-13
**PRD:** committed at `8beeeea` before any measurement; all constants frozen there; no parameter search occurred.
**Book:** daily top-7/bottom-7 LS on `COMBINER_RIDGE_DAILY_V1` (frozen 2026-07-13 snapshot), 1-day lag, gross. Evaluation 2008-03 → 2026-07 (post 3-year expanding warm-up), 4,361 days.

## Executive verdict

**DEAD — failed 4 of 5 pre-registered gates.** The dispersion throttle replicates the AA engine's vol-conditioning failure on a completely different engine class (cross-sectional LS vs single-market directional): it sells the book's positive skew and buys essentially nothing.

| Arm | Sharpe | CAGR | MDD | Calmar | Monthly skew |
|---|---|---|---|---|---|
| (a) baseline | 3.255 | 59.8% | −13.2% | 4.52 | **+2.99** |
| (b) dispersion throttle D1 (primary) | 3.246 | 51.5% | −12.6% | 4.09 | **+1.29** |
| (b2) dispersion D2 (monthly, secondary) | 3.427 | 53.6% | −13.1% | 4.11 | +2.60 |
| (c) vol-target control | 3.207 | 43.7% | −13.2% | 3.30 | +0.57 |

Gates: G1 Sharpe ≥ +0.10 **FAIL** (−0.009) · G2 shallower MDD pass (−12.6% vs −13.2%) · G3 skew loss ≤ 0.10 **FAIL** (−1.70) · G4 beat vol-target by ≥ 0.05 **FAIL** (+0.04) · G5 beat 95% of placebo **FAIL** (78.8%).

## What the result actually says

1. **The AA lesson generalizes across engines.** AA (2026-07-11): graded vol-conditioning sold +0.72 skew for ≤ +0.07 Sharpe on a directional momentum engine. R1 (2026-07-13): a dispersion throttle sold 1.70 of monthly skew for −0.01 Sharpe on a cross-sectional LS engine. Two engines, same failure shape. The mechanism is now clear enough to state as a house lesson: **this book's (and AA's) convexity lives in exactly the high-dispersion/high-vol episodes an inverse-state overlay de-levers; clipping them is selling cheap insurance you already own.**
2. **It is not that dispersion was the wrong state variable — any inverse-state throttle hurts this book.** The vol-target control (identical rule shape on the book's own vol) was equally pointless on Sharpe and *worse* on skew (+2.99 → +0.57). This kills the whole rule family for this engine, not just the dispersion flavor.
3. **The throttle offers no protection against the family decay** (the thing one might have hoped for): 2024–26 Sharpe identical throttled vs not (1.716 both). The decay is not a dispersion event — consistent with the G1 autopsy's finding that the flip is state-independent.
4. **The mild D2 Sharpe bump (+0.17) is not a survivor:** secondary variant by pre-registration, fails the same skew gate (+2.60 vs required ≥ +2.89), and sits well inside the placebo distribution's right tail behavior. Recorded for honesty, not promoted.

## Caveats

- The baseline book's gross Sharpe (3.3) reflects daily-rebalanced gross returns on the walk-forward combiner and carries the combiner's known in-sample-selection ceiling caveat; the LEVEL is not the claim here — the throttle *comparison* is, and it is insensitive to that caveat (all arms share the book).
- Multiplier was mild by construction (mean g = 0.94, never at floor). A more aggressive parameterization would sell more skew, not less — the direction of the failure is unambiguous; no re-parameterization was run (PRD §6).
- Gross returns per the 2026-07-13 cost-retraction directive.

## Bookkeeping

- Methodology ledger: `ME_20260713_002` registered + DEAD verdict appended.
- Lesson recorded in `docs/strategy/lessons.md` (inverse-state exposure overlays on positively-skewed books).
- Suggestion for Arjun (his call): annotate the Investment Learnings `AA.md` entry with this cross-engine confirmation.

## Artifacts

- `results/r1_summary.json` — gates, metrics, placebo distribution stats
- `results/r1_metrics.xlsx` — full + subperiod tables, placebo draws
- `results/r1_daily_book.parquet` — daily arm returns + multipliers
- `results/figures/r1_curves.pdf` — equity curves + multiplier paths
- Code: `r1_throttle_test.py` · Inputs: shared frozen snapshot `Data/work/experiments/flip_autopsy/snapshot_2026_07_13/`
