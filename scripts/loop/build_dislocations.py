#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: build_dislocations.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb (read-only)
  t2_factors_daily (returns, optimizer characteristics), t2_levels_daily
  (Currency, 10Yr Bond, REER), gdelt_factors_daily (attention/tone z),
  factor_returns_daily (8 optimizer factor return series),
  commodity_panel (Pink Sheet aggregate index 3m returns, for D1).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
  graph_features_daily (D2), etf_prices_daily + etf_t2_map (D9),
  portfolio_holdings_daily (D8), thesis_ledger via ledgers module (D8),
  tot_trade_shares (D1, from build_tot_shares.py),
  dislocation_daily (previous runs, for status/persistence).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime/results/regime_tags.parquet
  Latest regime tag attached to every row as context (context only - regime
  test H3 failed, so no mechanical re-weighting).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
  Table `dislocation_daily` - one row per (run_date, dislocation). Appended
  per run; resolved rows are KEPT forever (resolution history is training
  data).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/dislocations/brief_YYYY_MM_DD.md
  The daily brief: <= 100 rows, new-first then by |severity|. This file is
  what gets fed to the Layer 2 reasoning session.

VERSION: 1.1
LAST UPDATED: 2026-06-10
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 2)

DESCRIPTION:
The dislocation engine (PRD section 4): a nightly, deterministic, LLM-free
scan for places where ASADO's subsystems DISAGREE with each other. Each
detector encodes one trade archetype; each firing emits a row with severity,
the disagreeing components, persistence status across days, and regime
context.

v1.1 changes (2026-06-10):
1. TRADING-DAY WINDOWS EVERYWHERE. v1 rolled "5 row" windows over the
   calendar-day grid (weekend placeholder rows included), so windows spanned
   different economic days per surface - the D9 false-positive artifact and
   a silent dilution of every other window. All return windows now come
   from loopdb.daily_country_returns (backward-labeled, real trading days);
   all level windows (FX, 10Y, REER) compress carried-forward placeholder
   rows to REAL observations first.
2. D9 v1.1: T2-vs-ETF gap computed on COMMON dates only - both legs
   compound over the identical date set, so calendar mismatch can no longer
   manufacture a gap. Timezone async (Asia closes before NYSE) remains and
   stays in the note.
3. D1 LIVE (A1 terms-of-trade impulse, v0.5): WDI commodity trade shares
   (tot_trade_shares, 4 categories) x Pink Sheet aggregate index 3m returns
   -> per-country ToT impulse, z vs trailing 36 months. Fires when the
   impulse is extreme AND own equity hasn't repriced AND REER is flat.
   Taiwan is structurally missing (no WDI data) - reported, not dropped.
4. FRESHNESS GUARDS + DETECTOR_DEGRADED rows (constitution section 10.8):
   each detector checks its inputs' last REAL observation; stale surfaces
   are excluded loudly via a DETECTOR_DEGRADED row, never silently scanned
   narrower. (Root cause of the original t2_levels_daily staleness - the
   full-sample winsorize freeze - was fixed in build_t2_master_daily v1.1.)

DETECTORS LIVE: D1 D2 D4 D5 D7 D8 D9.
BLOCKED (insufficient accumulated data, reported in the brief):
  D3 revision momentum (needs >= 2 monthly vintages; first = 2026_06)
  D6 prediction-market disagreement (predmkt history accumulating from 2026-06-10)

STATUS MODEL: new -> persisting / intensifying (|z| up >= 20%) / fading
(|z| down >= 20%) -> resolved (detector stopped firing; resolution_note says
whether the entity repriced with/against the implied direction or decayed).

DEPENDENCIES:
- duckdb, pandas, numpy (project venv)

USAGE:
 python scripts/loop/build_dislocations.py            # nightly run (as-of latest data)
 python scripts/loop/build_dislocations.py --check    # show latest run summary
=============================================================================
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.loop.ledgers import fold_theses
from scripts.loop.loopdb import BASE_DIR, BRIEF_DIR, T2_UNIVERSE, loop_connection, returns_panel

REGIME_TAGS = BASE_DIR / "regime" / "results" / "regime_tags.parquet"

ZWIN = 756       # ~3y of trading days for self-history z-scores
ZMIN = 252       # minimum history before a z is trusted

OPT8 = ["120DTR_TS", "120MA Signal_CS", "120MA Signal_TS", "20DTR_CS",
        "20DTR_TS", "REER_CS", "RSI14_CS", "RSI14_TS"]

# Structural exclusions for D4 legs (not staleness):
NO_FX_LEG = {"U.S.", "NASDAQ", "US SmallCap"}       # USD vs USD = no FX surface
PEGGED_FX = {"Saudi Arabia", "Hong Kong"}           # peg/band: FX z is not an equity cross-check

# D1: tot_trade_shares category -> Pink Sheet aggregate 3m-return variable
D1_INDEX_MAP = {
    "fuel": "WB_CMDTY_IENERGY_RET_3M_PCT",
    "ores_metals": "WB_CMDTY_IMETMIN_RET_3M_PCT",
    "food": "WB_CMDTY_IFOOD_RET_3M_PCT",
    "agri_raw": "WB_CMDTY_IRAW_MATERIAL_RET_3M_PCT",
}
D1_TOT_Z_MIN = 1.5        # |ToT impulse z| trigger
D1_OWN_Z_MAX = 0.5        # own 21d equity return must be unresolved
D1_REER_Z_MAX = 0.5       # REER 3m change must be flat
D1_COMMODITY_MAX_AGE_D = 60   # Pink Sheet is monthly, published early next month
D4_LEVEL_MAX_AGE_D = 7        # FX/10Y series silent > 7 calendar days = stale
D9_ETF_MAX_AGE_D = 7


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} [dislocations] {msg}", flush=True)


def zscore_last(series: pd.Series) -> float:
    """z of the last value vs the series' own trailing history."""
    s = series.dropna()
    if len(s) < ZMIN:
        return np.nan
    hist = s.iloc[-ZWIN:]
    sd = hist.std()
    if not sd or np.isnan(sd):
        return np.nan
    return float((hist.iloc[-1] - hist.mean()) / sd)


def zscore_last_n(series: pd.Series, window: int, min_obs: int) -> float:
    """z of the last value vs its trailing `window` observations."""
    s = series.dropna()
    if len(s) < min_obs:
        return np.nan
    hist = s.iloc[-window:]
    sd = hist.std()
    if not sd or np.isnan(sd):
        return np.nan
    return float((hist.iloc[-1] - hist.mean()) / sd)


def pivot_var(con, table: str, variable: str, qualified: bool = True) -> pd.DataFrame:
    """(dates x countries) panel of one variable from a tidy table."""
    qual = f"asado.{table}" if qualified else table
    df = con.execute(
        f"SELECT date, country, value FROM {qual} WHERE variable = ? AND value IS NOT NULL",
        [variable],
    ).fetchdf()
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["country"].isin(T2_UNIVERSE)]
    return df.pivot_table(index="date", columns="country", values="value").sort_index()


def trailing_ret(piv: pd.DataFrame, n: int) -> pd.DataFrame:
    """Trailing compounded return over each country's own trading days.
    `piv` must be the loopdb.returns_panel (NaN on non-trading days)."""
    out = {}
    for c in piv.columns:
        s = piv[c].dropna()
        out[c] = np.exp(np.log1p(s).rolling(n).sum()) - 1
    return pd.DataFrame(out).reindex(piv.index).ffill(limit=5)


def compress_levels(piv: pd.DataFrame) -> dict[str, pd.Series]:
    """Per-country level series with carried-forward placeholder rows removed:
    keep the first observation and every REAL change. The result is each
    country's own observation calendar (daily for FX, monthly for REER...)."""
    out = {}
    for c in piv.columns:
        s = piv[c].dropna()
        if s.empty:
            out[c] = s
            continue
        keep = s.ne(s.shift(1))
        keep.iloc[0] = True
        out[c] = s[keep]
    return out


def staleness_split(compressed: dict[str, pd.Series], run_date: pd.Timestamp,
                    max_age_days: int, structural_skip: set[str] = frozenset()
                    ) -> tuple[set[str], dict[str, str]]:
    """Split countries into (fresh, stale) by last REAL observation age."""
    fresh, stale = set(), {}
    for c, s in compressed.items():
        if c in structural_skip:
            continue
        if s.empty:
            stale[c] = "no_observations"
        elif (run_date - s.index[-1]).days > max_age_days:
            stale[c] = f"last_real_change={s.index[-1].date()}"
        else:
            fresh.add(c)
    return fresh, stale


def degraded_row(detector: str, archetype: str, surface: str,
                 stale: dict[str, str], note: str) -> dict:
    """Constitution 10.8: inputs missing -> loud DETECTOR_DEGRADED row,
    never a quietly-narrower scan."""
    return {
        "detector": detector, "archetype": "degraded",
        "entity": f"{detector}_INPUTS:{surface}",
        "direction": "flag", "severity": 0.0,
        "components": {
            "stale_or_missing": stale,
            "n_affected": len(stale),
            "reading": f"DETECTOR_DEGRADED - {note}",
        },
    }


# ─────────────────────────────────────────────────────────────────────────────
# Detectors — each returns a list of row dicts
# ─────────────────────────────────────────────────────────────────────────────

def d1_tot_impulse(con, ret21: pd.DataFrame, run_date: pd.Timestamp) -> list[dict]:
    """A1: terms-of-trade impulse without repricing. WDI commodity trade
    shares x Pink Sheet aggregate 3m returns -> ToT impulse z (36m), gated
    on own equity 21d z and REER 3m-change z both flat."""
    rows: list[dict] = []

    shares = con.execute("SELECT country, category, net_share, export_year FROM tot_trade_shares").fetchdf()
    if shares.empty:
        return [degraded_row("D1", "A1", "tot_trade_shares", {"ALL": "table_empty"},
                             "run scripts/loop/build_tot_shares.py")]
    share_piv = shares.pivot_table(index="country", columns="category", values="net_share")

    # Pink Sheet aggregate 3m returns (monthly, percent -> decimal)
    cm = con.execute(
        f"""SELECT date, variable, value FROM asado.commodity_panel
            WHERE variable IN ({','.join('?' for _ in D1_INDEX_MAP)}) AND value IS NOT NULL""",
        list(D1_INDEX_MAP.values()),
    ).fetchdf()
    cm["date"] = pd.to_datetime(cm["date"])
    cmp_piv = cm.pivot_table(index="date", columns="variable", values="value").sort_index() / 100.0
    cmp_asof = cmp_piv.index.max()
    if (run_date - cmp_asof).days > D1_COMMODITY_MAX_AGE_D:
        return [degraded_row("D1", "A1", "commodity_panel",
                             {"ALL": f"latest_month={cmp_asof.date()}"},
                             "Pink Sheet data too old for a live ToT read")]

    # REER 3m change z per country (monthly series compressed from the daily carry)
    reer = compress_levels(pivot_var(con, "t2_levels_daily", "REER"))
    # ToT impulse per country: static net shares x commodity 3m returns
    missing_shares = sorted(set(T2_UNIVERSE) - set(share_piv.index))
    cats = [c for c in D1_INDEX_MAP if c in share_piv.columns]
    for country in share_piv.index:
        w = share_piv.loc[country, cats]
        basket = pd.Series(0.0, index=cmp_piv.index)
        for cat in cats:
            if pd.isna(w[cat]):
                continue
            basket = basket + float(w[cat]) * cmp_piv[D1_INDEX_MAP[cat]].fillna(0.0)
        tot_z = zscore_last_n(basket, window=36, min_obs=24)
        if np.isnan(tot_z) or abs(tot_z) < D1_TOT_Z_MIN:
            continue
        own_z = zscore_last(ret21[country]) if country in ret21.columns else np.nan
        if np.isnan(own_z) or abs(own_z) >= D1_OWN_Z_MAX:
            continue
        reer_s = reer.get(country, pd.Series(dtype=float))
        reer_z = zscore_last_n(reer_s.diff(3), window=36, min_obs=24) if len(reer_s) > 27 else np.nan
        if not np.isnan(reer_z) and abs(reer_z) >= D1_REER_Z_MAX:
            continue
        contrib = {cat: round(float(w[cat]) * float(cmp_piv[D1_INDEX_MAP[cat]].iloc[-1]), 4)
                   for cat in cats if pd.notna(w[cat]) and abs(w[cat]) > 0.005}
        rows.append({
            "detector": "D1", "archetype": "A1", "entity": country,
            "direction": "long" if tot_z > 0 else "short",
            "severity": round(tot_z, 2),
            "components": {
                "tot_impulse_3m": round(float(basket.iloc[-1]), 4),
                "tot_z_36m": round(tot_z, 2),
                "own_ret21_z": round(own_z, 2),
                "reer_chg3m_z": round(reer_z, 2) if not np.isnan(reer_z) else None,
                "net_share_x_ret3m": contrib,
                "commodity_asof": str(cmp_asof.date()),
                "reading": ("ToT improving, equity+REER not repriced"
                            if tot_z > 0 else "ToT deteriorating, equity+REER not repriced"),
                "note": "shares = latest WDI year, static across history (v0.5; Comtrade SITC-2 is the v1 upgrade)",
            },
        })
    if missing_shares:
        rows.append(degraded_row("D1", "A1", "share_coverage",
                                 {c: "no WDI data" for c in missing_shares},
                                 "World Bank has no data for these (Taiwan is structural until Comtrade)"))
    return rows


def d2_graph_propagation(con, ret21: pd.DataFrame) -> list[dict]:
    rows = []
    gap = pivot_var(con, "graph_features_daily", "GRAPH_TRADE_NBR_RET_GAP_21D", qualified=False)
    twohop = pivot_var(con, "graph_features_daily", "GRAPH_TWOHOP_TRADE_GAP_21D", qualified=False)

    for c in gap.columns:
        z = zscore_last(gap[c])
        if np.isnan(z) or abs(z) < 1.5:
            pass
        else:
            own_z = zscore_last(ret21[c]) if c in ret21 else np.nan
            rows.append({
                "detector": "D2", "archetype": "A2", "entity": c,
                "direction": "long" if z > 0 else "short",
                "severity": round(z, 2),
                "components": {
                    "trade_nbr_gap_21d": round(float(gap[c].dropna().iloc[-1]), 4),
                    "gap_z_3y": round(z, 2),
                    "own_ret21_z": round(own_z, 2) if not np.isnan(own_z) else None,
                    "reading": "neighbors outran country" if z > 0 else "country outran neighbors",
                },
            })
        if c in twohop.columns:
            z2 = zscore_last(twohop[c])
            own_z = zscore_last(ret21[c]) if c in ret21 else np.nan
            if not np.isnan(z2) and abs(z2) >= 1.5 and not np.isnan(own_z) and abs(own_z) < 0.5:
                rows.append({
                    "detector": "D2", "archetype": "A2", "entity": c,
                    "direction": "long" if z2 > 0 else "short",
                    "severity": round(z2, 2),
                    "components": {
                        "twohop_gap_21d": round(float(twohop[c].dropna().iloc[-1]), 4),
                        "twohop_z_3y": round(z2, 2),
                        "own_ret21_z": round(own_z, 2),
                        "reading": "two-hop network repriced, endpoint did not",
                    },
                })
    return rows


def d4_cross_asset(con, ret5: pd.DataFrame, run_date: pd.Timestamp) -> list[dict]:
    """A4 v1.1: equity vs FX vs 10Y over the same 5 TRADING days, with
    staleness guards on the level surfaces."""
    rows: list[dict] = []
    fx_c = compress_levels(pivot_var(con, "t2_levels_daily", "Currency"))
    y10_c = compress_levels(pivot_var(con, "t2_levels_daily", "10Yr Bond"))

    fx_fresh, fx_stale = staleness_split(fx_c, run_date, D4_LEVEL_MAX_AGE_D,
                                         structural_skip=NO_FX_LEG | PEGGED_FX)
    y_fresh, y_stale = staleness_split(y10_c, run_date, D4_LEVEL_MAX_AGE_D)

    for c in T2_UNIVERSE:
        if c not in ret5.columns:
            continue
        eq_z = zscore_last(ret5[c])
        if np.isnan(eq_z):
            continue
        # Currency is local-per-USD (JPY ~150, KRW ~1400): UP = local depreciation.
        fx_z = np.nan
        if c in fx_fresh:
            s = fx_c[c]
            fx_z = zscore_last(-(s / s.shift(5) - 1))
        y_z = np.nan
        if c in y_fresh:
            s = y10_c[c]
            y_z = zscore_last(s - s.shift(5))
        conflicts = []
        if not np.isnan(fx_z) and eq_z >= 1 and fx_z <= -1:
            conflicts.append(("fx_weak_vs_equity_strong", fx_z))
        if not np.isnan(fx_z) and eq_z <= -1 and fx_z >= 1:
            conflicts.append(("fx_strong_vs_equity_weak", fx_z))
        if not np.isnan(y_z) and eq_z >= 1 and y_z >= 1.5:
            conflicts.append(("yields_spiking_vs_equity_strong", y_z))
        if not conflicts:
            continue
        kind, other_z = conflicts[0]
        rows.append({
            "detector": "D4", "archetype": "A4", "entity": c,
            "direction": "flag",
            "severity": round(min(abs(eq_z), abs(other_z)) * np.sign(eq_z), 2),
            "components": {
                "equity_5d_z": round(eq_z, 2),
                "fx_strength_5d_z": round(fx_z, 2) if not np.isnan(fx_z) else None,
                "y10_chg_5d_z": round(y_z, 2) if not np.isnan(y_z) else None,
                "conflict": kind,
                "note": "trading-day windows (v1.1); CDS surface monthly-only, daily CDS lands Phase 3",
            },
        })
    if fx_stale:
        rows.append(degraded_row("D4", "A4", "Currency", fx_stale,
                                 "FX leg skipped for these countries (stale/missing series)"))
    if y_stale:
        rows.append(degraded_row("D4", "A4", "10Yr Bond", y_stale,
                                 "10Y leg skipped for these countries (stale/missing series)"))
    return rows


def d5_attention_no_resolution(con, ret5: pd.DataFrame) -> list[dict]:
    rows = []
    att = pivot_var(con, "gdelt_factors_daily", "attention_fast_z_TS")
    tone = pivot_var(con, "gdelt_factors_daily", "foreign_tone_fast_z_TS")
    for c in att.columns:
        s = att[c].dropna()
        if s.empty or (datetime.now() - s.index[-1].to_pydatetime()).days > 7:
            continue
        a = float(s.iloc[-1])
        if a < 2.0:
            continue
        r5_z = zscore_last(ret5[c]) if c in ret5.columns else np.nan
        if np.isnan(r5_z) or abs(r5_z) > 0.5:
            continue
        t = tone[c].dropna()
        tone_z = float(t.iloc[-1]) if len(t) else np.nan
        rows.append({
            "detector": "D5", "archetype": "A5", "entity": c,
            "direction": "flag",
            "severity": round(a, 2),
            "components": {
                "attention_fast_z": round(a, 2),
                "ret5d_z": round(r5_z, 2),
                "foreign_tone_fast_z": round(tone_z, 2) if not np.isnan(tone_z) else None,
                "reading": "news attention spiked, price has not resolved - LOOK, do not trade mechanically",
            },
        })
    return rows


def d7_factor_crowding(con) -> list[dict]:
    rows = []
    # dispersion compression per optimizer characteristic
    for f in OPT8:
        piv = pivot_var(con, "t2_factors_daily", f)
        disp = piv.std(axis=1).dropna()
        if len(disp) < ZMIN:
            continue
        z = zscore_last(disp)
        if np.isnan(z) or z > -1.5:
            continue
        rows.append({
            "detector": "D7", "archetype": "A7", "entity": f,
            "direction": "flag",
            "severity": round(z, 2),
            "components": {
                "xs_dispersion": round(float(disp.iloc[-1]), 4),
                "dispersion_z_3y": round(z, 2),
                "reading": "cross-sectional dispersion compressed - factor crowded, de-weight candidate",
            },
        })
    # herding: avg pairwise 63d corr of the 8 live factor return series
    ph = ",".join("?" for _ in OPT8)
    fr = con.execute(
        f"""SELECT date, factor, value FROM asado.factor_returns_daily
            WHERE source = 't2_optimizer_daily' AND factor IN ({ph}) AND value IS NOT NULL""",
        OPT8,
    ).fetchdf()
    fr["date"] = pd.to_datetime(fr["date"])
    fp = fr.pivot_table(index="date", columns="factor", values="value").sort_index()
    if len(fp) > ZMIN:
        win = fp.iloc[-(ZWIN + 63):]
        vals = []
        idx = []
        for i in range(63, len(win)):
            cm = win.iloc[i - 63:i].corr().values
            off = cm[np.triu_indices_from(cm, k=1)]
            vals.append(np.nanmean(off))
            idx.append(win.index[i])
        cs = pd.Series(vals, index=idx).dropna()
        z = zscore_last(cs)
        if not np.isnan(z) and z >= 1.5:
            rows.append({
                "detector": "D7", "archetype": "A7", "entity": "OPT8_HERDING",
                "direction": "flag",
                "severity": round(z, 2),
                "components": {
                    "avg_pairwise_corr_63d": round(float(cs.iloc[-1]), 3),
                    "corr_z_3y": round(z, 2),
                    "reading": "the 8 live factors are moving together - herding/regime stress",
                },
            })
    return rows


def d8_stewardship(con, ret21: pd.DataFrame) -> list[dict]:
    rows = []
    # open theses
    for tid, t in fold_theses().items():
        if t["status"] != "open":
            continue
        last_mark = t["marks"][-1] if t["marks"] else None
        rows.append({
            "detector": "D8", "archetype": "stewardship", "entity": t["entity"],
            "direction": "flag", "severity": 0.0,
            "components": {
                "thesis_id": tid,
                "direction": t["direction"],
                "cum_return": last_mark["cum_return"] if last_mark else None,
                "invalidation_level": t["invalidation_level"],
                "days_open": last_mark["days_open"] if last_mark else 0,
                "horizon_days": t["horizon_days"],
                "frozen_entry": t["entry_thesis_text"][:160],
            },
        })
    # mapped country-ETF holdings from the latest snapshot
    try:
        h = con.execute(
            """
            SELECT h.symbol, h.position_type, h.market_value, h.weight, m.country
            FROM portfolio_holdings_daily h
            JOIN etf_t2_map m ON h.symbol = m.etf_primary
            WHERE h.date = (SELECT max(date) FROM portfolio_holdings_daily)
            """
        ).fetchdf()
    except Exception:
        h = pd.DataFrame()
    for r in h.itertuples():
        z21 = zscore_last(ret21[r.country]) if r.country in ret21.columns else np.nan
        rows.append({
            "detector": "D8", "archetype": "stewardship", "entity": r.country,
            "direction": "flag", "severity": 0.0,
            "components": {
                "holding": r.symbol,
                "position_type": r.position_type,
                "market_value": round(float(r.market_value), 0) if pd.notna(r.market_value) else None,
                "weight": round(float(r.weight), 4) if pd.notna(r.weight) else None,
                "country_ret21_z": round(z21, 2) if not np.isnan(z21) else None,
                "reading": "live book exposure mapped to T2 country",
            },
        })
    return rows


def d9_index_vs_etf(con, ret_piv: pd.DataFrame, run_date: pd.Timestamp) -> list[dict]:
    """Basis v1.1: T2 vs primary-ETF 5d return gap on COMMON dates only.
    Both legs compound over the identical date labels, so holiday-calendar
    mismatch can no longer manufacture a gap. Timezone async (Asia closes
    hours before NYSE on the same label) remains - kept in the note."""
    rows: list[dict] = []
    etf = con.execute(
        """
        SELECT p.date, m.country, p.close
        FROM etf_prices_daily p JOIN etf_t2_map m ON p.yf_ticker = m.etf_primary
        """
    ).fetchdf()
    if etf.empty:
        return [degraded_row("D9", "basis", "etf_prices_daily", {"ALL": "table_empty"},
                             "news bridge has not accumulated ETF prices")]
    etf["date"] = pd.to_datetime(etf["date"])
    ep = etf.pivot_table(index="date", columns="country", values="close").sort_index()
    stale: dict[str, str] = {}
    for c in ep.columns:
        if c not in ret_piv.columns:
            continue
        etf_ret = ep[c].dropna().pct_change().dropna()
        t2_ret = ret_piv[c].dropna()
        common = t2_ret.index.intersection(etf_ret.index)
        if len(common) < 100:
            stale[c] = f"only {len(common)} common dates"
            continue
        if (run_date - common.max()).days > D9_ETF_MAX_AGE_D:
            stale[c] = f"last_common_date={common.max().date()}"
            continue
        t2c = t2_ret.reindex(common)
        ec = etf_ret.reindex(common)
        t2_5d = np.exp(np.log1p(t2c).rolling(5).sum()) - 1
        etf_5d = np.exp(np.log1p(ec).rolling(5).sum()) - 1
        gap = (t2_5d - etf_5d).dropna()
        sd = gap.std()
        if not sd or np.isnan(sd):
            continue
        z = float((gap.iloc[-1] - gap.mean()) / sd)
        if abs(z) < 2.0:
            continue
        rows.append({
            "detector": "D9", "archetype": "basis", "entity": c,
            "direction": "flag",
            "severity": round(z, 2),
            "components": {
                "t2_ret5d": round(float(t2_5d.iloc[-1]), 4),
                "etf_ret5d": round(float(etf_5d.iloc[-1]), 4),
                "gap_5d": round(float(gap.iloc[-1]), 4),
                "gap_z": round(z, 2),
                "n_obs": int(len(gap)),
                "note": "common-date windows (v1.1); same-label timezone async remains - persistent gaps matter, single days less so",
            },
        })
    if stale:
        rows.append(degraded_row("D9", "basis", "etf_prices_daily", stale,
                                 "ETF leg skipped for these countries"))
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Engine: persistence, status, resolution, brief
# ─────────────────────────────────────────────────────────────────────────────

def current_regime() -> str:
    try:
        rt = pd.read_parquet(REGIME_TAGS)
        last = rt.sort_values("date").iloc[-1]
        return f"{last['regime']} ({last['rules_fired']}, as of {pd.Timestamp(last['date']).date()})"
    except Exception as exc:
        return f"regime_unavailable ({exc.__class__.__name__})"


def run(as_of: Optional[str] = None) -> int:
    con = loop_connection()
    try:
        ret_piv = returns_panel(con)
        data_date = ret_piv.index.max()
        run_date = pd.Timestamp(as_of) if as_of else data_date
        log(f"run date {run_date.date()} (latest return data {data_date.date()})")

        ret5 = trailing_ret(ret_piv, 5)
        ret21 = trailing_ret(ret_piv, 21)

        detected: list[dict] = []
        for name, fn in [
            ("D1", lambda: d1_tot_impulse(con, ret21, run_date)),
            ("D2", lambda: d2_graph_propagation(con, ret21)),
            ("D4", lambda: d4_cross_asset(con, ret5, run_date)),
            ("D5", lambda: d5_attention_no_resolution(con, ret5)),
            ("D7", lambda: d7_factor_crowding(con)),
            ("D8", lambda: d8_stewardship(con, ret21)),
            ("D9", lambda: d9_index_vs_etf(con, ret_piv, run_date)),
        ]:
            got = fn()
            n_degraded = sum(1 for r in got if r["archetype"] == "degraded")
            log(f"{name}: {len(got) - n_degraded} row(s)"
                + (f" + {n_degraded} DEGRADED notice(s)" if n_degraded else ""))
            detected += got

        # ── status vs previous run ──────────────────────────────────────
        has_table = con.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name='dislocation_daily'"
        ).fetchone()[0]
        prev = pd.DataFrame()
        if has_table:
            prev = con.execute(
                """
                SELECT * FROM dislocation_daily
                WHERE date = (SELECT max(date) FROM dislocation_daily WHERE date < ?)
                  AND status != 'resolved'
                """, [str(run_date.date())],
            ).fetchdf()
        prev_keys = {}
        if not prev.empty:
            prev_keys = {
                (r.detector, r.entity): r for r in prev.itertuples()
            }

        regime = current_regime()
        out_rows = []
        seen_keys = set()
        for d in detected:
            key = (d["detector"], d["entity"])
            seen_keys.add(key)
            p = prev_keys.get(key)
            if p is None:
                status, first_seen, days_active = "new", run_date.date(), 1
            else:
                first_seen = pd.Timestamp(p.first_seen).date()
                days_active = int(p.days_active) + 1
                ps, ns = abs(p.severity), abs(d["severity"])
                if ps > 0 and ns >= 1.2 * ps:
                    status = "intensifying"
                elif ps > 0 and ns <= 0.8 * ps:
                    status = "fading"
                else:
                    status = "persisting"
            did = hashlib.sha1(f"{d['detector']}|{d['entity']}|{first_seen}".encode()).hexdigest()[:12]
            out_rows.append({
                "date": str(run_date.date()),
                "dislocation_id": did,
                "detector": d["detector"],
                "archetype": d["archetype"],
                "entity": d["entity"],
                "direction": d["direction"],
                "severity": d["severity"],
                "components_json": json.dumps(d["components"], default=str),
                "regime_context": regime,
                "status": status,
                "first_seen": str(first_seen),
                "days_active": days_active,
                "resolution_note": None,
            })

        # rows active yesterday but not today -> resolved
        for key, p in prev_keys.items():
            if key in seen_keys or p.detector == "D8":
                continue
            entity = p.entity
            note = "condition_cleared"
            if p.direction in ("long", "short") and entity in ret5.columns:
                r5 = ret5[entity].dropna()
                if len(r5):
                    move = float(r5.iloc[-1])
                    if abs(move) >= 0.01:
                        with_dir = (move > 0) == (p.direction == "long")
                        note = "repriced_with" if with_dir else "repriced_against"
                    else:
                        note = "decayed"
            out_rows.append({
                "date": str(run_date.date()),
                "dislocation_id": p.dislocation_id,
                "detector": p.detector,
                "archetype": p.archetype,
                "entity": entity,
                "direction": p.direction,
                "severity": 0.0,
                "components_json": p.components_json,
                "regime_context": regime,
                "status": "resolved",
                "first_seen": str(pd.Timestamp(p.first_seen).date()),
                "days_active": int(p.days_active),
                "resolution_note": note,
            })

        df = pd.DataFrame(out_rows)
        # Explicit schema: CREATE TABLE AS on day 1 inferred an all-NULL
        # resolution_note as INTEGER, which broke day-2 inserts of real notes.
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS dislocation_daily (
                date VARCHAR, dislocation_id VARCHAR, detector VARCHAR,
                archetype VARCHAR, entity VARCHAR, direction VARCHAR,
                severity DOUBLE, components_json VARCHAR, regime_context VARCHAR,
                status VARCHAR, first_seen VARCHAR, days_active BIGINT,
                resolution_note VARCHAR
            )
            """
        )
        con.execute("ALTER TABLE dislocation_daily ALTER resolution_note SET DATA TYPE VARCHAR")
        con.execute("DELETE FROM dislocation_daily WHERE date = ?", [str(run_date.date())])
        if not df.empty:
            df["resolution_note"] = df["resolution_note"].astype("string")
            # BY NAME: dict-built rows don't guarantee the table's column order
            con.execute("INSERT INTO dislocation_daily BY NAME SELECT * FROM df")
        log(f"dislocation_daily: +{len(df)} rows for {run_date.date()}")

        write_brief(df, run_date, regime)
        return 0
    finally:
        con.close()


def write_brief(df: pd.DataFrame, run_date: pd.Timestamp, regime: str) -> None:
    BRIEF_DIR.mkdir(parents=True, exist_ok=True)
    path = BRIEF_DIR / f"brief_{run_date.strftime('%Y_%m_%d')}.md"
    lines = [
        f"# Dislocation brief — {run_date.date()}",
        "",
        f"- Regime context: **{regime}** (context only; no mechanical overlay — H3 failed)",
        f"- Rows: {len(df)} | detectors live: D1 D2 D4 D5 D7 D8 D9 (v1.1 trading-day windows) | blocked: D3 (needs ≥2 vintages; first = 2026_06), D6 (predmkt accumulating since 2026-06-10)",
        "- Read me: severity = z vs own 3y history. `flag` = informational, not directional. D5 is a LOOK trigger, never a trade signal. DEGRADED rows = inputs stale/missing, scan ran narrower than designed.",
        "",
    ]
    if df.empty:
        lines.append("No dislocations detected.")
    else:
        active = df[df["status"] != "resolved"].copy()
        resolved = df[df["status"] == "resolved"]
        status_order = {"new": 0, "intensifying": 1, "persisting": 2, "fading": 3}
        active["_o"] = active["status"].map(status_order).fillna(9)
        active["_s"] = active["severity"].abs()
        active = active.sort_values(["_o", "_s"], ascending=[True, False]).head(100)
        lines.append("| status | det | entity | dir | sev | days | components |")
        lines.append("|---|---|---|---|---|---|---|")
        for r in active.itertuples():
            comp = json.loads(r.components_json)
            comp_str = "; ".join(f"{k}={v}" for k, v in comp.items() if k not in ("reading", "note"))
            reading = comp.get("reading") or comp.get("note") or ""
            lines.append(
                f"| {r.status} | {r.detector} | {r.entity} | {r.direction} | {r.severity} "
                f"| {r.days_active} | {comp_str}{(' — ' + reading) if reading else ''} |"
            )
        if not resolved.empty:
            lines += ["", "## Resolved since last run", ""]
            for r in resolved.itertuples():
                lines.append(f"- {r.detector} {r.entity} ({r.direction}) after {r.days_active}d: **{r.resolution_note}**")
    path.write_text("\n".join(lines) + "\n")
    log(f"brief: {path}")


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        df = con.execute(
            """
            SELECT date, detector, count(*) AS n, round(avg(abs(severity)), 2) AS avg_sev
            FROM dislocation_daily
            WHERE date = (SELECT max(date) FROM dislocation_daily)
            GROUP BY date, detector ORDER BY detector
            """
        ).fetchdf()
        print(df.to_string(index=False))
        return 0
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Nightly dislocation engine (Layer 1, deterministic, no LLM).")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--as-of", default=None, help="Override run date (YYYY-MM-DD), default = latest data date.")
    args = parser.parse_args()
    return check() if args.check else run(args.as_of)


if __name__ == "__main__":
    sys.exit(main())
