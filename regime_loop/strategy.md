# Strategy: Regime Conditioning Optimization

## Goal
Find a configuration of the regime conditioning test where ALL THREE hypotheses pass:
- **H1**: Weighted 1-month persistence ≥ 0.75
- **H2**: ≥ 16 factors (30%) significant after BH-FDR correction (p < 0.10)
- **H3**: Sharpe delta ≥ 0.2 AND ≥ 60% of rolling 5-year windows beat baseline

## Current State (v2 baseline)
- H1: FAIL (0.729 vs 0.75)
- H2: FAIL (0/52 factors significant)
- H3: FAIL (Sharpe Δ = +0.078, 7.1% rolling windows)

## Research Directions (Priority Order)

### Direction 1: Regime Definition Tuning
- Adjust macro thresholds to create more persistent regimes
- Try different combinations of indicators
- Experiment with regime duration minimums
- Consider merging rare regimes (Stagflation) into others

### Direction 2: Factor Selection and Weighting
- Test different factor subsets (e.g., only value, only momentum)
- Modify IC calculation window (currently full in-sample)
- Try different IC estimators (Pearson vs Spearman)
- Experiment with factor preprocessing (winsorization, standardization)

### Direction 3: Backtest Methodology
- Adjust quintile construction (e.g., terciles instead)
- Modify rebalancing frequency (currently monthly)
- Try different weighting schemes within quintiles
- Experiment with transaction cost modeling
- Test different shrinkage levels

### Direction 4: Statistical Testing
- Adjust FDR correction method (BH vs Bonferroni vs Holm)
- Modify significance threshold (currently 0.10)
- Try bootstrap-based significance testing
- Experiment with different F-test variants

### Direction 5: Time Period Selection
- Test different in-sample periods (currently ≤2018-12)
- Try different OOS start dates (currently 2019-01)
- Experiment with rolling window sizes (currently 5-year)
- Consider excluding crisis periods from analysis

### Direction 6: Data Quality and Preprocessing
- Try different macro data sources or vintages
- Experiment with macro indicator transformations
- Test different missing data handling
- Consider adding derived macro features

### Direction 7: Portfolio Construction
- Try long-only instead of long/short
- Experiment with different position sizing
- Test sector/country neutrality constraints
- Try different risk management overlays

## Success Criteria
The primary success metric is `all_pass` (binary: 1 if H1 AND H2 AND H3 all pass, 0 otherwise).
Secondary metrics track progress on individual hypotheses.

## Constraints
- Do NOT modify the core T2 factor data or returns
- Do NOT change the fundamental 34-country universe
- Keep the regime tagger deterministic (no ML classifier yet)
- Maintain interpretability of regime definitions
