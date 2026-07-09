---
name: asado-operations
description: >-
  The ASADO operational runbook — what runs when (launchd daily rhythm), how to run every
  pipeline stage manually with its verified flags, how to check system health, how to run the
  test suite SAFELY, what CI exists, and how to launch the frontends and MCP server. Use this
  when you need to operate the ASADO factory: run/re-run a pipeline stage by hand, diagnose
  whether the nightly jobs are healthy, tail a log, run tests, or start a dashboard. Repo root
  is "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO" and THE MAIN CHECKOUT IS
  PRODUCTION — launchd runs from this tree. Do NOT use this skill to (a) triage a live failure
  that is already happening — go to asado-debugging-playbook FIRST; (b) design or gate a code
  change — go to asado-change-control; (c) run a research experiment through the harness — go
  to asado-research-protocol; (d) get oriented from zero — go to asado-start-here. This skill
  is the "how do I operate and check it" reference, not the "why" or the "should I".
---

# ASADO Operations Runbook

You are operating a **production** research factory. The main checkout at
`/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO` is what launchd runs every day.
Quote every path — the parent directory `AAA Backup` contains a space.

## HARD RULES (read before you touch anything)

1. **NEVER switch git branches in the main checkout.** launchd runs whatever is checked out
   here. For code experiments use `git worktree add "../ASADO-exp-<name>"`. (asado-change-control
   has the full worktree protocol.)
2. **NEVER hold an open DuckDB connection** — not even idle read-only — to
   `Data/asado.duckdb` or `Data/loop/asado_loop.duckdb`. DuckDB is one-writer/many-readers; a
   stray holder blocks the nightly writers and caused the 2026-07-02/03 pipeline failures. This
   is why the Streamlit frontend (which holds a cached connection) must never be left running
   overnight — see §6.
3. **NEVER run `python -m pytest tests/` bare** — it opens the production loop DB. Use the safe
   invocation in §4. Never run it 06:00–08:30 PT (the nightly quiet window).
4. **If you observe a live job failing, STOP** and go to `asado-debugging-playbook` before
   running fixes. Do not fix monthly-collector / T2-feed bugs yourself — append to
   `docs/USER_FIX_LIST.md` and report to the user (repo law: FAIL IS FAIL, no silent fixes).
5. **Health = output freshness, not exit code.** A job can exit 0 while producing a stale
   artifact (the same `brief_2026_06_16.md` was auto-committed 15× while the pipeline stayed
   "green"). Always check the *content date* of the latest brief/artifact, not just `launchctl list`.

Activate the environment for any manual run:

```bash
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO" && source venv/bin/activate
```

`venv` is Python **3.14.3** (`venv/pyvenv.cfg:1`). Note: it was bootstrapped from the
Country-Autoresearch venv (`pyvenv.cfg` `command =` line) — a provenance oddity, harmless.
`requirements.txt` pins 22 packages but does **NOT** declare `pytest` or `streamlit`, both of
which are installed and required for §4/§6.

---

## 1. Daily rhythm (what runs when)

All times are **local Mac time (PT)**. Source of truth is the **loaded launchd state**, read
with `launchctl print gui/$(id -u)/<label>` — NOT the on-disk plist. The installed files in
`~/Library/LaunchAgents/com.arjundivecha.*.plist` contain only a `ProgramArguments` JSON array;
the schedule, log paths, and PATH live in the loaded domain state.

> **The 2 plists in the repo root** (`./com.arjundivecha.asado-loop-heartbeat.plist`,
> `./com.arjundivecha.neo4j-guard.plist`) are **UNINSTALLED TEMPLATES** — do not edit them
> expecting a schedule change. The live jobs are the ones under `~/Library/LaunchAgents`.
> (House law: DEPLOYED != COMMITTED — the Neo4j guard once existed in-repo while prod stayed
> down because the plist was never installed. Always verify `launchctl` state, never assume.)

| Time (PT) | launchd label | Command (all under repo root) | Log (`Data/logs/…`) | Healthy = |
|---|---|---|---|---|
| Mon–Fri 07:30 | `com.arjundivecha.asado-daily` | `caffeinate -i scripts/run_asado_daily.sh` | `asado_daily_launchd.log` | exit 0; fresh `brief_<today>.md`; latest `daily_update_<today>_*.log` ends OK |
| daily 11:30 | `com.arjundivecha.asado-loop-daily` | `venv/bin/python scripts/loop/loop_daily_job.py` (safety net re-run of the loop) | `loop_daily_launchd.log` | exit 0 |
| daily 12:45 | `com.arjundivecha.asado-loop-heartbeat` | `venv/bin/python scripts/loop/heartbeat.py --watchdog` | `loop_heartbeat_launchd.log` | exit 0; no iMessage alert fired |
| login + every 30 min | `com.arjundivecha.neo4j-guard` | `/bin/bash scripts/ops/neo4j_guard.sh` | `neo4j_guard_launchd.log` | exit 0; bolt port 7687 up |
| daily 06:30 | `com.arjundivecha.asado-predmkt-daily` | `venv/bin/python scripts/predmkt_daily_job.py` | `predmkt_launchd.log` | exit 0 |
| daily 16:45 | `com.arjundivecha.asado-predmkt-equity-harvest` | `venv/bin/python scripts/predmkt_equity_daily_job.py` | `predmkt_equity_daily.log` | exit 0 (two-step job: universe discovery + history harvest; check the log for which step failed, not just the launchd exit code) |
| every 600 s | `com.arjundivecha.asado-predmkt-equity-poller` | `venv/bin/python scripts/poll_predmkt_intraday.py` | `predmkt_equity_poller.log` | exit 0; self-gates to UTC market windows, so a no-op between windows is normal |
| always-on service | `homebrew.mxcl.neo4j` | Homebrew-managed Neo4j | (Neo4j's own logs) | running with a PID in `launchctl list` |

**Cross-repo consumer (not an ASADO job — do not disable it thinking it's ours):**

| Time (PT) | launchd label | What it does |
|---|---|---|
| Mon–Fri 12:20 | `com.arjundivecha.fdt-decide` | `run_fdt_phase.sh decide` in `A Complete/Fable Daily Trading` — reads ASADO's **loop DB read-only**. There is **NO completion handshake**: it assumes the ASADO loop has finished by 12:20. If you re-run or delay the loop past 12:20, fdt-decide may read stale/partial loop state. |

`fdt-decide` is the one that matters to ASADO, but note there are **five** loaded `fdt-*`
jobs in total (`decide`, `desk`, `execute`, `reconcile`, `predmkt-shadow` — the last is the
DeepSeek/prediction-market shadow-forecasting arm). All belong to Fable Daily Trading, not
this repo; `launchctl list | grep fdt` shows them.

To see live status and last exit codes at a glance:

```bash
launchctl list | grep -Ei 'asado|neo4j|fdt'
```
Column 2 is the last exit code (`0` good, non-zero = last run failed; `-` = never run this boot).
To inspect one job's full loaded config (schedule, program, log paths):
```bash
launchctl print "gui/$(id -u)/com.arjundivecha.asado-daily"
```

### What the two shell orchestrators actually do
- `scripts/run_asado_daily.sh` (the 07:30 entry point): guards against a double-run; runs a
  **Bloomberg preflight** (auto-starts the Parallels "Windows 11" VM, tests the OpusBloomberg
  data path, retries every 20 min until an 11:00 deadline); if Bloomberg never comes up it sends
  an iMessage and **exits 1 with no `--skip-bloomberg` fallback** (FAIL IS FAIL); then runs
  `daily_update.py --resume` with **one** retry after a 25-min wait, iMessaging the log path on a
  second failure (`scripts/run_asado_daily.sh`, verified full read).
- `scripts/ops/neo4j_guard.sh`: if bolt port 7687 is up, no-op exit 0; otherwise waits a 30 s
  grace window, then `brew services stop neo4j`, deletes stale `neo4j.pid` files under
  `/opt/homebrew/Cellar/neo4j/*/libexec/run/`, `brew services start neo4j`, and polls up to 60 s.
  Exit 1 if still down (`scripts/ops/neo4j_guard.sh`, verified full read).

---

## 2. Manual run reference (verified flags)

Every flag below was verified against the script's argparse block (file:line cited). Runtimes
marked `(doc)` are from repo docs, not measured. Always `source venv/bin/activate` first.
The nightly loop = **47 steps** per `config/governance_contract.yaml` (canonical); the
`loop_daily_job.py` docstring saying 37 and `CLAUDE.md` saying ~33 are **both stale** — do not
trust the docstring count.

### Orchestrators

```bash
# MONTHLY warehouse refresh (~8-10 min doc; hits live APIs + full DuckDB rebuild)
# argparse: scripts/monthly_update.py:468 . Exit: 0 ok / 1 a step failed (runs to end) /
#   2 = aborted at the --skip-bloomberg stale-master freshness gate.
python scripts/monthly_update.py
#   --skip-neo4j --skip-bloomberg --skip-gdelt-fetch --skip-wb-commodity --skip-ff
#   --commodity-only --collectors-only --db-only --dry-run
#   --skip-deep   (DEPRECATED no-op, still accepted; monthly_update.py:476)

# DAILY orchestrator (T2 Bloomberg pull -> DB -> Neo4j -> the loop LAST, 7200s timeout).
# argparse: scripts/daily_update.py:158 . Checkpointed --resume.
python scripts/daily_update.py --resume
#   --skip-bloomberg --skip-gdelt --skip-neo4j --skip-db --skip-loop --t2-only

# The nightly LOOP alone (Layer-1 dislocation engine, 47 steps).
# argparse: scripts/loop/loop_daily_job.py:400 — ONLY flag is --only.
python scripts/loop/loop_daily_job.py               # full run
python scripts/loop/loop_daily_job.py --only <step> # run a single named step
#   Env: ASADO_SKIP_FABLE=1 skips the LLM step (avoids Anthropic spend).
```

### Warehouse builders (no network unless noted)

```bash
# DELETES + recreates Data/asado.duckdb from panels. argparse: scripts/setup_duckdb.py:1101
python scripts/setup_duckdb.py            # rebuild (default, no flag)
python scripts/setup_duckdb.py --check    # inspect existing DB, do NOT rebuild

# normalized_panel + feature_panel / feature_panel_t2 views. argparse: build_normalized_panel.py:477
python scripts/build_normalized_panel.py
python scripts/build_normalized_panel.py --check

# Daily extension tables + variable_meta. argparse: scripts/build_daily_panels.py:823
python scripts/build_daily_panels.py
python scripts/build_daily_panels.py --check       # report tables, exit
#   --rebuild (drop+rebuild even if present) | --skip-levels (skip slow T2MasterDaily.xlsx parse)
#   --validate (daily-EOM vs monthly compare) | --no-backup (skip ~800MB DB backup)

# Neo4j graph. argparse: scripts/setup_neo4j.py:1359
python scripts/setup_neo4j.py
python scripts/setup_neo4j.py --check              # verify graph
#   --skip-crisis-events

# Embeddings into Neo4j vectors. argparse: scripts/build_embeddings.py:235
python scripts/build_embeddings.py
#   --dims <int> (default 128) | --no-pca

# T2 master (monthly). argparse: scripts/build_t2_master.py:487
python scripts/build_t2_master.py
#   --skip-p2p --dry-run --check --force --check-freshness
# T2 master (daily analog). argparse: scripts/build_t2_master_daily.py:220
python scripts/build_t2_master_daily.py            # --bloomberg <path> --p2p <path> --out <path>
```

### Collectors

```bash
# argparse: scripts/collect_bilateral.py:711
python scripts/collect_bilateral.py                # --trade-only --bank-only --portfolio-only --skip-portfolio
# argparse: scripts/collect_wb_commodity_prices.py:862
python scripts/collect_wb_commodity_prices.py --check   # --force --dry-run --allow-stale --url <u>
# Other collectors (existence-verified; see CLAUDE.md "Commands that work"):
python scripts/collect_external.py     # EPU/GPR/BIS/OECD/WB/REER   (--force --dry-run)
python scripts/collect_extended.py     # rates, BCI/CCI, ECB FX, ND-GAIN, ILOSTAT
python scripts/collect_imf.py          # CPI/WEO/BOP/rates/FX/labor/trade
python scripts/collect_macrostructure.py
python scripts/collect_ff_factors.py   # NOTE: scripts/, not scripts/loop/
```

### Bloomberg collectors — different environment

Bloomberg-touching collectors (`scripts/collect_bloomberg.py`, `scripts/collect_t2_bloomberg.py`,
`scripts/loop/collect_*_bbg.py`) run under the **OpusBloomberg conda env**, NOT `venv`, and
require the Parallels Windows VM + Terminal logged in:

```bash
conda run -p "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv" \
  python scripts/collect_bloomberg.py
```
For connection mechanics, ticker hygiene, BLPAPI/BQL debugging, and the daily API cap, use the
**global `bloomberg-skill`** — do not re-derive connection steps here. The paired `load_*.py`
loaders run in the project `venv` and rebuild loop tables idempotently.

### Freeze data before experimenting
Never snapshot by holding a connection. Freeze live tables to parquet first:
```bash
python scripts/snapshot_for_experiment.py          # NOTE: scripts/, not scripts/loop/
```

---

## 3. Health checks (exact command → expected-good shape)

**launchd job status** — column 2 is last exit code:
```bash
launchctl list | grep -Ei 'asado|neo4j|fdt'
```
Good: every ASADO label shows `0` in col 2 (or `-` if not yet run this boot). A non-zero
exit is a real signal, not something to explain away as "probably a known issue" — go
read that job's log (this table's Log column) before deciding whether it's transient
(e.g. a network blip) or a real regression. Don't assume any specific job is "known
broken" based on a past snapshot in this or any other doc — check its actual current
log.

**Neo4j is up** (two independent checks):
```bash
brew services list | grep neo4j        # good: "neo4j   started"
launchctl list | grep homebrew.mxcl.neo4j   # good: a numeric PID in col 1
```

**Latest nightly brief freshness** (the real health signal — see Hard Rule 5):
```bash
ls -t "Data/dislocations/"brief_*.md | head -1
```
Good: the newest brief's date (in its filename) matches the most recent weekday. If the
newest brief is several days stale while jobs show exit 0, that is the "green-but-stale"
failure — go to `asado-debugging-playbook`.

**Daily run log + progress file:**
```bash
ls -t "Data/logs/"daily_update_*.log | head -1        # tail it; good ending: "completed OK"
ls -t "Data/logs/"daily_update_progress_*.json | head -1   # per-run heartbeat/progress file
```

**Loop heartbeat** (written by `heartbeat.py`):
```bash
cat "Data/loop/governance/heartbeat.json"
```
Good: recent timestamp, healthy status, exit_code 0.

**run_history** (last runs summary):
```bash
cat "Data/processed/run_history.json"
```

**`--check` health flags** (verify state without mutating — safe to run any time):
```bash
python scripts/setup_duckdb.py --check
python scripts/setup_neo4j.py --check
python scripts/build_daily_panels.py --check
python scripts/build_normalized_panel.py --check
python scripts/collect_wb_commodity_prices.py --check
python scripts/predmkt_daily_job.py --check         # reports DB vs archive state (argparse :187)
```
Each prints a table/summary of existing artifacts and exits without rebuilding.

**Tail a specific launchd log:**
```bash
tail -n 60 "Data/logs/asado_daily_launchd.log"
tail -n 60 "Data/logs/predmkt_equity_daily.log"     # the currently-failing job
```

---

## 4. Tests (and the ONE way to run them safely)

`tests/` contains three groups:
- `tests/discovery_triage/` — 20 test files (cockpit/triage/harness-bridge), isolated (in-memory / tmp).
- `tests/loop/` — 12 test files (harness, ledger, PIT lag, governance, gap engine…).
- `tests/test_gdelt_daily_parquet.py` — one loose file.

> ⚠️ **CRITICAL HAZARD.** `tests/loop/test_gap_engine.py:140-145`
> (`test_live_gap_engine_tables_if_present`) opens the **PRODUCTION loop DB**
> `Data/loop/asado_loop.duckdb` read-only if it exists. A bare
> `python -m pytest tests/` therefore touches production and can contend with a running nightly
> writer. **Never** run the bare suite during **06:00–08:30 PT**.

**Safe invocation** — deselect that one live-DB test (self-contained; run outside
06:00–08:30 PT):
```bash
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO" && source venv/bin/activate
python -m pytest tests/ \
  --deselect tests/loop/test_gap_engine.py::test_live_gap_engine_tables_if_present
```
All other collected tests use `:memory:` / `tmp_path` and are safe.

Note: `tests/loop/test_daily_pipeline.py` is a **standalone script** with its own argparse
`main()` — pytest collects **0** tests from it. Do not expect it to run under pytest; invoke it
directly only if you know what it does.

There is **no** coverage gate and **no** test CI (see §5), so a green local suite is the only
automated signal you get — treat it accordingly.

---

## 5. CI — set expectations low

The **only** GitHub Actions workflow is `.github/workflows/openwiki-update.yml`: a docs updater
that runs on `workflow_dispatch` and cron `0 8 * * *` (**08:00 UTC daily**). It installs the
`openwiki` npm package, runs `openwiki --update --print --modelId z-ai/glm-5.2` (needs the
`OPENROUTER_API_KEY` secret), and auto-commits changes under `openwiki/` back to the branch.

There is **NO test CI, NO lint CI, NO pipeline CI.** Nothing verifies code or data on push.
Correctness is enforced only by (a) the local test suite you choose to run and (b) the nightly
loop's own fail-soft checks. Do not assume a merge was validated by CI — it was not.

---

## 6. Frontends & MCP server

Three independent frontends plus the MCP server. Ports below are verified.

**Streamlit dashboard** (`frontend/app.py`, default port **8501**):
```bash
streamlit run frontend/app.py
```
⚠️ It holds a process-wide cached DuckDB connection (`get_db()` is `@st.cache_resource`,
`frontend/app.py:132`). Use it **briefly, then Ctrl-C to close it — NEVER leave it running
overnight**, or it will block the nightly writers (see Hard Rule 2). `streamlit` is installed but
not in `requirements.txt`.

**Perspective Lab** (`frontend/perspective_lab/`, Vite — dev **5174**, preview **5175**):
```bash
cd "frontend/perspective_lab" && npm install && npm run dev
```

**Discovery Triage cockpit** (`scripts/run_discovery_cockpit.sh`, port **8800**):
```bash
./scripts/run_discovery_cockpit.sh --serve-only   # serve existing cockpit, NO Anthropic spend
./scripts/run_discovery_cockpit.sh                # rebuilds via daily_docket -> LIVE LLM SPEND
```
Default (no `--serve-only`) runs `daily_docket` + `forward_track`, which call Anthropic and cost
money; `--serve-only` skips those and just rebuilds+serves from the existing journal
(`scripts/run_discovery_cockpit.sh`, verified full read). Override the port with `PORT=…`.

**MCP server** (`scripts/asado_mcp_server.py`) — stdio server for Claude Desktop ("use ASADO").
Its `run_duckdb_sql` / `run_neo4j_cypher` tools are validated read-only. **Three tools MUTATE
ledgers/DB** and must not be invoked casually:
- `register_hypothesis` → appends to `ledgers/hypothesis_ledger.jsonl`.
- `evaluate_signal` → writes a harness result JSON + `harness_results` rows in the loop DB, and
  attaches a verdict back to the hypothesis ledger.
- `open_thesis` → appends to `ledgers/thesis_ledger.jsonl`.

Ledger and harness writes are governed by `asado-research-protocol` — do not fire these tools
outside that lifecycle.

---

## 7. Environment facts (quick reference)

- **venv**: Python 3.14.3 at `.../ASADO/venv` (`pyvenv.cfg:1`). Activate before any manual run.
- **requirements.txt**: 22 pins; **does NOT list `pytest` or `streamlit`** (both installed,
  both required for §4/§6). If you rebuild the venv, reinstall them by hand.
- **Bloomberg env**: OpusBloomberg conda env at
  `"/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv"` — invoke by absolute
  path (launchd PATH has no `/opt/homebrew/bin`).
- **.env / keys**: `/Users/arjundivecha/Dropbox/AAA Backup/.env.txt` (FRED/EIA/ANTHROPIC/OPENROUTER).
  Never hardcode or commit keys.
- **Neo4j**: `bolt://localhost:7687` (`neo4j` / `mythos2026`); browser UI `http://localhost:7474`.
- **Two live DBs, both one-writer**: `Data/asado.duckdb` (~3.4–3.6 GB, DELETED+recreated by
  every `setup_duckdb.py` rebuild) and `Data/loop/asado_loop.duckdb` (durable). Never hold a
  connection to either.
- **Logs live in** `Data/logs/`; nightly briefs in `Data/dislocations/`; ledgers in `ledgers/`.

---

## When NOT to use this skill

A runbook applied to the wrong situation is worse than none. Route elsewhere when:

- **Something is broken right now** (job failed, brief stale, DB locked, a `--check` reports
  bad state) → `asado-debugging-playbook` FIRST. This skill tells you how to *run and check*, not
  how to *diagnose a failure*.
- **You want to change pipeline code / schedules / plists** → `asado-change-control` (worktree
  rules, change classification, the house laws with their incidents). Never edit the main
  checkout or a plist ad hoc.
- **You want to test whether a signal works** (register a hypothesis, run the harness, read a
  verdict) → `asado-research-protocol`. The MCP mutating tools in §6 belong to that lifecycle.
- **You are new here and need orientation / doc authority** → `asado-start-here`.
- **You need the architecture / data contracts / weak points** → `asado-architecture-contract`.

If a command here fails or an artifact looks stale, do NOT improvise a fix — STOP and report to
the user (FAIL IS FAIL; monthly-collector / T2-feed bugs go to `docs/USER_FIX_LIST.md`, not into
an unauthorized patch).
