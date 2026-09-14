# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/src/p10_portfolio.py
#
# PRD 14 — gross ranking portfolio on FROZEN forecasts. No weight
# optimization, no thresholds, no cost gates (cost law retired; descriptive
# turnover only).
#
#   * origin with n eligible markets -> k = max(1, floor(0.2 n)); 50% of the
#     cohort sleeve long the top-k, 50% short the bottom-k; equal weight;
#     boundary ties split fractional membership equally (T50)
#   * 20 sleeves, each compounding its own capital; one new cohort per
#     origin in the next free sleeve on the SHARED opportunity calendar
#     (planned max exit across ALL eligible markets); full sleeves -> skip
#     the origin for every model's portfolio, still score statistically
#   * daily marks at latest legitimately published TRI marks; holidays use
#     last mark with a freshness flag; gross only
#   * portfolio Sharpe from marked daily NAV returns, NEVER from the
#     overlapping labels (T52)
# =============================================================================
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))

EXP = Path(__file__).resolve().parents[1]
AUDIT = EXP / "audit"
RESULTS = EXP / "results"
SNAP = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/"
            "Data/work/experiments/nonlinear_country_returns/"
            "snapshot_2026_09_13")
N_SLEEVES = 20


def select_members(g: pd.DataFrame, score: str):
    """k = max(1, floor(0.2 n)); top-k long / bottom-k short with boundary
    ties split fractionally. Returns (long_weights, short_weights) dicts."""
    n = len(g)
    k = max(1, int(np.floor(0.2 * n)))
    s = g[score]
    if s.nunique() <= 1:                      # all-constant: no exposure
        return {}, {}
    ranks_hi = s.rank(ascending=False, method="min")
    ranks_lo = s.rank(ascending=True, method="min")
    # group-aware boundary handling: count strictly-above members, split
    # remaining slots across the boundary tie group
    def side(ranks):
        w = {}
        groups = ranks.groupby(ranks)
        used = 0
        for rv in sorted(groups.groups):
            grp = list(groups.groups[rv])
            slots = k - used
            if slots <= 0:
                break
            take = min(len(grp), slots)
            frac = take / len(grp)
            for m in grp:
                w[m] = frac
            used += take
        return w
    lw = side(ranks_hi); sw = side(ranks_lo)
    tot_l, tot_s = sum(lw.values()), sum(sw.values())
    if tot_l > 0:
        lw = {m: v / tot_l for m, v in lw.items()}
    if tot_s > 0:
        sw = {m: v / tot_s for m, v in sw.items()}
    return lw, sw


def build_tri_panel() -> pd.DataFrame:
    """Daily USD TRI per market from the frozen snapshot."""
    t2 = pd.read_parquet(SNAP / "t2_levels_daily.parquet")
    t2 = t2[t2["variable"] == "Tot Return Index"]
    t2["date"] = pd.to_datetime(t2["date"])
    return t2.pivot_table(index="date", columns="country",
                          values="value", aggfunc="last").sort_index()


def run_portfolio(forecasts: pd.DataFrame, score: str,
                  cal: pd.DataFrame, tri: pd.DataFrame) -> dict:
    """20-sleeve cohort engine. cal: calendar_store with market/date."""
    fc = forecasts.dropna(subset=[score]).copy()
    fc["origin_date"] = pd.to_datetime(fc["origin_date"])
    lab = pd.read_parquet(AUDIT / "labels.parquet")
    lab = lab[lab.horizon == "h20"]
    lab["origin_date"] = pd.to_datetime(lab["origin_date"])
    lab["entry_date"] = pd.to_datetime(lab["entry_date"])
    lab["exit_date"] = pd.to_datetime(lab["exit_date"])
    fc = fc.merge(lab[["origin_date", "market", "entry_date", "exit_date"]],
                  on=["origin_date", "market"], how="left")

    sleeves = [{"capital": 1.0 / N_SLEEVES, "cohort": None}
               for _ in range(N_SLEEVES)]
    nav_hist, skips, cohorts = [], [], []

    origins = np.sort(fc["origin_date"].unique())
    # daily mark axis: union of all relevant dates
    all_days = tri.index
    for od in origins:
        g = fc[fc.origin_date == od]
        lw, sw = select_members(g, score)
        if not lw and not sw:
            continue
        # opportunity calendar: planned max exit across ALL eligible
        # markets at this origin (not only selected)
        max_exit = g["exit_date"].max()
        free = next((i for i, s in enumerate(sleeves)
                     if s["cohort"] is None), None)
        if free is None:
            skips.append(str(pd.Timestamp(od).date()))
            continue
        cap = sleeves[free]["capital"]
        legs = []
        for m, w in lw.items():
            e = g[g.market == m].iloc[0]
            legs.append({"market": m, "side": 1.0, "w": w,
                         "entry": e["entry_date"], "exit": e["exit_date"]})
        for m, w in sw.items():
            e = g[g.market == m].iloc[0]
            legs.append({"market": m, "side": -1.0, "w": w,
                         "entry": e["entry_date"], "exit": e["exit_date"]})
        sleeves[free]["cohort"] = {"origin": od, "cap0": cap,
                                   "legs": legs, "units": {}}
        cohorts.append({"origin": str(pd.Timestamp(od).date()),
                        "sleeve": free, "n_long": len(lw),
                        "n_short": len(sw), "max_exit": str(max_exit.date())})

    # mark daily: open cohort at entry close, value legs at TRI marks,
    # close at exit close. Sleeve NAV = cap0 * (1 + leg P&L weighted).
    def mark(cohort, day):
        tot = 0.0
        for leg in cohort["legs"]:
            m = leg["market"]
            if m not in tri.columns:
                return None
            if day < leg["entry"]:
                return cohort["cap0"]
            pe = tri[m].asof(leg["entry"])
            px = tri[m].asof(min(day, leg["exit"]))
            if not np.isfinite(pe) or not np.isfinite(px):
                return None
            tot += leg["side"] * leg["w"] * (px / pe - 1.0)
        # each side's weights sum to 1 and gets half the sleeve capital:
        # NAV = cap0 * (1 + 0.5*long_ret + 0.5*(-short_ret)) = 1 + 0.5*tot
        return cohort["cap0"] * (1.0 + 0.5 * tot)

    start = fc["entry_date"].min()
    end = tri.index[-1]
    for day in all_days[(all_days >= start) & (all_days <= end)]:
        nav = 0.0
        for s in sleeves:
            if s["cohort"] is None:
                nav += s["capital"]
                continue
            v = mark(s["cohort"], day)
            if v is None:
                nav += s["capital"]
                continue
            nav += v
            # close cohort when all legs past exit
            if all(day >= l["exit"] for l in s["cohort"]["legs"]):
                s["capital"] = v
                s["cohort"] = None
        nav_hist.append({"date": day, "nav": nav})
    nav = pd.DataFrame(nav_hist).set_index("date")
    nav["ret"] = nav["nav"].pct_change()
    rets = nav["ret"].dropna()
    sharpe = float(rets.mean() / rets.std() * np.sqrt(252)) \
        if rets.std() > 0 else 0.0
    cummax = nav["nav"].cummax()
    mdd = float(((nav["nav"] - cummax) / cummax).min())
    return {"score": score, "n_cohorts": len(cohorts),
            "n_skipped_origins": len(skips), "skipped": skips,
            "sharpe_gross": sharpe, "max_drawdown": mdd,
            "total_return": float(nav["nav"].iloc[-1] - 1.0),
            "n_days": int(len(nav)),
            "annualized_return": float(
                (nav["nav"].iloc[-1]) ** (252 / max(len(nav), 1)) - 1),
            "nav": nav}


def main() -> None:
    from runner import STREAMS
    from metrics import collect_forecasts
    REPLAY = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/"
                  "Data/work/experiments/nonlinear_country_returns/"
                  "p07_replay_real_v2")
    fc = collect_forecasts(REPLAY, STREAMS)
    cal = pd.read_parquet(AUDIT / "calendar_store.parquet")
    tri = build_tri_panel()
    out = {}
    for m in ("N_S", "L_S", "L_X", "L_star", "B0"):
        res = run_portfolio(fc, m, cal, tri)
        nav = res.pop("nav")
        nav.to_parquet(RESULTS / f"nav_{m}.parquet")
        out[m] = res
        print(f"{m}: sharpe={res['sharpe_gross']:.2f} "
              f"ret={res['total_return']:.1%} mdd={res['max_drawdown']:.1%} "
              f"cohorts={res['n_cohorts']} skips={res['n_skipped_origins']}")
    out["_note"] = ("gross reference portfolio; 20 sleeves; 50/50 long/"
                    "short; daily marks at latest published TRI; no costs; "
                    "T52: Sharpe from marked daily returns, not labels")
    (RESULTS / "portfolio_gross.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
