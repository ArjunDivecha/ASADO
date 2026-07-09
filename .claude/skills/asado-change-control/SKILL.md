---
name: asado-change-control
description: >-
  How changes are classified, gated, and reviewed in the ASADO repo, with the
  specific incident behind each rule so you can see the rules are earned, not
  arbitrary. Read this BEFORE editing any file under "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO",
  before deleting or renaming any symbol, and before merging any pipeline change.
  Covers: the change-classification table (experiment vs pipeline vs
  monthly-collector/T2-feed vs config/ledger vs ops), the five evidence-derived
  house laws with their incidents, the scrub-and-delete rule from the C1 leak
  chase, the pre-merge checklist, and this repo's git conventions. Do NOT use
  this skill for pure research/experiment design (use asado-research-protocol),
  for triaging a live failure that is already happening (use
  asado-debugging-playbook), or for step-by-step run/health/schedule commands
  (use asado-operations). This skill tells you whether and how you are allowed
  to change something; those tell you how to run or fix it.
---

# ASADO Change Control

You are most likely a Sonnet-class session with zero prior context, operating
autonomously in a production quant repo. **The main checkout at
`/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO` IS production** —
launchd jobs run the code in this exact tree every day. A careless change here
does not break a sandbox; it corrupts live output that a downstream trading
process (`fdt-decide`, the Fable Daily Trading repo) reads at 12:20 PT with no
completion handshake. Treat every edit as a production change until you have
classified it below and confirmed it is allowed.

This skill is the gate you pass through before touching code. It does not teach
you how to run the pipeline (see **asado-operations**), how to design an
experiment (see **asado-research-protocol**), or how to diagnose a failure in
progress (see **asado-debugging-playbook**).

---

## 1. Classify the change FIRST

Every change falls into exactly one of these classes. Find your class, obey its
rule. When in doubt, treat the change as the more restrictive class.

| Class | What it is | Where it may live | Hard rule |
|---|---|---|---|
| **(a) Experiment code** | A new hypothesis, signal, backtest, or exploratory analysis | A `git worktree` off the repo + that experiment's own sandbox dir (e.g. `regime/`, `momentum_fragility/`, `experiments/`) | **NEVER switch branches in the main checkout** — launchd runs from it. Create a worktree instead (see §5). Experiment output stays inside the experiment dir; do not write into `Data/` builders or panel views. |
| **(b) Pipeline code** | Nightly-loop steps, builders, panel construction, harness, governance, optimizer | Main tree, on `main` | Allowed, but the **§4 pre-merge checklist and the §2 house laws are mandatory**. Every pipeline change must preserve the data-contract invariants (no `NMRet` as predictor, no isolated table unioned into panels, no unguarded `duckdb.connect`). |
| **(c) Monthly-collector / T2-feed bug** | Anything in the Bloomberg monthly collector or the T2 data feed that ingests source data | Report only | **NEVER fix without the user's approval.** These pull real vendor data on a monthly cadence; a "fix" can silently corrupt the historical panel and is not re-runnable on demand. STOP, append the bug to `docs/USER_FIX_LIST.md`, and report it to the user. Do not edit the collector. |
| **(d) Config / ledgers** | `config/family_registry.yaml`, `config/governance_contract.yaml`, `ledgers/hypothesis_ledger.jsonl`, family/thesis registries | Main tree, on `main` | **Append-only.** Pre-registration in `config/family_registry.yaml` is a hard gate (an unregistered variable raises `UnclassifiedVariableError`). Never rewrite or delete a past ledger verdict — the ledger is the audit trail. Add a new line; do not mutate old ones. |
| **(e) Ops / scheduling** | launchd plists, `run_*.sh` wrappers, cron/heartbeat, service guards (Neo4j) | `~/Library/LaunchAgents/*.plist` + wrappers in the tree | **Committing the code is NOT deploying it.** A plist change only takes effect after it is installed and loaded (`launchctl`). You MUST verify the deployed state, not just the commit (House Law 3). |

Edge case worth naming: **adding a brand-new collector** (as opposed to fixing an
existing one) is class **(b)** pipeline code — gated by the §4 checklist and the
architecture data contract (**asado-architecture-contract** §1) — not class (c),
which covers *bugs in existing* vendor feeds.

If you cannot tell which class a change is, or the change spans two classes
(e.g. a pipeline edit that also touches the monthly collector), STOP and ask the
user. A wrong classification here is how production breaks.

---

## 2. The five house laws (each earned by a specific incident)

These are not style preferences. Each one is the scar left by a real failure in
this repo's history. Every commit hash below was verified with `git show` on
2026-07-08. When you follow a law, you are avoiding the exact bug that created
it.

### LAW 1 — DISTRUST A SEARCHED PASS

> Any PASS produced by an autonomous tuning/search loop is presumed FALSE until
> it is re-derived from a pre-registered hypothesis on corrected inputs.

**Incident.** The `regime_loop/` autonomous tuning loop produced the original
regime-test v1 "PASS" by searching configurations until one passed.
`regime_loop/output/state.json` confirms **zero honest successes**
(`best_primary_metric=0.0`, `loop_status="error"`, `retires=0`); the finer
"13 attempts, agents caught gaming the metric by modifying forbidden files"
account comes from run-history review and is NOT reconstructable from the current
`state.json` snapshot — treat that detail as reported, not re-verifiable. When the
inputs were corrected and the hypothesis re-run honestly, the verdict flipped to
**DEAD** (`regime/regime2.md`, 2026-05-23; evidence in
`regime/regime2_fresh_run.log:106`).

**How to comply.** If you find a PASS/WATCH that was discovered by a loop
tuning parameters, do not act on it and do not report it as a result. Re-run it
as a fresh, pre-registered hypothesis through the harness (see
**asado-research-protocol**). Only a pre-registered re-derivation counts.

### LAW 2 — METHODOLOGY EXPERIMENTS NEED THEIR OWN LEDGER (built 2026-07-09; historical backfill still pending)

> `ledgers/hypothesis_ledger.jsonl` only covers single-variable harness
> verdicts. Directory-experiment methodology tests (regime/, momentum_fragility/,
> etc.) register and get verdicted in the separate `ledgers/methodology_ledger.jsonl`
> instead — a real, tested, isolated extension (`scripts/loop/ledgers.py`), not a
> permanent gap to route around.

**Root cause.** `register_hypothesis()` (`scripts/loop/ledgers.py:179-230`)
requires a `signal_spec["variable"]` that resolves to a family via
`config/family_registry.yaml`'s `variable_prefixes` lists (it raises
`UnclassifiedVariableError` otherwise) — the hypothesis ledger's schema is
built around single-variable harness verdicts (IC / NW-t / deflated Sharpe /
cost grid from `evaluate_signal.py`). A directory-experiment methodology test
— an HMM regime classifier, a fragility composite, a whole regime-conditioning
approach — isn't one registered variable; it's evaluated against its own
PRD-defined gate ladder (Gate 1/2/3/...) that doesn't map onto that schema.

**The fix that's now built.** `scripts/loop/ledgers.py` gained a THIRD ledger,
`ledgers/methodology_ledger.jsonl`, with its own event set
(`METHODOLOGY_EVENTS`) and its own FAIL-IS-FAIL fold guard — a deliberately
**separate file**, because `fold_hypotheses()` raises on any event type
outside `HYP_EVENTS`, so a new event kind could not have been added into
`hypothesis_ledger.jsonl` without either weakening that guard or crashing the
nightly `fold_ledgers` step. Use `register_methodology_experiment()` +
`attach_methodology_verdict()` for any NEW directory experiment going forward
— pre-register the hypothesis and gate ladder BEFORE running it, exactly the
same discipline as the hypothesis ledger. `--list` and `--rebuild` on
`scripts/loop/ledgers.py` now cover all three ledgers; the loop DB gained a
`methodology_ledger` table alongside `hypothesis_ledger`/`thesis_ledger`.
Verified: 16 new tests in `tests/loop/test_methodology_ledger.py`, zero
regressions across the full safe test suite (251 passed), and a real
`--rebuild` run against production confirmed the new table folds correctly.

**Still open — the five historical experiments are NOT backfilled.**
`register_methodology_experiment`/`attach_methodology_verdict` require a real
pre-registration; a THIRD function, `backfill_methodology_verdict()`, exists
specifically for recording a historical experiment that predates this ledger
in one combined event, explicitly stamped `pre_registered: False` so a reader
can never mistake it for genuine pre-registration proof. Whether to actually
call it for the five known-missing experiments (`regime/`, `regime_loop/`,
`regime_ew/`, `regime_factor_selection/`, `momentum_fragility/`) is still the
user's call, not something to do unilaterally — check with the user before
backfilling; if approved, use `backfill_methodology_verdict()`, never a raw
edit to the JSONL file.

**How to comply.** For a NEW directory experiment: register it (with a real
gate ladder, before results) via `register_methodology_experiment()`, and
attach the verdict via `attach_methodology_verdict()` when it's done — check
**asado-research-protocol** for the parallel single-signal flow. Until the
five historical experiments are backfilled (if ever), the canonical graveyard
for THOSE specifically is still the union of: `results/RESULTS.md` in each
experiment dir, `docs/strategy/lessons.md`, and the external Investment
Learnings folder — **asado-graveyard** is the check-before-proposing protocol.
Do not treat a clean `methodology_ledger.jsonl` as "these five were never
tested."

### LAW 3 — DEPLOYED ≠ COMMITTED

> An ops fix is not done when it is committed. It is done when you have verified
> it is installed and running.

**Incident.** After the 2026-06-18 Neo4j outage, a stale-pidfile boot guard was
committed (`69174a1`, 2026-06-19). The code was correct and in the repo — but
the plist that would run it was **never installed**, so Neo4j failed again and
the loop degraded, forcing a graceful-degradation follow-up (`f6651c0`,
2026-06-20). The fix existed in-tree for days while production stayed broken.

**How to comply.** For any class (e) change, after committing you MUST confirm
the deployed state with read-only `launchctl list` / `launchctl print` and, for
services, that the process is actually up. "I committed the guard" is not a
completion report. See **asado-operations** for the launchctl verification
commands.

### LAW 4 — ARTIFACT FRESHNESS > EXIT CODES

> A green pipeline that exits 0 is not proof of health. Check that the OUTPUT
> CONTENT is fresh.

**Incident.** The **same** file `brief_2026_06_16.md` was auto-committed **15
times over 3 days** while the loop reported success — from `ce01ea4`
(2026-06-18) through `251a63f` (2026-06-21). The pipeline exited 0 every night;
the brief silently stopped regenerating and nobody noticed, because everyone was
watching exit codes instead of the artifact's date-stamped content.

**How to comply.** When you verify a pipeline change or a run, check that the
produced artifact's content/date advanced — not just that the process exited 0.
A repeated filename or a stale internal date is a failure even with exit 0.
(Note: two brief auto-commits per day in July with *different* timestamps is
benign morning+midday regen, not a stuck loop.)

### LAW 5 — FAIL IS FAIL (no silent fallbacks, no simulated success)

> If something fails, it fails. Never simulate success, never silently fall
> back to a degraded path, never claim a thing works without testing it.

This is the user's global hard law and it governs this repo. The specific repo
consequence: **do not fix monthly-collector or T2-feed bugs on your own
initiative** (class (c) above). When you hit such a bug, STOP, append it to
`docs/USER_FIX_LIST.md`, and report to the user rather than patching around it.

**How to comply.** If a step fails, report the actual failure with its output.
Do not substitute a hand-computed value, a cached result, or a "should work"
claim. Do not add a `try/except` that swallows the error and continues on a
default — the governance layer already had a silent-green bug from exactly this
pattern (empty contract → `expected=[]` → `max(default=0)` → GREEN with zero
checks; hardened in `9eef773`, "audit #1 CRITICAL", 2026-06-20). Aggregators
that default to "good" on empty input are the enemy.

---

## 3. Scrub-and-delete rule + the NOT_DONE convention

**Before deleting or renaming ANY symbol (variable, function, column, key),
grep every use site across the whole repo first.** A local scrub that looks
self-contained is the single most reliable way to plant a crash 200 lines away.

**Incident — the "C1" outcome-blindness leak chase (C1 = red-team finding #C1 from
`docs/REDTEAM_DISCOVERY_TRIAGE_2026_06_26.md`; three commits, verified):**

1. `e22305e` (2026-06-26, "Remediate red-team findings: outcome-blindness + PIT
   bypass + 14 more") — fixed the Discovery Lab leak where an allowlist checked
   a column name but not the JSON contents, so the future outcome leaked through.
2. `e717cf2` (2026-06-26, **"... NOT_DONE 2"**) — the same value was *also*
   leaking through a second Opus code path (the chat service). One fix was not
   enough; the leak had two sites. This was fixed at the data-access layer.
3. `f8b6bc0` (2026-06-27, "Fix build_price_state NameError from the C1 edit
   (restore `comb`)") — the scrub in step 1/2 deleted a variable named `comb`
   that had a **second, legitimate use ~180 lines later**. That crashed the
   nightly job with a `NameError`. The fix was to restore `comb`.

**The lesson, twice over:** (a) a leaked value can have more than one code path —
fix the data-access layer, not just the first call site you find; and (b) a
deleted symbol can have a distant second use — `grep` the entire repo for the
name before you remove it.

**How to comply — before any delete/rename:**

```bash
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
grep -rn "\bSYMBOL_NAME\b" --include="*.py" --include="*.yaml" --include="*.sql" .
```

Confirm every hit is one you intend to change. If a value is sensitive (a future
outcome, a target), fix it at the layer where the data is produced/accessed, not
at each individual consumer — consumers multiply.

**The NOT_DONE convention.** This repo marks a fix that is knowingly incomplete
by putting `NOT_DONE n` in the commit title (`n` = the iteration). You can see
it in `e717cf2` ("... NOT_DONE 2"), which flagged that the C1 leak was still not
fully closed. **If you make a partial fix, follow the convention: title it
`... NOT_DONE n` so the next reader knows the work is not finished.** Do not
report a NOT_DONE commit as "fixed".

---

## 4. Pre-merge checklist for any pipeline change (class (b))

Run through this before merging anything into `main`. Each item maps to a known
failure mode in this repo. These are read-only checks except where noted.

1. **`git status` is clean of untracked data.** No parquet/xlsx/duckdb/PDF/log
   files staged or committed. Data and run outputs belong in `.gitignore`, code
   only. **Never trust a list of "expected untracked files" in this or any
   other doc — tracked state drifts every time someone commits.** Confirm live
   with `git status --short` / `git ls-files <path>` before deciding what's
   safe to stage. If an untracked file looks like a synthesized review
   document or a dead experiment's results (not obvious scratch/data-cache
   output), don't assume it's "supposed to" stay untracked and don't assume
   it's fine to commit either — ask the user.

2. **No new `duckdb.connect` outside the guard.** Core builders must go through
   `guarded_connect()` in `scripts/duckdb_lock_guard.py`. Holding an
   unguarded connection — even an idle read-only one — is the documented root
   cause of the 2026-07-02/03 lock incidents. Check:
   ```bash
   cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
   git diff --cached | grep -n "duckdb.connect"
   ```
   Any new hit must be justified (only the known-unguarded writers — db_bridge,
   MCP, frontend, the 2 monthly GDELT-deep writers — are exceptions, and you
   should not be adding to that list).

3. **No isolated table unioned into a panel view.** These tables are analysis
   inputs, NEVER union them into `feature_panel` / `unified_panel`:
   `ff_factors`, `jst_macrohistory`, `factor_returns`, `factor_top20_membership`,
   `country_factor_attribution`. Consumers should read `feature_panel_t2` (34 T2
   names), the documented analysis default — not the 43-country `feature_panel`.

4. **No `NMRet` family as a predictor.** `1MRet/3MRet/6MRet/9MRet/12MRet` and
   their daily analogs (`1DRet/5DRet/20DRet/60DRet/120DRet`) are optimizer
   TARGETS (forward returns). Registering any of them as a predictor is a
   leakage bug (one was caught and blacklisted 2026-06-10). Canonical blacklist
   (the full 10-member set): `scripts/harness/evaluate_signal.py:146-149`
   (re-derived at `scripts/loop/triptych_kernel.py:84-90` — the duplication is a
   known P0 risk; see **asado-leakage-guard-campaign**).

5. **Tests still pass.** **Never run bare `python -m pytest tests/`** —
   `tests/loop/test_gap_engine.py:143-145` opens the PRODUCTION loop DB and will
   fight the live writer. The sanctioned ways to check tests: (a) collection
   only: `python -m pytest tests/ --collect-only -q`; (b) an actual run using the
   `--deselect` invocation documented in **asado-operations** §4 (deselects the
   prod-DB test), outside the 06:00–08:30 PT window. Never touch the loop DB
   path directly.

6. **Timing.** Do not merge or launch anything long-held during the nightly
   quiet window **06:00–08:30 PT** — that is when `asado-daily` (07:30) and the
   loop safety net run. A long-held resource there collides with production.

If any item fails, do not merge. Fix it, or if it is a class (c) collector bug,
STOP and append to `docs/USER_FIX_LIST.md`.

---

## 5. Git conventions in this repo

- **Auto-commit jobs exist.** Expect to see commits you did not make: nightly
  brief auto-commits and OpenWiki CI commits. Two brief commits/day with
  different timestamps is normal (Law 4). Do not "clean these up" or rebase
  over them.

- **Never rebase or force-push `main`.** launchd runs from this tree; a rewrite
  of `main` can strand the deployed state. Never push, force-push, or open a PR
  without the user asking.

- **Experiments go on a worktree, never a branch switch in the main checkout:**
  ```bash
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
  git worktree add ../ASADO-exp-<name> -b exp/<name>
  ```
  Work there; the production tree stays on `main` untouched.

- **Never trust a branch name as evidence of real work — verify divergence.**
  AI coding tool sessions (Codex, Traycer, Devin, Claude) routinely create a
  session-start branch stub that never receives a commit; a bare branch name
  proves nothing. Check before acting on any branch:
  ```bash
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
  git merge-base --is-ancestor <branch> main && echo "pure ancestor — no unique work"
  git log main..<branch> --oneline    # empty output = same conclusion
  ```
  A branch that DOES diverge still needs full review before you act on any
  part of it — never merge or hand-apply a piece of a branch (e.g. cherry-pick
  a single commit) without reading the whole diff and confirming with the user
  what else is bundled in. (This repo has previously had a genuinely useful
  one-line fix sitting stranded on an unmerged branch for weeks, bundled
  alongside hundreds of lines of unrelated log output — the fix was easy to
  miss and the log diff was not something to blindly pull in with it.) Check
  `git branch -a` and `git log main..<branch>` live rather than trusting any
  branch inventory in a doc — branches get created, merged, and deleted
  continuously.

- **Regime/label-tagging bugs have unusually high blast radius — verify, don't
  assume.** A function that classifies rows into named regimes/labels (the
  `tag_regime`-style pattern used in this repo's regime experiments) can fire
  the *correct* internal rule/tag while `return`ing the *wrong* label string —
  the fired-tag list and the returned label are independently editable, and
  nothing enforces they agree. Every downstream consumer trusts the returned
  label, not the internal tag, so a single wrong `return` silently mislabels
  every row that hits that branch for as long as the bug survives. Before
  trusting any regime-conditioned result, read the tagger function directly
  and confirm each branch's `fired`/tag list actually matches what it
  `return`s — do not infer correctness from the tag name alone.

- **Commit code only.** Data files, run outputs (parquet/xlsx/PDF),
  checkpoints, `.env`, and anything with keys go in `.gitignore`. Commit at
  logical checkpoints without asking; never push/PR without asking.

---

## When NOT to use this skill

- **You are designing or running an experiment / hypothesis** → use
  **asado-research-protocol** (the experiment → harness → ledger lifecycle).
  This skill only tells you *where* experiment code may live (§1 class (a)).
- **A job is failing RIGHT NOW and you are triaging it** → use
  **asado-debugging-playbook** (symptom → cause table). This skill governs how
  changes are made, not how live failures are diagnosed.
- **You need the actual run/health/schedule/test commands** → use
  **asado-operations**. This skill points at launchctl verification (Law 3) but
  does not carry the operational command set.
- **You are deciding whether an idea is already dead** → use **asado-graveyard**.
- **You are onboarding / need the doc-authority map** → use **asado-start-here**
  and **asado-architecture-contract**.

Applying this runbook to a task it does not cover is worse than having no
runbook — it will make you gate a research question as if it were a production
edit, or edit a monthly collector you were supposed to escalate.
