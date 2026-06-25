# PRD — ASADO Discovery Triage V1

## One-paragraph summary

ASADO Discovery Triage adds a quarantined LLM-native Discovery Lab and a minimal chain-of-custody Court around the existing Known Gap Monitor. The aim is to recover ASADO's original dream — discovering strange nonlinear relationships deterministic detectors would never invent — without laundering retrospective LLM stories into validated alpha. V1 is intentionally small: JSONL/YAML first, model training cutoff treated as the true PIT boundary for LLM-generated ideas, discipline before Lab, blind human rulings before bull-case unsealing, and forward tracking for both survivors and the graveyard.

## Non-negotiable design decisions

1. **The book is the center, not the magic.** Discovery and disbelief are instruments toward tradable, survivable country allocation.
2. **Model training cutoff is the real PIT boundary for LLM ideas.** Tool-level outcome blindness is necessary but insufficient; any certification window at or before the model's training cutoff is exploratory/prospective-only.
3. **Discipline precedes daily Lab operation.** The denominator, provenance classifier, minimal probes, and blind packet exist before the daily docket is enabled.
4. **Outcome-blind mode is enforced by code.** Context builders reject forward returns, harness verdicts, PnL, candidate outcomes, factor returns, top-20 membership, and attribution surfaces.
5. **The graveyard is a control arm.** Killed and quarantined ideas are tracked forward when mechanically measurable so ASADO can learn whether skepticism is helping or starving the book.

## V1 workflow

1. Known Gap Monitor emits deterministic measured relationships.
2. Research Look Ledger records what an LLM/human/tool saw before drafts were created.
3. Discovery Lab emits drafts only: cross-surface contradictions, graph motifs, analog mismatches, regime sign flips, and nonlinear condition drafts.
4. Claim Freezer turns selected drafts into attackable claims linked to looks/drafts/hypotheses.
5. Minimal triage runs target-reentry, crisis-concentration placeholder, country/region concentration placeholder, and conditional lag/horizon flags.
6. Blind packet excludes generator rationale and bull case.
7. Human records a blind ruling before unsealing rationale.
8. Router sends every claim — survivor, killed, quarantined, or legacy — into forward tracking when measurable.
9. Daily Discovery Docket writes one markdown artifact with 3–10 drafts and routes.

## V1 deliverables

- `config/discovery_triage.yaml`
- `config/claim_provenance_policy.yaml`
- `config/analog_metric_registry.yaml`
- `config/triage_probe_registry.yaml`
- `journal/*` JSONL/YAML-first storage directories
- `scripts/discovery_triage/*` minimal implementation
- `tests/discovery_triage/*` acceptance tests

## Explicit deferrals

- No LLM Prosecutor in V1.
- No prosecutor calibration until enough forward outcomes exist.
- No new DuckDB tables until JSONL workflow proves stable.
- No trade recommendation output.
