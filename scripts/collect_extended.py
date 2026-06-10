#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: collect_extended.py
=============================================================================

INPUT FILES:
- config/country_mapping.json: Maps 34 T2 countries to source-specific codes
  (ISO-2, ISO-3, OECD, BIS, World Bank, IMF, etc.)
- .env or env vars: API keys for FRED, EIA, ACLED, UN Comtrade (optional)

OUTPUT FILES:
- Data/processed/extended_factors_panel.parquet  (primary — tidy panel)
- Data/processed/extended_factors_panel.csv      (secondary — CSV copy)
- Data/processed/extended_variable_catalog.csv   (metadata per variable)

VERSION: 1.0
LAST UPDATED: 2026-04-11
AUTHOR: Arjun Divecha

DESCRIPTION:
Downloads, parses, and caches data from up to 12 extended external sources
(sources 8–19 in the data collection plan), aligns everything to the
34-country T2 Master universe, and outputs a tidy panel.

Sources collected:
  NO-KEY SOURCES (8):
   8. BIS Additional  — Central bank policy rates (monthly) + debt service (quarterly)
   9. OECD Additional — Business Confidence BCI + Consumer Confidence CCI (monthly)
  10. ECB             — EUR exchange rates + monetary aggregates (monthly)
  11. ND-GAIN         — Climate vulnerability index (annual)
  12. ILOSTAT         — Unemployment rate, labor force participation (annual)
  13. UNDP HDI        — Human Development Index (annual, 1990–2023)
  14. OFAC            — US sanctions list (country presence, point-in-time)
  15. FAOSTAT         — Food trade data: crops & livestock (annual)

  KEYED SOURCES (4 — skip gracefully if key missing):
  16. FRED            — VIX, yield curves, global macro (daily/monthly)
  17. EIA             — Energy production/consumption (annual)
  18. ACLED           — Armed conflict events (monthly)
  19. UN Comtrade     — Bilateral trade flows (annual)

DEPENDENCIES:
- pandas, numpy, requests, openpyxl, pyarrow, sdmx1, tqdm

USAGE:
  python scripts/collect_extended.py              # normal monthly update
  python scripts/collect_extended.py --force       # bypass 24h download cache
  python scripts/collect_extended.py --dry-run     # preview changes, don't save

NOTES:
- Raw downloads cached in Data/raw/ with 24-hour expiry
- Each source wrapped in try/except — pipeline never fails entirely
- Monthly-safe: if a source fails, existing data for that source is preserved
- Timestamped backup saved before every overwrite
- Run history tracked in Data/processed/extended_run_history.json
- Keyed sources fail gracefully with clear message if API key not found
=============================================================================
"""

import argparse
import csv
import json
import logging
import os
import shutil
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from io import BytesIO, StringIO
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
            CACHE_DIR / f"extended_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
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

COLLECTOR_SOURCE_KEYS = {
    "BIS Policy Rates":    ["bis_policy_rate"],
    "BIS Debt Service":    ["bis_debt_service"],
    "OECD BCI":            ["oecd_bci"],
    "OECD CCI":            ["oecd_cci"],
    "ECB FX":              ["ecb_fx"],
    "ND-GAIN":             ["ndgain"],
    "ILOSTAT":             ["ilostat"],
    "UNDP HDI":            ["undp_hdi"],
    "OFAC Sanctions":      ["ofac"],
    "FAOSTAT":             ["faostat"],
    "FRED":                ["fred"],
    "EIA":                 ["eia"],
    "ACLED":               ["acled"],
    "UN Comtrade":         ["comtrade"],
}

PANEL_PATH = PROCESSED_DIR / "extended_factors_panel.parquet"
CSV_PATH = PROCESSED_DIR / "extended_factors_panel.csv"
CAT_PATH = PROCESSED_DIR / "extended_variable_catalog.csv"
HISTORY_PATH = PROCESSED_DIR / "extended_run_history.json"
BACKUP_DIR = DATA_DIR / "backups"

# ── API Key file ──────────────────────────────────────────────────────────
ENV_FILE = Path("/Users/arjundivecha/Dropbox/AAA Backup/.env.txt")


# ═══════════════════════════════════════════════════════════════════════════
# INFRASTRUCTURE (shared with collect_external.py)
# ═══════════════════════════════════════════════════════════════════════════

class CacheManager:
    """File caching with 24-hour expiry."""

    @staticmethod
    def is_valid(filepath: Path, max_age_hours: int = 24) -> bool:
        if not filepath.exists():
            return False
        age = datetime.now() - datetime.fromtimestamp(filepath.stat().st_mtime)
        return age < timedelta(hours=max_age_hours)


def fetch_with_retry(url: str, max_retries: int = 3, timeout: int = 120,
                     headers: Optional[Dict] = None) -> requests.Response:
    """HTTP GET with exponential-backoff retries."""
    session = requests.Session()
    retry = Retry(total=max_retries, backoff_factor=2,
                  status_forcelist=[429, 500, 502, 503, 504])
    session.mount("http://", HTTPAdapter(max_retries=retry))
    session.mount("https://", HTTPAdapter(max_retries=retry))
    resp = session.get(url, timeout=timeout, headers=headers or {})
    resp.raise_for_status()
    return resp


def download_and_cache(url: str, cache_path: Path, label: str,
                       headers: Optional[Dict] = None) -> Path:
    """Download a file to cache_path if cache has expired."""
    if CacheManager.is_valid(cache_path):
        logger.info(f"  Using cached {label}")
    else:
        logger.info(f"  Downloading {label} ...")
        resp = fetch_with_retry(url, headers=headers)
        cache_path.write_bytes(resp.content)
        logger.info(f"  Saved {cache_path.name} ({len(resp.content) / 1e6:.1f} MB)")
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


def _parse_period(period_str: str) -> Optional[pd.Timestamp]:
    """Parse period strings: 2020-Q1 → 2020-03-01, 2020-01 → 2020-01-01, etc."""
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


def _log_source_summary(label: str, df: pd.DataFrame) -> None:
    """Standard one-line summary for a collected source."""
    n_obs = len(df)
    n_ctry = df["country"].nunique()
    d_min = df["date"].min().strftime("%Y-%m")
    d_max = df["date"].max().strftime("%Y-%m")
    n_vars = df["variable"].nunique()
    logger.info(f"      → {label}: {n_obs:,} obs, {n_ctry} countries, "
                f"{n_vars} variable(s), {d_min} to {d_max}")


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


def load_api_key(key_name: str) -> Optional[str]:
    """Load an API key from env vars or .env.txt file."""
    val = os.environ.get(key_name)
    if val:
        return val
    if ENV_FILE.exists():
        with open(ENV_FILE) as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{key_name}="):
                    return line.split("=", 1)[1].strip()
    return None


# ═══════════════════════════════════════════════════════════════════════════
# MONTHLY-UPDATE INFRASTRUCTURE
# ═══════════════════════════════════════════════════════════════════════════

def load_existing_panel() -> Optional[pd.DataFrame]:
    """Load the existing extended panel from disk (if any)."""
    if PANEL_PATH.exists():
        df = pd.read_parquet(PANEL_PATH)
        logger.info(f"Loaded existing panel: {len(df):,} rows, "
                    f"{df['source'].nunique()} sources")
        return df
    logger.info("No existing extended panel found — starting fresh")
    return None


def backup_panel() -> Optional[Path]:
    """Save a timestamped backup before overwriting."""
    if not PANEL_PATH.exists():
        return None
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    backup = BACKUP_DIR / f"extended_factors_panel_{ts}.parquet"
    shutil.copy2(PANEL_PATH, backup)
    logger.info(f"Backed up existing panel → {backup.name}")
    return backup


def merge_panels(existing: Optional[pd.DataFrame],
                 fresh_frames: Dict[str, pd.DataFrame],
                 source_status: Dict[str, str]) -> pd.DataFrame:
    """Source-level merge: replace successful, keep existing for failures."""
    if existing is None:
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
    if HISTORY_PATH.exists():
        with open(HISTORY_PATH) as f:
            data = json.load(f)
        # Backwards-compat: older versions wrote a bare list
        if isinstance(data, list):
            return {"runs": data}
        return data
    return {"runs": []}


def save_run_history(history: Dict) -> None:
    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2, default=str)


def record_run(source_status: Dict[str, str], panel: pd.DataFrame,
               elapsed: float) -> None:
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
    history["runs"] = history["runs"][-24:]
    save_run_history(history)
    logger.info(f"Saved run history → {HISTORY_PATH.name}")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Phase 1 Program 2: Extended Data Collection (sources 8-19)"
    )
    parser.add_argument("--force", action="store_true",
                        help="Bypass 24-hour download cache")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and merge but do NOT save output files")
    return parser.parse_args()


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE 8: BIS CENTRAL BANK POLICY RATES  (SDMX API)
# ═══════════════════════════════════════════════════════════════════════════

def collect_bis_policy_rates(countries: Dict) -> pd.DataFrame:
    logger.info("[1/12] BIS Central Bank Policy Rates ...")

    try:
        import sdmx

        bis_rev = _build_reverse_map(countries, "bis")
        client = sdmx.Client("BIS")

        logger.info("  Querying BIS SDMX WS_CBPOL ...")
        data = client.data("WS_CBPOL", params={"startPeriod": "2000-01"})
        dataset = data.data[0]
        logger.info(f"  Received {len(dataset.series)} series")

        records = []
        for series_key, obs_list in dataset.series.items():
            country_code = _sdmx_key_value(series_key, "REF_AREA")
            if not country_code or country_code not in bis_rev:
                continue
            for obs in obs_list:
                period = _sdmx_obs_period(obs)
                if not period:
                    continue
                val = pd.to_numeric(obs.value, errors="coerce")
                if pd.isna(val):
                    continue
                date = _parse_period(period)
                if date is None:
                    continue
                for t2 in bis_rev[country_code]:
                    records.append({
                        "date": date, "country": t2, "value": float(val),
                        "variable": "BIS_Policy_Rate", "source": "bis_policy_rate",
                    })

        result = pd.DataFrame(records)
        if result.empty:
            logger.warning("  No BIS policy rate records")
            return pd.DataFrame()

        # Resample to monthly (take last value per month)
        result["date"] = result["date"].dt.to_period("M").dt.to_timestamp()
        result = (result.sort_values("date")
                  .drop_duplicates(subset=["date", "country", "variable"], keep="last"))
        _log_source_summary("BIS Policy Rates", result)
        return result

    except Exception as e:
        logger.error(f"  BIS Policy Rates FAILED: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE 9: BIS DEBT SERVICE RATIOS  (SDMX API)
# ═══════════════════════════════════════════════════════════════════════════

def collect_bis_debt_service(countries: Dict) -> pd.DataFrame:
    logger.info("[2/12] BIS Debt Service Ratios ...")

    try:
        import sdmx

        bis_rev = _build_reverse_map(countries, "bis")
        client = sdmx.Client("BIS")

        logger.info("  Querying BIS SDMX WS_DSR ...")
        data = client.data("WS_DSR", params={"startPeriod": "2000-Q1"})
        dataset = data.data[0]
        logger.info(f"  Received {len(dataset.series)} series")

        records = []
        for series_key, obs_list in dataset.series.items():
            country_code = _sdmx_key_value(series_key, "BORROWERS_CTY")
            if not country_code or country_code not in bis_rev:
                continue
            # Private non-financial sector only
            tc = _sdmx_key_value(series_key, "BORROWERS_SECTOR")
            if tc and tc != "P":
                continue
            for obs in obs_list:
                period = _sdmx_obs_period(obs)
                if not period:
                    continue
                val = pd.to_numeric(obs.value, errors="coerce")
                if pd.isna(val):
                    continue
                date = _parse_period(period)
                if date is None:
                    continue
                for t2 in bis_rev[country_code]:
                    records.append({
                        "date": date, "country": t2, "value": float(val),
                        "variable": "BIS_DSR_Private",
                        "source": "bis_debt_service",
                    })

        result = pd.DataFrame(records)
        if result.empty:
            logger.warning("  No BIS debt service records")
            return pd.DataFrame()

        result = result.drop_duplicates(subset=["date", "country", "variable"])
        _log_source_summary("BIS Debt Service", result)
        return result

    except Exception as e:
        logger.error(f"  BIS Debt Service FAILED: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE 10: OECD BUSINESS CONFIDENCE INDEX (CSV REST API)
# ═══════════════════════════════════════════════════════════════════════════

def collect_oecd_bci(countries: Dict) -> pd.DataFrame:
    logger.info("[3/12] OECD Business Confidence Index ...")

    try:
        oecd_rev = _build_reverse_map(countries, "oecd")
        if not oecd_rev:
            logger.warning("  No OECD country mappings")
            return pd.DataFrame()

        codes_str = "+".join(sorted(oecd_rev.keys()))
        # BTS dataflow with BCICP measure, 9 dimensions
        url = (
            f"https://sdmx.oecd.org/public/rest/data/"
            f"OECD.SDD.STES,DSD_STES@DF_BTS,4.0/"
            f"{codes_str}.M.BCICP......?"
            f"startPeriod=2000-01&format=csvfilewithlabels"
        )
        cache_path = RAW_DIR / "oecd_bci.csv"
        download_and_cache(url, cache_path, "OECD BCI CSV")

        df = pd.read_csv(cache_path, low_memory=False)
        logger.info(f"  BCI CSV: {len(df)} rows")

        records = []
        for _, row in df.iterrows():
            code = str(row.get("REF_AREA", "")).strip()
            if code not in oecd_rev:
                continue
            period = str(row.get("TIME_PERIOD", "")).strip()
            date = _parse_period(period)
            if date is None:
                continue
            val = pd.to_numeric(row.get("OBS_VALUE"), errors="coerce")
            if pd.isna(val):
                continue
            for t2 in oecd_rev[code]:
                records.append({
                    "date": date, "country": t2, "value": float(val),
                    "variable": "OECD_BCI", "source": "oecd_bci",
                })

        if not records:
            logger.warning("  No OECD BCI records")
            return pd.DataFrame()

        result = pd.DataFrame(records)
        result = result.drop_duplicates(subset=["date", "country", "variable"])
        _log_source_summary("OECD BCI", result)
        return result

    except Exception as e:
        logger.error(f"  OECD BCI FAILED: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE 11: OECD CONSUMER CONFIDENCE INDEX (CSV REST API)
# ═══════════════════════════════════════════════════════════════════════════

def collect_oecd_cci(countries: Dict) -> pd.DataFrame:
    logger.info("[4/12] OECD Consumer Confidence Index ...")

    try:
        oecd_rev = _build_reverse_map(countries, "oecd")
        if not oecd_rev:
            logger.warning("  No OECD country mappings")
            return pd.DataFrame()

        codes_str = "+".join(sorted(oecd_rev.keys()))
        url = (
            f"https://sdmx.oecd.org/public/rest/data/"
            f"OECD.SDD.STES,DSD_STES@DF_CS,4.0/"
            f"{codes_str}.M.CCICP......?"
            f"startPeriod=2000-01&format=csvfilewithlabels"
        )
        cache_path = RAW_DIR / "oecd_cci.csv"
        download_and_cache(url, cache_path, "OECD CCI CSV")

        df = pd.read_csv(cache_path, low_memory=False)
        logger.info(f"  CCI CSV: {len(df)} rows")

        records = []
        for _, row in df.iterrows():
            code = str(row.get("REF_AREA", "")).strip()
            if code not in oecd_rev:
                continue
            period = str(row.get("TIME_PERIOD", "")).strip()
            date = _parse_period(period)
            if date is None:
                continue
            val = pd.to_numeric(row.get("OBS_VALUE"), errors="coerce")
            if pd.isna(val):
                continue
            for t2 in oecd_rev[code]:
                records.append({
                    "date": date, "country": t2, "value": float(val),
                    "variable": "OECD_CCI", "source": "oecd_cci",
                })

        if not records:
            logger.warning("  No OECD CCI records")
            return pd.DataFrame()

        result = pd.DataFrame(records)
        result = result.drop_duplicates(subset=["date", "country", "variable"])
        _log_source_summary("OECD CCI", result)
        return result

    except Exception as e:
        logger.error(f"  OECD CCI FAILED: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE 12: ECB EXCHANGE RATES  (SDMX API)
# ═══════════════════════════════════════════════════════════════════════════

ECB_CURRENCY_MAP = {
    "AUD": "AU", "BRL": "BR", "CAD": "CA", "CHF": "CH", "CNY": "CN",
    "DKK": "DK", "GBP": "GB", "HKD": "HK", "IDR": "ID", "INR": "IN",
    "JPY": "JP", "KRW": "KR", "MXN": "MX", "MYR": "MY", "NOK": "NO",
    "NZD": "NZ", "PHP": "PH", "PLN": "PL", "SEK": "SE", "SGD": "SG",
    "THB": "TH", "TRY": "TR", "TWD": "TW", "USD": "US", "ZAR": "ZA",
}


def collect_ecb_fx(countries: Dict) -> pd.DataFrame:
    logger.info("[5/12] ECB Exchange Rates ...")

    try:
        import sdmx

        bis_rev = _build_reverse_map(countries, "bis")
        client = sdmx.Client("ECB")

        records = []
        failed = []
        for ccy, bis_code in ECB_CURRENCY_MAP.items():
            if bis_code not in bis_rev:
                continue
            try:
                data = client.data(
                    "EXR",
                    key=f"M.{ccy}.EUR.SP00.A",
                    params={"startPeriod": "2000-01"},
                )
                if not data.data:
                    failed.append(ccy)
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
                        date = _parse_period(period)
                        if date is None:
                            continue
                        for t2 in bis_rev[bis_code]:
                            records.append({
                                "date": date, "country": t2, "value": float(val),
                                "variable": f"ECB_FX_{ccy}_EUR",
                                "source": "ecb_fx",
                            })
            except Exception:
                failed.append(ccy)

        if failed:
            logger.info(f"  ECB FX: no data for {len(failed)} currencies: "
                        f"{failed[:10]}")

        # Eurozone countries get EUR=1.0 (they are the base currency)
        euro_bis = ["DE", "FR", "IT", "ES", "NL"]
        for bis_code in euro_bis:
            if bis_code not in bis_rev:
                continue
            if records:
                dates = sorted(set(r["date"] for r in records))
                for dt in dates:
                    for t2 in bis_rev[bis_code]:
                        records.append({
                            "date": dt, "country": t2, "value": 1.0,
                            "variable": "ECB_FX_EUR_EUR", "source": "ecb_fx",
                        })

        result = pd.DataFrame(records)
        if result.empty:
            logger.warning("  No ECB FX records")
            return pd.DataFrame()

        result = result.drop_duplicates(subset=["date", "country", "variable"])
        _log_source_summary("ECB FX", result)
        return result

    except Exception as e:
        logger.error(f"  ECB FX FAILED: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE 13: ND-GAIN CLIMATE VULNERABILITY  (CSV download)
# ═══════════════════════════════════════════════════════════════════════════

def collect_ndgain(countries: Dict) -> pd.DataFrame:
    logger.info("[6/12] ND-GAIN Climate Vulnerability Index ...")

    try:
        zip_url = ("https://gain-new.crc.nd.edu/assets/gain/files/"
                   "resources-2026-23-00-11h22.zip")
        zip_cache = RAW_DIR / "ndgain_data.zip"

        if not CacheManager.is_valid(zip_cache):
            logger.info("  Downloading ND-GAIN ZIP ...")
            resp = fetch_with_retry(zip_url, timeout=60)
            zip_cache.write_bytes(resp.content)
            logger.info(f"  ZIP: {len(resp.content) / 1e6:.1f} MB")
        else:
            logger.info("  Using cached ND-GAIN ZIP")

        iso3_rev = _build_reverse_map(countries, "iso3")

        records = []
        files_to_read = {
            "resources/gain/gain.csv": "NDGAIN_Score",
            "resources/vulnerability/vulnerability.csv": "NDGAIN_Vulnerability",
            "resources/readiness/readiness.csv": "NDGAIN_Readiness",
        }

        with zipfile.ZipFile(zip_cache) as zf:
            for csv_name, var_name in files_to_read.items():
                try:
                    with zf.open(csv_name) as f:
                        df = pd.read_csv(f)
                    year_cols = [c for c in df.columns
                                 if c.isdigit() and len(c) == 4]
                    for _, row in df.iterrows():
                        iso = str(row.get("ISO3", "")).strip()
                        if iso not in iso3_rev:
                            continue
                        for yr_col in year_cols:
                            val = pd.to_numeric(row.get(yr_col), errors="coerce")
                            if pd.isna(val):
                                continue
                            date = pd.Timestamp(year=int(yr_col), month=12, day=1)
                            for t2 in iso3_rev[iso]:
                                records.append({
                                    "date": date, "country": t2,
                                    "value": float(val),
                                    "variable": var_name, "source": "ndgain",
                                })
                    logger.info(f"    {var_name}: {len(year_cols)} years")
                except Exception as e:
                    logger.warning(f"    {csv_name}: {e}")

        if not records:
            logger.warning("  No ND-GAIN records matched")
            return pd.DataFrame()

        result = pd.DataFrame(records)
        result = result.drop_duplicates(subset=["date", "country", "variable"])
        _log_source_summary("ND-GAIN", result)
        return result

    except Exception as e:
        logger.error(f"  ND-GAIN FAILED: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE 14: ILOSTAT LABOR MARKET  (SDMX API)
# ═══════════════════════════════════════════════════════════════════════════

ILOSTAT_INDICATORS = {
    "UNE_DEAP_SEX_AGE_RT": {
        "variable": "ILO_Unemployment_Rate",
        "filter": {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"},
    },
    "EAP_DWAP_SEX_AGE_RT": {
        "variable": "ILO_LFP_Rate",
        "filter": {"SEX": "SEX_T", "AGE": "AGE_YTHADULT_YGE15"},
    },
}


def collect_ilostat(countries: Dict) -> pd.DataFrame:
    logger.info("[7/12] ILOSTAT Labor Market ...")

    try:
        iso3_rev = _build_reverse_map(countries, "iso3")
        codes_str = "+".join(sorted(iso3_rev.keys()))

        records = []
        for flow_id, spec in ILOSTAT_INDICATORS.items():
            logger.info(f"  Fetching {spec['variable']} ...")
            try:
                url = (
                    f"https://sdmx.ilo.org/rest/data/ILO,DF_{flow_id},1.0/"
                    f"{codes_str}.A....?"
                    f"startPeriod=2000&format=csvfile"
                )
                cache_path = RAW_DIR / f"ilostat_{flow_id}.csv"
                download_and_cache(url, cache_path, f"ILOSTAT {flow_id}")

                df = pd.read_csv(cache_path, low_memory=False)
                logger.info(f"    {flow_id}: {len(df)} rows")

                for _, row in df.iterrows():
                    ref_area = str(row.get("REF_AREA", "")).strip()
                    if ref_area not in iso3_rev:
                        continue

                    # Apply dimension filters
                    skip = False
                    for dim, val in spec["filter"].items():
                        actual = str(row.get(dim, "")).strip()
                        if actual != val:
                            skip = True
                            break
                    if skip:
                        continue

                    period = str(row.get("TIME_PERIOD", "")).strip()
                    date = _parse_period(period)
                    if date is None:
                        continue
                    val = pd.to_numeric(row.get("OBS_VALUE"), errors="coerce")
                    if pd.isna(val):
                        continue

                    for t2 in iso3_rev[ref_area]:
                        records.append({
                            "date": date, "country": t2, "value": float(val),
                            "variable": spec["variable"], "source": "ilostat",
                        })

            except Exception as e:
                logger.warning(f"    {flow_id} FAILED: {e}")

        if not records:
            logger.warning("  No ILOSTAT records")
            return pd.DataFrame()

        result = pd.DataFrame(records)
        result = result.drop_duplicates(subset=["date", "country", "variable"])
        _log_source_summary("ILOSTAT", result)
        return result

    except Exception as e:
        logger.error(f"  ILOSTAT FAILED: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE 15: UNDP HUMAN DEVELOPMENT INDEX  (CSV download)
# ═══════════════════════════════════════════════════════════════════════════

def collect_undp_hdi(countries: Dict) -> pd.DataFrame:
    logger.info("[8/12] UNDP Human Development Index ...")

    try:
        url = ("https://hdr.undp.org/sites/default/files/2025_HDR/"
               "HDR25_Composite_indices_complete_time_series.csv")
        cache_path = RAW_DIR / "undp_hdi_timeseries.csv"
        download_and_cache(url, cache_path, "UNDP HDI CSV")

        df = pd.read_csv(cache_path, encoding="latin-1")
        logger.info(f"  UNDP HDI CSV: {len(df)} rows, cols: {list(df.columns[:10])}")

        iso3_rev = _build_reverse_map(countries, "iso3")

        # File has columns: iso3, country, hdicode, region, hdi_rank_2023,
        # hdi_1990, hdi_1991, ..., hdi_2023, plus other indices
        hdi_cols = [c for c in df.columns if c.startswith("hdi_") and c[-4:].isdigit()]
        logger.info(f"  Found {len(hdi_cols)} HDI year columns")

        records = []
        for _, row in df.iterrows():
            iso = str(row.get("iso3", "")).strip()
            if iso not in iso3_rev:
                continue
            for col in hdi_cols:
                yr = int(col.split("_")[-1])
                val = pd.to_numeric(row.get(col), errors="coerce")
                if pd.isna(val):
                    continue
                date = pd.Timestamp(year=yr, month=12, day=1)
                for t2 in iso3_rev[iso]:
                    records.append({
                        "date": date, "country": t2, "value": float(val),
                        "variable": "UNDP_HDI", "source": "undp_hdi",
                    })

        # Also grab inequality-adjusted HDI, gender development, etc.
        for prefix, var_name in [
            ("ihdi_", "UNDP_IHDI"),
            ("gdi_", "UNDP_GDI"),
            ("gii_", "UNDP_GII"),
        ]:
            extra_cols = [c for c in df.columns
                          if c.startswith(prefix) and c.replace(prefix, "").isdigit()]
            for _, row in df.iterrows():
                iso = str(row.get("iso3", "")).strip()
                if iso not in iso3_rev:
                    continue
                for col in extra_cols:
                    yr = int(col.replace(prefix, ""))
                    val = pd.to_numeric(row.get(col), errors="coerce")
                    if pd.isna(val):
                        continue
                    date = pd.Timestamp(year=yr, month=12, day=1)
                    for t2 in iso3_rev[iso]:
                        records.append({
                            "date": date, "country": t2, "value": float(val),
                            "variable": var_name, "source": "undp_hdi",
                        })

        if not records:
            logger.warning("  No UNDP HDI records")
            return pd.DataFrame()

        result = pd.DataFrame(records)
        result = result.drop_duplicates(subset=["date", "country", "variable"])
        _log_source_summary("UNDP HDI", result)
        return result

    except Exception as e:
        logger.error(f"  UNDP HDI FAILED: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE 16: OFAC SANCTIONS  (CSV download)
# ═══════════════════════════════════════════════════════════════════════════

def collect_ofac(countries: Dict) -> pd.DataFrame:
    logger.info("[9/12] OFAC Sanctions List ...")

    try:
        url = "https://www.treasury.gov/ofac/downloads/sdn.csv"
        cache_path = RAW_DIR / "ofac_sdn.csv"
        download_and_cache(url, cache_path, "OFAC SDN CSV")

        # SDN list doesn't have proper headers — columns are:
        # ent_num, sdn_name, sdn_type, program, title, call_sign,
        # vess_type, tonnage, grt, vess_flag, vess_owner, remarks
        col_names = [
            "ent_num", "sdn_name", "sdn_type", "program", "title",
            "call_sign", "vess_type", "tonnage", "grt", "vess_flag",
            "vess_owner", "remarks"
        ]
        df = pd.read_csv(cache_path, header=None, names=col_names,
                          encoding="latin-1", on_bad_lines="warn",
                          quoting=csv.QUOTE_MINIMAL)
        logger.info(f"  OFAC SDN: {len(df)} entries")

        # Count sanctions entries by country (from remarks field and program)
        iso2_rev = _build_reverse_map(countries, "iso2")
        iso3_rev = _build_reverse_map(countries, "iso3")

        # Build country → count from the remarks field
        country_counts: Dict[str, int] = {}
        for _, row in df.iterrows():
            remarks = str(row.get("remarks", ""))
            program = str(row.get("program", ""))
            # Look for country references in program name
            for code, t2_list in iso2_rev.items():
                if code in remarks or code in program:
                    for t2 in t2_list:
                        country_counts[t2] = country_counts.get(t2, 0) + 1

        now = pd.Timestamp.now().normalize().replace(day=1)
        records = []
        for t2 in T2_COUNTRIES:
            count = country_counts.get(t2, 0)
            records.append({
                "date": now, "country": t2, "value": float(count),
                "variable": "OFAC_Sanctions_Count", "source": "ofac",
            })
            records.append({
                "date": now, "country": t2,
                "value": 1.0 if count > 0 else 0.0,
                "variable": "OFAC_Sanctioned", "source": "ofac",
            })

        result = pd.DataFrame(records)
        result = result.drop_duplicates(subset=["date", "country", "variable"])
        _log_source_summary("OFAC", result)
        return result

    except Exception as e:
        logger.error(f"  OFAC FAILED: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE 17: FAOSTAT FOOD TRADE  (bulk CSV download)
# ═══════════════════════════════════════════════════════════════════════════

def collect_faostat(countries: Dict) -> pd.DataFrame:
    logger.info("[10/12] FAOSTAT Food Trade ...")

    try:
        # Use trade indicators bulk download
        url = ("https://bulks-faostat.fao.org/production/"
               "Trade_CropsLivestockIndicators_E_All_Data_(Normalized).zip")
        zip_cache = RAW_DIR / "faostat_trade_indicators.zip"
        csv_cache = RAW_DIR / "faostat_trade_indicators.csv"

        if not CacheManager.is_valid(csv_cache):
            logger.info("  Downloading FAOSTAT bulk ZIP ...")
            resp = fetch_with_retry(url, timeout=180)
            zip_cache.write_bytes(resp.content)
            logger.info(f"  ZIP: {len(resp.content) / 1e6:.1f} MB")

            # Extract CSV from zip
            with zipfile.ZipFile(zip_cache) as zf:
                csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
                if not csv_names:
                    logger.error("  No CSV in ZIP")
                    return pd.DataFrame()
                with zf.open(csv_names[0]) as src:
                    csv_cache.write_bytes(src.read())
                logger.info(f"  Extracted: {csv_names[0]}")
        else:
            logger.info("  Using cached FAOSTAT CSV")

        # Parse: Area Code (M49), Area, Item Code, Item, Element Code, Element,
        #         Year Code, Year, Unit, Value, Flag
        df = pd.read_csv(csv_cache, low_memory=False, encoding="latin-1")
        logger.info(f"  FAOSTAT CSV: {len(df)} rows, cols: {list(df.columns[:8])}")

        # Map M49 country codes or ISO3 to T2
        iso3_rev = _build_reverse_map(countries, "iso3")

        # Try to find area/country column
        area_col = None
        for cand in ["Area Code (M49)", "Area Code", "area_code"]:
            if cand in df.columns:
                area_col = cand
                break

        area_name_col = None
        for cand in ["Area", "area"]:
            if cand in df.columns:
                area_name_col = cand
                break

        element_col = None
        for cand in ["Element", "element", "Indicator", "indicator"]:
            if cand in df.columns:
                element_col = cand
                break

        year_col = None
        for cand in ["Year", "year", "Year Code"]:
            if cand in df.columns:
                year_col = cand
                break

        value_col = None
        for cand in ["Value", "value"]:
            if cand in df.columns:
                value_col = cand
                break

        if not all([area_name_col, element_col, year_col, value_col]):
            logger.error(f"  Missing columns. Found: {list(df.columns[:15])}")
            return pd.DataFrame()

        # Map FAO country names to ISO3
        fao_to_iso3 = {
            "Australia": "AUS", "Brazil": "BRA", "Canada": "CAN",
            "Chile": "CHL", "China, mainland": "CHN",
            "China, Hong Kong SAR": "HKG", "China, Taiwan Province of": "TWN",
            "Denmark": "DNK", "France": "FRA", "Germany": "DEU",
            "India": "IND", "Indonesia": "IDN", "Italy": "ITA",
            "Japan": "JPN", "Republic of Korea": "KOR", "Malaysia": "MYS",
            "Mexico": "MEX", "Netherlands (Kingdom of the)": "NLD",
            "Philippines": "PHL", "Poland": "POL", "Saudi Arabia": "SAU",
            "Singapore": "SGP", "South Africa": "ZAF", "Spain": "ESP",
            "Sweden": "SWE", "Switzerland": "CHE", "Thailand": "THA",
            "Türkiye": "TUR", "Turkey": "TUR",
            "United Kingdom of Great Britain and Northern Ireland": "GBR",
            "United States of America": "USA", "Viet Nam": "VNM",
        }

        # FAOSTAT trade indicators: Import dependency, Self-sufficiency,
        # Trade openness, Terms of trade, etc.
        indicator_col = None
        for cand in ["Indicator", "indicator"]:
            if cand in df.columns:
                indicator_col = cand
                break
        if indicator_col is None:
            indicator_col = element_col
        if indicator_col is None:
            logger.error("  No Indicator or Element column found")
            return pd.DataFrame()

        fao_var_map = {
            "Import dependency ratio": "FAO_Import_Dependency",
            "Self-sufficiency ratio": "FAO_Self_Sufficiency",
            "Agricultural trade openness index": "FAO_Trade_Openness",
            "Terms of trade": "FAO_Terms_of_Trade",
            "Share of agricultural exports to GDP": "FAO_AgExport_GDP_Share",
        }

        records = []
        for _, row in df.iterrows():
            area = str(row.get(area_name_col, "")).strip()
            iso3 = fao_to_iso3.get(area)
            if not iso3 or iso3 not in iso3_rev:
                continue

            indicator = str(row.get(indicator_col, "")).strip()
            var_name = fao_var_map.get(indicator)
            if not var_name:
                continue

            yr = pd.to_numeric(row.get(year_col), errors="coerce")
            if pd.isna(yr) or yr < 2000:
                continue

            val = pd.to_numeric(row.get(value_col), errors="coerce")
            if pd.isna(val):
                continue

            date = pd.Timestamp(year=int(yr), month=12, day=1)

            for t2 in iso3_rev[iso3]:
                records.append({
                    "date": date, "country": t2, "value": float(val),
                    "variable": var_name, "source": "faostat",
                })

        if not records:
            logger.warning("  No FAOSTAT records matched")
            return pd.DataFrame()

        result = pd.DataFrame(records)
        result = result.drop_duplicates(subset=["date", "country", "variable"])
        _log_source_summary("FAOSTAT", result)
        return result

    except Exception as e:
        logger.error(f"  FAOSTAT FAILED: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE 18: FRED  (REST API, needs key)
# ═══════════════════════════════════════════════════════════════════════════

FRED_SERIES = {
    "VIXCLS":      ("FRED_VIX",               "Global"),
    "DGS10":       ("FRED_UST_10Y",           "US"),
    "DGS2":        ("FRED_UST_2Y",            "US"),
    "T10Y2Y":      ("FRED_Yield_Curve_10Y2Y", "US"),
    "DTWEXBGS":    ("FRED_USD_Broad_Index",   "Global"),
    "BAMLH0A0HYM2": ("FRED_HY_OAS",          "Global"),
}


def collect_fred(countries: Dict) -> pd.DataFrame:
    logger.info("[11/12] FRED Economic Data ...")

    api_key = load_api_key("FRED_API_KEY")
    if not api_key:
        logger.warning("  FRED_API_KEY not found — skipping FRED")
        return pd.DataFrame()

    try:
        records = []
        for series_id, (var_name, scope) in FRED_SERIES.items():
            try:
                url = (
                    f"https://api.stlouisfed.org/fred/series/observations?"
                    f"series_id={series_id}&api_key={api_key}"
                    f"&file_type=json&observation_start=2000-01-01"
                    f"&frequency=m&aggregation_method=avg"
                )
                resp = fetch_with_retry(url, timeout=30)
                data = resp.json()
                obs = data.get("observations", [])
                logger.info(f"    {series_id}: {len(obs)} monthly obs")

                for ob in obs:
                    val = pd.to_numeric(ob.get("value", "."), errors="coerce")
                    if pd.isna(val):
                        continue
                    date = pd.Timestamp(ob["date"])
                    date = date.replace(day=1)

                    if scope == "Global":
                        target_countries = T2_COUNTRIES
                    elif scope == "US":
                        target_countries = ["U.S.", "NASDAQ", "US SmallCap"]
                    else:
                        target_countries = [scope]

                    for t2 in target_countries:
                        records.append({
                            "date": date, "country": t2, "value": float(val),
                            "variable": var_name, "source": "fred",
                        })

            except Exception as e:
                logger.warning(f"    {series_id} FAILED: {e}")

        if not records:
            logger.warning("  No FRED records")
            return pd.DataFrame()

        result = pd.DataFrame(records)
        result = result.drop_duplicates(subset=["date", "country", "variable"])
        _log_source_summary("FRED", result)
        return result

    except Exception as e:
        logger.error(f"  FRED FAILED: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE 19: EIA ENERGY  (REST API, needs key)
# ═══════════════════════════════════════════════════════════════════════════

def collect_eia(countries: Dict) -> pd.DataFrame:
    logger.info("[12/12] EIA Energy Data ...")

    api_key = load_api_key("EIA_API_KEY")
    if not api_key:
        logger.warning("  EIA_API_KEY not found — skipping EIA")
        return pd.DataFrame()

    try:
        iso3_rev = _build_reverse_map(countries, "iso3")
        iso_list = sorted(iso3_rev.keys())

        # EIA API v2: petroleum consumption (productId=5, activityId=2)
        records = []
        for iso3 in iso_list:
            try:
                # EIA returns 4 unit variants per year (MTOE/QBTU/TBPD/TJ); the
                # variable is TBPD, so filter to it. length=5000 + desc avoids the
                # old asc/length=100 truncation that capped data at ~2019.
                url = (
                    f"https://api.eia.gov/v2/international/data/?"
                    f"api_key={api_key}&frequency=annual"
                    f"&data[0]=value"
                    f"&facets[activityId][]=2"
                    f"&facets[productId][]=5"
                    f"&facets[unit][]=TBPD"
                    f"&facets[countryRegionId][]={iso3}"
                    f"&start=2000&length=5000"
                    f"&sort[0][column]=period&sort[0][direction]=desc"
                )
                resp = fetch_with_retry(url, timeout=30)
                data = resp.json()
                rows = data.get("response", {}).get("data", [])

                for row in rows:
                    if row.get("unit") != "TBPD":   # belt-and-suspenders vs the facet
                        continue
                    val = pd.to_numeric(row.get("value"), errors="coerce")
                    if pd.isna(val):
                        continue
                    yr = int(row.get("period", 0))
                    if yr < 2000:
                        continue
                    date = pd.Timestamp(year=yr, month=12, day=1)
                    for t2 in iso3_rev[iso3]:
                        records.append({
                            "date": date, "country": t2, "value": float(val),
                            "variable": "EIA_Petroleum_Consumption_TBPD",
                            "source": "eia",
                        })

                if rows:
                    logger.info(f"    {iso3}: {len(rows)} obs")

            except Exception as e:
                logger.warning(f"    {iso3} FAILED: {e}")

        if not records:
            logger.warning("  No EIA records")
            return pd.DataFrame()

        result = pd.DataFrame(records)
        result = result.drop_duplicates(subset=["date", "country", "variable"])
        _log_source_summary("EIA", result)
        return result

    except Exception as e:
        logger.error(f"  EIA FAILED: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE 20: ACLED CONFLICT  (REST API, needs key)
# ═══════════════════════════════════════════════════════════════════════════

def collect_acled(countries: Dict) -> pd.DataFrame:
    logger.info("[—/12] ACLED Armed Conflict (keyed source) ...")

    api_key = load_api_key("ACLED_API_KEY")
    email = load_api_key("ACLED_EMAIL")
    if not api_key or not email:
        logger.warning("  ACLED_API_KEY or ACLED_EMAIL not found — skipping")
        return pd.DataFrame()

    try:
        iso3_rev = _build_reverse_map(countries, "iso3")
        iso_list = sorted(iso3_rev.keys())

        records = []
        for iso3 in iso_list:
            try:
                # ACLED API: get event counts by month
                url = (
                    f"https://api.acleddata.com/acled/read?"
                    f"key={api_key}&email={email}"
                    f"&iso={_iso3_to_numeric(iso3)}"
                    f"&event_date=2000-01-01|{datetime.now().strftime('%Y-%m-%d')}"
                    f"&event_date_where=BETWEEN"
                    f"&fields=event_date|event_type|fatalities"
                    f"&limit=0"
                )
                resp = fetch_with_retry(url, timeout=60)
                data = resp.json()

                if not data.get("success", False):
                    continue

                events = data.get("data", [])
                if not events:
                    continue

                # Aggregate to monthly event counts + fatalities
                monthly: Dict[str, Dict[str, float]] = {}
                for evt in events:
                    dt = evt.get("event_date", "")[:7]
                    if dt not in monthly:
                        monthly[dt] = {"events": 0, "fatalities": 0}
                    monthly[dt]["events"] += 1
                    monthly[dt]["fatalities"] += pd.to_numeric(
                        evt.get("fatalities", 0), errors="coerce") or 0

                for ym, agg in monthly.items():
                    date = _parse_period(ym)
                    if date is None:
                        continue
                    for t2 in iso3_rev[iso3]:
                        records.append({
                            "date": date, "country": t2,
                            "value": float(agg["events"]),
                            "variable": "ACLED_Events", "source": "acled",
                        })
                        records.append({
                            "date": date, "country": t2,
                            "value": float(agg["fatalities"]),
                            "variable": "ACLED_Fatalities", "source": "acled",
                        })

            except Exception as e:
                logger.warning(f"    ACLED {iso3} FAILED: {e}")

        if not records:
            logger.warning("  No ACLED records")
            return pd.DataFrame()

        result = pd.DataFrame(records)
        result = result.drop_duplicates(subset=["date", "country", "variable"])
        _log_source_summary("ACLED", result)
        return result

    except Exception as e:
        logger.error(f"  ACLED FAILED: {e}")
        return pd.DataFrame()


def _iso3_to_numeric(iso3: str) -> int:
    """Convert ISO3 alpha to numeric code for ACLED API."""
    mapping = {
        "AUS": 36, "BRA": 76, "CAN": 124, "CHL": 152, "CHN": 156,
        "DNK": 208, "FRA": 250, "DEU": 276, "HKG": 344, "IND": 356,
        "IDN": 360, "ITA": 380, "JPN": 392, "KOR": 410, "MYS": 458,
        "MEX": 484, "NLD": 528, "PHL": 608, "POL": 616, "SAU": 682,
        "SGP": 702, "ZAF": 710, "ESP": 724, "SWE": 752, "CHE": 756,
        "TWN": 158, "THA": 764, "TUR": 792, "GBR": 826, "USA": 840,
        "VNM": 704,
    }
    return mapping.get(iso3, 0)


# ═══════════════════════════════════════════════════════════════════════════
# SOURCE 21: UN COMTRADE  (REST API, needs key)
# ═══════════════════════════════════════════════════════════════════════════

def collect_comtrade(countries: Dict) -> pd.DataFrame:
    logger.info("[—/12] UN Comtrade Trade Data (keyed source) ...")

    api_key = load_api_key("COMTRADE_API_KEY")
    if not api_key:
        logger.warning("  COMTRADE_API_KEY not found — skipping")
        return pd.DataFrame()

    try:
        iso3_rev = _build_reverse_map(countries, "iso3")
        iso_list = sorted(iso3_rev.keys())

        records = []
        for iso3 in iso_list:
            try:
                numeric = _iso3_to_numeric(iso3)
                if numeric == 0:
                    continue
                # Annual total merchandise trade
                url = (
                    f"https://comtradeapi.un.org/data/v1/get/C/A/HS?"
                    f"reporterCode={numeric}&partnerCode=0"
                    f"&cmdCode=TOTAL&flowCode=M,X"
                    f"&period=2020,2021,2022,2023"
                    f"&subscription-key={api_key}"
                )
                resp = fetch_with_retry(url, timeout=60)
                data = resp.json()
                rows = data.get("data", [])
                logger.info(f"    Comtrade {iso3}: {len(rows)} rows")

                for row in rows:
                    yr = int(row.get("period", 0))
                    val = pd.to_numeric(row.get("primaryValue"), errors="coerce")
                    if pd.isna(val) or yr < 2000:
                        continue
                    flow = row.get("flowDesc", "")
                    var_name = ("Comtrade_Exports" if "Export" in flow
                                else "Comtrade_Imports")
                    date = pd.Timestamp(year=yr, month=12, day=1)
                    for t2 in iso3_rev[iso3]:
                        records.append({
                            "date": date, "country": t2, "value": float(val),
                            "variable": var_name, "source": "comtrade",
                        })

                time.sleep(0.5)  # rate limit

            except Exception as e:
                logger.warning(f"    Comtrade {iso3} FAILED: {e}")

        if not records:
            logger.warning("  No Comtrade records")
            return pd.DataFrame()

        result = pd.DataFrame(records)
        result = result.drop_duplicates(subset=["date", "country", "variable"])
        _log_source_summary("UN Comtrade", result)
        return result

    except Exception as e:
        logger.error(f"  UN Comtrade FAILED: {e}")
        return pd.DataFrame()


# ═══════════════════════════════════════════════════════════════════════════
# QUALITY CHECKS & CATALOG
# ═══════════════════════════════════════════════════════════════════════════

def run_quality_checks(df: pd.DataFrame) -> Dict[str, Any]:
    logger.info("\n" + "=" * 60)
    logger.info("QUALITY CHECKS")
    logger.info("=" * 60)

    checks: Dict[str, Any] = {}

    present = sorted(df["country"].unique())
    missing = sorted(set(T2_COUNTRIES) - set(present))
    checks["present"] = present
    checks["missing"] = missing
    logger.info(f"Countries present: {len(present)}/34")
    if missing:
        logger.warning(f"  Missing: {missing}")

    dups = df.duplicated(subset=["date", "country", "variable"]).sum()
    checks["duplicates"] = dups
    if dups:
        logger.warning(f"Duplicate rows: {dups}")
        df.drop_duplicates(subset=["date", "country", "variable"], inplace=True)
        logger.info(f"  Removed → {len(df)} rows")
    else:
        logger.info("No duplicate rows")

    logger.info("\nDate ranges by variable:")
    for var in sorted(df["variable"].unique()):
        sub = df[df["variable"] == var]
        d_min, d_max = sub["date"].min(), sub["date"].max()
        logger.info(f"  {var:40s} {d_min.strftime('%Y-%m')} → "
                     f"{d_max.strftime('%Y-%m')}  ({sub['country'].nunique()} ctry)")

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

    logger.info("\nCoverage matrix:")
    cov = df.groupby(["country", "source"]).size().unstack(fill_value=0)
    for src in cov.columns:
        n = (cov[src] > 0).sum()
        logger.info(f"  {src:20s}: {n}/34 countries")
    checks["coverage"] = cov.to_dict()

    return checks


def create_variable_catalog(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (src, var), g in df.groupby(["source", "variable"]):
        rows.append({
            "source": src, "variable": var,
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
    logger.info(f"EXTENDED DATA COLLECTION — {mode_label}")
    logger.info("=" * 60)
    logger.info(f"Project directory: {BASE_DIR}")
    if args.force:
        logger.info("--force: bypassing download cache")
    if args.dry_run:
        logger.info("--dry-run: will NOT save output files")

    if args.force:
        for f in RAW_DIR.iterdir():
            if f.is_file() and f.name != ".DS_Store":
                # Only clear extended-source caches (don't touch Program 1 files)
                extended_prefixes = (
                    "oecd_bci", "oecd_cci", "ndgain", "ilostat", "undp_hdi",
                    "ofac_sdn", "faostat",
                )
                if any(f.name.startswith(p) for p in extended_prefixes):
                    f.unlink()
                    logger.info(f"  Cleared cache: {f.name}")

    countries = load_country_mapping()

    existing_panel = load_existing_panel()

    # ── Collectors: no-key first, then keyed ─────────────────────────
    collectors = [
        ("BIS Policy Rates",  collect_bis_policy_rates),
        ("BIS Debt Service",   collect_bis_debt_service),
        ("OECD BCI",           collect_oecd_bci),
        ("OECD CCI",           collect_oecd_cci),
        ("ECB FX",             collect_ecb_fx),
        ("ND-GAIN",            collect_ndgain),
        ("ILOSTAT",            collect_ilostat),
        ("UNDP HDI",           collect_undp_hdi),
        ("OFAC Sanctions",     collect_ofac),
        ("FAOSTAT",            collect_faostat),
        ("FRED",               collect_fred),
        ("EIA",                collect_eia),
        # ACLED and Comtrade are slower — put last
        # ("ACLED",              collect_acled),
        # ("UN Comtrade",        collect_comtrade),
    ]

    fresh_frames: Dict[str, pd.DataFrame] = {}
    status: Dict[str, str] = {}

    # Sequential execution — parallelizing the 12 collectors causes ECB / BIS /
    # OECD / FRED rate-limit collisions (each collector internally iterates many
    # sub-requests against the same host) and makes total runtime *worse*.
    # See git history for the parallel attempt; ECB FX in particular hangs when
    # other threads are concurrently hammering shared rate-limit budgets.
    for name, fn in collectors:
        try:
            df = fn(countries)
            if df is not None and not df.empty:
                fresh_frames[name] = df
                status[name] = "SUCCESS"
            else:
                fresh_frames[name] = pd.DataFrame()
                status[name] = "NO DATA"
                logger.warning(f"  {name}: returned no data")
        except Exception as e:
            fresh_frames[name] = pd.DataFrame()
            status[name] = f"FAILED: {e}"
            logger.error(f"  {name}: FAILED — {e}")

    # ── Merge ────────────────────────────────────────────────────────
    logger.info("\n" + "-" * 60)
    logger.info("MERGING fresh data with existing panel ...")
    panel = merge_panels(existing_panel, fresh_frames, status)

    if panel.empty:
        logger.error("Panel is empty after merge — aborting.")
        return

    logger.info(f"Merged panel: {len(panel):,} rows")

    run_quality_checks(panel)
    panel = panel.drop_duplicates(subset=["date", "country", "variable"])

    catalog = create_variable_catalog(panel)

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

    elapsed = time.time() - t0
    if not args.dry_run:
        record_run(status, panel, elapsed)

    if existing_panel is not None:
        old_rows = len(existing_panel)
        new_rows = len(panel)
        delta = new_rows - old_rows
        sign = "+" if delta >= 0 else ""
        logger.info(f"\nDelta vs. previous: {old_rows:,} → {new_rows:,} "
                    f"({sign}{delta:,} rows)")

    # ── Summary ──────────────────────────────────────────────────────
    logger.info("\n" + "=" * 60)
    logger.info("COLLECTION SUMMARY")
    logger.info("=" * 60)
    for name, st in status.items():
        marker = "OK" if st == "SUCCESS" else "WARN"
        logger.info(f"  [{marker:4s}] {name:25s} {st}")

    n_sources_ok = sum(1 for s in status.values() if s == "SUCCESS")
    n_total = len(collectors)
    n_vars = panel["variable"].nunique()
    n_ctry = panel["country"].nunique()
    logger.info(f"\nSources OK    : {n_sources_ok}/{n_total}")
    logger.info(f"Variables     : {n_vars}")
    logger.info(f"Countries     : {n_ctry}/34")
    logger.info(f"Total rows    : {len(panel):,}")
    logger.info(f"Date range    : {panel['date'].min().strftime('%Y-%m')} → "
                f"{panel['date'].max().strftime('%Y-%m')}")
    logger.info(f"Elapsed       : {elapsed:.1f}s")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
