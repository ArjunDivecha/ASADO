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
- Data/processed/bloomberg_factors_panel.parquet  (via collect_bloomberg.py)
- Data/asado.duckdb                               (via setup_duckdb.py)
- DuckDB normalized_panel + feature_panel         (via build_normalized_panel.py)
- Neo4j graph database                            (via setup_neo4j.py)
- Neo4j vector index on Country nodes             (via build_embeddings.py)
- Data/cache/query_assistant/*                    (via build_schema_registry.py)
- Data/logs/monthly_update_YYYY_MM_DD.log         (this run's log)

VERSION: 1.1
LAST UPDATED: 2026-04-12
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
  6. collect_bloomberg.py --force   (Bloomberg bonds, CDS, breakevens, ratings, ETF passive layer)
  7. setup_duckdb.py                (rebuild analytical DB)
  8. build_normalized_panel.py      (canonical normalized features + feature_panel)
  9. setup_neo4j.py                 (rebuild knowledge graph + bilateral edges)
 10. build_embeddings.py            (country-state vectors + Neo4j vector index)
 11. build_schema_registry.py       (refresh query-assistant schema cache)

Each collector preserves existing data for any source that fails,
so partial failures never lose historical data.

DEPENDENCIES:
- All dependencies from requirements.txt (pandas, duckdb, neo4j, etc.)
- Neo4j must be running: brew services start neo4j

USAGE:
  python scripts/monthly_update.py                 # full update
  python scripts/monthly_update.py --skip-neo4j    # skip Neo4j rebuild
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
import os
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


def setup_logging():
    """Create log directory and return log file path."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y_%m_%d_%H%M%S")
    return LOG_DIR / f"monthly_update_{timestamp}.log"


def run_step(name: str, script: str, args: list, log_file: Path) -> dict:
    """
    Run a pipeline step as a subprocess.

    Returns dict with keys: name, status, elapsed, returncode, output_tail
    """
    cmd = [PYTHON, str(SCRIPTS_DIR / script)] + args
    print(f"\n{'─' * 60}")
    print(f"STEP: {name}")
    print(f"CMD:  {' '.join(cmd)}")
    print(f"{'─' * 60}")

    start = time.time()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(BASE_DIR),
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
        tables = ["t2_master", "t2_raw", "country_reference", "external_factors", "extended_factors",
                   "gdelt_panel", "imf_factors", "macrostructure_factors", "bloomberg_factors",
                   "normalized_panel"]

        print("\n  DuckDB Verification:")
        total = 0
        for t in tables:
            try:
                if t == "country_reference":
                    count = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
                    iso3_count = con.execute(f"SELECT COUNT(DISTINCT iso3) FROM {t}").fetchone()[0]
                    print(f"    {t:20s}: {count:>10,} rows, {iso3_count:>3} iso3")
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

    with open(log_file, "w") as f:
        f.write(f"ASADO Monthly Update\n")
        f.write(f"Started: {datetime.now().isoformat()}\n")
        f.write(f"Python: {PYTHON}\n")
        f.write(f"Args: {vars(args)}\n\n")

    total_start = time.time()
    results = []

    collector_flags = ["--force"]
    if args.dry_run:
        collector_flags.append("--dry-run")

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

    # ── Stage 2: Database Rebuilds ────────────────────────────────────
    if not args.collectors_only:
        print("\n\n" + "=" * 60)
        print("  STAGE 2: DATABASE REBUILDS")
        print("=" * 60)

        results.append(run_step(
            "DuckDB Rebuild",
            "setup_duckdb.py",
            [],
            log_file
        ))

        results.append(run_step(
            "Normalization Layer",
            "build_normalized_panel.py",
            [],
            log_file
        ))

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

    total_elapsed = time.time() - total_start

    # ── Verification ──────────────────────────────────────────────────
    if not args.collectors_only and not args.dry_run:
        verify_duckdb()

    # ── Summary ───────────────────────────────────────────────────────
    print_summary(results, total_elapsed, log_file)


if __name__ == "__main__":
    main()
