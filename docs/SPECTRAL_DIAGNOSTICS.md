# Spectral Diagnostics for ASADO

Last updated: 2026-06-17

Canonical research/methods spec. Manual; update when the diagnostics or their
implementation change.

How the DSC-243 convex-quadratic theory (Drusvyatskiy, UCSD) maps onto ASADO's
factor-timing, regime, and analog machinery — and what to compute before the
next round of IC-chasing.

Source: Drusvyatskiy, *Convex Quadratics: Algorithms, Spectra, and Scaling
Limits*, DSC 243 lecture notes (Parts I–IV), https://ddrusvyat.github.io/DSC-243/.
DOI: 10.5281/zenodo.20726281.

---

## 0. Why this belongs in ASADO

Almost every estimator in ASADO is, at its core, a regularized least-squares /
quadratic problem: cross-sectional factor-return regressions, the T2 CVXPY
factor-timing optimizer, ridge/IPCA loadings, and the linear pieces of the
World-State Analogs weighting. The DSC-243 notes are entirely about quadratic
minimization, and their central message is directly actionable here:

> **Worst-case behavior is set by the extreme eigenvalues (the condition
> number). Actual behavior is set by the *whole spectrum* of the design matrix
> and by how the signal projects onto it.**

`unified_panel` carries on the order of 700 variables across 34 countries. The
sample length per cross-section is small relative to the variable count, so we
are squarely in the high-dimensional regime where the spectrum is *not*
incidental — it determines what is estimable at all. This doc translates three
results from the notes into concrete diagnostics:

1. **Source conditions** (§7) — a cheap test for whether the IC plateau is data-limited or model-limited.
2. **Marchenko–Pastur edges** (§7) — a principled noise-floor cutoff for the covariance spectrum.
3. **Effective rank & the Volterra/SGD limit** (§10) — stability and batch-size limits for any online/streaming estimation.

None of this requires new infrastructure; all three are scalar diagnostics
computable from matrices ASADO already forms.

---

## 1. The source-condition test (IC plateau triage)

### The idea

For a least-squares problem `min ½‖Xw − y‖²` with `H = XᵀX`, write the target's
error in the eigenbasis of `H`. A **source condition** of order `s` says the
coefficients decay like `λᵢˢ` — i.e. the signal lives in the *large*-eigenvalue
(well-conditioned) directions. The notes show:

- `s > 0`: signal concentrated on large eigenvalues → fast `O(k^{-(1+2s)})` convergence; the target is genuinely learnable from the sample.
- `s ∈ (−½, 0)`: signal smeared onto small-eigenvalue directions → the recoverable rate depends on `‖u‖` not `‖e₀‖`, and the naive error norm diverges as dimension grows.
- No source condition (negative slope): the signal sits in the noise-dominated tail. **No optimizer or model change recovers it** — the information is not in the sample.

In the notes' worked kernel example the diagnostic is a single log-log slope:
a smooth target gave slope ≈ **+0.4** (learnable), a random-sign target gave
≈ **−0.9** (unlearnable — error concentrated in small-eigenvalue directions).

### The ASADO procedure

Run this **before** investing more in the IPCA pipeline, the alpha-hunting
loop's proposer/verifier search, or any new factor:

1. Form the cross-sectional design matrix `X` used in the factor-return step (the same one feeding T2 / IPCA). Compute `H = XᵀX` (or the panel-pooled Gram matrix).
2. Eigendecompose `H = Σ λᵢ vᵢ vᵢᵀ`.
3. Project the prediction target (next-period country returns, or the factor you're trying to time) onto each eigenvector: `bᵢ = vᵢᵀ y`.
4. Compute the signal coefficients `cᵢ = bᵢ / λᵢ` (this is the initial error of GD-from-zero, `e₀ = H⁻¹b`).
5. Regress `log|cᵢ|` on `log λᵢ`. The slope `s'` is the **matrix-level source exponent**.

Reading the result:

| Slope `s'` | Interpretation | Action |
|---|---|---|
| `s' > 0` | Signal in well-conditioned directions | Plateau is model/optimizer-limited → IPCA, richer features, better search *can* help |
| `−½ < s' < 0` | Signal in soft-edge directions | Marginal; gains require dimension-free estimators (ridge-with-‖u‖ control), not more capacity |
| `s' ≤ −½` | Signal in the noise tail | **Plateau is information-theoretic.** Stop chasing IC on this target; change the target, horizon, or universe instead |

### Why this matters for the IC plateau

The IC plateau the loop hits after many iterations is exactly the symptom this
test discriminates. If `s'` on the relevant design is negative, the
proposer/verifier search and the IPCA break-through attempt are both fighting a
data limit, not an algorithmic one — and the honest move is to redefine the
prediction problem (longer horizon, fewer/denser variables, different
cross-section) rather than add search compute. If `s'` is positive, the plateau
is genuinely an estimator shortfall and IPCA is the right lever.

**Kernel-regression caveat:** the notes derive a one-step exponent shift between
the function-level smoothness `s` and the matrix-level exponent `s' = s − 1`.
For ASADO's *linear* factor models there is no kernel operator in between, so
work directly with the matrix-level slope `s'` from step 5; don't apply the
shift.

---

## 2. Marchenko–Pastur edges (covariance noise floor)

### The idea

When `X` has roughly iid entries and `d/n → γ`, the eigenvalues of the sample
covariance `H = (1/n)XᵀX` converge to the Marchenko–Pastur law, supported on
`[λ₋, λ₊]` with

```
λ± = (1 ± √γ)²,    γ = d / n.
```

Everything below `λ₋` is aspect-ratio noise, not structure. When `γ > 1`
(more variables than observations — ASADO's regime) there is additionally a
mass of exactly-zero eigenvalues; the informative bulk lives in
`[(√γ − 1)², (√γ + 1)²]`.

### The ASADO procedure

For the `unified_panel` design with `d` variables and `n` time-observations per
cross-section:

1. Compute `γ = d / n` for whatever estimation window you use. (With short windows `γ > 1`, so a large fraction of directions are pure noise.)
2. Compute the MP edges `λ±` for that `γ`.
3. Any sample-covariance eigendirection with eigenvalue inside the MP bulk is **indistinguishable from noise**. Loadings, factor exposures, or analog weights resting on those directions are fitting noise.

Uses:

- **Shrinkage cutoff.** This is the rigorous version of "why we need Ledoit-Wolf / IPCA shrinkage." Use the noise bulk's `λ₊` as the threshold separating retained vs. shrunk-to-prior eigendirections, instead of an ad-hoc `k`.
- **DIP and other constructed factors.** When validating a constructed factor (e.g. demographic inflation pressure), check that its covariance signature loads above the MP edge — otherwise its apparent cross-sectional structure may be an artifact of `γ`.
- **HMM regime panel.** The CRPS / regime-break validation harness implicitly trusts the covariance structure of the 34-country panel. MP tells you how many of those covariance directions are real before the HMM ever sees them; feeding sub-edge directions into regime detection injects noise as if it were signal.

### Sanity check at γ = 1

At the critical square aspect ratio the notes give a clean closed form: the MP
density behaves like `λ^{−1/2}` near zero, and CG on such a spectrum converges
at `O(k⁻³)` versus GD's `O(k^{−3/2})`. If you ever run an estimation window
where `n ≈ d`, expect the hard edge at zero and the `k^{−3/2}` GD rate — useful
as a "does my solver behave as theory predicts" check on the analog/optimizer
code.

---

## 3. Effective rank & the streaming-SGD limit (§10)

### The idea

Part IV studies streaming SGD on a quadratic in the proportional limit
(`d → ∞`, epoch time `t = k/d`). The risk trajectory converges to a
*deterministic* curve governed by a Volterra equation whose only inputs are two
spectral statistics of `H`: the empirical spectral measure `μ_H` (eigenvalue
density) and the signal-weighted measure `ν` (how the target projects onto
eigendirections). The dimension enters nowhere else. From this fall out three
constants ASADO can use directly.

### Constant 1 — Critical stepsize (stability is set by the *average* eigenvalue)

```
γ_c = 2 / λ̄ = 2d / Tr(H)
```

Stability of any online/streaming estimator is governed by the **average**
eigenvalue, not `λ_max`. This is counterintuitive relative to classical
gradient-descent intuition (which keys off `λ_max`). For any online-updating
component — rolling factor estimators, any SGD-style fit — the learning-rate
ceiling should be set from `Tr(H)/d`, not the top eigenvalue.

### Constant 2 — Noise floor

```
excess risk floor = γλ̄σ² / (2(2 − γλ̄))
```

A constant-stepsize online estimator does **not** converge to the optimum — it
contracts to a stepsize-proportional floor and oscillates. No single constant
stepsize avoids this bias–variance trade-off; tail-averaging (Polyak–Ruppert)
is what recovers the statistically optimal `O(σ²d/T)` rate. If any ASADO online
estimator is run with a fixed step and *not* tail-averaged, it is leaving the
floor's worth of accuracy on the table.

### Constant 3 — Effective rank / critical batch size

```
B_crit = Tr(H) / λ_max(H)
```

`Tr(H)/λ_max` is the **effective rank** (participation ratio) of the covariance
— the number of directions that genuinely carry variance. Its uses in ASADO:

- **Point of diminishing returns for batching.** Below `B_crit`, averaging more observations per update gives linear speedup; past it, larger batches barely move the iteration count. Don't over-batch beyond `B_crit`.
- **A single honest number for "how many factors are real."** Effective rank is a softer, more defensible answer than counting eigenvalues above a hard threshold, and it's one scalar you can track over time as the panel evolves.
- **Regime monitoring.** A sharp drop in `Tr(H)/λ_max` over a rolling window means variance is collapsing into a few directions — a concentration signal that is itself a regime indicator, complementary to the HMM.

---

## 4. What to actually compute (checklist)

All five are scalars/curves from matrices ASADO already forms. Suggested home:
a `diagnostics/spectral.py` module writing to `reports/`, optionally wired into
`monthly_update.py` so the readings refresh with the panel.

- [ ] **Source slope `s'`** on the live factor-return design → triage the IC plateau (§1).
- [ ] **MP edges `λ±`** for the current `γ = d/n` → covariance noise cutoff & shrinkage threshold (§2).
- [ ] **Effective rank `Tr(H)/λ_max`** on the panel covariance → "how many factors are real," tracked over time (§3).
- [ ] **Critical stepsize `2d/Tr(H)`** for any online estimator → learning-rate ceiling (§3).
- [ ] **Tail-averaging** on any constant-step online fit → kill the noise floor (§3).

---

## 5. Scope and limits

- This is **quadratic / least-squares** theory. It transfers cleanly to ASADO's ridge/IPCA/cross-sectional-regression pieces and to the linear parts of analogs and T2. It does **not** directly cover the HMM likelihood surface (non-quadratic), GDELT-sentiment nonlinearities, or the Neo4j graph layer — though the covariance diagnostics still apply to any feature matrix fed into those.
- The MP law assumes roughly iid entries. ASADO's variables are correlated and heavy-tailed, so treat `λ±` as a guide to the *order of magnitude* of the noise edge, not a hard boundary. The §10 limit results (effective rank, critical stepsize) are distribution-robust and don't lean on the iid assumption.
- The eigenvalue-decay specifics in the notes (Matérn/kernel smoothness rates) are kernel-regression-specific and **not** relevant unless ASADO adds kernel methods on the country panel.

---

Doc owner: research. Add empirical `s'`, `λ±`, and effective-rank readings here
once `diagnostics/spectral.py` is run on the current panel, so the plateau
triage decision is recorded rather than re-litigated.
