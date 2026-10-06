# ETF LAG TEST: Does Combiner Predict Gap Closing?

**Date:** 2026-10-05

## The Question

We know ETF gaps close 74% of the time. But can the combiner signal help us identify which gaps are safe to take?

## Results

| Prediction | IC | Verdict |
|------------|-----|---------|
| **Gap closure (binary)** | **-0.006** | **Cannot predict** |
| Gap size | 0.198 | Strong predictor |
| ETF return in 5 days | 0.005 | Cannot predict |
| Local return (baseline) | 0.125 | Predictor |

## Key Finding

**The combiner CANNOT predict whether a gap will close.**

The IC for predicting gap closure is -0.006 - essentially zero.

## What the Combiner DOES Predict

The combiner predicts **gap SIZE** with IC = 0.198:

| Combiner Decile | Gap Size | Closure Rate |
|-----------------|----------|--------------|
| Low (0) | -0.83% | 79.8% |
| High (9) | +1.63% | 78.1% |

**The gap size varies with the signal, but the closure rate does not.**

## Bottom Line

**The ETF lag is NOT predictable by the combiner.**

The gap closes ~78% of the time regardless of what the combiner says. This means:
- The lag exists (ETF under-reacts)
- The gap usually closes (78% of time)
- But the combiner doesn't help pick which gaps to take

This is a **market microstructure effect**, not a signal-based opportunity. The gap is mechanical (time zone, market maker pricing) rather than driven by fundamentals.

## Files

- `etf_lag_combiner_test.py` - Analysis script
- `combiner_test_results.csv` - Full data
