# PRD — ASADO Governance Layer + Chief-of-Staff Agent

| Field | Value |
|-------|-------|
| **Project** | ASADO country-equity macro research platform |
| **System name** | Governance Layer + Chief of Staff |
| **Short name** | `gov_cos_v1` |
| **Version** | 1.2 (locked for build — two adversarial-review passes folded in) |
| **Created** | 2026-06-17 |
| **Owner** | Arjun Divecha |
| **Executor** | Frontier-model agent sessions (multi-session) |
| **Reviewed by** | GPT-5.4 (two adversarial passes, 2026-06-17) — findings folded into v1.1 then v1.2 |
| **Status** | LOCKED — execute Phase A honest core ({A1, A3, A5, A6, A7, A8}); A2/A4 parallel |
| **Related** | `docs/JUDGMENT_OPERATING_MODEL_2026_06_17.md` (the analysis this operationalizes), `PRD_Alpha_Hunting_Loop.md` (the system being governed), `PRD_Semantic_Layer_Variable_Registry.md` (the coverage-gate pattern reused), `AGENTS.md` |

---

## 0. One-paragraph summary

ASADO's validation instruments are honest but **wired to nothing** — `evaluate_signal.py`, `ff_spanning.py`, and `diagnostics/spectral.py` are invoked by neither `loop_daily_job.py` nor `monthly_update.py`, so detectors and the combiner ship to Neo4j and the brief continuously bypassing the skeptic, and judgment leaks through a free-text `family_key` (sets the deflated-Sharpe N, `evaluate_signal.py:783`), a blanket `publication_lag=0` on the daily path (`evaluate_signal.py:645`), an order-dependent primary horizon (`evaluate_signal.py:704`), a near-empty calibration sample (`calibration_report.py:126` counts only hit/miss/invalidated as closed), an un-reconciled `verdict`/`status` field (the retired look-ahead `H_20260610_001` still folds to `WATCH`), an unmonitored data surface (the GSAB10YR South-Africa→Saudi swap), and a nightly log nobody reads. This PRD builds a **deterministic governance layer** that wires each honest instrument into the pipeline as a checkpoint that fails loudly without human action and collapses the result into **one machine-readable scorecard** (`governance_scorecard.json`), then a **read-only, grounded Chief-of-Staff agent** on top. The governing principle: **the pipeline is the constitution; the agent is the colleague.** The agent's trust ceiling equals its substrate's trust ceiling.

**The non-negotiable design rule:** *a partial check must never render green.* A green that means "the script emitted JSON" (or "a handful of pairs were checked") is worse than no scorecard — it launders false confidence. Therefore the scorecard's notion of "what must be checked" is a single source-controlled contract, every dimension that runs on partial coverage is **amber not green**, and the substrate covers the two worst verified defects (the PIT-embargo void and the GSAB-class silent swap) before any agent is built. The agent is built on a scorecard that **knows what it does not know.**

---

## 0.1 Review response — pass 1 (v1.1)

| GPT finding (pass 1) | Change |
|---|---|
| Phase A could go green without detecting the PIT-void or GSAB swap | A6 (PIT-lag proof) + A7 (cross-source/sentinel) pulled into Phase A |
| Heartbeat too skinny → stale-but-green | A1 run manifest (expected outputs + mtimes) built first |
| §3 constitution unenforceable | Agent split into status-mode / research-mode |
| A4 just another knob; horizon-order gameable | Versioned registry + migration diff + frozen `primary_horizon` |
| A2 proved one view, not the state machine; `void` breaks calibration | Full downstream-consumer tests + calibration closed-set fix |
| "5 nights" acceptance weak | Fixture replay + forced-failure-per-dimension |
| Phase B too broad → HARKing | B0 monitor / B1 research split |
| Agent's real authority is agenda control | Research-intent log added |
| "Run spectral once" is theater | Phase C: recurring monitored surface or it doesn't count |

## 0.2 Review response — pass 2 (v1.2)

| GPT finding (pass 2) | Change in v1.2 |
|---|---|
| A7 overclaims — "some swaps checked" rendered as green = new false-confidence surface | **Dimension renamed `cross_source_minimal`; stays AMBER until coverage crosses a threshold across critical mapped series; pairs derived semantic-equivalence-first, correlation-second** (§A7) |
| A8 only half a completeness contract; A1 `expected_outputs` and A8 `dimensions_expected` are two trust lists that drift | **Single source-controlled `config/governance_contract.yaml` generates BOTH the run-manifest expectations and the scorecard dimensions; its hash is stamped into manifest + scorecard** (§A1, §A8) |
| B0/B1 split is prose, not machinery | **B0 and B1 are SEPARATE skills with disjoint tool/file allow-lists; B0 can read only `Data/loop/governance/` rendered artifacts, no shell/DB/raw-ledger** (§3, §5, §6) |
| Agenda control logged but not priced; dead-trial preflight WARN-only → "peek, tweak, rerun" | **Intent→family attribution is deterministic; a registered intent increments the family's exploration count; repeated DEAD retests are BLOCKED absent an override token + rationale** (§1.3, §6) |
| `pit_proof` is not a governance object | **Versioned `pit_proof_registry` — proof type, entitled lag class, owning test id, last-passing-commit, stale-proof = fail** (§A6) |
| Trust moved into UNGUARDED config; config-lint deferred to Phase C (backwards) | **Governance-config guard in Phase A: scorecard stamps repo SHA + dirty flag; trust-root YAMLs must be committed or the scorecard is red** (§A8) |
| A2 "brief committed" underspecified → chronic false-red | **Resolved: governance/brief artifacts auto-committed by the loop, check scoped to the brief path vs `HEAD`** (§A2) |
| B1 "all reads logged" false | **All B1 reads pass through ONE proxy logger; the claim is comprehensive by construction** (§6) |
| Two trust decisions stranded in "open questions" | **Resolved in the body: A5 = full one-time in-place re-verdict with migration diff; A7 initial pair set named** (§A5, §A7) |
| Phase A too big | **Green-gate honest core = {A1, A3, A5, A6, A7, A8}; A2 (push) + A4 (model_id) are parallel "do-now" (A4 because it is irreversible), not gate prerequisites** |

---

## 1. Thesis and division of labor

### 1.1 What the deterministic layer owns
All adjudication. Verdicts come only from `evaluate_signal.py`. Liveness, ledger-integrity, PIT-proof, cross-source consistency, family-counting, and config-integrity are scripts that exit non-zero. The acceptance test for every control: **if it cannot be expressed as a script that exits non-zero without a human, it is advisory or cut.**

### 1.2 What the Chief-of-Staff agent owns
Explanation, synthesis, prioritization, research orchestration (B1 only), monitoring, task routing. It reads deterministic surfaces and **never writes a verdict, never marks a thesis, never adjudicates.**

### 1.3 The two authority channels — both controlled
- **Direct adjudication** (writing verdicts/marks): blocked structurally — no write path.
- **Agenda control** (shaping *what gets tested next*): this inflates the effective multiple-testing burden even with no `verdict` written, so it is **priced, not just logged.** Every agent-proposed research direction is written to the research-intent log with a deterministic **intent→family attribution**; a registered intent **increments that family's exploration count** (feeding deflated-Sharpe N / the freeze timer), and a re-test of a spec already folded DEAD is **blocked** unless accompanied by an override token + written rationale. Peeking and re-running is therefore charged, not free.

### 1.4 The contract between layers
`config/governance_contract.yaml` is the **single source of truth** for "what must be checked" — it declares every expected nightly governance step, its expected outputs, and the scorecard dimensions, and a generator derives both the run-manifest expectations and the scorecard dimension set from it (they cannot drift). Its content hash + the repo SHA + a dirty flag are stamped into `Data/loop/governance/governance_scorecard.json`, the machine surface the agent reads. The human reads the markdown rendering prepended to the nightly brief.

---

## 2. Architecture

```text
config/governance_contract.yaml  (SINGLE SOURCE OF TRUTH: steps, expected outputs, scorecard dimensions)
        │ generates ▼
DETERMINISTIC GOVERNANCE LAYER (nightly, no LLM, fails loud)
  run_manifest.json (per-step status + expected outputs + mtimes)   ← built first, from the contract
        ↓ read by
  liveness heartbeat · ledger integrity (full state machine) · family registry (versioned)
  · model_id stamping · per-variable PIT-lag proof (pit_proof_registry) · cross_source_minimal
  · governance-config guard (SHA + dirty + trust-root YAMLs committed)
        ↓ roll up into
  governance_scorecard.json  (completeness vs the contract; amber on partial coverage;
                              stamps contract-hash + repo SHA + dirty)   ← THE CONTRACT SURFACE
  + markdown block prepended to brief_YYYY_MM_DD.md (for the human)
        ↓ reads (read-only)
CHIEF-OF-STAFF AGENT (two SEPARATE in-repo skills with disjoint allow-lists)
  B0 (skill: status) — reads ONLY Data/loop/governance/ rendered artifacts; no shell/DB/raw-ledger
  B1 (skill: research) — raw surfaces via ONE proxy logger; NON-GOVERNING; agenda-priced
  voices: FACT (cited) / INFERENCE (labeled) / UNKNOWN-STALE (loud) — never adjudicates
```

All governance artifacts live under `Data/loop/governance/` and `Data/loop/asado_loop.duckdb` — **never** `Data/asado.duckdb` (wiped each rebuild). Ledgers stay git-tracked append-only JSONL.

---

## 3. The Chief-of-Staff constitution

1. **Three voices, always labeled.** **FACT** (read from a named surface, *with citation*), **INFERENCE** (labeled), **UNKNOWN/STALE** (surface red/missing/stale — said out loud).
2. **Cite or don't claim.** A FACT with no surface citation is not emitted.
3. **Mode separation is machinery, not prose.** Two separate skills:
   - **B0 (status):** tool/file allow-list permits reading ONLY pre-rendered artifacts under `Data/loop/governance/` (scorecard, run-manifest, heartbeat) plus the rendered brief and `live_signals`/calibration views. No generic shell, no `db_bridge`, no raw ledgers/harness JSON. This is the only skill that answers "what is the state / what should I care about."
   - **B1 (research):** may read raw surfaces and the warehouse, but only through a single proxy logger; every answer is stamped **NON-GOVERNING**; proposed directions hit the research-intent log (§1.3).
4. **Never adjudicates.** No verdicts, marks, severities, or good/dead declarations.
5. **Leads with red.** If the scorecard has a red/amber line, the first sentence of any status answer names it.
6. **No silent fallback (FAIL-IS-FAIL).** Missing/stale surface → says so and stops.

### 3.1 Bootstrap read-lists (enforced by each skill's allow-list)
- **B0:** `governance_scorecard.json` · `run_manifest.json` · `heartbeat.json` · latest `brief_YYYY_MM_DD.md` · `live_signals` view · latest `calibration_*.md`.
- **B1 (NON-GOVERNING, all reads logged):** the above plus raw `ledgers/*.jsonl`, `harness_runs/*.json`, `cost_model_summary_*.xlsx`, `db_bridge.AsadoDB` (read-only), the personal-knowledge MCP, this PRD + the operating-model doc.

---

## 4. Phase A — Hardened governance substrate

Green-gate honest core = **{A1, A3, A5, A6, A7, A8}**. A2 and A4 are parallel "do-now" (A4 is irreversible, do it week 1; neither is a gate prerequisite). Line references verified 2026-06-17.

### A1 — Governance contract + run manifest (foundational)
- **Files:** new `config/governance_contract.yaml` (declares expected steps, expected outputs, scorecard dimensions); new `scripts/loop/run_manifest.py` → `Data/loop/governance/run_manifest.json`; `scripts/loop/loop_daily_job.py` (wrap each step).
- **Behavior:** the contract is the one list; a generator derives manifest expectations + scorecard dimensions from it. Per step record `{step, status (ok/fail/skipped/stale), started_ts, ended_ts, expected_outputs[], output_mtimes[]}`. A step that fails while yesterday's artifact lingers reads **fail/stale**, not green. Contract content-hash stamped into the manifest.
- **Acceptance:** forced step failure → that step `fail`; deleted expected output → `fail` even at exit 0; unchanged-mtime expected output → `stale`; manifest and scorecard dimension sets are both generated from the contract (proven by a test that adds a contract entry and sees both update).

### A2 — Liveness heartbeat + push *(parallel do-now; not a gate prerequisite)*
- **Files:** `scripts/loop/heartbeat.py` → `Data/loop/governance/heartbeat.json`; launchd plist; brief/governance **auto-commit** step in `loop_daily_job.py`.
- **Behavior:** on any manifest `fail`/`stale`, non-zero exit, or missing brief, fire a push (channel: reuse Telegram loop plumbing if wired, else clean channel — confirm at build start). Brief-commit check is **scoped to the brief path vs `HEAD`** and the loop **auto-commits** governance/brief artifacts, so a dirty working tree elsewhere never false-reds.
- **Acceptance:** each of {forced fail, stale output, missing brief} fires the push; a healthy run auto-commits the brief and is silent.

### A3 — Ledger integrity (full state machine)
- **Files:** `scripts/loop/ledgers.py`, `scripts/loop/calibration_report.py`.
- **Changes:** `fold_theses()` gains a `thesis_review` branch and **raises on any unknown event type**; `fold_hypotheses()` invariant: `status ∈ {retired, rejected}` nulls/overrides `verdict`; canonical `live_signals` view; `killed_review`/null-Brier → auditable `outcome='void'`; update `calibration_report.py:126` closed-set so `void` is handled explicitly (excluded with a logged reason).
- **Acceptance (state machine):** fixture-replay proves — (i) `H_20260610_001` absent from `live_signals`; (ii) unknown event raises; (iii) the 3 `thesis_review` events fold; (iv) calibration, brief, and `db_bridge` "current/live" queries all exclude retired/rejected/void; (v) count-in == count-out (no drop/dup).

### A4 — `model_id`/`session_id` stamping *(parallel do-now; irreversible)*
- **Files:** `scripts/loop/ledgers.py` (`open_thesis`, `register_hypothesis`), `scripts/loop/calibration_report.py`.
- **Changes:** stamp `model_id`, `model_version`, `session_id`; backfill existing → `unknown_pre_20260617`; add a `("By model","model_id")` calibration slice (today 100% of `author` = `"agent-overnight"`).
- **Acceptance:** new theses/hyps carry `model_id`; by-model slice renders.

### A5 — Family registry (versioned) + migration diff + frozen primary horizon
- **Files:** new `config/family_registry.yaml` (`version` field), `scripts/loop/ledgers.py`, `scripts/harness/evaluate_signal.py`.
- **Changes:** map `(archetype, source, variable-prefix, mechanism-class) → canonical family_key`; `register_hypothesis()` **raises on unrecognized key**. Seed: collapse `graph_trade_gap`(15)/`leadlag_2026_06`(6)/`fund_similarity_2026_06`(2) → one `network_spillover`; split `bbg_skill_2026_06`'s 5 mechanisms. **Freeze `primary_horizon`/`hold_days` at registration** (`evaluate_signal.py:704` treats `horizons[0]` as primary → gameable until frozen).
- **DECISION (resolved):** perform a **full one-time in-place re-verdict** of the existing ledger under corrected N now, append-only, emitting `Data/loop/governance/family_migration_diff.json` (every historical trial: old_family→new_family, old_N→new_N). In-place via each `hypothesis_id` + stored params (**zero new registrations**; never `sweep_signals.py --force` for measurement, per AGENTS.md); each re-verdict event records `n_old`, `n_new`.
- **Destination (named, Phase C):** the registry is an interim knob; the un-gameable answer is ledger-wide **effective-N via correlation clustering** (operating-model doc E1).
- **Acceptance:** bogus `family_key` raises; migration diff accounts for **every** trial exactly once (no dup/drop); re-verdict appends `hyp_verdict` only, fold keeps latest; a horizon-reorder cannot change which NW-t gates the verdict.

### A6 — Per-variable PIT-lag proof + `pit_proof_registry`
- **Files:** `scripts/harness/evaluate_signal.py`, new `config/publication_lag.yaml`, new `config/pit_proof_registry.yaml`, `tests/loop/`.
- **Changes:** replace `if frequency=='daily': return 0` (`evaluate_signal.py:645`) with a per-variable lookup **defaulting to a conservative non-zero lag**; a daily variable earns lag 0 *only* via a `pit_proof_registry` entry. **`pit_proof` is a governance object:** `{variable, proof_type, entitled_lag_class, owning_test_id, last_passing_commit, status}`; a stale/failing proof = the variable reverts to the conservative lag (fail-closed). `graph_pit` edge-vintage canary asserts weight at *t* uses only vintages published `< t`.
- **Acceptance:** a daily signal with no valid proof gets the conservative lag (not 0); a stale proof reverts to conservative; the canary passes on PIT data and fails on a leaky fixture.

### A7 — `cross_source_minimal` (the GSAB defense — partial by design, never green-while-partial)
- **Files:** `scripts/loop/build_dislocations.py` (D11-lite), new `config/sentinels.yaml`, `scripts/loop/loop_daily_job.py`.
- **Changes:** (i) **sentinels** — manually-verified `(variable, country, date, expected_value, tolerance)` anchors per critical source; exact-match failure = hard stop. (ii) **D11-lite** cross-source consistency on a small set of **semantically-equivalent** redundant pairs (correlation only to rank within semantic matches), **frozen**. (iii) nightly **BBG ticker NAME/country re-resolution** vs `config/country_mapping.json`.
- **DECISION (resolved):** initial pair set = sovereign 10Y vs its own 5Y CDS; `bloomberg_factors` vs `sovereign_daily` overlapping sovereign series (the overlap that made GSAB10YR catchable); IMF GDP vs WEO vs OECD growth.
- **No-overclaim rule (v1.2):** the scorecard dimension is named `cross_source_minimal` and is **AMBER until coverage of checked-vs-critical-mapped-series crosses a declared threshold** — it never renders a green "cross-source covered" line on partial coverage. Full distribution sweep + nearest-neighbor-flip = Phase C.
- **Acceptance:** a synthetic GSAB-style swap in a fixture is caught by a sentinel or D11-lite; a NAME/country mismatch = hard stop + `USER_FIX_LIST.md` entry; the scorecard reports `cross_source_minimal` as amber with the actual coverage fraction, not green.

### A8 — Governance scorecard + completeness + config guard (keystone)
- **Files:** new `scripts/loop/build_governance_scorecard.py` → `Data/loop/governance/governance_scorecard.json` + markdown prepended to the brief. Final loop step.
- **Completeness (from the A1 contract):** `dimensions_expected[]` is read from `config/governance_contract.yaml` (not a separate hand list). The scorecard carries `schema_version`, `producer_version`, `as_of`, `contract_hash`, `repo_sha`, `repo_dirty`, and per-dimension `evidence` links. **Any expected dimension not computed → "blind" (amber/red), never green. Any dimension on partial coverage (e.g. A7) → amber.**
- **Config guard (v1.2, pulled from Phase C):** the trust-root YAMLs (`governance_contract`, `family_registry`, `publication_lag`, `pit_proof_registry`, `sentinels`) must be **committed**; an uncommitted/dirty trust-root makes the scorecard **red** (with `repo_dirty=true`), so trust cannot be silently changed.
- **Acceptance:** validates against a published JSON schema; a missing dimension → blind (not green); a dirty trust-root → red; green requires every contract dimension computed, passing, on full-or-above-threshold coverage, with a clean committed trust-root.

**Phase A acceptance (gate to B0) — fixture-driven:**
1. Fixture replay of the existing ledgers reproduces A3/A5 deterministically.
2. Forced-failure per scorecard dimension — each independently turns its line red/amber/blind (liveness pushes).
3. Schema validation of `run_manifest.json` + `governance_scorecard.json`; manifest+dimensions both regenerate from the contract.
4. Downstream-consumer replay (calibration/brief/bridge reflect corrected ledger state).
5. A5 migration diff reviewed (every trial once); A6 canary green + stale-proof fails closed; A7 synthetic-swap caught + reports amber-with-coverage; A8 dirty-trust-root → red.
6. Then 1–2 live nightly runs produce a scorecard that is green **only** when all contract dimensions are computed, passing, and above coverage threshold.

No agent (B0) is built until all six pass.

---

## 5. Phase B0 — Monitor/explainer skill (status-mode; after Phase A green)

A **separate skill** whose allow-list permits reading only `Data/loop/governance/` artifacts + the rendered brief + `live_signals`/calibration views (no shell, no `db_bridge`, no raw ledgers). Surfaces: the `/cos` status answer (leads with red/amber, says UNKNOWN/STALE on missing surfaces) and a scheduled monitor (on loop completion + a fixed morning digest) that pushes a digest leading with reds.

**Acceptance:** every factual claim cites a verified surface; red/amber leads; missing/stale → UNKNOWN/STALE; the monitor pushes a correct digest on a real loop completion; the skill has **no code path** to raw warehouse reads.

---

## 6. Phase B1 — Research colleague skill (gated)

A **separate skill** (raw reads via one proxy logger), enabled only after: the **exploration log** (`db_bridge`/MCP reads → `Data/loop/exploration_log.jsonl`), the **dead-trial preflight** (`scripts/qa/check_dead_registry.py`, **blocking-with-override**, not WARN), and the **research-intent log** with deterministic intent→family attribution (§1.3) all exist. Research-mode answers are stamped NON-GOVERNING.

**Acceptance:** an agent peek at `feature_panel`/returns appears in the exploration log; a re-test of a DEAD spec is **blocked** absent an override token + rationale; a proposed "test X next" appears in the research-intent log and increments the attributed family's exploration count.

---

## 7. Phase C — Deepen governance (CoS as PM)

Full auto-discovered `model_inventory.jsonl` + coverage gate + tiering (T3 meta-diagnostics monitored as T1-for-trust); **`diagnostics/spectral.py` wired and run as a RECURRING monitored surface with stale status** (`load_design_from_duckdb` is a `NotImplementedError` stub today; a one-off run is theater); FF-spanning as a registration gate; combiner as a champion-challenger with kill criteria; calibration-as-governance (Beta-Binomial shrinkage, Murphy resolution, Spiegelhalter z, process fields); **full distribution sweep + nearest-neighbor-flip** (extends A7 toward true cross-source coverage); Diátaxis memory split + `facts.jsonl` + `verify_facts.py` + ADRs; ledger-wide **effective-N** + PBO/CSCV + BH-FDR + alpha-decay haircut (the A5 destination); declared-consumer registry + config-lint; scoped path→check git hooks.

---

## 8. Non-goals (anti-overkill)

No commercial observability platform (Monte Carlo/Bigeye); no feature store (Feast); no MLflow/DVC/lakeFS/OpenLineage; no data-contract CLI per collector; no ML-Test-Score scored gate (cherry-pick ~7 tests only); no `CONSTITUTION.md` consolidation file; no hard-blocking auditor agent (advisory only); no second `trust_ledger.jsonl` (trust block lives in the Phase-C model inventory); **no full model inventory in Phase A** (only the A1 contract + A8 completeness — its cheap precursor); no SCD-2 bitemporal dimension beyond `imf/WEO/forecast` vars; no committees/RFC boards; no per-action human approval; no row-level bitemporality on the 17.4M-row tables; no calendar-driven reviews. The Chief of Staff does **not** replace the optimizer, trade live, or generate signals.

---

## 9. Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Scorecard green while blind / partial ("articulate narrator over a leaky system") | High | A6+A7 in the substrate; A8 completeness from the single contract; A7 amber-until-threshold; partial coverage never green |
| Stale-but-green (lingering artifacts) | High | A1 run manifest with expected outputs + mtimes |
| Two trust lists (manifest vs scorecard) drift | High | Single `governance_contract.yaml` generates both; hash stamped |
| Trust silently changed via unguarded config | High | A8 config guard: dirty/uncommitted trust-root → red; repo SHA stamped |
| Agent gains de-facto authority via agenda control | High | §1.3 priced intents (increment family count); B1 dead-retest blocked w/o override; B0 cannot research |
| B0/B1 boundary is just a prompt | High | Separate skills with disjoint tool/file allow-lists (machinery) |
| Corrected-N re-verdict double-counts/drops trials | High | Migration diff accounts every trial once; in-place, zero new registrations |
| `outcome='void'` breaks calibration | Medium | A3 updates `calibration_report.py:126` + downstream replay tests |
| `pit_proof` waved through weak | Medium | A6 registry: stale/failing proof fails closed to conservative lag |
| Brief-commit check false-reds a dirty repo | Medium | A2 auto-commits governance/brief; check scoped to brief path vs HEAD |
| Push-channel plumbing assumed but absent | Medium | Confirm Telegram wiring at A2 build start; else clean channel |

---

## 10. Open questions (defaults chosen; override at build start)

1. **Push channel:** reuse Telegram loop plumbing if wired, else clean channel. (Default: Telegram if wired.)
2. **CoS skill names:** `/cos` (B0 status) and `/cos-research` (B1)? (Default: yes.)
3. **Monitor cadence (B0):** on loop completion + a fixed morning digest. (Default: both.)
4. **A7 coverage threshold:** the amber→green coverage fraction for `cross_source_minimal` (Default: green only at ≥ the Phase-C full-sweep, i.e. A7 is amber-by-design until Phase C; pick an interim fraction at build start).

*(Resolved and moved into the body: A5 re-verdict scope → §A5; A7 initial pair set → §A7.)*

---

**Last updated:** 2026-06-17 (v1.2 — second adversarial pass folded in: single governance-contract source of truth, A7 amber-until-threshold, B0/B1 as separate skills, priced agenda control, pit_proof_registry, Phase-A config guard, brief-commit resolved, trust decisions resolved)
**One-line summary:** Wire each honest instrument into the pipeline as a fail-loud checkpoint driven by one source-controlled governance contract; never render green on partial coverage or a dirty trust-root; cover the two worst verified defects (PIT-void, GSAB swap) before any agent exists; then put a read-only, capability-separated, never-adjudicating Chief-of-Staff agent on top (status-only first, research only behind priced agenda controls) — pipeline as constitution, agent as colleague.
