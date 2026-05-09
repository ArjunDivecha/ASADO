"""
=============================================================================
SCRIPT NAME: scripts/strategy/analogs/aggregate.py
=============================================================================

INPUT FILES:
- Data/strategy/analogs/v1/analog_matches.parquet — top-k analogs per date.
- Data/asado.duckdb :: country_returns_monthly      — 1MRet by (date, country).

OUTPUT FILES:
- Data/strategy/analogs/v1/signals.parquet          — long-format scores:
    (date, country, score, rank, n_analogs_with_data, model_version)

VERSION: 1.0
LAST UPDATED: 2026-04-19
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
For each (decision_date t, country c), score(c | t) is the SIMILARITY-WEIGHTED
MEDIAN of forward 1-month returns observed for c on each analog_date a.

Algorithm (PRD §6.4, user direction 2026-04-19):
  - For each analog_date a in the top-k for t, look up the realized 1MRet for c
    at the FORWARD date a + 1 month (i.e. the return earned the month after a).
  - Drop analogs that have no return for c (e.g. coverage gap).
  - Compute the weighted median over surviving analogs using softmax_weight
    as the weight; renormalize the surviving weights to sum to 1.
  - Rank countries within each date (1 = highest score).

PIT NOTE:
  We use the *forward 1-month* realized return at the analog date as the
  predictive sample. This is fine — these are historical returns, not future
  data relative to t.

DEPENDENCIES:
- pandas, numpy, duckdb, pyarrow

USAGE:
  python scripts/strategy/analogs/aggregate.py            # full run
  python scripts/strategy/analogs/aggregate.py --check    # summary only
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

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.strategy.analogs import config as C  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_matches() -> pd.DataFrame:
    df = pd.read_parquet(C.ANALOG_MATCHES_PARQUET)
    df["date"] = pd.to_datetime(df["date"])
    df["analog_date"] = pd.to_datetime(df["analog_date"])
    return df


def load_returns() -> pd.DataFrame:
    with duckdb.connect(str(C.DUCKDB_PATH), read_only=True) as con:
        df = con.execute(
            f"SELECT date, country, mtd_return_usd FROM {C.RETURNS_TABLE}"
        ).df()
    df["date"] = pd.to_datetime(df["date"])
    return df


def weighted_median(values: np.ndarray, weights: np.ndarray) -> float:
    """Lower weighted median: smallest x such that cumulative weight ≥ 0.5.

    Weights need not sum to 1; renormalized internally.
    """
    if len(values) == 0:
        return float("nan")
    order = np.argsort(values)
    v = values[order]
    w = weights[order]
    w_sum = w.sum()
    if w_sum <= 0:
        return float("nan")
    w = w / w_sum
    cum = np.cumsum(w)
    idx = int(np.searchsorted(cum, 0.5, side="left"))
    idx = min(idx, len(v) - 1)
    return float(v[idx])


def aggregate(matches: pd.DataFrame,
              returns: pd.DataFrame,
              countries: list[str],
              forward_months: int) -> pd.DataFrame:
    # forward date = analog_date + forward_months (using first-of-month convention).
    # Our country_returns_monthly is keyed by the realized-return month (e.g.
    # row 2008-10-01 = return EARNED during Oct 2008). The analog date is also
    # the realized-return date. So the "forward 1-month" sample for analog a
    # is the return observed at a + 1 month.
    matches = matches.copy()
    matches["forward_date"] = matches["analog_date"] + pd.DateOffset(months=forward_months)

    # Pivot returns to (date, country) for fast lookup.
    ret_wide = returns.pivot(index="date", columns="country", values="mtd_return_usd")

    rows = []
    for t, group in matches.groupby("date"):
        # Build per-country sample arrays.
        for country in countries:
            if country not in ret_wide.columns:
                rows.append({
                    "date": t, "country": country,
                    "score": float("nan"),
                    "n_analogs_with_data": 0,
                })
                continue
            forward_dates = group["forward_date"].values
            weights = group["softmax_weight"].values
            # Look up each forward date.
            samples = []
            kept_w = []
            for fd, w in zip(forward_dates, weights):
                if fd in ret_wide.index:
                    v = ret_wide.at[fd, country]
                    if pd.notna(v):
                        samples.append(float(v))
                        kept_w.append(float(w))
            if not samples:
                rows.append({
                    "date": t, "country": country,
                    "score": float("nan"),
                    "n_analogs_with_data": 0,
                })
                continue
            score = weighted_median(np.asarray(samples), np.asarray(kept_w))
            rows.append({
                "date": t, "country": country,
                "score": score,
                "n_analogs_with_data": len(samples),
            })

    out = pd.DataFrame(rows)
    out["date"] = pd.to_datetime(out["date"])
    # Rank within each date: 1 = highest score. NaN scores get NaN rank.
    out["rank"] = (
        out.groupby("date")["score"]
        .rank(method="min", ascending=False, na_option="bottom")
    )
    out["model_version"] = C.MODEL_VERSION
    return out


def summarize(df: pd.DataFrame) -> None:
    if df.empty:
        logger.info("signals: empty")
        return
    logger.info(
        "signals: %d rows, %d decision dates, %d countries",
        len(df), df["date"].nunique(), df["country"].nunique(),
    )
    nonan = df.dropna(subset=["score"])
    logger.info(
        "  score coverage: %.1f%% non-NaN (%d / %d)",
        100 * len(nonan) / max(len(df), 1), len(nonan), len(df),
    )
    if not nonan.empty:
        logger.info(
            "  score range: min=%.4f, median=%.4f, max=%.4f",
            nonan["score"].min(), nonan["score"].median(), nonan["score"].max(),
        )
    logger.info(
        "  decision range: %s → %s",
        df["date"].min().date(), df["date"].max().date(),
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="Summarize existing signals.parquet without rebuilding.")
    args = ap.parse_args()

    C.ensure_dirs()

    if args.check:
        df = pd.read_parquet(C.SIGNALS_PARQUET)
        df["date"] = pd.to_datetime(df["date"])
        summarize(df)
        return 0

    matches = load_matches()
    returns = load_returns()
    df = aggregate(matches, returns, C.T2_COUNTRIES, C.FORWARD_HORIZON_MONTHS)
    df.to_parquet(C.SIGNALS_PARQUET, index=False)
    logger.info("Wrote %s (%d rows)", C.SIGNALS_PARQUET, len(df))
    summarize(df)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
