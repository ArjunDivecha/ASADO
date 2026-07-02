#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: triptych_kernel.py (shared module, not run directly)
=============================================================================

INPUT FILES:
- None (pure functions — callers pass numpy arrays / lists).

OUTPUT FILES:
- None (pure functions — no file I/O).

VERSION: 1.0
LAST UPDATED: 2026-07-02
AUTHOR: Arjun Divecha (built by agent session, Triptych Prediction Prior Layer PRD Phase 2)

DESCRIPTION:
The Triptych analytics kernel, ported to Python from the Triptych tool's
app/assets/core.js + triptych.js so ASADO can compute the SAME bucket
statistics the visual tool shows — but directly from DuckDB data, with a
genuine point-in-time (PIT) mode that has no lookahead bias.

Semantics mirrored exactly from core.js (verified line-by-line 2026-07-02):
- Expanding z-score      : Welford, POPULATION variance (m2/count), signal=0
                           while count<2 or std==0.
- Cross-country z        : (value - peer_mean) / peer_pop_std, peers EXCLUDE
                           self; None when <2 countries have data; 0 when
                           peer std is 0. (Triptych calls this
                           "cross_var_pct" — the name is historical.)
- Quantile               : linear interpolation on the sorted sample
                           (matches JS quantile()).
- Bucket thresholds      : k-1 quantiles at 1/k .. (k-1)/k; [] if <2 obs.
- PIT bucketing          : records in chronological order; each record's
                           signal is inserted into the running sorted list
                           BEFORE assignment; bucket=None until
                           PIT_MIN_OBS(=36) observations are accumulated;
                           thresholds at time t use ONLY signals of records
                           at or before t. No future observation can move a
                           past threshold.
- Bucket t-stat          : sample sd (n-1), overlap-adjusted
                           n_eff = max(2, n/horizon), None when n<3.
- Spearman IC            : Pearson on average-ties ranks, None when n<6;
                           t = ic*sqrt((n_eff-2)/(1-ic^2)),
                           n_eff = max(4, n/horizon).
- Linear fit             : OLS of bucket-average forward return on bucket
                           index (1..k) over buckets with finite averages.

Forward returns are computed by the CALLER (build_triptych_scan.py) from
monthly total-return index levels: fwd = TRI[t+h]/TRI[t] - 1; the relative
mode subtracts the equal-weight mean forward return across all countries
with valid data at the same date (mirrors buildForwardRecords).

FAIL-IS-FAIL: forward-return variables (1MRet/3MRet/... family) are refused
as signals by is_forbidden_signal(); callers must check it.

DEPENDENCIES:
- numpy (project venv)

USAGE:
 from scripts.loop.triptych_kernel import (
     expanding_z, cross_country_z, assign_buckets_pit,
     assign_buckets_full, bucket_stats, spearman_ic, linear_fit, ...)
=============================================================================
"""

from __future__ import annotations

import math
import re
from bisect import insort
from dataclasses import dataclass

import numpy as np

# --------------------------------------------------------------------------- #
# Constants — mirror core.js
# --------------------------------------------------------------------------- #
PIT_MIN_OBS = 36          # months of history before PIT bucketing starts
BUCKET_COUNT = 10         # deciles (Triptych default)
HORIZON_OPTIONS = [1, 3, 6, 12, 24, 36]
NORMALIZATIONS = ["raw", "history_z", "cross_var_pct"]
RETURN_MODES = ["absolute", "relative"]

# LOOKAHEAD TRAP (house rule): T2 NMRet variables are FORWARD returns anchored
# at the window start — optimizer targets, never signals.
_FORBIDDEN_SIGNAL_RE = re.compile(r"^\s*\d+\s*[MD]\s*Ret\s*$", re.IGNORECASE)


def is_forbidden_signal(variable: str) -> bool:
    """True when a variable is a forward-return series and must NOT be a signal."""
    return bool(_FORBIDDEN_SIGNAL_RE.match(str(variable)))


# --------------------------------------------------------------------------- #
# Signal construction
# --------------------------------------------------------------------------- #
def expanding_z(values: np.ndarray) -> np.ndarray:
    """Welford expanding z-score, population variance — mirrors
    buildExpandingZScoreSeries. Input must be finite values in
    chronological order; output has the same length."""
    out = np.zeros(len(values), dtype=float)
    count = 0
    mean = 0.0
    m2 = 0.0
    for i, x in enumerate(values):
        count += 1
        delta = x - mean
        mean += delta / count
        m2 += delta * (x - mean)
        if count < 2:
            out[i] = 0.0
            continue
        var = max(0.0, m2 / count)
        std = math.sqrt(var)
        out[i] = 0.0 if (not math.isfinite(std) or std == 0.0) else (x - mean) / std
    return out


def cross_country_z(pivot: np.ndarray) -> np.ndarray:
    """Cross-sectional z vs peers (self EXCLUDED), population std — mirrors
    percentileVsCrossCountry, vectorised over a (dates x countries) matrix
    that may contain NaN. Returns a same-shape matrix: NaN where the tool
    would return null (fewer than 2 countries with data, or no peers)."""
    x = np.asarray(pivot, dtype=float)
    finite = np.isfinite(x)
    n = finite.sum(axis=1, keepdims=True).astype(float)          # incl. self
    s = np.where(finite, x, 0.0).sum(axis=1, keepdims=True)
    s2 = np.where(finite, x * x, 0.0).sum(axis=1, keepdims=True)

    n_peer = np.where(finite, n - 1, n)                           # excl. self
    with np.errstate(invalid="ignore", divide="ignore"):
        peer_mean = (s - np.where(finite, x, 0.0)) / n_peer
        peer_msq = (s2 - np.where(finite, x * x, 0.0)) / n_peer
        peer_var = np.maximum(0.0, peer_msq - peer_mean**2)
        peer_std = np.sqrt(peer_var)
        z = (x - peer_mean) / peer_std

    # JS: arr.length < 2 -> null; peers empty -> null; std == 0 -> 0.
    z = np.where(peer_std == 0.0, 0.0, z)
    z = np.where(finite & (n >= 2) & (n_peer >= 1), z, np.nan)
    return z


# --------------------------------------------------------------------------- #
# Quantiles, thresholds, bucket assignment
# --------------------------------------------------------------------------- #
def quantile(sorted_vals, p: float):
    """Linear-interpolation quantile on an ascending list — mirrors JS."""
    if not len(sorted_vals):
        return None
    idx = (len(sorted_vals) - 1) * p
    lo = math.floor(idx)
    hi = math.ceil(idx)
    if lo == hi:
        return sorted_vals[lo]
    w = idx - lo
    return sorted_vals[lo] * (1 - w) + sorted_vals[hi] * w


def thresholds_from_sorted(sorted_vals, k: int):
    """k-1 thresholds at 1/k .. (k-1)/k quantiles; [] when <2 obs."""
    if len(sorted_vals) < 2:
        return []
    return [quantile(sorted_vals, i / k) for i in range(1, k)]


def assign_bucket(value: float, thresholds) -> int | None:
    if not thresholds or not math.isfinite(value):
        return None
    for i, t in enumerate(thresholds):
        if value <= t:
            return i + 1
    return len(thresholds) + 1


def assign_buckets_full(signals: np.ndarray, k: int = BUCKET_COUNT):
    """Full-sample (descriptive) thresholds. Returns (buckets, thresholds);
    buckets is an int array with 0 meaning 'no bucket'."""
    finite = np.asarray(signals, dtype=float)
    srt = sorted(finite[np.isfinite(finite)].tolist())
    thresholds = thresholds_from_sorted(srt, k)
    buckets = np.zeros(len(finite), dtype=int)
    for i, sig in enumerate(finite):
        b = assign_bucket(sig, thresholds)
        buckets[i] = b if b is not None else 0
    return buckets, thresholds


def assign_buckets_pit(signals: np.ndarray, k: int = BUCKET_COUNT,
                       min_obs: int = PIT_MIN_OBS):
    """Point-in-time thresholds — mirrors assignBucketsToRecords(mode='pit').

    signals MUST be in chronological order. Each signal is inserted into the
    running sorted list BEFORE its own bucket is assigned (matches core.js
    binaryInsert-then-assign). bucket=0 during the warm-up (< min_obs).
    Returns (buckets, final_thresholds)."""
    sorted_so_far: list[float] = []
    buckets = np.zeros(len(signals), dtype=int)
    for i, sig in enumerate(np.asarray(signals, dtype=float)):
        insort(sorted_so_far, float(sig))
        if len(sorted_so_far) < min_obs:
            continue
        b = assign_bucket(float(sig), thresholds_from_sorted(sorted_so_far, k))
        buckets[i] = b if b is not None else 0
    return buckets, thresholds_from_sorted(sorted_so_far, k)


# --------------------------------------------------------------------------- #
# Statistics — mirror core.js
# --------------------------------------------------------------------------- #
def bucket_t_stat(vals: np.ndarray, horizon_months: int) -> float | None:
    """Overlap-adjusted one-sample t: n_eff = max(2, n/horizon)."""
    n = len(vals)
    if n < 3:
        return None
    mean = float(np.mean(vals))
    sd = float(np.std(vals, ddof=1))
    if not math.isfinite(sd) or sd == 0.0:
        return None
    n_eff = max(2.0, n / max(1, horizon_months))
    return mean / (sd / math.sqrt(n_eff))


def _rank_avg_ties(vals: np.ndarray) -> np.ndarray:
    """Average-ties ranks (1-based) — mirrors rankArray."""
    order = np.argsort(vals, kind="stable")
    ranks = np.empty(len(vals), dtype=float)
    i = 0
    sv = vals[order]
    while i < len(sv):
        j = i
        while j + 1 < len(sv) and sv[j + 1] == sv[i]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        ranks[order[i:j + 1]] = avg_rank
        i = j + 1
    return ranks


def spearman_ic(signals: np.ndarray, fwd: np.ndarray,
                horizon_months: int) -> tuple[float | None, float | None]:
    """Spearman IC of signal vs forward return with overlap-adjusted t."""
    n = len(signals)
    if n < 6:
        return None, None
    rx = _rank_avg_ties(np.asarray(signals, dtype=float))
    ry = _rank_avg_ties(np.asarray(fwd, dtype=float))
    mx, my = rx.mean(), ry.mean()
    num = float(((rx - mx) * (ry - my)).sum())
    den = math.sqrt(float(((rx - mx) ** 2).sum()) * float(((ry - my) ** 2).sum()))
    if den == 0.0:
        return None, None
    ic = num / den
    if not math.isfinite(ic):
        return None, None
    n_eff = max(4.0, n / max(1, horizon_months))
    denom = 1 - ic * ic
    t = ic * math.sqrt((n_eff - 2) / denom) if denom > 0 else None
    return ic, t


def linear_fit(xs, ys) -> tuple[float | None, float | None, float | None]:
    """OLS y on x -> (slope, intercept, r2); Nones when underdetermined."""
    n = len(xs)
    if n < 2:
        return None, None, None
    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)
    mx, my = xs.mean(), ys.mean()
    sxx = float(((xs - mx) ** 2).sum())
    sxy = float(((xs - mx) * (ys - my)).sum())
    syy = float(((ys - my) ** 2).sum())
    if sxx == 0.0:
        return None, None, None
    slope = sxy / sxx
    intercept = my - slope * mx
    r2 = (sxy * sxy) / (sxx * syy) if syy > 0 else None
    return slope, intercept, r2


# --------------------------------------------------------------------------- #
# Bucketed record analysis (one combo)
# --------------------------------------------------------------------------- #
@dataclass
class ComboStats:
    """Everything Triptych's Deep-Dive shows for one
    (factor, country, normalization, return_mode, horizon, threshold_mode)."""
    threshold_mode: str            # 'pit' | 'full'
    n_records: int                 # bucketed records (PIT: post-warm-up)
    current_signal: float | None
    current_bucket: int | None     # latest signal vs FINAL thresholds
    bucket_n: list[int]            # per-bucket record count (len k)
    bucket_avg: list[float | None]
    bucket_hit: list[float | None]
    bucket_t: list[float | None]
    ic: float | None
    ic_t: float | None
    slope: float | None
    r2: float | None
    spread: float | None           # top-bucket avg minus bottom-bucket avg


def analyze_combo(signals: np.ndarray, fwd: np.ndarray,
                  current_signal: float | None,
                  horizon_months: int, threshold_mode: str,
                  k: int = BUCKET_COUNT) -> ComboStats | None:
    """Full bucket analysis of one combo. signals/fwd are aligned arrays of
    the record set (finite signal AND finite forward return), chronological.
    current_signal is the latest finite signal of the FULL series (it may
    postdate the last record because recent months have no forward return yet
    — mirrors the tool's 'current decile')."""
    signals = np.asarray(signals, dtype=float)
    fwd = np.asarray(fwd, dtype=float)
    if len(signals) < 2:
        return None

    if threshold_mode == "pit":
        buckets, final_thresholds = assign_buckets_pit(signals, k)
    elif threshold_mode == "full":
        buckets, final_thresholds = assign_buckets_full(signals, k)
    else:
        raise ValueError(f"threshold_mode must be 'pit' or 'full', got {threshold_mode!r}")

    mask = buckets > 0
    n_records = int(mask.sum())
    if n_records < 2:
        return None

    bucket_n: list[int] = []
    bucket_avg: list[float | None] = []
    bucket_hit: list[float | None] = []
    bucket_t: list[float | None] = []
    for b in range(1, k + 1):
        vals = fwd[buckets == b]
        if len(vals) == 0:
            bucket_n.append(0)
            bucket_avg.append(None)
            bucket_hit.append(None)
            bucket_t.append(None)
        else:
            bucket_n.append(int(len(vals)))
            bucket_avg.append(float(np.mean(vals)))
            bucket_hit.append(float((vals > 0).mean()))
            bucket_t.append(bucket_t_stat(vals, horizon_months))

    # IC over bucketed records only (PIT: warm-up rows excluded — they had no
    # tradable bucket, so they carry no predictive claim).
    ic, ic_t = spearman_ic(signals[mask], fwd[mask], horizon_months)

    fit_x = [b + 1 for b in range(k) if bucket_avg[b] is not None and math.isfinite(bucket_avg[b])]
    fit_y = [bucket_avg[b - 1] for b in fit_x]
    slope, _icept, r2 = linear_fit(fit_x, fit_y)

    spread = None
    if bucket_avg[0] is not None and bucket_avg[k - 1] is not None:
        spread = bucket_avg[k - 1] - bucket_avg[0]

    current_bucket = None
    if current_signal is not None and math.isfinite(current_signal):
        current_bucket = assign_bucket(float(current_signal), final_thresholds)

    return ComboStats(
        threshold_mode=threshold_mode,
        n_records=n_records,
        current_signal=(float(current_signal)
                        if current_signal is not None and math.isfinite(current_signal) else None),
        current_bucket=current_bucket,
        bucket_n=bucket_n,
        bucket_avg=bucket_avg,
        bucket_hit=bucket_hit,
        bucket_t=bucket_t,
        ic=ic,
        ic_t=ic_t,
        slope=slope,
        r2=r2,
        spread=spread,
    )


# --------------------------------------------------------------------------- #
# Prior confidence — PRD 7.3 deterministic score
# --------------------------------------------------------------------------- #
def confidence_score(stats: ComboStats, neighbor_direction_agreement: float | None = None
                     ) -> tuple[float, str]:
    """PRD 7.3: mean(sample, ic, hit, horizon) x directional-alignment flag.
    0.0 whenever threshold_mode != 'pit' (full-sample views are descriptive
    only and may NEVER carry prior confidence). Returns (score, notes)."""
    if stats.threshold_mode != "pit":
        return 0.0, "full-sample thresholds: descriptive only, no prior confidence"
    b = stats.current_bucket
    if b is None or not (1 <= b <= len(stats.bucket_avg)):
        return 0.0, "no current bucket"
    avg = stats.bucket_avg[b - 1]
    n = stats.bucket_n[b - 1]
    hit = stats.bucket_hit[b - 1]
    if avg is None or n == 0:
        return 0.0, "current bucket has no historical observations"

    # Directional alignment: the monotonic fit's predicted return at the
    # current bucket must agree in sign with the bucket's own average.
    aligned = 0
    if stats.slope is not None and stats.r2 is not None:
        fit_x = [i + 1 for i, a in enumerate(stats.bucket_avg)
                 if a is not None and math.isfinite(a)]
        fit_y = [stats.bucket_avg[i - 1] for i in fit_x]
        slope, icept, _ = linear_fit(fit_x, fit_y)
        if slope is not None:
            pred = slope * b + icept
            if pred != 0 and avg != 0 and math.copysign(1, pred) == math.copysign(1, avg):
                aligned = 1

    sample_score = min(1.0, n / 20.0)
    ic_score = min(1.0, abs(stats.ic_t) / 2.5) if stats.ic_t is not None else 0.0
    hit_score = abs(hit - 0.5) * 2 if hit is not None else 0.0
    horizon_score = (neighbor_direction_agreement
                     if neighbor_direction_agreement is not None else 0.5)
    score = (sample_score + ic_score + hit_score + horizon_score) / 4.0 * aligned

    notes = []
    if n < 10:
        notes.append(f"thin current bucket (n={n})")
    if not aligned:
        notes.append("bucket average disagrees with the monotonic fit direction")
    if stats.ic_t is not None and abs(stats.ic_t) < 1.5:
        notes.append("weak IC t-stat")
    return round(float(score), 4), ("; ".join(notes) if notes else "ok")


def implied_direction(stats: ComboStats, min_bucket_obs: int = 5) -> str:
    """'long' / 'short' / 'neutral' / 'insufficient' for the CURRENT bucket."""
    b = stats.current_bucket
    if b is None:
        return "insufficient"
    avg = stats.bucket_avg[b - 1]
    n = stats.bucket_n[b - 1]
    if avg is None or n < min_bucket_obs:
        return "insufficient"
    if avg > 0:
        return "long"
    if avg < 0:
        return "short"
    return "neutral"
