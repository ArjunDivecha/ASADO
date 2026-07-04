"""
=============================================================================
SCRIPT NAME: build_corpus.py (Brier Gate step 1)
=============================================================================

INPUT FILES:
- Polymarket Gamma API (https://gamma-api.polymarket.com/events) — closed
  events in macro tags; live network source
- Polymarket CLOB API (https://clob.polymarket.com/prices-history) — YES-token
  price history (30-day retention); live network source

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/brier_gate/corpus.parquet
  One row per (market, horizon): question, rules, tag, resolve_ts, outcome,
  p_mkt at forecast time, forecast_ts, volume, event grouping key.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/brier_gate/corpus_log.json
  Counts of what was screened out at each filter (no silent drops).

VERSION: 1.0
LAST UPDATED: 2026-07-03
AUTHOR: Claude Code (for Arjun Divecha)

DESCRIPTION:
Builds the retrospective evaluation corpus for the Brier Gate experiment
(docs/PRD_BRIER_GATE.md): resolved binary Polymarket markets in ASADO-relevant
macro tags from the trailing ~30 days (the CLOB history retention window),
with the market probability captured at T-7d, T-3d and T-1d before
resolution and the realized outcome. Markets already effectively resolved at
forecast time (p outside [0.05, 0.95]) are dropped per the PRD — echoing a
0.99 market is not forecasting.

DEPENDENCIES:
- requests, pandas, pyarrow (project venv)

USAGE:
  python scripts/brier_gate/build_corpus.py
  python scripts/brier_gate/build_corpus.py --max-per-event 3 --min-volume 1000

NOTES:
- Tags: economy, geopolitics, fed-rates, inflation, oil, world. Keyword
  blacklist removes sports/crypto/pop-culture leakage inside those tags.
- Anchoring note (accepted, documented in PRD §7): markets that resolved
  early were already drifting at T-k; the [0.05,0.95] screen mitigates.
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent.parent.parent
OUT_DIR = BASE_DIR / "Data" / "work" / "brier_gate"
CORPUS_PATH = OUT_DIR / "corpus.parquet"
LOG_PATH = OUT_DIR / "corpus_log.json"

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"
HEADERS = {"User-Agent": "ASADO-brier-gate/1.0", "Accept": "application/json"}
PAGE_SIZE = 100
MAX_OFFSET = 1000  # per tag; last-30d events are near the top of endDate desc
SLEEP = 0.25

TAGS = ["economy", "geopolitics", "fed-rates", "inflation", "oil", "world"]
HORIZON_DAYS = [7, 3, 1]
BLACKLIST = re.compile(
    r"\b(bitcoin|btc|ethereum|eth\b|solana|crypto|nba|nfl|mlb|nhl|ufc|f1|"
    r"premier league|champions league|grammy|oscar|album|box office|movie|"
    r"tiktok|youtube|spotify|elon tweet|mrbeast)\b",
    re.IGNORECASE,
)
LOOKBACK_DAYS = 29  # stay inside the CLOB retention window
P_MIN, P_MAX = 0.05, 0.95
MAX_PRINT_AGE_H = 48  # last print must be within this many hours of t


def fetch_closed_events(session: requests.Session) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    events: dict[str, dict] = {}
    for tag in TAGS:
        offset = 0
        while offset <= MAX_OFFSET:
            resp = session.get(
                f"{GAMMA_BASE}/events",
                params={
                    "closed": "true",
                    "limit": PAGE_SIZE,
                    "offset": offset,
                    "order": "endDate",
                    "ascending": "false",
                    "tag_slug": tag,
                },
                headers=HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            page = resp.json()
            if not isinstance(page, list) or not page:
                break
            stale = 0
            for e in page:
                end = pd.to_datetime(e.get("endDate"), utc=True, errors="coerce")
                if end is None or pd.isna(end) or end < cutoff:
                    stale += 1
                    continue
                if end > datetime.now(timezone.utc):
                    continue  # closed flag but future endDate — skip oddities
                key = e.get("slug") or e.get("id")
                if key not in events:
                    e["_tag"] = tag
                    events[key] = e
            if stale > PAGE_SIZE // 2:
                break  # deep into pre-window territory
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE
            time.sleep(SLEEP)
        print(f"  tag {tag}: cumulative events {len(events)}")
    return list(events.values())


def extract_markets(events: list[dict], min_volume: float, max_per_event: int, log: dict) -> list[dict]:
    recs: list[dict] = []
    for e in events:
        title = e.get("title") or ""
        if BLACKLIST.search(title):
            log["blacklisted_events"] += 1
            continue
        cands = []
        for m in e.get("markets", []):
            q = m.get("question") or ""
            if BLACKLIST.search(q):
                log["blacklisted_markets"] += 1
                continue
            try:
                outcomes = json.loads(m.get("outcomes") or "[]")
                prices = json.loads(m.get("outcomePrices") or "[]")
                tokens = json.loads(m.get("clobTokenIds") or "[]")
            except (ValueError, TypeError):
                log["malformed"] += 1
                continue
            if len(outcomes) != 2 or len(prices) != 2 or len(tokens) != 2:
                log["not_binary"] += 1
                continue
            if set(prices) - {"0", "1"}:
                log["unresolved_prices"] += 1
                continue
            vol = float(m.get("volumeNum") or 0)
            if vol < min_volume:
                log["below_volume"] += 1
                continue
            resolve_ts = pd.to_datetime(
                m.get("closedTime") or m.get("endDate"), utc=True, errors="coerce"
            )
            if resolve_ts is None or pd.isna(resolve_ts):
                log["no_resolve_ts"] += 1
                continue
            cands.append(
                {
                    "event_slug": e.get("slug"),
                    "event_title": title,
                    "tag": e.get("_tag"),
                    "market_id": m.get("conditionId"),
                    "question": q,
                    "rules_text": (m.get("description") or "")[:2000],
                    "yes_token_id": str(tokens[0]),
                    "outcome": 1.0 if prices[0] == "1" else 0.0,
                    "resolve_ts": resolve_ts,
                    "volume_usd": vol,
                }
            )
        cands.sort(key=lambda r: -r["volume_usd"])
        kept = cands[:max_per_event]
        log["strike_deduped"] += len(cands) - len(kept)
        recs.extend(kept)
    return recs


def attach_market_prices(session: requests.Session, recs: list[dict], log: dict) -> pd.DataFrame:
    rows: list[dict] = []
    for i, rec in enumerate(recs):
        try:
            resp = session.get(
                f"{CLOB_BASE}/prices-history",
                params={"market": rec["yes_token_id"], "interval": "max", "fidelity": 10},
                headers=HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            hist = resp.json().get("history", [])
        except (requests.RequestException, ValueError):
            log["history_fetch_failed"] += 1
            continue
        if not hist:
            log["history_empty"] += 1
            continue
        h = pd.DataFrame(hist).rename(columns={"t": "ts", "p": "p"})
        h["ts"] = pd.to_datetime(h["ts"], unit="s", utc=True)
        h = h.sort_values("ts")
        for k in HORIZON_DAYS:
            t = rec["resolve_ts"] - pd.Timedelta(days=k)
            prior = h[h["ts"] <= t]
            if prior.empty:
                log["no_print_at_horizon"] += 1
                continue
            last = prior.iloc[-1]
            if (t - last["ts"]).total_seconds() > MAX_PRINT_AGE_H * 3600:
                log["stale_print_at_horizon"] += 1
                continue
            p_mkt = float(last["p"])
            if not (P_MIN <= p_mkt <= P_MAX):
                log["effectively_resolved"] += 1
                continue
            rows.append({**rec, "horizon_days": k, "forecast_ts": t, "p_mkt": p_mkt})
        if (i + 1) % 100 == 0:
            print(f"  histories: {i + 1}/{len(recs)}, corpus rows so far: {len(rows)}", flush=True)
        time.sleep(SLEEP)
    return pd.DataFrame(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-volume", type=float, default=1000.0)
    parser.add_argument("--max-per-event", type=int, default=3)
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    log: dict = {
        k: 0
        for k in [
            "blacklisted_events", "blacklisted_markets", "malformed", "not_binary",
            "unresolved_prices", "below_volume", "no_resolve_ts", "strike_deduped",
            "history_fetch_failed", "history_empty", "no_print_at_horizon",
            "stale_print_at_horizon", "effectively_resolved",
        ]
    }

    print("Step 1: enumerating closed macro events...")
    events = fetch_closed_events(session)
    print(f"  {len(events)} unique events in window")

    print("Step 2: extracting resolved binary markets...")
    recs = extract_markets(events, args.min_volume, args.max_per_event, log)
    print(f"  {len(recs)} candidate markets")

    print("Step 3: attaching market prices at horizons...")
    corpus = attach_market_prices(session, recs, log)
    if corpus.empty:
        print("❌ Empty corpus — aborting.")
        return 1

    corpus.to_parquet(CORPUS_PATH, index=False)
    log["final_rows"] = len(corpus)
    log["final_markets"] = int(corpus["market_id"].nunique())
    log["final_events"] = int(corpus["event_slug"].nunique())
    log["outcome_base_rate"] = float(
        corpus.drop_duplicates("market_id")["outcome"].mean()
    )
    log["updated"] = datetime.now().isoformat(timespec="seconds")
    LOG_PATH.write_text(json.dumps(log, indent=2))
    print(json.dumps(log, indent=2))
    print(f"Wrote {len(corpus)} rows -> {CORPUS_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
