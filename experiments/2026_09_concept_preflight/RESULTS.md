# Concept-layer pre-flight checks — results

*Run 2026-09-23, 10:07–10:12 PT, on frozen snapshots taken at 10:05. Pre-registration:
[PREREG.md](PREREG.md) (commit 2049d06), amendment A1 (commit dec0925), both committed before any
statistic was computed. Gross returns, no costs. Diagnostic only: nothing was written to a
ledger, production table, or config.*

## Bottom line

**The relational experiment is cancelled.** None of the three link types — trade, banking or
portfolio holdings — carries next-month information once a country's own recent returns and its
region's are accounted for. The standard "neighbours minus own" gap did predict next month
through 2023, but a diagnostic shows that edge came from the country's *own* last-month return
reversing, not from its neighbours. That is exactly the case the G2 gate was designed to catch.
Under WP-11's rule, the diffusion/interaction territory downgrades.

**The country-level check is split, and its pre-registered verdict rests on a test that turned
out to have almost no power.** The T2 feature panel clearly holds about nine distinct concepts,
stable across every sub-period. But the pre-registered test of whether future returns line up
with those concepts came out exactly at its noise level — and a power check run afterwards shows
that test would have missed even an implausibly strong planted signal more than half the time.
Read literally, the pre-registered rule says drop the node-level experiment. Read honestly, the
check neither supports nor rules it out.

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

**Decision needed from Arjun.** Either (a) honour the pre-registered rule and drop the node-level
experiment, or (b) record A2 as inconclusive for lack of power and replace it with a test that
has power — for example, a pre-registered comparison of how much of the forward cross-section the
top nine directions explain in-sample against a within-month permutation null. Option (b) is a new
registration and should not be treated as a rerun that is allowed to reach a different answer.

---

## Files

- Pre-registration: `PREREG.md`
- Code: `src/common.py`, `src/check_b_g2.py`, `src/check_a_spectral.py`, `src/power_check_a2.py`
- Results (not in git): `results/check_b_g2.json`, `results/check_b_monthly_ic.parquet`,
  `results/check_b_yearly_ic.xlsx`, `results/check_b_cumulative_ic.pdf`, `results/check_b.log`,
  `results/check_a_spectral.json`, `results/check_a_eigen.xlsx`, `results/check_a_spectral.pdf`,
  `results/check_a_power.json`, `results/check_a.log`
- Frozen inputs: `Data/work/experiments/concept_preflight/snapshot_2026_09_23/`
  (`t2_master`, `t2_factors_daily`, `graph_edge_vintages`). The snapshot `MANIFEST.json` lists
  only the two main-DB tables because the second snapshot call overwrote it; the loop-DB table
  was frozen by the first call at 10:05 (93,800 rows).
