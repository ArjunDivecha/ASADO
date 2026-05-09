"""
=============================================================================
SCRIPT NAME: scripts/strategy/analogs/backtest.py
=============================================================================

INPUT FILES:
- Data/strategy/analogs/v1/signals.parquet         — score per (date, country).
- Data/asado.duckdb :: country_returns_monthly      — 1MRet by (date, country).

OUTPUT FILES:
- Data/strategy/analogs/v1/backtest.parquet         — one row per realized
    month with portfolio metrics:
      realized_date, signal_date, model, n_holdings, names (list),
      weight_per_name, return_gross, turnover, model_version

VERSION: 1.0
LAST UPDATED: 2026-04-19
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
Long-only walk-forward backtest of the World-State Analog strategy v1.

Decision rule (PRD §6.5, user direction 2026-04-19):
  At signal_date t, pick the TOP_N (=7) countries by analog score, equal-weight
  long, hold for one month. Realized return is the simple average of 1MRet at
  realized_date = t + 1 month, restricted to countries that have a return that
  month.

Convention:
  - signal_date t comes from signals.parquet (worldstate-built date)
  - realized_date r = t + 1 month, matches a row in country_returns_monthly
    where row 2026-03-01 = return earned during March 2026 (per user 2026-04-19)
  - Costs are OUT OF SCOPE; turnover is logged for a future cost layer

DEPENDENCIES:
- pandas, numpy, duckdb, pyarrow

USAGE:
  python scripts/strategy/analogs/backtest.py            # full run
  python scripts/strategy/analogs/backtest.py --check    # summary only
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


def load_signals() -> pd.DataFrame:
    df = pd.read_parquet(C.SIGNALS_PARQUET)
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_returns() -> pd.DataFrame:
    with duckdb.connect(str(C.DUCKDB_PATH), read_only=True) as con:
        df = con.execute(
            f"SELECT date, country, mtd_return_usd FROM {C.RETURNS_TABLE}"
        ).df()
    df["date"] = pd.to_datetime(df["date"])
    return df


def select_top_n(group: pd.DataFrame, n: int) -> list[str]:
    """Pick the top-n countries by score, dropping NaN scores."""
    g = group.dropna(subset=["score"]).sort_values(
        ["score", "country"], ascending=[False, True]
    )
    return g["country"].head(n).tolist()


def run_long_only(signals: pd.DataFrame,
                  returns: pd.DataFrame,
                  top_n: int,
                  forward_months: int) -> pd.DataFrame:
    ret_wide = returns.pivot(index="date", columns="country", values="mtd_return_usd")

    rows = []
    prev_holdings: set[str] = set()
    for signal_date, group in signals.groupby("date"):
        realized_date = signal_date + pd.DateOffset(months=forward_months)
        if realized_date not in ret_wide.index:
            continue
        names = select_top_n(group, top_n)
        if not names:
            continue
        # Restrict to countries with a realized return this month.
        avail = [c for c in names if c in ret_wide.columns
                 and pd.notna(ret_wide.at[realized_date, c])]
        if not avail:
            continue
        rets = np.array([ret_wide.at[realized_date, c] for c in avail])
        ret_gross = float(rets.mean())

        cur = set(avail)
        # Turnover = (added + removed) / (2 * top_n) — symmetric one-way
        if prev_holdings:
            added = len(cur - prev_holdings)
            removed = len(prev_holdings - cur)
            turnover = (added + removed) / (2.0 * top_n)
        else:
            turnover = 1.0  # initial fill
        prev_holdings = cur

        rows.append({
            "realized_date": realized_date,
            "signal_date": signal_date,
            "model": f"analog_top{top_n}",
            "n_holdings": len(avail),
            "names": ";".join(sorted(avail)),
            "weight_per_name": 1.0 / len(avail),
            "return_gross": ret_gross,
            "turnover": float(turnover),
            "model_version": C.MODEL_VERSION,
        })

    out = pd.DataFrame(rows)
    if not out.empty:
        out["realized_date"] = pd.to_datetime(out["realized_date"])
        out["signal_date"] = pd.to_datetime(out["signal_date"])
    return out


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


def summarize_with_baseline(bt: pd.DataFrame) -> None:
    if bt.empty:
        logger.info("backtest: empty")
        return
    series = bt.set_index("realized_date")["return_gross"]
    stats = annualized_stats(series)
    logger.info(
        "%-22s | n=%3d | ann_ret=%6.2f%% | ann_vol=%6.2f%% | Sharpe=%5.2f | turnover=%.2f/mo",
        f"analog_top{C.TOP_N}", stats["n_months"], stats["ann_return"] * 100,
        stats["ann_vol"] * 100, stats["sharpe"], bt["turnover"].mean(),
    )

    if C.BASELINES_PARQUET.exists():
        ew = pd.read_parquet(C.BASELINES_PARQUET)
        ew["date"] = pd.to_datetime(ew["date"])
        ew_aligned = ew[ew["date"].isin(series.index)].set_index("date")["return_gross"]
        ew_stats = annualized_stats(ew_aligned)
        logger.info(
            "%-22s | n=%3d | ann_ret=%6.2f%% | ann_vol=%6.2f%% | Sharpe=%5.2f",
            "equal_weight (aligned)", ew_stats["n_months"],
            ew_stats["ann_return"] * 100, ew_stats["ann_vol"] * 100,
            ew_stats["sharpe"],
        )
        excess = stats["ann_return"] - ew_stats["ann_return"]
        target = C.BENCHMARK_HURDLE_EXCESS_ANNUAL
        verdict = "PASS" if excess >= target else "FAIL"
        logger.info(
            "Excess vs equal-weight: %+.2f%% (target ≥ %.2f%%) → %s",
            excess * 100, target * 100, verdict,
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="Summarize existing backtest.parquet without rebuilding.")
    args = ap.parse_args()

    C.ensure_dirs()

    if args.check:
        bt = pd.read_parquet(C.BACKTEST_PARQUET)
        bt["realized_date"] = pd.to_datetime(bt["realized_date"])
        summarize_with_baseline(bt)
        return 0

    signals = load_signals()
    returns = load_returns()
    bt = run_long_only(signals, returns, C.TOP_N, C.FORWARD_HORIZON_MONTHS)
    bt.to_parquet(C.BACKTEST_PARQUET, index=False)
    logger.info("Wrote %s (%d rows)", C.BACKTEST_PARQUET, len(bt))
    summarize_with_baseline(bt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
