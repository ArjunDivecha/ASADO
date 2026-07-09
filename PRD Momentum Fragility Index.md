# PRD: Momentum Fragility Index — Conditional Reversal-Risk Test

**Author:** Arjun (spec drafted with Claude)
**Owner:** Claude Code (build + run)
**Status:** Ready to build
**Location:** `ASADO/momentum_fragility/` (new module, sibling to `regime/` and `regime_ew/`)
**Estimated effort:** 4-6 days

---

## 0. Read this first — what failed before, and why this is different

Two related tests already ran in this warehouse. Do not rebuild either.

1. **`ASADO/regime/`** (global 7-regime US-macro tagger reweighting the 52 `_CS` factors) — **failed decisively** (`regime2.md`: 0/52 factors significant after FDR). Root cause: T2's cross-sectional factors derive alpha from *relative* country positioning; a *global* macro state can't reorder that ranking.

2. **`ASADO/regime_ew/`** (per-country Gaussian HMM early-warning test, `PRD Per Country Regime EarlyWarning.md`) — already run. Gate 1 (persistence, 0.926) and Gate 2 (not a vol proxy, corr 0.152) **passed**. Gate 3 — does the adverse-state probability lead that *same* country's own forward return, walk-forward OOS — **failed** (17/34 negative vs. a 23/34 bar; median Spearman ≈ -0.003; spread wrong-signed). The full-sample (non-walk-forward) diagnostic version of the same test *did* look significant (23/34 negative, p=0.029) — exactly the false-positive pattern this house's gate discipline exists to catch, mirroring the `regime/` v1→v2 reversal (fixing one data bug flipped a PASS to a FAIL).

**Why this test is not just `regime_ew` again:** `regime_ew` tested an *unconditional* claim on a *narrow* 6-feature set (momentum, REER, RSI14, PE, inflation, ROE — no crowding, no valuation de-rating, no concentration, no factor-correlation stress). This test operationalizes a specific Bernstein sell-side thesis (Asia momentum reversal risk, verified against the source PDF): fragility matters *conditionally* — specifically for countries **already in a hot-momentum state**. That is a materially narrower, different hypothesis (an interaction effect, not a main effect).

**Guardrail against p-hacking (non-negotiable):** testing a conditional hypothesis after watching the unconditional one fail is a textbook setup for post-hoc rationalization. This PRD freezes the exact spec — composite formula, momentum-subset threshold, primary horizon — *before* Gate 3 is run. Do not sweep thresholds/horizons and report the best; if the frozen spec fails, that is the answer.

This is a **research test with hard kill-gates**, not a production build. If a gate fails, stop and write the negative result.

---

## 1. Objective

For each of the 34 T2 countries, each month, compute a **composite Fragility score** (continuous, cross-sectionally and time-series z-scored) from momentum, earnings-revision proxy, valuation, valuation de-rating, factor-correlation stress, crowding, and concentration.

**Test one pre-registered question:** among country-months in the **top quartile of `12-1MTR_CS`** (already-hot momentum), does a higher Fragility score predict **lower forward 1-month return**, out-of-sample, pooled across countries?

**Not the objective:** an unconditional "fragility predicts returns in general" claim (already tested and failed in `regime_ew`), a production classifier, or any model training.

---

## 2. Data — reuse the existing harness, do not re-query from scratch

Import from `ASADO/regime/src/data_loader.py` and `ASADO/regime/src/utils.py`:
- `load_factor_panel(factors=...)`, `load_country_returns(horizons=("1MRet","3MRet"))`, `build_forward_returns(returns, horizon)`, `list_t2_factor_variables()`, `T2_COUNTRIES`.
- **Convention, must match exactly:** in `t2_master`, `1MRet@t` is already the forward return (== next month's realized return). Signal[t] pairs with `1MRet[t]` directly — no extra shift. Confirm against `build_forward_returns`.
- Read-only duckdb always: `duckdb.connect(WAREHOUSE, read_only=True)`.

### 2.1 Composite components (pre-registered, do not add/remove after seeing Gate 3 results)

| # | Component | Source | Notes |
|---|---|---|---|
| 1 | Momentum level | `t2_master.12-1MTR_CS` | reuse directly |
| 2 | Earnings-revision proxy | derived: 1M % change in `t2_raw.BEST EPS` (raw, un-normalized level) | new transform, zero new pull; CS/TS z-score after computing |
| 3 | Valuation level | `t2_raw.Trailing PE` (raw) | **NOT `t2_master`'s `Best PE _CS`** — confirmed substituted with a specific-return reversal signal (Step Two v2.1 docstring, live-data-verified 2026-07-05). **NOT `t2_raw.Best PE` either** — live-verified 2026-07-05 to diverge ~3x from Trailing PE and from Bernstein's own reported Korea forward PE, unresolved discrepancy, avoided per explicit decision. CS/TS z-score, sign-inverted (lower PE = healthier, higher = more fragile) |
| 4 | Valuation de-rating | derived: 1M change in `t2_raw.Trailing PE` | new transform, zero new pull |
| 5 | Factor correlation stress | derived: rolling 6-month correlation between the momentum factor's country-portfolio return series (Step Four's per-factor monthly net returns) and value/quality/low-vol factor return series | new transform, zero new pull |
| 6 | Crowding | `bloomberg_factors.MS_ETF_NetFlow_to_MarketCap`, `MS_Passive_Flow_Distortion`, `MS_Index_Weight_Change` | reuse directly; **available from 2015 only** |
| 7 | Concentration | new Bloomberg pull: BQL `holdings('<country ETF> US Equity')` → top-5 weight + GICS sector aggregation (tech %) | live-verified 2026-07-05 (Taiwan top-5=38.1%, Korea top-5=56.2%, GICS tagging clean); **weights reliable only from ~2016-06-30 onward, degrade to zero at 2015-06-30, hard-fail before 2010** — see §2.2 |

**Explicitly deferred** (limit researcher degrees of freedom): GDELT sentiment/attention features. Add only as a later ablation if the core composite passes.

### 2.2 Two composite variants — test both, do not silently pick one

- **Core composite** (components 1, 2, 3, 4, 5 only): full 2000+ history, no crowding/concentration.
- **Full composite** (all 7 components): ~2016+ only, given components 6 and 7's shorter history.

Report Gate 3 results for **both** variants separately. Do not blend a 2000-2015 partial-composite (missing 2 of 7 components) with a 2016+ full-composite inside the same "simple average" — that silently changes what's being measured pre/post cutover.

### 2.3 Concentration data pull (component 7 — new Bloomberg ingestion)

Verified working pattern (live-tested 2026-07-05, Bloomberg Terminal connected via OpusBloomberg):
```python
# BQL over //blp/bqlsvc with EXCEL clientContext unlock (see bloomberg-skill/references/bql.md)
expr = f"get(id(), weights()) for(holdings('{etf_ticker}', dates='{date_str}'))"
# etf_ticker per country, e.g. Taiwan='EWT US Equity', Korea='EWY US Equity'
# then ref_batch(constituent_tickers, ['GICS_SECTOR_NAME']) for sector aggregation
```
Note: `holdings()` date parameter goes on the universe call, not on `weights()` (tested: `weights(dates=...)` raises `VALIDATION_PARAMETER_NO_MATCH`). Pull quarterly snapshots (not monthly — holdings don't change that fast, and this is a licensed/quota-metered pull) from 2016-06-30 forward for all 34 countries' corresponding ETFs; forward-fill between quarters. Map each of the 34 T2 countries to its representative ETF ticker (already present in `AssetList.xlsx`'s `Yahoo`/`Bloomberg` sheets per earlier research — reuse that map, don't re-derive it).

### 2.4 Per-country standardization

Per-country **expanding** z-score (min 24 months) before use — never full-sample. This is the same rule `regime_ew` used and the same reason: converts "vs peers this month" into "vs this country's own history," and avoids look-ahead.

---

## 3. Composite construction

Composite = simple average of the z-scored, sign-oriented components (higher = more fragile) listed in §2.1/§2.2. State explicitly in the run log if this changes to a PCA-weighted average — do not switch silently mid-analysis.

**Momentum subset (pre-registered, frozen):** top quartile of country-months ranked by `12-1MTR_CS`, computed cross-sectionally each month across the 34-country panel.

**Primary horizon (pre-registered, frozen):** forward `1MRet`. Report `3MRet`/`6MRet` as secondary diagnostics only, never as an alternate pass condition.

---

## 4. Hard kill-gates (evaluate in order; stop at first fail on the primary Gate 3 test)

### GATE 1 — Composite isn't just noise
Bucket the composite into terciles; check reasonable persistence (adapt `regime/src/regime_tagger.py::persistence_stats` to a 3-bucket continuous score rather than an HMM state). No fixed pass bar required here — report and move on unless it's degenerate (e.g., >95% in one bucket).

### GATE 2 — Not simply a relabeled volatility signal
Correlate the composite with trailing 6-month realized return volatility. Report median correlation; flag prominently (don't auto-fail) if |corr| > 0.7.

### GATE 3 (decisive) — Does fragility predict reversal, conditional on hot momentum?
Within the pre-registered top-momentum-quartile subset, walk-forward OOS (annual refit; expanding-window standardization only; train only on data before the prediction year — mirror `regime_ew`'s walk-forward discipline exactly):

- **Primary metric: POOLED panel test**, not a per-country sign test. Pool all qualifying (top-momentum-quartile) country-months across the 34-country panel and compute pooled Spearman rank correlation between the Fragility composite and forward `1MRet`. This is a deliberate adaptation from `regime_ew`'s per-country sign-test bar (23/34) — subsetting to top-momentum-quartile shrinks the per-country sample too thin for a meaningful per-country sign test.
- **Secondary/diagnostic only**: per-country sign test using `regime_ew/src/ew_model.py`'s `_spearman()`/`gate3_lead()` pattern, reported but not the pass/fail bar.
- **Economic check**: mean forward `1MRet` in the top-quartile-fragility vs. bottom-quartile-fragility subset of the momentum-quartile sample (a spread), reported in %/month.
- **PASS condition:** pooled Spearman ≤ -0.10 AND spread ≥ 50bp/month (pre-cost), on the walk-forward OOS sample. Report both the Core composite and Full composite results separately — a variant can pass or fail independently.

### GATE 4 — Robustness (mandatory before declaring any PASS)
- **Placebo:** shuffle the date index within each country, re-run Gate 3. The pooled Spearman must collapse toward zero. If the placebo also "passes," the result is a pipeline artifact — fail it.
- **Subsample stability:** split at 2013 (Core composite) / split the 2016-2026 sample at 2020 (Full composite). Sign of the effect must hold in both halves (may weaken, must not flip).
- **Point-in-time discipline:** confirm no full-sample standardization, no full-sample HMM/regression fit, and that the momentum-quartile subsetting itself uses only information available at time t (cross-sectional rank at t, not a look-ahead-contaminated rank).

---

## 5. Outputs

Write to `momentum_fragility/results/`:
- `fragility_scores.parquet` — `date, country, composite_core, composite_full, momentum_quartile, component_values...` (walk-forward OOS)
- `gate1_persistence.parquet`, `gate2_volatility.parquet`, `gate3_lead.parquet`, `gate4_robustness.parquet`
- `manifest.json` — machine-readable PASS/FAIL per gate, per composite variant, with key numbers
- `RESULTS.md` — human verdict in the same spirit as `regime_ew`'s `RESULTS.md`: Gate 1-4 PASS/FAIL table, headline metric + threshold for each, honest interpretation, one-line recommendation
- Figures: per-country fragility timelines for Taiwan/Korea (illustrative), histogram of pooled Gate-3 correlations, Core vs Full composite comparison

---

## 6. Decision framework

| Outcome | Interpretation | Next action |
|---|---|---|
| Gates 1-4 all PASS (either variant) | Conditional fragility signal genuinely predicts momentum reversal | Productionize into T2 as `Step Nineteen Momentum Fragility Index.py`, integrate into `Step Fourteen Target Optimization.py` as a linear penalty term (see T2 repo plan file) |
| Gate 3 fails (both variants) | Fragility does not predict reversal even conditionally | Stop. Negative result, written up honestly. Do not proceed to production integration |
| Gate 3 passes but Gate 4 fails (placebo/subsample) | Apparent effect is an artifact | Stop. Document exactly which check caught it |
| Gate 2 flags high vol-correlation | Signal may be mostly a vol proxy | Note in RESULTS.md; if Gate 3 also passes, consider reframing as a risk/vol overlay rather than alpha, as a separate follow-up question |

## 7. Build notes for Claude Code

- New module `momentum_fragility/`, importing from `regime/src/` (`data_loader`, `utils`, `regime_tagger.persistence_stats`) and `regime_ew/src/ew_model.py` (`_spearman`, `gate3_lead` pattern). Do not duplicate the loaders.
- `momentum_fragility/run_fragility_test.py` orchestrates: load → derive components → build Core + Full composites → Gate 1 → Gate 2 → Gate 3 (both variants) → Gate 4 → write `RESULTS.md`. Each gate prints PASS/FAIL; short-circuit reporting but still write what was computed, mirroring `regime_ew/run_ew_test.py`.
- Read-only DuckDB always (`read_only=True`).
- Concentration data pull is a separate, one-time script (`momentum_fragility/pull_concentration_bbg.py`) run under the OpusBloomberg conda env (`conda run -p ".../OpusBloomberg/.venv" python3 ...`), writing a cached parquet that the main test script reads — do not re-pull Bloomberg data on every test run.
- Fixed random_state/deterministic where applicable; persist intermediate composite scores so gate results are reproducible without recomputation.
