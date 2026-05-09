"""
=============================================================================
SCRIPT NAME: scripts/strategy/analogs/build_worldstate.py
=============================================================================

INPUT FILES:
- Data/asado.duckdb :: feature_panel              — normalized factor panel.
- Data/strategy/analogs/v1/pit_audit.csv          — variable PIT-safety flags.

OUTPUT FILES:
- Data/strategy/analogs/v1/worldstates.parquet    — one row per decision date
                                                    with PCA-reduced world-state
                                                    vector + metadata.

VERSION: 1.0
LAST UPDATED: 2026-04-19
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
For every month-end t in the analog library, build a single high-dimensional
world-state vector that summarizes the joint state of the 34-country system.

Per PRD §6.1, at each t:
  1. Pull all (date, country, value, variable) rows from feature_panel where
     date <= t and variable ends in '_CS' (cross-sectional z-scores).
  2. Restrict to variables flagged vintage_safe in pit_audit.csv.
  3. Time-varying feature set: keep variable v only if it has ≥ 60 monthly
     non-null observations strictly BEFORE t (so the inclusion criterion does
     not peek at t itself).
  4. Pivot to a (country × variable) matrix at date t. Missing cells filled
     with 0 (cross-sectional z-scores have mean 0 by construction).
  5. Flatten to a vector of length n_features_t * 34 (rows ordered by the
     fixed C.T2_COUNTRIES list).
  6. Standardize (zero mean, unit variance) using the *flat* vectors of all
     dates strictly < t.
  7. PCA fit on { worldstate_{t'} : t' < t }, retain enough components to
     explain ≥ 80% of variance, capped at 30. Project worldstate_t.
  8. Persist (date, n_features, n_components, vec[0..n-1]) to parquet.

PIT DISCIPLINE:
  Every PCA fit and every scaler fit at t uses ONLY data with date strictly
  less than t. There is NO global fit. This is enforced by recomputing scaler
  + PCA at each t against a growing prefix of the flat-vector matrix.

DETERMINISM:
  numpy + sklearn random seed = 42. Output is byte-identical across runs
  given the same input DuckDB.

DEPENDENCIES:
- duckdb, pandas, numpy, scikit-learn, pyarrow

USAGE:
  python scripts/strategy/analogs/build_worldstate.py            # full build
  python scripts/strategy/analogs/build_worldstate.py --check    # summary only

NOTES:
- Universe of dates: every month-end present in feature_panel from 2000-01
  through the latest date with feature data. Decision dates for the backtest
  start at C.BACKTEST_START (2008-01-31) — but worldstates are precomputed
  for ALL eligible dates from 2000-01 onward, since they form the analog
  library that grows over time.
- This step is the slowest stage (PCA refit per date). Cached by date so a
  rerun is fast for unchanged dates.
=============================================================================
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.strategy.analogs import config as C  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

np.random.seed(C.RANDOM_SEED)


# -----------------------------------------------------------------------------
# Loaders
# -----------------------------------------------------------------------------
def load_pit_safe_variables() -> list[str]:
    pit = pd.read_csv(C.PIT_AUDIT_CSV)
    return pit.loc[pit["vintage_safe"], "variable"].unique().tolist()


def load_feature_long(con: duckdb.DuckDBPyConnection,
                      variables: list[str]) -> pd.DataFrame:
    """Pull the entire usable history of feature_panel for the safe variables."""
    placeholders = ",".join(["?"] * len(variables))
    sql = f"""
        SELECT date, country, variable, value
        FROM feature_panel
        WHERE variable IN ({placeholders})
          AND value IS NOT NULL
    """
    df = con.execute(sql, variables).df()
    df["date"] = pd.to_datetime(df["date"])
    # Restrict to T2 universe only — feature_panel may include extra countries.
    df = df[df["country"].isin(C.T2_COUNTRIES)].copy()
    # Sanitize: a few _CS commodity series carry inf (degenerate cross-sections).
    # Treat as missing → handled by the 0-fill at pivot time.
    n_inf = int(np.isinf(df["value"]).sum())
    if n_inf:
        logger.warning("Replacing %d inf values with NaN", n_inf)
        df.loc[np.isinf(df["value"]), "value"] = np.nan
        df = df.dropna(subset=["value"])
    return df


# -----------------------------------------------------------------------------
# Per-date world-state builder
# -----------------------------------------------------------------------------
def eligible_variables_at(date_to_obs_count: dict[str, pd.Series],
                          t: pd.Timestamp,
                          min_history: int) -> list[str]:
    """Variables whose count of distinct dates with data strictly < t is ≥ min."""
    eligible: list[str] = []
    for var, dates in date_to_obs_count.items():
        n = int((dates < t).sum())
        if n >= min_history:
            eligible.append(var)
    return sorted(eligible)


def cross_section_at(panel: pd.DataFrame,
                     t: pd.Timestamp,
                     variables: list[str]) -> np.ndarray:
    """Return a flat vector of length len(variables) * 34 for date t.

    Layout: variable-major then country-minor, so block i corresponds to
    variable variables[i] across all 34 T2_COUNTRIES in fixed order.
    Missing cells (variable v missing for country c at date t) are filled 0.
    """
    snap = panel[panel["date"] == t]
    if snap.empty:
        return np.zeros(len(variables) * len(C.T2_COUNTRIES), dtype=np.float64)
    wide = (
        snap.pivot_table(index="country", columns="variable", values="value", aggfunc="mean")
        .reindex(index=C.T2_COUNTRIES, columns=variables)
        .fillna(0.0)
    )
    # Flatten variable-major: vec = [v0_c0, v0_c1, ..., v0_c33, v1_c0, ...]
    return wide.to_numpy().T.reshape(-1)


def build() -> pd.DataFrame:
    safe_vars = [v for v in load_pit_safe_variables() if v.endswith(C.FEATURE_PREFIX)]
    logger.info("PIT-safe %s variables: %d", C.FEATURE_PREFIX, len(safe_vars))

    with duckdb.connect(str(C.DUCKDB_PATH), read_only=True) as con:
        long = load_feature_long(con, safe_vars)
    logger.info("feature_panel rows loaded: %d", len(long))

    # Pre-compute per-variable date sets, used for eligibility lookups
    var_dates: dict[str, pd.Series] = {
        v: pd.Series(sorted(g["date"].unique()))
        for v, g in long.groupby("variable")
    }

    all_dates = pd.DatetimeIndex(sorted(long["date"].unique()))
    logger.info("Date universe: %d months (%s → %s)",
                len(all_dates), all_dates.min().date(), all_dates.max().date())

    flat_records: list[dict] = []
    flat_matrix: list[np.ndarray] = []  # rows = past worldstates (raw flat vectors)
    eligible_history: list[list[str]] = []

    # Cache pivots per date for speed; iterate in chronological order.
    for t in all_dates:
        eligible = eligible_variables_at(
            var_dates, t, C.MIN_FEATURE_HISTORY_MONTHS
        )
        if len(eligible) < 5:
            # Too few features to form a meaningful state; skip.
            flat_records.append({"date": t, "skipped": True, "n_features": len(eligible)})
            flat_matrix.append(None)
            eligible_history.append(eligible)
            continue

        flat_t = cross_section_at(long, t, eligible)
        flat_matrix.append(flat_t)
        eligible_history.append(eligible)
        flat_records.append({"date": t, "skipped": False, "n_features": len(eligible)})

    # Now compute PCA-reduced worldstate at each date using prior dates only
    rows: list[dict] = []
    history_vectors: list[np.ndarray] = []   # raw flat vectors of past dates with same dim
    history_dims: list[int] = []             # corresponding dims

    for i, t in enumerate(all_dates):
        rec = flat_records[i]
        if rec["skipped"]:
            continue
        flat_t = flat_matrix[i]
        n_features_t = rec["n_features"]
        dim_t = len(flat_t)

        # Build the past-only history matrix of vectors that match this dim_t.
        # Variable set varies over time, so dimensions can differ; we re-project
        # past vectors onto the current variable layout for fitting.
        past_flat: list[np.ndarray] = []
        for j in range(i):
            if flat_records[j]["skipped"]:
                continue
            past_flat.append(_reproject_to_current(
                flat_matrix[j], eligible_history[j], eligible_history[i]
            ))
        if len(past_flat) < 24:
            # Need a meaningful history before we can fit a scaler/PCA.
            rows.append({
                "date": t, "n_features": n_features_t, "n_components": 0,
                "vector": np.zeros(0, dtype=np.float64),
            })
            continue

        X_prior = np.vstack(past_flat)
        scaler = StandardScaler(with_mean=True, with_std=True)
        X_prior_scaled = scaler.fit_transform(X_prior)

        # Cap components at min(samples, features, max).
        max_components = min(C.PCA_MAX_COMPONENTS, X_prior_scaled.shape[0],
                             X_prior_scaled.shape[1])
        pca = PCA(n_components=max_components, random_state=C.RANDOM_SEED)
        pca.fit(X_prior_scaled)
        cum = np.cumsum(pca.explained_variance_ratio_)
        n_keep = int(np.searchsorted(cum, C.PCA_VARIANCE_TARGET) + 1)
        n_keep = max(1, min(n_keep, max_components))

        flat_t_scaled = scaler.transform(flat_t.reshape(1, -1))
        z = pca.transform(flat_t_scaled)[0, :n_keep]

        rows.append({
            "date": t, "n_features": n_features_t, "n_components": int(n_keep),
            "vector": z.astype(np.float64),
        })

        if (i % 50) == 0 or i == len(all_dates) - 1:
            logger.info(
                "  built worldstate %s | n_feat=%d | n_comp=%d | hist=%d",
                t.date(), n_features_t, n_keep, len(past_flat),
            )

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _reproject_to_current(past_vec: np.ndarray,
                          past_vars: list[str],
                          curr_vars: list[str]) -> np.ndarray:
    """Re-project a past flat vector onto the current variable layout.

    Past vector layout: variable-major over past_vars × T2_COUNTRIES.
    Output layout: variable-major over curr_vars × T2_COUNTRIES with 0 in
    variable blocks present today but absent in the past observation.
    """
    n_countries = len(C.T2_COUNTRIES)
    past_blocks = past_vec.reshape(len(past_vars), n_countries)
    past_index = {v: idx for idx, v in enumerate(past_vars)}
    out = np.zeros((len(curr_vars), n_countries), dtype=np.float64)
    for j, v in enumerate(curr_vars):
        if v in past_index:
            out[j] = past_blocks[past_index[v]]
    return out.reshape(-1)


# -----------------------------------------------------------------------------
# Persistence
# -----------------------------------------------------------------------------
def persist(df: pd.DataFrame) -> None:
    """Persist as a parquet with one column per PCA dim (variable-width handled
    by storing as a list of floats)."""
    out = df.copy()
    out["n_components"] = out["n_components"].astype(int)
    out["n_features"] = out["n_features"].astype(int)
    # Convert numpy arrays to lists for parquet portability.
    out["vector"] = out["vector"].apply(lambda a: a.tolist() if hasattr(a, "tolist") else list(a))
    out.to_parquet(C.WORLDSTATES_PARQUET, index=False)
    logger.info("Wrote %s (%d rows)", C.WORLDSTATES_PARQUET, len(out))


def summarize() -> None:
    df = pd.read_parquet(C.WORLDSTATES_PARQUET)
    df["date"] = pd.to_datetime(df["date"])
    logger.info("Worldstates: %d dates, %s → %s",
                len(df), df["date"].min().date(), df["date"].max().date())
    nz = df[df["n_components"] > 0]
    logger.info("With non-empty PCA: %d dates", len(nz))
    if len(nz):
        logger.info(
            "n_features: mean=%.1f, min=%d, max=%d",
            nz["n_features"].mean(), nz["n_features"].min(), nz["n_features"].max(),
        )
        logger.info(
            "n_components: mean=%.1f, min=%d, max=%d",
            nz["n_components"].mean(), nz["n_components"].min(), nz["n_components"].max(),
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="Summarize existing worldstates.parquet without rebuilding.")
    args = ap.parse_args()

    C.ensure_dirs()

    if args.check:
        summarize()
        return 0

    df = build()
    persist(df)
    summarize()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
