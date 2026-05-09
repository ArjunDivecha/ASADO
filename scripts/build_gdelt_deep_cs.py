"""
=============================================================================
SCRIPT NAME: scripts/build_gdelt_deep_cs.py
=============================================================================

INPUT FILES:
- Data/asado.duckdb :: gdelt_deep_factors    — raw treated Deep features

OUTPUT FILES:
- Data/asado.duckdb :: gdelt_deep_factors_cs — _CS-treated variants
    Same tidy schema (date, country, value, variable, source).
    Variable names suffixed with _CS, source kept as the parent family
    (gdelt_deep_theme / gdelt_deep_gcam / gdelt_deep_event) so downstream
    consumers can join on source family.

VERSION: 1.0
LAST UPDATED: 2026-04-27
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
Produces cross-sectional z-scored (_CS) variants of the Deep features by
reusing scripts/build_normalized_panel.py::_build_cross_sectional verbatim.

The _CS treatment is per-(variable, source, date): z = (v − mean) / std.
Requires count ≥ 2 and std > 0 within the group; otherwise the row is
dropped (single-country dates and constant cross-sections are excluded).

This is PIT-safe by construction — the denominator uses only the same-date
cross-section, no future data leaks in. Confirmed in the v1 worldstate PIT
audit (docs/strategy/analogs/v1/go_no_go.md §3).

Per the warehouse-ingest plan (docs/gdelt_deep_ingest_plan.md), the result
is stored in its own table — feature_panel is NOT modified. A future
normalization decision will choose how to expose these to consumers.

DEPENDENCIES:
- duckdb, pandas, numpy

USAGE:
  python scripts/build_gdelt_deep_cs.py            # build _CS table
  python scripts/build_gdelt_deep_cs.py --check    # summarize existing table
=============================================================================
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import duckdb
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from scripts.build_normalized_panel import _build_cross_sectional  # noqa: E402

DUCKDB_PATH = BASE_DIR / "Data" / "asado.duckdb"
SOURCE_TABLE = "gdelt_deep_factors"
TARGET_TABLE = "gdelt_deep_factors_cs"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def summarize(con: duckdb.DuckDBPyConnection) -> None:
    n_rows = con.execute(f"SELECT COUNT(*) FROM {TARGET_TABLE}").fetchone()[0]
    n_vars = con.execute(f"SELECT COUNT(DISTINCT variable) FROM {TARGET_TABLE}").fetchone()[0]
    n_countries = con.execute(f"SELECT COUNT(DISTINCT country) FROM {TARGET_TABLE}").fetchone()[0]
    by_source = con.execute(
        f"SELECT source, COUNT(DISTINCT variable) AS n_vars, COUNT(*) AS n_rows "
        f"FROM {TARGET_TABLE} GROUP BY source ORDER BY source"
    ).df()
    date_min, date_max = con.execute(
        f"SELECT MIN(date), MAX(date) FROM {TARGET_TABLE}"
    ).fetchone()
    logger.info("%s: %d rows, %d variables, %d countries", TARGET_TABLE, n_rows, n_vars, n_countries)
    logger.info("date range: %s → %s", date_min, date_max)
    logger.info("by source:\n%s", by_source.to_string())

    sample_var = con.execute(f"""
        SELECT variable, AVG(value) AS mean, STDDEV(value) AS std,
               COUNT(*) AS n
        FROM {TARGET_TABLE}
        WHERE variable LIKE 'theme_PROTEST_share_CS'
        GROUP BY variable
    """).df()
    if not sample_var.empty:
        logger.info("sanity (cross-sectional z scores ≈ mean 0, std 1):\n%s",
                    sample_var.to_string())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="Summarize existing table without rebuilding.")
    ap.add_argument("--force", action="store_true",
                    help="Rebuild even if target table is already up to date "
                         "with source max date.")
    args = ap.parse_args()

    if not DUCKDB_PATH.exists():
        logger.error("DuckDB not found: %s", DUCKDB_PATH)
        return 2

    if args.check:
        with duckdb.connect(str(DUCKDB_PATH), read_only=True) as con:
            summarize(con)
        return 0

    # Skip if target table already covers the source's full date range.
    if not args.force:
        try:
            with duckdb.connect(str(DUCKDB_PATH), read_only=True) as con:
                target_exists = con.execute(
                    f"SELECT COUNT(*) FROM information_schema.tables "
                    f"WHERE table_name = '{TARGET_TABLE}'"
                ).fetchone()[0] > 0
                if target_exists:
                    src_max = con.execute(
                        f"SELECT MAX(date) FROM {SOURCE_TABLE}"
                    ).fetchone()[0]
                    tgt_max = con.execute(
                        f"SELECT MAX(date) FROM {TARGET_TABLE}"
                    ).fetchone()[0]
                    if src_max is not None and tgt_max is not None and \
                       str(tgt_max) >= str(src_max):
                        logger.info(
                            "%s already up to date with %s "
                            "(target max=%s, source max=%s). Skipping.",
                            TARGET_TABLE, SOURCE_TABLE, tgt_max, src_max,
                        )
                        return 0
        except Exception as e:
            logger.warning("Up-to-date check failed (%s) — proceeding to rebuild.", e)

    with duckdb.connect(str(DUCKDB_PATH)) as con:
        logger.info("Reading %s ...", SOURCE_TABLE)
        panel = con.execute(
            f"SELECT date, country, value, variable, source FROM {SOURCE_TABLE}"
        ).df()
        logger.info("Source rows: %d", len(panel))

        logger.info("Building _CS variants ...")
        cs = _build_cross_sectional(panel)
        if cs.empty:
            logger.error("Cross-sectional build returned empty.")
            return 3

        # Keep the same canonical 5 columns; the helper adds metadata cols.
        cs = cs[["date", "country", "value", "variable", "source"]].copy()
        cs["date"] = pd.to_datetime(cs["date"]).dt.date
        cs["value"] = pd.to_numeric(cs["value"], errors="coerce")
        cs = cs.dropna(subset=["value"]).reset_index(drop=True)

        logger.info("Writing %s (%d rows) ...", TARGET_TABLE, len(cs))
        con.execute(f"DROP TABLE IF EXISTS {TARGET_TABLE}")
        con.register("cs_df", cs)
        con.execute(f"CREATE TABLE {TARGET_TABLE} AS SELECT * FROM cs_df")
        con.unregister("cs_df")
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_{TARGET_TABLE}_ctry_date "
                    f"ON {TARGET_TABLE}(country, date)")
        con.execute(f"CREATE INDEX IF NOT EXISTS idx_{TARGET_TABLE}_var "
                    f"ON {TARGET_TABLE}(variable)")
        summarize(con)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
