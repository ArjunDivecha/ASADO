# Pre-registration — Geopolitical alpha

Written 2026-08-26 before executing any statistical test in this experiment.

## Hypothesis

Geopolitical information should add value only when it changes a constrained actor's feasible
set faster than market prices absorb that change. A lagged country geopolitical-risk measure
should therefore predict risk before returns, and extreme adverse price reactions should reverse
only when the constraint evidence does not validate the market move. A true constraint-minus-
market probability gap should improve country-return rankings beyond own-price controls.

## Frozen tests

1. **Risk test.** Use country GPR observed in month `t-1` to predict absolute country return in
   month `t`. Primary statistic: monthly cross-sectional Spearman IC and Newey-West t-statistic
   with six lags. Pass requires mean IC > 0 and NW-t >= 2.0. The honest universe is the
   intersection of T2 returns and countries with country-specific GPR history.
2. **Reversal test.** At the end of month `t`, combine lagged GPR with the adverse country return
   realized during `t`. The frozen continuous signal is `GPR_CS * (-RETURN_1M_CS)` and the primary
   outcome is compounded return over `t+1..t+3`. Pass requires positive mean monthly rank IC and
   NW-t >= 2.0. An extreme-event spread is diagnostic only.
3. **Incremental-alpha test.** In expanding annual walk-forward folds, compare a returns-only
   model (`RETURN_1M_CS`, `MOM12_CS`) with an augmented model adding `GPR_CS` and the frozen
   interaction above. Pass requires positive mean monthly IC improvement, NW-t >= 2.0, and
   positive improvement in at least 60% of test years. Separately audit whether ASADO can run the
   exact Papic test: historical constraint probabilities, contemporaneous market probabilities,
   at least 60 aligned dates, and resolved markets for calibration. Missing any requirement makes
   the exact arm `INSUFFICIENT`, not a proxy pass.

## Interpretation rules

- GPR is a proxy for geopolitical attention/risk, not Marko Papic's constraint probability.
- The historical tests are descriptive methodology tests and cannot graduate the exact framework.
- No transaction-cost gate is applied; all return diagnostics are gross.
- Any positive searched result is non-promotable until independently preregistered and rerun
  through the production harness on a PIT-certified signal surface.
