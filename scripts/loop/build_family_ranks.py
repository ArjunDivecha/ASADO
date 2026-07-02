#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: build_family_ranks.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/family_ranks.yaml
    The registry of validated signal families: source table, variable,
    REGISTERED direction, harness verdict/IC, registered universe.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Family source tables (combiner_scores_daily, leadlag_features_daily,
    graph_features_pit_daily, similarity_features_daily, consensus_signals,
    etf_flow_signals, tot_trade_shares) — all read-only.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
    (attached read-only as `asado`) commodity_panel Pink Sheet 3m aggregate
    returns for the derived ToT-impulse column.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/family_ranks_daily.parquet
    Tidy full-history panel: (date, family, country, score, oriented_score,
    rank, universe_n). Parquet-first so the surface survives DB rebuilds.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `family_ranks_daily` — DROP + CREATE from the parquet (idempotent).

VERSION: 1.0
LAST UPDATED: 2026-07-01
AUTHOR: Arjun Divecha (built by agent session, Frontend Alpha Rethink PRD §4.2)

DESCRIPTION:
Builds the unified cross-family rank panel that powers the cockpit's
Consensus Matrix (P2) and Edge Board (P1) — the first increment of the
signal_panel_daily recommendation (data-structure audit R1).

For every family in config/family_ranks.yaml and every date in its source
table, the registered universe's cross-section is oriented by the REGISTERED
direction (higher_is_better keeps the sign; lower_is_better flips it) and
ranked: rank 1 = strongest LONG lean, rank N = strongest SHORT lean. No
re-fitting, no re-optimization — this is a deterministic re-presentation of
surfaces the harness has already measured, with each family's honest
universe respected (countries outside it get NO row, not a zero).

The one derived family is tot_impulse (D1's substrate without its quiet
gates): static Comtrade net trade shares x Pink Sheet aggregate 3m returns
-> per-country monthly impulse, z vs its own trailing 36 months
(min 24 obs). It carries verdict UNTESTED and is excluded from agreement
counts downstream (config: count_in_agreement: false).

DEPENDENCIES:
- duckdb, pandas, numpy, pyyaml (project venv)

USAGE:
 python scripts/loop/build_family_ranks.py           # full rebuild (~5s)
 python scripts/loop/build_family_ranks.py --check   # verify existing table

NOTES:
- Monthly families (cpi_rev, tot_impulse) keep their native month-end date
  labels; consumers must treat per-family as-of dates independently (the
  cockpit shows each column's own as-of).
- FAIL-IS-FAIL: a family whose source table/variable is missing is reported
  loudly and the script exits 1; there is no silent narrowing.
=============================================================================
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.loop.loopdb import LOOP_DIR, T2_UNIVERSE, loop_connection

BASE_DIR = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = BASE_DIR / "config" / "family_ranks.yaml"
OUT_PARQUET = LOOP_DIR / "family_ranks_daily.parquet"

# D1's category -> Pink Sheet aggregate 3m-return variable map (kept in sync
# with scripts/loop/build_dislocations.py::D1_INDEX_MAP).
TOT_INDEX_MAP = {
    "fuel": "WB_CMDTY_IENERGY_RET_3M_PCT",
    "ores_metals": "WB_CMDTY_IMETMIN_RET_3M_PCT",
    "precious": "WB_CMDTY_IPRECIOUSMET_RET_3M_PCT",
    "food": "WB_CMDTY_IFOOD_RET_3M_PCT",
    "agri_raw": "WB_CMDTY_IRAW_MATERIAL_RET_3M_PCT",
    "fertilizer": "WB_CMDTY_IFERTILIZERS_RET_3M_PCT",
}
TOT_Z_WINDOW = 36
TOT_Z_MIN_OBS = 24


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} [family_ranks] {msg}", flush=True)


def load_config() -> dict:
    cfg = yaml.safe_load(CONFIG_PATH.read_text())
    if not cfg.get("families"):
        raise ValueError(f"No families declared in {CONFIG_PATH}")
    return cfg


def family_universe(fam: dict) -> list[str]:
    names = [c.strip() for c in str(fam["universe"]).split(",") if c.strip()]
    unknown = sorted(set(names) - set(T2_UNIVERSE))
    if unknown:
        raise ValueError(f"[{fam['key']}] universe has non-T2 names: {unknown}")
    return names


def table_family_series(con, fam: dict) -> pd.DataFrame:
    """Tidy (date, country, score) for a table-backed family, universe-filtered."""
    df = con.execute(
        f"SELECT date, country, value AS score FROM {fam['table']} "
        f"WHERE variable = ? AND value IS NOT NULL",
        [fam["variable"]],
    ).fetchdf()
    if df.empty:
        raise ValueError(f"[{fam['key']}] no rows for {fam['table']}.{fam['variable']}")
    df["date"] = pd.to_datetime(df["date"])
    return df[df["country"].isin(family_universe(fam))].reset_index(drop=True)


def tot_impulse_series(con, fam: dict) -> pd.DataFrame:
    """Derived ToT-impulse z (monthly): static Comtrade net shares x Pink Sheet
    3m aggregate returns, z vs trailing 36 months per country (min 24 obs)."""
    shares = con.execute(
        "SELECT country, category, net_share FROM tot_trade_shares"
    ).fetchdf()
    if shares.empty:
        raise ValueError("[tot_impulse] tot_trade_shares is empty — run build_tot_shares.py")
    share_piv = shares.pivot_table(index="country", columns="category", values="net_share")

    cm = con.execute(
        f"""SELECT date, variable, value FROM asado.commodity_panel
            WHERE variable IN ({','.join('?' for _ in TOT_INDEX_MAP)}) AND value IS NOT NULL""",
        list(TOT_INDEX_MAP.values()),
    ).fetchdf()
    if cm.empty:
        raise ValueError("[tot_impulse] commodity_panel Pink Sheet aggregates missing")
    cm["date"] = pd.to_datetime(cm["date"])
    cmp_piv = cm.pivot_table(index="date", columns="variable", values="value").sort_index() / 100.0

    cats = [c for c in TOT_INDEX_MAP if c in share_piv.columns]
    universe = family_universe(fam)
    rows = []
    for country in share_piv.index:
        if country not in universe:
            continue
        w = share_piv.loc[country, cats]
        basket = pd.Series(0.0, index=cmp_piv.index)
        for cat in cats:
            if pd.isna(w[cat]):
                continue
            basket = basket + float(w[cat]) * cmp_piv[TOT_INDEX_MAP[cat]].fillna(0.0)
        roll = basket.rolling(TOT_Z_WINDOW, min_periods=TOT_Z_MIN_OBS)
        z = (basket - roll.mean()) / roll.std()
        z = z.replace([np.inf, -np.inf], np.nan).dropna()
        rows.append(pd.DataFrame({"date": z.index, "country": country, "score": z.values}))
    if not rows:
        raise ValueError("[tot_impulse] no country produced an impulse series")
    return pd.concat(rows, ignore_index=True)


def rank_family(tidy: pd.DataFrame, fam: dict) -> pd.DataFrame:
    """Per-date cross-sectional ranks. rank 1 = strongest LONG lean under the
    REGISTERED direction. Dates with < 5 countries are dropped (no honest
    cross-section)."""
    sign = 1.0 if fam["direction"] == "higher_is_better" else -1.0
    out = tidy.copy()
    out["oriented_score"] = sign * out["score"]
    grp = out.groupby("date")["oriented_score"]
    out["rank"] = grp.rank(ascending=False, method="first").astype(int)
    out["universe_n"] = grp.transform("size").astype(int)
    out = out[out["universe_n"] >= 5]
    out["family"] = fam["key"]
    return out[["date", "family", "country", "score", "oriented_score", "rank", "universe_n"]]


def build(con) -> pd.DataFrame:
    cfg = load_config()
    frames = []
    for fam in cfg["families"]:
        if fam["table"] == "derived":
            if fam["variable"] != "TOT_IMPULSE_Z36M":
                raise ValueError(f"[{fam['key']}] unknown derived variable {fam['variable']}")
            tidy = tot_impulse_series(con, fam)
        else:
            tidy = table_family_series(con, fam)
        ranked = rank_family(tidy, fam)
        latest = ranked["date"].max()
        log(f"{fam['key']:12s} rows={len(ranked):8,d} latest={latest.date()} "
            f"n_latest={int(ranked[ranked['date'] == latest]['universe_n'].iloc[0])}")
        frames.append(ranked)
    panel = pd.concat(frames, ignore_index=True)
    dupes = panel.duplicated(["date", "family", "country"]).sum()
    if dupes:
        raise ValueError(f"{dupes} duplicate (date, family, country) rows — refusing to write")
    return panel


def write(con, panel: pd.DataFrame) -> None:
    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(OUT_PARQUET, index=False)
    con.execute("DROP TABLE IF EXISTS family_ranks_daily")
    con.execute(f"""
        CREATE TABLE family_ranks_daily AS
        SELECT date, family, country, score, oriented_score, rank, universe_n
        FROM read_parquet('{OUT_PARQUET}')
    """)
    log(f"wrote {len(panel):,} rows -> {OUT_PARQUET.name} + loop table family_ranks_daily")


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        df = con.execute("""
            SELECT family, COUNT(*) AS n_rows, MAX(date) AS latest,
                   COUNT(DISTINCT country) AS countries
            FROM family_ranks_daily GROUP BY family ORDER BY family
        """).fetchdf()
    finally:
        con.close()
    print(df.to_string(index=False))
    return 0 if len(df) else 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the family_ranks_daily panel (PRD §4.2)")
    ap.add_argument("--check", action="store_true", help="verify the existing table")
    args = ap.parse_args()
    if args.check:
        return check()

    con = loop_connection()
    try:
        panel = build(con)
        write(con, panel)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
