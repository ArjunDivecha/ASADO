#!/usr/bin/env python3
"""
ASADO Perspective Lab backend.

Serves curated DuckDB-backed datasets for the Perspective web UI. The lab is
read-only by design: it exposes focused analytical slices instead of handing
the browser the full ASADO warehouse.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "Data" / "asado.duckdb"
LAB_DIR = BASE_DIR / "frontend" / "perspective_lab"
DIST_DIR = LAB_DIR / "dist"


def _duck_path(path: Path) -> str:
    return path.as_posix().replace("'", "''")


ANALOG_SIGNALS = _duck_path(BASE_DIR / "Data" / "strategy" / "analogs" / "v1" / "signals.parquet")
ANALOG_BACKTEST = _duck_path(BASE_DIR / "Data" / "strategy" / "analogs" / "v1" / "backtest.parquet")


@dataclass(frozen=True)
class Dataset:
    title: str
    description: str
    sql: str
    default_limit: int = 5000
    max_limit: int = 50000
    date_column: str | None = "date"


DATASETS: dict[str, Dataset] = {
    "daily_country_returns": Dataset(
        title="Daily Country Returns",
        description="Canonical T2 daily country returns across ASADO horizons.",
        sql="""
            WITH latest_by_horizon AS (
                SELECT variable, MAX(date) AS date
                FROM t2_factors_daily
                WHERE variable IN ('1DRet', '5DRet', '20DRet', '60DRet', '120DRet')
                  AND value IS NOT NULL
                  AND ABS(value) > 1e-12
                GROUP BY variable
            )
            SELECT
                d.date,
                d.country,
                d.variable AS horizon,
                d.value AS return_value
            FROM t2_factors_daily d
            JOIN latest_by_horizon m
              ON d.variable = m.variable
             AND d.date >= m.date - INTERVAL 180 DAY
             AND d.date <= m.date
            WHERE d.variable IN ('1DRet', '5DRet', '20DRet', '60DRet', '120DRet')
              AND d.value IS NOT NULL
            ORDER BY d.date DESC, d.variable, d.value DESC
        """,
        default_limit=25000,
    ),
    "daily_factor_returns": Dataset(
        title="Daily Factor Returns",
        description="Daily optimizer factor portfolio returns from T2 and GDELT.",
        sql="""
            WITH max_date AS (
                SELECT MAX(date) AS date
                FROM factor_returns_daily
            )
            SELECT
                d.date,
                d.source,
                d.factor,
                d.value AS return_value
            FROM factor_returns_daily d
            JOIN max_date m ON d.date >= m.date - INTERVAL 180 DAY
            WHERE d.value IS NOT NULL
            ORDER BY d.date DESC, d.source, d.factor
        """,
        default_limit=30000,
    ),
    "monthly_factor_payoff": Dataset(
        title="Monthly Factor Payoff",
        description="Rolling 12-month factor payoff diagnostics from monthly optimizer returns.",
        sql="""
            WITH max_date AS (
                SELECT MAX(date) AS date
                FROM factor_returns
            ),
            base AS (
                SELECT r.*
                FROM factor_returns r
                JOIN max_date m ON r.date > m.date - INTERVAL 12 MONTH
                WHERE r.value IS NOT NULL
            )
            SELECT
                source,
                factor,
                COUNT(*) AS observations,
                MAX(date) AS latest_date,
                SUM(value) AS payoff_sum_12m,
                AVG(value) AS avg_monthly_return,
                STDDEV_SAMP(value) AS vol_monthly_return,
                AVG(value) / NULLIF(STDDEV_SAMP(value), 0) * SQRT(12) AS sharpe_like_12m,
                AVG(CASE WHEN value > 0 THEN 1.0 ELSE 0.0 END) AS hit_rate_12m
            FROM base
            GROUP BY source, factor
            HAVING COUNT(*) >= 6
            ORDER BY sharpe_like_12m DESC NULLS LAST, payoff_sum_12m DESC
        """,
        date_column="latest_date",
    ),
    "country_attribution_latest": Dataset(
        title="Latest Country-Factor Attribution",
        description="Latest top-20 bucket contribution by country and factor.",
        sql="""
            WITH latest AS (
                SELECT MAX(date) AS date
                FROM country_factor_attribution
            )
            SELECT
                a.date,
                a.country,
                a.source,
                a.factor,
                a.weight,
                a.factor_return,
                a.contribution,
                ABS(a.contribution) AS abs_contribution
            FROM country_factor_attribution a
            JOIN latest l ON a.date = l.date
            ORDER BY ABS(a.contribution) DESC, a.country, a.factor
        """,
        default_limit=15000,
    ),
    "prediction_market_latest": Dataset(
        title="Latest Prediction-Market Signals",
        description="Curated prediction-market country and macro overlays.",
        sql="""
            WITH latest AS (
                SELECT MAX(snapshot_date) AS snapshot_date
                FROM predmkt_signals_daily
            )
            SELECT
                s.snapshot_date,
                s.signal_name,
                s.country,
                s.value,
                s.n_markets,
                s.total_liquidity_usd,
                s.confidence_score
            FROM predmkt_signals_daily s
            JOIN latest l ON s.snapshot_date = l.snapshot_date
            ORDER BY s.signal_name, s.value DESC NULLS LAST, s.country
        """,
        default_limit=5000,
        date_column="snapshot_date",
    ),
    "commodity_momentum_latest": Dataset(
        title="Latest Commodity Momentum",
        description="World Bank commodity features at the latest monthly cut.",
        sql="""
            WITH latest AS (
                SELECT MAX(date) AS date
                FROM wb_commodity_features
                WHERE feature IN ('ret_12m_pct', 'ret_3m_pct', 'z_36m', 'mom_pct')
            )
            SELECT
                f.date,
                f.category,
                f.display_name,
                f.series_code,
                f.feature,
                f.value,
                f.unit,
                f.source
            FROM wb_commodity_features f
            JOIN latest l ON f.date = l.date
            WHERE f.feature IN ('ret_12m_pct', 'ret_3m_pct', 'z_36m', 'mom_pct')
              AND f.value IS NOT NULL
            ORDER BY f.feature, f.value DESC
        """,
        default_limit=15000,
    ),
    "unified_panel_freshness": Dataset(
        title="Warehouse Freshness",
        description="Rows, variables, countries, and date coverage by source in unified_panel.",
        sql="""
            SELECT
                source,
                COUNT(*) AS rows,
                COUNT(DISTINCT variable) AS variables,
                COUNT(DISTINCT country) AS countries,
                MIN(date) AS first_date,
                MAX(date) AS latest_date
            FROM unified_panel
            GROUP BY source
            ORDER BY rows DESC
        """,
        default_limit=5000,
        date_column="latest_date",
    ),
    "analog_signals_latest": Dataset(
        title="Strategy #1 Latest Analog Signals",
        description="Latest saved analog strategy country scores, retained as a no-go baseline artifact.",
        sql=f"""
            WITH src AS (
                SELECT *
                FROM read_parquet('{ANALOG_SIGNALS}')
            ),
            latest AS (
                SELECT MAX(date) AS date
                FROM src
            )
            SELECT src.*
            FROM src
            JOIN latest ON src.date = latest.date
            ORDER BY rank ASC NULLS LAST, score DESC NULLS LAST
        """,
        default_limit=5000,
    ),
    "analog_backtest": Dataset(
        title="Strategy #1 Analog Backtest",
        description="Saved monthly backtest path for the no-go analog strategy.",
        sql=f"""
            SELECT *
            FROM read_parquet('{ANALOG_BACKTEST}')
            ORDER BY realized_date DESC
        """,
        default_limit=5000,
        date_column="realized_date",
    ),
}


app = FastAPI(title="ASADO Perspective Lab", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _connect() -> duckdb.DuckDBPyConnection:
    if not DB_PATH.exists():
        raise HTTPException(status_code=500, detail=f"DuckDB not found: {DB_PATH}")
    return duckdb.connect(str(DB_PATH), read_only=True)


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime("%Y-%m-%dT%H:%M:%S")
        elif pd.api.types.is_object_dtype(df[col]):
            df[col] = df[col].map(lambda x: x.isoformat() if hasattr(x, "isoformat") else x)
    return json.loads(df.to_json(orient="records"))


def _query_dataset(con: duckdb.DuckDBPyConnection, dataset: Dataset, limit: int) -> pd.DataFrame:
    limit = max(1, min(limit, dataset.max_limit))
    return con.execute(f"SELECT * FROM ({dataset.sql}) AS lab_dataset LIMIT ?", [limit]).fetchdf()


def _availability(con: duckdb.DuckDBPyConnection, dataset: Dataset) -> dict[str, Any]:
    try:
        df = _query_dataset(con, dataset, 1)
        return {"available": True, "columns": list(df.columns), "error": None}
    except Exception as exc:
        return {"available": False, "columns": [], "error": str(exc).splitlines()[0]}


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {
        "ok": DB_PATH.exists(),
        "db_path": str(DB_PATH),
        "db_size_bytes": DB_PATH.stat().st_size if DB_PATH.exists() else None,
        "dist_ready": DIST_DIR.exists(),
    }


@app.get("/api/summary")
def summary() -> dict[str, Any]:
    checks = [
        ("factor_returns", "date"),
        ("factor_returns_daily", "date"),
        ("factor_top20_membership", "date"),
        ("country_factor_attribution", "date"),
        ("t2_factors_daily", "date"),
        ("predmkt_signals_daily", "snapshot_date"),
        ("wb_commodity_features", "date"),
        ("unified_panel", "date"),
    ]
    with _connect() as con:
        rows = []
        for table, date_col in checks:
            try:
                row = con.execute(
                    f"""
                    SELECT
                        COUNT(*) AS row_count,
                        MIN({date_col}) AS first_date,
                        MAX({date_col}) AS latest_date
                    FROM {table}
                    """
                ).fetchone()
                rows.append(
                    {
                        "surface": table,
                        "available": True,
                        "row_count": row[0],
                        "first_date": row[1].isoformat() if row[1] else None,
                        "latest_date": row[2].isoformat() if row[2] else None,
                        "error": None,
                    }
                )
            except Exception as exc:
                rows.append(
                    {
                        "surface": table,
                        "available": False,
                        "row_count": None,
                        "first_date": None,
                        "latest_date": None,
                        "error": str(exc).splitlines()[0],
                    }
                )
    return {
        "db_path": str(DB_PATH),
        "db_size_bytes": DB_PATH.stat().st_size if DB_PATH.exists() else None,
        "surfaces": rows,
    }


@app.get("/api/datasets")
def datasets() -> dict[str, Any]:
    with _connect() as con:
        items = []
        for dataset_id, dataset in DATASETS.items():
            status = _availability(con, dataset)
            items.append(
                {
                    "id": dataset_id,
                    "title": dataset.title,
                    "description": dataset.description,
                    "default_limit": dataset.default_limit,
                    "max_limit": dataset.max_limit,
                    "date_column": dataset.date_column,
                    **status,
                }
            )
    return {"datasets": items}


@app.get("/api/dataset/{dataset_id}")
def dataset_rows(
    dataset_id: str,
    limit: int = Query(default=0, ge=0, le=50000),
) -> dict[str, Any]:
    if dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail=f"Unknown dataset: {dataset_id}")
    dataset = DATASETS[dataset_id]
    resolved_limit = limit or dataset.default_limit
    with _connect() as con:
        try:
            df = _query_dataset(con, dataset, resolved_limit)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {
        "id": dataset_id,
        "title": dataset.title,
        "description": dataset.description,
        "row_count": len(df),
        "columns": list(df.columns),
        "rows": _records(df),
    }


@app.get("/api/sql/{dataset_id}")
def dataset_sql(dataset_id: str) -> dict[str, str]:
    if dataset_id not in DATASETS:
        raise HTTPException(status_code=404, detail=f"Unknown dataset: {dataset_id}")
    return {"id": dataset_id, "sql": DATASETS[dataset_id].sql.strip()}


if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(DIST_DIR / "index.html")

    @app.get("/{path:path}")
    def spa_fallback(path: str):
        candidate = DIST_DIR / path
        if candidate.exists() and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(DIST_DIR / "index.html")
else:

    @app.get("/")
    def not_built() -> dict[str, str]:
        return {
            "status": "frontend-not-built",
            "dev": "cd frontend/perspective_lab && npm run dev",
            "api": "http://127.0.0.1:7832/api/datasets",
        }


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=7832, reload=False)


if __name__ == "__main__":
    main()
