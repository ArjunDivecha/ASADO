"""
=============================================================================
SCRIPT NAME: scripts/strategy/analogs/report.py
=============================================================================

INPUT FILES:
- Data/strategy/analogs/v1/signals.parquet
- Data/strategy/analogs/v1/backtest.parquet
- Data/strategy/analogs/v1/baselines.parquet
- Data/strategy/analogs/v1/analog_matches.parquet

OUTPUT FILES:
- Data/strategy/analogs/v1/Country_Forecasts.xlsx   — T2_Optimizer-style wide
    workbook with sheets:
      Scores       — rows = decision dates, cols = 34 countries, values = score
      Ranks        — same shape, values = within-date rank (1=best)
      Diagnostics  — per-date: n_countries_scored, mean_top_sim, top1, top7
- Data/strategy/analogs/v1/diagnostics.pdf          — equity curves + face
    validity plots (matplotlib, light mode)

VERSION: 1.0
LAST UPDATED: 2026-04-19
AUTHOR: Arjun Divecha (with Claude)

DESCRIPTION:
Builds the user-facing Country_Forecasts.xlsx in a layout matching the T2
Optimizer convention (wide, dates × countries) and a diagnostics PDF.

DEPENDENCIES:
- pandas, numpy, matplotlib, openpyxl, pyarrow

USAGE:
  python scripts/strategy/analogs/report.py
=============================================================================
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from scripts.strategy.analogs import config as C  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Light mode (per project CLAUDE.md): explicit white backgrounds, dark text.
plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
    "axes.edgecolor": "black",
    "axes.labelcolor": "black",
    "text.color": "black",
    "xtick.color": "black",
    "ytick.color": "black",
    "axes.grid": True,
    "grid.color": "#dddddd",
    "grid.linestyle": "-",
    "grid.linewidth": 0.5,
})


def load_all() -> dict[str, pd.DataFrame]:
    sig = pd.read_parquet(C.SIGNALS_PARQUET)
    sig["date"] = pd.to_datetime(sig["date"])
    bt = pd.read_parquet(C.BACKTEST_PARQUET)
    bt["realized_date"] = pd.to_datetime(bt["realized_date"])
    bl = pd.read_parquet(C.BASELINES_PARQUET)
    bl["date"] = pd.to_datetime(bl["date"])
    matches = pd.read_parquet(C.ANALOG_MATCHES_PARQUET)
    matches["date"] = pd.to_datetime(matches["date"])
    return {"signals": sig, "backtest": bt, "baselines": bl, "matches": matches}


def write_xlsx(d: dict[str, pd.DataFrame]) -> Path:
    sig = d["signals"]
    matches = d["matches"]

    scores_wide = sig.pivot(index="date", columns="country", values="score")
    ranks_wide = sig.pivot(index="date", columns="country", values="rank")

    # Order columns canonically (T2 list order).
    scores_wide = scores_wide.reindex(columns=C.T2_COUNTRIES)
    ranks_wide = ranks_wide.reindex(columns=C.T2_COUNTRIES)

    # Diagnostics per decision date.
    n_scored = sig.dropna(subset=["score"]).groupby("date").size().rename("n_countries_scored")
    top_sim = matches.groupby("date")["cosine_similarity"].agg(
        mean_top_sim="mean", max_top_sim="max", min_top_sim="min",
    )
    top1_score = sig.groupby("date")["score"].max().rename("top1_score")
    # Mean of top-7 scores (across countries, not analogs).
    top7_score = (
        sig.dropna(subset=["score"])
        .sort_values(["date", "score"], ascending=[True, False])
        .groupby("date")
        .head(C.TOP_N)
        .groupby("date")["score"]
        .mean()
        .rename("top7_mean_score")
    )
    # Top-7 holdings as a semicolon list.
    top7_names = (
        sig.dropna(subset=["score"])
        .sort_values(["date", "score"], ascending=[True, False])
        .groupby("date")
        .head(C.TOP_N)
        .groupby("date")["country"]
        .apply(lambda s: ";".join(sorted(s)))
        .rename("top7_names")
    )

    diag = pd.concat([n_scored, top_sim, top1_score, top7_score, top7_names], axis=1).reset_index()

    out_path = C.COUNTRY_FORECASTS_XLSX
    with pd.ExcelWriter(out_path, engine="openpyxl") as xw:
        scores_wide.to_excel(xw, sheet_name="Scores")
        ranks_wide.to_excel(xw, sheet_name="Ranks")
        diag.to_excel(xw, sheet_name="Diagnostics", index=False)
    logger.info("Wrote %s", out_path)
    return out_path


def annualized_stats(series: pd.Series) -> dict[str, float]:
    s = series.dropna()
    if s.empty:
        return {"ann_return": float("nan"), "ann_vol": float("nan"),
                "sharpe": float("nan"), "n_months": 0}
    ann_ret = (1 + s).prod() ** (12 / len(s)) - 1
    ann_vol = s.std() * np.sqrt(12)
    sharpe = ann_ret / ann_vol if ann_vol > 0 else float("nan")
    return {"ann_return": float(ann_ret), "ann_vol": float(ann_vol),
            "sharpe": float(sharpe), "n_months": int(len(s))}


def write_pdf(d: dict[str, pd.DataFrame]) -> Path:
    bt = d["backtest"].set_index("realized_date").sort_index()
    bl = d["baselines"].copy()
    ew = bl[bl["model"] == "equal_weight"].set_index("date")["return_gross"].sort_index()

    # Align EW to the analog window for fair comparison.
    ew_aligned = ew[ew.index.isin(bt.index)]

    analog_curve = (1 + bt["return_gross"]).cumprod()
    ew_curve = (1 + ew_aligned).cumprod()

    out_pdf = C.STRATEGY_DIR / "diagnostics.pdf"
    fig, axes = plt.subplots(3, 1, figsize=(10, 12))

    ax = axes[0]
    ax.plot(analog_curve.index, analog_curve.values, label=f"analog_top{C.TOP_N}", color="#1f77b4")
    ax.plot(ew_curve.index, ew_curve.values, label="equal_weight (aligned)", color="#888888", linestyle="--")
    ax.set_title("Cumulative gross return — analog vs equal-weight")
    ax.set_ylabel("Growth of $1")
    ax.legend()

    ax = axes[1]
    rolling_excess = (bt["return_gross"] - ew_aligned).rolling(12).mean() * 12
    ax.plot(rolling_excess.index, rolling_excess.values * 100, color="#2ca02c")
    ax.axhline(C.BENCHMARK_HURDLE_EXCESS_ANNUAL * 100, color="red", linestyle=":",
               label=f"hurdle +{C.BENCHMARK_HURDLE_EXCESS_ANNUAL * 100:.0f}%")
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_title("Rolling 12-month excess return (annualized, %)")
    ax.set_ylabel("Excess vs EW (%)")
    ax.legend()

    ax = axes[2]
    sims = d["matches"].groupby("date")["cosine_similarity"].mean()
    ax.plot(sims.index, sims.values, color="#9467bd")
    ax.set_title("Mean top-k cosine similarity by decision date")
    ax.set_ylabel("Mean top-k cosine sim")
    ax.set_ylim(-1, 1)

    fig.tight_layout()
    fig.savefig(out_pdf, format="pdf")
    plt.close(fig)
    logger.info("Wrote %s", out_pdf)
    return out_pdf


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    args = ap.parse_args()
    _ = args
    C.ensure_dirs()
    d = load_all()
    write_xlsx(d)
    write_pdf(d)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
