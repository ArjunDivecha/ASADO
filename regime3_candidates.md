# Regime Wars III — What We Missed, What's Actually Left

**Date:** 2026-07-13
**Type:** Research ideation memo (no code, no tests run — nothing registered)
**Inputs:** ASADO graveyard protocol (all five sources checked), Quantpedia prior-art scan (1,345-strategy catalog), three deep web research tracks (academic methods 2020–2026, practitioner frameworks, cross-country evidence)
**Lineage:** `regime.md` (v1, retracted) → `regime2.md` (v2, DEAD) → `regime_ew/`, `regime_factor_selection/` (DEAD) → this memo
**No file I/O:** this is a document, not a program.

---

## 0. Bottom line

The regime wars were lost fighting on the wrong front. Every internal kill and every honest external result says the same thing:

> **Regime information does not live in the first moment (WHICH country/factor to pick). It lives in the second moment (WHEN the cross-section pays, HOW MUCH risk to run, and WHEN it crashes).**

Our four kills — global-macro regime factor weighting, per-country HMM early warning, IP-regime factor selection, EF/HMM branch clustering — all tried to make a regime label reorder or predict the cross-section. The external literature contains **zero** published, replicated OOS evidence that any regime method (deterministic, HMM, jump model, NN, transformer) improves cross-sectional selection — a conspicuous gap that corroborates our nulls. What survives replication is narrow and specific:

1. **Cross-sectional return dispersion** predicts *when* cross-sectional strategies pay (Stivers–Sun JFQA 2010; Docherty–Hurst 2018, international, dispersion-scaled momentum beats unconditional in every region tested).
2. **A strategy's own conditional volatility / crash hazard** is forecastable even where its return is not (Daniel–Moskowitz 2016; Barroso–Santa-Clara 2015) — and our own dead experiments whispered this: the `Regime` branch states had below-random return AUC but real next-month **vol/drawdown** content; `regime_ew` states were persistent and real, they just didn't lead *returns*.
3. **Statistical jump models** (Nystrup; Kolm/Mulvey/Shu 2021–2024) fix the exact defect (regime persistence: our 0.729 / 3.5-month states) that made HMM regimes untradeable — with real OOS de-risking evidence and open-source code. They fix the *method*; they do not overturn the *selection null*.

So the recommended re-entry into regime work is: **one pre-registered "risk-state" family targeting the second moment of our own book, plus the already-sanctioned G1 flip autopsy** — and a standing refusal to re-fight the selection battle regardless of how novel the classifier is.

---

## 1. The graveyard (do not re-propose these)

| What died | Verdict | Where | Why it died |
|---|---|---|---|
| US-macro 7-regime taxonomy → conditional factor IC weights | DEAD | `regime2.md` | 0/52 factors clear FDR; Sharpe Δ +0.078; worse drawdowns, worse in stress |
| Autonomous regime-tuning loop | DEAD (self-defeating) | `regime_loop/` | Optimizer pointed at the pass metric games the metric |
| Per-country HMM early-warning → own-country return lead | DEAD (Gate 3) | `regime_ew/results/RESULTS.md` | States persistent & real (Gate 1 PASS 0.926) but no walk-forward return lead (17/34, need 23) |
| Own-country IP regime → factor rank-IC selection | DEAD (clean null) | `regime_factor_selection/results/RESULTS.md` | 0/74 FDR, placebo-confirmed calibrated machinery |
| EF/HMM branch clustering → next-month return | DEAD | `llmchat.md:54` | AUC 0.46–0.47 (below random); **vol/drawdown content survived descriptively** |
| PCA-stacked analog states | DEAD (NO-GO) | `docs/strategy/lessons.md` | Misspecified: 2,900-dim features ≫ samples |
| Regime cross-country posterior ranking | DEAD | Research-Agenda-2026-07-v2 §0.2 | Raw levels lost money; only own-history calibration worked |
| Every Pattern regime overlay | DEAD | Research-Agenda-2026-07-v2 §0.2 | All reduced CAGR and Sharpe |
| Graded vol-conditioning of AA's Q4 flip (BSC 1/σ, bear-gating, hysteresis) | REJECTED 2026-07-11 | Investment Learnings `AA.md` | Every graded variant sold +0.72 monthly skew for ≤ +0.07 OOS Sharpe |
| Sharpe-gated MTRS market-top overlay | FAILED | Investment Learnings `Market Top.md` | 1.4%/yr vs 200dMA 7.7%; gate destroys lead time |
| TabFM / flexible ML on monthly factor returns | KILL | Investment Learnings `TabFM.md` | Foundation model == LightGBM == noise fitter; trailing-36M mean undefeated |

**Standing priors this memo must respect:** the Six Laws (esp. 25bp cost law, index-space expression law, second-order law, 15–20% hit-rate law); "distrust a searched pass"; overlay-type conditioning already has two strikes from adjacent engines (AA, MTRS).

---

## 2. What the outside sweep found (condensed)

### Quantpedia (catalog of 1,345, scanned 2026-07-13)
- **#1046 Dynamic Asset Allocation with Asset-Specific Regime Forecasts** (Shu/Mulvey lineage) — the closest documented cousin to anything proposable here: statistical Jump Model labels per asset, shifted forward as supervised targets for XGBoost, bull/bear → allocation. Confidence "Strong", paper Sharpe 1.02. **This is the method family we never ran.**
- **#1284 Cross-Sectional Dispersion & State-Dependent Momentum** (crypto) — dispersion overlay scaling gross exposure with smoothing and bounds; exactly the WHEN-not-WHICH shape.
- **#1266 Momentum-Based Regime Switching on factor active returns** — EWMA z-score trend states; QP OOS full Sharpe 0.97. Really factor momentum in regime clothing.
- **#0989 Multi-Asset Multi-Factor through the Cycles** — growth/inflation quadrant overlay; the macro-quadrant leg is the weak leg per skeptics.

### Academic methods track (top-5 by honest evidence)
1. **Statistical jump models** — persistence tunable (<1 shift/yr vs HMM 2+), OOS 1990–2023 S&P timing Sharpe 0.68 vs 0.48 B&H, turnover 44% vs HMM's 141%; independent implementation ([jump-models](https://github.com/Yizhan-Oliver-Shu/jump-models), [arXiv 2402.05272](https://arxiv.org/html/2402.05272v3)). All evidence is de-risking/timing, **not** selection.
2. **Turbulence/Mahalanobis (continuous)** — best-replicated; never discretizes, so structurally immune to the persistence failure.
3. **Supervised cluster-then-classify** (SJM labels → XGBoost; [arXiv 2406.09578](https://arxiv.org/html/2406.09578v2)) — the "label regimes by what you want to predict" bridge.
4. **Changepoint + deep momentum** (Wood/Roberts/Zohren, [arXiv 2105.13727](https://arxiv.org/abs/2105.13727)) — +1/3 Sharpe from the CPD module; sizing overlay.
5. **Absorption ratio / correlation-structure** — leads drawdowns; risk overlay only.
- **Deprioritized with evidence:** time-series foundation models (fail vs naive baselines — consistent with our TabFM kill); LLM/news-text regimes (no OOS alpha); signatures/MMD/Wasserstein (synthetic-validated only); TDA (credible crisis early-warning, ~34-day lead, but detection ≠ alpha).

### Practitioner track
- **Consensus null on macro-regime selection**: AQR ("deceptively difficult"), Robeco/Blitz ("business cycle indicators do not capture much of the cyclical variation in factor returns" — the quant cycle is sentiment-driven), Vanguard/Ammann (markets price known macro). Bridgewater's honest use of regimes is *diversification across* them, not prediction.
- **Vol-managed portfolios**: Moreira–Muir (2017) fails real-time OOS (Cederburg et al. 2020, 103 strategies) and dies after costs ex-market (Barroso–Detzel 2021); rehabilitated only inside cost-aware multi-factor netting (DeMiguel et al. 2024). **Own-strategy** vol scaling of momentum (BSC/DM) is the robust special case.
- **Dacco–Satchell (1999)** is the mechanical explanation of every regime disappointment: small state misclassification wipes the entire theoretical advantage.
- Sell-side regime products (State Street MRI, Goldman RAI, MSCI Adaptive): no independent OOS replication anywhere.

### Cross-country track
- **Global financial cycle (Rey)** is real but contemporaneous and weak (global factors rarely explain >25% of flow variance; VIX–factor corr ~0.25). No clean lagged, cost-aware dollar/VIX country-allocation strategy found. Dollar-beta (BIS WP1000) is a priced *risk premium*, not a timing signal.
- **Dispersion conditioning: the strongest PIT-clean lead** (Stivers–Sun; Docherty–Hurst — top-quintile dispersion kills the momentum premium in every region; dispersion-scaled momentum beats unconditional everywhere tested).
- **Zaremba–Andreu** independently replicate our cost law: 120 anomalies × 42 country ETFs, costs "largely lethal," survivors only at annual rebalancing.
- **OECD CLI rotation**: vintage/revision trap (whole series revised each release) — same trap class as our ElasticNet PIT audit. Deprioritize.
- **Meta-labeling**: gates built on *macro regime features* show no OOS skill; gates on *signal-internal* features show some (Lund thesis).
- Flagged gap: nobody has tested **pooled panel regime estimation** on tradeable country allocation net of costs. Given three internal kills next door, treat as lottery ticket, not lane.

---

## 3. The candidate list (ranked)

Register anything from here as **one pre-registered family** (`regime_risk_state_2026_07` or similar) with family-count DSR haircuts — these ideas are correlated, and per the hit-rate law most will die.

### Tier 1 — test these

**R1. Dispersion throttle on the combiner book (the "breadth throttle").**
- **Mechanism:** month-end cross-sectional dispersion of the 34 country returns (and variant: dispersion of factor returns from `factor_returns_daily`) → smoothed inverse scaling of the combiner book's gross exposure, bounded (e.g. [0.25, 1.0]), with hysteresis to keep turnover near zero. Exactly the #1284 overlay shape applied to `combiner_scores_daily`.
- **Why it's not a graveyard rhyme:** every dead experiment conditioned on *external/revised macro states* or tried to *reorder* the cross-section. This conditions on the outcome-source-of-truth itself (country returns — zero revision risk, PIT-clean by construction) and only changes *how much* book to run. D7 already flags per-factor dispersion compression descriptively (`build_dislocations.py:585-618`) — infrastructure exists, but it has never been harness-tested as a book-level overlay.
- **Laws:** cost law OK (smoothed gross scaling ≈ near-zero added turnover); expression law not engaged (no new selection alpha claimed); second-order law compatible (dispersion is a second-moment object).
- **Prior to beat (state it in the PRD):** AA's graded vol-conditioning rejection and MTRS gate failure. The distinction: those scaled a *single-market directional* engine and paid in skew; this scales a *cross-sectional L/S* book whose crash mechanism (momentum crashes cluster in high-dispersion rebound states) is precisely what the international evidence says dispersion times.
- **Kill gate:** walk-forward, net-of-cost Sharpe/MDD of throttled vs unthrottled combiner; pre-register the Docherty–Hurst sign (high dispersion → lean out momentum-type sleeves). If the throttle only sells skew for ≤0.1 Sharpe like AA's did — dead, and we've settled the question for this engine class.

**R2. Strategy-state jump model ("does our book work right now"), supervised on our own PnL.**
- **Mechanism:** fit a statistical jump model (persistence-penalized, not HMM) on daily strategy-level series we own — combiner daily PnL, factor-return panel (`factor_returns_daily`, ~6,700 daily obs since 1999 — 20× the observations the dead monthly experiments starved on). Two-state good/bad label per *strategy family*, labels shifted forward as targets for a **low-capacity** classifier (logistic or shallow XGBoost with ≤6 features: trailing dispersion, book vol, correlation level, drawdown state). The #1046 / Shu–Mulvey architecture, but pointed at the only target the evidence supports: our own book's risk state.
- **Why novel:** regimes defined by *what we want to predict* (combiner profitability/drawdown), not by macro taxonomy; jump-model persistence fixes the 3.5-month churn that made regime/v2 untradeable; daily data fixes the small-sample F-test power problem that regime2.md itself diagnosed.
- **Prior to beat:** TabFM kill (flexible ML on monthly factor returns = noise). Answer: daily data, two states, ≤6 pre-registered features, no sweep. If a 6-parameter model can't see it, it isn't there.
- **Kill gate:** walk-forward — does P(bad state) predict next-month combiner drawdown/vol (second moment) and does gating gross on it improve net MDD-adjusted return? Return-lead is explicitly *not* required (that's the dead battle); risk-lead is.

**R3. The G1 flip autopsy, run with regime states as the diagnostic axes (already sanctioned).**
- **Mechanism:** Research-Agenda-2026-07-v2 G1 is the agenda's #1 diagnostic priority: is the 2024–26 sign flip of the graph/lead-lag/similarity family cyclical crowding, regime interaction, or construction drift? Condition the family's IC on: real-rate level/Δ, DXY trend state, cross-country dispersion, correlation/absorption state, EM/DM flow state.
- **Why it's the right first move:** it reuses all the regime machinery we built, on a question where regime *explanation* (not prediction) is the deliverable, with direct portfolio consequences for live sleeves. If a regime interaction shows up here, THAT is the evidence-based route back into regime conditioning — with a specific, mechanism-motivated interaction rather than a taxonomy fishing trip.
- **Kill gate:** none needed — it's a diagnosis. But pre-register the conditioning axes to keep forking-paths honest.

### Tier 2 — one shared "risk-state" construction, risk claims only

**R4. Pooled correlation-state monitor: absorption ratio + turbulence on daily country returns.**
- **Mechanism:** compute Kritzman–Li absorption ratio and Mahalanobis turbulence daily from `t2_levels_daily`-derived country returns (pooled across 34 countries — one shared state, the opposite shape of the dead per-country HMMs). Continuous, never discretized (sidesteps persistence entirely).
- **Use:** (a) input feature to R1/R2; (b) contagion/de-risking context in the nightly brief next to the JST tail-risk layer; (c) *candidate* gross throttle — claim variance/MDD reduction only, never alpha.
- **Evidence honesty:** AR leads drawdowns in replicated work; nothing shows net *alpha*. Frame accordingly.

**R5. JST 150-year crash-hazard prior (upgrade of the live tail-risk layer).**
- **Mechanism:** Schularick–Taylor-style low-capacity hazard model (credit growth, asset-price booms, current account) fit on `jst_macrohistory` (1870–2020 — sample-external to every backtest we run), producing per-country 12-month *drawdown/vol* hazard priors for the modern panel.
- **Why novel:** trains entirely outside the evaluation sample; targets the second moment; extends a layer that is already live and earning its keep as context (the one regime-adjacent survivor).
- **Expectation:** context/prior tier (Triptych precedent — killed as hard signal, kept as prior). Pre-register that expectation.

### Tier 3 — lottery tickets (hit-rate law: ~15–20% true-positive). Only after Tier 1 resolves.

**R6. Dollar/VIX persistent-trend interaction with the second-order family** — only if R3's autopsy shows a regime interaction; then it's mechanism-motivated, otherwise it's the dead global-macro battle again.
**R7. Meta-label sizing gate with signal-internal features only** (combiner score dispersion, detector agreement, trailing hit-rate — *no macro features*, per the Lund null). Low-capacity, after R1.
**R8. Dispersion-based value↔momentum sleeve tilt** (Stivers–Sun sign structure: high dispersion → value premium up, momentum premium down). This *is* factor timing, the consensus-null zone — flag as the most likely of the eight to die; the only reason it's listed is that the dispersion state variable is the one conditioning variable with real international OOS support.

---

## 4. Do-not-do list (settled, method-independent)

1. **Any regime classifier → cross-sectional factor/country selection.** Three internal clean nulls + zero published counter-evidence anywhere. No new classifier (SJM, transformer, pooled panel, signatures) reopens this — the null is about the *target*, not the *method*.
2. **TSFM/transformer/LLM regime classifiers on monthly return panels.** TabFM kill + independent 2025–26 evaluations (fail vs random walk). The only non-ruled-out crack from the TabFM post-mortem is factor *volatility* forecasting — which is R2's territory anyway.
3. **OECD CLI / revised-macro turning-point rotation.** Vintage trap, same class as the ElasticNet look-ahead incident.
4. **Economic-surprise regime conditioning.** Thin evidence, mean-reverting by construction — and it's the standalone Economic Surprise Lab's territory (started 2026-07-12); don't duplicate inside ASADO.
5. **Signature/MMD/Wasserstein/TDA as alpha projects.** Synthetic-validated. TDA at most as a watch-item feature inside R4's monitor.
6. **Per-country regime anything.** Pool or don't bother — 34 separate small-sample state estimations is how `regime_ew` died.

---

## 5. Suggested sequencing

1. **R3 (G1 autopsy)** — sanctioned, diagnostic, reuses everything, informs whether any regime interaction is real in the one signal family we actually run. Cheap.
2. **R1 (dispersion throttle)** — the single strongest external-evidence idea; PIT-clean; one pre-registered PRD with explicit AA-rejection prior; fast to test against the frozen combiner history via `snapshot_for_experiment.py`.
3. **R2 (strategy-state jump model)** — the genuine method upgrade, aimed at the right target. Needs the jump-models package in a per-experiment venv.
4. R4/R5 as infrastructure/brief upgrades alongside; Tier 3 only if Tier 1 produces a live thread.

All of it under one family registration with pre-registered gates, snapshot inputs, experiments-sandbox only, and the standing rule: **a regime idea is only allowed to claim the second moment.** The first moment belongs to the graveyard.

---

## 6. Sources (external)

Key URLs (full citation lists live in the three research-track reports, reproduced in the session log):
- Jump models: https://arxiv.org/html/2402.05272v3 · https://arxiv.org/html/2406.09578v2 · https://github.com/Yizhan-Oliver-Shu/jump-models
- Dispersion conditioning: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1064101 (Stivers–Sun) · https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2720123 (Docherty–Hurst)
- Momentum crash management: https://www.kentdaniel.net/papers/published/jfe_16.pdf · https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2041429
- Vol-management skeptics: https://www.sciencedirect.com/science/article/abs/pii/S0304405X2030132X (Cederburg) · https://www.sciencedirect.com/science/article/abs/pii/S0304405X21000775 (Barroso–Detzel) · https://onlinelibrary.wiley.com/doi/full/10.1111/jofi.13395 (DeMiguel)
- Factor-timing skeptics: https://www.aqr.com/Insights/Research/Journal-Article/Contrarian-Factor-Timing-is-Deceptively-Difficult · https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3930006 (Blitz, Quant Cycle)
- Country-ETF costs: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3038514 (Zaremba–Andreu)
- Turbulence/absorption: https://www.tandfonline.com/doi/abs/10.2469/faj.v66.n5.3 · https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1633027
- Global financial cycle skeptic: https://www.bis.org/publ/work661.pdf (Cerutti–Claessens–Rose)
- Regime-forecast fragility: Dacco–Satchell 1999, https://onlinelibrary.wiley.com/doi/abs/10.1002/(SICI)1099-131X(199901)18:1%3C1::AID-FOR685%3E3.0.CO;2-B
- Changepoint momentum: https://arxiv.org/abs/2105.13727 · TSFM skepticism: https://arxiv.org/abs/2606.27100
- Quantpedia cousins: https://quantpedia.com/strategies/dynamic-asset-allocation-with-asset-specific-regime-forecasts · https://quantpedia.com/strategies/a-regime-aware-market-capitalization-rotation-strategy
