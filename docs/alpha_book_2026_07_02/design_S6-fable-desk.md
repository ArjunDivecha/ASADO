# S6 — THE ANALYST DESK ("Fable's Desk")

**Sleeve type:** Layer-2 discretionary, human-AI hybrid. Fable (the AI) reads the nightly dislocation brief, evidence packs, prediction-market surfaces and Triptych conditional-history priors each morning and proposes 0–3 trades/week under a strict, pre-registered protocol.
**Account:** hypothetical $100,000 IBKR, 34 US-listed country ETFs, LONG-ONLY + CASH, no leverage/derivatives.
**Status at design date (2026-07-02):** the thesis layer has essentially NO track record — 3 paper theses ever opened (2026-06-10, all A2 graph propagation): Taiwan short killed day 1 (measurement artifact), Indonesia long at −5.71% (day 21/42, invalidation −7%), Hong Kong long at −2.22%. This design therefore treats the desk as an UNFUNDED sleeve that must earn capital through a paper gate. That is not a hedge; it is the design.

---

## 1. Thesis — what the desk knows that the ETF price doesn't

The mechanical sleeves (combiner tranches, slow graph/twins tilts) monetize *standing cross-sectional ranks* — validated, repeatable, harness-verdicted. But the ledger census shows the warehouse's information is not exhausted by ranks. Three classes of edge are structurally invisible to a mechanical rank and visible to a reading desk:

**(a) Validated event windows that fire too rarely to be a rank.** The event-study layer has measured, statistically significant post-event drift on country returns:
- Sovereign rating downgrade: −0.7% CAR at +5d (t=−2.0), EM-concentrated: EM −0.9%@5d, **−2.8%@63d**; DM flat.
- Rating **up**grades also drift negative: −2.4%@63d.
- CDS curve inversion: **−4.5% CAR at +63d** (t=−2.4, n=41 events).
These are avoidance edges (long-only native: the alpha is in *not holding* the name vs the equal-weight benchmark) plus occasional long entries at the far side of the window. A daily rank cannot hold them — they are episodic, entity-specific, and require reading (was the downgrade anticipated? is the CDS inversion a data artifact?). Live specimen: Mexico's Moody's downgrade (2026-06-01) puts EWW inside the measured −2.8%@63d EM drift window right now.

**(b) Multi-family confluence.** The ledger's honest summary is that ~4 independent mechanisms exist among 59 trials, all individually WEAK (deflation charges every burned trial). But WEAK×WEAK agreement is stronger than either alone, and the machinery already computes the families every night — it just doesn't cross them. Live specimen: Hong Kong is #1 on PIT bank-claims gap (+0.068), #3 on combiner, #3 on twohop simultaneously; Netherlands is dead-last on five families at once plus a D2 intensifying short (−2.77z). No single registered hypothesis captures "three validated families agree"; a reading desk can, and can pre-register the conjunction shape into the harness when it recurs (checklist item 12 forces exactly this).

**(c) Mechanism disambiguation.** A z-score cannot distinguish "governor resigned" from "volcano erupted" — same attention shock, opposite trades (this is verbatim why `build_evidence_packs.py` exists). The evidence packs freeze headlines for every fired dislocation; Triptych priors give conditional base rates; prediction markets give crowd probabilities on the macro branch points (recession 12m 14.2%, Hormuz 26.1% at 07-01). None of this is a signal. All of it changes whether a signal should be *acted on* — which is precisely the layer the harness cannot test and the constitution quarantines as context-tier.

**Why the edge persists / who is on the other side:** country ETF flows are dominated by index allocators and slow institutional rebalancers who do not read cross-country network state and cannot trade n=41 event studies (no systematic fund allocates to an edge it cannot backtest at scale). Jacobs & Müller (JFE 2020) show country-level anomalies do NOT decay post-publication outside the US — limits to arbitrage are structural at this asset-class level. And at $100k the desk's size is irrelevant to capacity: the constraint is skill, not room.

**The honest core claim:** this sleeve's edge is *conditional on demonstrated calibration*. The desk's premise is testable and the machinery to test it (thesis ledger + Brier-by-archetype calibration report) already runs nightly. The design below is a protocol for buying that option cheaply: zero capital until the calibration bar is met, hard-bounded downside after.

---

## 2. Exact rules — the Desk Protocol

### 2.1 Universe, expression, cash

- **Instruments:** the 34 US-listed country ETFs only (map fixed: Australia EWA … Vietnam VNM). LONG positions and CASH only. Negative views are expressed as (i) refusing to hold / exiting, and (ii) a written **Avoid List** published in the desk note that other sleeves *may* consume only if their own specs permit (the desk never overrides another sleeve's mechanical rules directly).
- **Spread-tier × horizon matrix** (cost inputs from the execution miner; one-way all-in at $3–10k clips):

| Tier | Tickers | One-way cost | Minimum desk horizon |
|---|---|---|---|
| A-mega | SPY QQQ IWM EWJ EWT EWY | 3 bp | 5 trading days |
| A | EWC MCHI INDA EWU EWQ EWG EWI EWL EWW EWZ ASHR KSA EWS EWA EWM EWH | 5 bp | 5 trading days |
| B | EPOL VNM EWD EWP EWN EIDO | 10 bp | 10 trading days |
| C | ECH TUR THD EPHE EZA (EDEN excluded) | 20 bp | 21 trading days |
| — | EDEN | 26 bp spread, $0.8M/day ADV | monthly+ horizons only; clip ≤ $5k |

- **Cash rule:** undeployed sleeve capital sits in IBKR cash (Pro rate ≈ benchmark −0.5%, ≈3.1–3.8% mid-2026 at NAV ≥ $100k). The desk is *expected* to be partly in cash most of the time; being fully invested is a red flag, not a goal.

### 2.2 The evidence-tier system — what the AI may act on

Every input the desk reads is classified into one of three tiers. **A trade's primary trigger must be Tier 1 or Tier 2. Tier 3 may modify size/priority within bounds but may never initiate and may never be load-bearing** (operational test: delete every Tier-3 line from the thesis text — the trade must still stand).

**Tier 1 — Validated event windows (may initiate LONG-entry or Avoid-List action):**
- EM sovereign rating downgrade → Avoid/exit the ETF for 63 trading days from event date (measured EM CAR −0.9%@5d, −2.8%@63d). DM downgrades: no action (measured flat).
- Sovereign rating upgrade → Avoid adding for 63d (measured −2.4%@63d).
- CDS curve inversion (from `sovereign_signals` 5Y/1Y slope) → Avoid/exit for 63d (measured −4.5%@63d, n=41).
- *Governance condition:* each of these must be formally registered in the harness as an event-class hypothesis before the desk's first FUNDED trade (see §7). Until then they are Tier 1 for PAPER theses only.

**Tier 2 — Multi-family validated confluence (may initiate LONG):** requires ALL of:
1. ≥2 **independent** validated families agree on direction for the entity, drawn from: {COMBINER_RIDGE_DAILY_V1 (`combiner_scores_daily`, validated 29-country ranks), PIT bank-claims neighbor gap (GRAPHP_BANK_NBR_RET_GAP_21D family — the entire graph-spillover family counts as ONE vote regardless of how many variants agree), fundamental twins (SIM_NBR_RET_GAP_63D), sovereign 2s10s (SOV_2S10S_Z252, ≥21d horizons only)}. LL_LEADER_GAP_5D may CONFIRM but never count as one of the two initiating votes (tradability trap: measured ETF capture is 0.36 at 1d — the US-listed ETF already embeds most of the move).
2. A live `dislocation_daily` row or gap-engine episode on the entity as the *occasion* (this is context, not evidence — it answers "why today").
3. No validated contrarian headwind: ETF 21d flow z > +2.0 blocks any long (ETF_FLOW contrarian, NW-t −2.2, corroborated by the dumb-money literature).

**Tier 3 — Context (size/priority modifiers only, ±25% of base size max, every use logged):** Triptych conditional-history priors (constitution: context-tier ONLY; the queue-lean rank tested DEAD at IC −0.003), GDELT/D5 attention + evidence-pack headlines, gap-engine tension/absorption index (self-declared unvalidated), prediction-market composites (D6 blocked until ~mid-Aug 2026), JST drawdown buckets, regime tag (H3 failed — no mechanical overlay), D1 ToT severity (TOT_IMPULSE_Z36M is explicitly UNTESTED as a rank), D7 crowding flags, D4 cross-asset, D10 FX-options-vs-equity, foreign-flows z (uncollected as a registered signal).

**Banned as rationale (hard list):** anything verdicted DEAD (valuation percentiles, FX implied-vol/RR/butterfly/carry as registered, GDP consensus revisions, ETF short interest, 12-1 momentum, monthly combiner, Triptych queue lean); any forward-return variable (`1MRet/3MRet/6MRet/12MRet`, daily analogs); headlines alone; D5 alone (constitution: LOOK trigger, never a trade signal); gap-engine "absorption" treated as validated ranking skill.

### 2.3 The daily desk session

- **Preconditions (stand-down if any fails — no new opens; existing stops still managed):**
  1. Last night's `run_manifest` all steps ok/fresh (the loop's T+2 tables — combiner, graph PIT, similarity, leadlag, `dislocation_daily`, price_state — carry data through T−1 only after the nightly run).
  2. Governance scorecard **GREEN** on all 7 dimensions (embedded at the top of the brief).
  3. `Data/dislocations/brief_YYYY_MM_DD.md` exists for T−1 and thesis marks ran (09:30 job).
- **Session window:** 08:30–09:15 ET. Reading list, in order: governance block → gap-engine top-5 → dislocation table → evidence packs for fired countries (`Data/loop/evidence_packs/{date}/`) → open-thesis D8 rows → family ranks / `combiner_scores_daily` top-bottom → predmkt snapshot → current-month calibration report (mandatory full read in the first session of each month).
- **Output:** 0–3 `thesis_open` events (via `scripts/loop/ledgers.py` `open_thesis`, author=`fable-desk`, paper flag per stage) + one desk note (markdown) containing: trades opened with full checklist, the Avoid List, and explicitly "no trade today" with one sentence why when nothing clears the bar. Silence is a valid, logged output.

### 2.4 Cadence and position limits

| Limit | Value |
|---|---|
| New opens | ≤ 3/week, ≤ 8/month |
| Concurrent open positions | ≤ 3 (stage 2), ≤ 2 (stage 1) |
| Per-trade size | min $2,000; max 10% of account ($10,000) at stage 2; $2,500 at stage 1 |
| Per-entity | 1 open thesis max; 1 re-entry per entity per 30 days after a stop |
| Regional concentration | ≤ 2 of 3 slots in one region bucket (Asia-EM / Europe-DM / LatAm / other) |
| Account-level per-country cap | desk + mechanical sleeves combined ≤ 15% in one country ETF |
| Averaging down | banned; adds require a NEW independent trigger and open as a new thesis |
| Stated probability | bounded 0.50–0.80; no thesis may claim > 0.80 until ≥ 40 closed theses exist (the calibration curve has no data above 0.7 — PROB_BUCKETS top bin is 0.7–1.0) |
| Same archetype concurrent | ≤ 2 open theses per archetype (§2.7) |

### 2.5 The mandatory skeptic checklist — 12 items, every trade, PASS/FAIL recorded in the thesis record

Any FAIL → no trade. The checklist is appended verbatim to the ledger entry (frozen, auditable).

1. **Mechanism.** One sentence: what mispricing, who is on the other side, why they are slow.
2. **Tier audit.** Primary trigger is Tier 1 or Tier 2. Enumerate every Tier-3 input consumed; confirm the trade survives deleting all of them.
3. **Evidence citation.** Named hypothesis IDs / event-study artifact, with measured effect size and t-stat. Expected move ≥ 5× the ETF's round-trip cost tier.
4. **Freshness proof.** Scorecard GREEN; per-input as-of date listed; no T+2 table treated as T+0; stale-by-design inputs (eco surprises, short interest, ToT commodity as-of, WEO vintage, COT) flagged with their actual dates.
5. **Lookahead audit.** No forward-return variables anywhere in the reasoning chain; any daily lag-0 claim is backed by the pit_proof_registry.
6. **Base-rate anchor.** Stated probability within ±10pp of the archetype's measured base rate (event-study hit rate, family positive-day share, or — once available — the desk's own Brier-by-archetype table). Larger deviations require written justification naming the differentiating evidence.
7. **Crowding & conflict scan.** ETF 21d flow z (> +2.0 blocks longs); D7 dispersion-compression flags on the loading factor; existing open theses and mechanical-sleeve holdings on the entity; account per-country cap.
8. **Cost & liquidity tier.** Horizon ≥ tier minimum (§2.1); for Asia names, premium/discount checked against index futures (not stale iNAV) — skip entry if |premium| > 50bp against the trade.
9. **Falsification triple.** (i) price stop = `invalidation_level` on cumulative return; (ii) mechanism invalidation — a non-price, observable condition ("wrong if …"); (iii) time stop = `horizon_days`. All three mandatory; the ledger schema already carries them.
10. **Long-only expectancy.** The edge must be positive on the long side alone or as avoidance-vs-EW; long-short stats are halved before use (measured: long-only tilts capture roughly half the cross-sectional alpha).
11. **Correlation cap.** New entity vs open desk positions: pairwise 63d return correlation < 0.7; not the 3rd expression of the same archetype+region.
12. **Registrability.** If this trigger shape has fired ≥3 times historically, it must be registered in the harness (family, variable, direction, mechanism) before the desk trades it again. One-offs must state why they are not registrable (n too small). This is the ratchet that forces the desk to feed the harness instead of bypassing it.

### 2.6 Entry / exit mechanics

- **Entry:** marketable limit or IBKR midpoint-peg (Adaptive); market orders permitted only on A-mega. Europe ETFs 09:45–11:30 ET (home market open, tightest window); Asia ETFs any US hour with the futures check (item 8); Tier C via LOC in the closing auction with a limit band.
- **Stops:** GTC stop-limit at the price corresponding to `invalidation_level` (limit band 30bp Tier A / 75bp Tier C), PLUS the daily 09:30 mark check as backstop (marks are on T2 country returns; the resting order is on the ETF — both must exist).
- **Time stop:** horizon expiry → exit MOC same day, no extensions. An extension is a new thesis with a new checklist.
- **Mechanism invalidation:** checked every session; if triggered, exit next liquidity window regardless of P&L.
- **Fractional shares** enabled (required for SPY ≈ $745 / QQQ ≈ $713 clips at these sizes).

### 2.7 The archetype menu — the unit of calibration

Every thesis carries exactly ONE archetype tag (new `archetype` field in the ledger entry; `calibration_report.py` already slices by detector via `source_dislocation_id`, and the desk tag makes the slice explicit and audit-proof). The menu is closed — a trade that fits no archetype is not taken; proposing a new archetype is a design change requiring a written addendum to this PRD, not a morning decision.

| Tag | Trigger class | Tier basis | Direction expressible | Funded-eligible? |
|---|---|---|---|---|
| **EVT_RATING** | EM sovereign rating change (`sov_rating_changes`) | Tier 1 | Avoid/exit only (63d embargo) | after §7.2 registration |
| **EVT_CDS** | CDS 5Y/1Y curve inversion onset (`sovereign_signals`) | Tier 1 | Avoid/exit only (63d embargo) | after §7.2 registration |
| **CONF_DIFFUSION** | ≥2 independent validated diffusion families agree long (combiner / bank-gap family / twins) + live dislocation occasion | Tier 2 | Long, 5–21d | yes (post-gate) |
| **CONF_SLOW** | twins-63d and/or 2s10s agreement, ≥21d horizon | Tier 2 | Long, 21–63d | yes (post-gate) |
| **REVISION_GAP** | D3 forecast-revision-vs-flat-price (Vietnam-type) | Tier 3 occasion only | Long | **paper-only** until the WEO event-shape trial (§7.3-adjacent) is registered and ≥ WATCH |
| **DEEP_DRAWDOWN** | drawdown ≤ −35% + evidence-pack mechanism read (Denmark-type; JST base rates are context) | Tier 3 | Long | **paper-only** until a JST-conditioner trial is registered and ≥ WATCH |
| **STRESS_DIVERGENCE** | D10/D4 FX-options-vs-equity conflict (Chile-type) | Tier 3 | Paper-short → Avoid-List advisory only | never (long-only book cannot express; pure calibration data) |

Paper-only and short archetypes are still opened, marked, and Brier-scored — they are free calibration data and feed the Avoid List. The archetype-ban rule (§4) and the ≥2-archetype gate condition operate on these tags.

---

## 3. Expected performance — honest arithmetic

**There is no measured expectancy for this sleeve. n=3 paper theses, currently −5.7%, −2.2%, and one day-1 kill.** Everything below is conditional arithmetic from cited components, labeled as such.

- **Stage 0 (paper, now → gate, realistically 5–8 months):** account P&L contribution = $0. Sleeve holds no capital; the $20k stays with the mechanical sleeves/cash. The desk's only stage-0 output is calibration data and the Avoid List.
- **Avoid-List channel (partially measured):** avoiding one EM-downgrade name at a typical 3% book weight for the 63d window saves ≈ 3% × 2.8% ≈ **8bp of account** per event (measured CAR, cited above); CDS-inversion avoidance ≈ 3% × 4.5% ≈ 13bp per event. At a handful of qualifying events/year across both, this channel is plausibly worth **10–30bp/yr vs equal-weight** — small, but it is the *measured* part.
- **Funded sleeve, conditional on passing the calibration gate (assumption-labeled):** capacity math: 3 slots × ~30-trading-day average hold → ~25 opens/yr, average clip $8k. IF the desk trades at exactly its gate bar (55% hit rate; winners +2.5% median, anchored to the 2.8–4.5% event-window magnitudes and typical dislocation-reversion sizes; losers −2.0% median given stops at −2.5% to −7%): EV ≈ 0.55×2.5% − 0.45×2.0% = **+0.48%/trade gross**; average round-trip cost across tiers ≈ 0.14% → **+0.33%/trade net** → 25 × $8k × 0.33% ≈ **$660/yr ≈ +0.7% on the $100k account** (~3.3% on sleeve capital above cash). A genuinely skilled desk (60% hit, +3/−2) would produce ≈ $2,800 ≈ +2.8%/yr. A failing desk is bounded by the demotion ladder (below) at roughly **−$3,000 lifetime (−3% of account)** before it is forced back to paper.
- **Sleeve vol / drawdown:** 2–3 concurrent positions × $8k in single-country ETFs (≈18–25% vol each, partially correlated) → sleeve vol contribution to the account ≈ 0.5–1.0%/yr; max drawdown hard-bounded by the demotion trigger at 15% of sleeve capital (= $3k = 3% of account).
- **Benchmark note:** the funded sleeve is benchmarked against **cash yield on its own capital** (it is mostly cash); its equal-weight-relative contribution flows through the Avoid List. Expected total: cash ≈3.4% on sleeve capital + 0 to +2.8% active, Sharpe on active capital ~0.3–0.8 *conditional on the gate* — and the design's honest central case for year 1 is **$0, because year 1 is paper.**

---

## 4. Capital & sizing — the staged ladder and the capital-feedback loop

**Stage 0 — PAPER (current, mandatory).** Sleeve capital $0. All theses `paper=true`, opened via the existing ledger, marked by the existing 09:30 machinery, scored by `calibration_report.py`.
**Graduation gate to Stage 1 (ALL required):**
- ≥ 20 CLOSED paper theses spanning ≥ 4 calendar months and ≥ 2 archetypes;
- Brier score ≤ 0.24 (constant-0.5 forecaster scores 0.25 — the desk must beat "no information");
- calibration-curve sanity: hit rate in the 0.55–0.60 stated-probability bucket ≥ 50%;
- mean per-thesis return, marked on **ETF closes** net of tier cost, > 0;
- phantom-alpha audit clean: median |index-mark − ETF-mark| divergence < 100bp/thesis (the machinery marks T2 country returns; the account trades ETFs; measured ETF capture of index alpha is only 0.36–0.60 — the gate must be passed in the tradable series).

**Stage 1 — PROBATION.** Sleeve cap **$5,000 (5%)**; per-trade $2,500; max 2 concurrent. Advance to Stage 2 after 15 closed LIVE theses meeting the same bars.
**Stage 2 — FUNDED.** Sleeve cap **$20,000 (20%)**; per-trade $10,000 (the mandated 10% hard cap); max 3 concurrent. Example clips at stage 2: $8,000 ≈ 10.7 shares SPY (fractional) or ~250–400 shares of a $20–30 EM ETF; every clip is < 0.5% of ADV for all tiers except EDEN (excluded/capped in §2.1) — capacity is a non-issue at this account size.

**Capital feedback (how live hit-rate decides whether the desk keeps capital):** the scoreboard is the existing monthly calibration report (Brier + hit rate by archetype, horizon, direction, regime), computed over a rolling 20-closed-thesis window:
- rolling-20 Brier > 0.30 → drop one stage immediately;
- sleeve peak-to-trough net P&L drawdown > 15% of stage cap → drop one stage;
- 3 consecutive price-stop closes → 2-week trading pause + written post-mortem before the next open;
- archetype ban: any archetype with ≥ 8 closed theses and hit rate < 35% is banned from the menu for 6 months;
- re-promotion requires 10 closed theses at the graduation bar; two demotions within 12 months → paper-only for 6 months.

---

## 5. Risks & failure modes (top 5, each with a detection signal)

1. **Narrative seduction / context-tier creep** — Fable talks itself into stories; Tier-3 color becomes load-bearing. *Detection:* monthly audit of frozen thesis texts — % of closed theses failing the "delete Tier-3 lines" test must be 0; any hit → protocol violation review, trade voided from calibration record only if caught pre-close, counted as a loss if post-hoc.
2. **Phantom alpha (the tradability trap).** Theses are marked on T2 local-index returns; the account trades US-hours ETFs which embed much of the move (measured capture 0.36 at 1d, 0.60 at 5d). *Detection:* the dual-mark audit (§4) — if median index-vs-ETF mark divergence across closed theses exceeds 75bp, suspend and re-spec toward ≥21d horizons where capture is highest.
3. **Correlated theses = one hidden macro bet** (e.g. three Asia longs are one China bet; the June cohort was three expressions of one A2 signal, and two of three are losing together). *Detection:* checklist item 11 pre-trade; post-trade, average pairwise 63d correlation of open entities > 0.7 flags in the desk note and blocks the next same-region open.
4. **Stale-input trades.** T+2 tables (combiner, graph, dislocations) read as fresh; stale-by-design inputs (ToT commodity as-of 2026-05-01, WEO 2026-04) treated as current. *Detection:* checklist item 4 requires per-input as-of dates in the frozen record; the stand-down rule (§2.3) makes a missed nightly run structurally untradeable.
5. **Miscalibration under a friendly tape** — the paper gate is passed in a benign regime and skill evaporates in the next one. *Detection:* the calibration report already slices Brier by regime-at-open; a funded desk whose losses concentrate in a regime absent from its paper window triggers a voluntary stage-down and 10 supplementary paper theses in the new regime.

---

## 6. Kill criteria (pre-registered)

| # | Metric | Window | Threshold | Consequence |
|---|---|---|---|---|
| K1 | Paper-gate failure | first 30 closed paper theses | Brier ≥ 0.28 OR mean net ETF-marked return ≤ 0 | Desk never funds; 6-month redesign moratorium before any new paper cohort |
| K2 | Live calibration collapse | rolling 20 closed live theses | Brier > 0.32 | Immediate return to paper (skip the one-stage ladder) |
| K3 | Live P&L floor | cumulative, from first funded trade | net P&L < −$2,000 | Back to paper; a SECOND such episode kills the sleeve permanently |
| K4 | 12-month funded review | ≥ 30 closed live theses | net contribution ≤ cash yield on sleeve capital | Kill; capital reallocated to mechanical sleeves |
| K5 | Phantom-alpha audit | any 15-closed-thesis window | median (index-mark − ETF-mark) > 75bp/thesis | Suspend; re-spec to ≥21d horizons or kill |

All five are evaluable from the existing thesis ledger + calibration artifacts plus the new desk blotter (§8); none requires judgment to trigger.

---

## 7. Governance — what backs this, and what must be registered first

**Existing machinery this design runs on (no new validation claims):**
- Thesis ledger (`ledgers/thesis_ledger.jsonl`, `scripts/loop/ledgers.py` — `thesis_open`/`thesis_mark`/close events; probability, invalidation_level, horizon_days already in schema).
- Calibration machinery (`scripts/loop/calibration_report.py` — Brier + hit rate by archetype/horizon/direction/regime, PROB_BUCKETS, ≥10-closed acceptance threshold; monthly `Data/loop/calibration/calibration_YYYY_MM.md/.xlsx`).
- D8 stewardship (open theses resurface in every nightly brief), governance scorecard (7 dimensions), evidence packs, gap engine (context-tier), family ranks.
- Validated families cited in Tier 2: COMBINER_RIDGE_DAILY_V1, GRAPHP_BANK_NBR_RET_GAP_21D (+ graph family), SIM_NBR_RET_GAP_63D, SOV_2S10S_Z252, LL_LEADER_GAP_5D (confirm-only); contrarian flow ETF_FLOW_21D_Z (blocker-only).

**Pre-conditions before the FIRST FUNDED trade (each is a specific action, not a vibe):**
1. **Reconcile `live_signals`:** the view currently shows all 16 registered hypotheses `effective_verdict=INSUFFICIENT_COVERAGE` despite a green scorecard (livedb miner). Until registry and harness digest agree, Tier-2 "validated family" status is asserted from run files, not from the live view — unacceptable for funded trading.
2. **Register the event-class hypotheses** (mechanism stated before results, one primary horizon, PIT event dates):
   - `EVT_SOV_RATING_CHANGE_EM` — family: sovereign-events; variable: `sov_rating_changes`; direction: negative drift post-change (both signs), EM subsample primary; mechanism: forced sellers + benchmark-driven underreaction; horizon 63d.
   - `EVT_CDS_CURVE_INVERSION` — family: sovereign-events; variable: `sovereign_signals` 5Y/1Y slope < 0 onset; direction: negative 63d drift; mechanism: distress repricing leaks from CDS to equity holders slowly.
3. **New-surface trials the desk wants but may NOT touch until registered and verdicted ≥ WATCH** (these need a `family_registry.yaml` trust-root edit first, per governance):
   - `D9_BASIS_GAP_REV` — family: etf_basis (new); variable: D9 `gap_z`; direction: reversion, tested against **ETF** forward returns; mechanism: US-hours over/under-shoot vs local close (the only signal where the tradable instrument is in the signal).
   - `TOT_IMPULSE_Z36M` — family: tot; direction: deterioration → underperformance; mechanism: commodity terms-of-trade repricing lag. Until verdicted, D1 rows stay Tier 3 for the desk.
4. **Desk blotter exists** (§8) so ETF-marked P&L and the phantom-alpha audit are computable from day 1 of paper stage.

**Standing rule:** the desk operates INSIDE the constitution — context-tier quarantine (GDELT, Triptych, JST, tot_impulse, gap absorption), forward-return blacklist, pre-registration-before-results, every trial charged. Checklist item 12 makes the desk a hypothesis *generator* for the harness rather than a validation bypass.

---

## 8. Implementation sketch

**Data dependencies (must have run before the session):** nightly `loop_daily_job.py` (33 steps) green — specifically dislocation build + brief render, evidence packs, gap engine, family ranks, combiner, graph/similarity/leadlag features, thesis marks (09:30), calibration report, governance scorecard; prediction-markets job (06:30). Freshness reality: combiner/graph/dislocation surfaces carry data through T−1 after the run; eco surprises, short interest, ToT commodity, WEO, COT are stale-by-design and must be date-stamped in any thesis using them.

**New artifacts this sleeve requires (design-spec; nothing built in this session):**
- `ledgers/desk_blotter.jsonl` — append-only ETF fill log: {thesis_id, ticker, side, shares, fill_price, commission, ts, order_type}. Feeds the ETF-marked P&L, the dual-mark (phantom-alpha) audit, and the cost-realization check.
- Desk note: `Data/loop/desk_notes/note_YYYY_MM_DD.md` — opened trades with full 12-item checklist, Avoid List, stand-down/no-trade statements.
- A small `desk_gate_status.py` (reads thesis ledger + blotter, prints current stage, rolling-20 Brier, gate progress) so stage transitions are mechanical, not remembered.

**IBKR plumbing:** IBKR Pro, Tiered pricing, SmartRouting, fractional shares enabled. Orders per §2.6: midpoint-peg/Adaptive default; Europe names in the 09:45–11:30 ET window; Asia names gated on the futures premium check; Tier C via LOC with band; GTC stop-limits resting at invalidation prices; time stops via MOC on horizon expiry. At $2.5–10k clips, commissions are $0.35–$0.50/side — spread tier dominates, which is why §2.1's horizon matrix is a hard rule.

**Monitoring loop:** daily — 09:30 marks + D8 rows in the brief + resting stops; weekly — desk note Friday with open-position review and correlation check; monthly — full calibration report read (first session of month) + Tier-3-creep audit + archetype ban review; quarterly — survivor/post-mortem distillation per the PRD's quarterly cadence row (survivors → PKS; retired-thesis post-mortems), and the stage/kill table (§6) formally evaluated.

**Session identity & authorship:** all desk theses `author="fable-desk"` (distinct from `agent-overnight`); the calibration xlsx carries the author column per thesis, so a desk-only Brier slice is a one-line filter (the report's standard slices are archetype/horizon/direction/regime — verified in `calibration_report.py`). Overrides of mechanical-sleeve output, if ever permitted by those sleeves' specs, are logged as theses too — overrides are calibration data (PRD's override-feedback rule).

---

*Design honesty statement: every measured number above traces to the miner evidence pack (event-study CARs, family ICs/t-stats/breakevens, cost tiers, capture ratios, cash rates) or to repo machinery read directly (ledger schema, calibration thresholds, archetype taxonomy, brief format). The per-trade EV in §3 is explicitly conditional arithmetic on the gate being met — the desk has no track record, two of its three ever-opened paper theses are currently under water, and the design funds it $0 until the data says otherwise.*
