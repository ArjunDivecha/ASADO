#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: country_news.py
=============================================================================

INPUT FILES:
- (none on disk) Live HTTPS calls to the GDELT DOC 2.0 API:
  https://api.gdeltproject.org/api/v2/doc/doc
  Free, no key. Rolling ~3-month full-text search window.

OUTPUT FILES:
- (none) Returns results in memory / prints to stdout. Nothing is stored -
  this is the deliberately stateless v0 of the article-evidence layer
  (PRD_Alpha_Hunting_Loop.md section 8, priority 4). The cached
  `gdelt_articles_recent` table + evidence packs are the Phase 2 v1.

VERSION: 1.0
LAST UPDATED: 2026-06-10
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 0d)

DESCRIPTION:
Fetches the actual news headlines behind a country's GDELT attention numbers.
ASADO stores only aggregates (tone averages, attention counts); when an
attention spike fires, this module answers "what is the news actually
saying?" by pulling the article list (headline, source domain, URL, language,
timestamp) for one T2 country over a recent window. Headlines are deduped
(wire stories repeat across hundreds of outlets) and returned newest-first
by relevance. A 10th grader's version: the database tells us "Indonesia is
suddenly in the news a lot"; this tool fetches the actual headlines so we
can see WHY.

RATE LIMITS (FAIL-IS-FAIL): the GDELT API throttles by IP (HTTP 429). On
429 this module retries with backoff, then raises GdeltRateLimited - it
never fabricates or silently truncates results.

DEPENDENCIES:
- requests (project venv)

USAGE:
 python scripts/loop/country_news.py Indonesia                # last 1 day
 python scripts/loop/country_news.py Korea --days 3 --max 40
 python scripts/loop/country_news.py Turkey --extra "lira OR cenbank"
 # As a library (used by the ASADO MCP server's country_news tool):
 from scripts.loop.country_news import fetch_country_news
=============================================================================
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Optional

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.loop.loopdb import T2_UNIVERSE

DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"
# GDELT rate-limits per IP and (verified empirically 2026-06-10) the cooldown
# clock RESETS on every probe: short-spaced retries keep the IP blocked
# indefinitely. So: browser-style UA, self-enforced 5s pacing, and FEW retries
# with LONG waits. If the tool still fails, stop calling for 15+ minutes.
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ASADO-research/1.0"
MIN_SECONDS_BETWEEN_REQUESTS = 5.5
RETRY_WAITS = [60, 180]  # seconds before 2nd and 3rd attempt
_last_request_ts: float = 0.0

# T2 names -> GDELT free-text search phrase. Market sleeves map to their
# economy; phrases are quoted in the query where multi-word.
SEARCH_NAME = {
    "ChinaA": "China",
    "ChinaH": "China",
    "Hong Kong": "Hong Kong",
    "Korea": "South Korea",
    "NASDAQ": "United States",
    "U.K.": "United Kingdom",
    "U.S.": "United States",
    "US SmallCap": "United States",
    "Saudi Arabia": "Saudi Arabia",
    "South Africa": "South Africa",
}


class GdeltRateLimited(RuntimeError):
    """Raised when the GDELT DOC API keeps returning HTTP 429."""


def _dedupe(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Drop wire-story repeats: same title modulo case/whitespace."""
    seen: set[str] = set()
    out = []
    for a in articles:
        key = " ".join((a.get("title") or "").lower().split())
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(a)
    return out


def fetch_country_news(
    country: str,
    days: int = 1,
    max_records: int = 75,
    extra_query: Optional[str] = None,
    english_only: bool = True,
    retries: int = 3,
) -> dict[str, Any]:
    """Fetch deduped article headlines for one T2 country.

    Returns {"country", "query", "timespan", "n_raw", "n_deduped", "articles":
    [{"seendate", "domain", "title", "url", "language", "sourcecountry"}]}.
    Raises GdeltRateLimited after exhausting retries on HTTP 429.
    """
    if country not in T2_UNIVERSE:
        raise ValueError(f"Unknown T2 country: {country!r}. Must be one of the 34 T2 names.")

    name = SEARCH_NAME.get(country, country)
    query = f'"{name}"' if " " in name else name
    if extra_query:
        query = f"{query} ({extra_query})"
    if english_only:
        query += " sourcelang:english"

    params = {
        "query": query,
        "mode": "artlist",
        "format": "json",
        "maxrecords": min(int(max_records) * 3, 250),  # overfetch; dedup shrinks it
        "timespan": f"{int(days)}d",
        "sort": "hybridrel",
    }

    global _last_request_ts
    last_status = None
    for attempt in range(retries):
        # Self-enforced pacing: GDELT asks for at most one request per 5s.
        elapsed = time.monotonic() - _last_request_ts
        if elapsed < MIN_SECONDS_BETWEEN_REQUESTS:
            time.sleep(MIN_SECONDS_BETWEEN_REQUESTS - elapsed)
        resp = requests.get(DOC_API, params=params, headers={"User-Agent": USER_AGENT}, timeout=30)
        _last_request_ts = time.monotonic()
        last_status = resp.status_code
        if resp.status_code == 200:
            if "limit requests" in resp.text[:200].lower():
                # GDELT's throttle message arrives as 200 + plain text
                if attempt + 1 >= retries:
                    break
                wait = RETRY_WAITS[min(attempt, len(RETRY_WAITS) - 1)]
                print(f"[country_news] throttle message (200), retry {attempt + 1}/{retries} in {wait}s", file=sys.stderr)
                time.sleep(wait)
                continue
            try:
                payload = resp.json()
            except ValueError:
                # GDELT sometimes returns a plain-text error with status 200
                raise RuntimeError(f"GDELT returned non-JSON payload: {resp.text[:200]!r}")
            raw = payload.get("articles", [])
            deduped = _dedupe(raw)[: int(max_records)]
            return {
                "country": country,
                "query": query,
                "timespan_days": days,
                "n_raw": len(raw),
                "n_deduped": len(deduped),
                "articles": [
                    {
                        "seendate": a.get("seendate"),
                        "domain": a.get("domain"),
                        "title": a.get("title"),
                        "url": a.get("url"),
                        "language": a.get("language"),
                        "sourcecountry": a.get("sourcecountry"),
                    }
                    for a in deduped
                ],
            }
        if resp.status_code == 429:
            if attempt + 1 >= retries:
                break
            wait = RETRY_WAITS[min(attempt, len(RETRY_WAITS) - 1)]
            print(f"[country_news] HTTP 429 (rate limited), retry {attempt + 1}/{retries} in {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        resp.raise_for_status()

    raise GdeltRateLimited(
        f"GDELT DOC API rate-limited after {retries} attempts (last status {last_status}). "
        "IMPORTANT: GDELT's per-IP cooldown RESETS on every request - stop calling "
        "this tool entirely for at least 15 minutes before trying again."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Headlines behind a T2 country's news flow (GDELT DOC API).")
    parser.add_argument("country", help="Exact T2 country name, e.g. Indonesia, Korea, 'U.S.'")
    parser.add_argument("--days", type=int, default=1, help="Lookback window in days (default 1).")
    parser.add_argument("--max", type=int, default=50, dest="max_records", help="Max deduped articles (default 50).")
    parser.add_argument("--extra", default=None, dest="extra_query", help="Extra query terms, e.g. 'lira OR cenbank'.")
    parser.add_argument("--all-languages", action="store_true", help="Include non-English sources.")
    args = parser.parse_args()

    result = fetch_country_news(
        args.country,
        days=args.days,
        max_records=args.max_records,
        extra_query=args.extra_query,
        english_only=not args.all_languages,
    )
    print(f"{result['country']} | query: {result['query']} | last {result['timespan_days']}d "
          f"| {result['n_deduped']} unique of {result['n_raw']} raw")
    for a in result["articles"]:
        print(f"  {a['seendate']}  [{a['domain']}]  {a['title']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
