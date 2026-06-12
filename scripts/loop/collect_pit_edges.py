#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/collect_pit_edges.py
=============================================================================

INPUT FILES:
- IMF IMTS SDMX 3.0 API (https://api.imf.org/external/sdmx/3.0/...):
    annual bilateral exports (XG_FOB_USD) + imports (MG_CIF_USD) for every
    T2 sovereign reporter against every T2 counterpart, ALL years >= 1999.
    (The monthly collector keeps only the latest year; here we keep history.)
- BIS LBS API (https://stats.bis.org/api/v2/...): quarterly cross-border
    bank claims per reporter-counterpart pair, startPeriod=1999, all quarters.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/processed/bilateral_portfolio_matrix.parquet
    IMF PIP annual bilateral portfolio holdings 1997-2024 (already historical).
- Neo4j bolt://localhost:7687 — iso3 -> t2_name mapping for sovereign-proxy
    Country nodes (one query; same mapping setup_neo4j.py uses, so the PIT
    matrices line up exactly with the current-weight graph).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/graph_edge_vintages.parquet
    Tidy historical edge vintages: edge_type (trade/bank/holder),
    vintage_end (period the weights describe), applies_from (vintage_end +
    publication lag — the first date a backtest may use these weights),
    focal (t2 name), neighbor (t2 name), weight (share, pct).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `graph_edge_vintages` (idempotent rebuild from the parquet).

VERSION: 1.0
LAST UPDATED: 2026-06-12
AUTHOR: Arjun Divecha (built by agent session, graph machine build-out)

DESCRIPTION:
Builds the POINT-IN-TIME bilateral edge history that the v1 graph features
lacked. v1 (build_graph_features.py) applies today's Neo4j edge weights over
the whole backtest — a lookahead caveat flagged in the README. This script
collects the full archive of trade / banking / portfolio weights so features
can use only weights that were publicly known at each date. A 10th grader's
version: instead of assuming today's friendship map was always true, we dig
up the old yearbooks and use each year's actual map.

PUBLICATION LAGS (conservative, documented choices):
- trade year Y      -> applies_from = (Y+1)-04-01  (IMTS annual ~3-4m lag)
- bank quarter-end Q -> applies_from = Q + 4 months (BIS LBS ~4m release lag)
- holder vintage D  -> applies_from = D + 9 months  (IMF PIP/CPIS benchmark
                       publishes ~9 months after the reference date)

DEPENDENCIES:
- requests, pandas, numpy, duckdb, neo4j (project venv)

USAGE:
 python scripts/loop/collect_pit_edges.py            # full collection (~4 min)
 python scripts/loop/collect_pit_edges.py --skip-api # rebuild duckdb table from existing parquet
 python scripts/loop/collect_pit_edges.py --check    # verify vintage counts

NOTES:
- FAIL-IS-FAIL: if an entire edge type yields nothing, the script aborts.
  Individual reporter failures are logged and skipped (per-source try/except).
- Weights are row-normalized shares within (edge_type, vintage, focal), so
  a missing counterpart redistributes weight rather than leaking it.
=============================================================================
"""

from __future__ import annotations

import argparse
import io
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.loop.loopdb import LOOP_DIR, T2_UNIVERSE, loop_connection  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PORTFOLIO_PARQUET = BASE_DIR / "Data" / "processed" / "bilateral_portfolio_matrix.parquet"
OUT_PARQUET = LOOP_DIR / "graph_edge_vintages.parquet"

IMF_BASE = "https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/IMTS/~"
BIS_BASE = "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_LBS_D_PUB/1.0"
NEO4J_URI = "bolt://localhost:7687"
NEO4J_AUTH = ("neo4j", "mythos2026")

START_YEAR = 1999


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} [pit_edges] {msg}", flush=True)


def iso3_to_t2_map() -> dict[str, str]:
    """Sovereign-proxy iso3 -> t2_name from Neo4j, restricted to the T2 universe."""
    from neo4j import GraphDatabase

    drv = GraphDatabase.driver(NEO4J_URI, auth=NEO4J_AUTH)
    try:
        with drv.session() as s:
            rows = s.run(
                "MATCH (c:Country) WHERE c.graph_role <> 'market_sleeve' "
                "RETURN c.iso3 AS iso3, c.t2_name AS t2"
            ).data()
    finally:
        drv.close()
    mapping = {r["iso3"]: r["t2"] for r in rows if r["t2"] in T2_UNIVERSE}
    if len(mapping) < 25:
        raise RuntimeError(f"iso3->t2 mapping too small ({len(mapping)}) — Neo4j incomplete?")
    return mapping


def iso3_to_bis_map() -> dict[str, str]:
    import json

    cfg = json.loads((BASE_DIR / "config" / "country_mapping.json").read_text())
    return {c["iso3"]: c.get("bis")
            for c in cfg["countries"].values() if c.get("bis") and c.get("iso3")}


# ── trade: IMF IMTS, all years ───────────────────────────────────────────────

def collect_trade_history(iso3_list: list[str]) -> pd.DataFrame:
    records: list[dict] = []
    failed: list[str] = []
    for n, reporter in enumerate(iso3_list, 1):
        others = [c for c in iso3_list if c != reporter]
        cp_str = "+".join(others)
        for indicator, var in [("XG_FOB_USD", "exports_usd"), ("MG_CIF_USD", "imports_usd")]:
            url = f"{IMF_BASE}/{reporter}.{indicator}.{cp_str}.A"
            try:
                r = requests.get(url, timeout=60, headers={"Accept": "application/json"})
                if r.status_code != 200:
                    failed.append(f"{reporter}/{indicator}: HTTP {r.status_code}")
                    continue
                data = r.json()
                structs = data.get("data", {}).get("structures", [])
                datasets = data.get("data", {}).get("dataSets", [])
                if not structs or not datasets:
                    continue
                series_dims = structs[0].get("dimensions", {}).get("series", [])
                obs_dims = structs[0].get("dimensions", {}).get("observation", [])
                cp_dim = next((d for d in series_dims if d["id"] == "COUNTERPART_COUNTRY"), None)
                if not cp_dim:
                    continue
                cp_vals = [v["id"] for v in cp_dim.get("values", [])]
                cp_pos = cp_dim.get("keyPosition", 2)
                time_vals = []
                if obs_dims:
                    time_vals = [v.get("value", v.get("id", "")) for v in obs_dims[0].get("values", [])]
                for series_key, series_data in datasets[0].get("series", {}).items():
                    key_parts = series_key.split(":")
                    cp_idx = int(key_parts[cp_pos]) if len(key_parts) > cp_pos else 0
                    cp_iso3 = cp_vals[cp_idx] if cp_idx < len(cp_vals) else None
                    if not cp_iso3 or cp_iso3 not in iso3_list:
                        continue
                    for obs_key, obs_val in series_data.get("observations", {}).items():
                        yr_idx = int(obs_key)
                        year = time_vals[yr_idx] if yr_idx < len(time_vals) else None
                        value = obs_val[0] if obs_val else None
                        if year and value is not None:
                            try:
                                yr = int(year)
                            except (ValueError, TypeError):
                                continue
                            if yr >= START_YEAR:
                                records.append({
                                    "reporter_iso3": reporter, "counterpart_iso3": cp_iso3,
                                    "year": yr, var: float(value),
                                })
            except Exception as exc:
                failed.append(f"{reporter}/{indicator}: {exc}")
            time.sleep(0.5)
        if n % 5 == 0:
            log(f"trade: {n}/{len(iso3_list)} reporters done ({len(records):,} obs)")
    if failed:
        log(f"trade: {len(failed)} failed queries (first 5: {failed[:5]})")
    if not records:
        raise RuntimeError("trade collection returned ZERO rows — aborting (FAIL-IS-FAIL)")

    df = pd.DataFrame(records)
    agg = df.groupby(["reporter_iso3", "counterpart_iso3", "year"], as_index=False).sum(min_count=1)
    agg["total"] = agg["exports_usd"].fillna(0) + agg["imports_usd"].fillna(0)
    agg = agg[agg["total"] > 0]
    agg["weight"] = agg["total"] / agg.groupby(["reporter_iso3", "year"])["total"].transform("sum") * 100
    out = agg.rename(columns={"reporter_iso3": "focal_iso3", "counterpart_iso3": "neighbor_iso3"})
    out["vintage_end"] = pd.to_datetime(out["year"].astype(str) + "-12-31")
    out["applies_from"] = pd.to_datetime((out["year"] + 1).astype(str) + "-04-01")
    out["edge_type"] = "trade"
    return out[["edge_type", "vintage_end", "applies_from", "focal_iso3", "neighbor_iso3", "weight"]]


# ── bank: BIS LBS, all quarters ──────────────────────────────────────────────

def collect_bank_history(iso3_to_bis: dict[str, str]) -> pd.DataFrame:
    bis_to_iso3 = {v: k for k, v in iso3_to_bis.items()}
    reporters = list(iso3_to_bis.values())
    frames: list[pd.DataFrame] = []
    failed: list[str] = []
    for n, rep in enumerate(reporters, 1):
        cp_str = "+".join([c for c in reporters if c != rep])
        url = (f"{BIS_BASE}/Q.S.C.A.TO1.A.5J.A.{rep}.A.{cp_str}.N"
               f"?startPeriod={START_YEAR}&format=csv")
        try:
            r = requests.get(url, timeout=90)
            if r.status_code != 200:
                failed.append(f"{rep}: HTTP {r.status_code}")
                continue
            df = pd.read_csv(io.StringIO(r.text))
            if df.empty or "OBS_VALUE" not in df.columns:
                continue
            df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
            df = df.dropna(subset=["OBS_VALUE"])
            df = df[df["L_CP_COUNTRY"].isin(bis_to_iso3)]
            if df.empty:
                continue
            keep = df[["L_CP_COUNTRY", "TIME_PERIOD", "OBS_VALUE"]].copy()
            keep["focal_iso3"] = bis_to_iso3[rep]
            keep["neighbor_iso3"] = keep["L_CP_COUNTRY"].map(bis_to_iso3)
            frames.append(keep[["focal_iso3", "neighbor_iso3", "TIME_PERIOD", "OBS_VALUE"]])
        except Exception as exc:
            failed.append(f"{rep}: {exc}")
        time.sleep(0.8)
        if n % 5 == 0:
            log(f"bank: {n}/{len(reporters)} reporters done")
    if failed:
        log(f"bank: {len(failed)} failed queries (first 5: {failed[:5]})")
    if not frames:
        raise RuntimeError("bank collection returned ZERO rows — aborting (FAIL-IS-FAIL)")

    df = pd.concat(frames, ignore_index=True)
    df = df.groupby(["focal_iso3", "neighbor_iso3", "TIME_PERIOD"], as_index=False)["OBS_VALUE"].sum()
    df = df[df["OBS_VALUE"] > 0]
    df["weight"] = df["OBS_VALUE"] / df.groupby(["focal_iso3", "TIME_PERIOD"])["OBS_VALUE"].transform("sum") * 100
    qe = pd.PeriodIndex(df["TIME_PERIOD"], freq="Q").to_timestamp(how="end").normalize()
    df["vintage_end"] = qe
    df["applies_from"] = (qe + pd.DateOffset(months=4)).to_period("M").to_timestamp()
    df["edge_type"] = "bank"
    return df[["edge_type", "vintage_end", "applies_from", "focal_iso3", "neighbor_iso3", "weight"]]


# ── holder: warehouse IMF PIP history ────────────────────────────────────────

def collect_holder_history() -> pd.DataFrame:
    if not PORTFOLIO_PARQUET.exists():
        raise FileNotFoundError(f"missing {PORTFOLIO_PARQUET}")
    df = pd.read_parquet(PORTFOLIO_PARQUET)
    df = df[(df["source"] == "imf_pip") & (df["amount_usd"] > 0)].copy()
    if df.empty:
        raise RuntimeError("no imf_pip rows in portfolio matrix — aborting (FAIL-IS-FAIL)")
    df["date"] = pd.to_datetime(df["date"])
    # focal = the country whose assets are held; neighbor = the holder.
    agg = df.groupby(["counterpart_iso3", "reporter_iso3", "date"], as_index=False)["amount_usd"].sum()
    agg = agg.rename(columns={"counterpart_iso3": "focal_iso3", "reporter_iso3": "neighbor_iso3"})
    agg["weight"] = (agg["amount_usd"]
                     / agg.groupby(["focal_iso3", "date"])["amount_usd"].transform("sum") * 100)
    agg["vintage_end"] = agg["date"]
    agg["applies_from"] = (agg["date"] + pd.DateOffset(months=9)).dt.to_period("M").dt.to_timestamp()
    agg["edge_type"] = "holder"
    return agg[["edge_type", "vintage_end", "applies_from", "focal_iso3", "neighbor_iso3", "weight"]]


# ── assembly ─────────────────────────────────────────────────────────────────

def to_t2(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    out = df.copy()
    out["focal"] = out["focal_iso3"].map(mapping)
    out["neighbor"] = out["neighbor_iso3"].map(mapping)
    out = out.dropna(subset=["focal", "neighbor"])
    out = out[out["focal"] != out["neighbor"]]
    return out[["edge_type", "vintage_end", "applies_from", "focal", "neighbor", "weight"]]


def store(df: pd.DataFrame) -> None:
    df = df.sort_values(["edge_type", "vintage_end", "focal", "neighbor"]).reset_index(drop=True)
    df.to_parquet(OUT_PARQUET, index=False)
    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS graph_edge_vintages")
        con.execute(f"""
            CREATE TABLE graph_edge_vintages AS
            SELECT edge_type, CAST(vintage_end AS DATE) AS vintage_end,
                   CAST(applies_from AS DATE) AS applies_from, focal, neighbor, weight
            FROM read_parquet('{OUT_PARQUET}')
        """)
        for et in ("trade", "bank", "holder"):
            n, nv, lo, hi = con.execute(
                "SELECT COUNT(*), COUNT(DISTINCT vintage_end), MIN(vintage_end), MAX(vintage_end) "
                "FROM graph_edge_vintages WHERE edge_type = ?", [et]).fetchone()
            if not n:
                raise RuntimeError(f"edge_type {et} stored empty — refusing to continue")
            log(f"stored {et}: {n:,} rows, {nv} vintages, {lo} -> {hi}")
    finally:
        con.close()


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        rows = con.execute("""
            SELECT edge_type, COUNT(DISTINCT vintage_end) AS nv,
                   MIN(vintage_end) AS lo, MAX(vintage_end) AS hi, COUNT(*) AS n
            FROM graph_edge_vintages GROUP BY 1 ORDER BY 1
        """).fetchall()
    finally:
        con.close()
    ok = len(rows) == 3
    for et, nv, lo, hi, n in rows:
        print(f"{et}: {nv} vintages, {lo} -> {hi}, {n:,} rows")
        if nv < 10:
            ok = False
    print("CHECK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    p = argparse.ArgumentParser(description="Collect point-in-time bilateral edge vintages.")
    p.add_argument("--check", action="store_true")
    p.add_argument("--skip-api", action="store_true",
                   help="Rebuild the duckdb table from the existing parquet only.")
    args = p.parse_args()
    if args.check:
        return check()

    if args.skip_api:
        if not OUT_PARQUET.exists():
            raise FileNotFoundError(f"--skip-api but {OUT_PARQUET} missing")
        store(pd.read_parquet(OUT_PARQUET))
        return 0

    mapping = iso3_to_t2_map()
    iso3_list = sorted(mapping)
    log(f"{len(iso3_list)} sovereign reporters: {iso3_list}")

    log("collecting holder history (warehouse, instant) ...")
    holder = to_t2(collect_holder_history(), mapping)
    log(f"holder: {len(holder):,} rows, {holder['vintage_end'].nunique()} vintages")

    log("collecting bank history (BIS LBS, ~1 min) ...")
    bank = to_t2(collect_bank_history(iso3_to_bis_map()), mapping)
    log(f"bank: {len(bank):,} rows, {bank['vintage_end'].nunique()} vintages")

    log("collecting trade history (IMF IMTS, ~2 min) ...")
    trade = to_t2(collect_trade_history(iso3_list), mapping)
    log(f"trade: {len(trade):,} rows, {trade['vintage_end'].nunique()} vintages")

    store(pd.concat([trade, bank, holder], ignore_index=True))
    log("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
