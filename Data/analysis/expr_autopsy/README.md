# Expression-Layer Autopsy (E1)

## Purpose

Determine where on the diffusion path the edge dies. Your program has PIT-proven signals but US-listed ETFs at US close show zero capture.

## Results to Date

### Base Case: Combiner → T2 Index

| Metric | Value |
|--------|-------|
| N observations | 169,113 |
| Rank IC | 0.0438 |
| Pre-2024 IC | 0.0460 |
| Post-2024 IC | 0.0285 |

**Verdict: EDGE EXISTS IN INDEX SPACE**

This is the BASE CASE. If IC were zero here, E1 would be done.

### Structural Break

The IC dropped from ~0.046 to ~0.029 around 2024, but **not to zero**. This suggests:
- Not all signals are equally affected
- Some countries retain stronger edges

### Top Countries by IC

| Country | IC |
|---------|----|
| Japan | 0.20 |
| Australia | 0.12 |
| Hong Kong | 0.09 |
| Taiwan | 0.09 |
| UK | 0.09 |

## What's Next

To complete E1, we need to compare against these expression spaces:

### 1. Local Index Futures (SGX, OSE, KRX, etc.)
- **Goal:** Measure capture at local session close
- **Data needed:** Bloomberg futures price series (e.g. NKY, KOSPI200, TWN, etc.)
- **Expected:** If IC here is similar to T2 index, capture exists in local hours

### 2. FX Forward
- **Goal:** Measure capture in currency markets
- **Data needed:** Bloomberg FX forward rates
- **Expected:** If signal is macro-driven, FX may retain edge

### 3. US-Listed ETF
- **Goal:** Measure capture at US close (the current null)
- **Data needed:** Bloomberg ETF close prices
- **Expected:** IC ≈ 0 (the problem we're trying to solve)

## Files

- `pre_computation_check.csv` - Base case results
- `expr_autopsy.py` - Pre-check script
- `expr_autopsy_analysis.py` - Full analysis
- `README.md` - This file

## Kill Criterion

If local futures IC < 0.015, E2 (futures overlay) is dead before we build the plumbing.

## Timeline

- **Week 1:** Pre-computation check (DONE - PASS)
- **Week 2-3:** Pull Bloomberg futures/FX data
- **Week 4:** Compute capture curves
- **Week 5:** Verdict on E2/E3
