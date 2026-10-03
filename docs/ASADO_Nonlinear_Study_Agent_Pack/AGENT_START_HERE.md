# Start here: ASADO nonlinear study

Read `ASADO_Nonlinear_Study_PRD.md` as the authoritative implementation specification. The HTML file is a navigable reading copy of the same text.

## Assignment

Implement the complete study in the existing ASADO repository, starting with P00 local-governance reconciliation and P01 read-only field-level data auditing. Follow the phase gates rather than jumping directly to fitting XGBoost-like models. Reuse verified ASADO utilities and preserve the existing daily loop.

The sole primary candidate is pooled depth-two histogram boosting on the fixed 16-input representation, predicting 20-local-session USD total returns. Compare independently tuned raw/state ridge models on an identical PIT-safe sample. All controls, grids, clocks, thresholds, and stop rules are specified in the PRD. A valid negative result is an acceptable completed study.

## Package contents

- `ASADO_Nonlinear_Study_PRD.md`: full requirements, every phase, module contracts, scientific gates, and source register.
- `ASADO_Nonlinear_Study_PRD.html`: readable, searchable rendering.
- `config/study.template.json`: draft scientific settings; not a registered or existing executable ASADO configuration.
- `config/feature_manifest.template.yaml`: all 24 aliases, deliberately unbound until local schema/collector inspection.
- `config/schemas/study.schema.json`: envelope validation with stricter registered-state requirements.
- `config/schemas/data_contracts.json`: minimum logical records and invariants.
- `implementation_backlog.json`: 56 dependency-linked tasks across 14 phases.
- `acceptance_tests.json`: 60 required test specifications; none are claimed executed against ASADO.
- `validate_pack.py`: standard-library validator for this handoff package, not the research pipeline.

## First implementation checkpoint

Deliver local protocol/harness reconciliation, a bound or blocked feature manifest, real coverage and source-timing evidence, an immutable snapshot plan, and the independent calendar/target contracts. Build synthetic testable modules in parallel where useful. Do not show real outer IC, Sharpe, or winner rankings at this checkpoint.

Proceed through engineering and registration, then execute the full pre-registered replay and evaluation. Do not ask the owner to repeat fixed choices, but obtain required registration approval and return concrete evidence for material blockers. Never invent source fields, replace missing features based on performance, relax failed support gates, or change the primary model after seeing results.

The original brief's exclusions and gross-only policy still bind. Do not write study tables into the rebuilt warehouse, initiate new data purchases, change production scheduling, or place trades. Prospective scheduling and the neural extension are disabled unless separately authorized.

## Validate this package

```bash
python validate_pack.py
python validate_pack.py --require-registered
```

The first command should pass package integrity checks. The second should fail for the supplied draft: registration, source bindings, source snapshot, native harness mapping, and approval must be established locally. A passing package-integrity check does not validate the scientific experiment or the ASADO data.
