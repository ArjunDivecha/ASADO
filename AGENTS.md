## Learned User Preferences

- Keep ASADO code, data outputs, and pipeline artifacts under the ASADO workspace root unless the user explicitly directs otherwise.
- Design collection and ETL so it can run on a recurring schedule (for example monthly) and refresh the master database.
- When the user attaches an implementation plan: do not edit the plan file; use existing to-dos without recreating them.
- When building integrations, list required third-party API keys up front if the user wants to provision them in parallel.
- When an API key can't be obtained (e.g., email verification broken), prefer alternative free data sources over blocking on registration.

## Learned Workspace Facts

- ASADO workspace root: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO`.
- User-specified location for T2 and GDELT inputs: `Data` under the ASADO root (full path: `.../ASADO/Data`).
- Phase 1 external data specs, paths, and indicator definitions live in `CLAUDE_CODE_BRIEF.md` and `PRD_Phase1_Program1_External_Data.md` in this repo.
- FRED and EIA credentials are expected in the project `.env` file.
- 3 collector scripts in `scripts/`: `collect_external.py` (7 sources), `collect_extended.py` (12 sources), `collect_imf.py` (7 IMF datasets). Plus `setup_duckdb.py`, `setup_neo4j.py`, `db_bridge.py`.
- IMF data uses the SDMX 3.0 API at `api.imf.org` with no API key required. The legacy `dataservices.imf.org` endpoint is defunct.
- DuckDB at `Data/asado.duckdb`; `unified_panel` view joins 5 tables: `t2_master`, `external_factors`, `extended_factors`, `gdelt_panel`, `imf_factors`.
- Neo4j at `bolt://localhost:7687` — start with `brew services start neo4j` before any graph operations.
- Monthly update: run the 3 collectors then the 2 setup scripts. All collectors use source-level merge (failed sources keep previous data), 24h cache, and timestamped backups.
- 34 countries tracked, defined in `config/country_mapping.json`.
