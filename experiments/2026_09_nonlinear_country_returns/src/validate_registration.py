# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/src/validate_registration.py
#
# PRD 10 — the `validate-registration` command. Rejects (exit 1, named
# reason) on: unresolved required bindings, hash mismatches, forbidden
# feature lineage, changed thresholds, unapproved model family, or code
# drift past the locked commit.
#
#   python src/validate_registration.py
# =============================================================================
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
GOV = EXP / "governance"
AUDIT = EXP / "audit"
REPO = EXP.parents[1]

FORBIDDEN_LINEAGE = ["1DRet", "5DRet", "20DRet", "60DRet", "120DRet",
                     "1MRet", "3MRet", "6MRet", "9MRet", "12MRet",
                     "NMRet", "NDRet", "ff_factors", "jst_macrohistory",
                     "factor_returns", "factor_top20_membership",
                     "country_factor_attribution"]

EXPECTED_THRESHOLDS = {
    "leaf_support": {"min_origins": 126, "min_20origin_bins": 12,
                     "min_years": 3, "min_markets": 4},
    "bootstrap": {"block_origins": 63, "draws": 1000},
    "models": ["B0", "L_X", "L_S", "L_star", "A_S", "Q_S", "N_S", "N_X"],
}


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fail(msg: str) -> None:
    print(f"VALIDATE-REGISTRATION: REJECT — {msg}")
    sys.exit(1)


def main() -> None:
    lock_p = GOV / "protocol.lock.json"
    rec_p = GOV / "registration_receipt.json"
    cfg_p = EXP / "config" / "study.v2.json"
    for p in (lock_p, rec_p, cfg_p, GOV / "trial_manifest.json",
              GOV / "run_plan.json", GOV / "exposure_log.jsonl"):
        if not p.exists():
            fail(f"missing required artifact {p.relative_to(EXP)}")

    lock = json.loads(lock_p.read_text())
    rec = json.loads(rec_p.read_text())
    cfg = json.loads(cfg_p.read_text())

    # 1. No unresolved required bindings in the study config.
    for k, v in cfg["bindings"].items():
        if v is None or v is False:
            fail(f"unresolved binding: {k}")

    # 2. Hash agreement: lock -> files, receipt -> lock/config/manifests.
    fh = lock["file_hashes"]
    for name, rel in (("environment_lock", "governance/environment.lock"),
                      ("feature_manifest_bound",
                       "governance/feature_manifest.bound.yaml"),
                      ("calendar_manifest", "audit/calendar_manifest.json"),
                      ("market_map", "audit/market_map.csv"),
                      ("splits", "audit/splits.json")):
        if sha256_file(EXP / rel) != fh[name]:
            fail(f"hash mismatch: {rel}")
    if sha256_file(lock_p) != rec["protocol_lock_sha256"]:
        fail("protocol.lock.json changed after registration")
    if sha256_file(GOV / "trial_manifest.json") != rec["trial_manifest_sha256"]:
        fail("trial_manifest.json changed after registration")
    if sha256_file(GOV / "run_plan.json") != rec["run_plan_sha256"]:
        fail("run_plan.json changed after registration")
    if sha256_file(GOV / "exposure_log.jsonl") != rec["exposure_log_sha256"]:
        fail("exposure_log.jsonl changed after registration")
    # Config hash at registration covers the pre-receipt version: recompute
    # with the self-referential fields reset.
    cfg_canon = json.loads(cfg_p.read_text())
    cfg_canon["bindings"]["registration_receipt"] = None
    cfg_canon["bindings"]["approval_evidence"] = None
    cfg_canon["status"] = "AMENDED_DRAFT_PRE_REGISTRATION"
    cfg_canon["execution_permissions"]["allow_real_outer_evaluation"] = False
    canon_hash = hashlib.sha256(
        json.dumps(cfg_canon, indent=1).encode()).hexdigest()
    if canon_hash != rec["study_config_sha256"]:
        fail("study.v2.json changed outside the permitted post-registration "
             "fields (registration_receipt/approval_evidence/status/"
             "allow_real_outer_evaluation)")

    # 3. Forbidden lineage must not appear in the bound feature manifest.
    bound = (GOV / "feature_manifest.bound.yaml").read_text()
    for bad in FORBIDDEN_LINEAGE:
        if bad in bound:
            fail(f"forbidden lineage in feature manifest: {bad}")

    # 4. Thresholds unchanged from the registered contract.
    if lock["leaf_support"] != EXPECTED_THRESHOLDS["leaf_support"]:
        fail("leaf-support thresholds changed")
    sel = lock["selection"]
    if (sel["bootstrap_block_origins"] != 63 or
            sel["bootstrap_draws"] != 1000):
        fail("bootstrap parameters changed")
    if lock["grids"]["models"] != EXPECTED_THRESHOLDS["models"]:
        fail("model family list changed")
    if lock["grids"]["n_tuned_configs"] != 72:
        fail("tuned-config count changed")

    # 5. Code integrity: no drift in src/ tests/ spec/ config semantics.
    diff = subprocess.run(
        ["git", "diff", "--name-only", lock["code_commit"], "HEAD",
         "--", "experiments/2026_09_nonlinear_country_returns/src",
         "experiments/2026_09_nonlinear_country_returns/tests",
         "experiments/2026_09_nonlinear_country_returns/spec"],
        cwd=REPO, capture_output=True, text=True)
    # p06_freeze/register/validator are P06 governance code added at the
    # lock commit boundary — allow exactly those names beyond code_commit.
    allowed_new = {"src/p06_freeze.py", "src/register_p06.py",
                   "src/validate_registration.py"}
    changed = [l.split("experiments/2026_09_nonlinear_country_returns/")[-1]
               for l in diff.stdout.split() if l.strip()]
    bad = [c for c in changed if c not in allowed_new]
    if bad:
        fail(f"code drift past locked commit: {bad}")

    # 6. Phase gates all PASS.
    for ph in ("P02", "P03", "P04", "P05"):
        g = json.loads((AUDIT / f"{ph}_gate.json").read_text())
        if g.get("status") != "PASS":
            fail(f"{ph} gate status != PASS")

    print("VALIDATE-REGISTRATION: PASS — all bindings resolved, hashes "
          "match, thresholds unchanged, no forbidden lineage, code "
          f"integrity holds at {lock['code_commit'][:7]}")


if __name__ == "__main__":
    main()
