#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/collect_weo_vintages.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/country_mapping.json
    ISO3 -> T2 country names (CHN -> ChinaA+ChinaH, USA -> U.S.+NASDAQ+US
    SmallCap, etc.)
- DBnomics API (network): https://api.db.nomics.world/v22/series/IMF/WEO:{vintage}
    Mirrors of every archived IMF WEO database vintage, 2008-04 .. 2025-04
    (the IMF's own bulk archive downloads are Akamai-blocked for scripts).
- IMF SDMX 3.0 API (network): https://api.imf.org/external/sdmx/3.0
    Dataflows IMF.RES/WEO_2025_OCT_VINTAGE (the Oct-2025 vintage, not yet on
    DBnomics) and IMF.RES/WEO (the live flow = the current vintage).
- Per-vintage JSON caches under
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/raw/weo_vintages/

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/weo_vintages.parquet
    Tidy panel: (vintage, vintage_date, country, target_year, variable,
    value, source). Variables: WEO_GDP_GROWTH_PCT (NGDP_RPCH),
    WEO_CPI_INFLATION_PCT (PCPIPCH). Target years bounded to
    [vintage_year-1, vintage_year+5].
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `weo_vintages` (idempotent rebuild from the parquet) and table
    `weo_revisions`: per (country, variable, target_year), the forecast
    change between consecutive vintages — the SURPRISE SURFACE.

VERSION: 1.0
LAST UPDATED: 2026-06-11
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 3)

DESCRIPTION:
PRD Priority 9 — the surprise-surface backfill. The forward-only insurance
(snapshot_vintages.py, first vintage 2026_06) can never recover the past;
this script does, from public WEO archives: what did the IMF forecast for
each country's GDP growth and inflation at every half-yearly vintage since
2008, and how did each forecast get revised vintage-over-vintage? Detector
D3 (revision-momentum quadrants, archetype A3) needs exactly this:
"forecast revised up + price flat" is the dislocation; the 2008+ revision
history is what makes a current revision's size interpretable (z-scorable).

Vintage label convention: "YYYY-04" (April) / "YYYY-10" (October), with
vintage_date = the 15th of that month (publication is mid-month). The live
WEO flow is labelled from today's date (Apr-Sep -> this April's vintage,
Oct-Dec -> this October's, Jan-Mar -> last October's).

DEPENDENCIES:
- requests, pandas, duckdb (project venv)

USAGE:
  python scripts/loop/collect_weo_vintages.py            # incremental (new vintages only)
  python scripts/loop/collect_weo_vintages.py --force    # re-fetch everything
  python scripts/loop/collect_weo_vintages.py --check    # verify tables

NOTES:
- Archived vintages are immutable: once in the parquet they are never
  re-fetched (unless --force). The CURRENT vintage is re-fetched every run
  (24h cache) because the live flow is replaced at each WEO release.
- DBnomics has no 2011-10 vintage (gap in their mirror) — logged, not fatal.
- Per-vintage isolation: one failed vintage never kills the run, but every
  failure is printed loudly and the vintage stays missing (FAIL-IS-FAIL).
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

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.loop.loopdb import loop_connection  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PANEL_PATH = BASE_DIR / "Data" / "work" / "loop" / "weo_vintages.parquet"
CACHE_DIR = BASE_DIR / "Data" / "raw" / "weo_vintages"
MAPPING_PATH = BASE_DIR / "config" / "country_mapping.json"

DBNOMICS_BASE = "https://api.db.nomics.world/v22"
SDMX_BASE = "https://api.imf.org/external/sdmx/3.0"

SUBJECTS = {
    "NGDP_RPCH": "WEO_GDP_GROWTH_PCT",
    "PCPIPCH": "WEO_CPI_INFLATION_PCT",
}
YEAR_BACK = 1    # keep target years from vintage_year-1 ...
YEAR_FWD = 5     # ... to vintage_year+5

HEADERS = {"User-Agent": "ASADO-research/1.0 (macro panel; contact: local)"}

# config/country_mapping.json carries 43 names; loop tables stay confined to
# the 34-country T2 universe (house rule: exact T2 names, nothing else).
T2_UNIVERSE = {
    "Australia", "Brazil", "Canada", "Chile", "ChinaA", "ChinaH", "Denmark",
    "France", "Germany", "Hong Kong", "India", "Indonesia", "Italy", "Japan",
    "Korea", "Malaysia", "Mexico", "NASDAQ", "Netherlands", "Philippines",
    "Poland", "Saudi Arabia", "Singapore", "South Africa", "Spain", "Sweden",
    "Switzerland", "Taiwan", "Thailand", "Turkey", "U.K.", "U.S.",
    "US SmallCap", "Vietnam",
}


def log(msg: str) -> None:
    print(f"[weo_vintages] {msg}", flush=True)


def iso3_map() -> dict[str, list[str]]:
    cfg = json.loads(MAPPING_PATH.read_text())
    out: dict[str, list[str]] = {}
    for t2_name, codes in cfg["countries"].items():
        if t2_name in T2_UNIVERSE:
            out.setdefault(codes["iso3"], []).append(t2_name)
    return out


def vintage_date(vintage: str) -> pd.Timestamp:
    y, m = vintage.split("-")
    return pd.Timestamp(int(y), int(m), 15)


def current_vintage_label(today: pd.Timestamp | None = None) -> str:
    t = today or pd.Timestamp.now()
    if 4 <= t.month <= 9:
        return f"{t.year}-04"
    if t.month >= 10:
        return f"{t.year}-10"
    return f"{t.year - 1}-10"


def cached_get(url: str, cache_name: str, max_age_h: float, force: bool) -> dict | None:
    """GET with on-disk JSON cache. Returns None on failure (caller logs)."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache = CACHE_DIR / cache_name
    if not force and cache.exists():
        age_h = (time.time() - cache.stat().st_mtime) / 3600
        if age_h < max_age_h:
            return json.loads(cache.read_text())
    try:
        r = requests.get(url, headers=HEADERS, timeout=120)
        if r.status_code != 200:
            log(f"  HTTP {r.status_code} for {url[:120]}")
            return None
        data = r.json()
        cache.write_text(json.dumps(data))
        return data
    except Exception as e:
        log(f"  fetch error: {e}")
        return None


# ── DBnomics (archived vintages, 2008-04 .. 2025-04) ───────────────────────

def dbnomics_vintage_list() -> list[str]:
    data = cached_get(f"{DBNOMICS_BASE}/providers/IMF", "dbnomics_provider_imf.json",
                      max_age_h=24, force=False)
    if not data:
        return []
    out: list[str] = []

    def walk(node):
        if isinstance(node, list):
            for x in node:
                walk(x)
        elif isinstance(node, dict):
            code = node.get("code")
            if code and isinstance(code, str) and code.startswith("WEO:") and "children" not in node:
                out.append(code.split(":", 1)[1])
            walk(node.get("children", []))

    walk(data.get("category_tree", []))
    return sorted(set(out))


def fetch_dbnomics_vintage(vintage: str, iso3s: list[str], force: bool) -> pd.DataFrame:
    dims = json.dumps({"weo-country": iso3s, "weo-subject": list(SUBJECTS)})
    url = (f"{DBNOMICS_BASE}/series/IMF/WEO%3A{vintage}"
           f"?dimensions={requests.utils.quote(dims)}&observations=1&limit=1000")
    data = cached_get(url, f"dbnomics_{vintage}.json", max_age_h=24 * 365 * 10, force=force)
    if not data:
        return pd.DataFrame()
    docs = data.get("series", {}).get("docs", [])
    rows = []
    for s in docs:
        parts = s["series_code"].split(".")
        if len(parts) < 2:
            continue
        iso3, subject = parts[0], parts[1]
        if subject not in SUBJECTS:
            continue
        for period, value in zip(s.get("period", []), s.get("value", [])):
            if value is None or value == "NA":
                continue
            try:
                rows.append((iso3, subject, int(period), float(value)))
            except (TypeError, ValueError):
                continue
    return pd.DataFrame(rows, columns=["iso3", "subject", "target_year", "value"])


# ── IMF SDMX 3.0 (2025-10 vintage + the live/current vintage) ──────────────

def fetch_sdmx_vintage(flow: str, vintage: str, iso3s: list[str], force: bool,
                       max_age_h: float) -> pd.DataFrame:
    key = "+".join(iso3s) + "." + "+".join(SUBJECTS)
    url = (f"{SDMX_BASE}/data/dataflow/IMF.RES/{flow}/+/{key}"
           f"?dimensionAtObservation=TIME_PERIOD&attributes=dsd&measures=all")
    data = cached_get(url, f"sdmx_{flow}.json", max_age_h=max_age_h, force=force)
    if not data:
        return pd.DataFrame()
    try:
        structs = data["data"]["structures"][0]
        series_dims = structs["dimensions"]["series"]
        time_vals = structs["dimensions"]["observation"][0]["values"]
        dim_ids = [d["id"] for d in series_dims]
        i_ctry = dim_ids.index("COUNTRY")
        i_subj = dim_ids.index("INDICATOR")
        rows = []
        for sk, sv in data["data"]["dataSets"][0].get("series", {}).items():
            idxs = [int(x) for x in sk.split(":")]
            iso3 = series_dims[i_ctry]["values"][idxs[i_ctry]]["id"]
            subject = series_dims[i_subj]["values"][idxs[i_subj]]["id"]
            if subject not in SUBJECTS:
                continue
            for ok, ov in sv.get("observations", {}).items():
                period = time_vals[int(ok)].get("value", "")
                val = ov[0] if ov else None
                if val in (None, "", "NA"):
                    continue
                try:
                    rows.append((iso3, subject, int(period), float(val)))
                except (TypeError, ValueError):
                    continue
        return pd.DataFrame(rows, columns=["iso3", "subject", "target_year", "value"])
    except (KeyError, IndexError, ValueError) as e:
        log(f"  SDMX parse error for {flow}: {e}")
        return pd.DataFrame()


# ── Assembly ────────────────────────────────────────────────────────────────

def tidy_vintage(raw: pd.DataFrame, vintage: str, source: str,
                 i2t: dict[str, list[str]]) -> pd.DataFrame:
    if raw.empty:
        return raw
    vy = int(vintage.split("-")[0])
    raw = raw[(raw["target_year"] >= vy - YEAR_BACK) & (raw["target_year"] <= vy + YEAR_FWD)]
    rows = []
    for iso3, subject, ty, val in raw.itertuples(index=False):
        for t2 in i2t.get(iso3, []):
            rows.append({
                "vintage": vintage, "vintage_date": vintage_date(vintage),
                "country": t2, "target_year": ty,
                "variable": SUBJECTS[subject], "value": val, "source": source,
            })
    return pd.DataFrame(rows)


def build(force: bool) -> pd.DataFrame:
    i2t = iso3_map()
    iso3s = sorted(i2t)
    existing = (pd.read_parquet(PANEL_PATH) if PANEL_PATH.exists() and not force
                else pd.DataFrame())
    have = set(existing["vintage"].unique()) if not existing.empty else set()
    cur_label = current_vintage_label()

    frames = [existing] if not existing.empty else []

    # 1. DBnomics archive
    vintages = dbnomics_vintage_list()
    if not vintages:
        log("WARNING: DBnomics vintage list unavailable")
    for v in vintages:
        if v in have:
            continue
        raw = fetch_dbnomics_vintage(v, iso3s, force)
        df = tidy_vintage(raw, v, "dbnomics_weo", i2t)
        if df.empty:
            log(f"  {v}: NO DATA (vintage stays missing)")
            continue
        frames.append(df)
        log(f"  {v}: {len(df):,} rows, {df['country'].nunique()} countries")

    # 2. SDMX: Oct-2025 vintage (immutable) + live flow (current vintage)
    sdmx_jobs = [("WEO_2025_OCT_VINTAGE", "2025-10", 24 * 365 * 10)]
    sdmx_jobs.append(("WEO", cur_label, 24))
    for flow, label, max_age in sdmx_jobs:
        if label in have and flow != "WEO":
            continue
        raw = fetch_sdmx_vintage(flow, label, iso3s, force, max_age)
        df = tidy_vintage(raw, label, f"imf_sdmx_{flow.lower()}", i2t)
        if df.empty:
            log(f"  {label} ({flow}): NO DATA")
            continue
        if not existing.empty:
            frames = [f[~((f["vintage"] == label))] for f in frames]
        frames.append(df)
        log(f"  {label} ({flow}): {len(df):,} rows, {df['country'].nunique()} countries")

    if not frames:
        raise RuntimeError("no WEO vintage data at all — refusing to write")
    out = pd.concat(frames, ignore_index=True)
    out = out.drop_duplicates(subset=["vintage", "country", "target_year", "variable"], keep="last")
    out = out.sort_values(["vintage", "variable", "country", "target_year"]).reset_index(drop=True)
    return out


def save(out: pd.DataFrame) -> None:
    PANEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PANEL_PATH.with_suffix(".parquet.tmp")
    out.to_parquet(tmp, index=False)
    tmp.replace(PANEL_PATH)
    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS weo_vintages")
        con.execute(
            f"""
            CREATE TABLE weo_vintages AS
            SELECT vintage, CAST(vintage_date AS DATE) AS vintage_date, country,
                   CAST(target_year AS INTEGER) AS target_year, variable, value, source
            FROM read_parquet('{PANEL_PATH}')
            """
        )
        # Surprise surface: forecast change between CONSECUTIVE vintages for
        # the same (country, variable, target_year).
        con.execute("DROP TABLE IF EXISTS weo_revisions")
        con.execute(
            """
            CREATE TABLE weo_revisions AS
            WITH ordered AS (
              SELECT *,
                     LAG(value) OVER w AS prev_value,
                     LAG(vintage) OVER w AS prev_vintage
              FROM weo_vintages
              WINDOW w AS (PARTITION BY country, variable, target_year ORDER BY vintage)
            )
            SELECT vintage, vintage_date, country, target_year, variable,
                   value, prev_vintage, prev_value,
                   value - prev_value AS revision
            FROM ordered
            WHERE prev_value IS NOT NULL
            """
        )
        n_v, n_r = (con.execute("SELECT COUNT(*) FROM weo_vintages").fetchone()[0],
                    con.execute("SELECT COUNT(*) FROM weo_revisions").fetchone()[0])
        if not n_v or not n_r:
            raise RuntimeError("weo tables rebuilt empty — refusing to continue")
        log(f"weo_vintages: {n_v:,} rows | weo_revisions: {n_r:,} rows")
    finally:
        con.close()


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        vs = con.execute(
            "SELECT vintage, COUNT(DISTINCT country) AS nc, COUNT(*) AS n "
            "FROM weo_vintages GROUP BY 1 ORDER BY 1").fetchall()
        print(f"{len(vs)} vintages:")
        for v, nc, n in vs[:3] + vs[-3:]:
            print(f"  {v}: {nc} countries, {n} rows")
        latest = con.execute(
            """
            SELECT country, revision FROM weo_revisions
            WHERE variable = 'WEO_GDP_GROWTH_PCT'
              AND vintage = (SELECT MAX(vintage) FROM weo_revisions)
              AND target_year = CAST(strftime(CURRENT_DATE, '%Y') AS INTEGER)
            ORDER BY revision LIMIT 5
            """
        ).fetchall()
        print("biggest current-year GDP downgrades, latest vintage:")
        for c, r in latest:
            print(f"  {c:<14} {r:+.2f}pp")
        ok = len(vs) >= 30
    finally:
        con.close()
    print("CHECK", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="WEO vintage backfill + surprise surface (PRD P9).")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        return check()
    started = datetime.now()
    out = build(args.force)
    save(out)
    log(f"done in {(datetime.now() - started).total_seconds():.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
