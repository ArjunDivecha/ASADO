# Results — Geopolitical alpha

**Methodology ledger:** `M_20260826_001`
**Overall verdict:** **INSUFFICIENT**

The exact Marko Papic constraint-minus-market probability test is not currently identified by
ASADO's historical data. The GPR tests below are explicitly proxy diagnostics.

| Gate | Result | Mean IC / improvement | NW t | Other |
|---|---:|---:|---:|---|
| 1. Lagged GPR predicts absolute next-month return | PASS | 0.0436 | 2.6188 | 317 months |
| 2. GPR x adverse-return predicts 3m reversal | FAIL | 0.0058 | 0.5078 | 315 months |
| 3a. Proxy features improve walk-forward rank IC | FAIL | -0.0118 | -1.8227 | positive years 0.3750 |
| 3b. Exact constraint-market gap is test-ready | INSUFFICIENT | — | — | 74 dates; 0 resolutions |

## Interpretation

- The panel contains 6,821 observations across 22 countries,
  from 2000-02-01 through 2026-07-01.
- Gate 1 tests risk prediction, not directional return alpha.
- Gate 2 is a frozen interaction proxy. It does not prove that a constraint forecast disagreed
  with the market; it only asks whether lagged GPR changes the usual adverse-return reversal.
- Gate 3a is expanding annual walk-forward and compares against returns-only controls. Gate 3b
  prevents that proxy from being relabeled as the exact Papic framework.
- Exact readiness failed because requirements were: {"historical_constraint_probability": false, "market_probability_dates_at_least_60": true, "resolved_markets_for_calibration": false}.

## Reproduction

Run `run.py` with the ASADO production interpreter. Input hashes are recorded in `summary.json`.
