"""
=============================================================================
SCRIPT NAME: discover_predmkt_equity_universe.py
=============================================================================

INPUT FILES:
- Polymarket Gamma API (https://gamma-api.polymarket.com/events, tag_slug=
  stocks) — live network source, no local input file
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/predmkt_equity_universe.yaml
  (read in --validate-only mode)

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/predmkt_equity_universe.yaml
  Curated firm-level equity market universe (PRD §4.1): one record per
  directional Polymarket stock market with ticker mapping and
  direction-cleaning metadata. Overwritten on each discovery run; a
  timestamped backup of the previous file is saved to
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/backups/{ts}/

VERSION: 1.0
LAST UPDATED: 2026-07-03
AUTHOR: Claude Code (for Arjun Divecha)

DESCRIPTION:
Milestone M1 of the Tier 1 overnight prediction-market -> equity signal.
Discovers all ACTIVE firm-level stock markets on Polymarket (tag "stocks"),
parses each question into a structured record via predmkt_equity_common
(ticker, target price, direction, contract class, YES-alignment flag), and
writes the curated universe YAML that the intraday poller (M2) and signal
builder (M3) will consume. Bucket markets are excluded (not directional).

DEPENDENCIES:
- requests, pyyaml (project venv)

USAGE:
  python scripts/discover_predmkt_equity_universe.py                 [discover + write YAML]
  python scripts/discover_predmkt_equity_universe.py --dry-run       [discover, print, no write]
  python scripts/discover_predmkt_equity_universe.py --validate-only [re-resolve every record in
                                                                      the existing YAML against Gamma]

NOTES:
- Polymarket rotates firm markets weekly/monthly: re-run this at least weekly
  (it is idempotent — full regeneration each run).
- Records below MIN_VOLUME_USD are still written but flagged is_active: false
  so downstream consumers skip them; nothing is silently dropped.
- ETF underlyings (SPY, QQQ, EWY, ...) are kept with is_etf: true.
=============================================================================
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "scripts"))

from predmkt_equity_common import parse_stock_market  # noqa: E402

CONFIG_PATH = BASE_DIR / "config" / "predmkt_equity_universe.yaml"
BACKUP_ROOT = BASE_DIR / "Data" / "backups"

GAMMA_BASE = "https://gamma-api.polymarket.com"
TAG_SLUG = "stocks"
PAGE_SIZE = 100
MAX_OFFSET = 2000  # Gamma rejects offsets > ~2000; active set is far smaller
MIN_VOLUME_USD = 100.0  # below this a strike is dead; kept but is_active=false
HEADERS = {"User-Agent": "ASADO-predmkt/1.0", "Accept": "application/json"}


def _fetch_events(session: requests.Session, closed: bool = False) -> list[dict]:
    """Paginate all stock-tag events from Gamma."""
    events: list[dict] = []
    offset = 0
    while offset <= MAX_OFFSET:
        resp = session.get(
            f"{GAMMA_BASE}/events",
            params={
                "closed": str(closed).lower(),
                "active": "true" if not closed else None,
                "limit": PAGE_SIZE,
                "offset": offset,
                "order": "endDate",
                "ascending": "false",
                "tag_slug": TAG_SLUG,
            },
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        page = resp.json()
        if not isinstance(page, list) or not page:
            break
        events.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
        time.sleep(0.25)
    return events


def discover(session: requests.Session) -> tuple[list[dict], int]:
    """Return (directional records, n_skipped_nondirectional) for active markets."""
    events = _fetch_events(session, closed=False)
    records: list[dict] = []
    skipped = 0
    seen: set[str] = set()
    for event in events:
        for market in event.get("markets", []):
            rec = parse_stock_market(market, event)
            if rec is None:
                skipped += 1
                continue
            if rec["market_id"] in seen:
                continue
            seen.add(rec["market_id"])
            volume = rec.get("volume_usd") or 0.0
            rec["is_active"] = bool(volume >= MIN_VOLUME_USD)
            records.append(rec)
    records.sort(key=lambda r: (r["ticker"], r["contract_class"], r.get("target_price") or 0))
    return records, skipped


def write_yaml(records: list[dict], skipped: int) -> None:
    if CONFIG_PATH.exists():
        ts = datetime.now().strftime("%Y_%m_%d_%H%M%S")
        backup_dir = BACKUP_ROOT / ts
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(CONFIG_PATH, backup_dir / CONFIG_PATH.name)
    header = (
        "# =============================================================================\n"
        "# Polymarket firm-level equity universe — Tier 1 overnight signal (PRD §4.1)\n"
        f"# Generated by discover_predmkt_equity_universe.py on {datetime.now():%Y-%m-%d %H:%M}\n"
        f"# {len(records)} directional markets ({skipped} non-directional bucket markets excluded)\n"
        "# Direction cleaning: yes_rises_with_stock=false means the stored aligned\n"
        "# price is 1 - p_yes (only hit_low contracts invert).\n"
        "# Regenerate weekly — Polymarket rotates firm markets.\n"
        "# =============================================================================\n"
    )
    with open(CONFIG_PATH, "w") as fh:
        fh.write(header)
        yaml.safe_dump(records, fh, sort_keys=False, allow_unicode=True)
    print(f"Wrote {len(records)} records -> {CONFIG_PATH}")


def validate_only(session: requests.Session) -> int:
    """Re-resolve every YAML record against Gamma; return count of failures."""
    if not CONFIG_PATH.exists():
        print(f"❌ {CONFIG_PATH} does not exist — run discovery first.")
        return 1
    with open(CONFIG_PATH) as fh:
        records = yaml.safe_load(fh) or []
    failures = 0
    for rec in records:
        cid = rec.get("market_id")
        try:
            resp = session.get(
                f"{GAMMA_BASE}/markets",
                params={"condition_ids": cid},
                headers=HEADERS,
                timeout=30,
            )
            resp.raise_for_status()
            found = resp.json()
            if not found:
                print(f"  ❌ unresolved: {rec.get('ticker')} {rec.get('question')} ({cid})")
                failures += 1
        except requests.RequestException as exc:
            print(f"  ❌ network error on {cid}: {exc}")
            failures += 1
        time.sleep(0.15)
    print(f"Validation complete: {len(records) - failures}/{len(records)} resolved.")
    return 0 if failures == 0 else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="discover and print, no write")
    parser.add_argument("--validate-only", action="store_true", help="validate existing YAML")
    args = parser.parse_args()

    session = requests.Session()
    if args.validate_only:
        return validate_only(session)

    records, skipped = discover(session)
    from collections import Counter

    by_class = Counter(r["contract_class"] for r in records)
    by_ticker = Counter(r["ticker"] for r in records)
    active = sum(1 for r in records if r["is_active"])
    print(f"Discovered {len(records)} directional markets ({skipped} bucket markets excluded)")
    print(f"  active (volume >= ${MIN_VOLUME_USD:.0f}): {active}")
    print(f"  by class: {dict(by_class)}")
    print(f"  by ticker: {dict(by_ticker.most_common())}")
    if args.dry_run:
        print("[dry-run] not writing YAML")
        return 0
    write_yaml(records, skipped)
    return 0


if __name__ == "__main__":
    sys.exit(main())
