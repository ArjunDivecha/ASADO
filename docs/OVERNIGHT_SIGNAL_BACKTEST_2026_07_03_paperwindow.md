# Overnight PM → Equity Signal — Backtest 2026_07_03

Open window: 12:30-15:30 UTC (paper). Pairs: 7507 market-nights, 2353 contracts, 18 tickers, 2026-06-04 → 2026-07-01.

## Gate 1 — event study (contract FE)

| spec                                 | cluster   | fe    |       gamma |    t_stat |          r2 |    n |   n_contracts |
|:-------------------------------------|:----------|:------|------------:|----------:|------------:|-----:|--------------:|
| all contracts                        | contract  | True  |  0.0267476  |  9.16948  | 0.0247745   | 7507 |          2353 |
| all contracts                        | day       | True  |  0.0267476  |  3.13114  | 0.0247745   | 7507 |          2353 |
| all contracts (pooled, no FE)        | contract  | False |  0.0293664  | 13.8271   | 0.0381783   | 7507 |          2353 |
| all contracts (pooled, no FE)        | day       | False |  0.0293664  |  3.15075  | 0.0381783   | 7507 |          2353 |
| class: close_above_daily (ticker FE) | contract  | True  |  0.0218163  |  8.67911  | 0.0989611   |  699 |           698 |
| class: close_above_daily (ticker FE) | day       | True  |  0.0218163  |  4.21858  | 0.0989611   |  699 |           698 |
| class: close_above_period            | contract  | True  |  0.0144183  |  4.73305  | 0.00737434  | 2025 |           140 |
| class: close_above_period            | day       | True  |  0.0144183  |  1.71562  | 0.00737434  | 2025 |           140 |
| class: finish_week_above             | contract  | True  |  0.020175   |  4.08913  | 0.0116814   | 1386 |           415 |
| class: finish_week_above             | day       | True  |  0.020175   |  1.64858  | 0.0116814   | 1386 |           415 |
| class: hit_high                      | contract  | True  |  0.0318413  |  3.05654  | 0.0340767   | 1451 |           380 |
| class: hit_high                      | day       | True  |  0.0318413  |  1.43097  | 0.0340767   | 1451 |           380 |
| class: hit_low                       | contract  | True  |  0.0512118  |  7.24421  | 0.112071    | 1638 |           412 |
| class: hit_low                       | day       | True  |  0.0512118  |  4.4094   | 0.112071    | 1638 |           412 |
| class: up_or_down (ticker FE)        | contract  | True  |  0.0851115  | 10.98     | 0.400159    |  308 |           308 |
| class: up_or_down (ticker FE)        | day       | True  |  0.0851115  |  9.73053  | 0.400159    |  308 |           308 |
| daily classes combined (ticker FE)   | contract  | True  |  0.0420977  | 11.7095   | 0.195695    | 1007 |          1006 |
| daily classes combined (ticker FE)   | day       | True  |  0.0420977  |  5.91894  | 0.195695    | 1007 |          1006 |
| single names only                    | contract  | True  |  0.0247649  |  8.67521  | 0.0218184   | 6966 |          2099 |
| single names only                    | day       | True  |  0.0247649  |  3.08086  | 0.0218184   | 6966 |          2099 |
| ex-weekend                           | contract  | True  |  0.0439235  |  7.48848  | 0.0371662   | 5895 |          2055 |
| ex-weekend                           | day       | True  |  0.0439235  |  2.65751  | 0.0371662   | 5895 |          2055 |
| PLACEBO: next-night gap              | contract  | True  | -0.00259143 | -0.886524 | 0.000229427 | 5154 |          1100 |
| PLACEBO: next-night gap              | day       | True  | -0.00259143 | -0.48364  | 0.000229427 | 5154 |          1100 |

## Gate 2 — realizable PnL grid

| leg                      |   theta |   cost_bps_oneway |   ann_return |    sharpe |   max_drawdown |   hit_rate |   n_trades |   avg_positions_per_day |
|:-------------------------|--------:|------------------:|-------------:|----------:|---------------:|-----------:|-----------:|------------------------:|
| gap (diagnostic)         |    0    |                 0 |    2.52469   | 17.2316   |    -0.00705638 |   0.947368 |        327 |                17.2105  |
| gap (diagnostic)         |    0    |                 2 |    2.42389   | 16.5436   |    -0.00745638 |   0.947368 |        327 |                17.2105  |
| gap (diagnostic)         |    0    |                 5 |    2.27269   | 15.5117   |    -0.00805638 |   0.947368 |        327 |                17.2105  |
| gap (diagnostic)         |    0    |                10 |    2.02069   | 13.7917   |    -0.00905638 |   0.894737 |        327 |                17.2105  |
| open->close (realizable) |    0    |                 0 |    0.236808  |  1.37428  |    -0.0198506  |   0.473684 |        327 |                17.2105  |
| open->close (realizable) |    0    |                 2 |    0.136008  |  0.789305 |    -0.0206425  |   0.473684 |        327 |                17.2105  |
| open->close (realizable) |    0    |                 5 |   -0.0151917 | -0.088163 |    -0.0253694  |   0.473684 |        327 |                17.2105  |
| open->close (realizable) |    0    |                10 |   -0.267192  | -1.55061  |    -0.0377037  |   0.421053 |        327 |                17.2105  |
| gap (diagnostic)         |    0.01 |                 0 |    2.74786   | 18.1404   |    -0.00923216 |   0.947368 |        259 |                13.6316  |
| gap (diagnostic)         |    0.01 |                 2 |    2.64706   | 17.4749   |    -0.00963216 |   0.947368 |        259 |                13.6316  |
| gap (diagnostic)         |    0.01 |                 5 |    2.49586   | 16.4767   |    -0.0102322  |   0.947368 |        259 |                13.6316  |
| gap (diagnostic)         |    0.01 |                10 |    2.24386   | 14.8131   |    -0.0112322  |   0.947368 |        259 |                13.6316  |
| open->close (realizable) |    0.01 |                 0 |   -0.348199  | -1.86426  |    -0.0410622  |   0.368421 |        259 |                13.6316  |
| open->close (realizable) |    0.01 |                 2 |   -0.448999  | -2.40395  |    -0.0441428  |   0.368421 |        259 |                13.6316  |
| open->close (realizable) |    0.01 |                 5 |   -0.600199  | -3.21348  |    -0.0507134  |   0.368421 |        259 |                13.6316  |
| open->close (realizable) |    0.01 |                10 |   -0.852199  | -4.56269  |    -0.0675568  |   0.368421 |        259 |                13.6316  |
| gap (diagnostic)         |    0.03 |                 0 |    3.38519   | 18.9487   |    -0.00948955 |   0.947368 |        175 |                 9.21053 |
| gap (diagnostic)         |    0.03 |                 2 |    3.28439   | 18.3845   |    -0.00988955 |   0.947368 |        175 |                 9.21053 |
| gap (diagnostic)         |    0.03 |                 5 |    3.13319   | 17.5381   |    -0.0104896  |   0.947368 |        175 |                 9.21053 |
| gap (diagnostic)         |    0.03 |                10 |    2.88119   | 16.1275   |    -0.0114896  |   0.894737 |        175 |                 9.21053 |
| open->close (realizable) |    0.03 |                 0 |    0.023682  |  0.102788 |    -0.0477488  |   0.631579 |        175 |                 9.21053 |
| open->close (realizable) |    0.03 |                 2 |   -0.077118  | -0.334716 |    -0.0523287  |   0.631579 |        175 |                 9.21053 |
| open->close (realizable) |    0.03 |                 5 |   -0.228318  | -0.990972 |    -0.0591608  |   0.631579 |        175 |                 9.21053 |
| open->close (realizable) |    0.03 |                10 |   -0.480318  | -2.08473  |    -0.0704473  |   0.631579 |        175 |                 9.21053 |
| gap (diagnostic)         |    0.05 |                 0 |    4.60304   | 19.1954   |    -0.00746488 |   0.947368 |        112 |                 5.89474 |
| gap (diagnostic)         |    0.05 |                 2 |    4.50224   | 18.7751   |    -0.00786488 |   0.947368 |        112 |                 5.89474 |
| gap (diagnostic)         |    0.05 |                 5 |    4.35104   | 18.1446   |    -0.00846488 |   0.842105 |        112 |                 5.89474 |
| gap (diagnostic)         |    0.05 |                10 |    4.09904   | 17.0937   |    -0.00946488 |   0.842105 |        112 |                 5.89474 |
| open->close (realizable) |    0.05 |                 0 |    0.200863  |  0.718267 |    -0.0503367  |   0.684211 |        112 |                 5.89474 |
| open->close (realizable) |    0.05 |                 2 |    0.100063  |  0.357816 |    -0.0511162  |   0.684211 |        112 |                 5.89474 |
| open->close (realizable) |    0.05 |                 5 |   -0.0511367 | -0.18286  |    -0.0522849  |   0.684211 |        112 |                 5.89474 |
| open->close (realizable) |    0.05 |                10 |   -0.303137  | -1.08399  |    -0.0605356  |   0.684211 |        112 |                 5.89474 |

Generated by scripts/backtest_overnight_signal.py