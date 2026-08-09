# Conditioning the risk inside Step Five so the ACTIVE BET shifts

**Run:** 2026-08-08 · **Script:** `run_step5_conditional_risk.py`
**Artifacts:** `results/step5_conditional_risk.xlsx` / `.json`
**Environment:** the T2 project's own venv (cvxpy 1.8.1) — the same one production Step Five
runs in. No packages installed; the ASADO nightly venv untouched.
**Safety:** T2 production inputs read READ-ONLY; nothing written outside this experiment dir.

---

## Why this lever, and why it cannot be beta in disguise

Step Five's constraints are `w ≥ 0`, `w ≤ max_weights`, **`sum(w) == 1`** — the book is
always fully invested. Total exposure is fixed by construction, so unlike the previous EWS
overlay (proven pure beta timing: +0.24 Sharpe on T2, +0.22 on plain SPX) nothing here can be
a market bet. Only *which* factors are held and *how concentrated* the bet is can change.

The objective is `w'mu − HHI·||w||² − KAPPA·Σ(tc·|w − w_prev|)`. The HHI term is the
anti-concentration penalty (production 0.001). Raising it in alarm months shrinks the active
bet; leaving it low keeps conviction high.

## Result: no statistically meaningful improvement

| Setup | Ann return | Vol | IR | Max DD | Eff. factors |
|---|---|---|---|---|---|
| **Baseline (production)** | 7.37% | 7.76% | **0.950** | −18.1% | 1.1 |
| Conditional ×5 in alarm | 7.56% | 7.45% | **1.015** | −18.1% | 1.1 |
| Unconditional ×5 always | 7.12% | 7.24% | 0.985 | −18.1% | 1.3 |
| Conditional ×100 in alarm | 6.68% | 6.60% | **1.012** | **−12.7%** | 2.5 |
| Unconditional ×100 always | 3.22% | 4.17% | 0.772 | −10.5% | 8.9 |

Paired monthly tests against baseline:

| Variant | Mean difference | t | p |
|---|---|---|---|
| Conditional ×5 | +0.18%/yr | +0.78 | **0.438** |
| Unconditional ×5 | −0.23%/yr | −0.66 | 0.507 |
| Conditional ×100 | −0.65%/yr | −0.93 | 0.351 |
| **Unconditional ×100** | **−3.96%/yr** | **−3.49** | **0.001** |

**The IR gains of ~+0.06 are indistinguishable from noise** (p ≈ 0.35–0.44). The IR
improvement at ×100 comes entirely from lower volatility — the *return* is 0.65%/yr **lower**.
The response is also non-monotonic across multipliers (0.950 → 1.015 → 0.996 → 0.982 → 0.973
→ 1.012), which is what noise looks like, not a dose-response.

## What IS significant, and it is a confirmation not a discovery

**Unconditional heavy diversification destroys the strategy**: −3.96%/yr, t = −3.49,
**p = 0.001**. This independently reproduces the existing Investment Learnings finding
(*T2 Factor Timing Fuzzy Residual Forecasting*) that pushing the optimizer toward
low-conviction equal-weight collapses it — there the mechanism was residualization, here it is
a raw concentration penalty, and the outcome is the same.

So conditioning does *matter* at high multipliers (conditional ×100 IR 1.012 vs unconditional
×100 IR 0.772) — but only in the sense that it avoids doing permanent damage. It is not
generating alpha.

## The genuinely useful incidental finding: Step Five holds ~ONE factor

The effective number of factors held (1/Σw²) at production settings is **1.1**.

With `mu` scaled 8× and an HHI penalty of 0.001, the quadratic term is ~2 orders of magnitude
too small to influence a corner solution, so the optimizer puts essentially all weight on the
single highest-`mu` factor each month, subject only to the max-weight caps. **The
anti-concentration penalty is effectively inert at its production value.**

That is a structural fact about the live strategy worth knowing independently of this
experiment: T2 Fuzzy is, in practice, a single-factor rotation, and its 7.7%/mo turnover is
the cost of switching which single factor it rides. Whether that is intended is Arjun's call.

## Verdict

**Do not implement.** The conditioning produces no statistically meaningful gain. The only
real effect available is a **risk/return trade**: conditional ×100 cuts max drawdown from
−18.1% to −12.7% for −0.65%/yr of return, at higher turnover (7.7% → 11.7%/mo). That is a
legitimate choice if drawdown is the binding constraint, but it is a preference, not alpha,
and it is not statistically established.

Worth pursuing instead: the effective-concentration finding. If the HHI penalty is inert, then
the real design question is not "should concentration vary with regime" but "should the
strategy be holding one factor at all" — a much larger question and one with a real prior
attached (residualization killed it by forcing diversification, so concentration is doing
genuine work).

---

# UPDATE — the verdict above is REVISED. Broadening when alarmed works.

The "do not implement" verdict was based on a paired t-test of monthly return
differences. **That was the wrong test.** The effect is not in the average monthly return —
it is in *when* the breadth changes. Two proper nulls both find it.

## 1. Sign test: inverting the signal is catastrophic

| | IR | Max DD |
|---|---|---|
| Baseline | 0.950 | −18.1% |
| **Broaden when ALARMED** | **1.012** | **−12.7%** |
| Broaden when CALM (inverted) | **0.647** | −16.7% |
| Random 24% of months (25 draws) | 0.920 ± 0.064 | −15.5% |

Inversion costs **0.365 of IR**. Noise does not do that. Against random same-frequency
timing the real signal is at the **88th percentile on IR, 96th on drawdown**.

## 2. Continuous beats binary

Replacing the threshold with `HHI = 0.001 · M^(diffusion / 0.40)` — smooth, no cut point:

| Setup | Return | Vol | IR | Max DD | Turnover | Eff. factors (calm → alarm) |
|---|---|---|---|---|---|---|
| Baseline | 7.37% | 7.76% | 0.950 | −18.1% | 7.7% | 1.1 |
| M=5 | 7.53% | 7.42% | 1.016 | −18.1% | 8.4% | 1.1 → 1.3 |
| **M=25** | 6.96% | 6.71% | **1.037** | **−13.3%** | 10.9% | 1.1 → 3.6 |
| M=100 | 6.37% | 6.17% | 1.033 | **−10.6%** | 13.8% | 1.1 → 12.1 |
| M=1000 | 5.49% | 5.82% | 0.944 | −11.2% | 18.0% | 1.1 → 33.4 |

Clear interior optimum around M=25–100 — a **plateau, not a spike**, which is what a real
effect looks like. Best IR 1.037 (+0.087 over production).

## 3. Circular-shift null — the decisive test

Same diffusion series, same autocorrelation, shifted so it no longer aligns with returns
(20 shifts). This is the `circular_shift_null` technique already used in the *AA* record.

| | IR | Max DD |
|---|---|---|
| **Real diffusion, M=25** | **1.037** | **−13.3%** |
| Null: mean | 0.909 | −18.0% |
| Null: sd / range | 0.051 / 0.810–1.020 | −18.1% to −16.9% |
| **Real vs null** | **beats 100% of shifts** | **beats 100% of shifts** |

Two things stand out:
- The real drawdown (−13.3%) is **3.6pp better than the best of 20 shifts**. Complete separation.
- The null's mean drawdown (−18.0%) is **indistinguishable from baseline** (−18.1%). Misaligned
  broadening delivers *no* drawdown benefit whatsoever. And the null's mean IR (0.909) is
  **below** baseline — broadening at the wrong times actively hurts.

So the entire benefit comes from the *alignment* of the diffusion signal with the return
series, which is exactly the claim being made.

## Revised verdict

**This is real, and it is not beta.** `sum(w) == 1` throughout — total exposure never changes,
only the breadth of the active bet. It survives inversion, random-timing and circular-shift
nulls, and shows a sensible dose-response plateau.

Recommended setting: **continuous, M = 25–100.** M=25 maximises IR (+0.087); M=100 buys a much
larger drawdown reduction (−18.1% → −10.6%) for ~1%/yr of return.

Honest remaining caveats:
1. **The EWS was calibrated on these same crashes.** This is the one caveat none of the nulls
   address — they test whether the *timing* matters given the signal, not whether the signal
   would have existed in advance. Unchanged from the earlier analysis.
2. **Turnover rises** 7.7% → 10.9%/mo at M=25 (13.8% at M=100). Reported as a fact, not a gate.
3. M was chosen from a 6-point sweep; the plateau mitigates but does not eliminate this.
4. One strategy, 317 months.
