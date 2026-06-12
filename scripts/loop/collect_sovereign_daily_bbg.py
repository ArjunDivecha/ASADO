#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/collect_sovereign_daily_bbg.py
=============================================================================

INPUT FILES:
- Bloomberg Terminal via OpusBloomberg (network source, no local input file)
    Sovereign CDS (5Y + 1Y) + generic government bond yields (10Y + 2Y), daily.
    Ticker map copied from scripts/collect_bloomberg.py COUNTRY_TICKERS
    (verified against the Terminal 2026-04-12, re-audited 2026-06-11):
    20 CDS series ("[ISSUER] CDS USD SR 5Y Corp" + D14 variants), 1Y CDS
    derived by tenor substitution (verified live 2026-06-12), 32 bond_10y,
    26 bond_2y tickers.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/sovereign_daily.parquet
    Tidy panel (date, country, value, variable, source='bloomberg'):
      SOV_CDS_5Y_BP      5Y CDS spread, basis points (19 countries, 2005+)
      SOV_CDS_1Y_BP      1Y CDS spread, bp (v1.1) — with 5Y gives the CDS
                         curve slope; 1Y > 5Y (inversion) = imminent-distress
      SOV_10Y_YIELD_PCT  generic 10Y govt yield, percent (31 countries)
      SOV_2Y_YIELD_PCT   generic 2Y govt yield, pct (v1.1) — with 10Y gives
                         the daily 2s10s curve slope per country
    New rows win on (date, country, variable). This script does NOT touch
    DuckDB (no duckdb in the OpusBloomberg env) — see
    scripts/loop/load_sovereign_daily.py for the loop-DB table rebuild.

VERSION: 1.1
LAST UPDATED: 2026-06-12
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 3)

DESCRIPTION:
PRD Priority 8 — "Daily CDS + 10Y for 34 sovereigns; upgrades D4 from
partial to full." The warehouse's CDS surface was monthly-only
(bloomberg_factors.BBG_CDS_5Y); D4 cross-asset incoherence needs daily.
The 10Y pull also repairs the t2_levels_daily staleness problem: Taiwan's
T2 10Y series died upstream in 2020-05, Philippines/Vietnam are stale —
this pull hits the generic govt tickers directly so D4's yield leg uses
live data wherever Bloomberg has it.

Coverage notes (structural, not bugs):
- No CDS ticker: Canada, Denmark, Germany, Hong Kong, India, NASDAQ,
  Netherlands, Singapore, Sweden, Switzerland, Taiwan, U.K., U.S.,
  US SmallCap (DM names with no liquid USD sovereign CDS, plus Taiwan).
  => 20 CDS series across 34 names (ChinaA/ChinaH share CHINAG).
- France/Italy/Poland/Spain/South Africa use ISDA-2014 (D14) contracts:
  history starts ~2014-09, the pre-2014 definition contracts are dead.
- ChinaA/ChinaH share CHINAG; U.S./NASDAQ/US SmallCap share USGG10YR.
- No 10Y ticker: Hong Kong, Vietnam (=> 32 of 34 covered).

DEPENDENCIES:
- OpusBloomberg conda env: blpapi, pandas, pyarrow (NOT the project venv)

USAGE:
  conda run -p "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv" \
      python scripts/loop/collect_sovereign_daily_bbg.py             # last 15 days
  ... collect_sovereign_daily_bbg.py --backfill                      # full 2005+ history

NOTES:
- Bloomberg Terminal must be logged in on the Parallels VM.
- Sanity guards: CDS must be in (0, 10000] bp, yields in (-5, 100] pct.
  Isolated bad prints are dropped and logged; if >5% of a series is out of
  range the run aborts and the parquet is left untouched (FAIL-IS-FAIL).
=============================================================================
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg")
from bbg import BBG, bloomberg_setup  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PANEL_PATH = BASE_DIR / "Data" / "work" / "loop" / "sovereign_daily.parquet"

HISTORY_START = "20050101"

# t2_name -> (cds_5y ticker | None, bond_10y (ticker, field) | None)
# Started from scripts/collect_bloomberg.py COUNTRY_TICKERS, then re-verified
# ticker-by-ticker against the Terminal on 2026-06-11. Corrections found:
#   - Chile CHILE10 invalid              -> CLGB10Y Index
#   - France/Italy/Poland/Spain/South Africa CDS need the ISDA-2014 (D14)
#     contract names (history starts ~2014-09)
#   - Malaysia/Philippines/Turkey/Saudi 10Y Index tickers invalid -> generic
#     Govt bonds (GT***10Y Govt) pulling YLD_YTM_MID, not PX_LAST (= price)
#   - Taiwan TAIBON10 invalid            -> TPGBTW10 Index (Tullett Prebon)
#   - BUG in the monthly map: GSAB10YR is SOUTH AFRICA's yield, but was
#     assigned to Saudi Arabia. Fixed here; monthly collector flagged in docs.
Y = "YLD_YTM_MID"   # field for GT***Y Govt generics (PX_LAST is price there)
TICKERS = {
    "Australia":    ("AUSTLA CDS USD SR 5Y Corp",      ("GACGB10 Index", "PX_LAST")),
    "Brazil":       ("BRAZIL CDS USD SR 5Y Corp",      ("GEBR10Y Index", "PX_LAST")),
    "Canada":       (None,                             ("GCAN10YR Index", "PX_LAST")),
    "Chile":        ("CHILE CDS USD SR 5Y Corp",       ("CLGB10Y Index", "PX_LAST")),
    "ChinaA":       ("CHINAG CDS USD SR 5Y Corp",      ("GCNY10YR Index", "PX_LAST")),
    "ChinaH":       ("CHINAG CDS USD SR 5Y Corp",      ("GCNY10YR Index", "PX_LAST")),
    "Denmark":      (None,                             ("GDGB10YR Index", "PX_LAST")),
    "France":       ("FRANCE CDS USD SR 5Y D14 Corp",  ("GFRN10 Index", "PX_LAST")),
    "Germany":      (None,                             ("GDBR10 Index", "PX_LAST")),
    "Hong Kong":    (None,                             None),
    "India":        (None,                             ("GIND10YR Index", "PX_LAST")),
    "Indonesia":    ("INDON CDS USD SR 5Y Corp",       ("GIDN10YR Index", "PX_LAST")),
    "Italy":        ("ITALY CDS USD SR 5Y D14 Corp",   ("GBTPGR10 Index", "PX_LAST")),
    "Japan":        ("JAPAN CDS USD SR 5Y Corp",       ("GJGB10 Index", "PX_LAST")),
    "Korea":        ("KOREA CDS USD SR 5Y Corp",       ("GVSK10YR Index", "PX_LAST")),
    "Malaysia":     ("MALAYS CDS USD SR 5Y Corp",      ("GTMYR10Y Govt", Y)),
    "Mexico":       ("MEXICO CDS USD SR 5Y Corp",      ("GMXN10YR Index", "PX_LAST")),
    "NASDAQ":       (None,                             ("USGG10YR Index", "PX_LAST")),
    "Netherlands":  (None,                             ("GNTH10YR Index", "PX_LAST")),
    "Philippines":  ("PHILIP CDS USD SR 5Y Corp",      ("GTPHP10Y Govt", Y)),
    "Poland":       ("POLAND CDS USD SR 5Y D14 Corp",  ("POGB10YR Index", "PX_LAST")),
    "Saudi Arabia": ("SAUDI CDS USD SR 5Y Corp",       ("GTSAR10Y Govt", Y)),
    "Singapore":    (None,                             ("MASB10Y Index", "PX_LAST")),
    "South Africa": ("REPSOU CDS USD SR 5Y D14 Corp",  ("GSAB10YR Index", "PX_LAST")),
    "Spain":        ("SPAIN CDS USD SR 5Y D14 Corp",   ("GSPG10YR Index", "PX_LAST")),
    "Sweden":       (None,                             ("GSGB10YR Index", "PX_LAST")),
    "Switzerland":  (None,                             ("GSWISS10 Index", "PX_LAST")),
    "Taiwan":       (None,                             ("TPGBTW10 Index", "PX_LAST")),
    "Thailand":     ("THAI CDS USD SR 5Y Corp",        ("GVTL10YR Index", "PX_LAST")),
    "Turkey":       ("TURKEY CDS USD SR 5Y Corp",      ("GTTRY10Y Govt", Y)),
    "U.K.":         (None,                             ("GUKG10 Index", "PX_LAST")),
    "U.S.":         (None,                             ("USGG10YR Index", "PX_LAST")),
    "US SmallCap":  (None,                             ("USGG10YR Index", "PX_LAST")),
    "Vietnam":      ("VIETNM CDS USD SR 5Y Corp",      None),
}

# t2_name -> 2Y generic govt yield (ticker, field). From the corrected monthly
# COUNTRY_TICKERS map (collect_bloomberg.py, re-audited 2026-06-11). Countries
# with no liquid 2Y generic: Chile, Hong Kong, Malaysia, Philippines,
# Saudi Arabia, Taiwan, Vietnam.
BOND_2Y = {
    "Australia":    ("GACGB2 Index", "PX_LAST"),
    "Brazil":       ("GTBRL2Y Govt", Y),   # GEBR2Y Index is dead (2026-06-12)
    "Canada":       ("GCAN2YR Index", "PX_LAST"),
    "ChinaA":       ("GCNY2YR Index", "PX_LAST"),
    "ChinaH":       ("GCNY2YR Index", "PX_LAST"),
    "Denmark":      ("GDGB2YR Index", "PX_LAST"),
    "France":       ("GFRN2 Index", "PX_LAST"),
    "Germany":      ("GDBR2 Index", "PX_LAST"),
    "India":        ("GIND2YR Index", "PX_LAST"),
    "Indonesia":    ("GIDN2YR Index", "PX_LAST"),
    "Italy":        ("GBTPGR2 Index", "PX_LAST"),
    "Japan":        ("GJGB2 Index", "PX_LAST"),
    "Korea":        ("GVSK2YR Index", "PX_LAST"),
    "Mexico":       ("GMXN02YR Index", "PX_LAST"),
    "NASDAQ":       ("USGG2YR Index", "PX_LAST"),
    "Netherlands":  ("GNTH2YR Index", "PX_LAST"),
    "Poland":       ("POGB2YR Index", "PX_LAST"),
    "Singapore":    ("MASB2Y Index", "PX_LAST"),
    "South Africa": ("GSAB2YR Index", "PX_LAST"),
    "Spain":        ("GSPG2YR Index", "PX_LAST"),
    "Sweden":       ("GSGB2YR Index", "PX_LAST"),
    "Switzerland":  ("GSWISS2 Index", "PX_LAST"),
    "Thailand":     ("GVTL2YR Index", "PX_LAST"),
    "Turkey":       ("GTTRY2Y Govt", Y),
    "U.K.":         ("GUKG2 Index", "PX_LAST"),
    "U.S.":         ("USGG2YR Index", "PX_LAST"),
    "US SmallCap":  ("USGG2YR Index", "PX_LAST"),
}


def cds_1y_ticker(cds_5y: str) -> str:
    """Derive the 1Y CDS contract from the 5Y name (same ISDA doc clause).
    Verified live 2026-06-12 for plain + D14 contracts."""
    return cds_5y.replace(" SR 5Y ", " SR 1Y ")


def hist_series(bbg: BBG, ticker: str, start: str, end: str, field: str = "PX_LAST") -> pd.Series:
    rows = bbg.hist(ticker, field, start, end)
    if not rows:
        return pd.Series(dtype=float)
    return pd.Series(
        {pd.Timestamp(r["date"]): float(r[field]) for r in rows if r.get(field) not in (None, "")}
    ).sort_index()


def sanity_filter(s: pd.Series, lo: float, hi: float, label: str) -> pd.Series:
    """Drop out-of-range observations (logged loudly). A handful of bad prints
    happens (e.g. TPGBTW10 published bond PRICES for 47 days in 2011); but if
    >5% of a series is out of range the units are wrong — abort, don't guess."""
    if s.empty:
        return s
    bad = (s <= lo) | (s > hi)
    if bad.any():
        frac = bad.mean()
        if frac > 0.05:
            raise RuntimeError(
                f"{label}: {bad.sum()}/{len(s)} obs outside ({lo}, {hi}] — looks like a unit error, refusing to write")
        print(f"  WARNING {label}: dropping {bad.sum()}/{len(s)} out-of-range obs "
              f"({s[bad].index.min().date()} .. {s[bad].index.max().date()})")
        s = s[~bad]
    return s


def collect(start: str, end: str) -> pd.DataFrame:
    bloomberg_setup(verbose=False)
    records: list[pd.DataFrame] = []
    # tickers are shared across countries (CHINAG, USGG10YR) — fetch each once
    cache: dict[str, pd.Series] = {}
    n_cds = n_y10 = 0
    with BBG() as bbg:
        def get(ticker: str, field: str = "PX_LAST") -> pd.Series:
            # per-ticker isolation (house rule): one bad ticker must not kill
            # the other 33 countries — but it is logged loudly, never swallowed.
            key = f"{ticker}|{field}"
            if key not in cache:
                try:
                    cache[key] = hist_series(bbg, ticker, start, end, field)
                except Exception as e:
                    print(f"  TICKER FAILED {ticker}: {e}")
                    cache[key] = pd.Series(dtype=float)
            return cache[key]

        n_cds1 = n_y2 = 0
        for country, (cds_t, y10_spec) in TICKERS.items():
            frames = []
            if cds_t:
                s = sanity_filter(get(cds_t), 0, 10_000, f"{country} CDS 5Y (bp)")
                if not s.empty:
                    frames.append(pd.DataFrame(
                        {"date": s.index, "value": s.values, "variable": "SOV_CDS_5Y_BP"}))
                    n_cds += 1
                else:
                    print(f"  WARNING {country}: CDS ticker {cds_t} returned no data")
                # 1Y CDS — derived contract name, same per-ticker isolation
                s1 = sanity_filter(get(cds_1y_ticker(cds_t)), 0, 10_000, f"{country} CDS 1Y (bp)")
                if not s1.empty:
                    frames.append(pd.DataFrame(
                        {"date": s1.index, "value": s1.values, "variable": "SOV_CDS_1Y_BP"}))
                    n_cds1 += 1
                else:
                    print(f"  WARNING {country}: 1Y CDS {cds_1y_ticker(cds_t)} returned no data")
            if y10_spec:
                y10_t, y10_field = y10_spec
                s = sanity_filter(get(y10_t, y10_field), -5, 100, f"{country} 10Y (pct)")
                if not s.empty:
                    frames.append(pd.DataFrame(
                        {"date": s.index, "value": s.values, "variable": "SOV_10Y_YIELD_PCT"}))
                    n_y10 += 1
                else:
                    print(f"  WARNING {country}: 10Y ticker {y10_t} returned no data")
            y2_spec = BOND_2Y.get(country)
            if y2_spec:
                y2_t, y2_field = y2_spec
                s = sanity_filter(get(y2_t, y2_field), -5, 100, f"{country} 2Y (pct)")
                if not s.empty:
                    frames.append(pd.DataFrame(
                        {"date": s.index, "value": s.values, "variable": "SOV_2Y_YIELD_PCT"}))
                    n_y2 += 1
                else:
                    print(f"  WARNING {country}: 2Y ticker {y2_t} returned no data")
            if frames:
                df = pd.concat(frames, ignore_index=True)
                df["country"] = country
                records.append(df)

    if not records:
        raise RuntimeError("no sovereign data collected at all")
    out = pd.concat(records, ignore_index=True)
    out["source"] = "bloomberg"
    print(f"collected: {n_cds} CDS-5Y, {n_cds1} CDS-1Y, {n_y10} 10Y, {n_y2} 2Y series, "
          f"{len(out):,} rows")
    return out[["date", "country", "value", "variable", "source"]]


def merge_and_save(new: pd.DataFrame) -> None:
    panel = pd.read_parquet(PANEL_PATH) if PANEL_PATH.exists() else pd.DataFrame(
        columns=["date", "country", "value", "variable", "source"])
    merged = pd.concat([panel, new], ignore_index=True)
    merged["date"] = pd.to_datetime(merged["date"])
    merged = merged.drop_duplicates(subset=["date", "country", "variable"], keep="last")
    merged = merged.sort_values(["country", "variable", "date"]).reset_index(drop=True)
    PANEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PANEL_PATH.with_suffix(".parquet.tmp")
    merged.to_parquet(tmp, index=False)
    tmp.replace(PANEL_PATH)
    print(f"panel: {len(merged):,} rows, {merged['date'].min().date()} -> {merged['date'].max().date()}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Bloomberg daily sovereign CDS + 10Y (loop, PRD P8).")
    parser.add_argument("--backfill", action="store_true", help="full history from 2005")
    parser.add_argument("--start", default=None, metavar="YYYY-MM-DD")
    args = parser.parse_args()

    end = date.today().strftime("%Y%m%d")
    start = (HISTORY_START if args.backfill
             else args.start.replace("-", "") if args.start
             else (date.today() - timedelta(days=15)).strftime("%Y%m%d"))
    print(f"Pulling sovereign CDS/10Y {start} -> {end}")
    try:
        new = collect(start, end)
    except Exception as e:
        print(f"SOVEREIGN PULL FAILED: {e} — existing parquet untouched")
        return 1
    merge_and_save(new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
