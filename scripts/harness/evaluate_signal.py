#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: evaluate_signal.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb (read-only)
  Signal data (feature_panel, t2_factors_daily, gdelt_factors_daily, any
  tidy table) referenced by the signal_spec.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
  country_returns_monthly (the marking surface) and loop-owned signal tables.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/ledgers/hypothesis_ledger.jsonl
  Pre-registration check + family trial counts for the deflated Sharpe.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/harness_runs/{hypothesis_id}_{ts}.json
  Full result payload for every run (written immediately - incremental
  result persistence).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
  Tables `harness_results` and `harness_ic_series` - one summary row per run
  plus the per-date rank-IC path used by the front end.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/ledgers/hypothesis_ledger.jsonl
  Verdict event appended automatically (never by hand).

VERSION: 2.1
LAST UPDATED: 2026-06-12
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 1/2)

DESCRIPTION:
The skeptic. The ONLY path from "idea" to "evidence" in the Alpha-Hunting
Loop (PRD section 5). Give it a pre-registered hypothesis and a signal
definition; it measures whether the signal actually predicted country
returns, with the safety rails INSIDE the machine so nobody (human or model)
can cheat even accidentally:

 1. PRE-REGISTRATION: refuses to run without a hypothesis_id already in the
    ledger. No anonymous backtests; every run counts as a trial.
 2. POINT-IN-TIME EMBARGO: a signal value labeled month M is only allowed to
    predict returns from month M+1+lag onward, where lag = publication delay
    (market-derived sources lag 0; everything else gets a conservative
    default by observed frequency: monthly 1, quarterly 3, annual 12).
 3. RANK IC by horizon with Newey-West t-stats (overlap-corrected) and a
    year-by-year IC table.
 4. PORTFOLIOS (monthly AND daily since v2): top-7 long-only vs the
    equal-weight-34 baseline and top7-minus-bottom7 long-short, at 10/25/50
    bps one-way costs + 50 bps/yr short borrow, with turnover reported.
    Daily uses overlapping tranches — see the DAILY FREQUENCY note below.
 5. SUB-PERIOD STABILITY: 2008-12 / 2013-17 / 2018-22 / 2023-now.
 6. DEFLATED SHARPE: the long-short Sharpe is compared to the expected
    maximum Sharpe from N trials of pure noise, where N = the hypothesis
    family's running trial count from the ledger. Deflated = SR - E[max SR_N].
 7. COVERAGE GATES: >= 28 countries on >= 95% of dates, >= 60 aligned months,
    else the verdict is INSUFFICIENT_*, not a number.

A 10th grader's version: this is the strict referee. You must write down
your prediction before the game, it deducts points for every extra attempt
you took, and it checks you never used tomorrow's newspaper.

VERDICTS (PRD 5.3): WATCH / WEAK / DEAD / INSUFFICIENT_COVERAGE /
INSUFFICIENT_HISTORY, written back to the hypothesis ledger automatically.

DAILY FREQUENCY (v2, 2026-06-10): daily runs now get the FULL gate set.
 a. RETURNS: daily marking uses loopdb.daily_country_returns - backward-
    labeled REAL trading-day returns (v1 used the raw forward-labeled
    calendar grid with 0.0 weekend placeholders, which both shifted labels
    and diluted windows).
 b. PORTFOLIOS: overlapping-tranche construction (Jegadeesh-Titman): the
    book is split into `hold_days` tranches; tranche k re-ranks every
    hold_days trading days on its own offset and holds otherwise. Daily
    portfolio return = average over tranches. Holdings take effect the
    trading day AFTER the rank date (no same-close execution).
 c. COSTS: one-way 10/25/50 bps x actual tranche turnover, charged on
    rebalance days, + 50 bps/yr borrow on the short leg. Country ETF
    spreads cluster near the 10-25 bps cases; 50 bps is the stress case.
 d. DEFLATED SHARPE: same Bailey-Lopez de Prado machinery with
    periods_per_year=252 on the net-25bps LS daily series.
 e. NW-t: max_lag now equals the horizon in TRADING DAYS (v1 used h//21
    which under-corrected 5d/21d overlap - the v1 daily t-stats were
    overstated; treat archived v1 daily runs accordingly).
The IC-only path (portfolios_skipped=true) survives only as a fallback when
the portfolio block errors (e.g. too few dates), and says so in gate_notes.

COST / HOLDING-PERIOD MODEL (v2.1, 2026-06-12): two additions, both
diagnostic (verdict gates unchanged, still keyed to the registered hold):
 f. HOLD-PERIOD GRID: every daily run is re-costed at 1d / 5d / 21d
    tranched holds (`hold_period_grid` in the result JSON) so a signal
    killed by 1d-rebalance turnover can show whether a slower
    implementation of the SAME ranks survives. Promotion to a slower hold
    requires registering a new spec with hold_days set explicitly.
 g. BREAKEVEN COST: `breakeven_cost_bps_ls` = the one-way cost (bps) at
    which the mean net LS return crosses zero, given the strategy's own
    turnover (monthly and daily). Negative = loses money even free.
    Cost cases now include a 5 bps leg (liquid-futures/DM-ETF case).

DEPENDENCIES:
- duckdb, pandas, numpy, scipy (project venv)

USAGE:
 from scripts.harness.evaluate_signal import evaluate_signal
 result = evaluate_signal(
     hypothesis_id="H_20260610_001",
     signal_spec={"table": "feature_panel", "variable": "EPU_CS", "source": "epu"},
     direction="lower_is_better",
     frequency="monthly",
 )
 # CLI smoke run:
 python scripts/harness/evaluate_signal.py --hypothesis H_... --table feature_panel \
     --variable EPU_CS --source epu --direction lower_is_better
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd
import yaml
from scipy import stats as sstats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.loop.ledgers import (attach_verdict, canonical_family_of,
                                  family_trial_count, get_hypothesis)
from scripts.loop.loopdb import LOOP_DIR, T2_UNIVERSE, daily_country_returns, loop_connection
from scripts.harness.ic_series_store import replace_ic_series

RUNS_DIR = LOOP_DIR / "harness_runs"

# Sources whose values are derived from market prices / real-time feeds and
# are therefore knowable at month-end with no publication delay.
ZERO_LAG_SOURCES = {"t2", "gdelt", "graph", "t2_optimizer", "gdelt_optimizer", "econ_optimizer"}

# FORWARD-RETURN VARIABLES — BANNED AS SIGNALS. Verified empirically
# 2026-06-10: every `NMRet`/`NDRet` variable in the t2 source is a FORWARD
# return labeled at the START of its window (e.g. 12MRet at 2024-01-01 is
# the return over 2024-01..2024-12). They are optimizer TARGETS. Using one
# as a signal is pure lookahead — H_20260610_001 demonstrated this with a
# fake IC of 0.25. The harness refuses them outright.
FORWARD_RETURN_VARIABLES = {
    "1MRet", "3MRet", "6MRet", "9MRet", "12MRet",
    "1DRet", "5DRet", "20DRet", "60DRet", "120DRet",
}

DEFAULT_MONTHLY_HORIZONS = [1, 3, 6]      # months
DEFAULT_DAILY_HORIZONS = [5, 21, 63]      # trading days

SUBPERIODS = [
    ("2008-2012", "2008-01-01", "2012-12-31"),
    ("2013-2017", "2013-01-01", "2017-12-31"),
    ("2018-2022", "2018-01-01", "2022-12-31"),
    ("2023-now", "2023-01-01", "2099-12-31"),
]


# ─────────────────────────────────────────────────────────────────────────────
# Pure computational core (unit-testable, no I/O)
# ─────────────────────────────────────────────────────────────────────────────

def month_index(dates: pd.Series) -> pd.Series:
    """Map timestamps to integer month counters (year*12 + month)."""
    d = pd.to_datetime(dates)
    return d.dt.year * 12 + d.dt.month


def align_monthly(
    signal: pd.DataFrame,
    returns: pd.DataFrame,
    lag_months: int,
    horizon_months: int,
) -> pd.DataFrame:
    """Join signal month M to the compounded forward return over months
    M+1+lag ... M+lag+horizon. Columns in: signal(date, country, value),
    returns(date, country, return_1m). Out: (date, country, value, fwd_return).

    PIT guarantee: the EARLIEST return month used is strictly greater than
    the signal month plus the publication lag.
    """
    sig = signal.copy()
    ret = returns.copy()
    sig["m"] = month_index(sig["date"])
    ret["m"] = month_index(ret["date"])

    # Cumulative log-return index per country for O(1) window compounding
    ret = ret.sort_values(["country", "m"])
    ret["log1p"] = np.log1p(ret["return_1m"])
    ret["cum"] = ret.groupby("country")["log1p"].cumsum()
    cum = ret.set_index(["country", "m"])["cum"]

    start_m = sig["m"] + lag_months          # last month BEFORE the window
    end_m = sig["m"] + lag_months + horizon_months

    idx_start = pd.MultiIndex.from_arrays([sig["country"], start_m])
    idx_end = pd.MultiIndex.from_arrays([sig["country"], end_m])
    cum_start = pd.Series(cum.reindex(idx_start).values, index=sig.index)
    cum_end = pd.Series(cum.reindex(idx_end).values, index=sig.index)

    # A window is valid only if the country has return rows for BOTH ends.
    # cum at start_m means "through end of start_m"; subtracting yields the
    # compounded return over (start_m, end_m].
    fwd = np.expm1(cum_end - cum_start)

    # Edge case: start_m before the country's first return month. cum.reindex
    # gives NaN there; for windows starting exactly at the first month we'd
    # lose the row - acceptable (one row per country) and conservative.
    out = sig[["date", "country", "value"]].copy()
    out["fwd_return"] = fwd.values
    return out.dropna(subset=["value", "fwd_return"])


def rank_ic_series(aligned: pd.DataFrame, min_countries: int = 10) -> pd.Series:
    """Per-date Spearman rank IC between signal value and forward return."""
    out = {}
    for dt, g in aligned.groupby("date"):
        if g["country"].nunique() < min_countries or g["value"].nunique() < 3:
            continue
        ic, _ = sstats.spearmanr(g["value"], g["fwd_return"])
        if not np.isnan(ic):
            out[dt] = ic
    return pd.Series(out).sort_index()


def nw_tstat(series: pd.Series, max_lag: int) -> float:
    """Newey-West t-stat of the series mean (Bartlett kernel)."""
    x = series.dropna().values
    T = len(x)
    if T < 8:
        return np.nan
    mu = x.mean()
    e = x - mu
    gamma0 = (e @ e) / T
    lrv = gamma0
    L = min(max_lag, T - 1)
    for k in range(1, L + 1):
        gamma_k = (e[k:] @ e[:-k]) / T
        lrv += 2 * (1 - k / (L + 1)) * gamma_k
    if lrv <= 0:
        return np.nan
    return float(mu / np.sqrt(lrv / T))


def yearly_ic_table(ic: pd.Series) -> dict[str, float]:
    if ic.empty:
        return {}
    return {str(y): round(float(v), 4) for y, v in ic.groupby(pd.to_datetime(ic.index).year).mean().items()}


def backtest_monthly(
    aligned_1m: pd.DataFrame,
    direction: str,
    n_top: int = 7,
    cost_bps_cases: tuple[int, ...] = (5, 10, 25, 50),
    borrow_bps_yr: float = 50.0,
    min_cross_section: int = 14,
) -> dict[str, Any]:
    """Top-N long-only vs equal-weight baseline + top-minus-bottom LS.

    aligned_1m must be the horizon=1 alignment (signal month M -> return of
    the single next allowed month). Ranking is on the lag-shifted signal, so
    the PIT embargo is inherited from align_monthly.
    """
    sign = 1.0 if direction == "higher_is_better" else -1.0
    df = aligned_1m.copy()
    df["score"] = sign * df["value"]

    dates = sorted(df["date"].unique())
    rows = []
    prev_top: set[str] = set()
    prev_bot: set[str] = set()
    for dt in dates:
        g = df[df["date"] == dt]
        if len(g) < min_cross_section:
            continue
        g = g.sort_values("score", ascending=False)
        top = set(g.head(n_top)["country"])
        bot = set(g.tail(n_top)["country"])
        ret_top = g[g["country"].isin(top)]["fwd_return"].mean()
        ret_bot = g[g["country"].isin(bot)]["fwd_return"].mean()
        ret_ew = g["fwd_return"].mean()
        to_top = len(top - prev_top) / n_top if prev_top else 1.0
        to_bot = len(bot - prev_bot) / n_top if prev_bot else 1.0
        rows.append({"date": dt, "ret_top": ret_top, "ret_bot": ret_bot, "ret_ew": ret_ew,
                     "turnover_top": to_top, "turnover_ls": to_top + to_bot})
        prev_top, prev_bot = top, bot

    bt = pd.DataFrame(rows)
    if bt.empty or len(bt) < 24:
        return {"error": "insufficient backtest months", "n_months": int(len(bt))}

    borrow_m = borrow_bps_yr / 10000.0 / 12.0
    result: dict[str, Any] = {
        "n_months": int(len(bt)),
        "start": str(pd.Timestamp(bt["date"].min()).date()),
        "end": str(pd.Timestamp(bt["date"].max()).date()),
        "avg_turnover_top_oneway": round(float(bt["turnover_top"].mean()), 4),
        "avg_turnover_ls_oneway": round(float(bt["turnover_ls"].mean()), 4),
        "breakeven_cost_bps_ls": _breakeven_bps(
            bt["ret_top"] - bt["ret_bot"], bt["turnover_ls"], borrow_m),
        "gross": {
            "top_ann_return": _ann_ret(bt["ret_top"]),
            "ew_ann_return": _ann_ret(bt["ret_ew"]),
            "excess_ann_return": _ann_ret(bt["ret_top"]) - _ann_ret(bt["ret_ew"]),
            "ls_ann_return": _ann_ret(bt["ret_top"] - bt["ret_bot"]),
            "ls_sharpe": _sharpe(bt["ret_top"] - bt["ret_bot"]),
            "top_excess_sharpe": _sharpe(bt["ret_top"] - bt["ret_ew"]),
        },
        "net": {},
    }
    for bps in cost_bps_cases:
        c = bps / 10000.0
        top_net = bt["ret_top"] - bt["turnover_top"] * 2 * c  # buy+sell per changed slot
        ls_net = (bt["ret_top"] - bt["ret_bot"]) - bt["turnover_ls"] * 2 * c - borrow_m
        result["net"][f"{bps}bps"] = {
            "top_excess_ann_return": _ann_ret(top_net) - _ann_ret(bt["ret_ew"]),
            "top_excess_sharpe": _sharpe(top_net - bt["ret_ew"]),
            "ls_ann_return": _ann_ret(ls_net),
            "ls_sharpe": _sharpe(ls_net),
        }
    result["_ls_net25_series"] = (
        (bt.set_index("date")["ret_top"] - bt["ret_bot"].values)
        - bt.set_index("date")["turnover_ls"] * 2 * 0.0025 - borrow_m
    )
    result["_subperiods_src"] = bt
    return result


def _breakeven_bps(ls_gross: pd.Series, turnover_ls: pd.Series,
                   borrow_per_period: float) -> Optional[float]:
    """One-way cost (bps) at which the mean net LS return hits zero:
    mean(gross) - mean(turnover_ls) * 2c - borrow = 0. Negative values mean
    the strategy loses money even at zero cost."""
    mean_gross = float(ls_gross.mean())
    mean_to = float(turnover_ls.mean())
    if mean_to <= 0:
        return None
    return round((mean_gross - borrow_per_period) / (2 * mean_to) * 10000, 1)


def _ann_ret(r: pd.Series, periods: int = 12) -> float:
    r = r.dropna()
    if r.empty:
        return np.nan
    return round(float((1 + r).prod() ** (periods / len(r)) - 1.0), 4)


def _sharpe(r: pd.Series, periods: int = 12) -> float:
    r = r.dropna()
    if len(r) < periods or r.std() == 0:
        return np.nan
    return round(float(r.mean() / r.std() * np.sqrt(periods)), 3)


def subperiod_table(bt: pd.DataFrame, periods: int = 12) -> dict[str, Any]:
    min_obs = periods  # one year of observations per sub-period
    out = {}
    for name, s, e in SUBPERIODS:
        m = bt[(bt["date"] >= pd.Timestamp(s)) & (bt["date"] <= pd.Timestamp(e))]
        if len(m) < min_obs:
            out[name] = {"n_obs": int(len(m))}
            continue
        out[name] = {
            "n_obs": int(len(m)),
            "top_excess_ann": _ann_ret(m["ret_top"], periods) - _ann_ret(m["ret_ew"], periods),
            "ls_sharpe_gross": _sharpe(m["ret_top"] - m["ret_bot"], periods),
        }
    return out


def backtest_daily(
    signal_panel: pd.DataFrame,
    ret_panel: pd.DataFrame,
    direction: str,
    hold_days: int,
    n_top: int = 7,
    cost_bps_cases: tuple[int, ...] = (5, 10, 25, 50),
    borrow_bps_yr: float = 50.0,
    min_cross_section: int = 14,
) -> dict[str, Any]:
    """Overlapping-tranche daily portfolio (Jegadeesh-Titman).

    signal_panel: (dates x countries) raw signal values on trading dates.
    ret_panel:    (dates x countries) backward-labeled trading-day returns
                  (loopdb.returns_panel) - NaN on non-trading days.

    Construction: `hold_days` tranches; tranche k re-ranks on rank dates
    with index i where i % hold_days == k and holds in between. Holdings
    chosen at rank date t earn returns from the NEXT trading day onward.
    Daily portfolio return = average across active tranches; per-tranche
    one-way turnover is charged on its rebalance day.
    """
    sign = 1.0 if direction == "higher_is_better" else -1.0
    score = (sign * signal_panel).dropna(how="all")
    rank_dates = [d for d in score.index if score.loc[d].notna().sum() >= min_cross_section]
    if len(rank_dates) < 5 * hold_days:
        return {"error": "insufficient rank dates", "n_dates": int(len(rank_dates))}

    ret_dates = ret_panel.index
    # rank date -> (top set, bottom set)
    sets: dict[pd.Timestamp, tuple[set, set]] = {}
    for d in rank_dates:
        row = score.loc[d].dropna().sort_values(ascending=False)
        sets[d] = (set(row.head(n_top).index), set(row.tail(n_top).index))

    tranche_top: list[Optional[set]] = [None] * hold_days
    tranche_bot: list[Optional[set]] = [None] * hold_days
    pend: dict[int, tuple[set, set]] = {}  # tranche -> holdings queued for next-day execution
    rank_pos = {d: i for i, d in enumerate(rank_dates)}
    rows = []
    for d in ret_dates:
        if d < rank_dates[0]:
            continue
        # activate holdings queued at the previous rank date (next-open execution)
        for k, (top, bot) in list(pend.items()):
            tranche_top[k], tranche_bot[k] = top, bot
            pend.pop(k)
        day_ret = ret_panel.loc[d]
        rets_top, rets_bot, costs = [], [], []
        for k in range(hold_days):
            if tranche_top[k] is None:
                continue
            rt = day_ret.reindex(list(tranche_top[k])).dropna()
            rb = day_ret.reindex(list(tranche_bot[k])).dropna()
            if len(rt) >= max(3, n_top - 3):
                rets_top.append(rt.mean())
                rets_bot.append(rb.mean() if len(rb) else 0.0)
        if rets_top:
            ew = day_ret.dropna()
            rows.append({
                "date": d,
                "ret_top": float(np.mean(rets_top)),
                "ret_bot": float(np.mean(rets_bot)),
                "ret_ew": float(ew.mean()) if len(ew) >= 14 else np.nan,
                "turnover_top": 0.0, "turnover_ls": 0.0,
            })
        # after the close of rank date d: queue the rebalance for tranche k
        if d in rank_pos:
            k = rank_pos[d] % hold_days
            top, bot = sets[d]
            old_t = tranche_top[k] if tranche_top[k] is not None else set()
            old_b = tranche_bot[k] if tranche_bot[k] is not None else set()
            to_t = len(top - old_t) / n_top if old_t else 1.0
            to_b = len(bot - old_b) / n_top if old_b else 1.0
            pend[k] = (top, bot)
            if rows and rows[-1]["date"] == d:
                # turnover hits the book on execution; charge it on this row
                # scaled by the tranche's share of the portfolio
                rows[-1]["turnover_top"] += to_t / hold_days
                rows[-1]["turnover_ls"] += (to_t + to_b) / hold_days

    bt = pd.DataFrame(rows).dropna(subset=["ret_ew"])
    if len(bt) < 252:
        return {"error": "insufficient backtest days", "n_days": int(len(bt))}

    borrow_d = borrow_bps_yr / 10000.0 / 252.0
    result: dict[str, Any] = {
        "construction": f"{hold_days} overlapping tranches, top{n_top}/bottom{n_top}, next-day execution",
        "n_days": int(len(bt)),
        "start": str(pd.Timestamp(bt["date"].min()).date()),
        "end": str(pd.Timestamp(bt["date"].max()).date()),
        "avg_daily_turnover_top_oneway": round(float(bt["turnover_top"].mean()), 5),
        "avg_daily_turnover_ls_oneway": round(float(bt["turnover_ls"].mean()), 5),
        "breakeven_cost_bps_ls": _breakeven_bps(
            bt["ret_top"] - bt["ret_bot"], bt["turnover_ls"], borrow_d),
        "gross": {
            "top_ann_return": _ann_ret(bt["ret_top"], 252),
            "ew_ann_return": _ann_ret(bt["ret_ew"], 252),
            "excess_ann_return": _ann_ret(bt["ret_top"], 252) - _ann_ret(bt["ret_ew"], 252),
            "ls_ann_return": _ann_ret(bt["ret_top"] - bt["ret_bot"], 252),
            "ls_sharpe": _sharpe(bt["ret_top"] - bt["ret_bot"], 252),
            "top_excess_sharpe": _sharpe(bt["ret_top"] - bt["ret_ew"], 252),
        },
        "net": {},
    }
    for bps in cost_bps_cases:
        c = bps / 10000.0
        top_net = bt["ret_top"] - bt["turnover_top"] * 2 * c
        ls_net = (bt["ret_top"] - bt["ret_bot"]) - bt["turnover_ls"] * 2 * c - borrow_d
        result["net"][f"{bps}bps"] = {
            "top_excess_ann_return": _ann_ret(top_net, 252) - _ann_ret(bt["ret_ew"], 252),
            "top_excess_sharpe": _sharpe(top_net - bt["ret_ew"], 252),
            "ls_ann_return": _ann_ret(ls_net, 252),
            "ls_sharpe": _sharpe(ls_net, 252),
        }
    result["_ls_net25_series"] = (
        (bt.set_index("date")["ret_top"] - bt["ret_bot"].values)
        - bt.set_index("date")["turnover_ls"] * 2 * 0.0025 - borrow_d
    )
    result["_subperiods_src"] = bt
    return result


HOLD_GRID_DAYS = (1, 5, 21)


def _compact_hold(res: dict[str, Any]) -> dict[str, Any]:
    """Compact one-line summary of a backtest_daily result for the hold grid."""
    if "error" in res:
        return {"error": res["error"]}
    net = res.get("net", {})
    return {
        "avg_daily_turnover_ls_oneway": res.get("avg_daily_turnover_ls_oneway"),
        "breakeven_cost_bps_ls": res.get("breakeven_cost_bps_ls"),
        "gross_ls_sharpe": res.get("gross", {}).get("ls_sharpe"),
        "net_ls_sharpe": {bps: net.get(bps, {}).get("ls_sharpe") for bps in net},
        "net_top_excess_25bps": net.get("25bps", {}).get("top_excess_ann_return"),
    }


def expected_max_sharpe(n_trials: int, n_obs: int) -> float:
    """E[max Sharpe] across n_trials of pure noise with n_obs observations
    (per-period units). Bailey & Lopez de Prado approximation."""
    if n_trials < 1 or n_obs < 3:
        return np.nan
    gamma = 0.5772156649
    n = max(n_trials, 1)
    if n == 1:
        return 0.0
    z1 = sstats.norm.ppf(1 - 1.0 / n)
    z2 = sstats.norm.ppf(1 - 1.0 / (n * np.e))
    return float(np.sqrt(1.0 / (n_obs - 1)) * ((1 - gamma) * z1 + gamma * z2))


def deflated_sharpe_block(period_series: pd.Series, n_trials: int,
                          periods_per_year: int = 12) -> dict[str, Any]:
    """Deflated Sharpe on a per-period return series (monthly or daily).
    All Sharpe quantities here are in PER-PERIOD units; only the reported
    `sharpe_annualized` is scaled."""
    r = period_series.dropna()
    if len(r) < 2 * periods_per_year or r.std() == 0:
        return {"deflated_sharpe": np.nan, "n_obs": int(len(r))}
    sr_p = float(r.mean() / r.std())
    emax = expected_max_sharpe(n_trials, len(r))
    skew = float(sstats.skew(r))
    kurt = float(sstats.kurtosis(r, fisher=False))
    denom = np.sqrt(max(1 - skew * sr_p + (kurt - 1) / 4 * sr_p**2, 1e-9))
    psr = float(sstats.norm.cdf((sr_p - emax) * np.sqrt(len(r) - 1) / denom))
    return {
        "sharpe_per_period": round(sr_p, 4),
        "periods_per_year": periods_per_year,
        "sharpe_annualized": round(sr_p * np.sqrt(periods_per_year), 3),
        "n_trials_family": n_trials,
        "expected_max_sharpe_per_period": round(emax, 4),
        "deflated_sharpe": round(sr_p - emax, 4),
        "prob_sharpe_exceeds_noise_max": round(psr, 4),
        "n_obs": int(len(r)),
    }


def decide_verdict(metrics: dict[str, Any], frequency: str) -> tuple[str, list[str]]:
    """PRD 5.3 gates. Returns (verdict, list of gate notes)."""
    notes = []
    if metrics.get("coverage_fail"):
        return "INSUFFICIENT_COVERAGE", ["coverage gate failed"]
    if metrics.get("history_fail"):
        return "INSUFFICIENT_HISTORY", ["fewer than 60 aligned months/dates"]

    t = metrics["primary_nw_t"]
    pct_pos = metrics["pct_positive_years"]
    g_t = t is not None and not np.isnan(t) and t >= 2.5
    g_years = pct_pos is not None and pct_pos >= 0.60
    notes.append(f"NW-t primary={t} (gate >=2.5: {'PASS' if g_t else 'FAIL'})")
    notes.append(f"positive IC years={pct_pos} (gate >=0.60: {'PASS' if g_years else 'FAIL'})")

    if metrics.get("portfolios_skipped"):
        # v2: only reachable when the portfolio block errored (fallback)
        notes.append(f"portfolio block unavailable ({metrics.get('portfolio_error')}) - IC-only verdict")
        if g_t and g_years:
            return "WATCH", notes
        return ("WEAK" if (t is not None and not np.isnan(t) and t >= 1.5) else "DEAD"), notes

    g_cost = metrics.get("ls_sharpe_net25") is not None and not np.isnan(metrics["ls_sharpe_net25"]) \
        and metrics["ls_sharpe_net25"] > 0 and metrics.get("top_excess_net25", np.nan) > 0
    g_dsr = metrics.get("deflated_sharpe") is not None and not np.isnan(metrics["deflated_sharpe"]) \
        and metrics["deflated_sharpe"] > 0
    notes.append(f"net-25bps LS Sharpe={metrics.get('ls_sharpe_net25')} & top7 excess={metrics.get('top_excess_net25')} "
                 f"(gate both >0: {'PASS' if g_cost else 'FAIL'})")
    notes.append(f"deflated Sharpe={metrics.get('deflated_sharpe')} (gate >0: {'PASS' if g_dsr else 'FAIL'})")

    if g_t and g_years and g_cost and g_dsr:
        return "WATCH", notes
    if t is not None and not np.isnan(t) and t >= 1.5:
        return "WEAK", notes
    return "DEAD", notes


# ─────────────────────────────────────────────────────────────────────────────
# I/O layer
# ─────────────────────────────────────────────────────────────────────────────

def load_signal(con, signal_spec: dict[str, Any], universe: list[str], start_date: str,
                frequency: str) -> tuple[pd.DataFrame, str]:
    """Load (date, country, value) per the spec. Returns (df, source_name)."""
    if signal_spec.get("variable") in FORWARD_RETURN_VARIABLES:
        raise ValueError(
            f"{signal_spec['variable']} is a FORWARD return (labeled at window start) - "
            "it is an optimizer target, not a signal. Using it would be lookahead. "
            "Use a trailing variable instead (e.g. 12-1MTR_CS)."
        )
    if "sql" in signal_spec:
        df = con.execute(signal_spec["sql"]).fetchdf()
        required = {"date", "country", "value"}
        if not required.issubset(df.columns):
            raise ValueError(f"signal SQL must return columns {required}, got {list(df.columns)}")
        src = signal_spec.get("source", "sql")
    else:
        table = signal_spec["table"]
        variable = signal_spec["variable"]
        src = signal_spec.get("source")
        # Loop-owned tables are unqualified; warehouse tables get asado. prefix
        loop_tables = {r[0] for r in con.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_catalog = 'asado_loop'"
        ).fetchall()}
        qual = table if table in loop_tables else f"asado.{table}"
        src_clause = "AND source = ?" if src else ""
        params = [variable] + ([src] if src else [])
        df = con.execute(
            f"""
            SELECT date, country, value FROM {qual}
            WHERE variable = ? {src_clause} AND value IS NOT NULL
            """,
            params,
        ).fetchdf()
        if src is None:
            srcs = con.execute(
                f"SELECT DISTINCT source FROM {qual} WHERE variable = ?", [variable]
            ).fetchall() if "source" in [c[0] for c in con.execute(f"DESCRIBE {qual}").fetchall()] else []
            if len(srcs) > 1:
                raise ValueError(f"variable {variable} exists under multiple sources {srcs}; specify source")
            src = srcs[0][0] if srcs else "unknown"

    df = df[df["country"].isin(universe)]
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["date"] >= pd.Timestamp(start_date)]
    if df.empty:
        raise ValueError("signal query returned zero rows after universe/date filters")
    return df.sort_values(["date", "country"]).reset_index(drop=True), str(src)


# A6 — PIT-lag governance. A daily signal earns lag 0 ONLY via a passing proof
# in config/pit_proof_registry.yaml; otherwise it FAILS CLOSED to this default.
CONSERVATIVE_DAILY_LAG_DAYS = 1
PIT_REGISTRY_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "pit_proof_registry.yaml"
_PIT_REGISTRY: Optional[dict] = None


def _load_pit_registry(path: Path = PIT_REGISTRY_PATH) -> dict:
    global _PIT_REGISTRY
    if path == PIT_REGISTRY_PATH and _PIT_REGISTRY is not None:
        return _PIT_REGISTRY
    data = yaml.safe_load(path.read_text()) if path.exists() else {}
    data = data or {}
    if path == PIT_REGISTRY_PATH:
        _PIT_REGISTRY = data
    return data


def daily_publication_lag_days(variable: str, source: str,
                               signal_spec: Optional[dict[str, Any]] = None,
                               registry: Optional[dict] = None) -> int:
    """A6 — per-variable daily publication lag (trading days). Replaces the old
    blanket `daily -> 0`. PIT by source -> 0; an explicit signal_spec override
    wins; a PASSING pit_proof grants its entitled lag; everything else FAILS
    CLOSED to the conservative default (a daily signal does not get same-day
    knowledge it hasn't proven)."""
    if signal_spec and signal_spec.get("publication_lag_days") is not None:
        return int(signal_spec["publication_lag_days"])
    if source in ZERO_LAG_SOURCES:
        return 0
    reg = registry if registry is not None else _load_pit_registry()
    proof = (reg.get("proofs") or {}).get(variable)
    if proof and proof.get("status") == "passing":
        return int(proof.get("entitled_lag_days", 0))
    return CONSERVATIVE_DAILY_LAG_DAYS


def infer_publication_lag(df: pd.DataFrame, source: str, frequency: str) -> int:
    """Conservative MONTHLY publication-lag default (months). Market-derived = 0.
    (Daily lag is governed separately by daily_publication_lag_days — A6.)"""
    if source in ZERO_LAG_SOURCES:
        return 0
    if frequency == "daily":
        # Kept for back-compat callers; the daily path now uses
        # daily_publication_lag_days() for the real per-variable embargo.
        return 0
    # infer native frequency from median gap between observations per country
    gaps = (
        df.sort_values(["country", "date"]).groupby("country")["date"].diff().dt.days.dropna()
    )
    med = float(gaps.median()) if len(gaps) else 31.0
    if med <= 45:
        return 1
    if med <= 135:
        return 3
    return 12


def evaluate_signal(
    hypothesis_id: str,
    signal_spec: dict[str, Any],
    direction: str,
    frequency: str = "monthly",
    horizons: Optional[list[int]] = None,
    universe: str = "t2_34",
    start_date: str = "2008-01-01",
) -> dict[str, Any]:
    """Run the full harness. See module docstring. Returns the result dict."""
    if direction not in ("higher_is_better", "lower_is_better"):
        raise ValueError("direction must be higher_is_better or lower_is_better")
    if frequency not in ("monthly", "daily"):
        raise ValueError("frequency must be monthly or daily")

    # Gate 1: pre-registration
    hyp = get_hypothesis(hypothesis_id)
    if hyp is None:
        raise PermissionError(
            f"hypothesis {hypothesis_id} is not pre-registered. Register it in the "
            "hypothesis ledger (mechanism first!) before any backtest. No anonymous backtests."
        )

    countries = T2_UNIVERSE if universe == "t2_34" else [c.strip() for c in universe.split(",")]
    bad = [c for c in countries if c not in T2_UNIVERSE]
    if bad:
        raise ValueError(f"unknown countries in universe: {bad}")
    horizons = horizons or (DEFAULT_MONTHLY_HORIZONS if frequency == "monthly" else DEFAULT_DAILY_HORIZONS)

    con = loop_connection()
    try:
        signal, source = load_signal(con, signal_spec, countries, start_date, frequency)
        lag = signal_spec.get("publication_lag_months")
        lag = infer_publication_lag(signal, source, frequency) if lag is None else int(lag)
        # A6: per-variable daily publication embargo (trading days). Replaces the
        # old blanket daily=0; an unproven daily variable fails closed to 1 day.
        lag_days = (daily_publication_lag_days(signal_spec.get("variable", ""), source, signal_spec)
                    if frequency == "daily" else 0)

        if frequency == "monthly":
            returns = con.execute(
                "SELECT date, country, return_1m FROM country_returns_monthly"
            ).fetchdf()
            returns["date"] = pd.to_datetime(returns["date"])
        else:
            # v2: backward-labeled REAL trading-day returns (shared definition)
            returns = daily_country_returns(con).rename(columns={"ret": "return_1m"})
            returns = returns[returns["country"].isin(countries)]

        # ── IC block per horizon ────────────────────────────────────────
        ic_block = {}
        ic_series_by_label = {}
        aligned_by_label: dict[str, Any] = {}
        first_label = None
        for h in horizons:
            if frequency == "monthly":
                aligned = align_monthly(signal, returns, lag, h)
                label = f"{h}m"
            else:
                aligned = align_daily(signal, returns, h, lag_days)
                label = f"{h}d"
            ic = rank_ic_series(aligned)
            ic_series_by_label[label] = ic
            yearly = yearly_ic_table(ic)
            pct_pos = (
                float(np.mean([v > 0 for v in yearly.values()])) if yearly else None
            )
            ic_block[label] = {
                "mean_ic": round(float(ic.mean()), 4) if len(ic) else None,
                # max_lag = horizon in native periods: overlapping h-period
                # windows induce MA(h-1) autocorrelation in the IC series
                # (v1 used h//21 for daily, which under-corrected badly)
                "nw_t": round(nw_tstat(ic, max_lag=h), 3) if len(ic) else None,
                "n_dates": int(len(ic)),
                "pct_positive_years": round(pct_pos, 3) if pct_pos is not None else None,
                "yearly_ic": yearly,
            }
            aligned_by_label[label] = aligned
            if first_label is None:
                first_label = label

        # A5: the verdict's gating horizon is FROZEN at registration, not just
        # horizons[0] (which an agent could reorder to pick the best NW-t).
        primary_label = first_label
        reg_primary = hyp.get("primary_horizon")
        if reg_primary is not None:
            reg_label = f"{int(reg_primary)}m" if frequency == "monthly" else f"{int(reg_primary)}d"
            if reg_label in ic_block:
                primary_label = reg_label
            else:
                raise ValueError(
                    f"registered primary_horizon {reg_primary} not among evaluated horizons "
                    f"{list(ic_block)} for {hypothesis_id}")
        aligned_primary = aligned_by_label[primary_label]

        # ── Coverage gates ──────────────────────────────────────────────
        # Full 34-country universe keeps the PRD's absolute 28-country gate.
        # Explicit sub-universes (e.g. the 18 CDS countries) get the same
        # gate PROPORTIONALLY (>= 80% of the stated universe, floor 10) —
        # otherwise structurally-narrow layers could never be evaluated.
        # The sub-universe is recorded in the result so nobody mistakes an
        # 18-country WATCH for a 34-country WATCH.
        min_cov = 28 if len(countries) >= 34 else max(10, int(np.ceil(0.8 * len(countries))))
        n_top = 7 if len(countries) >= 34 else max(3, len(countries) // 3)
        min_xs = max(10, 2 * n_top)
        cov = aligned_primary.groupby("date")["country"].nunique() if aligned_primary is not None else pd.Series(dtype=float)
        coverage_fail = bool(len(cov) == 0 or (cov >= min_cov).mean() < 0.95)
        history_fail = bool(len(cov) < (60 if frequency == "monthly" else 252))

        # ── Portfolios + deflated Sharpe (monthly AND daily, v2) ────────
        portfolio: dict[str, Any] = {}
        subperiods: dict[str, Any] = {}
        dsr: dict[str, Any] = {}
        hold_grid: dict[str, Any] = {}
        if not coverage_fail and not history_fail:
            if frequency == "monthly":
                aligned_1m = align_monthly(signal, returns, lag, 1)
                portfolio = backtest_monthly(aligned_1m, direction, n_top=n_top,
                                             min_cross_section=min_xs)
                periods = 12
            else:
                sig_panel = signal.pivot_table(index="date", columns="country", values="value").sort_index()
                if lag_days:
                    sig_panel = sig_panel.shift(lag_days)  # A6: embargo the portfolio path too
                ret_panel = returns.pivot_table(index="date", columns="country", values="return_1m").sort_index()
                # restrict to real cross-section dates (>=10 countries traded)
                ret_panel = ret_panel[ret_panel.notna().sum(axis=1) >= 10]
                hold_days = int(signal_spec.get("hold_days", horizons[0]))
                portfolio = backtest_daily(sig_panel, ret_panel, direction, hold_days=hold_days,
                                           n_top=n_top, min_cross_section=min_xs)
                periods = 252
                # Hold-period grid: same signal at 1d/5d/21d tranched holds.
                # Diagnostic only - verdict stays keyed to the registered hold.
                hold_grid: dict[str, Any] = {}
                for h in HOLD_GRID_DAYS:
                    if h == hold_days:
                        res_h = portfolio
                    else:
                        res_h = backtest_daily(sig_panel, ret_panel, direction, hold_days=h,
                                               n_top=n_top, min_cross_section=min_xs)
                        res_h.pop("_subperiods_src", None)
                        res_h.pop("_ls_net25_series", None)
                    hold_grid[f"hold_{h}d"] = _compact_hold(res_h)
            if "_subperiods_src" in portfolio:
                subperiods = subperiod_table(portfolio.pop("_subperiods_src"), periods)
                ls_series = portfolio.pop("_ls_net25_series")
                dsr = deflated_sharpe_block(ls_series, family_trial_count(canonical_family_of(hyp)),
                                            periods_per_year=periods)
            else:
                portfolio.pop("_ls_net25_series", None)

        # ── Verdict ─────────────────────────────────────────────────────
        prim = ic_block[primary_label]
        portfolios_skipped = "error" in portfolio or not portfolio
        metrics = {
            "coverage_fail": coverage_fail,
            "history_fail": history_fail,
            "primary_nw_t": prim["nw_t"],
            "pct_positive_years": prim["pct_positive_years"],
            "ls_sharpe_net25": portfolio.get("net", {}).get("25bps", {}).get("ls_sharpe"),
            "top_excess_net25": portfolio.get("net", {}).get("25bps", {}).get("top_excess_ann_return"),
            "deflated_sharpe": dsr.get("deflated_sharpe"),
            "portfolios_skipped": portfolios_skipped,
            "portfolio_error": portfolio.get("error"),
        }
        # Sign convention: direction lower_is_better flips the IC for gating
        if direction == "lower_is_better":
            metrics["primary_nw_t"] = -metrics["primary_nw_t"] if metrics["primary_nw_t"] is not None else None
            if prim["pct_positive_years"] is not None:
                metrics["pct_positive_years"] = round(
                    float(np.mean([v < 0 for v in prim["yearly_ic"].values()])), 3
                ) if prim["yearly_ic"] else None
        verdict, gate_notes = decide_verdict(metrics, frequency)

        result = {
            "hypothesis_id": hypothesis_id,
            "family_key": hyp["family_key"],
            "canonical_family": canonical_family_of(hyp),
            "primary_label": primary_label,
            "run_ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "signal_spec": signal_spec,
            "resolved_source": source,
            "publication_lag_months": lag,
            "publication_lag_days": lag_days,
            "direction": direction,
            "frequency": frequency,
            "horizons": horizons,
            "universe_n": len(countries),
            "universe": "t2_34" if len(countries) >= 34 else sorted(countries),
            "start_date": start_date,
            "coverage": {
                "median_countries_per_date": float(cov.median()) if len(cov) else 0,
                "min_countries_gate": min_cov,
                "n_top_portfolio": n_top,
                "pct_dates_above_gate": round(float((cov >= min_cov).mean()), 3) if len(cov) else 0.0,
                "n_dates": int(len(cov)),
            },
            "ic": ic_block,
            "portfolio": portfolio,
            "hold_period_grid": hold_grid,
            "subperiods": subperiods,
            "deflated_sharpe_block": dsr,
            "portfolios_skipped": portfolios_skipped,
            "verdict": verdict,
            "gate_notes": gate_notes,
        }
    finally:
        con.close()

    # ── Persist (immediately) + ledger write-back ───────────────────────
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    ts_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RUNS_DIR / f"{hypothesis_id}_{ts_tag}.json"
    out_path.write_text(json.dumps(result, indent=2, default=str))
    result["result_file"] = str(out_path)

    summary = {k: result[k] for k in ("hypothesis_id", "family_key", "run_ts", "frequency", "verdict")}
    summary.update({
        "primary_horizon": primary_label,
        "mean_ic": ic_block[primary_label]["mean_ic"],
        "nw_t": ic_block[primary_label]["nw_t"],
        "deflated_sharpe": dsr.get("deflated_sharpe"),
        "result_file": str(out_path),
    })
    con = loop_connection()
    try:
        con.execute("""
            CREATE TABLE IF NOT EXISTS harness_results (
                hypothesis_id VARCHAR, family_key VARCHAR, run_ts VARCHAR,
                frequency VARCHAR, verdict VARCHAR, primary_horizon VARCHAR,
                mean_ic DOUBLE, nw_t DOUBLE, deflated_sharpe DOUBLE, result_file VARCHAR
            )
        """)
        con.execute(
            "INSERT INTO harness_results VALUES (?,?,?,?,?,?,?,?,?,?)",
            [summary["hypothesis_id"], summary["family_key"], summary["run_ts"],
             summary["frequency"], summary["verdict"], summary["primary_horizon"],
             summary["mean_ic"], summary["nw_t"], summary["deflated_sharpe"],
             summary["result_file"]],
        )
        replace_ic_series(con, result, ic_series_by_label)
    finally:
        con.close()

    attach_verdict(hypothesis_id, verdict, summary)
    return result


def align_daily(signal: pd.DataFrame, returns: pd.DataFrame, horizon_days: int,
                lag_days: int = 0) -> pd.DataFrame:
    """Daily alignment: signal on trading day t predicts the compounded return
    over t+lag_days+1 ... t+lag_days+horizon_days, per country's own trading
    calendar. lag_days (A6) is the publication embargo: a signal not known
    until t+lag_days cannot predict anything before t+lag_days+1. lag_days=0
    reproduces the prior behaviour (t+1 ... t+h)."""
    ret = returns.sort_values(["country", "date"]).copy()
    ret["log1p"] = np.log1p(ret["return_1m"])
    out_frames = []
    for country, g in ret.groupby("country"):
        sig_c = signal[signal["country"] == country]
        if sig_c.empty:
            continue
        g = g.reset_index(drop=True)
        cum = g["log1p"].cumsum()
        pos = pd.Series(g.index.values, index=g["date"])  # date -> row position
        p = pos.reindex(sig_c["date"]).values
        valid = ~pd.isna(p)
        p = p[valid].astype(int)
        sig_v = sig_c.iloc[np.flatnonzero(valid)]
        start = p + lag_days            # embargo: window opens after the lag
        end = p + lag_days + horizon_days
        ok = end < len(g)
        start, end = start[ok], end[ok]
        sig_v = sig_v.iloc[np.flatnonzero(ok)]
        fwd = np.expm1(cum.values[end] - cum.values[start])
        f = sig_v[["date", "country", "value"]].copy()
        f["fwd_return"] = fwd
        out_frames.append(f)
    if not out_frames:
        return pd.DataFrame(columns=["date", "country", "value", "fwd_return"])
    return pd.concat(out_frames, ignore_index=True).dropna(subset=["value", "fwd_return"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the evaluation harness on a pre-registered hypothesis.")
    parser.add_argument("--hypothesis", required=True)
    parser.add_argument("--table", required=True)
    parser.add_argument("--variable", required=True)
    parser.add_argument("--source", default=None)
    parser.add_argument("--direction", required=True, choices=["higher_is_better", "lower_is_better"])
    parser.add_argument("--frequency", default="monthly", choices=["monthly", "daily"])
    parser.add_argument("--start", default="2008-01-01")
    parser.add_argument("--universe", default="t2_34",
                        help="'t2_34' or a comma-separated list of exact T2 names "
                             "(sub-universes scale the coverage gate and portfolio width).")
    args = parser.parse_args()

    spec = {"table": args.table, "variable": args.variable}
    if args.source:
        spec["source"] = args.source
    result = evaluate_signal(
        hypothesis_id=args.hypothesis,
        signal_spec=spec,
        direction=args.direction,
        frequency=args.frequency,
        start_date=args.start,
        universe=args.universe,
    )
    print(json.dumps({k: v for k, v in result.items() if k not in ("ic",)}, indent=2, default=str)[:3000])
    print("\nIC block:")
    for h, blk in result["ic"].items():
        print(f"  {h}: mean_ic={blk['mean_ic']} nw_t={blk['nw_t']} n={blk['n_dates']} "
              f"pct_pos_years={blk['pct_positive_years']}")
    print(f"\nVERDICT: {result['verdict']}")
    for note in result["gate_notes"]:
        print(f"  - {note}")
    print(f"\nFull result: {result['result_file']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
