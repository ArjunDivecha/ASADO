#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: build_triptych_signal.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/triptych_scan.yaml
    The SAME scan registry the nightly triptych scan uses: return spine,
    grid (horizons/normalizations/modes), warehouse factor extensions, and
    the review-queue gates. The walk-forward rule reuses the queue gates
    verbatim so the backtested rule IS the live rule.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
    (read-only) t2_raw monthly factor levels + declared warehouse factors.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/triptych_signal_monthly.parquet
    Tidy monthly panel (date, country, value, variable, source='triptych'):
      TRIPTYCH_QUEUE_LEAN  sum over qualifying (country, factor) pairs of
                           direction(+1 long/-1 short) x prior confidence,
                           0.0 when the country has no qualifying prior.
      TRIPTYCH_QUEUE_N     number of qualifying pairs (diagnostic).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `triptych_signal_monthly` (DROP+CREATE from the parquet).

VERSION: 1.0
LAST UPDATED: 2026-07-02
AUTHOR: Arjun Divecha (built by agent session, Triptych Prediction Prior Layer)

DESCRIPTION:
Walk-forward reconstruction of the Triptych review-queue rule, so the rule
can be honestly harness-tested. The nightly scan (build_triptych_scan.py)
answers "what does the queue say TODAY"; this script answers "what would the
queue have said at the end of EVERY month since 2004, using only information
available then":

  At evaluation month T, for every (factor, country, normalization,
  return_mode, horizon) combo:
    - usable records are those whose forward-return window has COMPLETED by
      T (record date <= T - horizon) - exactly the records the live scan
      would have had;
    - PIT decile thresholds are the running thresholds after the last usable
      record (record signals only, mirroring the live scan's final
      thresholds);
    - each record's own bucket is the one assigned at its own time by the
      PIT kernel (never re-bucketed with later thresholds);
    - the "current signal" is the latest factor observation labeled
      <= T - 1 month (a one-month AVAILABILITY EMBARGO: t2/warehouse factor
      values are as-labeled, not as-published, so the freshest label is not
      assumed knowable at T - conservative for market-derived factors,
      roughly right for macro);
    - IC t-stat / bucket-run R^2 / confidence / queue gates are recomputed
      from the usable prefix only (config queue thresholds, verbatim).
  Qualifying combos are deduped to the best row per (country, factor)
  (per_pair_cap), and the country's signal is the sum of direction x
  confidence over its qualifying pairs. The live queue's global cap of 25
  rows is a review-workload device, NOT part of the economic rule, and is
  deliberately not applied here (pre-declared deviation).

The output signal at month label T uses the return spine only through label
T, so in the harness it is traded with publication_lag_months=0 against
returns realized from month T+1 (align_monthly joins month M to M+1..M+h).

DEPENDENCIES:
- duckdb, pandas, numpy, scipy, pyyaml (project venv)

USAGE:
 python scripts/loop/build_triptych_signal.py                 # full build
 python scripts/loop/build_triptych_signal.py --factors REER  # subset (debug)
 python scripts/loop/build_triptych_signal.py --truncate-input 2020-12 \
     --factors REER --out /tmp/trunc.parquet --no-db          # lookahead canary
 python scripts/loop/build_triptych_signal.py --workers 4

NOTES:
- No-lookahead property (verified by the truncation canary): the value at
  month T depends only on factor labels <= T-1, return-spine labels <= T,
  and record forward-windows completed by T. Truncating all input at month
  X >= T leaves the value at T bit-identical.
- Spearman uses scipy.stats.rankdata (average ties) - numerically identical
  to the kernel's _rank_avg_ties, C-speed for the ~30M expanding calls.
- FAIL-IS-FAIL: zero qualifying rows over the whole history raises.
=============================================================================
"""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from bisect import insort
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import rankdata

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.loop.loopdb import LOOP_DIR, T2_UNIVERSE, loop_connection
from scripts.loop.build_triptych_scan import forward_panels, load_config, load_pivots
from scripts.loop.triptych_kernel import (
    BUCKET_COUNT,
    PIT_MIN_OBS,
    assign_bucket,
    cross_country_z,
    expanding_z,
    thresholds_from_sorted,
)

OUT_PARQUET = LOOP_DIR / "triptych_signal_monthly.parquet"
EVAL_START = "2004-01"      # first evaluation month (harness starts 2008)
AVAIL_LAG_MONTHS = 1        # current-signal availability embargo (see header)
MIN_RAW_OBS = 24            # same per-country floor as the scan


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} [triptych_signal] {msg}", flush=True)


# --------------------------------------------------------------------------- #
# Kernel-parity helpers
# --------------------------------------------------------------------------- #
def pit_buckets_with_threshold_history(signals: np.ndarray, k: int = BUCKET_COUNT,
                                       min_obs: int = PIT_MIN_OBS):
    """assign_buckets_pit PLUS the threshold list after every insertion.

    Identical insert-then-assign order to the kernel; thr_hist[i] are the
    thresholds available after record i (what the live scan's 'final
    thresholds' would have been if record i were the last one)."""
    sorted_so_far: list[float] = []
    n = len(signals)
    buckets = np.zeros(n, dtype=int)
    thr_hist: list[list[float]] = []
    for i, x in enumerate(np.asarray(signals, dtype=float)):
        insort(sorted_so_far, float(x))
        thr = thresholds_from_sorted(sorted_so_far, k)
        thr_hist.append(thr)
        if len(sorted_so_far) >= min_obs:
            b = assign_bucket(float(x), thr)
            buckets[i] = b if b is not None else 0
    return buckets, thr_hist


def fast_spearman(rank_s: np.ndarray, f: np.ndarray, horizon: int):
    """Kernel spearman_ic with a precomputed signal rank vector."""
    n = len(rank_s)
    if n < 6:
        return None, None
    ry = rankdata(f)                      # average ties, matches _rank_avg_ties
    mx, my = rank_s.mean(), ry.mean()
    num = float(((rank_s - mx) * (ry - my)).sum())
    den = math.sqrt(float(((rank_s - mx) ** 2).sum()) * float(((ry - my) ** 2).sum()))
    if den == 0.0:
        return None, None
    ic = num / den
    if not math.isfinite(ic):
        return None, None
    n_eff = max(4.0, n / max(1, horizon))
    denom = 1 - ic * ic
    t = ic * math.sqrt((n_eff - 2) / denom) if denom > 0 else None
    return ic, t


def _linfit(xs: np.ndarray, ys: np.ndarray):
    """Kernel linear_fit on numpy arrays -> (slope, intercept, r2)."""
    n = len(xs)
    if n < 2:
        return None, None, None
    mx, my = xs.mean(), ys.mean()
    sxx = float(((xs - mx) ** 2).sum())
    sxy = float(((xs - mx) * (ys - my)).sum())
    syy = float(((ys - my) ** 2).sum())
    if sxx == 0.0:
        return None, None, None
    slope = sxy / sxx
    icept = my - slope * mx
    r2 = (sxy * sxy) / (sxx * syy) if syy > 0 else None
    return slope, icept, r2


# --------------------------------------------------------------------------- #
# Per-factor worker: walk-forward queue rows for every eval month
# --------------------------------------------------------------------------- #
def signal_factor(args: tuple) -> list[tuple]:
    """Returns [(eval_ord, country, dir, confidence, priority), ...] — the
    best qualifying row per (eval month, country) for THIS factor."""
    (factor, pivot, fwd_by_h, norms, modes, broadcast, eval_ords, q) = args
    k = BUCKET_COUNT
    horizons = sorted(fwd_by_h.keys())
    n_eval = len(eval_ords)
    countries = [c for c in pivot.columns if c in set(T2_UNIVERSE)]

    cs_z = None
    if "cross_var_pct" in norms and not broadcast:
        cs_z = pd.DataFrame(cross_country_z(pivot.values),
                            index=pivot.index, columns=pivot.columns)

    # best[(t_idx, country)] = (priority, dir, conf)
    best: dict[tuple[int, str], tuple[float, int, float]] = {}

    for country in countries:
        raw = pivot[country].dropna()
        if len(raw) < MIN_RAW_OBS:
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

            sig_ords = np.array([p.ordinal for p in sig.index], dtype=np.int64)
            sig_vals = sig.values.astype(float)
            # Current signal at eval T = latest obs labeled <= T - AVAIL_LAG
            ci = np.searchsorted(sig_ords, eval_ords - AVAIL_LAG_MONTHS, side="right") - 1
            cur_sig = np.where(ci >= 0, sig_vals[np.clip(ci, 0, None)], np.nan)

            # Per-horizon per-mode stat arrays over eval months
            # stats[h][mode] = dict of np arrays len n_eval
            stats: dict[int, dict[str, dict[str, np.ndarray]]] = {}

            for h in horizons:
                fwd_pivot, ew = fwd_by_h[h]
                if country not in fwd_pivot.columns:
                    continue
                fwd_abs = fwd_pivot[country]
                idx = sig.index.intersection(fwd_abs.dropna().index).sort_values()
                if len(idx) < 2:
                    continue
                s = sig.loc[idx].values.astype(float)
                f_abs = fwd_abs.loc[idx].values.astype(float)
                f_rel = f_abs - ew.loc[idx].values.astype(float)
                rec_ords = np.array([p.ordinal for p in idx], dtype=np.int64)

                buckets, thr_hist = pit_buckets_with_threshold_history(s)
                mask = buckets > 0
                if not mask.any():
                    continue
                ms, mb = s[mask], buckets[mask]
                m_ords = rec_ords[mask]
                mf = {"absolute": f_abs[mask], "relative": f_rel[mask]}

                # Cumulative per-bucket stats over the bucketed record order
                onehot = mb[:, None] == np.arange(1, k + 1)[None, :]
                cnt = np.cumsum(onehot, axis=0)
                cums = {m: np.cumsum(onehot * mf[m][:, None], axis=0) for m in modes}
                cumh = {m: np.cumsum(onehot * (mf[m] > 0)[:, None], axis=0) for m in modes}

                # Prefix index per eval month (records completed by T)
                p_all = np.searchsorted(rec_ords, eval_ords - h, side="right")
                p_msk = np.searchsorted(m_ords, eval_ords - h, side="right")

                # Expanding stats per UNIQUE usable prefix (>= queue min)
                uniq = np.unique(p_msk[p_msk >= int(q["min_records"])])
                per_p: dict[int, dict] = {}
                for p in uniq:
                    rank_s = rankdata(ms[:p])
                    entry: dict[str, dict] = {}
                    for m in modes:
                        ic, ic_t = fast_spearman(rank_s, mf[m][:p], h)
                        c_row, s_row, h_row = cnt[p - 1], cums[m][p - 1], cumh[m][p - 1]
                        present = c_row > 0
                        avgs = np.where(present, s_row / np.maximum(c_row, 1), np.nan)
                        hits = np.where(present, h_row / np.maximum(c_row, 1), np.nan)
                        xs = np.arange(1, k + 1, dtype=float)[present]
                        slope, icept, r2 = _linfit(xs, avgs[present])
                        entry[m] = {"ic_t": ic_t, "slope": slope, "icept": icept,
                                    "r2": r2, "cnt": c_row, "avg": avgs, "hit": hits}
                    per_p[int(p)] = entry

                hstat: dict[str, dict[str, np.ndarray]] = {}
                for m in modes:
                    hstat[m] = {
                        "exists": p_msk >= 2,          # scan emits a row at n>=2
                        "ok": np.zeros(n_eval, bool),  # passes hard stat gates
                        "dir": np.zeros(n_eval, np.int8),
                        "ic_t": np.full(n_eval, np.nan),
                        "r2": np.full(n_eval, np.nan),
                        "sample": np.zeros(n_eval),
                        "ic_s": np.zeros(n_eval),
                        "hit_s": np.zeros(n_eval),
                        "aligned": np.zeros(n_eval, np.int8),
                        "dec": np.zeros(n_eval, np.int8),
                        "cur_n": np.zeros(n_eval, np.int32),
                    }

                for t in range(n_eval):
                    p = int(p_msk[t])
                    if p < int(q["min_records"]) or p_all[t] < 2:
                        continue
                    cs = cur_sig[t]
                    if not math.isfinite(cs):
                        continue
                    thr = thr_hist[p_all[t] - 1]
                    dec = assign_bucket(float(cs), thr)
                    if dec is None:
                        continue
                    e = per_p[p]
                    for m in modes:
                        em = e[m]
                        cur_n = int(em["cnt"][dec - 1])
                        cur_avg = em["avg"][dec - 1]
                        cur_hit = em["hit"][dec - 1]
                        st = hstat[m]
                        st["dec"][t] = dec
                        st["cur_n"][t] = cur_n
                        if cur_n >= 5 and math.isfinite(cur_avg) and cur_avg != 0:
                            st["dir"][t] = 1 if cur_avg > 0 else -1
                        ic_t, r2 = em["ic_t"], em["r2"]
                        if ic_t is None or r2 is None:
                            continue
                        st["ic_t"][t] = ic_t
                        st["r2"][t] = r2
                        st["sample"][t] = min(1.0, cur_n / 20.0)
                        st["ic_s"][t] = min(1.0, abs(ic_t) / 2.5)
                        st["hit_s"][t] = (abs(cur_hit - 0.5) * 2
                                          if math.isfinite(cur_hit) else 0.0)
                        if (em["slope"] is not None and em["icept"] is not None
                                and math.isfinite(cur_avg) and cur_avg != 0):
                            pred = em["slope"] * dec + em["icept"]
                            if pred != 0 and math.copysign(1, pred) == math.copysign(1, cur_avg):
                                st["aligned"][t] = 1
                        st["ok"][t] = True
                stats[h] = hstat

            if not stats:
                continue

            # Horizon agreement + gates + contribution, per mode
            for m in modes:
                hs = [h for h in horizons if h in stats and m in stats[h]]
                if not hs:
                    continue
                exists = np.stack([stats[h][m]["exists"] for h in hs])   # H x T
                dirs = np.stack([stats[h][m]["dir"] for h in hs])
                n_sib = exists.sum(axis=0)
                for hi, h in enumerate(hs):
                    st = stats[h][m]
                    d = dirs[hi]
                    same = ((dirs == d[None, :]) & exists & (d[None, :] != 0)).sum(axis=0)
                    with np.errstate(invalid="ignore", divide="ignore"):
                        agree = np.where((n_sib > 1) & (d != 0) & exists[hi],
                                         (same - 1) / np.maximum(n_sib - 1, 1), 0.0)
                    conf = ((st["sample"] + st["ic_s"] + st["hit_s"] + agree) / 4.0
                            ) * st["aligned"]
                    qual = (st["ok"]
                            & (st["cur_n"] >= int(q["min_bucket_obs"]))
                            & (np.abs(np.nan_to_num(st["ic_t"])) >= float(q["min_abs_ic_t"]))
                            & (np.nan_to_num(st["r2"]) >= float(q["min_r2"]))
                            & (d != 0)
                            & ((st["dec"] <= int(q["extreme_low_decile"]))
                               | (st["dec"] >= int(q["extreme_high_decile"])))
                            & (conf >= float(q["min_confidence"])))
                    if not qual.any():
                        continue
                    prio = (conf * np.minimum(np.abs(np.nan_to_num(st["ic_t"])), 6.0) / 6.0
                            * np.minimum(np.nan_to_num(st["r2"]), 1.0))
                    for t in np.flatnonzero(qual):
                        key = (int(t), country)
                        cand = (float(prio[t]), int(d[t]), float(conf[t]))
                        if key not in best or cand[0] > best[key][0]:
                            best[key] = cand

    return [(int(eval_ords[t]), c, dr, cf, pr) for (t, c), (pr, dr, cf) in best.items()]


# --------------------------------------------------------------------------- #
def build(args) -> pd.DataFrame:
    cfg = load_config()
    q = cfg["queue"]
    factor_filter = ({f.strip() for f in args.factors.split(",")}
                     if args.factors else None)

    log("loading pivots from DuckDB ...")
    ret_pivot, factors = load_pivots(cfg, factor_filter)

    if args.truncate_input:
        cut = pd.Period(args.truncate_input, freq="M")
        ret_pivot = ret_pivot[ret_pivot.index <= cut]
        factors = {n: (piv[piv.index <= cut], tbl) for n, (piv, tbl) in factors.items()}
        log(f"CANARY: all input truncated at {cut}")

    last = ret_pivot.index.max()
    eval_months = pd.period_range(EVAL_START, last, freq="M")
    eval_ords = np.array([p.ordinal for p in eval_months], dtype=np.int64)
    log(f"return spine to {last}; {len(factors)} factors; "
        f"{len(eval_months)} eval months from {EVAL_START}")

    fwd_by_h = forward_panels(ret_pivot, list(cfg["horizons"]))
    norms = list(cfg["normalizations"])
    modes = list(cfg["return_modes"])

    tasks = []
    for name, (pivot, _table) in factors.items():
        row_std = pivot.std(axis=1, skipna=True)
        broadcast = bool((row_std.fillna(0) < 1e-12).mean() > 0.9)
        tasks.append((name, pivot, fwd_by_h, norms, modes, broadcast, eval_ords, q))

    t0 = time.time()
    log(f"walk-forward over {len(tasks)} factors on {args.workers} workers ...")
    contrib: list[tuple] = []
    if args.workers <= 1 or len(tasks) == 1:
        for task in tasks:
            contrib.extend(signal_factor(task))
    else:
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            for i, rows in enumerate(pool.map(signal_factor, tasks, chunksize=1), 1):
                contrib.extend(rows)
                if i % 10 == 0 or i == len(tasks):
                    log(f"  {i}/{len(tasks)} factors ({len(contrib):,} pair-months, "
                        f"{time.time() - t0:.0f}s)")

    if not contrib:
        raise RuntimeError("walk-forward produced zero qualifying rows (FAIL-IS-FAIL)")

    pairs = pd.DataFrame(contrib, columns=["ord", "country", "dir", "conf", "priority"])
    lean = (pairs.assign(w=pairs["dir"] * pairs["conf"])
            .groupby(["ord", "country"])
            .agg(value=("w", "sum"), n=("w", "size"))
            .reset_index())

    # Dense emission: every country with a return-spine observation that month
    active = ret_pivot.reindex(eval_months).notna()
    grid = [(o, c) for o, p in zip(eval_ords, eval_months)
            for c in active.columns if c in set(T2_UNIVERSE) and active.loc[p, c]]
    dense = pd.DataFrame(grid, columns=["ord", "country"])
    dense = dense.merge(lean, on=["ord", "country"], how="left")
    dense[["value", "n"]] = dense[["value", "n"]].fillna(0.0)
    dense["date"] = pd.PeriodIndex.from_ordinals(
        dense["ord"].to_numpy(), freq="M").to_timestamp()

    out = pd.concat([
        dense.assign(variable="TRIPTYCH_QUEUE_LEAN")[["date", "country", "value", "variable"]],
        dense.assign(variable="TRIPTYCH_QUEUE_N", value=dense["n"])[
            ["date", "country", "value", "variable"]],
    ], ignore_index=True)
    out["source"] = "triptych"

    nz = dense[dense["value"] != 0].groupby("ord").size()
    log(f"pair-months: {len(pairs):,}; months with any prior: {len(nz)}/{len(eval_months)}; "
        f"median active countries/month (2008+): "
        f"{nz[nz.index >= pd.Period('2008-01', 'M').ordinal].median():.0f}")
    return out


def write_output(out: pd.DataFrame, path: Path, to_db: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False)
    log(f"wrote {path} ({len(out):,} rows)")
    if not to_db:
        return
    con = loop_connection()
    try:
        con.execute("DROP TABLE IF EXISTS triptych_signal_monthly")
        con.execute(
            f"CREATE TABLE triptych_signal_monthly AS SELECT * FROM read_parquet('{path}')")
        n = con.execute("SELECT count(*) FROM triptych_signal_monthly").fetchone()[0]
        log(f"loop table triptych_signal_monthly rebuilt ({n:,} rows)")
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Walk-forward Triptych queue-rule signal (monthly, PIT).")
    parser.add_argument("--factors", default=None, help="comma-separated subset (debug)")
    parser.add_argument("--workers", type=int,
                        default=max(1, (os.cpu_count() or 8) - 2))
    parser.add_argument("--truncate-input", default=None, metavar="YYYY-MM",
                        help="lookahead canary: truncate ALL input at this month")
    parser.add_argument("--out", default=None, help="alternate output parquet path")
    parser.add_argument("--no-db", action="store_true",
                        help="skip the loop-DB table rebuild (canary runs)")
    args = parser.parse_args()

    out = build(args)
    write_output(out, Path(args.out) if args.out else OUT_PARQUET, not args.no_db)
    return 0


if __name__ == "__main__":
    sys.exit(main())
