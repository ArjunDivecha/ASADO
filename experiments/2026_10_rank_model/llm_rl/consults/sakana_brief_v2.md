# Brief for outside review: an LLM reasoning policy, trained with RL on realised outcomes, to rank country equity markets

I want a critical, specific review and refinement of a research idea before anything is built. Please don't give generic ML advice; engage with the numbers below.

## 1. What already exists (the baseline the idea must beat)

- **Universe and task.** 34 country equity markets (country ETFs / MSCI-style indices), monthly, Feb 2000 – Sep 2026 (320 months). Each month: pick 8 of 34 countries; the score is the equal-weight basket's next-month return minus the equal-weight average of all 34 ("excess").
- **Inputs.** 238 monthly factors per country after cleaning, each as a cross-sectional z-score (country vs peers this month) and/or a time-series z-score (country vs its own history). Families: valuation (earnings yield, P/B, dividend yield…), momentum and short-term reversal, volatility, macro (inflation, rates, current account, budget, GDP), currency, ETF flows, news sentiment/attention (GDELT, from 2015 only), Bloomberg market-implied series. Publication lags applied for slow sources. A forensic audit removed series whose historical levels were retrospectively rebased to a future base year (e.g. BIS REER), which had leaked future information.
- **Current best ("the default").** A shared MLP (238 inputs → 256 → 128 → 1 score per country-month), 30-seed ensemble, retrained once a year on only the trailing 60 months (rolling — the owner's view is that "the world changes"), trained to predict next-month excess return; basket = top 8 by score with a hysteresis buffer (a held name stays while it is still ranked in the top 16; halves turnover at no cost).
- **Its out-of-sample record.** Walk-forward 2005–2026 (260 months, each year scored by a model trained only on prior data): **+3.1%/yr excess, t 2.8, information ratio 0.59**, reproducible across three independent runs (3.0 / 3.3 / 3.0%). Even across decades (2.7 / 3.3 / 3.1%). 1.8 of 8 names replaced per month.
- **What we learned getting there.** Ridge on the same inputs: 2–2.9%/yr, statistically indistinguishable from the net. Every robust configuration converges near 3%/yr, IR 0.5–0.6. Boosted trees overfit badly. Regularising the net harder hurt. Cross-country attention and global macro context added nothing. A blend of net and ridge reached the same ~3%. Single runs of the net vary by up to 3%/yr across seeds (ten-net ensembles were not enough). Random-month splits overstated results vs walk-forward. A design chosen on 2000–2013 and walked blind through 2013–2026 did not beat ridge.

## 2. Measured noise (this is the crux)

From the default model's out-of-sample scores, per month:

| candidate reward | mean | sd | per-month SNR | months needed for t = 2 at this edge |
|---|---|---|---|---|
| top-8 basket excess | +0.13% | 1.74% | 0.075 | ~710 |
| rank correlation (all 34) | +0.025 | 0.23 | 0.109 | ~340 |
| pairwise ordering accuracy − 0.5 | +0.009 | 0.081 | 0.107 | ~350 |
| score-weighted long-short | +0.10% | 1.22% | 0.084 | ~560 |

A 60-month training window therefore holds about t ≈ 0.8 worth of evidence about a policy as good as the current one. About 99% of any month's cross-sectional ranking is unexplainable noise.

**Re-identification.** Within-month factor *ranks* are very persistent (median month-to-month rank autocorrelation 0.91). A nearest-neighbour match on a country's rank vector re-identifies the same country in the next month 93.5% of the time (87% with a curated 20-factor subset). Extreme profiles (highest inflation, lowest rates) are nameable from general knowledge.

## 3. The idea (the owner's)

Inspired by how reasoning models are trained — hill-climbing / reinforcement learning with verifiable rewards:

1. For each historical month, give an LLM that month's factor table for 34 countries **with country names and dates removed**, together with **what actually happened next month**.
2. Have the LLM write the reasoning that would have led to the correct ranking (rationalisation, as in STaR).
3. Use those traces to warm-start a policy model, then train it with RL (e.g. GRPO) on anonymised months, reward = realised next-month outcome of its ranking.
4. At inference the policy sees only the current anonymised month and reasons its way to a ranking.

The owner's further point: an LLM's knowledge of real-world outcomes pollutes any historical backtest, **but that knowledge — experience of how economies and markets behave — may be genuinely valuable for forward-looking prediction**, the way a portfolio manager who lived through 2008 is better for it even though you can't backtest them on 2008.

## 4. My current working design (please attack it)

- **Two backtest arms.** *Anonymised* (only structural knowledge can act → the closer-to-honest estimate) vs *named* (structural + memorised outcomes → an optimistic upper bound and a cheap kill test: if it can't beat ~3%/yr even with hindsight, the idea is near-dead; if it does, that proves nothing).
- Same rolling 5-year walk-forward, same buffer, several independent runs, scored against the default.
- **Noise control in rationalisation:** per month ask for at most two patterns with a confidence; keep only patterns that recur across many months of the training window.
- **Phase 1:** in-context probe with a frontier API model (no training) — a rulebook of recurring lessons, updated yearly from the trailing window, applied to each new month. **Phase 2:** an open-weight model, SFT on traces then GRPO against realised outcomes, run locally (M4 Max, 128 GB) or on rented GPUs.
- **Forward:** from the model's knowledge cutoff, the named arm ranks countries every month alongside the default, with a live news overlay (it reads that month's news and can veto picks).

## 5. Known concerns

- SNR (above): RL on 60 noisy rewards per window cannot select between policies by outcome alone; the LLM's prior must carry most of the weight.
- Rationalising noise: an LLM writes a confident story for every month, including pure-noise months.
- Leakage in the "anonymised" arm (above).
- Compute: GRPO rollouts × 22 annual folds × several independent runs.
- Forward validation is slow: 48 months gives ±2.6%/yr standard error on the excess.

## 6. What I want from you

1. Where is the idea strongest and weakest? What is the most likely way it fails, and how would we know **early and cheaply**?
2. Reward design given the SNR table: denser or auxiliary *verifiable* targets (e.g. next-month changes in fundamentals, earnings revisions, inflation prints, volatility — which are far more predictable than returns), variance reduction, multi-horizon rewards, pooling across windows. Which would you use and why?
3. How to make the rationalisation step not fit noise (validation of lessons on other months; placebo rationalisation on permuted outcomes; anything better).
4. Leakage: how to measure and minimise re-identification in the anonymised arm (single-month contexts, fresh IDs, ranks instead of levels, a re-identification audit) — and whether the anonymised arm is worth having at all.
5. Alternative architectures that keep the spirit (LLM priors + learning from outcomes) with better odds: LLM as a residual critic over the quant model; LLM-generated features/hypotheses scored by the walk-forward (evolutionary search); LLM-elicited priors used as shrinkage targets for ridge/the net; anything else.
6. A phased plan with explicit kill criteria and a power-aware evaluation, and what must be pre-registered before any test is run.

Be concrete and critical. Assume the owner is an experienced quantitative investor.

## 6b. Corrections and a second proposal (added after a first outside review)

**Corrections.** The SNR table in section 2 was computed on one run of the net on the plain top-8 rule (1.57%/yr), not the 3.1% headline. The headline series itself: mean 0.260%/month, sd 1.52%/month, per-month SNR 0.171 (t ≈ 1.3 over 60 months, 2.76 over 260). Cross-sectional sd of a country's monthly excess ≈ 4.0%. A one-name swap made every month has incremental-return sd 0.80%/month; with 260 months the detectable increment at 80% power is ≈ 1.7%/yr (≈ 3.9%/yr with 48 forward months).

**Auxiliary targets measured.** Rolling 60-month ridge, out of sample, per-month rank-IC SNR for next-month *changes*: realised volatility 2.5, trailing EPS 1.0, long-term growth 0.90, forward EPS 0.68, ROE 0.66, inflation 0.60, 10-year yield 0.27 — versus next-month returns 0.13 and currency 0.12. (Caveats acknowledged: rolling forward-EPS changes can be mechanical; inflation can inherit base effects; predictable does not mean unpriced.)

**Second proposal — the hybrid (the owner's; currently the favoured main line).** A trained numeric model becomes a *toolkit* and a frontier LLM is the *decision-maker*. Every month the LLM calls point-in-time tools: (1) the default net's score and rank per country; (2) a multi-head model forecasting next-month changes in fundamentals with uncertainty; (3) factor attributions; (4) trailing track record of factor families and of the model; (5) precedents (similar past cross-sections and what followed); (6) forward only — that month's news per country. The LLM starts from the model's buffered portfolio and may swap at most one or two names with a fixed reason code. Evaluation: incremental return versus the baseline over all calendar months, multiple agent runs per month, an anonymised tools-only historical arm, and a prospective arm with names and news. One reviewer's view: the toolkit is the strongest part; whether the LLM-in-the-loop adds anything beyond a small fitted model on the same tool outputs is the unproven question; news is the strongest reason for an inference-time LLM; precedents and explanations are storytelling hazards.

## 7. How to answer (council instructions)

- Address **both** the original RL proposal and the hybrid. Generate several independent hypotheses about whether and how each can work **before** converging.
- Name hidden couplings and missed invariants (between the anonymisation, the reward noise, the walk-forward, the agent's non-determinism, the tools' shared inputs), and the failure modes most likely to produce a convincing-looking but false positive.
- Give a validation plan that can genuinely **falsify** each idea, cheap early tests first, explicit kill criteria, and what must be pre-registered. Say which of the two you would build first and why, and anything both proposals miss.
- Reason from first principles; do not rely on citing literature.
