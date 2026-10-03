# MacroState: bounded primary-source audit

Audit date: 2026-09-05. Both complete PDFs downloaded from their official hosts and text-extracted; Popescu Table 11 was also visually inspected. No replication, forecasting experiment, new data collection, or production database access was performed. Local PDF copies are temporary research material, not redistributed in this report.

## Closest country-index precedent

[Popescu (2020), dissertation chapter 1, official PDF](https://repository.tilburguniversity.edu/server/api/core/bitstreams/6e89c86d-d6df-47b4-a5e0-aa94dbaa5558/content).

Verified source summary (printed pages 27-35, 44-50, 67): 16 developed markets, February 1980-September 2018; monthly local-currency total returns less local short rates, one-month holding. Industrial production uses OECD release vintages, six-month lag; OOS HP output gaps are re-estimated quarterly using then-available data. Credit gaps receive twelve-month lags; comprehensive vintage treatment elsewhere remains unverified. Chronological 70/10/20 splitting is described, but annual expansion, monthly expansion, last-ten-year testing, and once-only fitting statements leave the exact operational split/refit protocol unresolved. PCR/PLS use four components. Networks use 32, 32/16, or 32/16/8 nodes; Appendix D lists penalty/learning-rate/patience grids and dropout. Macro NN2 reports OOS R-squared 4.98% versus PCR 4.12%; their pairwise statistic is 1.55, not significant at 5%. NN2 macro long-short monthly return is 1.32%, monthly Sharpe 0.53. The Fama-MacBeth comparator uses fewer inputs; no comparable all-macro FM fit is reported.

**Implications for MacroState (our assessment).** This is sufficiently close prior art to reject a novelty claim for macro-based country-return machine learning. It supports investigating nonlinear conditional relationships, but the incremental comparison must be against a well-regularized information-equivalent model. Beating an unstable regression does not identify whether improvement came from nonlinearities, shrinkage, or differing predictors. A convincing nonlinear advantage requires a paired test against the strongest eligible linear alternative.

Do not assert an HP lookahead error here: the inspected method explicitly attempts causal output-gap construction. Conversely, a methodological assurance is not a reconstructed vintage audit of every input. MacroState must independently implement and test its observation clock. Its USD benchmark-relative annual target also changes both the economic question and the dependence structure. Annual overlapping labels require their own purging and uncertainty treatment. The dissertation's performance is motivation for a test, not an expected return or sample-size calibration for ASADO.

## Counterargument to mandatory simplicity

[Kelly, Malamud and Zhou, NBER 30217, October 2022 revision, official PDF](https://www.nber.org/system/files/working_papers/w30217/w30217.pdf).

Verified source summary (printed pages 8-11, 37-47): the theory studies regularized high-dimensional prediction under specified coefficient/signal assumptions; the empirical test forecasts monthly aggregate US market returns. Fifteen existing predictors become random Fourier features, up to 12,000, with rolling 12/60/120-month training windows. Underlying history is 1926-2020; standardization requires initial history, leaving an analysis sample beginning 1930. OOS statistics average 1,000 random-feature draws. Table 1 compares heavy-ridge linear and nonlinear versions: with 120-month training, Sharpe is 0.49 linear versus 0.41 nonlinear, while nonlinear's information ratio against linear is 0.24 (alpha t=2.2). Thus its reported incremental contribution and standalone Sharpe ranking differ. This is a working-paper revision, not an audit of the later published version.

**Implications for MacroState (our assessment).** Parameter count alone cannot settle the architecture choice. A fixed rich feature map and strong shrinkage may have lower variance than a smaller, unstable fitted model. Permit one bounded nonlinear comparison after data/evaluator validation even if standalone concepts have weak marginal signals. Do not equate this permission with unlimited architecture search or a guarantee that more complexity helps.

Freeze the objective before inspecting results: cross-sectional rank skill, gross active portfolio performance, and incremental contribution are related but distinct measurements. A model can add diversifying information without having the best standalone Sharpe; the chosen success criterion must resolve that case in advance. Compare identical primitives, observations, target, preprocessing clocks and tuning opportunities, and charge alternatives to the research family. The practical question is whether economic structure supplies useful constraints beyond generic regularization, not whether nonlinear forecasting is theoretically possible.

## Items still requiring independent reconstruction

- Exact Popescu training/validation/test calendar, refit schedule, and the implementation of hyperparameter selection cannot be recovered unambiguously from the inspected prose alone.
- Complete historical revision provenance for all Popescu predictors was not established; absence of disclosure here is not proof of leakage.
- Neither paper was reproduced on its original data, nor tested on ASADO. Neither establishes 12-month USD country-relative forecasting performance.
- Source scope was deliberately capped at these two official PDFs; no secondary performance claims were adopted.
