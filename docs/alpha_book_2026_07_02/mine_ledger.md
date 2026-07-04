# ASADO Evidence Inventory — Ledgers & Harness Mine (Evidence Miner 1)

**Compiled:** 2026-07-02
**Sources (all read-only):**
- `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/ledgers/hypothesis_ledger.jsonl` (59 registrations, 89 verdict events, 1 status event)
- `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/ledgers/thesis_ledger.jsonl` (3 theses, 3 reviews, 1 close, 70 marks)
- `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/harness_runs/` — 91 per-hypothesis run JSONs (newest per hypothesis used), `remeasure_20260612.log`
- `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/harness_runs/sweeps/` — 23 sweep summaries

Scope note: this inventory covers the formal hypothesis/thesis ledgers and skeptic-harness runs ONLY. Event studies (rating changes, CDS inversions) and the FF spanning tests live outside these ledgers and are not re-derived here.

---

## 1. How to read the verdicts (critical context)

The harness verdict ladder observed in the data: `INSUFFICIENT_COVERAGE` (portfolio stage refused; coverage gate ~95% of dates ≥ min-countries), `DEAD`, `WEAK`, `WATCH`. **No hypothesis has ever been verdicted above WEAK.** Every completed run has a **negative deflated Sharpe** (range −0.02 to −0.54) because the deflation charges the full trial count; "WEAK" in this ledger means *statistically real IC (NW-t typically >2.3) but not net-of-cost viable at the harness's 25 bps reference cost*. The only WATCH ever issued (H_20260610_001, `12MRet`) was retired within 2 hours as a **lookahead leak** (forward return mislabeled as trailing; variable now blacklisted) — the sanity machinery works.

Verdict census over 59 registered hypotheses: **21 WEAK, 21 DEAD, 16 INSUFFICIENT_COVERAGE, 1 WATCH→retired(leak)**. Every registration received a verdict; 15 of the 16 INSUFFICIENT_COVERAGE runs were re-registered with corrected universes and resolved under new IDs. Exactly **one loose end: H_20260612_006 `SOV_CDS_SLOPE_Z252`** — coverage-gated (18 countries), never re-tested (its IC was ~0, t=0.18, so nobody bothered; still formally unresolved).

All daily WEAK/DEAD signals were **re-measured 2026-06-12 under harness v2.1** (hold-period grid 1d/5d/21d + breakeven cost) — the remeasure changed no verdicts, so the WEAK set is stable across the v2.0→v2.1 specification change.

---

## 2. Master evidence table (final verdict per hypothesis, newest harness run)

IC/NW-t at primary horizon (5d for daily, 1m for monthly). "Halves" = sign of summed yearly IC in first/second half of sample. BE = breakeven one-way cost bps (best hold). N = universe size. DS = deflated Sharpe.

### Family: momentum_sanity (2 trials)
| ID | Variable | Verdict | IC | NW-t | DS | Notes |
|---|---|---|---|---|---|---|
| H_20260610_001 | 12MRet | WATCH→**RETIRED (LEAK)** | 0.250 | 15.4 | 0.84 | Forward return; blacklisted. Trial still counted. |
| H_20260610_002 | 12-1MTR_CS | **DEAD** | −0.003 | −0.13 | −0.13 | **Classic 12-1 monthly momentum does NOT work in this 34-country universe** (2008+, halves −/+). |

### Family: graph_trade_gap (15 trials) — network spillover, daily
| ID | Variable | Verdict | IC(5d) | NW-t | posyrs | Halves | BE bps (1d/5d/21d) | N | Sample |
|---|---|---|---|---|---|---|---|---|---|
| H_20260610_003 | GRAPH_TRADE_NBR_RET_GAP_21D | WEAK | 0.019 | 3.07 | 74% | +/− | 8.8/8.7/8.1 | 34 | 2008+ |
| H_20260612_022 | GRAPH_TRADE_NBR_RET_GAP_63D | WEAK | 0.016 | 2.87 | 73% | +/+ | 11.7/13.2/9.9 | 30 | 2001+ |
| H_20260612_023 | GRAPH_BANK_NBR_RET_GAP_21D | WEAK | 0.034 | 5.67 | 81% | +/+ | 11.9/12.2/12.8 | 21 | 2001+ |
| H_20260612_024 | GRAPH_BANK_NBR_RET_GAP_63D | WEAK | 0.019 | 2.99 | 69% | +/+ | 13.7/12.3/4.8 | 21 | 2001+ |
| H_20260612_025 | GRAPH_TWOHOP_TRADE_GAP_21D | WEAK | 0.025 | 4.46 | 89% | +/+ | 10.8/10.3/9.7 | 30 | 2001+ |
| H_20260612_026 | GRAPH_PORT_HOLDER_STRESS_21D | DEAD | −0.007 | −1.32 | 39% | −/− | neg | 31 | 2001+ |
| H_20260612_027 | GRAPH_NBR_DRAWDOWN_COUNT | DEAD | −0.001 | −0.13 | 54% | +/− | ~0 | 31 | 2001+ |
| H_20260612_034 | GRAPHP_BANK_NBR_RET_GAP_21D | INSUF_COV | 0.041 | 6.30 | 81% | +/+ | — | 21 | re-run as _041 |
| H_20260612_035 | GRAPHP_TWOHOP_TRADE_GAP_21D | WEAK | 0.025 | 4.40 | 85% | +/+ | 10.2/10.3/9.6 | 31 | 2001+ |
| H_20260612_036 | GRAPHP_TRADE_NBR_RET_GAP_21D | WEAK | 0.022 | 4.10 | 81% | +/+ | 8.0/8.8/9.6 | 31 | 2001+ |
| H_20260612_037 | GRAPHP_TRADE_NBR_RET_GAP_63D | WEAK | 0.014 | 2.51 | 69% | +/+ | 11.1/12.6/9.6 | 31 | 2001+ |
| H_20260612_038 | GRAPHP_KATZ_TRADE_GAP_21D | WEAK | 0.024 | 4.25 | 77% | +/+ | 9.2/9.7/10.1 | 31 | 2001+ |
| H_20260612_039 | GRAPHP_HUB_GAP_21D | WEAK | 0.022 | 4.00 | 85% | +/+ | 8.2/8.7/8.8 | 31 | 2001+ |
| H_20260612_040 | GRAPHP_BLOC_GAP_21D | WEAK | 0.016 | 3.17 | 69% | +/+ | 4.6/6.6/7.3 | 31 | 2001+ |
| H_20260612_041 | GRAPHP_BANK_NBR_RET_GAP_21D | **WEAK** | 0.034 | 4.46 | 74% | +/+ | **13.1**/11.6/9.8 | 17 | 2008+ (stable BIS reporters) |

Direction: higher-is-better throughout (neighbors outran you → you catch up). PIT (`GRAPHP_`) versions confirm the current-weight (`GRAPH_`) versions — the family **survived the point-in-time edge re-test** at nearly identical IC. Portfolio-channel features (holder stress, drawdown count) are the only structural DEADs.

### Family: fund_similarity_2026_06 (2 trials) — fundamental twins, daily
| ID | Variable | Verdict | IC(5d) | NW-t | posyrs | Halves | BE bps (1d/5d/21d) | N |
|---|---|---|---|---|---|---|---|---|
| H_20260612_042 | SIM_NBR_RET_GAP_21D | WEAK | 0.028 | 5.64 | 85% | +/+ | 11.3/13.3/14.1 | 34 |
| H_20260612_043 | SIM_NBR_RET_GAP_63D | WEAK | 0.019 | 3.67 | 77% | +/+ | 14.1/16.3/**18.3** | 34 |

2/2 WEAK, full 34-country universe, 2001+, positive both halves. **SIM_NBR_RET_GAP_63D at 21d hold has the best slow-hold cost economics in the entire ledger** (BE 18.3 bps, net LS Sharpe +0.166 at 10 bps) and the lowest deflation penalty (DS −0.029, the least-negative of any completed run).

### Family: leadlag_2026_06 (6 trials) — lead-lag network, daily
| ID | Variable | Verdict | IC(5d) | NW-t | posyrs | Halves | BE bps (1d/5d/21d) | N |
|---|---|---|---|---|---|---|---|---|
| H_20260612_044 | LL_LEADER_RET_1D | INSUF_COV | 0.024 | 7.38 | 85% | +/+ | — | 34 |
| H_20260612_045 | LL_LEADER_GAP_5D | INSUF_COV | 0.060 | 11.29 | 96% | +/+ | — | 34 |
| H_20260612_047 | LL_LEADER_GAP_5D | INSUF_COV | 0.060 | 9.12 | 96% | +/+ | — | 17 |
| H_20260612_048 | LL_LEADER_RET_1D | WEAK | 0.024 | 6.40 | 83% | +/+ | 3.1/4.6/3.9 | 16 |
| H_20260612_049 | LL_LEADER_GAP_5D | **WEAK** | 0.057 | 8.48 | 92% | +/+ | **10.2**/10.4/7.2 | 16 |
| H_20260612_055 | LL_LEADER_GAP_5D | WEAK | 0.057 | 8.48 | 92% | +/+ | 10.2/10.4/7.2 | 16 | (duplicate re-register of _049 spec) |

Highest raw IC in the ledger after the combiner. Followers = 16 structural followers (Asia/Europe; U.S. leads, is never led; Denmark dropped for coverage). Gross 1d-hold LS Sharpe 2.44. **Tradability trap stands: tested on LOCAL-index returns; US-listed follower ETFs already embed the US leader move same-day.** LL_LEADER_RET_1D is real (t 6.4) but turnover kills it (BE 3.1–4.6 bps).

### Family: ml_combiner_2026_06 (5 trials)
| ID | Variable | Verdict | IC | NW-t | posyrs | Halves | BE bps (1d/5d/21d) | N | Notes |
|---|---|---|---|---|---|---|---|---|---|
| H_20260612_050 | COMBINER_RIDGE_V1 (monthly) | INSUF_COV | −0.001 | −0.11 | 48% | −/+ | — | 34 | 2006+ |
| H_20260612_051 | COMBINER_RIDGE_V1 lag0 | INSUF_COV | 0.024 | 1.89 | 62% | +/+ | — | 34 | |
| H_20260612_052 | COMBINER_RIDGE_V1 2012+ | **DEAD** | 0.017 | 1.08 | 53% | +/+ | — | 34 | monthly combiner is dead |
| H_20260612_053 | COMBINER_RIDGE_DAILY_V1 | INSUF_COV | 0.056 | 10.47 | 95% | +/+ | — | 34 | re-run as _054 |
| H_20260612_054 | COMBINER_RIDGE_DAILY_V1 | **WEAK** | **0.057** | **10.73** | **95%** | +/+ | **14.2**/13.7/11.7 | 29 | 2006+, gross 1d LS Sharpe 3.32, net 10bps 0.99 |

The daily combiner is the strongest registered surface: IC 0.0574, NW-t 10.7, 95% positive years, best breakeven (14.2 bps at 1d hold), net LS Sharpe at 5/10 bps = 2.15/0.99 (1d hold). **Standing caveat from the ledger itself: its six components were selected in-sample 2026-06 — these numbers are a ceiling; forward verification pending.** Live table: `combiner_scores_daily` in the loop DB.

### Family: bbg_skill_2026_06 (16 trials) — FX surfaces, sovereign curves, eco surprises
| ID | Variable | Dir | Verdict | IC | NW-t | Halves | Notes |
|---|---|---|---|---|---|---|---|
| H_20260612_001 | FX_CARRY_3M_PCT | high | DEAD | −0.007 | −0.86 | −/− | carry level dead |
| H_20260612_002 | FX_CARRY_Z252 | high | DEAD | 0.002 | 0.27 | −/+ | carry z dead (63d IC 0.037 t 1.76, still DEAD) |
| H_20260612_010 | FX_VOL_TERM_Z252 | low | DEAD | 0.003 | 0.50 | +/+ | |
| H_20260612_011 | FX_BF25_Z252 | low | DEAD | 0.016 | 2.57 | +/+ | **wrong-direction DEAD — see §5 loose ends** |
| H_20260612_012 | FX_RR25_Z252 | low | DEAD | 0.002 | 0.28 | +/+ | |
| H_20260612_013 | SOV_2S10S_Z252 | high | DEAD | 0.010 | 1.46 | +/+ | **21d hold: BE 15.8, net10 +0.08** — slow-signal exception |
| H_20260612_014 | ECO_GROWTH_SURPRISE_Z | high | DEAD | 0.002 | 0.09 | +/− | growth surprises carry nothing |
| H_20260612_009 | ECO_INFL_SURPRISE_Z | low | DEAD | 0.036 | 2.99 | +/+ | direction wrong as registered |
| H_20260612_015 | ECO_INFL_SURPRISE_Z | high | **WEAK** | 0.036 | 2.99 | +/+ | **FLIPPED** re-registration: hot inflation print → outperformance (reflation channel). Monthly, N=34, gross LS 0.56, net10 0.11 |
| H_20260612_030 | FX_IMPVOL_Z252 | low | DEAD | 0.011 | 1.58 | +/+ | 63d IC +0.055 t 2.57 in the UNregistered direction — see §5 |
| H_20260612_006 | SOV_CDS_SLOPE_Z252 | — | INSUF_COV | 0.002 | 0.18 | +/+ | **never re-tested — only unresolved registration** |
| (5 more coverage-gated rounds: _003/_004/_005/_007/_008 → resolved via v2 re-runs above) |

Net: FX-derivative surfaces (carry, implied vol level, term structure, risk reversals, butterflies) are 0-for-all as *registered*; the single WEAK is the flipped inflation surprise.

### Family: valuation_2026_06 (5 trials) — all DEAD
| ID | Variable | Verdict | IC(1m) | NW-t | Notes |
|---|---|---|---|---|---|
| H_20260612_016 | VAL_CAPE_PCTILE_10Y | DEAD | 0.018 | 1.12 | Registered cheap-is-good; IC sign says expensive kept winning (6m IC 0.054, t 1.95 anti-value) |
| H_20260612_017/_033 | VAL_EY_PCT | DEAD | 0.010 | 0.61 | earnings-yield level dead |
| H_20260612_018 | VAL_ERP_PCT_PCTILE_10Y | DEAD | −0.018 | −1.16 | |
| H_20260612_019 | VAL_DY_PCT_PCTILE_10Y | DEAD | −0.001 | −0.05 | |

Valuation percentiles are unambiguously dead as monthly CS return signals in this universe (2001–2026). Do not build return strategies on them; context tier only.

### Family: consensus_ecfc_2026_06 (4 trials)
| ID | Variable | Verdict | IC(1m) | NW-t | Halves | Notes |
|---|---|---|---|---|---|---|
| H_20260612_028/_031 | CONS_GDP_REV3M_12M | DEAD | −0.014 | −0.74 | −/+ | GDP revision momentum dead (even mildly negative) |
| H_20260612_029/_032 | CONS_CPI_REV3M_12M | **WEAK** | 0.039 | 2.31 | +/+ | 2013+ only, 159 monthly dates, N=34; gross LS 0.43, net10 0.26; 3m IC 0.053. Same reflation direction as flipped inflation surprise |

### Family: etf_flows_2026_06 (3 trials)
| ID | Variable | Dir | Verdict | IC(5d) | NW-t | BE bps | Notes |
|---|---|---|---|---|---|---|---|
| H_20260612_020 | ETF_FLOW_21D_Z | high | DEAD | −0.012 | −2.20 | neg | flow momentum dead |
| H_20260612_021 | ETF_SHORT_PCT_Z | low | DEAD | −0.003 | −0.27 | neg | short interest dead |
| H_20260612_046 | ETF_FLOW_21D_Z | low | **WEAK** | −0.012 | −2.20 | **2.3–3.9** | **FLIPPED contrarian** (big inflows → underperform). Statistically real but BE ≤3.9 bps ⇒ effectively untradable stand-alone; also sign-unstable (37.5% positive years, halves −/+, contrarian edge concentrated 2011-2015) |

### Family: triptych_prior_2026_07 (1 trial)
| ID | Variable | Verdict | IC(1m) | NW-t | Notes |
|---|---|---|---|---|---|
| H_20260702_001 | TRIPTYCH_QUEUE_LEAN | **DEAD** | −0.003 | −0.24 | Only post-June trial. Triptych decile-conditional review-queue lean has zero standalone predictive power → context tier only |

---

## 3. Robustness assessment: which families are real across specifications

**Robust (multiple independent specs, PIT-confirmed, positive both sample halves):**
1. **Graph spillover** — 12 WEAK verdicts across trade/bank/two-hop/Katz/hub/bloc × current & PIT weights × 21d/63d windows. Every propagation-flavored variant works (t 2.5–5.7); both portfolio-channel variants fail. IC band tight (0.014–0.041). Caveat: these ~10 variants are highly correlated expressions of ONE idea (neighbors repriced first → endpoint catches up), not ten discoveries. Strongest single expression: PIT bank-claims gap 21d on 17 stable-BIS countries (IC 0.034, t 4.5, BE 13.1).
2. **Fundamental twins (similarity)** — 2/2 WEAK, full universe, longest sample, best 21d-hold economics (BE 18.3), least deflation damage. Same convergence mechanism as graph family but different graph construction — partial independence.
3. **Lead-lag** — enormous ICs (0.057–0.060, t 8.5–11.3), 92–96% positive years, robust across 34→17→16 country respecifications. But: local-index tradability trap unresolved, and 1d version has untradable turnover.
4. **Daily ridge combiner** — the aggregation of the above; strongest stats in ledger (IC 0.057, t 10.7, BE 14.2). In-sample component-selection caveat applies.

**One-off / fragile WEAKs (real t-stat, thin or unstable):**
- CPI consensus revision momentum (WEAK, t 2.31, only 159 monthly obs, 2013+).
- Flipped inflation surprise (WEAK, t 2.99, monthly; direction chosen after seeing the data — trial 2 of the idea, correctly charged).
- Contrarian ETF flow (WEAK label but BE <4 bps and unstable sign — treat as dead for stand-alone trading; kept alive as a combiner component).

**Dead beyond appeal (do not resurrect as return signals):** valuation percentiles (5 trials), FX carry/vol/RR/term surfaces as registered (7+ trials), GDP consensus revisions (2), ETF short interest, portfolio-holder stress, neighbor drawdown count, monthly ridge combiner (3), Triptych queue lean, **monthly 12-1 momentum** (the classic factor is flat here — noteworthy for any "momentum overlay" temptation).

---

## 4. Multiple-testing ledger (trials burned per family)

| Family | Trials registered | WEAK | DEAD | Unresolved | Comment |
|---|---|---|---|---|---|
| bbg_skill_2026_06 | 16 | 1 | 9 | 1 (CDS slope) | includes 1 post-hoc direction flip |
| graph_trade_gap | 15 | 12 | 2 | 0 | ~10 correlated variants of 1 mechanism |
| leadlag_2026_06 | 6 | 3 | 0 | 0 | incl. 1 duplicate re-registration (_055 = _049) |
| ml_combiner_2026_06 | 5 | 1 | 1 | 0 | daily WEAK, monthly DEAD |
| valuation_2026_06 | 5 | 0 | 4 | 0 | |
| consensus_ecfc_2026_06 | 4 | 1 | 1 | 0 | |
| etf_flows_2026_06 | 3 | 1* | 2 | 0 | *flip; BE <4 bps |
| momentum_sanity | 2 | 0 | 1 | 0 | + 1 leak-retired |
| fund_similarity_2026_06 | 2 | 2 | 0 | 0 | |
| triptych_prior_2026_07 | 1 | 0 | 1 | 0 | |
| **Total** | **59** | **21** | **21** | **1** | 89 verdict events (re-measures included) |

Discipline observed in the ledger: direction flips are re-registered as new trials and charged to the family; coverage-gate failures are re-registered rather than silently re-run; a leaked variable was caught, retired, and blacklisted with the trial still counted. Deflated Sharpe is computed against the burned-trial count, which is why nothing exceeds WEAK. Effective independent mechanisms discovered: **~4** (network convergence, twins convergence, lead-lag sequencing, reflation/inflation-revision) out of 59 trials.

---

## 5. Close-to-promotion, loose ends, and untested flips

1. **SIM_NBR_RET_GAP_63D @ 21d hold** — closest to net-viable slow signal: BE 18.3 bps, net10 Sharpe +0.166, DS −0.023 (best in ledger). If any single signal gets promoted first, it is this or the combiner.
2. **SOV_2S10S_Z252 (H_20260612_013)** — verdicted DEAD by the 5d-primary-horizon rule, but its 21d hold grid shows BE 15.8 bps / net10 +0.08: a real slow steepener tilt the verdict machinery under-credits. 20 countries, 2008+, positive both halves at 5d/21d.
3. **FX_BF25_Z252 flip never tested** — registered lower-is-better, DEAD; but raw IC is **positive** and strong at long horizon (21d IC 0.040 t 3.4; 63d IC 0.069 t 3.9 on 26 countries; 0.078 t 4.5 on the 34-country coverage-gated run). A higher-is-better (buy countries with expensive FX tail wings) 21–63d spec is an obvious unburned registration. Same (weaker) story for **FX_IMPVOL_Z252** (63d IC +0.055, t 2.57) and FX_CARRY_Z252 (63d IC +0.037, t 1.76).
4. **SOV_CDS_SLOPE_Z252 (H_20260612_006)** — the only registered-never-resolved trial (coverage-gated, IC ≈ 0, low priority).
5. **CONS_CPI_REV3M_12M** — WEAK on only 159 monthly observations; one more sample-extension re-test would either promote or kill it.
6. **VAL_CAPE anti-value drift** — 6m IC +0.054 (t 1.95) in the *expensive-wins* direction; never registered as a flip. Given 5 burned valuation trials, family cost of another flip is high.

---

## 6. Thesis ledger — live state (as of 2026-07-02)

Only 3 theses ever opened (all paper, all A2 graph-propagation, all opened 2026-06-10 off the June 3–7 selloff):

| Thesis | Entity | Dir | Horizon | P(entry) | Invalidation | Status | Latest mark (2026-07-01, day 21) |
|---|---|---|---|---|---|---|---|
| T_20260610_001 | Indonesia | long | 42d | 0.58 | −7% | **OPEN** | **−5.71%** — within 1.3pp of the −7% invalidation stop |
| T_20260610_002 | Hong Kong | long | 42d | 0.55 | −7% | **OPEN** | −2.22% |
| T_20260610_003 | Taiwan | short | 21d | 0.52 | −5% | CLOSED (killed day 1) | 0.0% — entry z was a v1.0 calendar-misalignment artifact (−2.28 → −1.11 corrected) |

Entry conditions on the open pair: trade-weighted-partner 21d return gap z > +1.5 with own 21d return depressed; invalidation = country-specific stress (D4 cross-asset flag, FX stress) or −7% cum return. Day-1 review under v1.1 measurement *strengthened* Indonesia (gap z +2.33) and confirmed Hong Kong (+1.90). Marks have gone the wrong way since; Indonesia is nearly stopped out. No reviews recorded after 2026-06-10; marks are stamped daily (some duplicate stamps per day; mark dates occasionally lag 1 day). **Calibration takeaway: 3 theses, 1 killed for measurement error at day 1, 2 losing paper longs — the thesis layer has essentially no track record yet; nothing here validates or invalidates the underlying WEAK signal family.**

---

## 7. Cost-economics summary for the tradable WEAK set (harness v2.1, LS breakevens)

| Signal | BE 1d | BE 5d | BE 21d | Net LS Sharpe @10bps (best hold) | Gross LS Sharpe (1d) |
|---|---|---|---|---|---|
| COMBINER_RIDGE_DAILY_V1 | **14.2** | 13.7 | 11.7 | 0.99 (1d) | 3.32 |
| SIM_NBR_RET_GAP_63D | 14.1 | 16.3 | **18.3** | 0.42 (1d) / 0.17 (21d) | 1.47 |
| GRAPH_BANK_NBR_RET_GAP_63D | 13.7 | 12.3 | 4.8 | 0.38 (1d) | 1.43 |
| GRAPHP_BANK_NBR_RET_GAP_21D (17c) | 13.1 | 11.6 | 9.8 | 0.45 (1d) | 1.93 |
| SIM_NBR_RET_GAP_21D | 11.3 | 13.3 | 14.1 | 0.21 (5d) | 1.71 |
| GRAPH_BANK_NBR_RET_GAP_21D | 11.9 | 12.2 | 12.8 | 0.28 (1d) | 1.80 |
| LL_LEADER_GAP_5D (16c) | 10.2 | 10.4 | 7.2 | 0.06 (1d) | 2.44 |
| GRAPH/GRAPHP trade/Katz/hub/twohop 21d | 8.0–10.8 | 8.7–10.3 | 8.8–10.1 | ≈0 ± 0.1 | 1.2–1.5 |
| SOV_2S10S_Z252 (DEAD verdict) | 1.0 | 6.4 | 15.8 | 0.08 (21d) | 0.12 |
| ETF_FLOW contrarian | 3.9 | 3.2 | 2.3 | negative | 0.44 |
| LL_LEADER_RET_1D | 3.1 | 4.6 | 3.9 | negative | 1.62 |

Confirms the digest's cost law: **nothing survives 25 bps one-way; ~4 signals clear 10 bps (combiner, sim-63, bank-gap variants); ~12 clear 5 bps.** Fast signals must be held 1d to win net; only sim-63 and the 2s10s curve improve with 21d holds. All figures are LONG-SHORT; a long-only tilt captures roughly half.

---

## 8. What a strategy designer should take from this ledger

- The house edge is **one mechanism family measured four ways**: cross-country return diffusion (trade/bank networks, fundamental twins, lead-lag), aggregated by a daily ridge combiner. Everything else tested is dead, thin, or context-tier.
- The combiner's headline (net 0.99 @10bps) is the ceiling of an in-sample component selection; the honest floor is the individual PIT-verified components (bank gap, twins) at BE 13–18 bps.
- Both surviving *monthly* signals (CPI revision momentum, flipped inflation surprise) point the same reflationary direction and are near-duplicates in spirit — treat as one slow overlay, not two.
- Momentum, valuation, flows, positioning, FX-derivative signals: all formally burned. The ledger's multiple-testing accounting is honest — respect it and do not silently re-run dead specs.
- Unburned cheap tests if more evidence is wanted: FX_BF25_Z252 flipped at 63d; SOV_2S10S at 21d hold as a formal slow-signal registration; CONS_CPI extension.
