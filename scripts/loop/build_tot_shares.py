#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: build_tot_shares.py
=============================================================================

INPUT FILES:
- World Bank WDI API (via wbgapi, free, no key) - 8 indicators:
    TX.VAL.FUEL.ZS.UN  Fuel exports (% of merchandise exports)
    TX.VAL.MMTL.ZS.UN  Ores and metals exports (%)
    TX.VAL.FOOD.ZS.UN  Food exports (%)
    TX.VAL.AGRI.ZS.UN  Agricultural raw materials exports (%)
    TM.VAL.FUEL.ZS.UN / TM.VAL.MMTL.ZS.UN / TM.VAL.FOOD.ZS.UN /
    TM.VAL.AGRI.ZS.UN  The matching import shares.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/country_mapping.json
  T2 name -> World Bank ISO3 code.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
  Table `tot_trade_shares(country, category, export_share, import_share,
  net_share, export_year, import_year, fetched_ts)` - one row per
  (country, commodity category). Shares are DECIMALS of merchandise trade.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/tot_trade_shares.parquet
  Same data as parquet (survives loop-DB accidents).

VERSION: 1.0
LAST UPDATED: 2026-06-10
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop)

DESCRIPTION:
Commodity trade-composition shares for the D1 terms-of-trade impulse
detector. The PRD's correction stands: bilateral IMTS partner weights give
WHO a country trades with, not WHAT it exports - commodity composition
needs product-level shares. UN Comtrade SITC-2 is the v1 plan (Phase 3);
this v0.5 uses the World Bank WDI section-level shares (fuel / ores&metals /
food / agricultural raw materials, as % of merchandise exports and imports),
which map 1:1 onto four Pink Sheet aggregate indices already in the
warehouse:

    fuel          -> WB_CMDTY_IENERGY        (energy index)
    ores_metals   -> WB_CMDTY_IMETMIN        (metals & minerals index)
    food          -> WB_CMDTY_IFOOD          (food index)
    agri_raw      -> WB_CMDTY_IRAW_MATERIAL  (raw materials index)

For each country the LATEST available year per indicator is kept (years can
differ across indicators; both are recorded). Shares are slow-moving
structural quantities - using the latest year across history is the same
honest approximation as the graph edge weights, and is flagged as such
wherever D1 output is consumed.

KNOWN COVERAGE GAP (reported loudly, never silently dropped): the World
Bank has NO data for Taiwan. D1 cannot fire for Taiwan until Comtrade
lands. China shares apply to both ChinaA and ChinaH; U.S. shares apply to
U.S., NASDAQ and US SmallCap (CLAUDE.md mapping rules).

DEPENDENCIES:
- wbgapi, duckdb, pandas (project venv)

USAGE:
 python scripts/loop/build_tot_shares.py            # fetch + write
 python scripts/loop/build_tot_shares.py --check    # show current table
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.loop.loopdb import COUNTRY_MAPPING, LOOP_DIR, T2_UNIVERSE, loop_connection

PARQUET_OUT = LOOP_DIR / "tot_trade_shares.parquet"

CATEGORIES = {
    "fuel": ("TX.VAL.FUEL.ZS.UN", "TM.VAL.FUEL.ZS.UN"),
    "ores_metals": ("TX.VAL.MMTL.ZS.UN", "TM.VAL.MMTL.ZS.UN"),
    "food": ("TX.VAL.FOOD.ZS.UN", "TM.VAL.FOOD.ZS.UN"),
    "agri_raw": ("TX.VAL.AGRI.ZS.UN", "TM.VAL.AGRI.ZS.UN"),
}

# WB ISO3 -> list of T2 names (multi-assignment per CLAUDE.md rules)
def wb_to_t2() -> dict[str, list[str]]:
    mapping = json.loads(COUNTRY_MAPPING.read_text())["countries"]
    out: dict[str, list[str]] = {}
    for t2_name, codes in mapping.items():
        if t2_name not in T2_UNIVERSE:
            continue
        wb = codes.get("wb")
        if wb:
            out.setdefault(wb, []).append(t2_name)
    return out


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} [tot_shares] {msg}", flush=True)


def fetch_indicator(indicator: str, iso3_codes: list[str]) -> pd.DataFrame:
    """Latest non-null value per economy for one WDI indicator.
    Returns (economy, value, year). Raises on total failure (FAIL-IS-FAIL)."""
    import wbgapi as wb

    df = wb.data.DataFrame(indicator, economy=iso3_codes, mrnev=1,
                           numericTimeKeys=True, labels=False, timeColumns=True)
    # mrnev=1 -> one column with the most recent non-empty value + a time col
    df = df.reset_index()
    val_col = indicator
    time_col = f"{indicator}:T"
    if val_col not in df.columns or time_col not in df.columns:
        raise RuntimeError(f"unexpected wbgapi shape for {indicator}: {list(df.columns)}")
    out = df.rename(columns={"economy": "wb", val_col: "value", time_col: "year"})
    return out[["wb", "value", "year"]].dropna(subset=["value"])


def build() -> int:
    iso_map = wb_to_t2()
    iso3_codes = sorted(iso_map)
    log(f"fetching 8 WDI indicators for {len(iso3_codes)} WB economies ...")

    fetched: dict[tuple[str, str], pd.DataFrame] = {}
    failures = []
    for cat, (exp_ind, imp_ind) in CATEGORIES.items():
        for side, ind in (("export", exp_ind), ("import", imp_ind)):
            try:
                fetched[(cat, side)] = fetch_indicator(ind, iso3_codes)
                log(f"  {cat:<12} {side:<6} {ind}: {len(fetched[(cat, side)])} economies")
            except Exception as exc:
                failures.append(f"{ind} ({cat}/{side}): {exc!r}")
                log(f"  {cat:<12} {side:<6} {ind} FAILED: {exc!r}")

    if failures:
        # No partial overwrites: D1 needs export AND import sides coherent.
        log(f"{len(failures)} indicator fetch(es) FAILED - keeping any existing table unchanged")
        for f in failures:
            log(f"  FAILED: {f}")
        return 1

    ts = datetime.now().isoformat(timespec="seconds")
    rows = []
    for wb_code, t2_names in iso_map.items():
        for cat in CATEGORIES:
            exp = fetched[(cat, "export")]
            imp = fetched[(cat, "import")]
            e = exp[exp["wb"] == wb_code]
            i = imp[imp["wb"] == wb_code]
            if e.empty and i.empty:
                continue
            for t2_name in t2_names:
                rows.append({
                    "country": t2_name,
                    "category": cat,
                    "export_share": round(float(e["value"].iloc[0]) / 100.0, 6) if not e.empty else None,
                    "import_share": round(float(i["value"].iloc[0]) / 100.0, 6) if not i.empty else None,
                    "net_share": round((float(e["value"].iloc[0]) if not e.empty else 0.0) / 100.0
                                       - (float(i["value"].iloc[0]) if not i.empty else 0.0) / 100.0, 6),
                    "export_year": int(e["year"].iloc[0]) if not e.empty else None,
                    "import_year": int(i["year"].iloc[0]) if not i.empty else None,
                    "fetched_ts": ts,
                })
    df = pd.DataFrame(rows)
    if df.empty:
        log("ERROR: zero rows assembled - refusing to overwrite (FAIL-IS-FAIL)")
        return 1

    covered = sorted(df["country"].unique())
    missing = sorted(set(T2_UNIVERSE) - set(covered))
    log(f"coverage: {len(covered)}/34 countries"
        + (f" - MISSING (loud, structural): {', '.join(missing)}" if missing else ""))

    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS tot_trade_shares")
        con.execute("CREATE TABLE tot_trade_shares AS SELECT * FROM df")
        con.execute(f"COPY tot_trade_shares TO '{PARQUET_OUT}' (FORMAT PARQUET)")
    finally:
        con.close()
    log(f"tot_trade_shares: {len(df)} rows written; parquet: {PARQUET_OUT}")
    return 0


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        df = con.execute(
            "SELECT * FROM tot_trade_shares ORDER BY country, category"
        ).fetchdf()
        piv = df.pivot_table(index="country", columns="category", values="net_share")
        print(piv.round(3).to_string())
        print(f"\n{df['country'].nunique()}/34 countries; data years "
              f"{int(df['export_year'].min())}-{int(df['export_year'].max())}")
        return 0
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="WDI commodity trade-composition shares for detector D1.")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    return check() if args.check else build()


if __name__ == "__main__":
    sys.exit(main())
