# Overnight PM → Equity Signal — Backtest 2026_07_03

Open window: pre-13:30 UTC (tradeable). Pairs: 7417 market-nights, 2334 contracts, 18 tickers, 2026-06-04 → 2026-07-01.

## Gate 1 — event study (contract FE)

| spec                                 | cluster   | fe    |       gamma |    t_stat |          r2 |    n |   n_contracts |
|:-------------------------------------|:----------|:------|------------:|----------:|------------:|-----:|--------------:|
| all contracts                        | contract  | True  |  0.0269263  |  9.14735  | 0.0249463   | 7417 |          2334 |
| all contracts                        | day       | True  |  0.0269263  |  3.12079  | 0.0249463   | 7417 |          2334 |
| all contracts (pooled, no FE)        | contract  | False |  0.0295018  | 13.8196   | 0.0384283   | 7417 |          2334 |
| all contracts (pooled, no FE)        | day       | False |  0.0295018  |  3.1409   | 0.0384283   | 7417 |          2334 |
| class: close_above_daily (ticker FE) | contract  | True  |  0.022071   |  8.70396  | 0.100825    |  685 |           684 |
| class: close_above_daily (ticker FE) | day       | True  |  0.022071   |  4.25652  | 0.100825    |  685 |           684 |
| class: close_above_period            | contract  | True  |  0.014293   |  4.62773  | 0.00714913  | 2016 |           140 |
| class: close_above_period            | day       | True  |  0.014293   |  1.66446  | 0.00714913  | 2016 |           140 |
| class: finish_week_above             | contract  | True  |  0.0204292  |  4.11293  | 0.0119219   | 1368 |           411 |
| class: finish_week_above             | day       | True  |  0.0204292  |  1.65687  | 0.0119219   | 1368 |           411 |
| class: hit_high                      | contract  | True  |  0.0320866  |  3.06938  | 0.0348053   | 1423 |           380 |
| class: hit_high                      | day       | True  |  0.0320866  |  1.44548  | 0.0348053   | 1423 |           380 |
| class: hit_low                       | contract  | True  |  0.0517799  |  7.27566  | 0.114048    | 1617 |           411 |
| class: hit_low                       | day       | True  |  0.0517799  |  4.42816  | 0.114048    | 1617 |           411 |
| class: up_or_down (ticker FE)        | contract  | True  |  0.0851115  | 10.98     | 0.400159    |  308 |           308 |
| class: up_or_down (ticker FE)        | day       | True  |  0.0851115  |  9.73053  | 0.400159    |  308 |           308 |
| daily classes combined (ticker FE)   | contract  | True  |  0.042448   | 11.7444   | 0.197845    |  993 |           992 |
| daily classes combined (ticker FE)   | day       | True  |  0.042448   |  6.00282  | 0.197845    |  993 |           992 |
| single names only                    | contract  | True  |  0.0249273  |  8.65009  | 0.0219599   | 6887 |          2088 |
| single names only                    | day       | True  |  0.0249273  |  3.06927  | 0.0219599   | 6887 |          2088 |
| ex-weekend                           | contract  | True  |  0.0442579  |  7.45178  | 0.0374333   | 5818 |          2036 |
| ex-weekend                           | day       | True  |  0.0442579  |  2.64424  | 0.0374333   | 5818 |          2036 |
| PLACEBO: next-night gap              | contract  | True  | -0.00246977 | -0.833105 | 0.000205975 | 5083 |          1096 |
| PLACEBO: next-night gap              | day       | True  | -0.00246977 | -0.458534 | 0.000205975 | 5083 |          1096 |

## Gate 2 — realizable PnL grid

| leg                      |   theta |   cost_bps_oneway |   ann_return |     sharpe |   max_drawdown |   hit_rate |   n_trades |   avg_positions_per_day |
|:-------------------------|--------:|------------------:|-------------:|-----------:|---------------:|-----------:|-----------:|------------------------:|
| gap (diagnostic)         |    0    |                 0 |    2.48988   | 17.1091    |    -0.00705638 |   0.947368 |        327 |                17.2105  |
| gap (diagnostic)         |    0    |                 2 |    2.38908   | 16.4164    |    -0.00745638 |   0.947368 |        327 |                17.2105  |
| gap (diagnostic)         |    0    |                 5 |    2.23788   | 15.3775    |    -0.00805638 |   0.947368 |        327 |                17.2105  |
| gap (diagnostic)         |    0    |                10 |    1.98588   | 13.6459    |    -0.00905638 |   0.894737 |        327 |                17.2105  |
| open->close (realizable) |    0    |                 0 |    0.0388391 |  0.23474   |    -0.0269809  |   0.421053 |        327 |                17.2105  |
| open->close (realizable) |    0    |                 2 |   -0.0619609 | -0.374486  |    -0.0316518  |   0.421053 |        327 |                17.2105  |
| open->close (realizable) |    0    |                 5 |   -0.213161  | -1.28832   |    -0.0386197  |   0.421053 |        327 |                17.2105  |
| open->close (realizable) |    0    |                10 |   -0.465161  | -2.81139   |    -0.051903   |   0.368421 |        327 |                17.2105  |
| gap (diagnostic)         |    0.01 |                 0 |    2.71077   | 18.4732    |    -0.00827608 |   0.947368 |        262 |                13.7895  |
| gap (diagnostic)         |    0.01 |                 2 |    2.60997   | 17.7862    |    -0.00867608 |   0.947368 |        262 |                13.7895  |
| gap (diagnostic)         |    0.01 |                 5 |    2.45877   | 16.7558    |    -0.00927608 |   0.947368 |        262 |                13.7895  |
| gap (diagnostic)         |    0.01 |                10 |    2.20677   | 15.0385    |    -0.0102761  |   0.947368 |        262 |                13.7895  |
| open->close (realizable) |    0.01 |                 0 |   -0.387086  | -2.12631   |    -0.040049   |   0.421053 |        262 |                13.7895  |
| open->close (realizable) |    0.01 |                 2 |   -0.487886  | -2.68002   |    -0.0454266  |   0.421053 |        262 |                13.7895  |
| open->close (realizable) |    0.01 |                 5 |   -0.639086  | -3.51058   |    -0.0534405  |   0.368421 |        262 |                13.7895  |
| open->close (realizable) |    0.01 |                10 |   -0.891086  | -4.89485   |    -0.0702381  |   0.368421 |        262 |                13.7895  |
| gap (diagnostic)         |    0.03 |                 0 |    3.37845   | 18.8983    |    -0.00948955 |   0.947368 |        177 |                 9.31579 |
| gap (diagnostic)         |    0.03 |                 2 |    3.27765   | 18.3345    |    -0.00988955 |   0.947368 |        177 |                 9.31579 |
| gap (diagnostic)         |    0.03 |                 5 |    3.12645   | 17.4887    |    -0.0104896  |   0.947368 |        177 |                 9.31579 |
| gap (diagnostic)         |    0.03 |                10 |    2.87445   | 16.079     |    -0.0114896  |   0.894737 |        177 |                 9.31579 |
| open->close (realizable) |    0.03 |                 0 |   -0.1474    | -0.632051  |    -0.0477488  |   0.578947 |        177 |                 9.31579 |
| open->close (realizable) |    0.03 |                 2 |   -0.2482    | -1.06428   |    -0.0523287  |   0.578947 |        177 |                 9.31579 |
| open->close (realizable) |    0.03 |                 5 |   -0.3994    | -1.71263   |    -0.0591608  |   0.578947 |        177 |                 9.31579 |
| open->close (realizable) |    0.03 |                10 |   -0.6514    | -2.7932    |    -0.0704473  |   0.578947 |        177 |                 9.31579 |
| gap (diagnostic)         |    0.05 |                 0 |    4.54457   | 19.1446    |    -0.00746488 |   0.947368 |        115 |                 6.05263 |
| gap (diagnostic)         |    0.05 |                 2 |    4.44377   | 18.72      |    -0.00786488 |   0.947368 |        115 |                 6.05263 |
| gap (diagnostic)         |    0.05 |                 5 |    4.29257   | 18.083     |    -0.00846488 |   0.842105 |        115 |                 6.05263 |
| gap (diagnostic)         |    0.05 |                10 |    4.04057   | 17.0214    |    -0.00946488 |   0.842105 |        115 |                 6.05263 |
| open->close (realizable) |    0.05 |                 0 |    0.0849382 |  0.305014  |    -0.0503367  |   0.631579 |        115 |                 6.05263 |
| open->close (realizable) |    0.05 |                 2 |   -0.0158618 | -0.0569598 |    -0.0511162  |   0.631579 |        115 |                 6.05263 |
| open->close (realizable) |    0.05 |                 5 |   -0.167062  | -0.59992   |    -0.0522849  |   0.631579 |        115 |                 6.05263 |
| open->close (realizable) |    0.05 |                10 |   -0.419062  | -1.50485   |    -0.0600225  |   0.631579 |        115 |                 6.05263 |

Generated by scripts/backtest_overnight_signal.py