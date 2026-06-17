#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/harness/ff_spanning.py
=============================================================================

DESCRIPTION:
Style-factor SPANNING regressions against the Ken French regional factor
library (table `ff_factors`, built by scripts/collect_ff_factors.py). This is
the analytical companion to the skeptic harness (evaluate_signal.py): it asks
the one question raw IC / Sharpe cannot — "is this signal's long-short P&L
genuinely orthogonal alpha, or is it just repackaged regional value / size /
momentum / quality / market beta?"

It regresses a return series r_t on a chosen FF factor model:

    r_t (- RF_t)  =  alpha  +  b_mkt·Mkt_RF + b_smb·SMB + b_hml·HML
                              + b_rmw·RMW + b_cma·CMA + b_wml·WML  +  e_t

and reports the intercept (alpha) with a Newey-West (Bartlett-kernel) HAC
t-stat, every factor beta with its HAC t-stat, and R². A signal whose raw
Sharpe looks good but whose spanning alpha is insignificant is NOT new alpha —
it is a known style tilt you could already harvest with an index fund.

The Newey-West Bartlett kernel here matches evaluate_signal.nw_tstat so the two
tools speak the same statistical language.

Country -> FF region: config/ff_region_map.json (written by the collector). FF
factors are REGIONAL, never per-country — for a country return series the right
benchmark is its regional bundle (e.g. Brazil -> Emerging, Germany -> Europe).

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
    Read-only. Table `ff_factors` (date, region, frequency, variable, value%, ...).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/ff_region_map.json
    Country -> FF region map.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Read-only, ONLY for the --country convenience path (country_returns_monthly).

OUTPUT FILES:
- None by default (returns a dict / prints a report). With --json PATH, writes
  the result payload to PATH.

VERSION: 1.0
LAST UPDATED: 2026-06-17
AUTHOR: Claude Code for Arjun Divecha

DEPENDENCIES: duckdb, pandas, numpy (project venv).

USAGE (programmatic — the main intended use, on a harness LS return series):
    from scripts.harness.ff_spanning import style_spanning
    res = style_spanning(ls_returns, country="Brazil", model="ff5_mom",
                         frequency="monthly", returns_units="decimal")
    print(res["alpha_ann_pct"], res["alpha_tstat"])

USAGE (CLI convenience — span an ASADO country's own returns vs its FF region):
    python scripts/harness/ff_spanning.py --country Brazil --model ff5_mom
    python scripts/harness/ff_spanning.py --country U.S. --model ff6 --frequency monthly
    python scripts/harness/ff_spanning.py --region Emerging --returns-parquet my_ls.parquet

NOTES:
- For a self-financing long-short P&L pass subtract_rf=False (default): an LS
  book funds itself, so its raw return is regressed directly on the factors
  (Mkt_RF is itself already an excess return). For a long-only TOTAL return
  series use subtract_rf=True so the LHS is an excess return.
- RF is NOT a regressor — it is the funding rate. The regressors are the chosen
  subset of {Mkt_RF, SMB, HML, RMW, CMA, WML}.
=============================================================================
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

import duckdb
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ASADO_DB = BASE_DIR / "Data" / "asado.duckdb"
LOOP_DB = BASE_DIR / "Data" / "loop" / "asado_loop.duckdb"
REGION_MAP_PATH = BASE_DIR / "config" / "ff_region_map.json"

# Factor models: ordered regressor sets (RF excluded — it is the funding rate).
MODELS: dict[str, list[str]] = {
    "capm":     ["Mkt_RF"],
    "ff3":      ["Mkt_RF", "SMB", "HML"],
    "carhart":  ["Mkt_RF", "SMB", "HML", "WML"],   # == ff3_mom
    "ff3_mom":  ["Mkt_RF", "SMB", "HML", "WML"],
    "ff5":      ["Mkt_RF", "SMB", "HML", "RMW", "CMA"],
    "ff5_mom":  ["Mkt_RF", "SMB", "HML", "RMW", "CMA", "WML"],
    "ff6":      ["Mkt_RF", "SMB", "HML", "RMW", "CMA", "WML"],  # alias
}
PERIODS_PER_YEAR = {"monthly": 12, "daily": 252}


def _auto_nw_lags(T: int) -> int:
    """Newey-West rule of thumb: floor(4*(T/100)^(2/9)), >= 1."""
    return max(1, int(4 * (T / 100.0) ** (2.0 / 9.0)))


def _ols_hac(y: np.ndarray, X: np.ndarray, nw_lags: int) -> dict[str, Any]:
    """OLS with Newey-West (Bartlett-kernel) HAC covariance.

    X must already include the intercept column. Returns betas, HAC standard
    errors, t-stats, R², n. Bartlett weights w_l = 1 - l/(L+1) match
    evaluate_signal.nw_tstat.
    """
    T, k = X.shape
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ (X.T @ y)
    resid = y - X @ beta

    # HAC "meat": S0 + Bartlett-weighted autocovariances of the score x_t*e_t
    u = X * resid[:, None]                  # (T,k) scores
    S = u.T @ u                             # lag 0
    L = min(nw_lags, T - 1)
    for l in range(1, L + 1):
        w = 1.0 - l / (L + 1)
        G = u[l:].T @ u[:-l]                # (k,k)
        S += w * (G + G.T)
    cov = XtX_inv @ S @ XtX_inv
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    tstat = np.divide(beta, se, out=np.full_like(beta, np.nan), where=se > 0)

    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else np.nan
    return {"beta": beta, "se": se, "tstat": tstat, "r2": r2, "n": T, "nw_lags": L}


def _load_region_map() -> dict[str, Any]:
    if not REGION_MAP_PATH.exists():
        raise FileNotFoundError(
            f"{REGION_MAP_PATH} missing — run scripts/collect_ff_factors.py first.")
    return json.loads(REGION_MAP_PATH.read_text())


def region_of_country(country: str) -> tuple[str, str]:
    """Return (ff_region, confidence) for an ASADO T2 country."""
    cmap = _load_region_map().get("country_to_region", {})
    if country not in cmap:
        raise ValueError(
            f"No FF region for {country!r}. Known: {sorted(cmap)}")
    e = cmap[country]
    return e["region"], e.get("confidence", "exact")


def load_ff_factors(region: str, frequency: str,
                    variables: list[str],
                    con: Optional[duckdb.DuckDBPyConnection] = None) -> pd.DataFrame:
    """Wide, date-indexed DECIMAL factor frame for one region/frequency."""
    own = con is None
    con = con or duckdb.connect(str(ASADO_DB), read_only=True)
    try:
        vlist = ",".join(f"'{v}'" for v in set(variables) | {"RF"})
        df = con.execute(f"""
            SELECT date, variable, value
            FROM ff_factors
            WHERE region = '{region}' AND frequency = '{frequency}'
              AND variable IN ({vlist})
            ORDER BY date
        """).fetchdf()
    finally:
        if own:
            con.close()
    if df.empty:
        raise ValueError(f"No ff_factors rows for region={region} freq={frequency}")
    wide = df.pivot(index="date", columns="variable", values="value") / 100.0  # %→decimal
    wide.index = pd.to_datetime(wide.index)
    return wide


def style_spanning(returns: pd.Series,
                   region: Optional[str] = None,
                   country: Optional[str] = None,
                   model: str = "ff5_mom",
                   frequency: str = "monthly",
                   returns_units: str = "decimal",
                   subtract_rf: bool = False,
                   nw_lags: Optional[int] = None,
                   con: Optional[duckdb.DuckDBPyConnection] = None) -> dict[str, Any]:
    """Regress a return series on a Ken French factor model and report alpha.

    Args:
        returns: date-indexed Series of per-period returns (the thing to explain,
            e.g. a long-short P&L). Index is coerced to datetime.
        region / country: pick the FF benchmark bundle. Give one. `country` is
            mapped to its FF region via config/ff_region_map.json.
        model: key in MODELS ('capm','ff3','carhart','ff5','ff5_mom'/'ff6').
        frequency: 'monthly' or 'daily' (must match the returns' frequency).
        returns_units: 'decimal' (0.01 = 1%) or 'percent' (1.0 = 1%).
        subtract_rf: True for a long-only TOTAL return (LHS becomes excess);
            False for a self-financing long-short P&L (default).
        nw_lags: Newey-West lag truncation; None → rule-of-thumb.
        con: optional shared read-only DuckDB connection.

    Returns: dict with alpha (per-period + annualised, %), alpha t-stat, each
        factor beta + t-stat, R², n, span dates, region, confidence, model.
    """
    if model not in MODELS:
        raise ValueError(f"Unknown model {model!r}. Options: {sorted(MODELS)}")
    factors = MODELS[model]

    confidence = "exact"
    if region is None:
        if country is None:
            raise ValueError("Give either region or country.")
        region, confidence = region_of_country(country)

    r = returns.copy()
    r.index = pd.to_datetime(r.index)
    r = r.dropna()
    if returns_units == "percent":
        r = r / 100.0
    elif returns_units != "decimal":
        raise ValueError("returns_units must be 'decimal' or 'percent'")

    ff = load_ff_factors(region, frequency, factors, con=con)
    aligned = pd.concat([r.rename("ret"), ff], axis=1, join="inner").dropna(
        subset=["ret"] + factors)
    if subtract_rf:
        aligned["ret"] = aligned["ret"] - aligned["RF"]
    if len(aligned) < 24:
        raise ValueError(f"Only {len(aligned)} aligned periods — need >= 24.")

    y = aligned["ret"].to_numpy()
    Xcols = ["const"] + factors
    X = np.column_stack([np.ones(len(aligned))] + [aligned[f].to_numpy() for f in factors])
    L = nw_lags if nw_lags is not None else _auto_nw_lags(len(aligned))
    fit = _ols_hac(y, X, L)

    ppy = PERIODS_PER_YEAR[frequency]
    alpha = float(fit["beta"][0])
    out = {
        "region": region,
        "region_confidence": confidence,
        "country": country,
        "model": model,
        "frequency": frequency,
        "subtract_rf": subtract_rf,
        "n": int(fit["n"]),
        "nw_lags": int(fit["nw_lags"]),
        "span_start": str(aligned.index.min().date()),
        "span_end": str(aligned.index.max().date()),
        "alpha_per_period_pct": round(alpha * 100, 4),
        "alpha_ann_pct": round(alpha * ppy * 100, 3),
        "alpha_tstat": round(float(fit["tstat"][0]), 3),
        "r2": round(float(fit["r2"]), 4),
        "betas": {},
    }
    for i, name in enumerate(Xcols):
        if name == "const":
            continue
        out["betas"][name] = {
            "beta": round(float(fit["beta"][i]), 4),
            "tstat": round(float(fit["tstat"][i]), 3),
        }
    # plain-language verdict on the alpha
    t = out["alpha_tstat"]
    out["alpha_verdict"] = (
        "SPANNED (no significant alpha — return is explained by style factors)"
        if abs(t) < 2.0 else
        "UNSPANNED (significant alpha beyond the style factors)"
    )
    return out


def span_country_returns(country: str, model: str = "ff5_mom",
                         frequency: str = "monthly",
                         start_date: Optional[str] = None) -> dict[str, Any]:
    """Convenience: pull an ASADO country's own returns and span them vs its FF
    region. Proves the whole pipeline end-to-end. country_returns_monthly is a
    TOTAL return (decimal), so subtract_rf=True."""
    if frequency != "monthly":
        raise ValueError("span_country_returns currently supports monthly only "
                         "(country_returns_monthly).")
    con = duckdb.connect(str(LOOP_DB), read_only=True)
    try:
        clause = f"AND date >= '{start_date}'" if start_date else ""
        df = con.execute(f"""
            SELECT date, return_1m FROM country_returns_monthly
            WHERE country = '{country}' {clause} ORDER BY date
        """).fetchdf()
    finally:
        con.close()
    if df.empty:
        raise ValueError(f"No country_returns_monthly rows for {country!r}")
    s = pd.Series(df["return_1m"].to_numpy(), index=pd.to_datetime(df["date"]))
    return style_spanning(s, country=country, model=model, frequency=frequency,
                          returns_units="decimal", subtract_rf=True)


def _print_report(res: dict[str, Any]) -> None:
    print("=" * 64)
    print("  KEN FRENCH STYLE-SPANNING REGRESSION")
    print("=" * 64)
    who = res.get("country") or res["region"]
    print(f"  series:     {who}  (FF region: {res['region']}, "
          f"{res['region_confidence']})")
    print(f"  model:      {res['model']}  [{res['frequency']}]  "
          f"subtract_rf={res['subtract_rf']}")
    print(f"  span:       {res['span_start']} .. {res['span_end']}  "
          f"(n={res['n']}, NW lags={res['nw_lags']})")
    print(f"  R²:         {res['r2']:.4f}")
    print("-" * 64)
    print(f"  ALPHA:      {res['alpha_ann_pct']:+.2f}%/yr  "
          f"({res['alpha_per_period_pct']:+.4f}%/period)   "
          f"t = {res['alpha_tstat']:+.2f}")
    print(f"  -> {res['alpha_verdict']}")
    print("-" * 64)
    print("  factor betas (t-stat):")
    for name, b in res["betas"].items():
        print(f"    {name:8} {b['beta']:+.3f}  (t={b['tstat']:+.2f})")
    print("=" * 64)


def main() -> int:
    ap = argparse.ArgumentParser(description="Ken French style-spanning regression.")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--country", help="ASADO T2 country (uses country_returns_monthly).")
    g.add_argument("--region", help="FF region (requires --returns-parquet).")
    ap.add_argument("--model", default="ff5_mom", choices=sorted(MODELS),
                    help="Factor model (default ff5_mom).")
    ap.add_argument("--frequency", default="monthly", choices=["monthly", "daily"])
    ap.add_argument("--start-date", help="Optional YYYY-MM-DD lower bound.")
    ap.add_argument("--returns-parquet", help="Parquet with columns [date, return] "
                    "to span when using --region (or to override --country returns).")
    ap.add_argument("--returns-units", default="decimal", choices=["decimal", "percent"])
    ap.add_argument("--subtract-rf", action="store_true",
                    help="Subtract RF (use for long-only total returns).")
    ap.add_argument("--json", help="Write the result payload to this path.")
    args = ap.parse_args()

    if args.returns_parquet:
        df = pd.read_parquet(args.returns_parquet)
        cols = {c.lower(): c for c in df.columns}
        dcol = cols.get("date", df.columns[0])
        rcol = cols.get("return", cols.get("return_1m", df.columns[1]))
        s = pd.Series(df[rcol].to_numpy(), index=pd.to_datetime(df[dcol]))
        res = style_spanning(s, region=args.region, country=args.country,
                             model=args.model, frequency=args.frequency,
                             returns_units=args.returns_units,
                             subtract_rf=args.subtract_rf)
    elif args.country:
        res = span_country_returns(args.country, model=args.model,
                                   frequency=args.frequency,
                                   start_date=args.start_date)
    else:
        ap.error("--region requires --returns-parquet")
        return 2

    _print_report(res)
    if args.json:
        Path(args.json).write_text(json.dumps(res, indent=2))
        print(f"\n  wrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
