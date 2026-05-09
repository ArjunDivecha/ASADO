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
ASADO is a dual-database country research system with both monthly and daily data.

Use the tools conservatively:
- Prefer `get_schema_summary` before writing ad hoc SQL or Cypher.
- Prefer `ask_asado` for natural-language research questions when an API key is available.
- Use `run_duckdb_sql` and `run_neo4j_cypher` only for read-only queries.
- Use `event_window` for daily-frequency event studies around a specific date.
- Use `events_in_window` to find historical events by category/country/tag, then chain
  with `event_window` for each matched event. This two-step pattern handles queries like
  "show me Saudi Arabia around the last 3 OPEC cuts" without the user knowing dates.
- Never assume market sleeves are sovereign countries. `ChinaA` is the sovereign proxy for China;
  `ChinaH`, `NASDAQ`, and `US SmallCap` are market sleeves in the graph layer.
- ASADO's sanctions layer reflects OFAC/SDN-linked country associations, not a clean sovereign
  sanctions-target registry.

Daily tables (parallel to monthly, same DB):
- t2_factors_daily: 109 normalized _CS/_TS variables, 34 countries, 2000–present
- t2_levels_daily: 47 raw factor levels, 34 countries, 2000–present
- gdelt_factors_daily: 75 normalized GDELT factors, 34 countries, 2015–present
- gdelt_raw_daily: 249-country raw GDELT signals (off-universe entity bridge)
- factor_returns_daily: 157 optimizer factor returns (T2 + GDELT), 2000–present
- variable_meta: frequency / category / optimizer-selected metadata for all variables
- daily_calendar: per-country trading day calendar
- event_log: ~200 hand-curated dated events with category, severity, country tags

Event-anchored query pattern (two-step):
  1. events_in_window(start, end, category, country, tag) → find relevant events
  2. event_window(country, date, days_before, days_after) → per-event factor study
Trigger phrases: "around the last X", "during the X crisis", "compare reactions to X"
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
            "unified_panel is the main monthly analytical view.",
            "Daily tables: t2_factors_daily, t2_levels_daily, gdelt_factors_daily, "
            "gdelt_raw_daily, factor_returns_daily, variable_meta, daily_calendar.",
            "Use event_window tool for daily event studies instead of raw SQL.",
            "variable_meta.is_optimizer_selected flags the 8 strategy-driving factors.",
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


@mcp.tool(
    description=(
        "Daily event-window study: returns daily factor values and GDELT signals "
        "for a country around a specific date. Use this for event studies "
        "(e.g., 'what happened to Turkey around the 2018 lira crisis?'). "
        "Returns T2 factors, GDELT signals, and factor returns in the window."
    )
)
def event_window(
    country: str,
    date: str,
    days_before: int = 10,
    days_after: int = 10,
    variables: str = "optimizer",
    include_gdelt: bool = True,
    include_factor_returns: bool = True,
    max_rows: int = 500,
) -> dict[str, Any]:
    """
    Args:
        country: T2 country name (e.g., "Turkey", "Saudi Arabia", "Brazil").
        date: Center date in YYYY-MM-DD format.
        days_before: Calendar days before the event date to include.
        days_after: Calendar days after the event date to include.
        variables: Which T2 variables to include. Options:
            "optimizer" = 8 optimizer-selected factors (default),
            "all" = all 109 normalized variables,
            or a comma-separated list of specific variable names.
        include_gdelt: Whether to include GDELT daily signals for this country.
        include_factor_returns: Whether to include daily factor returns in the window.
        max_rows: Maximum rows per section.
    """
    import duckdb as _duckdb

    db_path = str(BASE_DIR / "Data" / "asado.duckdb")
    con = _duckdb.connect(db_path, read_only=True)

    start_date = f"DATE '{date}' - INTERVAL {days_before} DAY"
    end_date = f"DATE '{date}' + INTERVAL {days_after} DAY"

    # Resolve variable filter
    if variables == "optimizer":
        var_filter = """
            AND t.variable IN (
                SELECT variable FROM variable_meta WHERE is_optimizer_selected
            )
        """
    elif variables == "all":
        var_filter = ""
    else:
        var_list = ", ".join(f"'{v.strip()}'" for v in variables.split(","))
        var_filter = f"AND t.variable IN ({var_list})"

    # T2 daily factors
    t2_df = con.execute(f"""
        SELECT t.date, t.country, t.variable, t.value
        FROM t2_factors_daily t
        WHERE t.country = '{country}'
          AND t.date BETWEEN {start_date} AND {end_date}
          {var_filter}
        ORDER BY t.variable, t.date
        LIMIT {max_rows}
    """).fetchdf()

    result: dict[str, Any] = {
        "country": country,
        "event_date": date,
        "window": f"{days_before}d before → {days_after}d after",
        "t2_factors": _frame_payload(t2_df, max_rows=max_rows),
    }

    # GDELT daily factors for this country
    if include_gdelt:
        gdelt_df = con.execute(f"""
            SELECT g.date, g.country, g.variable, g.value
            FROM gdelt_factors_daily g
            WHERE g.country = '{country}'
              AND g.date BETWEEN {start_date} AND {end_date}
            ORDER BY g.variable, g.date
            LIMIT {max_rows}
        """).fetchdf()
        result["gdelt_factors"] = _frame_payload(gdelt_df, max_rows=max_rows)

    # Factor returns in the window (not country-specific — these are portfolio returns)
    if include_factor_returns:
        fr_df = con.execute(f"""
            SELECT f.date, f.factor, f.value, f.source
            FROM factor_returns_daily f
            WHERE f.date BETWEEN {start_date} AND {end_date}
              AND f.factor IN (
                  SELECT variable FROM variable_meta WHERE is_optimizer_selected
              )
            ORDER BY f.factor, f.date
            LIMIT {max_rows}
        """).fetchdf()
        result["factor_returns"] = _frame_payload(fr_df, max_rows=max_rows)

    # Trading calendar context
    cal_df = con.execute(f"""
        SELECT date, is_trading_day
        FROM daily_calendar
        WHERE country = '{country}'
          AND date BETWEEN {start_date} AND {end_date}
        ORDER BY date
    """).fetchdf()
    trading_days = int(cal_df["is_trading_day"].sum()) if not cal_df.empty else 0
    result["calendar"] = {
        "total_days": len(cal_df),
        "trading_days": trading_days,
    }

    con.close()
    return _json_ready(result)


@mcp.tool(
    description=(
        "Search the curated event registry by date range, category, subcategory, country, severity, or tags. "
        "Returns matching events sorted by date descending. "
        "Designed for chaining with event_window: find events first, then loop "
        "event_window per event for factor studies. "
        "Example: events_in_window(category='oil_supply', subcategory='opec_cut') then event_window each for Saudi Arabia."
    )
)
def events_in_window(
    start_date: str,
    end_date: str,
    category: str = None,
    subcategory: str = None,
    country: str = None,
    strict_country: bool = False,
    severity: str = "high",
    tag_filter: str = None,
    max_results: int = 50,
) -> dict[str, Any]:
    """
    Args:
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        category: Filter to one category (central_bank, macro_release, oil_supply,
                  geopolitical, financial_crisis, trade_policy, election, regulatory).
        subcategory: Filter to a specific subcategory within a category. Key values:
            central_bank: fomc_pivot, fomc_hike, fomc_cut, fomc_qe, ecb_pivot, ecb_qe,
                ecb_hike, ecb_cut, boj_qe, boj_nirp, boj_ycc, boj_hike, snb_unpeg,
                boe_intervention, pboc_fx, cb_governance, em_cb_hike, em_cb_defense
            oil_supply: opec_cut, opec_policy, opec_extend, supply_disruption,
                price_war, price_cap, sanctions, market_dislocation
            geopolitical: war, military_strike, terrorism, escalation, direct_strike,
                civil_unrest, nuclear, referendum, annexation, regime_change, pandemic
            financial_crisis: bank_failure, currency_crisis, sovereign_default,
                sovereign_bailout, sovereign_crisis, bailout, bailin, downgrade,
                fiscal_crisis, market_dislocation
            trade_policy: tariff_announcement, tariff_implementation, tariff_escalation,
                tariff_pause, trade_deal, trade_withdrawal, export_controls,
                industrial_policy, court_ruling
            election: presidential, parliamentary
            regulatory: tech_crackdown, china_crackdown, ipo_halt, sector_ban,
                antitrust, antitrust_ruling, crypto, crypto_enforcement,
                crypto_etf_approval, ai_regulation, market_structure,
                governance_reform, policy_doctrine
            macro_release: cpi_surprise, jobs_report, fed_speech_jh, gdp_print,
                data_revision, market_event
        country: T2 country name; returns events where country is in countries_affected
                 OR event is_global=TRUE (unless strict_country=True).
        strict_country: When False (default), country filter matches both
            country-specific events and global events. When True, returns only
            events explicitly tagged with this country (is_global=FALSE).
            Use True for "country-specific events only"; False for "all events
            that would have moved this country."
        severity: Filter: 'high', 'medium', 'low', or 'all' (default 'high').
        tag_filter: Comma-separated tags; matches events with ANY of these tags.
        max_results: Maximum events to return (default 50).
    """
    import duckdb as _duckdb

    db_path = str(BASE_DIR / "Data" / "asado.duckdb")
    con = _duckdb.connect(db_path, read_only=True)

    # Check if event_log table exists
    tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    if "event_log" not in tables:
        con.close()
        return {"error": "event_log table not found. Run build_event_log.py first."}

    # Build query with filters
    # Date overlap logic: point events must be in [start, end]; range events must overlap
    conditions = [
        "event_date <= ?",
        "((end_date IS NULL AND event_date >= ?) OR (end_date IS NOT NULL AND end_date >= ?))",
    ]
    params: list = [end_date, start_date, start_date]

    if category:
        conditions.append("category = ?")
        params.append(category)

    if subcategory:
        conditions.append("subcategory = ?")
        params.append(subcategory)

    if severity and severity != "all":
        conditions.append("severity = ?")
        params.append(severity)

    if country:
        if strict_country:
            conditions.append(
                "(is_global = FALSE AND countries_affected LIKE ?)"
            )
        else:
            conditions.append(
                "(is_global = TRUE OR countries_affected LIKE ?)"
            )
        params.append(f"%{country}%")

    if tag_filter:
        # Match ANY of the provided tags
        tag_clauses = []
        for tag in tag_filter.split(","):
            tag = tag.strip()
            if tag:
                tag_clauses.append("tags LIKE ?")
                params.append(f"%{tag}%")
        if tag_clauses:
            conditions.append(f"({' OR '.join(tag_clauses)})")

    where = " AND ".join(conditions)
    sql = f"""
        SELECT event_id, event_date, end_date, label, category,
               subcategory, severity, countries_affected, is_global, tags, description
        FROM event_log
        WHERE {where}
        ORDER BY event_date DESC
        LIMIT {max_results}
    """

    df = con.execute(sql, params).fetchdf()
    con.close()

    return _json_ready({
        "row_count": int(len(df)),
        "filters_applied": {
            "start_date": start_date,
            "end_date": end_date,
            "category": category,
            "subcategory": subcategory,
            "country": country,
            "strict_country": strict_country,
            "severity": severity,
            "tag_filter": tag_filter,
        },
        "columns": list(df.columns),
        "rows": _json_ready(df.head(max_results)),
    })


@mcp.tool(
    description=(
        "Return daily factor values for a country over a date range. "
        "More general than event_window — use for time-series extraction."
    )
)
def daily_factor_series(
    country: str,
    variables: str,
    start_date: str,
    end_date: str,
    source: str = "t2",
    max_rows: int = 500,
) -> dict[str, Any]:
    """
    Args:
        country: T2 country name or ISO3 code (ISO3 for gdelt_raw source).
        variables: Comma-separated variable names, or "optimizer" for the 8 selected.
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        source: Which table to query: "t2" (default), "t2_levels", "gdelt", "gdelt_raw".
        max_rows: Maximum rows to return.
    """
    import duckdb as _duckdb

    db_path = str(BASE_DIR / "Data" / "asado.duckdb")
    con = _duckdb.connect(db_path, read_only=True)

    table_map = {
        "t2": "t2_factors_daily",
        "t2_levels": "t2_levels_daily",
        "gdelt": "gdelt_factors_daily",
    }

    if variables == "optimizer":
        var_filter = """
            AND variable IN (
                SELECT variable FROM variable_meta WHERE is_optimizer_selected
            )
        """
    else:
        var_list = ", ".join(f"'{v.strip()}'" for v in variables.split(","))
        var_filter = f"AND variable IN ({var_list})"

    if source == "gdelt_raw":
        # Wide format — return all signal columns for the country
        df = con.execute(f"""
            SELECT *
            FROM gdelt_raw_daily
            WHERE country_iso3 = '{country}'
              AND date BETWEEN DATE '{start_date}' AND DATE '{end_date}'
            ORDER BY date
            LIMIT {max_rows}
        """).fetchdf()
    else:
        table = table_map.get(source, "t2_factors_daily")
        df = con.execute(f"""
            SELECT date, country, variable, value
            FROM {table}
            WHERE country = '{country}'
              AND date BETWEEN DATE '{start_date}' AND DATE '{end_date}'
              {var_filter}
            ORDER BY variable, date
            LIMIT {max_rows}
        """).fetchdf()

    con.close()
    return _json_ready({
        "country": country,
        "source": source,
        "date_range": f"{start_date} → {end_date}",
        "result": _frame_payload(df, max_rows=max_rows),
    })


def main() -> None:
    try:
        mcp.run(transport="stdio")
    except QueryAssistantError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
