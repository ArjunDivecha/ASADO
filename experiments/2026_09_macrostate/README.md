# MacroState — research experiments

**Latest:** [first linear, tree and neural model results](MODEL_RESULTS.md). Stages 3–5 are complete; the original input/evaluator stage is retained below.

Run the frozen model reproduction with `OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 venv/bin/python experiments/2026_09_macrostate/validate_models.py --prepared Data/work/experiments/macrostate_stage12/prepared` from the ASADO root. The additional missingness diagnostic is `stage5/run_masks.py`, with the same `--prepared` and its own `--out` directory.

## Original Stage 1–2 package

Stages 1–2 completed, 6 September 2026. **Question:** can a future MacroState ranking improve top-20% gross portfolio results versus equal-weight countries? **Current verdict:** input preparation and evaluator validated; MacroState has not yet been fitted or backtested.

Start with [RESULTS.md](RESULTS.md). The [results-first contract](contract.json) implements Arjun's latest direction: portfolio outcomes, without statistical-significance pass/fail gates. It supersedes statistical acceptance thresholds in the earlier research plan for this experiment; it does not change production harness rules.

- `prepare.py`: freezes existing source files, verifies workbook ticker/field order, preserves missingness, constructs 14 primitives and four explicitly masked state composites, and generates targets/availability clocks.
- `evaluator.py`: top ceil(20% × eligible count), equal weight, monthly or twelve-month staggered holdings; matched and broader equal-weight benchmarks; cumulative/annualized returns, drawdowns, win rates and reconciling country P&L.
- `test_stage12.py`: 24 timing/accounting canaries.
- `verify.py`: runs the build, canaries, real-data prefix checks and baseline demonstration end to end.
- `results/`: small keepable evidence; input snapshots and prepared panels remain under `Data/work/experiments/macrostate_stage12/`.

Source snapshot: [manifest](../../Data/work/experiments/macrostate_stage12/inputs/manifest.json). Prepared panels: `../../Data/work/experiments/macrostate_stage12/prepared/`. Source history is conditional vendor history; code timing is verified, original vendor revision provenance is not.

Run from the ASADO root, using the already installed environment:

```sh
venv/bin/python experiments/2026_09_macrostate/verify.py --root "$PWD" --scratch "$PWD/Data/work/experiments/macrostate_stage12"
```

If frozen sources have since changed, the runner refuses to overwrite the snapshot. Use a new scratch directory to create a separately identified run. No production DB, collectors, scheduler, configuration or ledger is modified. Work was developed in the isolated `exp/macrostate-stage12` worktree; only this new experiment directory is published in the main workspace. The seed and original research plan are preserved.
