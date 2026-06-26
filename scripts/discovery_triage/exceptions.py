"""
=============================================================================
SCRIPT NAME: scripts/discovery_triage/exceptions.py
=============================================================================

DESCRIPTION:
Explicit exception hierarchy for Discovery Triage so policy failures are visible
and catchable by category (FuguPRD merge PRD FR8). Ported/extended from the
codex-kahuna factoring.

INPUT/OUTPUT FILES: none (pure module).
VERSION: 1.0 (merge consolidation)
=============================================================================
"""
from __future__ import annotations


class DiscoveryTriageError(Exception):
    """Base class for discovery-triage failures."""


class ContextPolicyError(DiscoveryTriageError):
    """Context / surface policy violation (outcome-blindness, forbidden surface)."""


class LabValidationError(DiscoveryTriageError):
    """A Discovery Lab tool response failed strict-schema / policy validation."""


class ProvenanceError(DiscoveryTriageError):
    """Provenance classification / certification-route failure."""


class HarnessBridgeError(DiscoveryTriageError):
    """Harness bridge failure (missing required claim fields, etc.)."""
