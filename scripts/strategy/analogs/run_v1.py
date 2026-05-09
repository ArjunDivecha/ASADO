"""
=============================================================================
SCRIPT NAME: scripts/strategy/analogs/run_v1.py
=============================================================================

INPUT FILES:
- (downstream of monthly_update — this script orchestrates strategy build only)

OUTPUT FILES:
- Data/strategy/analogs/v1/{pit_audit.csv, baselines.parquet,
  worldstates.parquet, analog_matches.parquet, signals.parquet,
  backtest.parquet, Country_Forecasts.xlsx, diagnostics.pdf}

VERSION: 1.0
LAST UPDATED: 2026-04-19
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
End-to-end orchestrator for Strategy #1 — World-State Analog Country
Selection v1 MVP. Runs every stage in dependency order:

  Stage 0 — data prep:
    1. build_returns        (load 1MRet → DuckDB.country_returns_monthly)
    2. pit_audit            (flag PIT-unsafe variables → pit_audit.csv)
    3. baselines            (equal-weight benchmark → baselines.parquet)

  Stage 1 — strategy:
    4. build_worldstate     (PCA worldstate vectors → worldstates.parquet)
    5. analog_search        (top-k cosine search → analog_matches.parquet)
    6. aggregate            (similarity-weighted median → signals.parquet)
    7. backtest             (long-only top-7 → backtest.parquet)
    8. report               (Country_Forecasts.xlsx + diagnostics.pdf)

DEPENDENCIES:
- (each stage's deps; same venv)

USAGE:
  python scripts/strategy/analogs/run_v1.py            # run all stages
  python scripts/strategy/analogs/run_v1.py --stage 0  # data prep only
  python scripts/strategy/analogs/run_v1.py --stage 1  # strategy only
  python scripts/strategy/analogs/run_v1.py --dry-run  # print plan, no exec

NOTES:
- Each stage script is invoked as a subprocess so a stage failure logs
  loudly and stops the run (no silent fallbacks per project policy).
=============================================================================
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.strategy.analogs import config as C  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent

STAGE_0 = [
    ("build_returns", HERE / "build_returns.py"),
    ("pit_audit", HERE / "pit_audit.py"),
    ("baselines", HERE / "baselines.py"),
]
STAGE_1 = [
    ("build_worldstate", HERE / "build_worldstate.py"),
    ("analog_search", HERE / "analog_search.py"),
    ("aggregate", HERE / "aggregate.py"),
    ("backtest", HERE / "backtest.py"),
    ("report", HERE / "report.py"),
]


def run_stage(name: str, script: Path, dry_run: bool) -> None:
    cmd = [sys.executable, str(script)]
    logger.info("[%s] %s", name, " ".join(cmd))
    if dry_run:
        return
    proc = subprocess.run(cmd, check=False)
    if proc.returncode != 0:
        raise SystemExit(f"Stage {name} failed (rc={proc.returncode})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", choices=["0", "1"], default=None,
                    help="Run only stage 0 (data prep) or stage 1 (strategy).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print plan without executing.")
    args = ap.parse_args()

    C.ensure_dirs()

    if args.stage in (None, "0"):
        for name, script in STAGE_0:
            run_stage(name, script, args.dry_run)
    if args.stage in (None, "1"):
        for name, script in STAGE_1:
            run_stage(name, script, args.dry_run)

    logger.info("v1 run complete. Outputs in %s", C.STRATEGY_DIR)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
