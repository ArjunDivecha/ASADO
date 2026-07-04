# S8 — THE ARCHITECT: One $100k Account, All Sleeves Integrated

**Program:** ASADO Alpha Book, phase 2 (strategy design) | **Date:** 2026-07-02 (rev 2 — reconciled against the final S1–S7 documents on disk) | **Status:** design only — hypothetical account, no live trading
**Constraint set:** long-only + cash, no shorts/leverage/derivatives, 34 US-listed country ETFs, $100,000 IBKR account.

**Evidence inputs (all in this directory):** `mine_ledger.md` (trial census, hypothesis IDs), `mine_livedb.md` (live loop-DB state, freshness), `mine_docs.md` (detectors, governance), `mine_exec.md` (IBKR cost tiers), `mine_lit.md` (outside corroboration), `mine_math.md` + `mine_math_results.json` (ground-truth return math). **All seven sibling sleeve designs read in full and reconciled:** `design_S1-flagship-combiner.md`, `design_S2-slow-graph-book.md`, `design_S3-event-overlay.md`, `design_S4-microstructure.md`, `design_S5-regime-cash.md`, `design_S6-fable-desk.md`, `design_S7-wildcards.md`. Databases referenced (read-only): `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb`, `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb`.

**Sleeve roster (as actually designed by the siblings):** S1 = fast combiner tilt (`combiner_scores_daily`, banded top-5, h=5); S2 = slow composite (twins + PIT graph + 2s10s + reflation, 2 monthly tranches); S3 = event overlay (vetoes/haircuts/execution rules, $0 capital); S4 = microstructure book (M1 overshoot fade, M3 passive-bid harvest, M4 execution filter); S5 = **the cash dial** (a whole-book regime multiplier 100%→30%, $0 capital); S6 = Fable's Desk (staged discretionary, $0 until calibration gate); S7 = wildcards ($0 by charter). S3 and S5 are overlays, not capital sleeves. S7 gets zero.

---

## 1. Thesis — what the account as a whole monetizes

The warehouse knows one big thing the ETF prices don't fully carry: **cross-country return diffusion** — information that has already appeared in a country's *neighbors* (trade partners, bank creditors, fundamental twins) but not yet in the country's own price. Measured four ways (graph spillover, twins, lead-lag, the ridge combiner), all WEAK-verdicted but multi-spec, PIT-confirmed, positive in both sample halves (mine_ledger). It knows three smaller things: **slow sovereign-curve and reflation information** (S2's C4/C5); **event drift after sovereign credit actions** (EM downgrades −0.9%@5d/−2.8%@63d, CDS inversions −4.5%@63d, upgrades −2.4%@63d — purely *avoidance-shaped* for a long-only book, owned by S3); and — new since the first draft, with S4's pilot evidence — **the ETF's own microstructure**: US-hours prices over-embed the S&P move in closed-home-market names and revert (Levy–Lieberman, reproduced live: +7.7 bp/day gross at h=2, t=2.3, 13 months), plus a mean-reverting premium/discount band that a $2.5k resting limit order can harvest but no institution can arb. Finally it knows **when to be small**: VIX-term-structure backwardation with credit confirmation identifies the crash regimes in which a long-only book's conditional Sharpe is negative (S5's dial: maxDD −58.9%→−46.7% measured, at ~zero cost over the cycle).

Why the edges persist: country-level anomalies are the one place post-publication decay is weak (Jacobs & Müller 2020) — the marginal holders of EIDO/EPOL/EWZ are retail allocators and benchmark-driven institutions who reprice a country only on its own headlines; the natural arbitrageurs trade liquid futures, not 34 ETF wrappers; the negative-drift events are protected by exactly the friction a long-only book doesn't pay (expensive EM shorting); and the microstructure band exists because creation/redemption costs exceed the mispricing for institutions but not for a patient retail limit order.

The architect's own thesis, on top: **most of the measured alpha is destroyed by costs and by US-hours price embedding** (ETF capture 0.36 at h=1, 0.60 at h=5 — mine_math §3c; nothing survives 25 bp one-way). The account is therefore designed around the five things that survive contact: (i) weekly-or-slower pacing in cheap tickers for the diffusion alpha, (ii) same-close execution for the one fast edge that genuinely lives at the close (S4-M1), (iii) turnover discipline via netting and rank buffers, (iv) event avoidance as free insurance, (v) cash — floor, dial, and breakers — as the only hedge. At $100k the realistic steady-state net active vs equal-weight is roughly **+$500–2,500/yr, central ~+$1,300**; the honest primary products are drawdown control, a validated operating system, and the forward verification record that would justify scaling.

---

## 2. Capital allocation — what each sleeve asked, what the account grants

The sibling asks sum to ~$140k of capital plus two overlays against a $100k account (S1 asked 60%, S2 asked 35%, S4 asked 20%, S6's ladder tops at 20%, S3 reserved 5%). Arbitration is therefore the architect's first job.

| Sleeve | Identity | Signal surface (loop DB) | Cadence | Asked | **Granted (steady state P3)** | Type |
|---|---|---|---|---|---|---|
| **CORE** | Benchmark carrier (architect's own, §3.0) | none (EW-lite) | monthly | — | **17.5% ($17.5k)** — the donor pool for S6 Stage-2 and S4 escalation | ballast |
| **S1** | Fast Combiner (`design_S1`) | `combiner_scores_daily` / `family_ranks_daily` (validated 29-country ranks) | daily 1/5 roll, h=5, banded | 60% | **25% ($25k)**; hard-capped **15%** until Mode-A same-close execution is validated (§2.1, §3.1) | capital |
| **S2** | Slow Book (`design_S2`) | `similarity_features_daily`, `graph_features_pit_daily`, `sovereign_signals`, `consensus_signals`, `eco_surprise_signals` | 2 monthly tranches (1st + 11th bd) | $35k (30–40% band) | **30% ($30k)** — low end of band (§2.2) | capital |
| **S3** | Event Book overlay (`design_S3`) | `sov_rating_changes`, `sovereign_signals`, `etf_flow_signals`, `forward_calendar`, `dislocation_daily` | daily 08:00 recompute; Tier-1 binds ~2×/yr | $0 + $5k gated E-R | **$0 capital; governs 100% of the book.** E-R honored at $5k, gated on E-1…E-4, scope-limited (§3.3) | overlay |
| **S4** | Microstructure Book (`design_S4`) | intraday residual vs `t2_levels_daily` home closes; `price_state_daily` D9 gap; `etf_prices_daily` | M1 daily same-close h=2; M3 event-driven | $20k (self-gated at $0 until G1–G3) | **0% at launch → 12.5% ($12.5k: M1 $10k + M3 $2.5k) after its gates; escalation path to $20k (§2.3)** | gated capital |
| **S5** | Cash Dial (`design_S5`) | `market_implied_signals` (VIX TS, HY OAS z, MOVE z, FX-vol breadth) | daily 15:40 compute; ~1.8 de-risk episodes/yr | $0 (multiplier) | **$0 — the book-level invested-fraction governor** (§3.5) | overlay |
| **S6** | Fable's Desk (`design_S6`) | thesis ledger + calibration machinery | 0–3 trades/wk when funded | ladder $0→$5k→$20k | **ladder honored; Stage 2 capped at $10k in year 1** (§2.4) | gated capital |
| **S7** | Wildcards (`design_S7`) | 12 registered-trial specs | research | $0 by charter | **$0** — research budget only (§2.5) | zero-funded |
| **Cash** | IBKR idle cash | — | — | — | **10% hard floor; more whenever the dial or vetoes say so** | reserve |

Maximum-build ledger: CORE 17.5 + S1 25 + S2 30 + S4 12.5 + S6 5 (Stage 1) = 90% invested cap, cash floor 10%. **Donor rules:** S6 Stage-2 increment (+$5k under the year-1 cap) comes from CORE (→12.5%); S4's escalation to its full $20k ask (post-WATCH verdict, §2.3) comes from CORE down to a 10% CORE floor, then from S1 — never from the cash floor. Launch-state allocations are much smaller (§13).

### 2.1 Arbitration: S1 asked 60%, granted 25% (15% until Mode A)

S1's own document nominates itself "the largest single sleeve" at 60%. Granted 25% because: (a) **in-sample ceiling** — its components were selected 2026-06 by the same harness that scores them; forward verification is zero (S1's own §5 risk #1); 60% of the account on an unverified ML composite inverts the ledger's honest census (~4 independent mechanisms from 59 trials — the book should spread across all four, not triple-weight the newest); (b) **mechanism concentration** — S1 and S2's C1–C3 are the same diffusion idea; at 25+30 the account already has 55% on one mechanism (risk #2, §10); (c) **the marginal dollar is cheap** — S1's own arithmetic puts net active at +0.5 to +2.8%/yr of NAV *at the 60–70% config*; the incremental 35% of NAV buys a few hundred dollars a year of expected alpha while concentrating model risk. The **15% cap until Mode A** (S1's 15:30 intraday re-score) is the architect's tradability discipline: S1's h=5 economics were measured on same-close execution; launch default is Mode B (T+1 scores), whose index-based gross drops 12.9→8.1%/yr and whose ETF-space degradation is *unmeasured* (S1 §2.4). Capital follows measurement: 15% on Mode B, 25% only after Mode A is built and paper-validated per S1's own P-mode gate. S1 remains, correctly, the largest *alpha* sleeve.

**Architect delta — S1's internal 30% structural cash is superseded.** S1 designed a fixed 70/30 sleeve (justified by mine_math's 70/30 dial cutting maxDD a third at flat Sharpe). The account now has a *measured, signal-based* version of that same dial book-wide (S5) plus a P&L breaker ladder (§4). Three stacked de-risking layers would compound multiplicatively (dial 0.7 × sleeve step-down 0.5 × breaker cap) and leave the book un-invested and unmeasurable. The account runs **exactly two invested-fraction mechanisms — the S5 dial (ex-ante, stress-signal) and the §4 breakers (ex-post, loss-based)** — and every capital sleeve deploys its grant fully invested subject to them. Sleeve-internal *signal-driven* cash (S2's unfilled-slot rule, S3-freed weight, S4's calm-day 75% sizing) survives; sleeve-internal *fixed or drawdown-triggered* invested-fraction rules (S1 §2.7's 30% + step-down) are superseded. S1's IC/cost/capture kill criteria (L1–L6) are untouched.

### 2.2 Arbitration: S2 asked $35k, granted $30k

Inside S2's own 30–40% band, so no spec conflict. Low end because 65% of S2's composite weight is the same diffusion mechanism S1 monetizes, and S2's own expectation is +0.4–1.4%/yr on the sleeve — the marginal $5k buys ~$20–70/yr while adding to mechanism concentration. S2's V1–V3 vetoes are superseded by the account-level S3 overlay (identical rules, one implementation); S2's optional V1.1 combiner-at-21d variant stays **off** — its own diversification argument ("the book that survives if the combiner ceiling collapses") is adopted as account policy; its C4 (2s10s) is contingent on the 21d re-registration (§12).

### 2.3 Arbitration: S4 asked $20k, granted $12.5k post-gates, escalation path to $20k

S4 is the account's only genuinely *new* mechanism (instrument microstructure, uncorrelated with diffusion) and the only sleeve whose fast edge is measured to live at the close it trades. But its evidence is a 13-month pilot at t≈2.3 — **below the harness WATCH gate (2.5)** — with ~15 design variants burned, and S4 itself sets a three-gate gauntlet (G1 full-history rebuild on adjusted closes at NW-t ≥ 2.5, G2 harness WATCH verdict, G3 60-day paper) before any dollar. The architect honors the gauntlet and grants, on passage: **M1 $10k** (two $5k tranches, $1k clips — not the asked $15k, and deliberately not less: below ~$1k/clip the $0.35 commission alone is ≥4 bp and breaks M1's +1.8 bp/day net margin at 8 bp costs; a "half-size ramp" is therefore rejected as economically incoherent — S4 goes live at $10k M1 or not at all) and **M3 $2.5k** (one resting order, not two, until 20 fills of adverse-selection statistics exist — S4's own guard). **Escalation to the full $20k ask** requires 6 months live meeting S4's own kill table plus a WATCH-or-better verdict on the overshoot-residual registration (§12), funded from CORE. **M4 (the premium/discount execution filter) is adopted immediately, book-wide, at $0** — it re-times trades the book already makes, needs no validation to start logging its counterfactual value-add, and becomes the account's execution layer (§5, §3.4). S4's M2 (D9 conditioning) rides along at $0.

### 2.4 Arbitration: S6's Stage 2 is $10k in year 1, not $20k

Ladder accepted exactly as designed through Stage 1 ($5k probation). Stage-2 ask ($20k, per-trade $10k) capped at $10k (per-trade $5k) for the first 12 funded months: the desk's K3 kill floor is −$2,000 cumulative regardless of stage — at $20k that is only a 10% sleeve drawdown between funding and permanent kill, one bad clustered cohort; and the desk's edge is *conditional on demonstrated calibration* (its own words) with a live record of exactly 3 paper theses, 2 under water. After the 12-month funded review (S6's K4) passes, the full $20k unlocks from CORE.

### 2.5 Why S7 gets zero (and stays zero)

By its own charter — no capital until an idea clears WATCH or a pre-registered event-study base rate, then paper, then a separate PRD. Two integrations: (i) S7's **W3 turn-of-month** (CAL_ family; falsification pre-declared: in−out window difference < +5 bp/day or t < 2.0 → DEAD), if validated, becomes a *scheduling amendment* to §7 — monthly legs migrate to just before the [-1,+3] window, de-risking prefers mid-month; capital-free basis points, no new sleeve. (ii) S7's W4/W5 share the `etf_basis` family with S4's registrations and S3's E-3 — the architect's family-coordination directive in §12 prevents three documents from creating three families for one mechanism.

---

## 3. Binding specs and integration contracts per sleeve

Sibling documents own their internal rules; this section states only the architect-level deltas and the contract each sleeve must satisfy to plug in. A competent engineer implements sleeves from the sibling docs and the account from this one.

### 3.0 CORE — the benchmark carrier (architect's own)

- **Holdings:** equal weight across the 28 Tier A + Tier B names (mine_exec tiers). The 6 Tier-C names (ECH TUR THD EPHE EDEN EZA) are excluded from CORE on cost — their EW exposure is delegated to S2, the only sleeve whose 21d holds amortize 20 bp to ~1 bp/day.
- **Screens:** (1) S3 Tier-1 vetoes and Tier-2 add-blocks/haircuts apply in full; (2) **bottom-5 exclusion:** any name in the validated combiner bottom-8 for ≥15 of the last 21 sessions is dropped at the monthly rebalance (a slow, persistence-filtered use of the strongest validated ranking; on 2026-06-30 data this excludes EWN and EWL/EWD-class persisters). *Labeled assumption* — not harness-tested as a portfolio rule; carries its own kill row (§11).
- **Rebalance:** monthly, 1st business day (same tape as S2 tranche A — netting shares costs), suppression band per §5. Clips ~$600–650/name at 17.5%; fractional shares mandatory (SPY ~$745, QQQ ~$713).
- **Expected active:** ≈0 vs EW-34 by construction (±0.1–0.3% from the Tier-C exclusion and screens). Its job is beta: without it, tracking error to the benchmark would be dominated by cash drag and tilt concentration.

### 3.1 S1 — Fast Combiner (25%; 15% until Mode A)

Adopted as designed (`design_S1` §2: validated 29-country ranks from `family_ranks_daily`, EDEN excluded, banded top-5 with tier-aware entry/exit ranks and residence minima, h=5 rolling tranches, MOC/LOC at the close, downgrade-exclusion eligibility overlay, staleness + governance gates). Architect deltas: (i) capital per §2.1 — grant deploys fully invested, internal 70/30 superseded; (ii) S1's downgrade-exclusion overlay (§2.6.3) is implemented via the account-level S3 overlay, not separately — one veto engine; (iii) S1's Tier-C participation stands as specced (bands entry ≤3, exit >14, 15d residence) but counts against the Tier-C aggregate cap (§4); (iv) the S1-L contingency (Tier-A-only on 2 months of blended cost >7 bp) is honored and pre-approved — no review needed to trigger it; (v) PL-2 (banding backtest) and NT-1/NT-2 registrations are pre-live blockers (§12).

### 3.2 S2 — Slow Book (30%)

Adopted as designed: composite 0.30·twins + 0.20·bank-gap + 0.15·twohop + 0.15·2s10s + 0.20·reflation; two $15k tranches (1st/11th bd); top-8 per tranche (~$1,875/slot), rank-12 buffer; full 34-name universe incl. Tier C; EDEN worked-orders-only; 10:15–11:30 ET execution; freshness gates. Architect deltas: (i) $30k per §2.2; (ii) V1–V3 delegated to S3; (iii) its Asia futures-fair-value check is delegated to the M4 execution layer (one implementation; stricter threshold wins); (iv) C4 contingent on §12 R1 — on failure, weight redistributes per S2's own renormalization.

### 3.3 S3 — Event Book overlay ($0 capital, governs everything)

Adopted as designed and promoted to **account law**: every sleeve's targets pass through `w_final = ExecutionRules(Haircuts(Vetoes(w_pre)))`.

- **Tier 1 binding vetoes:** V-DG (EM downgrade, month-start anchor + 63 td, high-VIX acceleration), V-CI (CDS inversion onset + 63 td, with the mandatory data-sanity gate — the Spain −1013 bp artifact is known), V-EXP (no special re-entry trades). Live state 2026-07-02: **EWW vetoed** (Mexico Moody's, expiry ≈2026-09-29) and **EWQ vetoed** (France CDS inversion 06-22, expiry ≈2026-09-21).
- **Tier 2:** upgrade add-block (**EZA live**, Fitch 07-01, through ≈09-30 — binding directly against South Africa's #3 bank-gap rank, which is the overlay doing its job); extreme-inflow add-block (EIDO +3.14z, EWI, THD live); cold-print ×0.5 haircut (Germany/Netherlands live; France moot under its veto).
- **Tier 3 advisory (X-CAL, X-BASIS, X-STRESS):** administered **inside the M4 execution layer** (§3.4) so exactly one place decides order timing. X-BASIS and M4's premium/discount filter are one implementation (both are "don't buy rich vs fair value"); the stricter of the two thresholds binds; every delay logs its counterfactual price.
- **Freed weight goes to cash, never redistributed** (S3's rule, adopted verbatim). Note the deliberate asymmetry with cap-clipping in §5.
- **Fail-safe adopted book-wide:** scorecard not GREEN or nightly loop missing → existing vetoes persist, **no new adds anywhere in the book**.
- **E-R reserve ($5k, gated on E-1…E-4): scope-limited by the architect.** Basis-reversion trades are owned by S4-M3 (single owner per trade type — E-3 gates M3's value claims, not a second basis book); E-R may deploy only into E-2/E-4/E-5-class event reactions after their verdicts.
- Expected value: ≈ +0.3–0.5%/yr normal years, +1.5–4% in stress years, ≈ −5 bp/yr running (S3 §3.3, overlap-haircut applied).

### 3.4 S4 — Microstructure Book (0% → 12.5%, gated; M4 live at $0 from day 1)

Adopted as designed (`design_S4`): M1 overshoot-fade — 21 foreign Tier-A/B names, 15:40 ET residual vs home close + fair S&P beta, top-5, h=2 tranches, storm-day full-size/calm-day 75%, MOC/LOC same close, dividend guard, per-country calendar checks (FAIL IS FAIL — a missing home close drops the name, never ffills); M3 passive-bid harvest — Tier C only, D9 gap_z ≥ +2 triggers a next-morning resting limit at min(bid, FV − half-spread), no chasing; M4 — the book-wide fair-value filter. Architect deltas: (i) capital and clip arithmetic per §2.3; (ii) **M4 is the account's execution layer** — every sleeve's order generator calls it (input: ticker/side/size/urgency → output: execute now / midpoint peg / delay / substitute-alternate), and it administers S3's Tier-3 timing rules; M1's same-close trades are exempt from M4 delays (their alpha decays faster than the premium — S4's own rule); (iii) M1 turnover counts in the fast-turnover budget (§4); (iv) the adjusted-price history collector G1 requires is an **owner-approved pipeline change** — not something this program does itself — and is a hard gate.

### 3.5 S5 — the Cash Dial ($0, multiplies the whole book)

Adopted as designed (`design_S5`): stress score S(t) ∈ {0..8} from VIX term ratio, HY OAS z, MOVE z, FX-impvol breadth (all in `market_implied_signals`); states 100/70/50/30%; fast-down (2-day confirm, 1-day on hard trigger) / slow-stepped-up (5-day confirm, one step, ≥5d dwell); 15:40 ET compute; freeze-on-stale with manual CBOE fallback; advisory inputs (D10, dislocation breadth, predmkt, regime tag, JST) displayed never traded. Measured: +0.4%/yr net lag-1, Sharpe 0.56→0.69, maxDD −58.9%→−46.7%, 10 of 38 episodes profitable, all cumulative gain from 2008+2020, cost ~$101/yr. It is insurance, not alpha — adopted on exactly those terms.

Architect integration contract:
1. **The dial multiplies the invested cap:** target invested fraction = dial_state × 90%. At state 1.00 the book is ≤90% invested (10% floor); at 0.30 it is ≤27% invested. Sleeve grants are *relative weights on the invested fraction* (S5's own contract §8).
2. **Interaction with breakers:** effective invested cap = **min(dial-implied, breaker-implied)** (§4). The dial is ex-ante (stress signals); breakers are ex-post (realized loss); both mechanical; no double-count beyond the min.
3. **Netting:** dial-state changes execute on the same close as sleeve trades — final target shares computed ONCE (sleeve weights × dial × caps), one net order per ticker (S5's rule, and §5's).
4. **Vetoes survive re-risking:** the dial never forces buying an S3-flagged name; re-risk steps redistribute pro-rata across unflagged names (S5's own rule).
5. **Governance:** the dial goes live only after its `DIAL_STRESS_SCORE` registration (event-study path, `risk_timing` family) and its 6-month paper log (§12, §13). Its whipsaw/premium/payout kill rules (§11) are honored verbatim. Current live state: score 0 → 100% (2026-07-02).

### 3.6 S6 — Fable's Desk (ladder honored, §2.4 cap)

Adopted as designed (evidence tiers, 12-item checklist, stage gates, blotter, dual-mark phantom-alpha audit). Architect deltas: (i) desk trades route through §5 netting and the M4 execution layer like everyone else's; (ii) the desk's Avoid List is advisory to other sleeves — only S3 vetoes bind; (iii) desk positions count against all §4 caps (the desk's own 15%-per-country combined cap is *tighter* than the account's 10% single-ETF cap in name terms — the account cap binds first; the desk inherits it); (iv) funding: Stage 1 from cash above the floor, Stage-2 increment from CORE; (v) the desk's Tier-1 event triggers use the same S3 veto engine outputs — one event scanner, two consumers.

---

## 4. Account-level risk budget

| Limit | Value | Rationale |
|---|---|---|
| Invested cap (structural) | **90% of NAV** × dial state | 10% hard cash floor; first $10k earns nothing at IBKR anyway |
| Target book vol (trailing 63d, ann.) | **11–13%** | ~82% average invested (0.90 × dial avg 0.913) on EW vol 15.3–15.7% (mine_math §1, s5 results) |
| Max single ETF (all sleeves + CORE) | **10% NAV** (SPY alone 12%) | caps the pile-on when families agree (Indonesia today: combiner #1, twins #1, S3 inflow block already binding) |
| Max China complex (ASHR+MCHI) | 12% | one economy, two wrappers |
| Max US complex (SPY+QQQ+IWM) | 25% | one economy, three slices |
| Max EM aggregate | **50% NAV** | EM = BR CL CN(A/H) IN ID KR MY MX PH PL SA ZA TW TH TR VN |
| Max Tier C aggregate | 12% NAV; S2 tranches + S1's residence-gated entries + M3 only | 20 bp names live only in ≥15–21d holds or passive fills (cost law) |
| EDEN | max 2% NAV; S2 only, monthly-or-slower, worked orders | $0.8M/day ADV — the universe's one capacity constraint; excluded from S1 (its own rule) and M1 |
| Fast-turnover budget (S1 + S4-M1) | one-way ≤ **0.12/day of NAV** | measured design point ≈0.074 (S1 25%×0.148 + M1 10%×0.367); headroom 1.6× |
| Vol brake | trailing 21d book vol > 18% → cut invested cap 15 ppt | mechanical, pre-registered; stacks with dial via min() |

**Drawdown circuit breakers** (book NAV vs high-water mark, daily at the close; effective invested cap = min(dial, breaker)):

| Trigger | Action |
|---|---|
| −8% | Alert; no new risk beyond scheduled rolls |
| −10% | Invested cap 60%; S1 halved; raise cash from lowest-composite-rank names |
| −15% | Invested cap 40%; S1/S4-M1 suspended (roll off, no new buys); CORE+S2 remainder + cash only |
| −20% | 100% cash; **program shutdown review** (§11) |
| Re-entry | after 21 trading days with no new low AND 21d vol < 14%, restore one rung per week |

**Active-return breakers** (vs EW-34, from active-HWM): −4% → formal review; −6% → S1/S2 frozen pending review; −10% → shutdown review.

**Governance gates (hard, automated):** no new orders on a non-GREEN scorecard (S3's fail-safe, book-wide); S1/S4 staleness gates fail-closed (hold, never liquidate); S3 Tier-1 forced exits execute regardless (risk-reducing trades always allowed); the dial freeze-on-stale rule with the manual CBOE override in a falling tape (S5 §5.4).

---

## 5. Netting logic — one order file per close, shared costs, explicit precedence

Pipeline, assembled at 08:30 (file #1) and finalized 15:42 ET (file #2):

1. Each capital sleeve (CORE, S1, S2, S4, S6) emits a target-weight vector as a fraction of the invested book; unfilled slots = cash.
2. **S3 overlay:** `Haircuts(Vetoes(Σ sleeve vectors))`. Veto/haircut-freed weight → **cash** (signal-shaped information; redistributing would re-lever the book).
3. **Dial scaling:** multiply by (dial_state × 90%), then apply the breaker min().
4. **Caps (§4):** clip the breaching ticker; the excess redistributes *within the contributing sleeve* to its next-ranked eligible name; repeat until feasible. (Deliberate asymmetry with step 2: caps are risk constraints, not signals — the sleeve keeps its capital in its next-best name.)
5. **Net delta per ticker** = w_final − holdings. **Suppression band:** |delta| < 0.4% NAV ($400) → no trade, unless (a) an S3 Tier-1 veto mandates exit-to-zero, (b) a dial state-change (its own $200 min-trade filter applies instead), or (c) accumulated suppressed drift > 0.8% NAV. This is where overlapping sleeve trades collapse — a CORE monthly buy that S2's tranche is selling nets to zero and neither pays the spread; a dial de-risk nets against S1's roll.
6. **One net order per ticker**, styled by the M4 execution layer: tier styling (A-mega/A → MOC or Adaptive; B → midpoint peg in the home-market window, unfilled → capped marketable by 15:30; C → LOC ±0.3–0.5% band or worked midpoint; EDEN → resting midpoint, never MOC; never market orders below mega tier), S3 Tier-3 timing (X-CAL/X-BASIS/X-STRESS), M4 fair-value bands (rich ≥ FV+25 bp → delay/substitute; cheap ≤ FV−10 bp → execute now). M1 same-close orders bypass M4 delays. Whole shares for auction orders; fractional otherwise.
7. **Cost attribution:** realized cost of each net order is charged back to sleeves pro-rata by |delta contribution|; S3's value is measured separately via its per-veto counterfactual ledger; M4's value via paired filtered-vs-unfiltered arrival prices (S4's audit).

**Precedence (highest first):** S3 Tier-1 vetoes → dial/breaker invested cap → account caps → sleeve targets → suppression band → M4/Tier-3 execution timing. Nothing below a veto re-opens a vetoed name; nothing in the execution layer changes *whether* a position is held.

---

## 6. Benchmark — equal-weight 34, and why not ACWI

**Primary: EW-34** — equal weight of the 34 ETFs, monthly rebalanced at month-end close, dividends reinvested, computed internally from adjusted closes (execution era: `etf_prices_daily`; history: `t2_master`/`t2_levels_daily`). The owner's question is *cross-sectional country selection*; ACWI is ~65% US by cap and would turn the scorecard into a US-beta bet no sleeve decides. EW-34 is investable at trivial cost (≈ CORE without screens), so "active vs EW" is a real opportunity-cost number. Measured base: 7.9%/yr, Sharpe 0.56, maxDD −58.9% (2006–26, s5 run); 7.7%/yr, 0.44, −29% (2015+, mine_math). **Secondary reporting (context only):** ACWI and T-bills on the dashboard, never in triggers. The dial's insurance ledger is additionally marked against permanently-invested EW (its own convention).

---

## 7. The operations day and the unified rebalance calendar

### Daily timeline (ET)

| Time | Step | Notes |
|---|---|---|
| ~05:45 | News pipeline / bridges (existing) | feeds `gdelt_articles_recent`, `etf_prices_daily` |
| 06:30 | Prediction-market collectors (existing launchd) | context tier |
| ~07:00–07:40 | `daily_update.py` → `loop_daily_job.py` (33 steps) | combiner/graph/twins/dislocations stamped T-1; launchd safety net 11:30 |
| 08:00 | **S3 overlay recompute** | reads T-0-fresh event tables; emits overlay state file |
| **08:30** | **GATE 1 — freshness & governance** + order file #1 | scorecard GREEN; freshness board; S3 state applied; file #1 = Tier-1 forced exits (queued for the close), S2 tranche roll (1st/11th bd), CORE monthly (1st bd), risk-repair trades, M3 resting-bid list |
| 08:30–09:15 | S6 desk session (when funded); desk orders join file #1 or #2 | per desk protocol |
| 09:45–11:30 | Europe Tier B/C midpoint execution; **M3 resting bids placed** | home markets open — tightest window; M3 bids auto-cancel 15:30 |
| 11:00–15:00 | Asia/other Tier B/C midpoint execution | premium/discount (M4) check first |
| **15:20–15:30** | **GATE 2 — S1 Mode-A re-score** (Phase-2 build; until validated, S1 runs Mode B at the 15% cap) | frozen ridge coefficients + T-0 features |
| **15:40** | **Pre-close block:** S4-M1 residual compute; **S5 dial compute** (live VIX/VIX3M + lag-1 credit/FX) | S4 calendar checks; dial hysteresis counters |
| 15:42 | Order file #2 assembled: S1 tranche roll + M1 tranches + dial deltas + S3 exits, netted against morning residuals (§5) | abort-to-cash if not confirmed by 15:49 (S4's rule, adopted) |
| 15:45–15:50 | Submit MOC (Tier A) / LOC band (Tier B/C) | NYSE cutoff 15:50; Nasdaq-listed 15:55 |
| 16:15 | Fill reconciliation → strategy-local store (SQLite/CSV under the strategy dir — **never** the ASADO DBs) → NAV mark | |
| 16:30 | Nightly monitor page build + alarms | §14 |

No S1/S4 roll on US half-days or when GATE 1 fails (holdings ride; a failed gate never forces liquidation — except S3 Tier-1 exits, anchored to durable event dates). A dial *de-risk* is never blocked by a failed gate (risk-reducing); a dial *re-risk* is.

### Calendar summary

| Frequency | What | When |
|---|---|---|
| Daily | S1 1/5 roll (close); S4-M1 h=2 tranche (close); S4-M3 bids (morning); S3 recompute + event exits; dial compute; breakers; caps | per timeline |
| Monthly ×2 | S2 tranche A + CORE rebalance (1st bd); S2 tranche B (11th bd) | 10:15–11:30 ET |
| Ad hoc | S6 desk trades (0–3/wk when funded); dial state changes (~8/yr) | close, netted |
| Weekly ritual | review packet Friday 16:45; human review Saturday | §14 |
| Quarterly | program re-underwrite vs kill table; ETF-capture re-measurement; S4/S6 gate reviews | first Saturday Jan/Apr/Jul/Oct |

(If S7's W3 turn-of-month trial validates, the monthly legs migrate to the [-1,+3] window per §2.5 — a scheduling amendment, not a new sleeve.)

---

## 8. Expected performance — honest arithmetic

All component numbers cited from the named sibling/miner files; long-only degradation and ETF capture are inside the cited sleeve-level numbers where stated.

**Net active vs EW-34 (book contribution/yr, steady state P3):**

| Sleeve | Sleeve-level net expectation | Source | Book contribution |
|---|---|---|---|
| S1 (25%) | +0.7 to +4.0%/yr fully-invested at ~5 bp blend (decay × capture 0.60 at h=5; cost 252×2×0.148×5 bp ≈ 3.7%/yr; banding assumed ~offsetting per PL-2) | mine_math §4; design_S1 §3 | **+0.2% to +1.0%** |
| S2 (30%) | +0.4 to +1.4%/yr | design_S2 §3 | **+0.1% to +0.4%** |
| S3 (overlay) | +0.3–0.5%/yr normal years (overlap-haircut applied), +1.5–4% stress years, −5 bp running | design_S3 §3.3 | **+0.3% to +0.5%** |
| S4 (12.5%, post-gates) | M1 central +3–5%/yr on $10k; M3 $75–200; M4 savings $150–250 book-wide; **CI spans zero** | design_S4 §5, scaled | **0 to +0.6% (central ~+0.4%); 0 at launch** |
| S5 (dial) | active 0 ± 0.5%/yr (measured +0.38 lag-1 / −0.24 lag-2); vol −3 pts; crash maxDD −8 to −12 pts; ~0 in grinds | design_S5 §3 | **0 ± 0.5%** |
| S6 (0→5–10%) | 0 until calibration gate; conditional +0.7%/yr at the gate bar; downside bounded (K3 −$2k) | design_S6 §3 | **0 at launch** |
| CORE (17.5%) | ≈0 (±0.1–0.3%) | §3.0, *assumption* | **~0** |
| **Total net active vs EW-34** | | | **≈ +0.5% to +2.5%/yr; central ~+1.3% (+$1,300); launch state (CORE+S2+S3) ≈ +0.4 to +0.9%** |

**Total-return build (steady state):** ~0.82 avg invested (0.90 × dial avg 0.913) × EW base 7.7% (2015+ regime) ≈ 6.3% + avg ~18% cash × ~2.7% blended IBKR yield ≈ +0.5% + active +0.5–2.5% ≈ **7.3–9.3%/yr, central ~8.1%**.

| Metric | This book (expected) | EW-34 (measured) |
|---|---|---|
| Total return | 7.3–9.3%/yr | 7.7%/yr (2015+); 7.9% (2006+) |
| Vol | ~11–13% | 15.3–15.7% |
| Sharpe | ~0.55–0.75 | 0.44–0.56 |
| Max drawdown | ~−18 to −25% expected (dial-measured −46.7% full-cycle on pure EW; 2016+ −23.6%; breakers cap at −20% ex-gap-risk; **~no dial protection in a 2022-style grind** — S5's honest limit) | −29% (2015+) / −58.9% (full) |

Consistency check: mine_math's concentrated flagship (70% top-5 h=5 + 30% cash) projects 8–11%/yr, Sharpe 0.55–0.75, maxDD ~−30%; this design trades a slice of expected return for four-mechanism breadth, event-overlay left-tail insurance, a measured stress dial, and tighter breakers. **Stated plainly: at $100k the expected active is ~$500–2,500/yr.** The program is a validation vehicle, not a get-rich vehicle. It is also *not* a template that scales to the owner's real $33–40M book — Tier B/C capacity (EDEN, EPHE) does not exist at that size; only CORE, S1-in-megas, S3 avoidance, and the dial scale. (The loop DB's portfolio tables mirror that real book, not this one — mine_livedb.)

**Day-1 worked example (2026-06-30/07-02 data, launch-phase weights, illustrative):** dial score 0 → 100% state (invested cap 90%, but launch phase holds more cash by schedule). S3 state: **veto EWW, veto EWQ**; add-blocks EZA (upgrade), EIDO/EWI/THD (inflows); ×0.5 haircuts Germany/Netherlands (cold prints; France moot under veto); ECH add-freeze (D10); M4 delay-if-rich flags on ASHR (+2.13 gap z, ~10% premium) and QQQ. S2 tranche A: top-8 composite led by Hong Kong/Brazil/ChinaA-cluster/India; Indonesia retained-but-not-added (V1); Mexico and France skipped (vetoed). S1 (Mode B, 15% cap): banded top-5 = EIDO*, TUR, EWH, EPOL, EWZ per S1's own worked example — *EIDO maintenance-only under the S3 inflow block; TUR enters only under its 15-day Tier-C residence minimum. CORE: 28 Tier A/B names minus EWW/EWQ (vetoed) and persistent bottom-5 (EWN and peers). All §4 caps clear; Indonesia aggregate ≈ 8–9% < 10% cap.

---

## 9. Capital & sizing summary

- **Clip sizes:** CORE ~$600–650; S1 $3,000 (at 15%) → $5,000 (at 25%); S2 ~$1,875/slot; S4-M1 $1,000; S4-M3 $2,500 resting; S6 $2,500 (Stage 1) → $5,000 (year-1 Stage 2). Fractional shares enabled (mandatory for SPY/QQQ clips); whole shares for MOC/LOC auction orders.
- **Capacity:** trivially fine at $100k. Worst cases: EDEN S2 double-slot ~$3,750 ≈ 0.5% of $0.8M/day ADV (patient resting limit, one session); EPHE S1 slot ≤0.5% of ADV. Everything else <0.15% of ADV. Commissions (IBKR Pro Tiered) $0.35–1.00/order ≈ 0.5–4 bp at these clips — material only below ~$1k/clip, which is why S4-M1's grant is floored at $10k (§2.3).
- **Account:** IBKR Pro, Tiered, margin-type at zero leverage (T+1 settlement never blocks re-entry; PDT irrelevant above $25k), SmartRouting, fractional ETF trading on. Tax (one line): this book is short-term-gains-heavy — it belongs in an IRA if ever implemented for real.

---

## 10. Top risks and failure modes (top 5, each with a detection signal)

1. **Combiner forward decay below viability** — S1's components were selected in-sample 2026-06; 2016+ h=5 economics are ~breakeven at 10 bp; mine_lit's ~30% OOS-decay haircut for ML composites. *Detect:* panel 4 rolling 63/126d realized IC of scores vs next-day **ETF** returns; S1's own P/L gates; sleeve expectation cone (panel 3).
2. **Single-mechanism concentration** — S1 + S2's C1–C3 are one idea (diffusion); a convergence-breaking regime (decoupling, capital controls, bloc fragmentation) hits 55% of capital at once. *Detect:* rolling 126d S1–S2 active-return correlation > 0.7 AND combined 126d active < −4% → joint review, treat as ONE sleeve for breaker purposes.
3. **ETF capture worse than assumed** — 0.60 (h=5 measured) and 0.75–0.85 (h=21, extrapolated) rest on 13 months of ETF closes; live capture ≈0.4 sends S1 net to ~zero and halves S2. *Detect:* quarterly capture re-measurement (realized sleeve active ÷ index-based counterfactual at identical weights); S1's L5 kill (capture <0.40, 2 quarters); S6's phantom-alpha audit is the desk-side twin.
4. **Stacked de-risk whipsaw / insurance drag** — the dial (28 of 38 historical episodes lost money), breakers, and S3 vetoes can compound into structural under-investment in choppy years (2007-type: dial alone −6.9% vs benchmark). *Detect:* the dial's own whipsaw counters and insurance ledger (§11); a book-level "insurance drag" line on panel 3 = (dial drag + veto opportunity cost + breaker drag) vs EW; > −4%/yr rolling 12m with no benchmark DD >15% → convene the §14 review with S5's premium-cap rule on the table.
5. **Ops/data integrity failure** — trading stale combiner dates, a red scorecard, the unreconciled `live_signals` registry (all 16 hypotheses show INSUFFICIENT_COVERAGE despite a green scorecard — mine_livedb), a silently lost dial state file (path-dependent counters), or a missing home close feeding M1 garbage. *Detect:* GATE 1 hard-block + panel 8; the dial's fail-loud counter-file rule; S4's per-country calendar checks; any order on a non-GREEN/stale day is an incident; 2 incidents in a quarter → automation suspended, manual-only until root-caused.

(Standing sixth: cost-regime break — stress widens Tier B/C spreads past budget; pre-registered response: Tier-A-only until the trailing-20 average is back inside budget. Standing seventh: crowding — BlackRock's CORO runs the same shape at scale; watch its AUM and universe premium/discount behavior quarterly, plus M3 fill rates trending to zero as S4's canary.)

---

## 11. Kill criteria and the shutdown list

Sleeve-internal kill rules are honored verbatim: S1 P-gates + L1–L7; S2 K1–K5; S3 K-1…K-5; S4 G1–G3 + its post-launch table; S5's premium cap (>2.5%/yr drag over a no-crisis 3y window → advisory mode), payout-failure rule (in the next ≥25% benchmark DD the dial must reach ≤70% within 10 td of the −10% mark AND cut realized maxDD ≥15% relative, else permanently killed), and whipsaw kill (≥6 episodes/12m); S6 K1–K5. The account adds:

| Scope | Metric | Window | Threshold | Action |
|---|---|---|---|---|
| S1 | realized daily rank IC (scores vs next-day ETF returns) | rolling 126 td | < 0 | halve (S1's L1) |
| S1 | same | rolling 252 td | < 0 | **kill S1** (L2) |
| S1 | blended one-way cost | 2 consecutive months | > 7 bp | auto-switch to S1-L Tier-A-only (L4) |
| S4-M1 | net active vs its universe EW | rolling 126 td | < −3% ann. | **kill, return to paper** (S4's rule) |
| S4-M3 | fill-conditional 5d P&L | trailing 20 fills | mean < 0 | halt M3 |
| S4-M4 | filter value-add (paired audit) | trailing 50 filtered trades | < 0 | revert to default execution |
| Dial | S5's three rules above | per S5 §6 | — | honored |
| CORE screen | mean 63d fwd return of excluded names vs EW | last 20 exclusions | > +3% (excluded names outperforming) | drop the bottom-5 screen, keep S3 vetoes |
| Book | §4 breakers | daily | −10/−15/−20%; active −4/−6/−10% | de-risk ladder / shutdown review |

### What shuts the whole program down

1. Book drawdown −20% from HWM, or active drawdown vs EW-34 −10%.
2. **Two or more capital sleeves killed by their own criteria within any 6 months** (the shared-mechanism failure).
3. Twelve months live with book Sharpe < 0 while EW-34 Sharpe > 0.5 — the program is subtracting; collapse to EW + cash.
4. Governance integrity: scorecard RED > 5 consecutive nights unresolved, any append-only ledger violation, or a lookahead/blacklisted variable (`1MRet` class) discovered inside any live signal — automatic, immediate.
5. Cost structure: realized all-in costs > 2× tier budgets for a full month (structural spread-regime change).
6. Product structure: ≥3 universe ETFs close or fall below $50M AUM (EPHE $128M, TUR $175M are the watch names), or IBKR terms change materially (MOC access, fractional support).
7. Owner withdrawal of the governance exception (§12), at will.

(A dial payout failure in a live crisis kills the dial, not the program — the book reverts to breakers-only, which were designed to stand alone.) On shutdown: liquidate over 5 sessions via the M4 layer (no fire sale), park in CORE-lite or cash per owner instruction, write the post-mortem against §8, and feed every realized number back into the harness as forward out-of-sample record — a shutdown still produces the one thing the ledger lacks: live verification data.

---

## 12. Governance — what backs this, what must be registered first

**Existing anchors:** H_20260612_054 (COMBINER_RIDGE_DAILY_V1, WEAK — S1); H_20260612_043 (SIM_NBR_RET_GAP_63D), _041 (GRAPHP_BANK_NBR_RET_GAP_21D), _035 (GRAPHP_TWOHOP_TRADE_GAP_21D), _029/_032 (CONS_CPI_REV3M_12M), _015 (ECO_INFL_SURPRISE_Z flipped) — S2; event studies on file 2026-06-12 (downgrade_em, cds_inversion, rating_upgrade, VIX splits) — S3/S6; H_20260612_046 (ETF_FLOW contrarian) — the add-block; H_20260612_013 (SOV_2S10S_Z252, DEAD at 5d — used only per its 21d hold-grid exception, pending re-registration). LL_LEADER_GAP_5D is context-only account-wide (may confirm, never initiate); its tradable inversion is S4's registration. Forward-return variables are never touched.

**The uncomfortable truth, stated:** nothing in the ledger has ever been verdicted above WEAK; the constitution's promotion path (WATCH → paper → PRD → capital) authorizes **no live capital today**. This document is the account-level strategy PRD; the paper phase (§13) is mandatory and doubles as the missing forward verification. Going live requires the owner to sign a **documented governance exception** — rational basis: the WATCH gate is keyed to net-25 bp survival while measured Tier-A execution is 3–5 bp — or, cleaner, a trust-root amendment adding a "TRADABLE-AT-MEASURED-COST" verdict tier. Either path is deliberate and logged, never a silent override.

**Consolidated pre-live registration list** (the architect's coordination role: the siblings independently proposed overlapping families — they are merged below so one mechanism gets one family and one honest trial budget):

1. **Registry reconciliation (shared hard blocker):** `live_signals` shows all 16 registered hypotheses INSUFFICIENT_COVERAGE despite a GREEN scorecard — reconcile registry vs harness digest before any live order. (Named independently by S1, S2, S6.)
2. **S1:** NT-1 (Tier-A-17 universe trial), NT-2 (ETF-return outcome trial), PL-2 (banding/step-down engineering study). Gate S1 live.
3. **S2:** R1 — SOV_2S10S_Z252 re-registration at 21d primary (gates C4); R2 — `SLOWBOOK_COMPOSITE_V1` in new family `slow_composite_2026_07` (trust-root edit); R3 optional CPI-revision re-test.
4. **`etf_basis` family (ONE trust-root edit, prefix `BASIS_`)** — merges S3's E-3, S4's two registrations (the overshoot residual and the basis-gap trial, originally proposed as a separate `MICRO_` family), and S7's W4/W5, per S7's own "one instrument-mispricing family, shared trial budget" argument. Both S4 trials need `pit_proof_registry` entries (same-close formation/trade). Plus the **owner-approved adjusted-price history collector** (new `etf_prices_adj_daily` table; never touching `etf_prices_daily`; never unioned into unified/feature_panel) — gates S4's G1.
5. **`sov_events` family (ONE trust-root edit, prefix `SOVEV_`)** — merges S3's E-1/E-2 (event-study freeze + rating-change avoidance rank), S6's EVT_SOV_RATING_CHANGE_EM / EVT_CDS_CURVE_INVERSION, and S7's W9. One event scanner, one family, three consumers (S3 vetoes, S6 Tier-1, CORE screens).
6. **S5:** `risk_timing` family (trust-root edit, prefix `DIAL_`), registration of `DIAL_STRESS_SCORE` via the event-study path (locked §2.2–2.4 machine, 21d primary, PIT lag-1 proof), plus its 6-month nightly paper log. Gates the dial trading live money.
7. **S3:** E-4 (WEO/D3 event CAR) and E-5 (calendar-gate value test) — gate the E-R reserve and X-CAL value claims respectively.
8. **Optional, capital-free:** S7's W3 CAL_TOM (`cal_seasonality` family) — only its passing amends the §7 calendar. S7's other wildcards (W1 FX_BF25 flip, W2 TOT_, W6 FLOWF_, etc.) proceed as pure research on S7's charter; none touches this account before WATCH + paper + PRD.
9. **FF5+Mom spanning alpha** of the book (`scripts/harness/ff_spanning.py`) reported from paper-phase returns onward and quarterly thereafter.

Nothing in this design writes to any ASADO database; strategy state lives in its own store; every DB connection is `read_only=True`.

---

## 13. Paper-trading plan and phase-in schedule

The first draft's 2-month paper phase is withdrawn: the sibling documents impose longer gates (S1: ≥126 td; S2: one quarter; S4: G1–G3 incl. 60 td paper; S5: 6 months; S6: thesis-count-driven). The account phases in around the **slowest gate of each cohort**, and no sleeve goes live before its own gates pass — the architect never overrides a sleeve's paper requirement downward.

| Phase | Months | State | Exit criteria to next phase |
|---|---|---|---|
| **P0 — Paper everything** | Jul–Sep 2026 (mo 1–3) | Full ops day (§7) runs end-to-end on an IBKR paper account: GATE 1/2, netting, M4 styling, S3 overlay, dial nightly states (paper mo 1–3 of 6), S1 Modes A+B paper books, S2 runbook ×6 tranche events, S4 G1 build + G2 registration + G3 paper start, S6 Stage-0 cohort; registrations §12.1–.6 filed | ≥60 sessions; median \|paper MOC fill − official close\| ≤ 3 bp; zero unflagged stale-signal trades; §12.1 (registry) complete; S2's 6 paper tranches clean; owner governance sign-off |
| **P1 — Slow book live, half size** | Oct–Dec 2026 (mo 4–6) | **Live:** CORE 15%, S2 15% ($15k), S3 overlay (costs nothing). **Paper continues:** S1 (td count → ~126 by late Dec), S4 G3 (60 td), dial (mo 4–6 of 6), S6 Stage-0. Cash ~65% live | 2 clean months: realized costs ≤ 1.25× tier budgets; no kill triggers; veto latency ≤ 1 session; S1 P-gates evaluable |
| **P2 — Fast book + dial live** | Jan–Mar 2027 (mo 7–9) | S1 live at **12.5%** (Mode B) if its P-kill/P-go gates pass; S2 → 30%; CORE → 17.5%; **dial live** (6-mo paper + registration done); S4 live at its full §2.3 grant ($12.5k) if G1–G3 passed (no half-step — clip economics, §2.3); S6 Stage 1 ($5k) if its 20-closed-theses gate passed (realistically late in P2 or P3) | 2 more clean months; paper-vs-live slippage gap ≤ 2 bp; S1 live 63d IC > 0; dial state file audit clean |
| **P3 — Steady state** | Apr 2027 → | S1 → 15% (Mode B ceiling) or 25% (only with Mode A built + paper-validated per its P-mode gate); full §2 allocation; S4 escalation and S6 Stage-2 per their §2.3/§2.4 paths; quarterly re-underwrite | ongoing kill table |

Per-sleeve notes: any sleeve tripping a kill criterion during phase-in returns to paper for ≥3 months; de-scaling is always immediate, re-scaling always stepwise; a sleeve failing its paper gate (S1 P-kill, S4 G-gates, S6 K1) simply never funds and its grant stays in CORE/cash — the account is designed to run indefinitely on CORE + S2 + S3 + dial alone.

---

## 14. Monitoring dashboard and the weekly ritual

**Nightly dashboard (auto-built 16:30, one page + alarm emails):**

| Panel | Content | Alarm |
|---|---|---|
| 1. NAV & drawdown | book vs EW-34 vs ACWI vs cash; DD from HWM; active DD | breaker rungs §4 |
| 2. Exposure | invested % vs dial×90% target, cash %, EM %, Tier-C %, per-ticker weights vs caps; sleeve weights vs grants | any cap breach |
| 3. Sleeve P&L + insurance drag | cumulative net active per sleeve vs its expectation cone (§8); dial drag + veto opportunity cost + breaker drag line | 6 mo outside cone; drag rule (§10.4) |
| 4. Signal health | rolling 21/63/126d realized S1 IC (vs next-day ETF returns); S2 composite IC + rank-reconciliation vs `family_ranks_daily` (alert <0.9); S4-M1 regression R²/β drift, storm-day conditional | 63d IC < 0 |
| 5. Cost realization | per-fill one-way cost vs tier budget (3/5/10/20 bp); trailing-20 average; M4 delay counterfactuals + value-add | > 1.5× budget |
| 6. Turnover | one-way/day per sleeve vs design (S1 0.148 unbanded; M1 0.367 of its sleeve; S2 ~0.015–0.02; budget ≤0.12 NAV) | > 1.5× design |
| 7. Freshness board | max(date) per source table vs expectation (combiner T-1; sovereign/market-implied T-0; consensus/eco monthly; ToT/WEO stale-by-design); dial input staleness + counter-file integrity | any fast surface stale |
| 8. Governance | scorecard history; GATE 1/2 outcomes; registry-reconciliation status; incidents | any RED traded on |
| 9. Event board | active S3 vetoes/blocks with expiries (today: EWW ≈09-29, EWQ ≈09-21, EZA block ≈09-30, EIDO/EWI/THD inflow blocks, ECH freeze); new downgrades/inversions; SUSPECT_DATA log | new event |
| 10. Dial | score + 4 components (60d sparkline), state, dwell, days-to-re-risk eligibility; insurance ledger (premium paid vs payouts, per S5); advisory row (DXY z, D10 count, predmkt recession/Hormuz, regime tag) | state change; whipsaw/grind banners (S5 §5) |
| 11. Kill table | every §11 + sleeve-internal criterion, current value, traffic-lit | any red |
| 12. Context strip | dislocation brief link, desk note headline, gap-engine top-5, LL ranks | informational only |

**Weekly ritual (Saturday, 30–45 min, fixed agenda):** (1) kill table — reds decided ON THE SPOT per pre-registered rules, no re-litigating; (2) cost audit vs tiers + M4 value-add; (3) signal health + capture-ratio tracking; (4) event board, veto expiries, S3 false-positive audit; (5) netting/suppression audit (count netted-away trades — did cost sharing happen); (6) dial insurance ledger + whipsaw counters; (7) S6 calibration snapshot (Brier trend, open-thesis correlation) when active; (8) one page of context (dislocations brief, predmkt) — explicitly non-actionable; (9) append-only journal entry. Monthly addendum: paper-vs-live slippage; FF spanning; S3 marginal-value ledger; S4 dividend-calendar audit. Quarterly: full re-underwrite of §8; capture re-measurement; S4/S6 gate reviews; CORO AUM check.

---

## 15. Implementation sketch

**Data dependencies (must be true before each order file):** GATE 1 — `loop_daily_job.py` completed (combiner/graph/twins/dislocations/price_state stamped T-1); `sovereign_signals` + `market_implied_signals` T-0; `sov_rating_changes` scan + S3 state computed; scorecard GREEN; `etf_prices_daily` T-0. Monthly S2 files add `consensus_signals`/`eco_surprise_signals` at their native cadence. Pre-close block (15:20–15:42): S1 Mode-A re-score (Phase-2 build: frozen ridge coefficients + T-0 features, validated bit-identical vs official scores for 20 sessions in P0); S4-M1's 15:40 compute (IBKR snapshots for 21 ETFs + SPY; same-day home closes via IBKR index quotes; iShares distribution calendar; per-name `daily_calendar` checks); S5 dial (live VIX/VIX3M from CBOE + lag-1 credit/FX, persisted hysteresis counters in an append-only JSONL that fails loudly if lost).

**IBKR plumbing:** Pro, Tiered, margin-type at zero leverage, fractional on, SmartRouting. Order engine: Python against TWS/IB Gateway; the 08:30/15:42 netting steps emit a human-readable trade file (ticker, side, shares, order type, limit/band, sleeve attribution, S3/M4 flags, dial state) — human-reviewed before transmission in P0–P1, auto-transmitted with a 10-minute human veto window in P2+. Order types: MOC, LOC (±band), Adaptive marketable-limit, midpoint peg, GTC-day resting limits (M3), GTC stop-limits (S6). All fills, costs, marks, counterfactuals persist incrementally to the strategy-local store (SQLite/CSV under the strategy directory) — the ASADO warehouse and loop DB are read-only inputs, always `duckdb.connect(..., read_only=True)`; the loop DB's own portfolio tables (which mirror the owner's real account) are never written or reused.

**Monitoring build:** nightly Python job renders §14 from the strategy store + read-only loop-DB queries; alarms via email/push; weekly packet = same page + kill-table diff + journal template. Build order: netting engine + M4 wrapper + S3 state reader → paper account wiring → dial state machine → S1 Mode-A script (E-1) + S4 15:40 script → dashboards → P0 start. No step skipped, no step reordered.
