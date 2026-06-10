#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: build_graph_features.py
=============================================================================

INPUT FILES:
- Neo4j @ bolt://localhost:7687 (read-only queries)
  Edges: TRADES_WITH (trade_share_pct), HAS_BANKING_EXPOSURE_TO
  (share_of_total_claims_pct), HOLDS_PORTFOLIO (share_of_counterpart_inbound_pct).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb (read-only)
  t2_factors_daily 1DRet rows (daily country returns, decimal) - consumed via
  loopdb.daily_country_returns (backward-labeled real trading days).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
  graph_edge_snapshots (accumulated monthly PIT edge-weight snapshots).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
  Table `graph_features_daily(date, country, value, variable, source)` -
  tidy format, source='graph', full history.
  Table `graph_edge_snapshots(snapshot_month, edge_type, focal, neighbor,
  weight, captured_ts)` - current month's snapshot REPLACED each run, prior
  months never touched (the PIT archive).
  Table `loop_variable_meta` - variable descriptions for loop variables.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/graph_features_daily.parquet
  graph_features_daily as parquet.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/graph_edge_snapshots.parquet
  The PIT snapshot archive as parquet (survives any loop-DB accident).

VERSION: 1.1
LAST UPDATED: 2026-06-10
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 2)

DESCRIPTION:
The graph->panel feature factory (PRD section 7). Turns Neo4j from a lookup
table into a producer of ordinary panel variables: for every country and
day, how have its TRADING PARTNERS, its BANKS' EXPOSURE TARGETS, and the
COUNTRIES THAT OWN ITS ASSETS been doing - relative to the country itself?

v1.1 changes (2026-06-10):
1. POINT-IN-TIME EDGE WEIGHTS. Every run stores the current Neo4j edge
   weights as a snapshot keyed by month in `graph_edge_snapshots` (current
   month replaced, prior months immutable). Feature computation then uses,
   for each historical date, the LATEST SNAPSHOT AT OR BEFORE that date's
   month. Honesty boundary: dates before the FIRST snapshot (2026-06) are
   computed with that first snapshot - NOT point-in-time - and the boundary
   is recorded in loop_variable_meta.pit_weights_start. From 2026-07 onward
   the history becomes honestly PIT as snapshots accumulate.
2. CORRECTED RETURN ENGINE. v1 rolled windows over the calendar-day grid of
   the FORWARD-labeled 1DRet (weekend 0.0 placeholders included), so a "21d"
   window spanned ~15 trading days and labels sat one day in the future.
   Now uses loopdb.daily_country_returns: backward-labeled, real trading
   days only. Trailing returns compound over each country's own trading
   days; the union calendar keeps only dates where >= 10 countries traded.

v1 features (per country-day), unchanged in definition:
  GRAPH_TRADE_NBR_RET_GAP_21D / _63D  trade-share-weighted neighbor trailing
                                      return minus own trailing return
  GRAPH_BANK_NBR_RET_GAP_21D / _63D   banking-claims-weighted version
  GRAPH_PORT_HOLDER_STRESS_21D        inbound-ownership-weighted holder-country
                                      drawdown
  GRAPH_TWOHOP_TRADE_GAP_21D          two-hop (W squared) trade-weighted gap
  GRAPH_NBR_DRAWDOWN_COUNT            trade-share-weighted fraction of
                                      neighbors in >10 percent drawdown

DEPENDENCIES:
- duckdb, pandas, numpy, neo4j (project venv)

USAGE:
 python scripts/loop/build_graph_features.py          # full rebuild (~1 min)
 python scripts/loop/build_graph_features.py --check  # verify existing table
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

from scripts.loop.loopdb import LOOP_DIR, T2_UNIVERSE, loop_connection, returns_panel

NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "mythos2026")
PARQUET_OUT = LOOP_DIR / "graph_features_daily.parquet"
SNAPSHOT_PARQUET = LOOP_DIR / "graph_edge_snapshots.parquet"
FFILL_LIMIT = 5  # max days a country's trailing return is carried across holidays

EDGE_TYPES = ["trade", "bank", "holder"]

VARIABLE_META = {
    "GRAPH_TRADE_NBR_RET_GAP_21D": "Trade-share-weighted neighbor 21d return minus own 21d return",
    "GRAPH_TRADE_NBR_RET_GAP_63D": "Trade-share-weighted neighbor 63d return minus own 63d return",
    "GRAPH_BANK_NBR_RET_GAP_21D": "Banking-claims-weighted neighbor 21d return minus own 21d return",
    "GRAPH_BANK_NBR_RET_GAP_63D": "Banking-claims-weighted neighbor 63d return minus own 63d return",
    "GRAPH_PORT_HOLDER_STRESS_21D": "Inbound-portfolio-ownership-weighted holder-country drawdown (negative = holders stressed)",
    "GRAPH_TWOHOP_TRADE_GAP_21D": "Two-hop trade-weighted neighbor 21d return minus own 21d return",
    "GRAPH_NBR_DRAWDOWN_COUNT": "Trade-share-weighted fraction of neighbors in >10pct drawdown from 252d high",
}


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} [graph_features] {msg}", flush=True)


def fetch_weight_matrix(session, cypher: str, weight_key: str) -> pd.DataFrame:
    """Return a (focal x neighbor) weight matrix from an edge query."""
    rows = session.run(cypher).data()
    if not rows:
        raise RuntimeError(f"No edges returned for: {cypher[:80]} (Neo4j empty? FAIL-IS-FAIL)")
    df = pd.DataFrame(rows)
    w = df.pivot_table(index="focal", columns="neighbor", values=weight_key, aggfunc="sum")
    w = w.reindex(index=T2_UNIVERSE, columns=T2_UNIVERSE).copy()
    vals = w.to_numpy(copy=True)
    np.fill_diagonal(vals, np.nan)  # no self-loops
    return pd.DataFrame(vals, index=w.index, columns=w.columns)


def fetch_current_weights() -> dict[str, pd.DataFrame]:
    from neo4j import GraphDatabase

    drv = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    try:
        with drv.session() as s:
            w_trade = fetch_weight_matrix(
                s, "MATCH (a:Country)-[r:TRADES_WITH]->(b:Country) "
                   "RETURN a.t2_name AS focal, b.t2_name AS neighbor, r.trade_share_pct AS w", "w")
            w_bank = fetch_weight_matrix(
                s, "MATCH (a:Country)-[r:HAS_BANKING_EXPOSURE_TO]->(b:Country) "
                   "RETURN a.t2_name AS focal, b.t2_name AS neighbor, r.share_of_total_claims_pct AS w", "w")
            # holders of `focal`'s assets: (holder)-[HOLDS_PORTFOLIO]->(focal)
            w_holder = fetch_weight_matrix(
                s, "MATCH (h:Country)-[r:HOLDS_PORTFOLIO]->(c:Country) "
                   "RETURN c.t2_name AS focal, h.t2_name AS neighbor, r.share_of_counterpart_inbound_pct AS w", "w")
    finally:
        drv.close()
    return {"trade": w_trade, "bank": w_bank, "holder": w_holder}


# ── PIT snapshot store ───────────────────────────────────────────────────────

def store_snapshot(con, weights: dict[str, pd.DataFrame], snap_month: str) -> None:
    """Replace the CURRENT month's snapshot rows; prior months are immutable."""
    rows = []
    ts = datetime.now().isoformat(timespec="seconds")
    for etype, w in weights.items():
        tidy = w.stack().rename("weight").reset_index()
        tidy.columns = ["focal", "neighbor", "weight"]
        tidy = tidy.dropna(subset=["weight"])
        for r in tidy.itertuples():
            rows.append({"snapshot_month": snap_month, "edge_type": etype,
                         "focal": r.focal, "neighbor": r.neighbor,
                         "weight": float(r.weight), "captured_ts": ts})
    snap_df = pd.DataFrame(rows)
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS graph_edge_snapshots (
            snapshot_month VARCHAR, edge_type VARCHAR, focal VARCHAR,
            neighbor VARCHAR, weight DOUBLE, captured_ts VARCHAR
        )
        """
    )
    con.execute("DELETE FROM graph_edge_snapshots WHERE snapshot_month = ?", [snap_month])
    con.execute("INSERT INTO graph_edge_snapshots BY NAME SELECT * FROM snap_df")
    con.execute(f"COPY graph_edge_snapshots TO '{SNAPSHOT_PARQUET}' (FORMAT PARQUET)")
    log(f"snapshot {snap_month}: {len(snap_df):,} edge rows stored ({SNAPSHOT_PARQUET.name} refreshed)")


def load_snapshots(con) -> dict[str, dict[str, pd.DataFrame]]:
    """All stored snapshots as {snapshot_month: {edge_type: matrix}}, ordered."""
    df = con.execute("SELECT * FROM graph_edge_snapshots").fetchdf()
    out: dict[str, dict[str, pd.DataFrame]] = {}
    for (month, etype), g in df.groupby(["snapshot_month", "edge_type"]):
        w = g.pivot_table(index="focal", columns="neighbor", values="weight", aggfunc="sum")
        w = w.reindex(index=T2_UNIVERSE, columns=T2_UNIVERSE)
        out.setdefault(month, {})[etype] = w
    return dict(sorted(out.items()))


# ── math ─────────────────────────────────────────────────────────────────────

def weighted_neighbor(metric: pd.DataFrame, w: pd.DataFrame) -> pd.DataFrame:
    """For each date row in `metric` (dates x countries), compute the
    w-weighted neighbor average, re-normalizing weights over the countries
    with data that day."""
    out = pd.DataFrame(index=metric.index, columns=metric.columns, dtype=float)
    w_vals = w.values  # (34, 34), focal x neighbor
    m_vals = metric.values  # (T, 34)
    valid = ~np.isnan(m_vals)
    for fi in range(w_vals.shape[0]):
        wrow = w_vals[fi]
        has_w = ~np.isnan(wrow)
        if not has_w.any():
            continue
        wm = np.where(has_w, wrow, 0.0)
        eff = valid * wm
        denom = eff.sum(axis=1)
        numer = np.nansum(np.where(valid, m_vals, 0.0) * wm, axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            out.iloc[:, fi] = np.where(denom > 1e-12, numer / denom, np.nan)
    return out


def twohop_matrix(w_trade: pd.DataFrame) -> pd.DataFrame:
    wt = w_trade.fillna(0.0).values
    row_sums = wt.sum(axis=1, keepdims=True)
    wt_n = np.divide(wt, row_sums, out=np.zeros_like(wt), where=row_sums > 0)
    w2 = wt_n @ wt_n
    np.fill_diagonal(w2, 0.0)
    return pd.DataFrame(w2, index=T2_UNIVERSE, columns=T2_UNIVERSE).replace(0.0, np.nan)


def compute_features(metrics: dict[str, pd.DataFrame],
                     weights: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """All 7 features for one weight regime, on the metric frames given."""
    ret21, ret63 = metrics["ret21"], metrics["ret63"]
    drawdown, in_dd10 = metrics["drawdown"], metrics["in_dd10"]
    w_trade, w_bank, w_holder = weights["trade"], weights["bank"], weights["holder"]
    w_2hop = twohop_matrix(w_trade)
    return {
        "GRAPH_TRADE_NBR_RET_GAP_21D": weighted_neighbor(ret21, w_trade) - ret21,
        "GRAPH_TRADE_NBR_RET_GAP_63D": weighted_neighbor(ret63, w_trade) - ret63,
        "GRAPH_BANK_NBR_RET_GAP_21D": weighted_neighbor(ret21, w_bank) - ret21,
        "GRAPH_BANK_NBR_RET_GAP_63D": weighted_neighbor(ret63, w_bank) - ret63,
        "GRAPH_PORT_HOLDER_STRESS_21D": weighted_neighbor(drawdown, w_holder),
        "GRAPH_TWOHOP_TRADE_GAP_21D": weighted_neighbor(ret21, w_2hop) - ret21,
        "GRAPH_NBR_DRAWDOWN_COUNT": weighted_neighbor(in_dd10, w_trade),
    }


def build() -> int:
    # ── 1. Current edge weights from Neo4j + snapshot ───────────────────
    log("Fetching edge weights from Neo4j ...")
    current = fetch_current_weights()
    log(f"edges: trade focal rows={current['trade'].notna().any(axis=1).sum()}, "
        f"bank={current['bank'].notna().any(axis=1).sum()}, "
        f"holders={current['holder'].notna().any(axis=1).sum()}")

    snap_month = datetime.now().strftime("%Y-%m")
    con = loop_connection()
    try:
        store_snapshot(con, current, snap_month)
        snapshots = load_snapshots(con)
    finally:
        con.close()
    pit_start = min(snapshots)  # earliest snapshot month, e.g. '2026-06'
    log(f"snapshots available: {list(snapshots)} (PIT from {pit_start}; earlier history "
        f"uses the {pit_start} weights - NOT point-in-time, recorded in meta)")

    # ── 2. Backward-labeled trading-day returns ─────────────────────────
    log("Loading daily returns (backward-labeled, real trading days) ...")
    con = loop_connection()
    try:
        piv = returns_panel(con)
    finally:
        con.close()
    log(f"return panel: {piv.shape[0]} trading dates x {piv.shape[1]} countries, "
        f"{piv.index.min().date()} -> {piv.index.max().date()}")

    # Per-country trailing compounded returns over ITS OWN trading days
    def trailing(n: int) -> pd.DataFrame:
        out = {}
        for c in piv.columns:
            s = piv[c].dropna()
            out[c] = np.exp(np.log1p(s).rolling(n).sum()) - 1
        return pd.DataFrame(out).reindex(piv.index).ffill(limit=FFILL_LIMIT)

    ret21 = trailing(21)
    ret63 = trailing(63)

    dd = {}
    for c in piv.columns:
        s = piv[c].dropna()
        idx = (1 + s).cumprod()
        dd[c] = idx / idx.rolling(252, min_periods=60).max() - 1
    drawdown = pd.DataFrame(dd).reindex(piv.index).ffill(limit=FFILL_LIMIT)
    in_dd10 = (drawdown < -0.10).astype(float).where(~drawdown.isna())

    metrics_all = {"ret21": ret21, "ret63": ret63, "drawdown": drawdown, "in_dd10": in_dd10}

    # ── 3. Features per snapshot regime (PIT as-of join on months) ─────
    log("Computing weighted neighbor features per snapshot regime ...")
    months = sorted(snapshots)
    # regime m applies from month-start(m) up to month-start(next snapshot);
    # all dates BEFORE the first snapshot also use the first snapshot.
    bounds = []
    for i, m in enumerate(months):
        start = pd.Timestamp(f"{m}-01") if i > 0 else pd.Timestamp("1900-01-01")
        end = pd.Timestamp(f"{months[i + 1]}-01") if i + 1 < len(months) else pd.Timestamp("2200-01-01")
        bounds.append((m, start, end))

    regime_frames: dict[str, list[pd.DataFrame]] = {v: [] for v in VARIABLE_META}
    for m, start, end in bounds:
        mask = (piv.index >= start) & (piv.index < end)
        if not mask.any():
            continue
        metrics = {k: v.loc[mask] for k, v in metrics_all.items()}
        feats = compute_features(metrics, snapshots[m])
        for var, mat in feats.items():
            regime_frames[var].append(mat)
        log(f"  regime {m}: {int(mask.sum())} dates")

    frames = []
    for var, mats in regime_frames.items():
        mat = pd.concat(mats).sort_index()
        f = mat.stack().rename("value").reset_index()
        f.columns = ["date", "country", "value"]
        f["variable"] = var
        f["source"] = "graph"
        frames.append(f)
    tidy = pd.concat(frames, ignore_index=True).dropna(subset=["value"])

    # ── 4. Quality gates ────────────────────────────────────────────────
    # Banking edges (HAS_BANKING_EXPOSURE_TO) exist only for BIS LBS
    # reporter countries (21/34 focal) - a structural coverage limit, not a
    # bug. Gate banking features at >=18 and everything else at >=28, and
    # report the gap loudly instead of silently dropping it.
    recent = tidy[tidy["date"] >= tidy["date"].max() - pd.Timedelta(days=30)]
    cov = recent.groupby("variable")["country"].nunique()
    failures = {}
    for var, n in cov.items():
        min_required = 18 if var.startswith("GRAPH_BANK_") else 28
        if n < min_required:
            failures[var] = int(n)
        if n < 34:
            have = set(recent[recent["variable"] == var]["country"])
            missing = sorted(set(T2_UNIVERSE) - have)
            log(f"coverage gap {var}: {n}/34 countries (missing: {', '.join(missing)})")
    if failures:
        raise ValueError(f"Coverage below variable-specific minimum: {failures}")

    # ── 5. Write ────────────────────────────────────────────────────────
    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS graph_features_daily")
        con.execute("CREATE TABLE graph_features_daily AS SELECT * FROM tidy")
        con.execute(f"COPY graph_features_daily TO '{PARQUET_OUT}' (FORMAT PARQUET)")

        meta = pd.DataFrame(
            [{"variable": k, "source": "graph", "frequency": "daily",
              "description": v, "publication_lag_months": 0,
              "pit_weights_start": pit_start} for k, v in VARIABLE_META.items()]
        )
        con.execute("DROP TABLE IF EXISTS loop_variable_meta")
        con.execute("CREATE TABLE loop_variable_meta AS SELECT * FROM meta")

        n, d0, d1, nv = con.execute(
            "SELECT count(*), min(date), max(date), count(DISTINCT variable) FROM graph_features_daily"
        ).fetchone()
        log(f"graph_features_daily: {n:,} rows, {d0} -> {d1}, {nv} variables")
        log(f"parquet: {PARQUET_OUT}")
    finally:
        con.close()
    return 0


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        df = con.execute(
            """
            SELECT variable, count(*) AS n, min(date) AS d0, max(date) AS d1,
                   round(avg(value), 4) AS avg_val
            FROM graph_features_daily GROUP BY variable ORDER BY variable
            """
        ).fetchdf()
        print(df.to_string(index=False))
        snaps = con.execute(
            "SELECT snapshot_month, edge_type, count(*) AS n_edges FROM graph_edge_snapshots "
            "GROUP BY snapshot_month, edge_type ORDER BY snapshot_month, edge_type"
        ).fetchdf()
        print("\nPIT edge snapshots:")
        print(snaps.to_string(index=False))
        return 0
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Graph->panel feature factory (Neo4j edges x daily returns, PIT snapshots).")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return check() if args.check else build()


if __name__ == "__main__":
    sys.exit(main())
