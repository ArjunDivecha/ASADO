# G1 Flip Autopsy — Results

**Experiment:** `experiments/2026_07_flip_autopsy/` · **Run:** 2026-07-13 (single day)
**PRD:** committed at `bdfe9e4` BEFORE any measurement (Amendment 1 logged before measurement too)
**Question:** why did the network_spillover family's IC go negative in 2024–26 — crowding (a), regime interaction (b), or construction drift (c)?

## Executive verdict

**INCONCLUSIVE under the pre-registered taxonomy — (c) rejected, (b) rejected, (a) not confirmed — with the default action triggered: the family stays parked behind the agenda's R-A price gate (two consecutive positive month-ends re-arm it).** This was the outcome the agenda itself flagged as most likely. The autopsy nonetheless settles four things the record did not know this morning:

| Finding | Evidence |
|---|---|
| **The flip is real, not our artifact** (premise itself was previously undocumented — this memo is now the canonical evidence) | Frozen June-2026 harness IC series: family IC +0.023 (NW-t 4.0) 2012–23 → −0.012 post-2024, worsening monotonically (2024 +0.010, 2025 −0.011, 2026H1 −0.058). Today's recomputation matches the frozen record at corr 0.996 → no pipeline drift. PIT and non-PIT variants both flip → not an edge-vintage artifact. Constant-universe slice still flips; per-signal coverage identical 2023 vs 2025 → not composition. `a1_summary.json`, `a2_summary.json`, `a2c_constant_universe.json` |
| **The four regime axes do not explain it — the decay is state-independent** | Pre-2024 fit: no axis term significant (best NW-t 1.29, FDR passes none); conditional ICs flat across dollar/rates/dispersion buckets. Counterfactual: observed 2024–26 states predict IC **+0.031** (favorable!) vs observed **−0.011**, far outside the 90% CI; 28% of placebo draws are more pessimistic than the real states. C1/C2/C3 all FAIL. `a3_summary.json` |
| **Classic crowding is not confirmed** | S1 FAIL: no abnormal-inflow build-up into the signal's favored countries 2021–23 (z +0.15, needed ≥1.0). S2 weak PASS: 2024–26 losses tilt toward previously-high-inflow names (−0.91%/mo vs −0.70%/mo excess) but are broad, not concentrated. Pre-registered rule requires both → not confirmed. `a4_summary.json` |
| **Structure of the decay (the real clue)** | Break date 2024-04 (single-LS). Slow horizons died first and worst: 63d variants −0.019…−0.034 post-2024 vs pre +0.018…+0.024; the fastest signal (LL_LEADER_RET_1D) still positive (+0.025). The walk-forward daily combiner degraded gracefully — positive through 2025 (+0.026), first negative in 2026H1 (−0.022). `a2_drift_comparison.xlsx`, `a5_summary.json` |

## Interpretation (marked as interpretation, not a tested claim)

The pattern — state-independent decay, no ownership build-up fingerprint, slowest-diffusion horizons dying first, the adaptive combiner surviving longest — is most consistent with **absorption-speed compression**: the cross-country linkage information the family harvests over 21–63 trading days is now being priced faster than the diffusion window. That is generic-efficiency arbitrage (the mechanism getting *learned*), which produces exactly this signature and would NOT produce a flow/positioning fingerprint. The 2024-04 break sits in the H1-2024 "higher-for-longer" repricing, but the regime counterfactual says the macro state itself is not the cause; the EM/DM flow reversal began 2023-05, eleven months before the break, and the USD trend flipped sign six times 2024–25 — neither aligns.

## What this gates (per Research-Agenda-2026-07-v2 G1)

- **S2 slow-graph book revival: does NOT open.** No fixable artifact was found; the decay is market-based.
- **G2 trade-partner spillover build: stays gated** ("build only after G1 says cyclical or fixable" — it said neither).
- **Alpha Book: remains on its 2027-12 sunset path** unless the R-A price gate (two consecutive positive family month-ends) re-arms it first.
- **The one live survivor worth watching:** LL_LEADER_RET_1D (+0.025 post-2024) and, to a lesser degree, GRAPHP_BANK_NBR_RET_GAP_21D (+0.008 — the record's strongest signal decayed to zero, not through it).

## Recommendation requiring Arjun's decision (ops change — not made by this experiment)

The flip went undocumented for ~15 months because **family IC is not monitored nightly** — the harness runs only on demand (June 2026 was the family's first-ever measurement). Proposal: add a lightweight nightly family-IC tracker (reuse `a2_drift_test.py` machinery) writing one row per family per night to the loop DB, with the R-A price gate evaluated automatically. This is pipeline change-control territory → needs approval; logged in `docs/USER_FIX_LIST.md`.

## Honest caveats

1. The premise verification and all measurements share one outcome source (`1DRet`-derived returns) — consistent with the harness, but any convention error there would propagate everywhere (mitigated by matching the frozen June record at corr 0.996 with independent code).
2. Dispersion axis: intended expanding quintile realized as a 1–4 ordinal (int-truncation; bucket 5 unreachable). Immaterial (t = 0.38; conditional means flat) but recorded.
3. M2's `usd_sign` raw t = 2.11 on the short 2015+ sample does not survive FDR and carries the *opposite* sign to the dollar-hurts-the-family story; treated as noise per pre-registration.
4. S2's margin (21bp/mo) is within noise for 29 months; do not cite it as crowding evidence on its own.
5. Placebo count 500, circular shifts 24–200 months, seed 20260713 — deterministic and reproducible.
6. The 2026-07 Investment Learnings cost-law retraction is irrelevant here (no cost modeling in a diagnostic).

## Artifacts (all under `experiments/2026_07_flip_autopsy/results/`)

- `a1_summary.json`, `a1_per_year_ic_json.parquet/.xlsx`, `a1_family_ic_monthly.parquet` — premise verification (frozen June record)
- `a2_summary.json`, `a2_drift_comparison.xlsx`, `a2_recomputed_ic_daily.parquet`, `a2_family_ic_monthly_recomputed.parquet`, `a2c_constant_universe.json` — drift tests
- `a3_summary.json`, `a3_conditional_ic.xlsx`, `a3_states_monthly.parquet`, `figures/a3_counterfactual.pdf` — regime conditioning
- `a4_summary.json`, `a4_crowding.xlsx`, `figures/a4_crowding.pdf` — crowding forensics
- `a5_summary.json` — event alignment + live-combiner tie-out
- Code: `a1_premise_check.py`, `a2_drift_test.py`, `a3_regime_conditioning.py`, `a4_crowding.py`, `snapshot_daily_returns.py`
- Input freeze: `Data/work/experiments/flip_autopsy/snapshot_2026_07_13/` (MANIFEST.json)

---

## A7 addendum (2026-07-15) — the EWS fifth axis

Arjun's Early Warning System state (IN/TRANSITION/OUT, event-validated 12-signal confluence,
`Early Warning/outputs/run_20260715_113935`) was pre-registered as a fifth conditioning axis
(PRD Addendum A7) and tested against the family IC. Result — **the first axis to cross its bar**:

| Outcome | Period | mean IN | mean NOT-IN | NW-t (IN−NOTIN) |
|---|---|---|---|---|
| roster16 | pre-2024 | +0.022 (n=196) | **+0.043** (n=92) | **−2.17** ✂ bar |
| roster16 | 2024+ | −0.032 (n=13) | +0.002 (n=16) | −1.03 |
| book5 | pre-2024 | +0.031 | +0.049 | −1.58 (below bar) |

**Reading:** the propagation family historically earned ~2× its IC in TRANSITION/OUT months —
contagion propagates during stress; calm markets give it less to harvest. **The flip conclusion is
unchanged**: both states degraded by similar magnitudes post-2024 (IN −0.055, NOT-IN −0.041 level
shifts; negative 2024+ months split 44/56 IN/NOT-IN ≈ the base rate), so the decay remains a
state-independent level shift ON TOP of a real habitat difference. Honesty stamps: (1) fifth axis
tested — t=2.17 (p≈0.03) would NOT survive a five-axis FDR; the pre-registered single-axis bar
was 2.0 and is honored with this caveat attached; (2) the effect is a MEAN difference (state stds
pre-2024 are equal, 0.081 both) — not a dispersion artifact (a3's dispersion axis was flat); (3)
book-5 roster same direction, below bar. **Use-class: context tier for re-arm sizing** — if the
family re-arms while the EWS reads IN (its historically weaker habitat, and the current reading),
size accordingly; no trading rule registered. Artifacts: `a7_summary.json`, `a7_ews_axis.xlsx`.
