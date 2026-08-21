# Running Fix List — items needing Arjun's decision/action

Agent-maintained running list of problems found during build sessions that are
**outside agent scope** (rewrite warehouse history, delete files, or live in
upstream systems the agent shouldn't touch without explicit permission).
Newest items at the top. When you fix one, delete the entry or mark it done.

---

## Open

### 6. T2_Optimizer.xlsx "Monthly_Net_Returns" sheet missing/renamed "Date" column — breaks daily panel build
- **STILL FAILING 2026-08-12 07:30 launchd run** — second consecutive weekday
  failure, identical `KeyError: 'Date'` at the same line. Not self-healing;
  needs Arjun's attention.
- **Symptom (2026-08-11 07:30 launchd run, `asado-daily`):** `build_daily_panels.py`
  Stage 1 fails with `KeyError: 'Date'` in `load_factor_returns_daily()`
  (`scripts/build_daily_panels.py:359`), which reads
  `Data/work/t2_daily/T2_Optimizer.xlsx`, sheet `Monthly_Net_Returns`, and expects a
  literal `Date` column.
- **Trigger:** `Data/work/t2_daily/T2_Optimizer.xlsx` was rewritten by the upstream
  T2 feed at 08:19 today (mtime), i.e. between the two most recent daily runs — its
  `Monthly_Net_Returns` sheet no longer exposes a column literally named `Date`
  (renamed, reordered, or replaced by an index/date-as-header layout). Not
  independently confirmed by reading the sheet in this session — see Verification
  note in the fixer report for 2026-08-11.
- **Why not a same-session fix:** this is a T2-feed schema change, which
  `CLAUDE.md`'s house rule reserves for Arjun's review ("do not fix
  monthly-collector or T2-feed bugs without approval — append to
  `docs/USER_FIX_LIST.md` instead"), and this fixer agent's sandbox does not permit
  running Python/openpyxl to positively confirm the new column layout before
  proposing a patch.
- **Proposed fix (needs approval + confirmation of new column name):** once the
  actual current header of `Monthly_Net_Returns` is confirmed (e.g. via
  `python -c "import pandas as pd; print(pd.read_excel(path, sheet_name='Monthly_Net_Returns', nrows=0).columns.tolist())"`),
  either (a) update `scripts/build_daily_panels.py:358-359` to read the new column
  name, or (b) if the upstream T2 export was corrupted, ask the feed owner to
  restore a `Date` column. Do not blind-guess the rename.

---

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

## 2026-07-13 — G1 flip autopsy (experiments/2026_07_flip_autopsy)
- PROPOSAL (needs approval, pipeline change): nightly family-IC tracker for network_spillover (and other families) writing one row/family/night to the loop DB + automatic R-A price-gate evaluation. Rationale: the 2024-26 family IC flip went unmeasured for ~15 months because the harness only runs on demand; the flip was only ever visible inside June-2026 harness JSONs. Machinery exists in experiments/2026_07_flip_autopsy/a2_drift_test.py.

## 2026-07-13 — Daily lag-0 convention for "zero-lag" sources — ✅ RESOLVED 2026-07-14 by harness v4 (contract HARNESS-V4-HONEST-LEDGER-001, merged 8a1aa6e; all 59 hypotheses re-verdicted)
- **Issue:** for daily signals from ZERO_LAG_SOURCES (t2/graph/gdelt/...), evaluate_signal opens the forward-return window at the signal's OWN close (lag 0). On 34 asynchronous local closes this embeds same-close execution + the timezone echo: measured family IC/LS levels are ~2x reality (lag-1 check: pre-2024 family IC +0.0123 NW-t 2.2 vs lag-0 +0.0234 NW-t 4.0; combiner book Sharpe 1.76 -> 0.97 at 5d hold).
- **Why urgent NOW:** harness v3 (196536f, 2026-07-13) keys verdicts to GROSS metrics; the retired 25bp cost gate was accidentally suppressing echo-inflated daily signals. Without a fix, new daily verdicts can promote untradeable echo.
- **Proposed fix (needs approval):** apply CONSERVATIVE_DAILY_LAG_DAYS=1 to ALL daily signals including zero-lag sources (or equivalent: verdict horizon opens at t+1 close). Then re-verdict the ~29 daily hypotheses via the sanctioned re-measurement path (existing ids, zero new registrations, as in the v2.1 re-cost).
- **Scope note:** monthly verdicts unaffected (existing embargoes; 1-day echo is second-order at 21d horizons). All DEAD verdicts stand a fortiori (they died under the favorable convention).
- Evidence: experiments/2026_07_flip_autopsy/results/a6_lag1_family_ic.json; experiments/2026_07_dispersion_throttle/results/RESULTS.md correction block.

---

## 2026-08-09 — `factor_returns_daily` is invalid as an active-return series (3 bugs in `scripts/t2_optimizer_daily.py`)

**Found by:** health check prompted by "does ASADO calculate daily factor returns?"
**Scope:** `factor_returns_daily`, source `t2_optimizer_daily` — 106 factors, 1,030,002 rows,
1999-12-31 → 2026-08-07. **Live T2 Fuzzy strategy is NOT affected** (verified: the monthly
`Step Four Create Monthly Top20 Returns FAST.py` is clean on all three counts).
**Not fixed** — T2-feed code, needs owner approval per CLAUDE.md.

### Bug 1 (severe) — benchmark not shifted with the portfolio leg

`scripts/t2_optimizer_daily.py:107,121,122`
```python
ret_next = returns.shift(-1)                    # portfolio leg -> T+1 returns
port     = (w * rn).sum(axis=1, min_count=1)    # earns T+1
net      = (port - benchmark)                   # <-- benchmark still at T
```
`net(T) = [weights(T)·returns(T+1)] − benchmark(T)` — the long leg earns tomorrow, the
benchmark is charged today. It is a spread between two different days, not an active return.

**Empirically confirmed** (factor `120DTR_CS`, n=8,385 excluding the fake zeros):
- `corr(net, benchmark same-day T)  = −0.634`
- `corr(net, benchmark next-day T+1) = +0.537`

A correctly aligned active return should be ~0 against both. The series is dominated by
market direction on two consecutive days.

### Bug 2 — `min_count=1` yields partial-universe portfolio returns

`t2_optimizer_daily.py:121`. If even ONE country has data the sum returns a value, so on rows
whose *next* row is a near-holiday (Saturday row → Sunday returns, when only Saudi/Israel/Gulf
trade) the "portfolio return" is built from 1–3 markets whose weights no longer sum to 1, then
netted against the FULL benchmark. This is why Saturday rows show mean |ret| 0.776 despite no
market trading Saturday. (Sunday Gulf trading is legitimate and easily excepted — the bug is
the partial aggregation, not the Gulf data.)

### Bug 3 — `.fillna(0.0)` converts missing data into fake zero returns

`t2_optimizer_daily.py:128`. Friday's next row is Saturday, when nothing is open anywhere:
`port` → NaN → `net` → NaN → **filled with 0.0**. Result: **78% of Friday rows are exact
zeros**, 14.2% of the whole series. These are not "the factor returned 0%" — they are "no data,
call it zero." Also violates the house rule against silent imputation (`AAA Backup/CLAUDE.md`:
missing values get explicit NULL plus a logged record).

### Downstream effects

- Daily volatility is understated (14.2% artificial zeros): 21.83% annualising all calendar
  rows vs 19.58% on non-zero rows.
- Does not reconcile with monthly `factor_returns`: correlation 0.83, mean abs monthly
  difference 1.31pp, −3.02%/yr vs −1.44%/yr, sign disagreements in 3 of the last 6 months.
- Any day-of-week analysis on this table is meaningless.

### Suggested fix (for approval)

1. Shift the benchmark identically (`benchmark.shift(-1)`), or better, compute everything on
   the RETURN date: `port(T) = weights(T−1)·returns(T)` netted against `benchmark(T)`.
2. Replace `min_count=1` with a coverage floor — require a minimum share of benchmark weight
   present, else NaN.
3. Delete `.fillna(0.0)`; leave NaN and drop non-trading rows.
4. Reindex to a trading-day calendar, with an explicit exception for Sunday-trading markets
   (Saudi/Israel/Gulf) rather than a blanket weekend rule.
5. Check `gdelt_optimizer_daily.py` (36 factors, 147,708 rows) for the same pattern.

### UPDATE 2026-08-09 — bugs 1–3 FIXED upstream; a 4th, deeper bug found and NOT fixed

Fixed in `A Complete/T2 Factor Timing Fuzzy Daily/Step Four Create Monthly Top20 Returns.py`
(backup: `Backups/Step Four Create Monthly Top20 Returns.py.bak-20260809_222131`), which is
the canonical source ASADO's `t2_optimizer_daily.py` was ported from:
- benchmark now netted on the RETURN date (portfolio leg shifted onto it)
- `MIN_UNIVERSE` (10) coverage floor replaces implicit partial-universe books
- `.fillna(0.0)` removed; non-trading days masked NaN via `trading_day_mask()`

**Validated on a 4-factor / 2022+ subset (no production file overwritten):**
`corr(net, benchmark_T+1)` fell from **+0.537 to ~0.007**; exact zeros **14.2% -> 0**.
Note: `Daily Alpha/daily_alpha_backtest.py` was ALREADY correct — it lags the weights and
keeps returns/benchmark on the return date. The legacy path now matches it.

**BUG 4 (upstream, NOT fixed, needs owner decision).** `Portfolio_Data.xlsx` sheet `Returns`
has a corrupted date axis:
- **Friday rows are all-zero in 131 of 131 weeks** since 2024.
- **Sunday rows carry real US equity returns** (mean |ret| 0.0057) — the US market does not
  trade Sunday.
- The sheet averages ~6 populated rows per week for a 5-session week.

So the row LABELS do not correspond to trading sessions. The fix above makes the netting
internally consistent (both legs on the same row, whatever that row is), so the active-return
SERIES is now valid — but its date stamps still inherit this upstream offset. Fixing it means
changing the date axis of everything downstream, so it is left for Arjun.
Origin to inspect: `Step Two Point Five Create Benchmark Rets.py`.

### RETRACTION 2026-08-09 — "BUG 4" WAS NOT A BUG. Disregard it.

The claim that `Portfolio_Data.xlsx` / `T2 Master.xlsx` sheet `1DRet` has a "corrupted date
axis" is **WRONG and withdrawn**. `1DRet` is a **FORWARD** return by design:

```
corr(1DRet, TRAILING return T/T-1) = -0.0516
corr(1DRet, FORWARD  return T+1/T) = +1.0000     mean|diff| = 1.7e-07
```

Under that convention every observation I flagged is CORRECT:
- Friday rows = the Fri->Sat holding period, which genuinely earns 0 (market shut)
- Sunday rows = Sun->Mon, i.e. Monday's session
- Saturday rows = Sat->Sun, i.e. the Gulf markets that trade Sunday (owner confirmed)
- ~6 populated rows/week = 5 major sessions + the Gulf Sunday session

This is also consistent with ASADO's own forward-return blacklist, which lists `1DRet` as an
optimizer TARGET. I should have joined those facts rather than diagnosing corruption.
No upstream fix is needed and `Step Two Point Five Create Benchmark Rets.py` is not at fault.

**Bugs 1-3 and their fix are UNAFFECTED and still stand.** Re-verified under the forward
convention:
- original: portfolio = w(T)·1DRet(T+1) = return over T+1->T+2; benchmark = 1DRet(T) = T->T+1.
  Genuinely misaligned by one day. The fix shifts the portfolio leg onto row T+1, where the
  benchmark is also T+1->T+2. Both legs now earn the same period, and the deliberate 2-day
  implementation lag documented in the original header is preserved.
- Validation stands: corr(net, benchmark_T+1) +0.537 -> +0.007; exact zeros 14.2% -> 0.

---

## 2026-08-21 — T2 spine `_clean_sheet` uses future data (DECISION REQUIRED, not fixed)

`scripts/build_t2_master.py:_winsorize` clips to **full-sample** median±5·MAD, and
`_check_local_outliers` judges each point against a **centred** ±20-month window and replaces
it with a mean including the 20 months after it. Both are look-ahead. The cleaned sheets feed
the monthly optimizer and are unioned into `unified_panel` as `source='t2'` (1,085,246 rows =
30.6% of `feature_panel`), so the leak reaches recorded harness verdicts.

**Magnitude: 0.804% of populated source cells** (337,990 cells, 39 sheets). Small.

Per house rule this is T2-feed code and is **not** being fixed without approval. A causal fix
was built and measured; the obvious one (expanding window) makes the data *worse* — it clips
13.5% of Copper and 9.7% of Oil. The recommended alternative (drop the winsorizer, keep a
causal clip-to-band spike guard) touches only 0.236%, less than today's leaking rule.

Options, evidence, and reverted code:
[docs/T2_CAUSAL_CLEANING_2026-08-21.md](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/docs/T2_CAUSAL_CLEANING_2026-08-21.md)

Related, cosmetic only: `build_t2_master.py:309` counts cleaned cells as
`(series != winsorized).sum()`, and `NaN != NaN` is `True`, so the build log over-reports —
it credits every leading-NaN cell as "winsorized". Log message only; no data affected.

---

## 2026-08-21 — commodity betas ported to the MONTHLY builder; two follow-ups open

`scripts/build_t2_master.py` v1.2 now writes country **betas** to Gold/Copper/Oil/Agriculture
(and beta × 12M commodity return to the ` 12` sheets), ported from the monthly repo's
`Step One Create T2Master.py` (commit 397207b) with the backfilled first 120 months replaced
by an honest `min_periods=36` burn-in. Approved by Arjun 2026-08-21. Two things were
deliberately left alone:

**1. `scripts/build_t2_master_daily.py:95-96` still broadcasts.**
```python
"Gold": (120, False), "Copper": (120, False), "Oil": (120, False),
"Agriculture": (120, False), "Currency": (120, False),
```
The DAILY panel therefore still has the zero-cross-sectional-dispersion problem the monthly
port just fixed — its commodity `_CS` z-scores are 0/0 and are being NaN'd by the guard added
in `t2_normalize_daily.py` the same day. Out of the approved scope; needs its own decision
(a daily beta would want a different window than 120 months).

**2. `scripts/t2_optimizer.py:175-176` STEP4_EXCL still excludes all eight commodity `_CS`
factors.** That exclusion was correct while the variables were broadcast — they carried no
information. Now that they are betas the exclusion is arguably obsolete: the monthly repo
removed its equivalent list and reports IRs of Gold 12_CS 0.46, Oil_CS 0.39, Copper_CS 0.37,
Gold_CS 0.33. NOT changed here, because in ASADO a new signal earns its place through the
harness, not by being switched straight into the production optimizer.

**Verdict provenance.** Any loop-DB verdict or graveyard entry naming `Gold`, `Copper`, `Oil`,
`Agriculture` or their ` 12` / `_CS` / `_TS` derivatives was earned under the OLD broadcast
semantics. Same names, different variables from 2026-08-21 onward. Old verdicts do not transfer.

---

## 2026-08-21 — two dead entries in `t2_optimizer.py` STEP3_SKIP (found, NOT fixed)

While removing the commodity exclusions I noticed two entries in `STEP3_SKIP` that appear to
match nothing, meaning the variable they were meant to skip is being evaluated by Step Three:

| entry | problem |
|---|---|
| `"129MA_TS"` | almost certainly a typo for `"120MA_TS"`. `120MA_CS` is skipped right beside it, and `STEP4_EXCL` skips both `120MA_CS` and `120MA_TS`. |
| `"Tot Return Index_CS"` | the real variable carries a trailing space in the sheet name; `STEP4_EXCL` spells it `"Tot Return Index _CS"`. Same for the `_TS` pair. |

Arjun fixed the `129MA_TS` typo in the monthly repo in the same commit that introduced the
betas (397207b). ASADO still has it. Both are one-line fixes, but each **changes what Step
Three evaluates**, which is beyond the approved commodity scope — hence flagged, not fixed.

---

## 2026-08-21 — daily commodity broadcast RESOLVED

The `build_t2_master_daily.py:95-96` item logged earlier today is **fixed**. The daily lane now
carries country commodity betas, computed on month-end resampled returns with the same
`rolling(120, min_periods=36)` window as the monthly builder, stamped effective the day after
each month-end and forward-filled onto the daily grid.

Deliberately NOT estimated from daily returns: the daily workbook is a CALENDAR-day grid
(9,730 rows / 26.6 years ≈ 366 per year), so a "2520-row" window would be ~6.9 years rather
than 10; and daily betas of Asian markets against commodity closes are mechanically attenuated
by non-synchronous trading. Resampling dodges both and keeps one definition across cadences.

**Two notes, neither blocking:**

1. **These factors reach `t2_optimizer_daily.py` on the next nightly run** — it has no
   commodity exclusion list, so nothing gates them. That script is already logged in this file
   as a port of the OLD pre-fix Step Four carrying its defects plus `min_count=1` partial-universe
   summing. The new factors flow into a known-defective consumer. Context, not a reason to hold.
2. **`clean_excel`'s global `fillna(0)` was left alone.** It would have turned the 36-month beta
   burn-in into a fabricated beta of 0 — a claim of "no commodity exposure", not a gap — so the
   8 beta sheets go through a scoped `clean_excel_keep_na` instead. The global behaviour is
   Arjun's decided call from the 2026-08-10 revert and was not re-litigated.

---

## 2026-08-21 — STEP3_SKIP dead entries RESOLVED (and there were three, not two)

Fixed, Arjun approved. Checked against the 111 variables the normalizer actually emits:

| was | is | note |
|---|---|---|
| `"129MA_TS"` | `"120MA_TS"` | typo — no `129MA` variable exists |
| `"Tot Return Index_CS"` | `"Tot Return Index _CS"` | sheet name carries a trailing space |
| `"Tot Return Index_TS"` | `"Tot Return Index _TS"` | same; I had only flagged the `_CS` half |

All three matched nothing, so the variable each was meant to skip was being evaluated by Step
Three all along. Step Three now sees **90 of 111** variables rather than 93. `STEP4_EXCL` was
checked the same way and has no dead entries.

## 2026-08-21 — the stray `main` commits RESOLVED

`main` is back at `06984bb`. The two auto-checkpoints (`ccd8ba8`, `6f2797f`) that landed on it
after an unintended `checkout Complexity -> main` captured in-progress `build_t2_master.py`
edits against main's older lineage — a spike guard with no commodity betas, a hybrid that
existed nowhere else. Both were **local only**; `origin/main` (`cccd553`) was never touched and
no force-push was involved. They are preserved at tag `discarded/main-autocheckpoints-20260821`
(`dd766d6`) and that tag is safe to delete.

---

## 2026-08-21 — DAILY lane: 1.3M missing cells are being written as exact 0.0 (found, NOT fixed)

Surfaced by the full daily run of 2026-08-21. `clean_excel` in
`scripts/build_t2_master_daily.py` fills every missing numeric cell with `0`. Where Bloomberg
genuinely has **no data at all**, that fabricates a real-looking value: a P/B of 0, a dividend
yield of 0, a cash flow of 0. Measured on this run, source-NaN → output-zero, per sheet:

| sheet | missing in source | zeros in output | first date Bloomberg has ANY data |
|---|---|---|---|
| Shiller PE | 127,324 | 127,324 | 1999-12-31 |
| Best ROE | 82,117 | 82,117 | **2005-07-04** |
| Best Cash Flow | 81,949 | 83,464 | **2005-03-15** |
| Positive PE | 81,725 | 81,725 | **2005-03-15** |
| Best PBK | 81,533 | 81,533 | **2005-02-08** |
| Best Div Yield | 81,494 | 81,494 | **2005-03-14** |
| Best Price Sales | 68,305 | 68,305 | 2000-01-25 |
| Best PE / BEST EPS | 63,680 / 63,674 | 63,965 / 63,674 | 1999-12-31 |
| MCAP / Mcap Weights | 44,184 each | 44,184 each | 1999-12-31 |
| 10Yr Bond | 45,815 | 45,827 | 1999-12-31 |
| *(+9 more)* | | | |
| **total** | **1,299,823** | | |

**Five sheets have no Bloomberg data whatsoever before 2005**, so their entire pre-2005 daily
history is fabricated zeros — e.g. `Best Cash Flow` is exactly 0.0 for all 34 countries on
1,901 consecutive dates, 1999-12-31 → 2005-03-14, then real values from 2005-03-15.

**Consequences.** `_CS` on those dates is saved by the guard added 2026-08-21 (all values
identical → dispersion zero → NaN, logged). `_TS` is **not** protected: a five-year run of
exact 0.0 followed by a step to real values makes the 2005 transition look like an enormous
outlier to the expanding z-score, and every pre-2005 `_TS` value is derived from fabricated data.

**Not fixed.** This is T2-feed code, and it sits next to `clean_excel`'s global `fillna(0)`,
which is Arjun's decided behaviour from the 2026-08-10 revert. Note the distinction though:
that decision was about *price/return* sheets and the `Fill=P` pull convention. This is
different — filling an absent fundamental with 0 is not a convention choice, it asserts a
value Bloomberg never reported. The monthly lane is unaffected (it does not use `clean_excel`).

Cheapest honest fix if wanted: leave these cells NaN (as the commodity beta sheets already do
via `clean_excel_keep_na`), or start each sheet at its first real date.

---

## 2026-08-21 — Bloomberg API stopped negotiating mid-morning (ACTION NEEDED on the Windows side)

During the manual full daily run (10:31–10:57) the Bloomberg API went from working to refusing
sessions. The T2 daily pull at 10:31 succeeded (290s, 58.1 MB). By ~10:50 six loop Layer-1
collectors could not connect, and it is **still failing now**:

```
Windows 11 is running                    OK
Bloomberg is running (7 processes)       OK
Port 8194 reachable on 10.211.55.3       OK
BLPAPI session negotiation               FAILS
  "Session negotiation failed for 10.211.55.3:8194 result = 1"
  "Failed BBCOMM session negotiation"
  "Platform failed 3 consecutive times, stopped trying to reconnect"
```

TCP reaches the VM and the Bloomberg processes are alive, so this is not the VM being down —
it is the Terminal not accepting API sessions. Usual causes: the Terminal logged itself out or
the screen locked, the account got logged in somewhere else, or `bbcomm.exe` needs a restart.
**Requires someone on the Windows side to log the Terminal back in.**

Affected (all fail-soft — "existing parquet untouched", so no data was corrupted):
`collect_etf_flows_bbg.py`, `collect_consensus_bbg.py`, `collect_market_implied_bbg.py`,
`collect_sov_ratings_bql.py`, `collect_eco_surprise_bbg.py`.

Impact was small **only because the scheduled 09:13 nightly had already refreshed those files
at 09:29–09:32**, so they are ~1.5 h stale rather than missing. Had the manual run been the
day's only run, five Layer-1 inputs would have gone a full day stale while the pipeline still
reported `ALL STEPS OK`.

**The reporting gap is the real issue.** `daily_update.py` printed `ALL STEPS OK` for 12/12
stages while six collectors inside the loop stage failed. Fail-soft is right for these — a dead
Terminal should not kill the brief — but the summary should surface degraded sub-steps rather
than showing a clean bill of health. Worth a "N sub-collectors failed, data is stale" line in
the summary block.

Separately: `consensus_signals.parquet`, `market_implied_signals.parquet` and
`eco_surprise_signals.parquet` are all dated **2026-07-14** — five weeks stale, unrelated to
today's outage. Worth checking whether anything still rebuilds them.
