"""
=============================================================================
SCRIPT NAME: test_ews_context.py
=============================================================================

WHAT THIS PROGRAM DOES:
Tests for the EWS context-tier step (scripts/loop/build_ews_context.py) and
its brief section (build_dislocations._ews_and_gates_context_section).
Synthetic data only - never touches the real Early Warning repo, the real
Data/work/loop artifacts, or any DuckDB. Covers: correct extraction from a
synthetic EWS run dir, staleness flagging, fail-soft exit 2 when the source
repo is absent, atomic artifact writing, and graceful brief-section rendering
with artifacts present, stale, and absent.

INPUT FILES:  none (all fixtures built under pytest tmp_path)
OUTPUT FILES: none (tmp_path only)

VERSION: 1.0  |  LAST UPDATED: 2026-07-15  |  AUTHOR: Claude (EWS context tier)
USAGE: venv/bin/python -m pytest tests/test_ews_context.py -q
=============================================================================
"""
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from scripts.loop import build_ews_context as bec           # noqa: E402
from scripts.loop.build_dislocations import _ews_and_gates_context_section  # noqa: E402


def _mk_ews_run(root: Path, as_of="2026-05-31", state="IN"):
    run = root / "run_20990101_000000"
    run.mkdir(parents=True)
    idx = pd.date_range("2025-06-30", as_of, freq="ME")
    panel = pd.DataFrame({
        "state_best": [state] * len(idx),
        "composite": [0.42] * len(idx),
        "composite_pctile": [0.45] * len(idx),
        "diffusion": [0.0769] * len(idx),
    }, index=idx)
    panel.to_parquet(run / "signals_panel.parquet")
    (run / "summary.json").write_text(json.dumps({"best": {"variant": "V4"}}))
    return run


def test_extracts_latest_state(tmp_path, monkeypatch):
    monkeypatch.setattr(bec, "EWS_OUTPUTS", tmp_path)
    _mk_ews_run(tmp_path, as_of="2025-12-31")  # unambiguously old -> stale
    ctx = bec.build_context()
    assert ctx["state"] == "IN"
    assert ctx["as_of_month_end"] == "2025-12-31"
    assert ctx["composite"] == 0.42
    assert ctx["classifier"] == "V4"
    assert ctx["stale"] is True


def test_fresh_reading_not_stale(tmp_path, monkeypatch):
    monkeypatch.setattr(bec, "EWS_OUTPUTS", tmp_path)
    recent = (pd.Timestamp.now().normalize() - pd.offsets.MonthEnd(1)).strftime("%Y-%m-%d")
    _mk_ews_run(tmp_path, as_of=recent)
    ctx = bec.build_context()
    assert ctx["stale"] is False
    assert ctx["age_days"] <= bec.STALE_DAYS


def test_fail_soft_exit_2_when_repo_absent(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(bec, "EWS_OUTPUTS", tmp_path / "nope")
    monkeypatch.setattr(bec, "ARTIFACT", tmp_path / "out" / "ews_context.json")
    monkeypatch.setattr(sys, "argv", ["build_ews_context.py"])
    rc = bec.main()
    assert rc == 2
    assert "PARTIAL" in capsys.readouterr().err
    assert not (tmp_path / "out" / "ews_context.json").exists()


def test_artifact_written_atomically(tmp_path, monkeypatch):
    monkeypatch.setattr(bec, "EWS_OUTPUTS", tmp_path)
    art = tmp_path / "work" / "ews_context.json"
    monkeypatch.setattr(bec, "ARTIFACT", art)
    monkeypatch.setattr(sys, "argv", ["build_ews_context.py"])
    _mk_ews_run(tmp_path)
    assert bec.main() == 0
    ctx = json.loads(art.read_text())
    assert ctx["state"] == "IN" and not art.with_name(art.name + ".tmp").exists()
    assert "a7_habitat_note" in ctx and "context-only" in ctx["tier"]


def test_brief_section_renders_with_both_artifacts(tmp_path):
    (tmp_path / "ews_context.json").write_text(json.dumps({
        "state": "IN", "as_of_month_end": "2026-05-31", "composite": 0.42,
        "composite_pctile": 0.45, "diffusion": 0.0769, "stale": False,
        "a7_habitat_note": "A7 note here"}))
    (tmp_path / "family_ic_status.json").write_text(json.dumps({
        "as_of": "2026-07-15",
        "families": {"network_spillover": {"state": "parked", "consecutive_positive": 1}}}))
    lines = _ews_and_gates_context_section(base=tmp_path)
    joined = "\n".join(lines)
    assert "## US regime + family-gate context" in joined
    assert "**IN**" in joined and "A7 note here" in joined
    assert "network_spillover parked/1" in joined and "re-arm fires at 2" in joined
    assert "STALE" not in joined


def test_brief_section_flags_stale_and_degrades_when_absent(tmp_path):
    (tmp_path / "ews_context.json").write_text(json.dumps({
        "state": "OUT", "as_of_month_end": "2026-01-31", "composite": 0.9,
        "composite_pctile": 0.99, "diffusion": 0.5, "stale": True,
        "a7_habitat_note": "n"}))
    lines = _ews_and_gates_context_section(base=tmp_path)
    joined = "\n".join(lines)
    assert "STALE" in joined                       # staleness surfaced, not hidden
    assert "family gates UNAVAILABLE" in joined    # missing gate artifact degrades
    empty = _ews_and_gates_context_section(base=tmp_path / "void")
    assert any("EWS context UNAVAILABLE" in l for l in empty)
