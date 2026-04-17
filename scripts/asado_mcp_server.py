#!/usr/bin/env python3
"""
Local MCP server for ASADO.

This server is intended for local desktop clients such as Claude Desktop.
It exposes a small, read-only tool surface over the existing ASADO query layer.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from mcp.server.fastmcp import FastMCP

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.build_schema_registry import build_and_write_schema_cache, load_schema_cache
from scripts.db_bridge import AsadoDB
from scripts.query_assistant import ASADOQueryAssistant, QueryAssistantError, _json_ready

SERVER_INSTRUCTIONS = """
ASADO is a dual-database country research system.

Use the tools conservatively:
- Prefer `get_schema_summary` before writing ad hoc SQL or Cypher.
- Prefer `ask_asado` for natural-language research questions when an API key is available.
- Use `run_duckdb_sql` and `run_neo4j_cypher` only for read-only queries.
- Never assume market sleeves are sovereign countries. `ChinaA` is the sovereign proxy for China;
  `ChinaH`, `NASDAQ`, and `US SmallCap` are market sleeves in the graph layer.
- ASADO's sanctions layer reflects OFAC/SDN-linked country associations, not a clean sovereign
  sanctions-target registry.
""".strip()

mcp = FastMCP(
    name="ASADO",
    instructions=SERVER_INSTRUCTIONS,
)


def _schema_bundle(refresh_schema: bool = False) -> dict[str, Any]:
    if refresh_schema:
        build_and_write_schema_cache()
    return load_schema_cache(auto_build=True)


def _schema_snapshot(refresh_schema: bool = False) -> dict[str, Any]:
    schema = _schema_bundle(refresh_schema=refresh_schema)
    duckdb_tables = []
    for name, info in schema["duckdb"]["tables"].items():
        duckdb_tables.append(
            {
                "name": name,
                "description": info.get("description"),
                "columns": [col["column_name"] for col in info.get("columns", [])],
                "row_count": info.get("row_count"),
                "date_range": info.get("date_range"),
                "sample_variables": info.get("sample_variables", []),
            }
        )

    neo4j_labels = {
        name: {
            "description": info.get("description"),
            "count": info.get("count"),
            "properties": [prop["key"] for prop in info.get("properties", [])],
        }
        for name, info in schema["neo4j"].get("labels", {}).items()
    }
    neo4j_relationships = {
        name: {
            "description": info.get("description"),
            "count": info.get("count"),
            "source_labels": info.get("source_labels", []),
            "target_labels": info.get("target_labels", []),
            "properties": [prop["key"] for prop in info.get("properties", [])],
        }
        for name, info in schema["neo4j"].get("relationships", {}).items()
    }

    return {
        "generated_at": schema["manifest"].get("generated_at"),
        "duckdb_tables": duckdb_tables,
        "countries": schema["duckdb"].get("countries", []),
        "variable_names": schema["variable_catalog"].get("variable_names", []),
        "neo4j_labels": neo4j_labels,
        "neo4j_relationships": neo4j_relationships,
        "notes": [
            "unified_panel is the main analytical view.",
            "Use graph_role to separate sovereign proxies from market sleeves in Neo4j.",
            "ChinaA is the sovereign proxy for China for graph-network questions.",
            "Sanctions data is OFAC/SDN association data, not a sovereign target registry.",
        ],
    }


def _frame_payload(df: pd.DataFrame, max_rows: int) -> dict[str, Any]:
    return {
        "row_count": int(len(df)),
        "columns": list(df.columns),
        "rows": _json_ready(df.head(max_rows)),
    }


@mcp.resource(
    "asado://schema-summary",
    name="ASADO Schema Summary",
    description="Compact summary of the current ASADO DuckDB and Neo4j schema.",
    mime_type="application/json",
)
def schema_summary_resource() -> str:
    return json.dumps(_json_ready(_schema_snapshot(refresh_schema=False)), indent=2)


@mcp.tool(
    description=(
        "Natural-language ASADO query assistant. "
        "Uses the existing planner/executor/interpreter stack. "
        "Requires OPENAI_API_KEY or ANTHROPIC_API_KEY in the MCP server environment."
    )
)
def ask_asado(
    question: str,
    preview_only: bool = False,
    max_rows: int = 100,
    provider: str = "auto",
    model: Optional[str] = None,
    refresh_schema: bool = False,
) -> dict[str, Any]:
    if refresh_schema:
        build_and_write_schema_cache()

    assistant = ASADOQueryAssistant(provider=provider, model=model)
    response = assistant.ask(question, preview_only=preview_only, max_rows=max_rows)
    payload = dict(response)
    if isinstance(payload.get("result_df"), pd.DataFrame):
        payload["result"] = _frame_payload(payload["result_df"], max_rows=max_rows)
        del payload["result_df"]
    return _json_ready(payload)


@mcp.tool(
    description=(
        "Return the current ASADO schema summary for Claude to inspect before writing SQL or Cypher."
    )
)
def get_schema_summary(refresh_schema: bool = False) -> dict[str, Any]:
    return _json_ready(_schema_snapshot(refresh_schema=refresh_schema))


@mcp.tool(
    description=(
        "Execute a read-only DuckDB SQL query against ASADO. "
        "Only SELECT/CTE queries are allowed."
    )
)
def run_duckdb_sql(sql: str, max_rows: int = 100) -> dict[str, Any]:
    schema = _schema_bundle(refresh_schema=False)
    validated = ASADOQueryAssistant._validate_sql(
        sql,
        allowed_tables=set(schema["duckdb"]["tables"].keys()),
    )
    limited = ASADOQueryAssistant._ensure_sql_limit(validated, max_rows)
    with AsadoDB() as db:
        result = db.query_panel(limited)
    return {
        "engine": "duckdb",
        "query": limited,
        "result": _frame_payload(result, max_rows=max_rows),
    }


@mcp.tool(
    description=(
        "Execute a read-only Neo4j Cypher query against ASADO. "
        "Only MATCH/CALL/WITH/RETURN style queries are allowed."
    )
)
def run_neo4j_cypher(cypher: str, max_rows: int = 100) -> dict[str, Any]:
    schema = _schema_bundle(refresh_schema=False)
    validated = ASADOQueryAssistant._validate_cypher(
        cypher,
        allowed_labels=set(schema["neo4j"].get("labels", {}).keys()),
        allowed_rels=set(schema["neo4j"].get("relationships", {}).keys()),
    )
    limited = ASADOQueryAssistant._ensure_cypher_limit(validated, max_rows)
    with AsadoDB() as db:
        records = pd.DataFrame(db.query_graph(limited))
    return {
        "engine": "neo4j",
        "query": limited,
        "result": _frame_payload(records, max_rows=max_rows),
    }


@mcp.tool(
    description="Return the combined factor plus graph profile for one ASADO country node."
)
def get_country_profile(country: str) -> dict[str, Any]:
    with AsadoDB() as db:
        profile = db.country_profile(country)
    payload = dict(profile)
    if isinstance(payload.get("factors"), pd.DataFrame):
        payload["factors"] = _frame_payload(payload["factors"], max_rows=200)
    return _json_ready(payload)


def main() -> None:
    try:
        mcp.run(transport="stdio")
    except QueryAssistantError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
