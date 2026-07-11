# Running Fix List — items needing Arjun's decision/action

Agent-maintained running list of problems found during build sessions that are
**outside agent scope** (rewrite warehouse history, delete files, or live in
upstream systems the agent shouldn't touch without explicit permission).
Newest items at the top. When you fix one, delete the entry or mark it done.

---

## Open

### 5. CPI-revision consensus dates are calendar month-end, not true availability date — needs decision
- **Symptom (GPT-5.6 review 2026-07-10):** `cons_cpi_rev3m_12m` / the `cpi_rev`
  family carries month-end dates (e.g. `2026-07-31` today), which are future-dated
  vs the real observation and can contaminate any naive "latest as-of today" join.
- **Root cause:** `scripts/loop/load_consensus.py:72` uses `s.resample("ME").last()`,
  so the `date` becomes the calendar month-end. The value itself is real (last
  consensus observed in the month), so this is a **PIT-label** issue, not a
  forward-data leak.
- **Why not a clean loop-side fix:** the month-end date is a **load-bearing merge
  key** — `derive_signals` (`load_consensus.py:96-98`) merges the current- and
  next-target-year forecasts `on=["date", ...]` to build the rollover-free 12m
  blend. The two target-year series can have different real last-obs dates within a
  month, so relabeling `date` to the true observation date would break that merge.
- **Proposed fix (needs approval):** keep an internal month-end merge key, but stamp
  the *output* `date` (what lands in `consensus_signals` / `family_ranks_daily`) with
  `min(month_end, last_actual_obs_date)` so downstream PIT joins never see a future
  date. Add a test that no output row is dated after its last underlying observation.
- **Mitigating fact:** the cockpit already treats `cpi_rev` as monthly-lagging and
  excludes it from the daily freshness clock (`build_cockpit_data.py`), so the
  practical contamination surface is small — but the label is still wrong.

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
