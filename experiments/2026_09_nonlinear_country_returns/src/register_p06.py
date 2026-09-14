# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/src/register_p06.py
#
# PRD 10.3 — execution authorization: record the locked protocol in the
# repository's authorized registration mechanism (methodology ledger via
# scripts/loop/ledgers.py), then write governance/registration_receipt.json
# and flip the study config's registration bindings.
#
# This is the ONLY ledger write this experiment performs, and it goes through
# the ledgers.py API (governance_binding.json registration route). The
# hypothesis_text below was written before any real outer evaluation — no
# genuine outer IC/Sharpe/ranking exists yet.
# =============================================================================
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

EXP = Path(__file__).resolve().parents[1]
GOV = EXP / "governance"
REPO = EXP.parents[1]
sys.path.insert(0, str(REPO / "scripts" / "loop"))

import ledgers  # noqa: E402


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


HYPOTHESIS = (
    "A pre-specified pooled nonlinear model — depth-2 histogram boosting "
    "(max 4 leaves) on a fixed 15-input economic representation S — will "
    "predict 20-local-session forward USD country equity returns better "
    "than independently tuned ridge models on the same 21 raw primitives "
    "(L_X), the same S inputs (L_S), and their annual inner-selected "
    "combination (L_star), on an identical point-in-time-safe eligible "
    "sample. The claim is about pooled nonlinear STRUCTURE, not any single "
    "primitive; the graveyard already holds the individual primitives DEAD "
    "as standalone signals, which is expected and not a conflict. PRIOR "
    "EXPOSURE DECLARED: MacroState M_20260906_001-003 (same idea family, "
    "different monthly/12M contract, no nested PIT inference; its nonlinear "
    "stage was designed after earlier results were seen), the LLM-1M "
    "tabular HGB arm, and the T2 IPCA pooled-model experiment. This study "
    "is not fresh confirmation of any of them. Amendment AM-1 (dropped "
    "P07/P08 bank-neighbor primitives and the nonexistent P11 3M risk "
    "reversal; 21 primitives, 15-input S, 22-market universe) was approved "
    "before any result exposure. A valid negative result is a successful "
    "delivery."
)

GATE_LADDER = [
    {"gate": 1,
     "description": "Pre-execution integrity: P01-P05 phase gates PASS and "
                    "all registered hashes verify against on-disk artifacts "
                    "(validate-registration must pass)"},
    {"gate": 2,
     "description": "Inference calibration: empirical familywise rejection "
                    "rate of the 63-origin block-bootstrap/Holm engine on "
                    "100 fixed null replications has 95% Wilson lower bound "
                    "<= 5% nominal (else INVALID_INFERENCE_CALIBRATION)"},
    {"gate": 3,
     "description": "Positive control: the full nested selection procedure "
                    "detects the planted C04*C06 interaction at moderate "
                    "variance share (q>=0.005) at a non-trivial rate across "
                    ">=100 fixed replications"},
    {"gate": 4,
     "description": "Primary MSE: N_S outer origin-weighted MSE gain vs "
                    "BOTH L_X and L_S >= 0.1% relative, Holm-adjusted "
                    "significance over the primary family"},
    {"gate": 5,
     "description": "Primary IC: N_S outer IC gain vs L_star >= 0.01, "
                    "Holm-adjusted significance over the primary family"},
]


def main() -> None:
    lock_path = GOV / "protocol.lock.json"
    lock = json.loads(lock_path.read_text())

    cfg_path = EXP / "config" / "study.v2.json"
    cfg = json.loads(cfg_path.read_text())

    experiment_id = ledgers.register_methodology_experiment(
        experiment_name="nonlinear_country_returns_2026_09",
        experiment_dir=str(EXP),
        hypothesis_text=HYPOTHESIS,
        gate_ladder=GATE_LADDER,
        prd_path=str(EXP / "spec" / "PRD.md"),
        author="devin-agent",
    )
    print("registered:", experiment_id)

    lock["status"] = "LOCKED_REGISTERED"
    lock["registration_experiment_id"] = experiment_id
    lock_path.write_text(json.dumps(lock, indent=1))
    print("protocol.lock.json -> LOCKED_REGISTERED")

    receipt = {
        "phase": "P06",
        "experiment_id": experiment_id,
        "ledger": "ledgers/methodology_ledger.jsonl",
        "registration_api": "scripts/loop/ledgers.py::register_methodology_experiment",
        "protocol_lock_sha256": sha256_file(lock_path),
        "study_config_sha256": sha256_file(cfg_path),
        "trial_manifest_sha256": sha256_file(GOV / "trial_manifest.json"),
        "run_plan_sha256": sha256_file(GOV / "run_plan.json"),
        "exposure_log_sha256": sha256_file(GOV / "exposure_log.jsonl"),
        "code_commit": lock["code_commit"],
        "approval_evidence": (
            "Owner directives in-session 2026-09-13: 'loosen the blockers "
            "and make it run' + 'Drop P11' (AM-1 authorization); this "
            "methodology-ledger registration is the repository's authorized "
            "approval record per PRD 10.3 — no independent-review approval "
            "is invented."),
        "hypothesis_text": HYPOTHESIS,
        "gate_ladder": GATE_LADDER,
        "real_outer_evaluation_permitted_after": experiment_id,
    }
    (GOV / "registration_receipt.json").write_text(
        json.dumps(receipt, indent=1))
    print("wrote governance/registration_receipt.json")

    # Flip the config's registration bindings + status.
    cfg["bindings"]["registration_receipt"] = (
        "governance/registration_receipt.json")
    cfg["bindings"]["approval_evidence"] = receipt["approval_evidence"]
    cfg["status"] = "LOCKED_REGISTERED"
    cfg["execution_permissions"]["allow_real_outer_evaluation"] = True
    cfg_path.write_text(json.dumps(cfg, indent=1))
    print("study.v2.json -> LOCKED_REGISTERED")


if __name__ == "__main__":
    main()
