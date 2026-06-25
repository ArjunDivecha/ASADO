# PRD — ASADO Discovery Triage for Mythos-Class Models

## 0. Executive Summary

ASADO's current price-discovery gap engine is useful, but it remains mostly a deterministic **Known Gap Monitor**: it watches predefined relationships that we already know to ask about. The original ambition of ASADO is larger:

> **What does the data know that price has not yet figured out, including relationships we did not already know to ask about?**

The decided direction is to build **ASADO Discovery Triage**: a Mythos-aware research system that makes **Discovery** the product and **Disbelief** the chain of custody.

This PRD supersedes the earlier `fugu.md` framing where the Prosecutor/Court risked becoming the center of the system. The corrected design is:

```text
Known Gap Monitor
    ↓
Mythos Discovery Lab
    ↓
Tool-Enforced Context Builder
    ↓
Research Look Ledger
    ↓
Model-Cutoff Provenance Classifier
    ↓
Claim Freezer
    ↓
Minimal Triage Battery
    ↓
Blind Human Ruling
    ↓
Prospective Incubator + Graveyard Control Arm
    ↓
Research Desk Cockpit
    ↓
Optional Blind/Forensic Prosecutors Later
```

The core principle:

> **Use Mythos as a quarantined research physicist, not as an oracle.**

A Mythos-class model may discover deep nonlinear relationships, analog taxonomies, mechanism graphs, and detector families far beyond deterministic imagination. But because such a model may already encode historical market outcomes in its weights, any idea it generates from pre-training-cutoff history cannot be historically certified from that same history. Mythos makes discovery more valuable and contamination harder to measure.

Therefore:

- **Mythos can discover.**
- **Mythos can theorize.**
- **Mythos can generate detector drafts.**
- **Mythos can propose falsification tests.**
- **Mythos cannot certify its own historically inspired discoveries.**

Certification comes only from:

1. Forward live data after the idea is frozen.
2. Post-training-cutoff holdout data.
3. A genuinely older frozen model tested on later data.
4. Deterministic pre-registered claims with a known denominator.

---

## 1. Core Decisions Already Settled

### 1.1 Current gap engine is not the final intelligence layer

The existing gap engine remains valuable, but it should be conceptually demoted from “ASADO intelligence” to:

> **Known Gap Monitor** — deterministic measured relationships.

It watches known relationships such as:

- terms of trade versus ETF price,
- graph-neighbor returns versus local price,
- FX options versus equity stress,
- sovereign stress versus equity,
- valuation versus price,
- flows versus price,
- macro surprises versus realized return.

It answers:

> “Which known relationships are currently stretched or unabsorbed?”

It does **not** answer:

> “What relationship have we never imagined?”

### 1.2 Discovery is the product; disbelief is chain of custody

The corrected center of gravity is:

```text
Discovery Lab = product engine
Court / Triage = epistemic chain of custody
```

The system should not become only a rejection machine. The original dream must remain visible and alive: ASADO should discover strange, nonlinear, non-obvious relationships. But those discoveries must be routed through provenance, triage, blind ruling, and forward evidence before they can influence belief.

### 1.3 Mythos-class model assumption

The LLM used for Discovery Lab work is assumed to be **Mythos-class**: far beyond current frontier models in abstraction, causal synthesis, long-horizon reasoning, tool use, and pattern discovery.

This assumption means the Discovery Lab can be more ambitious:

- latent regime maps,
- mechanism graphs,
- analog taxonomies,
- nonlinear detector families,
- cross-surface contradictions,
- price-versus-fundamentals belief gaps,
- falsification plans,
- new probe ideas,
- new country classifications,
- new data-quality suspicions.

But this assumption also makes contamination worse:

> **The stronger the model, the more likely its weights already encode historical outcomes and market narratives.**

Thus Mythos output is not “clean” merely because a prompt or tool hides forward returns.

### 1.4 Model training cutoff is the real PIT boundary

For LLM-generated hypotheses, inference-time tool context is not the only information boundary. The model's training cutoff is the true point-in-time boundary.

If a model was trained through 2026, then ideas it generates about 2000–2025 market history may be contaminated by outcome knowledge encoded in its weights, even if the current tool context withholds forward returns.

Rule:

> **For Mythos-generated ideas, historical certification is allowed only on data after the model’s training cutoff, or on genuinely forward data after the claim is frozen.**

No cutoff, no certification.

Default route when model cutoff is missing:

```text
prospective_only_unknown_cutoff
```

### 1.5 Prompt-level outcome blindness is insufficient

Outcome blindness must be enforced by tools, not prompts.

The LLM should literally not receive:

- forward returns,
- future returns,
- harness verdicts,
- PnL,
- factor portfolio returns,
- optimizer returns,
- factor top-20 membership,
- country factor attribution,
- realized outcomes,
- candidate outcome summaries,
- prior claim verdicts when generating new ideas.

Even then, this is only **tool-outcome-blind**, not epistemically clean. Clean certification requires post-training-cutoff or forward data.

### 1.6 The Research Look Ledger is mandatory

The statistical sin is not only “what did we test?” but:

> “What did we look at before deciding what to test?”

Every exploratory look that could condition a claim must be recorded.

### 1.7 Blind human ruling is mandatory

The human judge is a contamination surface. Arjun may already know the bull case and may be persuaded by it.

Therefore the system must force:

1. Claim is frozen.
2. Bull case / generator rationale is sealed.
3. Triage probes run.
4. Blind packet is built.
5. Human rules using only neutral claim, provenance, triage outputs, and harness stats.
6. Only afterward may the bull case be unsealed.
7. Any ruling change after unsealing is logged.

### 1.8 The graveyard must be tracked forward

Do not track only survivors. Track killed, rejected, and quarantined claims too.

The graveyard is the control arm. It tells ASADO whether skepticism is helping or starving the book.

### 1.9 JSONL/YAML first, DuckDB later

Do not start by adding fourteen tables. V1 should be file-first:

- JSONL for append-only events,
- YAML/JSON for frozen objects,
- markdown for daily docket artifacts.

Fold to DuckDB only after the workflow proves stable.

### 1.10 Prosecutor is deferred

A full LLM Prosecutor is not V1. The first essential system is:

- denominator,
- provenance,
- minimal probes,
- blind ruling,
- prospective queue,
- graveyard tracking.

Later, add:

- Blind Prosecutor: attacks the claim without seeing bull case.
- Forensic Prosecutor: attacks the genealogy after seeing the research-look ledger and discarded variants.

---

## 2. System Goals

### G1 — Recover the original ASADO dream

ASADO should help a Mythos-class model find relationships deterministic detectors would never invent.

### G2 — Prevent historical story laundering

The system must prevent retrospective Mythos ideas from being laundered into “validated alpha” via ordinary in-sample testing.

### G3 — Make every idea attackable

Every idea that graduates beyond a draft becomes a frozen claim with:

- mechanism,
- variables,
- direction,
- horizon,
- universe,
- data timing,
- provenance,
- falsification plan.

### G4 — Make contamination visible

Every research object carries:

- model id,
- model version,
- model training cutoff,
- tool context cutoff,
- visibility mode,
- surfaces seen,
- surfaces excluded,
- certification route.

### G5 — Let interesting dirty ideas live prospectively

Retrospective or underpowered ideas are not automatically killed. They are quarantined and tracked forward.

### G6 — Keep the cockpit magical but epistemically honest

The cockpit should prominently show unvalidated but interesting Discovery Lab outputs, with epistemic status labels that are impossible to miss.

### G7 — Learn from false negatives

Track the forward performance of killed and quarantined ideas to measure whether triage is too aggressive.

---

## 3. Non-Goals

V1 does **not**:

- recommend trades,
- size positions,
- approve live allocation,
- certify Mythos-generated pre-cutoff ideas historically,
- build a full prosecutor court,
- create a giant DuckDB schema extension,
- replace the current gap engine,
- replace the existing harness,
- remove human judgment.

---

## 4. High-Level Architecture

```text
1. Known Gap Monitor
   Deterministic measured relationships.

2. Mythos Discovery Lab
   Powerful theory/draft/analog/contradiction generator.

3. Tool-Enforced Context Builder
   Controls what Mythos sees at inference.

4. Research Look Ledger
   Records what Mythos saw and when.

5. Model-Cutoff Provenance Classifier
   Decides whether any historical certification is allowed.

6. Claim Freezer
   Converts drafts into attackable claims.

7. Minimal Triage Battery
   Cheap leakage/concentration probes.

8. Blind Human Ruling
   Human rules before bull case is unsealed.

9. Prospective Incubator + Graveyard Control Arm
   Tracks survivors, quarantined ideas, and killed ideas forward.

10. Research Desk Cockpit
   Makes Discovery visible and epistemic status unavoidable.

11. Optional Prosecutor / Forensic Prosecutor
   Later, when enough process history exists.
```

---

## 5. Actor Definitions

### 5.1 Known Gap Monitor

Current deterministic gap engine.

Outputs measured states, not validated alpha.

Example:

```yaml
object_type: known_gap_event
source: deterministic_detector
detector: D10_fx_options_vs_equity
entity: Brazil
relationship: fx_options_stress_unpriced_by_equity
status: measured_gap
as_of: 2026-06-25
```

### 5.2 Mythos Discovery Lab

A quarantined Mythos-class research workbench.

Allowed to generate:

- mechanism graphs,
- detector family drafts,
- analog taxonomies,
- contradiction cards,
- nonlinear condition drafts,
- falsification plans,
- data-quality suspicions,
- new deterministic probe ideas.

Forbidden to generate:

- validated alpha,
- trade recommendations,
- portfolio actions,
- “this is real” claims,
- unqualified rankings of opportunities.

### 5.3 Tool-Enforced Context Builder

Builds constrained contexts for Discovery Lab sessions.

It must enforce outcome blindness at the data-access layer. Prompt instructions are not enough.

### 5.4 Research Look Ledger

Append-only record of each exploratory look.

Records:

- actor,
- model id,
- model version,
- training cutoff,
- tool context cutoff,
- visibility mode,
- surfaces seen,
- surfaces forbidden,
- generated drafts,
- contamination class,
- certification route.

### 5.5 Model-Cutoff Provenance Classifier

Routes each object based on:

- generator type,
- visibility mode,
- model training cutoff,
- certification window start,
- whether outcome blindness was tool-enforced.

### 5.6 Claim Freezer

Turns a draft into an attackable claim.

A frozen claim may link to:

- source look,
- detector draft,
- analog set,
- existing hypothesis ledger ID,
- sealed rationale.

### 5.7 Minimal Triage Battery

Runs cheap first-pass probes before any LLM Prosecutor.

V1 required probes:

1. target / optimizer re-entry,
2. leave-one-crisis-out,
3. country / region jackknife.

Conditional probes:

- publication-lag sensitivity,
- horizon profile.

### 5.8 Blind Human Ruling

Human ruling before bull case is unsealed.

The blind ruling file logs whether the ruling changed after unsealing.

### 5.9 Prospective Incubator

Tracks claims that cannot be historically certified but are worth forward evidence.

### 5.10 Graveyard Control Arm

Tracks killed, rejected, and quarantined claims forward where mechanically measurable.

This lets ASADO estimate its false-negative rate.

### 5.11 Optional Prosecutors

Deferred.

Two later types:

- **Blind Prosecutor:** sees neutral claim, provenance, stats, probes; not bull case.
- **Forensic Prosecutor:** sees research genealogy, discarded variants, prompt trail, bull case; attacks the process.

---

## 6. Mythos Model Assumption

ASADO assumes the Discovery Lab may eventually be operated by a Mythos-class model with capabilities far beyond current models.

### 6.1 Expected capabilities

A Mythos-class model may be able to infer:

- latent causal structures,
- cross-surface nonlinear relationships,
- analog families,
- hidden regime partitions,
- multi-hop graph motifs,
- second-order market absorption patterns,
- new ways signals fail,
- new falsification tests,
- new data-quality concerns.

### 6.2 Required metadata on every Mythos object

Every Mythos-generated object must include:

```yaml
model:
  model_id: mythos-x
  model_version: mythos-x-2027-03
  training_cutoff: 2027-01-31
  tool_context_cutoff: 2027-03-15
  web_access: false
  market_data_access: restricted
  outcome_surfaces_visible: false
```

### 6.3 Implication

The Mythos assumption does **not** mean:

> “The model is so smart we can trust its discoveries more.”

It means:

> “The model is so smart that its discoveries may be much more valuable, and its contamination may be much harder to measure.”

---

## 7. Visibility Modes and Certification Routes

The original four modes are revised for Mythos.

### 7.1 Mode A — Tool-outcome-blind, pre-cutoff

The model does not see outcome surfaces through ASADO tools, but the candidate certification period is at or before the model training cutoff.

Status:

```text
exploratory_only
prospective_required
```

Reason: the model may already know outcomes through weights.

### 7.2 Mode B — Tool-outcome-blind, post-cutoff

The model does not see outcome surfaces through tools, and the candidate test window begins after the model training cutoff.

Status:

```text
post_cutoff_holdout_testable
```

This is the clean Mythos path.

### 7.3 Mode C — Full retrospective

The model sees outcomes, harness results, prior verdicts, or PnL.

Status:

```text
theory_generation_only
prospective_required
```

Useful for imagination, never certifying.

### 7.4 Mode D — Frozen older model

If an archived model checkpoint predates the holdout window, its ideas may be tested on later data.

Status:

```text
archived_model_holdout_testable
```

### 7.5 Mode E — Legacy / unknown

Existing signals and prior conversations with unclear provenance.

Status:

```text
legacy_grandfathered
requires_forward_tracking
```

### 7.6 Practical collapse into two epistemic buckets

For LLM-generated ideas:

```text
Certifying bucket:
  - forward data after claim freeze
  - post-training-cutoff holdout
  - older frozen model tested on later data

Exploratory bucket:
  - pre-cutoff tool-outcome-blind
  - full retrospective
  - unknown cutoff
  - legacy unknown
```

---

## 8. Tool-Enforced Context Builder

### 8.1 Required behavior

Outcome-blind contexts must reject forbidden surfaces in code.

Forbidden surfaces include:

- `harness_results`,
- `hypothesis_ledger.verdict`,
- `verdict_json`,
- `factor_returns`,
- `factor_returns_daily`,
- `factor_top20_membership`,
- `country_factor_attribution`,
- forward returns,
- future returns,
- realized forward outcomes,
- PnL,
- candidate outcomes,
- prior claim verdicts.

### 8.2 Context manifest

Each Discovery Lab session gets a manifest:

```yaml
context_manifest:
  visibility_mode: tool_outcome_blind
  as_of_date: 2027-03-15
  model_id: mythos-x
  model_version: mythos-x-2027-03
  model_training_cutoff: 2027-01-31
  allowed_surfaces:
    - price_state_daily
    - valuation_monthly
    - sovereign_signals
    - market_implied_signals
    - etf_flow_signals
  forbidden_surfaces_enforced:
    - forward_returns
    - harness_results
    - factor_returns_daily
    - country_factor_attribution
  tool_enforced_outcome_blind: true
```

### 8.3 Acceptance tests

- Context builder fails if a requested surface matches a forbidden outcome surface.
- Context builder records exactly what surfaces were included.
- Context builder records model training cutoff.
- Context builder distinguishes tool-outcome-blind from epistemically clean.

---

## 9. Mythos Discovery Lab

### 9.1 Purpose

The Discovery Lab is where Mythos searches for non-obvious relationships.

It emits drafts and theory objects, not validated alpha.

### 9.2 First five daily discovery searches

V1 Discovery Docket should run or support these five searches:

1. **Cross-surface contradiction**
   - Find countries where price, valuation, FX options, flows, sovereign stress, and graph state strongly disagree.

2. **Graph motif**
   - Find patterns where neighbors, leaders, or similarity twins moved but endpoint price did not.

3. **Analog mismatch**
   - Retrieve outcome-blind analogs under multiple fixed metrics and flag disagreement between macro-state analogs and price-state analogs.

4. **Regime sign flip**
   - Search for contexts where a normally bad variable may become constructive, or a normally good variable may become dangerous.

5. **Nonlinear condition draft**
   - Draft simple two-to-four condition detector families from PIT-safe state contradictions.

### 9.3 Daily Discovery Docket

The first V1 should produce one real artifact per day:

```text
journal/dockets/discovery_docket_YYYY_MM_DD.md
```

The docket should include:

1. Weirdest cross-surface contradiction.
2. Best outcome-blind analog mismatch.
3. Strongest new nonlinear detector draft.
4. Most interesting mechanism graph.
5. Most important falsification idea.
6. One idea killed immediately by triage.
7. One idea routed to prospective incubator.

Each card must carry:

```yaml
epistemic_status:
  - unvalidated
  - tool_outcome_blind
  - pre_cutoff_model_contamination_possible
  - prospective_required
```

or the relevant status for its provenance.

---

## 10. Discovery Object Types

### 10.1 Mechanism graph

```yaml
object_type: mechanism_graph
title: FX stress normalization under ETF-flow capitulation

nodes:
  - FX option stress
  - ETF forced selling
  - sovereign CDS confirmation
  - local equity price absorption
  - foreign investor flow reversal

edges:
  - FX stress improving precedes equity stabilization
  - ETF flows lag macro-hedge normalization
  - sovereign CDS widening invalidates rebound thesis

predicted_observable:
  - FX skew improves before ETF flows recover
  - equity rebound strongest where CDS is stable
  - signal should fail in hard sovereign-stress regimes

status: unvalidated
route: prospective_or_post_cutoff_only
```

### 10.2 Detector family draft

```yaml
object_type: detector_family_draft
family_name: hedge_market_leads_forced_seller_exhaustion

members:
  - fx_skew_relief_plus_etf_outflow
  - cds_stable_plus_etf_capitulation
  - vol_term_normalization_plus_price_drawdown

certification_route: prospective_or_post_cutoff_only
```

### 10.3 Analog taxonomy

```yaml
object_type: analog_taxonomy
taxonomy_name: price_absorption_after_macro_hedge_relief

episode_classes:
  - hedge_market_relief_before_equity
  - equity_rebound_without_flow_confirmation
  - false_relief_before_sovereign_stress
  - commodity_beta_rescue_after_fx_stress
```

### 10.4 Contradiction card

```yaml
object_type: contradiction_card
entity: Indonesia
as_of: 2027-03-15

contradiction:
  price_state: panic_drawdown
  fx_options_state: stress_easing
  flows_state: still_capitulative
  valuation_state: cheapening
  sovereign_state: not_confirming_stress

mythos_interpretation: >
  Price may still be reflecting forced equity selling while the macro hedge
  market has stopped worsening.

status: unvalidated
route: prospective_incubator
```

### 10.5 Falsification plan

Every Mythos draft must include a falsification block:

```yaml
falsification:
  near_term:
    - sovereign CDS widens while FX skew improves
    - ETF flows remain negative but price fails to stabilize after 21d
  structural:
    - works only in one country
    - works only during COVID/GFC
    - sign flips outside commodity exporters
  data_quality:
    - FX options surface sparse
    - ETF flow series split artifact
```

### 10.6 Mythos self-falsification block

Every Discovery Lab output must include:

```yaml
mythos_self_falsification:
  strongest_objection: ...
  easiest_way_this_is_leakage: ...
  first_probe_to_run: ...
  condition_under_which_i_would_abandon_this: ...
```

This is not adjudication. It is raw material for triage.

---

## 11. Research Look Ledger

### 11.1 Purpose

Records what the model or human saw before producing an idea.

### 11.2 JSONL path

```text
journal/looks/research_looks.jsonl
```

### 11.3 Record schema

```yaml
look_id: L_20270625_001
created_at: 2027-06-25T15:22:11-07:00
actor: mythos
purpose: find_cross_surface_contradictions
visibility_mode: tool_outcome_blind

model:
  model_id: mythos-x
  model_version: mythos-x-2027-03
  training_cutoff: 2027-01-31
  tool_context_cutoff: 2027-06-25

surfaces_seen:
  - price_state_daily
  - valuation_monthly
  - sovereign_signals
  - market_implied_signals
  - etf_flow_signals

surfaces_forbidden:
  - forward_returns
  - harness_results
  - factor_returns_daily
  - country_factor_attribution

outputs:
  - detector_draft:DRAFT_20270625_004
  - analog_question:AQ_20270625_002

contamination_class: tool_blind_pre_cutoff_or_post_cutoff_classified_separately
certification_route: assigned_by_provenance_classifier
```

### 11.4 Acceptance tests

- Every draft links to a look.
- Every claim links to a look or is explicitly marked deterministic/legacy.
- Missing model training cutoff routes LLM ideas to `prospective_only_unknown_cutoff`.

---

## 12. Legacy Provenance Audit

ASADO cannot pretend all existing ideas were born under perfect pre-registration.

### 12.1 Purpose

Classify existing signals and book logic without forcing an artificial clean history.

### 12.2 Legacy tiers

```text
Tier 0 — clean PIT registered
Tier 1 — deterministic / documented before recent tests
Tier 2 — legacy retrospective but economically plausible
Tier 3 — narrative / unknown provenance
Tier 4 — fatal leakage or target contamination
```

### 12.3 Legacy object

```yaml
legacy_provenance:
  object_id: H_20260610_014
  class: legacy_grandfathered
  tier: tier_2_legacy_retrospective_plausible
  contamination_status: unknown_or_likely_retrospective
  current_use_status: grandfathered
  allowed_language: live_observed_strategy
  forbidden_language: cleanly_validated_alpha
  required_next_step:
    - triage_probe_pack
    - prospective_tracking
```

### 12.4 Rule

Legacy does not mean invalid. It means confidence language must be honest and forward tracking is required.

---

## 13. Fixed-Metric Analog Shelf

### 13.1 Decision

Move analogs early. Historical analogs are central to ASADO’s original dream.

### 13.2 Registry of metrics

Use 3–5 fixed metrics, not one.

Initial registry:

1. `macro_state_v1`
2. `price_state_v1`
3. `stress_state_v1`
4. `graph_state_v1`
5. `mixed_state_v1`

### 13.3 Metric schema

```yaml
metric_id: mixed_state_v1
feature_blocks:
  - price_state
  - valuation_state
  - sovereign_stress
  - fx_options_state
  - flows_positioning
  - graph_neighbor_state
distance: weighted_rank_normalized_euclidean
lookback_window_days: 252
outcome_blind: true
```

### 13.4 Workflow

```text
1. Analog metric is registered.
2. Analog set is retrieved outcome-blind.
3. Analog set is frozen.
4. Forward outcomes are attached only after freezing.
5. Mythos differencing is allowed only against fixed difference axes.
6. Differencing cannot change analog membership.
7. Differencing cannot promote a trade.
8. Differencing can create analog_note, detector_draft, claim_candidate, or caveat.
```

### 13.5 Difference axes

Allowed axes:

- valuation state,
- FX stress state,
- sovereign stress state,
- commodity exposure,
- foreign-flow state,
- ETF expression quality,
- drawdown state,
- graph-neighbor state,
- policy-rate state,
- inflation-surprise state.

### 13.6 Forbidden analog behavior

Mythos may not say:

> “These bad analogs do not count; the profitable analogs are the real comps.”

It may only explain differences within a frozen analog set.

---

## 14. Claim Freezer

### 14.1 Purpose

Convert drafts into attackable claims.

### 14.2 Path

```text
journal/claims/C_YYYYMMDD_NNN.yaml
```

### 14.3 Schema

```yaml
claim_id: C_20270625_004

links:
  hypothesis_id: H_20270625_018
  detector_draft_id: DRAFT_20270625_004
  source_look_id: L_20270625_001
  sealed_rationale_id: SR_20270625_004

provenance:
  source: mythos_discovery_lab
  visibility_mode: tool_outcome_blind
  model_training_cutoff: 2027-01-31
  certification_window_start: 2027-02-01
  contamination_class: post_cutoff_tool_blind
  certification_route: post_cutoff_holdout_testable

neutral_claim:
  sentence: >
    FX stress relief while ETF flows remain negative may predict 21-day
    relative outperformance in countries where sovereign CDS is not widening.

mechanism:
  text: >
    Macro hedge markets may stop worsening before forced equity selling is
    exhausted, creating delayed price absorption in local equities.
  channels:
    - FX options
    - ETF flow capitulation
    - sovereign stress confirmation

variables:
  - FX_RR25_1M_Z252
  - FX_ATM_VOL_1M_Z252
  - ETF_FLOW_21D_Z
  - SOV_CDS_5Y_Z

target:
  return_surface: country_returns_daily
  horizon_days: 21
  direction: long_high_signal
  target_type: relative_cross_sectional_return

universe:
  name: countries_with_fx_options_and_etf_flow_coverage
  min_countries: 10

falsification:
  fatal_if:
    - target_reentry
    - non_pit_feature
    - forward_return_dependency
  must_check:
    - leave_one_crisis_out
    - country_jackknife
    - horizon_profile
```

---

### 14.4 Integration with the existing harness (extend, do not duplicate)

The Court is an adversarial layer on top of ASADO's existing research machinery, not a parallel system. The repo already has `hypothesis_ledger`, `harness_results`, family keys, deflated-Sharpe trial counting, and mandatory pre-registration mechanism text in `sweep_signals.py`. The Claim Freezer must therefore:

- link each claim to an existing `hypothesis_id` rather than re-implementing trial accounting,
- reuse the existing family-key denominator so the deflated-Sharpe trial count stays honest,
- store Court-specific fields (provenance class, model cutoff, certification route, triage results, blind ruling) as a claim **overlay** keyed to the hypothesis id,
- never write Court state into `Data/asado.duckdb` (wiped on every rebuild); durable records live under `journal/` and, later, `Data/loop/asado_loop.duckdb`.

The harness verdict (`WATCH`/`WEAK`/`DEAD`/`INSUFFICIENT`) remains the statistical gate for PIT-preregistered claims. The Court adds the provenance gate, the triage probes, the blind ruling, and forward tracking on top of it.

---

## 15. Minimal Triage Battery

### 15.1 Philosophy

Cheap probes first. Do not invoke an LLM Prosecutor before obvious failures are caught.

### 15.2 Required V1 probes

#### Probe 1 — Optimizer / target re-entry

Fatal.

Reject claims whose signal variables or tables use:

- future returns,
- optimizer outputs,
- factor returns,
- top-20 membership,
- country factor attribution,
- future labels,
- target-derived transforms.

#### Probe 2 — Leave-one-crisis-out

Drop major crisis windows:

- GFC,
- COVID,
- 2022 inflation/rates shock,
- China 2015,
- Eurozone stress if relevant.

Flag crisis concentration. Do not automatically kill unless extreme or paired with other failures.

#### Probe 3 — Country / region jackknife

Flag if one country, region, or sleeve owns the signal.

### 15.3 Conditional probes

#### Publication-lag sensitivity

Run for revised or slow-published macro sources:

- WDI,
- WEO,
- IMF,
- BOP,
- governance,
- OECD,
- CLI,
- EPU/GPR.

#### Horizon profile

Run when mechanism implies a specific horizon.

### 15.4 Output schema

```yaml
triage_result:
  claim_id: C_20270625_004
  status: triage_passed_not_validated
  fatal_failures: []
  warnings:
    - crisis_concentration_medium
  probes:
    - probe_id: target_reentry
      status: pass
    - probe_id: leave_one_crisis_out
      status: warning
      detail: evidence weakens materially excluding COVID
    - probe_id: country_region_jackknife
      status: pass
```

---

### 15.5 Power-budget gate (band, not verdict)

The power-budget gate is a **warning instrument, not a judge**. In a 34-country panel with overlapping returns, few macro cycles, and true ICs near 0.02-0.05, conditional and nonlinear claims are the least-powered objects to certify. The gate must therefore expose its assumptions and emit a band, never a hard `certification_power: insufficient` verdict that relocates false authority from the backtest to the gate.

```yaml
power_budget:
  effective_n_band: [180, 650]
  assumptions:
    country_correlation: [0.25, 0.55]
    horizon_overlap_adjustment: true
    crisis_cluster_adjustment: true
  parameter_complexity: medium_high
  detectable_ic_band: [0.04, 0.09]
  conclusion: probably_underpowered_for_certification
  confidence: medium
  allowed_use: prospective_or_descriptive
```

Rule: an underpowered claim is not killed; it is routed to the prospective incubator with its power band attached. The band is one input to the blind ruling, never an automatic gate.

---

## 16. Blind Human Ruling

### 16.1 Protocol

```text
1. Claim is frozen.
2. Generator rationale is sealed.
3. Triage probes run.
4. Blind packet is built.
5. Human reads only allowed blind inputs.
6. Human records preliminary ruling.
7. Generator rationale may then be unsealed.
8. Any ruling change after unsealing is logged.
```

### 16.2 Blind packet allowed inputs

- neutral claim,
- provenance,
- model cutoff,
- certification route,
- triage probe output,
- harness stats if already applicable,
- power-budget band if available.

### 16.3 Blind packet forbidden inputs

- generator rationale,
- bull case,
- excitement score,
- trade recommendation,
- discovery transcript,
- “why this is huge,”
- persuasive prior memo.

### 16.4 Ruling schema

```yaml
ruling_id: R_20270625_004
claim_id: C_20270625_004
judge: Arjun

blind_ruling:
  decision: prospective_only
  timestamp: 2027-06-25T16:03:00-07:00
  rationale: >
    Interesting but generated by Mythos from pre-cutoff history; certification
    must be forward-only.

unseal:
  sealed_rationale_unsealed_at: 2027-06-25T16:15:00-07:00
  post_unseal_decision: prospective_only
  ruling_changed_after_unseal: false
```

---

## 17. Prospective Incubator

### 17.1 Purpose

Interesting but uncertifiable ideas accumulate forward evidence.

### 17.2 Schema

```yaml
incubator_entry:
  claim_id: C_20270625_004
  status: prospective_only
  start_date: 2027-06-25
  first_readout_date: 2027-09-25
  full_readout_date: 2028-06-25
  observations_required: 252
  observations_so_far: 0
  in_sample_certification: forbidden
  reason: mythos_pre_cutoff_or_retrospective_discovery
```

### 17.3 Rule

Prospective-only is not death. It is the clean certification path for most Mythos-generated nonlinear discoveries.

---

## 18. Graveyard Control Arm

### 18.1 Purpose

Track killed and quarantined ideas forward to measure false negatives.

### 18.2 Why this matters

A hyperactive skeptic can starve a low-IC strategy. ASADO must measure whether triage is helping or killing real signal.

### 18.3 Schema

```yaml
graveyard_entry:
  claim_id: C_20270625_007
  terminal_or_quarantine_status: killed_fatal_leakage
  forward_tracking_enabled: true
  start_date: 2027-06-25
  reason_for_tracking: false_negative_control_arm
  expected_readouts:
    - 21d
    - 63d
    - 252d
```

### 18.4 Later analytics

Only after enough observations:

- Did killed ideas outperform survivors?
- Which kill reasons were predictive?
- Which probes were too aggressive?
- Which source families generated false excitement?

Do not pretend this calibration exists before data accumulates.

---

## 19. Research Desk Cockpit

The cockpit should be a **research desk plus courtroom**, not only a courtroom.

### 19.1 Panels

#### Known Gaps

Deterministic known relationships.

#### Discovery Lab

Prominently show unvalidated Mythos outputs:

- detector drafts,
- graph motifs,
- cross-surface contradictions,
- regime sign flips,
- analog questions,
- mechanism graphs.

Every card must scream its epistemic status:

```text
UNVALIDATED
TOOL-OUTCOME-BLIND
PRE-CUTOFF MODEL CONTAMINATION POSSIBLE
POST-CUTOFF HOLDOUT TESTABLE
PROSPECTIVE REQUIRED
RETROSPECTIVE-SNOOPED
LEGACY UNKNOWN
```

#### Analog Shelf

Show:

- metric used,
- retrieval date,
- outcome-blind status,
- frozen analog set,
- attached outcomes,
- Mythos differencing notes,
- generated drafts.

#### Under Triage

Claims being checked by cheap probes.

#### Blind Rulings

Show preliminary ruling before bull-case unsealing.

#### Prospective Incubator

Ideas waiting for forward evidence.

#### Graveyard / Quarantine Library

Show killed and quarantined ideas under forward tracking.

### 19.2 Design principle

Do not hide magic. Label it correctly.

---

## 20. File and Directory Structure

### 20.1 V1 files

```text
FuguPRD.md
PRD_ASADO_Discovery_Triage.md

config/
  discovery_triage.yaml
  claim_provenance_policy.yaml
  analog_metric_registry.yaml
  triage_probe_registry.yaml

journal/
  looks/
  drafts/
  claims/
  sealed_rationales/
  blind_rulings/
  prospective_queue/
  dockets/
  analog_sets/
  graveyard/

scripts/discovery_triage/
  __init__.py
  paths.py
  jsonl_store.py
  context_builder.py
  provenance.py
  lab_session.py
  make_detector_draft.py
  record_look.py
  freeze_claim.py
  retrieve_analogs.py
  attach_analog_outcomes.py
  classify_provenance.py
  run_triage_probes.py
  build_blind_packet.py
  record_blind_ruling.py
  route_claim.py
  daily_docket.py
  forward_track.py

tests/discovery_triage/
  test_context_builder.py
  test_provenance_classifier.py
  test_record_look.py
  test_freeze_claim.py
  test_blind_packet.py
  test_route_claim.py
  test_graveyard_tracking.py
  test_analog_outcome_blindness.py
```

### 20.2 JSONL-first storage

Append-only JSONL paths:

```text
journal/looks/research_looks.jsonl
journal/drafts/detector_drafts.jsonl
journal/claims/claims.jsonl
journal/blind_rulings/blind_rulings.jsonl
journal/prospective_queue/prospective_queue.jsonl
journal/graveyard/graveyard_forward_tracking.jsonl
```

### 20.3 DuckDB later

Fold later into loop DB surfaces only after V1 stabilizes:

- `research_looks`,
- `detector_drafts`,
- `claim_overlays`,
- `triage_probe_results`,
- `blind_rulings`,
- `prospective_incubator`,
- `graveyard_forward_tracking`,
- `analog_sets`,
- `analog_members`,
- `analog_outcomes`.

---

## 21. Revised Implementation Phases

### Phase 1 — Minimal denominator

Build:

- research-look ledger,
- detector draft schema,
- claim schema,
- provenance classifier,
- model-cutoff routing,
- legacy provenance flags.

Acceptance:

- Every draft links to a look.
- Every LLM-generated claim has model cutoff metadata or routes to prospective-only.
- Pre-cutoff Mythos ideas cannot be historically certified.

### Phase 2 — Discipline before Lab

Build:

- tool-enforced context builder,
- forbidden-surface checks,
- minimal triage probes,
- blind packet builder,
- blind ruling recorder,
- prospective/graveyard router.

Acceptance:

- Outcome-blind mode fails if forward returns or harness verdicts are requested.
- Blind packet excludes bull case and generator rationale.
- Killed and quarantined claims route to forward tracking when measurable.

### Phase 3 — Quarantined Mythos Discovery Lab

Build:

- daily discovery searches,
- detector draft writer,
- mechanism graph object,
- contradiction card object,
- self-falsification block,
- daily Discovery Docket.

Acceptance:

- Daily docket produces 3–10 unvalidated drafts/cards.
- Every card has epistemic status and route.
- No Discovery Lab output claims validation.

### Phase 4 — Fixed-Metric Analog Shelf

Build:

- metric registry,
- outcome-blind retrieval,
- frozen analog set files,
- outcome attachment after freeze,
- constrained differencing notes.

Acceptance:

- Mythos cannot change analog membership after outcomes attach.
- Differencing cannot promote a trade.

### Phase 5 — Cockpit integration

Add panels for:

- Known Gaps,
- Discovery Lab,
- Analog Shelf,
- Under Triage,
- Blind Rulings,
- Prospective Incubator,
- Graveyard.

### Phase 6 — Optional Blind Prosecutor

Only after V1 workflow is useful.

### Phase 7 — Optional Forensic Prosecutor

Only after enough research-look history exists.

### Phase 8 — Calibration / kill analytics

Only after enough forward outcomes exist.

---

## 22. Acceptance Criteria for V1

V1 is complete when:

1. `FuguPRD.md` and `PRD_ASADO_Discovery_Triage.md` exist.
2. Config files exist for discovery triage, provenance, analog metrics, and probes.
3. Journal directories exist.
4. Context builder rejects forbidden outcome surfaces.
5. Provenance classifier routes Mythos pre-cutoff ideas to prospective-only.
6. Provenance classifier allows only post-cutoff tool-blind Mythos ideas into holdout-testable path.
7. Drafts require source looks.
8. Claims require provenance and falsification fields.
9. Blind packets exclude generator rationale and bull case.
10. Blind rulings log post-unseal changes.
11. Killed and quarantined claims can be forward tracked as graveyard control-arm entries.
12. Daily docket can render 3–10 unvalidated ideas with epistemic labels.
13. Tests pass for context builder, provenance classifier, freeze-claim, blind packet, routing, graveyard tracking, and analog outcome blindness.

---

## 23. Risks and Mitigations

### Risk: Mythos generates seductive but contaminated theories

Mitigation:

- model cutoff required,
- certification route restricted,
- prospective-only default for pre-cutoff ideas,
- blind ruling,
- graveyard tracking.

### Risk: Tool-outcome-blind is mistaken for clean

Mitigation:

- label as `tool_outcome_blind`, not `clean`,
- require post-training-cutoff for holdout-testable status.

### Risk: Discovery Lab becomes firehose before drain

Mitigation:

- discipline before daily Lab operation,
- docket capped at 3–10 drafts,
- all drafts routed,
- no validation language.

### Risk: Skepticism starves the book

Mitigation:

- prospective incubator,
- graveyard forward tracking,
- later false-negative analytics.

### Risk: Analog shelf smuggles narrative selection

Mitigation:

- fixed metrics,
- frozen analog sets,
- outcomes attached after freeze,
- constrained differencing,
- no trade promotion from differencing.

### Risk: Human judge is seduced by bull case

Mitigation:

- blind ruling before unseal,
- log ruling changes after unseal.

---

## 24. Language Discipline

Allowed terms:

- unvalidated draft,
- tool-outcome-blind,
- post-cutoff holdout-testable,
- prospective-only,
- measured gap,
- claim candidate,
- frozen claim,
- triage-passed not validated,
- incubating,
- killed for fatal leakage,
- legacy-grandfathered.

Forbidden terms unless truly earned:

- validated alpha,
- proven signal,
- promoted by Mythos,
- trade recommendation,
- high-confidence opportunity,
- clean historical certification for pre-cutoff Mythos idea.

---

## 25. Final Bottom Line

The final decided direction is:

> **Build ASADO Discovery Triage, Mythos-aware.**

Use Mythos as a quarantined research physicist:

- let it discover strange nonlinear relationships,
- let it build mechanism graphs,
- let it define analog taxonomies,
- let it propose detector families,
- let it generate falsification plans.

But never treat Mythos as an oracle:

- prompt-level blindness is insufficient,
- model training cutoff is the real PIT boundary,
- pre-cutoff Mythos ideas are exploratory,
- clean certification comes only from post-cutoff or forward evidence,
- blind human ruling is required,
- killed ideas are tracked forward as a control arm.

The corrected slogan:

> **Muse in quarantine. Measurement in code. Judgment under blindfold. Evidence accumulated forward.**
