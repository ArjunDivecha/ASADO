"""
=============================================================================
SCRIPT NAME: backtest_overnight_pull.py
=============================================================================

INPUT FILES:
- Polymarket Gamma API (https://gamma-api.polymarket.com/events, tag_slug=
  stocks, closed=true) — live network source
- Polymarket CLOB API (https://clob.polymarket.com/prices-history) — live
  network source
- No local input files

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/predmkt_equity/markets.parquet
  One row per parsed directional closed market (ticker, class, direction,
  target, tokens, resolve date, volume).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/predmkt_equity/history/{conditionId}.parquet
  Lifetime YES-token price history (10-minute fidelity) for one market:
  columns ts (UTC), p_yes.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/predmkt_equity/pull_log.json
  Incremental progress log (counts, failures) updated as the pull proceeds.

VERSION: 1.0
LAST UPDATED: 2026-07-03
AUTHOR: Claude Code (for Arjun Divecha)

DESCRIPTION:
Milestone M5a of the Tier 1 overnight prediction-market -> equity signal:
the historical data pull for the backtest gate. Enumerates all CLOSED
Polymarket stock-tag events (offset pagination, ~2,100 events back to
April 2026), parses each market into a directional record via
predmkt_equity_common, and pulls the full lifetime price history of each
market's YES token from the CLOB /prices-history endpoint at 10-minute
fidelity. Everything is cached incrementally per market: re-running skips
markets whose history parquet already exists, so the pull is resumable.

Markets with lifetime volume below MIN_VOLUME_USD are recorded in
markets.parquet but their history is NOT pulled (logged, not silent) —
dead strikes have no window prints and would waste ~half the requests.

DEPENDENCIES:
- requests, pandas, pyarrow (project venv)

USAGE:
  python scripts/backtest_overnight_pull.py               [full pull, resumable]
  python scripts/backtest_overnight_pull.py --limit 50    [first N histories, for testing]
  python scripts/backtest_overnight_pull.py --min-volume 500  [override volume floor]
  python scripts/backtest_overnight_pull.py --refresh-active  [also re-pull ACTIVE universe
      markets from config/predmkt_equity_universe.yaml and MERGE with cached history —
      needed because Polymarket purges /prices-history older than ~30 days, so a
      long-lived active contract loses its early prints unless harvested repeatedly]

NOTES:
- Rate limited to ~4 requests/sec against the CLOB endpoint.
- ~5,000-9,000 histories at 10-min fidelity: expect a 20-45 minute run.
- Bucket markets are excluded by the parser (not directional).
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

from predmkt_equity_common import parse_stock_market  # noqa: E402

WORK_DIR = BASE_DIR / "Data" / "work" / "predmkt_equity"
HISTORY_DIR = WORK_DIR / "history"
MARKETS_PATH = WORK_DIR / "markets.parquet"
LOG_PATH = WORK_DIR / "pull_log.json"

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"
HEADERS = {"User-Agent": "ASADO-predmkt/1.0", "Accept": "application/json"}
PAGE_SIZE = 100
MAX_OFFSET = 2000
DEFAULT_MIN_VOLUME = 100.0
SLEEP_BETWEEN = 0.25  # ~4 req/s

for d in [WORK_DIR, HISTORY_DIR]:
    d.mkdir(parents=True, exist_ok=True)


def _write_log(payload: dict) -> None:
    payload["updated"] = datetime.now().isoformat(timespec="seconds")
    tmp = LOG_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.rename(LOG_PATH)


def enumerate_closed_markets(session: requests.Session) -> pd.DataFrame:
    """Fetch all closed stock events and parse directional markets."""
    records: list[dict] = []
    skipped = 0
    seen: set[str] = set()
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
                "tag_slug": "stocks",
            },
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json()
        if not isinstance(page, list) or not page:
            break
        for event in page:
            for market in event.get("markets", []):
                rec = parse_stock_market(market, event)
                if rec is None:
                    skipped += 1
                    continue
                if rec["market_id"] in seen:
                    continue
                seen.add(rec["market_id"])
                records.append(rec)
        print(f"  offset {offset}: {len(records)} directional so far", flush=True)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(SLEEP_BETWEEN)
    df = pd.DataFrame(records)
    print(f"Enumerated {len(df)} directional closed markets ({skipped} bucket markets excluded)")
    return df


def pull_history(session: requests.Session, token_id: str) -> pd.DataFrame | None:
    """Pull full lifetime 10-min price history for one token."""
    try:
        resp = session.get(
            f"{CLOB_BASE}/prices-history",
            params={"market": token_id, "interval": "max", "fidelity": 10},
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        hist = resp.json().get("history", [])
    except (requests.RequestException, ValueError) as exc:
        print(f"  ❌ history fetch failed for token {token_id[:16]}...: {exc}")
        return None
    if not hist:
        return pd.DataFrame(columns=["ts", "p_yes"])
    df = pd.DataFrame(hist).rename(columns={"t": "ts", "p": "p_yes"})
    df["ts"] = pd.to_datetime(df["ts"], unit="s", utc=True)
    return df[["ts", "p_yes"]]


def refresh_active_histories(session: requests.Session) -> tuple[int, int]:
    """Re-pull every active universe market's history and merge with cache.

    Polymarket purges /prices-history beyond ~30 days, so long-lived active
    contracts must be re-harvested while alive; merging on ts preserves the
    prints that have already fallen out of the API's retention window.
    """
    import yaml

    universe_path = BASE_DIR / "config" / "predmkt_equity_universe.yaml"
    if not universe_path.exists():
        print(f"⚠️  --refresh-active: {universe_path} missing, skipping.")
        return 0, 0
    with open(universe_path) as fh:
        universe = yaml.safe_load(fh) or []
    active = [r for r in universe if r.get("is_active")]
    merged = failed = 0
    for rec in active:
        hist = pull_history(session, rec["yes_token_id"])
        if hist is None:
            failed += 1
            continue
        out_path = HISTORY_DIR / f"{rec['market_id']}.parquet"
        if out_path.exists():
            old = pd.read_parquet(out_path)
            hist = (
                pd.concat([old, hist], ignore_index=True)
                .drop_duplicates(subset="ts")
                .sort_values("ts")
                .reset_index(drop=True)
            )
        hist.to_parquet(out_path, index=False)
        merged += 1
        time.sleep(SLEEP_BETWEEN)
    print(f"refresh-active: merged {merged} active histories, {failed} failed")
    return merged, failed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None, help="max histories to pull (testing)")
    parser.add_argument("--min-volume", type=float, default=DEFAULT_MIN_VOLUME)
    parser.add_argument(
        "--refresh-active",
        action="store_true",
        help="also merge-refresh histories for active universe markets",
    )
    args = parser.parse_args()

    session = requests.Session()

    print("Step 1: enumerating closed stock events...")
    markets = enumerate_closed_markets(session)
    if markets.empty:
        print("❌ No markets enumerated — Gamma API problem. Aborting.")
        return 1
    markets.to_parquet(MARKETS_PATH, index=False)
    print(f"Wrote {MARKETS_PATH} ({len(markets)} rows)")

    eligible = markets[(markets["volume_usd"].fillna(0) >= args.min_volume)].copy()
    below_floor = len(markets) - len(eligible)
    print(
        f"Step 2: pulling histories for {len(eligible)} markets with volume >= "
        f"${args.min_volume:.0f} ({below_floor} below floor, recorded but not pulled)"
    )

    done = fail = skip = 0
    todo = eligible.itertuples()
    for i, row in enumerate(todo):
        if args.limit is not None and done + skip >= args.limit:
            break
        out_path = HISTORY_DIR / f"{row.market_id}.parquet"
        if out_path.exists():
            skip += 1
            continue
        hist = pull_history(session, row.yes_token_id)
        if hist is None:
            fail += 1
        else:
            hist.to_parquet(out_path, index=False)
            done += 1
        if (done + fail) % 100 == 0:
            _write_log(
                {
                    "total_markets": len(markets),
                    "eligible": len(eligible),
                    "below_volume_floor": below_floor,
                    "pulled": done,
                    "skipped_existing": skip,
                    "failed": fail,
                }
            )
            print(f"  progress: {done} pulled, {skip} cached, {fail} failed", flush=True)
        time.sleep(SLEEP_BETWEEN)

    _write_log(
        {
            "total_markets": len(markets),
            "eligible": len(eligible),
            "below_volume_floor": below_floor,
            "pulled": done,
            "skipped_existing": skip,
            "failed": fail,
            "complete": args.limit is None,
        }
    )
    print(f"DONE: {done} pulled, {skip} already cached, {fail} failed")

    if args.refresh_active:
        merged, refresh_fail = refresh_active_histories(session)
        if merged == 0 and refresh_fail > 0:
            return 1

    return 0 if fail == 0 else (0 if done > 0 else 1)


if __name__ == "__main__":
    sys.exit(main())
