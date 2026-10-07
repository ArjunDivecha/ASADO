"""
=============================================================================
SCRIPT NAME: poll_predmkt_intraday.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/predmkt_equity_universe.yaml
  Curated firm-level equity market universe (from discover_predmkt_equity_universe.py).
- Polymarket CLOB API (https://clob.polymarket.com/book) — live network source.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/predmkt_equity/intraday/poll_{YYYYMMDD_HHMMSS}.parquet
  One parquet per poll cycle (append-safe, no read-modify-write): one row per
  polled market with UTC timestamp, window tag, stock-up-aligned mid price,
  bid/ask, spread, book-depth liquidity proxy, and staleness flag.
  Schema: poll_ts, poll_date, window, platform, market_id, ticker,
  contract_class, p_yes_aligned, bid, ask, spread_bps, liquidity_usd,
  is_stale, yes_rises_with_stock.

VERSION: 1.0
LAST UPDATED: 2026-07-03
AUTHOR: Claude Code (for Arjun Divecha)

DESCRIPTION:
Milestone M2 of the Tier 1 overnight prediction-market -> equity signal:
the lightweight intraday poller. Designed to run every 10 minutes from
launchd (com.arjundivecha.asado-predmkt-equity-poller); it self-gates and
exits silently unless the current UTC time is inside one of the two PRD
windows on a weekday:
  close window: 19:30-23:30 UTC (defines the prior-day PM price)
  open window:  12:30-15:30 UTC (defines the next-morning PM price)
By default it polls only the daily contract classes (up_or_down and
close_above_daily) flagged is_active in the universe YAML — those carry
most of the signal (Gate 1 R^2 0.10-0.40) at ~1/10th the request load.

DEPENDENCIES:
- requests, pandas, pyaml, pyarrow (project venv)

USAGE:
  python scripts/poll_predmkt_intraday.py                [gated; normal launchd entry]
  python scripts/poll_predmkt_intraday.py --force        [poll now regardless of window]
  python scripts/poll_predmkt_intraday.py --all-classes  [poll every active directional class]

NOTES:
- The daily harvest refreshes YAML. Each poll rechecks market lifecycle/expiry;
  an exhausted eligible set triggers bounded read-only discovery, never a YAML rewrite.
- coverage_*.json records actual coverage/failures. No eligible contracts or usable
  rows is an explicit nonzero outcome, never a fabricated healthy observation.
- Books that are empty or one-sided are recorded with is_stale=true rather
  than dropped (log-don't-drop house style).
- US market holidays are not filtered: a few harmless extra polls.
=============================================================================
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
import sys
import time
from datetime import datetime, time as dtime, timezone
from pathlib import Path

import pandas as pd
import requests
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
UNIVERSE_PATH = BASE_DIR / "config" / "predmkt_equity_universe.yaml"
OUT_DIR = BASE_DIR / "Data" / "work" / "predmkt_equity" / "intraday"

sys.path.insert(0, str(BASE_DIR / 'scripts'))
from predmkt_equity_common import polling_ineligibility
from discover_predmkt_equity_universe import discover

CLOB_BASE = "https://clob.polymarket.com"
HEADERS = {"User-Agent": "ASADO-predmkt/1.0", "Accept": "application/json"}
SLEEP_BETWEEN = 0.15

CLOSE_WIN = (dtime(19, 30), dtime(23, 30))
OPEN_WIN = (dtime(12, 30), dtime(15, 30))
DAILY_CLASSES = {"up_or_down", "close_above_daily"}


def current_window(now_utc: datetime) -> str | None:
    if now_utc.weekday() >= 5:  # Sat/Sun
        return None
    tod = now_utc.time()
    if CLOSE_WIN[0] <= tod < CLOSE_WIN[1]:
        return "close"
    if OPEN_WIN[0] <= tod < OPEN_WIN[1]:
        return "open"
    return None


def poll_market(session: requests.Session, rec: dict, failures=None) -> dict | None:
    """Poll one market's CLOB book; returns a row dict or None on hard failure."""
    try:
        resp = session.get(
            f"{CLOB_BASE}/book",
            params={"token_id": rec["yes_token_id"]},
            headers=HEADERS,
            timeout=15,
        )
        resp.raise_for_status()
        book = resp.json()
    except (requests.RequestException, ValueError) as exc:
        print(f"  ❌ book fetch failed for {rec['ticker']} {rec['market_id'][:14]}...: {exc}")
        if failures is not None:
            failures.append({'market_id': rec['market_id'], 'reason': str(exc),
                             'http_status': getattr(locals().get('resp'), 'status_code', None)})
        return None
    bids = book.get("bids") or []
    asks = book.get("asks") or []
    best_bid = max((float(x["price"]) for x in bids), default=None)
    best_ask = min((float(x["price"]) for x in asks), default=None)
    depth = sum(float(x["price"]) * float(x["size"]) for x in bids + asks)
    is_stale = best_bid is None or best_ask is None
    mid = (best_bid + best_ask) / 2 if not is_stale else (best_bid or best_ask)
    p_aligned = None
    if mid is not None:
        p_aligned = mid if rec["yes_rises_with_stock"] else 1.0 - mid
    spread_bps = (
        (best_ask - best_bid) * 10_000 if (best_bid is not None and best_ask is not None) else None
    )
    return {
        "platform": rec["platform"],
        "market_id": rec["market_id"],
        "ticker": rec["ticker"],
        "contract_class": rec["contract_class"],
        "p_yes_aligned": p_aligned,
        "bid": best_bid,
        "ask": best_ask,
        "spread_bps": spread_bps,
        "liquidity_usd": depth,
        "is_stale": is_stale,
        "yes_rises_with_stock": rec["yes_rises_with_stock"],
    }


def eligible_targets(universe, now, all_classes=False):
    targets, excluded = [], Counter()
    for rec in universe:
        if not all_classes and rec.get('contract_class') not in DAILY_CLASSES:
            continue
        reason = polling_ineligibility(rec, now)
        if reason:
            excluded[reason] += 1
        else:
            targets.append(rec)
    return targets, dict(excluded)


def write_receipt(now, receipt):
    path = OUT_DIR / f'coverage_{now:%Y%m%d_%H%M%S}.json'
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(receipt, indent=2) + '\n')
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="poll regardless of window/weekday")
    parser.add_argument("--all-classes", action="store_true", help="poll every active class")
    args = parser.parse_args()

    now = datetime.now(timezone.utc)
    window = current_window(now)
    if window is None:
        if not args.force:
            return 0  # silent: outside windows, launchd fires us all day
        window = "other"

    if not UNIVERSE_PATH.exists():
        print(f"❌ Universe file missing: {UNIVERSE_PATH} — run discovery first.")
        return 1
    with open(UNIVERSE_PATH) as fh:
        universe = yaml.safe_load(fh) or []
    session = requests.Session()
    targets, excluded = eligible_targets(universe, now, args.all_classes)
    refreshed = False
    refresh_error = None
    if not targets:
        # Read-only discovery: never run the harvest producer or rewrite its YAML.
        try:
            universe, _ = discover(session)
            targets, excluded = eligible_targets(universe, now, args.all_classes)
            refreshed = True
        except (requests.RequestException, ValueError) as exc:
            refresh_error = str(exc)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    receipt = {'observed_at': now.isoformat(), 'window': window,
               'eligible_markets': [r['market_id'] for r in targets],
               'excluded': excluded, 'discovery_refreshed': refreshed,
               'discovery_error': refresh_error, 'failed_markets': []}
    if not targets:
        receipt.update(status='no_coverage', usable_rows=0, rows=0)
        write_receipt(now, receipt)
        print('NO COVERAGE: no eligible unexpired daily contracts; no price rows fabricated')
        return 1

    rows = []
    for rec in targets:
        row = poll_market(session, rec, receipt['failed_markets'])
        if row is not None:
            row["poll_ts"] = now
            row["poll_date"] = now.date()
            row["window"] = window
            rows.append(row)
        time.sleep(SLEEP_BETWEEN)

    if not rows:
        receipt.update(status='no_coverage', usable_rows=0, rows=0)
        write_receipt(now, receipt)
        print("❌ Poll cycle produced zero rows (all book fetches failed).")
        return 1
    out = pd.DataFrame(rows)
    out_path = OUT_DIR / f"poll_{now:%Y%m%d_%H%M%S}.parquet"
    out.to_parquet(out_path, index=False)
    n_stale = int(out["is_stale"].sum())
    usable = len(out) - n_stale
    receipt.update(status='usable' if usable else 'no_usable_rows',
                   rows=len(out), usable_rows=usable, output=str(out_path))
    write_receipt(now, receipt)
    print(
        f"[{now:%Y-%m-%d %H:%M} UTC] window={window}: wrote {len(out)} rows "
        f"({n_stale} stale) -> {out_path.name}"
    )
    return 0 if usable else 1


if __name__ == "__main__":
    sys.exit(main())
