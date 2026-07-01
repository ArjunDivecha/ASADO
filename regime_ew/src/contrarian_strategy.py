from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from regime.src.data_loader import load_country_returns


RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"
STRATEGY_DIR = RESULTS_DIR / "contrarian_strategy"


def ensure_strategy_dirs() -> None:
    (STRATEGY_DIR / "figures").mkdir(parents=True, exist_ok=True)


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        val = float(obj)
        return None if not np.isfinite(val) else val
    if isinstance(obj, pd.Timestamp):
        return obj.isoformat()
    return str(obj)


def load_strategy_panel(signal_path: Path | None = None) -> pd.DataFrame:
    if signal_path is None:
        signal_path = RESULTS_DIR / "ew_signals.parquet"
    signals = pd.read_parquet(signal_path)
    signals = signals[["date", "country", "P_adverse", "dP_adverse"]].copy()
    signals["date"] = pd.to_datetime(signals["date"]).dt.to_period("M").dt.to_timestamp()

    returns = load_country_returns(("1MRet", "3MRet"))
    returns["date"] = pd.to_datetime(returns["date"]).dt.to_period("M").dt.to_timestamp()
    r1 = (
        returns[returns["horizon"] == "1MRet"][["date", "country", "ret"]]
        .rename(columns={"ret": "fwd_ret_1m"})
        .dropna(subset=["fwd_ret_1m"])
    )
    r3 = (
        returns[returns["horizon"] == "3MRet"][["date", "country", "ret"]]
        .rename(columns={"ret": "fwd_ret_3m"})
        .dropna(subset=["fwd_ret_3m"])
    )
    panel = signals.merge(r1, on=["date", "country"], how="inner").merge(
        r3, on=["date", "country"], how="left"
    )
    return panel.sort_values(["date", "country"]).reset_index(drop=True)


def add_time_series_percentile(
    panel: pd.DataFrame,
    signal_col: str = "P_adverse",
    min_history: int = 24,
) -> pd.DataFrame:
    out = panel.copy()
    pct_values = []
    for _, g in out.sort_values(["country", "date"]).groupby("country", sort=False):
        hist: list[float] = []
        country_pct = []
        for val in g[signal_col].astype(float).values:
            if len(hist) < min_history or not np.isfinite(val):
                country_pct.append(np.nan)
            else:
                arr = np.asarray(hist, dtype=float)
                country_pct.append(float(np.mean(arr <= val)))
            if np.isfinite(val):
                hist.append(float(val))
        pct_values.extend(country_pct)
    out = out.sort_values(["country", "date"]).copy()
    out[f"{signal_col}_ts_pct"] = pct_values
    return out.sort_values(["date", "country"]).reset_index(drop=True)


def _equal_leg_weights(g: pd.DataFrame, long_mask: pd.Series, short_mask: pd.Series) -> pd.DataFrame:
    rows = []
    longs = g.loc[long_mask, "country"].tolist()
    shorts = g.loc[short_mask, "country"].tolist()
    if longs:
        lw = 1.0 / len(longs)
        rows.extend({"date": g["date"].iloc[0], "country": c, "weight": lw} for c in longs)
    if shorts:
        sw = -1.0 / len(shorts)
        rows.extend({"date": g["date"].iloc[0], "country": c, "weight": sw} for c in shorts)
    return pd.DataFrame(rows)


def cross_sectional_weights(panel: pd.DataFrame, q: float = 0.25, long_only: bool = False) -> pd.DataFrame:
    frames = []
    for _, g in panel.groupby("date", sort=True):
        g = g.dropna(subset=["P_adverse"]).copy()
        if len(g) < 8:
            continue
        pct = g["P_adverse"].rank(pct=True, method="average")
        long_mask = pct >= 1.0 - q
        short_mask = pd.Series(False, index=g.index) if long_only else pct <= q
        w = _equal_leg_weights(g, long_mask, short_mask)
        if not w.empty:
            frames.append(w)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["date", "country", "weight"])


def time_series_weights(
    panel: pd.DataFrame,
    q: float = 0.25,
    long_only: bool = False,
    min_history: int = 24,
) -> pd.DataFrame:
    p = add_time_series_percentile(panel, min_history=min_history)
    pct_col = "P_adverse_ts_pct"
    frames = []
    for _, g in p.groupby("date", sort=True):
        g = g.dropna(subset=[pct_col]).copy()
        if len(g) < 8:
            continue
        long_mask = g[pct_col] >= 1.0 - q
        short_mask = pd.Series(False, index=g.index) if long_only else g[pct_col] <= q
        if long_mask.sum() == 0 or (not long_only and short_mask.sum() == 0):
            continue
        w = _equal_leg_weights(g, long_mask, short_mask)
        if not w.empty:
            frames.append(w)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=["date", "country", "weight"])


def equal_weight_benchmark(panel: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for _, g in panel.groupby("date", sort=True):
        countries = g.dropna(subset=["fwd_ret_1m"])["country"].tolist()
        if not countries:
            continue
        w = 1.0 / len(countries)
        frames.append(pd.DataFrame({"date": g["date"].iloc[0], "country": countries, "weight": w}))
    return pd.concat(frames, ignore_index=True)


def evaluate_weights(
    panel: pd.DataFrame,
    weights: pd.DataFrame,
    name: str,
    cost_bps: tuple[float, ...] = (0.0, 5.0, 10.0, 25.0),
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if weights.empty:
        raise ValueError(f"No weights generated for {name}")
    merged = weights.merge(panel[["date", "country", "fwd_ret_1m"]], on=["date", "country"], how="left")
    gross = (
        merged.assign(contrib=merged["weight"] * merged["fwd_ret_1m"])
        .groupby("date", as_index=False)["contrib"]
        .sum()
        .rename(columns={"contrib": "gross_ret"})
    )

    wp = (
        weights.pivot_table(index="date", columns="country", values="weight", aggfunc="sum")
        .sort_index()
        .fillna(0.0)
    )
    turnover = wp.diff().abs().sum(axis=1)
    if len(turnover):
        turnover.iloc[0] = wp.iloc[0].abs().sum()
    gross_exposure = wp.abs().sum(axis=1)
    net_exposure = wp.sum(axis=1)

    returns = gross.merge(turnover.rename("turnover").reset_index(), on="date", how="left")
    returns = returns.merge(gross_exposure.rename("gross_exposure").reset_index(), on="date", how="left")
    returns = returns.merge(net_exposure.rename("net_exposure").reset_index(), on="date", how="left")
    returns["strategy"] = name
    for bps in cost_bps:
        col = "gross_ret" if bps == 0 else f"net_ret_{int(bps)}bps"
        returns[col] = returns["gross_ret"] - returns["turnover"] * (bps / 10000.0)

    summary = {"strategy": name, "start": returns["date"].min(), "end": returns["date"].max()}
    for bps in cost_bps:
        ret_col = "gross_ret" if bps == 0 else f"net_ret_{int(bps)}bps"
        prefix = "gross" if bps == 0 else f"net_{int(bps)}bps"
        summary.update(_performance_metrics(returns[ret_col], prefix))
    summary.update(
        {
            "months": int(len(returns)),
            "avg_turnover": float(returns["turnover"].mean()),
            "median_turnover": float(returns["turnover"].median()),
            "avg_gross_exposure": float(returns["gross_exposure"].mean()),
            "avg_net_exposure": float(returns["net_exposure"].mean()),
        }
    )
    return returns, summary


def _performance_metrics(r: pd.Series, prefix: str) -> dict[str, float | int]:
    r = r.dropna().astype(float)
    if r.empty:
        return {}
    wealth = (1.0 + r).cumprod()
    peak = wealth.cummax()
    dd = wealth / peak - 1.0
    n = len(r)
    ann_return = float(wealth.iloc[-1] ** (12.0 / n) - 1.0)
    ann_vol = float(r.std(ddof=0) * np.sqrt(12))
    sharpe = float(r.mean() / r.std(ddof=0) * np.sqrt(12)) if r.std(ddof=0) > 0 else np.nan
    return {
        f"{prefix}_total_return": float(wealth.iloc[-1] - 1.0),
        f"{prefix}_ann_return": ann_return,
        f"{prefix}_ann_vol": ann_vol,
        f"{prefix}_sharpe": sharpe,
        f"{prefix}_max_drawdown": float(dd.min()),
        f"{prefix}_hit_rate": float((r > 0).mean()),
        f"{prefix}_best_month": float(r.max()),
        f"{prefix}_worst_month": float(r.min()),
    }


def run_contrarian_backtest() -> dict[str, Any]:
    ensure_strategy_dirs()
    panel = load_strategy_panel()
    specs = [
        ("TS_Q25_LS_P", time_series_weights(panel, q=0.25, long_only=False), "Time-series top/bottom quartile long-short"),
        ("TS_Q25_LONG_P", time_series_weights(panel, q=0.25, long_only=True), "Time-series top-quartile long-only"),
        ("XS_Q25_LS_P", cross_sectional_weights(panel, q=0.25, long_only=False), "Cross-sectional top/bottom quartile long-short"),
        ("XS_Q20_LS_P", cross_sectional_weights(panel, q=0.20, long_only=False), "Cross-sectional top/bottom quintile long-short"),
        ("XS_Q25_LONG_P", cross_sectional_weights(panel, q=0.25, long_only=True), "Cross-sectional top-quartile long-only"),
        ("EW_UNIVERSE", equal_weight_benchmark(panel), "Equal-weight available-country benchmark"),
    ]

    return_frames = []
    summary_rows = []
    for name, weights, description in specs:
        weights.to_parquet(STRATEGY_DIR / f"weights_{name}.parquet", index=False)
        rets, summary = evaluate_weights(panel, weights, name)
        summary["description"] = description
        rets.to_parquet(STRATEGY_DIR / f"returns_{name}.parquet", index=False)
        return_frames.append(rets)
        summary_rows.append(summary)

    returns_all = pd.concat(return_frames, ignore_index=True)
    summary = pd.DataFrame(summary_rows)
    returns_all.to_parquet(STRATEGY_DIR / "strategy_returns.parquet", index=False)
    summary.to_csv(STRATEGY_DIR / "strategy_summary.csv", index=False)

    payload = {
        "status": "complete",
        "panel_rows": int(len(panel)),
        "panel_start": panel["date"].min(),
        "panel_end": panel["date"].max(),
        "countries": int(panel["country"].nunique()),
        "strategies": summary_rows,
        "notes": [
            "Uses walk-forward OOS P_adverse from regime_ew/results/ew_signals.parquet.",
            "Monthly weights at date t are paired with ASADO 1MRet@t, matching regime build_forward_returns convention.",
            "Costs are simple one-way bps times monthly absolute weight turnover.",
            "TS variants use prior-only 24-month country history to classify high/low P_adverse.",
        ],
    }
    (STRATEGY_DIR / "strategy_manifest.json").write_text(json.dumps(payload, indent=2, default=_json_default))
    write_strategy_report(summary, payload)
    plot_cumulative_returns(returns_all)
    return payload


def write_strategy_report(summary: pd.DataFrame, payload: dict[str, Any]) -> None:
    display_cols = [
        "strategy",
        "description",
        "months",
        "gross_total_return",
        "gross_ann_return",
        "gross_ann_vol",
        "gross_sharpe",
        "gross_max_drawdown",
        "net_10bps_ann_return",
        "net_10bps_sharpe",
        "net_25bps_ann_return",
        "net_25bps_sharpe",
        "avg_turnover",
        "avg_gross_exposure",
    ]
    s = summary[display_cols].copy()
    percent_cols = [c for c in s.columns if any(k in c for k in ["return", "vol", "drawdown"])]
    for col in percent_cols:
        s[col] = s[col].map(lambda x: f"{x:.2%}")
    for col in ["gross_sharpe", "net_10bps_sharpe", "net_25bps_sharpe", "avg_turnover", "avg_gross_exposure"]:
        s[col] = s[col].map(lambda x: f"{x:.2f}")

    lines = [
        "# Contrarian Per-Country Regime Strategy Backtest",
        "",
        "## Setup",
        "",
        "- Signal: walk-forward OOS `P_adverse` from the per-country HMM regime test.",
        "- Interpretation: contrarian; buy countries when the model says their adverse-regime probability is high.",
        "- Return convention: monthly weights at date `t` are paired with ASADO `1MRet@t`, matching `build_forward_returns`.",
        "- Costs: simple one-way bps times monthly absolute weight turnover.",
        "- Sample: "
        f"{pd.Timestamp(payload['panel_start']).date()} to {pd.Timestamp(payload['panel_end']).date()}, "
        f"{payload['countries']} countries.",
        "",
        "## Results",
        "",
        s.to_markdown(index=False),
        "",
        "## Read",
        "",
        "The cleanest production-shaped version is the time-series quartile long/short (`TS_Q25_LS_P`): it compares each country's `P_adverse` to its own prior 24-month history before trading. The cross-sectional variants are useful diagnostics, but less conceptually clean because HMM posterior probabilities are fitted separately by country.",
        "",
        "## Artifacts",
        "",
        "- `strategy_manifest.json`",
        "- `strategy_summary.csv`",
        "- `strategy_returns.parquet`",
        "- `weights_*.parquet` and `returns_*.parquet`",
        "- `figures/cumulative_returns.pdf`",
        "",
    ]
    (STRATEGY_DIR / "STRATEGY_RESULTS.md").write_text("\n".join(lines))


def plot_cumulative_returns(returns: pd.DataFrame) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    preferred = ["TS_Q25_LS_P", "XS_Q25_LS_P", "XS_Q20_LS_P", "EW_UNIVERSE"]
    for name in preferred:
        g = returns[returns["strategy"] == name].sort_values("date")
        if g.empty:
            continue
        wealth = (1.0 + g["gross_ret"].fillna(0.0)).cumprod()
        ax.plot(g["date"], wealth, label=name)
    ax.axhline(1.0, color="#555555", lw=0.8)
    ax.set_title("Contrarian P(adverse) strategy cumulative gross returns")
    ax.set_ylabel("Growth of $1")
    ax.legend()
    fig.tight_layout()
    fig.savefig(STRATEGY_DIR / "figures" / "cumulative_returns.pdf")
    plt.close(fig)

