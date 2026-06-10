#!/usr/bin/env python3
"""
ASADO natural-language query assistant.

This module provides a schema-aware, read-only query layer on top of the
existing AsadoDB bridge. It supports:

- natural-language -> structured query plan
- DuckDB SQL execution
- Neo4j Cypher execution
- limited hybrid orchestration via {{country_list}} placeholder
- result interpretation and local query logging

Usage:
    ./venv/bin/python scripts/query_assistant.py "Which countries have high BIS credit gaps?"
    ./venv/bin/python scripts/query_assistant.py --preview-only "Show me crisis history for Turkey"
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from scripts.build_schema_registry import CACHE_DIR, build_and_write_schema_cache, load_schema_cache
from scripts.db_bridge import AsadoDB

LOG_DIR = BASE_DIR / "Data" / "logs" / "query_assistant"

PLAN_FORMAT = {
    "understanding": "short restatement of the question",
    "query_mode": "duckdb | neo4j | hybrid | clarify",
    "confidence": "number between 0 and 1",
    "clarification_question": "null or a short question",
    "tables_or_labels": ["relevant DuckDB tables, Neo4j labels, or relationship types"],
    "reasoning_summary": "1-3 sentence planning summary",
    "expected_output": "what the result should contain",
    "warnings": ["list of caveats or empty list"],
    "duckdb_sql": "read-only SQL or null",
    "neo4j_cypher": "read-only Cypher or null",
    "hybrid_steps": [
        {
            "engine": "duckdb or neo4j",
            "query": "read-only query string; if a later step needs countries from an earlier step, use {{country_list}}",
            "result_key": "optional result key such as country_list",
        }
    ],
    "return_surface_used": (
        "country_returns | factor_returns | factor_returns_daily | "
        "country_factor_attribution | event_window | none"
    ),
    "return_surface_reason": "why this surface is or is not used for this question",
}

# Return-intent vocabulary — questions matching these phrases should route to a
# return surface (country_returns / factor_returns / attribution / event_window)
# by default unless the user explicitly wants non-return data only.
RETURN_INTENT_PHRASES = (
    "return", "returns", "performance", "perform",
    "winner", "winners", "loser", "losers",
    "leader", "leaders", "laggard", "laggards",
    "best", "worst",
    "worked", "did not work", "didn't work",
    "helped", "hurt",
    "beneficiar", "benefit", "benefited",
    "happened", "happens", "event reaction", "crisis impact",
    "analog outcome", "which signal matters", "signals worked",
    "did this factor work", "payoff", "p&l", "pnl", "attribution",
)

# Return-surface table names we recognize in plans
RETURN_TABLES = {
    "factor_returns",
    "factor_returns_daily",
    "factor_top20_membership",
    "country_factor_attribution",
}

SQL_BLOCKLIST = (
    "insert", "update", "delete", "drop", "alter", "create", "copy",
    "attach", "detach", "pragma", "vacuum", "export", "call",
)
CYPHER_BLOCKLIST = (
    "create", "merge", "delete", "detach", "remove", "set",
    "load csv", "apoc.periodic", "apoc.load", "db.create",
)

MARKET_SLEEVE_COUNTRIES = {"ChinaH", "NASDAQ", "US SmallCap"}
SANCTIONS_WARNING = (
    "ASADO's sanctions layer reflects OFAC/SDN-linked country associations, "
    "not a clean sovereign sanctions-target registry."
)
CURRENT_DATE = date.today()


def _next_month_start(anchor: date) -> date:
    if anchor.month == 12:
        return date(anchor.year + 1, 1, 1)
    return date(anchor.year, anchor.month + 1, 1)


GDELT_PARTIAL_LABEL_DATE = _next_month_start(CURRENT_DATE)
GDELT_PARTIAL_LABEL_NOTE = (
    "ASADO's GDELT monthly partial updates may use the first day of the next month "
    f"as the label; for CURRENT_DATE={CURRENT_DATE.isoformat()}, treat "
    f"{GDELT_PARTIAL_LABEL_DATE.isoformat()} as the current partial-month GDELT label, not a forecast."
)

COUNTRY_GROUPS: Dict[str, List[str]] = {
    "asean": ["Indonesia", "Malaysia", "Philippines", "Singapore", "Thailand", "Vietnam"],
    "g7": ["Canada", "France", "Germany", "Italy", "Japan", "U.K.", "U.S."],
    "brics": ["Brazil", "ChinaA", "India", "South Africa"],
    "latam": ["Brazil", "Chile", "Mexico"],
    "latin america": ["Brazil", "Chile", "Mexico"],
    "emea": [
        "Denmark",
        "France",
        "Germany",
        "Italy",
        "Netherlands",
        "Poland",
        "Saudi Arabia",
        "South Africa",
        "Spain",
        "Sweden",
        "Switzerland",
        "Turkey",
        "U.K.",
    ],
    "em": [
        "Brazil",
        "Chile",
        "ChinaA",
        "India",
        "Indonesia",
        "Korea",
        "Malaysia",
        "Mexico",
        "Philippines",
        "Poland",
        "Saudi Arabia",
        "South Africa",
        "Taiwan",
        "Thailand",
        "Turkey",
        "Vietnam",
    ],
    "emerging markets": [
        "Brazil",
        "Chile",
        "ChinaA",
        "India",
        "Indonesia",
        "Korea",
        "Malaysia",
        "Mexico",
        "Philippines",
        "Poland",
        "Saudi Arabia",
        "South Africa",
        "Taiwan",
        "Thailand",
        "Turkey",
        "Vietnam",
    ],
    "dm": [
        "Australia",
        "Canada",
        "Denmark",
        "France",
        "Germany",
        "Hong Kong",
        "Italy",
        "Japan",
        "Netherlands",
        "Singapore",
        "Spain",
        "Sweden",
        "Switzerland",
        "U.K.",
        "U.S.",
    ],
    "developed markets": [
        "Australia",
        "Canada",
        "Denmark",
        "France",
        "Germany",
        "Hong Kong",
        "Italy",
        "Japan",
        "Netherlands",
        "Singapore",
        "Spain",
        "Sweden",
        "Switzerland",
        "U.K.",
        "U.S.",
    ],
}


class QueryAssistantError(Exception):
    """Raised when planning, validation, or execution fails."""


def _json_ready(value: Any) -> Any:
    if isinstance(value, pd.DataFrame):
        return [_json_ready(row) for row in value.to_dict("records")]
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
    if isinstance(value, dict):
        return {str(k): _json_ready(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_ready(v) for v in value]
    return value


def _extract_json_object(text: str) -> Dict[str, Any]:
    text = text.strip()
    if not text:
        raise QueryAssistantError("LLM returned an empty response.")

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise QueryAssistantError("LLM response did not contain a valid JSON object.")

    return json.loads(text[start:end + 1])


def _extract_openai_output_text(payload: Dict[str, Any]) -> str:
    parts: List[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") in {"output_text", "text"}:
                parts.append(content.get("text", ""))
    return "".join(parts).strip()


def _extract_anthropic_output_text(payload: Dict[str, Any]) -> str:
    parts = [
        block.get("text", "")
        for block in payload.get("content", [])
        if block.get("type") == "text"
    ]
    return "".join(parts).strip()


class ASADOQueryAssistant:
    """Natural-language planner and read-only executor for ASADO."""

    def __init__(
        self,
        provider: str = "auto",
        model: Optional[str] = None,
        auto_refresh_schema: bool = True,
        request_timeout: int = 90,
    ):
        self.provider = self._resolve_provider(provider)
        self.model = model or self._default_model_for_provider(self.provider)
        self.auto_refresh_schema = auto_refresh_schema
        self.request_timeout = request_timeout

    @staticmethod
    def _resolve_provider(provider: str) -> str:
        normalized = (provider or "auto").strip().lower()
        if normalized not in {"auto", "openai", "anthropic"}:
            raise QueryAssistantError(f"Unsupported provider: {provider}")

        if normalized != "auto":
            return normalized

        if os.getenv("OPENAI_API_KEY"):
            return "openai"
        if os.getenv("ANTHROPIC_API_KEY"):
            return "anthropic"

        raise QueryAssistantError(
            "No LLM API key found. Set OPENAI_API_KEY or ANTHROPIC_API_KEY, "
            "or launch Streamlit via `oprun Anthropic,OpenAI -- ...`."
        )

    @staticmethod
    def _default_model_for_provider(provider: str) -> str:
        if provider == "openai":
            return (
                os.getenv("ASADO_QUERY_MODEL")
                or os.getenv("ASADO_QUERY_OPENAI_MODEL")
                or os.getenv("OPENAI_MODEL")
                or "gpt-5"
            )
        return (
            os.getenv("ASADO_QUERY_MODEL")
            or os.getenv("ASADO_QUERY_ANTHROPIC_MODEL")
            or os.getenv("ANTHROPIC_MODEL")
            or "claude-sonnet-4-20250514"
        )

    def _schema_bundle(self) -> Dict[str, Any]:
        if self.auto_refresh_schema:
            return load_schema_cache(auto_build=True)
        return load_schema_cache(auto_build=False)

    @staticmethod
    def _compact_schema_context(schema: Dict[str, Any]) -> str:
        duck = schema["duckdb"]
        neo = schema["neo4j"]
        variable_catalog = schema["variable_catalog"]
        returns_catalog = schema.get("returns_catalog", {}) or {}

        duck_summary = []
        for name, table in duck["tables"].items():
            duck_summary.append(
                {
                    "name": name,
                    "table_type": table.get("table_type"),
                    "description": table.get("description"),
                    "row_count": table.get("row_count"),
                    "columns": [col["column_name"] for col in table.get("columns", [])],
                    "column_value_samples": table.get("column_value_samples", {}),
                    "date_range": table.get("date_range"),
                    "country_count": table.get("country_count"),
                    "variable_count": table.get("variable_count"),
                    "sample_variables": table.get("sample_variables", []),
                }
            )

        neo_summary = {
            "available": neo.get("available", False),
            "labels": {
                label: {
                    "count": info.get("count"),
                    "properties": [row["key"] for row in info.get("properties", [])[:15]],
                    "description": info.get("description"),
                }
                for label, info in neo.get("labels", {}).items()
            },
            "relationships": {
                rel: {
                    "count": info.get("count"),
                    "properties": [row["key"] for row in info.get("properties", [])[:15]],
                    "source_labels": info.get("source_labels", []),
                    "target_labels": info.get("target_labels", []),
                    "description": info.get("description"),
                }
                for rel, info in neo.get("relationships", {}).items()
            },
            "indexes": neo.get("indexes", []),
        }

        primary_view = "feature_panel" if "feature_panel" in duck_summary else "unified_panel"

        context = {
            "duckdb": {
                "tables": duck_summary,
                "countries": duck.get("countries", []),
                "notes": [
                    f"{primary_view} is the primary analytical view.",
                    f"{primary_view} uses tidy rows: date, country, value, variable, source.",
                    "unified_panel is the raw warehouse and excludes ASADO-generated normalized variants.",
                    "country_reference is the canonical ISO3-to-ASADO country mapping table for joins from bilateral tables into factor surfaces.",
                    (
                        f"For latest/current questions, treat CURRENT_DATE as {CURRENT_DATE.isoformat()} "
                        "and constrain to dates on or before that date unless the user explicitly asks "
                        "for forecasts or projections."
                    ),
                    "For latest/current bilateral ownership, trade, or banking questions, prefer the single latest available snapshot date on or before CURRENT_DATE unless the user explicitly asks for history or a multi-period total.",
                    "Prefer observed/non-forecast series over forecast series for current/latest questions.",
                    GDELT_PARTIAL_LABEL_NOTE,
                "Prediction-market tables (if present): predmkt_daily, predmkt_market_meta, predmkt_outcome_meta, predmkt_country_spillover, predmkt_resolutions, predmkt_signals_daily.",
                "Use prediction-market tables for forward-looking probabilities, event odds, off-universe entity spillovers, and market-implied macro expectations.",
                    "World Bank commodity tables: wb_commodity_prices, wb_commodity_indices, wb_commodity_features, and the GLOBAL commodity_panel view (date x series, NOT country-keyed).",
                    "Commodities are GLOBAL series — use commodity_panel (or wb_commodity_features) and join to country_returns/factor_returns ON DATE. They are NOT in feature_panel/unified_panel (the old country-tiled broadcast is deprecated).",
                    "Country graph nodes include both sovereign states and market sleeves; use graph_role to distinguish them.",
                    "For sovereign graph questions, exclude graph_role = 'market_sleeve'.",
                    "ChinaA is the sovereign proxy for China in graph network relationships; ChinaH, NASDAQ, and US SmallCap are market sleeves.",
                    SANCTIONS_WARNING,
                ],
            },
            "neo4j": neo_summary,
            "variables": variable_catalog.get("variable_names", []),
            "return_surfaces": {
                "principle": returns_catalog.get("principle"),
                "country_returns": {
                    "canonical_source_note": returns_catalog.get("country_returns", {}).get(
                        "canonical_source_note"
                    ),
                    "monthly_table": "feature_panel",
                    "monthly_filter": "source = 't2' AND variable IN ('1MRet','3MRet','6MRet','9MRet','12MRet')",
                    "daily_table": "t2_factors_daily",
                    "daily_variables": ["1DRet", "5DRet", "20DRet", "60DRet", "120DRet"],
                },
                "factor_returns": {
                    "monthly_table": "factor_returns",
                    "monthly_sources": ["econ_optimizer", "t2_optimizer", "gdelt_optimizer"],
                    "daily_table": "factor_returns_daily",
                    "daily_sources": ["t2_optimizer_daily", "gdelt_optimizer_daily"],
                },
                "attribution_table": "country_factor_attribution",
                "latest_dates": returns_catalog.get("latest_dates", {}),
                "cycle_guardrail": returns_catalog.get("cycle_guardrail"),
            },
            "planning_rules": [
                "Never invent table, column, label, relationship, or variable names.",
                "DuckDB queries must be SELECT/CTE only.",
                "Neo4j queries must be MATCH/CALL/WITH/RETURN only.",
                "For hybrid plans, use query_mode='hybrid' and hybrid_steps.",
                "If a later hybrid step needs country names from an earlier step, use the literal token {{country_list}}.",
                "The step that produces a reusable country set should alias the relevant column as country.",
                "For sovereign graph/network questions, filter Country nodes to graph_role <> 'market_sleeve'.",
                "For joins between bilateral_portfolio_matrix and feature_panel/unified_panel/normalized_panel, use country_reference rather than inventing CASE mappings.",
                "For current/latest bilateral queries, use MAX(date) on or before CURRENT_DATE instead of summing over a date range unless the user explicitly asks for a period, trend, or cumulative history.",
                "For latest/current GDELT questions, prefer source = 'gdelt' or gdelt_panel so the next-month partial label convention is handled correctly.",
                "For questions about probabilities of future events or policy outcomes, prefer predmkt_signals_daily and predmkt_daily over lagged observed macro tables when prediction-market tables are available.",
                "For off-universe entities (for example Iran/Russia/Israel), use predmkt_country_spillover + predmkt_daily to map into T2 countries when possible.",
                "For commodity questions, use World Bank Pink Sheet variables as explanatory global context only. If the question asks who benefited, who was hurt, or whether a commodity shock mattered, join back to country_returns or factor_returns before making the analytical claim.",
                "When using monthly commodity context in a daily/event workflow, join to the most recent commodity observation on or before the daily/event date.",
                "If a question asks which countries are under sanctions, clarify unless the user explicitly wants OFAC/SDN-linked exposure or association data.",
                "Recognize common region/group terms such as ASEAN, G7, BRICS, LatAm, EMEA, EM, and DM when they appear in the question.",
                # --- Returns-first routing rules (PRD §8.1) ---
                "Returns are the outcome layer. For performance, winner/loser, leader/laggard, "
                "best/worst, worked/did not work, helped/hurt, beneficiary, what happened, "
                "event reaction, crisis impact, analog outcome, payoff, P&L, or attribution "
                "questions, ANCHOR the plan on a return surface unless the user explicitly "
                "asks for non-return data only.",
                "Country performance: use feature_panel (source='t2') with 1MRet/3MRet/6MRet/9MRet/12MRet "
                "for monthly, or t2_factors_daily with 1DRet/5DRet/20DRet/60DRet/120DRet for daily. "
                "There is ONE canonical country return source (T2). GDELT-labeled 1MRet/1DRet rows are "
                "bit-exact aliases — never treat them as a second country return source.",
                "Factor portfolio performance: use factor_returns (monthly) or factor_returns_daily (daily). "
                "These are top-20%-bucket portfolio returns, NOT raw factor levels.",
                "Country-factor contribution: use country_factor_attribution (weight × factor_return). "
                "State explicitly that this is top-20% bucket attribution, not a full portfolio decomposition.",
                "Event-window questions ('what happened around X', 'reaction to Y'): prefer daily return "
                "surfaces (t2_factors_daily 1DRet plus factor_returns_daily) over monthly feature_panel snapshots.",
                "Set the plan field 'return_surface_used' to one of country_returns | factor_returns | "
                "factor_returns_daily | country_factor_attribution | event_window | none, and provide "
                "return_surface_reason. If you set it to 'none' for a performance/event/explanation "
                "question, include a warning explaining why.",
                "Do NOT union factor_returns, factor_returns_daily, factor_top20_membership, or "
                "country_factor_attribution into feature_panel or unified_panel — those views are "
                "explanatory/input surfaces; mixing in optimizer outputs would create a modeling cycle.",
            ],
        }
        return json.dumps(context, indent=2)

    @staticmethod
    def _question_traits(question: str) -> Dict[str, bool]:
        lowered = question.lower()
        current_latest = any(
            phrase in lowered
            for phrase in (
                "latest",
                "current",
                "currently",
                "right now",
                "today",
                "most recent",
                "as of now",
            )
        )
        forecast_intent = any(
            phrase in lowered
            for phrase in (
                "forecast",
                "forecasts",
                "projected",
                "projection",
                "project",
                "expected",
                "expectation",
                "outlook",
                "consensus",
                "estimate",
                "estimated",
                "next year",
            )
        )
        explicit_normalized = any(token in lowered for token in ("_cs", "_ts", "z-score", "z score", "standard deviation"))
        comparative_signal = any(
            phrase in lowered
            for phrase in (
                "cheapest",
                "richest",
                "most expensive",
                "least expensive",
                "highest",
                "lowest",
                "overvalued",
                "undervalued",
                "signal",
            )
        )
        exact_level = any(
            phrase in lowered
            for phrase in (
                "what is",
                "show me",
                "show",
                "level",
                "value",
                "spread",
                "yield",
                "ratio",
            )
        )
        return_intent = any(phrase in lowered for phrase in RETURN_INTENT_PHRASES)
        non_return_only = any(
            phrase in lowered
            for phrase in (
                "no returns",
                "without returns",
                "exclude returns",
                "non-return",
                "ignore performance",
                "no performance",
                "ignore returns",
            )
        )
        event_intent = any(
            phrase in lowered
            for phrase in (
                "what happened",
                "around the",
                "during the",
                "reaction to",
                "after the",
                "before the",
                "event-window",
                "event window",
            )
        )
        return {
            "current_latest": current_latest,
            "forecast_intent": forecast_intent,
            "explicit_normalized": explicit_normalized,
            "comparative_signal": comparative_signal,
            "exact_level": exact_level,
            "return_intent": return_intent and not non_return_only,
            "non_return_only": non_return_only,
            "event_intent": event_intent,
        }

    @staticmethod
    def _recognized_country_groups(question: str) -> Dict[str, List[str]]:
        lowered = question.lower()
        matches: Dict[str, List[str]] = {}
        for label, countries in COUNTRY_GROUPS.items():
            pattern = rf"(?<![a-z]){re.escape(label)}(?![a-z])"
            if re.search(pattern, lowered):
                matches[label.upper() if label.isalpha() and len(label) <= 5 else label.title()] = countries
        return matches

    @staticmethod
    def _candidate_variables(question: str, schema: Dict[str, Any], top_n: int = 12) -> List[Dict[str, Any]]:
        question_text = question.lower()
        question_tokens = {
            token
            for token in re.split(r"[^a-z0-9]+", question_text)
            if token
        }
        traits = ASADOQueryAssistant._question_traits(question)
        alias_map = schema["variable_catalog"].get("variable_aliases", {})
        metadata_map = schema["variable_catalog"].get("variable_metadata", {})
        scored: List[Dict[str, Any]] = []

        for variable, aliases in alias_map.items():
            score = 0.0
            matched_aliases: List[str] = []
            alias_tokens = set()
            metadata = metadata_map.get(variable, {})

            for alias in aliases:
                alias_lower = alias.lower()
                tokens = {token for token in re.split(r"[^a-z0-9]+", alias_lower) if token}
                alias_tokens.update(tokens)
                if alias_lower and alias_lower in question_text:
                    matched_aliases.append(alias)
                    score += 8.0 if len(alias_lower) > 6 else 4.0
                overlap = question_tokens & tokens
                if overlap:
                    score += 1.25 * len(overlap)

            if variable.lower() in question_text:
                score += 10.0

            normalization = metadata.get("normalization")
            if not traits["explicit_normalized"]:
                if normalization == "raw":
                    score += 1.5
                elif normalization in {"cs", "ts"}:
                    score -= 1.0

            if traits["comparative_signal"] and normalization in {"cs", "ts"}:
                score += 1.5

            if traits["exact_level"] and normalization == "raw":
                score += 2.5

            if traits["current_latest"] and not traits["forecast_intent"]:
                if metadata.get("is_forecast"):
                    score -= 8.0
                if metadata.get("is_stale"):
                    score -= 4.0

            if metadata.get("is_sparse"):
                score -= 1.5

            if score > 0:
                scored.append(
                    {
                        "variable": variable,
                        "score": round(score, 2),
                        "matched_aliases": matched_aliases[:6],
                        "shared_tokens": sorted(question_tokens & alias_tokens),
                        "source": metadata.get("source"),
                        "last_date": metadata.get("last_date"),
                        "is_forecast": metadata.get("is_forecast"),
                        "is_stale": metadata.get("is_stale"),
                        "normalization": metadata.get("normalization"),
                    }
                )

        scored.sort(key=lambda row: (-row["score"], row["variable"]))
        return scored[:top_n]

    def _call_openai(self, system_prompt: str, user_prompt: str, expect_json: bool) -> str:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise QueryAssistantError("OPENAI_API_KEY is not set.")

        payload: Dict[str, Any] = {
            "model": self.model,
            "instructions": system_prompt,
            "input": [{"role": "user", "content": user_prompt}],
            "max_output_tokens": 2200,
            "temperature": 0.1,
        }
        if expect_json:
            payload["text"] = {"format": {"type": "json_object"}}

        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=self.request_timeout,
        )
        if not response.ok:
            raise QueryAssistantError(
                f"OpenAI request failed ({response.status_code}): {response.text}"
            )
        return _extract_openai_output_text(response.json())

    def _call_anthropic(self, system_prompt: str, user_prompt: str) -> str:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise QueryAssistantError("ANTHROPIC_API_KEY is not set.")

        payload = {
            "model": self.model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "max_tokens": 2200,
            "temperature": 0.1,
        }
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
            timeout=self.request_timeout,
        )
        if not response.ok:
            raise QueryAssistantError(
                f"Anthropic request failed ({response.status_code}): {response.text}"
            )
        return _extract_anthropic_output_text(response.json())

    def _call_llm(self, system_prompt: str, user_prompt: str, expect_json: bool = False) -> str:
        if self.provider == "openai":
            return self._call_openai(system_prompt, user_prompt, expect_json=expect_json)
        return self._call_anthropic(system_prompt, user_prompt)

    def plan(self, question: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        schema_bundle = schema or self._schema_bundle()
        candidate_variables = self._candidate_variables(question, schema_bundle)
        recognized_groups = self._recognized_country_groups(question)
        system_prompt = (
            "You are the ASADO query planner. "
            "Return JSON only. "
            "Your job is to translate a natural-language question into a safe, "
            "read-only query plan against the ASADO DuckDB + Neo4j schema. "
            "Do not invent identifiers. "
            "If the question is ambiguous, set query_mode to 'clarify' and provide "
            "a short clarification_question instead of guessing. "
            "The output JSON must match this shape exactly:\n"
            f"{json.dumps(PLAN_FORMAT, indent=2)}"
        )

        user_prompt = (
            f"ASADO schema context:\n{self._compact_schema_context(schema_bundle)}\n\n"
            f"CURRENT_DATE: {CURRENT_DATE.isoformat()}\n\n"
            f"Recognized country groups in this question:\n{json.dumps(recognized_groups, indent=2)}\n\n"
            f"Top variable candidates for this question:\n{json.dumps(candidate_variables, indent=2)}\n\n"
            f"User question:\n{question}\n\n"
            "For latest/current questions, avoid future-dated rows and prefer observed/non-forecast series unless the user explicitly asks for forecasts. "
            "For latest/current bilateral ownership, trade, or banking questions, use the latest available snapshot date on or before CURRENT_DATE rather than aggregating across a date range unless the user explicitly asks for history. "
            f"{GDELT_PARTIAL_LABEL_NOTE} "
            "Prefer matching against the candidate variables when they fit the question. "
            "Return JSON only."
        )

        raw = self._call_llm(system_prompt, user_prompt, expect_json=True)
        plan = _extract_json_object(raw)
        plan.setdefault("warnings", [])
        plan.setdefault("hybrid_steps", [])
        plan.setdefault("tables_or_labels", [])
        plan = self._apply_domain_guardrails(question, plan)
        return self._apply_returns_first_guardrail(question, plan)

    @staticmethod
    def _apply_returns_first_guardrail(question: str, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Set return_surface_used / return_surface_reason and warn on return-intent mismatch."""
        traits = ASADOQueryAssistant._question_traits(question)
        tables = [str(t) for t in (plan.get("tables_or_labels") or [])]
        all_text = " ".join(tables).lower() + " " + (
            (plan.get("duckdb_sql") or "") + " " + (plan.get("neo4j_cypher") or "")
        ).lower()
        for step in plan.get("hybrid_steps", []) or []:
            all_text += " " + str(step.get("query") or "").lower()

        def _has(token: str) -> bool:
            return token in all_text

        surface = "none"
        if _has("country_factor_attribution"):
            surface = "country_factor_attribution"
        elif _has("factor_returns_daily"):
            surface = "factor_returns_daily"
        elif _has("factor_returns"):
            surface = "factor_returns"
        elif _has("1dret") or _has("5dret") or _has("20dret") or _has("60dret") or _has("120dret"):
            surface = "country_returns"
        elif (_has("1mret") or _has("3mret") or _has("6mret") or _has("9mret") or _has("12mret")):
            surface = "country_returns"
        elif _has("event_window") or _has("events_in_window"):
            surface = "event_window"

        plan["return_surface_used"] = plan.get("return_surface_used") or surface
        if not plan.get("return_surface_reason"):
            plan["return_surface_reason"] = (
                f"Inferred from plan tables/SQL: {plan['return_surface_used']}"
                if plan["return_surface_used"] != "none"
                else "No return surface referenced in tables_or_labels or query text."
            )

        if traits.get("return_intent") and plan["return_surface_used"] == "none":
            warn = (
                "Question expresses a returns/performance/event intent but no return surface "
                "was selected. Prefer feature_panel 1MRet/source='t2' (or t2_factors_daily) for "
                "country performance, factor_returns / factor_returns_daily for factor performance, "
                "and country_factor_attribution for country-level contribution. GDELT 1MRet/1DRet "
                "are bit-exact aliases of T2 — do not treat them as a second source."
            )
            warnings = list(dict.fromkeys((plan.get("warnings") or []) + [warn]))
            plan["warnings"] = warnings

        return plan

    @staticmethod
    def _apply_domain_guardrails(question: str, plan: Dict[str, Any]) -> Dict[str, Any]:
        question_lower = question.lower()
        plan["warnings"] = list(dict.fromkeys(plan.get("warnings") or []))

        uses_sanctions = any(
            token in (plan.get("tables_or_labels") or [])
            for token in ("SUBJECT_TO", "SanctionsProgram", "OFAC_Sanctioned")
        )
        if not uses_sanctions and "sanction" not in question_lower:
            return plan

        if SANCTIONS_WARNING not in plan["warnings"]:
            plan["warnings"].append(SANCTIONS_WARNING)

        explicit_ofac_request = any(
            token in question_lower
            for token in ("ofac", "sdn", "association", "associated", "exposure")
        )
        asks_for_target_country_claim = any(
            phrase in question_lower
            for phrase in (
                "subject to active sanctions programs",
                "subject to sanctions",
                "countries under sanctions",
                "countries are under sanctions",
                "sanctioned countries",
                "active sanctions programs",
            )
        )

        if explicit_ofac_request or not asks_for_target_country_claim:
            return plan

        return {
            "understanding": (
                "Question asks for sovereign sanctions-target countries, but ASADO only "
                "tracks OFAC/SDN-linked country associations."
            ),
            "query_mode": "clarify",
            "confidence": 0.35,
            "clarification_question": (
                "ASADO's current sanctions layer reflects OFAC/SDN-linked country "
                "associations, not a clean sovereign target-country registry. Do you "
                "want OFAC-linked country exposure/association instead?"
            ),
            "tables_or_labels": ["Country", "SanctionsProgram", "SUBJECT_TO"],
            "reasoning_summary": (
                "Returning a direct answer here would overstate what the sanctions data "
                "actually means."
            ),
            "expected_output": (
                "Clarification about whether to use OFAC-linked exposure/association data."
            ),
            "warnings": plan["warnings"],
            "duckdb_sql": None,
            "neo4j_cypher": None,
            "hybrid_steps": [],
        }

    @staticmethod
    def _clean_query(query: str) -> str:
        cleaned = query.strip()
        while cleaned.startswith("--") or cleaned.startswith("/*"):
            if cleaned.startswith("--"):
                newline = cleaned.find("\n")
                cleaned = "" if newline == -1 else cleaned[newline + 1 :].lstrip()
                continue
            if cleaned.startswith("/*"):
                end = cleaned.find("*/")
                cleaned = "" if end == -1 else cleaned[end + 2 :].lstrip()
        return cleaned.rstrip(";").strip()

    @staticmethod
    def _apply_current_date_cutoff(sql: str) -> str:
        date_literal = CURRENT_DATE.isoformat()
        if date_literal in sql or "CURRENT_DATE" in sql.upper():
            return sql
        gdelt_literal = GDELT_PARTIAL_LABEL_DATE.isoformat()
        gdelt_specific_query = bool(
            re.search(r"\bgdelt_panel\b", sql, re.IGNORECASE)
            or re.search(r"\bsource\s*=\s*'gdelt'\b", sql, re.IGNORECASE)
            or re.search(r'\bsource\s*=\s*"gdelt"\b', sql, re.IGNORECASE)
        )
        if gdelt_specific_query:
            replacement = (
                rf"MAX(CASE WHEN \1date <= DATE '{date_literal}' "
                rf"OR \1date = DATE '{gdelt_literal}' THEN \1date END)"
            )
        else:
            replacement = rf"MAX(CASE WHEN \1date <= DATE '{date_literal}' THEN \1date END)"
        return re.sub(
            r"MAX\s*\(\s*((?:[A-Za-z_][\w]*\.)?)date\s*\)",
            replacement,
            sql,
            flags=re.IGNORECASE,
        )

    @staticmethod
    def _validate_sql(sql: str, allowed_tables: set[str]) -> str:
        cleaned = ASADOQueryAssistant._clean_query(sql)
        lowered = cleaned.lower()
        if not lowered.startswith(("select", "with")):
            raise QueryAssistantError("DuckDB query must start with SELECT or WITH.")
        for keyword in SQL_BLOCKLIST:
            if re.search(rf"\b{re.escape(keyword)}\b", lowered):
                raise QueryAssistantError(f"Blocked SQL keyword detected: {keyword}")
        cte_names = set(
            match.group(1).strip('"')
            for match in re.finditer(
                r'(?:\bwith\b|,)\s*"?(?:RECURSIVE\s+)?([A-Za-z_][\w]*)"?\s+as\s*\(',
                cleaned,
                re.IGNORECASE,
            )
        )
        referenced_tables = set(
            match.group(1).strip('"')
            for match in re.finditer(r'\b(?:from|join)\s+"?([A-Za-z_][\w]*)"?', cleaned, re.IGNORECASE)
        )
        unknown_tables = sorted(
            t for t in referenced_tables
            if t not in allowed_tables and t not in cte_names
        )
        if unknown_tables:
            raise QueryAssistantError(f"Unknown DuckDB table/view referenced: {', '.join(unknown_tables)}")
        return cleaned

    @staticmethod
    def _validate_cypher(cypher: str, allowed_labels: set[str], allowed_rels: set[str]) -> str:
        cleaned = ASADOQueryAssistant._clean_query(cypher)
        lowered = cleaned.lower()
        if not lowered.startswith(("match", "with", "call", "unwind")):
            raise QueryAssistantError("Neo4j query must start with MATCH, WITH, CALL, or UNWIND.")
        for keyword in CYPHER_BLOCKLIST:
            if keyword in lowered:
                raise QueryAssistantError(f"Blocked Cypher keyword detected: {keyword}")

        label_refs = set()
        for match in re.finditer(
            r"\(\s*(?:[A-Za-z_][\w]*\s*)?(?::\s*`?[A-Za-z_][\w]*`?\s*)+",
            cleaned,
        ):
            label_refs.update(
                token.replace("`", "")
                for token in re.findall(r":\s*(`?[A-Za-z_][\w]*`?)", match.group(0))
            )

        rel_refs = set()
        for match in re.finditer(
            r"\[\s*(?:[A-Za-z_][\w]*\s*)?(?::\s*`?[A-Za-z_][\w]*`?\s*)+",
            cleaned,
        ):
            rel_refs.update(
                token.replace("`", "")
                for token in re.findall(r":\s*(`?[A-Za-z_][\w]*`?)", match.group(0))
            )

        unknown_labels = sorted(label for label in label_refs if label not in allowed_labels)
        unknown_rels = sorted(rel for rel in rel_refs if rel not in allowed_rels)

        if unknown_labels:
            raise QueryAssistantError(f"Unknown Neo4j labels referenced: {', '.join(unknown_labels)}")
        if unknown_rels:
            raise QueryAssistantError(f"Unknown Neo4j relationships referenced: {', '.join(unknown_rels)}")
        return cleaned

    @staticmethod
    def _ensure_sql_limit(sql: str, limit: int) -> str:
        if re.search(r"\blimit\b", sql, re.IGNORECASE):
            return sql
        return f"SELECT * FROM ({sql}) AS asado_query_preview LIMIT {int(limit)}"

    @staticmethod
    def _ensure_cypher_limit(cypher: str, limit: int) -> str:
        if re.search(r"\blimit\b", cypher, re.IGNORECASE):
            return cypher
        return f"{cypher}\nLIMIT {int(limit)}"

    @staticmethod
    def _country_list_sql(countries: List[str]) -> str:
        if not countries:
            raise QueryAssistantError("Hybrid step expected countries but none were returned.")
        escaped = [country.replace("'", "''") for country in countries]
        return "(" + ", ".join(f"'{country}'" for country in escaped) + ")"

    @staticmethod
    def _country_list_cypher(countries: List[str]) -> str:
        if not countries:
            raise QueryAssistantError("Hybrid step expected countries but none were returned.")
        escaped = [country.replace("'", "\\'") for country in countries]
        return "[" + ", ".join(f"'{country}'" for country in escaped) + "]"

    @staticmethod
    def _substitute_country_placeholder(query: str, replacement: str, engine: str) -> str:
        if "{{country_list}}" not in query:
            return query
        wrapped_pattern = r"\(\s*\{\{country_list\}\}\s*\)" if engine == "duckdb" else r"\[\s*\{\{country_list\}\}\s*\]"
        query = re.sub(wrapped_pattern, replacement, query)
        return query.replace("{{country_list}}", replacement)

    @staticmethod
    def _should_apply_current_date_guardrail(question: str) -> bool:
        traits = ASADOQueryAssistant._question_traits(question)
        return traits["current_latest"] and not traits["forecast_intent"]

    @staticmethod
    def _maybe_retry_latest_per_country(
        db: AsadoDB,
        run_query: str,
        countries: List[str],
        result: pd.DataFrame,
        max_rows: int,
    ) -> pd.DataFrame:
        lowered = run_query.lower()
        if len(countries) <= 1 or "max(date)" not in lowered or "country in" not in lowered:
            return result
        if len(result) > 1:
            return result

        variable_match = re.search(r"variable\s*=\s*'([^']+)'", run_query, re.IGNORECASE)
        if not variable_match:
            return result
        variable = variable_match.group(1)

        value_alias_match = re.search(r"value\s+as\s+([A-Za-z_][\w]*)", run_query, re.IGNORECASE)
        date_alias_match = re.search(r"date\s+as\s+([A-Za-z_][\w]*)", run_query, re.IGNORECASE)
        value_alias = value_alias_match.group(1) if value_alias_match else "value"
        date_alias = date_alias_match.group(1) if date_alias_match else "date"

        surface = "feature_panel" if "feature_panel" in set(db.tables()) else "unified_panel"
        retry_sql = f"""
        WITH ranked AS (
            SELECT
                country,
                value,
                date,
                ROW_NUMBER() OVER (PARTITION BY country ORDER BY date DESC) AS rn
            FROM {surface}
            WHERE variable = '{variable.replace("'", "''")}'
              AND country IN {ASADOQueryAssistant._country_list_sql(countries)}
              AND value IS NOT NULL
        )
        SELECT
            country,
            value AS {value_alias},
            date AS {date_alias}
        FROM ranked
        WHERE rn = 1
        ORDER BY country
        LIMIT {int(max_rows)}
        """
        return db.query_panel(retry_sql)

    @staticmethod
    def _extract_country_list(payload: Any) -> List[str]:
        if isinstance(payload, pd.DataFrame):
            for column in ("country", "t2_name", "name"):
                if column in payload.columns:
                    return [str(v) for v in payload[column].dropna().unique().tolist()]
            return []

        if isinstance(payload, list):
            values = []
            for row in payload:
                if not isinstance(row, dict):
                    continue
                for key in ("country", "t2_name", "name"):
                    if key in row and row[key] is not None:
                        values.append(str(row[key]))
                        break
            return list(dict.fromkeys(values))

        return []

    @staticmethod
    def _tabular_preview(payload: Any, max_rows: int) -> str:
        if isinstance(payload, pd.DataFrame):
            if payload.empty:
                return "(no rows)"
            return payload.head(max_rows).to_string(index=False)
        if isinstance(payload, list):
            if not payload:
                return "(no rows)"
            return json.dumps(payload[:max_rows], indent=2)
        return str(payload)

    def execute(self, question: str, plan: Dict[str, Any], max_rows: int = 100) -> Dict[str, Any]:
        schema = self._schema_bundle()
        duck_tables = set(schema["duckdb"]["tables"].keys())
        allowed_labels = set(schema["neo4j"].get("labels", {}).keys())
        allowed_rels = set(schema["neo4j"].get("relationships", {}).keys())
        apply_current_date_guardrail = self._should_apply_current_date_guardrail(question)

        mode = plan.get("query_mode", "").strip().lower()
        if mode == "clarify":
            return {
                "mode": mode,
                "result_df": pd.DataFrame(),
                "row_count": 0,
                "executed_queries": [],
            }

        executed_queries: List[Dict[str, Any]] = []

        with AsadoDB() as db:
            if mode == "duckdb":
                sql = self._validate_sql(plan.get("duckdb_sql") or "", duck_tables)
                if apply_current_date_guardrail:
                    sql = self._apply_current_date_cutoff(sql)
                run_sql = self._ensure_sql_limit(sql, max_rows)
                df = db.query_panel(run_sql)
                executed_queries.append({"engine": "duckdb", "query": run_sql})
                return {
                    "mode": mode,
                    "result_df": df,
                    "row_count": len(df),
                    "executed_queries": executed_queries,
                }

            if mode == "neo4j":
                cypher = self._validate_cypher(plan.get("neo4j_cypher") or "", allowed_labels, allowed_rels)
                run_cypher = self._ensure_cypher_limit(cypher, max_rows)
                records = db.query_graph(run_cypher)
                executed_queries.append({"engine": "neo4j", "query": run_cypher})
                return {
                    "mode": mode,
                    "result_df": pd.DataFrame(records),
                    "row_count": len(records),
                    "executed_queries": executed_queries,
                }

            if mode == "hybrid":
                context: Dict[str, Any] = {}
                final_df = pd.DataFrame()
                steps = plan.get("hybrid_steps") or []
                if not steps:
                    raise QueryAssistantError("Hybrid mode requires non-empty hybrid_steps.")

                for index, step in enumerate(steps, start=1):
                    engine = (step.get("engine") or "").strip().lower()
                    query = step.get("query") or ""
                    if engine not in {"duckdb", "neo4j"}:
                        raise QueryAssistantError(f"Invalid hybrid step engine: {engine}")

                    if "{{country_list}}" in query:
                        countries = context.get("country_list", [])
                        replacement = (
                            self._country_list_sql(countries)
                            if engine == "duckdb"
                            else self._country_list_cypher(countries)
                        )
                        query = self._substitute_country_placeholder(query, replacement, engine)

                    step_limit = max_rows if index == len(steps) else min(max_rows, 50)
                    if engine == "duckdb":
                        validated = self._validate_sql(query, duck_tables)
                        if apply_current_date_guardrail:
                            validated = self._apply_current_date_cutoff(validated)
                        run_query = self._ensure_sql_limit(validated, step_limit)
                        result = db.query_panel(run_query)
                        result = self._maybe_retry_latest_per_country(
                            db,
                            run_query,
                            context.get("country_list", []),
                            result,
                            step_limit,
                        )
                    else:
                        validated = self._validate_cypher(query, allowed_labels, allowed_rels)
                        run_query = self._ensure_cypher_limit(validated, step_limit)
                        result = pd.DataFrame(db.query_graph(run_query))

                    executed_queries.append({"engine": engine, "query": run_query})
                    result_key = step.get("result_key")
                    if result_key == "country_list" or ("country" in getattr(result, "columns", [])):
                        context["country_list"] = self._extract_country_list(result)
                    final_df = result

                return {
                    "mode": mode,
                    "result_df": final_df,
                    "row_count": len(final_df),
                    "executed_queries": executed_queries,
                }

        raise QueryAssistantError(f"Unsupported query mode: {mode}")

    def interpret(
        self,
        question: str,
        plan: Dict[str, Any],
        execution: Dict[str, Any],
        max_rows: int = 50,
    ) -> str:
        mode = execution.get("mode")
        if mode == "clarify":
            return plan.get("clarification_question") or "The request needs clarification before execution."

        system_prompt = (
            "You are an ASADO research analyst. "
            "Summarize what the executed query actually shows, not what you wish it showed. "
            "Stay grounded in the returned rows. "
            "If results are empty, say so plainly. "
            "Mention important caveats or missing coverage. "
            f"Treat CURRENT_DATE={CURRENT_DATE.isoformat()} as authoritative. "
            f"{GDELT_PARTIAL_LABEL_NOTE} "
            "Do not call data projected or future-dated just because it is later than your training cutoff. "
            "Only mention forecasts/projections when the variable family, source, or returned dates actually indicate that."
        )
        user_prompt = (
            f"Original question:\n{question}\n\n"
            f"Plan JSON:\n{json.dumps(_json_ready(plan), indent=2)}\n\n"
            f"Executed queries:\n{json.dumps(execution.get('executed_queries', []), indent=2)}\n\n"
            f"Row count: {execution.get('row_count', 0)}\n\n"
            f"Result preview:\n{self._tabular_preview(execution.get('result_df'), max_rows)}"
        )
        return self._call_llm(system_prompt, user_prompt, expect_json=False)

    def _write_log(self, payload: Dict[str, Any]) -> None:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = LOG_DIR / f"{stamp}_query.json"
        path.write_text(json.dumps(_json_ready(payload), indent=2), encoding="utf-8")

    def ask(self, question: str, preview_only: bool = False, max_rows: int = 100) -> Dict[str, Any]:
        question = (question or "").strip()
        if not question:
            raise QueryAssistantError("Question cannot be empty.")

        schema = self._schema_bundle()
        plan = self.plan(question, schema=schema)

        response: Dict[str, Any] = {
            "question": question,
            "provider": self.provider,
            "model": self.model,
            "plan": plan,
            "preview_only": preview_only,
            "schema_generated_at": schema["manifest"].get("generated_at"),
        }

        if preview_only or plan.get("query_mode") == "clarify":
            response["interpretation"] = (
                plan.get("clarification_question")
                if plan.get("query_mode") == "clarify"
                else "Preview only - no query executed."
            )
            response["result_df"] = pd.DataFrame()
            response["row_count"] = 0
            response["executed_queries"] = []
            self._write_log(response)
            return response

        execution = self.execute(question, plan, max_rows=max_rows)
        interpretation = self.interpret(question, plan, execution)
        response.update(execution)
        response["interpretation"] = interpretation
        self._write_log(
            {
                **response,
                "result_preview": _json_ready(response["result_df"].head(min(max_rows, 25))),
            }
        )
        return response


def _cli_payload(response: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(response)
    if isinstance(payload.get("result_df"), pd.DataFrame):
        payload["result_rows"] = _json_ready(payload["result_df"].head(50))
        del payload["result_df"]
    return _json_ready(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="ASADO natural-language query assistant")
    parser.add_argument("question", help="Natural-language question to ask ASADO")
    parser.add_argument("--provider", default="auto", choices=["auto", "openai", "anthropic"])
    parser.add_argument("--model", default=None, help="Optional model override")
    parser.add_argument("--preview-only", action="store_true", help="Plan the query but do not execute it")
    parser.add_argument("--max-rows", type=int, default=100, help="Maximum rows to return")
    parser.add_argument(
        "--refresh-schema",
        action="store_true",
        help="Rebuild schema cache before planning the query",
    )
    args = parser.parse_args()

    if args.refresh_schema:
        build_and_write_schema_cache()

    assistant = ASADOQueryAssistant(provider=args.provider, model=args.model)
    response = assistant.ask(args.question, preview_only=args.preview_only, max_rows=args.max_rows)
    print(json.dumps(_cli_payload(response), indent=2))


if __name__ == "__main__":
    main()
