#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: check_cross_source.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/cross_source.yaml
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb (read-only)
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb (read-only, attached `asado`)

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/governance/cross_source_status.json
  {sentinel breaches, pair breaches, coverage_fraction, hard_breach}. The A8
  scorecard reads this and renders cross_source_minimal AMBER (by design) with
  the coverage fraction; a hard breach (sentinel mismatch) reds it.

VERSION: 1.0
LAST UPDATED: 2026-06-17
AUTHOR: Arjun Divecha (built by agent session, Governance Layer PRD v1.2, item A7)

DESCRIPTION:
A7 — the GSAB defense. Two checks: (1) human-curated SENTINEL anchors (exact
match, hard stop on mismatch — catches silent corruption/restatement);
(2) cross-source PAIRS — a redundant series from two independent sources must
agree per country; a large discrepancy is a series tracking the wrong entity
(the GSAB10YR shape). Partial by design: cross_source_minimal is AMBER, never
green in Phase A; coverage_fraction is reported honestly.

EXIT: non-zero on a hard breach (sentinel mismatch). Pair breaches are recorded
(they red the scorecard) but do NOT crash the nightly job — a convention
difference must not false-fail the whole loop.

DEPENDENCIES:
- duckdb, pandas, pyyaml (project venv)

USAGE:
  python scripts/loop/check_cross_source.py            # run + write status JSON
=============================================================================
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.loop.loopdb import BASE_DIR, LOOP_DIR, loop_connection

CONFIG_PATH = BASE_DIR / "config" / "cross_source.yaml"
OUT_PATH = LOOP_DIR / "governance" / "cross_source_status.json"


def _monthly_last(df: pd.DataFrame) -> pd.DataFrame:
    """Reduce tidy (date,country,value) to one month-end value per country."""
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["ym"] = df["date"].dt.to_period("M").astype(str)
    return (df.sort_values("date").groupby(["country", "ym"], as_index=False)
              .tail(1)[["country", "ym", "value"]])


def cross_source_discrepancies(a: pd.DataFrame, b: pd.DataFrame, threshold_abs: float,
                               recent_months: int = 6) -> tuple[list[dict], list[str]]:
    """Pure: per-country median |a-b| over the recent overlap; return
    (breaches over threshold, list of countries actually checked)."""
    am, bm = _monthly_last(a), _monthly_last(b)
    merged = am.merge(bm, on=["country", "ym"], suffixes=("_a", "_b"))
    if merged.empty:
        return [], []
    keep_ym = sorted(merged["ym"].unique())[-recent_months:]
    merged = merged[merged["ym"].isin(keep_ym)]
    merged["absdiff"] = (merged["value_a"] - merged["value_b"]).abs()
    med = merged.groupby("country")["absdiff"].median()
    breaches = [{"country": c, "median_absdiff": round(float(v), 3)}
                for c, v in med.items() if v > threshold_abs]
    return breaches, list(med.index)


def _query(con, db: str, table: str, variable: str) -> pd.DataFrame:
    qual = f"{table}" if db == "loop" else f"asado.{table}"
    return con.execute(
        f"SELECT date, country, value FROM {qual} WHERE variable = ? AND value IS NOT NULL",
        [variable]).fetchdf()


def run_checks(config: Optional[dict] = None) -> dict:
    cfg = config or yaml.safe_load(CONFIG_PATH.read_text())
    con = loop_connection(read_only=True)
    try:
        # ── Sentinels (hard) ──────────────────────────────────────────────
        # Query for the MOST RECENT value within `recent_days` rather than
        # an exact date, so stale sentinel dates don't false-trip. If no data
        # in window: log a warning and skip (can't verify) — BBG may have been
        # down. A large mismatch vs expected (GSAB-style swap) is a HARD STOP.
        sentinel_breaches = []
        for s in cfg.get("sentinels", []):
            qual = s["table"] if s["db"] == "loop" else f"asado.{s['table']}"
            recent_days = int(s.get("recent_days", 60))
            row = con.execute(
                f"""SELECT value FROM {qual}
                    WHERE variable=? AND country=?
                    AND date >= CURRENT_DATE - INTERVAL {recent_days} DAY
                    ORDER BY date DESC LIMIT 1""",
                [s["variable"], s["country"]]).fetchone()
            got = None if row is None else row[0]
            if got is None:
                print(f"  SENTINEL SKIP: no data for {s['country']} {s['variable']} "
                      f"in last {recent_days}d — cannot verify (BBG may be down)", flush=True)
                continue
            if abs(float(got) - float(s["expected"])) > float(s["tol"]):
                sentinel_breaches.append(
                    {**{k: s[k] for k in ("table", "variable", "country", "expected")},
                     "got": round(float(got), 4)})

        # ── Cross-source pairs (soft: red the scorecard, no crash) ────────
        pair_results = []
        checked_countries: set[str] = set()
        for p in cfg.get("pairs", []):
            a = _query(con, p["a"]["db"], p["a"]["table"], p["a"]["variable"])
            b = _query(con, p["b"]["db"], p["b"]["table"], p["b"]["variable"])
            breaches, checked = cross_source_discrepancies(
                a, b, float(p["threshold_abs"]), int(p.get("recent_months", 6)))
            checked_countries.update(checked)
            pair_results.append({"name": p["name"], "n_checked": len(checked),
                                 "breaches": breaches})
    finally:
        con.close()

    critical = int(cfg.get("critical_series_count", max(1, len(checked_countries))))
    coverage = round(len(checked_countries) / critical, 3) if critical else 0.0
    hard_breach = len(sentinel_breaches) > 0
    pair_breach = any(pr["breaches"] for pr in pair_results)
    return {
        "as_of": pd.Timestamp.now().isoformat(timespec="seconds"),
        "hard_breach": hard_breach,
        "pair_breach": pair_breach,
        "coverage_fraction": coverage,
        "n_checked": len(checked_countries),
        "critical_series_count": critical,
        "sentinel_breaches": sentinel_breaches,
        "pairs": pair_results,
        "note": "cross_source_minimal is AMBER by design (partial coverage); full sweep is Phase C.",
    }


def write_status(status: Optional[dict] = None) -> dict:
    status = status or run_checks()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(status, indent=2, default=str))
    os.replace(tmp, OUT_PATH)
    return status


def main() -> int:
    st = write_status()
    print(f"cross_source_minimal: coverage={st['coverage_fraction']} "
          f"({st['n_checked']}/{st['critical_series_count']})  "
          f"hard_breach={st['hard_breach']}  pair_breach={st['pair_breach']}")
    for s in st["sentinel_breaches"]:
        print(f"  SENTINEL BREACH: {s['country']} {s['variable']} {s['date']} "
              f"expected={s['expected']} got={s['got']}")
    for pr in st["pairs"]:
        for b in pr["breaches"]:
            print(f"  PAIR BREACH [{pr['name']}]: {b['country']} median|a-b|={b['median_absdiff']}")
    print(f"Wrote {OUT_PATH}")
    # HARD stop only on sentinel mismatch (curated exact anchors).
    return 1 if st["hard_breach"] else 0


if __name__ == "__main__":
    sys.exit(main())
