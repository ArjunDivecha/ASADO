#!/usr/bin/env python3
"""
Run a regression suite for the ASADO natural-language query assistant.

This suite exercises planning, execution, and a few graph/data integrity
expectations, then writes JSON and Markdown reports under
Data/reports/query_assistant_suite/.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List

import duckdb
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.build_schema_registry import build_and_write_schema_cache
from scripts.db_bridge import AsadoDB, DB_PATH
from scripts.query_assistant import ASADOQueryAssistant

REPORT_DIR = BASE_DIR / "Data" / "reports" / "query_assistant_suite"
MARKET_SLEEVES = {"ChinaH", "NASDAQ", "US SmallCap"}
SOVEREIGN_EDGE_TYPES = [
    "DATA_AVAILABLE_FROM",
    "EXPORT_EXPOSED_TO",
    "HAS_BANKING_EXPOSURE_TO",
    "HAS_CENTRAL_BANK",
    "HAS_CRISIS_HISTORY",
    "SUBJECT_TO",
    "TRADES_WITH",
]


def _json_ready(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except Exception:
            pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, dict):
        return {str(key): _json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(item) for item in value]
    return value


def _preview_df(df: pd.DataFrame, max_rows: int = 8) -> List[Dict[str, Any]]:
    if df.empty:
        return []
    return _json_ready(df.head(max_rows).to_dict("records"))


def _has_any_column(df: pd.DataFrame, names: List[str]) -> bool:
    return any(name in df.columns for name in names)


def _country_values(df: pd.DataFrame) -> List[str]:
    if "country" not in df.columns:
        return []
    return [str(value) for value in df["country"].dropna().tolist()]


def validate_country_column(df: pd.DataFrame, _: Dict[str, Any]) -> List[str]:
    return [] if "country" in df.columns else ["missing required 'country' column"]


def validate_crisis_column(df: pd.DataFrame, _: Dict[str, Any]) -> List[str]:
    return [] if _has_any_column(df, ["crisis", "crisis_name", "event", "event_name"]) else [
        "missing crisis/event column"
    ]


def validate_no_market_sleeves(df: pd.DataFrame, _: Dict[str, Any]) -> List[str]:
    offenders = sorted(MARKET_SLEEVES.intersection(_country_values(df)))
    if not offenders:
        return []
    return [f"unexpected market-sleeve rows present: {', '.join(offenders)}"]


def validate_sanctions_clarification(response: Dict[str, Any], _: Dict[str, Any]) -> List[str]:
    clarification = (response["plan"].get("clarification_question") or "").lower()
    if "ofac" in clarification or "sdn" in clarification:
        return []
    return ["sanctions clarification did not mention OFAC/SDN limitations"]


def validate_latest_gdp_not_forecast(response: Dict[str, Any], _: Dict[str, Any]) -> List[str]:
    rows = response.get("result_df", pd.DataFrame())
    if rows.empty:
        return ["no GDP rows returned"]
    first = rows.iloc[0]
    failures = []
    if pd.Timestamp(first["date"]).date() > datetime.now().date():
        failures.append("latest GDP row is future-dated")
    if str(first.get("source", "")).lower() == "imf_weo":
        failures.append("latest GDP row still came from IMF_WEO")
    return failures


def validate_trailing_pe_is_raw(response: Dict[str, Any], _: Dict[str, Any]) -> List[str]:
    rows = response.get("result_df", pd.DataFrame())
    if rows.empty:
        return ["no trailing PE rows returned"]
    first = rows.iloc[0]
    failures = []
    if str(first.get("variable")) != "Trailing PE":
        failures.append(f"expected raw 'Trailing PE' but got {first.get('variable')}")
    try:
        value = float(first.get("value"))
        if value <= 5.0:
            failures.append(f"expected a raw PE level, got suspiciously low value {value}")
    except Exception:
        failures.append("trailing PE value was not numeric")
    return failures


CASE_VALIDATORS: Dict[str, Callable[..., List[str]]] = {
    "country_column": validate_country_column,
    "crisis_column": validate_crisis_column,
    "no_market_sleeves": validate_no_market_sleeves,
}

SUITE_CASES: List[Dict[str, Any]] = [
    {
        "id": "duckdb_us_gdp_latest",
        "question": "What is the latest US GDP growth?",
        "expected_mode": "duckdb",
        "min_rows": 1,
        "validators": [],
        "response_validator": "latest_gdp_not_forecast",
    },
    {
        "id": "duckdb_bis_credit_gap",
        "question": "Which countries currently have the highest BIS_Credit_GDP_Gap values?",
        "expected_mode": "duckdb",
        "min_rows": 10,
        "validators": ["country_column"],
    },
    {
        "id": "duckdb_japan_trailing_pe_raw",
        "question": "What is Japan's current trailing PE?",
        "expected_mode": "duckdb",
        "min_rows": 1,
        "validators": [],
        "response_validator": "trailing_pe_is_raw",
    },
    {
        "id": "duckdb_trailing_pe",
        "question": "Which countries have the lowest latest Trailing PE_CS values?",
        "expected_mode": "duckdb",
        "min_rows": 10,
        "validators": ["country_column"],
    },
    {
        "id": "duckdb_asean_inflation_group",
        "question": "Show the latest IMF_CPI_Inflation_YoY values for ASEAN countries.",
        "expected_mode": "duckdb",
        "min_rows": 5,
        "validators": ["country_column"],
    },
    {
        "id": "neo4j_oil_exposure",
        "question": "Which countries are most exposed to oil shocks via commodity export exposure?",
        "expected_mode": "neo4j",
        "min_rows": 5,
        "validators": ["country_column", "no_market_sleeves"],
    },
    {
        "id": "neo4j_turkey_crisis_history",
        "question": "What crisis events are in Turkey's crisis history?",
        "expected_mode": "neo4j",
        "min_rows": 1,
        "validators": ["crisis_column"],
    },
    {
        "id": "neo4j_trade_with_australia",
        "question": "Which countries trade most heavily with Australia?",
        "expected_mode": "neo4j",
        "min_rows": 5,
        "validators": ["country_column", "no_market_sleeves"],
    },
    {
        "id": "hybrid_oil_inflation",
        "question": "Show oil-export-exposed countries and their latest IMF_CPI_Inflation_YoY values.",
        "expected_mode": "hybrid",
        "min_rows": 5,
        "validators": ["country_column", "no_market_sleeves"],
    },
    {
        "id": "hybrid_taper_gdp",
        "question": "Show countries with Taper Tantrum crisis history and their latest IMF_WEO_GDP_Growth values.",
        "expected_mode": "hybrid",
        "min_rows": 5,
        "validators": ["country_column", "no_market_sleeves"],
    },
    {
        "id": "clarify_cheapness",
        "question": "Which ones look cheapest right now?",
        "expected_mode": "clarify",
        "preview_only": True,
        "validators": [],
    },
    {
        "id": "clarify_sanctions_targets",
        "question": "Which countries are currently subject to active sanctions programs?",
        "expected_mode": "clarify",
        "preview_only": True,
        "validators": [],
        "response_validator": "sanctions_clarification",
    },
]


def run_case(assistant: ASADOQueryAssistant, case: Dict[str, Any]) -> Dict[str, Any]:
    started = time.time()
    preview_only = bool(case.get("preview_only", False))
    failures: List[str] = []

    try:
        response = assistant.ask(
            case["question"],
            preview_only=preview_only,
            max_rows=int(case.get("max_rows", 50)),
        )
    except Exception as exc:
        return {
            "id": case["id"],
            "question": case["question"],
            "passed": False,
            "failures": [f"execution raised: {exc}"],
            "elapsed_sec": round(time.time() - started, 2),
        }

    actual_mode = response["plan"].get("query_mode") or response.get("mode")
    if actual_mode != case["expected_mode"]:
        failures.append(f"expected mode {case['expected_mode']} but got {actual_mode}")

    row_count = int(response.get("row_count", 0))
    df = response.get("result_df", pd.DataFrame())

    if not preview_only and case["expected_mode"] != "clarify":
        if row_count < int(case.get("min_rows", 1)):
            failures.append(f"expected at least {case['min_rows']} rows but got {row_count}")

        for validator_name in case.get("validators", []):
            validator = CASE_VALIDATORS[validator_name]
            failures.extend(validator(df, case))

    response_validator = case.get("response_validator")
    if response_validator == "sanctions_clarification":
        failures.extend(validate_sanctions_clarification(response, case))
    elif response_validator == "latest_gdp_not_forecast":
        failures.extend(validate_latest_gdp_not_forecast(response, case))
    elif response_validator == "trailing_pe_is_raw":
        failures.extend(validate_trailing_pe_is_raw(response, case))

    return {
        "id": case["id"],
        "question": case["question"],
        "expected_mode": case["expected_mode"],
        "actual_mode": actual_mode,
        "row_count": row_count,
        "warnings": response["plan"].get("warnings", []),
        "preview_only": preview_only,
        "passed": not failures,
        "failures": failures,
        "elapsed_sec": round(time.time() - started, 2),
        "preview_rows": _preview_df(df),
        "clarification_question": response["plan"].get("clarification_question"),
        "executed_queries": response.get("executed_queries", []),
    }


def run_integrity_checks() -> List[Dict[str, Any]]:
    checks: List[Dict[str, Any]] = []

    with AsadoDB() as db:
        role_rows = db.query_graph(
            """
            MATCH (c:Country)
            RETURN c.t2_name AS country, c.graph_role AS graph_role
            ORDER BY country
            """
        )
        role_map = {row["country"]: row.get("graph_role") for row in role_rows}
        missing_role = sorted(country for country, role in role_map.items() if not role)
        bad_roles = []
        if role_map.get("ChinaA") != "sovereign_proxy":
            bad_roles.append(f"ChinaA graph_role={role_map.get('ChinaA')}")
        for country in sorted(MARKET_SLEEVES):
            if role_map.get(country) != "market_sleeve":
                bad_roles.append(f"{country} graph_role={role_map.get(country)}")
        failures = []
        if missing_role:
            failures.append(f"countries missing graph_role: {', '.join(missing_role)}")
        failures.extend(bad_roles)
        checks.append(
            {
                "id": "graph_role_assignment",
                "passed": not failures,
                "failures": failures,
            }
        )

        edge_rows = db.query_graph(
            """
            MATCH (c:Country)-[r]->()
            WHERE c.t2_name IN $market_sleeves
              AND type(r) IN $edge_types
            RETURN c.t2_name AS country, type(r) AS relationship, COUNT(*) AS edge_count
            ORDER BY country, relationship
            """,
            market_sleeves=sorted(MARKET_SLEEVES),
            edge_types=SOVEREIGN_EDGE_TYPES,
        )
        checks.append(
            {
                "id": "market_sleeves_excluded_from_sovereign_edges",
                "passed": len(edge_rows) == 0,
                "failures": [] if not edge_rows else [
                    "market-sleeve sovereign-edge leakage: " + json.dumps(edge_rows)
                ],
            }
        )

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        df = con.execute(
            """
            SELECT country, MAX(date) AS latest_date, MAX(value) AS value
            FROM extended_factors
            WHERE variable = 'OFAC_Sanctioned'
            GROUP BY country
            ORDER BY country
            """
        ).fetchdf()
    finally:
        con.close()

    latest_flag_count = int((df["value"] == 1.0).sum()) if not df.empty else 0
    checks.append(
        {
            "id": "ofac_signal_not_all_zero",
            "passed": latest_flag_count > 0,
            "failures": [] if latest_flag_count > 0 else ["OFAC_Sanctioned has no active country rows"],
            "details": {"latest_flagged_countries": latest_flag_count},
        }
    )

    with AsadoDB() as db:
        ds_rows = db.query_graph(
            """
            MATCH (d:DataSource)
            WHERE d.name IN ['t2', 't2_raw', 'gdelt', 'bloomberg']
            RETURN collect(d.name) AS names
            """
        )
        present = set(ds_rows[0]["names"]) if ds_rows else set()
        required = {"t2", "t2_raw", "gdelt", "bloomberg"}
        missing = sorted(required - present)
        checks.append(
            {
                "id": "core_datasources_present",
                "passed": not missing,
                "failures": [] if not missing else [f"missing data sources: {', '.join(missing)}"],
            }
        )

        orphan_rows = db.query_graph(
            """
            MATCH (f:Factor)
            WHERE NOT EXISTS { MATCH (:Country)-[:HAS_FACTOR_EXPOSURE]->(f) }
            RETURN COUNT(f) AS orphan_count
            """
        )
        orphan_count = int(orphan_rows[0]["orphan_count"]) if orphan_rows else 0
        checks.append(
            {
                "id": "no_orphan_factors",
                "passed": orphan_count == 0,
                "failures": [] if orphan_count == 0 else [f"orphan factor count = {orphan_count}"],
            }
        )

        taiwan_rows = db.query_graph(
            """
            MATCH (:Country {t2_name:'Taiwan'})-[r:TRADES_WITH]->(:Country)
            RETURN COUNT(r) AS outbound
            """
        )
        outbound = int(taiwan_rows[0]["outbound"]) if taiwan_rows else 0
        checks.append(
            {
                "id": "taiwan_trade_fallback_present",
                "passed": outbound > 0,
                "failures": [] if outbound > 0 else ["Taiwan still has zero outbound TRADES_WITH edges"],
                "details": {"outbound_edges": outbound},
            }
        )

    return checks


def write_reports(payload: Dict[str, Any]) -> Dict[str, Path]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = REPORT_DIR / f"{stamp}_query_assistant_suite.json"
    md_path = REPORT_DIR / f"{stamp}_query_assistant_suite.md"

    json_path.write_text(json.dumps(_json_ready(payload), indent=2), encoding="utf-8")

    lines = [
        "# ASADO Query Assistant Suite",
        "",
        f"- Generated at: `{payload['generated_at']}`",
        f"- Provider: `{payload['provider']}`",
        f"- Model: `{payload['model']}`",
        f"- Case pass rate: `{payload['passed_cases']}/{payload['total_cases']}`",
        f"- Integrity pass rate: `{payload['passed_integrity_checks']}/{payload['total_integrity_checks']}`",
        "",
        "## Case Results",
        "",
    ]

    for case in payload["cases"]:
        status = "PASS" if case["passed"] else "FAIL"
        lines.append(
            f"- `{status}` `{case['id']}` | mode `{case.get('actual_mode')}` | rows `{case.get('row_count', 0)}` | question: {case['question']}"
        )
        if case.get("failures"):
            for failure in case["failures"]:
                lines.append(f"  - {failure}")
        if case.get("clarification_question"):
            lines.append(f"  - Clarification: {case['clarification_question']}")
        if case.get("preview_rows"):
                lines.append("  - Preview:")
                for row in case["preview_rows"][:5]:
                    lines.append(f"    - `{json.dumps(_json_ready(row), ensure_ascii=True)}`")
    lines.extend(["", "## Integrity Checks", ""])

    for check in payload["integrity_checks"]:
        status = "PASS" if check["passed"] else "FAIL"
        lines.append(f"- `{status}` `{check['id']}`")
        for failure in check.get("failures", []):
            lines.append(f"  - {failure}")

    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ASADO query assistant regression suite")
    parser.add_argument("--provider", default="auto", choices=["auto", "openai", "anthropic"])
    parser.add_argument("--model", default=None, help="Optional model override")
    args = parser.parse_args()

    build_and_write_schema_cache()
    assistant = ASADOQueryAssistant(provider=args.provider, model=args.model)

    cases = [run_case(assistant, case) for case in SUITE_CASES]
    integrity_checks = run_integrity_checks()

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "provider": assistant.provider,
        "model": assistant.model,
        "cases": cases,
        "integrity_checks": integrity_checks,
        "total_cases": len(cases),
        "passed_cases": sum(1 for case in cases if case["passed"]),
        "total_integrity_checks": len(integrity_checks),
        "passed_integrity_checks": sum(1 for check in integrity_checks if check["passed"]),
    }
    paths = write_reports(payload)

    print(json.dumps(
        {
            "passed_cases": payload["passed_cases"],
            "total_cases": payload["total_cases"],
            "passed_integrity_checks": payload["passed_integrity_checks"],
            "total_integrity_checks": payload["total_integrity_checks"],
            "json_report": str(paths["json"]),
            "markdown_report": str(paths["markdown"]),
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()
