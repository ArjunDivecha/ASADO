#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: collect_imf.py
=============================================================================

INPUT FILES:
- config/country_mapping.json: Maps 34 T2 countries to source-specific codes

OUTPUT FILES:
- Data/processed/imf_factors_panel.parquet  (primary — tidy panel)
- Data/processed/imf_factors_panel.csv      (secondary — CSV copy)
- Data/processed/imf_variable_catalog.csv   (metadata per variable)

VERSION: 1.0
LAST UPDATED: 2026-04-12
AUTHOR: Arjun Divecha

DESCRIPTION:
Downloads data from 7 IMF datasets via the SDMX 3.0 REST API at
api.imf.org, aligns to the 34-country T2 Master universe, and outputs
a tidy panel. No API key required.

Datasets collected:
  1. CPI   — Consumer Price Index, monthly (IMF.STA)
  2. WEO   — World Economic Outlook forecasts, annual (IMF.RES)
  3. BOP_AGG — Balance of Payments aggregates, annual (IMF.STA)
  4. MFS_IR — Interest Rates, monthly (IMF.STA)
  5. ER    — Exchange Rates, monthly (IMF.STA)
  6. LS    — Labor Statistics, monthly (IMF.STA)
  7. ITG   — International Trade in Goods, monthly (IMF.STA)

API endpoint:
  https://api.imf.org/external/sdmx/3.0/data/dataflow/{AGENCY}/{FLOW}/~/{KEY}

Rate limit: 10 requests per 5 seconds — enforced via 0.6s sleep.

DEPENDENCIES:
- pandas, numpy, requests, tqdm, pyarrow

USAGE:
  python scripts/collect_imf.py              # normal run
  python scripts/collect_imf.py --force      # bypass 24h cache
  python scripts/collect_imf.py --dry-run    # preview, don't save

NOTES:
- Raw JSON cached in Data/raw/imf/ with 24h expiry
- Each dataset wrapped in try/except — never fails entirely
- Monthly-safe: if a dataset fails, existing data preserved
- Timestamped backup before every overwrite
- ISO3 country codes used throughout (per country_mapping.json)
=============================================================================
"""

import argparse
import json
import os
import shutil
import time as _time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
from tqdm import tqdm

# ── Paths ─────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "Data"
RAW_DIR = DATA_DIR / "raw" / "imf"
PROCESSED_DIR = DATA_DIR / "processed"
BACKUP_DIR = DATA_DIR / "backups"
CONFIG_DIR = BASE_DIR / "config"

PANEL_PQ = PROCESSED_DIR / "imf_factors_panel.parquet"
PANEL_CSV = PROCESSED_DIR / "imf_factors_panel.csv"
CATALOG_CSV = PROCESSED_DIR / "imf_variable_catalog.csv"
HISTORY_JSON = PROCESSED_DIR / "imf_run_history.json"

CACHE_HOURS = 24
API_BASE = "https://api.imf.org/external/sdmx/3.0/data/dataflow"
RATE_LIMIT_SLEEP = 0.6

# ── Country mapping ──────────────────────────────────────────────────────

def load_countries() -> Dict[str, Dict]:
    """Load country_mapping.json and return {t2_name: {...codes...}}."""
    with open(CONFIG_DIR / "country_mapping.json") as f:
        mapping = json.load(f)
    return mapping["countries"]


def build_iso3_to_t2(countries: Dict) -> Dict[str, List[str]]:
    """Build ISO3 -> [t2_name, ...] reverse map (handles CHN/USA dupes)."""
    iso3_map: Dict[str, List[str]] = {}
    for t2_name, codes in countries.items():
        iso3 = codes["iso3"]
        iso3_map.setdefault(iso3, []).append(t2_name)
    return iso3_map


def unique_iso3_list(countries: Dict) -> List[str]:
    """Return deduplicated list of ISO3 codes."""
    seen = set()
    result = []
    for codes in countries.values():
        iso3 = codes["iso3"]
        if iso3 not in seen:
            seen.add(iso3)
            result.append(iso3)
    return result

# ── Caching ───────────────────────────────────────────────────────────────

def _cache_path(dataset: str, key: str) -> Path:
    safe_key = key.replace("/", "_").replace("?", "_").replace("&", "_")
    return RAW_DIR / f"{dataset}_{safe_key}.json"


def _is_cached(path: Path, force: bool) -> bool:
    if force or not path.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age < timedelta(hours=CACHE_HOURS)

# ── SDMX 3.0 API helper ──────────────────────────────────────────────────

def fetch_sdmx_json(agency: str, flow: str, key: str,
                    params: str = "", force: bool = False) -> Optional[dict]:
    """
    Fetch data from the IMF SDMX 3.0 API and return parsed JSON.
    Caches raw response to disk.
    """
    cache = _cache_path(flow, key)
    if _is_cached(cache, force):
        with open(cache) as f:
            return json.load(f)

    url = f"{API_BASE}/{agency}/{flow}/~/{key}"
    if params:
        url += f"?{params}"

    try:
        r = requests.get(url, timeout=60,
                         headers={"Accept": "application/vnd.sdmx.data+json"})
        _time.sleep(RATE_LIMIT_SLEEP)
        if r.status_code != 200:
            return None
        data = r.json()
        cache.parent.mkdir(parents=True, exist_ok=True)
        with open(cache, "w") as f:
            json.dump(data, f)
        return data
    except Exception:
        return None


def parse_sdmx_series(data: dict) -> List[Tuple[str, str, float]]:
    """
    Parse SDMX 3.0 JSON into list of (period, dim_key, value) tuples.
    dim_key is a colon-separated string of dimension values.
    """
    results = []
    datasets = data.get("data", {}).get("dataSets", [])
    if not datasets:
        return results

    structs = data["data"]["structures"][0]
    series_dims = structs["dimensions"]["series"]
    obs_dims = structs["dimensions"]["observation"]
    time_vals = obs_dims[0]["values"] if obs_dims else []

    ds = datasets[0]
    for sk, sv in ds.get("series", {}).items():
        indices = sk.split(":")
        dim_parts = []
        for i, idx_str in enumerate(indices):
            idx = int(idx_str)
            dim = series_dims[i]
            vals = dim.get("values", [])
            if idx < len(vals):
                dim_parts.append(vals[idx].get("id", str(idx)))
            else:
                dim_parts.append(str(idx))
        dim_key = ":".join(dim_parts)

        for ok, ov in sv.get("observations", {}).items():
            idx = int(ok)
            if idx < len(time_vals):
                period = time_vals[idx].get("value", "")
            else:
                period = ""
            value = ov[0] if ov else None
            if value is not None and period:
                results.append((period, dim_key, float(value)))

    return results


def period_to_date(period: str) -> Optional[pd.Timestamp]:
    """Convert IMF period string to first-of-period date."""
    try:
        if "-M" in period:
            parts = period.split("-M")
            return pd.Timestamp(int(parts[0]), int(parts[1]), 1)
        elif "-Q" in period:
            parts = period.split("-Q")
            year, q = int(parts[0]), int(parts[1])
            month = q * 3
            return pd.Timestamp(year, month, 1)
        else:
            return pd.Timestamp(int(period), 12, 1)
    except Exception:
        return None

# ── Collector functions ───────────────────────────────────────────────────

def collect_cpi(countries: Dict, iso3_to_t2: Dict,
                iso3_list: List[str], force: bool) -> pd.DataFrame:
    """
    Collect monthly CPI index and YoY inflation for all countries.
    Endpoint: IMF.STA/CPI  Key: COUNTRY.CPI._T.IX.M
    """
    records = []
    for iso3 in tqdm(iso3_list, desc="  CPI"):
        data = fetch_sdmx_json("IMF.STA", "CPI",
                               f"{iso3}.CPI._T.IX.M",
                               "c[TIME_PERIOD]=ge:2000-M01", force)
        if not data:
            data = fetch_sdmx_json("IMF.STA", "CPI",
                                   f"{iso3}.CPI._T.YOY_PCH_PA_PT.M",
                                   "c[TIME_PERIOD]=ge:2000-M01", force)
            var_name = "IMF_CPI_YoY"
        else:
            var_name = "IMF_CPI_Index"

        if not data:
            continue

        parsed = parse_sdmx_series(data)
        for period, _, value in parsed:
            dt = period_to_date(period)
            if dt is None:
                continue
            for t2_name in iso3_to_t2.get(iso3, []):
                records.append({
                    "date": dt, "country": t2_name,
                    "value": value, "variable": var_name, "source": "imf_cpi"
                })

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    if "IMF_CPI_Index" in df["variable"].values:
        idx_df = df[df["variable"] == "IMF_CPI_Index"].copy()
        idx_df = idx_df.sort_values(["country", "date"])
        idx_df["yoy"] = idx_df.groupby("country")["value"].pct_change(12) * 100
        yoy_df = idx_df.dropna(subset=["yoy"]).copy()
        yoy_df["value"] = yoy_df["yoy"]
        yoy_df["variable"] = "IMF_CPI_Inflation_YoY"
        yoy_df = yoy_df.drop(columns=["yoy"])
        df = pd.concat([df, yoy_df], ignore_index=True)

    return df


def collect_weo(countries: Dict, iso3_to_t2: Dict,
                iso3_list: List[str], force: bool) -> pd.DataFrame:
    """
    Collect WEO annual forecasts (GDP growth, inflation, CA/GDP, debt/GDP,
    unemployment, population).
    Endpoint: IMF.RES/WEO  Key: COUNTRY.INDICATOR
    """
    indicators = {
        "NGDP_RPCH": "IMF_WEO_GDP_Growth",
        "PCPIPCH": "IMF_WEO_Inflation",
        "BCA_NGDPD": "IMF_WEO_CA_GDP",
        "GGXWDG_NGDP": "IMF_WEO_Debt_GDP",
        "LUR": "IMF_WEO_Unemployment",
        "LP": "IMF_WEO_Population",
    }

    batch_iso3 = "+".join(iso3_list)
    records = []

    for ind_code, var_name in tqdm(indicators.items(), desc="  WEO"):
        data = fetch_sdmx_json("IMF.RES", "WEO",
                               f"{batch_iso3}.{ind_code}",
                               "c[TIME_PERIOD]=ge:2000", force)
        if not data:
            continue

        datasets = data.get("data", {}).get("dataSets", [])
        if not datasets:
            continue

        structs = data["data"]["structures"][0]
        series_dims = structs["dimensions"]["series"]
        time_vals = structs["dimensions"]["observation"][0]["values"]
        country_vals = series_dims[0].get("values", [])

        ds = datasets[0]
        for sk, sv in ds.get("series", {}).items():
            indices = sk.split(":")
            ctry_idx = int(indices[0])
            if ctry_idx >= len(country_vals):
                continue
            iso3 = country_vals[ctry_idx].get("id", "")

            for ok, ov in sv.get("observations", {}).items():
                idx = int(ok)
                if idx >= len(time_vals):
                    continue
                period = time_vals[idx].get("value", "")
                value = ov[0] if ov else None
                if value is None or not period:
                    continue

                dt = period_to_date(period)
                if dt is None:
                    continue

                for t2_name in iso3_to_t2.get(iso3, []):
                    records.append({
                        "date": dt, "country": t2_name,
                        "value": float(value), "variable": var_name,
                        "source": "imf_weo"
                    })

    return pd.DataFrame(records) if records else pd.DataFrame()


def collect_bop(countries: Dict, iso3_to_t2: Dict,
                iso3_list: List[str], force: bool) -> pd.DataFrame:
    """
    Collect BOP aggregates (annual, USD).
    Endpoint: IMF.STA/BOP_AGG  Key: COUNTRY.INDICATOR.USD.A
    """
    indicators = {
        "CAB_NETCD": "IMF_BOP_Current_Account",
        "GS_CD": "IMF_BOP_Goods_Services_Credit",
        "GS_DB": "IMF_BOP_Goods_Services_Debit",
        "D_NNAFANIL": "IMF_BOP_Direct_Investment_Net",
        "P_NNAFANIL": "IMF_BOP_Portfolio_Investment_Net",
        "FAB_NNAFANIL_AFR": "IMF_BOP_Financial_Account_Bal",
    }

    batch_iso3 = "+".join(iso3_list)
    records = []

    for ind_code, var_name in tqdm(indicators.items(), desc="  BOP_AGG"):
        data = fetch_sdmx_json("IMF.STA", "BOP_AGG",
                               f"{batch_iso3}.{ind_code}.USD.A",
                               "c[TIME_PERIOD]=ge:2000", force)
        if not data:
            continue

        datasets = data.get("data", {}).get("dataSets", [])
        if not datasets:
            continue

        structs = data["data"]["structures"][0]
        series_dims = structs["dimensions"]["series"]
        time_vals = structs["dimensions"]["observation"][0]["values"]
        country_vals = series_dims[0].get("values", [])

        ds = datasets[0]
        for sk, sv in ds.get("series", {}).items():
            indices = sk.split(":")
            ctry_idx = int(indices[0])
            if ctry_idx >= len(country_vals):
                continue
            iso3 = country_vals[ctry_idx].get("id", "")

            for ok, ov in sv.get("observations", {}).items():
                idx = int(ok)
                if idx >= len(time_vals):
                    continue
                period = time_vals[idx].get("value", "")
                value = ov[0] if ov else None
                if value is None or not period:
                    continue

                dt = period_to_date(period)
                if dt is None:
                    continue

                for t2_name in iso3_to_t2.get(iso3, []):
                    records.append({
                        "date": dt, "country": t2_name,
                        "value": float(value), "variable": var_name,
                        "source": "imf_bop"
                    })

    return pd.DataFrame(records) if records else pd.DataFrame()


def collect_interest_rates(countries: Dict, iso3_to_t2: Dict,
                           iso3_list: List[str], force: bool) -> pd.DataFrame:
    """
    Collect monthly interest rates from MFS_IR.
    Endpoint: IMF.STA/MFS_IR  Key: COUNTRY.INDICATOR.M
    """
    indicators = {
        "MMRT_RT_PT_A_PT": "IMF_Money_Market_Rate",
        "DISR_RT_PT_A_PT": "IMF_Discount_Rate",
        "S13BOND_RT_PT_A_PT": "IMF_Govt_Bond_Yield",
        "GSTBILY_RT_PT_A_PT": "IMF_TBill_Rate",
    }

    batch_iso3 = "+".join(iso3_list)
    records = []

    for ind_code, var_name in tqdm(indicators.items(), desc="  MFS_IR"):
        data = fetch_sdmx_json("IMF.STA", "MFS_IR",
                               f"{batch_iso3}.{ind_code}.M",
                               "c[TIME_PERIOD]=ge:2000-M01", force)
        if not data:
            continue

        datasets = data.get("data", {}).get("dataSets", [])
        if not datasets:
            continue

        structs = data["data"]["structures"][0]
        series_dims = structs["dimensions"]["series"]
        time_vals = structs["dimensions"]["observation"][0]["values"]
        country_vals = series_dims[0].get("values", [])

        ds = datasets[0]
        for sk, sv in ds.get("series", {}).items():
            indices = sk.split(":")
            ctry_idx = int(indices[0])
            if ctry_idx >= len(country_vals):
                continue
            iso3 = country_vals[ctry_idx].get("id", "")

            for ok, ov in sv.get("observations", {}).items():
                idx = int(ok)
                if idx >= len(time_vals):
                    continue
                period = time_vals[idx].get("value", "")
                value = ov[0] if ov else None
                if value is None or not period:
                    continue

                dt = period_to_date(period)
                if dt is None:
                    continue

                for t2_name in iso3_to_t2.get(iso3, []):
                    records.append({
                        "date": dt, "country": t2_name,
                        "value": float(value), "variable": var_name,
                        "source": "imf_mfs_ir"
                    })

    return pd.DataFrame(records) if records else pd.DataFrame()


def collect_exchange_rates(countries: Dict, iso3_to_t2: Dict,
                           iso3_list: List[str], force: bool) -> pd.DataFrame:
    """
    Collect monthly exchange rates (national currency per USD).
    Endpoint: IMF.STA/ER  Key: COUNTRY.INDICATOR.PA_RT.M
    """
    batch_iso3 = "+".join(iso3_list)
    records = []

    data = fetch_sdmx_json("IMF.STA", "ER",
                           f"{batch_iso3}.XDC_USD.PA_RT.M",
                           "c[TIME_PERIOD]=ge:2000-M01", force)
    if not data:
        print("    Exchange rates: no data returned")
        return pd.DataFrame()

    datasets = data.get("data", {}).get("dataSets", [])
    if not datasets:
        return pd.DataFrame()

    structs = data["data"]["structures"][0]
    series_dims = structs["dimensions"]["series"]
    time_vals = structs["dimensions"]["observation"][0]["values"]
    country_vals = series_dims[0].get("values", [])

    ds = datasets[0]
    for sk, sv in ds.get("series", {}).items():
        indices = sk.split(":")
        ctry_idx = int(indices[0])
        if ctry_idx >= len(country_vals):
            continue
        iso3 = country_vals[ctry_idx].get("id", "")

        for ok, ov in sv.get("observations", {}).items():
            idx = int(ok)
            if idx >= len(time_vals):
                continue
            period = time_vals[idx].get("value", "")
            value = ov[0] if ov else None
            if value is None or not period:
                continue

            dt = period_to_date(period)
            if dt is None:
                continue

            for t2_name in iso3_to_t2.get(iso3, []):
                records.append({
                    "date": dt, "country": t2_name,
                    "value": float(value), "variable": "IMF_XRate_LCU_per_USD",
                    "source": "imf_er"
                })

    print(f"    Exchange rates: {len(records)} records")
    return pd.DataFrame(records) if records else pd.DataFrame()


def collect_labor(countries: Dict, iso3_to_t2: Dict,
                  iso3_list: List[str], force: bool) -> pd.DataFrame:
    """
    Collect monthly labor stats (unemployment rate, employment index).
    Endpoint: IMF.STA/LS  Key: COUNTRY.INDICATOR.TRANSFORMATION.M
    """
    indicators = {
        ("UP", "PT"): "IMF_Unemployment_Rate",
        ("E", "IX"): "IMF_Employment_Index",
    }

    batch_iso3 = "+".join(iso3_list)
    records = []

    for (ind_code, transf), var_name in tqdm(indicators.items(), desc="  LS"):
        data = fetch_sdmx_json("IMF.STA", "LS",
                               f"{batch_iso3}.{ind_code}.{transf}.M",
                               "c[TIME_PERIOD]=ge:2000-M01", force)
        if not data:
            continue

        datasets = data.get("data", {}).get("dataSets", [])
        if not datasets:
            continue

        structs = data["data"]["structures"][0]
        series_dims = structs["dimensions"]["series"]
        time_vals = structs["dimensions"]["observation"][0]["values"]
        country_vals = series_dims[0].get("values", [])

        ds = datasets[0]
        for sk, sv in ds.get("series", {}).items():
            indices = sk.split(":")
            ctry_idx = int(indices[0])
            if ctry_idx >= len(country_vals):
                continue
            iso3 = country_vals[ctry_idx].get("id", "")

            for ok, ov in sv.get("observations", {}).items():
                idx = int(ok)
                if idx >= len(time_vals):
                    continue
                period = time_vals[idx].get("value", "")
                value = ov[0] if ov else None
                if value is None or not period:
                    continue

                dt = period_to_date(period)
                if dt is None:
                    continue

                for t2_name in iso3_to_t2.get(iso3, []):
                    records.append({
                        "date": dt, "country": t2_name,
                        "value": float(value), "variable": var_name,
                        "source": "imf_ls"
                    })

    return pd.DataFrame(records) if records else pd.DataFrame()


def _parse_batch_sdmx(data: dict, iso3_to_t2: Dict,
                      var_name: str, source: str) -> List[dict]:
    """Shared helper to parse a batch SDMX response into tidy records."""
    records = []
    datasets = data.get("data", {}).get("dataSets", [])
    if not datasets:
        return records

    structs = data["data"]["structures"][0]
    series_dims = structs["dimensions"]["series"]
    time_vals = structs["dimensions"]["observation"][0]["values"]
    country_vals = series_dims[0].get("values", [])

    ds = datasets[0]
    for sk, sv in ds.get("series", {}).items():
        indices = sk.split(":")
        ctry_idx = int(indices[0])
        if ctry_idx >= len(country_vals):
            continue
        iso3 = country_vals[ctry_idx].get("id", "")

        for ok, ov in sv.get("observations", {}).items():
            idx = int(ok)
            if idx >= len(time_vals):
                continue
            period = time_vals[idx].get("value", "")
            value = ov[0] if ov else None
            if value is None or not period:
                continue

            dt = period_to_date(period)
            if dt is None:
                continue

            for t2_name in iso3_to_t2.get(iso3, []):
                records.append({
                    "date": dt, "country": t2_name,
                    "value": float(value), "variable": var_name,
                    "source": source
                })
    return records


def collect_trade(countries: Dict, iso3_to_t2: Dict,
                  iso3_list: List[str], force: bool) -> pd.DataFrame:
    """
    Collect monthly trade data from ITG (International Trade in Goods).
    Exports (FOB USD), Imports (CIF USD), Export/Import price indices,
    and YoY growth rates. Trade balance computed from exports - imports.
    Endpoint: IMF.STA/ITG  Key: COUNTRY.INDICATOR.TRANSFORMATION.FREQUENCY
    """
    batch_iso3 = "+".join(iso3_list)
    records = []

    queries = [
        ("XG", "FOB_USD", "M", "IMF_Exports_USD"),
        ("MG", "CIF_USD", "M", "IMF_Imports_USD"),
        ("EPI", "FOB_IX", "M", "IMF_Export_Price_Index"),
        ("MPI", "CIF_IX", "M", "IMF_Import_Price_Index"),
        ("XG", "FOB_YOY_PCH_PT", "M", "IMF_Exports_YoY"),
        ("MG", "CIF_YOY_PCH_PT", "M", "IMF_Imports_YoY"),
    ]

    for ind, transf, freq, var_name in tqdm(queries, desc="  ITG"):
        data = fetch_sdmx_json("IMF.STA", "ITG",
                               f"{batch_iso3}.{ind}.{transf}.{freq}",
                               "c[TIME_PERIOD]=ge:2000-M01", force)
        if not data:
            continue
        records.extend(_parse_batch_sdmx(data, iso3_to_t2, var_name, "imf_itg"))

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    exports = df[df["variable"] == "IMF_Exports_USD"].copy()
    imports = df[df["variable"] == "IMF_Imports_USD"].copy()
    if not exports.empty and not imports.empty:
        merged = exports.merge(imports, on=["date", "country"], suffixes=("_x", "_m"))
        merged["value"] = merged["value_x"] - merged["value_m"]
        merged["variable"] = "IMF_Trade_Balance_USD"
        merged["source"] = "imf_itg"
        balance = merged[["date", "country", "value", "variable", "source"]]
        df = pd.concat([df, balance], ignore_index=True)

    tot = df[df["variable"] == "IMF_Exports_USD"]
    if not tot.empty and not imports.empty:
        merged2 = exports.merge(imports, on=["date", "country"], suffixes=("_x", "_m"))
        merged2["value"] = merged2["value_x"] + merged2["value_m"]
        merged2["variable"] = "IMF_Trade_Openness_USD"
        merged2["source"] = "imf_itg"
        openness = merged2[["date", "country", "value", "variable", "source"]]
        df = pd.concat([df, openness], ignore_index=True)

    return df


# ── Assembly and I/O ──────────────────────────────────────────────────────

def build_catalog(df: pd.DataFrame) -> pd.DataFrame:
    """Build a variable metadata catalog from the panel."""
    if df.empty:
        return pd.DataFrame()

    rows = []
    for var in sorted(df["variable"].unique()):
        sub = df[df["variable"] == var]
        rows.append({
            "variable": var,
            "source": sub["source"].iloc[0],
            "n_countries": sub["country"].nunique(),
            "n_observations": len(sub),
            "date_min": sub["date"].min().strftime("%Y-%m-%d"),
            "date_max": sub["date"].max().strftime("%Y-%m-%d"),
            "value_min": sub["value"].min(),
            "value_max": sub["value"].max(),
            "value_mean": sub["value"].mean(),
        })
    return pd.DataFrame(rows)


def save_panel(df: pd.DataFrame, dry_run: bool):
    """Save the panel with backup and run history."""
    if dry_run:
        print("\n[DRY RUN] Would save:")
        print(f"  {PANEL_PQ}")
        print(f"  {PANEL_CSV}")
        print(f"  {CATALOG_CSV}")
        return

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    if PANEL_PQ.exists():
        ts = datetime.now().strftime("%Y_%m_%d_%H%M%S")
        backup = BACKUP_DIR / f"imf_factors_panel_{ts}.parquet"
        shutil.copy2(PANEL_PQ, backup)
        print(f"  Backup: {backup.name}")

    df.to_parquet(PANEL_PQ, index=False)
    df.to_csv(PANEL_CSV, index=False)

    catalog = build_catalog(df)
    catalog.to_csv(CATALOG_CSV, index=False)

    history = []
    if HISTORY_JSON.exists():
        with open(HISTORY_JSON) as f:
            history = json.load(f)

    history.append({
        "timestamp": datetime.now().isoformat(),
        "rows": len(df),
        "variables": int(df["variable"].nunique()),
        "countries": int(df["country"].nunique()),
        "sources": sorted(df["source"].unique().tolist()),
    })
    history = history[-24:]
    with open(HISTORY_JSON, "w") as f:
        json.dump(history, f, indent=2)

    print(f"\n  Saved: {PANEL_PQ.name} ({len(df):,} rows)")
    print(f"  Saved: {PANEL_CSV.name}")
    print(f"  Saved: {CATALOG_CSV.name} ({len(catalog)} variables)")


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ASADO IMF Data Collector")
    parser.add_argument("--force", action="store_true",
                        help="Bypass 24h download cache")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview changes without saving")
    args = parser.parse_args()

    print("=" * 60)
    print("ASADO IMF Data Collector (Program 3)")
    print("=" * 60)

    countries = load_countries()
    iso3_to_t2 = build_iso3_to_t2(countries)
    iso3_list = unique_iso3_list(countries)
    print(f"Countries: {len(countries)} T2 names, {len(iso3_list)} unique ISO3 codes")
    print()

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    collectors = [
        ("CPI (Consumer Prices)", collect_cpi),
        ("WEO (World Economic Outlook)", collect_weo),
        ("BOP_AGG (Balance of Payments)", collect_bop),
        ("MFS_IR (Interest Rates)", collect_interest_rates),
        ("ER (Exchange Rates)", collect_exchange_rates),
        ("LS (Labor Statistics)", collect_labor),
        ("ITG (International Trade in Goods)", collect_trade),
    ]

    all_dfs = []
    for name, func in collectors:
        print(f"Collecting {name} ...")
        try:
            df = func(countries, iso3_to_t2, iso3_list, args.force)
            if not df.empty:
                n_ctry = df["country"].nunique()
                n_var = df["variable"].nunique()
                n_rows = len(df)
                dmin = df["date"].min().strftime("%Y-%m")
                dmax = df["date"].max().strftime("%Y-%m")
                print(f"  OK: {n_rows:,} rows, {n_var} vars, {n_ctry} countries, {dmin} → {dmax}")
                all_dfs.append(df)
            else:
                print(f"  EMPTY: no data returned")
        except Exception as e:
            print(f"  FAILED: {e}")
        print()

    if not all_dfs:
        print("No data collected from any source.")
        return

    fresh = pd.concat(all_dfs, ignore_index=True)
    fresh = fresh.dropna(subset=["value"])
    fresh_sources = set(fresh["source"].unique())

    if PANEL_PQ.exists():
        existing = pd.read_parquet(PANEL_PQ)
        preserved = existing[~existing["source"].isin(fresh_sources)]
        if not preserved.empty:
            print(f"Preserving {len(preserved):,} rows from {preserved['source'].nunique()} "
                  f"sources not refreshed this run")
            fresh = pd.concat([fresh, preserved], ignore_index=True)

    panel = fresh.drop_duplicates(subset=["date", "country", "variable"])
    panel = panel.sort_values(["variable", "country", "date"]).reset_index(drop=True)

    print("=" * 60)
    print(f"Total: {len(panel):,} rows, {panel['variable'].nunique()} variables, "
          f"{panel['country'].nunique()} countries")
    print("=" * 60)

    save_panel(panel, args.dry_run)

    print("\nVariable summary:")
    catalog = build_catalog(panel)
    for _, row in catalog.iterrows():
        print(f"  {row['variable']:35s} | {row['n_countries']:2d} ctry | "
              f"{row['n_observations']:>6,} obs | {row['date_min'][:7]} → {row['date_max'][:7]}")


if __name__ == "__main__":
    main()
