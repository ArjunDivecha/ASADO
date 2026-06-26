"""Tests for ASADO_DATA_ROOT path resolution (merge Phase 5 / FR9). No real DB needed."""
from __future__ import annotations

from pathlib import Path

from scripts.discovery_triage import paths


def test_loop_db_path_honors_data_root_override(monkeypatch, tmp_path):
    monkeypatch.setenv("ASADO_DATA_ROOT", str(tmp_path))
    assert paths.data_root() == tmp_path
    assert paths.loop_db_path() == tmp_path / "loop" / "asado_loop.duckdb"


def test_loop_db_path_defaults_to_repo_data(monkeypatch):
    monkeypatch.delenv("ASADO_DATA_ROOT", raising=False)
    assert paths.loop_db_path() == paths.BASE_DIR / "Data" / "loop" / "asado_loop.duckdb"
    assert isinstance(paths.loop_db_path(), Path)
