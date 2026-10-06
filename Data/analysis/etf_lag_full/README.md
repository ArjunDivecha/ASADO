# ETF LAG FULL TEST Results

**Date:** 2026-10-05

## The Question

When local markets have big moves (|return| > 2%), does the ETF catch up over the following days, or does it stay behind?

## Key Findings

### On Big Move Day (T+0)

| Metric | Value |
|--------|-------|
| Mean local return | +0.20% |
| Mean ETF return | +0.03% |
| **Mean gap (local - ETF)** | **+0.17%** |

**The ETF lags by 0.17% on average.**

### After Big Move

| Metric | Value |
|--------|-------|
| ETF T+1 return | 0.03% |
| ETF T+5 return | 0.11% |
| **Gap closes by 50%+ in 5 days** | **74.4%** |

**The ETF DOES catch up - 74% of gaps close within 5 days.**

### Directional Breakdown

#### Up Moves (local > 0)
- Mean local return: +3.04%
- Mean ETF T+0: +0.65%
- Mean gap: +2.39%

#### Down Moves (local < 0)
- Mean local return: -3.05%
- Mean ETF T+0: -0.68%
- Mean gap: -2.37%

## What This Means

1. **The lag is real**: ETF under-reacts on big move day
2. **The lag closes**: 74% of gaps close within 5 days
3. **Exploitable window**: There's a 1-5 day window to capture the gap

## Why This Happens

**Up moves:** When local markets surge 3%+, ETF only captures ~0.65% on that day. The ETF needs 5+ days to fully catch up.

**Down moves:** Same pattern but negative - ETF under-reacts to crashes too.

## Implications for Trading

This supports the ETF lag hypothesis:

1. **When local > ETF today**: Gap likely closes in 3-5 days
2. **Strategy**: Go long ETF when you expect gap to close
3. **Horizon**: 3-5 days to let ETF catch up

## Files

- `etf_lag_full_test.py` - Analysis script
- `full_test_results.csv` - Full data
