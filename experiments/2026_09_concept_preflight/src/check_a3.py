"""
=============================================================================
SCRIPT NAME: check_a3.py
=============================================================================
Check A3 of the concept-layer pre-flight (replacement for the underpowered A2):
do the panel's 9 concepts explain next-year country returns better than chance,
once country identity is removed? U.S. markets excluded (amendment A3-1).
Pre-registration: ../PREREG.md, sections "Check A3" and "Amendment A3-1".

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/concept_preflight/snapshot_2026_09_23/t2_master.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/concept_preflight/snapshot_2026_09_23/t2_factors_daily.parquet   (--real only)

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_concept_preflight/results/check_a3_power.json   (--power)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_concept_preflight/results/check_a3.json         (--real)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_concept_preflight/results/check_a3_null.pdf     (--real)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_concept_preflight/results/check_a3.log

VERSION: 1.0
LAST UPDATED: 2026-09-23
AUTHOR: Claude (Opus 5.5) for Arjun Divecha

DESCRIPTION:
Concepts = top 9 principal components of the standardised ex-U.S. _CS panel
(features only). Primary statistic: pooled OLS R^2 of the two-way demeaned
(month and country) 12-month forward relative return on the two-way demeaned
concept scores. Null: 1,000 country-block permutations (each country's whole
target history reassigned to another country), same demeaning and regression.
--power runs the pre-registered power calibration on synthetic targets built
only from the features plus synthetic overlapping noise; it never reads returns.

DEPENDENCIES: numpy, pandas, matplotlib (ASADO venv)
USAGE:
  cd experiments/2026_09_concept_preflight/src
  ../../../venv/bin/python check_a3.py --power
  ../../../venv/bin/python check_a3.py --real
NOTES: diagnostic only; nothing outside results/ is written.
=============================================================================
"""
from __future__ import annotations

import argparse
import json
import os
import time
from concurrent.futures import ProcessPoolExecutor

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from check_a_spectral import load_features, parallel_analysis, standardize
from common import RESULTS, daily_returns, monthly_returns

US = {"U.S.", "NASDAQ", "US SmallCap"}
K = 9
N_PERM = 1000
N_POWER_DRAWS = 200
N_POWER_PERM = 200
RHOS = (0.05, 0.10, 0.20)
LOG = RESULTS / "check_a3.log"


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as fh:
        fh.write(line + "\n")


# ── panel ───────────────────────────────────────────────────────────────────
def build_panel():
    wide, info = load_features()
    wide = wide[~wide.index.get_level_values("country").isin(US)]
    months = wide.index.get_level_values("month")
    countries = wide.index.get_level_values("country")
    X = standardize(wide.to_numpy())
    C = np.corrcoef(X, rowvar=False)
    lam, V = np.linalg.eigh(C)
    order = np.argsort(lam)[::-1]
    Z = X @ V[:, order[:K]]
    m_levels = pd.PeriodIndex(sorted(months.unique()), freq="M")
    c_levels = sorted(countries.unique())
    mi = m_levels.get_indexer(months)
    ci = np.array([c_levels.index(c) for c in countries])
    return wide, X, Z, mi, ci, m_levels, c_levels, info


def demean(M: np.ndarray, mi: np.ndarray, ci: np.ndarray, two_way: bool = True,
           tol: float = 1e-10, max_iter: int = 200) -> np.ndarray:
    M = M.astype(float).copy()
    if M.ndim == 1:
        M = M[:, None]
    nm, nc = mi.max() + 1, ci.max() + 1
    cnt_m = np.bincount(mi, minlength=nm).astype(float)
    cnt_c = np.bincount(ci, minlength=nc).astype(float)
    for _ in range(max_iter if two_way else 1):
        mm = np.stack([np.bincount(mi, M[:, j], nm) for j in range(M.shape[1])], 1) / np.maximum(cnt_m, 1)[:, None]
        M -= mm[mi]
        if not two_way:
            break
        cm = np.stack([np.bincount(ci, M[:, j], nc) for j in range(M.shape[1])], 1) / np.maximum(cnt_c, 1)[:, None]
        M -= cm[ci]
        if np.abs(cm).max() < tol:
            break
    return M


def r2(Zd: np.ndarray, yd: np.ndarray) -> float:
    beta, *_ = np.linalg.lstsq(Zd, yd, rcond=None)
    resid = yd - Zd @ beta
    return float(1 - resid @ resid / (yd @ yd))


def stat_for(Y: np.ndarray, perm: np.ndarray | None, Z, mi, ci, two_way=True) -> float:
    """Y: (months x countries) target array (NaN = missing). perm maps country code -> source code."""
    src = ci if perm is None else perm[ci]
    y = Y[mi, src]
    ok = ~np.isnan(y)
    mi2, ci2 = mi[ok], ci[ok]
    # re-index to contiguous codes for the sample
    _, mi2 = np.unique(mi2, return_inverse=True)
    _, ci2 = np.unique(ci2, return_inverse=True)
    Zd = demean(Z[ok], mi2, ci2, two_way)
    yd = demean(y[ok], mi2, ci2, two_way)[:, 0]
    return r2(Zd, yd)


def perm_test(Y, Z, mi, ci, n_perm, seed, two_way=True):
    rng = np.random.default_rng(seed)
    real = stat_for(Y, None, Z, mi, ci, two_way)
    nc = ci.max() + 1
    null = np.array([stat_for(Y, rng.permutation(nc), Z, mi, ci, two_way) for _ in range(n_perm)])
    return real, null


# ── power (synthetic only) ──────────────────────────────────────────────────
_G = {}


def _power_init(Z, mi, ci, n_months, n_countries, sample_ok):
    _G.update(Z=Z, mi=mi, ci=ci, nm=n_months, nc=n_countries, ok=sample_ok)


def _power_draw(args):
    rho, seed = args
    g = _G
    rng = np.random.default_rng(seed)
    Z, mi, ci, nm, nc, ok = g["Z"], g["mi"], g["ci"], g["nm"], g["nc"], g["ok"]
    Zd_full = demean(Z, mi, ci, True)
    s = Zd_full[:, :3] @ rng.normal(size=3)
    s = (s - s.mean()) / s.std()
    monthly = rng.normal(size=(nm + 11, nc))
    n12 = np.array([monthly[t:t + 12].sum(0) for t in range(nm)])       # overlapping 12M noise
    n = n12[mi, ci]
    n = (n - n.mean()) / n.std()
    y_rows = rho * s + np.sqrt(1 - rho**2) * n
    Y = np.full((nm, nc), np.nan)
    Y[mi[ok], ci[ok]] = y_rows[ok]
    real, null = perm_test(Y, Z, mi, ci, N_POWER_PERM, seed + 1)
    return real > np.percentile(null, 95)


def run_power(Z, mi, ci, m_levels, c_levels, last_target_month):
    sample_ok = np.asarray(m_levels[mi] <= last_target_month)
    out = {"design": {"draws": N_POWER_DRAWS, "perms_per_draw": N_POWER_PERM,
                      "countries": len(c_levels), "rows": int(sample_ok.sum())},
           "detection_rate": {}}
    workers = max(1, (os.cpu_count() or 4) - 2)
    with ProcessPoolExecutor(workers, initializer=_power_init,
                             initargs=(Z, mi, ci, len(m_levels), len(c_levels), sample_ok)) as ex:
        for rho in RHOS:
            hits = list(ex.map(_power_draw, [(rho, 1000 * i + int(rho * 100)) for i in range(N_POWER_DRAWS)]))
            rate = float(np.mean(hits))
            out["detection_rate"][str(rho)] = rate
            log(f"power: planted corr {rho:.2f} -> detected {rate:.1%}")
    out["underpowered_at_0.10"] = out["detection_rate"]["0.1"] < 0.5
    return out


# ── main ────────────────────────────────────────────────────────────────────
def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--power", action="store_true")
    g.add_argument("--real", action="store_true")
    a = ap.parse_args()
    RESULTS.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    wide, X, Z, mi, ci, m_levels, c_levels, info = build_panel()
    log(f"ex-U.S. panel: {len(c_levels)} markets, {len(m_levels)} months, {len(Z)} rows, "
        f"{X.shape[1]} variables, {K} concepts")
    # last month whose 12M target can be complete: derived from the calendar, not from returns
    last_complete = pd.Period("2026-08", "M")
    last_target_month = last_complete - 11

    if a.power:
        out = run_power(Z, mi, ci, m_levels, c_levels, last_target_month)
        out["elapsed_sec"] = round(time.time() - t0, 1)
        (RESULTS / "check_a3_power.json").write_text(json.dumps(out, indent=2))
        log(f"power done in {out['elapsed_sec']}s; underpowered at 0.10: {out['underpowered_at_0.10']}")
        return

    d = daily_returns()
    mret, _, last = monthly_returns(d)
    assert last == last_complete, f"last complete month {last} != {last_complete}"
    lr = np.log1p(mret)
    r12 = np.expm1(lr[::-1].rolling(12, min_periods=12).sum()[::-1])
    out = {"data": {"markets": c_levels, "months": len(m_levels), "rows": len(Z)}, "tests": {}}

    def target_array(ret: pd.DataFrame) -> np.ndarray:
        r = ret.reindex(index=m_levels, columns=c_levels)
        r = r.sub(r.mean(axis=1), axis=0)      # relative to the ex-U.S. cross-section
        return r.to_numpy()

    Y12, Y1 = target_array(r12), target_array(mret)
    for name, Y, two_way in (("12M_two_way (PRIMARY)", Y12, True), ("12M_month_only", Y12, False),
                             ("1M_two_way", Y1, True)):
        real, null = perm_test(Y, Z, mi, ci, N_PERM, 20260923, two_way)
        p95 = float(np.percentile(null, 95))
        out["tests"][name] = {"r2": real, "null_mean": float(null.mean()), "null_p95": p95,
                              "p_value": float((1 + (null >= real).sum()) / (1 + len(null))),
                              "above_null_p95": bool(real > p95)}
        log(f"{name}: R2={real:.4f}; null mean {null.mean():.4f}, p95 {p95:.4f}; "
            f"p={out['tests'][name]['p_value']:.3f}")
        if name.startswith("12M_two_way"):
            prim_null = null
    # per-concept univariate R^2 (primary demeaning)
    y = Y12[mi, ci]
    ok = ~np.isnan(y)
    Zd = demean(Z[ok], np.unique(mi[ok], return_inverse=True)[1], np.unique(ci[ok], return_inverse=True)[1])
    yd = demean(y[ok], np.unique(mi[ok], return_inverse=True)[1], np.unique(ci[ok], return_inverse=True)[1])[:, 0]
    out["per_concept_r2"] = {f"C{j+1:02d}": r2(Zd[:, [j]], yd) for j in range(K)}
    # descriptive: ex-U.S. concept count
    rng = np.random.default_rng(11)
    groups = np.asarray(m_levels[mi].astype(str))
    out["ex_us_k_var"] = parallel_analysis(X, groups, rng)["k_var"]
    prim = out["tests"]["12M_two_way (PRIMARY)"]
    out["decision"] = ("PROCEED: node-level concept experiment, at most 9 concepts"
                       if prim["above_null_p95"] else
                       "DROP: node-level concept experiment (final)")
    out["elapsed_sec"] = round(time.time() - t0, 1)
    log(f"ex-U.S. k_var {out['ex_us_k_var']}; decision: {out['decision']} ({out['elapsed_sec']}s)")
    tmp = RESULTS / "check_a3.json.tmp"
    tmp.write_text(json.dumps(out, indent=2))
    tmp.replace(RESULTS / "check_a3.json")
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(prim_null, bins=40, color="#9bb7d4")
    ax.axvline(prim["null_p95"], color="#888888", ls="--", label="null 95th pct")
    ax.axvline(prim["r2"], color="#c0392b", lw=2, label="real")
    ax.set_xlabel("R² of next-year relative return on 9 concepts (identity removed)")
    ax.set_title("Check A3, ex-U.S.: real vs 1,000 country permutations")
    ax.legend(frameon=False)
    ax.set_facecolor("white"); fig.patch.set_facecolor("white")
    fig.tight_layout()
    fig.savefig(RESULTS / "check_a3_null.pdf")


if __name__ == "__main__":
    main()
