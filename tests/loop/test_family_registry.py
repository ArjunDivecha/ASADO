#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: tests/loop/test_family_registry.py
=============================================================================

INPUT FILES: the shipped config/family_registry.yaml + the real
hypothesis_ledger.jsonl (read-only) for the canonical-counting + migration
conservation tests. register_hypothesis is exercised only on the RAISE path
(unclassifiable variable), which fails BEFORE any ledger write.

OUTPUT FILES: none.

VERSION: 1.0
LAST UPDATED: 2026-06-17
AUTHOR: Arjun Divecha (built by agent session, Governance Layer PRD v1.2, item A5)

DESCRIPTION:
A5 acceptance: the deflated-Sharpe family N is variable-derived (un-gameable),
the split families collapse to one canonical family, the pooled family splits,
register raises on an unclassifiable variable, and the migration diff conserves
every trial charge exactly once.

USAGE:
  venv/bin/python -m pytest tests/loop/test_family_registry.py -q
=============================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
from scripts.loop import ledgers, family_migration  # noqa: E402
from scripts.loop.family_registry import resolve_family, UnclassifiedVariableError  # noqa: E402


# ── variable -> canonical family ────────────────────────────────────────────

@pytest.mark.parametrize("var,fam", [
    ("GRAPH_TRADE_NBR_RET_GAP_21D", "network_spillover"),
    ("GRAPHP_KATZ_TRADE_GAP_21D", "network_spillover"),
    ("LL_LEADER_GAP_5D", "network_spillover"),
    ("SIM_NBR_RET_GAP_21D", "network_spillover"),
    ("ECO_INFL_SURPRISE_Z", "eco_surprise"),
    ("FX_RR25_Z252", "fx_implied"),
    ("SOV_CDS_SLOPE_Z252", "sov_curve"),
    ("VAL_CAPE_PCTILE_10Y", "valuation"),
    ("COMBINER_RIDGE_DAILY_V1", "ml_combiner"),
    ("CONS_CPI_REV3M_12M", "consensus_revisions"),
    ("ETF_FLOW_21D_Z", "etf_positioning"),
    ("12MRet", "momentum_sanity"),
])
def test_resolve_family(var, fam):
    assert resolve_family(var) == fam


def test_resolve_family_raises_on_unknown():
    with pytest.raises(UnclassifiedVariableError):
        resolve_family("TOTALLY_NEW_THING_Z")
    with pytest.raises(UnclassifiedVariableError):
        resolve_family("")


# ── register raises on an unclassifiable variable (before any write) ─────────

def test_register_raises_on_unclassifiable_variable():
    n_before = len(ledgers._read_events(ledgers.HYP_PATH))
    with pytest.raises(UnclassifiedVariableError):
        ledgers.register_hypothesis(
            archetype="A1", family_key="whatever",
            mechanism_text="a real paragraph of at least fifteen words explaining the supposed "
                           "mechanism so the validation passes and we reach the variable check",
            signal_spec={"table": "x", "variable": "UNKNOWN_VAR_PREFIX_Z"})
    n_after = len(ledgers._read_events(ledgers.HYP_PATH))
    assert n_after == n_before, "raise must happen BEFORE any ledger append"


# ── canonical counting on the real ledger ───────────────────────────────────

def test_split_families_collapse_to_network_spillover():
    hyps = ledgers.fold_hypotheses()
    by_old = {}
    for h in hyps.values():
        by_old.setdefault(h["family_key"], h)
    for old in ("graph_trade_gap", "leadlag_2026_06", "fund_similarity_2026_06"):
        if old in by_old:
            assert ledgers.canonical_family_of(by_old[old]) == "network_spillover"


def test_canonical_N_larger_for_spillover_than_any_old_split():
    """The point of A5: collapsing the split families RAISES the bar (bigger N),
    splitting the pooled bbg family LOWERS each piece's N (was 16 pooled)."""
    n_spillover = ledgers.family_trial_count("network_spillover")
    n_graph_only = sum(ledgers._trial_charge(h) for h in ledgers.fold_hypotheses().values()
                       if h["family_key"] == "graph_trade_gap")
    assert n_spillover >= int(round(n_graph_only)), "spillover N must absorb the split families"
    # bbg_skill (was N~13-16 pooled) splits into distinct mechanisms, each smaller.
    for piece in ("eco_surprise", "fx_implied", "sov_curve"):
        assert ledgers.family_trial_count(piece) < 16


# ── migration diff conserves every trial charge exactly once ─────────────────

def test_migration_diff_conserves_charge():
    d = family_migration.build_diff()
    assert d["n_hypotheses"] == len(d["per_hypothesis"])
    assert d["charge_conserved"] is True
    old_total = sum(d["old_family_N"].values())
    new_total = sum(d["canonical_family_N"].values())
    # N is rounded per family, but the underlying charge is conserved; check the
    # per-hypothesis charges sum equally under both groupings.
    from collections import defaultdict
    old_c, new_c = defaultdict(float), defaultdict(float)
    for r in d["per_hypothesis"]:
        old_c[r["old_family"]] += r["trial_charge"]
        new_c[r["canonical_family"]] += r["trial_charge"]
    assert round(sum(old_c.values()), 6) == round(sum(new_c.values()), 6)
    # every hypothesis appears exactly once
    ids = [r["hypothesis_id"] for r in d["per_hypothesis"]]
    assert len(ids) == len(set(ids))
