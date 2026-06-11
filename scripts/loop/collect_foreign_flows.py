#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/collect_foreign_flows.py
=============================================================================

INPUT FILES:
- https://www.fpi.nsdl.co.in/web/Reports/Archive.aspx  (network source)
    NSDL "Daily Trends in FPI Investments" archive. ASP.NET page: GET once
    for __VIEWSTATE tokens, then POST a date and it returns a table of daily
    FPI flows for roughly the week ending on that date. Verified depth:
    2017 onward. This is India's official depository-confirmed foreign
    portfolio investor buy/sell data.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/raw/foreign_flows/
    Local HTML cache of every archive response (nsdl_upto_YYYY-MM-DD.html).
    Cached files are never re-fetched, so an interrupted backfill resumes
    where it stopped.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/foreign_flows.parquet
    Tidy panel (date, country, value, variable, source). Merged
    incrementally: new dates replace old rows for the same (date, variable).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `foreign_flows_daily` (idempotent rebuild from the parquet).
    Lives in the LOOP DB because setup_duckdb.py deletes the main warehouse
    on every monthly rebuild.

VERSION: 1.0
LAST UPDATED: 2026-06-10
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 3)

DESCRIPTION:
Collects daily foreign investor flows (Alpha-Hunting PRD Priority 6 — "the
best dataset not yet owned"). v1.0 covers India via NSDL FPI, the one PRD
exchange that is reachable from this network:

    TWSE (Taiwan)      -> www.twse.com.tw times out (geo-blocked)
    KRX (Korea)        -> data.krx.co.kr returns 403
    SET (Thailand)     -> www.set.or.th API returns 403
    IDX (Indonesia)    -> www.idx.co.id returns 403 (Cloudflare)
    PSE (Philippines)  -> reachable but market-level foreign flow needs
                          report scraping; deferred
    B3 (Brazil)        -> endpoint discovery needed; deferred

Variables produced (country='India', source='nsdl_fpi', all USD million,
converted by NSDL at its published daily RBI reference rate):

    FOREIGN_EQUITY_NET_USD_MN        equity sub-total net investment
    FOREIGN_EQUITY_GROSS_BUY_USD_MN  equity sub-total gross purchases
    FOREIGN_EQUITY_GROSS_SELL_USD_MN equity sub-total gross sales
    FOREIGN_DEBT_NET_USD_MN          sum of all Debt* category sub-totals
    FOREIGN_TOTAL_NET_USD_MN         the published all-category Total row

Gross figures are published in Rs crore only; they are converted using the
same daily conversion rate NSDL prints on each date row (verified: the
published USD net equals net_inr_crore * 10 / rate to the cent).

Negative numbers appear in parentheses, e.g. (406.29) = -406.29.

DEPENDENCIES:
- requests, pandas, pyarrow, duckdb (project venv)

USAGE:
  python scripts/loop/collect_foreign_flows.py                  # daily: fetch current week, merge
  python scripts/loop/collect_foreign_flows.py --backfill 2017-01-06   # weekly walk to today
  python scripts/loop/collect_foreign_flows.py --check          # report panel coverage, no fetch

NOTES:
- Backfill iterates FRIDAYS from the start date; each archive response
  covers at least the Mon-Fri of its week (2017 responses covered 7+
  trading days), so a weekly stride has no gaps.
- Per-source try/except per house rules: one failed week is logged and
  skipped; the panel keeps whatever it already has (source-level merge).
- Parquet is rewritten every 10 fetches during a backfill so an
  interruption loses at most ~10 weeks of work (result-persistence rule).
=============================================================================
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.loop.loopdb import loop_connection  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DIR = BASE_DIR / "Data" / "raw" / "foreign_flows"
PANEL_PATH = BASE_DIR / "Data" / "work" / "loop" / "foreign_flows.parquet"

ARCHIVE_URL = "https://www.fpi.nsdl.co.in/web/Reports/Archive.aspx"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
FETCH_SLEEP_S = 1.0  # politeness delay between archive POSTs

DATE_RE = re.compile(r"^\d{2}-[A-Za-z]{3}-\d{4}$")


# ---------------------------------------------------------------------------
# Fetch layer
# ---------------------------------------------------------------------------

def _new_session() -> tuple[requests.Session, dict]:
    """GET the archive page once; return (session, hidden ASP.NET tokens)."""
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA})
    resp = sess.get(ARCHIVE_URL, timeout=30)
    resp.raise_for_status()
    tokens = {}
    for name in ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__EVENTVALIDATION"):
        m = re.search(r'id="%s" value="([^"]*)"' % name, resp.text)
        if not m:
            raise RuntimeError(f"NSDL archive page missing token {name} — page layout changed?")
        tokens[name] = m.group(1)
    return sess, tokens


def fetch_archive_html(sess: requests.Session, tokens: dict, upto: date) -> str:
    """POST one archive request for the week ending `upto`. Returns HTML."""
    d_str = upto.strftime("%d-%b-%Y")
    data = {
        "__EVENTTARGET": "btnSubmit1",
        "__EVENTARGUMENT": "",
        **tokens,
        "txtDate": d_str,
        "hdnDate": d_str,
        "hdnFlag": "",
        "HdnValexceldata": "",
    }
    resp = sess.post(
        ARCHIVE_URL, data=data, timeout=45,
        headers={"Origin": "https://www.fpi.nsdl.co.in", "Referer": ARCHIVE_URL},
    )
    resp.raise_for_status()
    return resp.text


def cached_or_fetch(sess, tokens, upto: date, *, refetch: bool = False) -> str | None:
    """Return archive HTML for `upto`, using the local cache when present."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    cache = RAW_DIR / f"nsdl_upto_{upto.isoformat()}.html"
    if cache.exists() and not refetch:
        return cache.read_text(encoding="utf-8", errors="replace")
    html = fetch_archive_html(sess, tokens, upto)
    cache.write_text(html, encoding="utf-8")
    time.sleep(FETCH_SLEEP_S)
    return html


# ---------------------------------------------------------------------------
# Parse layer
# ---------------------------------------------------------------------------

def _num(cell: str) -> float:
    """Parse NSDL number: '1,234.56' / '(406.29)' -> -406.29."""
    s = cell.strip().replace(",", "")
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    val = float(s)
    return -val if neg else val


def parse_archive(html: str) -> pd.DataFrame:
    """Parse one archive/Latest response into tidy rows.

    Table grammar (verified identical 2017-2026):
      8 cells: date, category, route, gb, gs, net_inr, net_usd, 'Rs.<rate>'
      6 cells: category, route, gb, gs, net_inr, net_usd
      5 cells: route/label, gb, gs, net_inr, net_usd
               ('Sub-total' closes a category, 'Total' closes a date block)
    """
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, re.S)
    records: list[dict] = []
    cur_date: date | None = None
    cur_cat: str | None = None
    cur_rate: float | None = None
    started = False
    # per-date accumulators
    acc: dict = {}

    def flush_date():
        nonlocal acc
        if cur_date is None or not acc:
            acc = {}
            return
        eq = acc.get("Equity")
        if eq is not None:
            gb_usd = eq["gb_inr"] * 10.0 / cur_rate if cur_rate else None
            gs_usd = eq["gs_inr"] * 10.0 / cur_rate if cur_rate else None
            records.append({"date": cur_date, "variable": "FOREIGN_EQUITY_NET_USD_MN", "value": eq["net_usd"]})
            if gb_usd is not None:
                records.append({"date": cur_date, "variable": "FOREIGN_EQUITY_GROSS_BUY_USD_MN", "value": gb_usd})
                records.append({"date": cur_date, "variable": "FOREIGN_EQUITY_GROSS_SELL_USD_MN", "value": gs_usd})
        debt = [v["net_usd"] for k, v in acc.items() if k.startswith("Debt")]
        if debt:
            records.append({"date": cur_date, "variable": "FOREIGN_DEBT_NET_USD_MN", "value": sum(debt)})
        if "Total" in acc:
            records.append({"date": cur_date, "variable": "FOREIGN_TOTAL_NET_USD_MN", "value": acc["Total"]["net_usd"]})
        acc = {}

    for r in rows:
        cells = [re.sub(r"<[^>]+>", "", c).replace("\xa0", " ").strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", r, re.S)]
        if not cells or not any(cells):
            continue
        if "Reporting Date" in cells[0]:
            started = True
            continue
        if not started:
            continue

        try:
            if len(cells) == 8 and DATE_RE.match(cells[0]):
                flush_date()
                cur_date = datetime.strptime(cells[0], "%d-%b-%Y").date()
                cur_cat = cells[1]
                # cells[7] looks like 'Rs.95.6359' — must not capture the dot after 'Rs'
                rate_m = re.search(r"\d+(?:\.\d+)?", cells[7])
                cur_rate = float(rate_m.group(0)) if rate_m else None
                _accumulate(acc, cur_cat, cells[2], cells[3:7])
            elif len(cells) == 6:
                cur_cat = cells[0]
                _accumulate(acc, cur_cat, cells[1], cells[2:6])
            elif len(cells) == 5:
                label = cells[0]
                if label == "Total":
                    acc["Total"] = {"net_usd": _num(cells[4]), "gb_inr": _num(cells[1]),
                                    "gs_inr": _num(cells[2]), "net_inr": _num(cells[3])}
                else:
                    _accumulate(acc, cur_cat, label, cells[1:5])
        except (ValueError, TypeError):
            continue  # non-data row (notes, headers)

    flush_date()
    if not records:
        return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])
    df = pd.DataFrame(records)
    df["country"] = "India"
    df["source"] = "nsdl_fpi"
    df["date"] = pd.to_datetime(df["date"])
    return df[["date", "country", "value", "variable", "source"]]


def _accumulate(acc: dict, category: str | None, route: str, nums: list[str]) -> None:
    """Keep only each category's Sub-total row (the per-date category total)."""
    if category is None or route != "Sub-total":
        return
    acc[category] = {
        "gb_inr": _num(nums[0]),
        "gs_inr": _num(nums[1]),
        "net_inr": _num(nums[2]),
        "net_usd": _num(nums[3]),
    }


# ---------------------------------------------------------------------------
# Persist layer
# ---------------------------------------------------------------------------

def load_panel() -> pd.DataFrame:
    if PANEL_PATH.exists():
        return pd.read_parquet(PANEL_PATH)
    return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])


def merge_and_save(panel: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """New rows win on (date, country, variable); panel is rewritten atomically."""
    if new.empty:
        return panel
    merged = pd.concat([panel, new], ignore_index=True)
    merged = merged.drop_duplicates(subset=["date", "country", "variable"], keep="last")
    merged = merged.sort_values(["date", "variable"]).reset_index(drop=True)
    PANEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PANEL_PATH.with_suffix(".parquet.tmp")
    merged.to_parquet(tmp, index=False)
    tmp.replace(PANEL_PATH)
    return merged


def rebuild_db_table() -> None:
    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS foreign_flows_daily")
        con.execute(
            f"""
            CREATE TABLE foreign_flows_daily AS
            SELECT CAST(date AS DATE) AS date, country, value, variable, source
            FROM read_parquet('{PANEL_PATH}')
            """
        )
        n, lo, hi = con.execute(
            "SELECT COUNT(*), MIN(date), MAX(date) FROM foreign_flows_daily"
        ).fetchone()
        print(f"foreign_flows_daily: {n} rows, {lo} -> {hi}")
    finally:
        con.close()


# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------

def fetch_week(sess, tokens, end_date: date, *, refetch: bool = False,
               max_step_back: int = 4) -> pd.DataFrame:
    """Fetch the week ending `end_date`, stepping back day-by-day on empty.

    NSDL returns a table-less page when the requested To-Date is a market
    holiday (verified: 01-May-2026 / Maharashtra Day). Without the fallback
    a holiday Friday would silently lose its whole week.
    """
    for back in range(max_step_back + 1):
        d = end_date - timedelta(days=back)
        html = cached_or_fetch(sess, tokens, d, refetch=refetch)
        df = parse_archive(html)
        if not df.empty:
            return df
    return pd.DataFrame(columns=["date", "country", "value", "variable", "source"])


def run_daily() -> int:
    """Fetch the current week (always refetch — provisional data firms up)."""
    sess, tokens = _new_session()
    try:
        new = fetch_week(sess, tokens, date.today(), refetch=True)
    except requests.RequestException as e:
        print(f"[nsdl_fpi] FETCH FAILED: {e} — existing panel preserved")
        return 1
    if new.empty:
        print("[nsdl_fpi] no data in the last 5 days — existing panel preserved")
        return 1
    panel = merge_and_save(load_panel(), new)
    print(f"[nsdl_fpi] merged {new['date'].nunique()} day(s), panel now "
          f"{panel['date'].min().date()} -> {panel['date'].max().date()} ({len(panel)} rows)")
    rebuild_db_table()
    return 0


def run_backfill(start: date) -> int:
    """Walk every Friday from `start` to today; cache-first, resumable."""
    sess, tokens = _new_session()
    # first Friday on/after start
    d = start + timedelta(days=(4 - start.weekday()) % 7)
    fridays = []
    while d <= date.today():
        fridays.append(d)
        d += timedelta(days=7)
    fridays.append(date.today())  # catch the partial current week

    print(f"Backfill: {len(fridays)} weekly requests from {fridays[0]} to {fridays[-1]}")
    panel = load_panel()
    pending: list[pd.DataFrame] = []
    failures = 0
    for i, fri in enumerate(fridays, 1):
        try:
            df = fetch_week(sess, tokens, fri)
            if df.empty:
                print(f"  [{i}/{len(fridays)}] {fri}: 0 rows even after holiday fallback")
            else:
                pending.append(df)
        except requests.RequestException as e:
            failures += 1
            print(f"  [{i}/{len(fridays)}] {fri}: FETCH FAILED ({e}) — skipped")
            try:  # token refresh in case the session went stale
                sess, tokens = _new_session()
            except requests.RequestException:
                pass
        if pending and (i % 10 == 0 or i == len(fridays)):
            panel = merge_and_save(panel, pd.concat(pending, ignore_index=True))
            pending = []
            print(f"  [{i}/{len(fridays)}] checkpoint: panel {len(panel)} rows, "
                  f"latest {panel['date'].max().date()}")

    if panel.empty:
        print("BACKFILL FAILED: no data collected at all")
        return 1
    rebuild_db_table()
    print(f"Backfill complete: {failures} failed week(s) out of {len(fridays)}")
    return 0 if failures < len(fridays) * 0.2 else 1


def run_check() -> int:
    panel = load_panel()
    if panel.empty:
        print("No panel yet — run a backfill first.")
        return 1
    print(f"Panel: {len(panel)} rows, {panel['date'].min().date()} -> {panel['date'].max().date()}")
    print(panel.groupby("variable")["date"].agg(["count", "min", "max"]).to_string())
    by_year = panel[panel["variable"] == "FOREIGN_EQUITY_NET_USD_MN"].copy()
    by_year["year"] = by_year["date"].dt.year
    print("\nEquity-net trading days per year:")
    print(by_year.groupby("year").size().to_string())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect daily foreign investor flows (NSDL India).")
    parser.add_argument("--backfill", metavar="YYYY-MM-DD", default=None,
                        help="weekly backfill from this date to today")
    parser.add_argument("--check", action="store_true", help="report panel coverage, no fetch")
    args = parser.parse_args()

    if args.check:
        return run_check()
    if args.backfill:
        return run_backfill(datetime.strptime(args.backfill, "%Y-%m-%d").date())
    return run_daily()


if __name__ == "__main__":
    sys.exit(main())
