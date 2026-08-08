# RESULTS — D1, the boundary olympics (in-sample)

**Run:** 2026-08-08 · **Registered in:** `PREREGISTRATION.md` (commit `cc2e7ef`) as D1
**Artifacts:** `results/d1_olympics.xlsx`, `results/d1_olympics.json`
**Holdout:** enforced in code and **UNTOUCHED** — excluded dates ≥ 2021-08-01 and
ChinaA/India/Brazil/Poland. In-sample = 9,475 rows, 30 countries, ending 2021-07-01.

---

## Verdict: the kill criterion was NOT met — the premise survives, narrowly

The registered kill criterion was "no state variable reaches |t| ≥ 2 on the past-return ×
extremeness interaction". **CAPE reached −2.88.** So the "extremes break trend" premise is
not dead for this universe.

But it survives on one variable, and the two the prior favoured both failed.

| Tier | State variable | Interaction coef | t (Driscoll–Kraay) | Countries with the paper's sign |
|---|---|---|---|---|
| **REGISTERED** | **CAPE (valuation)** | **−0.3472** | **−2.88** ✓ | 14/21 (67%) |
| REGISTERED | credit_gap | −0.0950 | −1.08 | 16/27 |
| REGISTERED | REER | +0.1422 | +1.46 *(wrong sign)* | 15/30 |
| exploratory | EPU | −0.3241 | −1.84 | **15/18 (83%)** |
| exploratory | fx_reserves | −0.1893 | −1.29 | 16/28 |
| exploratory | term_spread_10y2y | +0.3280 | +1.54 *(wrong sign)* | **3/15** |
| exploratory | term_spread_10y3m | +0.1185 | +0.76 *(wrong sign)* | **6/15** |

(Full table of all 13 in `d1_olympics.xlsx`.)

---

## The stated prior was wrong, and that is the headline

The prior recorded in the handoff was **"REER + credit gap beat valuation."** The result is
the exact opposite:

- **REER** — the "cleanest boundary in finance" per idea #8 — has the **wrong sign** (+1.46)
  and splits 15/30 across countries, i.e. a perfect coin flip.
- **credit_gap** — testable at all only because of this session's quarterly-forward-fill
  fix — is insignificant (−1.08).
- **Valuation, the variable the prior expected to lose, is the only survivor.**

## Why the replication looked weaker than this: the paper's own construction dilutes it

| Construction | Interaction t (DK) |
|---|---|
| Paper's Boundaries = term-spread² + CAPE² | −1.67 |
| **CAPE extremeness alone** | **−2.88** |

The term-spread leg is not merely weak — it points the **wrong way** on both definitions
(+1.54 and +0.76) and carries the paper's sign in only **3 of 15** and **6 of 15** countries.
Adding it to CAPE halves the signal.

This lands on a weakness the handoff had already flagged in the paper ("symmetric
sum-of-squares boundary shape assumed not tested"; the term spread chosen on "data
availability"). **The actionable conclusion is to drop the term-spread leg**, which makes the
boundary a valuation-extremeness story rather than a joint equity-and-bond story — a
materially different claim from the paper's.

---

## Three caveats that keep this from being a result

1. **Country consistency is only weakly supportive.** 14 of 21 countries (67%) show the
   paper's sign — better than the replication's 8/16 coin flip, but a one-sided binomial
   gives **p = 0.095**. Not significant on its own. This is the same diagnostic that killed
   the replication, and here it neither kills nor confirms.
2. **It sits exactly on the multiplicity line.** CAPE was pre-registered as one of three, and
   it clears the Bonferroni threshold for 3 tests (2.39). But 13 variables were run in total,
   and the threshold for 13 is **2.89 — versus CAPE's 2.88.** Pre-registration is what
   licenses the 3-test threshold, so this is defensible; it is not comfortable.
3. **It is in-sample.** The holdout has not been touched.

## An exploratory note, recorded so it cannot later be dressed up as a prediction

**EPU (economic policy uncertainty)** has the strongest *country consistency* of anything
tested — 15 of 18 countries, binomial **p = 0.004** — while its pooled t is only −1.84. It
was not registered. It is a hypothesis for a future registration, not a finding, and it is
written down here precisely so its provenance stays visible.

## What this licenses, and what it does not

Licensed: a single, pre-registered holdout test of **CAPE extremeness alone**, without the
term-spread leg.

Not licensed: any allocation decision, and any claim that the boundary mechanism is
established. One variable clearing a 3-test threshold in-sample, on 67% country consistency,
is a reason to run the confirmatory test — not a reason to believe it.
