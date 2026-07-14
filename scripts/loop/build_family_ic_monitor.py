#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: build_family_ic_monitor.py
=============================================================================

WHAT THIS PROGRAM DOES (for someone with zero prior context)
-------------------------------------------------------------
This is the ASADO "family-IC monitor". A research *family* is a group of
related signals (e.g. `network_spillover` = the graph / lead-lag / similarity
spillover signals). The single most important number for a family is its
*Information Coefficient* (IC): the cross-sectional rank correlation between
what the signal said yesterday and what country returns actually did. When a
family's IC decays, the family is dying; when it turns positive again, the
family may be worth re-arming.

Before this monitor existed, family IC was only ever computed on demand by the
skeptic harness. The `network_spillover` family's IC went negative in ~April
2024 and NOBODY MEASURED IT for ~15 months (documented in
experiments/2026_07_flip_autopsy/results/RESULTS.md). This program fixes that.
Every night it:

  1. Recomputes each monitored family's monthly IC using the SAME "honest
     clock" the skeptic harness uses (harness v4: a daily signal seen at day
     t's close cannot predict the return that opens at that same close, so the
     forward-return window opens strictly AFTER the signal date; monthly
     signals get their publication embargo). The alignment/IC helpers are
     IMPORTED from scripts/harness/evaluate_signal.py -- never reimplemented --
     so the monitor and the harness can never silently disagree.
  2. Upserts one row per (family, roster, month) into a DURABLE loop-DB table
     (`family_ic_nightly`) -- never the main warehouse, which is destroyed on
     every monthly rebuild.
  3. Runs the "R-A price gate" state machine per family on its GATE roster: a
     family is `parked` until it prints two CONSECUTIVE positive family-IC
     month-ends, at which point it `re-arms`; any non-positive month-end (<= 0,
     incl. exactly zero) or a calendar gap resets the consecutive counter (and
     re-parks a re-armed family). Transitions are recorded with evidence months.
  4. Writes a small status artifact the nightly brief / Alpha Book can read.

The monitor MEASURES; it never verdicts. It cannot promote or kill a signal --
only the skeptic harness assigns verdicts.

ROSTERS (AUTHOR AMENDMENT 1, 2026-07-14)
----------------------------------------
Each family carries one or more named *rosters*, persisted in the table's
`roster` column so a family's monitored series is CONTINUOUS and changes only
on a deliberate re-issue -- never on every live re-verdict. Two roles:
  * role='gate' -- the Alpha Book v2 WATCH-tier members frozen at Book
    publication (`book_2026_07_14`). This is the series the R-A gate runs on
    and the status artifact reports.
  * role='inv4_reference' -- a6's exact frozen 16-member roster
    (`ref16_frozen`, network_spillover only), used ONLY for the INV4
    known-answer backfill comparison.
Rosters are read from the committed data file
`scripts/loop/family_ic_roster_v1.json`.

INPUT FILES (all absolute paths)
--------------------------------
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/scripts/loop/family_ic_roster_v1.json
    Frozen family rosters (members, tables, sources, directions, universes).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    The DURABLE loop DB. READ: member signal tables (graph_features_daily,
    graph_features_pit_daily, leadlag_features_daily, similarity_features_daily,
    combiner_scores_daily, eco_surprise_signals) and country_returns_monthly.
    WRITE: the monitor's own table `family_ic_nightly` (upsert). Opened through
    scripts.loop.loopdb.loop_connection() -> scripts.duckdb_lock_guard.guarded_connect().
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
    Main warehouse, attached READ-ONLY as `asado` by loop_connection(); read
    indirectly via loopdb.daily_country_returns (asado.t2_factors_daily) for the
    daily marking returns. NEVER written.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/a6_lag1_family_ic.json
    INV4 per-year + pre/post lag-1 known-answer reference (backfill only).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/a2_family_ic_monthly_recomputed.parquet
    INV4 monthly correlation reference (backfill only).

OUTPUT FILES (all absolute paths)
---------------------------------
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `family_ic_nightly` (one row per family per roster per month; upsert).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/loop/family_ic_status.json
    Per-family gate state + latest IC (atomic temp-then-rename write).

The monitor writes ONLY those two surfaces. It never writes ledgers/, config/,
Data/processed/, the main warehouse, or any experiment directory (INV6).

VERSION: 1.1
LAST UPDATED: 2026-07-14 (AUTHOR AMENDMENT 1: two-roster model; amended INV4)
AUTHOR: Arjun Divecha (built by agent session, contract FAMILY-IC-MONITOR-001)

DEPENDENCIES: duckdb, pandas, numpy, scipy, pyyaml (project venv). Imports the
harness alignment helpers from scripts/harness/evaluate_signal.py (read-only).

USAGE:
  python scripts/loop/build_family_ic_monitor.py               # nightly step (default)
  python scripts/loop/build_family_ic_monitor.py --backfill     # full history + INV4 (G3)
  python scripts/loop/build_family_ic_monitor.py --verify-idempotent  # run twice, assert idempotent (G4)
  python scripts/loop/build_family_ic_monitor.py --status       # print status JSON
  python scripts/loop/build_family_ic_monitor.py --dry-run      # validate wiring, no DB
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Honest-clock helpers imported from the harness (NEVER reimplemented -- INV1).
from scripts.harness.evaluate_signal import (  # noqa: E402
    HARNESS_VERSION,
    align_daily,
    align_monthly,
    effective_daily_lag_days,
    infer_publication_lag,
    rank_ic_series,
)
from scripts.loop.loopdb import (  # noqa: E402
    LOOP_DIR,
    LOOP_DB,
    daily_country_returns,
    loop_connection,
)

_log = logging.getLogger("family_ic_monitor")

# ─────────────────────────────────────────────────────────────────────────────
# Paths & constants
# ─────────────────────────────────────────────────────────────────────────────
ROSTER_PATH = Path(__file__).resolve().parent / "family_ic_roster_v1.json"
WORK_LOOP_DIR = BASE_DIR / "Data" / "work" / "loop"
STATUS_PATH = WORK_LOOP_DIR / "family_ic_status.json"

MONITOR_TABLE = "family_ic_nightly"

# INV4 known-answer references (backfill only).
FLIP_RESULTS = BASE_DIR / "experiments" / "2026_07_flip_autopsy" / "results"
A6_REF_PATH = FLIP_RESULTS / "a6_lag1_family_ic.json"
A2_REF_PATH = FLIP_RESULTS / "a2_family_ic_monthly_recomputed.parquet"

# INV4 thresholds (AUTHOR AMENDMENT 1, 2026-07-14). The a6 GENERATING SCRIPT was
# never committed (only its JSON output, commit cdcd9a4), so the original
# +/-0.005 per-year clause was unachievable from a faithful reconstruction.
# Amended to measured independent-reconstruction noise. All four clauses bind:
#   (i)   monthly corr >= INV4_MIN_CORR vs the committed a2 monthly series
#   (ii)  per-year means within INV4_PER_YEAR_TOL of a6
#   (iii) pre-2024 (2012-2023) mean within INV4_PRE_MEAN_TOL of a6's lag1_pre_mean
#   (iv)  post-2024 (>= 2024) mean < 0 (the flip must reproduce)
# Kept as named, adjustable module constants; the backfill prints the full
# per-year table regardless. See docs/family_ic_monitor_notes.md.
INV4_MIN_CORR = 0.95
INV4_PER_YEAR_TOL = 0.012
INV4_PRE_MEAN_TOL = 0.001
INV4_PRE_WINDOW = ("2012-01-01", "2024-01-01")   # [start, end) for the pre-2024 mean
INV4_POST_START = "2024-01-01"

# R-A price gate: consecutive positive family-IC month-ends required to re-arm.
GATE_REARM_CONSECUTIVE = 2

# The (family, roster) whose backfill is checked against the a6/a2 known-answer.
KNOWN_ANSWER_FAMILY = "network_spillover"
KNOWN_ANSWER_ROSTER = "ref16_frozen"
# AUTHOR AMENDMENT 3 (2026-07-14): the contract's authored expectation was
# parked/0 as of 2026-06, written from H1-average intuition. The backfilled
# data shows June 2026 was genuinely POSITIVE for the book roster (+0.093
# after May -0.137), so the true state is parked/1. The gate machine was
# right; the expectation was wrong. Verified against family_ic_nightly rows.
KNOWN_ANSWER_EXPECTED_CONSECUTIVE = 1


# Trailing months the nightly step recomputes/upserts (history is stable; only
# the recent tail moves as returns extend).
NIGHTLY_MONTHS_BACK = 18


# ─────────────────────────────────────────────────────────────────────────────
# Roster
# ─────────────────────────────────────────────────────────────────────────────
def load_roster(path: Path = ROSTER_PATH) -> dict[str, Any]:
    data = json.loads(Path(path).read_text())
    if "families" not in data:
        raise ValueError(f"{path} missing 'families'")
    return data


def monitored_families(roster: Optional[dict] = None) -> dict[str, Any]:
    return (roster or load_roster())["families"]


def gate_roster_name(family_spec: dict[str, Any]) -> str:
    """The roster the R-A gate runs on (role == 'gate'); falls back to the first."""
    for name, r in family_spec["rosters"].items():
        if r.get("role") == "gate":
            return name
    return next(iter(family_spec["rosters"]))


def _family_horizon(family_spec: dict[str, Any]) -> int:
    return int(family_spec["horizon_days"] if family_spec["frequency"] == "daily"
               else family_spec["horizon_months"])


def _family_horizon_label(family_spec: dict[str, Any]) -> str:
    if family_spec["frequency"] == "daily":
        return f"{int(family_spec['horizon_days'])}d"
    return f"{int(family_spec['horizon_months'])}m"


# ─────────────────────────────────────────────────────────────────────────────
# Pure computational core (no I/O; unit-testable)
# ─────────────────────────────────────────────────────────────────────────────
def _sign(direction: str) -> float:
    return 1.0 if direction == "higher_is_better" else -1.0


def member_daily_ic(signal: pd.DataFrame, returns_daily: pd.DataFrame, horizon_days: int,
                    direction: str, source: Optional[str], variable: str,
                    registry: Optional[dict] = None) -> pd.Series:
    """Per-date, sign-aligned cross-sectional rank IC of ONE daily member, on
    the harness-v4 honest clock (effective lag >= 1 for every daily source,
    INV1). Imported align/IC helpers -- never reimplemented."""
    lag = effective_daily_lag_days(variable, source or "", {}, registry)
    aligned = align_daily(signal, returns_daily, horizon_days, lag)
    ic = rank_ic_series(aligned)
    return (_sign(direction) * ic) if len(ic) else ic


def member_monthly_ic(signal: pd.DataFrame, returns_monthly: pd.DataFrame, horizon_months: int,
                      direction: str, source: Optional[str], variable: str,
                      lag_months: Optional[int] = None) -> pd.Series:
    """Per-month, sign-aligned rank IC of ONE monthly member (align_monthly
    publication embargo)."""
    lag = lag_months if lag_months is not None else infer_publication_lag(signal, source or "", "monthly")
    aligned = align_monthly(signal, returns_monthly, lag, horizon_months)
    ic = rank_ic_series(aligned)
    return (_sign(direction) * ic) if len(ic) else ic


def _to_month_start(ts_like) -> pd.DatetimeIndex:
    return pd.to_datetime(pd.Index(ts_like)).to_period("M").to_timestamp()


def _monthly_from_daily(ic_daily: pd.Series) -> pd.Series:
    if ic_daily is None or len(ic_daily) == 0:
        return pd.Series(dtype=float)
    return ic_daily.groupby(_to_month_start(ic_daily.index)).mean().sort_index()


def roster_monthly_ic(frequency: str, horizon: int, members: list[dict[str, Any]],
                      member_signals: dict[str, pd.DataFrame],
                      returns_daily: Optional[pd.DataFrame],
                      returns_monthly: Optional[pd.DataFrame],
                      registry: Optional[dict] = None) -> tuple[pd.Series, pd.Series]:
    """Roster monthly IC = equal-weight mean, across the members present in a
    month, of each member's sign-aligned monthly IC. Returns (family_ic month
    Series, n_members_present month Series)."""
    per_member: dict[str, pd.Series] = {}
    for m in members:
        sig = member_signals.get(m["variable"])
        if sig is None or len(sig) == 0:
            continue
        uni = m.get("universe")
        if uni:
            sig = sig[sig["country"].isin(uni)]
        if len(sig) == 0:
            continue
        if frequency == "daily":
            icm = _monthly_from_daily(member_daily_ic(
                sig, returns_daily, horizon, m["direction"], m.get("source"), m["variable"], registry))
        else:
            icm = member_monthly_ic(sig, returns_monthly, horizon,
                                    m["direction"], m.get("source"), m["variable"])
            if len(icm):
                icm.index = _to_month_start(icm.index)
                icm = icm.sort_index()
        if len(icm):
            per_member[m["variable"]] = icm
    if not per_member:
        return pd.Series(dtype=float, name="family_ic"), pd.Series(dtype="Int64")
    wide = pd.DataFrame(per_member).sort_index()
    fam = wide.mean(axis=1, skipna=True).rename("family_ic")
    n_members = wide.notna().sum(axis=1).astype("Int64")
    return fam, n_members


# ─────────────────────────────────────────────────────────────────────────────
# R-A price gate state machine (INV5)
# ─────────────────────────────────────────────────────────────────────────────
def _month_diff(a: pd.Timestamp, b: pd.Timestamp) -> int:
    a, b = pd.Timestamp(a), pd.Timestamp(b)
    return (b.year - a.year) * 12 + (b.month - a.month)


def evaluate_gate(monthly_points: list[tuple[Any, Optional[float]]]) -> dict[str, Any]:
    """R-A gate over an ordered list of (month_start, family_ic) for COMPLETED
    months only. Rules (INV5): start `parked`, consecutive_positive = 0; a
    calendar gap resets the counter BEFORE the month is counted; a strictly
    positive IC increments, any non-positive (<= 0, incl. exact zero or NaN)
    resets to 0; state is `re-armed` iff counter >= GATE_REARM_CONSECUTIVE
    (so a non-positive month after a re-arm re-parks it). Transitions recorded
    with evidence months."""
    state = "parked"
    consec = 0
    transitions: list[dict[str, Any]] = []
    prev: Optional[pd.Timestamp] = None
    for month, ic in monthly_points:
        month = pd.Timestamp(month)
        if prev is not None and _month_diff(prev, month) != 1:
            consec = 0
        positive = ic is not None and not pd.isna(ic) and float(ic) > 0.0
        consec = consec + 1 if positive else 0
        new_state = "re-armed" if consec >= GATE_REARM_CONSECUTIVE else "parked"
        if new_state != state:
            transitions.append({
                "month": str(month.date()),
                "from": state,
                "to": new_state,
                "consecutive_positive": consec,
                "family_ic": None if (ic is None or pd.isna(ic)) else round(float(ic), 6),
            })
            state = new_state
        prev = month
    return {
        "state": state,
        "consecutive_positive": consec,
        "last_month_end": None if prev is None else str(pd.Timestamp(prev).date()),
        "n_months": len(monthly_points),
        "transitions": transitions,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Persistence (durable loop DB; upsert; INV3 / INV6)
# ─────────────────────────────────────────────────────────────────────────────
_TABLE_DDL = f"""
CREATE TABLE IF NOT EXISTS {MONITOR_TABLE} (
    family VARCHAR,
    roster VARCHAR,
    month DATE,
    family_ic DOUBLE,
    n_members INTEGER,
    role VARCHAR,
    frequency VARCHAR,
    horizon VARCHAR,
    harness_version INTEGER,
    computed_ts VARCHAR,
    PRIMARY KEY (family, roster, month)
)
"""


def ensure_table(con) -> None:
    con.execute(_TABLE_DDL)


def upsert_family_ic(con, family: str, roster: str, role: Optional[str],
                     fam_series: pd.Series, n_members: pd.Series,
                     frequency: str, horizon: str, computed_ts: str) -> int:
    """Upsert one row per (family, roster, month). Re-running the same night
    updates in place (no duplicate rows). Returns rows written."""
    ensure_table(con)
    n = 0
    for month, ic in fam_series.items():
        nm = n_members.get(month)
        nm = int(nm) if nm is not None and not pd.isna(nm) else 0
        con.execute(
            f"""INSERT INTO {MONITOR_TABLE}
                (family, roster, month, family_ic, n_members, role, frequency,
                 horizon, harness_version, computed_ts)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (family, roster, month) DO UPDATE SET
                    family_ic = excluded.family_ic,
                    n_members = excluded.n_members,
                    role = excluded.role,
                    frequency = excluded.frequency,
                    horizon = excluded.horizon,
                    harness_version = excluded.harness_version,
                    computed_ts = excluded.computed_ts""",
            [family, roster, pd.Timestamp(month).date(),
             None if pd.isna(ic) else float(ic), nm, role,
             frequency, horizon, int(HARNESS_VERSION), computed_ts],
        )
        n += 1
    return n


def read_family_ic(con, family: str, roster: str) -> pd.Series:
    """Stored month->family_ic Series for a (family, roster) (empty if none)."""
    ensure_table(con)
    rows = con.execute(
        f"SELECT month, family_ic FROM {MONITOR_TABLE} WHERE family = ? AND roster = ? ORDER BY month",
        [family, roster],
    ).fetchall()
    if not rows:
        return pd.Series(dtype=float, name="family_ic")
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.Series([r[1] for r in rows], index=idx, name="family_ic")


def evaluate_all_gates(con, families: dict[str, Any], now: Optional[Any] = None) -> dict[str, Any]:
    """Evaluate the R-A gate for every family from its GATE roster series in the
    stored table, using only COMPLETED months (strictly before `now`'s month)."""
    now_ts = pd.Timestamp(now) if now is not None else pd.Timestamp.utcnow()
    current_month = now_ts.to_period("M").to_timestamp()
    out: dict[str, Any] = {}
    for fam, spec in families.items():
        roster = gate_roster_name(spec)
        series = read_family_ic(con, fam, roster)
        pts = [(m, ic) for m, ic in series.items() if pd.Timestamp(m) < current_month]
        gate = evaluate_gate(pts)
        last_ic = None
        if pts:
            last_ic = pts[-1][1]
            last_ic = None if (last_ic is None or pd.isna(last_ic)) else round(float(last_ic), 6)
        gate["last_family_ic"] = last_ic
        gate["roster"] = roster
        gate["frequency"] = spec.get("frequency")
        gate["horizon"] = _family_horizon_label(spec)
        out[fam] = gate
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Status artifact (atomic write) + reader
# ─────────────────────────────────────────────────────────────────────────────
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_status(status_path: Path, gate_states: dict[str, Any], now: Optional[Any] = None) -> Path:
    status_path = Path(status_path)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_ts": _now_iso(),
        "as_of": str((pd.Timestamp(now) if now is not None else pd.Timestamp.utcnow()).date()),
        "harness_version": int(HARNESS_VERSION),
        "monitor_table": MONITOR_TABLE,
        "families": gate_states,
    }
    tmp = status_path.with_name(status_path.name + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, default=str))
    tmp.replace(status_path)
    return status_path


def read_status(status_path: Path = STATUS_PATH) -> dict[str, Any]:
    status_path = Path(status_path)
    if not status_path.exists():
        return {"status": "not_run", "path": str(status_path)}
    return json.loads(status_path.read_text())


# ─────────────────────────────────────────────────────────────────────────────
# INV4 known-answer comparison (AUTHOR AMENDMENT 1: four binding clauses)
# ─────────────────────────────────────────────────────────────────────────────
def inv4_comparison(backfill_monthly: pd.Series,
                    per_year_tol: float = INV4_PER_YEAR_TOL,
                    min_corr: float = INV4_MIN_CORR,
                    pre_mean_tol: float = INV4_PRE_MEAN_TOL,
                    a6_path: Path = A6_REF_PATH,
                    a2_path: Path = A2_REF_PATH) -> dict[str, Any]:
    """Compare a backfilled monthly family-IC series (the ref16_frozen roster)
    against the flip-autopsy references. FOUR binding clauses (amended INV4):
      (i)   monthly corr >= min_corr vs the committed a2 monthly series;
      (ii)  per-year means within per_year_tol of a6's lag1_per_year;
      (iii) pre-2024 (2012-2023) mean within pre_mean_tol of a6's lag1_pre_mean;
      (iv)  post-2024 (>= 2024) mean < 0 (the decay/flip reproduces).
    `ok` is the AND of all four. Pure -- reads only the two committed refs."""
    a6json = json.loads(Path(a6_path).read_text())
    a6 = a6json["lag1_per_year"]
    a6_pre = float(a6json["lag1_pre_mean"])
    a2_df = pd.read_parquet(a2_path)
    a2 = pd.Series(a2_df["family_ic"].values, index=pd.to_datetime(a2_df["month"]))

    bm = backfill_monthly.copy()
    bm.index = pd.to_datetime(bm.index)
    bm = bm.sort_index()

    # (ii) per-year
    fy = bm.groupby(bm.index.year).mean()
    per_year, offenders = [], []
    for year_str, ref in sorted(a6.items(), key=lambda kv: int(kv[0])):
        y = int(year_str)
        got = fy.get(y)
        has = got is not None and not pd.isna(got)
        delta = abs(float(got) - float(ref)) if has else None
        per_year.append({"year": y, "got": round(float(got), 5) if has else None,
                         "ref": round(float(ref), 5),
                         "delta": round(delta, 5) if delta is not None else None})
        if delta is None or delta > per_year_tol:
            offenders.append(y)

    # (i) correlation
    ov = bm.index.intersection(a2.index)
    corr = float(bm.loc[ov].corr(a2.loc[ov])) if len(ov) >= 24 else float("nan")
    corr_ok = corr == corr and corr >= min_corr

    # (iii) pre-2024 mean
    pre = bm[(bm.index >= pd.Timestamp(INV4_PRE_WINDOW[0])) & (bm.index < pd.Timestamp(INV4_PRE_WINDOW[1]))]
    pre_mean = float(pre.mean()) if len(pre) else float("nan")
    pre_delta = abs(pre_mean - a6_pre) if pre_mean == pre_mean else None
    pre_ok = pre_delta is not None and pre_delta <= pre_mean_tol

    # (iv) post-2024 mean < 0
    post = bm[bm.index >= pd.Timestamp(INV4_POST_START)]
    post_mean = float(post.mean()) if len(post) else float("nan")
    post_ok = post_mean == post_mean and post_mean < 0.0

    ok = (not offenders) and corr_ok and pre_ok and post_ok
    return {
        "ok": bool(ok),
        "corr_vs_a2_monthly": round(corr, 4) if corr == corr else None,
        "corr_ok": bool(corr_ok), "min_corr": min_corr,
        "per_year_tol": per_year_tol, "n_offending_years": len(offenders),
        "offending_years": offenders,
        "pre_2024_mean": round(pre_mean, 5) if pre_mean == pre_mean else None,
        "pre_2024_ref": round(a6_pre, 5),
        "pre_2024_delta": round(pre_delta, 5) if pre_delta is not None else None,
        "pre_mean_tol": pre_mean_tol, "pre_ok": bool(pre_ok),
        "post_2024_mean": round(post_mean, 5) if post_mean == post_mean else None,
        "post_ok": bool(post_ok),
        "n_overlap_months": int(len(ov)),
        "per_year": per_year,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Production loaders (open the loop connection; used only by the live path)
# ─────────────────────────────────────────────────────────────────────────────
def _prod_returns_daily(con) -> pd.DataFrame:
    return daily_country_returns(con).rename(columns={"ret": "return_1m"})


def _prod_returns_monthly(con) -> pd.DataFrame:
    df = con.execute(
        "SELECT date, country, return_1m FROM country_returns_monthly WHERE return_1m IS NOT NULL"
    ).fetchdf()
    df["date"] = pd.to_datetime(df["date"])
    return df


def _prod_member_signal(con, member: dict[str, Any]) -> pd.DataFrame:
    df = con.execute(
        f"SELECT date, country, value FROM {member['table']} "
        f"WHERE variable = ? AND value IS NOT NULL",
        [member["variable"]],
    ).fetchdf()
    df["date"] = pd.to_datetime(df["date"])
    return df


def _default_loaders() -> dict[str, Callable]:
    return {"returns_daily": _prod_returns_daily,
            "returns_monthly": _prod_returns_monthly,
            "member_signal": _prod_member_signal}


def _needs(families: dict[str, Any], freq: str) -> bool:
    return any(spec.get("frequency") == freq for spec in families.values())


def _compute_all(con, families: dict[str, Any], loaders: dict[str, Callable],
                 since: Optional[pd.Timestamp] = None) -> dict[tuple[str, str], dict[str, Any]]:
    """Load member signals + returns and compute each (family, roster) monthly
    IC. `since` (a first-of-month cutoff) restricts to the trailing window for
    the incremental nightly path (None = full history). Member signals are
    cached by variable so members shared across rosters load once."""
    rd = loaders["returns_daily"](con) if _needs(families, "daily") else None
    rm = loaders["returns_monthly"](con) if _needs(families, "monthly") else None
    sig_cache: dict[str, pd.DataFrame] = {}

    def _signal(member) -> pd.DataFrame:
        key = member["variable"]
        if key not in sig_cache:
            sig = loaders["member_signal"](con, member)
            if since is not None and sig is not None and len(sig):
                sig = sig[pd.to_datetime(sig["date"]) >= since]
            sig_cache[key] = sig
        return sig_cache[key]

    results: dict[tuple[str, str], dict[str, Any]] = {}
    for fam_name, spec in families.items():
        horizon = _family_horizon(spec)
        for rname, r in spec["rosters"].items():
            member_signals = {m["variable"]: _signal(m) for m in r["members"]}
            fam, nmem = roster_monthly_ic(spec["frequency"], horizon, r["members"],
                                          member_signals, rd, rm)
            results[(fam_name, rname)] = {
                "series": fam, "n_members": nmem, "role": r.get("role"),
                "frequency": spec["frequency"], "horizon": _family_horizon_label(spec)}
    return results


def _persist(con, results: dict[tuple[str, str], dict[str, Any]], computed_ts: str) -> int:
    rows = 0
    for (fam, roster), r in results.items():
        if len(r["series"]):
            rows += upsert_family_ic(con, fam, roster, r["role"], r["series"], r["n_members"],
                                     r["frequency"], r["horizon"], computed_ts)
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Entry point: nightly incremental step (FAIL-SOFT -- INV2)
# ─────────────────────────────────────────────────────────────────────────────
def nightly_step(*, con=None, loop_db_path: Optional[Path] = None,
                 status_path: Path = STATUS_PATH, families: Optional[dict] = None,
                 loaders: Optional[dict] = None, now: Optional[Any] = None,
                 months_back: int = NIGHTLY_MONTHS_BACK) -> int:
    """Incremental nightly step the loop calls. FAIL-SOFT: catches EVERYTHING,
    logs it loudly, and returns exit 2 (PARTIAL) rather than raising, so a
    monitor failure can never take down the nightly loop (INV2). Returns 0 on
    success, 2 on any handled failure. Recomputes only the trailing
    `months_back` months (history is stable), upserts all (family, roster)
    series idempotently, re-evaluates gates and refreshes the status artifact."""
    try:
        fams = families if families is not None else monitored_families()
        loaders = loaders or _default_loaders()
        now_ts = pd.Timestamp(now) if now is not None else pd.Timestamp.utcnow()
        since = now_ts.to_period("M").to_timestamp() - pd.DateOffset(months=int(months_back))
        computed_ts = _now_iso()

        own_con = con is None
        if own_con:
            con = loop_connection(read_only=False)
        try:
            results = _compute_all(con, fams, loaders, since=since)
            _persist(con, results, computed_ts)
            gates = evaluate_all_gates(con, fams, now=now_ts)
        finally:
            if own_con:
                con.close()

        write_status(status_path, gates, now=now_ts)
        _log.info("family_ic_monitor nightly OK: %s", {k: v["state"] for k, v in gates.items()})
        print("family_ic_monitor: nightly OK ("
              + ", ".join(f"{k}={v['state']}/{v['consecutive_positive']}" for k, v in gates.items())
              + ")", flush=True)
        return 0
    except Exception as exc:  # noqa: BLE001 -- fail-soft is the whole point (INV2)
        _log.error("family_ic_monitor nightly FAILED (fail-soft, exit 2): %s", exc)
        print(f"!!! family_ic_monitor: nightly step FAILED (fail-soft, exit 2): {exc}", flush=True)
        traceback.print_exc()
        return 2


# ─────────────────────────────────────────────────────────────────────────────
# Entry point: full historical backfill + INV4 known-answer (G3, permissioned)
# ─────────────────────────────────────────────────────────────────────────────
def backfill(*, con=None, loop_db_path: Optional[Path] = None,
             status_path: Path = STATUS_PATH, families: Optional[dict] = None,
             loaders: Optional[dict] = None, now: Optional[Any] = None,
             per_year_tol: float = INV4_PER_YEAR_TOL, min_corr: float = INV4_MIN_CORR,
             pre_mean_tol: float = INV4_PRE_MEAN_TOL, verbose: bool = True) -> int:
    """Compute the full monthly history for every (family, roster), upsert it,
    evaluate gates, write the status artifact, and run the four-clause INV4
    known-answer comparison on network_spillover's ref16_frozen roster. Returns
    0 iff INV4 holds AND the network_spillover gate reads `parked`/0 as of the
    last completed month; else 1 (FAIL-IS-FAIL, failing clauses named)."""
    fams = families if families is not None else monitored_families()
    loaders = loaders or _default_loaders()
    now_ts = pd.Timestamp(now) if now is not None else pd.Timestamp.utcnow()
    computed_ts = _now_iso()

    own_con = con is None
    if own_con:
        con = loop_connection(read_only=False)
    try:
        results = _compute_all(con, fams, loaders, since=None)
        _persist(con, results, computed_ts)
        gates = evaluate_all_gates(con, fams, now=now_ts)
    finally:
        if own_con:
            con.close()

    write_status(status_path, gates, now=now_ts)

    ka = results.get((KNOWN_ANSWER_FAMILY, KNOWN_ANSWER_ROSTER), {})
    ka_series = ka.get("series", pd.Series(dtype=float))
    inv4 = inv4_comparison(ka_series, per_year_tol=per_year_tol, min_corr=min_corr,
                           pre_mean_tol=pre_mean_tol)

    ka_gate = gates.get(KNOWN_ANSWER_FAMILY, {})
    gate_ok = (ka_gate.get("state") == "parked"
               and ka_gate.get("consecutive_positive") == KNOWN_ANSWER_EXPECTED_CONSECUTIVE)

    if verbose:
        print("\n=== family_ic_monitor BACKFILL ===", flush=True)
        for (fam, roster), r in results.items():
            g = gates.get(fam, {}) if roster == gate_roster_name(fams[fam]) else {}
            gtxt = (f" gate={g['state']}/{g['consecutive_positive']} last={g['last_month_end']}"
                    if g else "  (inv4_reference roster)")
            print(f"  {fam:18} [{roster:16}] months={len(r['series']):>4}{gtxt}", flush=True)
        print(f"\n--- INV4 known-answer ({KNOWN_ANSWER_FAMILY}/{KNOWN_ANSWER_ROSTER}) ---", flush=True)
        print(f"  (i)  corr vs a2 monthly = {inv4['corr_vs_a2_monthly']} "
              f"(>= {inv4['min_corr']}: {'PASS' if inv4['corr_ok'] else 'FAIL'}, n={inv4['n_overlap_months']})", flush=True)
        print(f"  (ii) per-year |delta| vs a6 (tol {inv4['per_year_tol']}): "
              f"{inv4['n_offending_years']} offending: {inv4['offending_years']}", flush=True)
        print(f"  (iii) pre-2024 mean={inv4['pre_2024_mean']} vs a6 {inv4['pre_2024_ref']} "
              f"(delta {inv4['pre_2024_delta']}, tol {inv4['pre_mean_tol']}: {'PASS' if inv4['pre_ok'] else 'FAIL'})", flush=True)
        print(f"  (iv) post-2024 mean={inv4['post_2024_mean']} (< 0: {'PASS' if inv4['post_ok'] else 'FAIL'})", flush=True)
        for row in inv4["per_year"]:
            flag = "" if (row["delta"] is not None and row["delta"] <= inv4["per_year_tol"]) else "  <-- offends"
            print(f"    {row['year']}: got={row['got']} ref={row['ref']} delta={row['delta']}{flag}", flush=True)
        print(f"\n  INV4 ok = {inv4['ok']}   network_spillover parked/{KNOWN_ANSWER_EXPECTED_CONSECUTIVE} = {gate_ok}", flush=True)

    rc = 0 if (inv4["ok"] and gate_ok) else 1
    print(f"\nBACKFILL {'PASS (exit 0)' if rc == 0 else 'FAIL (exit 1)'}", flush=True)
    if rc != 0:
        if not inv4["ok"]:
            print(f"  INV4 failed: corr_ok={inv4['corr_ok']} per_year_offenders={inv4['offending_years']} "
                  f"pre_ok={inv4['pre_ok']} post_ok={inv4['post_ok']}", flush=True)
        if not gate_ok:
            print(f"  gate expectation failed: {KNOWN_ANSWER_FAMILY} is "
                  f"{ka_gate.get('state')}/{ka_gate.get('consecutive_positive')} "
                  f"(expected parked/{KNOWN_ANSWER_EXPECTED_CONSECUTIVE})", flush=True)
    return rc


# ─────────────────────────────────────────────────────────────────────────────
# Entry point: idempotence verifier (G4) -- run the nightly step twice
# ─────────────────────────────────────────────────────────────────────────────
def _count_rows(con) -> int:
    try:
        return int(con.execute(f"SELECT count(*) FROM {MONITOR_TABLE}").fetchone()[0])
    except Exception:  # noqa: BLE001 -- table may not exist yet
        return 0


def verify_idempotent(*, con=None, loaders: Optional[dict] = None,
                      families: Optional[dict] = None, status_path: Path = STATUS_PATH,
                      now: Optional[Any] = None, settle_s: float = 1.1) -> int:
    """G4: run the exact nightly step twice back-to-back and assert the second
    run changes NO row counts (INV3) and the status artifact is refreshed.
    Returns 0 iff both runs exit 0, the monitor-table row count is identical
    across the two runs, and the status JSON is rewritten with a fresh timestamp."""
    import time

    def _run() -> int:
        return nightly_step(con=con, loaders=loaders, families=families,
                            status_path=status_path, now=now)

    def _rows() -> int:
        if con is not None:
            return _count_rows(con)
        c = loop_connection(read_only=True)
        try:
            return _count_rows(c)
        finally:
            c.close()

    rc1 = _run()
    n1 = _rows()
    ts1 = read_status(status_path).get("generated_ts")
    time.sleep(settle_s)
    rc2 = _run()
    n2 = _rows()
    ts2 = read_status(status_path).get("generated_ts")

    row_ok = n1 == n2 and n1 > 0
    ts_ok = ts2 is not None and (ts1 is None or ts2 >= ts1)
    ok = rc1 == 0 and rc2 == 0 and row_ok and ts_ok
    print(f"verify_idempotent: rc1={rc1} rc2={rc2} rows {n1}->{n2} "
          f"status_ts {ts1} -> {ts2} (refreshed={ts_ok})", flush=True)
    print(f"G4 {'PASS (exit 0)' if ok else 'FAIL (exit 1)'}", flush=True)
    return 0 if ok else 1


# ─────────────────────────────────────────────────────────────────────────────
# Dry-run: validate wiring without touching any DB (verifies G3/G4 well-formed)
# ─────────────────────────────────────────────────────────────────────────────
def dry_run(mode: str) -> int:
    roster = load_roster()
    fams = monitored_families(roster)
    refs_ok = A6_REF_PATH.exists() and A2_REF_PATH.exists()
    plan = {
        "mode": mode,
        "roster_path": str(ROSTER_PATH),
        "roster_version": roster.get("version"),
        "families": {k: {"frequency": v["frequency"], "horizon": _family_horizon_label(v),
                         "gate_roster": gate_roster_name(v),
                         "rosters": {rn: {"role": rr.get("role"), "n_members": len(rr["members"])}
                                     for rn, rr in v["rosters"].items()}}
                     for k, v in fams.items()},
        "loop_db": str(LOOP_DB),
        "monitor_table": MONITOR_TABLE,
        "status_path": str(STATUS_PATH),
        "inv4_target": {"family": KNOWN_ANSWER_FAMILY, "roster": KNOWN_ANSWER_ROSTER},
        "inv4_refs": {"a6": str(A6_REF_PATH), "a2": str(A2_REF_PATH), "both_exist": refs_ok},
        "inv4_thresholds": {"min_corr": INV4_MIN_CORR, "per_year_tol": INV4_PER_YEAR_TOL,
                            "pre_mean_tol": INV4_PRE_MEAN_TOL},
        "harness_version": int(HARNESS_VERSION),
    }
    print(json.dumps(plan, indent=2))
    ok = bool(fams) and refs_ok and KNOWN_ANSWER_ROSTER in fams.get(KNOWN_ANSWER_FAMILY, {}).get("rosters", {})
    print(f"\nDRY-RUN {'OK' if ok else 'INCOMPLETE'} (mode={mode}) -- no DB opened", flush=True)
    return 0 if ok else 1


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────
def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="ASADO family-IC monitor (contract FAMILY-IC-MONITOR-001).")
    ap.add_argument("--backfill", action="store_true", help="Full historical backfill + INV4 (gate G3).")
    ap.add_argument("--verify-idempotent", action="store_true",
                    help="Run the nightly step twice and assert idempotent writes + status refresh (gate G4).")
    ap.add_argument("--status", action="store_true", help="Print the current status artifact and exit.")
    ap.add_argument("--dry-run", action="store_true", help="Validate wiring/paths without opening any DB.")
    args = ap.parse_args(argv)

    mode = ("backfill" if args.backfill else
            "verify-idempotent" if args.verify_idempotent else "nightly")
    if args.dry_run:
        return dry_run(mode)
    if args.status:
        print(json.dumps(read_status(), indent=2, default=str))
        return 0
    if args.backfill:
        return backfill()
    if args.verify_idempotent:
        return verify_idempotent()
    return nightly_step()


if __name__ == "__main__":
    sys.exit(main())
