# 2026_10_rank_model — country top-8 ranking model

**Where this lives (2026-10-07).** Branch `exp/NN`, worktree
`/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-NN/` — the main ASADO
checkout is production and carries none of this (moved off `main` in `d2942dc`).
Code, config and `results/` are here; the frozen data (snapshot, modelling panel)
stays under the main checkout's gitignored
`/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/`.
Run everything with the experiment's own venv, `.venv/bin/python` (uv, Python 3.12,
LightGBM) — never the ASADO `venv/`. Each script defaults to the newest upstream
run (`results/corr_*` → `factor_screen.py`, `results/screen_*` → `build_panel.py`).

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

## Step 2 — univariate screen vs next-month return (2026-10-07)

`factor_screen.py` → `results/screen_<timestamp>/` (latest run wins)

- Target: `1MRet` (source `t2`) — verified to be the forward one-month total return
  labeled at the window start (equals TotReturnIndex(D+1)/TotReturnIndex(D) − 1,
  correlation 1.000 over 320 months). Excess = country return minus the equal-weight
  average of all countries with a return that month.
- Alignment: harness convention (`infer_publication_lag`): lag 0 for T2 and GDELT,
  lag 1 for other monthly sources. Zero-lag columns alongside for comparison.
- Per factor, per month (≥ 20 countries): Fama-MacBeth slope and t, Spearman rank IC
  and t, top-8 / bottom-8 basket excess (annualized), hit rate, long-short spread.
  Two-sided p and Benjamini-Hochberg q across all factors. Cluster ids joined from
  step 1 and members ranked within each duplicate group (`Clusters_Ranked`).

Headline: the univariate signal is thin. 262 of 341 factors had enough coverage to
score; 23 clear |t| = 1.96 against about 13 expected by chance, and only one
(`BIS_REER_CS`, t = −3.6) survives a false-discovery cut at q < 0.10. The best
honest top-8 baskets (REER, tone dispersion, trailing PE, earnings yield) make 4–5%
a year over the equal-weight average with hit rates of 0.57–0.62; the median factor
makes 0.9%. TS variants screen slightly better than CS (14 vs 9 significant).

Findings worth keeping:
- **T2's REER is the BIS REER shifted one month** (T2 value at D == BIS value at
  D−1, exactly). So T2 REER at lag 0 and BIS REER at lag 1 are the same test
  (t = 3.4 / −3.6, sign-flipped); BIS REER at lag 0 shows nothing (t = −0.9). T2 bakes
  the publication lag into the stored series. Assume other T2 macro series may too.
- **Lag choice dominates for the slow sources.** For the 64 lagged-source factors,
  mean |t| is 0.9 at lag 1 and 1.9 at lag 0, with 18 vs 7 significant — most of the
  zero-lag "signal" in IMF/FRED/BIS data is information not available at the time.
  The model must apply the harness lags to these inputs.
- `MS_Index_Weight_CS` (t = −3.1) rests on 25 months at lag 12 — ignore.
- 79 factors are unscored: 24 single-currency ECB FX, 22 thin-coverage Bloomberg
  (breakevens, 30Y, OIS, PMIs — under 20 countries), 12 FRED, the 3 global GPR
  series (identical across countries), and a handful of IMF/OFAC series.

## Step 3 — factor set v1 and the modelling panel (2026-10-07)

`build_panel.py` → `factor_set_v1.json` (committed) and
`/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_v1/feature_panel_v1.parquet`

Arjun's rule: every screened factor (262) minus `PX_LAST`, `MCAP`, `MCAP Adj` in both
normalizations → **256 factors** (130 CS / 126 TS; 98 T2, 92 GDELT, 31 Bloomberg, 35
other; 190 lag 0, 64 lag 1, 2 lag 12). Panel: 10,623 country-month rows, 2000-02 →
2026-09, lags applied so row D holds what was available at D; target `fwd_excess` =
`1MRet` − equal-weight mean. Rows before 2015 carry ~125 of the 256 factors, after
2016 ~232 (GDELT starts 2015). Lag application verified exactly.

## Step 4 — the floor: ridge + LightGBM (2026-10-07)

`train_floor.py` → `results/floor_<timestamp>/` (first full run `floor_20261007_110654`,
3.2 min). 30 random 80/20 month splits + 5 contiguous blocks; shuffled-label controls on
10 splits; reference = REER_CS alone. Objective: equal-weight top-8 by score vs the
equal-weight average, annualized; soft top-k at τ = 0.25 / 1.0 alongside.

Eval, random splits (mean over 30; single-split SE ≈ ±2.9 %/yr):

| model | top-8 excess %/yr | hit | rank IC | L−S %/yr |
|---|---|---|---|---|
| ridge (256 factors) | +5.3 | 0.60 | 0.09 | 10.9 |
| reference REER_CS | +5.2 | 0.62 | 0.05 | 6.7 |
| LightGBM regression | +3.8 | 0.58 | 0.05 | 7.6 |
| LightGBM top-8 classifier | +2.8 | 0.55 | 0.03 | 4.4 |
| LightGBM lambdarank@8 | +1.9 | 0.52 | 0.01 | 3.3 |
| shuffled controls | +0.4 / +0.5 | 0.49 | 0.00 | — |

Verdict: **the floor is the single best factor.** Ridge ties REER on the top-8
objective (paired diff +0.1, t = 0.2) and beats it only on the full ordering. Trees
lose to one factor on eval while making 22–26 %/yr on their training months (overfit;
early stopping at ~100 rounds, sometimes 1). Contiguous blocks: ridge 3.2, reference
5.0, LightGBM regression 0.3 — about two points of the random-split score is temporal
proximity. Controls at zero. Ridge is steadier across eras than REER (every 5-year era
3.4–8.6 %/yr; REER −2.9 since 2025).

## Step 5 — the neural network (2026-10-07)

`train_nn.py` → `results/nn_<timestamp>/` (first full run `nn_20261007_112400`, 576 nets,
3.6 min on 14 cores). Shared MLP 271 → 64 → 32 → 1 (GELU, dropout 0.15, weight decay
0.01), three objectives: `mse` (predict excess, pick top 8), `soft_top8` (z-score the
34 outputs, sigmoid-threshold memberships summing to 8, maximise membership-weighted
excess; exact implicit-function gradient, finite-difference verified), `mse_then_soft`.
Five seeds → score-average ensemble. Same 30 random splits + 5 blocks as the floor;
early stopping on 12% of training months; shuffled-label control on 10 splits;
capacity check (24 months, unregularised) fits perfectly.

Eval, random splits (5-seed ensembles, mean over 30):

| model | top-8 excess %/yr | vs ridge (paired) | wins/30 | blocks %/yr |
|---|---|---|---|---|
| net, MSE | +6.3 | +1.1, t 2.1 | 22 | 4.7 |
| net, soft top-8 | +6.4 | +1.1, t 2.1 | 20 | 3.4 |
| net, MSE → soft | +6.5 | +1.3, t 2.3 | 21 | 4.3 |
| ridge (bar) | +5.3 | — | — | 3.2 |
| net, shuffled control | +0.7 | | | |

Verdict: **the net clears the bar by about a point a year — all of it from 2000–2009.**
Paired by month, net − ridge ≈ +4 %/yr in 2000–09 (t 2.5–3.0) and ≈ 0 in 2010–19 and
2020–26 (t ≈ 0). Objectives tie on the basket; the soft objective widens the long-short
spread (12.9 vs 11.5). Ensembling adds ~1–1.7 points over a single seed (within-split seed
sd ≈ 2). Nets fit training months at 30–43 %/yr (ridge 16) — regularisation is the next
lever. Controls at zero.

## Running report

`build_report.py` → `results/report.html` — one self-contained light-mode page: a
section per stage with number tiles, charts, sortable tables, commentary
(`report_commentary.md`, written after the numbers) and links to every file.
Regenerate after any stage: `.venv/bin/python build_report.py && open results/report.html`.

## Next

Hill-climb on the net (each full run < 4 min): regularisation/width sweep; 10–20 seed
ensembles; explain the 2000–09 edge (rerun without GDELT, without presence columns).
Then global-context block (v2 panel) and cross-country attention. Walk-forward through
time only once the design settles.
