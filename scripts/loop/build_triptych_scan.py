#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: build_triptych_scan.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/triptych_scan.yaml
    Scan registry: return spine, grid (horizons/normalizations/modes),
    warehouse factor extensions, review-queue selection thresholds.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
    (read-only) t2_raw monthly factor levels + the warehouse factor tables
    declared in the config (external/extended/imf/macrostructure/bloomberg).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/triptych_scan.parquet
    Full scan surface: one row per (factor, country, normalization,
    return_mode, horizon, threshold_mode) with bucket stats, IC, slope/R2,
    current decile, PIT prior confidence. Parquet-first (survives rebuilds).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/triptych_review_queue.parquet
    The top-N PIT review queue (PRD 8: capped, per-pair deduped).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Tables `triptych_scan` + `triptych_review_queue` (DROP+CREATE from the
    parquets, idempotent) and view `triptych_priors` (PIT rows only).

VERSION: 1.0
LAST UPDATED: 2026-07-02
AUTHOR: Arjun Divecha (built by agent session, Triptych Prediction Prior Layer PRD)

DESCRIPTION:
The ASADO-native Triptych scan. Replaces the Triptych app's slope_r2_scan.py
(which read t2_master.json and only supported full-sample descriptive
thresholds) with a DuckDB-fed sweep over every factor x country x
normalization x return-mode x horizon combination, computed in BOTH
threshold modes:
  pit  — point-in-time deciles (kernel-verified: no lookahead) -> the
         predictive prior surface (confidence per PRD 7.3)
  full — full-sample deciles (descriptive; matches the visual tool's
         default scan; confidence is hard-zeroed)
Factors = every t2_raw variable except the return spine + any variable in
config/triptych_scan.yaml's warehouse_factors block (the reason this scan
lives in ASADO: the whole warehouse is now sweepable, not just T2 sheets).

Parallelized across factors with ProcessPoolExecutor (M4 Max: all cores).

DEPENDENCIES:
- duckdb, pandas, numpy, pyyaml (project venv)

USAGE:
 python scripts/loop/build_triptych_scan.py            # full scan (~2-6 min)
 python scripts/loop/build_triptych_scan.py --check    # verify existing tables
 python scripts/loop/build_triptych_scan.py --factors REER,EPU  # subset (debug)
 python scripts/loop/build_triptych_scan.py --workers 4         # limit cores

NOTES:
- Forward-return variables (1MRet family) are refused as signals
  (kernel.is_forbidden_signal) — the house LOOKAHEAD TRAP rule.
- Countries outside a factor's coverage get NO row (universe honesty).
- cross_var_pct is skipped automatically for global-broadcast factors
  (identical value tiled across countries -> degenerate cross-section).
- triptych_url is filled for t2_raw factors only (the visual tool serves
  the T2 workbook; warehouse factors are ASADO-only surfaces).
- FAIL-IS-FAIL: a declared warehouse factor with no data raises.
=============================================================================
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.loop.loopdb import LOOP_DIR, T2_UNIVERSE, loop_connection
from scripts.loop.triptych_kernel import (
    BUCKET_COUNT,
    assign_bucket,
    assign_buckets_full,
    assign_buckets_pit,
    bucket_t_stat,
    cross_country_z,
    expanding_z,
    is_forbidden_signal,
    linear_fit,
    spearman_ic,
)
from scripts.triptych_tool_link import build_triptych_url

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BASE_DIR / "config" / "triptych_scan.yaml"
OUT_SCAN = LOOP_DIR / "triptych_scan.parquet"
OUT_QUEUE = LOOP_DIR / "triptych_review_queue.parquet"

# Horizons the visual tool supports for URL round-trips
_URL_HORIZONS = {1, 3, 6, 12, 24, 36}


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} [triptych_scan] {msg}", flush=True)


def load_config() -> dict:
    cfg = yaml.safe_load(CONFIG_PATH.read_text())
    for key in ("return_variable", "horizons", "normalizations", "return_modes", "queue"):
        if key not in cfg:
            raise ValueError(f"config missing '{key}': {CONFIG_PATH}")
    return cfg


# --------------------------------------------------------------------------- #
# Data loading — everything into (dates x countries) pivots up front
# --------------------------------------------------------------------------- #
def load_pivots(cfg: dict, factor_filter: set[str] | None):
    """Returns (return_pivot, {factor_name: (pivot, table)}) with monthly
    PeriodIndex rows and T2-country columns."""
    con = loop_connection(read_only=True)
    try:
        ret_var = cfg["return_variable"]
        tri = con.execute(
            "SELECT date, country, value FROM asado.t2_raw WHERE variable = ?", [ret_var]
        ).fetchdf()
        if tri.empty:
            raise RuntimeError(f"return spine '{ret_var}' not found in t2_raw")
        ret_pivot = _to_pivot(tri)

        factors: dict[str, tuple[pd.DataFrame, str]] = {}

        t2_vars = [r[0] for r in con.execute(
            "SELECT DISTINCT variable FROM asado.t2_raw ORDER BY 1").fetchall()]
        for v in t2_vars:
            if v == ret_var or is_forbidden_signal(v):
                continue
            if factor_filter and v not in factor_filter:
                continue
            df = con.execute(
                "SELECT date, country, value FROM asado.t2_raw WHERE variable = ?", [v]
            ).fetchdf()
            if not df.empty:
                factors[v] = (_to_pivot(df), "t2_raw")

        for spec in cfg.get("warehouse_factors") or []:
            v, table = spec["variable"], spec["table"]
            if factor_filter and v not in factor_filter:
                continue
            if v in factors:
                raise ValueError(f"duplicate factor name '{v}' (t2_raw vs {table})")
            df = con.execute(
                f"SELECT date, country, value FROM asado.{table} "
                f"WHERE variable = ? AND country IN ({','.join('?' * len(T2_UNIVERSE))})",
                [v, *T2_UNIVERSE],
            ).fetchdf()
            if df.empty:
                raise RuntimeError(
                    f"declared warehouse factor has no data: {table}/{v} (FAIL-IS-FAIL)")
            factors[v] = (_to_pivot(df), table)

        return ret_pivot, factors
    finally:
        con.close()


def _to_pivot(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["period"] = pd.to_datetime(df["date"]).dt.to_period("M")
    piv = df.pivot_table(index="period", columns="country", values="value",
                         aggfunc="last").sort_index()
    return piv


# --------------------------------------------------------------------------- #
# Forward-return panels (shared across every factor)
# --------------------------------------------------------------------------- #
def forward_panels(ret_pivot: pd.DataFrame, horizons: list[int]):
    """{h: (fwd_pivot, ew_mean_series)} — fwd = TRI[t+h]/TRI[t] - 1 per
    country; ew = equal-weight mean across countries with valid fwd at t
    (the tool's relative-return benchmark, all 34 return-sheet countries)."""
    out = {}
    tri = ret_pivot.replace(0.0, np.nan)          # base==0 is invalid (JS guard)
    for h in horizons:
        fwd = tri.shift(-h) / tri - 1.0
        ew = fwd.mean(axis=1, skipna=True)
        out[h] = (fwd, ew)
    return out


# --------------------------------------------------------------------------- #
# Per-factor worker
# --------------------------------------------------------------------------- #
def scan_factor(args: tuple) -> list[dict]:
    (factor, table, pivot, fwd_by_h, norms, modes, broadcast_skip) = args
    rows: list[dict] = []
    countries = [c for c in pivot.columns if c in set(T2_UNIVERSE)]

    # Pre-compute cross-country z on the factor's full pivot (self-excluded)
    cs_z = None
    if "cross_var_pct" in norms and not broadcast_skip:
        cs_z = pd.DataFrame(cross_country_z(pivot.values),
                            index=pivot.index, columns=pivot.columns)

    for country in countries:
        raw = pivot[country].dropna()
        if len(raw) < 24:
            continue
        for norm in norms:
            if norm == "raw":
                sig = raw.astype(float)
            elif norm == "history_z":
                sig = pd.Series(expanding_z(raw.values.astype(float)), index=raw.index)
            elif norm == "cross_var_pct":
                if cs_z is None:
                    continue
                sig = cs_z[country].dropna()
                if sig.empty:
                    continue
            else:
                raise ValueError(f"unknown normalization {norm!r}")

            current_signal = float(sig.iloc[-1]) if len(sig) else None

            for h, (fwd_pivot, ew) in fwd_by_h.items():
                if country not in fwd_pivot.columns:
                    continue
                fwd_abs = fwd_pivot[country]
                idx = sig.index.intersection(fwd_abs.dropna().index)
                if len(idx) < 2:
                    continue
                s = sig.loc[idx].values.astype(float)
                f_abs = fwd_abs.loc[idx].values.astype(float)
                f_rel = f_abs - ew.loc[idx].values.astype(float)

                # PIT + full bucket sequences depend only on the signal
                # sequence -> compute once, reuse for both return modes.
                pit_buckets, pit_final = assign_buckets_pit(s)
                full_buckets, full_final = assign_buckets_full(s)

                for mode in modes:
                    f = f_abs if mode == "absolute" else f_rel
                    for tmode, buckets, final_thr in (
                        ("pit", pit_buckets, pit_final),
                        ("full", full_buckets, full_final),
                    ):
                        row = _combo_row(s, f, buckets, final_thr,
                                         current_signal, h, tmode)
                        if row is None:
                            continue
                        row.update({
                            "factor": factor, "factor_table": table,
                            "country": country, "normalization": norm,
                            "return_mode": mode, "horizon_months": h,
                        })
                        rows.append(row)
    return rows


def _combo_row(signals, fwd, buckets, final_thresholds, current_signal,
               horizon, threshold_mode, k: int = BUCKET_COUNT) -> dict | None:
    mask = buckets > 0
    n_records = int(mask.sum())
    if n_records < 2:
        return None

    bucket_avg: list[float | None] = [None] * k
    bucket_n = [0] * k
    bucket_hit: list[float | None] = [None] * k
    for b in range(1, k + 1):
        vals = fwd[buckets == b]
        if len(vals):
            bucket_n[b - 1] = int(len(vals))
            bucket_avg[b - 1] = float(np.mean(vals))
            bucket_hit[b - 1] = float((vals > 0).mean())

    ic, ic_t = spearman_ic(signals[mask], fwd[mask], horizon)

    fit_x = [i + 1 for i, a in enumerate(bucket_avg) if a is not None and math.isfinite(a)]
    fit_y = [bucket_avg[i - 1] for i in fit_x]
    slope, icept, r2 = linear_fit(fit_x, fit_y)

    current_bucket = None
    if current_signal is not None and math.isfinite(current_signal):
        current_bucket = assign_bucket(float(current_signal), final_thresholds)

    cur_n = cur_avg = cur_hit = cur_t = None
    if current_bucket is not None:
        cur_n = bucket_n[current_bucket - 1]
        cur_avg = bucket_avg[current_bucket - 1]
        cur_hit = bucket_hit[current_bucket - 1]
        vals = fwd[buckets == current_bucket]
        cur_t = bucket_t_stat(vals, horizon) if len(vals) else None

    # Implied direction (min 5 obs in the current bucket, PRD 11 shape)
    if current_bucket is None or cur_avg is None or (cur_n or 0) < 5:
        direction = "insufficient"
    elif cur_avg > 0:
        direction = "long"
    elif cur_avg < 0:
        direction = "short"
    else:
        direction = "neutral"

    # Confidence sub-scores (PRD 7.3); horizon term is joined post-hoc.
    aligned = 0
    if slope is not None and icept is not None and current_bucket is not None \
            and cur_avg is not None:
        pred = slope * current_bucket + icept
        if pred != 0 and cur_avg != 0 and math.copysign(1, pred) == math.copysign(1, cur_avg):
            aligned = 1
    sample_score = min(1.0, (cur_n or 0) / 20.0)
    ic_score = min(1.0, abs(ic_t) / 2.5) if ic_t is not None else 0.0
    hit_score = abs(cur_hit - 0.5) * 2 if cur_hit is not None else 0.0

    return {
        "threshold_mode": threshold_mode,
        "n_records": n_records,
        "current_signal": current_signal,
        "current_decile": current_bucket,
        "bucket1_avg": bucket_avg[0],
        "bucket10_avg": bucket_avg[k - 1],
        "spread_top_minus_bottom": (bucket_avg[k - 1] - bucket_avg[0]
                                    if bucket_avg[0] is not None and bucket_avg[k - 1] is not None
                                    else None),
        "slope_per_bucket": slope,
        "r_squared": r2,
        "ic_spearman": ic,
        "ic_t_stat": ic_t,
        "cur_bucket_n": cur_n,
        "cur_bucket_avg_fwd": cur_avg,
        "cur_bucket_hit_rate": cur_hit,
        "cur_bucket_t_stat": cur_t,
        "implied_direction": direction,
        "aligned": aligned,
        "sample_score": sample_score,
        "ic_score": ic_score,
        "hit_score": hit_score,
    }


# --------------------------------------------------------------------------- #
# Post-processing: horizon agreement -> confidence; URLs; queue
# --------------------------------------------------------------------------- #
def finalize(df: pd.DataFrame, as_of: str, cfg: dict) -> pd.DataFrame:
    df = df.copy()
    df["as_of"] = as_of

    # Horizon consistency: share of sibling horizons (same factor/country/
    # norm/mode/threshold_mode) whose implied direction matches this row's.
    keys = ["factor", "country", "normalization", "return_mode", "threshold_mode"]
    dir_num = df["implied_direction"].map({"long": 1, "short": -1}).fillna(0)
    df["_dir"] = dir_num
    grp = df.groupby(keys)["_dir"]
    n_sib = grp.transform("size")
    same = df.groupby(keys + ["_dir"])["_dir"].transform("size")
    with np.errstate(invalid="ignore"):
        agree = np.where((n_sib > 1) & (df["_dir"] != 0),
                         (same - 1) / (n_sib - 1), 0.0)
    df["horizon_agreement"] = agree

    # PRD 7.3: confidence = mean of 4 sub-scores x aligned flag; hard 0 for
    # full-sample rows (descriptive only, never a prior).
    conf = ((df["sample_score"] + df["ic_score"] + df["hit_score"]
             + df["horizon_agreement"]) / 4.0) * df["aligned"]
    df["confidence_score"] = np.where(df["threshold_mode"] == "pit",
                                      conf.round(4), 0.0)
    notes = np.select(
        [df["threshold_mode"] != "pit",
         df["cur_bucket_n"].fillna(0) < 10],
        ["full-sample thresholds: descriptive only",
         "thin current bucket"],
        default="ok",
    )
    df["confidence_notes"] = notes
    df = df.drop(columns=["_dir"])

    # Triptych deep-links (t2 factors only; the tool serves the T2 workbook)
    def _url(row):
        if row["factor_table"] != "t2_raw" or row["horizon_months"] not in _URL_HORIZONS:
            return None
        norm = row["normalization"]
        try:
            return build_triptych_url(
                factor=row["factor"], country=row["country"],
                normalization=norm, return_mode=row["return_mode"],
                horizon=int(row["horizon_months"]), history_range="all",
                thresholds=row["threshold_mode"], buckets=10)
        except ValueError:
            return None
    df["triptych_url"] = df.apply(_url, axis=1)

    col_order = ["as_of", "factor", "factor_table", "country", "normalization",
                 "return_mode", "horizon_months", "threshold_mode", "n_records",
                 "current_signal", "current_decile", "bucket1_avg", "bucket10_avg",
                 "spread_top_minus_bottom", "slope_per_bucket", "r_squared",
                 "ic_spearman", "ic_t_stat", "cur_bucket_n", "cur_bucket_avg_fwd",
                 "cur_bucket_hit_rate", "cur_bucket_t_stat", "implied_direction",
                 "aligned", "sample_score", "ic_score", "hit_score",
                 "horizon_agreement", "confidence_score", "confidence_notes",
                 "triptych_url"]
    return df[col_order]


def build_queue(scan: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """PRD 8: the PIT review queue — strong, extreme, deduped, capped."""
    q = cfg["queue"]
    df = scan[
        (scan["threshold_mode"] == "pit")
        & (scan["n_records"] >= q["min_records"])
        & (scan["cur_bucket_n"].fillna(0) >= q["min_bucket_obs"])
        & (scan["ic_t_stat"].abs() >= q["min_abs_ic_t"])
        & (scan["r_squared"].fillna(0) >= q["min_r2"])
        & (scan["implied_direction"].isin(["long", "short"]))
        & ((scan["current_decile"] <= q["extreme_low_decile"])
           | (scan["current_decile"] >= q["extreme_high_decile"]))
        & (scan["confidence_score"] >= q["min_confidence"])
    ].copy()
    if df.empty:
        return df.assign(priority=pd.Series(dtype=float),
                         source_reason=pd.Series(dtype=str))

    df["priority"] = (df["confidence_score"]
                      * df["ic_t_stat"].abs().clip(upper=6.0) / 6.0
                      * df["r_squared"].clip(upper=1.0))
    df = df.sort_values("priority", ascending=False)
    df = df.groupby(["country", "factor"], as_index=False).head(
        int(q.get("per_pair_cap", 1)))
    df = df.sort_values("priority", ascending=False).head(int(q["cap"]))
    df["source_reason"] = "scan"
    return df.reset_index(drop=True)


# --------------------------------------------------------------------------- #
# Persistence
# --------------------------------------------------------------------------- #
def write_tables(scan: pd.DataFrame, queue: pd.DataFrame) -> None:
    OUT_SCAN.parent.mkdir(parents=True, exist_ok=True)
    scan.to_parquet(OUT_SCAN, index=False)
    queue.to_parquet(OUT_QUEUE, index=False)
    con = loop_connection()
    try:
        con.execute("DROP VIEW IF EXISTS triptych_priors")
        con.execute("DROP TABLE IF EXISTS triptych_scan")
        con.execute("DROP TABLE IF EXISTS triptych_review_queue")
        con.execute(f"CREATE TABLE triptych_scan AS SELECT * FROM read_parquet('{OUT_SCAN}')")
        con.execute(
            f"CREATE TABLE triptych_review_queue AS SELECT * FROM read_parquet('{OUT_QUEUE}')")
        con.execute("""
            CREATE VIEW triptych_priors AS
            SELECT * FROM triptych_scan WHERE threshold_mode = 'pit'
        """)
    finally:
        con.close()


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        for t in ("triptych_scan", "triptych_review_queue"):
            n = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            asof = con.execute(f"SELECT max(as_of) FROM {t}").fetchone()[0]
            print(f"{t}: {n:,} rows, as_of={asof}")
        top = con.execute("""
            SELECT country, factor, normalization, return_mode, horizon_months,
                   current_decile, implied_direction,
                   round(confidence_score, 3) AS conf, round(ic_t_stat, 2) AS ic_t
            FROM triptych_review_queue ORDER BY priority DESC LIMIT 10
        """).fetchdf()
        print(top.to_string(index=False))
        return 0
    finally:
        con.close()


# --------------------------------------------------------------------------- #
def main() -> int:
    parser = argparse.ArgumentParser(description="ASADO-native Triptych scan (PIT + full).")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--factors", default=None,
                        help="Comma-separated factor subset (debug)")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 8) - 2))
    args = parser.parse_args()

    if args.check:
        return check()

    t0 = time.time()
    cfg = load_config()
    factor_filter = ({f.strip() for f in args.factors.split(",")}
                     if args.factors else None)

    log("loading pivots from DuckDB ...")
    ret_pivot, factors = load_pivots(cfg, factor_filter)
    as_of = str(ret_pivot.index.max())
    log(f"return spine to {as_of}; {len(factors)} factors")

    fwd_by_h = forward_panels(ret_pivot, list(cfg["horizons"]))
    norms = list(cfg["normalizations"])
    modes = list(cfg["return_modes"])

    tasks = []
    for name, (pivot, table) in factors.items():
        # Global-broadcast detection: cross-section is degenerate when the
        # per-date spread is ~zero for essentially every date.
        row_std = pivot.std(axis=1, skipna=True)
        broadcast = bool((row_std.fillna(0) < 1e-12).mean() > 0.9)
        tasks.append((name, table, pivot, fwd_by_h, norms, modes, broadcast))

    log(f"scanning {len(tasks)} factors x 34 countries x {len(norms)} norms x "
        f"{len(modes)} modes x {len(cfg['horizons'])} horizons x 2 threshold modes "
        f"on {args.workers} workers ...")

    all_rows: list[dict] = []
    if args.workers <= 1 or len(tasks) == 1:
        for t in tasks:
            all_rows.extend(scan_factor(t))
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for i, rows in enumerate(pool.map(scan_factor, tasks, chunksize=1), 1):
                all_rows.extend(rows)
                if i % 10 == 0 or i == len(tasks):
                    log(f"  {i}/{len(tasks)} factors done "
                        f"({len(all_rows):,} rows, {time.time() - t0:.0f}s)")

    if not all_rows:
        raise RuntimeError("scan produced zero rows (FAIL-IS-FAIL)")

    scan = finalize(pd.DataFrame(all_rows), as_of, cfg)
    queue = build_queue(scan, cfg)
    write_tables(scan, queue)

    log(f"DONE: {len(scan):,} scan rows ({(scan['threshold_mode'] == 'pit').sum():,} PIT), "
        f"{len(queue)} queue rows, {time.time() - t0:.0f}s")
    log(f"wrote {OUT_SCAN}")
    log(f"wrote {OUT_QUEUE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
