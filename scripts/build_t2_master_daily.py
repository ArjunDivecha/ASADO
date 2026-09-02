#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/build_t2_master_daily.py
=============================================================================

DESCRIPTION:
    DAILY analog of build_t2_master.py — the ASADO-internal port of the
    reference "Step One Create T2 Master.py" in
    /Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy Daily.

    Reads the ASADO-generated daily Bloomberg workbook (Bloomberg-direct, no
    hand-maintained Excel) and reproduces the reference daily "T2 Master.xlsx":
    cleans each sheet (winsorize 5-MAD -> EWM 4-sigma local outlier adjust),
    then computes DAILY-horizon forward returns [1,5,20,60,120], trailing
    returns [1,5,20,120], the 120-5DTR spread, 120/252-day change variables,
    the 120MA signal, and merges the daily P2P scores.

    Everything mirrors the monthly build_t2_master.py except the metronome:
    1DRet/5DRet/... instead of 1MRet/3MRet/..., and the daily reference's extra
    data-quality cleaning (winsorize + EWM outlier adjust).

    COMMODITY SEMANTIC BREAK, 2026-08-21 -- read this before comparing any
    output to an earlier daily master or applying an older verdict:
      Gold, Copper, Oil, Agriculture
          WAS  the raw commodity price, broadcast identically to all 34 countries
          NOW  each country's beta to that commodity
      Gold 120, Copper 120, Oil 120, Agriculture 120
          WAS  the 120-period change in the commodity price (identical per country)
          NOW  that country's beta x the commodity's 120-period return
    The 120-period HORIZON is unchanged; only the country dimension is new. The
    old form had ZERO cross-sectional dispersion, so Gold_CS / Copper_CS /
    Oil_CS / Agriculture_CS were 0/0 and carried no information. Any loop-DB
    verdict or graveyard entry on those eight names, or their _CS / _TS
    derivatives, was earned under the OLD semantics and does not transfer.

    The beta is computed on MONTH-END resampled returns using the identical
    rolling(120, min_periods=36) window as the monthly builder, then stamped
    effective the day after each month-end and forward-filled onto the daily
    grid -- point-in-time by construction, and one definition of "commodity
    beta" across both cadences (measured parity vs the monthly builder:
    rank-corr +0.997 to +0.9995).

INPUT FILES:
    - /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/t2/
        T2 Bloomberg Master Daily.xlsx   (ASADO-generated, collect_t2_bloomberg.py --daily)
    - P2P daily scores workbook (--p2p; default: the reference daily P2P file
        until Step Zero daily is internalized)

OUTPUT FILES:
    - /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/t2_daily/
        T2 Master Daily.xlsx

VERSION: 1.1
LAST UPDATED: 2026-06-10
AUTHOR: Arjun Divecha (ported by Claude Code)

DEPENDENCIES:
    - pandas, numpy, scipy, openpyxl

USAGE:
    python scripts/build_t2_master_daily.py
    python scripts/build_t2_master_daily.py --bloomberg PATH --p2p PATH --out PATH

NOTES:
    - v1.1 (2026-06-10) WINSORIZE FIX: the reference used a FULL-SAMPLE
      median +/- 5*MAD clip. On trending level series (SPX, CCMP, Korea,
      Taiwan, TRY currency...) the entire recent history gets clipped to a
      constant ceiling — e.g. SPX was frozen at exactly 5331.89 (its
      full-sample median+5*MAD) from 2025-04-23 onward, Turkey's currency
      frozen since 2020-04. This was the root cause of the t2_levels_daily
      staleness that blocked detector D4. The clip is now a TRAILING ROLLING
      winsorize (252d rolling median +/- 5 * rolling MAD, min_periods=60):
      it still kills data-error spikes but adapts to trends, and is
      backward-looking (the full-sample median was also a lookahead).
      The 8 live optimizer factors are unaffected (their inputs — TRI
      returns, PX/120MA ratio — are loaded with clean=False or are bounded).
    - EWM outlier adjust unchanged: span=20, adjust=False, min_periods=10,
      4-sigma, replacing outliers with the EWM mean (not clip).
    - Returns are computed from the 'Tot Return Index ' sheet (trailing space).
    - Estimate sheets (Best/Trailing EPS, etc.) will differ from the canonical in
      recent dates by consensus revisions — inherent, not a bug.
=============================================================================
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
T2_DAILY_DIR = BASE_DIR / "Data" / "work" / "t2_daily"
DEFAULT_BLOOMBERG = BASE_DIR / "Data" / "work" / "t2" / "T2 Bloomberg Master Daily.xlsx"
DEFAULT_P2P = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Complete/"
                   "T2 Factor Timing Fuzzy Daily/P2P_Country_Historical_Scores.xlsx")
DEFAULT_OUT = T2_DAILY_DIR / "T2 Master Daily.xlsx"

# Exact 35-element country list (index 0 = date column 'Country'), from the reference.
COUNTRY_NAMES = [
    'Country', 'Singapore', 'Australia', 'Canada', 'Germany', 'Japan', 'Switzerland',
    'U.K.', 'NASDAQ', 'U.S.', 'France', 'Netherlands', 'Sweden', 'Italy', 'ChinaA',
    'Chile', 'Indonesia', 'Philippines', 'Poland', 'US SmallCap', 'Malaysia', 'Taiwan',
    'Mexico', 'Korea', 'Brazil', 'South Africa', 'Denmark', 'India', 'ChinaH', 'Hong Kong',
    'Thailand', 'Turkey', 'Spain', 'Vietnam', 'Saudi Arabia',
]

FORWARD_PERIODS = [1, 5, 20, 60, 120]
TRAILING_PERIODS = [1, 5, 20, 120]
CHANGE_CALCS = {   # name -> (days, is_absolute)
    # Gold/Copper/Oil/Agriculture are NOT here any more -- they are written as
    # betas (see commodity_betas_daily). Leaving them would also collide on the
    # "Gold 120" etc. sheet names, and the final cleaned-sheets loop swallows
    # collisions in a try/except, so it would fail SILENTLY rather than loudly.
    "Currency": (120, False),
    "10Yr Bond": (120, True), "Best EPS": (252, False), "Trailing EPS": (252, False),
}

# ── Commodity betas (daily lane) ─────────────────────────────────────────────
# The daily workbook broadcasts ONE commodity price across all 34 country
# columns, so cross-sectional dispersion is exactly zero and Gold_CS /
# Copper_CS / Oil_CS / Agriculture_CS are 0/0 -- the same degeneracy fixed on
# the monthly side in build_t2_master.py v1.2.
#
# The beta is deliberately NOT estimated from daily returns. Two reasons:
#   * this workbook is a CALENDAR-day grid (9,730 rows over 26.6 years =
#     ~366/yr), so a "2520-row" window would be ~6.9 years, not 10;
#   * daily betas of Asian markets against commodity closes are mechanically
#     attenuated by non-synchronous trading.
# Instead the series are resampled to month-end and run through the IDENTICAL
# rolling(120, min_periods=36) monthly beta the monthly builder uses, then
# forward-filled onto the daily grid. One definition of "commodity beta"
# across both cadences.
COMMODITY_SHEETS = ("Gold", "Copper", "Oil", "Agriculture")
BETA_WINDOW_M = 120        # months, matches build_t2_master.BETA_WINDOW
BETA_MIN_PERIODS_M = 36    # months, matches build_t2_master.BETA_MIN_PERIODS
COMMODITY_CHANGE_DAYS = 120  # horizon of the " 120" sheets, unchanged


# ── cleaning helpers (faithful to reference Step One) ─────────────────────────
def ensure_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Regex-clean object columns then coerce to float64 (reference _ensure_numeric)."""
    for col in df.columns:
        if col == "Country":
            continue
        s = df[col]
        if s.dtype == object:
            s = (s.astype(str)
                 .str.replace(" ", "", regex=False)
                 .str.replace("−", "-", regex=False)
                 .str.replace(",", "", regex=False)
                 .str.replace("%", "", regex=False)
                 .str.replace(r"^\((.*)\)$", r"-\1", regex=True)
                 .str.replace("nan", "", regex=False).str.replace("NaN", "", regex=False)
                 .str.replace("#N/A", "", regex=False).str.replace("#VALUE!", "", regex=False)
                 .str.replace("#NAME?", "", regex=False)
                 .str.strip().replace("", np.nan))
            num = pd.to_numeric(s, errors="coerce")
            if num.notna().sum() == 0 and s.notna().sum() > 0:
                num = pd.to_numeric(s.astype(str).str.replace(r"[^0-9eE\+\-\.]+", "", regex=True)
                                    .replace("", np.nan), errors="coerce")
            df[col] = num.astype("float64")
        else:
            df[col] = pd.to_numeric(s, errors="coerce").astype("float64")
    return df


def winsorize_series(s: pd.Series, mad_threshold: float = 5.0,
                     window: int = 252, min_periods: int = 60) -> pd.Series:
    """Trailing rolling winsorize: clip each value at its own trailing
    252-day rolling median +/- 5 * rolling MAD (normal-scaled).

    v1.1: replaces the reference's FULL-SAMPLE clip, which froze trending
    level series at a constant ceiling (SPX stuck at 5331.89 from 2025-04,
    TRY currency stuck since 2020-04) and was a lookahead besides. The
    rolling version adapts to trends while still killing one-off data-error
    spikes; values before min_periods of history are left unclipped.
    """
    x = s.astype(float)
    med = x.rolling(window, min_periods=min_periods).median()
    # normal-scaled MAD (x1.4826), same convention as scipy's scale="normal"
    mad = (x - med).abs().rolling(window, min_periods=min_periods).median() * 1.4826
    lo = med - mad_threshold * mad
    hi = med + mad_threshold * mad
    # where the rolling stats are undefined (warm-up) or degenerate (mad==0),
    # pass the value through unclipped — never freeze a series
    ok = mad.notna() & (mad > 0)
    clipped = x.clip(lower=lo, upper=hi)
    return clipped.where(ok, x)


def adjust_local_outliers_ewm(s: pd.Series, span: int = 20, sigma: float = 4.0) -> pd.Series:
    ewm_mean = s.ewm(span=span, adjust=False, min_periods=10).mean()
    ewm_std = s.ewm(span=span, adjust=False, min_periods=10).std()
    safe = ewm_std.where(ewm_std > 1e-12)
    z = (s - ewm_mean) / safe
    out = s.copy()
    mask = z.abs() > sigma
    out[mask] = ewm_mean[mask]
    return out


def standardize_date(df: pd.DataFrame) -> pd.DataFrame:
    try:
        df["Country"] = pd.to_datetime(df["Country"], errors="raise").dt.normalize()
    except Exception as e:
        logger.warning("date standardize failed: %s", e)
    return df


def assert_tri_has_data(tri: pd.DataFrame, sheet: str, source: Path) -> None:
    """FAIL IS FAIL: refuse to build returns from an empty Total Return Index.

    Every *DRet / *DTR column is derived from this one sheet, and clean_excel()
    fills NaN with 0. So an all-NaN TRI does not surface as missing data — it
    silently becomes a wall of 0.0 returns that looks like a legitimate series
    of flat days. Downstream that is indistinguishable from real data until it
    detonates far away: on 2026-08-11 a Bloomberg pull returned NaN for all 34
    tickers across the entire 1999-2026 history, the zeros propagated into
    t2_factors_daily, the optimizer dropped every factor whose net return summed
    to zero, and asado-daily died with a bare KeyError: 'Date' while
    asado-loop-daily lost nine steps to an empty returns panel. Nothing in the
    logs named the real cause. Hence this guard, at the point of entry.
    """
    values = tri.drop(columns=["Country"], errors="ignore")
    values = values.select_dtypes("number")
    populated = int(values.notna().sum().sum()) if not values.empty else 0
    if populated == 0:
        raise ValueError(
            f"Total Return Index sheet {sheet!r} in {source} contains no numeric "
            f"data ({len(tri)} rows, {values.shape[1]} country columns, 0 populated "
            "cells). Every return variable derives from this sheet, so building "
            "would emit all-zero returns rather than fail. Refusing. This is "
            "almost always an upstream Bloomberg problem (an empty "
            "tot_return_index_gross_dvds pull, or a quota hard stop) — re-pull "
            "before rebuilding; do NOT clean or hand-fill this sheet."
        )
    coverage = populated / max(values.size, 1)
    logger.info("TRI %r: %d/%d cells populated (%.1f%%) across %d countries",
                sheet, populated, values.size, 100 * coverage, values.shape[1])
    if coverage < 0.5:
        logger.warning(
            "TRI coverage is only %.1f%% — returns built from this will be "
            "mostly zeros after NaN-fill. Check the Bloomberg pull before "
            "trusting today's factors.", 100 * coverage)


def clean_excel(df: pd.DataFrame) -> pd.DataFrame:
    df = df.replace([np.inf, -np.inf], np.nan)
    filled = 0
    for col in df.columns:
        if col != "Country" and pd.api.types.is_numeric_dtype(df[col]):
            filled += int(df[col].isna().sum())
            df[col] = df[col].fillna(0).round(6)
    if filled:
        # No silent imputation: these zeros are manufactured, not observed.
        logger.info("clean_excel: filled %d missing numeric cells with 0", filled)
    if len(df) > 50000:
        df = df.iloc[-50000:].reset_index(drop=True)
    return df


def load_sheet(xl: pd.ExcelFile, sheet: str, clean: bool = True) -> pd.DataFrame:
    df = pd.read_excel(xl, sheet_name=sheet, header=None)
    # 2026-09-02: a healthy upstream sheet carries ~9,700 rows of history. A
    # near-empty one means the collector wrote during a Bloomberg outage —
    # abort before the emptiness propagates into "T2 Master Daily.xlsx".
    if len(df) < 1000:
        raise SystemExit(
            f"FATAL: upstream sheet {sheet!r} has only {len(df)} rows "
            f"(expected ~9,700) — refusing to build the T2 master from a "
            f"gutted Bloomberg workbook.")
    df = df.iloc[2:].reset_index(drop=True)
    if "Mcap Adj" in sheet or "MCAP Adj" in sheet:
        df = df.iloc[:400]
    df.columns = (COUNTRY_NAMES[: len(df.columns)]
                  + [f"Unknown_{i}" for i in range(len(df.columns) - len(COUNTRY_NAMES))])[: len(df.columns)]
    df = standardize_date(df)
    df.iloc[:, 1:] = df.iloc[:, 1:].ffill()
    df = ensure_numeric(df)
    if clean and "Mcap" not in sheet:
        for col in df.columns[1:]:
            df[col] = adjust_local_outliers_ewm(winsorize_series(df[col]))
    return df


def clean_excel_keep_na(df: pd.DataFrame) -> pd.DataFrame:
    """clean_excel WITHOUT the fillna(0). For the beta sheets only.

    clean_excel fills every missing numeric cell with 0. For a beta that is a
    FABRICATED CLAIM -- "this country has no exposure to gold" -- not a gap,
    and it would apply to the whole 36-month estimation burn-in at the head of
    the panel. NaN is the honest value there; t2_normalize_daily handles it.

    The global fillna(0) is left alone deliberately: Arjun reverted the
    code-level fill adjustments in the daily lane on 2026-08-10 in favour of
    handling it at the Bloomberg pull. This variant is scoped to 8 sheets.
    """
    df = df.replace([np.inf, -np.inf], np.nan)
    n_na = 0
    for col in df.columns:
        if col != "Country" and pd.api.types.is_numeric_dtype(df[col]):
            n_na += int(df[col].isna().sum())
            df[col] = df[col].round(6)
    if n_na:
        logger.info("clean_excel_keep_na: %d cells left as NaN (beta burn-in, NOT zeroed)", n_na)
    if len(df) > 50000:
        df = df.iloc[-50000:].reset_index(drop=True)
    return df


def _month_end_last_valid(s: pd.Series) -> pd.Series:
    """Last VALID observation of each calendar month (never a NaN month-end)."""
    return s.resample("ME").apply(
        lambda g: g.dropna().iloc[-1] if g.notna().any() else np.nan)


def commodity_betas_daily(com: pd.DataFrame, tri: pd.DataFrame, label: str = "") -> pd.DataFrame:
    """Country betas to a commodity, computed monthly, stamped onto the daily grid.

    POINT-IN-TIME: the beta whose window ends at month-end M is only knowable
    AFTER M, so it is stamped effective M + 1 day and forward-filled. A daily
    date d therefore always carries a beta estimated from data ending strictly
    BEFORE d. (The documented T2 ElasticNet PIT incident was exactly a one-month
    stamp error and fabricated +5.1%/yr, so this is stamped by construction and
    spot-checked, not assumed.)
    """
    num = com.iloc[:, 1:].apply(pd.to_numeric, errors="coerce")
    spread = num.std(axis=1).max()
    scale = float(np.nanmedian(np.abs(num.to_numpy())))
    if pd.notna(spread) and scale > 0 and (spread / scale) > 1e-9:
        raise ValueError(
            f"Daily commodity sheet '{label}' is NOT broadcast across countries "
            f"(max cross-sectional std {spread:.6g} vs level {scale:.6g}). "
            "commodity_betas_daily assumes a single shared price series.")

    daily_idx = pd.to_datetime(com["Country"])
    com_px = pd.to_numeric(com.iloc[:, 1], errors="coerce").set_axis(daily_idx)
    com_m = _month_end_last_valid(com_px)
    com_m_ret = com_m.pct_change()

    tri_idx = pd.to_datetime(tri["Country"])
    betas_daily = pd.DataFrame({"Country": daily_idx.values})
    n_fill = 0
    monthly_betas = {}
    for col in tri.columns[1:]:
        c_m = _month_end_last_valid(
            pd.to_numeric(tri[col], errors="coerce").set_axis(tri_idx))
        c_m_ret = c_m.pct_change()
        cov = c_m_ret.rolling(BETA_WINDOW_M, min_periods=BETA_MIN_PERIODS_M).cov(com_m_ret)
        var = com_m_ret.rolling(BETA_WINDOW_M, min_periods=BETA_MIN_PERIODS_M).var()
        monthly_betas[col] = cov / var

    mb = pd.DataFrame(monthly_betas)
    # Contemporaneous cross-sectional mean for late-inception countries. Same
    # date only -- no look-ahead. Logged, not silent.
    xs_mean = mb.mean(axis=1)
    fillable = mb.isna() & xs_mean.notna().values[:, None]
    n_fill = int(fillable.sum().sum())
    if n_fill:
        mb = mb.apply(lambda c: c.fillna(xs_mean))
        worst = fillable.sum()
        worst = worst[worst > 0].sort_values(ascending=False)
        logger.info("  %s betas: filled %d monthly cells with the contemporaneous "
                    "cross-sectional mean (late inception). Most affected: %s",
                    label, n_fill, ", ".join(f"{k} {v}" for k, v in worst.head(5).items()))

    # PIT stamp: month-end M -> effective M + 1 day, then ffill onto the grid.
    mb.index = mb.index + pd.Timedelta(days=1)
    aligned = mb.reindex(pd.DatetimeIndex(daily_idx), method="ffill")
    for col in aligned.columns:
        betas_daily[col] = aligned[col].to_numpy()

    n_na = int(betas_daily.iloc[:, 1:].isna().sum().sum())
    logger.info("  %s betas: %d daily cells NaN (pre-burn-in, kept as NaN)", label, n_na)
    return betas_daily


def forward_returns(tri: pd.DataFrame, days: int) -> pd.DataFrame:
    out = pd.DataFrame({"Country": tri["Country"]})
    for col in tri.columns[1:]:
        out[col] = tri[col].shift(-days) / tri[col] - 1.0
    return out


def trailing_returns(tri: pd.DataFrame, days: int) -> pd.DataFrame:
    out = pd.DataFrame({"Country": tri["Country"]})
    for col in tri.columns[1:]:
        out[col] = tri[col] / tri[col].shift(days) - 1.0
    return out


def change_calc(df: pd.DataFrame, days: int, absolute: bool) -> pd.DataFrame:
    out = pd.DataFrame({"Country": df["Country"]})
    for col in df.columns[1:]:
        out[col] = (df[col] - df[col].shift(days)) if absolute else (df[col] / df[col].shift(days) - 1.0)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the daily T2 Master from the daily Bloomberg workbook.")
    ap.add_argument("--bloomberg", default=str(DEFAULT_BLOOMBERG))
    ap.add_argument("--p2p", default=str(DEFAULT_P2P))
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    bbg_path = Path(args.bloomberg)
    if not bbg_path.exists():
        logger.error("Daily Bloomberg workbook not found: %s", bbg_path)
        return 1
    xl = pd.ExcelFile(str(bbg_path))
    sheet_names = xl.sheet_names[1:]   # skip Master placeholder
    norm = {s.strip().lower(): s for s in xl.sheet_names}

    def find(name: str):
        return norm.get(name.strip().lower())

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Loading daily Bloomberg workbook: %s (%d sheets)", bbg_path, len(sheet_names))
    tri_name = find("tot return index") or find("tot return index ") or "Tot Return Index "
    tri = load_sheet(xl, tri_name, clean=False)
    assert_tri_has_data(tri, tri_name, bbg_path)

    with pd.ExcelWriter(str(out_path), engine="xlsxwriter",
                        engine_kwargs={"options": {"strings_to_numbers": True,
                                                   "remove_timezone": True,
                                                   "default_date_format": "yyyy-mm-dd"}}) as writer:
        # forward returns
        for n in FORWARD_PERIODS:
            clean_excel(forward_returns(tri, n)).to_excel(writer, sheet_name=f"{n}DRet", index=False)
        # trailing returns
        tr = {}
        for n in TRAILING_PERIODS:
            tr[n] = trailing_returns(tri, n)
            clean_excel(tr[n]).to_excel(writer, sheet_name=f"{n}DTR", index=False)
        # 120-5DTR spread
        spread = tr[120].drop("Country", axis=1) - tr[5].drop("Country", axis=1)
        spread.insert(0, "Country", tr[120]["Country"])
        clean_excel(spread).to_excel(writer, sheet_name="120-5DTR", index=False)
        # commodity betas (replace the raw 120-day price change)
        logger.info("Commodity betas (monthly rolling %d, min_periods %d, ffilled to daily)",
                    BETA_WINDOW_M, BETA_MIN_PERIODS_M)
        for nm in COMMODITY_SHEETS:
            sn = find(nm)
            if not sn:
                logger.warning("  commodity sheet %s missing from the daily workbook", nm)
                continue
            logger.info("  %s", nm)
            com = load_sheet(xl, sn, clean=False)
            betas = commodity_betas_daily(com, tri, label=nm)
            clean_excel_keep_na(betas.copy()).to_excel(writer, sheet_name=nm, index=False)
            # scaled sheet keeps the ORIGINAL 120-row horizon, so " 120" still
            # means what it always meant -- only the country dimension is new.
            com_chg = change_calc(com, COMMODITY_CHANGE_DAYS, False)
            scaled = pd.DataFrame({"Country": betas["Country"]})
            for col in betas.columns[1:]:
                scaled[col] = betas[col].to_numpy() * pd.to_numeric(
                    com_chg[col], errors="coerce").to_numpy()
            clean_excel_keep_na(scaled).to_excel(
                writer, sheet_name=f"{nm} {COMMODITY_CHANGE_DAYS}", index=False)

        # change variables
        for nm, (days, absolute) in CHANGE_CALCS.items():
            sn = find(nm)
            if sn:
                data = load_sheet(xl, sn, clean=False)
                clean_excel(change_calc(data, days, absolute)).to_excel(
                    writer, sheet_name=f"{nm} {days}", index=False)
        # 120MA signal = PX_LAST / 120MA
        px_sn, ma_sn = find("px_last"), find("120ma")
        if px_sn and ma_sn:
            px = load_sheet(xl, px_sn, clean=False); ma = load_sheet(xl, ma_sn, clean=False)
            sig = pd.DataFrame({"Country": px["Country"]})
            for col in px.columns[1:]:
                sig[col] = px[col] / ma[col]
            clean_excel(sig).to_excel(writer, sheet_name="120MA Signal", index=False)
        # P2P
        p2p_path = Path(args.p2p)
        if p2p_path.exists():
            p2p = pd.read_excel(str(p2p_path))
            if len(p2p.columns) <= len(COUNTRY_NAMES):
                p2p.columns = COUNTRY_NAMES[: len(p2p.columns)]
            p2p["Country"] = pd.to_datetime(p2p["Country"], errors="coerce")
            p2p = p2p.iloc[1:].reset_index(drop=True)
            clean_excel(p2p).to_excel(writer, sheet_name="P2P", index=False)
        else:
            logger.warning("P2P file not found: %s — skipping P2P sheet", p2p_path)
        # original sheets (cleaned)
        for sn in sheet_names:
            if sn.strip() in COMMODITY_SHEETS:
                continue   # already written as betas; see CHANGE_CALCS note
            try:
                clean_excel(load_sheet(xl, sn, clean=True)).to_excel(
                    writer, sheet_name=sn[:31], index=False)
            except Exception as e:
                logger.warning("  sheet %s failed: %s", sn, e)

    logger.info("Wrote %s", out_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
