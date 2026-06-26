"""
=============================================================================
SCRIPT NAME: scripts/discovery_triage/schemas.py
=============================================================================

DESCRIPTION:
Pydantic (v2) models for every object written to the Discovery Triage journal
(FuguPRD §3.3 / §10–§18). Every JSONL/YAML writer validates through the matching
model BEFORE the write, so a malformed object raises at creation and can never
silently corrupt an append-only ledger. The models are the single source of
truth for the §22 required-key assertions.

Models: Look, DetectorDraft, MechanismGraph, ContradictionCard, AnalogTaxonomy,
Claim (+ ClaimTarget / ClaimExpression / ClaimProvenance), TriageResult,
BlindRuling, IncubatorEntry, GraveyardEntry, Readout.

Design notes:
- `extra="allow"` so forward-compatible fields don't break older readers, while
  required keys remain enforced.
- `protected_namespaces=()` silences pydantic warnings about model_* fields
  (model_id, model_version, model_training_cutoff) which are part of the PRD schema.

INPUT/OUTPUT FILES: none (pure schema/validation library).

VERSION: 1.0 (PR-1)
LAST UPDATED: 2026-06-25
AUTHOR: Arjun Divecha (built with Claude Code)

DEPENDENCIES: pydantic>=2,<3
=============================================================================
"""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

MeasurementShape = Literal[
    "single_country_event",
    "cross_sectional_rank_ic",
    "long_short_bucket",
    "analog_set_forward_readout",
]


# --- strict falsification guarantees (H1 / red-team 2026-06-26) -------------
# These were previously enforced ONLY in lab_session.validate_card, so a non-Lab
# writer (make_detector_draft, freeze_claim) could persist a degenerate,
# non-falsifiable draft/claim that the cockpit then rendered as a "useful" card.
# Moving the non-empty guarantee into the custody schema makes it structural:
# EVERY persisted object is falsifiable, regardless of which writer produced it
# (FuguPRD §10.5/§10.6 / Merge-PRD FR2 / AC3 / Invariant F).
def _nonempty_items(v: Any) -> list:
    return [x for x in v if str(x).strip()] if isinstance(v, list) else []


def _require_nonempty_list(v: Any, name: str) -> Any:
    if not _nonempty_items(v):
        raise ValueError(f"{name} must be a non-empty list")
    return v


def _require_falsification(v: Any) -> Any:
    if not isinstance(v, dict):
        raise ValueError("falsification must be a dict with non-empty fatal_if and must_check")
    for key in ("fatal_if", "must_check"):
        if not _nonempty_items(v.get(key)):
            raise ValueError(f"falsification.{key} must be a non-empty list (FuguPRD §10.5 / FR2)")
    return v


def _require_self_falsification(v: Any) -> Any:
    if not isinstance(v, dict):
        raise ValueError("mythos_self_falsification must be a dict")
    sc = v.get("strongest_counterargument")
    if not isinstance(sc, str) or not sc.strip():
        raise ValueError(
            "mythos_self_falsification.strongest_counterargument must be a non-empty string (FR2)"
        )
    if not _nonempty_items(v.get("what_would_change_my_mind")):
        raise ValueError(
            "mythos_self_falsification.what_would_change_my_mind must be a non-empty list (FR2)"
        )
    return v


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow", protected_namespaces=())


class ModelMeta(_Base):
    model_id: str
    model_version: Optional[str] = None
    training_cutoff: Optional[str] = None
    tool_context_cutoff: Optional[str] = None


# --- looks & drafts --------------------------------------------------------
class Look(_Base):
    look_id: str
    created_at: str
    actor: str
    purpose: str
    visibility_mode: str
    model: Optional[ModelMeta] = None
    surfaces_seen: list[str] = Field(default_factory=list)
    surfaces_forbidden: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    contamination_class: Optional[str] = None
    certification_route: Optional[str] = None


class DetectorDraft(_Base):
    object_type: Literal["detector_family_draft"] = "detector_family_draft"
    draft_id: str
    family_name: str
    members: list[str]
    source_look_id: str
    certification_route: Optional[str] = None
    epistemic_status: list[str] = Field(default_factory=list)
    falsification: dict[str, Any]
    mythos_self_falsification: dict[str, Any]

    @field_validator("members")
    @classmethod
    def _v_members(cls, v: Any) -> Any:
        return _require_nonempty_list(v, "members")

    @field_validator("falsification")
    @classmethod
    def _v_falsification(cls, v: Any) -> Any:
        return _require_falsification(v)

    @field_validator("mythos_self_falsification")
    @classmethod
    def _v_self_falsification(cls, v: Any) -> Any:
        return _require_self_falsification(v)


class MechanismGraph(_Base):
    object_type: Literal["mechanism_graph"] = "mechanism_graph"
    title: str
    nodes: list[str]
    edges: list[str]
    predicted_observable: list[str] = Field(default_factory=list)
    status: str = "unvalidated"
    route: Optional[str] = None
    falsification: dict[str, Any]
    mythos_self_falsification: dict[str, Any]


class ContradictionCard(_Base):
    object_type: Literal["contradiction_card"] = "contradiction_card"
    entity: str
    as_of: str
    contradiction: dict[str, Any]
    mythos_interpretation: Optional[str] = None
    status: str = "unvalidated"
    route: Optional[str] = None
    falsification: dict[str, Any]
    mythos_self_falsification: dict[str, Any]


class AnalogTaxonomy(_Base):
    object_type: Literal["analog_taxonomy"] = "analog_taxonomy"
    taxonomy_name: str
    episode_classes: list[str]
    falsification: dict[str, Any]
    mythos_self_falsification: dict[str, Any]


# --- claims ----------------------------------------------------------------
class ClaimTarget(_Base):
    return_surface: str
    horizon_days: int
    direction: str
    target_type: str
    measurement_shape: MeasurementShape


class ClaimExpression(_Base):
    # ASADO trades country ETFs: the intended expression + implementation quality
    # is frozen with the claim (Sakana review must-fix #5).
    etf_ticker: str
    proxy_type: str
    liquidity_tier: Optional[str] = None
    dollar_adv_21d: Optional[float] = None
    bid_ask_spread_bps: Optional[float] = None
    expense_ratio_bps: Optional[float] = None
    tracking_or_basis_gap: Optional[float] = None
    ownership_or_crowding: Optional[float] = None
    flow_drag: Optional[float] = None


class ClaimProvenance(_Base):
    source: str
    visibility_mode: str
    certification_route: Optional[str] = None
    model_training_cutoff: Optional[str] = None
    certification_window_start: Optional[str] = None
    contamination_class: Optional[str] = None
    tool_enforced_outcome_blind: bool = False


class Claim(_Base):
    claim_id: str
    links: dict[str, Any] = Field(default_factory=dict)
    provenance: ClaimProvenance
    neutral_claim: dict[str, Any]
    mechanism: dict[str, Any]
    variables: list[str]
    target: ClaimTarget
    expression: ClaimExpression
    universe: dict[str, Any] = Field(default_factory=dict)
    falsification: dict[str, Any]
    # overlay (Invariant B) — populated by Phase 2 harness wire / triage
    harness_verdict: Optional[str] = None

    @field_validator("falsification")
    @classmethod
    def _v_falsification(cls, v: Any) -> Any:
        # An "attackable claim" that is not falsifiable defeats the harness (AC3).
        return _require_falsification(v)
    court_status: Optional[str] = None
    triage_flags: Optional[dict[str, Any]] = None
    power_budget: Optional[dict[str, Any]] = None
    blind_ruling: Optional[dict[str, Any]] = None
    forward_tracking_id: Optional[str] = None


# --- triage / ruling / tracking -------------------------------------------
class TriageResult(_Base):
    claim_id: str
    status: str
    fatal_failures: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    probes: list[dict[str, Any]] = Field(default_factory=list)
    power_budget: Optional[dict[str, Any]] = None


class BlindRuling(_Base):
    ruling_id: str
    claim_id: str
    judge: str
    blind_ruling: dict[str, Any]
    unseal: Optional[dict[str, Any]] = None


class IncubatorEntry(_Base):
    record_kind: Literal["incubator_entry"] = "incubator_entry"
    claim_id: str
    status: str
    start_date: str
    first_readout_date: Optional[str] = None
    full_readout_date: Optional[str] = None
    observations_required: Optional[int] = None
    observations_so_far: int = 0
    in_sample_certification: Literal["forbidden"] = "forbidden"
    expected_readouts: list[Any] = Field(default_factory=list)
    return_surface: str
    target_country: Optional[str] = None
    measurement_shape: MeasurementShape
    direction: str
    reason: Optional[str] = None
    hypothesis_id: Optional[str] = None


class GraveyardEntry(_Base):
    record_kind: Literal["graveyard_entry"] = "graveyard_entry"
    claim_id: str
    terminal_or_quarantine_status: str
    forward_tracking_enabled: bool = True
    start_date: str
    reason_for_tracking: Optional[str] = None
    expected_readouts: list[Any] = Field(default_factory=list)
    return_surface: str
    target_country: Optional[str] = None
    # mirror incubator_entry so forward_track can score the control arm without
    # re-reading the original claim (Sakana review symmetry fix).
    measurement_shape: MeasurementShape
    direction: str
    hypothesis_id: Optional[str] = None


class AnalogSet(_Base):
    # M4 (red-team 2026-06-26): the frozen analog shelf set was written UNVALIDATED.
    analog_set_id: str
    metric_id: str
    target: str
    frozen: bool = True
    outcome_blind: bool = True
    outcomes_attached: bool = False
    members: list[dict[str, Any]] = Field(default_factory=list)


class Readout(_Base):
    record_kind: Literal["readout"] = "readout"
    claim_id: str
    hypothesis_id: Optional[str] = None
    arm: Literal["incubator", "graveyard"]
    measurement_shape: MeasurementShape
    observation_date: str
    first_forward_date: Optional[str] = None
    horizon_days: int


REGISTRY: dict[str, type[BaseModel]] = {
    "look": Look,
    "detector_draft": DetectorDraft,
    "mechanism_graph": MechanismGraph,
    "contradiction_card": ContradictionCard,
    "analog_taxonomy": AnalogTaxonomy,
    "claim": Claim,
    "triage_result": TriageResult,
    "blind_ruling": BlindRuling,
    "incubator_entry": IncubatorEntry,
    "graveyard_entry": GraveyardEntry,
    "analog_set": AnalogSet,
    "readout": Readout,
}


def validate(kind: str, data: dict[str, Any]) -> dict[str, Any]:
    """Validate `data` against the model registered under `kind`. Returns the
    normalized dict (model_dump). Raises pydantic.ValidationError on a bad object."""
    if kind not in REGISTRY:
        raise KeyError(f"unknown object kind {kind!r}; known: {sorted(REGISTRY)}")
    model = REGISTRY[kind].model_validate(data)
    return model.model_dump(mode="json", exclude_none=False)


def validator_for(kind: str):
    """Return a callable suitable for jsonl_store's `validate=` hook."""
    model = REGISTRY[kind]

    def _v(data: dict[str, Any]) -> None:
        model.model_validate(data)

    return _v
