#!/usr/bin/env python3
"""
Collect World Bank Commodity Markets Pink Sheet monthly prices for ASADO.

The official World Bank workbook is the canonical source. This collector keeps
the full commodity axis in dedicated tables, then broadcasts only the PRD V1
projection set into ASADO's factor-panel shape as explanatory global context.
It does not write any optimizer return/output tables.

INPUT FILES:
- https://...CMO-Historical-Data-Monthly.xlsx  (downloaded to
    Data/raw/wb_commodity_prices/CMO-Historical-Data-Monthly_<ts>.xlsx)

OUTPUT FILES (all under Data/processed/):
- wb_commodity_prices.parquet, wb_commodity_indices.parquet,
  wb_commodity_meta.parquet, wb_commodity_features.parquet,
  wb_commodity_factor_panel.parquet, wb_commodity_manifest.json,
  wb_commodity_variable_catalog.csv

VERSION: 1.1
LAST UPDATED: 2026-06-08

FORMAT NOTE (2026-06): The World Bank removed the short-code header row (the row
that held CRUDE_BRENT / GOLD / iOVERALL / ...) from the "Monthly Prices" and
"Monthly Indices" sheets, leaving only the display-name row. That silently broke
the old fixed-row parser (it read the first DATA row as codes -> series_code
became numeric junk like '1.63', so the factor projection matched 0 series and
wb_commodity_factor_panel collapsed to 0 rows). The parser is now
content-anchored: data-start is the first YYYYMmm row, the code row is detected
only if its cells are real codes, and when absent the canonical code is recovered
from the (stable) display name via PRICE_NAME_TO_CODE / INDEX_NAME_TO_CODE. This
is backward-compatible with the pre-June files that still carry the code row.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Data"
RAW_DIR = DATA_DIR / "raw" / "wb_commodity_prices"
PROCESSED_DIR = DATA_DIR / "processed"
BACKUP_DIR = DATA_DIR / "backups"
CONFIG_PATH = BASE_DIR / "config" / "country_mapping.json"

WORLD_BANK_COMMODITY_PAGE = "https://www.worldbank.org/en/research/commodity-markets"
DEFAULT_WORKBOOK_URL = (
    "https://thedocs.worldbank.org/en/doc/"
    "74e8be41ceb20fa0da750cda2f6b9e4e-0050012026/related/"
    "CMO-Historical-Data-Monthly.xlsx"
)
SOURCE_URL_ENV = "WB_COMMODITY_MONTHLY_XLS_URL"
CACHE_HOURS = 24

PRICES_PQ = PROCESSED_DIR / "wb_commodity_prices.parquet"
INDICES_PQ = PROCESSED_DIR / "wb_commodity_indices.parquet"
META_PQ = PROCESSED_DIR / "wb_commodity_meta.parquet"
FEATURES_PQ = PROCESSED_DIR / "wb_commodity_features.parquet"
FACTOR_PANEL_PQ = PROCESSED_DIR / "wb_commodity_factor_panel.parquet"
MANIFEST_PATH = PROCESSED_DIR / "wb_commodity_manifest.json"
CATALOG_CSV = PROCESSED_DIR / "wb_commodity_variable_catalog.csv"

OUTPUT_PATHS = [
    PRICES_PQ,
    INDICES_PQ,
    META_PQ,
    FEATURES_PQ,
    # FACTOR_PANEL_PQ deprecated: commodities are global (commodity_panel), not
    # broadcast/tiled across countries. The country-tiled factor panel is no longer written.
    MANIFEST_PATH,
    CATALOG_CSV,
]

FEATURE_SUFFIX = {
    "level": "LEVEL",
    "mom_pct": "MOM",
    "yoy_pct": "YOY",
    "ret_3m_pct": "RET_3M",
    "ret_12m_pct": "RET_12M",
    "vol_12m": "VOL_12M",
    "z_36m": "Z_36M",
}

INDEX_NAMES = {
    "iOVERALL": ("Total Index", "aggregate"),
    "iENERGY": ("Energy", "energy"),
    "iNONFUEL": ("Non-energy", "aggregate"),
    "iAGRICULTURE": ("Agriculture", "agriculture"),
    "iBEVERAGES": ("Beverages", "beverages"),
    "iFOOD": ("Food", "food"),
    "iFATS_OILS": ("Oils & Meals", "oils_meals"),
    "iGRAINS": ("Grains", "grains"),
    "iOTHERFOOD": ("Other Food", "food"),
    "iRAW_MATERIAL": ("Raw Materials", "raw_materials"),
    "iTIMBER": ("Timber", "timber"),
    "iOTHERRAWMAT": ("Other Raw Materials", "raw_materials"),
    "iFERTILIZERS": ("Fertilizers", "fertilizers"),
    "iMETMIN": ("Metals & Minerals", "metals_minerals"),
    "iBASEMET": ("Base Metals", "base_metals"),
    "iPRECIOUSMET": ("Precious Metals", "precious_metals"),
}

PROJECTED_PRICE_CODES = {
    "CRUDE_PETRO", "CRUDE_BRENT", "CRUDE_DUBAI", "CRUDE_WTI",
    "NGAS_US", "NGAS_EUR", "NGAS_JP", "iNATGAS",
    "COAL_AUS", "COAL_SAFRICA",
    "GOLD", "SILVER", "PLATINUM",
    "COPPER", "ALUMINUM", "IRON_ORE", "NICKEL", "Zinc", "LEAD", "Tin",
    "DAP", "UREA_EE_BULK", "PHOSROCK", "POTASH", "TSP",
    "MAIZE", "WHEAT_US_HRW", "WHEAT_US_SRW", "RICE_05", "BARLEY",
    "COCOA", "COFFEE_ARABIC", "COFFEE_ROBUS", "SUGAR_WLD",
    "PALM_OIL", "SOYBEANS", "SOYBEAN_OIL",
}
PROJECTED_INDEX_CODES = set(INDEX_NAMES)
PROJECTED_SERIES_CODES = PROJECTED_PRICE_CODES | PROJECTED_INDEX_CODES

# ── Display-name → series_code recovery maps ──────────────────────────────────
# The World Bank "CMO-Historical-Data-Monthly.xlsx" format changed in June 2026:
# they REMOVED the short-code row (the row that used to hold CRUDE_BRENT, GOLD,
# iOVERALL, ...) from both the "Monthly Prices" and "Monthly Indices" sheets,
# leaving only the human-readable display-name row. The codes the factor
# projection depends on therefore no longer exist in the source file. These maps
# recover the canonical code from the (stable) display name. They were extracted
# from the last workbook that still carried codes (2026-05-16) and verified to
# resolve every column in the new (2026-06) format. If WB ever restores the code
# row, the parser uses it directly and ignores these maps.
PRICE_NAME_TO_CODE = {
    "Crude oil, average": "CRUDE_PETRO",
    "Crude oil, Brent": "CRUDE_BRENT",
    "Crude oil, Dubai": "CRUDE_DUBAI",
    "Crude oil, WTI": "CRUDE_WTI",
    "Coal, Australian": "COAL_AUS",
    "Coal, South African": "COAL_SAFRICA",
    "Natural gas, US": "NGAS_US",
    "Natural gas, Europe": "NGAS_EUR",
    "Liquefied natural gas, Japan": "NGAS_JP",
    "Natural gas index": "iNATGAS",
    "Cocoa": "COCOA",
    "Coffee, Arabica": "COFFEE_ARABIC",
    "Coffee, Robusta": "COFFEE_ROBUS",
    "Tea, avg 3 auctions": "TEA_AVG",
    "Tea, Colombo": "TEA_COLOMBO",
    "Tea, Kolkata": "TEA_KOLKATA",
    "Tea, Mombasa": "TEA_MOMBASA",
    "Coconut oil": "COCONUT_OIL",
    "Groundnuts": "GRNUT",
    "Fish meal": "FISH_MEAL",
    "Groundnut oil": "GRNUT_OIL",
    "Palm oil": "PALM_OIL",
    "Palm kernel oil": "PLMKRNL_OIL",
    "Soybeans": "SOYBEANS",
    "Soybean oil": "SOYBEAN_OIL",
    "Soybean meal": "SOYBEAN_MEAL",
    "Rapeseed oil": "RAPESEED_OIL",
    "Sunflower oil": "SUNFLOWER_OIL",
    "Barley": "BARLEY",
    "Maize": "MAIZE",
    "Sorghum": "SORGHUM",
    "Rice, Thai 5%": "RICE_05",
    "Rice, Thai 25%": "RICE_25",
    "Rice, Thai A.1": "RICE_A1",
    "Rice, Viet Namese 5%": "RICE_05_VNM",
    "Wheat, US SRW": "WHEAT_US_SRW",
    "Wheat, US HRW": "WHEAT_US_HRW",
    "Banana, Europe": "BANANA_EU",
    "Banana, US": "BANANA_US",
    "Orange": "ORANGE",
    "Beef": "BEEF",
    "Chicken": "CHICKEN",
    "Lamb": "LAMB",
    "Shrimps, Mexican": "SHRIMP_MEX",
    "Sugar, EU": "SUGAR_EU",
    "Sugar, US": "SUGAR_US",
    "Sugar, world": "SUGAR_WLD",
    "Tobacco, US import u.v.": "TOBAC_US",
    "Logs, Cameroon": "LOGS_CMR",
    "Logs, Malaysian": "LOGS_MYS",
    "Sawnwood, Cameroon": "SAWNWD_CMR",
    "Sawnwood, Malaysian": "SAWNWD_MYS",
    "Plywood": "PLYWOOD",
    "Cotton, A Index": "COTTON_A_INDX",
    "Rubber, TSR20": "RUBBER_TSR20",
    "Rubber, RSS3": "RUBBER1_MYSG",
    "Phosphate rock": "PHOSROCK",
    "DAP": "DAP",
    "TSP": "TSP",
    "Urea": "UREA_EE_BULK",
    "Potassium chloride": "POTASH",
    "Aluminum": "ALUMINUM",
    "Iron ore, cfr spot": "IRON_ORE",
    "Copper": "COPPER",
    "Lead": "LEAD",
    "Tin": "Tin",
    "Nickel": "NICKEL",
    "Zinc": "Zinc",
    "Gold": "GOLD",
    "Platinum": "PLATINUM",
    "Silver": "SILVER",
}

# Index display-name → code: inverted INDEX_NAMES plus the two workbook spellings
# that differ from our canonical display strings ("Other Raw Mat.", "Base Metals
# (ex. iron ore)"), verified against the 2026-05-16 code row.
INDEX_NAME_TO_CODE = {name: code for code, (name, _cat) in INDEX_NAMES.items()}
INDEX_NAME_TO_CODE.update({
    "Other Raw Mat.": "iOTHERRAWMAT",
    "Base Metals (ex. iron ore)": "iBASEMET",
})


def _norm_name(value: Any) -> str:
    """Normalize a workbook header cell for name matching: drop footnote
    asterisks, collapse whitespace, strip."""
    return re.sub(r"\s+", " ", re.sub(r"\*+", "", str(value))).strip()


# Case-insensitive lookups built once at import.
_PRICE_LOOKUP = {_norm_name(k).lower(): v for k, v in PRICE_NAME_TO_CODE.items()}
_INDEX_LOOKUP = {_norm_name(k).lower(): v for k, v in INDEX_NAME_TO_CODE.items()}

_PERIOD_RE = re.compile(r"\d{4}M\d{1,2}")


def _find_data_start(raw: pd.DataFrame, max_scan: int = 40) -> int:
    """Row index of the first data row, detected as the first row whose column 0
    is a World-Bank monthly period token (YYYYMmm). Format-agnostic — survives
    the removal/insertion of header rows."""
    for r in range(min(max_scan, len(raw))):
        if _PERIOD_RE.fullmatch(str(raw.iloc[r, 0]).strip()):
            return r
    raise ValueError("Could not locate data-start row (no YYYYMmm in column 0)")


def _find_code_row(raw: pd.DataFrame, data_start: int, known_codes: set[str]) -> int | None:
    """Return the header-band row that actually holds series CODES (cells that
    are members of the known code set), or None if the source no longer carries
    a code row (the post-June-2026 format). This is what makes single-word
    display names like 'Energy' immune to being misread as codes."""
    for r in range(data_start):
        vals = [str(raw.iloc[r, c]).strip() for c in range(1, raw.shape[1])]
        vals = [v for v in vals if v and v.lower() != "nan"]
        if not vals:
            continue
        hits = sum(1 for v in vals if v in known_codes)
        if hits >= max(3, len(vals) // 2):
            return r
    return None


def _find_units_row(raw: pd.DataFrame, data_start: int) -> int | None:
    """Header row holding measurement units — cells like '($/bbl)', '($/mt)'."""
    best, best_hits = None, 0
    for r in range(data_start):
        hits = sum(
            1 for c in range(1, raw.shape[1])
            if str(raw.iloc[r, c]).strip().startswith("(")
        )
        if hits > best_hits:
            best, best_hits = r, hits
    return best if best_hits >= 3 else None


def _find_names_row(raw: pd.DataFrame, data_start: int,
                    units_row: int | None, code_row: int | None) -> int | None:
    """Header row holding the descriptive commodity names — the row (excluding
    the units/code rows and the title block) with the most alphabetic cells in
    columns 1+."""
    best, best_hits = None, 0
    for r in range(data_start):
        if r in (units_row, code_row):
            continue
        hits = 0
        for c in range(1, raw.shape[1]):
            v = _norm_name(raw.iloc[r, c])
            if v and v.lower() != "nan" and not v.startswith("(") and re.search(r"[A-Za-z]", v):
                hits += 1
        if hits > best_hits:
            best, best_hits = r, hits
    return best


def _resolve_code(name: str, code_cell: Any, lookup: dict[str, str]) -> str | None:
    """Resolve a series code: prefer an explicit code cell (old format); else map
    the display name via `lookup` (new format); else slug the name so the series
    is still preserved (it just won't be in the projected/broadcast set)."""
    if code_cell is not None:
        cc = _clean_code(code_cell)
        if cc and cc.lower() != "nan":
            return cc
    key = _norm_name(name).lower()
    if key in lookup:
        return lookup[key]
    slug = re.sub(r"[^A-Za-z0-9]+", "_", _norm_name(name)).strip("_").upper()
    return slug or None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)


def _session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=3,
        connect=3,
        read=3,
        backoff_factor=0.75,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {"User-Agent": "ASADO commodity collector/1.0 (+https://github.com/ArjunDivecha/ASADO)"}
    )
    return session


def _ensure_dirs() -> None:
    for path in (RAW_DIR, PROCESSED_DIR, BACKUP_DIR):
        path.mkdir(parents=True, exist_ok=True)


def resolve_workbook_url(explicit_url: str | None = None) -> str:
    if explicit_url:
        return explicit_url
    env_url = os.environ.get(SOURCE_URL_ENV)
    if env_url:
        return env_url

    try:
        response = _session().get(WORLD_BANK_COMMODITY_PAGE, timeout=30)
        response.raise_for_status()
        matches = re.findall(
            r"https://[^\"'> ]+CMO-Historical-Data-Monthly\.xlsx",
            response.text,
            flags=re.IGNORECASE,
        )
        if matches:
            return matches[0]
    except Exception as exc:
        log.warning("Could not resolve latest workbook URL from World Bank page: %s", exc)

    return DEFAULT_WORKBOOK_URL


def latest_cached_workbook() -> Path | None:
    candidates = sorted(RAW_DIR.glob("CMO-Historical-Data-Monthly_*.xlsx"))
    return candidates[-1] if candidates else None


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download_workbook(url: str, force: bool = False) -> Path:
    cached = latest_cached_workbook()
    if cached and not force:
        age_hours = (datetime.now().timestamp() - cached.stat().st_mtime) / 3600
        if age_hours <= CACHE_HOURS:
            log.info("Using cached World Bank workbook: %s", cached)
            return cached

    target = RAW_DIR / f"CMO-Historical-Data-Monthly_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    try:
        log.info("Downloading World Bank commodity workbook: %s", url)
        response = _session().get(url, timeout=90)
        response.raise_for_status()
        target.write_bytes(response.content)
        log.info("Downloaded %s (%.1f KB, sha256=%s)", target.name, target.stat().st_size / 1024, _sha256(target)[:12])
        return target
    except Exception as exc:
        if cached:
            log.warning("Download failed (%s); falling back to cached workbook: %s", exc, cached)
            return cached
        raise


def _parse_period(value: Any) -> pd.Timestamp | pd.NaT:
    text = str(value).strip()
    match = re.fullmatch(r"(\d{4})M(\d{1,2})", text)
    if match:
        return pd.Timestamp(year=int(match.group(1)), month=int(match.group(2)), day=1)
    return pd.to_datetime(value, errors="coerce")


def _parse_source_update_label(raw: pd.DataFrame) -> tuple[str | None, str | None]:
    label = None
    parsed_date = None
    for value in raw.iloc[:8, 0].dropna().astype(str):
        if "Updated on" in value:
            label = value.strip()
            try:
                parsed_date = pd.to_datetime(value.replace("Updated on", "").strip()).date().isoformat()
            except Exception:
                parsed_date = None
            break
    return label, parsed_date


def _clean_code(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).strip())


def _category_for_code(code: str) -> str:
    upper = code.upper()
    if upper.startswith("CRUDE") or upper.startswith("COAL") or upper.startswith("NGAS") or upper == "INATGAS":
        return "energy"
    if upper in {"COCOA", "COFFEE_ARABIC", "COFFEE_ROBUS"} or upper.startswith("TEA"):
        return "beverages"
    if upper in {
        "COCONUT_OIL", "GRNUT", "FISH_MEAL", "GRNUT_OIL", "PALM_OIL",
        "PLMKRNL_OIL", "SOYBEANS", "SOYBEAN_OIL", "SOYBEAN_MEAL",
        "RAPESEED_OIL", "SUNFLOWER_OIL",
    }:
        return "oils_meals"
    if upper in {"BARLEY", "MAIZE", "SORGHUM"} or upper.startswith("RICE") or upper.startswith("WHEAT"):
        return "grains"
    if upper.startswith("BANANA") or upper in {
        "ORANGE", "BEEF", "CHICKEN", "LAMB", "SHRIMP_MEX", "SUGAR_EU",
        "SUGAR_US", "SUGAR_WLD",
    }:
        return "food"
    if upper.startswith("LOGS") or upper.startswith("SAWNWD") or upper == "PLYWOOD":
        return "timber"
    if upper in {"TOBAC_US", "COTTON_A_INDX", "RUBBER_TSR20", "RUBBER1_MYSG"}:
        return "raw_materials"
    if upper in {"PHOSROCK", "DAP", "TSP", "UREA_EE_BULK", "POTASH"}:
        return "fertilizers"
    if upper in {"ALUMINUM", "IRON_ORE", "COPPER", "LEAD", "TIN", "NICKEL", "ZINC"}:
        return "metals_minerals"
    if upper in {"GOLD", "PLATINUM", "SILVER"}:
        return "precious_metals"
    return "other"


def parse_prices(path: Path, source_url: str) -> tuple[pd.DataFrame, str | None, str | None]:
    raw = pd.read_excel(path, sheet_name="Monthly Prices", header=None, engine="openpyxl")
    update_label, source_file_date = _parse_source_update_label(raw)

    # Content-anchored header detection (survives the June-2026 removal of the
    # code row). Data starts at the first YYYYMmm row; names/units rows and the
    # optional code row are found by content, not fixed offsets.
    data_start = _find_data_start(raw)
    known = set(PRICE_NAME_TO_CODE.values())
    code_row = _find_code_row(raw, data_start, known)
    units_row = _find_units_row(raw, data_start)
    names_row = _find_names_row(raw, data_start, units_row, code_row)
    if names_row is None:
        raise ValueError("Could not locate the commodity-name row in 'Monthly Prices'")

    names = raw.iloc[names_row, 1:]
    units = raw.iloc[units_row, 1:] if units_row is not None else None
    codes = raw.iloc[code_row, 1:] if code_row is not None else None
    data = raw.iloc[data_start:, :].copy()
    data = data[data.iloc[:, 0].notna()]

    frames: list[pd.DataFrame] = []
    slugged: list[str] = []
    for col_idx in names.index:
        name = _clean_code(names.get(col_idx))
        if not name or name.lower() == "nan":
            continue
        code = _resolve_code(name, codes.get(col_idx) if codes is not None else None, _PRICE_LOOKUP)
        if not code:
            continue
        if code_row is None and _norm_name(name).lower() not in _PRICE_LOOKUP:
            slugged.append(name)
        frame = pd.DataFrame(
            {
                "date": data.iloc[:, 0].map(_parse_period),
                "commodity_code": code,
                "commodity_name": name,
                "unit": _clean_code(units.get(col_idx, "")) if units is not None else "",
                "nominal_price_usd": pd.to_numeric(data[col_idx], errors="coerce"),
            }
        )
        frame = frame.dropna(subset=["date", "nominal_price_usd"])
        frames.append(frame)

    if not frames:
        raise ValueError("Monthly Prices: parsed 0 series — source layout may have changed again")
    if slugged:
        log.warning("Monthly Prices: %d column(s) had no code mapping (slugged): %s",
                    len(slugged), slugged[:8])
    log.info("Monthly Prices parsed: data_start=%d names_row=%s units_row=%s code_row=%s",
             data_start, names_row, units_row, code_row)
    prices = pd.concat(frames, ignore_index=True)
    prices["date"] = pd.to_datetime(prices["date"]).dt.date
    prices["category"] = prices["commodity_code"].map(_category_for_code)
    prices["source_sheet"] = "Monthly Prices"
    prices["source_file_date"] = source_file_date
    prices["source_url"] = source_url
    prices["last_loaded_at"] = datetime.now(timezone.utc).isoformat()
    return prices, update_label, source_file_date


def parse_indices(path: Path, source_url: str, source_file_date: str | None) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name="Monthly Indices", header=None, engine="openpyxl")

    # Index display names are spread across several merged/wrapped header rows, so
    # per-column we take the first non-NaN text cell in the header band. The code
    # row (post-June-2026: absent) is detected by content and preferred when present.
    data_start = _find_data_start(raw)
    code_row = _find_code_row(raw, data_start, set(INDEX_NAMES))
    codes = raw.iloc[code_row, 1:] if code_row is not None else None
    data = raw.iloc[data_start:, :].copy()
    data = data[data.iloc[:, 0].notna()]

    frames: list[pd.DataFrame] = []
    slugged: list[str] = []
    for col_idx in range(1, raw.shape[1]):
        name = None
        for r in range(data_start):
            if code_row is not None and r == code_row:
                continue
            v = _norm_name(raw.iloc[r, col_idx])
            if v and v.lower() != "nan":
                name = v
                break
        code_cell = codes.get(col_idx) if codes is not None else None
        if name is None and (code_cell is None or str(code_cell).strip().lower() == "nan"):
            continue
        code = _resolve_code(name or "", code_cell, _INDEX_LOOKUP)
        if not code:
            continue
        display_name, category = INDEX_NAMES.get(code, (name or code, "aggregate"))
        if code_row is None and code not in INDEX_NAMES:
            slugged.append(name or code)
        frame = pd.DataFrame(
            {
                "date": data.iloc[:, 0].map(_parse_period),
                "index_code": code,
                "index_name": display_name,
                "nominal_index_2010_100": pd.to_numeric(data[col_idx], errors="coerce"),
                "category": category,
            }
        )
        frame = frame.dropna(subset=["date", "nominal_index_2010_100"])
        frames.append(frame)

    if not frames:
        raise ValueError("Monthly Indices: parsed 0 series — source layout may have changed again")
    if slugged:
        log.warning("Monthly Indices: %d column(s) unmapped (slugged): %s",
                    len(slugged), slugged[:8])
    log.info("Monthly Indices parsed: data_start=%d code_row=%s", data_start, code_row)
    indices = pd.concat(frames, ignore_index=True)
    indices["date"] = pd.to_datetime(indices["date"]).dt.date
    indices["source_sheet"] = "Monthly Indices"
    indices["source_file_date"] = source_file_date
    indices["source_url"] = source_url
    indices["last_loaded_at"] = datetime.now(timezone.utc).isoformat()
    return indices


def build_meta(prices: pd.DataFrame, indices: pd.DataFrame) -> pd.DataFrame:
    price_meta = (
        prices[["commodity_code", "commodity_name", "category", "unit"]]
        .drop_duplicates("commodity_code")
        .rename(columns={"commodity_code": "series_code", "commodity_name": "display_name"})
    )
    price_meta["series_type"] = "price"

    index_meta = (
        indices[["index_code", "index_name", "category"]]
        .drop_duplicates("index_code")
        .rename(columns={"index_code": "series_code", "index_name": "display_name"})
    )
    index_meta["series_type"] = "index"
    index_meta["unit"] = "2010=100"

    meta = pd.concat([price_meta, index_meta], ignore_index=True)
    meta["source_description"] = np.where(
        meta["series_type"].eq("price"),
        "World Bank Pink Sheet monthly nominal U.S. dollar commodity price",
        "World Bank Pink Sheet monthly nominal U.S. dollar commodity price index",
    )
    meta["canonical_source"] = "World Bank Commodity Markets Pink Sheet"
    meta["import_status"] = "active"
    meta["is_projected_to_factor_panel"] = meta["series_code"].isin(PROJECTED_SERIES_CODES)
    return meta[
        [
            "series_code",
            "series_type",
            "display_name",
            "category",
            "unit",
            "source_description",
            "canonical_source",
            "import_status",
            "is_projected_to_factor_panel",
        ]
    ].sort_values(["series_type", "series_code"])


def _feature_frame(base: pd.DataFrame, value_column: str, code_column: str, type_name: str) -> pd.DataFrame:
    records: list[pd.DataFrame] = []
    source_cols = ["date", code_column, "display_name", "category", "unit", value_column]
    working = base[source_cols].copy().sort_values([code_column, "date"])
    working = working.rename(columns={code_column: "series_code", value_column: "level"})

    for series_code, group in working.groupby("series_code", sort=False):
        group = group.sort_values("date").copy()
        level = pd.to_numeric(group["level"], errors="coerce")
        mom = level.pct_change(1) * 100.0
        features = pd.DataFrame(
            {
                "date": group["date"],
                "series_code": series_code,
                "series_type": type_name,
                "display_name": group["display_name"],
                "category": group["category"],
                "unit": group["unit"],
                "level": level,
                "mom_pct": mom,
                "yoy_pct": level.pct_change(12) * 100.0,
                "ret_3m_pct": level.pct_change(3) * 100.0,
                "ret_12m_pct": level.pct_change(12) * 100.0,
                "vol_12m": mom.rolling(12, min_periods=6).std(ddof=0),
                "z_36m": (level - level.rolling(36, min_periods=12).mean())
                / level.rolling(36, min_periods=12).std(ddof=0),
            }
        )
        long = features.melt(
            id_vars=["date", "series_code", "series_type", "display_name", "category", "unit"],
            value_vars=list(FEATURE_SUFFIX),
            var_name="feature",
            value_name="value",
        )
        records.append(long.dropna(subset=["value"]))

    out = pd.concat(records, ignore_index=True)
    out["source"] = "wb_commodity"
    out["source_frequency"] = "monthly"
    out["last_loaded_at"] = datetime.now(timezone.utc).isoformat()
    return out


def build_features(prices: pd.DataFrame, indices: pd.DataFrame) -> pd.DataFrame:
    price_base = prices.rename(
        columns={
            "commodity_code": "series_code",
            "commodity_name": "display_name",
        }
    )
    price_features = _feature_frame(
        price_base,
        value_column="nominal_price_usd",
        code_column="series_code",
        type_name="price",
    )

    index_base = indices.rename(
        columns={
            "index_code": "series_code",
            "index_name": "display_name",
            "nominal_index_2010_100": "level_value",
        }
    )
    index_base["unit"] = "2010=100"
    index_features = _feature_frame(
        index_base,
        value_column="level_value",
        code_column="series_code",
        type_name="index",
    )
    return pd.concat([price_features, index_features], ignore_index=True)


def _tracked_countries() -> list[str]:
    with open(CONFIG_PATH, encoding="utf-8") as handle:
        return list(json.load(handle)["countries"].keys())


def _variable_name(series_code: str, feature: str) -> str:
    code_slug = re.sub(r"[^A-Za-z0-9]+", "_", series_code).strip("_").upper()
    return f"WB_CMDTY_{code_slug}_{FEATURE_SUFFIX[feature]}"


def build_factor_panel(features: pd.DataFrame) -> pd.DataFrame:
    countries = pd.DataFrame({"country": _tracked_countries()})
    projected = features[features["series_code"].isin(PROJECTED_SERIES_CODES)].copy()
    projected["variable"] = [
        _variable_name(code, feature)
        for code, feature in zip(projected["series_code"], projected["feature"], strict=False)
    ]
    projected["source"] = "wb_commodity"
    projected["is_global_broadcast"] = True

    factor = projected[["date", "value", "variable", "source", "series_code", "feature", "is_global_broadcast"]].merge(
        countries,
        how="cross",
    )
    return factor[
        ["date", "country", "value", "variable", "source", "series_code", "feature", "is_global_broadcast"]
    ].sort_values(["date", "variable", "country"])


def backup_outputs() -> None:
    existing = [path for path in OUTPUT_PATHS if path.exists()]
    if not existing:
        return
    stamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    backup_dir = BACKUP_DIR / f"wb_commodity_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    for path in existing:
        shutil.copy2(path, backup_dir / path.name)
    log.info("Backed up existing commodity outputs to %s", backup_dir)


def write_outputs(
    prices: pd.DataFrame,
    indices: pd.DataFrame,
    meta: pd.DataFrame,
    features: pd.DataFrame,
    factor_panel: pd.DataFrame,
    workbook_path: Path,
    source_url: str,
    update_label: str | None,
    source_file_date: str | None,
    dry_run: bool = False,
) -> dict[str, Any]:
    manifest = {
        "canonical_source": "World Bank Commodity Markets Pink Sheet",
        "source_page": WORLD_BANK_COMMODITY_PAGE,
        "source_url": source_url,
        "source_updated_label": update_label,
        "source_file_date": source_file_date,
        "workbook_path": str(workbook_path),
        "workbook_sha256": _sha256(workbook_path),
        "price_series_count": int(prices["commodity_code"].nunique()),
        "index_series_count": int(indices["index_code"].nunique()),
        "feature_series_count": int(features["series_code"].nunique()),
        "projected_series_count": int(factor_panel["series_code"].nunique()),
        "factor_panel_variable_count": int(factor_panel["variable"].nunique()),
        "factor_panel_row_count": int(len(factor_panel)),
        "min_date": str(min(prices["date"].min(), indices["date"].min())),
        "max_date": str(max(prices["date"].max(), indices["date"].max())),
        "loaded_at": datetime.now(timezone.utc).isoformat(),
        "source_role": "explanatory_global_broadcast_input",
        "returns_guardrail": (
            "World Bank commodity data is explanatory context only. "
            "ASADO country and factor returns remain the outcome source of truth."
        ),
    }

    catalog = (
        factor_panel[["variable", "series_code", "feature"]]
        .drop_duplicates()
        .merge(meta[["series_code", "series_type", "display_name", "category", "unit"]], on="series_code", how="left")
        .assign(source="wb_commodity", native_frequency="monthly", is_global_broadcast=True)
        .sort_values("variable")
    )

    if dry_run:
        return manifest

    backup_outputs()
    prices.to_parquet(PRICES_PQ, index=False)
    indices.to_parquet(INDICES_PQ, index=False)
    meta.to_parquet(META_PQ, index=False)
    features.to_parquet(FEATURES_PQ, index=False)
    # Commodities are GLOBAL series — the country-tiled broadcast (factor_panel) is
    # no longer persisted; setup_duckdb exposes them via the global commodity_panel view.
    catalog.to_csv(CATALOG_CSV, index=False)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def collect(args: argparse.Namespace) -> dict[str, Any]:
    _ensure_dirs()
    source_url = resolve_workbook_url(args.url)
    workbook = download_workbook(source_url, force=args.force)
    prices, update_label, source_file_date = parse_prices(workbook, source_url)
    indices = parse_indices(workbook, source_url, source_file_date)
    meta = build_meta(prices, indices)
    features = build_features(prices, indices)
    factor_panel = build_factor_panel(features)
    manifest = write_outputs(
        prices=prices,
        indices=indices,
        meta=meta,
        features=features,
        factor_panel=factor_panel,
        workbook_path=workbook,
        source_url=source_url,
        update_label=update_label,
        source_file_date=source_file_date,
        dry_run=args.dry_run,
    )
    log.info(
        "World Bank commodity collection: %s price series, %s index series, %s projected variables, latest=%s",
        manifest["price_series_count"],
        manifest["index_series_count"],
        manifest["factor_panel_variable_count"],
        manifest["max_date"],
    )
    return manifest


def check_outputs(allow_stale: bool = False) -> int:
    missing = [path for path in [PRICES_PQ, INDICES_PQ, FEATURES_PQ, MANIFEST_PATH] if not path.exists()]
    if missing:
        for path in missing:
            log.error("Missing commodity output: %s", path)
        return 1

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    prices = pd.read_parquet(PRICES_PQ)
    indices = pd.read_parquet(INDICES_PQ)
    features = pd.read_parquet(FEATURES_PQ, columns=["series_code", "feature"])

    latest = pd.to_datetime(max(prices["date"].max(), indices["date"].max())).date()
    age_days = (datetime.now().date() - latest).days
    stale = age_days > 95
    status = "stale" if stale else "ok"
    log.info(
        "wb_commodity_prices: %d series, latest=%s, age_days=%d, status=%s",
        prices["commodity_code"].nunique(),
        latest,
        age_days,
        status,
    )
    log.info(
        "wb_commodity_indices: %d series; global commodity features: %d series x %d feature types (commodity_panel)",
        indices["index_code"].nunique(),
        features["series_code"].nunique(),
        features["feature"].nunique(),
    )
    log.info("source_updated_label: %s", manifest.get("source_updated_label"))
    if stale and not allow_stale:
        return 2
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect World Bank Pink Sheet commodity prices")
    parser.add_argument("--force", action="store_true", help="Bypass 24h raw-workbook cache")
    parser.add_argument("--dry-run", action="store_true", help="Parse and summarize without writing outputs")
    parser.add_argument("--check", action="store_true", help="Check existing processed outputs and exit")
    parser.add_argument("--allow-stale", action="store_true", help="Return success even if latest observation is stale")
    parser.add_argument("--url", help=f"Override workbook URL (or set {SOURCE_URL_ENV})")
    args = parser.parse_args()

    try:
        if args.check:
            return check_outputs(allow_stale=args.allow_stale)
        collect(args)
        return check_outputs(allow_stale=True) if not args.dry_run else 0
    except Exception as exc:
        log.error("World Bank commodity collection failed: %s", exc)
        log.exception(exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
