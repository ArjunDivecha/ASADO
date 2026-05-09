"""
=============================================================================
SCRIPT NAME: scripts/strategy/analogs/build_returns.py
=============================================================================

INPUT FILES:
- Data/asado.duckdb :: t2_master                — already loaded canonical T2
                                                  panel; we slice variable='1MRet'.
- Data/T2 Master.xlsx :: sheet '1MRet'          — fallback if t2_master is empty
                                                  or stale.

OUTPUT FILES:
- Data/asado.duckdb :: country_returns_monthly  — (date, country, mtd_return_usd)
                                                  Tidy, one row per (date, country).

VERSION: 1.0
LAST UPDATED: 2026-04-19
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
Stage-0 loader for the World-State Analog strategy. Materializes the monthly
MSCI country price-return USD series ('1MRet') into a dedicated DuckDB table.

DATE CONVENTION (locked):
  Row dated YYYY-MM-01 carries the return earned during that calendar month.
  Sanity fixture: 1MRet[2008-10-01, 'U.S.'] ≈ -0.1680 (GFC October).

  In the backtest harness, a decision date t = end of month M reads its
  realized forward return r_{t+1}(c) from the row dated (M+1)-01.

DEPENDENCIES:
- duckdb, pandas, openpyxl

USAGE:
  python scripts/strategy/analogs/build_returns.py            # normal run
  python scripts/strategy/analogs/build_returns.py --from-xlsx  # bypass t2_master, re-read Excel
  python scripts/strategy/analogs/build_returns.py --check    # verify existing table only

NOTES:
- v1 uses 1MRet (price return). PRD §4.2 originally referenced 1MTR (total
  return); user direction 2026-04-19 corrected to 1MRet.
- 1MTR is also available in T2 Master if a future phase wants total return.
- Drops trailing rows where every country is NaN (incomplete current month).
=============================================================================
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.strategy.analogs import config as C  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

CONVENTION_FIXTURE = {
    "date": pd.Timestamp("2008-10-01"),
    "country": "U.S.",
    "expected": -0.168,
    "tolerance": 0.005,
}


def load_from_t2_master(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Pull 1MRet from the canonical t2_master table inside asado.duckdb."""
    df = con.execute(
        """
        SELECT date, country, value AS mtd_return_usd
        FROM t2_master
        WHERE variable = '1MRet'
          AND value IS NOT NULL
        """
    ).df()
    df["date"] = pd.to_datetime(df["date"])
    return df


def load_from_xlsx(xlsx_path: Path) -> pd.DataFrame:
    """Re-read T2 Master.xlsx sheet '1MRet' (used when t2_master is unavailable)."""
    wide = pd.read_excel(xlsx_path, sheet_name="1MRet")
    wide = wide.rename(columns={wide.columns[0]: "date"})
    wide["date"] = pd.to_datetime(wide["date"])
    long = wide.melt(id_vars=["date"], var_name="country", value_name="mtd_return_usd")
    long = long.dropna(subset=["mtd_return_usd"])
    return long


def drop_incomplete_tail(df: pd.DataFrame, expected_n_countries: int) -> pd.DataFrame:
    """Remove trailing months where coverage is too thin to be a real observation.

    The current calendar month sometimes appears in 1MRet with all-NaN cells
    until month-end values are stamped in. We strip those after melt+dropna by
    requiring a month to have at least half the universe reporting.
    """
    counts = df.groupby("date").size().sort_index()
    threshold = max(5, expected_n_countries // 2)
    last_real = counts[counts >= threshold].index.max()
    if pd.isna(last_real):
        return df.iloc[0:0]
    return df[df["date"] <= last_real].copy()


def assert_convention(df: pd.DataFrame) -> None:
    fix = CONVENTION_FIXTURE
    row = df[(df["date"] == fix["date"]) & (df["country"] == fix["country"])]
    if row.empty:
        raise AssertionError(
            f"Convention fixture missing: no row for {fix['country']} on {fix['date'].date()}"
        )
    actual = float(row["mtd_return_usd"].iloc[0])
    if abs(actual - fix["expected"]) > fix["tolerance"]:
        raise AssertionError(
            f"Convention fixture failed: {fix['country']} {fix['date'].date()} "
            f"expected ≈ {fix['expected']}, got {actual:.4f}"
        )
    logger.info(
        "Convention fixture OK: %s on %s = %.4f (expected ≈ %.3f)",
        fix["country"], fix["date"].date(), actual, fix["expected"],
    )


def assert_universe(df: pd.DataFrame) -> None:
    have = set(df["country"].unique())
    want = set(C.T2_COUNTRIES)
    missing = sorted(want - have)
    extra = sorted(have - want)
    if missing:
        raise AssertionError(f"1MRet missing T2 countries: {missing}")
    if extra:
        logger.warning("1MRet has countries not in T2 universe (will keep): %s", extra)


def write_table(con: duckdb.DuckDBPyConnection, df: pd.DataFrame) -> None:
    con.execute(f"DROP TABLE IF EXISTS {C.RETURNS_TABLE}")
    con.execute(
        f"""
        CREATE TABLE {C.RETURNS_TABLE} (
            date              DATE     NOT NULL,
            country           VARCHAR  NOT NULL,
            mtd_return_usd    DOUBLE   NOT NULL,
            PRIMARY KEY (date, country)
        )
        """
    )
    con.register("df_in", df)
    con.execute(
        f"""
        INSERT INTO {C.RETURNS_TABLE}
        SELECT CAST(date AS DATE), country, mtd_return_usd
        FROM df_in
        """
    )
    con.unregister("df_in")


def summarize(con: duckdb.DuckDBPyConnection) -> None:
    summary = con.execute(
        f"""
        SELECT MIN(date) AS first_date,
               MAX(date) AS last_date,
               COUNT(*) AS rows,
               COUNT(DISTINCT date) AS months,
               COUNT(DISTINCT country) AS countries
        FROM {C.RETURNS_TABLE}
        """
    ).fetchone()
    logger.info(
        "country_returns_monthly: rows=%s, months=%s, countries=%s, range=%s..%s",
        summary[2], summary[3], summary[4], summary[0], summary[1],
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from-xlsx", action="store_true",
                    help="Bypass t2_master and re-read T2 Master.xlsx")
    ap.add_argument("--check", action="store_true",
                    help="Only verify existing country_returns_monthly")
    args = ap.parse_args()

    C.ensure_dirs()

    if args.check:
        with duckdb.connect(str(C.DUCKDB_PATH), read_only=True) as con:
            df = con.execute(f"SELECT date, country, mtd_return_usd FROM {C.RETURNS_TABLE}").df()
        df["date"] = pd.to_datetime(df["date"])
        assert_convention(df)
        assert_universe(df)
        with duckdb.connect(str(C.DUCKDB_PATH), read_only=True) as con:
            summarize(con)
        return 0

    with duckdb.connect(str(C.DUCKDB_PATH)) as con:
        if args.from_xlsx:
            logger.info("Loading 1MRet from %s", C.T2_MASTER_XLSX)
            df = load_from_xlsx(C.T2_MASTER_XLSX)
        else:
            logger.info("Loading 1MRet from t2_master in %s", C.DUCKDB_PATH)
            df = load_from_t2_master(con)
            if df.empty:
                logger.warning("t2_master empty for 1MRet; falling back to Excel")
                df = load_from_xlsx(C.T2_MASTER_XLSX)

        df = drop_incomplete_tail(df, expected_n_countries=len(C.T2_COUNTRIES))
        assert_universe(df)
        assert_convention(df)
        write_table(con, df)
        summarize(con)

    logger.info("Done. Build timestamp: %s", datetime.now().isoformat(timespec="seconds"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
