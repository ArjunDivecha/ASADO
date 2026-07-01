# ASADO Court of Disbelief

## Working notes and assumptions

This note is the full response to the fundamental ASADO design question: if the current price-discovery gap engine is still mostly deterministic and based on known relationships, how should ASADO recover the original ambition of letting a very smart LLM discover highly nonlinear opportunities without turning the research process into an unbounded, history-snooped narrative machine?

My answer is deliberately opinionated:

- The current deterministic gap engine is valuable, but it should be treated as a **Known Gap Monitor**, not as ASADO's final intelligence layer.
- The next world-class agent should not primarily be an LLM muse that searches for alpha.
- The next world-class agent should be a **firewalled Prosecutor**: an adversarial agent that tries to kill claims, detect leakage, expose overfitting, and force every interesting idea into a governed evidentiary process.
- LLM imagination should still exist, but it should be quarantined into prospective detector drafts unless the hypothesis was cleanly pre-registered before outcome-conditioned exploration.

The core uncertainty is implementation scope. ASADO already has pieces of this substrate — hypothesis ledgers, harness results, family keys, governance scorecard, dislocation/gap tables — so this should enhance the existing loop rather than create a parallel research system. The biggest design risk is overbuilding an ornate court before the minimum viable adversarial gate exists. The correct first implementation slice is therefore: frozen claim schema, research-look/provenance ledger, deterministic probe battery, firewalled prosecutor packet, and one read-only prosecutor run.

---

# Executive answer

Yes: the current gap engine is still mostly deterministic. It watches known relationships: terms of trade versus ETF price, graph-neighbor returns versus local price, macro surprise versus country return, FX options versus equity stress, valuation versus price, flows versus price, and so on.

That is useful, but it is not the full ASADO dream.

The original dream was more ambitious:

> Build an environment where a truly smart model can notice relationships we did not predefine, compare them with past situations, propose nonlinear hypotheses, and let a hard statistical and operational substrate decide what deserves attention.

But the immediate answer is not to add an unconstrained LLM discovery engine. That would amplify the most dangerous failure mode in this project: convincing retrospective stories produced after an unbounded search over history.

The better answer is:

> **Build ASADO into a self-prosecuting research institution.**  
> Let imagination exist, but never let imagination validate itself.  
> The core new agent is not the Muse. It is the Prosecutor.

The world-class version of ASADO is not a machine that says:

> "I found a clever nonlinear alpha."

The world-class version says:

> "I found 47 plausible relationships. I killed 39. I quarantined 6 as statistically uncertifiable because they were history-snooped. I advanced 2 into prospective watch. I can tell you exactly why the others died, which data sources are manufacturing false excitement, which leakage classes recur, and what probes I permanently added so the same error cannot fool us again."

That is rarer. That is more defensible. That is the architecture I would build.

---

# The central design principle

The original ASADO dream was:

> "Give a brilliant LLM a rich data environment so it can find relationships a deterministic model could never imagine."

That dream is still valid, but only if it is split into three separate epistemic roles:

1. **Imagination** — allowed to propose possibilities.
2. **Measurement** — deterministic, repeatable, auditable.
3. **Disbelief** — adversarial, firewalled, hostile, and structurally separate.

The mistake would be to let the same system do all three.

A smart LLM looking through ASADO's historical panel can absolutely find nonlinear stories. But the moment it does that, the historical backtest is contaminated. It has already performed a gigantic, uncounted search over variables, lags, episodes, regimes, analogs, and narratives.

So the correct rule is:

> **LLM-generated retrospective hypotheses may be interesting, but they are not certifiable from the same historical data that inspired them.**

They can become prospective detectors. They can be tracked. They can be argued about. They can be compared to fixed-metric analogs. But they cannot be laundered through the harness as if they were one clean trial.

That means ASADO's scarce resource is not imagination.

ASADO's scarce resource is **trustworthy disbelief**.

So the new system should be called something like:

# ASADO Court of Disbelief

A firewalled adversarial research court for country-return hypotheses.

Not an alpha engine.

Not a chat bot.

Not a dashboard.

A court.

---

# The five actors in the final system

## 1. Known Gap Monitor

This is the current deterministic gap engine.

It watches predefined relationships:

- terms of trade versus ETF price,
- graph-neighbor returns versus local price,
- FX options versus equity stress,
- macro surprises versus return absorption,
- valuation versus realized price,
- sovereign stress versus equity,
- flows versus price.

This layer is still valuable. It gives ASADO clean measurement.

But conceptually it should be demoted from "the intelligence" to:

> **The Measuring Instruments.**

It answers:

> "Which known relationships are currently stretched or unabsorbed?"

It does **not** answer:

> "What relationship have we never imagined?"

So keep it, but stop treating it as the final expression of ASADO's intelligence.

---

## 2. Claim Registry

Every possible alpha idea becomes a frozen legal object.

No vague "Brazil looks weird."

No "maybe foreign flows matter after FX stress."

No "Opus noticed an interesting pattern."

A claim must be frozen as:

- mechanism,
- variables,
- direction,
- universe,
- lag,
- horizon,
- return surface,
- data availability assumption,
- falsification test,
- expected failure modes,
- provenance,
- trial denominator status.

The point is to make the idea attackable.

A claim that cannot be attacked is not a claim. It is a story.

---

## 3. Probe Battery

Before any LLM prosecutor speaks, deterministic probes attack the claim.

These are mechanical hostile tests:

- leave-one-crisis-out,
- country jackknife,
- region jackknife,
- publication-lag sensitivity,
- backfill sensitivity,
- optimizer-reentry checks,
- horizon stability,
- placebo tests,
- cost and ETF-expression realism,
- crowding and liquidity checks,
- target contamination checks.

This creates evidence for prosecution.

---

## 4. Prosecutor

This is the core new LLM agent.

Its job is not to find alpha.

Its job is to kill alpha.

It receives:

- the frozen claim,
- harness statistics,
- probe results,
- variable provenance,
- data samples,
- implementation details.

It does **not** receive:

- the original bull case,
- the generator's reasoning,
- the exciting narrative,
- the user's enthusiasm,
- the "why this could be huge" memo,
- the previous persuasive chat.

The Prosecutor's job is to write the strongest possible case that the claim is:

- leaked,
- overfit,
- crisis-owned,
- mechanically circular,
- postdictive,
- underpowered,
- economically incoherent,
- untradable,
- not point-in-time,
- dependent on one country,
- dependent on one regime,
- just a transformed return,
- not robust after costs,
- not really measuring the claimed mechanism.

The Prosecutor adjudicates nothing.

It does not approve.

It does not promote.

It does not recommend trades.

It only prosecutes.

---

## 5. Human Judge / Prospective Queue

You remain the judge.

A surviving claim does not become "true."

It becomes one of:

- killed,
- needs more evidence,
- prospective-only,
- watch,
- human override,
- retired.

Most surviving ideas should enter a **prospective OOS queue**, not a portfolio.

That is where the original dream becomes clean:

> "This relationship is interesting. We cannot honestly certify it from history because history helped generate it. So we begin tracking it now."

That is slow. But it is honest.

---

# The most important architectural rule: provenance decides the gate

Every claim must carry a provenance class.

This is the rule that prevents ASADO from fooling itself.

## Provenance class 1: PIT pre-registered

Example:

A YAML sweep spec was written before the run, every candidate counted as a trial, variables and family key were fixed, and the harness denominator is known.

This can receive normal in-sample harness treatment.

Allowed status:

- `WATCH`
- `WEAK`
- `DEAD`
- `INSUFFICIENT`
- then Prosecutor gate.

---

## Provenance class 2: deterministic detector output

Example:

The known gap engine fires because a predefined detector crossed a threshold.

This can be measured and prosecuted, but it is not automatically alpha. It is a state observation.

Allowed status:

- `MEASURED_GAP`
- `CLAIM_REQUIRED`
- `PROSECUTION_REQUIRED`
- `PROSPECTIVE_WATCH`

---

## Provenance class 3: human pre-test idea

Example:

You define a hypothesis before looking at the relevant outcome distribution.

This may be certifiable if the look ledger proves the idea was not conditioned on the result.

Allowed status:

- normal claim path,
- if contamination exists, prospective-only.

---

## Provenance class 4: retrospective LLM idea

Example:

A smart LLM browses the ASADO panel, notices that FX skew relief plus negative ETF flows preceded rebounds in several markets, and proposes a nonlinear detector.

This is the dangerous class.

Rule:

> **No in-sample certification. Ever.**

The idea may be useful. It may be brilliant. But the historical data helped create it, so the historical data cannot validate it.

Allowed status:

- `RETRO_SNOOPED_IDEA`
- `PROSPECTIVE_ONLY`
- `DETECTOR_DRAFT`
- `OOS_WATCH`

Forbidden status:

- `VALIDATED`
- `PROMOTED_BY_BACKTEST`
- `HARNESS_APPROVED`

---

## Provenance class 5: fixed-metric analog claim

Example:

A pre-registered matrix-profile retriever selects analogs without seeing forward returns, then outcomes are attached after selection.

This can be partially evaluated, because the metric was fixed before outcome inspection.

Allowed status:

- `ANALOG_MEASURED`
- `PROSPECTIVE_WATCH`
- `PROSECUTION_REQUIRED`

The LLM may explain differences among fixed analogs. It may not choose the metric after seeing the outcomes.

---

# The key new object: Frozen Claim

The Frozen Claim is the atom of the whole architecture.

Example:

```yaml
claim_id: C_20260625_0007
schema_version: 1

title: "Bank-neighbor return gap predicts 21-day country catch-up"
created_at: "2026-06-25T15:14:22-07:00"
created_by: "harness_sweep"
provenance_class: "pit_preregistered"

status: "frozen"

neutral_claim:
  sentence: >
    Countries with high bank-neighbor return gaps are expected to outperform
    low-gap countries over the next 21 trading days within the stable bank-coverage universe.

mechanism:
  economic_channel:
    - cross_border_banking_exposure
    - delayed_equity_absorption
  mechanism_text_neutral: >
    Banking-exposure neighbors may transmit information about regional risk appetite
    before local country equity prices fully reflect it.

variables:
  signal_table: "graph_features_pit_daily"
  signal_variable: "GRAPHP_BANK_NBR_RET_GAP_21D"
  transforms:
    - "cross_sectional_rank_by_date"

target:
  return_surface: "country_returns_daily"
  horizon_days: 21
  target_type: "relative_cross_sectional_return"
  direction: "long_high_short_low"

universe:
  universe_id: "stable_bank_coverage_v1"
  min_countries: 16
  exclusions:
    - "countries_without_pit_bank_edges"

timing:
  signal_asof_rule: "available_at_close_t"
  execution_lag_days: 1
  embargo_days: 21
  publication_lag_days: 0
  pit_proof_required: true

falsification:
  fatal_if:
    - "uses_non_pit_edges"
    - "requires_future_returns"
    - "fails_optimizer_reentry_check"
  must_survive:
    - "leave_gfc_out"
    - "leave_covid_out"
    - "country_jackknife"
    - "horizon_profile"
    - "cost_realism"
    - "postdiction_placebo"

data_snapshot:
  repo_sha: "<git_sha>"
  loop_db_snapshot_hash: "<hash>"
  asado_db_snapshot_hash: "<hash>"
  feature_asof: "2026-06-24"

firewall:
  prosecutor_packet_allowed: true
  sealed_rationale_ref: "journal/sealed_rationales/C_20260625_0007.md"
  prosecutor_may_see_rationale: false
```

Two versions exist:

1. **Git-canonical file**  
   `journal/claims/C_20260625_0007.yaml`

2. **Folded DB record**  
   stored into ASADO's loop database for querying and cockpit display.

If ASADO already has `hypothesis_ledger` and `harness_results`, this should **extend** those rather than duplicate them. The Court is not a parallel research system. It is the adversarial layer on top of the existing harness.

---

# The missing denominator: Research Look Ledger

This is one of the most important pieces.

The problem is not only:

> "Did we register the final hypothesis?"

The problem is:

> "How many things did we look at before we decided this was the hypothesis?"

That is the uncountable-trials hole.

So ASADO needs a **research look ledger**.

Every exploratory interaction that could condition a future claim gets logged.

Examples:

```yaml
look_id: L_20260625_0019
created_at: "2026-06-25T15:22:11-07:00"
actor: "llm"
purpose: "explore nonlinear country relationships"
data_seen:
  - "feature_panel"
  - "country_returns_daily"
  - "harness_results"
  - "gap_episodes"
  - "dislocation_daily"
look_type: "unbounded_exploratory_search"
generated_claims:
  - "C_20260625_0008"
snooping_status: "uncountable_trials"
certification_allowed: false
allowed_next_status: "prospective_only"
```

This is how you preserve imagination without poisoning the harness.

The system is allowed to say:

> "This is an interesting idea."

But it must also say:

> "This idea was born after an unbounded search, so historical validation is not admissible evidence."

That one sentence is the difference between a serious research institution and a narrative factory.

---

# Power-budget gate

This is the other piece I would add.

The project's romance is nonlinear discovery. But country allocation has a brutal statistical reality:

- only 34 countries,
- roughly 10,000 country-months / daily equivalents depending on horizon,
- overlapping returns,
- few true macro cycles,
- weak true ICs,
- major crisis concentration,
- many variables,
- many possible lags and transforms.

So before ASADO tries to certify a nonlinear claim, it should ask:

> "Do we even have the statistical budget to certify this?"

This is the **power-budget gate**.

A simple linear rank-IC claim with one variable and one horizon may be testable.

A conditional nonlinear claim like:

> "FX skew relief matters only when ETF flows are negative, sovereign CDS is not widening, valuation is cheap, and the country is a commodity exporter after a drawdown"

may be interesting, but it likely has too many degrees of freedom for the historical panel.

The system should compute an approximate power score:

```yaml
power_budget:
  effective_observations: 420
  raw_country_months: 10600
  overlap_adjusted_n: 900
  cycle_adjusted_n: 4.5
  parameter_count_proxy: 9
  expected_ic_band: [0.02, 0.05]
  minimum_detectable_ic: 0.075
  certification_power: "insufficient"
  allowed_status: "prospective_only"
```

Rule:

> If a claim is underpowered, it cannot be certified historically no matter how pretty the backtest looks.

This is how ASADO protects itself from exactly the kind of nonlinear overfitting that a brilliant model will naturally invent.

---

# Deterministic probe battery

Before the LLM Prosecutor runs, code should generate the evidence.

The first probe battery should be aggressive and ASADO-specific.

## Probe 1: Leave-one-crisis-out

Question:

> Does the signal survive without GFC, COVID, 2022 inflation/rates shock, China 2015, Eurozone crisis?

Output:

```yaml
probe: "leave_one_crisis_out"
base_nw_t: 3.1
without_gfc_nw_t: 0.8
without_covid_nw_t: 2.9
charge: "crisis_concentration"
severity: "high"
evidence: "GFC window accounts for 61% of total t-stat."
```

If the result is owned by one crisis, the Prosecutor should attack it hard.

---

## Probe 2: Country jackknife

Question:

> Does one country own the signal?

Output:

```yaml
probe: "country_jackknife"
worst_drop_country: "Turkey"
base_ic: 0.034
without_turkey_ic: 0.009
charge: "country_concentration"
severity: "high"
```

---

## Probe 3: Region and sleeve jackknife

Question:

> Does the mechanism claim broad macro behavior but work only in one sleeve?

Drop:

- LatAm,
- Asia,
- Europe,
- EM,
- DM,
- commodity exporters,
- commodity importers,
- current-account deficit countries,
- high-CDS countries,
- pegged FX countries.

If the claim says commodity pass-through and works only in importers, that is an indictment.

---

## Probe 4: Publication-lag sensitivity

Question:

> Would the signal still work if we used realistic data availability?

This matters for:

- IMF,
- WDI,
- WEO,
- IFS,
- BOP,
- WGI,
- OECD,
- CLI,
- EPU/GPR,
- any revised macro series.

Output:

```yaml
probe: "publication_lag_sensitivity"
lag_0_nw_t: 2.7
lag_1m_nw_t: 1.2
lag_3m_nw_t: 0.4
charge: "publication_lag_dependency"
severity: "fatal_or_high"
```

---

## Probe 5: Backfill/revision sensitivity

Question:

> Is the edge created by revised history that was not known at the time?

This is the classic macro-data trap.

If current-vintage data works but vintage-safe data does not, the Prosecutor should treat the claim as suspect.

---

## Probe 6: Optimizer re-entry / target contamination

Fatal check.

The feature must not secretly use:

- future returns,
- optimizer outputs,
- factor returns,
- top-20 membership,
- country factor attribution,
- future labels,
- any target-derived transformation.

Output:

```yaml
charge: "target_reentry"
severity: "fatal"
```

This should kill the claim automatically.

---

## Probe 7: Horizon coherence

Question:

> Does the claimed mechanism match the horizon where the signal works?

If the story is macro absorption over 6-12 months but the only edge is 1-day reversal, the mechanism is incoherent.

Output:

```yaml
probe: "horizon_profile"
ic_1d: 0.051
ic_5d: 0.012
ic_21d: -0.004
ic_63d: -0.006
charge: "horizon_incoherence"
severity: "medium"
```

---

## Probe 8: Cost and expression realism

A country signal is only as real as its expression path.

The system should check:

- primary ETF,
- alternate ETF,
- ADV,
- spread proxy,
- volume,
- tracking gap,
- expense ratio,
- FX basis,
- short interest,
- flow crowding,
- sleeve liquidity,
- China A/H proxy validity,
- pegged FX special cases,
- EM trading cost.

Output:

```yaml
probe: "expression_cost_realism"
gross_ls_sharpe: 0.72
net_5bps_sharpe: 0.31
net_10bps_sharpe: -0.05
breakeven_cost_bps: 7.8
charge: "edge_below_execution_noise"
severity: "high"
```

This is not "transaction costs are everything." It is expression realism: liquidity, ETF quality, expense drag, spread, crowding, tracking gap, FX basis.

---

## Probe 9: Placebo and postdiction

Question:

> Does the signal predict the past better than the future?

Test:

- past returns,
- shuffled country labels,
- shuffled date blocks,
- sign flip,
- wrong horizon,
- wrong universe.

If the signal predicts past returns better than future returns:

```yaml
charge: "postdictive_not_predictive"
severity: "high"
```

---

## Probe 10: Mechanism split

This is where ASADO becomes special.

The claim itself declares an economic channel. The probe battery then chooses splits implied by that channel.

If mechanism is commodity pass-through:

- exporters versus importers,
- oil exporters,
- copper exporters,
- precious metals,
- food/fertilizer exposure.

If mechanism is banking contagion:

- high bank exposure versus low bank exposure,
- creditor versus debtor,
- regional banking hubs.

If mechanism is FX stress:

- floating versus pegged,
- high FX debt versus low FX debt,
- current-account deficit versus surplus.

If mechanism is foreign-flow capitulation:

- markets with real flow coverage,
- high ETF ownership,
- foreign participation,
- liquidity sleeve.

The Prosecutor can then say:

> "The claimed mechanism is commodity pass-through, but the signal works mainly in non-exporters. The economic story is not coherent."

That is exactly the kind of reasoning code alone is bad at and an LLM Prosecutor is good at.

---

# The firewalled Prosecutor packet

The packet builder is the heart of the information firewall.

It should create a JSON packet like:

```json
{
  "claim_id": "C_20260625_0007",
  "neutral_claim": {
    "sentence": "High bank-neighbor return gap predicts 21-day relative outperformance.",
    "variables": ["GRAPHP_BANK_NBR_RET_GAP_21D"],
    "target": "21d relative country return",
    "universe": "stable_bank_coverage_v1",
    "direction": "long_high_short_low"
  },
  "provenance": {
    "class": "pit_preregistered",
    "trial_index": 14,
    "family_key": "graph_trade_gap",
    "research_look_contamination": false
  },
  "harness_stats": {
    "rank_ic": 0.034,
    "nw_t": 4.5,
    "deflated_sharpe": -0.12,
    "verdict": "WEAK"
  },
  "probe_results": [
    "... deterministic probe outputs ..."
  ],
  "variable_provenance": [
    "... source, lag, PIT proof ..."
  ],
  "allowed_actions": [
    "write_indictment",
    "assign_charge_codes",
    "request_permanent_probe",
    "recommend_prospective_only"
  ],
  "forbidden_actions": [
    "approve_claim",
    "promote_trade",
    "change_universe",
    "change_claim",
    "recommend_position",
    "use_generator_rationale"
  ]
}
```

It must explicitly exclude:

```yaml
forbidden_fields:
  - generator_rationale
  - bull_case
  - excitement_score
  - conviction
  - user_enthusiasm
  - trade_recommendation
  - prior_persuasive_memo
  - "why_this_is_huge"
```

The packet builder should fail if any forbidden field appears.

This is critical.

The Prosecutor must see enough to attack the claim, but not enough to be seduced by it.

---

# The Prosecutor prompt

The LLM prompt should be short, severe, and institutional.

Something like:

```text
You are the ASADO Prosecutor.

You are not an investment analyst.
You are not a portfolio manager.
You are not a signal promoter.
You are not allowed to recommend trades.

Your job is to make the strongest possible case that the frozen claim is false,
leaked, overfit, underpowered, crisis-owned, economically incoherent, mechanically
circular, untradable, or not point-in-time.

You receive only the neutralized claim, harness statistics, deterministic probe
results, and provenance metadata. You must not infer or recreate the claimant's
bull case. You must not praise the claim.

Survival under your critique is not approval. You do not adjudicate. You only
prosecute.

Return structured charges with evidence, severity, and proposed remedies.
If the evidence is insufficient, charge the claim with insufficient evidence.
If a new attack would be useful, propose it as a permanent probe for future claims.
```

Output:

```yaml
prosecution_id: P_20260625_0007
claim_id: C_20260625_0007
overall_posture: "serious_concerns"
recommended_gate_status: "prospective_only"

charges:
  - charge_code: "crisis_concentration"
    severity: "high"
    evidence:
      - "Removing GFC reduces NW t-stat from 3.1 to 0.8."
    interpretation: >
      The signal may be a single-crisis artifact rather than a persistent relationship.
    proposed_remedy:
      - "Require forward OOS tracking before any upgrade."

  - charge_code: "mechanism_incoherence"
    severity: "medium"
    evidence:
      - "Claimed banking channel, but effect is not monotonic by banking-exposure tercile."
    proposed_new_probe:
      name: "bank_exposure_tercile_monotonicity"
      scope: "all future banking-channel claims"

  - charge_code: "expression_fragility"
    severity: "medium"
    evidence:
      - "Net performance becomes unattractive above 10 bps one-way cost."
    proposed_remedy:
      - "Restrict to high-liquidity ETF sleeve before future tracking."

questions_for_human_judge:
  - "Should this be reclassified as short-horizon lead-lag rather than macro banking transmission?"

must_not_be_used_for:
  - "live allocation"
  - "claiming validated alpha"
```

---

# The Human Judge

The human ruling is separate from the Prosecutor.

The Prosecutor can recommend a gate status, but you decide.

Example:

```yaml
ruling_id: R_20260625_0007
claim_id: C_20260625_0007
judge: "Arjun"
decision: "prospective_watch"
date: "2026-06-25"

rationale: >
  The signal is interesting but partially crisis-concentrated and not strong enough
  after expression costs. It is worth tracking prospectively but not eligible for
  allocation or promotion.

conditions:
  - "Track for 252 trading days."
  - "Require no degradation in non-crisis windows."
  - "Add bank-exposure monotonicity probe to future battery."
  - "Do not use for live trading before future ruling."
```

No LLM is the judge.

That is the point.

---

# The prospective OOS queue

This is the clean path for nonlinear LLM discovery.

A model may propose a weird relationship. Fine.

But if the idea came from historical exploration, it goes here:

```yaml
claim_id: C_20260625_0011
status: "prospective_watch"
start_date: "2026-06-25"
first_readout_date: "2026-09-25"
full_horizon_date: "2027-06-25"
required_observations: 252
observations_so_far: 0
in_sample_certification: "forbidden"
reason: "retrospective_llm_discovery"
```

The cockpit should show this beautifully:

```text
Prospective Discoveries Incubating

C_0011  FX skew relief + negative flows capitulation
Status  38 / 252 trading days observed
First readout  2026-09-25
Full readout   2027-06-25
Historical status  Retrospective-snooped; not certifiable
```

This is psychologically important.

A lot of bad research happens because waiting feels like doing nothing.

ASADO should make waiting feel like accumulating evidence.

---

# The Prosecutor also needs a track record

The Prosecutor can itself become a source of false negativity.

So it must be scored.

Every charge is a prediction.

If the Prosecutor says:

> "This signal is likely crisis-owned and will decay OOS."

Then after the OOS window, ASADO checks:

- Did it decay?
- Did claims with this charge perform worse than claims without it?
- Which charge codes predict failure?
- Which charge codes are noise?
- Which Prosecutor model is too aggressive?
- Which Prosecutor model is discriminating?

Add a table:

```text
prosecutor_calibration
```

Fields:

```yaml
charge_code: "crisis_concentration"
claims_flagged: 37
oos_decay_rate_flagged: 72%
oos_decay_rate_unflagged: 41%
calibration_edge: 31%
status: "useful_charge"
```

This keeps the Prosecutor honest.

The Prosecutor is not above the system.

It is another model whose judgments must earn trust.

---

# The kill-reason library

This may become the most valuable artifact in ASADO.

Not an alpha library.

A failure library.

Every killed or downgraded claim gets structured kill reasons:

```yaml
kill_reason_taxonomy:
  leakage:
    - target_reentry
    - publication_lag_failure
    - backfill_dependency
    - non_pit_feature
    - analog_outcome_selection

  statistical_fragility:
    - crisis_concentration
    - country_concentration
    - region_capture
    - sign_instability
    - horizon_instability
    - low_effective_n
    - duplicate_family_inflation
    - insufficient_power

  economic_incoherence:
    - mechanism_split_failure
    - wrong_country_sleeve
    - exposure_nonmonotonicity
    - channel_not_present
    - narrative_afterthought

  expression_fragility:
    - edge_below_execution_noise
    - etf_tracking_gap
    - liquidity_too_thin
    - crowding_sensitive
    - borrow_or_short_constraint

  governance:
    - unregistered_claim
    - incomplete_trial_record
    - missing_data_snapshot
    - firewall_breach
    - uncountable_trials
```

The system should answer:

- What kills most ASADO signals?
- Which data family produces the most false excitement?
- Which mechanisms are repeatedly incoherent?
- Which probes draw blood most often?
- Which claims survive prosecution but fail OOS?
- Which Prosecutor charges are predictive?
- Which errors are warehouse problems rather than market problems?

This is the compounding edge.

Most investment systems hide their graveyard.

ASADO should make the graveyard the crown jewel.

---

# What to do with analogs

The analog idea is still valuable, but only if the LLM does **not** choose the analogs narratively.

The safe architecture is:

## Step 1: Pre-register analog metrics

For example:

```yaml
metric_id: "matrix_profile_macro_state_v1"
feature_blocks:
  - returns_state
  - valuation_state
  - sovereign_stress
  - fx_options_state
  - flows_positioning
  - commodity_exposure
distance: "rank_normalized_euclidean"
lookback_window_days: 252
outcome_blind: true
```

## Step 2: Retrieve analogs without seeing forward outcomes

The retriever selects analogs using only state information available at the time.

```text
Indonesia 2026-06-24 resembles:
- Brazil 2015-09-22
- Turkey 2018-08-13
- Korea 2008-10-15
- Indonesia 2020-03-18
```

## Step 3: Attach outcomes after retrieval

Only after the analog set is frozen do we join forward returns.

## Step 4: Let the LLM do qualitative differencing

Now the LLM can say:

> "Today resembles Brazil 2015 in FX stress and equity drawdown, but differs because current-account pressure is lower, commodity beta is favorable, and foreign-flow capitulation has not yet stabilized."

That is safe.

The LLM can explain.

It cannot choose the metric after seeing outcomes.

It cannot select the analog set narratively.

It cannot say, "These are the analogs I find compelling" after looking at which ones made money.

That is how you preserve the original dream while removing narrative cherry-picking.

---

# What to do with the Muse

I would not build a first-class "Imagination Engine" now.

I would eventually build a **quarantined Speculative Lab**, but with strict limits.

Its only allowed output:

```text
prospective detector drafts
```

Example:

```yaml
detector_draft_id: DRAFT_20260625_0012
created_by: "llm"
status: "draft_not_tested"

idea: >
  FX option skew relief while ETF flows remain negative may indicate capitulation
  in countries where sovereign CDS is not widening.

suggested_variables:
  - "FX_RR25_1M_Z252"
  - "ETF_FLOW_21D_Z"
  - "SOV_CDS_5Y_Z"

suggested_target:
  return_surface: "country_returns_daily"
  horizon_days: 21

certification_rule:
  historical_certification: "forbidden_if_generated_after_panel_search"
  allowed_path: "freeze_as_prospective_claim"
```

The Muse can create detector drafts.

It cannot validate.

It cannot rank today's best alpha.

It cannot write a persuasive trade memo.

It cannot appear in the cockpit as "LLM-discovered opportunities."

It appears as:

```text
Speculative Drafts Awaiting Prospective Registration
```

That wording matters.

---

# The cockpit: from dashboard to courtroom

The Chief-of-Staff cockpit should change.

Not:

```text
Known Gaps
LLM Ideas
Promoted Signals
Interesting Rejections
```

That is too flattering.

Instead:

## 1. Today's Docket

```text
Claims requiring judgment
Claims under prosecution
Claims newly killed
Claims entering prospective watch
Claims with OOS readouts due
```

## 2. Known Gap Monitor

The current deterministic layer.

Label it honestly:

```text
Known Relationships Currently Stretched
```

## 3. Prosecution Board

For each claim:

```text
Claim: Bank-neighbor gap
Harness: WEAK
Top charges:
- crisis concentration: high
- expression cost: medium
- mechanism monotonicity: unresolved
Recommended gate: prospective-only
```

## 4. Prospective Incubator

```text
C_0011: 38 / 252 days observed
C_0012: first readout due in 17 days
C_0013: full horizon completes 2027-06-25
```

## 5. Kill-Reason Analytics

```text
Last 90 days:
- 34% killed by publication-lag sensitivity
- 22% killed by crisis concentration
- 17% killed by expression cost
- 11% killed by mechanism incoherence
- 8% killed by target contamination
```

## 6. Prosecutor Calibration

```text
Charges that predicted OOS decay:
- crisis_concentration: strong
- expression_untradable: strong
- mechanism_incoherence: moderate
- region_capture: weak
```

## 7. Fixed-Metric Analogs

Show:

```text
Analog metric used:
Outcome-blind:
Forward outcomes attached after retrieval:
LLM qualitative differencing:
```

Make the epistemology visible.

That is the part that will amaze people.

Not the chart.

The honesty.

---

# Repo-native implementation

I would not build a giant parallel system. I would extend ASADO's existing research machinery.

Suggested new structure:

```text
PRD_ASADO_Court_Of_Disbelief.md

config/
  court_policy.yaml
  prosecutor_charge_taxonomy.yaml
  probe_battery.yaml
  analog_metric_registry.yaml

journal/
  claims/
  rulings/
  sealed_rationales/
  prosecutor_briefs/
  research_looks/
  detector_drafts/

scripts/
  court/
    __init__.py
    claim_schema.py
    freeze_claim.py
    research_look_ledger.py
    provenance_classifier.py
    power_budget.py
    build_probe_battery.py
    run_probe_battery.py
    build_prosecutor_packet.py
    run_prosecutor.py
    parse_prosecution.py
    gate_claim.py
    update_oos_queue.py
    prosecutor_calibration.py
    kill_reason_rollup.py
    retrieve_analogs.py
    attach_analog_outcomes.py

scripts/court/probes/
  leave_one_crisis_out.py
  country_jackknife.py
  region_jackknife.py
  lag_sensitivity.py
  backfill_sensitivity.py
  optimizer_reentry.py
  horizon_profile.py
  expression_cost.py
  placebo.py
  mechanism_split.py

tests/court/
  test_claim_schema.py
  test_research_look_ledger.py
  test_power_budget.py
  test_firewall_packet.py
  test_forbidden_fields.py
  test_probe_battery_toy_signal.py
  test_prosecutor_output_schema.py
  test_gate_claim.py
  test_analog_outcome_blindness.py
```

Loop DB additions:

```text
claim_overlay
research_look_ledger
probe_results
prosecutor_runs
prosecutor_charges
human_rulings
oos_watch_queue
oos_outcomes
kill_reason_rollups
prosecutor_calibration
analog_retrieval_runs
analog_members
detector_drafts
firewall_audit_log
```

If `hypothesis_ledger` already has many core fields, do not replace it. Add a claim overlay keyed to existing hypothesis IDs.

---

# Build order

## Phase A — Court constitution

Build:

- `PRD_ASADO_Court_Of_Disbelief.md`
- `config/court_policy.yaml`
- `config/prosecutor_charge_taxonomy.yaml`
- claim schema
- `journal/claims/`
- claim freeze CLI

Acceptance:

- A claim can be frozen.
- A malformed claim fails validation.
- A claim without provenance cannot proceed.
- A claim without falsification terms cannot proceed.

---

## Phase B — Research look ledger

Build:

- `research_look_ledger`
- CLI to record exploratory looks
- automatic contamination flag
- provenance classifier

Acceptance:

- A claim generated from an unbounded LLM look is auto-stamped `retrospective_llm`.
- Such a claim cannot receive in-sample validation status.
- It can only enter prospective watch.

This is the phase that actually fixes the harness-laundering problem.

---

## Phase C — Power-budget gate

Build:

- effective-N estimator,
- parameter-count proxy,
- certification power score,
- underpowered-claim routing.

Acceptance:

- A one-variable rank-IC claim can proceed.
- A complex conditional nonlinear claim is routed to `prospective_only` unless it has enough effective evidence.
- The system explicitly says why.

---

## Phase D — Deterministic probe battery

Start with seven probes:

1. leave-one-crisis-out,
2. country/region jackknife,
3. publication-lag sensitivity,
4. optimizer-reentry,
5. horizon profile,
6. expression cost,
7. placebo/postdiction.

Acceptance:

- Probe battery runs on existing known signals.
- It kills a deliberately contaminated toy signal.
- It produces machine-readable charges.

---

## Phase E — Firewalled packet builder

Build:

- neutralized claim packet,
- sealed rationale path,
- forbidden-field scanner,
- packet hash,
- CI tests.

Acceptance:

- Prosecutor packet excludes bull case.
- Tests fail if `generator_rationale`, `excitement_score`, `trade_recommendation`, or similar fields are included.
- Mechanism text is neutralized.

---

## Phase F — LLM Prosecutor

Build:

- `run_prosecutor.py`,
- structured charge output,
- charge parser,
- markdown prosecution brief,
- model/version stamping.

Acceptance:

- Given a claim and probe results, Prosecutor emits valid charges.
- It does not recommend trades.
- It does not approve claims.
- It does not rewrite the claim.
- It can propose permanent new probes.

---

## Phase G — Gate and prospective queue

Build:

- deterministic gate,
- human ruling file,
- OOS queue,
- forward outcome updater,
- cockpit data integration.

Acceptance:

- A claim can move through:

```text
frozen -> tested -> probed -> prosecuted -> ruled -> prospective watch
```

- A retrospective LLM claim skips certification and goes directly to prospective watch or death.
- No claim receives `approved_for_trading`.

---

## Phase H — Prosecutor calibration and kill-reason analytics

Build:

- prosecutor charge scoring,
- OOS charge calibration,
- kill-reason rollups,
- cockpit panels.

Acceptance:

- System can answer:
  - "Which charges predicted OOS failure?"
  - "What kills most ASADO claims?"
  - "Which source family creates the most false positives?"
  - "What probe should we harden next?"

---

## Phase I — Fixed-metric analog machine

Build later, after the Court works.

Acceptance:

- Analog metric is pre-registered.
- Retrieval occurs before outcomes are attached.
- Test proves the LLM cannot choose analogs after seeing forward returns.
- LLM only performs qualitative differencing on fixed analog sets.

---

## Phase J — Quarantined Muse

Only after A-I.

The Muse is rate-limited and can only create prospective detector drafts.

Acceptance:

- It cannot run historical validation.
- It cannot produce "opportunity" cards.
- It cannot appear as promoted intelligence.
- Its outputs are stamped `draft_not_tested`.

---

# What the Chief of Staff becomes

The Chief of Staff should not be the alpha genius.

It should be the research clerk, court reporter, and institutional memory interface.

It should answer:

- What claims are on today's docket?
- What did the Prosecutor kill?
- Which claims are stuck because of missing PIT proof?
- What are our most common kill reasons?
- Which claims are waiting for forward OOS?
- Which Prosecutor charges have historically been predictive?
- What data source is generating the most false excitement?
- Which gap episodes became frozen claims?
- Which speculative drafts need human decision?
- What would need to be true for this claim to survive?

It should not answer:

- What should I buy?
- Which signal is definitely true?
- Which LLM idea is best?
- Should we override the Prosecutor?
- Is this alpha real?

The CoS becomes a disciplined interface to the Court, not a charismatic narrator.

---

# The world-class demo

The demo I would want ASADO to give is not:

> "Look, ASADO found a high-Sharpe country signal."

That is ordinary. Everyone claims that.

The demo is:

> "ASADO generated 47 plausible country-return hypotheses this month.  
> 14 were killed for publication-lag dependency.  
> 8 were killed for crisis concentration.  
> 7 were killed for expression-cost fragility.  
> 5 were killed for mechanism incoherence.  
> 5 were underpowered nonlinear claims and were barred from historical certification.  
> 6 were retrospective LLM ideas and were quarantined into prospective watch.  
> 2 PIT-clean claims survived prosecution and entered forward OOS.  
> The Prosecutor's crisis-concentration charge has historically predicted 71% OOS decay, so we trust it.  
> The system added two permanent probes because repeated false positives came from WEO revision timing and ETF flow crowding."

That is the amazing thing.

Not that ASADO has imagination.

That ASADO has institutionalized doubt.

---

# The deepest answer

You are right that the deterministic gap engine is not the full dream.

But the next layer should not be:

> "A brilliant LLM finds hidden nonlinear alpha."

The next layer should be:

> "A brilliant LLM is safely deployed as an adversary inside a research court, while any alpha imagination it produces is quarantined into prospective registration."

That preserves the original ambition without letting it destroy the statistical honesty of the project.

The final architecture is:

```text
Known Gap Monitor
    ↓
Frozen Claim Registry
    ↓
Research Look / Provenance Ledger
    ↓
Power-Budget Gate
    ↓
Deterministic Probe Battery
    ↓
Firewalled LLM Prosecutor
    ↓
Human Ruling
    ↓
Prospective OOS Queue
    ↓
Prosecutor Calibration + Kill-Reason Library
    ↓
Courtroom Cockpit / Chief of Staff
```

Then, and only then:

```text
Fixed-Metric Analog Machine
Quarantined Prospective Muse
```

That is the solution.

ASADO should become the first investment research environment where the LLM's highest use is not persuasion, but **anti-persuasion**.

The best agent to build is not the dreamer.

It is the Prosecutor.
