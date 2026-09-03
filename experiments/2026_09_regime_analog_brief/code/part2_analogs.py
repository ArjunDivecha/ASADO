"""
=============================================================================
SCRIPT NAME: part2_analogs.py
=============================================================================
Part 2 of the 2026-09 regime-analog context brief. Finds historical months
whose world state resembled 2026-08-31 on the pre-registered 6-dimension state
vector (SPEC.md, frozen before any forward return was computed), collapses them
into episodes, and reports the DISTRIBUTION of what followed at 1/3/6/12 months
against a length-matched block bootstrap of the unconditional history.

Also runs a clearly-labelled POST-HOC cut suggested by Part 1: country-level
"leadership inversion" (momentum-crash) episodes.

This is a context-tier descriptive brief. It is NOT a signal, and the repo's
prior verdicts on regime conditioning (all DEAD - see SPEC.md) stand.

INPUT FILES (absolute):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/state_vector.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/monthly_returns.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_09_regime_analog_brief/snapshot_2026_09_02/wb_commodity_prices.parquet

OUTPUT FILES (absolute):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/analog_episodes.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/forward_outcomes.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/forward_country_table.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_regime_analog_brief/results/part2_summary.json

VERSION: 1.0
LAST UPDATED: 2026-09-02
AUTHOR: Claude (for Arjun Divecha)
DEPENDENCIES: pandas, numpy, pyarrow (ASADO venv)
USAGE: venv/bin/python experiments/2026_09_regime_analog_brief/code/part2_analogs.py
NOTES:
- WB Brent ends 2026-07; the 2026-08 OIL_3M reading carries the last available
  Brent forward and is flagged stale ("*") everywhere it is reported.
- Every statistic carries n_months AND n_episodes. Small n is the answer, not a bug.
=============================================================================
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(20260902)
ROOT = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
OUT = ROOT / "experiments/2026_09_regime_analog_brief/results"
SNAP = ROOT / "Data/work/experiments/2026_09_regime_analog_brief/snapshot_2026_09_02"

EXCL = {"NASDAQ", "US SmallCap"}
ANCHOR = pd.Timestamp("2026-08-31")
HORIZONS = [1, 3, 6, 12]
STATE_DIMS = ["OIL_3M", "UST10_CHG3M", "BREADTH_3M", "TECHLEAD_3M", "DISP_3M", "VOL"]

BLOCS = {
    "AI_complex (KR,TW,NL,NASDAQ)": ["Korea", "Taiwan", "Netherlands", "NASDAQ"],
    "EM_tech (KR,TW)": ["Korea", "Taiwan"],
    "EM_carry (BR,MX,ZA,ID,TR)": ["Brazil", "Mexico", "South Africa", "Indonesia", "Turkey"],
    "Commodity_exporters": ["Australia", "Brazil", "Canada", "Chile", "Saudi Arabia", "South Africa", "Indonesia"],
    "DM_Europe": ["France", "Germany", "Italy", "Netherlands", "Spain", "Sweden", "Switzerland", "U.K.", "Denmark"],
    "Japan": ["Japan"], "India": ["India"], "China (A+H)": ["ChinaA", "ChinaH"], "US": ["U.S."],
}

# ------------------------------------------------------------------ load
st = pd.read_parquet(OUT / "state_vector.parquet").set_index("date").sort_index()
rets = pd.read_parquet(OUT / "monthly_returns.parquet").set_index("date").sort_index()
# drop the partial current month (daily data stops 2026-09-02)
st = st.loc[:ANCHOR]
rets = rets.loc[:ANCHOR]
uni = [c for c in rets.columns if c not in EXCL]

# ---- patch the stale August OIL_3M with the last available Brent (flagged "*")
brent = pd.read_parquet(SNAP / "wb_commodity_prices.parquet")
brent = brent[brent["commodity_code"] == "CRUDE_BRENT"][["date", "nominal_price_usd"]].dropna()
brent["date"] = pd.to_datetime(brent["date"]).dt.to_period("M")
bs = brent.set_index("date")["nominal_price_usd"].sort_index()
bs_m = bs.reindex(st.index.to_period("M"))
stale_flag = bs_m.isna()
bs_ff = bs_m.ffill()
oil3m_ff = np.log(bs_ff.values / np.roll(bs_ff.values, 3))
oil3m_ff[:3] = np.nan
st["OIL_3M"] = oil3m_ff
st["OIL_STALE"] = stale_flag.values
# recompute expanding z for OIL_3M on the patched series
s = st["OIL_3M"]
st["OIL_3M_z"] = (s - s.expanding(min_periods=60).mean()) / s.expanding(min_periods=60).std()

zc = [d + "_z" for d in STATE_DIMS]
Z = st[zc].dropna()
anchor_z = Z.loc[ANCHOR]

# ------------------------------------------------------------------ forward outcomes
ew = rets[uni].mean(axis=1)
cw = st["CW"]
nasdaq = rets["NASDAQ"]


def fwd_cum(s: pd.Series, h: int) -> pd.Series:
    """Cumulative return of s over the h months AFTER each index date."""
    lg = np.log1p(s)
    return np.expm1(lg.shift(-h).rolling(h).sum().shift(0)) if False else \
        np.expm1(lg[::-1].rolling(h).sum()[::-1].shift(-1) * 0 + lg[::-1].rolling(h).sum()[::-1].shift(-1))


def fwd(s: pd.Series, h: int) -> pd.Series:
    lg = np.log1p(s)
    fw = lg.shift(-1).rolling(h).sum().shift(-(h - 1))
    return np.expm1(fw)


# trailing 12-1 momentum long/short spread, forward
tri_m = (1 + rets[uni]).cumprod()
mom_sig = tri_m.shift(1) / tri_m.shift(13) - 1  # trailing 12-1M, known at t
n_side = max(3, int(round(0.2 * len(uni))))
mom_fwd = {}
for h in HORIZONS:
    f = pd.DataFrame({c: fwd(rets[c], h) for c in uni})
    rank = mom_sig.rank(axis=1, ascending=False)
    top = (rank <= n_side)
    bot = (rank > len(uni) - n_side)
    mom_fwd[h] = (f.where(top).mean(axis=1) - f.where(bot).mean(axis=1))

outcomes: dict[int, pd.DataFrame] = {}
for h in HORIZONS:
    d = pd.DataFrame(index=rets.index)
    d["EW"] = fwd(ew, h)
    d["EW_minus_CW"] = fwd(ew, h) - fwd(cw, h)
    d["NASDAQ_minus_EW"] = fwd(nasdaq, h) - fwd(ew, h)
    d["Momentum_LS"] = mom_fwd[h]
    for name, members in BLOCS.items():
        m = [c for c in members if c in rets.columns]
        d["bloc::" + name] = pd.concat([fwd(rets[c], h) for c in m], axis=1).mean(axis=1) - fwd(ew, h)
    outcomes[h] = d


# ------------------------------------------------------------------ episodes
def to_episodes(dates: pd.DatetimeIndex, bridge: int = 1) -> list[list[pd.Timestamp]]:
    dates = sorted(dates)
    eps: list[list[pd.Timestamp]] = []
    for d in dates:
        if eps and (d.to_period("M") - eps[-1][-1].to_period("M")).n <= bridge + 1:
            eps[-1].append(d)
        else:
            eps.append([d])
    return eps


def block_bootstrap_p(obs: float, series: pd.Series, lengths: list[int], n: int = 10000) -> tuple[float, float, float]:
    """p-value for the episode-median of `series` vs length-matched random blocks."""
    v = series.dropna()
    idx = v.index
    pos = {d: i for i, d in enumerate(idx)}
    arr = v.values
    N = len(arr)
    draws = np.empty(n)
    for j in range(n):
        meds = []
        for L in lengths:
            if N - L <= 0:
                continue
            s0 = RNG.integers(0, N - L + 1)
            meds.append(arr[s0:s0 + L].mean())
        draws[j] = np.median(meds) if meds else np.nan
    p = float(np.mean(np.abs(draws - np.nanmedian(draws)) >= abs(obs - np.nanmedian(draws))))
    return p, float(np.nanpercentile(draws, 5)), float(np.nanpercentile(draws, 95))


def summarize(name: str, match_dates: pd.DatetimeIndex, note: str) -> tuple[list[dict], list[dict], list[dict]]:
    eps = to_episodes(match_dates)
    lengths = [len(e) for e in eps]
    ep_rows = [{"screen": name, "episode": i + 1, "start": e[0], "end": e[-1], "n_months": len(e)}
               for i, e in enumerate(eps)]
    rows, crows = [], []
    for h in HORIZONS:
        d = outcomes[h]
        for col in d.columns:
            ep_vals = [d.loc[[x for x in e if x in d.index], col].dropna().mean() for e in eps]
            ep_vals = [x for x in ep_vals if pd.notna(x)]
            if not ep_vals:
                continue
            obs = float(np.median(ep_vals))
            p, lo, hi = block_bootstrap_p(obs, d[col], lengths)
            uncond = float(d[col].median())
            rows.append({"screen": name, "horizon_m": h, "outcome": col,
                         "episode_median": obs, "unconditional_median": uncond,
                         "diff": obs - uncond, "hit_rate_pos": float(np.mean(np.array(ep_vals) > 0)),
                         "n_episodes": len(ep_vals), "n_months": len(match_dates),
                         "boot_p": p, "boot_5pct": lo, "boot_95pct": hi, "note": note})
        # per-country forward excess vs EW
        for c in uni:
            f = fwd(rets[c], h) - fwd(ew, h)
            ep_vals = [f.loc[[x for x in e if x in f.index]].dropna().mean() for e in eps]
            ep_vals = [x for x in ep_vals if pd.notna(x)]
            if not ep_vals:
                continue
            crows.append({"screen": name, "horizon_m": h, "country": c,
                          "episode_median_excess": float(np.median(ep_vals)),
                          "unconditional_median_excess": float(f.median()),
                          "hit_rate_pos": float(np.mean(np.array(ep_vals) > 0)),
                          "n_episodes": len(ep_vals)})
    return ep_rows, rows, crows


# ---- Screen A: pre-registered condition screen (sign match + half-magnitude on S1..S4)
thr = {d: anchor_z[d + "_z"] / 2 for d in ["OIL_3M", "UST10_CHG3M", "BREADTH_3M", "TECHLEAD_3M"]}
cond = pd.Series(True, index=Z.index)
for d, t in thr.items():
    cond &= (Z[d + "_z"] <= t) if t < 0 else (Z[d + "_z"] >= t)
A = Z.index[cond & (Z.index < ANCHOR)]

# relaxed 3-of-4 variant (reported alongside, same rule family)
hits = sum(((Z[d + "_z"] <= t) if t < 0 else (Z[d + "_z"] >= t)).astype(int) for d, t in thr.items())
A3 = Z.index[(hits >= 3) & (Z.index < ANCHOR)]

# ---- Screen B: kNN in 6-d z space, k=24, excluding the trailing 12 months
cand = Z.loc[Z.index < ANCHOR - pd.DateOffset(months=12)]
dist = np.sqrt(((cand - anchor_z) ** 2).sum(axis=1))
B = dist.nsmallest(24).index.sort_values()

# ---- Screen C (POST-HOC, discovered in Part 1): country-momentum crash / leadership inversion
r6 = tri_m / tri_m.shift(6) - 1
r3 = tri_m / tri_m.shift(3) - 1
inv = pd.Series(index=rets.index, dtype=float)
for d in rets.index:
    a, b = r6.shift(3).loc[d], r3.loc[d]
    ok = a.notna() & b.notna()
    inv.loc[d] = a[ok].rank().corr(b[ok].rank()) if ok.sum() > 10 else np.nan
C = inv[(inv <= -0.30) & (inv.index < ANCHOR)].index

print(f"anchor {ANCHOR.date()}  z = {anchor_z.round(2).to_dict()}")
print(f"OIL_3M for 2026-08 is STALE (Brent last month = {bs.index[-1]}) -> flagged *")
print(f"screen A (4/4 pre-registered): {len(A)} months")
print(f"screen A3 (3/4 relaxed):       {len(A3)} months")
print(f"screen B (kNN k=24):           {len(B)} months")
print(f"screen C (post-hoc inversion): {len(C)} months; current reading = {inv.loc[ANCHOR]:.3f}")

all_eps, all_rows, all_crows = [], [], []
for nm, dts, note in [("A_prereg_4of4", A, "pre-registered condition screen"),
                      ("A3_relaxed_3of4", A3, "pre-registered family, relaxed to 3 of 4"),
                      ("B_knn24", B, "pre-registered kNN cross-check"),
                      ("C_posthoc_inversion", C, "POST-HOC: discovered in Part 1, not pre-registered")]:
    if len(dts) == 0:
        print(f"  {nm}: NO MATCHES")
        continue
    e, r_, c_ = summarize(nm, dts, note)
    all_eps += e; all_rows += r_; all_crows += c_
    pd.DataFrame(all_eps).to_parquet(OUT / "analog_episodes.parquet", index=False)
    pd.DataFrame(all_rows).to_parquet(OUT / "forward_outcomes.parquet", index=False)
    pd.DataFrame(all_crows).to_parquet(OUT / "forward_country_table.parquet", index=False)
    print(f"  {nm}: {len(dts)} months -> {len(e)} episodes  [written]")

summary = {"anchor": str(ANCHOR.date()), "anchor_z": anchor_z.round(3).to_dict(),
           "oil_stale": True, "brent_last_month": str(bs.index[-1]),
           "inversion_now": float(inv.loc[ANCHOR]),
           "n_months_A": len(A), "n_months_A3": len(A3), "n_months_B": len(B), "n_months_C": len(C)}
(OUT / "part2_summary.json").write_text(json.dumps(summary, indent=2))
print("\nwrote", OUT / "part2_summary.json")
