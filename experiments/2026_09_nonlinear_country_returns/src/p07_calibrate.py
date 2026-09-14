# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/src/p07_calibrate.py
#
# PRD 11.1 — statistical engine calibration. 100 fixed replications of
# stationary, zero-mean paired-loss-difference processes with serial
# correlation (AR(1) phi=0.5 and the overlapping-20-innovation
# construction), same sample length as the planned outer scored axis and
# the registered 63-origin block size. One-sided block-bootstrap test +
# Holm over the three primary comparisons. Report empirical familywise
# rejection rate and Wilson interval. 95% Wilson lower bound above 5%
# nominal -> INVALID_INFERENCE_CALIBRATION.
# =============================================================================
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from estimators import MASTER_SEED, moving_block_bootstrap, holm_adjust

EXP = Path(__file__).resolve().parents[1]
AUDIT = EXP / "audit"
REPS = 100
BLOCK = 63
DRAWS = 5000
NOMINAL = 0.05


def scored_axis_len() -> int:
    """Outer scored origin count: eligible origins >= first fit cutoff with
    whole-mature h20 outcomes (the axis the primary tests run on)."""
    from metrics import load_scored
    return int(load_scored()["origin_date"].nunique())


def ar1(T: int, phi: float, rng) -> np.ndarray:
    e = np.empty(T)
    e[0] = rng.randn()
    sd = np.sqrt(1 - phi ** 2)
    for t in range(1, T):
        e[t] = phi * e[t - 1] + sd * rng.randn()
    return e


def overlap20(T: int, rng) -> np.ndarray:
    """Overlapping-20-innovation: x_t = sum of innovations t..t+19 -> the
    20-origin overlap structure of the real labels."""
    u = rng.randn(T + 19)
    return np.array([u[t:t + 20].sum() for t in range(T)])


def boot_pvalue(d: np.ndarray, seed: int) -> float:
    """One-sided mean-improvement p: center under zero-mean null,
    MBB the mean, p = (1 + count(null >= obs)) / (B+1) (PRD 12.3)."""
    obs = np.nanmean(d)
    centered = d - obs
    draws = moving_block_bootstrap(centered, block=BLOCK, draws=DRAWS,
                                   seed=seed)
    return float((1 + np.sum(draws >= obs)) / (DRAWS + 1))


def wilson_lb(k: int, n: int, z: float = 1.96) -> float:
    if n == 0:
        return 0.0
    p = k / n
    den = 1 + z ** 2 / n
    return (p - z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2))) / den


def run_calibration() -> dict:
    T = scored_axis_len()
    print(f"scored axis T={T}, reps={REPS}, block={BLOCK}, draws={DRAWS}")
    out = {}
    for name, gen in (("ar1_phi0.5", lambda r: ar1(T, 0.5, r)),
                      ("overlap20", lambda r: overlap20(T, r))):
        fwer_hits = 0
        pvals_all = []
        for rep in range(REPS):
            rng = np.random.RandomState(MASTER_SEED + 700_000 + rep)
            # three correlated-ish null comparisons per rep (the primary
            # family); common component induces cross-test dependence
            common = gen(rng)
            pvals = []
            for j in range(3):
                d = 0.5 * common + np.sqrt(0.75) * gen(rng)
                pvals.append(boot_pvalue(d, seed=MASTER_SEED + 800_000 +
                                         rep * 10 + j))
            adj = holm_adjust(pvals)
            pvals_all.append(pvals)
            if any(p < NOMINAL for p in adj):
                fwer_hits += 1
        fwer = fwer_hits / REPS
        lb = wilson_lb(fwer_hits, REPS)
        valid = lb <= NOMINAL
        out[name] = {"empirical_fwer": fwer, "rejects": fwer_hits,
                     "reps": REPS, "wilson95_lb": lb,
                     "valid": bool(valid)}
        print(f"{name}: FWER={fwer:.2f} ({fwer_hits}/{REPS}) "
              f"Wilson LB={lb:.3f} -> {'VALID' if valid else 'INVALID'}")
    status = ("PASS" if all(v["valid"] for v in out.values())
              else "INVALID_INFERENCE_CALIBRATION")
    res = {"phase": "P07-11.1", "T": T, "block": BLOCK, "draws": DRAWS,
           "nominal": NOMINAL, "reps": REPS, "processes": out,
           "status": status}
    (AUDIT / "P07_calibration.json").write_text(json.dumps(res, indent=1))
    print("status:", status)
    return res


if __name__ == "__main__":
    run_calibration()
