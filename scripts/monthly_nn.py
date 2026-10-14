#!/usr/bin/env python3
"""Independent NN sandbox validation and staged publication packaging.

Inputs: ASADO/Data/monthly/runs/<run>/STAGED.json, frozen prior NN state, existing
T2 NN production model cache. Output: two isolated scoring sandboxes, parity and
workbook checks, staged canonical NN artifacts and hashed publication_plan.json.
No training, providers, orders or canonical writes. Runs existing-model-only NN
commands under T2 NN/rank_model/.venv; packaging reuses the native output writer.
"""
import argparse
import copy
from datetime import datetime
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import numpy as np
import pandas as pd
from monthly_readiness import read, sha, atomic, PACIFIC
from monthly_stage import definitions


def same_scores(a, b):
    keys = ["date", "country", "ticker", "rank", "held_prev", "weight", "action"]
    a = a.sort_values("country").reset_index(drop=True)
    b = b.sort_values("country").reset_index(drop=True)
    pd.testing.assert_frame_equal(a[keys], b[keys], check_dtype=False)
    if not np.allclose(a.score, b.score, rtol=1e-10, atol=1e-10):
        raise RuntimeError("Independent NN scoring parity failed")
    if len(a) != 34 or a.country.nunique() != 34 or len(a[a.weight > 0]) != 8 or not np.isclose(a.weight.sum(), 1) or not np.isfinite(a.score).all():
        raise RuntimeError("NN score/holdings sanity check failed")
    return a


def build(c):
    root, nn, run = Path(c["root"]), Path(c["nn_root"]), Path(c["run"])
    cfg = c["config"]
    proof = read(run / "STAGED.json")
    snapshot = Path(proof["snapshot"])
    if sha(snapshot) != proof["snapshot_sha256"]:
        raise RuntimeError("Staged snapshot changed")
    originals = read(c["originals"])
    state_original = originals[str(nn / "production/state/holdings.json")]
    for label in ("a", "b"):
        box = run / ("nn_" + label)
        cache = box / "models" / Path(c["model_dir"]).name
        cache.mkdir(parents=True)
        for name, digest in c["model_hashes"].items():
            src = Path(c["model_dir"]) / name
            if sha(src) != digest:
                raise RuntimeError("Canonical model changed before scoring")
            shutil.copy2(src, cache / name)
        (box / "state").mkdir()
        shutil.copy2(state_original["backup"], box / "state/holdings.json")
        log = run / ("nn_" + label + ".log")
        with log.open("w") as output:
            subprocess.run([cfg["nn_python"], cfg["nn_script"], "--month", c["month"], "--snapshot", str(snapshot),
                            "--sandbox", str(box), "--existing-models-only", "--no-notify", "--workers", "4"],
                           stdout=output, stderr=subprocess.STDOUT, check=True)
    a = pd.read_parquet(run / "nn_a/output/nn_contract_latest.parquet")
    b = pd.read_parquet(run / "nn_b/output/nn_contract_latest.parquet")
    table = same_scores(a, b).sort_values("rank").reset_index(drop=True)
    meta_a = read(run / "nn_a/output/nn_contract_latest.json")
    meta_b = read(run / "nn_b/output/nn_contract_latest.json")
    for key in ("trade_month", "snapshot_sha256", "factor_set_sha256", "basket", "previous_basket", "rule"):
        if meta_a[key] != meta_b[key]:
            raise RuntimeError("Independent NN manifest parity failed: " + key)
    state = read(run / "nn_a/state/holdings.json")
    manifest = copy.deepcopy(meta_a)
    manifest.update(snapshot=c["snapshot_destination"], run_dir=c["nn_run_destination"],
                    generated=datetime.now(PACIFIC).isoformat(timespec="seconds"))
    manifest["model"]["fold_dir"] = c["model_dir"]
    detailed = proof["freshness"]
    # Preserve model calculations, expose all additional input warnings in the
    # publication metadata/workbook. This does not change imputation or scores.
    manifest["freshness"] = dict(passed=True, warnings=detailed["warnings"], full_coverage=detailed["full_coverage"])
    current = state["months"][c["month"]]
    current.update(snapshot=c["snapshot_destination"], run_dir=c["nn_run_destination"])
    outroot = run / "stage/NN"
    ns = definitions(cfg["nn_script"], {"write_outputs", "atomic_write", "atomic_json", "sha256"},
                     dict(pd=pd, np=np, Path=Path, os=__import__('os'), tempfile=__import__('tempfile'), json=__import__('json'), hashlib=__import__('hashlib'), T2_ORDER=c["config"]["countries"]))
    # Native output writer uses the canonical NN order, not the sorted ASADO list.
    # Constants were extracted by definitions; COUNTRY_TICKERS is authoritative.
    ns["T2_ORDER"] = [country for country, _ in ns["COUNTRY_TICKERS"]]
    paths = dict(output=outroot / "production/output", state=outroot / "production/state/holdings.json")
    ns["write_outputs"](paths, pd.Timestamp(c["month"]+"-01"), table, manifest, state, detailed)
    atomic(paths["state"], state)
    same_scores(pd.read_parquet(paths["output"] / "nn_contract_latest.parquet"), b)
    xlsx = paths["output"] / "T2_NN_Country_Weights.xlsx"
    sheets = pd.read_excel(xlsx, sheet_name=None)
    if set(sheets) != {"Latest Weights", "Scores", "All Periods", "Run Info"} or len(sheets["Scores"]) != 34 or len(sheets["Latest Weights"]) != 8 or not np.isclose(sheets["Latest Weights"].weight.sum(),1):
        raise RuntimeError("Canonical-format workbook verification failed")
    # Snapshot and receipts are also staged; canonical paths do not exist yet.
    snapdir = outroot / "snapshot"
    snapdir.mkdir()
    shutil.copy2(snapshot, snapdir / "feature_panel_observed.parquet")
    atomic(snapdir / "MANIFEST.json", dict(trade_month=c["month"], source_db=str(root / "Data/asado.duckdb"),
                                         snapshot_sha256=sha(snapshot), validation=str(run / "STAGED.json")))
    archive = outroot / "run"
    archive.mkdir()
    receipt = dict(accepted_at=datetime.now(PACIFIC).isoformat(), NN_month=c["month"], NN_scores_match_sandbox=True,
                   NN_manifest=manifest, freshness=detailed, source_receipts=str(run / "collection_receipts.json"),
                   preservation=str(run / "STAGED.json"), publication_journal=str(run / "publication.jsonl"))
    atomic(archive / "monthly_acceptance.json", receipt)
    atomic(archive / "summary.json", manifest)
    atomic(archive / "freshness_report.json", detailed)
    shutil.copy2(run / "nn_a.log", archive / "run.log")
    plan = []
    for destination, original in originals.items():
        dest = Path(destination)
        if dest.is_relative_to(root):
            src = run / "stage/ASADO" / dest.relative_to(root)
        elif dest.is_relative_to(nn / "production"):
            src = outroot / "production" / dest.relative_to(nn / "production")
        else:
            src = None
        if dest.parent == Path(c["snapshot_destination"]).parent:
            src = snapdir / dest.name
        if dest.parent == Path(c["nn_run_destination"]):
            src = archive / dest.name
        if src and src.exists() and sha(src) != original["before_sha256"]:
            plan.append(dict(source=str(src), destination=str(dest), sha256=sha(src)))
    needed = {str(nn / f"production/output/contracts/nn_contract_{c['month']}.json"), str(nn / "production/state/holdings.json"), c["snapshot_destination"], str(Path(c["nn_run_destination"])/"monthly_acceptance.json")}
    if not needed <= {p["destination"] for p in plan}:
        raise RuntimeError("Publication plan lacks required warehouse/NN/snapshot/receipt targets")
    atomic(run / "NN_VALIDATED.json", dict(independent_parity=True, warehouse_sha256=sha(run/'stage/ASADO/Data/asado.duckdb'), model_hashes=c["model_hashes"], scores=34, holdings=8, full_coverage=detailed["full_coverage"], warnings=detailed["warnings"], workbook_sheets=list(sheets)))
    atomic(run / "publication_plan.json", plan)


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--context',type=Path,required=True);args=ap.parse_args();build(read(args.context))


if __name__=='__main__':main()
