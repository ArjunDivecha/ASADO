# Morning Report — 2026-06-11 (overnight build session)

**Instruction:** "build build build and test and then give me a report" — full autonomy on
anything already in `PRD_Alpha_Hunting_Loop.md`.

**Bottom line:** PRD Phase 3 data priorities **7, 8, 9, and the Taiwan half of 10** were
built, backfilled, tested, and wired into the nightly job overnight. Two more detectors
went live: **D3 (revision momentum)** for the first time, and **D4 upgraded to v2** with a
daily CDS leg. The nightly job is now **14 steps, all green, ~55 seconds**. Three real
data bugs were found along the way (one in the monthly Bloomberg collector — needs your
call, see "Found bugs" below).

---

## 1. P8 — Daily sovereign CDS + 10Y (Bloomberg) ✅

The warehouse's CDS surface was monthly-only. Now there is a daily panel back to 2005:

- **20 sovereign 5Y CDS series** (`SOV_CDS_5Y_BP`) — every T2 country with a liquid
  sovereign CDS contract. EMs from 2005; France/Italy/Poland/Spain/South Africa use the
  ISDA-2014 ("D14") contracts, which exist from late 2014.
- **32 of 34 10Y yields** (`SOV_10Y_YIELD_PCT`) pulled directly from the generic
  government-bond tickers (only Hong Kong and Vietnam have no usable 10Y).
- 262,707 rows. New nightly steps pull the last 15 days and rebuild the loop-DB table.

Sanity validation (passed):
- COVID March-2020 peaks: Brazil 380bp, Mexico 312bp, Turkey 670bp — historically correct.
- Current levels orderly: Turkey 242bp > South Africa 130 ≈ Brazil 130 > … > Spain 16.5.

**Ticker corrections made vs the monthly collector's map** (every one re-verified live):
Chile 10Y `CLGB10Y Index` (old `CHILE10` is dead), Taiwan 10Y `TPGBTW10 Index` (fixes the
series that died upstream in 2020), Malaysia/Philippines/Turkey/Saudi 10Y via generic
Govt bonds using `YLD_YTM_MID` (their old Index tickers are invalid), 5 CDS switched to
D14 contract names.

Files:
- Collector: `scripts/loop/collect_sovereign_daily_bbg.py` (OpusBloomberg env)
- Loader: `scripts/loop/load_sovereign_daily.py` (venv)
- Data: [Data/work/loop/sovereign_daily.parquet](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/work/loop/sovereign_daily.parquet)

## 2. D4 upgraded to v2 — cross-asset incoherence now has a CDS leg ✅

D4 now checks **equity vs FX vs 10Y vs 5Y CDS** over the same 5 trading days:
- New conflicts: `cds_widening_vs_equity_strong`, `cds_tightening_vs_equity_weak`.
- The 10Y leg prefers the fresh direct pull (so Taiwan's yield leg is alive again);
  Philippines/Vietnam staleness is reported in a DEGRADED row, never silently skipped.
- Severity now comes from the **strongest** conflicting surface; every D4 row carries
  `cds_chg_5d_z` and `cds_level_bp`.

## 3. P7 — Valuation block (E5 "knowable vs priced" pricing layer) ✅

New month-end table `valuation_monthly` (128,472 rows, 2000 → present, 34 countries):

| Variable | What it is |
|---|---|
| `VAL_CAPE`, `VAL_PB`, `VAL_DY_PCT`, `VAL_EY_PCT`, `VAL_TRAIL_PE` | Levels from the T2 daily feed |
| `VAL_ERP_PCT` | Equity risk premium = earnings yield − (10Y − CPI YoY), 32 countries |
| `VAL_*_PCTILE_10Y` | Each metric vs its own trailing decade, 0 = cheapest, **100 = richest** (yields inverted so rich is always 100) |

No new Bloomberg pull was needed — the insight is that all valuation inputs already land
daily via the T2 manifest; the ERP's 10Y leg uses the new P8 pull. Verified by hand:
U.S. ERP = 3.68 − (4.55 − 4.20) = **3.32%** (77th percentile rich); Brazil ERP is
**−0.81%** (real yields above the earnings yield); Korea/Japan ERP sit at their 95th
percentile rich. Bad upstream prints (Brazil's Shiller PE prints exact 0.0 in stretches)
are treated as missing, never as data.

Script: `scripts/loop/build_valuation_block.py`

## 4. P9 — Surprise surface: WEO vintage backfill, and D3 IS LIVE ✅

The forward-only vintage snapshots could never recover the past. Now recovered from
public archives:

- **36 WEO vintages, 2008-04 → 2026-04** (semi-annual). Archives via DBnomics (the IMF's
  own bulk files are Akamai-blocked for scripts; DBnomics is the IMF-sanctioned mirror,
  free, keyless). The two newest vintages come straight from the IMF SDMX 3.0 API.
- `weo_vintages` (16,863 rows): GDP growth + CPI inflation forecasts per country per
  target year per vintage. `weo_revisions` (15,163 rows): every vintage-over-vintage
  forecast change — the surprise surface.
- Validation against history: the April-2020 vintage shows the COVID demolition exactly
  as published (U.S. 2020 GDP revised **−8.0pp**, Germany −8.2pp, Brazil −7.3pp).

**Detector D3 (A3 revision-momentum quadrants) went live** off this surface — revisions
z-scored against each country's own 18-year revision history, crossed with 6m price
momentum; only the *unpriced* quadrants fire; each vintage counts as live news for 120
days. **First live signal: Vietnam** — 2026-04 GDP forecast revised up +1.22pp (z=+1.83
vs its own history) while 6m momentum is flat (−0.29z) → long flag. Note it lines up
with the Vietnam MSCI EM-watchlist decision (June 23) already in the forward calendar.

Script: `scripts/loop/collect_weo_vintages.py`

## 5. P10 (partial) — Taiwan trade shares via WITS: D1 now covers 34/34 ✅

The World Bank has no Taiwan trade data, so D1 (terms-of-trade impulse) structurally
excluded Taiwan. Fixed via the WITS tradestats API (reporter `OAS` = "Other Asia, nes" =
Taiwan in Comtrade convention, keyless): same four commodity groups, shares computed
from values/Total. `tot_trade_shares` now covers **34/34 countries** and D1 ran clean
with zero DEGRADED notices. Full SITC 2-digit granularity remains the future v1 upgrade.

## 6. The nightly job — 14 steps, all green

```
collect_news_bridge → mark_theses → build_country_returns → build_tot_shares
→ build_graph_features → build_forward_calendar → collect_foreign_flows_bbg
→ collect_foreign_flows → collect_sovereign_daily_bbg → load_sovereign_daily
→ build_valuation_block → collect_weo_vintages → build_dislocations → fold_ledgers
```

Run three times end-to-end tonight, all steps OK each time, ~55s total. Detector status:
**live D1 D2 D3 D4 D5 D7 D8 D9** — only D6 remains blocked (predmkt history accumulating
since 2026-06-10, by design).

Latest brief: [Data/dislocations/brief_2026_06_09.md](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/dislocations/brief_2026_06_09.md)

## 7. Found bugs (data integrity — please read)

1. **Monthly Bloomberg collector ticker bug (NOT yet fixed — your call):** in
   `scripts/collect_bloomberg.py` COUNTRY_TICKERS, Saudi Arabia's 10Y ticker is
   `GSAB10YR Index`, but that series is **South Africa's** generic 10Y. Monthly
   `BBG_Bond_10Y` for Saudi Arabia in the warehouse is therefore South African yields.
   Several other monthly 10Y/CDS tickers there are dead (Chile, Taiwan, Malaysia,
   Philippines, Thailand, Turkey 10Y; FRTR/ITALY/POLAND/SPAIN/SOAFR EUR CDS) — the
   collector's per-source try/except hid this. The corrected map exists in the new
   daily collector; porting it to the monthly collector is a small change but rewrites
   warehouse history, so I did not touch it without permission.
2. **t2_levels_daily "10Yr Bond" Brazil is wrong** (prints ~2.85 vs the real ~14.8 local
   10Y). D4 and the valuation block now read the direct pull instead. The T2 upstream
   series is worth a look.
3. **TPGBTW10 (Taiwan 10Y)** published bond *prices* instead of yields for 47 days in
   2011-2012 — the collector drops out-of-range prints loudly (and aborts if >5% of a
   series is bad).

## 8. Files touched/created tonight

| File | What |
|---|---|
| `scripts/loop/collect_sovereign_daily_bbg.py` | NEW — daily CDS/10Y Bloomberg pull |
| `scripts/loop/load_sovereign_daily.py` | NEW — loop-DB loader |
| `scripts/loop/build_valuation_block.py` | NEW — P7 valuation surface |
| `scripts/loop/collect_weo_vintages.py` | NEW — P9 WEO vintages + revisions |
| `scripts/loop/build_tot_shares.py` | Taiwan via WITS (34/34) |
| `scripts/loop/build_dislocations.py` | D3 live, D4 v2, D1 notes |
| `scripts/loop/loop_daily_job.py` | 4 new steps (14 total) |
| `AGENTS.md` | New data layers documented |
| `Data/work/loop/sovereign_daily.parquet` | 262,707 rows, 2005+ |
| `Data/work/loop/valuation_monthly.parquet` | 128,472 rows, 2000+ |
| `Data/work/loop/weo_vintages.parquet` | 36 vintages, 2008+ |

(Also: `Data/work/loop/sovereign_daily.parquet.bad_saudi` is the quarantined first pull
that contained the Saudi/South-Africa mixup — kept per the no-deletion rule, safe to
delete.)

## 9. What remains from the PRD data list

- **P10 full version:** Comtrade SITC 2-digit shares (needs a Comtrade API key, or WITS
  SITC expansion) → D1 v1 corrected basket.
- **P6 remainder:** B3 (Brazil) foreign flows — no Bloomberg daily series found yet.
- **D6:** stays dark until ~60 days of predmkt snapshots (≈ early August).
- **P9 stretch:** ECFC consensus forward snapshots (monthly accumulation) to densify the
  surprise surface between WEO vintages.

---

# Session 2 (same night, after midnight) — four more PRD items

Per "keep a running list of fixes I need to make on my side - but lets go on to the next
things that need to be built": the fix list now lives at
[docs/USER_FIX_LIST.md](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/docs/USER_FIX_LIST.md)
(4 open items), and four more things got built and tested.

## 10. P11 — ETF share-count flows (positioning layer) ✅

Daily creations/redemptions for all **34 US-listed country ETFs, 2010 → today**
(390,829 raw rows; 521,391 derived signal rows). Flow = ΔsharesOut × NAV, with a 20%
split guard (62 corporate-action days nulled instead of becoming fake billion-dollar
flows). Signals per country: `ETF_FLOW_USD_MN`, 21d sum, 21d %-of-AUM, 21d z vs own
trailing year. Verified: shares × NAV = AUM to the dollar; Brazil COVID-crash
redemptions reproduce.

**This is also the Brazil flow answer (P6 remainder):** B3 has no live Bloomberg
foreign-flow series (the monthly one died 2021-08, the futures positioning family went
stale 2025-10) — but EWZ creations ARE US-investor Brazil positioning, daily. The brief
now has an "ETF positioning" section showing |z| ≥ 2 extremes. Tonight's read:
**Hong Kong/Switzerland/Netherlands seeing +3 to +4σ inflows; Brazil −2.4σ outflows,
cross-confirming the Korea/Brazil exchange-flow picture.**

- `scripts/loop/collect_etf_flows_bbg.py` + `scripts/loop/load_etf_flows.py`
- [Data/work/loop/etf_flows.parquet](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/work/loop/etf_flows.parquet)

## 11. P9 stretch — ECFC consensus revision surface ✅ (better than planned)

Planned: accumulate forward snapshots monthly and wait years for history. Found instead:
Bloomberg's **year-specific** consensus tickers (`ECGDUS 26 Index`, `ECPIBR 27 Index`…)
already store the full daily revision path per target year. One backfill =
**1,216 series, 921,423 rows, daily consensus GDP + CPI revisions back to 2007** —
20 target years × 31 economies, no waiting required.

Verified against ground truth: US 2020 GDP consensus path reads +1.8 (Feb) → −4.0 (Apr)
→ −5.7 (May trough) → −3.5 (Dec). Loop tables: `consensus_daily` (raw) and
`consensus_revisions` (month-end levels + 1m/3m revision deltas). The surprise surface
is now **daily-dense between WEO vintages**, which sets up a D3 v2 later.

Gotcha documented in AGENTS.md: this ticker family uses ISO-2 codes — `ECGDCH` here is
**Switzerland**, while the monthly collector's rolling `ECGDCH` is **China**. Never mix.

- `scripts/loop/collect_consensus_bbg.py` + `scripts/loop/load_consensus.py`
- [Data/work/loop/consensus_daily.parquet](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/work/loop/consensus_daily.parquet)

## 12. P4 v1 — GDELT article evidence layer ✅

When a dislocation fires, the headlines behind it are now **frozen permanently**:

- `Data/loop/evidence_packs/{date}/{country}.json` — trigger rows (which detectors
  fired, severities) + that day's deduped headlines. Append-only, never pruned. The
  article-level analog of vintage snapshotting.
- Loop table `gdelt_articles_recent` — everything pulled, 14-day rolling retention.
- Throttle-safe by design: only countries whose dislocations FIRED (status
  new/intensifying), D8 stewardship excluded, max 12 pulls/night ranked by |severity|,
  and on the first rate-limit it aborts the rest loudly (GDELT's cooldown resets on
  every probe, so retry loops are self-defeating).

First packs written for Hong Kong, Indonesia, Singapore (the D5 attention spikes).

- `scripts/loop/build_evidence_packs.py`
- [Data/loop/evidence_packs/](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/loop/evidence_packs/)

## 13. Phase 3 acceptance — D1 validated against 3 known episodes ✅

The PRD's acceptance test for Phase 3, now a repeatable script
(`scripts/loop/validate_d1_episodes.py`):

| Episode | Expected | Result |
|---|---|---|
| Saudi/oil 2020 (COVID + price war) | deeply negative | **z = −3.33** at Apr 2020 ✅ |
| Chile/copper 2021 (reflation record) | strongly positive | **z = +2.12** at May 2021 ✅ |
| Chile/copper 2024 (squeeze to ~$11k/t) | positive | **z = +1.46** at May 2024 ✅ |

OVERALL: PASS — the production basket (same shares, same Pink Sheet aggregates, same
36m z) screams in the right direction in all three episodes.

## 14. Housekeeping

- Last "8 factors" artifact removed: one stale `OPT8_HERDING` dislocation row renamed
  to `FACTOR_HERDING`.
- Nightly job is now **19 steps** (added: collect/load ETF flows, collect/load
  consensus, evidence packs after the detectors).

---

# Session 3 (02:00–02:20) — the "what remains" list, mostly cleared

## 16. P11 complete — short interest + CFTC COT ✅

**ETF short interest (Bloomberg, semi-monthly):** `SHORT_INT` / `SHORT_INT_RATIO`
added to the existing ETF-flows collector — zero new nightly steps. Derived
signals: `ETF_SHORT_PCT_SHOUT` (shares short / shares out) and `ETF_SHORT_PCT_Z`
(z vs own ~2y). 32/34 countries (INDA publishes none; EDEN no ratio).

The first print is striking and goes straight into the brief: **European ETFs
show record short interest exactly where creations spiked** — Netherlands (EWN)
17.5% of shares short (z=+5.9), Switzerland +5.4, U.K. +4.5, Italy +3.8 — the
classic hedged/basis-trade footprint, worth a Layer 2 look.

**CFTC COT (keyless Socrata API):** weekly speculator net positioning for 12
commodity futures mapped to the D1 channel (WTI, nat gas, gold, silver, copper,
platinum, corn, wheat, soybeans, sugar, coffee, cotton), 2006→current, with
net-%-of-OI and 52w z. Currently stretched: gold +1.9z, copper +1.9z, cotton +1.9z,
coffee −1.9z. New brief section "Commodity positioning (CFTC COT, weekly)".

- `scripts/loop/collect_etf_flows_bbg.py` / `load_etf_flows.py` (extended)
- `scripts/loop/collect_cot.py` (new; pull + load + `--check` in one)

## 17. P10 done better than spec — D1 v1 via Comtrade HS chapters ✅

The PRD wanted SITC 2-digit "needs an API key". Found the **keyless Comtrade
public preview endpoint** works for HS 2-digit chapters; one batched call per
reporter (28 codes × both flows). All 34 countries now have FRESH 2023–2025
shares — including Taiwan (reporter 490) — across **6 categories** instead of 4:
the old WDI sections completely missed **precious metals** (South Africa net
+18.1% of trade!, Australia +6.6%) and **fertilizer**.

Debug war story: big traders (Germany/France/U.K.) kept failing — the preview
endpoint truncates at 500 rows and their mode-of-transport breakdowns pushed the
TOTAL rows off the end. Server-side `motCode=0` filter fixed it. A 7-day
freshness gate keeps the nightly job from hammering the rate-limited endpoint.

D1 re-validated against all 3 episodes with the new 6-category basket:
Saudi 2020 **z=−3.32** ✅, Chile 2021 **z=+2.02** ✅, Chile 2024 **z=+1.52** ✅.

- `scripts/loop/build_tot_shares.py` (v2.0 rewrite)
- D1_INDEX_MAP in `build_dislocations.py` now maps 6 Pink Sheet indices

## 18. Phase 4 scaffold — calibration report machinery ✅

`scripts/loop/calibration_report.py` regenerates the current month's report
nightly: Brier score + hit rate overall and by archetype / horizon / direction /
regime-at-open / author (overrides ARE calibration data), plus a stated-p vs
realized calibration curve. Until ≥10 theses close it stamps itself **PARTIAL**
and reports only what exists. First report is live with 2 open theses.

- [Data/loop/calibration/calibration_2026_06.md](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/loop/calibration/calibration_2026_06.md)
- [Data/loop/calibration/calibration_2026_06.xlsx](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/loop/calibration/calibration_2026_06.xlsx)

## 19. Nightly job: 21 steps, full E2E green ✅

Added `collect_cot` (step 17) and `calibration_report` (step 21). Full run at
02:12: **all 21 steps OK in 2.5 minutes** (Comtrade freshness gate skipped the
weekly shares re-pull as designed).

## 20. Updated "what remains"

- **D6:** dark until ~60 days of predmkt snapshots (≈ early August) — time, not code.
- **FINRA direct short interest:** Bloomberg `SHORT_INT` already carries the FINRA
  print for the US-listed ETFs, so this is effectively covered; a direct FINRA file
  pull would only add non-ETF coverage.
- **Phase 4 acceptance:** needs ≥10 closed theses + 4 weeks of daily passes — the
  machinery is built, the clock is running.
- User-side items: see [docs/USER_FIX_LIST.md](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/docs/USER_FIX_LIST.md)

Report: [docs/MORNING_REPORT_2026_06_11.md](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/docs/MORNING_REPORT_2026_06_11.md)
