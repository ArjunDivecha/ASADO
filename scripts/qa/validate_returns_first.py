#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: validate_returns_first.py
=============================================================================

INPUT FILES:
- Data/asado.duckdb: live ASADO warehouse
- scripts/asado_mcp_server.py: MCP tool registry (introspected via FastMCP)

OUTPUT FILES:
- stdout: machine-readable JSON summary of all checks
- exit code: 0 if all checks pass, 1 otherwise

VERSION: 1.0
LAST UPDATED: 2026-05-12

DESCRIPTION:
QA regression for the Returns-First Source Of Truth layer (PRD §10 Phase D).
Verifies that return tables exist, country/factor return surfaces are populated,
the optimizer cycle guardrail holds (no optimizer-output sources leak into
feature_panel / unified_panel), and the deterministic MCP return tools return
non-empty rows for known canonical inputs.

USAGE:
  ./venv/bin/python scripts/qa/validate_returns_first.py
  ./venv/bin/python scripts/qa/validate_returns_first.py --skip-mcp
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

CODE_DIR = Path(__file__).resolve().parent.parent.parent
BASE_DIR = Path(
    os.environ.get("ASADO_BASE_DIR") or CODE_DIR
).expanduser().resolve()
# Code imports must come from the current checkout (CODE_DIR), not ASADO_BASE_DIR.
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

import duckdb

DB_PATH = BASE_DIR / "Data" / "asado.duckdb"

OPTIMIZER_SOURCES = {
    "econ_optimizer",
    "t2_optimizer",
    "gdelt_optimizer",
    "t2_optimizer_daily",
    "gdelt_optimizer_daily",
}
FACTOR_RETURN_MONTHLY_SOURCES = {"econ_optimizer", "t2_optimizer", "gdelt_optimizer"}
FACTOR_RETURN_DAILY_SOURCES = {"t2_optimizer_daily", "gdelt_optimizer_daily"}
COUNTRY_RETURN_MONTHLY = {"1MRet", "3MRet", "6MRet", "9MRet", "12MRet"}
COUNTRY_RETURN_DAILY = {"1DRet", "5DRet", "20DRet", "60DRet", "120DRet"}


def _check(label: str, ok: bool, detail: Any = None) -> Dict[str, Any]:
    return {"name": label, "ok": bool(ok), "detail": detail}


def run_db_checks(con: duckdb.DuckDBPyConnection) -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []
    tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}

    # 1. Return tables exist and are non-empty
    for tbl in ("factor_returns", "factor_returns_daily", "factor_top20_membership", "country_factor_attribution"):
        if tbl in tables:
            n = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
            checks.append(_check(f"table {tbl} non-empty", n > 0, {"row_count": int(n)}))
        else:
            checks.append(_check(f"table {tbl} non-empty", False, {"error": "missing"}))

    # 2a. Monthly country return vars in feature_panel (t2)
    df_m = con.execute(
        """
        SELECT variable, COUNT(DISTINCT country) AS countries, MIN(date) mn, MAX(date) mx
        FROM feature_panel
        WHERE source = 't2' AND variable IN ('1MRet','3MRet','6MRet','9MRet','12MRet')
        GROUP BY variable
        """
    ).fetchdf()
    found_m = set(df_m["variable"].tolist())
    missing_m = sorted(COUNTRY_RETURN_MONTHLY - found_m)
    checks.append(_check(
        "monthly country returns present (T2, all 5 horizons)",
        not missing_m and all(df_m["countries"] >= 34),
        {"found": sorted(found_m), "missing": missing_m, "sample": df_m.to_dict("records")},
    ))

    # 2b. Daily country return vars in t2_factors_daily
    df_d = con.execute(
        """
        SELECT variable, COUNT(DISTINCT country) AS countries, MIN(date) mn, MAX(date) mx
        FROM t2_factors_daily
        WHERE variable IN ('1DRet','5DRet','20DRet','60DRet','120DRet')
        GROUP BY variable
        """
    ).fetchdf()
    found_d = set(df_d["variable"].tolist())
    missing_d = sorted(COUNTRY_RETURN_DAILY - found_d)
    checks.append(_check(
        "daily country returns present (T2, all 5 horizons)",
        not missing_d and all(df_d["countries"] >= 34),
        {"found": sorted(found_d), "missing": missing_d, "sample": df_d.to_dict("records")},
    ))

    # 3. factor_returns has all three monthly sources
    fr_src = {
        row[0] for row in con.execute(
            "SELECT DISTINCT source FROM factor_returns"
        ).fetchall()
    }
    missing_fr = sorted(FACTOR_RETURN_MONTHLY_SOURCES - fr_src)
    checks.append(_check(
        "factor_returns has econ/t2/gdelt optimizer sources",
        not missing_fr,
        {"found": sorted(fr_src), "missing": missing_fr},
    ))

    # 4. factor_returns_daily has both daily sources
    frd_src = {
        row[0] for row in con.execute(
            "SELECT DISTINCT source FROM factor_returns_daily"
        ).fetchall()
    }
    missing_frd = sorted(FACTOR_RETURN_DAILY_SOURCES - frd_src)
    checks.append(_check(
        "factor_returns_daily has t2/gdelt daily optimizer sources",
        not missing_frd,
        {"found": sorted(frd_src), "missing": missing_frd},
    ))

    # 5. country_factor_attribution joins to factor_returns (contribution = weight * factor_return)
    row = con.execute(
        """
        SELECT COUNT(*) AS n,
               MAX(ABS(contribution - weight * factor_return)) AS max_err
        FROM country_factor_attribution
        WHERE weight IS NOT NULL AND factor_return IS NOT NULL AND contribution IS NOT NULL
        """
    ).fetchone()
    n_attrib, max_err = (row[0] or 0), float(row[1] or 0.0)
    checks.append(_check(
        "country_factor_attribution joins consistently with factor_returns",
        n_attrib > 0 and max_err < 1e-6,
        {"row_count": int(n_attrib), "max_abs_residual": max_err},
    ))

    # 6. Cycle guardrail — no optimizer-output sources in feature_panel / unified_panel
    bad_fp = con.execute(
        """
        SELECT source, COUNT(*) AS n
        FROM feature_panel
        WHERE source IN ('econ_optimizer','t2_optimizer','gdelt_optimizer',
                         't2_optimizer_daily','gdelt_optimizer_daily')
        GROUP BY source
        """
    ).fetchdf()
    bad_up = con.execute(
        """
        SELECT source, COUNT(*) AS n
        FROM unified_panel
        WHERE source IN ('econ_optimizer','t2_optimizer','gdelt_optimizer',
                         't2_optimizer_daily','gdelt_optimizer_daily')
        GROUP BY source
        """
    ).fetchdf()
    cycle_ok = bad_fp.empty and bad_up.empty
    checks.append(_check(
        "cycle guardrail: no optimizer return sources in feature_panel / unified_panel",
        cycle_ok,
        {
            "feature_panel_violations": bad_fp.to_dict("records"),
            "unified_panel_violations": bad_up.to_dict("records"),
        },
    ))

    # 7. GDELT 1MRet / 1DRet are aliases of T2 (verify bit-exact identity on overlap)
    alias_m = con.execute(
        """
        WITH t2 AS (SELECT date, country, value AS t2v FROM feature_panel
                    WHERE source='t2' AND variable='1MRet'),
             g  AS (SELECT date, country, value AS gv FROM feature_panel
                    WHERE source='gdelt' AND variable='1MRet')
        SELECT COUNT(*) AS n_overlap,
               SUM(CASE WHEN ABS(t2v - gv) < 1e-9 THEN 1 ELSE 0 END) AS n_match
        FROM t2 JOIN g USING(date, country)
        """
    ).fetchone()
    alias_d = con.execute(
        """
        WITH t2 AS (SELECT date, country, value AS t2v FROM t2_factors_daily WHERE variable='1DRet'),
             g  AS (SELECT date, country, value AS gv FROM gdelt_factors_daily WHERE variable='1DRet')
        SELECT COUNT(*) AS n_overlap,
               SUM(CASE WHEN ABS(t2v - gv) < 1e-9 THEN 1 ELSE 0 END) AS n_match
        FROM t2 JOIN g USING(date, country)
        """
    ).fetchone()
    monthly_alias_ok = alias_m[0] > 0 and alias_m[0] == alias_m[1]
    daily_alias_ok = alias_d[0] > 0 and alias_d[0] == alias_d[1]
    checks.append(_check(
        "GDELT-labeled 1MRet / 1DRet are bit-exact aliases of T2 (no second country return source)",
        monthly_alias_ok and daily_alias_ok,
        {
            "monthly": {"overlap": int(alias_m[0]), "exact_match": int(alias_m[1] or 0)},
            "daily": {"overlap": int(alias_d[0]), "exact_match": int(alias_d[1] or 0)},
        },
    ))

    return checks


def run_mcp_checks() -> List[Dict[str, Any]]:
    import scripts.asado_mcp_server as srv
    srv.BASE_DIR = BASE_DIR
    tools = srv.mcp._tool_manager._tools

    def call(name: str, **kw):
        return tools[name].fn(**kw)

    checks: List[Dict[str, Any]] = []

    r = call("country_returns", countries="all", horizon="1MRet", latest_only=True,
             rank="best", max_rows=5)
    checks.append(_check(
        "country_returns(rank='best', 1MRet) returns rows",
        r["result"]["row_count"] > 0,
        {"latest_date": r.get("latest_date"), "row_count": r["result"]["row_count"]},
    ))

    r = call("factor_return_series", factors="all", frequency="monthly", rank="best", max_rows=5)
    checks.append(_check(
        "factor_return_series(monthly, best) returns rows",
        r["result"]["row_count"] > 0,
        {"source": r.get("source"), "latest_date": r.get("latest_date"), "row_count": r["result"]["row_count"]},
    ))

    r = call("factor_return_series", factors="all", frequency="daily", rank="best", max_rows=5)
    checks.append(_check(
        "factor_return_series(daily, best) returns rows",
        r["result"]["row_count"] > 0,
        {"source": r.get("source"), "row_count": r["result"]["row_count"]},
    ))

    r = call("country_factor_attribution", country="Brazil", date="latest", max_rows=5)
    checks.append(_check(
        "country_factor_attribution(Brazil, latest) returns rows",
        r["result"]["row_count"] > 0,
        {"date": r.get("date"), "row_count": r["result"]["row_count"]},
    ))

    r = call("return_leaders", scope="country", direction="best", horizon="1MRet", max_rows=5)
    checks.append(_check(
        "return_leaders(country, best, 1MRet) returns rows",
        r["result"]["row_count"] > 0,
        {"row_count": r["result"]["row_count"]},
    ))

    r = call("return_leaders", scope="factor", direction="best", max_rows=5)
    checks.append(_check(
        "return_leaders(factor, best) returns rows",
        r["result"]["row_count"] > 0,
        {"row_count": r["result"]["row_count"]},
    ))

    r = call("event_window", country="Turkey", date="2018-08-13",
             days_before=5, days_after=5, max_rows=50)
    rs = r.get("return_summary", {})
    checks.append(_check(
        "event_window(Turkey, 2018-08-13) includes return_summary block",
        bool(rs)
        and rs.get("event_window_return_simple_sum") is not None
        and rs.get("factor_return_leaders", {}).get("row_count", 0) > 0,
        {
            "pre": rs.get("pre_event_return_simple_sum"),
            "post": rs.get("post_event_return_simple_sum"),
            "window": rs.get("event_window_return_simple_sum"),
            "leaders": rs.get("factor_return_leaders", {}).get("row_count"),
            "laggards": rs.get("factor_return_laggards", {}).get("row_count"),
        },
    ))

    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate Returns-First Source Of Truth layer")
    parser.add_argument("--skip-mcp", action="store_true", help="Skip MCP tool checks (DB-only)")
    args = parser.parse_args()

    if not DB_PATH.exists():
        print(json.dumps({"ok": False, "error": f"DuckDB not found at {DB_PATH}"}, indent=2))
        raise SystemExit(1)

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        results = run_db_checks(con)
    finally:
        con.close()

    if not args.skip_mcp:
        results.extend(run_mcp_checks())

    all_ok = all(c["ok"] for c in results)
    n_pass = sum(1 for c in results if c["ok"])
    n_total = len(results)
    summary = {
        "ok": all_ok,
        "checks_passed": n_pass,
        "checks_total": n_total,
        "checks": results,
    }
    print(json.dumps(summary, indent=2, default=str))
    raise SystemExit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
