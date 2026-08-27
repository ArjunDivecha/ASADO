# Geopolitical alpha experiment

This experiment tests three claims suggested by Marko Papic's constraint-first framework:
geopolitical risk prediction, conditional reversal, and incremental country-ranking alpha.

Inputs are frozen parquet snapshots created by `scripts/snapshot_for_experiment.py`. The exact
constraint-minus-market probability history does not currently exist in ASADO, so the experiment
keeps proxy evidence separate from the exact-framework readiness audit.

Run from the experiment worktree with the production ASADO interpreter:

```bash
/Users/arjundivecha/Dropbox/AAA\ Backup/A\ Working/ASADO/venv/bin/python \
  experiments/2026_08_geopolitical_alpha/run.py
```

Results are written only to `experiments/2026_08_geopolitical_alpha/results/`.
