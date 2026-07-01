# Contrarian Per-Country Regime Strategy Backtest

## Setup

- Signal: walk-forward OOS `P_adverse` from the per-country HMM regime test.
- Interpretation: contrarian; buy countries when the model says their adverse-regime probability is high.
- Return convention: monthly weights at date `t` are paired with ASADO `1MRet@t`, matching `build_forward_returns`.
- Costs: simple one-way bps times monthly absolute weight turnover.
- Sample: 2007-01-01 to 2026-04-01, 34 countries.

## Results

| strategy      | description                                    |   months | gross_total_return   | gross_ann_return   | gross_ann_vol   |   gross_sharpe | gross_max_drawdown   | net_10bps_ann_return   |   net_10bps_sharpe | net_25bps_ann_return   |   net_25bps_sharpe |   avg_turnover |   avg_gross_exposure |
|:--------------|:-----------------------------------------------|---------:|:---------------------|:-------------------|:----------------|---------------:|:---------------------|:-----------------------|-------------------:|:-----------------------|-------------------:|---------------:|---------------------:|
| TS_Q25_LS_P   | Time-series top/bottom quartile long-short     |      196 | 136.85%              | 5.42%              | 7.79%           |           0.72 | -11.05%              | 4.67%                  |               0.62 | 3.55%                  |               0.48 |           0.6  |                 2    |
| TS_Q25_LONG_P | Time-series top-quartile long-only             |      196 | 336.13%              | 9.44%              | 17.00%          |           0.62 | -26.37%              | 9.14%                  |               0.6  | 8.69%                  |               0.58 |           0.23 |                 1    |
| XS_Q25_LS_P   | Cross-sectional top/bottom quartile long-short |      213 | -40.60%              | -2.89%             | 12.19%          |          -0.18 | -59.15%              | -3.50%                 |              -0.23 | -4.40%                 |              -0.31 |           0.52 |                 1.86 |
| XS_Q20_LS_P   | Cross-sectional top/bottom quintile long-short |      213 | -38.64%              | -2.71%             | 13.74%          |          -0.13 | -61.71%              | -3.25%                 |              -0.17 | -4.05%                 |              -0.23 |           0.46 |                 1.75 |
| XS_Q25_LONG_P | Cross-sectional top-quartile long-only         |      184 | 92.91%               | 4.38%              | 16.81%          |           0.34 | -35.30%              | 4.09%                  |               0.32 | 3.66%                  |               0.3  |           0.23 |                 1    |
| EW_UNIVERSE   | Equal-weight available-country benchmark       |      232 | 193.66%              | 5.73%              | 18.14%          |           0.4  | -58.09%              | 5.71%                  |               0.4  | 5.69%                  |               0.4  |           0.01 |                 1    |

## Read

The cleanest production-shaped version is the time-series quartile long/short (`TS_Q25_LS_P`): it compares each country's `P_adverse` to its own prior 24-month history before trading. The cross-sectional variants are useful diagnostics, but less conceptually clean because HMM posterior probabilities are fitted separately by country.

## Artifacts

- `strategy_manifest.json`
- `strategy_summary.csv`
- `strategy_returns.parquet`
- `weights_*.parquet` and `returns_*.parquet`
- `figures/cumulative_returns.pdf`
