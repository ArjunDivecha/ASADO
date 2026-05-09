#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/build_event_log.py
=============================================================================

INPUT FILES:
- config/event_log_seed.yaml   (hand-curated event registry)

OUTPUT TABLES (added to Data/asado.duckdb):
- event_log                     (~200 rows, date-anchored event registry)

VERSION: 1.0
LAST UPDATED: 2026-05-08
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
Loads the hand-curated event_log_seed.yaml into the event_log table in
DuckDB. Idempotent — drops and recreates the table on each run.

Validates:
- All event_ids are unique
- All categories are from the controlled vocabulary
- All severities are valid
- All dates are parseable
- countries_affected entries are valid T2 names

DEPENDENCIES:
- duckdb >= 0.10, pyyaml

USAGE:
  python scripts/build_event_log.py              # load/rebuild event_log
  python scripts/build_event_log.py --check      # validate YAML only
  python scripts/build_event_log.py --stats      # show category/severity breakdown
=============================================================================
"""

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

import duckdb
import yaml

BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = BASE_DIR / "config"
DATA_DIR = BASE_DIR / "Data"
DB_PATH = DATA_DIR / "asado.duckdb"
SEED_PATH = CONFIG_DIR / "event_log_seed.yaml"
COUNTRY_MAPPING_PATH = CONFIG_DIR / "country_mapping.json"

# Controlled vocabularies from PRD §3.2
VALID_CATEGORIES = {
    "central_bank",
    "macro_release",
    "oil_supply",
    "geopolitical",
    "financial_crisis",
    "trade_policy",
    "election",
    "regulatory",
}

VALID_SEVERITIES = {"high", "medium", "low"}

# Canonical tag vocabulary (for validation warnings, not hard errors)
CANONICAL_TAGS = {
    "iran", "russia", "israel", "ukraine", "saudi_arabia",
    "opec_cut", "opec_plus", "fomc_pivot", "fomc", "currency_crisis",
    "em_contagion", "covid", "oil", "war", "sanctions",
    "trade_war", "tariffs", "trump", "china", "us",
}


def load_country_names() -> set[str]:
    """Load valid T2 country names from country_mapping.json."""
    with open(COUNTRY_MAPPING_PATH) as f:
        mapping = json.load(f)
    return set(mapping["countries"].keys())


def load_seed() -> list[dict]:
    """Load and parse the YAML seed file."""
    with open(SEED_PATH) as f:
        events = yaml.safe_load(f)
    if not isinstance(events, list):
        raise ValueError("event_log_seed.yaml must be a YAML list")
    return events


def validate_events(events: list[dict], valid_countries: set[str]) -> list[str]:
    """Validate all events. Returns list of error messages (empty = valid)."""
    errors = []
    warnings = []
    seen_ids = set()

    for i, ev in enumerate(events):
        prefix = f"Event #{i+1} ({ev.get('event_id', 'NO_ID')})"

        # Required fields
        for field in ("event_id", "event_date", "label", "category", "severity", "is_global"):
            if field not in ev or ev[field] is None:
                errors.append(f"{prefix}: missing required field '{field}'")

        # Unique event_id
        eid = ev.get("event_id")
        if eid:
            if eid in seen_ids:
                errors.append(f"{prefix}: duplicate event_id '{eid}'")
            seen_ids.add(eid)

        # Category vocabulary
        cat = ev.get("category")
        if cat and cat not in VALID_CATEGORIES:
            errors.append(f"{prefix}: invalid category '{cat}' (valid: {sorted(VALID_CATEGORIES)})")

        # Severity vocabulary
        sev = ev.get("severity")
        if sev and sev not in VALID_SEVERITIES:
            errors.append(f"{prefix}: invalid severity '{sev}' (valid: {sorted(VALID_SEVERITIES)})")

        # Date parsing
        edate = ev.get("event_date")
        if edate:
            try:
                if isinstance(edate, str):
                    datetime.strptime(edate, "%Y-%m-%d")
                elif not isinstance(edate, date):
                    errors.append(f"{prefix}: event_date not a valid date: {edate}")
            except ValueError:
                errors.append(f"{prefix}: cannot parse event_date '{edate}'")

        # End date parsing (optional)
        end_date = ev.get("end_date")
        if end_date:
            try:
                if isinstance(end_date, str):
                    datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                errors.append(f"{prefix}: cannot parse end_date '{end_date}'")

        # countries_affected validation
        countries = ev.get("countries_affected")
        is_global = ev.get("is_global", False)
        if countries and not is_global:
            for c in str(countries).split(","):
                c = c.strip()
                if c and c not in valid_countries:
                    errors.append(f"{prefix}: invalid country '{c}' in countries_affected")
        elif is_global and countries:
            warnings.append(f"{prefix}: is_global=True but countries_affected is set (should be null)")

    # Print warnings (non-fatal)
    for w in warnings:
        print(f"  [WARN] {w}")

    return errors


def create_table(con: duckdb.DuckDBPyConnection):
    """Create the event_log table with schema from PRD §3.1."""
    con.execute("DROP TABLE IF EXISTS event_log")
    con.execute("""
        CREATE TABLE event_log (
            event_id            VARCHAR PRIMARY KEY,
            event_date          DATE NOT NULL,
            end_date            DATE,
            label               VARCHAR NOT NULL,
            description         VARCHAR,
            category            VARCHAR NOT NULL,
            subcategory         VARCHAR,
            severity            VARCHAR NOT NULL,
            countries_affected  VARCHAR,
            is_global           BOOLEAN NOT NULL,
            source_url          VARCHAR,
            tags                VARCHAR,
            notes               VARCHAR,
            added_date          DATE NOT NULL DEFAULT CURRENT_DATE,
            added_by            VARCHAR DEFAULT 'manual'
        )
    """)
    con.execute("CREATE INDEX IF NOT EXISTS idx_event_log_date ON event_log(event_date)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_event_log_category ON event_log(category)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_event_log_severity ON event_log(severity)")


def insert_events(con: duckdb.DuckDBPyConnection, events: list[dict]):
    """Insert all events into the table."""
    for ev in events:
        event_date = ev["event_date"]
        if isinstance(event_date, date):
            event_date = event_date.isoformat()

        end_date = ev.get("end_date")
        if isinstance(end_date, date):
            end_date = end_date.isoformat()

        con.execute("""
            INSERT INTO event_log (
                event_id, event_date, end_date, label, description,
                category, subcategory, severity, countries_affected,
                is_global, source_url, tags, notes, added_date, added_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_DATE, 'manual')
        """, [
            ev["event_id"],
            event_date,
            end_date,
            ev["label"],
            ev.get("description"),
            ev["category"],
            ev.get("subcategory"),
            ev["severity"],
            ev.get("countries_affected"),
            ev.get("is_global", False),
            ev.get("source_url"),
            ev.get("tags"),
            ev.get("notes"),
        ])


def print_stats(con: duckdb.DuckDBPyConnection):
    """Print category and severity breakdown."""
    print("\n  Event Log Statistics:")
    print("  " + "─" * 50)

    total = con.execute("SELECT COUNT(*) FROM event_log").fetchone()[0]
    print(f"  Total events: {total}")

    date_range = con.execute(
        "SELECT MIN(event_date), MAX(event_date) FROM event_log"
    ).fetchone()
    print(f"  Date range: {date_range[0]} → {date_range[1]}")

    print("\n  By category:")
    cats = con.execute("""
        SELECT category, COUNT(*) as n
        FROM event_log GROUP BY category ORDER BY n DESC
    """).fetchall()
    for cat, n in cats:
        print(f"    {cat:20s}: {n:3d}")

    print("\n  By severity:")
    sevs = con.execute("""
        SELECT severity, COUNT(*) as n
        FROM event_log GROUP BY severity ORDER BY n DESC
    """).fetchall()
    for sev, n in sevs:
        print(f"    {sev:10s}: {n:3d}")

    print("\n  Global vs country-specific:")
    glob = con.execute("""
        SELECT is_global, COUNT(*) as n
        FROM event_log GROUP BY is_global ORDER BY is_global DESC
    """).fetchall()
    for is_g, n in glob:
        label = "global" if is_g else "country-specific"
        print(f"    {label:20s}: {n:3d}")


def main():
    parser = argparse.ArgumentParser(
        description="Build event_log table in ASADO DuckDB from YAML seed"
    )
    parser.add_argument("--check", action="store_true",
                        help="Validate YAML only, don't write to DB")
    parser.add_argument("--stats", action="store_true",
                        help="Show statistics after build")
    args = parser.parse_args()

    print("=" * 60)
    print("  ASADO Event Log Builder")
    print("=" * 60)

    # Load seed
    print(f"\n  Loading: {SEED_PATH}")
    events = load_seed()
    print(f"  Events in seed: {len(events)}")

    # Load valid countries
    valid_countries = load_country_names()
    print(f"  Valid T2 countries: {len(valid_countries)}")

    # Validate
    print("\n  Validating ...")
    errors = validate_events(events, valid_countries)
    if errors:
        print(f"\n  VALIDATION FAILED — {len(errors)} error(s):")
        for e in errors:
            print(f"    ✗ {e}")
        sys.exit(1)
    print(f"  ✓ All {len(events)} events pass validation")

    if args.check:
        print("\n  --check mode: validation only, no DB write")
        return

    # Build table
    if not DB_PATH.exists():
        print(f"\n  ERROR: DuckDB not found at {DB_PATH}")
        print("  Run setup_duckdb.py first.")
        sys.exit(1)

    print(f"\n  Connecting to: {DB_PATH}")
    con = duckdb.connect(str(DB_PATH))

    print("  Creating event_log table ...")
    create_table(con)

    print(f"  Inserting {len(events)} events ...")
    insert_events(con, events)

    # Verify
    count = con.execute("SELECT COUNT(*) FROM event_log").fetchone()[0]
    print(f"  ✓ event_log table: {count} rows")

    if args.stats:
        print_stats(con)
    else:
        # Brief summary
        cats = con.execute("""
            SELECT category, COUNT(*) as n
            FROM event_log GROUP BY category ORDER BY n DESC
        """).fetchall()
        cat_summary = ", ".join(f"{c}={n}" for c, n in cats)
        print(f"  Categories: {cat_summary}")

    con.close()
    print("\n  Done.")


if __name__ == "__main__":
    main()
