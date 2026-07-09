---
name: asado-research-protocol
description: >
  The end-to-end lifecycle for running ONE research experiment in the ASADO repo at the
  house standard — hypothesis → snapshot → sandbox → pre-register family → run the harness
  (evaluate_signal.py / sweep_signals.py) → interpret the DEAD/WEAK/WATCH/INSUFFICIENT verdict →
  record it (ledger + experiment RESULTS.md + lesson on a kill). This is the "Sonnet runs the
  research factory" core. Use it when you are asked to test a signal/factor, backtest a
  cross-sectional country idea, run or design a sweep, register a hypothesis, or decide whether a
  finding is real. It carries the mandatory safety gates (forward-return blacklist, publication-lag
  default, pre-registration) and the earned cost laws inline. Do NOT use this skill to OPERATE the
  live pipeline or run nightly jobs (use asado-operations), to DEBUG a broken run or failing job
  (use asado-debugging-playbook), to change collector/warehouse/harness CODE (use
  asado-change-control), or merely to check whether an idea is already dead — do that FIRST via
  asado-graveyard, which this skill routes you to at STEP 0.
---

# ASADO Research Protocol — running one experiment at the house standard

You are (probably) a zero-context Sonnet session about to test a research idea in this repo. This
skill is the checklist and the guardrails. Follow it in order. The bar: a signal never reaches a
"this works" claim except through the harness, pre-registered, charged as a trial — and a dead
idea is recorded so it stays dead.

**Repo root (quote the space in the path):** `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO`

**Hard rules restated inline (a Sonnet reader must not need a second hop to avoid breaking prod):**
- **The main checkout IS production.** launchd runs whatever is checked out here. NEVER `git checkout`/`switch` branches in this tree. Code experiments use a git worktree (STEP 3).
- **Never hold a DuckDB connection.** Both `Data/asado.duckdb` and `Data/loop/asado_loop.duckdb` are one-writer-OR-many-readers. Even an idle read-only connection blocks the nightly writers (this caused the 2026-07-02/03 outage). Snapshot to parquet first (STEP 2); if you must touch a live DB, open→query→close in seconds.
- **FAIL IS FAIL.** No simulated success, no silent fallback. If a step fails, STOP and report the real error. If the failure is a bug in a monthly collector or the T2 feed, do NOT fix it mid-experiment — append it to `docs/USER_FIX_LIST.md` and tell the user.
- **A found PASS is guilty until proven.** Any WATCH/PASS produced by autonomous tuning or search is presumed false until re-derived from a pre-registered spec (see STEP 6, the `regime_loop` story).

---

## STEP 0 — Check the graveyard FIRST (non-negotiable)

Before you design anything, confirm the idea is not already settled. **Re-proposing a dead idea is
the fastest way to lose the user's trust.** Route to the **asado-graveyard** skill and run its full
§1 PROTOCOL — all five sources, in order (hypothesis ledger, methodology ledger, experiment
`RESULTS.md` files, `docs/strategy/lessons.md`, external Investment Learnings). Don't re-enumerate
that list here — it drifts out of sync with the canonical one (this line was itself once stale after
the methodology ledger was added); **asado-graveyard** §1 is the single source of truth for what to
check.

**Why the ledger alone is not enough:** `regime_ew` died at Gate 3 with NO ledger entry — kills can
live only in an experiment `RESULTS.md`. If asado-graveyard says the mechanism is dead, STOP and
report that to the user instead of re-running it.

Respect the **earned laws** before you spend a day on something (Investment Learnings
`Research-Agenda-2026-07-v2.md:57-67`): nothing survives 25bp one-way (only 4 signals ever cleared
10bp); index-space alpha ≈ 0 at the US-listed ETF close; first-order macro dies (31 DEAD) — only
delayed second-order propagation has survived; per-mechanism true-positive rate is 15-20%, so DSR
haircuts are mandatory; proxy engines lie (test in the real engine); only arithmetic/statute edges
never decay.

---

## The lifecycle (STEP 1 → STEP 7)

### STEP 1 — Write the hypothesis + mechanism BEFORE any data

Write down, in prose, before you look at a single number:
- **The mechanism paragraph — at least 15 words**, describing the economic reason the signal should
  predict *next-period cross-sectional country returns*. This is not optional flavor: the sha256 of
  `(signal_spec + mechanism_text)` is the pre-registration proof, and `register_hypothesis` RAISES
  `ValueError` if the mechanism is under 15 words (`scripts/loop/ledgers.py:199-200`).
- **Direction:** `higher_is_better` or `lower_is_better`.
- **Primary horizon** (months for monthly, trading days for daily). Frozen at registration so the
  gating horizon can't be reordered after you see results (`ledgers.py:185,194-195`).
- **The invalidation condition** — what result would kill it.

The mechanism is written first specifically so a losing result cannot be retro-explained.

### STEP 2 — Snapshot the inputs (never work off the live DB)

Freeze exactly the tables you need to parquet, then work off the parquet. This is rule 2 of
`experiments/README.md`. Verified usage (from `scripts/snapshot_for_experiment.py:67-108`):

```
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"   # always: repo root, production venv's python
venv/bin/python scripts/snapshot_for_experiment.py --db loop \
    --tables combiner_scores_daily,dislocation_daily --name my_exp

# See what tables exist first:
venv/bin/python scripts/snapshot_for_experiment.py --db loop --list
venv/bin/python scripts/snapshot_for_experiment.py --db main --list
```

Flags (all verified by argparse):
- `--db` **required**, one of `main` (→ `Data/asado.duckdb`) or `loop` (→ `Data/loop/asado_loop.duckdb`).
- `--tables` comma-separated table/view names (views materialize into parquet).
- `--name` experiment name → output goes to `Data/work/experiments/<name>/snapshot_<YYYY_MM_DD>/<table>.parquet` + a `MANIFEST.json` recording source DB, row counts, and freeze time.
- `--list` list tables and exit (`--tables`/`--name` not required with `--list`).

The script opens read-only and closes in a `finally` block — it never writes to any DB, and
re-running on the same day overwrites that day's snapshot (idempotent).

> The harness itself (`evaluate_signal.py`) reads the live DBs directly via `loop_connection()` for
> the actual measurement — that is by design (open→measure→close). Your *exploration* code must run
> off the snapshot; only the front-door harness run touches the live DB.

### STEP 3 — Set up the sandbox

Two output homes (rule 3 of `experiments/README.md`):
- **Committed code + small keepable results:** `experiments/<YYYY_MM>_<name>/` — e.g.
  `experiments/2026_07_my_exp/`. Put a `README.md` (question, hypothesis, snapshot used, verdict),
  your `run.py` (mandatory doc header, absolute paths), and a `results/` subdir.
- **Big/regenerable scratch + snapshots:** `Data/work/experiments/<name>/` (gitignored).

**Never write into** `Data/processed/`, `Data/loop/`, `Data/work/{t2,gdelt,econ,loop,…}`, `config/`,
or `ledgers/` from experiment code.

**If your experiment changes pipeline CODE** (not just runs a harness measurement), you must use a
git worktree so the main tree stays on `main`:
```
git worktree add "../ASADO-exp-<name>" -b exp/<name>
```
(This is the domain of **asado-change-control** — read it before touching collector/warehouse/harness code.)

**Isolate the environment** (rule 5): need new packages? Make a venv *inside your experiment dir*
with `uv venv`. NEVER `pip install` into `ASADO/venv` — the nightly pipeline depends on it. Avoid
holding long jobs 06:00–08:30 PT (the nightly quiet window).

### STEP 4 — Pre-register the family (HARD GATE)

Every signal must be classified into a research family in `config/family_registry.yaml`. The family
sets the deflated-Sharpe trial count `N` the signal is charged against — this is what stops an agent
from splitting trials into easy small-`N` families or pooling them to hide losers.

The family is resolved from the signal's **VARIABLE prefix**, not a free-text key you pick
(`config/family_registry.yaml:14-17`; matching = longest case-sensitive `startswith`,
`resolve_family` at `scripts/loop/family_registry.py:77-88`). Existing families include
`network_spillover` (prefixes `GRAPH`,`LL_`,`SIM_`), `eco_surprise` (`ECO_`), `fx_implied` (`FX_`),
`sov_curve` (`SOV_`), `valuation` (`VAL_`), `ml_combiner`, and more.

**What happens if the variable matches no registered prefix:** `register_hypothesis` raises
**`UnclassifiedVariableError`** (`scripts/loop/family_registry.py:49,82-88`, called from
`ledgers.py:203`). Adding a family is a deliberate trust-root edit to a git-tracked file — the
config guard reds the governance scorecard if `family_registry.yaml` is left dirty. Do not invent a
family to make an idea run; classify it honestly or STOP.

### STEP 5 — Run the harness (the ONLY path from idea to evidence)

Two front doors. Both pre-register, embargo, cost, and write the verdict back to the ledger
automatically — you cannot cheat the gates by construction.

**A. One signal — `scripts/harness/evaluate_signal.py`** (argparse verified `:986-1009`):
```
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
venv/bin/python scripts/harness/evaluate_signal.py \
    --hypothesis H_20260708_001 \
    --table feature_panel --variable EPU_CS --source epu \
    --direction lower_is_better \
    --frequency monthly \
    --start 2008-01-01 \
    --universe t2_34
```
- `--hypothesis` **required** — the id must ALREADY be in the ledger, or the run raises
  `PermissionError` ("not pre-registered … No anonymous backtests", `:719-724`).
- `--table`, `--variable` **required**; `--source` optional.
- `--direction` **required**, `higher_is_better` | `lower_is_better`.
- `--frequency` `monthly` (default) | `daily`.
- `--start` default `2008-01-01`.
- `--universe` default `t2_34`, OR a comma-separated list of exact T2 names for a narrow
  sub-universe (this scales the coverage gate and portfolio width — see the sub-universe trap).

**B. A family of signals — `scripts/harness/sweep_signals.py`** (argparse verified `:283-289`):
```
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
venv/bin/python scripts/harness/sweep_signals.py --spec config/sweeps/my_sweep.yaml
venv/bin/python scripts/harness/sweep_signals.py --spec config/sweeps/my_sweep.yaml --dry-run
```
- `--spec` **required** — a YAML in `config/sweeps/`. Each signal entry carries its OWN ≥15-word
  mechanism (no family-level boilerplate; validated at `sweep_signals.py:128-134`). Spec format is
  documented in the script header (`:52-68`): `sweep_name`, `family_key`, per-signal `name`,
  `table`, `variable`, `direction`, `mechanism`, and optional `source`, `frequency`, `archetype`,
  `start_date`, `universe`, `publication_lag_months`, `hold_days`, `horizons`.
- `--dry-run` validate + list, write nothing.
- `--force` **— do NOT use for re-measurement.** See the trap below.

Outputs: `evaluate_signal` writes the full result JSON to
`Data/loop/harness_runs/{hypothesis_id}_{ts}.json`, summary rows to the `harness_results` /
`harness_ic_series` tables, and the verdict event to `ledgers/hypothesis_ledger.jsonl`. Sweeps add
an incrementally-appended `sweep_summary.json` + `.xlsx` leaderboard under
`Data/loop/harness_runs/sweeps/{sweep_name}_{ts}/`.

### STEP 6 — Interpret the verdict

The harness returns exactly one of five verdicts (logic verified at
`scripts/harness/evaluate_signal.py:553-589`, coverage/history at the top of `decide_verdict`):

| Verdict | Exact condition |
|---|---|
| `INSUFFICIENT_COVERAGE` | coverage gate failed: needs ≥28 countries on ≥95% of dates (scaled for sub-universes). |
| `INSUFFICIENT_HISTORY` | fewer than 60 aligned months/dates. |
| `WATCH` | **ALL four** pass: NW-t primary ≥ 2.5 **and** ≥60% positive-IC years **and** net-25bps LS Sharpe > 0 (with top-7 excess > 0) **and** deflated Sharpe > 0. |
| `WEAK` | not WATCH, but NW-t primary ≥ 1.5. |
| `DEAD` | everything else. |

The four WATCH gates are AND-ed (`if g_t and g_years and g_cost and g_dsr: return "WATCH"`,
`:585-586`). The net-25bps requirement is the cost realism gate — see STEP-cost below. Deflated Sharpe
subtracts the expected max Sharpe of `N` pure-noise trials, where `N` is the family's running trial
count; more trials in the family ⇒ a higher bar. There is a WATCH-only value: 1 hypothesis is WATCH
out of 59.

**Reading a WATCH with suspicion (canon laws — cite the incidents):**
- **DISTRUST SEARCHED PASSES.** `regime_loop` p-hacked a v1 PASS. Its `output/state.json`
  confirms zero honest successes (`best_primary_metric=0.0`, `loop_status="error"`); the
  "13 attempts / agents gaming metrics by editing forbidden files" detail is from
  run-history review, not reconstructable from the current snapshot. Correcting the inputs
  flipped the verdict to DEAD (`regime2.md`, 2026-05-23). Any PASS found by tuning is
  presumed false until re-derived from a pre-registered spec you froze in advance.
- **IN-SAMPLE SELECTION CEILINGS.** `ml_combiner` — a 7-signal ridge built entirely from surviving
  signals — is DEAD at **-0.19 deflated Sharpe** in the ledger, *despite* being assembled from
  winners. A model whose features were chosen in-sample reports a ceiling, not an estimate; the
  daily combiner's own honesty note says exactly this (`loop_daily_job` combiner block). Do not read
  an in-sample combination as live alpha.
- **FULL-SAMPLE = DESCRIPTIVE ONLY.** Full-sample fits routinely look significant and then die on
  walk-forward (`regime_ew`: full-sample looked strong, no walk-forward lead, DEAD at Gate 3). The
  Triptych prior layer hard-zeroes full-sample confidence for this reason. Never promote a
  full-sample number.

### STEP-cost — Cost realism is the verdict gate

The WATCH gate is keyed to **net-25bps** long-short Sharpe, not gross. This encodes the earned laws
(costs from `evaluate_signal.py` header `:34-40, 79`, laws from AGENTS.md `:79` and Investment
Learnings):
- **Nothing survives 25bp one-way.** All 29 verdicted daily hypotheses die at 25bps.
- **At 10bp, exactly four signals** cleared net LS Sharpe > 0.3 (daily ridge combiner, GRAPHP bank
  gap, SIM twins 63d, GRAPH bank 63d) — breakevens cluster 8-14 bps: real but thin, futures /
  cheap-DM-ETF execution only.
- **1-day holds win NET for fast signals** — top daily signals decay faster with hold length than
  turnover savings accrue, so slowing them down doesn't rescue them; 21d holds only help genuinely
  slow signals (e.g. SOV_2S10S breakeven 15.8bps).

Every daily run also emits diagnostic `hold_period_grid` (same ranks re-costed at 1d/5d/21d) and
`breakeven_cost_bps_ls` (the one-way bps at which net LS return crosses zero; negative = loses money
even for free). These are diagnostic only — the verdict stays keyed to the registered hold.

### STEP 7 — Record the result (kills are the product)

1. **Ledger:** the verdict event is appended automatically by the harness — never edit
   `hypothesis_ledger.jsonl` by hand.
2. **Experiment `RESULTS.md`:** write the verdict, the numbers, and the mechanism into
   `experiments/<YYYY_MM>_<name>/RESULTS.md` (or the dir experiment's `results/RESULTS.md`). The
   ledger alone is not the graveyard — `regime_ew` died with no ledger entry, so its kill lives only
   here.
3. **On a kill, write the lesson.** A null is not a failed experiment — it is the deliverable.
   Record it honestly and, if the approach is a settled no-go, add it to `docs/strategy/lessons.md`
   so it enters the asado-graveyard corpus. Then **trim to reusable primitives**: keep the
   generic engine, delete the no-go methodology scripts (the pattern of commit `fbef913` — "trim
   no-go methodology scripts, keep reusable primitives"). A clean, well-recorded null is worth more
   than a p-hacked PASS.

---

## The traps — each with its story

These are the specific ways a careful session still breaks the accounting. Read them.

**1. Forward-return blacklist (NMRet / NDRet).** The `NMRet` family — `1MRet`, `3MRet`, `6MRet`,
`9MRet`, `12MRet` and the daily analogs `1DRet`, `5DRet`, `20DRet`, `60DRet`, `120DRet` — are
FORWARD returns labeled at the *start* of their window, i.e. they are the optimizer's TARGETS. Using
one as a predictor is pure lookahead: `H_20260610_001` produced a fake IC of 0.25 this way. The
harness refuses them outright. Canonical set: `scripts/harness/evaluate_signal.py:146-149`; the same
set is re-derived at `scripts/loop/triptych_kernel.py:84-90` as a regex (this duplication is a known
P0 risk — if you add a forward-return variable, both lists must change). **Never register an
NMRet/NDRet variable as a signal.**

**2. Publication-lag default.** For a MONTHLY signal, if the source is not one of the market-derived
zero-lag sources (`t2`, `gdelt`, `graph`, `t2_optimizer`, `gdelt_optimizer`, `econ_optimizer` —
`ZERO_LAG_SOURCES`, `evaluate_signal.py:138`), `infer_publication_lag` assigns a conservative lag
from the observed sampling frequency: **monthly → 1 month**, quarterly → 3, annual → 12
(`:682-701`). **Consequence:** a *market-derived monthly table that is not one of those sources*
(e.g. combiner scores materialized into a plain table) will be tested a month STALE unless you set
`publication_lag_months: 0` explicitly in the spec. This actually bit the graph/lead-lag PIT re-test
(AGENTS.md `:77`). For daily signals the embargo is per-variable and **fails closed to 1 trading
day** unless the source is zero-lag or a passing `pit_proof_registry.yaml` entry grants a specific
lag (`daily_publication_lag_days`, `:663-679`; `CONSERVATIVE_DAILY_LAG_DAYS = 1`, `:647`).

**3. Sweep dedupe hash.** A sweep skips (reports "cached") any signal whose recipe hash already has
a verdict in the same family, so re-running a sweep does not double-charge the family. **The hash is
over `SIGNAL_KEYS_FOR_SPEC = (table, variable, source, publication_lag_months, hold_days)` plus the
mechanism text** — `sha256(json.dumps(spec, sort_keys=True) + mechanism)` (`sweep_signals.py:107-109`
for the key set, `:149-154` for the hash). It does **NOT** include `start_date` or `universe`
(verified) — so a coverage/period
re-spec collides with the old hash and gets cached; to re-measure it you need a distinguishable spec
(changed table/variable/source/lag/hold or changed mechanism text) or `--force`.
> Precise note: the code hash does **not** include `direction` either, even though AGENTS.md `:77`
> lists "direction" among the hashed fields — trust the code. A pure direction flip with identical
> mechanism text would be treated as cached; register a contrarian flip with its own (contrarian)
> mechanism paragraph, which changes the hash anyway.

**4. NEVER `sweep_signals.py --force` for re-measurement.** `--force` registers a NEW hypothesis and
charges a NEW trial — by design, for genuinely new candidates. If you use it to re-measure an
existing signal (e.g. to pick up a harness upgrade), you duplicate the registration, inflate the
family's trial count `N`, and **corrupt every deflated Sharpe in that family** (a higher `N` raises
the noise bar for everyone). The correct re-measurement path is to call `evaluate_signal` with the
*existing* `hypothesis_id` and stored params — the re-verdict event appends, the fold (the
nightly ledger step that dedupes each hypothesis to its latest verdict) keeps the
latest, ZERO new registrations (this is exactly how all 29 daily hypotheses were re-costed for the
v2.1 upgrade, AGENTS.md `:79`). This is also rule 4 of `experiments/README.md` and AGENTS.md `:32`.

**5. Declare honest sub-universes.** Some signals only exist for a structurally narrow set of
countries (FX options surface ≈ 26 stable names, daily 2s10s ≈ 20, growth-surprise composite ≈ 14;
1Y CDS is too thin to cross-sectionally rank — event-study only). When you pass a narrow
`--universe`, the harness scales the coverage gate to `max(10, ceil(0.8*n))` and the portfolio width
to `max(3, n//3)` (AGENTS.md `:73`). Declare the honest universe a signal actually covers — do NOT
pad it with countries that have no data to dodge the coverage gate, and do NOT claim a 34-country
WATCH from an 18-country sub-universe.

**6. Full-sample results are descriptive only** (restated from STEP 6): the Triptych prior layer
hard-zeroes full-sample confidence; `regime_ew`'s full-sample fit was a look-ahead artifact caught
only by walk-forward gates. If a number came from fitting on all the data at once, it is a
description of the past, not evidence.

---

## What a finished experiment looks like (checklist)

- [ ] STEP 0 done: asado-graveyard checked; the mechanism is not already dead; earned laws respected.
- [ ] Mechanism paragraph (≥15 words), direction, primary horizon, and invalidation written BEFORE any data.
- [ ] Inputs snapshotted with `snapshot_for_experiment.py`; exploration ran off parquet, not a held DB connection.
- [ ] Sandbox under `experiments/<YYYY_MM>_<name>/` (+ `Data/work/experiments/<name>/` scratch); own venv if new packages; no writes into protected dirs.
- [ ] Family pre-registered in `family_registry.yaml` (no `UnclassifiedVariableError`); no forward-return variable used.
- [ ] Harness run through the front door; verdict written to the ledger automatically.
- [ ] Verdict interpreted against the exact gates; any WATCH treated as guilty until pre-registered re-derivation.
- [ ] `RESULTS.md` written; on a kill, the lesson recorded (and `docs/strategy/lessons.md` updated if it's a no-go), code trimmed to reusable primitives.
- [ ] Report to the user: the verdict, the net-25bps number, and the honest universe — link the result JSON and `RESULTS.md` with `file://` paths.

**A null is the product.** Record it honestly. Do not simulate a PASS, do not soften a DEAD, do not
bury a surprising result.

---

## When NOT to use this skill

- **Operating or running the live pipeline** (nightly loop, manual `daily_update`/`monthly_update`
  runs, health checks, frontends, MCP) → **asado-operations**.
- **A harness run or job is broken/erroring** (lock errors, missing tables, crashed detector,
  launchd failures) → **asado-debugging-playbook**.
- **Changing collector / warehouse / harness / loop CODE** (not just running a measurement) →
  **asado-change-control** (and use a git worktree — never edit the production checkout on `main`).
- **You only want to know if an idea is already dead** → **asado-graveyard** directly (that is STEP 0
  here; you don't need the whole lifecycle to answer "has this been tried").
- **Orientation / which doc is authoritative / current repo state** → **asado-start-here**.
