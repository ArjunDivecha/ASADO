# ox.md — Alpha-Hunting Loop improvement ideas

| Field | Value |
|---|---|
| **Date** | 2026-08-21 |
| **Author** | Session "ox-alpha" (Claude Code), at Arjun's request |
| **What this is** | 62 improvement ideas for the Alpha-Hunting Loop, from a full read of the loop (PRD, orchestrator, skeptic harness, all builder/detector scripts, live loop-DB state, docs/ledger history). Ideas only — nothing here has been implemented. |
| **How produced** | Main session read: `PRD_Alpha_Hunting_Loop.md`, `scripts/loop/loop_daily_job.py`, `scripts/harness/evaluate_signal.py` (v4), `ASADO_ML_ARCHITECTURE_PLAN.md`, `ASADO_LEAKAGE_AUDIT.md`, `harness_v4_honest_ledger.spec.md`. Four read-only subagent sweeps covered the graph-machine builders, detectors + Triptych, the skeptic tooling + live `Data/loop/asado_loop.duckdb` state, and the docs/llmchat/experiments record. |
| **Status** | Proposal document. Sizes: **[S]** hours–1 day, **[M]** days, **[L]** weeks. |

**Repo root for every path below:** `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/`

Key files referenced (full paths):

- [PRD_Alpha_Hunting_Loop.md](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/PRD_Alpha_Hunting_Loop.md) — the loop's founding spec
- [scripts/loop/loop_daily_job.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/loop/loop_daily_job.py) — the 37-step nightly orchestrator
- [scripts/harness/evaluate_signal.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/harness/evaluate_signal.py) — the skeptic (harness v4)
- [scripts/loop/build_dislocations.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/loop/build_dislocations.py) — detectors D1–D10
- [scripts/loop/build_combiner.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/loop/build_combiner.py) — walk-forward ridge combiner
- [scripts/loop/ledgers.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/loop/ledgers.py) — hypothesis/thesis/methodology ledgers
- [scripts/loop/build_graph_features_pit.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/loop/build_graph_features_pit.py) / [build_graph_features.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/loop/build_graph_features.py) — PIT and v1 graph features
- [scripts/loop/build_price_state.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/loop/build_price_state.py) / [build_gap_episodes.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/loop/build_gap_episodes.py) — gap engine
- [scripts/loop/event_study.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/loop/event_study.py) / [scripts/harness/sweep_signals.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/harness/sweep_signals.py) / [scripts/harness/ff_spanning.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/harness/ff_spanning.py)
- [scripts/loop/build_family_ic_monitor.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/loop/build_family_ic_monitor.py) / [attribute_outcomes.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/loop/attribute_outcomes.py) / [score_gap_outcomes.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/loop/score_gap_outcomes.py)
- [Data/loop/asado_loop.duckdb](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/loop/asado_loop.duckdb) — live loop state (read 2026-08-21)
- [ASADO_LEAKAGE_AUDIT.md](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/ASADO_LEAKAGE_AUDIT.md) / [ASADO_ML_ARCHITECTURE_PLAN.md](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/ASADO_ML_ARCHITECTURE_PLAN.md) — Milestone-0 audit + ML plan

---

## The meta-finding

**The loop's weakest link is no longer data or detection — it is that the loop does not close.** The detection/feature machinery runs nightly and is genuinely well-built (PIT graph edges are clean by construction; the harness v4 execution embargo is honest; gap-engine config hashing is real pre-registration). But on 2026-08-21 the live state shows:

- **No harness runs since 2026-07-14**; no hypothesis registrations since 07-27 (`H_20260727_003` registered, never tested). Signals are produced nightly with nobody scoring them.
- **3 theses have ever been opened** (all 2026-06-10). The calibration report's ≥10-closed gate is mathematically unreachable at this rate. Layer 2 (the reasoning pass) effectively does not run.
- **1,447 LLM forecasts** in `brier_gate_live` (deepseek-v4-pro 1,404 / claude-fable-5 43), **zero resolved, zero scored**, all resolve-by dates passed.
- **Two finished artifacts have zero consumers**: `triptych_review_queue` (25 rows; passive readers only) and `triptych_signal_monthly` (TRIPTYCH_QUEUE_LEAN, stale since 07-01, no reader anywhere in the tree).
- **D6/predmkt is dead**: the brief claims predmkt is "accumulating since 2026-06-10", but the loop DB contains **no predmkt tables at all**. The claim is false every night.
- `outcome_attribution` (the gap engine's own ledger): **60 of 94 outcomes (64%) classified DATA_WRONG**.

Everything below is grounded in findings like these. Themes: 1) close the loop, 2) silent bugs, 3) skeptic statistics, 4) detectors, 5) combiner/ML, 6) data/features, 7) ops/meta.

---

## Theme 1 — Close the loop (highest leverage)

1. **[S] Restart the verdict pipeline.** Add a weekly auto-sweep of all registered-but-untested hypotheses through the `evaluate_signal` front door (trial accounting intact). Today the factory produces and never inspects.
2. **[S] Score the `brier_gate_live` backlog.** Write the resolver/scorer job for passed resolve-by dates. This is the LLM-calibration experiment, currently running for nothing.
3. **[M] Automate the Layer-2 morning pass.** A headless session that reads the nightly brief + evidence packs and writes structured theses (probability, invalidation level, catalyst) to the thesis ledger. The PRD's loop-closure principle ("nothing the model says evaporates") is currently unenforced — 3 theses in 10 weeks.
4. **[M] Auto-register Fable conjectures.** `fable_claims` has 110 rows with no grading loop. Wire claims → hypothesis ledger under a `fable_conjecture` family so conjectures are charged and validated, not evaporated.
5. **[S] Decide the fate of the two orphaned Triptych artifacts.** The walk-forward signal: register as a harness family (deliberately burns trials — Arjun's call, previously deferred) or retire. The review queue: its *rule* tested DEAD as a signal (H_20260702_001), so define its role explicitly as prior/context generator, never signal.
6. **[M] Score every detector's firings.** Only D1 and the gap engine have outcome scoring; D2/D4/D9/D10 firings are never marked against forward returns. Generalize `score_gap_outcomes.py` to all detectors → monthly per-detector precision curve in the brief.
7. **[M] Retro-miss audit (recall, not just precision).** Monthly pass: top-10 |return| country moves — which detectors *should* have fired? Log misses; the only way to improve detector design against the base rate of big moves.
8. **[M] Anchor thesis probabilities in base rates.** At thesis open, attach event-study CARs and historical base rates for that trigger type × regime, so stated probabilities are reference-class anchored. (The 2 closed theses averaged Brier 0.189 — promising, n=2.)
9. **[S] Thesis book constraints + richer scoring.** Cap open theses per country/regime/detector (correlated paper book); add expected-payoff at open and realized payoff at close; stop conflating stop-outs with horizon-expiry in one Brier pool (`ledgers.py:489-516`).

## Theme 2 — Silent bugs found 2026-08-21 (fix before anything builds on them)

10. **[S] Fix D6/predmkt or stop the false claim.** The `com.arjundivecha.asado-predmkt-daily` chain either isn't running or isn't loading. Related: `predmkt_resolutions` has never had a row (idea 54).
11. **[S] `build_price_state.py` fabricates direction.** Missing/None scores render as `direction_hint="short"` (`"long" if (score or 0) > 0 else "short"`, ~:239-249), and `latest_signal` swallows all exceptions to `{}` (~:78-79). Violates the never-render-n/a and fail-is-fail house rules.
12. **[S] `build_gap_episodes.py` lifecycle hole.** `partially_absorbed` past max_age matches no closure branch (~:529-581) → episodes stay open forever; `etf_drag_score = expense_bps/100` looks like a bps↔percent confusion (10–100× too large); 63d/126d episodes are absorption-marked on a 21d window (~:509-514, :602).
13. **[S] Freeze `canonical_family` at registration.** `canonical_family_of()` re-resolves from the *current* registry at count time (`ledgers.py:310-319`) — a registry edit silently re-shuffles every family's DSR trial count N. This corrupts the multiple-testing ledger's foundation.
14. **[S] Clear the family-registry RED.** Two unclassified variables (`KEEPLIST_93_HGB_WALKFWD`, `WIDE_DEEP_RAW_HGB_WALKFWD`) have held the registry RED since 07-29, and registration *raises* on unclassifiable variables — this may be blocking idea 1's sweep. Also fix the `build_governance_scorecard.py:145` bug that reports a missing `signal_spec.variable` as a taxonomy gap.
15. **[S] Retire or quarantine graph-features v1.** `build_graph_features.py` is the known-lookahead duplicate of the PIT version, published side-by-side with `source='graph'`; one wrong table choice in a consumer re-opens leakage finding L-05. Its snapshot archive is also last-write-wins within month (~:182).
16. **[S] D5's silent staleness skip** (`build_dislocations.py:548`) is the one detector violating the loud-DETECTOR_DEGRADED constitution — a dead GDELT feed just makes D5 vanish. D5 has fired twice ever; audit whether its input is even alive.
17. **[S] `attribute_outcomes` mis-matches severity by entity only, not detector** (~:162-169) — with 9 detectors on one entity the z can come from the wrong one; and `net=None → negative_net` (~:123) biases toward "data right, not capturable."
18. **[S] Split D8 out of `dislocation_daily`.** Stewardship rows are 1,293 of 2,603 (50%) — they dilute every detector statistic and the brief.
19. **[S] Hygiene batch.** Neo4j password hardcoded in 4 scripts → env; `dislocation_daily.first_seen` still VARCHAR (NaT class risk, deferred); USER_FIX_LIST #6 fixed 08-13 but not closed; `PRD_LLM_12M_Country_Return_Predictor.md` header says "no code written" for a run that completed and died; `docs/README.md` and `docs/factor_reference.md` stale vs the 08-11/13 rebuilds; both graduated specs still say `status: draft`.
20. **[S] Investigate the freshness gaps.** Loop last produced a brief 08-19 (today 08-21); `country_returns_monthly` maxes 07-01; `eco_surprise_signals` 07-01; `sov_rating_changes` 06-01 (verify genuine); `triptych_signal_monthly` 07-01. Some are label conventions, some are breaks — idea 59's freshness contract would tell you which.
21. **[M] Vintage the optimizer workbook at sweep time.** `T2_Optimizer.xlsx` was restated across its entire history 2026-08-09 (71.6% of cells changed) — stored sweep results no longer reproduce. Pin a snapshot of optimizer inputs whenever a sweep runs, so verdicts stay reproducible.

## Theme 3 — Skeptic statistics (the harness itself)

22. **[S] Raise the DSR bar.** `DSR > 0` ≈ PSR > 50% — a coin flip. Standard practice is PSR ≥ 0.95; at minimum report both and key WATCH to the stricter.
23. **[S] Deflate the IC gate too.** NW-t ≥ 2.5 has no multiple-testing discount; scale the threshold by family N (E[max t] under null), mirroring what DSR does for Sharpe.
24. **[S] Charge direction flips.** Direction is chosen by the registrant and never counted as a trial; the ETF_FLOW flip (contrarian, confirmed WEAK) shows flips need their own trials.
25. **[S] Kill family shopping.** Sweep dedupe is per `family_key` — the same spec under a new family escapes the cache and gets a fresh N. Add a global spec-hash index. Also fix within-sweep order-dependence (later signals face larger N): freeze N at sweep start.
26. **[M] Correlated-trial correction.** Families share the same return panel; DSR's independence assumption overstates the discount. Effective-N via IC-series correlation across family members.
27. **[M] Fix the monthly clock mix.** The IC gate can sit at the registered 3m/6m horizon while the portfolio and DSR are always computed on the 1-month book. Run the portfolio at the registered horizon (or both, gated on the registered one).
28. **[S] Two portfolio-construction biases.** Empty bottom tranche contributes 0.0 to `ret_bot` (`backtest_daily` ~:457) — biases LS up; skip the day or require both tranches. And the IC-only fallback can still issue WATCH when the portfolio block errors (`decide_verdict` ~:595-600) — make fallback WATCH-ineligible.
29. **[M] Add PBO/CSCV.** Combinatorially-symmetric cross-validation probability of backtest overfitting as a standard output alongside DSR — they catch different overfitting modes.
30. **[S] Regime-conditional IC as standard output.** Regime tags exist and H2 (conditional IC dispersion) PASSED — the harness should report IC by regime for every run, not just calendar sub-periods.
31. **[M] Cluster-robust event studies.** Currently independence-assumed with overlap only flagged: add date-clustered or BMP/Kolari-Pynnönen inference; fix `nancumsum` NaN-dilution of CARs; compound rather than sum CARs.
32. **[S] Wire `ff_spanning` into promotion.** Style-spanning exists but nothing requires a WATCH to pass a spanning-alpha test before a strategy PRD. Make it a promotion gate.
33. **[S] Standard sensitivity outputs.** IC at alternative start dates (2005/2008/2010 — `start_date` is currently a free parameter); binomial test + month-weighting on the `pct_positive_years` gate; replace gap-inferred monthly lags with the documented per-source lag dict (BIS/IMF/OECD 3, EPU 2, WB QPSD 5, BBG 1).
34. **[M] Per-hypothesis decay monitoring.** `build_family_ic_monitor.py` is family-level with a noise-easy gate (2 positive month-ends, no t-stat, no magnitude) and equal-weight member ICs. Add per-hypothesis live-IC tracking with a t-stat gate and an alert when a WATCH's forward IC decays — the Alpha Book's "everything died together" was invisible for months.

## Theme 4 — Detectors

35. **[L] Detector replay backfill — the single highest-leverage validation project.** Detectors are deterministic and their inputs (t2 daily to 2005, sovereign, market-implied, valuation) reach back years, but `dislocation_daily` has **45 run dates**. Replay 2008→present to manufacture real fire history, then event-study every detector with actual n. (Predmkt-dependent detectors can't replay; z-windows need burn-in handling.)
36. **[M] Placebo-calibrate the thresholds.** Every cut (1.5, 2.0, 0.5, 756d, top-10…) is a PRD round number with zero recorded calibration. Permute returns per detector → empirical null fire rates → set thresholds to target fires/year; publish the rate in the brief.
37. **[S] Make severities comparable.** D1's z and D10's z aren't the same scale; rank-normalize severities to per-detector percentiles so the brief's ordering means something.
38. **[S] Add hysteresis.** Fire-one-day/resolve-next churns statuses and `first_seen` IDs (no cooldown, no grace). Entry at 1.5z, exit below 1.0z, minimum active days.
39. **[S] A conjunction detector (E1, made deterministic).** ≥3 distinct detectors on the same country within 5 days → its own row. The PRD reserves conjunctions for Layer-2 reasoning, but co-firing detection is mechanical and cheap.
40. **[M] New detectors from machinery that already exists but has no detector:** twin-divergence (similarity features feed the combiner but nothing flags when twins de-converge), lead-lag violation (follower moves against its leader), flow-extremes-without-price-move (foreign/ETF flows |z|≥2, flat price), ratings-momentum (two agencies within 90d — the event table exists), CDS-vs-equity incoherence (extend D10 beyond FX options), curve-inversion *persistence*, consensus-revision divergence (upgrade D3, which is WEO-only and goes quiet 120d after each vintage — ECFC consensus is now daily).
41. **[S] D2 branch-1 gate.** The trade-gap branch fires on the gap alone — a global factor wobble can light up 34 countries. Add the own-price-flat gate branch 2 has, or orthogonalize the gap vs EW.
42. **[S] Fix in-sample z attenuation.** `zscore_last` includes the last point in its own 756d window (`build_dislocations.py:161`) — use leave-last-out z. Also D9's gap z is over the ENTIRE common history (~:742), conflating regime eras — make it rolling.
43. **[M] Graph hyperparameter sensitivity, registered once.** Katz α=0.5/3-hop, blocs k=4, K_TWINS=5, damping 0.85 are hand-set; one registered family sweeping 3 values each charges the search honestly.

## Theme 5 — Combiner & the ML path

44. **[S] Fix the combiner's ~1-week lookahead.** Daily labels at date t are t+1..t+5 compounded, and the annual refit trains on dates < Jan 1 (`build_combiner.py:274, :284-287`) — so late-December rows embed the first ~5 trading days of the *scoring* year. Purge the last 5 training days at refit.
45. **[M] Walk-forward component selection.** The 6 daily slots were picked in-sample (admitted at `build_combiner.py:47-52`); the honest fix is selecting components inside the expanding window only. Also `RIDGE_ALPHA=10` is never tuned — tune walk-forward or register the choice.
46. **[S] Breadth accounting.** The 6 daily slots are 3 graph variants + twins + leadlag + flows — one economic theme ("neighbors moved, I haven't") in six proxies. Publish the signal-correlation matrix and effective breadth (GR = IC×√breadth) so the composite's diversification is stated honestly.
47. **[M] Multi-horizon combiner heads.** Daily combiner targets 5d only; the monthly combiner died at month-end sampling — horizon structure is doing unknown work. Add 21d/63d heads as registered variants.
48. **[M] Meta-labeling: gate the combiner on detector co-firing.** Trade the daily combiner only when a dislocation is active on the country. Combines the loop's two strongest layers; register as its own family.
49. **[L] Milestone-1 PIT substrate remains the gate for everything ML** — already planned (`ASADO_LEAKAGE_AUDIT.md` L-01..L-13: forward returns in the feature view, full-sample T2 cleaning, all 1,440 registry rows missing publication lags, REER dual-convention). Don't duplicate; fund it. Include fixing the registry's local-vs-USD returns mislabel there.
50. **[M/L] Execute, don't redesign, the already-designed programs.** Learning-Loop stages 2–5 (multi-axis classifier, lesson ledger, weekly review board, learned priors, activation gate — `docs/LEARNING_LOOP_DESIGN_2026_07_10.md`); the boundaries-TSM 13-test sequence (holdout untouched — keep it that way); tree baselines after Milestones 1–2 (standing rule: tabular kill-criterion baseline first — the LLM-as-feature-extractor verdict is settled; don't re-litigate it).

## Theme 6 — Data & features

51. **[M] Decompose returns into equity + FX legs.** T2 returns are USD (registry wrongly says local). With daily FX already in the warehouse, split every country return into local-equity and FX components and report signal IC by leg — much of the ledger (CDS, rates, flows) may be FX trades in disguise, and "everything decayed together in 2024-25" is exactly what an FX-regime shift would produce.
52. **[S] Realized-risk features.** Own vol, beta/downside-beta to EW34, correlation-to-EW, skew — computable PIT-clean from daily returns in minutes, absent from the loop feature set, natural combiner inputs.
53. **[M] A fast graph to complement the slow one.** Trade/bank/holder edges update annually/quarterly; the lead-lag network (lag-1 raw corr, arbitrary 0.15 cut, timezone-dominated) is the only daily-ish graph. A monthly-refit realized-covariance network (graphical lasso, shrinkage) gives the spillover family a faster, denser cousin — and the family just RE-ARMED (2026-08-20), so this is well-timed.
54. **[M] Verify publication lags instead of assuming them.** Trade +4mo / bank +4mo / holder +9mo are documented assumptions; nothing checks actual first-publication dates. One verification pass either earns back lag (more usable history) or catches a leak.
55. **[M] Predmkt resolutions tracking.** Even once collection is fixed (idea 10), `predmkt_resolutions` stays empty without a resolver — and without resolutions there is no calibration of prediction markets, which is the whole point of E5/D6.
56. **[S/M] Automate the forward calendar.** CB meeting calendars and MSCI review dates are published; the curated YAML is fine for elections but will rot. Scrape the mechanical ones.

## Theme 7 — Ops & meta

57. **[M] DAG-parallelize the 37-step job.** Collectors are independent parquet writers; wave-parallelizing shrinks the Bloomberg-session window (the quota hard-stop took both nightly jobs dark for 2 days in August). Keep the loop-DB loaders serialized (single-writer).
58. **[M] Quota budgets + degradation modes.** Per-collector quota allocation; when low, skip optional pulls *loudly* rather than dying mid-pipeline (the 08-11 empty-TRI class of failure).
59. **[S/M] Freshness contract per table.** Expected cadence + max-lag alert for all 64 loop tables (heartbeat exists but doesn't know what "stale" means per table).
60. **[M] Research KPIs on the cockpit.** The cockpit shows state, not loop health. Add: trials/week, registrations vs verdicts, brief→thesis conversion, per-detector precision, calibration slope, family-budget usage, DSR-bar headroom.
61. **[S] Enforce config-hash pre-registration.** The gap engine records its config hash but nothing diffs it against the registered value — a silent weight edit is undetectable today.
62. **[L] The biggest open *research* question deserves a program: why did all 7 Alpha Book mechanisms decay together in 2024–25?** The flip autopsy was INCONCLUSIVE (state-independent, no crowding fingerprint, slowest horizons died first; working hypothesis "absorption-speed compression"). Design the discriminating experiments: per-mechanism decay curves vs crowding/flow proxies, decay vs signal age, decay vs universe breadth. The answer determines whether the loop is hunting a decaying edge class or a 2024–25 regime artifact.

---

## Sequencing: top 8 by leverage

1. **#1–2** Restart validation + score the forecast backlog — the machine currently validates nothing.
2. **#35** Detector replay backfill — turns 45 days of detector history into years, unlocking every detector-statistics idea.
3. **#10–17** Silent-bug batch — especially the false predmkt claim (#10) and the price_state direction fabrication (#11); both are trust-of-output issues.
4. **#3** Automated Layer-2 pass — without theses, calibration never starts and the loop has no memory.
5. **#13–14** Ledger-integrity fixes (canonical_family freeze, registry RED) — the DSR foundation.
6. **#22–25** Verdict-statistics tightening — cheap, and they change what WATCH means.
7. **#51** Return decomposition — likely re-frames what half the ledger's signals actually are.
8. **#62** The decay program — the answer determines whether the loop's product is worth scaling.

## Guardrails respected by this list

- **Dead ends not re-proposed:** Triptych queue-rule-as-signal, monthly combiner, dispersion throttle, valuation percentiles, short interest, FX vol level, economic-surprise (10/10 closed), regime-timing (5-for-5 graveyard), LLM-as-feature-extractor, ElasticNet-on-feature_panel, forward-return variables (hard-blacklisted).
- **Cost gating stays retired** (2026-07-13): no idea above uses cost or turnover as a gate.
- **Strategy-adjacent ideas (#38–43, #47–48, #51–53) should get the `quantpedia-prior-art` + graveyard check before building** — the loop's own hypothesis ledger is the graveyard of record; graph spillover is alive-but-decayed/re-armed, lead-lag and twins have existing verdicts.
- **Already-planned work referenced, not duplicated:** ML Milestones 1–15, Learning-Loop stages 2–5, boundaries-TSM sequence, Alpha Book v2 re-authoring from post-v4 verdicts.
