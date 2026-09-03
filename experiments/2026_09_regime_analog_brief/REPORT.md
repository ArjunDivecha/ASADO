# Does history give a guide? — the post-July-2026 tone change, tested against ASADO

**Run:** `run_20260902_191004` · **Date:** 2026-09-02
**Status:** CONTEXT-TIER DESCRIPTIVE BRIEF. Not a signal, not a ledger entry, no trade list.
**Pre-registration:** `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/SPEC.md`, written before any forward return was computed.

---

## Bottom line

1. **The tone change is real, but it is not the one the note describes.** ASADO confirms the
   leadership inversion and the yield rise, and contradicts the inflation-nervousness framing:
   oil momentum is *negative*, volatility has *collapsed*, and cross-country correlation is at
   its **2.8th percentile** since 2000. This is a leaderless, quiet, low-correlation market —
   not a stressed one.

2. **The pre-registered analog exercise returns a clean null.** Matching today's world state to
   history on a 6-dimension vector produces forward distributions statistically indistinguishable
   from the unconditional ones (3 of 64 cells at p<0.05, versus ~3 expected by chance). This
   replicates the four prior ASADO verdicts that killed regime conditioning and world-state
   analogs. **On the question as asked — does the macro state tell you what happens next — the
   answer stays no.**

3. **One narrower thing does survive, and it points the opposite way from the note.** After a
   country-leadership inversion this severe, the *pre-inversion* leadership has historically
   reasserted over the following ~6 months in **16 of 21 episodes**, beating the new leaders by a
   median **+5.9%**. Today's pre-inversion leaders are the AI complex — Korea, Taiwan, the
   Netherlands. The note concludes "the leadership that got us here won't be the leadership that
   carries us forward." History's base rate says the opposite, more often than not. This finding
   is **post-hoc**, rests on 21 episodes, and **fails precisely in genuine crises** (2008, 2009).

---

## Prior verdicts this brief does not pretend away

History-as-predictor has been tested in this repo four times and died every time:

| Experiment | Verdict | Evidence |
|---|---|---|
| Strategy #1 PCA world-state analogs | DEAD (NO-GO) | `docs/strategy/lessons.md:1-20` — IC≈0, sticky basis, n≪p |
| `regime/` v2 regime conditioning | DEAD | `regime2.md:12-18` — 0/52 factors significant post-BH-FDR |
| `regime_factor_selection/` | DEAD (clean null) | `regime_factor_selection/results/RESULTS.md:5-13` — 0/74 clear FDR |
| `regime_ew/` per-country HMM | DEAD (Gate 3) | `regime_ew/results/RESULTS.md:5-11` — 17/34 countries wrong sign |

Part 2 below is a fifth independent null on the same mechanism. Nothing here overturns those.

---

## Data as-of (stated, not assumed)

| Surface | Last observation |
|---|---|
| T2 daily levels / total-return index | **2026-09-02** |
| T2 monthly panel (`t2_raw`, `t2_master`) | 2026-08-01 (returns through end-July) |
| `factor_returns` (optimizer) | 2026-07-01 |
| World Bank Brent (monthly average) | **2026-07** — the August `OIL_3M` reading carries July forward and is flagged `*` |

Late-August narrative events (the 27 Aug Nvidia print, the late-August dollar rally) are inside
the daily window but outside the monthly panel and outside the Brent series.

---

## Part 1 — Testing the narrative leg by leg

| Narrative claim | ASADO says | Verdict |
|---|---|---|
| Leadership rotated | Spearman rank corr between 2026-H1 and post-Jul-1 country returns = **−0.40** | **CONFIRMED, strongly** |
| Yields rose 25–30bp | US 10Y 4.48 → 4.79, **+30.7bp** since Jul 1 | **CONFIRMED** — but H1 rose +29.7bp too, so the pace is not new |
| AI/semis paused | NASDAQ +0.5% since Jul 1 vs +13.1% in H1; Korea +118%→−9.4%, Taiwan +62%→−0.2%, Netherlands +38%→−5.9% | **CONFIRMED, dramatically** |
| Breadth expanded significantly | Countries beating EW: 46.9% → 50.0%. EW +4.5% beat US +2.2% and NASDAQ +0.5% | **PARTIAL** — leaders stopped leading; participation barely widened |
| Inflation scare revived by oil | Brent $71 (Jan) → **$120 (Apr)** → $85 (Jun) → $83 (Jul). 3-month oil momentum is **negative** (z ≈ −1.4) | **CONTRADICTED** — the oil shock was a Q1–Q2 event now *unwinding* |
| Higher volatility | Mean 20-day country vol 21.7 → 19.9; month-end Aug reading **15.0 (25th pctile)** | **CONTRADICTED** |
| Lower correlation | Avg pairwise country correlation **0.40 → 0.19** (2.8th percentile since 2000) | **CONFIRMED, emphatically** |
| Dispersion widened | Daily cross-sectional dispersion flat (0.041→0.042); top5-minus-bottom5 spread **collapsed 70% → 16%** | **CONTRADICTED** — the winner/loser gap narrowed sharply |

**Reframing.** The warehouse's story is not "supply shock plus hike fear arriving." It is *two
crowded Q1–Q2 trades unwinding at once* — the AI/semiconductor complex and the oil spike — into a
market with no dominant theme, unusually low correlation, low volatility, and a much narrower
winner/loser gap. The tone change is a **de-concentration**, not a stress event.

### Biggest movers, H1 rank → post-Jul-1 rank (of 32)

| Country | 2026 H1 | Since Jul 1 | Rank change |
|---|---|---|---|
| Korea | +118.5% (1) | −9.4% (32) | **−31** |
| Netherlands | +38.5% (3) | −5.9% (31) | −28 |
| Taiwan | +61.7% (2) | −0.2% (28) | −26 |
| Thailand | +25.5% (4) | −1.6% (30) | −26 |
| Indonesia | −41.0% (32) | +14.4% (3) | **+29** |
| South Africa | −5.1% (28) | +11.2% (4) | +24 |
| ChinaA | −15.8% (31) | +7.0% (9) | +22 |
| Hong Kong | −1.0% (25) | +8.8% (5) | +20 |

---

## Part 2 — The pre-registered analog test: a null

Six-dimension state vector (oil 3m change, US 10Y 3m change, EW-minus-cap-weight breadth,
NASDAQ-minus-EW tech lead, cross-sectional dispersion, volatility), expanding-window z-scored so
no historical reading uses future information. Anchor 2026-08-31, z = oil −1.36\*, yields +0.75,
breadth +0.32, tech lead −0.70, dispersion +0.19, vol −0.65.

**Today's state is not extreme.** No dimension is beyond ±1.4σ. The genuinely unusual months were
February–June 2026 (oil z +3.0, dispersion z +1.9); that regime has been *decaying* since July.

| Screen | Months | Episodes | Result |
|---|---|---|---|
| A — pre-registered condition screen (4 of 4) | 3 | 3 | too few to say anything |
| A3 — relaxed (3 of 4) | 27 | 14 | forward EW/breadth/momentum ≈ unconditional |
| B — kNN, k=24 | 24 | 17 | forward EW/breadth/momentum ≈ unconditional |
| C — post-hoc inversion cut | 50 | 24 | ≈ unconditional |

Across 64 screen × outcome × horizon cells, **3 reach p<0.05** against a length-matched block
bootstrap — exactly the chance rate. None survives as a finding.

---

## Part 3–5 — The one thing that survives, and what breaks it

Part 1's real discovery was the leadership inversion, so the sharper question is: **after an
inversion, does the new leadership persist or does the old one come back?**

Define RC(t) = cross-country rank correlation between the trailing 6-month return through t−2 and
the last 2 months' return. Windows do not overlap the forward window.

**RC(2026-08-31) = −0.488 — the 4.2nd percentile of 2000–2026.** One of the sharpest leadership
inversions in the 26-year record.

Conditional on severe inversions (RC ≤ −0.40, 27 months in **21 episodes**):

| Horizon | Old leadership revives (rank corr) | Unconditional | Bootstrap p | New leadership persists |
|---|---|---|---|---|
| 3m | +0.166 | +0.035 | 0.099 | −0.073 (ns) |
| 6m | **+0.266** | +0.048 | **0.015** | −0.109 (ns) |
| 12m | **+0.211** | +0.024 | **0.006** | −0.099 (ns) |

**Economic size:** long the 6 pre-inversion leaders, short the 6 post-inversion leaders, held 6
months → median **+5.9%** (unconditional +0.3%); 12 months → +7.8%. Positive in **16 of 21**
episodes (76%).

### What I tried to break it with

| Test | Result |
|---|---|
| Leave-one-episode-out jackknife (6m) | range **[+0.256, +0.268]** — not driven by any single episode |
| Exclude 2008–09 and 2020 COVID | +0.268 (6m), +0.217 (12m) — **holds, slightly stronger** |
| Placebo: sign-flipped condition (RC ≥ +0.40) | revival flips **negative** (−0.12) — the effect reverses as a real conditional should |
| Threshold sweep | clean dose-response: ≤−0.50 → +0.27; ≤−0.40 → +0.27; ≤−0.35 → +0.12; ≤−0.25 → +0.09 |
| Block-bootstrap placebo, 95th pctile | 0.188 (6m), 0.140 (12m) — observed +0.266 / +0.211 clear it |
| **Subsample 2013–2026 (8 episodes)** | 6m holds at **+0.209**; **12m collapses to +0.031** |

### And the one I killed

A second Part-3 candidate — *low cross-country correlation precedes weak forward index returns*
(raw medians looked stark: 12m forward EW −2.0% vs +10.0% unconditional) — **dies under episode
clustering**. Once the 78 months collapse into 24 episodes and the null is length-matched, every
p-value lands between 0.27 and 0.98. It was a month-count artifact. Reported here because it is
the kind of result that would have looked publishable if I had stopped one step earlier.

---

## Caveats that materially limit the surviving finding

1. **It is post-hoc.** It was discovered in Part 1, not pre-registered in SPEC.md. The
   "distrust a searched pass" law applies with full force.
2. **Multiple testing is not controlled.** ~20 tests were run in Parts 4–5. Naive Bonferroni would
   not clear p=0.015. The real evidence is the placebo sign-flip and the dose-response, not the p-value.
3. **21 episodes.** Law 4 in the Research Agenda puts the per-mechanism true-positive rate at 15–20%.
4. **It fails exactly when it matters most.** The 5 negative episodes are 2008-05, 2008-08, 2009-04,
   2016-02, 2022-11 — i.e. when the inversion signalled a *genuine* regime break rather than a
   rotation head-fake. There is no ex-ante rule here for telling the two apart.
5. **The 12-month effect is gone post-2013.** Only the 6-month horizon survives the modern subsample.
6. **A rank correlation of 0.27 explains ~7% of rank variance.** It is a base rate, not a forecast.
7. This is index-space at monthly frequency, so the expression law (index-space alpha ≈ 0 in the
   US-listed ETF at the US close) applies to any implementation thought.

8. **"Old leadership revives" and "new leadership fades" are close to mirror images.** RC ≤ −0.40
   means the last-2-month ranking is roughly the inverse of the prior-6-month ranking, so the two
   rows of the table above are largely one effect presented twice, not two independent
   confirmations. The load-bearing number is the +5.9% old-minus-new spread, which measures it once.

---

## So: does history give a guide?

**On the macro state — no**, and this is now the fifth independent test in this repo saying so.
Knowing that oil, yields, breadth, dispersion and volatility sit where they do tells you nothing
statistically distinguishable about the next 1–12 months.

**On the price structure — weakly, and against the note's conclusion.** The only conditioning
variable with a signal is the shape of the rotation itself, not the macro behind it. Its base rate
says the July–August rotation is more likely a head-fake than a handover: the AI complex (Korea,
Taiwan, Netherlands) reasserts and the new leaders (Singapore, Poland, Indonesia, South Africa,
Hong Kong) fade, 76% of the time, by a median 5.9% over six months — **unless** this is one of the
crisis cases, where the same signal has been dead wrong.

The honest framing is a prior, not a call: *a rotation this abrupt has usually been noise, but the
exceptions were the moments that mattered.*

---

## Files

All paths absolute.

| What | Path |
|---|---|
| Pre-registration | [SPEC.md](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/experiments/2026_09_regime_analog_brief/SPEC.md) |
| This report | [REPORT.md](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/experiments/2026_09_regime_analog_brief/results/run_20260902_191004/REPORT.md) |
| Charts (PDF, light mode) | [charts.pdf](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/experiments/2026_09_regime_analog_brief/results/run_20260902_191004/charts.pdf) |
| Workbook (11 sheets) | [regime_analog_brief.xlsx](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/experiments/2026_09_regime_analog_brief/results/run_20260902_191004/regime_analog_brief.xlsx) |
| Run summary | [run_summary.json](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/experiments/2026_09_regime_analog_brief/results/run_20260902_191004/run_summary.json) |
| Code | [code/](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/experiments/2026_09_regime_analog_brief/code/) |
| Frozen data snapshot | [snapshot_2026_09_02](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/work/experiments/2026_09_regime_analog_brief/snapshot_2026_09_02/) |

No production table, config, ledger, or `Data/processed` path was written. The warehouse was
opened read-only for seconds to freeze snapshots and never held.
