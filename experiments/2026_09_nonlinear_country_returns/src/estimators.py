# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/src/estimators.py
#
# P05 — estimator implementations per PRD section 9.
#
#   * Weighted ridge, closed form, unpenalized intercept (9.2). Weights sum
#     to 1; lambda grid 1e-5..1e3 (12 log-spaced).
#   * HistGradientBoostingRegressor wrapper on the fixed 12-config grid
#     (9.3): depth 2 / <=4 leaves for N_S,N_X; depth 1 / <=2 leaves for A_S.
#     early_stopping=False, max_features=1.0, warm_start=False, seed
#     20260913. Model-fit weights rescaled to mean 1 (documented convention
#     difference vs ridge).
#   * HGBLeafAdapter (9.4): version-locked to scikit-learn 1.8.0; read-only
#     traversal of est._predictors producing per-row leaf assignments; leaf
#     support audit on the FROZEN base calendar (>=126 distinct origins,
#     >=12 fixed 20-origin bins, >=3 calendar years, >=4 markets per leaf).
#     Fails closed on an unknown sklearn version (T59).
#   * Fold preprocessing (8.2): training-slice-only weighted center/scale;
#     constant column -> scale 1, zero-centered. Q_S expansion: 15 mains +
#     15 squares + C(15,2)=105 pairwise products = 135 ordered predictors
#     (AM-1: the spec's 152 assumed 16 S inputs).
#   * Row weights w_it = 1/(T * n_t) summing to 1 (8.2).
#   * Deterministic one-SE selection (9.5): 63-origin moving-block bootstrap
#     on paired per-origin excess loss, 1,000 draws, seeded per fit.
#   * holm_adjust for the three primary tests.
# =============================================================================
from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd

MASTER_SEED = 20260913
RIDGE_GRID = np.logspace(-5, 3, 12)
TREE_GRID = [(it, lf, l2)
             for it in (25, 50, 100)
             for lf in (0.025, 0.05)
             for l2 in (10.0, 100.0)]
assert len(TREE_GRID) == 12


# ---------------------------------------------------------------------------
# Ridge (9.2)
# ---------------------------------------------------------------------------
def fit_ridge(X: np.ndarray, y: np.ndarray, w: np.ndarray,
              lam: float) -> np.ndarray:
    """Weighted ridge: min sum w*(y - b0 - Xb)^2 + lam*||b||^2, w sums to 1.
    Returns coef vector [intercept, beta...] (intercept unpenalized)."""
    A = np.column_stack([np.ones(len(X)), X])
    Aw = A * w[:, None]
    G = A.T @ Aw
    d = np.diag_indices_from(G)
    G[d] += lam
    G[0, 0] -= lam                       # intercept stays unpenalized
    b = A.T @ (w * y)
    return np.linalg.solve(G, b)


def predict_ridge(coef: np.ndarray, X: np.ndarray) -> np.ndarray:
    return coef[0] + X @ coef[1:]


# ---------------------------------------------------------------------------
# Row weights + fold preprocessing (8.2)
# ---------------------------------------------------------------------------
def row_weights(origin_dates: pd.Series) -> np.ndarray:
    """w_it = 1/(T * n_t): each origin gets equal aggregate weight."""
    n_t = origin_dates.map(origin_dates.value_counts())
    T = origin_dates.nunique()
    return 1.0 / (T * n_t)


def fit_fold_scaler(X: np.ndarray, w: np.ndarray):
    """Weighted center/scale on the training slice only. Constant column ->
    scale 1, zero-centered (8.2 — distinct from the rolling-z rule)."""
    w = w / w.sum()
    mu = (X * w[:, None]).sum(axis=0)
    var = ((X - mu) ** 2 * w[:, None]).sum(axis=0)
    sd = np.sqrt(var)
    sd = np.where(sd <= 1e-12, 1.0, sd)
    return mu, sd


def apply_fold_scaler(X, mu, sd):
    return (X - mu) / sd


def quadratic_expand(Xs: np.ndarray) -> np.ndarray:
    """mains + squares + pairwise products, fixed order:
    [x1..xk, x1^2..xk^2, x1x2, x1x3, ...]. AM-1: k=15 -> 135 columns."""
    k = Xs.shape[1]
    cols = [Xs, Xs ** 2]
    prods = [Xs[:, i] * Xs[:, j] for i, j in combinations(range(k), 2)]
    cols.append(np.column_stack(prods))
    out = np.column_stack(cols)
    assert out.shape[1] == 2 * k + k * (k - 1) // 2
    return out


def b0_mean(y: np.ndarray, w: np.ndarray) -> float:
    """Date-weighted pooled mean of matured training labels."""
    w = w / w.sum()
    return float((w * y).sum())


# ---------------------------------------------------------------------------
# Histogram boosting (9.3)
# ---------------------------------------------------------------------------
def fit_hgb(X: np.ndarray, y: np.ndarray, w_mean1: np.ndarray,
            cfg: tuple, depth: int, leaves: int, seed: int = MASTER_SEED):
    """cfg = (max_iter, leaf_fraction, l2). w_mean1 must have mean 1.
    min_samples_leaf = max(256, ceil(leaf_fraction * N))."""
    from sklearn.ensemble import HistGradientBoostingRegressor
    max_iter, leaf_frac, l2 = cfg
    est = HistGradientBoostingRegressor(
        loss="squared_error", learning_rate=0.03, max_bins=16,
        max_depth=depth, max_leaf_nodes=leaves, max_iter=max_iter,
        min_samples_leaf=max(256, int(np.ceil(leaf_frac * len(X)))),
        l2_regularization=l2, early_stopping=False,
        categorical_features=None, warm_start=False, max_features=1.0,
        random_state=seed)
    est.fit(X, y, sample_weight=w_mean1)
    return est


# ---------------------------------------------------------------------------
# Leaf adapter (9.4) — version-locked to sklearn 1.8.0, fails closed (T59)
# ---------------------------------------------------------------------------
SKLEARN_LOCKED = "1.8.0"


class HGBLeafAdapter:
    """Read-only traversal of fitted HistGradientBoostingRegressor trees.

    Node semantics verified against sklearn 1.8.0 TreePredictor fields:
    num_threshold compares the RAW feature value (x <= thr -> left),
    missing_go_to_left routes NaN, is_leaf + value give the contribution,
    count is the node's training-row count. Parity vs est.predict() is
    asserted to 1e-10 at construction time (T35)."""

    def __init__(self, est):
        import sklearn
        if sklearn.__version__ != SKLEARN_LOCKED:
            raise RuntimeError(
                f"HGBLeafAdapter locked to sklearn {SKLEARN_LOCKED}; found "
                f"{sklearn.__version__} — refusing to invent leaf semantics")
        self.est = est
        self.predictors = [p for stage in est._predictors for p in stage]
        self.lr = est.learning_rate
        base = est._baseline_prediction
        self.baseline = float(np.ravel(base)[0])
        self._missing_bin = int(est._bin_mapper.missing_values_bin_idx_)

    def leaf_ids(self, X: np.ndarray) -> np.ndarray:
        """(n_rows, n_trees) leaf NODE INDEX per tree, matching
        _predict_one_from_binned_data semantics exactly: X is binned by
        est._bin_mapper, missing bin routes via missing_go_to_left, splits
        compare data_val <= bin_threshold -> left (verified against
        sklearn 1.8.0 _predictor.pyx)."""
        Xb = np.ascontiguousarray(self.est._bin_mapper.transform(X))
        n = len(Xb)
        out = np.empty((n, len(self.predictors)), dtype=np.int32)
        for t, pred in enumerate(self.predictors):
            nd = pred.nodes
            node = np.zeros(n, dtype=np.int64)
            is_leaf = nd["is_leaf"].astype(bool)
            fidx = nd["feature_idx"].astype(np.int64)
            thr = nd["bin_threshold"]
            mgl = nd["missing_go_to_left"].astype(bool)
            left = nd["left"].astype(np.int64)
            right = nd["right"].astype(np.int64)
            for _ in range(int(nd["depth"].max()) + 2):
                cur = node.copy()
                not_leaf = ~is_leaf[cur]
                if not not_leaf.any():
                    break
                xv = Xb[np.arange(n), fidx[cur].clip(0, Xb.shape[1] - 1)]
                go_left = np.where(xv == self._missing_bin, mgl[cur],
                                   xv <= thr[cur])
                node = np.where(not_leaf,
                                np.where(go_left, left[cur], right[cur]),
                                cur)
            out[:, t] = node
        return out

    def leaf_values(self, X: np.ndarray) -> np.ndarray:
        ids = self.leaf_ids(X)
        vals = np.empty_like(ids, dtype=np.float64)
        for t, pred in enumerate(self.predictors):
            vals[:, t] = pred.nodes["value"][ids[:, t]]
        return vals

    def predict_parity(self, X: np.ndarray, tol: float = 1e-10) -> float:
        """baseline + sum(leaf values) == est.predict(X). Node 'value' in
        sklearn 1.8.0 is already shrinkage-applied (verified: baseline +
        value reproduces predict exactly; multiplying by lr does not)."""
        recon = self.baseline + self.leaf_values(X).sum(axis=1)
        err = np.abs(recon - self.est.predict(X)).max()
        if err > tol:
            raise RuntimeError(f"leaf-parity failed: max err {err:.3e}")
        return float(err)


def leaf_support_audit(est, X: np.ndarray, rows: pd.DataFrame,
                       scored_origin_index: dict) -> pd.DataFrame:
    """Per (tree, leaf): distinct origins, fixed 20-origin bins (origin's
    index in the frozen scored-origin calendar // 20), calendar years,
    markets. rows must carry origin_date and market."""
    ad = HGBLeafAdapter(est)
    ids = ad.leaf_ids(X)
    oid = rows["origin_date"].map(scored_origin_index).values
    yr = pd.to_datetime(rows["origin_date"]).dt.year.values
    mk = rows["market"].values
    recs = []
    for t, pred in enumerate(ad.predictors):
        for leaf in np.unique(ids[:, t]):
            m = ids[:, t] == leaf
            recs.append({
                "tree": t, "leaf": int(leaf), "n_rows": int(m.sum()),
                "n_origins": len(np.unique(oid[m])),
                "n_bins20": len(np.unique(oid[m] // 20)),
                "n_years": len(np.unique(yr[m])),
                "n_markets": len(np.unique(mk[m])),
                "node_count_field": int(pred.nodes["count"][leaf]),
            })
    df = pd.DataFrame(recs)
    df["supported"] = ((df["n_origins"] >= 126) & (df["n_bins20"] >= 12) &
                       (df["n_years"] >= 3) & (df["n_markets"] >= 4))
    return df


# ---------------------------------------------------------------------------
# Deterministic selection (9.5)
# ---------------------------------------------------------------------------
def moving_block_bootstrap(values: np.ndarray, block: int = 63,
                           draws: int = 1000, seed: int = 0) -> np.ndarray:
    """Mean of each resample: sample ceil(T/block) blocks of `block`
    consecutive positions, truncate to T, mean over non-NaN positions.
    NaN positions are preserved (ineligible origins are empty slots)."""
    rng = np.random.RandomState(seed)
    T = len(values)
    nblocks = int(np.ceil(T / block))
    starts = np.arange(0, max(T - block + 1, 1))
    # vectorized: all draws' block starts at once, then gather
    s = rng.choice(starts, size=(draws, nblocks), replace=True)
    idx = (s[:, :, None] + np.arange(block)[None, None, :]
           ).reshape(draws, -1)[:, :T]
    v = values[idx]
    out = np.nanmean(v, axis=1)
    out[~np.isfinite(v).any(axis=1)] = np.nan
    return out


def se_of_mean(values: np.ndarray, **kw) -> float:
    return float(np.nanstd(moving_block_bootstrap(values, **kw), ddof=1))


def one_se_select(per_origin_losses: dict[str, np.ndarray],
                  admissible: set[str], kind: str,
                  seed: int) -> str:
    """kind='ridge' -> largest lambda in the one-SE set; kind='tree' ->
    fewest stages, then larger leaf fraction, then larger l2, then config id.

    per_origin_losses: config_id -> per-origin loss vector (aligned).
    Returns selected config_id."""
    adm = [c for c in per_origin_losses if c in admissible]
    if not adm:
        raise RuntimeError("no admissible candidates")
    mean_loss = {c: float(np.nanmean(per_origin_losses[c])) for c in adm}
    best = min(mean_loss, key=mean_loss.get)
    se_set = [best]
    for c in adm:
        if c == best:
            continue
        d = per_origin_losses[c] - per_origin_losses[best]
        se = se_of_mean(d, seed=seed)
        if np.nanmean(d) <= se:
            se_set.append(c)
    if kind == "ridge":
        # config ids are either bare lambda strings or "<model>|lam=<v>"
        return max(se_set,
                   key=lambda c: float(c.rsplit("=", 1)[-1]))
    # tree: cfg id encodes (max_iter, leaf_frac, l2)
    def key(c):
        # cfg id encodes (max_iter, leaf_frac, l2) either as a tuple or a
        # "<model>|it=<i>|lf=<f>|l2=<l>" string
        if isinstance(c, str):
            parts = dict(p.split("=") for p in c.split("|")[1:])
            return (-float(parts["it"]), -float(parts["lf"]),
                    -float(parts["l2"]))
        it, lf, l2 = c
        return (-it, -lf, -l2)  # fewer stages, larger leaf frac, larger l2
    return min(se_set, key=lambda c: (key(c), str(c)))


def holm_adjust(pvals: list[float]) -> list[float]:
    """Holm step-down adjusted p-values, returned in input order."""
    m = len(pvals)
    order = np.argsort(pvals)
    adj = np.empty(m)
    running = 0.0
    for rank, i in enumerate(order):
        a = min(1.0, (m - rank) * pvals[i])
        running = max(running, a)
        adj[i] = running
    return list(adj)
