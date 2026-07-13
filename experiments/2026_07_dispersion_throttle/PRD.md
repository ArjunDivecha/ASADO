# PRD — R1 Dispersion Throttle ("breadth throttle") on the Combiner Book

**Experiment:** `experiments/2026_07_dispersion_throttle/`
**Date frozen:** 2026-07-13 (before any throttled-book number was computed)
**Provenance:** `regime3_candidates.md` R1; external evidence Stivers–Sun (JFQA 2010), Docherty–Hurst (2018, international), Quantpedia #1284 (dispersion overlay shape). Pre-registered per asado-research-protocol; this is a **methodology experiment** (an exposure overlay, not a cross-sectional signal — the harness cannot evaluate it), so it records to the methodology ledger like the G1 autopsy.
**Metrics:** GROSS returns throughout (cost gating retracted 2026-07-13). Light-mode PDF figures.
**Inputs:** reuses the frozen `Data/work/experiments/flip_autopsy/snapshot_2026_07_13/` snapshot (combiner_scores_daily, t2_1dret_daily, country_returns_monthly). No DB access, no writes outside the sandbox.

## 1. Hypothesis and mechanism (written before any data)

When cross-sectional dispersion of country returns is abnormally high, the per-unit-of-signal payoff volatility of a cross-sectional long-short book rises mechanically (LS return ≈ IC × dispersion × breadth), and per the international evidence the momentum-type component of the cross-section becomes less reliable. Scaling the book's gross exposure inversely to a smoothed dispersion state should therefore deliver a better risk-adjusted and drawdown-adjusted return path **without** changing WHICH countries are held. Direction: **higher dispersion → lower gross**. Invalidation: if the throttled book fails the gates in §5 — in particular if it behaves like the AA engine's rejected vol-conditioning (small Sharpe gain bought by selling positive skew), or adds nothing beyond a plain vol-target control — the idea is DEAD for this engine and gets recorded as such.

## 2. Priors this experiment must beat (stated honestly)

1. **AA engine rejection (2026-07-11):** every graded vol-conditioning variant sold +0.72 monthly skew for ≤ +0.07 OOS Sharpe. Different engine (single-market directional momentum), but the pattern — overlay buys Sharpe by selling skew — is the null hypothesis here.
2. **G1 autopsy a3 finding (2026-07-13):** the network_spillover family's *IC* is flat across dispersion states (quartile means 0.025/0.014/0.030/0.025). So any benefit here must come through the **second moment** (vol/drawdown/skew of the book), not through IC timing. This weakens the Docherty–Hurst alpha-timing channel for THIS book and is exactly why the vol-target control (§4c) is decisive.
3. **Combiner decay:** the combiner's own IC went negative in 2026H1 (G1 autopsy a5). The throttle cannot rescue a dead signal; results will be reported for the full sample and for pre-decay subperiods separately.

## 3. The book (fixed)

- **Scores:** `COMBINER_RIDGE_DAILY_V1` from the frozen snapshot (the live walk-forward surface).
- **Portfolio:** per trading day t, rank the available countries by score; long the top 7 equal-weight, short the bottom 7 equal-weight (harness width). Positions earn day t+1's returns (1-day implementation lag). Daily country returns per the loopdb backward-shift + placeholder-drop convention (as validated in the G1 autopsy at corr 0.996 vs the frozen harness record).
- **Book return:** r_book(t+1) = mean(top7 ret) − mean(bot7 ret), gross.

## 4. Arms (all fixed; no fitted parameters anywhere)

Dispersion state (two pre-registered variants, both reported; D1 primary):
- **D1 (daily):** cross-sectional std across countries of trailing-21-trading-day returns, EWMA-smoothed (λ = 0.8, i.e. ~4.5d half-life... λ applied as s_t = 0.8·s_{t−1} + 0.2·D_t).
- **D2 (monthly, Stivers–Sun convention):** cross-sectional std of monthly returns, forward-filled daily, same smoothing.

Arms:
- **(a) Baseline:** unthrottled book, gross = 1.
- **(b) Dispersion throttle (the treatment):** g_t = clip( median_expanding(s)_{≤t} / s_t , 0.25, 1.00 ), where median_expanding has a 3-year minimum window; g applied to day t+1's book return with the same 1-day lag. (Quantpedia #1284's rule shape; zero free parameters beyond these constants, all frozen here.)
- **(c) Vol-target control:** identical rule shape on the book's OWN trailing 63d realized vol: g_t = clip( median_expanding(vol)_{≤t} / vol_t , 0.25, 1.00 ). If (b) ≈ (c), dispersion has no specific content.
- **(d) Placebo:** 500 circular shifts (offset 250..4000 days, seed 20260713) of the D1 series through the same rule; distribution of Sharpe deltas vs baseline.

## 5. Pre-registered gates (evaluated on 2005-01 → snapshot end, gross)

Headline metrics: annualized Sharpe, max drawdown, Calmar, monthly skew, and the multiplier's implied turnover (mean |Δg| per month).

Verdict **ALIVE (worth a follow-up)** requires ALL of:
1. Sharpe(b) − Sharpe(a) ≥ +0.10 on the full sample;
2. MDD(b) better (shallower) than MDD(a);
3. monthly skew(b) ≥ skew(a) − 0.10 — the overlay may NOT buy its Sharpe by selling skew (the AA lesson, hard-coded as a gate);
4. Sharpe(b) − Sharpe(c) ≥ +0.05 — must beat plain vol targeting, else the verdict is "just vol targeting" (DEAD as a dispersion idea; (c)'s own numbers reported for information);
5. Sharpe delta of (b) ≥ 95th percentile of the placebo deltas.

Anything else → **DEAD** (with the specific failing gate recorded). Subperiod honesty: also report 2005–2015, 2016–2023, 2024–2026H1; a full-sample pass driven entirely by one subperiod is reported as such and downgrades to "fragile" in the memo (no gate re-litigation).

## 6. What this experiment may NOT do

- No parameter search: the constants (21d window, λ=0.8, [0.25,1] bounds, 63d vol window, top/bottom 7, 3y expanding minimum) are frozen ABOVE, chosen from the literature/#1284 before any run. If they turn out unlucky, that is the result — deviations would be logged as post-hoc and cannot change the verdict.
- No cost modeling, no live-pipeline changes, no writes to protected dirs, no held DB connections.
- Record verdict in the methodology ledger + RESULTS.md; on DEAD, add the lesson to the graveyard corpus.
