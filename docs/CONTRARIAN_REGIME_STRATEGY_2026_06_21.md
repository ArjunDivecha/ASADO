# Contrarian Regime Strategy Report

Date: 2026-06-21

## TLDR

The contrarian version is usable as a research strategy, but only in the **time-series calibrated** form.

Best version tested:

- Strategy: `TS_Q25_LS_P`
- Rule: each month, go long countries whose walk-forward `P_adverse` is in the top quartile versus that country's own prior 24-month history; short countries in the bottom quartile.
- Sample: 2010-01 to 2026-04, monthly.
- Gross return: **+136.9% total**, **+5.4% annualized**
- Gross vol: **7.8%**
- Gross Sharpe: **0.72**
- Max drawdown: **-11.1%**
- Net at 10 bps one-way turnover cost: **+4.7% annualized**, **0.62 Sharpe**
- Net at 25 bps: **+3.5% annualized**, **0.48 Sharpe**

Long-only high-adverse version also worked:

- Strategy: `TS_Q25_LONG_P`
- Gross return: **+336.1% total**, **+9.4% annualized**
- Gross Sharpe: **0.62**
- Max drawdown: **-26.4%**
- Same-date equal-weight benchmark: **+7.35% annualized**, **0.53 Sharpe**
- Long-only excess vs benchmark: about **+2.0% annualized**, **0.42 Sharpe**

## Important Warning

Do **not** rank raw `P_adverse` cross-sectionally across countries. That version lost money:

- `XS_Q25_LS_P`: **-2.9% annualized**, **-0.18 Sharpe**
- `XS_Q20_LS_P`: **-2.7% annualized**, **-0.13 Sharpe**

The reason is conceptual: each country's HMM posterior is fitted independently, so raw posterior levels are not safely comparable across countries. The signal works better when each country is compared to its own prior `P_adverse` distribution.

## Return Table

| Strategy | Description | Gross total | Gross ann. | Gross vol | Gross Sharpe | Max DD | Net 10 bps ann. | Net 25 bps ann. |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `TS_Q25_LS_P` | Own-history top/bottom quartile long-short | 136.9% | 5.4% | 7.8% | 0.72 | -11.1% | 4.7% | 3.5% |
| `TS_Q25_LONG_P` | Own-history top-quartile long-only | 336.1% | 9.4% | 17.0% | 0.62 | -26.4% | 9.1% | 8.7% |
| `XS_Q25_LS_P` | Cross-sectional top/bottom quartile long-short | -40.6% | -2.9% | 12.2% | -0.18 | -59.1% | -3.5% | -4.4% |
| `XS_Q20_LS_P` | Cross-sectional top/bottom quintile long-short | -38.6% | -2.7% | 13.7% | -0.13 | -61.7% | -3.3% | -4.0% |
| `EW_UNIVERSE` | Equal-weight available country benchmark | 193.7% | 5.7% | 18.1% | 0.40 | -58.1% | 5.7% | 5.7% |

## Annual Returns: `TS_Q25_LS_P`

| Year | Gross return |
|---:|---:|
| 2010 | 2.2% |
| 2011 | -8.2% |
| 2012 | -0.2% |
| 2013 | 2.8% |
| 2014 | 1.3% |
| 2015 | 2.4% |
| 2016 | 14.2% |
| 2017 | 17.6% |
| 2018 | 2.8% |
| 2019 | 4.2% |
| 2020 | 11.3% |
| 2021 | 10.7% |
| 2022 | 19.2% |
| 2023 | -2.4% |
| 2024 | 8.2% |
| 2025 | 8.0% |
| 2026 YTD | -1.6% |

## Interpretation

This looks like a **country rebound / bad-news-priced-in overlay**, not an early-warning risk-off system.

The most production-shaped candidate is `TS_Q25_LS_P`: it is market-neutral-ish, has lower drawdown than the country benchmark, survives simple turnover costs, and does not require comparing separately fitted HMM posterior levels across countries.

The long-only version is useful if the desired implementation is country ETF rotation rather than a dollar-neutral book. It beat the aligned equal-weight benchmark by about 2% annualized gross, but with equity-market beta still present.

## Artifacts

- Full strategy report: <file:///Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_ew/results/contrarian_strategy/STRATEGY_RESULTS.md>
- Summary CSV: <file:///Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_ew/results/contrarian_strategy/strategy_summary.csv>
- Monthly returns: <file:///Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_ew/results/contrarian_strategy/strategy_returns.parquet>
- Cumulative chart: <file:///Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_ew/results/contrarian_strategy/figures/cumulative_returns.pdf>

Raw paths:

- `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_ew/results/contrarian_strategy/STRATEGY_RESULTS.md`
- `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_ew/results/contrarian_strategy/strategy_summary.csv`
- `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_ew/results/contrarian_strategy/strategy_returns.parquet`

