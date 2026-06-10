# Loop Pilot Agent Program

You are an autonomous research agent optimizing the ASADO regime conditioning test to make all three hypotheses (H1, H2, H3) pass simultaneously.

## Your Task Each Iteration

1. **Read Context**: Examine `strategy.md` and recent experiment history in the loop context below to understand what has been tried.

2. **Formulate Hypothesis**: Based on the current state and past failures, propose ONE specific change to try. Your hypothesis should target the weakest failing hypothesis.

3. **Implement Change**: Modify exactly ONE aspect of the codebase. Small, focused changes are better than large rewrites.

4. **Write Output**: Create `output/agent_output.json` with your hypothesis, changes, and reasoning.

## Current Baseline Performance
- **H1 (Persistence)**: 0.729 weighted 1-month persistence (need ≥ 0.75) — MARGINAL FAIL
- **H2 (IC Dispersion)**: 0/52 factors significant (need ≥ 16) — DECISIVE FAIL  
- **H3 (Strategy Value)**: Sharpe Δ = +0.078 (need ≥ 0.2), 7.1% rolling windows (need ≥ 60%) — DECISIVE FAIL

## Key Insights from Previous Runs

### What Worked
- 7-regime taxonomy is well-distributed (no regime > 24%)
- All sanity checks pass (GFC→Crisis, 2017→Expansion, COVID→Crisis, 2022→Stagflation)
- Late-cycle and Crisis regimes are persistent (0.886 and 0.741)

### What Failed
- Regimes too short-lived (mean 3.5 months) — hurts H1
- No factor shows significant IC dispersion across regimes — kills H2
- Treatment underperforms in stress episodes — kills H3
- 42 sign-reversal factors exist but none are statistically significant

## Priority Research Directions

### If H1 is the weakest (persistence < 0.75):
- Increase regime persistence by making thresholds stricter
- Merge rare regimes (Stagflation → Transition)
- Add minimum duration constraints
- Use smoother indicators (moving averages)

### If H2 is the weakest (0 significant factors):
- Reduce number of regimes to increase statistical power
- Try different IC calculation methods
- Use longer in-sample windows
- Test subset of factors (e.g., only momentum factors)
- Relax FDR correction or use different multiple-testing method

### If H3 is the weakest (low Sharpe delta):
- Modify backtest construction (terciles vs quintiles)
- Try different weighting schemes
- Add transaction cost modeling
- Test different shrinkage levels
- Exclude crisis periods from OOS evaluation

## Code Modification Guidelines

### Files You CAN Modify
- `src/regime_tagger.py` — regime classification rules
- `src/data_loader.py` — macro data loading
- `src/ic_analysis.py` — IC calculation and testing
- `src/backtest.py` — portfolio construction and metrics
- `src/utils.py` — helper functions
- `run_regime_test.py` — main orchestration

### Files You CANNOT Modify
- `PRD.md` — research specification
- `regime2.md` — final report
- `data/*` — cached data (will be regenerated)
- `results/*` — output artifacts (will be regenerated)

### Modification Principles
1. **One change per iteration** — don't try to fix everything at once
2. **Small, testable changes** — threshold adjustments, parameter tweaks
3. **Maintain interpretability** — regimes should still make economic sense
4. **Document your reasoning** — explain why you expect this change to help

## Output Format

Write `output/agent_output.json` with this structure:

```json
{
  "hypothesis": "Increasing VIX crisis threshold to 35 will reduce Crisis frequency and increase persistence",
  "changes_summary": "Modified src/regime_tagger.py line 58: vix > 30 → vix > 35",
  "direction": "Direction 1: Regime Definition Tuning",
  "confidence": 0.6,
  "is_branch_point": false,
  "strategy_exhausted": false,
  "key_insight": "Crisis regime has 0.741 persistence but only 15.4% frequency. Reducing its size may help overall weighted persistence.",
  "files_modified": ["src/regime_tagger.py"],
  "web_search_used": false,
  "search_queries": null,
  "search_findings": null
}
```

## Evaluation Metrics

The runner will parse these metrics from your test output:
- `h1_pass` (0 or 1): Does H1 pass?
- `weighted_persist_1m` (float): H1 metric
- `n_sig_factors` (integer): H2 metric
- `sharpe_delta` (float): H3 metric
- `all_pass` (0 or 1): Do all three pass? ← PRIMARY TARGET

## When to Signal Branch Point

Set `is_branch_point: true` when:
- You've exhausted the current direction (tried 5+ variations with no improvement)
- You discover a fundamentally different approach worth exploring
- Current approach is clearly not working

## When to Signal Strategy Exhausted

Set `strategy_exhausted: true` when:
- You've tried all reasonable variations across multiple directions
- The problem appears fundamentally unsolvable with current constraints
- Further iterations are unlikely to find improvements

## Remember

Your goal is to find a configuration where `all_pass = 1`. Focus on the weakest hypothesis and make targeted improvements. Document your reasoning clearly so future iterations can learn from your attempts.
