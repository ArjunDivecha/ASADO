# 2026_10_rank_model — country top-8 ranking model

**Question.** Can a model trained on the monthly cross-sectional factor z-scores pick
the top 8 of 34 countries (equal-weighted, against the equal-weight average) better
than chance? First step: Arjun hand-picks a de-duplicated factor set, so this
directory starts with the factor correlation matrix.

**Data snapshot.** `feature_panel_observed` frozen 2026-10-07 by
`scripts/snapshot_for_experiment.py` to
`/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/snapshot_2026_10_07/feature_panel_observed.parquet`
(3,258,033 rows, 34 T2 countries, forecasts excluded). No script here opens the
live DuckDB.

## Step 1 — factor correlation matrix (2026-10-07)

`factor_correlation.py` → `results/corr_<timestamp>/` (latest run wins; v1.0 was
`_CS` only, v1.1 adds `_TS`)

- Variables: every `_CS` (within-month cross-sectional z-score) and `_TS`
  (within-country time-series z-score) whose catalog frequency is not quarterly or
  annual: **341 of 475** — 161 CS + 180 TS. 154 base factors have both variants,
  26 are TS-only (3 global GPR series, 22 single-currency ECB FX series, one
  Bloomberg debt ratio), 7 are CS-only. The 134 quarterly/annual series are listed in
  the `Variables` sheet as excluded and can be added.
- Method: pooled Pearson over (date, country) rows, pairwise-complete, minimum 200
  overlapping observations (≈ 6 months × 34). For `_CS` (zero mean each month) this
  is the average within-month cross-sectional correlation. For `_TS` it also carries
  the common global swing (every country's rate z fell together in 2020), which is
  what a per-country-month model sees as feature redundancy.
- Order: average-linkage clustering on 1 − |ρ|; `Clusters` sheet cuts at |ρ| ≥ 0.9
  and ≥ 0.8. `CS_vs_TS` sheet: each base factor's correlation between its two
  variants.

Headline (v1.1): 673 pairs at |ρ| ≥ 0.7 across 50,644 defined pairs. CS and TS of
the same factor are genuinely different views for almost everything — median |ρ|
between them is 0.37 and only 19 of 151 exceed 0.8, all of them GDELT (the news
series are pre-standardized, so both normalizations land in the same place). The
duplication within each normalization is the same four families: GDELT news (46
series per variant collapse to roughly 8), interest rates (12 yields/policy rates in
one block), "size" (market cap, index weight, ETF AUM, article count, GPR), and
price-level series (PX_LAST, Tot Return Index, 120MA, BEST EPS, Trailing EPS — index
levels in local units, not signals). On the TS side the three ETF-flow series
(net flow USD, net creation shares, flow-to-market-cap) are one thing at 0.98+.
Drop outright: the 22 single-currency ECB FX series (one country each), the seven
single-month snapshots (ratings, ETF creation fee/unit size, OFAC), and
`BBG_Debt_GDP_Ratio_TS` (one country, 38 rows).

Suspicious, not fixed (collector territory): `MS_CentralBank_BalanceSheet_GDP_CS`
and `MS_CentralBank_Claims_on_Government_Pct_GDP_CS` correlate 0.98–0.99 with the
exchange rate level (`Currency_CS`, `IMF_XRate_LCU_per_USD_CS`), which a GDP ratio
should not do.

Outputs (gitignored, regenerable in 4 s):
- `results/corr_<ts>/factor_correlation_matrix.xlsx` — sheets Correlation, Overlap_N,
  Variables, Top_Pairs, Clusters, CS_vs_TS
- `results/corr_<ts>/factor_correlation_matrix.parquet`, `factor_overlap_n.parquet`
- `results/corr_<ts>/factor_correlation_heatmap.pdf`
- `results/corr_<ts>/summary.json`, `run.log`

## Next

Arjun picks the factor set from the `Clusters` / `Top_Pairs` sheets. Then: ridge
floor → LightGBM (lambdarank@8 / top-8 classification / regression) → MLP with a
soft-top-8 expected-excess-return loss, all on month-level random splits.
