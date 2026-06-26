# Discovery Triage — `claude-kahuna` vs `codex-kahuna`: differences & merge plan

**Date:** 2026-06-25
**Author:** Claude Code (analysis of both worktrees)
**Purpose:** Two agents (Claude + Codex) independently built the ASADO Discovery Triage
system from the same PRD, on two branches. This document details where they differ and
recommends how to consolidate into one canonical branch.

> Both branches are pushed to `origin`. Generated cockpit data (`cockpit_data.json/.js`)
> and the `journal/` runtime ledgers are NOT version-controlled; they regenerate at deploy.

---

## 0. TL;DR

- These are **two independent implementations**, not a shared codebase. All 20 same-named
  modules differ substantially — a literal `git merge` conflicts on **every file**.
- They **interoperate at the journal/data contract** (draft fields, ledger layout, the
  cockpit `research_desk` payload). That seam is real and proven: Claude's live drafts
  render unchanged in Codex's cockpit.
- **Recommendation:** make **`claude-kahuna` canonical** (fuller governance machine, more
  tests, and Codex's operational fixes + cockpit already ported in), then **port four
  specific things from `codex-kahuna`**: the stricter lab schema, the `harness_bridge` /
  `model_registry` / `exceptions` module split, and the `ASADO_DATA_ROOT` warehouse-root
  handling. Estimated effort: ~half a day.

---

## 1. The core reality: independent implementations

Per-file divergence on the 20 shared modules (diff lines; 0 = identical):

| Module | diff lines | Module | diff lines |
|---|---|---|---|
| `lab_session.py` | 525 | `run_triage_probes.py` | 222 |
| `freeze_claim.py` | 359 | `provenance.py` | 215 |
| `retrieve_analogs.py` | 342 | `record_look.py` | 152 |
| `schemas.py` | 330 | `route_claim.py` | 145 |
| `forward_track.py` | 288 | `make_detector_draft.py` | 118 |
| `surface_loader.py` | 259 | `classify_provenance.py` | 111 |
| `attach_analog_outcomes.py` | 247 | `build_blind_packet.py` | 103 |
| `jsonl_store.py` | 244 | `record_blind_ruling.py` | 102 |
| `daily_docket.py` | 233 | `context_builder.py` | 94 |

Nothing is line-compatible. **Consolidation = pick one canonical branch + port the other's
best parts**, not a three-way merge.

Backend size: claude ≈ 2,793 LOC / 13 test files / 65 tests · codex ≈ 2,551 LOC / 16 test files.

---

## 2. The interop seam (what makes a port feasible)

Both write the **same journal contract**, which is why cross-branch rendering works:

- `journal/drafts/detector_drafts.jsonl` with `draft_id`, `family_name`, `members`,
  `certification_route`, `epistemic_status`, `falsification`, `mythos_self_falsification`,
  `recorded_ts`.
- The cockpit `payload.research_desk` shape (6 panels: discovery_lab, analog_shelf,
  under_triage, blind_rulings, prospective, graveyard) with epistemic `badge`s.

Keep this contract stable and either branch's UI/readers consume the other's data.

---

## 3. Where they differ (by area)

### 3.1 Lab output schema — *the most important difference*
- **Codex (stricter):** one tool `emit_detector_family_draft` per call. Schema **requires**
  `members[]`, and `falsification.{fatal_if, must_check}` (both non-empty), plus
  `mythos_self_falsification.{strongest_counterargument, what_would_change_my_mind}`. It
  hard-rejects empty falsification lists and validation language.
- **Claude (broader):** one tool `emit_discovery_cards` emitting **1–6 cards across 5 search
  types** (contradiction / graph motif / analog mismatch / regime sign-flip / nonlinear).
  Each card has `summary` + `falsification.near_term` + a 4-field self-falsification block.
  Softer: drops cards missing a falsification block rather than hard-failing.
- **Verdict:** Codex's strictness (force `fatal_if`/`must_check`) is better discipline;
  Claude's breadth (5 searches, multi-object-type) is more of the original PRD's §9.2.
  **Best of both:** keep Claude's 5-search breadth, tighten its schema to Codex's required
  `fatal_if`/`must_check`.

### 3.2 Harness bridge
- **Codex:** dedicated `harness_bridge.py` — `run_harness_bridge(claim)`, `_pre_harness_gate`,
  `_harness_direction`; charges `family_trial_count`.
- **Claude:** folded into `freeze_claim._harness_bridge`, with **injectable hooks** so the
  wire is unit-tested offline.
- **Verdict:** Codex's separation is cleaner; Claude's injectability is better for testing.
  Adopt Codex's module boundary but keep Claude's injectable hooks.

### 3.3 Model registry
- **Codex:** `model_registry.py` (`load_model_registry`, `model_metadata`).
- **Claude:** reads `config/model_registry.yaml` directly in `classify_provenance`.
- Both read the same YAML; Codex's wrapper is tidier. Low-stakes; adopt Codex's wrapper.

### 3.4 Schema strictness
- **Codex:** `StrictRecord` (extra forbidden) vs `FlexibleRecord`; `DetectorDraftRecord.members`
  required. Catches drift hard.
- **Claude:** all models `extra="allow"` (forward-compatible) on one `_Base`.
- **Verdict:** Codex's strict/flexible split is the better default for ledger integrity;
  Claude's `extra="allow"` is friendlier to schema evolution. Adopt a strict base for the
  written-once records (look/claim/draft), keep flexible for cockpit-facing reads.

### 3.5 Warehouse-root handling
- **Codex:** `ASADO_DATA_ROOT` env → loop DB path (works across checkouts/worktrees).
- **Claude:** default loop-DB path + `--loop-db` override on the docket.
- **Verdict:** Codex's `ASADO_DATA_ROOT` is the right primitive (already in the adopted
  `build_cockpit_data.py`). Standardize on it everywhere.

### 3.6 Cockpit Research Desk
- **Now identical** — `claude-kahuna` adopted Codex's `cockpit.html` desk panels +
  `make_live_cockpit` adapter + rich readers (Playwright-verified rendering live drafts).

### 3.7 Tests
- **Claude:** 13 files / 65 tests (incl. cockpit readers, daily docket curation, lab session).
- **Codex:** 16 files (incl. `test_harness_bridge`, `test_triage_probes`, `test_blind_ruling`,
  a shared `fixtures.py`). Worth porting the harness-bridge + fixtures.

---

## 4. Strengths of each (from both agents' work + Codex's own review)

**`claude-kahuna` strengths**
- Fuller governance machine: provenance spine, lock-protected JSONL custody, outcome-blind
  surface allowlist (table + column denylist + explicit `price_state_daily` protection),
  blind packet/ruling, analog shelf, forward tracking, 5-search docket.
- More end-to-end tests (65), all offline.
- Codex's operational fixes + cockpit already merged in (nightly `-m` invocation, cost guard,
  key-loading order, rich cockpit readers).

**`codex-kahuna` strengths**
- Stricter, single-purpose lab schema (forces `fatal_if`/`must_check`).
- Cleaner module factoring (`exceptions.py`, `harness_bridge.py`, `model_registry.py`).
- `ASADO_DATA_ROOT` warehouse-root handling.
- `test_harness_bridge` + shared `fixtures.py`.

---

## 5. Merge options

**Option A — `claude-kahuna` canonical (recommended).**
It is the more complete single branch and already contains Codex's fixes + cockpit.
Port FROM codex: (1) strict lab schema requirements, (2) `harness_bridge`/`model_registry`/
`exceptions` module split, (3) `ASADO_DATA_ROOT` everywhere, (4) `test_harness_bridge` +
`fixtures.py`. ~½ day. Risk: low (additive ports; tests guard regressions).

**Option B — `codex-kahuna` canonical (Codex's recommendation).**
Port FROM claude: surface_loader column-denylist depth, analog shelf, the 5-search docket
breadth, the broader test suite, the injectable harness hooks. ~1 day (more to move).

**Option C — keep both, freeze one.**
Not recommended: doubles maintenance; the journal contract already lets one UI serve either,
so there's no interop reason to keep two backends.

---

## 6. Recommended plan (Option A, concrete)

1. **Freeze the journal contract** (§2) as the interop spec — write it into
   `IMPLEMENTATION_PLAN.md` so neither side breaks it.
2. **Tighten the lab schema** in `claude-kahuna/lab_session.py`: make `falsification.fatal_if`
   and `falsification.must_check` required and non-empty (Codex's discipline), while keeping
   the 5-search loop and multi-card emission.
3. **Refactor the harness wire** out of `freeze_claim` into `harness_bridge.py` (Codex's
   boundary), keeping Claude's injectable hooks for offline tests.
4. **Add `model_registry.py`** (thin wrapper over the YAML) and route `classify_provenance`
   through it.
5. **Add `exceptions.py`** and replace inline exception classes.
6. **Standardize on `ASADO_DATA_ROOT`** in `lab_session` / `daily_docket` / `forward_track`
   (drop the hardcoded loop-DB default).
7. **Port `test_harness_bridge.py` + `fixtures.py`** from codex; keep all 65 existing tests
   green.
8. Re-run the full suite + one live docket; confirm the cockpit still renders.

After this, retire `codex-kahuna` (its best parts are absorbed) and continue on
`claude-kahuna` as the single line.

---

## 7. Open question for the owner

The only genuine judgment call is **breadth vs strictness** in the Lab:
- Claude's 5-search, multi-object-type sweep surfaces more (and more varied) ideas per morning.
- Codex's single strict detector-family draft is more disciplined but narrower.

Recommendation: **keep the breadth, adopt the strictness** (step 2 above). But if you want a
tight, low-noise morning docket over a wide net, Codex's single-draft strictness is the
safer default — your call.
