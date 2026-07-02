# Triptych As A Prediction Tool For ASADO

Date: 2026-06-12

## Bottom Line

Triptych is useful for ASADO if it is treated as a factor-diagnostic workbench and prior generator, not as a database and not as final evidence.

The right role is:

1. ASADO finds a candidate country/factor/date from dislocations, graph features, the query assistant, or a human idea.
2. Triptych shows whether that factor has historically mattered for that market, which horizon mattered, whether the current reading is extreme, and whether peer markets agree.
3. ASADO records the Triptych diagnostics as a review/prior, then sends anything promising through the stricter ASADO harness before promotion.

In short: Triptych improves predictions by making the "is this factor likely to work here, now, and over which horizon?" step visible and repeatable.

The India / REER exhibit is exactly the kind of signal ASADO should harvest from the tool: when India's REER is very cheap versus its own history, Indian equities have historically done very well over the next 12 months relative to the all-country average. Triptych makes that conditional-return relationship visible, then ASADO should turn it into a testable prior.

## How It Improves Predictions

### 1. Horizon Selection

ASADO often has a candidate factor but not an obvious forecast horizon. Triptych's bucket x horizon matrix can identify whether the relationship historically works at 1M, 3M, 6M, 12M, 24M, or 36M.

Prediction use:

- Prefer horizons where the current bucket has positive forward return, positive spread, and supportive IC.
- Penalize ideas where only one horizon works and neighboring horizons disagree.
- Route the chosen horizon into ASADO hypothesis registration and harness evaluation.

Example from India / REER:

- 12M is the cleanest horizon in the Triptych views checked.
- 24M remains directionally supportive.
- 36M weakens/reverses in the latest 10Y PIT view, so the prediction should not be stretched into a generic long-horizon bullish call.

### 2. Factor Reliability Priors

Triptych's current-bucket stats can become a prior over expected return and confidence:

- current bucket
- bucket average forward return
- bucket hit rate
- bucket observation count
- top-minus-bottom spread
- Spearman IC and overlap-adjusted t-stat
- horizon consistency

Prediction use:

- Boost a candidate only when expected return, hit rate, spread, and IC point in the same direction.
- Shrink or reject candidates with tiny bucket sample sizes, contradictory IC, or weak horizon consistency.
- Use Triptych output as a prior, not as a verdict.

For India / REER, the Triptych prior would be approximately:

- direction: lower REER is better for forward India equity relative return
- horizon: 12M primary, 24M secondary
- current state: low/cheap REER bucket
- all-history PIT evidence: D1 about +25.5% 12M relative forward return, 100% hit rate, 20 observations, IC about -0.41, D10-D1 about -27.3%
- latest 10Y PIT evidence: D1 about +23.6% 12M relative forward return, 100% hit rate, but only 2 observations
- confidence adjustment: positive prior, shrink because the latest-window current bucket has very few observations

### 3. False-Positive Suppression

The visual workflow is especially useful when a factor looks extreme but historically did not predict returns for that specific market.

Prediction use:

- If the current factor value is extreme but the current bucket historically has poor or noisy forward returns, lower ASADO's confidence.
- If a factor has a strong cross-sectional story but weak country-specific history, keep it as context rather than a trade signal.
- If full-sample and point-in-time views disagree, trust the point-in-time result for prediction.

### 4. Cross-Market Context

Triptych's cross-market snapshot shows whether a country's current factor reading is idiosyncratic or part of a global cluster.

Prediction use:

- Idiosyncratic extremes can support country-specific theses.
- Broad global extremes can redirect the thesis toward factor/cycle exposure rather than one country.
- Peer-market comparisons help avoid interpreting a world-level shock as a local signal.

### 5. Better Human And Agent Triage

Triptych turns ASADO candidates into shareable inspection URLs. That makes the prediction workflow less abstract:

- Dislocation row -> Triptych link.
- Query-assistant answer -> Triptych link for the most relevant country/factor pair.
- Hypothesis ledger entry -> Triptych evidence URL.
- Morning brief -> a short queue of "inspect these in Triptych" links.

## Proposed ASADO Workflow

### Stage 0: Manual Tool-In-The-Loop

Use ASADO to produce 5-20 candidate country/factor pairs each morning:

- active dislocations
- largest country-factor attribution rows
- factor return leaders/laggards
- query-assistant ideas
- user-specified factors

For each candidate, generate a Triptych URL with:

- point-in-time thresholds by default
- expanding z-score vs own history by default
- relative cumulative return by default
- 10Y or all-history window, depending on sample depth

The analyst or agent records a short Triptych review:

- direction implied by current bucket
- best-supported horizon
- expected forward return from the current bucket
- IC and t-stat
- sample size
- contradictory evidence
- whether to register a harness hypothesis

### Stage 1: Batch Triptych Diagnostics

Port the Triptych analytics kernel into an ASADO batch diagnostic step. This should not create a new database. It should write review artifacts under `Data/loop/` or a dated report under `docs/`.

For each candidate as-of date, compute only from history available at that date:

- current bucket
- current normalized signal
- bucket forward-return mean by horizon
- hit rate
- top-bottom spread
- IC and t-stat
- sample-size penalty
- horizon-consistency score

This creates a reproducible Triptych prior that can be joined to ASADO forecast experiments.

### Stage 2: Test Whether It Helps

Run an ablation:

- baseline ASADO candidate score
- baseline plus Triptych prior
- baseline plus Triptych prior plus cross-market snapshot features

Evaluate with ASADO's existing standards:

- cross-sectional rank IC
- top-7 vs equal-weight country returns
- top-minus-bottom long-short return with costs
- Newey-West t-stats
- subperiod stability
- deflated Sharpe / trial-count penalty

Promote only if Triptych features improve out-of-sample predictive quality after costs and trial penalties.

### Stage 3: Productize As A Tool

If Stage 2 passes, add Triptych as a first-class ASADO tool surface:

- dashboard/MCP link generator for country/factor pairs
- morning-brief Triptych review queue
- hypothesis-ledger field for Triptych evidence URL and diagnostics
- optional "Open In Triptych" action from Factor Explorer and dislocation rows

## Guardrails

- Use point-in-time thresholds for predictive claims.
- Never use forward-return variables (`1MRet`, `3MRet`, `6MRet`, `9MRet`, `12MRet`, daily return analogs) as signals.
- Do not treat a chart as proof. Triptych can nominate, explain, and de-risk candidates; ASADO's harness still decides.
- Do not load optimizer output surfaces back into feature surfaces.
- Do not create persistent tables directly in `Data/asado.duckdb`.
- Keep current full-sample views labeled descriptive only.

## Live Tool Check

The live Triptych app rendered representative ASADO-style India / REER views successfully:

- URL: `https://triptych-one.vercel.app/triptych.html?tab=triptych&tf=REER&tc=India&tn=history_z&tm=relative&th=12&tr=10y&td=pit&tb=10`
- View: India / REER / expanding z-score / relative return / 12M horizon / 10Y / point-in-time deciles.
- Result observed in the UI: current decile D1, latest signal around -3.30 sigma, bucket average 12M forward return around +23.6%, hit rate 100%, but only 2 observations and IC around -0.36.
- All-history PIT companion view: current decile D1, bucket average 12M forward return around +25.5%, hit rate 100%, 20 observations, IC around -0.41, and D10-D1 spread around -27.3%.

That example shows the value of the tool: it surfaces a meaningful predictive clue and its weakness at the same time. ASADO should use the clue as a positive India-relative 12M prior when REER is very cheap, but it should still send the hypothesis through the ASADO harness before treating it as investable evidence.

## Recommendation

Proceed with Triptych as a tool-in-the-loop experiment. The highest-value integration is not importing its data. It is using Triptych's visual and statistical diagnostics to improve candidate selection, horizon choice, confidence calibration, and hypothesis quality before ASADO spends a formal harness trial.
