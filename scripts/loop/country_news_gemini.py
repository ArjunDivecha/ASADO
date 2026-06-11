#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/country_news_gemini.py
=============================================================================

DESCRIPTION:
Gemini-grounded fallback for country news headlines. The primary source for
evidence packs is the GDELT DOC API (country_news.py), but GDELT throttles
by IP — no API key exists, ~1 request/5s, and a 15-minute penalty box whose
timer resets on every request. When GDELT is rate-limited mid-pull, this
module fetches the same "recent market/economy headlines for country X"
via the Gemini API with Google Search grounding, which is quota'd per API
key (Arjun's key), not per IP.

Explicitly authorized fallback (Arjun, 2026-06-11): "what if we use my
Gemini api key". Packs produced this way are labeled news_source=
"gemini_search" so provenance is never ambiguous.

Returns the SAME dict shape as country_news.fetch_country_news():
  {"country", "query", "timespan", "n_raw", "n_deduped",
   "articles": [{"seendate", "domain", "title", "url", "language",
                 "sourcecountry"}], "source": "gemini_search"}

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/.env.txt
    Read only if GEMINI_API_KEY is not already in the environment
    (first GEMINI_API_KEY= line wins, per house rules).

OUTPUT FILES:
- None (library module; returns data to the caller). When run as a script
  (self-test) it prints the fetched articles for one country to stdout.

VERSION: 1.0
LAST UPDATED: 2026-06-11
AUTHOR: Claude Code for Arjun Divecha

DEPENDENCIES: requests (ASADO venv). Gemini API v1beta REST
(generativelanguage.googleapis.com), model gemini-3.5-flash with the
google_search grounding tool (verified against current docs via Context7
2026-06-11).

USAGE:
  from country_news_gemini import fetch_country_news_gemini
  news = fetch_country_news_gemini("Italy", days=1, max_records=25)

  Self-test:  venv/bin/python scripts/loop/country_news_gemini.py Italy

NOTES:
- FAIL IS FAIL: raises GeminiNewsError on any API/parse failure; the caller
  decides what a missing pack means. No silent empty results: an empty
  article list from a successful call is returned as-is and logged loudly
  by the caller.
- Cost: one grounded generateContent call per country (~7/day worst case);
  negligible.
=============================================================================
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

ENV_TXT = "/Users/arjundivecha/Dropbox/AAA Backup/.env.txt"
GEMINI_MODEL = "gemini-3.5-flash"
GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{GEMINI_MODEL}:generateContent"
)


class GeminiNewsError(RuntimeError):
    """Raised when the Gemini grounded-news fetch fails (API or parse)."""


def _gemini_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if key:
        return key
    try:
        with open(ENV_TXT, "r") as fh:
            for line in fh:
                if line.strip().startswith("GEMINI_API_KEY="):
                    return line.strip().split("=", 1)[1].strip()
    except OSError as exc:
        raise GeminiNewsError(f"GEMINI_API_KEY not in env and {ENV_TXT} unreadable: {exc}")
    raise GeminiNewsError(f"GEMINI_API_KEY not found in env or {ENV_TXT}")


def _extract_json_array(text: str) -> list[dict]:
    """Pull the first JSON array of objects out of model text (fences tolerated)."""
    cleaned = text.strip()
    cleaned = re.sub(r"^```[a-zA-Z0-9_]*\n?", "", cleaned)
    cleaned = re.sub(r"\n?```\s*$", "", cleaned).strip()
    start, end = cleaned.find("["), cleaned.rfind("]") + 1
    if start == -1 or end == 0:
        raise GeminiNewsError(f"No JSON array in Gemini response: {cleaned[:200]!r}")
    parsed = json.loads(cleaned[start:end])
    if not isinstance(parsed, list):
        raise GeminiNewsError("Gemini response JSON is not an array")
    return [item for item in parsed if isinstance(item, dict)]


def fetch_country_news_gemini(
    country: str,
    days: int = 1,
    max_records: int = 25,
    timeout: int = 90,
) -> dict:
    """Fetch recent market/economy headlines for one country via Gemini+Search.

    Same return shape as country_news.fetch_country_news, plus
    "source": "gemini_search".
    """
    prompt = (
        f"Search for the most significant financial-market, economic, and "
        f"political news about {country} from the last {int(days)} day(s) "
        f"that an emerging/developed-markets investor would care about "
        f"(markets, central bank, currency, politics, trade, major corporate). "
        f"Return ONLY a JSON array (no prose) of up to {int(max_records)} "
        f"objects, most important first, each with keys: "
        f'"title" (the headline), "domain" (news source domain like '
        f'"reuters.com"), "summary" (one sentence). Use only information '
        f"found via search, no invention."
    )
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}],
    }
    try:
        resp = requests.post(
            GEMINI_URL,
            headers={"x-goog-api-key": _gemini_api_key(),
                     "Content-Type": "application/json"},
            json=body,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        raise GeminiNewsError(f"Gemini request failed: {exc}") from exc
    if resp.status_code != 200:
        raise GeminiNewsError(
            f"Gemini HTTP {resp.status_code}: {resp.text[:300]}"
        )

    data = resp.json()
    try:
        candidate = data["candidates"][0]
        text = "".join(
            p.get("text", "") for p in candidate["content"]["parts"]
        )
    except (KeyError, IndexError, TypeError) as exc:
        raise GeminiNewsError(f"Unexpected Gemini response shape: {exc}") from exc

    raw_articles = _extract_json_array(text)

    # Grounding chunks give us real source URIs (redirect links) keyed by
    # domain-ish titles; map them onto articles by domain where possible.
    chunk_by_domain: dict[str, str] = {}
    meta = candidate.get("groundingMetadata") or {}
    for chunk in meta.get("groundingChunks", []):
        web = chunk.get("web") or {}
        title, uri = web.get("title", ""), web.get("uri", "")
        if title and uri:
            chunk_by_domain.setdefault(title.lower().strip(), uri)

    now_tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    articles = []
    for raw in raw_articles[: int(max_records)]:
        title = str(raw.get("title", "")).strip()
        if not title:
            continue
        domain = str(raw.get("domain", "")).strip().lower()
        domain = urlparse(domain).netloc or domain  # tolerate full URLs
        articles.append({
            "seendate": now_tag,
            "domain": domain,
            "title": title,
            "url": chunk_by_domain.get(domain, ""),
            "language": "English",
            "sourcecountry": "",
        })

    return {
        "country": country,
        "query": f"gemini_search:{country}",
        "timespan_days": int(days),
        "n_raw": len(raw_articles),
        "n_deduped": len(articles),
        "articles": articles,
        "source": "gemini_search",
    }


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "Italy"
    news = fetch_country_news_gemini(target)
    print(f"{news['country']}: {news['n_deduped']} articles (source={news['source']})")
    for a in news["articles"][:10]:
        print(f"  [{a['domain']}] {a['title']}")
