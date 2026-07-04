"""
=============================================================================
SCRIPT NAME: predmkt_equity_common.py
=============================================================================

INPUT FILES:
- None (pure library module; operates on Gamma API market/event dicts passed
  in by callers)

OUTPUT FILES:
- None (pure library module; no file I/O)

VERSION: 1.0
LAST UPDATED: 2026-07-03
AUTHOR: Claude Code (for Arjun Divecha)

DESCRIPTION:
Shared parsing and direction-cleaning logic for Polymarket firm-level equity
markets (Tier 1 overnight prediction-market -> equity signal, per
PRD_Overnight_Signal). Maps a raw Gamma API market record (question text +
token metadata) to a structured record: underlying ticker, target price,
direction, contract class, and the YES-alignment flag that orients every
contract so its aligned price RISES when the underlying stock rises
("direction cleaning" from Li & Wang 2026 §5.2).

Contract classes recognised (verified against 11,418 live/closed markets,
July 2026):
  hit_high            "Will NVIDIA (NVDA) hit (HIGH) $204 Week of April 6?"   -> rises
  hit_low             "Will NVIDIA (NVDA) hit (LOW) $176 Week of April 6?"    -> falls (invert)
  close_above_daily   "Will Google (GOOGL) close above $310 on April 13?"     -> rises
  close_above_period  "Will Amazon (AMZN) close above $150 end of April?"     -> rises
  finish_week_above   "Will Amazon (AMZN) finish week of April 6 above $180?" -> rises
  up_or_down          "Coinbase (COIN) Up or Down on April 13?"               -> rises (Up leg)

Bucket markets ("close at $X-$Y") are deliberately NOT parsed — they are not
directional binaries and are excluded from the Tier 1 universe.

USAGE:
  from scripts.predmkt_equity_common import parse_stock_market, aligned_price
  rec = parse_stock_market(market_dict, event_dict)   # None if not directional
  p_aligned = aligned_price(p_yes, rec["yes_rises_with_stock"])

DEPENDENCIES:
- Standard library only (json, re, datetime)

NOTES:
- clobTokenIds[0] always corresponds to outcomes[0] ("Yes" or "Up").
- endDate on the market is the contract resolution date (UTC).
- Tickers observed in the wild include ETFs (SPY, QQQ, EWY, SPCX); records
  carry an is_etf flag so callers can filter.
=============================================================================
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

# ETFs seen in the Polymarket stock universe (not single-name equities).
KNOWN_ETFS = {"SPY", "QQQ", "EWY", "SPCX", "IWM", "DIA", "GLD", "EEM", "EFA"}

# ── Question regexes (anchored to the exact phrasings observed live) ─────────
_RE_HIT = re.compile(
    r"^Will (?P<name>.+?) \((?P<ticker>[A-Z\.\-]{1,6})\) hit \((?P<side>HIGH|LOW)\)"
    r" \$(?P<price>[\d,]+(?:\.\d+)?) (?:Week of (?P<week>.+?)|in (?P<month>.+?))\?$"
)
_RE_CLOSE_ABOVE = re.compile(
    r"^(?:Will )?(?P<name>.+?) \((?P<ticker>[A-Z\.\-]{1,6})\) closes? above"
    r" \$(?P<price>[\d,]+(?:\.\d+)?) (?P<when_kind>on|end of) (?P<when>.+?)\?$"
)
_RE_FINISH_WEEK = re.compile(
    r"^Will (?P<name>.+?) \((?P<ticker>[A-Z\.\-]{1,6})\) finish week of"
    r" (?P<week>.+?) above \$(?P<price>[\d,]+(?:\.\d+)?)\?$"
)
_RE_UP_DOWN = re.compile(
    r"^(?P<name>.+?) \((?P<ticker>[A-Z\.\-]{1,6})\) Up or Down on (?P<when>.+?)\?$"
)


def _parse_price(raw: str) -> float:
    return float(raw.replace(",", ""))


def _token_ids(market: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Return (yes_token, no_token) from a Gamma market record.

    clobTokenIds may arrive as a JSON-encoded string or a list. Index 0
    corresponds to outcomes[0] ("Yes" / "Up").
    """
    raw = market.get("clobTokenIds")
    if raw is None:
        return None, None
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (ValueError, TypeError):
            return None, None
    if not isinstance(raw, list) or len(raw) < 2:
        return None, None
    return str(raw[0]), str(raw[1])


def parse_stock_market(
    market: Dict[str, Any], event: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """Parse one Gamma market record into a structured directional record.

    Returns None for anything that is not a recognised directional binary
    (bucket markets, non-equity questions, malformed records). Never raises
    on unexpected question text — unparseable means None.
    """
    question = (market.get("question") or "").strip()
    if not question:
        return None

    contract_class = None
    ticker = None
    name = None
    target_price = None
    direction = None  # above | below | up

    m = _RE_HIT.match(question)
    if m:
        side = m.group("side")
        contract_class = "hit_high" if side == "HIGH" else "hit_low"
        direction = "above" if side == "HIGH" else "below"
        ticker, name = m.group("ticker"), m.group("name")
        target_price = _parse_price(m.group("price"))
    if contract_class is None:
        m = _RE_CLOSE_ABOVE.match(question)
        if m:
            contract_class = (
                "close_above_daily" if m.group("when_kind") == "on" else "close_above_period"
            )
            direction = "above"
            ticker, name = m.group("ticker"), m.group("name")
            target_price = _parse_price(m.group("price"))
    if contract_class is None:
        m = _RE_FINISH_WEEK.match(question)
        if m:
            contract_class = "finish_week_above"
            direction = "above"
            ticker, name = m.group("ticker"), m.group("name")
            target_price = _parse_price(m.group("price"))
    if contract_class is None:
        m = _RE_UP_DOWN.match(question)
        if m:
            contract_class = "up_or_down"
            direction = "up"
            ticker, name = m.group("ticker"), m.group("name")

    if contract_class is None:
        return None

    yes_token, no_token = _token_ids(market)
    if yes_token is None:
        return None

    # Direction cleaning: the aligned series must rise when the stock rises.
    # Only the "hit LOW" (touch a downside barrier) YES leg pays when the
    # stock FALLS, so it is the only class that inverts.
    yes_rises_with_stock = contract_class != "hit_low"

    end_date = market.get("endDate") or (event or {}).get("endDate")

    return {
        "platform": "polymarket",
        "market_id": market.get("conditionId"),
        "slug": market.get("slug"),
        "question": question,
        "ticker": ticker,
        "company": name,
        "is_etf": ticker in KNOWN_ETFS,
        "contract_class": contract_class,
        "target_price": target_price,
        "direction": direction,
        "yes_rises_with_stock": yes_rises_with_stock,
        "yes_token_id": yes_token,
        "no_token_id": no_token,
        "start_date": market.get("startDate"),
        "resolve_date": end_date,
        "volume_usd": market.get("volumeNum"),
        "event_slug": (event or {}).get("slug"),
        "event_title": (event or {}).get("title"),
    }


def aligned_price(p_yes: Optional[float], yes_rises_with_stock: bool) -> Optional[float]:
    """Return the stock-up-aligned probability for a contract."""
    if p_yes is None:
        return None
    return p_yes if yes_rises_with_stock else 1.0 - p_yes
