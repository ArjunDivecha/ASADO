#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/build_daily_panels.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy Daily/
    Normalized_T2_MasterCSV.csv            (34.8M rows, 109 normalized _CS/_TS
                                            variables, 34 countries, 2000-01-01
                                            to 2026-05-07; tidy long format)
    T2MasterDaily.xlsx                     (57 sheets, raw factor levels —
                                            PX_LAST, Tot Return Index, MCAP,
                                            RSI14 raw, REER raw, etc.; wide
                                            format, one sheet per variable)
    T2_Optimizer_Top.xlsx                  (selected-factor list — the 8
                                            factors the optimizer actually
                                            uses to drive the strategy)
    T2_Optimizer.xlsx                     (9,552 rows, 84 columns, daily factor
                                            returns from T2 optimizer; sheet
                                            Monthly_Net_Returns, 2000-01-01 →
                                            2026-02-24)

- /Users/arjundivecha/Dropbox/AAA Backup/A Complete/GDELT Factor Timing Fuzzy Daily/
    T2-Factor-Timing-Daily/GDELT_Factors_MasterCSV.csv
                                           (11.6M rows, 87 normalized GDELT
                                            factors aligned to the 34-country
                                            T2 universe, 2015-06-24 to
                                            2026-04-19; tidy long format)
    T2-Factor-Timing-Daily/GDELT_Optimizer.xlsx
                                           (3,955 rows, 75 columns, daily factor
                                            returns from GDELT optimizer; sheet
                                            Monthly_Net_Returns, 2015-06-24 →
                                            2026-05-08)

- /Users/arjundivecha/Dropbox/AAA Backup/A Complete/GDELT/data/panels/
    country_signal_daily.parquet           (955K rows, 45 columns, raw GDELT
                                            for 249 ISO3 countries — the
                                            off-universe entity bridge)

OUTPUT TABLES (added to Data/asado.duckdb, additive — existing tables untouched):
- t2_factors_daily            normalized _CS/_TS daily panel  (~34M rows)
- t2_levels_daily             raw factor levels daily panel   (~18M rows)
- gdelt_factors_daily         34-country normalized GDELT     (~11.6M rows)
- gdelt_raw_daily             249-country raw GDELT signals   (~955K rows)
- factor_returns_daily        daily optimizer factor returns  (~1.2M rows)
- variable_meta               frequency / optimizer-selected / source mapping
- daily_calendar              (country, date, is_trading_day) derived from
                              non-null 1DRet observations
- t2_factors_monthly_from_daily  VIEW: last-trading-day-of-month snapshot
                                       of t2_factors_daily, for validation
                                       against existing t2_master

VERSION: 1.0
LAST UPDATED: 2026-05-08
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
Stage 1 of the ASADO daily extension. Adds four new daily tables alongside
the existing monthly tables in asado.duckdb, plus a variable_meta registry
and a daily trading calendar. Existing tables (t2_master, gdelt_panel,
t2_raw, factor_returns, etc.) are NOT touched.

The variable_meta table is the key unlock: every variable gets tagged with
its native frequency, monthly equivalent (so "1MRet" can route to "20DRet"
on the daily side), source file, category, and an is_optimizer_selected
flag derived from T2_Optimizer_Top.xlsx.

The script always backs up asado.duckdb before writing. On any failure,
new tables are dropped and the backup is restored.

DEPENDENCIES:
- duckdb >= 0.10, pandas, openpyxl, pyarrow

USAGE:
  python scripts/build_daily_panels.py              # full additive load
  python scripts/build_daily_panels.py --check      # report on existing tables
  python scripts/build_daily_panels.py --rebuild    # drop & rebuild daily tables
  python scripts/build_daily_panels.py --skip-levels  # skip slow xlsx parse
  python scripts/build_daily_panels.py --validate   # compare daily EOM vs t2_master
  python scripts/build_daily_panels.py --no-backup  # skip DB backup (faster)

NOTES:
- The Normalized CSV has ~2.5M epoch-dated (1970-01-01) rows from Bloomberg
  BEST-forecast warm-up periods; these are filtered on ingest.
- T2MasterDaily.xlsx parsing is slow (~3-5 min for 57 sheets, 121 MB).
  Use --skip-levels during iteration; run once for the canonical load.
- DB grows from ~800 MB to ~4-5 GB after this script. Backup adds another
  ~800 MB temporarily.
- Idempotent: re-running with the same inputs is a no-op (mtime check).
=============================================================================
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import duckdb
import pandas as pd

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "Data" / "asado.duckdb"
BACKUP_PATH = BASE_DIR / "Data" / "asado.duckdb.backup"

T2_DAILY_DIR = Path(
    "/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy Daily"
)
GDELT_DAILY_DIR = Path(
    "/Users/arjundivecha/Dropbox/AAA Backup/A Complete/GDELT Factor Timing Fuzzy Daily/T2-Factor-Timing-Daily"
)
GDELT_RAW_DIR = Path(
    "/Users/arjundivecha/Dropbox/AAA Backup/A Working/GDELT/data/panels"
)

T2_NORMALIZED_CSV = T2_DAILY_DIR / "Normalized_T2_MasterCSV.csv"
T2_LEVELS_XLSX    = T2_DAILY_DIR / "T2MasterDaily.xlsx"
T2_OPTIMIZER_TOP  = T2_DAILY_DIR / "T2_Optimizer_Top.xlsx"
T2_OPTIMIZER_RETURNS = T2_DAILY_DIR / "T2_Optimizer.xlsx"
GDELT_FACTORS_CSV = GDELT_DAILY_DIR / "GDELT_Factors_MasterCSV.csv"
GDELT_OPTIMIZER_RETURNS = GDELT_DAILY_DIR / "GDELT_Optimizer.xlsx"
GDELT_RAW_PQ      = GDELT_RAW_DIR / "country_signal_daily.parquet"

# Tables added by this script
NEW_TABLES = [
    "t2_factors_daily",
    "t2_levels_daily",
    "gdelt_factors_daily",
    "gdelt_raw_daily",
    "factor_returns_daily",
    "variable_meta",
    "daily_calendar",
]
NEW_VIEWS = ["t2_factors_monthly_from_daily"]

# Sheets in T2MasterDaily.xlsx that are *return* sheets (already _CS/_TS in
# normalized CSV — skip on the levels load to avoid duplication; keep raw
# levels and the few derived signals only)
T2_LEVELS_SKIP_SHEETS = {
    "1MRet", "3MRet", "6MRet", "9MRet", "12MRet",
    "1MTR", "3MTR", "12MTR", "12-1MTR",
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Pre-flight
# ═══════════════════════════════════════════════════════════════════════════════

def check_inputs(skip_levels: bool = False) -> List[Path]:
    """Verify all required input files exist. Returns list of missing files."""
    required = [T2_NORMALIZED_CSV, GDELT_FACTORS_CSV, GDELT_RAW_PQ, T2_OPTIMIZER_TOP,
               T2_OPTIMIZER_RETURNS, GDELT_OPTIMIZER_RETURNS]
    if not skip_levels:
        required.append(T2_LEVELS_XLSX)
    missing = [p for p in required if not p.exists()]
    return missing


def backup_database(no_backup: bool = False) -> Optional[Path]:
    """Copy asado.duckdb → asado.duckdb.backup. Returns backup path or None."""
    if no_backup or not DB_PATH.exists():
        return None
    if BACKUP_PATH.exists():
        BACKUP_PATH.unlink()
    log.info("Backing up DB → %s", BACKUP_PATH.name)
    shutil.copy2(DB_PATH, BACKUP_PATH)
    return BACKUP_PATH


def restore_backup() -> None:
    """Restore the DB from backup (called on failure)."""
    if BACKUP_PATH.exists():
        log.warning("Restoring DB from backup ...")
        if DB_PATH.exists():
            DB_PATH.unlink()
        shutil.move(str(BACKUP_PATH), str(DB_PATH))


# ═══════════════════════════════════════════════════════════════════════════════
# Loaders
# ═══════════════════════════════════════════════════════════════════════════════

def load_t2_factors_daily(con: duckdb.DuckDBPyConnection) -> int:
    """
    Load Normalized_T2_MasterCSV.csv → t2_factors_daily.
    Filters out 1970-01-01 epoch rows from Bloomberg BEST-forecast warm-ups.
    """
    log.info("Loading t2_factors_daily ...")
    t0 = time.time()
    con.execute("DROP TABLE IF EXISTS t2_factors_daily")
    con.execute(f"""
        CREATE TABLE t2_factors_daily AS
        SELECT
            CAST(date AS DATE) AS date,
            country,
            value,
            variable
        FROM read_csv_auto('{T2_NORMALIZED_CSV}', SAMPLE_SIZE=-1)
        WHERE date >= DATE '2000-01-01'
    """)
    n = con.execute("SELECT COUNT(*) FROM t2_factors_daily").fetchone()[0]
    nv = con.execute("SELECT COUNT(DISTINCT variable) FROM t2_factors_daily").fetchone()[0]
    nc = con.execute("SELECT COUNT(DISTINCT country) FROM t2_factors_daily").fetchone()[0]
    dmin, dmax = con.execute("SELECT MIN(date), MAX(date) FROM t2_factors_daily").fetchone()
    log.info("  t2_factors_daily: %s rows | %d vars | %d countries | %s → %s | %.1fs",
             f"{n:,}", nv, nc, dmin, dmax, time.time() - t0)
    return n


def load_gdelt_factors_daily(con: duckdb.DuckDBPyConnection) -> int:
    """Load GDELT_Factors_MasterCSV.csv → gdelt_factors_daily."""
    log.info("Loading gdelt_factors_daily ...")
    t0 = time.time()
    con.execute("DROP TABLE IF EXISTS gdelt_factors_daily")
    con.execute(f"""
        CREATE TABLE gdelt_factors_daily AS
        SELECT
            CAST(date AS DATE) AS date,
            country,
            value,
            variable
        FROM read_csv_auto('{GDELT_FACTORS_CSV}', SAMPLE_SIZE=-1)
        WHERE date IS NOT NULL
    """)
    n = con.execute("SELECT COUNT(*) FROM gdelt_factors_daily").fetchone()[0]
    nv = con.execute("SELECT COUNT(DISTINCT variable) FROM gdelt_factors_daily").fetchone()[0]
    nc = con.execute("SELECT COUNT(DISTINCT country) FROM gdelt_factors_daily").fetchone()[0]
    dmin, dmax = con.execute("SELECT MIN(date), MAX(date) FROM gdelt_factors_daily").fetchone()
    log.info("  gdelt_factors_daily: %s rows | %d vars | %d countries | %s → %s | %.1fs",
             f"{n:,}", nv, nc, dmin, dmax, time.time() - t0)
    return n


def load_gdelt_raw_daily(con: duckdb.DuckDBPyConnection) -> int:
    """
    Load country_signal_daily.parquet → gdelt_raw_daily.
    Wide format (45 columns). Keep as wide — this is the off-universe
    entity bridge (249 ISO3 countries, includes Iran, Russia, etc.).
    """
    log.info("Loading gdelt_raw_daily ...")
    t0 = time.time()
    con.execute("DROP TABLE IF EXISTS gdelt_raw_daily")
    con.execute(f"""
        CREATE TABLE gdelt_raw_daily AS
        SELECT * FROM read_parquet('{GDELT_RAW_PQ}')
    """)
    n = con.execute("SELECT COUNT(*) FROM gdelt_raw_daily").fetchone()[0]
    nc = con.execute("SELECT COUNT(DISTINCT country_iso3) FROM gdelt_raw_daily").fetchone()[0]
    dmin, dmax = con.execute("SELECT MIN(date), MAX(date) FROM gdelt_raw_daily").fetchone()
    log.info("  gdelt_raw_daily: %s rows | %d ISO3 countries | %s → %s | %.1fs",
             f"{n:,}", nc, dmin, dmax, time.time() - t0)
    return n


def load_t2_levels_daily(con: duckdb.DuckDBPyConnection) -> int:
    """
    Load T2MasterDaily.xlsx → t2_levels_daily (tidy long format).
    Wide format input: 57 sheets, each (Country=date, country_1, country_2, ...).
    Skips return sheets (already in normalized CSV with _CS/_TS variants).
    """
    log.info("Loading t2_levels_daily (parsing %s, this takes 3-5 min) ...",
             T2_LEVELS_XLSX.name)
    t0 = time.time()
    con.execute("DROP TABLE IF EXISTS t2_levels_daily")
    con.execute("""
        CREATE TABLE t2_levels_daily (
            date DATE,
            country VARCHAR,
            value DOUBLE,
            variable VARCHAR
        )
    """)

    total = 0
    with pd.ExcelFile(T2_LEVELS_XLSX, engine="openpyxl") as wb:
        sheets_to_load = [s for s in wb.sheet_names if s not in T2_LEVELS_SKIP_SHEETS]
        log.info("  parsing %d sheets (skipping %d return sheets) ...",
                 len(sheets_to_load), len(T2_LEVELS_SKIP_SHEETS))

        for i, sheet in enumerate(sheets_to_load, 1):
            wide = pd.read_excel(wb, sheet_name=sheet)
            if wide.empty:
                continue

            date_col = wide.columns[0]
            long = (
                wide.rename(columns={date_col: "date"})
                .melt(id_vars="date", var_name="country", value_name="value")
                .dropna(subset=["date", "value"])
            )
            if long.empty:
                continue

            long["date"] = pd.to_datetime(long["date"], errors="coerce").dt.date
            long = long.dropna(subset=["date"])
            long["country"] = long["country"].astype(str).str.strip()
            long["variable"] = sheet.strip()
            long = long[long["date"] >= pd.Timestamp("2000-01-01").date()]

            con.register("levels_stage", long[["date", "country", "value", "variable"]])
            con.execute("""
                INSERT INTO t2_levels_daily
                SELECT
                    CAST(date AS DATE) AS date,
                    country,
                    CAST(value AS DOUBLE) AS value,
                    variable
                FROM levels_stage
            """)
            con.unregister("levels_stage")
            total += len(long)
            if i % 10 == 0:
                log.info("    sheet %d/%d done (%s rows so far)",
                         i, len(sheets_to_load), f"{total:,}")

    nv = con.execute("SELECT COUNT(DISTINCT variable) FROM t2_levels_daily").fetchone()[0]
    nc = con.execute("SELECT COUNT(DISTINCT country) FROM t2_levels_daily").fetchone()[0]
    dmin, dmax = con.execute("SELECT MIN(date), MAX(date) FROM t2_levels_daily").fetchone()
    log.info("  t2_levels_daily: %s rows | %d vars | %d countries | %s → %s | %.1fs",
             f"{total:,}", nv, nc, dmin, dmax, time.time() - t0)
    return total


def load_factor_returns_daily(con: duckdb.DuckDBPyConnection) -> int:
    """
    Load T2 and GDELT optimizer daily factor returns → factor_returns_daily.
    Optimizer files are in wide format (Date, factor1_return, factor2_return, ...).
    Pivot to tidy long format matching monthly factor_returns schema.
    """
    log.info("Loading factor_returns_daily from optimizer outputs ...")
    t0 = time.time()
    con.execute("DROP TABLE IF EXISTS factor_returns_daily")
    con.execute("""
        CREATE TABLE factor_returns_daily (
            date DATE,
            factor VARCHAR,
            value DOUBLE,
            source VARCHAR
        )
    """)

    # T2 Optimizer returns
    t2_returns = pd.read_excel(T2_OPTIMIZER_RETURNS, sheet_name="Monthly_Net_Returns")
    t2_returns["Date"] = pd.to_datetime(t2_returns["Date"]).dt.date
    t2_long = (
        t2_returns.melt(id_vars="Date", var_name="factor", value_name="value")
        .dropna(subset=["Date", "value"])
        .rename(columns={"Date": "date"})
    )
    t2_long["source"] = "t2_optimizer_daily"
    con.register("t2_returns_stage", t2_long[["date", "factor", "value", "source"]])
    con.execute("""
        INSERT INTO factor_returns_daily
        SELECT CAST(date AS DATE) AS date, factor, CAST(value AS DOUBLE) AS value, source
        FROM t2_returns_stage
    """)
    con.unregister("t2_returns_stage")
    t2_count = len(t2_long)
    log.info("  T2 optimizer: %s rows | %d factors | %s → %s",
             f"{t2_count:,}", len(t2_returns.columns) - 1,
             t2_returns["Date"].min(), t2_returns["Date"].max())

    # GDELT Optimizer returns
    gdelt_returns = pd.read_excel(GDELT_OPTIMIZER_RETURNS, sheet_name="Monthly_Net_Returns")
    gdelt_returns["Date"] = pd.to_datetime(gdelt_returns["Date"]).dt.date
    gdelt_long = (
        gdelt_returns.melt(id_vars="Date", var_name="factor", value_name="value")
        .dropna(subset=["Date", "value"])
        .rename(columns={"Date": "date"})
    )
    gdelt_long["source"] = "gdelt_optimizer_daily"
    con.register("gdelt_returns_stage", gdelt_long[["date", "factor", "value", "source"]])
    con.execute("""
        INSERT INTO factor_returns_daily
        SELECT CAST(date AS DATE) AS date, factor, CAST(value AS DOUBLE) AS value, source
        FROM gdelt_returns_stage
    """)
    con.unregister("gdelt_returns_stage")
    gdelt_count = len(gdelt_long)
    log.info("  GDELT optimizer: %s rows | %d factors | %s → %s",
             f"{gdelt_count:,}", len(gdelt_returns.columns) - 1,
             gdelt_returns["Date"].min(), gdelt_returns["Date"].max())

    total = t2_count + gdelt_count
    nf = con.execute("SELECT COUNT(DISTINCT factor) FROM factor_returns_daily").fetchone()[0]
    ns = con.execute("SELECT COUNT(DISTINCT source) FROM factor_returns_daily").fetchone()[0]
    dmin, dmax = con.execute("SELECT MIN(date), MAX(date) FROM factor_returns_daily").fetchone()
    log.info("  factor_returns_daily: %s rows | %d factors | %d sources | %s → %s | %.1fs",
             f"{total:,}", nf, ns, dmin, dmax, time.time() - t0)
    return total


# ═══════════════════════════════════════════════════════════════════════════════
# Metadata + calendar
# ═══════════════════════════════════════════════════════════════════════════════

def build_variable_meta(con: duckdb.DuckDBPyConnection) -> int:
    """
    Build variable_meta: one row per variable across all daily tables, tagged
    with native_frequency, monthly_equivalent, category, source_file, and
    is_optimizer_selected (read from T2_Optimizer_Top.xlsx).
    """
    log.info("Building variable_meta ...")
    t0 = time.time()

    # ── Read optimizer-selected factors ────────────────────────────────────
    opt = pd.read_excel(T2_OPTIMIZER_TOP, sheet_name=0)
    selected = [c.strip() for c in opt.columns
                if c not in ("Date", "Return ", "Next ", "Return", "Next")]
    log.info("  optimizer-selected factors (%d): %s", len(selected), selected)

    # ── Categorize variables ───────────────────────────────────────────────
    def categorize(v: str) -> str:
        v_low = v.lower()
        if any(t in v_low for t in ["ret", "tr_", "dtr", "120-5"]): return "return"
        if any(t in v_low for t in ["rsi", "120ma", "advance dec", "p2p"]): return "technical"
        if any(t in v_low for t in ["vol", "currency vol"]): return "volatility"
        if any(t in v_low for t in ["pe", "pbk", "yield", "cash flow", "ebitda",
                                     "eps", "roe", "margin", "price sales", "shiller"]): return "valuation_fund"
        if any(t in v_low for t in ["gdp", "inflation", "current account",
                                     "debt", "budget", "lt growth"]): return "macro"
        if any(t in v_low for t in ["gold", "copper", "oil", "agriculture"]): return "commodity"
        if any(t in v_low for t in ["currency", "reer"]): return "fx"
        if any(t in v_low for t in ["10yr bond", "bond"]): return "rates"
        if any(t in v_low for t in ["mcap"]): return "size"
        if any(t in v_low for t in ["bloom country risk"]): return "risk"
        # GDELT
        if any(t in v_low for t in ["tone", "sentiment", "attention", "risk_",
                                     "metronome", "defensive", "dispersion",
                                     "n_articles", "negative_mean", "lf_gap",
                                     "local_", "foreign_"]): return "gdelt_signal"
        return "other"

    # ── Map daily naming to monthly equivalents ────────────────────────────
    # Daily uses 1DRet/5DRet/20DRet/60DRet/120DRet; monthly uses 1MRet/3MRet/12MRet.
    # Approximate: 20DRet ≈ 1MRet, 60DRet ≈ 3MRet, 120DRet ≈ 6MRet, etc.
    monthly_equiv_map = {
        "1DRet": None,            # no monthly equivalent (intraday-ish)
        "5DRet": None,
        "20DRet": "1MRet",
        "60DRet": "3MRet",
        "120DRet": None,          # ~6M; not in current monthly t2_master
        "1DTR_CS": None,  "1DTR_TS": None,
        "5DTR_CS": None,  "5DTR_TS": None,
        "20DTR_CS": "1MTR_CS", "20DTR_TS": "1MTR_TS",
        "120DTR_CS": "12MTR_CS", "120DTR_TS": "12MTR_TS",
        "120-5DTR_CS": "12-1MTR_CS", "120-5DTR_TS": "12-1MTR_TS",
    }

    rows: List[Dict] = []

    # T2 normalized vars
    t2_vars = [r[0] for r in con.execute(
        "SELECT DISTINCT variable FROM t2_factors_daily ORDER BY variable").fetchall()]
    for v in t2_vars:
        rows.append({
            "variable": v,
            "source_table": "t2_factors_daily",
            "source_file": "Normalized_T2_MasterCSV.csv",
            "native_frequency": "D",
            "monthly_equivalent": monthly_equiv_map.get(v, None),
            "is_normalized": v.endswith("_CS") or v.endswith("_TS"),
            "category": categorize(v),
            "is_optimizer_selected": v in selected,
        })

    # T2 levels (raw)
    try:
        levels_vars = [r[0] for r in con.execute(
            "SELECT DISTINCT variable FROM t2_levels_daily ORDER BY variable").fetchall()]
    except Exception:
        levels_vars = []
    for v in levels_vars:
        rows.append({
            "variable": v,
            "source_table": "t2_levels_daily",
            "source_file": "T2MasterDaily.xlsx",
            "native_frequency": "D",
            "monthly_equivalent": None,
            "is_normalized": False,
            "category": categorize(v),
            "is_optimizer_selected": False,
        })

    # GDELT factors
    g_vars = [r[0] for r in con.execute(
        "SELECT DISTINCT variable FROM gdelt_factors_daily ORDER BY variable").fetchall()]
    for v in g_vars:
        rows.append({
            "variable": v,
            "source_table": "gdelt_factors_daily",
            "source_file": "GDELT_Factors_MasterCSV.csv",
            "native_frequency": "D",
            "monthly_equivalent": None,
            "is_normalized": v.endswith("_CS") or v.endswith("_TS"),
            "category": categorize(v),
            "is_optimizer_selected": False,
        })

    # GDELT raw (wide-format columns, treat each column as a variable)
    g_raw_cols = [r[0] for r in con.execute("DESCRIBE gdelt_raw_daily").fetchall()
                  if r[0] not in ("date", "country_code_gdelt", "country_name",
                                   "country_iso3", "day_status", "top_themes_json",
                                   "has_country_day_data")]
    for v in g_raw_cols:
        rows.append({
            "variable": v,
            "source_table": "gdelt_raw_daily",
            "source_file": "country_signal_daily.parquet",
            "native_frequency": "D",
            "monthly_equivalent": None,
            "is_normalized": v.endswith("_z"),
            "category": "gdelt_raw",
            "is_optimizer_selected": False,
        })

    # Prediction-market derived signals (if Stage 2 table exists).
    tables = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    if "predmkt_signals_daily" in tables:
        p_vars = [
            r[0]
            for r in con.execute(
                "SELECT DISTINCT signal_name FROM predmkt_signals_daily ORDER BY signal_name"
            ).fetchall()
            if r[0]
        ]
        for v in p_vars:
            rows.append({
                "variable": v,
                "source_table": "predmkt_signals_daily",
                "source_file": "predmkt_derived",
                "native_frequency": "D",
                "monthly_equivalent": None,
                "is_normalized": False,
                "category": "predmkt_signal",
                "is_optimizer_selected": False,
            })

    # Monthly World Bank Pink Sheet commodity context. These are global
    # explanatory features broadcast to the ASADO country panel; they are not
    # daily data and are not optimizer return outputs.
    if "wb_commodity_factor_panel" in tables:
        c_vars = [
            r[0]
            for r in con.execute(
                "SELECT DISTINCT variable FROM wb_commodity_factor_panel ORDER BY variable"
            ).fetchall()
            if r[0]
        ]
        for v in c_vars:
            rows.append({
                "variable": v,
                "source_table": "wb_commodity_factor_panel",
                "source_file": "wb_commodity_factor_panel.parquet",
                "native_frequency": "monthly",
                "monthly_equivalent": v,
                "is_normalized": False,
                "category": "commodity",
                "is_optimizer_selected": False,
                "freshness_expectation": "monthly",
            })

    for row in rows:
        row.setdefault(
            "freshness_expectation",
            "daily" if row.get("native_frequency") == "D" else row.get("native_frequency"),
        )

    meta_df = pd.DataFrame(rows)
    con.execute("DROP TABLE IF EXISTS variable_meta")
    con.register("meta_stage", meta_df)
    con.execute("""
        CREATE TABLE variable_meta AS
        SELECT
            variable,
            source_table,
            source_file,
            native_frequency,
            monthly_equivalent,
            CAST(is_normalized AS BOOLEAN) AS is_normalized,
            category,
            CAST(is_optimizer_selected AS BOOLEAN) AS is_optimizer_selected,
            freshness_expectation
        FROM meta_stage
    """)
    con.unregister("meta_stage")

    n = con.execute("SELECT COUNT(*) FROM variable_meta").fetchone()[0]
    n_opt = con.execute(
        "SELECT COUNT(*) FROM variable_meta WHERE is_optimizer_selected").fetchone()[0]
    log.info("  variable_meta: %d rows | %d optimizer-selected | %.1fs",
             n, n_opt, time.time() - t0)
    return n


def build_daily_calendar(con: duckdb.DuckDBPyConnection) -> int:
    """
    Build daily_calendar from t2_factors_daily — a country has a trading day
    on dates where it has a non-null 1DRet observation.
    """
    log.info("Building daily_calendar ...")
    t0 = time.time()
    con.execute("DROP TABLE IF EXISTS daily_calendar")
    con.execute("""
        CREATE TABLE daily_calendar AS
        WITH all_dates AS (
            SELECT DISTINCT date FROM t2_factors_daily
        ),
        all_countries AS (
            SELECT DISTINCT country FROM t2_factors_daily
        ),
        all_pairs AS (
            SELECT d.date, c.country
            FROM all_dates d CROSS JOIN all_countries c
        ),
        trading_days AS (
            SELECT date, country
            FROM t2_factors_daily
            WHERE variable = '1DRet' AND value IS NOT NULL AND value <> 0
            GROUP BY date, country
        )
        SELECT
            ap.date,
            ap.country,
            (td.date IS NOT NULL) AS is_trading_day
        FROM all_pairs ap
        LEFT JOIN trading_days td
          ON td.date = ap.date AND td.country = ap.country
    """)
    n = con.execute("SELECT COUNT(*) FROM daily_calendar").fetchone()[0]
    n_td = con.execute(
        "SELECT COUNT(*) FROM daily_calendar WHERE is_trading_day").fetchone()[0]
    log.info("  daily_calendar: %s rows | %s trading days | %.1fs",
             f"{n:,}", f"{n_td:,}", time.time() - t0)
    return n


def build_monthly_view(con: duckdb.DuckDBPyConnection) -> None:
    """Last-trading-day-of-month snapshot view for validation."""
    log.info("Creating t2_factors_monthly_from_daily view ...")
    con.execute("DROP VIEW IF EXISTS t2_factors_monthly_from_daily")
    con.execute("""
        CREATE VIEW t2_factors_monthly_from_daily AS
        WITH eom AS (
            SELECT
                DATE_TRUNC('month', date) AS month_start,
                country,
                MAX(date) AS last_trading_day
            FROM daily_calendar
            WHERE is_trading_day
            GROUP BY 1, 2
        )
        SELECT
            eom.month_start AS date,
            t.country,
            t.value,
            t.variable
        FROM eom
        JOIN t2_factors_daily t
          ON t.country = eom.country AND t.date = eom.last_trading_day
    """)


# ═══════════════════════════════════════════════════════════════════════════════
# Indexes + validation
# ═══════════════════════════════════════════════════════════════════════════════

def create_indexes(con: duckdb.DuckDBPyConnection) -> None:
    log.info("Creating indexes on daily tables ...")
    for tbl in ["t2_factors_daily", "t2_levels_daily", "gdelt_factors_daily"]:
        try:
            con.execute(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_ctry_date ON {tbl}(country, date)")
            con.execute(f"CREATE INDEX IF NOT EXISTS idx_{tbl}_var ON {tbl}(variable)")
        except Exception as e:
            log.warning("  index on %s skipped (%s)", tbl, e)
    try:
        con.execute("CREATE INDEX IF NOT EXISTS idx_gdelt_raw_iso3_date "
                    "ON gdelt_raw_daily(country_iso3, date)")
    except Exception as e:
        log.warning("  index on gdelt_raw_daily skipped (%s)", e)
    try:
        con.execute("CREATE INDEX IF NOT EXISTS idx_factor_ret_daily_date_factor "
                    "ON factor_returns_daily(date, factor)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_factor_ret_daily_source "
                    "ON factor_returns_daily(source)")
    except Exception as e:
        log.warning("  index on factor_returns_daily skipped (%s)", e)
    try:
        con.execute("CREATE INDEX IF NOT EXISTS idx_var_meta_var "
                    "ON variable_meta(variable)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_daily_cal_ctry_date "
                    "ON daily_calendar(country, date)")
    except Exception as e:
        log.warning("  meta/calendar index skipped (%s)", e)


def validate_against_monthly(con: duckdb.DuckDBPyConnection) -> None:
    """
    Sanity check: compare last-trading-day-of-month from daily vs the
    existing monthly t2_master for a few overlap dates.
    Reports correlation per variable across the panel.
    """
    log.info("Validating daily-EOM vs monthly t2_master ...")
    try:
        result = con.execute("""
            WITH overlap AS (
                SELECT
                    m.country,
                    m.variable,
                    m.date,
                    m.value AS monthly_value,
                    d.value AS daily_eom_value
                FROM t2_master m
                JOIN t2_factors_monthly_from_daily d
                  ON d.country = m.country
                 AND d.variable = m.variable
                 AND d.date = m.date
                WHERE m.value IS NOT NULL AND d.value IS NOT NULL
            )
            SELECT
                variable,
                COUNT(*) AS n_obs,
                CORR(monthly_value, daily_eom_value) AS correlation,
                AVG(ABS(monthly_value - daily_eom_value)) AS mean_abs_diff
            FROM overlap
            GROUP BY variable
            HAVING COUNT(*) > 50
            ORDER BY correlation ASC
            LIMIT 10
        """).fetchdf()
        if len(result) == 0:
            log.warning("  no overlap rows found — variables may not align "
                        "(monthly uses 1MRet/3MRet, daily uses 1DRet/20DRet)")
        else:
            log.info("  worst-correlated overlapping variables:")
            for _, row in result.iterrows():
                log.info("    %-30s n=%d corr=%.4f mae=%.6f",
                         row["variable"], row["n_obs"], row["correlation"],
                         row["mean_abs_diff"])
    except Exception as e:
        log.warning("  validation query failed: %s", e)


# ═══════════════════════════════════════════════════════════════════════════════
# Check / report
# ═══════════════════════════════════════════════════════════════════════════════

def check_commodity_context(con: duckdb.DuckDBPyConnection, existing: set[str]) -> None:
    """Report monthly commodity context availability for daily/event workflows."""
    if "wb_commodity_prices" not in existing:
        log.info("  %-25s missing", "wb_commodity_prices")
        return

    try:
        series_count, latest = con.execute("""
            SELECT COUNT(DISTINCT commodity_code), MAX(date)
            FROM wb_commodity_prices
        """).fetchone()
        if latest is None:
            log.info("  %-25s %12s", "wb_commodity_prices", "empty")
            return
        latest_date = pd.to_datetime(latest).date()
        age_days = (datetime.now().date() - latest_date).days
        status = "stale" if age_days > 95 else "ok"
        log.info(
            "  %-25s %12s series | latest=%s | age_days=%d | status=%s",
            "wb_commodity_prices",
            f"{series_count:,}",
            latest_date,
            age_days,
            status,
        )
    except Exception as exc:
        log.error("  %-25s ERROR: %s", "wb_commodity_prices", exc)


def check_existing_tables() -> None:
    """Report on the daily tables in the existing DB."""
    if not DB_PATH.exists():
        log.error("Database not found: %s", DB_PATH)
        return
    con = duckdb.connect(str(DB_PATH), read_only=True)
    log.info("DB: %s (%.1f MB)", DB_PATH, DB_PATH.stat().st_size / 1e6)
    existing = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    for tbl in NEW_TABLES:
        if tbl in existing:
            try:
                if tbl == "gdelt_raw_daily":
                    n = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                    nc = con.execute(f"SELECT COUNT(DISTINCT country_iso3) FROM {tbl}").fetchone()[0]
                    dmin, dmax = con.execute(f"SELECT MIN(date), MAX(date) FROM {tbl}").fetchone()
                    log.info("  %-25s %12s rows | %3d ISO3 | %s → %s",
                             tbl, f"{n:,}", nc, dmin, dmax)
                elif tbl == "factor_returns_daily":
                    n = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                    nf = con.execute(f"SELECT COUNT(DISTINCT factor) FROM {tbl}").fetchone()[0]
                    ns = con.execute(f"SELECT COUNT(DISTINCT source) FROM {tbl}").fetchone()[0]
                    dmin, dmax = con.execute(f"SELECT MIN(date), MAX(date) FROM {tbl}").fetchone()
                    log.info("  %-25s %12s rows | %3d factors | %d sources | %s → %s",
                             tbl, f"{n:,}", nf, ns, dmin, dmax)
                elif tbl in ("variable_meta", "daily_calendar"):
                    n = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                    log.info("  %-25s %12s rows", tbl, f"{n:,}")
                else:
                    n = con.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                    nv = con.execute(f"SELECT COUNT(DISTINCT variable) FROM {tbl}").fetchone()[0]
                    nc = con.execute(f"SELECT COUNT(DISTINCT country) FROM {tbl}").fetchone()[0]
                    dmin, dmax = con.execute(f"SELECT MIN(date), MAX(date) FROM {tbl}").fetchone()
                    log.info("  %-25s %12s rows | %3d vars | %2d ctry | %s → %s",
                             tbl, f"{n:,}", nv, nc, dmin, dmax)
            except Exception as e:
                log.error("  %-25s ERROR: %s", tbl, e)
        else:
            log.info("  %-25s NOT BUILT", tbl)
    check_commodity_context(con, existing)
    con.close()


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="Report on existing daily tables and exit")
    ap.add_argument("--rebuild", action="store_true",
                    help="Drop and rebuild even if tables exist")
    ap.add_argument("--skip-levels", action="store_true",
                    help="Skip slow T2MasterDaily.xlsx parse")
    ap.add_argument("--validate", action="store_true",
                    help="Run daily-EOM vs monthly comparison (assumes tables built)")
    ap.add_argument("--no-backup", action="store_true",
                    help="Skip DB backup (saves ~800 MB temp space)")
    args = ap.parse_args()

    if args.check:
        check_existing_tables()
        return 0

    # ── Pre-flight ─────────────────────────────────────────────────────────
    missing = check_inputs(skip_levels=args.skip_levels)
    if missing:
        log.error("Missing input files:")
        for m in missing:
            log.error("  %s", m)
        return 1

    if not DB_PATH.exists():
        log.error("Database not found: %s — run setup_duckdb.py first", DB_PATH)
        return 1

    # ── Idempotency: if all daily tables already exist and inputs unchanged,
    #    skip unless --rebuild ─────────────────────────────────────────────
    if not args.rebuild:
        con_ro = duckdb.connect(str(DB_PATH), read_only=True)
        existing = {r[0] for r in con_ro.execute("SHOW TABLES").fetchall()}
        con_ro.close()
        if all(t in existing for t in NEW_TABLES):
            db_mtime = DB_PATH.stat().st_mtime
            input_mtimes = [p.stat().st_mtime for p in [
                T2_NORMALIZED_CSV, GDELT_FACTORS_CSV, GDELT_RAW_PQ, T2_OPTIMIZER_TOP,
                T2_OPTIMIZER_RETURNS, GDELT_OPTIMIZER_RETURNS
            ] if p.exists()]
            if not args.skip_levels and T2_LEVELS_XLSX.exists():
                input_mtimes.append(T2_LEVELS_XLSX.stat().st_mtime)
            if db_mtime >= max(input_mtimes):
                log.info("All daily tables exist and DB is newer than inputs. "
                         "Use --rebuild to force.")
                if args.validate:
                    con = duckdb.connect(str(DB_PATH), read_only=True)
                    validate_against_monthly(con)
                    con.close()
                return 0

    # ── Backup ─────────────────────────────────────────────────────────────
    backup_database(no_backup=args.no_backup)

    start = time.time()
    log.info("=" * 70)
    log.info("ASADO Daily Panels — Stage 1 Build")
    log.info("=" * 70)

    try:
        con = duckdb.connect(str(DB_PATH))
        # DuckDB memory hint: T2 CSV is 1.7 GB; let it use a chunk of RAM
        con.execute("SET memory_limit = '8GB'")
        con.execute("SET threads = 8")

        load_t2_factors_daily(con)
        load_gdelt_factors_daily(con)
        load_gdelt_raw_daily(con)
        load_factor_returns_daily(con)

        if args.skip_levels:
            log.info("Skipping t2_levels_daily (--skip-levels)")
            # ensure empty table exists so variable_meta builder doesn't fail
            con.execute("""
                CREATE TABLE IF NOT EXISTS t2_levels_daily (
                    date DATE, country VARCHAR, value DOUBLE, variable VARCHAR
                )
            """)
        else:
            load_t2_levels_daily(con)

        build_variable_meta(con)
        build_daily_calendar(con)
        build_monthly_view(con)
        create_indexes(con)

        if args.validate:
            validate_against_monthly(con)

        con.close()

    except Exception as e:
        log.error("BUILD FAILED: %s", e)
        log.exception(e)
        if not args.no_backup:
            restore_backup()
        return 1

    # Cleanup backup on success
    if not args.no_backup and BACKUP_PATH.exists():
        log.info("Build succeeded — removing backup")
        BACKUP_PATH.unlink()

    elapsed = time.time() - start
    db_size = DB_PATH.stat().st_size / 1e6
    log.info("=" * 70)
    log.info("Done in %.1fs | DB now %.1f MB", elapsed, db_size)
    log.info("=" * 70)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
