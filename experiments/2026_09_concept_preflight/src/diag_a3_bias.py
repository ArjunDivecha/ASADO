"""
=============================================================================
SCRIPT NAME: diag_a3_bias.py
=============================================================================
POST-HOC DIAGNOSTIC for Check A3 (not pre-registered; does not change A3's
registered decision). Tests whether A3's pass is produced by look-ahead in
full-sample country demeaning of persistent / price-level features (the
panel fixed-effects "Nickell"-type bias), which the country-block permutation
null does not reproduce.

D1: past-only identity removal - each country's features are demeaned by their
    own expanding mean over earlier months (>=24 obs); the 12M target by the
    country's mean of already-matured targets (months <= t-12, >=24 obs);
    then month-demeaned. Same 1,000-permutation null with the same procedure.
D2: A3's two-way test after dropping the five level-type variables
    (PX_LAST_CS, Tot Return Index _CS, MCAP_CS, MCAP Adj_CS, Mcap Weights_CS).
D3: D1 applied to the D2 panel.

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/concept_preflight/snapshot_2026_09_23/t2_master.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/concept_preflight/snapshot_2026_09_23/t2_factors_daily.parquet
OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_concept_preflight/results/diag_a3_bias.json
VERSION: 1.0   LAST UPDATED: 2026-09-23   AUTHOR: Claude (Opus 5.5) for Arjun Divecha
DEPENDENCIES: numpy, pandas (ASADO venv)
USAGE: cd experiments/2026_09_concept_preflight/src && ../../../venv/bin/python diag_a3_bias.py
=============================================================================
"""
import json
import numpy as np
import pandas as pd
from check_a_spectral import load_features, standardize
from check_a3 import US, K, demean, r2, perm_test
from common import RESULTS, daily_returns, monthly_returns

LEVELS = ["PX_LAST_CS", "Tot Return Index _CS", "MCAP_CS", "MCAP Adj_CS", "Mcap Weights_CS"]
N_PERM = 1000


def panel(drop_levels):
    wide, _ = load_features()
    wide = wide[~wide.index.get_level_values("country").isin(US)]
    if drop_levels:
        wide = wide.drop(columns=[c for c in LEVELS if c in wide.columns])
    X = standardize(wide.to_numpy())
    lam, V = np.linalg.eigh(np.corrcoef(X, rowvar=False))
    Z = X @ V[:, np.argsort(lam)[::-1][:K]]
    months = wide.index.get_level_values("month")
    countries = wide.index.get_level_values("country")
    m_levels = pd.PeriodIndex(sorted(months.unique()), freq="M")
    c_levels = sorted(countries.unique())
    return Z, m_levels.get_indexer(months), np.array([c_levels.index(c) for c in countries]), m_levels, c_levels, wide.shape[1]


def past_only_stat(Y, perm, Z, mi, ci, nm, nc):
    src = ci if perm is None else perm[ci]
    # dense arrays months x countries
    Zg = np.full((nm, nc, Z.shape[1]), np.nan); Zg[mi, ci] = Z
    Yg = np.full((nm, nc), np.nan); Yg[mi, ci] = Y[mi, src]
    # expanding past means (strictly earlier months) for features
    cz = np.nancumsum(np.nan_to_num(Zg), axis=0); nz = np.cumsum(~np.isnan(Zg[..., 0]), axis=0)
    zbar = np.full_like(Zg, np.nan)
    zbar[1:] = cz[:-1] / np.where(nz[:-1] >= 24, nz[:-1], np.nan)[..., None]
    # matured targets: mean of Y over months <= t-12
    cy = np.nancumsum(np.nan_to_num(Yg), axis=0); ny = np.cumsum(~np.isnan(Yg), axis=0)
    ybar = np.full_like(Yg, np.nan)
    ybar[12:] = cy[:-12] / np.where(ny[:-12] >= 24, ny[:-12], np.nan)
    Zd = Zg - zbar; yd = Yg - ybar
    ok = ~np.isnan(yd) & ~np.isnan(Zd).any(-1)
    ok &= ~np.isnan(Zg[..., 0])
    t, c = np.where(ok)
    Zr, yr = Zd[t, c], yd[t, c]
    _, tt = np.unique(t, return_inverse=True); _, cc = np.unique(c, return_inverse=True)
    return r2(demean(Zr, tt, cc, False), demean(yr, tt, cc, False)[:, 0]), int(ok.sum())


def main():
    d = daily_returns(); mret, _, _ = monthly_returns(d)
    r12 = np.expm1(np.log1p(mret)[::-1].rolling(12, min_periods=12).sum()[::-1])
    out = {}
    for drop in (False, True):
        Z, mi, ci, m_levels, c_levels, nvar = panel(drop)
        r = r12.reindex(index=m_levels, columns=c_levels)
        Y = r.sub(r.mean(axis=1), axis=0).to_numpy()
        tag = "levels_dropped" if drop else "all_36_vars"
        # two-way (A3 method)
        real, null = perm_test(Y, Z, mi, ci, N_PERM, 20260923, True)
        out[f"two_way_{tag}"] = {"variables": nvar, "r2": real, "null_p95": float(np.percentile(null, 95)),
                                 "p": float((1 + (null >= real).sum()) / (1 + N_PERM))}
        # past-only
        rng = np.random.default_rng(20260923)
        nm, nc = len(m_levels), len(c_levels)
        real_p, rows = past_only_stat(Y, None, Z, mi, ci, nm, nc)
        nullp = np.array([past_only_stat(Y, rng.permutation(nc), Z, mi, ci, nm, nc)[0] for _ in range(N_PERM)])
        out[f"past_only_{tag}"] = {"variables": nvar, "rows": rows, "r2": real_p,
                                   "null_p95": float(np.percentile(nullp, 95)),
                                   "p": float((1 + (nullp >= real_p).sum()) / (1 + N_PERM))}
        for k in (f"two_way_{tag}", f"past_only_{tag}"):
            v = out[k]; print(f"{k:28s} R2={v['r2']:.4f} null p95={v['null_p95']:.4f} p={v['p']:.3f}")
    (RESULTS / "diag_a3_bias.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
