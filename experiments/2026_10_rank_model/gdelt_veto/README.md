# GDELT veto test — result

**Verdict: FAIL** (run `results/gdelt_veto_20261007_214235/`, 2026-10-07 21:42, 124 months 2016-03 → 2026-09).

Question: does a GDELT news shock in the 14 days before rebalance identify which of the default
model's eight holdings will lag the other seven next month? Pre-registered in `PREREG.md`
(committed `03a3fd8` before the first run; amendment A1 committed `505cfd3` before any result was read).

- Primary: the most-shocked holding **beat** the other seven by +0.41% a month, t +0.89; it lagged in
  48% of months. The hypothesis predicted a lag.
- Stale news (same measure, three months earlier): +0.34% a month, t +0.74. Whatever is there is not
  news-specific.
- Country-shuffled news (500 permutations): 5th percentile t −1.70, 95th +1.53; the matched t sits at the
  85th percentile of the null.
- Acting on it (swap the flagged name for the best non-holding) would have cost 1.4% a year (t −1.6).
- Gated version (act only on a shock ≥ 1 sd, 64–76 months): shocked holdings lagged by 0.5–0.8% a
  month, t between −0.3 and −1.3. Nothing significant in any component or window (7/14/30 days),
  nor in the attention-share variant (amendment A1).
- Per seed draw: t +1.99, +0.58, +0.10 — the sign and size move with the draw, i.e. noise.
- Power: realised sd of the monthly difference 5.1%; detectable effect at 80% power 1.28% a month on the
  flagged name (≈1.9% a year on the basket). The 95% interval on the primary, −0.5% to +1.3%, excludes a
  useful veto effect, so this is a kill, not an inconclusive.
- Context: as a ranking signal over all 34 countries the composite shock has mean rank IC +0.02, t +1.16
  (the question already answered DEAD on 27 July).
- Correctness: the reconstructed pooled basket matches the saved default run to 1e-18.

Two data facts found on the way:

1. **GDELT country-day attention is a blunt instrument.** US articles in March 2020 ran at 79,000 a day
   against a 79,000 baseline; Turkey's final two weeks of August 2018 were at its normal 3,000 a day. Total
   GDELT volume is capacity-bound and halved between 2017 and 2020. A share-of-firehose attention measure
   (amendment A1) did not change the result.
2. **The daily deep file is a schema without content.** `country_signal_daily_deep.parquet` has columns
   for 568 theme shares, 75 GCAM and 24 event measures, but ~0.1% of theme cells are filled (all 2026)
   and the event columns are entirely empty for our 31 countries. Daily theme/event data does not exist;
   the content exists only monthly, in the file killed on 27 July.

Consequence: GDELT's remaining role in this project is as text an LLM reads forward. Nothing here
changes the live default model.
