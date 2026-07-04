"""
=============================================================================
SCRIPT NAME: backtest_overnight_signal.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/predmkt_equity/markets.parquet
  Parsed directional closed Polymarket firm markets (from backtest_overnight_pull.py).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/predmkt_equity/history/{conditionId}.parquet
  Lifetime YES-token price history per market (10-min fidelity, UTC).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/predmkt_equity/equity_bars.parquet
  Daily open/close bars per ticker (from pull_overnight_equity_bars.py, Bloomberg).

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/predmkt_equity/overnight_pairs.parquet
  One row per (market, trading-day pair): close-window price, open-window
  price, delta_p aligned, realized gap, continuation return.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/predmkt_equity/backtest_results_{YYYY_MM_DD}.xlsx
  Event-study regressions, PnL summaries, sensitivity grids, equity curves.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/docs/OVERNIGHT_SIGNAL_BACKTEST_{YYYY_MM_DD}.md
  Human-readable backtest report (gate verdict + realizable PnL + drawdown).

VERSION: 1.0
LAST UPDATED: 2026-07-03
AUTHOR: Claude Code (for Arjun Divecha)

DESCRIPTION:
Milestone M5c of the Tier 1 overnight prediction-market -> equity signal
(Li & Wang 2026 §5.2 replication on Arjun's own collected universe).

Per market and consecutive-trading-day pair (d, d_next):
  p_close = last aligned PM print in [d 19:30, d 23:30) UTC
  p_open  = first aligned PM print in [d_next 12:30, d_next 15:30) UTC
            (tradeable variant: first print in [12:30, 13:30) — before the
             US cash open, so the signal exists when you can still act)
  delta_p = p_open - p_close      (stock-up-aligned)
  r_gap   = ln(open_{d_next} / close_d)          [same-window gap — event study]
  r_cont  = ln(close_{d_next} / open_{d_next})   [realizable continuation]

Gate 1 (event study): pooled OLS of r_gap on delta_p with contract fixed
effects, SEs clustered by contract and by day; a positive significant gamma
replicates the paper. Placebo: delta_p regressed on the FOLLOWING night's
gap must be ~0.

Gate 2 (realizable PnL): sign(delta_p) portfolios earning r_cont (enter at
the open after the signal, exit same-day close), equal-weighted across
qualifying tickers each day, min-move theta grid x cost grid; reports
return, Sharpe, max drawdown, hit rate, turnover, and the equity curve.

DEPENDENCIES:
- pandas, numpy, statsmodels, pyarrow, openpyxl (project venv)

USAGE:
  python scripts/backtest_overnight_signal.py
  python scripts/backtest_overnight_signal.py --pre-open-only   [tradeable window variant]

NOTES:
- Windows are UTC per the PRD (US session 13:30-20:00 UTC in summer).
- Friday->Monday pairs are kept and flagged is_weekend for sensitivity.
- The same-window caveat is structural: gate 1 tests information content,
  gate 2 tests what is actually capturable after the open.
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, time as dtime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

BASE_DIR = Path(__file__).resolve().parent.parent
WORK_DIR = BASE_DIR / "Data" / "work" / "predmkt_equity"
HISTORY_DIR = WORK_DIR / "history"
MARKETS_PATH = WORK_DIR / "markets.parquet"
BARS_PATH = WORK_DIR / "equity_bars.parquet"
PAIRS_PATH = WORK_DIR / "overnight_pairs.parquet"
STAMP = datetime.now().strftime("%Y_%m_%d")
XLSX_PATH = WORK_DIR / f"backtest_results_{STAMP}.xlsx"
REPORT_PATH = BASE_DIR / "docs" / f"OVERNIGHT_SIGNAL_BACKTEST_{STAMP}.md"

# UTC windows (PRD §2)
CLOSE_WIN = (dtime(19, 30), dtime(23, 30))
OPEN_WIN = (dtime(12, 30), dtime(15, 30))
OPEN_WIN_TRADEABLE = (dtime(12, 30), dtime(13, 30))

THETA_GRID = [0.0, 0.01, 0.03, 0.05]
COST_BPS_GRID = [0, 2, 5, 10]  # one-way, megacap-appropriate
MIN_ABS_PRICE = 0.02  # drop aligned prices pinned at 0/1 (resolved/dead)
MAX_ABS_PRICE = 0.98


def build_pairs(pre_open_only: bool) -> pd.DataFrame:
    markets = pd.read_parquet(MARKETS_PATH)
    bars = pd.read_parquet(BARS_PATH)
    bars["date"] = pd.to_datetime(bars["date"]).dt.normalize()
    trading_days = sorted(bars["date"].unique())
    next_td = {d: n for d, n in zip(trading_days, trading_days[1:])}

    open_win = OPEN_WIN_TRADEABLE if pre_open_only else OPEN_WIN

    hist_files = {p.stem: p for p in HISTORY_DIR.glob("*.parquet")}
    rows: list[dict] = []
    n_loaded = 0
    for mk in markets.itertuples():
        path = hist_files.get(mk.market_id)
        if path is None:
            continue
        try:
            hist = pd.read_parquet(path)
        except Exception:
            continue
        if hist.empty:
            continue
        n_loaded += 1
        hist = hist.sort_values("ts")
        p = hist["p_yes"].astype(float)
        if not mk.yes_rises_with_stock:
            p = 1.0 - p
        hist = hist.assign(p_aligned=p)
        # keep only informative prints
        hist = hist[(hist["p_aligned"] > MIN_ABS_PRICE) & (hist["p_aligned"] < MAX_ABS_PRICE)]
        if hist.empty:
            continue
        ts = hist["ts"].dt
        hist = hist.assign(day=ts.normalize().dt.tz_localize(None), tod=ts.time)

        close_prints = hist[(hist["tod"] >= CLOSE_WIN[0]) & (hist["tod"] < CLOSE_WIN[1])]
        open_prints = hist[(hist["tod"] >= open_win[0]) & (hist["tod"] < open_win[1])]
        if close_prints.empty or open_prints.empty:
            continue
        last_close = close_prints.groupby("day")["p_aligned"].last()
        first_open = open_prints.groupby("day")["p_aligned"].first()

        for d, p_close in last_close.items():
            d_next = next_td.get(d)
            if d_next is None:
                continue
            p_open = first_open.get(d_next)
            if p_open is None or pd.isna(p_open):
                continue
            rows.append(
                {
                    "market_id": mk.market_id,
                    "ticker": mk.ticker,
                    "contract_class": mk.contract_class,
                    "is_etf": mk.is_etf,
                    "volume_usd": mk.volume_usd,
                    "d": d,
                    "d_next": d_next,
                    "is_weekend": (d_next - d).days > 1,
                    "p_close": float(p_close),
                    "p_open": float(p_open),
                    "delta_p": float(p_open - p_close),
                }
            )
    pairs = pd.DataFrame(rows)
    print(f"Loaded {n_loaded} histories -> {len(pairs)} market-night pairs")
    if pairs.empty:
        return pairs

    # label realized gap and continuation from equity bars
    bars = bars.sort_values(["ticker", "date"])
    bars["prev_close"] = bars.groupby("ticker")["px_last"].shift(1)
    bars["prev_date"] = bars.groupby("ticker")["date"].shift(1)
    lab = bars.rename(columns={"date": "d_next"})[
        ["ticker", "d_next", "px_open", "px_last", "prev_close", "prev_date"]
    ]
    pairs = pairs.merge(lab, on=["ticker", "d_next"], how="left")
    ok = pairs["prev_date"] == pairs["d"]
    print(f"  bar alignment: {ok.sum()}/{len(pairs)} pairs have matching prior trading day")
    pairs = pairs[ok & pairs["px_open"].notna() & pairs["prev_close"].notna()].copy()
    pairs["r_gap"] = np.log(pairs["px_open"] / pairs["prev_close"])
    pairs["r_cont"] = np.log(pairs["px_last"] / pairs["px_open"])
    return pairs


def event_study(pairs: pd.DataFrame) -> pd.DataFrame:
    """Pooled + FE regressions of r_gap on delta_p, plus next-night placebo."""
    df = pairs.copy()
    df["d_str"] = df["d"].astype(str)
    results = []

    def run(
        sub: pd.DataFrame,
        label: str,
        yvar: str = "r_gap",
        fe: bool = True,
        fe_key: str = "market_id",
    ):
        if len(sub) < 50:
            results.append({"spec": label, "n": len(sub), "note": "insufficient obs"})
            return
        sub = sub.copy()
        if fe:
            # contracts observed once contribute nothing under their own FE;
            # daily contract classes should pass fe_key="ticker"
            for v in [yvar, "delta_p"]:
                sub[v + "_dm"] = sub[v] - sub.groupby(fe_key)[v].transform("mean")
            formula = f"{yvar}_dm ~ {'delta_p_dm'} - 1"
        else:
            formula = f"{yvar} ~ delta_p"
        for cluster, cvar in [("contract", "market_id"), ("day", "d_str")]:
            m = smf.ols(formula, data=sub).fit(
                cov_type="cluster", cov_kwds={"groups": sub[cvar]}
            )
            coef = m.params.get("delta_p_dm", m.params.get("delta_p"))
            t = m.tvalues.get("delta_p_dm", m.tvalues.get("delta_p"))
            results.append(
                {
                    "spec": label,
                    "cluster": cluster,
                    "fe": fe,
                    "gamma": float(coef),
                    "t_stat": float(t),
                    "r2": float(m.rsquared),
                    "n": int(m.nobs),
                    "n_contracts": sub["market_id"].nunique(),
                }
            )

    DAILY_CLASSES = {"close_above_daily", "up_or_down"}
    run(df, "all contracts", fe=True)
    run(df, "all contracts (pooled, no FE)", fe=False)
    for cls, sub in df.groupby("contract_class"):
        fe_key = "ticker" if cls in DAILY_CLASSES else "market_id"
        run(sub, f"class: {cls}" + (" (ticker FE)" if fe_key == "ticker" else ""), fe=True, fe_key=fe_key)
    run(
        df[df["contract_class"].isin(DAILY_CLASSES)],
        "daily classes combined (ticker FE)",
        fe=True,
        fe_key="ticker",
    )
    run(df[~df["is_etf"]], "single names only", fe=True)
    run(df[~df["is_weekend"]], "ex-weekend", fe=True)

    # Placebo: tonight's delta_p vs the FOLLOWING night's gap
    df = df.sort_values(["market_id", "d"])
    df["r_gap_next"] = df.groupby("market_id")["r_gap"].shift(-1)
    plc = df.dropna(subset=["r_gap_next"])
    run(plc, "PLACEBO: next-night gap", yvar="r_gap_next", fe=True)

    return pd.DataFrame(results)


def _perf_stats(daily: pd.Series) -> dict:
    if daily.empty:
        return {}
    equity = (1 + daily).cumprod()
    peak = equity.cummax()
    dd = equity / peak - 1
    ann = 252
    mu = daily.mean() * ann
    sd = daily.std() * np.sqrt(ann)
    return {
        "n_days": len(daily),
        "total_return": float(equity.iloc[-1] - 1),
        "ann_return": float(mu),
        "ann_vol": float(sd),
        "sharpe": float(mu / sd) if sd > 0 else np.nan,
        "max_drawdown": float(dd.min()),
        "hit_rate": float((daily > 0).mean()),
    }


def pnl_backtest(pairs: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, pd.Series]]:
    """Ticker-level signals -> EW daily portfolio of continuation returns."""
    # aggregate to one signal per ticker-day, liquidity(volume)-weighted
    g = pairs.copy()
    g["w"] = g["volume_usd"].clip(lower=1.0)
    agg = (
        g.groupby(["ticker", "d_next"])
        .apply(
            lambda x: pd.Series(
                {
                    "delta_p": np.average(x["delta_p"], weights=x["w"]),
                    "n_contracts": len(x),
                    "r_gap": x["r_gap"].iloc[0],
                    "r_cont": x["r_cont"].iloc[0],
                }
            ),
            include_groups=False,
        )
        .reset_index()
    )
    summaries = []
    curves: dict[str, pd.Series] = {}
    for theta in THETA_GRID:
        sig = agg[agg["delta_p"].abs() >= theta].copy()
        if sig.empty:
            continue
        sig["side"] = np.sign(sig["delta_p"])
        for leg, ret_col in [("gap (diagnostic)", "r_gap"), ("open->close (realizable)", "r_cont")]:
            sig["pnl"] = sig["side"] * sig[ret_col]
            daily = sig.groupby("d_next")["pnl"].mean().sort_index()
            n_trades = len(sig)
            avg_positions = sig.groupby("d_next").size().mean()
            for cost in COST_BPS_GRID:
                # 2 one-way trades per position per day (in + out)
                net = daily - 2 * cost / 10_000
                stats = _perf_stats(net)
                stats.update(
                    {
                        "leg": leg,
                        "theta": theta,
                        "cost_bps_oneway": cost,
                        "n_trades": n_trades,
                        "avg_positions_per_day": float(avg_positions),
                        "trade_hit_rate": float((sig["pnl"] > 0).mean()),
                    }
                )
                summaries.append(stats)
                if cost == 5:
                    curves[f"{leg} θ={theta} c=5bp"] = (1 + net).cumprod()
    return pd.DataFrame(summaries), curves


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pre-open-only",
        action="store_true",
        help="use only pre-13:30 UTC open-window prints (tradeable variant)",
    )
    args = parser.parse_args()

    pairs = build_pairs(args.pre_open_only)
    if pairs.empty:
        print("❌ No pairs built — check history pull. Aborting.")
        return 1
    pairs.to_parquet(PAIRS_PATH, index=False)
    print(f"Wrote {len(pairs)} pairs -> {PAIRS_PATH}")

    es = event_study(pairs)
    print("\n=== EVENT STUDY ===")
    print(es.to_string(index=False))

    pnl, curves = pnl_backtest(pairs)
    print("\n=== PNL (top rows) ===")
    show_cols = [
        "leg", "theta", "cost_bps_oneway", "ann_return", "sharpe",
        "max_drawdown", "hit_rate", "n_trades", "avg_positions_per_day",
    ]
    print(pnl[show_cols].to_string(index=False))

    with pd.ExcelWriter(XLSX_PATH, engine="openpyxl") as xw:
        es.to_excel(xw, sheet_name="event_study", index=False)
        pnl.to_excel(xw, sheet_name="pnl_grid", index=False)
        pairs.head(50_000).to_excel(xw, sheet_name="pairs_sample", index=False)
        if curves:
            pd.DataFrame(curves).to_excel(xw, sheet_name="equity_curves")
    print(f"\nWrote {XLSX_PATH}")

    # markdown report
    window_label = "pre-13:30 UTC (tradeable)" if args.pre_open_only else "12:30-15:30 UTC (paper)"
    main_fe = es[(es["spec"] == "all contracts") & (es["cluster"] == "contract")]
    plc = es[es["spec"].str.startswith("PLACEBO")]
    lines = [
        f"# Overnight PM → Equity Signal — Backtest {STAMP}",
        "",
        f"Open window: {window_label}. Pairs: {len(pairs)} market-nights, "
        f"{pairs['market_id'].nunique()} contracts, {pairs['ticker'].nunique()} tickers, "
        f"{pairs['d'].min():%Y-%m-%d} → {pairs['d'].max():%Y-%m-%d}.",
        "",
        "## Gate 1 — event study (contract FE)",
        "",
        es.to_markdown(index=False),
        "",
        "## Gate 2 — realizable PnL grid",
        "",
        pnl[show_cols].to_markdown(index=False),
        "",
        "Generated by scripts/backtest_overnight_signal.py",
    ]
    REPORT_PATH.write_text("\n".join(lines))
    print(f"Wrote {REPORT_PATH}")
    if not main_fe.empty:
        row = main_fe.iloc[0]
        print(
            f"\nGATE 1 VERDICT: gamma={row['gamma']:.4f}, t={row['t_stat']:.2f} "
            f"(paper: 0.076). Placebo t={plc['t_stat'].iloc[0]:.2f}"
            if not plc.empty and "t_stat" in plc.columns and not plc["t_stat"].isna().all()
            else ""
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
