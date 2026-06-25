from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

VisibilityMode = Literal["outcome_blind", "frozen_window", "full_retrospective", "legacy_unknown", "human_pretest", "pit_preregistered", "deterministic_detector"]
GeneratorType = Literal["llm", "human", "deterministic", "harness"]

# Canonical internal visibility modes (the only values the routing/enforcement
# logic checks against).
CANONICAL_VISIBILITY_MODES = {
    "outcome_blind", "frozen_window", "full_retrospective", "legacy_unknown",
    "human_pretest", "pit_preregistered", "deterministic_detector",
}
# PRD / user-facing aliases (after lowercasing and mapping '-'/' ' -> '_').
_VISIBILITY_ALIASES = {"tool_outcome_blind": "outcome_blind"}


def normalize_visibility_mode(mode: str | None) -> str:
    """Map any accepted spelling to a canonical visibility mode.

    Closes the bypass the Sakana/Fugu review flagged: the PRD writes
    `tool_outcome_blind` but the code enforces on `outcome_blind`, so an
    un-normalized alias would skip outcome-blind enforcement entirely. Aliases
    (`tool_outcome_blind`, `tool-outcome-blind`) normalize to `outcome_blind`.
    FAIL-SAFE: an unrecognized mode raises rather than silently passing through
    to the fail-open `mode in {...}` checks downstream.
    """
    if mode is None or str(mode).strip() == "":
        raise ValueError("visibility_mode is required")
    key = str(mode).strip().lower().replace("-", "_").replace(" ", "_")
    if key in CANONICAL_VISIBILITY_MODES:
        return key
    if key in _VISIBILITY_ALIASES:
        return _VISIBILITY_ALIASES[key]
    raise ValueError(
        f"unknown visibility_mode {mode!r}; expected one of "
        f"{sorted(CANONICAL_VISIBILITY_MODES)} or a known alias"
    )


def parse_date(value: str | date | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


@dataclass(frozen=True)
class ProvenanceInput:
    generator_type: GeneratorType
    visibility_mode: str  # any accepted spelling; normalized in classify_provenance
    model_training_cutoff: str | None = None
    certification_window_start: str | None = None
    generated_at: str | None = None
    tool_enforced_outcome_blind: bool = False
    legacy_tier: str | None = None


def classify_provenance(inp: ProvenanceInput) -> dict[str, str | bool | None]:
    """Classify certification route with model cutoff as the LLM PIT boundary.

    The critical rule from the Opus critique is implemented here: for
    LLM-generated ideas, inference-time outcome blindness is not enough. Any
    proposed certification window at or before the model's training cutoff is
    potentially contaminated by model weights and routes to prospective-only.
    """
    vis = normalize_visibility_mode(inp.visibility_mode)
    if inp.generator_type == "deterministic":
        return {
            "provenance_class": "deterministic_detector",
            "certification_route": "measured_gap_claim_required",
            "historical_certification_allowed": False,
            "reason": "deterministic_gap_is_measured_state_not_alpha",
        }
    if inp.generator_type == "harness" or vis == "pit_preregistered":
        return {
            "provenance_class": "pit_preregistered",
            "certification_route": "standard_harness_then_triage",
            "historical_certification_allowed": True,
            "reason": "known_denominator_pre_registered",
        }
    if vis == "legacy_unknown":
        return {
            "provenance_class": "legacy_unknown",
            "certification_route": "legacy_grandfathered_forward_tracking",
            "historical_certification_allowed": False,
            "reason": "legacy_or_unknown_prior_looking",
            "legacy_tier": inp.legacy_tier,
        }
    if inp.generator_type == "human":
        route = "standard_if_look_ledger_clean_else_prospective"
        return {
            "provenance_class": "human_pretest",
            "certification_route": route,
            "historical_certification_allowed": inp.tool_enforced_outcome_blind,
            "reason": "human_claim_requires_look_ledger_cleanliness",
        }

    # LLM path: cutoff is the real PIT boundary.
    if inp.generator_type == "llm":
        if vis == "full_retrospective":
            return {
                "provenance_class": "llm_retrospective_or_pre_cutoff",
                "certification_route": "prospective_only_retrospective",
                "historical_certification_allowed": False,
                "reason": "llm_full_retrospective_search_has_uncountable_trials",
            }
        cutoff = parse_date(inp.model_training_cutoff)
        start = parse_date(inp.certification_window_start)
        if cutoff is None:
            return {
                "provenance_class": "llm_retrospective_or_pre_cutoff",
                "certification_route": "prospective_only_unknown_cutoff",
                "historical_certification_allowed": False,
                "reason": "missing_model_training_cutoff",
            }
        if start is None:
            return {
                "provenance_class": "llm_retrospective_or_pre_cutoff",
                "certification_route": "prospective_only_missing_certification_window",
                "historical_certification_allowed": False,
                "reason": "missing_certification_window_start",
            }
        if start <= cutoff:
            return {
                "provenance_class": "llm_retrospective_or_pre_cutoff",
                "certification_route": "prospective_only_training_cutoff_contamination",
                "historical_certification_allowed": False,
                "reason": "certification_window_not_after_model_training_cutoff",
            }
        if vis in {"outcome_blind", "frozen_window"} and inp.tool_enforced_outcome_blind:
            return {
                "provenance_class": "llm_outcome_blind_post_cutoff",
                "certification_route": "post_cutoff_holdout_testable",
                "historical_certification_allowed": True,
                "reason": "post_cutoff_window_and_tool_enforced_outcome_blind",
            }
        return {
            "provenance_class": "llm_retrospective_or_pre_cutoff",
            "certification_route": "prospective_only_no_tool_enforced_blindness",
            "historical_certification_allowed": False,
            "reason": "outcome_blindness_not_tool_enforced",
        }

    raise ValueError(f"unsupported provenance input: {inp}")
