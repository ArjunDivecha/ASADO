# RESULTS — Boundaries of TSM, replication (sequencing step 1)

**Run:** 2026-08-08 · **Pre-registration:** `PREREGISTRATION.md` (committed `cc2e7ef`, before any regression)
**Frozen input:** `boundaries_panel.parquet` md5 `ecf8d8149f30ed8868547464b25fae0d` (asserted at runtime)
**Artifacts:** `results/replication_results.xlsx`, `results/signflip_diagnosis.xlsx`, `results/tsmom_index.parquet`

---

## Verdict: PARTIAL (leaning NEGATIVE) — signs replicate, but the effect is a coin flip across countries

Both of the paper's headline claims come out with the **correct sign** in the paper's own
construction, and neither reaches |t| ≥ 2 once the standard error accounts for the
overlapping 12-month windows. That is the outcome the pre-registration anticipated for this
arm, and it is a statement about our 15-year sample, not evidence against the paper.

| Spec | Paper's claim | Our coef (paper construction) | t (month-clustered) | **t (Driscoll–Kraay)** |
|---|---|---|---|---|
| A — `fwd12_tsmom ~ Boundaries` | b < 0 | **−0.01592** ✓ sign | −2.54 | **−1.05** |
| B — `past12 × Boundaries` | b3 < 0 | **−0.18267** ✓ sign | −2.62 | **−1.67** |

### An honest note on the standard error I used

`PREREGISTRATION.md` named **month-clustered** as the headline and Driscoll–Kraay as a
"noted upgrade". **I am reporting DK as the headline instead, and that is a deviation from
what I registered** — flagged here rather than quietly swapped, because it is the kind of
substitution that would otherwise look like SE-shopping.

The reason it is the right call cuts *against* the result rather than for it: month-clustering
handles contemporaneous cross-country correlation but **not** the serial correlation induced
by overlapping 12-month forward returns, and on this data it produced *larger* t-statistics
than even NW-12 — i.e. my registered headline was the most flattering of the three. DK
handles both dependencies. Every t-statistic falls by roughly half under it, on every arm,
in both directions. The paper's own robustness section makes the same point (its Hodrick and
IVX tables show NW-12 overstates); we are simply seeing it again, harder, in a shorter sample.

---

## The plainest evidence against the effect: it is a coin flip across countries

Added 2026-08-08 after Arjun asked what the bucket averages actually represent. One row is
ONE country, ONE month; the value is that country's trend-following return over the
following 12 months, in excess of cash. The headline buckets are averages over ~500
country-months each. Splitting the SAME gap country by country:

| | |
|---|---|
| Countries showing the paper's effect (worse in extremes) | **8** |
| Countries showing the **opposite** | **8** |
| Median country's calm-vs-extreme gap | **+0.0pp** |
| Range across countries | −18.8pp to +10.7pp |

The pooled −2.4pp gap is not a pattern repeated across countries. It is a handful of
countries with large negative gaps, offset by others going the other way, with the median
country showing nothing at all. A real mechanism about behaviour near valuation extremes
should appear in most countries most of the time.

**This is more decisive than the t-statistics and requires no econometrics to see.** The
pooled average concealed it; reporting it first was a presentation error.

**Context that makes it worse:** the unconditional average is **+0.7%** over cash across all
2,488 country-months, and traded as one equal-weighted diversified book it is **+0.6%/yr on
7.6% vol — a return/risk of 0.08**. We are hunting a conditioning effect on top of a
strategy that did not make money in this sample.

---

## The finding that actually matters: the two constructions are nearly ORTHOGONAL

The pre-registration called a sign flip between constructions "a finding, not a bug". It
happened — and the diagnosis is more interesting than a flip.

**corr(paper Boundaries, peer-relative Boundaries) = 0.0279** across 2,704 shared rows.

They are not two normalizations of one quantity. They are **different variables**. The
handoff intuited the concepts differ ("own-history extreme ⇒ domestic constraint;
peer-relative ⇒ relative-value flows") but framed idea #3 as a *horse-race* between rival
measurements of the same thing. At r = 0.03 there is no horse-race to run.

**The flip is caused by the normalization, not the sample** — proven by holding the sample
fixed at exactly the same 2,488 country-months:

| Arm | Construction | Sample | Spec A coef | t_clustered | **t_DK** |
|---|---|---|---|---|---|
| 1 | paper-exact | 18 ctry, 2010-12→ | **−0.01592** | −2.54 | −1.05 |
| 2 | peer-relative | **identical rows** | **+0.03337** | +6.34 | **+2.57** |
| 3 | peer-relative | 23 ctry, 2001-02→ | +0.01001 | +2.59 | +1.05 |

ARM1 vs ARM2 isolates the measure. Same countries, same months, same dependent variable —
opposite sign. So this is not a period effect and not a coverage effect.

### What that does to the programme

1. **The "+2.24× sample" argument for peer-relative does not transfer the paper's mechanism —
   it replaces it.** The extra data is real, but it buys observations of a *different*
   hypothesis. Peer-relative cannot be used as a cheap proxy for the paper's boundary and
   must not be described as one.
2. **D4 is rewritten.** It was registered as a horse-race between normalizations. It is not
   one; it is two separate hypotheses that happen to share a name. Either test both as
   distinct constructs or drop one.
3. **The one result that survives DK is the peer-relative arm, with the opposite sign**
   (ARM2: +2.57 on Spec A, +3.45 on Spec B's Boundaries term). Being *cross-sectionally*
   extreme is associated with **better** forward TSMOM returns in this sample. That is
   unregistered and therefore a hypothesis to be tested on the holdout, **not a result** —
   recorded here so it cannot later be presented as a prediction.

---

## Deviations from the paper (all declared in advance)

1. **USD basis with the US risk-free rate** for every country, vs the paper's local-currency
   cash markets with local risk-free. Ours matches the traded instruments.
2. **Sample floors at 2000/2001** vs US 1927–2024 / DM 1989–2024.
3. **Shiller PE** as the valuation leg rather than dividend yield — the paper's own
   acknowledged international weakness.

Any of the three could account for attenuation on its own; with signs correct and magnitudes
sensible, the most economical reading is simply that ~15 years of overlapping annual returns
cannot resolve an effect this size.

## Verification performed

- Frozen-input md5 asserted at runtime; the script refuses to run if the panel changed.
- **Forward-return alignment hand-checked** before any regression: Japan 2015-01, manual
  compounding of the next 12 monthly excess returns = 0.076288 vs computed 0.076288. This is
  the same error class that produced ~0.0 correlations earlier in the session, so it was
  checked by hand rather than assumed.
- No holdout used or burned: the last 5 years and ChinaA/India/Brazil/Poland remain untouched
  and are reserved for the D1–D4 discovery tests.

## What this does NOT license

The programme's premise survives with the correct sign but without statistical support in
this universe. Before any allocation decision it needs the D1 boundary olympics, and it needs
them on the registered holdout. **Nothing here justifies conditioning a live book on
Boundaries.**
