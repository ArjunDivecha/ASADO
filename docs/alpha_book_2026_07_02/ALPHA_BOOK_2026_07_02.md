# THE ALPHA BOOK — Integrated Final Draft
## Country selection from the ASADO warehouse, expressed through 34 US-listed country ETFs, hypothetical $100,000 IBKR account, long-only + cash

**Synthesizer's draft, 2026-07-02.** This document integrates eight sleeve designs (S1–S8), sixteen skeptic critiques (statistical + execution per sleeve), and six miner reports. Where designers and skeptics disagreed, the synthesizer rules and says why. All numbers trace to the miner                                                       t  /skeptic measurements cited inline; nothing here was newly computed. This is analysis and design, not live trading advice.

---

# PART 1 — THE ANSWER

**"What does the data know about picking countries that the current stock price of the ETFs doesn't?"**

The honest, evidence-ranked answer: **the warehouse knows several real things about relative country returns measured in local-index space; almost all of that knowledge is either already embedded in the US-hours ETF price by the time you can trade it, or eaten by trading costs at any realistic execution. What survives net, at $100k, is small, defensive, and mostly about avoidance, timing, and cost — not about picking winners.**

#                nn   1.1 The genuine informational edges, ranked by evidence

**Edge 1 — Cross-country return diffusion (the house edge, index space only).** When a country's bank creditors, trade partners, and fundamental twins have outrun it over ~21 days, it tends to catch up. This is the only multi-specification, point-in-time-confirmed mechanism in the ledger: the daily ridge combiner shows mean daily IC 0.057, NW-t 10.7 over 2006+; the PIT graph family (bank-neighbor gap NW-t 4.5, two-hop trade NW-t 4.4, twins NW-t 3.7) survived the point-in-time edge re-test. **But three facts gut its tradability today:** (a) the only direct test on the tradable instrument — 13 months of actual ETF closes — gives a top-5 spread of +1.9bp/day with t = 0.82 (95% CI −2.6 to +6.4 bp/day) and an ETF-based rank IC of −0.002 (t −0.16), versus +0.036 (t 2.64) on indices in the identical window; (b) the diffusion components' own 21-day ICs have been **negative since roughly early 2024** (twins 2024+ −0.070, bank gap −0.062, two-hop −0.049; the family's two live paper theses are 0-for-2); (c) the combiner's measured top-5 habitat is ~46–48% Tier-B/C tickers, implying 9.4–10bp one-way blended cost — the exact level at which its own economics table reads zero-to-negative, against a breakeven of 14.2bp. Components were selected in-sample 2026-06; every deflated Sharpe in the ledger is negative. **Verdict: the data knows this; it is not yet proven that the ETF price doesn't. It is a research asset, not fundable alpha.**

**Edge 2 — Sovereign credit event drift, short window (the one clean long-only edge).** EM rating downgrades are followed by −0.9% relative return over the next ~5 trading days (t −2.02 as reported; this is the **only** event cell that survives sovereign dedup and cluster-robust inference, at t ≈ −1.9 to −2.3). The famous longer-horizon numbers — downgrade −2.8%@63d, CDS-curve inversion −4.5%@63d, upgrades −2.4%@63d — do **not** survive honest inference: deduplicating ChinaA/ChinaH, clustering crisis-overlapped windows, and removing 2007–09 drops their t-stats to −0.8 to −1.8, and they are the best cells of a 30+-cell unregistered grid. The mechanism (EM mandate-driven forced selling; expensive EM ETF shorting protects the anomaly) is credible for the short window. A long-only book monetizes the free side: refuse to hold or buy the name for ~2–4 weeks after the event. Worth roughly 0–15bp/yr in normal years, more in downgrade-cluster years. Small, real, free.

**Edge 3 — Knowing when to be small.** A four-input stress score (VIX3M/VIX term structure, HY OAS z, MOVE z, breadth of FX-implied-vol stress across 29 currencies) scaled a 2006–2026 EW backtest from maxDD −58.9% to −46.7% at roughly zero cost in CAGR (8.27% vs 7.89% at lag-1; **−0.24%/yr at lag-2** — the achievable mixed-lag version was never run and the sign of the active return lives inside that gap). Only 10 of 38 de-risk episodes made money; the entire payout is GFC (+19.2pts) and COVID (+10.0pts); it did nothing in 2022 and hurt in 2015–16. It may be replicable by naive realized-vol targeting — untested. **This is insurance with an uncertain premium (~−1.6%/yr mean drag in ex-crisis years), not alpha.** The data "knows" stress states; the ETF price knows them too — the value is behavioral pre-commitment, honestly priced.

**Edge 4 — Execution microstructure and calendar (the most certain edge, and it's a cost edge).** ETF premium/discount vs fair value (Petajisto-style) as a *timing filter* — delay buys when ≥25bp rich, accelerate at discounts — plus turn-of-month scheduling (international ETFs earn most of their return in the [-1,+3] window per the literature; honest incremental value at realistic cash fractions ~0.2–0.4%/yr, not the 0.5–1.5% first claimed), plus refusing to pay spreads (MOC/LOC into closing auctions, midpoint pegs, never market orders, never the open). Worth perhaps 10–40bp/yr book-wide with essentially zero risk of being wrong-way. The data knows the ETF's own microstructure better than a naive executor does; that is genuinely knowledge the price doesn't charge you for.

**Edge 5 — Option value on unasked questions.** The warehouse has collected-but-never-tested surfaces with real priors: the FX 25-delta butterfly z-score **flipped** (higher-is-better) at 63d shows raw IC 0.069 with NW-t 3.9 in June's run files and was never registered (must first be orthogonalized to plain 63d reversal); terms-of-trade impulse (TOT_IMPULSE_Z36M) shipped in the rank registry untested; foreign-investor flow leads for 6 Asian EMs (58k rows, never registered). At the ledger's honest per-mechanism hit rate (~15–20%, not the variant-inflated 36%), 14–18 registered trials should yield 2–4 WEAK survivors and maybe one new mechanism. This is the pipeline through which any future funded tilt must come.

**Edge 6 — Negative knowledge: what the ETF price already knows.** The lead-lag network result (US leads 16 structural followers, IC 0.057, NW-t 8.5) is real in index space and **worthless at the US close**: US-listed follower ETFs embed the US leader's move the same day. The "US-hours overshoot fade" (S4) collapsed on inspection: 70% of its 13-month paper alpha came from one broken index mapping (EWY, +56% cumulative index-vs-ETF drift), and the properly gated result is 3.4bp/day, t = 1.4, net −0.1bp at 5bp costs. Treat both as proof of how efficiently the US-hours market maker embeds public cross-market information.

## 1.2 What the data does NOT know (the dead list)

Killed by the harness or by the skeptics and **not to be rebuilt on**: valuation percentiles (CAPE/PB/DY 10-year percentiles — if anything, 6-month drift runs anti-value, t 1.95); ETF short interest; FX implied-vol *levels*, risk reversals, butterflies as-specced, and FX carry; GDP consensus revisions; WEO-derived GDP revisions as a cross-sectional signal; Triptych review-queue lean (IC −0.003, context-tier only); holder-stress contagion (DEAD); the monthly combiner; ETF-flow contrarian (t −2.2, weak); "buy Asia after big US up-days" (refuted: −72bp vs own index next day). And the governing physical law of the whole book: **nothing in the ledger survives 25bp one-way costs; only 4 signals clear 10bp; 12 clear 5bp — while the flagship's own measured cost habitat is 9.4–10bp.**

## 1.3 The honest size of the edge, net, at $100k

- **Fundable expected active return vs an equal-weight-34 benchmark, today: roughly 0 to +0.7%/yr** ($0–700), coming from event avoidance (0–15bp), execution/calendar discipline (10–40bp), turn-of-month if it replicates (0–30bp), and cash-structure effects — **not** from country-picking signals.
- **Plus insurance:** an expected −8 to −12 point maxDD reduction in a GFC/COVID-class crash (conditional on crash-type; historical hit rate 2 of 5 major drawdowns), paid for by ~−0.5 to −1.6%/yr in ex-crisis years.
- **Plus option value:** the S7 research pipeline and the diffusion-family revival gates. If the 2024–26 diffusion sign-flip proves cyclical and ETF capture at slow holds is real (~0.6–0.75), the fundable active number roughly triples. That is a hypothesis, not an expectation.
- The gross index-space alpha the warehouse measures (+4% to +13%/yr in various constructions) **nets to approximately zero** at the ETF, at this account's cost structure, on current evidence. Anyone who tells you otherwise is quoting the numerator.

---

# PART 2 — THE BOOK (post-critique)

## 2.0 Synthesizer's rulings — where I sided, and why

| Sleeve | Designer asked | Stat skeptic | Exec skeptic | RULING |
|---|---|---|---|---|
| S1 Combiner Core | $60–100k flagship | FATAL | MAJOR | **KILLED as funded sleeve → S1-Shadow (measurement program, $0)** |
| S2 Slow Book | $35k | FATAL | MAJOR | **NOT FUNDED at launch → pre-registered revival gate** |
| S3 Event Book | $0 overlay | MAJOR | MINOR | **FUNDED as overlay, restructured to the short-window kernel** |
| S4 Microstructure | $20k post-gates | FATAL | MAJOR | **KILLED; M4 execution filter retained book-wide at $0** |
| S5 Cash Dial | $0 multiplier | MAJOR | MINOR | **FUNDED as risk overlay, gated on two mandatory re-runs** |
| S6 Fable's Desk | $0 → staged | MAJOR | MINOR | **FUNDED as paper program, gate repaired** |
| S7 Wildcards | $0 | MAJOR | MAJOR | **FUNDED as research charter — now the book's alpha engine of record** |
| S8 Architect | book structure | MAJOR | MAJOR | **Structure retained; allocation completely redrawn; arithmetic corrected** |

**On S1 I side with both skeptics against the designer, and with the stat skeptic against the exec skeptic's fix #1.** The designer's return chain multiplies an insignificant numerator (ETF spread t = 0.82) by a marginal denominator into a "measured" 0.60 capture, documents the wrong model (the 7-feature dead monthly table instead of the 6-feature daily ridge that actually includes the untradeable LL_LEADER_GAP_5D), and prices costs at 5bp when its own top-5 habitat measures 9.4–10bp. The exec skeptic proposed inverting to a Tier-A-only primary (S1-L); I reject that too — S1-L's alpha is admitted unmeasured (NT-1 never run). **You do not fund an unmeasured variant of a signal whose direct tradable-instrument test reads zero.** S1 becomes a shadow program (§2.2).

**On S2 I side with the stat skeptic's data over the designer's prose.** The recomputed 21-day ICs of the 65%-weight diffusion block are negative for ~2.5 years ending at the evaluation date (2024+: −0.05 to −0.07), the harness's own IC series corroborates, the family's forward record is 0-for-2, and the design's own K1 kill condition would fire at launch. A sleeve whose pre-registered kill criterion is currently true cannot be funded; drafting fixes don't change data. The revival gate (the skeptic's own fix #1) is honored and pre-registered (§2.3).

**On S3 I side with the stat skeptic on demotion and with the designer on existence.** The overlay survives because it is nearly free (~2–4 forced round-trips/yr, exec verdict MINOR) and the 5-day downgrade kernel survives cluster-robust inference. Everything built on 63-day CARs is demoted from binding rule to advisory/trial. The "no-adds book-wide on red scorecard" blast radius — a $300/yr overlay claiming authority to freeze a $100k book — is revoked.

**On S4 I side with the stat skeptic completely.** When the design's own benchmark-quality gate is applied to its own pilot, the funded configuration's net at its own cost assumption is −0.13bp/day, and 70% of the headline alpha came from one broken-mapping name that the design itself suspends. There is no funding case and no gauntlet toward one on this evidence. M4 — the fair-value execution filter both skeptics endorsed — is retained at $0 as part of the book's execution layer. The overshoot mechanism may return via S7 (W4/W5, respec'd to executable lags) once ETF history exceeds ~24 months and per-ETF true-benchmark mappings exist.

**On S5 I side with the stat skeptic's three fixes and add a ruling:** the mixed-lag re-run becomes the pre-live headline; a naive-baseline duel (21d/63d realized-vol targeting, 200dma, same EW index, same period) is a **binding gate** — and *whichever rule wins the duel goes live*. The book gets a cash dial either way; complexity must earn its keep or the simple rule serves. Stress-conditional costs (25–50bp on de-risk legs) and a crisis NAV-basis haircut go into the GFC/COVID payout sensitivity before anyone quotes maxDD numbers again.

**On S6 and S7 I side with the skeptics' fixes and keep both at $0.** They cost research time, produce calibration data and registered trials, and are the only mechanism by which this book can ever legitimately fund a tilt. S7's fix list is adopted wholesale; S6's gate arithmetic is repaired (Brier ≤0.24 for a calibrated forecaster means ≥60% hit rate — the EV table is redone at that bar).

**On S8 I keep the architecture (one net order file, precedence chain, EW-34 benchmark, breakers) and redraw everything quantitative.** Cash yield corrected to ~+0.1–0.25%/yr (IBKR pays zero on the first $10k — which is exactly the floor). Paper-fill "validation" is reclassified as plumbing-only; fill quality is validated with live micro-size orders. The 15:52 "human veto" on irrevocable 15:50 close orders is deleted (auto-transmit with a kill-switch before 15:49). Cost alarms bind at 1.2× tier budget, not 1.5×.

## 2.1 CORE — the book (90% / $90,000)

**What it is.** An equal-weight portfolio of the 34 US-listed country ETFs (EW-34: SPY, QQQ, IWM count as three US lines per the T2 universe definition), held at a 90% invested cap with a 10% hard cash floor, rebalanced monthly.

**Rules.**
- Rebalance once a month, scheduled inside the turn-of-month window ([-1,+3] business days) — this is simultaneously the live implementation of S7-W3's *re-timing* variant (the zero-incremental-cost version; the cash-deployment variant requires W3 to pass its registered trial first).
- One net order file per close on rebalance day: MOC for Tier A, LOC with band (reference = last trade at 15:45, band ±30bp calm / ±50–75bp on stress days) for Tier B/C, submitted 15:45 ET, auto-transmit, kill-switch cutoff 15:49. Whole shares only into closing auctions; fractional residues cleaned with SMART limit orders; no market orders, ever; no trading at the open.
- M4 fair-value filter governs timing: buys delayed up to 3 sessions when the ETF is ≥25bp rich to fair value; accelerated at discounts. Zero incremental turnover.
- $400 suppression band per position (no order below $400 of drift); positions ~$2.6k each at EW.
- S3 overlay edits target weights before order generation (§2.4); S5 dial multiplies the invested cap (§2.5). Precedence: **vetoes → dial (min of dial and drawdown breakers) → caps → EW targets → suppression band → M4 timing.**
- Caps retained from S8: 10% single ETF (binds only via overlays), 50% EM, 12% Tier-C aggregate, EDEN 2%.

**Cost budget.** ~12–25 orders/month-rebalance plus overlay/dial trades: ~150–350 orders/yr, ~$150–400/yr commissions+fees, blended one-way spread cost dominated by Tier-A names because monthly EW drift is small. Total expected cost drag ≈ 10–25bp/yr. Every order except EDEN is <0.35% of ADV — capacity is a non-issue at this size, permanently.

**Why EW-34 and not ACWI.** The question under test is cross-sectional country selection; ACWI is a US-beta bet. EW-34 is also the benchmark, which makes CORE the honest null: **if every overlay and every research program fails, the book converges to its own benchmark minus ~10–25bp of costs plus ~10–25bp of cash yield — approximately a wash.** That is the designed failure mode, and it is deliberate.

## 2.2 S1-Shadow — the combiner measurement program ($0)

**What changed from the design:** everything. No capital, no paper-toward-funding phase, no Mode-A intraday build. The FATAL findings are adopted as the program's task list:

1. **Fix the documentation to the true model** — the 6-feature daily ridge from `build_combiner.py` DAILY_FEATURES (including LL_LEADER_GAP_5D), not the dead 7-feature monthly table; persist daily ridge coefficients per vintage so kill gates have something real to monitor.
2. **Component-level ETF-capture decomposition** — measure per-component index-vs-ETF capture; test a combiner variant excluding or lagging LL_LEADER_GAP_5D (the mechanistic suspect for why ETF-space IC ≈ 0).
3. **Run NT-1 (Tier-A-only universe IC) and PL-2 (banded construction) on ETF returns**, with the skip-2 lag the pipeline actually delivers (combiner surfaces arrive T+2 as observed live on 2026-07-02).
4. **Accumulate ≥252 trading days of shadow ETF-based, top-5-expression IC** with autocorrelation-corrected standard errors (per-126d IC se ≈ 0.027, not 0.017), scored on the traded expression, not full-ranking IC.

**Re-entry gate (pre-registered):** shadow ETF-based top-5 IC ≥ +0.015 over ≥252td with corrected se, AND a measured (not assumed) tier-blend cost model showing positive net at the realized blend, AND banding gross-retention measured. Until all three: combiner ranks are context-tier only, book-wide.

## 2.3 S2 — the Slow Book revival gate ($0 at launch)

**What changed:** killed at launch because its own kill condition is currently true. Pre-registered revival gate, checked at each month-end from October 2026:

- **Gate R-A (recency):** trailing-252bd IC of the diffusion block (SIM_NBR_RET_GAP_63D + GRAPHP_BANK_NBR_RET_GAP_21D + GRAPHP_TWOHOP_TRADE_GAP_21D, at the 21d horizon) > 0 at **two consecutive month-ends**.
- **Gate R-B (composite):** SLOWBOOK_COMPOSITE_V1 registered and run through harness v2.1 (hold grid, breakeven, subperiod table), with a positive 2023+ subwindow — not just the full-sample row.
- **Gate R-C (mechanism memo):** a written diagnosis of the 2024–26 sign flip (crowding vs regime vs construction change in the nightly rebuilds). This memo is the single most valuable research deliverable in the program: it decides whether the house edge is cyclical or gone.
- **Gate R-D (exec fixes):** clip-size-correct cost table (~9–10.5bp one-way at $2.2k clips, incl. the $1 fractional minimum), Europe-name unfilled-order conversion at 11:15 ET (before home close) not 15:30, stress exit rule for veto-forced sells (cap 30bp shortfall, split across 2–3 sessions), consensus-vintage stamp contradiction resolved (spec SQL, implementation, and live run provably identical), Asia futures fair-value check replaced with a free proxy, whole-share odd lots below mega-tier.

If revived: fund at $20–25k carved from CORE, two staggered tranches, 21bd holds, top-8, exactly per the v1.1 spec as amended, expected net +0.1 to +1.0%/yr on the sleeve (the exec-corrected band, not the designer's +0.4 to +1.4). If Gate R-A has not passed by 2027-12, archive the family.

## 2.4 S3 — the Event Book overlay ($0, restructured)

**What changed (stat fixes 1–6 and exec fixes 1–7 adopted):**

- **V-DG (EM downgrade veto): binding window shortened from 63td to 21td** from the next-close anchor — the cluster-robust kernel (−0.9%@5d, cluster t ≈ −2.3) plus buffer. The 63d window is registered as a **trial** (EVT_SOV_RATING_CHG_63D), not a rule. High-VIX acceleration retained (exit next close) since damage front-loads.
- **V-CI (CDS inversion veto): demoted to advisory** pending (a) 2-day persistence or independent 1Y/5Y level confirmation for single-day flips (98 of 147 historical runs last one day; the France 2026-06-22 print is a plausible artifact), and (b) a re-run with sovereign dedup + cluster-robust inference. If the re-run clears |t|≥2, it re-promotes to binding at 21td.
- **H-UG (upgrade block): demoted to a 50% sizing haircut for 63td**, never a full add-block, never overriding a validated NW-t≥4 rank (evidence t ≈ −1.7 does not outrank evidence t 4.5). The upgrades-also-negative anomaly must be explained (EM-in-the-news base-rate drift vs real drift) via matched non-event baselines before either sign is treated as tradable.
- **Value restated with the cash-vs-universe benchmark correction:** normal-year expectation ≈ **0 to +15bp/yr** (insurance framing only); the "+150–400bp in a 2008-analog" claim is struck as circular (the estimate *is* 2008) and replaced with "in-sample worst case."
- **Blast radius capped:** a red governance scorecard freezes overlay *state changes* and adds in Tier-1-affected names only; book-wide freeze requires 2 consecutive red days + owner acknowledgment. The scorecard's trailing GREEN rate gets measured and published before launch.
- **Mechanics:** LOC band reference = last trade 15:45; unfilled forced-exit ladder (LOC → next-morning midpoint → marketable by 11:30); whole-share MOC + fractional cleanup; stress exits (tier-C-heavy veto targets: TUR/EZA/ECH historically dominate downgrades) costed at 2–4× calm spreads (30–80bp) and netted into the K-1 per-binding ledger; 12:30 ET re-compute on days the 08:00 pass saw stale inputs; multiple-testing charge (~30 cells) recorded in the ledger.
- **Kill criteria retained:** vetoed names' mean window return ≥0 after 12 bindings/24 months kills Tier 1; cumulative +1.5% opportunity cost kills earlier; dormancy review hard-dated 12 months post-launch.

**Live state at launch under the new rules (as of 2026-07-02):** EWW (Mexico) veto expires ~21td after its early-June anchor — i.e., roughly the first week of July rather than late September; EWQ (France inversion) advisory-only pending persistence confirmation; EZA (South Africa upgrade 07-01) 50% haircut on new buys, not a block; flow add-blocks (EIDO/EWI/THD) retained as zero-cost Tier-2 rules.

## 2.5 S5 — the Cash Dial ($0, gated multiplier)

**What changed (stat fixes 1–5, exec fixes 1–6 adopted, plus one synthesizer ruling):**

- **Pre-live gate 1 — the achievable backtest:** re-run the locked spec at mixed lag (VIX TS lag-1; HY OAS, MOVE, FX breadth lag-2 — what 15:40 ET actually knows). That number is the headline; uniform lag-1 (8.27%) is demoted to an upper bound. The active return's sign lives inside this gap (lag-1 +0.38%/yr vs lag-2 −0.24%/yr vs EW).
- **Pre-live gate 2 — the naive duel:** trailing 21d/63d realized-vol targeting and a 200dma rule on the same EW index, same 2006–2026 window, same stress-cost model. **The winner on maxDD-reduction-per-unit-of-ex-crisis-drag goes live.** The book gets a dial either way; the four-input Bloomberg-dependent version must beat a price-only rule to justify its fragility.
- **Stress-conditional costs:** 25–50bp one-way on score≥4 days (2–3× calm spreads), plus a crisis ETF/NAV-basis haircut sensitivity on the GFC/COVID payouts, before any maxDD claim is quoted.
- **Honest restatement:** ex-crisis drag −1.6%/yr **mean** (not the −1.2% median); payout hit rate **2 of 5** major drawdowns (GFC, COVID yes; 2011, 2022 no; China 2015–16 negative); protection is crash-type-conditional; N=2 on the payouts; backtest start masked until all z-windows have 252 obs; pre-Nov-2007 VIX3M backcast disclosed.
- **Operations:** per-component staleness degradation with a pre-specified partial-score map (the TS<0.92 hard trigger runs on free CBOE data and is **always** live, even in a full pipeline outage); fully scripted 15:40 → netted basket → submission by 15:48 (manual entry prohibited on state-change days); Tier B/C close bands widened to ±50–75bp on de-risk days with next-morning-midpoint fallback logged as lag-2; whole shares only; missed-operator day = lag-2 execution, logged; LULD Level-3 days = freeze one day.
- **Kill retained and central:** if the next ≥25% EW drawdown is not cut by ≥15% relative, the dial dies permanently. Plus: two consecutive years of >2.5% drag without a score≥4 episode triggers a spec review.

**States:** stress score 0–1 → 100% of the 90% invested cap; 2–3 → 70%; 4–5 → 50%; ≥6 → 30%. De-risk after 2 confirming days (1 on hard trigger); re-risk one step per 5 confirming days + 5-day dwell. All dial trades netted with the monthly rebalance where calendars collide.

## 2.6 S6 — Fable's Desk ($0 paper; Stage-1 $5k conditional, 2027 earliest)

**What changed (stat fixes 1–6, exec fixes 1–8 adopted):** Tier-2 confluence now requires **two mechanistically disjoint families** — the combiner may never pair with graph/twins/lead-lag as the second initiating vote (it *is* them, aggregated); Tier-1 event rationale re-based on the clustered re-runs — only the short-window downgrade kernel is citable evidence until the re-studies clear; the calibration gate is restated honestly (Brier ≤0.24 ⇒ ≥60% hit for a calibrated forecaster; the §3 EV table redone at that bar), with ≥40 closed paper theses or a binomial test (hit>50%, p<0.10) and K1 retries hard-capped at one; embargo windows aligned to the measured month-end anchors; sessions moved post-09:30 with T−2 data explicitly accepted at 5–63d horizons; whole-share sizing for auction orders; OCA-grouped stops/time-stops (no accidental shorts); the "−$3,000 lifetime" bound relabeled an expected demotion bound with a gap-risk stress line; high-basis names (ASHR) get index-mark invalidation, not ETF-price stops; per-trade cost re-based at the realistic ~20–30bp EM-heavy round-trip mix; the Avoid-List's consumer is now **named: CORE** (overlay §2.4 is the enforcement path), which converts its 0–15bp/yr from unrealizable to realized.

**Gate timeline restated honestly:** ~10–13 months of paper at 3 concurrent slots before Stage-1 eligibility. Year-1 expected P&L: $0 by construction.

## 2.7 S7 — the Wildcards research charter ($0 live; the alpha engine of record)

**What changed (stat fixes 1–7, exec fixes 1–8 adopted):** W6 respec'd (per-market event-study/time-series, never a 6-country CS rank into a min-10-coverage harness); **W3 pre-registers its implementation** — the re-timing variant is already live via CORE at ~0.1–0.3%/yr expected, the cash-deployment variant (~0.3–0.5%/yr gross of a 30% cash sleeve, net ~0.2–0.4%) requires its own trial and does not apply to 1d-hold sleeves; W1 (FX butterfly flip) carries a mandatory orthogonalization to own trailing 63d return — if the orthogonal IC t < 2 the verdict records "repackaged reversal"; W9 registers downgrades + inversions only (upgrades as diagnostic leg) with stressed-spread ablation; W2 at the 1m monthly-path horizon with the 2-month embargo verified through the backfill; W5 respec'd to the executable T+1 entry (or shelved until intraday capability exists); W8 registered at its live-achievable T+2 lag; W4's history recomputed read-only from `etf_prices_daily` (the stored table is a 1-day snapshot); paper graduates marked on **ETF closes**, never index returns; minimum clip $2,500 for fast graduates (max 3–5 names at $10–15k funding); no fractionals into auctions.

**Expectations restated at the per-mechanism base rate:** 2–4 WEAKs from 14–18 trials, ~15–20% per mechanism; sleeve kill extended to 0-for-12 (the 0-for-8 rule carried a ~20% false-suspension risk). Test-first queue: **W3, W2, W1** (three unrelated families, 20+ years PIT-clean history, one research-week combined).

**Graduation path (the only route to new funded capital in this book):** WEAK+ verdict with breakeven ≥10bp, FF-spanning alpha t≥2, ETF-capture re-test ≥0.5, then a 60-day ETF-marked paper thesis, then a separate PRD — fundable at ≤$15k carved from CORE, max 2 concurrent graduates.

## 2.8 Final capital allocation

| Sleeve | Capital | Status |
|---|---|---|
| CORE EW-34 carrier | **$90,000** | Live from P0 (60%) → P1 (90%) |
| Cash floor | **$10,000** | Structural (earns ~0 at IBKR; yield accrues only on cash above it in de-risk states) |
| S3 Event overlay | $0 | Live P1, governs CORE weights (restructured rules) |
| S5 Cash dial | $0 | Live P2 after gates; multiplies CORE invested cap |
| M4 execution filter | $0 | Live P0, book-wide |
| S1 Combiner | $0 | KILLED → shadow measurement; re-entry gate §2.2 |
| S2 Slow book | $0 | KILLED at launch → revival gate §2.3 (first check Oct 2026) |
| S4 Microstructure | $0 | KILLED; mechanism may return via S7 W4/W5 |
| S6 Desk | $0 paper | Stage-1 $5k possible 2027, carved from CORE |
| S7 Wildcards | $0 | Graduates ≤$15k each, max 2, carved from CORE |

Every dollar of future tilt capital is carved from CORE through a pre-registered gate. Nothing is funded on designer arithmetic again.

## 2.9 Expected net book performance (12-month forward, honest derivation)

Benchmark: EW-34 fully invested, historical ~7.7–7.9%/yr, vol ~15.5%, maxDD −59% (2008). Convention: Sharpe quoted rf=0 to match the miner artifacts; cash assumed ~3.4–3.9% on balances above the $10k zero band.

Derivation of the base case: CORE at 90% invested captures 0.90 × EW return; the 10% floor costs ~70–80bp/yr in an average up-year, partially offset by cash yield above the floor (+5–15bp state-weighted), execution/calendar layer (+10–40bp), avoidance (0–15bp), dial ≈ wash ex-crisis with −0.3 to −1.0% drag in whipsaw years, total costs −10 to −25bp.

| Scenario | Total return | Active vs EW-34 | Notes |
|---|---|---|---|
| **Conservative** | ~4.5–6.0% | −1.5 to −0.5% | Dial premium year (2007/2019/2025-type whipsaws), W3 fails, no events to dodge, EW itself mediocre |
| **Base** | ~7.0–7.8% | −0.4 to +0.3% | Overlays roughly pay for the cash floor; risk-adjusted better than EW (vol ~13–14%, Sharpe ~0.55–0.60 vs ~0.50) |
| **Optimistic** | ~8.5–9.5% | +0.5 to +1.2% | W3 replicates at half strength incl. cash-deployment variant, one S7 graduate funded mid-year, downgrade-cluster year makes avoidance pay, S2 revives in Q4 |
| **Crash year (GFC/COVID-class)** | — | maxDD ~−25 to −35% vs −45 to −59% unprotected | Conditional on crash-type; 2-of-5 historical hit rate; stress-cost haircut applied |

**Stated plainly: in expectation this book approximately matches its benchmark in total return while cutting volatility and tail risk, and buys a research pipeline that may later justify real tilts. It is a validation vehicle and an insurance structure, not a return engine. It does not scale to, and does not pretend to inform, the owner's real $33–40M book except through what its research program learns.**

## 2.10 Unified operations calendar

**Daily (≤10 min, mostly automated):**
- 08:00 ET — pipeline/scorecard check; S3 overlay recompute (12:30 re-pass if morning inputs were stale); log gate-failure days as first-class data.
- 15:40 ET — dial script (auto): score → netted basket → auto-transmit 15:45–15:48, kill-switch by 15:49. Human involvement only on state-change alerts. Missed day = lag-2, logged.

**Weekly (Monday, ~60–90 min):**
- S6 desk session (post-09:30, on T−2 surfaces, acknowledged).
- S7: ≤1 registration/week; review running trials.
- Dashboard: realized costs vs tier budget (1.2× alarm), overlay states, dial state log, shadow-combiner IC accrual.

**Monthly:**
- Turn-of-month window — CORE rebalance day: one net order file (~12–25 orders), M4 timing filter, whole shares, MOC/LOC at 15:45.
- Month-end: S2 revival Gate R-A check; cost ledger close; paper-thesis marks.

**Quarterly:** event-study refresh (clustered inference, dedup); S1-shadow report; kill-criteria review; tier-composition and spread-tier re-measure.

**Annual load:** ~150–350 orders, ~$150–400 commissions/fees, one operator + AI, with a written absence protocol: **no new orders, holdings ride, dial falls back to lag-2.**

## 2.11 Phase-in

**P0 — Jul–Sep 2026 (build + paper + live plumbing):**
- CORE live at 60% ($60k), 40% cash; M4 live. Purpose: real fills, not simulator fills.
- Live micro-size order-type validation: 1-share/one-clip live orders across every tier and order type (MOC, banded LOC, midpoint peg) — paper simulators auto-pass fill-fidelity tests and are used for workflow only.
- Execute the mandatory re-runs: S5 mixed-lag + naive duel + stress costs; S3 clustered/dedup event re-studies; S6/S7 registrations filed (W3, W2, W1 first); live_signals registry reconciliation (hard blocker, carried over from every sleeve).
- Exit criteria: 20 consecutive clean pipeline days; realized micro-order costs within 1.2× tier budgets; re-runs published.

**P1 — Oct–Dec 2026:** CORE to 90%; S3 restructured overlay live; first S2 revival gate checks; dial paper-final (state-logging live); S1-shadow accrual begins formally.

**P2 — Jan–Mar 2027:** dial (or its naive-duel winner) live; S6 Stage-1 eligibility window opens (if the 40-thesis/binomial bar is somehow met early — unlikely before mid-2027); first S7 graduate eligible for ETF-marked paper.

**P3 — Apr 2027+:** steady state. Graduates fundable ≤$15k each (max 2). S2 revival and S1 re-entry only through their gates. Program review at 12 months: if no graduate, no revival, and the dial lost its duel, the book formally becomes "EW + insurance + research" and is re-chartered or wound down to a passive EW holding.

## 2.12 Book-level monitoring and kill criteria

**The statistical honesty clause (adopted from the S8 stat critique, fix #4):** at ~2–4% tracking error vs EW, a ±0.5%/yr active claim needs decades to verify; **therefore live gates are process and cost gates, not alpha gates.** What CAN be verified in 12 months and is: realized execution cost vs tier budget (≥20 fills per tier), pipeline gate-failure rate, the avoidance ledger event-by-event (realized exit cost netted against avoided CAR), dial state fidelity vs spec, paper Brier scores, and shadow-IC accrual with corrected standard errors. Alpha verification lives in the harness and the shadow programs, on their own clocks.

**Program-level kills (any one triggers a full halt and owner review):**
1. −20% absolute drawdown from high-water mark.
2. Discovery of any lookahead variable in any live input (immediate freeze + audit; forward-return variables 1MRet/3MRet/6MRet/12MRet and daily analogs remain hard-blacklisted).
3. Realized blended cost >1.2× tier budget for 2 consecutive months → automatic fallback to quarterly-rebalance-only mode; >1.5× → halt.
4. Governance scorecard non-GREEN >5 consecutive business days → no new orders anywhere (holdings ride).
5. Dial payout-failure: next ≥25% EW drawdown not cut ≥15% relative → dial dies permanently (book reverts to static 90/10).
6. Avoidance failure: vetoed names' mean window return ≥0 after 12 bindings → Tier-1 demoted to advisory.
7. Two failed S7 graduate paper phases consecutively → graduation bar raised (capture ≥0.6, breakeven ≥12bp) before the next attempt.

---

# PART 3 — RISK STATEMENT (frank)

**The three most likely ways this program underperforms cash:**

**1. Beta, not process.** The book is ~85–90% long global equities with no shorts, no derivatives, and cash as the only hedge. At cash yields of ~3.4–3.9%, any 12-month window in which the EW-34 country universe returns less than ~4% puts this book under cash **regardless of every overlay, gate, and kill criterion in this document.** Historically that is roughly one year in three. The entire engineered layer is worth ±1%/yr against an equity distribution whose annual swing is ±20%. Nothing in the warehouse changes this; only the dial softens it, and only in 2-of-5 crash shapes.

**2. Insurance premium without payout.** The dial (or its naive replacement) drags a mean −1.6%/yr in ex-crisis years and pays off only in fast, vol-signaled crashes. A decade like 2011–2021 — grinds, whipsaws, one crash the dial half-catches — is a realistic path where the book pays ~1%/yr of premium, collects little, and compounds below both EW and (in flat markets) cash. The 2007/2019/2025 whipsaw years (−3.7 to −6.9% premium) are the template. The payout-failure kill bounds this at one missed crash, but one missed crash plus years of premium is already material underperformance.

**3. Death by a thousand operational cuts.** ~$300–700/yr of commissions, fees, and market data; forced exits at 2–4× calm spreads exactly when vetoes and the dial fire; T+2 pipeline staleness turning designed edges into lagged ones (observed live: the combiner's surfaces were T+2 on the very day this program was designed); gate-failure days desynchronizing the rebalance machine; a single operator with a hard 15:40 ET daily dependency. Against a central active expectation under +$700/yr, ordinary friction — not any signal being wrong — is fully capable of putting the active line negative for years. The book's tiny order flow is its main defense; the 1.2× cost alarm and quarterly-fallback rule are the backstop.

**The single biggest unknown:** **whether any of the index-space diffusion edge survives at the US-listed ETF close.** Everything the warehouse most genuinely "knows" that prices might not — the combiner at IC 0.057/NW-t 10.7, the PIT graph family, the twins — lives in local-index space. The only direct ETF-space measurement (13 months) reads approximately zero, and the components' own index-space ICs have been wrong-way since early 2024. Two interpretations fit the data: (a) the 2024–26 flip is cyclical crowding that mean-reverts, ETF capture at slow holds is real (~0.6–0.75), and the S2 revival gate opens within a year — in which case the fundable edge roughly triples and this book becomes an alpha book; or (b) the edge was always a local-hours phenomenon that US-hours market makers embed and costs consume, and the flip is the sound of it being arbitraged away — in which case this book is permanently an equal-weight carrier with insurance and a well-run lab. The S1-shadow program and the S2 revival gates exist to answer that question with measurements instead of hope, on a ~12–18 month clock. That answer — not anything currently funded — determines whether this program deserves to exist past 2027.

---

*End of integrated draft. Source designs: design_S1…S8 in this directory; skeptic critiques embedded in the program record; miner reports mine_ledger/mine_livedb/mine_docs/mine_exec/mine_lit/mine_math. All database claims trace to read-only queries against the main warehouse and loop DB as of 2026-07-02.*
