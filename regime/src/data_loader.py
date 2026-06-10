"""
=============================================================================
SCRIPT NAME: data_loader.py
=============================================================================

DESCRIPTION:
    Loads and processes data for regime conditioning analysis. Factors,
    returns, and macro state are sourced from the ASADO DuckDB database
    (t2_master, extended_factors tables) with fallback to a normalized
    CSV file when the database is absent. Macro indicators (VIX, yields,
    CPI, unemployment, etc.) are fetched from the FRED API and cached
    as parquet files under data/raw/. All processed outputs are saved
    as parquet panels under data/processed/ for downstream modeling.

INPUT FILES:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb (optional)
        DuckDB database containing t2_master (52 cross-sectional factors
        and country returns), extended_factors (macro supplement series),
        and bloomberg_factors. Primary source for factor and return data.
    /Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing
    Fuzzy/Normalized_T2_MasterCSV.csv (fallback)
        Normalized CSV of T2 master data, used as fallback when the
        DuckDB database is not available.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime/data/raw/
    fred_{series_id}.parquet
        Cached FRED API responses, one parquet per series. Read back on
        subsequent runs to avoid repeated API calls.
    /Users/arjundivecha/Dropbox/AAA Backup/.env.txt
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/.env
        Environment files read (via utils.load_api_key) to obtain the
        FRED_API_KEY. Checked in order: environment variable, .env.txt,
        repo .env.
    FRED API (https://api.stlouisfed.org/fred/series/observations)
        HTTP source for 11 macro regime indicator series. Fetched when
        no cached parquet exists or force_refresh=True.

OUTPUT FILES:
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime/data/raw/
    fred_{series_id}.parquet
        Cached FRED API response written after each fetch. One parquet
        per series, serving as cache for subsequent runs.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime/data/raw/
    fred_{series_id}.meta.json
        Metadata sidecar for each FRED cache: series_id, row count, and
        source label.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime/data/
    processed/macro_monthly.parquet
        Monthly macro regime panel with raw indicators (vix, baa_oas,
        yield_2s10s, ust_10y, dxy, fed_funds, nber_recession, cpi_index,
        unemployment, umcsent, sp500) plus derived fields (cpi_yoy,
        sahm_rule, global_eq_vol_3m, etc.). Output of load_macro_panel.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime/data/
    processed/t2_factors_cs.parquet
        Tidy panel of cross-sectional T2 factor z-scores indexed by date,
        country, and factor. Output of load_factor_panel.
    /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime/data/
    processed/country_returns.parquet
        Realized country returns by horizon (1MRet, 3MRet). Output of
        load_country_returns.

VERSION: 1.0
LAST UPDATED: 2026-06-05
AUTHOR: Arjun Divecha

DEPENDENCIES:
    - duckdb
    - numpy
    - pandas
    - requests

USAGE:
    python -c "from data_loader import load_macro_panel, load_factor_panel,
    load_country_returns; panel = load_macro_panel()"

NOTES:
    - FRED data uses current vintage (not ALFRED), so values may differ
      from real-time historical.
    - The DuckDB database at asado.duckdb is preferred; the CSV fallback
      path is slower and only reads factor variables.
    - Cached FRED parquets are invalidated when force_refresh=True is
      passed to load_macro_panel.
    - Logging writes to /Users/arjundivecha/Dropbox/AAA Backup/A Working/
      ASADO/regime/results/regime_test.log (set up in utils.setup_logging).
=============================================================================
"""

from __future__ import annotations

import json
import logging
from typing import Dict, Optional

import duckdb
import numpy as np
import pandas as pd
import requests

from .utils import (
    ASADO_ROOT,
    DUCKDB_PATH,
    FULL_START,
    PROCESSED_DIR,
    RAW_DIR,
    T2_COUNTRIES,
    T2_CSV,
    ensure_dirs,
    load_api_key,
    month_start,
)

logger = logging.getLogger(__name__)

FRED_MACRO_SERIES: Dict[str, str] = {
    "VIXCLS": "vix",
    "BAA10Y": "baa_oas",  # Moody's BAA Corporate Bond Option-Adjusted Spread (full history 1990+)
    "T10Y2Y": "yield_2s10s",
    "DGS10": "ust_10y",
    "DTWEXBGS": "dxy",
    "FEDFUNDS": "fed_funds",
    "USREC": "nber_recession",
    "CPIAUCSL": "cpi_index",
    "UNRATE": "unemployment",
    "UMCSENT": "umcsent",  # University of Michigan Consumer Sentiment (ISM PMI discontinued on FRED)
    "SP500": "sp500",
}


def _fetch_fred_series(series_id: str, api_key: str, start: str = "1990-01-01") -> pd.Series:
    cache = RAW_DIR / f"fred_{series_id}.parquet"
    if cache.exists():
        df = pd.read_parquet(cache)
        return df.set_index("date")["value"].sort_index()

    url = (
        "https://api.stlouisfed.org/fred/series/observations"
        f"?series_id={series_id}&api_key={api_key}&file_type=json"
        f"&observation_start={start}&frequency=m&aggregation_method=avg"
    )
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    obs = resp.json().get("observations", [])
    rows = []
    for ob in obs:
        val = pd.to_numeric(ob.get("value", "."), errors="coerce")
        if pd.isna(val):
            continue
        rows.append({"date": pd.Timestamp(ob["date"]), "value": float(val)})
    df = pd.DataFrame(rows)
    df["date"] = month_start(df["date"])
    df = df.drop_duplicates("date").sort_values("date")
    df.to_parquet(cache, index=False)
    meta = {"series_id": series_id, "n": len(df), "source": "FRED current vintage (not ALFRED)"}
    (RAW_DIR / f"fred_{series_id}.meta.json").write_text(json.dumps(meta, indent=2))
    return df.set_index("date")["value"].sort_index()


def load_macro_panel(force_refresh: bool = False) -> pd.DataFrame:
    """Monthly macro state for regime tagging (US/global)."""
    ensure_dirs()
    out_path = PROCESSED_DIR / "macro_monthly.parquet"
    if out_path.exists() and not force_refresh:
        return pd.read_parquet(out_path)

    api_key = load_api_key("FRED_API_KEY")
    if not api_key:
        raise RuntimeError("FRED_API_KEY required for macro regime indicators")

    if force_refresh:
        for sid in FRED_MACRO_SERIES:
            p = RAW_DIR / f"fred_{sid}.parquet"
            if p.exists():
                p.unlink()

    series_map = {
        FRED_MACRO_SERIES[sid]: _fetch_fred_series(sid, api_key)
        for sid in FRED_MACRO_SERIES
    }

    macro = pd.DataFrame(series_map)
    macro.index.name = "date"
    macro = macro.sort_index()
    macro = macro.loc[macro.index >= FULL_START].copy()

    # Derived fields
    macro["cpi_yoy"] = macro["cpi_index"].pct_change(12) * 100
    macro["fed_funds_chg_12m"] = macro["fed_funds"] - macro["fed_funds"].shift(12)
    macro["dxy_chg_6m"] = macro["dxy"].pct_change(6) * 100
    macro["baa_oas_chg_3m"] = macro["baa_oas"] - macro["baa_oas"].shift(3)
    macro["vix_chg_3m"] = macro["vix"] - macro["vix"].shift(3)
    macro["umcsent_chg_3m"] = macro["umcsent"] - macro["umcsent"].shift(3)

    # Sahm rule: 3m avg unemployment minus 12m low of 3m avg unemployment
    u3 = macro["unemployment"].rolling(3, min_periods=3).mean()
    macro["sahm"] = u3 - u3.rolling(12, min_periods=12).min()
    macro["sahm_triggered"] = (macro["sahm"] >= 0.5).astype(float)

    # Global equity vol proxy: 3m realized vol of SP500 monthly returns
    sp_ret = macro["sp500"].pct_change()
    macro["global_eq_vol_3m"] = sp_ret.rolling(3, min_periods=3).std() * np.sqrt(12) * 100

    # Supplement from ASADO DuckDB where FRED gaps exist
    if DUCKDB_PATH.exists():
        macro = _supplement_from_duckdb(macro)

    macro = macro.reset_index()
    macro.to_parquet(out_path, index=False)
    logger.info("Macro panel: %s rows, %s to %s", len(macro), macro["date"].min(), macro["date"].max())
    return macro


def _supplement_from_duckdb(macro: pd.DataFrame) -> pd.DataFrame:
    """Fill select series from ASADO extended_factors when available."""
    if "date" in macro.columns:
        merged = macro.set_index("date")
    else:
        merged = macro.copy()
        merged.index.name = "date"

    con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
    mapping = {
        "FRED_VIX": "vix",
        "FRED_HY_OAS": "baa_oas",
        "FRED_Yield_Curve_10Y2Y": "yield_2s10s",
        "FRED_UST_10Y": "ust_10y",
        "FRED_USD_Broad_Index": "dxy",
    }
    for var, col in mapping.items():
        if col not in merged.columns:
            continue
        q = f"""
        SELECT date, AVG(value) AS value
        FROM extended_factors
        WHERE variable = '{var}' AND country = 'U.S.'
        GROUP BY date ORDER BY date
        """
        try:
            ext = con.execute(q).fetchdf()
        except Exception:
            continue
        if ext.empty:
            continue
        ext["date"] = month_start(ext["date"])
        ext = ext.set_index("date")["value"]
        missing = merged[col].isna()
        merged.loc[missing, col] = ext.reindex(merged.index)[missing]
    con.close()
    return merged.reset_index()


def list_t2_factor_variables() -> list[str]:
    """52 cross-sectional T2 factors (_CS), excluding return columns."""
    if DUCKDB_PATH.exists():
        con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
        df = con.execute("""
            SELECT DISTINCT variable FROM t2_master
            WHERE variable LIKE '%_CS'
              AND variable NOT LIKE '%Ret%'
              AND variable NOT LIKE 'Tot Return%'
            ORDER BY 1
        """).fetchdf()
        con.close()
        return df["variable"].tolist()

    # Fallback from CSV
    df = pd.read_csv(T2_CSV, usecols=["variable"])
    vars_ = df["variable"].unique()
    return sorted(
        v for v in vars_
        if v.endswith("_CS") and "Ret" not in v and "Tot Return" not in v
    )


def load_factor_panel(factors: Optional[list[str]] = None) -> pd.DataFrame:
    """Tidy panel: date, country, factor, value (factor z-scores)."""
    ensure_dirs()
    out = PROCESSED_DIR / "t2_factors_cs.parquet"
    if out.exists() and factors is None:
        return pd.read_parquet(out)

    if factors is None:
        factors = list_t2_factor_variables()

    if DUCKDB_PATH.exists():
        con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
        placeholders = ",".join(f"'{f}'" for f in factors)
        df = con.execute(f"""
            SELECT date, country, variable AS factor, value
            FROM t2_master
            WHERE variable IN ({placeholders})
              AND country IN ({','.join(repr(c) for c in T2_COUNTRIES)})
            ORDER BY date, country, factor
        """).fetchdf()
        con.close()
    else:
        raw = pd.read_csv(T2_CSV)
        df = raw[raw["variable"].isin(factors)].rename(columns={"variable": "factor"})
        df = df[df["country"].isin(T2_COUNTRIES)]

    df["date"] = month_start(df["date"])
    df.to_parquet(out, index=False)
    logger.info("Factor panel: %s rows, %d factors", len(df), df["factor"].nunique())
    return df


def load_country_returns(horizons: tuple[str, ...] = ("1MRet", "3MRet")) -> pd.DataFrame:
    """Realized country returns (wide-ready tidy)."""
    ensure_dirs()
    out = PROCESSED_DIR / "country_returns.parquet"
    if out.exists():
        return pd.read_parquet(out)

    if DUCKDB_PATH.exists():
        con = duckdb.connect(str(DUCKDB_PATH), read_only=True)
        hlist = ",".join(f"'{h}'" for h in horizons)
        df = con.execute(f"""
            SELECT date, country, variable AS horizon, value AS ret
            FROM t2_master
            WHERE variable IN ({hlist})
              AND country IN ({','.join(repr(c) for c in T2_COUNTRIES)})
        """).fetchdf()
        con.close()
    else:
        raw = pd.read_csv(T2_CSV)
        df = raw[raw["variable"].isin(horizons)].rename(
            columns={"variable": "horizon", "value": "ret"}
        )

    df["date"] = month_start(df["date"])
    df.to_parquet(out, index=False)
    return df


def build_forward_returns(returns: pd.DataFrame, horizon: str = "1MRet") -> pd.DataFrame:
    """
    1MRet at date t = return over month t. Factors are lagged one month in
    prepare_ic_panel, so merged signal at t pairs with fwd_ret at t.
    """
    r = returns[returns["horizon"] == horizon][["date", "country", "ret"]].copy()
    r = r.rename(columns={"ret": "fwd_ret"})
    r["date"] = month_start(r["date"])
    return r.dropna(subset=["fwd_ret"])
