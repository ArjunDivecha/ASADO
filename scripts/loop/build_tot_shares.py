#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: build_tot_shares.py
=============================================================================

INPUT FILES:
- UN Comtrade public preview API (keyless, free):
  https://comtradeapi.un.org/public/v1/preview/C/A/HS
  Annual goods trade by HS 2-digit chapter, reporter -> World, both flows.
  27 commodity chapters + TOTAL pulled per reporter in ONE call.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/tot_trade_shares.parquet
  Previous run's table (rows preserved for any reporter that fails tonight).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
  Table `tot_trade_shares(country, category, export_share, import_share,
  net_share, export_year, import_year, fetched_ts)` - one row per
  (country, commodity category). Shares are DECIMALS of total goods trade.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/tot_trade_shares.parquet
  Same data as parquet (survives loop-DB accidents).

VERSION: 2.0  (v1 was WDI 4-section shares; this is the PRD's D1 v1 upgrade)
LAST UPDATED: 2026-06-11
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop)

DESCRIPTION:
Commodity trade-composition shares for the D1 terms-of-trade impulse
detector. v2 sources EVERY country (including Taiwan, reporter 490 = "Other
Asia, nes") from UN Comtrade HS 2-digit chapters and maps them onto SIX Pink
Sheet aggregate indices - adding precious metals and fertilizers, which the
old WDI sections missed entirely (gold matters for South Africa/Australia,
fertilizer for Brazil/India imports):

    fuel        HS 27                       -> WB_CMDTY_IENERGY
    ores_metals HS 26,72,74,75,76,78,79,80  -> WB_CMDTY_IMETMIN
    precious    HS 71                       -> WB_CMDTY_IPRECIOUSMET
    food        HS 02,03,04,07,08,09,10,11,12,15,17 -> WB_CMDTY_IFOOD
    agri_raw    HS 40,41,44,47,52           -> WB_CMDTY_IRAW_MATERIAL
    fertilizer  HS 31                       -> WB_CMDTY_IFERTILIZERS

For each reporter the latest year with a usable TOTAL on both flows is kept
(walks back up to 5 years). Shares are slow-moving structural quantities;
the static-latest-year approximation is flagged in every D1 row. In plain
terms: we ask the UN's trade database what slice of each country's exports
and imports is oil, metals, gold, food, raw materials and fertilizer, then
D1 multiplies those slices by what commodity prices just did.

RESILIENCE (repo pattern, per CLAUDE.md): one reporter failing keeps that
country's PREVIOUS rows and is logged loudly; it never breaks the run.
A full-API failure leaves the existing table untouched and exits 1.

DEPENDENCIES:
- requests, duckdb, pandas (project venv)

USAGE:
 python scripts/loop/build_tot_shares.py            # fetch + write (skips if <7d old)
 python scripts/loop/build_tot_shares.py --force    # re-pull regardless of freshness
 python scripts/loop/build_tot_shares.py --check    # show current table
=============================================================================
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.loop.loopdb import LOOP_DIR, T2_UNIVERSE, loop_connection

PARQUET_OUT = LOOP_DIR / "tot_trade_shares.parquet"

COMTRADE_PREVIEW = "https://comtradeapi.un.org/public/v1/preview/C/A/HS"
SLEEP_BETWEEN_CALLS = 3.0   # keyless preview endpoint - be polite
RATE_LIMIT_BACKOFF_S = 65   # on HTTP 429: wait out the window, retry same year
RATE_LIMIT_RETRIES = 2

# HS 2-digit chapter -> category (Pink Sheet aggregate mapping in D1_INDEX_MAP)
CATEGORY_CHAPTERS = {
    "fuel": ["27"],
    "ores_metals": ["26", "72", "74", "75", "76", "78", "79", "80"],
    "precious": ["71"],
    "food": ["02", "03", "04", "07", "08", "09", "10", "11", "12", "15", "17"],
    "agri_raw": ["40", "41", "44", "47", "52"],
    "fertilizer": ["31"],
}
ALL_CHAPTERS = sorted({ch for chs in CATEGORY_CHAPTERS.values() for ch in chs})

# Comtrade reporter codes, verified live against Reporters.json 2026-06-11.
# Note the non-M49 quirks: France 251, India 699, Switzerland 757, USA 842,
# Taiwan 490 ("Other Asia, nes" - the Comtrade convention for Taiwan).
# Multi-assignment per CLAUDE.md: China -> ChinaA+ChinaH; USA -> U.S.,
# NASDAQ, US SmallCap.
REPORTERS: dict[int, list[str]] = {
    36: ["Australia"], 76: ["Brazil"], 124: ["Canada"], 152: ["Chile"],
    156: ["ChinaA", "ChinaH"], 208: ["Denmark"], 251: ["France"],
    276: ["Germany"], 344: ["Hong Kong"], 699: ["India"], 360: ["Indonesia"],
    380: ["Italy"], 392: ["Japan"], 410: ["Korea"], 458: ["Malaysia"],
    484: ["Mexico"], 528: ["Netherlands"], 608: ["Philippines"],
    616: ["Poland"], 682: ["Saudi Arabia"], 702: ["Singapore"],
    710: ["South Africa"], 724: ["Spain"], 752: ["Sweden"],
    757: ["Switzerland"], 764: ["Thailand"], 792: ["Turkey"], 826: ["U.K."],
    842: ["U.S.", "NASDAQ", "US SmallCap"], 704: ["Vietnam"], 490: ["Taiwan"],
}


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} [tot_shares] {msg}", flush=True)


def fetch_reporter(code: int) -> tuple[dict[str, dict[str, float]], int] | None:
    """One Comtrade preview call per reporter: all chapters + TOTAL, both
    flows, reporter->World. Walks back up to 5 years until TOTALs exist on
    both flows. Returns ({chapter: {'X': usd, 'M': usd}}, year) or None."""
    cmd = ",".join(["TOTAL"] + ALL_CHAPTERS)
    for year in range(datetime.now().year - 1, datetime.now().year - 6, -1):
        # Server-side filters matter: the preview endpoint truncates at 500
        # rows, and large traders' mode-of-transport breakdowns overflow that,
        # cutting off the TOTAL rows (Germany/France/U.K. failures, 2026-06-11).
        params = {
            "reporterCode": code, "period": year, "partnerCode": 0,
            "partner2Code": 0, "motCode": 0, "customsCode": "C00",
            "cmdCode": cmd, "flowCode": "X,M",
        }
        data = None
        for attempt in range(RATE_LIMIT_RETRIES + 1):
            try:
                r = requests.get(COMTRADE_PREVIEW, params=params, timeout=90)
                if r.status_code == 429 and attempt < RATE_LIMIT_RETRIES:
                    log(f"  reporter {code} year {year}: 429 rate-limited, "
                        f"backing off {RATE_LIMIT_BACKOFF_S}s")
                    time.sleep(RATE_LIMIT_BACKOFF_S)
                    continue
                r.raise_for_status()
                data = r.json().get("data", [])
            except Exception as exc:
                log(f"  reporter {code} year {year}: {exc!r}")
            break
        if data is None:
            continue
        # Keep only the all-modes / all-customs / world aggregate rows.
        vals: dict[str, dict[str, float]] = {}
        for row in data:
            if (row.get("partnerCode") == 0 and row.get("partner2Code") in (0, None)
                    and str(row.get("motCode", "0")) == "0"
                    and str(row.get("customsCode", "C00")) in ("C00", "0")):
                ch = str(row.get("cmdCode"))
                fl = str(row.get("flowCode"))
                if fl in ("X", "M"):
                    vals.setdefault(ch, {})[fl] = float(row.get("primaryValue") or 0.0)
        tot = vals.get("TOTAL", {})
        if tot.get("X") and tot.get("M"):
            return vals, year
    return None


def assemble_rows(code: int, t2_names: list[str]) -> list[dict]:
    fetched = fetch_reporter(code)
    if fetched is None:
        return []
    vals, year = fetched
    tot_x = vals["TOTAL"]["X"]
    tot_m = vals["TOTAL"]["M"]
    ts = datetime.now().isoformat(timespec="seconds")
    rows = []
    for cat, chapters in CATEGORY_CHAPTERS.items():
        e = sum(vals.get(ch, {}).get("X", 0.0) for ch in chapters)
        i = sum(vals.get(ch, {}).get("M", 0.0) for ch in chapters)
        e_sh, i_sh = e / tot_x, i / tot_m
        for t2_name in t2_names:
            rows.append({
                "country": t2_name, "category": cat,
                "export_share": round(e_sh, 6), "import_share": round(i_sh, 6),
                "net_share": round(e_sh - i_sh, 6),
                "export_year": year, "import_year": year, "fetched_ts": ts,
            })
    fuel_x = sum(vals.get(ch, {}).get("X", 0.0) for ch in CATEGORY_CHAPTERS["fuel"]) / tot_x
    met_x = sum(vals.get(ch, {}).get("X", 0.0) for ch in CATEGORY_CHAPTERS["ores_metals"]) / tot_x
    log(f"  {'/'.join(t2_names):<24} year {year}: fuel_x={fuel_x:.1%}, metals_x={met_x:.1%}")
    return rows


REFRESH_DAYS = 7  # shares are annual-structural; weekly refresh is plenty


def build(force: bool = False) -> int:
    prev = pd.read_parquet(PARQUET_OUT) if PARQUET_OUT.exists() else pd.DataFrame()

    # Freshness gate (repo cache pattern): Comtrade preview is rate-limited,
    # and these shares change once a year. Skip if the table is recent.
    if not force and not prev.empty and "fetched_ts" in prev.columns:
        age_days = (datetime.now() - pd.to_datetime(prev["fetched_ts"]).max()).days
        if age_days < REFRESH_DAYS and prev["country"].nunique() >= 34:
            log(f"table is {age_days}d old with full coverage (< {REFRESH_DAYS}d) - skipping pull "
                "(--force to override)")
            return 0

    log(f"fetching Comtrade HS-chapter shares for {len(REPORTERS)} reporters ...")

    rows: list[dict] = []
    failed_countries: list[str] = []
    for code, t2_names in REPORTERS.items():
        got = assemble_rows(code, t2_names)
        if got:
            rows.extend(got)
        else:
            failed_countries.extend(t2_names)
            log(f"  FAILED reporter {code} ({'/'.join(t2_names)}) - keeping previous rows")
        time.sleep(SLEEP_BETWEEN_CALLS)

    if not rows:
        log("ERROR: Comtrade returned nothing for ANY reporter - existing table untouched (FAIL-IS-FAIL)")
        return 1

    df = pd.DataFrame(rows)
    # Per-source resilience: failed reporters keep their previous rows.
    if failed_countries and not prev.empty:
        keep = prev[prev["country"].isin(failed_countries)]
        if not keep.empty:
            log(f"  preserved previous rows for: {', '.join(sorted(keep['country'].unique()))}")
            df = pd.concat([df, keep], ignore_index=True)

    covered = sorted(df["country"].unique())
    missing = sorted(set(T2_UNIVERSE) - set(covered))
    log(f"coverage: {len(covered)}/34 countries"
        + (f" - MISSING (loud): {', '.join(missing)}" if missing else ""))

    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS tot_trade_shares")
        con.execute("CREATE TABLE tot_trade_shares AS SELECT * FROM df")
        con.execute(f"COPY tot_trade_shares TO '{PARQUET_OUT}' (FORMAT PARQUET)")
    finally:
        con.close()
    log(f"tot_trade_shares: {len(df)} rows written; parquet: {PARQUET_OUT}")
    return 0 if not missing else 1


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        df = con.execute(
            "SELECT * FROM tot_trade_shares ORDER BY country, category"
        ).fetchdf()
        piv = df.pivot_table(index="country", columns="category", values="net_share")
        print(piv.round(3).to_string())
        print(f"\n{df['country'].nunique()}/34 countries; "
              f"{df['category'].nunique()} categories; data years "
              f"{int(df['export_year'].min())}-{int(df['export_year'].max())}")
        return 0
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Comtrade HS-chapter commodity trade shares for detector D1 (v2).")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--force", action="store_true",
                        help=f"re-pull even if table is fresher than {REFRESH_DAYS}d")
    args = parser.parse_args()
    return check() if args.check else build(force=args.force)


if __name__ == "__main__":
    sys.exit(main())
