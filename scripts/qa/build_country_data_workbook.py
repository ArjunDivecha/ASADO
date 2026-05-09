"""
=============================================================================
SCRIPT NAME: scripts/qa/build_country_data_workbook.py
=============================================================================

INPUT FILES:
- Data/asado.duckdb :: feature_panel

OUTPUT FILES:
- Data/reports/Country_Data_Book.xlsx
    Excel workbook with one sheet per panel variable, shaped:
        rows    = dates (chronological, first-of-month)
        columns = 34 T2 countries in canonical order
        values  = raw observation; NaN = blank cell
    Plus a leading "INDEX" sheet listing every variable with metadata
    (source, sheet name, first_date, last_date, n_dates, n_countries).

VERSION: 1.0
LAST UPDATED: 2026-04-28
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
Inventory workbook for every panel data item in the warehouse EXCEPT for
Bloomberg market data and GDELT. Inclusion rule:

  - All variables tagged source NOT IN ('bloomberg', 'gdelt', 'gdelt_deep_*',
    't2', 't2_raw'), restricted to RAW (non-_CS, non-_TS) variants.
  - PLUS the 9 Bloomberg ETF / passive layer variables (the "MS_*" ETF / flow
    items) that conceptually belong to the macrostructure layer despite
    being sourced from Bloomberg.

Sheet naming:
  Excel limits sheet names to 31 chars. We use the variable name verbatim
  where possible; longer names get a hashed suffix to disambiguate. The
  full original name and source are always recoverable from the INDEX sheet.

DEPENDENCIES:
- duckdb, pandas, openpyxl

USAGE:
  python scripts/qa/build_country_data_workbook.py
=============================================================================
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import re
from pathlib import Path

import duckdb
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "Data"
DUCKDB_PATH = DATA_DIR / "asado.duckdb"
OUT_DIR = DATA_DIR / "reports"
OUT_XLSX = OUT_DIR / "Country_Data_Book.xlsx"
OUT_DIR.mkdir(parents=True, exist_ok=True)

T2_COUNTRIES = [
    "Australia", "Brazil", "Canada", "Chile", "ChinaA", "ChinaH",
    "Denmark", "France", "Germany", "Hong Kong", "India", "Indonesia",
    "Italy", "Japan", "Korea", "Malaysia", "Mexico", "NASDAQ",
    "Netherlands", "Philippines", "Poland", "Saudi Arabia", "Singapore",
    "South Africa", "Spain", "Sweden", "Switzerland", "Taiwan",
    "Thailand", "Turkey", "U.K.", "U.S.", "US SmallCap", "Vietnam",
]

EXCLUDED_SOURCES = ("gdelt", "gdelt_deep_theme", "gdelt_deep_gcam",
                    "gdelt_deep_event", "t2", "t2_raw")

# 9 Bloomberg ETF / passive vars to include despite source='bloomberg'
BLOOMBERG_INCLUDE = [
    "MS_Country_ETF_AUM_USD",
    "MS_Country_ETF_NetFlow_USD",
    "MS_ETF_Creation_Fee_USD",
    "MS_ETF_Creation_Unit_Size_Shares",
    "MS_ETF_NetCreation_Shares",
    "MS_ETF_NetFlow_to_MarketCap",
    "MS_ETF_Redemption_Fee_USD",
    "MS_Passive_AUM_to_MarketCap",
    "MS_Passive_Flow_Distortion",
]

INVALID_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")
SHEET_NAME_LIMIT = 31

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def safe_sheet_name(name: str, used: set[str]) -> str:
    """Coerce a variable name into a unique, Excel-legal sheet name (≤31 chars)."""
    cleaned = INVALID_SHEET_CHARS.sub("_", name)
    if len(cleaned) <= SHEET_NAME_LIMIT and cleaned not in used:
        used.add(cleaned)
        return cleaned
    # Truncate; append 4-char hash for uniqueness.
    h = hashlib.md5(name.encode("utf-8")).hexdigest()[:4]
    base_len = SHEET_NAME_LIMIT - 5  # 1 underscore + 4 hash chars
    candidate = f"{cleaned[:base_len]}_{h}"
    while candidate in used:
        h = hashlib.md5((name + candidate).encode("utf-8")).hexdigest()[:4]
        candidate = f"{cleaned[:base_len]}_{h}"
    used.add(candidate)
    return candidate


def fetch_inventory(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Return the (variable, source) inventory for the workbook."""
    placeholders = ",".join(["?"] * len(EXCLUDED_SOURCES))
    bb_placeholders = ",".join(["?"] * len(BLOOMBERG_INCLUDE))

    sql = f"""
        SELECT source, variable
        FROM feature_panel
        WHERE source NOT IN ({placeholders})
          AND source != 'bloomberg'
          AND variable NOT LIKE '%\\_CS' ESCAPE '\\'
          AND variable NOT LIKE '%\\_TS' ESCAPE '\\'
        GROUP BY source, variable

        UNION ALL

        SELECT source, variable
        FROM feature_panel
        WHERE source = 'bloomberg'
          AND variable IN ({bb_placeholders})
        GROUP BY source, variable
        ORDER BY source, variable
    """
    params = list(EXCLUDED_SOURCES) + BLOOMBERG_INCLUDE
    return con.execute(sql, params).df()


def fetch_variable_panel(con: duckdb.DuckDBPyConnection,
                         variable: str, source: str) -> pd.DataFrame:
    """Fetch (date, country, value) for one variable, return wide pivot."""
    df = con.execute(
        "SELECT date, country, value FROM feature_panel "
        "WHERE variable = ? AND source = ?",
        [variable, source],
    ).df()
    if df.empty:
        return pd.DataFrame(index=pd.DatetimeIndex([], name="date"),
                            columns=T2_COUNTRIES)
    df["date"] = pd.to_datetime(df["date"])
    wide = df.pivot_table(
        index="date", columns="country", values="value", aggfunc="first"
    )
    wide = wide.reindex(columns=T2_COUNTRIES)
    wide = wide.sort_index()
    return wide


def build_workbook() -> Path:
    with duckdb.connect(str(DUCKDB_PATH), read_only=True) as con:
        inventory = fetch_inventory(con)
        n_total = len(inventory)
        logger.info("Inventory: %d variables across %d sources",
                    n_total, inventory["source"].nunique())

        used_names: set[str] = {"INDEX"}
        index_rows: list[dict] = []
        sheet_data: list[tuple[str, pd.DataFrame]] = []

        for i, (_, row) in enumerate(inventory.iterrows(), start=1):
            variable, source = row["variable"], row["source"]
            sheet_name = safe_sheet_name(variable, used_names)
            wide = fetch_variable_panel(con, variable, source)
            if wide.empty:
                logger.warning("[%d/%d] %s — empty, skipping", i, n_total, variable)
                continue

            n_dates = wide.shape[0]
            n_countries_with_data = (wide.notna().any(axis=0)).sum()
            first_date = wide.index.min().date() if n_dates else None
            last_date = wide.index.max().date() if n_dates else None

            index_rows.append({
                "sheet_id": i,
                "sheet_name": sheet_name,
                "variable": variable,
                "source": source,
                "first_date": first_date,
                "last_date": last_date,
                "n_dates": n_dates,
                "n_countries_with_data": int(n_countries_with_data),
            })
            sheet_data.append((sheet_name, wide))

            if i % 25 == 0 or i == n_total:
                logger.info("[%d/%d] processed", i, n_total)

    index_df = pd.DataFrame(index_rows)

    logger.info("Writing workbook to %s ...", OUT_XLSX)
    # NaN → blank cells (default openpyxl behavior with na_rep="").
    with pd.ExcelWriter(OUT_XLSX, engine="openpyxl") as xw:
        index_df.to_excel(xw, sheet_name="INDEX", index=False)
        for sheet_name, wide in sheet_data:
            # Format index as date strings for readability; blank for NaN.
            out = wide.copy()
            out.index = out.index.strftime("%Y-%m-%d")
            out.index.name = "date"
            out.to_excel(xw, sheet_name=sheet_name, na_rep="")
    logger.info("Wrote %s (%.1f MB)", OUT_XLSX, OUT_XLSX.stat().st_size / 1e6)
    return OUT_XLSX


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args()
    if not DUCKDB_PATH.exists():
        logger.error("DuckDB not found: %s", DUCKDB_PATH)
        return 2
    build_workbook()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
