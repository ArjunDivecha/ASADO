"""
=============================================================================
SCRIPT NAME: check_b_g2.py
=============================================================================
Check B of the concept-layer pre-flight: the Research-Agenda G2 / WP-11 Step 2
orthogonalization gate, run separately for each relation type (trade, bank,
holder) in graph_edge_vintages. Pre-registration: ../PREREG.md (+ amendment A1).

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/concept_preflight/snapshot_2026_09_23/t2_factors_daily.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/concept_preflight/snapshot_2026_09_23/graph_edge_vintages.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/ff_region_map.json

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_concept_preflight/results/check_b_g2.json
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_concept_preflight/results/check_b_monthly_ic.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_concept_preflight/results/check_b_yearly_ic.xlsx
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_concept_preflight/results/check_b_cumulative_ic.pdf
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_09_concept_preflight/results/check_b.log

VERSION: 1.0
LAST UPDATED: 2026-09-23
AUTHOR: Claude (Opus 5.5) for Arjun Divecha

DESCRIPTION:
For each month m and relation r: partner-weighted month-m return PW_r(i,m)
(latest vintage with applies_from <= end of m, diagonal removed, weights
re-normalised over neighbours with a return). Cross-sectional OLS of PW_r on
[1, own 1m, own 12-1 momentum, regional EW 1m ex-self] -> residual. Monthly
Spearman IC of residual vs month m+1 return (P) and vs month m+1 return
excluding the first trading day (S). Pooled t and Newey-West(3) t. Placebo:
200 within-row neighbour permutations per vintage.

DEPENDENCIES: numpy, pandas, scipy, matplotlib, openpyxl (ASADO venv)
USAGE: cd experiments/2026_09_concept_preflight/src && ../../../venv/bin/python check_b_g2.py
NOTES: gross, no costs. Diagnostic only; writes nothing outside results/.
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
from scipy import stats

from common import RESULTS, SNAP, SOVEREIGNS, daily_returns, monthly_returns, regions

RELATIONS = ["trade", "bank", "holder"]
MIN_COUNTRIES = 15
N_PLACEBO = 200
ERAS = {"2000-13": ("2000-01", "2013-12"), "2014-23": ("2014-01", "2023-12"),
        "2024-26": ("2024-01", "2026-12")}
LOG = RESULTS / "check_b.log"


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a") as fh:
        fh.write(line + "\n")


def load_vintages(etype: str) -> list[tuple[pd.Timestamp, np.ndarray]]:
    g = pd.read_parquet(SNAP / "graph_edge_vintages.parquet")
    g = g[g["edge_type"] == etype].copy()
    g["applies_from"] = pd.to_datetime(g["applies_from"])
    out = []
    for af, d in g.groupby("applies_from"):
        w = d.pivot_table(index="focal", columns="neighbor", values="weight", aggfunc="sum")
        w = w.reindex(index=SOVEREIGNS, columns=SOVEREIGNS).to_numpy(copy=True)
        np.fill_diagonal(w, np.nan)
        w = np.where(np.isnan(w) | (w < 0), 0.0, w)
        out.append((af, w))
    out.sort(key=lambda t: t[0])
    return out


def pick_vintage(vints, month: pd.Period):
    end = month.end_time.normalize()
    cand = [w for af, w in vints if af <= end]
    return cand[-1] if cand else None


def partner_weighted(w: np.ndarray, r: np.ndarray) -> np.ndarray:
    valid = ~np.isnan(r)
    rv = np.where(valid, r, 0.0)
    num = w @ rv
    den = w @ valid.astype(float)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(den > 1e-12, num / den, np.nan)


def newey_west_t(x: np.ndarray, lags: int = 3) -> float:
    x = x[~np.isnan(x)]
    n = len(x)
    u = x - x.mean()
    s = u @ u / n
    for l in range(1, lags + 1):
        s += 2 * (1 - l / (lags + 1)) * (u[l:] @ u[:-l]) / n
    return float(x.mean() / np.sqrt(s / n))


def tstat(x: np.ndarray) -> float:
    x = x[~np.isnan(x)]
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def build_controls(R: pd.DataFrame, reg: dict[str, str]):
    """own 1m, 12-1 momentum, regional EW 1m ex-self (sovereign tokens only)."""
    own = R.copy()
    lr = np.log1p(R)
    mom = np.expm1(lr.shift(1).rolling(11, min_periods=11).sum())
    regser = {}
    for c in SOVEREIGNS:
        mates = [k for k in SOVEREIGNS if reg[k] == reg[c] and k != c]
        regser[c] = R[mates].mean(axis=1, skipna=True)
    region = pd.DataFrame(regser)[SOVEREIGNS]
    return own, mom, region


def run_relation(vints, R, own, mom, region, tgtP, tgtS, months, rng=None):
    """Monthly ICs for one relation. If rng given, permute each focal row per vintage."""
    if rng is not None:
        perm_vints = []
        for af, w in vints:
            wp = w.copy()
            n = wp.shape[0]
            for i in range(n):
                idx = np.array([j for j in range(n) if j != i])
                wp[i, idx] = wp[i, rng.permutation(idx)]
            perm_vints.append((af, wp))
        vints = perm_vints
    icP, icS, ncty = [], [], []
    for m in months:
        w = pick_vintage(vints, m)
        if w is None:
            icP.append(np.nan); icS.append(np.nan); ncty.append(0); continue
        pw = partner_weighted(w, R.loc[m].to_numpy())
        X = np.column_stack([np.ones(len(SOVEREIGNS)), own.loc[m].to_numpy(),
                             mom.loc[m].to_numpy(), region.loc[m].to_numpy()])
        ok = ~np.isnan(pw) & ~np.isnan(X).any(axis=1)
        if ok.sum() < MIN_COUNTRIES:
            icP.append(np.nan); icS.append(np.nan); ncty.append(int(ok.sum())); continue
        beta, *_ = np.linalg.lstsq(X[ok], pw[ok], rcond=None)
        resid = np.full(len(SOVEREIGNS), np.nan)
        resid[ok] = pw[ok] - X[ok] @ beta
        out = []
        for tgt in (tgtP, tgtS):
            y = tgt.loc[m].to_numpy()
            k = ok & ~np.isnan(y)
            out.append(stats.spearmanr(resid[k], y[k]).statistic if k.sum() >= MIN_COUNTRIES else np.nan)
        icP.append(out[0]); icS.append(out[1]); ncty.append(int(ok.sum()))
    return np.array(icP), np.array(icS), np.array(ncty)


def main() -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    LOG.write_text("")
    t0 = time.time()
    d = daily_returns()
    mret, first, last_month = monthly_returns(d)
    R = mret[SOVEREIGNS]
    F = first[SOVEREIGNS]
    tgtP = R.shift(-1)
    tgtS = ((1 + R) / (1 + F) - 1).shift(-1)
    own, mom, region = build_controls(R, regions())
    log(f"monthly panel {R.index.min()}..{R.index.max()} (last complete {last_month}); "
        f"countries {R.shape[1]}")
    summary = {"last_complete_month": str(last_month), "relations": {}}
    frames = []
    rng = np.random.default_rng(20260923)
    for rel in RELATIONS:
        vints = load_vintages(rel)
        start = max(pd.Timestamp("2000-01-01"), vints[0][0]).to_period("M")
        months = [m for m in R.index if start <= m <= last_month - 1]
        icP, icS, nc = run_relation(vints, R, own, mom, region, tgtP, tgtS, months)
        tP, tS = tstat(icP), tstat(icS)
        log(f"{rel}: months={np.sum(~np.isnan(icP))} meanIC_P={np.nanmean(icP):+.4f} t_P={tP:+.2f} "
            f"NW={newey_west_t(icP):+.2f} | meanIC_S={np.nanmean(icS):+.4f} t_S={tS:+.2f} "
            f"NW={newey_west_t(icS):+.2f} | median countries {int(np.median(nc))}")
        null_t = []
        for rep in range(N_PLACEBO):
            pP, _, _ = run_relation(vints, R, own, mom, region, tgtP, tgtS, months, rng=rng)
            null_t.append(tstat(pP))
        null_t = np.array(null_t)
        pct = float((null_t < tP).mean())
        log(f"{rel}: placebo t_P mean {null_t.mean():+.2f}, 95th pct {np.percentile(null_t, 95):+.2f}; "
            f"real t at null percentile {pct:.3f}")
        df = pd.DataFrame({"month": [str(m) for m in months], "relation": rel,
                           "ic_P": icP, "ic_S": icS, "n_countries": nc})
        frames.append(df)
        eras = {}
        for name, (a, b) in ERAS.items():
            sel = [(pd.Period(a) <= m <= pd.Period(b)) for m in months]
            xP, xS = icP[sel], icS[sel]
            eras[name] = {"months": int(np.sum(~np.isnan(xP))),
                          "mean_ic_P": float(np.nanmean(xP)), "t_P": tstat(xP),
                          "mean_ic_S": float(np.nanmean(xS)), "t_S": tstat(xS)}
        passes_g2 = bool(tP >= 2.0)
        qualifies = bool(passes_g2 and tS >= 2.0)
        summary["relations"][rel] = {
            "first_month": str(months[0]), "last_month": str(months[-1]),
            "months_scored": int(np.sum(~np.isnan(icP))),
            "median_countries": int(np.median(nc)),
            "mean_ic_P": float(np.nanmean(icP)), "t_P": tP, "nw_t_P": newey_west_t(icP),
            "p_one_sided_P": float(stats.t.sf(tP, np.sum(~np.isnan(icP)) - 1)),
            "mean_ic_S": float(np.nanmean(icS)), "t_S": tS, "nw_t_S": newey_west_t(icS),
            "placebo_t_mean": float(null_t.mean()), "placebo_t_p95": float(np.percentile(null_t, 95)),
            "real_t_null_percentile": pct,
            "eras": eras,
            "convergence_flag_t_le_-2": bool(tP <= -2.0),
            "passes_G2": passes_g2, "qualifies_for_relational_experiment": qualifies,
        }
    # Holm across relations (one-sided p, primary)
    ps = sorted(((v["p_one_sided_P"], k) for k, v in summary["relations"].items()))
    m = len(ps)
    running = 0.0
    for rank, (p, k) in enumerate(ps):
        adj = min(1.0, max(running, (m - rank) * p))
        running = adj
        summary["relations"][k]["holm_p_P"] = adj
    summary["any_relation_passes_G2"] = any(v["passes_G2"] for v in summary["relations"].values())
    summary["any_relation_qualifies"] = any(v["qualifies_for_relational_experiment"]
                                            for v in summary["relations"].values())
    summary["elapsed_sec"] = round(time.time() - t0, 1)
    ics = pd.concat(frames, ignore_index=True)
    ics.to_parquet(RESULTS / "check_b_monthly_ic.parquet", index=False)
    ics["year"] = ics["month"].str[:4]
    yearly = ics.groupby(["relation", "year"])[["ic_P", "ic_S"]].mean().unstack("relation")
    with pd.ExcelWriter(RESULTS / "check_b_yearly_ic.xlsx") as xw:
        yearly.to_excel(xw, sheet_name="yearly_mean_ic")
        ics.drop(columns="year").to_excel(xw, sheet_name="monthly_ic", index=False)
    tmp = RESULTS / "check_b_g2.json.tmp"
    tmp.write_text(json.dumps(summary, indent=2))
    tmp.replace(RESULTS / "check_b_g2.json")
    # chart: cumulative IC, light mode
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=True)
    for ax, col, title in ((axes[0], "ic_P", "Next-month return"),
                           (axes[1], "ic_S", "Next month, first day skipped")):
        for rel in RELATIONS:
            s = ics[ics.relation == rel].set_index("month")[col].fillna(0).cumsum()
            ax.plot(pd.PeriodIndex(s.index, freq="M").to_timestamp(), s.values, label=rel)
        ax.axhline(0, color="#999999", lw=0.8)
        ax.axvline(pd.Timestamp("2024-01-01"), color="#bbbbbb", ls="--", lw=0.8)
        ax.set_title(title)
        ax.set_facecolor("white")
    axes[0].set_ylabel("Cumulative monthly IC of orthogonalized partner return")
    axes[0].legend(frameon=False)
    fig.patch.set_facecolor("white")
    fig.tight_layout()
    fig.savefig(RESULTS / "check_b_cumulative_ic.pdf")
    log(f"done in {summary['elapsed_sec']}s; any passes G2: {summary['any_relation_passes_G2']}; "
        f"any qualifies: {summary['any_relation_qualifies']}")


if __name__ == "__main__":
    main()
