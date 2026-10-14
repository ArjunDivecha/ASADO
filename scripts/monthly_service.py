#!/usr/bin/env python3
"""Hourly monthly service: readiness -> one durable worker attempt -> readiness.

Inputs: ASADO/config/monthly_{readiness,worker}.json and accepted/attempt state.
Outputs: ASADO/Data/monthly receipts/alerts; worker may publish the approved NN-core
data/NN after all gates. Accepted October2026 exits before all producer calls.
"""
import os
from pathlib import Path
import subprocess
import sys


def main():
    scripts = Path(__file__).resolve().parent
    env = dict(os.environ, ASADO_LOCK_GUARD_KILL="0", TZ="America/Los_Angeles", PYTHONUNBUFFERED="1")
    subprocess.run([sys.executable, str(scripts / "monthly_readiness.py"), "--notify"], env=env, check=False)
    worker = subprocess.run([sys.executable, str(scripts / "monthly_worker.py"), "--tick"], env=env, check=False)
    subprocess.run([sys.executable, str(scripts / "monthly_readiness.py"), "--notify"], env=env, check=False)
    return worker.returncode


if __name__ == "__main__":
    raise SystemExit(main())
