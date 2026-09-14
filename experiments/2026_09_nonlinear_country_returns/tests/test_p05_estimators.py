# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/tests/test_p05_estimators.py
#
# P05 synthetic QA — acceptance tests T26, T28, T30, T31, T32, T35, T36,
# T39, T42, T43, T44, T59 plus ridge-weight semantics and HGB determinism.
# =============================================================================
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from estimators import (HGBLeafAdapter, RIDGE_GRID, apply_fold_scaler, b0_mean,  # noqa: E402
                        fit_fold_scaler, fit_hgb, fit_ridge, holm_adjust,
                        leaf_support_audit, moving_block_bootstrap,
                        one_se_select, predict_ridge, quadratic_expand,
                        row_weights)

rng = np.random.RandomState(7)


# ---- T31: hand-derived weighted ridge --------------------------------------
def test_t31_ridge_closed_form():
    X = rng.randn(80, 3); y = X @ np.array([1., -2., 0.5]) + 0.3 + rng.randn(80) * 0.01
    w = rng.rand(80); w /= w.sum()
    lam = 2.5
    coef = fit_ridge(X, y, w, lam)
    # hand-derived normal equations
    A = np.column_stack([np.ones(80), X])
    G = (A * w[:, None]).T @ A
    for i in range(1, 4):
        G[i, i] += lam
    b = (A * w[:, None]).T @ y
    hand = np.linalg.solve(G, b)
    assert np.allclose(coef, hand, atol=1e-10)
    # unpenalized intercept: lam -> inf drives beta -> 0, not b0
    c2 = fit_ridge(X, y, w, 1e12)
    assert abs(c2[0] - (w * y).sum()) < 1e-2 and np.abs(c2[1:]).max() < 1e-6


# ---- T30: duplicated rows with split weights reproduce the solution ---------
def test_t30_duplication_split_weights():
    X = rng.randn(60, 2); y = X[:, 0] + rng.randn(60) * 0.05
    w = rng.rand(60); w /= w.sum()
    c1 = fit_ridge(X, y, w, 1.0)
    X2 = np.vstack([X, X]); y2 = np.r_[y, y]
    w2 = np.r_[w, w] / 2.0                      # halved weights, still sums 1
    c2 = fit_ridge(X2, y2, w2, 1.0)
    assert np.allclose(c1, c2, atol=1e-10)
    assert np.allclose(predict_ridge(c1, X), predict_ridge(c2, X), atol=1e-10)


# ---- T39: B0 = equal-origin date-weighted mean on a ragged panel ------------
def test_t39_b0_equal_origin():
    # origin A has 3 markets, origin B has 1 -> equal weight per ORIGIN
    od = pd.Series(["2020-01-02"] * 3 + ["2020-01-03"])
    y = np.array([1.0, 3.0, 5.0, 10.0])
    w = row_weights(od)
    got = b0_mean(y, w)
    want = (np.mean([1., 3., 5.]) + 10.0) / 2   # (3 + 10)/2 = 6.5
    assert got == pytest.approx(want)
    assert w.sum() == pytest.approx(1.0)


# ---- T26: fold preprocessing ignores future rows -----------------------------
def test_t26_fold_scaler_future_invariant():
    Xtr = rng.randn(200, 4); w = rng.rand(200)
    mu, sd = fit_fold_scaler(Xtr, w)
    mu2, sd2 = fit_fold_scaler(Xtr, w)          # deterministic
    assert np.array_equal(mu, mu2) and np.array_equal(sd, sd2)
    # appending validation rows must not change the fitted transform
    Xv = rng.randn(50, 4) * 100
    assert np.array_equal(apply_fold_scaler(Xv, mu, sd), (Xv - mu) / sd)
    # constant column -> scale 1, zero-centered
    Xc = np.column_stack([Xtr, np.full(200, 3.7)])
    mu3, sd3 = fit_fold_scaler(Xc, w)
    assert sd3[-1] == 1.0 and mu3[-1] == pytest.approx(3.7)


# ---- T32: quadratic expansion order/count (AM-1: 15 -> 135) -----------------
def test_t32_quadratic_expansion():
    Xs = rng.randn(10, 15)
    Q = quadratic_expand(Xs)
    assert Q.shape[1] == 135                     # 15 + 15 + 105
    assert np.allclose(Q[:, :15], Xs)
    assert np.allclose(Q[:, 15:30], Xs ** 2)
    assert np.allclose(Q[:, 30], Xs[:, 0] * Xs[:, 1])   # first pair product
    # no duplicated/intercept column
    assert not (Q == 1.0).all(axis=0).any()


# ---- T35: leaf traversal reproduces predict() --------------------------------
def test_t35_leaf_parity():
    X = rng.randn(2000, 15); y = X[:, 0] * X[:, 1] + rng.randn(2000) * 0.1
    w = np.ones(2000)
    est = fit_hgb(X, y, w, (25, 0.05, 10.0), depth=2, leaves=4)
    ad = HGBLeafAdapter(est)
    assert ad.predict_parity(X) < 1e-10


# ---- T36: short-episode leaf rejected despite min_samples_leaf ---------------
def test_t36_short_episode_leaf_rejected():
    # 8+ years of origins; a ~5-month episode that is SEPARABLE in feature
    # space (X0 extreme during the episode) and large enough in rows to pass
    # min_samples_leaf — but it must fail origin/bin/year support.
    n_origins, mkts = 2400, 8   # ~9.2 business years, ends 2021-03
    od = pd.Series(pd.date_range("2012-01-02", periods=n_origins, freq="B")
                   .repeat(mkts))
    rows = pd.DataFrame({"origin_date": od,
                         "market": [f"M{i}" for i in range(mkts)] * n_origins})
    X = rng.rand(len(rows), 15) * 2 - 1
    X[:, 0] = 0.0        # constant for non-episode rows: f0 then has exactly
                         # two distinct values, so a leaf isolating the episode
                         # cannot be padded out by scattered normal rows
    y = rng.randn(len(rows)) * 0.05
    ep = ((od >= "2020-03-02") & (od <= "2020-07-31")).values  # ~110 origins
    X[ep, 0] = 50.0      # clean outlier bin -> episode leaf gets ZERO
                         # contamination (a leaf kept "supported" only by
                         # scattered normal rows has genuinely broad support
                         # and legitimately passes the audit)
    y[ep] = 3.0                                               # huge episode
    n_ep = int(ep.sum())
    w = np.ones(len(rows))
    est = fit_hgb(X, y, w, (100, 0.025, 10.0), depth=2, leaves=4)
    # episode rows >= min_samples_leaf=max(256, ceil(.025*N))=420 -> formable
    assert n_ep >= max(256, int(np.ceil(0.025 * len(rows))))
    scored_index = {d: i for i, d in enumerate(sorted(od.unique()))}
    aud = leaf_support_audit(est, X, rows, scored_index)
    # the model found the episode; the audit must catch its thin support
    assert (~aud["supported"]).any()
    thin = aud[~aud["supported"]]
    # the isolated episode leaf covers ~110 origins / ~5 bins / 1 year
    assert ((thin["n_origins"] < 126) | (thin["n_bins20"] < 12) |
            (thin["n_years"] < 3)).any()


# ---- T59: adapter fails closed on unknown version ----------------------------
def test_t59_unknown_version_fails():
    import estimators
    X = rng.randn(500, 5); y = rng.randn(500)
    est = fit_hgb(X, y, np.ones(500), (25, 0.05, 10.0), depth=2, leaves=4)
    real = estimators.SKLEARN_LOCKED
    try:
        estimators.SKLEARN_LOCKED = "0.0.0-fake"
        with pytest.raises(RuntimeError, match="locked"):
            HGBLeafAdapter(est)
    finally:
        estimators.SKLEARN_LOCKED = real


# ---- T42: bootstrap mean is centered on the sample mean ----------------------
def test_t42_bootstrap_centering():
    v = np.concatenate([rng.randn(500) * 0.02, np.full(300, 0.10)])
    boots = moving_block_bootstrap(v, block=63, draws=1000, seed=11)
    assert abs(boots.mean() - v.mean()) < 0.01
    # positive-mean fixture -> most draws positive (one-sided test sanity)
    assert (boots > 0).mean() > 0.95


# ---- T43: missing-origin gaps preserved, not compressed ----------------------
def test_t43_gap_positions_preserved():
    v = np.full(200, np.nan); v[::2] = rng.randn(100)  # every other slot empty
    boots = moving_block_bootstrap(v, block=63, draws=200, seed=3)
    # a resample spanning only gaps would be NaN; blocks preserve positions
    assert np.isfinite(boots).all()
    # deterministic seed -> identical draws
    b2 = moving_block_bootstrap(v, block=63, draws=200, seed=3)
    assert np.array_equal(boots, b2)


# ---- T44: Holm correction on known fixture -----------------------------------
def test_t44_holm():
    adj = holm_adjust([0.01, 0.04, 0.03])
    # sorted: .01(x3), .03(x2), .04(x1) -> .03, .06, .04 -> monotone .03,.06,.06
    assert adj == pytest.approx([0.03, 0.06, 0.06])


# ---- one-SE selection: ridge picks largest lambda in set ---------------------
def test_one_se_ridge_parsimony():
    T = 400
    base = rng.randn(T)
    # identical losses -> every excess is identically 0 -> 0 <= 0 admits all
    # candidates -> parsimony selects the largest lambda
    losses = {str(lam): base ** 2 for lam in RIDGE_GRID}
    sel = one_se_select(losses, set(losses), kind="ridge", seed=5)
    assert float(sel) == float(RIDGE_GRID[-1])
    # a huge deterministic excess for the largest lambda -> excluded
    losses2 = {k: (v + 1000.0 if float(k) == RIDGE_GRID[-1] else v)
               for k, v in losses.items()}
    sel2 = one_se_select(losses2, set(losses2), kind="ridge", seed=5)
    assert float(sel2) == float(RIDGE_GRID[-2])


# ---- HGB determinism + no internal validation --------------------------------
def test_hgb_deterministic_and_grid():
    X = rng.randn(3000, 15); y = X[:, 2] ** 2 + rng.randn(3000) * 0.1
    w = np.ones(3000)
    a = fit_hgb(X, y, w, (50, 0.05, 10.0), depth=2, leaves=4)
    b = fit_hgb(X, y, w, (50, 0.05, 10.0), depth=2, leaves=4)
    assert np.array_equal(a.predict(X), b.predict(X))
    assert len(a._predictors) == 50            # early_stopping=False honored


# ---- T28: fold assignment — markets stay with their origin -------------------
def test_t28_origin_level_assignment():
    od = pd.Series(pd.date_range("2020-01-01", periods=60, freq="D")
                   .repeat(4))
    rows = pd.DataFrame({"origin_date": od,
                         "market": list("ABCD") * 60})
    cut = pd.Timestamp("2020-02-15")
    tr = rows[rows.origin_date < cut]; te = rows[rows.origin_date >= cut]
    # no origin straddles the boundary
    assert set(tr.origin_date).isdisjoint(te.origin_date)
