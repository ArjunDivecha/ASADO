# Operations and runbooks

This repository has several moving parts that are safe only when run in the right order. The operational story is mostly encoded in `README.md`, `CLAUDE.md`, `AGENTS.md`, and the docstrings of the orchestrator scripts.

## Runtime prerequisites

From the source docs:
- Bloomberg Terminal must be logged in on the Parallels Windows VM for Bloomberg-dependent steps.
- Neo4j must be running locally before graph steps (`brew services start neo4j`).
- The project venv is the default environment for most scripts.
- Bloomberg-specific scripts use the OpusBloomberg environment described in `CLAUDE.md` and the script headers.

## Main commands

### Monthly full rebuild
`python scripts/monthly_update.py`

This is the high-level monthly orchestrator. Its docstring shows the stage order and output surfaces. It rebuilds collectors, panels, DuckDB, Neo4j, embeddings, and schema docs.

Use this when you need a full warehouse refresh or when upstream source coverage changed.

### Daily metronome
`python scripts/daily_update.py`

This is the daily run for the fast-moving T2 + GDELT surfaces. The script docstring is explicit that:
- T2 uses live Bloomberg pulls,
- GDELT is refreshed daily,
- Econ is skipped,
- and the loop stage is chained last.

The script supports `--resume`, `--skip-bloomberg`, `--skip-gdelt`, `--skip-neo4j`, and `--t2-only`.

### Nightly loop job
`python scripts/loop/loop_daily_job.py`

This is the nightly alpha-hunting orchestrator. It reads from both the main warehouse and the loop DB, emits dislocations, briefs, evidence packs, ledgers, calibration reports, and cockpit refresh data.

The docstring is useful because it lists the ordered steps and clarifies which collectors are parquet-only versus loop-DB loaders.

## Resume and lock discipline

Two operational patterns are especially important:

1. **Daily resume fingerprints** — `scripts/daily_update.py` records script content hashes and argv so a changed stage invalidates its checkpoint for that day.
2. **DuckDB lock guard** — the repo has a dedicated `scripts/duckdb_lock_guard.py` because idle readers can block nightly writers. `AGENTS.md` says the guard auto-kills only known sandbox squatter patterns and otherwise waits or fails loudly.

## Data safety rules

- Never create persistent tables directly in `Data/asado.duckdb`; `setup_duckdb.py` recreates it on rebuild.
- Keep loop artifacts in `Data/loop/` and `Data/work/loop/`.
- Treat `Data/` artifacts as runtime outputs, not source docs.
- Preserve the one-writer / many-readers constraint around DuckDB.

## Operational failure modes to watch

- Bloomberg connectivity or terminal login problems.
- Neo4j not running.
- DuckDB lock contention from idle analysis sessions.
- Stale or missing loop outputs when the nightly chain is interrupted.
- Pipeline stage edits that invalidate resume checkpoints.

## Operational source references

- `README.md` — primary runtime guidance and command summary.
- `CLAUDE.md` — pipeline and environment conventions.
- `AGENTS.md` — durable gotchas and workspace rules.
- `scripts/daily_update.py` — daily flow, resume fingerprints, stage timeout.
- `scripts/monthly_update.py` — monthly orchestration and output map.
- `scripts/loop/loop_daily_job.py` — loop step order and outputs.
- `scripts/duckdb_lock_guard.py` — lock-squatter handling.

## Where to go next

- [Architecture overview](architecture.md)
- [Loop and research workflows](loop-and-research.md)
- [Prediction markets and Brier Gate](prediction-markets.md)
