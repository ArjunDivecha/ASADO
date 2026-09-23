# Concept-layer pre-flight checks — results

*Run 2026-09-23, 10:07–10:12 PT, on frozen snapshots taken at 10:05. Pre-registration:
[PREREG.md](PREREG.md) (commit 2049d06), amendment A1 (commit dec0925), both committed before any
statistic was computed. Gross returns, no costs. Diagnostic only: nothing was written to a
ledger, production table, or config.*

## Bottom line

**The relational experiment is cancelled; the country-level concept experiment goes ahead.**

None of the three link types — trade, banking or portfolio holdings — carries next-month
information once a country's own recent returns and its region's are accounted for. The standard
"neighbours minus own" gap did predict next month through 2023, but that edge came from the
country's *own* last-month return reversing, not from its neighbours — exactly the case the G2
gate was designed to catch. Under WP-11's rule the diffusion/interaction territory downgrades.

On the country side, the T2 feature panel holds about nine distinct concepts, and — on the
replacement test A3, with the U.S. markets removed and each country's own average stripped out —
those nine concepts explain 11.8% of the variation in next-year relative returns, against a
chance ceiling of 3.1% (p = 0.001). The result survives the two look-ahead checks run afterwards.
The pre-registered rule therefore says proceed, with at most nine concepts. This is an in-sample
alignment test, not a forecast: it says the concept directions carry return-relevant signal, not
that a concept model beats a flat one out of sample. That is what the node experiment has to show.

The original spectral test (A2) was recorded as inconclusive for lack of power, by owner
decision, and replaced by A3 rather than rerun.

---

## Check B — G2 orthogonalization gate, by relation type

For each month, each country's partner-weighted return (weights from the point-in-time
`graph_edge_vintages`) was regressed across countries on its own month return, its own 12-1
momentum and its region's return; the residual was then correlated with next month's return.

| Relation | Months | Mean IC | t (primary) | t (first day skipped) | Passes G2 (t ≥ 2) |
|---|---:|---:|---:|---:|---|
| Trade | 308 | −0.010 | −0.81 | −0.76 | No |
| Banking | 253 | +0.013 | +0.83 | +1.20 | No |
| Holdings | 308 | +0.002 | +0.13 | +0.17 | No |

Newey-West t-statistics are within 0.15 of these. After Holm adjustment across the three
relations, the smallest one-sided p-value is 0.61. The placebo, which scrambles each country's
partners 200 times, puts the real results at the 22nd, 78th and 61st percentiles of its null
distribution: ordinary. No relation shows significant convergence either (t ≤ −2 over the full
sample).

By era, nothing is significant before 2024. In 2024–26 all three turn negative, and holdings
reaches t = −2.08 over 31 months. That is the known sign flip, but on a sample this short it is
descriptive, not a finding.

**Why the familiar gap signal looked alive (not pre-registered, run as a pipeline sanity
check).** Without the controls, the neighbour-minus-own gap reproduces the family's historical
strength: through 2023 its t-statistics are +2.50 (trade), +3.17 (banking) and +2.88
(holdings). But the neighbours' return by itself has no predictive power (t between −1.1 and
+0.2), while a country's own last-month return predicts next month *negatively* (IC −0.031,
t −2.16). The gap is neighbour minus own, so it inherits one-month reversal. Once own return is
controlled, nothing is left. This was the G2 gate's stated concern: "if the orthogonal IC is ~0,
the graph survivors were correlated momentum." Here the correlated effect is short-term reversal
rather than momentum, but the conclusion is the same.

**Caveat.** This is the monthly test the gate specifies. The daily 1- and 5-day versions of the
family (the ones the flip autopsy found stayed positive longest) were not tested here, so this
result does not by itself say the daily signals are reversal in disguise — though the same
decomposition would be the obvious next check on them.

## Check A — how many concepts, and is the return signal in them?

Panel: 36 T2 cross-sectional variables with at least 90% coverage from 2005, 7,031 complete
country-months over 249 months. The macro variables (GDP, current account, budget deficit,
debt, country risk) failed the coverage bar, as did the eight broadcast commodity series, so this
is a market, valuation and technicals panel.

**A1 — number of concepts: 9.** The leading eigenvalues (9.2, 5.3, 3.4, 2.7, 2.2 …) stand far
above the permutation null (about 1.1 each). The count is 9 on the full sample and 9, 8 and 9 on
the samples ending 2010, 2015 and 2020, so the structure is stable. The secondary Wang-Liu-Chen
eigenvalue-ratio estimate picks one dominant factor in each mode. That reflects a single large
first factor, not an absence of further structure.

**A2 — does future return line up with the strong directions: no detectable alignment.**

| Target | Slope s′ | Null mean | Null 95th pct | Real at null percentile |
|---|---:|---:|---:|---:|
| 12-month relative return (primary) | −0.486 | −0.488 | −0.387 | 55% |
| 1-month relative return | −0.539 | −0.503 | −0.400 | 30% |

A pure-noise target gives a slope near −0.5, and the real returns sit right there. The
pre-registered rule therefore reads **drop the node-level concept experiment**.

**Power check (run after the result, does not change the rule).** Synthetic targets were
planted along the panel's three strongest directions and passed through the same test:

| Planted pooled correlation | Detected (of 100) |
|---:|---:|
| 0.05 | 12 |
| 0.10 | 16 |
| 0.20 | 30 |
| 0.30 | 45 |

Realistic country-return signals sit around 0.03–0.10. At those strengths the test fires
only 12–16% of the time, barely above its 5% false-alarm rate. The reason is structural: the
slope is fitted across all 36 eigen-directions, and the 33 weak ones drown the few strong ones.
The chart (`results/check_a_spectral.pdf`) shows a second weakness: a few near-duplicate
variable pairs (for example `MCAP_CS` and `MCAP Adj_CS`, `Best PE _CS` and `Earnings Yield_CS`)
create eigenvalues near 10⁻⁴, and dividing by them produces the largest coefficients, which
pull the fitted slope around. The spectral-diagnostics spec (`docs/SPECTRAL_DIAGNOSTICS.md` §1)
did not anticipate either problem.
So A2's null result is a failure to detect, from a test that could not have detected a plausible
effect. It is not evidence that the return signal lives in the noise.

**Decision (Arjun, 2026-09-23): option (b).** A2 is recorded as inconclusive for lack of power and
replaced by A3, registered before it ran (below). A2's own result stands as recorded.

---

## Check A3 — do the nine concepts explain next-year returns better than chance?

Registered in `PREREG.md` (commit f0ec126), with the U.S. markets removed at Arjun's direction
before any code was written (amendment A3-1, commit d1b9119), and the power calibration committed
before the real returns were read (commit 6a094a4).

Panel: 30 markets (the 31 non-U.S. markets less Vietnam, which fails the coverage bar), 249
months, 36 variables. Concepts: the top nine principal components of the features alone. Both the
concepts and the 12-month relative return have month and country averages removed, so a country
that simply did well throughout cannot drive the result. Chance is measured by giving each
country another country's entire return history, 1,000 times.

| Test | R² | Chance, 95th pct | p |
|---|---:|---:|---:|
| **12-month, identity removed (primary)** | **0.118** | 0.031 | 0.001 |
| 12-month, month averages only | 0.056 | 0.020 | 0.001 |
| 1-month, identity removed | 0.014 | 0.003 | 0.001 |

p = 0.001 is the floor with 1,000 shuffles: none of them matched the real value. **Pre-registered
decision: proceed with the node-level concept experiment, at most nine concepts.** The ex-U.S.
concept count from parallel analysis is eight.

**Power.** Calibrated on synthetic targets before the real run: the test catches a planted signal
of correlation 0.20 95.5% of the time, 0.10 25% of the time, 0.05 6% of the time. By the
registered bar it is underpowered for signals near 0.10. That caveat matters only for a null
result; the real result here is far outside chance.

**Could look-ahead in the averaging have manufactured it? No (post-hoc diagnostics,
`src/diag_a3_bias.py`, not pre-registered).** Removing each country's average over the *whole*
sample leaks the future for slow-moving features such as price levels, and the shuffle test does
not reproduce that leak. Two checks:

| Variant | R² | Chance, 95th pct | p |
|---|---:|---:|---:|
| Past-only averages (features: earlier months; returns: only already-matured 12-month windows) | 0.120 | 0.037 | 0.001 |
| Five price-level variables removed, identity removed as in A3 | 0.087 | 0.028 | 0.001 |
| Both | 0.096 | 0.035 | 0.001 |

**What the strongest concepts are made of** (the four with the largest individual R², 1.4–3.3%
each; described from their largest loadings, oriented so that a higher score means a higher next-
year relative return):
- a size-and-reversal concept: small market capitalisation, weak trailing 12-month and 12-1
  returns, but firm RSI;
- a short-term-reversal-and-currency concept: weak 1- and 3-month returns with a strong real
  exchange rate;
- an earnings-and-price-level concept: high EPS and price levels relative to peers;
- a mixed concept of real exchange rate, recent return, volatility and bond yield (negative sign).

So most of the aligned signal is built from price, size, reversal and currency inputs that the T2
additive predictor already uses. The node experiment's real question is therefore whether a
small constrained concept layer combines these better than the flat ridge and the additive
predictor do, out of sample. This check says there is something to combine; it does not say the
combination wins.

---

## Files

- Pre-registration: `PREREG.md`
- Code: `src/common.py`, `src/check_b_g2.py`, `src/check_a_spectral.py`, `src/power_check_a2.py`,
  `src/check_a3.py`, `src/diag_a3_bias.py`
- Results (not in git): `results/check_b_g2.json`, `results/check_b_monthly_ic.parquet`,
  `results/check_b_yearly_ic.xlsx`, `results/check_b_cumulative_ic.pdf`, `results/check_b.log`,
  `results/check_a_spectral.json`, `results/check_a_eigen.xlsx`, `results/check_a_spectral.pdf`,
  `results/check_a_power.json`, `results/check_a.log`, `results/check_a3_power.json`,
  `results/check_a3.json`, `results/check_a3_null.pdf`, `results/check_a3.log`, `results/diag_a3_bias.json`
- Frozen inputs: `Data/work/experiments/concept_preflight/snapshot_2026_09_23/`
  (`t2_master`, `t2_factors_daily`, `graph_edge_vintages`). The snapshot `MANIFEST.json` lists
  only the two main-DB tables because the second snapshot call overwrote it; the loop-DB table
  was frozen by the first call at 10:05 (93,800 rows).
