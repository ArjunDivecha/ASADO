"""
=============================================================================
SCRIPT NAME: a3_regime_conditioning.py
=============================================================================

WHAT THIS PROGRAM DOES:
Step (ii) of the G1 flip autopsy (PRD section 5): tests whether the
network_spillover family's IC is regime-dependent, and whether the observed
2024-26 negative IC is PREDICTED by the pre-2024 relationship between the IC
and four pre-registered macro/market state axes. Everything runs off frozen
snapshot parquets - no DB access.

The four pre-registered axes (PRD section 5), built PIT-honestly and lagged so
the state is KNOWN by the end of month m-1 when it conditions the IC of
month m (bloomberg-direct variables get +1 month publication lag per the
ElasticNet-audit convention; ECB FX and own-return dispersion are market-
observable with zero lag):
  1. US 10y real rate = BBG_Govt_Bond_10Y(U.S.) - BBG_Breakeven_10Y(U.S.):
     expanding z of the level (min 60 months) and sign of the 12m change.
  2. Broad-USD trend from a fixed-ICE-weight basket (EUR .576, JPY .136,
     GBP .119, CAD .091, SEK .042, CHF .036) built from ECB_FX_*_EUR crosses:
     sign of trailing 12m return and expanding |z| of it.
  3. Cross-country return dispersion = monthly cross-sectional std of the 34
     country returns: expanding quintile (1..5).
  4. EM/DM flow regime = EM-minus-DM mean of MS_ETF_NetFlow_to_MarketCap,
     3m mean, expanding z (coverage 2015+ only).

Tests (frozen in the PRD before any conditional number was computed):
  - conditional mean family IC by state bucket (descriptive), full sample and
    pre-2024;
  - OLS of IC_m on the axis terms, Newey-West (lag 6) t-stats, fit on
    pre-2024 only; BH-FDR at alpha=0.10 across the axis terms.
    M1 = without the flow axis (full 2001+ history);
    M2 = with the flow axis (2015+). M1 is primary (disclosed choice: the
    flow axis simply has no pre-2015 data).
  - counterfactual: predict 2024-01..latest ICs from the pre-2024 fit and the
    OBSERVED 2024-26 states; compare predicted vs observed mean.
  - placebo: 500 circular shifts of the state matrix (offset 24..200 months),
    same fit-and-predict pipeline, to calibrate the real axes' ability to
    "predict" the flip by chance.

PRD verdict-(b) criteria evaluated at the end (all three must hold):
  C1  >=1 axis term significant at BH-FDR alpha=0.10 (pre-2024 fit)
  C2  predicted 2024+ mean IC <= 25th percentile of pre-2024 rolling-30m
      means AND more pessimistic than >=95% of placebo predictions
  C3  observed 2024+ mean inside the prediction's 90% CI

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13/bloomberg_factors.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13/extended_factors.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/flip_autopsy/snapshot_2026_07_13/country_returns_monthly.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/a2_family_ic_monthly_recomputed.parquet

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/a3_states_monthly.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/a3_conditional_ic.xlsx
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/a3_summary.json
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_07_flip_autopsy/results/figures/a3_counterfactual.pdf

VERSION: 1.0  |  LAST UPDATED: 2026-07-13  |  AUTHOR: Claude (G1 flip autopsy)
DEPENDENCIES: pandas, numpy, scipy, matplotlib, openpyxl (production venv)
USAGE: venv/bin/python experiments/2026_07_flip_autopsy/a3_regime_conditioning.py
NOTES: placebo uses a fixed seed (20260713) - deterministic.
=============================================================================
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO")
SNAP = ROOT / "Data/work/experiments/flip_autopsy/snapshot_2026_07_13"
RES = ROOT / "experiments/2026_07_flip_autopsy/results"
FIG = RES / "figures"
FIG.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(20260713)

EM = {"Brazil", "Chile", "ChinaA", "ChinaH", "India", "Indonesia", "Korea",
      "Malaysia", "Mexico", "Philippines", "Poland", "Saudi Arabia",
      "South Africa", "Taiwan", "Thailand", "Turkey", "Vietnam"}
ICE_W = {"EUR": .576, "JPY": .136, "GBP": .119, "CAD": .091, "SEK": .042, "CHF": .036}

# ---------------------------------------------------------------- family IC
fam = pd.read_parquet(RES / "a2_family_ic_monthly_recomputed.parquet")
fam["month"] = pd.to_datetime(fam["month"])
fam = fam.set_index("month")["family_ic"].sort_index()

# ---------------------------------------------------------------- axes
bbg = pd.read_parquet(SNAP / "bloomberg_factors.parquet")
ext = pd.read_parquet(SNAP / "extended_factors.parquet")
crm = pd.read_parquet(SNAP / "country_returns_monthly.parquet")
for df in (bbg, ext, crm):
    df["date"] = pd.to_datetime(df["date"])


def monthly_series(df, variable, country=None):
    d = df[df["variable"] == variable]
    if country is not None:
        d = d[d["country"] == country]
    s = d.set_index("date")["value"].sort_index()
    return s.groupby(s.index.to_period("M").to_timestamp()).last()


def expanding_z(s, min_n=60):
    mu = s.expanding(min_n).mean()
    sd = s.expanding(min_n).std()
    return (s - mu) / sd


# 1. US real rate (bloomberg-direct: +1m publication lag)
rr = (monthly_series(bbg, "BBG_Govt_Bond_10Y", "U.S.")
      - monthly_series(bbg, "BBG_Breakeven_10Y", "U.S.")).dropna()
rr_z = expanding_z(rr).shift(1)                     # +1m pub lag
rr_d12 = np.sign(rr.diff(12)).shift(1)

# 2. Broad USD from ECB crosses (market data, zero pub lag)
crosses = {}
for ccy in ICE_W:
    s = monthly_series(ext, f"ECB_FX_{ccy}_EUR")
    if ccy == "EUR":
        continue
    crosses[ccy] = s
eur_usd = monthly_series(ext, "ECB_FX_USD_EUR")     # USD per EUR
usd_ccy = {}
usd_ccy["EUR"] = 1.0 / eur_usd                       # EUR per USD... (USD strength vs EUR)
for ccy, s in crosses.items():
    usd_ccy[ccy] = (s / eur_usd).dropna()            # CCY per USD
usd_idx = None
for ccy, w in ICE_W.items():
    lg = np.log(usd_ccy[ccy].astype(float)) * w
    usd_idx = lg if usd_idx is None else usd_idx.add(lg, fill_value=np.nan)
usd_idx = usd_idx.dropna()
usd_12m = usd_idx.diff(12)
usd_sign = np.sign(usd_12m)                          # zero lag; known at month end
usd_absz = expanding_z(usd_12m.abs())

# 3. Dispersion (own returns, zero lag)
disp = crm.groupby(crm["date"].dt.to_period("M").dt.to_timestamp())["return_1m"].std()
disp_q = disp.expanding(60).apply(
    lambda w: 1 + int(4 * (pd.Series(w).rank(pct=True).iloc[-1] - 1e-12)), raw=False)

# 4. EM/DM flow (bloomberg-direct: +1m pub lag)
fl = bbg[bbg["variable"] == "MS_ETF_NetFlow_to_MarketCap"].copy()
fl["month"] = fl["date"].dt.to_period("M").dt.to_timestamp()
fl["grp"] = np.where(fl["country"].isin(EM), "EM", "DM")
flow = fl.pivot_table(index="month", columns="grp", values="value", aggfunc="mean")
flow_emdm = (flow["EM"] - flow["DM"]).rolling(3).mean()
flow_z = expanding_z(flow_emdm, min_n=24).shift(1)   # +1m pub lag

states = pd.DataFrame({
    "rr_z": rr_z, "rr_d12": rr_d12,
    "usd_sign": usd_sign, "usd_absz": usd_absz,
    "disp_q": disp_q, "flow_z": flow_z,
}).sort_index()
# predictive alignment: state known by end of m-1 conditions IC of month m
states = states.shift(1)
states.reset_index().rename(columns={"index": "month"}).to_parquet(
    RES / "a3_states_monthly.parquet", index=False)

df = states.join(fam, how="inner").dropna(subset=["family_ic"])
print(f"joined months: {len(df)}  ({df.index.min():%Y-%m} .. {df.index.max():%Y-%m})")

M1_TERMS = ["rr_z", "rr_d12", "usd_sign", "usd_absz", "disp_q"]
M2_TERMS = M1_TERMS + ["flow_z"]
PRE, POST = df.index < "2024-01-01", df.index >= "2024-01-01"


def ols_nw(y, X, lags=6):
    """OLS with Newey-West HAC standard errors. X includes const."""
    Xv, yv = X.values.astype(float), y.values.astype(float)
    beta, *_ = np.linalg.lstsq(Xv, yv, rcond=None)
    e = yv - Xv @ beta
    n, k = Xv.shape
    XtX_inv = np.linalg.inv(Xv.T @ Xv)
    S = (Xv * e[:, None]).T @ (Xv * e[:, None]) / n
    for l in range(1, lags + 1):
        w = 1 - l / (lags + 1)
        G = (Xv[l:] * e[l:, None]).T @ (Xv[:-l] * e[:-l, None]) / n
        S += w * (G + G.T)
    V = n * XtX_inv @ S @ XtX_inv
    se = np.sqrt(np.diag(V))
    return beta, se, e


def bh_fdr(pvals, alpha=0.10):
    p = np.asarray(pvals)
    order = np.argsort(p)
    m = len(p)
    passed = np.zeros(m, bool)
    thresh = 0.0
    for rank, idx in enumerate(order, 1):
        if p[idx] <= alpha * rank / m:
            thresh = p[idx]
    passed = p <= thresh if thresh > 0 else passed
    return passed


from scipy import stats as sstats


def fit_predict(dfx, terms):
    sub = dfx.dropna(subset=terms + ["family_ic"])
    pre, post = sub[sub.index < "2024-01-01"], sub[sub.index >= "2024-01-01"]
    X = np.column_stack([np.ones(len(pre)), pre[terms].values])
    beta, se, resid = ols_nw(pre["family_ic"], pd.DataFrame(X))
    t = beta / se
    p = 2 * (1 - sstats.norm.cdf(np.abs(t)))
    Xp = np.column_stack([np.ones(len(post)), post[terms].values])
    pred = Xp @ beta
    return dict(pre=pre, post=post, beta=beta, se=se, t=t, p=p,
                pred=pred, resid=resid, terms=terms)


def nw_var_of_mean(x, lags=6):
    x = np.asarray(x, float)
    n = len(x)
    e = x - x.mean()
    s = e @ e / n
    for k in range(1, lags + 1):
        s += 2 * (1 - k / (lags + 1)) * (e[k:] @ e[:-k]) / n
    return s / n


results = {}
for name, terms in [("M1", M1_TERMS), ("M2", M2_TERMS)]:
    r = fit_predict(df, terms)
    fdr_pass = bh_fdr(r["p"][1:])                    # exclude intercept
    obs_mean = float(r["post"]["family_ic"].mean())
    pred_mean = float(np.mean(r["pred"]))
    # CI of (obs mean - pred mean): residual-based, NW-adjusted over post months
    resid_var = nw_var_of_mean(r["post"]["family_ic"].values - r["pred"])
    ci_lo, ci_hi = pred_mean - 1.645 * np.sqrt(resid_var), pred_mean + 1.645 * np.sqrt(resid_var)
    roll30 = r["pre"]["family_ic"].rolling(30).mean().dropna()
    q25 = float(roll30.quantile(0.25))
    results[name] = {
        "n_pre": len(r["pre"]), "n_post": len(r["post"]),
        "coef": {t: round(float(b), 5) for t, b in zip(["const"] + terms, r["beta"])},
        "nw_t": {t: round(float(v), 2) for t, v in zip(["const"] + terms, r["t"])},
        "p": {t: round(float(v), 4) for t, v in zip(["const"] + terms, r["p"])},
        "fdr_pass_terms": [t for t, ok in zip(terms, fdr_pass) if ok],
        "pred_2024plus_mean": round(pred_mean, 5),
        "obs_2024plus_mean": round(obs_mean, 5),
        "pred_90ci": [round(ci_lo, 5), round(ci_hi, 5)],
        "obs_within_ci": bool(ci_lo <= obs_mean <= ci_hi),
        "pre_roll30_q25": round(q25, 5),
        "pred_below_q25": bool(pred_mean <= q25),
        "_r": r,
    }

# ---------------------------------------------------------------- placebo (M1)
r1 = results["M1"]["_r"]
sub = df.dropna(subset=M1_TERMS + ["family_ic"]).copy()
state_mat = sub[M1_TERMS].values
placebo_preds = []
n = len(sub)
for _ in range(500):
    off = int(RNG.integers(24, 200))
    shifted = np.roll(state_mat, off, axis=0)
    dfx = sub.copy()
    dfx[M1_TERMS] = shifted
    try:
        rr_ = fit_predict(dfx, M1_TERMS)
        placebo_preds.append(float(np.mean(rr_["pred"])))
    except np.linalg.LinAlgError:
        continue
placebo_preds = np.array(placebo_preds)
real_pred = results["M1"]["pred_2024plus_mean"]
placebo_pct = float((placebo_preds > real_pred).mean())  # share of placebos LESS pessimistic

# ---------------------------------------------------------------- conditional means
cond_rows = []
for term, buckets in [("usd_sign", [-1, 1]), ("rr_d12", [-1, 1]),
                      ("disp_q", [1, 2, 3, 4, 5])]:
    for b in buckets:
        m_all = df[df[term] == b]["family_ic"]
        m_pre = df[PRE & (df[term] == b)]["family_ic"]
        cond_rows.append({"axis": term, "bucket": b,
                          "mean_ic_full": round(float(m_all.mean()), 5) if len(m_all) else None,
                          "n_full": len(m_all),
                          "mean_ic_pre2024": round(float(m_pre.mean()), 5) if len(m_pre) else None,
                          "n_pre": len(m_pre)})
cond = pd.DataFrame(cond_rows)

# ---------------------------------------------------------------- verdict (b)
C1 = len(results["M1"]["fdr_pass_terms"]) > 0
C2 = results["M1"]["pred_below_q25"] and (placebo_pct >= 0.95)
C3 = results["M1"]["obs_within_ci"]
verdict_b = "CONFIRMED" if (C1 and C2 and C3) else (
    "PARTIAL (states matter but residual flip unexplained)" if (C1 and C2) else "REJECTED")

summary = {
    "criteria": {"C1_fdr_any_term": C1, "C2_pred_bad_and_beats_placebo": C2,
                 "C3_obs_within_pred_ci": C3},
    "verdict_b_regime_interaction": verdict_b,
    "placebo_share_less_pessimistic_than_real": round(placebo_pct, 3),
    "M1": {k: v for k, v in results["M1"].items() if k != "_r"},
    "M2": {k: v for k, v in results["M2"].items() if k != "_r"},
    "conditional_means": cond.to_dict("records"),
    "seed": 20260713,
}
(RES / "a3_summary.json").write_text(json.dumps(summary, indent=2))

with pd.ExcelWriter(RES / "a3_conditional_ic.xlsx") as xw:
    cond.to_excel(xw, sheet_name="conditional_means", index=False)
    pd.DataFrame({"placebo_pred_mean": placebo_preds}).to_excel(
        xw, sheet_name="placebo", index=False)
    df.reset_index().to_excel(xw, sheet_name="ic_and_states", index=False)

# ---------------------------------------------------------------- figure (light mode)
r = results["M1"]["_r"]
fig, ax = plt.subplots(figsize=(11, 5.5))
roll = fam.rolling(12).mean()
ax.plot(roll.index, roll.values, color="#1a6faf", lw=1.8, label="family IC (12m rolling)")
ax.axhline(0, color="#888", lw=0.8)
ax.axvline(pd.Timestamp("2024-04-01"), color="#c0392b", ls="--", lw=1.2,
           label="LS break 2024-04")
post_idx = r["post"].index
ax.plot(post_idx, pd.Series(r["pred"], index=post_idx).rolling(6, min_periods=1).mean(),
        color="#e67e22", lw=1.8, ls=":", label="counterfactual (pre-2024 fit, 6m sm.)")
ax.set_title("network_spillover family IC: observed vs regime counterfactual")
ax.legend(frameon=False)
ax.set_facecolor("white"); fig.patch.set_facecolor("white")
fig.tight_layout()
fig.savefig(FIG / "a3_counterfactual.pdf")

print("\n=== STEP (ii) REGIME CONDITIONING ===")
print(f"M1 pre-2024 fit (n={results['M1']['n_pre']}): NW-t {results['M1']['nw_t']}")
print(f"FDR-passing terms: {results['M1']['fdr_pass_terms'] or 'NONE'}")
print(f"predicted 2024+ mean IC: {results['M1']['pred_2024plus_mean']}  "
      f"(pre-2024 roll30 q25 = {results['M1']['pre_roll30_q25']})")
print(f"observed  2024+ mean IC: {results['M1']['obs_2024plus_mean']}  "
      f"90% CI around prediction: {results['M1']['pred_90ci']}")
print(f"placebo: {placebo_pct:.1%} of 500 shifted-state draws predict LESS pessimistically")
print(f"C1={C1}  C2={C2}  C3={C3}  ->  verdict (b): {verdict_b}")
print("\nconditional means:\n", cond.to_string(index=False))
print("\nDone. Outputs in", RES)
