# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/src/p07_controls.py
#
# PRD 11.2 — linear-world and positive-control studies. For each q in the
# locked grid, >=100 fixed replications: generate pseudo-labels from the
# P06-frozen generator, run the FULL nested selection/replay procedure, and
# record the primary declarations + interaction-detection outcomes.
#
# Rep-level multiprocessing (each rep is an independent replay). Outputs go
# to Data/work scratch (main checkout path — the worktree has no Data/);
# per-rep forecasts are kept for auditability.
#
#   python p07_controls.py [--q 0.005] [--reps 100] [--workers 12]
# =============================================================================
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import time
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

EXP = Path(__file__).resolve().parents[1]
SCRATCH = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/"
               "Data/work/experiments/nonlinear_country_returns/p07_controls")


def one_rep(task):
    q, rep = task
    from pseudolabels import generate
    from runner import ReplayRunner, STREAMS
    from metrics import collect_forecasts, origin_metric_table, primary_tests
    tag = f"q{q:g}_r{rep}"
    run_dir = SCRATCH / f"q{q:g}" / f"rep_{rep:03d}"
    run_dir.mkdir(parents=True, exist_ok=True)
    lab_p = run_dir / "pseudo_labels.parquet"
    if not lab_p.exists():
        generate(q, rep, lab_p)
    try:
        r = ReplayRunner(run_dir, labels_path=lab_p, tag=tag, quiet=True)
        r.run()

        # scored axis under the pseudo-labels = same maturity masks as real
        from metrics import load_scored
        scored = load_scored()  # real maturity metadata
        lab = pd.read_parquet(lab_p)
        lab["origin_date"] = pd.to_datetime(lab["origin_date"])
        scored = scored.drop(columns=["label"]).merge(
            lab[["origin_date", "market", "label"]],
            on=["origin_date", "market"], how="left")
        fc = collect_forecasts(run_dir, STREAMS)
        tab = origin_metric_table(scored, fc, STREAMS)
        tests = primary_tests(tab)

        def _nm(a):
            v = np.asarray(a, dtype=float)
            return float(np.nanmean(v)) if np.isfinite(v).any() else None

        dec = {
            "q": q, "rep": rep, "status": "ok",
            "mse_gain_LX": tests[0]["rel_gain"], "p_LX": tests[0]["p_holm"],
            "mse_gain_LS": tests[1]["rel_gain"], "p_LS": tests[1]["p_holm"],
            "ic_gain_Lstar": tests[2]["point"], "p_Lstar": tests[2]["p_holm"],
            "ns_vs_as_ic": _nm(tab["N_S_ic"] - tab["A_S_ic"]),
            "qs_vs_ls_mse": _nm(tab["L_S_mse"] - tab["Q_S_mse"]),
            "ns_mean_ic": _nm(tab["N_S_ic"]),
            "blocked_fits": _count_blocked(run_dir),
        }
        # null metrics = unavailable stream = cannot be declared
        ge = lambda x, t: x is not None and x >= t   # noqa: E731
        lt = lambda x, t: x is not None and x < t    # noqa: E731
        dec["primary_declared"] = bool(
            ge(tests[0]["rel_gain"], 0.001) and lt(tests[0]["p_holm"], 0.05) and
            ge(tests[1]["rel_gain"], 0.001) and lt(tests[1]["p_holm"], 0.05) and
            ge(tests[2]["point"], 0.01) and lt(tests[2]["p_holm"], 0.05))
    except Exception as e:  # a crashed rep is a recorded failure, not silent
        return {"q": q, "rep": rep, "status": "CRASHED", "error": str(e)}
    (run_dir / "control_result.json").write_text(json.dumps(dec, indent=1))
    return dec


def _count_blocked(run_dir: Path) -> int:
    n = 0
    for p in run_dir.glob("fit_*.json"):
        rec = json.loads(p.read_text())
        for m, v in rec.get("selected", {}).items():
            if isinstance(v, dict) and v.get("status") == "BLOCKED_FIT_SUPPORT":
                n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", type=float, default=None,
                    help="single q value (default: full locked grid)")
    ap.add_argument("--reps", type=int, default=100)
    ap.add_argument("--workers", type=int, default=12)
    args = ap.parse_args()

    lock = json.loads(
        (EXP / "governance" / "protocol.lock.json").read_text())
    q_grid = ([args.q] if args.q is not None
              else lock["synthetic_generators"]["q_grid"])
    tasks = [(q, r) for q in q_grid for r in range(args.reps)]
    # skip reps already on disk (restartable)
    done = set()
    for q in q_grid:
        d = SCRATCH / f"q{q:g}"
        if d.exists():
            for p in d.glob("rep_*/control_result.json"):
                done.add((q, int(p.parent.name.split("_")[1])))
    tasks = [t for t in tasks if t not in done]
    print(f"control tasks: {len(tasks)} remaining of "
          f"{len(q_grid) * args.reps}")

    t0 = time.time()
    results = []
    with mp.Pool(args.workers) as pool:
        for i, res in enumerate(pool.imap_unordered(one_rep, tasks)):
            results.append(res)
            if (i + 1) % 10 == 0:
                el = time.time() - t0
                eta = el / (i + 1) * (len(tasks) - i - 1)
                print(f"{i+1}/{len(tasks)} done ({el/60:.0f}m elapsed, "
                      f"~{eta/60:.0f}m left)", flush=True)
    out_p = SCRATCH / "control_summary.json"
    prev = []
    if out_p.exists():
        prev = json.loads(out_p.read_text())
    out_p.write_text(json.dumps(prev + results, indent=1))
    print(f"wrote {out_p} ({len(prev) + len(results)} total reps)")


if __name__ == "__main__":
    main()
