"""
=============================================================================
SCRIPT NAME: select_gdelt_for_t2.py
=============================================================================

INPUT FILES:
- Data/asado.duckdb :: factor_returns (filtered to source='gdelt_optimizer')

OUTPUT FILES:
- Data/research/gdelt_t2_candidates.csv
    Ranked candidate list with all per-variant metrics. The user reviews
    this and picks the final set to add to T2 Master.
- Data/research/gdelt_t2_candidates_log.txt
    Run summary: counts at each stage, threshold values used, holdout date.

VERSION: 1.0
LAST UPDATED: 2026-04-29
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
Picks a small shortlist of GDELT factors that are robust enough to add to
the T2 Master pipeline, with structural defenses against selection bias.

The 2,312 GDELT factors (1,156 base names x {_CS,_TS}) are too many to
ad-hoc cherry-pick — picking "the best Sharpe" out of that many under the
null gives a ~0.7 annualized Sharpe just from luck. This script applies
five gates in order. Stage 1 is the only judgment-based filter; everything
after is mechanical.

Pipeline:
  1. Economic-prior name filter — only inspect factors matching one of
     the regex patterns in PRIOR_PATTERNS (attention / risk / sentiment /
     goldstein / event aggregates / conflict-theme families). The whole
     point of this stage is to do "selection" before any return data is
     touched, so the shortlist size N is bounded BEFORE the deflated-Sharpe
     correction is computed.
  2. Variant pairing — require the factor's _CS AND _TS variants to
     BOTH be present and BOTH pass every subsequent gate.
  3. Two-half stability — split each variant's return series at its
     median date. Require positive annualized Sharpe in both halves.
     Filters out factors whose entire edge came from one regime.
  4. Deflated Sharpe (Bailey-Lopez de Prado, simplified) — compute the
     expected max Sharpe under the null given N pre-screened factors and
     T months. Subtract from the apparent Sharpe. Require deflated
     Sharpe >= DEFLATED_SHARPE_MIN in BOTH variants.
  5. Correlation pruning — sort survivors by min-deflated-Sharpe across
     variants (worst-of); greedy add to the final list while max pairwise
     correlation with any already-selected factor stays below CORR_CAP.

Holdout: --holdout-end clips the analysis to <= that date so the user
can validate picks on data after that date without ever having peeked.

DEPENDENCIES:
- duckdb, pandas, numpy

USAGE:
  python scripts/select_gdelt_for_t2.py
  python scripts/select_gdelt_for_t2.py --holdout-end 2023-12-31
  python scripts/select_gdelt_for_t2.py --max-picks 5
  python scripts/select_gdelt_for_t2.py --deflated-min 0.5
  python scripts/select_gdelt_for_t2.py --corr-cap 0.5

NOTES:
- All Sharpe values are annualized assuming monthly returns.
- T2's existing equity-side Sharpes are typically in the 0.5-1.0 range;
  picking GDELT factors with deflated Sharpe < 0.3 is unlikely to add
  signal at the optimizer level.
- The script never modifies T2 Master.xlsx; it just produces a CSV the
  user reviews and acts on.
=============================================================================
"""

from __future__ import annotations

import argparse
import math
import re
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

import duckdb
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DUCKDB_PATH = BASE_DIR / "Data" / "asado.duckdb"
OUT_DIR = BASE_DIR / "Data" / "research"
OUT_CSV = OUT_DIR / "gdelt_t2_candidates.csv"
OUT_LOG = OUT_DIR / "gdelt_t2_candidates_log.txt"

# ─── Pre-screen by economic prior ──────────────────────────────────────────
# Each pattern is matched against the BASE factor name (without _CS/_TS).
# Add or remove categories here based on what you believe should matter.
PRIOR_PATTERNS: List[str] = [
    # Attention / news flow
    r"^attention_(fast|slow|trend|shock)(_z)?$",
    r"^country_news_attention$",
    r"^local_attention_share$",
    # Risk tone family
    r"^risk_fast(_z)?$",
    r"^dispersion_fast(_z)?$",
    r"^country_news_risk(_raw)?$",
    r"^monthly_risk(_rank_pct)?$",
    r"^monthly_metronome(_rank_pct)?$",
    r"^monthly_defensive(_rank_pct)?$",
    # Sentiment momentum
    r"^sentiment_(fast|slow|trend)(_z)?$",
    r"^country_news_sentiment(_raw)?$",
    r"^local_tone(_fast)?(_z)?$",
    r"^foreign_tone(_fast)?(_z)?$",
    r"^local_foreign_gap(_z)?$",
    r"^tone_(dispersion|wavg_wordcount|mean|p50|p10|p90)(_z)?$",
    # Goldstein / event aggregates
    r"^event_goldstein_(mean|min)(_fast|_trend|_z)?$",
    r"^event_n_total(_fast|_trend|_z)?$",
    r"^event_n_quad[1-4](_fast|_trend|_z)?$",
    r"^event_avgtone_mean(_fast|_trend|_z)?$",
    r"^event_persistence_[37]d(_fast|_trend|_z)?$",
    # High-signal conflict / risk themes (WB_-prefixed and bare)
    r"^theme_(WB_\d+_)?(PROTEST|ARMEDCONFLICT|KILL|TERROR|VIOLENCE|CRISIS|"
    r"CRIME|CONFLICT|UNREST|REBELLION|REFUGEE|MILITARY|WAR|TAX_FNCACT_REPORTER)",
    # GCAM Loughran-McDonald financial sentiment (relevant for markets)
    r"^gcam_lm_(negative|positive|uncertainty|litigious|"
    r"modal_strong|modal_weak)_mean(_fast|_slow|_trend|_z)?$",
]

VARIANTS = ("_CS", "_TS")

# ─── Defaults (overridable via CLI) ────────────────────────────────────────
DEFAULT_DEFLATED_SHARPE_MIN = 0.3   # net of multiple-testing adjustment, annualized
DEFAULT_CORR_CAP = 0.6              # pairwise monthly-return correlation cap
DEFAULT_MAX_PICKS = 8                # stop after this many factors selected
DEFAULT_HALF_SHARPE_MIN = 0.0        # each half must clear this
MIN_OBS_PER_HALF = 24                # months — below this the Sharpe is too noisy

# Bailey-LdP deflated-Sharpe constants
EULER_GAMMA = 0.5772156649015329


# ─── Helpers ───────────────────────────────────────────────────────────────
def annualized_sharpe(returns: pd.Series) -> float:
    """Annualized Sharpe for a monthly return series (no rf adjustment)."""
    if returns.empty or returns.std(ddof=1) == 0 or pd.isna(returns.std(ddof=1)):
        return float("nan")
    return float(returns.mean() / returns.std(ddof=1) * math.sqrt(12))


def expected_max_sharpe_under_null(N: int, T: int) -> float:
    """Bailey-LdP expected best-of-N Sharpe under H0: SR=0, T monthly obs.

    Returns annualized SR units. Approximation:
        E[max_SR_period] ≈ sqrt(V) × [(1-γ)Φ⁻¹(1-1/N) + γΦ⁻¹(1-1/(N·e))]
    where V[SR_period] ≈ 1/(T-1) under the normal-iid null.
    """
    if N <= 1 or T <= 2:
        return 0.0
    from scipy.stats import norm
    a = norm.ppf(1.0 - 1.0 / N)
    b = norm.ppf(1.0 - 1.0 / (N * math.e))
    period_max = ((1 - EULER_GAMMA) * a + EULER_GAMMA * b)
    var_sr_period = 1.0 / (T - 1)
    period_max *= math.sqrt(var_sr_period)
    return period_max * math.sqrt(12)


def matches_any(name: str, patterns: List[re.Pattern]) -> bool:
    return any(p.search(name) for p in patterns)


# ─── Pipeline stages ───────────────────────────────────────────────────────
def stage_1_prior_filter(returns_df: pd.DataFrame) -> List[str]:
    """Return list of base factor names matching the economic-prior patterns."""
    compiled = [re.compile(p) for p in PRIOR_PATTERNS]
    base_names = sorted({
        name[:-3] for name in returns_df["factor"].unique()
        if name.endswith(VARIANTS)
    })
    matched = [n for n in base_names if matches_any(n, compiled)]
    return matched


def stage_2_variant_pairing(returns_df: pd.DataFrame, base_names: List[str]) -> List[str]:
    """Keep only base names whose _CS AND _TS both exist in returns_df."""
    have = set(returns_df["factor"].unique())
    paired = [b for b in base_names if (b + "_CS") in have and (b + "_TS") in have]
    return paired


def compute_factor_metrics(
    pivot: pd.DataFrame, factor_full: str
) -> dict:
    """Per-variant Sharpe metrics across full window, halves, and obs counts."""
    series = pivot[factor_full].dropna()
    n_total = len(series)
    if n_total == 0:
        return {"n": 0}

    median_date = series.index[n_total // 2]
    h1 = series[series.index <= median_date]
    h2 = series[series.index > median_date]
    return {
        "n": n_total,
        "n_h1": len(h1),
        "n_h2": len(h2),
        "sharpe": annualized_sharpe(series),
        "sharpe_h1": annualized_sharpe(h1),
        "sharpe_h2": annualized_sharpe(h2),
        "mean_monthly": float(series.mean()),
        "std_monthly": float(series.std(ddof=1)),
    }


def stage_3_4_score_and_filter(
    returns_df: pd.DataFrame,
    paired: List[str],
    holdout_end: pd.Timestamp | None,
    deflated_min: float,
    half_min: float,
) -> Tuple[pd.DataFrame, float]:
    """Compute Sharpe metrics + deflated-Sharpe gate. Returns (survivors_df, deflation_term)."""
    rows = []
    df = returns_df.copy()
    if holdout_end is not None:
        df = df[df["date"] <= holdout_end]
    pivot = df.pivot(index="date", columns="factor", values="value").sort_index()

    # N = number of variants tested (= 2 * paired). Count both _CS and _TS toward N.
    N = 2 * len(paired)
    # T = average non-null obs across paired variants (rough)
    T_estimates = []
    for base in paired:
        for v in VARIANTS:
            full = base + v
            if full in pivot.columns:
                T_estimates.append(pivot[full].notna().sum())
    T = int(np.median(T_estimates)) if T_estimates else 0
    deflation_term = expected_max_sharpe_under_null(N, T)

    for base in paired:
        cs_name, ts_name = base + "_CS", base + "_TS"
        cs = compute_factor_metrics(pivot, cs_name)
        ts = compute_factor_metrics(pivot, ts_name)
        if cs.get("n", 0) < 2 * MIN_OBS_PER_HALF or ts.get("n", 0) < 2 * MIN_OBS_PER_HALF:
            continue
        if cs["n_h1"] < MIN_OBS_PER_HALF or cs["n_h2"] < MIN_OBS_PER_HALF:
            continue
        if ts["n_h1"] < MIN_OBS_PER_HALF or ts["n_h2"] < MIN_OBS_PER_HALF:
            continue

        cs_dsr = cs["sharpe"] - deflation_term
        ts_dsr = ts["sharpe"] - deflation_term

        # Stage 3: half-positivity in both variants
        half_ok = (
            cs["sharpe_h1"] > half_min and cs["sharpe_h2"] > half_min
            and ts["sharpe_h1"] > half_min and ts["sharpe_h2"] > half_min
        )
        # Stage 4: deflated Sharpe >= threshold in both variants
        defl_ok = cs_dsr >= deflated_min and ts_dsr >= deflated_min

        rows.append({
            "factor": base,
            "n_months": cs["n"],
            "cs_sharpe": cs["sharpe"],
            "cs_sharpe_h1": cs["sharpe_h1"],
            "cs_sharpe_h2": cs["sharpe_h2"],
            "cs_deflated_sharpe": cs_dsr,
            "ts_sharpe": ts["sharpe"],
            "ts_sharpe_h1": ts["sharpe_h1"],
            "ts_sharpe_h2": ts["sharpe_h2"],
            "ts_deflated_sharpe": ts_dsr,
            "min_deflated_sharpe": min(cs_dsr, ts_dsr),
            "passed_half_test": half_ok,
            "passed_deflated_test": defl_ok,
            "passed_all_gates": half_ok and defl_ok,
        })

    out = pd.DataFrame(rows).sort_values("min_deflated_sharpe", ascending=False)
    return out, deflation_term


def stage_5_correlation_pruning(
    returns_df: pd.DataFrame,
    survivors: pd.DataFrame,
    corr_cap: float,
    max_picks: int,
    holdout_end: pd.Timestamp | None,
) -> List[str]:
    """Greedy correlation pruning. Returns ordered list of selected base factor names."""
    if survivors.empty:
        return []
    df = returns_df.copy()
    if holdout_end is not None:
        df = df[df["date"] <= holdout_end]

    # Correlation across variant-averaged monthly returns: average _CS and _TS
    # so we score the underlying signal not one quirky variant.
    pivot = df.pivot(index="date", columns="factor", values="value").sort_index()

    base_returns = {}
    for base in survivors["factor"].tolist():
        cs, ts = base + "_CS", base + "_TS"
        if cs in pivot.columns and ts in pivot.columns:
            base_returns[base] = pivot[[cs, ts]].mean(axis=1)
    if not base_returns:
        return []
    R = pd.DataFrame(base_returns).dropna(how="all")
    corr = R.corr()

    selected: List[str] = []
    for base in survivors["factor"].tolist():
        if base not in corr.columns:
            continue
        if not selected:
            selected.append(base)
            if len(selected) >= max_picks:
                break
            continue
        max_existing_corr = max(abs(corr.loc[base, s]) for s in selected if s in corr.columns)
        if max_existing_corr < corr_cap:
            selected.append(base)
            if len(selected) >= max_picks:
                break
    return selected


# ─── Driver ────────────────────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--holdout-end", type=str, default=None,
                        help="Cap analysis at this date (YYYY-MM-DD). Validate picks "
                             "on dates after this. Default: use full sample.")
    parser.add_argument("--deflated-min", type=float, default=DEFAULT_DEFLATED_SHARPE_MIN,
                        help=f"Min deflated annualized Sharpe (each variant). "
                             f"Default {DEFAULT_DEFLATED_SHARPE_MIN}.")
    parser.add_argument("--corr-cap", type=float, default=DEFAULT_CORR_CAP,
                        help=f"Max pairwise correlation in final picks. Default {DEFAULT_CORR_CAP}.")
    parser.add_argument("--max-picks", type=int, default=DEFAULT_MAX_PICKS,
                        help=f"Cap on final picks. Default {DEFAULT_MAX_PICKS}.")
    parser.add_argument("--half-min", type=float, default=DEFAULT_HALF_SHARPE_MIN,
                        help=f"Min annualized Sharpe in each half. Default {DEFAULT_HALF_SHARPE_MIN}.")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    holdout_end = pd.to_datetime(args.holdout_end) if args.holdout_end else None

    # Load
    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    returns_df = con.execute("""
        SELECT CAST(date AS DATE) AS date, factor, value
        FROM factor_returns
        WHERE source = 'gdelt_optimizer'
    """).fetchdf()
    con.close()
    returns_df["date"] = pd.to_datetime(returns_df["date"])
    full_min, full_max = returns_df["date"].min(), returns_df["date"].max()

    # Stage 1
    matched_bases = stage_1_prior_filter(returns_df)
    # Stage 2
    paired_bases = stage_2_variant_pairing(returns_df, matched_bases)
    # Stages 3 + 4
    scored, deflation_term = stage_3_4_score_and_filter(
        returns_df, paired_bases, holdout_end,
        deflated_min=args.deflated_min, half_min=args.half_min,
    )
    survivors = scored[scored["passed_all_gates"]].copy()
    # Stage 5
    final_picks = stage_5_correlation_pruning(
        returns_df, survivors,
        corr_cap=args.corr_cap, max_picks=args.max_picks,
        holdout_end=holdout_end,
    )

    scored["selected"] = scored["factor"].isin(final_picks)
    selection_order = {b: i + 1 for i, b in enumerate(final_picks)}
    scored["pick_rank"] = scored["factor"].map(selection_order)
    scored = scored.sort_values(
        ["selected", "pick_rank", "min_deflated_sharpe"],
        ascending=[False, True, False],
    )

    # Write outputs
    scored.to_csv(OUT_CSV, index=False)
    log_lines = [
        f"GDELT-for-T2 candidate selection — {datetime.now().isoformat(timespec='seconds')}",
        f"DuckDB: {DUCKDB_PATH}",
        f"Full sample: {full_min.date()} → {full_max.date()}",
        f"Holdout-end clip: {holdout_end.date() if holdout_end is not None else '(none — full sample used)'}",
        f"Pre-screen patterns: {len(PRIOR_PATTERNS)}",
        f"Stage 1 (prior filter):    {len(matched_bases)} base factors matched",
        f"Stage 2 (variant pairing): {len(paired_bases)} base factors have both _CS and _TS",
        f"  N (variants tested) = {2 * len(paired_bases)}",
        f"Stage 3+4 inputs scored:   {len(scored)} factors",
        f"  Deflation term (annualized SR null adj): {deflation_term:.3f}",
        f"  Threshold: deflated Sharpe ≥ {args.deflated_min}, "
        f"each-half Sharpe ≥ {args.half_min}",
        f"Stage 3+4 survivors:       {len(survivors)}",
        f"Stage 5 final picks:       {len(final_picks)}  "
        f"(corr cap {args.corr_cap}, max_picks {args.max_picks})",
        "",
        "Final picks (in greedy-correlation order):",
    ]
    for i, base in enumerate(final_picks, 1):
        row = scored[scored["factor"] == base].iloc[0]
        log_lines.append(
            f"  {i}. {base}  "
            f"min_DSR={row['min_deflated_sharpe']:.3f}  "
            f"CS={row['cs_sharpe']:.2f}  TS={row['ts_sharpe']:.2f}  "
            f"halves CS=({row['cs_sharpe_h1']:.2f},{row['cs_sharpe_h2']:.2f}) "
            f"TS=({row['ts_sharpe_h1']:.2f},{row['ts_sharpe_h2']:.2f})"
        )
    OUT_LOG.write_text("\n".join(log_lines) + "\n")

    print("\n".join(log_lines))
    print(f"\nFull metric table: {OUT_CSV}")
    print(f"Run log:           {OUT_LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
