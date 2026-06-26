# PRD: Discovery Triage Merge Consolidation

Status: Ready for implementation  
Owner: ASADO / Arjun  
Prepared for: Claude Code implementation on `claude-kahuna`  
Date: 2026-06-25  

## 1. Purpose

Consolidate the two independent Discovery Triage implementations into one canonical ASADO branch.

The merged system must answer the original ASADO question:

> What does the data know that price has not yet figured out?

It should do this by running a broad, outcome-blind LLM Discovery Lab over ASADO's formidable state database, then forcing every candidate idea through strict custody, falsification, and prospective-certification rules before anything can influence a signal, thesis, or trade workflow.

## 2. Decision

Use `claude-kahuna` as the canonical backend base, then port the best strictness and operational pieces from `codex-kahuna`.

Rationale:

- `claude-kahuna` has the fuller governance machine: provenance, blind packets, analog shelf, forward tracking, five-search docket, and broader tests.
- `codex-kahuna` has stronger lab discipline, cleaner module boundaries, stricter schemas, better worktree data-root handling, and a richer Research Desk cockpit rendering.
- A literal git merge is not acceptable. These branches independently implemented the same modules, so consolidation must be done by choosing canonical files and intentionally porting specific pieces.

## 3. Non-Goals

Do not merge all generated live LLM output into main.

Do not treat LLM drafts as validated alpha.

Do not let the Lab see forward returns, harness verdicts, PnL, optimizer outputs, combiner scores, or any realized outcome surface.

Do not make the nightly job spend Anthropic/API tokens unless explicitly enabled.

Do not degrade the current cockpit gap engine, Research Desk, Chief-of-Staff chat, or static cockpit fallback behavior.

Do not reintroduce transaction-cost-centric framing as the core bottleneck. ETF expression quality should include liquidity, expense/ownership drag, bid-ask, tracking gap, currency basis, and crowding.

## 4. Canonical Branch And Source Branches

Canonical implementation branch:

- `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO_worktrees/claude-kahuna`
- Git branch: `claude-kahuna`

Port-from branch:

- `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO_worktrees/codex-kahuna`
- Git branch: `codex-kahuna`

Recommended implementation workflow:

1. Create a new integration branch from current `claude-kahuna`.
2. Port targeted Codex pieces manually.
3. Run all tests and live smoke checks.
4. Push the integration branch.
5. Only merge to `main` after the acceptance gates pass.

## 5. Artifact Policy

Version-controlled:

- Source code under `scripts/discovery_triage/`
- Source code under `cos_mockups/`
- Config files under `config/`
- Tests under `tests/discovery_triage/`
- PRDs / implementation docs
- Journal directory placeholders such as `.gitkeep`

Not version-controlled:

- Live generated journal rows:
  - `journal/drafts/DRAFT_*.yaml`
  - `journal/drafts/detector_drafts.jsonl`
  - `journal/looks/research_looks.jsonl`
  - `journal/dockets/discovery_docket_*.md`
  - lock files
- Bulk/generated cockpit payloads, unless the repo already intentionally tracks them as static mock artifacts. If tracked, update them only when a browser-visible UI change requires it and call out the generated churn in the commit.

Before final merge, remove any uncurated generated live model output from the branch unless Arjun explicitly asks to preserve a specific docket/draft as a fixture.

## 6. Functional Requirements

### FR1. Keep Claude's Discovery Lab breadth

The merged Lab must retain the five discovery search modes:

- `cross_surface_contradiction`
- `graph_motif`
- `analog_mismatch`
- `regime_sign_flip`
- `nonlinear_condition_draft`

The daily docket may run all five searches when explicitly enabled.

Each search may emit multiple raw candidates, but the final docket must dedupe, rank, and cap them before surfacing.

### FR2. Adopt Codex's stricter Lab schema

Every persisted detector draft must include:

- `object_type`
- `family_name`
- `members`
- `falsification.fatal_if`
- `falsification.must_check`
- `mythos_self_falsification.strongest_counterargument`
- `mythos_self_falsification.what_would_change_my_mind`
- `epistemic_status`
- `source_look_id`
- `certification_route`

Required arrays must be non-empty.

The model tool schema should enforce this, and post-response validation must independently enforce it again.

Drafts missing mandatory falsification/self-falsification should be rejected or quarantined, never silently shown as useful cards.

### FR3. Preserve outcome-blindness at the data-access layer

Discovery Lab context must be loaded only through the allowlisted surface loader.

Forbidden surfaces include at least:

- `country_returns_daily`
- `country_returns_monthly`
- `factor_returns`
- `factor_returns_daily`
- `forward_returns`
- `harness_results`
- `harness_ic_series`
- `hypothesis_ledger`
- `combiner_scores_daily`
- `combiner_scores`
- `combiner_weights`
- `gap_holdout_daily.promoted`

The surface loader must enforce table allowlists and column deny/allow rules in code, not only in prompts.

Snapshot rows should be point-in-time safe and latest-as-of by country, and where relevant by `(country, variable)`.

### FR4. Dedupe, rank, and cap the daily docket

The docket should collect raw cards from all enabled searches, then produce a morning docket of 3-10 cards.

The docket must:

- Deduplicate repeated country/theme cards.
- Prefer cards with stronger cross-surface evidence and clearer falsification.
- Penalize stale rows, heterogeneous units, single-country outlier dependency, and missing observability.
- Show why a card was ranked.
- Preserve all rejected/dropped counts in metadata.
- Never pad with low-quality cards just to hit the minimum.

The final docket must not say "Cards: 26 (cap 3-10)" while rendering only 10 without explanation. It should distinguish raw candidates from shown cards.

### FR5. Keep the Research Desk useful

The cockpit Research Desk must show, for each Discovery Lab draft:

- Title / family name
- Epistemic badges
- Certification route
- Proposed observable relationships
- Fatal-if checks
- Must-check-before-claim checks
- Strongest counterargument
- What would change the model's mind
- Source look id
- Timestamp

The static cockpit must not show noisy API failures such as `Chief-of-Staff API unavailable` or `HTTP 501` when opening local Research Desk views.

### FR6. Separate harness bridge into a module

Port Codex's cleaner `harness_bridge.py` boundary into the Claude backend.

The bridge should:

- Expose a small public API for freezing/routing claims into harness evaluation.
- Keep Claude's injectable hooks for offline testing.
- Preserve pre-harness gates.
- Charge/track family trial count where applicable.
- Fail closed on missing required claim fields.

`freeze_claim.py` should call this module rather than carrying a large inline harness bridge.

### FR7. Add shared model registry wrapper

Add or port `scripts/discovery_triage/model_registry.py`.

The wrapper should:

- Load `config/model_registry.yaml`.
- Provide `load_model_registry()`.
- Provide `model_metadata(model_id)`.
- Route missing or unknown cutoff to `prospective_only_unknown_cutoff`.

Do not guess training cutoffs.

### FR8. Add shared exceptions module

Add or port `scripts/discovery_triage/exceptions.py`.

Use explicit exception classes for:

- Context/surface policy violations
- Lab output validation failures
- Provenance/routing failures
- Harness bridge failures

Avoid ad hoc generic exceptions where policy failures should be visible.

### FR9. Standardize data-root handling

Use `ASADO_DATA_ROOT` as the canonical runtime data-root override.

Expected behavior:

- Default data root: `<repo>/Data`
- Override: `ASADO_DATA_ROOT=/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data`
- Loop DB: `$ASADO_DATA_ROOT/loop/asado_loop.duckdb`
- Main DB if needed: `$ASADO_DATA_ROOT/asado.duckdb`

Apply this to:

- `daily_docket.py`
- `lab_session.py`
- `forward_track.py`
- any helper that opens the ASADO loop DB
- cockpit data builder if not already present

Hardcoded absolute paths may remain only as documented operator examples, not as primary logic.

### FR10. Nightly job must be safe and verifiable

Nightly Discovery Lab behavior:

- `python -m scripts.discovery_triage.daily_docket --nightly` must no-op unless `ASADO_RUN_DISCOVERY_LAB=1`.
- The no-op must exit 0 and print a clear "disabled/no spend" line.
- The loop job must invoke package modules with `-m` when modules use relative imports.
- The loop job must not report a missing binary for valid `python -m ...` commands.
- Optional status is allowed for live LLM spending, but command wiring failures should be test-detectable.

Validation must be run from a checkout with a working ASADO venv. A worktree without `venv/bin/python` is not enough to prove failure of the code; use the real main checkout or configure the worktree venv before final signoff.

## 7. Technical Requirements

### TR1. Schema strategy

Use strict schemas for append-only custody records:

- looks
- drafts
- claims
- blind rulings
- prospective queue entries
- graveyard tracking entries

Use flexible parsing only for cockpit read models where forward compatibility matters.

### TR2. Journal contract

Freeze the journal draft contract:

```yaml
draft_id: string
object_type: detector_family_draft
family_name: string
members: list
source_look_id: string
certification_route: string
epistemic_status: list
falsification:
  fatal_if: list
  must_check: list
mythos_self_falsification:
  strongest_counterargument: string
  what_would_change_my_mind: list
recorded_ts: string
```

Cockpit readers must accept this canonical shape.

If legacy Claude card fields exist (`card.summary`, `falsification.near_term`, `strongest_objection`), add a migration/normalization layer rather than breaking display.

### TR3. Credential handling

For Anthropic:

- Prefer the parsed project/global env file at `/Users/arjundivecha/Dropbox/AAA Backup/.env.txt` when running ASADO helper scripts, unless an explicit override is requested.
- Avoid trusting stale ambient `ANTHROPIC_API_KEY` by default.
- Never print secrets.
- If credentials fail, report clearly and do not fabricate a fallback model result.

### TR4. Live model limits

One live test is required before merge, but avoid uncontrolled spending.

Suggested live validation:

- First run one search with `--search nonlinear_condition_draft`.
- Confirm strict schema fields are present.
- Then run all five searches only after dedupe/cap is implemented.
- Print token usage summary.

## 8. Implementation Plan

### Phase 1. Branch hygiene

1. Start from current `claude-kahuna`.
2. Create an integration branch, for example `merge/discovery-triage-canonical`.
3. Confirm worktree status is clean.
4. Do not merge generated live journal output.
5. Decide whether static cockpit payload artifacts should be regenerated in this branch or left to runtime.

### Phase 2. Port Codex discipline modules

From `codex-kahuna`, port or recreate:

- `scripts/discovery_triage/exceptions.py`
- `scripts/discovery_triage/model_registry.py`
- `scripts/discovery_triage/harness_bridge.py`
- relevant tests and fixtures

Keep Claude's broad backend behavior unless it conflicts with strict custody.

### Phase 3. Tighten Lab output contract

Modify `scripts/discovery_triage/lab_session.py`:

- Keep multi-search/multi-card support.
- Update tool schema to require canonical fields.
- Require non-empty `fatal_if` and `must_check`.
- Require self-falsification fields.
- Validate after tool return.
- Normalize legacy card shapes into canonical draft records.
- Reject/drop cards with explicit reasons when they fail policy.

### Phase 4. Docket ranking and dedupe

Modify `scripts/discovery_triage/daily_docket.py`:

- Track raw candidate count.
- Deduplicate by country/theme/member signature.
- Score/rank cards.
- Cap shown cards to configured `max_drafts`.
- Include dropped/duplicate counts.
- Render canonical falsification fields.

Add tests:

- duplicate country/theme cards collapse
- raw count differs from shown count cleanly
- card below quality threshold can be dropped
- minimum is not padded with junk

### Phase 5. Runtime path standardization

Apply `ASADO_DATA_ROOT` to:

- `daily_docket.py`
- `forward_track.py`
- `lab_session.py`
- any direct loop DB open in Discovery Triage

Add tests for path resolution without requiring a real DB.

### Phase 6. Nightly wiring

Confirm `scripts/loop/loop_daily_job.py` uses:

```python
("discovery_forward_track", [PY, "-m", "scripts.discovery_triage.forward_track"])
("discovery_docket", [PY, "-m", "scripts.discovery_triage.daily_docket", "--nightly"])
```

Then validate from a checkout with a real venv:

```bash
python3 scripts/loop/loop_daily_job.py --only discovery_docket
```

Expected no-spend behavior:

- exit 0
- no API call
- clear disabled/no-spend message

### Phase 7. Cockpit contract

Ensure `cos_mockups/build_cockpit_data.py` preserves rich draft fields:

- `members`
- `falsification`
- `self_falsification` or normalized `mythos_self_falsification`
- `labels`
- `route_label`

Regenerate `cockpit_live.html` only if the UI source changed.

Browser smoke:

- Open static cockpit.
- Click Research Desk.
- Confirm proposed relationships, fatal-if, must-check, and strongest counterargument are visible.
- Confirm no `HTTP 501` / API-unavailable noise for local Research Desk.

### Phase 8. Generated artifact cleanup

Before final commit/merge:

- Remove generated live `DRAFT_*.yaml` unless intentionally preserved as fixtures.
- Remove generated live JSONL rows unless intentionally preserved as fixtures.
- Keep `.gitkeep` journal dirs.
- Confirm `.gitignore` covers generated journal runtime files and lock files.

### Phase 9. Final validation

Run:

```bash
python3 -m pytest tests/discovery_triage -q
python3 -m scripts.discovery_triage.daily_docket --nightly
```

Then run one live strict-schema search:

```bash
ASADO_DATA_ROOT="/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data" \
  env -u ANTHROPIC_API_KEY \
  python3 -m scripts.discovery_triage.daily_docket \
  --as-of 2026-06-24 \
  --search nonlinear_condition_draft
```

Then, only after that passes, run all enabled searches if desired:

```bash
ASADO_DATA_ROOT="/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data" \
  env -u ANTHROPIC_API_KEY \
  python3 -m scripts.discovery_triage.daily_docket \
  --as-of 2026-06-24
```

## 9. Acceptance Criteria

The merge is complete only when all are true:

1. One canonical branch contains the consolidated implementation.
2. Discovery Lab retains five-search breadth.
3. Every persisted draft has strict falsification and self-falsification fields.
4. The Lab remains outcome-blind by code-level surface enforcement.
5. Docket raw candidates are deduped/ranked/capped before display.
6. Nightly `--nightly` mode exits 0 without spend unless `ASADO_RUN_DISCOVERY_LAB=1`.
7. `ASADO_DATA_ROOT` works for worktrees and the main checkout.
8. Research Desk shows useful details in the cockpit.
9. Static cockpit no longer shows local API failure noise for Research Desk.
10. Generated live LLM artifacts are not accidentally merged as source.
11. `pytest tests/discovery_triage -q` passes.
12. One live Opus/Anthropic run succeeds with the strict schema.
13. Browser smoke confirms the merged front-end path.

## 10. Suggested Commit Structure

1. `Merge discovery triage strict contracts`
2. `Refactor discovery harness bridge`
3. `Rank and cap discovery docket`
4. `Standardize discovery data roots`
5. `Bind rich discovery cards to cockpit`
6. `Clean generated discovery artifacts`

Keep generated payload churn separate from source changes if it must be committed.

## 11. Final Operator Notes

The merged system should run wide and think creatively, but publish narrowly and skeptically.

The goal is not "more LLM ideas." The goal is:

- more non-obvious relationships found,
- fewer ungrounded claims shown,
- every claim forced through falsification,
- every possible alpha routed through prospective evidence before it can matter.

In short:

**Claude backend breadth + Codex custody discipline = canonical ASADO Discovery Triage.**
