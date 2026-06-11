#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: monthly_update.py
=============================================================================

INPUT FILES:
- (none directly — orchestrates other scripts)

OUTPUT FILES:
- Data/processed/external_factors_panel.parquet   (via collect_external.py)
- Data/processed/extended_factors_panel.parquet   (via collect_extended.py)
- Data/processed/imf_factors_panel.parquet        (via collect_imf.py)
- Data/processed/bilateral_trade_matrix.parquet   (via collect_bilateral.py)
- Data/processed/bilateral_banking_matrix.parquet (via collect_bilateral.py)
- Data/processed/bilateral_portfolio_matrix.parquet (via collect_bilateral.py)
- Data/processed/macrostructure_panel.parquet     (via collect_macrostructure.py)
- Data/processed/factor_returns_panel.parquet     (via collect_optimizer_returns.py)
- Data/processed/factor_top20_membership_panel.parquet (via collect_optimizer_returns.py)
- Data/processed/wb_commodity_*.parquet          (via collect_wb_commodity_prices.py)
- Data/processed/bloomberg_factors_panel.parquet  (via collect_bloomberg.py)
- Data/processed/gdelt_deep_panel.parquet         (via collect_gdelt_deep.py)
- Data/asado.duckdb                               (via setup_duckdb.py)
- DuckDB normalized_panel + feature_panel         (via build_normalized_panel.py)
- DuckDB gdelt_deep_factors                       (via load_gdelt_deep_to_duckdb.py)
- DuckDB gdelt_deep_factors_cs                    (via build_gdelt_deep_cs.py)
- Data/processed/pit_audit_gdelt_deep.csv         (via qa/pit_audit_gdelt_deep.py)
  (T2/GDELT/Econ factor pipelines are now standalone inside ASADO; all work
   files live under Data/work/{t2,gdelt,econ} — no external A Complete/ deps)
- Data/work/t2/T2 Master.xlsx                     (via build_t2_master.py)
- Data/work/t2/Normalized_T2_MasterCSV.csv        (via t2_normalize.py)
- Data/work/t2/T2_Top_20_Exposure.csv             (via t2_optimizer.py step3)
- Data/work/t2/T2_Optimizer.xlsx                  (via t2_optimizer.py step4)
- Data/work/gdelt/GDELT.xlsx                       (via build_gdelt_panel.py / core workbook copy)
- Data/work/gdelt/GDELT_Factors_MasterCSV.csv      (via gdelt_normalize.py)
- Data/work/gdelt/GDELT_Top_20_Exposure.csv        (via t2_optimizer.py --pipeline gdelt step3)
- Data/work/gdelt/GDELT_Optimizer.xlsx             (via t2_optimizer.py --pipeline gdelt step4)
- Data/work/econ/Econ.xlsx                          (via build_econ_panel.py)
- Data/work/econ/Econ_Factors_MasterCSV.csv         (via econ_normalize.py)
- Data/work/econ/Econ_Top_20_Exposure.csv           (via t2_optimizer.py --pipeline econ step3)
- Data/work/econ/Econ_Optimizer.xlsx                (via t2_optimizer.py --pipeline econ step4)
- Data/processed/econ_workbook_panel.parquet      (via build_econ_panel.py)
- Data/processed/gdelt_workbook_panel.parquet     (via build_gdelt_panel.py)
- Neo4j graph database                            (via setup_neo4j.py)
- Neo4j vector index on Country nodes             (via build_embeddings.py)
- Data/cache/query_assistant/*                    (via build_schema_registry.py)
- docs/factor_reference.md                        (via build_factor_reference.py)
- Data/logs/monthly_update_YYYY_MM_DD.log         (this run's log)

VERSION: 1.2
LAST UPDATED: 2026-04-29
AUTHOR: Arjun Divecha

DESCRIPTION:
Single-command monthly update orchestrator for the ASADO platform.
Runs all data collectors (panel + bilateral), rebuilds DuckDB, rebuilds
Neo4j (including trade/banking edges), builds country-state embeddings,
and produces a summary report. Designed to be run once per month.

Pipeline stages:
  1. collect_external.py  --force   (7 sources,  ~35 variables)
  2. collect_extended.py  --force   (12 sources, ~51 variables)
  3. collect_imf.py       --force   (7 datasets, ~26 variables)
  4. collect_bilateral.py           (IMF IMTS trade + BIS LBS banking + IMF PIP/TIC ownership)
  5. collect_macrostructure.py --force (IMF FSI + QPSD + sticky-capital + policy-backstop layer)
  5b. collect_wb_commodity_prices.py --force (World Bank Pink Sheet monthly commodity context)
  6. collect_bloomberg.py --force   (Bloomberg bonds, CDS, breakevens, ratings, ETF passive layer)
  6a. collect_t2_bloomberg.py       (live blpapi → T2 Bloomberg Master.xlsx, replaces Excel dump)
  6b. build_t2_master.py            (P2P via yfinance + T2 Master.xlsx → T2 Fuzzy/GDELT/Econ)
  7. collect_gdelt_deep.py          (GDELT Deep — incremental: themes + GCAM + events)
  8. setup_duckdb.py                (rebuild analytical DB)
  9. build_normalized_panel.py      (canonical normalized features + feature_panel)
 10. load_gdelt_deep_to_duckdb.py   (gdelt_deep_factors table)
 11. build_gdelt_deep_cs.py         (gdelt_deep_factors_cs cross-sectional variants)
 12. qa/pit_audit_gdelt_deep.py     (PIT audit on Deep tables)
 8a. setup_duckdb.py pass 1         (DuckDB from parquet panels + prior-month CSVs)
 8b. build_normalized_panel.py pass 1
 9a. build_econ_panel.py            (Econ.xlsx → /A Complete/T2 Econ/, reads DuckDB)
 9b. build_gdelt_panel.py           (GDELT.xlsx → /A Complete/T2 GDELT/, reads parquet)
 10a. T2 Fuzzy Step Two             (Normalized_T2_MasterCSV.csv, reads T2 Master.xlsx)
 10b. T2 GDELT Step Two             (GDELT_Factors_MasterCSV.csv, reads GDELT.xlsx)
 10c. T2 Econ Step Two              (Econ_Factors_MasterCSV.csv, reads Econ.xlsx)
 10d. T2 Fuzzy Step Three           (T2_Top_20_Exposure.csv)
 10e. T2 Fuzzy Step Four            (T2_Optimizer.xlsx)
 10f. T2 GDELT Step Three           (GDELT_Top_20_Exposure.csv)
 10g. T2 GDELT Step Four            (GDELT_Optimizer.xlsx)
 10h. T2 Econ Step Three            (Econ_Top_20_Exposure.csv)
 10i. T2 Econ Step Four             (Econ_Optimizer.xlsx)
 10j. collect_optimizer_returns.py  (ingest Optimizer.xlsx + exposure CSVs → DuckDB)
 11a. setup_duckdb.py pass 2        (DuckDB reloaded with fresh T2 + GDELT CSVs)
 11b. build_normalized_panel.py pass 2
 12. load_gdelt_deep_to_duckdb.py   (gdelt_deep_factors table)
 13. build_gdelt_deep_cs.py         (gdelt_deep_factors_cs cross-sectional variants)
 14. qa/pit_audit_gdelt_deep.py     (PIT audit on Deep tables)
 15. setup_neo4j.py                 (rebuild knowledge graph + bilateral edges)
 14. build_embeddings.py            (country-state vectors + Neo4j vector index)
 15. build_schema_registry.py       (refresh query-assistant schema cache)

Each collector preserves existing data for any source that fails,
so partial failures never lose historical data.

DEPENDENCIES:
- All dependencies from requirements.txt (pandas, duckdb, neo4j, etc.)
- Neo4j must be running: brew services start neo4j

USAGE:
  python scripts/monthly_update.py                 # full update
  python scripts/monthly_update.py --skip-neo4j    # skip Neo4j rebuild
  python scripts/monthly_update.py --skip-bloomberg # skip Bloomberg (no Terminal)
  python scripts/monthly_update.py --skip-deep    # skip GDELT Deep ingest
  python scripts/monthly_update.py --skip-wb-commodity # preserve prior World Bank commodity files
  python scripts/monthly_update.py --commodity-only # commodity collector + DuckDB/schema refresh only
  python scripts/monthly_update.py --collectors-only  # data collection only
  python scripts/monthly_update.py --db-only       # rebuild DBs only (no collection)
  python scripts/monthly_update.py --dry-run       # collectors in dry-run mode

NOTES:
- Total runtime: ~12-18 minutes depending on API response times
- Safe to re-run — every step is idempotent
- Log file saved automatically for each run
=============================================================================
"""

import argparse
import importlib
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
LOG_DIR = BASE_DIR / "Data" / "logs"
PYTHON = sys.executable

NEO4J_HOST = "localhost"
NEO4J_BOLT_PORT = 7687

# ── External T2 pipeline directories ────────────────────────────────────────
T2_FUZZY_DIR  = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/t2")
T2_GDELT_DIR  = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/gdelt")
T2_ECON_DIR   = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/econ")

# ── Canonical in-repo GDELT store (migrated from A Complete/GDELT) ───────────
# ASADO is the sole source of truth for GDELT: ingestion engine in
# scripts/gdelt_ingest/, raw GKG cache + panels + workbooks under Data/gdelt/.
GDELT_DIR = BASE_DIR / "Data" / "gdelt"


# Map pip package names to their Python import names where they differ
_IMPORT_NAME = {
    "scikit-learn": "sklearn",
    "pyarrow": "pyarrow",
    "openpyxl": "openpyxl",
    "mcp": "mcp",
    "sse-starlette": "sse_starlette",
    "sdmx1": "sdmx",
    "xlsxwriter": "xlsxwriter",
}


def ensure_dependencies():
    """Check that every package in requirements.txt is importable.

    Missing packages are installed automatically with
    ``pip install --break-system-packages`` so the pipeline never fails
    due to a missing module on a Homebrew-managed Python.
    """
    req_file = BASE_DIR / "requirements.txt"
    if not req_file.exists():
        print("  [WARN] requirements.txt not found — skipping dependency check")
        return

    missing: list[str] = []
    for line in req_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # strip extras, version specifiers  e.g. "mcp[cli]>=1.12" → "mcp"
        pkg = re.split(r"[\[><=!;]", line)[0].strip()
        import_name = _IMPORT_NAME.get(pkg, pkg.replace("-", "_"))
        try:
            importlib.import_module(import_name)
        except ModuleNotFoundError:
            missing.append(line)  # keep full spec for install

    if not missing:
        print("  All Python dependencies satisfied.")
        return

    print(f"  Missing packages: {', '.join(missing)}")
    print("  Installing ...")
    cmd = [
        sys.executable, "-m", "pip", "install",
        "--break-system-packages", "--quiet",
    ] + missing
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [ERROR] pip install failed:\n{result.stderr}")
        sys.exit(1)
    print(f"  Installed: {', '.join(missing)}")


def setup_logging():
    """Create log directory and return log file path."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    return LOG_DIR / f"monthly_update_{timestamp}.log"


def run_step(name: str, script: str, args: list, log_file: Path,
             cwd: Path | None = None) -> dict:
    """
    Run a pipeline step as a subprocess.

    script may be an absolute path (for external T2 pipeline scripts) or a
    path relative to SCRIPTS_DIR (for ASADO scripts).
    cwd defaults to BASE_DIR; pass a T2 directory for external scripts that
    use relative file paths.

    Returns dict with keys: name, status, elapsed, returncode, output_tail
    """
    script_path = Path(script)
    if not script_path.is_absolute():
        script_path = SCRIPTS_DIR / script
    cmd = [PYTHON, str(script_path)] + args
    run_cwd = str(cwd or BASE_DIR)
    print(f"\n{'─' * 60}")
    print(f"STEP: {name}")
    print(f"CMD:  {' '.join(cmd)}")
    print(f"CWD:  {run_cwd}")
    print(f"{'─' * 60}")

    start = time.time()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=run_cwd,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )
    elapsed = time.time() - start

    output = result.stdout + result.stderr
    status = "OK" if result.returncode == 0 else "FAILED"

    print(output)

    with open(log_file, "a") as f:
        f.write(f"\n{'=' * 60}\n")
        f.write(f"STEP: {name} ({script})\n")
        f.write(f"STATUS: {status} (exit code {result.returncode})\n")
        f.write(f"ELAPSED: {elapsed:.1f}s\n")
        f.write(f"{'=' * 60}\n")
        f.write(output)
        f.write("\n")

    tail_lines = output.strip().split("\n")[-10:]

    return {
        "name": name,
        "status": status,
        "elapsed": elapsed,
        "returncode": result.returncode,
        "output_tail": tail_lines,
    }


def print_summary(results: list, total_elapsed: float, log_file: Path):
    """Print and log the final summary report."""
    print("\n")
    print("=" * 60)
    print("  ASADO MONTHLY UPDATE — SUMMARY")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    print()

    all_ok = True
    for r in results:
        icon = "OK  " if r["status"] == "OK" else "FAIL"
        print(f"  [{icon}]  {r['name']:35s}  {r['elapsed']:6.1f}s")
        if r["status"] != "OK":
            all_ok = False

    print()
    print(f"  Total elapsed: {total_elapsed:.1f}s ({total_elapsed / 60:.1f} min)")
    print(f"  Log file:      {log_file}")
    print()

    if all_ok:
        print("  ALL STEPS COMPLETED SUCCESSFULLY.")
    else:
        failed = [r["name"] for r in results if r["status"] != "OK"]
        print(f"  WARNING: {len(failed)} step(s) had errors: {', '.join(failed)}")
        print("  Check the log file for details.")

    print("=" * 60)

    with open(log_file, "a") as f:
        f.write("\n" + "=" * 60 + "\n")
        f.write("FINAL SUMMARY\n")
        f.write("=" * 60 + "\n")
        for r in results:
            icon = "OK  " if r["status"] == "OK" else "FAIL"
            f.write(f"  [{icon}]  {r['name']:35s}  {r['elapsed']:6.1f}s\n")
        f.write(f"\nTotal elapsed: {total_elapsed:.1f}s\n")
        if not all_ok:
            failed = [r["name"] for r in results if r["status"] != "OK"]
            f.write(f"FAILED STEPS: {', '.join(failed)}\n")


def neo4j_is_reachable() -> bool:
    """Check if Neo4j bolt port is accepting connections."""
    try:
        with socket.create_connection((NEO4J_HOST, NEO4J_BOLT_PORT), timeout=2):
            return True
    except (ConnectionRefusedError, OSError):
        return False


def ensure_neo4j() -> bool:
    """
    Make sure Neo4j is running. Returns True if ready, False if unreachable.

    If Neo4j is already running, this is a no-op. If it's stopped, starts it
    via brew services and waits up to 30 seconds for the bolt port to open.
    """
    if neo4j_is_reachable():
        print("  Neo4j already running (bolt://localhost:7687)")
        return True

    print("  Neo4j not running — starting via brew services ...")
    try:
        subprocess.run(
            ["brew", "services", "start", "neo4j"],
            capture_output=True, text=True, timeout=15,
        )
    except FileNotFoundError:
        print("  WARNING: brew not found — cannot auto-start Neo4j")
        return False
    except subprocess.TimeoutExpired:
        print("  WARNING: brew services start timed out")
        return False

    for i in range(15):
        time.sleep(2)
        if neo4j_is_reachable():
            print(f"  Neo4j started successfully (took ~{(i + 1) * 2}s)")
            return True

    print("  WARNING: Neo4j did not respond within 30s — skipping Neo4j step")
    return False


def verify_duckdb():
    """Quick verification of the rebuilt database."""
    try:
        import duckdb
        db_path = BASE_DIR / "Data" / "asado.duckdb"
        if not db_path.exists():
            print("  DuckDB not found — skipping verification")
            return

        con = duckdb.connect(str(db_path), read_only=True)
        # wb_commodity_factor_panel is deprecated (country-tiled commodity data);
        # global commodity series now live in wb_commodity_prices + commodity_panel view.
        tables = ["t2_master", "t2_raw", "country_reference", "external_factors", "extended_factors",
                   "gdelt_panel", "imf_factors", "macrostructure_factors", "bloomberg_factors",
                   "wb_commodity_prices", "demographics_dip", "factor_returns",
                   "factor_top20_membership", "normalized_panel"]

        print("\n  DuckDB Verification:")
        total = 0
        for t in tables:
            try:
                if t == "country_reference":
                    count = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    iso3_count = con.execute(f"SELECT COUNT(DISTINCT iso3) FROM {t}").fetchone()[0]
                    print(f"    {t:20s}: {count:>10,} rows, {iso3_count:>3} iso3")
                elif t in ("factor_returns", "factor_top20_membership"):
                    count = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    n_factors = con.execute(f"SELECT COUNT(DISTINCT factor) FROM {t}").fetchone()[0]
                    print(f"    {t:20s}: {count:>10,} rows, {n_factors:>4} factors")
                elif t == "wb_commodity_prices":
                    count = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    n_codes = con.execute(f"SELECT COUNT(DISTINCT commodity_code) FROM {t}").fetchone()[0]
                    print(f"    {t:20s}: {count:>10,} rows, {n_codes:>3} commodities")
                else:
                    count = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    n_vars = con.execute(f"SELECT COUNT(DISTINCT variable) FROM {t}").fetchone()[0]
                    print(f"    {t:20s}: {count:>10,} rows, {n_vars:>3} vars")
                total += count
            except Exception:
                print(f"    {t:20s}: NOT FOUND")

        try:
            ucount = con.execute("SELECT COUNT(*) FROM unified_panel").fetchone()[0]
            uvars = con.execute("SELECT COUNT(DISTINCT variable) FROM unified_panel").fetchone()[0]
            print(f"    {'unified_panel':20s}: {ucount:>10,} rows, {uvars:>3} vars (view)")
        except Exception:
            pass

        try:
            fcount = con.execute("SELECT COUNT(*) FROM feature_panel").fetchone()[0]
            fvars = con.execute("SELECT COUNT(DISTINCT variable) FROM feature_panel").fetchone()[0]
            print(f"    {'feature_panel':20s}: {fcount:>10,} rows, {fvars:>3} vars (view)")
        except Exception:
            pass

        try:
            prices = con.execute("SELECT COUNT(DISTINCT commodity_code) FROM wb_commodity_prices").fetchone()[0]
            indices = con.execute("SELECT COUNT(DISTINCT index_code) FROM wb_commodity_indices").fetchone()[0]
            latest = con.execute("""
                SELECT MAX(date) FROM (
                    SELECT MAX(date) AS date FROM wb_commodity_prices
                    UNION ALL
                    SELECT MAX(date) AS date FROM wb_commodity_indices
                )
            """).fetchone()[0]
            print(f"    {'wb_commodity_canonical':20s}: {prices:>10} prices, {indices:>3} indices, latest {latest}")
        except Exception:
            pass

        try:
            pcount = con.execute("SELECT COUNT(*) FROM bilateral_portfolio_matrix").fetchone()[0]
            print(f"    {'bilateral_portfolio_matrix':20s}: {pcount:>10,} rows")
        except Exception:
            pass

        con.close()
    except ImportError:
        print("  duckdb not installed — skipping verification")


def main():
    parser = argparse.ArgumentParser(
        description="ASADO Monthly Update — run all data collection and database rebuilds"
    )
    parser.add_argument("--skip-neo4j", action="store_true",
                        help="Skip Neo4j rebuild (useful if Neo4j not running)")
    parser.add_argument("--skip-bloomberg", action="store_true",
                        help="Skip Bloomberg collection (requires Terminal + Parallels)")
    parser.add_argument("--skip-deep", action="store_true",
                        help="(Deprecated no-op) GDELT Deep themes/GCAM layer has been retired; "
                             "the core GDELT chain always runs now.")
    parser.add_argument("--skip-gdelt-fetch", action="store_true",
                        help="Rebuild GDELT from the cached country-day store WITHOUT fetching "
                             "new days from data.gdeltproject.org (offline / testing).")
    parser.add_argument("--skip-wb-commodity", action="store_true",
                        help="Skip World Bank commodity collection and preserve prior processed files")
    parser.add_argument("--commodity-only", action="store_true",
                        help="Run World Bank commodity collector plus DuckDB/schema refresh only")
    parser.add_argument("--collectors-only", action="store_true",
                        help="Run data collectors only, skip database rebuilds")
    parser.add_argument("--db-only", action="store_true",
                        help="Rebuild databases only, skip data collection")
    parser.add_argument("--dry-run", action="store_true",
                        help="Pass --dry-run to collectors (preview, no writes)")

    args = parser.parse_args()
    log_file = setup_logging()

    print("=" * 60)
    print("  ASADO MONTHLY UPDATE")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Python:  {PYTHON}")
    print(f"  Log:     {log_file}")
    print("=" * 60)

    # ── Step 0: Dependency check ────────────────────────────────────
    print("\nChecking Python dependencies ...")
    ensure_dependencies()

    with open(log_file, "w") as f:
        f.write(f"ASADO Monthly Update\n")
        f.write(f"Started: {datetime.now().isoformat()}\n")
        f.write(f"Python: {PYTHON}\n")
        f.write(f"Args: {vars(args)}\n\n")

    # ── Step 0b: Bloomberg-master freshness gate (T2 source) ────────────────
    # The T2 factor data comes from T2 Bloomberg Master.xlsx, which ASADO now
    # GENERATES from live blpapi in Stage 1 (Program 6a) instead of reading a
    # hand-refreshed Excel dump. That changes where the gate belongs:
    #   - Normal run: Program 6a regenerates the workbook THIS run, then Program
    #     6b's internal check_bloomberg_freshness() verifies the FRESH file. A
    #     pre-flight check here would only see last month's not-yet-regenerated
    #     file and wrongly abort — so we SKIP it and let 6a/6b be the gate.
    #   - --skip-bloomberg: we reuse the existing workbook untouched, so verify
    #     HERE that it already covers the last completed month (FAIL IS FAIL).
    if not args.db_only and not args.commodity_only and args.skip_bloomberg:
        print("\nChecking Bloomberg master freshness (T2 source, --skip-bloomberg) ...")
        fresh = subprocess.run(
            [PYTHON, str(SCRIPTS_DIR / "build_t2_master.py"), "--check-freshness"],
            capture_output=True, text=True,
        )
        print(fresh.stdout + fresh.stderr)
        with open(log_file, "a") as f:
            f.write("\nFreshness gate:\n" + fresh.stdout + fresh.stderr + "\n")
        if fresh.returncode != 0:
            print("=" * 60)
            print("  ABORTING UPDATE: existing Bloomberg master is STALE (see above).")
            print("  Re-run WITHOUT --skip-bloomberg so Program 6a regenerates it")
            print("  from live blpapi (Bloomberg Terminal must be up on Parallels).")
            print("=" * 60)
            return

    total_start = time.time()
    results = []

    collector_flags = ["--force"]
    if args.dry_run:
        collector_flags.append("--dry-run")

    if args.commodity_only:
        print("\n\n" + "=" * 60)
        print("  COMMODITY-ONLY UPDATE")
        print("=" * 60)

        if not args.skip_wb_commodity:
            results.append(run_step(
                "World Bank Commodity Price Intelligence",
                "collect_wb_commodity_prices.py",
                collector_flags,
                log_file,
            ))
        else:
            print("\n  (World Bank commodity collection skipped via --skip-wb-commodity)")

        if not args.collectors_only:
            results.append(run_step(
                "DuckDB Rebuild (commodity-aware)",
                "setup_duckdb.py",
                [],
                log_file,
            ))

            results.append(run_step(
                "Normalization Layer (commodity-aware)",
                "build_normalized_panel.py",
                [],
                log_file,
            ))

            results.append(run_step(
                "Daily Panels (restore + commodity metadata)",
                "build_daily_panels.py",
                ["--rebuild", "--no-backup"],
                log_file,
            ))

            results.append(run_step(
                "Schema Cache Refresh",
                "build_schema_registry.py",
                ["--duck-only"],
                log_file,
            ))

            results.append(run_step(
                "Factor Reference (docs/factor_reference.md)",
                "build_factor_reference.py",
                [],
                log_file,
            ))

        total_elapsed = time.time() - total_start
        if not args.collectors_only and not args.dry_run:
            verify_duckdb()
        print_summary(results, total_elapsed, log_file)
        return

    # ── Stage 1: Data Collection ──────────────────────────────────────
    if not args.db_only:
        print("\n\n" + "=" * 60)
        print("  STAGE 1: DATA COLLECTION")
        print("=" * 60)

        results.append(run_step(
            "Program 1: External Sources (7)",
            "collect_external.py",
            collector_flags,
            log_file
        ))

        results.append(run_step(
            "Program 2: Extended Sources (12)",
            "collect_extended.py",
            collector_flags,
            log_file
        ))

        if not args.skip_wb_commodity:
            results.append(run_step(
                "World Bank Commodity Price Intelligence",
                "collect_wb_commodity_prices.py",
                collector_flags,
                log_file,
            ))
        else:
            print("\n  (World Bank commodity collection skipped via --skip-wb-commodity)")

        results.append(run_step(
            "Program 3: IMF Datasets (7)",
            "collect_imf.py",
            collector_flags,
            log_file
        ))

        results.append(run_step(
            "Program 4: Bilateral Data (trade + banking + portfolio)",
            "collect_bilateral.py",
            [],
            log_file
        ))

        results.append(run_step(
            "Program 5: Macrostructure Panel (FSI + QPSD + backstop)",
            "collect_macrostructure.py",
            collector_flags,
            log_file
        ))

        if not args.skip_bloomberg:
            bbg_env = '/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv'
            bbg_script = str(SCRIPTS_DIR / "collect_bloomberg.py")
            bbg_flags = ["--force"] if not args.dry_run else ["--force", "--dry-run"]
            bbg_cmd = ["conda", "run", "-p", bbg_env, "python", bbg_script] + bbg_flags

            print(f"\n{'─' * 60}")
            print(f"STEP: Program 6: Bloomberg (rates + credit + ETF passive layer)")
            print(f"CMD:  {' '.join(bbg_cmd)}")
            print(f"{'─' * 60}")

            bbg_start = time.time()
            bbg_result = subprocess.run(
                bbg_cmd, capture_output=True, text=True, cwd=str(BASE_DIR),
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            bbg_elapsed = time.time() - bbg_start
            bbg_output = bbg_result.stdout + bbg_result.stderr
            bbg_status = "OK" if bbg_result.returncode == 0 else "FAILED"
            print(bbg_output)

            with open(log_file, "a") as f:
                f.write(f"\n{'=' * 60}\n")
                f.write(f"STEP: Program 6: Bloomberg\n")
                f.write(f"STATUS: {bbg_status} (exit code {bbg_result.returncode})\n")
                f.write(f"ELAPSED: {bbg_elapsed:.1f}s\n")
                f.write(f"{'=' * 60}\n")
                f.write(bbg_output + "\n")

            results.append({
                "name": "Program 6: Bloomberg",
                "status": bbg_status,
                "elapsed": bbg_elapsed,
                "returncode": bbg_result.returncode,
                "output_tail": bbg_output.strip().split("\n")[-10:],
            })
        else:
            print("\n  (Bloomberg collection skipped via --skip-bloomberg)")

        # Program 6a: T2 Bloomberg Master — generate the T2 Bloomberg workbook
        # DIRECTLY from live blpapi (scripts/collect_t2_bloomberg.py), replacing
        # the old hand-maintained Excel dump "Country Bloomberg Data Master T.xlsx".
        # Runs in the OpusBloomberg conda env (same as Program 6). The collector
        # self-probes (bloomberg_setup retry + AAPL ref) and exits non-zero if the
        # Terminal is unreachable — build_t2_master's freshness gate is the backstop.
        # Must run BEFORE Program 6b, which reads this workbook.
        if not args.skip_bloomberg and not args.dry_run:
            t2bbg_env = '/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv'
            t2bbg_script = str(SCRIPTS_DIR / "collect_t2_bloomberg.py")
            t2bbg_cmd = ["conda", "run", "-p", t2bbg_env, "python", t2bbg_script]

            print(f"\n{'─' * 60}")
            print(f"STEP: Program 6a: T2 Bloomberg Master (live blpapi -> T2 Bloomberg Master.xlsx)")
            print(f"CMD:  {' '.join(t2bbg_cmd)}")
            print(f"{'─' * 60}")

            t2bbg_start = time.time()
            t2bbg_result = subprocess.run(
                t2bbg_cmd, capture_output=True, text=True, cwd=str(BASE_DIR),
                env={**os.environ, "PYTHONUNBUFFERED": "1"},
            )
            t2bbg_elapsed = time.time() - t2bbg_start
            t2bbg_output = t2bbg_result.stdout + t2bbg_result.stderr
            t2bbg_status = "OK" if t2bbg_result.returncode == 0 else "FAILED"
            print(t2bbg_output)

            with open(log_file, "a") as f:
                f.write(f"\n{'=' * 60}\n")
                f.write(f"STEP: Program 6a: T2 Bloomberg Master\n")
                f.write(f"STATUS: {t2bbg_status} (exit code {t2bbg_result.returncode})\n")
                f.write(f"ELAPSED: {t2bbg_elapsed:.1f}s\n")
                f.write(f"{'=' * 60}\n")
                f.write(t2bbg_output + "\n")

            results.append({
                "name": "Program 6a: T2 Bloomberg Master",
                "status": t2bbg_status,
                "elapsed": t2bbg_elapsed,
                "returncode": t2bbg_result.returncode,
                "output_tail": t2bbg_output.strip().split("\n")[-10:],
            })
        elif args.skip_bloomberg:
            print("\n  (T2 Bloomberg Master generation skipped via --skip-bloomberg; "
                  "using existing T2 Bloomberg Master.xlsx)")
        else:  # dry-run
            print("\n  (T2 Bloomberg Master generation skipped in --dry-run; "
                  "live blpapi pull not exercised)")

        # Program 6b: T2 Master — P2P scores (yfinance) + T2 Master.xlsx from Bloomberg
        t2_flags = ["--dry-run"] if args.dry_run else []
        if args.skip_bloomberg:
            t2_flags.append("--skip-p2p")
        results.append(run_step(
            "Program 6b: T2 Master (P2P + Bloomberg → T2 Master.xlsx)",
            "build_t2_master.py",
            t2_flags,
            log_file
        ))

        # Program 7: GDELT Deep (themes + GCAM + events) — RETIRED.
        # The deep-themes layer has been dropped from ASADO; the core GDELT
        # sentiment/attention chain (ingest -> normalize -> optimizer) fully
        # replaces it for the warehouse + optimizer.

        # Vintage snapshot — freeze this month's freshly collected panels so
        # future research can see what was knowable at the time (Alpha-Hunting
        # Loop PRD §8 priority 2). --force: the monthly pull is the canonical
        # vintage for the month, replacing any earlier ad-hoc snapshot.
        if not args.dry_run:
            results.append(run_step(
                "Vintage Snapshot (Data/processed -> Data/vintages)",
                "snapshot_vintages.py",
                ["--force"],
                log_file
            ))

    # ── Stage 2: Database Rebuilds ────────────────────────────────────
    if not args.collectors_only:
        print("\n\n" + "=" * 60)
        print("  STAGE 2A: DUCKDB PASS 1 (existing CSVs)")
        print("=" * 60)

        # Pass 1: rebuild DuckDB from the latest parquet panels + existing
        # GDELT_Factors_MasterCSV.csv / Normalized_T2_MasterCSV.csv (prior
        # month). The T2 Step Twos below will produce fresh CSVs; Pass 2 then
        # reloads them so the final DuckDB is fully up to date.
        results.append(run_step(
            "DuckDB Rebuild (pass 1)",
            "setup_duckdb.py",
            [],
            log_file
        ))

        results.append(run_step(
            "Normalization Layer (pass 1)",
            "build_normalized_panel.py",
            [],
            log_file
        ))

        print("\n\n" + "=" * 60)
        print("  STAGE 2B: WORKBOOK EXPORTS")
        print("=" * 60)

        # Econ.xlsx — reads unified_panel (DuckDB pass 1 must be done first)
        results.append(run_step(
            "Econ Workbook Export (Econ.xlsx)",
            "build_econ_panel.py",
            [],
            log_file
        ))

        # GDELT INGEST — ASADO-internal port of the GKG pipeline. Fetches new
        # GKG days from data.gdeltproject.org incrementally, rebuilds the signal
        # panels, and exports the monthly + daily workbooks into the canonical
        # in-repo store (Data/gdelt/). Replaces the old shutil copy from
        # A Complete/GDELT — ASADO is now the sole source of truth for GDELT.
        gdelt_ingest_flags = [
            "--daily", "--save-panels",
            "--country-day-dir", str(GDELT_DIR / "country_day"),
            "--manifest-dir", str(GDELT_DIR / "manifests" / "country_day"),
            "--lookups-dir", str(GDELT_DIR / "lookups"),
            "--panels-dir", str(GDELT_DIR / "panels"),
            "--output", str(GDELT_DIR / "spreadsheet" / "GDELT.xlsx"),
            "--output-daily", str(GDELT_DIR / "spreadsheet" / "GDELT_DAILY.xlsx"),
        ]
        if args.skip_gdelt_fetch:
            gdelt_ingest_flags.append("--skip-fetch")
        results.append(run_step(
            "GDELT Ingest (GKG source -> panels + workbooks, in-repo)",
            "gdelt_ingest/build_fullhistory_workbook.py",
            gdelt_ingest_flags,
            log_file,
        ))
        # Hand the freshly-built monthly workbook to the normalize/optimizer work dir.
        import shutil
        src_wb = GDELT_DIR / "spreadsheet" / "GDELT.xlsx"
        dest = T2_GDELT_DIR / "GDELT.xlsx"
        if src_wb.exists():
            shutil.copy2(src_wb, dest)
            print(f"  GDELT.xlsx -> {dest} (for normalize/optimizer)")
        else:
            print(f"  WARNING: in-repo GDELT.xlsx not found: {src_wb}")

        print("\n\n" + "=" * 60)
        print("  STAGE 2C: T2 PIPELINE STEP TWOS")
        print("=" * 60)

        # T2 normalization — ASADO-internal port of Fuzzy Step Two.
        # Reads T2 Master.xlsx (from build_t2_master.py) → Normalized_T2_MasterCSV.csv.
        # No external "T2 Factor Timing Fuzzy" run required.
        results.append(run_step(
            "T2 Normalize (ASADO → Normalized_T2_MasterCSV.csv)",
            "t2_normalize.py",
            ["--no-xlsx"],
            log_file,
        ))

        # Distribute Normalized_T2_MasterCSV.csv to T2 GDELT and T2 Econ so
        # their Step Twos pick up the freshly rebuilt 1MRet series.
        normalized_src = T2_FUZZY_DIR / "Normalized_T2_MasterCSV.csv"
        if normalized_src.exists():
            import shutil
            for dest_dir in (T2_GDELT_DIR, T2_ECON_DIR):
                shutil.copy2(normalized_src, dest_dir / "Normalized_T2_MasterCSV.csv")
                print(f"  Copied Normalized_T2_MasterCSV.csv → {dest_dir.name}/")
        else:
            print("  WARNING: Normalized_T2_MasterCSV.csv not found — T2 Step Twos will fall back to T2 Master.xlsx")

        # Benchmark returns — ASADO-internal port of "Step Two Point Five".
        # Rebuilds Portfolio_Data.xlsx (Returns/Weights/Benchmarks) from the
        # Bloomberg-rooted T2 Master so the optimizer's net-of-benchmark returns
        # are NOT clipped to a stale benchmark month. Without this, all three
        # pipelines' factor returns truncate to whatever month the old
        # Portfolio_Data.xlsx reached (the GDELT-stuck-at-2026-03 bug).
        results.append(run_step(
            "Benchmark Returns (ASADO -> Portfolio_Data.xlsx)",
            "build_benchmark_rets.py",
            [],
            log_file,
        ))
        # Distribute the fresh Portfolio_Data.xlsx to GDELT + Econ work dirs.
        portfolio_src = T2_FUZZY_DIR / "Portfolio_Data.xlsx"
        if portfolio_src.exists():
            import shutil
            for dest_dir in (T2_GDELT_DIR, T2_ECON_DIR):
                shutil.copy2(portfolio_src, dest_dir / "Portfolio_Data.xlsx")
                print(f"  Copied Portfolio_Data.xlsx -> {dest_dir.name}/")
        else:
            print("  WARNING: Portfolio_Data.xlsx not found — optimizer returns may truncate to a stale benchmark")

        # GDELT normalize — ASADO-internal port of T2 GDELT Step Two (core, always runs).
        results.append(run_step(
            "GDELT Normalize (ASADO -> GDELT_Factors_MasterCSV.csv)",
            "gdelt_normalize.py",
            [],
            log_file,
        ))

        # Econ normalize — ASADO-internal port of T2 Econ Step Two.
        # (Econ.xlsx is built in-repo by build_econ_panel.py from unified_panel.)
        results.append(run_step(
            "Econ Normalize (ASADO → Econ_Factors_MasterCSV.csv)",
            "econ_normalize.py",
            [],
            log_file,
        ))

        # ── Steps Three + Four for all three T2 pipelines ────────────────
        # Step Three builds the Top-20 long/short portfolios and writes the
        # country exposure CSV.  Step Four computes monthly returns from those
        # portfolios and writes the Optimizer.xlsx.  These must run AFTER the
        # Step Twos have produced fresh *_Factors_MasterCSV.csv files.

        # T2 optimizer — ASADO-internal port of Fuzzy Steps Three + Four.
        results.append(run_step(
            "T2 Optimizer Step Three (ASADO → T2_Top_20_Exposure.csv)",
            "t2_optimizer.py",
            ["--step", "three"],
            log_file,
        ))
        results.append(run_step(
            "T2 Optimizer Step Four (ASADO → T2_Optimizer.xlsx)",
            "t2_optimizer.py",
            ["--step", "four"],
            log_file,
        ))

        # GDELT optimizer — ASADO-internal port (t2_optimizer --pipeline gdelt; core, always runs).
        results.append(run_step(
            "GDELT Optimizer Step Three (ASADO -> GDELT_Top_20_Exposure.csv)",
            "t2_optimizer.py",
            ["--pipeline", "gdelt", "--step", "three"],
            log_file,
        ))
        results.append(run_step(
            "GDELT Optimizer Step Four (ASADO -> GDELT_Optimizer.xlsx)",
            "t2_optimizer.py",
            ["--pipeline", "gdelt", "--step", "four"],
            log_file,
        ))

        # Econ optimizer — ASADO-internal port (t2_optimizer --pipeline econ).
        results.append(run_step(
            "Econ Optimizer Step Three (ASADO → Econ_Top_20_Exposure.csv)",
            "t2_optimizer.py",
            ["--pipeline", "econ", "--step", "three"],
            log_file,
        ))
        results.append(run_step(
            "Econ Optimizer Step Four (ASADO → Econ_Optimizer.xlsx)",
            "t2_optimizer.py",
            ["--pipeline", "econ", "--step", "four"],
            log_file,
        ))

        # Ingest freshly-produced Optimizer.xlsx + Top-20 exposure CSVs
        # back into DuckDB (factor_returns + factor_top20_membership tables).
        # Runs here — after all three Step Fours — so it always picks up the
        # files produced in this same run, not last month's.
        results.append(run_step(
            "Optimizer Returns + Top-20 Membership (ingest)",
            "collect_optimizer_returns.py",
            collector_flags,
            log_file,
        ))

        print("\n\n" + "=" * 60)
        print("  STAGE 2D: DUCKDB PASS 2 (fresh CSVs)")
        print("=" * 60)

        # Pass 2: reload DuckDB now that GDELT_Factors_MasterCSV.csv and
        # Normalized_T2_MasterCSV.csv are freshly produced by the Step Twos.
        results.append(run_step(
            "DuckDB Rebuild (pass 2 — fresh T2 + GDELT CSVs)",
            "setup_duckdb.py",
            [],
            log_file
        ))

        results.append(run_step(
            "Normalization Layer (pass 2)",
            "build_normalized_panel.py",
            [],
            log_file
        ))

        results.append(run_step(
            "Daily Panels (T2 + GDELT + optimizer returns)",
            "build_daily_panels.py",
            ["--rebuild", "--no-backup"],
            log_file
        ))

        # Stage 2 prediction-market layer (Kalshi + Polymarket), additive.
        # Runs after daily factor surfaces are rebuilt so variable_meta can
        # be upserted with fresh prediction-market signal names.
        results.append(run_step(
            "Prediction Markets (Kalshi + Polymarket)",
            "build_predmkt_panel.py",
            [],
            log_file
        ))

        results.append(run_step(
            "Event Log (curated event registry)",
            "build_event_log.py",
            [],
            log_file
        ))

        # Variable Registry (semantic layer) — reloads curated seed from
        # config/variable_registry_seed.yaml, rescans auto-facts from the
        # freshly rebuilt DB, rebuilds variable_registry_full, and re-renders
        # docs/VARIABLE_DICTIONARY.md. --bootstrap-seed appends skeleton rows
        # for any newly-appeared variables (never edits existing entries).
        results.append(run_step(
            "Variable Registry (semantic layer)",
            "build_variable_registry.py",
            ["--bootstrap-seed"],
            log_file
        ))

        # GDELT Deep DB stages (gdelt_deep_factors / _cs / PIT audit) — RETIRED.
        # Deep-themes tables are no longer built. Existing gdelt_deep_factors*
        # tables in the live DB are left as harmless dead tables until a separate
        # cleanup drops them.

        if not args.skip_neo4j:
            if ensure_neo4j():
                results.append(run_step(
                    "Neo4j Knowledge Graph",
                    "setup_neo4j.py",
                    [],
                    log_file
                ))

                results.append(run_step(
                    "Country-State Embeddings",
                    "build_embeddings.py",
                    [],
                    log_file
                ))

                results.append(run_step(
                    "Schema Cache Refresh",
                    "build_schema_registry.py",
                    [],
                    log_file
                ))
            else:
                print("  Neo4j unavailable — skipping knowledge graph + embeddings")
                results.append(run_step(
                    "Schema Cache Refresh",
                    "build_schema_registry.py",
                    ["--duck-only"],
                    log_file
                ))
        else:
            print("\n  (Neo4j + embeddings skipped via --skip-neo4j)")
            results.append(run_step(
                "Schema Cache Refresh",
                "build_schema_registry.py",
                ["--duck-only"],
                log_file
            ))

        # Always regenerate docs/factor_reference.md from the freshly-rebuilt
        # schema cache so the AI-readable factor catalog stays current.
        results.append(run_step(
            "Factor Reference (docs/factor_reference.md)",
            "build_factor_reference.py",
            [],
            log_file
        ))

    total_elapsed = time.time() - total_start

    # ── Verification ──────────────────────────────────────────────────
    if not args.collectors_only and not args.dry_run:
        verify_duckdb()

    # ── Summary ───────────────────────────────────────────────────────
    print_summary(results, total_elapsed, log_file)


if __name__ == "__main__":
    main()
