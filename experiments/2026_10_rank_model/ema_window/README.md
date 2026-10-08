# Rolling five-year window versus all-history with recency weights — result

**Verdict: KEEP rolling-60** (comparison run `results/ema_compare_20261007_233844`, grid runs 2026-10-07 22:32–23:2x, pre-registered in `PREREG.md`).

Pooled three-draw ensembles, default basket rule, out-of-sample 2005-02 → 2026-09, % a year excess over the equal-weight 34:

| arm | excess %/yr | t | IR | paired vs rolling-60 | paired t | 2005–09 | 2010–19 | 2020–26 |
|---|---|---|---|---|---|---|---|---|
| rolling-60 (default) | 3.19 | 2.48 | 0.53 | — | — | 2.13 | 2.74 | 4.62 |
| expanding, equal weights | 3.00 | 2.21 | 0.48 | −0.19 | −0.15 | 0.33 | 3.96 | 3.52 |
| half-life 24 m | 2.42 | 1.88 | 0.40 | −0.77 | −0.69 | −2.28 | 4.93 | 2.11 |
| half-life 36 m | 3.11 | 2.37 | 0.51 | −0.08 | −0.07 | 0.03 | 3.63 | 4.59 |
| half-life 60 m | 2.63 | 1.99 | 0.43 | −0.56 | −0.46 | 0.61 | 3.10 | 3.40 |
| half-life 120 m | 3.26 | 2.50 | 0.54 | +0.07 | +0.05 | 1.10 | 3.87 | 3.91 |

No arm is distinguishable from rolling-60: every paired t is inside ±0.7, against a pre-registered bar of 2.0 with all
three draws ahead. None had more than one draw ahead.

**The real finding is stability across seed draws.** Per draw (s0 / s1000 / s2000):

| arm | s0 | s1000 | s2000 | spread |
|---|---|---|---|---|
| rolling-60 | 3.05 | 3.28 | 3.02 | 0.26 |
| expanding | 4.55 | 1.66 | 2.17 | 2.89 |
| half-life 24 | 5.70 | 1.18 | 1.95 | 4.52 |
| half-life 36 | 5.96 | 2.11 | 1.99 | 3.97 |
| half-life 60 | 5.83 | 1.78 | 1.55 | 4.28 |
| half-life 120 | 5.15 | 2.50 | 2.54 | 2.65 |

Every all-history arm scored 4.5–6.0% on seed 0 and 1.2–2.5% on the other two seeds. The draws share the inner
validation split (the early-stopping months are drawn from the seed), so seed 0 is one lucky validation draw that every
all-history arm fell for and rolling-60 did not. Training on all history makes the net three to seventeen times more
sensitive to which months happen to be held out for early stopping. Rolling-60 is the robust choice as well as the
even one across decades (the all-history arms are weak in 2005–09, when "all history" is short and recency weights
shrink it further).

Consequence: the default stays rolling-60. Decision 2 in `llm_rl/DESIGN.md` is closed; the reviewers' "stable prior
plus recent layer" was tested and did not beat the owner's rolling window. The first two grid runs (exp_s0 4.55,
ema24_s0 5.70) looked like a breakthrough for about ten minutes — the pre-registered three-draw rule is what stopped it
being reported as one.

Code: `walk_forward.py --window 0 --half-life H` (recency weights in the loss and the early-stopping score, mean 1);
`ema_window/run_grid.sh`, `ema_window/compare.py`. Report: `results/ema_compare_20261007_233844/report.html`, with `arms.xlsx` and `charts.pdf`.
