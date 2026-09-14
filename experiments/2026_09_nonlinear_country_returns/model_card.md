# Model Card — N_S nonlinear country-return forecaster (registered study)

**Registration:** methodology ledger `M_20260913_001`, protocol
`governance/protocol.lock.json` (code commit `fa7e51d`).

## Intended use

Research-only evaluation of whether a pooled depth-2 histogram-boosted
model on a fixed 15-input economic state representation predicts
20-local-session USD total returns better than tuned ridge baselines on
the same point-in-time-safe sample. **Not for production use, not a
trading signal, no allocation authority.**

## Target / universe / horizon

- Label: 20-local-session forward USD TRI return, entry = first local
  session strictly after the 23:59 UTC origin, exit = 20th subsequent
  local session.
- Universe (AM-1): 22 markets with complete-case primitive coverage;
  ≥20 eligible markets required per origin.
- Scored axis: 1,467 eligible whole-mature origins, 2020-07-01 →
  2026-08-12.

## Inputs

21 audited primitives (own/trade-neighbor returns, FX options 1W IV +
carry + 1M RR, sovereign 2Y/10Y/CDS, consensus GDP/CPI revision path
features, policy rate, global VIX/MOVE/DXY/Brent), compressed to the
15-input S map in `config/study.v2.json`. All PIT-safe per P01 audit.

## Training

8-year rolling window, quarterly refits, annual July retunes with
4×6-month inner blocks, 63-origin moving-block one-SE parsimony,
63-origin/1000-draw bootstrap inference, Holm over 3 primary tests.
sklearn 1.8.0 `HistGradientBoostingRegressor`, `learning_rate=0.03`,
`max_bins=16`, depth ≤2, ≤4 leaves, `early_stopping=False`,
`random_state=20260913`.

## Registered failure modes

- **Terminal-leaf support audit** (≥126 origins / ≥12 20-origin bins /
  ≥3 years / ≥4 markets per leaf) — the model is *blocked* when any leaf
  fails; this fired on every real outer fit (the dataset's episode
  structure defeats shallow-tree admissibility). A blocked fit must be
  reported, never substituted.
- Effective DM-tilted universe (no US complex as outcome, no 3M FX
  options); 2024-26 reversal regime concentrated in a few episodes;
  overlapping labels induce strong serial dependence (handled by block
  bootstrap, not assumed away).

## Prior exposure

MacroState M_20260906_001–003 (monthly/12M cousin contract, WATCH),
LLM-1M tabular HGB arm, T2 IPCA pooled model. This study is a different
contract and is not fresh confirmation of any of them.

## Prohibited uses

Any live or paper order, portfolio allocation, scheduler integration, or
production scoring. Prospective shadow operation (P12) is disabled by
default and requires separate explicit owner approval.
