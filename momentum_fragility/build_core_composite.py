#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: build_core_composite.py  (ASADO / momentum_fragility)
=============================================================================

DESCRIPTION:
    Builds the CORE Momentum-Fragility composite (PRD sections 2.1 components
    1-5, 2.4, and 3) for the 34 T2 countries, monthly. This is the
    "no new Bloomberg pull" half of the Momentum Fragility Index: every input
    already exists in the ASADO DuckDB warehouse; we only derive / transform /
    standardize it. Concentration (component 7) and crowding (component 6) are
    NOT built here -- this script runs fully independently and produces the
    2000+ Core composite that the later Gate stage consumes.

    Composite = simple average of five sign-oriented, per-country-expanding
    z-scored components (higher composite => more fragile):

      1. mom_level          reuse t2_master '12-1MTR_CS'  (cross-sectional z)
                            sign +  (more-extended momentum = more reversal-prone)
      2. earn_revision_proxy 1M % change of t2_raw 'BEST EPS'
                            sign - (INVERTED: DECELERATING earnings revisions
                            while price momentum stays hot = weakening
                            fundamental support = fragile; pairs with the
                            de-rating component)
      3. val_level          t2_raw 'Trailing PE'
                            sign + (higher PE = more expensive = more fragile)
      4. val_derating       1M change of t2_raw 'Trailing PE'
                            sign - (INVERTED: FALLING PE / multiple compression
                            while momentum & earnings are still hot is exactly
                            the Bernstein de-rating fragility signal)
      5. factor_corr_stress rolling-6m mean ABSOLUTE correlation of the momentum
                            factor return with value/quality/low-vol factor
                            returns (market-wide, one series broadcast to all
                            countries)
                            sign + (higher factor entanglement / crowding =
                            more systemic factor-unwind risk = fragile)

    STANDARDIZATION (PRD 2.4, hard house rule -- never full-sample):
      Each component enters the composite as a per-country EXPANDING-window
      z-score (min_periods=24) computed on top of its cross-sectional-z ("_CS")
      series, mirroring exactly regime_ew/src/ew_model.expanding_zscore applied
      to the existing t2 "_CS" panel. We build BOTH variants explicitly:
        <comp>_cs  = cross-sectional z across the 34-country panel each month
        <comp>_ts  = expanding per-country z (min 24) of the _cs series
                     (== the sign-oriented value that enters the composite)

    SIGN NOTE (pre-registered, frozen BEFORE any Gate-3 return test to avoid
    p-hacking): the signs above are chosen from a-priori economics, not fitted
    to returns. The two INVERTED components (2 earnings-revision, 4 de-rating)
    are the subtle ones and are documented inline where computed.

    MOMENTUM QUARTILE FLAG (frozen, for the later Gate stage): top quartile of
    '12-1MTR_CS' computed cross-sectionally each month; descending percentile
    rank <= 0.25 => True (the hottest-momentum 25% of countries that month).
    Uses only same-month cross-sectional information (point-in-time safe).

INPUT FILES (all read-only):
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
        - t2_master  : variable '12-1MTR_CS' (momentum), '1MRet','3MRet' returns
        - t2_raw     : variable 'BEST EPS', 'Trailing PE' (raw, un-normalized)
        - factor_returns : market-wide per-factor monthly return series
                           ('12-1MTR_CS','Earnings Yield_CS','Best ROE_CS',
                            '360 Day Vol_CS')
    Reused modules (imported, not reimplemented):
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime/src/data_loader.py
        load_country_returns, build_forward_returns, load_factor_panel
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime/src/utils.py
        T2_COUNTRIES, month_start
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_ew/src/ew_model.py
        expanding_zscore  (per-country expanding z, min_periods=24, ddof=0)

OUTPUT FILES:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/momentum_fragility/results/core_composite.parquet
        Columns:
          date, country,
          mom_level, earn_revision_proxy, val_level, val_derating,
          factor_corr_stress            (the five sign-oriented composite inputs)
          composite_core                (simple average of the five; NaN if <4 present)
          momentum_quartile_flag (bool)
          1MRet, 3MRet                  (raw forward returns, build_forward_returns)
          n_components                  (how many of the 5 were non-null; diagnostic)
          mom_level_cs, earn_revision_proxy_cs, val_level_cs, val_derating_cs,
          factor_corr_stress_cs         (the cross-sectional-z intermediates, diagnostic)

VERSION: 1.0
LAST UPDATED: 2026-07-05
AUTHOR: Arjun Divecha (build: Claude Code)

DEPENDENCIES: duckdb, numpy, pandas   (+ reused regime / regime_ew modules)

USAGE:
    python3 "build_core_composite.py"

NOTES:
    - FAIL IS FAIL: no silent fallbacks. If a required variable/table is
      missing or empty, the script raises rather than fabricating data.
    - Data hygiene (documented, not hidden):
        * BEST EPS % change is unit-invariant per country, but a handful of
          currency-redenomination / zero-crossing months produce absurd
          (>1e10) jumps; we winsorize the % change cross-sectionally each month
          at the 1st/99th percentile before z-scoring.
        * Trailing PE <= 0 (negative / zero earnings) is set to NaN (a PE is
          undefined there), and the level + its 1M change are winsorized
          cross-sectionally at 1/99 each month.
    - Component 5 is MARKET-WIDE (factor_returns has no country dimension), so
      its cross-sectional "_cs" variant is degenerate (identical across
      countries => std 0). We therefore standardize it in the time dimension
      only (expanding z of the single market series) and broadcast it to every
      country as a market-wide stress indicator, exactly as the PRD permits.
=============================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

MODULE_ROOT = Path(__file__).resolve().parent
ASADO_ROOT = MODULE_ROOT.parent
RESULTS_DIR = MODULE_ROOT / "results"
WAREHOUSE = ASADO_ROOT / "Data" / "asado.duckdb"

sys.path.insert(0, str(ASADO_ROOT))

from regime.src.data_loader import (  # noqa: E402
    build_forward_returns,
    load_country_returns,
    load_factor_panel,
)
from regime.src.utils import T2_COUNTRIES, month_start  # noqa: E402
from regime_ew.src.ew_model import expanding_zscore  # noqa: E402

MIN_STD_MONTHS = 24            # PRD 2.4 hard rule
CORR_WINDOW = 6               # PRD component 5: rolling 6-month correlation
WINSOR_LO, WINSOR_HI = 0.01, 0.99

# Factor-correlation-stress: momentum vs value/quality/low-vol factor returns.
# Single clean canonical pick per style (all present in factor_returns, source
# t2_optimizer). Value uses 'Earnings Yield_CS' (a clean value factor return),
# deliberately NOT 'Best PE _CS' -- the PRD flags the Best-PE line as a
# substituted specific-return signal, so we avoid that name even at the
# factor-return level.
MOM_FACTOR = "12-1MTR_CS"
STYLE_FACTORS = {
    "value": "Earnings Yield_CS",
    "quality": "Best ROE_CS",
    "lowvol": "360 Day Vol_CS",
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _connect() -> duckdb.DuckDBPyConnection:
    if not WAREHOUSE.exists():
        raise FileNotFoundError(f"Warehouse not found: {WAREHOUSE}")
    return duckdb.connect(str(WAREHOUSE), read_only=True)


def _monthly_grid_wide(long_df: pd.DataFrame) -> pd.DataFrame:
    """
    Pivot a (date, country, value) long frame to a wide (date x country) frame
    on a *complete* monthly grid so that per-country diff / pct_change never
    silently spans a data gap (a gap becomes NaN, not a spurious multi-month
    change).
    """
    w = long_df.pivot_table(index="date", columns="country", values="value", aggfunc="mean")
    w = w.reindex(columns=[c for c in T2_COUNTRIES if c in w.columns])
    full_idx = pd.date_range(w.index.min(), w.index.max(), freq="MS")
    return w.reindex(full_idx).sort_index()


def _winsor_rows(wide: pd.DataFrame, lo: float = WINSOR_LO, hi: float = WINSOR_HI) -> pd.DataFrame:
    """Cross-sectional winsorization: clip each month (row) to its [lo, hi]
    quantile across the country columns."""
    ql = wide.quantile(lo, axis=1)
    qh = wide.quantile(hi, axis=1)
    return wide.clip(lower=ql, upper=qh, axis=0)


def _cross_sectional_z(wide: pd.DataFrame) -> pd.DataFrame:
    """z-score across countries within each month (row-wise). Point-in-time
    safe: uses only same-month cross-section."""
    mean = wide.mean(axis=1)
    std = wide.std(axis=1, ddof=0).replace(0, np.nan)
    return wide.sub(mean, axis=0).div(std, axis=0)


def _wide_to_long(wide: pd.DataFrame, value_name: str) -> pd.DataFrame:
    out = wide.reset_index().rename(columns={"index": "date"})
    out = out.melt(id_vars="date", var_name="country", value_name=value_name)
    return out


# --------------------------------------------------------------------------- #
# Component builders (each returns a long frame: date, country, <cs>, <ts>)
# --------------------------------------------------------------------------- #
def build_momentum(con) -> pd.DataFrame:
    """Component 1. Reuse '12-1MTR_CS' (already cross-sectional z). Sign +."""
    panel = load_factor_panel()  # no-arg reuse: returns cached full panel, no side effects
    mom = panel[panel["factor"] == MOM_FACTOR][["date", "country", "value"]].copy()
    if mom.empty:
        raise RuntimeError(f"'{MOM_FACTOR}' not found in factor panel")
    mom["date"] = month_start(mom["date"])
    mom = mom[mom["country"].isin(T2_COUNTRIES)]
    cs_wide = _monthly_grid_wide(mom)                 # already a _CS series
    ts_wide = expanding_zscore(cs_wide, MIN_STD_MONTHS)
    out = _wide_to_long(cs_wide, "mom_level_cs").merge(
        _wide_to_long(ts_wide, "mom_level"), on=["date", "country"]
    )
    return out  # sign +: mom_level = ts


def build_earnings_revision(con) -> pd.DataFrame:
    """Component 2. 1M % change of raw BEST EPS. Sign - (INVERTED).

    Reasoning (frozen, a-priori): among hot-momentum countries, fragility is
    the *weakening of fundamental support* -- i.e. earnings revisions
    DECELERATING / turning down while price momentum is still elevated. So a
    LOW / negative revision maps to HIGH fragility => invert the z-score. This
    is chosen on economics (complements the de-rating component, and adds
    fundamental-deterioration info orthogonal to the froth already captured by
    val_level), NOT to make the return test pass.
    """
    raw = con.execute(
        "SELECT date, country, value FROM t2_raw WHERE variable = 'BEST EPS'"
    ).fetchdf()
    if raw.empty:
        raise RuntimeError("t2_raw 'BEST EPS' is empty")
    raw["date"] = month_start(raw["date"])
    raw = raw[raw["country"].isin(T2_COUNTRIES)]
    lvl = _monthly_grid_wide(raw)
    # % change is unit-invariant per country (cancels currency scale); gaps -> NaN.
    pct = lvl.pct_change(1)
    pct = pct.replace([np.inf, -np.inf], np.nan)
    pct = _winsor_rows(pct)                            # tame redenomination / zero-cross blowups
    cs_wide = _cross_sectional_z(pct)
    ts_wide = expanding_zscore(cs_wide, MIN_STD_MONTHS)
    out = _wide_to_long(cs_wide, "earn_revision_proxy_cs").merge(
        _wide_to_long(-ts_wide, "earn_revision_proxy"), on=["date", "country"]
    )
    # keep the _cs sign natural (rising revision positive); only the composite
    # input (ts) is inverted so higher = more fragile.
    return out


def build_valuation(con) -> pd.DataFrame:
    """Components 3 & 4 from the same cleaned Trailing PE level.

    3 val_level : sign + (higher PE = more expensive = more fragile).
    4 val_derating : 1M change in PE, sign - (INVERTED). Falling PE (multiple
      compression / de-rating) while momentum & earnings are still hot is the
      Bernstein fragility signal, so a NEGATIVE dPE maps to HIGH fragility =>
      invert.
    """
    raw = con.execute(
        "SELECT date, country, value FROM t2_raw WHERE variable = 'Trailing PE'"
    ).fetchdf()
    if raw.empty:
        raise RuntimeError("t2_raw 'Trailing PE' is empty")
    raw["date"] = month_start(raw["date"])
    raw = raw[raw["country"].isin(T2_COUNTRIES)]
    lvl = _monthly_grid_wide(raw)
    lvl = lvl.where(lvl > 0)                           # PE<=0 (neg/zero earnings) undefined -> NaN

    # ---- component 3: valuation level (sign +) ----
    lvl_w = _winsor_rows(lvl)
    val_cs = _cross_sectional_z(lvl_w)
    val_ts = expanding_zscore(val_cs, MIN_STD_MONTHS)  # sign +
    val = _wide_to_long(val_cs, "val_level_cs").merge(
        _wide_to_long(val_ts, "val_level"), on=["date", "country"]
    )

    # ---- component 4: valuation de-rating (sign -) ----
    dpe = lvl.diff(1)                                  # change of cleaned (nonpos->NaN) level
    dpe = _winsor_rows(dpe)
    der_cs = _cross_sectional_z(dpe)
    der_ts = expanding_zscore(der_cs, MIN_STD_MONTHS)
    der = _wide_to_long(der_cs, "val_derating_cs").merge(
        _wide_to_long(-der_ts, "val_derating"), on=["date", "country"]  # INVERTED
    )
    return val.merge(der, on=["date", "country"])


def build_factor_corr_stress(con) -> pd.DataFrame:
    """Component 5. Market-wide rolling-6m mean |corr| of the momentum factor
    return with value/quality/low-vol factor returns. Sign +.

    factor_returns has NO country dimension -> this is a single market series
    broadcast to all 34 countries (a market-wide crowding / factor-entanglement
    stress indicator, as the PRD permits). Its cross-sectional '_cs' variant is
    therefore degenerate (identical across countries => std 0 => NaN); we
    standardize in time only (expanding z of the single series).

    We use mean ABSOLUTE correlation because momentum's signed correlation with
    the styles is mixed (positive with quality, negative with value); |corr|
    measures how *entangled* momentum has become with the other factors, which
    is the crowding notion. Higher entanglement = more fragile => sign +.
    """
    names = [MOM_FACTOR, *STYLE_FACTORS.values()]
    ph = ",".join(f"'{n}'" for n in names)
    fr = con.execute(
        f"SELECT date, factor, value FROM factor_returns WHERE factor IN ({ph})"
    ).fetchdf()
    missing = set(names) - set(fr["factor"].unique())
    if missing:
        raise RuntimeError(f"factor_returns missing required factors: {missing}")
    fr["date"] = month_start(fr["date"])
    w = fr.pivot_table(index="date", columns="factor", values="value").sort_index()
    w = w.reindex(pd.date_range(w.index.min(), w.index.max(), freq="MS"))

    abs_corrs = []
    for style_factor in STYLE_FACTORS.values():
        c = w[MOM_FACTOR].rolling(CORR_WINDOW, min_periods=CORR_WINDOW).corr(w[style_factor])
        abs_corrs.append(c.abs())
    stress_raw = pd.concat(abs_corrs, axis=1).mean(axis=1)   # market-wide series
    stress_raw.name = "stress"

    # time-only expanding z (single-column frame). _cs is degenerate -> NaN.
    ts = expanding_zscore(stress_raw.to_frame(), MIN_STD_MONTHS)["stress"]

    # broadcast to every country
    countries = [c for c in T2_COUNTRIES]
    rows = []
    for dt in stress_raw.index:
        for c in countries:
            rows.append(
                {
                    "date": dt,
                    "country": c,
                    "factor_corr_stress_cs": np.nan,      # degenerate by construction
                    "factor_corr_stress": ts.loc[dt],     # sign + ; market-wide value
                }
            )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Momentum quartile flag + forward returns
# --------------------------------------------------------------------------- #
def add_momentum_quartile_flag(con) -> pd.DataFrame:
    """Top-quartile of raw '12-1MTR_CS' cross-sectionally each month.
    Descending percentile rank <= 0.25 => hottest 25% => True. Frozen."""
    panel = load_factor_panel()
    mom = panel[panel["factor"] == MOM_FACTOR][["date", "country", "value"]].copy()
    mom["date"] = month_start(mom["date"])
    mom = mom[mom["country"].isin(T2_COUNTRIES)].dropna(subset=["value"])
    # ascending=False => hottest momentum gets the smallest pct rank
    mom["rank_pct"] = mom.groupby("date")["value"].rank(ascending=False, pct=True)
    mom["momentum_quartile_flag"] = mom["rank_pct"] <= 0.25
    return mom[["date", "country", "momentum_quartile_flag"]]


def load_forward_returns(horizons=("1MRet", "3MRet")) -> pd.DataFrame:
    returns = load_country_returns(horizons)
    returns["date"] = month_start(returns["date"])
    out = None
    for h in horizons:
        fr = build_forward_returns(returns, h).rename(columns={"fwd_ret": h})
        out = fr if out is None else out.merge(fr, on=["date", "country"], how="outer")
    return out


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    con = _connect()
    try:
        print("Building components ...")
        mom = build_momentum(con)
        earn = build_earnings_revision(con)
        val = build_valuation(con)          # val_level + val_derating
        corr = build_factor_corr_stress(con)
        flag = add_momentum_quartile_flag(con)
        fwd = load_forward_returns()
    finally:
        con.close()

    # merge all components on (date, country)
    panel = mom
    for part in (earn, val, corr):
        panel = panel.merge(part, on=["date", "country"], how="outer")
    panel = panel.merge(flag, on=["date", "country"], how="left")
    panel = panel.merge(fwd, on=["date", "country"], how="left")
    panel["momentum_quartile_flag"] = (
        panel["momentum_quartile_flag"].astype("boolean").fillna(False).astype(bool)
    )

    comp_cols = [
        "mom_level",
        "earn_revision_proxy",
        "val_level",
        "val_derating",
        "factor_corr_stress",
    ]
    panel["n_components"] = panel[comp_cols].notna().sum(axis=1)
    # simple average; require >= 4 of 5 present, else undefined
    panel["composite_core"] = panel[comp_cols].mean(axis=1)
    panel.loc[panel["n_components"] < 4, "composite_core"] = np.nan

    ordered = [
        "date", "country",
        *comp_cols,
        "composite_core", "momentum_quartile_flag",
        "1MRet", "3MRet",
        "n_components",
        "mom_level_cs", "earn_revision_proxy_cs", "val_level_cs",
        "val_derating_cs", "factor_corr_stress_cs",
    ]
    panel = panel[[c for c in ordered if c in panel.columns]].sort_values(["country", "date"])
    panel = panel.reset_index(drop=True)

    out_path = RESULTS_DIR / "core_composite.parquet"
    panel.to_parquet(out_path, index=False)

    _sanity_report(panel, comp_cols, out_path)


def _sanity_report(panel: pd.DataFrame, comp_cols, out_path: Path) -> None:
    print("\n" + "=" * 70)
    print("CORE COMPOSITE  --  SANITY REPORT")
    print("=" * 70)
    print(f"rows={len(panel):,}  countries={panel['country'].nunique()}  "
          f"months={panel['date'].nunique()}  "
          f"date range {panel['date'].min().date()} .. {panel['date'].max().date()}")

    print("\nPer-component coverage (% non-null of all country-months):")
    for c in comp_cols:
        print(f"  {c:22s} {panel[c].notna().mean()*100:6.1f}%   "
              f"mean={panel[c].mean():+.3f} std={panel[c].std():.3f}")

    cc = panel["composite_core"].dropna()
    print(f"\ncomposite_core: n={len(cc):,} ({panel['composite_core'].notna().mean()*100:.1f}% non-null)")
    print(f"  mean={cc.mean():+.4f} std={cc.std():.4f} "
          f"min={cc.min():+.3f} max={cc.max():+.3f}")
    print("  n_components distribution:")
    print(panel["n_components"].value_counts().sort_index().to_string())

    # momentum quartile flag ~25% each month by construction
    per_month = panel.groupby("date")["momentum_quartile_flag"].mean()
    print(f"\nmomentum_quartile_flag: overall True share = "
          f"{panel['momentum_quartile_flag'].mean()*100:.1f}%")
    print(f"  per-month True share: mean={per_month.mean()*100:.1f}% "
          f"min={per_month.min()*100:.1f}% max={per_month.max()*100:.1f}%")

    # forward-return coverage
    for h in ("1MRet", "3MRet"):
        if h in panel.columns:
            print(f"  {h} non-null: {panel[h].notna().mean()*100:.1f}%")

    # spot check: Taiwan / Korea recent high-momentum months
    print("\nSpot-check: Taiwan / Korea, hot-momentum months since 2023 "
          "(top decile of their composite_core):")
    for ctry in ("Taiwan", "Korea"):
        g = panel[(panel["country"] == ctry) & (panel["date"] >= "2023-01-01")].dropna(
            subset=["composite_core"]
        )
        if g.empty:
            print(f"  {ctry}: no composite in window")
            continue
        hot = g[g["momentum_quartile_flag"]].sort_values("composite_core", ascending=False).head(3)
        show = hot if not hot.empty else g.sort_values("composite_core", ascending=False).head(3)
        for _, r in show.iterrows():
            print(f"  {ctry} {r['date'].date()}  composite={r['composite_core']:+.2f}  "
                  f"mom={r['mom_level']:+.2f} val={r['val_level']:+.2f} "
                  f"derate={r['val_derating']:+.2f} earn={r['earn_revision_proxy']:+.2f} "
                  f"corr={r['factor_corr_stress']:+.2f}  "
                  f"hotMom={bool(r['momentum_quartile_flag'])}  1MRet={r['1MRet']}")

    print(f"\nWrote: {out_path}")
    print(f"file://{str(out_path).replace(' ', '%20')}")


if __name__ == "__main__":
    main()
