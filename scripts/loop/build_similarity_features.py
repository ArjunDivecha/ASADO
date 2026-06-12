#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/build_similarity_features.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb (read-only)
    Table `t2_factors_daily` — month-end snapshots of cross-sectionally
    normalized (_CS) FUNDAMENTAL factors per country (valuation, macro,
    rates, fx, commodity exposure, risk, size, volatility categories;
    return/technical/momentum categories are EXCLUDED so similarity means
    "similar fundamentals", not "correlated recent prices").
    Table `variable_meta` — category map used for that selection.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `country_returns_daily` (via loopdb.returns_panel).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/similarity_features_daily.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `similarity_features_daily` — tidy (date, country, value, variable,
    source='fund_similarity'):
      SIM_NBR_RET_GAP_21D  fundamental-twins (top-5 cosine) avg trailing 21d
                           return minus own — convergence-to-twins read
      SIM_NBR_RET_GAP_63D  63d version
    Table `similarity_twins` — (month, focal, neighbor, sim) top-5 twin list
    per month, kept for Neo4j SIMILAR_TO write-back and inspection.

VERSION: 1.0
LAST UPDATED: 2026-06-12
AUTHOR: Arjun Divecha (built by agent session, graph machine build-out)

DESCRIPTION:
Activates the warehouse's biggest idle connection surface: the country-factor
exposure profile. Each month-end, every country becomes a vector of ~45
normalized fundamental factors; cosine similarity finds its 5 nearest
"fundamental twins"; the twin map is applied to the FOLLOWING month's daily
dates (point-in-time: estimated at month-end m, used from m+1). The signal
is the gap between your twins' trailing return and your own — if countries
with your fundamentals rallied and you didn't, you're expected to catch up.
A 10th grader's version: find each country's look-alikes by report card,
then bet the kid whose look-alikes just got picked for the team.

DEPENDENCIES:
- duckdb, pandas, numpy (project venv)

USAGE:
 python scripts/loop/build_similarity_features.py          # full rebuild (~1 min)
 python scripts/loop/build_similarity_features.py --check  # verify tables

NOTES:
- Factor vectors use _CS variables only (already cross-sectionally scaled);
  remaining NaNs are set to 0 (the cross-sectional mean) and countries with
  < 60 percent factor coverage that month are dropped from the twin map.
- FAIL-IS-FAIL: empty factor pulls or an empty twin map abort the build.
=============================================================================
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.loop.loopdb import LOOP_DIR, T2_UNIVERSE, loop_connection, returns_panel  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MAIN_DB = BASE_DIR / "Data" / "asado.duckdb"
OUT_PARQUET = LOOP_DIR / "similarity_features_daily.parquet"

K_TWINS = 5
MIN_COVERAGE = 0.60
FFILL_LIMIT = 5
FUND_CATEGORIES = ("valuation_fund", "macro", "rates", "fx", "commodity",
                   "risk", "size", "volatility")


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} [similarity] {msg}", flush=True)


def month_end_factors() -> pd.DataFrame:
    """Month-end _CS fundamental factor snapshot per (month, country, variable)."""
    con = duckdb.connect(str(MAIN_DB), read_only=True)
    try:
        df = con.execute(f"""
            SELECT date_trunc('month', f.date) AS month, f.country, f.variable,
                   arg_max(f.value, f.date) AS value
            FROM t2_factors_daily f
            JOIN variable_meta m ON m.variable = f.variable
            WHERE m.category IN {FUND_CATEGORIES}
              AND f.variable LIKE '%\\_CS' ESCAPE '\\'
              AND f.value IS NOT NULL
            GROUP BY 1, 2, 3
        """).fetchdf()
    finally:
        con.close()
    if df.empty:
        raise RuntimeError("no fundamental _CS factors pulled — refusing to continue")
    return df


def twin_maps(factors: pd.DataFrame) -> tuple[dict[pd.Timestamp, pd.DataFrame], pd.DataFrame]:
    """{month: W (focal x neighbor sim weights)} + tidy twin list."""
    maps: dict[pd.Timestamp, pd.DataFrame] = {}
    twin_rows: list[dict] = []
    for month, g in factors.groupby("month"):
        mat = g.pivot_table(index="country", columns="variable", values="value")
        mat = mat.replace([np.inf, -np.inf], np.nan)  # a few _CS rows carry inf
        cov = mat.notna().mean(axis=1)
        mat = mat.loc[cov >= MIN_COVERAGE]
        if len(mat) < 10:
            continue
        x = np.clip(mat.fillna(0.0).to_numpy(), -10.0, 10.0)
        norms = np.linalg.norm(x, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        xn = x / norms
        sim = xn @ xn.T
        np.fill_diagonal(sim, -np.inf)
        names = list(mat.index)
        w = pd.DataFrame(np.nan, index=T2_UNIVERSE, columns=T2_UNIVERSE)
        for i, focal in enumerate(names):
            order = np.argsort(sim[i])[::-1][:K_TWINS]
            for j in order:
                s = sim[i, j]
                if not np.isfinite(s) or s <= 0:
                    continue
                w.loc[focal, names[j]] = s
                twin_rows.append({"month": month, "focal": focal,
                                  "neighbor": names[j], "sim": float(s)})
        maps[pd.Timestamp(month)] = w
    if not maps:
        raise RuntimeError("twin map empty — refusing to continue")
    return maps, pd.DataFrame(twin_rows)


def build() -> int:
    from scripts.loop.build_graph_features import weighted_neighbor

    log("pulling month-end fundamental factor snapshots ...")
    factors = month_end_factors()
    nvar = factors["variable"].nunique()
    log(f"{len(factors):,} snapshot rows, {nvar} factors, "
        f"{factors['month'].min().date()} -> {factors['month'].max().date()}")

    maps, twins = twin_maps(factors)
    log(f"twin maps for {len(maps)} months")

    con = loop_connection()
    try:
        piv = returns_panel(con)
    finally:
        con.close()

    def trailing(n: int) -> pd.DataFrame:
        out = {}
        for c in piv.columns:
            s = piv[c].dropna()
            out[c] = np.exp(np.log1p(s).rolling(n).sum()) - 1
        return pd.DataFrame(out).reindex(piv.index).ffill(limit=FFILL_LIMIT)

    metrics = {"SIM_NBR_RET_GAP_21D": trailing(21), "SIM_NBR_RET_GAP_63D": trailing(63)}

    # twin map of month m applies to dates in month m+1 (PIT)
    months = sorted(maps)
    frames: list[pd.DataFrame] = []
    for var, metric in metrics.items():
        parts = []
        for i, m in enumerate(months):
            start = m + pd.DateOffset(months=1)
            end = months[i + 1] + pd.DateOffset(months=1) if i + 1 < len(months) else pd.Timestamp("2200-01-01")
            mask = (piv.index >= start) & (piv.index < end)
            if not mask.any():
                continue
            seg = metric.loc[mask]
            parts.append(weighted_neighbor(seg, maps[m]) - seg)
        full = pd.concat(parts).sort_index()
        tidy = full.stack().rename("value").reset_index()
        tidy.columns = ["date", "country", "value"]
        tidy["variable"] = var
        frames.append(tidy)
        log(f"{var}: {len(tidy):,} rows")

    out = pd.concat(frames, ignore_index=True).dropna(subset=["value"])
    out["source"] = "fund_similarity"
    out.to_parquet(OUT_PARQUET, index=False)

    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS similarity_features_daily")
        con.execute(f"""
            CREATE TABLE similarity_features_daily AS
            SELECT CAST(date AS DATE) AS date, country, value, variable, source
            FROM read_parquet('{OUT_PARQUET}')
        """)
        con.execute("DROP TABLE IF EXISTS similarity_twins")
        con.register("twins_df", twins)
        con.execute("""
            CREATE TABLE similarity_twins AS
            SELECT CAST(month AS DATE) AS month, focal, neighbor, sim FROM twins_df
        """)
        n, lo, hi = con.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM similarity_features_daily").fetchone()
        if not n:
            raise RuntimeError("similarity_features_daily rebuilt empty")
        log(f"stored: {n:,} feature rows {lo} -> {hi}; {len(twins):,} twin rows")
    finally:
        con.close()
    return 0


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        rows = con.execute("""
            SELECT variable, COUNT(DISTINCT country) nc, MIN(date) lo, MAX(date) hi
            FROM similarity_features_daily GROUP BY 1 ORDER BY 1
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
    p = argparse.ArgumentParser(description="Build fundamental-twins similarity features.")
    p.add_argument("--check", action="store_true")
    args = p.parse_args()
    return check() if args.check else build()


if __name__ == "__main__":
    sys.exit(main())
