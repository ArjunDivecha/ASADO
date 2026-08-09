# ASADO monthly_update.py — full run
Started: 2026-08-09 12:51:58 PDT
Backup taken first: Data/backups/pre_monthly_20260809_125117 (3.4GB: asado.duckdb + Data/processed)
Flags: none (full run — Bloomberg confirmed reachable at 10.211.55.3:8194)
Log: run.log  ·  Heartbeat: heartbeat.txt

## OUTCOME — SUCCESS

Finished 2026-08-09 13:26:50 PDT. **Total elapsed 2084.5s (34.7 min). Exit 0.
"ALL STEPS COMPLETED SUCCESSFULLY."**

### Data verified to have ADVANCED (not just exit-0)

| Table | Before | After | Rows |
|---|---|---|---|
| t2_raw | 2026-07-01 | **2026-08-01** | 477,965 |
| t2_master | 2026-07-01 | **2026-08-01** | 1,085,246 |
| bloomberg_factors | 2026-07-01 | **2026-08-01** | 106,600 |
| macrostructure_factors | 2026-07-01 | **2026-08-01** | 97,105 |
| external_factors | 2026-06-01 | **2026-07-01** | 138,042 |
| factor_returns | 2026-06-01 | **2026-07-01** | 106,816 |
| commodity_panel | 2026-05-01 | **2026-07-01** | 438,313 (caught up 2 months) |
| ff_factors | 2026-05-29 | **2026-06-30** | 542,125 |
| imf_factors | 2031-12-01 | 2031-12-01 | 125,474 (WEO forward-dating — still excluded per PIT audit) |

`asado.duckdb` rebuilt 13:26, 3.2GB -> 2.38GB (fresh build reclaims space).
`docs/factor_reference.md` regenerated (was a month stale at Jul 1).

### One collector failed — benign

`ND-GAIN` (Notre Dame Global Adaptation Index): SSL cert verification failed against
`gain-new.crc.nd.edu` after 3 retries — an untrusted cert chain on THEIR server, not ours.
Existing data intact (1,189 rows per variable, max 2023-12-01); the dataset is annual and was
already ~2.5 years stale, so no new vintage was missed. No action needed unless NDGAIN_* is
wanted current, which would need a cert workaround.

### Notes

- Forward-dated rows added: exactly 2 (`ILO_LFP_Rate`, `ILO_Unemployment_Rate` at 2026-12-01).
  Same hazard class as IMF_WEO but negligible in size.
- Backup retained at `Data/backups/pre_monthly_20260809_125117` (3.4GB). Safe to delete once
  this warehouse has been exercised for a few days.
- Preflight before launch: no DuckDB holders, no pipeline processes, Bloomberg reachable at
  10.211.55.3:8194, 391GB free.
