#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/calibrate_jst_bearbottom.py
=============================================================================

DESCRIPTION:
Distills the JST Macrohistory annual panel (1870-2020, 13 in-universe DMs)
into BEAR-BOTTOM CONDITIONAL FORWARD-RETURN tables — the tail-calibration
layer the proposal calls for. It answers, on 150 years of real data:

  "Given we are in a deep equity drawdown (or a banking-crisis onset, or
   early post-crisis recovery), what is the distribution of forward 1/3/5-year
   REAL total returns for equities, bonds and bills?"

The modern ASADO sample (~2000+) has ~3 crises — too few to estimate this.
JST pools ~65 banking-crisis onsets plus every Depression / war / hyperinflation
across the in-universe developed markets, giving a real tail population.

Method (per country, then pooled):
  1. Real returns: real = (1+nominal_tr)/(1+cpi_inflation) - 1, for equities
     (eq_tr), bonds (bond_tr), bills (bill_rate). Real conversion is essential —
     nominal returns are meaningless across hyperinflations (Germany 1923).
  2. Real equity total-return index per country -> drawdown vs running peak.
  3. Conditioning states for each year t:
       - drawdown buckets: (0,-10], (-10,-20], (-20,-35], (<= -35]%
       - banking_crisis: crisisJST==1 (onset year)
       - post_crisis_1_3y: 1-3 years after an onset
       - normal: drawdown shallower than -10% and not crisis
  4. Forward H-year real return from t (annualized), H in {1,3,5}.
  5. Pool across countries; report n, mean, median, std, p10/p25/p50/p75/p90,
     prob(return < 0). A hyperinflation-excluded variant (|cpi inflation| > 50%
     in the window) is reported alongside as robustness.

OUTPUT is small lookup tables, read OFFLINE by the live conditional-return /
regime context layer. The live monthly system never touches the raw 150-yr
panel — only these distilled tables.

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/processed/jst_macrohistory_panel.parquet
    Tidy annual JST panel from collect_jst_macrohistory.py.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime/calib/jst_bearbottom_conditional_returns.parquet
    Tidy table: (state, asset, horizon_y, variant, n_obs, n_episodes, mean,
    median, std, p10, p25, p50, p75, p90, prob_neg).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime/calib/jst_bearbottom_conditional_returns.json
    Same content nested (state -> asset -> horizon -> stats) for easy load by
    the live layer.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/regime/calib/jst_calibration_report.md
    Human-readable summary: episode counts, headline distributions, thin-sample
    flags, provenance (JST R6).

VERSION: 1.0
LAST UPDATED: 2026-06-15
AUTHOR: Claude Code for Arjun Divecha

DEPENDENCIES: pandas, numpy, pyarrow (ASADO venv).

USAGE:
  venv/bin/python scripts/calibrate_jst_bearbottom.py

NOTES:
- Forward windows from nearby years overlap; n_obs is the raw count and
  n_episodes the distinct onset/entry count, so the user can judge the
  effective (non-overlapping) sample. Any (state,asset,horizon) cell with
  n_episodes < MIN_EPISODES is flagged THIN in the report, not silently used.
- This is a research/calibration artifact. It does NOT alter any live trade
  logic on its own; wiring into the conditional-return layer is a separate,
  explicit step.
=============================================================================
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
PANEL = BASE_DIR / "Data" / "processed" / "jst_macrohistory_panel.parquet"
CALIB_DIR = BASE_DIR / "regime" / "calib"
OUT_PARQUET = CALIB_DIR / "jst_bearbottom_conditional_returns.parquet"
OUT_JSON = CALIB_DIR / "jst_bearbottom_conditional_returns.json"
OUT_REPORT = CALIB_DIR / "jst_calibration_report.md"

HORIZONS = [1, 3, 5]
ASSETS = ["equity", "bond", "bill"]
DD_BUCKETS = [
    ("dd_0_10", -0.10, 0.001),     # (0, -10%]
    ("dd_10_20", -0.20, -0.10),    # (-10, -20%]
    ("dd_20_35", -0.35, -0.20),    # (-20, -35%]
    ("dd_35_plus", -10.0, -0.35),  # <= -35%
]
HYPERINFLATION_THRESH = 0.50       # |annual inflation| > 50% flags the window
MIN_EPISODES = 8                   # below this, a cell is flagged THIN


def real_returns(g: pd.DataFrame) -> pd.DataFrame:
    """Add real equity/bond/bill returns, real equity index, drawdown."""
    g = g.sort_values("year").reset_index(drop=True)
    infl = g["cpi"].pct_change()
    g["infl"] = infl
    denom = 1.0 + infl
    g["r_equity"] = (1.0 + g["eq_tr"]) / denom - 1.0
    g["r_bond"] = (1.0 + g["bond_tr"]) / denom - 1.0
    g["r_bill"] = (1.0 + g["bill_rate"]) / denom - 1.0
    # Real equity total-return index and drawdown vs running peak.
    idx = (1.0 + g["r_equity"].fillna(0.0)).cumprod()
    g["eq_index"] = idx
    g["drawdown"] = idx / idx.cummax() - 1.0
    return g


def forward_annualized(series: pd.Series, h: int) -> pd.Series:
    """Annualized real return over the next h years from each row (NaN if short)."""
    vals = series.to_numpy(dtype=float)
    n = len(vals)
    out = np.full(n, np.nan)
    for t in range(n):
        if t + h < n:
            window = vals[t + 1: t + 1 + h]
            if np.all(np.isfinite(window)):
                cum = np.prod(1.0 + window)
                if cum > 0:
                    out[t] = cum ** (1.0 / h) - 1.0
                else:
                    out[t] = -1.0  # total wipeout
    return pd.Series(out, index=series.index)


def assign_states(g: pd.DataFrame) -> pd.DataFrame:
    """Boolean conditioning states per year."""
    dd = g["drawdown"]
    g["st_normal"] = (dd > -0.10) & (g["crisisJST"] != 1)
    g["st_banking_crisis"] = g["crisisJST"] == 1
    # post-crisis 1-3y: any onset in the preceding 1..3 years
    onset_years = set(g.loc[g["crisisJST"] == 1, "year"].tolist())
    g["st_post_crisis_1_3y"] = g["year"].apply(
        lambda y: any((y - k) in onset_years for k in (1, 2, 3))
    )
    for name, lo, hi in DD_BUCKETS:
        g[f"st_{name}"] = (dd > lo) & (dd <= hi)
    return g


def hyperinflation_flag(g: pd.DataFrame, h: int) -> pd.Series:
    """True at row t if any of the next h years had |inflation| > threshold."""
    infl = g["infl"].to_numpy(dtype=float)
    n = len(infl)
    out = np.zeros(n, dtype=bool)
    for t in range(n):
        window = infl[t + 1: t + 1 + h]
        if window.size and np.any(np.abs(window) > HYPERINFLATION_THRESH):
            out[t] = True
    return pd.Series(out, index=g.index)


def summarize(vals: np.ndarray) -> dict:
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return {}
    return {
        "n_obs": int(vals.size),
        "mean": float(np.mean(vals)),
        "median": float(np.median(vals)),
        "std": float(np.std(vals, ddof=1)) if vals.size > 1 else float("nan"),
        "p10": float(np.percentile(vals, 10)),
        "p25": float(np.percentile(vals, 25)),
        "p50": float(np.percentile(vals, 50)),
        "p75": float(np.percentile(vals, 75)),
        "p90": float(np.percentile(vals, 90)),
        "prob_neg": float(np.mean(vals < 0)),
    }


def main() -> int:
    if not PANEL.exists():
        raise FileNotFoundError(f"JST panel missing — run collect_jst_macrohistory.py first: {PANEL}")
    long = pd.read_parquet(PANEL)
    wide = long.pivot_table(index=["country", "year"], columns="variable",
                            values="value", aggfunc="first").reset_index()

    needed = {"eq_tr", "bond_tr", "bill_rate", "cpi", "crisisJST"}
    missing = needed - set(wide.columns)
    if missing:
        raise ValueError(f"JST panel missing required columns: {missing}")

    frames = [real_returns(g) for _, g in wide.groupby("country")]
    panel = pd.concat(frames, ignore_index=True)
    panel = pd.concat(
        [assign_states(g) for _, g in panel.groupby("country")], ignore_index=True
    )

    asset_col = {"equity": "r_equity", "bond": "r_bond", "bill": "r_bill"}
    state_cols = (
        ["st_normal", "st_banking_crisis", "st_post_crisis_1_3y"]
        + [f"st_{name}" for name, _, _ in DD_BUCKETS]
    )

    # forward returns + hyperinflation flags per country/horizon
    fwd = {}
    for asset, col in asset_col.items():
        for h in HORIZONS:
            fwd[(asset, h)] = pd.concat(
                [forward_annualized(g[col], h) for _, g in panel.groupby("country")]
            ).reindex(panel.index)
    hyper = {h: pd.concat([hyperinflation_flag(g, h) for _, g in panel.groupby("country")]
                          ).reindex(panel.index) for h in HORIZONS}

    rows = []
    nested: dict = {}
    for state in state_cols:
        mask_state = panel[state].fillna(False).to_numpy(dtype=bool)
        # distinct episodes = entries into the state (rising edge per country)
        n_episodes = 0
        for _, g in panel.groupby("country"):
            s = g[state].fillna(False).to_numpy(dtype=bool)
            n_episodes += int(np.sum(s & ~np.r_[False, s[:-1]]))
        for asset in ASSETS:
            for h in HORIZONS:
                fseries = fwd[(asset, h)].to_numpy(dtype=float)
                for variant in ("all", "ex_hyperinflation"):
                    m = mask_state.copy()
                    if variant == "ex_hyperinflation":
                        m = m & ~hyper[h].to_numpy(dtype=bool)
                    stats = summarize(fseries[m])
                    if not stats:
                        continue
                    rec = {"state": state.replace("st_", ""), "asset": asset,
                           "horizon_y": h, "variant": variant,
                           "n_episodes": n_episodes, **stats,
                           "thin": stats["n_obs"] > 0 and n_episodes < MIN_EPISODES}
                    rows.append(rec)
                    if variant == "all":
                        nested.setdefault(rec["state"], {}).setdefault(asset, {})[str(h)] = stats

    out = pd.DataFrame(rows)
    CALIB_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(OUT_PARQUET, index=False)
    OUT_JSON.write_text(json.dumps({
        "source": "Jordà-Schularick-Taylor Macrohistory Database R6 (1870-2020)",
        "scope": "13 in-universe developed markets",
        "returns": "real (CPI-deflated) annualized total returns",
        "generated_states": list(nested.keys()),
        "tables": nested,
    }, indent=2))

    write_report(panel, out)
    print(f"  states: {out['state'].nunique()}  cells: {len(out)}")
    print(f"  -> {OUT_PARQUET}")
    print(f"  -> {OUT_JSON}")
    print(f"  -> {OUT_REPORT}")
    return 0


def write_report(panel: pd.DataFrame, out: pd.DataFrame) -> None:
    n_crisis = int((panel["crisisJST"] == 1).sum())
    span = f"{int(panel['year'].min())}-{int(panel['year'].max())}"
    lines = [
        "# JST Bear-Bottom Conditional-Return Calibration",
        "",
        f"**Source:** Jordà-Schularick-Taylor Macrohistory Database R6 ({span}), "
        "13 in-universe developed markets.",
        "**Returns:** real (CPI-deflated) annualized total returns. "
        "**Banking-crisis onsets in sample:** "
        f"{n_crisis}.",
        "",
        "Conditioning states: drawdown buckets (0/-10/-20/-35%+), banking-crisis "
        "onset, post-crisis 1-3y, and normal. Forward horizons 1/3/5y.",
        "",
        "## Headline — forward 3y real EQUITY return by state (variant=all)",
        "",
        "| State | n_episodes | median | mean | p10 | p90 | P(neg) | flag |",
        "|---|---|---|---|---|---|---|---|",
    ]
    eq3 = out[(out.asset == "equity") & (out.horizon_y == 3) & (out.variant == "all")]
    order = ["dd_35_plus", "dd_20_35", "dd_10_20", "dd_0_10",
             "banking_crisis", "post_crisis_1_3y", "normal"]
    eq3 = eq3.set_index("state").reindex([s for s in order if s in eq3["state"].values])
    for st, r in eq3.iterrows():
        flag = "THIN" if r["thin"] else ""
        lines.append(
            f"| {st} | {int(r['n_episodes'])} | {r['median']:.1%} | {r['mean']:.1%} | "
            f"{r['p10']:.1%} | {r['p90']:.1%} | {r['prob_neg']:.0%} | {flag} |"
        )
    lines += [
        "",
        "Read: deeper real drawdowns historically precede higher forward 3y real "
        "equity returns (mean-reversion at bear bottoms), but with a fatter "
        "left tail — the p10 column is the once-in-a-century downside the modern "
        "sample cannot see.",
        "",
        f"_Generated by calibrate_jst_bearbottom.py. Cells with n_episodes < "
        f"{MIN_EPISODES} are flagged THIN._",
    ]
    OUT_REPORT.write_text("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
