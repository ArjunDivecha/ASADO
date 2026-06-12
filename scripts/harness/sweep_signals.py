#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: sweep_signals.py
=============================================================================

INPUT FILES:
- A sweep spec YAML passed via --spec, e.g.
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/sweeps/new_bbg_layers_2026_06.yaml
  Family-level defaults + a list of signals, each with its OWN mechanism
  paragraph (pre-registration is per signal, never templated away).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/ledgers/hypothesis_ledger.jsonl
  Existing registrations (used to skip already-tested identical specs).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb (read-only)
  and /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
  Signal + return data (read through the harness).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/harness_runs/sweeps/{sweep_name}_{ts}/
    sweep_summary.json   - one entry per signal, APPENDED AFTER EACH RUN
                           (incremental persistence; a crash loses nothing)
    sweep_summary.xlsx   - same content as a sortable sheet, rewritten after
                           each run
- Everything the harness itself writes per run (harness_runs/*.json,
  harness_results rows, ledger verdict events).

VERSION: 1.0
LAST UPDATED: 2026-06-12
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop)

DESCRIPTION:
Batch front-end for the skeptic harness. Give it a YAML family of signal
candidates; it pre-registers each one in the hypothesis ledger (so the
deflated-Sharpe trial counting stays honest - EVERY candidate counts as a
trial, not just the winners), runs evaluate_signal on each, and writes a
running leaderboard. A 10th grader's version: instead of testing one idea
at a time by hand, you hand the referee a whole list - and the referee
writes every attempt down in the book BEFORE looking at any scores, so
nobody can pretend the losers never happened.

HONESTY RAILS:
- Each signal entry MUST carry its own mechanism paragraph (>= 15 words),
  written before results. No family-level boilerplate is auto-copied.
- Re-running a sweep does NOT double-charge the family: a signal whose
  (spec + mechanism) hash already has a verdict in the ledger is skipped
  (reported as cached) unless --force is passed. --force registers a NEW
  hypothesis and charges a new trial - by design.
- One signal failing (bad table name, zero rows) never stops the sweep;
  the failure is recorded in the summary with the error text.

SWEEP SPEC FORMAT (YAML):
  sweep_name: new_bbg_layers
  family_key: bbg_skill_2026_06        # trial-accounting family
  archetype: A4                        # default, per-signal override allowed
  frequency: daily                     # default, per-signal override allowed
  start_date: "2008-01-01"             # default, per-signal override allowed
  signals:
    - name: fx_carry_level
      table: market_implied_signals    # loop table (unqualified) or warehouse table
      variable: FX_CARRY_3M_PCT
      direction: higher_is_better
      mechanism: >
        At least fifteen words explaining the economic mechanism BEFORE
        seeing any results, e.g. higher forward-implied carry compensates ...
      # optional: source, frequency, archetype, start_date, universe
      #           (comma list of exact T2 names for structurally narrow
      #           layers - scales the coverage gate + portfolio width),
      #           publication_lag_months, hold_days, horizons

DEPENDENCIES:
- duckdb, pandas, numpy, scipy, pyyaml, openpyxl (project venv)

USAGE:
 python scripts/harness/sweep_signals.py --spec config/sweeps/my_sweep.yaml
 python scripts/harness/sweep_signals.py --spec ... --dry-run   # validate + list, no writes
 python scripts/harness/sweep_signals.py --spec ... --force     # re-test cached specs (new trials)

NOTES:
- Verdict meanings (PRD 5.3): WATCH (all gates pass) / WEAK / DEAD /
  INSUFFICIENT_COVERAGE / INSUFFICIENT_HISTORY.
- The leaderboard sorts WATCH first, then by |NW-t|.
- Runtime: roughly 5-30s per signal (daily runs are the slow ones).
=============================================================================
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.harness.evaluate_signal import evaluate_signal
from scripts.loop.ledgers import fold_hypotheses, register_hypothesis
from scripts.loop.loopdb import LOOP_DIR

SWEEPS_DIR = LOOP_DIR / "harness_runs" / "sweeps"

SIGNAL_KEYS_FOR_SPEC = (
    "table", "variable", "source", "publication_lag_months", "hold_days",
)
VERDICT_ORDER = {"WATCH": 0, "WEAK": 1, "DEAD": 2,
                 "INSUFFICIENT_COVERAGE": 3, "INSUFFICIENT_HISTORY": 3,
                 "ERROR": 4, "CACHED": 5}


def load_spec(path: Path) -> dict[str, Any]:
    """Load and validate the sweep YAML. FAIL-IS-FAIL on any bad entry."""
    spec = yaml.safe_load(path.read_text())
    problems: list[str] = []
    for key in ("sweep_name", "family_key", "signals"):
        if not spec.get(key):
            problems.append(f"top-level '{key}' is required")
    if problems:
        raise ValueError("; ".join(problems))

    names = set()
    for i, sig in enumerate(spec["signals"]):
        tag = sig.get("name", f"#{i}")
        for key in ("name", "table", "variable", "direction", "mechanism"):
            if not sig.get(key):
                problems.append(f"signal {tag}: '{key}' is required")
        if sig.get("direction") not in ("higher_is_better", "lower_is_better", None):
            problems.append(f"signal {tag}: bad direction {sig.get('direction')!r}")
        if sig.get("mechanism") and len(str(sig["mechanism"]).split()) < 15:
            problems.append(f"signal {tag}: mechanism must be >= 15 words (pre-registration)")
        if sig.get("name") in names:
            problems.append(f"duplicate signal name {sig.get('name')!r}")
        names.add(sig.get("name"))
    if problems:
        raise ValueError("sweep spec invalid:\n  - " + "\n  - ".join(problems))
    return spec


def build_signal_spec(sig: dict[str, Any]) -> dict[str, Any]:
    """The exact dict handed to register_hypothesis AND evaluate_signal."""
    out = {k: sig[k] for k in SIGNAL_KEYS_FOR_SPEC if sig.get(k) is not None}
    return out


def spec_hash(signal_spec: dict[str, Any], mechanism: str) -> str:
    """Identical recipe to ledgers.register_hypothesis - lets us recognise
    a spec that is already registered without re-registering it."""
    return hashlib.sha256(
        (json.dumps(signal_spec, sort_keys=True) + mechanism).encode()
    ).hexdigest()


def find_existing(family_key: str, h: str) -> Optional[dict[str, Any]]:
    """Latest registered hypothesis in this family with the same spec hash."""
    matches = [
        hyp for hyp in fold_hypotheses().values()
        if hyp["family_key"] == family_key and hyp["signal_spec_hash"] == h
    ]
    return matches[-1] if matches else None


def write_summary(out_dir: Path, rows: list[dict[str, Any]]) -> None:
    """Rewrite summary JSON + xlsx from the accumulated rows (called after
    EVERY signal so a crash mid-sweep loses nothing)."""
    (out_dir / "sweep_summary.json").write_text(json.dumps(rows, indent=2, default=str))
    df = pd.DataFrame(rows)
    df["_order"] = df["verdict"].map(VERDICT_ORDER).fillna(9)
    df["_t"] = pd.to_numeric(df["nw_t"], errors="coerce").abs()
    df = df.sort_values(["_order", "_t"], ascending=[True, False]).drop(columns=["_order", "_t"])
    df.to_excel(out_dir / "sweep_summary.xlsx", index=False)


def run_sweep(spec_path: Path, dry_run: bool, force: bool) -> int:
    spec = load_spec(spec_path)
    family = spec["family_key"]
    defaults = {
        "archetype": spec.get("archetype", "other"),
        "frequency": spec.get("frequency", "monthly"),
        "start_date": spec.get("start_date", "2008-01-01"),
    }

    print(f"Sweep '{spec['sweep_name']}' | family={family} | {len(spec['signals'])} signals")
    if dry_run:
        for sig in spec["signals"]:
            existing = find_existing(family, spec_hash(build_signal_spec(sig), str(sig["mechanism"]).strip()))
            state = f"cached ({existing['hypothesis_id']}, {existing.get('verdict')})" if existing and existing.get("verdict") else "will register + run"
            print(f"  {sig['name']:<28} {sig['table']}.{sig['variable']:<28} "
                  f"{sig.get('frequency', defaults['frequency']):<8} {state}")
        print("Dry run - nothing written.")
        return 0

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = SWEEPS_DIR / f"{spec['sweep_name']}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []

    for i, sig in enumerate(spec["signals"], 1):
        name = sig["name"]
        signal_spec = build_signal_spec(sig)
        mechanism = str(sig["mechanism"]).strip()
        frequency = sig.get("frequency", defaults["frequency"])
        row: dict[str, Any] = {
            "name": name, "table": sig["table"], "variable": sig["variable"],
            "direction": sig["direction"], "frequency": frequency,
        }
        print(f"\n[{i}/{len(spec['signals'])}] {name} ({sig['table']}.{sig['variable']}, {frequency})")

        existing = find_existing(family, spec_hash(signal_spec, mechanism))
        if existing and existing.get("verdict") and not force:
            print(f"  cached: {existing['hypothesis_id']} already tested -> {existing['verdict']} (use --force to re-test)")
            vj = existing.get("verdict_json") or {}
            row.update({"hypothesis_id": existing["hypothesis_id"], "verdict": "CACHED",
                        "cached_verdict": existing["verdict"],
                        "mean_ic": vj.get("mean_ic"), "nw_t": vj.get("nw_t"),
                        "deflated_sharpe": vj.get("deflated_sharpe"),
                        "result_file": vj.get("result_file")})
            rows.append(row)
            write_summary(out_dir, rows)
            continue

        try:
            if existing and not existing.get("verdict"):
                hyp_id = existing["hypothesis_id"]   # registered earlier, never run
                print(f"  re-using registered-but-untested {hyp_id}")
            else:
                hyp_id = register_hypothesis(
                    archetype=sig.get("archetype", defaults["archetype"]),
                    family_key=family,
                    mechanism_text=mechanism,
                    signal_spec=signal_spec,
                    author=spec.get("author", "agent_sweep"),
                )
                print(f"  registered {hyp_id}")
            result = evaluate_signal(
                hypothesis_id=hyp_id,
                signal_spec=signal_spec,
                direction=sig["direction"],
                frequency=frequency,
                horizons=sig.get("horizons"),
                start_date=sig.get("start_date", defaults["start_date"]),
                universe=sig.get("universe", spec.get("universe", "t2_34")),
            )
            prim = result["ic"][list(result["ic"].keys())[0]]  # primary horizon
            row.update({
                "hypothesis_id": hyp_id,
                "verdict": result["verdict"],
                "mean_ic": prim["mean_ic"],
                "nw_t": prim["nw_t"],
                "pct_positive_years": prim["pct_positive_years"],
                "ls_sharpe_net25": result.get("portfolio", {}).get("net", {}).get("25bps", {}).get("ls_sharpe"),
                "deflated_sharpe": result.get("deflated_sharpe_block", {}).get("deflated_sharpe"),
                "n_dates": result["coverage"]["n_dates"],
                "result_file": result.get("result_file"),
            })
            print(f"  VERDICT {result['verdict']}  ic={prim['mean_ic']} nw_t={prim['nw_t']} "
                  f"dsr={row['deflated_sharpe']}")
        except Exception as exc:  # one bad signal never kills the sweep
            row.update({"verdict": "ERROR", "error": f"{type(exc).__name__}: {exc}"})
            print(f"  ERROR: {exc}")

        rows.append(row)
        write_summary(out_dir, rows)

    # ── leaderboard ────────────────────────────────────────────────────────
    print("\n" + "=" * 78)
    print(f"SWEEP COMPLETE - {len(rows)} signals | family '{family}'")
    print("=" * 78)
    ordered = sorted(rows, key=lambda r: (VERDICT_ORDER.get(r["verdict"], 9),
                                          -abs(r.get("nw_t") or 0)))
    for r in ordered:
        v = r["verdict"] + (f"({r['cached_verdict']})" if r["verdict"] == "CACHED" else "")
        print(f"  {v:<28} {r['name']:<28} ic={r.get('mean_ic')} "
              f"nw_t={r.get('nw_t')} dsr={r.get('deflated_sharpe')}")
    print(f"\nSummary: {out_dir / 'sweep_summary.xlsx'}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Batch-register and harness-evaluate a family of signals.")
    p.add_argument("--spec", required=True, help="Path to the sweep YAML.")
    p.add_argument("--dry-run", action="store_true", help="Validate + list, write nothing.")
    p.add_argument("--force", action="store_true",
                   help="Re-test signals whose identical spec already has a verdict (charges new trials).")
    args = p.parse_args()
    return run_sweep(Path(args.spec), args.dry_run, args.force)


if __name__ == "__main__":
    sys.exit(main())
