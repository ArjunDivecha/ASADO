"""
=============================================================================
SCRIPT NAME: part1_verify.py
=============================================================================
Part 1 of the 2026-09 regime-analog context brief: tests each factual leg of
the "markets changed tone after 2026-07-01" narrative against the ASADO
warehouse, using frozen parquet snapshots only (no DuckDB warehouse
connection). Compares the post-2026-07-01 window against 2026-H1 and against
the full 2000-2026 history.

INPUT FILES (absolute):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_09_regime_analog_brief/snapshot_2026_09_02/t2_levels_daily_slice.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/state_vector.parquet

OUTPUT FILES (absolute):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/part1_country_returns.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/part1_narrative_scorecard.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/part1_rolling.parquet

VERSION: 1.0
LAST UPDATED: 2026-09-02
AUTHOR: Claude (for Arjun Divecha)
DEPENDENCIES: duckdb, pandas, numpy (ASADO venv)
USAGE: venv/bin/python experiments/2026_09_regime_analog_brief/code/part1_verify.py
NOTES: Uses daily total-return indices only; no forward-labelled T2 variable.
=============================================================================
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
SNAP = ROOT / "Data/work/experiments/2026_09_regime_analog_brief/snapshot_2026_09_02"
OUT = ROOT / "experiments/2026_09_regime_analog_brief/results"
DAILY = SNAP / "t2_levels_daily_slice.parquet"
EXCL = {"NASDAQ", "US SmallCap"}

con = duckdb.connect()
tri = con.execute(f"SELECT date, country, value FROM '{DAILY}' WHERE variable='Tot Return Index' AND value IS NOT NULL").df()
tri["date"] = pd.to_datetime(tri["date"])
px = tri.pivot(index="date", columns="country", values="value").sort_index()
r = px.pct_change()
uni = [c for c in px.columns if c not in EXCL]

y = con.execute(f"SELECT date, value FROM '{DAILY}' WHERE variable='10Yr Bond' AND country='U.S.' AND value IS NOT NULL").df()
y["date"] = pd.to_datetime(y["date"]); y10 = y.set_index("date")["value"].sort_index()
vol = con.execute(f"SELECT date, country, value FROM '{DAILY}' WHERE variable='20 Day Vol' AND value IS NOT NULL").df()
vol["date"] = pd.to_datetime(vol["date"])
volp = vol.pivot(index="date", columns="country", values="value").sort_index()

H1 = ("2026-01-01", "2026-06-30")
H2 = ("2026-07-01", "2026-09-02")


def tot(win, cols):
    sl = px.loc[win[0]:win[1], cols]
    return sl.iloc[-1] / sl.iloc[0] - 1


# ---- per-country table
tbl = pd.DataFrame({
    "ret_2026H1": tot(H1, px.columns),
    "ret_since_Jul1": tot(H2, px.columns),
})
ew_h1 = tbl.loc[uni, "ret_2026H1"].mean()
ew_h2 = tbl.loc[uni, "ret_since_Jul1"].mean()
tbl["excess_vs_EW_H1"] = tbl["ret_2026H1"] - ew_h1
tbl["excess_vs_EW_since_Jul1"] = tbl["ret_since_Jul1"] - ew_h2
tbl["rank_H1"] = tbl.loc[uni, "ret_2026H1"].rank(ascending=False)
tbl["rank_since_Jul1"] = tbl.loc[uni, "ret_since_Jul1"].rank(ascending=False)
tbl["rank_change"] = tbl["rank_H1"] - tbl["rank_since_Jul1"]
tbl = tbl.sort_values("ret_since_Jul1", ascending=False)
tbl.index.name = "country"
tbl.reset_index().to_parquet(OUT / "part1_country_returns.parquet", index=False)

# ---- rolling series for charts / regime dating
win = 63  # ~3 months of trading days
roll = pd.DataFrame(index=r.index)
roll["ew"] = r[uni].mean(axis=1)
roll["disp_63d"] = r[uni].std(axis=1).rolling(win).mean()
roll["nasdaq_minus_ew_63d"] = (r["NASDAQ"] - roll["ew"]).rolling(win).sum()
roll["vol_mean"] = volp[uni].mean(axis=1)
roll["y10"] = y10.reindex(r.index).ffill()


def avg_pair_corr(block: pd.DataFrame) -> float:
    c = block.corr().values
    n = c.shape[0]
    iu = np.triu_indices(n, 1)
    return float(np.nanmean(c[iu]))


pc = pd.Series(index=r.index, dtype=float)
ri = r[uni]
for i in range(win, len(ri)):
    pc.iloc[i] = avg_pair_corr(ri.iloc[i - win:i])
roll["avg_pair_corr_63d"] = pc
roll.reset_index().to_parquet(OUT / "part1_rolling.parquet", index=False)


def stat_block(win_):
    sl = slice(win_[0], win_[1])
    rr = r.loc[sl, uni]
    ewd = rr.mean(axis=1)
    return {
        "EW_total_ret": (1 + ewd).prod() - 1,
        "CW_proxy_US_ret": tot(win_, ["U.S."])["U.S."],
        "NASDAQ_ret": tot(win_, ["NASDAQ"])["NASDAQ"],
        "pct_countries_beating_EW": float((tot(win_, uni) > (1 + ewd).prod() - 1).mean()),
        "xsec_disp_monthly_ann": float(rr.std(axis=1).mean() * np.sqrt(21)),
        "avg_pairwise_corr": avg_pair_corr(rr),
        "mean_20d_vol": float(volp.loc[sl, uni].mean(axis=1).mean()),
        "US10Y_start": float(y10.loc[sl].iloc[0]),
        "US10Y_end": float(y10.loc[sl].iloc[-1]),
        "US10Y_chg_bp": float((y10.loc[sl].iloc[-1] - y10.loc[sl].iloc[0]) * 100),
        "spread_top5_minus_bot5": float(np.sort(tot(win_, uni).values)[-5:].mean() - np.sort(tot(win_, uni).values)[:5].mean()),
    }


sc = pd.DataFrame({"2026_H1": stat_block(H1), "since_Jul1": stat_block(H2)})
sc["change"] = sc["since_Jul1"] - sc["2026_H1"]
sc.index.name = "metric"
sc.reset_index().to_parquet(OUT / "part1_narrative_scorecard.parquet", index=False)

pd.set_option("display.width", 200)
print("=== NARRATIVE SCORECARD ===")
print(sc.round(4).to_string())
print("\n=== COUNTRY TABLE (since Jul 1, sorted) ===")
print(tbl.round(4).to_string())
print("\n=== leadership correlation H1 vs since-Jul1 (Spearman on 32-country ranks) ===")
print(round(tbl.loc[uni, "ret_2026H1"].corr(tbl.loc[uni, "ret_since_Jul1"], method="spearman"), 3))
