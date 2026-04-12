#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: collect_bilateral.py
=============================================================================

INPUT FILES:
- config/country_mapping.json: Maps 34 T2 countries to ISO-3 and BIS codes

OUTPUT FILES:
- Data/processed/bilateral_trade_matrix.parquet   (34x34 trade matrix)
- Data/processed/bilateral_banking_matrix.parquet  (reporting x counterparty banking claims)

VERSION: 1.0
LAST UPDATED: 2026-04-12
AUTHOR: Arjun Divecha

DESCRIPTION:
Collects bilateral (country-to-country) data for Neo4j graph enrichment:

  1. IMF IMTS  — bilateral merchandise trade (exports, imports) between all
                 34 T2 country pairs via SDMX 3.0 API. Annual frequency.
  2. BIS LBS  — cross-border banking claims from BIS Locational Banking
                 Statistics via BIS SDMX CSV API. Quarterly frequency.

These are NOT panel variables — they produce adjacency matrices that become
directed edges in the Neo4j knowledge graph:
  - (:Country)-[:TRADES_WITH]->(:Country)
  - (:Country)-[:HAS_BANKING_EXPOSURE_TO]->(:Country)

DEPENDENCIES:
- pandas, numpy, requests, pyarrow, tqdm

USAGE:
  python scripts/collect_bilateral.py              # collect both
  python scripts/collect_bilateral.py --trade-only  # trade matrix only
  python scripts/collect_bilateral.py --bank-only   # banking matrix only

NOTES:
- IMF IMTS uses SDMX 3.0 at api.imf.org — no API key needed
- BIS LBS uses CSV API at stats.bis.org — no API key needed
- Rate limits: IMF ~10 req/5s, BIS ~1 req/s
- Only ~25 of 34 T2 countries are BIS reporting countries
- ChinaA/ChinaH share CHN; U.S./NASDAQ/US SmallCap share USA
=============================================================================
"""

import argparse
import io
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from tqdm import tqdm

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = BASE_DIR / "config" / "country_mapping.json"
PROCESSED_DIR = BASE_DIR / "Data" / "processed"
TRADE_PQ = PROCESSED_DIR / "bilateral_trade_matrix.parquet"
BANK_PQ = PROCESSED_DIR / "bilateral_banking_matrix.parquet"

IMF_BASE = "https://api.imf.org/external/sdmx/3.0/data/dataflow/IMF.STA/IMTS/~"
BIS_BASE = "https://stats.bis.org/api/v2/data/dataflow/BIS/WS_LBS_D_PUB/1.0"

MULTI_MAP = {
    "ChinaA": "CHN", "ChinaH": "CHN",
    "U.S.": "USA", "NASDAQ": "USA", "US SmallCap": "USA",
}


def load_countries():
    """Load country mapping, return unique ISO3 list and reverse map."""
    with open(CONFIG_PATH) as f:
        data = json.load(f)

    iso3_set = {}
    t2_to_iso3 = {}
    for t2_name, codes in data["countries"].items():
        iso3 = codes["iso3"]
        t2_to_iso3[t2_name] = iso3
        if iso3 not in iso3_set:
            iso3_set[iso3] = t2_name

    iso3_to_bis = {}
    for t2_name, codes in data["countries"].items():
        iso3 = codes["iso3"]
        bis = codes.get("bis")
        if bis and iso3 not in iso3_to_bis:
            iso3_to_bis[iso3] = bis

    return list(iso3_set.keys()), iso3_set, t2_to_iso3, iso3_to_bis


def collect_trade(iso3_list: list, iso3_to_t2: dict) -> pd.DataFrame:
    """
    Collect bilateral merchandise trade from IMF IMTS (SDMX 3.0).

    For each unique ISO3 reporter, fetches annual exports (XG_FOB_USD) and
    imports (MG_CIF_USD) to/from every other T2 ISO3 counterpart.

    Returns DataFrame with columns:
      reporter_iso3, counterpart_iso3, exports_usd, imports_usd, year
    """
    print("=" * 60)
    print("Collecting bilateral trade from IMF IMTS ...")
    print("=" * 60)

    records = []
    failed = []

    for reporter in tqdm(iso3_list, desc="  IMF IMTS reporters"):
        others = [c for c in iso3_list if c != reporter]
        cp_str = "+".join(others)

        for indicator, var_name in [("XG_FOB_USD", "exports_usd"), ("MG_CIF_USD", "imports_usd")]:
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

                struct = structs[0]
                series_dims = struct.get("dimensions", {}).get("series", [])
                obs_dims = struct.get("dimensions", {}).get("observation", [])

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
                                records.append({
                                    "reporter_iso3": reporter,
                                    "counterpart_iso3": cp_iso3,
                                    "year": int(year),
                                    var_name: float(value),
                                })
                            except (ValueError, TypeError):
                                pass

            except Exception as e:
                failed.append(f"{reporter}/{indicator}: {e}")

            time.sleep(0.6)

    if not records:
        print("  No trade data collected")
        return pd.DataFrame()

    df = pd.DataFrame(records)

    exports = df[df["exports_usd"].notna()][["reporter_iso3", "counterpart_iso3", "year", "exports_usd"]]
    imports = df[df["imports_usd"].notna()][["reporter_iso3", "counterpart_iso3", "year", "imports_usd"]]

    merged = pd.merge(exports, imports, on=["reporter_iso3", "counterpart_iso3", "year"], how="outer")
    merged["exports_usd"] = merged["exports_usd"].fillna(0)
    merged["imports_usd"] = merged["imports_usd"].fillna(0)
    merged["total_trade_usd"] = merged["exports_usd"] + merged["imports_usd"]

    latest_year = merged["year"].max()
    latest = merged[merged["year"] == latest_year].copy()

    latest["trade_share_pct"] = 0.0
    for reporter in latest["reporter_iso3"].unique():
        mask = latest["reporter_iso3"] == reporter
        total = latest.loc[mask, "total_trade_usd"].sum()
        if total > 0:
            latest.loc[mask, "trade_share_pct"] = (
                latest.loc[mask, "total_trade_usd"] / total * 100
            )

    n_pairs = len(latest)
    n_reporters = latest["reporter_iso3"].nunique()
    print(f"\n  Trade matrix: {n_pairs} pairs, {n_reporters} reporters, year={latest_year}")
    if failed:
        print(f"  Failed queries: {len(failed)}")

    return latest


def collect_banking(iso3_list: list, iso3_to_bis: dict) -> pd.DataFrame:
    """
    Collect cross-border banking claims from BIS Locational Banking Statistics.

    Uses BIS SDMX CSV API. For each T2 reporting country, fetches total claims
    (stocks, all instruments, all currencies) against each T2 counterparty.

    Returns DataFrame with columns:
      reporter_iso3, counterpart_iso3, claims_usd_millions, quarter
    """
    print("\n" + "=" * 60)
    print("Collecting banking exposure from BIS LBS ...")
    print("=" * 60)

    bis_to_iso3 = {v: k for k, v in iso3_to_bis.items()}
    bis_reporters = list(iso3_to_bis.values())
    bis_counterparts = list(iso3_to_bis.values())

    records = []
    failed = []

    for reporter_bis in tqdm(bis_reporters, desc="  BIS LBS reporters"):
        cp_str = "+".join([c for c in bis_counterparts if c != reporter_bis])
        url = (
            f"{BIS_BASE}/Q.S.C.A.TO1.A.5J.A.{reporter_bis}.A.{cp_str}.N"
            f"?startPeriod=2020&format=csv"
        )

        try:
            r = requests.get(url, timeout=60)
            if r.status_code != 200:
                failed.append(f"{reporter_bis}: HTTP {r.status_code}")
                continue

            df = pd.read_csv(io.StringIO(r.text))
            if df.empty:
                continue

            required_cols = {"L_REP_CTY", "L_CP_COUNTRY", "TIME_PERIOD", "OBS_VALUE"}
            if not required_cols.issubset(df.columns):
                obs_col = [c for c in df.columns if "OBS" in c.upper()]
                if obs_col:
                    df = df.rename(columns={obs_col[0]: "OBS_VALUE"})

            if "OBS_VALUE" not in df.columns:
                continue

            df["OBS_VALUE"] = pd.to_numeric(df["OBS_VALUE"], errors="coerce")
            df = df.dropna(subset=["OBS_VALUE"])

            latest_q = df["TIME_PERIOD"].max()
            latest = df[df["TIME_PERIOD"] == latest_q]

            for _, row in latest.iterrows():
                cp_bis = row["L_CP_COUNTRY"]
                if cp_bis in bis_to_iso3:
                    records.append({
                        "reporter_iso3": bis_to_iso3.get(reporter_bis, reporter_bis),
                        "counterpart_iso3": bis_to_iso3[cp_bis],
                        "claims_usd_millions": float(row["OBS_VALUE"]),
                        "quarter": latest_q,
                    })

        except Exception as e:
            failed.append(f"{reporter_bis}: {e}")

        time.sleep(1.0)

    if not records:
        print("  No banking data collected")
        return pd.DataFrame()

    result = pd.DataFrame(records)
    result = result.groupby(
        ["reporter_iso3", "counterpart_iso3", "quarter"], as_index=False
    ).agg({"claims_usd_millions": "sum"})

    for reporter in result["reporter_iso3"].unique():
        mask = result["reporter_iso3"] == reporter
        total = result.loc[mask, "claims_usd_millions"].sum()
        if total > 0:
            result.loc[mask, "share_of_total_claims_pct"] = (
                result.loc[mask, "claims_usd_millions"] / total * 100
            )

    n_pairs = len(result)
    n_reporters = result["reporter_iso3"].nunique()
    quarter = result["quarter"].iloc[0] if not result.empty else "?"
    print(f"\n  Banking matrix: {n_pairs} pairs, {n_reporters} reporters, quarter={quarter}")
    if failed:
        print(f"  Failed queries: {len(failed)}")

    return result


def main():
    parser = argparse.ArgumentParser(description="ASADO Bilateral Data Collector")
    parser.add_argument("--trade-only", action="store_true", help="Collect trade data only")
    parser.add_argument("--bank-only", action="store_true", help="Collect banking data only")
    args = parser.parse_args()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    iso3_list, iso3_to_t2, t2_to_iso3, iso3_to_bis = load_countries()
    print(f"Universe: {len(iso3_list)} unique ISO3 codes from 34 T2 countries\n")

    do_trade = not args.bank_only
    do_bank = not args.trade_only

    if do_trade:
        trade_df = collect_trade(iso3_list, iso3_to_t2)
        if not trade_df.empty:
            trade_df.to_parquet(TRADE_PQ, index=False)
            print(f"  Saved: {TRADE_PQ}")
        else:
            print("  WARNING: No trade data to save")

    if do_bank:
        bank_df = collect_banking(iso3_list, iso3_to_bis)
        if not bank_df.empty:
            bank_df.to_parquet(BANK_PQ, index=False)
            print(f"  Saved: {BANK_PQ}")
        else:
            print("  WARNING: No banking data to save")

    print("\nDone.")


if __name__ == "__main__":
    main()
