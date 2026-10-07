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

`factor_correlation.py` → `results/corr_20261007_094631/`

- Variables: every `_CS` (within-month cross-sectional z-score) whose catalog
  frequency is not quarterly or annual: **161 of 228** (53 T2, 46 GDELT, 29 Bloomberg,
  33 from IMF/FRED/BIS/OECD/EPU/GPR/OFAC). The 67 quarterly/annual series are listed
  in the `Variables` sheet as excluded and can be added.
- Method: pooled Pearson over (date, country) rows, pairwise-complete, minimum 200
  overlapping observations (≈ 6 months × 34). Because `_CS` has zero mean each month
  this is essentially the average within-month cross-sectional correlation — the
  right measure of "do these two factors order the countries the same way".
- Order: average-linkage clustering on 1 − |ρ|; `Clusters` sheet cuts at |ρ| ≥ 0.9
  and ≥ 0.8.

Headline: 97 pairs at |ρ| ≥ 0.9, 183 at ≥ 0.8, out of 11,614 defined pairs. The
duplication is concentrated in four families — GDELT news (46 series collapse to
roughly 8 distinct things), interest rates (12 yields/policy rates in one block),
"size" (market cap, index weight, ETF AUM, article count, GPR all move together), and
price-level series (PX_LAST, Tot Return Index, 120MA, BEST EPS, Trailing EPS — index
levels in local units, not signals). Seven variables have no defined correlations
because they exist for a single month (ratings, ETF creation fee/unit size, OFAC) or
three countries (ECB FX).

Suspicious, not fixed (collector territory): `MS_CentralBank_BalanceSheet_GDP_CS`
and `MS_CentralBank_Claims_on_Government_Pct_GDP_CS` correlate 0.98–0.99 with the
exchange rate level (`Currency_CS`, `IMF_XRate_LCU_per_USD_CS`), which a GDP ratio
should not do.

Outputs (gitignored, regenerable in 4 s):
- `results/corr_<ts>/factor_correlation_matrix.xlsx` — sheets Correlation, Overlap_N,
  Variables, Top_Pairs, Clusters
- `results/corr_<ts>/factor_correlation_matrix.parquet`, `factor_overlap_n.parquet`
- `results/corr_<ts>/factor_correlation_heatmap.pdf`
- `results/corr_<ts>/summary.json`, `run.log`

## Next

Arjun picks the factor set from the `Clusters` / `Top_Pairs` sheets. Then: ridge
floor → LightGBM (lambdarank@8 / top-8 classification / regression) → MLP with a
soft-top-8 expected-excess-return loss, all on month-level random splits.
