#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/daily_update.py
=============================================================================

DESCRIPTION:
    DAILY-metronome counterpart to monthly_update.py. Runs the same factor
    pipeline as monthly, one day at a time, for the two domains that move daily
    (T2 prices and GDELT news); Econ is skipped (it has no daily factors). The
    T2 prices come DIRECT from Bloomberg (no hand-maintained Excel), exactly like
    the monthly Bloomberg-direct pull but at DAILY periodicity.

    Stages:
      T2:    collect_t2_bloomberg.py --daily   (live blpapi, calendar-day grid)
             build_t2_master_daily.py          (raw daily factors: 1DRet..120DRet, etc.)
             t2_normalize_daily.py             (_CS/_TS normalized daily factors)
             build_benchmark_rets_daily.py     (daily benchmarks -> Portfolio_Data.xlsx)
             t2_optimizer_daily.py             (daily factor returns)
      GDELT: refresh_gdelt_daily.py            (GKG source -> upstream parquet)
             gdelt_normalize_daily.py          (parquet -> normalized daily factors)
             gdelt_optimizer_daily.py          (daily GDELT factor returns)
      DB:    build_daily_panels.py             (load daily tables into DuckDB)
      Graph: setup_neo4j.py                    (refresh from the fresh daily data)
      Loop:  loop/loop_daily_job.py            (Layer 1: dislocations + brief,
             chained LAST so detectors always see the data built above)

INPUT FILES:
    - Bloomberg live API (OpusBloomberg) for T2 daily prices
    - /Users/arjundivecha/Dropbox/AAA Backup/A Working/GDELT/data/panels/
      country_signal_daily.parquet for GDELT

OUTPUT FILES:
    - Data/work/t2_daily/*  (T2 Bloomberg Master Daily.xlsx, T2 Master Daily.xlsx,
        Normalized_T2_MasterCSV.csv, Portfolio_Data.xlsx, T2_Optimizer.xlsx)
    - Data/work/gdelt_daily/* (GDELT daily normalized factors + returns)
    - Data/asado.duckdb daily tables (via build_daily_panels.py)
    - Data/logs/daily_update_YYYY_MM_DD_HHMMSS.log

VERSION: 1.1
LAST UPDATED: 2026-06-10
AUTHOR: Arjun Divecha (built by Claude Code)

DEPENDENCIES: pandas, numpy, duckdb, neo4j; OpusBloomberg conda env for the pull.

USAGE:
    python scripts/daily_update.py                 # full daily run
    python scripts/daily_update.py --resume         # skip stages already OK today
    python scripts/daily_update.py --skip-bloomberg # reuse existing daily Bloomberg pull
    python scripts/daily_update.py --skip-gdelt     # T2 only
    python scripts/daily_update.py --skip-neo4j     # skip graph refresh
    python scripts/daily_update.py --t2-only        # T2 chain only (no GDELT/DB/graph)

NOTES:
    - Designed to run unattended on a cron/launchd schedule with the Bloomberg
      connection kept alive. Econ is intentionally NOT part of the daily run.
    - FAIL-FAST + RESUME (2026-06-10): a failed stage aborts the remaining
      stages (downstream stages must never run on stale upstream data), and
      every completed stage is checkpointed to
      Data/logs/daily_update_progress_YYYY_MM_DD.json. Re-running with
      --resume skips stages already completed today, so a failure at stage 7
      no longer costs a full re-run of stages 1-6 (including the ~3 min
      Bloomberg pull).
=============================================================================
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = BASE_DIR / "scripts"
PYTHON = sys.executable
BBG_ENV = "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv"
LOG_DIR = BASE_DIR / "Data" / "logs"

# Shared bounded-subprocess helper (needs the repo root on sys.path).
sys.path.insert(0, str(BASE_DIR))
from scripts.loop.procutil import run_bounded  # noqa: E402
# Absolute conda path: launchd's PATH lacks /opt/homebrew/bin, and a bare
# "conda" raised FileNotFoundError that killed the loop on 2026-06-11.
CONDA = shutil.which("conda") or "/opt/homebrew/bin/conda"


def run_step(name, script, flags, log_file, conda=False, timeout=None):
    if conda:
        cmd = [CONDA, "run", "-p", BBG_ENV, "python", str(SCRIPTS_DIR / script)] + flags
    else:
        cmd = [PYTHON, str(SCRIPTS_DIR / script)] + flags
    to = timeout or (1800 if conda else 1200)  # BBG steps get a longer budget
    print(f"\n{'─'*60}\nSTEP: {name}\nCMD:  {' '.join(cmd)}\n{'─'*60}", flush=True)
    t0 = time.time()
    res = run_bounded(cmd, timeout=to, cwd=str(BASE_DIR),
                      env={**os.environ, "PYTHONUNBUFFERED": "1"})
    elapsed = time.time() - t0
    out = res.stdout + res.stderr
    if res.returncode == 0:
        status = "OK"
    elif getattr(res, "timed_out", False):
        status = "TIMEOUT"
    else:
        status = "FAILED"
    print(out[-2000:], flush=True)
    with open(log_file, "a") as f:
        f.write(f"\n{'='*60}\nSTEP: {name}\nSTATUS: {status} (exit {res.returncode}) ELAPSED {elapsed:.1f}s\n{'='*60}\n{out}\n")
    print(f"  [{status}] {name}  ({elapsed:.1f}s)", flush=True)
    return {"name": name, "status": status, "elapsed": elapsed, "rc": res.returncode}


def main() -> int:
    ap = argparse.ArgumentParser(description="ASADO daily update (T2 + GDELT, daily metronome).")
    ap.add_argument("--skip-bloomberg", action="store_true")
    ap.add_argument("--skip-gdelt", action="store_true")
    ap.add_argument("--skip-neo4j", action="store_true")
    ap.add_argument("--skip-db", action="store_true")
    ap.add_argument("--skip-loop", action="store_true",
                    help="Skip the Alpha-Hunting Loop Layer 1 stage at the end.")
    ap.add_argument("--t2-only", action="store_true")
    ap.add_argument("--resume", action="store_true",
                    help="Skip stages already completed OK today (per the daily progress checkpoint).")
    args = ap.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"daily_update_{datetime.now().strftime('%Y_%m_%d_%H%M%S')}.log"
    progress_file = LOG_DIR / f"daily_update_progress_{datetime.now().strftime('%Y_%m_%d')}.json"

    # Stages completed OK today (for --resume). Written incrementally after
    # every stage so a crash/abort never loses progress.
    done: dict = {}
    if args.resume and progress_file.exists():
        try:
            done = json.loads(progress_file.read_text())
        except (json.JSONDecodeError, OSError):
            done = {}

    print(f"{'='*60}\n  ASADO DAILY UPDATE\n  Started: {datetime.now():%Y-%m-%d %H:%M:%S}\n  Log: {log_file}")
    if args.resume and done:
        print(f"  Resume: {len(done)} stage(s) already OK today will be skipped")
    print("=" * 60)
    results = []
    t_start = time.time()

    # ── declarative stage list (name, script, flags, conda, enabled[, timeout]) ─────
    full = not args.t2_only
    stages = [
        ("T2: daily Bloomberg pull (live blpapi)", "collect_t2_bloomberg.py", ["--daily"], True,
         not args.skip_bloomberg),
        ("T2: build daily master", "build_t2_master_daily.py", [], False, True),
        ("T2: normalize daily", "t2_normalize_daily.py", [], False, True),
        ("T2: daily benchmarks", "build_benchmark_rets_daily.py", [], False, True),
        ("T2: daily factor returns", "t2_optimizer_daily.py", [], False, True),
        ("GDELT: refresh upstream parquet", "refresh_gdelt_daily.py", [], False,
         full and not args.skip_gdelt, 7200),
        # GDELT factor returns use the GDELT-SPECIFIC optimizer (1DRet same-date,
        # CSV-only dates, cross-sectional fill) — NOT the T2 Step-Four taper.
        ("GDELT: normalize daily", "gdelt_normalize_daily.py", [], False,
         full and not args.skip_gdelt),
        ("GDELT: daily factor returns", "gdelt_optimizer_daily.py", [], False,
         full and not args.skip_gdelt),
        ("DB: build daily panels", "build_daily_panels.py", ["--rebuild", "--no-backup"], False,
         full and not args.skip_db),
        ("Graph: Neo4j refresh", "setup_neo4j.py", [], False,
         full and not args.skip_neo4j),
        # Loop chained LAST on purpose (2026-06-10): the standalone launchd loop
        # job used to run BEFORE this pipeline finished, so detectors scanned
        # yesterday's tables. As the final stage it always sees fresh data.
        ("Loop: Layer 1 (dislocations + brief)", "loop/loop_daily_job.py", [], False,
         full and not args.skip_db and not args.skip_loop),
    ]

    aborted_at = None
    for stage in stages:
        name, script, flags, conda, enabled = stage[:5]
        timeout = stage[5] if len(stage) > 5 else None
        if not enabled:
            continue
        if args.resume and done.get(name) == "OK":
            print(f"\n  [RESUME] skipping '{name}' (already OK today)", flush=True)
            results.append({"name": name, "status": "OK", "elapsed": 0.0, "rc": 0,
                            "skipped_resume": True})
            continue
        r = run_step(name, script, flags, log_file, conda=conda, timeout=timeout)
        results.append(r)
        if r["status"] == "OK":
            done[name] = "OK"
            progress_file.write_text(json.dumps(done, indent=2))
        else:
            # FAIL-FAST: downstream stages must never run on stale upstream
            # data (e.g. building the master from last week's workbook after a
            # failed Bloomberg pull). Fix or wait, then rerun with --resume to
            # continue from exactly here.
            aborted_at = name
            print(f"\n  ✗ Stage '{name}' failed — aborting remaining stages. "
                  f"Rerun with --resume to continue from this stage.", flush=True)
            break

    # ── summary ───────────────────────────────────────────────────────────
    elapsed = time.time() - t_start
    print(f"\n{'='*60}\n  DAILY UPDATE SUMMARY ({elapsed/60:.1f} min)\n{'='*60}")
    for r in results:
        tag = " (resumed-skip)" if r.get("skipped_resume") else ""
        print(f"  [{r['status']:>6}] {r['name']:<42} {r['elapsed']:.1f}s{tag}")
    failed = [r for r in results if r["status"] != "OK"]
    if aborted_at:
        print(f"\n  ABORTED at '{aborted_at}' — rerun with --resume to continue.")
    print(f"\n  {'ALL STEPS OK' if not failed else f'{len(failed)} STEP(S) FAILED'}\n  Log: {log_file}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
