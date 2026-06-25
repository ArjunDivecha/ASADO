"""Tests for outcome-blind enforcement: context_builder + surface_loader (PR-2A).

Covers §22 #4 (context rejects forbidden surfaces) and the Sakana column-level
leak (raw return columns on price_state_daily). Offline (synthetic in-memory DB).
"""
from __future__ import annotations

import duckdb
import pytest

from scripts.discovery_triage import surface_loader as sl
from scripts.discovery_triage.context_builder import (
    ContextPolicyError,
    ContextRequest,
    build_context_manifest,
)


@pytest.mark.parametrize("table", [
    "combiner_scores_daily", "graph_features_daily", "factor_returns",
    "factor_returns_daily", "country_returns_monthly", "country_factor_attribution",
])
def test_forbidden_tables_rejected(table):
    with pytest.raises(sl.SurfaceNotAllowed):
        sl.check_surface(table)


def test_non_whitelisted_table_rejected():
    with pytest.raises(sl.SurfaceNotAllowed):
        sl.check_surface("some_random_table")


def test_allowed_table_ok():
    assert sl.check_surface("price_state_daily")
    assert sl.check_surface("sovereign_signals")


def test_raw_return_column_rejected_on_price_state():
    # The Sakana leak: price_state_daily has raw return columns that must not be exposed.
    for col in ("country_return_21d", "etf_return_5d", "basis_gap_21d"):
        with pytest.raises(sl.SurfaceNotAllowed):
            sl.check_surface("price_state_daily", col)
    # ...but the json descriptors are allowed.
    assert sl.check_surface("price_state_daily", "equity_state_json")
    assert sl.check_surface("price_state_daily", "price_state_summary")


def test_load_surface_applies_column_allowlist_and_pit_cut():
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE price_state_daily (date VARCHAR, country VARCHAR, "
        "country_return_21d DOUBLE, equity_state_json VARCHAR, price_state_summary VARCHAR)"
    )
    con.execute(
        "INSERT INTO price_state_daily VALUES "
        "('2027-01-10','Brazil', 0.05, '{\"z\":1}', 'calm'),"
        "('2027-01-20','Brazil', 0.09, '{\"z\":2}', 'stress'),"   # after as_of -> excluded
        "('2027-01-05','Chile', -0.02, '{\"z\":0}', 'calm')"
    )
    rows = sl.load_surface(con, "price_state_daily", "2027-01-15")
    by_country = {r["country"]: r for r in rows}
    # raw return column never exposed
    assert all("country_return_21d" not in r for r in rows)
    assert "equity_state_json" in by_country["Brazil"]
    # PIT cut: Brazil's post-as_of row (2027-01-20) excluded -> latest <= as_of is 2027-01-10
    assert by_country["Brazil"]["price_state_summary"] == "calm"
    assert set(by_country) == {"Brazil", "Chile"}


def test_manifest_blocks_forbidden_surface_under_alias():
    # tool_outcome_blind alias must STILL enforce (normalizer closes the bypass).
    req = ContextRequest(visibility_mode="tool_outcome_blind",
                         requested_surfaces=["factor_returns_daily"])
    with pytest.raises(ContextPolicyError):
        build_context_manifest(req)


def test_manifest_allows_clean_surfaces_and_normalizes_mode():
    req = ContextRequest(visibility_mode="tool_outcome_blind",
                         requested_surfaces=["price_state_daily", "valuation_monthly"])
    manifest = build_context_manifest(req)
    assert manifest["visibility_mode"] == "outcome_blind"  # alias normalized
    assert manifest["tool_enforced_outcome_blind"] is True
