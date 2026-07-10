#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: score_gap_outcomes.py  (Learning Loop — Stage 1 outcome scorer)
=============================================================================

WHAT THIS DOES (plain language)
-------------------------------
ASADO promotes "gap episodes" — bets that a country's world-state has moved
ahead of its price. Nothing used to score whether those bets paid off. This
nightly loop step is the deterministic outcome scorer specified in
docs/LEARNING_LOOP_STAGE0_SPEC_2026_07_10.md. For every promoted episode and
every eligible-but-not-promoted CONTROL, once it has been alive for its full
declared horizon, it computes the honest, net-of-cost active return of the
tradable ETF expression versus an equal-weight basket of all country ETFs over
the exact same window, plus a decomposition into index-space information
content and ETF capture.

It writes the APPEND-ONLY `gap_outcomes` table in the LOOP DB. A matured
episode is scored once and frozen (first-write-wins per outcome_id); pending
episodes are simply not persisted until they mature. It NEVER writes the main
warehouse (attached read-only) and NEVER modifies gap_holdout_daily / gap_episodes.

FROZEN CONVENTIONS (Arjun, 2026-07-10 — see the Stage 0 spec):
  * Price basis .. yfinance adjusted close (auto_adjust total return), kept in
                  loop table `etf_total_return_daily`. Seeded from the FDT
                  parquet; topped up nightly by a BOUNDED, FAIL-SOFT yfinance
                  fetch (keeps the existing table on any fetch failure — the
                  house collector pattern; a stale store just matures fewer
                  episodes, it never fabricates a price).
  * Direction ... score BOTH directions for learning (a short is a paper bet);
                  the long-only BOOK constraint is the boolean tradable_long_only.
                  Realizable lift is measured on tradable_long_only=TRUE.
  * Benchmark ... per-episode window EW-34 (1/N buy-and-hold over the window).
  * Costs ....... 25 bp per side (50 bp round-trip). ETF expense NOT re-deducted.
  * Entry ....... first ETF-calendar close STRICTLY AFTER opened_at (1-day lag).
  * Exit ........ entry + horizon_days trading days on the ETF price index.
  * Country leg . backward-labeled, 0.0-dropped daily TRI returns compounded
                  over the window (loopdb.daily_country_returns semantics).

INPUT FILES (read-only)
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/etf_t2_map.json
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/fdt_mech_backtest/etf_prices_full.parquet   (seed price store)
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb   (attached read-only as `asado`: t2_factors_daily)

INPUT/OUTPUT (loop DB, read + append)
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    reads:  gap_episodes, gap_holdout_daily
    writes: etf_total_return_daily (upsert), gap_outcomes (append-only)

VERSION: 1.0  LAST UPDATED: 2026-07-10  AUTHOR: Claude (Opus 4.8)

NOTES
  * As of 2026-07-10 NO episode has matured (earliest 21d exit ~2026-07-22), so
    a correct run inserts 0 scored rows and reports the pending backlog. That is
    the honest state, not a failure. Arithmetic is validated by
    experiments/learning_loop/test_score_gap_outcomes.py (7/7 green).
  * Registered as an OPTIONAL loop step (governance_contract.yaml): a failure is
    a warning, never a red-light for the nightly job.
  * --loop-db PATH overrides the loop DB (for testing on a copy). Default =
    production loop DB via loopdb.loop_connection().
=============================================================================
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE_DIR))
from scripts.loop.loopdb import loop_connection, MAIN_DB  # noqa: E402

ETF_MAP_JSON = BASE_DIR / "config" / "etf_t2_map.json"
SEED_PARQUET = BASE_DIR / "experiments" / "fdt_mech_backtest" / "etf_prices_full.parquet"

SCORING_VERSION = "1.0"
COST_1WAY = 0.0025
HORIZON_DAYS = {"5d": 5, "21d": 21, "63d": 63, "126d": 126}

T2_UNIVERSE = [
    "Australia", "Brazil", "Canada", "Chile", "ChinaA", "ChinaH", "Denmark",
    "France", "Germany", "Hong Kong", "India", "Indonesia", "Italy", "Japan",
    "Korea", "Malaysia", "Mexico", "NASDAQ", "Netherlands", "Philippines",
    "Poland", "Saudi Arabia", "Singapore", "South Africa", "Spain", "Sweden",
    "Switzerland", "Taiwan", "Thailand", "Turkey", "U.K.", "U.S.",
    "US SmallCap", "Vietnam",
]

GAP_OUTCOMES_DDL = """
CREATE TABLE IF NOT EXISTS gap_outcomes (
  outcome_id VARCHAR, gap_id VARCHAR, candidate_signature VARCHAR, role VARCHAR,
  selection_date DATE, entity VARCHAR, direction INTEGER, preferred_ticker VARCHAR,
  benchmark VARCHAR, evaluation_horizon INTEGER, entry_ts TIMESTAMP, exit_ts TIMESTAMP,
  r_etf DOUBLE, r_idx DOUBLE, r_ew DOUBLE, gross_active DOUBLE,
  index_information DOUBLE, etf_capture DOUBLE, entry_cost DOUBLE, exit_cost DOUBLE,
  borrow_cost DOUBLE, net_active DOUBLE, tradable_long_only BOOLEAN,
  stale_price BOOLEAN, borrow_estimated BOOLEAN, unscoreable_reason VARCHAR,
  scoring_version VARCHAR, scored_at TIMESTAMP, price_source VARCHAR, correction_of VARCHAR
)
"""
OUTCOME_COLS = [
    "outcome_id", "gap_id", "candidate_signature", "role", "selection_date",
    "entity", "direction", "preferred_ticker", "benchmark", "evaluation_horizon",
    "entry_ts", "exit_ts", "r_etf", "r_idx", "r_ew", "gross_active",
    "index_information", "etf_capture", "entry_cost", "exit_cost", "borrow_cost",
    "net_active", "tradable_long_only", "stale_price", "borrow_estimated",
    "unscoreable_reason", "scoring_version", "scored_at", "price_source", "correction_of",
]


def log(msg: str) -> None:
    print(f"[score_gap_outcomes] {msg}", flush=True)


def _hash(*parts) -> str:
    return hashlib.sha1("|".join(str(p) for p in parts).encode()).hexdigest()[:20]


def open_conn(loop_db_override: str | None):
    """Production: loopdb.loop_connection() (guarded, main attached read-only).
    Test: a plain connection to the override path with main attached read-only."""
    if not loop_db_override:
        return loop_connection(read_only=False)
    con = duckdb.connect(loop_db_override)
    try:
        con.execute(f"ATTACH '{MAIN_DB}' AS asado (READ_ONLY)")
    except duckdb.Error as exc:
        if "already attached" not in str(exc).lower():
            raise
    return con


# ----------------------------------------------------------------------------
# ETF total-return price store
# ----------------------------------------------------------------------------
def ensure_price_store(con) -> pd.DataFrame:
    """Maintain etf_total_return_daily(date, ticker, adj_close). Seed from the
    FDT parquet if empty; bounded fail-soft yfinance top-up. Returns wide frame."""
    con.execute(
        "CREATE TABLE IF NOT EXISTS etf_total_return_daily "
        "(date DATE, ticker VARCHAR, adj_close DOUBLE)"
    )
    have = con.execute("SELECT count(*) FROM etf_total_return_daily").fetchone()[0]
    if have == 0 and SEED_PARQUET.exists():
        seed = pd.read_parquet(SEED_PARQUET)
        seed.index = pd.to_datetime(seed.index)
        long = seed.reset_index().melt(id_vars=seed.index.name or "index",
                                       var_name="ticker", value_name="adj_close")
        long.columns = ["date", "ticker", "adj_close"]
        long = long.dropna(subset=["adj_close"])
        con.register("seed_long", long)
        con.execute("INSERT INTO etf_total_return_daily SELECT date, ticker, adj_close FROM seed_long")
        con.unregister("seed_long")
        log(f"seeded etf_total_return_daily from FDT parquet: {len(long)} rows")

    _yfinance_topup(con)  # fail-soft; keeps existing table on any failure

    wide = con.execute(
        "SELECT date, ticker, adj_close FROM etf_total_return_daily"
    ).fetchdf()
    wide["date"] = pd.to_datetime(wide["date"])
    px = wide.pivot_table(index="date", columns="ticker", values="adj_close").sort_index()
    return px


def _yfinance_topup(con) -> None:
    """Bounded, FAIL-SOFT: fetch the recent window for the 34 primaries and
    upsert. ANY failure leaves the existing table intact (house pattern)."""
    try:
        import yfinance as yf  # local import: absence must not break scoring
        tickers = sorted(load_etf_map().values())
        last = con.execute("SELECT max(date) FROM etf_total_return_daily").fetchone()[0]
        start = (pd.to_datetime(last) - pd.Timedelta(days=7)).date().isoformat() if last else "2004-01-01"
        raw = yf.download(tickers, start=start, auto_adjust=True, progress=False,
                          threads=True, timeout=45)
        if raw is None or len(raw) == 0:
            log("yfinance top-up: no data returned; keeping existing store")
            return
        close = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw
        long = close.reset_index().melt(id_vars="Date", var_name="ticker", value_name="adj_close")
        long.columns = ["date", "ticker", "adj_close"]
        long = long.dropna(subset=["adj_close"])
        long["date"] = pd.to_datetime(long["date"]).dt.date
        con.register("tu", long)
        # upsert: delete overlapping (date,ticker) then insert
        con.execute("""
            DELETE FROM etf_total_return_daily o
            USING tu WHERE o.date = tu.date AND o.ticker = tu.ticker
        """)
        con.execute("INSERT INTO etf_total_return_daily SELECT date, ticker, adj_close FROM tu")
        con.unregister("tu")
        log(f"yfinance top-up: upserted {len(long)} rows from {start}")
    except Exception as exc:  # noqa: BLE001  fail-soft by design (documented)
        log(f"yfinance top-up failed (non-fatal, keeping existing store): {exc}")


def load_etf_map() -> dict[str, str]:
    d = json.loads(ETF_MAP_JSON.read_text())
    m = d.get("map", d)
    return {k: v["primary"] for k, v in m.items() if v.get("primary")}


# ----------------------------------------------------------------------------
# Warehouse reads
# ----------------------------------------------------------------------------
def load_episodes_and_controls(con):
    eps = con.execute("""
        SELECT gap_id, episode_key, entity, direction, horizon_days,
               preferred_ticker, opened_at, status
        FROM gap_episodes
    """).fetchdf()
    controls = con.execute("""
        SELECT DISTINCT date AS selection_date, candidate_signature, entity,
               direction, horizon_bucket
        FROM gap_holdout_daily
        WHERE eligible = TRUE AND promoted = FALSE
    """).fetchdf()
    promo = con.execute("""
        SELECT gap_id, MIN(date) AS first_selection_date
        FROM gap_holdout_daily
        WHERE promoted = TRUE AND gap_id IS NOT NULL
        GROUP BY gap_id
    """).fetchdf()
    return eps.merge(promo, on="gap_id", how="left"), controls


def load_country_daily_returns(con) -> pd.DataFrame:
    """Backward-labeled, 0.0-dropped daily TRI returns — loopdb.daily_country_returns
    semantics (scripts/loop/loopdb.py:161-195). Reads the attached warehouse."""
    raw = con.execute("""
        SELECT date, country, value FROM asado.t2_factors_daily
        WHERE variable = '1DRet' AND value IS NOT NULL
        ORDER BY country, date
    """).fetchdf()
    raw = raw[raw["country"].isin(T2_UNIVERSE)].copy()
    raw["date"] = pd.to_datetime(raw["date"])
    raw["ret"] = raw.groupby("country")["value"].shift(1)
    out = raw[(raw["ret"].notna()) & (raw["ret"] != 0.0)][["date", "country", "ret"]]
    return out.reset_index(drop=True)


# ----------------------------------------------------------------------------
# Window math (identical semantics to the validated prototype)
# ----------------------------------------------------------------------------
def resolve_entry_exit(opened_at, horizon_days, cal):
    opened = pd.to_datetime(opened_at).normalize()
    after = cal[cal > opened]
    if len(after) == 0:
        return None, None, False  # no trading day after open yet -> pending
    entry = after[0]
    xpos = cal.get_loc(entry) + int(horizon_days)
    if xpos >= len(cal):
        return entry, None, False  # exit beyond last price -> pending
    return entry, cal[xpos], True


def window_return(prices, entry, exit_):
    if entry not in prices.index or exit_ not in prices.index:
        return None
    p0, p1 = prices.loc[entry], prices.loc[exit_]
    if pd.isna(p0) or pd.isna(p1) or p0 <= 0:
        return None
    return float(p1 / p0 - 1.0)


def ew_window_return(px, entry, exit_):
    rets = [window_return(px[t], entry, exit_) for t in px.columns]
    rets = [r for r in rets if r is not None]
    return float(np.mean(rets)) if rets else None


def country_window_return(cret, country, entry, exit_):
    s = cret[(cret["country"] == country) & (cret["date"] > entry) & (cret["date"] <= exit_)]
    if s.empty:
        return None
    return float(np.prod(1.0 + s["ret"].values) - 1.0)


def score_one(*, role, gap_id, candidate_signature, selection_date, entity,
              direction, horizon_days, ticker, opened_at, px, cret, cal):
    row = {c: None for c in OUTCOME_COLS}
    row.update({
        "outcome_id": _hash(gap_id or candidate_signature, role, horizon_days, SCORING_VERSION),
        "gap_id": gap_id, "candidate_signature": candidate_signature, "role": role,
        "selection_date": selection_date, "entity": entity,
        "direction": 1 if str(direction).lower() == "long" else -1,
        "preferred_ticker": ticker, "benchmark": "EW34_window",
        "evaluation_horizon": int(horizon_days), "borrow_cost": 0.0,
        "tradable_long_only": False, "stale_price": False, "borrow_estimated": False,
        "scoring_version": SCORING_VERSION,
        "scored_at": datetime.now().isoformat(timespec="seconds"),
        "price_source": "yf_adj",
    })
    status = None
    if not ticker or ticker not in px.columns:
        row["unscoreable_reason"] = "no_expression"
        return row, "unscoreable"
    row["tradable_long_only"] = (row["direction"] == 1)

    entry, exit_, matured = resolve_entry_exit(opened_at or selection_date, horizon_days, cal)
    row["entry_ts"] = None if entry is None else entry
    if not matured:
        return row, "pending"
    row["exit_ts"] = exit_

    r_etf = window_return(px[ticker], entry, exit_)
    r_ew = ew_window_return(px, entry, exit_)
    r_idx = country_window_return(cret, entity, entry, exit_)
    if r_etf is None or r_ew is None:
        row["unscoreable_reason"] = "no_price_history"
        return row, "unscoreable"

    d = row["direction"]
    row["r_etf"], row["r_ew"], row["r_idx"] = r_etf, r_ew, r_idx
    row["gross_active"] = d * (r_etf - r_ew)
    row["etf_capture"] = None if r_idx is None else d * (r_etf - r_idx)
    row["index_information"] = None if r_idx is None else d * (r_idx - r_ew)
    row["entry_cost"] = row["exit_cost"] = COST_1WAY
    row["net_active"] = row["gross_active"] - 2 * COST_1WAY
    return row, "scored"


# ----------------------------------------------------------------------------
# Orchestration
# ----------------------------------------------------------------------------
def run(loop_db_override: str | None) -> int:
    con = open_conn(loop_db_override)
    try:
        con.execute(GAP_OUTCOMES_DDL)
        px = ensure_price_store(con)
        cal = px.index
        etf_map = load_etf_map()
        eps, controls = load_episodes_and_controls(con)
        cret = load_country_daily_returns(con)

        rows, statuses = [], []
        for _, e in eps.iterrows():
            r, st = score_one(
                role="promoted", gap_id=e["gap_id"], candidate_signature=None,
                selection_date=(None if pd.isna(e.get("first_selection_date"))
                                else pd.to_datetime(e["first_selection_date"]).date()),
                entity=e["entity"], direction=e["direction"],
                horizon_days=int(e["horizon_days"]) if pd.notna(e["horizon_days"]) else 21,
                ticker=e.get("preferred_ticker") or etf_map.get(e["entity"]),
                opened_at=e.get("opened_at"), px=px, cret=cret, cal=cal)
            rows.append(r); statuses.append(st)
        for _, c in controls.iterrows():
            hb = c.get("horizon_bucket") or "21d"
            r, st = score_one(
                role="control", gap_id=None, candidate_signature=c["candidate_signature"],
                selection_date=pd.to_datetime(c["selection_date"]).date(),
                entity=c["entity"], direction=c["direction"],
                horizon_days=HORIZON_DAYS.get(hb, 21), ticker=etf_map.get(c["entity"]),
                opened_at=c["selection_date"], px=px, cret=cret, cal=cal)
            rows.append(r); statuses.append(st)

        allrows = pd.DataFrame(rows)
        allrows["_status"] = statuses
        # APPEND-ONLY: persist only terminal rows (scored or terminally unscoreable),
        # and only outcome_ids not already frozen.
        terminal = allrows[allrows["_status"].isin(["scored", "unscoreable"])].copy()
        n_new = 0
        if len(terminal):
            new = terminal[OUTCOME_COLS]
            con.register("new_outcomes", new)
            n_new = con.execute("""
                INSERT INTO gap_outcomes
                SELECT * FROM new_outcomes
                WHERE outcome_id NOT IN (SELECT outcome_id FROM gap_outcomes)
                RETURNING 1
            """).fetchdf().shape[0]
            con.unregister("new_outcomes")

        counts = pd.Series(statuses).value_counts().to_dict()
        total_frozen = con.execute("SELECT count(*) FROM gap_outcomes").fetchone()[0]
        n_scored_frozen = con.execute(
            "SELECT count(*) FROM gap_outcomes WHERE unscoreable_reason IS NULL").fetchone()[0]
        log(f"price store: {len(cal)} trading days, last {cal.max().date()}")
        log(f"this run: {counts} | inserted {n_new} new terminal rows")
        log(f"gap_outcomes now: {total_frozen} rows ({n_scored_frozen} scored, "
            f"{total_frozen - n_scored_frozen} terminally unscoreable)")
        return 0
    finally:
        con.close()


def main() -> int:
    ap = argparse.ArgumentParser(description="Score matured gap episodes into gap_outcomes (append-only).")
    ap.add_argument("--loop-db", default=None, help="Override loop DB path (testing on a copy).")
    args = ap.parse_args()
    return run(args.loop_db)


if __name__ == "__main__":
    raise SystemExit(main())
