#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/build_forward_calendar.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/forward_calendar_seed.yaml
    Hand-curated forward event registry (CB decisions, elections, index
    reviews). Every date verified against a primary source — see the seed
    header rules.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/country_mapping.json
    T2 country name validation.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `forward_calendar` (idempotent drop + recreate). Lives in the LOOP
    DB (not asado.duckdb) because setup_duckdb.py deletes the main warehouse
    on every monthly rebuild.

VERSION: 1.0
LAST UPDATED: 2026-06-10
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 3)

DESCRIPTION:
Loads the forward event calendar into the loop DuckDB. This is the "trades
need catalysts" surface from the Alpha-Hunting PRD (Priority 5): the Layer 2
reasoning session sees the dislocation table PLUS this calendar, so theses
can be anchored to scheduled catalysts (FOMC, Copom, MSCI classification,
elections). The daily brief renders the next 30 days.

Validates (FAIL-IS-FAIL — hard errors, no silent skips):
- unique event_ids, parseable dates, valid category/severity vocabulary
- countries_affected names are valid T2 names
- warns (does not fail) when fewer than 2 future events remain per category,
  so the calendar does not silently go stale.

DEPENDENCIES:
- duckdb, pyyaml (project venv)

USAGE:
  python scripts/loop/build_forward_calendar.py             # load/rebuild
  python scripts/loop/build_forward_calendar.py --check     # validate YAML only
  python scripts/loop/build_forward_calendar.py --upcoming 45   # print next 45 days
=============================================================================
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path

import duckdb
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.loop.loopdb import loop_connection, t2_countries  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SEED_PATH = BASE_DIR / "config" / "forward_calendar_seed.yaml"

VALID_CATEGORIES = {"central_bank", "election", "index_review"}
VALID_SEVERITIES = {"high", "medium", "low"}


def load_seed() -> list[dict]:
    events = yaml.safe_load(SEED_PATH.read_text())
    if not isinstance(events, list):
        raise ValueError("forward_calendar_seed.yaml must be a YAML list")
    return events


def validate(events: list[dict]) -> list[str]:
    """Hard validation. Returns error list (empty = valid)."""
    errors: list[str] = []
    seen: set[str] = set()
    valid_countries = set(t2_countries())

    for i, ev in enumerate(events):
        prefix = f"Event #{i + 1} ({ev.get('event_id', 'NO_ID')})"
        for field in ("event_id", "event_date", "label", "category",
                      "severity", "is_global", "date_confirmed", "verified_on"):
            if field not in ev or ev[field] is None:
                errors.append(f"{prefix}: missing required field '{field}'")

        eid = ev.get("event_id")
        if eid in seen:
            errors.append(f"{prefix}: duplicate event_id")
        seen.add(eid)

        for dfield in ("event_date", "verified_on"):
            try:
                datetime.strptime(str(ev.get(dfield, "")), "%Y-%m-%d")
            except ValueError:
                errors.append(f"{prefix}: unparseable {dfield} {ev.get(dfield)!r}")

        if ev.get("category") not in VALID_CATEGORIES:
            errors.append(f"{prefix}: invalid category {ev.get('category')!r}")
        if ev.get("severity") not in VALID_SEVERITIES:
            errors.append(f"{prefix}: invalid severity {ev.get('severity')!r}")

        countries = ev.get("countries_affected")
        if countries:
            for name in [c.strip() for c in countries.split(",")]:
                if name not in valid_countries:
                    errors.append(f"{prefix}: unknown T2 country {name!r}")
    return errors


def staleness_warnings(events: list[dict]) -> list[str]:
    """Warn when a category is running out of future entries."""
    today = date.today().isoformat()
    warnings = []
    for cat in sorted(VALID_CATEGORIES):
        future = [e for e in events if e["category"] == cat and str(e["event_date"]) >= today]
        if len(future) < 2:
            warnings.append(
                f"CALENDAR RUNNING DRY: category '{cat}' has only {len(future)} future "
                f"event(s) — extend config/forward_calendar_seed.yaml"
            )
    return warnings


def build(events: list[dict]) -> None:
    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS forward_calendar")
        con.execute(
            """
            CREATE TABLE forward_calendar (
                event_id VARCHAR PRIMARY KEY,
                event_date DATE,
                label VARCHAR,
                category VARCHAR,
                severity VARCHAR,
                is_global BOOLEAN,
                countries_affected VARCHAR,
                source_url VARCHAR,
                tags VARCHAR,
                date_confirmed BOOLEAN,
                verified_on DATE
            )
            """
        )
        rows = [
            (
                ev["event_id"], str(ev["event_date"]), ev["label"], ev["category"],
                ev["severity"], bool(ev["is_global"]), ev.get("countries_affected"),
                ev.get("source_url"), ev.get("tags"), bool(ev["date_confirmed"]),
                str(ev["verified_on"]),
            )
            for ev in events
        ]
        con.executemany(
            "INSERT INTO forward_calendar VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", rows
        )
        n_future = con.execute(
            "SELECT COUNT(*) FROM forward_calendar WHERE event_date >= current_date"
        ).fetchone()[0]
        print(f"forward_calendar: {len(rows)} rows loaded ({n_future} future-dated)")
    finally:
        con.close()


def print_upcoming(days: int) -> None:
    con = loop_connection(read_only=True)
    try:
        df = con.execute(
            """
            SELECT event_date, category, severity, label, countries_affected
            FROM forward_calendar
            WHERE event_date BETWEEN current_date AND current_date + INTERVAL (?) DAY
            ORDER BY event_date, severity
            """,
            [days],
        ).fetchdf()
        if df.empty:
            print(f"No scheduled events in the next {days} days.")
            return
        print(f"Scheduled events, next {days} days:")
        for r in df.itertuples():
            scope = r.countries_affected or "global"
            print(f"  {r.event_date}  [{r.severity:>6}] {r.label}  ({scope})")
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the forward event calendar (loop DB).")
    parser.add_argument("--check", action="store_true", help="validate YAML only, no DB write")
    parser.add_argument("--upcoming", type=int, metavar="DAYS", default=None,
                        help="print events in the next N days (no rebuild)")
    args = parser.parse_args()

    if args.upcoming is not None:
        print_upcoming(args.upcoming)
        return 0

    events = load_seed()
    errors = validate(events)
    if errors:
        print(f"VALIDATION FAILED ({len(errors)} errors):")
        for e in errors:
            print(f"  - {e}")
        return 1
    for w in staleness_warnings(events):
        print(f"WARNING: {w}")
    print(f"Seed valid: {len(events)} events")

    if args.check:
        return 0

    build(events)
    return 0


if __name__ == "__main__":
    sys.exit(main())
