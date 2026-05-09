#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: collect_external.py
=============================================================================

INPUT FILES:
- config/country_mapping.json: Maps 34 T2 countries to source-specific codes
  (ISO-2, ISO-3, OECD, BIS, World Bank, EPU column names, GPR codes)

OUTPUT FILES:
- Data/processed/external_factors_panel.parquet  (primary — tidy panel)
- Data/processed/external_factors_panel.csv      (secondary — CSV copy)
- Data/processed/external_variable_catalog.csv   (metadata per variable)

VERSION: 2.0
LAST UPDATED: 2026-04-10
AUTHOR: Arjun Divecha

DESCRIPTION:
Downloads, parses, and caches data from 7 free external sources, aligns
everything to the 34-country T2 Master universe, and outputs a tidy panel.
This script runs independently of Bloomberg.

Sources collected (with output variables):
  1. EPU  — Economic Policy Uncertainty        (monthly, ~22 countries)
  2. GPR  — Geopolitical Risk                   (monthly, ~18 specific + global)
  3. BIS  — Credit-to-GDP Gap                   (quarterly, 30+ countries)
  4. BIS  — Residential Property Prices          (quarterly, 30+ countries)
  5. OECD — Composite Leading Indicators         (monthly, ~20 countries)
  6. World Bank — 27 governance/macro/demo/climate indicators (annual, 33)
  7. BIS  — Real Effective Exchange Rates         (monthly, 32+ countries)

World Bank indicators (27 total):
  Governance (WGI source 3):
                GOV_WGI_CC.EST, GOV_WGI_GE.EST, GOV_WGI_PV.EST,
                GOV_WGI_RQ.EST, GOV_WGI_RL.EST, GOV_WGI_VA.EST
  Macro:        NY.GDP.MKTP.KD.ZG, FP.CPI.TOTL.ZG, FS.AST.PRVT.GD.ZS,
                CM.MKT.LCAP.GD.ZS, BN.CAB.XOKA.GD.ZS, BX.KLT.DINV.WD.GD.ZS,
                GC.DOD.TOTL.GD.ZS, SL.UEM.TOTL.ZS
  Demographics: SP.POP.TOTL, SP.POP.GROW, SP.POP.DPND.OL,
                SL.TLF.TOTL.IN, SL.TLF.CACT.FE.ZS, SL.TLF.TOTL.FE.ZS
  Reserves:     FI.RES.TOTL.CD, FI.RES.TOTL.MO, DT.DOD.DECT.GN.ZS
  Climate:      EN.GHG.CO2.PC.CE.AR5, EG.FEC.RNEW.ZS
  Structural:   NE.TRD.GNFS.ZS
  NOTE: EN.ATM.CO2E.PC retired (replaced by EDGAR-based EN.GHG.CO2.PC.CE.AR5)
  NOTE: IC.BUS.EASE.XQ (Ease of Business) discontinued 2021 — removed

DEPENDENCIES:
- pandas, numpy, requests, openpyxl, pyarrow, wbgapi, sdmx1, tqdm, xlrd

USAGE:
  python scripts/collect_external.py              # normal monthly update
  python scripts/collect_external.py --force       # bypass 24h download cache
  python scripts/collect_external.py --dry-run     # preview changes, don't save

NOTES:
- Raw downloads cached in Data/raw/ with 24-hour expiry
- Each source wrapped in try/except — pipeline never fails entirely
- Monthly-safe: if a source fails, existing data for that source is preserved
- Timestamped backup saved before every overwrite
- Run history tracked in Data/processed/run_history.json
- Runtime target: under 10 minutes
=============================================================================
"""

import argparse
import json
import logging
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── Paths ─────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "Data"
RAW_DIR = DATA_DIR / "raw"
CACHE_DIR = DATA_DIR / "cache"
PROCESSED_DIR = DATA_DIR / "processed"
CONFIG_DIR = BASE_DIR / "config"

for d in [RAW_DIR, CACHE_DIR, PROCESSED_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            CACHE_DIR / f"collection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        ),
    ],
)
logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────
T2_COUNTRIES = [
    "Australia", "Brazil", "Canada", "Chile", "ChinaA", "ChinaH",
    "Denmark", "France", "Germany", "Hong Kong", "India", "Indonesia",
    "Italy", "Japan", "Korea", "Malaysia", "Mexico", "NASDAQ",
    "Netherlands", "Philippines", "Poland", "Saudi Arabia", "Singapore",
    "South Africa", "Spain", "Sweden", "Switzerland", "Taiwan",
    "Thailand", "Turkey", "U.K.", "U.S.", "US SmallCap", "Vietnam",
]

# WDI indicators (source 2) — 21 indicators
WDI_INDICATORS = {
    # Macro (8)
    "NY.GDP.MKTP.KD.ZG":    "WB_GDP_Growth_Real",
    "FP.CPI.TOTL.ZG":       "WB_Inflation_CPI",
    "FS.AST.PRVT.GD.ZS":    "WB_Domestic_Credit_GDP",
    "CM.MKT.LCAP.GD.ZS":    "WB_Market_Cap_GDP",
    "BN.CAB.XOKA.GD.ZS":    "WB_Current_Account_GDP",
    "BX.KLT.DINV.WD.GD.ZS": "WB_FDI_Inflows_GDP",
    "GC.DOD.TOTL.GD.ZS":    "WB_Govt_Debt_GDP",
    "SL.UEM.TOTL.ZS":       "WB_Unemployment",
    # Demographics (6)
    "SP.POP.TOTL":           "WB_Population",
    "SP.POP.GROW":           "WB_Population_Growth",
    "SP.POP.DPND.OL":        "WB_OldAge_Dependency",
    "SL.TLF.TOTL.IN":        "WB_Labor_Force",
    "SL.TLF.CACT.FE.ZS":    "WB_Female_LFP",
    "SL.TLF.TOTL.FE.ZS":    "WB_Female_Labor_Share",
    # Reserves / external debt (3)
    "FI.RES.TOTL.CD":        "WB_FX_Reserves",
    "FI.RES.TOTL.MO":        "WB_Import_Cover_Months",
    "DT.DOD.DECT.GN.ZS":     "WB_External_Debt_GNI",
    # Climate (2) — EN.ATM.CO2E.PC retired; using EDGAR-based replacement
    "EN.GHG.CO2.PC.CE.AR5":  "WB_CO2_Per_Capita",
    "EG.FEC.RNEW.ZS":        "WB_Renewable_Energy_Share",
    # Structural (1) — IC.BUS.EASE.XQ discontinued 2021
    "NE.TRD.GNFS.ZS":        "WB_Trade_Openness",
}

# WGI indicators (source 3 = Worldwide Governance Indicators) — 6 indicators
WGI_INDICATORS = {
    "GOV_WGI_CC.EST": "WB_Control_Corruption",
    "GOV_WGI_GE.EST": "WB_Govt_Effectiveness",
    "GOV_WGI_PV.EST": "WB_Political_Stability",
    "GOV_WGI_RQ.EST": "WB_Regulatory_Quality",
    "GOV_WGI_RL.EST": "WB_Rule_of_Law",
    "GOV_WGI_VA.EST": "WB_Voice_Accountability",
}

WORLD_BANK_INDICATORS = {**WDI_INDICATORS, **WGI_INDICATORS}  # 27 total

GPR_GLOBAL_VAR_MAP = {
    "GPR": "Global_GPR",
    "GPRT": "Global_GPR_Threat",
    "GPRA": "Global_GPR_Act",
}


# Map collector names to the `source` column values they produce
COLLECTOR_SOURCE_KEYS = {
    "EPU":                 ["epu"],
    "GPR":                 ["gpr"],
    "BIS Credit Gap":      ["bis_credit"],
    "BIS Property Prices": ["bis_property"],
    "OECD CLI":            ["oecd"],
    "World Bank":          ["worldbank"],
    "BIS REER":            ["bis_reer"],
}

PANEL_PATH = PROCESSED_DIR / "external_factors_panel.parquet"
CSV_PATH   = PROCESSED_DIR / "external_factors_panel.csv"
CAT_PATH   = PROCESSED_DIR / "external_variable_catalog.csv"
HISTORY_PATH = PROCESSED_DIR / "run_history.json"
BACKUP_DIR = DATA_DIR / "backups"


# ═══════════════════════════════════════════════════════════════════════════
# MONTHLY-UPDATE INFRASTRUCTURE
# ═══════════════════════════════════════════════════════════════════════════

def load_existing_panel() -> Optional[pd.DataFrame]:
    """Load the existing panel from disk (if any)."""
    if PANEL_PATH.exists():
        df = pd.read_parquet(PANEL_PATH)
        logger.info(f"Loaded existing panel: {len(df):,} rows, "
                    f"{df['source'].nunique()} sources")
        return df
    logger.info("No existing panel found — starting fresh")
    return None


def backup_panel() -> Optional[Path]:
    """Save a timestamped backup of the existing panel before overwriting."""
    if not PANEL_PATH.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    backup = BACKUP_DIR / f"external_factors_panel_{ts}.parquet"
    shutil.copy2(PANEL_PATH, backup)
    logger.info(f"Backed up existing panel → {backup.name}")
    return backup


def merge_panels(existing: Optional[pd.DataFrame],
                 fresh_frames: Dict[str, pd.DataFrame],
                 source_status: Dict[str, str]) -> pd.DataFrame:
    """Source-level merge: replace data for successful sources, keep existing for failures.

    For each collector that SUCCEEDED, we drop all old rows with that source key
    and replace them with the fresh data.  For collectors that FAILED, old rows
    for that source are retained unchanged.
    """
    if existing is None:
        # First run — just concat the fresh data
        parts = [df for df in fresh_frames.values() if df is not None and not df.empty]
        if not parts:
            return pd.DataFrame()
        return pd.concat(parts, ignore_index=True)

    merged = existing.copy()

    for collector_name, status in source_status.items():
        source_keys = COLLECTOR_SOURCE_KEYS.get(collector_name, [])
        fresh = fresh_frames.get(collector_name)

        if status == "SUCCESS" and fresh is not None and not fresh.empty:
            old_count = merged["source"].isin(source_keys).sum()
            merged = merged[~merged["source"].isin(source_keys)]
            merged = pd.concat([merged, fresh], ignore_index=True)
            logger.info(f"  {collector_name}: replaced {old_count:,} old rows "
                        f"with {len(fresh):,} fresh rows")
        else:
            kept = merged["source"].isin(source_keys).sum()
            if kept > 0:
                logger.info(f"  {collector_name}: KEPT {kept:,} existing rows "
                            f"(source did not succeed this run)")

    return merged


def load_run_history() -> Dict:
    """Load run history from JSON file."""
    if HISTORY_PATH.exists():
        with open(HISTORY_PATH) as f:
            data = json.load(f)
        # Backwards-compat: older versions wrote a bare list
        if isinstance(data, list):
            return {"runs": data}
        return data
    return {"runs": []}


def save_run_history(history: Dict) -> None:
    """Write run history to JSON."""
    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2, default=str)


def record_run(source_status: Dict[str, str], panel: pd.DataFrame,
               elapsed: float) -> None:
    """Append a run entry to run_history.json."""
    history = load_run_history()
    entry = {
        "timestamp": datetime.now().isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "total_rows": len(panel),
        "total_variables": int(panel["variable"].nunique()),
        "total_countries": int(panel["country"].nunique()),
        "date_min": panel["date"].min().isoformat(),
        "date_max": panel["date"].max().isoformat(),
        "sources": {},
    }
    for name, status in source_status.items():
        source_keys = COLLECTOR_SOURCE_KEYS.get(name, [])
        sub = panel[panel["source"].isin(source_keys)]
        entry["sources"][name] = {
            "status": status,
            "rows": len(sub),
            "countries": int(sub["country"].nunique()) if not sub.empty else 0,
            "date_max": sub["date"].max().isoformat() if not sub.empty else None,
        }
    history["runs"].append(entry)
    # Keep last 24 runs (2 years of monthly)
    history["runs"] = history["runs"][-24:]
    save_run_history(history)
    logger.info(f"Saved run history → {HISTORY_PATH.name}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Phase 1 Program 1: External Data Collection"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Bypass 24-hour download cache and re-download everything"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch and merge but do NOT save output files"
    )
    return parser.parse_args()


# ═══════════════════════════════════════════════════════════════════════════
# INFRASTRUCTURE
# ═══════════════════════════════════════════════════════════════════════════

class CacheManager:
    """File caching with 24-hour expiry."""

    @staticmethod
    def is_valid(filepath: Path, max_age_hours: int = 24) -> bool:
        if not filepath.exists():
            return False
        age = datetime.now() - datetime.fromtimestamp(filepath.stat().st_mtime)
        return age < timedelta(hours=max_age_hours)


def fetch_with_retry(url: str, max_retries: int = 3, timeout: int = 120) -> requests.Response:
    """HTTP GET with exponential-backoff retries."""
    session = requests.Session()
    retry = Retry(total=max_retries, backoff_factor=2,
                  status_forcelist=[429, 500, 502, 503, 504])
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    resp = session.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp


def download_and_cache(url: str, cache_path: Path, label: str) -> Path:
    """Download a file to cache_path if cache has expired."""
    if CacheManager.is_valid(cache_path):
        logger.info(f"  Using cached {label}")
    else:
        logger.info(f"  Downloading {label} ...")
        resp = fetch_with_retry(url)
        cache_path.write_bytes(resp.content)
        logger.info(f"  Saved {cache_path.name} ({len(resp.content)/1e6:.1f} MB)")
    return cache_path


def load_country_mapping() -> Dict[str, Dict[str, Optional[str]]]:
    """Load config/country_mapping.json."""
    path = CONFIG_DIR / "country_mapping.json"
    if not path.exists():
        raise FileNotFoundError(f"Country mapping not found: {path}")
    with open(path) as f:
        data = json.load(f)
    mapping = data["countries"]
    logger.info(f"Loaded country mapping for {len(mapping)} countries")
    return mapping


def _build_reverse_map(countries: Dict, field: str) -> Dict[str, List[str]]:
    """Build code → [t2_country, ...] from country_mapping, handling one-to-many."""
    rev: Dict[str, List[str]] = {}
    for t2, info in countries.items():
        code = info.get(field)
        if code:
            rev.setdefault(code, []).append(t2)
    return rev


def _parse_bis_period(period_str: str) -> Optional[pd.Timestamp]:
    """Parse BIS TIME_PERIOD strings: 2020-Q1 → 2020-03-01, 2020-01 → 2020-01-01."""
    s = str(period_str).strip()
    try:
        if "-Q" in s:
            year, q = s.split("-Q")
            return pd.Timestamp(year=int(year), month=int(q) * 3, day=1)
        if len(s) == 7 and s[4] == "-":
            return pd.Timestamp(f"{s}-01")
        if len(s) == 4 and s.isdigit():
            return pd.Timestamp(year=int(s), month=12, day=1)
        return pd.Timestamp(s)
    except Exception:
        return None


def _find_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """Find first matching column name from a list of candidates (case-insensitive)."""
    col_lower = {c.lower(): c for c in df.columns}
    for cand in candidates:
        if cand.lower() in col_lower:
            return col_lower[cand.lower()]
    return None


# SDMX helpers (used by OECD CLI collector)
def _sdmx_key_value(key_obj: Any, field: str) -> Optional[str]:
    key_text = str(key_obj).strip("()")
    for part in key_text.split(", "):
        if part.startswith(f"{field}="):
            return part.split("=", 1)[1]
    return None


def _sdmx_obs_period(obs: Any) -> Optional[str]:
    try:
        return obs.dimension.values["TIME_PERIOD"].value
    except Exception:
        return _sdmx_key_value(obs, "TIME_PERIOD")


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE 1: ECONOMIC POLICY UNCERTAINTY
# ═══════════════════════════════════════════════════════════════════════════

def collect_epu(countries: Dict) -> pd.DataFrame:
    logger.info("[1/7] Economic Policy Uncertainty indices ...")

    url = "https://www.policyuncertainty.com/media/All_Country_Data.xlsx"
    cache_path = RAW_DIR / "epu_all_country.xlsx"

    try:
        download_and_cache(url, cache_path, "EPU Excel")
        df_raw = pd.read_excel(cache_path)

        t2_to_epu = {t2: info["epu_col"] for t2, info in countries.items()
                     if info.get("epu_col")}

        def _norm(t: str) -> str:
            return "".join(ch.lower() for ch in str(t) if ch.isalnum())

        col_by_norm = {_norm(c): c for c in df_raw.columns}

        alias_map = {
            "unitedkingdom": ["uk", "unitedkingdom"],
            "unitedstates":  ["us", "usa", "unitedstates"],
            "southkorea":    ["korea", "southkorea"],
            "korea":         ["korea", "southkorea"],
            "hongkong":      ["hongkong", "scmpchina"],
            "china":         ["china", "mainlandchina", "scmpchina"],
        }

        matched_cols: Dict[str, str] = {}
        for t2_country, epu_col in t2_to_epu.items():
            if t2_country == "ChinaA":
                for cand in ["Mainland China", "China"]:
                    if cand in df_raw.columns:
                        matched_cols[t2_country] = cand
                        break
                continue
            if t2_country == "ChinaH":
                for cand in ["SCMP China", "China"]:
                    if cand in df_raw.columns:
                        matched_cols[t2_country] = cand
                        break
                continue

            target = _norm(epu_col)
            matched = col_by_norm.get(target)

            if not matched:
                for alias in alias_map.get(target, [target]):
                    if _norm(alias) in col_by_norm:
                        matched = col_by_norm[_norm(alias)]
                        break

            if not matched:
                for c in df_raw.columns:
                    cn = _norm(c)
                    if target in cn or cn in target:
                        matched = c
                        break

            if matched:
                matched_cols[t2_country] = matched

        logger.info(f"  Matched {len(matched_cols)} T2 countries to EPU columns")

        results = []
        for t2_country, col_name in matched_cols.items():
            tmp = df_raw[["Year", "Month", col_name]].copy()
            tmp.columns = ["year", "month", "value"]
            tmp["value"] = pd.to_numeric(tmp["value"], errors="coerce")
            tmp = tmp.dropna(subset=["value"])
            tmp["date"] = pd.to_datetime(tmp[["year", "month"]].assign(day=1))
            tmp["country"] = t2_country
            tmp["variable"] = "EPU"
            tmp["source"] = "epu"
            results.append(tmp[["date", "country", "value", "variable", "source"]])

        if not results:
            logger.warning("  No EPU data collected")
            return pd.DataFrame()

        df = pd.concat(results, ignore_index=True)
        _log_source_summary("EPU", df)
        return df

    except Exception as e:
        logger.error(f"  EPU FAILED: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE 2: GEOPOLITICAL RISK
# ═══════════════════════════════════════════════════════════════════════════

def collect_gpr(countries: Dict) -> pd.DataFrame:
    logger.info("[2/7] Geopolitical Risk indices ...")

    url = "https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls"
    cache_path = RAW_DIR / "gpr_export.xls"

    try:
        download_and_cache(url, cache_path, "GPR Excel")
        df_raw = pd.read_excel(cache_path)

        date_col = df_raw.columns[0]
        df_raw[date_col] = pd.to_datetime(df_raw[date_col])

        # Build gpr_code → [t2_countries] (one-to-many)
        gpr_rev = _build_reverse_map(countries, "gpr")

        # Match GPRC_XXX columns to T2 countries
        country_cols: Dict[str, str] = {}  # t2_country → column_name
        for col in df_raw.columns:
            if col.startswith("GPRC_"):
                iso = col.replace("GPRC_", "")
                for t2 in gpr_rev.get(iso, []):
                    country_cols[t2] = col

        global_col_map: Dict[str, str] = {}
        for col in df_raw.columns:
            if col in GPR_GLOBAL_VAR_MAP:
                global_col_map[col] = GPR_GLOBAL_VAR_MAP[col]

        logger.info(f"  Country-specific GPR columns: {len(country_cols)}")
        logger.info(f"  Global GPR columns: {list(global_col_map.keys())}")

        results = []

        for t2_country, gpr_col in country_cols.items():
            tmp = df_raw[[date_col, gpr_col]].copy()
            tmp.columns = ["date", "value"]
            tmp["value"] = pd.to_numeric(tmp["value"], errors="coerce")
            tmp = tmp.dropna(subset=["value"])
            tmp["date"] = tmp["date"].dt.to_period("M").dt.to_timestamp()
            tmp["country"] = t2_country
            tmp["variable"] = "GPR"
            tmp["source"] = "gpr"
            results.append(tmp[["date", "country", "value", "variable", "source"]])

        for raw_col, var_name in global_col_map.items():
            tmp = df_raw[[date_col, raw_col]].copy()
            tmp.columns = ["date", "value"]
            tmp["value"] = pd.to_numeric(tmp["value"], errors="coerce")
            tmp = tmp.dropna(subset=["value"])
            tmp["date"] = tmp["date"].dt.to_period("M").dt.to_timestamp()
            for t2_country in countries.keys():
                row = tmp.copy()
                row["country"] = t2_country
                row["variable"] = var_name
                row["source"] = "gpr"
                results.append(row[["date", "country", "value", "variable", "source"]])

        if not results:
            logger.warning("  No GPR data collected")
            return pd.DataFrame()

        df = pd.concat(results, ignore_index=True)
        _log_source_summary("GPR", df)
        return df

    except Exception as e:
        logger.error(f"  GPR FAILED: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE 3: BIS CREDIT-TO-GDP GAP  (SDMX API)
# ═══════════════════════════════════════════════════════════════════════════

def collect_bis_credit(countries: Dict) -> pd.DataFrame:
    logger.info("[3/7] BIS Credit-to-GDP Gap ...")

    try:
        import sdmx

        bis_rev = _build_reverse_map(countries, "bis")

        logger.info("  Querying BIS SDMX WS_CREDIT_GAP ...")
        client = sdmx.Client("BIS")
        data = client.data("WS_CREDIT_GAP", params={"startPeriod": "2000-Q1"})
        dataset = data.data[0]
        logger.info(f"  Received {len(dataset.series)} series")

        records = []
        for series_key, obs_list in dataset.series.items():
            country_code = _sdmx_key_value(series_key, "BORROWERS_CTY")
            if not country_code or country_code not in bis_rev:
                continue
            tc = _sdmx_key_value(series_key, "TC_BORROWERS")
            if tc and tc != "P":
                continue
            dtype = _sdmx_key_value(series_key, "CG_DTYPE")
            if dtype and dtype != "A":
                continue
            for obs in obs_list:
                period = _sdmx_obs_period(obs)
                if not period:
                    continue
                val = pd.to_numeric(obs.value, errors="coerce")
                if pd.isna(val):
                    continue
                date = _parse_bis_period(period)
                if date is None:
                    continue
                for t2 in bis_rev[country_code]:
                    records.append({
                        "date": date, "country": t2, "value": float(val),
                        "variable": "BIS_Credit_GDP_Gap", "source": "bis_credit",
                    })

        result = pd.DataFrame(records)
        if result.empty:
            logger.warning("  No BIS credit gap records after filtering")
            return pd.DataFrame()

        result = result.drop_duplicates(subset=["date", "country", "variable"])
        _log_source_summary("BIS Credit Gap", result)
        return result

    except Exception as e:
        logger.error(f"  BIS Credit Gap FAILED: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE 4: BIS RESIDENTIAL PROPERTY PRICES  (SDMX API)
# ═══════════════════════════════════════════════════════════════════════════

def collect_bis_property(countries: Dict) -> pd.DataFrame:
    logger.info("[4/7] BIS Residential Property Prices ...")

    try:
        import sdmx

        bis_rev = _build_reverse_map(countries, "bis")

        logger.info("  Querying BIS SDMX WS_SPP ...")
        client = sdmx.Client("BIS")
        data = client.data("WS_SPP", params={"startPeriod": "2000-Q1"})
        dataset = data.data[0]
        logger.info(f"  Received {len(dataset.series)} series")

        records = []
        for series_key, obs_list in dataset.series.items():
            country_code = _sdmx_key_value(series_key, "REF_AREA")
            if not country_code or country_code not in bis_rev:
                continue
            # Prefer real prices (VALUE=R)
            val_type = _sdmx_key_value(series_key, "VALUE")
            if val_type and val_type != "R":
                continue
            for obs in obs_list:
                period = _sdmx_obs_period(obs)
                if not period:
                    continue
                val = pd.to_numeric(obs.value, errors="coerce")
                if pd.isna(val):
                    continue
                date = _parse_bis_period(period)
                if date is None:
                    continue
                for t2 in bis_rev[country_code]:
                    records.append({
                        "date": date, "country": t2, "value": float(val),
                        "variable": "BIS_Property_Price", "source": "bis_property",
                    })

        result = pd.DataFrame(records)
        if result.empty:
            logger.warning("  No BIS property price records")
            return pd.DataFrame()

        result = result.drop_duplicates(subset=["date", "country", "variable"])
        _log_source_summary("BIS Property", result)
        return result

    except Exception as e:
        logger.error(f"  BIS Property FAILED: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE 5: OECD COMPOSITE LEADING INDICATORS  (SDMX + CSV fallback)
# ═══════════════════════════════════════════════════════════════════════════

def collect_oecd_cli(countries: Dict) -> pd.DataFrame:
    logger.info("[5/7] OECD Composite Leading Indicators ...")

    oecd_rev = _build_reverse_map(countries, "oecd")
    if not oecd_rev:
        logger.warning("  No OECD country mappings found")
        return pd.DataFrame()

    unique_codes = sorted(oecd_rev.keys())
    codes_str = "+".join(unique_codes)

    # ── Try SDMX first ────────────────────────────────────────────────
    try:
        import sdmx

        logger.info("  Trying SDMX API ...")
        client = sdmx.Client("OECD")
        data = client.data(
            "OECD.SDD.STES,DSD_STES@DF_CLI,4.1",
            key=f"{codes_str}.M.LI........",
            params={"startPeriod": "2000-01"},
        )
        dataset = data.data[0]

        records = []
        for series_key, obs_list in dataset.series.items():
            oecd_code = _sdmx_key_value(series_key, "REF_AREA")
            if not oecd_code or oecd_code not in oecd_rev:
                continue
            for obs in obs_list:
                period = _sdmx_obs_period(obs)
                if not period:
                    continue
                val = pd.to_numeric(obs.value, errors="coerce")
                if pd.isna(val):
                    continue
                date = _parse_bis_period(period)
                if date is None:
                    continue
                for t2 in oecd_rev[oecd_code]:
                    records.append({
                        "date": date, "country": t2, "value": float(val),
                        "variable": "OECD_CLI", "source": "oecd",
                    })

        if records:
            result = pd.DataFrame(records)
            result = result.drop_duplicates(subset=["date", "country", "variable"])
            _log_source_summary("OECD CLI (SDMX)", result)
            return result

        logger.warning("  SDMX returned no data, trying CSV fallback ...")

    except Exception as e:
        logger.warning(f"  SDMX failed ({e}), trying CSV fallback ...")

    # ── CSV fallback ──────────────────────────────────────────────────
    try:
        fallback_url = (
            f"https://sdmx.oecd.org/public/rest/data/"
            f"OECD.SDD.STES,DSD_KEI@DF_KEI,4.0/"
            f"{codes_str}.M.LI.LOLITOAA.AA..?"
            f"startPeriod=2000-01&format=csvfilewithlabels"
        )
        cache_path = RAW_DIR / "oecd_cli_fallback.csv"
        download_and_cache(fallback_url, cache_path, "OECD CLI CSV fallback")
        df = pd.read_csv(cache_path, low_memory=False)
        logger.info(f"  Fallback CSV: {len(df)} rows, columns: {list(df.columns[:8])}")

        country_col = _find_col(df, ["REF_AREA", "Reference area"])
        time_col = _find_col(df, ["TIME_PERIOD", "Time period"])
        value_col = _find_col(df, ["OBS_VALUE", "Observation value"])

        if not all([country_col, time_col, value_col]):
            logger.error("  Fallback CSV missing required columns")
            return pd.DataFrame()

        records = []
        for _, row in df.iterrows():
            code = str(row[country_col]).strip()
            if code not in oecd_rev:
                continue
            date = _parse_bis_period(row[time_col])
            if date is None:
                continue
            val = pd.to_numeric(row[value_col], errors="coerce")
            if pd.isna(val):
                continue
            for t2 in oecd_rev[code]:
                records.append({
                    "date": date, "country": t2, "value": float(val),
                    "variable": "OECD_CLI", "source": "oecd",
                })

        if not records:
            logger.warning("  OECD CLI fallback: no records")
            return pd.DataFrame()

        result = pd.DataFrame(records)
        result = result.drop_duplicates(subset=["date", "country", "variable"])
        _log_source_summary("OECD CLI (CSV fallback)", result)
        return result

    except Exception as e:
        logger.error(f"  OECD CLI FAILED (both methods): {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE 6: WORLD BANK  (28 indicators via wbgapi)
# ═══════════════════════════════════════════════════════════════════════════

def _fetch_wb_indicators(indicator_dict: Dict[str, str], wb_codes: List[str],
                         wb_rev: Dict[str, List[str]], db: int = 2):
    """Fetch a batch of World Bank indicators from a specific source database."""
    import wbgapi as wb

    old_db = wb.db
    wb.db = db
    results = []
    succeeded = failed = 0

    for wb_code, var_name in indicator_dict.items():
        try:
            df_ind = wb.data.DataFrame(
                wb_code, economy=wb_codes, time=range(2000, 2027)
            )
            df_ind = df_ind.reset_index()

            year_cols = [c for c in df_ind.columns if str(c).startswith("YR")]
            if not year_cols:
                logger.warning(f"    {var_name}: no year columns")
                failed += 1
                continue

            long = df_ind.melt(
                id_vars=["economy"], value_vars=year_cols,
                var_name="yr_col", value_name="value",
            )
            long["value"] = pd.to_numeric(long["value"], errors="coerce")
            long = long.dropna(subset=["value"])
            long["year"] = pd.to_numeric(
                long["yr_col"].str.replace("YR", "", regex=False), errors="coerce"
            )
            long = long.dropna(subset=["year"])
            long["year"] = long["year"].astype(int)
            long["date"] = pd.to_datetime(long["year"].astype(str) + "-12-01")

            long["t2_list"] = long["economy"].map(wb_rev)
            long = long.dropna(subset=["t2_list"])
            long = long.explode("t2_list")

            chunk = long[["date", "t2_list", "value"]].copy()
            chunk.columns = ["date", "country", "value"]
            chunk["variable"] = var_name
            chunk["source"] = "worldbank"
            results.append(chunk)
            succeeded += 1
            logger.info(f"    {var_name}: {len(chunk)} obs, "
                        f"{chunk['country'].nunique()} countries")

        except Exception as e:
            logger.warning(f"    {var_name} FAILED: {e}")
            failed += 1

    wb.db = old_db
    return results, succeeded, failed


def collect_worldbank(countries: Dict) -> pd.DataFrame:
    logger.info("[6/7] World Bank indicators (27) ...")

    try:
        import wbgapi as wb
    except ImportError:
        logger.error("  wbgapi not installed")
        return pd.DataFrame()

    wb_rev = _build_reverse_map(countries, "wb")
    if not wb_rev:
        logger.warning("  No World Bank mappings found")
        return pd.DataFrame()

    unique_wb_codes = sorted(wb_rev.keys())
    total = len(WDI_INDICATORS) + len(WGI_INDICATORS)
    logger.info(f"  Querying {total} indicators for {len(unique_wb_codes)} economies")

    # Phase A: WDI (source 2) — macro, demographics, climate, structural
    logger.info(f"  --- WDI indicators (source 2, {len(WDI_INDICATORS)} indicators) ---")
    wdi_results, wdi_ok, wdi_fail = _fetch_wb_indicators(
        WDI_INDICATORS, unique_wb_codes, wb_rev, db=2
    )

    # Phase B: WGI (source 3) — governance
    logger.info(f"  --- WGI indicators (source 3, {len(WGI_INDICATORS)} indicators) ---")
    wgi_results, wgi_ok, wgi_fail = _fetch_wb_indicators(
        WGI_INDICATORS, unique_wb_codes, wb_rev, db=3
    )

    all_results = wdi_results + wgi_results
    total_ok = wdi_ok + wgi_ok
    total_fail = wdi_fail + wgi_fail
    logger.info(f"  World Bank: {total_ok}/{total} indicators succeeded, "
                f"{total_fail} failed")

    if not all_results:
        logger.warning("  No World Bank data collected")
        return pd.DataFrame()

    df = pd.concat(all_results, ignore_index=True)
    _log_source_summary("World Bank", df)
    return df


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE 7: BIS REAL EFFECTIVE EXCHANGE RATES  (SDMX API, per-country)
# ═══════════════════════════════════════════════════════════════════════════

def collect_bis_reer(countries: Dict) -> pd.DataFrame:
    logger.info("[7/7] BIS Real Effective Exchange Rates ...")

    try:
        import sdmx

        bis_rev = _build_reverse_map(countries, "bis")
        client = sdmx.Client("BIS")

        records = []
        failed_codes = []
        for country_code, t2_list in bis_rev.items():
            try:
                data = client.data(
                    "WS_EER",
                    key=f"M.R.B.{country_code}",
                    params={"startPeriod": "2000-01"},
                )
            except Exception:
                failed_codes.append(country_code)
                continue

            if not data.data:
                failed_codes.append(country_code)
                continue

            dataset = data.data[0]
            for series_key, obs_list in dataset.series.items():
                for obs in obs_list:
                    period = _sdmx_obs_period(obs)
                    if not period:
                        continue
                    val = pd.to_numeric(obs.value, errors="coerce")
                    if pd.isna(val):
                        continue
                    date = _parse_bis_period(period)
                    if date is None:
                        continue
                    for t2 in t2_list:
                        records.append({
                            "date": date, "country": t2, "value": float(val),
                            "variable": "BIS_REER", "source": "bis_reer",
                        })

        if failed_codes:
            logger.info(f"  BIS REER: no data for {len(failed_codes)} codes: "
                        f"{failed_codes[:10]}")

        result = pd.DataFrame(records)
        if result.empty:
            logger.warning("  No BIS REER records")
            return pd.DataFrame()

        result = result.drop_duplicates(subset=["date", "country", "variable"])
        _log_source_summary("BIS REER", result)
        return result

    except Exception as e:
        logger.error(f"  BIS REER FAILED: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# QUALITY CHECKS & CATALOG
# ═══════════════════════════════════════════════════════════════════════════

def _log_source_summary(label: str, df: pd.DataFrame) -> None:
    """Standard one-line summary for a collected source."""
    n_obs = len(df)
    n_ctry = df["country"].nunique()
    d_min = df["date"].min().strftime("%Y-%m")
    d_max = df["date"].max().strftime("%Y-%m")
    n_vars = df["variable"].nunique()
    logger.info(f"      → {label}: {n_obs:,} obs, {n_ctry} countries, "
                f"{n_vars} variable(s), {d_min} to {d_max}")


def run_quality_checks(df: pd.DataFrame) -> Dict[str, Any]:
    """PRD Section 8 quality checks."""
    logger.info("\n" + "=" * 60)
    logger.info("QUALITY CHECKS")
    logger.info("=" * 60)

    checks: Dict[str, Any] = {}

    # 1. Country coverage
    present = sorted(df["country"].unique())
    missing = sorted(set(T2_COUNTRIES) - set(present))
    checks["present"] = present
    checks["missing"] = missing
    logger.info(f"Countries present: {len(present)}/34")
    if missing:
        logger.warning(f"  Missing: {missing}")

    # 2. Duplicates
    dups = df.duplicated(subset=["date", "country", "variable"]).sum()
    checks["duplicates"] = dups
    if dups:
        logger.warning(f"Duplicate (date, country, variable) rows: {dups}")
        df.drop_duplicates(subset=["date", "country", "variable"], inplace=True)
        logger.info(f"  Removed duplicates → {len(df)} rows")
    else:
        logger.info("No duplicate rows")

    # 3. Date range sanity
    logger.info("\nDate ranges by variable:")
    for var in sorted(df["variable"].unique()):
        sub = df[df["variable"] == var]
        d_min, d_max = sub["date"].min(), sub["date"].max()
        flag = ""
        if var in ("EPU", "GPR", "OECD_CLI") or var.startswith("Global_GPR"):
            if d_min.year > 2005:
                flag = " ⚠ starts after 2005"
        elif var.startswith("BIS_"):
            if d_min.year > 2010:
                flag = " ⚠ starts after 2010"
        elif var.startswith("WB_"):
            if d_min.year > 2005:
                flag = " ⚠ starts after 2005"
        logger.info(f"  {var:35s} {d_min.strftime('%Y-%m')} → "
                     f"{d_max.strftime('%Y-%m')}  ({sub['country'].nunique()} ctry){flag}")

    # 4. Outlier check (> 10x std from mean)
    outlier_warnings = []
    for var in df["variable"].unique():
        vals = df.loc[df["variable"] == var, "value"].dropna()
        if len(vals) < 20:
            continue
        mean, std = vals.mean(), vals.std()
        if std == 0:
            continue
        n_outliers = (vals.sub(mean).abs() > 10 * std).sum()
        if n_outliers:
            outlier_warnings.append(f"{var}: {n_outliers} outliers > 10x std")
    checks["outliers"] = outlier_warnings
    if outlier_warnings:
        logger.warning(f"Outlier issues: {outlier_warnings}")
    else:
        logger.info("No outlier issues (10x std threshold)")

    # 5. Coverage matrix (countries × sources)
    logger.info("\nCoverage matrix (obs count per source):")
    cov = df.groupby(["country", "source"]).size().unstack(fill_value=0)
    for src in cov.columns:
        n = (cov[src] > 0).sum()
        logger.info(f"  {src:20s}: {n}/34 countries")
    checks["coverage"] = cov.to_dict()

    return checks


def create_variable_catalog(df: pd.DataFrame) -> pd.DataFrame:
    """PRD Section 4.2 metadata catalog."""
    rows = []
    for (src, var), g in df.groupby(["source", "variable"]):
        rows.append({
            "source": src,
            "variable": var,
            "n_countries": g["country"].nunique(),
            "n_observations": len(g),
            "date_min": g["date"].min(),
            "date_max": g["date"].max(),
            "mean": g["value"].mean(),
            "std": g["value"].std(),
            "pct_missing": 0.0,
        })
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    args = parse_args()
    t0 = time.time()

    mode_label = "DRY-RUN" if args.dry_run else "UPDATE"
    logger.info("=" * 60)
    logger.info(f"EXTERNAL DATA COLLECTION — {mode_label}")
    logger.info("=" * 60)
    logger.info(f"Project directory: {BASE_DIR}")
    if args.force:
        logger.info("--force: bypassing download cache")
    if args.dry_run:
        logger.info("--dry-run: will NOT save output files")

    # If --force, invalidate all cached raw files
    if args.force:
        for f in RAW_DIR.iterdir():
            if f.is_file() and f.name != ".DS_Store":
                f.unlink()
                logger.info(f"  Cleared cache: {f.name}")

    countries = load_country_mapping()

    # ── Load existing panel ───────────────────────────────────────────
    existing_panel = load_existing_panel()

    # ── Collect fresh data from all 7 sources ─────────────────────────
    collectors = [
        ("EPU",                collect_epu),
        ("GPR",                collect_gpr),
        ("BIS Credit Gap",     collect_bis_credit),
        ("BIS Property Prices",collect_bis_property),
        ("OECD CLI",           collect_oecd_cli),
        ("World Bank",         collect_worldbank),
        ("BIS REER",           collect_bis_reer),
    ]

    fresh_frames: Dict[str, pd.DataFrame] = {}
    status: Dict[str, str] = {}

    # Run all 7 collectors in parallel — each hits a different host so they
    # don't share rate-limit budgets and the per-source try/except keeps one
    # failure from poisoning the others.
    def _run_one(name: str, fn) -> Tuple[str, pd.DataFrame, str]:
        try:
            df = fn(countries)
            if df is not None and not df.empty:
                return name, df, "SUCCESS"
            return name, pd.DataFrame(), "NO DATA"
        except Exception as e:
            logger.error(f"  {name}: FAILED — {e}")
            return name, pd.DataFrame(), f"FAILED: {e}"

    with ThreadPoolExecutor(max_workers=len(collectors)) as ex:
        futures = {ex.submit(_run_one, name, fn): name for name, fn in collectors}
        for fut in as_completed(futures):
            name, df, st = fut.result()
            fresh_frames[name] = df
            status[name] = st
            if st == "NO DATA":
                logger.warning(f"  {name}: returned no data")

    # ── Merge fresh data with existing panel ──────────────────────────
    logger.info("\n" + "-" * 60)
    logger.info("MERGING fresh data with existing panel ...")
    panel = merge_panels(existing_panel, fresh_frames, status)

    if panel.empty:
        logger.error("Panel is empty after merge — aborting.")
        return

    logger.info(f"Merged panel: {len(panel):,} rows")

    # Quality checks (also deduplicates in-place)
    run_quality_checks(panel)
    panel = panel.drop_duplicates(subset=["date", "country", "variable"])

    catalog = create_variable_catalog(panel)

    # ── Save (unless --dry-run) ───────────────────────────────────────
    if args.dry_run:
        logger.info("\n--dry-run: skipping file writes")
    else:
        backup_panel()
        panel.to_parquet(PANEL_PATH, index=False)
        panel.to_csv(CSV_PATH, index=False)
        catalog.to_csv(CAT_PATH, index=False)
        logger.info(f"\nSaved: {PANEL_PATH}")
        logger.info(f"Saved: {CSV_PATH}")
        logger.info(f"Saved: {CAT_PATH}")

    # ── Record run metadata ───────────────────────────────────────────
    elapsed = time.time() - t0
    if not args.dry_run:
        record_run(status, panel, elapsed)

    # ── Delta report (what changed vs. previous) ─────────────────────
    if existing_panel is not None:
        old_rows = len(existing_panel)
        new_rows = len(panel)
        delta = new_rows - old_rows
        sign = "+" if delta >= 0 else ""
        logger.info(f"\nDelta vs. previous: {old_rows:,} → {new_rows:,} ({sign}{delta:,} rows)")

        old_max = existing_panel["date"].max()
        new_max = panel["date"].max()
        if new_max > old_max:
            logger.info(f"  Date range extended: {old_max.strftime('%Y-%m')} → "
                        f"{new_max.strftime('%Y-%m')}")

    # ── Final summary ─────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("COLLECTION SUMMARY")
    logger.info("=" * 60)
    for name, st in status.items():
        marker = "OK" if st == "SUCCESS" else "WARN"
        logger.info(f"  [{marker:4s}] {name:25s} {st}")

    n_sources_ok = sum(1 for s in status.values() if s == "SUCCESS")
    n_vars = panel["variable"].nunique()
    n_ctry = panel["country"].nunique()
    logger.info(f"\nSources OK    : {n_sources_ok}/7 (need >= 5)")
    logger.info(f"Variables     : {n_vars}")
    logger.info(f"Countries     : {n_ctry}/34")
    logger.info(f"Total rows    : {len(panel):,}")
    logger.info(f"Date range    : {panel['date'].min().strftime('%Y-%m')} → "
                f"{panel['date'].max().strftime('%Y-%m')}")
    logger.info(f"Elapsed       : {elapsed:.1f}s")

    epu_ctry = panel.loc[panel["variable"] == "EPU", "country"].nunique()
    bis_ctry = panel.loc[panel["variable"] == "BIS_Credit_GDP_Gap", "country"].nunique()
    logger.info(f"\nSuccess criteria:")
    logger.info(f"  Sources >= 5    : {'PASS' if n_sources_ok >= 5 else 'FAIL'} ({n_sources_ok})")
    logger.info(f"  EPU >= 25 ctry  : {'PASS' if epu_ctry >= 25 else 'FAIL'} ({epu_ctry})")
    logger.info(f"  BIS CG >= 20    : {'PASS' if bis_ctry >= 20 else 'FAIL'} ({bis_ctry})")

    if n_sources_ok >= 5:
        logger.info("\nALL CRITICAL CRITERIA MET.")
    else:
        logger.warning("\nSOME CRITERIA NOT MET — review above.")

    logger.info("=" * 60)


if __name__ == "__main__":
    main()
