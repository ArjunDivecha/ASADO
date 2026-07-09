# Regime-Conditional Factor Selection Test — Results

## Executive Verdict

**Overall:** **NULL — 0 of 74 tested factors clear FDR (α=0.10). Pre-registered null-result branch (PRD section 6, "<8 factors").**

The decisive question (PRD Objective B): conditioned on each country's OWN industrial-production regime state (Growth / Recession / Neutral), does any T2 factor's within-date rank-IC slope differ significantly by regime? Answer: **no factor does.** The placebo confirms the test machinery is well-calibrated (it does not manufacture significance), so this is a genuine null, not a data-insufficiency result and not a pipeline artifact.

| Branch | Included factors | Pass FDR (α=0.10) | Smallest bootstrap p | Smallest FDR-adj p | Raw p<0.10 (vs ~7.4 by chance) |
|---|---:|---:|---:|---:|---:|
| **IP (PRIMARY)** | 74 | **0** | 0.022 | 0.362 | 18 |
| Placebo (IP labels shuffled) | 74 | **0** | 0.002 | 0.361 | 8 |
| GDP (EXPLORATORY, separate family) | 74 | **0** | 0.023 | 0.565 | 11 |

## Country coverage — enough to trust the test?

**Yes. 34 of 34 T2 countries got usable IP-YoY labels** — well above PRD section 6's "<10 countries → data insufficiency" floor, so this is a *tested-and-failed* result, not an *untested* one. 31 Bloomberg IP tickers were pulled (all accepted); the 34 count arises because US/NASDAQ/US SmallCap share `IP YOY Index` and ChinaA/ChinaH share `CHVAIOY Index` (Hong Kong has its own ticker), exactly the mapping PRD section 2.1 specifies. Per-country history depth varies (Australia only 27 months, Switzerland 85, vs 329 for the US) — thin-history countries simply contribute fewer post-warm-up rows, and 58 of the 74 tested factors still used the full 34-country cross-section (the rest 29–33).

## The primary IP-based test

**0 of 74 included factors pass Benjamini-Hochberg FDR at α=0.10.** There are no passing factors to list.

- **9 of the 83 curated factors were structurally excluded** (non-tunably, before any p-value was seen): the Agriculture / Copper / Gold / Oil variants have **zero cross-sectional dispersion** — the same commodity value is broadcast to every country each month, so a *within-date cross-sectional* rank-IC test is mathematically undefined for them. Excluded: `Agriculture 12_TS`, `Agriculture_TS`, `Copper 12_TS`, `Copper_TS`, `Gold 12_TS`, `Gold 12_CS`, `Gold_TS`, `Oil 12_TS`, `Oil_TS`. The remaining 74 all cleared the ≥20-obs-per-regime-bucket minimum, so nothing was dropped for cell size.
- The three factors that came *closest* (still comfortably non-significant, shown only for transparency — **not** a passing set):

  | Factor | β(signal×Growth) | β(signal×Recession) | Joint F | Bootstrap p | FDR-adj p | Cells G/R/N |
  |---|---:|---:|---:|---:|---:|---|
  | Operating Margin_TS | −0.0039 | +0.0681 | 4.52 | 0.022 | 0.362 | 2014 / 2968 / 3313 |
  | Best PBK_CS | −0.0820 | −0.0523 | 3.95 | 0.022 | 0.362 | 1600 / 2551 / 2715 |
  | Best ROE_TS | +0.0122 | +0.0686 | 3.40 | 0.024 | 0.362 | 1591 / 2547 / 2698 |

  The smallest raw bootstrap p is 0.022. BH needs the top-ranked p ≤ 0.10 × 1/74 ≈ 0.00135 to reject even one factor — 0.022 is ~16× too large — so every FDR-adjusted p lands at ~0.36. This is a legitimate FDR outcome, not a borderline miss.

**One honest caveat worth stating plainly:** 18 of 74 factors have a *raw* (uncorrected) bootstrap p<0.10, against ~7.4 expected by pure chance. That is a faint hint of *some* diffuse regime-conditional structure — but it is exactly what FDR exists to discipline, and the placebo (below) adjudicates it.

## Placebo — does the null survive label-shuffling?

Each country's regime-label *sequence* was independently permuted (frozen seed 20260705), preserving that country's exact Growth/Recession/Neutral marginal frequencies while destroying the true date alignment. The **identical** pipeline was rerun — same factor panel, same within-date ranks, same interaction regression, same wild-cluster bootstrap (seed 42, B=999), same FDR at α=0.10. Only the regime column changed.

- **Placebo: 0 of 74 pass FDR** — same as the real test.
- **The excess raw structure collapses to chance:** the real test's 18 raw-p<0.10 hits fall to **8** under shuffling — right at the ~7.4 expected by chance. The faint above-chance signal in the real test therefore reflected *real* (if diffuse and FDR-insignificant) date-aligned structure, and the machinery does **not** conjure significance from noise.
- **Reading:** the placebo neither invalidates nor rescues the result. Both real and placebo pass 0 factors, so the null stands on its own; and because the placebo doesn't inflate the pass count, the null is not a pipeline artifact. (Had the real test shown ≥8 passes *and* the placebo a similar count, that would have flagged an artifact and overridden any apparent PASS — it did not, and there was no PASS to override.)

## GDP exploratory comparison (non-primary)

Run separately on all 34 countries using annual GDP growth (Jul-1 labels, +6-month point-in-time lag, forward-filled 12 months), with its **own** `multipletests()` call — **never pooled into the IP FDR family** (PRD section 2.1). Result: **0 of 74 pass FDR** (smallest bootstrap p 0.023, smallest FDR-adjusted p 0.565, 11 raw p<0.10). It corroborates the primary null but carries less weight: GDP is annual, lower-frequency, and forecast-vintage-contaminated, so it is context, not evidence.

## Garden-of-forking-paths accounting (PRD section 4)

The FDR correction disciplines the 74-factor family — **it does not account for the researcher choices upstream of it.** Building this test required decisions the correction never saw: IP vs. GDP as the classifier instrument, the 30/40/30 percentile split, the 24-month expanding-window minimum, the within-date rank-and-standardize transform, the wild-cluster bootstrap over asymptotic SEs, and the ≥20-obs cell floor. Each is a defensible, pre-registered, frozen-before-running choice — but collectively they are additional implicit tests. **The α=0.10 FDR result should not be read as if it had corrected for all of them.** That said, the direction of the finding (a clean null) makes this caveat comforting rather than worrying: it means the null is not the product of a lucky path through those forks.

## Git provenance

- ASADO repo root: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO`
- HEAD at write time: **`2ddbe030e4f1c716c8ef72956e6665a24ff0177c`** (2026-07-05 11:52:24 −0700)
- **Caveat (honest, per PRD section 4's silent-overwrite warning):** the `regime_factor_selection/` module is **untracked** (`git status '??'`) at write time — the code that produced these results is *not yet committed*, so the HEAD hash above is the repo's HEAD, not a commit that contains this module. **Commit the module to make this stamp binding.** This is exactly the `regime2.md`-vs-`regime.md` failure mode the PRD exists to prevent; flagging it rather than papering over it.

## Recommendation (one line, PRD section 6 decision table)

**STOP — pre-registered null: 0/74 factors clear FDR (α=0.10), placebo confirms the machinery is calibrated; there is no genuine per-country regime-conditional factor-selection edge in this data. Do not sweep the classifier split, FDR α, or cell-size floor, and do not proceed to Phase 2.**

## Artifacts

- `regime_factor_selection/results/manifest.json`
- `regime_factor_selection/results/factor_test_results.parquet` (IP primary)
- `regime_factor_selection/results/factor_test_results_gdp_exploratory.parquet` (GDP exploratory)
- `regime_factor_selection/results/placebo_results.parquet`
- `regime_factor_selection/results/regime_labels_ip.parquet`, `regime_labels_gdp.parquet`, `ip_panel.parquet`, `ip_pull_log.csv`, `ip_ticker_map.json`
- `regime_factor_selection/results/figures/pvalue_histogram_ip.pdf`
- `regime_factor_selection/results/figures/pvalue_histogram_real_vs_placebo.pdf`
- `regime_factor_selection/results/factor_test_summary.json`, `placebo_summary.json`
- Code: `run_factor_regime_test.py`, `run_placebo_test.py`, `build_regime_classifiers.py`, `pull_industrial_production_bbg.py`
