#!/usr/bin/env python3
"""
Build ASADO Price-Discovery Gap Engine price-state surfaces.

Outputs:
- loop DB table price_state_daily
- loop DB table price_state_surface
- Data/loop/gap_engine/price_state_daily.parquet
- Data/loop/gap_engine/price_state_surface.parquet
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from scripts.loop.gap_engine_common import (  # noqa: E402
    ensure_loop_artifact_dir,
    json_dumps,
    latest_table_date,
    liquidity_tier,
    load_etf_map,
    load_etf_overrides,
    load_gap_config,
)
from scripts.loop.loopdb import T2_UNIVERSE, loop_connection, returns_panel  # noqa: E402


def log(msg: str) -> None:
    print(f"{datetime.now().strftime('%H:%M:%S')} [price-state] {msg}", flush=True)


def trailing_return(s: pd.Series, n: int) -> float | None:
    s = s.dropna()
    if len(s) < n:
        return None
    return float(np.exp(np.log1p(s.iloc[-n:]).sum()) - 1)


def trailing_price_return(prices: pd.Series, n: int) -> float | None:
    s = prices.dropna()
    if len(s) <= n:
        return None
    return float(s.iloc[-1] / s.iloc[-n - 1] - 1.0)


def z_last(values: pd.Series, window: int = 252, min_obs: int = 60) -> float | None:
    s = values.dropna()
    if len(s) < min_obs:
        return None
    hist = s.iloc[-window:]
    sd = hist.std()
    if not sd or np.isnan(sd):
        return None
    return float((hist.iloc[-1] - hist.mean()) / sd)


def latest_signal(con, table: str, country: str, variables: list[str], as_of: pd.Timestamp) -> dict[str, Any]:
    try:
        df = con.execute(
            f"""
            SELECT date, variable, value, source
            FROM {table}
            WHERE country = ? AND variable IN ({','.join(['?'] * len(variables))})
              AND CAST(date AS DATE) <= CAST(? AS DATE)
            QUALIFY row_number() OVER (PARTITION BY variable ORDER BY CAST(date AS DATE) DESC) = 1
            """,
            [country, *variables, str(as_of.date())],
        ).fetchdf()
    except Exception:
        return {}
    out: dict[str, Any] = {}
    for r in df.itertuples():
        out[r.variable] = {
            "value": None if pd.isna(r.value) else float(r.value),
            "date": str(pd.Timestamp(r.date).date()),
            "source": r.source,
        }
    return out


def surface_row(date, country, surface, state_score, direction_hint, freshness_date, lag_policy, state):
    return {
        "date": str(pd.Timestamp(date).date()),
        "country": country,
        "surface": surface,
        "state_score": state_score,
        "direction_hint": direction_hint,
        "freshness_date": str(pd.Timestamp(freshness_date).date()) if freshness_date is not None else None,
        "lag_policy": lag_policy,
        "state_json": json_dumps(state),
    }


def build(as_of: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg, _cfg_hash = load_gap_config()
    etf_map = load_etf_map()
    overrides = load_etf_overrides()
    override_rows = overrides.get("overrides", {})
    default_expense = overrides.get("defaults", {}).get("expense_ratio_bps")
    default_basis = overrides.get("metadata", {}).get("default_currency_basis", "usd_unhedged_etf_vs_t2")

    con = loop_connection()
    try:
        ret = returns_panel(con)
        if ret.empty:
            raise RuntimeError("returns_panel is empty")
        as_ts = pd.Timestamp(as_of) if as_of else pd.Timestamp(ret.index.max())
        ret = ret[ret.index <= as_ts]
        if ret.empty:
            raise RuntimeError(f"no returns <= {as_ts.date()}")

        etf_prices = con.execute(
            "SELECT CAST(date AS DATE) AS date, yf_ticker, close, volume FROM etf_prices_daily "
            "WHERE CAST(date AS DATE) <= CAST(? AS DATE)",
            [str(as_ts.date())],
        ).fetchdf()
        etf_prices["date"] = pd.to_datetime(etf_prices["date"])

        price_rows: list[dict[str, Any]] = []
        surface_rows: list[dict[str, Any]] = []
        for country in T2_UNIVERSE:
            mapped = etf_map.get(country, {})
            ov = override_rows.get(country, {})
            ticker = ov.get("primary") or mapped.get("primary")
            alternates = mapped.get("alternates", [])
            proxy_type = ov.get("proxy_type") or ("single_country_etf" if ticker else "none")
            expense = ov.get("expense_ratio_bps", default_expense)
            currency_basis = ov.get("currency_basis", default_basis)

            cret = ret[country].dropna() if country in ret.columns else pd.Series(dtype=float)
            c5 = trailing_return(cret, 5)
            c21 = trailing_return(cret, 21)
            c63 = trailing_return(cret, 63)
            c21_z = z_last(cret.rolling(21).apply(lambda x: np.exp(np.log1p(x).sum()) - 1, raw=False))

            ep = etf_prices[etf_prices["yf_ticker"] == ticker].sort_values("date") if ticker else pd.DataFrame()
            e5 = e21 = e63 = adv = basis5 = basis21 = basis_z = None
            latest_etf_date = None
            if not ep.empty:
                latest_etf_date = ep["date"].max()
                e5 = trailing_price_return(ep.set_index("date")["close"], 5)
                e21 = trailing_price_return(ep.set_index("date")["close"], 21)
                e63 = trailing_price_return(ep.set_index("date")["close"], 63)
                last21 = ep.tail(21).copy()
                adv = float((last21["close"] * last21["volume"]).mean()) if not last21.empty else None
                basis5 = None if e5 is None or c5 is None else e5 - c5
                basis21 = None if e21 is None or c21 is None else e21 - c21
                basis_series = []
                px = ep.set_index("date")["close"].pct_change()
                country_ret = cret.reindex(px.index).dropna()
                common = pd.concat([px, country_ret], axis=1, join="inner").dropna()
                if len(common) > 80:
                    b = common.iloc[:, 0] - common.iloc[:, 1]
                    basis_series = b.rolling(21).sum()
                    basis_z = z_last(basis_series)

            liq = liquidity_tier(adv, cfg)
            flow = latest_signal(con, "etf_flow_signals", country,
                                 ["ETF_FLOW_21D_Z", "ETF_FLOW_PCT_AUM_21D", "ETF_SHORT_PCT_Z"], as_ts)
            fx = latest_signal(con, "market_implied_signals", country,
                               ["FX_IMPVOL_Z252", "FX_RR25_Z252", "FX_BF25_Z252",
                                "FX_VOL_TERM_Z252", "FX_CARRY_3M_Z252"], as_ts)
            sov = latest_signal(con, "sovereign_signals", country,
                                ["SOV_CDS_SLOPE_BP_Z252", "SOV_2S10S_Z252",
                                 "SOV_CDS_SLOPE_BP", "SOV_2S10S_PCT"], as_ts)
            val = latest_signal(con, "valuation_monthly", country,
                                ["VAL_CAPE_PCTILE_10Y", "VAL_PB_PCTILE_10Y",
                                 "VAL_DY_PCTILE_10Y", "VAL_ERP_PCTILE_10Y"], as_ts)
            cons = latest_signal(con, "consensus_signals", country,
                                 ["CONS_GDP_REV3M_12M", "CONS_CPI_REV3M_12M"], as_ts)
            eco = latest_signal(con, "eco_surprise_signals", country,
                                ["ECO_GROWTH_SURPRISE_Z", "ECO_INFL_SURPRISE_Z"], as_ts)
            # NOTE (red-team 2026-06-26 / C1): combiner_scores_daily (COMBINER_RIDGE_DAILY_V1)
            # is a Ridge fit on FORWARD returns — a forbidden outcome surface. It must NOT be
            # embedded in source_freshness_json, which is allowlisted into the outcome-blind
            # Discovery Lab snapshot via surface_loader. Removed from the freshness blob below.

            equity_state = {"return_5d": c5, "return_21d": c21, "return_63d": c63, "return_21d_z": c21_z}
            etf_state = {"ticker": ticker, "alternates": alternates, "return_5d": e5, "return_21d": e21,
                         "return_63d": e63, "dollar_adv_21d": adv, "liquidity_tier": liq}
            summary = (
                f"{country}: T2 21d {c21:.1%}, {ticker or 'no ETF'} 21d {e21:.1%}, "
                f"basis {basis21:.1%}, liquidity {liq}"
                if c21 is not None and e21 is not None and basis21 is not None
                else f"{country}: partial price state; ETF={ticker or 'none'}, liquidity={liq}"
            )
            freshness = {
                "t2_returns": str(ret.index.max().date()),
                "etf_prices_daily": str(latest_etf_date.date()) if latest_etf_date is not None else None,
                "etf_flow_signals": flow,
                "market_implied_signals": fx,
                "sovereign_signals": sov,
                "valuation_monthly": val,
                "consensus_signals": cons,
                "eco_surprise_signals": eco,
            }
            price_rows.append({
                "date": str(as_ts.date()),
                "country": country,
                "preferred_ticker": ticker,
                "proxy_type": proxy_type,
                "expense_ratio_bps": expense,
                "dollar_adv_21d": adv,
                "liquidity_tier": liq,
                "bid_ask_spread_bps": None,
                "currency_basis": currency_basis,
                "etf_return_5d": e5,
                "etf_return_21d": e21,
                "country_return_5d": c5,
                "country_return_21d": c21,
                "basis_gap_5d": basis5,
                "basis_gap_21d": basis21,
                "basis_gap_z": basis_z,
                "fx_component_21d": None,
                "fx_adjusted_basis_gap_21d": None,
                "equity_state_json": json_dumps(equity_state),
                "fx_options_state_json": json_dumps(fx),
                "sovereign_state_json": json_dumps(sov),
                "flow_state_json": json_dumps(flow),
                "valuation_state_json": json_dumps(val),
                "predmkt_state_json": json_dumps({}),
                "price_state_summary": summary,
                "source_freshness_json": json_dumps(freshness),
            })

            surface_rows.append(surface_row(as_ts, country, "equity", c21_z, "long" if (c21 or 0) > 0 else "short", ret.index.max(), "market_daily", equity_state))
            surface_rows.append(surface_row(as_ts, country, "etf", basis_z, "long" if (basis21 or 0) < 0 else "short", latest_etf_date, "market_daily", etf_state))
            for name, state in [("fx_options", fx), ("sovereign", sov), ("valuation", val),
                                ("flows", flow), ("live_signal", comb), ("macro_revisions", {**cons, **eco})]:
                vals = [v.get("value") for v in state.values() if isinstance(v, dict) and v.get("value") is not None]
                score = float(np.nanmean(vals)) if vals else None
                fdates = [v.get("date") for v in state.values() if isinstance(v, dict) and v.get("date")]
                fdate = max(fdates) if fdates else None
                surface_rows.append(surface_row(as_ts, country, name, score,
                                                "long" if (score or 0) > 0 else "short",
                                                fdate, "source_specific", state))

        price_df = pd.DataFrame(price_rows)
        surface_df = pd.DataFrame(surface_rows)
        con.execute("CREATE OR REPLACE TABLE price_state_daily AS SELECT * FROM price_df")
        con.execute("CREATE OR REPLACE TABLE price_state_surface AS SELECT * FROM surface_df")

        out_dir = ensure_loop_artifact_dir()
        price_df.to_parquet(out_dir / "price_state_daily.parquet", index=False)
        surface_df.to_parquet(out_dir / "price_state_surface.parquet", index=False)
        log(f"price_state_daily: {len(price_df)} rows; price_state_surface: {len(surface_df)} rows for {as_ts.date()}")
        return price_df, surface_df
    finally:
        con.close()


def check() -> int:
    con = loop_connection(read_only=True)
    try:
        for table in ["price_state_daily", "price_state_surface"]:
            n = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            max_date = con.execute(f"SELECT max(date) FROM {table}").fetchone()[0]
            print(f"{table}: rows={n} max_date={max_date}")
        return 0
    finally:
        con.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Price-Discovery Gap Engine price-state tables.")
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        return check()
    build(args.as_of)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
