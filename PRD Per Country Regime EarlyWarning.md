# PRD: Per-Country Regime Early-Warning Test

**Author:** Arjun (spec drafted with Claude)
**Owner:** Claude Code (build + run)
**Status:** Ready to build
**Location:** `ASADO/regime_ew/` (new module, sibling to `regime/`)
**Estimated effort:** 1–2 days

---

## 0. Read this first — what failed before, and why this is different

The existing `ASADO/regime/` module already tested **regime conditioning** and **failed** (`regime2.md`). Do **not** rebuild that. The failure was specific and structural, and it dictates the design here.

What was built before: a **global, rule-based, 7-regime US-macro tagger** (`regime/src/regime_tagger.py` — inputs are VIX, BAA OAS, 2s10s, fed funds, NBER, Sahm, CPI, Michigan sentiment; one label per *month* applied to all 34 countries). It was used to **re-weight cross-sectional T2 factors**. Verdict: H2 (conditional IC dispersion) = **0/52 factors significant** after FDR.

Two facts from that history that constrain this build:

1. **The v1→v2 reversal.** `regime.md` (v1) reported H2 **PASS** (21/52 significant); `regime2.md` (v2) reported H2 **FAIL** (0/52). The *only* change was fixing broken macro inputs (a bad HY-OAS proxy and a mislabeled PMI series). **Conclusion: this domain manufactures false-positive regime signal when the regime tags are noisy.** A per-country monthly HMM produces *noisier* tags than the global rule tagger. Therefore any positive result here is guilty until proven innocent.

2. **Why a per-country approach is nonetheless not what failed.** The structural killer in `regime2.md` was: a *global* macro state cannot reorder a *cross-sectional* ranking, so it cannot change which country looks attractive vs peers. A **per-country** state is a statement about that one country's own dynamics and is not subject to that argument. Both prior reports' root-cause sections explicitly name "time-series conditioning / country-specific overlays" as the unexplored promising direction. **This test is that direction.**

This is a **research test with hard kill-gates**, not a production build. If a gate fails, stop and write the negative result. Do not tune until it passes.

---

## 1. Objective

For each of the 34 T2 countries, fit an **unsupervised** latent-state model (Gaussian HMM) on monthly features, producing per country per month:

- a **regime label** (most likely latent state),
- a **posterior probability vector** over states,
- the country's **transition matrix**.

Define an **early-warning signal** = the smoothed posterior probability of the country's *adverse* state, and its month-over-month slope.

**Test one question:** does that early-warning signal, observed at month *t*, **lead that same country's own forward returns**? This is a **time-series, per-country** test — never cross-sectional.

**Not the objective:** building a production classifier, training any LLM, or re-weighting factors. (An LLM explainer is a *possible downstream* step, explicitly out of scope here and contingent on this test passing.)

---

## 2. Data — reuse the existing harness

All of this already exists in `ASADO/regime/src/data_loader.py`. **Import and reuse; do not re-query from scratch.**

- `load_factor_panel()` → tidy `date, country, factor, value` for the 52 `_CS` factors from `t2_master`. Cached at `regime/data/processed/t2_factors_cs.parquet`.
- `load_country_returns(horizons=("1MRet","3MRet"))` → `date, country, horizon, ret` from `t2_master`. Cached at `regime/data/processed/country_returns.parquet`.
- `build_forward_returns(returns, horizon)` → `date, country, fwd_ret`.
- `T2_COUNTRIES` constant in `regime/src/utils.py`.

**Critical convention (from the DB map, do not get this wrong):** in `t2_master`, `1MRet@t` is the **forward** return — `1MRet@t == 1MTR@t+1`. It is already the forward dependent variable. So the signal at month *t* pairs with `1MRet@t` directly (no extra shift). Confirm this against `data_loader.build_forward_returns`, which already encodes the pairing — match its convention exactly so signal/return alignment is identical to the prior study.

### 2.1 Feature set (per country, monthly)

Use a **small, economically distinct** set of `_CS` features so each country has enough history per estimated parameter. Start with **6**:

1. a momentum factor — use the longest-horizon trailing return `_CS` available in `t2_master` (e.g. `12-1MTR_CS` if present; otherwise nearest equivalent — **discover via `SELECT DISTINCT variable`, do not assume the exact string**),
2. `REER_CS`,
3. `RSI14_CS`,
4. `Best PE _CS` (valuation),
5. `Inflation_CS`,
6. a GDELT risk feature if monthly-available for the country, else a second valuation/quality `_CS` (e.g. `Best ROE_CS`).

**Per-country standardization:** within each country, z-score each feature over an **expanding** window (min 24 months) before fitting, so the HMM sees comparable scales and there is **no look-ahead** (never standardize using full-sample mean/std). Drop a country-month if >2 of 6 features are missing; forward-fill single gaps up to 1 month only.

> Note: `_CS` features are *already* cross-sectional z-scores. Re-standardizing them per-country in time is intentional — it converts "vs peers this month" into "vs this country's own history of its peer-ranking," which is the time-series view the HMM needs. Document this clearly in code comments.

---

## 3. Model — per-country Gaussian HMM

Library: `hmmlearn` (`GaussianHMM`, `covariance_type="diag"`). Add to `regime_ew/requirements.txt`.

For each country independently:

- Fit `GaussianHMM(n_components=K, covariance_type="diag", n_iter=200, random_state=0)` on the country's monthly feature matrix.
- **K selection:** fit K ∈ {2, 3} and select by **BIC** per country. Do **not** force K=3 everywhere — short-history / structurally-quiet countries (some EM sleeves; `NASDAQ`, `US SmallCap`) will degenerate at K=3. Cap at K=3; this is early-warning, not a fine-grained taxonomy.
- **Identify the "adverse" state post-hoc** (HMM state numbering is arbitrary / not identified). Label as adverse the state with the **lowest mean realized contemporaneous return** for that country (join states to that country's `1MTR`-equivalent realized return and pick the worst-mean state). Record the mapping per country.
- Use **`predict_proba`** (smoothed posteriors) for the probability vector. The early-warning signal is `P_adverse[t]` and `dP_adverse[t] = P_adverse[t] - P_adverse[t-1]`.

### 3.1 Determinism / leakage discipline

- Fit on history only where feasible; at minimum, **report both** (a) full-sample fit and (b) a walk-forward / expanding re-fit (annual re-fit, predict the next 12 months out-of-sample). The walk-forward result is the one that counts for the gates. Full-sample is diagnostic only.
- Fixed `random_state`. Persist fitted params per country so runs are reproducible.

---

## 4. Hard kill-gates (evaluate in order; stop at first fail)

### GATE 1 — Persistence floor (the H1 problem, worse here)

The global tagger only reached ~3.5–4.6 month mean durations and **failed/marginal** the 0.75 persistence bar. A faster-flipping per-country signal is noise.

- Compute, **per country**, 1-month state persistence and mean regime duration. **Reuse `regime/src/regime_tagger.py::persistence_stats`** logic (or import it) so the metric is identical to the prior study.
- **PASS condition:** median-across-countries weighted 1-month persistence **≥ 0.75**, AND ≥ 60% of countries have mean adverse-state duration ≥ 3 months.
- If FAIL: the latent states are too unstable to early-warn. Stop. Write negative result.

### GATE 2 — "Is this just a volatility forecast in disguise?"

If the adverse state is merely "high-vol months," you've built a vol predictor, not a return predictor — useful but a different product, and it must be labeled honestly.

- For each country, correlate `P_adverse[t]` with that country's trailing realized return volatility (rolling 6m std of `1MTR`).
- **Report** the median correlation. If median |corr| > 0.7, **flag prominently**: "early-warning signal is substantially a volatility state." This does **not** auto-fail, but it reframes the deliverable and changes Gate 3 interpretation (a vol signal predicting returns is suspicious; investigate whether the return-lead is just the vol risk premium).

### GATE 3 — Does the signal LEAD own-country forward returns? (the actual test)

Pure **time-series, within-country**. Never pool cross-sectionally for the headline test.

For each country, align signal at *t* with forward return:

- **Primary metric:** Spearman rank correlation between `P_adverse[t]` (and separately `dP_adverse[t]`) and forward `1MRet@t` and `3MRet@t`, **using the walk-forward out-of-sample posteriors only.** Expect negative correlation (high P(adverse) → low forward return).
- **Aggregate across the 34** countries: report the distribution of per-country correlations and a sign test (how many of 34 are negative, binomial p-value vs 50/50).
- **Economic check:** within each country, compare mean forward `1MRet` in the top-quartile-`P_adverse` months vs bottom-quartile months (a within-country spread). Aggregate the spread.
- **PASS condition (all three):**
  1. Sign test: ≥ 23 of 34 countries show the expected negative lead on `1MRet` (binomial p < 0.05), AND
  2. Median per-country Spearman ≤ −0.10 on at least one of {`P_adverse`→`1MRet`, `dP_adverse`→`1MRet`}, AND
  3. Aggregate within-country forward-return spread (bottom-`P_adverse` minus top-`P_adverse`) is positive and economically meaningful (≥ ~50bp/month, pre-cost), and survives the v1-artifact check below.

### GATE 4 — v1-artifact / robustness check (mandatory before declaring PASS)

The prior work flipped from PASS to FAIL on an input fix. Any PASS here must survive:

- **Point-in-time discipline:** confirm no full-sample standardization or full-sample HMM fit leaked into the Gate-3 numbers (walk-forward only). The prior reports used FRED *current-vintage* (look-ahead); your features come from `t2_master` which is cleaner, but verify no forward information enters the expanding standardization or the adverse-state labeling. (Adverse-state labeling uses realized returns — ensure that labeling is done on the *training* window only in the walk-forward, not refitted with future returns.)
- **Placebo:** shuffle the date index within each country, re-run Gate 3. The lead must collapse to ~zero under shuffle. If the placebo also "passes," the result is a pipeline artifact — fail it.
- **Subsample stability:** split at 2013. The sign of the lead must hold in both halves (it can weaken, not flip).

---

## 5. Outputs / artifacts

Write to `regime_ew/results/`:

- `hmm_params/{country}.json` — fitted HMM params, chosen K, BIC, adverse-state index, state→mean-return map.
- `ew_signals.parquet` — `date, country, P_adverse, dP_adverse, state, K` (walk-forward OOS).
- `gate1_persistence.parquet`, `gate3_lead.parquet` — per-country metrics + aggregates.
- `manifest.json` — machine-readable PASS/FAIL for each gate with the key numbers.
- `RESULTS.md` — human verdict in the same spirit as `regime2.md`: a table of Gate 1–4 PASS/FAIL with the headline metric and threshold for each, an honest interpretation, and a one-line recommendation.

Reuse the figure style from `regime/results/figures/` where useful (per-country adverse-prob timelines for a few illustrative countries; a histogram of the 34 per-country Gate-3 correlations).

---

## 6. Decision framework

| Outcome | Interpretation | Next action |
|---|---|---|
| Gates 1–4 all PASS | Per-country regime probability leads own-country returns; real time-series overlay | Productionize the signal into ASADO as a country-level timing overlay; **then** (and only then) consider the fine-tuned MLX explainer that narrates `{country, P_adverse, transition, driving features}` |
| Gate 1 FAIL | States too unstable | Stop. Negative result. Per-country monthly regimes are noise at this frequency. (Consider: would a slower feature set or quarterly frequency help? Separate PRD.) |
| Gate 3 FAIL (1–2 pass) | States persist but don't lead returns | Stop as a return-overlay. If Gate 2 flagged vol, the artifact may still be useful as a **risk/vol overlay** — spin that out as its own question, do not dress it as alpha |
| Gate 4 FAIL (placebo/subsample) | Apparent lead is an artifact — the v1 trap, recreated | Stop. Document exactly which check caught it, so it's not re-discovered later |

**The LLM fine-tuning step is downstream of an all-PASS outcome and narration-only.** It never generates the regime or the probability. If this test does not pass, the fine-tuning question is moot.

---

## 7. Build notes for Claude Code

- New module `regime_ew/`, importing from `regime/src/` (data_loader, utils, persistence_stats). Do not duplicate the loaders.
- `regime_ew/run_ew_test.py` orchestrates: load → per-country standardize → fit (walk-forward) → signals → Gate 1 → Gate 2 → Gate 3 → Gate 4 → write `RESULTS.md`. Each gate prints PASS/FAIL and short-circuits on fail (but still writes what it computed).
- Read-only DuckDB always (`read_only=True`).
- Add a `--full-sample-only` flag for a fast diagnostic pass, but the default run is walk-forward and only walk-forward numbers populate the gates.
- Keep the 34-country loop embarrassingly parallel but deterministic; a simple sequential loop is fine (34 small HMMs is seconds).
- Unit test: per-country alignment of signal[t] with forward return[t] matches `build_forward_returns` convention exactly (mirror `regime/tests/test_alignment.py`).
