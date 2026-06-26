from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_DIR = BASE_DIR / "config"
JOURNAL_DIR = BASE_DIR / "journal"


def data_root() -> Path:
    """Canonical runtime data root (merge PRD FR9). Default <repo>/Data; override with
    ASADO_DATA_ROOT (e.g. the main checkout's Data when running from a worktree)."""
    return Path(os.environ.get("ASADO_DATA_ROOT", str(BASE_DIR / "Data"))).expanduser()


def loop_db_path() -> Path:
    """$ASADO_DATA_ROOT/loop/asado_loop.duckdb (resolved at call time)."""
    return data_root() / "loop" / "asado_loop.duckdb"
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
MODEL_REGISTRY_PATH = MODEL_REGISTRY  # alias consumed by model_registry.py (Codex naming)

# Append-only JSONL ledgers (FuguPRD §20.2)
RESEARCH_LOOKS = LOOKS_DIR / "research_looks.jsonl"
DETECTOR_DRAFTS = DRAFTS_DIR / "detector_drafts.jsonl"
CLAIMS_JSONL = CLAIMS_DIR / "claims.jsonl"
BLIND_RULINGS = BLIND_RULINGS_DIR / "blind_rulings.jsonl"
PROSPECTIVE_QUEUE = PROSPECTIVE_DIR / "prospective_queue.jsonl"
GRAVEYARD_TRACKING = GRAVEYARD_DIR / "graveyard_forward_tracking.jsonl"
ANALOG_SETS_INDEX = ANALOG_DIR / "analog_sets.jsonl"

# Aliases consumed by cos_mockups/build_cockpit_data.py (Codex-aligned naming).
DETECTOR_DRAFTS_PATH = DETECTOR_DRAFTS
CLAIMS_PATH = CLAIMS_JSONL
BLIND_RULINGS_PATH = BLIND_RULINGS
PROSPECTIVE_QUEUE_PATH = PROSPECTIVE_QUEUE
GRAVEYARD_TRACKING_PATH = GRAVEYARD_TRACKING
ANALOG_SETS_PATH = ANALOG_SETS_INDEX


def ensure_dirs() -> None:
    for d in [LOOKS_DIR, DRAFTS_DIR, CLAIMS_DIR, SEALED_DIR, BLIND_RULINGS_DIR,
              PROSPECTIVE_DIR, DOCKETS_DIR, ANALOG_DIR, GRAVEYARD_DIR]:
        d.mkdir(parents=True, exist_ok=True)
