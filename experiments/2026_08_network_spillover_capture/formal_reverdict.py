#!/usr/bin/env python3
"""Re-measure only the pre-registered network_spillover family.

This is deliberately a thin front-door wrapper: it recovers each hypothesis'
already-registered run parameters from the local harness result, then calls
evaluate_signal with the existing hypothesis ID.  It never registers a new
trial and never uses --force.
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.harness.evaluate_signal import evaluate_signal  # noqa: E402
from scripts.loop.ledgers import canonical_family_of, fold_hypotheses  # noqa: E402


RUNS = ROOT / "Data/loop/harness_runs"
OUT = ROOT / "experiments/2026_08_network_spillover_capture/results"


def latest_local_result(hypothesis_id: str) -> tuple[Path, dict]:
    paths = sorted(RUNS.glob(f"{hypothesis_id}_*.json"))
    if not paths:
        raise FileNotFoundError(f"no local harness result for {hypothesis_id}")
    path = paths[-1]
    return path, json.loads(path.read_text())


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    hypotheses = {
        hid: hyp
        for hid, hyp in fold_hypotheses().items()
        if canonical_family_of(hyp) == "network_spillover"
    }
    if not hypotheses:
        raise RuntimeError("no registered network_spillover hypotheses found")

    rows = []
    for i, hid in enumerate(sorted(hypotheses), 1):
        local_path, prior = latest_local_result(hid)
        universe = prior.get("universe", "t2_34")
        if isinstance(universe, list):
            universe = ",".join(universe)
        print(f"[{i}/{len(hypotheses)}] {hid} prior={prior.get('verdict')} source={local_path.name}", flush=True)
        result = evaluate_signal(
            hypothesis_id=hid,
            signal_spec=prior["signal_spec"],
            direction=prior["direction"],
            frequency=prior["frequency"],
            horizons=prior["horizons"],
            universe=universe,
            start_date=prior["start_date"],
        )
        row = {
            "hypothesis_id": hid,
            "prior_verdict": prior.get("verdict"),
            "new_verdict": result["verdict"],
            "primary_label": result["primary_label"],
            "mean_ic": result["ic"][result["primary_label"]]["mean_ic"],
            "nw_t": result["ic"][result["primary_label"]]["nw_t"],
            "coverage_n_dates": result["coverage"]["n_dates"],
            "coverage_pct_dates_above_gate": result["coverage"]["pct_dates_above_gate"],
            "gross_ls_sharpe": result.get("portfolio", {}).get("gross", {}).get("ls_sharpe"),
            "gross_top_excess": result.get("portfolio", {}).get("gross", {}).get("excess_ann_return"),
            "result_file": result["result_file"],
        }
        rows.append(row)
        (OUT / "formal_reverdict_rows.json").write_text(json.dumps(rows, indent=2) + "\n")

    counts = {}
    for row in rows:
        counts[row["new_verdict"]] = counts.get(row["new_verdict"], 0) + 1
    summary = {
        "family": "network_spillover",
        "n_hypotheses": len(rows),
        "prior_verdict_counts": _counts(rows, "prior_verdict"),
        "new_verdict_counts": counts,
        "method": "existing hypothesis IDs through evaluate_signal; no registration and no --force",
        "harness_version_expected": 4,
        "effective_daily_lag_expected": 1,
        "rows": rows,
    }
    (OUT / "formal_reverdict_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "rows"}, indent=2))


def _counts(rows: list[dict], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        value = row[key]
        out[value] = out.get(value, 0) + 1
    return out


if __name__ == "__main__":
    main()
