# Pre-registration: rolling five-year window versus recency-weighted all-history (Arjun, decision 2, 2026-10-07)

Written before any run of the grid. The default model trains each fold on only the trailing 60 months.
Both outside reviewers argued for keeping all history with more weight on recent years. Arjun's view is
that the world changes, which is why rolling holds up evenly across decades. This grid tests it.

**Arms** (all otherwise identical to the default: cleaned v3 panel, 30 nets per fold, objectives mse and
soft_top8, hold while ranked ≤ 16, three independent seed draws 0 / 1000 / 2000):
- `exp`: expanding window, equal weights (all history, no recency).
- `ema24`, `ema36`, `ema60`, `ema120`: expanding window, each training month weighted 0.5^(age / half-life)
  in the loss and in the early-stopping score, normalised to mean one. Half-lives in months. A 36-month
  half-life puts about the same total weight on the last five years as a hard 60-month window does; 120 is
  close to equal weights.
- Comparator: the three existing rolling-60 draws (`walk_20261007_15*_default_s*`).

**Primary statistic.** For each arm, the pooled ensemble of its three draws (mean score per date and country),
baskets under the default rule, paired monthly excess versus the pooled rolling-60 default over the common
out-of-sample months 2005-02 → 2026-09, annualised, with its t. Secondary: each draw separately (spread
between draws is the noise floor), information ratio, turnover, by-decade excess.

**Decision.** The default changes only if an arm beats rolling-60 by a paired t ≥ 2.0 on the pooled comparison
and is ahead in each of the three draws. Otherwise rolling-60 stays. With about 1.5% a month of paired noise
over 260 months, t = 2 needs roughly +2.2% a year, so "no detectable difference" is the expected outcome and
is reported as such, not as evidence that either is better. The ridge inside each run is unweighted and is not
part of this comparison.
