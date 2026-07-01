#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from regime_ew.src.contrarian_strategy import run_contrarian_backtest  # noqa: E402


def main() -> None:
    payload = run_contrarian_backtest()
    print(json.dumps({"status": payload["status"], "strategies": len(payload["strategies"])}, indent=2))


if __name__ == "__main__":
    main()

