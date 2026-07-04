"""
=============================================================================
SCRIPT NAME: live_shadow.py (Brier Gate — live shadow mode)
=============================================================================

INPUT FILES:
- Polymarket Gamma API (https://gamma-api.polymarket.com/events, active
  macro-tag events; and market lookups by condition_ids for scoring)
- /Users/arjundivecha/Dropbox/AAA Backup/.env.txt (ANTHROPIC_API_KEY)
- ASADO DuckDBs read-only via context_packs.py:
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
  Table `brier_gate_live` (created if absent): one row per (forecast_date,
  market_id) — the pre-registered forecast — later updated in place with the
  resolution and Brier scores when the market resolves.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/brier_gate/live_shadow_log.jsonl
  Append-only audit log of every forecast call (prompt hash, samples, raw).

VERSION: 1.0
LAST UPDATED: 2026-07-04
AUTHOR: Claude Code (for Arjun Divecha)

DESCRIPTION:
Live shadow mode for the Brier Gate (docs/PRD_BRIER_GATE.md §6 "Ambiguous"
path, triggered by the 2026-07-04 result: Fable-5-xhigh A2 beat the market
on the retrospective corpus with n too small to trust). Each run:

  1. SCORES any previously-forecast markets that have since resolved
     (Gamma lookup by conditionId) — fills resolution_value, brier_ai,
     brier_mkt in `brier_gate_live`.
  2. ENUMERATES active macro-tag Polymarket markets (economy, geopolitics,
     fed-rates, inflation, oil, world), filters to genuinely-uncertain
     (0.05 <= p_mkt <= 0.95), liquid (volume >= $1,000), non-blacklisted
     binaries; dedups to <= 3 strikes/event; ranks by 24h volume.
  3. FORECASTS up to --max-markets (default 40) with DeepSeek V4 Pro via
     the NATIVE API (api.deepseek.com) at reasoning_effort="max", arm A2
     (PIT warehouse context pack + current market price), k=5 samples,
     median. A market is re-forecast only if last forecast is > 2 days old
     OR it resolves within 3 days. (v1.0 used Fable-5 xhigh — day-1 rows in
     brier_gate_live carry model/effort columns, so the history is mixed by
     design; DeepSeek-xhigh validated retrospectively 2026-07-04.)
  4. DUAL-LOGS Kalshi (api.elections.kalshi.com, public, unauthenticated):
     each forecast's question is token-matched against all open Kalshi
     markets in Politics/World/Economics/Financials; the best match's
     ticker, title, yes bid/ask and match score are stored alongside the
     forecast — so the go/no-go decision can be scored against a price
     executable on a US-regulated venue, not just Polymarket's mid.
  5. Prints a running scoreboard: cumulative Brier AI vs market on resolved
     rows, plus the hypothetical threshold-rule PnL (theta=0.05, 5c cost).

NO ORDERS ARE EVER PLACED. This is validation infrastructure; the FDT repo
schedules it (com.arjundivecha.fdt-predmkt-shadow) but it touches nothing
in the execution path.

DEPENDENCIES:
- anthropic, duckdb, pandas, requests (ASADO project venv)

USAGE:
  python scripts/brier_gate/live_shadow.py                 [daily run]
  python scripts/brier_gate/live_shadow.py --max-markets 10 --samples 1  [cheap test]
  python scripts/brier_gate/live_shadow.py --score-only    [no new forecasts]

NOTES:
- Fable 5 API: thinking={"type":"adaptive"} + output_config={"effort":"xhigh"}
  (rejects thinking.enabled/disabled — learned 2026-07-03).
- Cost at defaults: ~40 markets x 3 samples ~= $15-40/day.
- Loop-DB writes retry on lock (nightly jobs may hold it briefly).
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

import duckdb
import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts" / "brier_gate"))
from context_packs import ContextPackBuilder  # noqa: E402

LOOP_DB = BASE_DIR / "Data" / "loop" / "asado_loop.duckdb"
AUDIT_LOG = BASE_DIR / "Data" / "work" / "brier_gate" / "live_shadow_log.jsonl"
ENV_PATH = Path("/Users/arjundivecha/Dropbox/AAA Backup/.env.txt")

GAMMA_BASE = "https://gamma-api.polymarket.com"
HEADERS = {"User-Agent": "ASADO-brier-shadow/1.0", "Accept": "application/json"}
TAGS = ["economy", "geopolitics", "fed-rates", "inflation", "oil", "world"]
BLACKLIST = re.compile(
    r"\b(bitcoin|btc|ethereum|eth\b|solana|crypto|nba|nfl|mlb|nhl|ufc|f1|"
    r"premier league|champions league|grammy|oscar|album|box office|movie|"
    r"tiktok|youtube|spotify|elon tweet|mrbeast)\b",
    re.IGNORECASE,
)
# Forecaster: DeepSeek V4 Pro via the NATIVE API (api.deepseek.com, OpenAI-
# compatible) at reasoning_effort="max" (native supports low/medium/high/
# xhigh/max; validated retrospectively at xhigh: A2 beats market, Brier
# 0.186 vs 0.202). ~10-30x cheaper than Fable (<$2/day at 40x5 calls).
# The Kalshi matcher still uses a cheap Anthropic Sonnet call.
MODEL_ID = "deepseek-v4-pro"
EFFORT = "max"
DEEPSEEK_BASE = "https://api.deepseek.com"
P_MIN, P_MAX = 0.05, 0.95
MIN_VOLUME = 1000.0
MAX_PER_EVENT = 3
REFORECAST_DAYS = 2
NEAR_RESOLUTION_DAYS = 3

KALSHI_BASE = "https://api.elections.kalshi.com/trade-api/v2"
KALSHI_CATEGORIES = {"Politics", "World", "Economics", "Financials"}
KALSHI_MATCH_MIN_SCORE = 0.45
KALSHI_MATCH_MIN_TOKENS = 3
_STOPWORDS = {
    "will", "the", "a", "an", "be", "by", "in", "on", "of", "to", "before",
    "after", "any", "or", "and", "for", "at", "is", "next", "this", "with",
    "does", "do", "how", "who", "what", "which", "than", "above", "below",
    "yes", "no", "2026", "2027",
}

DDL = """
CREATE TABLE IF NOT EXISTS brier_gate_live (
    forecast_date DATE,
    forecast_ts TIMESTAMP,
    market_id VARCHAR,
    event_slug VARCHAR,
    question VARCHAR,
    tag VARCHAR,
    resolve_by TIMESTAMP,
    days_to_resolution DOUBLE,
    p_mkt DOUBLE,
    p_ai DOUBLE,
    n_samples INTEGER,
    pack_sha VARCHAR,
    model VARCHAR,
    effort VARCHAR,
    resolution_value DOUBLE,
    resolved_ts TIMESTAMP,
    brier_ai DOUBLE,
    brier_mkt DOUBLE,
    scored_ts TIMESTAMP,
    kalshi_ticker VARCHAR,
    kalshi_title VARCHAR,
    kalshi_yes_bid DOUBLE,
    kalshi_yes_ask DOUBLE,
    kalshi_match_score DOUBLE,
    PRIMARY KEY (forecast_date, market_id)
)
"""

KALSHI_COLS_DDL = [
    "ALTER TABLE brier_gate_live ADD COLUMN IF NOT EXISTS kalshi_ticker VARCHAR",
    "ALTER TABLE brier_gate_live ADD COLUMN IF NOT EXISTS kalshi_title VARCHAR",
    "ALTER TABLE brier_gate_live ADD COLUMN IF NOT EXISTS kalshi_yes_bid DOUBLE",
    "ALTER TABLE brier_gate_live ADD COLUMN IF NOT EXISTS kalshi_yes_ask DOUBLE",
    "ALTER TABLE brier_gate_live ADD COLUMN IF NOT EXISTS kalshi_match_score DOUBLE",
]


def _tokens(text: str) -> set[str]:
    text = (text or "").lower().replace("u.s.", "us").replace("u.k.", "uk")
    words = re.findall(r"[a-z0-9\$%]+", text)
    return {w for w in words if w not in _STOPWORDS and len(w) > 1}


def fetch_kalshi_universe(session: requests.Session) -> list[dict]:
    """All open Kalshi markets in macro categories, with nested market quotes."""
    out: list[dict] = []
    cursor = None
    pages = 0
    while pages < 30:
        params = {"status": "open", "limit": 200, "with_nested_markets": "true"}
        if cursor:
            params["cursor"] = cursor
        try:
            resp = session.get(f"{KALSHI_BASE}/events", params=params, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError) as exc:
            print(f"  ⚠️ Kalshi events fetch failed: {exc}")
            break
        for e in data.get("events", []):
            if e.get("category") not in KALSHI_CATEGORIES:
                continue
            etitle = e.get("title") or ""
            for m in e.get("markets") or []:
                title = f"{etitle} {m.get('yes_sub_title') or m.get('subtitle') or ''}".strip()
                out.append({
                    "ticker": m.get("ticker"),
                    "title": title,
                    "tokens": _tokens(title),
                    "yes_bid": (m.get("yes_bid") / 100.0) if m.get("yes_bid") is not None else None,
                    "yes_ask": (m.get("yes_ask") / 100.0) if m.get("yes_ask") is not None else None,
                })
        cursor = data.get("cursor")
        pages += 1
        if not cursor:
            break
        time.sleep(0.25)
    print(f"  Kalshi universe: {len(out)} macro-category markets")
    return out


def match_kalshi(
    question: str,
    universe: list[dict],
    llm_client=None,
    session: requests.Session | None = None,
) -> dict | None:
    """Two-stage match: token-overlap shortlist, then LLM adjudication.

    Stage 1 shortlists the top-8 Kalshi markets by token Jaccard (>= 2 shared
    content tokens). Stage 2 asks a cheap Sonnet call whether any shortlist
    entry asks the SAME question (same event, same direction, comparable
    deadline) — phrasing differs too much across venues for tokens alone.
    A confirmed match gets a live quote fetched for its ticker.
    """
    q_tokens = _tokens(question)
    if not q_tokens:
        return None
    scored = []
    for k in universe:
        if not k["tokens"]:
            continue
        shared = len(q_tokens & k["tokens"])
        if shared < 2:
            continue
        scored.append((shared / len(q_tokens | k["tokens"]), shared, k))
    scored.sort(key=lambda x: -x[0])
    shortlist = [k for _, _, k in scored[:8]]
    if not shortlist:
        return None
    # High-confidence token match needs no LLM
    if scored[0][0] >= 0.60 and scored[0][1] >= KALSHI_MATCH_MIN_TOKENS:
        chosen, score = shortlist[0], scored[0][0]
    elif llm_client is not None:
        listing = "\n".join(f"{i}. {k['title'][:120]}" for i, k in enumerate(shortlist))
        try:
            resp = llm_client.messages.create(
                model="claude-sonnet-5",
                max_tokens=50,
                temperature=0,
                system=(
                    "You match prediction-market questions across venues. Answer with ONLY "
                    'a JSON object {"match": <index or null>}. A match must ask about the '
                    "SAME underlying event with the same YES direction and a comparable "
                    "deadline. If none qualify, use null."
                ),
                messages=[{
                    "role": "user",
                    "content": f"QUESTION: {question}\n\nCANDIDATES:\n{listing}\n\nWhich candidate (if any) is the same question?",
                }],
                thinking={"type": "disabled"},
            )
            text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
            idx = json.loads(re.search(r"\{.*\}", text, re.DOTALL).group(0)).get("match")
            if idx is None or not (0 <= int(idx) < len(shortlist)):
                return None
            chosen, score = shortlist[int(idx)], scored[int(idx)][0] if int(idx) < len(scored) else 0.0
        except Exception:
            return None
    else:
        return None
    # Live quote for the chosen ticker (nested-market quotes are often stale/absent)
    if session is not None:
        try:
            resp = session.get(
                f"{KALSHI_BASE}/markets/{chosen['ticker']}", headers=HEADERS, timeout=15
            )
            resp.raise_for_status()
            m = resp.json().get("market", {})
            chosen = {**chosen,
                      "yes_bid": (m.get("yes_bid") / 100.0) if m.get("yes_bid") is not None else None,
                      "yes_ask": (m.get("yes_ask") / 100.0) if m.get("yes_ask") is not None else None}
        except (requests.RequestException, ValueError):
            pass
    return {**chosen, "score": score}


def _loop_con(retries: int = 5) -> duckdb.DuckDBPyConnection:
    for attempt in range(retries):
        try:
            return duckdb.connect(str(LOOP_DB))
        except duckdb.IOException:
            if attempt == retries - 1:
                raise
            time.sleep(10 * (attempt + 1))
    raise RuntimeError("unreachable")


def _env_key(name: str) -> str:
    for line in ENV_PATH.read_text().splitlines():
        m = re.match(rf"^{name}=(.+)$", line.strip())
        if m:
            return m.group(1).strip()
    raise RuntimeError(f"{name} not found in .env.txt")


def _parse_probability(text: str):
    try:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            p = float(json.loads(m.group(0)).get("probability"))
            if 0.0 <= p <= 1.0:
                return p
    except (ValueError, TypeError, json.JSONDecodeError):
        pass
    m = re.search(r"(?:0?\.\d+|[01](?:\.0+)?)", text)
    if m and 0.0 <= float(m.group(0)) <= 1.0:
        return float(m.group(0))
    return None


def score_resolved(con: duckdb.DuckDBPyConnection, session: requests.Session) -> int:
    open_rows = con.execute(
        "SELECT DISTINCT market_id FROM brier_gate_live WHERE resolution_value IS NULL"
    ).fetchall()
    ids = [r[0] for r in open_rows]
    scored = 0
    for i in range(0, len(ids), 20):
        chunk = ids[i : i + 20]
        try:
            resp = session.get(
                f"{GAMMA_BASE}/markets",
                params={"condition_ids": ",".join(chunk), "limit": len(chunk)},
                headers=HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            markets = resp.json()
        except (requests.RequestException, ValueError) as exc:
            print(f"  ⚠️ score lookup failed for chunk: {exc}")
            continue
        for m in markets:
            if not m.get("closed"):
                continue
            try:
                prices = json.loads(m.get("outcomePrices") or "[]")
            except (ValueError, TypeError):
                continue
            if len(prices) != 2 or set(prices) - {"0", "1"}:
                continue
            y = 1.0 if prices[0] == "1" else 0.0
            rts = pd.to_datetime(m.get("closedTime") or m.get("endDate"), utc=True, errors="coerce")
            con.execute(
                """UPDATE brier_gate_live SET
                     resolution_value = ?, resolved_ts = ?,
                     brier_ai = (p_ai - ?) * (p_ai - ?),
                     brier_mkt = (p_mkt - ?) * (p_mkt - ?),
                     scored_ts = now()
                   WHERE market_id = ? AND resolution_value IS NULL""",
                [y, rts.to_pydatetime() if rts is not None and not pd.isna(rts) else None,
                 y, y, y, y, m.get("conditionId")],
            )
            scored += 1
        time.sleep(0.3)
    return scored


def enumerate_targets(session: requests.Session) -> pd.DataFrame:
    now = datetime.now(timezone.utc)
    events: dict[str, dict] = {}
    for tag in TAGS:
        try:
            resp = session.get(
                f"{GAMMA_BASE}/events",
                params={"active": "true", "closed": "false", "limit": 100,
                        "order": "volume24hr", "ascending": "false", "tag_slug": tag},
                headers=HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            for e in resp.json():
                key = e.get("slug") or e.get("id")
                if key not in events:
                    e["_tag"] = tag
                    events[key] = e
        except (requests.RequestException, ValueError) as exc:
            print(f"  ⚠️ tag {tag} enumeration failed: {exc}")
        time.sleep(0.3)

    recs = []
    for e in events.values():
        title = e.get("title") or ""
        if BLACKLIST.search(title):
            continue
        cands = []
        for m in e.get("markets", []):
            q = m.get("question") or ""
            if BLACKLIST.search(q):
                continue
            try:
                outcomes = json.loads(m.get("outcomes") or "[]")
                prices = json.loads(m.get("outcomePrices") or "[]")
            except (ValueError, TypeError):
                continue
            if len(outcomes) != 2 or len(prices) != 2:
                continue
            try:
                p_mkt = float(prices[0])
            except (ValueError, TypeError):
                continue
            vol = float(m.get("volumeNum") or 0)
            vol24 = float(m.get("volume24hr") or 0)
            end = pd.to_datetime(m.get("endDate"), utc=True, errors="coerce")
            if pd.isna(end) or end <= now:
                continue
            if vol < MIN_VOLUME or not (P_MIN <= p_mkt <= P_MAX):
                continue
            cands.append({
                "event_slug": e.get("slug"), "event_title": title, "tag": e["_tag"],
                "market_id": m.get("conditionId"), "question": q,
                "rules_text": (m.get("description") or "")[:2000],
                "p_mkt": p_mkt, "volume_usd": vol, "volume_24h": vol24,
                "resolve_by": end,
                "days_to_resolution": (end - now).total_seconds() / 86400,
            })
        cands.sort(key=lambda r: -r["volume_usd"])
        recs.extend(cands[:MAX_PER_EVENT])
    df = pd.DataFrame(recs)
    if not df.empty:
        df = df.sort_values("volume_24h", ascending=False).reset_index(drop=True)
    return df


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-markets", type=int, default=40)
    parser.add_argument("--samples", type=int, default=5)
    parser.add_argument("--score-only", action="store_true")
    args = parser.parse_args()

    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    con = _loop_con()
    con.execute(DDL)
    for ddl in KALSHI_COLS_DDL:
        con.execute(ddl)

    print("Step 1: scoring resolved markets...")
    n_scored = score_resolved(con, session)
    print(f"  scored {n_scored} newly-resolved forecasts")

    if not args.score_only:
        print("Step 2: enumerating active targets...")
        targets = enumerate_targets(session)
        print(f"  {len(targets)} candidate markets")
        if not targets.empty:
            recent = con.execute(
                """SELECT market_id, MAX(forecast_date) last_fc
                   FROM brier_gate_live GROUP BY market_id"""
            ).df()
            # release the write handle: ContextPackBuilder opens this same DB
            # read-only, and DuckDB refuses mixed-config connections to one file
            con.close()
            last_fc = dict(zip(recent["market_id"], pd.to_datetime(recent["last_fc"])))
            today = pd.Timestamp(datetime.now(timezone.utc).date())

            def needs_forecast(row) -> bool:
                lf = last_fc.get(row.market_id)
                if lf is None:
                    return True
                age = (today - lf).days
                return age >= REFORECAST_DAYS or (
                    row.days_to_resolution <= NEAR_RESOLUTION_DAYS and age >= 1
                )

            todo = [r for r in targets.itertuples() if needs_forecast(r)][: args.max_markets]
            print(f"  forecasting {len(todo)} markets (max {args.max_markets})")

            print("Step 2b: Kalshi dual-log — fetching macro universe...")
            kalshi_universe = fetch_kalshi_universe(session)
            n_matched = 0

            import anthropic
            from openai import OpenAI

            ds_client = OpenAI(base_url=DEEPSEEK_BASE, api_key=_env_key("DEEPSEEK_API_KEY"))
            match_client = anthropic.Anthropic(api_key=_env_key("ANTHROPIC_API_KEY"))
            cpb = ContextPackBuilder()
            now = datetime.now(timezone.utc)
            fdate = now.date()
            n_ok = n_fail = 0
            pending_inserts: list[list] = []

            # Phase A (serial, local): context packs — DuckDB connections in
            # ContextPackBuilder are not thread-safe, and packs are fast.
            jobs = []
            for row in todo:
                try:
                    pack_text, sha = cpb.build(row.question, row.event_title, row.tag, pd.Timestamp(now))
                except Exception as exc:
                    print(f"  ❌ pack: {row.market_id[:12]}: {exc}")
                    n_fail += 1
                    continue
                system = (
                    "You are a careful probabilistic forecaster evaluating a prediction-market "
                    f"question. Today's date is {fdate}. Use your general knowledge plus the "
                    "data provided. Respond with ONLY a JSON object: "
                    '{"probability": <float 0-1 that the market resolves YES>, '
                    '"rationale": "<one sentence>"}'
                )
                user = (
                    f"QUESTION: {row.question}\n"
                    f"RESOLUTION RULES: {row.rules_text or '(none)'}\n"
                    f"RESOLUTION DEADLINE: {row.resolve_by:%Y-%m-%d}\n\n"
                    f"DATA:\n{pack_text}\n"
                    f"CURRENT MARKET PRICE (probability of YES): {row.p_mkt:.3f}\n\n"
                    "Your probability that this resolves YES?"
                )
                jobs.append({"row": row, "sha": sha, "system": system, "user": user})
            cpb.close()

            # Phase B (parallel): every (market, sample) forecast call at once.
            from concurrent.futures import ThreadPoolExecutor

            def one_sample(job):
                try:
                    resp = ds_client.chat.completions.create(
                        model=MODEL_ID,
                        temperature=1.0,
                        messages=[
                            {"role": "system", "content": job["system"]},
                            {"role": "user", "content": job["user"]},
                        ],
                        max_tokens=16000,
                        extra_body={"reasoning_effort": EFFORT},
                    )
                    return _parse_probability(resp.choices[0].message.content or "")
                except Exception as exc:
                    print(f"  ⚠️ api: {job['row'].market_id[:12]}: {str(exc)[:80]}")
                    return None

            with ThreadPoolExecutor(max_workers=12) as pool:
                futures = {
                    job["row"].market_id: [
                        pool.submit(one_sample, job) for _ in range(args.samples)
                    ]
                    for job in jobs
                }
                results = {
                    mid: [f.result() for f in fs] for mid, fs in futures.items()
                }

            # Phase C (parallel-ish): Kalshi matching per market, then persist.
            for job in jobs:
                row, sha = job["row"], job["sha"]
                samples = [p for p in results.get(row.market_id, []) if p is not None]
                if not samples:
                    n_fail += 1
                    continue
                p_ai = float(pd.Series(samples).median())
                km = match_kalshi(row.question, kalshi_universe, llm_client=match_client, session=session)
                if km is not None:
                    n_matched += 1
                pending_inserts.append(
                    [fdate, now, row.market_id, row.event_slug, row.question, row.tag,
                     row.resolve_by.to_pydatetime(), float(row.days_to_resolution),
                     float(row.p_mkt), p_ai, len(samples), sha, MODEL_ID, EFFORT,
                     km["ticker"] if km else None, km["title"][:300] if km else None,
                     km["yes_bid"] if km else None, km["yes_ask"] if km else None,
                     km["score"] if km else None]
                )
                with open(AUDIT_LOG, "a") as fh:
                    fh.write(json.dumps({
                        "ts": str(now), "market_id": row.market_id, "question": row.question,
                        "p_mkt": row.p_mkt, "p_ai": p_ai, "samples": samples, "pack_sha": sha,
                        "kalshi": {k: km[k] for k in ("ticker", "title", "yes_bid", "yes_ask", "score")} if km else None,
                    }) + "\n")
                n_ok += 1
                print(f"  ✓ {row.question[:60]}... mkt={row.p_mkt:.2f} ai={p_ai:.2f}")
            con = _loop_con()
            for vals in pending_inserts:
                con.execute(
                    """INSERT OR REPLACE INTO brier_gate_live
                       (forecast_date, forecast_ts, market_id, event_slug, question, tag,
                        resolve_by, days_to_resolution, p_mkt, p_ai, n_samples, pack_sha,
                        model, effort, resolution_value, resolved_ts, brier_ai, brier_mkt, scored_ts,
                        kalshi_ticker, kalshi_title, kalshi_yes_bid, kalshi_yes_ask, kalshi_match_score)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL,
                               ?, ?, ?, ?, ?)""",
                    vals,
                )
            print(f"  forecasts written: {n_ok} ok, {n_fail} failed "
                  f"({n_matched}/{n_ok} matched to a Kalshi contract)")
        else:
            pass
    if con is None or not hasattr(con, "execute"):
        con = _loop_con()
    try:
        con.execute("SELECT 1")
    except Exception:
        con = _loop_con()

    print("\n=== SHADOW SCOREBOARD ===")
    board = con.execute(
        """SELECT COUNT(*) n_forecasts,
                  COUNT(resolution_value) n_resolved,
                  AVG(brier_ai) brier_ai, AVG(brier_mkt) brier_mkt,
                  SUM(CASE WHEN resolution_value IS NOT NULL AND ABS(p_ai - p_mkt) > 0.05
                      THEN CASE WHEN p_ai > p_mkt THEN resolution_value - (p_mkt + 0.05)
                           ELSE (1 - resolution_value) - ((1 - p_mkt) + 0.05) END END) pnl_theta05_c05,
                  SUM(CASE WHEN resolution_value IS NOT NULL AND ABS(p_ai - p_mkt) > 0.05
                      THEN 1 ELSE 0 END) n_trades
           FROM brier_gate_live"""
    ).df()
    print(board.to_string(index=False))
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
