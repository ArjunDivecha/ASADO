"""H5 (red-team 2026-06-26): forward_track must attach the main warehouse as `asado`
so the daily return surface (asado.t2_factors_daily) resolves instead of raising
CatalogException. Honors ASADO_DATA_ROOT. Offline: tiny temp loop + main DBs.
"""
from __future__ import annotations

import duckdb

from scripts.discovery_triage.forward_track import (
    open_loop_with_warehouse,
    resolve_return_surface,
)


def test_open_loop_attaches_asado_for_daily_returns(tmp_path, monkeypatch):
    data = tmp_path / "Data"
    (data / "loop").mkdir(parents=True)
    # main warehouse with the asado-side daily factor table the resolver needs
    main = duckdb.connect(str(data / "asado.duckdb"))
    main.execute("CREATE TABLE t2_factors_daily(date DATE, country VARCHAR, variable VARCHAR, value DOUBLE)")
    main.execute(
        "INSERT INTO t2_factors_daily VALUES "
        "(DATE '2026-06-01','Brazil','1DRet',0.01),(DATE '2026-06-02','Brazil','1DRet',0.02),"
        "(DATE '2026-06-01','Chile','1DRet',-0.01),(DATE '2026-06-02','Chile','1DRet',0.03)"
    )
    main.close()
    # the loop DB file must exist (main() guards on it)
    duckdb.connect(str(data / "loop" / "asado_loop.duckdb")).close()

    monkeypatch.setenv("ASADO_DATA_ROOT", str(data))
    con = open_loop_with_warehouse(read_only=True)
    try:
        # pre-fix this raised duckdb CatalogException: schema 'asado' does not exist
        df = resolve_return_surface(con, "country_returns_daily")
        assert set(df.columns) >= {"date", "country", "ret"}
        assert len(df) >= 1
    finally:
        con.close()


def test_optimizer_return_surface_is_refused(tmp_path, monkeypatch):
    data = tmp_path / "Data"
    (data / "loop").mkdir(parents=True)
    duckdb.connect(str(data / "loop" / "asado_loop.duckdb")).close()
    monkeypatch.setenv("ASADO_DATA_ROOT", str(data))
    con = open_loop_with_warehouse(read_only=True)
    try:
        import pytest
        with pytest.raises(PermissionError):
            resolve_return_surface(con, "combiner_scores_daily")
    finally:
        con.close()
