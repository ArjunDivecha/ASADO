#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/collect_eco_surprise_bbg.py
=============================================================================

INPUT FILES:
- Bloomberg Terminal via OpusBloomberg (network source, no local input file).
    Economic-release tickers (ECO calendar "... Index" securities) pulled
    with TWO historical fields each:
      ACTUAL_RELEASE     what the statistic actually printed
      BN_SURVEY_MEDIAN   the Bloomberg economist-survey median BEFORE print
    Four indicator families across the T2 universe (CPI/UNEMP/PMI maps from
    the bloomberg-skill findatapy econ grid; GDP map rebuilt by live probe
    — the grid's GDP tickers were stale; all verified live 2026-06-12):
      CPI YoY (31 countries), Unemployment Rate (27), GDP headline (17),
      Markit Manufacturing PMI (20).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/eco_surprise_monthly.parquet
    Tidy panel (date, country, value, variable, source='bloomberg'), dates
    are the OBSERVATION reference period normalized to first-of-month
    (house rule), NOT the release timestamp. Variables per indicator
    <IND> in {CPI, UNEMP, GDP, PMI}:
      ECO_<IND>_ACTUAL     released value (native units: %, index pts)
      ECO_<IND>_SURPRISE   ACTUAL_RELEASE - BN_SURVEY_MEDIAN (same units);
                           positive = the print came in ABOVE consensus.
                           Sign interpretation differs by indicator: above-
                           consensus GDP/PMI = growth-positive, above-
                           consensus UNEMPLOYMENT = growth-negative, above-
                           consensus CPI = inflation above expectations.
                           The loader (load_eco_surprise.py) builds the
                           sign-consistent composites.
    New rows win on (date, country, variable). This script does NOT touch
    DuckDB — see scripts/loop/load_eco_surprise.py.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/bbg_quota_log.csv
    Append-only quota log per the bloomberg-skill mandatory pattern.

VERSION: 1.0
LAST UPDATED: 2026-06-12
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop)

DESCRIPTION:
Economic surprise layer. The warehouse has plenty of macro LEVELS (OECD,
IMF, World Bank) but nothing about what markets EXPECTED — and returns
react to the gap between print and consensus, not to the level. This
collector builds the actual-vs-survey surprise history per T2 country so
the loop can (a) flag countries whose data keeps beating/missing, and
(b) join dated surprises against return windows in event studies.

Mechanics note (verified 2026-06-12): ACTUAL_RELEASE and BN_SURVEY_MEDIAN
are BDH-able on ECO release tickers; the returned dates are the reference
period end (e.g. May CPI = 2026-05-31), survey history serves from ~2015
on most series. Surprise rows require BOTH fields on the same date.

DEPENDENCIES:
- OpusBloomberg conda env: blpapi, pandas, pyarrow (NOT the project venv)

USAGE:
  conda run -p "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv" \
      python scripts/loop/collect_eco_surprise_bbg.py             # last 6 months
  ... collect_eco_surprise_bbg.py --backfill                      # full 2000+ history

NOTES:
- Bloomberg Terminal must be logged in on the Parallels VM.
- ~103 tickers x 2 fields = 206 history requests per run (1 hit each
  regardless of range). All first-pulled 2026-06-12 => free against the
  monthly unique-ID counter thereafter.
- Sanity guards: |surprise| must be < 25 native units (a CPI print 25pts
  from consensus is a data error, not a surprise; Turkey's wildest CPI
  misses were ~5pts). Series failing >5% abort the run (FAIL-IS-FAIL).
- 'United States' maps to U.S. + NASDAQ + US SmallCap; 'China' to
  ChinaA + ChinaH (house mapping rules).
=============================================================================
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg")
from bbg import BBG, bloomberg_setup  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PANEL_PATH = BASE_DIR / "Data" / "work" / "loop" / "eco_surprise_monthly.parquet"
QUOTA_LOG = BASE_DIR / "Data" / "work" / "loop" / "bbg_quota_log.csv"

HISTORY_START = "20000101"

# Broadcast names per house mapping rules.
BROADCAST = {"United States": ["U.S.", "NASDAQ", "US SmallCap"],
             "China": ["ChinaA", "ChinaH"]}

# indicator -> {display country -> ECO release ticker}
# Extracted from the bloomberg-skill findatapy econ grid 2026-06-12.
ECO_TICKERS: dict[str, dict[str, str]] = {
    "CPI": {
        "Australia": "AUCPIYOY Index", "Brazil": "BZPIIPCY Index",
        "Canada": "CACPIYOY Index", "Chile": "CNPINSYO Index",
        "China": "CNCPIYOY Index", "Denmark": "DNCPIYOY Index",
        "France": "FRCPIYOY Index", "Germany": "GRCP20YY Index",
        "Hong Kong": "HKCPIY Index", "India": "INFUTOTY Index",
        "Indonesia": "IDCPIY Index", "Italy": "ITCPNICY Index",
        "Japan": "JNCPIYOY Index", "Korea": "KOCPIYOY Index",
        "Malaysia": "MACPIYOY Index", "Mexico": "MXCPYOY Index",
        "Netherlands": "NECPIYOY Index", "Philippines": "PHC2II Index",
        "Poland": "POCPIYOY Index", "Saudi Arabia": "SRCPIYOY Index",
        "Singapore": "SICPIYOY Index", "South Africa": "SACPIYOY Index",
        "Spain": "SPIPCYOY Index", "Sweden": "SWCPYOY Index",
        "Switzerland": "SZCPIYOY Index", "Taiwan": "TWCPIYOY Index",
        "Thailand": "THCPIYOY Index", "Turkey": "TUCPIY Index",
        "U.K.": "UKRPCJYR Index", "United States": "CPI YOY Index",
        "Vietnam": "VNCPIYOY Index",
    },
    "UNEMP": {
        "Australia": "AULFUNEM Index", "Brazil": "BZUETOTN Index",
        "Canada": "CANLXEMR Index", "Chile": "CHUETOTL Index",
        "China": "CNUERATE Index", "Denmark": "UMRTDK Index",
        "France": "UMRTFR Index", "Germany": "GILOURS Index",
        "Hong Kong": "HKUERATE Index", "Italy": "ITMUURS Index",
        "Japan": "JNUE Index", "Korea": "KOEAUERS Index",
        "Malaysia": "MAEPRATE Index", "Mexico": "MXUEUNSA Index",
        "Netherlands": "NEUETOTR Index", "Philippines": "PHLFUERT Index",
        "Poland": "POUER Index", "Singapore": "SIQUTOTA Index",
        "South Africa": "SAUERATQ Index", "Spain": "UMRTES Index",
        "Sweden": "SWUESART Index", "Switzerland": "SZUEUEA Index",
        "Taiwan": "TWLFADJ Index", "Thailand": "THLMUERT Index",
        "Turkey": "TULSUR Index", "U.K.": "UKUEILOR Index",
        "United States": "USURTOT Index",
        # Dead/no-survey (probed 2026-06-12, alternatives also dead):
        # Denmark UMRTDK, France UMRTFR, Spain UMRTES, Thailand THLMUERT,
        # Turkey TULSUR (kept in map for the day Bloomberg revives it; the
        # collector skips empties loudly).
    },
    # GDP: the findatapy grid's GDP tickers were almost all dead/renamed —
    # this map was rebuilt by live Terminal probe 2026-06-12 (only tickers
    # that carry BOTH ACTUAL_RELEASE and BN_SURVEY_MEDIAN kept). A mix of
    # QoQ and YoY headline measures — fine for SURPRISES (same units within
    # each country's own series). No survey-carrying release ticker found
    # for: Canada, Chile, Denmark, India, Italy, Netherlands, Philippines,
    # Switzerland, Taiwan, Thailand, Turkey.
    "GDP": {
        "Australia": "AUNAGDPC Index", "Brazil": "BZGDQOQ% Index",
        "China": "CNGDPYOY Index", "France": "FRGEGDPQ Index",
        "Germany": "GRGDPPGQ Index", "Indonesia": "IDGDPY Index",
        "Japan": "JGDOQOQ Index", "Korea": "KOGDPQOQ Index",
        "Malaysia": "MAGDHIY Index", "Mexico": "MXGCTOT Index",
        "Poland": "POGDYOY Index", "Singapore": "SGDPYOY Index",
        "South Africa": "SAGDPANN Index", "Spain": "SPNAGDPQ Index",
        "Sweden": "SWGDPAQQ Index", "U.K.": "UKGRABIQ Index",
        "United States": "GDP CQOQ Index",
    },
    "PMI": {
        "Brazil": "MPMIBRMA Index", "Canada": "MPMICAMA Index",
        "China": "MPMICNMA Index", "France": "MPMIFRMA Index",
        "Germany": "MPMIDEMA Index", "India": "MPMIINMA Index",
        "Indonesia": "MPMIIDMA Index", "Italy": "MPMIITMA Index",
        "Japan": "MPMIJPMA Index", "Korea": "MPMIKRMA Index",
        "Malaysia": "MPMIMYMA Index", "Mexico": "MPMIMXMA Index",
        "Netherlands": "MPMINLMA Index", "Poland": "MPMIPLMA Index",
        "Spain": "MPMIESMA Index", "Taiwan": "MPMITWMA Index",
        "Turkey": "MPMITRMA Index", "U.K.": "MPMIGBMA Index",
        "United States": "MPMIUSMA Index", "Vietnam": "MPMIVNMA Index",
    },
}

MAX_ABS_SURPRISE = 25.0  # native units; bigger = data error, not a surprise


def log_quota(operation: str, est_hits: int, rows: int, elapsed: float, status: str) -> None:
    QUOTA_LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not QUOTA_LOG.exists()
    with QUOTA_LOG.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "script", "operation", "est_hits", "rows", "elapsed_s", "status"])
        w.writerow([datetime.now().isoformat(timespec="seconds"),
                    "collect_eco_surprise_bbg", operation, est_hits, rows,
                    f"{elapsed:.1f}", status])


def hist_series(bbg: BBG, ticker: str, field: str, start: str, end: str) -> pd.Series:
    rows = bbg.hist(ticker, field, start, end)
    if not rows:
        return pd.Series(dtype=float)
    return pd.Series(
        {pd.Timestamp(r["date"]): float(r[field]) for r in rows if r.get(field) not in (None, "")}
    ).sort_index()


def collect(start: str, end: str) -> pd.DataFrame:
    bloomberg_setup(verbose=False)
    t0 = time.time()
    frames: list[pd.DataFrame] = []
    n_req = n_series = 0

    with BBG() as bbg:
        for indicator, ticker_map in ECO_TICKERS.items():
            for display_country, ticker in ticker_map.items():
                countries = BROADCAST.get(display_country, [display_country])
                try:
                    n_req += 2
                    actual = hist_series(bbg, ticker, "ACTUAL_RELEASE", start, end)
                    survey = hist_series(bbg, ticker, "BN_SURVEY_MEDIAN", start, end)
                except Exception as e:
                    print(f"  TICKER FAILED {indicator}/{display_country} {ticker}: {e}")
                    continue
                if actual.empty:
                    print(f"  WARNING {indicator}/{display_country}: no ACTUAL_RELEASE history")
                    continue
                both = pd.concat([actual.rename("a"), survey.rename("s")], axis=1, sort=True)
                surprise = (both["a"] - both["s"]).dropna()
                # sanity: a surprise bigger than MAX_ABS_SURPRISE native units
                # is a unit/data error
                bad = surprise.abs() >= MAX_ABS_SURPRISE
                if bad.any():
                    if bad.mean() > 0.05:
                        raise RuntimeError(
                            f"{indicator}/{display_country}: {bad.sum()}/{len(surprise)} "
                            f"surprises >= {MAX_ABS_SURPRISE} — unit error, refusing to write")
                    print(f"  WARNING {indicator}/{display_country}: dropping {bad.sum()} "
                          f"absurd surprise obs")
                    surprise = surprise[~bad]

                def fom(s: pd.Series) -> pd.Series:
                    s = s.copy()
                    s.index = s.index.to_period("M").to_timestamp()
                    return s[~s.index.duplicated(keep="last")]

                actual_m, surprise_m = fom(actual), fom(surprise)
                for c in countries:
                    frames.append(pd.DataFrame(
                        {"date": actual_m.index, "country": c,
                         "value": actual_m.values, "variable": f"ECO_{indicator}_ACTUAL"}))
                    if not surprise_m.empty:
                        frames.append(pd.DataFrame(
                            {"date": surprise_m.index, "country": c,
                             "value": surprise_m.values, "variable": f"ECO_{indicator}_SURPRISE"}))
                n_series += 1

    elapsed = time.time() - t0
    if not frames:
        log_quota(f"eco hist {start}->{end}", n_req, 0, elapsed, "EMPTY")
        raise RuntimeError("no economic surprise data collected at all")
    out = pd.concat(frames, ignore_index=True)
    out["source"] = "bloomberg"
    log_quota(f"eco hist {start}->{end}", n_req, len(out), elapsed, "OK")
    print(f"collected: {n_series} release series, {len(out):,} rows, "
          f"{n_req} requests, {elapsed:.0f}s")
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
    parser = argparse.ArgumentParser(
        description="Bloomberg economic surprise layer (actual vs survey median, T2 universe).")
    parser.add_argument("--backfill", action="store_true", help="full history from 2000")
    parser.add_argument("--start", default=None, metavar="YYYY-MM-DD")
    args = parser.parse_args()

    end = date.today().strftime("%Y%m%d")
    start = (HISTORY_START if args.backfill
             else args.start.replace("-", "") if args.start
             else (date.today() - timedelta(days=185)).strftime("%Y%m%d"))
    print(f"Pulling economic surprise layer {start} -> {end}")
    try:
        new = collect(start, end)
    except Exception as e:
        print(f"ECO SURPRISE PULL FAILED: {e} — existing parquet untouched")
        return 1
    merge_and_save(new)
    return 0


if __name__ == "__main__":
    sys.exit(main())
