# S7 — LET A THOUSAND ALPHAS BLOOM
## The Speculative Research Sleeve: 12 novel, falsifiable strategy ideas the warehouse can support but has never tested

**Designer:** Strategy sleeve S7 (wildcards), phase 2 of the ASADO alpha book
**Date:** 2026-07-02
**Capital allocated:** **$0.00** — by charter, this sleeve receives no capital until an idea clears the skeptic harness (WATCH or better, or a pre-registered event-study base rate), then paper trading, then a separate strategy PRD. Everything below is research design, not a trading instruction.
**Account context:** hypothetical $100,000 IBKR account, long-only + cash, 34 US-listed country ETFs.

---

## 1. Thesis — what informational edge this sleeve hunts

The ledger's brutal census (59 hypotheses, 21 WEAK, 21 DEAD, 0 above WEAK, ~4 independent mechanisms discovered) proves two things simultaneously: (a) the harness kills almost everything, and (b) the warehouse contains far more surfaces than have ever been asked a question. Evidence miner 3 catalogued at least ten collected-but-never-registered surfaces (D9 ETF basis, ToT impulse, foreign flows, macrostructure fragility, JST buckets, long-horizon valuation, WEO event shapes, GDELT event shapes, prediction markets, gap-engine tension). Evidence miner 5 found three literature-validated effects in **exactly these instruments** that are absent from the internal digest (turn-of-month in international iShares ETFs, the Levy–Lieberman US-hours overshoot reversal, Petajisto peer-controlled premium/discount). And the ledger itself contains measured-but-unregistered loose ends (FX_BF25_Z252 raw 63d IC +0.069 to +0.078, t 3.9–4.5, in the direction opposite to the one that was registered and killed).

The meta-edge is therefore **option value on unasked questions**: each registered trial costs nothing but research time and a deflated-Sharpe charge to its family, while a single graduate with SIM_NBR_RET_GAP_63D-like economics (BE 18.3 bps, the best slow-hold cost profile in the ledger) adds a durable sleeve to the book. Who is on the other side? For most of these ideas the counterparty is structural, not smart: month-end institutional rebalancing flows (W3), US-hours market makers pricing closed home markets off S&P beta (W4/W5), exchanges publishing foreign-investor flows that US ETF holders don't read (W6), commodity markets repricing terms-of-trade instantly while country equity indices take weeks (W2), and rating agencies whose actions are followed by slow, EM-concentrated drift that benchmarked investors cannot front-run (W9). Jacobs & Müller (JFE 2020) is the license for optimism: country-level anomalies show **no reliable post-publication decay** outside the US — limits to arbitrage keep this pond under-fished.

This sleeve deliberately does NOT re-propose anything the ledger killed: no valuation percentiles at 1m, no FX carry/vol levels as registered, no GDP consensus revisions, no ETF short interest, no 12-1 country momentum, and no holder-stress contagion via the bilateral portfolio matrix (GRAPH_PORT_HOLDER_STRESS_21D, H_20260612_026, is DEAD at IC −0.007 — the mandate's example is respectfully declined; the ledger's multiple-testing accounting is honest and binding).

---

## 2. The twelve wildcards

Format per idea: one-paragraph thesis, then a falsifiable harness test spec (family / variable / direction / mechanism / universe / horizon / outcome / kill condition). Scores: **P** = prior plausibility (1–5), **T** = testability today (1–5). All variable names below were verified read-only against the loop DB on 2026-07-02.

---

### W1 — FX tail-wing premium, flipped: buy countries whose currency options are pricing fear (FX_BF25_Z252, higher-is-better, slow hold)

The single cheapest unburned registration in the entire ledger. FX_BF25_Z252 (25-delta butterfly z vs 252d — the price of both tail wings of the currency smile) was registered lower-is-better in June and verdicted DEAD (H_20260612_011), but the run files show the **raw IC is positive and strong at long horizons in the opposite direction**: 21d IC 0.040 (t 3.4), 63d IC 0.069 (t 3.9) on 26 countries, 0.078 (t 4.5) on the 34-country coverage-gated run. Mechanism: an expensive butterfly means crash-hedging demand has already been paid — FX markets have priced the fear before equity markets finish digesting it; as the hedged episode resolves without disaster, the fear premium decays and the country's equity outperforms over the following quarter. The counterparty is the corporate/real-money hedger who buys wings at any price during stress. This is honest about its provenance: the direction was seen in the data before registration, so the new trial is charged to the already-heavy bbg_skill family (16 trials burned) and the deflated-Sharpe bar is correspondingly high — which is exactly what the governance is for.

**Test spec:** family `bbg_skill_2026_06` (existing prefix FX_ → no registry edit). Variable `FX_BF25_Z252` from `market_implied_signals` (confirmed present, fresh to 2026-07-02). Direction: **higher-is-better** (expensive wings → subsequent outperformance). Mechanism text: "paid-for tail-hedging premium decays into equity outperformance." Universe: FX-options coverage set (~26–31 countries; pegs HKD/SAR flagged per D10 convention; declare honest sub-universe at registration). Primary horizon **63d**, hold 21d; 1d/5d/21d grid as diagnostics. PIT: market-derived daily, needs `pit_proof_registry` entry (lag-0 legitimate — options close before US equity close). Kill: NW-t < 2.5 at 63d or negative in either sample half → DEAD, family takes the charge, idea closed permanently (this is the second trial of the idea; no third). Sister diagnostic (not a separate trial): confirm `FX_IMPVOL_Z252` 63d flip (raw t 2.57) moves the same way as a robustness read, without registering it.
**P=3.5, T=5.0 → 17.5**

---

### W2 — Terms-of-trade impulse as a standalone exporter-windfall rank (TOT_IMPULSE_Z36M)

`config/family_ranks.yaml` explicitly ships this as `verdict: UNTESTED, hypothesis_id: null` — a cockpit context column that has never been asked the only question that matters. The substrate: Comtrade HS-2 net export/import shares × Pink Sheet 3m commodity returns, z vs 36m, all 34 countries. It is episode-validated (Saudi/oil 2020 z −3.3, Chile/copper 2021 +2.0 and 2024 +1.5) and currently drives the broadest live dislocation theme (D1 shorts on U.K./Italy/Japan/Taiwan/Turkey — fuel importers with deteriorating ToT and un-repriced equity). Mechanism: commodity prices are global, instantaneous, and traded 23 hours a day; the earnings and fiscal consequences for a commodity exporter/importer arrive in country equity indices over weeks-to-months because the index reprices through analyst revisions and flows, not through the commodity tick. The counterparty is the benchmark-weighted country allocator who rebalances quarterly. D1 only ever fires on the *conjunction* (impulse extreme AND quiet price); nobody has tested whether the raw impulse ranks the cross-section.

**Test spec:** NEW family `tot_impulse` (requires a deliberate trust-root edit to `config/family_registry.yaml`, prefix `TOT_` — git-tracked, done before registration). Variable `TOT_IMPULSE_Z36M` (already computed into `family_ranks_daily`, family='tot_impulse'; currently as-of 2026-05-01 on 2026-07-02 — i.e. the live Pink Sheet/Comtrade lag is ~2 months; set `publication_lag_months` to the MEASURED vintage lag (2, verified against actual release dates), not an assumed 1 — declaring it shorter than reality is a PIT violation the harness cannot catch on its own). Direction: **higher-is-better** (windfall → outperformance). Universe: full 34. Primary horizon **21d** (monthly-frequency signal, slow hold). Trial 2 (only if trial 1 is ≥WEAK): the D1-gated conjunction — impulse |z|≥1.5 AND |own 21d equity z|<0.5 — as an event-study CAR since 2000 (Pink Sheet + Comtrade shares support a long backfill). Trial 3 (optional, curve-shape variant): re-weight the basket by physical tightness using `CMD_CL/CO/HG/GC/NG_CURVE_Z252` (confirmed in `market_implied_signals`) — backwardation-weighted ToT; COT positioning (`cot_signals`) reserved as a diagnostic conditioner, never a standalone trial. Kill: trial 1 NW-t < 2.5 at 21d → the rank is dead; the D1 detector remains a detector.
**P=4.0, T=4.5 → 18.0**

---

### W3 — Turn-of-month harvest: the calendar as a cash rule (CAL_TOM)

The largest documented effect absent from the internal digest, and the only wildcard that is natively long-only+cash with almost no cross-sectional machinery. McConnell–Xu (FAJ 2008, US + 30 international markets), Chen–Chou–Ko (2015, **international iShares country ETFs specifically**: 15–20 bp/day inside the [-1,+3] month-end window vs ~0 outside), and 2024–2026 re-tests (~10 bp/day persisting) all say the same thing: essentially all country-index return accrues in a 4–5 day window around month-end, plausibly driven by pension/institutional rebalancing inflows. For this book the expression is an overlay, not a strategy: be fully invested through the window, do any de-risking/rebalancing mid-month, and let the equity sleeve's residual cash sit larger outside the window. At ~24 decision points/year and an edge of 40–80 bp per window against Tier-A spreads of 3–5 bp, the cost math is trivially favorable if the effect replicates in the T2 panel. Who is on the other side: calendar-insensitive flows that must buy at month-end regardless of price.

**Test spec:** NEW family `cal_seasonality` (trust-root edit, prefix `CAL_`). This is a time-series rule, not a CS rank, so the validation path is the pre-registered rule-backtest / event-study path (governance explicitly allows "event-study for event-shaped claims"): define TOM window = last trading day through +3 of each month on the `daily_calendar`; compute EW-34 T2 USD portfolio daily returns 2001–2026 (from Tot Return Index on business days, per the math miner's alignment warning — never the calendar-grid `1DRet`); pre-register ONE statistic: mean(in-window daily return) − mean(out-window daily return), Newey–West t, plus by-decade and DM/EM splits as diagnostics. Falsification threshold declared now: **difference < +5 bp/day or t < 2.0 over the full sample → DEAD**. Secondary diagnostic (not a trial): does the window effect differ across the 34 (EM stronger per literature)? PIT is trivial (the calendar is known in advance). If validated, the "strategy" is a scheduling constitution amendment for every other sleeve (rebalance into strength before month-end, de-risk mid-month), worth capital-free basis points across the whole book.
**P=4.0, T=5.0 → 20.0**

---

### W4 — D9 ETF-vs-index basis-gap reversion: trade the instrument's own disagreement (BASIS_GAP_Z)

The most-firing real detector (136 fires in June) and the only surface in the warehouse where **the tradable ETF is part of the signal**. `price_state_daily.basis_gap_z` (confirmed column) measures the rolling 5d/21d gap between the T2 local-index return and the US-listed ETF return, z vs own history on common-date windows. Taiwan just fired at −2.7z (local index −3.2% over 5d vs EWT +3.2%); ASHR shows a ~10% 21d premium. Mechanism: a persistent gap is either a NAV premium/discount that creation/redemption arbitrage must close (Petajisto: ~100 bp of genuine mispricing band in international ETFs even after stale-NAV controls) or stale local pricing the ETF will drag — both imply reversion, in opposite instruments. The long-only expression: when the ETF is *cheap* vs its index (index outran ETF, positive gap), planned buys get accelerated and the name is a 1–5d long candidate; when the ETF is *rich* (ASHR now), delay buys. Honesty requirement from the LL trap: the outcome variable must be **ETF returns, not index returns** — otherwise the test marks the signal on its own numerator.

**Test spec:** NEW family `etf_basis` (trust-root edit, prefix `BASIS_`). Variable: `basis_gap_z` from `price_state_daily` (materialize a history table; the snapshot table is rebuilt nightly, so the nightly job must start archiving it — small builder change, flagged as a data dependency). Direction: higher-is-better for the **ETF** (ETF lagging its index → ETF outperforms next 1–5d). Universe: 34 ETFs; primary horizon **5d**; outcome = `etf_prices_daily` close-to-close returns. Hard constraint: `etf_prices_daily` history starts 2025-06-09 (~13 months) — a full harness verdict is underpowered, so stage it: (a) event study now on |gap_z| ≥ 2 days (13 months × ~136 fires/month cadence gives n in the low hundreds, enough for a first CAR read with wide bands); (b) recommend to the owner a one-time yfinance ETF-history backfill to 2005 (a collector change — owner permission required; this sleeve does not touch pipeline code); (c) full registration once ≥5y of ETF outcomes exist. Kill: event-study CAR at +5d indistinguishable from zero (|t|<1.5) on n≥100 events → deprioritize until data deepens.
**P=4.0, T=2.5 → 10.0**

---

### W5 — Fade the US-hours overshoot in closed-home-market ETFs (BASIS_USBETA_RESID)

The literature's answer to the ledger's biggest frustration. LL_LEADER_GAP_5D has the second-highest IC in the ledger (0.057, t 8.5) but is untradable as registered because US-listed follower ETFs embed the US move same-day. Levy & Lieberman (JBF 2013) sharpen this: during non-synchronized hours, country ETFs don't just embed the S&P move — they **over-embed it** (beta above the true underlying beta), and the overshoot subsequently reverses. The math miner's capture analysis (ETF captures only 0.36 of index-based alpha at h=1) is the same phenomenon measured from the other side. The tradable residual is therefore contrarian: on days SPY moves sharply, compute each Asia/Europe ETF's US-hours return minus its fair-beta prediction; buy the names that overshot DOWN at the US close, exit next close. Long-only native (only the buy side is expressed; overshoot-up names simply aren't bought). Confined to Tier A names (3–5 bp) where a 1d-hold edge can survive. Counterparty: US-hours market makers and momentum-chasing retail pricing a closed Tokyo/Seoul/Frankfurt off S&P futures with a systematically-too-high beta.

**Test spec:** family `etf_basis` (same new prefix as W4 — deliberately, these are two expressions of one instrument-mispricing family and share the trial budget). Variable: `BASIS_USBETA_RESID_1D` = ETF 1d return − β̂×SPY 1d return, β̂ estimated on trailing 252d, z-scored; computed from `etf_prices_daily`. Direction: **lower-is-better** (overshot down → buy). Universe: the ~14 Tier-A ETFs whose home markets are fully or mostly closed during US hours (EWJ EWY EWT EWH MCHI ASHR EWA EWS EWM INDA + European Tier A names for partial overlap; declared at registration). Condition: |SPY 1d| ≥ 1% (event-gated, declared primary). Primary horizon **1d**. Same 13-month data constraint and staging as W4: event study first, full harness after backfill. Kill: mean next-day reversal on overshoot-down events < spread cost (5 bp) or wrong-signed on n≥60 events.
**P=4.0, T=2.5 → 10.0**

---

### W6 — Foreign-investor flow lead in the six Asian EMs (FLOWF_EQ_NET_5D_Z)

"The best dataset not yet owned" per the PRD — except it IS owned now: `foreign_flows_daily` holds exchange-sourced foreign net equity buying for Korea, Taiwan, Thailand, Philippines, Indonesia (2005+, trade-dated) and India (NSDL, 2017+), fresh to 2026-07-02, 58,047 rows, confirmed variables including `FOREIGN_EQUITY_NET_USD_MN`. Twenty-one years of daily history and it has never been registered. Mechanism: in exactly these markets, foreign institutional flow is the marginal price-setter and is publicly reported with a 0–1 day lag that US-listed ETF holders demonstrably don't consume; a large literature finds foreign flows lead local returns in Asian EMs. Right now Korea sits at −3.0z and Taiwan at −2.8z 5d outflows. The design must pre-commit a direction: the literature prior is **momentum** (foreign buying leads outperformance) at normal readings; the contrarian-at-extremes variant is a second, separate trial if the first fails. Tradability note for later: EWY and EWT are Tier A-mega (3 bp) — the two deepest signals land in the two cheapest ETFs; THD/EPHE/EIDO are Tier B/C, so any graduate book gets expressed mostly in Korea/Taiwan/India.

**Test spec:** NEW family `foreign_flows` (trust-root edit, prefix `FLOWF_`). Variable: `FLOWF_EQ_NET_5D_Z` = 5d sum of `FOREIGN_EQUITY_NET_USD_MN` scaled by trailing 1y ADV-equivalent, z vs 252d (built read-only from `foreign_flows_daily`). Direction: **higher-is-better** (trial 1, declared now). Universe: honest sub-universe of 6 (harness scales coverage gate; 5 countries 2005+, India joins 2017+). Primary horizon **5d**; 1d/5d/21d grid diagnostics; trade-dated data needs a `pit_proof_registry` entry documenting the exchange publication clock (Korea/Taiwan publish same evening — lag-0 defensible; if not provable, register with 1-day embargo). Trial 2 (only after trial 1 verdict): extremes-contrarian (|z|≥2.5) as an event study. Kill: trial 1 NW-t < 2.5 → run trial 2; both dead → family closed at 2 trials.
**P=3.5, T=4.0 → 14.0**

---

### W7 — Buy the laggard twin: long-only convergence entries on extreme similarity gaps (SIM event expression)

The twins family is the ledger's quiet star: 2/2 WEAK, full 34-country universe, 2001+, positive both halves, and SIM_NBR_RET_GAP_63D at 21d hold has the best slow-hold economics ever measured here (BE 18.3 bps, net-10bps LS Sharpe +0.17, least deflation damage). But it has only ever been tested as a continuous rank. The long-only wildcard is an **event expression**: when a country's 63d return gap vs its fundamental twins exceeds +2z (it lagged its twins badly — Indonesia +0.295 and Korea −0.566 are today's extremes), enter a concentrated long in the laggard and hold 21–42d toward convergence; never short the leader (long-only). This converts a thin continuous tilt into a lumpy, high-conviction entry rule with far lower turnover — precisely the transformation the cost model rewards (fewer, bigger, slower trades at 18 bp breakeven). Counterparty: index flows that reprice "similar" countries asynchronously because they trade different benchmarks. Family charge is cheap: fund_similarity has only 2 trials burned, the lowest deflation bar of any live family.

**Test spec:** family `fund_similarity_2026_06` (existing prefix SIM_ — no registry edit). Variable: `SIM_NBR_RET_GAP_63D` from `similarity_features_daily` (confirmed). Spec: event study + tranche backtest — events = gap z crossing +2.0 (z vs own 3y), entry next close, hold 21d and 42d, CARs vs EW; plus the harness run on the thresholded dummy (direction higher-is-better) at primary horizon **21d**. Universe: 34. PIT: same as the validated parent (daily, lag-0 proof exists for the similarity build). Kill: event CAR at +21d < +1.0% or t < 2.0 on the 2001–2026 event set (expected n ≈ 150–300 events) → the event expression adds nothing over the rank; family keeps its rank-based WEAK.
**P=4.0, T=4.0 → 16.0**

---

### W8 — Combiner-score momentum: is the signal's CHANGE itself a signal? (COMBINER_CHG_5D)

The daily ridge combiner (H_20260612_054, IC 0.057, NW-t 10.7) is the strongest surface in the house, and its hold-grid decays slowly (BE 14.2/13.7/11.7 at 1d/5d/21d) — meaning the score is persistent. The untested question: does the **5-day change** in a country's combiner score carry information beyond the level? Mechanism: the combiner aggregates six diffusion features; a *rising* score means neighbor/leader repricing is accelerating into the country — the pipeline of un-transmitted return is filling faster than it drains. If IC-autocorrelation is the source of the level's persistence, the change may front-run the level's rank shifts by 1–3 days, worth real money at the margin when the level signal's turnover (0.60/day one-way) is the binding cost. It may equally be pure noise-chasing (a second derivative of an already-noisy surface) — which is exactly why it should be asked cheaply rather than assumed either way. Charged to ml_combiner (5 trials burned).

**Test spec:** family `ml_combiner_2026_06` (existing prefix COMBINER_ — no registry edit). Variable: `COMBINER_CHG_5D` = score(t) − score(t−5) from `combiner_scores_daily` (history confirmed back to 2005-01-03). Direction: **higher-is-better**. Universe: the validated 29-country combiner universe. Primary horizon **5d**. Mandatory diagnostic: IC of the change **orthogonalized to the level** (residual from CS regression on level) — if the orthogonal IC is ~0, the change is redundant and the verdict must say so regardless of raw IC. PIT: inherits the combiner's walk-forward discipline; the in-sample component-selection caveat propagates and must be restated in the registration. Kill: orthogonalized NW-t < 2.0 → DEAD, no re-spec.
**P=2.5, T=5.0 → 12.5**

---

### W9 — Sovereign-event avoidance overlay: zero-weight anything a rating agency touched (SOVEV_ACTION_63D)

The event-study file is unambiguous and strange: downgrades bleed (EM −0.9% at +5d, −2.8% at +63d), CDS 1s5s inversions bleed hard (−4.5% at +63d, t −2.4, 41 events), and — the strange part — **upgrades also drift negative** (−2.4% at +63d, t −2.2). The tradable shape for a long-only book is therefore not a tilt but an *avoidance rule*: any rating action in either direction, or a CDS curve inversion, within the past 63 days → the country is ineligible for long positions; its weight goes to cash or is redistributed. Mexico (Moody's downgrade 2026-06-01) is the live specimen — EWW sits inside the validated negative-drift window through August. Mechanism: rating actions are lagging confirmations that trigger slow, mandate-driven flows (funds with rating floors, insurance capital rules) that take weeks to complete; upgrades drifting negative suggests actions of any kind mark the end of the repricing that motivated them. Counterparty: mandate-constrained sellers/buyers who transact on a schedule, not a price. This never generates a position, only removes them — its value is measured as avoided loss, which is real money in a book whose only hedge is cash.

**Test spec:** family: extend existing `SOV_` prefix mapping (bbg_skill family) or, cleaner, NEW family `sov_events` (prefix `SOVEV_`, trust-root edit) so the avoidance idea isn't crushed by bbg_skill's 16-trial deflation. Variable: `SOVEV_ACTION_63D` — binary dummy built from `sov_rating_changes` (confirmed: date, country, agency, delta; 128 events) plus CDS-inversion days from `sovereign_signals`. Direction: **lower-is-better** (event → underperformance). Universe: the 20 rated + 20 CDS-covered countries (declare honest sub-universe ~26). Primary horizon **21d**. Complementary portfolio test (not a harness trial): ablation backtest — EW-34 vs EW-with-avoidance 2015+ (ratings history starts 2015), pre-registered statistic = active return + maxDD difference. Kill: harness IC t < 2.0 AND ablation shows < +0.3%/yr avoided loss → the event studies stay event studies.
**P=3.5, T=4.0 → 14.0**

---

### W10 — Macrostructure fragility as a conditional-severity gate: which longs to shed first (MS_FRAGILITY)

Zero harness exposure across the entire macrostructure layer (IMF FSI NPLs, QPSD FX-share/foreign-held/short-maturity debt, `MS_Investor_Base_Fragility`, `MS_Reserve_Adequacy`, `MS_Swap_Line_Access`). The right question is not "does fragility rank next month's returns" (almost certainly DEAD — quarterly data, structural not cyclical) but "**conditional on stress, who falls furthest?**" — the missing risk layer for a long-only book where cash is the only hedge. Mechanism: FX-denominated, foreign-held, short-maturity sovereign debt plus a fragile investor base converts a global shock into a local funding crisis; this is textbook and episode-validated (2013 taper, 2018 TRY/ARS, 2022) but has never been quantified on this panel. If it works, every other sleeve inherits a rule: when the stress trigger fires, shed high-fragility longs first, hold DM/low-fragility longs longer.

**Test spec:** NEW family `macrostructure` (trust-root edit, prefix `MS_`). Two pre-registered stages, both declared before any data is looked at: (a) **event interaction** — re-cut the existing downgrade/CDS-inversion event studies by fragility tercile (composite = mean z of QPSD FX-share, foreign-held share, inverse reserve adequacy, investor-base fragility, from the main warehouse read-only); falsifiable claim: high-fragility tercile CAR at +63d is ≥2× more negative than low tercile. (b) **regime-conditioned rank** — fragility composite IC measured only in months where VIX z > +1 (declared primary spec at registration; this is NOT a post-hoc conditional). Universe: ~30 with QPSD/FSI coverage. Primary horizon 21d within stress months. Publication lags set honestly (quarterly → 1q embargo). Kill: stage (a) shows no tercile separation (Δ CAR < 1% at 63d) → stage (b) is cancelled and the family closed at 1 trial.
**P=3.0, T=3.0 → 9.0**

---

### W11 — Strategic deep-value / deep-drawdown bands: the 3–5 year sleeve (VAL 6–12m horizon + JST drawdown buckets)

The ledger killed valuation at the 1-month horizon (5 trials, unambiguous) — it never asked about 6–12 months, where `VAL_EY_PCT` was already flirting with significance (IC 0.0297, nw_t 1.96, gated on coverage not signal), and the literature's entire case for country value lives at 3+ years. Meanwhile the JST calibration (65 crisis onsets, 1870–2020) says deep-drawdown countries (dd ≤ −35%) are median-best forward buys (+8.8%/yr fwd-3y median) with a fat left tail (p10 −12%/yr, P(neg)=27%) — a shape that argues for small, diversified, patient overweights in crushed markets, sized for the p10. Denmark (−43% drawdown, EDEN) is the live specimen. The GVAL disaster (backtest 16–18%/yr, live 2.4%/yr for a decade) is the mandatory scar tissue: value alone, expressed as a concentrated quartile bet, fails live because the convergence clock is unknowable. Hence *bands, not bets*: a strategic ±2–4% band overlay on the EW benchmark weight for names in the cheapest ERP decile AND a deep-drawdown bucket, revisited quarterly, never the whole book. Counterparty: performance-chasing capital that abandons markets after multi-year drawdowns for career reasons.

**Test spec:** family `valuation_2026_06` (existing prefix VAL_, 5 trials burned — the DSR bar is high and that is accepted; one trial only). Variable: `VAL_ERP_PCT_PCTILE_10Y` from `valuation_monthly` (confirmed), direction **lower percentile = cheaper = better**, primary horizon **6m** (the never-tested horizon), universe 32. Companion trial in a NEW family `dd_cycle` (prefix `DD_`, trust-root edit): `DD_BUCKET` = trailing drawdown from the T2 total-return index (PIT-clean, price-derived), ordinal buckets, direction deeper-drawdown-is-better, primary horizon **6m**, monthly. Conjunction (cheap AND crushed AND positive CPI-revision, the E1 archetype) reserved as trial 3 only if both parents show t > 1.5. Kill: both parents t < 1.5 at 6m → the strategic sleeve is folded permanently; valuation stays context-tier.
**P=3.0, T=3.5 → 10.5**

---

### W12 — WEO revision-without-repricing as an event, not a rank (D3 event shape)

The CS rank died (CONS_GDP_REV3M_12M DEAD, WEO-derived variant DEAD) but the **event shape** was never studied: a large WEO vintage revision (|z| ≥ 1.5 vs own 2008+ revision history, from `weo_revisions` — 36 vintages) coinciding with flat 6m price momentum. That conjunction is rare (~2 vintages/yr × 34 countries × low base rate ≈ usable but modest n since 2008), which is exactly why the monthly rank diluted it to zero. Mechanism: the IMF revision aggregates official-sector information with a stamp of authority that reprices slowly in smaller markets when no price trend is already underway; when the market has already moved, the revision is stale news (hence the quadrant split matters). Vietnam is the live specimen (revision +1.22pp, z +1.83, flat price, D3 persisting 14 days) — and the gap engine already marks its episode "repriced_against," a useful reminder that this idea must earn its base rate, not borrow it from a narrative.

**Test spec:** event-study path (allowed by governance for event-shaped claims), preset with `--events-sql` on `weo_revisions`: events = vintage-country rows with revision z ≥ +1.5 (up-quadrant) and |6m momentum z| < 0.5 at vintage date; anchor next trading day; CARs to +21d/+63d/+126d vs EW; quadrant-split table (up/flat, up/strong, down/flat, down/strong) pre-registered. Universe 34, sample 2008+. PIT: WEO vintage dates are publication dates — embargo trivially satisfied. Kill: up/flat quadrant CAR at +63d < +1.5% or t < 2.0 → D3 remains a look-trigger with no trade attached.
**P=3.0, T=4.0 → 12.0**

---

### Bench (registered intentions, not yet testable or deliberately declined)

- **Prediction-market composite changes / D6 disagreement CARs** — structurally blocked until ~60 snapshots (~mid-August 2026; 21 accumulated). Pre-commit now: first trial = 5d change in `predmkt_country_risk_composite`, lower-is-better, honest 18–19-country sub-universe, primary 5d, registered the week the archive crosses 60. No peeking at the accumulating archive before registration.
- **GDELT attention-shock event study** — constitution-compliant version only: CARs after attention z > +2 with |5d return| < 0.5σ, computable back to ~2015 from `gdelt_factors_daily`; validates D5 as a look-trigger with a measurable base rate, never a mechanical signal.
- **Dislocation resolution base rates** — `repriced_with/against/decayed` per detector is the meta-signal Layer 2 needs; needs months more history (table starts 2026-06-09). Compute quarterly, no trial charge (descriptive).
- **ECFC revision breadth** (share of forecasters revising up, vs magnitude) — one trial in the consensus family if/when the CPI-revision WEAK survives its sample-extension re-test; otherwise the family is thin enough already.
- **Gap-engine tension-rank validation** — forward-mark all episodes via `gap_episode_marks`; test tension-score rank skill at n≈60 episodes (~Q4 2026). Config hash `gap_engine_v2_2026_07_01` frozen as the spec.
- **DECLINED: holder-stress contagion via bilateral portfolio matrix** — already tested and DEAD (H_20260612_026, IC −0.007). The PIT holder-stress leg stays untested only because its non-PIT parent failed; re-proposing it would be trial-burning theater.

---

## 3. Ranking and the first three tests

Score = prior plausibility × testability (each 1–5, scored above; ties broken by family trial-budget cost — cheaper families first).

| Rank | Idea | P | T | Score | Family (trials burned) | New registry prefix? |
|---|---|---|---|---|---|---|
| 1 | **W3 Turn-of-month overlay** | 4.0 | 5.0 | **20.0** | cal_seasonality (0) | CAL_ yes |
| 2 | **W2 ToT impulse rank** | 4.0 | 4.5 | **18.0** | tot_impulse (0) | TOT_ yes |
| 3 | **W1 FX butterfly flip @63d** | 3.5 | 5.0 | **17.5** | bbg_skill (16) | no |
| 4 | W7 Laggard-twin convergence entries | 4.0 | 4.0 | 16.0 | fund_similarity (2) | no |
| 5 | W6 Foreign-flows lead (6 EMs) | 3.5 | 4.0 | 14.0 | foreign_flows (0) | FLOWF_ yes |
| 6 | W9 Sovereign-event avoidance | 3.5 | 4.0 | 14.0 | sov_events (0) | SOVEV_ yes |
| 7 | W8 Combiner Δscore momentum | 2.5 | 5.0 | 12.5 | ml_combiner (5) | no |
| 8 | W12 WEO revision × flat price event | 3.0 | 4.0 | 12.0 | event-study path | no |
| 9 | W11 Strategic value/drawdown bands | 3.0 | 3.5 | 10.5 | valuation (5) + dd_cycle (0) | DD_ yes |
| 10 | W4 D9 ETF-basis gap reversion | 4.0 | 2.5 | 10.0 | etf_basis (0) | BASIS_ yes |
| 11 | W5 US-hours overshoot fade | 4.0 | 2.5 | 10.0 | etf_basis (0) | BASIS_ yes |
| 12 | W10 Fragility severity gate | 3.0 | 3.0 | 9.0 | macrostructure (0) | MS_ yes |

**Test first (in order): W3, W2, W1.** Rationale: all three run on 20+ years of PIT-clean history that already sits in the databases; they span three different families (no shared trial budget, no correlated-failure risk); together they cost roughly one research-week; and each has an unusually crisp kill threshold. W7 is the standing alternate (cheapest family in the ledger). W4/W5 carry the highest *strategic* value — the tradable instrument is inside the signal — but are honestly blocked on ETF price-history depth (13 months); their event-study first passes run in parallel without burning full-harness trials, and the yfinance ETF-history backfill (owner decision) is the single highest-leverage data acquisition this sleeve can request.

---

## 4. Exact rules — how this sleeve operates

Because this sleeve holds no positions, its "rules" are a research pipeline. A competent engineer implements the following without further guidance:

1. **Registration before computation.** For each idea, in ranked order: make the family-registry trust-root edit if required (git commit, scorecard must stay green), write the hypothesis JSON (mechanism text verbatim from §2, direction, universe, ONE primary horizon, publication lag / pit-proof entry), append to `ledgers/hypothesis_ledger.jsonl` via `register_hypothesis()` — then and only then run `scripts/harness/evaluate_signal.py` (or the event-study preset with `--events-sql` for W3/W12 and the staged W4/W5/W7 event passes).
2. **Cadence.** One registration per week maximum (guards against burst-burning family budgets); event studies may run in parallel. Top-3 in weeks 1–3; W7/W6/W9 in weeks 4–6 conditional on nothing (they are independent); W8/W12 weeks 7–8; W10/W11 in month 3; W4/W5 event passes anytime, full registration only after ETF history ≥5y.
3. **No peeking.** No signal is computed against forward returns before its registration exists. The predmkt bench item explicitly forbids inspecting the accumulating archive before the 60-snapshot gate.
4. **Verdicts are written by the harness, never by hand.** DEAD is final for the registered spec; a direction flip is a new trial and must be justified by a mechanism, not by the IC sign just observed (W1 is the one grandfathered flip, already priced into its plausibility score).
5. **Promotion path (unchanged from governance):** WEAK-or-better with breakeven ≥ 10 bps at some hold AND FF style-spanning alpha t ≥ 2 → 60-day paper thesis in the thesis ledger (frozen entry, numeric invalidation, auto-marked) → separate strategy PRD → only then capital, from the book's slow-sleeve budget, never from this sleeve (which stays at $0 permanently — graduates leave; the sleeve does not accrete AUM).
6. **Tradability gate before paper:** any graduate validated on T2 local-index returns must pass an ETF-outcome capture re-test (capture ratio ≥ 0.5 at the registered hold, per the math miner's method) before a paper thesis opens. This is the LL-trap firewall, and it is mandatory.

---

## 5. Expected performance — honest arithmetic

This sleeve's expected performance is an expectation over research outcomes, not returns. Every number below is either cited or explicitly labeled an assumption.

- **Base rate:** the ledger produced 21 WEAK / 59 trials (36%) and ~4 independent mechanisms / 59 trials (~7%). The 12 wildcards imply roughly 14–18 registered trials (some ideas are 2-trial). Applying the base rate naively: **expect 5–6 WEAK verdicts and 1–2 genuinely new mechanisms** (assumption: these ideas are drawn from the same quality distribution as June's; arguably better, since June's sweep already skimmed the obvious surfaces, but also worse, since the cheap wins are gone — the two effects are taken to cancel).
- **Value of a graduate:** the best slow-hold signal ever measured here (SIM_63 @21d) carries net-10bps LS Sharpe +0.17 (H_20260612_043); long-only captures roughly half. The math miner's blended slow book estimate is **net +0.5–2.5%/yr** on allocated capital for exactly this class of signal. One graduate funded at $10–15k would therefore add roughly **$50–375/yr** in expectation — small, but permanent, uncorrelated shelf space.
- **The asymmetric exception is W3 (ToM):** if the international-iShares literature number (15–20 bp/day in-window; ~10 bp/day in 2024–26 re-tests) replicates at even half strength on the T2 panel, a scheduling overlay worth **~0.5–1.5%/yr book-wide at zero incremental turnover cost** (assumption: 4-day window × ~5 bp/day incremental × 12 months on the invested fraction, net of nothing because trades that would happen anyway are merely re-timed). This is the only wildcard whose payoff applies to the whole $100k rather than a sleeve.
- **Cost of running the sleeve:** $0 capital, zero market risk, ~2–3 research-days/week for one quarter, plus the intangible cost of burned trials raising deflation bars for future ideas in shared families (quantified: W1 raises bbg_skill to 17, W8 raises ml_combiner to 6, W11 raises valuation to 6; all other trials land in fresh families at N=1–2).
- **Expected drawdown: none.** Max loss is research time and family-budget optionality.

---

## 6. Capital & sizing

- **Live capital: $0.** Hard-coded by charter. This sleeve never holds a position in the $100k book.
- **Paper capital:** graduates open paper theses sized at a notional $10,000 each (10% of book) for the 60-day paper gate, marked from T2 returns by the existing thesis machinery.
- **Post-PRD funding (outside this sleeve's authority):** recommendation to the book architect — a single graduated wildcard should start at **$8,000–12,000 (8–12%)**, funded pro-rata from the slow sleeve, with W3 (ToM) as the exception: it is a scheduling rule, requires $0 of its own, and if validated should be adopted book-wide immediately.
- **Capacity:** irrelevant at these sizes. Even the worst-capacity ticker in the universe (EDEN, $0.8M/day ADV) absorbs a $10k clip at 1.25% of ADV; every other name is far deeper. Ideas W4/W5/W6 are explicitly designed toward Tier-A names (3–5 bp) where $3–15k clips cost 1.3–6.8 bp all-in per the execution miner.

---

## 7. Risks & failure modes (top 5, each with a detection signal)

1. **Multiple-testing burn / family freeze.** 14–18 new trials risk pushing shared families toward the 20-trials-no-WATCH 6-month freeze (bbg_skill at 16 is two trials from frozen). *Detection:* trials-per-family counter checked before every registration; sleeve hard cap of 18 trials/quarter; W1 is bbg_skill's LAST allowed trial from this sleeve.
2. **Post-hoc contamination masquerading as priors.** W1's direction was observed before registration; W9's "upgrades also negative" shape came from the data. *Detection:* deflated Sharpe charges these automatically; procedural rule — any idea whose direction was informed by observed ASADO data gets a one-trial-no-flip rider written into its registration.
3. **Young-data illusions.** D9/gap-engine/dislocation surfaces have ≤13 months of history; event studies on n<60 produce confident-looking noise. *Detection:* minimum-n gates written into every spec above (n≥60 events, ≥3y span for any verdict); staged designs (W4/W5) that refuse full registration until data deepens.
4. **Tradability mirage (the LL trap generalizes).** Signals validated on T2 local-index returns can lose 40–64% in ETF expression (math miner: capture 0.36 at h=1, 0.60 at h=5). *Detection:* mandatory ETF-outcome capture re-test ≥0.5 before any paper thesis (§4 rule 6); W4/W5 are immune by construction (ETF outcomes native).
5. **Governance drift while the sleeve is fast-moving.** Seven trust-root registry edits are proposed; a dirty config or a red scorecard invalidates the night's warehouse. *Detection:* each registry edit is a single atomic git commit; no registration on any night the 7-dimension governance scorecard is not GREEN; the live_signals-view discrepancy flagged by the livedb miner (all 16 rows showing INSUFFICIENT_COVERAGE) must be reconciled before any graduate goes to paper.

---

## 8. Kill criteria (pre-registered)

- **Per-trial:** the harness verdict is the kill. DEAD = permanently dead for that spec. Specific thresholds are embedded in each spec above (restated): W1 NW-t<2.5 @63d; W2 NW-t<2.5 @21d; W3 in/out difference <+5bp/day or t<2.0 on 2001–2026; W7 event CAR@21d <+1.0% or t<2.0; W6 NW-t<2.5 then contrarian trial then closed; W8 orthogonalized t<2.0; W9 t<2.0 AND ablation <+0.3%/yr; W10 tercile ΔCAR<1% @63d; W11 both parents t<1.5 @6m; W12 up/flat CAR@63d <+1.5% or t<2.0; W4/W5 event CAR |t|<1.5 on n≥100 / mean reversal < 5bp on n≥60.
- **Sleeve-level:** if the first **8 registered trials** (expected by ~end-September 2026) produce **zero** verdicts at WEAK-or-better with breakeven ≥10 bps at any hold, the sleeve suspends for 6 months and its research time reverts to forward-verifying the existing WEAK set.
- **Per-graduate (paper stage):** kill the paper thesis if 63-trading-day paper active return < −3% vs EW, or realized IC ≤ 0 over ≥60 daily observations, or the frozen numeric invalidation level is touched — whichever comes first.
- **Meta-kill:** if two consecutive graduates fail the ETF-capture gate (≥0.5), all further local-index-validated ideas are frozen until the ETF price-history backfill exists.

---

## 9. Governance — existing IDs and required new registrations

**Existing hypothesis IDs this sleeve builds on (context, not validation):**
- H_20260612_011 (FX_BF25_Z252 DEAD wrong-direction) — W1 is its charged, mechanism-stated flip; H_20260612_030 (FX_IMPVOL) is the uncharged robustness read.
- H_20260612_042 / _043 (SIM twins WEAK) — W7 parents.
- H_20260612_054 (daily combiner WEAK) — W8 parent, in-sample caveat propagates.
- H_20260612_013 (SOV_2S10S) and the event-study file (rating downgrade/upgrade, CDS inversion, 2026-06-12) — W9's evidentiary base.
- H_20260612_026 (holder stress DEAD) — the declined idea; H_20260702_001 (Triptych lean DEAD) — why all Triptych/context-tier surfaces stay quarantined here.
- H_20260610_002 (12-1 momentum DEAD) — why no wildcard proposes trailing price momentum.

**Required trust-root edits to `config/family_registry.yaml` before registration (each an atomic, reviewed git commit):** `CAL_` (cal_seasonality), `TOT_` (tot_impulse), `FLOWF_` (foreign_flows), `SOVEV_` (sov_events), `BASIS_` (etf_basis), `MS_` (macrostructure), `DD_` (dd_cycle). Seven prefixes; the harness RAISES on unknown prefixes by design, so these edits are the deliberate act of bringing each surface under governance.

**PIT-proof registry entries needed (`config/pit_proof_registry.yaml`):** W1 (FX options lag-0), W6 (exchange flow publication clock — Korea/Taiwan same-evening; register with 1-day embargo if unprovable), W4/W5 (ETF closes are trivially lag-0). W2/W9/W10/W11/W12 use monthly/quarterly embargoes set honestly (Pink Sheet 1m, WEO vintage dates, QPSD 1q).

**Every trial is charged.** Nothing in this document has been run against forward returns except where the evidence pack already contains the number (W1's raw flip IC — measured in June's run files, which is precisely why its registration is charged as trial #17 of a tired family and carries the highest DSR bar in the sleeve).

---

## 10. Implementation sketch

**Data dependencies (all confirmed present, read-only, 2026-07-02):**
- Loop DB: `market_implied_signals` (W1; fresh 07-02), `family_ranks_daily` family='tot_impulse' (W2; as-of 2026-05-01, Pink Sheet lag), `foreign_flows_daily` (W6; fresh 07-02, 2005+), `similarity_features_daily` (W7; T+2 nightly), `combiner_scores_daily` (W8; 2005+, T+2 nightly), `sov_rating_changes` + `sovereign_signals` (W9; fresh), `weo_revisions` (W12; vintage 2026-04-15), `valuation_monthly` (W11), `price_state_daily` + `etf_prices_daily` (W4/W5; ETF history starts 2025-06-09 — the binding constraint), `gap_episode_marks` (bench), `daily_calendar` + T2 total-return indices in the main DB (W3, W11 drawdown).
- Main DB (read-only): macrostructure/QPSD/FSI panels (W10), T2 returns as outcome source of truth everywhere.
- **Nightly-job prerequisites for any live use of a graduate:** the loop nightly (33 steps) must have run (combiner/graph/similarity/dislocations are T+2 otherwise) and the governance scorecard must be GREEN; one builder addition is needed to start archiving `price_state_daily` history (currently snapshot-only) — flagged to the owner, not performed by this sleeve.

**Test execution:** `scripts/harness/evaluate_signal.py` with the registered H-id for CS ranks; the event-study preset with `--events-sql` for W3/W12 and the W4/W5/W7 event passes; `scripts/harness/ff_spanning.py` on any WEAK-or-better survivor before promotion. All outputs land in `Data/loop/harness_runs/` per convention; verdicts append to the ledger by harness action only.

**IBKR plumbing (applies only to graduates, per the execution miner's standards):** IBKR Pro Tiered; fast graduates (W4/W5/W6-Korea/Taiwan) trade Tier-A names only with MOC/LOC at the close matching close-to-close test assumptions; slow graduates (W2/W9/W11) use midpoint-peg mid-session, Europe names 9:45–11:30 ET; W3 requires no orders of its own — it re-times other sleeves' orders to the [-1,+3] window; fractional shares enabled for SPY/QQQ clips.

**Monitoring:** weekly research review of trial verdicts vs the §8 kill table; quarterly dislocation-resolution base-rate computation (bench); paper theses auto-marked daily by the existing thesis machinery with Brier accumulation; a standing check that `live_signals` effective-verdict reconciliation (flagged by the livedb miner) is complete before any graduate's paper thesis opens.

---

*End of S7 design. This sleeve asks twelve cheap, pre-registered questions; it expects most answers to be no; and it is structured so that a single yes pays for the entire program while a dozen nos cost nothing but honesty.*
