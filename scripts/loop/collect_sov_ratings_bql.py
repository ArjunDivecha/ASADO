#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/collect_sov_ratings_bql.py
=============================================================================

INPUT FILES:
- Bloomberg Terminal via raw blpapi //blp/bqlsvc (network source, no local
    input file). This is ASADO's FIRST BQL-based collector. For each country
    it runs:
      get(rating(source=<SP|MOODY|FITCH>, dates=range(-20Y,0D, frq=M)))
      for(issuerof('<anchor>'))
    where <anchor> is the country's 5Y CDS contract when one exists (the
    CDS issuer entity is the sovereign itself and carries the standard
    FOREIGN-CURRENCY issuer ratings from all three agencies), else the
    GT[CCY]10Y Govt generic (DM names with no liquid CDS).
    The issuerof() hop is the key discovery (2026-06-12): rating() directly
    on a generic/CDS returns null, and rating() on the resolved bond is
    capped at that bond's issue date — but the ISSUER entity carries the
    sovereign's monthly rating history (Bloomberg serves ~11 years, 2015+).
    The CDS anchor matters: for Mexico / South Africa / Turkey the local
    GT generics resolve to NO issuer entity at all, and for several locals
    (Brazil, Chile) the local-notes program entity has no Moody's rating —
    the CDS entity has all three.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/sov_ratings_monthly.parquet
    Tidy monthly panel (date, country, value, variable, source='bloomberg_bql'):
      SOV_RATING_SP      S&P LT issuer rating, 21-point numeric scale
      SOV_RATING_MOODY   Moody's, same scale
      SOV_RATING_FITCH   Fitch, same scale
    Scale matches scripts/collect_bloomberg.py RATING_SCALE exactly
    (AAA/Aaa = 21 ... C = 1, D/SD = 0; higher = better credit) so monthly
    warehouse snapshots and this history are directly comparable.
    Dates normalized to first-of-month. Full replace each run (history is
    served complete every time; no incremental merge needed).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/bbg_quota_log.csv
    Append-only quota log per the bloomberg-skill mandatory pattern.

VERSION: 1.0
LAST UPDATED: 2026-06-12
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop)

DESCRIPTION:
Historical sovereign credit ratings. The monthly warehouse only has a
CURRENT-rating snapshot (collect_bloomberg.py collector 4, one row per
month going forward). This collector backfills the actual rating PATH —
Brazil's BBB+ (2015) -> BB- (2018) -> BB (2023) downgrade arc, Turkey's
slide, Saudi's upgrades — which is what event studies and the dislocation
engine need: a rating CHANGE is a dated, tradeable event; the loop can
check how returns/CDS led or lagged it.

Why BQL and not BDH: RTG_* fields are not BDH-able (no history via
refdata), and rating() via BQL needs the EXCEL clientContext unlock plus
the issuerof() universe hop — see bloomberg-skill references/bql.md and
references/bql-extended.md.

Known coverage notes (verified 2026-06-12):
- Hong Kong: no CDS ticker and no resolvable GT generic — skipped.
- Vietnam: covered via its CDS anchor (no GT generic).
- CDS-anchored countries return FC issuer ratings (the standard headline
  sovereign rating); GT-anchored DM names may return the local program's
  ratings — for DM these are identical in practice.
- Moody's history starts ~2017-02 vs 2015-01 for S&P/Fitch (Bloomberg-side
  depth limit, not a bug).

DEPENDENCIES:
- OpusBloomberg conda env: blpapi, pandas, pyarrow (NOT the project venv)

USAGE:
  conda run -p "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv" \
      python scripts/loop/collect_sov_ratings_bql.py

NOTES:
- Bloomberg Terminal must be logged in on the Parallels VM.
- ~96 BQL queries (32 countries x 3 sources), ~2s each => ~3-4 min run.
  BQL is compute-capacity bound, not unique-ID bound — safe to run nightly.
- FAIL-IS-FAIL: per-country/source isolation (one dead entity must not kill
  the run), but if NOTHING is collected the parquet is left untouched.
=============================================================================
"""

from __future__ import annotations

import csv
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg")
import blpapi  # noqa: E402
from bbg import detect_vm_ip, bloomberg_setup  # noqa: E402

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PANEL_PATH = BASE_DIR / "Data" / "work" / "loop" / "sov_ratings_monthly.parquet"
QUOTA_LOG = BASE_DIR / "Data" / "work" / "loop" / "bbg_quota_log.csv"

# country -> issuerof() anchor. CDS contract where one exists (sovereign FC
# issuer entity, all 3 agencies), else the GT[CCY]10Y Govt generic.
# CDS names from scripts/loop/collect_sovereign_daily_bbg.py TICKERS;
# GT generics from scripts/collect_bloomberg.py RATING_TICKER_OVERRIDES.
ANCHORS = {
    "Australia":    "AUSTLA CDS USD SR 5Y Corp",
    "Brazil":       "BRAZIL CDS USD SR 5Y Corp",
    "Canada":       "GTCAD10Y Govt",
    "Chile":        "CHILE CDS USD SR 5Y Corp",
    "ChinaA":       "CHINAG CDS USD SR 5Y Corp",
    "ChinaH":       "CHINAG CDS USD SR 5Y Corp",
    "Denmark":      "GTDKK10Y Govt",
    "France":       "FRANCE CDS USD SR 5Y D14 Corp",
    "Germany":      "GTDEM10Y Govt",
    "India":        "GTINR10Y Govt",
    "Indonesia":    "INDON CDS USD SR 5Y Corp",
    "Italy":        "ITALY CDS USD SR 5Y D14 Corp",
    "Japan":        "JAPAN CDS USD SR 5Y Corp",
    "Korea":        "KOREA CDS USD SR 5Y Corp",
    "Malaysia":     "MALAYS CDS USD SR 5Y Corp",
    "Mexico":       "MEXICO CDS USD SR 5Y Corp",
    "NASDAQ":       "GTUSD10Y Govt",
    "Netherlands":  "GTNLG10Y Govt",
    "Philippines":  "PHILIP CDS USD SR 5Y Corp",
    "Poland":       "POLAND CDS USD SR 5Y D14 Corp",
    "Saudi Arabia": "SAUDI CDS USD SR 5Y Corp",
    "Singapore":    "GTSGD10Y Govt",
    "South Africa": "REPSOU CDS USD SR 5Y D14 Corp",
    "Spain":        "SPAIN CDS USD SR 5Y D14 Corp",
    "Sweden":       "GTSEK10Y Govt",
    "Switzerland":  "GTCHF10Y Govt",
    "Taiwan":       "GTTWD10Y Govt",
    "Thailand":     "THAI CDS USD SR 5Y Corp",
    "Turkey":       "TURKEY CDS USD SR 5Y Corp",
    "U.K.":         "GTGBP10Y Govt",
    "U.S.":         "GTUSD10Y Govt",
    "US SmallCap":  "GTUSD10Y Govt",
    "Vietnam":      "VIETNM CDS USD SR 5Y Corp",
}

SOURCES = {"SP": "SOV_RATING_SP", "MOODY": "SOV_RATING_MOODY", "FITCH": "SOV_RATING_FITCH"}

# Letter -> 21-point numeric scale, identical to collect_bloomberg.py
# RATING_SCALE (higher = better credit).
RATING_SCALE = {
    "AAA": 21,                        "Aaa": 21,
    "AA+": 20, "AA": 19, "AA-": 18,   "Aa1": 20, "Aa2": 19, "Aa3": 18,
    "A+": 17, "A": 16, "A-": 15,      "A1": 17, "A2": 16, "A3": 15,
    "BBB+": 14, "BBB": 13, "BBB-": 12, "Baa1": 14, "Baa2": 13, "Baa3": 12,
    "BB+": 11, "BB": 10, "BB-": 9,    "Ba1": 11, "Ba2": 10, "Ba3": 9,
    "B+": 8, "B": 7, "B-": 6,         "B1": 8, "B2": 7, "B3": 6,
    "CCC+": 5, "CCC": 4, "CCC-": 3,   "Caa1": 5, "Caa2": 4, "Caa3": 3,
    "CC": 2, "Ca": 2,
    "C": 1,
    "D": 0, "SD": 0, "RD": 0,
}


def rating_to_score(raw) -> float | None:
    """Normalize a Bloomberg rating string to the 21-point scale.
    Strips watch/preliminary decorations ('*+', '*-', '(P)') and the
    unsolicited/expected suffixes ('u', 'e' — e.g. 'AA+u'). Returns None
    for anything unmappable ('N.A.', 'NR', 'WD') — never a silent guess."""
    if raw is None:
        return None
    s = str(raw).strip()
    for token in ("*+", "*-", "(P)", " PRELIM"):
        s = s.replace(token, "")
    s = s.strip().rstrip("ue").strip()
    return float(RATING_SCALE[s]) if s in RATING_SCALE else None


def log_quota(operation: str, est_hits: int, rows: int, elapsed: float, status: str) -> None:
    QUOTA_LOG.parent.mkdir(parents=True, exist_ok=True)
    new = not QUOTA_LOG.exists()
    with QUOTA_LOG.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "script", "operation", "est_hits", "rows", "elapsed_s", "status"])
        w.writerow([datetime.now().isoformat(timespec="seconds"),
                    "collect_sov_ratings_bql", operation, est_hits, rows,
                    f"{elapsed:.1f}", status])


class BQLSession:
    """Minimal BQL-over-blpapi client (//blp/bqlsvc + the EXCEL unlock).
    See bloomberg-skill references/bql.md — without appName='EXCEL'
    Bloomberg returns a misleading 'User not authorized to use BQL' error."""

    def __init__(self) -> None:
        opts = blpapi.SessionOptions()
        opts.setServerHost(detect_vm_ip())
        opts.setServerPort(8194)
        self.session = blpapi.Session(opts)
        if not self.session.start():
            raise ConnectionError("Bloomberg session start failed")
        if not self.session.openService("//blp/bqlsvc"):
            self.session.stop()
            raise ConnectionError("//blp/bqlsvc open failed")
        self.svc = self.session.getService("//blp/bqlsvc")

    def close(self) -> None:
        self.session.stop()

    def __enter__(self) -> "BQLSession":
        return self

    def __exit__(self, *exc) -> bool:
        self.close()
        return False

    def query(self, expression: str, timeout_ms: int = 60_000) -> dict:
        """Run one BQL expression, return the parsed result JSON dict.
        The answer arrives as a single scalar message named 'result' whose
        VALUE is a JSON string (msg.asElement().getValueAsString() — it is
        NOT a sub-element, msg.getElementAsString('result') fails)."""
        req = self.svc.createRequest("sendQuery")
        req.set("expression", expression)
        try:
            req.getElement("clientContext").setElement("appName", "EXCEL")
        except blpapi.NotFoundException:
            pass  # some blpapi versions lack the element; try anyway
        self.session.sendRequest(req)
        result: dict = {}
        while True:
            ev = self.session.nextEvent(timeout_ms)
            if ev.eventType() == blpapi.Event.TIMEOUT:
                raise TimeoutError(f"BQL timeout: {expression[:80]}")
            for msg in ev:
                if str(msg.messageType()) == "result":
                    result = json.loads(msg.asElement().getValueAsString())
            if ev.eventType() == blpapi.Event.RESPONSE:
                return result


def parse_rating_result(result: dict) -> pd.Series:
    """Extract (date -> letter rating) from a BQL rating() result dict."""
    results = result.get("results") or {}
    if not results:
        return pd.Series(dtype=object)
    block = next(iter(results.values()))
    vals = block["valuesColumn"]["values"]
    dates = None
    for sc in block.get("secondaryColumns", []):
        if sc.get("name") == "DATE":
            dates = sc["values"]
    if dates is None:
        return pd.Series(dtype=object)
    pairs = {pd.Timestamp(d): v for d, v in zip(dates, vals)
             if d is not None and v not in (None, "")}
    return pd.Series(pairs).sort_index()


def collect() -> pd.DataFrame:
    bloomberg_setup(verbose=False)
    t0 = time.time()
    frames: list[pd.DataFrame] = []
    n_queries = n_series = 0

    with BQLSession() as bql:
        for country, anchor in ANCHORS.items():
            for src, variable in SOURCES.items():
                expr = (f"get(rating(source={src}, dates=range(-20Y,0D, frq=M))) "
                        f"for(issuerof('{anchor}'))")
                n_queries += 1
                try:
                    s = parse_rating_result(bql.query(expr))
                except Exception as e:
                    print(f"  QUERY FAILED {country}/{src}: {e}")
                    continue
                scores = s.map(rating_to_score).dropna()
                if scores.empty:
                    print(f"  WARNING {country}/{src}: no mappable rating history")
                    continue
                # first-of-month normalization (house rule); BQL dates are tz-aware
                scores.index = pd.DatetimeIndex(scores.index).tz_localize(None)
                scores.index = scores.index.to_period("M").to_timestamp()
                scores = scores[~scores.index.duplicated(keep="last")]
                frames.append(pd.DataFrame(
                    {"date": scores.index, "country": country,
                     "value": scores.values, "variable": variable}))
                n_series += 1

    elapsed = time.time() - t0
    if not frames:
        log_quota("bql rating history", n_queries, 0, elapsed, "EMPTY")
        raise RuntimeError("no rating history collected at all")
    out = pd.concat(frames, ignore_index=True)
    out["source"] = "bloomberg_bql"
    log_quota("bql rating history", n_queries, len(out), elapsed, "OK")
    print(f"collected: {n_series} series from {n_queries} BQL queries, "
          f"{len(out):,} rows, {elapsed:.0f}s")
    return out[["date", "country", "value", "variable", "source"]]


def save(panel: pd.DataFrame) -> None:
    """Full atomic replace — BQL serves the complete history every run."""
    panel = panel.sort_values(["country", "variable", "date"]).reset_index(drop=True)
    PANEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = PANEL_PATH.with_suffix(".parquet.tmp")
    panel.to_parquet(tmp, index=False)
    tmp.replace(PANEL_PATH)
    print(f"panel: {len(panel):,} rows, {panel['date'].min().date()} -> "
          f"{panel['date'].max().date()}, {panel['country'].nunique()} countries")


def main() -> int:
    print("Pulling sovereign rating history via BQL (S&P / Moody's / Fitch, monthly)")
    try:
        panel = collect()
    except Exception as e:
        print(f"RATINGS PULL FAILED: {e} — existing parquet untouched")
        return 1
    save(panel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
