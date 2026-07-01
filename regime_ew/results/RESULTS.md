# Per-Country Regime Early-Warning Test - Results

## Executive Verdict

**Overall:** **FAIL - stopped at Gate 3 own-country lead**

| Gate | Result | Headline | Threshold |
|---|---:|---|---|
| Gate 1: persistence | **PASS** | Median weighted 1m persistence 0.926; adverse-duration share 100.0% | >=0.75 and >=60% |
| Gate 2: volatility disguise | **clear** | Median abs corr with trailing 6m vol 0.152 | flag if >0.70 |
| Gate 3: own-country return lead | **FAIL** | dP_adverse: 17/34 negative, median rho -0.003; spread -0.682%/mo | >=23 negative, median <= -0.10, spread >= 0.50%/mo |

## Feature Set

The live warehouse did not expose a monthly-usable `GDELT*_CS` factor, so the PRD's fallback valuation/quality feature was used.

- `12-1MTR_CS`
- `REER_CS`
- `RSI14_CS`
- `Best PE _CS`
- `Inflation_CS`
- `Best ROE_CS`

## Leakage Discipline

- `1MRet` and `3MRet` are treated exactly as the prior `build_forward_returns` convention treats them: signal at month `t` pairs with forward return at month `t`.
- Per-country feature scaling is expanding-only with a 24-month minimum; no full-sample mean/std enters the walk-forward signal.
- Rows with more than two raw feature gaps are dropped; remaining one- or two-feature standardized gaps are neutral-imputed to zero after the one-month forward-fill attempt.
- HMMs are refit annually using only data before the prediction year.
- Adverse-state labels are ranked using training-window forward `1MRet` only.
- Full-sample HMM outputs are written as diagnostics only; gates read `ew_signals.parquet` walk-forward OOS rows.

## Interpretation

The states are stable enough to examine, but the early-warning probability does not lead own-country forward returns strongly enough. Treat this as a negative return-overlay result.

## Full-Sample Diagnostic

This is deliberately non-decisive because it uses full-sample HMM fits.

- Best diagnostic signal: `dP_adverse`
- Spread: 0.667%/mo

## Artifacts

- `regime_ew/results/manifest.json`
- `regime_ew/results/ew_signals.parquet`
- `regime_ew/results/ew_signals_full_sample.parquet`
- `regime_ew/results/gate1_persistence.parquet`
- `regime_ew/results/gate2_volatility.parquet`
- `regime_ew/results/gate3_lead.parquet`
- `regime_ew/results/gate4_robustness.parquet` if Gate 4 ran
- `regime_ew/results/hmm_params/*.json`
- `regime_ew/results/figures/*.pdf`
