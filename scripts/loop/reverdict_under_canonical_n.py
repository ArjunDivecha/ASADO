#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: reverdict_under_canonical_n.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/ledgers/hypothesis_ledger.jsonl
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/harness_runs/*.json
  (the stored result per verdict — carries deflated_sharpe_block + ic + portfolio)

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/governance/reverdict_under_canonical_n.json
  (the full recompute table: old/new N, old/new deflated Sharpe, old/new verdict)
- (with --apply) appends a hyp_verdict event to the hypothesis ledger ONLY for
  verdicts that FLIP under the corrected N. Append-only; zero new registrations.

VERSION: 1.0
LAST UPDATED: 2026-06-17
AUTHOR: Arjun Divecha (built by agent session, Governance Layer PRD v1.2, item A5 follow-up)

DESCRIPTION:
A5 in-place re-verdict, done ANALYTICALLY (the PRD-preferred path). A5 fixed the
deflated-Sharpe trial count N (canonical, variable-derived) for FUTURE
evaluations; this re-scores the ALREADY-tested hypotheses under the corrected N
WITHOUT re-running any backtest. Only the deflated-Sharpe gate depends on N:
  new_deflated_sharpe = sharpe_per_period - expected_max_sharpe(new_N, n_obs)
Every other gate (NW-t, positive-year share, net-cost Sharpe) is N-independent
and read from the stored result, so the recompute isolates the N effect exactly
(no data-drift confound). The real decide_verdict() is reused.

A verdict event is appended ONLY when the verdict actually flips; unchanged
verdicts were already correct under the new N, so no ledger churn.

DEPENDENCIES:
- (project venv)

USAGE:
  python scripts/loop/reverdict_under_canonical_n.py            # DRY RUN (no writes)
  python scripts/loop/reverdict_under_canonical_n.py --apply    # append flip events
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.loop import ledgers
from scripts.loop.ledgers import (attach_verdict, canonical_family_of,
                                  family_trial_count, fold_hypotheses)
from scripts.harness.evaluate_signal import decide_verdict, expected_max_sharpe
from scripts.loop.loopdb import LOOP_DIR

OUT_PATH = LOOP_DIR / "governance" / "reverdict_under_canonical_n.json"


def _metrics_from_result(res: dict[str, Any], new_dsr: float) -> dict[str, Any]:
    """Rebuild the exact metrics dict evaluate_signal feeds decide_verdict, with
    deflated_sharpe replaced by the N-corrected value. Only portfolio-ran
    results reach here (coverage/history passed)."""
    freq = res["frequency"]
    h0 = res["horizons"][0]
    plabel = f"{h0}m" if freq == "monthly" else f"{h0}d"
    prim = res["ic"][plabel]
    direction = res["direction"]
    primary_nw_t = prim.get("nw_t")
    pct_pos = prim.get("pct_positive_years")
    if direction == "lower_is_better":
        primary_nw_t = -primary_nw_t if primary_nw_t is not None else None
        yic = prim.get("yearly_ic") or {}
        pct_pos = (round(sum(1 for v in yic.values() if v < 0) / len(yic), 3)
                   if yic else None)
    net25 = (res.get("portfolio") or {}).get("net", {}).get("25bps", {})
    return {
        "coverage_fail": False, "history_fail": False,
        "primary_nw_t": primary_nw_t, "pct_positive_years": pct_pos,
        "ls_sharpe_net25": net25.get("ls_sharpe"),
        "top_excess_net25": net25.get("top_excess_ann_return"),
        "deflated_sharpe": new_dsr,
        "portfolios_skipped": bool(res.get("portfolios_skipped")),
        "portfolio_error": (res.get("portfolio") or {}).get("error"),
    }


def build_recompute() -> dict[str, Any]:
    hyps = fold_hypotheses()
    recomputes, flips, skipped = [], [], 0
    for hid, h in hyps.items():
        vj = h.get("verdict_json") or {}
        rf = vj.get("result_file")
        if not rf or not os.path.exists(rf):
            skipped += 1
            continue
        res = json.load(open(rf))
        dsb = res.get("deflated_sharpe_block") or {}
        sr_p, n_obs = dsb.get("sharpe_per_period"), dsb.get("n_obs")
        if sr_p is None or not n_obs:
            skipped += 1   # INSUFFICIENT / no portfolio -> N-independent
            continue
        new_N = family_trial_count(canonical_family_of(h))
        new_emax = expected_max_sharpe(new_N, n_obs)
        new_dsr = round(float(sr_p) - float(new_emax), 4)
        new_verdict, _ = decide_verdict(_metrics_from_result(res, new_dsr), res["frequency"])
        old_verdict = h.get("verdict")
        rec = {
            "hypothesis_id": hid,
            "canonical_family": canonical_family_of(h),
            "old_family_key": h.get("family_key"),
            "n_old": dsb.get("n_trials_family"), "n_new": new_N,
            "deflated_sharpe_old": dsb.get("deflated_sharpe"), "deflated_sharpe_new": new_dsr,
            "verdict_old": old_verdict, "verdict_new": new_verdict,
            "flipped": new_verdict != old_verdict,
        }
        recomputes.append(rec)
        if rec["flipped"]:
            flips.append(rec)
    return {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "n_recomputed": len(recomputes), "n_flipped": len(flips),
        "n_skipped_n_independent": skipped,
        "flips": flips, "recomputes": sorted(recomputes, key=lambda r: r["hypothesis_id"]),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="A5 analytical re-verdict under canonical N.")
    ap.add_argument("--apply", action="store_true", help="Append hyp_verdict events for FLIPS.")
    args = ap.parse_args()

    out = build_recompute()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(out, indent=2, default=str))

    print(f"recomputed {out['n_recomputed']} tested hypotheses "
          f"({out['n_skipped_n_independent']} skipped as N-independent); "
          f"{out['n_flipped']} FLIP under canonical N")
    for r in out["flips"]:
        print(f"  {r['hypothesis_id']}  {r['canonical_family']:18} "
              f"N {r['n_old']}->{r['n_new']}  DSR {r['deflated_sharpe_old']}->{r['deflated_sharpe_new']}  "
              f"{r['verdict_old']} -> {r['verdict_new']}")
    print(f"Wrote {OUT_PATH}")

    if not args.apply:
        print("\nDRY RUN — no ledger writes. Re-run with --apply to append flip events.")
        return 0

    for r in out["flips"]:
        attach_verdict(r["hypothesis_id"], r["verdict_new"], {
            "reverdict": "canonical_N_analytical",
            "n_old": r["n_old"], "n_new": r["n_new"],
            "deflated_sharpe_old": r["deflated_sharpe_old"],
            "deflated_sharpe_new": r["deflated_sharpe_new"],
            "verdict_old": r["verdict_old"],
            "note": "A5 analytical re-verdict under canonical family N (no backtest re-run).",
        })
    if out["flips"]:
        ledgers.rebuild_duckdb_tables()
        print(f"\nAPPLIED {len(out['flips'])} flip verdict event(s); loop DB rebuilt.")
    else:
        print("\nNo flips — nothing appended.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
