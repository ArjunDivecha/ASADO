## Learned User Preferences

- Keep ASADO code, data outputs, and pipeline artifacts under the ASADO workspace root unless the user explicitly directs otherwise.
- Design collection and ETL so it can run on a recurring schedule (for example monthly) and refresh the master database.
- When the user attaches an implementation plan: do not edit the plan file; use existing to-dos without recreating them.
- When building integrations, list required third-party API keys up front if the user wants to provision them in parallel.
- When an API key can't be obtained (e.g., email verification broken), prefer alternative free data sources over blocking on registration.
- For Bloomberg Terminal ingestion, use the user's OpusBloomberg pathway (Mac to Parallels to Terminal) and that project's configured Python environment; do not substitute a different Bloomberg connectivity approach.

## Learned Workspace Facts

- ASADO workspace root: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO`.
- Canonical T2 inputs for DuckDB (see `scripts/setup_duckdb.py`): `/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/Normalized_T2_MasterCSV.csv` and `/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/T2 Master.xlsx`. GDELT prefers `/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 GDELT/GDELT_Factors_MasterCSV.csv` when present and otherwise falls back to `Data/processed/gdelt_panel_snapshot.parquet` inside this repo.
- Phase 1 external data specs, paths, and indicator definitions live in `CLAUDE_CODE_BRIEF.md` and `PRD_Phase1_Program1_External_Data.md` in this repo.
- FRED and EIA credentials are expected in the project `.env` file.
- `scripts/` pipeline: collectors `collect_external.py`, `collect_extended.py`, `collect_imf.py`, `collect_bilateral.py`, `collect_bloomberg.py` (Bloomberg via `/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg` and its venv as wired in the Bloomberg scripts); `setup_duckdb.py`, `setup_neo4j.py`, `build_embeddings.py`, `db_bridge.py`, and monthly orchestrator `monthly_update.py`.
- IMF data uses the SDMX 3.0 API at `api.imf.org` with no API key required. The legacy `dataservices.imf.org` endpoint is defunct.
- DuckDB at `Data/asado.duckdb`; `unified_panel` view joins 7 tables: `t2_master`, `t2_raw`, `external_factors`, `extended_factors`, `gdelt_panel`, `imf_factors`, `bloomberg_factors`. Current rebuilt size is ~4 GB (monthly ~96 MB + daily extension ~3.9 GB). Monthly: ~2.46M rows, 385 variables. Daily: 58M+ rows across 7 tables (`t2_factors_daily`, `t2_levels_daily`, `gdelt_factors_daily`, `gdelt_raw_daily`, `factor_returns_daily`, `variable_meta`, `daily_calendar`).
- Daily extension built by `scripts/build_daily_panels.py` (runs `--rebuild --no-backup` in orchestrator). MCP tools `event_window` and `daily_factor_series` in `asado_mcp_server.py` expose daily data. Full status: `docs/DAILY_EXTENSION_STATUS.md`.
- Neo4j Factor nodes carry daily performance stats (`daily_sharpe_252d`, `daily_vol_252d`, `daily_max_drawdown_252d`, `daily_cum_return_252d`, `is_optimizer_selected`) from `factor_returns_daily`. Added via `set_daily_factor_stats()` in `setup_neo4j.py`, refreshed each rebuild. 157 factors have daily stats; 8 are `is_optimizer_selected = true`.
- Bloomberg collector (`collect_bloomberg.py`) has 11 data categories across 3 phases: Phase 1 (bond yields 4 tenors, CDS 5Y, breakevens, credit ratings), Phase 2 (OIS 10Y swap rates, WIRP implied policy rates, ECFC consensus GDP/CPI with EHGD fallback, DDIS debt metrics), Phase 3 (PMI Manufacturing/Services, M2 money supply YoY), plus 3 derived signals (yield curve slope, MIPD default probability, Z-spread vs OIS). Total: 66,656 rows, 17 variables. The `BBG` class in OpusBloomberg supports `ref()`, `ref_batch()`, `hist()`, and `bds()` methods.
- ECFC GDP tickers use a fallback strategy: try ECGD[CC] (consensus) first, fall back to EHGD[CC]Y (actual GDP YoY). Switzerland uses ECGDSW (not ECGDCH, which is China).
- PMI tickers follow MPMI[CC]MA/SA pattern; Japan uses JA not JN in PMI tickers.
- M2 tickers have no uniform pattern; collector tries multiple candidates per country.
- Neo4j at `bolt://localhost:7687` — start with `brew services start neo4j` before any graph operations.
- Monthly refresh: run `python scripts/monthly_update.py` from the repo root; it runs the collectors (source-level merge, 24h cache, timestamped backups) then rebuilds DuckDB, Neo4j, and embeddings as configured.
- 34 countries tracked, defined in `config/country_mapping.json`.
- Git remote for this project: https://github.com/ArjunDivecha/ASADO
