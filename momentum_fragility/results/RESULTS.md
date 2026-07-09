# Momentum Fragility Index - Conditional Reversal Test - Results

## Executive Verdict

**Overall (core):** **FAIL - stopped at Gate 3 (decisive)**  
**Overall (full):** **FAIL - stopped at Gate 3 (decisive)**

Pre-registered decisive test (Gate 3): within the top-quartile-`12-1MTR_CS` (hot-momentum) subset, does higher Fragility predict lower forward 1M return, walk-forward OOS, pooled across countries? PASS = pooled Spearman <= -0.10 AND bottom-vs-top composite-quartile forward-return spread >= 50bp/month.

| Variant | Gate 1 persistence | Gate 2 vol-proxy | Gate 3 (DECISIVE) | Gate 4 robustness | Overall |
|---|---|---|---|---|---|
| core | persist 0.509 (ok) | |corr| 0.119 (clear) | **FAIL** rho=-0.0135, spread=-11.4bp (n=2108) | diagnostic (placebo rho=0.0051, collapsed) | **FAIL - stopped at Gate 3 (decisive)** |
| full | persist 0.521 (ok) | |corr| 0.148 (clear) | **FAIL** rho=0.0301, spread=-93.0bp (n=656) | diagnostic (placebo rho=0.0070, collapsed) | **FAIL - stopped at Gate 3 (decisive)** |

## Gate 3 detail (the pre-registered decisive metric)

### composite_core

- Walk-forward OOS pooled Spearman: **-0.0135** (p=0.537, n=2108, OOS years 2004-2026) -- threshold <= -0.1: **FAIL**
- Bottom(low-frag) minus Top(high-frag) forward-return spread: **-11.4 bp/month** (bottom 1.069% vs top 1.183%, n_bottom=541, n_top=482) -- threshold >= 50bp: **FAIL**
- Diagnostic per-country sign test (NOT a pass bar): 15/33 negative, sign-test p=0.757, median per-country rho=0.0132
- **Gate 3 core: FAIL**

### composite_full

- Walk-forward OOS pooled Spearman: **0.0301** (p=0.442, n=656, OOS years 2019-2026) -- threshold <= -0.1: **FAIL**
- Bottom(low-frag) minus Top(high-frag) forward-return spread: **-93.0 bp/month** (bottom 0.950% vs top 1.880%, n_bottom=159, n_top=159) -- threshold >= 50bp: **FAIL**
- Diagnostic per-country sign test (NOT a pass bar): 6/10 negative, sign-test p=0.377, median per-country rho=-0.0456
- **Gate 3 full: FAIL**

## Gate 4 robustness detail

### composite_core

- Role: **diagnostic only** (Gate 3 already FAILED -- there is no PASS to defend). The subsample sign not holding here reflects the absence of any signal (a true null has no stable sign), and the placebo collapsing to ~0 is expected; neither changes the verdict.
- Placebo (within-country date shuffle) pooled Spearman: 0.0051 -> collapsed toward zero: True; also-significant override: False
- Subsample sign stability (split 2013): pre_2013: rho=-0.0634 (n=925); post_2013: rho=0.0154 (n=1260) -> sign held: False
- Point-in-time discipline: pass (5 audited invariants)
- **Gate 4 core: not decisive (diagnostic)**

### composite_full

- Role: **diagnostic only** (Gate 3 already FAILED -- there is no PASS to defend). The subsample sign not holding here reflects the absence of any signal (a true null has no stable sign), and the placebo collapsing to ~0 is expected; neither changes the verdict.
- Placebo (within-country date shuffle) pooled Spearman: 0.0070 -> collapsed toward zero: True; also-significant override: False
- Subsample sign stability (split 2020): pre_2020: rho=-0.0505 (n=143); post_2020: rho=0.0200 (n=571) -> sign held: False
- Point-in-time discipline: pass (5 audited invariants)
- **Gate 4 full: not decisive (diagnostic)**

## Interpretation

- **core:** Gate 3 FAILED (pooled Spearman -0.0135 did not reach -0.1; spread -11.4bp did not reach 50bp). The frozen pre-registered spec does not show conditional reversal predictability. This is the answer -- no threshold/horizon sweeping is permitted (PRD section 0 anti-p-hacking rule).
- **full:** Gate 3 FAILED (pooled Spearman 0.0301 did not reach -0.1; spread -93.0bp did not reach 50bp). The frozen pre-registered spec does not show conditional reversal predictability. This is the answer -- no threshold/horizon sweeping is permitted (PRD section 0 anti-p-hacking rule).

## Recommendation

**STOP. Negative result.** Neither composite variant clears the decisive Gate 3. Do not productionize into `Step Nineteen` and do not integrate a fragility penalty into `Step Fourteen Target Optimization.py`. Written up honestly per this repo's negative-result culture.

## Artifacts

- `momentum_fragility/results/manifest.json`
- `momentum_fragility/results/fragility_scores.parquet`
- `momentum_fragility/results/gate1_persistence.parquet`
- `momentum_fragility/results/gate2_volatility.parquet`
- `momentum_fragility/results/gate3_lead.parquet`
- `momentum_fragility/results/gate4_robustness.parquet`
- `momentum_fragility/results/figures/*.pdf`
