#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: reverdict_v4.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-harness-v4/ledgers/hypothesis_ledger.jsonl
  The append-only hypothesis ledger (59 hyp_register events). Read to enumerate
  every existing hypothesis id and to recover the last verdict per id. This is
  the worktree ledger — the scope-visible surface the contract's scope check
  reads. evaluate_signal appends the fresh hyp_verdict events back to this file.
- The latest per-hypothesis result JSON referenced by each id's last verdict,
  e.g. /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/harness_runs/{id}_{ts}.json
  Read to recover the run parameters (direction, frequency, horizons, universe,
  start_date) that registration itself does not store. Absolute paths as
  recorded in the ledger's verdict_json.result_file.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-harness-v4/Data/asado.duckdb (read-only, via loopdb)
  Signal data. NOTE: gitignored / not checked out into the worktree; see the
  "RUNTIME PREREQUISITE" section below — this driver fails loudly with the exact
  fix if the warehouse is absent.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-harness-v4/Data/loop/asado_loop.duckdb
  Marking surface (country returns) + harness result tables, opened/closed per
  evaluation by the harness itself (open->measure->close; this driver never
  holds a DuckDB connection).

OUTPUT FILES:
- /Users/arjundivecha/.../ASADO-exp-harness-v4/ledgers/hypothesis_ledger.jsonl
  One fresh hyp_verdict event appended per SUCCESSFULLY re-run hypothesis id
  (written by evaluate_signal's attach_verdict; never by this driver directly).
  Zero new hyp_register events (INV4).
- /Users/arjundivecha/.../ASADO/Data/loop/harness_runs/{id}_{ts}.json
  One fresh per-run result JSON per re-run id (written by the harness), each
  carrying the v4 execution_convention block (INV7).
- /Users/arjundivecha/.../ASADO/Data/loop/harness_runs/reverdict_v4_<date>/summary.parquet
- /Users/arjundivecha/.../ASADO/Data/loop/harness_runs/reverdict_v4_<date>/summary.xlsx
  Old-vs-new verdict table (one row per hypothesis id, 59 rows) with columns
  hypothesis_id, variable, family, frequency, old_verdict, new_verdict,
  old_nw_t, new_nw_t, old_dsr_basis, new_dsr, lag_days_effective, status.
- /Users/arjundivecha/.../ASADO/Data/loop/harness_runs/reverdict_v4_<date>/manifest.json
  Machine-readable run manifest: reverdicted ids, refused ids, result-JSON
  paths (consumed by the INV4 check here and by check_convention_labels.py / G4).

VERSION: 1.0
LAST UPDATED: 2026-07-14
AUTHOR: Arjun Divecha (built by agent session, HARNESS-V4-HONEST-LEDGER-001)

DESCRIPTION:
The honest re-verdict sweep (contract gate G3, requires_permission: true). It
re-evaluates every one of the 59 pre-registered hypotheses through the SAME
front door a human would use (scripts.harness.evaluate_signal.evaluate_signal
with the hypothesis's own id), so the v4 daily execution embargo (min 1 trading
day, applied even to ZERO_LAG_SOURCES) is now baked into every recorded verdict.
It NEVER registers a new hypothesis and NEVER calls sweep_signals --force
(either would corrupt the deflated-Sharpe trial count N for the family). After
re-verdicting it runs an INV4 ledger-integrity check (0 new registrations,
exactly one new verdict per re-run id, per-family trial-count N unchanged) and
writes an old-vs-new verdict table (parquet + xlsx) plus a manifest.

One of the 59, H_20260610_001 (variable 12MRet), is a forward-return lookahead
that the harness blacklist (INV5) correctly REFUSES to run. It is recorded in
the summary as REFUSED_BLACKLIST (still one of the 59 rows) and produces no
verdict event; the INV4 check therefore asserts new_verdict_events ==
len(reverdicted_ids) (the ids that actually produced a verdict), not a blind 59.
See implementation-notes.md deviation D1.

A 10th grader's version: it re-grades every past experiment with the corrected
stopwatch (you can't trade at the exact instant you saw the signal), then proves
it didn't sneak any extra experiments into the gradebook.

RUNTIME PREREQUISITE (this driver is run by an operator OUTSIDE the 06:00-08:30
PT nightly window, after Arjun's approval — it is NOT executed in Build Mode):
The worktree does not contain the (gitignored) databases. Before running, point
the worktree's Data/ at the production copies, e.g.:
    ln -s "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb" \
          "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-harness-v4/Data/asado.duckdb"
    ln -s "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop" \
          "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO-exp-harness-v4/Data/loop"
The driver preflight fails loudly with this instruction if the warehouse is absent.

DEPENDENCIES:
- pandas, pyarrow, openpyxl (project venv); scripts.harness.evaluate_signal;
  scripts.loop.ledgers; scripts.loop.loopdb.

USAGE:
  "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/venv/bin/python" \
      scripts/harness/reverdict_v4.py            # run the sweep (permissioned)
  ...reverdict_v4.py --check-integrity-only DIR  # re-run only the INV4 check on a prior manifest
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.harness.evaluate_signal import evaluate_signal, FORWARD_RETURN_VARIABLES
from scripts.loop import ledgers as L
from scripts.loop.loopdb import LOOP_DIR, MAIN_DB


RUNS_DIR = LOOP_DIR / "harness_runs"


# ── INV4 — pure ledger-integrity report (no I/O; unit-testable) ──────────────

def _fold_last_verdict(events: list[dict[str, Any]]) -> dict[str, Optional[str]]:
    """id -> its LAST verdict string (or None if never verdicted), from events."""
    out: dict[str, Optional[str]] = {}
    for e in events:
        if e.get("event") == "hyp_register":
            out.setdefault(e["hypothesis_id"], None)
        elif e.get("event") == "hyp_verdict":
            out[e["hypothesis_id"]] = e.get("verdict")
    return out


def _charge(verdict: Optional[str]) -> float:
    """Mirror of ledgers._trial_charge: 1.0 tested, 0.5 INSUFFICIENT_*, 0 untested."""
    if verdict is None:
        return 0.0
    return 0.5 if str(verdict).startswith("INSUFFICIENT") else 1.0


def _family_of(events: list[dict[str, Any]]) -> dict[str, str]:
    """id -> family_key from its hyp_register event."""
    return {e["hypothesis_id"]: e.get("family_key", "unknown")
            for e in events if e.get("event") == "hyp_register"}


def ledger_integrity_report(before_events: list[dict[str, Any]],
                            after_events: list[dict[str, Any]],
                            reverdicted_ids: list[str]) -> dict[str, Any]:
    """INV4 — compare the hypothesis ledger before/after the re-verdict sweep.

    Pure function on event lists so it is unit-testable with synthetic ledgers
    and never opens a database. Checks:
      1. new hyp_register events == 0 (no new registrations);
      2. new hyp_verdict events == len(reverdicted_ids) (one per re-run id);
      3. per-family REGISTRATION count unchanged (bulletproof: registrations
         are the trial units);
      4. per-family charged trial-count N unchanged, where N mirrors
         family_trial_count (sum of per-id charges, grouped by family_key).
    Returns a report dict with per-check pass flags and an overall `ok`.
    """
    def count(events, ev):
        return sum(1 for e in events if e.get("event") == ev)

    reg_before, reg_after = count(before_events, "hyp_register"), count(after_events, "hyp_register")
    ver_before, ver_after = count(before_events, "hyp_verdict"), count(after_events, "hyp_verdict")

    fam_before = _family_of(before_events)
    fam_after = _family_of(after_events)
    reg_ct_before = Counter(fam_before.values())
    reg_ct_after = Counter(fam_after.values())

    verd_before = _fold_last_verdict(before_events)
    verd_after = _fold_last_verdict(after_events)
    N_before: Counter = Counter()
    N_after: Counter = Counter()
    for hid, fam in fam_before.items():
        N_before[fam] += _charge(verd_before.get(hid))
    for hid, fam in fam_after.items():
        N_after[fam] += _charge(verd_after.get(hid))
    # family_trial_count floors at max(1, round(N)); compare on that basis.
    N_before_floored = {f: max(1, round(v)) for f, v in N_before.items()}
    N_after_floored = {f: max(1, round(v)) for f, v in N_after.items()}

    checks = {
        "no_new_registrations": (reg_after - reg_before) == 0,
        "new_verdicts_match_reverdicted": (ver_after - ver_before) == len(reverdicted_ids),
        "per_family_registration_counts_unchanged": reg_ct_before == reg_ct_after,
        "per_family_trial_N_unchanged": N_before_floored == N_after_floored,
    }
    return {
        "new_register_events": reg_after - reg_before,
        "new_verdict_events": ver_after - ver_before,
        "n_reverdicted": len(reverdicted_ids),
        "reg_count_before": len([e for e in before_events if e.get("event") == "hyp_register"]),
        "reg_count_after": len([e for e in after_events if e.get("event") == "hyp_register"]),
        "family_N_before": dict(N_before_floored),
        "family_N_after": dict(N_after_floored),
        "checks": checks,
        "ok": all(checks.values()),
    }


# ── run-parameter recovery ───────────────────────────────────────────────────

def recover_run_params(hyp: dict[str, Any]) -> dict[str, Any]:
    """Recover the parameters evaluate_signal needs (direction, frequency,
    horizons, universe, start_date) from the hypothesis's LAST result JSON.
    Registration stores only signal_spec/primary_horizon, so the run params are
    read back from the most recent run recorded in verdict_json.result_file.
    FAIL-IS-FAIL: raise a clear error if the result JSON cannot be read."""
    vj = hyp.get("verdict_json") or {}
    result_file = vj.get("result_file")
    if not result_file:
        raise ValueError(f"{hyp['hypothesis_id']}: no verdict_json.result_file to recover params from")
    p = Path(result_file)
    if not p.exists():
        raise FileNotFoundError(
            f"{hyp['hypothesis_id']}: last result JSON not found at {result_file}. "
            "Is the production Data/loop symlinked into the worktree? (see doc header)")
    prev = json.loads(p.read_text())
    universe = prev.get("universe")
    if isinstance(universe, list):
        universe = ",".join(universe)
    elif universe in (None, "t2_34"):
        universe = "t2_34"
    return {
        "signal_spec": hyp.get("signal_spec") or prev.get("signal_spec"),
        "direction": prev.get("direction"),
        "frequency": prev.get("frequency", vj.get("frequency", "monthly")),
        "horizons": prev.get("horizons"),
        "universe": universe,
        "start_date": prev.get("start_date", "2008-01-01"),
        "old_verdict": prev.get("verdict") or vj.get("verdict"),
        "old_nw_t": vj.get("nw_t"),
        "old_dsr_basis": vj.get("deflated_sharpe"),
    }


# ── driver ────────────────────────────────────────────────────────────────────

def _preflight() -> None:
    if not MAIN_DB.exists():
        wt = Path(__file__).resolve().parent.parent.parent
        prod = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
        raise SystemExit(
            "reverdict_v4 preflight FAILED: warehouse not reachable at\n"
            f"  {MAIN_DB}\n"
            "The worktree does not carry the (gitignored) DBs. Symlink production first:\n"
            f'  ln -s "{prod / "Data" / "asado.duckdb"}" "{wt / "Data" / "asado.duckdb"}"\n'
            f'  ln -s "{prod / "Data" / "loop"}" "{wt / "Data" / "loop"}"\n'
            "Then re-run OUTSIDE the 06:00-08:30 PT nightly window.")


def run(out_root: Path = RUNS_DIR) -> int:
    _preflight()
    before_events = L._read_events(L.HYP_PATH)
    state = L.fold_hypotheses(before_events)
    ids = [e["hypothesis_id"] for e in before_events if e.get("event") == "hyp_register"]
    print(f"reverdict_v4: {len(ids)} registered hypotheses to re-verdict through the front door")

    canonical_families = sorted({L.canonical_family_of(state[i]) for i in ids})
    N_before = {f: L.family_trial_count(f) for f in canonical_families}

    rows: list[dict[str, Any]] = []
    reverdicted_ids: list[str] = []
    refused_ids: list[str] = []
    result_files: list[str] = []

    for i, hid in enumerate(ids, 1):
        hyp = state[hid]
        spec = hyp.get("signal_spec") or {}
        variable = spec.get("variable")
        family = hyp.get("family_key")
        row: dict[str, Any] = {"hypothesis_id": hid, "variable": variable, "family": family}
        # INV5: never attempt a blacklisted forward-return variable through the harness.
        if variable in FORWARD_RETURN_VARIABLES:
            vj = hyp.get("verdict_json") or {}
            row.update({"frequency": vj.get("frequency"), "old_verdict": vj.get("verdict"),
                        "new_verdict": "REFUSED_BLACKLIST", "old_nw_t": vj.get("nw_t"),
                        "new_nw_t": None, "old_dsr_basis": vj.get("deflated_sharpe"),
                        "new_dsr": None, "lag_days_effective": None, "status": "refused"})
            refused_ids.append(hid)
            rows.append(row)
            print(f"[{i}/{len(ids)}] {hid} {variable}: REFUSED_BLACKLIST (forward return)")
            continue
        try:
            params = recover_run_params(hyp)
            result = evaluate_signal(
                hypothesis_id=hid,
                signal_spec=params["signal_spec"],
                direction=params["direction"],
                frequency=params["frequency"],
                horizons=params["horizons"],
                universe=params["universe"] or "t2_34",
                start_date=params["start_date"],
            )
            conv = result.get("execution_convention") or {}
            row.update({
                "frequency": result.get("frequency"),
                "old_verdict": params["old_verdict"],
                "new_verdict": result.get("verdict"),
                "old_nw_t": params["old_nw_t"],
                "new_nw_t": (result.get("ic", {}).get(result.get("primary_label"), {}) or {}).get("nw_t"),
                "old_dsr_basis": params["old_dsr_basis"],
                "new_dsr": (result.get("deflated_sharpe_block", {}) or {}).get("deflated_sharpe"),
                "lag_days_effective": conv.get("lag_days_effective"),
                "status": "reverdicted",
            })
            reverdicted_ids.append(hid)
            result_files.append(result.get("result_file"))
            print(f"[{i}/{len(ids)}] {hid} {variable} ({row['frequency']}): "
                  f"{row['old_verdict']} -> {row['new_verdict']} lag_days={row['lag_days_effective']}")
        except Exception as exc:  # a bad id never aborts the sweep (recorded)
            row.update({"new_verdict": "ERROR", "error": f"{type(exc).__name__}: {exc}",
                        "status": "error"})
            rows.append(row)
            print(f"[{i}/{len(ids)}] {hid} {variable}: ERROR {exc}")
            continue
        rows.append(row)

    # ── INV4 integrity check (event-list report + canonical-family cross-check) ──
    after_events = L._read_events(L.HYP_PATH)
    report = ledger_integrity_report(before_events, after_events, reverdicted_ids)
    N_after = {f: L.family_trial_count(f) for f in canonical_families}
    canonical_N_unchanged = N_before == N_after
    report["canonical_family_N_before"] = N_before
    report["canonical_family_N_after"] = N_after
    report["checks"]["canonical_family_N_unchanged"] = canonical_N_unchanged
    report["ok"] = report["ok"] and canonical_N_unchanged

    # ── artifacts ────────────────────────────────────────────────────────────
    out_dir = out_root / f"reverdict_v4_{date.today().isoformat()}"
    out_dir.mkdir(parents=True, exist_ok=True)
    import pandas as pd
    cols = ["hypothesis_id", "variable", "family", "frequency", "old_verdict",
            "new_verdict", "old_nw_t", "new_nw_t", "old_dsr_basis", "new_dsr",
            "lag_days_effective", "status"]
    df = pd.DataFrame(rows)
    for c in cols:
        if c not in df.columns:
            df[c] = None
    df = df[cols + [c for c in df.columns if c not in cols]]
    df.to_parquet(out_dir / "summary.parquet", index=False)
    df.to_excel(out_dir / "summary.xlsx", index=False)
    manifest = {
        "run_date": date.today().isoformat(),
        "n_registered": len(ids),
        "reverdicted_ids": reverdicted_ids,
        "refused_ids": refused_ids,
        "error_ids": [r["hypothesis_id"] for r in rows if r.get("status") == "error"],
        "result_files": result_files,
        "integrity": report,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))

    print("\n" + "=" * 78)
    print(f"reverdict_v4 complete: {len(reverdicted_ids)} reverdicted, "
          f"{len(refused_ids)} refused (blacklist), {len(manifest['error_ids'])} errors")
    print(f"INV4 integrity: {'PASS' if report['ok'] else 'FAIL'}  -> {report['checks']}")
    print(f"summary: {out_dir / 'summary.xlsx'}")
    if not report["ok"]:
        print("INV4 FAIL-IS-FAIL: ledger integrity violated", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="v4 honest re-verdict sweep (contract gate G3).")
    ap.add_argument("--out-root", default=str(RUNS_DIR),
                    help="parent dir for the reverdict_v4_<date> output directory")
    args = ap.parse_args()
    return run(Path(args.out_root))


if __name__ == "__main__":
    sys.exit(main())
