# S2 — THE SLOW BOOK
## A monthly-tranched, long-only composite sleeve from the PIT-validated slow cross-sectional families

**Designer:** Strategy designer, phase 2 (angle: slow book) | **Date:** 2026-07-02 (v1.1, second-pass verification same day) | **Status:** design, hypothetical $100k IBKR account, NOT live trading

**v1.1 changes (second pass, 2026-07-02 evening):** all component tables/variables re-verified against the live loop DB (`s2_verify.py`); reference implementation `slowbook_compute.py` (same directory) aligned 1:1 to Sections 2.3–2.5 (an earlier draft of that script had drifted weights — the weights in this document are the registered spec, and are the ones the S8 portfolio architect adopted); added per-tranche shared-macro group caps (Section 2.4); added V2b upgrade new-buy block (Section 2.5) on the strength of the documented upgrade-drift event study (−2.4%@63d) and its live specimen (South Africa, Fitch upgrade 2026-07-01); corrected C5b coverage; appendix refreshed with the doc-spec live ranking.

**Evidence base (all read-only, verified this session):**
- Loop DB `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb` — schemas and live cross-sections of `graph_features_pit_daily`, `similarity_features_daily`, `sovereign_signals`, `consensus_signals`, `eco_surprise_signals`, `etf_flow_signals`, `family_ranks_daily`, `sov_rating_changes` queried 2026-07-02
- Miner reports: `mine_ledger.md` (harness verdicts, cost table), `mine_math.md` (ground-truth return math, ETF capture), `mine_exec.md` (spread tiers, IBKR plumbing), `mine_livedb.md` (freshness, live cross-section), `mine_docs.md` (governance), `mine_lit.md` (outside corroboration) — all in this directory

---

## 1. Thesis — what the data knows that the ETF price doesn't

**The edge: cross-country return diffusion measured through slow relationship graphs, plus a slow reflation-expectations channel.** Concretely:

1. **Graph spillover (banking + trade networks).** When a country's trade partners and bank creditors/debtors have already repriced (up or down) over the past 21 days and the country itself has not, the country converges toward its neighbors over the following weeks. This is the single most robust finding in the ASADO ledger: 12 WEAK verdicts across trade/bank/two-hop/Katz/hub/bloc specifications, NW-t 2.5–5.7, IC 0.014–0.041, positive in both sample halves, and — critically — it **survived the point-in-time edge re-test** (`GRAPHP_` vintages, so no edge-weight lookahead). Best single expressions: PIT bank-claims neighbor gap 21d (H_20260612_041: IC 0.034, NW-t 4.5, 17–21 stable-BIS countries, 2008+) and PIT two-hop trade gap 21d (H_20260612_035: IC 0.025, NW-t 4.4, 30–31 countries, 2001+).
2. **Fundamental twins.** Same convergence mechanism on a different graph: countries that look alike on fundamentals (similarity graph, not trade flows) converge when their twins have outrun them over 63 days. `SIM_NBR_RET_GAP_63D` (H_20260612_043) is the **best slow-hold economics in the entire ledger**: breakeven 18.3 bps one-way at 21d hold, net long-short Sharpe +0.17 at 10 bps, full 34-country universe, 2001+, positive both halves, least deflation damage of any completed run (DS −0.029).
3. **Sovereign curve steepness.** `SOV_2S10S_Z252` (H_20260612_013) was verdicted DEAD at its 5-day primary horizon but the harness's own hold-grid shows breakeven 15.8 bps and net-10bps Sharpe +0.08 **at 21d hold** — a real slow steepener tilt the 5d verdict rule under-credits (ledger loose end #2). Steep local curves encode growth/reflation expectations that country equities absorb over weeks, not days.
4. **Reflation overlay (WEAK tier, monthly).** CPI consensus revision momentum (`CONS_CPI_REV3M_12M`, H_20260612_029/_032: IC 0.039, NW-t 2.31, 2013+, 159 monthly obs) and the flipped inflation surprise (`ECO_INFL_SURPRISE_Z` higher-is-better, H_20260612_015: IC 0.036, NW-t 2.99) point the same direction: **in this universe, hot/rising inflation expectations have been a reflation/growth signal, not a de-rating signal.** The ledger explicitly says to treat these as ONE overlay, not two discoveries — this design does exactly that.
5. **Contrarian ETF-flow veto.** Big 21d ETF inflows precede underperformance (H_20260612_046, NW-t −2.2), corroborated by the dumb-money literature (mine_lit). Its breakeven is under 4 bps and its sign is unstable — dead for standalone trading — so it is used here **only as an entry veto**, which costs zero turnover.

**Why does the edge exist and who is on the other side?** Country ETF prices are set in US hours largely by US-centric flows (asset allocators, model portfolios, retail) that watch the country's own price and headline news, not its position inside the trade/banking/similarity network. Nobody's Bloomberg screen shows "your bank creditors just repriced +7% and you didn't." The information is public but requires assembling BIS bilateral claims, IMF trade matrices, and a fundamental-similarity graph — a data-engineering moat, not an information-access moat. It persists because (a) the per-name edge is small (a few bps/day) and decays over weeks, so it cannot absorb institutional size in the thin half of the ETF universe; (b) the natural arbitrageurs (macro funds) trade the liquid futures subset, not EPHE/ECH/EZA; (c) Jacobs & Muller (JFE 2020, cited in mine_lit) show country-level anomalies do NOT decay post-publication the way US anomalies do — limits to arbitrage are structural. The reflation channel persists because consensus economists revise slowly and equity investors treat inflation as unconditionally bad, while in a 34-country cross-section the hot-inflation names have been the recovering-demand names (2013–2026 sample; regime caveat in Section 5).

**Why the slow expression specifically?** Three measured facts force it: (i) nothing survives 25 bps one-way and only ~4 signals clear 10 bps — the slow signals are the only ones whose breakevens (15.8–18.3 bps at 21d) sit ABOVE realistic all-in costs for the full 34-ETF universe including the 20 bp tier; (ii) mine_math's ETF-capture measurement: US-listed ETFs already embed ~64% of next-day foreign-index alpha at 1d holds (capture 0.36) but capture recovers to 0.60 at 5d and an extrapolated ~0.75–0.85 at 21d — **slow holds are where the tradable share of the alpha lives**; (iii) 21d holds amortize a 20 bp one-way cost to ~1 bp/day, which is why this is the only sleeve that can own the wide-spread names (EZA, EDEN, EPHE, THD, TUR, ECH) at all. This sleeve is the book's ballast: it is the expression that still works if the fast (combiner) alpha decays, because it is built from individually PIT-verified components, not an in-sample-selected ML composite.

---

## 2. Exact rules

### 2.1 Signal sources (loop DB, exact table/variable names — verified 2026-07-02)

All tables are tidy `(date, country, value, variable, source)` unless noted. All components below are **higher-is-better** after the orientation stated.

| # | Component | Table | Variable | Orientation | Coverage (latest) | Backing |
|---|---|---|---|---|---|---|
| C1 | Twins gap 63d | `similarity_features_daily` | `SIM_NBR_RET_GAP_63D` | higher = better | 34 | H_20260612_043 WEAK |
| C2 | PIT bank-network gap 21d | `graph_features_pit_daily` | `GRAPHP_BANK_NBR_RET_GAP_21D` | higher = better | 21 | H_20260612_041 WEAK |
| C3 | PIT two-hop trade gap 21d | `graph_features_pit_daily` | `GRAPHP_TWOHOP_TRADE_GAP_21D` | higher = better | 30 | H_20260612_035 WEAK |
| C4 | Sovereign 2s10s z | `sovereign_signals` | `SOV_2S10S_Z252` | higher (steeper) = better | 26 | H_20260612_013 (21d re-registration required, Section 7) |
| C5a | CPI consensus revision | `consensus_signals` | `CONS_CPI_REV3M_12M` | higher = better | 33 | H_20260612_029/_032 WEAK |
| C5b | Inflation surprise (flipped) | `eco_surprise_signals` | `ECO_INFL_SURPRISE_Z` | higher = better | ~30 within 75d staleness (monthly, stale-by-design; 9 at the single latest stamp) | H_20260612_015 WEAK |
| V1 | Flow veto | `etf_flow_signals` | `ETF_FLOW_21D_Z` | veto if > +2.0 | 33–34 | H_20260612_046 WEAK (contrarian) |
| V2 | Downgrade veto (hard) / upgrade new-buy block (soft, V2b) | `sov_rating_changes` | rating change events (`delta` sign) | veto 63 trading days after a downgrade; block NEW buys 63td after an upgrade | 20 rated | event studies: EM downgrade −0.9%@5d / −2.8%@63d; upgrades −2.4%@63d |
| V3 | CDS-inversion veto | `sovereign_signals` | `SOV_CDS_SLOPE_BP` < 0 | veto while inverted | ~20 | event study: −4.5%@63d, 41 events, t=−2.4 |

Deliberate exclusions: only ONE of the correlated trade-cluster variants (twohop) is used — Katz/hub/bloc/plain-trade are ~the same idea (mine_ledger Section 3) and stacking them would fake diversification. `LL_LEADER_GAP_5D` is excluded (local-index tradability trap, measured capture 0.36 at short holds — mine_math Section 3c). The daily combiner is excluded from the core spec (it belongs to the fast sleeve and its components were selected in-sample); an optional variant is noted in Section 2.8. Valuation, FX surfaces, momentum, short interest: DEAD in the ledger, not used.

### 2.2 Universe

All 34 US-listed country ETFs per the fixed map (Australia EWA ... Vietnam VNM), including the wide-spread tier-C names — the whole point of the slow sleeve is that 21d holds amortize a 20 bp one-way cost to ~1 bp/day. Cost tiers from mine_exec (design inputs, all-in one-way): A-mega 3 bp (SPY QQQ IWM EWJ EWT EWY), A 5 bp (16 names), B 10 bp (EPOL VNM EWD EWP EWN EIDO), C 20 bp (ECH TUR THD EPHE EDEN EZA). **EDEN special handling:** eligible (monthly-cadence trades only) but always executed with resting limit orders worked over hours, never marketable; ADV is only $0.8M/day.

### 2.3 Composite score (the ONE rank)

At each tranche rebalance date t, using the most recent available row per (country, variable) with `date <= t` (staleness gates in Section 2.6):

1. For each component C1–C4 and C5a/C5b separately: cross-sectional z-score across available countries — `z_i = (x_i − mean_cs) / std_cs` — then clip to [−3, +3].
2. Reflation subscore: `z_C5 = mean of available {z_C5a, z_C5b}` (either alone if the other is missing for that country; C5b coverage is thin by design).
3. Composite (weights frozen at registration; renormalize over the components present for that country):

```
COMPOSITE = 0.30 * z_C1 (twins 63d)
          + 0.20 * z_C2 (bank gap 21d)
          + 0.15 * z_C3 (twohop trade gap 21d)
          + 0.15 * z_C4 (sov 2s10s z252)
          + 0.20 * z_C5 (reflation overlay)
```

Weight rationale (evidence-ranked, decided before any composite backtest): C1 gets the most because it has the best 21d-hold economics in the ledger (BE 18.3, net10 +0.17) and full 34-country coverage; C2 has the strongest graph t-stat (4.5) but only 21 countries; C3 is the broadest PIT trade-cluster representative; C4 is the independent rates-channel mechanism but carries a DEAD-at-5d verdict (weight capped accordingly); C5 is WEAK-tier and thin-sample, capped at 0.20 combined.

4. Eligibility: a country must have **C1 present plus at least 2 of {C2, C3, C4, C5}** (renormalized weights otherwise); C1 covers all 34 daily, so in practice everything is scored.
5. Vetoes applied AFTER ranking (Section 2.5).

Missing-data note (house rule compliant): a component missing for a country is neutral-by-renormalization, never imputed as a fake value; the pre-trade report logs which components were missing per name. Cross-check surface: `family_ranks_daily` carries `oriented_score`/`rank` for families `twins`, `graph_bank`, `graph_twohop`, `cpi_rev`, `etf_contra` — the implementation must reconcile its component ranks against that table nightly and alert on rank-correlation < 0.9 (guards against silent orientation bugs; orientation verified this session: twins rank 1 = Indonesia = highest gap = long).

### 2.4 Portfolio construction and rebalance schedule

- **Two staggered tranches, each 50% of sleeve capital.** Tranche A rebalances on the **1st business day of each month**; Tranche B on the **11th business day of each month**. Each tranche therefore holds ~21 business days — exactly the hold period at which C1/C4 breakevens were measured — and the staggering halves timing luck and smooths turnover (this replicates the overlapping-tranche construction the harness and mine_math used for h=21).
- **Each tranche buys the top 8 eligible names by COMPOSITE, equal-weighted** (12.5% of tranche = 6.25% of sleeve per slot). A name in both tranches holds up to 12.5% of the sleeve. Expected distinct holdings: 9–13 names (slow signals overlap heavily between tranches).
- **Buffer rule to cut turnover:** at a tranche rebalance, an incumbent holding is retained if it still ranks in the **top 12** of COMPOSITE; only incumbents falling below rank 12 are sold, replaced by the highest-ranked non-held eligible names. (Standard rank-buffer; cuts churn roughly a third for slow signals at zero expected alpha cost. This is a turnover-control device, not a signal change.)
- **Shared-macro group caps (v1.1):** within a tranche, at most **1 of {ChinaA, ChinaH}** and at most **2 of {U.S., NASDAQ, US SmallCap}** may be selected (highest-ranked wins; the skipped name's slot passes to the next eligible country). Rationale: China macro data is broadcast to both China lines and US data to all three US lines (`config/country_mapping.json` rules), so their C2–C5 inputs are near-identical — without a cap, top-8 selection can put 25–37% of a tranche on one macro bet dressed as diversification. Live illustration (2026-07-02): ChinaA #3 and ChinaH #4 rank adjacently; the cap keeps ChinaA and passes ChinaH's slot down. This is a selection-time risk control, not a signal change; the account-level per-ticker caps in the S8 architecture sit above it.
- No position may exceed 12.5% of sleeve NAV (automatic by construction). No shorts, no leverage, no derivatives.

### 2.5 Vetoes and the cash rule

Applied at each tranche rebalance, in order:

1. **V2 downgrade veto (hard):** any country with a sovereign rating downgrade event in `sov_rating_changes` (`delta < 0`) within the past 63 trading days is ineligible; if held, it is SOLD at this rebalance. (Live example: Mexico, Moody's 2026-06-01 — EWW is untouchable until ~end-August.) Grounded in the validated EM downgrade drift (−2.8%@63d).
2. **V2b upgrade new-buy block (soft, v1.1):** a country with a rating UPGRADE (`delta > 0`) within the past 63 trading days cannot be NEWLY bought (incumbents may be retained under the buffer rule — upgrades are not forced sales because the upgrade-drift evidence, −2.4%@63d, is an event-study average without the downgrade study's EM/DM split, so it earns a zero-turnover block, not a liquidation). Live example: South Africa, Fitch upgrade 2026-07-01 — EZA (rank 12 on 2026-07-02) is un-buyable until ~end-September.
3. **V3 CDS-inversion veto (hard):** any country whose `SOV_CDS_SLOPE_BP` (5Y−1Y) is negative at rebalance is ineligible; if held, SOLD. Grounded in the −4.5%@63d inversion event study.
4. **V1 flow veto (soft):** a name with `ETF_FLOW_21D_Z` > +2.0 cannot be NEWLY bought this rebalance (an incumbent may be retained under the buffer rule). Costs zero turnover; blocks buying into crowding spikes (live example: EIDO at +3.14z on 2026-07-01).
5. **Cash rule:** any tranche slot that cannot be filled — because a top name is vetoed and the next-eligible name has COMPOSITE z ≤ 0 — is held in **cash**. Cash is the only hedge in a long-only book. Expected steady-state cash: 0–20% of sleeve; it is signal-driven scarcity of longs, not market timing (no market-timing signal in this book has ever been validated, so none is used). Sleeve cash earns the IBKR Pro rate (~BM −0.5%; note the account-level first-$10k-earns-zero rule — account cash accounting should pool sleeves).

### 2.6 Data-freshness gate (pre-trade, mandatory)

Rebalance proceeds only if, as of the rebalance morning:
- `similarity_features_daily` and `graph_features_pit_daily` max(date) ≥ t − 3 business days (they run T+1/T+2 off the nightly loop);
- `sovereign_signals` max(date) ≥ t − 2 business days;
- `consensus_signals` has a row for the current month (its convention stamps month-end forward, e.g. 2026-07-31 visible on 2026-07-02 — this is a data-availability stamp, not lookahead: the underlying ECFC survey is published before the stamp; the implementation must use the collector's ingest date, `date <= today`, when in doubt);
- nightly governance scorecard GREEN.

If any gate fails: postpone the tranche rebalance one business day at a time, up to 5; after 5, freeze (hold existing positions, no trades) and alert. Signals with 21–63d formation windows lose almost nothing to 1–3 days of staleness; trading on a broken pipeline loses everything. Never substitute a fallback data source.

### 2.7 Execution — time of day and order types

- **When:** 10:15–11:30 ET on the rebalance day. Europe's home markets are still open (tightest spreads for EWQ/EWG/EWI/EWP/EWN/EWD/EDEN/EWL/EWU per mine_exec), the US open scramble is over, and Asia names are in their stable (structurally wider but calm) US-hours regime.
- **Order types (IBKR Pro, Tiered, SmartRouting):**
  - Tier A / A-mega: marketable limit at NBBO offer (buys) / bid (sells), or IBKR Adaptive.
  - Tier B and C: **midpoint-pegged SMART limit**, patient (recovers 25–50% of quoted spread; on a 20 bp name that is worth ~10x the commission). If unfilled by 15:30 ET, convert to a marketable limit capped at NBBO ± 1 tick; for EDEN only, if still unfilled, roll the residual to the next day's 10:15 window (never MOC — its closing auction is thin).
  - Asia-name sanity check before any B/C-tier clip: compare the ETF's intraday move to the relevant index future (NKY, KOSPI200, FTSE China A50, MSCI Taiwan), NOT iNAV (stale during US hours). Defer a buy if the ETF trades > 75 bp rich to its futures-implied fair value (Petajisto-style premium filter, mine_lit idea 3 — zero-turnover execution alpha); re-attempt next morning.
- Fractional shares ON (needed for SPY/QQQ-class prices at $2.2k slots). Margin-type account at zero leverage so T+1 settlement never blocks re-entry. SEC fee 0.206 bp on sells; commissions ~0.5–2.5 bp/side at these clip sizes (mine_exec worked numbers).

### 2.8 Optional variant (V1.1, not the core spec)

Adding the daily combiner at a 21d hold (`combiner_scores_daily`, top-5, h=21: gross +4.2%/yr index-based, net +2.1% at 10 bp, turnover 0.041/day — mine_math Section 3) as a sixth component at 20% weight (others scaled by 0.8) would roughly double the sleeve's expected gross active. It is excluded from the core spec because (a) its components were selected in-sample 2026-06 (stated ceiling, forward verification pending), and (b) this sleeve's mandate is to be the book that survives if exactly that ceiling collapses. Revisit after two quarters of live combiner forward verification.

---

## 3. Expected performance — honest arithmetic

Every number below traces to a measured stat or is labeled ASSUMPTION.

**Building blocks (measured):**
- Cross-sectional dispersion of monthly (~21bd) returns: 4.3%/month, stable post-2015 (mine_math Section 1).
- Component ICs at 5d: C1 0.019, C2 0.034, C3 0.025, C4 0.010 (rises with hold), C5a 0.039 (monthly), C5b 0.036 (monthly) — mine_ledger master table. Long-short breakevens at 21d hold: C1 18.3, C2 9.8, C3 9.6, C4 15.8 bps.
- Top-8 order-statistic multiplier: z-bar(8 of 29) = 1.175 (mine_math Monte Carlo); for 8 of 34, ~1.24 (ASSUMPTION: interpolated, same method).
- ETF capture of index-based alpha at 21d hold: 0.75–0.85 (ASSUMPTION: mine_math extrapolation from measured 0.36 at h=1 and 0.60 at h=5; not directly measured).
- Long-only tilt captures roughly half of long-short alpha (harness digest rule; the fundamental-law construction below builds the long side directly, so this haircut is embedded rather than double-applied).

**Gross active (fundamental law):** composite 21d-horizon rank IC assumed **0.02–0.03** (ASSUMPTION, anchored: a diversified blend of components with individual 5d ICs 0.010–0.039 that hold up at 21d; deliberately NOT assuming diversification lifts it above the best component). Expected top-8 long-only active per 21d cycle = IC × sigma_cs × z-bar = (0.02–0.03) × 4.3% × 1.24 ≈ **10.7–16.0 bp/cycle → 1.3–1.9%/yr gross, index-based** (12 cycles/yr). Cross-check: mine_math's "blended slow book" row shows +4–6%/yr gross ceiling, but that row includes a combiner-h=21 tier this core spec excludes; strip it and the remainder is consistent with ~1.5–2.5%/yr gross. Take **1.3–2.2%/yr gross index-based** as the honest band.

**ETF capture:** × 0.75–0.85 → **1.0–1.9%/yr gross in ETF space.**

**Costs (measured inputs):** each tranche replaces ~2–3 of 8 names per cycle with the rank-12 buffer (ASSUMPTION: churn estimate for 21–63d-formation signals; monitored live) → one-way turnover ≈ 0.3 × 12 cycles × sleeve = **3.5–5x sleeve NAV per year one-way**. Universe-blended all-in one-way cost at these clip sizes ≈ 7–8 bp (22 names at 3–5 bp, 6 at 10 bp, 6 at 20 bp, midpoint execution; mine_exec design inputs). Annual cost = 2 × (3.5–5) × 7.5 bp ≈ **0.5–0.8%/yr**. This sits comfortably below the component breakevens (the design's central requirement).

**Net active vs equal-weight-34 benchmark: +0.4% to +1.4%/yr, central ~+0.8%/yr.** On a $35k sleeve that is ~$150–500/yr. Stated plainly: the slow book is a modest edge. Its value is that it is the only expression in the whole program whose breakevens exceed its realistic costs across the FULL universe, that it is built from individually PIT-verified parts rather than an in-sample composite, and that it keeps working (or fails cheaply) if fast alpha decays.

**Total sleeve expectation (2015+ regime):** base = top-8-ish subset of the EW universe ≈ EW return 7.7%/yr (Sharpe 0.44, maxDD −29% for EW 2015+; −58% full-sample including GFC — mine_math Section 1) minus ~0.5%/yr average expense ratio drag (index-based numbers ignore ER), plus net active. **Expected total ≈ 7.5–9.0%/yr, vol 16–18% (mild concentration premium over EW's 15.3%), Sharpe ~0.45–0.55, expected maxDD −30% to −40% fully invested.** No validated drawdown-timing mechanism exists in this book; the honest statement is that this sleeve carries near-full country-equity beta and its downside protection is limited to the vetoes (downgrade/CDS-inversion avoidance) and signal-scarcity cash. Whole-book drawdown control belongs to the book-level cash dial (mine_math: 70/30 cuts maxDD by a third at unchanged Sharpe), which is an allocator decision above this sleeve.

---

## 4. Capital & sizing

- **Ask: $35,000 of the $100k** (30–40% band). Rationale: this is the ballast sleeve — big enough to matter and to justify its 24 rebalance events/yr, small enough that the fast sleeve(s), which carry higher expected active return in liquid names, keep the majority of risk capital.
- **Structure:** 2 tranches × $17,500; 8 slots/tranche × ~$2,187/slot. A name held in both tranches = ~$4,375 (12.5% of sleeve, 4.4% of the $100k book).
- **Approximate shares at current prices (mine_exec table):** EWH $20.93 → ~104 sh/slot; EWZ $34.43 → ~64 sh; EIDO $11.45 → ~191 sh; SPY $744.78 → ~2.9 sh (fractional); EDEN $114.67 → ~19 sh; EZA $64.00 → ~34 sh.
- **Capacity:** trivially fine. Worst case is EDEN: a $4,375 double-slot order = ~0.55% of its $0.8M/day ADV — absorbed by a patient resting limit within a session; every other name is < 0.15% of ADV (most < 0.01%). Commissions $0.35–1.00/order are 0.5–2.5 bp — immaterial. The strategy would scale to ~$5–10M before EDEN/EPHE-class names need order-working beyond a day; at $100k nothing binds.
- Tax note (one line, per mine_exec): ~21d holds are all short-term gains — this sleeve is materially better sited in an IRA than a taxable account.

---

## 5. Risks & failure modes (top 5, each with a detection signal)

1. **Single-mechanism concentration.** C1+C2+C3 (65% of weight) are three measurements of ONE idea — return diffusion (mine_ledger: "~10 correlated variants of one mechanism"). A regime that breaks cross-country convergence (decoupling, capital controls, bloc fragmentation) kills 65% of the composite at once. *Detection:* rolling 126bd pairwise rank correlation of C1/C2/C3 cross-sections AND their joint rolling IC; alarm if average pairwise correlation > 0.8 while blended 126bd IC < 0.*
2. **Reflation overlay regime flip.** C5 is validated only 2013+ (159 monthly obs), and the direction was chosen after seeing the data (honestly charged, but still). In a deflationary bust or a 2021-style inflation shock that becomes a tightening panic, hot-CPI-revision countries could underperform hard. *Detection:* 6-month rolling IC of the C5 subscore < −0.05; secondary trigger: VIX z > +2 with DM CPI surprises z < −2 (the 2026-06-30 brief already shows Germany/Netherlands/France cold prints — watch item).*
3. **ETF capture worse than assumed at 21d.** The 0.75–0.85 capture is an extrapolation from 13 months of ETF closes at h=1/h=5 (measured 0.36/0.60). If US-hours pricing embeds slow signals too, realistic gross halves and net goes ~zero. *Detection:* quarterly regression of realized sleeve active (ETF space) on same-period paper active (index space, from `t2_levels_daily` Tot Return Index); capture estimate < 0.5 for two consecutive quarters.*
4. **Execution decay in the wide tier.** EZA (27 bp), EDEN (26 bp, $0.8M ADV), EPHE (20 bp) spreads are the current official 6c-11 medians; stress regimes widen them 2–3x, and this sleeve deliberately owns them. *Detection:* per-fill implementation-shortfall log (fill vs arrival mid); alarm if tier-C average one-way shortfall > 15 bp over a rolling quarter → restrict universe to tiers A+B until re-audited.*
5. **Stale or silently broken pipeline.** Graph/similarity tables already run T+2 in the live DB; the `live_signals` view currently shows all 16 registered hypotheses as INSUFFICIENT_COVERAGE despite a green scorecard (registry/harness mismatch, mine_livedb Section 7) — a warning that surface-level dashboards and ground truth can diverge. *Detection:* the Section 2.6 freshness gate (hard, pre-trade) plus a weekly reconciliation of component cross-sections vs `family_ranks_daily` oriented ranks (rank correlation ≥ 0.9 required).*

Humility flag (not a numbered risk): the diffusion family's only live track record is 2 losing paper theses (Indonesia −5.7%, Hong Kong −2.2% at day 21 of 42). Sample of two, uninformative — but nobody should pretend this family has proven itself forward yet.

---

## 6. Kill criteria (pre-registered)

Benchmark for all criteria: equal-weight 34-ETF portfolio, quarterly rebalanced, same execution assumptions. Measurement starts at first live (or paper) trade.

| ID | Metric | Window | Threshold | Action |
|---|---|---|---|---|
| K1 | Realized composite rank IC (formation score vs 21bd forward ETF total return) | rolling 252bd, evaluated monthly, first evaluation at month 12 | IC ≤ 0 at two consecutive month-ends | KILL sleeve |
| K2 | Net active return vs EW benchmark | trailing 12m | < −1.0 × realized tracking error (TE expected ~4–5%/yr) | HALVE sleeve capital |
| K2b | Same | trailing 12m | < −1.5 × realized TE | KILL sleeve |
| K3 | Realized all-in one-way cost (implementation shortfall + fees) | rolling quarter | sleeve-average > 12 bp, or tier-C average > 25 bp | Restrict to tiers A+B; if still breached next quarter, KILL |
| K4 | Component health: harness re-measure of any component (scheduled semi-annual re-runs) | per re-measure | NW-t < 1.0 → zero that component's weight and renormalize; 3 of 5 components zeroed | KILL sleeve |
| K5 | Pipeline integrity | continuous | governance scorecard non-green > 10 consecutive business days | FREEZE (no trades); owner decides unwind-to-cash vs hold |

Falsification statement: the edge claims composite IC ≈ 0.02–0.03 at 21d in ETF space. Twelve months of live tracking gives ~12 independent 21d cycles per tranche (24 staggered); at IC 0.025 and dispersion 4.3% the expected active is ~+0.8% with TE ~4.5% — one year cannot statistically confirm the edge, but K1 (IC ≤ 0 over a full year) and K2b (−1.5 TE) would each mean the live data looks nothing like the 25-year backtest and the design is falsified, not unlucky. No threshold may be loosened after go-live; tightening is allowed.

---

## 7. Governance

**Existing harness IDs this design stands on:**
- H_20260612_043 `SIM_NBR_RET_GAP_63D` — WEAK (core, 30% weight)
- H_20260612_041 `GRAPHP_BANK_NBR_RET_GAP_21D` — WEAK (20%)
- H_20260612_035 `GRAPHP_TWOHOP_TRADE_GAP_21D` — WEAK (15%)
- H_20260612_029/_032 `CONS_CPI_REV3M_12M` — WEAK (inside C5, 20%)
- H_20260612_015 `ECO_INFL_SURPRISE_Z` flipped — WEAK (inside C5)
- H_20260612_046 `ETF_FLOW_21D_Z` contrarian — WEAK (veto-only use, consistent with the ledger's "dead for stand-alone trading" note)
- Event studies (outside the hypothesis ledger, documented on file 2026-06-12: downgrade_em, cds_inversion, rating_upgrade): EM downgrade drift, CDS-inversion drift, upgrade drift (−2.4%@63d) — used as avoidance vetoes / new-buy blocks only, never as buy signals.

**Components NOT currently covered by a supporting verdict, requiring registration BEFORE any live capital:**

1. **R1 — SOV_2S10S_Z252 at 21d primary horizon.** Current verdict is DEAD (H_20260612_013) at the 5d primary horizon; using it at 15% weight on the strength of its hold-grid row without a registered 21d trial would be exactly the silent re-run the governance forbids. Register: family `bbg_skill_2026_06` (charged to that family's trial count), variable `SOV_2S10S_Z252`, direction higher-is-better, **primary horizon 21d**, mechanism: "sovereign curve steepness encodes local growth/reflation expectations that country equities absorb over weeks; short-horizon verdict under-credits a slow signal." If the trial fails WEAK gates at 21d, C4's weight goes to zero and the composite renormalizes (weights were chosen so the design survives this).
2. **R2 — the composite itself.** Blending is a spec choice and must be charged. Register `SLOWBOOK_COMPOSITE_V1`: new family `slow_composite_2026_07` (requires the owner's trust-root edit to `config/family_registry.yaml` per the constitution), variable = the Section 2.3 formula with weights frozen as written, direction higher, primary horizon 21d, mechanism = cross-country return diffusion + reflation revision. Run it through harness v2.1 (hold grid + breakeven) for the record. Expected outcome: WEAK (deflation will charge the family; that is fine — the purpose is a registered, dated, pre-live record of the exact spec).
3. **R3 (optional, cheap) — CONS_CPI_REV3M_12M sample-extension re-test** (ledger loose end #5): 159 monthly obs is thin; one scheduled re-measure either strengthens or removes half of C5.
4. **Registry reconciliation:** resolve the `live_signals` view showing effective_verdict=INSUFFICIENT_COVERAGE for all 16 registered hypotheses vs the harness digest (mine_livedb Section 7) before go-live.

Constitution compliance notes: no forward-return variables used anywhere (C1–C5, V1–V3 are all trailing/PIT surfaces; the `1MRet`-class blacklist is respected); Triptych/GDELT/JST/valuation/tot_impulse remain context-tier and are not inputs; one primary horizon (21d) per registration; the WATCH→paper→PRD ladder applies before real capital — this document is the strategy-PRD stage, and a paper-trading phase (Section 8) precedes any live order.

---

## 8. Implementation sketch

**Data dependencies (must have run before a rebalance):** the nightly loop job (`scripts/loop/loop_daily_job.py`) steps that build `graph_features_pit_daily` (build_graph_features_pit), `similarity_features_daily` (build_similarity_features), `sovereign_signals` (sovereign daily collectors — currently same-day fresh), `consensus_signals` (ECFC collector), `eco_surprise_signals` (monthly), `etf_flow_signals` (daily), `sov_rating_changes` (BQL ratings), `family_ranks_daily` (cross-check), plus the governance scorecard. The Section 2.6 gate encodes the acceptable staleness per table.

**Signal query (read-only, per rebalance date :t):**

```sql
WITH latest AS (
  SELECT country, variable, value,
         ROW_NUMBER() OVER (PARTITION BY country, variable ORDER BY date DESC) rn
  FROM (
    SELECT date, country, value, variable FROM similarity_features_daily
      WHERE variable = 'SIM_NBR_RET_GAP_63D' AND date <= :t
    UNION ALL
    SELECT date, country, value, variable FROM graph_features_pit_daily
      WHERE variable IN ('GRAPHP_BANK_NBR_RET_GAP_21D','GRAPHP_TWOHOP_TRADE_GAP_21D')
        AND date <= :t
    UNION ALL
    SELECT date, country, value, variable FROM sovereign_signals
      WHERE variable IN ('SOV_2S10S_Z252','SOV_CDS_SLOPE_BP') AND date <= :t
    UNION ALL
    SELECT date, country, value, variable FROM consensus_signals
      WHERE variable = 'CONS_CPI_REV3M_12M' AND date <= :t   -- see stamp-convention note, Sec 2.6
    UNION ALL
    SELECT date, country, value, variable FROM eco_surprise_signals
      WHERE variable = 'ECO_INFL_SURPRISE_Z' AND date <= :t
    UNION ALL
    SELECT date, country, value, variable FROM etf_flow_signals
      WHERE variable = 'ETF_FLOW_21D_Z' AND date <= :t
  )
)
SELECT country, variable, value FROM latest WHERE rn = 1;
```

Composite assembly, z-scoring, vetoes (`sov_rating_changes` 63bd lookback; `SOV_CDS_SLOPE_BP` < 0), rank-buffer diffing vs current holdings, and order-list generation are ~150 lines of pandas in a standalone runner script under the sleeve's own directory (never inside the repo pipeline; DB opened `read_only=True` always). **A working reference implementation exists:** `slowbook_compute.py` (v2.0, this directory) implements Sections 2.3–2.5 exactly — component pulls with staleness windows, z-score/clip, C5 subscore, weight renormalization, eligibility, all four vetoes, group caps, and the fresh-start top-8 selection — and was run against the live DB on 2026-07-02 (output in the Appendix). The only piece it does not implement is the rank-12 incumbent buffer, which requires current holdings as input.

**Rebalance-day runbook (1st and 11th business day, ~30 min):**
1. 09:30 ET — freshness gate + governance check; reconcile component ranks vs `family_ranks_daily` (rank-corr ≥ 0.9). Fail → postpone per Section 2.6.
2. 09:45 — generate target book for the day's tranche; apply vetoes; produce order list with per-name tier tags and futures-fair-value checks for Asia B/C names.
3. 10:15–11:30 — submit orders: marketable-limit (tier A), midpoint-peg SMART (tier B/C), EDEN resting limit. Log arrival mid per order.
4. 15:30 — convert unfilled midpoint orders to capped marketable limits (except EDEN → roll to next morning).
5. EOD — write fills, implementation shortfall, positions, cash, and the day's composite cross-section to the sleeve's append-only log (incremental persistence, per house rules); update the K1–K5 monitor.

**Monitoring (weekly, automated):** rolling IC chart (K1 feed), active return vs EW benchmark (K2), cost audit (K3), component-health panel, freshness panel. Any red row emails the owner; no mechanical trading response beyond the pre-registered K-actions.

**Paper-first:** run the full runbook in paper mode for one quarter (6 tranche rebalances) to validate plumbing, fill assumptions, and the capture-ratio measurement (risk #3) before the hypothetical account trades — consistent with the constitution's WATCH → paper → PRD → capital ladder.

---

## Appendix — live cross-section, doc-spec composite computed against the loop DB (v1.1, 2026-07-02)

`slowbook_compute.py` v2.0 (Section 2.3–2.5 exactly: frozen weights 0.30/0.20/0.15/0.15/0.20, z-clip ±3, renormalized coverage, all vetoes, group caps) was run read-only against the live loop DB on 2026-07-02. Component freshness at run time: twins/graph 2026-06-30 (T+2, normal), 2s10s + CDS slope 2026-07-02 (same-day), CPI-rev stamp 2026-07-31 (forward month-end convention), eco-surprise 2026-06-01 (stale-by-design), flows 2026-07-01.

**Vetoes fired:** V2 hard — Mexico (Moody's downgrade 2026-06-01); V2b new-buy block — South Africa (Fitch upgrade 2026-07-01); V1 flow block — Indonesia (+3.1z), Italy, Thailand; V3 CDS-inversion — none.

**Full ranking (top/bottom):** #1 Hong Kong 1.031, #2 Indonesia 1.008 (flow-blocked), #3 ChinaA 0.854, #4 ChinaH 0.648 (group-capped behind ChinaA), #5 Brazil 0.636, #6 Turkey 0.606, #7 Thailand 0.582 (flow-blocked), #8 Malaysia 0.479, #9 India 0.458, #10 Japan 0.268, #11 Sweden 0.255, #12 South Africa 0.252 (upgrade-blocked), #13 Mexico 0.217 (VETOED) … bottom: #29 Denmark −0.702, #30 US SmallCap −0.733, #31 Taiwan −0.751, #32 Philippines −0.777, #33 Vietnam −0.862, #34 Netherlands −1.440.

**Fresh-start tranche buy list (8/8 slots filled, no cash forced):** EWH (Hong Kong), ASHR (ChinaA), EWZ (Brazil), TUR (Turkey), EWM (Malaysia), INDA (India), EWJ (Japan), EWD (Sweden).

This coheres with the independent live-DB miner's "tomorrow-morning book" (core longs EWH/EWZ/INDA; Netherlands/Denmark/Switzerland zero-weight; EIDO conflicted) — a useful consistency check that the composite measures what the families measure, with every veto class doing visible work on real, current names (Mexico downgrade, South Africa upgrade, Indonesia crowding, ChinaH redundancy). Note what the vetoes bought: without them the tranche would hold Indonesia (open paper thesis at −5.7% vs a −7% kill level) and both China lines.
