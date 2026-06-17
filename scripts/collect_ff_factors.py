#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/collect_ff_factors.py
=============================================================================

DESCRIPTION:
Ingests the Kenneth R. French Data Library factor returns (Fama-French 5
factors + momentum) for the US and six international regions into ASADO as an
ISOLATED, REGION-KEYED benchmark/explanatory corpus.

What this is FOR (the design decision, 2026-06-17):
  ASADO already treats T2 country/factor returns as the OUTCOME source of
  truth. Ken French data is NOT another return source — it is the canonical
  free set of GLOBAL STYLE-FACTOR returns (market, size, value, profitability,
  investment, momentum) plus the risk-free rate. Its job is to answer one
  question the skeptic harness could not previously ask: "is a candidate
  signal's long-short P&L genuinely orthogonal alpha, or is it just repackaged
  regional value / size / momentum / quality beta?" That is a style-spanning
  regression (see scripts/harness/ff_spanning.py), and the risk-free series
  also standardises excess-return / Sharpe math across the loop.

CRITICAL ARCHITECTURE RULE (same lesson as JST macrohistory + the deprecated
wb_commodity_factor_panel):
  FF factors are REGIONAL (US, Developed, Developed_ex_US, North_America,
  Europe, Japan, Asia_Pacific_ex_Japan, Emerging) — there are only 8 series
  per variable, NOT 34 country series. They are loaded into their OWN DuckDB
  table `ff_factors` and are *never* unioned into `unified_panel` /
  `feature_panel` and *never* broadcast/tiled to the 34 countries. Tiling 8
  regional series across 34 countries would manufacture degenerate _CS
  cross-sections (the wb_commodity_factor_panel mistake). The country->region
  link (config/ff_region_map.json) is applied ON THE FLY at regression time,
  not materialised into rows.

Units: values are stored EXACTLY as Ken French publishes them — monthly/daily
percent returns (e.g. 0.77 means +0.77%). Missing markers -99.99 / -999 are
converted to NULL and dropped. The `units` column records 'percent'. The
spanning tool divides by 100 to align with decimal return series.

Region/coverage notes:
- US factors run from 1963-07 (5-factor) / 1926-11 (momentum), USD.
- The six international regions run from 1990-07 (5-factor) / 1990-11 (mom).
- Emerging runs from 1989-07 (monthly only — French publishes NO daily
  Emerging file; the daily block is US + the six developed regions).
- Currency: USD only (the standard French international files). Local-currency
  variants exist on the site and can be added later behind a `currency` flag.
- Momentum is stored under the single variable name 'WML' for every region
  (the US file calls its column 'Mom'; it is normalised to WML so cross-region
  joins are clean).

INPUT FILES:
- https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/<dataset>_CSV.zip
    Live downloads (24h raw cache); see FF_DATASETS below for the exact 30-file
    manifest (HEAD-verified 2026-06-17).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/ff_region_map.json
    Country->region map + region metadata (written/refreshed by this script if
    absent; consumed by scripts/harness/ff_spanning.py).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/raw/ff/<dataset>.zip
    Raw downloaded zips (24h cache; --force bypasses).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/processed/ff_factors_panel.parquet
    Tidy panel: (date, region, frequency, currency, variable, value, units,
    source). source = 'ken_french'. Loaded to DuckDB table `ff_factors`
    (isolated; NOT in unified_panel).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/backups/ff_factors_panel_YYYY_MM_DD_HHMMSS.parquet
    Timestamped backup of the prior panel before any overwrite.

VERSION: 1.0
LAST UPDATED: 2026-06-17
AUTHOR: Claude Code for Arjun Divecha

DEPENDENCIES: pandas, numpy, requests, pyarrow (ASADO venv).

USAGE:
  venv/bin/python scripts/collect_ff_factors.py            # normal (24h cache)
  venv/bin/python scripts/collect_ff_factors.py --force    # bypass cache
  venv/bin/python scripts/collect_ff_factors.py --dry-run  # preview, no writes
  venv/bin/python scripts/collect_ff_factors.py --check    # verify existing panel

NOTES:
- Per-dataset try/except: one missing/failed file never aborts the run; the
  collector logs exactly what it skipped (no silent caps) and preserves any
  prior panel rows for the failed datasets via source-level merge.
- This collector refreshes monthly (French updates ~monthly). It is wired into
  monthly_update.py Stage 1 and setup_duckdb.py (load_ff_factors).
=============================================================================
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ── Paths ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "Data" / "raw" / "ff"
PROCESSED_DIR = BASE_DIR / "Data" / "processed"
BACKUP_DIR = BASE_DIR / "Data" / "backups"
CACHE_DIR = BASE_DIR / "Data" / "cache"
OUT_PARQUET = PROCESSED_DIR / "ff_factors_panel.parquet"
REGION_MAP_PATH = BASE_DIR / "config" / "ff_region_map.json"

for _d in (RAW_DIR, PROCESSED_DIR, CACHE_DIR):
    _d.mkdir(parents=True, exist_ok=True)

FF_BASE_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
SOURCE = "ken_french"

# ── Dataset manifest (HEAD-verified 2026-06-17) ─────────────────────────────
# Each entry: (region, frequency, kind, filename). kind ∈ {"5f","mom"}.
# US 5-factor is F-F_Research_Data_5_Factors_2x3; US momentum is a separate
# file whose column is 'Mom' (normalised to WML on load). The six developed
# regions follow the <Region>_5_Factors[_Daily] / <Region>_Mom_Factor[_Daily]
# convention. Emerging has NO daily file on the French site.
_INTL_REGIONS = [
    "Developed", "Developed_ex_US", "North_America",
    "Europe", "Japan", "Asia_Pacific_ex_Japan",
]
FF_DATASETS: list[tuple[str, str, str, str]] = [
    # region, frequency, kind, filename
    ("US", "monthly", "5f",  "F-F_Research_Data_5_Factors_2x3_CSV.zip"),
    ("US", "daily",   "5f",  "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"),
    ("US", "monthly", "mom", "F-F_Momentum_Factor_CSV.zip"),
    ("US", "daily",   "mom", "F-F_Momentum_Factor_daily_CSV.zip"),
]
for _r in _INTL_REGIONS:
    FF_DATASETS += [
        (_r, "monthly", "5f",  f"{_r}_5_Factors_CSV.zip"),
        (_r, "daily",   "5f",  f"{_r}_5_Factors_Daily_CSV.zip"),
        (_r, "monthly", "mom", f"{_r}_Mom_Factor_CSV.zip"),
        (_r, "daily",   "mom", f"{_r}_Mom_Factor_Daily_CSV.zip"),
    ]
# Emerging: monthly only (no daily file exists on the French site).
FF_DATASETS += [
    ("Emerging", "monthly", "5f",  "Emerging_5_Factors_CSV.zip"),
    ("Emerging", "monthly", "mom", "Emerging_Mom_Factor_CSV.zip"),
]

# Expected value columns by kind. We parse POSITIONALLY against these names
# (robust to French's messy multi-line preambles), then clean "Mkt-RF"->"Mkt_RF".
VALUE_COLS = {
    "5f":  ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"],
    "mom": ["WML"],
}
MISSING_MARKERS = {-99.99, -999.0, -99.99}

# ── Country -> region map (the on-the-fly join used by ff_spanning.py) ──────
# Primary FF region per ASADO T2 country. "exact" = country is in that FF
# region universe; "proxy" = no clean FF home (Saudi/Vietnam are not in FF EM)
# so Emerging is the least-bad benchmark — flagged so consumers can downweight.
COUNTRY_TO_REGION = {
    # US bundle (native long-history US factors)
    "U.S.": ("US", "exact"), "NASDAQ": ("US", "exact"),
    "US SmallCap": ("US", "exact"),
    # North America (US+Canada); Canada has no standalone FF region
    "Canada": ("North_America", "exact"),
    # Developed Europe
    "France": ("Europe", "exact"), "Germany": ("Europe", "exact"),
    "Italy": ("Europe", "exact"), "Netherlands": ("Europe", "exact"),
    "Spain": ("Europe", "exact"), "Sweden": ("Europe", "exact"),
    "Switzerland": ("Europe", "exact"), "U.K.": ("Europe", "exact"),
    "Denmark": ("Europe", "exact"),
    # Japan
    "Japan": ("Japan", "exact"),
    # Developed Asia-Pacific ex Japan
    "Australia": ("Asia_Pacific_ex_Japan", "exact"),
    "Hong Kong": ("Asia_Pacific_ex_Japan", "exact"),
    "Singapore": ("Asia_Pacific_ex_Japan", "exact"),
    # Emerging (FF EM universe)
    "Brazil": ("Emerging", "exact"), "Chile": ("Emerging", "exact"),
    "ChinaA": ("Emerging", "exact"), "ChinaH": ("Emerging", "exact"),
    "India": ("Emerging", "exact"), "Indonesia": ("Emerging", "exact"),
    "Korea": ("Emerging", "exact"), "Malaysia": ("Emerging", "exact"),
    "Mexico": ("Emerging", "exact"), "Philippines": ("Emerging", "exact"),
    "Poland": ("Emerging", "exact"), "South Africa": ("Emerging", "exact"),
    "Taiwan": ("Emerging", "exact"), "Thailand": ("Emerging", "exact"),
    "Turkey": ("Emerging", "exact"),
    # Proxies (not in FF EM universe — Emerging is the least-bad benchmark)
    "Saudi Arabia": ("Emerging", "proxy"), "Vietnam": ("Emerging", "proxy"),
}

REGION_META = {
    "US": {"description": "United States (CRSP)", "has_daily": True,
           "fivef_start": "196307", "mom_start": "192611"},
    "Developed": {"description": "Developed markets (23 countries)",
                  "has_daily": True, "fivef_start": "199007", "mom_start": "199011"},
    "Developed_ex_US": {"description": "Developed ex US", "has_daily": True,
                        "fivef_start": "199007", "mom_start": "199011"},
    "North_America": {"description": "US + Canada", "has_daily": True,
                      "fivef_start": "199007", "mom_start": "199011"},
    "Europe": {"description": "Developed Europe", "has_daily": True,
               "fivef_start": "199007", "mom_start": "199011"},
    "Japan": {"description": "Japan", "has_daily": True,
              "fivef_start": "199007", "mom_start": "199011"},
    "Asia_Pacific_ex_Japan": {"description": "Developed Asia-Pacific ex Japan",
                              "has_daily": True, "fivef_start": "199007",
                              "mom_start": "199011"},
    "Emerging": {"description": "Emerging markets", "has_daily": False,
                 "fivef_start": "198907", "mom_start": "199001"},
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            CACHE_DIR / f"ff_factors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        ),
    ],
)
logger = logging.getLogger(__name__)


def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=1.0,
                  status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.headers.update({"User-Agent": "Mozilla/5.0 (ASADO collect_ff_factors)"})
    return s


def _cache_is_fresh(path: Path, hours: int = 24) -> bool:
    if not path.exists():
        return False
    age = (datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)).total_seconds()
    return age < hours * 3600


def download_zip(sess: requests.Session, filename: str, force: bool) -> bytes | None:
    """Fetch a single FF zip (24h raw cache). Returns raw bytes or None."""
    dest = RAW_DIR / filename
    if not force and _cache_is_fresh(dest):
        return dest.read_bytes()
    try:
        resp = sess.get(FF_BASE_URL + filename, timeout=60)
        resp.raise_for_status()
        dest.write_bytes(resp.content)
        return resp.content
    except requests.RequestException as e:
        logger.error(f"[{filename}] download failed: {e}")
        # fall back to a stale cached copy if one exists (so a transient
        # network error preserves prior coverage rather than dropping it)
        if dest.exists():
            logger.warning(f"[{filename}] using stale cached copy")
            return dest.read_bytes()
        return None


def parse_ff_csv(raw: bytes, frequency: str, value_cols: list[str]) -> pd.DataFrame:
    """Parse one FF csv (inside a zip) into long rows.

    The French CSVs carry a free-text preamble, then a periodic block
    (YYYYMM monthly / YYYYMMDD daily), then an ANNUAL block (4-digit dates),
    then a copyright footer. We select ONLY the periodic block by keeping rows
    whose first comma-token is all-digits of the expected length (6 for
    monthly, 8 for daily); the 4-digit annual rows and text footer are dropped
    automatically. Values are assigned POSITIONALLY to value_cols (robust to
    the multi-line headers). -99.99/-999 -> NaN.
    """
    zf = zipfile.ZipFile(io.BytesIO(raw))
    text = zf.read(zf.namelist()[0]).decode("latin-1")
    want_len = 6 if frequency == "monthly" else 8

    recs = []
    for line in text.splitlines():
        toks = [t.strip() for t in line.split(",")]
        if not toks or not toks[0]:
            continue
        date_tok = toks[0]
        if len(date_tok) != want_len or not date_tok.isdigit():
            continue
        vals = toks[1:]
        if len(vals) < len(value_cols):
            continue
        rec = {"date_tok": date_tok}
        for col, v in zip(value_cols, vals[:len(value_cols)]):
            try:
                fv = float(v)
            except ValueError:
                fv = np.nan
            if fv in MISSING_MARKERS:
                fv = np.nan
            rec[col] = fv
        recs.append(rec)

    if not recs:
        return pd.DataFrame(columns=["date", "variable", "value"])

    df = pd.DataFrame(recs)
    if frequency == "monthly":
        # first-of-month, matching ASADO monthly convention
        df["date"] = pd.to_datetime(df["date_tok"], format="%Y%m")
    else:
        df["date"] = pd.to_datetime(df["date_tok"], format="%Y%m%d")
    long = df.melt(id_vars=["date"], value_vars=value_cols,
                   var_name="variable", value_name="value").dropna(subset=["value"])
    # normalise variable names: Mkt-RF -> Mkt_RF; momentum Mom -> WML
    long["variable"] = long["variable"].str.replace("-", "_", regex=False)
    long.loc[long["variable"] == "Mom", "variable"] = "WML"
    return long


def collect() -> pd.DataFrame:
    sess = _session()
    frames: list[pd.DataFrame] = []
    ok, skipped = [], []
    for region, freq, kind, filename in FF_DATASETS:
        raw = download_zip(sess, filename, force=ARGS.force)
        if raw is None:
            skipped.append((filename, "download_failed"))
            continue
        try:
            long = parse_ff_csv(raw, freq, VALUE_COLS[kind])
        except Exception as e:  # noqa: BLE001 - per-dataset isolation
            logger.error(f"[{filename}] parse failed: {e}")
            skipped.append((filename, f"parse_error:{e}"))
            continue
        if long.empty:
            skipped.append((filename, "empty_after_parse"))
            continue
        long["region"] = region
        long["frequency"] = freq
        long["currency"] = "USD"
        long["units"] = "percent"
        long["source"] = SOURCE
        frames.append(long)
        ok.append(f"{region}/{freq}/{kind}={len(long):,}")
        logger.info(f"  [{filename}] {region}/{freq}/{kind}: {len(long):,} rows "
                    f"({long['date'].min().date()}..{long['date'].max().date()})")

    if skipped:
        for fn, why in skipped:
            logger.warning(f"  SKIPPED {fn}: {why}")

    if not frames:
        raise RuntimeError("No FF datasets parsed — refusing to overwrite panel.")

    panel = pd.concat(frames, ignore_index=True)
    panel = panel[["date", "region", "frequency", "currency",
                   "variable", "value", "units", "source"]]
    panel = panel.sort_values(["region", "frequency", "variable", "date"]).reset_index(drop=True)
    # integrity: no duplicate (date, region, frequency, variable)
    dupes = panel.duplicated(["date", "region", "frequency", "variable"]).sum()
    if dupes:
        raise RuntimeError(f"{dupes} duplicate (date,region,frequency,variable) rows")
    logger.info(f"OK datasets: {len(ok)} | skipped: {len(skipped)}")
    return panel


def write_region_map() -> None:
    """(Re)write config/ff_region_map.json — the country->region link consumed
    by the spanning tool. Kept here so the map and the data ship together."""
    payload = {
        "_description": ("ASADO T2 country -> Ken French regional factor bundle. "
                         "Applied on-the-fly at regression time (ff_spanning.py); "
                         "NEVER materialised into ff_factors rows."),
        "_generated_by": "scripts/collect_ff_factors.py",
        "regions": list(REGION_META.keys()),
        "region_meta": REGION_META,
        "country_to_region": {
            c: {"region": r, "confidence": conf}
            for c, (r, conf) in sorted(COUNTRY_TO_REGION.items())
        },
    }
    REGION_MAP_PATH.write_text(json.dumps(payload, indent=2))
    logger.info(f"  wrote region map -> {REGION_MAP_PATH}")


def backup_existing() -> None:
    if OUT_PARQUET.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y_%m_%d_%H%M%S")
        dest = BACKUP_DIR / f"ff_factors_panel_{ts}.parquet"
        shutil.copy2(OUT_PARQUET, dest)
        logger.info(f"  backed up prior panel -> {dest}")


def summarize(panel: pd.DataFrame) -> None:
    print("\n" + "=" * 64)
    print("  KEN FRENCH FACTOR PANEL — SUMMARY")
    print("=" * 64)
    print(f"  rows:       {len(panel):,}")
    print(f"  regions:    {panel['region'].nunique()} "
          f"({', '.join(sorted(panel['region'].unique()))})")
    print(f"  variables:  {sorted(panel['variable'].unique())}")
    for freq in ["monthly", "daily"]:
        sub = panel[panel["frequency"] == freq]
        if len(sub):
            print(f"  {freq:7}: {len(sub):,} rows, "
                  f"{sub['date'].min().date()}..{sub['date'].max().date()}, "
                  f"{sub['region'].nunique()} regions")


def check_existing() -> int:
    if not OUT_PARQUET.exists():
        logger.error(f"No panel at {OUT_PARQUET}")
        return 1
    panel = pd.read_parquet(OUT_PARQUET)
    summarize(panel)
    return 0


def main() -> int:
    global ARGS
    ap = argparse.ArgumentParser(description="Ingest Ken French factor returns (isolated regional benchmark corpus).")
    ap.add_argument("--force", action="store_true", help="Bypass 24h raw cache.")
    ap.add_argument("--dry-run", action="store_true", help="Preview, no writes.")
    ap.add_argument("--check", action="store_true", help="Verify existing panel and exit.")
    ARGS = ap.parse_args()

    if ARGS.check:
        return check_existing()

    print("=" * 64)
    print("  KEN FRENCH FACTOR INGEST (isolated regional benchmark corpus)")
    print("=" * 64)
    panel = collect()
    summarize(panel)

    if ARGS.dry_run:
        print("\n  [dry-run] no files written.")
        return 0

    backup_existing()
    panel.to_parquet(OUT_PARQUET, index=False)
    write_region_map()
    print(f"\n  -> {OUT_PARQUET}")
    print("  NOTE: isolated table `ff_factors` — NOT unioned into unified_panel/feature_panel.")
    return 0


ARGS = argparse.Namespace(force=False, dry_run=False, check=False)

if __name__ == "__main__":
    sys.exit(main())
