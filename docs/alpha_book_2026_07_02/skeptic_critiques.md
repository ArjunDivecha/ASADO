# Adversarial Skeptic Critiques — Alpha Book 2026-07-02

Each sleeve design was independently attacked by a statistical skeptic (PIT integrity, multiple testing, in-sample selection, long-only degradation) and an execution skeptic (real per-ticker costs at $100k clips, turnover drag, pipeline timing, operational load). Verdicts: FATAL = do not fund; MAJOR = fund only after fixes; MINOR = fund with monitoring. The synthesizer rulings that resolved these are in ALPHA_BOOK_2026_07_02.md Part 2.0.

---

# S1-flagship-combiner

## Statistical skeptic

VERDICT: FATAL

CRITIQUE

**1. The tradable edge is statistically indistinguishable from zero, and the design's central numbers launder this.** I replicated mine_math's 13-month ETF tradability check exactly (n=264, top-5 h=5 on `etf_prices_daily`): mean +1.90 bp/day — matching their 1.9 — but sd 37 bp/day, **NW-t = 0.82, 95% CI [−2.6, +6.4] bp/day, annualized [−6.6%, +16.2%]**. The "capture 0.60" is a ratio of an insignificant numerator over a marginal denominator, yet it enters the return chain as a measured multiplicative constant producing "+4.4 to +7.7% realistic gross." Worse, the more direct test the design never reports: **ETF-based daily rank IC on the validated 29-name universe over the same window = −0.002 (t −0.16)** — first 63d +0.042, last 63d −0.038 — while the index-based IC in the identical window is +0.036 (t 2.64). The signal demonstrably exists in indices and demonstrably fails to show up in the instrument you'd actually trade. The design's own P-go metric (ETF IC ≥ +0.015 over 126 td) has, over the most recent 126 days of available data, already been failing. The central net-active claim (+1–2%/yr of NAV) is smaller than one standard error of every input it's built from.

**2. The design documents the wrong model.** `combiner_weights` (7 features, incl. CONS_CPI_REV3M_12M and ECO_INFL_SURPRISE_Z) is the **DEAD monthly model's** table. The actual traded daily signal, per `scripts/loop/build_combiner.py` `DAILY_FEATURES`, has **6 features, excludes both reflation overlays, and includes LL_LEADER_GAP_5D** — the lead-lag feature with the explicitly documented ETF tradability trap. Consequences: (a) §1's thesis mis-describes what S1 buys; (b) engineering item E-1 ("recompute the 7 features and apply the current `combiner_weights` vintage") would compute a signal that is not COMBINER_RIDGE_DAILY_V1; (c) kill gate L6 monitors coefficients of the dead monthly model — the daily ridge coefficients are refit in-code each January and persisted nowhere. And the presence of LL_LEADER_GAP_5D (the highest-IC component in the ledger) is the mechanistic explanation for finding #1: US-hours follower ETFs embed the US-leader move same-day, so the design's story that "market makers hedge beta, not cross-country relative diffusion" is wrong for its largest component.

**3. Selection bias is acknowledged but then argued around.** Deflated Sharpe −0.104 after 59 burned trials is the ledger's own verdict: not significant post-deflation. Components were chosen 2026-06 on the full sample, so the 2021–26 subperiod (t=4.3) cited as mitigation is inside the selection window — nothing is out-of-sample. "Independently reproduced by two separate measurement passes" is arithmetic replication (same scores, same returns, two scripts), not independent evidence. Subperiod decay is monotone (18.9→11.1→7.1→7.0 bp/day), which supports continued erosion, not a stable 0.57× haircut; the honest Mode B launch-configuration number is 2016+ h=5 skip-1: **1.66 bp/day, t=2.0, ≈ +4.2%/yr gross index — ≈ +0.5%/yr net at a 5 bp blend**, before ETF conversion.

**4. The verification gates cannot resolve the question they're assigned.** Daily ICs are autocorrelated via overlapping 21d feature windows (plain t 16.8 vs NW-t 10.7 → variance inflation ≈2.5); the 126d IC se is ≈0.027, not the design's 0.017. Under pure overfit the P-go gate passes ~29%; under the correct capture-shrunk truth (~0.015–0.02 on ETF returns — the design wrongly used the index-decay 0.03) power is ~50%. A coin flip both ways. L5's quarterly capture re-measurement (<0.40 threshold) has se ≈6 bp/day on a ~2–3 bp mean — unmeasurable at that cadence. The gates also score full-ranking IC while the expression trades only the top-5 tail.

**5. Residual PIT and survivorship issues.** ETF_FLOW_21D_Z dated t (shares-outstanding flows publish T+1 morning) cannot be known at the day-t close, so Mode A cannot reproduce the backtested inputs and the backtest plausibly embeds a one-day peek on that feature (skip-1 bounds the damage in index space only). The 31-country universe is today's list backtested to 2005: no Russia (the ERUS-2022 precedent for an EM-tilted top-5 at 20%/name), and EIDO/EPOL/INDA/ASHR didn't exist for large parts of the sample. The −30% expected maxDD understates single-name tail risk. Finally, the live 2026-06-30 cross-section blends 10 bp one-way — the cost level at which the design's own arithmetic goes zero-to-negative — and the banding rescue is an unmeasured assumption (PL-2 never run).

The index-space diffusion family is real (PIT-confirmed components, t 3–5.7). The funding case for S1 as flagship is not: it allocates 60–100% of the book to an edge whose only direct tradable-instrument evidence is t≈0.8 on the spread and ≈0 on IC.

REQUIRED FIXES:
1. Do not fund. A corrected paper/shadow phase may proceed only after fixes 2–6.
2. Re-write the design against the true daily model (6 features from `build_combiner.py` DAILY_FEATURES, incl. LL_LEADER_GAP_5D); re-spec E-1 and L6 accordingly; persist daily ridge coefficients per vintage.
3. Run a component-level ETF-tradability decomposition: measure per-component ETF-vs-index capture, and test a combiner variant excluding (or lagging) LL_LEADER_GAP_5D before claiming any residual ETF alpha.
4. Report the capture ratio and ETF IC with standard errors everywhere; replace the ×0.60 point estimate with the CI; re-derive expected net active as a distribution — if the central case doesn't clear costs at the realized blend, say so.
5. Re-size the verification: ≥252 td (ideally 2 yrs) shadow measurement with autocorrelation-corrected se (≈0.027 per 126d), gates scored on the traded top-5 expression, not full-ranking IC; drop the unmeasurable quarterly L5 gate for a cumulative one.
6. Verify ETF_FLOW_21D_Z availability timing (flows-at-t knowable at close t?); if not, lag it one day in both backtest and production.
7. Run PL-2 (banded construction backtest) and a no-Russia-class survivorship stress note before any capital ask; cap the sleeve at a minority share of the book even post-gates.

## Execution skeptic

VERDICT: MAJOR

CRITIQUE (ex-market-maker view)

The commissions are fine. Everything else about the cost case is not.

**(a) The blended-cost target is contradicted by the signal's own measured habitat — this is the core kill-shot.** I queried `family_ranks_daily` (family='combiner', rank≤5, full 2005–2026 history, 27,905 slot-days, read-only): 23.0% of all top-5 slots are Tier C (20 bp design cost), 22.7% Tier B, only 10.4% A-mega. Slot-weighted blended one-way cost: **9.4 bp on the design's own tier inputs (8.1 bp on mine_exec's realistic all-in column); 9.6 bp restricted to 2021+**. The 2026-06-30 cross-section at 10 bp is not "unusually EM" as §2.8 claims — it is the median state. The design's own §3 table says net active at a 10 bp blend is **−3.0% to +0.3%/yr**. So the construction that generated every measured performance number (unbanded top-5 h=5) is net ≈ zero-to-negative at its measured cost habitat, and the L4 cost trigger (>7 bp for 2 months) would fire almost immediately, auto-switching to S1-L — whose alpha is admitted unmeasured. The flagship as specified is a strategy whose measured-alpha variant and achievable-cost variant are two different, never-jointly-measured portfolios. At 9.4 bp and 0.148/day turnover the cost line is ~7.0%/yr of sleeve against a realistic gross of 4.4–7.7%. Even the assumed banded turnover (0.09–0.10/day, unmeasured) gives ~4.4–4.7%/yr of cost — consuming the entire conservative gross.

**(b) Turnover/commission math.** 0.148/day one-way on $70k = ~$20.7k two-sided daily notional, ~$5.2M/yr (52× NAV), ~3–6 orders/day in $2.8–5k tranche clips, ~800–1,400 orders/yr. Commissions alone ≈ $600–1,000/yr (0.6–1.0% of NAV; EIDO-class per-share fees run ~6 bp at any clip size) — already inside the tier inputs, but note it roughly equals the entire central net-active claim of +1–2%/yr.

**(c) Timing is worse than designed.** Verified live: `combiner_scores_daily` max date is **2026-06-30 on 2026-07-02** — T+2, exactly as mine_livedb warned. Mode B is described as "T+1 close on yesterday's scores," but the pipeline's observed cadence delivers T+2; the skip-1 haircut (12.9%→8.1%/yr, −37% for one day of delay on a fast-decaying signal) says skip-2 takes another material, unmeasured bite. Worse, the §2.6.1 staleness gate ("older than last business day → no trade") would have been CLOSED today — under observed cadence the fail-closed gate either blocks trading chronically or gets quietly relaxed. Mode A is scoped as "a new intraday scoring script, read-only against both DBs" — but at 15:30 ET the DBs do not contain day-t foreign closes; ASADO ingests index levels overnight. E-1 actually requires a new intraday market-data pipeline (live foreign index/TR-index levels, matching the proprietary T2 feature definitions) plus a hard daily 15:30–15:50 human-in-the-loop window. Using ETF prices as proxies is circular (they embed the US-hours pricing the thesis says isn't there). E-1 is understated by an order of magnitude.

**(d/g) The cost model is unconditional; the signal is conditional.** 6c-11 spreads are calm-market 30-day medians (July 2026). The signal buys laggards precisely after neighbor divergence — risk-off, EM, dollar-spike days — when TUR/EPHE/EZA/ECH quoted spreads go 1.5–3× median and closing auctions thin out. The 2/5 bp slippage allowances don't cover this. And the TCA design is self-blinding: measuring MOC/LOC fills "vs official close" when your 340–570-share EPHE order is a double-digit percentage of a thin closing auction means your own impact IS the benchmark — measured slippage ≈ 0 by construction while real cost bleeds. LOC bands ±25/50 bp guarantee unfilled remainders on exactly the stress days, forcing next-day chases the backtest never modeled.

**(e) Ops.** 252 hard 15-minute execution windows/yr, 3–6 auction orders/day, dual-mode paper books, weekly/monthly/quarterly monitoring stack, PL-1/PL-2/NT-1/NT-2 pre-work — for a central expectation of $1–2k/yr active on $100k, with realistic central ≈ $0 after (a). The ratio of operational surface to expected edge is the worst I've seen at this scale.

**(f) IBKR mechanics — mostly fine.** Pro/Tiered correct; MOC/LOC at 15:45 clears all venue cutoffs; PDT exempt; cash-yield modeling correct. Two nits: fractional orders are internalized and cannot route to closing auctions (whole shares only for MOC/LOC), and IBKR requires activating "Close" TIF order types per exchange — trivial.

Why not FATAL: no live dollars are at risk, the gates are honestly pre-registered, capacity/impact genuinely is a non-issue, and a Tier-A-only, slower-tranche expression of a real diffusion effect may survive. But S1-F as the primary configuration is dead on arrival by its own L4 criterion, and the paper phase as designed would measure the wrong (self-benchmarked) costs.

REQUIRED FIXES:
1. Invert the variant hierarchy: S1-L (Tier A/A-mega only) becomes the primary; run NT-1 and PL-2 on the restricted universe BEFORE the design is accepted, not as pre-launch blockers of S1-F. S1-F is contingent on S1-L showing alpha, not vice versa.
2. Re-run the §3 economics table at the measured 9.4 bp slot-weighted blend (and a 2021+ 9.6 bp case), not the aspirational 5 bp; publish the tier-composition query as a standing monitor.
3. Rescope E-1 as an intraday data-acquisition project (live foreign index levels consistent with T2 feature definitions, source named, failure modes specified) or drop Mode A from the economics and re-baseline on measured skip-2, not skip-1; measure the skip-2 haircut on the index grid now (one query, mine_math machinery).
4. Reconcile the staleness gate with observed T+2 cadence: either fix the pipeline to T+1 (and prove 20 consecutive days) or re-spec the gate/backtest to the true lag.
5. Replace close-benchmarked TCA for Tier B/C with an uncontaminated benchmark (15:45 mid, or VWAP 15:30–16:00) and log auction size vs order size per fill.
6. Add a stress-conditional cost model: tier costs ×2 when VIX>25 or the ticker's own 5-day realized spread >1.5× its 6c-11 median; re-run net economics under it — if net active goes negative, the entry rule must skip stress-day entries, and that variant must be backtested (PL-2 scope).
7. Cap Tier C participation structurally (e.g., max 1 of 5 slots) or price entries with an explicit cost-adjusted rank (rank penalty = expected round-trip/expected residence) instead of hysteresis bands alone; measure in PL-2.
8. Publish expected orders/day and an explicit missed-window protocol (what happens when the human can't stage orders at 15:45 — hold vs next-close catch-up), since a 5-day tranche machine desynchronizes from the backtest after every skipped day.

---

# S2-slow-graph-book

## Statistical skeptic

VERDICT: FATAL

The design is the most honest document in this program — pre-registration asks, frozen weights, kill criteria, no forward-return variables (verified: all inputs are trailing/PIT surfaces), correct one-sided fundamental-law math with no double haircut, trivial capacity. None of that saves it, because its core empirical premise fails a check the designer never ran: **recency**.

**(e) Subperiod fragility — the killer.** The composite puts 65% of weight on C1+C2+C3 (return diffusion) and justifies IC 0.02–0.03 at the 21d horizon from full-sample harness stats ("positive both halves", posyrs 74–89%). I recomputed daily Spearman ICs of all three components against forward 21-business-day total returns (TRI levels, PIT-safe convention identical to mine_math) directly from the live loop DB:

- SIM_NBR_RET_GAP_63D: full +0.021, 2016+ +0.009, 2021+ **−0.025**, 2024+ **−0.070** (by-year 2024/25/26: −0.052/−0.052/−0.158)
- GRAPHP_BANK_NBR_RET_GAP_21D: full +0.045, 2021+ +0.015, 2024+ **−0.062** (2024/25/26: −0.049/−0.056/−0.108)
- GRAPHP_TWOHOP_TRADE_GAP_21D: full +0.024, 2016+ +0.006, 2024+ **−0.049** (2024/25/26: −0.044/−0.051/−0.057)

The harness's OWN artifact (`harness_ic_series`, 5d horizon) says the same thing: H_043 2025 −0.049, 2026 −0.125; H_041 2025 −0.052, 2026 −0.110; H_035 2025 −0.043, 2026 −0.060. The "halves +/+" summary the design leans on conceals a ~2.5-year wrong-way run ending at the evaluation date. Corroboration: the family's only forward track record — two live paper theses — is 0-for-2 (Indonesia −5.7%, Hong Kong −2.2%), which the design waves off as "sample of two" while the component-level data shows it is not a sample of two, it is the tail of 600+ trading days of negative IC. Decisive self-contradiction: the design's own K1 kill rule (252bd composite IC ≤ 0 at two consecutive month-ends) **would fire at launch** if applied retrospectively — rolling 252bd ICs of the 65%-weight block have been ≤ 0 since roughly early 2024. Funding a sleeve whose pre-registered kill condition is currently true is not a fixable drafting issue.

**(g) Expected returns don't follow from cited evidence.** Gross 1.3–2.2%/yr assumes the full-sample IC persists; the last 30 independent 21d windows average IC ≈ −0.05 to −0.07. The margin was thin even on the design's own numbers: C2/C3 21d LS breakevens are 9.8/9.6bp against a 7.5bp blended cost — a ~2bp cushion described as "comfortable." Layer the unmeasured capture (only 0.36@h=1 and 0.60@h=5 are measured, on 13 months of ETF closes; the 0.75–0.85 is extrapolation — a power-law fit of the two measured points gives ~0.74, making 0.85 unsupported) and the realistic central case is ≤ 0 net even before the regime problem.

**(b, c) Selection effects, honestly charged but real.** The five components were picked post hoc from 59 burned trials (~4 independent mechanisms); C5's direction was flipped after seeing the data (2013+ only, 159 obs); C4 carries a DEAD verdict and enters at 15% weight on the strength of the best cell of a 3-cell hold grid scanned across ~40 signals — classic grid mining, mitigated only by the promised R1 registration. The composite itself has **never been backtested**; Section 3 is arithmetic, not measurement, and R2 is deferred to pre-live. Every deflated Sharpe in the ledger is negative — the harness's own multiple-testing accounting already says nothing here survives its reference cost.

**(a) PIT integrity — one genuine spec defect.** The Section 8 SQL (`date <= :t`) would select the 2026-06-30 consensus stamp at t=2026-07-02, while the appendix run and Section 2.6 use the forward-stamped 2026-07-31 row (33 countries, confirmed present today). Spec and reference implementation disagree by a full month of C5a vintage, and the "survey published before the stamp" claim is asserted, not verified against collector ingest dates. Not lookahead per se, but an unresolved alignment between what was harness-tested and what would be traded.

**(d, f, h)** Long-only degradation is handled correctly (top-k order-statistic construction, no double haircut). Universe drift is modest (index-return backtests 2001+ vs ETFs launched 2009–2015; tracking/ER acknowledged). Capacity/crowding is genuinely fine at $35k.

Bottom line: a disciplined, well-governed design built on a mechanism that stopped working roughly two and a half years before the funding request, with an expected-return band computed as if it hadn't. Do not fund. The case reopens only if the evidence changes, not the prose.

REQUIRED FIXES:
1. Registered recency-stratified re-measure of C1/C2/C3 at the 21d horizon with explicit 2021+ and 2024+ subwindow gates; funding requires the trailing-252bd IC of the 65%-weight block to be > 0 — i.e., the design's own K1 must not be true at go-live.
2. Diagnose the 2024–26 sign flip before re-submission (regime shift, crowding, or feature-construction change in the nightly rebuilds) — a mechanism story for why it returns, not just a wait-and-see.
3. Run R2 (SLOWBOOK_COMPOSITE_V1 through harness v2.1, hold grid + breakeven + subperiod table) BEFORE any funding decision, and make the funding conditional on its 2023+ subwindow, not the full-sample row.
4. Resolve the consensus_signals vintage contradiction: align Section 8 SQL, slowbook_compute.py, and Section 2.6 on one stamped-vintage rule, and verify the forward-stamp availability claim against collector ingest dates.
5. Replace the extrapolated 0.75–0.85 ETF capture with a measured h=21 capture on the available 13 months of ETF closes (widen bands accordingly); re-state net expectations at capture 0.60 as the floor case.
6. Re-state the cost cushion honestly: C2/C3 21d breakevens (9.8/9.6bp LS) vs 7.5bp blended cost is a ~2bp margin, not "comfortable"; show the long-only-equivalent breakeven for the composite from the R2 run.

## Execution skeptic

VERDICT: MAJOR

The cost architecture is fundamentally sound — this is the rare design that took the cost law seriously. 21d holds amortize even the 20bp tier to ~1bp/day, breakevens (15.8–18.3bp at 21d) sit above realistic all-in costs, and turnover of 3.5–5x/yr is genuinely retail-executable. It is not FATAL. But five execution defects, each independently capable of eating 20–50% of a net edge that is only +0.4% to +1.4%/yr to begin with, must be fixed before even paper trading.

**(a) Costs: the commission table was computed at the wrong clip size.** mine_exec's per-ticker commission column assumes $7,500 clips; the strategy trades $2,187 slots. Per-share fees hold constant in bps, but minimums bite: any fractional order carries IBKR's ~$1.00 minimum = 4.6bp on a $2,187 clip (vs 0.5bp assumed for SPY/QQQ-class), and the $0.35 tiered minimum alone is 1.6bp. Realistic commission is 1.6–5.9bp/side, not 0.5–2.5bp. Blended one-way cost moves from the claimed 7–8bp to ~9–10.5bp. Still under every component breakeven — the thesis survives — but annual cost drifts to ~0.8–1.1%/yr, compressing the central net estimate from +0.8% toward +0.3–0.5%. On a $35k sleeve that is ~$100–175/yr of expected profit. Say it plainly in the doc.

**(b) Turnover math** is honest as stated (~112–160 orders/yr, $60–160/yr commission = 17–46bp of sleeve), but veto-forced liquidations (V2/V3 hard sells), group-cap substitutions, and flow-block skips all add churn on top of the 2–3-names-per-cycle estimate. Expect realized turnover at or above the top of the 3.5–5x band. K3 catches this, but the base-case P&L should use the top of the band.

**(c) Timing: one real flaw.** Signal-to-trade latency is fine — 21–63d formation signals lose nothing to T+2 graph staleness, and the 07:30 pipeline → 09:30 gate → 10:15 execution sequence works. The flaw is the fallback: unfilled tier-B/C midpoint orders convert to marketable at 15:30 ET. Europe closes ~11:30 ET; per mine_exec's own timing table, European spreads widen materially after the home close. So EWN (15bp), EWP (12bp), EWD (10bp), EDEN (26bp) unfilled midpoints get force-crossed in their single worst window of the US day. The patient-then-panic pattern also leaks: a midpoint order resting for hours in a 19-share-deep name signals a motivated buyer before crossing.

**(d) Pipeline: an internal contradiction the doc papers over.** The Section 8 reference SQL uses `date <= :t`, but the appendix's live run consumed the `consensus_signals` row stamped 2026-07-31 on 2026-07-02 — a row the spec query would exclude. Either the implementation and spec disagree (which one traded?) or the stamp convention silently bypasses the `date <= t` guard. Not lookahead (the survey pre-dates the stamp), but exactly the kind of spec/code divergence that "silent orientation bug" monitoring exists for — and it's already present at v1.1. Separately, `live_signals` showing all 16 hypotheses INSUFFICIENT_COVERAGE against a green scorecard means the freshness gate's "governance GREEN" input is currently uninformative; the gate would pass on a partially broken pipeline today.

**(e) Operational load** is acceptable: ~5–10 orders per rebalance day, 24 days/yr, ~30 min each. But the Asia futures fair-value check (NKY, KOSPI200, FTSE A50, MSCI Taiwan) requires live futures market-data subscriptions (OSE/SGX/HKEX) that a US retail IBKR account does not have by default — an unbudgeted dependency for a step that's a pre-trade blocker on B/C Asia names. And the 1st/11th-business-day schedule assumes human availability with only a postpone-5-then-freeze safety net; a single missed morning cascades into a stale tranche.

**(f) IBKR mechanics** mostly check out (Pro Tiered, fractional for high-priced names, PDT-exempt, margin-type account). Two gaps: fractional orders execute internally and cannot be midpoint-pegged or SmartRouted (fine for SPY/QQQ, but don't extend fractionals below mega-tier); and the midpoint-fill assumption ("recovers 25–50% of spread") is untested for odd-lot orders in tier-C names where quoted depth is a few hundred shares and midpoint liquidity may simply never arrive — fill rates, not spread math, decide realized tier-C cost.

**(g) Stress slippage is the strategy's structural weak point.** The hard vetoes force sells of downgraded/CDS-inverted names at the first rebalance after the event — mechanically selling TUR/EZA-class names into 2–3x-widened spreads, at exactly the moment midpoint liquidity vanishes. The current book is EM-heavy (HK, ChinaA, Brazil, Turkey, Malaysia, India); a global risk-off widens the entire held tier simultaneously, and the 15:30 marketable conversion pays full stressed spreads across all of them on the same day. The 20bp tier-C design input is a calm-market number; budget 40–60bp for veto-forced exits.

None of this kills a 21d-hold expression whose breakevens exceed costs. It does mean the realistic net band is +0.1% to +1.0%, not +0.4% to +1.4%.

REQUIRED FIXES:
1. Recompute the per-ticker cost table at actual clip sizes ($2,187 single, $4,375 double), including the $1 fractional minimum and $0.35 tiered minimum; restate blended one-way cost (~9–10.5bp) and the net-active band in Section 3.
2. Change the fallback conversion for European tier-B/C names (EWN, EWP, EWD, EDEN) from 15:30 to 11:15 ET, before the home-market close; keep 15:30 only for Asia/Americas names.
3. Resolve the consensus_signals stamp contradiction: rewrite the Section 8 SQL to key on collector ingest date (or map the forward stamp to ingest date), and make slowbook_compute.py and the spec provably identical on this path.
4. Make the freshness gate independent of the governance scorecard until the live_signals INSUFFICIENT_COVERAGE mismatch is reconciled: gate directly on per-table max(date) checks plus the family_ranks_daily rank-correlation test.
5. Add a stress execution rule for veto-forced sells: cap acceptable one-way shortfall (e.g., 30bp vs arrival mid) and allow splitting the exit across 2–3 sessions rather than force-crossing a 50bp spread on day one; log these separately in K3.
6. Either budget and subscribe to the required Asia index-futures market data on IBKR, or replace the futures fair-value check with a free proxy (e.g., ETF move vs prior close + S&P futures beta) and document the degraded filter explicitly.
7. During the paper quarter, measure tier-C midpoint fill rates and realized spread capture on odd lots; pre-register a rule (e.g., fill rate <50% or capture <25% for a quarter → tier-C entries switch to next-morning marketable limits and the cost model is restated).
8. Prohibit fractional orders below the mega tier (they bypass SmartRouting/midpoint); enforce whole-share odd lots for everything except SPY/QQQ/IWM/EWY/EWT/EWJ.

---

# S3-event-overlay

## Statistical skeptic

VERDICT: MAJOR

CRITIQUE

I re-derived every headline number from the raw per-event CARs in `Data/loop/event_studies/*/summary.xlsx` (read-only, 2026-07-02). The reported means/t-stats reproduce exactly. The problem is not the arithmetic — it is that the inference treats overlapping, duplicated, crisis-clustered events as independent, and the design's three Tier-1/Tier-2 pillars all fail once that is corrected.

1. The "firmest" claim — CDS inversion −4.52%@63d, t −2.44, "the only CI excluding zero" — is a GFC artifact with inflated n. The 41 "events" include ChinaA+ChinaH counted twice on the same day four times (8 rows = 4 sovereigns), and 20 of 41 events fall in 2007–09, including 10 events inside one 90-day window (Oct 2008: Korea 10-14, Philippines 10-22, Turkey 10-23, ChinaA/H+Thailand 10-28, Malaysia 10-30…), whose 63d CARs are the same GFC crash measured repeatedly. My recomputations: dedup sovereigns t −2.25; collapsing events into time-clusters ≥90d apart, t −1.77 (22 clusters); ex-2007–09, mean −2.66%, t −1.06 (n 21); drop Turkey, t −1.38. The bootstrap CI "excluding zero" is an iid event bootstrap over non-iid events — it understates variance mechanically. In the normal-year regime where the design claims +36bp/binding, the effect is statistically indistinguishable from zero.

2. EM downgrade 63d fails harder. As reported t −1.45 (CI already includes 0, disclosed); dedup t −1.30; cluster-robust t −0.82 (14 clusters). Turkey is 14/54 events with overlapping windows (2018-03/05/08 during one lira crisis). The one cell that survives clustering is the +5d CAR (cluster-mean t −2.30, dedup t −1.92) — the drift kernel is real-ish for ~a week, not for 63 trading days. Yet V-DG locks the name out for 13 weeks, which is where the K-2 opportunity-cost risk lives (the design's own counterfactual: the combiner ranked Turkey #2, Brazil #5 while inside/near inversion windows).

3. Upgrade block: the most cut-stable result (dedup-invariant, worst leave-one-sovereign-out t −1.77), but cluster-robust t −1.65, and neither subperiod is significant alone (pre-2024 t −1.81 n 28; 2024–25 t −1.22 n 17). This t≈−1.7 evidence is used to block adds against South Africa's #3 rank on the bank-gap family (NW-t 4.5) — a weaker instrument overriding a validated one.

4. Multiple testing. The event_studies directory contains 14 runs (~10 distinct specs) × 3 horizons plus EM/DM and high/low-VIX splits of a parent study whose own 63d t was −1.45 (ns). The three headline cells are p=.019/.034/.049 — the best of 30+ cells, exactly the ~1.5 false positives expected at α=.05. The high-VIX "damage front-loads" refinement (−1.31%@5d, p=.0479, n 23, 63d ns) is the best of two post-hoc splits of the third-best study.

5. The value arithmetic double-counts and mis-benchmarks. (a) CARs are vs universe, but vetoed weight goes to cash, so per-binding value = CAR + (cash − universe) ≈ CAR minus ~1%/quarter equity premium in normal years: V-DG 23bp→~15bp, V-CI 36bp→~28bp; gross ~65bp→~50bp, net ~20–30bp — before conceding that the underlying normal-year CARs are ns. (b) The crisis claim (+150–400bp in a 2008-analog) is circular: the −4.5% estimate IS 2008; the same 11 onsets both establish the CAR and star in the crisis scenario. Directionally holding cash in a crisis is fine, but the number is the training data quoted back as a forecast.

6. PIT/data quality: mostly clean and honestly handled — next_month anchoring is conservative, pre-window runups are small (no leak signature), the Spain −1013bp artifact and the 45-vs-41 census mismatch are disclosed. Remaining live risk: 98 of 147 inversion runs last exactly one day, and France 2026-06-22 (−54bp between +19bp sessions, a 73bp one-day jump) passes the 300bp sanity gate — a plausible false veto of a DM name for 63 days, on an all-country rule whose limits-to-arbitrage mechanism story (§1.2) is EM-specific.

What saves this from FATAL: $0 capital, pre-registered mechanical kills (K-1..K-5), disclosed CIs, ~2 bindings/yr, ~−5bp/yr running cost, and a genuinely robust short-horizon downgrade kernel. As insurance-with-uncertain-premium it is cheap. But its Tier-1 rules currently force exits from validated-signal longs on evidence that fails cluster-robust inference at every 63d horizon, and its expected-value section claims normal-year alpha its own data cannot support.

REQUIRED FIXES:
1. Re-run all three studies with sovereign dedup (ChinaA/H, U.S. triplet = one event) and cluster/block-robust inference (calendar-time or block bootstrap); any rule whose 63d effect fails |t|≥2 under that inference demotes from binding veto to advisory. On today's data that demotes V-CI-63d and V-DG-63d.
2. Restructure V-DG around the cell that survives clustering: short exclusion window (~5–21td post-anchor), not 63td; register the 63d window as a trial, not a rule.
3. Restate §3.3/§4 with the cash-vs-universe benchmark correction and normal-year expectation of ≈0 (insurance framing only); strip the circular 2008-analog bp claim or label it "in-sample worst case."
4. Resolve precedence: H-UG (t≈−1.7) may not override a validated NW-t≥4 rank without a registered head-to-head trial; until then downgrade H-UG to a sizing haircut, not an add-block.
5. Tighten V-CI onset admission: require 2-day persistence or independent 1Y/5Y level confirmation for single-day flips (France-type prints), and log the E-1 persistence re-measure before the next binding.
6. Charge the event-study family for multiple testing in the ledger (≥30 cells) and state the family-wise-adjusted significance honestly in the design doc.

## Execution skeptic

VERDICT: MINOR

CRITIQUE

I came to kill this on execution and mostly couldn't. The overlay generates almost no order flow — that is its structural defense against everything in my toolkit. But the design has real spec gaps at exactly the moments it exists for, plus one policy choice whose cost is unbounded. Findings, per the checklist, with claims re-verified read-only against the loop DB on 2026-07-02:

(a) Costs vs breakeven. Fine — and I'll say so. Tier 1 produces ~2–4 forced round-trips/yr at $5–12k clips. Even doubling every cost input, the arithmetic holds. The one understatement: the veto's historical target mix is tier-C-heavy. Downgrade counts by country (measured): Turkey 16, South Africa 10, Chile 7, Mexico 7, Brazil 7 — i.e., TUR (17bp), EZA (27bp), ECH (16bp) dominate, and 6 of the 18 CDS-slope countries (Chile, Indonesia, Philippines, Thailand, Turkey, South Africa) are B/C tickers. On the actual downgrade/inversion day these names trade 2–4x their 6c-11 median: realistic stress exit is 30–80bp one-way, not the calm-market "5–20bp by tier" the design costed. The −2 to −6bp/yr running-cost line is ~2–3x light in an EM-stress year. Still ~4:1 favorable vs +23–36bp avoided per binding — a margin note, not a kill.

(b) Turnover math. <10 overlay-driven orders/yr, ~$1–2 commission each ≈ 0.2bp/yr on $100k. Tier 2/3 rules are zero-order by construction — genuinely free. Trivial.

(c) Timing feasibility. Verified: sovereign_signals max date 2026-07-02 (same-day), sov_rating_changes 2026-07-01, etf_flow_signals 2026-07-01, market_implied_daily 2026-07-02, eco_surprise 2026-06-01 (monthly by design), price_state_daily 2026-06-30 (T+2, advisory-only — consistent with the stated tolerance). The 08:00 ET recompute → same-day close execution chain works and honors the study's next_day anchor. Gap: if the 07:30 job fails and the 11:30 launchd safety net runs instead, the 08:00 recompute has already fired against stale data and entered fail-safe; no re-run is specified, so a recoverable morning becomes a lost day.

(d) Pipeline reliability. My staleness attack fails empirically: SOV_CDS_SLOPE_BP delivered on 263 of 263 business days over the trailing 12 months; 18 slope countries confirmed. However, the chain is Bloomberg-Terminal-in-Parallels + launchd, and the design's fail-safe on a red scorecard is "no new adds book-wide." That blast radius is the single worst thing in this document: a layer worth +30–45bp/yr claims authority to freeze the entire $100k alpha engine's adds whenever any warehouse component goes red. No scorecard GREEN-rate is measured or cited. If red-rate is even 5% of days, the expected opportunity-cost tax on the host sleeves plausibly exceeds the overlay's whole annual value.

(e) Operational load. Order count and monitoring are fine for one human + AI. The "one ~200-line script" is a 3–5x underestimate: append-only state versioning, NYSE trading-day arithmetic, evidence bundles with attached quotes, counterfactual price logging for every delayed entry, K-1/K-2 statistics, a paper ledger marking every Tier-1/X-BASIS/D3 event at +5/+21/+63d, weekly SUSPECT_DATA review, monthly false-positive audits, annual study refresh. That is a real maintenance surface for a layer that binds twice a year and is worth $300–450/yr in normal times. The dormancy-demotion clause (risk 4) is the right escape valve; it needs a date.

(f) IBKR mechanics. MOC by 15:50 is safe across listings (NYSE 15:50 / Nasdaq 15:55 / Arca-Cboe later). PDT exempt at $100k; margin-type account correctly assumed; cash yield modeled including the $10k zero band. Two catches: (1) fractional shares are not eligible for exchange closing-auction orders — "fractional enabled, so share counts are irrelevant" collides with "exits at MOC"; forced exits need whole-share MOC/LOC plus a residual cleanup order. (2) The LOC "±30bp band" never states its reference price; if referenced to prior close on a day the name is down 2%, the order cannot fill. And nowhere does the design say what happens when a forced-exit LOC goes unfilled — in a 2008-analog (11 onsets, thin tier-C auctions) the veto silently becomes a hold at the exact moment the strategy justifies its existence.

(g) Slippage under stress. The high-VIX acceleration deliberately sells into stressed closes. Worst case (tier-C EM, high-VIX): ~50–100bp one-way against an avoided −131bp@5d point estimate with a wide CI — roughly 2:1, not 10:1. Acceptable, but each binding should log realized exit cost vs the avoided-CAR estimate so K-1 nets costs, not just returns.

Bottom line: costs, turnover, timing, and capacity are genuinely fine. The failure modes are spec gaps — fixable in a page — not economics.

REQUIRED FIXES:
1. Cap the fail-safe blast radius: red scorecard freezes overlay state changes and adds only in Tier-1-affected names, not book-wide; book-wide freeze only after 2 consecutive red days with owner acknowledgment. Measure and publish the scorecard's trailing-6-month GREEN rate before launch.
2. Add a second recompute at ~12:30 ET on days the 08:00 pass found stale inputs (after the 11:30 safety-net run).
3. Specify the unfilled forced-exit fallback ladder: LOC unfilled/partial at close → next morning midpoint-peg work order → marketable limit by 11:30 ET; log slippage vs the missed close.
4. Define the LOC band reference price (e.g., last trade at 15:45, not prior close).
5. Re-cost Tier-1 exits using stress spreads (2–4x 6c-11 median) for the tier-C-heavy veto target mix (TUR/EZA/ECH/THD/EPHE); restate running cost as ~−5 to −15bp in stress years.
6. Fix fractional/auction mechanics: whole-share MOC/LOC plus residual fractional limit order; document in §9 step 4.
7. Net realized execution costs into K-1's per-binding ledger, and hard-date the dormancy demotion review (12 months post-launch).

---

# S4-microstructure

## Statistical skeptic

VERDICT: FATAL

CRITIQUE

I replicated the pilot pipeline exactly (read-only; code at `/private/tmp/claude-501/-Users-arjundivecha-Dropbox-AAA-Backup-A-Working-ASADO/087bd20c-1f7d-42e8-9ea0-cad499732b04/scratchpad/alpha_book/s4_skeptic_check.py`, results `s4_skeptic_check.json`, plus `s4_skeptic_ic.py`, `s4_skeptic_sign.py`). My replication matches the designer's headline to the decimal (h=1: 11.79 bp/d, t=2.31; h=2: 7.67, t=2.34), so the following are differences of substance, not of pipeline.

1. The headline dies under the design's own rule. §3.1 rule 6 suspends EWY (Korea) and ASHR (ChinaA) as of 2026-07-01 because their index↔ETF mappings are broken (+55.8%/−46.1% drift — I confirm both numbers). But every §4 evidence number was computed WITH those names, and the pilot was never re-run gated. Gated: h=2 (the funded config) falls from 7.67 bp/d (t=2.34, net +4.0 @5bp) to **3.42 bp/d, t=1.37, net −0.13 bp/d at the design's own 5bp cost**. h=1 falls to 6.82, t=1.96, net −1.4. The "pilot ceiling +4.0bp/day net" that anchors the entire §5 expected-return arithmetic is an artifact of two names the design itself declares garbage-in.

2. The "alpha" is one broken name. Per-name attribution: Korea alone contributed 1,205 bp of the 1,709 bp total cumulative active (70.5%); Korea+ChinaA = 77.9%. Korea was in the top-5 on 39% of days. Mechanically: garbage residuals from a mis-mapped index made EWY a quasi-permanent holding during Korea's historic 2025–26 rally. That is a lucky structural overweight, not mean-reversion of mispricing.

3. The design cannot pass its own kill table on day one. Measured 13-month cumulative index-minus-ETF drift: Netherlands +25.7%, Vietnam +20.6%, Taiwan +9.5%, U.K. +8.1% — all far beyond 3%-per-90-sessions. §8 says ">2 names beyond the 2 currently suspended → halt sleeve pending mapping audit." The claim that only EWY/ASHR breach is contradicted by the design's own data; either the T2↔ETF mapping is unusable book-wide for this purpose, or the threshold is miscalibrated (note: Netherlands, the #2 positive contributor at +247bp, is also a drift name).

4. The storm overlay is calibrated on the wrong universe. The quoted +24.6 bp/d (t=3.56) came from pilot1's 27-name FOREIGN universe including Tier-C names M1 will never trade. On the actual traded A/B universe, storm days give 10.9 bp (t=1.23) ungated, 11.3 (t=1.61) gated, n=32. A live sizing rule (full-size deployment, top-4 tilt) rests on a subsample statistic that does not exist in the traded universe.

5. The "independent second pass" is unauditable and its headline is universe-inflated. No scan script was saved — only JSONs. By forensic reconstruction: scan's `tierA_bottom5` (10.9, t=3.51) reproduces ONLY on a 22-name universe that includes SPY/QQQ/IWM (synchronized names with no mispricing mechanism, excluded from M1) plus Korea/ChinaA, with no artifact filter. With the artifact filter and the design's traded gated universe, the gap fade is 2.46 bp/d, t=0.99. `scan_clean`'s 8.78/t=3.73 is not reproducible under any construction I tried. The S1 "mechanism-health" IC of −0.043 (t=−3.1) is the all-34 pooled number; on the gated A/B universe the per-day IC is 0.033, t=1.85 — below its own kill threshold's spirit.

6. Event study S3 (+63bp/5d, n=228, "t=3.4") misattributes its t-stats: `events_clean` contains no Tier-A t-stats; the quoted 3.0/3.4 match the full 377-event pool (`d9_events`: 3.05/3.66). 5-day forward windows overlap and events cluster cross-sectionally on common stress dates; no clustered/NW errors anywhere. The event universe includes the broken-mapping names (EWY had 60 days with |1d gap|>3%), and if closes are truly unadjusted (caveat 3), ex-div drops of 1–2% slip under the 3% filter and fire fake "laggard" events. The design does not actually know whether `etf_prices_daily` closes are adjusted — this must be resolved before any gap statistic means anything.

7. Multiple testing finishes the job. ~25 disclosed variants; the best gated, traded-universe, cost-relevant statistic is t≈1.4–2.0 over 145 days (~7 months, one foreign-rally regime). Under any honest deflation the MICRO family's current evidence is zero.

What survives: the PIT return mechanics are clean (shift(-1) correct, no forward-return variables, 120d window excludes t); the long-only treatment (top-5 vs universe EW) is correct and needs no halving; the phase-gate/zero-capital posture is honest; M4 is a sensible zero-turnover execution discipline whose value should simply be audited, not projected; the Levy–Lieberman/Petajisto mechanism remains plausible in principle. But the empirical case presented for funding M1/M3 is invalid as written, and §5's "+3–5%/yr central" does not follow from the gated evidence, which is net-negative.

REQUIRED FIXES:
1. Re-run all pilot/scan evidence with the benchmark-quality gate applied; publish gated numbers as the headline (current gated result: net −0.13 bp/d at 5bp — i.e., no funding case).
2. Replace the T2-index anchor with each ETF's actual benchmark or NAV/iNAV; the drift table proves T2 indices are not the ETFs' benchmarks for ≥4–6 names. Recalibrate the 3%/90-session gate after removing any dividend-basis component.
3. Determine definitively whether `etf_prices_daily` closes are dividend-adjusted; redo gap/event statistics accordingly with an explicit ex-div exclusion.
4. Save and version the second-pass scan code; reproduce or retract `scan_clean` and the S1/S2/S3 numbers; recompute S3 with clustering-robust errors on the actual Tier-A traded subset.
5. Recompute the storm overlay on the traded A/B universe; at t≈1.2–1.6 it must be dropped from the rules, not sized at 25%.
6. Run G1 (2002–2026, adjusted closes) with era-appropriate costs, not 2026 tier costs, and with correct benchmark mappings; register with the full ~25-variant burn. Only a gated, deflated, full-history pass constitutes a new funding case.

## Execution skeptic

VERDICT: MAJOR

**Where the design is right (credit where due).** MOC execution is the correct call: an MOC fill IS the official close, so for the Tier-A majority the pilot's close-to-close arithmetic pays no spread at all versus the backtest benchmark — the 5bp tier assumption is, on the spread component, conservative. Capacity at $1.5k clips is genuinely a non-issue. The zero-capital gauntlet, benchmark-quality gate, and the refusal to trade the leader-follow trap are better hygiene than 90% of retail designs. The costs are NOT fine, however, for three reasons the design's own numbers don't survive.

**1. Clip-size/commission mismatch quietly eats most of the net (the biggest concrete hole).** The exec miner's tier table (3/5/10bp) embeds ~1–1.5bp commission computed at **$7.5k clips**. M1 trades **$1.5k clips**, where the IBKR Pro Tiered $0.35 minimum plus auction/exchange/clearing fees run $0.40–0.85/order ≈ **2.5–6bp per side** (EIDO at $11.45/sh is the 6bp case). Turnover math: 0.367 one-way/day × $15k = $5.5k bought + $5.5k sold daily ≈ 7.3 orders/day ≈ **~1,850 orders/yr ≈ $800–1,000/yr of commission on the M1 sleeve alone** — versus a stated central expectation of $450–750/yr. Roughly $500–600/yr of that is *unmodeled* relative to the 5bp assumption. Run the design's own sensitivity: at a true blended ~8bp the pilot nets +1.8bp/day; after the design's own 50% haircut that is ~$340/yr, before market-data fees. Five names × $1.5k is the wrong shape; commission bps fall by half at $3k clips.

**2. The 3:40→close gap is a signed cost, not "noise," and it is unmodeled anywhere in the gauntlet.** The pilot forms the signal AT the official close and trades AT that same close — impossible live. Live, you rank on 3:40pm prices and get filled at 4:00pm. For a **reversal** signal this is systematically adverse: names most oversold at 3:40 tend to begin reverting into the close (that's your own thesis), so your MOC fill is conditionally *worse* than the decision price — you buy after part of the bounce. Mine_math says 61% of h=1 alpha dies in one day; the decay curve at 20-minute horizon is unknown but the sign is against you, it is largest exactly on the storm days where the overlay concentrates capital, and the entire net margin is ~4bp/day at t=2.3. G1 (daily closes) structurally cannot measure this; G3's 60 days cannot either (see #4). This can plausibly zero the sleeve on its own.

**3. The live signal is not the backtested signal.** The regression is fit on `t2_levels_daily` USD total-return indices — a warehouse object refreshed **monthly** — but the live 3:40pm regressor is "IBKR index quotes or MSCI iNAV feeds": price-only, local-currency (needs a same-day FX leg), different index families. The design's own second pass proved T2-vs-ETF-benchmark divergence can hit ±50% cumulative (EWY/ASHR); feeding a third index object into betas fitted on T2 injects a bias into every residual. Also unstated: between monthly refreshes the sleeve must maintain its **own** daily home-close archive to keep the 120d window current, then reconcile against the warehouse — plumbing that doesn't exist and isn't in the gauntlet. Compounding: the benchmark gate has already suspended EWY and ASHR — two of the three cheapest, most liquid names — pushing the traded universe toward the expensive tail.

**4. G3 has no statistical power on alpha.** Daily active SE on a 5-name portfolio is ~40–60bp; over 60 days the mean's SE is ~6–8bp/day against a 4bp/day target (t≈0.6). The paper gate "net active < 0 → fail" is a coin flip both ways. G3 *can* measure realized costs and fill rates to useful precision (20+ round-trips) — reframe it as a cost/ops gate, not an alpha gate.

**5. Smaller but real:** (i) LOC 15bp bands on Tier B will fail to fill precisely on the biggest-signal (storm) days — non-fill handling is unspecified, and non-fills truncate the right tail the P&L depends on; Arca on-close orders can't be cancelled after 3:50, so a bad 3:40 print rides into the auction with no sanity check. (ii) IBKR pays zero on the first $10k of cash and needs paid market-data subscriptions (US bundles + foreign index feeds, ~$200–500/yr) — material against a sleeve expectation of $600–1,400. (iii) US half-days (1pm close, 12:50 cutoff) aren't in the pipeline calendar. (iv) M3's spread "earned" is ~$3/fill on $2.5k against 5-day EM-event tail risk, ~20 fills/yr; the 20-fill adverse-selection guard takes a full year to trigger; "GTC-day limit" is a contradiction. (v) ~1,900 hard-deadline orders/yr in a 6-minute daily window is a single-point-of-failure ops load; the design's own 10% compute-failure tolerance implies chronic under-deployment.

None of this is fatal because the ask is $0 today and the gates exist — but as specified, M1's central expectation after correctly-sized commissions, signal staleness, and data fees is approximately **zero**, and the gauntlet as written would not detect that before go-live.

REQUIRED FIXES:
1. Re-run all M1 economics with clip-size-correct commissions (2.5–6bp/side at $1.5k); restructure to $3k clips × top-3, or one $15k tranche at h=2 top-5, to halve commission bps; publish the blended-cost number per the actual selection distribution (Tier-B overrepresentation in residual tails must be measured, not assumed).
2. Add a signal-staleness test to the gauntlet: acquire intraday (or 3:45pm snapshot) history for the 21 names, or during G3 log decision-price-vs-fill on every order and pre-register a gate: mean adverse drift > 2bp one-way → the h=2 economics recompute must stay net-positive or the sleeve fails.
3. Unify the regressor: either backtest G1 on the SAME live-constructible object (ETF-benchmark index / iNAV-implied home close in USD) or build and validate the sleeve-owned daily home-close archive with monthly warehouse reconciliation before G3 starts. The traded signal must equal the tested signal.
4. Reframe G3 as a cost-and-operations gate (realized one-way cost ≤ 8bp incl. commission over ≥20 round-trips; ≥90% compute success; fill-rate stats on LOC) and drop the powerless 60-day alpha criterion; alpha validation lives in G1 + post-launch kill table only.
5. Specify LOC non-fill handling (remainder to cash, logged as truncation cost) and add a pre-submission sanity band (3:40 price vs trailing 5-min VWAP) since Arca on-close orders are immutable after 3:50.
6. Add the missing line items to §5: market-data subscriptions ($200–500/yr), $10k zero-yield cash floor, US half-day calendar; restate sleeve central expectation net of these.
7. Shrink M3 to an explicitly-labeled learning book with a per-name kill (2 consecutive bad fills) and a 10-fill guard, and correct the order type (DAY limit, re-entered daily, not "GTC-day").

---

# S5-regime-cash

## Statistical skeptic

VERDICT: MAJOR

CRITIQUE

This is the most honest design in the book — it claims zero alpha, prices itself as insurance, reports its own losing years, and pre-registers a payout-failure kill. I verified the plumbing: the Z252 inputs are genuinely point-in-time (rolling 252d trailing windows, `load_market_implied.py` lines 79–84), history exists from 2006-01/2006-03, FX breadth uses an adaptive denominator (26→29 currencies), no forward-return variables anywhere, and the results/verification JSONs match the script. But three substantive problems survive, and one of them guts the headline number.

1. The "primary" lag-1 convention is unachievable for 3 of 4 components. Live process (§2.5): compute at 15:40 ET day t, trade MOC at close t, first affected return is day t+1. VIX TS is live at 15:40 → true lag-1. But HY OAS, MOVE, and FX impvol available at 15:40 on day t are day t−1 values → effective lag-2 relative to the affected return. The backtest (`state.shift(lag)`, lines 128–133) runs uniform lag-1 as "primary" and uniform lag-2 as "conservative"; the achievable strategy is a mixed-lag hybrid that was never run. This matters enormously at the margin: lag-1 net CAGR 8.27% vs EW 7.89% (+0.38%/yr); lag-2 is 7.65% (−0.24%/yr). The entire claimed active return flips sign inside the lag ambiguity. The design's own §2.5 claim that "the primary results already reflect" the lag-1 publication convention is wrong accounting.

2. The positive CAGR gap is arithmetically an artifact of variance drag, i.e., the generic vol-targeting effect. From the verification JSON's annual ledger: ex-2008/2020 the annual gaps sum to −30.1pts over 19 years (mean drag −1.6%/yr, not the quoted median −1.2%); the two payouts sum to +27.8pts. The arithmetic sum of all annual gaps is negative (−2.3pts), yet CAGR gap is positive — the whole geometric edge comes from losing less at high volatility, which is exactly what Moreira–Muir vol-managed scaling delivers mechanically with one input (trailing realized vol). The design never runs the obvious cheap baseline — trailing-vol targeting or a 200dma on the same EW index — so we cannot tell whether the 4-component, Bloomberg-dependent, ops-fragile score (the design's own risk #4) adds anything over a self-contained price rule. For a strategy whose entire justification is "same protection, minimal complexity," this is the single most important missing comparison.

3. Costs are calm-market costs applied to trades that occur, by construction, in stressed tapes. The 5bp flat one-way assumption is fine for the 80% of days at score 0; it is indefensible for de-risk executions that trigger precisely when VIX is backwardated and credit is blowing out. In March 2020, EM country ETFs (EIDO, EPHE, THD, VNM, ECH) had spreads of 50–150bp and NAV discounts of 2–6%; selling MOC into that tape and re-buying stepwise as premiums re-establish haircuts the +19.2pt GFC and +10.0pt COVID payouts — the only two positive entries in the ledger. Additionally the backtest is run on index total returns, not ETF prices, so crisis-time ETF/NAV basis is entirely unmodeled, and it is concentrated exactly where the strategy's value is.

Smaller but real: (i) the payout evidence is N=2, and the components were chosen because they are the literature's most famous 2008/2020 indicators — meta-level in-sample selection the design half-acknowledges; across the five major drawdown windows the dial helped in 2 (GFC, COVID), did nothing in 2022 and 2011 (−0.4pt), and was worse in China 2015–16 (−17.6% vs −15.2%). "MaxDD −8 to −12pts" should be stated as conditional on crash-type with a 2-in-5 historical hit rate. (ii) The backtest violates the design's own §2.1 rule by scoring missing data as calm (`.fillna(False)`) — coverage happens to be near-complete so the effect is small, but the 2006-07→2007-03 start runs on z-scores with far fewer than 252 observations (raw data starts 2006-03), and the 2007 whipsaw (−6.9%, worst premium year) fired partly on immature z's. (iii) VIX3M before Nov-2007 is a CBOE backcast, not a traded print — acceptable but undisclosed. (iv) The dial offers zero protection against overnight gap events (Russia-2022-type delisting, lira gaps in TUR), and the universe's exclusion of Russia flatters the book-level maxDD framing, though not the active comparison. (v) Long-only degradation and combiner-ceiling critiques don't apply — this is a time-series overlay, and the sleeve-interaction cost is honestly handled in risk #5.

None of this is FATAL because the design already promises nothing (0 ± 0.5%/yr) and the hysteresis machine, kill criteria, and governance path are sound. But the headline row of §3 is not the achievable strategy, and the complexity is unjustified against a naive baseline.

REQUIRED FIXES:
1. Re-run the locked spec with the achievable mixed-lag convention (VIX TS lag-1; HY OAS, MOVE, FX breadth lag-2) and make that the primary headline; demote uniform lag-1 to an upper bound.
2. Add a stress-conditional cost model (e.g., 25–50bp one-way on score≥4 days, 5bp otherwise) plus a crisis ETF/NAV-basis haircut sensitivity on the GFC/COVID episodes; report whether the two payouts and the maxDD improvement survive.
3. Run the naive comparators on the same EW index and period — trailing 21d/63d realized-vol targeting and a 200dma rule — and fund the 4-input dial only if it beats them on maxDD-per-unit-premium; otherwise adopt the simpler rule.
4. Restate the insurance claim honestly: mean (not median) ex-crisis drag −1.6%/yr; payout hit rate 2 of 5 major drawdowns, one negative; maxDD improvement conditional on crash-type; N=2 caveat in the executive summary, not just §3.
5. Start the backtest 2007-04 (or mask scores until all z-windows have ≥252 obs) and disclose the pre-Nov-2007 VIX3M backcast; re-report the 2007 premium year under mature z's.

## Execution skeptic

VERDICT: MINOR

I came to kill this on execution and could not. The dial's execution profile is unusually cheap and the design already anticipated most of the traps I'd normally spring (close-auction convention matching the close-to-close backtest, netting with sleeve rebalances, min-trade filter, LOC not MOC in thin names, staleness freeze, manual VIX fallback). I verified the artifacts: results JSON matches every cited number (turnover 2.014×/yr, 7.8 changes/yr, 10.1bp/yr), and the loop DB shows all four inputs fresh (FX_IMPVOL_Z252 and VIX TS through 2026-07-02, HY/MOVE through 07-01 — exactly the designed lag-1) with zero historical >5-day gaps in the VIX TS series. Remaining issues are fixable spec defects, not viability threats.

(a) Costs vs breakeven — fine, and I'll say so plainly. One-way turnover of 2.01×NAV/yr at the miner's tier grid: even assuming a book-pro-rata blend of ~6bp calm, the true objection is that the dial trades ONLY on stress days, when 30-day-median spreads are the wrong number. Assume de-risk legs (~1×NAV/yr) execute at 2-3× calm spreads: dial cost rises from ~$101/yr to maybe $250-350/yr (25-35bp). Against a measured lag-1 active of +38bp/yr and an insurance payout denominated in drawdown POINTS (-12pts maxDD), a 15-25bp/yr cost error cannot kill it. Clips are <0.35% of ADV everywhere except EDEN, where the dial's slice is ~$600 — irrelevant. There is no cost kill here.

(b) Turnover math — ~8 state-change days/yr × 15-20 netted orders ≈ 130-160 orders/yr; IBKR Pro tiered commissions ~$0.50-1.50/order ≈ $100-200/yr ≈ 10-20bp, inside the stated budget. Fine.

(c) Timing — mostly sound, two real defects. First, the 15:40 compute → auction-cutoff window is 10 minutes (NYSE/Arca MOC/LOC entry closes 15:50 ET; Nasdaq 15:55 for QQQ). Computing the score, refreshing live VIX/VIX3M, generating netted target shares across 15-20 positions, and entering orders is feasible only as a scripted basket; done by hand it will miss the cutoff or fat-finger on exactly the panicked days it matters. Second, someone must be present at 15:40 ET every trading day; a missed crash day silently becomes lag-2 execution. The saving grace — and it's a genuine design strength — is that lag-2 was backtested (7.65%/yr, maxDD -47.5%), so the failure mode is bounded and quantified. It should be codified as the explicit fallback, not left implicit.

(d) Pipeline staleness — this is my biggest finding. §2.1's rule "if ANY input is stale >5 days, freeze the dial in its current state" mechanically contradicts §2.4's hard trigger. FX_IMPVOL_Z252 rides the most fragile link in the stack (Bloomberg VM → launchd collector). A Bloomberg outage during a developing crash freezes the dial at 100% and blocks even the TS<0.92 hard trigger — which is computable from free real-time CBOE data and needs no pipeline at all. The §5.4 manual override half-fixes this but never specifies what a partial input set maps to: VIX-only scoring maxes at 2 points → the dial can never reach 50%/30% states during an outage. Degradation must be per-component, not all-or-nothing.

(e) Operational load — ~8 action days/yr plus a one-glance dashboard is well within one human + AI. Fine.

(f) IBKR mechanics — one real contradiction: §4 declares fractional shares "mandatory" for SPY while §2.5 routes Tier A via MOC. IBKR fractional orders do not route to closing auctions (auction orders are whole-share; fractional executes internally as market/limit day orders). You cannot have both. Whole-share rounding is the honest answer — SPY at $745 is 0.75% NAV granularity, absorbed by the $200 min-trade filter. PDT exempt at $100k, margin-type for T+1 correct, cash-yield claims match the miner (note: a drawdown of NAV below $100k prorates the published rate — trivial).

(g) Slippage when signals fire — the LOC ±15bp band is miscalibrated for the tape it will meet. On a -3% de-risk day the 15:40→16:00 drift routinely exceeds 15bp; Tier B/C sells will systematically fail exactly when the dial fires, rolling into next-morning gap risk in the adverse direction. Choosing the close itself is right (deepest venue in stress, even March 2020), but the band guarantees non-fills. Level-3 halt days (no auction) need a stated default.

REQUIRED FIXES:
1. Rewrite §2.1 staleness as per-component degradation: hard trigger (TS<0.92, public CBOE data) always live; stale components carry last value ≤5d then score conservatively per a pre-specified partial-score map (define what VIX-only, VIX+HY-only, etc. imply for target state).
2. Widen the Tier B/C close band from ±15bp to ±50-75bp on de-risk days (or MOC Tier B, banded LOC Tier C only), and pre-register the next-morning-midpoint fallback as costed lag-2 behavior.
3. Resolve the fractional/MOC contradiction: dial trades are whole-share only, rounded, with the $200 filter absorbing residue; delete "fractional mandatory."
4. Script the 15:40 pipeline end-to-end (score → netted basket → API submission by 15:48); manual entry is prohibited on state-change days.
5. Restate dial cost with a stress multiplier (2-3× median spread on de-risk legs): ~25-35bp/yr honest figure — still trivial, but the 10.1bp print flatters.
6. Add the missed-operator-day rule explicitly: any missed 15:40 compute executes next close as lag-2, logged against the §6 ops-kill counter; define the no-auction (LULD Level 3) default as freeze-one-day.

---

# S6-fable-desk

## Statistical skeptic

I have everything needed. Writing the verdict now.

VERDICT: MAJOR

**Critique**

The design's structure is genuinely good — $0 funding, staged gate, pre-registered kills, bounded ~−$3k downside. That structure is why this isn't FATAL. But its two evidence pillars and its gate all fail statistical inspection.

**1. The Tier-1 event evidence is weaker than stated — one pillar is statistically zero.** The design calls the event windows "measured, statistically significant post-event drift." The artifacts say otherwise. From `Data/loop/event_studies/downgrade_em_20260612_131744/results.json`: the −2.8%@63d EM-downgrade CAR has t=−1.5 and a 2000-draw bootstrap 95% CI of **[−6.96%, +1.05%] — it includes zero**. The 63-day EVT_RATING embargo, and the 8bp/event Avoid-List math built on 2.8%×3%, rest on an insignificant cell. Only the 5d EM number clears |t|=2.0, barely, and it is the best of a 12+-cell grid (all/EM/DM/high-VIX/low-VIX × 5d/63d × up/down) mined without registration. The miner's own scope note confirms event studies "live outside these ledgers" — i.e., the constitution's "every trial counts" deflation was never applied to ~15 event studies × multiple horizons/subsamples. The two cells that do clear (upgrades −2.4%@63d t=−2.2; CDS inversion −4.5%@63d t=−2.4) are the best of ~30 undeflated cells; neither survives even crude multiplicity correction.

**2. The significant cells are crisis-clustered and double-counted.** CDS-inversion events by year: 20 of 41 fall in 2007–2009, 11 more in 2020–2022. Overlapping 63d windows inside the GFC mean the bootstrap (which resamples events as i.i.d.) badly understates the CI; the effective independent-episode count is ~10–15, and "−4.5%@63d" is substantially "conditioning on being in 2008" — pure regime dependence. Worse, ChinaA and ChinaH appear as two events for the same 2007-08-03 sovereign inversion (per repo convention, China broadcasts to both), inflating n and correlating "independent" observations. And the diagnostic the design waves past: **upgrades also drift −2.4%** (hit rate 0.31). When both signs of an event predict the same direction, the event carries no directional information — the conditioning is "a rating action happened to a (mostly EM) country," a regime/benchmark artifact, not drift.

**3. Tier-2 "independence" violates the repo's own constitution.** mine_docs §11 (context-tier quarantine): "the combiner is excluded from agreement counts (double-counting)." The design's Tier-2 explicitly lets COMBINER_RIDGE_DAILY_V1 be one of the two initiating votes alongside bank-gap or twins. The ledger's own summary: the house edge is "**one mechanism family measured four ways** (trade/bank networks, fundamental twins, lead-lag), aggregated by a daily ridge combiner." So the flagship live specimen — Hong Kong #1 bank-gap + #3 combiner + #3 twohop — is one diffusion signal counted three times, not confluence. CONF_DIFFUSION as specced initiates on ~1 independent mechanism, and the combiner vote imports the in-sample component-selection ceiling (components picked 2026-06, forward verification pending) into a "validated confluence" label.

**4. The gate arithmetic is internally inconsistent and noisy.** Brier ≤0.24 for a calibrated forecaster requires hit rate ≥60% (h(1−h)≤0.24 ⇔ h≥0.6). Yet §3's EV case models the desk "at exactly its gate bar (55% hit)" — a calibrated 55% desk scores 0.2475 and **never funds**. Either the EV scenario describes a desk that fails the gate, or the desk passes by overstating probabilities. And at n=20, a zero-skill desk stating 0.55s (Brier mean 0.2525, se≈0.011) passes ≤0.24 by luck ~13% of the time; the "mean net return >0" co-condition is roughly a coin flip. K1 permits unlimited new paper cohorts after 6-month moratoria — gate-shopping compounds the false-pass rate across retries.

**5. Measured vs traded object mismatches.** Rating events are monthly-bucketed (`sov_ratings_monthly` diffs, anchor = month-end: event 2015-05-01 → anchor 2015-05-29); the live rule embargoes "63 trading days from event date" (e.g., Mexico 2026-06-01 announcement). The desk would trade a window the study never measured. Separately, all CARs are on T2 index returns; the 0.36/0.60 ETF capture ratios guarding the phantom-alpha audit are measured on only 13 months of `etf_prices_daily` (2025-06+), one regime, with 0.75–0.85@21d an extrapolation, not a measurement.

**6. The only "measured" P&L channel is unrealizable as specced.** The 10–30bp/yr Avoid-List value accrues only if other sleeves consume it, which the design leaves to "their own specs" — no consumer is named. Its largest component (EM downgrade 63d) is statistically zero per point 1.

What survives: the paper stage itself is free, the ledger/Brier machinery is real, and the mechanism-disambiguation thesis (c) is plausible but unmeasured — which the design admits. Points 1–4 must be fixed before any funded trade.

REQUIRED FIXES:
1. Re-run the three Tier-1 event studies with clustering-aware inference (calendar-time portfolio or block bootstrap by episode; deduplicate ChinaA/ChinaH and U.S.-triple broadcasts), charge all ~15 burned event studies to the new sovereign-events family trial count, and require EVT_SOV_RATING_CHANGE_EM / EVT_CDS_CURVE_INVERSION to clear the harness's deflated gates on one pre-declared primary horizon. Drop the EM-downgrade 63d embargo (bootstrap CI spans zero) unless it survives re-testing; explain or abandon the upgrade-also-negative anomaly before treating either sign as tradable.
2. Enforce the constitution's combiner exclusion in Tier 2: the combiner may never pair with a diffusion-family member (graph/twins/leadlag) as the second initiating vote; CONF_DIFFUSION requires two mechanistically disjoint families (e.g., diffusion + SOV_2S10S) or is demoted to paper-only permanently.
3. Repair the gate: state the true implied bar (calibrated ⇒ ≥60% hit at Brier 0.24) and redo §3's EV at that bar; raise the paper gate to ≥40 closed theses or add a binomial test (hit >50%, p<0.10) to cut the ~13% no-skill false-pass; hard-cap K1 retries at one new cohort, ever.
4. Align the live embargo window to the measured anchor (month-end-after-event for ratings) or re-anchor the studies on actual announcement dates before registration.
5. Name the Avoid-List consumer (which sleeve, what rule) or delete the 10–30bp/yr claim; restate it net of ETF capture.
6. Flag capture ratios (0.36/0.60) as 13-month single-regime estimates; re-measure before Stage 1 and recompute K5/gate thresholds from the updated numbers.

## Execution skeptic

VERDICT: MINOR

This is the hardest of the eight sleeves to kill on execution grounds because it asks for $0, trades ~25 times a year, and already ate the execution miner's homework. The costs are fine. Say it plainly: at $2.5–10k clips, every ticker except EDEN is <0.35% of ADV, commissions are $0.35–$1/order (~60 orders/yr ≈ $60 ≈ 0.06bp on the account), and the tier×horizon matrix with the 5×-cost expectancy rule is exactly what a market maker would impose. Capacity, impact, and commission drag are non-issues. What survives scrutiny less well is the operational plumbing and two pieces of arithmetic.

(a) Cost realism. The §3 assumption of ~14bp average round-trip is skewed low for where this desk will actually live. Its Tier-1 events are EM-concentrated and its live specimens are EIDO (Tier B, 12bp), TUR (Tier C, 15bp), EWW (Tier A, fine). A realistic mix of half Tier A / half Tier B-C is ~20–30bp round-trip, cutting the gate-bar case from +33bp/trade to ~+20–25bp and $660/yr toward ~$450–500. Still positive; overstated ~30%.

(b) Turnover. Trivial. No issue.

(c) Timing contradiction — real bug. The session runs 08:30–09:15 ET but precondition 3 requires the 09:30 marks job, which hasn't run yet at session time. Worse, the livedb miner shows the brief available on 07-02 covered 06-30 — T−2, not the T−1 the precondition demands. As written, the stand-down rule fires on normal days. Either the desk trades on T−2 data (acceptable at 5–63d horizons, but say so) or it stands down chronically — which wrecks the gate timeline. And that timeline is already optimistic: ≤3 concurrent slots × 30–63d holds ≈ 18–25 closes/yr, so 20 closed paper theses is 10–13 months, not "5–8" — unless paper-stage concurrency is uncapped, which §2.4 never specifies.

(d) Pipeline reliability. Rating events depend on nightly BBG/BQL collectors behind a Parallels terminal; a down terminal means the downgrade is seen at T+2, eating most of the −0.9%@5d leg (the 63d leg survives). sov_rating_changes covers only 20 rated countries. The live_signals INSUFFICIENT_COVERAGE mismatch is already a named precondition — good.

(e) Operational load. ~45 min/day × 252 days ≈ 190 hours/yr of attention for a year-1 EV of $0 and a conditional best case ($660–2,800) roughly equal to the cash yield on the notional sleeve. The design admits this is an option purchase on calibration; fine, but it competes with seven other sleeves for one operator. Tolerable, not free.

(f) IBKR mechanics — three concrete defects. (1) MOC/LOC auction orders cannot carry fractional share quantities (fractional executes internally, auctions are exchange-routed whole-share). The design mandates fractional sizing AND Tier-C LOC entries AND MOC time-stop exits — incompatible as written. (2) Double-sell hazard: a resting GTC stop-limit plus a same-day MOC time-stop can both fill, creating an accidental short in the margin-type account — a mandate violation. No OCA grouping is specified. (3) The "failure bounded at ~−$3,000 lifetime" claim is soft: stop-LIMITS with 30–75bp bands do not bound gap risk; three correlated EM positions gapping through their bands (exactly the stress scenario in which Tier-1 events cluster) can overshoot the K3 −$2,000 floor before any trigger evaluates. Also, stops rest on ETF prices while invalidation is defined on T2 index marks — for high-basis names (ASHR 21d premium ~10%, EWY −2.1% prem snapshot) the stop will fire on basis noise, not thesis failure. Finally, IBKR pays zero on the first $10k of cash, so "cash ≈3.4% on sleeve capital" overstates the mostly-cash sleeve's benchmark unless cash is pooled account-level.

(g) Stress slippage. Tier-1 exits trade exactly when spreads are 2–5× median (EZA 27bp → 50–100bp on a downgrade day). Paying 100bp to dodge a measured −280 to −450bp drift is still correct — acceptable. The deeper problem is that the sleeve's only *measured* economics, the Avoid List (10–30bp/yr), has no execution pathway: it requires mechanical sleeves to sell names they hold, the desk forbids itself from overriding them, and no sleeve is obligated to consume the list. As designed, the measured channel's realized value is $0.

None of this is fatal for a $0-capital paper protocol with a 10-month runway to fix plumbing. It is a MINOR verdict with mandatory fixes before Stage 1.

REQUIRED FIXES:
1. Resolve the session-timing contradiction: move the session to post-09:30 or restate precondition 3 as "previous session's marks"; explicitly permit trading on T−2 surfaces (with decay note) or accept chronic stand-downs.
2. Specify paper-stage concurrency and restate the gate timeline honestly (~10–13 months at 3 slots), or raise paper concurrency to hit 5–8 months.
3. Whole-share sizing for any position entering via LOC or exiting via MOC; restrict fractional use to SMART limit/stop orders on SPY/QQQ/EWY-class prices.
4. OCA-group every position's stop-limit and time-stop exits (or hard rule: cancel resting stops before placing MOC) to eliminate the double-sell/short hazard.
5. Reword the downside claim: −$3,000 is an expected demotion bound, not a hard floor; add a gap-risk stress line (3 × $10k correlated EM positions, −8% gap ≈ −$2,400 in one day) to §5.
6. Define stop placement for high-basis names: widen or waive ETF-price stops where 21d basis vol > band width (ASHR, EWY), relying on the 09:30 index-mark check instead.
7. Define an Avoid-List consumer at book level (which sleeve, what rule) or reclassify the 10–30bp/yr channel as unrealizable and remove it from expected numbers.
8. Re-baseline §3 per-trade cost using the desk's realistic tier mix (~20–30bp RT), and model cash yield with the $10k zero-interest floor.

---

# S7-wildcards

## Statistical skeptic

VERDICT: MAJOR

CRITIQUE

This is the best-governed design in the book: $0 capital, pre-registration, per-trial kill thresholds, family-charged flips, and a mandatory ETF-capture gate. I verified its load-bearing claims against the evidence and the repo (read-only): the ledger census (59/21/21, ~4 mechanisms) matches miner 1 exactly; the W1 flip numbers match the actual run file (`H_20260612_011_20260612_135100.json`: 63d IC 0.0687, NW-t 3.917); the harness NW lag equals the horizon in trading days (v2), so the 63d t-stat is properly overlap-corrected — a trap the design does not fall into; `scripts/loop/event_study.py --events-sql` exists with bootstrap-across-events and a >30% country-month overlap guard, so the event-study path is real tooling, not vaporware; `etf_prices_daily` genuinely starts 2025-06-09. Nothing killed is re-proposed. But three findings are fix-before-run, not monitoring items.

1. W6 is structurally impossible as specified — verified in code. `evaluate_signal.py` sets `min_cov = max(10, ceil(0.8×N))` and `rank_ic_series(min_countries=10)`: every date with fewer than 10 countries is dropped from the IC series. The foreign-flows universe is 6 (5 before India's 2017 entry). The registration would produce an empty IC series and a guaranteed INSUFFICIENT_COVERAGE verdict, burning a trial in the new FLOWF_ family for nothing. The design's claim that the "harness scales coverage gate" is half-true — it scales with a floor of 10 that the designer evidently did not check. A 6-name cross-sectional rank IC is dubious anyway (effective breadth ~2–3 after the Asian common factor).

2. The sleeve's headline payoff (W3, "~0.5–1.5%/yr book-wide at zero incremental turnover") conflates two different strategies. The zero-cost version — re-time rebalances you were doing anyway into the [-1,+3] window — touches only trades that already exist; on a book rebalancing weekly/monthly its edge is a handful of bp/yr, not 50–150. The version that earns the design's arithmetic (4 days × ~5bp × 12 on the invested fraction = 240bp on the *affected* fraction) requires deploying the book's ~30% cash sleeve into equities 12 times a year: one-way turnover ≈ 12×2×0.30 = 7.2×/yr, ≈36bp/yr at 5bp — real cost against ~72bp gross benefit at half-strength literature effect on a 30% sleeve. Net ≈ 0.3–0.4%/yr, not 0.5–1.5% "at zero cost." The trial itself (in/out difference, t≥2, +5bp/day floor) is clean; the expected-value claim justifying the sleeve's asymmetry is roughly 2–4x overstated and must pre-register which implementation is being valued, with its turnover.

3. The expected-outcome math inherits a known inflation. The 36% WEAK base rate counts ~12 correlated graph variants of one mechanism as 12 successes; the per-mechanism hit rate is ~4/25 ≈ 15–20%. Expect 2–4 WEAKs from 14–18 trials, not 5–6. This also mis-calibrates the sleeve-level kill: at an honest ~17.5% rate, P(zero WEAK in the first 8 trials) ≈ 0.825⁸ ≈ 21% — a one-in-five chance of false suspension even if the ideas are as good as June's. Conservative bias, but state it.

Second-tier issues. W1's 63d/t-4.5 headline is the max over a ~30-look grid (3 horizons × 2 directions × ~5 FX-surface variables — impvol, carry show the same flipped-63d sign at t 2.6/1.8), so shrink expectations well below 3.9; more importantly the mechanism ("fear premium decays") is confounded with simple post-stress reversal, and the FF-spanning gate (Mkt/SMB/HML/RMW/CMA/WML) contains no short/medium-term reversal factor, so a repackaged reversal effect would pass promotion — add an orthogonalization-to-own-trailing-63d-return diagnostic. W9's primary dummy bundles downgrades (literature-corroborated) with upgrades-drift-negative (t=−2.2, n small, literature says no drift) — a likely-noise leg baked into a pre-registered rule; split it. W11 registers cheap-is-better ERP at 6m while the ledger's own CAPE 6m drift runs *anti-value* (+0.054, t 1.95), and 6m was chosen after seeing VAL_EY_PCT t≈1.96 there — a data-informed horizon the design doesn't flag with the one-trial-no-flip rider it applies elsewhere. W2 specifies a "21d" primary horizon for a monthly-frequency, 2-month-lagged signal; the harness's monthly path aligns in months — the spec should say 1m. W4/W5's n≥100 event gate on 13 months of episode-clustered fires (136 in June alone, mostly the same episodes) will collide with the event tool's 30% overlap guard; expect INSUFFICIENT rather than signal — acceptable, since staged.

What survives scrutiny: charging W1 as bbg_skill trial 17, the DECLINED holder-stress item, the live_signals reconciliation precondition, the predmkt no-peek gate, and the ETF-capture ≥0.5 firewall are all correct and verifiable. With the fixes below this sleeve is fundable research.

REQUIRED FIXES:
1. W6: respec before registration — either (a) event-study path per country / pooled with `--events-sql`, (b) a portfolio time-series test per market, or (c) owner-approved harness change to the min-10 floor. Do not submit a 6-country CS rank to the current harness; it is a guaranteed wasted trial.
2. W3: pre-register the implementation (pure re-timing vs cash-deployment), its incremental one-way turnover, and a net-of-cost expected value; replace the "0.5–1.5%/yr at zero cost" claim with the consistent pair (~0.1–0.3% re-timing; ~0.3–0.5% net cash-deployment at half-strength literature effect on a 30% cash sleeve).
3. W1: add a mandatory diagnostic orthogonalizing FX_BF25_Z252 to the country's own trailing 63d return (and to SIM/graph gap scores); if the orthogonal IC t < 2, the verdict must record it as repackaged reversal regardless of raw IC — mirror the W8 orthogonalization language.
4. W9: primary spec = downgrades + CDS inversions only; upgrades as a separately-reported diagnostic leg, not part of the registered dummy.
5. Recompute §5 expectations with the per-mechanism base rate (~15–20% → 2–4 WEAKs) and either restate the 0/8 sleeve-kill as accepting a ~20% false-suspension risk or extend it to 0/12.
6. W11: attach the one-trial-no-flip rider (6m horizon was data-informed via VAL_EY_PCT t≈1.96) and acknowledge the CAPE 6m anti-value drift as adverse prior evidence in the registration.
7. W2: state the primary horizon as 1m on the harness's monthly path (not "21d"); confirm the historical TOT_IMPULSE backfill uses the 2-month embargo throughout, including the pre-2026 reconstructed portion.

## Execution skeptic

VERDICT: MAJOR

**Framing.** S7 commits $0 and trades nothing, so there is no order flow to kill today — max loss is research time, exactly as chartered. On pure cost grounds the sleeve is clean, and I'll say so where true. But the design embeds execution assumptions that flow directly into its headline expected value and into the capital decision its graduates will trigger. Several are wrong, and one flagship spec is untradeable as written. That earns MAJOR, not MINOR.

**(a) Costs vs breakevens — mostly fine, with honest caveats.** The graduation bar (BE ≥10bps) plus Tier-A concentration handles most of it. W2 at 21d holds survives even Tier-C tickers (~1bp/day amortized). W7's laggard events fire disproportionately in stressed, wide names (today's specimen Indonesia = EIDO, 12bp), but 21–42d holds amortize that. W11's live specimen is EDEN — the universe's worst ticker ($0.8M ADV, 26bp spread) — tolerable only because bands are quarterly and worked with LOC/resting limits. W6's THD/EPHE/EIDO legs at 5d holds are marginal; the design's own concentration in EWY/EWT/INDA is the correct answer. Costs: broadly fine.

**(b) Turnover math — the miner's per-side inputs break at graduate scale.** The 3–5bp Tier-A design input assumes $3–7.5k clips. A fast graduate (W4/W5/W6 class) funded at $10–15k running combiner-like turnover (0.6/day one-way) mathematically forces clips of $600–1,500 unless the book holds 2–3 names. At an $800 clip the $0.35 tiered minimum is 4.4bp of commission alone — the "3bp all-in" Tier-A name becomes 6–8bp one-way, roughly doubling assumed costs and cutting the already-thin $50–375/yr graduate economics toward zero. Slow graduates (8–20 orders/quarter) are unaffected.

**(c) Timing — W5 is untradeable as specified.** BASIS_USBETA_RESID_1D completes at the 16:00 close; MOC submission cutoffs are ~15:50 ET (NYSE/Arca) / 15:55 (Nasdaq), and ASADO has zero intraday data infrastructure — everything is daily closes landing at ~07:30 next morning. "Buy the overshoot-down names at the US close" cannot be executed by any process this pipeline can run. The real alternatives — T+1 open (spreads 2–5x wider per the miner's own tactics, reversal partly gone) or T+1 close (a different, 1-day-lagged signal) — must be what gets tested, or the event study validates a phantom trade. W4 loses day 1 of a 1–5d signal the same way (the 0.60 capture at h=5 coincidentally clears the ≥0.5 gate — thin). W8 live use inherits the combiner's T+2 staleness against a 5d horizon; register the achievable lag, not lag-0.

**(d) Pipeline reliability — one spec can't run as written.** Verified read-only today: `price_state_daily` contains exactly one date (2026-06-30, 34 rows). The W4 event study's "13 months × ~136 fires/month" history does not exist in storage; it must be recomputed from `etf_prices_daily` (2025-06-09 onward, verified) — feasible, but the spec equivocates between "materialize a history table" and running now. The archiving builder change is an owner dependency the sleeve cannot perform. TOT staleness (as-of 2026-05-01) and the live_signals INSUFFICIENT_COVERAGE reconciliation are correctly self-flagged.

**(e) Operational load — fine.** One registration/week, parallel event studies, ~2–3 research-days/week is realistic for one human + AI. The binding load is governance discipline across seven trust-root edits, which the design already treats as atomic commits.

**(f) IBKR mechanics — two errors.** Fractional orders cannot route to closing auctions; MOC/LOC requires whole shares, so "MOC/LOC + fractional SPY/QQQ clips" is internally inconsistent (whole-share granularity at $10k is acceptable; drop fractionals for MOC sleeves). And the first $10k of cash earns 0% at IBKR — a graduate funded at exactly $10–15k whose "hedge is cash" earns roughly nothing on its defensive posture, further shaving the stated economics.

**(g) Stress slippage — W9 sells into the blowout.** The avoidance rule exits within days of a downgrade, precisely when spreads run 3–5x median (EWW 4→15–20bp; Tier-C names toward 60–100bp). The −2.8%@63d drift dwarfs a stressed round trip; the −0.9%@5d leg does not. The ablation must charge stressed spreads, not median.

**The biggest single problem is W3's headline arithmetic.** The sleeve's asymmetric payoff — "0.5–1.5%/yr book-wide at zero incremental turnover" — double-counts. The invested fraction of the book earns the ToM window whether or not an overlay exists; the overlay adds only (average idle cash) × (window edge), and cycling that cash in/out 12×/year costs real spread. At 15% average cash and half-strength literature effect: ~36bp/yr gross, ~14bp cycling cost, net ~20bp/yr ≈ $200 — roughly 3–5x below claim. It also conflicts with fast sleeves, whose 1d signals cannot wait for a calendar window. W3 remains worth testing; its EV as the program's justification is inflated.

REQUIRED FIXES:
1. Rewrite W5's spec around an executable trade: signal from T close (available 07:30 T+1), entry T+1 at a declared venue/time (open with a spread haircot of 5–10bp, or T+1 close), and test THAT lagged version — or shelve W5 until intraday capability exists.
2. Restate W3's expected value as incremental-cash-only, net of 24 cycling legs/yr at tier-weighted costs; cap the claim near ~0.2–0.4%/yr at realistic cash fractions, and exempt 1d-hold sleeves from the re-timing rule.
3. Mark the 60-day paper theses on ETF closing prices (the tradable instrument), not T2 local-index returns; the capture re-test is a backtest, not a substitute for ETF-marked paper.
4. Add a minimum-clip rule for fast graduates: no order below ~$2,500 (keeps the $0.35 minimum ≤1.5bp), which implies max 3–5 concurrent names at $10–15k funding — write this into the graduate PRD template.
5. Fix the W4 spec: state explicitly that basis_gap_z history will be recomputed read-only from `etf_prices_daily` + T2 indices (the stored table is a 1-day snapshot, verified 2026-07-02), and that the archiving builder change is requested, not assumed.
6. Register W8 with its live-achievable lag (T+2), not the harness-convenient lag.
7. Remove "fractional shares" from any MOC/LOC sleeve; whole shares only into closing auctions.
8. Charge W9's ablation stressed-spread exits (3–5x median on event day, LOC bands, partial-fill risk) rather than median spreads.

---

# S8-portfolio-architect

## Statistical skeptic

VERDICT: MAJOR

CRITIQUE

This is an unusually honest design — the PIT hygiene is genuinely good (the `1DRet` forward-return trap was caught and returns rebuilt from TRI levels; skip-1 tested; ETF capture measured; PIT edge re-test run; no forward returns anywhere; long-only numbers are native top-5-minus-EW, not naively halved LS). The multiplicity ledger is real (59 trials charged, every deflated Sharpe negative, nothing above WEAK) and the design admits it. Nothing here is FATAL. But the central alpha claim (+0.5 to +2.5%/yr, central +1.3%) does not survive contact with the design's own evidence, in four specific places.

1. The S1 cost blend is contradicted by the signal's own composition — and I measured it. The design prices S1 at "~5 bp blend" (cost 252×2×0.148×5bp ≈ 3.7%/yr) against realistic gross of +4.4%/yr. I queried `combiner_scores_daily` (read-only): the historical top-5 membership is 21% Tier-B + 25% Tier-C (blended one-way ≈ 9.5 bp full-sample, 10.0 bp in 2024+, stable across every period). At the measured blend the drag is ~7.1%/yr — S1's realistic net is ≈ −2.7%/yr, matching mine_math's own Net@10bp row (−3.0 to +0.3%). Worse: the single most frequent top-5 name in 2024+ is Denmark (199 days), which S1 excludes — so the measured IC/backtest is not the portfolio S1 trades. The escape hatches are all unmeasured: the L4 Tier-A-only fallback rests on NT-1 (IC on the restricted universe: unknown, registration pending), and banding's gross retention is "assumed ~offsetting per PL-2" (untested). S1's central book contribution of +0.2 to +1.0% should be ≈0 until one of these is measured.

2. Mode B goes live in P2 with unmeasured, plausibly negative economics. All of S1's cited economics are same-close (Mode A). Mode B (T-1 scores) drops index gross to 8.1%/yr at h=5, and its ETF-space degradation is admitted to be unmeasured — yet P2 schedules 12.5% live capital on Mode B. Combined with point 1, the sleeve carrying most of the claimed alpha launches in a configuration whose best-available analog nets roughly zero to negative. The 13-month ETF panel exists; Mode-B-in-ETFs can and must be measured before live.

3. The expectation table sums one mechanism twice and rides tiny event samples. S1 (25%) and S2's C1–C3 (≈65% of a 30% sleeve) are the same diffusion signals — the combiner's inputs overlap S2's components — yet §8 adds their standalone expectations as if independent. The `SLOWBOOK_COMPOSITE_V1` itself has never been harness-tested (R2 pending); its +0.4–1.4% is designer arithmetic on individually marginal parts (twins net10 LS Sharpe 0.17; 2s10s 0.08; reflation t 2.3–3.0). S3's +0.3–0.5%/yr "normal years" comes from CARs at t≈2.0–2.4 on ≤41 events, and the fact that upgrades AND downgrades both drift negative (−2.4% and −2.8% @63d) is a classic conditioning-on-event confound — it may just be "EM sovereign in the news" base-rate drift, never tested against matched country-period baselines. S5's entire cumulative gain comes from 2 of 38 episodes (2008, 2020) and flips sign from lag-1 (+0.38%/yr) to lag-2 (−0.24%/yr). The −18 to −25% expected maxDD stacks dial × breakers × vetoes narratively; the joint overlay was never simulated, and breakers measured on daily closes don't bind through gaps (2020's −29% happened in ~4 weeks).

4. The verification machinery is statistically underpowered — which guts the "validation vehicle" purpose. From NW-t 10.7 on ~5,580 days, daily IC σ ≈ 0.38. The P2 gate "live 63d IC > 0" passes ~88% under a fully-alive signal and 50% under a dead one — a near-coin-flip gate. The 126d halving rule fires on noise ~19%/window under a decayed-but-alive IC of 0.03 (expect spurious halvings most years). At book level, mean +1.3% against ~3–5% tracking error needs ~21–38 years for t=2; twelve months of live record verifies nothing. The kill table will whipsaw on noise while the program cannot actually confirm its central claim on any stated horizon.

Secondary notes: full-sample (2005+) stats include a decade when ASHR/INDA/KSA/EPHE/EIDO/EDEN didn't exist — the 2016+ haircut partially handles this, but 2016+ h=5 net@10bp is −0.1%/yr, i.e., the instrument-tradable subperiod at the measured blend is dead. The 2021–26 "decay mitigation" subperiod sits inside the June-2026 component-selection window, so no true OOS exists; mine_lit's ~30% ML-composite OOS haircut is never applied. Capture 0.60 is a 264-day estimate with a wide CI, and 0.75–0.85 at h=21 is a two-point extrapolation. These are all acknowledged as risks but not propagated into the central number, which is built assumption-on-assumption toward the optimistic edge.

The paper-first phasing, $0-at-launch gating, breakers, and honest governance-exception framing keep this from being dangerous. Funded as designed, the likely outcome is an expensive index fund with excellent record-keeping — acceptable only if the fixes below are binding.

REQUIRED FIXES:

1. Reprice S1 at the measured top-5 tier blend (~9.5–10 bp one-way, 46–48% Tier-B/C membership; EDEN is the most frequent top-5 name and is excluded from the traded book) or gate S1 on NT-1 (Tier-A-only IC, currently unmeasured) plus a measured (not assumed) PL-2 banding gross-retention number. Until then, state S1's expected contribution as ≈0.
2. Measure Mode-B economics in ETF space from the existing 13-month ETF panel before any P2 live capital; no live S1 on unmeasured execution mode.
3. Replace the additive §8 expectation with a joint estimate: S2 composite's marginal IC orthogonal to combiner scores; register and test SLOWBOOK_COMPOSITE_V1 (R2) before attaching any expectation to it.
4. Publish false-kill/false-pass probabilities for every gate and kill window (63d/126d/252d IC rules, 2-clean-month phase exits); lengthen windows or explicitly re-label them monitoring rather than validation, and restate what the program can and cannot verify in 12–36 months.
5. Re-test S3 event CARs against matched non-event country-period baselines (resolve the upgrades-also-negative confound); set S3's normal-year expectation to 0 pending that test, keeping vetoes as free insurance.
6. Run the joint dial × breaker × veto historical simulation on the EW book before publishing the −18 to −25% maxDD claim; label gap risk explicitly.
7. Apply an explicit OOS-selection haircut (mine_lit's ~30% class prior) to all combiner-derived central estimates, since the 2021–26 subperiod is inside the component-selection window and does not constitute out-of-sample evidence.

## Execution skeptic

VERDICT: MAJOR

**The good news first, because it's real.** The cost architecture survives adversarial review. At $600–$7,500 clips, every ticker except EDEN is <0.35% of ADV; impact is a rounding error and the spread tiers in mine_exec are honest (official 6c-11 medians, not stale folklore). Confining daily turnover to Tier A, amortizing Tier C over ≥15–21d holds, LOC-with-band below Tier A, banning market orders and the open, netting one order file per close — this is what a cost-aware book should look like. Commission math checks out at $3k+ clips (0.5–2bp). Nothing here is FATAL. But five execution/ops findings are MAJOR, and together they mean the central "+$1,300/yr" is not yet a measured number.

**1. The go-live gates measure the simulator, not the market.** P0's exit criterion "median |paper MOC fill − official close| ≤ 3bp" auto-passes: IBKR's paper simulator fills MOC at the official closing print by construction. Same for S4's G3 ("simulated MOC fills") and M3's resting-bid economics — paper fills passive limits on touch with no queue position, so M3's fill-rate and adverse-selection stats will be fantasy-optimistic. The three things paper genuinely cannot test are exactly the three the book depends on: LOC partial-fill behavior in thin Tier-B/C closing auctions (ECH/THD/EPHE/EDEN), real MOC prints in $5–15M/day Arca auctions (EWM, EWS, EWH, KSA), and M3 queue economics. The paper phase validates plumbing only; the design presents it as validating execution.

**2. The same-close sleeves rest on an unverified data source.** S4-M1's 15:40 compute and S1's Mode A both require same-day home closes at 15:40 ET "via IBKR index quotes." Nobody has verified IBKR carries live index data for all 21 home markets — Taiwan (TWSE), Vietnam (VN-Index), and Saudi (Tadawul) are not available as IBKR index feeds, and several others need per-exchange subscriptions never budgeted or listed. `t2_levels_daily` is nightly; it cannot substitute. Until this is resolved per-market, M1's 21-name universe (and its pilot statistics) and the entire Mode-A unlock to 25% are aspiration. Related: mine_livedb shows the combiner at T+2 (06-30 data on 07-02) on the very day this was written — S1's own staleness rule would have blocked trading. Gate-failures will be routine; the economics assume ~252 trading days and will get materially fewer.

**3. Cost consumes ~60% of gross, and the alarm is set past the point of death.** Steady-state annual cost base: S1 ≈ $930 (252×2×0.148×5bp on $25k), M1 ≈ $1,490 (2×0.367×8bp×252 on $10k), plus S2/CORE/dial ≈ $150–250 → ~$2,500–2,700/yr against central net active of $1,300. A 1.3× cost overrun — from LOC partials, auction prints, or the Tier-A budget being calibrated at $7.5k clips while S1 trades $3k at launch — erases most of the expected profit, yet the dashboard alarm fires at 1.5× and the program-shutdown trigger at 2×. The tolerance band is wider than the margin.

**4. The S8 arbitration quietly broke M1's clip economics.** S4 specced $15k → $1.5k clips → 2.3–4bp commission. S8 granted $10k → $1k clips, where the $0.35 minimum alone is 3.5bp — the document's own words: "below ~$1k/clip the $0.35 commission alone is ≥4bp and breaks M1's +1.8bp/day net margin." The grant sits exactly on the stated economic floor; realistic all-in at $1k clips is 6–8bp, i.e., at M1's own 8bp suspend threshold before any adverse auction print. M1 as granted will likely kill itself on arithmetic, not alpha.

**5. The 15:40–15:50 crunch contradicts itself.** Dial compute 15:40, M1 residual 15:40, file #2 assembled 15:42, submit 15:45–15:50 (NYSE MOC cutoff 15:50, no cancels after), abort by 15:49 — and §15 grants P2+ a "10-minute human veto window," which expires at 15:52, after the orders are irrevocable. The veto is fiction for close orders. Also unaddressed: single-human availability at 15:42 ET daily in P0–P1 (manual review is mandatory then), with no coverage protocol.

**Smaller but real:** (a) the +0.5%/yr cash-yield line is ~2× overstated — 80% of days the book sits at the 10% floor, which is exactly the first $10k IBKR pays zero on; honest figure ≈ +0.25%, which cuts central total return to ~7.85% vs EW's 7.7% — the "beats EW" headline is inside the noise of one arithmetic correction; (b) S3 forced exits and dial de-risks sell into precisely the sessions when Tier-B/C spreads run 2–5× the 6c-11 medians and EM ETFs trade at discounts — the −0.9%@5d avoidance CAR was measured on index closes, not on dislocated exit prints, and no stress-cost haircut appears in S3's +0.3–0.5%/yr; (c) dial de-risk deltas on $625 CORE positions fall under the $200 min-trade filter or force whole-position churn — the integration is under-specified in S8 (S5 solved it standalone).

REQUIRED FIXES:
1. Replace the paper fill-fidelity gates with live micro-size validation: in P1, trade 1-share/one-clip live orders (LOC bands, MOC, midpoint pegs, M3 resting bids) in every tier and score realized cost vs tier budgets; paper validates workflow only, never fill quality.
2. Before granting M1/Mode-A any status, verify per-market live home-close availability at IBKR (or futures proxies with subscription costs listed); publish the verified universe and re-run the M1 pilot restricted to it. Names without a T-0 home close are out.
3. Restore M1 clips to ≥$1.5k (either fund at S4's $15k spec or run 2×$3.75k tranches with top-3 concentration); re-derive net margin at measured $1k-vs-$1.5k commission and set the suspend threshold below realistic cost, not at it.
4. Re-set cost alarms to bind at 1.2× tier budget (trailing 20 fills) with auto-fallback to S1-L Tier-A-only, since 1.3× already destroys the margin.
5. Fix the timeline contradiction: no human veto on file #2 (auto-transmit at 15:45 with a kill-switch, not a review), or move the veto to file #1 only; add a written absence protocol (default = no new orders, holdings ride).
6. Correct §8 arithmetic: cash yield ≈ +0.25%/yr (state-weighted, $10k zero tranche); restate total-return central estimate and the EW comparison honestly.
7. Add a stress-execution haircut to S3/dial expectations (assume 2× tier spread + 50bp discount on forced EM exits) and specify the CORE/dial min-trade interaction (adopt S5's "sell-entirely-below-$650" rule explicitly in §5).
8. Log expected vs realized trading days per sleeve from P0 onward (gate-failure rate is a first-class economic input, per the 07-02 T+2 combiner evidence); re-base sleeve expectations on realized days.
