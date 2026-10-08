## 1. Multi-Agent Synthesis

The central distinction is between:

1. **The substantive hypothesis:** a pretrained LLM contains transferable economic priors that are useful for country allocation.
2. **The proposed learning mechanism:** hindsight rationalisation followed by SFT/GRPO on realised returns.

The first is plausible. The second is poorly matched to the information structure and is likely to manufacture coherent explanations for noise.

### Quantitative implications of the corrections

For the actual headline series:

\[
t_{60}=\frac{0.260}{1.52}\sqrt{60}=1.33,\qquad
t_{260}=2.76,\qquad
IR=\frac{0.260}{1.52}\sqrt{12}=0.59.
\]

Thus the correction raises the evidence in a 60-month window from roughly \(t=0.8\) to \(t=1.3\), but that is evidence about one already-selected policy. It is not enough to select among many prompts, reasoning policies, lessons, horizons, seeds, and RL configurations.

For one swap per month with monthly incremental-return standard deviation \(0.80\%\):

\[
SE_{\text{annual}}=\frac{12(0.80\%)}{\sqrt N}.
\]

| Sample | Annualized SE | 80%-power MDE at 5% two-sided |
|---|---:|---:|
| 260 months | 0.595% | \(2.80 \times 0.595=1.67\%\) |
| 48 months | 1.386% | \(2.80 \times 1.386=3.88\%\) |

A true 1%/year overlay has monthly SNR \(0.0833/0.80=0.104\). Its required sample is approximately:

\[
N=\left(\frac{2.80\times0.80}{0.0833}\right)^2\approx723\text{ months}.
\]

Serial dependence, policy search, or multiplicity increases that requirement.

The quoted 48-month \(\pm2.6\%\) figure for the full basket is approximately **one** standard error:

\[
12(1.52\%)/\sqrt{48}=2.63\%\text{/year};
\]

a nominal 95% half-width would be about 5.2%/year. The one-swap comparison is more precise, but still cannot confirm modest alpha in four years.

The initial reward table came from a different, weaker run. Rank IC, pairwise accuracy, and long-short rewards must be recomputed on the same frozen 30-seed, buffered portfolio before comparing them.

### Strongest and weakest elements

| Proposal | Strongest element | Weakest element |
|---|---|---|
| Original RL | A pretrained economic prior may impose useful signs, interactions, and regime logic that cannot be estimated from 60 months. | A realised one-month ranking is not a latent “correct answer”; it is predominantly a noisy draw. Hindsight rationales will explain the noise. |
| Hybrid | It anchors to the incumbent, permits paired residual evaluation, and can add genuinely omitted information through news. | Most tools are correlated transformations of the same 238 inputs. There is no reason yet to think an LLM combines them better than a small fitted model. |
| Auxiliary toolkit | Several targets are highly predictable and independently auditable. | Predictability can be mechanical and does not imply that the change is unpriced. |
| News component | It is the clearest genuinely new information channel. | Timestamp leakage, pretrained-model memory, immediate price incorporation, and API drift are substantial risks. |

The most likely false positive is a compelling historical uplift created by some mixture of country/date re-identification, pretrained memory, overlapping-window reuse, prompt selection, precedents, and choosing favourable agent runs. It will look economically coherent, may be concentrated in a few crises, and then disappear prospectively.

Three training runs demonstrate operational reproducibility; they are not three independent market samples.

## 2. Independent Hypotheses

These hypotheses make different predictions and should not be blended into one vague “LLMs may help” claim.

### Original proposal

| ID | Hypothesis | Distinguishing prediction | Falsifier |
|---|---|---|---|
| O1 | **Transferable structural prior.** The LLM knows robust economic relationships between valuation, revisions, inflation, policy, and market regimes. | Rules generated without outcomes, names, or dates transfer to later periods or other asset universes. | Gains require recognisable countries/dates or disappear on genuinely post-cutoff data. |
| O2 | **Auxiliary representation.** Predicting fundamentals teaches a useful economic state representation. | A frozen auxiliary encoder improves swap returns conditional on the incumbent score and versus a same-capacity return-only model. | Excellent auxiliary IC produces no residual return information. |
| O3 | **Hindsight rationalisation works.** Repeated outcome-fed explanations identify recurring causal lessons. | The true-outcome pipeline materially exceeds a complete permuted-outcome pipeline on later, untouched months. | True and permuted outcomes generate equally convincing and equally profitable “lessons.” |
| O4 | **Memory/re-identification drives the result.** | Performance rises sharply with identity confidence and is reproduced by names/date-only controls. | Performance survives severe identity scrubbing and a frozen post-cutoff test. |

O1 and O2 are plausible. O3 is unlikely as currently designed. O4 is a major threat given 93.5% re-identification.

### Hybrid proposal

| ID | Hypothesis | Distinguishing prediction | Falsifier |
|---|---|---|---|
| H1 | **Numeric residual information.** Toolkit outputs identify occasional incumbent errors. | A small regularized action model adds net paired return at fixed coverage. | Toolkit outputs have no return information conditional on the incumbent. |
| H2 | **Orthogonal news semantics.** The LLM extracts sanctions, controls, elections, policy shifts, investability issues, or other events missing from numeric factors. | Correctly matched current news beats no-news, stale-news, and country-shuffled-news controls. | Current news performs no better than those controls. |
| H3 | **LLM allocation skill.** Given the same structured packet, LLM reasoning chooses better actions than a numeric allocator. | A constrained LLM allocator beats the numeric allocator at matched action rate and cost. | It is less stable or fails to add return over the same-information allocator. |
| H4 | **Conservative veto skill.** The LLM is useful primarily for rare risk, data-quality, and investability failures. | Sparse, evidence-supported vetoes outperform matched random vetoes and a baseline uncertainty rule. | Vetoes merely reduce exposure after vivid stories without improving the preregistered objective. |
| H5 | **Narrative-selection failure.** Rich precedents and attributions induce storytelling rather than prediction. | Results vary sharply by prompt/run, depend on a few months, or survive equally under shuffled precedents. | Stable gains survive all negative controls and prospective freezing. |

The strongest plausible combination is H2 plus a tightly constrained version of H4. H3 is worth testing directly, but it should not be assumed.

## 3. Recommended Path

### 3.1 Build the hybrid attribution ladder first

Use four frozen policies:

| Policy | Definition | Contrast identified |
|---|---|---|
| **A — Incumbent** | Exact frozen 30-seed buffered baseline | Reference |
| **B — Numeric residual** | Small regularized action model using numeric toolkit outputs | B−A: does the toolkit contain residual information? |
| **C — Semantic overlay** | B plus structured, timestamped features extracted from news by an LLM | C−B: does semantic extraction add information? |
| **D — Constrained LLM allocator** | LLM allocates using exactly the same structured packet available to C | D−C: does LLM decision-making add value? |

Build A/B/C first. Test D afterward with a tightly fixed interface so the owner’s allocation hypothesis is genuinely tested rather than avoided.

For the initial overlay:

- Start from the incumbent’s actual buffered portfolio.
- Permit at most one veto.
- Choose the replacement mechanically as the highest-ranked eligible incumbent candidate.
- Require a fixed reason code and timestamped evidence.
- Reset from the new incumbent portfolio each month; do not initially let overlay actions alter future buffer state.
- Abstain unless a calibrated numeric advantage threshold and fixed agent-consensus rule are met.

This isolates critic skill before testing unconstrained replacement selection.

Do **not** build the original free-form rationalisation/SFT/GRPO system now. Preserve its structural-prior thesis through cleaner mechanisms described below.

### 3.2 Reward design

For a baseline holding \(i\) replaced by \(j\):

\[
\Delta_t(i\rightarrow j)
=\frac{r_{j,t+1}-r_{i,t+1}}{8}
-c_t(i,j).
\]

The all-country benchmark cancels exactly. For two swaps, sum the two return differences, divide by eight, and subtract all incremental costs.

This is a missed invariant with two consequences:

1. The correct primary reward for the hybrid is the **net paired action advantage**, not full-portfolio rank IC.
2. Once the month has elapsed, all 34 returns are observed. The historical problem is therefore a **full-information contextual decision problem**, not a setting where only the chosen action reward is observed.

There are \(8\times26=208\) legal one-name swaps in a typical month. They can all be labelled for training, but they share the same 34 returns. They are not 208 independent observations; statistical inference must remain clustered by month.

GRPO can technically optimize a discrete output, but it creates no new information here. Direct action-value, pairwise, or listwise learning is simpler and lower variance.

#### Recommended use of auxiliary targets

The nominal 60-month \(t\)-values implied by the auxiliary rank-IC SNRs are approximately:

- realised volatility: 19.4;
- trailing EPS: 7.7;
- long-term growth: 7.0;
- forward EPS: 5.3;
- ROE: 5.1;
- inflation: 4.6;
- 10-year yield: 2.1;
- returns: 1.0.

Serial dependence and mechanical construction will reduce these values, but the ordering is clear. Use the targets to:

- pretrain or regularize a stable numeric representation;
- verify that tools work point in time;
- estimate economic state and uncertainty;
- create structured inputs for the action model.

Do not combine them with returns in one scalar reward. Otherwise the system can win by predicting volatility or inflation while adding no alpha.

For each auxiliary target:

- preserve exact release vintages;
- predict the next value actually released to investors;
- separate deterministic carry/base effects from innovations;
- calibrate uncertainty using prior out-of-sample residuals, not seed dispersion alone;
- test whether it adds return information conditional on the incumbent.

#### Variance reduction and horizon choices

Use:

- paired candidate-minus-incumbent returns;
- one fixed action budget;
- raw net returns as the final endpoint;
- robust or rank losses only for training;
- matched action coverage when comparing policies;
- month-clustered/HAC inference.

Multi-horizon targets may test whether structural priors work better over three or six months, but they are different investment policies. Use separate fixed heads and holding rules. Overlapping horizons do not add independent observations.

Do not pool the 22 rolling windows by duplicating the same months. Prefer:

- an expanding stable encoder trained on unique history;
- a small recency-weighted/local head;
- a half-life or recency weight selected only on development data.

A long-lived economic prior combined with complete relearning from only 60 months is internally inconsistent.

### 3.3 Replace free-form rationalisation with executable hypotheses

“At most two patterns per month” limits response length, not hypothesis-space size. Across months, prompts, and linguistic variants, the search remains effectively unbounded.

A cleaner process is:

1. **Generate hypotheses without outcomes.** Give the LLM factor definitions and the economic task, but no realised returns, names, dates, or recognisable episodes.
2. **Compile every hypothesis.** Each accepted lesson must specify:
   - variables and transformations;
   - sign or monotonicity;
   - interaction/regime;
   - horizon;
   - eligible observations;
   - action and abstention rule;
   - explicit failure condition.
3. **Use disjoint discovery and confirmation blocks.** Once a rule is selected, it cannot be rewritten after confirmation results are seen.
4. **Maintain a complete proposal ledger.** A revised rule is a new hypothesis and consumes a new test.
5. **Calibrate confidence empirically.** Self-reported LLM confidence is not uncertainty. Compare realised advantages by locked confidence bucket.
6. **Fine-tune only on validated rules**, not on month-specific hindsight stories.

If outcome-fed rationalisation is retained as an experiment, run the entire pipeline—generation, semantic deduplication, rule selection, training, and evaluation—on:

- true outcomes;
- within-month country permutations;
- circularly shifted 34-country return vectors;
- block-permuted months;
- shuffled or stale precedents.

Permuting labels only after lessons have been selected is not a valid placebo.

### 3.4 Leakage and the anonymised arm

Chance country identification is \(1/34=2.94\%\). A 93.5% nearest-neighbour result is more than 30 times chance and decisively invalidates the statement that the current packet is anonymous. The 87% result on only 20 factors shows that this is not a high-dimensional accident.

- Fresh IDs prevent explicit linkage but not profile recognition.
- Single-month contexts prevent direct sequence chaining but not recognition.
- Ranks do not solve the problem; the stated attack already uses ranks.
- The full 34-country macro configuration can reveal the era or date.
- Tool outputs, missingness patterns, precedents, and attributions can add further fingerprints.

Audit the exact packet provided to the policy using:

1. Chronological country classifiers: top-1, top-5, entropy, and calibration.
2. Year/month or regime classifiers using the full cross-section.
3. Direct LLM identity/date probes.
4. Names/date-only return-ranking controls over many months.
5. Performance conditional on re-identification confidence.
6. True-name, permuted-name, and IDs-only packets.
7. Progressive removal of persistent levels, missingness fingerprints, precedents, and stable country profiles.

For a redesigned arm, a reasonable preregistered practical threshold is top-1 country accuracy no greater than twice chance, approximately 5.9%, on a chronological holdout. Passing that test would only show that one adversary failed; it would not prove anonymity to a frontier model.

The arm remains useful as a **sensitivity ablation**: does performance decline as identity information is removed? It is not a clean estimate of “structural knowledge only.”

The named historical arm is also not an optimistic upper bound. Memory can help, hurt, or be retrieved unreliably. Success is contaminated; failure kills only that interface, not the structural-prior thesis. Credible named evaluation requires a frozen model tested prospectively after its genuine release/training date.

### 3.5 Better ways to encode the LLM prior

In order of attractiveness:

1. **LLM news extraction plus deterministic allocation.**
2. **LLM-elicited shrinkage priors.** Generate signs, monotonicities, and a small number of interactions from factor definitions only, then fit:
   \[
   \hat\beta=\arg\min_\beta L(\beta)+\lambda\|\beta-\beta_{\text{LLM}}\|^2.
   \]
   Compare with zero-prior and sign-randomized-prior controls.
3. **Finite executable hypothesis generation.** Score a fixed budget of machine-readable rules through nested walk-forward tests. Unlimited evolutionary search would simply move the multiple-testing problem.
4. **Strongly shrunk residual policy.** Keep the incumbent as the prior policy and learn only action advantages near the selection boundary.
5. **Risk and data-quality officer.** Use the LLM to flag sanctions, capital controls, investability, stale data, and unsupported tool outputs.
6. **Cross-asset transfer.** Generate or train priors on sectors, industries, or currencies, freeze them, and then test country markets. Domain transfer must itself be validated.

## 4. Risks and Hidden Assumptions

| Coupling or invariant | Consequence |
|---|---|
| **Shared tool inputs** | Auxiliary forecasts, attributions, factor track records, and the incumbent mostly derive from the same 238 variables. Agreement is not independent confirmation. |
| **Attributions are not signals** | They explain the incumbent score under a chosen reference method; they do not add information. |
| **Mechanical auxiliary predictability** | Volatility persistence, EPS roll-off, stale long-term-growth fields, and inflation base effects can generate high IC without economic surprise. |
| **Overlapping rolling windows** | A rule recurring in several annual windows may be supported by the same month repeatedly. |
| **Cross-sectional pseudo-replication** | The 208 swap labels share 34 returns. Training can use them, but portfolio inference remains month-clustered. |
| **Agent and seed pseudo-replication** | More calls or seeds reduce implementation variance; they do not create more market outcomes. Selecting the best call after outcomes is leakage. |
| **Buffer path dependence** | If an overlay changes future holdings, a one-month decision alters later opportunity sets. Maintain a frozen shadow baseline or model the path explicitly. |
| **Precedent coupling** | With rank persistence of 0.91, nearest precedents may be adjacent versions of the same country/regime. Compare with a direct numeric nearest-neighbour model. |
| **News timing** | “That month’s news” must mean text first available before the exact rebalance and executable price, including article-version timestamps. |
| **Model cutoff ambiguity** | API knowledge cutoffs are not guaranteed corpus cutoffs; later instruction tuning or silent model updates can contaminate the test. |
| **Objective mismatch** | Full-universe rank IC, top-eight return, buffered turnover, one-swap advantage, and Sharpe are different objectives. |
| **Research selection** | The incumbent and any prompt/tool policy were selected after experimentation. Incremental comparisons must use frozen code and a complete variant ledger. |
| **Tail concentration** | A few crisis actions may create the entire uplift. Report block influence, but do not remove crises post hoc. |
| **Sparse-action reporting** | Conditional return per swap can look excellent while total portfolio alpha is negligible. The primary series must include zero in no-action months. |
| **Action costs** | A temporary overlay may require entering and later reversing positions. Include every incremental execution, FX, tax, and access cost. |

Both proposals also underemphasize the **economic action ceiling**. Compute the ex-post legal one-swap oracle, random-swap distribution, and score-boundary opportunity set. The oracle is not attainable evidence, but it shows whether one swap has enough leverage after costs to justify the machinery.

## 5. Validation Plan

“Kill” should mean stopping development or deployment of a tested component. With this little data, failure to achieve significance is not automatically proof of zero effect. Genuine economic falsification occurs when the confidence interval’s upper bound is below the preregistered material hurdle.

### Phase 0 — Freeze and audit before modelling

1. Freeze the incumbent code, all 30 seeds, annual retraining, buffer state, return construction, execution convention, and transaction costs.
2. Recompute every candidate reward on that exact incumbent.
3. Materialize all 208 legal one-swap rewards per month.
4. Estimate month-level covariance, serial dependence, action coverage, and power.
5. Audit every auxiliary series for release vintages and revisions.
6. Validate historical news first-seen timestamps and article versions.
7. State which data, if any, remain genuinely untouched.

Immediate stops:

- If the 3.1% series cannot be exactly reproduced, stop all comparisons.
- If a target lacks defensible point-in-time vintages, remove that target.
- If news timing cannot be reconstructed, historical news results are diagnostic only.
- If all historical outcomes have already influenced design, do not label any historical result confirmatory.

### Phase 1 — Cheap mechanism falsification

| Claim | Cheap test | Explicit kill criterion |
|---|---|---|
| Current anonymised arm is identity-free | Exact-packet chronological re-identification audit | Already failed at 93.5%. For a redesign, top-1 above 5.9% kills the “anonymous” interpretation. |
| Hindsight rationalisation learns transferable lessons | Run the complete locked pipeline on true outcomes and at least 199 dependence-preserving null datasets | Kill rationalisation/SFT/GRPO unless the true confirmation score exceeds the 99th percentile of the maximum null, has the same positive sign in two fixed later blocks, and beats a no-rationale direct learner. |
| Auxiliary representation adds return information | Freeze the encoder and compare auxiliary, return-only, and shuffled-auxiliary models | Kill the return-alpha claim if auxiliaries do not improve locked paired return conditional on the incumbent. Retain useful forecasting tools separately. |
| Numeric toolkit has residual value | B−A with nested chronological fitting | If the 95% upper confidence bound is below 1.0%/year net, kill B as an investable overlay. |
| News supplies orthogonal information | C versus no-news, stale-news, and country-shuffled-news controls | Kill the news-alpha mechanism if current matched news does not beat the maximum control result on the locked statistic. |
| LLM allocation adds value | D−C with identical information, costs, and action budget | If the 95% upper bound is below 0.5%/year, kill LLM allocation. If wide, classify it as inconclusive rather than successful. |
| LLM is operationally safe | Audit evidence support, timestamps, parsing, and repeated-call stability | Do not deploy if evidence-supported assertion precision is below 95%, structured-output success is below 99%, or the fixed consensus rule is not met; default to abstention. |

The 1.0% and 0.5% hurdles are recommended starting values reflecting additional turnover and complexity. If the owner chooses different economic hurdles, they must be fixed before seeing candidate results.

A simple numeric model failing does not logically prove that D must fail. It means D must demonstrate its purported nonlinear/prior advantage directly; it cannot claim value merely by beating a weak comparator.

### Phase 2 — One locked retrospective evaluation

Choose exactly one candidate after development. A sensible primary contrast is C−A, with B−A and C−B as mechanism analyses. D−C should be a separate sequential hypothesis or receive a fixed multiplicity allocation.

Use:

- monthly net paired return as the primary endpoint;
- one month as the inference cluster;
- HAC or a preregistered moving-block bootstrap;
- all no-action months as zero;
- fixed transaction costs and execution assumptions;
- leave-one-block-out influence as a robustness report;
- no exclusion of adverse crises or “bad data” after seeing returns.

Decision rules:

- **Statistical success:** 95% interval excludes zero.
- **Economic success:** point estimate is at least the hurdle.
- **Strong confirmation:** lower confidence bound exceeds the hurdle.
- **Futility:** upper confidence bound is below the hurdle.
- **Otherwise:** inconclusive.

Under the stated \(0.80\%\) monthly swap volatility, the 260-month 95% half-width is roughly:

\[
1.96\times0.595\%=1.17\%\text{/year},
\]

before HAC or multiplicity penalties. A modest 1% effect will therefore often remain inconclusive even over the full history.

### Phase 3 — Prospective shadow test

For every rebalance:

- commit a hash of the input packet, model/API version, prompts, tool outputs, random seeds, aggregation rule, action, evidence, and timestamp before the return period;
- run the incumbent and candidate simultaneously;
- never replace a prior prediction after an API update;
- treat any prompt, tool, model-version, or action-rule change as a new policy;
- preregister any sequential stopping or futility boundary.

Forty-eight months can confirm only a very large effect—about 3.9%/year under the stated assumptions. The trial is still valuable for detecting leakage, operational instability, unsupported news use, and catastrophic underperformance, but it cannot turn a modest point estimate into strong evidence.

### What must be preregistered

At minimum:

- primary hypothesis, policy, contrast, economic hurdle, success rule, and futility rule;
- universe, currencies, benchmark, delistings, unavailable markets, costs, rebalance timestamp, and execution price;
- baseline code checksum, ensemble members, annual retraining, buffer logic, and overlay state/reset rule;
- legal actions, maximum swaps, replacement rule, abstention rule, reason taxonomy, and action-coverage reporting;
- training windows, recency weights, auxiliary transformations, target vintages, uncertainty calibration, and horizons;
- every model version, prompt, tool schema, temperature, seed, call count, retry rule, parser, and aggregation rule;
- news sources, first-seen timestamp rules, article updates, and evidence requirements;
- attribution method and reference point;
- precedent similarity metric, permissible dates, adjacency exclusions, and whether outcomes are displayed;
- anonymity representation, row ordering, re-identification attacks, and thresholds;
- all placebo pipelines and permutation schemes;
- primary estimator, HAC lag or bootstrap block, alpha allocation, multiplicity treatment, and sequential stopping;
- complete prompt/model/hypothesis-search budget and variant ledger;
- handling of missing tools, API failures, ties, unsupported outputs, and model updates.

## 6. Next Action

Before any SFT or GRPO work, complete three packages:

1. **Reward and power notebook:** reproduce the incumbent, construct every legal paired action reward, include exact incremental costs, and compute HAC-aware power and oracle ceilings.
2. **Leakage and null harness:** run country/date re-identification and the complete rationalisation pipeline on dependence-preserving placebo outcomes.
3. **Hybrid ladder:** implement A/B/C with a one-veto, mechanically replaced, reset-monthly overlay; then run one constrained D test using exactly C’s information.

Build the hybrid first because it preserves the proven strategy, provides identifiable component contrasts, and gives the LLM a genuinely new information channel. Shelve the original hindsight-rationalisation/GRPO architecture unless it clears the full-pipeline placebo and direct-learner gates.

RECOMMENDATION: REVISE
