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

VERSION: 1.1
LAST UPDATED: 2026-06-12
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
  6. build_forward_calendar - load curated forward catalysts (CB decisions,
                            elections, index reviews) from the seed YAML
  7. collect_foreign_flows_bbg - Bloomberg foreign flows (Korea, Taiwan,
                            Thailand, Philippines, Indonesia; runs in the
                            OpusBloomberg conda env, parquet only)
  8. collect_foreign_flows - NSDL India FPI flows + rebuild of the loop-DB
                            foreign_flows_daily table from the merged parquet
  9. collect_sovereign_daily_bbg - Bloomberg daily 5Y+1Y CDS (20/18
                            countries) + 10Y+2Y yields (32/27)
                            -> sovereign_daily.parquet
                            (OpusBloomberg conda env, parquet only)
 10. load_sovereign_daily  - rebuild loop-DB sovereign_daily + the derived
                            sovereign_signals (CDS curve slope 5Y-1Y,
                            2s10s govt curve, both with z-scores)
 11. build_valuation_block - month-end CAPE/PB/DY/EY/ERP + 10y percentiles
                            -> valuation_monthly (PRD P7, E5 pricing layer)
 12. collect_weo_vintages - WEO vintage backfill + current vintage refresh
                            -> weo_vintages / weo_revisions (PRD P9; D3 input)
 13. collect_etf_flows_bbg - Bloomberg ETF shares-out/NAV/AUM for the 34
                            country ETFs (OpusBloomberg conda env, parquet only)
 14. load_etf_flows       - rebuild loop-DB etf_flows + etf_flow_signals
                            (PRD P11 positioning layer; brief crowding section)
 15. collect_consensus_bbg - Bloomberg ECFC consensus GDP/CPI forecast history
                            for current+next target year (OpusBloomberg env)
 16. load_consensus       - rebuild loop-DB consensus_daily + consensus_revisions
                            (PRD P9 stretch: dense surprise surface)
 17. collect_cot          - CFTC COT speculator positioning, 12 commodity
                            futures (keyless Socrata; PRD P11 positioning layer)
 18. collect_market_implied_bbg - Bloomberg FX implied vol (1W/1M/3M) +
                            25D risk reversals + butterflies + 3M forward
                            carry (25 pairs -> 30 countries), VIX/MOVE/
                            OAS/DXY dashboard, commodity curve generics
                            (OpusBloomberg conda env, parquet only)
 19. load_market_implied  - rebuild loop-DB market_implied_daily +
                            market_implied_signals (z-scores, VIX term
                            structure, vol term slope, carry z, curve
                            shape; brief stress section)
 20. collect_sov_ratings_bql - sovereign rating history S&P/Moody's/Fitch
                            via BQL issuerof() (33 countries, 2015+,
                            OpusBloomberg conda env, parquet only)
 21. load_sov_ratings     - rebuild loop-DB sov_ratings_monthly + the
                            dated sov_rating_changes event table
 22. collect_eco_surprise_bbg - economic releases actual-vs-survey
                            (CPI/UNEMP/GDP/PMI, OpusBloomberg env)
 23. load_eco_surprise    - rebuild loop-DB eco_surprise_monthly +
                            eco_surprise_signals (per-print z, growth/
                            inflation surprise composites)
 24. build_dislocations   - run all detectors, persist statuses, render brief
                            (brief includes the next-30-day catalyst section)
 25. build_evidence_packs - freeze GDELT headlines for tonight's fired
                            dislocations (PRD P4 v1; permanent packs + 14d table)
 26. ledgers --rebuild    - fold JSONL ledgers into loop-DB tables
 27. calibration_report   - regenerate current-month calibration report
                            (PRD 6.3; PARTIAL-stamped until >= 10 closed theses)

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
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
PY = str(BASE_DIR / "venv" / "bin" / "python")
BBG_ENV = "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv"
# Absolute conda path: under launchd the default PATH has no /opt/homebrew/bin,
# and a bare "conda" raised FileNotFoundError which killed the whole job
# (2026-06-11 11:30 silent death). Resolve from PATH first, then Homebrew.
CONDA = shutil.which("conda") or "/opt/homebrew/bin/conda"

STEPS = [
    ("collect_news_bridge", [PY, "scripts/loop/collect_news_bridge.py"]),
    ("mark_theses", [PY, "scripts/loop/ledgers.py", "--mark"]),
    ("build_country_returns", [PY, "scripts/loop/build_country_returns.py"]),
    ("build_tot_shares", [PY, "scripts/loop/build_tot_shares.py"]),
    ("build_graph_features", [PY, "scripts/loop/build_graph_features.py"]),
    ("build_forward_calendar", [PY, "scripts/loop/build_forward_calendar.py"]),
    # Bloomberg flows (KR/TW/TH/PH/ID) must run BEFORE the NSDL step: it only
    # writes the parquet (no duckdb in the OpusBloomberg env); the NSDL step
    # merges India and rebuilds the loop-DB table from the merged parquet.
    ("collect_foreign_flows_bbg",
     [CONDA, "run", "-p", BBG_ENV, "python", "scripts/loop/collect_foreign_flows_bbg.py"]),
    ("collect_foreign_flows", [PY, "scripts/loop/collect_foreign_flows.py"]),
    # Sovereign CDS/10Y: same conda/venv split as foreign flows — the bbg step
    # appends the last 15 days to the parquet, the load step rebuilds the
    # loop-DB sovereign_daily table that D4 and the valuation block read.
    ("collect_sovereign_daily_bbg",
     [CONDA, "run", "-p", BBG_ENV, "python", "scripts/loop/collect_sovereign_daily_bbg.py"]),
    ("load_sovereign_daily", [PY, "scripts/loop/load_sovereign_daily.py"]),
    ("build_valuation_block", [PY, "scripts/loop/build_valuation_block.py"]),
    # WEO vintages: archived vintages are cached forever; only the current
    # vintage is re-fetched (24h cache) -> ~2 cheap HTTP calls per night.
    ("collect_weo_vintages", [PY, "scripts/loop/collect_weo_vintages.py"]),
    # ETF share-count flows (PRD P11): same conda/venv split — bbg step appends
    # the last 15 days of shares/NAV/AUM, load step rebuilds etf_flows +
    # etf_flow_signals (positioning layer read by the brief).
    ("collect_etf_flows_bbg",
     [CONDA, "run", "-p", BBG_ENV, "python", "scripts/loop/collect_etf_flows_bbg.py"]),
    ("load_etf_flows", [PY, "scripts/loop/load_etf_flows.py"]),
    # ECFC consensus (PRD P9 stretch): nightly pull is ~120 cheap hist calls
    # for the current + next target year; loader derives the revision surface.
    ("collect_consensus_bbg",
     [CONDA, "run", "-p", BBG_ENV, "python", "scripts/loop/collect_consensus_bbg.py"]),
    ("load_consensus", [PY, "scripts/loop/load_consensus.py"]),
    # COT (PRD P11): CFTC Socrata, keyless, 12 markets, ~12 cheap HTTP calls.
    ("collect_cot", [PY, "scripts/loop/collect_cot.py"]),
    # Market-implied stress layer: FX implied vol (1W/1M/3M) + 25D risk
    # reversals + butterflies + 3M forward-implied carry for 25 T2 currency
    # pairs, VIX/MOVE/OAS/DXY dashboard, commodity curve shape (~187 cheap
    # hist hits/night). Same conda/venv split as the other BBG steps.
    ("collect_market_implied_bbg",
     [CONDA, "run", "-p", BBG_ENV, "python", "scripts/loop/collect_market_implied_bbg.py"]),
    ("load_market_implied", [PY, "scripts/loop/load_market_implied.py"]),
    # Sovereign rating history (BQL): ~99 compute-bound BQL queries, ~2 min;
    # serves the full 2015+ monthly history each run -> loader derives the
    # dated rating-change event table the brief reads.
    ("collect_sov_ratings_bql",
     [CONDA, "run", "-p", BBG_ENV, "python", "scripts/loop/collect_sov_ratings_bql.py"]),
    ("load_sov_ratings", [PY, "scripts/loop/load_sov_ratings.py"]),
    # Economic surprise layer: actual-vs-survey for CPI/UNEMP/GDP/PMI across
    # the T2 universe (~190 cheap hist hits/night, 6-month window).
    ("collect_eco_surprise_bbg",
     [CONDA, "run", "-p", BBG_ENV, "python", "scripts/loop/collect_eco_surprise_bbg.py"]),
    ("load_eco_surprise", [PY, "scripts/loop/load_eco_surprise.py"]),
    ("build_dislocations", [PY, "scripts/loop/build_dislocations.py"]),
    # Evidence packs MUST run after build_dislocations: they freeze headlines
    # for the countries whose dislocations fired in tonight's run (PRD P4 v1;
    # capped at 12 GDELT pulls, D8 excluded).
    ("build_evidence_packs", [PY, "scripts/loop/build_evidence_packs.py"]),
    ("fold_ledgers", [PY, "scripts/loop/ledgers.py", "--rebuild"]),
    # Calibration report (PRD 6.3): regenerates the current month's report
    # nightly from the folded ledgers; stamps itself PARTIAL until >= 10
    # closed theses exist (Phase 4 gate). Must run AFTER fold_ledgers.
    ("calibration_report", [PY, "scripts/loop/calibration_report.py"]),
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
    warnings = []
    for name, cmd in steps:
        print(f"\n{'─' * 60}\n{datetime.now().strftime('%H:%M:%S')} STEP: {name}\n{'─' * 60}", flush=True)
        try:
            res = subprocess.run(cmd, cwd=str(BASE_DIR))
            rc = res.returncode
        except FileNotFoundError as exc:
            # A missing binary (e.g. conda not on launchd's PATH) must fail the
            # STEP loudly, never kill the whole job silently (2026-06-11 bug).
            rc = 127
            print(f"!!! STEP BINARY MISSING: {name}: {exc}", flush=True)
        if rc == 2:
            # Exit 2 = PARTIAL: the step kept its completed work and the missing
            # part self-heals next run (e.g. evidence packs hit GDELT's rate
            # limit after writing some packs). Warn, don't fail the job.
            warnings.append(name)
            print(f"~~~ STEP PARTIAL: {name} (exit 2) - recorded as warning", flush=True)
        elif rc != 0:
            failures.append(name)
            print(f"!!! STEP FAILED: {name} (exit {rc}) - continuing with remaining steps", flush=True)

    print(f"\n{'=' * 60}")
    if failures:
        print(f"LOOP DAILY JOB: {len(failures)} FAILURE(S): {failures}"
              + (f" | partial: {warnings}" if warnings else ""))
        return 1
    if warnings:
        print(f"LOOP DAILY JOB: all steps OK ({len(warnings)} partial: {warnings})")
        return 0
    print("LOOP DAILY JOB: all steps OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
