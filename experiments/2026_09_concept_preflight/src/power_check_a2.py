"""
=============================================================================
SCRIPT NAME: power_check_a2.py
=============================================================================
Post-hoc POWER check for Check A2 (not part of the pre-registered decision; it
characterises how sensitive the pre-registered test is). Plants a synthetic
target concentrated in the top-3 principal directions of the real T2 feature
panel at pooled correlations 0.05 / 0.10 / 0.20 / 0.30 and records how often
the source-condition slope clears the real test's null 95th percentile.

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/concept_preflight/snapshot_2026_09_23/t2_master.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_concept_preflight/results/check_a_spectral.json

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_concept_preflight/results/check_a_power.json

VERSION: 1.0   LAST UPDATED: 2026-09-23   AUTHOR: Claude (Opus 5.5) for Arjun Divecha
DEPENDENCIES: numpy, pandas (ASADO venv)
USAGE: cd experiments/2026_09_concept_preflight/src && ../../../venv/bin/python power_check_a2.py
=============================================================================
"""
import json
import numpy as np
from check_a_spectral import load_features, standardize, source_slope
from common import RESULTS

wide, _ = load_features()
X = standardize(wide.to_numpy())
p95 = json.loads((RESULTS / "check_a_spectral.json").read_text())["A2"]["12M"]["null_p95"]
lam, V = np.linalg.eigh(X.T @ X / len(X))
top = V[:, np.argsort(lam)[::-1][:3]]
rng = np.random.default_rng(7)
out = {"null_p95_used": p95, "reps": 100, "detection_rate": {}}
for rho in (0.05, 0.10, 0.20, 0.30):
    hits = 0
    for _ in range(100):
        s = X @ (top @ rng.normal(size=3))
        s = (s - s.mean()) / s.std()
        y = rho * s + np.sqrt(1 - rho**2) * rng.normal(size=len(s))
        hits += source_slope(X, (y - y.mean()) / y.std())[0] > p95
    out["detection_rate"][str(rho)] = hits / 100
    print(f"planted pooled corr {rho:.2f}: detected {hits}/100")
(RESULTS / "check_a_power.json").write_text(json.dumps(out, indent=2))
