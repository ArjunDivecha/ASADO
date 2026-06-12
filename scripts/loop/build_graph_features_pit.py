#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/build_graph_features_pit.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `graph_edge_vintages` (from collect_pit_edges.py): historical
    trade/bank/holder weight matrices with publication-lagged applies_from.
    Table `country_returns_daily` (via loopdb.returns_panel).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/graph_features_pit_daily.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `graph_features_pit_daily` — tidy (date, country, value, variable,
    source='graph_pit'). Variables:
      GRAPHP_TRADE_NBR_RET_GAP_21D / _63D   PIT trade-weighted neighbor gap
      GRAPHP_BANK_NBR_RET_GAP_21D / _63D    PIT banking-claims neighbor gap
      GRAPHP_TWOHOP_TRADE_GAP_21D           PIT two-hop (W^2) trade gap
      GRAPHP_HOLDER_STRESS_21D              PIT inbound-ownership holder drawdown
      GRAPHP_NBR_DD_COUNT                   PIT trade-weighted frac of neighbors in >10% DD
      GRAPHP_KATZ_TRADE_GAP_21D             Katz propagation gap: sum_{k=1..3}(0.5*Wn)^k
      GRAPHP_HUB_GAP_21D                    hub-amplified gap: neighbor returns scaled by
                                            neighbor PageRank before weighting
      GRAPHP_BLOC_GAP_21D                   spectral trade-bloc mates' avg return minus own

VERSION: 1.0
LAST UPDATED: 2026-06-12
AUTHOR: Arjun Divecha (built by agent session, graph machine build-out)

DESCRIPTION:
Point-in-time rebuild of the graph spillover features plus three genuinely
new graph algorithms (Katz multi-hop propagation, PageRank hub amplification,
spectral trade blocs). Unlike build_graph_features.py v1 (which applies
TODAY'S Neo4j weights over the whole backtest), every date here uses only
edge weights whose publication date precedes it. A 10th grader's version:
the old version graded history with today's friendship map; this one uses
the map that was actually pinned to the wall at the time.

DEPENDENCIES:
- duckdb, pandas, numpy, networkx, scikit-learn (project venv)

USAGE:
 python scripts/loop/build_graph_features_pit.py          # full rebuild (~2 min)
 python scripts/loop/build_graph_features_pit.py --check  # verify table

NOTES:
- Feature values are NaN before the first applicable vintage of their edge
  type (trade features start 2000-04, holder 1998-09) — fully PIT, no
  backfill of structure that was not yet published.
- FAIL-IS-FAIL: empty vintages or an empty return panel abort the build.
=============================================================================
"""

from __future__ import annotations

import argparse
import sys
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.loop.loopdb import LOOP_DIR, T2_UNIVERSE, loop_connection, returns_panel  # noqa: E402
from scripts.loop.build_graph_features import weighted_neighbor, twohop_matrix  # noqa: E402

OUT_PARQUET = LOOP_DIR / "graph_features_pit_daily.parquet"
FFILL_LIMIT = 5
KATZ_ALPHA = 0.5
KATZ_HOPS = 3
N_BLOCS = 4

VARIABLE_META = {
    "GRAPHP_TRADE_NBR_RET_GAP_21D": "PIT trade-share-weighted neighbor 21d return minus own",
    "GRAPHP_TRADE_NBR_RET_GAP_63D": "PIT trade-share-weighted neighbor 63d return minus own",
    "GRAPHP_BANK_NBR_RET_GAP_21D": "PIT banking-claims-weighted neighbor 21d return minus own",
    "GRAPHP_BANK_NBR_RET_GAP_63D": "PIT banking-claims-weighted neighbor 63d return minus own",
    "GRAPHP_TWOHOP_TRADE_GAP_21D": "PIT two-hop trade-weighted neighbor 21d return minus own",
    "GRAPHP_HOLDER_STRESS_21D": "PIT inbound-ownership-weighted holder drawdown",
    "GRAPHP_NBR_DD_COUNT": "PIT trade-weighted fraction of neighbors in >10pct drawdown",
    "GRAPHP_KATZ_TRADE_GAP_21D": "PIT Katz (3-hop, alpha 0.5) trade propagation gap",
    "GRAPHP_HUB_GAP_21D": "PIT PageRank-hub-amplified trade neighbor gap",
    "GRAPHP_BLOC_GAP_21D": "PIT spectral trade-bloc mates avg 21d return minus own",
}


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} [graph_pit] {msg}", flush=True)


# ── vintage loading ─────────────────────────────────────────────────────────

def load_vintages(con) -> dict[str, list[tuple[pd.Timestamp, pd.DataFrame]]]:
    """{edge_type: [(applies_from, W focal x neighbor)] sorted}. For edge
    types with multiple vintages sharing an applies_from month (shouldn't
    happen), the later vintage_end wins."""
    df = con.execute("SELECT * FROM graph_edge_vintages").fetchdf()
    if df.empty:
        raise RuntimeError("graph_edge_vintages is empty — run collect_pit_edges.py first")
    df["applies_from"] = pd.to_datetime(df["applies_from"])
    out: dict[str, list[tuple[pd.Timestamp, pd.DataFrame]]] = {}
    for (etype, af), g in df.groupby(["edge_type", "applies_from"]):
        w = g.pivot_table(index="focal", columns="neighbor", values="weight", aggfunc="sum")
        w = w.reindex(index=T2_UNIVERSE, columns=T2_UNIVERSE)
        vals = w.to_numpy(copy=True)
        np.fill_diagonal(vals, np.nan)
        out.setdefault(etype, []).append((af, pd.DataFrame(vals, index=w.index, columns=w.columns)))
    for etype in out:
        out[etype].sort(key=lambda t: t[0])
    return out


def segments(vintages: list[tuple[pd.Timestamp, pd.DataFrame]],
             index: pd.DatetimeIndex):
    """Yield (date_mask, W) pairs; dates before the first applies_from get none."""
    for i, (af, w) in enumerate(vintages):
        end = vintages[i + 1][0] if i + 1 < len(vintages) else pd.Timestamp("2200-01-01")
        mask = (index >= af) & (index < end)
        if mask.any():
            yield mask, w


# ── new graph algorithms ────────────────────────────────────────────────────

def row_normalize(w: pd.DataFrame) -> np.ndarray:
    vals = w.fillna(0.0).to_numpy()
    rs = vals.sum(axis=1, keepdims=True)
    return np.divide(vals, rs, out=np.zeros_like(vals), where=rs > 0)


def katz_matrix(w: pd.DataFrame) -> pd.DataFrame:
    """Katz propagation: sum of (alpha * Wn)^k for k = 1..KATZ_HOPS."""
    wn = row_normalize(w)
    acc = np.zeros_like(wn)
    p = np.eye(wn.shape[0])
    for _ in range(KATZ_HOPS):
        p = p @ (KATZ_ALPHA * wn)
        acc += p
    np.fill_diagonal(acc, 0.0)
    return pd.DataFrame(acc, index=w.index, columns=w.columns).replace(0.0, np.nan)


def hub_matrix(w: pd.DataFrame) -> pd.DataFrame:
    """Neighbor weights scaled by the neighbor's trade PageRank (hub
    amplification: shocks at central hubs propagate harder)."""
    import networkx as nx

    wn = row_normalize(w)
    g = nx.DiGraph()
    names = list(w.index)
    for i, a in enumerate(names):
        for j, b in enumerate(names):
            if wn[i, j] > 0:
                g.add_edge(a, b, weight=wn[i, j])
    if g.number_of_edges() == 0:
        raise RuntimeError("empty trade graph for PageRank — refusing to continue")
    pr = nx.pagerank(g, alpha=0.85, weight="weight")
    pr_vec = np.array([pr.get(n, 0.0) for n in names])
    scaled = wn * pr_vec[np.newaxis, :]
    np.fill_diagonal(scaled, 0.0)
    return pd.DataFrame(scaled, index=w.index, columns=w.columns).replace(0.0, np.nan)


def bloc_matrix(w: pd.DataFrame) -> pd.DataFrame:
    """Equal-weight adjacency among spectral trade-bloc mates."""
    from sklearn.cluster import SpectralClustering

    present = w.index[w.notna().any(axis=1).to_numpy()]
    sub = w.loc[present, present].fillna(0.0).to_numpy()
    sym = (row_normalize(pd.DataFrame(sub, index=present, columns=present))
           + row_normalize(pd.DataFrame(sub.T, index=present, columns=present)).T) / 2
    sym = (sym + sym.T) / 2
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        labels = SpectralClustering(
            n_clusters=N_BLOCS, affinity="precomputed", assign_labels="discretize",
            random_state=42).fit_predict(sym + 1e-9)
    adj = np.zeros((len(T2_UNIVERSE), len(T2_UNIVERSE)))
    name_to_pos = {n: i for i, n in enumerate(T2_UNIVERSE)}
    for li in range(N_BLOCS):
        members = [present[k] for k in range(len(present)) if labels[k] == li]
        for a in members:
            for b in members:
                if a != b:
                    adj[name_to_pos[a], name_to_pos[b]] = 1.0
    return pd.DataFrame(adj, index=T2_UNIVERSE, columns=T2_UNIVERSE).replace(0.0, np.nan)


# ── build ───────────────────────────────────────────────────────────────────

def build() -> int:
    con = loop_connection()
    try:
        vintages = load_vintages(con)
        piv = returns_panel(con)
    finally:
        con.close()
    if piv.empty:
        raise RuntimeError("empty return panel — refusing to continue")
    log(f"vintages: " + ", ".join(f"{k}={len(v)}" for k, v in vintages.items())
        + f" | returns {piv.shape[0]} dates x {piv.shape[1]} countries")

    def trailing(n: int) -> pd.DataFrame:
        out = {}
        for c in piv.columns:
            s = piv[c].dropna()
            out[c] = np.exp(np.log1p(s).rolling(n).sum()) - 1
        return pd.DataFrame(out).reindex(piv.index).ffill(limit=FFILL_LIMIT)

    ret21, ret63 = trailing(21), trailing(63)
    dd = {}
    for c in piv.columns:
        s = piv[c].dropna()
        idx = (1 + s).cumprod()
        dd[c] = idx / idx.rolling(252, min_periods=60).max() - 1
    drawdown = pd.DataFrame(dd).reindex(piv.index).ffill(limit=FFILL_LIMIT)
    in_dd10 = (drawdown < -0.10).astype(float).where(~drawdown.isna())

    # feature -> (edge_type, metric, derived weight transform, subtract own?)
    feature_defs = {
        "GRAPHP_TRADE_NBR_RET_GAP_21D": ("trade", ret21, None, True),
        "GRAPHP_TRADE_NBR_RET_GAP_63D": ("trade", ret63, None, True),
        "GRAPHP_BANK_NBR_RET_GAP_21D": ("bank", ret21, None, True),
        "GRAPHP_BANK_NBR_RET_GAP_63D": ("bank", ret63, None, True),
        "GRAPHP_TWOHOP_TRADE_GAP_21D": ("trade", ret21, twohop_matrix, True),
        "GRAPHP_HOLDER_STRESS_21D": ("holder", drawdown, None, False),
        "GRAPHP_NBR_DD_COUNT": ("trade", in_dd10, None, False),
        "GRAPHP_KATZ_TRADE_GAP_21D": ("trade", ret21, katz_matrix, True),
        "GRAPHP_HUB_GAP_21D": ("trade", ret21, hub_matrix, True),
        "GRAPHP_BLOC_GAP_21D": ("trade", ret21, bloc_matrix, True),
    }

    frames: list[pd.DataFrame] = []
    for var, (etype, metric, transform, sub_own) in feature_defs.items():
        parts: list[pd.DataFrame] = []
        # cache transforms per vintage (bloc/hub/katz are vintage-level work)
        for mask, w in segments(vintages[etype], piv.index):
            w_eff = transform(w) if transform else w
            seg_metric = metric.loc[mask]
            nbr = weighted_neighbor(seg_metric, w_eff)
            feat = (nbr - seg_metric) if sub_own else nbr
            parts.append(feat)
        if not parts:
            raise RuntimeError(f"{var}: no applicable vintage segments")
        full = pd.concat(parts).sort_index()
        tidy = full.stack().rename("value").reset_index()
        tidy.columns = ["date", "country", "value"]
        tidy["variable"] = var
        frames.append(tidy)
        log(f"{var}: {len(tidy):,} rows, {tidy['date'].min().date()} -> {tidy['date'].max().date()}")

    out = pd.concat(frames, ignore_index=True)
    out["source"] = "graph_pit"
    out = out.dropna(subset=["value"])
    out.to_parquet(OUT_PARQUET, index=False)

    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS graph_features_pit_daily")
        con.execute(f"""
            CREATE TABLE graph_features_pit_daily AS
            SELECT CAST(date AS DATE) AS date, country, value, variable, source
            FROM read_parquet('{OUT_PARQUET}')
        """)
        n, nv, lo, hi = con.execute(
            "SELECT COUNT(*), COUNT(DISTINCT variable), MIN(date), MAX(date) "
            "FROM graph_features_pit_daily").fetchone()
        if not n:
            raise RuntimeError("graph_features_pit_daily rebuilt empty")
        log(f"stored: {n:,} rows, {nv} variables, {lo} -> {hi}")
    finally:
        con.close()
    return 0


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        rows = con.execute("""
            SELECT variable, COUNT(DISTINCT country) nc, MIN(date) lo, MAX(date) hi
            FROM graph_features_pit_daily GROUP BY 1 ORDER BY 1
        """).fetchall()
    finally:
        con.close()
    ok = len(rows) == len(VARIABLE_META)
    for var, nc, lo, hi in rows:
        print(f"{var}: {nc} countries, {lo} -> {hi}")
        if nc < 15:
            ok = False
    print("CHECK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Build point-in-time graph spillover features.")
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    return check() if args.check else build()


if __name__ == "__main__":
    sys.exit(main())
