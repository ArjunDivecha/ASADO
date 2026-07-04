# S1 — THE FLAGSHIP: "Combiner Core" — Long-Only Weekly-Tranche Tilt on COMBINER_RIDGE_DAILY_V1

**Strategy designer, phase 2 | 2026-07-02 | Hypothetical $100,000 IBKR account | Long-only + cash, US-listed country ETFs | Analysis/design only — NOT live trading**

**Evidence base (all numbers traced):** harness digest v2.1 (2026-06-12); miner reports `mine_math.md`, `mine_exec.md`, `mine_livedb.md`, `mine_ledger.md`, `mine_lit.md`, `mine_docs.md` (same directory); read-only loop-DB queries run 2026-07-02 (schema of `combiner_scores_daily`, `combiner_weights`, `family_ranks_daily`, `hypothesis_ledger` verified directly).

---

## 0. One-page summary

| Item | Spec |
|---|---|
| Signal | `combiner_scores_daily` (loop DB), variable `COMBINER_RIDGE_DAILY_V1`, validated 29-country universe from `family_ranks_daily` (family=`combiner`) |
| Expression | Banded top-5, equal-weight, 5-day rolling tranches (h=5), traded at the US close (MOC/LOC), same close the signal is formed on (Mode A) |
| Universe | 28 of the 29 validated names (EDEN excluded for capacity); tier-dependent entry/exit bands throttle Tier B/C churn |
| Invested fraction | 70% ($70k in 5 × $14k positions), 30% cash ($30k at IBKR Pro ~BM−0.5%) |
| Expected active vs EW-29 (net, 5 bp blended one-way) | **+0.5% to +2.8%/yr on NAV** (scaled from mine_math's +0.7 to +4.0% at 100% invested); ~zero-to-negative at a 10 bp blend — cost control is existential |
| Expected total book | **~8–11%/yr, vol ~13%, Sharpe ~0.55–0.75, maxDD ~−30%** vs 7.7%/yr, 0.44, −29% for plain EW (2015+) — from mine_math §4 with decay × ETF-capture haircuts |
| Status gate | H_20260612_054 = WEAK (IC 0.0574, NW-t 10.7, deflated Sharpe −0.10). In-sample component selection 2026-06 ⇒ **mandatory 6-month paper phase with pre-registered gates before any live dollar** |
| The one thing that kills it | Blended execution cost drifting above ~7 bp one-way, or forward IC falling below ~half the 2021–26 in-sample level |

---

## 1. Thesis — what the data knows that the ETF price doesn't

**The informational edge.** COMBINER_RIDGE_DAILY_V1 is a walk-forward ridge blend (yearly refits, weights in `combiner_weights`; latest vintage trained through 2025-12-01 carries 7 features) of the only mechanism family that survived ASADO's 59-trial skeptic harness: **cross-country return diffusion** — banking-network neighbor gaps (GRAPHP_BANK_NBR_RET_GAP_21D), trade-network propagation (GRAPHP_TWOHOP_TRADE_GAP_21D, GRAPHP_KATZ_TRADE_GAP_21D), fundamental-twins gaps (SIM_NBR_RET_GAP_21D), plus slow reflation overlays (CONS_CPI_REV3M_12M, ECO_INFL_SURPRISE_Z) and contrarian ETF flows (ETF_FLOW_21D_Z). The claim, measured: when a country's economic neighbors (creditors, trade partners, fundamental twins) have outrun it over the past ~21 days, that country's own index catches up over the following days-to-weeks. Realized daily rank IC 0.0552–0.0574 (NW-t 10.5–10.7, 95% positive years, 2005–2026, 5,580 days) — independently reproduced by two separate measurement passes (harness run H_20260612_054 and mine_math §3).

**Why the edge exists / who is on the other side.** Country-index prices incorporate their *own* news quickly but incorporate *neighbors'* news slowly — the classic limits-to-arbitrage result. Jacobs & Müller (JFE 2020, 241 anomalies, 39 markets) find the US is the only market with reliable post-publication anomaly decay; country-level cross-sectional effects persist because almost no arbitrage capital operates at the country-index level (the counterparties are index-tracking flows, domestic institutions benchmarked locally, and retail — none of whom trade "Indonesia is cheap versus what its bank creditors and trade partners just did"). BlackRock's CORO (Dec 2024) is the first institutional product in this exact space — a validation and a future crowding tripwire, not yet a competitor at scale.

**Why it survives in the ETF, partially.** The honest part of this thesis: US-listed country ETFs trade in US hours and already embed roughly 40% (h=5) to 64% (h=1) of the next-day foreign-index alpha by the 4 pm close (mine_math §3c: ETF capture ratio 0.60 at h=5, 0.36 at h=1, measured on 13 months of actual ETF closes; consistent with Levy–Lieberman 2013 over-embedding). **The tradable edge is the ~60% of the 5-day diffusion alpha that US-hours market makers do not price**, because their fair-value models hedge beta (S&P futures, FX, index futures) — they do not price cross-country *relative* diffusion. That is precisely what this book buys.

**Why h=5 and not h=1.** The daily h=1 expression is the strongest number in the warehouse (gross +28.5%/yr, IR 2.81) and it is **untradable in ETFs**: capture 0.36 cuts realistic gross to +6.4%/yr against ~9.5%/yr of costs at even 5 bp (turnover 0.378/day). At h=5, turnover falls to 0.148/day, capture rises to 0.60, and the net arithmetic turns positive. Weekly tranching is the fastest defensible frequency (mine_math bottom line). This design accepts that verdict completely.

---

## 2. Exact rules

### 2.1 Signal source

- **Table:** `Data/loop/asado_loop.duckdb` → `combiner_scores_daily` (tidy schema: `date DATE, country VARCHAR, value DOUBLE, variable VARCHAR, source VARCHAR`; single variable `COMBINER_RIDGE_DAILY_V1`, source `combiner`; business days 2005-01-03 → present, 31 countries).
- **Ranks:** use the validated 29-country universe as published in `family_ranks_daily WHERE family='combiner'` (`universe_n = 29`; excludes Taiwan and Saudi Arabia from the raw 31 — Taiwan additionally carries a live D9 ETF-basis flag). Do NOT re-rank the raw 31-country table.
- **Reference query (one day's ranks):**
  ```sql
  SELECT date, country, score, rank
  FROM family_ranks_daily
  WHERE family = 'combiner'
    AND date = (SELECT max(date) FROM family_ranks_daily WHERE family='combiner')
  ORDER BY rank;
  ```
- **Blacklist compliance:** no forward-return variables (`1MRet`/`1DRet` family) touch this strategy anywhere. Returns for monitoring are built from `Tot Return Index` levels on the business-day grid (index) and `etf_prices_daily` closes (tradable), per mine_math §0.

### 2.2 Universe and cost tiers

28 tradable names = validated 29 minus **Denmark/EDEN (excluded: $0.8M/day ADV, 26 bp spread — a $10–14k order is >1.25% of ADV; mine_exec flags it as the single capacity-constrained ticker)**. Cost design inputs from mine_exec §5 (official SEC 6c-11 30-day median spreads + IBKR Pro Tiered commissions, $3–15k clips):

| Tier | One-way design cost | Countries (ETF) |
|---|---|---|
| A-mega | 3 bp | U.S. (SPY), Japan (EWJ), Korea (EWY) |
| A | 5 bp | Canada (EWC), India (INDA), U.K. (EWU), France (EWQ), Germany (EWG), Italy (EWI), Switzerland (EWL), Mexico (EWW), Brazil (EWZ), ChinaA (ASHR), Singapore (EWS), Australia (EWA), Malaysia (EWM), Hong Kong (EWH) |
| B | 10 bp | Poland (EPOL), Vietnam (VNM), Sweden (EWD), Spain (EWP), Netherlands (EWN), Indonesia (EIDO) |
| C | 20 bp | Chile (ECH), Turkey (TUR), Thailand (THD), Philippines (EPHE), South Africa (EZA) |
| Excluded | — | Denmark (EDEN); Taiwan (EWT) and Saudi Arabia (KSA) are outside the validated ranks; ChinaH/NASDAQ/US SmallCap are outside the combiner universe entirely |

**Two universe variants:**
- **S1-F (Full, primary as specified here):** all 28 names, with the tier-dependent entry/exit throttles of §2.5. Target blended one-way cost ≤ 6–7 bp (measured monthly ex-post; see kill criteria).
- **S1-L (Liquid-only, contingency):** Tier A + A-mega only (17 names), top-4 instead of top-5. Fundamental-law tilt intensity is ~93% of the full universe **if IC is uniform across names** (Monte-Carlo order statistics: z̄(4 of 20)=1.33, z̄(5 of 29)=1.43 — computed this session; assumption flagged, since combiner alpha may concentrate in the EM names). S1-L's alpha on the restricted universe is **unmeasured — it must be measured (pre-launch study PL-1, §7) before it can carry capital**. S1-L becomes the book automatically if S1-F's measured blended cost exceeds 7 bp for two consecutive months.

### 2.3 Portfolio construction

Faithful to the backtested construction (mine_math §3 code):

1. Each business day t, take the validated ranks. Apply eligibility filters (§2.6).
2. Build the **daily selection vector** using banded membership (§2.5): names currently held stay selected until they breach their exit band; names not held enter when they breach their entry band; the selection always contains exactly 5 names (if bands yield >5, keep the 5 best-ranked among holds-plus-entrants; if <5, fill with best-ranked eligible non-members).
3. Equal-weight the 5 selected names → daily target vector `w_t` (each 1/5 of invested sleeve).
4. **Tranche:** actual target = 5-day rolling mean of the last 5 daily vectors, renormalized. (This is the h=5 overlapping-tranche construction as backtested; it means each day roughly 1/5 of the sleeve migrates toward the newest selection.)
5. Scale by invested fraction 0.70 of NAV. Cash = residual.
6. **Dust filter:** skip any order below $500 or below 0.5% of NAV drift per name; true-up weekly (every Friday) regardless.

### 2.4 Rebalance schedule and time of day

- **Daily, at the US close.** Orders staged 15:35–15:45 ET, submitted as MOC/LOC before the 15:50 ET NYSE cutoff (15:55 Nasdaq-listed). The close is the deepest print, the fill *is* the official close, and it matches the close-to-close backtest convention exactly (mine_exec §3.3).
- **Mode A (required for full economics): same-close execution.** The measured ETF capture (0.60 at h=5) was computed with signal date t → ETF close(t)→close(t+1), i.e., it assumes you trade the close of the same day the signal's inputs complete. All 28 foreign closes for day t occur before 16:00 ET (Asia by ~04:00 ET, Europe by ~11:35 ET); only the Americas inputs (U.S., Canada, Mexico, Brazil, Chile own-returns inside the 21-day windows) are incomplete at 15:40 — a 15:40 snapshot or a t−1 carry-forward for those five is an acceptable approximation because every feature is a 21-day window (one partial day ≈ 1/21 of one input; flagged as a small optimism in §5 monitoring). **This requires a new intraday scoring script** (engineering item E-1, §8) because the production pipeline computes scores only in the nightly job.
- **Mode B (fallback, and the launch default for paper): T+1 close.** Trade today's close on yesterday's official nightly scores. Economics degrade: full-sample index-based h=5 gross drops from +12.9%/yr to +8.1%/yr (skip-1 row, mine_math §3) — but the skip-1 haircut and the ETF-capture haircut overlap heavily (both measure "the ETF already priced it"; mine_math notes capture 0.36 ≈ skip1 ratio 0.39 at h=1), so applying both fully would double-count. The Mode A vs Mode B gap **in ETF space is unmeasured** — the paper phase runs both modes in parallel precisely to measure it (§6).
- No intraday trading, no opening trades, ever (spreads 2–5× wider at the open).

### 2.5 Entry/exit bands and turnover throttles (tier-aware)

Rank-hysteresis bands make expensive names sticky and cheap names nimble:

| Tier | Enters selection when rank ≤ | Exits selection when rank > | Minimum residence |
|---|---|---|---|
| A-mega / A | 5 | 10 | none |
| B | 4 | 12 | 10 trading days |
| C | 3 | 14 | 15 trading days |

Rationale: a Tier C round trip costs ~40 bp; amortized over a 15-day minimum residence that is ≤2.7 bp/day — comparable to Tier A daily-band churn. Plain (unbanded) top-5 h=5 turnover is the measured 0.148/day one-way; banding is **estimated** (not measured) to cut it by ~30–45% at modest alpha cost — pre-launch study PL-2 (§7) must measure the banded variant's alpha/turnover on the full 2005–2026 grid before the paper phase locks parameters. The no-trade dust filter (§2.3.6) removes the long tail of sub-$500 tranche drifts.

**Hard turnover throttle:** if realized one-way turnover exceeds 0.20/day averaged over any rolling 21 days, widen all exit bands by 2 ranks until it falls below 0.15.

### 2.6 Eligibility overlays (pre-registered, mechanical, and few)

1. **Staleness gate:** if `max(date)` in `combiner_scores_daily` (Mode B) or the intraday recompute (Mode A) is older than the last business day, **no trading today** — hold the current book. Never trade ranks older than T+1.
2. **Governance gate:** if the nightly 7-dimension governance scorecard is not GREEN, hold (no new trades) until it is.
3. **Downgrade exclusion (validated event overlay):** any EM country with a sovereign rating downgrade (`sov_rating_changes`) in the past 63 trading days is ineligible for entry (validated EM drift −0.9%@5d / −2.8%@63d). Currently binding: Mexico/EWW (Moody's 2026-06-01) ineligible through ~end-August 2026. Existing positions are not force-sold; they simply exit via normal bands.
4. **Nothing else.** The live cross-section is full of tempting discretionary overlays (Indonesia's +3.14z inflow headwind, Turkey short interest, DXY z +2.07). S1 stays mechanical; conflicted-signal sizing belongs to other sleeves of the book. Contrarian-flow vetoes are explicitly rejected (ETF_FLOW_21D_Z is sign-unstable, BE <4 bp — mine_ledger).

### 2.7 Cash rule

- Fixed structural cash: **30% of NAV** ($30k). Justification is measured, not aesthetic: the 70/30 dial cut the simulated maxDD from −43.2% to −31.7% at *identical* Sharpe (0.72) — mine_math §4. Cash is the only hedge in a long-only book.
- Cash sits in USD at IBKR Pro (~BM−0.5% on balances above $10k; ≈3.1–3.8% quoted mid-2026 → roughly $680–800/yr on $30k after the $10k zero-yield band, ≈0.7% of NAV).
- **Defensive step-down (mechanical):** if the invested sleeve's drawdown vs its own high-water mark exceeds 25%, reduce invested fraction to 50% until drawdown recovers to <15%. (Design parameter, inspired by but not identical to the sim; flagged as an assumption — PL-2 backtests it.)

### 2.8 Worked example — the book as of the 2026-06-30 cross-section

Validated ranks (queried live): 1 Indonesia, 2 Turkey, 3 Hong Kong, 4 Poland, 5 Brazil, 6 Philippines, 7 U.S., 8 India … 29 Netherlands. Applying §2.5 bands to a fresh start (no incumbents): EIDO (B, rank 1 ≤ 4 ✓), TUR (C, rank 2 ≤ 3 ✓), EWH (A, rank 3 ≤ 5 ✓), EPOL (B, rank 4 ✓), EWZ (A, rank 5 ✓). Mexico is ineligible anyway (downgrade window). Target sleeve at $100k NAV, 70% invested, $14k/name:

| ETF | Tier | Price (07-01) | ~Shares | % of ADV |
|---|---|---|---|---|
| EIDO | B | $11.45 | 1,222 | 0.08% |
| TUR | C | $39.34 | 355 | 0.12% |
| EWH | A | $20.93 | 668 | 0.02% |
| EPOL | B | $39.44 | 354 | 0.08% |
| EWZ | A | $34.43 | 406 | 0.001% |

Blended one-way cost of this particular cross-section ≈ (10+20+5+10+5)/5 = **10 bp** — a live illustration of why the throttles exist: this is an unusually EM/expensive top-5, and the residence minima ensure these entries are amortized over ≥10–15 days. Note EIDO also carries the open paper thesis at −5.7% vs a −7% kill and a +3.14z inflow headwind — S1 buys it anyway (mechanical rule; see §2.6.4), and this tension is exactly what the paper phase is for.

---

## 3. Expected performance — honest arithmetic

Every number below is from mine_math (measured) unless labeled assumption.

**The chain, active return vs EW-29, fully-invested basis:**

| Step | Value | Source |
|---|---|---|
| Gross ceiling, top-5 h=5, index returns, 2005–2026 | +12.9%/yr (5.1 bp/day, NW-t 9.0, IR 1.76) | mine_math §3 |
| Recent-regime decay (2016+ h=5 gross) | +7.4%/yr (~0.57×) | mine_math §3a |
| ETF capture at h=5 (13-month measured window) | ×0.60 | mine_math §3c |
| **Realistic forward gross** | **+4.4%/yr (conservative: decay×capture) to +7.7%/yr (optimistic: full-sample×capture)** | mine_math §4 table |
| Cost at 0.148/day one-way turnover | −3.7%/yr at 5 bp; −7.5%/yr at 10 bp | 252×2×0.148×c |
| **Net active, 100% invested** | **+0.7% to +4.0%/yr at 5 bp; −3.0% to +0.3%/yr at 10 bp** | mine_math §4 |
| Scaled to 70% invested | **+0.5% to +2.8%/yr of NAV at 5 bp blend** | arithmetic |

Banding (§2.5) shifts the cost line down (est. turnover 0.09–0.10/day → −2.3 to −2.6%/yr at 5 bp) at some gross give-up — **net effect to be measured in PL-2, assumed roughly to offset**. The blended-cost target of ≤6–7 bp (given B/C participation) puts the central estimate of net active at **≈ +1 to +2%/yr of NAV ($1,000–2,000 on $100k)**. That is the honest size of the flagship edge after every measured haircut. It is small. It is also the strongest validated surface the warehouse has.

**Total book expectation (70/30, $100k):**

| Metric | Expectation | Source |
|---|---|---|
| Total return | **~8–11%/yr** ($8–11k) | mine_math §4 bottom line (EW base 7.7%×0.7 + cash ~0.7–1.0% + net active) |
| Volatility | ~13% | 70/30 sim: 12.9% |
| Sharpe | **~0.55–0.75** | mine_math §4 (sim 0.72 is the ceiling; lit haircut to 0.55+) |
| Max drawdown | **~−30%** | 70/30 sim −31.7%; must be expected, not feared |
| Benchmark (EW-29 fully invested, 2015+) | 7.7%/yr, Sharpe 0.44, maxDD −29% | mine_math §1 |

**Cross-check from the outside view (mine_lit):** stacked haircuts for ML-selected composites (~30% OOS decay) plus the long-only ~50% capture imply realistic net active IR of 0.3–0.8 for daily country signals at retail cost — the +1–2%/yr on ~4–5% active vol tracking error sits at IR ≈ 0.25–0.45, the conservative end. Consistent, not contradicted.

**What this sleeve is really for:** the active return pays for the discipline, but most of the P&L is the EW country-beta base (7.7%/yr) with a measured drawdown-management dial. Anyone expecting the backtest's IR 1.76 in an ETF account has not read §3c of mine_math.

---

## 4. Capital & sizing

- **Allocation: $100k — this sleeve IS the core book** in the flagship-only configuration; if the book runs multiple sleeves, S1 takes **60% ($60k: 5 × $8.4k positions + $18k cash pro-rata)** and remains the largest single sleeve. All numbers in §2–3 scale linearly.
- Position size $14k (or $8.4k in the 60% config). Every position ≤0.12% of ADV except EPHE (0.48% worst case) — no capacity issue at one or even fifty times this size; mine_exec: "impact is negligible; the spread is the whole game."
- Fractional shares enabled (needed only if SPY/EWY enter; $14k SPY = 18.8 shares — fine even without fractionals, but enable anyway).
- Margin-type account at zero leverage so T+1 settlement never blocks re-entry; PDT irrelevant above $25k.
- Tax note (one line, per mine_exec): this turnover profile is short-term-gains heavy — it belongs in an IRA if available; in a taxable account the after-tax active edge may not survive.

## 5. Risks & failure modes (top 5, each with a detection signal)

1. **Forward IC collapse (the in-sample ceiling problem).** Components were chosen 2026-06 from the same harness that scores them; the full-sample IR is partly self-selected. The 2021–26 subperiod (7.0 bp/day gross h=1, t=4.3) says the mechanism is real recently, but the blend weights are still untested forward. *Detection:* rolling 63d realized ETF-based rank IC published daily in monitoring; paper-phase gates (§6). *This is the #1 risk and the reason no live dollar moves before the paper gates pass.*
2. **Cost bleed above model.** The live top-5 skews EM/Tier B-C (today's blend: 10 bp); spreads widen in stress exactly when the signal trades most; LOC partial fills in TUR/EPHE force chasing. *Detection:* per-trade TCA log (fill vs official close, §8); monthly blended one-way cost print. Trigger: >7 bp blended for 2 consecutive months → automatic switch to S1-L (Tier A only).
3. **ETF-capture erosion.** The 0.60 capture was measured on 13 months of `etf_prices_daily`; US-hours fair-value models keep improving, and Levy–Lieberman over-embedding implies the residual can shrink toward zero (or even invert to a fade). *Detection:* quarterly re-run of the mine_math capture measurement on the growing ETF-close history; capture <0.40 at h=5 for two consecutive quarters → treat as kill-level structural change.
4. **Correlated-diffusion regime break / EM beta concentration.** All six market-derived components are one mechanism (return diffusion); they will die together in a global risk-off, and the top-5 is often 3–5 EM names — a dollar spike (DXY z +2.07 right now) hits all of them at once. The −30% expected maxDD is the base case, not the tail. *Detection:* invested-sleeve drawdown vs EW-29 gap >8% over 126d (alpha drawdown, distinct from beta drawdown); the §2.7 mechanical de-risking step-down; DXY/VIX flags logged but NOT traded (no discretionary overrides).
5. **Operational staleness / silent pipeline drift.** Combiner is T+2 today (2026-06-30 scores on 2026-07-02); the nightly job failing quietly, or the `live_signals` registry inconsistency (all 16 hypotheses show effective_verdict=INSUFFICIENT_COVERAGE despite a green scorecard — mine_livedb §7), means the book could trade stale or ungoverned ranks. *Detection:* the §2.6 staleness + governance gates fail-closed (hold, don't trade); weekly reconciliation of registry vs harness digest is a pre-launch blocker (§7).

Also monitored (below top-5): single-name geopolitical gaps in Tier C EM (Turkey capital-controls risk — mitigated by the 14% cap and equal-weighting, not otherwise hedgeable long-only); crowding via CORO-style products (watch CORO AUM quarterly).

## 6. Kill criteria — pre-registered, forward-looking

**Phase P (paper, mandatory, target 6 months / minimum 126 trading days).** Run Modes A and B in parallel as paper books; log everything as if live (simulated MOC fills at official closes, cost model 3/5/10/20 bp by tier).

| Gate | Metric | Window | Threshold | Action |
|---|---|---|---|---|
| P-kill (early) | Mean daily rank IC, scores vs ETF close-to-close forward returns, 28 names | first 63 td | < −0.01 | Abandon; return to harness |
| P-go | Same IC | 126 td | ≥ +0.015 | Proceed to Phase L at half size |
| P-go (P&L) | Paper net active vs EW-28, Mode A | 126 td | > 0 | Required jointly with IC gate |
| P-mode | Mode A minus Mode B paper active | 126 td | informational | Sets the value of the intraday recompute; if ≤0, run Mode B live (simpler ops) |

Power arithmetic (assumption, stated): daily cross-sectional rank IC noise ≈ 1/√28 ≈ 0.19/day; over 126 days, se ≈ 0.017. If the true forward IC is the decayed ~0.03, the P-go gate at 0.015 is ~0.9 se below truth (reasonable power); if the truth is 0 (pure overfit), passing probability ≈ 19% — one-in-five false-go, which the L-phase ramp then contains. Gates were set before any paper data exists.

**Phase L (live, ramp 50% of target sleeve for the first 3 months, then full).**

| # | Metric | Window | Threshold | Action |
|---|---|---|---|---|
| L1 | Realized ETF-based rank IC | rolling 126 td | < 0 | Halve invested fraction |
| L2 | Realized ETF-based rank IC | rolling 252 td | < 0 | **Kill sleeve** (revert to EW-28 + 30% cash or all-cash pending review) |
| L3 | Net active vs EW-28 | rolling 252 td | < −4% | **Kill sleeve** |
| L4 | Blended realized one-way cost | 2 consecutive months | > 7 bp | Switch to S1-L (Tier A only) |
| L5 | ETF capture ratio (quarterly re-measurement) | 2 consecutive quarters | < 0.40 at h=5 | **Kill sleeve** (structural) |
| L6 | Annual ridge refit | each Dec vintage | >3 of 7 coefficients flip sign | Freeze trading; structural review before adopting new vintage |
| L7 | Sleeve drawdown | any | −25% from HWM | De-risk to 50% invested until <−15% (per §2.7) |

Kill means kill: no re-entry without a fresh harness verdict on out-of-sample data and a new PRD. The −4%/252td active threshold ≈ 2× the central net-active expectation to the downside; the IC thresholds are the primary (they detect signal death faster than P&L does).

## 7. Governance

**Backing hypotheses (verified in `hypothesis_ledger`, family `ml_combiner_2026_06`):**
- **H_20260612_054** — the operative verdict: daily ridge on the coverage-corrected 29-country universe, primary horizon **5d** (matching this design's hold), mean IC 0.0574, NW-t 10.726, verdict **WEAK** (deflated Sharpe −0.104 after 59 burned trials — the ledger's honest multiple-testing charge; nothing in the warehouse has ever exceeded WEAK).
- H_20260612_053 (31-country daily, INSUFFICIENT_COVERAGE), H_20260612_050/051/052 (monthly variants — DEAD/insufficient; the monthly combiner is explicitly not used).
- Component verdicts: 12 WEAK graph-family verdicts, 2/2 twins, CPI-revision t 2.31, flipped inflation surprise t 2.99, contrarian flows t −2.2 (mine_ledger). PIT edge re-test passed for the graph family.

**Pre-launch registrations required (before any live dollar; each charges a trial to `ml_combiner_2026_06` — accepted):**
- **NT-1 (harness trial):** COMBINER_RIDGE_DAILY_V1 restricted to the Tier-A 17-name universe (`combiner_scores_daily` filtered to Tier A countries), direction long-high-score, primary horizon 5d, mechanism unchanged (diffusion, liquid subset). This is the S1-L variant's license and pre-launch study **PL-1**.
- **NT-2 (harness trial, expected INSUFFICIENT_COVERAGE by design):** same signal scored against **ETF forward returns** from `etf_prices_daily` (13 months and growing). Registers the tradability question formally so coverage accumulates under a fixed ID rather than being re-decided ad hoc.
- **PL-2 (engineering study, not a hypothesis — portfolio construction, no new signal):** banded top-5 h=5 backtest on the 2005–2026 index grid measuring the turnover/alpha trade of §2.5's bands, the §2.7 step-down, and locking final parameters. Run with the mine_math machinery; results filed alongside this design before paper start.
- **Registry reconciliation (blocker):** resolve the `live_signals` view showing effective_verdict=INSUFFICIENT_COVERAGE for all 16 registered hypotheses vs the harness digest (mine_livedb §7) — a book "backed by H_20260612_054" must be able to point at a registry that agrees.

**Ongoing governance:** nightly scorecard GREEN required to trade (§2.6.2); paper thesis for S1 opened in `thesis_ledger` at paper start with the §6 gates as its invalidation terms; monthly FF style-spanning (`scripts/harness/ff_spanning.py`) on the sleeve's paper/live active P&L — the sleeve must show alpha not explained by regional Mkt/SMB/HML/RMW/CMA/WML bundles, reported with NW HAC t; every parameter change after paper start is a new registered variant, never an in-flight edit.

## 8. Implementation sketch

**Data dependencies (must have run before the 15:35 ET session):**
- Nightly `scripts/loop/loop_daily_job.py` steps: graph PIT features (`build_graph_features_pit.py`), similarity (`build_similarity_features.py`), lead-lag, **`build_combiner.py`** (writes `combiner_scores_daily` + `family_ranks_daily`), ETF flows load, consensus load, dislocation build (for the scorecard), governance scorecard.
- `sov_rating_changes` current (for the downgrade filter); `etf_prices_daily` (for TCA and monitoring); `etf_t2_map` (country→ticker, verified to match this design's map).
- **E-1 (new, required for Mode A): intraday scoring script** — recompute the 7 features and apply the current `combiner_weights` vintage at ~15:30 ET using foreign closes of day t (Asia/Europe final; Americas inputs at t−1 carry-forward or 15:30 snapshot), emitting a same-day rank file. Read-only against both DBs; writes only to a strategy-local directory (never to the loop DB — the loop DB stays pipeline-owned).
- **E-2 (new): order generator + TCA logger** — computes target weights (§2.3), diffs against IBKR positions, applies dust/band/residence rules, emits the order list, and logs fills vs official closes.

**IBKR plumbing:**
- Account: IBKR Pro, Tiered pricing, margin type, zero leverage, fractional shares enabled.
- Orders: **MOC** for Tier A/A-mega; **LOC with a limit band of ~±25 bp (B) / ±50 bp (C) around the 15:45 mid** for Tier B/C (protects against thin closing auctions; accept occasional partial fills — unfilled remainder re-attempted next day, residence clocks unaffected). Submit 15:45 ET; NYSE MOC/LOC cutoff 15:50 ET.
- Never market orders; never trade the first 30 minutes; no intraday adjustments between closes.

**Monitoring (all logged to flat files in the strategy directory, reviewed on cadence):**
- **Daily (pre-trade):** freshness gate (combiner date = last business day), governance scorecard status, band/residence state dump, order list with expected cost.
- **Daily (post-close):** fills vs official close (TCA), realized position weights, sleeve NAV, rank IC accrual.
- **Weekly:** rolling 63d IC, turnover, blended cost vs 7 bp budget, Mode A vs Mode B paper gap.
- **Monthly:** FF spanning on active P&L; downgrade-filter roster; ridge-vintage check; kill-criteria dashboard (every §6 row with current value vs threshold).
- **Quarterly:** ETF capture re-measurement (mine_math §3c machinery on the growing `etf_prices_daily` history); CORO AUM crowding check; sub-period IC decay update.

**Build order:** PL-2 + NT-1/NT-2 registrations → E-1/E-2 scripts → registry reconciliation → paper phase (both modes, ≥126 td) → P-gates → live ramp at 50% → full size. No step skipped, no step reordered.

---

## Appendix — honesty ledger (what is measured vs assumed)

| Claim | Status |
|---|---|
| IC 0.0552–0.0574, NW-t ~10.7, 95% positive years | Measured twice (harness H_054; mine_math independent) |
| h=5 top-5 gross +12.9%/yr, TO 0.148/day, net +9.2/+5.5% at 5/10 bp | Measured (mine_math §3, full sample, index) |
| Decay to 7.0–7.4 bp-class gross post-2016/2021 | Measured (sub-periods) |
| ETF capture 0.60 at h=5 | Measured on 13 months only — the single thinnest measured input; quarterly re-measurement is mandatory |
| Tier cost inputs 3/5/10/20 bp | Measured (official 6c-11 spreads + IBKR fee schedule, mine_exec) |
| Banding cuts turnover 30–45% at small alpha cost | **Assumption — PL-2 must measure before paper** |
| S1-L (Tier-A-only) alpha ≈ 93% of full-universe tilt intensity | **Assumption (order-statistic bound, uniform-IC premise) — NT-1 must measure** |
| Mode B (T+1) degradation in ETF space | **Unmeasured — paper phase measures it** |
| 25%-DD step-down parameters | Design assumption, PL-2 backtests it |
| Net active +0.5 to +2.8%/yr NAV; total 8–11%/yr, Sharpe 0.55–0.75, maxDD ~−30% | Arithmetic from measured inputs, per mine_math §4; treated as a ceiling until paper confirms |
