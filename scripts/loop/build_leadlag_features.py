#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/build_leadlag_features.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `country_returns_daily` (via loopdb.returns_panel) — daily T2
    country returns 2000+, 34 countries.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/leadlag_features_daily.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `leadlag_features_daily` — tidy (date, country, value, variable,
    source='leadlag'):
      LL_LEADER_RET_1D   lead-lag-weighted average of the focal country's
                         leaders' SAME-DAY return (leaders identified by
                         trailing-252d lag-1 cross-correlation; the harness
                         embargo means this predicts the NEXT day onward)
      LL_LEADER_GAP_5D   leaders' trailing 5d return minus own 5d return —
                         the slower "leaders moved, I haven't" convergence gap
    Table `leadlag_edges` — (month, leader, follower, corr) surviving edges
    per estimation month, kept for Neo4j LEADS write-back and inspection.

VERSION: 1.0
LAST UPDATED: 2026-06-12
AUTHOR: Arjun Divecha (built by agent session, graph machine build-out)

DESCRIPTION:
Builds a connection surface that exists nowhere in Neo4j: the empirical
lead-lag network of country returns. Each month-end, every ordered country
pair gets the correlation between the leader's day t-1 return and the
follower's day t return over the trailing 252 trading days; edges with
corr >= 0.15 (and >= 150 overlapping days) survive. The edge map estimated
at month m is applied to dates in month m+1 — fully point-in-time. Part of
the lag-1 structure is timezone mechanics (Asia closes before New York);
that is real, tradable sequencing for a next-open implementation, and the
mechanism text of any registered hypothesis says so explicitly.

DEPENDENCIES:
- duckdb, pandas, numpy (project venv)

USAGE:
 python scripts/loop/build_leadlag_features.py          # full rebuild (~2 min)
 python scripts/loop/build_leadlag_features.py --check  # verify tables

NOTES:
- FAIL-IS-FAIL: an empty returns panel or an empty edge map aborts the build.
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
from scripts.loop.loopdb import LOOP_DIR, T2_UNIVERSE, loop_connection, returns_panel  # noqa: E402
from scripts.loop.build_graph_features import weighted_neighbor  # noqa: E402

OUT_PARQUET = LOOP_DIR / "leadlag_features_daily.parquet"

WINDOW = 252
MIN_OBS = 150
CORR_THRESHOLD = 0.15
FFILL_LIMIT = 5


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} [leadlag] {msg}", flush=True)


def monthly_edge_maps(piv: pd.DataFrame) -> tuple[dict[pd.Timestamp, pd.DataFrame], pd.DataFrame]:
    """{estimation_month: W (follower x leader corr weights)} + tidy edges."""
    month_ends = piv.groupby(piv.index.to_period("M")).tail(1).index
    maps: dict[pd.Timestamp, pd.DataFrame] = {}
    edge_rows: list[dict] = []
    for me in month_ends:
        pos = piv.index.get_loc(me)
        if pos + 1 < WINDOW:
            continue
        window = piv.iloc[pos + 1 - WINDOW: pos + 1]
        w = pd.DataFrame(np.nan, index=T2_UNIVERSE, columns=T2_UNIVERSE)
        month = me.to_period("M").to_timestamp()
        for leader in piv.columns:
            lead_lagged = window[leader].shift(1)
            if lead_lagged.notna().sum() < MIN_OBS:
                continue
            corr = window.corrwith(lead_lagged)
            n_overlap = window.notna().mul(lead_lagged.notna(), axis=0).sum()
            corr = corr.where(n_overlap >= MIN_OBS)
            for follower, c in corr.items():
                if follower == leader or not np.isfinite(c) or c < CORR_THRESHOLD:
                    continue
                w.loc[follower, leader] = c
                edge_rows.append({"month": month, "leader": leader,
                                  "follower": follower, "corr": float(c)})
        if w.notna().any(axis=None):
            maps[month] = w
    if not maps:
        raise RuntimeError("lead-lag edge map empty — refusing to continue")
    return maps, pd.DataFrame(edge_rows)


def build() -> int:
    con = loop_connection()
    try:
        piv = returns_panel(con)
    finally:
        con.close()
    if piv.empty:
        raise RuntimeError("empty return panel — refusing to continue")
    log(f"returns: {piv.shape[0]} dates x {piv.shape[1]} countries")

    maps, edges = monthly_edge_maps(piv)
    log(f"edge maps for {len(maps)} months, {len(edges):,} edges total "
        f"(median {edges.groupby('month').size().median():.0f}/month)")

    ret1 = piv.copy()
    ret5 = {}
    for c in piv.columns:
        s = piv[c].dropna()
        ret5[c] = np.exp(np.log1p(s).rolling(5).sum()) - 1
    ret5 = pd.DataFrame(ret5).reindex(piv.index).ffill(limit=FFILL_LIMIT)

    months = sorted(maps)
    frames: list[pd.DataFrame] = []
    for var, metric, gap in [("LL_LEADER_RET_1D", ret1, False),
                             ("LL_LEADER_GAP_5D", ret5, True)]:
        parts = []
        for i, m in enumerate(months):
            start = m + pd.DateOffset(months=1)
            end = months[i + 1] + pd.DateOffset(months=1) if i + 1 < len(months) else pd.Timestamp("2200-01-01")
            mask = (piv.index >= start) & (piv.index < end)
            if not mask.any():
                continue
            seg = metric.loc[mask]
            nbr = weighted_neighbor(seg, maps[m])
            parts.append((nbr - seg) if gap else nbr)
        full = pd.concat(parts).sort_index()
        tidy = full.stack().rename("value").reset_index()
        tidy.columns = ["date", "country", "value"]
        tidy["variable"] = var
        frames.append(tidy)
        log(f"{var}: {len(tidy):,} rows")

    out = pd.concat(frames, ignore_index=True).dropna(subset=["value"])
    out["source"] = "leadlag"
    out.to_parquet(OUT_PARQUET, index=False)

    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS leadlag_features_daily")
        con.execute(f"""
            CREATE TABLE leadlag_features_daily AS
            SELECT CAST(date AS DATE) AS date, country, value, variable, source
            FROM read_parquet('{OUT_PARQUET}')
        """)
        con.execute("DROP TABLE IF EXISTS leadlag_edges")
        con.register("edges_df", edges)
        con.execute("""
            CREATE TABLE leadlag_edges AS
            SELECT CAST(month AS DATE) AS month, leader, follower, corr FROM edges_df
        """)
        n, lo, hi = con.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM leadlag_features_daily").fetchone()
        if not n:
            raise RuntimeError("leadlag_features_daily rebuilt empty")
        log(f"stored: {n:,} feature rows {lo} -> {hi}; {len(edges):,} edge rows")
    finally:
        con.close()
    return 0


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        rows = con.execute("""
            SELECT variable, COUNT(DISTINCT country) nc, MIN(date) lo, MAX(date) hi
            FROM leadlag_features_daily GROUP BY 1 ORDER BY 1
        """).fetchall()
    finally:
        con.close()
    ok = len(rows) == 2
    for var, nc, lo, hi in rows:
        print(f"{var}: {nc} countries, {lo} -> {hi}")
        if nc < 20:
            ok = False
    print("CHECK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Build lead-lag network features.")
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    return check() if args.check else build()


if __name__ == "__main__":
    sys.exit(main())
