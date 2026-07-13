# PRD — G1 Flip Autopsy (network_spillover family, 2024–26 IC sign flip)

**Experiment:** `experiments/2026_07_flip_autopsy/`
**Date frozen:** 2026-07-13 (before any conditional IC, vintage comparison, or crowding number was computed)
**Provenance:** Research-Agenda-2026-07-v2 project G1 (Territory T-GRAPH, "the Alpha Book's Gate R-C"); `regime3_candidates.md` R3. The four regime axes below were specified in the agenda before this experiment existed.
**Type:** Diagnostic methodology experiment. NOT a signal registration — no harness trial is charged, no new hypothesis enters `family_registry.yaml`. Gross ICs throughout; no cost modeling (transaction-cost gates are retracted per Arjun's 2026-07-13 directive, and none are needed for a diagnostic).
**Sandbox:** code + small results here; snapshots and scratch in `Data/work/experiments/flip_autopsy/`. No writes to `Data/processed/`, `Data/loop/`, `config/`, `ledgers/` from experiment code.

---

> **AMENDMENT 1 (2026-07-13, logged BEFORE any measurement):** recon found no repo artifact
> documenting the premise (post-2024 negative family IC); the Alpha Book (2026-07-02) reports the
> family positive in both sample halves, and the family was harness-measured only on 2026-06-10/12.
> Therefore a fifth outcome is added: **(∅′) premise false — no flip exists** (family IC 2024→ is
> not materially negative under §3's definition). Phase order updated: verify the premise first,
> from the frozen June-2026 harness JSONs' per-year IC tables, then from fresh recomputation.
> Recon also established there are NO stored nightly signal vintages (all signal tables are
> drop-and-recreate; `build_combiner.py:208-210,307-309`, `build_graph_features.py:371-372`) and
> essentially a single construction commit (`96d0f80`) — so step (i-a) binds to "frozen June-2026
> harness JSONs vs today's recomputation" and step (i-b) code-vintage reconstruction is DROPPED
> (no code vintages exist to reconstruct). (i-c) coverage slices and PIT-vs-non-PIT comparison
> remain. No numbers were seen before this amendment.

## 1. Question

The network_spillover family (GRAPH*/GRAPHP*/LL_*/SIM_* — "neighbour returns propagate before the endpoint reprices"), the strongest mechanism in the ledger record, shows negative ICs since ~2024. Exactly one of four verdicts must come out of this memo:

- **(c) Construction drift** — the nightly pipeline changed the signal; the flip is our artifact.
- **(b) Regime interaction** — the IC is genuinely state-dependent and 2024–26 sits in the bad state.
- **(a) Cyclical crowding** — the trade got owned and is unwinding.
- **(∅) Inconclusive** — say so; default to the agenda's pre-registered R-A price gate (family re-arms after two consecutive positive month-ends).

Checked strictly in the order (c) → (b) → (a): drift first because if the flip is an artifact everything downstream is moot.

## 2. Subject roster (deterministic, no cherry-picking)

- **Signals:** every `network_spillover`-family variable (prefixes `GRAPH`, `LL_`, `SIM_`) whose FINAL ledger verdict is WEAK or WATCH (dedupe to last verdict per hypothesis_id, as per graveyard protocol §1b). DEAD variables are excluded from the family composite but reported individually in an appendix.
- **Aggregates:** the daily ridge combiner series (`combiner_scores_daily` / COMBINER_RIDGE_DAILY_V1) as the family's live expression.
- **Outcome:** next-period country returns exactly as the harness defines them (same source and alignment as `evaluate_signal.py`; forward-return variables used ONLY as outcomes, never as predictors).

## 3. Metrics (fixed)

- **Per-signal IC_t:** cross-sectional Spearman rank IC of signal at t vs next-period country return at the signal's registered horizon, sign-aligned to its registered direction (so +IC always = "worked").
- **Family IC_t:** equal-weight mean of sign-aligned per-signal ICs, monthly frequency (daily ICs averaged within month).
- **Flip established as:** mean family IC 2024-01→latest vs mean 2012-01→2023-12, with Newey-West (lag 6) t on the difference; break date estimated by single-unknown-breakpoint least squares on the monthly family IC, search window 2022-01→2026-01. These numbers are descriptive anchors, not gates.

## 4. Step (i) — Drift test (kill test; run FIRST)

- **(i-a) Vintage-vs-recompute:** where stored historical signal values exist (nightly-written rows whose values were computed at the time), compare them to a today's-code recomputation for the same dates. Metric: per-date cross-sectional Spearman between stored and recomputed signal. **Pre-registered reading:** median ≥ 0.98 and no sustained window < 0.95 → "no material value drift"; any sustained window < 0.90 → drift candidate, localize the commit.
- **(i-b) Code-vintage reconstruction:** if (i-a) is impossible (values rewritten nightly; no vintages) or shows divergence: identify builder commits 2024-01→2026-07 that touched construction; rebuild signals at the newest pre-flip commit in a **git worktree** (never a checkout in the production tree) on frozen raw inputs; compare IC histories old-code vs current-code on identical raw data. **Drift confirmed** iff pre-flip code on the same data does NOT reproduce the flip while current code does.
- **(i-c) Coverage-stability slice:** recompute the family IC on the pre-existing stable-coverage sub-universes already used by the ledger re-tests (e.g. the 17 stable BIS LBS reporters for BANK signals; the structural-follower sets for LL). **If the flip vanishes on stable-coverage slices while present on full coverage → data-composition artifact** (a sub-species of (c)).
- **Decision:** any confirmed drift → verdict (c); STOP the autopsy; report. Pipeline fixes are change-control territory and require Arjun's approval — this experiment only diagnoses.

## 5. Step (ii) — Regime conditioning (only if the flip survives step (i))

**Four axes, frozen (all PIT-lagged to information available at month-end t):**
1. **US 10y real rate** — level (expanding z) and 12m change (sign): `BBG_Govt_Bond_10Y`(U.S.) − `BBG_Breakeven_10Y`(U.S.).
2. **Broad-USD trend** — sign of trailing 12m return and expanding |z| of it; series preference order: a broad USD index if present in the warehouse; else fixed-weight DXY-style basket from `ecb_fx` majors (EUR 57.6, JPY 13.6, GBP 11.9, CAD 9.1, SEK 4.2, CHF 3.6 — the fixed ICE weights, deterministic).
3. **Cross-country return dispersion** — monthly cross-sectional std of the 34 country returns (outcome table itself); state = expanding-window quintile.
4. **EM/DM flow regime** — EM-minus-DM mean of `MS_ETF_NetFlow_to_MarketCap`, 3m mean, expanding z (coverage 2015→ only; acknowledged and reported as the shorter axis).

**Tests, frozen:**
- Conditional mean family IC by state bucket; NW-t on bucket differences.
- Interaction regression IC_t = α + Σβ_k·State_k,t + ε, NW lag 6, on pre-2024 data.
- **The decisive counterfactual:** fit the conditional model on **pre-2024 only**; feed it the observed 2024–26 states; compare predicted vs observed 2024–26 mean IC.
- **Placebo:** 500 circular block-shifts of the state matrix (preserving autocorrelation), same pipeline, to calibrate how often noise "explains" the flip.

**Pre-registered criteria for verdict (b) — ALL three:**
1. ≥1 axis coefficient significant at BH-FDR α=0.10 across the 8 axis terms, fit on pre-2024 data;
2. predicted 2024–26 mean IC from the pre-2024 model is ≤ the 25th percentile of pre-2024 rolling-30-month mean ICs (states genuinely forecast a bad spell), AND the real-state prediction error beats ≥95% of placebo draws;
3. observed 2024–26 mean IC falls within the counterfactual's 90% CI (no large unexplained residual flip remains).
Failing (1) or (2) → regime interaction rejected. Passing (1)–(2) but failing (3) → "partial regime contribution, residual unexplained" (reported honestly; does not open the S2 gate on its own).

## 6. Step (iii) — Crowding forensics (only if (c) rejected)

- **Portfolios:** monthly top-7 / bottom-7 countries by the family composite (sign-aligned mean of roster signals; combiner score where the composite is unavailable).
- **Metrics 2015→2026 on those portfolios:** cumulative `MS_ETF_NetFlow_to_MarketCap` (abnormal vs 34-country mean), `MS_Passive_AUM_to_MarketCap` drift, and (coarse, annual) `portfolio_ownership` shifts.
- **Pre-registered crowding signature (verdict (a) requires BOTH):** top-portfolio abnormal inflow z ≥ +1 sustained over 2021–2023 with reversal 2024–26; AND 2024–26 family losses concentrated in the previously-high-inflow half of the top portfolio (split-half comparison). Crowding evidence is descriptive; verdict (a) additionally requires (b) and (c) to have been rejected.

## 7. Step (iv) — Event alignment (descriptive)

Estimated break date laid against: the 2024 EM flow reversal, tariff-regime onset, and the Fed cutting-cycle start. Narrative corroboration only; no gate.

## 8. Deliverable & bookkeeping

- `results/RESULTS.md` — the mechanism memo: verdict + numbers + what it gates (S2 revival / G2 build / Alpha Book 2027-12 sunset).
- All intermediate parquets + figures (PDF, light mode) under `results/`; incremental writes.
- Methodology-ledger entry (`ledgers/methodology_ledger.jsonl`) appended at verdict time via the existing mechanism (a diagnostic verdict, not a signal trial). If the mechanism can't accept a diagnostic entry, record in RESULTS.md only and flag to Arjun.
- If any pipeline bug is found: append to `docs/USER_FIX_LIST.md`, do NOT fix collector/T2 code silently.

## 9. What this experiment may NOT do (self-imposed)

- No trading rule, no sleeve, no harness registration, no `--force` sweeps.
- No tuning of the axes, buckets, thresholds, or roster after seeing results — deviations get logged in RESULTS.md as post-hoc and cannot change the verdict.
- No writes outside the sandbox; no held DB connections (snapshot-first; any unavoidable live touch is open→query→close).
