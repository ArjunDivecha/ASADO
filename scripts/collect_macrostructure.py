#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: collect_macrostructure.py
=============================================================================

INPUT FILES:
- config/country_mapping.json: Maps 34 T2 countries to ISO3 / World Bank codes
- Data/processed/bilateral_portfolio_matrix.parquet: Annual IMF PIP benchmark
  plus optional U.S. TIC supplement used for derived ownership context

OUTPUT FILES:
- Data/processed/macrostructure_panel.parquet
- Data/processed/macrostructure_panel.csv
- Data/processed/macrostructure_variable_catalog.csv
- Data/processed/macrostructure_formula_catalog.json

VERSION: 1.3
LAST UPDATED: 2026-04-19
AUTHOR: Arjun Divecha

DESCRIPTION:
Collects ASADO's macrostructure panel as a tidy country-date-variable
 dataset. The current release lands five transparent blocks:

1. IMF Financial Soundness Indicators
   - bank capital, liquidity, and credit-quality stress metrics
2. World Bank QPSD debt-structure metrics
   - public debt composition by creditor residency, currency, and maturity
3. OECD institutional-depth and sticky-capital signals
   - pension assets / GDP
   - insurance assets / GDP
   - household direct equity share
4. Explicit derived signals
   - U.S. holder share from tracked IMF PIP ownership benchmarks
   - a transparent investor-base fragility composite
5. Phase 3 policy / official-sector footprint signals
   - central-bank balance-sheet size relative to GDP
   - central-bank claims on central government relative to GDP
   - central-bank sovereign-debt share proxy

DEPENDENCIES:
- pandas, requests, tqdm, pyarrow

USAGE:
  python scripts/collect_macrostructure.py
  python scripts/collect_macrostructure.py --force
  python scripts/collect_macrostructure.py --dry-run

NOTES:
- Uses IMF SDMX 3.0 at api.imf.org — no API key required
- Uses World Bank QPSD at api.worldbank.org — no API key required
- Raw JSON cached under Data/raw/macrostructure/ with 24h expiry
- ChinaA/ChinaH and U.S./NASDAQ/US SmallCap are duplicated only at the final
  panel stage, matching the rest of ASADO
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from tqdm import tqdm

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Data"
RAW_BASE_DIR = DATA_DIR / "raw" / "macrostructure"
IMF_RAW_DIR = RAW_BASE_DIR / "imf_fsi"
OECD_RAW_DIR = RAW_BASE_DIR / "oecd_financial_dashboard"
QPSD_RAW_DIR = RAW_BASE_DIR / "worldbank_qpsd"
PROCESSED_DIR = DATA_DIR / "processed"
BACKUP_DIR = DATA_DIR / "backups"
CONFIG_PATH = BASE_DIR / "config" / "country_mapping.json"
PORTFOLIO_PQ = PROCESSED_DIR / "bilateral_portfolio_matrix.parquet"
EXTERNAL_PANEL_PQ = PROCESSED_DIR / "external_factors_panel.parquet"

PANEL_PQ = PROCESSED_DIR / "macrostructure_panel.parquet"
PANEL_CSV = PROCESSED_DIR / "macrostructure_panel.csv"
CATALOG_CSV = PROCESSED_DIR / "macrostructure_variable_catalog.csv"
FORMULA_JSON = PROCESSED_DIR / "macrostructure_formula_catalog.json"

IMF_API_BASE = "https://api.imf.org/external/sdmx/3.0/data/dataflow"
OECD_API_BASE = "https://sdmx.oecd.org/public/rest/data"
WORLD_BANK_API_BASE = "https://api.worldbank.org/v2"
CACHE_HOURS = 24
RATE_LIMIT_SLEEP = 0.6
FSI_SECTOR = "S12CFSI"

FSI_INDICATORS = {
    "FSI688_CFSI_PT": "MS_Bank_Capital_Adequacy",
    "FSI765_CFSI_PT": "MS_Bank_Liquidity_Ratio",
    "AQ12_CFSI_PT": "MS_NPL_Ratio",
    "FSI17_CFSI_PT": "MS_NPL_Net_Provisions_to_Capital_Pct",
    "FSI288_CFSI_PT": "MS_Bank_Liquidity_Coverage_Ratio",
    "FSI289_CFSI_PT": "MS_Bank_Net_Stable_Funding_Ratio",
}

QPSD_COMPONENTS = {
    "total_debt_pct_gdp": {
        "variable": "MS_Public_Debt_Total_Pct_GDP",
        "series": {
            "CG": "DP.DOD.DECT.CR.CG.Z1",
            "BC": "DP.DOD.DECT.CR.BC.Z1",
        },
    },
    "domestic_creditors_pct_gdp": {
        "variable": "MS_Public_Debt_Domestic_Creditors_Pct_GDP",
        "series": {
            "CG": "DP.DOD.DECD.CR.CG.Z1",
            "BC": "DP.DOD.DECD.CR.BC.Z1",
        },
    },
    "external_creditors_pct_gdp": {
        "variable": "MS_Public_Debt_External_Creditors_Pct_GDP",
        "series": {
            "CG": "DP.DOD.DECX.CR.CG.Z1",
            "BC": "DP.DOD.DECX.CR.BC.Z1",
        },
    },
    "domestic_currency_pct_gdp": {
        "variable": "MS_Public_Debt_Domestic_Currency_Pct_GDP",
        "series": {
            "CG": "DP.DOD.DECN.CR.CG.Z1",
            "BC": "DP.DOD.DECN.CR.BC.Z1",
        },
    },
    "foreign_currency_pct_gdp": {
        "variable": "MS_Public_Debt_Foreign_Currency_Pct_GDP",
        "series": {
            "CG": "DP.DOD.DECF.CR.CG.Z1",
            "BC": "DP.DOD.DECF.CR.BC.Z1",
        },
    },
    "short_term_pct_gdp": {
        "variable": "MS_Public_Debt_Short_Term_Pct_GDP",
        "series": {
            "CG": "DP.DOD.DSTC.CR.CG.Z1",
            "BC": "DP.DOD.DSTC.CR.BC.Z1",
        },
    },
}

QPSD_DERIVED_VARIABLES = [
    {
        "variable": "MS_Public_Debt_Foreign_Held_Pct",
        "numerator": "external_creditors_pct_gdp",
        "denominator": "total_debt_pct_gdp",
        "description": "Share of public debt owed to external creditors.",
        "formula": "100 * external_creditors_pct_gdp / total_debt_pct_gdp",
    },
    {
        "variable": "MS_Public_Debt_Local_Currency_Pct",
        "numerator": "domestic_currency_pct_gdp",
        "denominator": "total_debt_pct_gdp",
        "description": "Share of public debt denominated in domestic currency.",
        "formula": "100 * domestic_currency_pct_gdp / total_debt_pct_gdp",
    },
    {
        "variable": "MS_Public_Debt_Short_Maturity_Pct",
        "numerator": "short_term_pct_gdp",
        "denominator": "total_debt_pct_gdp",
        "description": "Share of public debt with short maturity.",
        "formula": "100 * short_term_pct_gdp / total_debt_pct_gdp",
    },
]

OECD_INSTITUTIONAL_INVESTORS_FLOW = "OECD.SDD.NAD,DSD_FIN_DASH@DF_7II_INDIC,1.0"
OECD_HOUSEHOLD_DASHBOARD_FLOW = "OECD.SDD.NAD,DSD_FIN_DASH@DF_FIN_DASH_S1M,1.0"

OECD_INSTITUTIONAL_INVESTOR_MEASURES = {
    "LES129_FAS": "MS_Pension_Assets_GDP",
    "LES128_FAS": "MS_Insurance_Assets_GDP",
}

OECD_HOUSEHOLD_MEASURES = {
    "LES1M_F51AS": "MS_Household_Direct_Equity_Share",
}

INVESTOR_BASE_FRAGILITY_COMPONENTS = [
    {
        "variable": "MS_Public_Debt_Foreign_Held_Pct",
        "direction": "higher_is_more_fragile",
        "rationale": "Higher foreign-held public debt increases sudden-stop sensitivity.",
    },
    {
        "variable": "MS_Public_Debt_Local_Currency_Pct",
        "direction": "lower_is_more_fragile",
        "rationale": "Lower local-currency debt share increases funding and FX rollover risk.",
    },
    {
        "variable": "MS_Public_Debt_Short_Maturity_Pct",
        "direction": "higher_is_more_fragile",
        "rationale": "Shorter maturity structure raises refinancing risk.",
    },
    {
        "variable": "MS_NPL_Ratio",
        "direction": "higher_is_more_fragile",
        "rationale": "Higher NPL ratios increase balance-sheet stress in the banking system.",
    },
    {
        "variable": "MS_NPL_Net_Provisions_to_Capital_Pct",
        "direction": "higher_is_more_fragile",
        "rationale": "Higher unprovisioned loss burden weakens capital resilience.",
    },
    {
        "variable": "MS_Bank_Capital_Adequacy",
        "direction": "lower_is_more_fragile",
        "rationale": "Lower bank capital buffers reduce shock absorption.",
    },
    {
        "variable": "MS_Bank_Liquidity_Ratio",
        "direction": "lower_is_more_fragile",
        "rationale": "Lower liquid-asset coverage makes forced selling more likely.",
    },
    {
        "variable": "MS_Bank_Liquidity_Coverage_Ratio",
        "direction": "lower_is_more_fragile",
        "rationale": "Lower LCR implies weaker short-term liquidity resilience.",
    },
    {
        "variable": "MS_Bank_Net_Stable_Funding_Ratio",
        "direction": "lower_is_more_fragile",
        "rationale": "Lower stable funding raises rollover and funding fragility.",
    },
    {
        "variable": "MS_Pension_Assets_GDP",
        "direction": "lower_is_more_fragile",
        "rationale": "Smaller pension-sector balance sheets reduce the depth of sticky domestic capital.",
    },
    {
        "variable": "MS_Insurance_Assets_GDP",
        "direction": "lower_is_more_fragile",
        "rationale": "Smaller insurance-sector balance sheets reduce the domestic absorber base for stress.",
    },
    {
        "variable": "MS_Household_Direct_Equity_Share",
        "direction": "lower_is_more_fragile",
        "rationale": "Lower direct household equity ownership suggests a thinner local buy-and-hold investor base.",
    },
]

MIN_COMPONENTS_FOR_FRAGILITY = 4
STANDING_SWAP_LINE_COUNTRIES = {
    "Canada",
    "France",
    "Germany",
    "Italy",
    "Japan",
    "Netherlands",
    "Spain",
    "Switzerland",
    "U.K.",
}
TEMPORARY_SWAP_LINE_COUNTRIES = {
    "Australia",
    "Brazil",
    "Denmark",
    "Korea",
    "Mexico",
    "Singapore",
    "Sweden",
}
US_HOME_BACKSTOP_COUNTRIES = {"U.S.", "NASDAQ", "US SmallCap"}
STANDING_SWAP_LINE_START = pd.Timestamp(2013, 11, 1)
TEMPORARY_SWAP_LINE_START = pd.Timestamp(2020, 3, 1)
TEMPORARY_SWAP_LINE_END = pd.Timestamp(2021, 12, 1)

WEO_NOMINAL_GDP_USD_INDICATOR = "NGDPD"
WEO_DEBT_GDP_INDICATOR = "GGXWDG_NGDP"
MFS_CBS_TOTAL_ASSETS_INDICATOR = "S121_A_TA_ASEC_CB1SR"
MFS_CBS_CLAIMS_ON_GOVT_INDICATOR = "S121_A_ACO_S1311MIXED_CBS"
MFS_FREQUENCY_PRIORITY = {"M": 0, "Q": 1, "A": 2}


def load_countries() -> Dict[str, Dict[str, Any]]:
    """Load country mapping and return the `countries` block."""
    with open(CONFIG_PATH, encoding="utf-8") as handle:
        mapping = json.load(handle)
    return mapping["countries"]


def build_iso3_to_t2(countries: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    """Build ISO3 -> [T2 countries] reverse mapping."""
    iso3_to_t2: Dict[str, List[str]] = {}
    for t2_name, codes in countries.items():
        iso3 = codes["iso3"]
        iso3_to_t2.setdefault(iso3, []).append(t2_name)
    return iso3_to_t2


def build_wb_to_t2(countries: Dict[str, Dict[str, Any]]) -> Dict[str, List[str]]:
    """Build World Bank code -> [T2 countries] reverse mapping."""
    wb_to_t2: Dict[str, List[str]] = {}
    for t2_name, codes in countries.items():
        wb_code = codes.get("wb")
        if wb_code:
            wb_to_t2.setdefault(wb_code, []).append(t2_name)
    return wb_to_t2


def unique_iso3_list(countries: Dict[str, Dict[str, Any]]) -> List[str]:
    """Return tracked ISO3 codes without duplicates, preserving order."""
    seen = set()
    ordered: List[str] = []
    for codes in countries.values():
        iso3 = codes["iso3"]
        if iso3 not in seen:
            seen.add(iso3)
            ordered.append(iso3)
    return ordered


def unique_wb_list(countries: Dict[str, Dict[str, Any]]) -> List[str]:
    """Return tracked World Bank country codes without duplicates."""
    seen = set()
    ordered: List[str] = []
    for codes in countries.values():
        wb_code = codes.get("wb")
        if wb_code and wb_code not in seen:
            seen.add(wb_code)
            ordered.append(wb_code)
    return ordered


def _sanitize_cache_key(value: str) -> str:
    return (
        value.replace("/", "_")
        .replace("+", "_")
        .replace(".", "_")
        .replace("&", "_")
        .replace("=", "_")
        .replace(":", "_")
        .replace("?", "_")
        .replace("[", "_")
        .replace("]", "_")
        .replace(";", "_")
    )


def _cache_path(base_dir: Path, dataset: str, key: str, params: str = "") -> Path:
    safe_key = _sanitize_cache_key(key)
    safe_params = _sanitize_cache_key(params)
    suffix = f"_{safe_params}" if safe_params else ""
    return base_dir / f"{dataset}_{safe_key}{suffix}.json"


def _is_cached(path: Path, force: bool) -> bool:
    if force or not path.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age < timedelta(hours=CACHE_HOURS)


def fetch_oecd_csv(flow: str, start_period: str, force: bool = False) -> pd.DataFrame:
    """Fetch and cache OECD SDMX CSV responses."""
    cache_path = OECD_RAW_DIR / f"{_sanitize_cache_key(flow)}_{_sanitize_cache_key(start_period)}.csv"
    if not _is_cached(cache_path, force):
        url = f"{OECD_API_BASE}/{flow}/all"
        response = requests.get(
            url,
            params={"startPeriod": start_period, "format": "csvfilewithlabels"},
            timeout=120,
            headers={
                "Accept": "text/csv",
                "User-Agent": "Mozilla/5.0",
            },
        )
        time.sleep(RATE_LIMIT_SLEEP)
        if response.status_code != 200:
            return pd.DataFrame()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(response.text, encoding="utf-8")

    try:
        return pd.read_csv(cache_path, low_memory=False)
    except Exception:
        return pd.DataFrame()


def fetch_sdmx_json(
    agency: str,
    flow: str,
    key: str,
    params: str = "",
    force: bool = False,
) -> Optional[dict]:
    """Fetch and cache IMF SDMX 3.0 JSON responses."""
    cache_path = _cache_path(IMF_RAW_DIR, flow, key, params)
    if _is_cached(cache_path, force):
        with open(cache_path, encoding="utf-8") as handle:
            return json.load(handle)

    url = f"{IMF_API_BASE}/{agency}/{flow}/~/{key}"
    if params:
        url += f"?{params}"

    try:
        response = requests.get(
            url,
            timeout=60,
            headers={"Accept": "application/vnd.sdmx.data+json"},
        )
        time.sleep(RATE_LIMIT_SLEEP)
        if response.status_code != 200:
            return None
        data = response.json()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        return data
    except Exception:
        return None


def fetch_world_bank_json(path: str, params: Dict[str, Any], force: bool = False) -> Optional[Any]:
    """Fetch and cache World Bank API responses."""
    param_str = "&".join(f"{key}={value}" for key, value in sorted(params.items()))
    cache_path = _cache_path(QPSD_RAW_DIR, "qpsd", path, param_str)
    if _is_cached(cache_path, force):
        with open(cache_path, encoding="utf-8") as handle:
            return json.load(handle)

    url = f"{WORLD_BANK_API_BASE}{path}"
    try:
        response = requests.get(url, params=params, timeout=60)
        time.sleep(RATE_LIMIT_SLEEP)
        if response.status_code != 200:
            return None
        data = response.json()
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as handle:
            json.dump(data, handle)
        return data
    except Exception:
        return None


def period_to_date(period: str) -> Optional[pd.Timestamp]:
    """Convert IMF period strings to aligned first-of-period dates."""
    try:
        if "-M" in period:
            year, month = period.split("-M")
            return pd.Timestamp(int(year), int(month), 1)
        if "-Q" in period:
            year, quarter = period.split("-Q")
            return pd.Timestamp(int(year), int(quarter) * 3, 1)
        if len(period) == 4 and period.isdigit():
            return pd.Timestamp(int(period), 12, 1)
    except Exception:
        return None
    return None


def qpsd_period_to_date(period: str) -> Optional[pd.Timestamp]:
    """Convert World Bank QPSD period strings like 2025Q4 to aligned dates."""
    try:
        if len(period) == 6 and period[:4].isdigit() and period[4] == "Q":
            year = int(period[:4])
            quarter = int(period[5])
            return pd.Timestamp(year, quarter * 3, 1)
        if len(period) == 4 and period.isdigit():
            return pd.Timestamp(int(period), 12, 1)
    except Exception:
        return None
    return None


def _extract_series_values(data: dict) -> tuple[list[dict], list[dict], dict]:
    """Return series dimensions, time values, and series observations."""
    datasets = data.get("data", {}).get("dataSets", [])
    structures = data.get("data", {}).get("structures", [])
    if not datasets or not structures:
        return [], [], {}

    structure = structures[0]
    series_dims = structure.get("dimensions", {}).get("series", [])
    observation_dims = structure.get("dimensions", {}).get("observation", [])
    time_values = observation_dims[0].get("values", []) if observation_dims else []
    series = datasets[0].get("series", {})
    return series_dims, time_values, series


def collect_fsi(
    iso3_to_t2: Dict[str, List[str]],
    iso3_list: List[str],
    force: bool,
) -> pd.DataFrame:
    """Collect IMF FSI bank-fragility indicators."""
    print("=" * 60)
    print("Collecting IMF Financial Soundness Indicators ...")
    print("=" * 60)

    batch_iso3 = "+".join(iso3_list)
    records: List[Dict[str, Any]] = []

    for indicator_code, variable_name in tqdm(FSI_INDICATORS.items(), desc="  IMF FSIC"):
        for frequency, time_filter in [("Q", "c[TIME_PERIOD]=ge:2000-Q1"), ("A", "c[TIME_PERIOD]=ge:2000")]:
            key = f"{batch_iso3}.{FSI_SECTOR}.{indicator_code}.{frequency}"
            data = fetch_sdmx_json("IMF.STA", "FSIC", key, time_filter, force)
            if not data:
                continue

            series_dims, time_values, series = _extract_series_values(data)
            if not series_dims or not series:
                continue

            country_dim = next((dim for dim in series_dims if dim["id"] == "COUNTRY"), None)
            if not country_dim:
                continue

            country_values = [value.get("id") for value in country_dim.get("values", [])]
            country_position = country_dim["keyPosition"]

            for series_key, series_data in series.items():
                key_parts = series_key.split(":")
                if len(key_parts) <= country_position:
                    continue

                country_idx = int(key_parts[country_position])
                if country_idx >= len(country_values):
                    continue
                iso3 = country_values[country_idx]
                if iso3 not in iso3_to_t2:
                    continue

                for observation_key, observation_value in series_data.get("observations", {}).items():
                    time_idx = int(observation_key)
                    if time_idx >= len(time_values):
                        continue
                    period = time_values[time_idx].get("value", time_values[time_idx].get("id", ""))
                    dt = period_to_date(period)
                    value = observation_value[0] if observation_value else None
                    if dt is None or value is None:
                        continue

                    for t2_name in iso3_to_t2[iso3]:
                        records.append(
                            {
                                "date": dt,
                                "country": t2_name,
                                "value": float(value),
                                "variable": variable_name,
                                "source": "imf_fsi",
                            }
                        )

    if not records:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    df = pd.DataFrame(records)
    df = (
        df.sort_values(["country", "variable", "date"])
        .drop_duplicates(subset=["date", "country", "variable"], keep="last")
        .reset_index(drop=True)
    )
    return df


def collect_qpsd(
    wb_to_t2: Dict[str, List[str]],
    wb_codes: List[str],
    force: bool,
) -> pd.DataFrame:
    """Collect World Bank QPSD debt-structure variables plus transparent shares."""
    print("\n" + "=" * 60)
    print("Collecting World Bank QPSD debt structure ...")
    print("=" * 60)

    if not wb_codes:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    country_batch = ";".join(wb_codes)
    records: List[Dict[str, Any]] = []

    for component_key, metadata in tqdm(QPSD_COMPONENTS.items(), desc="  World Bank QPSD"):
        for gov_scope, indicator_code in metadata["series"].items():
            path = f"/country/{country_batch}/indicator/{indicator_code}"
            payload = fetch_world_bank_json(
                path,
                {"format": "json", "per_page": 20000},
                force=force,
            )
            if not payload or len(payload) < 2 or not isinstance(payload[1], list):
                continue

            for row in payload[1]:
                wb_code = row.get("countryiso3code")
                if wb_code not in wb_to_t2:
                    continue
                dt = qpsd_period_to_date(str(row.get("date", "")))
                value = row.get("value")
                if dt is None or value is None:
                    continue

                for t2_name in wb_to_t2[wb_code]:
                    records.append(
                        {
                            "date": dt,
                            "country": t2_name,
                            "component": component_key,
                            "gov_scope": gov_scope,
                            "value": float(value),
                        }
                    )

    if not records:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    raw_df = pd.DataFrame(records)
    raw_df["gov_scope_rank"] = raw_df["gov_scope"].map({"CG": 0, "BC": 1}).fillna(9)
    preferred = (
        raw_df.sort_values(["country", "component", "date", "gov_scope_rank"])
        .drop_duplicates(subset=["date", "country", "component"], keep="first")
        .reset_index(drop=True)
    )
    preferred["variable"] = preferred["component"].map(
        lambda component: QPSD_COMPONENTS[component]["variable"]
    )

    raw_panel = preferred[["date", "country", "value", "variable"]].copy()
    raw_panel["source"] = "qpsd"

    pivot = preferred.pivot_table(
        index=["date", "country"],
        columns="component",
        values="value",
        aggfunc="last",
    ).reset_index()

    derived_frames: List[pd.DataFrame] = []
    for spec in QPSD_DERIVED_VARIABLES:
        numerator = spec["numerator"]
        denominator = spec["denominator"]
        if numerator not in pivot.columns or denominator not in pivot.columns:
            continue

        subset = pivot[["date", "country", numerator, denominator]].copy()
        subset = subset[subset[numerator].notna() & subset[denominator].notna() & (subset[denominator] != 0)]
        if subset.empty:
            continue

        subset["value"] = subset[numerator] / subset[denominator] * 100.0
        subset["variable"] = spec["variable"]
        subset["source"] = "qpsd"
        derived_frames.append(subset[["date", "country", "value", "variable", "source"]])

    if not derived_frames:
        return raw_panel

    return pd.concat([raw_panel, *derived_frames], ignore_index=True)


def _finalize_oecd_panel(
    df: pd.DataFrame,
    iso3_to_t2: Dict[str, List[str]],
    measure_map: Dict[str, str],
    expected_unit: str,
    source: str,
) -> pd.DataFrame:
    """Normalize OECD dashboard extracts to ASADO's tidy panel schema."""
    if df.empty:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    required_columns = {"REF_AREA", "MEASURE", "UNIT_MEASURE", "TIME_PERIOD", "OBS_VALUE"}
    if not required_columns.issubset(df.columns):
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    subset = df[
        df["REF_AREA"].isin(iso3_to_t2)
        & df["MEASURE"].isin(measure_map)
        & df["UNIT_MEASURE"].eq(expected_unit)
        & df["TIME_PERIOD"].notna()
        & df["OBS_VALUE"].notna()
    ].copy()
    if subset.empty:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    subset["date"] = subset["TIME_PERIOD"].astype(str).map(period_to_date)
    subset["value"] = pd.to_numeric(subset["OBS_VALUE"], errors="coerce")
    subset["variable"] = subset["MEASURE"].map(measure_map)
    subset["freq_rank"] = subset.get("FREQ", pd.Series(index=subset.index)).map({"Q": 0, "A": 1}).fillna(9)
    subset = subset.dropna(subset=["date", "value", "variable"])
    if subset.empty:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    records: List[Dict[str, Any]] = []
    for row in subset.to_dict("records"):
        for t2_name in iso3_to_t2[row["REF_AREA"]]:
            records.append(
                {
                    "date": row["date"],
                    "country": t2_name,
                    "value": float(row["value"]),
                    "variable": row["variable"],
                    "source": source,
                    "freq_rank": int(row["freq_rank"]),
                }
            )

    if not records:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    result = pd.DataFrame(records)
    result = (
        result.sort_values(["country", "variable", "date", "freq_rank"])
        .drop_duplicates(subset=["date", "country", "variable"], keep="first")
        .drop(columns=["freq_rank"])
        .reset_index(drop=True)
    )
    return result


def collect_oecd_institutional_depth(
    iso3_to_t2: Dict[str, List[str]],
    force: bool,
) -> pd.DataFrame:
    """Collect pension and insurance depth as a share of GDP from OECD dashboards."""
    print("\n" + "=" * 60)
    print("Collecting OECD institutional-depth indicators ...")
    print("=" * 60)

    df = fetch_oecd_csv(OECD_INSTITUTIONAL_INVESTORS_FLOW, "2010", force)
    return _finalize_oecd_panel(
        df=df,
        iso3_to_t2=iso3_to_t2,
        measure_map=OECD_INSTITUTIONAL_INVESTOR_MEASURES,
        expected_unit="PT_B1GQ",
        source="oecd_institutional_investors",
    )


def collect_oecd_household_sticky_capital(
    iso3_to_t2: Dict[str, List[str]],
    force: bool,
) -> pd.DataFrame:
    """Collect the household direct-equity share proxy from the OECD household dashboard."""
    print("\n" + "=" * 60)
    print("Collecting OECD household sticky-capital proxy ...")
    print("=" * 60)

    df = fetch_oecd_csv(OECD_HOUSEHOLD_DASHBOARD_FLOW, "2010", force)
    return _finalize_oecd_panel(
        df=df,
        iso3_to_t2=iso3_to_t2,
        measure_map=OECD_HOUSEHOLD_MEASURES,
        expected_unit="PT_FAS_S1M",
        source="oecd_household_dashboard",
    )


def collect_weo_indicator(
    iso3_to_t2: Dict[str, List[str]],
    iso3_list: List[str],
    indicator_code: str,
    variable_name: str,
    force: bool,
) -> pd.DataFrame:
    """Collect an annual WEO indicator for helper denominators."""
    batch_iso3 = "+".join(iso3_list)
    data = fetch_sdmx_json(
        "IMF.RES",
        "WEO",
        f"{batch_iso3}.{indicator_code}",
        "c[TIME_PERIOD]=ge:2000",
        force,
    )
    if not data:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    datasets = data.get("data", {}).get("dataSets", [])
    structures = data.get("data", {}).get("structures", [])
    if not datasets or not structures:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    series_dims = structures[0].get("dimensions", {}).get("series", [])
    observation_dims = structures[0].get("dimensions", {}).get("observation", [])
    if not series_dims or not observation_dims:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    country_dim = next((dim for dim in series_dims if dim["id"] == "COUNTRY"), None)
    if not country_dim:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    country_position = country_dim["keyPosition"]
    country_values = [value.get("id") for value in country_dim.get("values", [])]
    time_values = observation_dims[0].get("values", [])
    records: List[Dict[str, Any]] = []

    for series_key, series_data in datasets[0].get("series", {}).items():
        key_parts = series_key.split(":")
        if len(key_parts) <= country_position:
            continue

        country_idx = int(key_parts[country_position])
        if country_idx >= len(country_values):
            continue
        iso3 = country_values[country_idx]
        if iso3 not in iso3_to_t2:
            continue

        for observation_key, observation_value in series_data.get("observations", {}).items():
            time_idx = int(observation_key)
            if time_idx >= len(time_values):
                continue
            period = time_values[time_idx].get("value", time_values[time_idx].get("id", ""))
            dt = period_to_date(period)
            value = observation_value[0] if observation_value else None
            if dt is None or value is None:
                continue

            for t2_name in iso3_to_t2[iso3]:
                records.append(
                    {
                        "date": dt,
                        "country": t2_name,
                        "value": float(value),
                        "variable": variable_name,
                        "source": "imf_weo_helper",
                    }
                )

    if not records:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    df = pd.DataFrame(records)
    return (
        df.sort_values(["country", "variable", "date"])
        .drop_duplicates(subset=["date", "country", "variable"], keep="last")
        .reset_index(drop=True)
    )


def collect_mfs_cbs_indicator(
    iso3_to_t2: Dict[str, List[str]],
    iso3_list: List[str],
    indicator_code: str,
    force: bool,
) -> pd.DataFrame:
    """Collect a central-bank balance-sheet indicator from IMF MFS_CBS."""
    batch_iso3 = "+".join(iso3_list)
    data = fetch_sdmx_json("IMF.STA", "MFS_CBS", f"{batch_iso3}.{indicator_code}", force=force)
    if not data:
        return pd.DataFrame(columns=["date", "country", "value", "frequency", "indicator_code"])

    series_dims, time_values, series = _extract_series_values(data)
    if not series_dims or not series:
        return pd.DataFrame(columns=["date", "country", "value", "frequency", "indicator_code"])

    country_dim = next((dim for dim in series_dims if dim["id"] == "COUNTRY"), None)
    frequency_dim = next((dim for dim in series_dims if dim["id"] == "FREQUENCY"), None)
    if not country_dim or not frequency_dim:
        return pd.DataFrame(columns=["date", "country", "value", "frequency", "indicator_code"])

    country_position = country_dim["keyPosition"]
    frequency_position = frequency_dim["keyPosition"]
    country_values = [value.get("id") for value in country_dim.get("values", [])]
    frequency_values = [value.get("id") for value in frequency_dim.get("values", [])]
    records: List[Dict[str, Any]] = []

    for series_key, series_data in series.items():
        key_parts = series_key.split(":")
        if len(key_parts) <= max(country_position, frequency_position):
            continue

        country_idx = int(key_parts[country_position])
        frequency_idx = int(key_parts[frequency_position])
        if country_idx >= len(country_values) or frequency_idx >= len(frequency_values):
            continue

        iso3 = country_values[country_idx]
        frequency = frequency_values[frequency_idx]
        if iso3 not in iso3_to_t2:
            continue

        for observation_key, observation_value in series_data.get("observations", {}).items():
            time_idx = int(observation_key)
            if time_idx >= len(time_values):
                continue
            period = time_values[time_idx].get("value", time_values[time_idx].get("id", ""))
            dt = period_to_date(period)
            value = observation_value[0] if observation_value else None
            if dt is None or value is None:
                continue

            for t2_name in iso3_to_t2[iso3]:
                records.append(
                    {
                        "date": dt,
                        "country": t2_name,
                        "value": float(value),
                        "frequency": frequency,
                        "indicator_code": indicator_code,
                    }
                )

    if not records:
        return pd.DataFrame(columns=["date", "country", "value", "frequency", "indicator_code"])

    return pd.DataFrame(records)


def _attach_same_year_annual_value(
    df: pd.DataFrame,
    annual_df: pd.DataFrame,
    annual_value_name: str,
) -> pd.DataFrame:
    """Attach an annual helper series to higher-frequency rows by calendar year."""
    if df.empty or annual_df.empty:
        return pd.DataFrame()

    left = df.copy()
    right = annual_df.copy()
    left["date"] = pd.to_datetime(left["date"], errors="coerce")
    right["date"] = pd.to_datetime(right["date"], errors="coerce")
    left = left.dropna(subset=["date", "country", "value"])
    right = right.dropna(subset=["date", "country", "value"])
    if left.empty or right.empty:
        return pd.DataFrame()

    left["year"] = left["date"].dt.year
    right["year"] = right["date"].dt.year
    right = (
        right.sort_values(["country", "year", "date"])
        .drop_duplicates(subset=["country", "year"], keep="last")
        .rename(columns={"value": annual_value_name})
    )
    merged = left.merge(
        right[["country", "year", annual_value_name]],
        on=["country", "year"],
        how="left",
    )
    return merged


def derive_mfs_ratio_to_gdp(
    raw_mfs_df: pd.DataFrame,
    nominal_gdp_df: pd.DataFrame,
    variable_name: str,
) -> pd.DataFrame:
    """Scale a raw USD MFS_CBS series by same-year nominal GDP in USD."""
    merged = _attach_same_year_annual_value(raw_mfs_df, nominal_gdp_df, "nominal_gdp_usd")
    if merged.empty:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    merged = merged[
        merged["nominal_gdp_usd"].notna()
        & (merged["nominal_gdp_usd"] != 0)
        & merged["value"].notna()
    ].copy()
    if merged.empty:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    merged["value"] = merged["value"] / merged["nominal_gdp_usd"] * 100.0
    merged["freq_rank"] = merged["frequency"].map(MFS_FREQUENCY_PRIORITY).fillna(9)
    merged["variable"] = variable_name
    merged["source"] = "imf_mfs_cbs"

    result = (
        merged.sort_values(["country", "variable", "date", "freq_rank"])
        .drop_duplicates(subset=["date", "country", "variable"], keep="first")
        .reset_index(drop=True)
    )
    return result[["date", "country", "value", "variable", "source"]]


def derive_central_bank_sovdebt_share(
    panel: pd.DataFrame,
    debt_ratio_fallback: pd.DataFrame,
) -> pd.DataFrame:
    """
    Derive the central-bank sovereign-debt share proxy.

    Numerator: central-bank claims on central government as a share of GDP.
    Denominator preference:
      1. QPSD total public debt / GDP
      2. WEO debt / GDP annual fallback mapped by calendar year
    """
    claims = panel[panel["variable"] == "MS_CentralBank_Claims_on_Government_Pct_GDP"].copy()
    if claims.empty:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    claims["date"] = pd.to_datetime(claims["date"], errors="coerce")
    claims["value"] = pd.to_numeric(claims["value"], errors="coerce")
    claims = claims.dropna(subset=["date", "country", "value"]).sort_values(["country", "date"])
    if claims.empty:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    qpsd_debt = panel[panel["variable"] == "MS_Public_Debt_Total_Pct_GDP"][["date", "country", "value"]].copy()
    qpsd_debt["date"] = pd.to_datetime(qpsd_debt["date"], errors="coerce")
    qpsd_debt["value"] = pd.to_numeric(qpsd_debt["value"], errors="coerce")
    qpsd_debt = qpsd_debt.dropna(subset=["date", "country", "value"]).sort_values(["country", "date"])

    merged_parts: List[pd.DataFrame] = []
    for country in sorted(claims["country"].unique()):
        country_claims = claims[claims["country"] == country].sort_values("date").copy()
        country_debt = qpsd_debt[qpsd_debt["country"] == country].sort_values("date").copy()

        if not country_debt.empty:
            merged = pd.merge_asof(
                country_claims,
                country_debt[["date", "value"]].rename(columns={"value": "debt_ratio_pct_gdp"}),
                on="date",
                direction="backward",
            )
        else:
            merged = country_claims.copy()
            merged["debt_ratio_pct_gdp"] = pd.NA

        merged["country"] = country
        merged_parts.append(merged)

    if not merged_parts:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    merged = pd.concat(merged_parts, ignore_index=True)

    if not debt_ratio_fallback.empty:
        fallback = _attach_same_year_annual_value(
            merged[merged["debt_ratio_pct_gdp"].isna()][["date", "country", "value"]].copy(),
            debt_ratio_fallback,
            "fallback_debt_ratio_pct_gdp",
        )
        if not fallback.empty:
            fallback = fallback[["date", "country", "fallback_debt_ratio_pct_gdp"]].copy()
            merged = merged.merge(fallback, on=["date", "country"], how="left")
            merged["debt_ratio_pct_gdp"] = merged["debt_ratio_pct_gdp"].fillna(
                merged["fallback_debt_ratio_pct_gdp"]
            )
            merged = merged.drop(columns=["fallback_debt_ratio_pct_gdp"])

    merged = merged[
        merged["debt_ratio_pct_gdp"].notna()
        & (pd.to_numeric(merged["debt_ratio_pct_gdp"], errors="coerce") != 0)
    ].copy()
    if merged.empty:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    merged["debt_ratio_pct_gdp"] = pd.to_numeric(merged["debt_ratio_pct_gdp"], errors="coerce")
    merged = merged[merged["debt_ratio_pct_gdp"].notna() & (merged["debt_ratio_pct_gdp"] != 0)].copy()
    if merged.empty:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    merged["value"] = merged["value"] / merged["debt_ratio_pct_gdp"] * 100.0
    merged["variable"] = "MS_CentralBank_SovDebt_Share"
    merged["source"] = "macrostructure_derived"
    return merged[["date", "country", "value", "variable", "source"]]


def derive_portfolio_context(
    countries: Dict[str, Dict[str, Any]],
) -> pd.DataFrame:
    """
    Derive a country-level U.S. holder share from tracked IMF PIP benchmarks.

    This uses the annual benchmark only because TIC is a U.S.-only monthly
    supplement and does not provide a comparable all-holder denominator.
    """
    if not PORTFOLIO_PQ.exists():
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    try:
        df = pd.read_parquet(PORTFOLIO_PQ)
    except Exception:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    if df.empty or "source" not in df.columns:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    annual = df[df["source"] == "imf_pip"].copy()
    if annual.empty:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    annual["date"] = pd.to_datetime(annual["date"], errors="coerce")
    annual = annual.dropna(subset=["date"])
    annual["amount_usd"] = pd.to_numeric(annual["amount_usd"], errors="coerce")
    annual = annual.dropna(subset=["amount_usd"])
    if annual.empty:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    inbound_totals = (
        annual.groupby(["date", "counterpart_iso3"], as_index=False)
        .agg(total_tracked_inbound_usd=("amount_usd", "sum"))
    )
    us_holdings = (
        annual[annual["reporter_iso3"] == "USA"]
        .groupby(["date", "counterpart_iso3"], as_index=False)
        .agg(us_holdings_usd=("amount_usd", "sum"))
    )
    merged = inbound_totals.merge(us_holdings, on=["date", "counterpart_iso3"], how="left")
    merged["us_holdings_usd"] = merged["us_holdings_usd"].fillna(0.0)
    merged = merged[merged["total_tracked_inbound_usd"] > 0].copy()
    if merged.empty:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    merged["value"] = merged["us_holdings_usd"] / merged["total_tracked_inbound_usd"] * 100.0

    iso3_to_t2 = build_iso3_to_t2(countries)
    records: List[Dict[str, Any]] = []
    for row in merged.to_dict("records"):
        counterpart_iso3 = row["counterpart_iso3"]
        if counterpart_iso3 not in iso3_to_t2:
            continue
        for t2_name in iso3_to_t2[counterpart_iso3]:
            records.append(
                {
                    "date": row["date"],
                    "country": t2_name,
                    "value": float(row["value"]),
                    "variable": "MS_US_Holder_Share_Pct",
                    "source": "portfolio_ownership",
                }
            )

    return pd.DataFrame(records, columns=["date", "country", "value", "variable", "source"])


def _percentile_fragility_score(series: pd.Series, direction: str) -> pd.Series:
    ascending = direction == "higher_is_more_fragile"
    return series.rank(method="average", pct=True, ascending=ascending) * 100.0


def derive_investor_base_fragility(panel: pd.DataFrame) -> pd.DataFrame:
    """Build the first transparent macrostructure composite from raw variables."""
    needed = {spec["variable"] for spec in INVESTOR_BASE_FRAGILITY_COMPONENTS}
    available = panel[panel["variable"].isin(needed)].copy()
    if available.empty:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    pivot = available.pivot_table(
        index=["date", "country"],
        columns="variable",
        values="value",
        aggfunc="last",
    ).reset_index()
    if pivot.empty:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    score_columns: List[str] = []
    for spec in INVESTOR_BASE_FRAGILITY_COMPONENTS:
        variable = spec["variable"]
        if variable not in pivot.columns:
            continue

        score_column = f"score__{variable}"
        pivot[score_column] = (
            pivot.groupby("date")[variable]
            .transform(lambda col: _percentile_fragility_score(col, spec["direction"]))
        )
        score_columns.append(score_column)

    if not score_columns:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    scores = pivot[["date", "country", *score_columns]].copy()
    scores["component_count"] = scores[score_columns].notna().sum(axis=1)
    scores["value"] = scores[score_columns].mean(axis=1, skipna=True)
    scores = scores[scores["component_count"] >= MIN_COMPONENTS_FOR_FRAGILITY].copy()
    if scores.empty:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    scores["variable"] = "MS_Investor_Base_Fragility"
    scores["source"] = "macrostructure_derived"
    return scores[["date", "country", "value", "variable", "source"]]


def derive_reserve_adequacy() -> pd.DataFrame:
    """Build a transparent reserve-adequacy score from existing external inputs."""
    if not EXTERNAL_PANEL_PQ.exists():
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    try:
        external = pd.read_parquet(EXTERNAL_PANEL_PQ)
    except Exception:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    needed = {"WB_Import_Cover_Months", "WB_External_Debt_GNI"}
    subset = external[external["variable"].isin(needed)].copy()
    if subset.empty:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    subset["date"] = pd.to_datetime(subset["date"], errors="coerce")
    subset["value"] = pd.to_numeric(subset["value"], errors="coerce")
    subset = subset.dropna(subset=["date", "country", "value", "variable"])
    if subset.empty:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    pivot = subset.pivot_table(
        index=["date", "country"],
        columns="variable",
        values="value",
        aggfunc="last",
    ).reset_index()
    if pivot.empty:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    score_columns: List[str] = []
    if "WB_Import_Cover_Months" in pivot.columns:
        pivot["score__import_cover"] = (
            pivot.groupby("date")["WB_Import_Cover_Months"]
            .transform(lambda col: col.rank(method="average", pct=True, ascending=True) * 100.0)
        )
        score_columns.append("score__import_cover")

    if "WB_External_Debt_GNI" in pivot.columns:
        pivot["score__external_debt"] = (
            pivot.groupby("date")["WB_External_Debt_GNI"]
            .transform(lambda col: col.rank(method="average", pct=True, ascending=False) * 100.0)
        )
        score_columns.append("score__external_debt")

    if not score_columns:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    pivot["value"] = pivot[score_columns].mean(axis=1, skipna=True)
    pivot["variable"] = "MS_Reserve_Adequacy"
    pivot["source"] = "macrostructure_derived"
    return pivot[["date", "country", "value", "variable", "source"]]


def derive_swap_line_access(countries: Dict[str, Dict[str, Any]]) -> pd.DataFrame:
    """Encode Fed standing and temporary USD swap-line access as a monthly series."""
    current_month = pd.Timestamp(datetime.now()).to_period("M").to_timestamp()
    dates = pd.date_range(pd.Timestamp(2000, 1, 1), current_month, freq="MS")
    records: List[Dict[str, Any]] = []

    for country in countries:
        for dt in dates:
            value = 0.0
            if country in US_HOME_BACKSTOP_COUNTRIES:
                value = 100.0
            elif country in STANDING_SWAP_LINE_COUNTRIES and dt >= STANDING_SWAP_LINE_START:
                value = 100.0
            elif (
                country in TEMPORARY_SWAP_LINE_COUNTRIES
                and TEMPORARY_SWAP_LINE_START <= dt <= TEMPORARY_SWAP_LINE_END
            ):
                value = 75.0

            records.append(
                {
                    "date": dt,
                    "country": country,
                    "value": value,
                    "variable": "MS_Swap_Line_Access",
                    "source": "macrostructure_derived",
                }
            )

    return pd.DataFrame(records, columns=["date", "country", "value", "variable", "source"])


def derive_policy_backstop(panel: pd.DataFrame) -> pd.DataFrame:
    """Average reserve-adequacy and swap-line support into a simple backstop score."""
    needed = {"MS_Reserve_Adequacy", "MS_Swap_Line_Access"}
    subset = panel[panel["variable"].isin(needed)].copy()
    if subset.empty:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    pivot = subset.pivot_table(
        index=["date", "country"],
        columns="variable",
        values="value",
        aggfunc="last",
    ).reset_index()
    if pivot.empty:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    component_columns = [col for col in ["MS_Reserve_Adequacy", "MS_Swap_Line_Access"] if col in pivot.columns]
    if not component_columns:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    pivot["value"] = pivot[component_columns].mean(axis=1, skipna=True)
    pivot = pivot[pivot["value"].notna()].copy()
    if pivot.empty:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    pivot["variable"] = "MS_Policy_Backstop"
    pivot["source"] = "macrostructure_derived"
    return pivot[["date", "country", "value", "variable", "source"]]


def build_catalog(df: pd.DataFrame) -> pd.DataFrame:
    """Build per-variable coverage metadata for the saved panel."""
    if df.empty:
        return pd.DataFrame(
            columns=["variable", "source", "n_obs", "n_countries", "min_date", "max_date"]
        )

    catalog = (
        df.groupby(["variable", "source"], as_index=False)
        .agg(
            n_obs=("value", "size"),
            n_countries=("country", "nunique"),
            min_date=("date", "min"),
            max_date=("date", "max"),
        )
        .sort_values(["source", "variable"])
        .reset_index(drop=True)
    )
    return catalog


def build_formula_catalog() -> Dict[str, Any]:
    """Write an explicit, inspectable definition of derived macrostructure signals."""
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "notes": [
            "QPSD variables prefer central government coverage and fall back to budgetary central government when central government data is missing for a country-date.",
            "MS_US_Holder_Share_Pct is based on the annual IMF PIP benchmark only and measures the U.S. share of tracked cross-border portfolio holdings into each counterpart country.",
            "OECD institutional-depth variables use official dashboard indicators rather than reverse-engineered balance-sheet totals where OECD already publishes the target ratio directly.",
            "IMF MFS central-bank footprint variables use the MFS_CBS dataset in USD terms and scale by same-year WEO nominal GDP in USD for cross-country comparability.",
            "MS_CentralBank_SovDebt_Share is a transparent public-data proxy: it uses central-bank claims on central government as the numerator and total public debt / GDP as the denominator, preferring QPSD debt coverage and falling back to WEO debt / GDP when QPSD is missing.",
            "MS_Reserve_Adequacy blends import-cover strength with inverse external-debt burden where the latter exists; countries without external-debt coverage still receive the import-cover component.",
            "MS_Swap_Line_Access is a transparent policy-support proxy based on Federal Reserve standing and temporary USD liquidity swap arrangements, plus a full home-market backstop for the U.S. sleeves.",
            "MS_Investor_Base_Fragility is a transparent percentile composite; it does not use fitted weights or learned parameters.",
        ],
        "derived_variables": [
            *[
                {
                    "variable": spec["variable"],
                    "source": "qpsd",
                    "description": spec["description"],
                    "formula": spec["formula"],
                    "inputs": [spec["numerator"], spec["denominator"]],
                }
                for spec in QPSD_DERIVED_VARIABLES
            ],
            {
                "variable": "MS_US_Holder_Share_Pct",
                "source": "portfolio_ownership",
                "description": "Share of tracked cross-border inbound portfolio holdings held by U.S. residents.",
                "formula": "100 * inbound_holdings_from_USA / total_tracked_inbound_holdings",
                "inputs": [
                    "bilateral_portfolio_matrix.amount_usd where source='imf_pip' and reporter_iso3='USA'",
                    "bilateral_portfolio_matrix.amount_usd where source='imf_pip'",
                ],
            },
            {
                "variable": "MS_Investor_Base_Fragility",
                "source": "macrostructure_derived",
                "description": "Average cross-sectional percentile fragility score across available public-debt and bank-balance-sheet inputs on each date.",
                "formula": "Average of available component percentile scores on the same date, with higher values always meaning more fragility.",
                "min_components_required": MIN_COMPONENTS_FOR_FRAGILITY,
                "components": INVESTOR_BASE_FRAGILITY_COMPONENTS,
            },
            {
                "variable": "MS_CentralBank_BalanceSheet_GDP",
                "source": "imf_mfs_cbs",
                "description": "Central-bank total assets scaled by same-year nominal GDP in USD.",
                "formula": "100 * MFS_CBS total_assets_usd / WEO nominal_gdp_usd for the same calendar year.",
                "inputs": [
                    MFS_CBS_TOTAL_ASSETS_INDICATOR,
                    WEO_NOMINAL_GDP_USD_INDICATOR,
                ],
            },
            {
                "variable": "MS_CentralBank_Claims_on_Government_Pct_GDP",
                "source": "imf_mfs_cbs",
                "description": "Central-bank claims on central government scaled by same-year nominal GDP in USD.",
                "formula": "100 * MFS_CBS claims_on_central_government_usd / WEO nominal_gdp_usd for the same calendar year.",
                "inputs": [
                    MFS_CBS_CLAIMS_ON_GOVT_INDICATOR,
                    WEO_NOMINAL_GDP_USD_INDICATOR,
                ],
            },
            {
                "variable": "MS_CentralBank_SovDebt_Share",
                "source": "macrostructure_derived",
                "description": "Proxy for the central bank share of sovereign debt, using claims on central government relative to total public debt.",
                "formula": "100 * MS_CentralBank_Claims_on_Government_Pct_GDP / debt_ratio_pct_gdp, where debt_ratio_pct_gdp prefers MS_Public_Debt_Total_Pct_GDP and falls back to IMF_WEO_Debt_GDP.",
                "inputs": [
                    "MS_CentralBank_Claims_on_Government_Pct_GDP",
                    "MS_Public_Debt_Total_Pct_GDP",
                    "IMF_WEO_Debt_GDP",
                ],
            },
            {
                "variable": "MS_Reserve_Adequacy",
                "source": "macrostructure_derived",
                "description": "Average of reserve-buffer component scores, using import-cover strength and inverse external-debt burden where available.",
                "formula": "Average of cross-sectional percentile(import_cover_months) and cross-sectional reverse-percentile(external_debt_gni) on the same date.",
                "inputs": ["WB_Import_Cover_Months", "WB_External_Debt_GNI"],
            },
            {
                "variable": "MS_Swap_Line_Access",
                "source": "macrostructure_derived",
                "description": "Monthly policy-support proxy based on Fed standing and temporary USD liquidity swap-line access.",
                "formula": "100 for standing-swap-line countries from 2013-11 onward; 75 for temporary 2020-03 through 2021-12 swap-line countries; 100 for U.S. sleeves across the full sample; otherwise 0.",
                "inputs": [
                    "Federal Reserve standing USD swap-line counterparties",
                    "Federal Reserve temporary 2020-2021 USD swap-line counterparties",
                ],
            },
            {
                "variable": "MS_Policy_Backstop",
                "source": "macrostructure_derived",
                "description": "Simple average of reserve adequacy and swap-line support, keeping the policy-support block transparent and inspectable.",
                "formula": "Average of available values for MS_Reserve_Adequacy and MS_Swap_Line_Access on the same date.",
                "inputs": ["MS_Reserve_Adequacy", "MS_Swap_Line_Access"],
            },
        ],
    }


def save_outputs(
    df: pd.DataFrame,
    catalog: pd.DataFrame,
    formula_catalog: Dict[str, Any],
    dry_run: bool,
) -> None:
    """Persist the macrostructure panel, coverage catalog, and derived formulas."""
    if dry_run:
        print("\nDRY RUN")
        print(f"  Rows collected: {len(df):,}")
        print(f"  Variables:      {df['variable'].nunique() if not df.empty else 0}")
        print(f"  Countries:      {df['country'].nunique() if not df.empty else 0}")
        print(f"  Formula entries: {len(formula_catalog.get('derived_variables', []))}")
        return

    if df.empty:
        print("\nNo macrostructure data collected — existing outputs left unchanged.")
        return

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for output_path in [PANEL_PQ, PANEL_CSV, CATALOG_CSV, FORMULA_JSON]:
        if output_path.exists():
            backup_path = BACKUP_DIR / f"{output_path.stem}_{timestamp}{output_path.suffix}"
            shutil.copy2(output_path, backup_path)

    df.to_parquet(PANEL_PQ, index=False)
    df.to_csv(PANEL_CSV, index=False)
    catalog.to_csv(CATALOG_CSV, index=False)
    with open(FORMULA_JSON, "w", encoding="utf-8") as handle:
        json.dump(formula_catalog, handle, indent=2)

    print(f"\nSaved: {PANEL_PQ}")
    print(f"Saved: {PANEL_CSV}")
    print(f"Saved: {CATALOG_CSV}")
    print(f"Saved: {FORMULA_JSON}")


def main() -> None:
    parser = argparse.ArgumentParser(description="ASADO Macrostructure Collector")
    parser.add_argument("--force", action="store_true", help="Bypass 24h API caches")
    parser.add_argument("--dry-run", action="store_true", help="Preview only; do not save")
    args = parser.parse_args()

    countries = load_countries()
    iso3_to_t2 = build_iso3_to_t2(countries)
    wb_to_t2 = build_wb_to_t2(countries)
    iso3_list = unique_iso3_list(countries)
    wb_codes = unique_wb_list(countries)

    print(f"Universe: {len(iso3_list)} unique ISO3 codes from {len(countries)} T2 countries\n")

    fsi_panel = collect_fsi(iso3_to_t2, iso3_list, args.force)
    qpsd_panel = collect_qpsd(wb_to_t2, wb_codes, args.force)
    oecd_institutional_panel = collect_oecd_institutional_depth(iso3_to_t2, args.force)
    household_sticky_panel = collect_oecd_household_sticky_capital(iso3_to_t2, args.force)
    nominal_gdp_panel = collect_weo_indicator(
        iso3_to_t2,
        iso3_list,
        WEO_NOMINAL_GDP_USD_INDICATOR,
        "IMF_WEO_Nominal_GDP_USD",
        args.force,
    )
    weo_debt_panel = collect_weo_indicator(
        iso3_to_t2,
        iso3_list,
        WEO_DEBT_GDP_INDICATOR,
        "IMF_WEO_Debt_GDP",
        args.force,
    )
    central_bank_assets_raw = collect_mfs_cbs_indicator(
        iso3_to_t2,
        iso3_list,
        MFS_CBS_TOTAL_ASSETS_INDICATOR,
        args.force,
    )
    central_bank_claims_raw = collect_mfs_cbs_indicator(
        iso3_to_t2,
        iso3_list,
        MFS_CBS_CLAIMS_ON_GOVT_INDICATOR,
        args.force,
    )
    central_bank_balance_sheet_panel = derive_mfs_ratio_to_gdp(
        central_bank_assets_raw,
        nominal_gdp_panel,
        "MS_CentralBank_BalanceSheet_GDP",
    )
    central_bank_claims_panel = derive_mfs_ratio_to_gdp(
        central_bank_claims_raw,
        nominal_gdp_panel,
        "MS_CentralBank_Claims_on_Government_Pct_GDP",
    )
    portfolio_panel = derive_portfolio_context(countries)
    reserve_adequacy_panel = derive_reserve_adequacy()
    swap_line_panel = derive_swap_line_access(countries)

    raw_panel = pd.concat(
        [
            frame
            for frame in [
                fsi_panel,
                qpsd_panel,
                oecd_institutional_panel,
                household_sticky_panel,
                central_bank_balance_sheet_panel,
                central_bank_claims_panel,
                portfolio_panel,
                reserve_adequacy_panel,
                swap_line_panel,
            ]
            if not frame.empty
        ],
        ignore_index=True,
    ) if any(
        not frame.empty
        for frame in [
            fsi_panel,
            qpsd_panel,
            oecd_institutional_panel,
            household_sticky_panel,
            central_bank_balance_sheet_panel,
            central_bank_claims_panel,
            portfolio_panel,
            reserve_adequacy_panel,
            swap_line_panel,
        ]
    ) else pd.DataFrame(
        columns=["date", "country", "value", "variable", "source"]
    )

    derived_panel = derive_investor_base_fragility(raw_panel)
    central_bank_sovdebt_panel = derive_central_bank_sovdebt_share(raw_panel, weo_debt_panel)
    policy_backstop_panel = derive_policy_backstop(raw_panel)

    panel = pd.concat(
        [
            frame
            for frame in [
                raw_panel,
                derived_panel,
                central_bank_sovdebt_panel,
                policy_backstop_panel,
            ]
            if not frame.empty
        ],
        ignore_index=True,
    ) if any(
        not frame.empty
        for frame in [raw_panel, derived_panel, central_bank_sovdebt_panel, policy_backstop_panel]
    ) else pd.DataFrame(columns=["date", "country", "value", "variable", "source"])

    if not panel.empty:
        panel["date"] = pd.to_datetime(panel["date"])
        panel["value"] = pd.to_numeric(panel["value"], errors="coerce")
        panel = (
            panel.dropna(subset=["date", "country", "value", "variable", "source"])
            .sort_values(["country", "variable", "date", "source"])
            .drop_duplicates(subset=["date", "country", "variable"], keep="last")
            .reset_index(drop=True)
        )

    catalog = build_catalog(panel)
    formula_catalog = build_formula_catalog()

    if not panel.empty:
        print("\nMacrostructure coverage:")
        print(f"  Rows:       {len(panel):,}")
        print(f"  Variables:  {panel['variable'].nunique()}")
        print(f"  Countries:  {panel['country'].nunique()}")
        print(f"  Date range: {panel['date'].min().date()} -> {panel['date'].max().date()}")
    else:
        print("No macrostructure data collected")

    save_outputs(panel, catalog, formula_catalog, args.dry_run)
    print("\nDone.")


if __name__ == "__main__":
    main()
