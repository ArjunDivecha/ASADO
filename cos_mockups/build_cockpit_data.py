#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: build_cockpit_data.py
=============================================================================

INPUT FILES (all read-only):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Loop database. Tables read:
      * dislocation_daily        — D1..D10 detector firings (entity, severity=z, components)
      * harness_results          — skeptic-harness verdict summaries
      * harness_ic_series        — per-date rank-IC paths for signal details
      * combiner_scores_daily    — COMBINER_RIDGE_DAILY_V1 cross-sectional score per country
      * country_returns_monthly  — latest monthly return per T2 country (map 'return' layer)
      * thesis_ledger            — open PAPER theses
      * etf_prices_daily + etf_t2_map — best-effort trailing drawdown (tail dots); optional
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/governance/governance_scorecard.json
    The nightly governance scorecard (overall + 7 dimensions).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/dislocations/brief_YYYY_MM_DD.md
    The nightly dislocation brief (latest by filename) — surfaced as a pointer only.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/journal/{drafts,claims,blind_rulings,routing,analog_sets}/*.jsonl
    Discovery Triage Research Desk stores. Missing files render empty states;
    sealed rationales are never read or surfaced.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/cos_mockups/cockpit_data.json
    Single JSON the cockpit UI binds to. Shape documented in build_payload() and
    intended to mirror the panels in cockpit.html / DESIGN_BRIEF.md.

VERSION: 1.0
LAST UPDATED: 2026-06-19
AUTHOR: Arjun Divecha / Claude Code

DESCRIPTION:
Produces the live data payload for the ASADO "Chief of Staff" cockpit by reading
the loop warehouse and governance artifacts, then APPLYING THE SELECTION
INTELLIGENCE described in cos_mockups/DESIGN_BRIEF.md §1 — i.e. the rules that
decide *what the cockpit shows*, not merely how it looks:
  - §1.2 three-slot "Today" promotion (governance exception -> best-standing
          signal-with-caveat -> freshest unpriced country dislocation)
  - §1.4 latest signal runs ordered by NW-t, verdicts owned by the harness,
          registry tally, and real IC series when persisted
  - §1.5 detector firing ranked by |severity|, country vs structural archetypes
  - §1.7 governance overall = worst dimension ("honest, not broken")
Every source is wrapped in try/except so one failure never blanks the payload
(data-resilience). The write is atomic (temp file + rename).

DEPENDENCIES:
- duckdb, pandas (project venv)

USAGE:
  source venv/bin/activate
  python cos_mockups/build_cockpit_data.py            # write cockpit_data.json
  python cos_mockups/build_cockpit_data.py --pretty   # human-readable indent
  python cos_mockups/build_cockpit_data.py --print     # also echo to stdout

NOTES:
- Read-only on every database connection. Safe to run anytime.
- Intended to be re-runnable nightly after the loop job; cheap (<5s).
- Signal IC series come from harness_ic_series. If a run is not backfilled yet,
  that one run is marked missing rather than faked.
=============================================================================
"""

import argparse
import json
import math
import os
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import duckdb

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
DATA_ROOT = Path(os.environ.get("ASADO_DATA_ROOT", BASE_DIR / "Data")).expanduser()
LOOP_DB = DATA_ROOT / "loop" / "asado_loop.duckdb"
GOV_JSON = DATA_ROOT / "loop" / "governance" / "governance_scorecard.json"
DISLO_DIR = DATA_ROOT / "dislocations"
OUT_JSON = BASE_DIR / "cos_mockups" / "cockpit_data.json"

from scripts.discovery_triage.jsonl_store import read_jsonl  # noqa: E402
from scripts.discovery_triage.paths import (  # noqa: E402
    ANALOG_SETS_PATH,
    BLIND_RULINGS_PATH,
    CLAIMS_PATH,
    DETECTOR_DRAFTS_PATH,
    GRAVEYARD_TRACKING_PATH,
    PROSPECTIVE_QUEUE_PATH,
)

# The 34 T2 universe, grouped by region (must match DESIGN_BRIEF / cockpit.html)
REGIONS = [
    ("Americas", ["Canada", "U.S.", "NASDAQ", "US SmallCap", "Mexico", "Brazil", "Chile"]),
    ("Europe", ["U.K.", "France", "Germany", "Netherlands", "Switzerland", "Italy",
                "Spain", "Sweden", "Denmark", "Poland"]),
    ("MEA", ["South Africa", "Saudi Arabia", "Turkey"]),
    ("Asia", ["ChinaA", "ChinaH", "Hong Kong", "Japan", "Korea", "Taiwan", "India",
              "Indonesia", "Malaysia", "Philippines", "Singapore", "Thailand", "Vietnam"]),
    ("Oceania", ["Australia"]),
]
ALL_COUNTRIES = [c for _, cs in REGIONS for c in cs]
ISO = {"Canada": "CAN", "U.S.": "US", "NASDAQ": "NDX", "US SmallCap": "SML", "Mexico": "MEX",
       "Brazil": "BRA", "Chile": "CHL", "U.K.": "UK", "France": "FRA", "Germany": "DEU",
       "Netherlands": "NLD", "Switzerland": "CHE", "Italy": "ITA", "Spain": "ESP",
       "Sweden": "SWE", "Denmark": "DNK", "Poland": "POL", "South Africa": "ZAF",
       "Saudi Arabia": "SAU", "Turkey": "TUR", "ChinaA": "CNA", "ChinaH": "CNH",
       "Hong Kong": "HK", "Japan": "JPN", "Korea": "KOR", "Taiwan": "TWN", "India": "IND",
       "Indonesia": "IDN", "Malaysia": "MYS", "Philippines": "PHL", "Singapore": "SGP",
       "Thailand": "THA", "Vietnam": "VNM", "Australia": "AUS"}

# Detector archetypes that are COUNTRY-level (promotable to a country dislocation)
# vs structural/portfolio detectors that are not single-country tradeable.
STRUCTURAL_DETECTORS = {"D8", "D9", "D10"}  # stewardship, index-vs-ETF basis, etc.
# Families that are diagnostics, not promotable alpha (still shown in the registry).
SANITY_FAMILIES = {"momentum_sanity"}

VERDICT_ORDER = {"WATCH": 0, "WEAK": 1, "INSUFFICIENT_COVERAGE": 2, "DEAD": 3}
SIGNAL_IC_SAMPLE_LIMIT = 140


def _connect():
    return duckdb.connect(str(LOOP_DB), read_only=True)


def _safe(fn, label, default):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 - one source failing must not blank payload
        sys.stderr.write(f"[WARN] {label} failed: {e}\n")
        return default


def _clean_num(value, digits=None):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(out) or math.isinf(out):
        return None
    return round(out, digits) if digits is not None else out


def _json_load(value, default):
    if not value:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _table_exists(con, name):
    return bool(con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = ?",
        [name],
    ).fetchone()[0])


def _date_str(value):
    if value is None:
        return None
    if hasattr(value, "date"):
        value = value.date()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _first_present(row, keys, default=None):
    for key in keys:
        value = row.get(key)
        if value not in (None, "", [], {}):
            return value
    return default


def _epistemic_labels(row):
    labels = []
    for key in ("epistemic_status", "triage_flags"):
        value = row.get(key)
        if isinstance(value, list):
            labels.extend(str(v) for v in value if v)
        elif value:
            labels.append(str(value))
    route = row.get("certification_route") or (row.get("provenance") or {}).get("certification_route")
    if route:
        labels.append(str(route))
    if not labels:
        labels.append("UNVALIDATED")
    return list(dict.fromkeys(labels))


def _route_label(route):
    mapping = {
        "post_cutoff_holdout_testable": "POST-CUTOFF HOLDOUT TESTABLE",
        "prospective_only_unknown_cutoff": "PROSPECTIVE REQUIRED",
        "prospective_only_training_cutoff_contamination": "PRE-CUTOFF MODEL CONTAMINATION POSSIBLE",
        "prospective_only_no_tool_enforced_blindness": "PROSPECTIVE REQUIRED",
        "legacy_unknown": "LEGACY UNKNOWN",
        "retrospective_snooped": "RETROSPECTIVE-SNOOPED",
        "measured_gap_claim_required": "DETERMINISTIC",
    }
    return mapping.get(str(route or ""), str(route or "UNVALIDATED").replace("_", " ").upper())


def _jsonl_cards(path, mapper):
    return [mapper(row) for row in read_jsonl(path)]


def _sample_points(points, limit=SIGNAL_IC_SAMPLE_LIMIT):
    """Evenly sample a long chart path while preserving first and last point."""
    if len(points) <= limit:
        return points
    if limit < 2:
        return points[-limit:]
    n = len(points)
    idx = sorted({round(i * (n - 1) / (limit - 1)) for i in range(limit)})
    return [points[i] for i in idx]


def _read_ic_summary(result_file):
    path = Path(result_file) if result_file else None
    if not path or not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return {}
    out = {}
    for horizon, block in (payload.get("ic") or {}).items():
        out[horizon] = {
            "mean_ic": _clean_num(block.get("mean_ic"), 4),
            "nw_t": _clean_num(block.get("nw_t"), 3),
            "n_dates": int(block.get("n_dates") or 0),
            "pct_positive_years": _clean_num(block.get("pct_positive_years"), 3),
        }
    return out


def _missing_ic_series():
    return {
        "status": "missing",
        "source": "harness_ic_series",
        "horizons": {},
        "note": "IC series has not been backfilled for this harness run.",
    }


def _attach_signal_ic_series(con, rows):
    for row in rows:
        row["ic_series"] = _missing_ic_series()
    if not rows or not _table_exists(con, "harness_ic_series"):
        return rows
    for row in rows:
        result_file = row.get("result_file")
        if not result_file:
            continue
        df = con.execute(
            """
            SELECT horizon, date, ic, n_dates
            FROM harness_ic_series
            WHERE result_file = ?
            ORDER BY horizon, date
            """,
            [result_file],
        ).fetchdf()
        if df.empty:
            continue
        horizons = {}
        for horizon, g in df.groupby("horizon", sort=False):
            points = [
                {"date": _date_str(r.date), "ic": round(float(r.ic), 4)}
                for r in g.itertuples(index=False)
                if r.ic is not None and not (isinstance(r.ic, float) and math.isnan(r.ic))
            ]
            if not points:
                continue
            n_dates = int(g["n_dates"].dropna().iloc[0]) if g["n_dates"].notna().any() else len(points)
            sampled = _sample_points(points)
            horizons[str(horizon)] = {
                "points": sampled,
                "n_dates": n_dates,
                "sampled_points": len(sampled),
                "sampled": len(sampled) < n_dates,
                "latest_date": points[-1]["date"],
                "latest_ic": points[-1]["ic"],
            }
        if horizons:
            row["ic_series"] = {
                "status": "fresh",
                "source": "harness_ic_series",
                "primary_horizon": row.get("horizon"),
                "horizons": horizons,
            }
    return rows


# --------------------------------------------------------------------------- #
# Source readers
# --------------------------------------------------------------------------- #
def read_governance():
    """§1.7 — overall = worst dimension; surface each dim + 'amber_by_design'."""
    with open(GOV_JSON) as f:
        g = json.load(f)
    dims = [{
        "name": d.get("name"),
        "status": d.get("effective", d.get("status")),
        "amber_by_design": bool(d.get("amber_by_design")),
        "detail": d.get("detail", ""),
        "evidence": d.get("evidence", ""),
    } for d in g.get("dimensions", [])]
    return {
        "overall": g.get("overall"),
        "as_of": g.get("as_of"),
        "dimensions": dims,
        "repo_dirty": g.get("repo_dirty"),
    }


def read_signals(con):
    """§1.4 — latest harness run per hypothesis, ordered by verdict then NW-t."""
    df = con.execute(
        """
        WITH ranked AS (
            SELECT hypothesis_id, family_key, run_ts, frequency, verdict,
                   primary_horizon, mean_ic, nw_t, deflated_sharpe, result_file,
                   row_number() OVER (
                       PARTITION BY hypothesis_id
                       ORDER BY run_ts DESC NULLS LAST, result_file DESC NULLS LAST
                   ) AS rn
            FROM harness_results
        )
        SELECT hypothesis_id, family_key, run_ts, frequency, verdict,
               primary_horizon, mean_ic, nw_t, deflated_sharpe, result_file
        FROM ranked
        WHERE rn = 1
        """
    ).fetchdf()
    rows = []
    for r in df.itertuples(index=False):
        rows.append({
            "id": r.hypothesis_id,
            "name": r.family_key,
            "run_ts": r.run_ts,
            "frequency": r.frequency,
            "verdict": r.verdict,
            "horizon": r.primary_horizon,
            "ic": None if r.mean_ic is None or (isinstance(r.mean_ic, float) and math.isnan(r.mean_ic)) else round(float(r.mean_ic), 4),
            "nw_t": None if r.nw_t is None or (isinstance(r.nw_t, float) and math.isnan(r.nw_t)) else round(float(r.nw_t), 2),
            "deflated_sharpe": None if r.deflated_sharpe is None or (isinstance(r.deflated_sharpe, float) and math.isnan(r.deflated_sharpe)) else round(float(r.deflated_sharpe), 3),
            "result_file": r.result_file,
            "ic_horizons": _read_ic_summary(r.result_file),
            "is_sanity": r.family_key in SANITY_FAMILIES,
        })
    rows.sort(key=lambda x: (VERDICT_ORDER.get(x["verdict"], 9), -(x["nw_t"] or -99)))
    rows = _attach_signal_ic_series(con, rows)
    tally = {}
    for x in rows:
        tally[x["verdict"]] = tally.get(x["verdict"], 0) + 1
    return rows, tally


def read_dislocations(con):
    """§1.5 — latest-date firings, country rows ranked by |severity| then freshness."""
    latest = con.execute("SELECT max(date) FROM dislocation_daily").fetchone()[0]
    df = con.execute(
        "SELECT date, dislocation_id, detector, archetype, entity, direction, "
        "severity, components_json, days_active, first_seen, status "
        "FROM dislocation_daily WHERE date = ?", [latest]
    ).fetchdf()
    rows = []
    for r in df.itertuples(index=False):
        reading = ""
        try:
            comp = json.loads(r.components_json) if r.components_json else {}
            reading = comp.get("reading", "")
        except Exception:
            comp = {}
        rows.append({
            "id": r.dislocation_id,
            "detector": r.detector,
            "archetype": r.archetype,
            "entity": r.entity,
            "direction": r.direction,
            "severity": round(float(r.severity), 2) if r.severity is not None else None,
            "abs_severity": abs(float(r.severity)) if r.severity is not None else 0.0,
            "days_active": int(r.days_active) if r.days_active is not None else None,
            "first_seen": r.first_seen,
            "status": r.status,
            "reading": reading,
            "is_country": (r.detector not in STRUCTURAL_DETECTORS) and (r.entity in ISO),
        })
    counts = {}
    for x in rows:
        counts[x["detector"]] = counts.get(x["detector"], 0) + 1
    # country rows, strongest & freshest first
    country_rows = sorted(
        [x for x in rows if x["is_country"]],
        key=lambda x: (-x["abs_severity"], x["days_active"] if x["days_active"] is not None else 999),
    )
    return {"as_of": str(latest), "counts": counts, "rows": rows,
            "country_ranked": country_rows, "total": len(rows)}


def read_combiner(con):
    """Latest cross-sectional combiner score per country (map 'signal' layer)."""
    latest = con.execute("SELECT max(date) FROM combiner_scores_daily").fetchone()[0]
    df = con.execute(
        "SELECT country, value FROM combiner_scores_daily WHERE date = ? ORDER BY value DESC",
        [latest]
    ).fetchdf()
    scores = {row.country: round(float(row.value), 5) for row in df.itertuples(index=False)}
    leaders = [{"country": row.country, "score": round(float(row.value), 5)}
               for row in df.head(5).itertuples(index=False)]
    return {
        "as_of": str(latest),
        "scores": scores,
        "leaders": leaders,
        # Epistemic contract (§1.1): no IC time series exists in the loop DB. Do NOT fabricate.
        "ic_series": None,
        "ic_series_note": "No combiner IC time series is persisted in the loop DB; "
                          "report cross-sectional scores only until one is built.",
    }


def read_returns(con):
    """Latest monthly return per country (map 'return' layer)."""
    latest = con.execute("SELECT max(date) FROM country_returns_monthly").fetchone()[0]
    df = con.execute(
        "SELECT country, return_1m FROM country_returns_monthly WHERE date = ?", [latest]
    ).fetchdf()
    return str(latest), {row.country: round(float(row.return_1m) * 100, 2)
                         for row in df.itertuples(index=False)
                         if row.return_1m is not None and not math.isnan(row.return_1m)}


def read_theses(con):
    """Open PAPER theses for the country-letter chip (§1.8)."""
    df = con.execute(
        "SELECT thesis_id, entity, direction, paper, status, probability, "
        "horizon_days, entry_thesis_text, open_date FROM thesis_ledger "
        "WHERE status = 'open'"
    ).fetchdf()
    out = {}
    for r in df.itertuples(index=False):
        out.setdefault(r.entity, []).append({
            "id": r.thesis_id,
            "direction": r.direction,
            "paper": bool(r.paper),
            "probability": round(float(r.probability), 2) if r.probability is not None else None,
            "horizon_days": int(r.horizon_days) if r.horizon_days is not None else None,
            "thesis": r.entry_thesis_text,
            "open_date": r.open_date,
        })
    return out


def read_countries(con):
    """Per-country fundamentals for the country-letter panel (§1.8).

    Latest value per (country, variable) from the tidy sovereign/valuation tables:
      SOV_10Y_YIELD_PCT, SOV_2Y_YIELD_PCT, SOV_CDS_5Y_BP,
      VAL_CAPE_PCTILE_10Y, VAL_ERP_PCT_PCTILE_10Y.
    2s10s slope is derived (10Y - 2Y).
    """
    wanted = {
        "SOV_10Y_YIELD_PCT": "y10",
        "SOV_2Y_YIELD_PCT": "y2",
        "SOV_CDS_5Y_BP": "cds",
        "VAL_CAPE_PCTILE_10Y": "cape_pctile",
        "VAL_ERP_PCT_PCTILE_10Y": "erp_pctile",
    }
    out = {c: {} for c in ALL_COUNTRIES}
    for tbl, vars_ in [("sovereign_daily", ["SOV_10Y_YIELD_PCT", "SOV_2Y_YIELD_PCT", "SOV_CDS_5Y_BP"]),
                       ("valuation_monthly", ["VAL_CAPE_PCTILE_10Y", "VAL_ERP_PCT_PCTILE_10Y"])]:
        ph = ",".join("?" * len(vars_))
        df = con.execute(
            f"SELECT country, variable, value FROM {tbl} t "
            f"WHERE variable IN ({ph}) AND date = ("
            f"  SELECT max(date) FROM {tbl} x WHERE x.country=t.country AND x.variable=t.variable)",
            vars_
        ).fetchdf()
        for r in df.itertuples(index=False):
            if r.country in out and r.variable in wanted and r.value is not None \
                    and not (isinstance(r.value, float) and math.isnan(r.value)):
                out[r.country][wanted[r.variable]] = round(float(r.value), 3)
    # derive 2s10s slope; drop the raw 2Y helper
    for c, d in out.items():
        if "y10" in d and "y2" in d:
            d["s210"] = round(d["y10"] - d["y2"], 2)
        d.pop("y2", None)
    return {c: d for c, d in out.items() if d}


def read_drawdowns(con):
    """Best-effort trailing-252d drawdown per country for tail dots. Optional."""
    df = con.execute("""
        WITH px AS (
            SELECT m.country AS country, p.date AS date, p.close AS close
            FROM etf_prices_daily p JOIN etf_t2_map m ON p.yf_ticker = m.etf_primary
        ), recent AS (
            SELECT country, date, close,
                   max(close) OVER (PARTITION BY country ORDER BY date
                                    ROWS BETWEEN 251 PRECEDING AND CURRENT ROW) AS peak
            FROM px
        ), latest AS (
            SELECT country, max(date) AS date FROM recent GROUP BY country
        )
        SELECT r.country, round((r.close/r.peak - 1)*100, 1) AS dd
        FROM recent r JOIN latest l ON r.country=l.country AND r.date=l.date
        WHERE r.peak > 0
    """).fetchdf()
    # surface only meaningful drawdowns (< -15%) as tail dots
    return {row.country: float(row.dd) for row in df.itertuples(index=False)
            if row.dd is not None and row.dd < -15}


def _gap_row_from_record(row):
    source_ids = _json_load(row.get("source_dislocation_ids"), [])
    if not isinstance(source_ids, list):
        source_ids = [str(source_ids)]
    return {
        "gap_id": row.get("gap_id"),
        "episode_key": row.get("episode_key"),
        "date": str(row.get("date")) if row.get("date") is not None else None,
        "entity": row.get("entity"),
        "direction": row.get("direction"),
        "gap_class": row.get("gap_class"),
        "horizon_bucket": row.get("horizon_bucket"),
        "status": row.get("status"),
        "preferred_ticker": row.get("preferred_ticker"),
        "proxy_type": row.get("proxy_type"),
        "currency_basis": row.get("currency_basis"),
        "liquidity_tier": row.get("liquidity_tier"),
        "expense_ratio_bps": _clean_num(row.get("expense_ratio_bps"), 1),
        "dollar_adv_21d": _clean_num(row.get("dollar_adv_21d"), 0),
        "expression_quality": _clean_num(row.get("expression_quality"), 3),
        "tension_score_current": _clean_num(row.get("tension_score_current"), 3),
        "tension_score_at_open": _clean_num(row.get("tension_score_at_open"), 3),
        "absorption_state": row.get("absorption_state"),
        "price_absorption_index": _clean_num(row.get("price_absorption_index"), 3),
        "unabsorbed_fraction": _clean_num(row.get("unabsorbed_fraction"), 3),
        "expected_move": _clean_num(row.get("expected_move"), 4),
        "realized_move": _clean_num(row.get("realized_move"), 4),
        "expected_move_source": row.get("expected_move_source"),
        "realized_etf_return": _clean_num(row.get("realized_etf_return"), 4),
        "realized_country_return": _clean_num(row.get("realized_country_return"), 4),
        "days_active": int(row["days_active"]) if row.get("days_active") is not None else None,
        "mechanism_text": row.get("mechanism_text"),
        "invalidation_rule": row.get("invalidation_rule"),
        "world_state": _json_load(row.get("world_state_json"), {}),
        "price_state": _json_load(row.get("price_state_json"), {}),
        "source_dislocation_ids": source_ids,
        "source_freshness": _json_load(row.get("source_freshness_json"), {}),
        "scoring_config_version": row.get("scoring_config_version"),
        "scoring_config_hash": row.get("scoring_config_hash"),
        "epistemic_tag": "INFERENCE",
        "notes": ["Absorption is provisional until the registered horizon completes."],
    }


def _diversified_gap_rows(rows, limit=5):
    """Attention list: strongest first, then best other gap classes, then fill by score."""
    if not rows or limit <= 0:
        return []
    selected = []
    selected_ids = set()
    seen_classes = set()

    def add(row):
        gid = row.get("gap_id")
        if not gid or gid in selected_ids or len(selected) >= limit:
            return False
        selected.append(row)
        selected_ids.add(gid)
        seen_classes.add(row.get("gap_class"))
        return True

    add(rows[0])
    for row in rows[1:]:
        if row.get("gap_class") not in seen_classes:
            add(row)
        if len(selected) >= limit:
            return selected
    for row in rows:
        add(row)
        if len(selected) >= limit:
            return selected
    return selected


def read_gap_engine(con):
    """Primary price-discovery gap read model for Today, map, and country detail."""
    required = {
        "price_state_daily",
        "price_state_surface",
        "gap_episodes",
        "gap_episode_marks",
        "gap_episode_expression",
        "gap_holdout_daily",
    }
    missing = sorted(t for t in required if not _table_exists(con, t))
    if missing:
        return {"status": "missing", "as_of": None, "missing_tables": missing,
                "top": [], "by_country": {}, "counts": {}, "holdout": {}, "staleness": {}}

    latest_mark = con.execute("SELECT max(date) FROM gap_episode_marks").fetchone()[0]
    if latest_mark is None:
        return {"status": "empty", "as_of": None, "top": [], "by_country": {},
                "counts": {}, "holdout": {}, "staleness": {}}

    latest_dislo = None
    if _table_exists(con, "dislocation_daily"):
        latest_dislo = con.execute("SELECT max(date) FROM dislocation_daily").fetchone()[0]

    df = con.execute("""
        WITH expr AS (
            SELECT *
            FROM gap_episode_expression
            WHERE COALESCE(is_primary, TRUE)
        )
        SELECT
            m.gap_id,
            m.date,
            m.mark_window,
            m.entity,
            COALESCE(e.direction, 'unknown') AS direction,
            COALESCE(e.gap_class, 'unknown') AS gap_class,
            e.horizon_bucket,
            COALESCE(e.status, 'open') AS status,
            m.preferred_ticker,
            COALESCE(e.proxy_type, x.proxy_type) AS proxy_type,
            COALESCE(e.currency_basis, x.currency_basis) AS currency_basis,
            COALESCE(x.liquidity_tier, e.liquidity_tier_at_open) AS liquidity_tier,
            x.expense_ratio_bps,
            x.dollar_adv_21d,
            COALESCE(m.expression_quality_current, x.expression_quality, e.expression_quality_at_open) AS expression_quality,
            m.tension_score_current,
            e.tension_score_at_open,
            m.absorption_state,
            m.price_absorption_index,
            m.unabsorbed_fraction,
            m.expected_move,
            m.realized_move,
            m.expected_move_source,
            m.realized_etf_return,
            m.realized_country_return,
            m.days_active,
            e.episode_key,
            e.mechanism_text,
            e.invalidation_rule,
            e.world_state_json,
            e.price_state_json,
            e.source_dislocation_ids,
            m.source_freshness_json,
            e.scoring_config_version,
            e.scoring_config_hash
        FROM gap_episode_marks m
        LEFT JOIN gap_episodes e ON m.gap_id = e.gap_id
        LEFT JOIN expr x ON m.gap_id = x.gap_id
        WHERE m.date = ?
        ORDER BY
            CASE WHEN COALESCE(e.status, 'open') = 'open' THEN 0 ELSE 1 END,
            m.tension_score_current DESC NULLS LAST,
            m.days_active ASC NULLS LAST,
            COALESCE(m.expression_quality_current, x.expression_quality, e.expression_quality_at_open) DESC NULLS LAST
    """, [latest_mark]).fetchdf()

    rows = [_gap_row_from_record(r._asdict()) for r in df.itertuples(index=False)]
    open_rows = [r for r in rows if r.get("status") == "open"]
    eligible_rows = open_rows or rows
    raw_top = eligible_rows[:5]
    top = _diversified_gap_rows(eligible_rows, 5)

    by_country = {}
    for row in rows:
        entity = row.get("entity")
        if not entity:
            continue
        bucket = by_country.setdefault(entity, {"primary": None, "all": []})
        bucket["all"].append(row)
        if bucket["primary"] is None and row.get("status") == "open":
            bucket["primary"] = row
    for bucket in by_country.values():
        if bucket["primary"] is None and bucket["all"]:
            bucket["primary"] = bucket["all"][0]

    counts = {"open": len(open_rows), "marked_today": len(rows),
              "by_class": {}, "by_direction": {}, "by_absorption": {}}
    for row in rows:
        for key, field in [("by_class", "gap_class"), ("by_direction", "direction"),
                           ("by_absorption", "absorption_state")]:
            val = row.get(field) or "unknown"
            counts[key][val] = counts[key].get(val, 0) + 1

    holdout = {}
    try:
        h = con.execute("""
            SELECT
                COUNT(*) AS rows,
                SUM(CASE WHEN promoted THEN 1 ELSE 0 END) AS promoted,
                SUM(CASE WHEN eligible AND NOT promoted THEN 1 ELSE 0 END) AS eligible_unpromoted,
                MAX(date) AS as_of
            FROM gap_holdout_daily
        """).fetchone()
        holdout = {
            "rows": int(h[0] or 0),
            "promoted": int(h[1] or 0),
            "eligible_unpromoted": int(h[2] or 0),
            "as_of": str(h[3]) if h[3] is not None else None,
            "note": "Forward holdout is accumulating; backfill is a plumbing smoke test.",
        }
    except Exception:
        holdout = {"note": "Holdout summary unavailable."}

    status = "fresh"
    if latest_dislo is not None and str(latest_mark) < str(latest_dislo):
        status = "stale"

    return {
        "status": status,
        "as_of": str(latest_mark),
        "config_version": top[0].get("scoring_config_version") if top else None,
        "config_hash": top[0].get("scoring_config_hash") if top else None,
        "top": top,
        "raw_top": raw_top,
        "selection_note": "top is class-diversified for cockpit attention; raw_top preserves pure tension ranking.",
        "by_country": by_country,
        "counts": counts,
        "holdout": holdout,
        "staleness": {
            "latest_gap_mark": str(latest_mark) if latest_mark is not None else None,
            "latest_dislocation": str(latest_dislo) if latest_dislo is not None else None,
        },
    }


def latest_brief():
    briefs = sorted(DISLO_DIR.glob("brief_*.md"))
    if not briefs:
        return None
    b = briefs[-1]
    return {"file": str(b), "name": b.name}


# --------------------------------------------------------------------------- #
# §1.2 — the three-slot "Today" promotion rule
# --------------------------------------------------------------------------- #
def build_today(gov, signals, dislo, gap_engine=None):
    slots = []

    # Slot 1 — governance exception first (if not all green).
    if gov.get("overall") and gov["overall"].lower() != "green":
        amber = [d for d in gov["dimensions"] if d["status"] and d["status"].lower() != "green"]
        by_design = [d for d in amber if d["amber_by_design"]]
        lead = (by_design or amber or [{}])[0]
        honest = " — honest, not broken" if (by_design and len(amber) == len(by_design)) else ""
        slots.append({
            "kind": "governance",
            "headline": f"Governance is {gov['overall'].upper()}{honest}",
            "why": f"{lead.get('name','a dimension')}: {lead.get('detail','')}".strip(": "),
            "source": "governance_scorecard.json",
            "route": {"view": "health"},
        })

    # Slot 2 — best-standing signal (top non-sanity WATCH by NW-t), stated with caveat.
    promotable = [s for s in signals if s["verdict"] == "WATCH" and not s["is_sanity"]]
    if promotable:
        s = max(promotable, key=lambda x: x["nw_t"] or -99)
        slots.append({
            "kind": "signal",
            "headline": f"Best-standing signal: {s['name']}",
            "why": f"WATCH · IC {s['ic']} · NW-t {s['nw_t']} ({s['horizon']}). "
                   f"A standing read, not a champion — deflated Sharpe still unproven.",
            "source": "harness_results",
            "route": {"view": "signal", "name": s["name"], "id": s["id"]},
        })

    # Slot 3 — top price-discovery gap when fresh; raw dislocation is fallback only.
    gap_engine = gap_engine or {}
    if gap_engine.get("status") == "fresh" and gap_engine.get("top"):
        g = gap_engine["top"][0]
        ticker = f" via {g['preferred_ticker']}" if g.get("preferred_ticker") else ""
        unabsorbed = g.get("unabsorbed_fraction")
        unabsorbed_txt = f" · {round(unabsorbed * 100)}% unabsorbed" if unabsorbed is not None else ""
        slots.append({
            "kind": "gap",
            "headline": f"{g['entity']} {g['direction']} gap{ticker}",
            "why": f"{g.get('gap_class','gap')} · {g.get('absorption_state','unknown')}"
                   f"{unabsorbed_txt} · {g.get('horizon_bucket') or 'horizon unknown'}. "
                   f"{g.get('mechanism_text') or 'World-state and price-state tension remains open.'}",
            "source": f"gap_episode_marks · {gap_engine.get('as_of')}",
            "route": {"view": "gap", "gap_id": g["gap_id"], "name": g.get("entity")},
        })
    elif dislo["country_ranked"]:
        d = dislo["country_ranked"][0]
        prefix = "Gap engine unavailable; fallback raw dislocation"
        if gap_engine.get("status") in {"stale", "missing", "empty"}:
            prefix = f"Gap engine {gap_engine.get('status')}; fallback raw dislocation"
        slots.append({
            "kind": "dislocation",
            "headline": f"Fresh {d['detector']} · {d['entity']}",
            "why": f"{prefix}: {d['reading'] or d['archetype']} (severity {d['severity']}σ, "
                   f"{d['days_active']}d active).",
            "source": f"brief · {dislo['as_of']}",
            "route": {"view": "country", "name": d["entity"]},
        })

    return slots[:3]


# --------------------------------------------------------------------------- #
# Research Desk readers (journal JSONL only; no sealed rationales)
def read_discovery_lab():
    def map_row(row):
        route = row.get("certification_route")
        return {
            "id": row.get("draft_id"),
            "kind": "detector_draft",
            "title": row.get("family_name") or row.get("draft_id"),
            "subtitle": f"{len(row.get('members') or [])} proposed members",
            "source": row.get("source_look_id"),
            "status": "UNVALIDATED",
            "route": route,
            "route_label": _route_label(route),
            "labels": _epistemic_labels(row),
            "recorded_ts": row.get("recorded_ts"),
            # members may be plain strings (Claude lab) or objects (Codex lab); the
            # cockpit memberList reads .proposed_relationship, so wrap bare strings.
            "members": [m if isinstance(m, dict) else {"proposed_relationship": m}
                        for m in (row.get("members") or [])],
            "falsification": row.get("falsification") or {},
            "self_falsification": row.get("mythos_self_falsification") or {},
        }

    rows = _jsonl_cards(DETECTOR_DRAFTS_PATH, map_row)
    rows.sort(key=lambda r: str(r.get("recorded_ts") or r.get("id") or ""), reverse=True)
    return rows


def read_analog_shelf():
    def map_row(row):
        return {
            "id": row.get("set_id"),
            "kind": "analog_set",
            "title": f"{row.get('query_country')} analogs",
            "subtitle": f"{row.get('metric_id')} · {len(row.get('members') or [])} members",
            "status": "FROZEN OUTCOME-BLIND",
            "route": "analog_shelf",
            "route_label": "OUTCOME-BLIND ANALOG SET",
            "labels": ["OUTCOME-BLIND", "FROZEN MEMBERSHIP"],
            "recorded_ts": row.get("recorded_ts") or row.get("set_frozen_at"),
            "as_of": row.get("as_of"),
            "metric_id": row.get("metric_id"),
            "query_country": row.get("query_country"),
            "members": row.get("members") or [],
            "surfaces_seen": row.get("surfaces_seen") or [],
        }

    rows = _jsonl_cards(ANALOG_SETS_PATH, map_row)
    rows.sort(key=lambda r: str(r.get("recorded_ts") or r.get("id") or ""), reverse=True)
    return rows


def read_under_triage():
    def map_row(row):
        route = (row.get("provenance") or {}).get("certification_route")
        status = row.get("court_status") or row.get("harness_verdict") or "frozen_not_validated"
        return {
            "id": row.get("claim_id"),
            "kind": "claim",
            "title": ((row.get("neutral_claim") or {}).get("sentence") or row.get("claim_id")),
            "subtitle": f"{status} · {row.get('harness_verdict') or 'no harness verdict'}",
            "status": str(status).replace("_", " ").upper(),
            "route": route,
            "route_label": _route_label(route),
            "labels": _epistemic_labels(row),
            "recorded_ts": row.get("recorded_ts"),
            "target": row.get("target") or {},
            "expression": row.get("expression") or {},
            "triage_flags": row.get("triage_flags") or [],
        }

    rows = _jsonl_cards(CLAIMS_PATH, map_row)
    rows.sort(key=lambda r: str(r.get("recorded_ts") or r.get("id") or ""), reverse=True)
    return rows


def read_blind_rulings():
    def map_row(row):
        ruling = row.get("blind_ruling") or {}
        decision = _first_present(ruling, ["decision", "preliminary_decision"], "unknown")
        return {
            "id": row.get("ruling_id"),
            "kind": "blind_ruling",
            "title": f"{row.get('claim_id')} · {decision}",
            "subtitle": f"judge {row.get('judge') or 'unknown'}",
            "status": str(decision).replace("_", " ").upper(),
            "route": "blind_ruling",
            "route_label": "BLIND RULING",
            "labels": ["BLIND PACKET ONLY"],
            "recorded_ts": row.get("recorded_ts"),
            "claim_id": row.get("claim_id"),
            "ruling_changed_after_unseal": row.get("ruling_changed_after_unseal"),
            "unseal": row.get("unseal") or {},
        }

    rows = _jsonl_cards(BLIND_RULINGS_PATH, map_row)
    rows.sort(key=lambda r: str(r.get("recorded_ts") or r.get("id") or ""), reverse=True)
    return rows


def read_prospective():
    def map_row(row):
        return {
            "id": row.get("claim_id"),
            "kind": "incubator_entry",
            "title": row.get("claim_id"),
            "subtitle": f"{row.get('measurement_shape')} · {row.get('expected_readouts') or []}",
            "status": str(row.get("status") or "forward_incubating").replace("_", " ").upper(),
            "route": "prospective_queue",
            "route_label": "PROSPECTIVE REQUIRED",
            "labels": ["FORWARD INCUBATING"],
            "recorded_ts": row.get("recorded_ts"),
            "start_date": row.get("start_date"),
            "first_readout_date": row.get("first_readout_date"),
            "full_readout_date": row.get("full_readout_date"),
            "return_surface": row.get("return_surface"),
            "target_country": row.get("target_country"),
        }

    rows = _jsonl_cards(PROSPECTIVE_QUEUE_PATH, map_row)
    rows.sort(key=lambda r: str(r.get("recorded_ts") or r.get("id") or ""), reverse=True)
    return rows


def read_graveyard():
    def map_row(row):
        return {
            "id": row.get("claim_id"),
            "kind": "graveyard_entry",
            "title": row.get("claim_id"),
            "subtitle": row.get("reason_for_tracking") or row.get("terminal_or_quarantine_status"),
            "status": str(row.get("terminal_or_quarantine_status") or "graveyard").replace("_", " ").upper(),
            "route": "graveyard_control",
            "route_label": "GRAVEYARD CONTROL ARM",
            "labels": ["CONTROL ARM", "FORWARD TRACKED"],
            "recorded_ts": row.get("recorded_ts"),
            "start_date": row.get("start_date"),
            "expected_readouts": row.get("expected_readouts") or [],
            "return_surface": row.get("return_surface"),
            "target_country": row.get("target_country"),
        }

    rows = _jsonl_cards(GRAVEYARD_TRACKING_PATH, map_row)
    rows.sort(key=lambda r: str(r.get("recorded_ts") or r.get("id") or ""), reverse=True)
    return rows


def read_research_desk():
    return {
        "discovery_lab": _safe(read_discovery_lab, "research_desk.discovery_lab", []),
        "analog_shelf": _safe(read_analog_shelf, "research_desk.analog_shelf", []),
        "under_triage": _safe(read_under_triage, "research_desk.under_triage", []),
        "blind_rulings": _safe(read_blind_rulings, "research_desk.blind_rulings", []),
        "prospective": _safe(read_prospective, "research_desk.prospective", []),
        "graveyard": _safe(read_graveyard, "research_desk.graveyard", []),
    }


# --------------------------------------------------------------------------- #
def build_map(returns_map, dislo, combiner, drawdowns, gap_engine=None):
    dislo_entities = {x["entity"]: x for x in dislo["country_ranked"]}
    gap_by_country = (gap_engine or {}).get("by_country", {})
    regions = []
    for reg, cs in REGIONS:
        tiles = []
        for c in cs:
            d = dislo_entities.get(c)
            g = (gap_by_country.get(c) or {}).get("primary")
            tiles.append({
                "country": c,
                "iso": ISO.get(c, c[:3].upper()),
                "return": returns_map.get(c),
                "dislocation": (f"{d['detector']} {d['direction']} {d['severity']}σ" if d else None),
                "combiner": combiner["scores"].get(c),
                "drawdown": drawdowns.get(c),
                "gap": (f"{g['gap_class']} {g['direction']} {g.get('preferred_ticker') or ''} "
                        f"{g.get('absorption_state') or ''}".strip() if g else None),
                "gap_id": g.get("gap_id") if g else None,
                "gap_direction": g.get("direction") if g else None,
                "gap_tension": g.get("tension_score_current") if g else None,
                "gap_absorption": g.get("absorption_state") if g else None,
                "gap_ticker": g.get("preferred_ticker") if g else None,
            })
        regions.append({"region": reg, "tiles": tiles})
    return regions


def build_payload():
    payload = {
        "meta": {
            "generated_ts": datetime.now().isoformat(timespec="seconds"),
            "generator": "cos_mockups/build_cockpit_data.py 1.0",
            "epistemic_contract": "FACT cited · INFERENCE labelled · UNKNOWN/STALE aloud · "
                                  "nothing is a trade until the harness clears it",
        }
    }

    gov = _safe(read_governance, "governance", {"overall": None, "dimensions": []})
    payload["governance"] = gov
    payload["research_desk"] = read_research_desk()

    con = _safe(_connect, "loop_db_connect", None)
    if con is None:
        payload["error"] = "loop DB unavailable"
        return payload

    signals, tally = _safe(lambda: read_signals(con), "signals", ([], {}))
    payload["signals"] = {"registry": signals, "tally": tally}

    dislo = _safe(lambda: read_dislocations(con), "dislocations",
                  {"as_of": None, "counts": {}, "rows": [], "country_ranked": [], "total": 0})
    payload["dislocations"] = dislo

    gap_engine = _safe(lambda: read_gap_engine(con), "gap_engine",
                       {"status": "missing", "as_of": None, "top": [], "by_country": {},
                        "counts": {}, "holdout": {}, "staleness": {}})
    payload["gap_engine"] = gap_engine

    combiner = _safe(lambda: read_combiner(con), "combiner",
                     {"as_of": None, "scores": {}, "leaders": [], "ic_series": None})
    payload["combiner"] = combiner

    ret_asof, returns_map = _safe(lambda: read_returns(con), "returns", (None, {}))
    payload["returns"] = {"as_of": ret_asof, "by_country": returns_map}

    theses = _safe(lambda: read_theses(con), "theses", {})
    payload["theses"] = theses

    payload["countries"] = _safe(lambda: read_countries(con), "countries", {})

    drawdowns = _safe(lambda: read_drawdowns(con), "drawdowns", {})
    payload["drawdowns"] = drawdowns

    payload["brief"] = _safe(latest_brief, "brief", None)

    payload["map"] = build_map(returns_map, dislo, combiner, drawdowns, gap_engine)
    payload["today"] = build_today(gov, signals, dislo, gap_engine)

    con.close()
    return payload


def atomic_write(path: Path, data: dict, pretty: bool):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2 if pretty else None, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def main():
    ap = argparse.ArgumentParser(description="Build cockpit_data.json from the loop warehouse")
    ap.add_argument("--pretty", action="store_true", help="indent the JSON")
    ap.add_argument("--print", dest="echo", action="store_true", help="echo payload to stdout")
    args = ap.parse_args()

    payload = build_payload()
    atomic_write(OUT_JSON, payload, pretty=True)  # always pretty on disk for diffability

    # Also emit a JS global so cockpit_live.html can load via <script src> (no file:// CORS).
    js_path = OUT_JSON.with_suffix(".js")
    js_path.write_text("window.COCKPIT_DATA = " + json.dumps(payload, ensure_ascii=False) + ";\n")

    today = payload.get("today", [])
    print(f"[OK] wrote {OUT_JSON}")
    print(f"     governance={payload.get('governance',{}).get('overall')} | "
          f"signals={len(payload.get('signals',{}).get('registry',[]))} "
          f"({payload.get('signals',{}).get('tally',{})}) | "
          f"dislocations={payload.get('dislocations',{}).get('total')} "
          f"as-of {payload.get('dislocations',{}).get('as_of')} | "
          f"gaps={payload.get('gap_engine',{}).get('status')} "
          f"top={len(payload.get('gap_engine',{}).get('top',[]))}")
    print("     Today's three slots:")
    for i, s in enumerate(today, 1):
        print(f"       {i}. [{s['kind']}] {s['headline']} — {s['why'][:70]}")
    if args.echo:
        print(json.dumps(payload, indent=2 if args.pretty else None))


if __name__ == "__main__":
    main()
