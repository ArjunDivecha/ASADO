---
type: "Reference"
title: "Discovery Triage"
description: "ASADO's quarantined LLM-native Discovery Lab and chain-of-custody Court: outcome-blind snapshots, model-cutoff provenance classification, blind human rulings, the prospective incubator, and the graveyard control arm. JSONL/YAML-first, no DuckDB tables."
tags: [discovery-triage, llm, provenance, pit, custody, forward-tracking]
openwiki:
  roles: [architecture, domain, workflow, testing]
  change_kinds: [lifecycle, public-api]
  source_paths:
    - scripts/discovery_triage/
    - config/discovery_triage.yaml
    - config/claim_provenance_policy.yaml
    - config/triage_probe_registry.yaml
    - config/analog_metric_registry.yaml
    - config/model_registry.yaml
    - scripts/loop/loop_daily_job.py
    - cos_mockups/build_cockpit_data.py
  symbols:
    - classify_provenance
    - freeze_claim
    - build_blind_packet
    - record_blind_ruling
    - route_claim
    - forward_track
    - run_triage_probes
    - read_research_desk
  test_paths:
    - tests/discovery_triage/
  invariants:
    - Discovery emits drafts, never validated alpha.
    - Model training cutoff is the true PIT boundary for LLM ideas; null/unknown cutoff routes prospective_only_unknown_cutoff.
    - The Lab is outcome-blind by code-level surface enforcement, not by prompt.
    - Court records are append-only under fcntl.flock; no DuckDB writes.
    - Blind ruling is recorded before the bull case is unsealed.
    - The graveyard is a control arm: killed/quarantined claims are forward-tracked when measurable.
  validation_commands:
    - "python -m pytest tests/discovery_triage -q"
---

# Discovery Triage

ASADO's deterministic detectors (the Known Gap Monitor inside the loop) only watch relationships we already know to ask about. Discovery Triage is the quarantine system that lets a Mythos-class LLM *discover* strange nonlinear relationships without laundering retrospective LLM stories into validated alpha. The design makes **Discovery** the product and **Disbelief** the chain of custody.

Canonical intent lives in `PRD_ASADO_Discovery_Triage.md`, `FuguPRD.md`, and `PRD_DISCOVERY_TRIAGE_MERGE_CONSOLIDATION.md`. The red-team report `docs/REDTEAM_DISCOVERY_TRIAGE_2026_06_26.md` records the adversarial audit that drove several of the invariants below.

## What it is

A two-track custody pipeline that sits after the loop's deterministic detectors and before the cockpit refresh:

1. **Discovery Lab** — a quarantined Claude session is given a tool-enforced, outcome-blind snapshot of ASADO's state and asked to emit *drafts only* (cross-surface contradictions, graph motifs, analog mismatches, regime sign flips, nonlinear condition drafts). Every draft carries falsification and self-falsification blocks.
2. **Court** — drafts become attackable frozen claims, are triaged, judged blind by a human, routed by provenance, and forward-tracked. Survivors go to the Prospective Incubator; killed/quarantined claims go to the Graveyard Control Arm.

It is JSONL/YAML-first under `journal/` and writes **no DuckDB tables** (a deliberate V1 deferral). It never produces a trade recommendation.

## Custody chain

<!-- openwiki: mermaid parse failed and this diagram was converted to a text fence so it does not break rendering. Fix the diagram source and restore the mermaid fence. Parser error: Heuristic: an unescaped angle bracket inside a label breaks rendering; rephrase the label. -->
```text
flowchart TD
    A[Known Gap Monitor<br/>loop detectors] --> B[Research Look Ledger<br/>record_look]
    B --> C[Discovery Lab<br/>lab_session]
    C -->|drafts only| D[Detector Drafts<br/>make_detector_draft]
    D --> E[Provenance Classifier<br/>classify_provenance]
    E --> F[Claim Freezer<br/>freeze_claim]
    F --> G[Triage Battery<br/>run_triage_probes]
    G --> H[Blind Packet<br/>build_blind_packet]
    H --> I[Blind Human Ruling<br/>record_blind_ruling]
    I -->|after unseal| J[Router<br/>route_claim]
    J -->|survivor/quarantined| K[Prospective Incubator]
    J -->|killed/rejected| L[Graveyard Control Arm]
    K --> M[Forward Track<br/>forward_track]
    L --> M
```

The Lab never sees forward returns, harness verdicts, PnL, the combiner, factor returns, top-20 membership, or attribution surfaces. The snapshot is built from a **code-level allowlist**, not a prompt.

## Key subsystems

All under `scripts/discovery_triage/`:

- **`provenance.py`** — the 11-branch provenance classifier. Routes a claim by generator type, visibility mode, and the model's *training cutoff* (the real PIT boundary for LLM ideas). A null/unknown cutoff forces `prospective_only_unknown_cutoff`; pre-cutoff or retrospective LLM ideas can never be historically certified. `classify_provenance.py` is the thin CLI wrapper that adds `config/model_registry.yaml` lookup.
- **`surface_loader.py`** — code-level outcome-blindness enforcement at the data-access layer (Invariant E). Two tiers: a table allowlist (`ALLOWED_SURFACES`, 8 families) and a JSON-content sanitizer that scrubs forbidden keys (e.g. `combiner_scores_daily`) out of allowlisted blob columns like `price_state_daily.source_freshness_json`. Default-deny.
- **`context_builder.py`** — builds the per-search outcome-blind context from `config/discovery_triage.yaml::discovery_searches[].allowed_surfaces`; rejects forbidden surfaces.
- **`lab_session.py`** — the quarantined Discovery Lab. Records a Research Look *before* drafts, enforces the strict canonical draft schema (falsification + self-falsification), applies a language gate (no validation vocabulary), and tags each draft with its certification route. The Anthropic client and snapshot are injectable for offline tests. Reads `ASADO_ANTHROPIC_KEY`/`ANTHROPIC_API_KEY`.
- **`record_look.py`** — appends a Research Look (`L_YYYYMMDD_NNN`) to the look ledger; no draft without a look.
- **`make_detector_draft.py`** — writes a `detector_family_draft` to the drafts ledger + per-object YAML, enforcing the source-look linkage and the mandatory falsification blocks.
- **`freeze_claim.py`** — converts a draft into an attackable frozen claim. Re-runs the provenance classifier itself (never trusts a caller-supplied route), stamps the computed route, and rejects a freeze that claims historical certification while the computed route is prospective-only (anti-laundering gate, Invariant D). The bull case / generator rationale goes to a separate sealed file; only its id enters the claim.
- **`run_triage_probes.py`** — the minimal triage battery (FuguPRD §15). Probe 1 `target_reentry` is FATAL: a pure, no-DB check that a claim's signal never touches forward returns / optimizer outputs / factor returns / attribution / forward-return variables. Probes 2–3 (`leave_one_crisis_out`, `country_region_jackknife`) flag concentration. A power-budget BAND is attached, never a verdict.
- **`build_blind_packet.py`** — assembles the blind packet a human judge rules on *before* the bull case is unsealed, from a strict whitelist; forbidden inputs (generator rationale, bull case, excitement score, trade recommendation, discovery transcript) can never appear.
- **`record_blind_ruling.py`** — records the blind ruling protocol by *order*: `record_blind_ruling` writes the preliminary ruling (`unseal` null), then `record_unseal` appends a second event recording the post-unseal decision and `ruling_changed_after_unseal`. One unseal per ruling.
- **`route_claim.py`** — routes every frozen claim to forward tracking. Survivors / quarantined / prospective-only / holdout-testable → Incubator; killed / rejected → Graveyard (control arm). Entry records carry `measurement_shape` + `direction` so `forward_track` can score without re-reading the claim.
- **`forward_track.py`** — the readout engine. For each matured (claim, horizon) on the incubator/graveyard rosters, appends a `readout` with the forward relative return. Idempotent per `(claim_id, horizon_days, measurement_shape)`. Reads returns only through a whitelist (`RETURN_SURFACES`); never an optimizer surface. Attaches the main warehouse as `asado` so `asado.t2_factors_daily` resolves.
- **`harness_bridge.py`** — the single boundary between a frozen claim and ASADO's existing signal harness: dedup by `(family_key, spec_hash)`, register only if new, evaluate, return an overlay. Never writes Court fields into the ledger.
- **`retrieve_analogs.py`** / **`attach_analog_outcomes.py`** — the Fixed-Metric Analog Shelf (FuguPRD §13). Outcome-blind retrieval freezes a K-nearest-neighbor set; membership is immutable. Outcomes are attached *after* freezing and never change membership; differencing may explain a frozen set only along allowed axes.
- **`schemas.py`** — Pydantic v2 models for every journal object; every JSONL/YAML writer validates before the write.
- **`jsonl_store.py`** — concurrency-safe append-only JSONL persistence. ID minting and the append happen inside one `fcntl.flock`-guarded critical section (no temp-file + replace, no duplicate IDs, no torn lines).
- **`paths.py`** — `ASADO_DATA_ROOT` override for worktree/main resolution; journal dir is `<repo>/journal`.
- **`daily_docket.py`** — the Daily Discovery Docket (FuguPRD §9.3). Runs one or more outcome-blind searches and renders one markdown artifact (`journal/dockets/discovery_docket_YYYY_MM_DD.md`) with 3–10 unvalidated draft cards, each tagged with its epistemic status + certification route. Dedupes/ranks/caps; never pads to the minimum; reports raw vs shown counts.

## Configuration

The custody rules are config-driven so the code stays generic:

- `config/discovery_triage.yaml` — principles, status ladder, LLM certification policy, forbidden context surfaces, the five `discovery_searches` with per-search `allowed_surfaces`, and daily docket limits.
- `config/claim_provenance_policy.yaml` — provenance classes → certification routes, legacy tiers, and blind-ruling allowed/forbidden inputs.
- `config/triage_probe_registry.yaml` — the V1 required probes (`target_reentry` fatal; `leave_one_crisis_out`, `country_region_jackknife` warnings) and conditional probes; `graveyard_tracking` flags.
- `config/analog_metric_registry.yaml` — registered analog metrics (macro-state, price-state, stress-state, graph-state, mixed-state), each `outcome_blind: true` with feature blocks, distance, and lookback.
- `config/model_registry.yaml` — maps `model_id` → `training_cutoff` (sourced from official model cards, never guessed). While `claude-opus-4-8.training_cutoff` is null, every historical LLM idea routes `prospective_only_unknown_cutoff`.

## Journal storage

All durable Court records are append-only JSONL/YAML under `journal/`:

- `journal/looks/` — research looks
- `journal/drafts/` — detector drafts
- `journal/claims/` — frozen claims + per-object YAML
- `journal/sealed_rationales/` — sealed bull cases / generator rationales
- `journal/blind_rulings/` — blind rulings + unseals
- `journal/prospective_queue/` — incubator entry records
- `journal/graveyard/` — graveyard entry records + forward tracking
- `journal/analog_sets/` — frozen analog sets
- `journal/dockets/` — daily discovery dockets

## Nightly wiring and cost gate

`scripts/loop/loop_daily_job.py` chains two Discovery Triage steps after `build_country_returns` and before the cockpit refresh:

1. `discovery_forward_track` — `python -m scripts.discovery_triage.forward_track` (append readouts; optional no-op until claims are routed).
2. `discovery_docket` — `python -m scripts.discovery_triage.daily_docket --nightly`.

The docket is a **cost gate**: `daily_docket.py` no-ops unless `ASADO_RUN_DISCOVERY_LAB=1`, so the nightly job never auto-spends on the Anthropic API. A manual run (without `--nightly`) always proceeds. Both steps run as modules (`-m`) because the package uses relative imports.

## Cockpit surface

`cos_mockups/build_cockpit_data.py::read_research_desk()` surfaces the Court in the cockpit's `research_desk` block: `discovery_lab`, `analog_shelf`, `under_triage`, `blind_rulings`, `prospective`, and `graveyard`. It reads the JSONL ledgers via `scripts.discovery_triage.jsonl_store.read_jsonl` and returns `[]` (never fabricates) when a ledger is absent, so the cockpit degrades cleanly. The cockpit refresh runs *after* the docket so the front end reflects the latest drafts. See [Frontend and cockpit](frontend-and-cockpit.md).

## What to watch out for

- **Outcome-blindness is code-enforced, not prompt-enforced.** The red-team report found a historical leak where the live `COMBINER_RIDGE_DAILY_V1` score (a Ridge fit on forward returns) was smuggled through `price_state_daily.source_freshness_json` because the column gate inspected names, not JSON contents. `surface_loader.py` now sanitizes the blob contents; `tests/discovery_triage/test_surface_loader_sanitize.py` is the canary. When extending the snapshot, allowlist at the table *and* JSON-content tier.
- **Do not trust a caller-supplied certification route.** `freeze_claim.py` re-runs the provenance classifier and rejects historical-certification claims that compute as prospective-only. The red-team found `provenance.py` could short-circuit on caller-trusted `generator_type='harness'`/`visibility_mode='pit_preregistered'` before the LLM-cutoff branch; verify the honest LLM path stays the default if you touch the classifier.
- **Strict falsification must survive non-Lab writers.** The red-team noted the non-empty falsification guarantee lived only in `lab_session.validate_card`, not the Pydantic schema, so a non-Lab writer could persist degenerate claims. Keep the schema-level gate strong.
- **The graveyard is a control arm, not a trash bin.** Killed and quarantined claims are forward-tracked when mechanically measurable so ASADO can learn whether skepticism is helping or starving the book.
- **No DuckDB tables in V1.** Persist to `journal/` JSONL/YAML only; the JSONL workflow must prove stable before any DB tables are added.
- **The nightly docket never spends by default.** Setting `ASADO_RUN_DISCOVERY_LAB=1` opts into live Anthropic API runs.

## Source references

- `scripts/discovery_triage/` — all subsystem modules above.
- `scripts/loop/loop_daily_job.py` — nightly wiring of `discovery_forward_track` and `discovery_docket`.
- `cos_mockups/build_cockpit_data.py` — `read_research_desk` and `read_analog_shelf` cockpit readers.
- `config/discovery_triage.yaml`, `config/claim_provenance_policy.yaml`, `config/triage_probe_registry.yaml`, `config/analog_metric_registry.yaml`, `config/model_registry.yaml`.
- `PRD_ASADO_Discovery_Triage.md`, `FuguPRD.md`, `PRD_DISCOVERY_TRIAGE_MERGE_CONSOLIDATION.md` — canonical intent.
- `docs/REDTEAM_DISCOVERY_TRIAGE_2026_06_26.md` — adversarial audit and invariant scorecard.
- `DISCOVERY_TRIAGE_MERGE_ANALYSIS.md` — merge consolidation analysis.

## Focused tests

The offline suite (`tests/discovery_triage/`, 18 files) uses injected/fake clients and in-memory DuckDB so it runs with no API spend and no real DB:

- `test_provenance_classifier.py` — §7 routing, alias normalization, fail-safe on unknown modes.
- `test_freeze_claim.py` — cutoff gate (Invariant D, no laundering), language gate, sealed-rationale separation.
- `test_surface_loader_sanitize.py` — JSON-content sanitizer canary (C1): the combiner-score leak is scrubbed while legitimate descriptors survive.
- `test_context_builder.py` — context rejects forbidden surfaces and the column-level return leak.
- `test_lab_session.py` — look-before-draft, source-look linkage, strict canonical schema, prospective routing.
- `test_triage.py` — triage battery: target-reentry (FATAL), power band, warnings.
- `test_blind_packet.py` / `test_blind_ruling.py` — §16 exclusions, route-aware harness stats, enforced blind orchestrator, one-unseal-per-ruling.
- `test_route_claim.py` / `test_graveyard_tracking.py` — router and forward-track readouts, idempotency, return-surface whitelist.
- `test_analog_outcome_blindness.py` — outcome-blind retrieval, frozen membership, post-freeze outcome attachment, constrained differencing.
- `test_harness_bridge.py` — dedup, no double-charge, never writes Court fields into the ledger.
- `test_schemas.py` — Pydantic models + jsonl_store hardening (lock-protected append, no duplicate IDs).
- `test_daily_docket.py` — dedupe/rank/cap, raw-vs-shown accounting, no-padding, nightly cost gate.
- `test_cockpit_readers.py` — Research Desk empty-state (no fabrication) and rich card content survival.
- `test_paths.py` — `ASADO_DATA_ROOT` worktree/main resolution.

Minimal validation:

```bash
python -m pytest tests/discovery_triage -q
```

## Where to go next

- [Architecture overview](architecture.md)
- [Loop and research workflows](loop-and-research.md)
- [Frontend and cockpit](frontend-and-cockpit.md)
- [Operations and runbooks](operations.md)
