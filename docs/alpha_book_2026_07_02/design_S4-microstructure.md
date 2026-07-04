# S4 — THE MICROSTRUCTURE BOOK
## Monetizing the ETF-vs-home-market timing structure (long-only + cash, $100k IBKR, hypothetical)

**Designer:** Strategy sleeve S4, phase 2 of the alpha-book program
**Date:** 2026-07-02
**Status:** DESIGN + PILOT EVIDENCE. Zero capital until the validation gauntlet in §7 passes.
**New empirical work in this document:** two pilot scripts run read-only against the warehouse on 2026-07-02, results at
`/private/tmp/claude-501/-Users-arjundivecha-Dropbox-AAA-Backup-A-Working-ASADO/087bd20c-1f7d-42e8-9ea0-cad499732b04/scratchpad/alpha_book/s4_micro_pilot_results.json` and `s4_micro_pilot2_results.json` (code: `s4_micro_pilot.py`, `s4_micro_pilot2.py`, same directory), plus an **independent second-pass replication** (different signal constructions, same data, same day) at `s4_micro_scan.json`, `s4_micro_scan_clean.json`, `s4_micro_scan3.json` — see §4.1. The second pass corroborates the pilot and forces two rule changes (benchmark-quality gate; event-conditioned Tier-A expression), both incorporated below.

---

## 0. The one-paragraph verdict

US-listed country ETFs trade for 4–15 hours per day while their home markets are closed. During those hours the ETF price is not a measurement — it is a market-maker *forecast*, anchored overwhelmingly on the S&P 500. The data (home-market closes, sitting in `t2_levels_daily` hours before the US close) knows the true value; the ETF price knows a beta-extrapolation of it. Levy & Lieberman (JBF 2013) showed the extrapolation systematically **over-embeds** the US move and then reverses; ASADO's own math miner measured the flip side (ETF capture ratio 0.36 at h=1 — the ETF has already "spent" two-thirds of tomorrow's index alpha by tonight's close). A 13-month pilot on the loop DB's actual ETF closes confirms the tradable residual **exists right now, in the contrarian direction**: buying the 5 foreign ETFs whose US-hours move is most *unjustified* by their own home close + fair S&P beta earned **+11.8 bp/day gross (t = 2.3) at h=1 and +7.7 bp/day (t = 2.3) at 2-day tranches, net-positive at realistic Tier-A/B costs**, while the naive momentum version ("buy Asia after big US up-days") is directly refuted (next-day Asia −20.8 bp vs SPY, t = −2.0). This book trades that reversal daily in small size, harvests the D9 basis gap in wide-spread names *passively* (limit orders that earn the spread), and exports a premium/discount execution filter that lowers costs for every other sleeve in the $100k book.

---

## 1. Thesis — what the data knows that the ETF price doesn't

### 1.1 The information asymmetry, precisely

For every non-US name in the 34-ETF universe there are two prices for the same claim each calendar day:

1. **The home-market close** — Tokyo 2:00am ET, Hong Kong/Shanghai ~4:00am ET, Mumbai ~6:00am ET, Europe ~11:30am ET. This is a *fact*: thousands of local stocks clearing at auction, published hours before the NYSE close. It lands in ASADO as `t2_levels_daily / 'Tot Return Index'` (USD, per-country, daily since 2000).
2. **The US ETF close at 4:00pm ET** — a price set while the underlying basket cannot trade. Petajisto (FAJ 2017) measured the band of oscillation around fair value at ~200 bp for international-underlying funds, of which ~100 bp is *genuine* mispricing after controlling for stale NAVs with peer-group fair values. The mine_exec snapshot of live premiums/discounts runs ±0.3–1.2% across the universe (EWY −2.1% on the snapshot day).

The ETF price during US hours is driven predominantly by the S&P 500 with a beta **above** the true long-run beta of the underlying index (Levy & Lieberman 2013, on exactly these iShares country funds) — the marginal US-hours trader treats EWJ/EWY/EWG as levered S&P substitutes. The overshoot reverses when the home market re-opens and prints reality.

### 1.2 Why the edge persists (who is on the other side)

- **US-hours beta flow**: retail and macro traders expressing "risk-on/risk-off" through country ETFs without reconciling to home-market closes. They are structurally price-insensitive to the home-close anchor.
- **Market-maker inventory**: authorized participants hedge country-ETF inventory with S&P futures during non-synchronized hours (the underlying is untradable), mechanically importing US beta into the ETF print. Unwinding that hedge the next morning is part of the reversal.
- **Limits to arbitrage in the thin tail**: for Tier-C names (EZA 27 bp spread, EDEN 26 bp, EPHE 20, THD 19, TUR 17, ECH 16) the creation/redemption cost is roughly the size of the mispricing band — which is *why* the band exists (Petajisto's mechanism). Nobody institutional will arb a 30 bp gap that costs 25 bp to close. A $3k resting limit order has no such cost.
- **Jacobs & Müller (JFE 2020)**: country-level anomalies show no post-publication decay outside the US — the arbitrage capital that grinds US single-stock effects away has not shown up at the country-ETF level.

### 1.3 What this book is NOT

- It is **not** the LL_LEADER_GAP_5D follow-the-leader trade. That signal (IC 0.057, NW-t 8.5 on **local-index** returns) is real but already (over-)priced into US-listed followers by the US close — the trap named in the digest, measured by mine_math (capture 0.36), and resolved by the literature (Levy–Lieberman): **the tradable ETF-space expression is the fade, not the follow.** Our pilot independently reproduces this: after SPY +1% days, Asia ETFs return −6.1 bp absolute / −20.8 bp vs SPY the next day (n = 24, t = −2.0). The "buy Asia at US close after big US up-moves" idea assigned for consideration is hereby REFUTED on the available evidence and is not built.
- It is **not** an unconditional overnight-premium harvest (the NightShares NSPY/NIWM funds died doing that in 2023). Overnight/intraday decomposition is used as *signal input* only.

---

## 2. Sleeve architecture

| Sleeve | Name | What it trades | Frequency | Capital |
|---|---|---|---|---|
| **M1** | Overshoot fade (flagship) | Buy the 5 foreign Tier-A/B ETFs most oversold vs home-close + fair-beta fair value | Daily at the close, 2-day tranches | $15k |
| **M2** | D9 basis monitor | The D9 detector's gap_z as a *conditioning input* to M1/M3 — not a standalone book | — | $0 |
| **M3** | Thin-ETF passive-bid harvest | Resting limit buys in Tier-C names only when D9-style gap says the ETF lags its index; earn the spread instead of paying it | Event-driven, ~1–3 resting orders/week | $5k cap |
| **M4** | Premium/discount execution filter | Peer-controlled fair-value check applied to EVERY planned trade of the whole $100k book; buy at/below fair value, delay at premium | Overlay, zero added turnover | $0 |

Total sleeve allocation: **$20k of the $100k** (M1 $15k + M3 $5k max simultaneous resting exposure). M4 is an overlay exported to the other sleeves.

---

## 3. Exact rules

### 3.1 M1 — Overshoot fade (flagship)

**Universe (21 names, foreign Tier A/B only — cost-gated per mine_exec):**
- Tier A-mega (cost 3 bp one-way): EWJ (Japan), EWT (Taiwan), EWY (Korea)
- Tier A (cost 5 bp): MCHI, ASHR, INDA, EWU, EWQ, EWG, EWI, EWL, KSA, EWS, EWA, EWM, EWH
- Tier B (cost 10 bp): EPOL, VNM, EWD, EWP, EWN, EIDO
- **Excluded**: synchronized-hours names (SPY, QQQ, IWM, EWC, EWW, EWZ, ECH — no non-synchronized-hours mispricing mechanism) and all Tier C (ECH, TUR, THD, EPHE, EDEN, EZA — handled by M3 only).

**Signal (computed at 3:40pm ET each US trading day t):**

1. For each country c in the universe, obtain:
   - `etf_ret(c,t)` = ETF price at 3:40pm ET on day t / previous official close − 1 (IBKR snapshot; the ≤20-minute approximation error vs the true close is a known noise term).
   - `t2_ret(c,t)` = today's home-market **local-close** total return in USD. For Asia this printed 10–14 hours ago; for Europe ~4 hours ago. Live source: IBKR index quotes or the MSCI single-country iNAV feeds; overnight reconciliation source: `t2_levels_daily / 'Tot Return Index'` (main DB).
   - `spy_ret(t)` = SPY return, same 3:40pm convention.
2. Rolling OLS per country over the trailing 120 US trading days (excluding day t):
   `etf_ret(c,s) = α(c) + β1(c)·t2_ret(c,s) + β2(c)·spy_ret(s) + ε(c,s)`
3. Today's residual: `ε(c,t) = etf_ret(c,t) − [α + β1·t2_ret(c,t) + β2·spy_ret(t)]`.
   ε < 0 means the ETF has fallen during US hours **beyond** what its own home close and fair S&P beta justify — the Levy–Lieberman overshoot.
4. **Buy signal** = −ε(c,t). Rank the 21 names descending.
5. **Dividend guard**: skip any name with an ex-dividend date on t or t+1 (unadjusted intraday prices manufacture fake residuals; iShares distributions are semiannual, calendar known in advance).
6. **Benchmark-quality gate (added after the second-pass scan, §4.1):** a name is SUSPENDED from signal generation while its trailing-90-session |cumulative (T2-index − ETF) return drift| > 3%. The scan found EWY at **+55.8%** cumulative index-minus-ETF drift over 13 months (60 days with |1d gap| > 3%) and ASHR at **−46.1%** — for these names the T2 index and the ETF's actual benchmark are materially different objects right now (Korea re-rating composition/cap differences; CSI-300-vs-T2-ChinaA mismatch), so their "gap" or "residual" is not mispricing and never converges. **As of 2026-07-01 this suspends EWY and ASHR** and puts EWT on watch. Re-admission is automatic when drift re-enters the band. Recompute nightly; alarm if >2 further names breach (would indicate book-wide index↔ETF mapping degradation).

**Portfolio construction:**
- Two tranches of $7.5k each, held 2 trading days (this is the h=2 configuration — the pilot's most cost-robust: gross 7.7 bp/day, one-way turnover 0.367/day, net +4.0 bp/day at 5 bp, still +1.8 bp/day at 8 bp).
- Each day at the close, the expiring tranche is redeployed into the current top-5 names, $1.5k per name, equal-weight.
- **Storm-day overlay**: if |SPY return| ≥ 1% at 3:30pm ET, the signal is at its strongest (pilot: +24.6 bp/day, t = 3.6, hit 72%, n = 32 days). On storm days, deploy the expiring tranche at full size and tilt to top-4 ($1.875k per name). On calm days deploy at 75% size (rest to sleeve cash). This keeps average exposure ~85% while concentrating capital where the conditional evidence is strongest.
- A name already held by the live tranche that re-qualifies is simply held (no wash trade).

**Entry/exit and time of day:**
- All entries and exits at the **US close**: MOC orders submitted 3:42–3:48pm ET (NYSE MOC cutoff 3:50pm ET; Nasdaq-listed names 3:55pm). For Tier B names use **LOC with a 15 bp band** instead of MOC (mine_exec rule: LOC-with-band, not MOC, below Tier A).
- The skip-1 finding (61% of h=1 alpha dies if you wait a day — mine_math) applies with full force: **trading the same close the signal forms on is mandatory.** There is no "compute tonight, trade tomorrow" fallback; if the 3:40pm compute fails, the tranche rolls into sleeve cash, never into a stale signal.

**Cash rule:** any tranche without a valid signal (data failure, dividend guard, kill-switch) goes to cash (IBKR pays ~3.1–3.8% on balances above $10k at NAV ≥ $100k). Cash is the only hedge; the sleeve never shorts and never levers.

### 3.2 M3 — Thin-ETF passive-bid harvest

The pilot's key negative result disciplines this sleeve: the D9-style basis-reversion alpha **concentrates in the wide-spread names** (all-34 universe: +9.7 bp/day, t = 2.3; restricted to Tier A/B: +5.6 bp/day, t = 1.5, net-negative after costs). The gross edge lives exactly where paying the spread destroys it — so the *only* honest expression is to **be the resting bid**: earn the half-spread as compensation instead of paying it.

**Universe:** Tier C only — EZA, EDEN, THD, EPHE, TUR, ECH (spreads 15–27 bp).

**Trigger (from the nightly loop tables, not intraday):** country fires D9 with `gap_z ≥ +2.0` (home index outran the ETF over the common-date 5-day window — ETF is the laggard; source: `dislocation_daily` where detector='D9', components.gap_z; recompute intraday from the same formula in `build_dislocations.py::d9_index_vs_etf` for freshness — the nightly table is T+1). Cleaner audit surface: loop `price_state_daily` carries the same signal pre-joined per country as typed columns — `basis_gap_5d`, `basis_gap_21d`, `basis_gap_z` — alongside `liquidity_tier` and `bid_ask_spread_bps`, so the tier gate and the trigger read from one row without parsing detector JSON; use it as the nightly reconciliation source and `dislocation_daily` as the fire log.

**Order:** next US morning 9:45–11:30am ET (avoid the open), place a **GTC-day limit buy** at `min(bid, peer fair value − half of the name's 6c-11 median spread)`, size $2,500. Maximum 2 simultaneous resting orders ($5k cap). Peer fair value per §3.3.
- **If filled:** hold 5 trading days or until the D9 gap_z crosses 0, whichever first; exit with a limit at fair value (again earning, not paying).
- **If not filled by 3:30pm ET:** cancel. No chase. The economics of this sleeve *require* passivity — a fill at the bid on EZA banks ~13 bp of half-spread before the gap edge; crossing the spread pays 27 bp and reverses the sign of expectancy.

**Adverse-selection guard:** if the last 20 fills show negative mean 5-day forward P&L, M3 halts (see kill criteria).

### 3.3 M4 — Peer-controlled premium/discount execution filter (book-wide overlay)

Petajisto's implementation insight: raw premium/discount vs published NAV is uninformative for Asia funds (NAV up to 15 hours stale). The robust object is price vs **peer-implied fair value**.

**Fair value for ETF e at time τ:**
`FV(e,τ) = last home close (USD) × [1 + β_basket(e) · basket_ret(τ)]`
where `basket_ret(τ)` is the since-home-close return of a liquid same-region proxy basket (Asia: EWJ+EWY+EWT+MCHI equal-weight; Europe: EWG+EWQ+EWU; global fallback: SPY), and β_basket is the trailing 120d regression beta of the ETF onto the basket during US hours. (S&P futures could sharpen this but derivatives are out of scope; the liquid-ETF basket is the long-only-account version.)

**Rule applied to every planned BUY anywhere in the $100k book:**
- price ≤ FV − 10 bp → execute now (marketable limit at mid + 1 tick);
- FV − 10 bp < price < FV + 25 bp → execute per the owning sleeve's default schedule (midpoint peg / MOC);
- price ≥ FV + 25 bp → delay up to 2 days or substitute the alternate ticker (`etf_t2_map.etf_alternates`: FLBR for EWZ, KBA for ASHR, FXI for MCHI, INDY for INDA) if the alternate is ≥ 25 bp cheaper vs its own FV. Mirror logic for planned sells. Slow-sleeve trades (21d+ holds) get the full 2-day patience; M1's same-close trades are exempt (their alpha decays faster than the premium).

This adds **zero turnover** — it re-times and re-routes trades the book was doing anyway. Mine_exec measured live premium/discount snapshots of ±0.3–1.2% and flagged ~50–100 bp avoidable round-trip on Asia names in volatile weeks; Petajisto puts the genuine band at ~100 bp. Capturing even a 5–10 bp average improvement on the book's foreign-name volume is pure cost reduction.

### 3.4 Scheduling detail exported to other sleeves (not claimed as this sleeve's P&L)

The turn-of-month evidence (15–20 bp/day in the [−1,+3] window on international iShares — Chen et al. 2015, McConnell–Xu 2008, 2026 JIMF re-test; lit miner import #1) implies a free scheduling rule for the *slow* sleeves: **do de-risking/trimming mid-month; avoid being out of the market in the ToM window.** It belongs to the slow book's design; noted here because it is a calendar-microstructure effect and the rebalance calendars should be coordinated book-wide. **Own-data check (§4.1 S6):** on ASADO's 20-year EW-34 index panel the window premium is real full-sample (9.3 vs 2.5 bp/day, diff t = 2.0) but attenuated post-2015 (4.9 vs 3.1, diff t = 0.5) — so this stays a zero-cost scheduling tie-breaker and must never be sized as a return sleeve.

---

## 4. Pilot evidence (run 2026-07-02, read-only, PIT-safe)

Window: 2025-06-10 → 2026-07-01 (266 US trading days; 145 days for M1 after the 120-day regression warm-up). Data: `etf_prices_daily` (loop DB — the only ETF price history the warehouse has; starts 2025-06-09), `t2_levels_daily` Tot Return Index (main DB). Signal at close t → ETF close(t)→close(t+1) forward return. Active return = top-N portfolio vs equal-weight of the same universe.

| Test | Config | Gross bp/day | t | Hit | 1-way TO/day | Net @5bp | Net @8bp |
|---|---|---|---|---|---|---|---|
| **M1 overshoot fade** | top5 foreign-A/B, h=1 | 11.8 | 2.31 | 61% | 0.82 | +3.6 | −1.3 |
| **M1 overshoot fade** | **top5 foreign-A/B, h=2 (chosen)** | **7.7** | **2.34** | **59%** | **0.367** | **+4.0** | **+1.8** |
| M1 storm days only | top5, \|SPY\|≥1% (n=32 days) | 24.6 | 3.56 | 72% | — | — | — |
| D9 basis reversion | top5 gap_z, all 34 | 9.7 | 2.34 | 59% | 0.65 | +3.2 | −0.7 |
| D9 basis reversion | top5, foreign Tier A/B only | 5.6 | 1.48 | 58% | 0.63 | −0.7 | −4.5 |
| Follow-the-leader (refuted) | Asia next-day after SPY≥+1% | −6.1 abs / −20.8 vs SPY | −1.99 | — | — | — | — |
| Asia bounce after SPY≤−1% | (storm-day fade, buy side) | +63.8 abs next day | 1.6 | — | — | — | — |

Signal overlap: overshoot residual vs D9 gap_z cross-sectional correlation 0.34 — related but distinct; a rank-average combo *diluted* both (5.2 bp/day, t = 1.2), so M1 runs the residual alone.

**Honest caveats, in order of severity:**
1. **13 months, one regime.** 145–201 daily observations; t ≈ 2.3 is *below* the harness WATCH gate (NW-t ≥ 2.5). This is pilot evidence, not validation.
2. **Design freedom burned ~15 variants** in the two pilot scripts (universes × holds × signals). A deflated-Sharpe accounting would charge these; the harness registration in §8 does so formally.
3. **Unadjusted closes**: ex-dividend days create fake residuals (the dividend guard in the live rules; the full-history rebuild must use adjusted closes).
4. **3:40pm proxy**: the pilot used official closes for both signal and execution; live signals form at 3:40–3:48pm. The last-20-minutes drift is an unmodeled noise/slippage term (measured in paper trading).
5. **Encouraging counterweight**: Levy–Lieberman's sample ended 2010; the standard worry is that market-maker fair-value models have since arbitraged the effect away. The pilot is 2025–26 data — the effect is measurably alive *now*, which is stronger recency evidence than most of the warehouse's 20-year backtests possess, on far fewer observations.

### 4.1 Independent second-pass replication (same day, different constructions, artifacts `s4_micro_scan*.json`)

A second designer pass re-derived the signals from scratch — raw 1d/5d ETF-minus-index gaps instead of regression residuals, artifact filter |1d gap| ≤ 3% instead of a dividend calendar — on the same 13-month window. Where the two passes measure the same object they agree; where they differ, the differences are informative and are folded into the rules:

| Second-pass finding | Number | Consequence for this design |
|---|---|---|
| S1: 1d gap fade, pooled CS rank IC vs next-day ETF return | **IC −0.043, t = −3.06**, 264 days, 59% negative days | Independent confirmation of the M1 mechanism with a simpler signal; adopted as the quarterly mechanism-health metric in the kill table (§8) |
| S2: big-SPY-day split of the fade (19 Tier-A names) | SPY<−1%: **+32.0 bp/day (t = 4.3, n = 25)**; SPY>+1%: +13.2 (t = 2.3); quiet: +4.5 (t = 1.8) | Sharper storm-day evidence than the pilot's pooled ±1% number (24.6 bp, t = 3.6); supports the storm overlay, and long-only harvests mostly the down-day side |
| S3: **event-conditioned Tier-A expression**: 5d gap z(120d) ≤ −1.5 AND gap5 ≤ −1%, de-clustered, 5-day hold | n = 228 Tier-A events → fwd 1d **+25 bp (t = 3.0)**, fwd 5d **+63 bp (t = 3.4)** ≈ +53 bp net per event at 10 bp round-trip | Materially stronger than the pilot's *persistent-rank* Tier-A/B basis test (5.6 bp/day, t = 1.5). Read: the basis edge in liquid names is **episodic, not a standing rank** — trade it as discrete events with ~1 round-trip per 5 days per slot, not as a daily-turnover rank portfolio. Registered as the pre-declared event-conditioned sub-spec of MICRO_ETF_BASIS_GAP5_Z (§9) and a candidate M1 companion once it clears the gauntlet |
| S4: "buy Asia after big US up-moves" | next-day Asia EW **−0.3 bp** absolute (n = 24), **−72 bp** vs own index; after SPY<−1%: +71 bp absolute, +157 bp vs index | Same refutation as the pilot's T3, independently measured — the ban stands |
| S5: benchmark-mismatch discovery | EWY +55.8% / ASHR −46.1% cumulative index-minus-ETF drift | New risk the pilot missed → benchmark-quality gate added to §3.1 and risks (§7) |
| S6: turn-of-month on ASADO's own 20y EW-34 index panel | 2005+: **9.3 vs 2.5 bp/day (diff t = 2.0)**; 2015+: 4.9 vs 3.1 (diff t = 0.5) | Tempers §3.4: ToM is real full-sample but attenuated post-2015 in this universe — scheduling tie-breaker only, never a sleeve |

Honest accounting: the second pass burned roughly 10 further design variants (universes × holds × thresholds × conditioning); the MICRO family registration in §9 must disclose the combined ~25-variant burn from both passes.

---

## 5. Expected performance (honest arithmetic)

**Benchmark note:** M1's natural benchmark is the equal-weight of its own 21-name foreign universe; the sleeve inherits full market beta (~15–18% vol on foreign-DM/EM mix). It is an alpha sleeve, not a hedge.

**M1 ($15k):**
- Pilot ceiling: +4.0 bp/day net at 5 bp one-way (blended realistic cost ≈ 5–7 bp given mostly-Tier-A membership) × 252 ≈ **+10%/yr active** — treat as a ceiling in the same way the combiner's 12.9% is one.
- Apply the program's standard haircuts: ~50% for small-sample/selection burn (the AFA-2024 ML-overfit haircut logic; the pilot's ~15 variants), no additional long-only haircut (the pilot construction is already long-only vs universe). **Central expectation: +3–5%/yr active on the sleeve ≈ $450–750/yr on $15k.** Realistic range including regime risk: **−$500 to +$1,500/yr.**
- Total-return terms: foreign-A/B EW base (~7–8%/yr per mine_math's EW numbers) + active − cash drag ≈ **10–12%/yr, vol ~16%, Sharpe ~0.55–0.7, maxDD ~−30%** (market-inherited; the 15% calm-day cash reserve trims it slightly).
- Storm-day overlay is where the conditional expectation is 3× the unconditional — but n = 32; it is sized (25% tilt), not bet.

**M3 ($5k cap):** ~40–60 qualifying D9 fires/yr in Tier C at current base rates (June 2026: ~20 Tier-C fires). Assume 40% fill rate ≈ 20 fills/yr, each banking ~8–13 bp half-spread + a gap edge the pilot measured at ~9.7 bp/day gross in the wide universe over a 5-day hold. **Expectation: $150–400/yr — explicitly labeled an assumption-stack**, because fill-conditional adverse selection is unmeasured (that is what the 20-fill guard is for). The sleeve's primary value is optionality + learning the fill statistics.

**M4 (overlay):** if the whole book turns over ~$300–500k/yr notional in foreign names and the filter improves execution 5 bp on average (conservative vs the 50–100 bp avoidable band mine_exec measured), **$150–250/yr of cost savings** credited to the book, not this sleeve.

**Sleeve total: central expectation ≈ +$600–1,400/yr on $20k deployed** (3–7% active), with an honest confidence interval spanning zero. At $100k-book level this sleeve is worth roughly as much through M4's cost reduction and its role as the book's execution-intelligence layer as through its own P&L — which is the correct shape for a microstructure sleeve at retail scale.

---

## 6. Capital & sizing

| Component | Capital | Positions | Clip size | Approx shares |
|---|---|---|---|---|
| M1 tranche 1 | $7.5k | 5 | $1.5k | e.g. EWJ ~20 sh, EWY ~8 sh, EWG ~40 sh, EIDO ~75 sh |
| M1 tranche 2 | $7.5k | 5 | $1.5k | same order of magnitude |
| M3 resting bids | ≤$5k | ≤2 | $2.5k | e.g. EZA ~50 sh, THD ~35 sh |
| **Total sleeve** | **$20k** | ≤12 | — | — |

- Fractional shares enabled (needed for nothing here — smallest clip $1.5k vs max price ~$250 for EWL; but enable anyway per mine_exec).
- **Capacity:** trivially fine. $1.5k clips are 0.001–0.1% of ADV everywhere in Tier A/B; the binding case is M3's $2.5k in EDEN-class names (~0.3% of EDEN's $0.8M ADV — and EDEN is excluded from M3's active list until its D9 fires anyway; a $2.5k resting bid is invisible).
- **Commissions:** IBKR Pro Tiered, ~$0.35–0.60/order on these clips = 2–4 bp — inside the cost assumptions but not negligible at $1.5k clips; this is why tranches are 5 names and not 10.
- The remaining $80k of the book belongs to the other sleeves; M4 serves them.

---

## 7. Risks & failure modes (top 6, each with a detection signal)

1. **Pilot overfit / regime artifact (the big one).** 13 months, one choppy-risk regime, ~15 design variants burned. *Detection:* the full-history reconstruction in §8 — if the residual-fade alpha does not exist at NW-t ≥ 2.5 over 2002–2026 with adjusted closes, the sleeve never launches. Post-launch: 63-day rolling net active < 0 triggers half-size (see §8 kill table).
2. **Reversal-regime inversion (the NightShares failure mode).** Overnight/reversal effects have historically inverted abruptly. *Detection:* trailing-126-day sign of the storm-day conditional (fade after SPY moves) flips negative with t < −1.5 → suspend storm overlay; whole-signal trailing 12-month t < 0 → kill.
3. **Execution decay at the close.** MOC imbalances and closing-auction spread widening on foreign names could eat the 4 bp/day net margin. *Detection:* implementation-shortfall log (decision price 3:40pm vs fill); if realized all-in one-way cost > 8 bp averaged over 20 trades → suspend (at 8 bp the h=2 pilot economics compress to +1.8 bp/day, and the haircut expectation goes ~0).
4. **Adverse selection on M3 resting bids** — the limit order fills precisely when informed flow (a genuine home-market shock the D9 gap misclassified as noise) is selling. *Detection:* mean 5-day forward P&L of the last 20 fills < 0 → M3 halts; also halt any single name after 2 consecutive fills with < −2% 5-day P&L.
5. **Data-dependency fragility.** M1's 3:40pm compute needs same-day home closes (IBKR index quotes) + live ETF snapshots; the nightly warehouse only reconciles T+1. A silent staleness (e.g., holiday in the home market — Japan trades ~245 days/yr vs NYSE 252) would feed the regression garbage. *Detection:* per-country calendar check against `daily_calendar` (main DB) before every compute; missing home close for day t → name excluded that day (FAIL IS FAIL — no ffill into the signal); >6 names excluded → tranche rolls to cash.
6. **Benchmark mismatch masquerading as signal (found by the second pass, §4.1 S5).** A "gap" between the T2 index and an ETF tracking a *different* benchmark never converges — it is composition drift, not mispricing. EWY (+55.8% cumulative index-minus-ETF drift over 13 months) and ASHR (−46.1%) are live cases; a residual/gap signal computed on them is garbage-in. *Detection:* the §3.1 benchmark-quality gate (trailing-90-session |cumulative drift| > 3% → suspend), recomputed nightly; alarm if more than 2 additional names breach, which would mean the T2-index↔ETF mapping is degrading book-wide and the sleeve must halt pending a mapping audit.

Secondary risks tracked but not top-5: dividend-guard misses (audit vs iShares distribution calendar monthly); QQQ/SPY correlation regime making β2 unstable for high-beta EM names (monitor rolling R²; drop any name whose 120d regression R² < 0.3); crowding via CORO-style institutional country-rotation products (watch M3 fill rates trending to zero as the canary).

---

## 8. Kill criteria (pre-registered, forward)

**Phase gates before any capital:**

| Gate | Requirement | Falsifies if |
|---|---|---|
| G1: History rebuild | Reconstruct M1 signal on 2002–2026 dividend-**adjusted** ETF closes (yfinance/IBKR history — the loop DB's 13 months is execution data, not backtest data) | Full-period NW-t < 2.5, OR either sample half ≤ 0, OR net at tier-mapped costs ≤ 0 |
| G2: Harness registration | Register per §9; verdict must reach WATCH under harness v2.1 (deflated vs the MICRO family trial count including this pilot's burn) | Verdict DEAD or INSUFFICIENT after honest deflation |
| G3: Paper trading | 60 trading days live-paper at IBKR with real 3:40pm computes and simulated MOC fills | Paper net active < 0 over the 60d, OR realized cost > 8 bp one-way, OR >10% of computes fail their data checks |

**Post-launch (forward performance):**

| Metric | Window | Threshold | Action |
|---|---|---|---|
| M1 net active vs universe EW | rolling 63 trading days | < 0 | halve size |
| M1 net active | rolling 126 trading days | < −3% annualized | **kill sleeve**, return to paper |
| M1 realized one-way cost | trailing 20 round-trips | > 8 bp | suspend, fix execution, re-paper 20 days |
| Storm-overlay conditional mean | trailing 126d storm days (min 15) | < 0 with t < −1.5 | drop overlay, keep base |
| M3 fill-conditional 5d P&L | trailing 20 fills | mean < 0 | halt M3 |
| M4 filter value-add (paired: filtered vs unfiltered arrival price) | trailing 50 filtered trades | < 0 | revert to default execution |
| Mechanism health: pooled CS rank IC of 1d gap fade vs next-day ETF return (§4.1 S1, re-measured) | trailing 12 months, quarterly | IC > −0.01 (reversion gone) | kill sleeve — the mechanism, not just the P&L, is dead |
| Benchmark-quality gate breaches | nightly | > 2 names beyond the 2 currently suspended | halt sleeve pending index↔ETF mapping audit |
| Any single day | — | sleeve down > 4% while foreign EW down < 1.5% | manual review before next tranche (idiosyncratic blowup check) |

These are pre-registered: crossing a threshold is a decision already made, not a discussion.

---

## 9. Governance

**Existing harness backing:** none directly — that is the point of this sleeve, and the governance consequence is unavoidable:
- `LL_LEADER_GAP_5D` (WEAK, IC 0.057, NW-t 8.5) is the registered *cousin*, measured on local-index returns with the tradability trap explicitly unresolved. This design is its tradable inversion, but the inversion **is a different hypothesis and must be registered as such** — the ledger's lesson about post-hoc direction flips (ECO_INFL flip, the unregistered FX_BF25 flip) applies squarely.
- D9 is a live detector (136 June fires) but mine_docs is explicit: **never harness-tested**, and the pilot here shows its tradable Tier-A/B expression is weak (t = 1.5) — consistent with it being a *conditioning* surface, which is how M2/M3 use it.
- The pilot scripts plus the second-pass scans in this directory constitute **~25 burned design variants combined** (pilot ~15, second pass ~10) that the MICRO family deflation must be told about at registration — the registration text should reference all seven artifact files by name.

**New trials to register BEFORE capital (family_registry.yaml needs a trust-root edit to create the `MICRO_` family; both trials need `pit_proof_registry` entries because the signal is daily lag-0, formed and traded at the same close):**

1. **MICRO_OVERSHOOT_RESID_1D** — family MICRO; variable: negative residual of ETF daily return regressed on same-label home-index USD total return + SPY return (120d rolling OLS, adjusted closes); universe: 21 foreign Tier-A/B ETFs; direction: most-negative residual → outperforms next day; primary horizon: 1d (h=2 tranche as the traded expression); mechanism: Levy–Lieberman non-synchronized-hours over-embedding of the US move, reverting at the next home-market open. Secondary (registered, not primary): storm-day conditional |SPY|≥1%.
2. **MICRO_ETF_BASIS_GAP5_Z** — family MICRO; variable: z-score (120d) of [5-day home-index return − 5-day ETF return on common dates] (the D9 v1.1 formula, adjusted closes); universe: all 33 foreign ETFs, with two pre-registered sub-tests: (a) Tier-C-only (the M3 passive-bid substrate), and (b) **event-conditioned Tier-A**: z ≤ −1.5 in ETF-lag direction AND |5d gap| ≥ 1%, de-clustered, 5-day hold — the §4.1 S3 shape (+63 bp/5d, t = 3.4, n = 228 in the 13-month scan), tested as an event study (CARs at +1/+5/+21d) rather than a standing rank; direction: positive gap (ETF laggard) → ETF outperforms; primary horizon: 5d; mechanism: Petajisto premium/discount band mean-reversion where creation/redemption costs block institutional arbitrage. Benchmark-quality gate (§3.1 rule 6) applied at registration so suspended names are excluded from the test universe, not silently included.

**Data addition required (owner approval, per the no-unauthorized-collectors rule):** a dividend-adjusted daily ETF price history collector (yfinance, 34 primary + 4 alternate tickers, 1996+) writing to a NEW loop-DB table (e.g. `etf_prices_adj_daily`) — never touching `etf_prices_daily` (execution surface) and never unioned into `unified_panel`/`feature_panel` (cycle protection). Without this, G1 cannot run.

**Constitution compliance:** context-tier surfaces (D9 detector output, gap-engine absorption states) are used only as conditioners, never as mechanical stand-alone signals until their own registrations clear; every performance number above is either traced to a miner report, traced to the two pilot scripts, or labeled as an assumption; the forward-return blacklist is respected (no 1MRet-family variables anywhere in the signal chain — signals are built from prices and home closes only).

---

## 10. Implementation sketch

**Data dependencies (what must have run / be live):**
- Nightly: `loop_daily_job.py` steps that refresh `etf_prices_daily` and `dislocation_daily` (D9) — used for T+1 reconciliation and M3 triggers. Note both are T+2-flagged in the freshness audit until the nightly run completes; M3 recomputes the D9 formula intraday from live data rather than trusting the stale table.
- Monthly: `t2_levels_daily` refresh (Tot Return Index) — anchors the regression history.
- Intraday (new, this sleeve's own plumbing, no repo changes): a 3:35pm ET script pulling (a) IBKR snapshots for the 21 M1 ETFs + SPY, (b) same-day home-index closes (IBKR index quotes; fallback: MSCI country iNAV tickers), (c) the iShares distribution calendar; computing residuals; emitting the order list. Every input stamped and checked against `daily_calendar`; any check fails → that name is dropped for the day (no fallback estimation — FAIL IS FAIL).

**IBKR order plumbing:**
- M1: MOC for Tier A / A-mega names, LOC (limit = 3:40pm mid ± 15 bp band) for Tier B, submitted 3:42–3:48pm ET; NYSE MOC/LOC cutoff is 3:50pm ET — the pipeline aborts (tranche to cash) if not confirmed by 3:49.
- M3: GTC-day limit buys placed 9:45–11:30am ET at min(bid, FV − half-spread); auto-cancel 3:30pm; exits as limit-at-FV sells, downgraded to LOC on day 5.
- M4: implemented as a pre-trade wrapper every sleeve's order generator calls: input (ticker, side, size, urgency) → output (execute now / midpoint peg / delay / substitute-alternate). Logs FV, premium estimate, and the counterfactual arrival price for the value-add audit.
- Account: margin-type (never borrowing — margin type solely so T+1 settlement never blocks re-entry), IBKR Pro Tiered, SmartRouting on, fractional shares enabled.

**Monitoring (daily, ~5 minutes):**
- Implementation-shortfall ledger: decision price vs fill vs next-day reconciled close, per trade, appended to the sleeve's own log (incremental writes per the persistence rule).
- Signal-health panel: per-name 120d regression R² and β2 drift; count of names excluded by data checks; D9 Tier-C fire list vs M3 order state.
- Kill-table dashboard: every §8 metric with current value vs threshold; storm-day counter.
- Weekly: reconcile 3:40pm-proxy signals against official-close recomputes (quantifies caveat 4); audit dividend calendar against actual ex-dates.

**Build order:** history collector + G1 rebuild (2–3 days) → harness registration + verdicts (G2) → paper harness with live 3:40pm computes (G3, 60 trading days) → capital. Earliest realistic go-live: ~October 2026. Until then this sleeve's only live component is M4, which needs no validation to start saving the book money — it re-times trades the book already makes and its value-add is audited from day one.

---

## Appendix — pilot artifacts

- `s4_micro_pilot.py` / `s4_micro_pilot_results.json` — signal existence tests (T1 basis, T2 residual fade, T3 leader-follow refutation).
- `s4_micro_pilot2.py` / `s4_micro_pilot2_results.json` — turnover, tier restriction, tranche holds, net-of-cost economics, signal overlap.
- `s4_micro_scan.json` / `s4_micro_scan_clean.json` / `s4_micro_scan3.json` — independent second-pass replication (§4.1): raw-gap fade IC, artifact-cleaned re-runs, big-SPY-day conditioning, event-conditioned Tier-A expression, up-move refutation, benchmark-drift discovery (EWY/ASHR), 20-year turn-of-month check.
- All queries read-only against `Data/asado.duckdb` (t2_levels_daily) and `Data/loop/asado_loop.duckdb` (etf_prices_daily, etf_t2_map, dislocation_daily). No database writes, no repo modifications.
