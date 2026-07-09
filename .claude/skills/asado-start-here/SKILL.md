---
name: asado-start-here
description: >-
  The entry point for ANY zero-context session in the ASADO repo
  (/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO). Read this FIRST when
  you land in ASADO with no prior context and are unsure what the repo is, which
  doc to trust, what today's true state is, or which sibling skill to use. It
  gives you (1) the five hard safety rules that keep you from breaking
  production, (2) a doc-authority router that says which docs to trust vs which
  are stale, (3) how to reconstruct today's real state, and (4) a routing map to
  the seven sibling asado-* skills. Trigger phrases: "what is ASADO", "get me
  oriented in ASADO", "where do I start", "which doc is current", "is this
  pipeline safe to touch". Do NOT use when a specific sibling skill already
  matches your task (e.g. you already know you are debugging, operating,
  proposing research, or changing code) — route straight to that skill instead
  of reading everything here.
---

# ASADO — Start Here

You are (probably) a fresh Claude session with zero prior context, operating
autonomously inside a **live production quant-research system**. This skill
makes you safe and oriented in a few minutes. Read the safety rules in full
before you run anything that writes, deletes, or switches branches.

Repo root (quote the spaces): `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO`

## 1. What ASADO is

ASADO is an **alpha-research factory**: a nightly automated pipeline that
ingests market/macro/news data, builds a normalized factor warehouse, mines
candidate trading signals, and runs them through a falsification harness that is
deliberately hard to fool. Its core value is **trustworthy falsification** — the
system is built to kill bad ideas honestly (pre-registration gates, forward-
return bans, cost-and-deflation-adjusted verdicts) rather than to manufacture
passing backtests. The **main checkout is the production tree**: launchd
(macOS) runs the nightly jobs directly from it, so the repo you are standing in
is not a scratch copy — it is the running factory. Verdicts accumulate in
append-only ledgers, and a small set of docs (below) hold the current truth
while many older docs have gone stale.

**The one term you must know before anything else: "T2".** T2 is the in-house
34-country factor-timing universe/book that ASADO exists to serve. "T2 names" =
the 34 canonical country labels (source of truth:
`scripts/loop/loopdb.py::T2_UNIVERSE`; exact spellings like `Brazil`, `ChinaA`,
`U.S.`). "The T2 feed" = the monthly Bloomberg-sourced data feed that populates
it (never fix its bugs without approval — Rule 5). `feature_panel_t2` = the
34-country analysis view you should read instead of the 43-country
`feature_panel`. A glossary of the other house terms is in §6.

## 2. THE FIVE HARD SAFETY RULES (read before touching anything)

These are restated inline so you are safe after this section alone. If you
cannot follow one, **STOP and report to the user** rather than guessing.

**Rule 1 — The main checkout IS production. Never mutate the tree's branch or
untracked files.**
- Never `git checkout <branch>`, `git switch`, `git reset --hard`, `git stash`,
  or rebase in this checkout. launchd runs from HEAD of this tree; switching
  branches silently changes what runs tonight.
- Never `git clean -fd` / `git clean -fdx`. Load-bearing synthesis docs
  `ARJUN.md` and `FABLE.md` (both 2026-07-06) are **untracked** — verified via
  `git status --short` showing `?? ARJUN.md` / `?? FABLE.md`. A clean deletes
  them permanently.
- Do all experiments in an isolated worktree: `git worktree add <path> <branch>`.
  See **asado-change-control** and **asado-operations**.

**Rule 2 — Never hold a connection to either DuckDB. Both are one-writer.**
- Two live DBs: `Data/asado.duckdb` (~3.4–3.6 GB, the warehouse — it is DELETED
  and recreated on every rebuild by `scripts/setup_duckdb.py`) and
  `Data/loop/asado_loop.duckdb` (durable ledger/loop DB).
- Do NOT open a `.duckdb` file interactively (no `duckdb Data/asado.duckdb`, no
  long-lived read-only handle). Even an idle read-only connection can block the
  nightly writer. Core builders use `guarded_connect()` in
  `scripts/duckdb_lock_guard.py:206` (reactive retry, kills only
  `.claude-science` lock holders, 300s budget, fails loudly). Several paths are
  **unguarded** (db_bridge, MCP server, Streamlit frontend, two monthly GDELT
  writers) — do not add your own unguarded opener. To inspect data, prefer the
  read-only API layers described in **asado-operations**.

**Rule 3 — Stay in the sandbox; never run a destructive rebuild on production
without an explicit user go-ahead.**
- The repo's own permission allowlist (`.claude/settings.local.json`) only
  pre-approves `Bash(./venv/bin/python -c ' *)` — i.e. tiny read-only probes
  through the project venv. Anything beyond that needs a decision.
- `scripts/setup_duckdb.py` performs a FULL DESTRUCTIVE rebuild: it `unlink`s
  the ~3.4 GB warehouse and recreates every table (verified from architect trace
  of `setup_duckdb.py:1134-1138`). Never run it, `monthly_update.py`, or other
  mutating pipeline scripts on the production tree "to see what happens." Run
  exploratory work read-only or in a worktree with its own DB.

**Rule 4 — Respect the nightly quiet window: 06:00–08:30 PT.**
- The nightly loop and daily jobs run in the early morning (launchd:
  `asado-daily` weekdays 07:30, `asado-predmkt-daily` 06:30, `asado-loop-daily`
  11:30 safety net). Do not launch long-running or resource-heavy work, and
  above all do not hold DB resources, during 06:00–08:30 PT. If you must, ask
  first.

**Rule 5 — FAIL IS FAIL. No silent fallbacks, no simulated success.**
- If something fails, report the actual failure with its output. Never fake a
  pass, never swap in a fallback path to make a run "green," never claim
  something works untested. Health is measured by **output-content freshness**,
  not by exit code 0 (a brief once auto-committed 15× while silently stale — see
  **asado-debugging-playbook**).
- Do NOT auto-fix data-collector / T2-feed bugs. Append the issue to
  `docs/USER_FIX_LIST.md` and ask the user before changing collectors.

## 3. Doc-authority router — which doc answers what, and whether to trust it

Statuses: **TRUST** = current authority; **GENERATED** = auto-regenerated schema
truth (trust the numbers, don't hand-edit); **AT-RISK** = trustworthy but
untracked (back it up before any git clean); **NAV** = navigation index, not
ground truth; **STALE** = do NOT trust as current state. Dates are the last
commit touching the file (verified 2026-07-08 via `git log -1 --format=%ci`).

| Doc (path relative to repo root) | Status | Last commit | Answers |
|---|---|---|---|
| `AGENTS.md` | TRUST (LIVE) | 2026-07-04 `cc97cab` | Conventions, tribal knowledge, "read openwiki/quickstart.md first." Caveat: its loop step-counts (27→32→33 across entries) are all stale — see §4. |
| `CLAUDE.md` | TRUST (LIVE) | 2026-07-04 `cc97cab` (working copy modified) | Project rules + a dated `## Current state (2026-07-06)` snapshot (line ~133). |
| `openwiki/quickstart.md` | NAV | LLM-generated (glm, daily CI) | Navigation into architecture/workflow/ops notes. Derivative, not ground truth. |
| `docs/factor_reference.md` | GENERATED | 2026-07-02 `3609af5` | Current factor/variable schema — what factors exist right now. |
| `docs/VARIABLE_DICTIONARY.md` | GENERATED | 2026-07-02 `3609af5` | Current variable definitions. Regen every `monthly_update`. |
| `ARJUN.md` | TRUST / AT-RISK (untracked) | 2026-07-06 (untracked) | Newest synthesized review of the system. Untracked — one `git clean` from gone. |
| `FABLE.md` | TRUST / AT-RISK (untracked) | 2026-07-06 (untracked) | Newest synthesized review incl. the P0 leakage-guard proposal. Untracked. |
| `ledgers/hypothesis_ledger.jsonl`, `ledgers/thesis_ledger.jsonl` | TRUST (append-only) | live | The authoritative verdict record (DEAD/WEAK/WATCH/INSUFFICIENT_COVERAGE). |
| `Data/dislocations/brief_<YYYY_MM_DD>.md` | GENERATED (daily) | latest `brief_2026_07_07.md` | Today's dislocation brief. Verify the filename date is recent AND the content isn't a stale repeat (see §4). |
| `docs/ASADO_TRADING_RUNBOOK_2026_07_03.md` | TRUST / UNINDEXED | 2026-07-03 | The actual paper→live runbook (8 sleeves). Not in docs/README index. |
| `docs/alpha_book_2026_07_02/` (16 files) | TRUST / UNINDEXED | 2026-07-02 | The net-edge audit: fundable edge ~0–0.7%/yr on $100k; nothing survives 25bp. Not indexed. |
| `docs/JUDGMENT_OPERATING_MODEL_2026_06_17.md` | REFERENCE | 2026-06-17 | Judgment layer, family_key gaming, calibration-sample and zero-lag bugs. |
| `llmchat.md` | **STALE** | 2026-07-02 `ce15611` | Frozen ~20 commits behind. Do NOT treat as current state. |
| `DATA_DICTIONARY.md` | **STALE** | 2026-06-11 `ecf1da7` | Superseded by `docs/factor_reference.md` + `docs/VARIABLE_DICTIONARY.md`. |
| `ASADO_DATABASE_MAP.md` | **STALE** | 2026-06-11 `ecf1da7` | Superseded; schema is ~4+ weeks behind. |
| `CLAUDE_CODE_BRIEF.md` | **STALE** | 2026-05-16 `37a131c` | Self-flagged stale. Do not trust. |
| `docs/README.md` (index) | **PARTIAL/STALE** | — | Missing ~30 files, incl. the whole `alpha_book_2026_07_02/` cluster and the trading runbook. Don't rely on it to find docs. |

## 4. Where is the current state? (reconstruct today's truth)

There is no single "state of the world" file. To reconstruct today's truth, read
these, in this order:

1. `cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO" && git log --oneline -20`
   — what actually changed recently. Note: `Auto-commit
   nightly brief ...` commits are **benign** background noise (55+ of them). Two
   brief commits per day (morning + midday, different timestamps) is normal
   regeneration, not a stuck loop.
2. `CLAUDE.md` → the `## Current state (YYYY-MM-DD)` section — the human-curated
   snapshot (what's live, what recently died, what's on hold).
3. `AGENTS.md` → conventions + "Learned User Preferences."
4. `ledgers/hypothesis_ledger.jsonl` and `ledgers/thesis_ledger.jsonl` — the
   authoritative kill/keep verdicts (as of 2026-07-08: 59 hypotheses — 21 DEAD,
   21 WEAK, 16 INSUFFICIENT_COVERAGE, 1 WATCH).
5. `Data/dislocations/brief_<latest>.md` — the newest daily brief (latest is
   `brief_2026_07_07.md`). **Check both the date in the filename AND that the
   body is not a stale repeat** — a green pipeline once re-committed an identical
   stale brief 15 times.
6. `ARJUN.md` + `FABLE.md` — the newest synthesized reviews (2026-07-06), if
   present. Back them up before any git operation that could clean untracked
   files.

**What NOT to trust for current state:** `llmchat.md`, `DATA_DICTIONARY.md`,
`ASADO_DATABASE_MAP.md`, `CLAUDE_CODE_BRIEF.md`, the `docs/README.md` index, and
**any step-count quoted in prose**. Multiple docs disagree on the nightly loop
size (`AGENTS.md` says 27, then 32, then 33 across its dated entries;
`loop_daily_job.py`'s docstring says ~33/37) — all stale. The authority is `config/governance_contract.yaml`, which currently
defines **47 steps** (verified: 47 list entries under the `steps:` block; 20 are
`optional: false` / hard-required, 27 are fail-soft `optional: true`).

## 5. Routing map — the seven sibling skills

Go straight to the one that matches your task instead of reading everything here:

- **asado-architecture-contract** — the load-bearing design decisions, data
  contracts (unified/feature panels, isolated tables, T2 default), and known
  weak points. Use when you need to understand *how data flows or why a design
  is the way it is* before touching a builder.
- **asado-change-control** — how changes are classified and gated here, plus the
  house laws with the incidents that earned them. Use *before you modify
  anything* or when deciding how risky a change is.
- **asado-research-protocol** — the experiment → harness → ledger lifecycle at
  house standard (pre-registration, gates, verdicts). Use when *proposing or
  running a new signal / hypothesis*.
- **asado-debugging-playbook** — a symptom → triage table built from real
  failure modes. Use when *a job failed, errored, or looks wrong*.
- **asado-graveyard** — the settled battles and the check-before-proposing
  protocol. Use *before proposing any research idea* (re-proposing a dead end
  loses trust fast).
- **asado-operations** — schedules, launchd jobs, manual runs, health checks,
  tests, frontends, and MCP tools. Use when *operating the factory or checking
  its health*.
- **asado-leakage-guard-campaign** — the decision-gated campaign to build and CI
  the P0 forward-return leakage guard. Use only when *working on that specific
  guard*.

## 6. Glossary (house terms a zero-context reader will hit)

- **T2** — see §1. The 34-country factor-timing universe/book; `feature_panel_t2` is its analysis view.
- **PIT** — point-in-time: using only data that was actually published/available at the decision date. The harness enforces PIT via publication-lag embargoes; violating it is "leakage"/"look-ahead."
- **NMRet / forward returns** — `1MRet/3MRet/6MRet/9MRet/12MRet` (+ daily `1DRet/5DRet/20DRet/60DRet/120DRet`): FUTURE returns used as optimizer targets. Never predictors. Canonical set: `scripts/harness/evaluate_signal.py:146-149`.
- **NW-t** — Newey–West t-statistic (autocorrelation-robust significance of a signal's IC).
- **DSR / deflated Sharpe** — Sharpe ratio penalized for the number of trials tried in the same family (multiple-testing correction). More trials ⇒ higher bar.
- **IC** — information coefficient: rank correlation between signal and subsequent returns.
- **Verdicts** — `WATCH` (all four gates pass — rare, treat with suspicion), `WEAK`, `DEAD`, `INSUFFICIENT_COVERAGE`/`INSUFFICIENT_HISTORY`. Defined in **asado-research-protocol** STEP 6.
- **Family / trial** — every hypothesis is charged to a signal family in `config/family_registry.yaml`; the family's trial count feeds the DSR bar. Pre-registration is a hard gate.
- **Fold / ledger fold** — the nightly step that dedupes the append-only hypothesis ledger to each hypothesis's latest verdict.
- **PARTIAL / exit 2** — a loop step that kept its completed work but skipped a part that self-heals next run; a warning, not a failure.
- **Dislocation / brief** — nightly detector output (D1–D10) rendered to `Data/dislocations/brief_YYYY_MM_DD.md`.
- **Docket / daily_docket** — the Discovery-Triage LLM step (calls Anthropic; costs money).
- **Triptych** — the conditional-history prior layer. Context/prior tier ONLY — its queue rule tested DEAD; never treat its lean as a return signal.
- **The two DBs** — `Data/asado.duckdb` (warehouse, destroyed+rebuilt each rebuild) vs `Data/loop/asado_loop.duckdb` (durable loop/ledger DB). Never hold a connection to either.
- **Quiet window** — 06:00–08:30 PT; nightly jobs own the machine and the DBs.
- **Gate numbering warning** — three different "gate" schemes exist: harness verdict gates (research-protocol STEP 6), per-experiment PRD gate ladders ("died at Gate 3" — that experiment's own pre-registered ladder, see **asado-graveyard**), and the leakage-campaign's G1–G5. Never map one onto another.

## When NOT to use this skill

This is the **default entry point** — its whole job is to hand you off. Do NOT
sit here re-reading it when a specific sibling skill already matches your task:
route straight to that skill. In particular:
- Need current factor/variable schema? → `docs/factor_reference.md` /
  `docs/VARIABLE_DICTIONARY.md`, not this skill.
- Operating / running / checking health? → **asado-operations**.
- Something broke? → **asado-debugging-playbook**.
- About to propose or change something? → **asado-graveyard** /
  **asado-research-protocol** / **asado-change-control**.
- Bloomberg data work? → the global **bloomberg-skill** (not restated here).

A wrong runbook is worse than none: if a claim here conflicts with a LIVE
authority (`AGENTS.md` / `CLAUDE.md`) or the ledgers, trust the live authority
and tell the user about the drift.
