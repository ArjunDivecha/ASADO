---
title: "An LLM that reasons about countries — a developed proposal for discussion"
subtitle: "Country top-8 ranking project · 7 October 2026 · not yet tested"
---

# The short version

**Your hybrid is the right main line. The original reinforcement-learning design is the wrong place to start.** Both outside reviewers and my own numbers converge on this independently. Building a model that knows and predicts things, and letting a frontier LLM use it, plays each part to its strength. Training a language model on 60 noisy rewards per window does not.

The reviewers sharpen the hybrid in one important way. Sakana frames it as a ladder, so each rung's contribution can be measured separately:

- **A.** Today's default model, frozen.
- **B.** The default plus a small fitted model using a new toolkit: forecasts of next month's fundamentals, which are five to nineteen times more predictable than returns.
- **C.** B plus news, turned into structured features and fed to the same kind of mechanical rule.
- **D.** An LLM making the decision itself, from exactly the information C had.

B tests whether the toolkit adds anything. C tests whether news adds anything. D tests whether the LLM's judgment adds anything beyond a fitted rule. Both reviewers rate news as the clearest genuinely new information an LLM can bring.

**Your GDELT instinct has substance.** The retired GDELT pipeline left a daily news dataset that no model has ever used. It covers every country, every day, February 2015 to April 2026: 568 theme shares (debt, taxation, elections, protests, corruption, the stock market…), 75 emotion and uncertainty measures, and 24 political-event measures. Our models have only seen 46 monthly tone and attention summaries. This is the raw material for rung C. Its historical test is clean, because the features are computed by GDELT, not by an LLM that knows how history turned out.

**The evaluation is harder than the build.** A named frontier LLM cannot be backtested honestly, because it has read the history. Hiding names doesn't hide identity: countries are re-identifiable 94% of the time. And an override adding 1–2% a year takes many years to prove forward. So the order is: build the toolkit and the clean news features first, measure each rung, then put the LLM in the loop and judge it forward.

Nothing here has been tested. This document is for deciding what to test.

# What we are trying to get from an LLM

Your thesis has three parts, and they need different evidence.

- **Experience.** An LLM has absorbed far more economic history than our 320 months: how inflation shocks transmit, how currency defences fail, when cheap markets stay cheap. That is a prior, and priors are exactly what is scarce when each training window holds 60 months.
- **Context.** It can read what the factors cannot see: capital controls, disputed elections, a central bank defending a peg, an accounting change that makes a number misleading.
- **Polluted knowledge is still knowledge.** What it knows about how history turned out spoils any backtest. But the same knowledge, as experience, can be genuinely valuable for forward decisions, like a portfolio manager who lived through 2008.

The first two can in principle be tested historically in a limited way. The third can only be judged forward.

# Five facts that shape every design

**1. Returns are among the least learnable things in the panel.** The default model's monthly excess return has a signal-to-noise ratio of 0.17 per month. That is a t-statistic of about 1.3 over a 60-month training window, and 2.8 over the full 260 months. Even at the edge we already have, one window carries very little evidence about whether a policy is good.

**2. Fundamentals are far more learnable than returns.** I fitted the same rolling five-year ridge to forecast next month's *change* in fundamentals instead of returns, scored out of sample. Per-month signal-to-noise:

| next-month change in | signal-to-noise per month |
|---|---|
| realised volatility | 2.48 |
| trailing earnings | 0.99 |
| long-term growth estimate | 0.90 |
| forward earnings estimate | 0.68 |
| return on equity | 0.66 |
| inflation | 0.60 |
| 10-year yield | 0.27 |
| **returns** | **0.13** |
| currency | 0.12 |

Fundamentals come out five to nineteen times more learnable than returns. The two market prices, currency and returns, are the least predictable, which is what efficient-ish markets imply. GPT adds three cautions. Rolling forward-earnings estimates change mechanically when the forecast year rolls, so fixed-fiscal-year consensus should be used. Inflation changes inherit base effects. And predictable does not mean unpriced.

**3. Hiding names does not hide identity.** A country's factor ranks barely change month to month (median autocorrelation 0.91). A nearest-neighbour match on its rank vector re-identifies it the next month 94% of the time. Anonymisation therefore only works one month per context, with fresh random IDs. Even then it is a diagnostic, not a guarantee.

**4. Overrides are expensive to prove.** Swapping one of the eight names every month adds incremental-return noise of 0.8% a month. Over our 260 months, an override process adding 2% a year would be detected with about 92% power; one adding 1% a year, only 39%. Over four forward years those powers fall to 30% and 11%. The obstacle to a historical test is contamination, not power. The obstacle to a forward test is time.

**5. Overrides need real skill.** Adding 1% a year from one swap a month needs the incoming country to beat the outgoing one by 0.67% a month on average. That is like winning about 55% of swaps; adding 2% a year means winning about 59%. If the LLM acts only a quarter of the time, each intervention needs a 2.7% edge. Selectivity only helps if the selected decisions are that much better.

# The designs, in the order I would build them

## 1. The toolkit (rung B) — build first, whatever else we decide

This is your "model trained to know and predict stuff". It is a set of walk-forward, point-in-time models whose outputs are useful to a human, a mechanical rule or an LLM alike.

- **Return score:** the default net's score and rank for each country, its buffered holdings, and the gaps between adjacent scores.
- **Fundamental forecasts:** one head each for next-month changes in earnings, inflation and volatility, with calibrated uncertainty. Each head must beat a simple baseline (persistence, revision momentum, an autoregressive volatility model) by a pre-set margin, for example 5% lower out-of-sample loss. Otherwise it is not used.
- **Input health:** how fresh each input is, definition changes and missing data. GPT rates "the model is running on stale or misleading inputs" as one of the best reasons for an override.

Two of today's lessons apply directly. Every head should be a large seed ensemble, because single trained models proved unstable. And every output must be genuinely out of sample at the date it is used, including any track record shown.

**The mechanical comparator (rung B).** A small fitted model that takes the toolkit's outputs and adjusts the default ranking. If adding earnings and volatility forecasts improves the basket mechanically, that is a toolkit success, not evidence for the LLM. This is the comparator both reviewers insist on.

## 2. The hybrid — the LLM as decision-maker (rung D)

Each month the LLM starts from the default model's actual buffered portfolio and may replace at most one holding. Candidates come from a fixed set: the three lowest-ranked holdings against the three highest-ranked non-holdings, nine possible swaps. Abstaining is always allowed. The override lasts one month, then the portfolio reverts to the baseline's own buffer state, so small discretion cannot drift into a different portfolio.

**What an override must contain:**
- incoming and outgoing country, with one reason code;
- the exact tool outputs, with timestamps, that support it;
- why the baseline misses or misreads that evidence;
- a stated fundamental expectation, kept separate from the expected return;
- one observable forecast and one falsifier.

Reason codes are limited to three:
- new information absent from the numbers;
- verified input or model invalidity;
- a pre-registered conditional relationship.

"The macro outlook looks better" does not qualify.

**Reproducibility filter.** Each month, five independent calls run on the same frozen snapshot. An override is executed only if at least four of them propose the same swap. This is a stability filter, not a confidence measure, and five calls are not five observations.

**Tools to include and exclude.** Include the return score, the fundamental forecasts, input health and, in the forward named version only, timestamped news. Exclude precedents ("similar past months") from the first version. They are a leakage channel, crisis months cluster, and they invite narrative cherry-picking. Factor attributions are shown only to check inputs. LLMs anchor on explanations, and "the model leans on valuation" is not a reason valuation will work. The heads share inputs, so the LLM must not count agreement between them as independent confirmation.

**Scoring the reasoning, not just the returns.** If the agent keeps overriding on "earnings will surprise", its own earnings calls should beat the earnings head. If they don't, the stated mechanism is failing long before returns can say anything. This is the most informative early signal the hybrid offers.

## 3. Cheap ways to use the LLM's knowledge without putting it in the loop

- **LLM-proposed features.** Ask for at most six explicit interactions or transformations, for example "valuation matters only when earnings revisions are positive". Compute them in code, then fit a small, heavily regularised model to the default's out-of-sample mistakes.
- **LLM priors for the linear model.** Elicit signs and rough sizes for factor families, and shrink ridge toward those priors instead of toward zero. Compare against the zero-centred version. This tests whether the economic prior improves estimation.

GPT's first choice for spending the first research dollar is the question these answer: does a small, explicit economic prior improve the existing model's mistakes?

## 4. The original idea, rebuilt as a research track

Reasoning traces fitted to realised winners would teach a model to explain shocks as if they were signals. And because we observe every country's return every month, policy-gradient RL buys nothing that supervised learning cannot. If we pursue the spirit of the idea, it should look like this:

- **Hypotheses before outcomes.** The LLM proposes falsifiable rules without seeing the answers. Outcomes then decide which rules earn weight. Inside each five-year window: propose up to ten rules on the first 36 months, select up to three on the next 12, assess on the last 12, then walk forward. If nothing survives, the answer is "no adjustment".
- **Three-way comparison.** Rules written without outcomes, rules learned from real outcomes, and rules learned from placebo outcomes. The placebo reruns every outcome-dependent step, not just the final scoring.
- **Supervised training before RL.** If weights are ever trained, supervised training on documented forecast errors must beat the frozen model before GRPO is considered. Auxiliary targets stay separate losses, not one blended reward. One technical trap: in GRPO, subtracting the baseline's return from every rollout changes nothing once rewards are normalised within the group.
- **Pooled history for representation, recent five years for adaptation.** This one is your call (see below).

# News: what GDELT could give beyond what we use today

**What exists.** The live GDELT store, refreshed nightly, has daily tone, attention, tone dispersion and local-versus-foreign coverage for every country since February 2015. The model has only seen monthly summaries of it. The retired GDELT pipeline kept a much richer daily file that no model has ever touched:

- **568 theme shares:** the fraction of a country's coverage about each topic, for example debt, taxation, elections, protests, corruption, housing prices, the stock market and disease.
- **75 emotion and uncertainty measures:** for example litigious, uncertainty and modal-strength word counts from finance dictionaries.
- **24 political-event measures:** counts of protests, assaults, threats and cooperation, and a cooperation-to-conflict score.

It covers February 2015 to April 2026, about 135 months. It stopped when the pipeline was retired, and it was never validated.

**Why the current use probably leaves value on the table.** Monthly tone mostly follows prices: bad markets produce bad news, so its level carries little that returns don't already show. The value is more likely in four places:

1. **Surprise and novelty.** A theme that suddenly dominates a country's coverage relative to its own norm: capital controls, a debt restructuring, an IMF programme.
2. **Topics that aren't about prices.** Policy, institutions, conflict, elections.
3. **Uncertainty and disagreement.** Tone dispersion was the strongest top-8 basket in the original single-factor screen.
4. **Timing.** What happened in the final week before the rebalance, which daily data allows and monthly data hides.

**Two ways to use it, with different evidence:**

- **Mechanical features (rung C, historical test possible).** Turn the daily file into point-in-time monthly features: theme-share surprises against each country's trailing norm, uncertainty spikes, event counts, late-month shifts. Run them through the same rolling walk-forward. Because GDELT computes the features with fixed dictionaries, an LLM's hindsight never touches them. That makes this the cleanest test of the news idea we can run.
- **LLM-read news (rungs C and D, forward).** An LLM classifies what happened (event type, direction, novelty, whether it is price-relevant) into structured fields. A mechanical rule decides what to do with them. Using the LLM to describe what happened, not to forecast what happens next, sharply limits how much its hindsight can leak in. Historically this needs article text. The article archive was deleted in July's GDELT cleanup, so it would have to be re-fetched from GDELT's links. Forward, it is straightforward.

**The controls Sakana insists on, and I agree:** the matched current news must beat stale news (from an earlier month) and country-shuffled news (another country's coverage). Only then is it the news itself doing the work, not some property of having more inputs.

**Honest limits.** About 135 months gives weak statistical power. With a 0.8% monthly noise level, only effects of roughly 2.5% a year or more would be reliably detected. The theme taxonomy drifts over time. And restarting the retired pipeline for forward use is a change in the GDELT repository that needs your approval.

# The contamination question

GPT sharpened this usefully. Country identity is legitimate at investment time. The danger is the combination of knowing which country and period this is, recognising the historical episode, and remembering what happened next. The audits should measure each separately: can the LLM name the country, name the period, name both, and then recall the outcome? Use both an LLM attacker and an ordinary classifier. Flag country identification above 10% (chance is 3%), or period identification above twice chance. GDELT's 2015 start date is itself a period clue.

Two corrections to what I told you earlier:
- **Named is not a clean upper bound.** Names can bring stereotypes, and the model may not remember monthly rankings. A failed named arm screens the idea out but does not kill it.
- **The cleaner historical control is point-in-time models.** These are language models trained only on text up to a date. GPT cites recent work building such checkpoints for 2013–2024. Their provenance needs checking, and they are weaker than today's frontier models, but they would give a historical test without hindsight.

Real evidence for rung D starts with timestamped forecasts from a frozen procedure, going forward.

# How we would decide

GPT proposes, and I agree, separating three decisions with three different standards:

- **Fund the research:** a credible mechanism, reliable operation, a finite budget. No proof of alpha needed.
- **Run a small capital experiment:** an explicit risk budget, called an experiment. GPT's illustration:
  - cap the LLM sleeve at 10% of capital;
  - stop at a 0.5% overall relative drawdown;
  - require six clean monthly cycles first;
  - review at 24 months, and treat fewer than ten overrides as not yet evaluable.
- **Promote to the strategy:** evidence of incremental net value. Operational consistency alone does not count.

For the middle decision, a Bayesian rule fixed in advance is defensible. Example: with a prior centred on zero (1% standard deviation), four years at +2% a year would give an 80% probability that the edge is positive, and a 2% probability that it is worse than −1%. That could justify a small allocation. It would not establish a 2% edge. The prior has to be chosen before results are seen.

**Minimum worthwhile improvement:** GPT suggests 1% a year net of incremental costs, with futility stopping if the upper confidence bound falls below it. "Inconclusive" is a legitimate outcome and must not be relabelled as "no effect".

# Phased programme with gates

| Phase | What | Gate to continue | Rough cost |
|--|--------------------------------|------------------|--------|
| 0 | **Freeze and audit.** Reproduce the 3.1% default exactly. Build every legal one-swap reward per month, and the one-swap ceiling (best possible, random, near-cut-off). Run power with realistic dependence. Audit data vintages. | Default reproduces exactly; the ceiling leaves room after costs | Compute only, about 1–2 days |
| 0b | **Capability and leakage checks.** Synthetic tables with known rules (≥95% correct). Five row reorderings (≥7.5 of 8 picks unchanged). Country and period re-identification attacks on the exact packets the LLM would see. | All pass; anything identity-free must re-identify countries at no more than about 6% (twice chance) | ≤ $100 API, 2 days |
| 1 | **Rung B: the toolkit.** Fundamental-forecast heads (earnings, inflation, volatility) and input health, each a seed ensemble. Plus a small fitted model that may swap one name. | Each head beats its simple baseline; B − A reported over several runs, with a futility stop if its upper bound is below 1%/yr | Compute only |
| 2 | **Rung C: news.** Mechanical features from the daily GDELT theme, emotion and event file (2015–2026). Same mechanical swap rule. Stale-news and country-shuffled-news controls. | Matched news beats both controls; C − B reported | Compute only |
| 3 | **Rung D: the LLM decides,** with exactly C's information. One swap from a fixed candidate set. Five calls, act if four agree. Reason codes, falsifiable forecasts. | Stability ≤10% format-driven changes; reasons actually drive actions; D − C upper bound above 0.5%/yr, else stop | API calls: tens to low hundreds of dollars |
| 4 | **Forward, frozen and timestamped:** A, B, C, D and a named, live-news version of D, with an input hash committed before each month. | Six clean cycles before any capital; then the decision rules above | Small monthly cost |
| R | **Research track:** hypotheses-first rule generation; full placebo pipeline | Only if D beats C | Larger; cloud GPUs if weights are ever trained |

# What must be pre-registered before anything runs

- The primary comparison: incremental return of the candidate over the baseline, every calendar month including abstentions, net of costs.
- The minimum worthwhile effect, the decision rule, review dates and the stopping rules.
- The data:
  - vintages and publication timing;
  - the country set;
  - currency and return conventions;
  - execution timing and costs.
- The model checkpoint and version, the prompt and tools, and exactly what information each rung sees.
- The candidate set, the abstention rule and the five-call agreement rule.
- How model or prompt changes start a new record without erasing the old one's results.
- An honest list of what has already been looked at. The 2005–2026 history has been inspected all day and cannot be called untouched.

# Decisions for you

1. **Do we adopt the ladder (A → B → C → D) as the plan?** It builds the toolkit and news features first and tests the LLM's judgment last, on equal information. That is a slower path to "the LLM decides" than your hybrid as first stated, but every rung tells us something.
2. **Rolling five years, or a stable model on all history plus a recent-years head?** Both reviewers push back on pure five-year relearning for the toolkit. GPT says "the world changes" argues for adapting, not for deleting history. Sakana calls a long-lived prior plus five-year relearning "internally inconsistent". Your rolling preference is also why the default holds up evenly across decades. My suggestion is to build both and compare. Your call.
3. **The evidence standard for capital:** the Bayesian rule, the minimum effect, the sleeve size and the stop.
4. **Which LLMs.** Pin versions. Each model upgrade starts a new forward record, and record each model's knowledge cutoff.
5. **Restart the GDELT theme/emotion/event pipeline?** It stopped in April 2026. The historical test (rung C) can run on what exists, but forward use needs it running again. That's a change in the GDELT repository, so it's yours to approve.
6. **Data upgrades.** Point-in-time fixed-fiscal-year consensus earnings and first-release macro prints with consensus would make the fundamental heads much more honest. Bloomberg can likely supply both. That's a deliberate pull, given how expensive Bloomberg data is to re-fetch.

# What the outside reviewers said

**GPT (gpt-6-astra, extra-high effort), round 1, on the original idea.** It would fund a small experiment in LLM-derived priors, and would not build the rationalise → train → RL pipeline. That pipeline's likely achievement is "convincing explanations for historical noise", and it treats realised winners as reasoning targets when they are mostly luck. It caught three errors in my brief. The noise table came from a weaker run than the headline. The t-statistic I quoted mixed two rewards. My "months needed" figure was a 50%-power landmark, not a real power design. It also says nothing yet establishes a 3% ceiling. Full response saved with this document.

**GPT, round 2, on your hybrid.** It calls the hybrid "substantially better" than the RL proposal and says to test it. But it would not yet make the LLM decision-maker the preferred architecture. The toolkit is the strongest improvement, and whether handing its outputs to an LLM improves decisions is "a separate, unproven hypothesis". It says the strongest case for an LLM at decision time is new information (news, policy, accounting changes) and input invalidity, not re-ranking eighth versus ninth. Most of the concrete design above comes from this round: the 3×3 swap set, the five-call agreement rule, the reason codes, the four frozen comparison books (which Sakana's ladder refines), and the gates. Its closing line is worth quoting: *"I would fund this as a test of whether source-grounded contextual judgment improves a strong numeric baseline. I would not fund it on the premise that predictable fundamentals plus fluent reasoning naturally produce superior return decisions. That missing link is the research question."*

**Sakana council (Fugu Ultra, deep tier, web search off; about $2.20).** Its verdict is REVISE. It separates the substantive hypothesis from the proposed mechanism:
- **The hypothesis is plausible:** a pretrained LLM carries economic priors useful for country allocation.
- **The mechanism is poorly matched:** hindsight rationalisation followed by RL is "likely to manufacture coherent explanations for noise".

It lays out nine competing hypotheses. Its strongest plausible combination is that news supplies genuinely new information, plus a tightly constrained "veto" skill for rare risk, data-quality and investability failures.

The ladder A → B → C → D above is its recommendation. Build A, B and C first; then test D with exactly C's information, "so the owner's allocation hypothesis is genuinely tested rather than avoided".

Other points worth keeping:
- **The hybrid's right reward is the paired action advantage.** The return of the country swapped in minus the one swapped out, after costs. The benchmark cancels out of that. There are about 208 legal one-name swaps each month, all observable after the fact, so this is a full-information problem: direct action-value learning, not policy gradients.
- **The economic action ceiling.** Before building anything, compute the best possible one-swap result in hindsight, the distribution of random swaps, and the opportunity set near the cut-off. If even perfect swaps barely move the portfolio after costs, the machinery isn't worth building.
- **Windows.** "A long-lived economic prior combined with complete relearning from only 60 months is internally inconsistent." It suggests a stable model trained on all history, with a small recency-weighted head on top. That is the same point GPT made, put more sharply.
- **Placebos must rerun the whole pipeline.** If hypothesis generation is ever outcome-fed, run the entire pipeline on at least 199 placebo datasets. Real lessons must beat the 99th percentile of the best placebo result.
- **Its three next packages:** a reward-and-power notebook; a leakage and placebo harness; and the A/B/C ladder.

Full response saved with this document.

# Where I land, and where I'd push back

I agree with almost all of GPT's restructuring. In particular:
- the mechanical toolkit is the comparator that matters;
- precedents and explanations are hazards;
- "harmless and consistent" must not be mistaken for evidence of value.

Two places I'd push back gently. First, the rolling-versus-pooled question is a genuine judgment call, not an error. Your "the world changes" view is the reason the default holds up evenly across decades, so the comparison should be run rather than assumed. Second, I'd keep the anonymised historical arm smaller than GPT's framing suggests. Its realistic job is to catch an LLM that is unstable, ignores its tools or invents facts, not to estimate alpha. Running it cheaply for that purpose is worth it.

Files: the brief sent to both reviewers (`BRIEF.md`), my working notes (`NOTES_own_analysis.md`), and the full reviewer responses (`consults/`), all in this folder.
