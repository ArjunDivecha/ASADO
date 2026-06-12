# Running Fix List — items needing Arjun's decision/action

Agent-maintained running list of problems found during build sessions that are
**outside agent scope** (rewrite warehouse history, delete files, or live in
upstream systems the agent shouldn't touch without explicit permission).
Newest items at the top. When you fix one, delete the entry or mark it done.

---

## Open

*(none — all items resolved)*

---

## Done

### 2. T2 "10Yr Bond" sheet: USD override + dead Taiwan ticker — FIXED 2026-06-11
- Root cause: `collect_t2_bloomberg.py` pulled every sheet with `currency=USD`,
  which FX-divides yield series for some currencies (Brazil 14.46→2.81,
  Mexico 9.01→0.52, Vietnam 4.35→0.0002). Taiwan's `GTTWD10YR Corp` was dead.
- Fix: exempted the "10Yr Bond" sheet from the global USD override (pulls in local
  terms). Swapped Taiwan to `TPGBTW10 Index` in both manifests. Fixed `all_idx`
  builder to use the local-series key. Also discovered the pipeline was missing
  the `build_t2_master_daily.py` conversion step (ticker→country headers).
- Daily verification (vs `sovereign_daily`): Brazil 14.46, Mexico 9.01,
  Taiwan 1.69, Vietnam 4.35 ✓. Monthly: 10Yr Bond_CS now z-scored from correct
  levels across all countries (Vietnam NaN is edge case from zero→4.35 transition;
  self-corrects on next full monthly run).
- Files: `scripts/collect_t2_bloomberg.py` (v1.0→v1.1),
  `scripts/config/t2_bbg_manifest.json`, `scripts/config/t2_bbg_manifest_daily.json`.

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
