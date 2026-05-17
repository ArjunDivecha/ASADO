#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: setup_duckdb.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/Normalized_T2_MasterCSV.csv
                                                   (1.19M rows, 111 variables, 34 countries)
- /Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/T2 Master.xlsx
                                                   (58 sheets, raw factor levels)
- Data/processed/external_factors_panel.parquet  (112K rows, 35 variables)
- Data/processed/extended_factors_panel.parquet  (77K rows, 51 variables)
- /Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 GDELT/GDELT_Factors_MasterCSV.csv
                                                   (405K rows, 93 variables, 34 countries)
- Data/processed/imf_factors_panel.parquet       (61K rows, 18 variables, 34 countries)
- Data/processed/macrostructure_panel.parquet    (macrostructure fragility / ownership panel)
- Data/processed/bilateral_portfolio_matrix.parquet (historical portfolio ownership matrix)
- Data/processed/bloomberg_factors_panel.parquet (Bloomberg sovereign data, 34 countries)
- Data/processed/wb_commodity_factor_panel.parquet (World Bank Pink Sheet global commodity context)

OUTPUT FILES:
- Data/asado.duckdb                             (unified analytical database)

VERSION: 1.0
LAST UPDATED: 2026-04-12
AUTHOR: Arjun Divecha

DESCRIPTION:
Creates a DuckDB analytical database containing all ASADO data sources in a
unified schema. Loads T2 Master factors, external/extended panels, and GDELT
sentiment data into separate tables, then creates a unified view for
cross-source queries.

Tables created:
  - t2_master:          T2 normalized factor data (111 vars, 34 countries, 2000-2026)
  - t2_raw:             Raw T2 factor levels from the authoritative workbook
  - country_reference:  Canonical ISO/ASADO country mapping surface for joins
  - external_factors:   Program 1 panel (35 vars from 7 sources)
  - extended_factors:   Program 2 panel (51 vars from 12 sources)
  - gdelt_panel:        GDELT normalized factors (93 vars, 34 countries, 2015-2026)
  - imf_factors:        Program 3 panel (18 vars from 6 IMF datasets)
  - macrostructure_factors: Macrostructure panel (IMF FSI, QPSD debt structure, derived scores)
  - bilateral_portfolio_matrix: Historical portfolio ownership matrix
  - bloomberg_factors:  Bloomberg sovereign data (bonds, CDS, ratings, 34 countries)
  - wb_commodity_prices / wb_commodity_indices / wb_commodity_features:
                        World Bank Pink Sheet canonical monthly commodity tables
  - wb_commodity_factor_panel: Selected global commodity features broadcast to
                        the 34-country ASADO panel as explanatory inputs
  - factor_returns:     Monthly net returns of top-20% portfolios per factor variant
                        (Econ / T2 Style / GDELT optimizer outputs; no country axis)
  - factor_top20_membership: Sparse country-level membership in each factor's top-20%
                        bucket per month (date, country, factor, weight, source)
  - country_factor_attribution: VIEW = membership ⨝ factor_returns; contribution per
                        (date, country, factor) computed as weight × factor_return
  - unified_panel:      VIEW union of all factor-panel tables

DEPENDENCIES:
- duckdb, pandas

USAGE:
  python scripts/setup_duckdb.py          # create/rebuild database
  python scripts/setup_duckdb.py --check  # verify existing database

NOTES:
- Overwrites existing asado.duckdb on each run (idempotent rebuild)
- GDELT loaded from normalized tidy CSV (same schema as T2 Master)
- Indexes on (country, date) and (variable) for fast analytical queries
=============================================================================
"""

import argparse
import json
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "Data"
DB_PATH = DATA_DIR / "asado.duckdb"
CONFIG_PATH = BASE_DIR / "config" / "country_mapping.json"

T2_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy")
T2_CSV = T2_DIR / "Normalized_T2_MasterCSV.csv"
T2_WORKBOOK = T2_DIR / "T2 Master.xlsx"
EXTERNAL_PQ = DATA_DIR / "processed" / "external_factors_panel.parquet"
EXTENDED_PQ = DATA_DIR / "processed" / "extended_factors_panel.parquet"
GDELT_CSV = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 GDELT/GDELT_Factors_MasterCSV.csv")
GDELT_FALLBACK_PQ = DATA_DIR / "processed" / "gdelt_panel_snapshot.parquet"
IMF_PQ = DATA_DIR / "processed" / "imf_factors_panel.parquet"
MACROSTRUCTURE_PQ = DATA_DIR / "processed" / "macrostructure_panel.parquet"
BILATERAL_PORTFOLIO_PQ = DATA_DIR / "processed" / "bilateral_portfolio_matrix.parquet"
BLOOMBERG_PQ = DATA_DIR / "processed" / "bloomberg_factors_panel.parquet"
FACTOR_RETURNS_PQ = DATA_DIR / "processed" / "factor_returns_panel.parquet"
FACTOR_TOP20_MEMBERSHIP_PQ = DATA_DIR / "processed" / "factor_top20_membership_panel.parquet"
WB_COMMODITY_PRICES_PQ = DATA_DIR / "processed" / "wb_commodity_prices.parquet"
WB_COMMODITY_INDICES_PQ = DATA_DIR / "processed" / "wb_commodity_indices.parquet"
WB_COMMODITY_META_PQ = DATA_DIR / "processed" / "wb_commodity_meta.parquet"
WB_COMMODITY_FEATURES_PQ = DATA_DIR / "processed" / "wb_commodity_features.parquet"
WB_COMMODITY_FACTOR_PANEL_PQ = DATA_DIR / "processed" / "wb_commodity_factor_panel.parquet"

T2_RETURN_SHEETS = {"1MRet", "3MRet", "6MRet", "9MRet", "12MRet"}
GLOBAL_BROADCAST_VARIABLES = {
    "FRED_UST_2Y",
    "FRED_UST_10Y",
    "FRED_Yield_Curve_10Y2Y",
}
MARKET_SLEEVE_COUNTRIES = {"ChinaH", "NASDAQ", "US SmallCap"}
SOVEREIGN_PROXY_COUNTRIES = {"ChinaA"}


def _canonical_variable_name(name: str) -> str:
    return " ".join(str(name).split()).strip()


def _tracked_countries() -> list[str]:
    with open(CONFIG_PATH, encoding="utf-8") as handle:
        mapping = json.load(handle)
    return list(mapping["countries"].keys())


def _graph_role_for_country(country: str) -> str:
    if country in MARKET_SLEEVE_COUNTRIES:
        return "market_sleeve"
    if country in SOVEREIGN_PROXY_COUNTRIES:
        return "sovereign_proxy"
    return "sovereign"


def create_country_reference_table(con: duckdb.DuckDBPyConnection) -> int:
    """Create a canonical ISO3 -> ASADO country mapping surface for cross-table joins."""
    print("Creating country_reference table ...")
    with open(CONFIG_PATH, encoding="utf-8") as handle:
        mapping = json.load(handle)["countries"]

    grouped: dict[str, list[dict[str, str | None]]] = {}
    for country, codes in mapping.items():
        iso3 = codes["iso3"]
        grouped.setdefault(iso3, []).append(
            {
                "country": country,
                "iso2": codes.get("iso2"),
                "iso3": iso3,
                "imf": codes.get("imf"),
                "oecd": codes.get("oecd"),
                "bis": codes.get("bis"),
                "wb": codes.get("wb"),
                "fred_epu": codes.get("fred_epu"),
                "gpr": codes.get("gpr"),
                "epu_col": codes.get("epu_col"),
                "graph_role": _graph_role_for_country(country),
            }
        )

    role_priority = {"sovereign_proxy": 0, "sovereign": 1, "market_sleeve": 2}
    rows = []
    for iso3, entries in grouped.items():
        ordered = sorted(
            entries,
            key=lambda row: (role_priority.get(str(row["graph_role"]), 99), str(row["country"])),
        )
        canonical = ordered[0]
        variants = [str(row["country"]) for row in ordered]
        market_sleeves = [str(row["country"]) for row in ordered if row["graph_role"] == "market_sleeve"]
        rows.append(
            {
                "country": canonical["country"],
                "iso2": canonical["iso2"],
                "iso3": canonical["iso3"],
                "imf": canonical["imf"],
                "oecd": canonical["oecd"],
                "bis": canonical["bis"],
                "wb": canonical["wb"],
                "fred_epu": canonical["fred_epu"],
                "gpr": canonical["gpr"],
                "epu_col": canonical["epu_col"],
                "graph_role": canonical["graph_role"],
                "variant_count": len(variants),
                "all_country_variants": ", ".join(variants),
                "market_sleeve_variants": ", ".join(market_sleeves) if market_sleeves else None,
                "has_market_sleeves": bool(market_sleeves),
            }
        )

    reference_df = pd.DataFrame(rows).sort_values(["country"]).reset_index(drop=True)
    con.execute("DROP TABLE IF EXISTS country_reference")
    con.register("country_reference_df", reference_df)
    con.execute("""
        CREATE TABLE country_reference AS
        SELECT
            country,
            iso2,
            iso3,
            imf,
            oecd,
            bis,
            wb,
            fred_epu,
            gpr,
            epu_col,
            graph_role,
            CAST(variant_count AS INTEGER) AS variant_count,
            all_country_variants,
            market_sleeve_variants,
            CAST(has_market_sleeves AS BOOLEAN) AS has_market_sleeves
        FROM country_reference_df
    """)
    con.unregister("country_reference_df")
    count = con.execute("SELECT COUNT(*) FROM country_reference").fetchone()[0]
    print(f"  country_reference: {count:,} canonical ISO3 mappings")
    return count


def load_t2_master(con: duckdb.DuckDBPyConnection) -> int:
    """Load T2 Master CSV into t2_master table."""
    print("Loading T2 Master CSV ...")
    con.execute("DROP TABLE IF EXISTS t2_master")
    con.execute(f"""
        CREATE TABLE t2_master AS
        SELECT
            CAST(date AS DATE) AS date,
            country,
            value,
            variable
        FROM read_csv_auto('{T2_CSV}')
    """)
    count = con.execute("SELECT COUNT(*) FROM t2_master").fetchone()[0]
    vars_count = con.execute("SELECT COUNT(DISTINCT variable) FROM t2_master").fetchone()[0]
    countries = con.execute("SELECT COUNT(DISTINCT country) FROM t2_master").fetchone()[0]
    print(f"  t2_master: {count:,} rows, {vars_count} variables, {countries} countries")
    return count


def load_t2_raw(con: duckdb.DuckDBPyConnection) -> int:
    """Load raw T2 workbook factors into t2_raw."""
    print("Loading raw T2 workbook factors ...")
    con.execute("DROP TABLE IF EXISTS t2_raw")
    con.execute("""
        CREATE TABLE t2_raw (
            date DATE,
            country VARCHAR,
            value DOUBLE,
            variable VARCHAR
        )
    """)

    total_rows = 0
    with pd.ExcelFile(T2_WORKBOOK, engine="openpyxl") as workbook:
        raw_sheets = [sheet for sheet in workbook.sheet_names if sheet not in T2_RETURN_SHEETS]
        for sheet_name in raw_sheets:
            wide_df = pd.read_excel(workbook, sheet_name=sheet_name)
            if wide_df.empty:
                continue

            date_column = wide_df.columns[0]
            long_df = (
                wide_df.rename(columns={date_column: "date"})
                .melt(id_vars="date", var_name="country", value_name="value")
                .dropna(subset=["date", "value"])
            )
            if long_df.empty:
                continue

            long_df["date"] = pd.to_datetime(long_df["date"]).dt.date
            long_df["country"] = long_df["country"].astype(str).str.strip()
            long_df["variable"] = _canonical_variable_name(sheet_name)

            con.register("t2_raw_stage", long_df[["date", "country", "value", "variable"]])
            con.execute("""
                INSERT INTO t2_raw
                SELECT
                    CAST(date AS DATE) AS date,
                    country,
                    CAST(value AS DOUBLE) AS value,
                    variable
                FROM t2_raw_stage
            """)
            con.unregister("t2_raw_stage")
            total_rows += len(long_df)

    vars_count = con.execute("SELECT COUNT(DISTINCT variable) FROM t2_raw").fetchone()[0]
    countries = con.execute("SELECT COUNT(DISTINCT country) FROM t2_raw").fetchone()[0]
    print(f"  t2_raw: {total_rows:,} rows, {vars_count} variables, {countries} countries")
    return total_rows


def broadcast_global_reference_series(con: duckdb.DuckDBPyConnection, table_name: str) -> int:
    """Replicate truly global U.S. Treasury reference series across the tracked country set."""
    countries_df = pd.DataFrame({"country": _tracked_countries()})
    con.register("broadcast_countries", countries_df)
    variable_list = ", ".join(f"'{name}'" for name in sorted(GLOBAL_BROADCAST_VARIABLES))
    before_count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    con.execute(f"""
        INSERT INTO {table_name}
        SELECT
            src.date,
            bc.country,
            src.value,
            src.variable,
            src.source
        FROM (
            SELECT
                date,
                variable,
                source,
                MAX(value) AS value
            FROM {table_name}
            WHERE variable IN ({variable_list})
            GROUP BY date, variable, source
        ) AS src
        CROSS JOIN broadcast_countries AS bc
        LEFT JOIN {table_name} existing
            ON existing.date = src.date
           AND existing.variable = src.variable
           AND existing.country = bc.country
        WHERE existing.country IS NULL
    """)
    inserted = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0] - before_count
    con.unregister("broadcast_countries")
    if inserted:
        print(f"  {table_name}: broadcast {inserted:,} global U.S. Treasury rows")
    return inserted


def load_parquet_table(con: duckdb.DuckDBPyConnection, table_name: str,
                       pq_path: Path, label: str) -> int:
    """Load a parquet panel file into a named table."""
    print(f"Loading {label} ...")
    con.execute(f"DROP TABLE IF EXISTS {table_name}")
    con.execute(f"""
        CREATE TABLE {table_name} AS
        SELECT
            CAST(date AS DATE) AS date,
            country,
            value,
            variable,
            source
        FROM read_parquet('{pq_path}')
    """)
    if table_name in {"external_factors", "extended_factors"}:
        broadcast_global_reference_series(con, table_name)
    count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    vars_count = con.execute(f"SELECT COUNT(DISTINCT variable) FROM {table_name}").fetchone()[0]
    countries = con.execute(f"SELECT COUNT(DISTINCT country) FROM {table_name}").fetchone()[0]
    print(f"  {table_name}: {count:,} rows, {vars_count} variables, {countries} countries")
    return count


def create_empty_factor_table(con: duckdb.DuckDBPyConnection, table_name: str) -> int:
    """Create an empty factor-style table when an optional panel is absent."""
    con.execute(f"DROP TABLE IF EXISTS {table_name}")
    con.execute(f"""
        CREATE TABLE {table_name} (
            date DATE,
            country VARCHAR,
            value DOUBLE,
            variable VARCHAR,
            source VARCHAR
        )
    """)
    return 0


def load_wb_commodity_tables(con: duckdb.DuckDBPyConnection) -> int:
    """Load World Bank Pink Sheet commodity tables and factor-panel projection."""
    print("Loading World Bank Commodity Price Intelligence ...")
    total = 0

    if WB_COMMODITY_PRICES_PQ.exists():
        con.execute("DROP TABLE IF EXISTS wb_commodity_prices")
        con.execute(f"""
            CREATE TABLE wb_commodity_prices AS
            SELECT
                CAST(date AS DATE) AS date,
                commodity_code,
                commodity_name,
                unit,
                CAST(nominal_price_usd AS DOUBLE) AS nominal_price_usd,
                category,
                source_sheet,
                TRY_CAST(source_file_date AS DATE) AS source_file_date,
                source_url,
                last_loaded_at
            FROM read_parquet('{WB_COMMODITY_PRICES_PQ}')
        """)
    else:
        con.execute("DROP TABLE IF EXISTS wb_commodity_prices")
        con.execute("""
            CREATE TABLE wb_commodity_prices (
                date DATE,
                commodity_code VARCHAR,
                commodity_name VARCHAR,
                unit VARCHAR,
                nominal_price_usd DOUBLE,
                category VARCHAR,
                source_sheet VARCHAR,
                source_file_date DATE,
                source_url VARCHAR,
                last_loaded_at VARCHAR
            )
        """)

    if WB_COMMODITY_INDICES_PQ.exists():
        con.execute("DROP TABLE IF EXISTS wb_commodity_indices")
        con.execute(f"""
            CREATE TABLE wb_commodity_indices AS
            SELECT
                CAST(date AS DATE) AS date,
                index_code,
                index_name,
                CAST(nominal_index_2010_100 AS DOUBLE) AS nominal_index_2010_100,
                category,
                source_sheet,
                TRY_CAST(source_file_date AS DATE) AS source_file_date,
                source_url,
                last_loaded_at
            FROM read_parquet('{WB_COMMODITY_INDICES_PQ}')
        """)
    else:
        con.execute("DROP TABLE IF EXISTS wb_commodity_indices")
        con.execute("""
            CREATE TABLE wb_commodity_indices (
                date DATE,
                index_code VARCHAR,
                index_name VARCHAR,
                nominal_index_2010_100 DOUBLE,
                category VARCHAR,
                source_sheet VARCHAR,
                source_file_date DATE,
                source_url VARCHAR,
                last_loaded_at VARCHAR
            )
        """)

    if WB_COMMODITY_META_PQ.exists():
        con.execute("DROP TABLE IF EXISTS wb_commodity_meta")
        con.execute(f"""
            CREATE TABLE wb_commodity_meta AS
            SELECT
                series_code,
                series_type,
                display_name,
                category,
                unit,
                source_description,
                canonical_source,
                import_status,
                CAST(is_projected_to_factor_panel AS BOOLEAN) AS is_projected_to_factor_panel
            FROM read_parquet('{WB_COMMODITY_META_PQ}')
        """)
    else:
        con.execute("DROP TABLE IF EXISTS wb_commodity_meta")
        con.execute("""
            CREATE TABLE wb_commodity_meta (
                series_code VARCHAR,
                series_type VARCHAR,
                display_name VARCHAR,
                category VARCHAR,
                unit VARCHAR,
                source_description VARCHAR,
                canonical_source VARCHAR,
                import_status VARCHAR,
                is_projected_to_factor_panel BOOLEAN
            )
        """)

    if WB_COMMODITY_FEATURES_PQ.exists():
        con.execute("DROP TABLE IF EXISTS wb_commodity_features")
        con.execute(f"""
            CREATE TABLE wb_commodity_features AS
            SELECT
                CAST(date AS DATE) AS date,
                series_code,
                series_type,
                display_name,
                category,
                unit,
                feature,
                CAST(value AS DOUBLE) AS value,
                source,
                source_frequency,
                last_loaded_at
            FROM read_parquet('{WB_COMMODITY_FEATURES_PQ}')
        """)
    else:
        con.execute("DROP TABLE IF EXISTS wb_commodity_features")
        con.execute("""
            CREATE TABLE wb_commodity_features (
                date DATE,
                series_code VARCHAR,
                series_type VARCHAR,
                display_name VARCHAR,
                category VARCHAR,
                unit VARCHAR,
                feature VARCHAR,
                value DOUBLE,
                source VARCHAR,
                source_frequency VARCHAR,
                last_loaded_at VARCHAR
            )
        """)

    if WB_COMMODITY_FACTOR_PANEL_PQ.exists():
        con.execute("DROP TABLE IF EXISTS wb_commodity_factor_panel")
        con.execute(f"""
            CREATE TABLE wb_commodity_factor_panel AS
            SELECT
                CAST(date AS DATE) AS date,
                country,
                CAST(value AS DOUBLE) AS value,
                variable,
                source,
                series_code,
                feature,
                CAST(is_global_broadcast AS BOOLEAN) AS is_global_broadcast
            FROM read_parquet('{WB_COMMODITY_FACTOR_PANEL_PQ}')
        """)
    else:
        con.execute("DROP TABLE IF EXISTS wb_commodity_factor_panel")
        con.execute("""
            CREATE TABLE wb_commodity_factor_panel (
                date DATE,
                country VARCHAR,
                value DOUBLE,
                variable VARCHAR,
                source VARCHAR,
                series_code VARCHAR,
                feature VARCHAR,
                is_global_broadcast BOOLEAN
            )
        """)

    price_series = con.execute("SELECT COUNT(DISTINCT commodity_code) FROM wb_commodity_prices").fetchone()[0]
    index_series = con.execute("SELECT COUNT(DISTINCT index_code) FROM wb_commodity_indices").fetchone()[0]
    projected_rows = con.execute("SELECT COUNT(*) FROM wb_commodity_factor_panel").fetchone()[0]
    projected_vars = con.execute("SELECT COUNT(DISTINCT variable) FROM wb_commodity_factor_panel").fetchone()[0]
    latest = con.execute("""
        SELECT MAX(date) FROM (
            SELECT MAX(date) AS date FROM wb_commodity_prices
            UNION ALL
            SELECT MAX(date) AS date FROM wb_commodity_indices
        )
    """).fetchone()[0]
    total += con.execute("SELECT COUNT(*) FROM wb_commodity_prices").fetchone()[0]
    total += con.execute("SELECT COUNT(*) FROM wb_commodity_indices").fetchone()[0]
    total += con.execute("SELECT COUNT(*) FROM wb_commodity_features").fetchone()[0]
    total += projected_rows
    print(
        "  wb_commodity: "
        f"{price_series} prices, {index_series} indices, "
        f"{projected_vars} projected variables, {projected_rows:,} factor rows, latest={latest}"
    )
    return total


def load_bilateral_portfolio_table(con: duckdb.DuckDBPyConnection) -> int:
    """Load the historical portfolio ownership matrix into DuckDB."""
    print("Loading bilateral portfolio matrix ...")
    con.execute("DROP TABLE IF EXISTS bilateral_portfolio_matrix")
    con.execute(f"""
        CREATE TABLE bilateral_portfolio_matrix AS
        SELECT
            CAST(date AS DATE) AS date,
            reporter_iso3,
            counterpart_iso3,
            instrument_type,
            CAST(amount_usd AS DOUBLE) AS amount_usd,
            CAST(share_of_reporter_portfolio_pct AS DOUBLE) AS share_of_reporter_portfolio_pct,
            CAST(share_of_counterpart_inbound_pct AS DOUBLE) AS share_of_counterpart_inbound_pct,
            source,
            frequency,
            CAST(is_official_sector AS BOOLEAN) AS is_official_sector
        FROM read_parquet('{BILATERAL_PORTFOLIO_PQ}')
    """)
    count = con.execute("SELECT COUNT(*) FROM bilateral_portfolio_matrix").fetchone()[0]
    reporters = con.execute("SELECT COUNT(DISTINCT reporter_iso3) FROM bilateral_portfolio_matrix").fetchone()[0]
    counterparts = con.execute("SELECT COUNT(DISTINCT counterpart_iso3) FROM bilateral_portfolio_matrix").fetchone()[0]
    print(
        "  bilateral_portfolio_matrix: "
        f"{count:,} rows, {reporters} reporters, {counterparts} counterparts"
    )
    return count


def create_empty_bilateral_portfolio_table(con: duckdb.DuckDBPyConnection) -> int:
    """Create an empty historical portfolio matrix table when the parquet is absent."""
    con.execute("DROP TABLE IF EXISTS bilateral_portfolio_matrix")
    con.execute("""
        CREATE TABLE bilateral_portfolio_matrix (
            date DATE,
            reporter_iso3 VARCHAR,
            counterpart_iso3 VARCHAR,
            instrument_type VARCHAR,
            amount_usd DOUBLE,
            share_of_reporter_portfolio_pct DOUBLE,
            share_of_counterpart_inbound_pct DOUBLE,
            source VARCHAR,
            frequency VARCHAR,
            is_official_sector BOOLEAN
        )
    """)
    return 0


def load_gdelt(con: duckdb.DuckDBPyConnection) -> int:
    """Load normalized GDELT panel into gdelt_panel table."""
    if GDELT_CSV.exists():
        source_path = GDELT_CSV
        source_kind = "csv"
        print("Loading GDELT normalized CSV ...")
    elif GDELT_FALLBACK_PQ.exists():
        source_path = GDELT_FALLBACK_PQ
        source_kind = "parquet"
        print("Loading GDELT fallback snapshot ...")
    else:
        raise FileNotFoundError(
            f"Neither canonical GDELT CSV nor fallback snapshot exists: {GDELT_CSV} | {GDELT_FALLBACK_PQ}"
        )

    con.execute("DROP TABLE IF EXISTS gdelt_panel")
    if source_kind == "csv":
        con.execute(f"""
            CREATE TABLE gdelt_panel AS
            SELECT
                CAST(date AS DATE) AS date,
                country,
                value,
                variable
            FROM read_csv_auto('{source_path}')
        """)
    else:
        con.execute(f"""
            CREATE TABLE gdelt_panel AS
            SELECT
                CAST(date AS DATE) AS date,
                country,
                value,
                variable
            FROM read_parquet('{source_path}')
        """)
    count = con.execute("SELECT COUNT(*) FROM gdelt_panel").fetchone()[0]
    vars_count = con.execute("SELECT COUNT(DISTINCT variable) FROM gdelt_panel").fetchone()[0]
    countries = con.execute("SELECT COUNT(DISTINCT country) FROM gdelt_panel").fetchone()[0]
    print(f"  gdelt_panel: {count:,} rows, {vars_count} variables, {countries} countries")
    return count


def load_factor_returns(con: duckdb.DuckDBPyConnection) -> int:
    """Load factor_returns_panel.parquet into the factor_returns table."""
    print("Loading Factor Returns Panel ...")
    con.execute("DROP TABLE IF EXISTS factor_returns")
    con.execute(f"""
        CREATE TABLE factor_returns AS
        SELECT
            CAST(date AS DATE) AS date,
            factor,
            CAST(value AS DOUBLE) AS value,
            source
        FROM read_parquet('{FACTOR_RETURNS_PQ}')
    """)
    count = con.execute("SELECT COUNT(*) FROM factor_returns").fetchone()[0]
    factors = con.execute("SELECT COUNT(DISTINCT factor) FROM factor_returns").fetchone()[0]
    sources = con.execute("SELECT COUNT(DISTINCT source) FROM factor_returns").fetchone()[0]
    print(f"  factor_returns: {count:,} rows, {factors} factors, {sources} sources")
    return count


def create_empty_factor_returns_table(con: duckdb.DuckDBPyConnection) -> int:
    con.execute("DROP TABLE IF EXISTS factor_returns")
    con.execute("""
        CREATE TABLE factor_returns (
            date DATE,
            factor VARCHAR,
            value DOUBLE,
            source VARCHAR
        )
    """)
    return 0


def load_factor_top20_membership(con: duckdb.DuckDBPyConnection) -> int:
    """Load factor_top20_membership_panel.parquet into factor_top20_membership."""
    print("Loading Factor Top-20 Membership Panel ...")
    con.execute("DROP TABLE IF EXISTS factor_top20_membership")
    con.execute(f"""
        CREATE TABLE factor_top20_membership AS
        SELECT
            CAST(date AS DATE) AS date,
            country,
            factor,
            CAST(weight AS DOUBLE) AS weight,
            source
        FROM read_parquet('{FACTOR_TOP20_MEMBERSHIP_PQ}')
    """)
    count = con.execute("SELECT COUNT(*) FROM factor_top20_membership").fetchone()[0]
    factors = con.execute("SELECT COUNT(DISTINCT factor) FROM factor_top20_membership").fetchone()[0]
    countries = con.execute("SELECT COUNT(DISTINCT country) FROM factor_top20_membership").fetchone()[0]
    print(
        f"  factor_top20_membership: {count:,} rows, "
        f"{factors} factors, {countries} countries"
    )
    return count


def create_empty_factor_top20_membership_table(con: duckdb.DuckDBPyConnection) -> int:
    con.execute("DROP TABLE IF EXISTS factor_top20_membership")
    con.execute("""
        CREATE TABLE factor_top20_membership (
            date DATE,
            country VARCHAR,
            factor VARCHAR,
            weight DOUBLE,
            source VARCHAR
        )
    """)
    return 0


def create_country_factor_attribution_view(con: duckdb.DuckDBPyConnection):
    """Country-level attribution = membership ⨝ factor returns, joined on (date, factor, source)."""
    print("Creating country_factor_attribution view ...")
    con.execute("DROP VIEW IF EXISTS country_factor_attribution")
    con.execute("""
        CREATE VIEW country_factor_attribution AS
        SELECT
            m.date,
            m.country,
            m.factor,
            m.weight,
            r.value AS factor_return,
            m.weight * r.value AS contribution,
            m.source
        FROM factor_top20_membership AS m
        JOIN factor_returns AS r
          ON r.date = m.date
         AND r.factor = m.factor
         AND r.source = m.source
    """)
    try:
        count = con.execute("SELECT COUNT(*) FROM country_factor_attribution").fetchone()[0]
        print(f"  country_factor_attribution: {count:,} rows (view)")
    except Exception as exc:
        print(f"  country_factor_attribution: created (count unavailable: {exc})")


def create_unified_view(con: duckdb.DuckDBPyConnection):
    """Create a unified view across all ASADO factor tables."""
    print("Creating unified_panel view ...")
    con.execute("DROP VIEW IF EXISTS unified_panel")
    con.execute("""
        CREATE VIEW unified_panel AS
        SELECT date, country, value, variable, 't2' AS source FROM t2_master
        UNION ALL
        SELECT date, country, value, variable, 't2_raw' AS source FROM t2_raw
        UNION ALL
        SELECT date, country, value, variable, source FROM external_factors
        UNION ALL
        SELECT date, country, value, variable, source FROM extended_factors
        UNION ALL
        SELECT date, country, value, variable, 'gdelt' AS source FROM gdelt_panel
        UNION ALL
        SELECT date, country, value, variable, source FROM imf_factors
        UNION ALL
        SELECT date, country, value, variable, source FROM macrostructure_factors
        UNION ALL
        SELECT date, country, value, variable, source FROM wb_commodity_factor_panel
        UNION ALL
        SELECT date, country, CAST(value AS DOUBLE) AS value, variable, source
        FROM bloomberg_factors
        WHERE TRY_CAST(value AS DOUBLE) IS NOT NULL
    """)
    count = con.execute("SELECT COUNT(*) FROM unified_panel").fetchone()[0]
    vars_count = con.execute("SELECT COUNT(DISTINCT variable) FROM unified_panel").fetchone()[0]
    print(f"  unified_panel: {count:,} rows, {vars_count} variables")


def create_indexes(con: duckdb.DuckDBPyConnection):
    """Create indexes for fast analytical queries."""
    print("Creating indexes ...")
    for table in ["t2_master", "t2_raw", "external_factors", "extended_factors", "gdelt_panel",
                   "imf_factors", "macrostructure_factors", "bloomberg_factors",
                   "wb_commodity_factor_panel"]:
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_ctry_date ON {table}(country, date)")
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_var ON {table}(variable)")
    con.execute("""
        CREATE INDEX IF NOT EXISTS idx_wb_commodity_prices_code_date
        ON wb_commodity_prices(commodity_code, date)
    """)
    con.execute("""
        CREATE INDEX IF NOT EXISTS idx_wb_commodity_indices_code_date
        ON wb_commodity_indices(index_code, date)
    """)
    con.execute("""
        CREATE INDEX IF NOT EXISTS idx_wb_commodity_features_code_feature_date
        ON wb_commodity_features(series_code, feature, date)
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_country_reference_country ON country_reference(country)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_country_reference_iso3 ON country_reference(iso3)")
    con.execute("""
        CREATE INDEX IF NOT EXISTS idx_bilateral_portfolio_matrix_rep_cp_date
        ON bilateral_portfolio_matrix(reporter_iso3, counterpart_iso3, date)
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_factor_returns_date_factor ON factor_returns(date, factor)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_factor_returns_source ON factor_returns(source)")
    con.execute("""
        CREATE INDEX IF NOT EXISTS idx_factor_top20_membership_date_country
        ON factor_top20_membership(date, country)
    """)
    con.execute("""
        CREATE INDEX IF NOT EXISTS idx_factor_top20_membership_factor
        ON factor_top20_membership(factor, date)
    """)
    print("  Indexes created on factor tables, country_reference, commodity, bilateral ownership, and optimizer panels")


def check_database():
    """Verify an existing database."""
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH}")
        return

    con = duckdb.connect(str(DB_PATH), read_only=True)
    print(f"Database: {DB_PATH}")
    print(f"File size: {DB_PATH.stat().st_size / 1e6:.1f} MB")
    print()

    tables = con.execute("SHOW TABLES").fetchall()
    print(f"Tables: {[t[0] for t in tables]}")
    print()

    for table in ["t2_master", "t2_raw", "country_reference", "external_factors", "extended_factors", "gdelt_panel",
                   "imf_factors", "macrostructure_factors", "bloomberg_factors",
                   "wb_commodity_factor_panel", "factor_returns", "factor_top20_membership"]:
        try:
            if table == "factor_returns":
                count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                fac_c = con.execute(f"SELECT COUNT(DISTINCT factor) FROM {table}").fetchone()[0]
                src_c = con.execute(f"SELECT COUNT(DISTINCT source) FROM {table}").fetchone()[0]
                date_min = con.execute(f"SELECT MIN(date) FROM {table}").fetchone()[0]
                date_max = con.execute(f"SELECT MAX(date) FROM {table}").fetchone()[0]
                print(f"  {table:20s}: {count:>10,} rows | {fac_c:>4} factors | {src_c} sources | {date_min} → {date_max}")
                continue
            if table == "factor_top20_membership":
                count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                fac_c = con.execute(f"SELECT COUNT(DISTINCT factor) FROM {table}").fetchone()[0]
                ctry_c = con.execute(f"SELECT COUNT(DISTINCT country) FROM {table}").fetchone()[0]
                date_min = con.execute(f"SELECT MIN(date) FROM {table}").fetchone()[0]
                date_max = con.execute(f"SELECT MAX(date) FROM {table}").fetchone()[0]
                print(f"  {table:20s}: {count:>10,} rows | {fac_c:>4} factors | {ctry_c:>2} countries | {date_min} → {date_max}")
                continue
            if table == "country_reference":
                count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                iso3_c = con.execute(f"SELECT COUNT(DISTINCT iso3) FROM {table}").fetchone()[0]
                print(f"  {table:20s}: {count:>10,} rows | {iso3_c:>2} ISO3 codes")
            else:
                count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                vars_c = con.execute(f"SELECT COUNT(DISTINCT variable) FROM {table}").fetchone()[0]
                ctry_c = con.execute(f"SELECT COUNT(DISTINCT country) FROM {table}").fetchone()[0]
                date_min = con.execute(f"SELECT MIN(date) FROM {table}").fetchone()[0]
                date_max = con.execute(f"SELECT MAX(date) FROM {table}").fetchone()[0]
                print(f"  {table:20s}: {count:>10,} rows | {vars_c:>3} vars | {ctry_c:>2} countries | {date_min} → {date_max}")
        except Exception as e:
            print(f"  {table}: ERROR — {e}")

    try:
        price_series = con.execute("SELECT COUNT(DISTINCT commodity_code) FROM wb_commodity_prices").fetchone()[0]
        index_series = con.execute("SELECT COUNT(DISTINCT index_code) FROM wb_commodity_indices").fetchone()[0]
        feature_rows = con.execute("SELECT COUNT(*) FROM wb_commodity_features").fetchone()[0]
        latest = con.execute("""
            SELECT MAX(date) FROM (
                SELECT MAX(date) AS date FROM wb_commodity_prices
                UNION ALL
                SELECT MAX(date) AS date FROM wb_commodity_indices
            )
        """).fetchone()[0]
        print(
            "  wb_commodity_canonical: "
            f"{price_series:>3} prices | {index_series:>2} indices | "
            f"{feature_rows:>10,} feature rows | latest {latest}"
        )
    except Exception as e:
        print(f"  wb_commodity_canonical: ERROR — {e}")

    try:
        count = con.execute("SELECT COUNT(*) FROM bilateral_portfolio_matrix").fetchone()[0]
        reporters = con.execute("SELECT COUNT(DISTINCT reporter_iso3) FROM bilateral_portfolio_matrix").fetchone()[0]
        counterparts = con.execute("SELECT COUNT(DISTINCT counterpart_iso3) FROM bilateral_portfolio_matrix").fetchone()[0]
        date_min = con.execute("SELECT MIN(date) FROM bilateral_portfolio_matrix").fetchone()[0]
        date_max = con.execute("SELECT MAX(date) FROM bilateral_portfolio_matrix").fetchone()[0]
        print(
            "  bilateral_portfolio_matrix: "
            f"{count:>10,} rows | {reporters:>2} reporters | {counterparts:>2} counterparts | "
            f"{date_min} → {date_max}"
        )
    except Exception as e:
        print(f"  bilateral_portfolio_matrix: ERROR — {e}")

    try:
        total = con.execute("SELECT COUNT(*) FROM unified_panel").fetchone()[0]
        total_vars = con.execute("SELECT COUNT(DISTINCT variable) FROM unified_panel").fetchone()[0]
        print(f"\n  {'unified_panel':20s}: {total:>10,} rows | {total_vars:>3} vars (view)")
    except Exception as e:
        print(f"\n  unified_panel: ERROR — {e}")

    con.close()


def main():
    parser = argparse.ArgumentParser(description="ASADO DuckDB Setup")
    parser.add_argument("--check", action="store_true", help="Check existing database")
    args = parser.parse_args()

    if args.check:
        check_database()
        return

    required = [T2_CSV, T2_WORKBOOK, EXTERNAL_PQ, EXTENDED_PQ, IMF_PQ]
    optional = [
        MACROSTRUCTURE_PQ, BILATERAL_PORTFOLIO_PQ, BLOOMBERG_PQ,
        FACTOR_RETURNS_PQ, FACTOR_TOP20_MEMBERSHIP_PQ,
        WB_COMMODITY_FACTOR_PANEL_PQ,
    ]
    for f in required:
        if not f.exists():
            print(f"MISSING: {f}")
            sys.exit(1)
    if not GDELT_CSV.exists() and not GDELT_FALLBACK_PQ.exists():
        print(f"MISSING: {GDELT_CSV}")
        print(f"MISSING: {GDELT_FALLBACK_PQ}")
        sys.exit(1)
    for f in optional:
        if not f.exists():
            print(f"OPTIONAL NOT FOUND (will skip): {f}")

    start = time.time()
    print("=" * 60)
    print("ASADO DuckDB Setup")
    print("=" * 60)
    print(f"Database path: {DB_PATH}")
    print()

    if DB_PATH.exists():
        DB_PATH.unlink()
        print("Removed existing database (clean rebuild)")

    con = duckdb.connect(str(DB_PATH))

    total = 0
    total += load_t2_master(con)
    print()
    total += load_t2_raw(con)
    print()
    total += create_country_reference_table(con)
    print()
    total += load_parquet_table(con, "external_factors", EXTERNAL_PQ, "External Factors Panel")
    print()
    total += load_parquet_table(con, "extended_factors", EXTENDED_PQ, "Extended Factors Panel")
    print()
    total += load_gdelt(con)
    print()
    total += load_parquet_table(con, "imf_factors", IMF_PQ, "IMF Factors Panel")
    print()
    if MACROSTRUCTURE_PQ.exists():
        total += load_parquet_table(con, "macrostructure_factors", MACROSTRUCTURE_PQ,
                                    "Macrostructure Panel")
    else:
        print("Macrostructure panel not found — creating empty table")
        create_empty_factor_table(con, "macrostructure_factors")
    print()
    total += load_wb_commodity_tables(con)
    print()
    if BILATERAL_PORTFOLIO_PQ.exists():
        total += load_bilateral_portfolio_table(con)
    else:
        print("Bilateral portfolio matrix not found — creating empty table")
        create_empty_bilateral_portfolio_table(con)
    print()
    if BLOOMBERG_PQ.exists():
        total += load_parquet_table(con, "bloomberg_factors", BLOOMBERG_PQ,
                                    "Bloomberg Factors Panel")
    else:
        print("Bloomberg panel not found — creating empty table")
        con.execute("DROP TABLE IF EXISTS bloomberg_factors")
        con.execute("""
            CREATE TABLE bloomberg_factors (
                date DATE, country VARCHAR, value VARCHAR,
                variable VARCHAR, source VARCHAR
            )
        """)
    print()
    if FACTOR_RETURNS_PQ.exists():
        total += load_factor_returns(con)
    else:
        print("Factor returns panel not found — creating empty table")
        create_empty_factor_returns_table(con)
    print()
    if FACTOR_TOP20_MEMBERSHIP_PQ.exists():
        total += load_factor_top20_membership(con)
    else:
        print("Factor top-20 membership panel not found — creating empty table")
        create_empty_factor_top20_membership_table(con)
    print()
    create_country_factor_attribution_view(con)
    print()
    create_unified_view(con)
    print()
    create_indexes(con)

    con.close()

    elapsed = time.time() - start
    db_size = DB_PATH.stat().st_size / 1e6

    print()
    print("=" * 60)
    print(f"Total rows loaded:  {total:,}")
    print(f"Database size:      {db_size:.1f} MB")
    print(f"Elapsed:            {elapsed:.1f}s")
    print(f"Database path:      {DB_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
