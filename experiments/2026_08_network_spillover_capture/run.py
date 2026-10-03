#!/usr/bin/env python3
"""Focused E1 capture test for the frozen network_spillover ranks.

This is an experiment runner, not a pipeline step. It reads frozen parquets,
the read-only Global Data Mart futures panel, and downloads only the ETF OHLC
data needed for the expression measurement. It never opens either ASADO
DuckDB database and never writes to pipeline-owned directories.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
EXP = ROOT / "experiments/2026_08_network_spillover_capture"
SCRATCH = ROOT / "Data/work/experiments/network_spillover_capture"
RESULTS = EXP / "results"
SNAP = ROOT / "Data/work/experiments/flip_autopsy/snapshot_2026_07_13"
GDM_FUTURES_LOADER = Path(
    "/Users/arjundivecha/Dropbox/AAA Backup/A Working/Global Data Mart"
    "/sources/futures/loader"
)

sys.path.insert(0, str(ROOT))
from scripts.harness.evaluate_signal import (  # noqa: E402
    HARNESS_VERSION,
    effective_daily_lag_days,
    nw_tstat,
)


RANK_FAMILIES = ("graph_bank", "graph_twohop", "leadlag", "twins")
FUTURES_MAP = {
    "France": "CF",
    "Germany": "GX",
    "Hong Kong": "HI",
    "Japan": "NK",
    "U.K.": "Z",
    "U.S.": "ES",
}
COST_CASES_BPS = (2.5, 5.0, 10.0, 25.0)
HOLD_DAYS = (1, 5, 21)
ETF_MAP_PATH = ROOT / "config/etf_t2_map.json"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_signal() -> pd.DataFrame:
    """Use the existing nightly rank rows; only deterministic aggregation is new."""
    df = pd.read_parquet(SNAP / "family_ranks_daily.parquet")
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["family"].isin(RANK_FAMILIES)].copy()
    # rank=1 is strongest long. Normalize within each existing family/date so
    # a 16-country family and a 34-country family have comparable rank strength.
    den = (df["universe_n"] - 1).replace(0, np.nan)
    df["rank_strength"] = (df["universe_n"] - df["rank"]) / den
    out = (
        df.groupby(["date", "country"], as_index=False)
        .agg(value=("rank_strength", "mean"), member_count=("family", "nunique"))
    )
    out = out[out["member_count"] >= 2].copy()
    out["value"] = out["value"].astype(float)
    return out[["date", "country", "value"]].sort_values(["date", "country"])


def load_local_returns() -> pd.DataFrame:
    """Convert ASADO's forward-labelled daily return rows to close-labelled rows.

    The frozen snapshot follows the repo convention used by the prior corrected
    daily tests: shifting one row by country labels the realized return at its
    next available close, and zero weekend placeholders are excluded.
    """
    df = pd.read_parquet(SNAP / "t2_1dret_daily.parquet")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["country", "date"])
    df["return"] = df.groupby("country")["value"].shift(1)
    df = df.dropna(subset=["return"])
    df = df[df["return"] != 0.0]
    return df[["date", "country", "return"]].sort_values(["country", "date"])


def load_futures_returns() -> pd.DataFrame:
    """Load roll-aware generic-2 futures returns and backward-label them."""
    sys.path.insert(0, str(GDM_FUTURES_LOADER))
    from futures_data import build_returns, load_curves  # type: ignore

    roots = list(FUTURES_MAP.values())
    curves = load_curves(roots=roots, contracts=[2])
    fwd = build_returns(curves=curves, contract=2)
    long = fwd.rename_axis("date").reset_index().melt(
        id_vars="date", var_name="root", value_name="fwd_return"
    )
    long["date"] = pd.to_datetime(long["date"])
    long = long.sort_values(["root", "date"])
    # build_returns[t] is t -> t+1. Label that realized move at t+1, matching
    # the harness's backward-labeled return panel.
    long["return"] = long.groupby("root")["fwd_return"].shift(1)
    inv = {root: country for country, root in FUTURES_MAP.items()}
    long["country"] = long["root"].map(inv)
    return long.dropna(subset=["return", "country"])[
        ["date", "country", "return"]
    ].sort_values(["country", "date"])


def load_etf_ohlc() -> tuple[pd.DataFrame, dict[str, str]]:
    """Fetch adjusted ETF OHLC once into the experiment scratch area."""
    import yfinance as yf

    cfg = json.loads(ETF_MAP_PATH.read_text())
    tickers = {country: spec["primary"] for country, spec in cfg["map"].items()}
    cache = SCRATCH / "etf_ohlc.parquet"
    if cache.exists():
        raw = pd.read_parquet(cache)
    else:
        raw = yf.download(
            sorted(tickers.values()),
            start="2004-01-01",
            end="2026-08-24",
            auto_adjust=True,
            actions=False,
            progress=False,
            threads=True,
            timeout=60,
            group_by="column",
        )
        if raw is None or raw.empty:
            raise RuntimeError("yfinance returned no ETF OHLC data")
        if not isinstance(raw.columns, pd.MultiIndex):
            raise RuntimeError(f"unexpected yfinance columns: {list(raw.columns)}")
        frames = []
        for field in ("Open", "Close"):
            if field not in raw.columns.get_level_values(0):
                raise RuntimeError(f"ETF OHLC missing {field}")
        for ticker in sorted(tickers.values()):
            if ("Open", ticker) not in raw.columns or ("Close", ticker) not in raw.columns:
                raise RuntimeError(f"ETF OHLC missing ticker {ticker}")
            x = raw.loc[:, [("Open", ticker), ("Close", ticker)]].copy()
            x.columns = ["open", "close"]
            x = x.reset_index().rename(columns={"Date": "date"})
            x["ticker"] = ticker
            frames.append(x)
        raw = pd.concat(frames, ignore_index=True)
        raw["date"] = pd.to_datetime(raw["date"])
        SCRATCH.mkdir(parents=True, exist_ok=True)
        raw.to_parquet(cache, index=False)
    raw["date"] = pd.to_datetime(raw["date"])
    raw = raw.sort_values(["ticker", "date"])
    inv = {ticker: country for country, ticker in tickers.items()}
    raw["country"] = raw["ticker"].map(inv)
    raw["close_return"] = raw.groupby("ticker")["close"].pct_change()
    # Open->close is already a same-session realized return; its date label is
    # the session close, so the v4 next-session queue uses the following row.
    raw["open_return"] = raw["close"] / raw["open"] - 1.0
    return raw, tickers


def to_panel(df: pd.DataFrame) -> pd.DataFrame:
    return df.pivot_table(index="date", columns="country", values="return", aggfunc="last").sort_index()


def ann_return(x: pd.Series, periods: int = 252) -> float:
    x = x.dropna()
    if len(x) == 0:
        return float("nan")
    return float((1.0 + x).prod() ** (periods / len(x)) - 1.0)


def sharpe(x: pd.Series, periods: int = 252) -> float:
    x = x.dropna()
    return float(x.mean() / x.std() * np.sqrt(periods)) if len(x) > 1 and x.std() > 0 else float("nan")


def portfolio(signal: pd.DataFrame, returns: pd.DataFrame, hold_days: int, n_top: int, cost_bps: float | None = None) -> dict:
    """Harness-v4 daily portfolio path, adapted only to allow n<14 futures."""
    score = signal.pivot_table(index="date", columns="country", values="value").sort_index()
    cols = score.columns.intersection(returns.columns)
    score = score.reindex(columns=cols)
    returns = returns.reindex(columns=cols)
    ret_dates = list(returns.index)
    ret_values = returns.to_numpy(dtype=float)
    rank_dates = [d for d in score.index if score.loc[d].notna().sum() >= max(2 * n_top, 4)]
    rank_pos = {d: i for i, d in enumerate(rank_dates)}
    col_pos = {c: i for i, c in enumerate(cols)}
    sets: dict[pd.Timestamp, tuple[np.ndarray, np.ndarray]] = {}
    for d in rank_dates:
        vals = score.loc[d].to_numpy(dtype=float)
        valid = np.flatnonzero(np.isfinite(vals))
        order = valid[np.argsort(-vals[valid], kind="stable")]
        sets[d] = (order[:n_top], order[-n_top:])
    top_tranches: list[np.ndarray | None] = [None] * hold_days
    bot_tranches: list[np.ndarray | None] = [None] * hold_days
    pending: dict[int, tuple[np.ndarray, np.ndarray, float, float]] = {}
    rows = []
    for i, d in enumerate(ret_dates):
        if not rank_dates or d < rank_dates[0]:
            continue
        # Orders queued after a rank date execute on the next available return
        # date. Their turnover is charged on that execution date, exactly as in
        # the harness-v4 daily portfolio path.
        turnover_top = turnover_ls = 0.0
        for k, (top, bot, to_top, to_ls) in list(pending.items()):
            top_tranches[k], bot_tranches[k] = top, bot
            turnover_top += to_top
            turnover_ls += to_ls
            pending.pop(k)
        day = ret_values[i]
        top_rs, bot_rs = [], []
        for k in range(hold_days):
            top, bot = top_tranches[k], bot_tranches[k]
            if top is None or bot is None:
                continue
            rt = day[top]
            rb = day[bot]
            rt = rt[np.isfinite(rt)]
            rb = rb[np.isfinite(rb)]
            if len(rt) >= max(2, n_top - 2):
                top_rs.append(float(rt.mean()))
                bot_rs.append(float(rb.mean()) if len(rb) else 0.0)
        ew = day[np.isfinite(day)]
        if top_rs and len(ew) >= max(2 * n_top, 4):
            rows.append({
                "date": d,
                "top": float(np.mean(top_rs)),
                "bottom": float(np.mean(bot_rs)),
                "ew": float(ew.mean()),
                "turnover_top": turnover_top,
                "turnover_ls": turnover_ls,
            })
        if d in rank_pos:
            k = rank_pos[d] % hold_days
            top, bot = sets[d]
            old_top = top_tranches[k]
            old_bot = bot_tranches[k]
            to_top = len(np.setdiff1d(top, old_top, assume_unique=True)) / n_top if old_top is not None else 1.0
            to_bot = len(np.setdiff1d(bot, old_bot, assume_unique=True)) / n_top if old_bot is not None else 1.0
            pending[k] = (top, bot, to_top / hold_days, (to_top + to_bot) / hold_days)

    bt = pd.DataFrame(rows)
    if bt.empty:
        return {"n_days": 0, "error": "no common rank/return dates"}
    active = bt["top"] - bt["ew"]
    ls = bt["top"] - bt["bottom"]
    if cost_bps is not None:
        c = cost_bps / 10000.0
        active = active - bt["turnover_top"] * 2.0 * c
        ls = ls - bt["turnover_ls"] * 2.0 * c
    return {
        "n_days": int(len(bt)),
        "start": str(pd.Timestamp(bt.date.min()).date()),
        "end": str(pd.Timestamp(bt.date.max()).date()),
        "n_top": int(n_top),
        "cost_bps_one_way": cost_bps,
        "gross_top_ann_return": ann_return(bt["top"]),
        "gross_ew_ann_return": ann_return(bt["ew"]),
        "top_excess_ann_return": ann_return(active),
        "top_excess_sharpe": sharpe(active),
        "top_excess_nw_t": nw_tstat(active, max(5, hold_days)),
        "ls_ann_return": ann_return(ls),
        "ls_sharpe": sharpe(ls),
        "ls_nw_t": nw_tstat(ls, max(5, hold_days)),
        "avg_turnover_top_oneway": float(bt["turnover_top"].mean()),
        "avg_turnover_ls_oneway": float(bt["turnover_ls"].mean()),
        "series": bt.assign(active=active, ls=ls),
    }


def run() -> None:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    signal = load_signal()
    local = to_panel(load_local_returns())
    futures = to_panel(load_futures_returns())
    etf, tickers = load_etf_ohlc()
    etf_close = to_panel(
        etf.rename(columns={"close_return": "return"})[["date", "country", "return"]]
        .dropna(subset=["return"])
    )
    etf_open = to_panel(
        etf.rename(columns={"open_return": "return"})[["date", "country", "return"]]
        .dropna(subset=["return"])
    )
    expressions = {
        "local_index": (local, "all T2 names; diagnostic, not directly tradable"),
        "futures": (futures, "six mapped equity-index futures; roll-aware generic-2"),
        "etf_market_open": (etf_open, "next US ETF session open-to-close"),
        "etf_close_to_close": (etf_close, "US ETF close-to-close"),
    }
    lag = effective_daily_lag_days("NETWORK_SPILLOVER_CAPTURE", "graph")
    if lag != 1 or HARNESS_VERSION < 4:
        raise RuntimeError(f"unexpected harness clock: version={HARNESS_VERSION}, lag={lag}")

    rows = []
    series_frames = []
    for expr, (ret, coverage_note) in expressions.items():
        common = signal[signal.country.isin(ret.columns)].copy()
        max_n = int(common.groupby("date")["country"].nunique().max()) if not common.empty else 0
        n_top = 7 if max_n >= 14 else max(2, max_n // 3)
        for hold in HOLD_DAYS:
            for cost in [None, *COST_CASES_BPS]:
                out = portfolio(common, ret, hold, n_top, cost)
                series = out.pop("series", None)
                out.update({
                    "expression": expr,
                    "hold_days": hold,
                    "coverage_max_n": max_n,
                    "coverage_note": coverage_note,
                    "harness_version": HARNESS_VERSION,
                    "lag_days_effective": lag,
                })
                rows.append(out)
                if series is not None:
                    series_frames.append(series.assign(expression=expr, hold_days=hold, cost_bps=cost))

    metrics = pd.DataFrame(rows)
    metrics.to_csv(RESULTS / "metrics.csv", index=False)
    if series_frames:
        pd.concat(series_frames, ignore_index=True).to_parquet(RESULTS / "daily_series.parquet", index=False)

    gross = metrics[metrics["cost_bps_one_way"].isna()].copy()
    # Capture survives only if at least one tradable expression is positive in
    # the gross top-vs-EW result and remains positive at its 10bp diagnostic.
    tradable = gross[gross.expression.isin(["futures", "etf_market_open", "etf_close_to_close"])]
    ten = metrics[metrics["cost_bps_one_way"] == 10.0]
    ten = ten[ten.expression.isin(tradable.expression.unique())]
    gross_pass = bool((tradable["top_excess_ann_return"] > 0).any()) if not tradable.empty else False
    cost_pass = bool((ten["top_excess_ann_return"] > 0).any()) if not ten.empty else False
    surviving = sorted(set(tradable.loc[tradable.top_excess_ann_return > 0, "expression"]))
    surviving_10bp = sorted(set(ten.loc[ten.top_excess_ann_return > 0, "expression"]))
    summary = {
        "experiment": "2026_08_network_spillover_capture",
        "status": "SURVIVES_NARROW_FUTURES_CAPTURE_ONLY" if gross_pass and cost_pass else "PARKED_NO_CAPTURE_SURVIVAL",
        "gross_tradable_positive": gross_pass,
        "positive_at_10bp_diagnostic": cost_pass,
        "surviving_expressions_gross": surviving,
        "surviving_expressions_at_10bp": surviving_10bp,
        "futures_coverage_max_n": int(metrics.loc[metrics.expression == "futures", "coverage_max_n"].max()),
        "deployment_authorized": False,
        "harness_version": HARNESS_VERSION,
        "lag_days_effective": lag,
        "rank_input": str(SNAP / "family_ranks_daily.parquet"),
        "rank_input_sha256": sha256(SNAP / "family_ranks_daily.parquet"),
        "rank_families": list(RANK_FAMILIES),
        "futures_map": FUTURES_MAP,
        "etf_map": tickers,
        "cost_cases_bps_one_way": list(COST_CASES_BPS),
        "hold_days": list(HOLD_DAYS),
        "note": "The re-arm gate is not a deployment gate. Formal re-verdict is conditional on capture survival.",
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    manifest = {
        "rank_input": str(SNAP / "family_ranks_daily.parquet"),
        "rank_input_sha256": summary["rank_input_sha256"],
        "local_input": str(SNAP / "t2_1dret_daily.parquet"),
        "futures_input": str(GDM_FUTURES_LOADER.parent / "data/futures_curves.parquet"),
        "etf_ohlc_cache": str(SCRATCH / "etf_ohlc.parquet"),
        "etf_ohlc_sha256": sha256(SCRATCH / "etf_ohlc.parquet"),
    }
    (RESULTS / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    print("\nHEADLINE GROSS RESULTS")
    print(gross[["expression", "hold_days", "coverage_max_n", "n_days", "top_excess_ann_return", "top_excess_sharpe", "top_excess_nw_t", "ls_sharpe"]].to_string(index=False))
    print("\n10bp EXECUTION DIAGNOSTIC")
    print(ten[["expression", "hold_days", "top_excess_ann_return", "top_excess_sharpe", "ls_sharpe"]].to_string(index=False))


if __name__ == "__main__":
    run()
