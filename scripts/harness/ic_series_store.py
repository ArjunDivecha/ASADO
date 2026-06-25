#!/usr/bin/env python3
"""
Persist per-date rank-IC series from skeptic-harness runs into the loop DB.

The harness summary table is intentionally small. This companion table gives
front ends a real IC path to display without rerunning the harness or inventing
mock chart data.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

import pandas as pd


IC_SERIES_TABLE = "harness_ic_series"


def ensure_ic_series_table(con) -> None:
    con.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {IC_SERIES_TABLE} (
            hypothesis_id VARCHAR,
            family_key VARCHAR,
            run_ts VARCHAR,
            frequency VARCHAR,
            horizon VARCHAR,
            result_file VARCHAR,
            date DATE,
            ic DOUBLE,
            n_dates INTEGER,
            created_ts TIMESTAMP DEFAULT current_timestamp
        )
        """
    )


def _clean_ic(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return out


def ic_series_rows(
    result: Mapping[str, Any],
    ic_by_horizon: Mapping[str, pd.Series],
) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    result_file = str(result.get("result_file") or "")
    for horizon, series in ic_by_horizon.items():
        s = pd.Series(series).dropna().sort_index()
        n_dates = int(len(s))
        for dt, value in s.items():
            ic = _clean_ic(value)
            if ic is None:
                continue
            rows.append(
                (
                    result.get("hypothesis_id"),
                    result.get("family_key"),
                    result.get("run_ts"),
                    result.get("frequency"),
                    str(horizon),
                    result_file,
                    pd.Timestamp(dt).date().isoformat(),
                    ic,
                    n_dates,
                )
            )
    return rows


def replace_ic_series(con, result: Mapping[str, Any], ic_by_horizon: Mapping[str, pd.Series]) -> int:
    """Replace IC rows for one harness result_file. Returns inserted row count."""
    ensure_ic_series_table(con)
    result_file = str(result.get("result_file") or "")
    if not result_file:
        raise ValueError("result_file is required to persist harness IC series")
    con.execute(f"DELETE FROM {IC_SERIES_TABLE} WHERE result_file = ?", [result_file])
    rows = ic_series_rows(result, ic_by_horizon)
    if rows:
        con.executemany(
            f"""
            INSERT INTO {IC_SERIES_TABLE}
              (hypothesis_id, family_key, run_ts, frequency, horizon,
               result_file, date, ic, n_dates)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    return len(rows)
