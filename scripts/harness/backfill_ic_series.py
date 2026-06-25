#!/usr/bin/env python3
"""
Backfill harness_ic_series from existing harness result JSON files.

This does not create new hypotheses, verdicts, or harness_results rows. It
reconstructs the rank-IC time series for already-recorded runs so UI surfaces
can chart real historical IC paths instead of saying the series is unavailable.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.harness.evaluate_signal import (  # noqa: E402
    DEFAULT_DAILY_HORIZONS,
    DEFAULT_MONTHLY_HORIZONS,
    T2_UNIVERSE,
    align_daily,
    align_monthly,
    daily_country_returns,
    load_signal,
    rank_ic_series,
)
from scripts.harness.ic_series_store import (  # noqa: E402
    IC_SERIES_TABLE,
    ensure_ic_series_table,
    replace_ic_series,
)
from scripts.loop.loopdb import loop_connection  # noqa: E402


def _countries(value: Any) -> list[str]:
    if not value or value == "t2_34":
        return list(T2_UNIVERSE)
    if isinstance(value, list):
        return [str(x) for x in value]
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    return list(T2_UNIVERSE)


def _horizons(result: dict[str, Any]) -> list[int]:
    raw = result.get("horizons")
    if raw:
        return [int(x) for x in raw]
    return list(DEFAULT_MONTHLY_HORIZONS if result.get("frequency") == "monthly" else DEFAULT_DAILY_HORIZONS)


def _result_rows(con, hypothesis: str | None) -> list[dict[str, Any]]:
    where = "WHERE result_file IS NOT NULL AND result_file <> ''"
    params: list[Any] = []
    if hypothesis:
        where += " AND hypothesis_id = ?"
        params.append(hypothesis)
    df = con.execute(
        f"""
        SELECT DISTINCT hypothesis_id, family_key, run_ts, frequency, result_file
        FROM harness_results
        {where}
        ORDER BY run_ts, hypothesis_id, result_file
        """,
        params,
    ).fetchdf()
    return [dict(row._asdict()) for row in df.itertuples(index=False)]


def compute_ic_series(con, result: dict[str, Any]) -> dict[str, pd.Series]:
    frequency = result.get("frequency") or "monthly"
    countries = _countries(result.get("universe"))
    signal_spec = result["signal_spec"]
    start_date = result.get("start_date") or "2008-01-01"
    signal, _source = load_signal(con, signal_spec, countries, start_date, frequency)

    if frequency == "monthly":
        returns = con.execute("SELECT date, country, return_1m FROM country_returns_monthly").fetchdf()
        returns["date"] = pd.to_datetime(returns["date"])
        lag_months = int(result.get("publication_lag_months") or 0)
    else:
        returns = daily_country_returns(con).rename(columns={"ret": "return_1m"})
        returns = returns[returns["country"].isin(countries)]
        # Legacy daily run files predate the explicit daily lag field; use the
        # stored value when present, otherwise preserve the old lag-0 behavior.
        lag_days = int(result.get("publication_lag_days") or signal_spec.get("publication_lag_days") or 0)

    out: dict[str, pd.Series] = {}
    for h in _horizons(result):
        if frequency == "monthly":
            label = f"{h}m"
            aligned = align_monthly(signal, returns, lag_months, h)
        else:
            label = f"{h}d"
            aligned = align_daily(signal, returns, h, lag_days)
        out[label] = rank_ic_series(aligned)
    return out


def backfill(rebuild: bool = False, hypothesis: str | None = None, limit: int | None = None) -> dict[str, Any]:
    con = loop_connection()
    inserted = 0
    skipped = 0
    failed: list[dict[str, str]] = []
    try:
        ensure_ic_series_table(con)
        rows = _result_rows(con, hypothesis)
        if limit is not None:
            rows = rows[:limit]
        for i, row in enumerate(rows, 1):
            result_file = row["result_file"]
            existing = con.execute(
                f"SELECT count(*) FROM {IC_SERIES_TABLE} WHERE result_file = ?",
                [result_file],
            ).fetchone()[0]
            if existing and not rebuild:
                skipped += 1
                continue
            path = Path(result_file)
            if not path.exists():
                failed.append({"result_file": result_file, "error": "missing result file"})
                continue
            try:
                result = json.loads(path.read_text())
                result.update({k: row[k] for k in ("hypothesis_id", "family_key", "run_ts", "frequency")})
                result["result_file"] = result_file
                ic_by_horizon = compute_ic_series(con, result)
                inserted += replace_ic_series(con, result, ic_by_horizon)
                print(f"[{i}/{len(rows)}] {row['hypothesis_id']} {row['family_key']} -> "
                      f"{sum(len(s) for s in ic_by_horizon.values())} IC rows", flush=True)
            except Exception as exc:  # noqa: BLE001
                failed.append({"result_file": result_file, "error": str(exc)})
                print(f"[WARN] {result_file}: {exc}", file=sys.stderr, flush=True)
    finally:
        con.close()
    return {"inserted_rows": inserted, "skipped_results": skipped, "failed": failed}


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill harness_ic_series from existing harness run JSON files.")
    parser.add_argument("--rebuild", action="store_true", help="Delete/rewrite rows for result files already backfilled.")
    parser.add_argument("--hypothesis", help="Limit to one hypothesis_id.")
    parser.add_argument("--limit", type=int, help="Debug limit on result files processed.")
    args = parser.parse_args()
    summary = backfill(rebuild=args.rebuild, hypothesis=args.hypothesis, limit=args.limit)
    print(json.dumps(summary, indent=2))
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
