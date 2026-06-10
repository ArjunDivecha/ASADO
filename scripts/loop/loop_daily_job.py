#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: loop_daily_job.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/News/data/report.db (via collect_news_bridge)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb (read-only, all steps)
- Neo4j @ bolt://localhost:7687 (via build_graph_features)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/ledgers/*.jsonl (via ledgers)

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
  (all loop tables refreshed)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/dislocations/brief_YYYY_MM_DD.md
  (the daily brief for the Layer 2 reasoning session)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/logs/loop_daily_launchd.log
  (when run from launchd)

VERSION: 1.0
LAST UPDATED: 2026-06-10
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 2)

DESCRIPTION:
The nightly Layer 1 orchestrator. Runs every morning at 06:45 (launchd:
com.arjundivecha.asado-loop-daily) in this order:

  1. collect_news_bridge  - accumulate holdings + ETF prices from the News repo
  2. ledgers --mark       - auto-mark open theses from T2 daily returns,
                            close mechanically (invalidated/expired)
  3. build_country_returns - refresh the monthly marking surface
  4. build_tot_shares     - WDI commodity trade shares for D1 (slow-moving;
                            keeps existing table on any fetch failure)
  5. build_graph_features - refresh graph->panel features from Neo4j + returns
                            (also stores the monthly PIT edge snapshot)
  6. build_dislocations   - run all detectors, persist statuses, render brief
  7. ledgers --rebuild    - fold JSONL ledgers into loop-DB tables

Each step runs in its own subprocess with the house per-source isolation
pattern: one failing step does not stop the rest, but ANY failure makes the
job exit non-zero and is shouted in the log (FAIL-IS-FAIL: visible, never
swallowed).

DEPENDENCIES:
- project venv (duckdb, pandas, numpy, neo4j, requests)

USAGE:
 python scripts/loop/loop_daily_job.py          # full nightly sequence
 python scripts/loop/loop_daily_job.py --only build_dislocations
=============================================================================
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PY = str(BASE_DIR / "venv" / "bin" / "python")

STEPS = [
    ("collect_news_bridge", [PY, "scripts/loop/collect_news_bridge.py"]),
    ("mark_theses", [PY, "scripts/loop/ledgers.py", "--mark"]),
    ("build_country_returns", [PY, "scripts/loop/build_country_returns.py"]),
    ("build_tot_shares", [PY, "scripts/loop/build_tot_shares.py"]),
    ("build_graph_features", [PY, "scripts/loop/build_graph_features.py"]),
    ("build_dislocations", [PY, "scripts/loop/build_dislocations.py"]),
    ("fold_ledgers", [PY, "scripts/loop/ledgers.py", "--rebuild"]),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Nightly Alpha-Hunting Loop Layer 1 job.")
    parser.add_argument("--only", default=None, help="Run a single named step.")
    args = parser.parse_args()

    steps = [(n, c) for n, c in STEPS if args.only is None or n == args.only]
    if not steps:
        print(f"No step named {args.only!r}. Steps: {[n for n, _ in STEPS]}")
        return 2

    failures = []
    for name, cmd in steps:
        print(f"\n{'─' * 60}\n{datetime.now().strftime('%H:%M:%S')} STEP: {name}\n{'─' * 60}", flush=True)
        res = subprocess.run(cmd, cwd=str(BASE_DIR))
        if res.returncode != 0:
            failures.append(name)
            print(f"!!! STEP FAILED: {name} (exit {res.returncode}) - continuing with remaining steps", flush=True)

    print(f"\n{'=' * 60}")
    if failures:
        print(f"LOOP DAILY JOB: {len(failures)} FAILURE(S): {failures}")
        return 1
    print("LOOP DAILY JOB: all steps OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
