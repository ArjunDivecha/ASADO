# experiments/ — the sandbox convention

ASADO doubles as a base for experimentation. This directory is where experiments
live so they never interfere with the production nightly pipeline (daily_update →
loop job → briefs) or the Fable Daily Trading system that reads the loop DB.

## The five rules (also in AGENTS.md — binding for all agent sessions)

1. **Never experiment in the main checkout's state.** Code experiments that modify
   pipeline code use a git worktree: `git worktree add "../ASADO-exp-<name>" -b exp/<name>`.
   The main tree stays on `main` — launchd runs whatever is checked out here.
2. **Snapshot, don't share.** Never hold a connection to `Data/asado.duckdb` or
   `Data/loop/asado_loop.duckdb` — even read-only connections block the nightly
   writers (DuckDB is one-writer OR many-readers). Freeze what you need first:
   `python scripts/snapshot_for_experiment.py --db loop --tables combiner_scores_daily,dislocation_daily --name my_exp`
   then work entirely off the parquet snapshot. Open→query→close in seconds if
   you must touch the live DB directly.
3. **Own your output space.** Code + keepable results: `experiments/<YYYY_MM>_<name>/`
   (committed, with a short README: question, data snapshot used, verdict).
   Scratch + snapshots: `Data/work/experiments/<name>/` (gitignored). NEVER write
   into `Data/processed/`, `Data/loop/`, `Data/work/{t2,gdelt,econ,loop,...}`,
   `config/`, or `ledgers/` from an experiment.
4. **Verdicts go through the front door.** Exploration is unrestricted, but any
   claim that a signal works must be registered as a harness trial charged to a
   family (`config/family_registry.yaml`) — otherwise the deflated-Sharpe
   accounting dies. Never `sweep_signals.py --force` for re-measurement.
5. **Isolate your environment.** Need new packages? Make a venv inside your
   experiment dir (`uv venv`). Never pip-install into `ASADO/venv` — the nightly
   pipeline depends on it. Long jobs: avoid holding anything 06:00–08:30 PT.

## Layout of one experiment

```
experiments/2026_07_example_name/
  README.md          # question, hypothesis, snapshot used, result, verdict
  run.py             # code (mandatory doc header, absolute paths)
  results/           # small keepable outputs (xlsx/pdf/md)
```

Big/regenerable artifacts stay in `Data/work/experiments/example_name/`.
