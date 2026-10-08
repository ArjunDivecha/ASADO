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

---

# Test 2 — Arjun's rule: exclude countries with news score ≤ −1

**Verdict: FAIL** (run `results/gdelt_filter_20261007_223003/`, 2026-10-07 22:30, 127 months 2016-03 → 2026-09).
Pre-registered as "Test 2" in `PREREG.md`, committed before the run.

Rule: run the default model exactly as normal, but any country whose news score (minus the 14-day composite
shock) is −1 or worse is ineligible that month; a held name with bad news is dropped and the next-ranked
eligible name fills the slot.

- About 2.8 of 34 countries were ineligible in a typical month and 0.47 holdings a month were dropped for news;
  the basket differed from the default in 96 of 127 months.
- The filtered basket made 1.83% a year against the default's 3.01% over the same months: a **cost of 1.18% a year**
  (paired t −1.21), beating the default in 34% of months. The 95% interval on the gain is −3.1% to +0.7% a year.
- Stale news (three months old) under the same rule cost 1.86% a year (t −2.34). The harm is not about timing.
- Country-shuffled news: 95th percentile of the paired t is +0.82; the matched t sits at the 18th percentile.
- Every threshold (−0.5, −1, −1.5), window (7/14/30 days) and score (composite, attention-share composite, tone alone)
  was negative, except two cells at the loosest filter (−1.5, 30 days: +0.4% and +0.6%, t 0.3–0.5). The tighter the
  filter, the larger the loss: at −0.5 the cost is 2–4% a year.

Why excluding bad-news countries hurts (diagnostic, same data): the model's score is positively correlated with the
news shock within a month (Spearman 0.063, t 2.5) — the model leans slightly toward countries in the news, which are
often the cheap, distressed ones it likes. Bad-news holdings did do a little worse (−0.07% a month against +0.29% for
the other holdings), but the names that replaced them, further down the ranking, did worse still, and the filter also
skipped top-ranked newcomers with bad news and broke the hysteresis (2.6 names changed a month against 1.8). The
model's ranking beats the news filter. Nothing here changes the default model. This closes the last stated-rule use of
GDELT aggregates on this project.

---

# Test 3 — Arjun's rule: boost countries with news score ≥ +1

**Verdict: FAIL** (run `results/gdelt_boost_20261007_224509/`, 2026-10-07 22:45, 127 months). Pre-registered as "Test 3"
in `PREREG.md`, committed before the run.

Rule: default model as normal, but a country with news score ≥ +1 (good news) moves up four places in the ranking
before the buffer rule. About 2.6 countries a month qualified and 0.65 boosted names a month were held; the basket
differed from the default in 31 of 127 months.

- Primary: **cost 0.19% a year** against the default (t −0.60); 95% interval −0.8% to +0.4%. Stale news: −0.14% (t −0.22).
  Shuffled null 95th percentile t +1.63; the matched t sits at the 17th percentile.
- Every good-news cell (thresholds +0.5/+1/+1.5, boosts 2/4/8, windows 7/14/30, three scores) is within ±0.9% a year
  and none reaches |t| 1.6. Good news does not help the model pick.

**The mirror (boost bad-news names, pre-registered as secondary, cannot pass on its own):** at threshold 1.0, 14-day
window, boost 4 it gave **+1.22% a year (t +2.26)**, and boost 8 gave +1.79% (t +2.58). Read with the rest of its grid:
at threshold 1.5 the same rule *loses* (−0.54%, t −2.24); at 0.5 it is +0.7% with t below 1; at 7- and 30-day windows it
is +0.35% and +0.14% with t 0.6 and 0.3. Two cells above t 2 and one below −2 out of 27, with no monotone response to
threshold or window, is what noise looks like under multiple comparisons, not a contrarian signal. GDELT starts in 2015
and every month has now been used, so there is no independent slice to confirm it on; the only honest follow-up would be
a forward record, which is not worth the attention for a rule of this shape.

Three stated rules, three fails. GDELT aggregates are closed on this project; nothing changes the default model.

---

*Note (2026-10-08).* `holdings.parquet` in the test-1 run holds the default basket from 2016-03 with the hysteresis state
carried from 2005 (3.36% a year over those months). Tests 2 and 3 re-ran the hysteresis from a cold start at 2016-03 for
both their filtered/boosted baskets and their default comparator (3.01% a year), so their paired comparisons are like
with like; the two "default" figures differ only in warm-up. No verdict depends on it.
