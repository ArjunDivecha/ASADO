#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/build_predmkt_panel.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/predmkt_curated.yaml
    Hand-curated prediction-market registry. One record per market with:
    platform, market_id, category tags, optional outcome metadata,
    optional resolution source text, and spillover-country mappings.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/country_mapping.json
    Canonical T2 country names used to validate spillover mappings.
- Public API endpoints (read-only):
    - Kalshi: https://api.elections.kalshi.com/trade-api/v2
    - Polymarket Gamma: https://gamma-api.polymarket.com
    - Polymarket CLOB: https://clob.polymarket.com
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
    Existing ASADO DuckDB warehouse file.

OUTPUT TABLES (added/updated in Data/asado.duckdb):
- predmkt_daily
- predmkt_market_meta
- predmkt_outcome_meta
- predmkt_country_spillover
- predmkt_resolutions
- predmkt_signals_daily
- variable_meta (upsert-only for predmkt signal rows when table exists)

VERSION: 1.0
LAST UPDATED: 2026-05-08
AUTHOR: Arjun Divecha (with Codex)

DESCRIPTION:
Builds ASADO Stage 2 prediction-market surfaces from curated Kalshi and
Polymarket markets. The script captures a daily snapshot, writes normalized
fact/dimension tables, tracks resolved-market calibration records, and
materializes derived daily signals for macro, geopolitics, and spillover risk.

The script is additive and idempotent by snapshot date:
- It deletes and rewrites the current snapshot date for predmkt_daily/signals.
- It upserts metadata tables by platform+market keys.
- It preserves history for prior snapshot dates.

DEPENDENCIES:
- duckdb
- pandas
- pyyaml
- requests
- urllib3
- cryptography (optional; required only when Kalshi authenticated mode is used)

USAGE:
  python scripts/build_predmkt_panel.py
  python scripts/build_predmkt_panel.py --check
  python scripts/build_predmkt_panel.py --validate-only
  python scripts/build_predmkt_panel.py --stats
  python scripts/build_predmkt_panel.py --rebuild
  python scripts/build_predmkt_panel.py --dry-run
  python scripts/build_predmkt_panel.py --no-backup

NOTES:
- This is a read-only market-data ingestor. It never trades.
- The registry is mandatory. Missing or invalid registry is a hard failure.
- Per-market API failures are logged and skipped so one bad market does not
  block the full daily snapshot.
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import re
import shutil
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import duckdb
import pandas as pd
import requests
import yaml
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "Data"
DB_PATH = DATA_DIR / "asado.duckdb"
BACKUP_PATH = DATA_DIR / "asado.duckdb.predmkt.backup"
REGISTRY_PATH = CONFIG_DIR / "predmkt_curated.yaml"
COUNTRY_MAP_PATH = CONFIG_DIR / "country_mapping.json"

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"
POLY_GAMMA_BASE = "https://gamma-api.polymarket.com"
POLY_CLOB_BASE = "https://clob.polymarket.com"

VALID_PLATFORMS = {"kalshi", "polymarket"}
VALID_CONFIDENCE = {"high", "medium", "low"}
VALID_RESOLUTION_CLARITY = {"high", "medium", "low"}
VALID_CHANNELS = {
    "oil_export",
    "oil_import_dependency",
    "regional_proximity",
    "trade_partner",
    "usd_beta",
    "em_beta",
    "tech_supply_chain",
    "commodity_export",
    "safe_haven",
    "regional_proxy",
}

SIGNAL_CONFIDENCE_WEIGHT = {"low": 0.5, "medium": 0.75, "high": 1.0}
LIQUIDITY_THRESHOLD = {"kalshi": 500.0, "polymarket": 1000.0}

SIGNAL_SPECS = [
    "fed_cut_count_expectation",
    "fed_decision_distribution_next",
    "cpi_nowcast_yoy_next",
    "cpi_nowcast_core_next",
    "unemployment_nowcast_next",
    "recession_prob_12m",
    "oil_shock_prob_30d",
    "hormuz_disruption_prob_90d",
    "regional_conflict_premium_middle_east",
    "regional_conflict_premium_pacific",
    "regional_conflict_premium_eastern_europe",
    "tariff_intensity_by_country",
    "predmkt_country_risk_composite",
    "predmkt_country_opportunity_composite",
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)


@dataclass
class PullResult:
    daily_rows: List[Dict[str, Any]]
    market_meta_rows: List[Dict[str, Any]]
    outcome_meta_rows: List[Dict[str, Any]]
    errors: List[str]


def _build_session() -> requests.Session:
    retry = Retry(
        total=3,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": "ASADO-PredMkt-Collector/1.0"})

    # Optional Kalshi auth signing (additive).
    # If credentials are missing, requests continue unauthenticated.
    try:
        try:
            from scripts._kalshi_auth import maybe_create_kalshi_auth
        except ModuleNotFoundError:
            from _kalshi_auth import maybe_create_kalshi_auth

        kalshi_auth = maybe_create_kalshi_auth()
        if kalshi_auth is not None:
            session.auth = kalshi_auth
            log.info("Kalshi auth: signed requests enabled (key_id=%s...)", kalshi_auth.key_id[:8])
        else:
            log.info("Kalshi auth: no credentials configured; using public endpoints")
    except Exception as exc:
        log.warning("Kalshi auth setup failed: %s; using public endpoints", exc)

    return session


def _parse_datetime(value: Any) -> Optional[datetime]:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        try:
            if float(value) > 10_000_000_000:
                return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except Exception:
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        text = text.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(text)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            pass
    return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        if isinstance(value, str):
            value = value.replace(",", "").strip()
        parsed = float(value)
        if math.isnan(parsed) or math.isinf(parsed):
            return None
        return parsed
    except Exception:
        return None


def _probability(value: Any) -> Optional[float]:
    parsed = _safe_float(value)
    if parsed is None:
        return None
    if parsed > 1.0:
        parsed = parsed / 100.0
    if parsed < 0.0:
        return 0.0
    if parsed > 1.0:
        return 1.0
    return parsed


def _first_non_null(mapping: Dict[str, Any], keys: Iterable[str]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return None


def _parse_jsonish(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return json.loads(text)
        except Exception:
            return value
    return value


def _fetch_json(session: requests.Session, url: str, params: Optional[dict] = None) -> Any:
    resp = session.get(url, params=params, timeout=20)
    resp.raise_for_status()
    return resp.json()


def _load_t2_countries() -> set[str]:
    if not COUNTRY_MAP_PATH.exists():
        raise FileNotFoundError(f"Country mapping not found: {COUNTRY_MAP_PATH}")
    payload = json.loads(COUNTRY_MAP_PATH.read_text(encoding="utf-8"))
    if isinstance(payload.get("countries"), dict):
        return set(payload["countries"].keys())
    countries = payload.get("t2_countries", [])
    return {row["t2_name"] for row in countries if isinstance(row, dict) and row.get("t2_name")}


def _load_registry() -> list[dict[str, Any]]:
    if not REGISTRY_PATH.exists():
        raise FileNotFoundError(f"Missing curation registry: {REGISTRY_PATH}")
    raw = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        markets = raw.get("markets")
    else:
        markets = raw
    if not isinstance(markets, list):
        raise ValueError("predmkt_curated.yaml must be a YAML list or {markets: [...]} payload.")
    return markets


def _validate_registry(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    valid_countries = _load_t2_countries()
    seen = set()
    normalized: list[dict[str, Any]] = []

    for idx, market in enumerate(markets):
        if not isinstance(market, dict):
            raise ValueError(f"Registry entry #{idx + 1} is not a mapping.")

        platform = str(market.get("platform", "")).lower().strip()
        market_id = str(market.get("market_id", "")).strip()
        category = str(market.get("asado_category", "")).strip()
        subcategory = str(market.get("asado_subcategory", "")).strip()
        resolution_clarity = str(market.get("resolution_clarity", "medium")).lower().strip()
        raw_is_active = market.get("is_active", True)
        if isinstance(raw_is_active, str):
            is_active = raw_is_active.strip().lower() in {"1", "true", "yes", "y"}
        else:
            is_active = bool(raw_is_active)

        if platform not in VALID_PLATFORMS:
            raise ValueError(f"{market_id or idx}: unsupported platform '{platform}'.")
        if not market_id:
            raise ValueError(f"Registry entry #{idx + 1} missing market_id.")
        if not category:
            raise ValueError(f"{platform}:{market_id} missing asado_category.")
        if resolution_clarity not in VALID_RESOLUTION_CLARITY:
            raise ValueError(
                f"{platform}:{market_id} invalid resolution_clarity '{resolution_clarity}'."
            )
        key = (platform, market_id)
        if key in seen:
            raise ValueError(f"Duplicate registry market key: {platform}:{market_id}")
        seen.add(key)

        spillovers = market.get("spillover_countries", []) or []
        if not isinstance(spillovers, list):
            raise ValueError(f"{platform}:{market_id} spillover_countries must be a list.")
        for spill in spillovers:
            if not isinstance(spill, dict):
                raise ValueError(f"{platform}:{market_id} has non-mapping spillover row.")
            country = str(spill.get("country", "")).strip()
            channel = str(spill.get("channel", "")).strip()
            confidence = str(spill.get("confidence", "medium")).lower().strip()
            if country not in valid_countries:
                raise ValueError(
                    f"{platform}:{market_id} spillover country '{country}' is not a valid T2 name."
                )
            if channel not in VALID_CHANNELS:
                raise ValueError(
                    f"{platform}:{market_id} spillover channel '{channel}' is outside taxonomy."
                )
            if confidence not in VALID_CONFIDENCE:
                raise ValueError(
                    f"{platform}:{market_id} spillover confidence '{confidence}' invalid."
                )

        outcomes = market.get("outcomes", []) or []
        if outcomes and not isinstance(outcomes, list):
            raise ValueError(f"{platform}:{market_id} outcomes must be a list when provided.")

        normalized.append(
            {
                **market,
                "platform": platform,
                "market_id": market_id,
                "asado_category": category,
                "asado_subcategory": subcategory,
                "resolution_clarity": resolution_clarity,
                "is_active": is_active,
                "spillover_countries": spillovers,
            }
        )

    return normalized


def _as_spillover_rows(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for market in markets:
        platform = market["platform"]
        market_id = market["market_id"]
        for spill in market.get("spillover_countries", []) or []:
            rows.append(
                {
                    "platform": platform,
                    "market_id": market_id,
                    "country": spill["country"],
                    "elasticity": _safe_float(spill.get("elasticity")) or 0.0,
                    "channel": spill.get("channel"),
                    "confidence": str(spill.get("confidence", "medium")).lower(),
                    "notes": spill.get("notes"),
                }
            )
    return rows


def _infer_stale(
    platform: str,
    probability: Optional[float],
    last_traded_price: Optional[float],
    last_traded_ts: Optional[datetime],
    volume_24h: Optional[float],
) -> bool:
    threshold = LIQUIDITY_THRESHOLD.get(platform, 500.0)
    no_flow = (volume_24h or 0.0) < threshold
    old_trade = True
    if last_traded_ts:
        old_trade = (datetime.now(timezone.utc) - last_traded_ts) > timedelta(hours=24)
    large_gap = False
    if probability is not None and last_traded_price is not None:
        large_gap = abs(last_traded_price - probability) > 0.05
    return bool(no_flow or old_trade or large_gap)


def _kalshi_market_payload(session: requests.Session, ticker: str) -> dict[str, Any]:
    try:
        data = _fetch_json(session, f"{KALSHI_BASE}/markets/{ticker}")
        if isinstance(data, dict):
            return data.get("market", data)
    except Exception:
        pass

    data = _fetch_json(session, f"{KALSHI_BASE}/markets", params={"tickers": ticker, "limit": 1})
    if isinstance(data, dict) and isinstance(data.get("markets"), list) and data["markets"]:
        return data["markets"][0]
    raise ValueError(f"Kalshi market not found: {ticker}")


def _kalshi_orderbook_payload(session: requests.Session, ticker: str) -> dict[str, Any]:
    """
    Return a normalized orderbook with explicit yes_bid / yes_ask /
    no_bid / no_ask keys, plus order-book depth, regardless of which
    nested format Kalshi returns.

    Kalshi returns:
      {"orderbook_fp": {"yes_dollars": [[price, qty], ...],
                        "no_dollars":  [[price, qty], ...]}}
    where prices are probabilities in [0, 1]. The best YES bid is the
    highest price in yes_dollars; the best YES ask is implied as
    1 - (highest no_dollars price).
    """
    try:
        data = _fetch_json(session, f"{KALSHI_BASE}/markets/{ticker}/orderbook")
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}

    book = data.get("orderbook_fp") or data.get("orderbook") or data
    if not isinstance(book, dict):
        return {}

    def _best_price(side: list, take_max: bool) -> Optional[float]:
        if not isinstance(side, list) or not side:
            return None
        prices = []
        for entry in side:
            if isinstance(entry, (list, tuple)) and len(entry) >= 1:
                p = _safe_float(entry[0])
                if p is not None:
                    prices.append(p)
        if not prices:
            return None
        return max(prices) if take_max else min(prices)

    def _depth_qty(side: list) -> float:
        if not isinstance(side, list):
            return 0.0
        total = 0.0
        for entry in side:
            if isinstance(entry, (list, tuple)) and len(entry) >= 2:
                q = _safe_float(entry[1])
                if q is not None:
                    total += q
        return total

    yes_side = book.get("yes_dollars") or book.get("yes") or []
    no_side = book.get("no_dollars") or book.get("no") or []

    best_yes_bid = _best_price(yes_side, take_max=True)
    best_no_bid = _best_price(no_side, take_max=True)
    yes_ask_implied = (1.0 - best_no_bid) if best_no_bid is not None else None
    no_ask_implied = (1.0 - best_yes_bid) if best_yes_bid is not None else None

    depth_yes = _depth_qty(yes_side)
    depth_no = _depth_qty(no_side)

    return {
        "yes_bid": best_yes_bid,
        "yes_ask": yes_ask_implied,
        "no_bid": best_no_bid,
        "no_ask": no_ask_implied,
        "yes_depth_qty": depth_yes,
        "no_depth_qty": depth_no,
        "total_depth_qty": depth_yes + depth_no,
        "raw": book,
    }


def _pull_kalshi_market(
    session: requests.Session,
    market: dict[str, Any],
    snapshot_ts: datetime,
) -> PullResult:
    ticker = market["market_id"]
    rows: List[Dict[str, Any]] = []
    meta_rows: List[Dict[str, Any]] = []
    outcome_rows: List[Dict[str, Any]] = []
    errors: List[str] = []

    try:
        payload = _kalshi_market_payload(session, ticker)
        book = _kalshi_orderbook_payload(session, ticker)
    except Exception as exc:
        return PullResult([], [], [], [f"kalshi:{ticker}: {exc}"])

    bid_yes_raw = _first_non_null(book, ["yes_bid", "bid_yes", "yesBid"])
    if bid_yes_raw is None:
        bid_yes_raw = _first_non_null(payload, ["yes_bid", "bid_yes", "yesBid"])
    bid_yes = _probability(bid_yes_raw)

    ask_yes_raw = _first_non_null(book, ["yes_ask", "ask_yes", "yesAsk"])
    if ask_yes_raw is None:
        ask_yes_raw = _first_non_null(payload, ["yes_ask", "ask_yes", "yesAsk"])
    ask_yes = _probability(ask_yes_raw)

    last_yes = _probability(_first_non_null(payload, ["last_price", "lastPrice", "yes_price"]))

    # Fallback order:
    # 1) midpoint when both sides are present
    # 2) one-sided quote (bid or ask) for thin books
    # 3) last trade
    # 4) metadata probability hints
    prob_yes = None
    if bid_yes is not None and ask_yes is not None:
        prob_yes = (bid_yes + ask_yes) / 2.0
    elif bid_yes is not None:
        prob_yes = bid_yes
    elif ask_yes is not None:
        prob_yes = ask_yes
    if prob_yes is None:
        prob_yes = last_yes
    if prob_yes is None:
        prob_yes = _probability(_first_non_null(payload, ["yes_sub_title_prob", "yes_probability"]))
    if prob_yes is None:
        errors.append(f"kalshi:{ticker}: missing probability fields")
        return PullResult([], [], [], errors)

    prob_no = max(0.0, min(1.0, 1.0 - prob_yes))
    bid_no = (1.0 - ask_yes) if ask_yes is not None else None
    ask_no = (1.0 - bid_yes) if bid_yes is not None else None
    last_no = (1.0 - last_yes) if last_yes is not None else None

    volume_24h = _safe_float(_first_non_null(payload, ["volume_24h", "volume24h", "volume_1d"]))
    volume_total = _safe_float(_first_non_null(payload, ["volume", "volume_total", "total_volume"]))
    liquidity = _safe_float(_first_non_null(payload, ["liquidity", "liquidity_usd"]))
    open_interest = _safe_float(_first_non_null(payload, ["open_interest", "openInterest"]))

    # Kalshi markets payload frequently returns null volume/liquidity.
    # Fall back to orderbook resting depth as a proxy.
    if (volume_24h is None or volume_24h == 0) and book.get("total_depth_qty"):
        volume_24h = float(book["total_depth_qty"])
    if (liquidity is None or liquidity == 0) and book.get("total_depth_qty"):
        liquidity = float(book["total_depth_qty"])

    last_trade_ts = _parse_datetime(
        _first_non_null(payload, ["last_traded_ts", "last_trade_time", "updated_time"])
    )
    status = str(_first_non_null(payload, ["status", "market_status", "result"]) or "").lower()
    is_resolved = "settle" in status or "close" in status or "resolved" in status
    settlement_raw = _first_non_null(payload, ["settle_value", "result", "final_value"])
    resolution_value = _probability(settlement_raw)

    stale_yes = _infer_stale("kalshi", prob_yes, last_yes, last_trade_ts, volume_24h)
    stale_no = _infer_stale("kalshi", prob_no, last_no, last_trade_ts, volume_24h)

    rows.extend(
        [
            {
                "snapshot_ts": snapshot_ts,
                "snapshot_date": snapshot_ts.date(),
                "platform": "kalshi",
                "market_id": ticker,
                "outcome_id": f"{ticker}:YES",
                "probability": prob_yes,
                "bid": bid_yes,
                "ask": ask_yes,
                "spread_bps": (ask_yes - bid_yes) * 10000.0 if ask_yes is not None and bid_yes is not None else None,
                "last_traded_price": last_yes,
                "last_traded_ts": last_trade_ts,
                "volume_24h_usd": volume_24h,
                "volume_total_usd": volume_total,
                "liquidity_usd": liquidity,
                "open_interest_usd": open_interest,
                "is_stale": stale_yes,
                "is_resolved": is_resolved,
                "resolution_value": resolution_value,
            },
            {
                "snapshot_ts": snapshot_ts,
                "snapshot_date": snapshot_ts.date(),
                "platform": "kalshi",
                "market_id": ticker,
                "outcome_id": f"{ticker}:NO",
                "probability": prob_no,
                "bid": bid_no,
                "ask": ask_no,
                "spread_bps": (ask_no - bid_no) * 10000.0 if ask_no is not None and bid_no is not None else None,
                "last_traded_price": last_no,
                "last_traded_ts": last_trade_ts,
                "volume_24h_usd": volume_24h,
                "volume_total_usd": volume_total,
                "liquidity_usd": liquidity,
                "open_interest_usd": open_interest,
                "is_stale": stale_no,
                "is_resolved": is_resolved,
                "resolution_value": (1.0 - resolution_value) if resolution_value is not None else None,
            },
        ]
    )

    title = str(_first_non_null(payload, ["title", "market_title", "subtitle"]) or ticker)
    slug = str(_first_non_null(payload, ["ticker", "slug"]) or ticker)
    open_ts = _parse_datetime(_first_non_null(payload, ["open_time", "open_ts", "created_time"]))
    close_ts = _parse_datetime(_first_non_null(payload, ["close_time", "close_ts", "close_date"]))
    resolved_ts = _parse_datetime(
        _first_non_null(payload, ["settled_time", "resolved_time", "close_time"])
    ) if is_resolved else None

    meta_rows.append(
        {
            "market_id": ticker,
            "platform": "kalshi",
            "series_id": str(_first_non_null(payload, ["series_ticker", "series_id"]) or ""),
            "title": title,
            "slug": slug,
            "rules_text": str(market.get("rules_text", "") or _first_non_null(payload, ["rules_primary"]) or ""),
            "rules_url": str(market.get("rules_url", "") or _first_non_null(payload, ["rules_url"]) or ""),
            "resolution_source": str(
                market.get("resolution_source", "") or _first_non_null(payload, ["settlement_source"]) or ""
            ),
            "resolution_clarity": market["resolution_clarity"],
            "asado_category": market["asado_category"],
            "asado_subcategory": market.get("asado_subcategory"),
            "contract_type": str(market.get("contract_type", "binary")),
            "open_ts": open_ts,
            "close_ts": close_ts,
            "resolved_ts": resolved_ts,
            "last_updated_ts": snapshot_ts,
        }
    )

    outcome_rows.extend(
        [
            {
                "platform": "kalshi",
                "market_id": ticker,
                "outcome_id": f"{ticker}:YES",
                "label": "Yes",
                "threshold_low": None,
                "threshold_high": None,
                "sort_order": 1,
            },
            {
                "platform": "kalshi",
                "market_id": ticker,
                "outcome_id": f"{ticker}:NO",
                "label": "No",
                "threshold_low": None,
                "threshold_high": None,
                "sort_order": 2,
            },
        ]
    )

    return PullResult(rows, meta_rows, outcome_rows, errors)


def _resolve_polymarket_market(
    session: requests.Session,
    market: dict[str, Any],
) -> dict[str, Any]:
    """
    Resolve a curated Polymarket market entry to a live Gamma API record.

    STRICT RESOLUTION POLICY (no fuzzy fallback):
      1) If market_id is a real conditionId (0x + 64 hex), require exact
         match via ?condition_ids=...
      2) Else if slug exists, require exact slug match via ?slug=...
      3) Otherwise fail.
    """
    condition_id = str(market.get("market_id") or "").strip()
    slug = str(market.get("slug") or "").strip()

    cid_looks_real = (
        condition_id.startswith("0x")
        and len(condition_id) == 66
        and all(c in "0123456789abcdefABCDEF" for c in condition_id[2:])
    )

    if cid_looks_real:
        data = _fetch_json(
            session,
            f"{POLY_GAMMA_BASE}/markets",
            params={"condition_ids": condition_id, "limit": 5},
        )
        candidates = data if isinstance(data, list) else (data.get("markets") or [])
        for row in candidates:
            row_cid = str(_first_non_null(row, ["conditionId", "condition_id"]) or "")
            if row_cid.lower() == condition_id.lower():
                return row
        raise ValueError(
            f"Polymarket conditionId {condition_id!r} did not resolve to an exact match "
            f"(got {len(candidates)} candidates)."
        )

    if slug:
        data = _fetch_json(
            session,
            f"{POLY_GAMMA_BASE}/markets",
            params={"slug": slug, "limit": 5},
        )
        candidates = data if isinstance(data, list) else (data.get("markets") or [])
        for row in candidates:
            if str(row.get("slug", "")).strip() == slug:
                return row
        raise ValueError(
            f"Polymarket slug {slug!r} did not resolve to an exact match "
            f"(got {len(candidates)} candidates)."
        )

    raise ValueError(
        "Polymarket market entry has neither a real conditionId "
        f"(0x + 64 hex) nor a slug to resolve. Got market_id={condition_id!r}."
    )


def _clob_book(session: requests.Session, token_id: str) -> dict[str, Any]:
    try:
        data = _fetch_json(session, f"{POLY_CLOB_BASE}/book", params={"token_id": token_id})
        if isinstance(data, dict):
            return data
    except Exception:
        return {}
    return {}


def _best_book_prices(book: dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    bids = book.get("bids") or []
    asks = book.get("asks") or []
    best_bid = None
    best_ask = None
    if bids:
        head = bids[0]
        if isinstance(head, dict):
            best_bid = _probability(head.get("price"))
        elif isinstance(head, (list, tuple)) and head:
            best_bid = _probability(head[0])
    if asks:
        head = asks[0]
        if isinstance(head, dict):
            best_ask = _probability(head.get("price"))
        elif isinstance(head, (list, tuple)) and head:
            best_ask = _probability(head[0])
    return best_bid, best_ask


def _pull_polymarket_market(
    session: requests.Session,
    market: dict[str, Any],
    snapshot_ts: datetime,
) -> PullResult:
    market_id = market["market_id"]
    rows: List[Dict[str, Any]] = []
    meta_rows: List[Dict[str, Any]] = []
    outcome_rows: List[Dict[str, Any]] = []
    errors: List[str] = []

    try:
        payload = _resolve_polymarket_market(session, market)
    except Exception as exc:
        return PullResult([], [], [], [f"polymarket:{market_id}: {exc}"])

    labels = _parse_jsonish(_first_non_null(payload, ["outcomes", "outcomeLabels"])) or []
    prices = _parse_jsonish(_first_non_null(payload, ["outcomePrices", "outcome_prices"])) or []
    token_ids = _parse_jsonish(_first_non_null(payload, ["clobTokenIds", "token_ids"])) or []

    if not isinstance(labels, list):
        labels = []
    if not isinstance(prices, list):
        prices = []
    if not isinstance(token_ids, list):
        token_ids = []

    max_len = max(len(labels), len(prices), len(token_ids), 1)
    volume_24h = _safe_float(_first_non_null(payload, ["volume24hr", "volume24h", "volume_24h"]))
    volume_total = _safe_float(_first_non_null(payload, ["volume", "volumeNum", "volume_total"]))
    liquidity = _safe_float(_first_non_null(payload, ["liquidity", "liquidityNum"]))
    open_interest = None
    last_trade_ts = _parse_datetime(_first_non_null(payload, ["updatedAt", "lastTradeTimestamp"]))
    is_resolved = bool(
        _first_non_null(payload, ["closed", "resolved"])
    ) or str(_first_non_null(payload, ["status"]) or "").lower() in {"resolved", "closed"}
    winning_outcome = str(_first_non_null(payload, ["winningOutcome", "winner"]) or "").strip()

    title = str(_first_non_null(payload, ["question", "title", "name"]) or market_id)
    slug = str(_first_non_null(payload, ["slug"]) or market.get("slug") or market_id)
    open_ts = _parse_datetime(_first_non_null(payload, ["startDate", "startTime", "createdAt"]))
    close_ts = _parse_datetime(_first_non_null(payload, ["endDate", "endTime", "closeTime"]))
    resolved_ts = _parse_datetime(_first_non_null(payload, ["resolutionTime", "resolvedAt", "endDate"])) if is_resolved else None

    for i in range(max_len):
        label = str(labels[i]) if i < len(labels) else f"Outcome {i + 1}"
        token_id = str(token_ids[i]) if i < len(token_ids) else f"{market_id}:{i + 1}"
        probability = _probability(prices[i]) if i < len(prices) else None

        book = _clob_book(session, token_id) if token_id else {}
        bid, ask = _best_book_prices(book)
        if probability is None and bid is not None and ask is not None:
            probability = (bid + ask) / 2.0
        if probability is None:
            probability = _probability(_first_non_null(payload, ["lastTradePrice", "last_price"]))
        if probability is None:
            continue

        last_price = _probability(_first_non_null(book, ["mid", "last_price"])) or probability
        stale = _infer_stale("polymarket", probability, last_price, last_trade_ts, volume_24h)
        resolution_value = None
        if is_resolved:
            if winning_outcome:
                resolution_value = 1.0 if label.lower() == winning_outcome.lower() else 0.0
            elif len(labels) == 2:
                if label.lower() == "yes":
                    resolution_value = _probability(_first_non_null(payload, ["resolutionValue", "finalProbability"]))
                elif label.lower() == "no":
                    yes_val = _probability(_first_non_null(payload, ["resolutionValue", "finalProbability"]))
                    resolution_value = (1.0 - yes_val) if yes_val is not None else None

        rows.append(
            {
                "snapshot_ts": snapshot_ts,
                "snapshot_date": snapshot_ts.date(),
                "platform": "polymarket",
                "market_id": market_id,
                "outcome_id": token_id,
                "probability": probability,
                "bid": bid,
                "ask": ask,
                "spread_bps": (ask - bid) * 10000.0 if ask is not None and bid is not None else None,
                "last_traded_price": last_price,
                "last_traded_ts": last_trade_ts,
                "volume_24h_usd": volume_24h,
                "volume_total_usd": volume_total,
                "liquidity_usd": liquidity,
                "open_interest_usd": open_interest,
                "is_stale": stale,
                "is_resolved": is_resolved,
                "resolution_value": resolution_value,
            }
        )
        outcome_rows.append(
            {
                "platform": "polymarket",
                "market_id": market_id,
                "outcome_id": token_id,
                "label": label,
                "threshold_low": _safe_float(
                    (market.get("outcomes", [{}] * (i + 1))[i] or {}).get("threshold_low")
                    if i < len(market.get("outcomes", []))
                    else None
                ),
                "threshold_high": _safe_float(
                    (market.get("outcomes", [{}] * (i + 1))[i] or {}).get("threshold_high")
                    if i < len(market.get("outcomes", []))
                    else None
                ),
                "sort_order": i + 1,
            }
        )

    if not rows:
        return PullResult([], [], [], [f"polymarket:{market_id}: no valid outcomes found"])

    meta_rows.append(
        {
            "market_id": market_id,
            "platform": "polymarket",
            "series_id": str(_first_non_null(payload, ["eventId", "event_id", "series_id"]) or ""),
            "title": title,
            "slug": slug,
            "rules_text": str(market.get("rules_text", "") or _first_non_null(payload, ["description", "rules"]) or ""),
            "rules_url": str(market.get("rules_url", "") or _first_non_null(payload, ["url", "rules_url"]) or ""),
            "resolution_source": str(
                market.get("resolution_source", "") or _first_non_null(payload, ["resolutionSource"]) or ""
            ),
            "resolution_clarity": market["resolution_clarity"],
            "asado_category": market["asado_category"],
            "asado_subcategory": market.get("asado_subcategory"),
            "contract_type": str(
                market.get("contract_type") or _first_non_null(payload, ["marketType"]) or "binary"
            ),
            "open_ts": open_ts,
            "close_ts": close_ts,
            "resolved_ts": resolved_ts,
            "last_updated_ts": snapshot_ts,
        }
    )

    return PullResult(rows, meta_rows, outcome_rows, errors)


def _pull_markets(markets: list[dict[str, Any]], snapshot_ts: datetime) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str]]:
    session = _build_session()
    daily_rows: List[Dict[str, Any]] = []
    market_meta_rows: List[Dict[str, Any]] = []
    outcome_meta_rows: List[Dict[str, Any]] = []
    errors: List[str] = []

    active = [m for m in markets if m.get("is_active", True)]
    log.info("Polling prediction markets: %d active curated entries", len(active))

    for market in active:
        platform = market["platform"]
        if platform == "kalshi":
            result = _pull_kalshi_market(session, market, snapshot_ts)
        elif platform == "polymarket":
            result = _pull_polymarket_market(session, market, snapshot_ts)
        else:
            errors.append(f"{platform}:{market['market_id']}: unsupported platform")
            continue
        daily_rows.extend(result.daily_rows)
        market_meta_rows.extend(result.market_meta_rows)
        outcome_meta_rows.extend(result.outcome_meta_rows)
        errors.extend(result.errors)

    daily_df = pd.DataFrame(daily_rows)
    market_meta_df = pd.DataFrame(market_meta_rows)
    outcome_meta_df = pd.DataFrame(outcome_meta_rows)
    return daily_df, market_meta_df, outcome_meta_df, errors


def _create_tables(con: duckdb.DuckDBPyConnection, rebuild: bool = False) -> None:
    if rebuild:
        con.execute("DROP TABLE IF EXISTS predmkt_daily")
        con.execute("DROP TABLE IF EXISTS predmkt_market_meta")
        con.execute("DROP TABLE IF EXISTS predmkt_outcome_meta")
        con.execute("DROP TABLE IF EXISTS predmkt_country_spillover")
        con.execute("DROP TABLE IF EXISTS predmkt_resolutions")
        con.execute("DROP TABLE IF EXISTS predmkt_signals_daily")

    con.execute(
        """
        CREATE TABLE IF NOT EXISTS predmkt_daily (
            snapshot_ts TIMESTAMP,
            snapshot_date DATE,
            platform VARCHAR,
            market_id VARCHAR,
            outcome_id VARCHAR,
            probability DOUBLE,
            bid DOUBLE,
            ask DOUBLE,
            spread_bps DOUBLE,
            last_traded_price DOUBLE,
            last_traded_ts TIMESTAMP,
            volume_24h_usd DOUBLE,
            volume_total_usd DOUBLE,
            liquidity_usd DOUBLE,
            open_interest_usd DOUBLE,
            is_stale BOOLEAN,
            is_resolved BOOLEAN,
            resolution_value DOUBLE,
            PRIMARY KEY (snapshot_date, platform, market_id, outcome_id)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS predmkt_market_meta (
            market_id VARCHAR,
            platform VARCHAR,
            series_id VARCHAR,
            title VARCHAR,
            slug VARCHAR,
            rules_text VARCHAR,
            rules_url VARCHAR,
            resolution_source VARCHAR,
            resolution_clarity VARCHAR,
            asado_category VARCHAR,
            asado_subcategory VARCHAR,
            contract_type VARCHAR,
            open_ts TIMESTAMP,
            close_ts TIMESTAMP,
            resolved_ts TIMESTAMP,
            last_updated_ts TIMESTAMP,
            PRIMARY KEY (platform, market_id)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS predmkt_outcome_meta (
            platform VARCHAR,
            market_id VARCHAR,
            outcome_id VARCHAR,
            label VARCHAR,
            threshold_low DOUBLE,
            threshold_high DOUBLE,
            sort_order INTEGER,
            PRIMARY KEY (platform, market_id, outcome_id)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS predmkt_country_spillover (
            platform VARCHAR,
            market_id VARCHAR,
            country VARCHAR,
            elasticity DOUBLE,
            channel VARCHAR,
            confidence VARCHAR,
            notes VARCHAR,
            PRIMARY KEY (platform, market_id, country, channel)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS predmkt_resolutions (
            platform VARCHAR,
            market_id VARCHAR,
            resolved_ts TIMESTAMP,
            resolution_value DOUBLE,
            final_probability_24h_before DOUBLE,
            final_probability_1h_before DOUBLE,
            notes VARCHAR,
            PRIMARY KEY (platform, market_id)
        )
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS predmkt_signals_daily (
            snapshot_date DATE,
            signal_name VARCHAR,
            country VARCHAR,
            value DOUBLE,
            n_markets INTEGER,
            total_liquidity_usd DOUBLE,
            confidence_score DOUBLE,
            constituent_markets VARCHAR,
            PRIMARY KEY (snapshot_date, signal_name, country)
        )
        """
    )

    con.execute("CREATE INDEX IF NOT EXISTS idx_predmkt_daily_snapshot_date ON predmkt_daily(snapshot_date)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_predmkt_daily_market ON predmkt_daily(platform, market_id)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_predmkt_meta_category ON predmkt_market_meta(asado_category)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_predmkt_signal_name_date ON predmkt_signals_daily(signal_name, snapshot_date)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_predmkt_spill_country ON predmkt_country_spillover(country)")


def _backup_database(no_backup: bool = False) -> None:
    if no_backup:
        return
    if not DB_PATH.exists():
        raise FileNotFoundError(f"DuckDB file not found: {DB_PATH}")
    if BACKUP_PATH.exists():
        BACKUP_PATH.unlink()
    log.info("Backing up DuckDB -> %s", BACKUP_PATH.name)
    shutil.copy2(DB_PATH, BACKUP_PATH)


def _restore_backup(no_backup: bool = False) -> None:
    if no_backup:
        return
    if BACKUP_PATH.exists():
        log.warning("Restoring DuckDB from backup after failure")
        if DB_PATH.exists():
            DB_PATH.unlink()
        shutil.move(str(BACKUP_PATH), str(DB_PATH))


def _cleanup_backup(no_backup: bool = False) -> None:
    if no_backup:
        return
    if BACKUP_PATH.exists():
        BACKUP_PATH.unlink()


def _category_confidence(con: duckdb.DuckDBPyConnection) -> Dict[str, float]:
    tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    if "predmkt_resolutions" not in tables or "predmkt_market_meta" not in tables:
        return {}
    df = con.execute(
        """
        SELECT
            m.asado_category AS category,
            AVG(POWER(COALESCE(r.final_probability_24h_before, 0.5) - r.resolution_value, 2)) AS brier
        FROM predmkt_resolutions r
        JOIN predmkt_market_meta m
          ON m.platform = r.platform
         AND m.market_id = r.market_id
        WHERE r.resolution_value IS NOT NULL
        GROUP BY m.asado_category
        """
    ).fetchdf()
    mapping: Dict[str, float] = {}
    if df.empty:
        return mapping
    for _, row in df.iterrows():
        brier = _safe_float(row.get("brier"))
        if brier is None:
            continue
        mapping[str(row["category"])] = max(0.1, min(1.0, 1.0 - brier))
    return mapping


def _primary_outcome_rows(
    daily_df: pd.DataFrame,
    outcome_meta_df: pd.DataFrame,
) -> pd.DataFrame:
    if daily_df.empty:
        return pd.DataFrame(columns=["platform", "market_id", "outcome_id", "label", "probability", "liquidity_usd", "volume_24h_usd", "is_stale"])

    merged = daily_df.merge(
        outcome_meta_df[["platform", "market_id", "outcome_id", "label", "threshold_low", "threshold_high", "sort_order"]],
        how="left",
        on=["platform", "market_id", "outcome_id"],
    )
    merged["label"] = merged["label"].fillna("")
    merged["is_yes"] = merged["label"].str.lower().eq("yes")
    merged["sort_order"] = merged["sort_order"].fillna(999)
    merged = merged.sort_values(
        ["platform", "market_id", "is_yes", "sort_order", "probability"],
        ascending=[True, True, False, True, False],
    )
    return merged.groupby(["platform", "market_id"], as_index=False).head(1).copy()


def _weighted_probability(df: pd.DataFrame) -> Tuple[Optional[float], int, float, list[str]]:
    if df.empty:
        return None, 0, 0.0, []
    active = df[~df["is_stale"].fillna(True)].copy()
    if active.empty:
        return None, 0, 0.0, []
    weight = active["liquidity_usd"].fillna(0.0).clip(lower=0.0)
    weight = weight.where(weight > 0.0, active["volume_24h_usd"].fillna(0.0).clip(lower=0.0))
    active = active.assign(weight=weight)
    active = active[active["weight"] > 0]
    if active.empty:
        return None, 0, 0.0, []
    value = float((active["probability"] * active["weight"]).sum() / active["weight"].sum())
    markets = [f"{r.platform}:{r.market_id}" for r in active.itertuples(index=False)]
    return value, int(len(active)), float(active["weight"].sum()), sorted(set(markets))


def _threshold_midpoint(row: pd.Series) -> Optional[float]:
    low = _safe_float(row.get("threshold_low"))
    high = _safe_float(row.get("threshold_high"))
    if low is not None and high is not None:
        return (low + high) / 2.0
    label = str(row.get("label", ""))
    nums = re.findall(r"-?\d+(?:\.\d+)?", label)
    if not nums:
        return None
    if len(nums) == 1:
        return float(nums[0])
    return (float(nums[0]) + float(nums[1])) / 2.0


def _expectation_from_distribution(df: pd.DataFrame) -> Tuple[Optional[float], int, float, list[str]]:
    if df.empty:
        return None, 0, 0.0, []
    active = df[~df["is_stale"].fillna(True)].copy()
    if active.empty:
        return None, 0, 0.0, []
    active["midpoint"] = active.apply(_threshold_midpoint, axis=1)
    active = active.dropna(subset=["midpoint", "probability"])
    if active.empty:
        return None, 0, 0.0, []
    active["market_weight"] = active["liquidity_usd"].fillna(0.0).clip(lower=0.0)
    active["market_weight"] = active["market_weight"].where(
        active["market_weight"] > 0.0,
        active["volume_24h_usd"].fillna(0.0).clip(lower=0.0),
    )
    active = active[active["market_weight"] > 0]
    if active.empty:
        return None, 0, 0.0, []

    grouped = (
        active.groupby(["platform", "market_id"], as_index=False)
        .apply(
            lambda x: pd.Series(
                {
                    "expected": float((x["midpoint"] * x["probability"]).sum()),
                    "weight": float(x["market_weight"].max()),
                }
            )
        )
        .reset_index(drop=True)
    )
    if grouped.empty:
        return None, 0, 0.0, []
    expected = float((grouped["expected"] * grouped["weight"]).sum() / grouped["weight"].sum())
    markets = [f"{r.platform}:{r.market_id}" for r in grouped.itertuples(index=False)]
    return expected, int(len(grouped)), float(grouped["weight"].sum()), sorted(set(markets))


def _compute_signals(
    con: duckdb.DuckDBPyConnection,
    snapshot_date: date,
    daily_df: pd.DataFrame,
    market_meta_df: pd.DataFrame,
    outcome_meta_df: pd.DataFrame,
    spillover_df: pd.DataFrame,
) -> pd.DataFrame:
    if daily_df.empty or market_meta_df.empty:
        return pd.DataFrame(
            columns=[
                "snapshot_date",
                "signal_name",
                "country",
                "value",
                "n_markets",
                "total_liquidity_usd",
                "confidence_score",
                "constituent_markets",
            ]
        )

    merged = daily_df.merge(
        market_meta_df[["platform", "market_id", "asado_category", "asado_subcategory"]],
        on=["platform", "market_id"],
        how="left",
    ).merge(
        outcome_meta_df[["platform", "market_id", "outcome_id", "label", "threshold_low", "threshold_high"]],
        on=["platform", "market_id", "outcome_id"],
        how="left",
    )

    primary = _primary_outcome_rows(daily_df, outcome_meta_df).merge(
        market_meta_df[["platform", "market_id", "asado_category", "asado_subcategory"]],
        on=["platform", "market_id"],
        how="left",
    )
    confidence_map = _category_confidence(con)

    def _signal_confidence(categories: Iterable[str]) -> float:
        vals = [confidence_map.get(cat, 0.6) for cat in categories if isinstance(cat, str)]
        if not vals:
            return 0.6
        return float(sum(vals) / len(vals))

    rows: List[Dict[str, Any]] = []

    def append_signal(
        signal_name: str,
        value: Optional[float],
        n_markets: int,
        total_liquidity: float,
        constituent: list[str],
        categories: Iterable[str],
        country: Optional[str] = None,
    ) -> None:
        if value is None:
            return
        signal_country = country if country else "__GLOBAL__"
        rows.append(
            {
                "snapshot_date": snapshot_date,
                "signal_name": signal_name,
                "country": signal_country,
                "value": float(value),
                "n_markets": int(n_markets),
                "total_liquidity_usd": float(total_liquidity),
                "confidence_score": _signal_confidence(categories),
                "constituent_markets": json.dumps(sorted(set(constituent))),
            }
        )

    fed_cut_df = merged[merged["asado_subcategory"].fillna("").str.contains("fed_cut_count", case=False)]
    v, n, liq, mkts = _expectation_from_distribution(fed_cut_df)
    append_signal("fed_cut_count_expectation", v, n, liq, mkts, ["fed_policy"])

    fed_dist_df = merged[merged["asado_subcategory"].fillna("").str.contains("fed_decision", case=False)]
    v, n, liq, mkts = _expectation_from_distribution(fed_dist_df)
    append_signal("fed_decision_distribution_next", v, n, liq, mkts, ["fed_policy"])

    cpi_yoy_df = merged[
        (merged["asado_category"] == "cpi")
        & (merged["asado_subcategory"].fillna("").str.contains("yoy", case=False))
    ]
    v, n, liq, mkts = _expectation_from_distribution(cpi_yoy_df)
    append_signal("cpi_nowcast_yoy_next", v, n, liq, mkts, ["cpi"])

    cpi_core_df = merged[
        (merged["asado_category"] == "cpi")
        & (merged["asado_subcategory"].fillna("").str.contains("core", case=False))
    ]
    v, n, liq, mkts = _expectation_from_distribution(cpi_core_df)
    append_signal("cpi_nowcast_core_next", v, n, liq, mkts, ["cpi"])

    unemp_df = merged[merged["asado_category"] == "unemployment"]
    v, n, liq, mkts = _expectation_from_distribution(unemp_df)
    append_signal("unemployment_nowcast_next", v, n, liq, mkts, ["unemployment"])

    recession_df = primary[
        (primary["asado_category"] == "gdp_recession")
        & (primary["asado_subcategory"].fillna("").str.contains("recession", case=False))
    ]
    v, n, liq, mkts = _weighted_probability(recession_df)
    append_signal("recession_prob_12m", v, n, liq, mkts, ["gdp_recession"])

    oil_df = primary[primary["asado_category"] == "oil_shock"]
    v, n, liq, mkts = _weighted_probability(oil_df)
    append_signal("oil_shock_prob_30d", v, n, liq, mkts, ["oil_shock"])

    hormuz_df = primary[primary["asado_subcategory"].fillna("").str.contains("hormuz", case=False)]
    v, n, liq, mkts = _weighted_probability(hormuz_df)
    append_signal("hormuz_disruption_prob_90d", v, n, liq, mkts, ["regional_conflict_me", "oil_shock"])

    me_df = primary[primary["asado_category"] == "regional_conflict_me"]
    v, n, liq, mkts = _weighted_probability(me_df)
    append_signal("regional_conflict_premium_middle_east", v, n, liq, mkts, ["regional_conflict_me"])

    pacific_df = primary[primary["asado_category"] == "regional_conflict_pacific"]
    v, n, liq, mkts = _weighted_probability(pacific_df)
    append_signal("regional_conflict_premium_pacific", v, n, liq, mkts, ["regional_conflict_pacific"])

    ee_df = primary[primary["asado_category"] == "regional_conflict_eastern_europe"]
    v, n, liq, mkts = _weighted_probability(ee_df)
    append_signal("regional_conflict_premium_eastern_europe", v, n, liq, mkts, ["regional_conflict_eastern_europe"])

    if not spillover_df.empty:
        country_join = spillover_df.merge(
            primary[
                [
                    "platform",
                    "market_id",
                    "probability",
                    "liquidity_usd",
                    "volume_24h_usd",
                    "is_stale",
                    "asado_category",
                ]
            ],
            on=["platform", "market_id"],
            how="left",
        )
        country_join = country_join.dropna(subset=["probability"])
        if not country_join.empty:
            country_join["confidence_mult"] = country_join["confidence"].map(SIGNAL_CONFIDENCE_WEIGHT).fillna(0.75)
            country_join["liquidity_weight"] = country_join["liquidity_usd"].fillna(0.0).clip(lower=0.0)
            country_join["liquidity_weight"] = country_join["liquidity_weight"].where(
                country_join["liquidity_weight"] > 0.0,
                country_join["volume_24h_usd"].fillna(0.0).clip(lower=0.0),
            )
            stale_mask = country_join["is_stale"].astype("boolean").fillna(True)
            country_join["effective_weight"] = country_join["liquidity_weight"] * country_join["confidence_mult"]
            country_join["effective_weight"] = country_join["effective_weight"].where(
                ~stale_mask,
                0.0,
            )
            country_join = country_join[country_join["effective_weight"] > 0]

            tariff_join = country_join[country_join["asado_category"].isin(["tariff", "trade_war"])]
            if not tariff_join.empty:
                grouped = tariff_join.groupby("country", as_index=False)
                for _, grp in grouped:
                    weight_sum = float(grp["effective_weight"].sum())
                    value = float((grp["probability"] * grp["effective_weight"]).sum() / weight_sum)
                    append_signal(
                        "tariff_intensity_by_country",
                        value,
                        int(grp["market_id"].nunique()),
                        weight_sum,
                        [f"{r.platform}:{r.market_id}" for r in grp.itertuples(index=False)],
                        ["tariff", "trade_war"],
                        country=str(grp["country"].iloc[0]),
                    )

            country_join["signed_effect"] = (
                country_join["probability"]
                * country_join["elasticity"].fillna(0.0)
                * country_join["effective_weight"]
            )
            grouped = country_join.groupby("country", as_index=False)
            for _, grp in grouped:
                country_name = str(grp["country"].iloc[0])
                liq_sum = float(grp["effective_weight"].sum())
                risk_value = float(grp["signed_effect"].sum() / liq_sum) if liq_sum > 0 else None
                if risk_value is None:
                    continue
                append_signal(
                    "predmkt_country_risk_composite",
                    risk_value,
                    int(grp["market_id"].nunique()),
                    liq_sum,
                    [f"{r.platform}:{r.market_id}" for r in grp.itertuples(index=False)],
                    grp["asado_category"].dropna().tolist(),
                    country=country_name,
                )
                append_signal(
                    "predmkt_country_opportunity_composite",
                    -risk_value,
                    int(grp["market_id"].nunique()),
                    liq_sum,
                    [f"{r.platform}:{r.market_id}" for r in grp.itertuples(index=False)],
                    grp["asado_category"].dropna().tolist(),
                    country=country_name,
                )

    if not rows:
        base = pd.DataFrame(
            columns=[
                "snapshot_date",
                "signal_name",
                "country",
                "value",
                "n_markets",
                "total_liquidity_usd",
                "confidence_score",
                "constituent_markets",
            ]
        )
        return base

    signal_df = pd.DataFrame(rows)
    required_global = {
        "fed_cut_count_expectation",
        "fed_decision_distribution_next",
        "cpi_nowcast_yoy_next",
        "cpi_nowcast_core_next",
        "unemployment_nowcast_next",
        "recession_prob_12m",
        "oil_shock_prob_30d",
        "hormuz_disruption_prob_90d",
        "regional_conflict_premium_middle_east",
        "regional_conflict_premium_pacific",
        "regional_conflict_premium_eastern_europe",
    }
    present_global = {
        row.signal_name
        for row in signal_df.itertuples(index=False)
        if row.country == "__GLOBAL__"
    }
    missing_global = sorted(required_global - present_global)
    if missing_global:
        placeholders = pd.DataFrame(
            [
                {
                    "snapshot_date": snapshot_date,
                    "signal_name": name,
                    "country": "__GLOBAL__",
                    "value": None,
                    "n_markets": 0,
                    "total_liquidity_usd": 0.0,
                    "confidence_score": 0.0,
                    "constituent_markets": "[]",
                }
                for name in missing_global
            ]
        )
        signal_df = pd.concat([signal_df, placeholders], ignore_index=True)

    return signal_df


def _build_resolution_rows(
    con: duckdb.DuckDBPyConnection,
    daily_df: pd.DataFrame,
    market_meta_df: pd.DataFrame,
    outcome_meta_df: pd.DataFrame,
) -> pd.DataFrame:
    if daily_df.empty or market_meta_df.empty:
        return pd.DataFrame(
            columns=[
                "platform",
                "market_id",
                "resolved_ts",
                "resolution_value",
                "final_probability_24h_before",
                "final_probability_1h_before",
                "notes",
            ]
        )
    resolved_markets = market_meta_df.dropna(subset=["resolved_ts"]).copy()
    if resolved_markets.empty:
        return pd.DataFrame(
            columns=[
                "platform",
                "market_id",
                "resolved_ts",
                "resolution_value",
                "final_probability_24h_before",
                "final_probability_1h_before",
                "notes",
            ]
        )

    primary = _primary_outcome_rows(daily_df, outcome_meta_df)
    rows: List[Dict[str, Any]] = []
    for market in resolved_markets.itertuples(index=False):
        subset = primary[
            (primary["platform"] == market.platform)
            & (primary["market_id"] == market.market_id)
        ]
        if subset.empty:
            continue
        current_prob = _safe_float(subset.iloc[0]["probability"])
        resolution_value = _safe_float(subset.iloc[0]["resolution_value"])
        resolved_ts = _parse_datetime(market.resolved_ts) or datetime.now(timezone.utc)

        prior_24h = con.execute(
            """
            SELECT probability
            FROM predmkt_daily
            WHERE platform = ?
              AND market_id = ?
              AND snapshot_ts <= ?
            ORDER BY snapshot_ts DESC
            LIMIT 1
            """,
            [market.platform, market.market_id, resolved_ts - timedelta(hours=24)],
        ).fetchone()
        prior_1h = con.execute(
            """
            SELECT probability
            FROM predmkt_daily
            WHERE platform = ?
              AND market_id = ?
              AND snapshot_ts <= ?
            ORDER BY snapshot_ts DESC
            LIMIT 1
            """,
            [market.platform, market.market_id, resolved_ts - timedelta(hours=1)],
        ).fetchone()

        rows.append(
            {
                "platform": market.platform,
                "market_id": market.market_id,
                "resolved_ts": resolved_ts,
                "resolution_value": resolution_value,
                "final_probability_24h_before": _safe_float(prior_24h[0]) if prior_24h else current_prob,
                "final_probability_1h_before": _safe_float(prior_1h[0]) if prior_1h else current_prob,
                "notes": "auto-captured on resolved market snapshot",
            }
        )
    return pd.DataFrame(rows)


def _upsert_table(
    con: duckdb.DuckDBPyConnection,
    table: str,
    df: pd.DataFrame,
    key_cols: list[str],
) -> None:
    if df.empty:
        return
    stage = f"stage_{table}"
    con.register(stage, df)
    join_cond = " AND ".join([f"t.{c} = s.{c}" for c in key_cols])
    con.execute(f"DELETE FROM {table} t USING {stage} s WHERE {join_cond}")
    con.execute(f"INSERT INTO {table} SELECT * FROM {stage}")
    con.unregister(stage)


def _replace_snapshot_table(
    con: duckdb.DuckDBPyConnection,
    table: str,
    df: pd.DataFrame,
    snapshot_date: date,
    date_col: str,
) -> None:
    con.execute(f"DELETE FROM {table} WHERE {date_col} = ?", [snapshot_date])
    if df.empty:
        return
    stage = f"stage_{table}"
    con.register(stage, df)
    con.execute(f"INSERT INTO {table} SELECT * FROM {stage}")
    con.unregister(stage)


def _upsert_variable_meta(con: duckdb.DuckDBPyConnection, signal_names: list[str]) -> None:
    if not signal_names:
        return
    tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    if "variable_meta" not in tables:
        return
    rows = pd.DataFrame(
        [
            {
                "variable": name,
                "source_table": "predmkt_signals_daily",
                "source_file": "predmkt_derived",
                "native_frequency": "D",
                "monthly_equivalent": None,
                "is_normalized": False,
                "category": "predmkt_signal",
                "is_optimizer_selected": False,
            }
            for name in sorted(set(signal_names))
        ]
    )
    if rows.empty:
        return
    con.register("stage_predmkt_variable_meta", rows)
    con.execute(
        """
        DELETE FROM variable_meta
        WHERE source_table = 'predmkt_signals_daily'
          AND variable IN (SELECT variable FROM stage_predmkt_variable_meta)
        """
    )
    con.execute(
        """
        INSERT INTO variable_meta (
            variable, source_table, source_file, native_frequency,
            monthly_equivalent, is_normalized, category, is_optimizer_selected
        )
        SELECT
            variable, source_table, source_file, native_frequency,
            monthly_equivalent, is_normalized, category, is_optimizer_selected
        FROM stage_predmkt_variable_meta
        """
    )
    con.unregister("stage_predmkt_variable_meta")


def _print_stats(con: duckdb.DuckDBPyConnection) -> None:
    print("=" * 70)
    print("Prediction Markets Table Stats")
    print("=" * 70)
    targets = [
        "predmkt_daily",
        "predmkt_market_meta",
        "predmkt_outcome_meta",
        "predmkt_country_spillover",
        "predmkt_resolutions",
        "predmkt_signals_daily",
    ]
    tables = {row[0] for row in con.execute("SHOW TABLES").fetchall()}
    for table in targets:
        if table not in tables:
            print(f"{table:<28} missing")
            continue
        row_count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table:<28} {row_count:>12,} rows")
    if "predmkt_daily" in tables:
        dmin, dmax = con.execute("SELECT MIN(snapshot_date), MAX(snapshot_date) FROM predmkt_daily").fetchone()
        print(f"predmkt_daily date range: {dmin} -> {dmax}")
    if "predmkt_signals_daily" in tables:
        signal_count = con.execute("SELECT COUNT(DISTINCT signal_name) FROM predmkt_signals_daily").fetchone()[0]
        print(f"distinct signal_name count: {signal_count}")


def _run_check_mode(markets: list[dict[str, Any]]) -> int:
    print("=" * 70)
    print("Prediction Markets Registry Check")
    print("=" * 70)
    print(f"Registry path: {REGISTRY_PATH}")
    print(f"Curated records: {len(markets)}")
    active = sum(1 for m in markets if m.get("is_active", True))
    print(f"Active records:  {active}")
    by_platform = {}
    for m in markets:
        by_platform[m["platform"]] = by_platform.get(m["platform"], 0) + 1
    print(f"By platform:    {by_platform}")

    if not DB_PATH.exists():
        print(f"\nDuckDB missing: {DB_PATH}")
        return 1
    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        _print_stats(con)
    finally:
        con.close()
    return 0


def _run_validate_only_mode(markets: list[dict[str, Any]]) -> int:
    """
    Validate that each active curated market resolves to a live API record.
    No DuckDB writes. Returns non-zero if any active market fails.
    """
    print("=" * 70)
    print("Prediction Markets Registry Validation")
    print("=" * 70)
    print(f"Registry: {REGISTRY_PATH}")
    print(f"Active records: {sum(1 for m in markets if m.get('is_active', True))}\n")

    session = _build_session()
    failures: list[tuple[dict[str, Any], str]] = []
    successes = 0

    for market in markets:
        if not market.get("is_active", True):
            continue
        platform = market["platform"]
        market_id = market["market_id"]
        slug = market.get("slug", "")
        try:
            if platform == "kalshi":
                payload = _kalshi_market_payload(session, market_id)
                title = str(_first_non_null(payload, ["title", "subtitle"]) or "?")[:70]
                book = _kalshi_orderbook_payload(session, market_id)
                yes_bid = book.get("yes_bid")
                yes_ask = book.get("yes_ask")
                depth = book.get("total_depth_qty", 0.0)
                print(f"  ✓ kalshi:{market_id}")
                print(f"      {title}")
                print(f"      yes_bid/ask: {yes_bid}/{yes_ask}  depth: {depth}")
                successes += 1
            elif platform == "polymarket":
                payload = _resolve_polymarket_market(session, market)
                title = str(_first_non_null(payload, ["question", "title"]) or "?")[:70]
                vol24h = payload.get("volume24hr") or 0
                liq = payload.get("liquidity") or payload.get("liquidityNum") or 0
                end = str(payload.get("endDate") or "")[:10]
                label = slug if slug else f"{market_id[:24]}..."
                print(f"  ✓ polymarket:{label}")
                print(f"      {title}")
                print(f"      vol24h: ${vol24h}  liq: ${liq}  ends: {end}")
                successes += 1
            else:
                raise ValueError(f"unsupported platform: {platform}")
        except Exception as exc:
            failures.append((market, str(exc)))
            print(f"  ✗ {platform}:{market_id}")
            print(f"      slug:  {slug or '(none)'}")
            print(f"      error: {exc}")

    print()
    print("=" * 70)
    print(f"Resolved: {successes}  |  Failed: {len(failures)}")
    print("=" * 70)
    if failures:
        print("\nFailed markets need fresh condition_ids / tickers from the live API.")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build ASADO prediction-market daily panel and signals.")
    parser.add_argument("--check", action="store_true", help="Validate registry and print DB stats only.")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Verify every curated market resolves to a live API record. Exits non-zero on any failure. No DB writes.",
    )
    parser.add_argument("--stats", action="store_true", help="Print table stats after run.")
    parser.add_argument("--rebuild", action="store_true", help="Drop and rebuild prediction-market tables.")
    parser.add_argument("--dry-run", action="store_true", help="Pull/compute but do not write DB tables.")
    parser.add_argument("--no-backup", action="store_true", help="Skip DB backup before writes.")
    args = parser.parse_args()

    start = time.time()
    snapshot_ts = datetime.now(timezone.utc)
    snapshot_date = snapshot_ts.date()

    try:
        markets = _validate_registry(_load_registry())
    except Exception as exc:
        log.error("Registry validation failed: %s", exc)
        return 1

    if args.check:
        return _run_check_mode(markets)
    if args.validate_only:
        return _run_validate_only_mode(markets)

    if not DB_PATH.exists():
        log.error("DuckDB not found: %s", DB_PATH)
        return 1

    daily_df, market_meta_df, outcome_meta_df, pull_errors = _pull_markets(markets, snapshot_ts)
    spillover_df = pd.DataFrame(_as_spillover_rows(markets))
    if pull_errors:
        for err in pull_errors:
            log.warning(err)

    log.info(
        "Pulled snapshot rows: daily=%s meta=%s outcomes=%s spillover=%s",
        f"{len(daily_df):,}",
        f"{len(market_meta_df):,}",
        f"{len(outcome_meta_df):,}",
        f"{len(spillover_df):,}",
    )

    if args.dry_run:
        print("=" * 70)
        print("DRY RUN — no DuckDB writes")
        print("=" * 70)
        print(f"snapshot_date: {snapshot_date}")
        print(f"daily_rows:    {len(daily_df):,}")
        print(f"meta_rows:     {len(market_meta_df):,}")
        print(f"outcome_rows:  {len(outcome_meta_df):,}")
        print(f"spillover_rows:{len(spillover_df):,}")
        print(f"errors:        {len(pull_errors):,}")
        return 0

    try:
        _backup_database(no_backup=args.no_backup)
        con = duckdb.connect(str(DB_PATH))
        con.execute("SET memory_limit = '8GB'")
        con.execute("SET threads = 8")
        _create_tables(con, rebuild=args.rebuild)

        resolution_df = _build_resolution_rows(con, daily_df, market_meta_df, outcome_meta_df)
        signals_df = _compute_signals(
            con=con,
            snapshot_date=snapshot_date,
            daily_df=daily_df,
            market_meta_df=market_meta_df,
            outcome_meta_df=outcome_meta_df,
            spillover_df=spillover_df,
        )

        _replace_snapshot_table(con, "predmkt_daily", daily_df, snapshot_date, "snapshot_date")
        _replace_snapshot_table(con, "predmkt_signals_daily", signals_df, snapshot_date, "snapshot_date")
        _upsert_table(con, "predmkt_market_meta", market_meta_df, ["platform", "market_id"])
        _upsert_table(con, "predmkt_outcome_meta", outcome_meta_df, ["platform", "market_id", "outcome_id"])
        _upsert_table(con, "predmkt_country_spillover", spillover_df, ["platform", "market_id", "country", "channel"])
        _upsert_table(con, "predmkt_resolutions", resolution_df, ["platform", "market_id"])
        _upsert_variable_meta(con, signals_df["signal_name"].dropna().astype(str).tolist())

        if args.stats:
            _print_stats(con)
        con.close()
        _cleanup_backup(no_backup=args.no_backup)
    except Exception as exc:
        log.error("Prediction-markets build failed: %s", exc)
        log.exception(exc)
        _restore_backup(no_backup=args.no_backup)
        return 1

    elapsed = time.time() - start
    log.info("Prediction-markets build completed in %.1fs", elapsed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
