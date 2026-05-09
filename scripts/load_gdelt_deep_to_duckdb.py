"""
=============================================================================
SCRIPT NAME: scripts/load_gdelt_deep_to_duckdb.py
=============================================================================

INPUT FILES:
- Data/processed/gdelt_deep_panel.parquet   — produced by collect_gdelt_deep.py

OUTPUT FILES:
- Data/asado.duckdb :: gdelt_deep_factors   — raw treated Deep features
    (date, country, value, variable, source) with 1,086 vars × 34 countries
    × 133 months ≈ 4.8M rows. Indexed on (country, date) and (variable).

VERSION: 1.0
LAST UPDATED: 2026-04-27
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
Loads the tidy Deep panel into DuckDB as a sibling table to gdelt_panel.

Per the warehouse-ingest plan in docs/gdelt_deep_ingest_plan.md, this stage:
  - Drops and recreates the gdelt_deep_factors table from the parquet.
  - Adds (country, date) and variable indexes.
  - Does NOT modify the feature_panel view. The view stays unchanged
    until the normalization decision (next stage) lands the _CS variants.

DEPENDENCIES:
- duckdb, pyarrow

USAGE:
  python scripts/load_gdelt_deep_to_duckdb.py            # rebuild table
  python scripts/load_gdelt_deep_to_duckdb.py --check    # summarize existing table
=============================================================================
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import duckdb

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "Data"
DUCKDB_PATH = DATA_DIR / "asado.duckdb"
DEEP_PARQUET = DATA_DIR / "processed" / "gdelt_deep_panel.parquet"
TABLE = "gdelt_deep_factors"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def summarize(con: duckdb.DuckDBPyConnection) -> None:
    n_rows = con.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0]
    n_vars = con.execute(f"SELECT COUNT(DISTINCT variable) FROM {TABLE}").fetchone()[0]
    n_countries = con.execute(f"SELECT COUNT(DISTINCT country) FROM {TABLE}").fetchone()[0]
    by_source = con.execute(
        f"SELECT source, COUNT(DISTINCT variable) AS n_vars, COUNT(*) AS n_rows "
        f"FROM {TABLE} GROUP BY source ORDER BY source"
    ).df()
    date_min, date_max = con.execute(
        f"SELECT MIN(date), MAX(date) FROM {TABLE}"
    ).fetchone()
    logger.info("%s: %d rows, %d variables, %d countries", TABLE, n_rows, n_vars, n_countries)
    logger.info("date range: %s → %s", date_min, date_max)
    logger.info("by source:\n%s", by_source.to_string())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="Summarize existing table without rebuilding.")
    ap.add_argument("--force", action="store_true",
                    help="Rebuild even if table is already up to date with parquet mtime.")
    args = ap.parse_args()

    if not DUCKDB_PATH.exists():
        logger.error("DuckDB not found: %s", DUCKDB_PATH)
        return 2

    if args.check:
        with duckdb.connect(str(DUCKDB_PATH), read_only=True) as con:
            summarize(con)
        return 0

    if not DEEP_PARQUET.exists():
        logger.error("Source parquet missing: %s", DEEP_PARQUET)
        logger.error("Run scripts/collect_gdelt_deep.py first.")
        return 2

    # Skip if the table is already loaded from a parquet that hasn't changed.
    # Compare parquet mtime against the DuckDB file mtime — if the duck file
    # is newer than the parquet AND the table already exists with rows that
    # match the parquet's max date, we can safely skip.
    if not args.force:
        try:
            with duckdb.connect(str(DUCKDB_PATH), read_only=True) as con:
                exists = con.execute(
                    f"SELECT COUNT(*) FROM information_schema.tables "
                    f"WHERE table_name = '{TABLE}'"
                ).fetchone()[0] > 0
                if exists:
                    table_max = con.execute(
                        f"SELECT MAX(date) FROM {TABLE}"
                    ).fetchone()[0]
                    import pyarrow.parquet as pq
                    pq_max = pq.read_table(
                        str(DEEP_PARQUET), columns=["date"]
                    )["date"].to_pandas().max()
                    if table_max is not None and pq_max is not None and \
                       str(table_max) >= str(pq_max):
                        logger.info(
                            "Table %s already up to date with parquet "
                            "(table max=%s, parquet max=%s). Skipping.",
                            TABLE, table_max, pq_max,
                        )
                        return 0
        except Exception as e:
            logger.warning("Up-to-date check failed (%s) — proceeding to rebuild.", e)

    with duckdb.connect(str(DUCKDB_PATH)) as con:
        logger.info("Dropping and rebuilding %s ...", TABLE)
        con.execute(f"DROP TABLE IF EXISTS {TABLE}")
        con.execute(f"""
            CREATE TABLE {TABLE} AS
            SELECT
                CAST(date AS DATE) AS date,
                country,
                value,
                variable,
                source
            FROM read_parquet('{DEEP_PARQUET.as_posix()}')
        """)
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_ctry_date ON {TABLE}(country, date)")
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABLE}_var ON {TABLE}(variable)")
        summarize(con)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
