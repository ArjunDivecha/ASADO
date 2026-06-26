"""Tests for the surface_loader JSON-content sanitizer (C1 / red-team 2026-06-26).

The column-name allowlist permits `price_state_daily.source_freshness_json`, but the
blob's CONTENTS previously smuggled the live `combiner_scores_daily` score (a Ridge fit
on forward returns) into the outcome-blind Discovery Lab snapshot. These tests prove the
forbidden key is scrubbed at the data-access layer, while legitimate descriptors survive.
Offline: a tiny in-memory DuckDB stands in for the loop DB.
"""
from __future__ import annotations

import json

import duckdb
import pytest

from scripts.discovery_triage import surface_loader as sl


def test_sanitizer_drops_combiner_key():
    blob = json.dumps({
        "t2_returns": "2026-06-24",
        "etf_flow_signals": {"ETF_FLOW_21D_Z": 0.4},
        "combiner_scores_daily": {"COMBINER_RIDGE_DAILY_V1": {"value": -9.55e-05}},
    })
    out = json.loads(sl.sanitize_json_blob(blob))
    assert "combiner_scores_daily" not in out
    assert "combiner" not in sl.sanitize_json_blob(blob).lower()
    # legitimate outcome-blind descriptors are preserved
    assert out["t2_returns"] == "2026-06-24"
    assert out["etf_flow_signals"]["ETF_FLOW_21D_Z"] == 0.4


def test_sanitizer_drops_nested_forward_return_and_combiner_value_key():
    blob = json.dumps({"freshness": {"COMBINER_RIDGE_DAILY_V1": -1.0, "1mret": 0.2, "ok": 1}})
    out = json.loads(sl.sanitize_json_blob(blob))
    # nested keys naming a forbidden surface/variable are removed with their values
    assert "COMBINER_RIDGE_DAILY_V1" not in out["freshness"]
    assert "1mret" not in out["freshness"]
    assert out["freshness"]["ok"] == 1


def test_sanitizer_passes_non_json_through():
    assert sl.sanitize_json_blob(None) is None
    assert sl.sanitize_json_blob("not json {") == "not json {"
    assert sl.sanitize_json_blob(3.14) == 3.14


def test_load_surface_scrubs_combiner_from_blob():
    con = duckdb.connect(":memory:")
    con.execute(
        'CREATE TABLE price_state_daily('
        ' "date" DATE, "country" VARCHAR, "source_freshness_json" VARCHAR,'
        ' "equity_state_json" VARCHAR, "price_state_summary" VARCHAR)'
    )
    leak = json.dumps({
        "t2_returns": "2026-06-24",
        "combiner_scores_daily": {"COMBINER_RIDGE_DAILY_V1": {"value": -9.552327532121927e-05}},
    })
    con.execute(
        "INSERT INTO price_state_daily VALUES (DATE '2026-06-24', 'Australia', ?, ?, ?)",
        [leak, json.dumps({"return_21d": 0.01}), "Australia summary"],
    )
    rows = sl.load_surface(con, "price_state_daily", "2026-06-24")
    assert len(rows) == 1
    serialized = json.dumps(rows[0], default=str)
    assert "combiner" not in serialized.lower()
    assert "9.552327532121927e-05" not in serialized
    # legitimate descriptors survive
    assert json.loads(rows[0]["source_freshness_json"])["t2_returns"] == "2026-06-24"
    assert json.loads(rows[0]["equity_state_json"])["return_21d"] == 0.01


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
