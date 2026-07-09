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
- Never `git clean -fd` / `git clean -fdx`. This repo has repeatedly accumulated
  genuinely load-bearing untracked files — synthesized reviews, dead-experiment
  records with real research value — that a clean deletes **permanently and
  irreversibly**, no warning, no undo. Before ANY operation that could remove
  untracked content, run `git status --short` and look for anything that isn't
  obvious scratch/cache/data output; if in doubt, ask the user rather than
  clean.
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

Statuses reflect each doc's **structural category** — why it tends to be trustworthy
or not — which stays true regardless of when you're reading this. They are NOT a
point-in-time freshness verdict: **never trust a specific date, commit hash, or
filename baked into this table (or any doc) as still current.** Where currency
matters, check live with the command shown.

- **TRUST (LIVE)** = the repo's own designated current authority (self-declared
  reading order, or the file that's actively edited as state changes).
- **GENERATED** = mechanically regenerated on a schedule by pipeline code — trust the
  numbers, never hand-edit.
- **NAV** = a navigation/summary layer derived from other docs — useful for finding
  things, not a source of ground truth.
- **STRUCTURALLY STALE** = superseded by a generated doc, or self-flagged stale in its
  own text, or an index that has no auto-update mechanism — durably a *weaker* source
  than its live/generated counterpart, even though its specific "how far behind" gap
  will keep changing.

| Doc (path relative to repo root) | Status | Answers | Check currency with |
|---|---|---|---|
| `AGENTS.md` | TRUST (LIVE) | Conventions, tribal knowledge, "read openwiki/quickstart.md first." Caveat: loop step-counts written in prose here are never reliable — see §4. | `git log -1 --format=%ci -- AGENTS.md` |
| `CLAUDE.md` | TRUST (LIVE) | Project rules + a dated `## Current state (YYYY-MM-DD)` section. | `git log -1 --format=%ci -- CLAUDE.md`; also check `git status` for an uncommitted working-copy edit |
| `openwiki/quickstart.md` | NAV | Navigation into architecture/workflow/ops notes. Derivative (LLM-generated by daily CI), not ground truth. | n/a — always derivative |
| `docs/factor_reference.md` | GENERATED | Current factor/variable schema — what factors exist right now. Regenerated every `monthly_update.py` run. | `git log -1 --format=%ci -- docs/factor_reference.md` |
| `docs/VARIABLE_DICTIONARY.md` | GENERATED | Current variable definitions. Regen every `monthly_update`. | `git log -1 --format=%ci -- docs/VARIABLE_DICTIONARY.md` |
| `ARJUN.md` | TRUST (if present) | Synthesized business-value review of the system, when it exists. | `git ls-files ARJUN.md` (confirm tracked) + `git log -1 --format=%ci -- ARJUN.md` |
| `FABLE.md` | TRUST (if present) | Synthesized engineering review, when it exists (e.g. incl. the P0 leakage-guard proposal history). | `git ls-files FABLE.md` + `git log -1 --format=%ci -- FABLE.md` |
| `ledgers/hypothesis_ledger.jsonl`, `ledgers/thesis_ledger.jsonl` | TRUST (append-only) | The authoritative verdict record for the single-variable harness pathway (pre-register via `family_registry.yaml` → `evaluate_signal.py` → DEAD/WEAK/WATCH/INSUFFICIENT_COVERAGE) — current *by construction* since it's append-only. **Scope limit:** does NOT capture directory-experiment methodology verdicts — see the next row. | always live; see **asado-graveyard** §1b for the live-tally command |
| `ledgers/methodology_ledger.jsonl` | TRUST (append-only) | The verdict record for whole-methodology directory experiments (regime/, momentum_fragility/, etc.) that the hypothesis ledger's single-variable schema can't represent — built 2026-07-09, `scripts/loop/ledgers.py`. **Scope limit:** the five known historical experiments predating this ledger are NOT backfilled into it (a separate, still-open decision) — until/unless they are, check each experiment dir's `RESULTS.md` too. See **asado-change-control** LAW 2 and **asado-graveyard** §1c. | always live; see **asado-graveyard** §1c for the live-tally command |
| `Data/dislocations/brief_<YYYY_MM_DD>.md` | GENERATED (daily) | Today's dislocation brief. | `ls -t Data/dislocations/brief_*.md \| head -1` — then verify the filename date is recent AND the body isn't a stale repeat (see §4) |
| `docs/ASADO_TRADING_RUNBOOK_2026_07_03.md` | TRUST / UNINDEXED | The paper→live runbook (multi-sleeve), as of the date in its filename. Not in `docs/README.md`'s index — find successors/updates with `find docs -iname "*RUNBOOK*"`. | filename date is fixed identity, not freshness — check for a newer-dated sibling file before trusting it's still the latest |
| `docs/alpha_book_2026_07_02/` (dir) | TRUST / UNINDEXED | The net-edge audit as of its dated directory name. Historically absent from `docs/README.md`'s index. | `find docs -maxdepth 1 -iname "alpha_book_*"` for a newer dated sibling |
| `docs/JUDGMENT_OPERATING_MODEL_2026_06_17.md` | REFERENCE | Judgment layer, family_key gaming, calibration-sample and zero-lag bugs, as diagnosed on its dated filename. | check `docs/` for a newer-dated judgment/governance doc before assuming this is still the latest word |
| `llmchat.md` | **STRUCTURALLY STALE** | An append-only cross-agent session log — trustworthy only if actively being written to. | `git log -1 --format=%ci -- llmchat.md`; if the gap to `git log -1` on HEAD is more than a few days, treat it as abandoned, not current |
| `DATA_DICTIONARY.md` | **STRUCTURALLY STALE** | Hand-maintained; structurally superseded by the GENERATED pair above, which will always be more current since nothing regenerates this one. | prefer `docs/factor_reference.md` / `docs/VARIABLE_DICTIONARY.md` outright rather than checking a date here |
| `ASADO_DATABASE_MAP.md` | **STRUCTURALLY STALE** | Same reason as `DATA_DICTIONARY.md` — hand-maintained schema doc with a generated replacement. | same as above |
| `CLAUDE_CODE_BRIEF.md` | **STRUCTURALLY STALE** | Self-flagged stale in its own text (an intrinsic, durable property — read the file's own header). | n/a — trust the self-flag, not a date |
| `docs/README.md` (index) | **STRUCTURALLY STALE** | A hand-maintained doc index with no auto-update mechanism — has repeatedly fallen behind newly added docs. Don't rely on it to find docs; use `find docs -iname "*<keyword>*"` instead. | n/a — the failure mode is structural (no regen), not a specific staleness date |

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
4. `ledgers/hypothesis_ledger.jsonl`, `ledgers/thesis_ledger.jsonl`, and
   `ledgers/methodology_ledger.jsonl` — the authoritative kill/keep verdicts
   (single-variable, trade-thesis, and whole-methodology respectively).
   Verdict counts grow daily; don't trust a count in any doc (including this
   one) — get the live tally with **asado-graveyard** §1b (hypothesis) or
   §1c (methodology).
5. `Data/dislocations/brief_<latest>.md` — the newest daily brief. Find it live
   with `ls -t Data/dislocations/brief_*.md | head -1`, not by trusting a
   filename in any doc. **Check both the date in the filename AND that the
   body is not a stale repeat** — a green pipeline once re-committed an identical
   stale brief 15 times.
6. `ARJUN.md` + `FABLE.md` — synthesized reviews of the system's state, useful
   context if present; check `git log -1 --format=%ci -- ARJUN.md FABLE.md` for
   how current they are rather than assuming a date.

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
