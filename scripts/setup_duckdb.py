#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: setup_duckdb.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/Transformer/Normalized_T2_MasterCSV.csv
                                                   (1.19M rows, 111 variables, 34 countries)
- Data/processed/external_factors_panel.parquet  (112K rows, 35 variables)
- Data/processed/extended_factors_panel.parquet  (77K rows, 51 variables)
- /Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 GDELT/GDELT_Factors_MasterCSV.csv
                                                   (405K rows, 93 variables, 34 countries)
- Data/processed/imf_factors_panel.parquet       (61K rows, 18 variables, 34 countries)
- Data/processed/bloomberg_factors_panel.parquet (Bloomberg sovereign data, 34 countries)

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
  - t2_master:          T2 factor data (111 vars, 34 countries, 2000-2026)
  - external_factors:   Program 1 panel (35 vars from 7 sources)
  - extended_factors:   Program 2 panel (51 vars from 12 sources)
  - gdelt_panel:        GDELT normalized factors (93 vars, 34 countries, 2015-2026)
  - imf_factors:        Program 3 panel (18 vars from 6 IMF datasets)
  - bloomberg_factors:  Bloomberg sovereign data (bonds, CDS, ratings, 34 countries)
  - unified_panel:      VIEW union of all six tables

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
import sys
import time
from pathlib import Path

import duckdb
import pandas as pd

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "Data"
DB_PATH = DATA_DIR / "asado.duckdb"

T2_CSV = Path("/Users/arjundivecha/Dropbox/AAA Backup/Transformer/Normalized_T2_MasterCSV.csv")
EXTERNAL_PQ = DATA_DIR / "processed" / "external_factors_panel.parquet"
EXTENDED_PQ = DATA_DIR / "processed" / "extended_factors_panel.parquet"
GDELT_CSV = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 GDELT/GDELT_Factors_MasterCSV.csv")
IMF_PQ = DATA_DIR / "processed" / "imf_factors_panel.parquet"
BLOOMBERG_PQ = DATA_DIR / "processed" / "bloomberg_factors_panel.parquet"


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
    count = con.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
    vars_count = con.execute(f"SELECT COUNT(DISTINCT variable) FROM {table_name}").fetchone()[0]
    countries = con.execute(f"SELECT COUNT(DISTINCT country) FROM {table_name}").fetchone()[0]
    print(f"  {table_name}: {count:,} rows, {vars_count} variables, {countries} countries")
    return count


def load_gdelt(con: duckdb.DuckDBPyConnection) -> int:
    """Load normalized GDELT tidy CSV into gdelt_panel table."""
    print("Loading GDELT normalized CSV ...")
    con.execute("DROP TABLE IF EXISTS gdelt_panel")
    con.execute(f"""
        CREATE TABLE gdelt_panel AS
        SELECT
            CAST(date AS DATE) AS date,
            country,
            value,
            variable
        FROM read_csv_auto('{GDELT_CSV}')
    """)
    count = con.execute("SELECT COUNT(*) FROM gdelt_panel").fetchone()[0]
    vars_count = con.execute("SELECT COUNT(DISTINCT variable) FROM gdelt_panel").fetchone()[0]
    countries = con.execute("SELECT COUNT(DISTINCT country) FROM gdelt_panel").fetchone()[0]
    print(f"  gdelt_panel: {count:,} rows, {vars_count} variables, {countries} countries")
    return count


def create_unified_view(con: duckdb.DuckDBPyConnection):
    """Create a unified view across all six tables."""
    print("Creating unified_panel view ...")
    con.execute("DROP VIEW IF EXISTS unified_panel")
    con.execute("""
        CREATE VIEW unified_panel AS
        SELECT date, country, value, variable, 't2' AS source FROM t2_master
        UNION ALL
        SELECT date, country, value, variable, source FROM external_factors
        UNION ALL
        SELECT date, country, value, variable, source FROM extended_factors
        UNION ALL
        SELECT date, country, value, variable, 'gdelt' AS source FROM gdelt_panel
        UNION ALL
        SELECT date, country, value, variable, source FROM imf_factors
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
    for table in ["t2_master", "external_factors", "extended_factors", "gdelt_panel",
                   "imf_factors", "bloomberg_factors"]:
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_ctry_date ON {table}(country, date)")
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_var ON {table}(variable)")
    print("  Indexes created on (country, date) and (variable) for all tables")


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

    for table in ["t2_master", "external_factors", "extended_factors", "gdelt_panel",
                   "imf_factors", "bloomberg_factors"]:
        try:
            count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            vars_c = con.execute(f"SELECT COUNT(DISTINCT variable) FROM {table}").fetchone()[0]
            ctry_c = con.execute(f"SELECT COUNT(DISTINCT country) FROM {table}").fetchone()[0]
            date_min = con.execute(f"SELECT MIN(date) FROM {table}").fetchone()[0]
            date_max = con.execute(f"SELECT MAX(date) FROM {table}").fetchone()[0]
            print(f"  {table:20s}: {count:>10,} rows | {vars_c:>3} vars | {ctry_c:>2} countries | {date_min} → {date_max}")
        except Exception as e:
            print(f"  {table}: ERROR — {e}")

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

    required = [T2_CSV, EXTERNAL_PQ, EXTENDED_PQ, GDELT_CSV, IMF_PQ]
    optional = [BLOOMBERG_PQ]
    for f in required:
        if not f.exists():
            print(f"MISSING: {f}")
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
    total += load_parquet_table(con, "external_factors", EXTERNAL_PQ, "External Factors Panel")
    print()
    total += load_parquet_table(con, "extended_factors", EXTENDED_PQ, "Extended Factors Panel")
    print()
    total += load_gdelt(con)
    print()
    total += load_parquet_table(con, "imf_factors", IMF_PQ, "IMF Factors Panel")
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
