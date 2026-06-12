#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: event_study.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
  Event sources (sov_rating_changes, sovereign_signals, eco_surprise_signals,
  dislocation_daily, or any SQL) + the warehouse attached read-only as
  `asado` (t2_factors_daily 1DRet for the return surface, event_log).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb (read-only,
  attached) - daily country returns and the curated event_log.

OUTPUT FILES (one directory per run):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/event_studies/{name}_{ts}/
    results.json   - full result payload (written incrementally: events first,
                     then stats, then bootstrap - a crash keeps partials)
    summary.xlsx   - CAR-by-day table + per-event panel + horizon stats sheets
    car_plot.pdf   - mean CAR path with bootstrap CI band (light mode)

VERSION: 1.0
LAST UPDATED: 2026-06-12
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop)

DESCRIPTION:
Event-study engine for the Alpha-Hunting Loop. The harness answers "does
this monthly/daily cross-sectional rank predict returns?"; this tool answers
the OTHER question the new data layers raise: "what happens to a country's
return in the days after a discrete EVENT?" - a rating downgrade, a CDS
curve inversion, a hot inflation print, a dislocation firing.

A 10th grader's version: take every time the same kind of thing happened
(say, 80 downgrades), line up the day it happened as "day 0", average what
the country's stock market did relative to everyone else over the next 60
trading days, and draw the path with error bars so you can tell signal from
luck.

METHOD:
1. EVENTS: (date, country[, sign]) rows from a built-in preset or your SQL.
   sign (+1/-1) optionally flips the return so "positive CAR = event helped"
   regardless of event polarity.
2. ANCHORING (the PIT rule): events become tradeable at the first trading
   day AFTER they are knowable.
     anchor=next_day   : first trading day strictly after the event date
                         (for daily-observed events, e.g. CDS inversions).
     anchor=next_month : first trading day of the month AFTER the event's
                         label month. REQUIRED for monthly-sampled tables
                         (sov_rating_changes, eco_surprise_*): a row labeled
                         2020-03-01 is the state observed at END of March,
                         so it is only knowable from April 1. Presets pick
                         the right anchor automatically.
3. ABNORMAL RETURN: country trading-day return minus the equal-weight mean
   of all T2 countries trading that day (market-adjusted model). Returns are
   the loop's backward-labeled REAL trading-day series (loopdb helper) - no
   weekend ghosts, no forward labels.
4. CAR: per event, cumulative sum of abnormal log-ish (simple-sum) ARs over
   trading-day offsets -pre..+post relative to the anchor (day 0 = anchor's
   PREVIOUS close, so the first post-event return lands on offset +1; the
   pre-window shows run-up/leakage and is NOT tradeable).
5. INFERENCE: bootstrap across EVENTS (resample events with replacement,
   default 2000 draws) -> 95% CI band for the mean CAR path; per-horizon
   (+5/+21/+63) mean CAR, t-stat across events, hit rate, and the same for
   the pre-window (leakage check).
6. GUARDS: < 8 usable events -> verdict INSUFFICIENT_EVENTS (still writes
   output, loudly labeled). Overlapping windows for the same country are
   kept but counted; heavy overlap (> 30% of events sharing country-months)
   is flagged in the caveats.

BUILT-IN PRESETS (--preset):
  rating_downgrade   sov_rating_changes delta < 0 (sign=-1: CAR>0 = fell)
                     ... default agency=all, --agency SP|MOODY|FITCH filters
  rating_upgrade     sov_rating_changes delta > 0 (sign=+1)
  cds_inversion      first day SOV_CDS_SLOPE_BP crosses below 0 after >= 60
                     non-inverted trading days (onset detection, daily anchor)
  growth_hot         ECO_GROWTH_SURPRISE_Z >= +1.5 prints (monthly anchor)
  growth_cold        ECO_GROWTH_SURPRISE_Z <= -1.5 prints
  inflation_hot      ECO_INFL_SURPRISE_Z  >= +1.5 prints
  dislocation        dislocation_daily rows; --detector D4 filters; anchor
                     next_day; sign from the row's direction where present
  event_log          asado.event_log curated registry; --category filters

CUSTOM EVENTS (--events-sql):
  Any SQL against the loop connection returning columns
  date, country [, sign]. Example:
    --events-sql "SELECT date, country, -1 AS sign FROM sov_rating_changes
                  WHERE delta <= -2"

DEPENDENCIES:
- duckdb, pandas, numpy, scipy, matplotlib, openpyxl (project venv)

USAGE:
 python scripts/loop/event_study.py --preset rating_downgrade
 python scripts/loop/event_study.py --preset cds_inversion --post 40
 python scripts/loop/event_study.py --preset dislocation --detector D4
 python scripts/loop/event_study.py --name my_events \
     --events-sql "SELECT date, country FROM ..." --anchor next_day

NOTES:
- This is a DESCRIPTIVE tool: it quantifies conditional return behavior. It
  does not register hypotheses or charge harness trials. If an event type
  looks tradeable here, register it properly and put the derived signal
  through evaluate_signal before believing it.
- Monthly-anchored studies are conservative by construction: the true
  announcement happened up to a month before day 0, so any post-anchor CAR
  is drift that survived the publication delay - the tradeable part.
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats as sstats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.loop.loopdb import LOOP_DIR, T2_UNIVERSE, loop_connection, returns_panel

OUT_ROOT = LOOP_DIR / "event_studies"
DEFAULT_PRE, DEFAULT_POST = 20, 63
DEFAULT_HORIZONS = (5, 21, 63)
MIN_EVENTS = 8


# ─────────────────────────────────────────────────────────────────────────────
# Event extraction
# ─────────────────────────────────────────────────────────────────────────────

def preset_events(con, preset: str, args) -> tuple[pd.DataFrame, str]:
    """Return (events df with date/country/sign, default anchor mode)."""
    if preset in ("rating_downgrade", "rating_upgrade"):
        op, sign = ("<", -1.0) if preset == "rating_downgrade" else (">", 1.0)
        agency_clause = ""
        params: list[Any] = []
        if args.agency:
            agency_clause = "AND agency = ?"
            params.append(args.agency)
        df = con.execute(
            f"SELECT date, country FROM sov_rating_changes WHERE delta {op} 0 {agency_clause}",
            params).fetchdf()
        # several agencies can move in the same month - one event per country-month
        df = df.drop_duplicates(subset=["date", "country"])
        df["sign"] = sign
        return df, "next_month"

    if preset == "cds_inversion":
        raw = con.execute(
            "SELECT date, country, value FROM sovereign_signals "
            "WHERE variable = 'SOV_CDS_SLOPE_BP' ORDER BY country, date").fetchdf()
        events = []
        for country, g in raw.groupby("country"):
            inv = (g["value"] < 0).values
            run_clean = 0
            for i in range(len(g)):
                if inv[i] and run_clean >= 60:
                    events.append({"date": g["date"].iloc[i], "country": country, "sign": -1.0})
                run_clean = 0 if inv[i] else run_clean + 1
        return pd.DataFrame(events, columns=["date", "country", "sign"]), "next_day"

    if preset in ("growth_hot", "growth_cold", "inflation_hot"):
        var = "ECO_GROWTH_SURPRISE_Z" if preset.startswith("growth") else "ECO_INFL_SURPRISE_Z"
        op, sign = (">=", 1.0) if preset.endswith("hot") else ("<=", -1.0)
        thr = args.threshold if preset.endswith("hot") else -args.threshold
        if preset == "inflation_hot":
            sign = -1.0  # hot inflation is presumed BAD for equities; CAR>0 = fell
        df = con.execute(
            f"SELECT date, country, {sign} AS sign FROM eco_surprise_signals "
            f"WHERE variable = ? AND value {op} ?", [var, thr]).fetchdf()
        return df, "next_month"

    if preset == "dislocation":
        det_clause, params = "", []
        if args.detector:
            det_clause = "AND detector = ?"
            params.append(args.detector)
        df = con.execute(
            f"""SELECT CAST(date AS DATE) AS date, entity AS country,
                       CASE WHEN direction = 'short' THEN -1.0 ELSE 1.0 END AS sign
                FROM dislocation_daily
                WHERE status IN ('new') {det_clause}""", params).fetchdf()
        return df, "next_day"

    if preset == "event_log":
        # event_log rows carry a comma-separated countries_affected list
        # (NULL for is_global rows, which have no single-country attribution
        # and are skipped here).
        cat_clause, params = "", []
        if args.category:
            cat_clause = "AND category = ?"
            params.append(args.category)
        df = con.execute(
            f"""SELECT event_date AS date,
                       trim(unnest(string_split(countries_affected, ','))) AS country,
                       1.0 AS sign
                FROM asado.event_log
                WHERE countries_affected IS NOT NULL {cat_clause}""",
            params).fetchdf()
        return df, "next_day"

    raise ValueError(f"unknown preset {preset!r}")


def clean_events(events: pd.DataFrame) -> pd.DataFrame:
    if "sign" not in events.columns:
        events["sign"] = 1.0
    missing = {"date", "country"} - set(events.columns)
    if missing:
        raise ValueError(f"events need columns date, country[, sign]; missing {missing}")
    events = events.copy()
    events["date"] = pd.to_datetime(events["date"])
    events = events[events["country"].isin(T2_UNIVERSE)]
    events = events.dropna(subset=["date", "country"]).drop_duplicates(["date", "country"])
    return events.sort_values(["date", "country"]).reset_index(drop=True)


# ─────────────────────────────────────────────────────────────────────────────
# Core computation
# ─────────────────────────────────────────────────────────────────────────────

def abnormal_returns(ret_panel: pd.DataFrame) -> pd.DataFrame:
    """Market-adjusted: country return minus that day's EW mean across the
    countries that actually traded."""
    return ret_panel.sub(ret_panel.mean(axis=1), axis=0)


def anchor_position(event_date: pd.Timestamp, dates: pd.DatetimeIndex, mode: str) -> Optional[int]:
    """Index of day 0 (the last pre-tradeable close) in the trading calendar."""
    if mode == "next_month":
        # event labeled month M is knowable at month-end; tradeable from the
        # first trading day of M+1. Day 0 = last trading day <= end of M.
        knowable = (event_date + pd.offsets.MonthEnd(0))
    else:
        knowable = event_date
    pos = dates.searchsorted(knowable, side="right") - 1
    if pos < 0 or pos >= len(dates):
        return None
    return int(pos)


def event_car_matrix(
    events: pd.DataFrame,
    ar: pd.DataFrame,
    anchor_mode: str,
    pre: int,
    post: int,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Per-event CAR path. Returns (matrix events x offsets [-pre..post],
    event metadata list). CAR is the cumulative sum of signed ARs; offset 0
    = anchor close (CAR=0 by construction at offset 0)."""
    dates = ar.index
    rows, meta = [], []
    for _, ev in events.iterrows():
        c = ev["country"]
        if c not in ar.columns:
            continue
        p0 = anchor_position(ev["date"], dates, anchor_mode)
        if p0 is None or p0 - pre < 0 or p0 + post >= len(dates):
            continue  # window must fit fully inside the sample
        window = ar[c].iloc[p0 - pre: p0 + post + 1].values * float(ev["sign"])
        if np.isnan(window).mean() > 0.4:
            continue  # country barely traded in the window
        path = np.nancumsum(window)
        path = path - path[pre]  # re-base so CAR(offset 0) = 0
        rows.append(path)
        meta.append({"event_date": str(ev["date"].date()), "country": c,
                     "sign": float(ev["sign"]), "anchor_date": str(dates[p0].date())})
    if not rows:
        return pd.DataFrame(), meta
    mat = pd.DataFrame(rows, columns=range(-pre, post + 1))
    return mat, meta


def bootstrap_band(mat: pd.DataFrame, n_boot: int, seed: int = 42) -> dict[str, np.ndarray]:
    """Resample EVENTS with replacement -> percentile CI of the mean CAR path."""
    rng = np.random.default_rng(seed)
    n = len(mat)
    means = np.empty((n_boot, mat.shape[1]))
    vals = mat.values
    for b in range(n_boot):
        idx = rng.integers(0, n, n)
        means[b] = np.nanmean(vals[idx], axis=0)
    return {
        "lo": np.nanpercentile(means, 2.5, axis=0),
        "hi": np.nanpercentile(means, 97.5, axis=0),
    }


def horizon_stats(mat: pd.DataFrame, horizons: tuple[int, ...]) -> dict[str, Any]:
    out = {}
    for h in horizons:
        if h not in mat.columns:
            continue
        x = mat[h].dropna().values
        t, p = (np.nan, np.nan)
        if len(x) >= 5 and x.std() > 0:
            t, p = sstats.ttest_1samp(x, 0.0)
        out[f"+{h}d"] = {
            "mean_car": round(float(np.mean(x)), 5),
            "median_car": round(float(np.median(x)), 5),
            "t_stat": round(float(t), 3) if not np.isnan(t) else None,
            "p_value": round(float(p), 4) if not np.isnan(p) else None,
            "hit_rate": round(float((x > 0).mean()), 3),
            "n_events": int(len(x)),
        }
    # leakage check: CAR over the pre-window (from -pre to 0 it ends at 0 by
    # construction, so measure run-up as -(CAR at first offset))
    first = mat.columns.min()
    runup = -mat[first].dropna().values  # CAR(0) - CAR(-pre) = run-up into the event
    out["pre_window_runup"] = {
        "mean_car": round(float(np.mean(runup)), 5),
        "hit_rate": round(float((runup > 0).mean()), 3),
        "note": "signed AR drift from -pre to day 0 (leakage / announcement-month move; NOT tradeable)",
    }
    return out


def overlap_caveat(meta: list[dict[str, Any]]) -> Optional[str]:
    km = pd.Series([f"{m['country']}|{m['anchor_date'][:7]}" for m in meta])
    dup = km.duplicated().mean()
    if dup > 0.3:
        return f"{dup:.0%} of events share a country-month - windows overlap heavily; treat CIs as optimistic"
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Outputs
# ─────────────────────────────────────────────────────────────────────────────

def make_plot(mat: pd.DataFrame, band: dict[str, np.ndarray], title: str, path: Path) -> None:
    """Mean CAR path with 95% bootstrap band. Light mode, PDF."""
    offsets = list(mat.columns)
    mean = mat.mean(axis=0).values
    fig, ax = plt.subplots(figsize=(9, 5.5), facecolor="white")
    ax.set_facecolor("white")
    ax.fill_between(offsets, band["lo"] * 100, band["hi"] * 100,
                    color="#9ecae1", alpha=0.5, label="95% bootstrap CI")
    ax.plot(offsets, mean * 100, color="#08519c", lw=2.0, label="mean CAR")
    ax.axvline(0, color="#666666", lw=1, ls="--")
    ax.axhline(0, color="#999999", lw=0.8)
    ax.set_xlabel("Trading days relative to anchor (0 = last pre-tradeable close)")
    ax.set_ylabel("Cumulative abnormal return (%)")
    ax.set_title(f"{title}  (n={len(mat)} events)")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, format="pdf")
    plt.close(fig)


def write_xlsx(mat: pd.DataFrame, meta: list[dict[str, Any]],
               stats_block: dict[str, Any], path: Path) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as xw:
        prof = pd.DataFrame({
            "offset": mat.columns,
            "mean_car": mat.mean(axis=0).values,
            "median_car": mat.median(axis=0).values,
            "n": mat.notna().sum(axis=0).values,
        })
        prof.to_excel(xw, sheet_name="car_by_day", index=False)
        pd.DataFrame(stats_block).T.to_excel(xw, sheet_name="horizon_stats")
        ev = pd.DataFrame(meta)
        for h in DEFAULT_HORIZONS:
            if h in mat.columns:
                ev[f"car_+{h}d"] = mat[h].values
        ev.to_excel(xw, sheet_name="events", index=False)


# ─────────────────────────────────────────────────────────────────────────────
# Driver
# ─────────────────────────────────────────────────────────────────────────────

def run(args) -> int:
    con = loop_connection(read_only=True)
    try:
        if args.events_sql:
            if not args.name:
                raise ValueError("--name is required with --events-sql")
            events = con.execute(args.events_sql).fetchdf()
            anchor = args.anchor or "next_day"
            name = args.name
        else:
            events, default_anchor = preset_events(con, args.preset, args)
            anchor = args.anchor or default_anchor
            name = args.name or args.preset
        events = clean_events(events)
        print(f"{name}: {len(events)} raw events | anchor={anchor} | window -{args.pre}..+{args.post}")

        ret = returns_panel(con)
    finally:
        con.close()

    ar = abnormal_returns(ret)
    mat, meta = event_car_matrix(events, ar, anchor, args.pre, args.post)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = OUT_ROOT / f"{name}_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Any] = {
        "name": name, "run_ts": ts, "anchor": anchor,
        "window": [-args.pre, args.post],
        "n_raw_events": int(len(events)), "n_usable_events": int(len(mat)),
        "events": meta,
    }
    # incremental persistence: events written before any stats are computed
    (out_dir / "results.json").write_text(json.dumps(result, indent=2, default=str))

    if len(mat) < MIN_EVENTS:
        result["verdict"] = "INSUFFICIENT_EVENTS"
        result["note"] = f"only {len(mat)} usable events (< {MIN_EVENTS}); no inference attempted"
        (out_dir / "results.json").write_text(json.dumps(result, indent=2, default=str))
        print(f"INSUFFICIENT_EVENTS: {len(mat)} usable events. Output: {out_dir}")
        return 1

    stats_block = horizon_stats(mat, tuple(args.horizons))
    result["horizon_stats"] = stats_block
    caveat = overlap_caveat(meta)
    if caveat:
        result["caveats"] = [caveat]
    (out_dir / "results.json").write_text(json.dumps(result, indent=2, default=str))

    band = bootstrap_band(mat, args.n_boot)
    result["bootstrap"] = {"n_boot": args.n_boot,
                           "ci95_final_offset": [round(float(band["lo"][-1]), 5),
                                                 round(float(band["hi"][-1]), 5)]}
    (out_dir / "results.json").write_text(json.dumps(result, indent=2, default=str))

    write_xlsx(mat, meta, stats_block, out_dir / "summary.xlsx")
    make_plot(mat, band, name, out_dir / "car_plot.pdf")

    print(f"\n{'=' * 70}\nEVENT STUDY: {name} - {len(mat)} usable events (of {len(events)})")
    if caveat:
        print(f"CAVEAT: {caveat}")
    for h, blk in stats_block.items():
        if h == "pre_window_runup":
            print(f"  pre-window run-up: mean={blk['mean_car']:+.4f} hit={blk['hit_rate']}")
        else:
            print(f"  CAR {h}: mean={blk['mean_car']:+.4f} t={blk['t_stat']} "
                  f"p={blk['p_value']} hit={blk['hit_rate']} n={blk['n_events']}")
    print(f"\nOutput dir: {out_dir}")
    for f in ("results.json", "summary.xlsx", "car_plot.pdf"):
        print(f"  {out_dir / f}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Cross-event CAR study on T2 country returns.")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--preset", choices=["rating_downgrade", "rating_upgrade", "cds_inversion",
                                          "growth_hot", "growth_cold", "inflation_hot",
                                          "dislocation", "event_log"])
    src.add_argument("--events-sql", help="SQL returning date, country[, sign] (loop connection).")
    p.add_argument("--name", help="Study name (required for --events-sql; overrides preset name).")
    p.add_argument("--anchor", choices=["next_day", "next_month"],
                   help="Override the preset's anchoring rule.")
    p.add_argument("--pre", type=int, default=DEFAULT_PRE, help="Pre-window trading days (default 20).")
    p.add_argument("--post", type=int, default=DEFAULT_POST, help="Post-window trading days (default 63).")
    p.add_argument("--horizons", type=int, nargs="+", default=list(DEFAULT_HORIZONS))
    p.add_argument("--n-boot", type=int, default=2000)
    p.add_argument("--agency", help="rating presets: SP / MOODY / FITCH (default all).")
    p.add_argument("--threshold", type=float, default=1.5, help="surprise presets: |z| threshold.")
    p.add_argument("--detector", help="dislocation preset: filter to one detector (e.g. D4).")
    p.add_argument("--category", help="event_log preset: filter to one category.")
    args = p.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
