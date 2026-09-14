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

**Verdict: `INCOMPLETE_REGISTERED_PROCEDURE`.**

The primary candidate N_S (depth-2 histogram boosting on S) and N_X
produced **zero outer forecasts**: at every one of the 7 annual retunes,
all 12 tree configurations failed the registered terminal-leaf support
audit (≥126 distinct origins, ≥12 fixed-20-origin bins, ≥3 calendar
years, ≥4 markets per leaf) in at least one inner fit, and/or failed the
audit at the outer refit. A_S (depth-1, 2 leaves) was selected at some
retunes but additionally failed support at ~10 of 25 outer refits.

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

[in progress — 500 replays under frozen pseudo-label generator;
`Data/work/experiments/nonlinear_country_returns/p07_controls/`]

## 5. Mechanism / fragility (P09)

[conditional contrasts are descriptive-only under an incomplete primary;
sensitivity set manifests in `results/`]

## 6. Gross portfolio (P10)

[gross reference portfolio on covered streams only; N_S has no
expression; see `results/portfolio_gross.json`]

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
