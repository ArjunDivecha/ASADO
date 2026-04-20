#!/usr/bin/env python3
"""
Build schema cache artifacts for the ASADO natural-language query assistant.

This script introspects the live DuckDB and Neo4j databases, then writes a
compact JSON cache under Data/cache/query_assistant/ for LLM query planning.

Usage:
    ./venv/bin/python scripts/build_schema_registry.py
    ./venv/bin/python scripts/build_schema_registry.py --duck-only
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
import re
from typing import Any, Dict, List, Set

import duckdb
from neo4j import GraphDatabase

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.db_bridge import DB_PATH, NEO4J_PASS, NEO4J_URI, NEO4J_USER

CACHE_DIR = BASE_DIR / "Data" / "cache" / "query_assistant"
DUCKDB_SCHEMA_PATH = CACHE_DIR / "duckdb_schema.json"
NEO4J_SCHEMA_PATH = CACHE_DIR / "neo4j_schema.json"
VARIABLE_CATALOG_PATH = CACHE_DIR / "variable_catalog.json"
ACCESS_GUIDE_PATH = CACHE_DIR / "access_guide.json"
MANIFEST_PATH = CACHE_DIR / "manifest.json"

TABLE_DESCRIPTIONS = {
    "t2_master": "Original T2 monthly factor panel.",
    "t2_raw": "Raw T2 factor levels from the authoritative T2 Master workbook.",
    "country_reference": (
        "Canonical ISO-to-ASADO country mapping surface. Use this to join bilateral tables "
        "that store reporter_iso3/counterpart_iso3 onto ASADO factor surfaces that use country names."
    ),
    "external_factors": "Free-source external macro, risk, and structural data.",
    "extended_factors": "Extended country dataset built from additional free sources.",
    "gdelt_panel": "Country-level GDELT-derived media, tone, and risk signals.",
    "imf_factors": "IMF datasets normalized into the ASADO tidy panel shape.",
    "macrostructure_factors": "Macrostructure panel spanning bank fragility, debt structure, institutional depth, sticky-capital proxies, and transparent derived signals.",
    "bilateral_portfolio_matrix": (
        "Historical portfolio ownership matrix combining IMF PIP annual benchmarks and the U.S. TIC supplement. "
        "Common instrument_type values include equity_fund_shares, debt_long, debt_short, equity, debt_long_govt, and debt_long_corp."
    ),
    "bloomberg_factors": "Bloomberg market-implied, macro, and ETF passive-flow data collected via OpusBloomberg.",
    "normalized_panel": (
        "Canonical ASADO-generated normalized factors. Contains _CS same-date cross-sectional z-scores "
        "and _TS rolling time-series z-scores for eligible raw source variables."
    ),
    "feature_panel": (
        "Query-facing union of unified_panel (raw warehouse) plus normalized_panel "
        "for analytics, assistants, and feature discovery."
    ),
    "unified_panel": "Unified analytic view across all ASADO factor tables.",
}

LABEL_DESCRIPTIONS = {
    "Country": (
        "Tracked T2 universe member with metadata. The graph_role property distinguishes "
        "sovereign nodes, sovereign proxies, and market-sleeve nodes."
    ),
    "Factor": "ASADO factor/variable node aligned to the unified panel variable catalog.",
    "CentralBank": "Central bank entity linked to a country.",
    "DataSource": "Upstream source system or dataset.",
    "CrisisEvent": "Historical crisis event linked to affected countries.",
    "SanctionsProgram": "Sanctions-related node used for OFAC/SDN association queries.",
    "Commodity": "Commodity node used for export exposure edges.",
}

RELATIONSHIP_DESCRIPTIONS = {
    "HAS_FACTOR_EXPOSURE": "Latest non-null factor exposure edge per country and variable, built from DuckDB.",
    "TRADES_WITH": "Directed bilateral trade relationship.",
    "HAS_BANKING_EXPOSURE_TO": "Directed bilateral banking claims relationship.",
    "DATA_AVAILABLE_FROM": "Country coverage edge to an upstream source.",
    "HAS_CRISIS_HISTORY": "Country linked to historical crisis events.",
    "SUBJECT_TO": (
        "Country linked to OFAC/SDN-associated sanctions exposure. This is not a clean "
        "sovereign sanctions-target registry."
    ),
    "HAS_CENTRAL_BANK": "Country linked to its central bank node.",
    "EXPORT_EXPOSED_TO": "Country linked to major commodity exposure.",
}

SOURCE_TOKEN_MAP = {
    "BBG": ["bloomberg"],
    "BIS": ["bis", "bank for international settlements"],
    "ECB": ["ecb", "european central bank"],
    "EIA": ["eia", "energy information administration"],
    "FAO": ["fao", "food and agriculture organization"],
    "FRED": ["fred", "federal reserve economic data"],
    "GPR": ["gpr", "geopolitical risk"],
    "ILO": ["ilo", "international labour organization", "international labor organization"],
    "IMF": ["imf", "international monetary fund"],
    "NDGAIN": ["nd-gain", "ndgain", "climate readiness", "climate vulnerability"],
    "OECD": ["oecd"],
    "OFAC": ["ofac", "sanctions"],
    "UNDP": ["undp", "united nations development programme", "united nations development program"],
    "WB": ["world bank", "wb"],
}

TOKEN_SYNONYMS = {
    "cds": ["credit default swap", "credit default swaps", "cds spread", "cds spreads", "sovereign cds"],
    "cpi": ["consumer price index", "inflation"],
    "fragility": ["vulnerability", "stress", "fragile investor base"],
    "inflation": ["cpi", "price growth"],
    "insurance": ["insurer", "insurance corporations"],
    "investor": ["holder", "owner", "ownership base"],
    "household": ["retail", "domestic household base"],
    "ownership": ["holder base", "investor base"],
    "pension": ["retirement assets", "pension funds"],
    "yoy": ["year over year", "year-on-year", "annual change", "annual growth"],
    "gdp": ["gross domestic product", "growth"],
    "fx": ["foreign exchange", "exchange rate", "currency"],
    "xrate": ["exchange rate", "fx", "currency"],
    "bond": ["government bond", "sovereign bond", "yield"],
    "yield": ["rate"],
    "ois": ["overnight index swap", "swap rate"],
    "wirp": ["implied policy rate", "policy expectations"],
    "pmi": ["purchasing managers index", "manufacturing survey", "services survey"],
    "m2": ["money supply", "broad money"],
    "breakeven": ["inflation breakeven", "inflation expectations"],
    "zspread": ["z-spread", "spread over ois", "credit spread"],
    "reer": ["real effective exchange rate"],
    "policy": ["policy rate"],
    "credit": ["lending"],
    "gap": ["deviation"],
    "trade": ["exports and imports", "external trade"],
    "exports": ["export"],
    "imports": ["import"],
    "debt": ["indebtedness"],
    "holder": ["owner", "investor"],
    "foreign": ["external", "offshore"],
    "local": ["domestic", "home currency"],
    "currency": ["fx denomination", "domestic currency", "foreign currency"],
    "maturity": ["tenor", "duration bucket", "rollover"],
    "qpsd": ["quarterly public sector debt", "public debt structure", "debt holder structure"],
    "tic": ["treasury international capital", "u.s. treasury tic", "us foreign holdings"],
    "portfolio": ["portfolio ownership", "cross-border holdings", "investor base"],
    "etf": ["exchange traded fund", "fund proxy", "country etf"],
    "passive": ["index-driven", "mechanical flows", "passive flows"],
    "creation": ["primary market basket", "creation basket", "shares outstanding"],
    "redemption": ["redeem basket", "redemption basket"],
    "swap": ["liquidity swap", "swap line", "central bank swap"],
    "unemployment": ["jobless rate"],
    "employment": ["jobs", "labor market", "labour market"],
    "population": ["population level"],
    "current": ["external balance"],
    "account": ["balance of payments", "bop"],
    "metronome": ["metronome signal"],
    "risk": ["risk signal"],
    "sentiment": ["tone", "news sentiment"],
    "attention": ["news attention", "media attention"],
    "tone": ["sentiment"],
    "pe": ["price earnings", "p/e", "valuation"],
    "pbk": ["price to book", "p/b", "book value"],
    "roe": ["return on equity"],
    "eps": ["earnings per share"],
    "ebitda": ["enterprise value to ebitda"],
    "mcap": ["market cap", "market capitalization"],
    "vol": ["volatility"],
    "ret": ["return", "performance"],
    "tr": ["total return"],
}

SOURCE_FREQUENCIES = {
    "bis_credit": "quarterly",
    "bis_debt_service": "quarterly",
    "bis_policy_rate": "daily",
    "bis_property": "quarterly",
    "bis_reer": "monthly",
    "bloomberg": "monthly",
    "ecb_fx": "monthly",
    "eia": "annual",
    "epu": "monthly",
    "faostat": "annual",
    "fred": "monthly",
    "gdelt": "monthly",
    "gpr": "monthly",
    "ilostat": "annual",
    "imf_bop": "annual",
    "imf_cpi": "monthly",
    "imf_er": "monthly",
    "imf_fsi": "quarterly",
    "imf_itg": "monthly",
    "imf_ls": "monthly",
    "imf_mfs_ir": "monthly",
    "macrostructure_derived": "quarterly",
    "imf_weo": "annual",
    "ndgain": "annual",
    "oecd": "monthly",
    "oecd_bci": "monthly",
    "oecd_cci": "monthly",
    "oecd_household_dashboard": "annual",
    "oecd_institutional_investors": "quarterly",
    "ofac": "event-driven",
    "portfolio_ownership": "annual",
    "qpsd": "quarterly",
    "t2": "monthly",
    "t2_raw": "monthly",
    "undp_hdi": "annual",
    "worldbank": "annual",
}

FRESHNESS_THRESHOLDS = {
    "daily": 45,
    "monthly": 120,
    "quarterly": 220,
    "annual": 550,
    "event-driven": 365,
    "snapshot": 550,
}

FORECAST_SOURCES = {"imf_weo"}
FORECAST_VARIABLE_PREFIXES = ("BBG_ECFC_",)
GLOBAL_REFERENCE_VARIABLES = {"FRED_UST_2Y", "FRED_UST_10Y", "FRED_Yield_Curve_10Y2Y"}
HOME_CURRENCY_REFERENCE_PREFIX = "ECB_FX_"


def _clean_display_name(variable: str) -> str:
    return re.sub(r"\s+", " ", variable.replace("_", " ")).strip()


def _tokenize(text: str) -> List[str]:
    return [token for token in re.split(r"[^a-z0-9]+", text.lower()) if token]


def _expand_token(token: str) -> Set[str]:
    expanded = {token}
    expanded.update(TOKEN_SYNONYMS.get(token, []))
    if token in SOURCE_TOKEN_MAP:
        expanded.update(SOURCE_TOKEN_MAP[token])
    return expanded


def _variable_aliases(variable: str, source: str) -> List[str]:
    aliases: Set[str] = set()
    aliases.add(variable)
    aliases.add(_clean_display_name(variable))

    tokens = variable.split("_")
    clean_tokens = [token.strip() for token in tokens if token.strip()]
    lower_tokens = [token.lower() for token in clean_tokens]

    for token in clean_tokens:
        aliases.add(token)
        aliases.add(token.lower())

    expanded_phrases: Set[str] = set()
    for token in clean_tokens:
        expanded_phrases.update(_expand_token(token.lower()))
        if token in SOURCE_TOKEN_MAP:
            expanded_phrases.update(SOURCE_TOKEN_MAP[token])
    aliases.update(expanded_phrases)

    if variable.startswith("BBG_"):
        base = variable.removeprefix("BBG_")
        aliases.add(f"bloomberg {_clean_display_name(base)}")
        aliases.add(_clean_display_name(base))
    if variable.startswith("IMF_"):
        base = variable.removeprefix("IMF_")
        aliases.add(f"imf {_clean_display_name(base)}")
        aliases.add(_clean_display_name(base))
    if variable.startswith("WB_"):
        base = variable.removeprefix("WB_")
        aliases.add(f"world bank {_clean_display_name(base)}")
        aliases.add(_clean_display_name(base))

    if "cds" in lower_tokens:
        aliases.update({"current cds", "sovereign cds", "5y cds", "5 year cds", "credit spread"})
    if "cpi" in lower_tokens or "inflation" in lower_tokens:
        aliases.update({"inflation rate", "cpi inflation", "consumer inflation"})
    if "pmi" in lower_tokens:
        aliases.update({"pmi", "purchasing managers index"})
    if "bond" in lower_tokens and any(t in lower_tokens for t in ("10y", "5y", "2y", "30y")):
        tenor = next((t for t in lower_tokens if t in {"2y", "5y", "10y", "30y"}), "")
        if tenor:
            aliases.update({
                f"{tenor} government bond yield",
                f"{tenor.replace('y', '-year')} government bond yield",
            })
    if "xrate" in lower_tokens or "fx" in lower_tokens:
        aliases.update({"exchange rate", "fx rate", "currency rate"})
    if "unemployment" in lower_tokens:
        aliases.add("unemployment rate")
    if "population" in lower_tokens:
        aliases.add("population")

    if source:
        aliases.add(source)
        aliases.add(source.replace("_", " "))
        aliases.add(f"{source} {_clean_display_name(variable)}")

    return sorted({alias.strip() for alias in aliases if alias and alias.strip()})


def _normalization_type(variable: str) -> str:
    if variable.endswith("_CS"):
        return "cs"
    if variable.endswith("_TS"):
        return "ts"
    return "raw"


def _base_variable_name(variable: str) -> str:
    if variable.endswith("_CS") or variable.endswith("_TS"):
        return variable[:-3]
    return variable


def _freshness_days(last_date: Any) -> int | None:
    if last_date is None:
        return None
    if isinstance(last_date, datetime):
        last_day = last_date.date()
    elif isinstance(last_date, date):
        last_day = last_date
    else:
        try:
            last_day = datetime.fromisoformat(str(last_date)).date()
        except ValueError:
            return None
    return (date.today() - last_day).days


def _series_scope(variable: str) -> str:
    if variable in GLOBAL_REFERENCE_VARIABLES:
        return "global_reference"
    if variable.startswith(HOME_CURRENCY_REFERENCE_PREFIX):
        return "home_currency_reference"
    return "country_specific"


def _is_forecast_series(variable: str, source: str) -> bool:
    return source in FORECAST_SOURCES or variable.startswith(FORECAST_VARIABLE_PREFIXES)


def _question_variable_candidates(question: str, variable_alias_map: Dict[str, List[str]], top_n: int = 12) -> List[Dict[str, Any]]:
    question_text = question.lower()
    question_tokens = set(_tokenize(question_text))
    scored: List[Dict[str, Any]] = []

    for variable, aliases in variable_alias_map.items():
        alias_tokens: Set[str] = set()
        score = 0.0
        matched_aliases: List[str] = []

        for alias in aliases:
            alias_lower = alias.lower()
            tokens = set(_tokenize(alias_lower))
            alias_tokens.update(tokens)
            if alias_lower and alias_lower in question_text:
                matched_aliases.append(alias)
                score += 8.0 if len(alias_lower) > 6 else 4.0
            overlap = question_tokens & tokens
            if overlap:
                score += 1.25 * len(overlap)

        if score <= 0:
            continue

        if variable.lower() in question_text:
            score += 10.0

        scored.append(
            {
                "variable": variable,
                "score": round(score, 2),
                "matched_aliases": matched_aliases[:6],
                "shared_tokens": sorted(question_tokens & alias_tokens),
            }
        )

    scored.sort(key=lambda row: (-row["score"], row["variable"]))
    return scored[:top_n]


def _json_ready(value: Any) -> Any:
    """Recursively convert values into JSON-serializable primitives."""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if hasattr(value, "iso_format"):
        try:
            return value.iso_format()
        except Exception:
            pass
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(v) for v in value]
    return value


def _next_month_start(anchor: date) -> date:
    if anchor.month == 12:
        return date(anchor.year + 1, 1, 1)
    return date(anchor.year, anchor.month + 1, 1)


def _fetch_sample_rows(con: duckdb.DuckDBPyConnection, table_name: str) -> List[Dict[str, Any]]:
    query = f'SELECT * FROM "{table_name}" LIMIT 5'
    return [_json_ready(row) for row in con.execute(query).fetchdf().to_dict("records")]


def _column_value_samples(
    con: duckdb.DuckDBPyConnection,
    table_name: str,
    column_names: Set[str],
) -> Dict[str, List[Any]]:
    """Capture distinct value hints for key categorical columns used in NL planning."""
    sample_columns = {"instrument_type", "source", "frequency"}
    samples: Dict[str, List[Any]] = {}

    for column_name in sorted(sample_columns & column_names):
        values = [
            row[0]
            for row in con.execute(
                f'SELECT DISTINCT "{column_name}" FROM "{table_name}" '
                f'WHERE "{column_name}" IS NOT NULL ORDER BY "{column_name}" LIMIT 20'
            ).fetchall()
        ]
        if values:
            samples[column_name] = [_json_ready(value) for value in values]

    return samples


def _duckdb_table_schema(con: duckdb.DuckDBPyConnection, table_name: str, table_type: str) -> Dict[str, Any]:
    columns_df = con.execute(
        """
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'main' AND table_name = ?
        ORDER BY ordinal_position
        """,
        [table_name],
    ).fetchdf()

    columns = columns_df.to_dict("records")
    column_names = {c["column_name"] for c in columns}
    row_count = con.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]

    summary: Dict[str, Any] = {
        "name": table_name,
        "table_type": table_type,
        "description": TABLE_DESCRIPTIONS.get(table_name, ""),
        "row_count": row_count,
        "columns": columns,
        "sample_rows": _fetch_sample_rows(con, table_name),
        "column_value_samples": _column_value_samples(con, table_name, column_names),
    }

    if "date" in column_names:
        min_date, max_date = con.execute(
            f'SELECT MIN(date), MAX(date) FROM "{table_name}"'
        ).fetchone()
        summary["date_range"] = {
            "min": _json_ready(min_date),
            "max": _json_ready(max_date),
        }

    if "country" in column_names:
        summary["country_count"] = con.execute(
            f'SELECT COUNT(DISTINCT country) FROM "{table_name}"'
        ).fetchone()[0]

    if "variable" in column_names:
        summary["variable_count"] = con.execute(
            f'SELECT COUNT(DISTINCT variable) FROM "{table_name}"'
        ).fetchone()[0]
        summary["sample_variables"] = [
            row[0]
            for row in con.execute(
                f'SELECT DISTINCT variable FROM "{table_name}" ORDER BY variable LIMIT 25'
            ).fetchall()
        ]

    return _json_ready(summary)


def build_duckdb_schema(db_path: Path = DB_PATH) -> Dict[str, Any]:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = con.execute(
            """
            SELECT table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = 'main'
            ORDER BY table_name
            """
        ).fetchall()

        schema_tables = {
            table_name: _duckdb_table_schema(con, table_name, table_type)
            for table_name, table_type in tables
        }

        indexes = []
        try:
            idx_df = con.execute(
                """
                SELECT index_name, table_name, expressions
                FROM duckdb_indexes()
                ORDER BY table_name, index_name
                """
            ).fetchdf()
            indexes = idx_df.to_dict("records")
        except Exception:
            indexes = []

        countries = []
        factor_surface = "feature_panel" if "feature_panel" in schema_tables else "unified_panel"
        if factor_surface in schema_tables:
            countries = [
                row[0]
                for row in con.execute(
                    f"SELECT DISTINCT country FROM {factor_surface} ORDER BY country"
                ).fetchall()
            ]

        return _json_ready(
            {
                "available": True,
                "db_path": db_path,
                "factor_surface": factor_surface,
                "tables": schema_tables,
                "indexes": indexes,
                "countries": countries,
            }
        )
    finally:
        con.close()


def build_variable_catalog(db_path: Path = DB_PATH) -> Dict[str, Any]:
    con = duckdb.connect(str(db_path), read_only=True)
    try:
        tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
        factor_surface = "feature_panel" if "feature_panel" in tables else "unified_panel"
        catalog_df = con.execute(
            f"""
            SELECT
                variable,
                source,
                COUNT(*) AS row_count,
                COUNT(DISTINCT country) AS country_count,
                MIN(date) AS first_date,
                MAX(date) AS last_date
            FROM {factor_surface}
            GROUP BY variable, source
            ORDER BY variable, source
            """
        ).fetchdf()

        variable_metadata: Dict[str, Dict[str, Any]] = {}
        for variable, group in catalog_df.groupby("variable", sort=True):
            source = str(group["source"].iloc[0])
            row_count = int(group["row_count"].sum())
            country_count = int(group["country_count"].max())
            first_date = group["first_date"].min()
            last_date = group["last_date"].max()
            frequency = SOURCE_FREQUENCIES.get(source, "monthly")
            freshness_days = _freshness_days(last_date)
            freshness_threshold = FRESHNESS_THRESHOLDS.get(frequency, 180)
            variable_metadata[variable] = _json_ready(
                {
                    "variable": variable,
                    "display_name": _clean_display_name(variable),
                    "base_variable": _base_variable_name(variable),
                    "source": source,
                    "row_count": row_count,
                    "country_count": country_count,
                    "first_date": first_date,
                    "last_date": last_date,
                    "frequency": frequency,
                    "freshness_days": freshness_days,
                    "freshness_threshold_days": freshness_threshold,
                    "is_stale": freshness_days is not None and freshness_days > freshness_threshold,
                    "is_sparse": country_count <= 2,
                    "is_forecast": _is_forecast_series(variable, source),
                    "normalization": _normalization_type(variable),
                    "series_scope": _series_scope(variable),
                }
            )

        alias_map = {
            variable: _variable_aliases(
                variable=variable,
                source=group["source"].iloc[0],
            )
            for variable, group in catalog_df.groupby("variable", sort=True)
        }

        return _json_ready(
            {
                "available": True,
                "factor_surface": factor_surface,
                "variable_count": int(catalog_df["variable"].nunique()),
                "variables": catalog_df.to_dict("records"),
                "variable_names": sorted(catalog_df["variable"].unique().tolist()),
                "variable_aliases": alias_map,
                "variable_metadata": variable_metadata,
            }
        )
    finally:
        con.close()


def build_neo4j_schema(
    neo4j_uri: str = NEO4J_URI,
    neo4j_user: str = NEO4J_USER,
    neo4j_pass: str = NEO4J_PASS,
) -> Dict[str, Any]:
    try:
        driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_pass))
        driver.verify_connectivity()
    except Exception as exc:
        return {
            "available": False,
            "uri": neo4j_uri,
            "error": str(exc),
            "labels": {},
            "relationships": {},
            "indexes": [],
        }

    try:
        with driver.session() as session:
            labels = [
                row["label"]
                for row in session.run(
                    "CALL db.labels() YIELD label RETURN label ORDER BY label"
                )
            ]
            rel_types = [
                row["relationshipType"]
                for row in session.run(
                    """
                    CALL db.relationshipTypes() YIELD relationshipType
                    RETURN relationshipType
                    ORDER BY relationshipType
                    """
                )
            ]

            label_schema = {}
            for label in labels:
                count = session.run(
                    f"MATCH (n:`{label}`) RETURN COUNT(n) AS count"
                ).single()["count"]
                prop_rows = session.run(
                    f"""
                    MATCH (n:`{label}`)
                    UNWIND keys(n) AS key
                    RETURN key, COUNT(*) AS frequency
                    ORDER BY frequency DESC, key
                    """
                ).data()
                sample = session.run(
                    f"MATCH (n:`{label}`) RETURN properties(n) AS props LIMIT 1"
                ).single()
                label_schema[label] = {
                    "description": LABEL_DESCRIPTIONS.get(label, ""),
                    "count": count,
                    "properties": prop_rows,
                    "sample": _json_ready(sample["props"]) if sample else {},
                }

            rel_schema = {}
            for rel_type in rel_types:
                count = session.run(
                    f"MATCH ()-[r:`{rel_type}`]->() RETURN COUNT(r) AS count"
                ).single()["count"]
                prop_rows = session.run(
                    f"""
                    MATCH ()-[r:`{rel_type}`]->()
                    UNWIND keys(r) AS key
                    RETURN key, COUNT(*) AS frequency
                    ORDER BY frequency DESC, key
                    """
                ).data()
                sample = session.run(
                    f"""
                    MATCH (a)-[r:`{rel_type}`]->(b)
                    RETURN labels(a) AS source_labels,
                           labels(b) AS target_labels,
                           properties(r) AS props
                    LIMIT 1
                    """
                ).single()
                rel_schema[rel_type] = {
                    "description": RELATIONSHIP_DESCRIPTIONS.get(rel_type, ""),
                    "count": count,
                    "properties": prop_rows,
                    "source_labels": sample["source_labels"] if sample else [],
                    "target_labels": sample["target_labels"] if sample else [],
                    "sample": _json_ready(sample["props"]) if sample else {},
                }

            indexes = session.run(
                """
                SHOW INDEXES
                YIELD name, type, entityType, labelsOrTypes, properties, options
                RETURN name, type, entityType, labelsOrTypes, properties, options
                ORDER BY name
                """
            ).data()

            return _json_ready(
                {
                    "available": True,
                    "uri": neo4j_uri,
                    "labels": label_schema,
                    "relationships": rel_schema,
                    "indexes": indexes,
                }
            )
    finally:
        driver.close()


def build_access_guide(
    duckdb_schema: Dict[str, Any],
    neo4j_schema: Dict[str, Any],
    variable_catalog: Dict[str, Any],
) -> Dict[str, Any]:
    current_date = date.today()
    gdelt_partial_label_date = _next_month_start(current_date)
    duck_tables = duckdb_schema.get("tables", {})
    factor_surface = variable_catalog.get("factor_surface") or duckdb_schema.get("factor_surface") or "unified_panel"

    return _json_ready(
        {
            "project": "ASADO",
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "purpose": (
                "Agent-facing access contract for the live ASADO DuckDB, Neo4j, and "
                "schema-cache artifacts. Use this as the first-stop machine-readable "
                "guide for how to access the database safely."
            ),
            "preferred_access_order": [
                "python_bridge",
                "duckdb_sql",
                "query_assistant",
                "neo4j_cypher",
            ],
            "artifacts": {
                "base_dir": str(BASE_DIR),
                "duckdb_path": str(DB_PATH),
                "neo4j_uri": NEO4J_URI,
                "duckdb_schema_path": str(DUCKDB_SCHEMA_PATH),
                "neo4j_schema_path": str(NEO4J_SCHEMA_PATH),
                "variable_catalog_path": str(VARIABLE_CATALOG_PATH),
                "primary_factor_view": factor_surface,
                "python_bridge_module": "scripts.db_bridge",
                "query_assistant_script": str(BASE_DIR / "scripts" / "query_assistant.py"),
                "normalized_builder_script": str(BASE_DIR / "scripts" / "build_normalized_panel.py"),
                "macrostructure_formula_catalog_path": str(
                    BASE_DIR / "Data" / "processed" / "macrostructure_formula_catalog.json"
                ),
                "panel_variable_catalog_paths": {
                    "external": str(BASE_DIR / "Data" / "processed" / "external_variable_catalog.csv"),
                    "extended": str(BASE_DIR / "Data" / "processed" / "extended_variable_catalog.csv"),
                    "imf": str(BASE_DIR / "Data" / "processed" / "imf_variable_catalog.csv"),
                    "macrostructure": str(BASE_DIR / "Data" / "processed" / "macrostructure_variable_catalog.csv"),
                    "bloomberg": str(BASE_DIR / "Data" / "processed" / "bloomberg_variable_catalog.csv"),
                },
            },
            "connections": {
                "python_bridge": {
                    "preferred": True,
                    "module": "scripts.db_bridge",
                    "class": "AsadoDB",
                    "duckdb_method": "query_panel(sql)",
                    "neo4j_method": "query_graph(cypher)",
                    "notes": [
                        "Best default entrypoint for agents because it exposes both DuckDB and Neo4j.",
                        "Use context-manager style: with AsadoDB() as db: ...",
                    ],
                },
                "duckdb_sql": {
                    "type": "duckdb_file",
                    "path": str(DB_PATH),
                    "read_only_recommended": True,
                    "preferred_entrypoint": "scripts.db_bridge.AsadoDB.query_panel",
                    "primary_view": factor_surface,
                    "canonical_factor_columns": ["date", "country", "value", "variable", "source"],
                    "tables_available": sorted(duck_tables.keys()),
                    "primary_view_row_count": duck_tables.get(factor_surface, {}).get("row_count"),
                    "primary_view_variable_count": variable_catalog.get("variable_count"),
                    "notes": [
                        f"Use {factor_surface} for most cross-source factor questions.",
                        "Use unified_panel when you explicitly want the raw warehouse without generated normalized variants.",
                        "Use country_reference to map ISO3 codes in bilateral tables onto canonical ASADO country names.",
                        "Use table-specific panels when you need source-specific behavior or panel-specific columns.",
                    ],
                },
                "neo4j_cypher": {
                    "type": "neo4j_bolt",
                    "uri": NEO4J_URI,
                    "username": NEO4J_USER,
                    "password": NEO4J_PASS,
                    "available": neo4j_schema.get("available", False),
                    "preferred_entrypoint": "scripts.db_bridge.AsadoDB.query_graph",
                    "labels_available": sorted((neo4j_schema.get("labels") or {}).keys()),
                    "relationships_available": sorted((neo4j_schema.get("relationships") or {}).keys()),
                    "notes": [
                        "Use Neo4j for relationship and network questions: trade, banking, portfolio ownership, crises, central banks, and factor-node traversals.",
                        "Country nodes include graph_role to distinguish sovereign states from market sleeves.",
                    ],
                },
                "query_assistant": {
                    "type": "schema_aware_nl_query_layer",
                    "script": str(BASE_DIR / "scripts" / "query_assistant.py"),
                    "schema_cache_dir": str(CACHE_DIR),
                    "rebuild_command": "./venv/bin/python scripts/build_schema_registry.py",
                    "preferred_for": [
                        "natural-language questions",
                        "safe read-only query planning",
                        "mixed DuckDB + Neo4j routing",
                    ],
                },
            },
            "surface_selection": [
                {
                    "surface": factor_surface,
                    "use_for": "Primary query-facing factor surface across raw and normalized analytics rows.",
                },
                {
                    "surface": "unified_panel",
                    "use_for": "Raw warehouse only. Use when you explicitly do not want generated normalized variants.",
                },
                {
                    "surface": "normalized_panel",
                    "use_for": "Canonical ASADO-generated _CS and _TS feature rows with explicit normalization metadata.",
                },
                {
                    "surface": "country_reference",
                    "use_for": "Canonical ISO3-to-ASADO join table for bilateral ownership/trade/banking queries.",
                },
                {
                    "surface": "gdelt_panel",
                    "use_for": "Raw GDELT-only questions, especially latest/current questions using the GDELT partial-month label convention.",
                },
                {
                    "surface": "bilateral_portfolio_matrix",
                    "use_for": "Reporter/counterparty/instrument portfolio ownership questions.",
                },
                {
                    "surface": "Neo4j graph",
                    "use_for": "Network and relationship questions across trade, banking, portfolio, crises, sanctions, and central-bank links.",
                },
            ],
            "special_cases": {
                "current_date": current_date.isoformat(),
                "gdelt_partial_month_label": {
                    "enabled": True,
                    "applies_to_source": "gdelt",
                    "current_partial_label_date": gdelt_partial_label_date.isoformat(),
                    "description": (
                        "ASADO's GDELT monthly partial updates may use the first day of the next month "
                        "as the label for the current partial month. Treat this as observed current-month "
                        "data, not a forecast, when the query is explicitly about GDELT."
                    ),
                },
                "bilateral_portfolio_matrix_shape": {
                    "description": (
                        "This table is not in the standard factor-panel shape. It uses reporter_iso3, "
                        "counterpart_iso3, instrument_type, and amount_usd rather than country/value/variable."
                    )
                },
            },
            "examples": {
                "python_bridge": (
                    "from scripts.db_bridge import AsadoDB\n"
                    "with AsadoDB() as db:\n"
                    f"    df = db.query_panel(\"SELECT country, value, date FROM {factor_surface} "
                    "WHERE variable = 'BIS_Credit_GDP_Gap' ORDER BY date DESC LIMIT 10\")"
                ),
                "duckdb_sql": (
                    "WITH latest_portfolio AS (\n"
                    "  SELECT counterpart_iso3, SUM(amount_usd) AS total_holdings\n"
                    "  FROM bilateral_portfolio_matrix\n"
                    "  WHERE reporter_iso3 = 'USA'\n"
                    "  GROUP BY counterpart_iso3\n"
                    ")\n"
                    "SELECT cr.country, lp.total_holdings\n"
                    "FROM latest_portfolio lp\n"
                    "JOIN country_reference cr ON lp.counterpart_iso3 = cr.iso3\n"
                    "ORDER BY lp.total_holdings DESC\n"
                    "LIMIT 10"
                ),
                "neo4j_cypher": (
                    "MATCH (c:Country)-[r:TRADES_WITH]->(p:Country)\n"
                    "RETURN c.t2_name AS country, p.t2_name AS partner, r.total_trade_usd\n"
                    "ORDER BY r.total_trade_usd DESC\n"
                    "LIMIT 25"
                ),
                "query_assistant": (
                    "./venv/bin/python scripts/query_assistant.py "
                    "\"Which countries have rising GDELT risk but low ETF passive distortion?\""
                ),
            },
            "operational_commands": {
                "build_normalized_features": "./venv/bin/python scripts/build_normalized_panel.py",
                "refresh_schema_cache": "./venv/bin/python scripts/build_schema_registry.py",
                "rebuild_databases_only": "./venv/bin/python scripts/monthly_update.py --db-only",
                "full_monthly_update": "./venv/bin/python scripts/monthly_update.py",
            },
            "guardrails": [
                "Prefer read-only access patterns.",
                "Use SELECT/CTE only for DuckDB queries.",
                "Use MATCH/CALL/WITH/RETURN only for Neo4j queries.",
                f"Prefer {factor_surface} unless a panel-specific table is clearly better.",
                "For joins from bilateral tables onto factor panels, join reporter_iso3/counterpart_iso3 to country_reference.iso3 and then join country_reference.country to the factor surface country column.",
                "For latest/current questions, constrain to dates on or before CURRENT_DATE unless the query explicitly concerns forecasts or the GDELT partial-month convention.",
            ],
        }
    )


def build_and_write_schema_cache(duck_only: bool = False) -> Dict[str, Any]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    duckdb_schema = build_duckdb_schema()
    variable_catalog = build_variable_catalog()
    neo4j_schema = build_neo4j_schema() if not duck_only else {
        "available": False,
        "uri": NEO4J_URI,
        "error": "Skipped via --duck-only",
        "labels": {},
        "relationships": {},
        "indexes": [],
    }
    access_guide = build_access_guide(duckdb_schema, neo4j_schema, variable_catalog)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "duckdb_path": str(DB_PATH),
        "neo4j_uri": NEO4J_URI,
        "cache_dir": str(CACHE_DIR),
        "duckdb_schema_path": str(DUCKDB_SCHEMA_PATH),
        "neo4j_schema_path": str(NEO4J_SCHEMA_PATH),
        "variable_catalog_path": str(VARIABLE_CATALOG_PATH),
        "access_guide_path": str(ACCESS_GUIDE_PATH),
    }

    DUCKDB_SCHEMA_PATH.write_text(json.dumps(duckdb_schema, indent=2), encoding="utf-8")
    NEO4J_SCHEMA_PATH.write_text(json.dumps(neo4j_schema, indent=2), encoding="utf-8")
    VARIABLE_CATALOG_PATH.write_text(json.dumps(variable_catalog, indent=2), encoding="utf-8")
    ACCESS_GUIDE_PATH.write_text(json.dumps(access_guide, indent=2), encoding="utf-8")
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "manifest": manifest,
        "duckdb": duckdb_schema,
        "neo4j": neo4j_schema,
        "variable_catalog": variable_catalog,
        "access_guide": access_guide,
    }


def load_schema_cache(auto_build: bool = True) -> Dict[str, Any]:
    paths = [DUCKDB_SCHEMA_PATH, NEO4J_SCHEMA_PATH, VARIABLE_CATALOG_PATH, ACCESS_GUIDE_PATH, MANIFEST_PATH]
    if auto_build and not all(path.exists() for path in paths):
        return build_and_write_schema_cache()

    return {
        "manifest": json.loads(MANIFEST_PATH.read_text(encoding="utf-8")),
        "duckdb": json.loads(DUCKDB_SCHEMA_PATH.read_text(encoding="utf-8")),
        "neo4j": json.loads(NEO4J_SCHEMA_PATH.read_text(encoding="utf-8")),
        "variable_catalog": json.loads(VARIABLE_CATALOG_PATH.read_text(encoding="utf-8")),
        "access_guide": json.loads(ACCESS_GUIDE_PATH.read_text(encoding="utf-8")),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build ASADO schema cache artifacts")
    parser.add_argument(
        "--duck-only",
        action="store_true",
        help="Skip Neo4j introspection and only build DuckDB cache files.",
    )
    args = parser.parse_args()

    payload = build_and_write_schema_cache(duck_only=args.duck_only)
    duck_tables = len(payload["duckdb"]["tables"])
    neo_labels = len(payload["neo4j"].get("labels", {}))
    print(f"Schema cache written to {CACHE_DIR}")
    print(f"  DuckDB tables/views: {duck_tables}")
    print(f"  Variables: {payload['variable_catalog']['variable_count']}")
    if payload["neo4j"].get("available"):
        print(f"  Neo4j labels: {neo_labels}")
    else:
        print(f"  Neo4j unavailable: {payload['neo4j'].get('error', 'unknown error')}")


if __name__ == "__main__":
    main()
