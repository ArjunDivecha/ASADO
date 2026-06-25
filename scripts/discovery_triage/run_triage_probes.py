"""
=============================================================================
SCRIPT NAME: scripts/discovery_triage/run_triage_probes.py
=============================================================================

DESCRIPTION:
The minimal triage battery (FuguPRD §15) — cheap first-pass probes run BEFORE any
LLM prosecutor. PR-2A implements:
  - Probe 1 target_reentry (FATAL): pure, no-DB check that a claim's signal does
    not touch forward returns / optimizer outputs / factor returns / attribution /
    forward-return variables. A fatal hit => killed_fatal_leakage.
  - Probe 2 leave_one_crisis_out (warning) and Probe 3 country_region_jackknife
    (warning): evidence-driven — they flag concentration when per-crisis / per-
    country contribution evidence is supplied; otherwise they report `not_run`
    (the per-window IC needed to compute them lands with the harness wire in 2B).
  - Power-budget BAND (§15.5): a band, NEVER a verdict. An underpowered claim is
    routed to the incubator with its band attached, never killed here.

INPUT FILES: none directly (operates on a claim dict + optional returns panel).
OUTPUT FILES: none (returns a validated triage_result dict; the caller persists it).

VERSION: 1.0 (PR-2A)
LAST UPDATED: 2026-06-25
AUTHOR: Arjun Divecha (built with Claude Code)

DEPENDENCIES: pydantic (via schemas); numpy/pandas only if a returns panel is passed.
=============================================================================
"""
from __future__ import annotations

from typing import Any, Optional

from . import schemas
from .surface_loader import (
    FORBIDDEN_COLUMN_PATTERNS,
    FORBIDDEN_SURFACES,
    FORWARD_RETURN_VARIABLES,
)


def _signal_tables(claim: dict[str, Any]) -> list[str]:
    tables: list[str] = []
    spec = claim.get("signal_spec") or {}
    for key in ("table", "tables", "sql"):
        v = spec.get(key)
        if isinstance(v, str):
            tables.append(v)
        elif isinstance(v, list):
            tables.extend(str(x) for x in v)
    return tables


def target_reentry(claim: dict[str, Any]) -> dict[str, Any]:
    """FATAL probe: reject a signal built on a forbidden outcome surface, a forward
    optimizer target, or a forward-return-shaped variable. Note: the claim's
    `target.return_surface` is the legitimate OUTCOME side and is NOT inspected here."""
    fatal: list[str] = []
    for table in _signal_tables(claim):
        if str(table).strip().lower() in FORBIDDEN_SURFACES:
            fatal.append(f"signal table {table!r} is a forbidden outcome surface")
    for var in claim.get("variables", []) or []:
        v = str(var).strip().lower()
        if v in FORWARD_RETURN_VARIABLES:
            fatal.append(f"variable {var!r} is a forward optimizer target")
        elif FORBIDDEN_COLUMN_PATTERNS.search(v):
            fatal.append(f"variable {var!r} matches a forbidden (forward/return/combiner) pattern")
    status = "fail" if fatal else "pass"
    return {"probe_id": "target_reentry", "fatal": True, "status": status,
            "detail": "; ".join(fatal) if fatal else "no optimizer/forward re-entry detected"}


def leave_one_crisis_out(crisis_ic: Optional[dict[str, float]] = None,
                         full_ic: Optional[float] = None) -> dict[str, Any]:
    """Warning probe. If per-crisis IC evidence is supplied, flag when dropping a
    single crisis window collapses the evidence (concentration)."""
    if not crisis_ic or full_ic is None or full_ic == 0:
        return {"probe_id": "leave_one_crisis_out", "fatal": False, "status": "not_run",
                "detail": "per-crisis IC evidence not supplied (computed with the harness wire, 2B)"}
    worst = min(crisis_ic.values())  # IC with the most-damaging crisis removed
    ratio = worst / full_ic
    if ratio < 0.5:
        return {"probe_id": "leave_one_crisis_out", "fatal": False, "status": "warning",
                "detail": f"evidence weakens materially excluding one crisis (residual {ratio:.0%})"}
    return {"probe_id": "leave_one_crisis_out", "fatal": False, "status": "pass",
            "detail": f"robust to leave-one-crisis-out (residual {ratio:.0%})"}


def country_region_jackknife(country_contrib: Optional[dict[str, float]] = None) -> dict[str, Any]:
    """Warning probe. If per-country contribution evidence is supplied, flag when a
    single country/region owns the signal."""
    if not country_contrib:
        return {"probe_id": "country_region_jackknife", "fatal": False, "status": "not_run",
                "detail": "per-country contribution evidence not supplied (2B)"}
    total = sum(abs(v) for v in country_contrib.values()) or 1.0
    top = max(abs(v) for v in country_contrib.values()) / total
    if top > 0.5:
        owner = max(country_contrib, key=lambda k: abs(country_contrib[k]))
        return {"probe_id": "country_region_jackknife", "fatal": False, "status": "warning",
                "detail": f"{owner} owns {top:.0%} of the signal"}
    return {"probe_id": "country_region_jackknife", "fatal": False, "status": "pass",
            "detail": f"no single country dominates (max {top:.0%})"}


def power_budget_band(returns_panel: Any, horizon_rows: int = 1,
                      corr_band: tuple[float, float] = (0.25, 0.55)) -> dict[str, Any]:
    """A BAND, not a verdict (FuguPRD §15.5). Estimates the detectable-IC range from
    a wide returns panel (rows=dates, cols=countries) under an equicorrelation band."""
    n_obs, n_ctry = (int(returns_panel.shape[0]), int(returns_panel.shape[1]))
    n_blocks = max(1, n_obs // max(1, horizon_rows))
    eff_ns: list[float] = []
    ics: list[float] = []
    for rho in corr_band:
        eff_ctry = n_ctry / (1 + (n_ctry - 1) * rho) if n_ctry > 0 else 0.0
        eff_n = max(1.0, n_blocks * eff_ctry)
        eff_ns.append(eff_n)
        ics.append(2.8 / (eff_n ** 0.5))
    return {
        "effective_n_band": [round(min(eff_ns)), round(max(eff_ns))],
        "detectable_ic_band": [round(min(ics), 3), round(max(ics), 3)],
        "assumptions": {"country_correlation": list(corr_band),
                        "horizon_overlap_adjustment": True,
                        "horizon_rows": horizon_rows},
        "n_obs": n_obs, "n_countries": n_ctry,
        "conclusion": "advisory_band_not_a_verdict",
        "allowed_use": "prospective_or_descriptive",
    }


def run_triage(
    claim: dict[str, Any],
    *,
    returns_panel: Any = None,
    horizon_rows: int = 1,
    crisis_ic: Optional[dict[str, float]] = None,
    full_ic: Optional[float] = None,
    country_contrib: Optional[dict[str, float]] = None,
) -> dict[str, Any]:
    """Run the battery and assemble a validated triage_result. A FATAL probe yields
    status `killed_fatal_leakage`; otherwise `triage_passed_not_validated`."""
    probes = [
        target_reentry(claim),
        leave_one_crisis_out(crisis_ic, full_ic),
        country_region_jackknife(country_contrib),
    ]
    fatal = [p["detail"] for p in probes if p.get("fatal") and p["status"] == "fail"]
    warnings = [p["probe_id"] for p in probes if p["status"] == "warning"]
    result: dict[str, Any] = {
        "claim_id": claim.get("claim_id", "UNKNOWN"),
        "status": "killed_fatal_leakage" if fatal else "triage_passed_not_validated",
        "fatal_failures": fatal,
        "warnings": warnings,
        "probes": probes,
    }
    if returns_panel is not None:
        result["power_budget"] = power_budget_band(returns_panel, horizon_rows)
    schemas.TriageResult.model_validate(result)
    return result
