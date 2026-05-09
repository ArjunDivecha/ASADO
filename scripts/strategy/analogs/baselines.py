"""
=============================================================================
SCRIPT NAME: scripts/strategy/analogs/baselines.py
=============================================================================

INPUT FILES:
- Data/asado.duckdb :: country_returns_monthly   — monthly MSCI USD price
                                                   returns by (date, country).

OUTPUT FILES:
- Data/strategy/analogs/v1/baselines.parquet     — one row per (date, model)
                                                   with monthly long return.

VERSION: 1.1
LAST UPDATED: 2026-04-19
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
Phase-0 benchmark for the World-State Analog strategy.

ONE BENCHMARK:
  equal_weight — long all 34 countries, equal-weighted, monthly rebalance.
                 Used to compute the analog strategy's *excess* return.

SUCCESS HURDLE (PRD §10, user direction 2026-04-19):
  analog_ann_return − equal_weight_ann_return ≥ 0.06   (gross, annualized)

DEPENDENCIES:
- duckdb, pandas, numpy, pyarrow

USAGE:
  python scripts/strategy/analogs/baselines.py            # full run
  python scripts/strategy/analogs/baselines.py --check    # summarize existing parquet
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


def load_returns(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    df = con.execute(
        f"SELECT date, country, mtd_return_usd FROM {C.RETURNS_TABLE}"
    ).df()
    df["date"] = pd.to_datetime(df["date"])
    return df


def make_decision_dates(returns: pd.DataFrame, start: str) -> pd.DatetimeIndex:
    """Realized-return dates t > start. We index by the row date in
    country_returns_monthly, which already represents the realized month
    following the decision."""
    all_dates = pd.DatetimeIndex(sorted(returns["date"].unique()))
    return all_dates[all_dates > pd.Timestamp(start)]


def run_equal_weight(returns: pd.DataFrame, decisions: pd.DatetimeIndex) -> pd.DataFrame:
    rows = []
    by_date = returns.groupby("date")["mtd_return_usd"]
    for t in decisions:
        if t not in by_date.groups:
            continue
        r = by_date.get_group(t).dropna()
        rows.append({
            "date": t,
            "model": "equal_weight",
            "return_gross": float(r.mean()),
            "n_names": int(len(r)),
        })
    return pd.DataFrame(rows)


def annualized_stats(series: pd.Series) -> dict[str, float]:
    s = series.dropna()
    if s.empty:
        return {"ann_return": float("nan"), "ann_vol": float("nan"),
                "sharpe": float("nan"), "n_months": 0}
    ann_ret = (1 + s).prod() ** (12 / len(s)) - 1
    ann_vol = s.std() * np.sqrt(12)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else float("nan")
    return {
        "ann_return": float(ann_ret),
        "ann_vol": float(ann_vol),
        "sharpe": float(sharpe),
        "n_months": int(len(s)),
    }


def summarize(df: pd.DataFrame) -> None:
    for model, sub in df.groupby("model"):
        stats = annualized_stats(sub.set_index("date")["return_gross"])
        logger.info(
            "%-22s | n=%3d | ann_ret=%6.2f%% | ann_vol=%6.2f%% | Sharpe=%5.2f",
            model, stats["n_months"], stats["ann_return"] * 100,
            stats["ann_vol"] * 100, stats["sharpe"],
        )
    ew_stats = annualized_stats(
        df[df["model"] == "equal_weight"].set_index("date")["return_gross"]
    )
    hurdle = ew_stats["ann_return"] + C.BENCHMARK_HURDLE_EXCESS_ANNUAL
    logger.info(
        "Hurdle for analog strategy: ann_return ≥ %.2f%% (= %.2f%% EW + %.2f%% excess)",
        hurdle * 100, ew_stats["ann_return"] * 100,
        C.BENCHMARK_HURDLE_EXCESS_ANNUAL * 100,
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="Summarize existing baselines.parquet without rebuilding.")
    args = ap.parse_args()

    C.ensure_dirs()

    if args.check:
        df = pd.read_parquet(C.BASELINES_PARQUET)
        df["date"] = pd.to_datetime(df["date"])
        summarize(df)
        return 0

    with duckdb.connect(str(C.DUCKDB_PATH), read_only=True) as con:
        returns = load_returns(con)

    decisions = make_decision_dates(returns, C.BACKTEST_START)
    logger.info(
        "Decision dates: %d (%s → %s)",
        len(decisions), decisions[0].date(), decisions[-1].date(),
    )

    ew = run_equal_weight(returns, decisions)
    ew["date"] = pd.to_datetime(ew["date"])
    ew.to_parquet(C.BASELINES_PARQUET, index=False)
    logger.info("Wrote %s (%d rows)", C.BASELINES_PARQUET, len(ew))

    summarize(ew)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
