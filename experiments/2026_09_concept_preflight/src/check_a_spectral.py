"""
=============================================================================
SCRIPT NAME: check_a_spectral.py
=============================================================================
Check A of the concept-layer pre-flight: how many "concepts" the T2 country
panel holds (Horn parallel analysis + Wang-Liu-Chen eigenvalue ratios), and
whether the forward-return signal lives in the strong or the noise directions
of the feature covariance (source-condition slope, docs/SPECTRAL_DIAGNOSTICS.md
§1). Pre-registration: ../PREREG.md (+ amendment A1).

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/concept_preflight/snapshot_2026_09_23/t2_master.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/concept_preflight/snapshot_2026_09_23/t2_factors_daily.parquet

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_concept_preflight/results/check_a_spectral.json
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_concept_preflight/results/check_a_eigen.xlsx
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_concept_preflight/results/check_a_spectral.pdf
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_concept_preflight/results/check_a.log

VERSION: 1.0
LAST UPDATED: 2026-09-23
AUTHOR: Claude (Opus 5.5) for Arjun Divecha

DESCRIPTION:
Features: t2_master _CS variables (forward returns excluded; near-zero
cross-sectional variance dropped; >=90% coverage of country-months from 2005-01;
complete cases). A t2_master row dated first-of-month t holds information known
at the end of month t-1 and its 1MRet is calendar month t (verified: Spearman
1.0 against compounded daily returns), so targets are compounded calendar-month
returns for months t..t+11 (12M, primary) and month t (1M), each demeaned
across countries within the month.
A1: eigenvalues of the pooled correlation matrix vs 200 within-month
country permutations of each variable; k_var = leading eigenvalues above the
null 95th percentile. A2: s' = slope of log|c_i| on log lambda_i with
c_i = v_i'X'y/(n lambda_i); null = 200 within-month country permutations of y.

DEPENDENCIES: numpy, pandas, matplotlib, openpyxl (ASADO venv)
USAGE: cd experiments/2026_09_concept_preflight/src && ../../../venv/bin/python check_a_spectral.py
NOTES: diagnostic only; no forecasts, no walk-forward comparison (see PREREG).
=============================================================================
"""
from __future__ import annotations

import json
import time

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from common import RESULTS, SNAP, T2_UNIVERSE, daily_returns, monthly_returns

N_NULL = 200
START = pd.Period("2005-01", "M")
CUTOFFS = ["2010-12", "2015-12", "2020-12"]
FWD = {"1MRet", "3MRet", "6MRet", "9MRet", "12MRet"}
LOG = RESULTS / "check_a.log"


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as fh:
        fh.write(line + "\n")


def load_features() -> tuple[pd.DataFrame, dict]:
    t = pd.read_parquet(SNAP / "t2_master.parquet")
    t = t[t["variable"].str.endswith("_CS") & ~t["variable"].isin(FWD) & t["country"].isin(T2_UNIVERSE)]
    t["month"] = pd.to_datetime(t["date"]).dt.to_period("M")
    wide = t.pivot_table(index=["month", "country"], columns="variable", values="value")
    wide = wide[wide.index.get_level_values("month") >= START]
    info = {"cs_variables_total": int(wide.shape[1])}
    cs_sd = wide.groupby(level="month").std().mean()
    keep = cs_sd[cs_sd > 0.1].index
    info["dropped_low_cs_variance"] = sorted(set(wide.columns) - set(keep))
    wide = wide[keep]
    full_idx = pd.MultiIndex.from_product([sorted(wide.index.get_level_values("month").unique()), T2_UNIVERSE])
    cover = wide.reindex(full_idx).notna().mean()
    keep = cover[cover >= 0.90].index
    info["dropped_low_coverage"] = {k: round(float(v), 3) for k, v in cover[cover < 0.90].items()}
    wide = wide[keep].dropna()
    info["kept_variables"] = list(keep)
    info["rows_complete_case"] = int(len(wide))
    info["months"] = int(wide.index.get_level_values("month").nunique())
    return wide, info


def targets(months_countries: pd.MultiIndex) -> tuple[pd.Series, pd.Series]:
    d = daily_returns()
    mret, _, last = monthly_returns(d)
    lr = np.log1p(mret)
    r12 = np.expm1(lr[::-1].rolling(12, min_periods=12).sum()[::-1])  # months t..t+11
    r12 = r12.loc[: last - 11] if False else r12
    def rel(df):
        s = df.stack(future_stack=True)
        s.index.names = ["month", "country"]
        s = s.dropna()
        return s - s.groupby(level="month").transform("mean")
    y12 = rel(r12).reindex(months_countries)
    y1 = rel(mret).reindex(months_countries)
    return y12, y1


def standardize(X: np.ndarray) -> np.ndarray:
    return (X - X.mean(0)) / X.std(0)


def eig_corr(X: np.ndarray) -> np.ndarray:
    C = np.corrcoef(X, rowvar=False)
    return np.sort(np.linalg.eigvalsh(C))[::-1]


def permute_within_month(X: np.ndarray, groups: np.ndarray, rng) -> np.ndarray:
    Xp = X.copy()
    for g in np.unique(groups):
        idx = np.where(groups == g)[0]
        for j in range(X.shape[1]):
            Xp[idx, j] = X[rng.permutation(idx), j]
    return Xp


def parallel_analysis(X: np.ndarray, groups: np.ndarray, rng) -> dict:
    ev = eig_corr(X)
    null = np.array([eig_corr(permute_within_month(X, groups, rng)) for _ in range(N_NULL)])
    p95 = np.percentile(null, 95, axis=0)
    k = 0
    while k < len(ev) and ev[k] > p95[k]:
        k += 1
    return {"k_var": int(k), "eigenvalues": ev.tolist(), "null_p95": p95.tolist(),
            "share_top5": float(ev[:5].sum() / ev.sum())}


def eigen_ratio(M: np.ndarray, kmax: int = 10) -> int:
    ev = np.sort(np.linalg.eigvalsh(M))[::-1]
    ev = np.clip(ev, 1e-12, None)
    r = ev[:kmax] / ev[1:kmax + 1]
    return int(np.argmax(r) + 1)


def wang_liu_chen(wide: pd.DataFrame) -> dict:
    months = wide.index.get_level_values("month")
    per_month = wide.groupby(level="month").size()
    common = [c for c in T2_UNIVERSE
              if (wide.index.get_level_values("country") == c).sum() >= 0.95 * per_month.size]
    Mrow, Mcol, T = 0, 0, 0
    for m, g in wide.groupby(level="month"):
        g = g.droplevel("month")
        if not set(common).issubset(g.index):
            continue
        Xt = g.loc[common].to_numpy()
        Mrow = Mrow + Xt @ Xt.T
        Mcol = Mcol + Xt.T @ Xt
        T += 1
    return {"countries_used": len(common), "months_used": T,
            "k_country_mode": eigen_ratio(Mrow / T), "k_variable_mode": eigen_ratio(Mcol / T)}


def source_slope(X: np.ndarray, y: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    n = len(y)
    H = X.T @ X / n
    lam, V = np.linalg.eigh(H)
    keep = lam > 1e-8
    lam, V = lam[keep], V[:, keep]
    b = V.T @ (X.T @ y) / n
    c = b / lam
    slope = np.polyfit(np.log(lam), np.log(np.abs(c) + 1e-300), 1)[0]
    return float(slope), lam, c


def permute_y(y: np.ndarray, groups: np.ndarray, rng) -> np.ndarray:
    yp = y.copy()
    for g in np.unique(groups):
        idx = np.where(groups == g)[0]
        yp[idx] = y[rng.permutation(idx)]
    return yp


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    LOG.write_text("")
    t0 = time.time()
    rng = np.random.default_rng(20260923)
    wide, info = load_features()
    log(f"features kept {len(info['kept_variables'])} of {info['cs_variables_total']} _CS; "
        f"rows {info['rows_complete_case']}, months {info['months']}")
    months = wide.index.get_level_values("month")
    groups = months.astype(str).to_numpy()
    X = standardize(wide.to_numpy())
    out = {"data": info, "A1": {}, "A2": {}}

    # A1 full sample + expanding cutoffs
    pa = parallel_analysis(X, groups, rng)
    out["A1"]["full"] = pa
    log(f"A1 full: k_var={pa['k_var']}; top eigenvalues {np.round(pa['eigenvalues'][:8], 2).tolist()}; "
        f"null p95 {np.round(pa['null_p95'][:8], 2).tolist()}")
    for cut in CUTOFFS:
        sel = months <= pd.Period(cut, "M")
        Xs = standardize(wide.to_numpy()[sel])
        r = parallel_analysis(Xs, groups[sel], rng)
        out["A1"][f"to_{cut}"] = {"k_var": r["k_var"], "rows": int(sel.sum()),
                                  "eigenvalues": r["eigenvalues"][:12], "null_p95": r["null_p95"][:12]}
        log(f"A1 to {cut}: k_var={r['k_var']} (rows {int(sel.sum())})")
    out["A1"]["wang_liu_chen"] = wang_liu_chen(wide)
    log(f"A1 Wang-Liu-Chen eigenvalue ratio: {out['A1']['wang_liu_chen']}")

    # A2 source-condition slope
    y12, y1 = targets(wide.index)
    for name, y in (("12M", y12), ("1M", y1)):
        ok = y.notna().to_numpy()
        Xy = standardize(wide.to_numpy()[ok])
        yy = y.to_numpy()[ok]
        yy = (yy - yy.mean()) / yy.std()
        g = groups[ok]
        s, lam, c = source_slope(Xy, yy)
        null = np.array([source_slope(Xy, permute_y(yy, g, rng))[0] for _ in range(N_NULL)])
        p95 = float(np.percentile(null, 95))
        out["A2"][name] = {"rows": int(ok.sum()), "slope": s, "null_mean": float(null.mean()),
                           "null_p95": p95, "null_percentile_of_real": float((null < s).mean()),
                           "above_null_p95": bool(s > p95),
                           "lambda": lam.tolist(), "c": c.tolist()}
        log(f"A2 {name}: slope s'={s:+.3f}; null mean {null.mean():+.3f}, p95 {p95:+.3f}; "
            f"real at null pct {(null < s).mean():.3f}")

    k = out["A1"]["full"]["k_var"]
    above = out["A2"]["12M"]["above_null_p95"]
    if not above:
        decision = "DROP node-level concept experiment (return signal not concentrated in strong directions)"
    elif k <= 2:
        decision = "REDUCE to IPCA listwise ablation only (vocabulary too small)"
    else:
        decision = f"PROCEED with node-level concept experiment, concepts capped at {k}"
    out["decision"] = decision
    out["elapsed_sec"] = round(time.time() - t0, 1)
    log(f"decision: {decision} ({out['elapsed_sec']}s)")

    tmp = RESULTS / "check_a_spectral.json.tmp"
    tmp.write_text(json.dumps(out, indent=2))
    tmp.replace(RESULTS / "check_a_spectral.json")
    ev = pd.DataFrame({"rank": np.arange(1, len(pa["eigenvalues"]) + 1),
                       "eigenvalue": pa["eigenvalues"], "null_p95": pa["null_p95"]})
    with pd.ExcelWriter(RESULTS / "check_a_eigen.xlsx") as xw:
        ev.to_excel(xw, sheet_name="A1_full_scree", index=False)
        pd.DataFrame({"variable": info["kept_variables"]}).to_excel(xw, sheet_name="kept_variables", index=False)
        for name in ("12M", "1M"):
            pd.DataFrame({"lambda": out["A2"][name]["lambda"], "c": out["A2"][name]["c"]}).to_excel(
                xw, sheet_name=f"A2_{name}", index=False)

    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    r = ev["rank"][:20]
    axes[0].plot(r, ev["eigenvalue"][:20], "o-", label="T2 _CS panel")
    axes[0].plot(r, ev["null_p95"][:20], "--", color="#888888", label="null 95th pct")
    axes[0].set_title(f"How many concepts? k = {k}")
    axes[0].set_xlabel("eigenvalue rank"); axes[0].legend(frameon=False)
    for ax, name in ((axes[1], "12M"), (axes[2], "1M")):
        lam = np.array(out["A2"][name]["lambda"]); c = np.abs(np.array(out["A2"][name]["c"]))
        ax.loglog(lam, c, "o", ms=4)
        ax.set_title(f"{name} target: slope {out['A2'][name]['slope']:+.2f} "
                     f"(null p95 {out['A2'][name]['null_p95']:+.2f})")
        ax.set_xlabel("eigenvalue λ"); ax.set_ylabel("|signal coefficient c|")
    for ax in axes:
        ax.set_facecolor("white")
    fig.patch.set_facecolor("white")
    fig.tight_layout()
    fig.savefig(RESULTS / "check_a_spectral.pdf")


if __name__ == "__main__":
    main()
