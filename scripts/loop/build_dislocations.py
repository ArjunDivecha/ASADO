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
  market_implied_daily + market_implied_signals (D10 + brief stress section,
  from collect_market_implied_bbg.py / load_market_implied.py),
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

VERSION: 1.2
LAST UPDATED: 2026-06-11
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

DETECTORS LIVE: D1 D2 D3 D4 D5 D7 D8 D9 D10.
  D3 went live 2026-06-11 (A3 revision momentum, v1): WEO vintage backfill
  2008+ via collect_weo_vintages.py gives every revision its own z-history;
  D4 v2 same date: daily 5Y CDS leg + direct-pull 10Y (sovereign_daily).
  D10 went live 2026-06-11 (A10 FX options vs equity, v1): 25D risk-reversal
  and implied-vol z's from the market-implied stress layer vs own-equity
  trading-day return z's; two conflict shapes (options stress unpriced by
  equity / equity stress unconfirmed by options).
BLOCKED (insufficient accumulated data, reported in the brief):
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

# D7 scans ALL T2 factor return series in factor_returns_daily (live list,
# pulled at runtime). The old hardcoded OPT8 whitelist was a stale artifact
# of the retired Fuzzy Daily project and was removed 2026-06-10.
D7_MAX_DISPERSION_FLAGS = 10   # report only the most-compressed factors

# Structural exclusions for D4 legs (not staleness):
NO_FX_LEG = {"U.S.", "NASDAQ", "US SmallCap"}       # USD vs USD = no FX surface
PEGGED_FX = {"Saudi Arabia", "Hong Kong"}           # peg/band: FX z is not an equity cross-check
NO_CDS = {"Canada", "Denmark", "Germany", "Hong Kong", "India", "NASDAQ",
          "Netherlands", "Singapore", "Sweden", "Switzerland", "Taiwan",
          "U.K.", "U.S.", "US SmallCap"}            # no liquid sovereign CDS ticker

# D1: tot_trade_shares category -> Pink Sheet aggregate 3m-return variable
# (v1, 2026-06-11: 6 Comtrade HS-chapter categories; precious + fertilizer
# were invisible in the old WDI 4-section version)
D1_INDEX_MAP = {
    "fuel": "WB_CMDTY_IENERGY_RET_3M_PCT",
    "ores_metals": "WB_CMDTY_IMETMIN_RET_3M_PCT",
    "precious": "WB_CMDTY_IPRECIOUSMET_RET_3M_PCT",
    "food": "WB_CMDTY_IFOOD_RET_3M_PCT",
    "agri_raw": "WB_CMDTY_IRAW_MATERIAL_RET_3M_PCT",
    "fertilizer": "WB_CMDTY_IFERTILIZERS_RET_3M_PCT",
}
D1_TOT_Z_MIN = 1.5        # |ToT impulse z| trigger
D1_OWN_Z_MAX = 0.5        # own 21d equity return must be unresolved
D1_REER_Z_MAX = 0.5       # REER 3m change must be flat
D1_COMMODITY_MAX_AGE_D = 60   # Pink Sheet is monthly, published early next month
D3_REVISION_MAX_AGE_D = 120   # WEO vintage counts as live news for ~4 months
D4_LEVEL_MAX_AGE_D = 7        # FX/10Y series silent > 7 calendar days = stale
D9_ETF_MAX_AGE_D = 7

# D10: FX options market vs equity (market_implied_* tables, loop DB)
NO_FX_OPTIONS = {"U.S.", "NASDAQ", "US SmallCap",   # USD numeraire, no pair
                 "Denmark", "Vietnam"}              # no liquid vol surface
PEG_FX_OPTIONS = {"Hong Kong", "Saudi Arabia"}      # included: options price peg risk
D10_MAX_AGE_D = 7         # surface silent > 7 calendar days = stale
D10_RR_Z_MIN = 2.0        # 25D risk-reversal z trigger (crash-protection bid)
D10_IV_Z_MIN = 2.5        # 1M ATM implied-vol z trigger
D10_EQ_QUIET_MAX = 0.75   # |21d equity z| below this = "price has not resolved"
D10_EQ_STRESS_MIN = -1.5  # 5d equity z at/below this = equity stress leg
D10_OPT_QUIET_MAX = 0.5   # RR and vol z at/below this = options see nothing


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
                "note": "shares = latest Comtrade HS-chapter year (2023-2025), static across history; 6 categories incl. precious+fertilizer (D1 v1, 2026-06-11)",
            },
        })
    if missing_shares:
        rows.append(degraded_row("D1", "A1", "share_coverage",
                                 {c: "no trade-share data" for c in missing_shares},
                                 "neither WDI nor WITS produced shares for these countries"))
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


def d3_revision_momentum(con, ret_piv: pd.DataFrame, run_date: pd.Timestamp) -> list[dict]:
    """A3 v1 (2026-06-11, PRD Priority 9): WEO forecast-revision momentum
    quadrants. Latest-vintage GDP-growth revision (current-year + next-year
    average), z-scored against the country's OWN 2008+ revision history from
    the weo_vintages backfill, crossed with 6m price momentum:

        revised UP   + price flat/weak   -> long flag  (upgrade not priced)
        revised DOWN + price flat/strong -> short flag (downgrade not priced)

    A vintage is treated as live news for D3_REVISION_MAX_AGE_D calendar days
    after publication; past that the revision is stale and D3 goes quiet
    until the next vintage."""
    rows: list[dict] = []
    rev = con.execute(
        """
        SELECT vintage, vintage_date, country, target_year, revision
        FROM weo_revisions
        WHERE variable = 'WEO_GDP_GROWTH_PCT'
          AND target_year - CAST(substr(vintage, 1, 4) AS INTEGER) IN (0, 1)
        """
    ).fetchdf()
    if rev.empty:
        return [degraded_row("D3", "A3", "weo_revisions", {"ALL": "table_empty"},
                             "run scripts/loop/collect_weo_vintages.py")]
    rev["vintage_date"] = pd.to_datetime(rev["vintage_date"])

    latest_v = rev["vintage"].max()
    latest_date = rev.loc[rev["vintage"] == latest_v, "vintage_date"].iloc[0]
    age_d = (run_date - latest_date).days
    if age_d > D3_REVISION_MAX_AGE_D:
        return [degraded_row("D3", "A3", "weo_vintage_age",
                             {latest_v: f"published {latest_date.date()}, {age_d}d ago"},
                             "latest WEO vintage older than the live-news window; D3 quiet until next vintage")]

    # avg of current-year + next-year revision, per (vintage, country)
    avg = (rev.groupby(["vintage", "country"])["revision"].mean()
              .unstack("country").sort_index())
    ret126 = trailing_ret(ret_piv, 126)

    for c in T2_UNIVERSE:
        if c not in avg.columns:
            continue
        hist = avg[c].dropna()
        if latest_v not in hist.index or len(hist) < 10:
            continue
        cur = float(hist.loc[latest_v])
        prior = hist.drop(index=latest_v)
        sd = prior.std()
        if not sd or np.isnan(sd):
            continue
        rev_z = (cur - prior.mean()) / sd
        if abs(rev_z) < 1.0:
            continue
        mom_z = zscore_last(ret126[c]) if c in ret126.columns else np.nan
        if np.isnan(mom_z):
            continue
        # only the unpriced quadrants fire
        if rev_z >= 1.0 and mom_z < 0.5:
            direction, reading = "long", "forecast revised up, price has not followed"
        elif rev_z <= -1.0 and mom_z > -0.5:
            direction, reading = "short", "forecast revised down, price has not repriced"
        else:
            continue
        rows.append({
            "detector": "D3", "archetype": "A3", "entity": c,
            "direction": direction,
            "severity": round(rev_z, 2),
            "components": {
                "vintage": latest_v,
                "gdp_revision_pp": round(cur, 2),
                "revision_z_vs_own_history": round(rev_z, 2),
                "n_history_vintages": int(len(prior)),
                "mom_126d_z": round(mom_z, 2),
                "reading": reading,
                "note": "WEO semi-annual vintages (2008+ backfill via DBnomics); avg of current+next-year GDP growth revisions",
            },
        })
    return rows


def d4_cross_asset(con, ret5: pd.DataFrame, run_date: pd.Timestamp) -> list[dict]:
    """A4 v2: equity vs FX vs 10Y vs 5Y CDS over the same 5 TRADING days,
    with staleness guards on the level surfaces.

    v2 (2026-06-11, PRD Priority 8): daily CDS + fresh direct-pull 10Y from
    `sovereign_daily` (Bloomberg, scripts/loop/collect_sovereign_daily_bbg.py).
    10Y prefers the direct pull (fixes Taiwan's dead t2 series), falling back
    to t2_levels_daily for countries the pull does not cover."""
    rows: list[dict] = []
    fx_c = compress_levels(pivot_var(con, "t2_levels_daily", "Currency"))

    # 10Y: direct Bloomberg pull first, t2 levels as fallback per-country
    y10_sov = pivot_var(con, "sovereign_daily", "SOV_10Y_YIELD_PCT", qualified=False)
    y10_t2 = pivot_var(con, "t2_levels_daily", "10Yr Bond")
    t2_only = [c for c in y10_t2.columns if c not in y10_sov.columns]
    y10_piv = y10_sov.join(y10_t2[t2_only], how="outer") if t2_only else y10_sov
    y10_c = compress_levels(y10_piv)

    cds_c = compress_levels(pivot_var(con, "sovereign_daily", "SOV_CDS_5Y_BP", qualified=False))

    fx_fresh, fx_stale = staleness_split(fx_c, run_date, D4_LEVEL_MAX_AGE_D,
                                         structural_skip=NO_FX_LEG | PEGGED_FX)
    y_fresh, y_stale = staleness_split(y10_c, run_date, D4_LEVEL_MAX_AGE_D)
    cds_fresh, cds_stale = staleness_split(cds_c, run_date, D4_LEVEL_MAX_AGE_D,
                                           structural_skip=NO_CDS)

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
        # CDS spread in bp: UP = credit deterioration (risk-off).
        cds_z = np.nan
        if c in cds_fresh:
            s = cds_c[c]
            cds_z = zscore_last(s - s.shift(5))
        conflicts = []
        if not np.isnan(fx_z) and eq_z >= 1 and fx_z <= -1:
            conflicts.append(("fx_weak_vs_equity_strong", fx_z))
        if not np.isnan(fx_z) and eq_z <= -1 and fx_z >= 1:
            conflicts.append(("fx_strong_vs_equity_weak", fx_z))
        if not np.isnan(y_z) and eq_z >= 1 and y_z >= 1.5:
            conflicts.append(("yields_spiking_vs_equity_strong", y_z))
        if not np.isnan(cds_z) and eq_z >= 1 and cds_z >= 1.5:
            conflicts.append(("cds_widening_vs_equity_strong", cds_z))
        if not np.isnan(cds_z) and eq_z <= -1 and cds_z <= -1.5:
            conflicts.append(("cds_tightening_vs_equity_weak", cds_z))
        if not conflicts:
            continue
        # severity from the strongest conflicting surface
        kind, other_z = max(conflicts, key=lambda kv: abs(kv[1]))
        rows.append({
            "detector": "D4", "archetype": "A4", "entity": c,
            "direction": "flag",
            "severity": round(min(abs(eq_z), abs(other_z)) * np.sign(eq_z), 2),
            "components": {
                "equity_5d_z": round(eq_z, 2),
                "fx_strength_5d_z": round(fx_z, 2) if not np.isnan(fx_z) else None,
                "y10_chg_5d_z": round(y_z, 2) if not np.isnan(y_z) else None,
                "cds_chg_5d_z": round(cds_z, 2) if not np.isnan(cds_z) else None,
                "cds_level_bp": (round(float(cds_c[c].iloc[-1]), 1)
                                 if c in cds_fresh and len(cds_c[c]) else None),
                "conflict": kind,
                "all_conflicts": [k for k, _ in conflicts] if len(conflicts) > 1 else None,
                "note": "trading-day windows; v2 adds daily 5Y CDS + direct-pull 10Y (sovereign_daily)",
            },
        })
    if fx_stale:
        rows.append(degraded_row("D4", "A4", "Currency", fx_stale,
                                 "FX leg skipped for these countries (stale/missing series)"))
    if y_stale:
        rows.append(degraded_row("D4", "A4", "10Yr Bond", y_stale,
                                 "10Y leg skipped for these countries (stale/missing series)"))
    if cds_stale:
        rows.append(degraded_row("D4", "A4", "CDS_5Y", cds_stale,
                                 "CDS leg skipped for these countries (stale/missing series)"))
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
    """Factor crowding scan over ALL T2 factor return series (live list from
    factor_returns_daily) — no hardcoded whitelist."""
    rows = []

    factors = [r[0] for r in con.execute(
        """SELECT DISTINCT factor FROM asado.factor_returns_daily
           WHERE source = 't2_optimizer_daily' AND value IS NOT NULL
           ORDER BY factor"""
    ).fetchall()]
    if not factors:
        return rows

    # dispersion compression per factor characteristic — single scan, then
    # keep only the D7_MAX_DISPERSION_FLAGS most-compressed factors.
    # (std computed in pandas: DuckDB STDDEV_SAMP overflows on a few series
    # with extreme values.)
    f_ph = ",".join("?" for _ in factors)
    c_ph = ",".join("?" for _ in T2_UNIVERSE)
    vals_df = con.execute(
        f"""SELECT date, variable, value
            FROM asado.t2_factors_daily
            WHERE variable IN ({f_ph}) AND country IN ({c_ph})
              AND value IS NOT NULL AND isfinite(value)""",
        factors + list(T2_UNIVERSE),
    ).fetchdf()
    vals_df["date"] = pd.to_datetime(vals_df["date"])

    flagged = []
    for f, grp in vals_df.groupby("variable"):
        disp = grp.groupby("date")["value"].std().sort_index().dropna()
        if len(disp) < ZMIN:
            continue
        z = zscore_last(disp)
        if np.isnan(z) or z > -1.5:
            continue
        flagged.append((z, f, float(disp.iloc[-1])))
    flagged.sort()  # most negative z first
    for z, f, last_disp in flagged[:D7_MAX_DISPERSION_FLAGS]:
        rows.append({
            "detector": "D7", "archetype": "A7", "entity": f,
            "direction": "flag",
            "severity": round(z, 2),
            "components": {
                "xs_dispersion": round(last_disp, 4),
                "dispersion_z_3y": round(z, 2),
                "reading": "cross-sectional dispersion compressed - factor crowded, de-weight candidate",
            },
        })

    # herding: avg pairwise 63d corr of all T2 factor return series
    fr = con.execute(
        """SELECT date, factor, value FROM asado.factor_returns_daily
           WHERE source = 't2_optimizer_daily' AND value IS NOT NULL"""
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
                "detector": "D7", "archetype": "A7", "entity": "FACTOR_HERDING",
                "direction": "flag",
                "severity": round(z, 2),
                "components": {
                    "avg_pairwise_corr_63d": round(float(cs.iloc[-1]), 3),
                    "corr_z_3y": round(z, 2),
                    "n_factors": int(fp.shape[1]),
                    "reading": "T2 factor return series are moving together - herding/regime stress",
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


def d10_fx_options_vs_equity(con, ret5: pd.DataFrame, ret21: pd.DataFrame,
                             run_date: pd.Timestamp) -> list[dict]:
    """A10 v1 (2026-06-11): FX OPTIONS market vs equity disagreement.

    Inputs are the market-implied stress layer (loop DB, from
    collect_market_implied_bbg.py / load_market_implied.py): 25-delta 1M
    risk reversals (sign-normalized: positive = options premium on
    LOCAL-currency depreciation) and 1M ATM implied vol, with their
    precomputed trailing-252d z's (market_implied_signals).

    Two conflict shapes:
      fx_options_stress_unpriced_by_equity — options market paying up for
        crash protection (RR z >= 2 or implied-vol z >= 2.5) while the
        country's own equity has NOT resolved over 21 trading days
        (|eq21 z| <= 0.75). The options market sees something equities
        haven't priced.
      equity_stress_unconfirmed_by_fx_options — equity selling off hard
        (5d z <= -1.5) while RR and vol z are both quiet (<= 0.5). The
        FX options market does not confirm the equity stress: local-only
        story or potential overreaction.

    Hong Kong / Saudi Arabia are INCLUDED (unlike D4's spot-FX leg): a
    near-zero peg surface waking up is exactly peg/devaluation risk getting
    priced — but rows carry a peg note because z's off a near-zero baseline
    run hot. U.S./NASDAQ/US SmallCap (USD numeraire) and Denmark/Vietnam
    (no liquid surface) are structural skips."""
    rows: list[dict] = []

    def piv(table: str, variable: str) -> pd.DataFrame:
        p = pivot_var(con, table, variable, qualified=False)
        return p[p.index <= run_date]

    try:
        rr_z_p = piv("market_implied_signals", "FX_RR25_Z252")
        iv_z_p = piv("market_implied_signals", "FX_IMPVOL_Z252")
        rr_p = piv("market_implied_daily", "FX_RR25_1M_PCT")
        iv_p = piv("market_implied_daily", "FX_IMPVOL_1M_PCT")
    except Exception as exc:
        return [degraded_row("D10", "A10", "market_implied", {"ALL": str(exc)},
                             "market_implied tables unavailable - run load_market_implied.py")]
    if rr_p.empty:
        return [degraded_row("D10", "A10", "market_implied", {"ALL": "no_rows"},
                             "market_implied_daily empty - run collect_market_implied_bbg.py")]

    stale: dict[str, str] = {}
    for c in T2_UNIVERSE:
        if c in NO_FX_OPTIONS:
            continue
        rr = rr_p[c].dropna() if c in rr_p.columns else pd.Series(dtype=float)
        if rr.empty:
            stale[c] = "no_observations"
            continue
        if (run_date - rr.index[-1]).days > D10_MAX_AGE_D:
            stale[c] = f"last_obs={rr.index[-1].date()}"
            continue

        def last(p: pd.DataFrame) -> float:
            s = p[c].dropna() if c in p.columns else pd.Series(dtype=float)
            return float(s.iloc[-1]) if len(s) else np.nan

        rr_z, iv_z = last(rr_z_p), last(iv_z_p)
        rr_lvl, iv_lvl = last(rr_p), last(iv_p)
        eq5_z = zscore_last(ret5[c]) if c in ret5.columns else np.nan
        eq21_z = zscore_last(ret21[c]) if c in ret21.columns else np.nan

        opt_stress = max(rr_z if not np.isnan(rr_z) else -np.inf,
                         iv_z if not np.isnan(iv_z) else -np.inf)
        conflict = severity = None
        if ((not np.isnan(rr_z) and rr_z >= D10_RR_Z_MIN)
                or (not np.isnan(iv_z) and iv_z >= D10_IV_Z_MIN)) \
                and not np.isnan(eq21_z) and abs(eq21_z) <= D10_EQ_QUIET_MAX:
            conflict = "fx_options_stress_unpriced_by_equity"
            severity = round(float(opt_stress), 2)
        elif (not np.isnan(eq5_z) and eq5_z <= D10_EQ_STRESS_MIN
                and not np.isnan(rr_z) and rr_z <= D10_OPT_QUIET_MAX
                and not np.isnan(iv_z) and iv_z <= D10_OPT_QUIET_MAX):
            conflict = "equity_stress_unconfirmed_by_fx_options"
            severity = round(float(eq5_z), 2)
        if conflict is None:
            continue
        comp = {
            "rr25_1m": round(rr_lvl, 2) if not np.isnan(rr_lvl) else None,
            "rr25_z252": round(rr_z, 2) if not np.isnan(rr_z) else None,
            "impvol_1m_pct": round(iv_lvl, 2) if not np.isnan(iv_lvl) else None,
            "impvol_z252": round(iv_z, 2) if not np.isnan(iv_z) else None,
            "equity_5d_z": round(eq5_z, 2) if not np.isnan(eq5_z) else None,
            "equity_21d_z": round(eq21_z, 2) if not np.isnan(eq21_z) else None,
            "conflict": conflict,
            "note": "+RR = depreciation premium; z's from market_implied_signals (252d, shifted baseline)",
        }
        if c in PEG_FX_OPTIONS:
            comp["peg_note"] = ("pegged currency: surface z's run hot off a near-zero "
                                "baseline - read as peg-risk repricing, not magnitude")
        rows.append({
            "detector": "D10", "archetype": "A10", "entity": c,
            "direction": "flag", "severity": severity, "components": comp,
        })
    if stale:
        rows.append(degraded_row("D10", "A10", "market_implied", stale,
                                 "FX options surface stale/missing for these countries"))
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
            ("D3", lambda: d3_revision_momentum(con, ret_piv, run_date)),
            ("D4", lambda: d4_cross_asset(con, ret5, run_date)),
            ("D5", lambda: d5_attention_no_resolution(con, ret5)),
            ("D7", lambda: d7_factor_crowding(con)),
            ("D8", lambda: d8_stewardship(con, ret21)),
            ("D9", lambda: d9_index_vs_etf(con, ret_piv, run_date)),
            ("D10", lambda: d10_fx_options_vs_equity(con, ret5, ret21, run_date)),
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

        write_brief(con, df, run_date, regime)
        return 0
    finally:
        con.close()


def write_brief(con, df: pd.DataFrame, run_date: pd.Timestamp, regime: str) -> None:
    BRIEF_DIR.mkdir(parents=True, exist_ok=True)
    path = BRIEF_DIR / f"brief_{run_date.strftime('%Y_%m_%d')}.md"
    lines = [
        f"# Dislocation brief — {run_date.date()}",
        "",
        f"- Regime context: **{regime}** (context only; no mechanical overlay — H3 failed)",
        f"- Rows: {len(df)} | detectors live: D1 D2 D3 D4 D5 D7 D8 D9 D10 (D10 FX-options-vs-equity v1 since 2026-06-11) | blocked: D6 (predmkt accumulating since 2026-06-10)",
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
    lines += _calendar_section(con, run_date)
    lines += _market_implied_section(con, run_date)
    lines += _curves_ratings_surprises_section(con, run_date)
    lines += _flows_section(con, run_date)
    lines += _etf_positioning_section(con, run_date)
    lines += _cot_section(con, run_date)
    lines += _jst_tail_context_section(con, run_date)
    path.write_text("\n".join(lines) + "\n")
    log(f"brief: {path}")


def _jst_tail_context_section(con, run_date: pd.Timestamp) -> list[str]:
    """Long-cycle tail context from the JST 1870-2020 calibration (read-only).

    For any in-universe country currently in a >=20% equity drawdown, print the
    JST-calibrated forward-3y real-equity return distribution for that drawdown
    bucket — the once-in-a-century tail the modern (~2000+) sample cannot show.
    Pure context: it does NOT change any detector severity or trade sizing.
    Degrades gracefully if the calibration file or returns panel is absent.
    """
    header = ["", "## Long-cycle tail context (JST 1870-2020, 13 DMs)", ""]
    try:
        from regime.calib import jst_calib
    except Exception as exc:
        return header + [f"UNAVAILABLE ({exc}) — run scripts/calibrate_jst_bearbottom.py"]
    if not jst_calib._tables():
        return header + ["UNAVAILABLE — run scripts/calibrate_jst_bearbottom.py first."]

    try:
        dds = jst_calib.country_drawdowns(returns_panel(con))
    except Exception as exc:
        dds = {}
        note = f" (per-country drawdown unavailable: {exc.__class__.__name__})"
    else:
        note = ""

    deep = sorted(((c, d) for c, d in dds.items() if d <= -0.20), key=lambda x: x[1])
    lines = list(header)
    lines.append("Read: forward-3y **real** equity return distribution conditional on the "
                 "current drawdown bucket, calibrated on 150y of DM crises. Context only — "
                 "no overlay on severity or sizing.")
    lines.append("")
    if deep:
        lines.append("| country | trail. drawdown | JST bucket | fwd3y median | p10 | P(neg) |")
        lines.append("|---|---|---|---|---|---|")
        for c, dd in deep:
            dist = jst_calib.lookup_by_drawdown("equity", dd, horizon=3)
            if not dist:
                continue
            lines.append(
                f"| {c} | {dd:.0%} | {dist['state']} | {dist['median']:.1%} | "
                f"{dist['p10']:.1%} | {dist['prob_neg']:.0%} |"
            )
    else:
        lines.append(f"No in-universe country in a >=20% drawdown today{note}. "
                     "Standing reference — deepest-bucket (dd<=-35%) forward-3y real equity:")
        ref = jst_calib.forward_distribution("equity", "dd_35_plus", 3)
        if ref:
            lines.append(f"  median {ref['median']:.1%}, p10 {ref['p10']:.1%}, "
                         f"P(neg) {ref['prob_neg']:.0%} (n={ref['n_obs']}).")
    return lines


def _calendar_section(con, run_date: pd.Timestamp) -> list[str]:
    """Next-30-day scheduled catalysts from forward_calendar (loop DB).

    Theses need catalysts (PRD Priority 5): the Layer 2 session should see
    what is scheduled before reasoning about dislocations. Missing table is
    reported, not swallowed. Reuses the caller's open loop-DB connection
    (DuckDB forbids a second same-file connection with different config).
    """
    try:
        cal = con.execute(
            """
            SELECT event_date, severity, label, countries_affected, date_confirmed
            FROM forward_calendar
            WHERE event_date BETWEEN CAST(? AS DATE) AND CAST(? AS DATE) + INTERVAL 30 DAY
            ORDER BY event_date, severity
            """,
            [str(run_date.date()), str(run_date.date())],
        ).fetchdf()
    except Exception as exc:
        return ["", "## Forward calendar (next 30 days)", "",
                f"UNAVAILABLE ({exc}) — run scripts/loop/build_forward_calendar.py"]

    lines = ["", "## Forward calendar (next 30 days)", ""]
    if cal.empty:
        lines.append("No scheduled catalysts in the window.")
        return lines
    for r in cal.itertuples():
        scope = r.countries_affected or "global"
        tbc = "" if r.date_confirmed else " *(day not yet confirmed)*"
        d = pd.Timestamp(r.event_date).date()
        lines.append(f"- **{d}** [{r.severity}] {r.label} — {scope}{tbc}")
    return lines


def _flows_section(con, run_date: pd.Timestamp) -> list[str]:
    """Foreign investor flow snapshot from foreign_flows_daily (loop DB).

    Context only, not a detector (yet): latest day plus 5-day and 20-day
    cumulative net equity flow per country, with a z-score of the 5-day sum
    against that country's own 1-year history of 5-day sums. Missing table
    is reported, not swallowed.
    """
    try:
        raw = con.execute(
            """
            SELECT date, country, value FROM foreign_flows_daily
            WHERE variable = 'FOREIGN_EQUITY_NET_USD_MN'
              AND date <= CAST(? AS DATE)
            ORDER BY country, date
            """,
            [str(run_date.date())],
        ).fetchdf()
    except Exception as exc:
        return ["", "## Foreign investor flows (equity, USD mn)", "",
                f"UNAVAILABLE ({exc}) — run scripts/loop/collect_foreign_flows.py"]

    lines = ["", "## Foreign investor flows (equity, USD mn)", ""]
    if raw.empty:
        lines.append("No flow data yet.")
        return lines
    for country, g in raw.groupby("country"):
        g = g.sort_values("date")
        last_date = pd.Timestamp(g["date"].iloc[-1]).date()
        last = g["value"].iloc[-1]
        sum5 = g["value"].tail(5).sum()
        sum20 = g["value"].tail(20).sum()
        roll5 = g["value"].rolling(5).sum().dropna()
        hist = roll5.tail(252)
        z5 = (sum5 - hist.mean()) / hist.std() if len(hist) >= 60 and hist.std() > 0 else None
        z_str = f", 5d z={z5:+.1f}" if z5 is not None else ""
        stale = " *(STALE)*" if (run_date.date() - last_date).days > 5 else ""
        lines.append(
            f"- **{country}** ({last_date}{stale}): last {last:+,.0f} | "
            f"5d {sum5:+,.0f} | 20d {sum20:+,.0f}{z_str}"
        )
    return lines


def _etf_positioning_section(con, run_date: pd.Timestamp) -> list[str]:
    """ETF share-count positioning extremes from etf_flow_signals (loop DB).

    Context only, not a detector (yet — PRD P11 says this unblocks crowding
    detectors). Shows only countries whose 21-day creation/redemption flow is
    stretched (|z| >= 2 vs own trailing year) so the Layer 2 session sees
    crowding without 34 rows of noise. Missing table reported, not swallowed.
    """
    try:
        df = con.execute(
            """
            SELECT country, etf,
              MAX(CASE WHEN variable='ETF_FLOW_21D_Z' THEN value END)        AS z,
              MAX(CASE WHEN variable='ETF_FLOW_21D_USD_MN' THEN value END)   AS flow_mn,
              MAX(CASE WHEN variable='ETF_FLOW_21D_PCT_AUM' THEN value END)  AS pct_aum,
              MAX(date)                                                      AS asof
            FROM etf_flow_signals
            WHERE date = (SELECT MAX(date) FROM etf_flow_signals WHERE date <= CAST(? AS DATE))
            GROUP BY 1, 2
            """,
            [str(run_date.date())],
        ).fetchdf()
    except Exception as exc:
        return ["", "## ETF positioning (21d creations/redemptions)", "",
                f"UNAVAILABLE ({exc}) — run scripts/loop/load_etf_flows.py"]

    lines = ["", "## ETF positioning (21d creations/redemptions)", ""]
    if df.empty:
        lines.append("No ETF flow data yet.")
        return lines
    asof = pd.Timestamp(df["asof"].iloc[0]).date()
    stale = " *(STALE)*" if (run_date.date() - asof).days > 5 else ""
    hot = df[df["z"].abs() >= 2.0].sort_values("z", ascending=False)
    if hot.empty:
        lines.append(f"No stretched positioning (|21d flow z| >= 2) as of {asof}{stale}.")
        return lines
    lines.append(f"As of {asof}{stale} — |21d flow z| >= 2 vs own trailing year:")
    for r in hot.itertuples():
        lines.append(
            f"- **{r.country}** ({r.etf}): z={r.z:+.1f}, 21d {r.flow_mn:+,.0f}mn "
            f"({r.pct_aum:+.1f}% of AUM)"
        )
    # Short interest extremes (semi-monthly; |z| >= 2 vs own ~2y)
    try:
        si = con.execute(
            """
            SELECT country, etf,
              MAX(CASE WHEN variable='ETF_SHORT_PCT_SHOUT' THEN value END) AS si_pct,
              MAX(CASE WHEN variable='ETF_SHORT_PCT_Z' THEN value END)     AS si_z,
              MAX(date)                                                    AS asof
            FROM etf_flow_signals
            WHERE variable LIKE 'ETF_SHORT%'
              AND date = (SELECT MAX(date) FROM etf_flow_signals
                          WHERE variable = 'ETF_SHORT_PCT_Z' AND date <= CAST(? AS DATE))
            GROUP BY 1, 2 HAVING si_z IS NOT NULL AND ABS(si_z) >= 2.0
            ORDER BY si_z DESC
            """,
            [str(run_date.date())],
        ).fetchdf()
        if not si.empty:
            si_asof = pd.Timestamp(si["asof"].iloc[0]).date()
            lines += ["", f"Short interest extremes (FINRA settle {si_asof}, |z| >= 2 vs own ~2y):"]
            for r in si.itertuples():
                lines.append(f"- **{r.country}** ({r.etf}): SI {r.si_pct:.1f}% of shares out, z={r.si_z:+.1f}")
    except Exception as exc:
        lines += ["", f"Short interest UNAVAILABLE ({exc})"]
    return lines


def _market_implied_section(con, run_date: pd.Timestamp) -> list[str]:
    """Market-implied stress snapshot from market_implied_daily/_signals
    (loop DB; Bloomberg FX options, vol/credit dashboard, futures curves).

    Context only, not a detector (yet): a global risk dashboard line plus
    the currencies whose 1M implied vol or 25-delta risk reversal is
    stretched (|252d z| >= 2) and futures curves in unusual shape. RR is
    sign-normalized upstream: positive = options market paying premium for
    LOCAL-currency depreciation. Missing table reported, not swallowed.
    """
    try:
        sig = con.execute(
            """
            SELECT s.country, s.variable, s.value
            FROM market_implied_signals s
            JOIN (SELECT country, variable, MAX(date) AS d
                  FROM market_implied_signals
                  WHERE date <= CAST(? AS DATE)
                  GROUP BY 1, 2) m
              ON s.country = m.country AND s.variable = m.variable AND s.date = m.d
            """,
            [str(run_date.date())],
        ).fetchdf()
        raw = con.execute(
            """
            SELECT r.country, r.variable, r.value, r.date
            FROM market_implied_daily r
            JOIN (SELECT country, variable, MAX(date) AS d
                  FROM market_implied_daily
                  WHERE date <= CAST(? AS DATE)
                  GROUP BY 1, 2) m
              ON r.country = m.country AND r.variable = m.variable AND r.date = m.d
            """,
            [str(run_date.date())],
        ).fetchdf()
    except Exception as exc:
        return ["", "## Market-implied stress (FX options, vol, credit, curves)", "",
                f"UNAVAILABLE ({exc}) — run scripts/loop/load_market_implied.py"]

    lines = ["", "## Market-implied stress (FX options, vol, credit, curves)", ""]
    if sig.empty or raw.empty:
        lines.append("No market-implied data yet.")
        return lines

    sval = {(r.country, r.variable): r.value for r in sig.itertuples()}
    rval = {(r.country, r.variable): r.value for r in raw.itertuples()}
    asof = pd.Timestamp(raw["date"].max()).date()
    stale = " *(STALE)*" if (run_date.date() - asof).days > 5 else ""

    def _num(d, key):
        v = d.get(key)
        return v if v is not None and pd.notna(v) else None

    def _fmt(v, spec):
        return spec.format(v) if v is not None else "n/a"

    def zfmt(var):
        return _fmt(_num(sval, ("GLOBAL", var)), "{:+.1f}")

    vix = _num(rval, ("GLOBAL", "RISK_VIX"))
    term = _num(sval, ("GLOBAL", "RISK_VIX_TERM_RATIO"))
    move = _num(rval, ("GLOBAL", "RISK_MOVE"))
    hy = _num(rval, ("GLOBAL", "RISK_HY_OAS"))
    term_str = (f"{term:.2f}" + (" **INVERTED**" if term < 1 else "")) if term is not None else "n/a"
    lines.append(
        f"Global (as of {asof}{stale}): VIX {_fmt(vix, '{:.1f}')} (z={zfmt('RISK_VIX_Z252')}) | "
        f"VIX3M/VIX {term_str} | MOVE {_fmt(move, '{:.0f}')} (z={zfmt('RISK_MOVE_Z252')}) | "
        f"HY OAS {_fmt(hy, '{:.2f}')}% (z={zfmt('RISK_HY_OAS_Z252')}) | "
        f"DXY z={zfmt('RISK_DXY_Z252')}"
    )

    FX_Z_VARS = ("FX_RR25_Z252", "FX_IMPVOL_Z252", "FX_BF25_Z252",
                 "FX_VOL_TERM_Z252", "FX_CARRY_Z252")
    fx_countries = {c for (c, v), z in sval.items()
                    if v in FX_Z_VARS and pd.notna(z) and abs(z) >= 2.0}
    if fx_countries:
        lines.append("")
        lines.append("Stretched currencies (any |252d z| >= 2; +RR = depreciation "
                     "premium, +term = 1W vol above 3M = stress NOW, BF = tail "
                     "premium, +carry = local rates above USD):")

        def worst_z(c):
            zs = [abs(z) for v in FX_Z_VARS
                  if (z := _num(sval, (c, v))) is not None]
            return max(zs) if zs else 0.0

        for c in sorted(fx_countries, key=lambda c: -worst_z(c)):
            rr, rrz = _num(rval, (c, "FX_RR25_1M_PCT")), _num(sval, (c, "FX_RR25_Z252"))
            iv, ivz = _num(rval, (c, "FX_IMPVOL_1M_PCT")), _num(sval, (c, "FX_IMPVOL_Z252"))
            bfz = _num(sval, (c, "FX_BF25_Z252"))
            tm, tmz = _num(sval, (c, "FX_VOL_TERM_PCT")), _num(sval, (c, "FX_VOL_TERM_Z252"))
            cy, cyz = _num(rval, (c, "FX_CARRY_3M_PCT")), _num(sval, (c, "FX_CARRY_Z252"))
            lines.append(
                f"- **{c}**: RR {_fmt(rr, '{:+.2f}')} (z={_fmt(rrz, '{:+.1f}')}) | "
                f"impvol {_fmt(iv, '{:.1f}')}% (z={_fmt(ivz, '{:+.1f}')}) | "
                f"BF z={_fmt(bfz, '{:+.1f}')} | term {_fmt(tm, '{:+.1f}')} "
                f"(z={_fmt(tmz, '{:+.1f}')}) | carry {_fmt(cy, '{:+.1f}')}% "
                f"(z={_fmt(cyz, '{:+.1f}')})")
    else:
        lines.append("No stretched currency surfaces (|252d z| >= 2).")

    curves = [(v.replace("CMD_", "").replace("_CURVE_Z252", ""), z)
              for (c, v), z in sval.items()
              if c == "GLOBAL" and v.endswith("_CURVE_Z252") and pd.notna(z) and abs(z) >= 2.0]
    if curves:
        lines.append("")
        lines.append("Futures curves in unusual shape (|252d z| >= 2; + = backwardation):")
        names = {"CL": "WTI", "CO": "Brent", "HG": "Copper", "GC": "Gold", "NG": "NatGas"}
        for root, z in sorted(curves, key=lambda x: -abs(x[1])):
            pct = _num(sval, ("GLOBAL", f"CMD_{root}_CURVE_PCT"))
            lines.append(f"- **{names.get(root, root)}**: front/2nd {_fmt(pct, '{:+.1f}')}% (z={z:+.1f})")
    return lines


def _curves_ratings_surprises_section(con, run_date: pd.Timestamp) -> list[str]:
    """Sovereign curve shapes, rating changes, and economic surprises
    (loop DB: sovereign_signals, sov_rating_changes, eco_surprise_signals).

    Context only, not detectors (yet). Three blocks, extremes only:
      1. CDS curve INVERSIONS (1Y > 5Y = imminent-distress pricing) and
         stretched 2s10s moves (|z| >= 2).
      2. Rating changes in the last 90 days (dated, tradeable events).
      3. Latest economic surprise composites with |z| >= 1.5 (data
         beating/missing consensus hard).
    Missing tables reported, not swallowed.
    """
    lines = ["", "## Sovereign curves, ratings & macro surprises", ""]

    # --- 1. curve shapes -----------------------------------------------------
    try:
        cur = con.execute(
            """
            SELECT s.country, s.variable, s.value
            FROM sovereign_signals s
            JOIN (SELECT country, variable, MAX(date) AS d
                  FROM sovereign_signals WHERE date <= CAST(? AS DATE)
                  GROUP BY 1, 2) m
              ON s.country = m.country AND s.variable = m.variable AND s.date = m.d
            """,
            [str(run_date.date())],
        ).fetchdf()
        cval = {(r.country, r.variable): r.value for r in cur.itertuples()}
        inverted = [(c, v) for (c, var), v in cval.items()
                    if var == "SOV_CDS_SLOPE_BP" and pd.notna(v) and v < 0]
        stretched = [(c, cval.get((c, "SOV_2S10S_PCT")), z)
                     for (c, var), z in cval.items()
                     if var == "SOV_2S10S_Z252" and pd.notna(z) and abs(z) >= 2.0]
        if inverted:
            lines.append("CDS curve INVERTED (1Y above 5Y — imminent-distress pricing):")
            for c, v in sorted(inverted, key=lambda x: x[1]):
                lines.append(f"- **{c}**: 5Y-1Y slope {v:+.0f}bp")
        if stretched:
            lines.append("Govt 2s10s stretched (|252d z| >= 2):")
            for c, slope, z in sorted(stretched, key=lambda x: -abs(x[2])):
                s_str = f"{slope:+.2f}" if slope is not None and pd.notna(slope) else "n/a"
                lines.append(f"- **{c}**: 2s10s {s_str}pp (z={z:+.1f})")
        if not inverted and not stretched:
            lines.append("No CDS curve inversions; no stretched 2s10s moves.")
    except Exception as exc:
        lines.append(f"Curve signals UNAVAILABLE ({exc}) — run scripts/loop/load_sovereign_daily.py")

    # --- 2. recent rating changes -------------------------------------------
    try:
        chg = con.execute(
            """
            SELECT date, country, agency, old_score, new_score, delta
            FROM sov_rating_changes
            WHERE date >= CAST(? AS DATE) - INTERVAL 90 DAY
              AND date <= CAST(? AS DATE)
            ORDER BY date DESC, country
            """,
            [str(run_date.date()), str(run_date.date())],
        ).fetchdf()
        lines.append("")
        if chg.empty:
            lines.append("No sovereign rating changes in the last 90 days.")
        else:
            lines.append("Sovereign rating changes (last 90 days, 21-pt scale, higher = better):")
            for r in chg.itertuples():
                arrow = "UPGRADE" if r.delta > 0 else "DOWNGRADE"
                d = pd.Timestamp(r.date).date()
                lines.append(
                    f"- **{r.country}** {arrow} ({r.agency}, {d}): "
                    f"{r.old_score:.0f} -> {r.new_score:.0f} ({r.delta:+.0f} notches)")
    except Exception as exc:
        lines.append(f"Rating changes UNAVAILABLE ({exc}) — run scripts/loop/load_sov_ratings.py")

    # --- 3. economic surprises ------------------------------------------------
    try:
        eco = con.execute(
            """
            SELECT s.country, s.variable, s.value, s.date
            FROM eco_surprise_signals s
            JOIN (SELECT country, variable, MAX(date) AS d
                  FROM eco_surprise_signals WHERE date <= CAST(? AS DATE)
                  GROUP BY 1, 2) m
              ON s.country = m.country AND s.variable = m.variable AND s.date = m.d
            WHERE s.variable IN ('ECO_GROWTH_SURPRISE_Z', 'ECO_INFL_SURPRISE_Z')
              AND s.date >= CAST(? AS DATE) - INTERVAL 75 DAY
            """,
            [str(run_date.date()), str(run_date.date())],
        ).fetchdf()
        hot = eco[eco["value"].abs() >= 1.5]
        lines.append("")
        if hot.empty:
            lines.append("No hot economic surprises (|z| >= 1.5 on latest prints).")
        else:
            lines.append("Hot economic surprises (latest print, |z| >= 1.5; +growth = beat, "
                         "+infl = hotter than consensus):")
            label = {"ECO_GROWTH_SURPRISE_Z": "growth", "ECO_INFL_SURPRISE_Z": "inflation"}
            for r in hot.sort_values("value", key=lambda s: s.abs(), ascending=False).itertuples():
                d = pd.Timestamp(r.date).date()
                lines.append(f"- **{r.country}** {label[r.variable]} surprise z={r.value:+.1f} ({d})")
    except Exception as exc:
        lines.append(f"Surprises UNAVAILABLE ({exc}) — run scripts/loop/load_eco_surprise.py")

    return lines


def _cot_section(con, run_date: pd.Timestamp) -> list[str]:
    """Commodity speculator positioning extremes from cot_signals (loop DB).

    Context for D1: when specs are record-long a commodity, the flow that
    could chase a ToT impulse is already positioned. Shows |z| >= 1.5 only.
    Missing table reported, not swallowed.
    """
    try:
        df = con.execute(
            """
            SELECT commodity, net_pct_oi, net_pct_oi_z52w AS z, date
            FROM cot_signals
            WHERE date = (SELECT MAX(date) FROM cot_signals WHERE date <= CAST(? AS DATE))
            ORDER BY z DESC
            """,
            [str(run_date.date())],
        ).fetchdf()
    except Exception as exc:
        return ["", "## Commodity positioning (CFTC COT, weekly)", "",
                f"UNAVAILABLE ({exc}) — run scripts/loop/collect_cot.py"]

    lines = ["", "## Commodity positioning (CFTC COT, weekly)", ""]
    if df.empty:
        lines.append("No COT data yet.")
        return lines
    asof = pd.Timestamp(df["date"].iloc[0]).date()
    stale = " *(STALE)*" if (run_date.date() - asof).days > 12 else ""
    hot = df[df["z"].abs() >= 1.5]
    if hot.empty:
        lines.append(f"No stretched speculator positioning (|52w z| >= 1.5) as of {asof}{stale}.")
        return lines
    lines.append(f"As of {asof}{stale} — speculator net as % of OI, |52w z| >= 1.5:")
    for r in hot.itertuples():
        lines.append(f"- **{r.commodity}**: net {r.net_pct_oi:+.1f}% of OI, z={r.z:+.1f}")
    return lines


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
