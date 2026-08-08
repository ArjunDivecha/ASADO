# Does Shiller PE extremeness time the live T2 Fuzzy strategy?

**Question (Arjun, 2026-08-08):** if valuation extremeness has timing power over the T2
Factor Timing Fuzzy returns, exposure could be vol-scaled down at extremes.

**Answer: only in one place, and its entire value is a single episode. Do not build it as
specced — the record already points at a better version.**

Artifacts: `results/t2_timing.xlsx` (10y window, superseded), `results/t2_timing_gfc.xlsx`
(5y window, the valid one). Returns GROSS; signal lagged one month.

---

## First attempt was invalid, and the reason is worth recording

The initial run used a 10-year normalization window for extremeness. That starts the sample
at 2010-02 — and the T2 strategy's **−62.7% max drawdown troughed 2009-02**, with **five of
its six worst months** (2008-10 −28.4%, 2008-09, 2008-01, 2001-09, 2008-03) outside the
window. Only 2020-03 was inside.

**A de-risking rule cannot be evaluated on a sample containing no crash.** The first run's
t-statistics were real and meaningless. Worse, it pointed the wrong way — extremeness looked
*good* for returns — because in a 2010-2026 sample, extremeness correlates **+0.37 with time**
(p<0.0001) and so mostly proxies for "2016 onwards", a strong stretch for the strategy.

Rebuilt on a **5-year window** (coverage from 2005-02, 258 months, GFC in sample). Shorter
lookback is a noisier definition of "extreme" — but a definition computable only after the
crash is useless for avoiding one.

## Result: one of six variants works

| Signal | Target | Sharpe | Max drawdown |
|---|---|---|---|
| **US Shiller extremeness** | **portfolio** | 0.84 → **0.90** (+0.06) | **−62.7% → −38.5%** (+24.2pp) |
| US Shiller extremeness | net (alpha) | 0.94 → 0.90 (−0.04) | −18.1% → −13.1% |
| breadth of extremes | portfolio | 0.84 → 0.73 (−0.11) | −62.7% → −53.5% |
| mean extremeness | portfolio | 0.84 → 0.69 (−0.14) | −62.7% → −53.3% |

(Rule = 50% exposure in the top tercile of extremeness.)

Only **US** extremeness, only on the **total portfolio**, and it does **not** improve the
alpha — `net` Sharpe gets slightly worse. This manages market exposure, not skill.

## The entire benefit is 2008

| Period | Months | Base max DD | Scaled max DD |
|---|---|---|---|
| 2008–09 GFC | 24 | −52.6% | **−27.2%** |
| 2020 COVID | 12 | −21.2% | −17.9% |
| **Everything else** | **222** | **−21.7%** | **−21.7%** *(identical)* |

For 86% of the sample the rule does **nothing**. Its value rests on **n = 1** event.

## And it does not lead — it coincides

| Date | US extremeness | Weight applied | Actual return |
|---|---|---|---|
| 2007-10 (the peak) | 0.49 | **1.0** | +13.0% |
| 2008-01 | 0.39 | **1.0** | **−13.9%** ← taken at full size |
| 2008-06 | 0.90 | 0.5 | −7.5% |
| 2008-09 | 1.00 | 0.5 | −14.6% |
| 2008-10 | 0.93 | 0.5 | −28.4% |

It gave **no warning at the top** and only engaged once the decline was underway. It halved
the back half of the crash, not the front.

## The record already predicted this, and already has the better tool

Investment Learnings *Market Top*: **"CAPE-momentum (Δ12m) + inverted-yield-curve LEADS by
~9–12 months (pre-peak AUC 0.90)"** while **"trend/VIX/breadth/credit-spread-LEVEL only
CONFIRM declines"**, and **"valuation warnings SATURATE in rich regimes (2020s fire ~45% of
months)"**.

That is exactly what happened here. A valuation **level** measure confirmed rather than led,
and saturated (US extremeness sits at 1.00 for much of the recent sample). The record says
the *change* in CAPE, not its level, is the leading signal — and that already exists as the
live Early Warning System.

Also relevant: the *AA* entry records that graded vol-conditioning variants were **tested and
rejected** (every graded variant sold skew for ≤+0.07 OOS Sharpe), and that "bear-state gating
makes the flip late" — the same lateness seen above.

## Recommendation

1. **Do not build the Shiller-extremeness scaler.** One event, no lead time, no alpha
   improvement, and the threshold is unvalidated.
2. **If the goal is drawdown control, use the existing EWS** (CAPE Δ12m + yield curve), which
   the record shows leads by 9–12 months rather than coinciding.
3. If a valuation-based scaler is still wanted, the honest test is **CAPE Δ12m** rather than
   |extremeness| — and it needs more than one crash, which this universe does not contain.
   That is a reason to test on longer external history (the JST corpus), not on this panel.
