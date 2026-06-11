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
- predmkt_daily/predmkt_*: Stage 2 prediction-market snapshots, metadata, and composites
- wb_commodity_*: World Bank Pink Sheet monthly commodity prices, indices, features,
  and selected global-broadcast explanatory variables

Event-anchored query pattern (two-step):
  1. events_in_window(start, end, category, country, tag) → find relevant events
  2. event_window(country, date, days_before, days_after) → per-event factor study
Trigger phrases: "around the last X", "during the X crisis", "compare reactions to X"

Prediction-market query pattern:
  1. event_market_set(keyword) → find relevant curated markets
  2. predmkt_snapshot(category, date) → inspect current probabilities and liquidity
  3. country_signal_now(country, channels) → spillover-implied country risk/opportunity
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
            "Returns are the primary outcome layer. Use country_returns / factor_return_series / "
            "country_factor_attribution / return_leaders tools for performance, event, and "
            "explanation questions before writing ad hoc SQL.",
            "Country returns have ONE canonical source: T2 (34 countries). Monthly: feature_panel "
            "source='t2' with 1MRet/3MRet/6MRet/9MRet/12MRet. Daily: t2_factors_daily with "
            "1DRet/5DRet/20DRet/60DRet/120DRet.",
            "GDELT-labeled 1MRet/1DRet rows are bit-exact aliases of T2 country returns — do "
            "NOT treat them as a second return source.",
            "Factor portfolio returns: factor_returns (monthly: econ_optimizer, t2_optimizer, "
            "gdelt_optimizer) and factor_returns_daily (t2_optimizer_daily, gdelt_optimizer_daily). "
            "These are top-20%-bucket portfolio returns, NOT raw factor levels.",
            "country_factor_attribution joins factor_top20_membership ⨝ factor_returns and "
            "gives weight × factor_return contribution per country/factor.",
            "Do NOT add factor_returns / factor_returns_daily / factor_top20_membership / "
            "country_factor_attribution into feature_panel or unified_panel — those are "
            "explanatory/input surfaces the optimizer consumes.",
            "unified_panel is the main monthly analytical view.",
            "Daily tables: t2_factors_daily, t2_levels_daily, gdelt_factors_daily, "
            "gdelt_raw_daily, factor_returns_daily, variable_meta, daily_calendar.",
            "Prediction-market tables: predmkt_daily, predmkt_market_meta, "
            "predmkt_outcome_meta, predmkt_country_spillover, predmkt_resolutions, "
            "predmkt_signals_daily.",
            "Prediction-market tools: predmkt_snapshot, country_signal_now, event_market_set.",
            "Commodity tool: commodity_price_series. World Bank commodity variables are explanatory context; use return tools before claiming country/factor impact.",
            "Use event_window tool for daily event studies instead of raw SQL — it now "
            "includes a return_summary block with pre/post/window country returns and "
            "factor return leaders/laggards.",
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


def _predmkt_date_expression(date_str: str, table: str = "predmkt_daily", date_col: str = "snapshot_date") -> str:
    if date_str.strip().lower() in {"today", "latest", "now", ""}:
        return f"(SELECT MAX({date_col}) FROM {table})"
    return f"(SELECT MAX({date_col}) FROM {table} WHERE {date_col} <= DATE '{date_str}')"


# --- Returns-first helpers -------------------------------------------------

MONTHLY_RETURN_HORIZONS = {"1MRet", "3MRet", "6MRet", "9MRet", "12MRet"}
DAILY_RETURN_HORIZONS = {"1DRet", "5DRet", "20DRet", "60DRet", "120DRet"}
FACTOR_RETURN_MONTHLY_SOURCES = {"econ_optimizer", "t2_optimizer", "gdelt_optimizer"}
FACTOR_RETURN_DAILY_SOURCES = {"t2_optimizer_daily", "gdelt_optimizer_daily"}

RETURNS_CAVEATS = {
    "country_return": (
        "Country returns have one canonical source (T2, 34 countries). GDELT-labeled "
        "1MRet/1DRet rows are bit-exact aliases of T2 returns; do not treat them as a "
        "second source."
    ),
    "factor_return": (
        "These are top-20%-of-countries portfolio returns from the ASADO optimizer "
        "pipelines — factor portfolio returns, NOT raw factor levels."
    ),
    "attribution": (
        "country_factor_attribution gives top-20% bucket contribution "
        "(weight × factor_return), not a full country portfolio decomposition."
    ),
}


def _duck_conn():
    import duckdb as _duckdb
    db_path = str(BASE_DIR / "Data" / "asado.duckdb")
    return _duckdb.connect(db_path, read_only=True)


def _resolve_horizon(frequency: str, horizon: Optional[str]) -> str:
    freq = (frequency or "monthly").strip().lower()
    if freq == "daily":
        default, allowed = "1DRet", DAILY_RETURN_HORIZONS
    else:
        default, allowed = "1MRet", MONTHLY_RETURN_HORIZONS
    h = (horizon or default).strip()
    if h not in allowed:
        raise ValueError(
            f"Unsupported horizon '{h}' for frequency '{freq}'. "
            f"Allowed: {sorted(allowed)}"
        )
    return h


def _split_csv(value: Optional[str]) -> list[str]:
    if not value or value.strip().lower() == "all":
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _country_in_clause(countries: list[str]) -> tuple[str, list[Any]]:
    if not countries:
        return "", []
    placeholders = ", ".join("?" for _ in countries)
    return f"AND country IN ({placeholders})", list(countries)


def _factor_in_clause(factors: list[str]) -> tuple[str, list[Any]]:
    if not factors:
        return "", []
    placeholders = ", ".join("?" for _ in factors)
    return f"AND factor IN ({placeholders})", list(factors)


def _resolve_window_start_sql(window: str, latest_date_expr: str) -> Optional[str]:
    w = (window or "latest").strip().lower()
    if w in {"latest", ""}:
        return None
    if w == "ytd":
        return f"DATE_TRUNC('year', {latest_date_expr})"
    if w.endswith("m"):
        try:
            months = int(w[:-1])
        except ValueError:
            return None
        return f"({latest_date_expr} - INTERVAL {months} MONTH)"
    return None


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
    variables: str = "all",
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
            "all" = all normalized variables (default),
            or a comma-separated list of specific variable names.
            ("optimizer" was removed 2026-06-10 — the 8-factor whitelist was a
            stale artifact from the retired Fuzzy Daily project.)
        include_gdelt: Whether to include GDELT daily signals for this country.
        include_factor_returns: Whether to include daily factor returns in the window.
        max_rows: Maximum rows per section.
    """
    import duckdb as _duckdb

    if variables == "optimizer":
        raise ValueError(
            "The 'optimizer' variable shortcut was removed (2026-06-10): the "
            "8-factor whitelist was a stale artifact, not a live strategy. "
            "Pass 'all' or an explicit comma-separated variable list."
        )

    db_path = str(BASE_DIR / "Data" / "asado.duckdb")
    con = _duckdb.connect(db_path, read_only=True)

    start_date = f"DATE '{date}' - INTERVAL {days_before} DAY"
    end_date = f"DATE '{date}' + INTERVAL {days_after} DAY"

    # Resolve variable filter
    if variables == "all":
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

    # --- Return summary (PRD §7.6) ---------------------------------------
    # Pre / post / window cumulative country returns; factor return leaders/laggards.
    country_ret_df = con.execute(f"""
        SELECT date, value AS ret_1d
        FROM t2_factors_daily
        WHERE country = '{country}'
          AND variable = '1DRet'
          AND date BETWEEN {start_date} AND {end_date}
        ORDER BY date
    """).fetchdf()

    pre_return = post_return = window_return = None
    pivot_date = pd.Timestamp(date).date() if not isinstance(date, pd.Timestamp) else date.date()
    if not country_ret_df.empty:
        cr = country_ret_df.dropna(subset=["ret_1d"]).copy()
        cr["d"] = pd.to_datetime(cr["date"]).dt.date
        pre_mask = cr["d"] < pivot_date
        post_mask = cr["d"] > pivot_date
        pre_return = float(cr.loc[pre_mask, "ret_1d"].sum()) if pre_mask.any() else None
        post_return = float(cr.loc[post_mask, "ret_1d"].sum()) if post_mask.any() else None
        window_return = float(cr["ret_1d"].sum())

    fr_leaders = con.execute(f"""
        SELECT factor, SUM(value) AS cum_return, source
        FROM factor_returns_daily
        WHERE date BETWEEN {start_date} AND {end_date}
          AND value IS NOT NULL
        GROUP BY factor, source
        ORDER BY cum_return DESC NULLS LAST
        LIMIT 10
    """).fetchdf()
    fr_laggards = con.execute(f"""
        SELECT factor, SUM(value) AS cum_return, source
        FROM factor_returns_daily
        WHERE date BETWEEN {start_date} AND {end_date}
          AND value IS NOT NULL
        GROUP BY factor, source
        ORDER BY cum_return ASC NULLS LAST
        LIMIT 10
    """).fetchdf()

    result["return_summary"] = {
        "country": country,
        "event_date": date,
        "country_daily_returns": _frame_payload(country_ret_df, max_rows=max_rows),
        "pre_event_return_simple_sum": pre_return,
        "post_event_return_simple_sum": post_return,
        "event_window_return_simple_sum": window_return,
        "factor_return_leaders": _frame_payload(fr_leaders, max_rows=10),
        "factor_return_laggards": _frame_payload(fr_laggards, max_rows=10),
        "caveats": [
            RETURNS_CAVEATS["country_return"],
            RETURNS_CAVEATS["factor_return"],
            "Cumulative window returns use simple sum of daily 1DRet values (not compounded).",
            "Event-window evidence is descriptive — causality is not separately tested here.",
        ],
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
        "Return prediction-market rows for one ASADO category at a given snapshot date. "
        "Defaults to latest available date."
    )
)
def predmkt_snapshot(
    category: str,
    date: str = "today",
    max_rows: int = 200,
) -> dict[str, Any]:
    import duckdb as _duckdb

    db_path = str(BASE_DIR / "Data" / "asado.duckdb")
    con = _duckdb.connect(db_path, read_only=True)

    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    required = {"predmkt_daily", "predmkt_market_meta"}
    if not required.issubset(tables):
        con.close()
        return {"error": "Prediction-market tables not found. Run build_predmkt_panel.py first."}

    date_expr = _predmkt_date_expression(date, table="predmkt_daily", date_col="snapshot_date")
    sql = f"""
        WITH target AS (
            SELECT {date_expr} AS snapshot_date
        )
        SELECT
            d.snapshot_date,
            d.platform,
            d.market_id,
            m.title,
            m.asado_category,
            m.asado_subcategory,
            d.outcome_id,
            o.label AS outcome_label,
            d.probability,
            d.bid,
            d.ask,
            d.spread_bps,
            d.volume_24h_usd,
            d.liquidity_usd,
            d.is_stale,
            m.resolution_clarity,
            m.rules_url,
            DATE_DIFF('day', d.snapshot_date, CAST(m.close_ts AS DATE)) AS days_to_resolution
        FROM predmkt_daily d
        JOIN target t
          ON d.snapshot_date = t.snapshot_date
        LEFT JOIN predmkt_market_meta m
          ON m.platform = d.platform
         AND m.market_id = d.market_id
        LEFT JOIN predmkt_outcome_meta o
          ON o.platform = d.platform
         AND o.market_id = d.market_id
         AND o.outcome_id = d.outcome_id
        WHERE LOWER(COALESCE(m.asado_category, '')) = LOWER(?)
        ORDER BY d.volume_24h_usd DESC NULLS LAST, d.liquidity_usd DESC NULLS LAST
        LIMIT {max_rows}
    """
    df = con.execute(sql, [category]).fetchdf()
    con.close()

    snapshot_date = None
    if not df.empty:
        snapshot_date = str(df["snapshot_date"].iloc[0])
    return _json_ready(
        {
            "category": category,
            "snapshot_date": snapshot_date,
            "result": _frame_payload(df, max_rows=max_rows),
        }
    )


@mcp.tool(
    description=(
        "Return prediction-market-implied country signals and spillover channel decomposition "
        "for one T2 country at a given date (defaults to latest). "
        "Sign convention: predmkt_country_risk_composite > 0 means implied downside risk, "
        "while predmkt_country_opportunity_composite > 0 means implied upside opportunity."
    )
)
def country_signal_now(
    country: str,
    channels: str = None,
    date: str = "today",
    max_rows: int = 200,
) -> dict[str, Any]:
    import duckdb as _duckdb

    db_path = str(BASE_DIR / "Data" / "asado.duckdb")
    con = _duckdb.connect(db_path, read_only=True)

    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    required = {"predmkt_signals_daily", "predmkt_country_spillover", "predmkt_daily"}
    if not required.issubset(tables):
        con.close()
        return {"error": "Prediction-market tables not found. Run build_predmkt_panel.py first."}

    date_expr = _predmkt_date_expression(date, table="predmkt_signals_daily", date_col="snapshot_date")
    channel_items = []
    if channels:
        channel_items = [c.strip() for c in channels.split(",") if c.strip()]

    signal_sql = f"""
        WITH target AS (SELECT {date_expr} AS snapshot_date)
        SELECT
            snapshot_date,
            signal_name,
            country,
            value,
            n_markets,
            total_liquidity_usd,
            confidence_score
        FROM predmkt_signals_daily
        WHERE snapshot_date = (SELECT snapshot_date FROM target)
          AND country = ?
        ORDER BY signal_name
        LIMIT {max_rows}
    """
    signal_df = con.execute(signal_sql, [country]).fetchdf()

    if channel_items:
        placeholders = ", ".join("?" for _ in channel_items)
        channel_filter = f"AND s.channel IN ({placeholders})"
        params: list[Any] = [country] + channel_items
    else:
        channel_filter = ""
        params = [country]

    breakdown_sql = f"""
        WITH target AS (SELECT {date_expr} AS snapshot_date)
        SELECT
            s.channel,
            s.confidence,
            m.asado_category,
            m.asado_subcategory,
            m.title,
            d.platform,
            d.market_id,
            d.probability,
            s.elasticity,
            d.liquidity_usd,
            d.volume_24h_usd,
            d.is_stale,
            d.probability * s.elasticity AS implied_effect
        FROM predmkt_country_spillover s
        JOIN predmkt_daily d
          ON d.platform = s.platform
         AND d.market_id = s.market_id
         AND d.snapshot_date = (SELECT snapshot_date FROM target)
        LEFT JOIN predmkt_outcome_meta o
          ON o.platform = d.platform
         AND o.market_id = d.market_id
         AND o.outcome_id = d.outcome_id
        LEFT JOIN predmkt_market_meta m
          ON m.platform = d.platform
         AND m.market_id = d.market_id
        WHERE s.country = ?
          AND (LOWER(COALESCE(o.label, '')) = 'yes' OR o.label IS NULL)
          {channel_filter}
        ORDER BY ABS(d.probability * s.elasticity) DESC, d.liquidity_usd DESC NULLS LAST
        LIMIT {max_rows}
    """
    breakdown_df = con.execute(breakdown_sql, params).fetchdf()
    channel_agg = pd.DataFrame()
    if not breakdown_df.empty:
        channel_agg = (
            breakdown_df.groupby("channel", as_index=False)
            .agg(
                market_count=("market_id", "nunique"),
                avg_probability=("probability", "mean"),
                avg_elasticity=("elasticity", "mean"),
                net_implied_effect=("implied_effect", "sum"),
                total_liquidity_usd=("liquidity_usd", "sum"),
            )
            .sort_values("net_implied_effect", ascending=False)
        )
    con.close()

    snapshot_date = None
    if not signal_df.empty:
        snapshot_date = str(signal_df["snapshot_date"].iloc[0])
    elif not breakdown_df.empty:
        snapshot_date = date if date != "today" else None
    return _json_ready(
        {
            "country": country,
            "snapshot_date": snapshot_date,
            "channels_filter": channel_items,
            "signals": _frame_payload(signal_df, max_rows=max_rows),
            "channel_breakdown": _frame_payload(channel_agg, max_rows=max_rows),
            "market_breakdown": _frame_payload(breakdown_df, max_rows=max_rows),
        }
    )


@mcp.tool(
    description=(
        "Search curated prediction markets by keyword across title/rules/slug, "
        "ranked by recent liquidity."
    )
)
def event_market_set(keyword: str, max_rows: int = 100) -> dict[str, Any]:
    import duckdb as _duckdb

    db_path = str(BASE_DIR / "Data" / "asado.duckdb")
    con = _duckdb.connect(db_path, read_only=True)

    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    required = {"predmkt_daily", "predmkt_market_meta"}
    if not required.issubset(tables):
        con.close()
        return {"error": "Prediction-market tables not found. Run build_predmkt_panel.py first."}

    token = keyword.strip().lower()
    like = f"%{token}%"
    sql = f"""
        WITH latest AS (
            SELECT MAX(snapshot_date) AS snapshot_date FROM predmkt_daily
        ),
        latest_primary AS (
            SELECT
                d.platform,
                d.market_id,
                d.probability,
                d.volume_24h_usd,
                d.liquidity_usd,
                ROW_NUMBER() OVER (
                    PARTITION BY d.platform, d.market_id
                    ORDER BY
                        CASE WHEN LOWER(COALESCE(o.label, '')) = 'yes' THEN 0 ELSE 1 END,
                        d.probability DESC
                ) AS rn
            FROM predmkt_daily d
            LEFT JOIN predmkt_outcome_meta o
              ON o.platform = d.platform
             AND o.market_id = d.market_id
             AND o.outcome_id = d.outcome_id
            WHERE d.snapshot_date = (SELECT snapshot_date FROM latest)
        ),
        vol7 AS (
            SELECT
                platform,
                market_id,
                SUM(COALESCE(volume_24h_usd, 0.0)) AS volume_7d_usd
            FROM predmkt_daily
            WHERE snapshot_date >= (SELECT snapshot_date FROM latest) - INTERVAL 6 DAY
            GROUP BY platform, market_id
        )
        SELECT
            m.platform,
            m.market_id,
            m.title,
            m.slug,
            m.asado_category,
            m.asado_subcategory,
            lp.probability AS primary_probability,
            lp.volume_24h_usd,
            lp.liquidity_usd,
            v.volume_7d_usd,
            m.resolution_clarity
        FROM predmkt_market_meta m
        LEFT JOIN latest_primary lp
          ON lp.platform = m.platform
         AND lp.market_id = m.market_id
         AND lp.rn = 1
        LEFT JOIN vol7 v
          ON v.platform = m.platform
         AND v.market_id = m.market_id
        WHERE LOWER(COALESCE(m.title, '')) LIKE ?
           OR LOWER(COALESCE(m.rules_text, '')) LIKE ?
           OR LOWER(COALESCE(m.slug, '')) LIKE ?
        ORDER BY COALESCE(v.volume_7d_usd, 0.0) DESC, COALESCE(lp.volume_24h_usd, 0.0) DESC
        LIMIT {max_rows}
    """
    df = con.execute(sql, [like, like, like]).fetchdf()
    con.close()
    return _json_ready(
        {
            "keyword": keyword,
            "result": _frame_payload(df, max_rows=max_rows),
        }
    )


@mcp.tool(
    description=(
        "World Bank Pink Sheet commodity price/index series and derived monthly features. "
        "Use for commodity-axis context; for country impact questions, pair this with "
        "country_returns or factor_return_series."
    )
)
def commodity_price_series(
    commodity: str,
    feature: str = "level",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_rows: int = 500,
) -> dict[str, Any]:
    """Return a World Bank commodity or commodity-index feature time series.

    Args:
        commodity: Code or fuzzy display name, such as CRUDE_BRENT, brent, copper, iENERGY.
        feature: level, mom_pct, yoy_pct, ret_3m_pct, ret_12m_pct, vol_12m, or z_36m.
        start_date: Optional inclusive start date.
        end_date: Optional inclusive end date.
        max_rows: Row cap.
    """
    aliases = {
        "mom": "mom_pct",
        "yoy": "yoy_pct",
        "ret_3m": "ret_3m_pct",
        "return_3m": "ret_3m_pct",
        "ret_12m": "ret_12m_pct",
        "return_12m": "ret_12m_pct",
    }
    allowed = {"level", "mom_pct", "yoy_pct", "ret_3m_pct", "ret_12m_pct", "vol_12m", "z_36m"}
    feature = aliases.get(feature.strip().lower(), feature.strip())
    if feature not in allowed:
        raise ValueError(f"Unsupported feature '{feature}'. Allowed: {sorted(allowed)}")

    con = _duck_conn()
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        if "wb_commodity_features" not in tables or "wb_commodity_meta" not in tables:
            return _json_ready({
                "commodity": commodity,
                "feature": feature,
                "error": "World Bank commodity tables are not loaded in DuckDB.",
                "result": _frame_payload(pd.DataFrame(), max_rows=max_rows),
            })

        term = commodity.strip().lower()
        like = f"%{term}%"
        matches = con.execute(
            """
            SELECT
                series_code,
                series_type,
                display_name,
                category,
                unit,
                is_projected_to_factor_panel,
                CASE
                    WHEN lower(series_code) = ? THEN 0
                    WHEN lower(display_name) = ? THEN 1
                    WHEN lower(series_code) LIKE ? THEN 2
                    ELSE 3
                END AS match_rank
            FROM wb_commodity_meta
            WHERE lower(series_code) = ?
               OR lower(display_name) = ?
               OR lower(series_code) LIKE ?
               OR lower(display_name) LIKE ?
            ORDER BY match_rank, is_projected_to_factor_panel DESC, series_code
            LIMIT 5
            """,
            [term, term, like, term, term, like, like],
        ).fetchdf()

        if matches.empty:
            return _json_ready({
                "commodity": commodity,
                "feature": feature,
                "error": "No matching World Bank commodity series.",
                "result": _frame_payload(pd.DataFrame(), max_rows=max_rows),
            })

        series_code = str(matches.iloc[0]["series_code"])
        clauses = ["series_code = ?", "feature = ?"]
        params: list[Any] = [series_code, feature]
        if start_date:
            clauses.append("date >= CAST(? AS DATE)")
            params.append(start_date)
        if end_date:
            clauses.append("date <= CAST(? AS DATE)")
            params.append(end_date)

        df = con.execute(
            f"""
            SELECT date, series_code, series_type, display_name, category, unit, feature, value, source
            FROM wb_commodity_features
            WHERE {' AND '.join(clauses)}
            ORDER BY date
            LIMIT {int(max_rows)}
            """,
            params,
        ).fetchdf()
        latest = con.execute(
            """
            SELECT date, value
            FROM wb_commodity_features
            WHERE series_code = ? AND feature = ? AND date <= CURRENT_DATE
            ORDER BY date DESC
            LIMIT 1
            """,
            [series_code, feature],
        ).fetchdf()
    finally:
        con.close()

    return _json_ready({
        "commodity_requested": commodity,
        "matched_series": matches.head(5).drop(columns=["match_rank"]).to_dict("records"),
        "feature": feature,
        "latest": latest.to_dict("records"),
        "caveat": (
            "World Bank commodity data is monthly explanatory context. "
            "Use country_returns / factor_return_series before claiming country or factor performance impact."
        ),
        "result": _frame_payload(df, max_rows=max_rows),
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
        variables: Comma-separated variable names.
            ("optimizer" was removed 2026-06-10 — the 8-factor whitelist was a
            stale artifact from the retired Fuzzy Daily project.)
        start_date: Start date in YYYY-MM-DD format.
        end_date: End date in YYYY-MM-DD format.
        source: Which table to query: "t2" (default), "t2_levels", "gdelt", "gdelt_raw".
        max_rows: Maximum rows to return.
    """
    import duckdb as _duckdb

    if variables == "optimizer":
        raise ValueError(
            "The 'optimizer' variable shortcut was removed (2026-06-10): the "
            "8-factor whitelist was a stale artifact, not a live strategy. "
            "Pass an explicit comma-separated variable list."
        )

    db_path = str(BASE_DIR / "Data" / "asado.duckdb")
    con = _duckdb.connect(db_path, read_only=True)

    table_map = {
        "t2": "t2_factors_daily",
        "t2_levels": "t2_levels_daily",
        "gdelt": "gdelt_factors_daily",
        # Country return tables — same underlying T2 returns; gdelt is an alias.
        "t2_returns": "t2_factors_daily",
        "gdelt_returns": "gdelt_factors_daily",
    }

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
    elif source == "factor_returns_daily":
        # Country arg is ignored — these are factor portfolio returns, not country-keyed.
        factor_filter = f"AND factor IN ({var_list})"
        df = con.execute(f"""
            SELECT date, factor, value, source
            FROM factor_returns_daily
            WHERE date BETWEEN DATE '{start_date}' AND DATE '{end_date}'
              {factor_filter}
            ORDER BY factor, date
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


# --- Returns-first deterministic tools -------------------------------------


@mcp.tool(
    description=(
        "Country returns (monthly or daily) for the 34-country T2 universe. "
        "There is exactly one canonical country return source (T2); the source arg "
        "is not exposed because GDELT-labeled returns are bit-exact aliases. "
        "Use for performance leaderboards, country return series, and event country reactions."
    )
)
def country_returns(
    countries: str = "all",
    frequency: str = "monthly",
    horizon: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    latest_only: bool = True,
    rank: Optional[str] = None,
    max_rows: int = 100,
) -> dict[str, Any]:
    """Return country return rows.

    Args:
        countries: Comma-separated T2 country names, or "all".
        frequency: "monthly" (default) or "daily".
        horizon: Monthly: 1MRet/3MRet/6MRet/9MRet/12MRet. Daily: 1DRet/5DRet/20DRet/60DRet/120DRet.
        start_date: Optional inclusive start (YYYY-MM-DD).
        end_date: Optional inclusive end (YYYY-MM-DD).
        latest_only: If True, restrict to the latest available date on or before CURRENT_DATE.
        rank: "best" or "worst" to sort by return; otherwise unsorted by value.
        max_rows: Row cap.
    """
    horizon_v = _resolve_horizon(frequency, horizon)
    country_list = _split_csv(countries)
    is_daily = frequency.strip().lower() == "daily"

    if is_daily:
        table = "t2_factors_daily"
        select_cols = "date, country, variable, value AS return_value"
        var_clause = "WHERE variable = ?"
        params: list[Any] = [horizon_v]
    else:
        table = "feature_panel"
        select_cols = "date, country, variable, source, value AS return_value"
        var_clause = "WHERE variable = ? AND source = 't2'"
        params = [horizon_v]

    cin, cargs = _country_in_clause(country_list)
    base_params = list(params) + list(cargs)

    date_clauses: list[str] = []
    date_args: list[Any] = []
    if start_date:
        date_clauses.append("date >= CAST(? AS DATE)")
        date_args.append(start_date)
    if end_date:
        date_clauses.append("date <= CAST(? AS DATE)")
        date_args.append(end_date)
    date_clause = ("AND " + " AND ".join(date_clauses)) if date_clauses else ""

    con = _duck_conn()
    try:
        latest_sql = f"""
            SELECT MAX(date) AS latest_date
            FROM {table}
            {var_clause}
              {cin}
              AND date <= CURRENT_DATE
              AND value IS NOT NULL
        """
        latest_row = con.execute(latest_sql, base_params).fetchone()
        latest_date = latest_row[0] if latest_row else None

        if latest_only and not date_clauses:
            main_clause = (
                f"AND date = (SELECT MAX(date) FROM {table} {var_clause} {cin} "
                f"AND date <= CURRENT_DATE AND value IS NOT NULL)"
            )
            main_params = list(base_params) + list(base_params)
        else:
            main_clause = date_clause
            main_params = list(base_params) + list(date_args)

        order_clause = "ORDER BY date DESC, country"
        if rank == "best":
            order_clause = "ORDER BY return_value DESC NULLS LAST"
        elif rank == "worst":
            order_clause = "ORDER BY return_value ASC NULLS LAST"

        sql = f"""
            SELECT {select_cols}
            FROM {table}
            {var_clause}
              {cin}
              AND value IS NOT NULL
              {main_clause}
            {order_clause}
            LIMIT {int(max_rows)}
        """
        df = con.execute(sql, main_params).fetchdf()
    finally:
        con.close()

    return _json_ready({
        "table": table,
        "source": "t2",
        "frequency": "daily" if is_daily else "monthly",
        "horizon": horizon_v,
        "latest_date": latest_date,
        "rank": rank,
        "countries_requested": country_list or "all",
        "caveat": RETURNS_CAVEATS["country_return"],
        "result": _frame_payload(df, max_rows=max_rows),
    })


@mcp.tool(
    description=(
        "Factor portfolio return series from the ASADO optimizer pipelines "
        "(top-20%-of-countries returns, NOT raw factor levels). "
        "Monthly source values: econ_optimizer, t2_optimizer, gdelt_optimizer. "
        "Daily source values: t2_optimizer_daily, gdelt_optimizer_daily."
    )
)
def factor_return_series(
    factors: str = "all",
    frequency: str = "monthly",
    source: str = "auto",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    rank: Optional[str] = None,
    window: str = "latest",
    max_rows: int = 100,
) -> dict[str, Any]:
    """Return factor portfolio returns.

    Args:
        factors: Comma-separated factor names or "all".
        frequency: "monthly" or "daily".
        source: Optimizer source. "auto" picks t2_optimizer (monthly) or t2_optimizer_daily (daily).
        start_date / end_date: Optional inclusive window (YYYY-MM-DD).
        rank: "best" or "worst" — ranks by return at the latest date (or aggregate over window).
        window: "latest" (default), "1m", "3m", "12m", "ytd", or "custom" (use start_date/end_date).
        max_rows: Row cap.
    """
    is_daily = frequency.strip().lower() == "daily"
    table = "factor_returns_daily" if is_daily else "factor_returns"
    allowed = FACTOR_RETURN_DAILY_SOURCES if is_daily else FACTOR_RETURN_MONTHLY_SOURCES

    if source == "auto":
        source = "t2_optimizer_daily" if is_daily else "t2_optimizer"
    if source not in allowed:
        raise ValueError(f"Unsupported source '{source}' for frequency '{frequency}'. Allowed: {sorted(allowed)}")

    factor_list = _split_csv(factors)
    fin, fargs = _factor_in_clause(factor_list)
    base_params: list[Any] = [source] + fargs

    con = _duck_conn()
    try:
        latest_row = con.execute(
            f"SELECT MAX(date) FROM {table} WHERE source = ? AND date <= CURRENT_DATE",
            [source],
        ).fetchone()
        latest_date = latest_row[0] if latest_row else None

        start_expr = None
        if start_date or end_date:
            window_used = "custom"
        else:
            window_used = window
            start_expr = _resolve_window_start_sql(window, "CURRENT_DATE")

        date_clauses: list[str] = []
        sql_params: list[Any] = list(base_params)
        if start_date:
            date_clauses.append("date >= CAST(? AS DATE)")
            sql_params.append(start_date)
        elif start_expr:
            date_clauses.append(f"date >= {start_expr}")
        if end_date:
            date_clauses.append("date <= CAST(? AS DATE)")
            sql_params.append(end_date)
        else:
            date_clauses.append("date <= CURRENT_DATE")

        # For rank without explicit window, default to latest snapshot ranking
        if rank in {"best", "worst"} and not (start_date or end_date) and window == "latest":
            order = "DESC" if rank == "best" else "ASC"
            sql = f"""
                SELECT date, factor, value AS factor_return, source
                FROM {table}
                WHERE source = ? {fin}
                  AND date = (SELECT MAX(date) FROM {table} WHERE source = ? AND date <= CURRENT_DATE)
                  AND value IS NOT NULL
                ORDER BY factor_return {order} NULLS LAST
                LIMIT {int(max_rows)}
            """
            df = con.execute(sql, [source] + fargs + [source]).fetchdf()
        elif rank in {"best", "worst"}:
            # Aggregate (cumulative simple sum) over window then rank
            order = "DESC" if rank == "best" else "ASC"
            where_dates = " AND ".join(date_clauses)
            sql = f"""
                SELECT factor, source, SUM(value) AS cum_return,
                       COUNT(*) AS n_obs, MIN(date) AS first_date, MAX(date) AS last_date
                FROM {table}
                WHERE source = ? {fin}
                  AND value IS NOT NULL
                  AND {where_dates}
                GROUP BY factor, source
                ORDER BY cum_return {order} NULLS LAST
                LIMIT {int(max_rows)}
            """
            df = con.execute(sql, sql_params).fetchdf()
        else:
            where_dates = " AND ".join(date_clauses)
            sql = f"""
                SELECT date, factor, value AS factor_return, source
                FROM {table}
                WHERE source = ? {fin}
                  AND value IS NOT NULL
                  AND {where_dates}
                ORDER BY factor, date
                LIMIT {int(max_rows)}
            """
            df = con.execute(sql, sql_params).fetchdf()
    finally:
        con.close()

    return _json_ready({
        "table": table,
        "source": source,
        "frequency": "daily" if is_daily else "monthly",
        "window": window_used,
        "latest_date": latest_date,
        "rank": rank,
        "factors_requested": factor_list or "all",
        "caveat": RETURNS_CAVEATS["factor_return"],
        "result": _frame_payload(df, max_rows=max_rows),
    })


@mcp.tool(
    description=(
        "Country-level factor bucket attribution: weight × factor_return for each factor "
        "where the country was in the top-20%% bucket at that date. "
        "Sources: econ_optimizer, t2_optimizer, gdelt_optimizer. Monthly only."
    )
)
def country_factor_attribution(
    country: str,
    source: str = "auto",
    date: str = "latest",
    factors: str = "all",
    rank: str = "largest_abs",
    max_rows: int = 50,
) -> dict[str, Any]:
    """Return country-factor attribution rows.

    Args:
        country: T2 country name (e.g., "Brazil").
        source: "econ_optimizer", "t2_optimizer", "gdelt_optimizer", or "auto" (=econ_optimizer).
        date: "latest" or YYYY-MM-DD month start.
        factors: Comma-separated factor names or "all".
        rank: "positive" (top positive contributions), "negative" (top negative), or "largest_abs" (default).
        max_rows: Row cap.
    """
    if source == "auto":
        source = "econ_optimizer"
    if source not in FACTOR_RETURN_MONTHLY_SOURCES:
        raise ValueError(f"Unsupported source '{source}'. Allowed: {sorted(FACTOR_RETURN_MONTHLY_SOURCES)}")

    factor_list = _split_csv(factors)
    fin, fargs = _factor_in_clause(factor_list)

    con = _duck_conn()
    try:
        # Resolve target date
        if date.strip().lower() == "latest":
            row = con.execute(
                "SELECT MAX(date) FROM country_factor_attribution "
                "WHERE source = ? AND country = ? AND date <= CURRENT_DATE",
                [source, country],
            ).fetchone()
            target_date = row[0] if row else None
            if target_date is None:
                return _json_ready({"country": country, "source": source, "result": _frame_payload(__import__("pandas").DataFrame(), max_rows), "error": "No attribution rows for that country/source."})
        else:
            target_date = date

        if rank == "positive":
            order = "ORDER BY contribution DESC NULLS LAST"
        elif rank == "negative":
            order = "ORDER BY contribution ASC NULLS LAST"
        else:
            order = "ORDER BY ABS(contribution) DESC NULLS LAST"

        sql = f"""
            SELECT date, country, factor, weight, factor_return, contribution, source
            FROM country_factor_attribution
            WHERE country = ?
              AND source = ?
              AND date = CAST(? AS DATE)
              {fin}
            {order}
            LIMIT {int(max_rows)}
        """
        df = con.execute(sql, [country, source, str(target_date)[:10]] + fargs).fetchdf()
    finally:
        con.close()

    return _json_ready({
        "country": country,
        "source": source,
        "date": str(target_date)[:10] if target_date else None,
        "rank": rank,
        "caveat": RETURNS_CAVEATS["attribution"],
        "result": _frame_payload(df, max_rows=max_rows),
    })


@mcp.tool(
    description=(
        "Return leaderboard for countries or factors. Deterministic wrapper around "
        "country_returns and factor_return_series for the most common 'who led / who lagged' questions."
    )
)
def return_leaders(
    scope: str,
    frequency: str = "monthly",
    source: str = "auto",
    horizon: Optional[str] = None,
    window: str = "latest",
    date: str = "latest",
    direction: str = "best",
    max_rows: int = 25,
) -> dict[str, Any]:
    """Return leaders or laggards for countries or factor portfolios.

    Args:
        scope: "country" or "factor".
        frequency: "monthly" or "daily".
        source: Country: ignored (T2 canonical). Factor: optimizer source or "auto".
        horizon: Country return horizon (e.g., "1MRet"). Required for scope="country".
        window: Factor-return aggregation window ("latest", "1m", "3m", "12m", "ytd").
        date: "latest" or YYYY-MM-DD.
        direction: "best" or "worst".
        max_rows: Row cap.
    """
    if scope == "country":
        return country_returns(
            countries="all",
            frequency=frequency,
            horizon=horizon,
            latest_only=(date.strip().lower() == "latest"),
            rank=direction,
            max_rows=max_rows,
        )
    if scope == "factor":
        return factor_return_series(
            factors="all",
            frequency=frequency,
            source=source,
            rank=direction,
            window=window,
            max_rows=max_rows,
        )
    raise ValueError(f"Unsupported scope '{scope}'. Use 'country' or 'factor'.")


@mcp.tool(
    description=(
        "Actual news headlines behind a T2 country's GDELT attention numbers "
        "(GDELT DOC 2.0 API, live, ~3-month window). Use when an attention/tone "
        "aggregate spikes and you need to know WHAT the news is saying. "
        "Headlines are deduped (wire repeats dropped). Evidence for reasoning "
        "only - never a mechanical trading signal."
    )
)
def country_news(
    country: str,
    days: int = 1,
    max_records: int = 50,
    extra_query: Optional[str] = None,
    english_only: bool = True,
) -> dict[str, Any]:
    """Fetch deduped article headlines for one T2 country.

    Args:
        country: Exact T2 country name (e.g., "Indonesia", "Korea", "U.S.").
            Market sleeves map to their economy (NASDAQ -> United States).
        days: Lookback window in days (default 1, max useful ~90).
        max_records: Max deduped articles returned (default 50).
        extra_query: Optional extra GDELT query terms, e.g. "lira OR central bank".
        english_only: Restrict to English-language sources (default True).
    """
    from scripts.loop.country_news import GdeltRateLimited, fetch_country_news

    try:
        return _json_ready(fetch_country_news(
            country,
            days=days,
            max_records=max_records,
            extra_query=extra_query,
            english_only=english_only,
            retries=2,
        ))
    except GdeltRateLimited as exc:
        return _json_ready({
            "country": country,
            "error": "rate_limited",
            "detail": str(exc),
            "advice": "GDELT throttles by IP. Wait 2-5 minutes and retry.",
        })


@mcp.tool(
    description=(
        "Pre-register a research hypothesis in the Alpha-Hunting Loop ledger. "
        "MUST be called before evaluate_signal - mechanism written BEFORE results. "
        "Every registration counts as a trial against its family for the deflated Sharpe."
    )
)
def register_hypothesis(
    archetype: str,
    family_key: str,
    mechanism_text: str,
    signal_table: str,
    signal_variable: str,
    signal_source: Optional[str] = None,
    author: str = "mcp",
) -> dict[str, Any]:
    """Pre-register a hypothesis.

    Args:
        archetype: A1..A7 or "other" (PRD trade archetypes).
        family_key: Groups related trials (all variants of one idea share a family).
        mechanism_text: WHY this should predict returns - one paragraph, written
            before any results are seen (>= 15 words enforced).
        signal_table: Table holding the signal (e.g. "feature_panel").
        signal_variable: Variable name (e.g. "EPU_CS").
        signal_source: Optional source filter (e.g. "epu").
        author: Attribution string.
    """
    from scripts.loop.ledgers import register_hypothesis as _register

    spec: dict[str, Any] = {"table": signal_table, "variable": signal_variable}
    if signal_source:
        spec["source"] = signal_source
    hid = _register(archetype, family_key, mechanism_text, spec, author=author)
    return {"hypothesis_id": hid, "signal_spec": spec, "status": "registered"}


@mcp.tool(
    description=(
        "Run the Alpha-Hunting Loop evaluation harness on a PRE-REGISTERED hypothesis. "
        "The only path from idea to evidence: PIT embargo, rank IC + Newey-West t-stats, "
        "top-7 portfolios vs equal-weight with costs, sub-periods, deflated Sharpe vs the "
        "family trial count. Verdict (WATCH/WEAK/DEAD/INSUFFICIENT_*) is written back to "
        "the ledger automatically. Forward-return variables (1MRet etc.) are refused."
    )
)
def evaluate_signal(
    hypothesis_id: str,
    signal_table: str,
    signal_variable: str,
    direction: str,
    signal_source: Optional[str] = None,
    frequency: str = "monthly",
    start_date: str = "2008-01-01",
    publication_lag_months: Optional[int] = None,
) -> dict[str, Any]:
    """Evaluate a pre-registered signal hypothesis.

    Args:
        hypothesis_id: From register_hypothesis (required - no anonymous backtests).
        signal_table: Table holding the signal.
        signal_variable: Variable name.
        direction: "higher_is_better" or "lower_is_better".
        signal_source: Optional source filter.
        frequency: "monthly" (full harness) or "daily" (IC-only v1).
        start_date: Backtest start (default 2008-01-01).
        publication_lag_months: Override the conservative embargo default (logged).
    """
    from scripts.harness.evaluate_signal import evaluate_signal as _evaluate

    spec: dict[str, Any] = {"table": signal_table, "variable": signal_variable}
    if signal_source:
        spec["source"] = signal_source
    if publication_lag_months is not None:
        spec["publication_lag_months"] = int(publication_lag_months)
    result = _evaluate(
        hypothesis_id=hypothesis_id,
        signal_spec=spec,
        direction=direction,
        frequency=frequency,
        start_date=start_date,
    )
    # Trim yearly tables for chat consumption; full detail is in result_file.
    slim = dict(result)
    slim["ic"] = {
        h: {k: v for k, v in blk.items() if k != "yearly_ic"}
        for h, blk in result["ic"].items()
    }
    return _json_ready(slim)


@mcp.tool(
    description=(
        "Open a trade thesis in the Alpha-Hunting Loop thesis ledger with a FROZEN "
        "entry (mechanism + invalidation), stated probability (feeds Brier calibration), "
        "and auto-marking from T2 daily returns. Paper by default."
    )
)
def open_thesis(
    entity: str,
    direction: str,
    horizon_days: int,
    entry_thesis_text: str,
    probability: float,
    invalidation_level: float,
    catalyst: str = "",
    source_dislocation_id: str = "",
    author: str = "mcp",
) -> dict[str, Any]:
    """Open a paper trade thesis.

    Args:
        entity: Exact T2 country name.
        direction: "long" or "short".
        horizon_days: Calendar days until mechanical expiry.
        entry_thesis_text: Mechanism + what would make it wrong (frozen at open).
        probability: Stated P(thesis right) in (0,1).
        invalidation_level: ADVERSE cumulative return that closes the thesis,
            negative decimal (e.g. -0.07 = stop at -7%%).
        catalyst: Optional event/catalyst reference.
        source_dislocation_id: Provenance dislocation row, if any.
        author: Attribution string.
    """
    from scripts.loop.ledgers import open_thesis as _open

    tid = _open(
        entity=entity,
        direction=direction,
        horizon_days=horizon_days,
        entry_thesis_text=entry_thesis_text,
        probability=probability,
        invalidation_level=invalidation_level,
        catalyst=catalyst,
        source_dislocation_id=source_dislocation_id,
        author=author,
        paper=True,
    )
    return {"thesis_id": tid, "status": "open", "paper": True}


def main() -> None:
    try:
        mcp.run(transport="stdio")
    except QueryAssistantError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
