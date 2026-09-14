# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/src/p07_replay.py
#
# PRD 11.3 — run the frozen historical replay on REAL labels. Produces the
# immutable forecast store + fit records that P08 evaluates. Restartable
# via hash-matched checkpoints; refuses to mix versions (T48/T49). Prints
# no outer performance (T45).
#
#   python p07_replay.py [--out <dir>]
# =============================================================================
from __future__ import annotations

import argparse
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runner import ReplayRunner  # noqa: E402

DEFAULT_OUT = Path(
    "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/"
    "experiments/nonlinear_country_returns/p07_replay_real")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--labels", default=None,
                    help="override labels parquet (controls use pseudo)")
    ap.add_argument("--tag", default="real")
    args = ap.parse_args()
    r = ReplayRunner(Path(args.out), labels_path=args.labels,
                     tag=args.tag, quiet=False)
    res = r.run()
    print("REPLAY COMPLETE:", res)


if __name__ == "__main__":
    main()
