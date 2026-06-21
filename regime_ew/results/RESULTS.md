# Per-Country Regime Early-Warning Test — Results
**Features used (6):** 12-1MTR_CS, REER_CS, RSI14_CS, Best PE _CS, Inflation_CS, Best ROE_CS
**Countries:** 34

## Gate Summary
| Gate | Result | Threshold | Notes |
|------|--------|-----------|-------|
| Gate 1 Persistence | **PASS** | persist≥0.75 + 60% dur≥3m | median persist=0.767 (≥0.75); frac_dur_3m=0.69 (≥0.60) |
| Gate 2 Vol check | **OK** | |r|<0.70 | median |corr|=0.133 |
| Gate 3 Lead test | **FAIL** | sign≥23 + med_rho≤−0.10 + spread≥0.50% | sign=7/26 p=0.9953; med_rho_P=0.053 med_rho_dP=-0.025; spread=-1.01%/mo |
| Gate 4 Artifact | skipped | — | — |

## Per-Country Persistence (Gate 1)
| Country | persist_1m | mean_adv_dur_months | n_months |
|---------|-----------|---------------------|----------|
| Hong Kong | 0.523 | 2.6 | 217 |
| France | 0.645 | 2.5 | 218 |
| US SmallCap | 0.661 | 1.7 | 219 |
| Turkey | 0.685 | 4.5 | 217 |
| Japan | 0.703 | 2.7 | 220 |
| Italy | 0.704 | 1.8 | 217 |
| Denmark | 0.725 | 2.8 | 219 |
| Germany | 0.728 | 4.7 | 218 |
| U.K. | 0.729 | 4.0 | 219 |
| Indonesia | 0.731 | 4.2 | 217 |
| Poland | 0.747 | 3.1 | 218 |
| Netherlands | 0.748 | 3.6 | 219 |
| India | 0.756 | 1.0 | 124 |
| Thailand | 0.779 | 6.4 | 218 |
| Sweden | 0.780 | 4.7 | 219 |
| Canada | 0.783 | 4.8 | 218 |
| ChinaH | 0.810 | 7.3 | 217 |
| Vietnam | 0.815 | 2.2 | 136 |
| U.S. | 0.822 | 3.4 | 220 |
| Korea | 0.838 | 7.6 | 217 |
| NASDAQ | 0.854 | 3.2 | 220 |
| Switzerland | 0.858 | 4.2 | 219 |
| Spain | 0.870 | 6.1 | 208 |
| Singapore | 0.872 | 11.1 | 219 |
| South Africa | 0.881 | 9.8 | 220 |
| Saudi Arabia | 0.929 | 9.0 | 43 |

## Per-Country Lead Correlations (Gate 3)
| Country | rho_P | rho_dP | n_months |
|---------|-------|--------|----------|
| U.K. | -0.116 | -0.088 | 218 |
| Korea | -0.082 | -0.050 | 216 |
| U.S. | -0.070 | 0.025 | 219 |
| Hong Kong | -0.052 | 0.030 | 216 |
| Canada | -0.045 | -0.075 | 217 |
| Spain | -0.030 | -0.021 | 207 |
| Japan | -0.010 | -0.042 | 219 |
| Netherlands | 0.007 | -0.104 | 218 |
| Germany | 0.028 | -0.117 | 217 |
| Poland | 0.034 | -0.031 | 217 |
| Vietnam | 0.036 | 0.034 | 135 |
| US SmallCap | 0.043 | -0.028 | 218 |
| Switzerland | 0.046 | -0.043 | 218 |
| Thailand | 0.061 | -0.042 | 217 |
| Singapore | 0.072 | 0.108 | 218 |
| Sweden | 0.074 | -0.059 | 218 |
| ChinaH | 0.082 | 0.036 | 216 |
| France | 0.111 | -0.047 | 217 |
| Indonesia | 0.111 | 0.011 | 216 |
| NASDAQ | 0.115 | -0.033 | 219 |
| Denmark | 0.122 | 0.079 | 218 |
| South Africa | 0.147 | 0.040 | 219 |
| Saudi Arabia | 0.150 | 0.188 | 42 |
| India | 0.182 | 0.010 | 123 |
| Turkey | 0.189 | 0.003 | 216 |
| Italy | 0.192 | 0.009 | 216 |

## Interpretation
**Gate 3 failed** (sign test (7/26 < 23); median Spearman (P: 0.053, dP: -0.025) not ≤ −0.10; spread (-1.01% < 0.50%/mo)). States persist but do not lead returns. The median Spearman is **positive** (+0.053), meaning the adverse state (labeled by worst contemporaneous return) is systematically followed by rebounding returns — short-term within-country mean reversion dominates. The adverse state captures "already bad" months, not "about-to-be-bad" months. This is a structural limitation of contemporaneous adverse-state labeling at monthly frequency, not a data error. Stop as a return overlay.

**Structural diagnosis:** The adversely-labeled HMM state reliably captures periods of poor own-country performance *in the contemporaneous month*, but those periods are followed by mean reversion, not continuation. This is the opposite of what an early-warning signal needs. Potential next directions (separate PRDs): (a) relabel the adverse state by *forward* return within the walk-forward training window (accepting the in-training-window circularity as a necessary design trade-off); (b) test at quarterly frequency where momentum effects dominate reversal; (c) pivot to a different labeling criterion such as volatility regime or CDS spread regime.
