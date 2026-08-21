# T2 monthly spine — the look-ahead in `_clean_sheet`, and why the approved fix was backed out

**Date:** 2026-08-21
**Status:** DECISION REQUIRED — nothing has been landed in `scripts/build_t2_master.py`.
It sits at HEAD, unmodified, still with the look-ahead.
**Origin:** Tier 1 item 5 of
[ox-review.md](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/ox-review.md).

---

## Bottom line

The look-ahead is real but **small — 0.804% of cells**, not the 7.7% an earlier
buggy count of mine suggested.

The fix I had approval to make — adopt the daily builder's expanding-window
pattern — was implemented, measured on the real workbook, and **makes the data
substantially worse**: it touches 3.318% of cells and clips 13.5% of Copper and
9.7% of Oil, because an expanding median±MAD band anchors on the early sample
and then clips the entire later uptrend. It has been reverted.

A better option exists and is measured: **drop the winsorizer entirely and keep
only a causal spike guard**. It is fully point-in-time, and it touches **0.236%**
of cells — *less* than the current leaking rule — while leaving every trending
level series essentially untouched.

I am not landing it without your call, because it changes the T2 feed's cleaning
philosophy rather than fixing a bug in it.

---

## What the leak is

`_clean_sheet` (`scripts/build_t2_master.py:300`) runs two mechanisms over every
Bloomberg sheet. Both use data from the future.

**1. `_winsorize`** clips each observation to bounds from the **full-sample**
median and MAD:

```python
median = series.median()                                 # 2005–2026
mad    = stats.median_abs_deviation(series, scale="normal")
return series.clip(median - 5*mad, median + 5*mad)
```

Whether a 2008 observation got clipped depended on what happened in 2024.

**2. `_check_local_outliers`** judges point *i* against a **centred** ±20-month
window and replaces it with a mean computed from the 20 months *after* it:

```python
end    = min(len(series), i + window_size + 1)
window = pd.concat([series[start:i], series[i + 1 : end]])   # includes the future
```

**Reach.** These cleaned sheets are the monthly optimizer's inputs *and* are
unioned into `unified_panel` as `source='t2'` — 1,085,246 rows, 30.6% of
`feature_panel`, the harness surface. So the leak reaches recorded verdicts, not
just the optimizer.

---

## Why the approved fix failed

The plan was to adopt the expanding-window pattern that already exists correctly
in this codebase at `scripts/t2_normalize_daily.py:75-85`. The analogy does not
hold, and the reason is worth recording:

> In `t2_normalize_daily.py` the expanding statistic **produces the output** — a
> z-score. Here the expanding statistic is used to **clip a level that is then
> retained**. Expanding stats are fine for normalization; they are not fine for
> level-clipping.

`median ± k·MAD` clipping of a retained **level** is ill-posed for a trending
series, whatever window you use. The existing full-sample version only escapes it
because the full-sample median sits mid-trend, so the ±5 MAD band spans the whole
range — which is *precisely* the look-ahead. Make the same statistic causal and
the band anchors on the early sample, and the later trend is clipped away.

This is not a window-length problem. Sweeping expanding / rolling-120 /
rolling-60 does not fix it — see variants B, C, D below.

---

## Measured on the real workbook

Source: `Data/work/t2/T2 Bloomberg Master.xlsx`, 39 cleaned sheets, 337,990
populated cells. `touched` = clipped or replaced. `differs` = cells whose final
value differs from what production produces today.

| # | variant | causal? | touched | differs vs prod | Copper | Oil | Gold | Agri | Currency | TotRetIdx |
|---|---|---|---|---|---|---|---|---|---|---|
| **A** | **full-sample + centred — PRODUCTION** | ✗ **leaks** | **0.804%** | — | 0.00 | 0.00 | 0.31 | 0.00 | 1.43 | 0.96 |
| B | expanding + trail 4σ/mean — *the approved fix* | ✓ | 3.318% | 3.586% | **13.48** | **9.72** | 0.31 | 3.45 | 5.91 | 4.19 |
| C | rolling-60 + trail 4σ/mean | ✓ | 3.683% | 4.068% | 8.15 | 9.09 | **8.15** | **8.46** | 3.59 | 1.97 |
| D | rolling-60 + trail 6σ/clip | ✓ | 3.195% | 3.655% | 7.52 | 8.46 | 8.15 | 8.46 | 3.17 | 1.63 |
| **E** | **no winsorize + trail 6σ/clip** | ✓ | **0.236%** | 0.955% | 0.00 | 0.31 | 0.00 | 0.00 | 0.22 | 0.04 |
| F | no winsorize + trail 8σ/clip | ✓ | 0.134% | 0.876% | 0.00 | 0.31 | 0.00 | 0.00 | 0.14 | 0.00 |

Every variant that keeps a winsorizer (B, C, D) destroys trends. Every variant
that drops it (E, F) is both causal and *gentler than production*.

Two design choices inside E/F matter:

- **Trailing-only, not centred.** A causal detector cannot wait for the future to
  confirm a new level.
- **Clip-to-band, not replace-with-mean.** Replacing a point with the trailing
  mean turns every genuine regime shift into data destruction — the detector
  cannot tell a spike from a step. Clipping to the band edge preserves the
  direction and most of the magnitude of a real move. (Variant B's
  replace-with-mean raised replacements from 777 to 2,369.)

---

## Correction: my earlier 7.7% figure was wrong

The first version of this measurement counted clipped cells as
`(series != winsorized).sum()`. **`NaN != NaN` is `True`**, so every leading-NaN
cell counted as clipped. MCAP reported 1,429 clipped — exactly its 1,429 NaN
cells. Corrected to `((s != w) & s.notna()).sum()`.

Reconciling the three percentages that now exist for "the leak":

| figure | what it measures | status |
|---|---|---|
| 0.72% | earlier count on the **final `t2_master` output** (475,567 obs), whose denominator includes derived return sheets that never pass through `_clean_sheet` | valid, different denominator |
| 7.69% | source-workbook count, **NaN-inflated** | **retracted** |
| 0.804% | source-workbook count, cells `_clean_sheet` actually touches | **authoritative** |

0.72% and 0.804% agree to within their denominators. Only the 7.69% was an artifact.

The same `(series != winsorized)` pattern is in production at
`scripts/build_t2_master.py:309`, but it only feeds a log message — **no data is
affected**; the build log has simply been over-reporting how much it cleaned.

---

## Options

**(a) Do nothing.** Leak documented, magnitude known (0.804%, ~1% of cells would
move under any fix). Defensible: it is small, and for calibration the documented
T2 ElasticNet PIT incident — a 1-month date-convention error — fabricated
+5.1%/yr, which is a different order of severity.

**(b) Adopt variant E or F.** Fully causal, smaller footprint than today, no
trend destruction. Changes ~0.96% of cells. This is my recommendation. It is a
change of cleaning philosophy — "this step should only catch fat-fingers" — not a
bug fix, which is why it needs your sign-off.

**(c) Redesign in change-space.** Detect and repair outliers on log-differences,
then reintegrate. Most principled, but reintegration shifts every level after a
repair point — defensible for prices, wrong for valuation ratios and yields. That
is per-sheet-type semantics and a design call I should not make for you.

Whichever you pick, the change only takes effect at the next monthly rebuild.

---

## Files

- Report — [/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/docs/T2_CAUSAL_CLEANING_2026-08-21.md](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/docs/T2_CAUSAL_CLEANING_2026-08-21.md)
- Sweep script — [.../Data/work/experiments/t2_causal_clean_20260821/variant_sweep.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/work/experiments/t2_causal_clean_20260821/variant_sweep.py)
- Variant table — [.../variant_sweep.xlsx](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/work/experiments/t2_causal_clean_20260821/variant_sweep.xlsx)
- Per-sheet detail — [.../per_sheet_detail.xlsx](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/work/experiments/t2_causal_clean_20260821/per_sheet_detail.xlsx)
- Sweep log — [.../variant_sweep.log](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/work/experiments/t2_causal_clean_20260821/variant_sweep.log)
- First (superseded, NaN-inflated) measurement — [.../measure_causal_clean.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/work/experiments/t2_causal_clean_20260821/measure_causal_clean.py)
- **Reverted code** — [.../causal_patch_REJECTED.diff](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/work/experiments/t2_causal_clean_20260821/causal_patch_REJECTED.diff)
- Pre-Tier-1 backups — [/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/backups/tier1_20260821_010600/](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/backups/tier1_20260821_010600/)
