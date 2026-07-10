"""
=============================================================================
SCRIPT NAME: score_gap_outcomes.py  (Learning Loop — Stage 1 outcome scorer, PROTOTYPE)
=============================================================================

WHAT THIS DOES (plain language)
-------------------------------
ASADO promotes "gap episodes" — bets that a country's world-state has moved
ahead of its price. Until now nothing ever scored whether those bets paid off.
This script is the deterministic outcome scorer specified in
docs/LEARNING_LOOP_STAGE0_SPEC_2026_07_10.md. For every promoted episode (and
every eligible-but-not-promoted CONTROL), once it has been alive for its full
declared horizon, it computes the honest, net-of-cost active return of the
tradable ETF expression versus an equal-weight basket of all country ETFs over
the exact same window, plus a decomposition into "did the index-space view pay"
(index_information) and "what did the ETF wrapper keep or lose" (etf_capture).

It is APPEND-ONLY: a matured episode is scored once and frozen. It NEVER writes
to the production loop DB or the main warehouse (both are opened read-only and
closed immediately). Output goes to a sandbox parquet under this experiment dir.

FROZEN CONVENTIONS (Arjun, 2026-07-10 — see the Stage 0 spec):
  * Price source .... yfinance adjusted close (auto_adjust=True, dividend+split
                     adjusted = total return). Seeded here from the FDT parquet,
                     which is the same yfinance auto_adjust series; the
                     production scorer tops it up nightly.
  * Direction ....... Score BOTH directions for LEARNING (a short episode is a
                     paper bet — we still learn whether the data led price). The
                     long-only BOOK constraint is carried as the separate boolean
                     `tradable_long_only`; realizable lift is measured on the
                     tradable_long_only=True subset. (Arjun, 2026-07-10: decouple
                     "what we learn from" from "what the book trades".) Borrow
                     cost is NOT modeled for paper shorts (documented); trading
                     costs are charged symmetrically at 25 bp/side.
  * Benchmark ....... per-episode window EW-34: 1/N buy-and-hold across all
                     primary ETFs with a valid price at both endpoints of the
                     episode's own [entry, exit] window.
  * Costs ........... 25 bp per side (entry + exit = 50 bp round-trip).
  * ETF expense ..... NOT deducted (already inside the adjusted-close return).
  * Entry ........... first ETF-calendar close STRICTLY AFTER opened_at (1-day
                     PIT lag; the gap engine scores after the close).
  * Exit ............ entry + horizon_days trading days on the ETF price index.
  * Country leg ..... backward-labeled, 0.0-dropped daily TRI returns compounded
                     over the window (replicates loopdb.daily_country_returns,
                     scripts/loop/loopdb.py:161-195 — a known-tricky date shift).

INPUT FILES (all read-only)
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/etf_t2_map.json
      Canonical country -> primary/alternate ETF ticker map (34 countries).
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/fdt_mech_backtest/etf_prices_full.parquet
      yfinance auto_adjust daily close, wide (Date index x 34 tickers). Seed
      price store; production version refreshes via yfinance nightly.
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
      Loop DB (read-only): tables gap_episodes, gap_holdout_daily.
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
      Main warehouse (read-only): t2_factors_daily (daily country TRI returns).

OUTPUT FILES
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/learning_loop/gap_outcomes.parquet
      Append-only scored outcomes (schema per Stage 0 spec §6). Sandbox only.
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/learning_loop/score_run_report.json
      Honest run summary: counts by role/direction, matured vs pending,
      earliest maturity date.

VERSION: 0.1 (prototype)  LAST UPDATED: 2026-07-10  AUTHOR: Claude (Opus 4.8)

NOTES
  * As of 2026-07-10 NO episode has matured (earliest open 2026-06-22; 21
    trading days is ~2026-07-22), so a correct run reports 0 scored / N pending.
    That is the honest state, not a failure. Arithmetic is validated separately
    in test_score_gap_outcomes.py against known historical price windows.
  * FAIL IS FAIL: missing prices at an endpoint -> the row is written with
    net_active=NULL and an explicit unscoreable_reason. Never zero-filled.
=============================================================================
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, date
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------
# Absolute paths (CLAUDE.md: never bare/relative)
# ----------------------------------------------------------------------------
REPO = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
ETF_MAP_JSON = REPO / "config" / "etf_t2_map.json"
PRICE_PARQUET = REPO / "experiments" / "fdt_mech_backtest" / "etf_prices_full.parquet"
LOOP_DB = REPO / "Data" / "loop" / "asado_loop.duckdb"
MAIN_DB = REPO / "Data" / "asado.duckdb"
OUT_DIR = REPO / "experiments" / "learning_loop"
OUT_PARQUET = OUT_DIR / "gap_outcomes.parquet"
OUT_REPORT = OUT_DIR / "score_run_report.json"

SCORING_VERSION = "0.1"
COST_1WAY = 0.0025  # 25 bp per side, house law (backtest_fdt_layers.py:59)
HORIZON_DAYS = {"5d": 5, "21d": 21, "63d": 63, "126d": 126}

T2_UNIVERSE = [
    "Australia", "Brazil", "Canada", "Chile", "ChinaA", "ChinaH", "Denmark",
    "France", "Germany", "Hong Kong", "India", "Indonesia", "Italy", "Japan",
    "Korea", "Malaysia", "Mexico", "NASDAQ", "Netherlands", "Philippines",
    "Poland", "Saudi Arabia", "Singapore", "South Africa", "Spain", "Sweden",
    "Switzerland", "Taiwan", "Thailand", "Turkey", "U.K.", "U.S.",
    "US SmallCap", "Vietnam",
]


def _hash(*parts: str) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:20]


# ----------------------------------------------------------------------------
# Loaders (each opens read-only and closes immediately — never hold a handle)
# ----------------------------------------------------------------------------
def load_etf_map() -> dict[str, str]:
    """country -> primary ticker (canonical, all 34 present)."""
    d = json.loads(ETF_MAP_JSON.read_text())
    m = d.get("map", d)
    return {k: v["primary"] for k, v in m.items() if v.get("primary")}


def load_prices() -> pd.DataFrame:
    """Wide (DatetimeIndex x ticker) yfinance adjusted close. Index = ETF calendar."""
    px = pd.read_parquet(PRICE_PARQUET)
    px.index = pd.to_datetime(px.index)
    return px.sort_index()


def load_episodes_and_controls() -> tuple[pd.DataFrame, pd.DataFrame]:
    con = duckdb.connect(str(LOOP_DB), read_only=True)
    try:
        eps = con.execute(
            """
            SELECT gap_id, episode_key, entity, direction, horizon_days,
                   preferred_ticker, opened_at, status
            FROM gap_episodes
            """
        ).fetchdf()
        # Controls: eligible but NOT promoted, deduped (the table has no PK and
        # 33/810 candidate_ids duplicate within a day — Stage 0 spec §4).
        controls = con.execute(
            """
            SELECT DISTINCT date AS selection_date, candidate_signature, entity,
                   direction, horizon_bucket
            FROM gap_holdout_daily
            WHERE eligible = TRUE AND promoted = FALSE
            """
        ).fetchdf()
        # Promoted selection dates per gap_id -> the episode's first selection.
        promo = con.execute(
            """
            SELECT gap_id, MIN(date) AS first_selection_date
            FROM gap_holdout_daily
            WHERE promoted = TRUE AND gap_id IS NOT NULL
            GROUP BY gap_id
            """
        ).fetchdf()
    finally:
        con.close()
    eps = eps.merge(promo, on="gap_id", how="left")
    return eps, controls


def load_country_daily_returns() -> pd.DataFrame:
    """Backward-labeled, 0.0-dropped daily TRI returns — faithful replica of
    scripts/loop/loopdb.py:161-195 (daily_country_returns). Tidy (date,country,ret)."""
    con = duckdb.connect(str(MAIN_DB), read_only=True)
    try:
        raw = con.execute(
            """
            SELECT date, country, value FROM t2_factors_daily
            WHERE variable = '1DRet' AND value IS NOT NULL
            ORDER BY country, date
            """
        ).fetchdf()
    finally:
        con.close()
    raw = raw[raw["country"].isin(T2_UNIVERSE)].copy()
    raw["date"] = pd.to_datetime(raw["date"])
    raw["ret"] = raw.groupby("country")["value"].shift(1)  # forward -> backward label
    out = raw[(raw["ret"].notna()) & (raw["ret"] != 0.0)][["date", "country", "ret"]]
    return out.reset_index(drop=True)


# ----------------------------------------------------------------------------
# Window math
# ----------------------------------------------------------------------------
def resolve_entry_exit(opened_at, horizon_days: int, cal: pd.DatetimeIndex):
    """entry = first ETF-calendar date strictly after opened_at; exit = entry +
    horizon_days trading days. Returns (entry_ts, exit_ts, matured?) or (None,...)."""
    opened = pd.to_datetime(opened_at).normalize()
    after = cal[cal > opened]
    if len(after) == 0:
        return None, None, False
    entry = after[0]
    epos = cal.get_loc(entry)
    xpos = epos + int(horizon_days)
    if xpos >= len(cal):
        # exit is beyond the last available trading day -> not matured yet
        return entry, None, False
    return entry, cal[xpos], True


def window_return(prices: pd.Series, entry: pd.Timestamp, exit_: pd.Timestamp):
    """Total return of one ticker over (entry, exit], both endpoints required."""
    if entry not in prices.index or exit_ not in prices.index:
        return None
    p0, p1 = prices.loc[entry], prices.loc[exit_]
    if pd.isna(p0) or pd.isna(p1) or p0 <= 0:
        return None
    return float(p1 / p0 - 1.0)


def ew_window_return(px: pd.DataFrame, entry, exit_) -> float | None:
    """Equal-weight buy-and-hold across all tickers valid at BOTH endpoints."""
    rets = []
    for tk in px.columns:
        r = window_return(px[tk], entry, exit_)
        if r is not None:
            rets.append(r)
    return float(np.mean(rets)) if rets else None


def country_window_return(cret: pd.DataFrame, country: str, entry, exit_) -> float | None:
    """Compound backward-labeled country TRI returns over (entry, exit]."""
    s = cret[(cret["country"] == country) & (cret["date"] > entry) & (cret["date"] <= exit_)]
    if s.empty:
        return None
    return float(np.prod(1.0 + s["ret"].values) - 1.0)


# ----------------------------------------------------------------------------
# Scoring one candidate (promoted episode or control)
# ----------------------------------------------------------------------------
def score_one(*, role, gap_id, candidate_signature, selection_date, entity,
              direction, horizon_days, ticker, opened_at, px, cret, cal) -> dict:
    row = {
        "outcome_id": _hash(str(gap_id or candidate_signature), role,
                            str(horizon_days), SCORING_VERSION),
        "gap_id": gap_id, "candidate_signature": candidate_signature,
        "role": role, "selection_date": selection_date, "entity": entity,
        "direction": 1 if str(direction).lower() == "long" else -1,
        "preferred_ticker": ticker, "benchmark": "EW34_window",
        "evaluation_horizon": int(horizon_days),
        "entry_ts": None, "exit_ts": None,
        "r_etf": None, "r_idx": None, "r_ew": None,
        "gross_active": None, "index_information": None, "etf_capture": None,
        "entry_cost": None, "exit_cost": None, "borrow_cost": 0.0,
        "net_active": None, "stale_price": False, "borrow_estimated": False,
        "tradable_long_only": False,
        "unscoreable_reason": None, "status": None,
        "scoring_version": SCORING_VERSION,
        "scored_at": datetime.now().isoformat(timespec="seconds"),
        "price_source": "yf_adj", "correction_of": None,
    }
    # Score both directions for learning; the long-only book constraint is a flag.
    if not ticker or ticker not in px.columns:
        row["unscoreable_reason"] = "no_expression"
        row["status"] = "unscoreable"
        return row
    row["tradable_long_only"] = (row["direction"] == 1)

    entry, exit_, matured = resolve_entry_exit(opened_at or selection_date,
                                               horizon_days, cal)
    row["entry_ts"] = None if entry is None else entry.isoformat()
    if entry is None:
        row["unscoreable_reason"] = "no_entry_date"
        row["status"] = "unscoreable"
        return row
    if not matured:
        row["status"] = "pending"  # exit_ts in the future; score later, don't freeze
        return row
    row["exit_ts"] = exit_.isoformat()

    r_etf = window_return(px[ticker], entry, exit_)
    r_ew = ew_window_return(px, entry, exit_)
    r_idx = country_window_return(cret, entity, entry, exit_)
    if r_etf is None or r_ew is None:
        row["unscoreable_reason"] = "no_price_history"
        row["status"] = "unscoreable"
        return row

    d = row["direction"]
    row["r_etf"], row["r_ew"], row["r_idx"] = r_etf, r_ew, r_idx
    row["gross_active"] = d * (r_etf - r_ew)
    row["etf_capture"] = None if r_idx is None else d * (r_etf - r_idx)
    row["index_information"] = None if r_idx is None else d * (r_idx - r_ew)
    row["entry_cost"] = COST_1WAY
    row["exit_cost"] = COST_1WAY
    row["net_active"] = row["gross_active"] - 2 * COST_1WAY
    row["status"] = "scored"
    return row


# ----------------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------------
def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    etf_map = load_etf_map()
    px = load_prices()
    cal = px.index
    eps, controls = load_episodes_and_controls()
    cret = load_country_daily_returns()

    rows: list[dict] = []
    for _, e in eps.iterrows():
        ticker = e.get("preferred_ticker") or etf_map.get(e["entity"])
        rows.append(score_one(
            role="promoted", gap_id=e["gap_id"], candidate_signature=None,
            selection_date=(None if pd.isna(e.get("first_selection_date"))
                            else pd.to_datetime(e["first_selection_date"]).date().isoformat()),
            entity=e["entity"], direction=e["direction"],
            horizon_days=int(e["horizon_days"]) if pd.notna(e["horizon_days"]) else 21,
            ticker=ticker, opened_at=e.get("opened_at"), px=px, cret=cret, cal=cal))

    for _, c in controls.iterrows():
        hb = c.get("horizon_bucket") or "21d"
        rows.append(score_one(
            role="control", gap_id=None,
            candidate_signature=c["candidate_signature"],
            selection_date=pd.to_datetime(c["selection_date"]).date().isoformat(),
            entity=c["entity"], direction=c["direction"],
            horizon_days=HORIZON_DAYS.get(hb, 21),
            ticker=etf_map.get(c["entity"]),
            opened_at=c["selection_date"], px=px, cret=cret, cal=cal))

    out = pd.DataFrame(rows)
    out.to_parquet(OUT_PARQUET, index=False)

    # Honest run report
    def _c(df, **kw):
        m = pd.Series(True, index=df.index)
        for k, v in kw.items():
            m &= (df[k] == v)
        return int(m.sum())

    report = {
        "scored_at": datetime.now().isoformat(timespec="seconds"),
        "scoring_version": SCORING_VERSION,
        "last_price_date": cal.max().date().isoformat(),
        "n_rows": len(out),
        "n_promoted": _c(out, role="promoted"),
        "n_control": _c(out, role="control"),
        "n_scored": _c(out, status="scored"),
        "n_pending": _c(out, status="pending"),
        "n_unscoreable": _c(out, status="unscoreable"),
        "n_long": int((out["direction"] == 1).sum()),
        "n_short": int((out["direction"] == -1).sum()),
        "n_tradable_long_only": int(out["tradable_long_only"].sum()),
        "by_status": out["status"].value_counts().to_dict(),
    }
    _pend_promo = (out["status"] == "pending") & (out["role"] == "promoted")
    report["n_pending_promoted"] = int(_pend_promo.sum())
    report["n_pending_promoted_tradable"] = int((_pend_promo & out["tradable_long_only"]).sum())
    OUT_REPORT.write_text(json.dumps(report, indent=2, default=str))

    print(json.dumps(report, indent=2, default=str))
    if report["n_scored"]:
        cols = ["role", "entity", "preferred_ticker", "entry_ts", "exit_ts",
                "r_etf", "r_ew", "net_active"]
        print("\nSCORED OUTCOMES:")
        print(out[out["status"] == "scored"][cols].to_string(index=False))


if __name__ == "__main__":
    main()
