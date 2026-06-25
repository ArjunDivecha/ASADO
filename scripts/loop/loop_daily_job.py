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
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/governance/run_manifest.json
  (A1 governance run manifest: per-step ok/fail/stale/partial/skipped + the
  governance-contract hash; written fail-soft after the STEPS loop)

VERSION: 1.2
LAST UPDATED: 2026-06-12 (graph machine: PIT graph features, fundamental
              twins, lead-lag network, ridge combiner, Neo4j write-back)
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
 24. build_graph_features_pit - point-in-time graph spillover features from
                            stored edge vintages (PIT bank/trade/twohop gaps,
                            Katz, hub, bloc; the vintage COLLECTOR
                            collect_pit_edges.py runs monthly, not here)
 25. build_similarity_features - fundamental-twins cosine map (month-end
                            factor vectors) -> twin-convergence gaps
 26. build_leadlag_features - lag-1 cross-correlation network -> leader
                            gap features (timezone + diffusion channel)
 27. build_combiner       - walk-forward ridge composite scores (monthly
                            table for the record; DAILY table is the live
                            prediction surface, IC 0.057 / t 10.7 at launch)
 28. write_graph_discoveries - push SIMILAR_TO / LEADS edges + combiner
                            ranks into Neo4j for MCP/browser exploration
 29. build_dislocations   - run all detectors, persist statuses, render brief
                            (brief includes the next-30-day catalyst section)
 30. build_evidence_packs - freeze GDELT headlines for tonight's fired
                            dislocations (PRD P4 v1; permanent packs + 14d table)
 31. ledgers --rebuild    - fold JSONL ledgers into loop-DB tables
 32. calibration_report   - regenerate current-month calibration report
                            (PRD 6.3; PARTIAL-stamped until >= 10 closed theses)
 33. build_jst_risk_report - dated JST long-cycle tail-risk report (xlsx + PDF)
                            in Data/loop/risk_reports/ (read-only; context only)

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
import fcntl
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))  # so `from scripts.loop import run_manifest` resolves
from scripts.loop.procutil import run_bounded  # noqa: E402  bounded subprocess + group kill
PY = str(BASE_DIR / "venv" / "bin" / "python")
BBG_ENV = "/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv"
# Absolute conda path: under launchd the default PATH has no /opt/homebrew/bin,
# and a bare "conda" raised FileNotFoundError which killed the whole job
# (2026-06-11 11:30 silent death). Resolve from PATH first, then Homebrew.
CONDA = shutil.which("conda") or "/opt/homebrew/bin/conda"

# Per-step hard wall-clock cap (seconds). A hung BBG/Neo4j/Dropbox child must
# never block the whole 33-step pipeline indefinitely. Generous by default
# (catch a HANG, not a slow step); override per step where known.
DEFAULT_STEP_TIMEOUT = 1800
STEP_TIMEOUTS = {
    "collect_sov_ratings_bql": 900,   # BQL rating history is the slowest BBG pull
}
# Singleton lock so the 07:30 chained run and the 11:30 launchd safety-net
# cannot rebuild the loop DB concurrently (self-collision guard).
LOCK_PATH = BASE_DIR / "Data" / "loop" / ".loop_daily.lock"


def _acquire_singleton_lock():
    """Non-blocking exclusive flock. Returns the open fd (keep it referenced for
    the lifetime of the run) or None if another full run already holds it."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd = open(LOCK_PATH, "w")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        fd.close()
        return None
    fd.write(f"{os.getpid()} {datetime.now().isoformat(timespec='seconds')}\n")
    fd.flush()
    return fd

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
    # ── The graph machine (2026-06-12 build-out) ──────────────────────────
    # PIT graph features: full rebuild each night from the stored edge
    # vintages (graph_edge_vintages; ~5 s). The vintage COLLECTOR
    # (collect_pit_edges.py) is NOT in the nightly job — trade vintages are
    # annual and bank/holder quarterly, so it is run from monthly_update or
    # by hand; the features still move daily because returns move daily.
    ("build_graph_features_pit", [PY, "scripts/loop/build_graph_features_pit.py"]),
    # Fundamental twins: month-end factor vectors -> top-5 cosine twins ->
    # twin-convergence gaps (~10 s full rebuild).
    ("build_similarity_features", [PY, "scripts/loop/build_similarity_features.py"]),
    # Lead-lag network: monthly re-estimated lag-1 cross-correlation edges ->
    # leader gap features (~30 s full rebuild).
    ("build_leadlag_features", [PY, "scripts/loop/build_leadlag_features.py"]),
    # Walk-forward ridge combiner (monthly + daily scores, ~10 s). Must run
    # AFTER the three feature builders and load_etf_flows/load_consensus/
    # load_eco_surprise, which feed it.
    ("build_combiner", [PY, "scripts/loop/build_combiner.py"]),
    # Push discovered SIMILAR_TO / LEADS edges + combiner ranks into Neo4j.
    ("write_graph_discoveries", [PY, "scripts/loop/write_graph_discoveries.py"]),
    ("build_dislocations", [PY, "scripts/loop/build_dislocations.py"]),
    # Price-Discovery Gap Engine (v1 pilot): enhancement layer over
    # dislocation_daily. These steps are additive and feature-flagged in
    # config/gap_engine.yaml; the original brief exists before render runs, so
    # disabling render_top_gaps restores the old brief path.
    ("build_price_state", [PY, "scripts/loop/build_price_state.py"]),
    ("build_gap_episodes", [PY, "scripts/loop/build_gap_episodes.py"]),
    ("render_dislocation_brief", [PY, "scripts/loop/render_dislocation_brief.py"]),
    # Cross-source consistency (A7 — the GSAB defense): sentinels (hard stop)
    # + redundant-pair agreement. Exits non-zero only on a sentinel mismatch.
    ("check_cross_source", [PY, "scripts/loop/check_cross_source.py"]),
    # Evidence packs MUST run after build_dislocations: they freeze headlines
    # for the countries whose dislocations fired in tonight's run (PRD P4 v1;
    # capped at 12 GDELT pulls, D8 excluded).
    ("build_evidence_packs", [PY, "scripts/loop/build_evidence_packs.py"]),
    ("fold_ledgers", [PY, "scripts/loop/ledgers.py", "--rebuild"]),
    # Calibration report (PRD 6.3): regenerates the current month's report
    # nightly from the folded ledgers; stamps itself PARTIAL until >= 10
    # closed theses exist (Phase 4 gate). Must run AFTER fold_ledgers.
    ("calibration_report", [PY, "scripts/loop/calibration_report.py"]),
    # JST long-cycle tail-risk report (read-only): per-country current drawdown
    # -> JST 1870-2020 bucket -> forward real-equity tail (the once-in-a-century
    # p10 the modern sample can't see). Dated xlsx + PDF in Data/loop/risk_reports/.
    # Pure reporting (no warehouse writes, no signal) — safe as the final step.
    ("build_jst_risk_report", [PY, "scripts/loop/build_jst_risk_report.py"]),
]


def _auto_commit_brief() -> None:
    """A2: path-scoped auto-commit of the newest brief so it is durably tracked
    (the 06-15/06-16 briefs sat uncommitted because nothing committed them).
    Path-scoped — never `git add -A`; fail-soft."""
    brief_dir = BASE_DIR / "Data" / "dislocations"
    try:
        briefs = sorted(brief_dir.glob("brief_*.md"), key=lambda p: p.stat().st_mtime)
        if not briefs:
            return
        newest = str(briefs[-1])
        r = subprocess.run(["git", "add", "--", newest], cwd=str(BASE_DIR),
                           capture_output=True, timeout=60)
        if r.returncode != 0:
            print(f"!!! brief auto-commit: git add failed: {r.stderr.decode().strip()}", flush=True)
            return
        if subprocess.run(["git", "diff", "--cached", "--quiet", "--", newest],
                          cwd=str(BASE_DIR), timeout=60).returncode != 0:
            subprocess.run(["git", "commit", "-q", "-m",
                            f"Auto-commit nightly brief {briefs[-1].name}", "--", newest],
                           cwd=str(BASE_DIR), timeout=60)
    except Exception as exc:  # noqa: BLE001
        print(f"!!! brief auto-commit failed (non-fatal): {exc}", flush=True)


def _load_optional_steps() -> set[str]:
    """Read optional=true step names from governance_contract.yaml. Fail-soft."""
    try:
        contract_path = BASE_DIR / "config" / "governance_contract.yaml"
        contract = yaml.safe_load(contract_path.read_text())
        return {s["name"] for s in contract.get('steps', []) if s.get("optional")}
    except Exception as exc:  # noqa: BLE001
        print(f"!!! could not load governance_contract.yaml optional flags: {exc}", flush=True)
        return set()


def _run_step(name: str, cmd: list[str], max_attempts: int = 2,
              timeout: float = DEFAULT_STEP_TIMEOUT) -> int:
    """Run a step subprocess, BOUNDED by `timeout` (the whole process group is
    killed on expiry so conda/python/bbcomm grandchildren can't orphan), with up
    to max_attempts tries. Output streams to the parent (capture=False) so a hang
    is visible. Exit 2 (PARTIAL), a timeout, and a missing binary are NOT retried
    (a hang won't self-heal in 10s; a missing binary never will)."""
    rc = 1
    for attempt in range(max_attempts):
        res = run_bounded(cmd, timeout=timeout, cwd=str(BASE_DIR), capture=False)
        rc = res.returncode
        if res.timed_out:
            print(f"!!! STEP TIMEOUT: {name} exceeded {timeout:.0f}s — process group killed", flush=True)
            return rc
        if rc == 127:
            print(f"!!! STEP BINARY MISSING: {name}", flush=True)
            return rc
        if rc == 0 or rc == 2:
            return rc
        if attempt + 1 < max_attempts:
            wait = 2 ** (attempt + 1) * 5  # 10s, 20s, ...
            print(f"--- RETRY: {name} exited {rc} (attempt {attempt + 1}/{max_attempts}), "
                  f"waiting {wait}s ...", flush=True)
            time.sleep(wait)
    return rc


def main() -> int:
    parser = argparse.ArgumentParser(description="Nightly Alpha-Hunting Loop Layer 1 job.")
    parser.add_argument("--only", default=None, help="Run a single named step.")
    args = parser.parse_args()

    steps = [(n, c) for n, c in STEPS if args.only is None or n == args.only]
    if not steps:
        print(f"No step named {args.only!r}. Steps: {[n for n, _ in STEPS]}")
        return 2

    # Concurrency guard: a full run takes a singleton lock so the 07:30 chained
    # run and the 11:30 launchd safety-net cannot rebuild the loop DB at the same
    # time. Single-step (--only) runs are operator-driven and skip the lock.
    lock_fd = None
    if args.only is None:
        lock_fd = _acquire_singleton_lock()
        if lock_fd is None:
            print("Another full loop run is in progress — skipping (concurrency guard).", flush=True)
            return 0

    # Honour optional=true from the governance contract: a failing optional step
    # is a warning (exit 2 equivalent), not a hard failure that red-lights the loop.
    optional_steps = _load_optional_steps()
    if optional_steps:
        print(f"Optional steps (failures treated as warnings): {sorted(optional_steps)}", flush=True)

    failures = []
    warnings = []
    records = []  # per-step status for the governance run manifest (A1)
    for name, cmd in steps:
        print(f"\n{'─' * 60}\n{datetime.now().strftime('%H:%M:%S')} STEP: {name}\n{'─' * 60}", flush=True)
        started_ts = datetime.now().isoformat(timespec="seconds")
        rc = _run_step(name, cmd, timeout=STEP_TIMEOUTS.get(name, DEFAULT_STEP_TIMEOUT))
        ended_ts = datetime.now().isoformat(timespec="seconds")
        records.append({"name": name, "rc": rc, "started_ts": started_ts, "ended_ts": ended_ts})
        if rc == 0:
            pass  # success
        elif rc == 2:
            # Exit 2 = PARTIAL: the step kept its completed work and the missing
            # part self-heals next run (e.g. evidence packs hit GDELT's rate
            # limit after writing some packs). Warn, don't fail the job.
            warnings.append(name)
            print(f"~~~ STEP PARTIAL: {name} (exit 2) - recorded as warning", flush=True)
        elif name in optional_steps:
            # Optional step failed: same treatment as PARTIAL — warn but don't
            # kill the loop. The governance contract explicitly marks these steps
            # as non-critical (Bloomberg-down, Neo4j-down, GDELT rate-limit, etc.).
            warnings.append(name)
            print(f"~~~ OPTIONAL STEP FAILED: {name} (exit {rc}) - treated as warning", flush=True)
        else:
            failures.append(name)
            print(f"!!! STEP FAILED: {name} (exit {rc}) - continuing with remaining steps", flush=True)

    # Governance run manifest (A1): observability only. FAIL-SOFT — a manifest
    # bug must never change this job's exit code (A2/A8 are the fail-loud
    # readers that turn its contents into a hard gate).
    try:
        from scripts.loop import run_manifest
        m = run_manifest.write_manifest(records)
        if not m["overall_ok"]:
            print(f"run_manifest: NOT OK — fail={m['fail_steps']} stale={m['stale_steps']}"
                  + (f" unknown={m['unknown_steps']}" if m["unknown_steps"] else ""), flush=True)
    except Exception as exc:  # noqa: BLE001
        print(f"!!! run_manifest write failed (non-fatal): {exc}", flush=True)

    # Governance tail (A2 + A8): auto-commit the brief so it is durably tracked,
    # then heartbeat (pushes on trouble) and the scorecard the CoS agent reads.
    # All fail-soft — none of this changes the job's exit code.
    rc_final = 1 if failures else 0
    _auto_commit_brief()
    for gov_cmd, label in (([PY, "scripts/loop/heartbeat.py", "--exit-code", str(rc_final)], "heartbeat"),
                           ([PY, "scripts/loop/build_governance_scorecard.py"], "scorecard")):
        try:
            run_bounded(gov_cmd, timeout=300, cwd=str(BASE_DIR), capture=False)
        except Exception as exc:  # noqa: BLE001
            print(f"!!! governance {label} failed (non-fatal): {exc}", flush=True)

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
