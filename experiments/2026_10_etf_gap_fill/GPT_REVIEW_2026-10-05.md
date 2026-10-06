## Verdict

The underlying one-day ETF reversal is real as a gross historical phenomenon. The local-market “gap fill” story has mostly collapsed into ordinary ETF reversal.

But this does **not** survive as a deployable strategy yet. The optimized one-name vol-scaled version is post-selected, unstable, concentrated in thin ETFs, and unproven out of sample. The long-short version is almost certainly unharvestable at roughly 2 bp per dollar traded.

### Solid

- The `1DRet` correction is right. Shifting the forward return one calendar day and compounding across each US close-to-close interval correctly maps the Sunday observation into Monday’s realized local return ([etf_gap_fill.py:159](</Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/etf_gap_fill.py:159>)). I independently reproduced the Japan example and the reported subperiod coefficients.

- The local component really has decayed: my read-only reproduction gave local coefficients of 0.307 in 2000–04, 0.098 in 2015–19, and 0.029 with t=1.96 in 2023–26. The recent ETF-reversal coefficient remains approximately −0.056. The regression implementation is correctly cross-sectional and dated ([etf_gap_fill.py:234](</Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/etf_gap_fill.py:234>)).

- The aggregate timing decomposition is arithmetically credible: most idealized close-to-close reversal return occurs from close to next open ([etf_reversal_1d.py:311](</Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/etf_reversal_1d.py:311>)). That does not establish the proposed economic mechanism, because closing-price bounce and stale opening prints produce exactly the same pattern.

### Fragile

- The 15:30 MOC result is not obvious close leakage. Time-zone conversion handles DST correctly, and the cached 15:30 values differ from the daily close by a median 8.8 bp; only 4.7% are exactly equal. But Yahoo’s value is the **open of the entire 15:30–16:00 hourly bar**, meaning the first trade sometime within that interval—not necessarily a tradable 15:30:00 price. That distinction is dangerous precisely because thin funds dominate the selections ([etf_gap_fill_intraday.py:103](</Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/etf_gap_fill_intraday.py:103>), [etf_gap_fill_intraday.py:143](</Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/etf_gap_fill_intraday.py:143>)).

- The full-history evidence is not a stable 34-ETF test. The hard-coded current-survivor universe had only about 17–22 available names during much of the early sample and reached all 34 only in 2016 ([etf_reversal_1d.py:97](</Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/etf_reversal_1d.py:97>)). Discontinued country funds are absent. The spectacular early Sharpe therefore mixes stale pricing, changing breadth, and survivorship.

- The sweep uses future return availability when determining the day’s eligible ranking universe: `ok` includes `fwd.notna()` before names are selected ([etf_reversal_sweep.py:172](</Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/etf_reversal_sweep.py:172>), [etf_reversal_volscaled.py:96](</Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/etf_reversal_volscaled.py:96>)). That is look-ahead. My corrected rerun changed fewer than 1% of days and barely moved Sharpe, so it is a real bug but not the source of the result.

### Wrong or unsupported

- The regional overnight claim is unsupported. The code calculates the overnight leg only for the combined universe. The regional test is instead performed on the later open-to-open E3 return ([etf_reversal_1d.py:311](</Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/etf_reversal_1d.py:311>), [etf_reversal_1d.py:349](</Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/etf_reversal_1d.py:349>)). Therefore “overnight reversal comes from Asia and Europe, not the Americas” was not actually tested.

- The README’s leave-one-ETF-out statement is false. It says the five-year Sharpe remains 1.0–1.4, but the generated test reports 0.43–0.70 ([README.md:87](</Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/README.md:87>), [etf_reversal_1d.py:378](</Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/etf_reversal_1d.py:378>)).

- The 15:30-entry return wrongly adds the current day’s dividend even though entry occurs after the ex-date ([etf_gap_fill_intraday.py:169](</Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/etf_gap_fill_intraday.py:169>), [etf_reversal_1d.py:422](</Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/etf_reversal_1d.py:422>)). Correcting it reduces that variant’s Sharpe from 1.86 to approximately 1.69. It does not affect the headline MOC-entry result.

- The vol-scaling explanation is mathematically wrong: subtracting the common cross-sectional mean **does change the ranking** when each observation is subsequently divided by a different volatility ([etf_reversal_volscaled.py:13](</Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/etf_reversal_volscaled.py:13>)). This is a relative-volatility signal, not merely raw returns divided by volatility.

- The reported `p=0.006` for one-name vol scaling is not honest confirmation after that formulation was selected from the preceding 147-cell sweep. Its pairwise bootstrap does not account for that earlier selection ([etf_reversal_volscaled.py:123](</Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/etf_reversal_volscaled.py:123>)). The recent E5 vol-scaled improvement is nonsignificant by the experiment’s own results, and full-history versus five-year cell rankings have correlation 0.06.

- “Pre-registered” is overstated. The only registration is text inside the script; there is no frozen methodology or hypothesis-ledger entry, and the script was committed after its output was generated ([etf_reversal_1d.py:20](</Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/etf_reversal_1d.py:20>)).

## Three checks that matter next

1. Rebuild the 15:30 test from 1-minute Bloomberg/TAQ/IBKR data using a last-completed 15:29 bar, NBBO midpoint, and actual closing-auction price. This resolves timestamp leakage, stale prints, bid-ask bounce, and MOC feasibility together.

2. Repeat on a point-in-time ETF universe including liquidated funds, with fixed liquidity eligibility and no future-availability filtering. Report common-universe and liquid-only results separately.

3. Freeze exactly two rules—raw seven-name and relative-vol one-name—and run a prospective MOC shadow with actual auction spreads, impact, borrow availability and fills. No further parameter changes.

Bottom line: **keep the reversal as a credible research observation; reject the regional story and the optimized-rule confidence; do not deploy it.**