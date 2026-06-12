# Running Fix List — items needing Arjun's decision/action

Agent-maintained running list of problems found during build sessions that are
**outside agent scope** (rewrite warehouse history, delete files, or live in
upstream systems the agent shouldn't touch without explicit permission).
Newest items at the top. When you fix one, delete the entry or mark it done.

---

## Open

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

---

## Done

### 1. Monthly Bloomberg ticker map — FIXED 2026-06-11 (approved by Arjun)
- Full Terminal re-audit found the rot went deeper than first reported: Saudi
  Arabia's **5Y and 30Y** (`GSAB5YR`/`GSAB30YR`) were ALSO South African series,
  and Malaysia/Thailand/Turkey 2Y+5Y tenors were dead too.
- Fixed in `scripts/collect_bloomberg.py` (map + `YLD_YTM_MID` field rule for
  `* Govt` generics), force re-pull done, warehouse rebuilt (`--db-only`), all
  values verified against the daily collector. Bonds now 104/105 series, CDS 20/20.
- Bonus: sovereign credit ratings finally work (panel historically had ZERO
  rating rows — rating fields don't exist on generic yield indices). Now pulled
  from `GT[CCY]10Y Govt` bonds as numeric 21-point scores: 94 rows, 32 countries.
- Backup of pre-fix data: `Data/backups/2026_06_11_150809_pre_ticker_fix/`.

### 3. `validate_returns_first.py` alias check — FIXED 2026-06-11
- Root cause: the check counted NULL==NULL as a mismatch. The 34 "failing" rows
  were the open month's forward 1MRet, legitimately NULL on BOTH sides — the
  alias was never actually broken (daily was already bit-exact 136,136/136,136).
- Fixed the check's NULL semantics (v1.1); validator now 18/18 green.

### 4. Quarantined `sovereign_daily.parquet.bad_saudi` — DELETED 2026-06-11
- Deleted with explicit permission.
