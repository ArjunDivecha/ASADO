"""
=============================================================================
SCRIPT NAME: build_panel.py
=============================================================================
Builds the monthly country-return panel and the 6-dimension world-state vector
used by the 2026-09 regime-analog context brief. Reads ONLY frozen parquet
snapshots of the ASADO warehouse - it never opens a DuckDB warehouse file.

Every state variable is trailing/contemporaneous. The T2 forward-return family
(1MRet/3MRet/6MRet/9MRet/12MRet, daily NDRet) is deliberately never read here;
forward outcomes are constructed downstream from the total-return index only.

INPUT FILES (all absolute):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_09_regime_analog_brief/snapshot_2026_09_02/t2_levels_daily_slice.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_09_regime_analog_brief/snapshot_2026_09_02/wb_commodity_prices.parquet  (written by this script's caller if absent; see NOTES)

OUTPUT FILES (all absolute):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/monthly_returns.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/state_vector.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/panel_build_log.json

VERSION: 1.0
LAST UPDATED: 2026-09-02
AUTHOR: Claude (for Arjun Divecha)
DEPENDENCIES: duckdb, pandas, numpy (ASADO venv)
USAGE: venv/bin/python experiments/2026_09_regime_analog_brief/code/build_panel.py
NOTES:
- Month-end = last available daily observation inside each calendar month.
- WB Brent is a monthly average series and lags equity month-ends by up to a
  month; its last observation is 2026-07. That staleness is recorded in the log
  and flagged in the brief rather than papered over.
=============================================================================
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
SNAP = ROOT / "Data/work/experiments/2026_09_regime_analog_brief/snapshot_2026_09_02"
OUT = ROOT / "experiments/2026_09_regime_analog_brief/results"
OUT.mkdir(parents=True, exist_ok=True)

DAILY = SNAP / "t2_levels_daily_slice.parquet"
BRENT = SNAP / "wb_commodity_prices.parquet"

# Universe: 34 T2 names minus the two US style/size proxies. ChinaA and ChinaH both kept.
EXCLUDE_FROM_UNIVERSE = {"NASDAQ", "US SmallCap"}
TECH_PROXY = "NASDAQ"

con = duckdb.connect()
log: dict = {}


def q(sql: str) -> pd.DataFrame:
    return con.execute(sql).df()


# ---------------------------------------------------------------- daily -> monthly
tri = q(f"""
    SELECT date, country, value AS tri
    FROM '{DAILY}' WHERE variable = 'Tot Return Index' AND value IS NOT NULL
""")
tri["date"] = pd.to_datetime(tri["date"])
tri["ym"] = tri["date"].dt.to_period("M")
# month-end observation per country
idx = tri.groupby(["country", "ym"])["date"].transform("max") == tri["date"]
me = tri[idx].copy()
me = me.pivot(index="ym", columns="country", values="tri").sort_index()
rets = me.pct_change()
log["tri_last_date"] = str(tri["date"].max().date())
log["n_months"] = int(len(rets))

universe = [c for c in rets.columns if c not in EXCLUDE_FROM_UNIVERSE]
log["universe"] = universe
log["universe_n"] = len(universe)

# cap weights (month-end, lagged one month so the weight is knowable ex ante)
w = q(f"""
    SELECT date, country, value AS w FROM '{DAILY}' WHERE variable = 'Mcap Weights' AND value IS NOT NULL
""")
w["date"] = pd.to_datetime(w["date"])
w["ym"] = w["date"].dt.to_period("M")
iw = w.groupby(["country", "ym"])["date"].transform("max") == w["date"]
wm = w[iw].pivot(index="ym", columns="country", values="w").sort_index()
wm = wm.reindex(index=rets.index, columns=rets.columns)

ew = rets[universe].mean(axis=1)
wu = wm[universe].shift(1)
wu = wu.div(wu.sum(axis=1), axis=0)
cw = (rets[universe] * wu).sum(axis=1, min_count=1)
nasdaq = rets[TECH_PROXY]
disp = rets[universe].std(axis=1)

# 20-day vol, cross-country mean at month-end
vol = q(f"""
    SELECT date, country, value FROM '{DAILY}' WHERE variable = '20 Day Vol' AND value IS NOT NULL
""")
vol["date"] = pd.to_datetime(vol["date"])
vol["ym"] = vol["date"].dt.to_period("M")
iv = vol.groupby(["country", "ym"])["date"].transform("max") == vol["date"]
volm = vol[iv].pivot(index="ym", columns="country", values="value").sort_index()
vol_mean = volm[[c for c in universe if c in volm.columns]].mean(axis=1).reindex(rets.index)

# US 10y yield, month-end
y = q(f"""
    SELECT date, value FROM '{DAILY}'
    WHERE variable = '10Yr Bond' AND country = 'U.S.' AND value IS NOT NULL
""")
y["date"] = pd.to_datetime(y["date"])
y["ym"] = y["date"].dt.to_period("M")
y10 = y.loc[y.groupby("ym")["date"].transform("max") == y["date"]].set_index("ym")["value"].sort_index()
y10 = y10.reindex(rets.index)

# Brent, monthly average (WB Pink Sheet)
br = q(f"""
    SELECT date, nominal_price_usd AS value FROM '{BRENT}' WHERE commodity_code = 'CRUDE_BRENT' AND nominal_price_usd IS NOT NULL
""")
br["date"] = pd.to_datetime(br["date"])
br["ym"] = br["date"].dt.to_period("M")
brent = br.set_index("ym")["value"].sort_index().reindex(rets.index)
log["brent_last_month"] = str(brent.dropna().index[-1])

# ---------------------------------------------------------------- state vector
state = pd.DataFrame(index=rets.index)
state["OIL_3M"] = np.log(brent / brent.shift(3))
state["UST10_CHG3M"] = y10 - y10.shift(3)
r3 = lambda s: (1 + s).rolling(3).apply(np.prod, raw=True) - 1
state["BREADTH_3M"] = r3(ew) - r3(cw)
state["TECHLEAD_3M"] = r3(nasdaq) - r3(ew)
state["DISP_3M"] = disp.rolling(3).mean()
state["VOL"] = vol_mean

# expanding-window z, min 60 months of history, uses data <= t only
z = pd.DataFrame(index=state.index)
for c in state.columns:
    s = state[c]
    m = s.expanding(min_periods=60).mean()
    sd = s.expanding(min_periods=60).std()
    z[c + "_z"] = (s - m) / sd

out_state = pd.concat([state, z], axis=1)
out_state["EW"] = ew
out_state["CW"] = cw
out_state["NASDAQ"] = nasdaq
out_state["DISP"] = disp
out_state["Y10"] = y10
out_state["BRENT"] = brent
out_state = out_state.reset_index()
out_state["date"] = out_state["ym"].dt.to_timestamp("M")

rets_out = rets.reset_index()
rets_out["date"] = rets_out["ym"].dt.to_timestamp("M")

rets_out.drop(columns=["ym"]).to_parquet(OUT / "monthly_returns.parquet", index=False)
out_state.drop(columns=["ym"]).to_parquet(OUT / "state_vector.parquet", index=False)
log["state_last_full_row"] = str(out_state.dropna(subset=["OIL_3M", "UST10_CHG3M", "BREADTH_3M", "TECHLEAD_3M"])["date"].max().date())
(OUT / "panel_build_log.json").write_text(json.dumps(log, indent=2, default=str))

print(json.dumps({k: v for k, v in log.items() if k != "universe"}, indent=2, default=str))
print("\nlast 6 months of state:")
print(out_state.set_index("date")[["OIL_3M", "UST10_CHG3M", "BREADTH_3M", "TECHLEAD_3M", "DISP_3M", "VOL", "EW", "Y10", "BRENT"]].tail(8).to_string())
