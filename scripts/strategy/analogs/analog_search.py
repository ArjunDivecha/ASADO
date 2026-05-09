"""
=============================================================================
SCRIPT NAME: scripts/strategy/analogs/analog_search.py
=============================================================================

INPUT FILES:
- Data/strategy/analogs/v1/worldstates.parquet    — PCA-reduced worldstate
                                                    vectors per date.

OUTPUT FILES:
- Data/strategy/analogs/v1/analog_matches.parquet — top-k analog dates per
                                                    decision date with weights.

VERSION: 1.0
LAST UPDATED: 2026-04-19
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
For each decision date t (>= BACKTEST_START), search the analog library
{worldstate_{t'} : t' < t − MIN_LAG_MONTHS} for the top-K nearest neighbours
under cosine similarity. Convert similarities to softmax weights at temperature
SOFTMAX_TAU.

Output schema (one row per (date, analog_date)):
  date              DATE        — decision date t
  analog_date       DATE        — historical date selected as analog
  cosine_similarity DOUBLE      — raw cosine similarity in [-1, 1]
  softmax_weight    DOUBLE      — normalized softmax weight, sums to 1 within t
  rank_in_topk      INTEGER     — 1 = closest

PIT DISCIPLINE:
  Two worldstates compared at decision t may have different PCA dimensions.
  We project both into the *intersection dimensions* (i.e., truncate each
  vector to min(n_t, n_t')). This is conservative — uses only components
  both vectors share. A future phase may replace this with a single global
  embedding refit at t.

DEPENDENCIES:
- pandas, numpy, pyarrow

USAGE:
  python scripts/strategy/analogs/analog_search.py            # full run
  python scripts/strategy/analogs/analog_search.py --check    # summary only
=============================================================================
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.strategy.analogs import config as C  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_worldstates() -> pd.DataFrame:
    df = pd.read_parquet(C.WORLDSTATES_PARQUET)
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["n_components"] > 0].copy()
    df["vector"] = df["vector"].apply(lambda lst: np.asarray(lst, dtype=np.float64))
    df = df.sort_values("date").reset_index(drop=True)
    return df


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    n = min(len(a), len(b))
    if n == 0:
        return 0.0
    av, bv = a[:n], b[:n]
    na = float(np.linalg.norm(av))
    nb = float(np.linalg.norm(bv))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(av, bv) / (na * nb))


def softmax(values: np.ndarray, tau: float) -> np.ndarray:
    z = values / max(tau, 1e-12)
    z = z - z.max()  # numerical stability
    e = np.exp(z)
    return e / e.sum()


def search(world: pd.DataFrame,
           backtest_start: pd.Timestamp,
           min_lag_months: int,
           k: int,
           tau: float) -> pd.DataFrame:
    decisions = world[world["date"] >= backtest_start].copy()
    if decisions.empty:
        return pd.DataFrame(columns=[
            "date", "analog_date", "cosine_similarity",
            "softmax_weight", "rank_in_topk",
        ])

    rows: list[dict] = []
    for _, row in decisions.iterrows():
        t = row["date"]
        cutoff = t - pd.DateOffset(months=min_lag_months)
        library = world[world["date"] < cutoff]
        if len(library) < k:
            logger.warning("Library too thin at %s (%d < k=%d) — skipping",
                           t.date(), len(library), k)
            continue
        sims = np.array([cosine(row["vector"], v) for v in library["vector"].values])
        order = np.argsort(-sims)[:k]
        top_dates = library.iloc[order]["date"].values
        top_sims = sims[order]
        top_weights = softmax(top_sims, tau)
        for rank, (ad, sim, w) in enumerate(zip(top_dates, top_sims, top_weights), start=1):
            rows.append({
                "date": t,
                "analog_date": pd.Timestamp(ad),
                "cosine_similarity": float(sim),
                "softmax_weight": float(w),
                "rank_in_topk": rank,
            })

    out = pd.DataFrame(rows)
    out["date"] = pd.to_datetime(out["date"])
    out["analog_date"] = pd.to_datetime(out["analog_date"])
    return out


def summarize(df: pd.DataFrame) -> None:
    if df.empty:
        logger.info("analog_matches: empty")
        return
    by_date = df.groupby("date")
    logger.info(
        "analog_matches: %d decisions, k_per_decision=%d (median)",
        df["date"].nunique(),
        int(by_date.size().median()),
    )
    logger.info(
        "  similarity range: min=%.3f, median=%.3f, max=%.3f",
        df["cosine_similarity"].min(),
        df["cosine_similarity"].median(),
        df["cosine_similarity"].max(),
    )
    earliest = df["date"].min()
    latest = df["date"].max()
    logger.info("  decision range: %s → %s", earliest.date(), latest.date())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="Summarize existing analog_matches.parquet without rebuilding.")
    args = ap.parse_args()

    C.ensure_dirs()

    if args.check:
        df = pd.read_parquet(C.ANALOG_MATCHES_PARQUET)
        df["date"] = pd.to_datetime(df["date"])
        summarize(df)
        return 0

    world = load_worldstates()
    df = search(
        world,
        backtest_start=pd.Timestamp(C.BACKTEST_START),
        min_lag_months=C.MIN_LAG_MONTHS,
        k=C.K_ANALOGS,
        tau=C.SOFTMAX_TAU,
    )
    df.to_parquet(C.ANALOG_MATCHES_PARQUET, index=False)
    logger.info("Wrote %s (%d rows)", C.ANALOG_MATCHES_PARQUET, len(df))
    summarize(df)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
