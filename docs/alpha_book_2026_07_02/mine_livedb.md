# Live Database State Report — ASADO Loop DB (Evidence Miner 2)

Run date: 2026-07-02. All queries read-only against
`/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb` (loop) and
`/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb` (main, predmkt tables only).
Latest nightly brief read in full: `Data/dislocations/brief_2026_06_30.md` (data as-of 2026-06-30, generated 2026-07-02, governance scorecard **GREEN**, all 7 dims green; working tree dirty).

---

## 1. Table inventory and freshness (loop DB, 59 objects)

| Table | Rows | Latest date | Countries @ latest | Freshness verdict (vs 2026-07-01 trading day) |
|---|---|---|---|---|
| combiner_scores_daily | 167,009 | **2026-06-30** | 31 (29 in validated family_ranks universe) | T+2 lag — needs nightly run before trading 07-02/03 |
| combiner_scores (monthly) | 8,136 | 2026-06-30 | 31 | monthly variant is DEAD as a signal anyway |
| combiner_weights | 154 | keyed by train_through | — | walk-forward coefs, OK |
| graph_features_pit_daily | 1,843,587 | 2026-06-30 | 31 (per-var 21–34) | T+2, nightly cadence |
| graph_features_daily (non-PIT legacy) | 1,327,251 | 2026-06-30 | 31 | superseded by PIT table |
| similarity_features_daily | 452,667 | 2026-06-30 | 34 | T+2, nightly |
| similarity_twins | 54,230 | month 2026-07-01 | — | fresh |
| leadlag_features_daily | 357,702 | 2026-06-30 | 24 (15 followers ranked) | T+2, nightly |
| leadlag_edges | 85,703 | month 2026-06 | — | monthly, OK |
| sovereign_daily / sovereign_signals | 454,688 / 372,874 | **2026-07-02** | 33 / 31 | FRESH (same-day) |
| sov_ratings_monthly / sov_rating_changes | 12,588 / 128 | 2026-07-01 | 20 / 1 | fresh; 20 rated countries only |
| eco_surprise_signals | 28,014 | **2026-06-01** | 15 | monthly; GDP variant only 2026-03 — STALE for daily use, normal cadence |
| consensus_daily / consensus_signals | 923,448 / 14,124 | 2026-07-02 / stamped 2026-07-31 | 34 | FRESH (month-end forward stamp convention) |
| etf_flows / etf_flow_signals | 416,212 / 546,515 | **2026-07-01** | 34 | FRESH; but ETF_SHORT_PCT_Z from FINRA settle **2026-06-15** (biweekly, stale-by-design ~2 wks) |
| etf_prices_daily | 214,450 | 2026-07-01 | 34 ETFs | FRESH (only 1y history: starts 2025-06-09) |
| market_implied_daily / market_implied_signals | 989,289 / 982,811 | **2026-07-02** | 31 | FRESH (FX vol/RR/BF/carry, VIX/MOVE/OAS, commodity curves) |
| foreign_flows_daily | 58,047 | 2026-07-02 | **6 only** (India, Indonesia, Korea, Philippines, Taiwan, Thailand) | fresh, narrow universe |
| dislocation_daily | 1,070 | 2026-06-30 | — | T+2 nightly; table only starts 2026-06-09 (young) |
| price_state_daily / price_state_surface | 34 / 272 | 2026-06-30 (single snapshot) | 34 | snapshot-only tables, rebuilt nightly |
| family_ranks_daily | 969,999 | mixed: combiner/graph/twins/leadlag 06-30; etf_contra 07-01; cpi_rev 07-31 stamp; **tot_impulse 2026-05-01** | 15–34 | tot_impulse ~2 months behind (Pink Sheet lag) |
| valuation_monthly | 128,808 | stamped 2026-07-31 (CAPE 2026-06-30) | 34 | fresh; context-tier only (DEAD as signal) |
| triptych_signal_monthly / triptych_scan / triptych_review_queue / triptych_priors | 18,102 / 165,642 / 25 / 81,582 | as_of 2026-07 | 34 | fresh; **context-tier ONLY** (H_20260702_001 IC −0.003) |
| cot_signals / cot_weekly | 12,528 / 38,484 | 2026-06-23 | commodities | weekly cadence, OK |
| weo_vintages / weo_revisions | 16,863 / 15,163 | vintage 2026-04-15 | 34 | quarterly WEO — normal |
| gap_episodes / marks / autopsy / expression | 33 / 136 / 11 / 34 | marks 2026-06-30 | — | pilot gap engine; 22 episodes open |
| portfolio_holdings_daily / portfolio_summary_daily | 1,022 / 17 | 2026-07-01 | — | mirror of the owner's REAL ~$33–40M book (holdings_stale=1) — context, not the $100k design |
| hypothesis_ledger / harness_results / harness_ic_series | 58 / 89 / 1.15M | run 2026-06-16 | — | validation artifacts |
| thesis_ledger / thesis_marks | 3 / 70 | marks ~06-30 | — | 2 open paper theses (see §5) |
| live_signals (view) | 16 | — | — | **all 16 rows show effective_verdict = INSUFFICIENT_COVERAGE** (see §7) |
| forward_calendar | 50 | events to 2026-12-18 | — | fresh |
| gdelt_articles_recent | 1,116 | pull-date keyed | — | news bridge cache |
| etf_t2_map | 34 | — | — | matches the ETF map in the task spec |

**predmkt (main DB):** predmkt_daily / predmkt_signals_daily latest snapshot **2026-07-01** — FRESH but only ONE snapshot date in the main DB (main DB is rebuilt monthly; history lives in `Data/loop/predmkt_archive`). D6 predmkt detector still **blocked** ("accumulating since 2026-06-10").

---

## 2. Today's combiner cross-section (COMBINER_RIDGE_DAILY_V1, 2026-06-30)

Validated 29-country family-rank universe (raw table also scores Taiwan +0.00233 and Saudi Arabia −0.00058, excluded from the validated ranks):

**TOP 8 (long candidates)**
| Rank | Country | ETF | Score |
|---|---|---|---|
| 1 | Indonesia | EIDO | +0.00492 |
| 2 | Turkey | TUR | +0.00215 |
| 3 | Hong Kong | EWH | +0.00103 |
| 4 | Poland | EPOL | +0.00093 |
| 5 | Brazil | EWZ | +0.00074 |
| 6 | Philippines | EPHE | +0.00066 |
| 7 | U.S. | SPY | +0.00058 |
| 8 | India | INDA | +0.00058 |

**BOTTOM 8 (avoid / cash side)**
| Rank | Country | ETF | Score |
|---|---|---|---|
| 29 | Netherlands | EWN | −0.00443 |
| 28 | Denmark | EDEN | −0.00256 |
| 27 | Thailand | THD | −0.00182 |
| 26 | Switzerland | EWL | −0.00171 |
| 25 | Sweden | EWD | −0.00155 |
| 24 | Korea | EWY | −0.00139 |
| 23 | France | EWQ | −0.00106 |
| 22 | Spain | EWP | −0.00098 |

(Mid-table longs if raw 31-country table used: Taiwan would be #2 — flagged D9 basis dislocation, see §4.)

## 3. Latest graph-family gaps (2026-06-30; positive gap = neighbors outran focal = bullish per registered IC sign)

- **GRAPHP_BANK_NBR_RET_GAP_21D** (21 countries): top Hong Kong +0.068, Germany +0.041, South Africa +0.038, Brazil +0.027, Korea +0.019; bottom Netherlands −0.112, Philippines −0.086, Spain −0.049, Switzerland −0.042, Denmark −0.040.
- **GRAPHP_TWOHOP_TRADE_GAP_21D** (30): top ChinaA +0.080, Indonesia +0.074, Hong Kong +0.071, Poland +0.037, Malaysia +0.032; bottom Netherlands −0.131, Philippines −0.094, Spain −0.070, Switzerland −0.050, India −0.045.
- **SIM_NBR_RET_GAP_63D** (34): top Indonesia +0.295, India +0.114, Brazil +0.106, ChinaH +0.094, Malaysia +0.086; bottom Korea −0.566, Taiwan −0.249, Vietnam −0.225, US SmallCap −0.156, Denmark −0.108.
- **LL_LEADER_GAP_5D** (24 valued / 15 ranked followers): top Indonesia +0.088, Turkey +0.055, Philippines +0.051, Taiwan +0.043, Poland +0.037; bottom Netherlands −0.044, Thailand −0.019, Korea −0.018. (Tradability trap stands: computed on local-index returns; US-listed follower ETFs embed the US move same-day.)

**Consensus across families:** Indonesia is #1 in combiner, twins, leadlag and #2 twohop. Hong Kong #1 bank-gap / #3 combiner / #3 twohop. Netherlands is dead-last in combiner, bank-gap, twohop, leadlag and 33/34 twins. Philippines is split — bottom of graph/twins ("outran neighbors", D2 short persisting sev −2.4) but #2 leadlag and #1 CPI-revision.

## 4. Extremes (|z| >= 2) on the fast surfaces

**ETF 21d flows (2026-07-01, contrarian-validated: inflow = headwind):** Indonesia EIDO +3.14, Italy EWI +2.96, Thailand THD +2.65 (inflow extremes); Malaysia EWM −3.14, Brazil EWZ −2.11 (outflow extremes = contrarian tailwind).
**Short interest (FINRA 2026-06-15):** Turkey TUR z +3.09 (SI 29.9% of sh out), Sweden +2.72, Indonesia +2.71, NASDAQ QQQ +2.53, Germany +2.45, ChinaH MCHI +2.41, Italy +2.33, Korea +2.12.
**FX options (2026-07-02):** Turkey RR z −2.98 / impvol z −2.13 / BF z −2.36 (depreciation premium UNWINDING = calm); Chile RR z +2.00, carry z −2.87 (stress building); Japan BF z +2.46 (tail premium); South Africa carry z +2.10; Saudi carry z −2.20.
**Sovereign 2s10s (2026-07-02):** U.S./NASDAQ/US SmallCap z −2.06, Indonesia −2.22 (flattening); Japan +2.54 (steepening).
**Global risk dashboard (07-01/07-02):** VIX z −0.47, MOVE z −0.61, HY OAS z −0.65 (all calm) but **DXY z +2.07** (dollar strength extreme — EM headwind watch); NG curve pct +2.99.
**ETF-vs-country basis gaps (price_state_daily 2026-06-30):** ETF cheap vs country: Philippines EPHE z −2.99, Netherlands EWN −2.47, South Africa EZA −1.87; ETF rich: NASDAQ QQQ +2.39, ChinaA ASHR +2.13 (ASHR 21d premium ~10%!), Taiwan EWT +1.51 (D9 flag, gap_z −2.7 on 5d window).

## 5. Active dislocations & open theses (brief 2026-06-30, 53 rows: 8 new, 2 intensifying, 36 persisting, 7 resolved)

Directional (non-flag) actives:
- **Netherlands SHORT** D2 intensifying sev −2.77 day 5 (own_ret21_z +1.55, outran neighbors).
- **Switzerland SHORT** D2 intensifying −2.19 day 3.
- **U.K. SHORT** D1 new −2.41 (ToT deteriorating, not repriced) — also gap-engine #1 ("U.K. short", EWU, 21d).
- Persisting shorts: Italy D1 −2.49, Japan D1 −2.44, Philippines D2 −2.40, Taiwan D1 −2.34, Turkey D1 −2.18, Spain D2 −1.92.
- **Germany LONG** D2 persisting +1.64 (neighbors outran).
- **Vietnam LONG** D3 persisting +1.83 day 14 (WEO GDP revision +1.22pp, price not followed) — gap-engine #2 (VNM, 63d horizon), though absorption already "repriced_against".
- Flags: D9 Taiwan basis gap −2.7; D10 Chile FX-stress-vs-equity +2.14 day 8; six D7 crowding flags (Best PE_CS, Operating Margin_CS, 20 Day Vol_CS, REER_CS, Debt to EV_CS, GDP_CS dispersion compressed).
- Regime context: **R7_Transition** (as of 2026-04-01), context only.

Open paper theses: **T_20260610_001 Indonesia long** (cum −5.7% vs −7.0% invalidation — one bad week from a kill), **T_20260610_002 Hong Kong long** (cum −2.2%); T_20260610_003 Taiwan killed_review. Gap engine: 22 episodes open (U.K. newest 06-30); 11 autopsied.

Event overlay: **Mexico Moody's DOWNGRADE 2026-06-01** (13→12) — validated event drift says EM downgrades bleed −0.9%@5d / −2.8%@63d: EWW negative overlay through ~August. Eco surprises: Germany/Netherlands/France inflation z −3.9/−3.7/−3.3 (validated FLIPPED sign: cold prints = bearish for relative performance). Forward calendar: BOK 07-16, ECB 07-23, FOMC 07-29, BOE 07-30.

## 6. Prediction markets (main DB, 2026-07-01)

Country opportunity composite: NASDAQ +0.184, U.S. +0.130, Brazil +0.104, Mexico +0.093, Spain +0.064, India +0.046. Risk composite: US SmallCap +0.242, Poland +0.090, Saudi Arabia +0.087, Turkey +0.033. Globals: recession 12m 14.2%, Hormuz 90d 26.1%, oil shock 30d 4.7%, Fed cut count 0.22, conflict premia E.Europe 0.279 / MidEast 0.227 / Pacific 0.054. Coverage thin (n_markets 1–22, confidence 0.6); D6 detector still blocked pending history.

## 7. "If we traded it tomorrow morning" — hypothetical $100k long-only book

Signals aligned enough to act on (combiner + >=1 confirming family, minus contrarian-flow/thesis warnings):
- **Core longs (combiner top, graph-confirmed):** EWH Hong Kong (bank-gap #1, twohop #3), EPOL Poland, EWZ Brazil (twins #3, flow-contrarian tailwind −2.11z), INDA India (twins #2), SPY U.S. (predmkt opportunity #2).
- **Conflicted longs, size down:** EIDO Indonesia — #1 on four families but +3.14z inflow (contrarian headwind), SI z +2.7, and the open Indonesia thesis is at −5.7% vs −7% kill. TUR Turkey — combiner #2, leadlag #2, FX-stress unwinding (RR z −3), but SI z +3.1 and D1 ToT short persisting. EPHE Philippines — leadlag/CPI-rev longs vs graph shorts + D2 short.
- **Zero-weight (cash instead — long-only cannot short):** EWN Netherlands (worst on 5 families, D2 intensifying), EDEN Denmark, THD Thailand (inflow +2.65z), EWL Switzerland (D2 intensifying), EWD Sweden, EWY Korea (twins −0.57, foreign outflow 5d z −3.0), EWQ France, EWP Spain, EWU U.K. (D1 new short, gap-engine #1), EWJ Japan (D1 short), EWI Italy (D1 short + inflow +2.96z), EWW Mexico (downgrade drift window).
- **Cash** is the residual hedge; DXY z +2.07 and R7_Transition argue for a nontrivial cash sleeve.

**Ops gate before trading:** the fast book is priced off 2026-06-30 scores. The nightly loop job (or `scripts/loop/loop_daily_job.py`) must run to roll combiner/graph/leadlag/dislocations to 07-01/07-02; market-implied, sovereign, consensus, ETF flows and predmkt are already current (07-01/07-02). Monthly-cadence inputs (eco surprises 06-01, ToT impulse 05-01, WEO 04-15, FINRA SI 06-15) are stale-by-design — fine for slow overlays, not for daily ranks. `live_signals` view currently shows all 16 registered hypotheses as effective_verdict=INSUFFICIENT_COVERAGE — governance scorecard is green, but any book built "only on registered live signals" should note the registry's effective verdicts do not currently mirror the harness digest; reconcile before go-live. foreign_flows_daily covers only 6 Asian markets. etf_prices_daily has only ~13 months of history (starts 2025-06-09) — fine for execution, not for backtests.
