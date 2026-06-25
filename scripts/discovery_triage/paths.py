from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
JOURNAL_DIR = BASE_DIR / "journal"
LOOKS_DIR = JOURNAL_DIR / "looks"
DRAFTS_DIR = JOURNAL_DIR / "drafts"
CLAIMS_DIR = JOURNAL_DIR / "claims"
SEALED_DIR = JOURNAL_DIR / "sealed_rationales"
BLIND_RULINGS_DIR = JOURNAL_DIR / "blind_rulings"
PROSPECTIVE_DIR = JOURNAL_DIR / "prospective_queue"
DOCKETS_DIR = JOURNAL_DIR / "dockets"
ANALOG_DIR = JOURNAL_DIR / "analog_sets"
GRAVEYARD_DIR = JOURNAL_DIR / "graveyard"

DISCOVERY_CONFIG = CONFIG_DIR / "discovery_triage.yaml"
PROVENANCE_POLICY = CONFIG_DIR / "claim_provenance_policy.yaml"
ANALOG_REGISTRY = CONFIG_DIR / "analog_metric_registry.yaml"
TRIAGE_PROBE_REGISTRY = CONFIG_DIR / "triage_probe_registry.yaml"
MODEL_REGISTRY = CONFIG_DIR / "model_registry.yaml"

# Append-only JSONL ledgers (FuguPRD §20.2)
RESEARCH_LOOKS = LOOKS_DIR / "research_looks.jsonl"
DETECTOR_DRAFTS = DRAFTS_DIR / "detector_drafts.jsonl"
CLAIMS_JSONL = CLAIMS_DIR / "claims.jsonl"
BLIND_RULINGS = BLIND_RULINGS_DIR / "blind_rulings.jsonl"
PROSPECTIVE_QUEUE = PROSPECTIVE_DIR / "prospective_queue.jsonl"
GRAVEYARD_TRACKING = GRAVEYARD_DIR / "graveyard_forward_tracking.jsonl"
ANALOG_SETS_INDEX = ANALOG_DIR / "analog_sets.jsonl"


def ensure_dirs() -> None:
    for d in [LOOKS_DIR, DRAFTS_DIR, CLAIMS_DIR, SEALED_DIR, BLIND_RULINGS_DIR,
              PROSPECTIVE_DIR, DOCKETS_DIR, ANALOG_DIR, GRAVEYARD_DIR]:
        d.mkdir(parents=True, exist_ok=True)
