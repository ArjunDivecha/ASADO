# ASADO Nonlinear Country-Return Study — Results

**Spec:** `spec/PRD.md` (ASADO_NL_20260913_V2, AM-1 amended)
**Registration:** methodology ledger `M_20260913_001`
**Locked code commit:** `fa7e51d` (validator: `src/validate_registration.py`)
**Amendments:** AM-1 — dropped P07/P08 (bank-neighbor, 21-focal cap) and
P11 (3M FX risk reversal does not exist in the collector); 21 primitives,
15-input S, 22-market universe. Approved by owner before any result
exposure.

## 1. Was the experiment valid?

- P01 field-level audit: strict spec was BLOCKED_DATA (15 markets max vs
  the 20-market floor); resolved by owner-approved AM-1.
- P02: independent local-session calendars from TRI mark changes; labels
  built from TRI levels, not forward-return fields; censored tail kept.
- P03: 21-primitive causal panel + 15-input S; trade-impulse graph uses
  the full 34-market network (mass-preserving).
- P04: common sample, 25 chronological outer fits (first 2020-07-01),
  four 6-month inner blocks per annual retune, maturity-gated label store.
- P05: estimator suite verified on synthetic fixtures (22 tests).
- P06: protocol locked + registered (`governance/protocol.lock.json`,
  `registration_receipt.json`, `trial_manifest.json` 72 configs,
  `run_plan.json`, `exposure_log.jsonl`).
- P07: inference calibration PASS (FWER 3%/5% vs 5% nominal);
  historical replay of all 25 fits completed twice (v2 is authoritative;
  v1 preserved; the correction is a logged exposure event).

## 2. The actual sample

- Eligible panel: 72,872 origin×market rows, 3,403 scored origins,
  2012-01-20 → 2026-09-10; last whole-mature origin 2026-08-12.
- Outer scored axis: 1,467 origins (2020-07-01 → 2026-08-12).

## 3. Headline result

**Verdict: `INCOMPLETE_REGISTERED_PROCEDURE`** (authoritative run:
`p07_replay_real_v2`, all 25 fits, frozen base-calendar bin indexing).

The primary candidate N_S (depth-2 histogram boosting on S) and N_X
produced **zero outer forecasts**: at every one of the 7 annual retunes,
**all 12** tree configurations failed the registered terminal-leaf
support audit (≥126 distinct origins, ≥12 fixed-20-origin bins, ≥3
calendar years, ≥4 markets per leaf) in **every** inner fit — a uniform
structural failure, not a marginal one. The binding constraint is the
126-origin-per-leaf floor: depth-2 boosting reliably isolates narrow
episodes into leaves spanning 34–106 origins.

A_S (depth-1, 2 leaves) was admissible at 4 of 7 retunes and issued
forecasts at 15 of 25 fits (899/1467 origins): selection-level blocking
under the 2021-07 and 2023-07 retunes, plus outer-fit support failures
at 2022-10-03 (5 unsupported leaves) and 2026-07-01.

Per the registered decision table: "Mandatory model cannot fit under
support rules → Incomplete registered procedure. Preserve failures; no
quarter deletion or replacement winner." The support guard's binding
dimension is exactly what it was designed to catch: real 20-session
country returns contain concentrated episodes that shallow trees isolate
into temporally thin leaves.

### Descriptive (not a claim): covered linear streams

| stream | mean MSE | mean IC | origins covered |
|---|---|---|---|
| B0 | ~0.003858 | 0.000 | 1467/1467 |
| L_X | ~0.003845 | +0.007 | 1467/1467 |
| L_S | ~0.003858 | +0.017 | 1467/1467 |
| L_star | ~0.003845 | +0.004 | 1467/1467 |
| Q_S | ~0.003858 | −0.012 | 1467/1467 |
| A_S | ~0.003698 (partial) | −0.013 | 899/1467 |
| N_S | — | — | 0/1467 |
| N_X | — | — | 0/1467 |

Descriptive only — no primary comparison can run when the primary stream
has no forecasts. The linear streams' ICs are small; nothing here is
promotable.

## 4. Controls (P07 §11.2)

Terminated early at owner's direction: 338/500 full nested replays
completed under the frozen pseudo-label generator (q=0, 0.001, 0.005:
100 each; q=0.01: 38; q=0.10: 0). The generator reads frozen generator
parameters and genuine maturity/eligibility metadata only — never
genuine label values. Per-rep results in
`Data/work/experiments/nonlinear_country_returns/p07_controls/`;
restartable from checkpointed fits.

Partial-run distribution (decisive for the scientific question):
- **Primary declarations: 0/338**, including all 138 reps with planted
  nonlinear signal (q ≥ 0.005).
- **N_S never reached full coverage in any rep** — max 426/1467 scored
  origins at q=0.01. The 12.2 coverage gate therefore makes a primary
  declaration structurally unreachable for this model class.
- Linear-world false-positive rate: 0/100 at q=0 (correctly
  conservative under the full gate ladder).

Early-control observation (from in-flight q0 reps, not the final
distribution): N_S/N_X are 0/12 admissible at every retune **even under
purely linear synthetic labels**, and A_S is mostly inadmissible too
(0–4/12). The support blocking is therefore structural to shallow trees
on this panel — smooth z-scored state features partition time into
contiguous leaves spanning far fewer than 126 origins — not evidence
about the presence or absence of nonlinear signal. This strengthens the
interpretation of the headline verdict: the registered contract could
not evaluate the model class at all.

Correction logged (exposure event `controls_v2`): the first control
wave exposed an unpaired `rel_gain` (per-stream means over each
stream's own origins) and a declaration proxy that omitted the
registered coverage/stability/absolute gates — a q0 rep briefly
"declared" on a 46% artifact over 30/1467 origins. Both fixed and
verified (paired gain 1.8%, coverage gate rejects); declarations now
mirror the full 12.2 ladder.

## 5. Mechanism / fragility (P09)

Conditional contrasts N_S vs {A_S, Q_S, N_X}: all null (N_S has no
forecasts) and flagged `descriptive_only` — `results/mechanism_comparisons.json`.
The P09 gatekeeping rule holds: no affirmative conditional claim without
primary passes.

Frozen sensitivity set (`results/sensitivity_runs.json`):

- Leave-one-training-year-out and leave-one-region-out refits under the
  frozen selected configurations (no retuning, unchanged evaluation
  rows) — deltas recorded for every covered stream.
- Fixed 5/63-session outcome associations of the 20-session scores
  (diagnostic, no horizon-specific models): h5 IC ≈ +0.010 for
  L_S/L_X/L_star; h63 IC ≈ −0.006 / +0.006 / +0.006.
- 126-origin block inference: `results/stability.json`.
- One-source-session lag variant and the 20-seed network placebo are
  separate heavy rebuilds (P03/P05-level); manifests noted in
  `sensitivity_runs.json` and deferred — they cannot change the primary
  verdict under a zero-coverage N_S.

## 6. Gross portfolio (P10)

20-sleeve overlapping-cohort engine, daily TRI marks, fractional ties,
no exposure on constant scores, gross-only (`results/portfolio_gross.json`,
`nav_*.parquet`):

| stream | cohorts | skipped origins | gross Sharpe | total ret | maxDD |
|---|---|---|---|---|---|
| N_S | — | — | — | — | — | (no forecasts)
| L_S | 1317 | 170 | +0.08 | +2.3% | −5.9% |
| L_X | 1321 | 166 | +0.08 | +2.5% | −8.5% |
| L_star | 1322 | 165 | +0.07 | +2.3% | −8.5% |
| A_S | 589 | 58 | +0.01 | ~0.0% | −3.2% |
| B0 | 0 | 0 | 0.00 | 0.0% | 0.0% |

Reference diagnostics only — near-zero gross Sharpe on the covered
streams; no cost model applied (25bp law retired); no live or paper
orders; the native harness mapping is a documented qualification
blocker for a different contract (this study's PIT replay produces
scored forecasts, not signal registrations).

## 7. Uncertainty and limitations

- The registered leaf-support contract made the primary model
  unfit-for-purpose on this dataset; whether a *different* registered
  contract would admit it is a new ticket, not a post-hoc relaxation.
- Prior exposure declared: MacroState M_20260906_001–003, LLM-1M tabular
  arm, T2 IPCA. This is not fresh confirmation of any of them.
- Historical replay is not an untouched holdout merely because nested
  validation was used.

## 8. Reproduction

See `REPRODUCE.md`. All forecasts, fit records, selection decisions, and
leaf audits are preserved under
`Data/work/experiments/nonlinear_country_returns/p07_replay_real_v2/`
(v1 at `p07_replay_real/`).
