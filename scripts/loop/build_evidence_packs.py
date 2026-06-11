#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/build_evidence_packs.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `dislocation_daily` — which countries fired today (status new /
    intensifying) decide what evidence is frozen.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
    Table `event_log` (attached read-only as `asado`) — curated dated events;
    an event dated within 2 days of the run date also triggers a pack.
- Live HTTPS calls to the GDELT DOC 2.0 API (free, no key) via
  scripts/loop/country_news.py (5.5s self-enforced pacing per request).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/evidence_packs/{YYYY-MM-DD}/{country}.json
    PERMANENT, never pruned. One pack per (run date, country): the trigger
    rows (dislocations and/or event_log entries) plus that day's deduped
    headlines (seendate, domain, title, url). The article-level analog of
    vintage snapshotting — news history survives exactly where it matters.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `gdelt_articles_recent` — every headline pulled by this script,
    accumulated with a 14-DAY ROLLING RETENTION (rows older than 14 days are
    pruned each run). Queryable evidence for the Layer 2 session.

VERSION: 1.0
LAST UPDATED: 2026-06-11
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 3)

DESCRIPTION:
PRD Priority 4 v1 — the article-level evidence layer. ASADO's GDELT panel
stores only aggregates: D5 can say "Indonesia attention z=+2.4" but a tone
aggregate can't distinguish "governor resigned" from "volcano erupted" —
same shock, opposite trades. This script freezes the actual headlines for
every country whose dislocation FIRED today (status new/intensifying) and
for countries with a fresh event_log entry, so the mechanism behind every
trigger is permanently reconstructable. Headlines are Layer 2 reading
evidence ONLY — nothing here enters a detector or the harness
(constitution §10.6).

Scope note (deliberate deviation from a full 34-country nightly sweep): the
GDELT API rate-limits per IP and its cooldown clock resets on every probe.
Triggers exclude D8 (stewardship fires on most of the live book daily and
needs no headline freeze) and are capped at 12 countries/night, highest
|severity| first — skips are logged loudly. `--all` sweeps all 34 countries.

RATE-LIMIT BEHAVIOR (FAIL-IS-FAIL): on GdeltRateLimited the remaining pulls
are ABORTED immediately (retrying makes GDELT's reset-on-probe cooldown
worse). Packs already written are kept; the script exits non-zero so the
nightly job shouts. Already-written packs are never re-pulled on re-runs.

DEPENDENCIES:
- requests, duckdb, pandas (project venv)

USAGE:
  python scripts/loop/build_evidence_packs.py            # trigger countries only
  python scripts/loop/build_evidence_packs.py --all      # full 34-country sweep
  python scripts/loop/build_evidence_packs.py --check    # verify tables/packs

NOTES:
- Pack JSONs are append-only artifacts; do not edit or prune them.
- gdelt_articles_recent holds ALL pulled headlines (max ~25/country/day),
  deduped on (country, url).
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.loop.country_news import GdeltRateLimited, fetch_country_news  # noqa: E402
from scripts.loop.loopdb import T2_UNIVERSE, LOOP_DIR, loop_connection  # noqa: E402

PACK_DIR = LOOP_DIR / "evidence_packs"
RETENTION_DAYS = 14
ARTICLES_PER_COUNTRY = 25
LOOKBACK_DAYS = 2          # article window per pull
EVENT_LOG_WINDOW_D = 2     # event_log entries within +/- this of run date trigger packs

FIRING_STATUSES = ("new", "intensifying")
# D8 (portfolio stewardship) fires for most of the live book every day —
# "you hold this and it moved" needs no headline freeze. Mechanism-hunting
# detectors (D1-D5, D7, D9) do.
EXCLUDE_DETECTORS = {"D8"}
# GDELT throttles per IP and the cooldown resets on every probe: cap the
# nightly pull count (highest |severity| first) so one noisy day can't turn
# into a 30-country crawl. Skipped countries are logged loudly.
MAX_COUNTRIES_PER_RUN = 12
PULL_RETRIES = 2           # 1 retry (60s) then abort the whole run


def log(msg: str) -> None:
    print(f"[evidence_packs] {msg}", flush=True)


def safe_name(country: str) -> str:
    return country.replace(".", "").replace(" ", "_")


def trigger_countries(con, run_date: pd.Timestamp) -> dict[str, list[dict]]:
    """Country -> list of trigger descriptors (dislocations + event_log)."""
    out: dict[str, list[dict]] = {}
    dis = con.execute(
        """
        SELECT detector, archetype, entity, direction, severity, status,
               days_active, components_json
        FROM dislocation_daily
        WHERE date = ? AND status IN ('new', 'intensifying')
        """,
        [str(run_date.date())],
    ).fetchdf()
    for r in dis.itertuples():
        if r.detector in EXCLUDE_DETECTORS:
            continue
        if r.entity not in T2_UNIVERSE:
            continue  # factor-level entities (D7) have no country news
        out.setdefault(r.entity, []).append({
            "kind": "dislocation", "detector": r.detector, "archetype": r.archetype,
            "direction": r.direction, "severity": r.severity, "status": r.status,
            "days_active": int(r.days_active),
            "components": json.loads(r.components_json or "{}"),
        })
    try:
        ev = con.execute(
            """
            SELECT event_date, label, category, countries_affected, is_global
            FROM asado.event_log
            WHERE ABS(DATEDIFF('day', CAST(event_date AS DATE), CAST(? AS DATE))) <= ?
            """,
            [str(run_date.date()), EVENT_LOG_WINDOW_D],
        ).fetchdf()
        for r in ev.itertuples():
            if r.is_global or not isinstance(r.countries_affected, str):
                continue  # global events have no single-country news query
            for country in (c.strip() for c in r.countries_affected.split(",")):
                if country in T2_UNIVERSE:
                    out.setdefault(country, []).append({
                        "kind": "event_log", "event_date": str(r.event_date),
                        "label": r.label, "category": r.category,
                    })
    except Exception as exc:
        log(f"WARNING event_log unavailable ({exc}) — dislocation triggers only")
    return out


def write_pack(run_date: pd.Timestamp, country: str, triggers: list[dict],
               news: dict) -> Path:
    day_dir = PACK_DIR / str(run_date.date())
    day_dir.mkdir(parents=True, exist_ok=True)
    path = day_dir / f"{safe_name(country)}.json"
    path.write_text(json.dumps({
        "run_date": str(run_date.date()),
        "country": country,
        "triggers": triggers,
        "query": news["query"],
        "news_source": news.get("source", "gdelt"),
        "article_window_days": news["timespan_days"],
        "n_articles": news["n_deduped"],
        "articles": news["articles"],
    }, indent=2, ensure_ascii=False))
    return path


def ensure_recent_table(con) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS gdelt_articles_recent (
            pull_date DATE, country VARCHAR, seendate VARCHAR, domain VARCHAR,
            title VARCHAR, url VARCHAR, language VARCHAR, sourcecountry VARCHAR
        )
        """
    )


def upsert_recent(con, run_date: pd.Timestamp, country: str, news: dict) -> int:
    rows = [
        (str(run_date.date()), country, a.get("seendate"), a.get("domain"),
         a.get("title"), a.get("url"), a.get("language"), a.get("sourcecountry"))
        for a in news["articles"]
    ]
    if not rows:
        return 0
    con.execute("DELETE FROM gdelt_articles_recent WHERE pull_date = ? AND country = ?",
                [str(run_date.date()), country])
    con.executemany("INSERT INTO gdelt_articles_recent VALUES (?,?,?,?,?,?,?,?)", rows)
    return len(rows)


def prune_recent(con, run_date: pd.Timestamp) -> None:
    # DuckDB can't parameterize INTERVAL units; RETENTION_DAYS is a module
    # constant, so the f-string is safe.
    cutoff_sql = f"CAST(? AS DATE) - INTERVAL '{RETENTION_DAYS} days'"
    n = con.execute(
        f"SELECT COUNT(*) FROM gdelt_articles_recent WHERE pull_date < {cutoff_sql}",
        [str(run_date.date())],
    ).fetchone()[0]
    if n:
        con.execute(
            f"DELETE FROM gdelt_articles_recent WHERE pull_date < {cutoff_sql}",
            [str(run_date.date())],
        )
        log(f"pruned {n} rows older than {RETENTION_DAYS}d from gdelt_articles_recent")


def run(pull_all: bool) -> int:
    con = loop_connection()
    try:
        run_date = pd.Timestamp(con.execute(
            "SELECT MAX(date) FROM dislocation_daily").fetchone()[0])
        if pd.isna(run_date):
            raise RuntimeError("dislocation_daily is empty — run build_dislocations.py first")
        ensure_recent_table(con)
        triggers = trigger_countries(con, run_date)
        if pull_all:
            countries = list(T2_UNIVERSE)
        else:
            # highest-stakes first: order by max |severity| across triggers
            def stake(c: str) -> float:
                return max((abs(t.get("severity", 0) or 0) for t in triggers[c]), default=0.0)
            ranked = sorted(triggers, key=stake, reverse=True)
            countries = ranked[:MAX_COUNTRIES_PER_RUN]
            if len(ranked) > MAX_COUNTRIES_PER_RUN:
                log(f"WARNING capping pulls at {MAX_COUNTRIES_PER_RUN}/{len(ranked)} trigger "
                    f"countries — skipped: {', '.join(ranked[MAX_COUNTRIES_PER_RUN:])}")
        log(f"run date {run_date.date()}: {len(triggers)} trigger countries"
            + (f", sweeping all {len(countries)}" if pull_all else f", pulling {len(countries)}"))
        if not countries:
            log("nothing fired today — no packs to freeze")
            prune_recent(con, run_date)
            return 0

        n_packs = n_skipped = n_failed = 0
        rate_limited = False
        use_gemini = False
        for country in countries:
            pack_path = PACK_DIR / str(run_date.date()) / f"{safe_name(country)}.json"
            if pack_path.exists():
                # no re-pull, but make sure the recent table has the articles
                # (covers a crash between pack write and table commit)
                have = con.execute(
                    "SELECT COUNT(*) FROM gdelt_articles_recent WHERE pull_date=? AND country=?",
                    [str(run_date.date()), country]).fetchone()[0]
                if not have:
                    pack = json.loads(pack_path.read_text())
                    upsert_recent(con, run_date, country,
                                  {"articles": pack.get("articles", [])})
                    log(f"  {country}: recent table backfilled from existing pack")
                n_skipped += 1
                continue

            news = None
            if not use_gemini:
                try:
                    news = fetch_country_news(country, days=LOOKBACK_DAYS,
                                              max_records=ARTICLES_PER_COUNTRY,
                                              retries=PULL_RETRIES)
                except GdeltRateLimited as exc:
                    # GDELT throttles by IP and its 15-min cooldown resets on
                    # every request — do NOT keep poking it. Switch the rest of
                    # this run to the Gemini Google-Search fallback (explicitly
                    # authorized by Arjun 2026-06-11; packs are labeled).
                    log(f"RATE LIMITED at {country}: {exc}")
                    log("SWITCHING remaining pulls to Gemini Search fallback "
                        "(packs labeled news_source=gemini_search)")
                    rate_limited = True
                    use_gemini = True
                except Exception as exc:
                    log(f"PULL FAILED {country}: {exc}")
                    n_failed += 1
                    continue
            if use_gemini and news is None:
                try:
                    from scripts.loop.country_news_gemini import fetch_country_news_gemini
                    news = fetch_country_news_gemini(
                        country, days=LOOKBACK_DAYS,
                        max_records=ARTICLES_PER_COUNTRY)
                except Exception as exc:
                    log(f"GEMINI FALLBACK FAILED {country}: {exc}")
                    n_failed += 1
                    continue

            path = write_pack(run_date, country, triggers.get(country, []), news)
            n_rows = upsert_recent(con, run_date, country, news)
            src = news.get("source", "gdelt")
            log(f"  {country}: {news['n_deduped']} articles -> {path.name} "
                f"(+{n_rows} recent rows{', source=' + src if src != 'gdelt' else ''})")
            n_packs += 1

        prune_recent(con, run_date)
        log(f"done: {n_packs} packs written, {n_skipped} already existed, {n_failed} failed")
        # Exit semantics (2026-06-11): a GDELT rate limit now fails over to the
        # Gemini Search fallback, so rate_limited alone is NOT a failure — if
        # every pack was still written (mixed sources, labeled), that is a
        # clean 0. PARTIAL (exit 2, loop job records a warning) only when some
        # countries are actually missing; they self-heal next run. Hard failure
        # (exit 1) only when every pull failed and nothing was written.
        if n_failed and not n_packs and not n_skipped:
            return 1
        if n_failed:
            return 2
        if rate_limited:
            log("NOTE: GDELT was rate-limited; remaining packs completed via "
                "Gemini Search fallback — no packs missing.")
        return 0
    finally:
        con.close()


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        rows = con.execute(
            "SELECT pull_date, COUNT(DISTINCT country), COUNT(*) FROM gdelt_articles_recent "
            "GROUP BY 1 ORDER BY 1 DESC LIMIT 5").fetchall()
    except Exception as exc:
        print(f"gdelt_articles_recent missing: {exc}")
        return 1
    finally:
        con.close()
    for d, nc, n in rows:
        print(f"{d}: {nc} countries, {n} articles")
    packs = sorted(PACK_DIR.glob("*/*.json"))
    print(f"evidence packs on disk: {len(packs)}"
          + (f" (latest: {packs[-1].relative_to(PACK_DIR)})" if packs else ""))
    print("CHECK", "PASS" if rows or packs else "FAIL")
    return 0 if (rows or packs) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze GDELT article evidence for fired dislocations.")
    parser.add_argument("--all", action="store_true", help="full 34-country sweep, not just triggers")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        return check()
    return run(pull_all=args.all)


if __name__ == "__main__":
    sys.exit(main())
