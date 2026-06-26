"""Tests for record_look + the look ledger (PR-1). Offline."""
from __future__ import annotations

from scripts.discovery_triage.jsonl_store import read_jsonl
from scripts.discovery_triage.record_look import record_look


def test_record_look_writes_and_increments(tmp_path):
    looks = tmp_path / "research_looks.jsonl"
    id1, rec1 = record_look(actor="mythos", purpose="find_contradictions",
                            visibility_mode="tool_outcome_blind",
                            surfaces_seen=["price_state_daily", "valuation_monthly"],
                            looks_path=looks)
    id2, _ = record_look(actor="mythos", purpose="graph_motif",
                         visibility_mode="outcome_blind", looks_path=looks)

    # IDs increment within the day
    assert id1.startswith("L_") and id2.startswith("L_")
    assert int(id1.rsplit("_", 1)[1]) + 1 == int(id2.rsplit("_", 1)[1])

    # required §11.3 keys present; alias normalized to canonical
    for k in ("look_id", "created_at", "actor", "purpose", "visibility_mode",
              "surfaces_seen", "surfaces_forbidden", "outputs"):
        assert k in rec1
    assert rec1["visibility_mode"] == "outcome_blind"  # tool_outcome_blind -> canonical
    assert rec1["recorded_ts"].endswith(rec1["recorded_ts"][-6:])  # has offset tail

    # round-trips
    rows = read_jsonl(looks)
    assert len(rows) == 2
    assert {r["look_id"] for r in rows} == {id1, id2}
