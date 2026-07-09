---
name: asado-leakage-guard-campaign
description: >-
  Decision-gated campaign playbook for building ASADO's single highest-leverage
  safety asset: the P0 deterministic leakage/isolation guard, and wiring it into
  CI. Use this when the task is to execute the "P0 — Central deterministic
  leakage/isolation guard" improvement from FABLE.md — i.e. collapse the two
  crown-jewel correctness rules (the forward-return NMRet blacklist and the
  isolated-table exclusion) into one read-only script that exits nonzero and
  names offenders, prove it with seeded fixtures, and add a GitHub Actions job
  that runs it on every change. Trigger phrases: "build the leakage guard",
  "P0 guard", "leakage_isolation_guard", "wire the isolation guard into CI",
  "run the FABLE.md P0 Divecha contract". Do NOT use this skill for any other
  research/ops/debugging task, for fixing the blacklist duplication itself
  (that is the separate P2 — see WRONG PATHS), or for extending guard coverage
  to new leakage classes beyond the two named here (that is a new contract and a
  new campaign, not this one).
---

# ASADO leakage-guard campaign

You are running a **campaign**, not a one-shot task. This skill is the playbook a
Sonnet-class session follows to execute the P0 improvement already specified as a
validated Divecha contract inside `FABLE.md`. (**Divecha** = the house format for a
portable, gated implementation contract: deterministic shell-verifiable gates instead
of agent self-certification; the global `divecha` skill executes one in Build Mode.) Follow the phases in order. Each phase
ends in a **GATE** with an **EXPECTED OBSERVATION**; if what you observe does not
match, **STOP and report to the user** — do not paper over it and continue.

Repo root (quote the spaces in every command):
`/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO`

---

## 1. Mission & why this is P0

**Mission:** produce one deterministic, read-only guard script that mechanically
re-checks ASADO's two crown-jewel correctness rules and exits nonzero (naming the
offender) whenever either is violated — then wire it into CI so it runs on every
change. Prove it works with seeded fixtures. Nothing else.

**Why this was assessed as the highest-leverage item in the repo** (from the FABLE.md P0
review, `FABLE.md:44-61`, at the time it was written): the two rules that protect *every*
future experiment and collector were enforced only by **convention and duplication
across ≥8 files**, with **almost no CI**. This rationale is historical — before doing
any work, confirm in Phase 0.0 below that the gap it describes is still open; someone
may have already closed it since this skill was written. Two concrete manifestations of
that risk, as originally diagnosed:

1. **The forward-return blacklist is re-implemented independently, and the two copies
   have already diverged.**
   - Canonical explicit set — `scripts/harness/evaluate_signal.py:146-149`:
     `{"1MRet","3MRet","6MRet","9MRet","12MRet","1DRet","5DRet","20DRet","60DRet","120DRet"}`
     (banned as signals; comment at `:140-145` records the empirical 2026-06-10
     justification — a fake IC of 0.25 from look-ahead, hypothesis `H_20260610_001`).
   - Independent regex analog — `scripts/loop/triptych_kernel.py:86`:
     `_FORBIDDEN_SIGNAL_RE = re.compile(r"^\s*\d+\s*[MD]\s*Ret\s*$", re.IGNORECASE)`,
     consumed by `is_forbidden_signal()` at `:88-90`.
   - These are **not the same rule**: the regex matches *any* `<n>[MD]Ret`, while the
     set is a fixed enumeration. Any new signal path that imports neither, or diverges
     its own regex, can register a target as a predictor and **no gate stops it**.
2. **Isolated-table exclusion is a house rule, not a check.** `feature_panel` /
   `unified_panel` are built in `scripts/build_normalized_panel.py` and (for
   `unified_panel`) the UNION-ALL in `scripts/setup_duckdb.py` (~`:920-953`, per
   findings-architect). Nothing fails the build if a future edit unions `factor_returns`,
   `ff_factors`, or the JST corpus into those views — the cycle-break and
   no-broadcast guarantees rely entirely on the author remembering.

The guard turns that vigilance into a command. See the sibling skill
**asado-architecture-contract** for the full data-contract rationale, and
**asado-change-control** for the house laws these rules live under.

---

## Phase 0 — PRE-FLIGHT (do this before anything else)

### 0.0 Confirm the campaign hasn't already been completed

Before investing in any of the phases below, check whether someone already built and
wired the guard — do not assume the gap described in §1 is still open just because this
skill exists:
```bash
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
find scripts/qa -iname "*leakage*" -o -iname "*isolation*"
find .github/workflows -type f
```
**If a leakage/isolation guard script already exists:** read it, confirm it covers both
INV1 (forward-return blacklist) and INV2 (isolated-table exclusion) from §2 below, and
confirm it's wired into `.github/workflows/`. If it fully covers both, this campaign is
already graduated — tell the user and stop; don't rebuild it. If it's partial, treat the
remaining phases as filling the gap, not starting from zero.

The entire contract lives in `FABLE.md`. Your first job is to confirm it still exists
and capture its content — do not assume its tracked-in-git status from this skill or
any other doc (check live with `git ls-files FABLE.md`); either way, files can be
moved, renamed, or deleted between when this skill was written and when you read it.

### 0.1 Verify the contract source exists

```bash
ls -la "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/FABLE.md"
git ls-files "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/FABLE.md"   # tracked or not?
```

**EXPECTED OBSERVATION:** the file exists. The embedded Divecha contract is the fenced
` ```markdown ` block at approximately `FABLE.md:137-322`; the handoff prompt is at
`FABLE.md:118-131`. (Exact line numbers can drift if the file has been edited since —
if the fenced block isn't there, search the file for `spec_id: ASADO-LEAKAGE-ISOLATION-GUARD-001`.)

**CONTINGENCY — if `FABLE.md` is MISSING:** do not invent a contract. The essential
invariants are carried as backup in section "Backup: the invariants the guard checks"
at the bottom of THIS skill; reconstruct the contract from those, keeping
`schema_version: 1`, `spec_id: ASADO-LEAKAGE-ISOLATION-GUARD-001`, the three invariants
INV1/INV2/INV3, and gates G1–G5 exactly as described below. Then tell the user FABLE.md
was missing and you reconstructed from the skill's backup, so the substitution is not
silent.

### 0.2 Save the contract to a spec file

Copy the fenced contract body (the content **inside** the ` ```markdown … ``` ` fence
at `FABLE.md:137-322`, starting at the `---` / `schema_version: 1` line) verbatim to:

`/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/leakage_isolation_guard.spec.md`

Do NOT alter the frontmatter, invariants, gates, `scope.forbid`, or budget. The gates
carry `command: TODO` — resolving those TODOs into real shell commands IS the campaign.

### 0.3 Verify the Divecha validator path, then validate the contract

```bash
ls -la "/Users/arjundivecha/code/divecha/divecha/scripts/validate_contract.py"
```
**EXPECTED OBSERVATION:** file exists and is executable. If it's missing, `divecha` may
have moved or been reinstalled elsewhere — check the global `divecha` skill for its
current path rather than assuming this one is wrong.

```bash
python3 "/Users/arjundivecha/code/divecha/divecha/scripts/validate_contract.py" \
  --mode author \
  "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/leakage_isolation_guard.spec.md"
```
(Exact command form per `FABLE.md:116`; the validator's argparse confirms
`spec` positional + `--mode {author,build}`, and it prints the success banner at
`validate_contract.py:450`.)

**EXPECTED OBSERVATION:** stdout contains
`DIVECHA_CONTRACT_VALID mode=author path=…/leakage_isolation_guard.spec.md` and the
process exits `0`.

**GATE (hard stop):** if validation prints anything other than
`DIVECHA_CONTRACT_VALID` or exits nonzero, **STOP and report to the user**. Do not
edit the contract to force it to pass, and do not proceed to build. A failing
Author-Mode validation means the saved spec drifted from the FABLE.md original.

> Execution mechanism: this campaign runs the contract via the **`divecha`** skill in
> Build Mode (see the handoff prompt at `FABLE.md:118-131`). This skill is the campaign
> wrapper around that — it tells you what "done" looks like, what the gates must observe,
> and which paths are off-limits. Let `divecha` drive the build loop; you own the gate
> observations and the stop conditions.

---

## Phase 1 — Build the guard (resolve gate G1)

**Change-control class:** this is `asado-change-control` class (b) pipeline code — it may
be built directly on `main` (it is additive and read-only), but you MUST run the
`asado-change-control` §4 pre-merge checklist before committing, and all violation
fixtures (Phase 2) live in gitignored scratch (`Data/work/experiments/` or the session
scratchpad), never in `config/` or the repo root.

**Natural home (per the contract):** `scripts/qa/leakage_isolation_guard.py`, alongside
the existing `scripts/qa/validate_returns_first.py` (verified present). A coding model may
confirm the exact filename in Build Mode, but `scripts/qa/` is the correct directory.

**Mandatory file header** (house rule, `~/CLAUDE.md`): the script MUST open with a doc
header stating (a) what it does in plain terms and (b) a complete inventory of every
input/output file with FULL absolute paths. The guard's inputs are
`config/family_registry.yaml` and the builder **source files**
(`scripts/build_normalized_panel.py`, `scripts/setup_duckdb.py`); it has **no output
files** (it prints to stdout and sets an exit code) — state that explicitly.

What the guard must do:
- **INV1:** parse `config/family_registry.yaml`, and for each registered signal/predictor
  variable, flag any that is a forward-return (NMRet/NDRet family). Match against BOTH
  the canonical set at `evaluate_signal.py:146-149` AND the regex form at
  `triptych_kernel.py:86` — importing/reusing the canonical set is preferred over
  re-typing it. Exit nonzero listing every match.
- **INV2:** read the **CREATE VIEW / builder SQL text** for `feature_panel` and
  `unified_panel` from the builder **source files** and flag any reference to an isolated
  table: `ff_factors`, the JST macrohistory table (`jst_macrohistory`), `factor_returns`,
  `factor_top20_membership`, `country_factor_attribution`. Exit nonzero naming the table.
- **INV3:** read-only. No writes; **no connection to either live DuckDB** — parse SQL from
  source files, never query the database.

Run it against the current clean repo:

```bash
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO" && source venv/bin/activate
python scripts/qa/leakage_isolation_guard.py   # exact name as built
```

**EXPECTED OBSERVATION (G1):** exit `0`, with a short "clean" summary printing how many
registrations and how many view definitions were scanned. Write this command into the
contract's `G1.command`.

---

## Phase 2 — Prove it fails when it should (gates G2, G3)

Fixtures are **throwaway copies** with a violation injected. NEVER edit the real
`config/family_registry.yaml` or the real builders to make a fixture (see WRONG PATHS c).
Point the guard at a temp copy via a flag/arg, or write fixtures under
`Data/work/experiments/leakage_guard/` (gitignored) or the session scratchpad.

- **G2 — seeded forward-return registration:** a fixture registry that registers an
  NMRet-family variable (e.g. `1MRet`) as a signal.
  **EXPECTED OBSERVATION:** guard exits **nonzero** and prints `1MRet` as the offender.
- **G3 — seeded isolated-table leak:** a fixture where the `feature_panel` (or
  `unified_panel`) view SQL selects from an isolated table (e.g. `factor_returns`).
  **EXPECTED OBSERVATION:** guard exits **nonzero** and names `factor_returns`.

**GATE:** if the guard exits 0 on either seeded violation, it cannot distinguish clean
from violating — the contract's `kill` condition. STOP, report, iterate on the guard;
do not wire CI to a guard that does not fail on the fixtures.

Write the two fixture commands into `G2.command` and `G3.command`.

---

## Phase 3 — Prove it is side-effect-free (gate G4)

```bash
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
python scripts/qa/leakage_isolation_guard.py
git diff --name-only
```

**EXPECTED OBSERVATION (G4):** `git diff --name-only` prints **nothing** after a guard
run, and the guard held no writable or long-held connection to `Data/asado.duckdb` or
`Data/loop/asado_loop.duckdb`. This is INV3. If `git diff` is non-empty, the guard is
mutating state — STOP and fix before continuing. Write this into `G4.command`.

---

## Phase 4 — Existing checks stay green (gate G5)

The guard must add coverage without breaking anything.

```bash
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO" && source venv/bin/activate
python scripts/qa/validate_returns_first.py
```
**EXPECTED OBSERVATION:** `validate_returns_first.py` stays green (exit 0).

```bash
# pytest — SEE CAVEAT BELOW before running bare
python -m pytest tests/ \
  --deselect tests/loop/test_gap_engine.py::test_live_gap_engine_tables_if_present
```

> **CAVEAT (hard rule):** `tests/loop/test_gap_engine.py::test_live_gap_engine_tables_if_present`
> (defined at `tests/loop/test_gap_engine.py:140`) **opens the PRODUCTION loop DB** if it
> is present. Running it can hold a connection during the nightly window and break the
> pipeline. Either `--deselect` it as shown, OR run pytest only OUTSIDE **06:00–08:30 PT**
> (the nightly quiet window). Never open a live `.duckdb` file to "check" this yourself.

**EXPECTED OBSERVATION (G5):** the deselected suite passes (or is green modulo the single
deselected live-DB test). Write the exact command you used into `G5.command`.

Once G1–G5 all exit 0, run the contract's configured **review** (per the contract's
`review` block) and record the verdict.

---

## Phase 5 — CI wiring (the `scale` step)

Add a new GitHub Actions job that runs the guard on every change. Model it on the
**structure** of `.github/workflows/openwiki-update.yml` (verified present), but:
- Trigger on `push` / `pull_request` (not only `workflow_dispatch`/`schedule`).
- Steps: `actions/checkout@v4` → `actions/setup-python@v5` (install the guard's deps) →
  run `python scripts/qa/leakage_isolation_guard.py`.
- **No secrets needed** — unlike the openwiki job, the guard uses no API keys and needs no
  `OPENROUTER_API_KEY`; it reads repo files only. Do not copy the `permissions: contents:
  write`, the commit-and-push step, or the model-id env from openwiki-update.yml.

**CI runs the GUARD ONLY.** Do NOT wire CI to run `pytest tests/` — that suite includes
the prod-DB test above and CI must never touch the live warehouse (see WRONG PATHS d).

**EXPECTED OBSERVATION (scale):** a **green** run on GitHub Actions for the clean branch,
AND a deliberately-broken branch fixture (an injected NMRet registration or isolated-table
reference) that makes the job **fail red**. Both observations are required — a job that
only ever passes proves nothing.

Optional: also add a local **pre-commit hook** that runs the guard, for fast local
feedback. This is a nice-to-have, not part of the graduate condition.

---

## WRONG PATHS (explicitly forbidden in this campaign)

These are fenced off. Doing any of them is a failure of the campaign even if gates pass.

- **(a) Do NOT "fix" the blacklist duplication by editing `triptych_kernel.py`.**
  De-duplicating the two forward-return definitions into one importable constant is the
  **separate P2** improvement (`FABLE.md:87-95`). Touching it here is scope creep. The
  guard should *consume* the canonical set; making it the single source of truth is a
  different contract.
- **(b) Do NOT have the guard query the live DuckDB for view definitions.** That violates
  INV3. Parse the CREATE VIEW / builder SQL from the **source files**
  (`build_normalized_panel.py`, `setup_duckdb.py`) instead. Opening either live DB — even
  read-only — can block the nightly writers (this exact class of holder caused the
  2026-07-02/03 outage).
- **(c) Do NOT modify `config/family_registry.yaml`, `ledgers/`, or any `scope.forbid`
  path — even to "add a test fixture."** `scope.forbid` includes `Data/asado.duckdb`,
  `Data/loop/asado_loop.duckdb`, `Data/processed/**`, `Data/raw/**`,
  `config/family_registry.yaml`, `ledgers/**`, `**/.env*`. Fixtures are throwaway COPIES,
  pointed at via a flag or written to gitignored scratch.
- **(d) Do NOT wire CI to run `pytest` (the prod-DB test).** CI runs the guard only.
- **(e) Do NOT mark the campaign "done" on gates alone.** Per the contract's Build-Loop
  vs Product-Loop section (`FABLE.md` context, ~`:293-307`): passing G1–G5 proves the
  guard *works*, NOT that the platform is *leak-free forever*. The product bet (no leaked
  feature ever reaches a live trading decision) is **explicitly NOT claimable** from
  gates. State this plainly in the handback; do not overclaim.

---

## DONE criteria & handback

**Graduate** (verbatim from the contract, `FABLE.md:231-235` / legacy block):
> gates G1 through G5 exit 0, the review verdict is pass, and no scope.forbid path is
> modified in the final diff.

**Scale** (verbatim):
> graduated AND the guard is wired into a pre-commit or CI step (in the style of
> `.github/workflows/openwiki-update.yml`) so it runs on every change, and it reruns clean
> on a second independent fixture.

**Kill** (verbatim): after 10 turns the guard cannot both pass on the clean repo (G1) and
fail on the two seeded fixtures (G2, G3) — i.e. it cannot distinguish a clean state from a
violating one. If you hit kill, STOP and report; do not ship a guard that cannot tell the
two apart.

**Handback to the user** — report:
1. The guard's absolute path and a `file://` link (house rule: always link results).
2. Gate evidence: the actual command + observed exit code / offender output for G1–G5 (real
   output, not "should pass" — FAIL IS FAIL).
3. The GitHub Actions run URL for both the green clean run and the red broken-branch run.
4. The explicit statement that the **product bet is not claimed** (WRONG PATHS e).
5. Record the outcome per house convention — append to `docs/USER_FIX_LIST.md` or the
   appropriate ledger. Do not silently close it out.

---

## When NOT to use this skill

- Any research, ops, debugging, or data task that is not literally building this P0 guard.
  For orientation use **asado-start-here**; for pipeline ops use **asado-operations**; for
  debugging use **asado-debugging-playbook**; for the experiment→harness→ledger lifecycle
  use **asado-research-protocol**.
- The **P2 blacklist de-duplication** (one importable constant across `evaluate_signal.py`
  and `triptych_kernel.py`) — that is a different FABLE.md improvement with its own bet.
- **Extending guard coverage to new leakage classes** beyond the two named here (e.g. the
  `guarded_connect()` adoption scan is a separate P1 in `FABLE.md:76-85`). A new leakage
  class = a new Divecha contract + a new campaign, not a patch to this one.

---

## Backup: the invariants the guard checks (use only if FABLE.md is missing)

If `FABLE.md` cannot be found in Phase 0, reconstruct the contract around these invariants
(the data-contract rules themselves — durable regardless of when you're reading this;
re-verify the cited file:line references live since exact line numbers can drift as the
source files change). Keep `schema_version: 1`,
`spec_id: ASADO-LEAKAGE-ISOLATION-GUARD-001`, `target_agent: either`.

- **INV1 — forward-return blacklist.** No NMRet/NDRet-family variable may be a registered
  signal in `config/family_registry.yaml`. Canonical set —
  `scripts/harness/evaluate_signal.py:146-149`:
  `{1MRet, 3MRet, 6MRet, 9MRet, 12MRet, 1DRet, 5DRet, 20DRet, 60DRet, 120DRet}`.
  Regex analog — `scripts/loop/triptych_kernel.py:86`:
  `^\s*\d+\s*[MD]\s*Ret\s*$` (case-insensitive). Enforced in the harness at
  `evaluate_signal.py:599-604`.
- **INV2 — isolated-table exclusion.** None of `ff_factors`, `jst_macrohistory` (JST
  corpus), `factor_returns`, `factor_top20_membership`, `country_factor_attribution` may
  appear as a source in the `feature_panel` or `unified_panel` view definitions
  (built by `scripts/build_normalized_panel.py`; `unified_panel` UNION-ALL in
  `scripts/setup_duckdb.py` ~`:920-953`).
- **INV3 — side-effect-free.** The guard modifies no file (`git diff --name-only` empty
  after a run) and holds no writable/long-held connection to `Data/asado.duckdb` or
  `Data/loop/asado_loop.duckdb`.
- **Gates:** G1 clean repo → exit 0; G2 seeded NMRet registration → nonzero naming the
  variable; G3 seeded isolated-table-in-view → nonzero naming the table; G4 `git diff
  --name-only` empty; G5 `validate_returns_first.py` + `pytest tests/` (deselecting
  `tests/loop/test_gap_engine.py::test_live_gap_engine_tables_if_present`) stay green.
- **scope.forbid:** `Data/asado.duckdb`, `Data/loop/asado_loop.duckdb`,
  `Data/processed/**`, `Data/raw/**`, `config/family_registry.yaml`, `ledgers/**`,
  `**/.env*`.
