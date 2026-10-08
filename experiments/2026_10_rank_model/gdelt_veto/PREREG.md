# Pre-registration: GDELT news shocks as a veto on the default model's holdings

Written 2026-10-07, before any result was computed. Committed on `exp/NN` before `veto_test.py`
was first run on the full sample. Changes after this commit are amendments and must be listed at
the bottom with their reason.

## Question

Each month the default model (rolling 60-month window, 30-net ensemble, hold while ranked ≤ 16)
holds eight countries. Does a sharp news shock in the days before the rebalance identify the
holding that will lag the other seven over the coming month?

This is the only role the research agenda leaves GDELT ("conditioning, not a standalone
signal"). It has never been tested. It is not a re-run of the dead tests: those asked whether
GDELT ranks 34 countries; this asks whether it flags a failure among eight already chosen.

## Data

- **Holdings and scores.** Out-of-sample scores from the three independent default-model draws
  (`results/walk_20261007_15*_default_s{0,1000,2000}/predictions_oos.parquet`, model `nn_mse`),
  averaged per date and country (the pooled ensemble). Holdings follow `hysteresis.build_baskets`
  with k = 8, M = 16. A correctness check requires the reconstructed basket's monthly excess to
  match the saved default run.
- **Returns.** `fwd_excess` for the row dated D is the country's return over the month after D
  minus the equal-weight mean of all 34. Panel: `panel_v3_clean/feature_panel_v3_clean.parquet`.
- **News, primary.** The live nightly GDELT store
  (`A Working/GDELT/data/panels/country_signal_daily.parquet`), daily per country:
  `n_articles`, `tone_mean`, `tone_dispersion`, `country_news_risk_raw`. Mapped to the 34 buckets
  through `PRICE_BUCKETS`; the three US buckets share USA news and the two China buckets share CHN.
- **News, exploratory.** The retired deep file
  (`A Working/GDELT/Deep/data/features/country_signal_daily_deep.parquet`, ends 2026-04):
  `theme_*_share` (284 themes), `gcam_lm_uncertainty_mean`, `event_goldstein_mean`,
  `event_root_protest_n`.

## Timing

A row dated D (first of month) holds information available at the end of the previous month and
is scored on the following month's return. The news window is the w calendar days ending the day
before D: `[D − w, D)`. No news day overlaps the holding month.

## Shock construction

For each country and daily series, take the rolling w-day mean on a full calendar index (missing
GDELT days stay missing; a window needs at least w/2 days). The shock at D is that window mean
standardised against the distribution of the same rolling mean over the trailing 365 days ending
at D − w (so the baseline excludes the window itself). Sign convention: a higher shock is worse
news, so tone enters with its sign flipped.

- Components: attention `log1p(n_articles)`, tone (flipped), dispersion, risk.
- **Composite** = mean of the available component z-scores.
- Windows: w = 14 (primary), 7 and 30 (secondary).

Shocks are available from 2016-03-01 (one year of baseline after the store's 2015-02-18 start).
Months tested: 2016-03-01 to 2026-09-01, about 127.

## Primary statistic

Each month, among the eight holdings, the **flagged** holding is the one with the highest
composite shock (w = 14). Primary outcome: flagged holding's `fwd_excess` minus the mean
`fwd_excess` of the other seven, in percent per month. Averaged over months, with a plain
t-statistic (monthly observations do not overlap). Hypothesis: negative.

## Secondary statistics (reported, not decisive)

1. Within-holdings Spearman correlation between composite shock and `fwd_excess`, averaged over
   months, with its t.
2. Action-gated variant: flag only when the composite shock is at least 1.0; otherwise abstain.
   Same difference statistic over flagging months, and the count of months flagged.
3. Basket consequence: replace the flagged holding with the highest-scored non-holding. Report
   the annualised change in basket excess return and its t, for the always-flag and gated variants.
4. Each component separately, and each window (7, 14, 30), for the primary statistic.
5. Each of the three draws separately (robustness to the seed draw).
6. Exploratory deep-file arm, to 2026-04: theme-surge count (number of theme shares whose w-day
   z exceeds 3), uncertainty z, Goldstein (flipped) z, protest-count z. Same primary statistic.
7. Context only: cross-sectional rank correlation of the composite shock with `fwd_excess` over
   all 34 countries each month. This is the question already answered DEAD; it is shown to make
   clear the veto test is a different question.

## Controls (both must be beaten)

- **Stale news.** The composite computed from the window `[D − 90 − w, D − 90)`, three months
  earlier. Same primary statistic.
- **Country-shuffled news.** 500 permutations. Each month the eight holdings receive the composite
  shocks of eight countries drawn at random from the 31 news countries, excluding each holding's
  own. Same primary statistic each time, giving a null distribution of t.

## Decision rule

**PASS** only if all three hold:
1. matched primary t ≤ −2.0;
2. matched t is below the 5th percentile of the shuffled-null t distribution;
3. the stale-news t is not itself ≤ −2.0, and the matched t is more negative than the stale t.

Otherwise **FAIL**. A positive t of 2 or more (shocked holdings outperform) is reported as a
surprise, not a pass; it would be a different hypothesis.

Power is reported from the realised standard deviation of the monthly difference: the effect
detectable at 80% power over the months available. If a FAIL comes with a wide interval that
includes an economically useful effect, the verdict is "inconclusive", stated as such, not
"no effect".

## What is not allowed afterwards

- No sign flips, no new windows, no component re-weighting after seeing results.
- No kill or pass on cost or turnover grounds (cost law retracted 2026-07-13).
- Secondary and exploratory results cannot rescue a primary FAIL. They can motivate a *new*
  pre-registration.

## Amendments

**A1, 2026-10-07 21:45, before any result of the full run was read.** A sanity check of the
shock measure on two known episodes (Turkey, rebalance 2018-09-01; United States, rebalance
2020-04-01) showed that absolute article counts barely move: US articles in March 2020 were
79,000 a day against a 79,000 baseline. GDELT's total daily volume is capacity-bound and fell by
half between 2017 and 2020, so `log1p(n_articles)` cannot register a surge for a large country.
Added as **secondary** components: `attention_share` = log of the country's share of that day's
total articles across the 31 news countries; and `composite_share`, the composite with
`attention_share` in place of `attention`. The primary (composite, w = 14, absolute attention)
is unchanged and remains the decision statistic. The same check also showed the 14-day window
ending 31 August 2018 missed the Turkish crisis week of 10–17 August; the 30-day secondary
window covers it, and no window was added.
