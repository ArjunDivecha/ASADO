# PRD: Regime Conditioning Value Test for ASADO

**Author:** Arjun  
**Owner:** Claude Code  
**Status:** Ready to build  
**Estimated effort:** 3-5 days

---

## 1. Context and objective

ASADO currently weights factor signals without regard to market regime. Before investing in any regime classification architecture (CNN, LLM, or otherwise), we need to empirically establish whether regime-conditional factor weighting would improve performance on the 34-country panel.

**Objective:** Determine whether deterministic regime tags meaningfully improve ASADO's risk-adjusted returns, and quantify the magnitude of improvement, so that subsequent architectural decisions can be made on evidence rather than assumption.

**Not the objective:** Building a regime classifier, training any models, or implementing this in production ASADO. This is a research test.

## 2. Hypothesis being tested

**H1 (persistence):** Regimes defined by deterministic macro indicators persist with P(same regime next month) ≥ 0.75.

**H2 (conditional IC dispersion):** For the 53 T2 factors, mean IC differs significantly across regimes for at least 30% of factors (p < 0.05 via F-test, with multiple testing correction).

**H3 (strategy value):** A regime-conditional ASADO variant that re-weights factors by historical regime-conditional IC improves Sharpe by ≥ 0.2 vs unconditional baseline over the full sample, with consistent improvement across rolling 5-year windows.

## 3. Decision framework

| Result | Interpretation | Next action |
|--------|----------------|-------------|
| H1, H2, H3 all hold | Regime conditioning adds material value | Build deterministic regime classifier into production ASADO; consider ML enhancements later |
| H1, H2 hold but H3 fails (Sharpe gain < 0.2) | Regime structure exists but weighting scheme doesn't capture it | Try alternative conditioning schemes (sizing modulation, exposure caps) before abandoning |
| H2 fails (no IC dispersion) | Regimes don't meaningfully differentiate factor performance | Abandon regime concept for ASADO; pursue alternative alpha sources |
| H1 fails | Regimes are too unstable to act on | Reconsider regime definitions or abandon |

## 4–10. (Full PRD — see user message / regime_test_summary for execution results)
