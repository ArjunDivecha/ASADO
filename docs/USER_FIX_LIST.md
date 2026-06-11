# Running Fix List — items needing Arjun's decision/action

Agent-maintained running list of problems found during build sessions that are
**outside agent scope** (rewrite warehouse history, delete files, or live in
upstream systems the agent shouldn't touch without explicit permission).
Newest items at the top. When you fix one, delete the entry or mark it done.

---

## Open

### 1. Monthly Bloomberg collector: Saudi Arabia 10Y is actually South Africa's series
- **Found:** 2026-06-11 (overnight build, P8)
- **Where:** `scripts/collect_bloomberg.py` → `COUNTRY_TICKERS["Saudi Arabia"]["bond_10y"] = "GSAB10YR Index"`
- **Problem:** `GSAB10YR Index` is **South Africa** Govt Bonds 10 Year Generic Bid Yield.
  Every monthly `BBG_Bond_10Y` row for Saudi Arabia in `bloomberg_factors` is South
  African data. Correct Saudi ticker: `GTSAR10Y Govt` with field `YLD_YTM_MID`.
- **Also dead in the same map** (collector's per-source try/except hid them — these
  countries silently have no monthly data): Chile 10Y `CHILE10` (→ `CLGB10Y Index`),
  Taiwan `TAIBON10` (→ `TPGBTW10 Index`), Malaysia `MALAY10Y` (→ `GTMYR10Y Govt`/YLD),
  Philippines `PHLGB10Y` (→ `GTPHP10Y Govt`/YLD), Thailand `THAI10Y` (→ `GVTL10YR Index`),
  Turkey `TURKBON10` (→ `GTTRY10Y Govt`/YLD), South Africa `SAGB10Y` (→ `GSAB10YR Index`),
  and 5 CDS: FRTR/ITALY/POLAND/SPAIN EUR + SOAFR (→ `FRANCE/ITALY/POLAND/SPAIN CDS USD
  SR 5Y D14 Corp`, `REPSOU CDS USD SR 5Y D14 Corp`).
- **Why agent didn't fix:** porting the corrected map rewrites monthly warehouse history
  (`bloomberg_factors`) on the next monthly run. Corrected map already lives in
  `scripts/loop/collect_sovereign_daily_bbg.py` — copy from there when approved.
- **Action:** approve the ticker-map port + a `--force` monthly Bloomberg re-pull.

### 2. T2 daily feed: "10Yr Bond" for Brazil is wrong
- **Found:** 2026-06-11
- **Where:** `t2_levels_daily`, variable `10Yr Bond`, country Brazil (comes from the T2
  manifest pull, `scripts/config/t2_bbg_manifest_daily.json` → sheet "10Yr Bond").
- **Problem:** prints ~2.85 while Brazil's local 10Y is ~14.8 (the new direct pull
  `sovereign_daily` has the correct 14.81). Looks like the T2 sheet's Brazil column
  points at the wrong ticker. Downstream consumers of T2 "10Yr Bond" for Brazil
  (including the optimizer's bond factors, if used) see a wrong level.
- **Mitigation in place:** D4 and the valuation block read `sovereign_daily` instead.
- **Action:** check the Brazil column ticker in the T2 manifest / upstream T2 workbook.

### 3. `validate_returns_first.py` alias check fails (pre-existing, minor)
- **Found:** 2026-06-10
- **Problem:** a small number of GDELT-labeled return rows are not bit-exact duplicates
  of T2 returns (34/4,420 monthly; 17/136,136 daily). Cosmetic unless something joins
  on GDELT-labeled returns expecting exact equality.
- **Action:** decide whether to rebuild the GDELT returns alias or relax the check.

### 4. Quarantined file safe to delete (agent may not delete files)
- **Found:** 2026-06-11
- **File:** `Data/work/loop/sovereign_daily.parquet.bad_saudi` — first P8 pull,
  quarantined because Saudi rows contained South Africa yields (bug #1).
- **Action:** delete when convenient, or tell the agent to.

---

## Done

(nothing yet)
