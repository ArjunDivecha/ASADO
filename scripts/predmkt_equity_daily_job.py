"""
=============================================================================
SCRIPT NAME: predmkt_equity_daily_job.py
=============================================================================

INPUT FILES:
- Polymarket Gamma + CLOB APIs (via the two child scripts below)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/predmkt_equity_universe.yaml
  (read + regenerated in step 1)

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/predmkt_equity_universe.yaml
  (refreshed universe — step 1)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/predmkt_equity/markets.parquet
  and history/{conditionId}.parquet (harvested/merged — step 2)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/logs/predmkt_equity_daily.log
  (via launchd redirection)

VERSION: 1.0
LAST UPDATED: 2026-07-03
AUTHOR: Claude Code (for Arjun Divecha)

DESCRIPTION:
Daily orchestrator for the Tier 1 overnight PM->equity data layer. Runs two
steps, each isolated (one failing never stops the other, house style):
  1. discover_predmkt_equity_universe.py  — refresh the active universe YAML
     (Polymarket rotates firm markets weekly).
  2. backtest_overnight_pull.py --refresh-active — harvest newly-closed
     markets' price histories AND merge-refresh active markets' histories
     before Polymarket's ~30-day retention purges them. THIS IS THE HISTORY
     ACCUMULATOR: every day it doesn't run is backtest sample lost forever.
Exits non-zero if any step failed (so launchd logs show red), but always
attempts every step.

DEPENDENCIES:
- project venv (requests, pandas, pyyaml, pyarrow)

USAGE:
  python scripts/predmkt_equity_daily_job.py
  (scheduled: launchd com.arjundivecha.asado-predmkt-equity-harvest, daily 16:45 local)

NOTES:
- Runtime dominated by step 2's first-day catch-up; steady-state ~5-10 min
  (a few hundred new closures/day + ~250 active refreshes).
=============================================================================
"""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
PYTHON = BASE_DIR / "venv" / "bin" / "python"

STEPS = [
    ("universe discovery", [str(PYTHON), str(BASE_DIR / "scripts" / "discover_predmkt_equity_universe.py")]),
    (
        "history harvest",
        [str(PYTHON), str(BASE_DIR / "scripts" / "backtest_overnight_pull.py"), "--refresh-active"],
    ),
]


def main() -> int:
    failures = 0
    print(f"=== predmkt_equity_daily_job start {datetime.now():%Y-%m-%d %H:%M:%S} ===", flush=True)
    for name, cmd in STEPS:
        print(f"--- step: {name} ---", flush=True)
        try:
            rc = subprocess.run(cmd, cwd=BASE_DIR, timeout=3 * 3600).returncode
        except subprocess.TimeoutExpired:
            print(f"❌ step '{name}' timed out after 3h")
            rc = 1
        except Exception as exc:
            print(f"❌ step '{name}' crashed: {exc}")
            rc = 1
        if rc != 0:
            print(f"❌ step '{name}' exited {rc}")
            failures += 1
        else:
            print(f"✓ step '{name}' ok")
    print(f"=== done, {failures} failed step(s) ===", flush=True)
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
