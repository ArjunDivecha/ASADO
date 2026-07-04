# S5 — THE CASH DIAL
## A regime/risk-off allocator scaling gross equity 100% → 30% for the long-only 34-ETF book

**Status:** design, hypothetical $100k IBKR account. Not live trading.
**Author:** Strategy designer S5, 2026-07-02.
**Calibration evidence:** single locked-spec backtest run 2026-07-02 against read-only warehouse data (script and raw results co-located: `s5_cash_dial_backtest.py`, `s5_cash_dial_results.json` in this directory). The specification below was written down BEFORE the backtest was run and was not tuned afterward — one spec, one run, results reported as-is including the parts that look bad.

---

## 0. Design philosophy (read this first)

Every piece of evidence in this program says regime timing is **not alpha**:

- ASADO's own regime project (`regime/regime.md`): H1 persistence PASS, H2 conditional-IC PASS, **H3 strategy value FAIL** (rolling windows beat baseline only 47.2% vs 60% required).
- The miner-lit report: Morningstar's TAA-fund record — essentially all tactical allocation funds underperform 60/40, and timing subtracted roughly half their return.
- The harness ledger: no timing signal has ever been verdicted above WEAK; most regime-adjacent surfaces (FX vol levels, valuation percentiles) are DEAD as return signals.

So this sleeve is designed as **cheap catastrophe insurance, not a return source**. The design targets are, in order: (1) cut the left tail of a book whose only hedge is cash (benchmark maxDD −59%); (2) cost approximately zero over a full cycle; (3) whipsaw rarely enough that the owner keeps the discipline on. The calibration backtest below shows exactly this profile: **+0.4%/yr CAGR net at 1-day lag (−0.2%/yr at 2-day lag), Sharpe 0.56 → 0.69, max drawdown −58.9% → −46.7%, vol 15.7% → 12.7%** — with only 10 of 38 de-risk episodes profitable and ALL of the cumulative gain coming from 2008 and 2020. That is what real insurance looks like. Anyone expecting the dial to "add alpha" should not run it.

---

## 1. Thesis

**What the data knows:** stress propagates through option and credit markets before it is fully priced into country-ETF levels — and, more importantly for a long-only book, once a genuine crisis regime starts, high-volatility clusters persist for weeks (GARCH persistence; ASADO regime persistence 0.79 at 1 month). Three specific surfaces carry this:

1. **VIX term-structure backwardation** (VIX3M/VIX < 1). The vol market pays a premium for *immediate* protection only when dealers and vol sellers are being run over. Backwardation days cluster almost exclusively inside genuine crisis windows (10.7% of days since 2006; measured in `market_implied_signals.RISK_VIX_TERM_RATIO`, confirmed 0.78–0.89 through Sep–Oct 2008 and 0.82–0.99 through Mar 2020, vs median 1.11).
2. **Credit and rates-vol confirmation** (HY OAS z, MOVE z). Equity vol spikes without credit confirmation are usually noise (Feb 2018); with credit confirmation they are usually regime (2008, 2020, 2022).
3. **Breadth of FX-option stress across the 29-currency panel** (share of countries with `FX_IMPVOL_Z252` > 2). When a quarter of the currency universe simultaneously prices elevated vol, the shock is global, not idiosyncratic — this is the backtestable substrate underneath detector D10 (FX-options stress unpriced by equity).

**Why the edge (such as it is) persists:** it isn't really an informational edge — it is a *risk-transfer premium*. The counterparty is every investor who cannot or will not de-gross into confirmed stress (mandates, benchmarks, career risk) and every vol seller harvesting carry until the term structure inverts. What the long-only book buys with the dial is a mechanical willingness to hold cash for ~20% of the time, forgoing ~1–2%/yr in most years, in exchange for −10 to −15 points of drawdown in the two-per-decade true crises. The persistence of volatility clustering is one of the most replicated facts in finance; the *unprofitability* of trading it aggressively is equally replicated — hence the deliberately coarse 4-state dial rather than continuous vol targeting.

**What the ETF price doesn't know:** nothing, on most days — and the design assumes so. The dial only claims that on the ~3% of days when the vol term structure is inverted AND credit confirms, the conditional distribution of next-month equity returns is left-shifted and fat enough that holding 30–50% cash is worth the whipsaw premium paid the rest of the time.

---

## 2. Exact rules

### 2.1 Inputs (all from the loop DB, `market_implied_signals`, tidy schema date/country/variable/value)

```sql
-- daily, one row per date (country='GLOBAL' block):
SELECT date, variable, value FROM market_implied_signals
WHERE variable IN ('RISK_VIX_TERM_RATIO','RISK_HY_OAS_Z252','RISK_MOVE_Z252');
-- daily, 29 currencies:
SELECT date, country, value FROM market_implied_signals
WHERE variable = 'FX_IMPVOL_Z252';
```

Missing-data rule: forward-fill each input up to 5 trading days (HY OAS routinely lags one day). If any input is stale > 5 days, **freeze the dial in its current state** and raise an ops alert — never silently score a missing component as calm. (FAIL IS FAIL.)

### 2.2 Stress score S(t) — computed once per day

| Component | +1 point | +2 points | Fire rate since 2006 |
|---|---|---|---|
| VIX term structure `RISK_VIX_TERM_RATIO` | < 1.00 | < 0.92 | 10.7% / 2.8% of days |
| HY credit `RISK_HY_OAS_Z252` | > 1.5 | > 2.5 | 15.5% of days (≥1pt) |
| Rates vol `RISK_MOVE_Z252` | > 1.5 | > 2.5 | 14.1% of days (≥1pt) |
| FX stress breadth: share of the 29 currencies with `FX_IMPVOL_Z252` > 2.0 | ≥ 25% | ≥ 50% | 9.4% of days (≥1pt) |

S(t) ∈ {0…8}. Thresholds are canonical round numbers (backwardation at 1.00 is the textbook definition; 1.5σ/2.5σ are conventional bands), chosen before the backtest and not searched.

### 2.3 Target equity fraction

| Score | Target gross equity |
|---|---|
| 0–1 | **100%** |
| 2–3 | **70%** |
| 4–5 | **50%** |
| ≥6 | **30%** |

The floor is 30%, never 0%. Rationale (context-tier, honest status below): the JST 150-year calibration (`docs/JST_MACROHISTORY_CALIBRATION.md`) shows deep real drawdowns (≤ −35%) are followed by the *best* median 3-year forward real equity returns (+8.8%/yr, 70 episodes) with a fat left tail (p10 −12%). A dial that can go to zero systematically sells the historical bottom. The 30% floor caps how wrong the dial can be in both directions.

### 2.4 Hysteresis state machine (fast down, slow and stepped up)

States: {1.00, 0.70, 0.50, 0.30}. Let `cur` = current state, `tgt` = target from S(t).

- **De-risk** (tgt < cur): move directly to `tgt` after S has implied a lower state for **2 consecutive days** — OR immediately (1 day) on a hard trigger: `S ≥ 6` or `RISK_VIX_TERM_RATIO < 0.92`.
- **Re-risk** (tgt > cur): move **one step only** (30→50→70→100) after S has implied a higher state for **5 consecutive days** AND the current state has been held ≥ 5 trading days. Full re-risk from 30% therefore takes a minimum of ~15 trading days.
- Confirmation counters reset on any state change or direction flip.

Measured consequence of this exact machine (2006–2026): 7.8 state changes/yr, 1.8 de-risk episodes/yr, median episode 18 trading days, time at 100% = 80.1%, average equity fraction 0.913.

### 2.5 Rebalance mechanics, time of day

- **Compute at 15:40 ET** each trading day. VIX/VIX3M are live indices; MOVE and HY OAS use the prior close (their components are lag-1 in the backtest convention, which the primary results already reflect). FX impvol z uses the loop DB's last nightly load.
- If the state changes, trade the whole book pro-rata to the new gross at the **same close**: MOC orders for Tier A names, **LOC with a ±15bp band** for Tier B/C names (per miner-exec: the close is the deepest print and matches the close-to-close backtest convention; never MOC in Tier C).
- **Netting rule:** the dial executes on the same close as any sleeve rebalance; compute final target shares ONCE (sleeve weights × dial fraction) and send the net orders. The dial must never generate a second round-trip on top of sleeve trades.
- **Min-trade filter:** skip any order below $200 (0.2% of NAV) — at $100k, sub-$200 clips are commission-inefficient noise.
- Proceeds sit in USD cash at IBKR (Pro tier: ~3.1–3.8% on balances above the first $10k as of mid-2026, per miner-exec). **The backtest credits cash at 0%** — live cash yield is uncounted upside of roughly +0.3%/yr at the average 8.7% cash weight, more in de-risked years.

### 2.6 Advisory (non-mechanical) inputs — displayed, never traded on their own

These were named in the design brief; they are deliberately excluded from the score, with reasons:

| Input | Why excluded from the mechanical dial |
|---|---|
| **D10 detector rows** (`dislocation_daily`, detector='D10') | The detector itself has 21 days of history (table starts 2026-06-09) — unbacktestable. Its *substrate* (FX-option stress) IS in the score via the FX breadth component, backtested to 2006. |
| **Breadth of dislocation severity** (count/Σseverity across D1–D10) | Same 21-day history; also D8 fires 495 times with severity 0.0 (stewardship rows) — the surface needs a cleaning convention before it can gate money. Display Σ|severity| for directional detectors (D1,D2,D4,D9,D10) on the dashboard; revisit for score inclusion after ~1 year of accumulation, via the governance path in §7. |
| **Predmkt country-risk composites** (`predmkt_signals_daily`) | One snapshot exists (2026-07-01); D6 is blocked until ~60 snapshots (mid-August at the earliest). `recession_prob_12m` (14.2% currently) and `hormuz_disruption_prob_90d` (26.1%) go on the dashboard as context only. |
| **Regime tagger R1–R7** (`regime/src/regime_tagger.py`) | Its own project verdict is H3 FAIL for strategy value. The monthly label (currently R7_Transition, tagged in every `dislocation_daily` row) is context for the human, not an input. |
| **JST drawdown buckets** | Never cleared the harness, annual data ending 2020 — context tier by constitution. Used exactly once in this design: to justify the 30% floor (§2.3). |

Hard rule: advisory inputs can prompt a HUMAN to review; they can never move the dial mechanically.

### 2.7 Current live state (as of data through 2026-07-02)

Score = 0 (VIX TS 1.155/1.159 contango, HY z −0.45/−0.65, MOVE z −0.28/−0.61, FX breadth 0.0). **State = 100% equity.** Note the livedb miner flagged DXY z +2.07 and an R7_Transition tag — dashboard-yellow, but the dial's mechanical answer today is fully invested; the DXY extreme is not a score component (it was not pre-specified, and adding it post-hoc would be tuning).

---

## 3. Expected performance (all numbers measured, single locked run, 2006-07-03 → 2026-06-30, 5,204 days)

Benchmark = equal-weight 34-country daily USD total-return index built from `t2_levels_daily` 'Tot Return Index' (pre-inception zeros for Vietnam/Saudi masked; countries enter as data begins). Cash at 0%. Dial cost 5bp × one-way turnover.

| | CAGR | Vol | Sharpe (rf=0) | MaxDD (date) |
|---|---|---|---|---|
| EW 100% invested | 7.89% | 15.7% | 0.56 | −58.9% (2009-03-09) |
| **Dial, net 5bp, lag 1 (primary)** | **8.27%** | **12.7%** | **0.69** | **−46.7%** (2009-03-09) |
| Dial, net 5bp, lag 2 (conservative) | 7.65% | 12.8% | 0.64 | −47.5% |
| Sub-period 2016–2026: EW | 9.77% | 12.6% | 0.80 | −31.9% (2020-03-23) |
| Sub-period 2016–2026: Dial net | 9.76% | 10.8% | 0.92 | **−23.6%** |

**The honest decomposition — where the money comes from and goes:**

- Of 38 de-risk episodes, only **10 made money vs staying invested; 28 lost**. Cumulative episode wins +36.6 pts, losses −36.1 pts: the dial is a **zero-expected-cost insurance policy** over this sample, not a return source.
- The two payouts: GFC episode 2008-09-10→2009-01-12 **+19.2 pts** vs benchmark; COVID 2020-02-25→2020-04-30 **+10.0 pts**. Everything else nets to roughly zero.
- The premium in bad years for timing: 2007 −6.9%, 2019 −6.6%, 2025 −3.7% vs benchmark (worst single whipsaws ~−3% each: Jul–Oct 2007, Nov 2018–Jan 2019, Apr–May 2025). Median non-crisis-year drag ≈ 1.2%/yr.
- Crisis-window detail: GFC half (2008-07→2009-03-09) EW −48.7% vs dial −35.1%; COVID crash (2020-02-19→03-23) EW −27.9% vs dial −12.8%. But: China 2015–16 the dial did WORSE (−17.6% vs −15.2%, whipsaw), 2018Q4 slightly worse (−8.7% vs −8.2%), 2022 bear ~no help (−21.6% vs −21.9% — the 2022 grind never produced sustained backwardation). **The dial protects against crashes, not grinds.**
- Missed upside: 2009 recovery fully captured (dial was back to 100% by March — the stepped re-risk worked); COVID recovery gave up 11.7 pts of the +55% (re-risking through April 2020).
- Dial trading cost: one-way turnover 2.01×NAV/yr → **10.1 bp/yr** at 5bp blended one-way ≈ **$101/yr on $100k**. Trivial.

**Forward expectation for the book owner (assumption-labeled):** expected *active* return of the dial vs a permanently-invested book ≈ **0 ± 0.5%/yr** (range spans lag-1 +0.38%/yr to lag-2 −0.24%/yr, before ~+0.3%/yr uncounted cash yield); expected vol reduction ≈ 3 points; expected maxDD improvement ≈ 8–12 points in a 2008/2020-class event, **≈ 0 in a 2022-class grind**; Sharpe improvement ≈ +0.10. Applied on top of the alpha sleeves (miner-math's realistic whole-book estimate ~8–11%/yr, Sharpe 0.55–0.75, maxDD ~−30%), the dial's role is to defend the maxDD estimate, not raise the return one.

**Overfitting disclosure:** this is ONE specification tested ONCE (no threshold search, no parameter grid), which is the strongest anti-overfit protection available in a design phase — but the components themselves (VIX TS, credit spreads) are the most-published regime indicators in existence, so treat the backtest as *confirmation the plumbing behaves sensibly*, not as proof of edge. The regime-timer base rate (most fail live) still applies.

---

## 4. Capital & sizing

- **The dial is not a sleeve — it is a multiplier on the whole $100k book.** It holds no positions of its own; it converts equity to cash pro-rata.
- Dollar mechanics at $100k: 100→70% moves **$30,000** to cash; 70→50% moves $20,000; 50→30% moves $20,000. Across a book of ~15–20 ETF positions, a full first-step de-risk is ~15–20 sell orders of $600–4,500 each — comfortably above the $200 min-trade filter for core positions; satellite positions below $650 are sold entirely rather than trimmed (avoid $200-floor residue).
- Approximate share clips for the largest core holdings at a 100→70 step (30% trim, prices ~mid-2026): SPY ~$745 → fractional shares mandatory (enable IBKR fractional trading); EWJ ~$75 → ~28 shares on a $7k position; EWH/EPOL/EWZ similar single-digit-to-tens clips. All Tier A/B — fills are a non-issue.
- **Capacity:** total dial turnover is ~$200k/yr notional at $100k NAV, spread over ~8 trading days/yr, mostly in the six mega-tier and 16 Tier-A names. Irrelevant to market impact by ~5 orders of magnitude. The only capacity-constrained name in the universe (EDEN, $0.8M/day ADV) would see at most a ~$600 dial order — still fine, but route it LOC.
- Cash parking: IBKR USD sweep. At the 30% state, $70k idle earns the IBKR benchmark-minus-50bp rate on $60k of it (first $10k earns zero).

---

## 5. Risks & failure modes (top 5, each with a detection signal)

1. **Whipsaw clustering** — a choppy year (2015, 2018–19, 2025-type) fires 3–4 losing episodes back-to-back; owner loses faith and turns the dial off right before it pays. *Detection:* rolling-12m count of de-risk episodes > 4 AND rolling-12m dial-vs-invested gap < −4% with no benchmark drawdown > 15% in the window. (Historical worst: ~−6.9% in 2007 — which was in fact the year BEFORE the payout; the detection rule flags for review, it does not auto-disable.)
2. **Grind blindness** — 2022-style slow bears without sustained VIX backwardation get ~no protection; the owner believes he is hedged when he is not. *Detection:* benchmark drawdown < −15% while the dial's trailing-63d average equity fraction is > 0.85 → publish a "DIAL NOT ENGAGED IN THIS DRAWDOWN" banner. This is a known, accepted limitation, not a bug — the slow-bear defense must come from sleeve-level signals (sovereign curve, downgrade avoidance), not the dial.
3. **Input decay/regime change in the vol market** — the structural growth of 0DTE options and vol-selling ETPs is changing what VIX term structure means; backwardation may become rarer/noisier. *Detection:* rolling-3y fire rate of the TS<1.00 component drifting outside [5%, 20%] (historical 10.7%), or a crisis (benchmark −20%+) in which the TS component never fires ≥1 point for 10+ consecutive days.
4. **Stale-input freeze at exactly the wrong time** — the nightly `collect_market_implied_bbg.py` fails during a crash (Bloomberg VM down), dial freezes at 100%. *Detection:* the §2.1 staleness alert; ops runbook says: if inputs stale > 2 days AND SPY 5-day return < −5%, compute VIX3M/VIX manually from CBOE's public quotes (both indices are free real-time) and override by hand. The primary anchor deliberately uses instruments with public real-time fallbacks.
5. **Interaction damage — the dial cuts the alpha sleeves at their moment of maximum expected return.** Cross-sectional dispersion (the alpha fuel, 4.3%/mo per miner-math) is highest exactly in crises; scaling to 30% cuts sleeve alpha capture ~70% during the richest periods. *Detection:* track sleeve-alpha-foregone (paper P&L of the uncut book minus actual) per episode; if cumulative alpha-foregone over 2 years exceeds 2× cumulative drawdown-avoided, the floor should be revisited upward (30→50) via governance amendment. (This is the honest cost of being long-only with a cash-only hedge — the alternative, staying gross-long through −59%, was already rejected by the owner's brief.)

---

## 6. Kill criteria (pre-registered)

The dial is falsified as *insurance* differently than an alpha signal — it must be judged on tail events and on premium paid:

1. **Premium cap:** if over any rolling 3-year forward window with NO benchmark drawdown ≥ 20%, the dial's net CAGR drag vs permanently-invested exceeds **2.5%/yr** (≈ 2× the historical worst 3-year non-crisis drag), the spec is mis-calibrated → drop to advisory mode, re-register.
2. **Payout failure (the real kill):** in the NEXT benchmark drawdown ≥ 25% peak-to-trough, the dial must (a) reach state ≤ 70% within 10 trading days of the −10% mark, and (b) reduce the realized max drawdown by ≥ 15% *relative* (e.g., −30% → −25.5% or better). Failing either in a live crisis kills the dial permanently — insurance that doesn't pay is fraud against yourself.
3. **Whipsaw kill:** ≥ 6 de-risk episodes in any 12 months (historical max ~4) → the score has lost its clustering property → advisory mode.
4. **Ops kill:** > 3 stale-input freezes lasting > 3 days each in any 6 months → the data dependency is unreliable → fix pipeline before re-arming.
5. **Review clock:** mandatory design review at 24 months regardless (2028-07), against accumulated live episode marks.

---

## 7. Governance

- **Existing harness backing: NONE — stated plainly.** No hypothesis ID in `hypothesis_ledger` covers a time-series (non-cross-sectional) risk dial; the harness measures cross-sectional IC and would not apply directly. The nearest prior art is negative: the regime project's H3 FAIL and the DEAD verdicts on FX-vol *levels as cross-sectional country signals* (different object from this time-series breadth gate, but a directional caution).
- **Required registration BEFORE any live (or paper-with-consequence) use** — one new trial:
  - **ID (proposed):** `H_2026xxxx_DIAL_STRESS_SCORE_V1`
  - **Family:** new family `risk_timing` — requires the trust-root edit to `config/family_registry.yaml` (per miner-docs, new surfaces need family assignment by variable prefix; propose prefix `DIAL_`).
  - **Variable:** `DIAL_STRESS_SCORE` = the §2.2 composite, computed nightly and persisted (new derived series; all four inputs already exist in `market_implied_signals`, so no new collector).
  - **Direction & mechanism:** score ≥ 4 ⇒ forward 21-day EW-universe return distribution is left-shifted and fatter-tailed vs unconditional; mechanism = vol-term-structure inversion + credit confirmation identifies persistent high-volatility regimes (vol clustering), during which the long-only book's conditional Sharpe is negative.
  - **Test form:** conditional/event study (the harness's CS-IC machinery doesn't fit a timing series — use the event-study path, like the rating-downgrade CARs), primary horizon 21d, PIT lag-1 proof required (daily lag-0 needs `pit_proof_registry`), one primary spec = the locked §2.2–2.4 machine.
  - **Charge the trial to the ledger** like any other; deflated stats reported against the new family's N=1.
- **Paper phase:** 6 months of nightly computed states logged to a file (no orders), then the WATCH→paper→PRD ladder as for any signal. The dial's episode marks feed the §6 criteria.
- **Blacklist compliance:** no forward-return variables used anywhere in the dial. All inputs are same-day market observables.

---

## 8. Implementation sketch

**Data dependencies (nightly, before 15:40 ET next day):**
1. `collect_market_implied_bbg.py` (OpusBloomberg conda env, absolute conda path) → parquet; `load_market_implied.py` (project venv) → `market_implied_signals`. These already run in the 33-step loop job; the dial adds no new collector.
2. Freshness check: max(date) for each of the four variables ≥ today−1 business day (HY OAS/MOVE are allowed today−2 as they publish lag-1; term ratio and FX must be fresh). Else freeze + alert (§2.6/§5.4).
3. Nightly job addition (design-phase; would be a new loop step, NOT a modification made by this document): compute `DIAL_STRESS_SCORE`, target state, hysteresis counters; persist `{date, score, components, tgt, state, dwell, confirm_counters}` as an append-only JSONL so the state machine survives restarts and is auditable. State is path-dependent — losing the counter file must fail loudly, not re-initialize silently at 100%.

**Intraday decision (manual or scripted, 15:40 ET):**
- Read yesterday's persisted state + counters; read live VIX/VIX3M (CBOE, free real-time) to refresh the term-ratio component; other three components use last-loaded values (lag-1, matching the backtest's primary convention).
- If state changes: recompute the book's target shares = (sleeve weights) × (new equity fraction) − current shares; emit order list.

**IBKR order plumbing:**
- Account: IBKR Pro, Tiered, margin-type (never borrow — margin type only so T+1 settlement never blocks re-entry, per miner-exec), fractional ETF trading enabled.
- Orders at 15:50 ET cutoff: **MOC** for Tier A-mega and Tier A; **LOC ±15bp** for Tier B/C; anything unfilled at close (LOC misses) re-sent next morning 9:45–11:30 ET (Europe names tightest then) as midpoint-peg. Never market orders below mega-tier.
- Sells incur SEC fee 0.206bp — ignore in sizing, it's in the 5bp budget.

**Monitoring (daily one-glance dashboard):**
- Score + 4 components (sparkline, 60d), current state, dwell, days-to-eligible-re-risk.
- Advisory row (§2.6): Σ|severity| directional dislocations, D10 count, predmkt recession/Hormuz, regime tag, DXY z.
- Insurance ledger: per-episode start/end, dial-vs-invested P&L gap, cumulative premium paid since inception, cumulative payout received — the §6 criteria computed live.
- Banner logic from §5 detections (whipsaw cluster, grind-blindness, input decay, staleness).

**Interaction with sleeve weights (summary of the contract other designers build against):**
- Sleeves define *relative* weights on the invested fraction; the dial defines the fraction. Final target = sleeve weight × dial state.
- Single netted execution per close (§2.5). Sleeve rebalances scheduled on dial-change days execute at the new gross in one pass.
- Sleeves may hold their own signal-driven cash (e.g., zero-weighting Netherlands-type names); dial cash stacks on top — the book's realized cash can exceed 1−state, never be below it.
- Event-driven defensive sleeves (downgrade-drift avoidance) are exempt from *re-risking* — the dial never forces buying a name a sleeve has flagged; the re-risk step redistributes pro-rata across unflagged names.

---

## Appendix — measured numbers referenced in this document

| Quantity | Value | Source |
|---|---|---|
| Benchmark EW CAGR / vol / Sharpe / maxDD 2006–26 | 7.89% / 15.7% / 0.56 / −58.9% | s5_cash_dial_results.json (this run) |
| Dial net lag1 CAGR / vol / Sharpe / maxDD | 8.27% / 12.7% / 0.69 / −46.7% | same |
| Dial net lag2 | 7.65% / 12.8% / 0.64 / −47.5% | same |
| 2016–26: EW vs dial maxDD | −31.9% vs −23.6% | same |
| Episodes won/lost, cumulative | 10 / 28, +36.6 / −36.1 pts | same |
| GFC / COVID episode payouts | +19.2 / +10.0 pts | same |
| Worst annual premiums | 2007 −6.9%, 2019 −6.6%, 2025 −3.7% | same |
| Time at 100% / avg fraction / episodes/yr | 80.1% / 0.913 / 1.8 | same |
| Dial turnover / cost | 2.01×/yr one-way / 10.1bp/yr ≈ $101 | same, 5bp blended |
| Component fire rates | TS<1: 10.7%; HYz>1.5: 15.5%; MOVEz>1.5: 14.1%; FX breadth≥25%: 9.4% | same |
| Current state (2026-07-02) | score 0 → 100% equity | live query |
| JST deep-drawdown forward 3y median / p10 | +8.8% / −12.0% real (70 episodes) | docs/JST_MACROHISTORY_CALIBRATION.md — context tier, never harness-cleared |
| Regime project verdict | H1 PASS, H2 PASS, H3 FAIL | regime/regime.md |
| VIX TS in crises | 0.78–0.89 (Sep–Oct 2008), 0.82–0.99 (Mar 2020), median 1.11 | market_implied_signals query |
| IBKR cash yield / tier costs | ~3.1–3.8% above $10k; Tier A ~5bp, megas ~3bp one-way | mine_exec.md |
| Whole-book context (sleeves) | realistic 8–11%/yr, Sharpe 0.55–0.75, maxDD ~−30% | mine_math.md |
