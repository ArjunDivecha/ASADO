---
type: "Reference"
title: "Operations and runbooks"
description: "How to run ASADO's monthly, daily, and nightly pipelines safely — prerequisites, commands, resume/lock discipline, failure modes, and the automated OpenWiki documentation workflow."
---

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

Two interactive launchers wrap the same monthly sequence with live streaming: `run.py` (interactive top-level launcher that prompts for the one manual Bloomberg prerequisite, then runs every automated step in order with a running status board) and `dashboard.py` (a real-time terminal dashboard that tails the `run.py` log and shows per-step status, collector metrics, DuckDB table sizes, and live output). These are operator conveniences over the same stages and flags as `monthly_update.py`, not separate pipelines.

### Daily metronome
`python scripts/daily_update.py`

This is the daily run for the fast-moving T2 + GDELT surfaces. The script docstring is explicit that:
- T2 uses live Bloomberg pulls,
- GDELT is refreshed daily,
- Econ is skipped,
- and the loop stage is chained last.

The script supports `--resume`, `--skip-bloomberg`, `--skip-gdelt`, `--skip-neo4j`, `--skip-db`, `--skip-loop`, and `--t2-only`. The `--skip-db` and `--skip-loop` flags carve out the DuckDB panel load and the chained nightly loop job respectively, letting you re-run just the collection + graph stages or just the fast-moving surfaces.

### Nightly loop job
`python scripts/loop/loop_daily_job.py`

This is the nightly alpha-hunting orchestrator. It reads from both the main warehouse and the loop DB, emits dislocations, briefs, evidence packs, ledgers, calibration reports, and cockpit refresh data.

The docstring is useful because it lists the ordered steps and clarifies which collectors are parquet-only versus loop-DB loaders. The full ordered `STEPS` chain is documented in [Loop and research workflows](loop-and-research.md); a singleton `fcntl.flock` (`Data/loop/.loop_daily.lock`) guards against the 07:30 chained run and the 11:30 launchd safety-net rebuilding the loop DB concurrently.

Near the end of the run it also chains two Discovery Triage steps (`discovery_forward_track`, then the gated `discovery_docket --nightly`). The docket is a **cost gate**: it no-ops unless `ASADO_RUN_DISCOVERY_LAB=1`, so the nightly job never auto-spends on the Anthropic API. See [Discovery Triage](discovery-triage.md) for the full custody chain.

The nightly job also runs the optional Learning Loop steps (`score_gap_outcomes`, `attribute_outcomes`) and the Fable connections step (`build_fable_connections`); the lesson layer and Discovery Lab are separately gated cost switches (`ASADO_RUN_ATTRIBUTION_LLM=1`, `ASADO_RUN_DISCOVERY_LAB=1`) that are no-op by default. Optional steps (declared in `config/governance_contract.yaml`) never red-light the nightly run.

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
- Accidentally enabling the Discovery Lab in the nightly run (`ASADO_RUN_DISCOVERY_LAB=1`) or the Fable-xhigh lesson layer (`ASADO_RUN_ATTRIBUTION_LLM=1`) and incurring Anthropic API spend; both are no-op by default.

## Operational source references

- `README.md` — primary runtime guidance and command summary.
- `CLAUDE.md` — pipeline and environment conventions.
- `AGENTS.md` — durable gotchas and workspace rules.
- `scripts/daily_update.py` — daily flow, resume fingerprints, stage timeout.
- `scripts/monthly_update.py` — monthly orchestration and output map.
- `scripts/loop/loop_daily_job.py` — loop step order and outputs.
- `scripts/duckdb_lock_guard.py` — lock-squatter handling.

## OpenWiki documentation workflow

The repository's `openwiki/` wiki is refreshed by a scheduled GitHub Actions workflow at `.github/workflows/openwiki-update.yml`. The workflow:

1. Installs the `openwiki` CLI globally.
2. Runs `openwiki code --update --print`, configured via `OPENWIKI_PROVIDER`, `OPENWIKI_MODEL_ID`, and `OPENROUTER_API_KEY` env vars (with optional LangSmith tracing).
3. Opens a pull request (`openwiki/update` branch) with the regenerated `openwiki/` content and touched agent-instruction files, instead of committing directly to the main branch.

Do not hand-edit generated OpenWiki pages unless explicitly asked; prefer updating source code/docs and letting the workflow regenerate.

## Where to go next

- [Architecture overview](architecture.md)
- [Loop and research workflows](loop-and-research.md)
- [Discovery Triage](discovery-triage.md)
- [Prediction markets and Brier Gate](prediction-markets.md)
