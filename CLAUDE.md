# CLAUDE.md — ASADO operator's manual

Guidance for a coding agent working in this repo. Global rules (light mode, mandatory
doc headers, `file://` result links) live in `~/CLAUDE.md` and are not repeated here.
**Read `openwiki/quickstart.md` and `AGENTS.md` first** — `AGENTS.md` carries the most
current operational gotchas and is updated more often than this file.

> Verification note (2026-07-06 review): every script path below was confirmed to exist on
> disk. Pipelines were **not executed** in this review (they hit live APIs / large rebuilds),
> so runtimes are from the repo's own docs, marked `(doc)`.

## Purpose

ASADO is a hybrid data-collection + research platform for a 34-country macro universe. A
warehouse (DuckDB + Neo4j) ingests 26+ free sources, World Bank commodities, and ~28
Bloomberg variables; on top of it runs the **Alpha-Hunting Loop** — a nightly engine that
finds cross-subsystem dislocations, forms hypotheses, and puts them through a skeptic harness
(PIT embargo, Newey–West t, deflated Sharpe, cost model). Its actual product is *trustworthy
falsification*: most candidate signals are expected to die, and the discipline that kills them
honestly is the asset. Country and factor returns are the **outcome source of truth**;
everything else (commodities, GDELT, Bloomberg, graph edges, prediction markets) is
explanatory and must be joined back to returns before any performance claim.

## Architecture map (load-bearing files, absolute paths)

- `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/scripts/monthly_update.py` — single-command warehouse orchestrator (collect → rebuild DuckDB → Neo4j → schema cache).
- `.../scripts/daily_update.py` — daily orchestrator; runs the loop as its final stage (~07:30 PT).
- `.../scripts/setup_duckdb.py` — **deletes and recreates** `Data/asado.duckdb` from panels.
- `.../scripts/build_normalized_panel.py` — builds `normalized_panel` + `feature_panel` (the query-facing views).
- `.../scripts/build_daily_panels.py` — daily extension (T2 / GDELT / optimizer-return tables).
- `.../scripts/db_bridge.py` — `AsadoDB` unified query interface (DuckDB + Neo4j); prefer over the MCP for scripts.
- `.../scripts/asado_mcp_server.py` — stdio MCP server for Claude Desktop ("use ASADO").
- `.../scripts/duckdb_lock_guard.py` — `guarded_connect()`; wraps every pipeline open of the main DB.
- `.../scripts/loop/loop_daily_job.py` — Alpha-Hunting Loop nightly orchestrator (~33 steps).
- `.../scripts/loop/build_dislocations.py` — detectors D1–D10 + the nightly brief.
- `.../scripts/loop/build_combiner.py` — walk-forward ridge combiner; `combiner_scores_daily` is the live prediction surface.
- `.../scripts/harness/evaluate_signal.py` — skeptic harness (PIT embargo, NW-t, deflated Sharpe, cost grid).
- `.../scripts/harness/ff_spanning.py` — regresses a return series on regional Fama-French factors (alpha vs repackaged beta).
- `.../scripts/qa/validate_returns_first.py` — returns-first / leakage QA check.
- `.../config/country_mapping.json` — Rosetta Stone: 34 T2 names → source codes (ISO/OECD/BIS/WB/EPU/GPR).
- `.../config/family_registry.yaml` — every harness signal-family registration (any "signal works" claim must land here).
- `.../config/ff_region_map.json` — country → FF region link, applied at regression time.

## Commands that work (scripts existence-verified; not executed this review)

```bash
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO" && source venv/bin/activate

# Full monthly refresh (~8-10 min, doc). Flags: --skip-neo4j --skip-bloomberg
#   --skip-wb-commodity --commodity-only --collectors-only --db-only --dry-run
python scripts/monthly_update.py

# DB rebuilds from existing panels (no network):
python scripts/setup_duckdb.py            # add --check to verify instead of rebuild
python scripts/build_normalized_panel.py  # refresh normalized_panel + feature_panel
python scripts/build_daily_panels.py      # --skip-levels (fast) | --check
python scripts/setup_neo4j.py             # --check to verify
python scripts/build_embeddings.py        # --dims 64 to override 128-d default

# Individual collectors (each: --force bypasses 24h cache, --dry-run previews):
python scripts/collect_external.py   # EPU/GPR/BIS/OECD/WB/REER
python scripts/collect_extended.py   # rates, BCI/CCI, ECB FX, ND-GAIN, ILOSTAT...
python scripts/collect_imf.py        # CPI/WEO/BOP/rates/FX/labor/trade
python scripts/collect_bilateral.py  # --trade-only | --bank-only
python scripts/collect_macrostructure.py
python scripts/collect_wb_commodity_prices.py   # --check
python scripts/collect_ff_factors.py            # NOTE: scripts/, not scripts/loop/

# Bloomberg — needs Parallels + Terminal logged in; runs under the OpusBloomberg env:
conda run -p "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv" \
  python scripts/collect_bloomberg.py            # test: scripts/test_bloomberg_connection.py

# Freeze live tables to parquet before experimenting (never hold a live-DB connection):
python scripts/snapshot_for_experiment.py        # NOTE: scripts/, not scripts/loop/

# Tests
python -m pytest tests/                           # repo test suite
brew services list | grep neo4j                   # is the graph up?
```

## Data locations (absolute paths)

- `.../Data/asado.duckdb` — main analytical warehouse (~3.6 GB; **recreated every rebuild**).
- `.../Data/loop/asado_loop.duckdb` — Alpha-Hunting Loop DB (separate, durable; gitignored).
- `.../Data/processed/` — tidy parquet panels per collector; `run_history.json` (last 24 runs).
- `.../Data/work/loop/` — loop parquet intermediates; `bbg_quota_log.csv` (Bloomberg quota).
- `.../Data/dislocations/brief_YYYY_MM_DD.md` — nightly dislocation brief (committed).
- `.../ledgers/*.jsonl` — append-only hypothesis/thesis ledgers (committed).
- `.../Data/logs/monthly_update_YYYY_MM_DD.log` — per-run logs.
- `.../docs/factor_reference.md` — auto-regenerated "what does ASADO know" catalog (every table/variable/graph label).
- Neo4j: `bolt://localhost:7687` (`neo4j` / `mythos2026`); UI `http://localhost:7474`.
- API keys / env: `/Users/arjundivecha/Dropbox/AAA Backup/.env.txt` (FRED_API_KEY, EIA_API_KEY, ANTHROPIC_API_KEY).

## Conventions & gotchas (repo-specific — the parts that bite)

- **The main checkout is production.** launchd runs whatever is checked out in this tree.
  Never switch branches here — use `git worktree add "../ASADO-exp-<name>"` for pipeline-code
  experiments. `A Complete/Fable Daily Trading` reads the loop DB read-only at 12:20 PT.
- **`setup_duckdb.py` deletes and recreates `Data/asado.duckdb`.** Never create persistent
  tables in the main DB — they will vanish. Durable loop state lives in `asado_loop.duckdb`
  (the main DB is attached read-only there as schema `asado`).
- **Never hold a DuckDB connection** (even idle read-only) to either DB. DuckDB is
  one-writer/many-readers; a stray holder blocks the nightly writers — this caused the
  2026-07-02/03 pipeline failures. `duckdb_lock_guard.guarded_connect()` now wraps pipeline
  opens; snapshot inputs with `snapshot_for_experiment.py` before experimenting.
- **Forward-return blacklist (leakage trap):** T2 `NMRet`/`NDRet` variables
  (`1MRet/3MRet/6MRet/9MRet/12MRet` + daily analogs `1DRet/5DRet/20DRet/60DRet/120DRet`)
  are optimizer **targets**, not trailing momentum. They are hard-blacklisted as harness
  signals (canonical set: `scripts/harness/evaluate_signal.py:146-149`) — never register
  one as a predictor.
- **Isolated tables — never union into `feature_panel`/`unified_panel`:** `ff_factors` (regional,
  8 series), the JST Macrohistory calibration corpus, and optimizer outputs (`factor_returns`,
  `factor_top20_membership`, `country_factor_attribution`). The optimizer-output exclusion is a
  structural guard against the optimizer input/output cycle; the FF/JST exclusion prevents
  region-level series being broadcast/tiled across the 34 countries (a leakage class). If you
  find yourself adding any of these to a panel view, stop.
- **Experiment sandbox:** write only to `experiments/<name>/` (committed) or
  `Data/work/experiments/<name>/` (gitignored). Never touch `Data/processed/`, `Data/loop/`,
  shared `Data/work/{...}`, `config/`, or `ledgers/`. New packages go in a per-experiment venv
  (`uv venv`), never into `venv/` (the nightly pipeline depends on it). Avoid long-held
  resources 06:00–08:30 PT (nightly window).
- **Any "signal works" claim must register a harness trial** in `config/family_registry.yaml`.
  Do not use `sweep_signals.py --force` for re-measurement (it duplicates registrations).
- **Conda/venv split for Bloomberg:** `collect_*_bbg.py` collectors run under the OpusBloomberg
  conda env and write parquet only; paired `load_*.py` scripts run in the project `venv` and
  rebuild loop tables idempotently. launchd's PATH has no `/opt/homebrew/bin` — invoke conda by
  absolute path.
- **Do not fix monthly-collector / T2-feed bugs without approval** — append to `docs/USER_FIX_LIST.md`.
- **Bloomberg ticker hygiene:** confirm each ticker's country (past bugs: `GSAB10YR` is South
  Africa's 10Y, not Saudi; dead EM `* Index` 2Y/5Y/10Y generics replaced by `GT<CCY>*Y Govt`).
- **Data conventions:** first-of-month dates; exact T2 country names (`Brazil`, `ChinaA`, `U.S.`);
  tidy/long panel schema `(date, country, value, variable, source)`; China → both ChinaA & ChinaH;
  United States → U.S., NASDAQ, US SmallCap.

## Current state (2026-07-06)

- **Very active.** Nightly loop + daily auto-commits run continuously. Warehouse healthy
  (`unified_panel` ~17.4M rows; `feature_panel` ~31.6M rows; DB ~3.6 GB, per docs).
- **Live:** the loop, the cockpit frontend (Edge Board / Consensus Matrix / Fable's Desk), the
  Triptych Prediction Prior Layer (context/prior tier only — its queue rule tested DEAD, correctly
  demoted), and the daily combiner (`combiner_scores_daily`, strongest registered signal but an
  in-sample-selected ceiling).
- **Recently died (as designed):** `regime/` global regime-factor test (0/52), `momentum_fragility`
  (failed walk-forward Gate 3), `regime_factor_selection` (0/74, placebo-confirmed null). These are
  untracked in git as of this review.
- **On hold:** Brier Gate prediction-market arm (awaiting Polymarket US access); DeepSeek shadow
  continues.
- **Known stale:** `llmchat.md` last entry 2026-07-02, ~20 commits behind — do not treat it as
  current state; use `git log` + `AGENTS.md`.
