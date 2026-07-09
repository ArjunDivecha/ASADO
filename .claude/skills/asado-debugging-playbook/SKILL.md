---
name: asado-debugging-playbook
description: >
  Symptom-to-triage runbook for the ASADO daily/monthly pipeline's REAL failure
  modes, each with the incident that produced it. Use this when something is
  broken or looks wrong: the nightly pipeline failed or a launchd job errored, a
  DuckDB "Conflicting lock" appears, Neo4j / graph steps are down, the dislocation
  brief is stale while everything looks green, a launchd job silently isn't
  running, the Bloomberg pull is hanging or failing, GDELT is rate-limiting, a
  loop/detector step crashed, or you suspect silent data corruption (wrong
  ticker/country). It routes each symptom to the exact log to open, the exact
  command to run, and the expected output, and it restates the hard STOP rules so
  a zero-context session cannot make production worse. Do NOT use this to DESIGN a
  change (use asado-change-control), to answer a research/experiment question (use
  asado-research-protocol), to check whether an idea is already dead (use
  asado-graveyard), or for routine operation/health checks with nothing broken
  (use asado-operations). For any fix that touches the monthly collectors or the
  T2/Bloomberg feed, STOP — that needs the user's approval, never a silent fix.
---

# ASADO Debugging Playbook

You are triaging a live production system. **The main checkout at
`/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO` IS production** — launchd
runs directly from this tree. Never `git checkout`/`git switch` a branch here, never
"just try" a fix on the monthly collectors or the T2/Bloomberg feed, and never open
either `.duckdb` file with a long-lived connection while diagnosing (an idle read-only
handle is itself a failure mode — see Symptom 2).

Quote every path — they contain spaces. All paths below are absolute.

## Two laws that override any fix you are tempted to make

1. **FAIL IS FAIL.** No silent fallback, no simulated success. If a step failed,
   report it failed with the real error. If a fix would touch a **monthly collector,
   `setup_duckdb.py` rebuild, or any T2/Bloomberg feed**, STOP and ask the user —
   the repo convention is to *append the bug to `docs/USER_FIX_LIST.md`*, not fix it
   (`AGENTS.md` / repo CLAUDE.md: "Do not fix monthly-collector / T2-feed bugs
   without approval").
2. **Exit code 0 ≠ healthy.** This pipeline is fail-soft by design; green means "the
   process finished," not "the output is fresh and correct." Always confirm the
   *artifact* (Symptom 4), not just the exit code.

## Triage table (symptom → jump)

| Symptom you observe | First move | Section |
|---|---|---|
| Nightly pipeline failed / no brief this morning | Read `asado_daily_launchd.log` then `asado_daily_runner.log` | [1](#s1) |
| `IOException ... Conflicting lock is held in ... (PID n)` | Read the guard's culprit line; identify holder before killing | [2](#s2) |
| Neo4j down / graph steps failing / `bolt` refused | Read `neo4j_guard.log`; check bolt 7687 | [3](#s3) |
| Everything green but brief looks days old | `ls Data/dislocations/`; compare date-in-filename to today | [4](#s4) |
| A launchd job isn't running at all | `launchctl list | grep asado`; check PATH/conda | [5](#s5) |
| Bloomberg pull hanging / never ready | Read runner log; check Parallels VM + preflight | [6](#s6) |
| GDELT rate-limited / evidence packs partial | Do NOT retry-loop; understand cooldown-resets-on-probe | [7](#s7) |
| A single loop/detector step crashed | Re-run just that step with `--only`; read PARTIAL vs FAIL | [8](#s8) |
| Numbers look wrong / suspected corruption | Verify ticker↔country; report, don't fix | [9](#s9) |
| — | Known live issues as of 2026-07-08 | [10](#s10) |

---

## The launchd jobs and their logs (verified 2026-07-08)

Seven ASADO jobs plus Homebrew Neo4j are installed. Confirmed loaded via
`launchctl list` (second column = last exit code):

| launchd label | When | Runs | Its log file (in `Data/logs/`) |
|---|---|---|---|
| `com.arjundivecha.asado-daily` | weekdays 07:30 | `caffeinate -i scripts/run_asado_daily.sh` | `asado_daily_launchd.log` (launchd stdout) + `asado_daily_runner.log` (runner's own log) |
| `com.arjundivecha.asado-loop-daily` | daily 11:30 | `venv/bin/python scripts/loop/loop_daily_job.py` (safety net) | `loop_daily_launchd.log` |
| `com.arjundivecha.asado-loop-heartbeat` | daily 12:45 | `scripts/loop/heartbeat.py --watchdog` | `loop_heartbeat_launchd.log` |
| `com.arjundivecha.neo4j-guard` | login + every 30 min | `scripts/ops/neo4j_guard.sh` | `neo4j_guard_launchd.log` (0-byte wrapper) + `neo4j_guard.log` (guard's own log) |
| `com.arjundivecha.asado-predmkt-daily` | 06:30 | `scripts/predmkt_daily_job.py` | `predmkt_launchd.log` |
| `com.arjundivecha.asado-predmkt-equity-harvest` | 16:45 | `scripts/predmkt_equity_daily_job.py` | `predmkt_equity_daily.log` |
| `com.arjundivecha.asado-predmkt-equity-poller` | every 600 s | `scripts/poll_predmkt_intraday.py` | `predmkt_equity_poller.log` |

All log paths above are the files that **actually exist** in
`/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/logs/` (verified by `ls`),
and they match the log-path constants inside the runner and guard scripts
(`run_asado_daily.sh:52`, `neo4j_guard.sh:52`).

> **UNVERIFIED / gotcha:** In this repo snapshot the files in `~/Library/LaunchAgents/`
> are stripped to a bare JSON array of just the `ProgramArguments` (e.g.
> `com.arjundivecha.asado-daily.plist` is 123 bytes and has **no** `StandardOutPath`
> key), so `plutil -extract StandardOutPath raw <plist>` **fails**. Do not trust a
> plist file on disk to tell you the log path here. The authoritative sources are (a)
> the actual files in `Data/logs/`, and (b) `launchctl print gui/$(id -u)/<label>`.
> The **repo-root** `*.plist` files are TEMPLATES and are NOT what launchd loaded
> (build-tracer finding). Ground truth for "is it installed / what was its exit code"
> is always `launchctl`, never a plist file.

Quick health snapshot:

```bash
launchctl list | grep -E 'asado|neo4j'
# col 1 = PID (- if not running now), col 2 = last exit code, col 3 = label
```

---

<a id="s1"></a>
## 1. Nightly pipeline failed / no brief this morning

**What runs and in what order.** `com.arjundivecha.asado-daily` (07:30 weekdays) →
`scripts/run_asado_daily.sh` → `scripts/daily_update.py --resume` → `daily_update.py`
runs the loop (`scripts/loop/loop_daily_job.py`) as its LAST stage. Separately,
`com.arjundivecha.asado-loop-daily` re-runs the loop at 11:30 as a safety net, and the
heartbeat watchdog runs at 12:45.

**Read the logs in this order — outer to inner:**

```bash
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
tail -50 "Data/logs/asado_daily_launchd.log"     # launchd-level: did the job even fire?
tail -80 "Data/logs/asado_daily_runner.log"      # runner decisions: preflight, retries, alerts
ls -t Data/logs/daily_update_2*.log | head -1    # newest per-run pipeline log
```

The runner writes a per-run pipeline log at
`Data/logs/daily_update_YYYY_MM_DD_HHMMSS.log` and a resume checkpoint at
`Data/logs/daily_update_progress_YYYY_MM_DD.json` (`daily_update.py:171-172`). A clean
abort inside the pipeline is stamped `ABORTED at <stage>`; the runner greps that line
to build its iMessage alert (`run_asado_daily.sh:155-157`).

**Distinguish the three failure classes:**

- **Bloomberg preflight never passed** → the runner log ends with
  `"Bloomberg still not ready at deadline"` and `"Aborting: Bloomberg unavailable"`,
  and there is **no** `daily_update_*.log` for today. The pipeline deliberately did NOT
  run on stale prices (`run_asado_daily.sh:129-136`). Go to [Symptom 6](#s6).
- **A pipeline/loop step failed** → today's `daily_update_*.log` exists and contains
  `ABORTED at <stage>` (pipeline stage) or a `!!! STEP FAILED: <name>` line (loop
  step). Go to [Symptom 8](#s8).
- **DuckDB lock** → any log contains `Conflicting lock is held in ... (PID n)` or
  `Could not set lock`. Go to [Symptom 2](#s2).

**Note on the 07:30 vs 11:30 pair:** the loop takes a non-blocking singleton flock
(`Data/loop/.loop_daily.lock`, `loop_daily_job.py:175-190`). If the 07:30 chained run
is still going at 11:30, the 11:30 safety net prints `"Another full loop run is in
progress — skipping"` and exits 0 (`loop_daily_job.py:415-417`). That is normal, not a
failure.

---

<a id="s2"></a>
## 2. DuckDB lock error — `Conflicting lock is held in ... (PID n)`

DuckDB is one-writer / many-readers on a single file. **A single stray process holding
either DB — even an idle read-only handle — blocks every nightly writer.** In practice
the squatters are Claude Desktop analysis-sandbox kernels under `~/.claude-science/`
that open `Data/asado.duckdb` and never close it. This is exactly what killed the
nightly daily-panels build AND the predmkt job on **2026-07-02 and 2026-07-03**
(`scripts/duckdb_lock_guard.py:22-24`; guard wired in commit `fc1e0d2`, 2026-07-03).

**The guard's behaviour** (`guarded_connect()`, `scripts/duckdb_lock_guard.py:206`),
which wraps the ~11 core builders:

1. On a lock error it parses the culprit from DuckDB's own message with the regex
   `Conflicting lock is held in (.+?) \(PID (\d+)\)` (`:93`). That gives it
   `(exe_path, PID)`.
2. It kills the holder **only if** the holder's path/command matches a killable pattern
   (default: the single substring `.claude-science`, `:84`) **AND** `lsof` confirms that
   exact PID still holds the DB file open (`:245-253`, the guard against PID reuse). It
   never kills its own process/parent, and clears at most `MAX_KILLS = 5` stacked
   read-only squatters per call (`:88`).
3. If the holder is **not** killable (e.g. a legitimate overlapping ASADO job like a
   monthly `setup_duckdb` rebuild), it waits with backoff up to the budget (default
   **300 s**, `:90`), then raises a loud `RuntimeError` naming the holder.

**How to read the guard's messages** in the log:

- `LOCK GUARD: ... is locked by killable squatter PID n (...)` then `killing lock
  squatter PID n` → it self-healed; no action needed.
- `LOCK GUARD: ... locked by non-killable PID n (...) — waiting` → it is waiting out a
  process it won't kill. Find out what PID `n` is: `ps -o command= -p <n>`.
- `RuntimeError: Database ... is still locked by PID n (<exe>) after 300s` → it gave up
  loudly (`:277-284`). Now you decide.

**Decide: add a killable pattern, or wait.**

- If PID `n` is a **stray sandbox / notebook / editor** kernel (not an ASADO pipeline
  process), it is safe to let the guard clear it. Add its path substring to the killable
  set for the next run via env, e.g.:
  ```bash
  ASADO_LOCK_GUARD_KILLABLE=".claude-science,jupyter" \
    "/Users/.../ASADO/venv/bin/python" scripts/daily_update.py --resume
  ```
- If PID `n` is a **real ASADO job** (another `daily_update`, `setup_duckdb`,
  `monthly_update`), do NOT kill it. Let it finish and re-run.

**Env knobs** (`scripts/duckdb_lock_guard.py:41-44`):

- `ASADO_LOCK_GUARD_KILL=0` — disable killing entirely (wait-only). Use when unsure.
- `ASADO_LOCK_GUARD_KILLABLE=a,b,c` — replace the killable substring list.
- `ASADO_LOCK_GUARD_WAIT_S=600` — extend the wait budget past 300 s.

**Two UNGUARDED writers — a real hole to know about.** The guard wraps the daily/core
builders, but the two **monthly** GDELT-deep writers do NOT use `guarded_connect()` and
will raise a raw DuckDB lock exception with no self-heal:
`scripts/load_gdelt_deep_to_duckdb.py:126` and `scripts/build_gdelt_deep_cs.py:142`
(monthly steps ~10-13). If a monthly run dies on a lock at one of those, that is why.
**Fixing those touches the monthly pipeline → approval required (append to
`docs/USER_FIX_LIST.md`).** Also unguarded (reads, generally harmless but can be the
squatter themselves): `db_bridge.py`, the MCP server, the Streamlit frontend.

---

<a id="s3"></a>
## 3. Neo4j down / graph steps failing

Neo4j runs under Homebrew launchd (`homebrew.mxcl.neo4j`, `neo4j console`) at
`bolt://localhost:7687` (UI `http://localhost:7474`). The self-healing guard is
`scripts/ops/neo4j_guard.sh` (login + every 30 min).

**The recurring failure (the "stale pidfile" story):** after a hard crash / power loss,
Neo4j never deletes its PID file; the OS recycles that PID to something unrelated; on
next boot `neo4j console` sees "Neo4j is already running (pid:NNN)" and refuses to start.
`RunAtLoad` alone can't fix it because the failure is *inside* the start command. A
pidfile guard existed in-repo (commit `69174a1`) **but its plist was never installed**,
so Neo4j failed again on 2026-06-20 (`f6651c0`) — a textbook "deployed ≠ committed" trap.
The guard now installed does: probe bolt 7687 (`neo4j_guard.sh:59`) → if down, wait a
~30 s grace for a legit startup (`:70-76`) → `brew services stop neo4j` (`:84`) → delete
every stale PID file at `/opt/homebrew/Cellar/neo4j/*/libexec/run/neo4j.pid` (`:92-95`)
→ `brew services start neo4j` and poll 60 s (`:100-108`). Exit 0 = healthy/recovered,
exit 1 = still down after restart (`:44`).

**Triage:**

```bash
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
nc -z -G 2 localhost 7687 && echo "bolt UP" || echo "bolt DOWN"
tail -40 "Data/logs/neo4j_guard.log"      # what the guard checked/cleared/recovered
brew services list | grep neo4j
```

- Guard log ends `RECOVERED: bolt 7687 open` → healthy; if a loop graph step still failed
  it was a transient it has since fixed. Re-run just that step ([Symptom 8](#s8)).
- Guard log ends `FAILED: bolt 7687 still down ~60s after restart — manual attention
  needed` → Neo4j genuinely won't start. This is an infra problem, not a code bug; do
  NOT edit pipeline code. Inspect the Neo4j server log and surface it to the user.

**CRITICAL — "graph ran" ≠ "graph fresh".** `scripts/build_graph_features.py:127-156`
does a socket probe and, if Neo4j is unreachable, **falls back to the last PIT graph
snapshot** and continues. So a green loop with Neo4j down can silently ship *stale* graph
features. The coupling is intentionally soft (`monthly_update.py:1069-1099`,
`daily_update.py:214-215`), but it means: if graph-derived numbers look stale, check bolt
7687 was actually up *at run time*, not just now. Also note the 128-d PCA state embeddings
live **only** in Neo4j (`Country.state_embedding`) — if Neo4j was rebuilt, embeddings must
be rebuilt too.

Credentials (from repo CLAUDE.md): `neo4j` / `mythos2026`.

---

<a id="s4"></a>
## 4. Stale artifacts while everything is green

**This is the most dangerous failure mode because nothing errors.** The scar: the
identical `brief_2026_06_16.md` was auto-committed **15 times over 3 days** while the
pipeline reported green (commits `ce01ea4..251a63f`); the loop had silently degraded and
the brief was frozen, and nobody noticed because exit codes stayed 0.

**Check brief freshness directly — never trust the exit code here:**

```bash
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
ls -lt Data/dislocations/brief_*.md | head -5
```

The date is in the **filename** (`brief_YYYY_MM_DD.md`) and inside the file. On a healthy
weekday the newest brief's date should be the last trading day. If the newest brief is
days old while the loop "ran," the loop is degraded — go to [Symptom 8](#s8) to find which
step stopped producing.

**The automated watchdog for exactly this** is `scripts/loop/heartbeat.py --watchdog`
(the 12:45 job). It reads `Data/loop/governance/heartbeat.json`
(`heartbeat.py:60`) and alerts if that heartbeat is missing or older than
`WATCHDOG_STALE_HOURS = 2` (`heartbeat.py:63,161-177`). `compute_health()` also flags a
missing OR *uncommitted* brief and any fail/stale manifest steps (`heartbeat.py:102-143`).
To check health by hand:

```bash
tail -20 "Data/logs/loop_heartbeat_launchd.log"
cat "Data/loop/governance/heartbeat.json"     # brief_path, brief_committed, fail/stale steps
```

> Benign look-alike: on a normal day the brief is auto-committed roughly twice (morning
> regen + midday regen) with different timestamps — that is NOT a stuck loop
> (git-archaeologist finding). A stuck loop is the *same date* re-committed across
> multiple *days*.

---

<a id="s5"></a>
## 5. A launchd job isn't running / `conda: command not found`

**First, is it even installed and what was its last exit?**

```bash
launchctl list | grep -E 'asado|neo4j'
```

If a job is missing from this list, it is **not installed** — the `*.plist` files in the
**repo root are templates, not the installed jobs** (build-tracer finding). Do not assume
"the plist is in the repo" means "the job is scheduled." Ground truth is `launchctl`.

**The classic PATH gotcha:** launchd's environment does **not** include
`/opt/homebrew/bin`, so a bare `conda` invocation fails with `command not found`. The
scripts already defend against this by invoking conda / python by **absolute path** —
if you write or edit any launchd-invoked script, keep that pattern:

- `scripts/run_asado_daily.sh:61` sets an explicit `PATH` including `/opt/homebrew/bin`.
- Absolute conda/venv fallbacks live at `loop_daily_job.py:160-164`,
  `daily_update.py:96-98`, `run_asado_daily.sh:61`.

To see a job's full loaded definition (including its real stdout/stderr paths, which the
stripped plist files won't tell you):

```bash
launchctl print "gui/$(id -u)/com.arjundivecha.asado-daily"
```

If the installed job and the repo template disagree, the **installed** one is what runs.
Reconciling them is a change → see `asado-change-control` before editing.

---

<a id="s6"></a>
## 6. Bloomberg pull failing / hanging

Bloomberg data comes through a Parallels "Windows 11" VM running the Bloomberg Terminal;
the Mac reaches it via the OpusBloomberg conda env. The daily runner has a **preflight
loop** before it will run the pipeline (`run_asado_daily.sh:90-126`):

1. Ensure the Parallels "Windows 11" VM is running; auto-start it if not (`:92-96`).
2. Run a real `bloomberg_setup()` data-path test in the OpusBloomberg env (`:101-110`).
3. If not ready: send **one** iMessage, then retry every 20 min
   (`RETRY_WAIT=1200`) **until the 11:00 wall-clock deadline** (`DEADLINE_HOUR=11`).
   There is **no attempt cap** — it is bounded by wall-clock, not tries.
4. If still not ready at 11:00 → send a failure iMessage and **exit 1**. It deliberately
   does NOT fall back to `--skip-bloomberg` (that would build today's factors on stale
   prices — FAIL IS FAIL, `:129-136`).

**Triage:**

```bash
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
grep -E 'Bloomberg|Parallels|preflight|deadline' "Data/logs/asado_daily_runner.log" | tail -20
prlctl list | grep -i 'windows 11'          # is the VM running?
tail -20 "Data/work/loop/bbg_quota_log.csv" # daily API quota usage
```

- Runner log shows repeated `Bloomberg preflight failed — retrying` then `not ready at
  deadline` → the Terminal wasn't up/logged in on the VM. This is an environment issue,
  not a code bug: the user must open/log into Bloomberg Terminal, then
  `python scripts/daily_update.py --resume`.
- **Hang** (a pull that never returns): historically a wedged Bloomberg subprocess could
  hang indefinitely; `scripts/loop/procutil.py` `run_bounded()` (`:14-24,89-119`) now
  wall-clock-bounds subprocesses so a hang surfaces instead of stalling the loop. If a
  step is hung, check whether it goes through `run_bounded`.
- Note the one **pipeline** retry inside the runner waits `PIPELINE_RETRY_WAIT = 1500`
  (**25 min**), deliberately longer than GDELT's 15-min cooldown (`:56-59`). The runner
  docstring saying "retry ... after 10 minutes" (`:23`) is **stale** — trust the constant
  (25 min), not the comment.

**For anything deeper** (BLPAPI/BQL errors, ticker/field selection, connection internals,
quota limits): STOP here and use the global **`bloomberg-skill`**, which owns the
OpusBloomberg connection flow and the proven-ticker/field knowledge base. Do not
re-derive Bloomberg connection logic in this playbook.

---

<a id="s7"></a>
## 7. GDELT DOC API rate-limit / evidence packs partial

**The one hard rule: never retry-loop against GDELT.** GDELT's DOC 2.0 API rate-limits
per IP and its ~15-minute cooldown clock **resets on every request** — so a tight retry
guarantees you re-trip the limit forever. This is why the daily runner's single pipeline
retry waits 25 min, not 10 (`run_asado_daily.sh:56-59`), and why
`scripts/loop/build_evidence_packs.py` caps attempts and streams rather than hammering
(`:44,93,266`).

**Current exit semantics of `build_evidence_packs.py`** (updated 2026-06-11,
`:299-312`) — note this is NOT a blanket "abort non-zero":

- **exit 1** only when *every* pull failed and *nothing* was written
  (`n_failed and not n_packs and not n_skipped`).
- **exit 2 (PARTIAL)** when some countries are missing but others were written; they
  self-heal next run. The loop job records this as a warning, not a failure
  (`loop_daily_job.py:436-441`).
- **exit 0** when packs completed — including when GDELT was rate-limited but the step
  **failed over to the Gemini Search fallback** so no packs are missing (`:309-311`).
  A rate limit alone is therefore NOT a failure.

So: if you see `NOTE: GDELT was rate-limited; remaining packs completed via Gemini
Search fallback`, the step succeeded — do nothing. If you see PARTIAL (exit 2), let the
next nightly run self-heal it. **Do not add a manual retry loop.** (The Gemini fallback
needs its API key configured; a missing key can turn a rate-limit into a real failure —
check the log for the fallback line.)

---

<a id="s8"></a>
## 8. A single loop / detector step crashed

The nightly loop (`scripts/loop/loop_daily_job.py`) is **47 steps** (matches
`config/governance_contract.yaml`; the docstring saying ~33/37 is stale). It is
**fail-soft**: each step gets up to 2 attempts, exit 2 is PARTIAL, `optional:true` steps
never fail the job, and the job only returns exit 1 at the end if the *required*-failure
list is non-empty (`loop_daily_job.py:428-485`).

**Re-run just the failed step** (this skips the singleton lock — it is operator-driven,
`loop_daily_job.py:411-417`):

```bash
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO" && source venv/bin/activate
python scripts/loop/loop_daily_job.py --only <step_name>
# an unknown name prints the full list of valid step names and returns 2
```

**Read the per-step status lines** to know what actually happened
(`loop_daily_job.py:434-450`):

- `~~~ STEP PARTIAL: <name> (exit 2)` → kept its completed work, missing part self-heals
  next run. Warning, not failure.
- `~~~ OPTIONAL STEP FAILED: <name>` → an `optional:true` step (Bloomberg-down,
  Neo4j-down, GDELT-limited, etc.) failed; treated as a warning by design.
- `!!! STEP FAILED: <name> (exit n)` → a **required** step failed; this is what turns the
  job exit to 1. This is the one that needs real diagnosis.

`optional:true`/`false` come from `config/governance_contract.yaml` (`_load_optional_steps`,
`loop_daily_job.py:361-368`). **20 of 47** steps are `optional:false` (required); the
other 27 degrade gracefully.

**Known-fragile steps to suspect first (detectors).** `build_dislocations.py` runs
detectors D1–D5, D7–D10 (D6 is blocked on insufficient history; D8 is bookkeeping,
severity 0). The detector dispatch has **no top-level try/except**, and detectors D2, D5,
D7 have **zero internal error handling** (architect finding) — so a single bad row can
crash the whole required detector step and starve the 4 downstream readers of
`dislocation_daily`. If a required step crashed with a raw traceback, it is very often
one of D2/D5/D7. Read the traceback, identify the offending input, and **report it** —
do not paper over it with a bare `except`.

---

<a id="s9"></a>
## 9. Suspected silent data corruption (numbers look wrong)

The scar here is a **ticker↔country mismatch**: `GSAB10YR` was being treated as Saudi
Arabia's 10-year when it is in fact **South Africa's** 10Y; dead EM `* Index` 2Y/5Y/10Y
generics were silently wrong until replaced by `GT<CCY><n>Y Govt` (repo CLAUDE.md,
"Bloomberg ticker hygiene"). Bad tickers don't error — they return *a* number, just the
wrong country's.

**Habit when a country's series looks off:** verify the ticker actually maps to that
country before trusting the value. The Rosetta Stone is
`config/country_mapping.json` (34 T2 names → source codes). Cross-check the ticker's real
issuer/country against Bloomberg's `NAME`/description via the **`bloomberg-skill`** rather
than assuming the ticker string.

**USER_FIX_LIST protocol — report, don't fix.** If you find a suspected data-quality or
feed bug, especially in a **monthly collector or the T2/Bloomberg feed**: STOP. Do NOT
edit the collector. **Append a clear description to `docs/USER_FIX_LIST.md`** and tell the
user. This is a hard rule: only the user decides fixes to those feeds
(`AGENTS.md` / repo CLAUDE.md). Silently "correcting" a ticker could re-map a whole
history and is exactly the kind of change that must be reviewed.

Also useful: the returns-first / leakage QA check lives at
`scripts/qa/validate_returns_first.py` — country and factor returns are the source of
truth everything else must join back to.

---

<a id="s10"></a>
## 10. Known live issues as of 2026-07-08 (don't rediscover these)

- **`asado-predmkt-equity-harvest` last run failed (exit 1).** Confirmed via
  `launchctl list` (its last-exit column is `1`; all other ASADO jobs are `0`). It is a
  known, currently-unfixed live failure — investigate its log
  (`Data/logs/predmkt_equity_daily.log`) but don't be surprised it's red.
- **`regime/src/regime_tagger.py:70` mislabels Recession as "Crisis."** The R3 (Recession)
  branch appends `"R3_Recession"` but `return "Crisis", fired` (verified live on this
  checkout). A one-line fix exists only on the **unmerged** branch
  `origin/claude/nightwatch-06-20-failures-37d4lv` (commit `4825fa9`) — it is NOT on main.
  If you touch regime labels, know this bug is live.
- **`tests/loop/test_gap_engine.py:143-145`** (`test_live_gap_engine_tables_if_present`)
  opens the **real production loop DB** read-only. Running `python -m pytest tests/`
  therefore touches production — avoid it during the 06:00–08:30 PT nightly window
  (build-tracer finding).
- **Two UNGUARDED monthly writers** (`load_gdelt_deep_to_duckdb.py:126`,
  `build_gdelt_deep_cs.py:142`) — see [Symptom 2](#s2).
- **Untracked on disk** (not in git as of this handover): `ARJUN.md`, `FABLE.md`,
  `momentum_fragility/`, `regime_factor_selection/`. Don't assume they're versioned.

---

## When NOT to use this skill

- **Designing or classifying a change** (is this safe? what gate does it need?) →
  **`asado-change-control`**.
- **A research / experiment / harness question** (run a signal, read a verdict, register
  a family) → **`asado-research-protocol`**.
- **Checking whether an idea is already dead** before proposing it →
  **`asado-graveyard`**.
- **Routine operation with nothing broken** (schedules, manual runs, health checks,
  frontends, MCP) → **`asado-operations`**; orientation / doc-authority → **`asado-start-here`**.

## The STOP rule, restated (do not skip)

For **any** fix that touches a **monthly collector, `setup_duckdb.py`, or a
T2/Bloomberg feed**: STOP and get the user's approval. Append the issue to
`/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/docs/USER_FIX_LIST.md` and report
it — do not fix it yourself. FAIL IS FAIL: never mask a failure with a silent fallback or
a simulated success.
