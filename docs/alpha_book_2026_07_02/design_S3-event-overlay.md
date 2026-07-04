# S3 — THE EVENT BOOK
## A veto/tilt overlay from validated event studies, plus a (deliberately empty-at-launch) event-reaction sleeve

**Designer:** Strategy phase 2, angle "Event Book" · **Date:** 2026-07-02 · **Account:** hypothetical $100k IBKR, long-only + cash, 34 US-listed country ETFs · **Status:** design only, not live trading

**One-line:** The Event Book is not a return engine. It is the book's immune system: a small set of pre-registered, evidence-backed rules that force capital OUT of names entering validated negative-drift windows (EM rating downgrades, CDS curve inversions), block buying into validated traps (rating upgrades, extreme ETF inflows, cold inflation prints), and time executions around known risk events — with cash as the destination. All validated event CARs in this warehouse are NEGATIVE-drift; a long-only book cannot short them, but it can refuse to stand in front of them at zero shorting cost. That asymmetry is the entire edge.

---

## 1. Thesis — what the data knows that the ETF price doesn't

### 1.1 The informational edge

Three event shapes are validated in `Data/loop/event_studies/` (all runs 2026-06-12, CARs on T2 country returns vs universe, bootstrap-supported):

| Event | n | +5d CAR (t) | +63d CAR (t) | 95% CI @63d | Hit rate @63d |
|---|---|---|---|---|---|
| **EM rating downgrade** (anchor next_month) | 54 | **−0.91% (−2.02, p=.049)** | −2.83% (−1.45) | [−7.0%, +1.0%] | 41% positive |
| **CDS curve inversion** (1Y>5Y, anchor next_day) | 41 | −0.61% (−0.53) | **−4.52% (−2.44, p=.019)** | **[−8.3%, −0.7%]** | 46% positive |
| **Rating upgrade** (anchor next_month) | 45 | −0.33% (−0.70) | **−2.42% (−2.19, p=.034)** | [−4.6%, −0.3%] | **31% positive** |
| DM rating downgrade | 19 | −0.1% (ns) | −0.1% (ns) | — | — |
| Downgrade, high-VIX subset | 23 | **−1.31% (−2.10)** | −0.7% (ns) | wide | — |
| Downgrade, low-VIX subset | 50 | −0.4% (ns) | −2.8% (−1.8) | — | — |
| Growth/inflation surprise *events* | 206–1013 | ~0 | ~0 / ns | — | — |

(Source: `Data/loop/event_studies/downgrade_em_20260612_131744/results.json`, `cds_inversion_20260612_124544`, `rating_upgrade_20260612_124545`, `downgrade_highvix/lowvix_20260612_*`; corroborated by the ratings-drift literature and peer-reviewed CDS-term-structure→equity work per miner LIT.)

Complementary WEAK harness signals used only as *haircuts* (never vetoes):
- **ECO_INFL_SURPRISE_Z flipped** (H_20260612_015, WEAK, NW-t 2.99, monthly, N=34): hot inflation print → outperformance ⇒ **cold print → underperformance**. Long-short gross Sharpe 0.56, net-10bps 0.11 — thin, direction chosen post-hoc; haircut-tier only.
- **ETF_FLOW_21D_Z contrarian** (H_20260612_046, WEAK, NW-t −2.20): big 21d inflows → underperform. Breakeven <4bps ⇒ untradable standalone, but free when applied as a *no-new-buys* block (zero added turnover).

### 1.2 Why the edge exists (who is on the other side)

- **Rating downgrades:** rating actions trigger mandate- and index-driven forced flows in credit that spill into equity with a lag, while equity holders of EM country funds (heavily retail/allocator flows) underreact to sovereign-creditworthiness deterioration. The post-announcement drift persists because *arbitraging it requires shorting expensive-to-borrow EM ETFs* — the friction that protects the anomaly is a friction we don't pay: a long-only book monetizes it by simply not holding the name. DM markets, with deep analyst coverage and cheap shorting, show zero drift (n=19, flat) — consistent with the limits-to-arbitrage mechanism, and why the veto is EM-only.
- **CDS curve inversion:** the sovereign CDS market (banks, macro funds) reprices near-term default/stress risk days-to-weeks before the equity index does; cross-asset information diffuses slowly (limited attention). The −4.5%@63d CAR is the strongest single event in the warehouse and the only one whose bootstrap CI excludes zero at 63d. Again: the short side is hard (borrow, timing); the avoidance side is free.
- **Rating upgrades drift negative:** agencies are lagging indicators — an upgrade certifies improvement the market priced quarters ago and often marks peak optimism. 69% of upgrades were followed by negative 63d relative returns. The other side is the allocator who buys the headline. We refuse to be that allocator: **never buy the upgrade**.
- **Cold inflation prints → underperformance:** in the current reflation-priced regime, downside inflation surprises signal demand weakness; markets initially misread them as "cuts are coming" and underreact to the growth signal (harness-validated direction, with the honesty caveat that the direction was flipped after seeing data).

### 1.3 What this sleeve is NOT

Every validated event CAR here is negative. There is **no validated long-side event reaction** in the warehouse (growth-hot, inflation-hot, growth-cold event CARs are all ~0; the D3 WEO-revision *rank* is DEAD; the D3 *event shape* is untested; D9 basis reversion is untested; D6 prediction-market disagreement is blocked until ~mid-August). Therefore the standalone event-reaction sleeve launches at **$0** and stays there until the registered trials in §8 produce verdicts. The Event Book earns its keep by modifying the other sleeves' target weights. That is the honest design, and §3 quantifies its marginal value.

---

## 2. Exact rules

### 2.0 Architecture and precedence

The overlay receives the **pre-overlay target weight vector** `w_pre` (per country ETF, summing to ≤ 1 with the residual in cash) produced by the book's alpha sleeves at each rebalance, and emits `w_final`:

```
w_final = ExecutionRules( Haircuts( Vetoes( w_pre ) ) )
```

Three tiers, strictly ordered:
- **Tier 1 — BINDING VETOES** (validated event studies): force weight to zero. Override everything, including any sleeve's conviction and any detector long-flag.
- **Tier 2 — HAIRCUTS / ADD-BLOCKS** (validated WEAK signals): reduce or freeze weights; never force exits.
- **Tier 3 — ADVISORY / EXECUTION** (unvalidated detectors, forward calendar, basis filter): change *when/how* orders execute, never *whether* a position is held. Explicitly assumption-tier.

Freed weight from any rule goes to **cash** (IBKR, ~3.1–3.8% on balances at $100k NAV per miner EXEC). It is never redistributed to other longs — redistribution would lever the surviving signals beyond their sized conviction and would contaminate measurement of the overlay's marginal value.

### 2.1 Tier 1 — Binding vetoes

**RULE V-DG (EM downgrade veto).**
- *Source:* `sov_rating_changes` (loop DB; columns date, country, agency, old_score, new_score, delta; 128 rows, 26 countries with at least one recorded change, 3 agencies; refreshed nightly — fresh as of 2026-07-01).
- *Trigger:* new row with `delta < 0` for a country classified EM (per `country_reference.dm_em` in the main DB; the event study's EM set). ChinaA/ChinaH share one sovereign; a China downgrade vetoes both ASHR and MCHI. DM downgrades (validated flat) trigger NO action — logged only.
- *Action:* `w_final = 0` for that country's ETF.
- *Window:* the study is anchored `next_month` (rating table is month-stamped; the action date within the month is unknown — anchoring to the following month-start is the PIT-safe convention). Veto runs from the **first trading day of the month after the event month** through **63 trading days** later. If the position is already held when the veto begins, exit at that day's close (order mechanics §9).
- *Multiple agencies:* overlapping downgrades on one country extend the window (expiry = latest anchor + 63 trading days); they do not stack any other way.
- *High-VIX acceleration:* if VIX z ≥ +1 (from `market_implied_daily`) on the day the downgrade row lands, exit at the **next close after detection** rather than waiting for the month-start anchor — the high-VIX subsample shows the damage front-loads into +5d (−1.31%, t −2.10). This is a timing refinement inside a validated rule, not a new rule.

**RULE V-CI (CDS inversion veto).**
- *Source:* `sovereign_signals`, variable `SOV_CDS_SLOPE_BP` (5Y−1Y CDS, daily, 2005+, **18 countries** carry the full 1Y/5Y pair [measured] — the other 16 ETFs structurally cannot fire this veto; fresh same-day, 2026-07-02).
- *Trigger:* onset = first day with `SOV_CDS_SLOPE_BP < 0` after ≥60 trading days of non-inverted history (the clean-onset definition reproduces the event study's n=41 census — my read-only re-count found 45 raw onsets 2005–2026 under this rule, 44 after the sanity gate below rejects one confirmed data artifact).
- *Data-sanity gate (mandatory):* reject onsets with |slope| > 500bp or a one-day slope change > 300bp unless confirmed by both the 1Y and 5Y CDS levels in `sovereign_daily` (the table contains at least one artifact: Spain 2025-09-19 printed −1013bp). A rejected onset is logged `SUSPECT_DATA`, escalated for manual confirmation, and only becomes a veto on confirmation.
- *Duration reality check (measured read-only 2026-07-02):* raw consecutive-inversion runs are mostly fleeting — of **147 run-episodes 2005–2026, 98 lasted exactly one day** (median 1 day; only 11 ran ≥5 days; France's 2026-06-22 −54bp print sat between +18.8bp and +19.8bp sessions and reverted the next day). The event study's n=41 census *includes* such brief onsets and still finds −4.5%@63d with a CI excluding zero, so the live rule stays faithful to the tested spec rather than bolting on an untested persistence filter — but a **≥2-day-persistence variant is queued as a robustness re-measure under E-1** (persistence-filtered onsets run ≈1.4/yr normal, 12 in 2009), and if it materially strengthens or weakens the CAR the rule migrates to whichever spec the re-measure supports.
- *Action:* `w_final = 0`, all countries (study was all-country; DM inversions like France are included).
- *Window:* anchor `next_day` (per the study): veto from the next trading day after onset for **63 trading days**. The veto does NOT lift early if the curve dis-inverts — the CAR accrues over the full window in the study (France inverted 2026-06-22, dis-inverted within days; the drift claim still runs to ~2026-09-21).

**RULE V-EXP (expiry / re-entry).** On expiry of any Tier-1 window the country's veto is lifted and it resumes whatever weight the sleeves then assign — at the next *scheduled* sleeve rebalance, not via a special re-entry trade. No "buy the recovery" logic: post-window re-entry outperformance is untested (see §8, trial E-4 territory).

### 2.2 Tier 2 — Haircuts and add-blocks (validated WEAK, applied cost-free)

**RULE H-UG (upgrade add-block).**
- *Source:* `sov_rating_changes`, `delta > 0`, all countries (the −2.4%@63d, t −2.19 result is full-sample).
- *Action:* **no increase** in the country's weight for 63 trading days from the month-start after the upgrade month. Existing holdings are untouched (the house digest's framing is "avoidance, not tilt"; forcing exits of a name the sleeves still like on an *upgrade* is a stronger claim than the evidence grades). Live example: South Africa Fitch upgrade stamped 2026-07-01 ⇒ EZA add-block through ≈2026-09-30.

**RULE H-CI (cold-print haircut).**
- *Source:* `eco_surprise_signals`, variable `ECO_INFL_SURPRISE_Z` (monthly, 33 countries, latest 2026-06-01 — stale-by-design ~1 month; that lag is inside the signal's validated monthly cadence).
- *Action:* if the latest monthly `ECO_INFL_SURPRISE_Z ≤ −2.0`, multiply the country's target weight by **0.5** until the next monthly print. Downward-only: hot prints (z ≥ +2) confer no boost from this overlay (the long side of the reflation tilt belongs to the slow sleeve; boosting here would double-count). Live example (June prints): Germany −3.9z, Netherlands −3.7z, France −3.3z.

**RULE H-FL (crowded-inflow add-block).**
- *Source:* `etf_flow_signals`, `ETF_FLOW_21D_Z` (daily, 34 ETFs, fresh 2026-07-01).
- *Action:* if 21d inflow z ≥ +2.5: **no new buys / no adds** in that ETF until z < +1.5. Holds are untouched, sells unaffected. Zero-turnover application is what makes a BE-<4bps signal usable at all. Live examples: EIDO +3.14z, EWI +2.96z, THD +2.65z.

### 2.3 Tier 3 — Advisory / execution rules (assumption-tier; timing only, never holdings)

**RULE X-CAL (forward-calendar entry delay).** Source: `forward_calendar` (50 events through 2026-12-18: ~40 CB decisions, 5 elections, 5 index reviews; severities tagged). For any **high-severity local** event (e.g., Banxico decision for EWW, Brazil first-round election 2026-10-04 for EWZ, MSCI classification for VNM/EWY/EWT/ASHR): do not *initiate* a new position in the affected ETF on the event day or the prior trading day; queue the entry for the day after. Exits and holds are unaffected. **Honesty label:** no ASADO evidence values this rule (the FX-vol-term × calendar gate is explicitly untested — miner DOCS §2.11); it is pre-event variance hygiene with near-zero expected cost, and it is registered as trial E-5 before anyone claims it adds return.

**RULE X-BASIS (D9 premium/discount execution filter).** Source: `price_state_daily` ETF-vs-index gap z (D9 substrate, T+2). When executing a *planned buy*: if the ETF is rich vs its index (gap z ≥ +2 on the ETF-rich side — e.g., ASHR +2.13 with a ~10% 21d premium, QQQ +2.39 on 2026-06-30), delay one day or work a limit near prior-close-implied fair value; if the ETF is cheap (e.g., EPHE −2.99), execute as planned. Zero added turnover; lit-corroborated (Petajisto ~100bp genuine mispricing band, miner LIT idea #3) but ASADO-untested (trial E-3 registered before this is credited with any bps).

**RULE X-STRESS (stress add-freeze).** While a country carries an active D4 (cross-asset incoherence) or D10 (FX-options stress unpriced by equity) flag with |severity| ≥ 2 in `dislocation_daily`: no new adds in that ETF; holds untouched. Untested detectors ⇒ advisory by constitution (context-tier quarantine). Live example: Chile D10 persisting (RR z +2.14) ⇒ ECH add-freeze.

**What deliberately does NOT bind:** D1/D2 directional fires (their substrates are either the graph sleeves' job (D2 = validated gap family, owned elsewhere in the book) or untested (D1 ToT)); D3 WEO longs (rank DEAD, event shape untested — Vietnam's D3 long may not override anything); D5 GDELT (constitution: look-only); D7 crowding; Triptych priors; Gap-Engine tension (both context-tier by governance); DXY/regime context (advisory commentary only). §3 shows why making detectors binding would destroy the book.

### 2.4 Schedule, time of day, cash rule

- **Recompute:** every morning ~08:00 ET, after the nightly loop job (~07:30) — reads only event tables that are same-day or T+1 fresh (`sov_rating_changes`, `sovereign_signals`, `etf_flow_signals`, `market_implied_daily`, `forward_calendar`; `eco_surprise_signals` monthly). Emits the overlay state file (§9).
- **Execution:** Tier-1 forced exits and any rebalance trades execute **at the close** — MOC for Tier A/A-mega ETFs (submit by 15:50 ET), LOC with a ~30bp band for Tier B/C (EDEN, EZA, EPHE, THD, TUR, ECH, EPOL, VNM, EWD, EWP, EWN, EIDO) per miner EXEC. Close-to-close matches the event studies' return convention.
- **Cash:** all vetoed/haircut weight sits in cash. No minimum or maximum cash from this overlay; it inherits the book's cash floor from the allocator.
- **Fail-safe:** if the governance scorecard is not GREEN or the nightly loop did not run, **existing vetoes persist** (they are anchored to durable event dates, not to tonight's data) and **no new adds** are made book-wide until the warehouse is green. Never trade on a red scorecard.

### 2.5 Standalone event-reaction sleeve (E-R): $0 at launch

Reserved capacity: up to **$5k**, deployable only after at least one of trials E-1…E-4 (§8) reaches a positive verdict with a tradable long-only shape. Until then E-R is a paper ledger: every Tier-1 event, every X-BASIS trigger, and every D3 conjunction gets a paper entry marked at +5/+21/+63d, building the forward sample the trials need. This is the "small standalone sleeve where evidence supports it" — today, evidence supports a sleeve of size zero, and pretending otherwise would be invention.

---

## 3. Event frequency — how often does this actually bind, and what is it worth?

This is the section the assignment demands and most overlay designs dodge. Measured from the live loop DB (read-only, 2026-07-02):

### 3.1 Raw event rates

- **Rating changes** (26 countries with recorded changes, 3 agencies, 2015–2026): ≈11.5 changes/yr — **≈7.2 downgrades/yr, ≈4.3 upgrades/yr**. Downgrades are ~75% EM (Turkey 16, South Africa 10, Brazil/Mexico/Chile 7 each over the sample) ⇒ ≈5 EM agency-downgrades/yr ⇒ after clustering same-country multi-agency actions, **≈3–4 distinct EM downgrade episodes/yr**.
- **CDS inversion onsets** (60-day clean-history rule, 2005–2026): 44 onsets in 21.5 years ≈ **2/yr — but violently clustered**: 11 in 2008, 6 in 2007, 4 each in 2020/2021, **4 already in 2026** (South Africa 03-05, Turkey 03-05, Brazil 03-10, France 06-22). The rule binds most exactly when the long-only book most needs a reason to hold cash.
- **Upgrades:** ≈4.3/yr; 2024–25 was upgrade-heavy (9–10/yr) — the add-block binds a few times a year for one quarter each.
- **Cold prints (z ≤ −2):** a handful of country-months per year; currently 3 (Germany/Netherlands/France).
- **Extreme inflows (z ≥ +2.5):** typically 1–3 ETFs at a time (currently EIDO, EWI, THD).
- **Forward calendar:** ~5 CB decisions/month across the universe + rare elections/index reviews ⇒ X-CAL delays a new entry maybe 1–2×/month, costing one day of timing each.

### 3.2 Binding rate on THIS book

A veto only creates value if the sleeves would otherwise have held the name. With a core book of ~8–12 positions drawn from 29–34 eligible countries (holding probability ≈ 30–40%, EM slightly over-represented in the reversion-flavored sleeves):

| Rule | Episodes/yr | P(book holds it) | **Bindings/yr** | Weeks active each |
|---|---|---|---|---|
| V-DG (EM downgrade) | 3–4 | ~0.35 | **≈1.2** | ~13 |
| V-CI (CDS inversion) | ~2 (normal) / 6–11 (crisis) | ~0.35 | **≈0.7** (normal), 2–4 (crisis yr) | ~13 |
| H-UG (upgrade add-block) | ~4 | binds only if a sleeve wants to ADD in-window | ≈0.5–1 | ~13 |
| H-CI / H-FL | monthly/daily | — | a few country-months/yr | 4–8 |
| Tier 3 | weekly | — | execution-timing only | days |

So Tier 1 — the part with teeth — bites **roughly twice a year in normal times, and 3–6 times in a stress year**. Most quarters the Event Book does nothing visible. That is correct behavior, not a defect: an overlay that fired constantly would be a signal, and the signals live in other sleeves.

**Counterfactual that proves the tiering:** June 2026 `dislocation_daily` directional fires — D1: 112 rows/15 short entities, D2: 110 rows/9+8 entities. Making detectors binding would have zeroed **10–15 of 34 countries simultaneously** (U.K., Italy, Japan, Taiwan, Turkey, Netherlands, Switzerland, Philippines, Spain…), amputating half the sleeves' opportunity set on unvalidated triggers — including Turkey and Brazil, which the combiner ranked #2 and #5 long on 2026-06-30. This is why D1/D2 are quarantined to Tier 3/other sleeves and only the small validated event set binds.

### 3.3 Marginal value arithmetic (all inputs cited, assumptions labeled)

Per binding, at a representative 8% position weight:
- V-DG: avoided CAR −2.83%@63d (point estimate; CI includes 0) × 8% ≈ **+23bp of book**; the −0.91%@5d component (p=.049) is the firmest part.
- V-CI: avoided −4.52%@63d (CI excludes 0) × 8% ≈ **+36bp of book**.
- H-UG: avoided −2.42% on adds that would have happened ≈ +19bp, discounted 50% for "would the add really have happened" ⇒ ~+10bp.

Annualized, normal year: 1.2×23 + 0.7×36 + ~7 (H-UG) + ~5 (H-CI/H-FL, thin) ≈ **+65bp/yr gross**.
**Overlap haircut (important honesty):** the sleeves rebalance daily/weekly and would themselves down-rank a collapsing name part-way through the drift window; the overlay's *incremental* contribution over what the sleeves would do anyway is realistically **50–70% of the raw arithmetic ⇒ ≈ +30–45bp/yr in normal years**.
Costs: ~2 forced round-trips/yr × 8% × 2× (5–20bp one-way by tier) ≈ **−2 to −6bp/yr**; cash carry on vetoed weight ≈ +1–2bp/yr; Tier 3 ≈ 0 by construction (monitored, §6 risk 5).
Crisis year (2008-analog: 11 inversion onsets, downgrade wave, and the EW book's −58% maxDD): 3–5 bindings ⇒ **+150–400bp avoided, concentrated exactly in the left tail**.

**Net expectation: ≈ +0.3–0.5%/yr in normal years, +1.5–4% in stress years, at ≈ −5bp/yr running cost.** The distribution matters more than the mean: this overlay buys drawdown insurance with positive expected premium, which is rare.

---

## 4. Expected performance (overlay-adjusted book, honest arithmetic)

The Event Book has no standalone return stream; its performance is expressed as a delta on the host book. Host baseline from miner MATH (realistic, ETF-capture- and decay-adjusted): **~8–11%/yr total, Sharpe 0.55–0.75, maxDD ≈ −30%** vs plain EW at 7.7%/0.44/−58% (2005–2026 EW stats; −29% maxDD 2015+).

| Metric | Host book | Host + Event Book |
|---|---|---|
| Expected total return | 8–11%/yr | **8.3–11.5%/yr** (+0.3–0.5 normal-yr mean, more in stress years) |
| Expected active return vs EW | +0.6–3.8%/yr (per MATH blended est.) | **+0.9–4.3%/yr** |
| Volatility | ~14–16% (index-based sim) | equal or ~0.2–0.5pp lower (vetoes push into cash at stressed moments) |
| Sharpe | 0.55–0.75 | **+0.02–0.06** vs host |
| Max drawdown | ≈ −30% | **−28% to −30%**; the layer's design payoff is the 2008/2020-analog year where 3–5 simultaneous vetoes are worth 1.5–4% of book |

Every number above traces to: the three event-study CARs (§1.1), the measured event rates (§3.1), the binding-probability assumption (~0.35, labeled), the 8%-weight assumption (labeled), the 50–70% overlap haircut (labeled, conservative), and miner EXEC's tier costs. Nothing else is claimed. The single most fragile input is the downgrade 63d point estimate (CI includes 0); the single firmest is the inversion 63d CAR (CI excludes 0) and the upgrade block (p=.034, 69% negative hit rate).

---

## 5. Capital & sizing

- **Dedicated capital: $0.** The Event Book governs 100% of the $100k by modifying sleeve target weights; it holds nothing itself. Freed weight sits in the book's cash sleeve (IBKR ~3.1–3.8% at $100k NAV — note the first $10k of cash earns zero).
- **Standalone E-R sleeve: $0 at launch**, hard cap $5k, unlockable only by a passing verdict on trials E-1…E-4 (§8).
- **Trade sizes it generates:** forced exits of one position at a time — $5–12k clips (8–12 positions on ~$80–95k invested). At $100k these are 0.5–2.5bp commission + 1.5–10bp half-spread by tier (miner EXEC); the only capacity-flagged ticker, EDEN ($0.8M/day ADV, $10k = 1.25% of ADV), is exited via LOC-with-band and, at 26bp spread, is already excluded from fast sleeves anyway. Fractional shares are enabled, so share counts are irrelevant even for SPY (~$745) and QQQ (~$713) clips.
- **Capacity:** trivially fine — the overlay *reduces* market footprint (its output is fewer/earlier exits and delayed entries), and event-window avoidance scales to institutional size (it is the shorting of these events that doesn't).

---

## 6. Risks & failure modes (top 5, each with a detection signal)

1. **Small-sample fragility of the CARs.** n = 41–54; the EM-downgrade 63d CI includes 0; hit rates are 54–69% negative, so means lean on tails. *Detection:* the per-veto ledger (§9) marks every binding at +5/+21/+63d vs the residual book; a running mean and CI is recomputed after every event; kill rule K-1 (§7) triggers automatically.
2. **Opportunity cost against the book's own reversion engines.** The combiner/graph sleeves systematically like post-stress names — on 2026-06-30 the combiner ranked Turkey #2 and Brazil #5 while both sat inside Q1-2026 inversion windows (expired early June). The veto may repeatedly amputate the sleeves' best convergence longs. *Detection:* "veto opportunity cost" series = forward return of vetoed names at sleeve-implied weights minus book return; if vetoed names cumulatively OUTPERFORM by >1.5% (kill rule K-2), the overlay is fighting the alpha engine and loses.
3. **Event-table data quality.** `sov_ratings_monthly` is month-stamped (true action date hidden ⇒ late anchors); `SOV_CDS_SLOPE_BP` contains at least one artifact (Spain 2025-09-19: −1013bp); a false veto is a real cost. *Detection:* the mandatory sanity gate in V-CI logs `SUSPECT_DATA` rows; every veto requires the underlying quotes (1Y/5Y CDS levels, agency/notch) attached to its ledger entry; a monthly false-positive audit; >1 confirmed false veto per year ⇒ tighten gates before next binding.
4. **Regime shift in the ratings cycle.** 2024–25 was upgrade-heavy (9–10 upgrades/yr vs 2 downgrades in 2024); a benign EM cycle makes V-DG dormant and the layer contributes ≈ nothing while adding process complexity. *Detection:* Tier-1 binding count over trailing 24 months; if <2 total, demote the Event Book to a quarterly-reviewed checklist (no harm done — dormancy is cheap, but flag it honestly).
5. **Tier-3 rules silently taxing alpha.** Calendar delays and basis-filter delays could cost more in missed entries than they save (both are ASADO-untested). *Detection:* every delayed entry logs the counterfactual (undelayed execution price); monthly report of mean delay cost; if delays cost >5bp per occurrence on average over 25+ occurrences, drop the rule and record the negative result against trials E-3/E-5.

---

## 7. Kill criteria (pre-registered, mechanical)

- **K-1 (vetoes don't avoid anything):** after the *earlier of* 12 Tier-1 bindings or 24 months live: if the mean veto-window relative return of vetoed names (vs residual book, close-to-close over each binding's window) is **≥ 0**, kill Tier 1. Interim tripwire: same test at 6 bindings with threshold ≥ +1%.
- **K-2 (fighting the alpha engine):** if cumulative veto opportunity cost (risk 2) exceeds **+1.5% of book** in favor of the vetoed names at any point after ≥6 bindings, kill Tier 1.
- **K-3 (haircut decay):** if the rolling-24-month monthly IC of the flipped inflation-surprise direction turns ≤ 0, drop H-CI; if ETF-flow contrarian sign instability recurs (it is already flagged sign-unstable, 37.5% positive years), drop H-FL on the first 12-month stretch of wrong-signed IC.
- **K-4 (evidence refresh fails):** re-run the three event studies annually with the grown sample; if `downgrade_em` AND `cds_inversion` both lose |t| ≥ 1.5 at 63d once n has grown ≥20%, demote all of Tier 1 to advisory.
- **K-5 (process):** any Tier-1 trade executed off a red governance scorecard, or any veto placed without its evidence bundle in the ledger, is a process kill for the automation until reviewed.

---

## 8. Governance

**Existing evidence backing (by artifact):**
- Event studies (not harness hypotheses — no H_ IDs exist for them): `Data/loop/event_studies/rating_downgrade_20260612_122930`, `downgrade_em_20260612_131744`, `downgrade_dm_20260612_131746`, `downgrade_highvix_20260612_131747`, `downgrade_lowvix_20260612_131748`, `rating_upgrade_20260612_124545`, `cds_inversion_20260612_124544` (+ the 104606 first run), `growth_hot/cold`, `inflation_hot` (null results, used to EXCLUDE surprise-event rules).
- Harness WEAKs used in Tier 2: **H_20260612_015** (ECO_INFL_SURPRISE_Z, flipped, WEAK), **H_20260612_046** (ETF_FLOW_21D_Z, contrarian, WEAK).
- Consciously NOT used: H_20260612_013 (SOV_2S10S — slow tilt, belongs to the slow sleeve), H_20260612_006 (SOV_CDS_SLOPE_Z252 rank — unresolved), CONS_CPI_REV3M (slow sleeve), all DEAD verdicts.

**New trials to register BEFORE any scale-up beyond the rules above (exact specs):**
- **E-1 — Formal event-study freeze.** Re-register the downgrade/inversion/upgrade studies as frozen specs (event source SQL + anchor + window hashed), so the annual K-4 refresh is a re-measure, not a re-registration. No family charge (event-study path), but ledger-logged.
- **E-2 — Rating-change avoidance rank.** Family: `bbg_skill_2026_06` (SOV_ prefix per `family_registry.yaml`). Variable: `SOV_RATING_CHG_63D` (signed notches, either direction, decaying over 63 trading days). Direction: |recent change| → underperform (avoidance rank). Mechanism: agency actions are lagging information cascades that trigger mandate-driven flows; both directions drift negative. Primary horizon: 21d, monthly grid. Purpose: converts the event veto into a rankable variable the harness can grade; 20-country honest sub-universe declared.
- **E-3 — D9 basis-gap event trial vs ETF returns.** Requires a trust-root `family_registry.yaml` edit (new `BASIS_` prefix — flagged, owner-approved, scorecard-visible). Signal: D9 `gap_z`; outcome: **ETF** (not index) forward returns from `etf_prices_daily`; event variant: CARs after |gap_z| ≥ 2.5. Gates rule X-BASIS being credited with value and any E-R capital in basis-reversion trades.
- **E-4 — WEO/D3 event CAR study.** |revision z| ≥ 1.5 × flat 6m momentum conjunctions since 2008 (`weo_revisions`, 36 vintages), `next_month` anchor, quadrant split. Gates any D3-based standalone reaction (Vietnam-style) ever receiving E-R capital.
- **E-5 — Calendar-gate value test.** FX_VOL_TERM_Z252 × `forward_calendar` event-date interaction (miner DOCS §2.11): does pre-event implied-vol term inversion predict post-event drift? Gates rule X-CAL being treated as more than hygiene.
- **D6 prediction-market disagreement** joins the overlay only after ~2026-08 when 60 snapshots exist, and only via its own registered trial.

**Standing constraints honored:** forward-return blacklist (no 1MRet-family inputs anywhere in this sleeve); detectors and Triptych/JST/Gap-Engine stay context-tier; every rule reads only validated or explicitly-labeled-advisory surfaces; scorecard-GREEN gating (§2.4); no writes to any repo database — overlay state lives in the sleeve's own directory.

---

## 9. Implementation sketch

**Data dependencies (must have run before 08:00 ET compute):**
- Nightly loop job (`scripts/loop/loop_daily_job.py`) — specifically the sovereign collector/loader (`sovereign_daily`/`sovereign_signals`, same-day fresh), ratings loader (`sov_ratings_monthly`/`sov_rating_changes`), ETF flow loader (`etf_flow_signals`), market-implied loader (VIX z for the high-VIX acceleration), dislocation build (Tier-3 flags), price_state build (X-BASIS), and the governance scorecard. Monthly: eco-surprise loader. Static-ish: `forward_calendar` (verify `date_confirmed` weekly).
- The overlay tolerates T+2 staleness in Tier-3 inputs (advisory) but requires ≤T+1 freshness in `sov_rating_changes` and same-day `sovereign_signals` for Tier 1; if stale ⇒ fail-safe mode (§2.4).

**Pipeline (one ~200-line script, read-only DB access, no repo writes):**
1. 08:00 ET: connect read-only to loop DB; scan for new Tier-1 triggers (V-DG rows, V-CI onsets with sanity gate); roll forward existing windows (trading-day arithmetic on the NYSE calendar); evaluate Tier-2 states; pull Tier-3 flags.
2. Emit `event_book_state.json` (append-only versions): per country — `{etf, rule, action ∈ {VETO, ADD_BLOCK, HAIRCUT_0.5, DELAY_ENTRY, ADD_FREEZE}, anchor_date, expiry_date, evidence: {source_table, raw_row, quotes}}`.
3. Book allocator applies precedence (§2.0) to `w_pre` → `w_final` → order list.
4. Orders: new Tier-1 exits → MOC (Tier A/A-mega, submit 15:50 ET) or LOC ±30bp band (Tier B/C); delayed entries re-queued with their counterfactual price logged; all via IBKR Pro Tiered + SmartRouting, fractional enabled.
5. Post-close: append fills + marks to the per-veto ledger; update K-1/K-2 statistics; weekly human review of `SUSPECT_DATA` and dormancy stats; annual event-study refresh (K-4).

**Live state the overlay would emit today (2026-07-02) — worked example:**
- **VETO EWW** (Mexico Moody's downgrade, event month 2026-06, EM): anchor 2026-07-01 → expiry ≈ 2026-09-29. Binds: mine_livedb's implied book already zero-weights EWW — overlay makes it mandatory, not advisory.
- **VETO EWQ** (France CDS inversion onset 2026-06-22 at −54bp; sanity gate passes; all-country rule): anchor 2026-06-23 → expiry ≈ 2026-09-21. France was already bottom-8 on the combiner — overlay locks it out.
- **ADD-BLOCK EZA** (South Africa Fitch upgrade, month 2026-07): no adds through ≈ 2026-09-30 — directly binds against South Africa's #3 bank-gap rank; this is the overlay doing its job (never buy the upgrade).
- **HAIRCUT ×0.5:** Germany, Netherlands, France (June inflation z −3.9/−3.7/−3.3) — mostly moot (sleeves have them near zero; Germany's D2 long gets halved if sized).
- **ADD-BLOCKS (flows):** EIDO (+3.14z — also caps the conflicted Indonesia long the live-DB miner flagged), EWI, THD. **ADD-FREEZE:** ECH (Chile D10). **EXEC:** delay adds priced rich — ASHR, QQQ; Taiwan D9 flag → X-BASIS scrutiny on any EWT order. **Expired:** Turkey/Brazil/South Africa Q1 inversion vetoes (lapsed ~2026-06-04/09) — TUR and EWZ are free to be held.

---

## 10. Bottom line

The Event Book converts the warehouse's only validated *event* knowledge — EM downgrades bleed, CDS inversions bleed hard, upgrades are a trap, cold prints and hot inflows are headwinds — into a zero-capital discipline layer that a long-only book can actually monetize, because avoidance is the one side of these anomalies that costs nothing to hold. It binds rarely (~2 Tier-1 events/yr normal, 3–6 in stress), costs single-digit bps to run, and its honest expectation is +0.3–0.5%/yr with a convex payoff concentrated in exactly the years the host book's −30% drawdown estimate comes from. Everything speculative in it is either quarantined to execution timing or parked at $0 behind five pre-specified registrations.
