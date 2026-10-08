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

**Correction (later on 7 October).** The first version of this document said the deep GDELT file had never been used and that an LLM on numeric inputs was an open question. Both statements were wrong; I had not checked Investment Learnings. The deep GDELT panel died in a 27 July walk-forward, and in July an LLM reading numeric country dossiers predicted nothing. Rung D now depends on text, not numbers, and rung C is narrowed to the GDELT angles nobody has tested. The section "What has already been tried" sets out the record.

**News is still the most promising thing an LLM can add, but it is not untouched ground.** Broad tests of GDELT as a return predictor have failed at both monthly and daily frequency. Two things remain open. One is news as *conditioning*, meaning when to trust or override the default model, which is the only role the research agenda leaves GDELT. The other is news an LLM *reads*, which has never been tested.

**The evaluation is harder than the build.** A named frontier LLM cannot be backtested honestly, because it has read the history. Hiding names doesn't hide identity: countries are re-identifiable 94% of the time. And an override adding 1–2% a year takes many years to prove forward. So the order is: build the toolkit and the clean news features first, measure each rung, then put the LLM in the loop and judge it forward.

Nothing here has been tested. This document is for deciding what to test.

# What has already been tried

**An LLM reading numbers (July 2026, dead).** The LLM-1M Country Rotation project gave a frozen, blinded LLM a monthly dossier of about 30 z-scored fields for each of the 34 countries. The LLM scored six sub-scores, and a ridge combined them. Out of sample, over 197 months, the rank correlation with next-month returns was 0.002, and the permutation canary failed. A plain gradient-boosted model on the same raw fields beat the LLM by about two to one in the burn-in decade. The lesson recorded: LLMs are not feature extractors for numeric panels. Two parts of it carry over to this design. The blinding protocol worked operationally. And a tabular model on the same inputs is the kill baseline, which is exactly what rungs B and C are.

**GDELT as a monthly predictor (dead, several times).**
- The gdelt_narrative_v2 Stage 1 test (27 July) ran a walk-forward over 2017–2021 on the 34 buckets, with the 2022–26 lockbox untouched. The 93-variable keep-list scored a rank correlation of −0.019 with trees and +0.014 with ridge. The full deep panel (about 1,100 columns of themes, emotions and events) scored −0.033 at t −2.2. All three failed the permutation canary. That deep panel is the file the first draft of this document called unused.
- In T2 GDELT, GDELT factors run through the T2 factor-timing optimizer gave a Sharpe of 0.07. Equal-weighting every factor beat any selection of them.
- In this project, dropping all 92 GDELT factors from the default model costs about 0.5% a year, at t −1.4. That contribution is small and not significant.
- The research agenda (v2) excludes standalone GDELT projects. GDELT tone survives only as a conditioning input.

**GDELT at daily frequency (weak, no verdict).** The GDELT Factor Timing Fuzzy Daily project ran 74 daily tone and attention factors through the daily factor-timing stack. The optimised strategy earned about 1% a year at a Sharpe of 0.22. Across the 74 factors, the average information ratio was roughly zero. It has no Investment Learnings entry. Daily country-ETF timing also has an earned law against it: index-space alpha is about zero at the US-listed ETF close.

**Still open.**
- *Narrative freshness* (H_20260727_003): do stories that are new, as opposed to ones that keep running, carry the signal? The hypothesis is registered and its measurement is gated. The embedding build it needs stalled on 5 August, after repeated kills, with features complete only through August 2015.
- *GDELT as conditioning* — **tested 7 October, FAIL** (`gdelt_veto/`). The most-shocked holding beat the other seven by 0.4% a month (t +0.9), inside the country-shuffled null and matched by stale news. Acting on it would have cost 1.4% a year. No component, window or gating variant was significant. A useful effect is excluded by the interval.
- *Last-week timing* — covered by the 7- and 14-day windows of the veto test. Nothing.
- *LLM-read text*. Never tested historically. The article archive was deleted in July, so this works forward only, unless articles are re-fetched from GDELT's links.
- *Daily theme and event data*. Does not exist: the daily deep file is a schema without content. Any daily news test is limited to tone, attention, dispersion and risk.

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

**Restricted after LLM-1M.** An LLM given only numbers (toolkit outputs, scores, fundamentals) is a re-run of LLM-1M, which died. So rung D is tested only where the LLM gets something a fitted rule cannot easily use: text (news, policy statements) and checks on whether inputs are valid. A numeric-only rung D can still run cheaply as a stability and tool-use check (phase 0b), but it is not a test of value.

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

**What exists.** The live GDELT store is refreshed nightly. It holds daily tone, attention, tone dispersion and local-versus-foreign coverage for every country since February 2015. That is the only daily news data we have. The retired deep pipeline's daily file has columns for 568 theme shares, 75 emotion measures and 24 event measures, but on inspection (7 October, evening) those columns are empty: about 0.1% of cells are filled, all in 2026, and the event columns are entirely blank for our 31 countries. The theme, emotion and event content exists only at monthly frequency, in the file that was tested and killed on 27 July. The article-level archive that could regenerate daily themes was deleted in July.

**What has failed.** Using these series as broad predictors of next-month returns has failed. The keep-list, the full deep panel and the T2 factor-timing stack all failed, and the daily factor-timing version was weak. Monthly tone mostly follows prices: bad markets produce bad news. Rebuilding wide monthly theme features and putting them through another walk-forward would be a fourth attempt at a dead idea. I am dropping that from the plan.

**What is left, narrowly.**

1. **Conditioning, meaning a veto — now tested and dead.** Does a sharp news shock in the weeks before rebalance predict that one of the default model's holdings will lag the others? Pre-registered and run on 7 October over 124 months: no. The shocked holding did marginally better, not worse, and stale news did the same. A second pre-registered rule the same evening — run the default model but make any country with a news score of −1 or worse ineligible — cost 1.2% a year against the untouched default, and every tighter threshold lost more. A third — boost countries with good news up the ranking — cost 0.2% a year; its contrarian mirror showed one t of 2.3 in a 27-cell grid with a sign flip next door, i.e. noise. Details in `gdelt_veto/README.md`.
2. **Last-week timing.** Whether moves in the final days before rebalance carry information that monthly averages wash out. This folds into test 1 as one of its feature windows.
3. **Narrative freshness** (H_20260727_003). The open hypothesis is that new stories, unlike continuing ones, move prices. Testing it needs the stalled embedding build finished, about 73 hours of compute by the original estimate.
4. **LLM-read news (rung D, forward).** An LLM classifies what happened (event type, direction, novelty, whether it is price-relevant) into structured fields, and a mechanical rule decides what to do. Asking the LLM to describe events rather than forecast them limits how much its hindsight can leak in. A historical test needs article text re-fetched from GDELT's links. Forward, it is straightforward.

**The controls Sakana insists on, and I agree:** the matched current news must beat stale news (from an earlier month) and country-shuffled news (another country's coverage). Only then is the news itself doing the work, rather than some property of having more inputs.

**Honest limits.** The overlap between GDELT (from 2015) and the default model's out-of-sample record is about 130 months. Only veto effects of roughly 2.5% a year or more would be reliably detected. The 2015 start date also means every GDELT test sits inside a period that has been looked at heavily.

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
| 2 | **Rung C: news as conditioning.** ~~One pre-registered veto test~~ **Run 7 October: FAIL.** Pre-rebalance GDELT shocks do not flag lagging holdings (t +0.9, wrong sign, inside the shuffled null). Rung C with GDELT aggregates is closed; news re-enters only as text in rung D. | — | done |
| 3 | **Rung D: the LLM decides,** with C's information plus text. A numbers-only D is a stability check only, since LLM-1M already failed that way. One swap from a fixed candidate set. Five calls, act if four agree. Reason codes, falsifiable forecasts. | Stability ≤10% format-driven changes; reasons actually drive actions; D − C upper bound above 0.5%/yr, else stop | API calls: tens to low hundreds of dollars |
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
2. **Rolling five years, or a stable model on all history plus a recent-years head?** Both reviewers pushed for the second. **Tested 7 October (`ema_window/`): rolling wins.** Expanding-window training with half-lives of 24, 36, 60 and 120 months, three seed draws each, was indistinguishable from rolling-60 on the pooled comparison (every paired t inside ±0.7) and far less stable across draws (spreads of 2.7–4.5 points against 0.26 for rolling). The default stays rolling-60; the toolkit heads should follow the same window unless a head-specific test says otherwise.
3. **The evidence standard for capital:** the Bayesian rule, the minimum effect, the sleeve size and the stop.
4. **Which LLMs.** Pin versions. Each model upgrade starts a new forward record, and record each model's knowledge cutoff.
5. **GDELT.** Answered 7 October: the veto test failed, and the daily deep file turned out to hold no theme or event data. Do not restart the deep pipeline. The only open GDELT item is the stalled narrative-freshness build (H_20260727_003, about 73 hours of compute), which is a GDELT-repo decision, not this project's.
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
