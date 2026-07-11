# ASADO Learning Loop — Design (v2)

**Date:** 2026-07-10 (v2, same day — incorporates GPT-5.6 design review)
**Status:** DRAFT — approved as design basis with amendments; no code written yet
**Authors:** Claude (Fable 5) v1; v2 amendments from GPT-5.6 review, accepted by Fable
**Supersedes:** v1 of this file (see git history)

---

## Purpose

Close the loop the 2026-07-10 GPT-5.6 repo review identified as missing. ASADO
makes recommendations (promoted gap episodes, briefs, cockpit consensus, Fable
conjectures) but never scores them, never attributes why they were right or
wrong, and never feeds anything back. This designs a **closed learning loop**:

> **Recommend → Track (data flow + price action) → Score → Attribute → Learn → Adjust future recommendations**

with Fable-xhigh as the attribution/synthesis brain and deterministic code as
the measurement substrate, reusing existing machinery (gap episode lifecycle,
`gap_holdout_daily`, autopsy table, JSONL ledgers, nightly Fable call site).

**Design principle (unchanged from v1):**
**Deterministic code measures; the LLM interprets; nothing self-modifies without a gate.**
The LLM never assigns outcome classes or touches numbers; it explains within a
code-assigned decomposition. Adaptation is shadow-first and human-gated.

**v2 headline changes vs v1** (from the GPT-5.6 review, all accepted):
1. New **Stage 0**: a universal claim contract + structured evidence/confirmation/invalidation specs + frozen return formula — the measurement substrate is now specified before the learning intelligence.
2. Outcomes go to a new **append-only `gap_outcomes` table** with correction events, not mutations of `gap_holdout_daily`.
3. **`etf_ownership_drag_bps` is NOT deducted from realized returns** — adjusted ETF prices already embed expenses (double-count bug caught in review). It stays ex-ante only.
4. Single-label outcome taxonomy replaced by **multi-axis attribution** (labels like `DATA_RIGHT_NOT_CAPTURABLE` become *derived* headlines).
5. Learned priors run **shadow-only** with counterfactual logging until the pre-registered `gap_engine.yaml` evidence gate (≥80 closed promoted episodes, ≥3 matched controls each) passes — my 126-day gate was weaker than the existing preregistration and is dropped in its favor.
6. Full **LLM provenance** on every lesson (model ID, effort, prompt hash, packet hash, response hash, tokens, schema version).
7. Inference clusters by selection date and country; the unit is the episode, not the candidate-date row.

---

## Stage 0 — The measurement substrate (new in v2)

### 0a. Canonical claim contract

Every recommendation the system ever wants evaluated must eventually be
expressible as one canonical claim record:

```text
claim_id            emitted_at           data_as_of
decision_available_at                    entity
direction           expression_ticker    benchmark
horizon_days        mechanism_cluster    evidence_refs[]
confirmation_spec   invalidation_spec    policy_version
```

- **Adapter 1 (v1 scope): gap episodes** — mostly a projection of existing columns plus the new structured specs below.
- **Adapter 2 (later): Fable conjectures** — `build_fable_connections.py` output schema gains required `entity/direction/horizon_days/expression_ticker/invalidation_spec` fields; a conjecture that won't declare them is context, not a claim, and is excluded from evaluation.
- **Adapter 3 (later): cockpit consensus and thesis-ledger claims.**

### 0b. Structured evidence, confirmation, invalidation

Current `world_state_json` is values + prose and `invalidation_rule` is free
text — a deterministic classifier cannot decide "the data was right" from
those. Each claim (at open, PIT-frozen) must carry:

- `evidence_refs[]`: `{table, variable, entity, obs_date, available_at, vintage, value}` — machine-readable pointers into the warehouse.
- `confirmation_spec`: an executable predicate over future values of the referenced series (e.g. "trade_nbr_gap_21d reverts below +0.5σ within horizon" / "CPI revision confirmed in next vintage"), evaluated point-in-time at maturity.
- `invalidation_spec`: an executable predicate (level/date), same discipline.

Detector authors write these once per detector template. Without them, Fable
would end up implicitly judging whether the data was right — the exact thing
the architecture forbids.

> **DECISION (Arjun, 2026-07-10): v1 uses a LIGHTWEIGHT deterministic heuristic,
> not full per-detector predicates.** The classifier assigns `data_validity` by
> checking whether the claim's headline world-state z-score **reverted toward
> neutral vs persisted/extended** over the horizon (computed from the warehouse,
> PIT). Imperfect — it approximates confirmed/revised_away rather than reading a
> bespoke `confirmation_spec` — but real, cheap, and it unblocks Stage 2 without a
> per-detector build. The code still assigns the class from the z-trajectory;
> Fable only explains within it, so the "code assigns, LLM explains" invariant
> holds. Full structured `evidence_refs`/`confirmation_spec`/`invalidation_spec`
> per detector remain the upgrade path once the heuristic's error cases are seen.

### 0c. Frozen return formula (pre-registered here)

Primary outcome, per claim, at its declared horizon:

```text
gross_active = direction × (ETF total return − EW-34 benchmark return)
net_active   = gross_active − entry_cost − exit_cost − borrow_cost(if short)
```

Reported alongside, never mixed in:

```text
index_information = direction × (country-index return − EW-34 return)
etf_capture       = direction × (ETF return − country-index return)   # includes FX + basis
```

Conventions to freeze before coding (Stage 0 deliverable is this spec, reviewed by Arjun):
- **Entry:** first tradable close at/after `decision_available_at` (promotion is computed after the close, so entry = next session's close; no look-ahead).
- **Exit:** close of session `entry + horizon_days` trading days on the ETF's calendar; holiday/stale-quote handling = last prior close carried, flagged.
- **Prices:** total-return (dividend-adjusted) series for ETF and benchmark alike; document the source and the adjustment convention.
- **Expenses:** `etf_ownership_drag_bps` is **not** subtracted from realized adjusted returns (already embedded in NAV/price); it remains an ex-ante expression-quality input only.
- **Costs:** 25bp **per side** (entry + exit both charged); short borrow at a per-ticker table (default conservative estimate, flagged where estimated).
- **Benchmark:** EW-34, rebalancing convention documented and identical to the FDT/Alpha-Book convention so results are comparable.
- **Mapping edge cases:** ChinaA/ChinaH dual expression, U.S. multi-expression, ETF delistings/mapping changes — enumerated in the spec with one rule each.
- Every outcome row carries `scoring_version`; formula changes bump the version, never rewrite old rows.

### 0d. Append-only outcome store

`gap_holdout_daily` stays immutable (it is the selection record). New loop-DB table:

```text
gap_outcomes
  outcome_id  claim_id/candidate_id  evaluation_horizon
  entry_ts  exit_ts
  gross_etf_return  benchmark_return  index_return  capture_return
  transaction_cost  borrow_cost  net_active_return
  scoring_version  scored_at  correction_of (nullable)
```

Data corrections append a new row with `correction_of` set — history is never
silently rewritten and wrong values are never forced to stand.

---

## Stage 1 — Scorer + truthfulness fixes

**1a. Outcome scorer** — new loop step `score_gap_outcomes` after
`build_country_returns`: for every claim (promoted **and** eligible control)
reaching maturity, append a `gap_outcomes` row per the frozen formula.
Idempotent; append-only; fail-loud on missing prices (no silent skips).

**1b. Autopsy honesty** (`build_gap_episodes.py`): direction-adjust
`net_return_after_etf_drag` (and rename it — the drag deduction is gone);
close adverse/expired episodes with honest labels so autopsies stop being
survivorship-selected.

**1c. Capture clock**: `data_known_at`, `decision_available_at`,
`absorbed_at` on episodes/claims — distinguishes "data led and was tradable"
from "the open already had it".

**1d. Brief hygiene** (`render_dislocation_brief.py`): `repriced_against`
episodes out of Top Gaps, into a "rejected by price / awaiting autopsy" section.

**1e. Mechanism clustering**: `mechanism:` field in `config/family_ranks.yaml`
(diffusion = graph_bank + graph_twohop + twins + leadlag); cockpit consensus
counts one vote per mechanism; lessons and priors accrue at mechanism level.

**Stage 1.5 — shadow audit.** Run the scorer for the first maturation cycle
(~1 month) and **manually audit every early matured case** (entry/exit prices,
FX, calendar handling, control matching) before anything downstream consumes
the numbers.

---

## Stage 2 — Attribution (multi-axis, then Fable xhigh)

At claim maturity/closure, a deterministic **autopsy packet** (~2-4KB) is
assembled: the claim as frozen at open; what the referenced data did
(via `confirmation_spec` evaluated PIT); what price did (the `gap_outcomes`
decomposition + absorption path vs expected + capture clock); matched-control
outcomes and the frozen `random_shadow_score`.

The classifier scores **independent axes** (no single mutually-exclusive label):

| Axis | Values |
|---|---|
| data_validity | confirmed / revised_away / unknown |
| price_response | with_thesis / against_thesis / unresolved |
| timing | tradable / pre_absorbed / late |
| expression | captured / basis_failure / unavailable |
| economics | positive_net / negative_net |
| horizon_fit | on_time / too_early / too_late |

Headline classes (e.g. `DATA_RIGHT_NOT_CAPTURABLE` = data confirmed +
with_thesis on index + basis_failure or pre_absorbed + negative_net) are
*derived* views for reporting; the axes are the record.

Then **one Fable-xhigh call per matured claim** (cap 5/night, overflow queued,
fail-soft) writes the structured lesson to **`ledgers/lesson_ledger.jsonl`**
(append-only, committed):

```json
{"event": "lesson", "lesson_id": "L_...", "claim_ids": [...],
 "mechanism_cluster": "diffusion", "axes": {...}, "headline_class": "...",
 "diagnosis": "<3-5 sentences>", "generalizable": true,
 "proposed_adjustment": {"knob": "...", "direction": "down", "evidence_n": 7},
 "confidence": "medium", "supersedes": null,
 "provenance": {"model_id": "<exact>", "effort": "xhigh",
                "prompt_version": "...", "prompt_hash": "...",
                "packet_hash": "...", "response_hash": "...",
                "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0,
                "attribution_schema_version": "1"}}
```

"Fable xhigh" is operationally defined: the exact model ID resolved at call
time is recorded, the reasoning-effort parameter is explicitly set and
recorded, and prompt/packet/response hashes make every lesson reproducible and
auditable. Fable explains *within* the code-assigned axes; it never assigns them.

---

## Stage 3 — Feed-forward

**3a. Lessons digest (informational, automatic).** The nightly
`build_fable_connections.py` packet gains the 10 most recent + 10
highest-confidence lessons — the cheap 80% of "learning from mistakes".

**3b. Weekly review board (Fable xhigh, human-gated).** Weekly job: read the
week's matured autopsies + lesson ledger + promoted-vs-control lift table;
write `Data/dislocations/review_board_YYYY_MM_DD.md` with systematic-error
findings and concrete **proposals** (threshold/weight/eligibility changes).
Proposals only — Arjun approves before any config/code change.

**3c. Learned priors — SHADOW ONLY (Stage 4).** A versioned
`mechanism_priors` table, built with:
- Hierarchical Beta-Binomial shrinkage for hit probability, a separate
  shrunken model for net-return magnitude; hierarchy global → mechanism →
  gap_class → region (cells inherit until they earn data — no fixed N=10 knife-edge).
- Fixed monthly update dates; every row `as_of`-versioned (PIT-reproducible).
- **Every day, both policies are computed and logged side by side:**
  `static_score, learned_score, static_promoted, learned_promoted` per
  candidate — the counterfactual record that later proves (or kills) the learner.
- **Zero effect on actual promotion** until Stage 5's gate.

**Stage 5 — activation gate.** Learned priors may influence real promotion
only after the pre-registered `config/gap_engine.yaml` holdout gate is met
(≥80 closed promoted episodes with ≥3 matched controls each) AND the shadow
log shows learned-policy selections outperforming static net of costs. Until
then the learner is context, exactly like Triptych.

---

## Controls & inference (tightened in v2)

- Controls matched on: selection date, horizon, gap class/mechanism, region,
  direction, liquidity tier, expression availability. The existing
  `gap_engine.yaml` preregistration (3 controls per promoted episode, ≥80
  closed promoted episodes) is the governing sample-size gate.
- **Statistical unit = episode**, never the repeated candidate-date row.
- Overlapping 21d windows are not independent: cluster standard errors by
  selection date and by country (two-way), or block-bootstrap by selection date.

## Evaluation horizon

Claims are scored at their **declared** `horizon_days` (frozen at open — no
horizon shopping), 63d as secondary. Live mix today: 37/38 episodes at 21d,
1 at 63d; buckets 5/21/63/126 exist in config. If autopsies show a systematic
`too_early` pattern on slow-diffusion mechanisms, the review board's remedy is
detectors declaring longer buckets — not post-hoc horizon extension.

## Cost & cadence

Nightly: scorer + classifier (no LLM) + ≤5 Fable-xhigh autopsy calls →
typically <$2/night. Weekly: one review-board session (~50-100K in / 8K out).
All LLM steps fail-soft; the deterministic scorer never depends on the LLM.

## Build order (v2)

| # | Stage | Contents | Gate to proceed |
|---|---|---|---|
| 1 | **0** | Claim/evidence/outcome schemas; frozen return + control spec doc | Arjun reviews the metric spec |
| 2 | **1** | Scorer, `gap_outcomes`, autopsy honesty, capture clock, brief hygiene, mechanism clustering | tests + adversarial cases |
| 3 | **1.5** | Scorer shadow month; manual audit of first matured cases | audit clean |
| 4 | **2** | Multi-axis classifier + Fable autopsies + lesson ledger | — (informational) |
| 5 | **3** | Lessons digest + weekly review board | — (informational/human-gated) |
| 6 | **4** | Learned priors in shadow + counterfactual logging | — (shadow) |
| 7 | **5** | Priors affect promotion | preregistered 80-episode gate + shadow outperformance |

Effort: ~10-12 working days for a production-quality substrate (calendars,
total-return data, control matching, correction events, adversarial tests) —
the v1 7-day figure was a prototype estimate. The **evidence** still takes
months to earn; nothing shortens that honestly.

## What cannot be backtested (unchanged from v1, restated)

The scorer and the prior-update *mechanics* can be validated on history; the
learning itself cannot: episode history is ~1 month old, synthetic historical
episodes would be contaminated (detectors were designed on that history; PIT
world-state doesn't exist retrospectively for several sources), and Fable's
training data contains the historical outcomes, so backtested "lessons" are
recall, not inference. The loop earns its evidence forward, via the shadow
logs and the preregistered gate.

## Approval status (per Arjun / GPT-5.6 review, 2026-07-10)

- **Approved now:** autopsy honesty, brief hygiene, mechanism clustering, claim/outcome schema work (Stage 0-1 structural items).
- **Approved after metric spec review:** outcome scorer + capture clock (the Stage 0c/0d spec doc is the gate).
- **Approved as informational:** Fable autopsies, lessons digest, weekly review board.
- **Deferred from affecting recommendations:** automatic mechanism priors, until the forward gate is met.
