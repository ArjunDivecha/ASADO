#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: build_full_composite.py  (ASADO / momentum_fragility)
=============================================================================

DESCRIPTION:
    Builds the FULL Momentum-Fragility composite (PRD sections 2.1 components
    6-7, plus 2.2's "Full composite" variant) for the 34 T2 countries, monthly.
    This is the second half of the Momentum Fragility Index: it takes the 5
    already-built CORE components (from core_composite.parquet) and adds the
    two shorter-history components -- crowding and concentration -- then forms
    the 7-component Full composite.

    COMPONENT 6  Crowding (from bloomberg_factors, long/tidy):
        variables:
          MS_ETF_NetFlow_to_MarketCap   (monthly, 2015+)
          MS_Passive_Flow_Distortion    (monthly, filtered to 2015+ per PRD;
                                         pre-2015 exists but PRD deems it
                                         unreliable so it is dropped)
          MS_Index_Weight_Change        (ANNUAL, December snapshots only ->
                                         forward-filled to monthly, same
                                         treatment the PRD endorses for the
                                         quarterly concentration snapshots)
        Each variable: cross-sectional z across the 34-country panel each month
        (CS), then per-country EXPANDING z (min 24 months) of that CS series
        (TS). crowding_subscore = skipna mean of the three TS z-scores.
        Sign +  (more passive/ETF crowding & rising index weight => more
        fragile). Natural sign, no inversion.

    COMPONENT 7  Concentration (from concentration_panel.parquet):
        columns top_5_weight, tech_sector_weight (quarterly snapshots, in
        percent 0-100). Quarter-end dates are mapped to month-start and the
        snapshots are forward-filled to monthly frequency (holdings do not
        change month to month -- PRD 2.3). Each column: CS z across countries,
        then per-country EXPANDING z (min 24) TS. concentration_subscore =
        mean of the two TS z-scores. Sign +  (more top-5 / tech concentration
        => more fragile). Natural sign, no inversion.

    FULL COMPOSITE (PRD 2.2):
        composite_full = simple average of ALL 7 sign-oriented z-scored
        components:
          the 5 CORE components (mom_level, earn_revision_proxy, val_level,
          val_derating, factor_corr_stress -- read straight from
          core_composite.parquet, already the sign-oriented per-country
          expanding-z values that enter composite_core)
          + crowding_subscore + concentration_subscore.
        Computed ONLY for country-months where ALL 7 are non-null. This
        naturally restricts it to the window where concentration data exists
        AND has accumulated the 24 months of history the expanding-z rule
        requires (empirically ~2018-05 onward, NOT 2016 -- concentration
        starts 2016-06 and the hard min-24 expanding rule delays its first
        standardized value to 2018-05). No blending of a partial pre-2016
        composite with the full 2016+ one (PRD 2.2).

    STANDARDIZATION (PRD 2.4, hard house rule -- never full-sample):
        per-country EXPANDING z (min_periods=24) via
        regime_ew.src.ew_model.expanding_zscore, applied on top of a monthly
        cross-sectional z. Identical pattern to build_core_composite.py.

    KNOWN DATA LIMITATIONS (reported, never silently worked around -- FAIL IS
    FAIL):
      * TAIWAN has NO crowding data in bloomberg_factors (33/34 countries
        present; Taiwan absent from all three MS_* variables). Because
        composite_full requires all 7 components, Taiwan therefore has NO
        composite_full value at all -- it is present in the output as rows
        (with composite_full = NaN) but contributes nothing to the Full-
        composite sample. Taiwan is central to the Bernstein Asia-momentum
        thesis, so this gap is called out explicitly in the run report.
        Taiwan DOES have concentration data; the gap is crowding only.
      * MS_Index_Weight_Change is annual (December only) -> forward-filled.

INPUT FILES (all read-only):
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
        - bloomberg_factors : variables MS_ETF_NetFlow_to_MarketCap,
                              MS_Passive_Flow_Distortion, MS_Index_Weight_Change
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/momentum_fragility/results/core_composite.parquet
        - the 5 core components + composite_core + momentum_quartile_flag
          + 1MRet + 3MRet
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/momentum_fragility/results/concentration_panel.parquet
        - date, country, top_5_weight, tech_sector_weight (quarterly, percent)
    Reused modules (imported, not reimplemented):
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime/src/utils.py
        T2_COUNTRIES, month_start
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime_ew/src/ew_model.py
        expanding_zscore  (per-country expanding z, min_periods=24, ddof=0)

OUTPUT FILES:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/momentum_fragility/results/full_composite.parquet
        Columns (PRD 5, exact):
          date, country,
          composite_core, composite_full,
          crowding_subscore, concentration_subscore,
          momentum_quartile_flag, 1MRet, 3MRet

VERSION: 1.0
LAST UPDATED: 2026-07-05
AUTHOR: Arjun Divecha (build: Claude Code)

DEPENDENCIES: duckdb, numpy, pandas  (+ reused regime / regime_ew modules)

USAGE:
    python3 "build_full_composite.py"

NOTES:
    - FAIL IS FAIL: no silent fallbacks. Missing required variable/table/file
      raises. Taiwan's missing crowding is surfaced in the report, not patched.
    - Winsorization: raw crowding values are winsorized cross-sectionally each
      month at the 1st/99th percentile before z-scoring (a few MS_* readings
      are extreme outliers), mirroring build_core_composite.py hygiene.
    - Concentration weights are already bounded (0-100%), lightly winsorized
      cross-sectionally for symmetry with the crowding path.
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

from regime.src.utils import T2_COUNTRIES, month_start  # noqa: E402
from regime_ew.src.ew_model import expanding_zscore  # noqa: E402

MIN_STD_MONTHS = 24            # PRD 2.4 hard rule
WINSOR_LO, WINSOR_HI = 0.01, 0.99
CROWDING_START = "2015-01-01"  # PRD component 6: "available from 2015 only"

CROWDING_VARS = [
    "MS_ETF_NetFlow_to_MarketCap",   # monthly
    "MS_Passive_Flow_Distortion",    # monthly (filtered to 2015+)
    "MS_Index_Weight_Change",        # ANNUAL -> forward-filled
]
# annual variables that must be forward-filled to monthly before CS/TS z
ANNUAL_CROWDING_VARS = {"MS_Index_Weight_Change"}

CORE_COMPONENTS = [
    "mom_level",
    "earn_revision_proxy",
    "val_level",
    "val_derating",
    "factor_corr_stress",
]

CORE_PATH = RESULTS_DIR / "core_composite.parquet"
CONC_PATH = RESULTS_DIR / "concentration_panel.parquet"
OUT_PATH = RESULTS_DIR / "full_composite.parquet"


# --------------------------------------------------------------------------- #
# Helpers (identical conventions to build_core_composite.py)
# --------------------------------------------------------------------------- #
def _connect() -> duckdb.DuckDBPyConnection:
    if not WAREHOUSE.exists():
        raise FileNotFoundError(f"Warehouse not found: {WAREHOUSE}")
    return duckdb.connect(str(WAREHOUSE), read_only=True)


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


def _monthly_wide(
    long_df: pd.DataFrame, max_date: pd.Timestamp, ffill: bool
) -> pd.DataFrame:
    """
    Pivot a (date, country, value) long frame to wide (date x country) on a
    complete monthly grid spanning the data start .. max_date. If ffill=True
    (snapshot / annual series), forward-fill within each country so a slow
    snapshot contributes in the months between observations. If ffill=False
    (genuine monthly series), gaps stay NaN.
    """
    w = long_df.pivot_table(index="date", columns="country", values="value", aggfunc="mean")
    w = w.reindex(columns=[c for c in T2_COUNTRIES if c in w.columns])
    full_idx = pd.date_range(w.index.min(), max_date, freq="MS")
    w = w.reindex(full_idx).sort_index()
    if ffill:
        w = w.ffill()
    return w


def _cs_then_ts(wide_raw: pd.DataFrame, value_name: str) -> pd.DataFrame:
    """
    Standard pipeline: winsorize cross-sectionally -> cross-sectional z (CS) ->
    per-country expanding z (TS, min 24). Returns a long frame with columns
    date, country, <value_name>_cs, <value_name> (the TS value that enters the
    subscore).
    """
    w = _winsor_rows(wide_raw)
    cs = _cross_sectional_z(w)
    ts = expanding_zscore(cs, MIN_STD_MONTHS)
    out = _wide_to_long(cs, f"{value_name}_cs").merge(
        _wide_to_long(ts, value_name), on=["date", "country"]
    )
    return out


# --------------------------------------------------------------------------- #
# Component 6: crowding
# --------------------------------------------------------------------------- #
def build_crowding(con, max_date: pd.Timestamp) -> tuple[pd.DataFrame, dict]:
    """PRD component 6. Three MS_* crowding variables -> CS/TS z each ->
    skipna-mean into crowding_subscore. Sign + (natural)."""
    ts_frames = []
    diag = {}
    for var in CROWDING_VARS:
        raw = con.execute(
            "SELECT date, country, value FROM bloomberg_factors WHERE variable = ?",
            [var],
        ).fetchdf()
        if raw.empty:
            raise RuntimeError(f"bloomberg_factors '{var}' is empty")
        raw["date"] = month_start(raw["date"])
        raw = raw[raw["country"].isin(T2_COUNTRIES)]
        raw = raw[raw["date"] >= pd.Timestamp(CROWDING_START)]
        diag[var] = {
            "countries": sorted(raw["country"].unique().tolist()),
            "n_countries": raw["country"].nunique(),
            "date_min": str(raw["date"].min().date()),
            "date_max": str(raw["date"].max().date()),
            "annual": var in ANNUAL_CROWDING_VARS,
        }
        wide = _monthly_wide(raw, max_date, ffill=(var in ANNUAL_CROWDING_VARS))
        piece = _cs_then_ts(wide, var).rename(columns={var: f"{var}__ts"})
        ts_frames.append(piece[["date", "country", f"{var}__ts"]])

    merged = ts_frames[0]
    for f in ts_frames[1:]:
        merged = merged.merge(f, on=["date", "country"], how="outer")
    ts_cols = [f"{v}__ts" for v in CROWDING_VARS]
    # skipna mean: crowding_subscore exists if >=1 of the 3 TS z's is present.
    # By the time composite_full is active (~2018+) all three are present, so
    # this threshold only matters for the diagnostic early crowding history.
    merged["crowding_subscore"] = merged[ts_cols].mean(axis=1, skipna=True)
    merged["n_crowding"] = merged[ts_cols].notna().sum(axis=1)
    return merged[["date", "country", "crowding_subscore", "n_crowding"]], diag


# --------------------------------------------------------------------------- #
# Component 7: concentration
# --------------------------------------------------------------------------- #
def build_concentration(max_date: pd.Timestamp) -> tuple[pd.DataFrame, dict]:
    """PRD component 7. top_5_weight + tech_sector_weight from the quarterly
    concentration panel -> month-start + forward-fill to monthly -> CS/TS z each
    -> mean into concentration_subscore. Sign + (natural)."""
    if not CONC_PATH.exists():
        raise FileNotFoundError(f"Concentration panel not found: {CONC_PATH}")
    cp = pd.read_parquet(CONC_PATH)
    for col in ("top_5_weight", "tech_sector_weight"):
        if col not in cp.columns:
            raise RuntimeError(f"concentration_panel missing column '{col}'")
    cp["date"] = month_start(cp["date"])  # quarter-end -> month-start of that month
    cp = cp[cp["country"].isin(T2_COUNTRIES)]

    diag = {
        "n_countries": cp["country"].nunique(),
        "date_min": str(cp["date"].min().date()),
        "date_max": str(cp["date"].max().date()),
        "n_snapshots": cp["date"].nunique(),
    }

    ts_frames = []
    for col in ("top_5_weight", "tech_sector_weight"):
        long = cp[["date", "country", col]].rename(columns={col: "value"})
        wide = _monthly_wide(long, max_date, ffill=True)  # snapshot -> ffill monthly
        piece = _cs_then_ts(wide, col).rename(columns={col: f"{col}__ts"})
        ts_frames.append(piece[["date", "country", f"{col}__ts"]])

    merged = ts_frames[0].merge(ts_frames[1], on=["date", "country"], how="outer")
    ts_cols = ["top_5_weight__ts", "tech_sector_weight__ts"]
    merged["concentration_subscore"] = merged[ts_cols].mean(axis=1, skipna=True)
    merged["n_concentration"] = merged[ts_cols].notna().sum(axis=1)
    return merged[["date", "country", "concentration_subscore", "n_concentration"]], diag


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    if not CORE_PATH.exists():
        raise FileNotFoundError(f"core_composite.parquet not found: {CORE_PATH}")
    core = pd.read_parquet(CORE_PATH)
    core["date"] = pd.to_datetime(core["date"])
    missing_core = [c for c in CORE_COMPONENTS if c not in core.columns]
    if missing_core:
        raise RuntimeError(f"core_composite.parquet missing components: {missing_core}")
    max_date = core["date"].max()
    core_countries = set(core["country"].unique())

    con = _connect()
    try:
        print("Building crowding (component 6) ...")
        crowding, crowd_diag = build_crowding(con, max_date)
    finally:
        con.close()

    print("Building concentration (component 7) ...")
    concentration, conc_diag = build_concentration(max_date)

    # merge onto core (LEFT from core -> never drops a core country-month)
    keep_core = [
        "date", "country",
        *CORE_COMPONENTS,
        "composite_core", "momentum_quartile_flag", "1MRet", "3MRet",
    ]
    panel = core[keep_core].merge(
        crowding[["date", "country", "crowding_subscore"]],
        on=["date", "country"], how="left",
    ).merge(
        concentration[["date", "country", "concentration_subscore"]],
        on=["date", "country"], how="left",
    )

    # Full composite = simple average of ALL 7 sign-oriented components,
    # only where ALL 7 are non-null (PRD 2.2).
    seven = CORE_COMPONENTS + ["crowding_subscore", "concentration_subscore"]
    all_present = panel[seven].notna().all(axis=1)
    panel["composite_full"] = np.where(all_present, panel[seven].mean(axis=1), np.nan)

    out_cols = [
        "date", "country",
        "composite_core", "composite_full",
        "crowding_subscore", "concentration_subscore",
        "momentum_quartile_flag", "1MRet", "3MRet",
    ]
    out = panel[out_cols].sort_values(["country", "date"]).reset_index(drop=True)
    out.to_parquet(OUT_PATH, index=False)

    _report(out, core_countries, crowd_diag, conc_diag, OUT_PATH)


def _report(out, core_countries, crowd_diag, conc_diag, out_path) -> None:
    print("\n" + "=" * 72)
    print("FULL COMPOSITE  --  REPORT")
    print("=" * 72)

    nz = out.dropna(subset=["composite_full"])
    print(f"\nOutput rows: {len(out):,}   countries in output: {out['country'].nunique()}")
    print(f"core_composite countries: {len(core_countries)}  ->  "
          f"merge dropped none: {out['country'].nunique() == len(core_countries)}")

    print("\n--- composite_full (all-7-present) ---")
    print(f"non-null rows: {len(nz):,}  "
          f"({out['composite_full'].notna().mean()*100:.1f}% of output)")
    if not nz.empty:
        print(f"date range: {nz['date'].min().date()} .. {nz['date'].max().date()}")
        print(f"countries with >=1 composite_full: {nz['country'].nunique()}")
        print(f"mean={nz['composite_full'].mean():+.4f} std={nz['composite_full'].std():.4f} "
              f"min={nz['composite_full'].min():+.3f} max={nz['composite_full'].max():+.3f}")

    print("\n--- subscore coverage ---")
    for c in ("crowding_subscore", "concentration_subscore", "composite_core"):
        s = out[c]
        print(f"  {c:24s} non-null {s.notna().mean()*100:5.1f}%  "
              f"mean={s.mean():+.3f} std={s.std():.3f}  "
              f"countries={out.loc[s.notna(),'country'].nunique()}")

    # Taiwan gap (crowding missing) surfaced explicitly
    missing_crowd = sorted(set(T2_COUNTRIES) - set(crowd_diag[CROWDING_VARS[0]]["countries"]))
    print("\n--- KNOWN DATA LIMITATIONS ---")
    print(f"  Countries absent from crowding (all MS_* vars): {missing_crowd}")
    for v in CROWDING_VARS:
        d = crowd_diag[v]
        print(f"    {v}: {d['n_countries']} countries, {d['date_min']}..{d['date_max']}"
              f"{'  [ANNUAL, ffilled]' if d['annual'] else '  [monthly]'}")
    tw = out[(out["country"] == "Taiwan")]
    print(f"  Taiwan: {len(tw)} output rows, "
          f"crowding_subscore non-null={tw['crowding_subscore'].notna().sum()}, "
          f"concentration_subscore non-null={tw['concentration_subscore'].notna().sum()}, "
          f"composite_full non-null={tw['composite_full'].notna().sum()}  "
          f"(=> Taiwan excluded from Full composite: no crowding data)")

    print(f"\n  Concentration panel: {conc_diag['n_countries']} countries, "
          f"{conc_diag['date_min']}..{conc_diag['date_max']}, "
          f"{conc_diag['n_snapshots']} snapshots")

    # per-country composite_full counts
    print("\n--- composite_full months per country (non-null) ---")
    cnt = nz.groupby("country").size().sort_values()
    print(cnt.to_string())

    # momentum-quartile subset (the actual Gate-3 sample) size within full composite
    q = nz[nz["momentum_quartile_flag"]]
    print(f"\ntop-momentum-quartile country-months WITHIN composite_full sample: {len(q):,}")

    print(f"\nWrote: {out_path}")
    print(f"file://{str(out_path).replace(' ', '%20')}")


if __name__ == "__main__":
    main()
