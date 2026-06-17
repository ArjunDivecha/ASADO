# Maintaining Judgment Across the ASADO Stack
### An operating model for a one-human-plus-rotating-agents research institution

**For:** Arjun Divecha · **Date:** 2026-06-17 · **Status:** Proposal — DESIGN ONLY (no code written; per the "ask before writing code" rule)

**What this is / how it was produced.** A research-backed operating model answering the question: *now that ASADO has crossed from a data project into a small research institution, how do you maintain judgment across the whole stack?* It was produced by a multi-agent workflow: 4 agents read the live ASADO code/ledgers/docs to inventory where judgment leaks; 7 deep-web-research agents covered quant multiple-testing/alpha-decay, ML technical debt, data observability, research-org memory, calibration science, agentic-research governance, and model-risk management; 3 competing operating models (automate / institution / epistemic) were drafted, adversarially critiqued, and integrated. Every defect named below was verified against the working tree on 2026-06-17. **Inputs read:** `scripts/harness/evaluate_signal.py`, `scripts/loop/ledgers.py`, `scripts/loop/build_dislocations.py`, `scripts/loop/loop_daily_job.py`, `scripts/loop/calibration_report.py`, `diagnostics/spectral.py`, `ledgers/*.jsonl`, `Data/loop/calibration/calibration_2026_06.md`, `AGENTS.md`, `llmchat.md`, `docs/USER_FIX_LIST.md`, `docs/SPECTRAL_DIAGNOSTICS.md`, `PRD_Alpha_Hunting_Loop.md`. **This file (output):** `docs/JUDGMENT_OPERATING_MODEL_2026_06_17.md`.

---

## 1. Diagnosis — what "maintaining judgment across the stack" actually means right now

ASADO has crossed from a data project into a small research institution, and its hard problem is no longer adding data — it is **keeping every layer's claims trustworthy when one human cannot eyeball 17.4M rows, ~1,400 variables, 33 nightly steps, and a firehose of agent-generated hypotheses.** The encouraging truth first: the *hardest* parts are already right. Pre-registration is load-bearing (`sweep_signals.py` registers every candidate mechanism-first before scoring; the honest 39 WEAK / 31 DEAD / 16 INSUFFICIENT / 2 WATCH base rate proves the skeptic actually kills things), the forward-return blacklist fires inside `load_signal()`, verdicts can only be written by the harness, and the isolation/cycle guards are enforced in code. This is the **idea-counting problem inside the harness**, and on that problem ASADO is at or above professional standard.

The failure is structural and singular: **almost every governance instrument is a capability sitting *beside* the pipeline, not a checkpoint *inside* it** — and the discipline that is supposed to be enforced actually lives in the wrong substrate. Grep confirms `evaluate_signal.py`, `ff_spanning.py`, and `diagnostics/spectral.py` are invoked by *neither* `loop_daily_job.py` nor `monthly_update.py`. The detectors and the combiner ship to Neo4j and the brief **continuously bypassing the skeptic**. Concretely, judgment leaks through:

1. **A free-text string sets the central anti-overfitting statistic.** `family_key` in `register_hypothesis()` (`scripts/loop/ledgers.py`, the only check is `if not family_key`) sets the deflated-Sharpe denominator `N` consumed at `evaluate_signal.py:783`. The live ledger already shows the distortion: one network-spillover mechanism is **split** across `graph_trade_gap` (N=15), `leadlag_2026_06` (N=6), `fund_similarity_2026_06` (N=2) — each getting an easier `E[max Sharpe]` bar — while **five distinct mechanisms are over-pooled** into `bbg_skill_2026_06` (N=16). The headline overfitting protection (Bailey & López de Prado's **deflated Sharpe**) is honest only by accident.

2. **A blanket assumption grants the entire daily layer tomorrow's information.** `infer_publication_lag()` (`evaluate_signal.py:645`) returns `0` for *every* daily signal unconditionally; the `ZERO_LAG_SOURCES` guard is bypassed on the daily path, so `graph_pit`, `combiner`, `leadlag`, `fund_similarity` all resolve `publication_lag_months=0` despite not being whitelisted. **This is the GSAB10YR failure *shape* at the validation layer** — a provenance assumption no detector watches — and it silently invalidates the embargo for most of the live signal surface.

3. **Calibration governs nothing because the closed-thesis sample is ~0.** `thesis_ledger.jsonl`: 3 opens, 28 marks, exactly **1 close** — and that one is `killed_review`, `outcome=null`, contributing nothing to Brier. `calibration_report.py` slices by `author`, but 100% of authors are the string `"agent-overnight"`, and `open_thesis()` has **no `model_id`** — so the single most decision-relevant axis under a rotating-frontier-model labor model ("which model do I trust to size up?") is *unrecorded and unrecoverable for every thesis opened so far.*

4. **The canonical "what passed" key is never reconciled with retirement.** `fold_hypotheses()` overwrites `verdict` only on a `hyp_verdict` event; `H_20260610_001` (the retired 12MRet look-ahead that produced a fake IC=0.25) **still folds to `verdict='WATCH'`** while `status='retired'` lives in a field a consumer keying on `verdict` won't read. The system's strongest cautionary tale is still labeled WATCH. Worse, `fold_theses()` has **no branch for `thesis_review`** — three hand-written review events are silently dropped (a FAIL-IS-FAIL violation), and the `killed_review`/null-Brier path is a soft escape hatch for pruning losers before they close mechanically.

5. **Silent data corruption has no automated detector — the proven failure mode.** The GSAB10YR ticker fed **South Africa's sovereign data into Saudi Arabia's series** for an unknown period, caught only by a manual Bloomberg Terminal re-audit. That swap passed freshness, volume, schema, and single-series range — it was visible *only* as a broken cross-source relationship. Nothing in the pipeline catches the next one. And `setup_duckdb.py` **deletes and recreates `asado.duckdb` every cycle**, so there is no value-level cross-month diff to catch a silent *restatement* (an in-range number that changed) either.

6. **Memory is unguarded trusted prose, and the engine's failures have no listener.** `AGENTS.md` (59 dense lines) mixes a constitutional isolation rule and a Bloomberg ticker that died last week as visually identical lines, with no source, no expiry, no re-validator — so a wrong fact propagates to *every* future session (GSAB10YR at the memory layer, wider blast radius). Meanwhile `loop_daily_job.py` correctly exits non-zero on failure (real FAIL-IS-FAIL) but **shouts into a log file with no listener** — a multi-day brief gap (06-12 → 06-16) was caught *by eye*, and two real briefs (06-15, 06-16) sit **uncommitted on disk right now**.

7. **The agent firehose + honor-system exploration.** `db_bridge.AsadoDB` and the MCP give agents unlogged read access to `feature_panel`/returns *outside* the harness; an agent can peek, then register a "mechanism" post-hoc (H_20260610_001 registered and verdicted one wall-clock second apart). Pre-registration is honest for in-harness sweeps but blind to HARKing informed by out-of-harness exploration.

**The through-line:** ASADO's guarantees are airtight where the work is *idea-counting* and leak exactly where *judgment re-enters through a string, an assumption, an empty sample, an un-reconciled field, a docstring, or a log nobody reads.* The job of this operating model is **not to redesign the constitution, the PIT embargo, deflated Sharpe, or the isolation guards** — they meet best practice. It is to **wire the honest instruments to the engine so they cannot be skipped, and convert every control that depends on a human remembering into a script that fails loudly without human action.**

---

## 2. Resolving the philosophy tension (automate vs. institution vs. epistemic)

The three lenses are not equally right everywhere. The decisive ruling, stated once:

- **EPISTEMIC wins on *what to govern*.** The right mental model is the epistemic candidate's: every component (detector, signal, model, agent-session, the human) is a **scored, falsifiable, killable** thing, and — because outcome-based trust is *1–3 years away* at ~1 close/week — near-term governance must lean on **process quality (gradable at n=1) + hierarchical shrinkage**, not on calibration statistics that won't be significant for years. This is the honest core.

- **INSTITUTION wins on *the spine*, but only its irreducible core.** Borrow **SR 11-7 / SR 26-2**'s skeleton — inventory + independent validation + effective challenge + ongoing monitoring — *minus the committee, the calendar reviews, and the data-contract/ML-Test-Score/SCD-2 apparatus*, which are multi-team ceremony that will rot under solo labor. The institution candidate, taken whole, becomes a governance *program* rather than a few un-bypassable gates.

- **AUTOMATE wins on *enforcement and delivery*.** Its diagnosis ("the discipline lives in the wrong substrate") is the sharpest articulation of the problem, and its mechanism — **deterministic git hooks + nightly jobs that exit non-zero, all converging on ONE scorecard + ONE push on red** — is the only enforcement model that survives solo+agents (Anthropic's own finding: humans approve **93%** of permission prompts, so advisory rules rot and only hooks bite).

- **Where they collide, three explicit calls:**
  1. **One inventory, not two ledgers.** The epistemic "trust ledger" and the institution "model inventory" are merged into a **single** `model_inventory.jsonl` with a *trust block* inside each row. A second parallel ledger would re-create the very free-text ambiguity (`family_key`) it criticizes.
  2. **The auditor/skeptic agent is ADVISORY, never a hard freeze-blocker.** A different-provider skeptic agent as a loop step that *blocks* a thesis freeze on DISAGREE is, for solo+agents, the *highest-rot* surface (second-provider key management, latency, nondeterministic DISAGREE either stalls the nightly job or trains the operator to override — rubber-stamp in reverse). It writes a DISAGREE line on the scorecard; the *deterministic* gates do the blocking.
  3. **Cap new durable artifacts at ~3 stores** (the inventory, a facts store, an ADR dir) + a handful of YAML configs. The institution candidate's full 8-artifact menu is itself the infeasibility.

**The acceptance test applied to every mechanism below:** *if a control cannot be expressed as a script that exits non-zero without human action, it is downgraded to advisory or cut* — because under solo+agents, anything that depends on remembering will rot, and the GSAB10YR manual re-audit is the proof.

---

## 3. The operating model — 8 load-bearing mechanisms

Everything is one of eight mechanisms. Each names the artifact it lives in, exactly what runs and when, and how it fails loudly.

### M1 — The Model Inventory (the spine that ASADO lacks)

**(a) What it is.** ASADO has ledgers for *hypotheses* and *theses* but **no inventory of the models themselves** — which is precisely why meta-diagnostics (spectral, FF, JST) and the live detectors float ungoverned. M1 is the single governing layer: SR 26-2's irreducible core adapted to a flat file. The **designation rule** (the load-bearing sentence): *if an artifact's output can influence capital, seed a thesis, OR change the validation verdict of another model, it is a MODEL and gets a row.* That last clause is what forces the highest-leverage, least-governed artifacts — the maps that judge other models — into governance.

**(b) Artifact.** `ledgers/model_inventory.jsonl` (append-only, git-tracked, folded into a `model_scores` table in `asado_loop.duckdb` — **never** `asado.duckdb`, which is wiped each rebuild). One row per artifact:
```
{model_id, tier, owner, inputs, output, purpose,
 trust:{shrunk_hit, resolution, spiegelhalter_z, last_scored},
 falsifier,            # MANDATORY, machine-checkable — register() RAISES without it
 kill_criteria, isolation_control, status, registered_ts}
```
Tiers: **T1** = trust-as-ground-truth (`combiner_scores_daily`, `country_returns`, direction-implying D1–D4/D9/D10); **T2** = decision-support (D5/D8 LOOK-only, `eco_surprise_signals`); **T3** = meta-diagnostics that judge other models (spectral trio, `ff_spanning.py`, JST tables) — **monitored as T1-for-trust** precisely because a wrong map silently corrupts every downstream verdict.

**(c) Enforced by.** `scripts/qa/build_model_inventory.py` auto-discovers detector constants in `build_dislocations.py` and output tables in `asado_loop.duckdb`, runs in `monthly_update.py`, and **mirrors `validate_variable_registry.py`'s coverage gate** — it is self-maintaining, not hand-curated.

**(d) Fails loudly.** The build step **exits non-zero on any un-inventoried model-designated output** (a new detector, a new `*_daily` table with no row), and `register()` raises if a row lacks a machine-checkable `falsifier`. (Inventory + independent validation + effective challenge + ongoing monitoring is the **SR 11-7 / SR 26-2** irreducible core; "is this factor real?" is governed against **Harvey-Liu-Zhu**'s t>3 bar, not 2.0, given the search space.)

### M2 — Four un-bypassable harness/ledger gates

**(a) What it is.** The four judgment leaks (§1.1–1.4) are each closed by a small mechanical fix in code, turning the harness from a capability-beside into a checkpoint-inside.

**(b)–(c) Artifacts + enforcement.**
- **Gate A — Family canonicalization.** `config/family_registry.yaml` maps `(archetype, source, variable-prefix, mechanism-class) → one canonical family_key`. `register_hypothesis()` resolves the caller's string against it and **raises on an unrecognized key** (no silently minting a small-N easy family). A validator in `loop_daily_job.py` asserts `graph_trade_gap`/`leadlag`/`fund_similarity` collapse to one `network_spillover` family and `bbg_skill`'s five mechanisms split out. *N becomes a property of mechanism, not of which YAML an agent authored.*
- **Gate B — Per-variable publication lag.** Replace `if frequency=='daily': return 0` with a lookup into `config/publication_lag.yaml` keyed *by variable*, **defaulting to a conservative non-zero lag**; a daily variable earns lag 0 *only* by carrying a `pit_proof` pointer to the test that demonstrates its inputs are point-in-time. A `graph_pit` edge-vintage **canary in `tests/loop/`** asserts the weight at date *t* uses only vintages published `< t`. (This is the formal **point-in-time-correctness / feature-store embargo** discipline made per-variable instead of blanket.)
- **Gate C — Verdict/status reconciliation + the canonical live view.** `fold_hypotheses()` gets one invariant: `status ∈ {retired, rejected}` **nulls/overrides** `verdict`; the canonical "what is live" is a single DuckDB view `live_signals` (`WHERE status NOT IN ('retired','rejected')`). A test asserts `H_20260610_001` is absent from `live_signals`.
- **Gate D — FAIL-IS-FAIL on the ledger reader.** `fold_theses()` gets an explicit `thesis_review` branch and **raises on any unknown event type**; `_append_event` validates against a known schema; the `killed_review` loser-pruning hole is closed with a distinct, auditable `outcome='void'` that is visibly *not* a mechanical close.

**(d) Fails loudly.** Each gate raises/exits non-zero; Gate A and the `live_signals` test run in the nightly job so a violation is caught before the morning bootstrap.

### M3 — The pre-registration + no-bypass git hook (the highest-leverage single move)

**(a) What it is.** The harness is the bottleneck only if it cannot be routed around. `.git/hooks/` is **empty today** — repo-tracked hooks are free leverage.

**(b) Artifact.** `.githooks/` (activated by `git config core.hooksPath .githooks`), running `scripts/qa/validate_memory.py` + a path→required-check mapper.

**(c) Enforced.** On every commit (and as the *first and last step* of `loop_daily_job.py`, to catch a 2am autonomous defect before morning): (i) **pre-registration gate** — any `thesis_ledger` freeze whose `hypothesis_id` lacks an *earlier-timestamped* `hyp_register` is rejected, protecting the deflated-Sharpe N; (ii) **append-only enforcement** — a commit mutating a prior line of `llmchat.md`/`*_ledger.jsonl`/`facts.jsonl` (git-diff vs HEAD) is rejected, making the append-only ledger an *enforced* invariant, not a social convention; (iii) **path→check mapper** — touching `evaluate_signal.py` requires `tests/loop/test_harness_pit.py` green, a collector edit requires `validate_returns_first.py` green, a `build_dislocations.py` D1 edit requires `validate_d1_episodes.py` green (stops **implementation drift** — an agent quietly loosening an embargo to make a favored signal pass).

**(d) Fails loudly.** Exit non-zero blocks the commit (FAIL-IS-FAIL). This is the mechanism that makes "the model never marks its own homework" *structural* rather than aspirational — the 93%-approval finding is exactly why it must be a hook, not a habit.

### M4 — Nightly data-integrity sweep (the GSAB10YR defense)

**(a) What it is.** The missing **Distribution + cross-source-consistency pillars** of data observability (Barr Moses / Monte Carlo's five pillars). A swap passes freshness/volume/schema; it is visible *only* as a broken relationship or a series tracking the wrong entity.

**(b)–(c) Artifacts + enforcement.** New steps in `loop_daily_job.py`, all writing to `asado_loop.duckdb` and the scorecard:
- **D11 cross-source consistency** in `build_dislocations.py`: redundant independent country views must agree — Bloomberg sovereign 10Y vs its own 5Y CDS, **`bloomberg_factors` vs `sovereign_daily` on overlapping series** (the overlap that made GSAB10YR catchable at all), IMF GDP vs WEO vs OECD — plus a **nearest-cross-sectional-neighbor-flip alarm** (Saudi's 10Y suddenly tracking South Africa's). *Critical feasibility fix:* the "should-agree" pairs are **auto-derived from historical top-k correlation and frozen**, never hand-curated (a hand list rots as variables churn). A month-end `sovereign_daily`-vs-`bloomberg_factors` level assert would have failed *the day* GSAB10YR was wired wrong.
- **Cross-sectional + level-shift sweep** (`scripts/qa/observability_sweep.py`): reuses the `_CS` z-score math already in `t2_normalize.py`/`econ_normalize.py`. Catches units changes (% → bps), decimal shifts, sign flips, flatlines. **Ruthlessly severity-tiered to avoid the alert-avalanche anti-pattern** across 1,400 vars: fire only on **|z|>5 sustained N days**, roll up to **one scorecard line per source**, never per variable.
- **Cross-month value-drift alarm** (closes the coverage gap no candidate had): because `setup_duckdb.py` destroys `asado.duckdb`, a per-variable distribution/checksum diff is run against `Data/backups/` panels to catch a silent **restatement** (an in-range number that changed and tracks no other country — the one thing D11 misses).
- **Sentinels** (`config/sentinels.yaml`): ~3–5 manually-verified `(variable, country, date, expected_value, tolerance)` anchors per critical source. A ticker swap fails the exact-match assertion *instantly*, with zero statistical subtlety — a hard FAIL-IS-FAIL stop.

**(d) Fails loudly.** Breaches write to the scorecard; a sentinel failure or a `NAME`/country mismatch on the ~5 nightly BBG ticker re-resolutions (asserting the mapped T2 country matches `config/country_mapping.json`) is a hard stop + a `USER_FIX_LIST.md` entry. This **automates the manual Terminal re-audit that was the only mechanism that ever caught the swap.**

### M5 — Calibration-as-governance (honest at the n it will actually have)

**(a) What it is.** Turn the hollow PARTIAL scaffold into a control by confronting the binding constraint: a significant per-model/per-detector cell is **1–3 years out** (~1 close, 21–42d horizons), so a 2/2 detector would otherwise top the book.

**(b)–(c) Artifacts + enforcement.** All in `calibration_report.py` + `ledgers.py`:
- **Stamp `model_id`/`model_version`/`session_id` at `thesis_open` and `hyp_register` — this week.** Irreversible if skipped: every thesis opened without it is *permanently* un-attributable, and 2025 evidence is that RLHF often makes the *flagship* the most overconfident author — invisible until stamped. Add a `("By model","model_id")` slice.
- **Hierarchical Beta-Binomial shrinkage** (the antidote to over-updating on tiny cells): report `trust_hit = (hits+α)/(n+α+β)` with prior = pooled rate; **governance reads `trust_hit`, never raw `hit_rate`** (~30 lines). A 2/2 detector sits near the grand mean until it earns out.
- **Murphy decomposition (reliability − resolution + uncertainty)**: govern retire/promote on **resolution**, not Brier — a perfectly-calibrated-but-non-discriminating detector is worthless even with a clean Brier. Flag `resolution ≈ 0` as "do not size."
- **Spiegelhalter z + Beta credible interval per cell**: replace the binary `MIN_CLOSED_FULL=10` gate with "act only when the credible interval excludes the grand mean."
- **Process-quality fields gradable at n=1** (the honest near-term lever): mandatory machine-checkable `invalidation_rule` + named `premortem_failure_mode` (past tense) on `thesis_open`; the auto-marker tags every close **`foreseen` vs `surprise`**. Surface the by-archetype `trust_hit` as the **reference-class prior** an agent reads at open, flagging stated-p deviations >0.15 without an override note. (**Tetlock/Brier** scoring; reference-class anchoring scored Brier 0.17 vs 0.26 in GJP; Klein's pre-mortem raises failure-cause identification ~30%; Annie Duke's process-vs-outcome "resulting" inverted for a low-volume shop.)
- **Log Arjun as a forecaster**: on every override/veto/size, write `author='arjun'` + his own probability, so the human appears in the *same* table as the models — the only way to learn when to defer vs override.

**(d) Fails loudly.** The report stays stamped PARTIAL and *refuses to extrapolate below the credible-interval threshold* — it says "noise, do not act" loudly rather than inviting resulting on n=1.

### M6 — Meta-diagnostics: falsifiable, scheduled, never trusted on faith

**(a) What it is.** The T3 maps must earn authority or be labeled "theory-only." The sharpest finding in the whole review: `diagnostics/spectral.py`'s `load_design_from_duckdb` is a **`NotImplementedError` stub (line 367)** — the single diagnostic that would tell ASADO whether the IC plateau is even *beatable* (where to spend search compute) **has never run.**

**(b)–(c) Enforced.**
- **Spectral.** Wire `load_design_from_duckdb` to the `unified_panel`/factor-return design and **run it once** into `Data/loop/diagnostics/spectral_YYYY_MM.json` + a dated "Empirical readings" table in `SPECTRAL_DIAGNOSTICS.md`. **Pre-register the falsification condition *before* running** (the exact X, y, window, and the numeric reading that CONFIRMS vs REFUTES "plateau is information-theoretic", e.g. source-condition slope `s' ≤ −0.5`; *if a later harness trial earns NW-t>3 on the same target, the diagnostic was wrong and is flagged*). This is the **Gelman-Loken "garden of forking paths"** defense — an un-pre-registered diagnostic re-specified post-hoc *always* "confirms." Until run, the doc is labeled **"theory-only, no live reading"** and may not be cited to justify compute allocation. Re-runs on the monthly vintage refresh.
- **FF-spanning becomes a registration *gate*, not a manual capability**: no signal is surfaced as a live Neo4j rank until `ff_spanning.py` has run on its long-short P&L and the alpha-t is recorded in M1 (is the IC just regional momentum/value/size beta?). The U.S.-β≈1 sanity check already passed; the gap is it's manual-only.
- **JST tail** stays structurally isolated (verified COUNT=0 in `feature_panel`) and context-only; its isolation is recorded as the `isolation_control` field in M1 so an overnight session can't quietly un-isolate it, and EM-analogy rows keep their `scope=EM-analogy` label. Falsifier: it earns a *detector* designation only after harness validation, never by sitting in the brief next to tradeable rows.
- **Alpha decay as a monitored quantity**: fit `α=K/(1+λt)` on each T1 signal's live-IC history; persistent negative residuals = crowding → auto-downgrade to `watch`. A flat-Sharpe threshold misreads hyperbolic, ETF-accelerated decay.

**(d) Fails loudly.** A diagnostic past its `review_after` or with no live reading is flagged on the scorecard; a signal reaching the Neo4j rank without an FF-spanning verdict is blocked by M1's gate.

### M7 — The combiner is a CHALLENGER, governed by champion-challenger kill criteria

**(a) What it is.** `combiner_scores_daily` is README/CLAUDE.md-described as "the strongest registered signal (IC 0.057, NW-t 10.7)" and pushed nightly to Neo4j as live ranks — but its own HONESTY NOTE says components were selected **in-sample 2026-06** and **deflated Sharpe is still negative.** By ASADO's *own* constitution it has **not earned champion status**, and the caveat lives only in a docstring no Layer-2 agent reads.

**(b)–(c) Enforced.** Register it in M1 as a **challenger** with pre-registered kill criteria, **auto-evaluated nightly by a harness replay step in `loop_daily_job.py`** (the move that turns the harness into a *checkpoint*): any one, sustained over a min window — (a) live OOS rank-IC < 0.5× registered IC for N consecutive 21d windows; (b) deflated Sharpe stays negative on rolling OOS; (c) hyperbolic-decay residual persistently negative; (d) FF-spanning alpha loses significance. It earns champion *only* when rolling-OOS deflated Sharpe turns positive *from its June-2026 registration date forward*. The honesty caveat **moves from the docstring to the Neo4j rank and the brief** — the point of consumption. (Champion-challenger with explicit kill criteria; **deflated Sharpe / PBO** as the bar.)

**(d) Fails loudly.** A fired kill criterion auto-marks the combiner DEAD/WATCH in `thesis_ledger.jsonl` and flags it on the scorecard — no human cron-memory.

### M8 — Memory hygiene: Diátaxis split, verifiable facts, ADRs, and the one scorecard

**(a) What it is.** Stop both memory failures: stale-fact poisoning (a wrong `AGENTS.md` line propagates to every future session) and re-litigation of settled decisions (an agent re-adds `is_optimizer_selected` or tiles FF to 34 countries).

**(b)–(c) Enforced.**
- **Diátaxis split** (mixing modes degrades all of them): `AGENTS.md` → *procedures only*; `Data/loop/facts.jsonl` → one record per verifiable fact `{claim, source_of_truth, verify_cmd, ttl_days, last_verified, status}`; `docs/decisions/` → settled choices. A nightly `scripts/qa/verify_facts.py` runs each `verify_cmd`, flips status to `stale` past TTL, and writes a STALE-FACTS line to the scorecard (Bloomberg tickers TTL 30d; schemas until next `setup_duckdb`; isolation rules never). `verify_cmd`+TTL turns "trust the prose" into "trust, then cheaply verify" — the antidote to GSAB10YR-at-the-memory-layer.
- **ADRs adapted to solo+agents** (Nygard format + a `Falsifier` + `Review-after` field): back-fill ~6 load-bearing decisions buried as `AGENTS.md` prose — isolation rule, optimizer cycle break, forward-return blacklist, harness-sole-verdict-source, DuckDB+Neo4j split, **Regime forecasting REJECTED (AUC 0.46)** with falsifier "a walk-forward regime classifier earns OOS AUC>0.55 on a registered harness trial." `AGENTS.md` lines *point to* ADR ids; **no informal reopening (Rust-RFC rule)** — only a superseding ADR Arjun accepts. The Falsifier threads the needle: settled *against opinion*, auto-reopened *against evidence*.
- **The one consumption surface.** All eight mechanisms converge on a **nightly Data-Health + Governance Scorecard prepended to `Data/dislocations/brief_YYYY_MM_DD.md`** (the file Arjun already reads): one red/amber/green line per source (the five pillars), the day's D11/drift breaches, combiner kill-criteria status, meta-diagnostics past review, stale-fact count, dead-family count, and the **loop liveness heartbeat**. **Green = "trust the warehouse, don't re-check"** — that is what buys back the hand-auditing time. Light mode only, per project rules.

**(d) Fails loudly — the listener the log never had.** A `PushNotification` fires on **any non-zero loop exit OR a missing/uncommitted brief** (closing the gap where the 06-12→06-16 outage was caught by eye, *and* the human-commit-gate SPOF — the heartbeat asserts the latest brief is **committed, not just on disk**, since two briefs are uncommitted right now). A monthly `memory_health_report.py` (`.xlsx`, with `file://` link per project rules) skims stale facts, broken `verify_cmd`s, and ADRs past `review_after`.

---

## 4. The agentic-labor problem, addressed head-on

The labor model is one human + rotating frontier-model sessions running sometimes-overnight and autonomous. Each named risk maps to a mechanism above; the residual decisions:

- **Marking own homework.** Verdicts already come only from the harness; M3's pre-registration + no-bypass hook extends "can't grade your own work" to *fact-writing and thesis prose*. The skeptic/auditor agent stays **advisory** (writes a DISAGREE line to the scorecard, never blocks the freeze) — because a different-provider model call inside the nightly job is the highest-rot surface (key management, latency, nondeterministic DISAGREE → rubber-stamp-in-reverse). **Self-preference bias** (an LLM judge favors its own lower-perplexity output) means *if* the advisory skeptic is ever invoked, it must be a different model family from the author, fed only raw harness JSON + the brief, and told to flag correctness gaps only (not style — chasing every reviewer finding causes over-engineering). **Who checks the auditor?** Nobody needs to, because it has no veto — the deterministic gates (M2/M3) do the blocking, and the auditor only adds a visible second opinion.

- **Stale-doc poisoning.** M8: `facts.jsonl` with `verify_cmd`+TTL + the nightly `verify_facts.py` sweep; ADRs replace re-litigable prose. A wrong fact now has an expiry and a re-validator, surfaced as a measured number.

- **Hypothesis firehose + un-counted exploration (the coverage gap).** M2 Gate A makes N honest *within* the harness. For the *out-of-harness* leak — `db_bridge`/MCP let agents peek at `feature_panel`/returns before registering — add a **lightweight query log** on `db_bridge.AsadoDB` read paths (append `{session_id, table, ts}` to `Data/loop/exploration_log.jsonl`), and a **negative-results pre-flight** (`scripts/qa/check_dead_registry.py`) wired into `sweep_signals.py`: re-testing a spec whose `(table,variable,lag,direction,mechanism)` already folded to DEAD emits a loud WARN with the prior verdict+date (closing the known dedupe leak that ignores start_date/universe and re-burns the trial budget). This does not *prevent* HARKing but makes prior peeking *visible* and re-testing-the-dead *expensive* — the honest, non-ceremonial version. **Implement the un-enforced constitution rules 4–5**: a family-wise **freeze timer** (after 20 trials without a WATCH, `register_hypothesis()` refuses new trials in that family for 6 months — `bbg_skill` N=16 and `graph_trade_gap` N=15 are 4–5 trials away), and a **registration-time frozen `primary_horizon`** (today it's `horizons[0]`, orderable by an agent to pick which NW-t gates the verdict — a real multiple-comparisons leak).

- **Silent quality regression across model versions.** A minimal **golden-task suite** (`scripts/loop/golden_regression.py`, ~10 frozen cases: a known-DEAD signal that must verdict DEAD, a known ticker→country fact, a fixed brief that must render byte-identically), **auto-triggered when `CLAUDE.md`'s model snapshot changes** (a git-diff watch in the hook, *not* a manual "remember to run it" step — that's the only way it survives), result logged with `model_id`. ~91% of production LLMs drift within 90 days; this is the only solo-shop detector for a quietly-worse model passing junk.

- **Fact provenance + expiry, and per-thesis replay.** M8 covers facts. For theses, stamp the **load-bearing subset only** — `model_id` + `harness_run_json` (git already gives the SHA; six provenance fields per thesis at ~3/week is theater). That subset makes any verdict re-derivable.

---

## 5. Prioritized roadmap

**This week (≤5 cheap, high-leverage, all S):**
1. **Stamp `model_id`/`session_id`** on `thesis_open` + `hyp_register` (`ledgers.py`). *Irreversible if skipped.* — **S**
2. **Liveness heartbeat + `PushNotification`** on any non-zero loop exit OR missing/uncommitted brief (`loop_daily_job.py` + launchd plist). Cheapest blast-radius cut in the set. — **S**
3. **Fix the ledger FAIL-IS-FAIL holes** (`ledgers.py`): `thesis_review` branch + raise-on-unknown-event; `status∈{retired,rejected}` overrides `verdict` + `live_signals` view; `killed_review`→`outcome='void'`. — **S**
4. **`config/family_registry.yaml`** + raise-on-unrecognized-key in `register_hypothesis()`. Restores the deflated-Sharpe N's honesty. — **S**
5. **Repo-tracked `.githooks/`** with the pre-registration gate + append-only enforcement (`.git/hooks` is empty — free leverage). — **S→M**

**This month:**
- **Gate B per-variable publication lag** + `graph_pit` canary (`evaluate_signal.py`, `tests/loop/`). — **M**
- **D11 cross-source + nearest-neighbor swap** (auto-derived pairs) + **sentinels** + nightly BBG ticker NAME/country re-resolution (`build_dislocations.py`, `loop_daily_job.py`). — **M**
- **Calibration upgrade**: shrinkage + Murphy resolution + Spiegelhalter z + by-model slice + Arjun-as-forecaster (`calibration_report.py`). — **M**
- **Process fields**: mandatory `premortem_failure_mode` + `invalidation_rule`, `foreseen`/`surprise` close tags (`ledgers.py`). — **M**
- **Path→check mapper** in the hook (no collector/harness edit without its validator green). — **M**
- **Declared-consumer registry + config-lint** (see §6, E6/E7) — the two highest-severity technical-debt leaks, an afternoon each. — **S**

**This quarter:**
- **`model_inventory.jsonl`** + auto-discovery coverage gate + tiering (`build_model_inventory.py`). — **M**
- **Combiner champion-challenger** kill criteria + nightly harness replay; move caveat to the Neo4j rank. — **L**
- **Wire `spectral.py`** (pre-registered falsifier) and **run it once**; **FF-spanning as a registration gate**; **alpha-decay residual monitor**. — **M→L**
- **Diátaxis memory split** + `facts.jsonl` + `verify_facts.py` + ~6 back-filled **ADRs** + `validate_memory.py`. — **M**
- **Cross-month value-drift alarm** against `Data/backups/` (restatement defense); **exploration log** + `check_dead_registry.py`; **family freeze timer** + frozen `primary_horizon`; **golden_regression.py** auto-triggered on model-snapshot change. — **M→L**
- **Ledger-wide effective-N + PBO/CSCV + BH-FDR + alpha-decay haircut** (see §6, E1/E2/E4/E5). — **M**

### Anti-overkill — deliberately NOT doing
- **No data-contract CLI suite** (`datacontract-cli` per collector). ASADO's producers are external APIs that never sign SLAs; `build_schema_registry.py` + `validate_variable_registry.py` + D11 + the cross-sectional sweep already do ~90%. A three-layer contract gate would be silently disabled the first time it false-positives during a legitimate monthly source outage (which the resilience pattern *expects*) — it conflicts with the per-source try/except design.
- **No ML Test Score scorecard per model** — a generic rubric; its min-across-4-categories score penalizes ASADO for serving/monitoring it correctly doesn't do. (Cherry-pick ~7 of its 28 tests as a checklist instead — see §6, E8.)
- **No `CONSTITUTION.md` consolidation as a new file** — the constitution already lives in `CLAUDE.md` + PRD §10 + the harness; a new top-level doc is a *fifth* stale memory surface. The leverage is enforcing rules in code (M2/M3), not re-housing prose.
- **No hard-blocking auditor agent** — advisory only (rot/latency/nondeterminism; rubber-stamp-in-reverse).
- **No second `trust_ledger.jsonl`** — merged into M1's per-row trust block (avoids the double-bookkeeping).
- **No SCD-2 effective-dated `country_mapping` dimension** — a git-diff-on-change alarm suffices; full Kimball dimensional ceremony is over-engineered for a rarely-changing map. (Scope `knowledge_date` to `imf_factors`/WEO/forecast vars only; lean on existing `Data/vintages/`.)
- **No commercial observability platform** (Monte Carlo/Bigeye), **no feature store** (Feast/Tecton), **no Great Expectations Python suites**, **no OpenLineage/Marquez**, **no MLflow/DVC/lakeFS**, **no cryptographic artifact signing**, **no EU-AI-Act paperwork**, **no per-action human approval** (the 93%-approval rubber-stamp), **no committees/RFC boards/calibration-committee/dot-collector**, **no scoring-rule zoo** beyond Brier+Murphy, **no row-level bitemporality** on the 17.4M-row market tables, **no calendar-driven reviews** (use trigger-driven revalidation). Sculley et al.'s **CACE** ("Changing Anything Changes Everything") is the *reason* the isolation/cycle guards already in code are sacred — preserve them; do not add the heavy MLOps stack around them.

---

## 6. Research-grounded enrichments (the two recovered research legs)

Two of the seven deep-research legs (quant multiple-testing/alpha-decay; ML technical debt) initially failed on transient socket errors and were re-run with full web sourcing. They add the following **concrete, cited** practices, which slot into the mechanisms and roadmap above. Citations are in the Appendix.

### Multiple-testing & alpha decay (anchors: Harvey-Liu-Zhu; Bailey & López de Prado; McLean-Pontiff; Benjamini-Hochberg)

- **E1 — Effective-N at the LEDGER level, not just per-family (strengthens M2 Gate A). — S→M.** The deflated-Sharpe N should be the count of *effectively independent* trials, estimated by clustering correlated specs across the **entire** `hypothesis_ledger.jsonl`, not a hand-drawn family integer. Mis-grouping silently mis-sets the bar (the exact §1.1 defect). `evaluate_signal.py` emits `dsr`, `N_naive`, `N_effective`. *[Bailey & López de Prado DSR / False Strategy Theorem; ONC clustering.]*
- **E2 — PBO via CSCV as an orthogonal second gate above DSR. — M.** DSR asks "is this winner significant given N?"; **PBO** asks "what is the probability the in-sample winner underperforms out-of-sample?" — precisely the question `combiner_scores_daily` (components selected in-sample 2026-06) begs. Build the trial-returns matrix, run CSCV (S≈8–16 partitions), reject if PBO>0.5, flag 0.2–0.5. Wire the published implementation; don't re-derive. *[Bailey, Borwein, López de Prado & Zhu 2017.]*
- **E3 — `t>3.0` is a necessary FLOOR, not a sufficient pass. — S.** Harvey's 2017 Presidential Address states verbatim that "making a decision based on t > 3 is not sufficient either" when the prior odds of a real effect are low (his t=3.23 three-letter-ticker portfolio is pure p-hacking from ~12,640 trials). Add a `prior_odds` enum (high/med/low) set at pre-registration; low-prior signals must clear a higher effective bar. ASADO's mechanism-text pre-registration is already ~90% of this. *[Harvey 2017; Harvey-Liu-Zhu 2016.]*
- **E4 — Benjamini-Hochberg FDR sweep across the whole ledger (q=0.10) in `calibration_report.py`. — S.** Per-test NW t-stats don't control the *ledger-wide* false-discovery rate; expected false positives grow with the JSONL. BH controls the *proportion* of false discoveries (the right power/rigor tradeoff for a research ledger — Bonferroni/FWER is too brutal). Stamp each row `bh_pass`/`bh_reject` + the current BH critical p; track survivor count over time. *[Benjamini & Hochberg 1995.]*
- **E5 — Live-vs-backtest IC-decay monitor with a pre-budgeted haircut. — M (complements M7).** McLean-Pontiff: published predictors return **26% less out-of-sample** and **58% less post-publication**, with decay *worst for the strongest backtest signals* — so the combiner (highest backtest IC) is the prime suspect. Pre-register an expected decay band per live signal (mark a known/crowded signal down ~25–58% before deployment; watch rising cross-correlation to other live signals as the crowding tell), alarm on breach. *[McLean & Pontiff 2016.]*

### Technical debt (anchors: Sculley et al. CACE; Breck et al. ML Test Score)

- **E6 — Declared-consumer registry for each DuckDB view (`config/view_consumers.yaml`) + a ~30-line lint. — S (slots into M1/M8).** **Undeclared consumers of `feature_panel`/`unified_panel` is ASADO's single highest-severity Sculley debt** (read by the MCP, `db_bridge`, the harness, `Step Zero Build Econ.py`, `Step Zero Build GDELT.py`, the brief, ad-hoc agent scripts — with nothing declaring who reads which columns). List each view → declared consumers + columns; the lint walks `scripts/` and **fails if any reader is undeclared**, turning the optimizer cycle-guard from convention into a *checked* invariant. Cheapest high-leverage technical-debt fix. *[Sculley et al. 2015 — undeclared-consumer / visibility debt.]*
- **E7 — Config-lint over the 38 YAMLs / 23 sweeps. — S.** Configuration debt is the second real leak (monthly-suffixed sweep configs, no schema, no dead-config detection). `scripts/lint_configs.py`: validate each `config/sweeps/*.yaml` against a tiny JSON-schema (required keys, valid date ranges, variable names cross-checked against the M1 inventory), flag stale/dead configs, run nightly. Implements Sculley's explicit config-debt prescription (assert, diff, dead-config detect). *[Sculley et al. 2015 — configuration debt.]*
- **E8 — Cherry-pick ~7 ML-Test-Score tests as a checklist; SKIP the score.** Lift only the tests that map to ASADO's real leaks — data validation, feature expectations/statistics, leave-one-out feature correlation (the underutilized-dependency purge), model reproducibility, model staleness / prediction-distribution monitoring. **Confirmed:** ASADO's isolation/cycle guards *are* exactly Sculley's prescribed CACE / undeclared-consumer / unstable-dependency mitigations (the optimizer-output exclusion breaks a hidden feedback loop *and* a correction cascade; WEO vintage snapshotting is a versioned-copy of an unstable dependency) — preserve them as invariants; **do not** wrap them in DVC/MLflow/Feast/OpenLineage, which would re-encode the same guard with more moving parts and a server to operate solo. *[Breck et al. 2017; Sculley et al. 2015.]*

---

## North Star

**ASADO's instruments are honest; they are simply wired to nothing.** Govern it as one task repeated at every layer: *take each honest-but-bypassable instrument and make it a checkpoint that fails loudly without you in the loop* — the harness becomes a nightly replay, the deflated-Sharpe N becomes a canonical (effectively-independent) count, the daily embargo becomes a per-variable proof, the silent swap becomes a D11 row, the model becomes an inventoried-and-killable thing, and trust becomes a shrunk, falsifiable number per component surfaced on one scorecard where a green line *means* "don't re-check." The binding constraint is your judgment bandwidth, never compute — so the system's job is to **spend your attention only on red**, grade *process* now (gradable at n=1) because *outcomes* won't be statistically real for years, and treat the GSAB10YR swap as the permanent reminder that the most dangerous failure is not an agent being wrong but the **data quietly lying** while every downstream number looks plausible. Everything you add from here forward earns its place by passing one test: *can it be a script that exits non-zero on its own?* If not, it will rot — so it is advisory, or it is cut.

---

## Appendix — Citations

The 5 research legs whose findings are cited inline (data observability, institutional memory, calibration science, agentic governance, model-risk/SR 11-7) are sourced by name in §2–§4 (Monte Carlo five pillars; Nygard ADRs / Diátaxis; Tetlock/Brier/Good Judgment Project, Klein pre-mortems, Annie Duke "resulting"; LLM-judge self-preference & agentic-oversight findings; Fed/OCC SR 11-7 / SR 26-2). The two recovered legs (§6) carry full URLs below.

### Multiple-testing & alpha decay
1. Harvey, Liu & Zhu (2016), "…and the Cross-Section of Expected Returns," *RFS* 29(1) — https://academic.oup.com/rfs/article-abstract/29/1/5/1843824 · NBER w20592 https://www.nber.org/papers/w20592
2. Harvey & Liu (2015), "Backtesting," *JPM* 42(1) — https://people.duke.edu/~charvey/Research/Published_Papers/P120_Backtesting.PDF
3. Harvey & Liu (2014), "Evaluating Trading Strategies," *JPM* 40(5) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2474755
4. Bailey & López de Prado (2014), "The Deflated Sharpe Ratio," *JPM* 40(5) — https://www.davidhbailey.com/dhbpapers/deflated-sharpe.pdf
5. Bailey, Borwein, López de Prado & Zhu (2017), "The Probability of Backtest Overfitting," *J. Computational Finance* 20(4) — https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf
6. López de Prado (2018), "The 10 Reasons Most Machine Learning Funds Fail," *JPM* 44(6) — https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3104816
7. Hou, Xue & Zhang (2020), "Replicating Anomalies," *RFS* 33(5) — https://global-q.org/uploads/1/2/2/6/122679606/houxuezhang2020rfs.pdf
8. Harvey (2017), "Presidential Address: The Scientific Outlook in Financial Economics," *JoF* 72(4) — https://people.duke.edu/~charvey/Research/Published_Papers/P131_The_scientific_outlook.pdf
9. McLean & Pontiff (2016), "Does Academic Research Destroy Stock Return Predictability?" *JoF* 71(1) — https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12365
10. Benjamini & Hochberg (1995), "Controlling the False Discovery Rate," *JRSS-B* 57(1) — https://en.wikipedia.org/wiki/False_discovery_rate
11. Deflated Sharpe ratio — False Strategy Theorem / E[max SR] & ONC effective-N reference — https://en.wikipedia.org/wiki/Deflated_Sharpe_ratio

### Technical debt & reproducibility
1. Sculley et al. (2015), "Hidden Technical Debt in Machine Learning Systems," *NeurIPS* — https://proceedings.neurips.cc/paper_files/paper/2015/file/86df7dcfd896fcaf2674f757a2463eba-Paper.pdf
2. Breck et al. (2017), "The ML Test Score," *IEEE Big Data* — https://research.google.com/pubs/archive/aad9f93b86b7addfea4c419b9100c6cdd26cacea.pdf
3. Breck et al. (2016), "What's Your ML Test Score?" *NIPS workshop* — https://research.google.com/pubs/archive/45742.pdf
4. MLflow vs DVC vs Feast overview — https://oleg-dubetcky.medium.com/data-versioning-dvc-mlflow-or-feast-82dd9e7c454f
5. DVC vs Git-LFS vs Dolt vs lakeFS — https://lakefs.io/blog/dvc-vs-git-vs-dolt-vs-lakefs/
6. Feast purpose (training/serving consistency), O'Reilly — https://www.oreilly.com/library/view/implementing-mlops-in/9781098136574/ch04.html
7. OpenLineage getting started — https://openlineage.io/getting-started/ · Marquez — https://marquezproject.ai/
8. DuckDB + parquet minimal-tooling baseline — https://www.kdnuggets.com/building-your-modern-data-analytics-stack-with-python-parquet-and-duckdb

---

*Last updated: 2026-06-17. Produced by a multi-agent research workflow (16 agents; ~1.8M tokens). Design only — no code changes made. Implementation of any item above is gated on Arjun's go-ahead, per the project's "ask before writing code" rule.*
