## Learned User Preferences

- Keep ASADO code, data outputs, and pipeline artifacts under the ASADO workspace root unless the user explicitly directs otherwise.
- Design collection and ETL so it can run on a recurring schedule (for example monthly) and refresh the master database.
- When the user attaches an implementation plan: do not edit the plan file; use existing to-dos without recreating them.
- When building integrations, list required third-party API keys up front if the user wants to provision them in parallel.
- When an API key can't be obtained (e.g., email verification broken), prefer alternative free data sources over blocking on registration.
- For Bloomberg Terminal ingestion, use the user's OpusBloomberg pathway (Mac to Parallels to Terminal) and that project's configured Python environment; do not substitute a different Bloomberg connectivity approach.
- Exclude `.cursor/hooks/state/` (for example `continual-learning-index.json`) from git commits unless the user explicitly asks to version those files.

## Learned Workspace Facts

- ASADO workspace root: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO`.
- Canonical T2 inputs for DuckDB (see `scripts/setup_duckdb.py`): `/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/Normalized_T2_MasterCSV.csv` and `/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/T2 Master.xlsx`. GDELT prefers `/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 GDELT/GDELT_Factors_MasterCSV.csv` when present and otherwise falls back to `Data/processed/gdelt_panel_snapshot.parquet` inside this repo.
- Phase 1 external data specs, paths, and indicator definitions live in `CLAUDE_CODE_BRIEF.md` and `PRD_Phase1_Program1_External_Data.md` in this repo.
- FRED and EIA credentials are expected in the project `.env` file.
- `scripts/` pipeline: collectors `collect_external.py`, `collect_extended.py`, `collect_imf.py`, `collect_bilateral.py`, `collect_bloomberg.py` (Bloomberg via `/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg` and its venv as wired in the Bloomberg scripts); `setup_duckdb.py`, `setup_neo4j.py`, `build_embeddings.py`, `db_bridge.py`, and monthly orchestrator `monthly_update.py`.
- IMF data uses the SDMX 3.0 API at `api.imf.org` with no API key required. The legacy `dataservices.imf.org` endpoint is defunct.
- DuckDB at `Data/asado.duckdb`; `unified_panel` view joins 7 tables (`t2_master`, `t2_raw`, `external_factors`, `extended_factors`, `gdelt_panel`, `imf_factors`, `bloomberg_factors`). Rebuilt size is on the order of ~4 GB (monthly plus daily extension). Daily tables include `t2_factors_daily`, `t2_levels_daily`, `gdelt_factors_daily`, `gdelt_raw_daily`, `factor_returns_daily`, `variable_meta`, `daily_calendar`.
- Daily extension built by `scripts/build_daily_panels.py` (orchestrator uses `--rebuild --no-backup`). MCP tools `event_window` and `daily_factor_series` in `asado_mcp_server.py` expose daily data. Status: `docs/DAILY_EXTENSION_STATUS.md`.
- Stage 2 prediction markets: built by `scripts/build_predmkt_panel.py` from curated registry `config/predmkt_curated.yaml`; DuckDB holds `predmkt_daily`, `predmkt_market_meta`, `predmkt_outcome_meta`, `predmkt_country_spillover`, `predmkt_resolutions`, and `predmkt_signals_daily`. MCP exposes `predmkt_snapshot`, `country_signal_now`, and `event_market_set`. For country composites, `predmkt_country_risk_composite` > 0 means implied downside risk; `predmkt_country_opportunity_composite` > 0 means implied upside.
- Neo4j at `bolt://localhost:7687` — start with `brew services start neo4j` before graph operations. Factor nodes carry daily performance stats from `factor_returns_daily` (`daily_sharpe_252d`, `daily_vol_252d`, `daily_max_drawdown_252d`, `daily_cum_return_252d`, `is_optimizer_selected`), set in `setup_neo4j.py`; 157 factors have daily stats; 8 are `is_optimizer_selected = true`.
- Bloomberg collector (`collect_bloomberg.py`): multi-phase bonds, CDS, OIS, WIRP, ECFC/EHGD consensus, PMI, M2, derived signals; `BBG` supports `ref()`, `ref_batch()`, `hist()`, `bds()`. Ticker quirks: ECFC try `ECGD[CC]` then `EHGD[CC]Y` (Switzerland `ECGDSW`, not `ECGDCH`); PMI `MPMI[CC]MA/SA` with Japan `JA` not `JN`; M2 tries multiple candidates per country.
- Monthly refresh: run `python scripts/monthly_update.py` from the repo root; collectors use source-level merge, 24h cache, and timestamped backups, then DB and embedding rebuilds as configured.
- 34 countries tracked, defined in `config/country_mapping.json`.
- Git remote for this project: https://github.com/ArjunDivecha/ASADO
