#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/build_combiner.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Feature tables (month-end snapshots taken per country):
      graph_features_pit_daily  GRAPHP_BANK_NBR_RET_GAP_21D,
                                GRAPHP_TWOHOP_TRADE_GAP_21D,
                                GRAPHP_KATZ_TRADE_GAP_21D
      similarity_features_daily SIM_NBR_RET_GAP_21D
      consensus_signals         CONS_CPI_REV3M_12M
      eco_surprise_signals      ECO_INFL_SURPRISE_Z
      etf_flow_signals          ETF_FLOW_21D_Z (entered NEGATED — contrarian)
    Labels: country_returns_monthly (next-month cross-sectionally demeaned).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/combiner_scores.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/combiner_scores_daily.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `combiner_scores` — tidy (date, country, value, variable,
    source='combiner'), variable COMBINER_RIDGE_V1: the walk-forward ridge
    composite country score for the NEXT month (monthly model; tested DEAD
    2026-06 — kept for the record and for comparison).
    Table `combiner_scores_daily` — variable COMBINER_RIDGE_DAILY_V1: the
    daily walk-forward ridge over the daily market-derived survivors,
    trained on next-5d cross-sectionally demeaned returns, refit yearly.
    Table `combiner_weights` — (train_through, feature, coef) refit history
    so the model's evolving view is inspectable.

VERSION: 1.0
LAST UPDATED: 2026-06-12
AUTHOR: Arjun Divecha (built by agent session, graph machine build-out)

DESCRIPTION:
The prediction layer: combines every signal family that survived the 2026-06
harness passes (|NW-t| >= 2.2) into one composite next-month country score
via walk-forward ridge regression. Features are cross-sectionally z-scored
each month; the model refits each January on ALL data through the prior
December (expanding window, 60-month burn-in) and scores months strictly
out-of-sample relative to its own fit. A 10th grader's version: take every
clue that has actually worked, let a referee weigh them using only the past,
and produce one ranking of countries for next month.

HONESTY NOTE (stated wherever this model is cited): although the ridge fits
are walk-forward, the FEATURE LIST was selected on the full 2008-2026 sample
during the June 2026 sweeps, so the combiner backtest inherits that
selection bias. Its harness verdict is a ceiling, not an estimate; the real
test is forward performance from registration.

DEPENDENCIES:
- duckdb, pandas, numpy, scikit-learn (project venv)

USAGE:
 python scripts/loop/build_combiner.py          # full rebuild (~30 s)
 python scripts/loop/build_combiner.py --check  # verify table

NOTES:
- FAIL-IS-FAIL: missing feature tables abort; months with < 10 scored
  countries are dropped.
=============================================================================
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.loop.loopdb import LOOP_DIR, loop_connection  # noqa: E402

OUT_PARQUET = LOOP_DIR / "combiner_scores.parquet"
OUT_DAILY_PARQUET = LOOP_DIR / "combiner_scores_daily.parquet"

# (table, variable, sign) — sign -1 enters the feature negated (contrarian).
FEATURES = [
    ("graph_features_pit_daily", "GRAPHP_BANK_NBR_RET_GAP_21D", 1.0),
    ("graph_features_pit_daily", "GRAPHP_TWOHOP_TRADE_GAP_21D", 1.0),
    ("graph_features_pit_daily", "GRAPHP_KATZ_TRADE_GAP_21D", 1.0),
    ("similarity_features_daily", "SIM_NBR_RET_GAP_21D", 1.0),
    ("consensus_signals", "CONS_CPI_REV3M_12M", 1.0),
    ("eco_surprise_signals", "ECO_INFL_SURPRISE_Z", 1.0),
    ("etf_flow_signals", "ETF_FLOW_21D_Z", -1.0),
]
# Daily combiner: only the daily market-derived survivors (the monthly
# version tested DEAD — month-end resampling discards the ~weekly horizon
# where these families actually live).
DAILY_FEATURES = [
    ("graph_features_pit_daily", "GRAPHP_BANK_NBR_RET_GAP_21D", 1.0),
    ("graph_features_pit_daily", "GRAPHP_TWOHOP_TRADE_GAP_21D", 1.0),
    ("graph_features_pit_daily", "GRAPHP_KATZ_TRADE_GAP_21D", 1.0),
    ("similarity_features_daily", "SIM_NBR_RET_GAP_21D", 1.0),
    ("leadlag_features_daily", "LL_LEADER_GAP_5D", 1.0),
    ("etf_flow_signals", "ETF_FLOW_21D_Z", -1.0),
]
RIDGE_ALPHA = 10.0
BURN_IN_MONTHS = 60
MIN_FEATURES_PRESENT = 4
MIN_COUNTRIES = 10
DAILY_TARGET_HORIZON = 5  # train the daily model on next-5d demeaned returns


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} [combiner] {msg}", flush=True)


def month_end_feature_panel(con) -> pd.DataFrame:
    """(month, country) x feature matrix from month-end snapshots."""
    frames = []
    for table, var, sign in FEATURES:
        df = con.execute(f"""
            SELECT date_trunc('month', date) AS month, country,
                   arg_max(value, date) * {sign} AS value
            FROM {table}
            WHERE variable = ? AND value IS NOT NULL
            GROUP BY 1, 2
        """, [var]).fetchdf()
        if df.empty:
            raise RuntimeError(f"feature {table}.{var} returned zero rows")
        df["feature"] = var
        frames.append(df)
    panel = pd.concat(frames, ignore_index=True)
    wide = panel.pivot_table(index=["month", "country"], columns="feature", values="value")
    return wide


def next_month_labels(con) -> pd.Series:
    """Next-month cross-sectionally demeaned return per (month, country):
    the label attached to month m is the return realized in month m+1."""
    df = con.execute("""
        SELECT date_trunc('month', date) AS month, country, return_1m AS value
        FROM country_returns_monthly WHERE return_1m IS NOT NULL
    """).fetchdf()
    df["month"] = pd.to_datetime(df["month"])
    df["xs_demeaned"] = df["value"] - df.groupby("month")["value"].transform("mean")
    df["label_month"] = df["month"] - pd.DateOffset(months=1)
    return df.set_index(["label_month", "country"])["xs_demeaned"]


def zscore_by_month(wide: pd.DataFrame) -> pd.DataFrame:
    def z(g: pd.DataFrame) -> pd.DataFrame:
        return (g - g.mean()) / g.std(ddof=0).replace(0, np.nan)
    return wide.groupby(level="month", group_keys=False).apply(z)


def build() -> int:
    from sklearn.linear_model import Ridge

    con = loop_connection()
    try:
        wide = month_end_feature_panel(con)
        labels = next_month_labels(con)
    finally:
        con.close()
    log(f"feature panel: {wide.shape[0]:,} (month,country) rows x {wide.shape[1]} features")

    z = zscore_by_month(wide)
    z = z[z.notna().sum(axis=1) >= MIN_FEATURES_PRESENT]
    x = z.fillna(0.0)
    y = labels.reindex(x.index)

    months = sorted(x.index.get_level_values("month").unique())
    if len(months) < BURN_IN_MONTHS + 12:
        raise RuntimeError(f"only {len(months)} months of features — too short to walk forward")

    score_rows: list[pd.DataFrame] = []
    weight_rows: list[dict] = []
    model, trained_through = None, None
    for m in months[BURN_IN_MONTHS:]:
        refit_due = model is None or (m.month == 1)
        if refit_due:
            train_mask = (x.index.get_level_values("month") < m) & y.notna()
            xt, yt = x[train_mask], y[train_mask]
            if len(xt) < 500:
                continue
            model = Ridge(alpha=RIDGE_ALPHA).fit(xt, yt)
            trained_through = xt.index.get_level_values("month").max()
            for feat, coef in zip(x.columns, model.coef_):
                weight_rows.append({"train_through": trained_through,
                                    "feature": feat, "coef": float(coef)})
        rows = x.loc[x.index.get_level_values("month") == m]
        if len(rows) < MIN_COUNTRIES:
            continue
        preds = model.predict(rows)
        score_rows.append(pd.DataFrame({
            "date": (m + pd.offsets.MonthEnd(0)),
            "country": rows.index.get_level_values("country"),
            "value": preds,
        }))

    if not score_rows:
        raise RuntimeError("no combiner scores produced — refusing to continue")
    scores = pd.concat(score_rows, ignore_index=True)
    scores["variable"] = "COMBINER_RIDGE_V1"
    scores["source"] = "combiner"
    scores.to_parquet(OUT_PARQUET, index=False)
    weights = pd.DataFrame(weight_rows)

    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS combiner_scores")
        con.execute(f"""
            CREATE TABLE combiner_scores AS
            SELECT CAST(date AS DATE) AS date, country, value, variable, source
            FROM read_parquet('{OUT_PARQUET}')
        """)
        con.execute("DROP TABLE IF EXISTS combiner_weights")
        con.register("w_df", weights)
        con.execute("""
            CREATE TABLE combiner_weights AS
            SELECT CAST(train_through AS DATE) AS train_through, feature, coef FROM w_df
        """)
        n, lo, hi = con.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM combiner_scores").fetchone()
        if not n:
            raise RuntimeError("combiner_scores rebuilt empty")
        log(f"stored: {n:,} scores {lo} -> {hi}; {len(weights)} weight rows")
    finally:
        con.close()

    latest = weights[weights["train_through"] == weights["train_through"].max()]
    log("latest refit coefficients:")
    for r in latest.itertuples():
        log(f"  {r.feature:34s} {r.coef:+.5f}")
    return 0


def build_daily() -> int:
    """Walk-forward ridge on the DAILY market-derived survivors, trained on
    next-5d cross-sectionally demeaned returns, refit each January using
    only data through the prior year. Same honesty note as the monthly
    model: the feature list was selected in-sample this month."""
    from sklearn.linear_model import Ridge

    from scripts.loop.loopdb import returns_panel

    con = loop_connection()
    try:
        frames = []
        for table, var, sign in DAILY_FEATURES:
            df = con.execute(f"""
                SELECT CAST(date AS TIMESTAMP) AS date, country, value * {sign} AS value
                FROM {table} WHERE variable = ? AND value IS NOT NULL
            """, [var]).fetchdf()
            if df.empty:
                raise RuntimeError(f"daily feature {table}.{var} returned zero rows")
            df["feature"] = var
            frames.append(df)
        piv_ret = returns_panel(con)
    finally:
        con.close()

    panel = pd.concat(frames, ignore_index=True)
    wide = panel.pivot_table(index=["date", "country"], columns="feature", values="value")
    log(f"daily feature panel: {wide.shape[0]:,} rows x {wide.shape[1]} features")

    # cross-sectional z per date
    z = wide.groupby(level="date", group_keys=False).apply(
        lambda g: (g - g.mean()) / g.std(ddof=0).replace(0, np.nan))
    z = z[z.notna().sum(axis=1) >= MIN_FEATURES_PRESENT]
    x = z.fillna(0.0)

    # label: next-5d compounded return, cross-sectionally demeaned
    log1p = np.log1p(piv_ret)
    # compounded return over t+1 .. t+5: reverse-rolling sum of log returns
    # anchored at t (covers t..t+4), then shifted one day forward
    fwd = np.exp(log1p[::-1].rolling(DAILY_TARGET_HORIZON).sum()[::-1].shift(-1)) - 1
    fwd = fwd.sub(fwd.mean(axis=1), axis=0)
    y = fwd.stack().rename("y")
    y.index.names = ["date", "country"]
    y = y.reindex(x.index)

    dates = x.index.get_level_values("date")
    years = sorted(set(dates.year))
    score_rows: list[pd.DataFrame] = []
    model = None
    for yr in years:
        train_mask = (dates < pd.Timestamp(f"{yr}-01-01")) & y.notna()
        if train_mask.sum() >= 20_000:
            model = Ridge(alpha=RIDGE_ALPHA).fit(x[train_mask], y[train_mask])
        if model is None:
            continue
        rows = x[dates.year == yr]
        if rows.empty:
            continue
        score_rows.append(pd.DataFrame({
            "date": rows.index.get_level_values("date"),
            "country": rows.index.get_level_values("country"),
            "value": model.predict(rows),
        }))
    if not score_rows:
        raise RuntimeError("no daily combiner scores produced — refusing to continue")
    scores = pd.concat(score_rows, ignore_index=True)
    scores["variable"] = "COMBINER_RIDGE_DAILY_V1"
    scores["source"] = "combiner"
    scores.to_parquet(OUT_DAILY_PARQUET, index=False)

    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS combiner_scores_daily")
        con.execute(f"""
            CREATE TABLE combiner_scores_daily AS
            SELECT CAST(date AS DATE) AS date, country, value, variable, source
            FROM read_parquet('{OUT_DAILY_PARQUET}')
        """)
        n, lo, hi = con.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM combiner_scores_daily").fetchone()
        if not n:
            raise RuntimeError("combiner_scores_daily rebuilt empty")
        log(f"stored daily: {n:,} scores {lo} -> {hi}")
    finally:
        con.close()
    return 0


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        n, nc, lo, hi = con.execute("""
            SELECT COUNT(*), COUNT(DISTINCT country), MIN(date), MAX(date)
            FROM combiner_scores
        """).fetchone()
        nd = con.execute("SELECT COUNT(*) FROM combiner_scores_daily").fetchone()[0]
    finally:
        con.close()
    print(f"combiner_scores: {n:,} rows, {nc} countries, {lo} -> {hi}")
    print(f"combiner_scores_daily: {nd:,} rows")
    ok = bool(n and nc >= 20 and nd)
    print("CHECK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Walk-forward ridge combiner over surviving signals.")
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    if args.check:
        return check()
    rc = build()
    return rc or build_daily()


if __name__ == "__main__":
    sys.exit(main())
