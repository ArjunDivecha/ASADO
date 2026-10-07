## overview

Stages 1 to 3 are complete: the factor universe has been mapped for duplicates, every factor has been screened on its own against next month's return, and your 256-factor set has been frozen into one modelling table with publication lags applied. Stage 4, the floor, is the first time anything is actually trained — a linear model and three flavours of boosted trees, each run on thirty different random partitions of the months so that no single lucky split can carry the result.

The honest prior going in: no single factor is strong. The best of them make four to five percent a year over the equal-weight average in a top-8 basket, the median factor makes under one percent, and a single split of the data is uncertain by about three percent a year. So the floor models are being asked whether *combining* 256 weak inputs does better than the best one alone — and the stage 4 numbers should be read with that noise band in mind.

## stage1

Your instinct about the news factors was right, and they are not the only redundant family. The duplication sits in four places. The 46 GDELT news series (in each normalisation) collapse into roughly eight distinct things: two pairs are exact mirrors of each other, the `_raw` and `_z` variants track their parent at 0.98 or better, and the fast, slow, local and risk sentiment measures form one block. Twelve government yields, policy rates and money-market rates sit in a single block. Market cap, index weight, ETF assets, article count and the geopolitical-risk index all move together above 0.95, because big countries get more news and more index weight. And the price-level series — `PX_LAST`, the total-return index, the 120-day average, EPS levels — correlate above 0.9 with each other because a cross-sectional z-score of an index level in local currency is just units, not a signal.

The CS and TS versions of a factor are genuinely different views for almost everything: the median correlation between them is 0.37, and only 19 of the 151 factors with both exceed 0.8. Every one of those 19 is GDELT, whose series are standardised upstream so both normalisations land in the same place. That is why both versions are kept for the model, and why the de-duplication happens within each normalisation rather than across.

About thirty variables are junk for a 34-country model before you choose anything: 22 ECB exchange-rate series that each cover exactly one country, seven series that exist for a single month (the credit ratings, ETF creation fee and unit size, OFAC sanctions), and one Bloomberg debt ratio with one country and 38 rows. They show as the grey stripes in the heatmap.

## stage2

The univariate signal is thin. Of the 262 factors with enough history to score, 23 clear a t-statistic of 1.96 — against about 13 you would expect by chance from 262 tries — and only one survives a false-discovery correction. The best honest top-8 baskets make four to five percent a year over the equal-weight average with hit rates around 0.6, and the median factor makes under one percent.

The strongest names are familiar. REER from T2 has a t-statistic of 3.4 and its top-8 basket makes 5.0% a year at a 0.61 hit rate. Advance-decline is 3.2 on 229 months. One-month reversal in time-series form is 3.1, and Best ROE in time-series form is 2.7. Trailing PE and earnings yield each make about 4% a year in the basket at 0.57 hit rates, though their t-statistics are only 1.4 and 1.8. The best top-8 number anywhere is GDELT tone dispersion at 5.4% a year with a 0.62 hit rate — but that is 133 months since 2015, and one of a dozen near-identical news series, so it is one hit tested many ways. Time-series variants screen a bit better than cross-sectional ones overall, 14 significant versus 9.

Two things surprised me, and both matter for the model build. First, **T2's REER is the BIS REER shifted one month**: the T2 value at any date equals the BIS value from the month before, exactly, across all 10,494 country-months. That is why T2 REER at lag zero and BIS REER at lag one give the same answer while BIS REER at lag zero shows nothing. T2 bakes the publication lag into the stored series, and I would assume its other macro columns do the same. Second, **lag choice dominates for the slow sources**: across the 64 lagged-source factors the mean |t| is 0.9 at the harness lag and 1.9 at zero lag, with 18 significant versus 7. Most of that zero-lag "signal" is information that was not available in time, which is why the modelling panel applies the lags.

One artifact to ignore: `MS_Index_Weight_CS` shows a t of −3.1 but rests on 25 months at a 12-month lag. And 79 factors are unscored because they cover fewer than 20 countries or 24 months. This is in-sample over the full history by design — it ranks the factors, it does not validate them.

## stage3

The set is 256 factors: the 262 the screen could score, minus the six price-level and market-cap series. By source that is 98 from T2, 92 from GDELT, 31 from Bloomberg and 35 from the IMF, FRED, BIS, OECD and the uncertainty indices; 130 cross-sectional and 126 time-series; 190 used as stored and 64 lagged one month. Two of the 256 — `MS_Index_Weight` in both forms — are the 25-month, 12-month-lag artifacts from the screen; they are in by your rule but cover 7% of rows and will contribute nothing.

The coverage chart is the thing to keep in mind when reading every later result. Before 2015 a typical row has about 125 of the 256 factors; after 2016 it has about 232, because the whole GDELT block starts in 2015. The models are not allowed to drop the early rows — that would throw away half the history — so each handles the missingness its own way: the trees natively, the linear model by treating a missing z-score as average and carrying a per-source "how much of this block is present" column.

Still in the set, flagged rather than removed: the total-return index, the 120-day average, and the BEST and trailing EPS *levels*, which are scale rather than signal in cross-sectional form. They were not on your drop list, so they stay — your call.

The lag application was verified exactly: every lagged column at month D equals the raw value at D−1, and every unlagged column equals the raw value at D. The excess-return target averages to zero within every month by construction.

## next

The neural-network stage: a small shared network scoring each country-month from the same 256 inputs, trained on a differentiable soft-top-8 portfolio loss — the expected excess return of the selected basket, which is linear in the selection and so needs no reinforcement learning. Judged on exactly the same thirty splits and the same metrics as the floor, with the shuffled-label control and a fit-capacity check on a tiny subset first. Then two extensions, one at a time: a global-context block (series identical across countries, which a net can only use through interactions — expected to inflate random-month scores, so paired with the contiguous-block diagnostic), and a cross-country attention model where one country's score can depend on the others'.
