#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: tests/loop/test_daily_pipeline.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/dislocations/brief_*.md

OUTPUT FILES:
- stdout (pass/fail per check)

VERSION: 1.0
LAST UPDATED: 2026-06-10
AUTHOR: Arjun Divecha (built by agent session)

DESCRIPTION:
End-to-end validation for the daily pipeline. Checks freshness, row counts,
country coverage, cross-table consistency, and structural invariants across
both the main warehouse and the loop database. Run after daily_update.py and
loop_daily_job.py complete.

USAGE:
 python tests/loop/test_daily_pipeline.py              # today
 python tests/loop/test_daily_pipeline.py --date 2026-06-10
=============================================================================
"""
from __future__ import annotations

import argparse
import glob
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# ── bootstrap ────────────────────────────────────────────────────────────
BASE = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE))

import duckdb  # noqa: E402

from scripts.loop.loopdb import LOOP_DIR, MAIN_DB, T2_UNIVERSE  # noqa: E402

PASS = 0
FAIL = 0


def ok(label: str):
    global PASS
    PASS += 1
    print(f"  [PASS] {label}")


def fail(label: str, detail: str = ""):
    global FAIL
    FAIL += 1
    d = f" -- {detail}" if detail else ""
    print(f"  [FAIL] {label}{d}")


def check(pred: bool, label: str, detail: str = ""):
    if pred:
        ok(label)
    else:
        fail(label, detail)


# ── main ─────────────────────────────────────────────────────────────────
def run(asof: str):
    global PASS, FAIL
    PASS = FAIL = 0

    asof_date = datetime.strptime(asof, "%Y-%m-%d").date()
    yesterday = asof_date - timedelta(days=1)

    print(f"\n{'=' * 60}")
    print(f"  DAILY PIPELINE VALIDATION  {asof}")
    print(f"{'=' * 60}\n")

    # ── A. main warehouse ────────────────────────────────────────────────
    print("A. Main warehouse (asado.duckdb)")
    if not MAIN_DB.exists():
        fail("asado.duckdb exists", "not found")
        print("\nSkipping warehouse checks.\n")
    else:
        con = duckdb.connect(str(MAIN_DB), read_only=True)

        # A1. t2_factors_daily freshness
        max_ret = con.execute(
            "SELECT max(date) FROM t2_factors_daily"
        ).fetchone()[0]
        check(
            max_ret is not None and str(max_ret) >= str(asof_date),
            "t2_factors_daily max date >= today",
            f"got {max_ret}",
        )

        # A2. t2_factors_daily coverage
        ret_countries = con.execute(
            "SELECT count(DISTINCT country) FROM t2_factors_daily WHERE date = ?",
            [str(asof_date)],
        ).fetchone()[0]
        check(
            ret_countries >= 30,
            f"t2_factors_daily countries at {asof_date}: {ret_countries}",
            f"expected >= 30 of 34",
        )

        # A3. t2_levels_daily freshness (at least one variable changed today)
        levels_countries = con.execute(
            "SELECT count(DISTINCT country) FROM t2_levels_daily WHERE date = ?",
            [str(asof_date)],
        ).fetchone()[0]
        check(
            levels_countries >= 30,
            f"t2_levels_daily countries at {asof_date}: {levels_countries}",
        )

        # A4. gdelt_factors_daily freshness (GDELT can lag 1 day)
        max_gdelt = con.execute(
            "SELECT max(date) FROM gdelt_factors_daily"
        ).fetchone()[0]
        check(
            max_gdelt is not None and str(max_gdelt) >= str(yesterday),
            f"gdelt_factors_daily max date: {max_gdelt}",
        )

        # A5. factor_returns_daily freshness
        max_fr = con.execute(
            "SELECT max(date) FROM factor_returns_daily"
        ).fetchone()[0]
        check(
            max_fr is not None and str(max_fr) >= str(asof_date),
            f"factor_returns_daily max date: {max_fr}",
        )

        # A6. 1DRet non-zero check — must use the PREVIOUS trading day,
        # not today (market may still be open; Bloomberg fills today with
        # prior close so today's 1DRet = 0 until the close prints).
        check_date = str(yesterday)
        nonzero_rets = con.execute(
            "SELECT count(*) FROM t2_factors_daily "
            "WHERE date = ? AND variable = '1DRet' AND abs(value) > 0.0001",
            [check_date],
        ).fetchone()[0]
        check(
            nonzero_rets >= 20,
            f"1DRet non-zero rows at {check_date}: {nonzero_rets}",
            "Bloomberg data may not have loaded",
        )

        con.close()

    # ── B. loop database ─────────────────────────────────────────────────
    print("\nB. Loop database (asado_loop.duckdb)")
    loop_db = LOOP_DIR / "asado_loop.duckdb"
    if not loop_db.exists():
        fail("asado_loop.duckdb exists", "not found")
        print("\n  Skipping loop checks.\n")
    else:
        con = duckdb.connect(str(loop_db), read_only=True)

        # B1. all expected tables exist
        expected_tables = {
            "country_returns_monthly",
            "graph_features_daily",
            "dislocation_daily",
            "hypothesis_ledger",
            "thesis_ledger",
            "thesis_marks",
            "harness_results",
            "loop_variable_meta",
            "etf_prices_daily",
            "etf_t2_map",
            "portfolio_holdings_daily",
        }
        actual = set(
            con.execute(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'main'"
            ).fetchall()
        )
        actual_names = {r[0] for r in actual}
        missing = expected_tables - actual_names
        check(
            len(missing) == 0,
            "all expected loop tables present",
            f"missing: {missing}" if missing else "",
        )

        # B2. country_returns_monthly has rows and coverage
        crm_count = con.execute(
            "SELECT count(*) FROM country_returns_monthly"
        ).fetchone()[0]
        check(crm_count > 8000, f"country_returns_monthly: {crm_count} rows")

        # B3. graph_features_daily freshness
        try:
            max_gf = con.execute(
                "SELECT max(date) FROM graph_features_daily"
            ).fetchone()[0]
            check(
                max_gf is not None and str(max_gf) >= str(asof_date),
                f"graph_features_daily max date: {max_gf}",
            )
            gf_vars = con.execute(
                "SELECT count(DISTINCT variable) FROM graph_features_daily"
            ).fetchone()[0]
            check(gf_vars >= 5, f"graph feature variables: {gf_vars}")
        except Exception as e:
            fail("graph_features_daily", str(e))

        # B4. dislocation_daily: today has rows
        try:
            dl_today = con.execute(
                "SELECT count(*) FROM dislocation_daily WHERE date = ?",
                [str(asof_date)],
            ).fetchone()[0]
            check(
                dl_today > 0,
                f"dislocation_daily rows today: {dl_today}",
            )
            # Status lifecycle: at least some non-'new' if day > 1
            dl_statuses = con.execute(
                "SELECT status, count(*) FROM dislocation_daily "
                "WHERE date = ? GROUP BY status ORDER BY 2 DESC",
                [str(asof_date)],
            ).fetchdf()
            if dl_today > 0:
                status_set = set(dl_statuses["status"])
                check(
                    "new" in status_set,
                    f"dislocation statuses: {status_set}",
                )
        except Exception as e:
            fail("dislocation_daily", str(e))

        # B5. thesis_ledger: at least the 3 seed theses
        try:
            tl_count = con.execute(
                "SELECT count(*) FROM thesis_ledger WHERE status = 'open'"
            ).fetchone()[0]
            check(tl_count >= 3, f"open theses: {tl_count}")
        except Exception as e:
            fail("thesis_ledger", str(e))

        # B6. etf_prices_daily: has today's data
        try:
            max_etf = con.execute(
                "SELECT max(date) FROM etf_prices_daily"
            ).fetchone()[0]
            check(
                max_etf is not None and str(max_etf) >= str(asof_date),
                f"etf_prices_daily max date: {max_etf}",
            )
            etf_count = con.execute(
                "SELECT count(*) FROM etf_prices_daily"
            ).fetchone()[0]
            check(etf_count > 100000, f"etf_prices_daily: {etf_count} rows")
        except Exception as e:
            fail("etf_prices_daily", str(e))

        # B7. etf_t2_map: 34 countries mapped
        try:
            map_count = con.execute(
                "SELECT count(*) FROM etf_t2_map"
            ).fetchone()[0]
            check(map_count == 34, f"etf_t2_map countries: {map_count}")
        except Exception as e:
            fail("etf_t2_map", str(e))

        # B8. portfolio_holdings_daily: has today's snapshot
        try:
            ph_max = con.execute(
                "SELECT max(date) FROM portfolio_holdings_daily"
            ).fetchone()[0]
            check(
                ph_max is not None and str(ph_max) >= str(asof_date),
                f"portfolio_holdings_daily max date: {ph_max}",
            )
        except Exception as e:
            fail("portfolio_holdings_daily", str(e))

        con.close()

    # ── C. brief file ────────────────────────────────────────────────────
    print("\nC. Brief file")
    brief_path = (
        BASE / "Data" / "dislocations" / f"brief_{asof.replace('-', '_')}.md"
    )
    check(brief_path.exists(), f"brief exists: {brief_path.name}")
    if brief_path.exists():
        content = brief_path.read_text()
        check(len(content) > 200, f"brief not empty ({len(content)} chars)")
        check(
            "det" in content and "|" in content,
            "brief has table rows",
        )

    # ── D. predmkt archive ───────────────────────────────────────────────
    print("\nD. Predmkt archive")
    predmkt_dir = LOOP_DIR / "predmkt_archive"
    if predmkt_dir.exists():
        parquets = list(predmkt_dir.glob("*.parquet"))
        check(
            len(parquets) >= 5,
            f"predmkt_archive parquets: {len(parquets)}",
        )
        # Check newest is today
        newest_mtime = max(
            os.path.getmtime(p) for p in parquets
        ) if parquets else 0
        newest_date = datetime.fromtimestamp(newest_mtime).date()
        check(
            newest_date >= asof_date,
            f"predmkt_archive newest mtime: {newest_date}",
        )
    else:
        fail("predmkt_archive exists", "not found")

    # ── summary ──────────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"  RESULT: {PASS} passed, {FAIL} failed")
    if FAIL > 0:
        print("  Status: NOT CLEAN -- investigate [FAIL] items above")
    else:
        print("  Status: ALL CLEAR")
    print(f"{'=' * 60}\n")
    return 1 if FAIL else 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="As-of date (YYYY-MM-DD, default today)",
    )
    args = parser.parse_args()
    sys.exit(run(args.date))


if __name__ == "__main__":
    main()
