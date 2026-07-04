# Evidence Miner 3 — Docs & Untested Surfaces

**Date:** 2026-07-02. **Sources read:** README.md (loop + graph-machine sections), PRD_Alpha_Hunting_Loop.md, AGENTS.md, docs/MARKET_IMPLIED_EXTENSION_STATUS.md, docs/PREDMKT_EXTENSION_STATUS.md, docs/JST_MACROHISTORY_CALIBRATION.md, docs/BBG_SKILL_ENHANCEMENTS_2026_06_12.md, docs/factor_reference.md, config/family_registry.yaml, config/triptych_scan.yaml, config/governance_contract.yaml, config/family_ranks.yaml, Data/loop/event_studies/* (all 15 results.json), Data/dislocations/brief_2026_06_30.md, plus read-only DuckDB checks (dislocation_daily fire counts, predmkt archive depth, gap_episodes, triptych_review_queue).

---

## Part 1 — Detector inventory D1–D10

The nightly dislocation engine (`scripts/loop/build_dislocations.py`, Layer 1, deterministic, no LLM) emits rows into `dislocation_daily` (loop DB; 1,070 rows since 2026-06-09) and renders `Data/dislocations/brief_YYYY_MM_DD.md`. Severity = z vs own ~3y history; rows persist across days with status new → persisting/intensifying/fading → resolved, and resolutions are labeled `repriced_with` / `repriced_against` / `decayed` — this resolution history is itself an accumulating (untested) training surface. `flag` = informational, not directional.

**Live:** D1 D2 D3 D4 D5 D7 D8 D9 D10. **Blocked:** D6 (prediction-market accumulation began 2026-06-10). **Fire counts, 2026-06-01 → 06-30 (from `dislocation_daily`):** D1=112, D2=110, D3=14, D4=43, D5=2, D7=101, D8=495, D9=136, D10=57.

| Det | Archetype | Fires on | Recent activity (brief 2026-06-30) |
|---|---|---|---|
| **D1** | A1 ToT impulse without repricing | Comtrade net-trade-share-weighted commodity basket 3m return, z_36m beyond ±1.5, while \|own 21d equity z\| < 0.5 and \|REER 3m z\| < 0.5. v1 basket validated against Saudi/oil-2020 (z −3.3), Chile/copper-2021 (+2.0), Chile/copper-2024 (+1.5). | Very active: shorts on U.K. (new, z −2.41), Italy, Japan, Taiwan, Turkey (all ToT deteriorating, price not repriced — a broad fuel-import story). |
| **D2** | A2 two-hop graph propagation | Exposure-weighted neighbor 21d return minus own return (trade / banking / holder edges) beyond ±1.5z vs 3y; two-hop variant needs middle node repriced, endpoint not. | Very active: Netherlands short (intensifying, −2.77), Switzerland, Philippines, Spain shorts ("country outran neighbors"); Germany long (+1.64, neighbors outran). |
| **D3** | A3 revision momentum | IMF WEO vintage GDP-forecast revision z vs own 2008+ revision history, crossed with 6m price momentum; flags "revised up + flat price" and inverse. 120-day live window per vintage. | Vietnam long persisting 14d (gdp_revision +1.22pp, z=+1.83, momentum flat). |
| **D4** | A4 cross-asset incoherence | Sign disagreement across ≥2 of {equity (t2 daily), FX, 10Y/2Y yields, 5Y+1Y CDS from `sovereign_daily`} with each \|z\|>1 in the same 5d window. | 43 fires in June; none in top rows of 06-30 brief. |
| **D5** | A5 attention without resolution | GDELT attention/tone z > +2 while \|5d return\| < 0.5σ. Constitutionally a LOOK trigger, never a trade signal; triggers evidence-pack freezing. | Nearly silent (2 fires in June). |
| **D6** | A6 predmkt vs sovereign-market disagreement | BLOCKED. Needs ≥60d of prediction-market history; Δprob(5d) >10pts on a country-mapped market with mapped sovereign surface flat, via `predmkt_country_spillover` elasticities (18/34 countries). Archive has 21 snapshot dates (2026-06-10→07-01), `predmkt_resolutions` = 0 rows. | Blocked; ships dark until ~mid-August 2026. |
| **D7** | A7 factor crowding | Cross-sectional dispersion of each of ~106 T2 factor characteristics, rolling z < −1.5 (compression = crowding, de-weight candidate); capped 10/day; plus pairwise factor-return correlation spike (herding). | Active: Best PE_CS, Operating Margin_CS, 20 Day Vol_CS, REER_CS, Debt to EV_CS, GDP_CS all compressed. |
| **D8** | Open-thesis / book stewardship | Every open thesis (frozen entry, distance to invalidation, days to horizon) and every live News-repo book position mapped to T2 country. | Dominant row count (495/month) by construction: 2 open theses (Indonesia, Hong Kong A2 longs, both underwater) + full live ETF book. |
| **D9** | Country index vs ETF gap | T2 country return vs primary US-listed ETF return, rolling 5d/21d gap z vs own history (common-date windows v1.1). A persistent gap = investable expression and index disagree — tradeable basis or data problem. | Taiwan new (gap_z −2.7: local index −3.2% over 5d vs ETF +3.2%). 136 fires in June — the most active non-stewardship detector. |
| **D10** | A10 FX options vs equity | (a) `fx_options_stress_unpriced_by_equity`: RR z ≥ 2 or implied-vol z ≥ 2.5 with \|21d equity z\| ≤ 0.75; (b) `equity_stress_unconfirmed_by_fx_options`: 5d equity z ≤ −1.5 with RR and vol z ≤ 0.5. Pegs (HKD/SAR) included with peg note; US complex, Denmark, Vietnam structurally skipped. | Chile persisting 8d (RR z +2.14, equity flat — depreciation premium unpriced by equity). |

**Brief context sections beyond the detector table** (all inputs to Layer-2 reasoning, none harness-gated): Gap Engine top-5 (pilot), forward calendar (CB decisions: BOK 7/16, ECB 7/23, FOMC 7/29, BOE 7/30), market-implied stress dashboard (DXY z +2.5 on 06-30; Turkey/Chile/Japan/Saudi/South Africa/Switzerland stretched), sovereign 2s10s stretches + rating changes (Mexico Moody's downgrade 2026-06-01) + hot surprises (big DM inflation misses: Germany −3.9z, Netherlands −3.7z, France −3.3z), foreign flows (Korea 5d z −3.0, Taiwan −2.8), ETF positioning (EIDO +3.2z inflow, EWZ −2.1z outflow; TUR short interest 29.9% of shares out, z +3.1), COT, JST long-cycle tail context (Denmark −43% drawdown → dd_35_plus bucket).

---

## Part 2 — Surfaces that exist but were NEVER harness-tested (or are undertested)

Ordered roughly by promise for a LONG-ONLY 34-ETF book with cash. "Test" = the concrete validation path under the governance rules of Part 3 (register → harness → verdict, or event-study for event-shaped claims).

### 2.1 D9 ETF-vs-index basis gap as a reversion signal — NEVER TESTED, most directly tradable
- **What:** `t2_ret5d − etf_ret5d` gap, z vs own history (D9 substrate; `etf_prices_daily` ~800 tickers from the News bridge, one-time yfinance backfill, 34 country ETFs mapped via `etf_t2_map`).
- **Why prices might not know it:** the US-listed ETF is the *only* instrument the book trades; a persistent local-index-vs-ETF gap is either NAV premium/discount that must converge (Asia timezone async washes out over multi-day windows — v1.1 already uses common-date windows) or stale local pricing the ETF will drag. Taiwan just fired at −2.7z. This is the one surface where the tradable instrument itself is part of the signal.
- **Caveat:** the LL_LEADER_GAP tradability trap is adjacent — same-day US-hours embedding. The honest formulation is: does a 5d/21d *persistent* gap z predict next-1-5d ETF (not index) return?
- **Test:** register in a new family (needs a family_registry prefix — trust-root edit), signal = D9 gap_z, outcome = ETF returns from `etf_prices_daily` (not T2 returns — avoids marking the signal on its own numerator), 1d/5d holds, breakeven-cost grid. Event-study variant: CARs after \|gap_z\|≥2.5 days.

### 2.2 TOT_IMPULSE_Z36M as a standalone rank — explicitly flagged UNTESTED in config/family_ranks.yaml
- **What:** D1's terms-of-trade impulse (Comtrade HS-2 net export/import shares × Pink Sheet 3m commodity returns, z vs 36m) WITHOUT the equity/REER quiet gates. All 34 countries, monthly shares, daily-computable. Already shipped as an ungated "context column" in the cockpit (`count_in_agreement: false`, `verdict: UNTESTED`, `hypothesis_id: null`).
- **Why it might know something:** episode-validated (Saudi 2020, Chile 2021/2024); commodity prices are global and instantaneous while country equity indices reprice ToT slowly; D1 currently fires on the *conjunction* only. Nobody has ever asked the harness whether the raw impulse ranks countries.
- **Test:** register `TOT_IMPULSE_Z36M` higher_is_better (exporter windfall → outperformance), monthly and daily variants, 21d primary horizon; charge to a new `tot_` family. Second trial: interact with the D1 quiet gate (impulse × not-yet-repriced) as a conjunction spec.

### 2.3 Foreign investor flows (6 Asian EMs, daily, 2005+) — collected, briefed, never registered
- **What:** `foreign_flows_daily` — exchange-sourced foreign net equity buying for Korea, Taiwan, Thailand, Philippines, Indonesia (Bloomberg, trade-dated, 2005+) + India (NSDL, T+1, 2017+). USD mn, 5d/20d sums, 5d z in the brief.
- **Why:** "the best dataset not yet owned" per the PRD (priority 6); foreign flows lead price in exactly these EMs per a large literature; 20 years of daily history is enough for a real verdict; currently Korea −3.0z / Taiwan −2.8z outflows sit next to Taiwan's D9 gap.
- **Why untested:** landed after the 2026-06-12 systematic pass; no `FF_`-style prefix exists in the family registry yet.
- **Test:** declared honest sub-universe (6 countries — harness scales coverage gate and top-N), flow 5d z and 20d z, both momentum and contrarian registrations are plausible (two trials, same family), 1d/5d holds, cost grid. Also event-study: \|z\|≥3 flow days → forward CARs.
- **Long-only note:** with 6 names this is an overlay/tilt input, not a book — but EWY/EWT/THD/EPHE/EIDO/INDA are exactly the high-cost ETFs where the cost model says edges die; a 21d-hold variant matters.

### 2.4 Macrostructure fragility + debt structure as a SLOW crisis-avoidance gate — never tested in any form
- **What:** warehouse families never touched by the harness: `imf_fsi` (NPL ratio, capital adequacy, liquidity, 2001+, quarterly, ~41 countries), `qpsd` (9 public-debt-structure vars: FX-share, foreign-held share, short-maturity share, 1995+), `macrostructure_derived` (`MS_Investor_Base_Fragility`, `MS_Reserve_Adequacy`, `MS_Swap_Line_Access`, `MS_Policy_Backstop`), `MS_CentralBank_BalanceSheet_GDP` / `MS_CentralBank_SovDebt_Share` (monthly, 1997+), plus `MS_US_Holder_Share_Pct` (annual portfolio ownership).
- **Why prices might not know it:** these are structural vulnerability measures — they don't predict the cross-section month-to-month (likely DEAD as a fast CS rank, and quarterly publication lags make them slow by construction), but they plausibly predict *conditional severity*: which countries fall furthest when a shock arrives (FX-debt-heavy + foreign-held + low reserves). For a long-only book whose only hedge is cash, "which longs to shed first when stress starts" is a first-class question no current signal answers.
- **Test:** two-stage. (a) Event-conditioned: interact fragility quintile with the already-validated downgrade/CDS-inversion event studies — do high-fragility countries drift worse post-event? (b) Regime-conditioned harness run: fragility rank IC measured only in high-VIX / drawdown months (declared at registration as the primary spec, not cherry-picked after). Both charge trials to a new `MS_`-prefix family.

### 2.5 JST drawdown buckets as a cash/deploy conditioner — calibration corpus, deliberately never gated
- **What:** `jst_macrohistory` (1870–2020 annual, 13 DM overlap) → conditional forward 1/3/5y REAL equity distributions by drawdown bucket and banking-crisis state (65 crisis onsets). Headline: dd ≤ −35% → fwd-3y median +8.8%/yr but p10 −12%/yr, P(neg)=27%. Live wiring is context-only (brief section + nightly `build_jst_risk_report.py`).
- **Why:** the modern sample has 3 crises; JST has 65. For long-only sizing, the actionable shape is asymmetric: deep-drawdown countries are *on median* the best forward buys (mean-reversion at bottoms) with a fat left tail — i.e., buy drawdowns but size for the p10. Nobody has tested a "drawdown-bucket tilt" (overweight dd_35_plus names, e.g. Denmark now) or a JST-informed cash rule on the modern 34-country panel.
- **Test:** monthly harness run on trailing-drawdown-bucket membership (a t2-derived variable, PIT-clean) as a slow signal, 6m/12m horizons; separately, a portfolio-level rule study (cash fraction as f(median own-universe drawdown)) — the latter is a strategy-PRD backtest, not a CS harness question. Caveats baked in: live drawdown is nominal vs JST real; EM names are DM-analogy only.

### 2.6 Valuation as a SLOW conditioner / long-horizon signal — only the 1m CS version was killed
- **What:** `valuation_monthly` (CAPE/PB/DY/EY/Trailing-PE + ERP for 32 countries + `_PCTILE_10Y` own-decade percentiles). Verdict DEAD applies to the 1m-horizon cross-sectional percentile ranks (2026-06-12 sweep; `VAL_EY_PCT` was actually ic 0.0297, nw_t 1.96, INSUFFICIENT_COVERAGE — closer to "unproven" than "dead").
- **Why:** valuation's documented horizon is 3–10 years; the harness's monthly primary horizons top out at 6m in the registered specs. And valuation-as-*conditioner* — e.g., ERP percentile gating how much weight momentum/combiner tilts get, or "cheap + upward revisions" conjunctions (E1 archetype) — has never been registered. The Triptych scan grid (horizons out to 36M) already computes exactly these conditional-forward-return tables as PRIOR-tier context (e.g., Shiller PE deciles per country) but priors are barred from being signals without a fresh trial.
- **Test:** (a) one registered trial at 6m primary horizon on `VAL_ERP_PCTILE_10Y` cheap-is-good, full universe; (b) one conjunction trial: ERP decile ≤3 AND CONS_GDP/CPI revision positive. Charge to `valuation` family (prefix `VAL_`, N already includes the dead trials — honest but raises the DSR bar).

### 2.7 Prediction-market composites — structurally blocked, unblocking on a known clock
- **What:** `predmkt_signals_daily` — 14 signals incl. `predmkt_country_risk_composite` / `opportunity_composite` (19 countries), Fed/CPI/unemployment nowcasts, Hormuz/oil-shock probabilities, regional conflict premia, tariff intensity (3 countries); curated registry ~152 markets, spillover elasticities for 18/34 countries. Archive: 21 daily snapshots (2026-06-10 →), 0 resolutions.
- **Why prices might not know it:** prediction markets aggregate event probabilities (elections, tariffs, conflict, CB decisions) that equity indices absorb with delay, and the mapping to countries (elasticity × channel) is hand-curated knowledge the market doesn't publish. D6 is *designed* and waiting.
- **Test:** nothing legitimate is possible until ~60 snapshots (mid-August 2026). Then: D6 disagreement rows → event-study CARs; composite 5d-change as a CS rank on the honest 18-19-country sub-universe. Calibration (Brier vs resolutions) must accumulate before any confidence weighting.

### 2.8 GDELT attention/tone as event trigger — 75 daily factors, 10.2M rows, zero event studies
- **What:** `gdelt_factors_daily` (attention fast/slow/shock/trend, risk, sentiment ±z). Constitution §10.6: never a mechanical signal. But the A5 shape — attention shock WITHOUT price resolution — has never even been event-studied (D5 fired only 2× in June; thresholds may be too tight, and the `dislocation` event-study preset was INSUFFICIENT_EVENTS as of 06-12 because detector history only starts 2026-06-09).
- **Why:** aggregates destroy *what the news says*, but the CAR question ("do attention-z>2/flat-price days predict drift, in either direction?") is a legitimate aggregate test that respects the constitution — it validates D5 as a *look trigger with a measurable base rate*, feeding Layer-2 triage priors rather than a trading rule.
- **Test:** event-study preset with `--events-sql` on historical attention-shock/flat-price conjunctions (computable back to ~2015 from gdelt_factors_daily — does NOT need detector history); split by subsequent-evidence class once evidence packs accumulate.

### 2.9 WEO/D3 revision momentum as EVENT trigger (vs the dead CS rank)
- **What:** `weo_vintages`/`weo_revisions` — 36 vintages 2008+, GDP + CPI forecast paths, revision z vs own history. The CS-rank version (`CONS_GDP_REV3M_12M`, and WEO-derived) tested DEAD/negative. But D3's *conjunction* — big upward revision z AND flat 6m momentum (the current Vietnam row, z +1.83, 14 days active) — is an event shape that was never event-studied.
- **Test:** event-study on \|revision z\| ≥ 1.5 × flat-momentum episodes since 2008 (≈2 vintages/yr × 34 countries gives a usable n), next_month anchoring, quadrant-split (revised-up/flat-price vs revised-down/strong-price). If CARs are real, the trade is the event, not the rank.

### 2.10 Gap Engine tension/absorption scores — a live prediction surface with no validated skill
- **What:** `price_state_daily`/`price_state_surface`/`gap_episodes` (33 episodes since 2026-06-22) — the price-discovery gap machine (2026-06-22 pilot): maps dislocations to ETF expressions, scores "tension" (G1–G4 classes), tracks absorption (unabsorbed / repriced_with / repriced_against). Brief header explicitly: "Absorption is provisional…not yet validated ranking skill."
- **Why:** it is the direct operationalization of the owner's question (what's known vs priced), already emitting ranked long/short candidates with invalidation statements — but 8 of its early episodes show `repriced_against`, and nothing gates it.
- **Test:** forward-mark all episodes (marks table exists: `gap_episode_marks`); after ~60 episodes, test tension-score rank vs realized episode returns; treat the config hash (`gap_engine_v2_2026_07_01`) as the frozen spec. Until then it is context-tier, same rule as Triptych.

### 2.11 Remaining undertested items (shorter list)
- **FX vol TERM slope (`FX_VOL_TERM_Z252`) and butterfly (`FX_BF25_Z252`) as event-timing gates.** First-pass verdicts were INSUFFICIENT_COVERAGE (pre sub-universe scaling; BF had nw_t 2.58); the *level* family is DEAD but "positive term slope = event priced NOW" as a *conditioner on forward-calendar events* (hold-off-buying gate ahead of CB decisions/elections) was never tested. Test: interaction with forward_calendar event dates.
- **`ECO_GROWTH_SURPRISE_Z` on its honest 14-country universe** — INSUFFICIENT_COVERAGE at u34; a clean re-spec at u14 was recommended in AGENTS.md but not run. (Inflation surprise flipped-WEAK sister result suggests the reflation direction.)
- **Commodity curve shape → country mapping.** `CMD_*_CURVE_Z252` (backwardation z for CL/CO/HG/GC/NG) is collected but country attribution is "deliberately left to detectors" — a curve-weighted ToT variant (physical tightness, not just price) was never built or tested.
- **COT speculator positioning (12 futures, 2006+) as exporter-country conditioner** — collected, briefed, never registered.
- **Holder-stress PIT gap (`GRAPHP_PORT_HOLDER_STRESS`).** The PIT re-test validated trade/bank/twohop/Katz/hub/bloc; the holder-stress leg (IMF PIP vintages, +9m lag) is the least-tested edge type of the graph family.
- **Rating *momentum* / notch-distance as CS rank.** `sov_ratings_monthly` (33 countries, 2015+, 3 agencies) is only used as a dated event table; a "recently downgraded, still drifting" rank (EM-only per the event finding) is untested. Note both downgrades AND upgrades drift negative at 63d — the tradable shape for long-only is avoidance, not tilt.
- **Dislocation resolution history as meta-signal.** `repriced_with/against/decayed` labels accumulate per detector; "which detector's fires resolve directionally" is the empirical base-rate table Layer 2 needs and nobody has computed (needs months more history).
- **Demographics (`DIP_*` to 2100), EPU/GPR, BIS credit-gap/property, OECD CLI as slow conditioners** — swept into Triptych PIT priors (context-tier) but individually never harness-registered at long horizons. The Triptych scan is effectively a pre-screen: its review queue (25 rows, PIT-gated: n≥60, bucket n≥8, \|IC t\|≥2, R²≥0.4, extreme decile) is a curated list of exactly these candidate conditioners — but the queue's aggregate lean tested DEAD (H_20260702_001), so any individual promotion is a NEW `TRIPTYCH_`/family-matched trial.

---

## Part 3 — Governance rules a live strategy must respect

**The skeptic architecture (PRD §10, non-negotiable "anti-overfitting constitution"):**
1. **Pre-registration before results.** A hypothesis (`H_YYYYMMDD_NNN`) with mechanism text + sha256 spec hash must exist in the git-tracked, append-only `ledgers/hypothesis_ledger.jsonl` *before* the harness will run. Anonymous backtests fail hard.
2. **Every trial counts.** Deflated Sharpe uses the FAMILY trial count, not N=1. `INSUFFICIENT_*` verdicts count half. Re-specs, flipped re-registrations, gate variants — all new trials.
3. **Canonical families by variable prefix** (`config/family_registry.yaml` v1.1): the family is determined by the signal variable's longest-prefix match (GRAPH*/LL_/SIM_ → network_spillover; ECO_; FX_; SOV_; VAL_; COMBINER_; CONS_; ETF_; momentum_sanity incl. the 1MRet look-ahead canaries; TRIPTYCH_). `register_hypothesis()` RAISES if a variable matches no family — adding a new surface (e.g. foreign flows, D9 gap, MS_ fragility) requires a deliberate trust-root edit to this file, which is git-tracked and reds the scorecard if dirty.
4. **Family-wise budget:** 20 trials without a WATCH → family frozen 6 months.
5. **One primary horizon per hypothesis,** declared at registration; other horizons are diagnostics only.
6. **PIT and embargo enforced INSIDE the harness** (`scripts/harness/evaluate_signal.py`): publication-lag embargo per variable (conservative defaults: monthly → 1m, quarterly → 1q, annual → 12m); daily signals claiming lag-0 must have a valid entry in `config/pit_proof_registry.yaml` or fail closed (scorecard dim `pit_lag_proof`). Gotcha: market-derived monthly tables must set `publication_lag_months: 0` explicitly or get tested a month stale.
7. **Forward-return blacklist:** `1MRet/3MRet/6MRet/12MRet` and daily analogs are optimizer TARGETS, hard-blacklisted as signals.
8. **Verdict gates (harness-written, never by hand):** WATCH needs NW-t(IC) ≥ 2.5 at primary horizon, IC positive ≥60% of years, survives base costs (verdict keyed to net-25bps at the registered hold), deflated Sharpe > 0. Coverage gate ≥28/34 countries at 95% of dates, scaled proportionally when an honest sub-universe is declared at registration. v2.1 adds the 1d/5d/21d hold grid + breakeven bps + 5bps case as *diagnostics* (gates unchanged).
9. **Re-measure ≠ re-register:** measurement upgrades re-run `evaluate_signal` with the existing hypothesis_id (zero new trials); `sweep_signals.py --force` would register NEW trials and inflate N — never use it for measurement.
10. **Promotion path:** WATCH → paper allocation / thesis ledger only. Nothing goes to capital without a separate strategy PRD. Theses (`T_YYYYMMDD_NNN`) freeze entry text + probability + numeric invalidation level at open, are auto-marked from T2 returns (never hand-marked), and feed Brier calibration (report PARTIAL until ≥10 closed).
11. **Context-tier quarantine:** GDELT and attention signals trigger looking, never mechanical trading; Triptych priors are PRIOR/context-tier (queue lean tested DEAD — must not enter the combiner or any rank); JST is calibration-only; Gap Engine absorption is provisional; `tot_impulse` cockpit column is an untested detector substrate and is excluded from cross-family agreement counts; the combiner is excluded from agreement counts (double-counting).
12. **Data hygiene rails:** loop state lives only in `Data/loop/asado_loop.duckdb` + parquets (main DB is deleted on rebuild); optimizer outputs never union into `feature_panel`/`unified_panel` (cycle guard, `validate_returns_first.py`); JST/FF/commodities never tiled to countries; no silent fallbacks — degraded detectors emit loud `DETECTOR_DEGRADED` rows.
13. **Nightly governance scorecard** (`config/governance_contract.yaml` v1.3, stamped atop each brief; GREEN on 2026-06-30): 7 dimensions — run_manifest, liveness, ledger_integrity, family_registry, pit_lag_proof, cross_source_minimal, config_guard. Red on any hard failure ⇒ don't trust that night's warehouse. A live strategy should condition "act on tonight's signals" on scorecard GREEN.
14. **Style-spanning discipline:** `ff_spanning.py` — a candidate whose Sharpe survives but whose FF5+Mom alpha t is insignificant is a repackaged style tilt, not new alpha. Expect any promoted book strategy to report its spanning alpha vs the regional FF bundles.
15. **Cost realism:** nothing survives 25bps one-way; a long-only tilt captures roughly half the LS alpha. Strategy designs must state the assumed one-way cost per ETF tier and use the breakeven grid; fast-family edges (8–14bps breakevens) are only monetizable in cheap-DM/liquid ETFs.

---

## Appendix — Event-study verdicts on file (Data/loop/event_studies/, all 2026-06-12)

| Study | n | +5d CAR (t) | +63d CAR (t) | Read |
|---|---|---|---|---|
| rating_downgrade (all) | 73 | −0.7% (−2.0) | −2.1% (−1.5) | Real 5d drift |
| downgrade_em | 54 | −0.9% (−2.0) | −2.8% (−1.5) | EM phenomenon |
| downgrade_dm | 19 | −0.1% (−0.3) | −0.1% (−0.2) | DM flat |
| downgrade_highvix | 23 | −1.3% (−2.1) | −0.7% (−0.2) | High-VIX: hits immediately |
| downgrade_lowvix | 50 | −0.4% (−1.0) | −2.8% (−1.8) | Low-VIX: slow drift |
| rating_upgrade | 45 | −0.3% (−0.7) | −2.4% (−2.2, hit 0.31) | Upgrades ALSO drift negative — avoidance, not tilt |
| cds_inversion | 41 | −0.6% (−0.5) | −4.5% (−2.4) | Strongest event; exit/avoid on 1Y>5Y CDS |
| growth_hot / growth_cold | 370/206 | ~0 | ~0 | No event drift |
| inflation_hot | 502–1013 | ~0 | −0.3…−0.6% (ns) | Nothing at event level (CS flip lives elsewhere) |
| dislocation preset | 0 | — | — | INSUFFICIENT_EVENTS until detector history accumulates |
