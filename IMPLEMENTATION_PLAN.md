# ASADO Discovery Triage — Implementation Plan

> **Document type:** Engineering roadmap (FINAL — adversarially reviewed across 4 lenses + Sakana/Fugu Ultra).
> **Status:** FINAL — derived from the authoritative PRD; every cross-cutting reference re-verified
> against the live repo / loop DB (read-only) on 2026-06-25. Supersedes all prior drafts.
> **Last updated:** 2026-06-25.
>
> **Review provenance (honest record):** the synthesis draft and 3 of the 4 review lenses first hit
> transient API connection drops; the **completeness** lens completed in-workflow. The **correctness**,
> **epistemic-integrity**, and **sequencing/feasibility** lenses were then re-run cleanly against this
> on-disk file and their findings applied. Net result of the second pass:
> - *Sequencing/feasibility:* no conceptual blockers — buildable as ordered once the PR-1 contract fixes
>   below are applied.
> - *Correctness:* the `price_state_daily` "leak" lead **resolved SAFE** (its `country_return_*`/`etf_return_*`
>   columns are trailing/PIT-safe, verified in `build_price_state.py`); one doc defect fixed → §3.2 now uses
>   a column-level allowlist instead of a fictional column list.
> - *Epistemic integrity:* **two real holes closed in `freeze_claim.py`** — (1) the model-cutoff gate is now
>   code-enforced at freeze time so a human cannot launder a pre-cutoff LLM idea into historical
>   certification (Invariant D); (2) language-discipline is enforced on frozen claims, not only Lab output
>   (Invariant F). See §4(d), §5(d), and the §4(f) tests.
> - *Final Sakana/Fugu Ultra vetting:* **approved with must-fix edits** incorporated here: canonical
>   visibility-mode aliases, lock-protected JSONL/ID writes, explicit `measurement_shape`, first-class ETF
>   expression quality, route-aware blind packets, and provisional Phase-3 model/SDK wiring.

---

## 0. Header — Purpose, Inputs, Outputs, Ground Rules

### 0.1 Purpose

This document turns the **ASADO Discovery Triage** PRDs into a buildable, sequenced engineering
roadmap. It is the bridge between *what the system must do* (the PRDs) and *what an engineer
types* (files, functions, tests, wiring). Every phase is written so a single engineer can pick it
up and build it without re-deriving design decisions.

The system being built: a **quarantined LLM-native Discovery Lab** that lets a current Claude model
discover strange, nonlinear, non-obvious cross-country relationships, wrapped in a minimal
**chain-of-custody Court** (provenance routing, tool-enforced outcome blindness, cheap triage probes,
blind human ruling, prospective incubation, and a graveyard control arm). The Discovery Lab is the
*product*; disbelief is the *chain of custody*. The Lab emits **drafts, never validated alpha.**

### 0.2 Authoritative inputs (this plan derives them faithfully)

- **`FuguPRD.md`** (1655 lines, sections 0–25) — the **authoritative** full design spec. It owns
  the record schemas, the visibility-mode/certification-route tables, the object types, and the
  phase/acceptance detail. Where this plan and FuguPRD disagree, FuguPRD wins.
- **`PRD_ASADO_Discovery_Triage.md`** (43 lines) — the short **V1 scope gate**: the executive
  contract that distills FuguPRD into the 9-step V1 workflow, the V1 deliverables list, and the
  4 explicit deferrals. It is the gate that says "this much, no more, for V1."
- **`fugu.md`** — predecessor narrative essay; design rationale only, NOT a deliverable. Reference
  context, not a contract.

### 0.3 Three settled decisions baked into this plan

1. **DECISION 1 (Lab engine is real).** Phase 3 wires a **real current frontier model** against the
   tool-enforced outcome-blind context, recording **real `model_training_cutoff` metadata**. Specific
   model IDs, SDK method shapes, retention constraints, and structured-output parameters are **not settled
   by this plan**; they are verified at Phase-3 wiring time. Because current model cutoffs usually precede
   historical certification windows, historical backtests of LLM-generated ideas **correctly route to
   prospective-only**; only forward windows after the cutoff are `post_cutoff_holdout_testable`. **This is
   intended behavior, not a limitation** — it is the PRD's core epistemic guarantee (FuguPRD §1.4, §7).
2. **DECISION 2 (Scope = all 8 phases).** Phases 1–5 are V1 (PRD §21). Phases 6–8 (Blind
   Prosecutor, Forensic Prosecutor, kill/calibration analytics) are detailed here but **explicitly
   GATED on accumulated forward data** per FuguPRD §10/§18.4/§21 and the short PRD's deferrals.
3. **DECISION 3 (Deliverable).** This plan is the tracked markdown doc at
   `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/IMPLEMENTATION_PLAN.md`.

### 0.4 "No fabricated references" note — re-verified for the FINAL pass

Every function signature, table name, column name, file path, and config key cited in this plan was
**re-verified against the live repo and the loop DB (opened read-only) on 2026-06-25** as part of
finalization. The adversarial reviews flagged the references most likely to be hallucinated; each was
re-checked at source. Corrections applied in this pass (versus earlier drafts):

- **`find_existing` / `spec_hash` live in `scripts/harness/sweep_signals.py`, not `scripts/loop/`.**
  Verified: `find_existing(family_key, h)` is `scripts/harness/sweep_signals.py:157`; the spec-hash
  helper `spec_hash(signal_spec, mechanism)` is `:148` (same `hashlib.sha256(json.dumps(spec,
  sort_keys=True) + mechanism)` recipe as `ledgers.register_hypothesis`); the harness-call/dedup block
  is `:206–235`. **Note `find_existing` keys on the raw `family_key` + `signal_spec_hash`**, while the
  deflated-Sharpe N keys on the **canonical** family (`canonical_family_of`). Both are reused as-is.
- **`evaluate_signal` exact signature re-read** (`scripts/harness/evaluate_signal.py:703`):
  `evaluate_signal(hypothesis_id, signal_spec, direction, frequency="monthly", horizons=None,
  universe="t2_34", start_date="2008-01-01")`. `direction` must be `"higher_is_better"` /
  `"lower_is_better"` (NOT `long_high_signal`); there is **no** `primary_horizon` argument here
  (`primary_horizon` is a `register_hypothesis` arg). The harness raises `PermissionError` if the
  `hypothesis_id` was not pre-registered (Gate 1) — which is exactly why the Court must register first.
- **`register_hypothesis` exact signature re-read** (`scripts/loop/ledgers.py:179`):
  `register_hypothesis(archetype, family_key, mechanism_text, signal_spec, author="agent",
  primary_horizon=None) -> str`. It RAISES if `mechanism_text` < 15 words or if the signal `variable`
  matches no family in `config/family_registry.yaml` (`resolve_family`).
- **Loop-DB helpers re-confirmed present** (`scripts/loop/loopdb.py`): `loop_connection(read_only=False)`
  `:72`, `T2_UNIVERSE` `:113`, `t2_countries()` `:123`, `daily_country_returns(con)` `:128`,
  `returns_panel(con, min_countries=10)` `:165`.
- **`factor_returns_daily` is NOT a table in the loop DB** (verified: it lives in the main
  `Data/asado.duckdb`, absent from `Data/loop/asado_loop.duckdb`'s 54 tables). It remains on the
  forbidden list by name regardless — the surface loader's whitelist is default-deny, so a table that
  does not exist in the loop DB cannot leak; and if it ever appeared, the name-match blocks it.
- **`combiner_scores_daily` is a trap — re-verified.** It IS a real loop-DB table (one of 54), and its
  `value` (`variable = COMBINER_RIDGE_DAILY_V1`) is a `Ridge` regression **fit directly on next-5d
  cross-sectionally demeaned forward returns** (`scripts/loop/build_combiner.py:270–278`, target
  horizon `:107`, table create `:307–316`). It is therefore an **outcome surface** and is classified
  as **forbidden** everywhere in this plan — never a Lab input, never in any `allowed_surfaces` block.
  Its siblings `combiner_scores` and `combiner_weights`, and the non-PIT `graph_features_daily`, are
  likewise forbidden. It must **never** enter the Lab whitelist; the plan hard-excludes it in code.
- **`country_returns_daily` is a logical name, not a table.** No such table exists. The real daily
  return surface is the `daily_country_returns(con)` helper (`loopdb.py:130–166`). `forward_track.py`
  resolves the logical name through a whitelist, never `SELECT ... FROM country_returns_daily`.
- **`append_jsonl` is not lock-protected** and **`now_iso()` is tz-naive** (local time) while FuguPRD §11.3
  example timestamps carry an offset. Both are PR-1 / Phase-1 hardening items before any real ledger write.

---

## 1. Current-State Audit — BUILT vs MISSING

### 1.1 What the existing foundation gives us for free

The foundation scaffold is present, but it is **not trusted until PR-1 hardening and tests land**. Four
library modules + four config contracts provide the starting implementation of FuguPRD §7 (routes),
§8 (context builder), and the §20.1/§20.2 paths. Concretely, we already have:

| Asset | What it gives us | Used by phases |
|---|---|---|
| `scripts/discovery_triage/paths.py` | All 9 journal-dir constants + 4 config-path constants + `ensure_dirs()` | All |
| `scripts/discovery_triage/jsonl_store.py` | `append_jsonl`, `read_jsonl`, `write_json`, `latest_id(prefix, records, key)` | All writers; harden in PR-1 |
| `scripts/discovery_triage/provenance.py` | `classify_provenance(ProvenanceInput) -> dict` — the **full cutoff-as-PIT-boundary router** (Invariant D), all 11 branches | 1, 3 |
| `scripts/discovery_triage/context_builder.py` | `assert_outcome_blind`, `build_context_manifest`, `_matches_forbidden` (dotted-column + return/PnL-alias regex) — **code-level blindness** (Invariant E) | 2, 3 |
| `config/discovery_triage.yaml` | status ladder, `llm_certification_policy`, 12 `forbidden_context_surfaces`, 5 discovery searches, docket bounds | 2, 3, 5 |
| `config/claim_provenance_policy.yaml` | 6 classes, 5 legacy tiers, blind-ruling allowed/forbidden inputs | 1, 2 |
| `config/analog_metric_registry.yaml` | 5 metrics + differencing policy (10 axes) | 4 |
| `config/triage_probe_registry.yaml` | 3 required + 2 conditional probes, graveyard tracking flags | 2 |

**Critical existing-harness assets to REUSE (never re-implement):**

- `scripts/loop/ledgers.py` — `register_hypothesis(...)` (`:179`), `get_hypothesis` (`:253`),
  `canonical_family_of` (`:266`), `family_trial_count` (`:278`), `attach_verdict` (`:233`, harness-only).
- `scripts/harness/evaluate_signal.py` — `evaluate_signal(...)` (`:703`), the statistical gate.
- `config/family_registry.yaml` + `scripts/loop/family_registry.py::resolve_family` — the honest
  deflated-Sharpe denominator (Invariant B).
- `scripts/loop/loopdb.py` — `loop_connection(read_only=True)`, `daily_country_returns(con)`,
  `returns_panel(con)`, `t2_countries`, `T2_UNIVERSE`.
- `scripts/harness/ff_spanning.py::style_spanning(...)` — optional orthogonality probe (alpha t<2 ⇒ SPANNED).
- `cos_mockups/build_cockpit_data.py` + `cos_mockups/make_live_cockpit.py` — the live cockpit (light mode).

### 1.2 BUILT vs MISSING against PRD Section 20

**Configs (4 BUILT / 0 MISSING):** all four present, internally consistent with the modules' route/surface strings.

**Journal dirs (9 BUILT / 0 MISSING):** all 9 exist with `.gitkeep` only; **0 JSONL records exist** (no data has flowed).

**Scripts (`scripts/discovery_triage/`) — 5 BUILT / 13 MISSING:**

| File | Status | Phase to build |
|---|---|---|
| `__init__.py` | **BUILT** | — |
| `paths.py` | **BUILT** | — |
| `jsonl_store.py` | **BUILT scaffold** | 1 (lock-protected append + tz-aware timestamps) |
| `context_builder.py` | **BUILT** | (extend in 2/3) |
| `provenance.py` | **BUILT** | (CLI wrapper in 1) |
| `record_look.py` | MISSING | 1 |
| `make_detector_draft.py` | MISSING | 1 (schema) / 3 (Lab) |
| `freeze_claim.py` | MISSING | 1 (schema) / 2 (harness wire) |
| `classify_provenance.py` | MISSING (thin CLI; logic exists) | 1 |
| `run_triage_probes.py` | MISSING | 2 |
| `build_blind_packet.py` | MISSING | 2 |
| `record_blind_ruling.py` | MISSING | 2 |
| `route_claim.py` | MISSING | 2 |
| `lab_session.py` | MISSING | 3 |
| `retrieve_analogs.py` | MISSING | 4 |
| `attach_analog_outcomes.py` | MISSING | 4 |
| `daily_docket.py` | MISSING | 3 |
| `forward_track.py` | MISSING | 2 (entry) / forward readouts wired in nightly |

**New files NOT in PRD §20.1 but required by this plan:**
- `scripts/discovery_triage/surface_loader.py` — code-level whitelist surface loader (Invariant E; Phase 2/3).
- `config/model_registry.yaml` — model→cutoff registry feeding the provenance classifier (stub in Phase 1; populate in Phase 3).

**JSONL stores (Section 20.2) — 0 BUILT / 6 MISSING:** all missing.
`research_looks.jsonl`, `detector_drafts.jsonl`, `claims.jsonl`, `blind_rulings.jsonl`,
`prospective_queue.jsonl`, `graveyard_forward_tracking.jsonl`.

**Tests (`tests/discovery_triage/`) — 0 BUILT / 8 MISSING:** all missing.
`test_context_builder.py`, `test_provenance_classifier.py`, `test_record_look.py`,
`test_freeze_claim.py`, `test_blind_packet.py`, `test_route_claim.py`, `test_graveyard_tracking.py`,
`test_analog_outcome_blindness.py`.

**The single missing wire:** no code path yet calls `register_hypothesis` → `evaluate_signal` from
`scripts/discovery_triage/`. `grep` for these names in the triage dir returns zero hits. Bridging
that wire (Phase 2) is the heart of V1.

---

## 2. Integration Contract — The Non-Negotiable Invariants

Every phase obeys these six invariants. They are restated here with the **exact** reuse targets so
no phase re-derives them.

### INVARIANT A — Court/Triage state never enters `Data/asado.duckdb`

`scripts/setup_duckdb.py` deletes and recreates `Data/asado.duckdb` on every rebuild. Therefore
**all durable Court records live under `journal/`** (JSONL append-only + per-object YAML) in V1.
Folding into `Data/loop/asado_loop.duckdb` is allowed **only later**, after the JSONL workflow
stabilizes (FuguPRD §20.3; short PRD deferral "No new DuckDB tables until JSONL workflow proves stable").

- Writes go through `append_jsonl(path, record)` / `write_json(path, record)` from `jsonl_store.py`.
- The surface loader and `forward_track.py` open the loop DB **read-only**: `loop_connection(read_only=True)`.
- **DuckDB-later fold (FuguPRD §20.3) is EXPLICITLY OUT OF V1 SCOPE.** The 10 candidate loop-DB
  surfaces — `research_looks`, `detector_drafts`, `claim_overlays`, `triage_probe_results`,
  `blind_rulings`, `prospective_incubator`, `graveyard_forward_tracking`, `analog_sets`,
  `analog_members`, `analog_outcomes` — are named here only to record the deferred target. They are
  **not built in V1**; the first legitimate fold is Phase 8 (gated on accumulated forward readouts),
  and even then only into `Data/loop/asado_loop.duckdb`, never `Data/asado.duckdb`. (Short PRD deferral:
  "No new DuckDB tables until JSONL workflow proves stable.")

### INVARIANT B — Do NOT duplicate the harness; reuse the canonical denominator

A claim links to **one existing `hypothesis_id`** via `register_hypothesis(...)`. The deflated-Sharpe
trial count comes from `family_trial_count(canonical_family_of(hyp))` where the family is derived
from the signal **`variable`** (`resolve_family`, `config/family_registry.yaml`), **not** the
free-text `family_key`.

- `register_hypothesis(archetype, family_key, mechanism_text, signal_spec, author="agent", primary_horizon=None) -> str`
  raises `UnclassifiedVariableError` if the variable matches no family. **A Discovery claim whose
  signal is a novel variable prefix MUST add that prefix to `family_registry.yaml` first** (a
  deliberate, git-tracked trust-root edit) or registration fails. The Court gets no private counter.
- Court-specific fields are stored as a **claim OVERLAY keyed to `hypothesis_id`** in
  `journal/claims/claims.jsonl` + `journal/claims/C_*.yaml`. **Never** mutate
  `ledgers/hypothesis_ledger.jsonl` with Court fields — only the harness writes there via `attach_verdict`.
- De-dup re-freezes with the existing helpers `find_existing(family_key, spec_hash(signal_spec,
  mechanism))` from **`scripts/harness/sweep_signals.py`** (`find_existing` `:157`, `spec_hash` `:148`)
  so a re-freeze never double-charges the family. `spec_hash` uses the identical
  `hashlib.sha256(json.dumps(signal_spec, sort_keys=True) + mechanism)` recipe as `register_hypothesis`,
  so a cached verdict is recognised without re-registering. (`find_existing` matches on the raw
  `family_key` + `signal_spec_hash`; the deflated-Sharpe N still keys on the canonical family.)

### INVARIANT C — Cycle protection (forbidden outcome surfaces)

`factor_returns`, `factor_returns_daily`, `factor_top20_membership`, `country_factor_attribution`
are optimizer **outputs**. They are NEVER unioned into `feature_panel`/`unified_panel` and NEVER
used as signal inputs. They are already in `discovery_triage.yaml:forbidden_context_surfaces`. The
surface loader (Invariant E) and `freeze_claim` triage Probe 1 both block them in code.

### INVARIANT D — Model training cutoff is the real PIT boundary for LLM ideas

Tool-level outcome blindness (Invariant E) is **necessary but NOT sufficient**. The router is
`provenance.classify_provenance`. The load-bearing routes (already implemented):
- missing cutoff → `prospective_only_unknown_cutoff`
- `certification_window_start <= model_training_cutoff` → `prospective_only_training_cutoff_contamination`
- `start > cutoff` AND `visibility_mode ∈ {outcome_blind, frozen_window}` AND `tool_enforced_outcome_blind`
  → `post_cutoff_holdout_testable` (the only clean LLM path)
- `start > cutoff` but blindness NOT tool-enforced → `prospective_only_no_tool_enforced_blindness`

`config/discovery_triage.yaml` enforces `ordinary_in_sample_validation_for_llm: forbidden`.

**PR-1 must normalize visibility-mode aliases before any caller can write objects.** Canonical internal
values are `outcome_blind`, `frozen_window`, `full_retrospective`, `legacy_unknown`, `human_pretest`,
`pit_preregistered`, and `deterministic_detector`. Accepted aliases include PRD/user-facing strings such
as `tool_outcome_blind` and `tool-outcome-blind`, both normalized to `outcome_blind` before provenance
classification or context checks. Tests must prove a literal `tool_outcome_blind` request still triggers
outcome-blind enforcement. **Fail-safe:** an unrecognized visibility mode is a hard error (the normalizer
raises) — it is never silently passed through to the underlying fail-open `mode in {...}` checks, so a
typo or a future PRD term cannot skip enforcement by default.

### INVARIANT E — Outcome blindness enforced in CODE at the data-access layer

Not by prompt. The **code-level whitelist** is the single gate. Default-deny: any surface not in the
frozenset raises, regardless of what config or the model requests.

- `context_builder.assert_outcome_blind(requested_surfaces)` raises `ContextPolicyError` on any
  forbidden match (dotted-column rule + return/PnL alias regex).
- `context_builder.build_context_manifest(...)` must call the same visibility-mode normalizer used by
  `provenance.py`; no raw user/PRD string may bypass the `outcome_blind` / `frozen_window` enforcement
  branch.
- `surface_loader.py` (to build) carries a hardcoded `ALLOWED_SURFACES` frozenset of exactly **8**
  raw families: `price_state_daily, valuation_monthly, sovereign_signals, market_implied_signals,
  etf_flow_signals, graph_features_pit_daily, leadlag_features_daily, similarity_features_daily`.
  It applies a **column-level allowlist per table** (default-deny on columns, not only on tables): from
  `price_state_daily` it exposes only the PIT-safe state descriptors (`*_state_json`,
  `price_state_summary`) and never the raw numeric columns. NOTE — verified in `build_price_state.py`
  (`trailing_return` uses `.iloc[-n:]` on data filtered `<= as_of`): the table's actual
  `country_return_5d/21d`, `etf_return_5d/21d`, and `basis_gap_*` columns are **trailing / PIT-safe**,
  but they are still raw realized returns, so the column allowlist excludes them from the model's view
  by default rather than relying on the name-regex (which correctly does NOT match `country_return_21d`).
  A belt-and-suspenders `FORBIDDEN_COLUMN_PATTERNS` denylist (`future_*`, `*forward*`, `realized_return*`,
  `promoted`, `verdict*`, `effective_verdict`, `*pnl*`) backs the allowlist for any column that might ever
  appear. Apply `date <= as_of` on every read (PIT cut; cast `price_state_daily.date` VARCHAR→DATE).
- **`combiner_scores_daily` / `combiner_scores` / `combiner_weights` are FORBIDDEN** (outcome surface,
  §0.4 trap). **`graph_features_daily`** (non-PIT sibling) is FORBIDDEN; only the `_pit_` variant is allowed.

### INVARIANT F — Language discipline

No "validated alpha", "proven signal", "trade recommendation", "promoted by Mythos", or
"high-confidence opportunity" unless truly earned. The Discovery Lab emits **drafts**. The terminal
Court pass state is `triage_passed_not_validated` (`discovery_triage.yaml:status_ladder.triage_pass`),
never "validated alpha". A harness `WATCH` is a statistical pass, not validation. Allowed/forbidden
vocab is enumerated in FuguPRD §24 and gated in code (regex check in `lab_session` output validation,
Phase 3).

---

## 3. Cross-Cutting Foundations (Built First, Used Everywhere)

These are built/finalized in Phase 1 and consumed by all later phases.

### 3.1 ID schemes

All IDs follow `PREFIX_YYYYMMDD_NNN` (3-digit, zero-padded, incrementing within the day). Mint with
the existing `latest_id(prefix, records, key) -> int` then `f"{prefix}_{date}_{n+1:03d}"`:

| Prefix | Object | Store / key | Minter |
|---|---|---|---|
| `L_` | research look | `looks/research_looks.jsonl`, key `look_id` | `record_look.py` |
| `DRAFT_` | detector draft | `drafts/detector_drafts.jsonl`, key `draft_id` | `make_detector_draft.py` |
| `C_` | frozen claim | `claims/claims.jsonl`, key `claim_id` | `freeze_claim.py` |
| `SR_` | sealed rationale | `sealed_rationales/SR_*.yaml`, key `sealed_rationale_id` | `freeze_claim.py` |
| `R_` | blind ruling | `blind_rulings/blind_rulings.jsonl`, key `ruling_id` | `record_blind_ruling.py` |
| `H_` | hypothesis | `ledgers/hypothesis_ledger.jsonl` (existing) | `register_hypothesis` (REUSE) |
| `AQ_` | analog question | per-look output ref | `lab_session.py` / `retrieve_analogs.py` |

Note: `H_` IDs are minted by the existing ledger (`ledgers.py::_next_id`), **not** by triage code.
Court IDs (`L_/DRAFT_/C_/SR_/R_`) are minted by triage `latest_id`.

**Concurrency rule (Sakana final vetting):** Court ID minting and append are one critical section. A
writer must not call `latest_id(...)`, release control, and later append; that creates duplicate IDs under
parallel writers. PR-1 implements a per-store lock helper that reads records, mints the next ID, validates
the object, appends the JSONL line, and `fsync`s before releasing the lock.

### 3.2 Persistence model: JSONL append-only + per-object YAML

- **Append-only event streams** (the 6 §20.2 JSONL files) — one line per event, `recorded_ts`
  stamped by `append_jsonl`.
- **Frozen single-object artifacts** — per-object YAML/JSON via `write_json` (sealed rationales,
  claim files `C_*.yaml`, analog sets, dockets). YAML for human-frozen objects per FuguPRD §14.2/§16.4.
- **Hardening — done in PR-1 (Phase 1), NOT deferred:** because Phase 1 already writes real research-look
  records, JSONL append must use a lock-protected append strategy, not temp-file replace. PR-1 adds a
  `fcntl.flock`-guarded critical section for `(read existing rows → mint id → validate → append one line
  with O_APPEND or an append handle → flush/fsync)`. `now_iso()` is made **timezone-aware** (local-offset
  ISO) to match FuguPRD §11.3 before the first `research_looks.jsonl` line is ever written. Per-object
  JSON/YAML files may still use temp-file + `os.replace`; append-only JSONL ledgers may not.

### 3.3 Object schemas (the contracts every writer/reader honors)

All schemas below are sourced from FuguPRD sections cited. Field-level fidelity is mandatory — tests
assert presence of every required key.

- **look** (§11.3): `look_id`, `created_at`, `actor`, `purpose`, `visibility_mode`,
  `model{model_id, model_version, training_cutoff, tool_context_cutoff}`, `surfaces_seen[]`,
  `surfaces_forbidden[]`, `outputs[]` (`detector_draft:DRAFT_...`, `analog_question:AQ_...`),
  `contamination_class`, `certification_route`.
- **detector_draft** (§10.2): `object_type: detector_family_draft`, `draft_id`, `family_name`,
  `members[]`, `certification_route`, plus mandatory `falsification` (§10.5) and
  `mythos_self_falsification` (§10.6) blocks, `source_look_id`, `epistemic_status[]`.
- **mechanism_graph** (§10.1): `object_type`, `title`, `nodes[]`, `edges[]`, `predicted_observable[]`,
  `status: unvalidated`, `route`, `falsification`, `mythos_self_falsification`.
- **contradiction_card** (§10.4): `object_type`, `entity`, `as_of`, `contradiction{...states}`,
  `mythos_interpretation`, `status: unvalidated`, `route`, `falsification`, `mythos_self_falsification`.
- **analog_taxonomy** (§10.3): `object_type`, `taxonomy_name`, `episode_classes[]`,
  `falsification`, `mythos_self_falsification`.
- **claim** (§14.3): `claim_id`, `links{hypothesis_id, detector_draft_id, source_look_id,
  sealed_rationale_id}`, `provenance{source, visibility_mode, model_training_cutoff,
  certification_window_start, contamination_class, certification_route}`, `neutral_claim.sentence`,
  `mechanism{text, channels[]}`, `variables[]`, `target{return_surface, horizon_days, direction,
  target_type, measurement_shape}`, `expression{etf_ticker, proxy_type, liquidity_tier,
  dollar_adv_21d, bid_ask_spread_bps, expense_ratio_bps, tracking_or_basis_gap, ownership_or_crowding,
  flow_drag}`, `universe{name, min_countries}`, `falsification{fatal_if[], must_check[]}`.
  Plus OVERLAY fields (Invariant B): `harness_verdict`, `court_status`, `triage_flags`,
  `power_budget{...}`, `blind_ruling` (null until ruled), `forward_tracking_id`.
- **triage_result** (§15.4): `claim_id`, `status`, `fatal_failures[]`, `warnings[]`,
  `probes[]` (each `{probe_id, status, detail?}`), `power_budget{...}` (§15.5).
- **blind_ruling** (§16.4): `ruling_id`, `claim_id`, `judge`, `blind_ruling{decision, timestamp,
  rationale}`, `unseal{sealed_rationale_unsealed_at, post_unseal_decision, ruling_changed_after_unseal}`.
- **incubator_entry** (§17.2): `record_kind: incubator_entry`, `claim_id`, `status`, `start_date`,
  `first_readout_date`, `full_readout_date`, `observations_required`, `observations_so_far`,
  `in_sample_certification: forbidden`, `expected_readouts[]`, `return_surface`, `target_country`,
  `measurement_shape`, `direction`, `reason`, `hypothesis_id`.
- **graveyard_entry** (§18.3): `record_kind: graveyard_entry`, `claim_id`,
  `terminal_or_quarantine_status`, `forward_tracking_enabled`, `start_date`, `reason_for_tracking`,
  `expected_readouts[]`, `return_surface`, `target_country`, `measurement_shape`, `direction`,
  `hypothesis_id`. (`measurement_shape`/`direction` mirror `incubator_entry` so `forward_track.py` — which
  keys on `(claim_id, horizon, measurement_shape)` — can score the graveyard control arm without re-reading
  the original claim.)
- **readout** (§14.3/§18 forward-track, this plan): `record_kind: readout`, `claim_id`,
  `hypothesis_id`, `arm` (`incubator`/`graveyard`), `measurement_shape`, `observation_date`,
  `first_forward_date`, `horizon_days`, plus shape-specific metrics: for `single_country_event`,
  `country_cum_return`, `xs_mean_return`, `relative_return`, `n_countries_in_xs`; for
  `cross_sectional_rank_ic`, `rank_ic`, `n_countries_in_xs`; for `long_short_bucket`, `long_return`,
  `short_return`, `ls_return`; for `analog_set_forward_readout`, analog-set aggregate return fields.

**Schema validation from day one (Codex review).** These contracts are not just prose: Phase 1 ships
`scripts/discovery_triage/schemas.py` with a Pydantic (v2) model for **every** written object (look,
detector_draft, mechanism_graph, contradiction_card, analog_taxonomy, claim + overlay, triage_result,
blind_ruling, incubator_entry, graveyard_entry, readout). Every `append_jsonl` / `write_json` writer
validates through the matching model *before* the write, so a malformed object raises at creation and
can never silently corrupt a ledger. Pin `pydantic>=2,<3` in `requirements.txt`. The models are the
single source of truth for the §22 required-key assertions, so each phase's tests validate against them
rather than re-listing keys by hand.

### 3.4 `config/model_registry.yaml`

Maps `model_id → {model_version, training_cutoff, ...}`. Feeds the provenance classifier's
`model_training_cutoff`. **`training_cutoff` MUST be sourced from an official model card or equivalent
provider documentation, never guessed.** A null/unknown cutoff forces
`certification_route = prospective_only_unknown_cutoff`. The stub is created in Phase 1; concrete models,
versions, availability, retention constraints, and cutoff evidence are filled in Phase 3 only after the
hard docs/API verification gate passes. Schema:

```yaml
version: 1
default_model: null
models:
  # Fill after Phase-3 verification. Example keys may include a current Claude/Anthropic model id,
  # but no model id is authoritative until current docs + installed SDK + org access are verified.
  verified_model_id:
    model_version: null
    training_cutoff: null
    training_cutoff_source: null   # URL/doc name or provider reference
    cutoff_retrieved_at: null
    access_mode: null              # API/subscription/ZDR/non-ZDR/etc.
    context_window: null
    max_output_tokens: null
    structured_outputs: null
    retention_constraints: null
certification_routing:
  unknown_cutoff_route: prospective_only_unknown_cutoff
  rule: "if training_cutoff is null OR model_id absent -> unknown_cutoff_route"
```

### 3.5 API-key handling + verified `anthropic` dependency + docs/API gate

- **Dependency:** add the verified current `anthropic` SDK package/version to `requirements.txt` only
  after Phase 3 confirms the provider docs, installed SDK surface, model availability, structured-output
  support, retention mode, and cutoff evidence. Record the exact package version in the Phase 3 PR notes.
- **Context7 verification is a HARD GATE before any Phase 3 LLM code (Codex review):** treat every
  model/API detail in this plan as **untrusted until verified**. Candidate model IDs, the structured
  output call shape, extended-thinking controls, and potentially removed/forbidden generation parameters
  are all assumed stale until reconfirmed at wiring time. Per CLAUDE.md, run `resolve-library-id` →
  `query-docs` for the Anthropic SDK and consult the in-repo `claude-api` skill (the source of truth),
  then reconcile against what the installed SDK actually exposes. **Phase 3 does not start until this
  check passes; if any detail here disagrees with current docs, the docs win** and this section is
  corrected before code is written.
- **Key resolution:** `os.getenv("ANTHROPIC_API_KEY")`, else **first** `ANTHROPIC_API_KEY=` entry in
  `/Users/arjundivecha/Dropbox/AAA Backup/.env.txt`. Never hardcode; FAIL-IS-FAIL if absent.
  (The existing `query_assistant.py` raw-HTTP pattern is the wrong thing to copy — it carries a
  deprecated date-suffixed model and a `temperature` that 400s. Phase 3 uses the SDK.)

---

## 4. PHASE 1 — Minimal Denominator (Provenance + Schemas + Look Ledger)

### (a) Goal + PRD refs
Establish the denominator and provenance spine: research-look ledger, detector-draft schema, claim
schema, provenance classifier CLI, model-cutoff routing, legacy provenance flags. **FuguPRD §11
(Look Ledger), §10.2/§10.5/§10.6 (draft schema), §14.3 (claim schema), §7 (routes), §12 (legacy),
§21 Phase 1.**

### (b) Depends on
Nothing beyond the existing foundation (`provenance.py`, `jsonl_store.py`, `paths.py`, the 4 configs).

### (c) Files to build / modify
- `scripts/discovery_triage/schemas.py` — **NEW.** Pydantic (v2) models for every journal object (§3.3);
  every writer validates through it. (Codex review: schema validation from day one.) Add `pydantic>=2,<3`
  to `requirements.txt`.
- (modify) `scripts/discovery_triage/jsonl_store.py` — **harden now, not Phase 3:** add lock-protected
  JSONL append + ID minting (`fcntl.flock`, append/flush/fsync before unlock); make `now_iso()`
  timezone-aware.
- (modify) `scripts/discovery_triage/provenance.py` and `context_builder.py` — add canonical
  visibility-mode normalization so `tool_outcome_blind` / `tool-outcome-blind` aliases cannot bypass
  outcome-blind enforcement.
- `scripts/discovery_triage/record_look.py` — write a `look` record to `looks/research_looks.jsonl`; mint `L_` id.
- `scripts/discovery_triage/classify_provenance.py` — thin CLI wrapper around
  `provenance.classify_provenance` (logic already exists); reads `model_registry.yaml` for cutoff.
- `scripts/discovery_triage/make_detector_draft.py` — write a `detector_draft` to
  `drafts/detector_drafts.jsonl` + per-object YAML; **enforce `source_look_id` present** (FuguPRD §11.4).
- `scripts/discovery_triage/freeze_claim.py` — **Phase-1 portion only:** write the claim *schema*
  (validate §14.3 required keys, mint `C_`, mint `SR_` sealed-rationale file). Harness wiring is Phase 2.
- `config/model_registry.yaml` — created here as a stub (cutoffs null), populated in Phase 3.
- (modify) `scripts/discovery_triage/__init__.py` — re-export new entrypoints if convenient.

### (d) Key logic & decisions
- **Look→draft linkage (FuguPRD §11.4):** `make_detector_draft.py` refuses to write a draft without
  a resolvable `source_look_id` that exists in `research_looks.jsonl` (read via `read_jsonl`).
- **Locked writer discipline:** every writer that mints `L_` / `DRAFT_` / `C_` / `SR_` / `R_` IDs uses
  a lock-protected helper that reads the current store, mints the next ID, validates through `schemas.py`,
  appends the JSONL event or writes the per-object file, and `fsync`s before unlocking. This is a PR-1
  trust boundary, not a later durability enhancement.
- **Visibility normalization:** CLI args, JSON/YAML inputs, and PRD-facing strings are normalized before
  classification or context checks. Tests include `tool_outcome_blind` and `tool-outcome-blind` as aliases
  for canonical `outcome_blind`.
- **Provenance routing (Invariant D):** `classify_provenance.py` builds a `ProvenanceInput` from CLI
  args + `model_registry.yaml`. If `generator_type == "llm"` and the model's `training_cutoff` is
  null/missing → the classifier already returns `prospective_only_unknown_cutoff`. Do not special-case;
  trust the existing 11-branch router.
- **Legacy flags (§12):** support `visibility_mode: legacy_unknown` + `legacy_tier` passthrough →
  classifier returns `legacy_grandfathered_forward_tracking`. `allowed_language: live_observed_strategy`,
  `forbidden_language: cleanly_validated_alpha` (Invariant F).
- **Claim schema validation (§14.3):** `freeze_claim.py` rejects a claim missing any of:
  `provenance`, `neutral_claim`, `mechanism`, `variables`, `target.measurement_shape`, `expression`,
  `falsification`. Sealed rationale (bull case / generator rationale) is written to a SEPARATE `SR_*.yaml`
  and only its id goes in the claim. `expression` is required because ASADO trades country ETFs: the
  claim must freeze the intended ETF/proxy and basic implementation quality before the idea is judged.
- **Cutoff gate is code-enforced at freeze time (Invariant D — closes an epistemic leak found in review):**
  `freeze_claim.py` requires `provenance.certification_window_start` to be present (reject if null) and
  **re-runs `classify_provenance(...)` itself** — it does NOT trust a `certification_route` the caller or
  LLM supplied. It stamps the route the classifier returns and **rejects any freeze whose stated intent is
  historical certification while the computed route is `prospective_only_*` or `*_unknown_cutoff`.** A human
  therefore cannot set `certification_window_start` after the model cutoff (or null it out) to launder a
  pre-cutoff LLM idea — the classifier, not the human, decides. For LLM-generated claims the only
  historically-testable route is `post_cutoff_holdout_testable`; everything else is forced to
  prospective-only *before* the Phase-2 harness wire can run on historical data.
- **Language discipline is code-enforced at freeze (Invariant F — not only on Lab output):**
  `freeze_claim.py` runs a forbidden-vocabulary regex (FuguPRD §24: "validated alpha", "proven signal",
  "promoted by Mythos", "trade recommendation", "high-confidence opportunity", "clean historical
  certification") over `neutral_claim.sentence` and `mechanism.text`, raising `ContextPolicyError` with the
  offending phrase. This catches manually-frozen claims, not just `lab_session` output.

### (e) Integration points
- Reuses `provenance.classify_provenance`, `jsonl_store.*`, `paths.*`.
- Produces the `look_id`/`draft_id`/`claim_id`/`SR_id` consumed by Phase 2/3.

### (f) Tests
- `tests/discovery_triage/test_provenance_classifier.py` — asserts: missing cutoff → `prospective_only_unknown_cutoff`;
  `start <= cutoff` → `prospective_only_training_cutoff_contamination`; `start > cutoff` + tool-enforced
  blind → `post_cutoff_holdout_testable`; deterministic → `measured_gap_claim_required`; legacy → grandfathered.
  Also assert `tool_outcome_blind` and `tool-outcome-blind` normalize to canonical `outcome_blind`.
- `tests/discovery_triage/test_record_look.py` — appended look has all §11.3 keys; `L_` id increments;
  reading back via `read_jsonl` round-trips.
- `tests/discovery_triage/test_schemas.py` — every Pydantic model accepts a golden valid object and
  rejects a missing-required-key variant, including missing `measurement_shape` and missing `expression`
  on claims; lock-protected append leaves the prior file intact / adds no torn line on simulated failure;
  concurrent ID-mint tests do not produce duplicates; `now_iso()` carries a UTC offset.
- (partial) `tests/discovery_triage/test_freeze_claim.py` — claim missing `falsification`/`provenance`
  is rejected; a valid §14.3 claim writes both `claims.jsonl` and `C_*.yaml`; bull case lands only in `SR_*.yaml`.
  **Cutoff gate (Invariant D):** an LLM claim with `certification_window_start <= training_cutoff` (or null)
  that asks for historical certification is rejected/forced to prospective-only, and a caller-supplied
  `post_cutoff_holdout_testable` route is **overridden** by the classifier's own re-computation.
  **Language discipline (Invariant F):** a claim whose `neutral_claim.sentence` contains "validated alpha"
  / "trade recommendation" raises `ContextPolicyError`.

### (g) V1 acceptance criteria satisfied (§22)
**#5, #6** (provenance routing pre-cutoff → prospective; post-cutoff tool-blind → holdout), **#7**
(drafts require looks), **#8** partial (claims require provenance + falsification fields).

### (h) Effort: **M** (5 small CLIs + `schemas.py` + `jsonl_store` hardening + 1 config stub; core
provenance logic already exists). Information, not a constraint.

---

## 5. PHASE 2 — Discipline Before Lab (delivered as two PRs: 2A then 2B)

### (a) Goal + PRD refs
Build everything that must exist **before** the daily Lab is enabled (short PRD design decision #3).
Per the Codex review, this phase ships as **two reviewable slices** so one PR is not overloaded:

- **Phase 2A — Outcome-blind discipline (no harness; fully offline-testable):** `surface_loader.py`
  (+ forbidden-surface/column tests), `run_triage_probes.py` (+ power band), `build_blind_packet.py`,
  `record_blind_ruling.py`, `route_claim.py` (writes incubator/graveyard ENTRY records). None of this
  touches the harness or realized returns, so it tests entirely on a synthetic read-only fixture.
- **Phase 2B — Harness bridge + forward tracking:** the `freeze_claim.py` harness wire
  (`register_hypothesis` → `evaluate_signal` + overlay + pre-harness gate) and `forward_track.py`
  (the readout engine + nightly wiring). **2B depends on 2A** (claims must be routed before readouts run).

**FuguPRD §8 (context), §15 (triage + power band), §16 (blind ruling), §17/§18 (router targets),
§14.4 (harness overlay), §21 Phase 2.** Each file/logic/test bullet below is tagged **[2A]** or **[2B]**.

### (b) Depends on
Phase 1 (claim schema, look ledger, provenance CLI). The existing harness/ledger/family-registry.

### (c) Files to build / modify
- **[2A]** `scripts/discovery_triage/surface_loader.py` — **NEW.** Code-level `ALLOWED_SURFACES` frozenset
  (8 families) + **per-table column allowlist** + `FORBIDDEN_COLUMN_PATTERNS` denylist (§Invariant E);
  `load_country_snapshot(as_of)` reads via `loop_connection(read_only=True)` with `date <= as_of`; raises
  `PermissionError` on any non-whitelisted table **or column**.
- **[2A]** `scripts/discovery_triage/run_triage_probes.py` — runs the registry probes (FuguPRD §15.2/§15.3),
  emits `triage_result` (§15.4) + power band (§15.5).
- **[2A]** `scripts/discovery_triage/build_blind_packet.py` — builds the blind packet from §16.2 allowed
  inputs ONLY; strips every §16.3 forbidden input (rationale, bull case, excitement, transcript).
- **[2A]** `scripts/discovery_triage/record_blind_ruling.py` — writes `R_` ruling to `blind_rulings.jsonl`;
  records `ruling_changed_after_unseal`.
- **[2A]** `scripts/discovery_triage/route_claim.py` — routes claim → `prospective_queue.jsonl` (incubator_entry)
  or `graveyard_forward_tracking.jsonl` (graveyard_entry).
- **[2B]** `scripts/discovery_triage/forward_track.py` — **NEW (readout engine).** Reads incubator/graveyard
  rosters; idempotent per `(claim_id, horizon, measurement_shape)`; dispatches to a shape-specific
  calculator (`single_country_event`, `cross_sectional_rank_ic`, `long_short_bucket`,
  `analog_set_forward_readout`) via the whitelist resolver; appends `readout` records. (Wired into nightly
  in §14/§11 sequencing.)
- **[2B]** (modify) `scripts/discovery_triage/freeze_claim.py` — **Phase-2 portion:** call the harness bridge
  (`register_hypothesis` → `evaluate_signal`) and write the overlay to `claims.jsonl`.
- **[2B]** (modify) `config/family_registry.yaml` — add any novel signal variable prefix a claim needs
  (deliberate git-tracked trust-root edit, Invariant B) — only when a real claim requires it.

### (d) Key logic & decisions
- **[2B] Harness bridge (Invariant B), the heart of V1** — `freeze_claim.py` mirrors the verified pattern in
  `scripts/harness/sweep_signals.py:206–235`:
  1. `os.environ.setdefault("ASADO_MODEL_ID", model_id)` (provenance stamp).
  2. De-dup: `existing = find_existing(family_key, spec_hash(signal_spec, mechanism))` → if
     `existing and existing.get("verdict")`, reuse it, do **not** re-register and do **not** re-charge
     the family (exactly the `sweep_signals.py:212–224` cached path).
  3. `hyp_id = register_hypothesis(archetype="other", family_key=..., mechanism_text=...(≥15 words),
     signal_spec=..., author=model_id, primary_horizon=...)` — verified signature
     (`ledgers.py:179`); raises on <15-word mechanism or unclassifiable variable.
  4. `result = evaluate_signal(hyp_id, signal_spec, direction="higher_is_better"|"lower_is_better",
     frequency=..., horizons=..., universe="t2_34", start_date=...)` → `result["verdict"]`
     (WATCH/WEAK/DEAD/INSUFFICIENT_*). **Verified signature** (`evaluate_signal.py:703`): `direction`
     is `higher_is_better`/`lower_is_better` (translate the claim's `target.direction` to this); there
     is **no** `primary_horizon` kwarg here (that lives on `register_hypothesis`); Gate 1 raises
     `PermissionError` unless the `hyp_id` is already registered (hence step 3 first).
  5. Write the **overlay** to `journal/claims/claims.jsonl` keyed to `hyp_id` (Invariant A); also
     refresh `C_*.yaml`. **Never** touch `hypothesis_ledger.jsonl` with Court fields.
  - **Pre-harness gate (Invariants C + D):** before calling the harness, `freeze_claim` asserts the claim's
    `table`/`sql` references **no** forbidden optimizer surface and the `variable` is not in
    `FORWARD_RETURN_VARIABLES`; that the `variable` resolves in `family_registry.yaml` (else add
    the prefix first or fail loudly); **and that the claim's computed `certification_route` is
    `post_cutoff_holdout_testable`, `pit_preregistered`, or a `measured_gap_*` deterministic route before
    any historical `evaluate_signal` run.** An LLM claim routed prospective-only is recorded and
    forward-tracked but is **never** sent to the historical harness for certification. If a retrospective
    descriptive run is ever allowed for research diagnostics, it must happen after the blind ruling and
    must never feed the pre-ruling blind packet or any certification language.
- **[2A] Triage probes (§15.2/§15.3):**
  - **Probe 1 target_reentry (FATAL):** reject if signal variables/tables touch future returns,
    optimizer outputs, factor returns, top-20 membership, country attribution, target-derived
    transforms (Invariant C). Reuses the same forbidden-surface list as the context builder.
  - **Probe 2 leave_one_crisis_out (warning):** drop GFC/COVID/2022/China-2015/Eurozone windows;
    flag crisis concentration; do not auto-kill unless extreme.
  - **Probe 3 country_region_jackknife (warning):** flag if one country/region owns the signal.
  - **Conditional:** `publication_lag_sensitivity` (revised macro sources), `horizon_profile` (when
    mechanism implies a horizon).
- **[2A] Power-budget band (§15.5, band NOT verdict):** `power_budget_band(con, horizon_days, ...)` from
  `returns_panel(con)`: non-overlapping block count `n_dates = len(piv)//horizon` × effective-N over
  a correlation band [0.25, 0.55]; detectable-IC band `2.8/sqrt(eff_n)`. **An underpowered claim is
  routed to the incubator with its band attached — never killed.** The band is one input to the
  blind ruling.
- **[2A] Blind packet (§16.2/§16.3):** allowed = neutral_claim, provenance, model cutoff, certification
  route, triage output, expression block, and power band. Harness stats are included **only when applicable
  by route**: `post_cutoff_holdout_testable`, `pit_preregistered`, or deterministic/harness-clean. For
  `prospective_only_*`, `legacy_unknown`, and retrospective LLM routes, pre-ruling packets must exclude
  historical IC/Sharpe/verdict fields even if someone ran them descriptively. Forbidden = generator
  rationale, bull case, excitement score, trade recommendation, discovery transcript. The packet reads the
  claim but explicitly never reads `SR_*.yaml`.
- **[2A] Blind ruling (§16.1):** record preliminary `blind_ruling.decision` BEFORE unseal; on unseal,
  record `post_unseal_decision` and set `ruling_changed_after_unseal` (config
  `claim_provenance_policy.yaml:blind_ruling.log_ruling_change_after_unseal: true`).
- **[2A] Router (§17/§18):** survivors with `post_cutoff_holdout_testable` + a clean harness verdict may
  stay testable; everything else (pre-cutoff, unknown-cutoff, retrospective, underpowered, killed)
  routes to forward tracking. Killed/quarantined → graveyard control arm (`graveyard_is_control_arm: true`).
  Router writes the **entry** record (incubator/graveyard); `forward_track.py` writes **readouts**.
- **[2B] Forward-track return-surface whitelist (Invariant C/E):** `forward_track.py` uses
  `RETURN_SURFACE_RESOLVERS = {"country_returns_daily": daily_country_returns,
  "country_returns_monthly": <SELECT date,country,return_1m AS ret>}`; any other name raises.
  **`country_returns_daily` is a logical name resolved to the `daily_country_returns(con)` helper —
  not a table** (§0.4 caveat). Reading realized returns is correct here (outcome side, post-decision);
  it never touches optimizer surfaces. The resolver returns raw return panels; `measurement_shape` decides
  whether the readout is a country-relative event, cross-sectional rank IC, long/short bucket return, or
  analog-set aggregate.

### (e) Integration points
- `register_hypothesis`/`evaluate_signal`/`family_trial_count`/`canonical_family_of` (REUSE).
- `loop_connection(read_only=True)`, `daily_country_returns`, `returns_panel`, `T2_UNIVERSE` (REUSE).
- `ff_spanning.style_spanning(...)` as an optional orthogonality probe on a claim's LS P&L.
- `forward_track.py` wired into `scripts/loop/loop_daily_job.py` `STEPS` (the `("name", [PY, "..."])`
  tuple list at `loop_daily_job.py:175`) **after** `build_country_returns` (`:178`, the marking surface
  it reads) and after `mark_theses` (`:177`, the ledger fold). Add a matching `- name: discovery_forward_track`
  entry with `optional: true` in `config/governance_contract.yaml` (per-step `optional` flag, contract
  `:41`/`:51`) so a soft skip / exit-2 never reds governance (see §14/§11).

### (f) Tests
- **[2A]** `tests/discovery_triage/test_context_builder.py` — requesting `forward_returns`, `harness_results`,
  `factor_returns_daily`, `hypothesis_ledger.verdict`, or any `*.verdict`/`*pnl*` surface raises
  `ContextPolicyError`; an allowed 8-family request passes; manifest records cutoff + tool-enforced flag.
  Also assert `surface_loader._check` raises `PermissionError` for `combiner_scores_daily`,
  `graph_features_daily`, `country_returns_monthly`, `factor_returns`, **and for a raw return column
  (`country_return_21d`) that is not on the per-table column allowlist.**
- **[2B]** `tests/discovery_triage/test_freeze_claim.py` (full) — freeze a synthetic claim against a tiny
  fixture loop DB: asserts a `hypothesis_id` is minted, the overlay lands in `claims.jsonl` keyed to it,
  `hypothesis_ledger.jsonl` is NOT mutated with Court fields, and a re-freeze of the same spec does not
  double-charge the family (`family_trial_count` unchanged).
- **[2A]** `tests/discovery_triage/test_blind_packet.py` — packet contains only §16.2 keys; asserts bull case /
  generator rationale / excitement score / transcript are absent; asserts the packet never opened `SR_*.yaml`;
  asserts `prospective_only_*` claims exclude historical harness stats while clean post-cutoff / PIT routes may
  include them.
- **[2A]** `tests/discovery_triage/test_route_claim.py` — a `prospective_only_*` claim writes an `incubator_entry`;
  a `killed_fatal_leakage` claim writes a `graveyard_entry` with `forward_tracking_enabled: true`.
- **[2B]** `tests/discovery_triage/test_graveyard_tracking.py` — `forward_track.py` over a fixture: a matured
  `(claim_id, horizon, measurement_shape)` writes exactly one shape-appropriate `readout`; re-running writes
  nothing (idempotent); an unmatured horizon writes nothing and is retried next run.

### (g) V1 acceptance criteria satisfied (§22)
**[2A]** **#4** (context rejects forbidden surfaces), **#9** (blind packets exclude rationale/bull case),
**#10** (blind rulings log post-unseal changes), **#11** (killed/quarantined → graveyard forward tracking).
**[2B]** **#8** complete (claims require provenance + falsification, frozen against the harness denominator).

### (h) Effort: **2A = M** (surface loader + 4 CLIs + 3 offline tests, no harness). **2B = M** (harness
wire + forward-track engine + 2 tests). Splitting keeps each PR reviewable. Information, not a constraint.

---

## 6. PHASE 3 — Quarantined Discovery Lab (Real Claude Model) + Daily Docket

### (a) Goal + PRD refs
Wire a **real current Claude model** as the quarantined research physicist that emits drafts/cards
against the tool-enforced outcome-blind context, then render the daily docket. **FuguPRD §6 (model
assumption + metadata), §9 (Lab + 5 searches + docket), §10 (object types + self-falsification),
§21 Phase 3. DECISION 1.**

### (b) Depends on
Phase 1 (look ledger, provenance, draft schema) + Phase 2 (surface loader, context builder usage).

### (c) Files to build / modify
- `scripts/discovery_triage/lab_session.py` — **NEW.** End-to-end Lab driver: build outcome-blind
  context → call Claude with strict structured output → validate → record look + write drafts.
- `scripts/discovery_triage/make_detector_draft.py` — **Phase-3 portion:** the Lab calls it to persist
  validated draft objects (it already enforces `source_look_id`).
- `scripts/discovery_triage/daily_docket.py` — **NEW.** Render `journal/dockets/discovery_docket_YYYY_MM_DD.md`
  with 3–10 cards, each carrying its `epistemic_status` + route.
- `config/model_registry.yaml` — **populate** `model_version` (via `client.models.retrieve`) and
  `training_cutoff` plus cutoff evidence (`training_cutoff_source`, `cutoff_retrieved_at`, `access_mode`,
  retention constraints). Unknown cutoffs remain null.
- (modify) `requirements.txt` — add the verified current Anthropic SDK package/version after the Phase-3
  docs/API gate passes.
- (`jsonl_store.py` lock-protected append + tz-aware `now_iso()` hardening is **already shipped in PR-1 / Phase 1**
  — see §3.2 — so there is no JSONL hardening work left in Phase 3.)

### (d) Key logic & decisions
- **The 5 daily discovery searches (FuguPRD §9.2, enumerated in `discovery_triage.yaml:discovery_searches`):**
  the Lab supports all five, each pinned to its own `allowed_surfaces` whitelist (so the surface loader
  enforces blindness per-search): (1) `cross_surface_contradiction`, (2) `graph_motif`,
  (3) `analog_mismatch`, (4) `regime_sign_flip`, (5) `nonlinear_condition_draft`. Until Phase 4 ships
  `retrieve_analogs.py`, the `analog_mismatch` search is disabled or emits an explicit
  `analog_retrieval_not_enabled` placeholder; it must not fabricate analog sets. `lab_session.py` takes
  `--search <id>` and reads the search's `allowed_surfaces` from the YAML, never a free-text list.
- **The 6 discovery object types (FuguPRD §10) the Lab can emit — each a Pydantic model:**
  (1) `mechanism_graph` (§10.1: `nodes/edges/predicted_observable`), (2) `detector_family_draft`
  (§10.2: `family_name/members/certification_route`), (3) `analog_taxonomy` (§10.3: `episode_classes`),
  (4) `contradiction_card` (§10.4: per-surface `contradiction` states + `mythos_interpretation`),
  (5) `falsification` block (§10.5 — **mandatory on every draft**), (6) `mythos_self_falsification`
  block (§10.6 — **mandatory on every Lab output**: `strongest_objection`, `easiest_way_this_is_leakage`,
  `first_probe_to_run`, `condition_under_which_i_would_abandon_this`). Object schemas are restated in
  §3.3 with field-level fidelity; Pydantic validators enforce that (5) and (6) are present and non-empty.
- **SDK call pattern (provisional, §14.1):** the call shape in §14.1 is a blueprint only. Phase 3 starts
  by verifying current official docs, installed SDK methods, model IDs, structured-output support,
  retention/access constraints, and cutoff-source availability. If docs/API disagree with this plan, the
  docs/API win and this plan is corrected before code.
- **Outcome-blind context (Invariant E):** `lab_session` calls
  `context_builder.build_context_manifest(ContextRequest(visibility_mode="outcome_blind",
  requested_surfaces=[...8 families...], ...))` → this raises before any LLM call if a forbidden
  surface leaks. The actual data sent to the model comes from `surface_loader.load_country_snapshot(as_of)`
  (whitelist-gated, `date <= as_of`). The model **never** receives forward returns,
  `combiner_scores_daily`, factor returns, harness verdicts, or PnL.
- **DECISION 1 — current-cutoff models correctly route to prospective-only (the intended behavior):**
  Each draft is tagged with `model_training_cutoff` and cutoff evidence from `model_registry.yaml`.
  Because current model cutoffs usually precede any historical certification window, `classify_provenance` routes a
  historical-window LLM idea to `prospective_only_training_cutoff_contamination` (start ≤ cutoff) or
  `prospective_only_unknown_cutoff` (cutoff null). **Only a forward window after the cutoff** is
  `post_cutoff_holdout_testable`. This is the PRD's guarantee, not a bug — the Lab is for discovery,
  certification waits for forward evidence. Drafts loudly carry this route.
- **Language discipline (Invariant F):** the system prompt forbids validation/performance language
  ("works", "outperforms", "Sharpe", "backtest confirms"); a regex gate on `resp.parsed_output`
  rejects forbidden vocab (FuguPRD §24) and rejects empty `falsification`/`mythos_self_falsification`.
- **Record-then-write order (CLAUDE.md fault tolerance):** append the `research_look` first (model id,
  version, cutoff, cutoff source, access mode, effort, manifest hash, `stop_reason`, usage,
  provider request id if available), then append each
  draft (incremental persistence — never accumulate in memory and write at the end).
- **Daily docket (§9.3):** select the 7 docket cards (weirdest contradiction, best analog mismatch,
  strongest detector draft, most interesting mechanism graph, most important falsification idea, one
  triage-killed idea, one prospective-routed idea), 3–10 total. Each card prints its loud
  epistemic-status label. The docket is markdown only (no DuckDB).

### (e) Integration points
- `build_context_manifest` + `surface_loader` (Phase 2) + `provenance.classify_provenance` (Phase 1).
- Feeds Phase 2's `freeze_claim` (a docket draft a human selects becomes a frozen claim).
- Feeds Phase 5 cockpit `read_discovery_lab` (reads `detector_drafts.jsonl`).

### (f) Tests
- `tests/discovery_triage/test_lab_session.py` (new; not in §20.1 but needed) — **monkeypatch the
  Anthropic client** (no network): a stub returns a valid structured object; assert a `look` and a
  `draft` are written, the draft carries the cutoff-derived route, and forbidden-vocab output is
  rejected. Assert that requesting a forbidden surface in the context request raises before any
  (stubbed) model call.
- Extend `tests/discovery_triage/test_context_builder.py` to cover the `lab_session` manifest path.
- Assert the docket renderer caps at 3–10 cards and stamps every card with an epistemic label.

### (g) V1 acceptance criteria satisfied (§22)
**#5/#6** reinforced (real cutoff routing), **#7** (drafts require looks, enforced live),
**#12** (daily docket renders 3–10 unvalidated ideas with epistemic labels).

### (h) Effort: **L** (real SDK wiring + Pydantic schemas + prompt + docket + monkeypatched tests +
model-card cutoff lookup).

---

## 7. PHASE 4 — Fixed-Metric Analog Shelf

### (a) Goal + PRD refs
Outcome-blind analog retrieval under fixed metrics, frozen analog sets, outcome attachment **after**
freeze, constrained differencing. **FuguPRD §13 (analog shelf, registry, workflow, difference axes,
forbidden behavior), §21 Phase 4.**

### (b) Depends on
Phase 2 surface loader (the analog distance is computed over allowed surfaces only) + Phase 1 schemas.

### (c) Files to build / modify
- `scripts/discovery_triage/retrieve_analogs.py` — **NEW.** Outcome-blind retrieval under a registered
  metric (`config/analog_metric_registry.yaml`); writes a **frozen** analog set to `journal/analog_sets/`.
- `scripts/discovery_triage/attach_analog_outcomes.py` — **NEW.** Attaches forward outcomes to a
  frozen analog set ONLY after it is frozen; refuses to change membership.

### (d) Key logic & decisions
- **5 fixed metrics (§13.2):** `macro_state_v1`, `price_state_v1`, `stress_state_v1`, `graph_state_v1`,
  `mixed_state_v1`. Each has `feature_blocks`, `distance`, `lookback_window_days`, `outcome_blind: true`
  from the registry.
- **Outcome-blind distance (Invariant E):** features come from `surface_loader.load_country_snapshot`
  (allowed surfaces only, `date <= as_of`). The retrieval **never** reads forward returns or
  `combiner_scores_daily`.
- **Freeze-then-attach (§13.4):** `retrieve_analogs.py` writes a frozen set with
  `set_frozen_at`; `differencing_policy.may_view_forward_outcomes_before_set_frozen: false`.
  `attach_analog_outcomes.py` checks `set_frozen` and only then reads realized forward outcomes
  (via the same whitelist resolver as `forward_track.py`).
- **Membership immutability (§13.4/§13.6):** differencing `may_change_analog_membership: false`.
  `allowed_outputs: [analog_note, detector_draft, claim_candidate, caveat]` only — **no trade
  promotion**. The 10 allowed difference axes (§13.5) are enforced by the registry.

### (e) Integration points
- Reuses surface loader; outcome attachment reuses the return-surface whitelist.
- Feeds Phase 5 cockpit `read_analog_shelf` (reads `journal/analog_sets/*`).

### (f) Tests
- `tests/discovery_triage/test_analog_outcome_blindness.py` — asserts: retrieval never selects a
  forward-return / combiner column; membership is fixed at freeze; `attach_analog_outcomes` refuses to
  run before `set_frozen`; differencing cannot mutate membership and cannot emit a trade output.

### (g) V1 acceptance criteria satisfied (§22)
**#13** (analog outcome-blindness test passes). Supports G1 (recover the dream) and the §23
analog-smuggling risk mitigation.

### (h) Effort: **M** (2 CLIs + 1 test; distance math over the snapshot).

---

## 8. PHASE 5 — Research Desk Cockpit Integration

### (a) Goal + PRD refs
Extend the existing live cockpit (committed in `69ccb09`) with the 7 research-desk panels, each
screaming its epistemic status. **FuguPRD §19 (panels + "label the magic"), §21 Phase 5.**

### (b) Depends on
Panel *content* comes from Phases 1–4, but the panels themselves need not wait. **Codex review — stand up
the empty-state Research Desk shell right after Phase 2** (a thin slice: the 7 panels + status badges +
the 6 readers returning `[]`), so the front-end can settle around the new layout while the Lab and analog
shelf are still being built. Readers render an explicit "no entries yet" state until writers have run —
never fabricate. Full content lands as Phases 3–4 produce their JSONL/YAML.

### (c) Files to build / modify (extend, do not fork)
- (modify) `cos_mockups/build_cockpit_data.py` — add 6 reader fns (`read_discovery_lab`,
  `read_analog_shelf`, `read_under_triage`, `read_blind_rulings`, `read_prospective`, `read_graveyard`),
  each wrapping `discovery_triage.jsonl_store.read_jsonl(<journal path>)` in the existing `_safe()`;
  add `payload["research_desk"] = {...}` in `build_payload()` (`:794`), before `con.close()` (`:844`).
  Rename the
  existing `#dislo` panel to **"Known Gaps"**; keep `read_dislocations`/`read_gap_engine` unchanged.
  Update the header INPUT FILES block to list the `journal/*.jsonl` paths.
- (modify) `cos_mockups/cockpit.html` — add 6 panels as new `FVIEWS` focus sub-views reachable from a
  top ribbon nav, reusing `.subpanel`/`.chip`/`.v-watch` styling; add a status-badge CSS class set for
  the 7 epistemic labels using the existing light palette (`--oxblood/--amber/--teal`). **Light mode
  only — add no `prefers-color-scheme`, no dark styles.**
- (regenerate) `cos_mockups/cockpit_live.html` — re-run `cos_mockups/make_live_cockpit.py` (no
  structural change; `window.COCKPIT_DATA` is already generic).
- (modify) `scripts/loop/loop_daily_job.py` + `config/governance_contract.yaml` — append
  `("build_cockpit_data", [PY, "cos_mockups/build_cockpit_data.py"])` (and optionally
  `make_live_cockpit`) AFTER the governance tail; mark `optional: true` so a cockpit failure never
  reds the loop.

### (d) Key logic & decisions
- **Panel → feed map:** Known Gaps = `payload["dislocations"]`+`gap_engine` (exists; add a
  "DETERMINISTIC — measured state, not alpha" badge). Discovery Lab = `detector_drafts.jsonl`.
  Analog Shelf = `journal/analog_sets/*` + `analog_metric_registry.yaml`. Under Triage =
  `claims.jsonl` filtered to open-probe status. Blind Rulings = `blind_rulings.jsonl` (preliminary
  ruling before unseal; sealed rationale stays in `sealed_rationales/`, **never surfaced**).
  Prospective = `prospective_queue.jsonl`. Graveyard = `graveyard_forward_tracking.jsonl`.
- **"Label the magic" (§19.2, Invariant F):** every Discovery Lab / Analog / Prospective / Graveyard
  card carries its `provenance_class`/`certification_route` badge: `UNVALIDATED`, `TOOL-OUTCOME-BLIND`,
  `PRE-CUTOFF MODEL CONTAMINATION POSSIBLE`, `POST-CUTOFF HOLDOUT TESTABLE`, `PROSPECTIVE REQUIRED`,
  `RETROSPECTIVE-SNOOPED`, `LEGACY UNKNOWN`. These map 1:1 to `provenance.py` route strings.

### (e) Integration points
- All 6 readers consume the journal JSONL produced by Phases 1–4.
- The nightly hook (currently absent) is added so panels refresh on the loop cadence.

### (f) Tests
- `tests/discovery_triage/test_cockpit_readers.py` (new; not in §20.1) — each reader returns `[]`
  (empty-state) when its JSONL is absent (no fabrication), and parses a golden JSONL row into the
  expected card dict carrying `provenance_class`. (Pure-Python, no DB needed for the journal readers.)

### (g) V1 acceptance criteria satisfied (§22)
Supports G6 (cockpit magical but epistemically honest) and surfaces #12's docket/drafts. No new §22
item is *uniquely* gated on the cockpit, but it is the §21 Phase 5 deliverable.

### (h) Effort: **M** (6 readers + HTML panels + nightly hook; reuse existing cockpit machinery).

---

## 9. PHASE 6 — Optional Blind Prosecutor  — **GATED**

> **GATE:** FuguPRD §1.10 + §21 Phase 6 — "Only after V1 workflow is useful." Short PRD deferral:
> "No LLM Prosecutor in V1." Do not build until Phases 1–5 are running daily and a meaningful number
> of frozen claims exist.

### (a) Goal + PRD refs
An LLM **Blind Prosecutor** that attacks a frozen claim seeing only neutral claim, provenance, stats,
and probes — **not** the bull case. **FuguPRD §5.11, §1.10, §21 Phase 6.**

### (b) Depends on
Phase 2 blind packet (the prosecutor consumes exactly the §16.2 allowed inputs) + Phase 3 SDK wiring
+ accumulated frozen claims.

### (c) Files to build (future)
- `scripts/discovery_triage/blind_prosecutor.py` — feeds the blind packet (NOT `SR_*.yaml`) to a Claude
  model; emits structured objections; appends to a new `journal/prosecutions/blind_prosecutions.jsonl`.

### (d) Key logic & decisions
- Reuses Phase 2 `build_blind_packet.py` output verbatim (chain-of-custody: the prosecutor sees only
  what the human saw blind). Reuses Phase 3 SDK call discipline (structured output, no temperature,
  stop_reason check, outcome-blind context). Output is an **attack**, not a verdict — it is one more
  input to the human ruling, never an auto-kill (Invariant F).

### (e) Integration points
- Slots between Phase 2 triage and Phase 2 blind ruling as an optional extra adversarial input.

### (f) Tests (future)
- `test_blind_prosecutor.py` — monkeypatched model; assert the prosecutor packet excludes bull
  case/rationale (reuses the `build_blind_packet` guarantees); assert output carries no validation
  language and no trade recommendation.

### (g) V1 acceptance: **none** (deferred). (h) Effort: **M** (gated).

---

## 10. PHASE 7 — Optional Forensic Prosecutor — **GATED**

> **GATE:** FuguPRD §1.10 + §21 Phase 7 — "Only after enough research-look history exists." The
> forensic prosecutor needs a populated `research_looks.jsonl` and discarded-variant trail to attack.

### (a) Goal + PRD refs
A **Forensic Prosecutor** that attacks the *genealogy* — sees research-look ledger, discarded variants,
prompt trail, and the (now-unsealed) bull case, and attacks the process (selection, look-then-test
contamination). **FuguPRD §5.11, §1.10, §21 Phase 7.**

### (b) Depends on
A meaningful history in `research_looks.jsonl` (Phase 1 ledger accumulating over time) + Phase 6.

### (c) Files to build (future)
- `scripts/discovery_triage/forensic_prosecutor.py` — reconstructs the claim's genealogy from
  `research_looks.jsonl` + `detector_drafts.jsonl` + (post-unseal) `SR_*.yaml`; emits a
  process-contamination report to `journal/prosecutions/forensic_prosecutions.jsonl`.

### (d) Key logic & decisions
- This is the **only** prosecutor allowed to see sealed rationale, and only **after** the blind ruling
  and unseal (FuguPRD §16.1 ordering preserved). It quantifies "what did we look at before we decided
  what to test" (FuguPRD §1.6) — counts looks-before-freeze, discarded sibling drafts in the same
  family, and selection across the §11.3 ledger.

### (e) Integration points
- Reads the look ledger as a time series; cross-references `family_trial_count` to detect undercounted
  selection (a forensic complement to the deflated-Sharpe denominator).

### (f) Tests (future)
- `test_forensic_prosecutor.py` — golden look-ledger fixture with N sibling drafts; assert the report
  counts the selection correctly and flags look-then-test contamination.

### (g) V1 acceptance: **none** (deferred). (h) Effort: **L** (gated).

---

## 11. PHASE 8 — Calibration / Kill Analytics — **GATED on forward data**

> **GATE:** FuguPRD §18.4 + §21 Phase 8 — "Only after enough forward outcomes exist. Do not pretend
> this calibration exists before data accumulates." The graveyard control arm must accumulate
> readouts (21d/63d/252d) first. With a 252-observation full-readout horizon, meaningful analytics
> are **>1 year** away from first claim freeze.

### (a) Goal + PRD refs
Measure the false-negative rate: did killed ideas outperform survivors? Which kill reasons were
predictive? Which probes were too aggressive? Which source families generated false excitement?
**FuguPRD §18 (graveyard control arm), §18.4, §21 Phase 8.**

### (b) Depends on
Phase 2 `route_claim` + `forward_track.py` accumulating `readout` records in
`prospective_readouts.jsonl` and `graveyard_forward_tracking.jsonl` over time.

### (c) Files to build (future)
- `scripts/discovery_triage/kill_calibration.py` — folds the readout streams; compares incubator vs
  graveyard arm forward relative returns by kill reason / probe / source family; emits a calibration
  report (markdown + optional xlsx). This is the point at which folding to `Data/loop/asado_loop.duckdb`
  (FuguPRD §20.3 tables `prospective_incubator`, `graveyard_forward_tracking`) becomes worthwhile.

### (d) Key logic & decisions
- **Direction applied only here (§18.4):** `forward_track.py` stores the **raw** `relative_return`
  (direction-agnostic, control arm stays clean); the sign from `claim.target.direction` is applied
  only in this analytics phase.
- **Arm comparison:** group readouts by `arm` (`incubator`/`graveyard`) and by `terminal_or_quarantine_status`
  kill reason; test whether killed claims systematically out/under-performed survivors at each horizon.
- **No verdicts until the data exists** (Invariant F / §18.4) — the report states sample sizes loudly
  and refuses conclusions on thin data.

### (e) Integration points
- First legitimate place to **fold journal → loop DB** (Invariant A relaxation, post-stabilization).

### (f) Tests (future)
- `test_kill_calibration.py` — synthetic readout streams with a known false-negative signal; assert the
  report recovers it and that it refuses conclusions below a minimum N.

### (g) V1 acceptance: **none** (deferred). (h) Effort: **M** (gated; analytics over accumulated JSONL).

---

## 12. Dependency / Sequencing Graph

```
                 (existing foundation: provenance.py, context_builder.py,
                  jsonl_store.py, paths.py, 4 configs, harness, ledgers, loopdb)
                                        │
                ┌───────────────────────┼──────────────────────────┐
                ▼                        ▼                          │
        PHASE 1 (denominator)    PHASE 2 (discipline)               │
        looks, schemas,          surface_loader, triage,            │
        provenance CLI,          blind packet/ruling, router,       │
        claim schema             HARNESS WIRE, forward_track         │
                │                        │                          │
                │   "discipline before Lab" (short PRD decision #3) │
                └────────────┬───────────┘                          │
                             ▼                                       │
                     PHASE 3 (Discovery Lab + real Claude + docket)  │
                             │                                       │
                             ▼                                       │
                     PHASE 4 (Analog Shelf) ──────────────┐         │
                             │                              │         │
                             ▼                              ▼         ▼
                     PHASE 5 (Cockpit: reads journal from 1–4) ──────┘
                             │
        ─────────────── GATED on usefulness / forward data ───────────────
                             ▼
                     PHASE 6 (Blind Prosecutor)   [gate: V1 useful + claims exist]
                             ▼
                     PHASE 7 (Forensic Prosecutor) [gate: look-ledger history]
                             ▼
                     PHASE 8 (Kill calibration)    [gate: ≥1yr forward readouts]
```

**The non-negotiable ordering** (short PRD design decision #3, FuguPRD §1.10): **Phase 2 (discipline)
must exist before Phase 3 (Lab) is enabled.** The denominator (Phase 1), the provenance classifier,
the minimal probes, the blind packet, and the router all exist before the daily docket runs. The Lab
firehose must not open before the drain is built. Phases 6–8 never start until Phases 1–5 are running
daily and forward data accumulates.

---

## 13. V1 Acceptance-Criteria Traceability Matrix (PRD §22, items 1–13)

| # | §22 criterion | Deliverable file(s) | Proving test | Phase |
|---|---|---|---|---|
| 1 | PRDs exist | `FuguPRD.md`, `PRD_ASADO_Discovery_Triage.md` | (present — no test required) | — |
| 2 | Config files exist | `config/{discovery_triage,claim_provenance_policy,analog_metric_registry,triage_probe_registry}.yaml` | (present, BUILT) | — |
| 3 | Journal dirs exist | `journal/{looks,drafts,claims,sealed_rationales,blind_rulings,prospective_queue,dockets,analog_sets,graveyard}/` | (present, BUILT) | — |
| 4 | Context builder rejects forbidden surfaces | `context_builder.py` (BUILT), `surface_loader.py` | `test_context_builder.py` | 2A |
| 5 | Provenance routes pre-cutoff LLM → prospective-only | `provenance.py` (BUILT), `classify_provenance.py`, `model_registry.yaml` | `test_provenance_classifier.py` | 1 (3 reinforces) |
| 6 | Provenance allows only post-cutoff tool-blind → holdout | `provenance.py` (BUILT), `classify_provenance.py` | `test_provenance_classifier.py` | 1 (3 reinforces) |
| 7 | Drafts require source looks | `make_detector_draft.py`, `record_look.py` | `test_record_look.py` (+ draft-link assert) | 1 (3 enforces live) |
| 8 | Claims require provenance + falsification fields | `freeze_claim.py` | `test_freeze_claim.py` | 1 (schema) / 2B (harness) |
| 9 | Blind packets exclude rationale + bull case | `build_blind_packet.py`, `freeze_claim.py` (SR_ split) | `test_blind_packet.py` | 2A |
| 10 | Blind rulings log post-unseal changes | `record_blind_ruling.py` | `test_route_claim.py` / ruling assert | 2A |
| 11 | Killed/quarantined → graveyard forward tracking | `route_claim.py`, `forward_track.py` | `test_graveyard_tracking.py` | 2A route / 2B track |
| 12 | Daily docket renders 3–10 unvalidated ideas w/ labels | `daily_docket.py`, `lab_session.py` | docket cap/label assert | 3 |
| 13 | Tests pass (context, provenance, freeze, blind, route, graveyard, analog) | all 8 §20.1 tests | the 8 named test files | 1–4 |

---

## 14. Discovery Lab LLM Wiring Detail (Real Model — DECISION 1)

### 14.1 Provisional Anthropic SDK wiring blueprint

The repo's existing call (`query_assistant.py::_call_anthropic`, raw HTTP) is the **wrong** thing to
copy if it still uses stale model IDs or unsupported sampling parameters. The Lab should use the current
official SDK shape verified at Phase-3 wiring time. The example below is **not authoritative** until the
Context7 / official-doc / installed-SDK gate passes:

```python
import anthropic, os
key = os.getenv("ANTHROPIC_API_KEY") or first_value("ANTHROPIC_API_KEY", ENV_TXT_PATH)
if not key:
    raise LabError("No ANTHROPIC_API_KEY")          # FAIL IS FAIL — never hardcode
client = anthropic.Anthropic(api_key=key)

resp = client.messages.parse(
    model=verified_model_id,
    max_tokens=16000,
    system=SYSTEM_PROMPT,                             # cache the stable prefix; volatile snapshot last
    thinking={"type": "adaptive"},                    # budget_tokens 400s
    output_config={"effort": "high"},                 # effort inside output_config
    output_format=DetectorFamilyDraft,                # one Pydantic model per object type
    messages=[{"role": "user", "content": user_prompt}],
)
if resp.stop_reason == "refusal":                     # mandatory: check before reading content
    raise LabRefusal(resp.stop_details)
obj = resp.parsed_output                              # validated instance
```

Potentially removed/forbidden params such as `temperature`, `top_p`, `top_k`, budgeted thinking, or
assistant prefill must be verified against current docs before use. JSON-schema limits must also be
re-checked. Run the **Context7 lookup** before writing this code (CLAUDE.md mandate), and update this
section if the current API differs.

### 14.2 `config/model_registry.yaml` and cutoff sourcing

`training_cutoff` may not be a Models-API field — fill it from the official model card or equivalent
provider documentation, never guess. Persist the evidence, not only the date: `model_id`,
`model_version`, `training_cutoff`, `training_cutoff_source`, `cutoff_retrieved_at`, `access_mode`, and
retention constraints. **Until `training_cutoff` is verified for a model, it stays null → every LLM idea
from that model routes to `prospective_only_unknown_cutoff`** (Invariant D). Confirm the chosen model id,
org access, structured-output support, and retention mode before making it the default.

### 14.3 `lab_session.py` data flow

1. Resolve key (env → first `.env.txt` entry → fail).
2. `build_context_manifest(ContextRequest(visibility_mode="outcome_blind", requested_surfaces=[8
   families], as_of_date, model_id, model_training_cutoff))` — raises before any model call if a
   forbidden surface leaks (Invariant E).
3. `surface_loader.load_country_snapshot(as_of)` — whitelist-gated PIT snapshot (the only data the
   model sees). No forward returns, no combiner, no factor returns, no verdicts.
4. Call the verified SDK structured-output method with the strict system prompt + Pydantic schema (one per object type),
   each requiring `falsification` + `mythos_self_falsification`.
5. Validate `resp.parsed_output`; regex-reject forbidden vocab (§24) and empty falsification blocks.
6. `append_jsonl(research_looks.jsonl, look)` FIRST (model id/version/cutoff, cutoff source, access mode,
   effort, manifest hash, `stop_reason`, usage, provider request id if available).
7. `append_jsonl(detector_drafts.jsonl, draft)` + per-object YAML (JSONL append under lock; per-object
   file temp→rename is allowed).
8. Tag each draft with `epistemic_status` + route from `classify_provenance` keyed on the registry
   cutoff.

### 14.4 Why current-cutoff models correctly route historical ideas to prospective-only

This is **the** epistemic guarantee (FuguPRD §1.4, §7), and it operates exactly as intended with
today's models:

- A current frontier model may have a `training_cutoff` that **precedes** any historical
  certification window the Lab might propose for a 2008–2025 backtest.
- `classify_provenance` therefore returns `prospective_only_training_cutoff_contamination` for the
  historical window (`start <= cutoff`), or `prospective_only_unknown_cutoff` if the cutoff is null.
- The **only** clean LLM path is a **forward window after the cutoff** with tool-enforced blindness →
  `post_cutoff_holdout_testable`.
- **Consequence:** the Lab's LLM ideas about history cannot be "validated" by in-sample backtest
  (`ordinary_in_sample_validation_for_llm: forbidden`). They incubate forward. This is not a
  limitation to work around — it is the system working. The Lab produces *discovery*; *certification*
  comes from forward evidence, post-cutoff holdout, or a genuinely older frozen model (FuguPRD §7.4).

---

## 15. Test Strategy & Fixtures

**Constraint:** all tests must run with **no network and no Bloomberg**, fast, deterministic.

- **Tiny synthetic loop-DB fixture.** A pytest fixture builds an in-memory / temp DuckDB seeded with
  minimal rows for the 8 allowed surfaces + a tiny `t2_factors_daily`-shaped `1DRet` slice so
  `daily_country_returns`-style logic and `surface_loader.load_country_snapshot` work over ~3–5 fake
  countries and ~300 dates. Monkeypatch `loop_connection` to return the fixture connection.
- **Monkeypatched LLM for `lab_session`.** Patch `anthropic.Anthropic` so `messages.parse` returns a
  canned valid object (and a separate case returning forbidden vocab / empty falsification to prove the
  validator rejects). No real API key, no spend, no flakiness.
- **Golden JSONL.** Commit small golden `research_looks.jsonl` / `detector_drafts.jsonl` /
  `claims.jsonl` / `prospective_queue.jsonl` / `graveyard_forward_tracking.jsonl` fixtures so reader
  and routing tests assert exact parse → dict shapes (including `provenance_class` badges for the cockpit).
- **Forbidden-surface negative tests.** Parametrize every forbidden surface
  (`forward_returns`, `harness_results`, `factor_returns_daily`, `hypothesis_ledger.verdict`,
  `combiner_scores_daily`, `graph_features_daily`, `country_returns_monthly`, `gap_holdout_daily.promoted`)
  and assert each raises (`ContextPolicyError` or `PermissionError`).
- **Idempotency tests.** Run `forward_track.py` twice over the fixture; assert the second run appends
  zero new readouts (key `(claim_id, horizon)`).
- **Harness-wire test isolation.** `test_freeze_claim.py` uses a temp `ledgers/` and a fixture loop DB;
  assert `family_trial_count` is unchanged on re-freeze and that `hypothesis_ledger.jsonl` carries no
  Court fields. Add the novel test variable prefix to a **fixture** `family_registry.yaml` copy, not
  the real one, where possible.

Run command: `./venv/bin/python -m pytest tests/discovery_triage/ -q`.

---

## 16. Implementation Risks & Mitigations (implementation-specific)

| Risk | Mitigation |
|---|---|
| **`append_jsonl` is not lock-protected** — a crash or concurrent writer can corrupt an append-only ledger or duplicate IDs. | **Fixed in PR-1 / Phase 1:** `fcntl.flock` around read/mint/validate/append/fsync; temp-file + `os.replace` is allowed for per-object files, not for append-only JSONL ledgers. |
| **`now_iso()` is tz-naive** but FuguPRD §11.3 examples carry `-07:00`. | **Fixed in PR-1 / Phase 1 (Codex review):** `now_iso()` made timezone-aware (local offset) so timestamps round-trip and sort correctly across the ledgers. |
| **A malformed object silently corrupts a ledger** (wrong/missing keys, type drift). | **PR-1 (Codex review):** `schemas.py` Pydantic models validate every object before `append_jsonl`/`write_json`; `test_schemas.py` covers accept-valid / reject-malformed. |
| **`combiner_scores_daily` looks allowed** (strong signal, listed in passing) but is an outcome surface. | Hard-exclude in `surface_loader.ALLOWED_SURFACES`; negative test; never add it to any `allowed_surfaces` YAML block. |
| **`country_returns_daily` is a logical name** — naive `SELECT FROM country_returns_daily` fails silently/loudly. | `forward_track.py` resolves via `RETURN_SURFACE_RESOLVERS` (whitelist) → `daily_country_returns(con)`; raises on any other name. |
| **`register_hypothesis` raises `UnclassifiedVariableError`** for a novel signal prefix → freeze fails unexpectedly. | `freeze_claim` checks `resolve_family` up front and fails loudly with the instruction to add the prefix to `family_registry.yaml` (a deliberate git-tracked trust-root edit). |
| **Double-charging the deflated-Sharpe family** on re-freeze. | Reuse `find_existing(family, spec_hash)` (same hash recipe) before `register_hypothesis`; cached verdict path. Test asserts `family_trial_count` unchanged. |
| **Court state accidentally written to `Data/asado.duckdb`** (wiped on rebuild) — silent data loss. | INVARIANT A: all writes via `jsonl_store` under `journal/`; surface loader opens loop DB read-only; no `CREATE TABLE` in V1. |
| **Nightly step failure reds the governance scorecard** while the JSONL workflow is teething. | Mark `discovery_forward_track`, `discovery_daily_docket`, `build_cockpit_data` `optional: true` in `config/governance_contract.yaml`; exit 2 (PARTIAL) for soft conditions (unmatured readouts), non-zero only on real faults. |
| **LLM emits validation language** ("works", "Sharpe", "trade") despite the prompt. | Code-level regex gate on `resp.parsed_output` against FuguPRD §24 forbidden vocab; reject + retry; Pydantic requires non-empty falsification blocks. |
| **Model `training_cutoff` guessed/fabricated** → false `post_cutoff_holdout_testable`. | `model_registry.yaml` cutoffs default null (→ `prospective_only_unknown_cutoff`); cutoff filled only from the official model card, never the Models API. |
| **Visibility-mode alias bypass** (`tool_outcome_blind` vs `outcome_blind`) lets a PRD-compliant caller skip outcome-blind checks. | PR-1 canonicalizes visibility modes before context/provenance logic; tests cover `tool_outcome_blind` and `tool-outcome-blind` aliases. |
| **Descriptive historical harness stats launder prospective-only LLM ideas into blind rulings.** | `build_blind_packet.py` includes historical harness stats only for `post_cutoff_holdout_testable`, `pit_preregistered`, or deterministic/harness-clean routes; prospective-only packets exclude IC/Sharpe/verdict fields. |
| **Forward tracking silently assumes one measurement shape.** | Claim schema requires `target.measurement_shape`; `forward_track.py` dispatches by shape and tests each supported shape. |
| **Statistical claim ignores ETF implementation quality.** | Claim schema requires an `expression` block freezing ETF/proxy, liquidity, cost/drag, basis/tracking, and crowding/flow context before ruling. |
| **Cockpit panels fabricate data** before writers exist. | Readers return `[]` empty-state when JSONL absent; explicit "no entries yet" render; never synthesize rows. |
| **`as_of` blindness mistaken for clean** (tool-blind ≠ epistemically clean). | Manifest labels `tool_enforced_outcome_blind`, not `clean`; certification still gates on cutoff (Invariant D). |

---

## 17. Definition of Done Per Phase + Suggested First PR Slice

### Definition of done (per phase)
- **Phase 1:** `schemas.py` (Pydantic, all objects) + hardened `jsonl_store` (lock-protected append/ID
  minting + tz-aware timestamps) +
  `record_look`, `classify_provenance`, `make_detector_draft`, `freeze_claim` (schema + cutoff gate +
  language gate + `measurement_shape` + `expression`), visibility-mode alias normalization,
  `model_registry.yaml` stub exist; `test_provenance_classifier.py` + `test_record_look.py`
  + `test_schemas.py` + partial `test_freeze_claim.py` (incl. cutoff/language gates) pass; §22 #5/#6/#7 +
  partial #8 demonstrably met.
- **Phase 2A:** `surface_loader` (table + column allowlist), `run_triage_probes`, `build_blind_packet`
  (route-aware harness-stat filtering),
  `record_blind_ruling`, `route_claim` exist; `test_context_builder` / `test_blind_packet` /
  `test_route_claim` pass; §22 #4/#9/#10/#11 met. Fully offline (no harness, no realized returns).
- **Phase 2B:** `freeze_claim` calls the harness and writes the overlay; `forward_track` exists and is
  wired into the nightly loop; `test_freeze_claim` (full) + `test_graveyard_tracking` pass; §22 #8 met;
  harness wire proven (overlay keyed to `hypothesis_id`, ledger untouched, no double-charge).
- **Phase 3:** Context7/SDK hard-gate passed; `lab_session` calls a verified current model behind the
  outcome-blind context with structured output; `daily_docket` renders 3–10 labeled cards;
  `model_registry.yaml` cutoffs filled-or-null with source evidence; monkeypatched `test_lab_session.py`
  passes; §22 #12 met. `analog_mismatch` is disabled or placeholder-only until Phase 4 retrieval exists.
- **Phase 4:** `retrieve_analogs` + `attach_analog_outcomes` exist; `test_analog_outcome_blindness.py`
  passes; §22 #13's analog test met; membership immutable, no trade promotion.
- **Phase 5:** 6 cockpit readers + `research_desk` payload block + 7 panels (light mode) + nightly hook;
  empty-state when journals empty; `test_cockpit_readers.py` passes. (Per the Codex review, the empty-state
  shell may ship right after Phase 2; live content arrives as Phases 3–4 land.)
- **Phases 6–8:** **not done in V1** — gated; revisited when their gate opens.
- **Whole V1 (Phases 1–5):** all 8 §20.1 tests green
  (`./venv/bin/python -m pytest tests/discovery_triage/ -q`); §22 items 1–13 satisfied; no Court state
  in `Data/asado.duckdb`; the nightly loop runs the new optional steps without redding governance.

### Suggested first PR slice (smallest shippable, highest-leverage)
**PR-1: "Provenance + Look Ledger + Claim Schema" (Phase 1 core).**
- Add: `schemas.py` (Pydantic, all objects), hardened `jsonl_store.py` (lock-protected append/ID minting +
  tz-aware timestamps),
  `record_look.py`, `classify_provenance.py`, `make_detector_draft.py`, `freeze_claim.py`
  (schema-only + cutoff gate + language gate + `measurement_shape` + `expression`, no harness yet),
  visibility-mode alias normalization, `config/model_registry.yaml`
  (stub, null cutoffs). Also `git add` the existing **untracked** foundation (the 4 configs, the 4 built
  modules, the `journal/` dirs) so PR-1 brings the working-tree artifacts under version control
  (per Codex's repo-reality note).
- Tests: `test_provenance_classifier.py`, `test_record_look.py`, `test_schemas.py`,
  partial `test_freeze_claim.py` (incl. cutoff + language gates).
- Why first: it stands on the already-built foundation (only `pydantic` added), produces the first real
  JSONL records (`research_looks.jsonl`) on a lock-protected writer, and proves the Invariant-D routing
  end-to-end with the model registry — the spine everything else hangs off. No network, no LLM, no DB
  writes. Branch off `main` (do not commit to `main` directly per repo policy); commit only when the user asks.

**PR-2A: "Outcome-blind discipline" (Phase 2A)** — `surface_loader` (table + column allowlist) + triage
probes + power band + route-aware blind packet + blind ruling + router; fully offline tests. **PR-2B: "Harness wire +
forward tracking" (Phase 2B)** — the single missing wire (`freeze_claim` → `register_hypothesis` →
`evaluate_signal`) + shape-aware `forward_track` + nightly hook. **PR-3 (after 2A):** empty-state Research Desk cockpit
shell (let the front-end settle early). **PR-4:** Discovery Lab (real Claude, *after* the Context7 hard-gate)
+ docket. **PR-5:** Analog Shelf. **PR-6:** fill the cockpit panels with live content.

---

### Output links

- Plan: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/IMPLEMENTATION_PLAN.md`
  ([file://](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/IMPLEMENTATION_PLAN.md))
