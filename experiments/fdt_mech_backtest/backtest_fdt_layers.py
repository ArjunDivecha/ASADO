"""
=============================================================================
SCRIPT NAME: backtest_fdt_layers.py
=============================================================================

Historical backtest of the Fable Daily Trading MECHANICAL layers on the 34
US-listed country ETFs, versus the EW-34 equal-weight benchmark. QuantConnect
cannot run this (the signals live in the ASADO warehouse), so this is a local
replication of the FDT sleeve rules on the loop DB's own historical scores:

  S1  — top-5 equal-weight by combiner_scores_daily (walk-forward ridge; the
        stored history is itself out-of-sample by construction).
  S2  — top-5 equal-weight by the z-averaged slow-diffusion composite
        (SIM_NBR_RET_GAP_63D + GRAPHP_BANK_NBR_RET_GAP_21D +
        GRAPHP_TWOHOP_TRADE_GAP_21D), z-scored cross-sectionally per date.
  BLEND — 2:1 S1:S2 (the FDT book's 30%/15% sleeve ratio, renormalized).

Monthly metronome rebalance at each month-end close; positions held one month.
Signals are lagged one trading day (decide at t close uses scores as-of t-1)
to mirror FDT's actual operation. Costs: 25bp one-way on traded weight (the
house cost law for country ETFs). Benchmark: equal weight of all universe
tickers with valid prices that month, same cost model, monthly rebalanced.

Reports the house six-metric scorecard (Strategy/Benchmark/Net ann. return,
IR, net drawdown, turnover) over Full / 5y / 3y / 1y monthly windows, writes
xlsx + PDF (light mode, cumulative net-return headline chart), and prints the
markdown table.

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    (READ-ONLY, opened briefly: combiner_scores_daily, similarity_features_daily,
     graph_features_pit_daily, etf_prices_daily, etf_t2_map)

OUTPUT FILES (in this experiment directory):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/fdt_mech_backtest/results.xlsx
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/fdt_mech_backtest/report.pdf
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/fdt_mech_backtest/report.png (page render)

VERSION: 1.0  |  LAST UPDATED: 2026-07-09  |  AUTHOR: Fable (Claude) for Arjun

DEPENDENCIES: duckdb, pandas, numpy, matplotlib, openpyxl
USAGE: venv/bin/python experiments/fdt_mech_backtest/backtest_fdt_layers.py
=============================================================================
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
OUT = ROOT / "experiments" / "fdt_mech_backtest"
COST_1WAY = 0.0025  # 25bp one-way, house law
TOP_N = 5
S2_VARS = ["SIM_NBR_RET_GAP_63D", "GRAPHP_BANK_NBR_RET_GAP_21D",
           "GRAPHP_TWOHOP_TRADE_GAP_21D"]


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    con = duckdb.connect(str(ROOT / "Data/loop/asado_loop.duckdb"), read_only=True)
    try:
        comb = con.execute(
            "SELECT date, country, value FROM combiner_scores_daily").df()
        sim = con.execute(
            "SELECT date, country, variable, value FROM similarity_features_daily "
            f"WHERE variable = '{S2_VARS[0]}'").df()
        gph = con.execute(
            "SELECT date, country, variable, value FROM graph_features_pit_daily "
            f"WHERE variable IN ('{S2_VARS[1]}','{S2_VARS[2]}')").df()
        t2map = dict(con.execute(
            "SELECT country, etf_primary FROM etf_t2_map").fetchall())
    finally:
        con.close()
    # full adjusted-close history (loop DB only holds ~1y; fetched via yfinance)
    px = pd.read_parquet(OUT / "etf_prices_full.parquet")
    px = px.stack().rename("close").reset_index()
    px.columns = ["date", "ticker", "close"]
    return comb, pd.concat([sim, gph]), px, t2map


def month_end_dates(idx: pd.DatetimeIndex) -> pd.DatetimeIndex:
    s = pd.Series(idx, index=idx)
    return pd.DatetimeIndex(s.groupby([idx.year, idx.month]).max().values)


def run() -> None:
    comb, s2raw, px, t2map = load_inputs()
    for df in (comb, s2raw, px):
        df["date"] = pd.to_datetime(df["date"])

    px_wide = px.pivot_table(index="date", columns="ticker", values="close").sort_index()
    universe = sorted(set(t2map.values()) & set(px_wide.columns))
    px_wide = px_wide[universe]

    # signal panels in ticker space, one row per date
    comb["ticker"] = comb["country"].map(t2map)
    s1 = comb.dropna(subset=["ticker"]).pivot_table(
        index="date", columns="ticker", values="value")

    s2raw["ticker"] = s2raw["country"].map(t2map)
    s2p = s2raw.dropna(subset=["ticker"]).pivot_table(
        index="date", columns="ticker", values="value", aggfunc="mean")
    # z-average the three components cross-sectionally per date
    zparts = []
    for v in S2_VARS:
        part = s2raw[s2raw["variable"] == v].pivot_table(
            index="date", columns="ticker", values="value")
        zparts.append(part.sub(part.mean(axis=1), axis=0)
                          .div(part.std(axis=1), axis=0))
    s2 = sum(z.reindex_like(zparts[0]) for z in zparts) / len(zparts)

    rebal = month_end_dates(px_wide.index)
    daily_ret = px_wide.pct_change()

    def build_weights(scores: pd.DataFrame) -> pd.DataFrame:
        rows = {}
        for d in rebal:
            avail = [t for t in universe if pd.notna(px_wide.loc[d, t])]
            sc_dates = scores.index[scores.index < d]  # one-day-lag PIT guard
            if len(sc_dates) == 0:
                continue
            sc = scores.loc[sc_dates[-1], [t for t in avail if t in scores.columns]].dropna()
            if len(sc) < TOP_N * 2:  # need a real cross-section to rank
                continue
            top = sc.nlargest(TOP_N).index
            rows[d] = pd.Series(1.0 / TOP_N, index=top)
        return pd.DataFrame(rows).T.reindex(columns=universe).fillna(0.0)

    def build_ew() -> pd.DataFrame:
        rows = {}
        for d in rebal:
            avail = [t for t in universe if pd.notna(px_wide.loc[d, t])]
            rows[d] = pd.Series(1.0 / len(avail), index=avail)
        return pd.DataFrame(rows).T.reindex(columns=universe).fillna(0.0)

    def monthly_returns(w: pd.DataFrame) -> pd.Series:
        """Return of the portfolio held from each rebalance date to the next."""
        out, turn = {}, {}
        dates = w.index
        prev = pd.Series(0.0, index=universe)
        for i, d in enumerate(dates[:-1]):
            nxt = dates[i + 1]
            seg = daily_ret.loc[(daily_ret.index > d) & (daily_ret.index <= nxt)]
            gross = (w.loc[d] * ((1 + seg.fillna(0)).prod() - 1)).sum()
            traded = (w.loc[d] - prev).abs().sum()
            out[nxt] = gross - traded * COST_1WAY
            turn[nxt] = traded
            # drift weights to next rebalance for turnover accounting
            drift = w.loc[d] * (1 + seg.fillna(0)).prod()
            prev = drift / drift.sum() if drift.sum() > 0 else w.loc[d]
        r = pd.Series(out).sort_index()
        r.attrs["turnover"] = pd.Series(turn).sort_index()
        return r

    w_s1, w_s2, w_ew = build_weights(s1), build_weights(s2), build_ew()
    common = w_s1.index.intersection(w_s2.index)
    w_s1, w_s2 = w_s1.loc[common], w_s2.loc[common]
    w_bl = (2 * w_s1 + w_s2) / 3
    w_ew = w_ew.loc[w_ew.index.intersection(common)]

    rets = {name: monthly_returns(w) for name, w in
            [("S1 combiner top-5", w_s1), ("S2 slow-diffusion top-5", w_s2),
             ("Blend 2:1", w_bl), ("EW benchmark", w_ew)]}

    bench = rets["EW benchmark"]

    def six_metrics(r: pd.Series, window_months: int | None) -> dict:
        rr, bb = r.align(bench, join="inner")
        if window_months:
            rr, bb = rr.iloc[-window_months:], bb.iloc[-window_months:]
        yrs = len(rr) / 12
        ann = lambda x: (1 + x).prod() ** (1 / yrs) - 1
        active = rr - bb
        cumgap = (1 + rr).cumprod() - (1 + bb).cumprod()
        dd = (cumgap - cumgap.cummax()).min()
        ir = active.mean() / active.std() * np.sqrt(12) if active.std() > 0 else np.nan
        tv = r.attrs["turnover"].reindex(rr.index).mean() * 12
        return {"Strategy Return (ann.)": ann(rr), "Benchmark Return (ann.)": ann(bb),
                "Net Return (ann.)": ann(rr) - ann(bb), "Strategy IR": ir,
                "Net Drawdown": dd, "Turnover (ann.)": tv}

    windows = {"Full": None, "5y": 60, "3y": 36, "1y": 12}
    tables = {name: pd.DataFrame({wn: six_metrics(r, wm) for wn, wm in windows.items()}).T
              for name, r in rets.items() if name != "EW benchmark"}

    # ---- outputs ----
    OUT.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(OUT / "results.xlsx") as xl:
        for name, t in tables.items():
            t.to_excel(xl, sheet_name=name.replace(':', '-')[:30])
        pd.DataFrame({n: r for n, r in rets.items()}).to_excel(xl, sheet_name="monthly_returns")

    fig, axes = plt.subplots(2, 1, figsize=(11, 8.5),
                             gridspec_kw={"height_ratios": [3, 2]})
    fig.patch.set_facecolor("white")
    for name in ["S1 combiner top-5", "S2 slow-diffusion top-5", "Blend 2:1"]:
        rr, bb = rets[name].align(bench, join="inner")
        gap = (1 + rr).cumprod() - (1 + bb).cumprod()
        axes[0].plot(gap.index, gap.values * 100, label=name, linewidth=1.4)
    axes[0].axhline(0, color="gray", linewidth=0.8)
    axes[0].set_title("Cumulative net return vs EW-34 (net of 25bp one-way costs)")
    axes[0].set_ylabel("cumulative gap, %")
    axes[0].legend()
    axes[0].grid(alpha=0.3)
    for name in ["Blend 2:1", "EW benchmark"]:
        r = rets[name]
        axes[1].plot(r.index, (1 + r).cumprod(), label=name, linewidth=1.4)
    axes[1].set_yscale("log")
    axes[1].set_title("Cumulative wealth (log)")
    axes[1].legend()
    axes[1].grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "report.pdf")
    fig.savefig(OUT / "report.png", dpi=160)

    for name, t in tables.items():
        print(f"\n### {name}")
        print(t.to_markdown(floatfmt=".2%"))
    print(f"\nfirst month: {bench.index.min():%Y-%m}, last: {bench.index.max():%Y-%m}, "
          f"n={len(common)} rebalances")


if __name__ == "__main__":
    run()
