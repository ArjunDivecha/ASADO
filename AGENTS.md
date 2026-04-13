## Learned User Preferences

- Keep ASADO code, data outputs, and pipeline artifacts under the ASADO workspace root unless the user explicitly directs otherwise.
- Design collection and ETL so it can run on a recurring schedule (for example monthly) and refresh the master database.
- When the user attaches an implementation plan: do not edit the plan file; use existing to-dos without recreating them.
- When building integrations, list required third-party API keys up front if the user wants to provision them in parallel.
- When an API key can't be obtained (e.g., email verification broken), prefer alternative free data sources over blocking on registration.
- For Bloomberg Terminal ingestion, use the user's OpusBloomberg pathway (Mac to Parallels to Terminal) and that project's configured Python environment; do not substitute a different Bloomberg connectivity approach.

## Learned Workspace Facts

- ASADO workspace root: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO`.
- Canonical CSV inputs for T2 and GDELT when loading DuckDB (see `scripts/setup_duckdb.py`): `/Users/arjundivecha/Dropbox/AAA Backup/Transformer/Normalized_T2_MasterCSV.csv` and `/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 GDELT/GDELT_Factors_MasterCSV.csv`.
- Phase 1 external data specs, paths, and indicator definitions live in `CLAUDE_CODE_BRIEF.md` and `PRD_Phase1_Program1_External_Data.md` in this repo.
- FRED and EIA credentials are expected in the project `.env` file.
- `scripts/` pipeline: collectors `collect_external.py`, `collect_extended.py`, `collect_imf.py`, `collect_bilateral.py`, `collect_bloomberg.py` (Bloomberg via `/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg` and its venv as wired in the Bloomberg scripts); `setup_duckdb.py`, `setup_neo4j.py`, `build_embeddings.py`, `db_bridge.py`, and monthly orchestrator `monthly_update.py`.
- IMF data uses the SDMX 3.0 API at `api.imf.org` with no API key required. The legacy `dataservices.imf.org` endpoint is defunct.
- DuckDB at `Data/asado.duckdb`; `unified_panel` view joins 6 tables: `t2_master`, `external_factors`, `extended_factors`, `gdelt_panel`, `imf_factors`, `bloomberg_factors`.
- Bloomberg collector (`collect_bloomberg.py`) has 9 data categories: bond yields (4 tenors), CDS 5Y, breakevens, OIS 10Y swap rates, WIRP implied policy rates, ECFC consensus GDP/CPI, plus 3 derived signals (yield curve slope, MIPD default probability, Z-spread vs OIS). The `BBG` class in OpusBloomberg supports `ref()`, `ref_batch()`, `hist()`, and `bds()` methods.
- Neo4j at `bolt://localhost:7687` — start with `brew services start neo4j` before any graph operations.
- Monthly refresh: run `python scripts/monthly_update.py` from the repo root; it runs the collectors (source-level merge, 24h cache, timestamped backups) then rebuilds DuckDB, Neo4j, and embeddings as configured.
- 34 countries tracked, defined in `config/country_mapping.json`.
- Git remote for this project: https://github.com/ArjunDivecha/ASADO
