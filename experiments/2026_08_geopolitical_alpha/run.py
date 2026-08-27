"""Run the preregistered geopolitical-alpha methodology experiment.

Inputs (read-only, absolute paths):
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/geopolitical_alpha/snapshot_2026_08_26/external_factors.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/geopolitical_alpha/snapshot_2026_08_26/country_returns_monthly.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/geopolitical_alpha/snapshot_2026_08_26/predmkt_signals_daily.parquet
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/geopolitical_alpha/snapshot_2026_08_26/predmkt_resolutions.parquet

Outputs (written only inside this experiment):
- experiments/2026_08_geopolitical_alpha/results/summary.json
- experiments/2026_08_geopolitical_alpha/results/monthly_diagnostics.csv
- experiments/2026_08_geopolitical_alpha/results/RESULTS.md
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


SNAPSHOT = Path(
    "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/"
    "Data/work/experiments/geopolitical_alpha/snapshot_2026_08_26"
)
HERE = Path(__file__).resolve().parent
OUT = HERE / "results"
MIN_COUNTRIES = 10


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def nw_t(values: pd.Series, lags: int = 6) -> float | None:
    x = pd.Series(values).dropna().to_numpy(float)
    n = len(x)
    if n < max(12, lags + 3):
        return None
    mu = float(x.mean())
    e = x - mu
    lrv = float(np.dot(e, e) / n)
    for lag in range(1, min(lags, n - 2) + 1):
        weight = 1.0 - lag / (lags + 1.0)
        gamma = float(np.dot(e[lag:], e[:-lag]) / n)
        lrv += 2.0 * weight * gamma
    if lrv <= 0:
        return None
    return mu / np.sqrt(lrv / n)


def monthly_ic(df: pd.DataFrame, signal: str, target: str, label: str) -> pd.DataFrame:
    rows = []
    for date, g in df[["date", signal, target]].dropna().groupby("date"):
        if len(g) < MIN_COUNTRIES or g[signal].nunique() < 3 or g[target].nunique() < 3:
            continue
        ic = spearmanr(g[signal], g[target]).statistic
        rows.append({"test": label, "date": date, "ic": float(ic), "n": len(g)})
    return pd.DataFrame(rows)


def cs_rank(s: pd.Series) -> pd.Series:
    return s.rank(method="average", pct=True) - 0.5


def build_panel() -> tuple[pd.DataFrame, dict]:
    ret_path = SNAPSHOT / "country_returns_monthly.parquet"
    gpr_path = SNAPSHOT / "external_factors.parquet"
    returns = pd.read_parquet(ret_path)
    returns["date"] = pd.to_datetime(returns["date"])
    returns = returns.sort_values(["country", "date"]).drop_duplicates(["country", "date"])

    grp = returns.groupby("country", group_keys=False)
    returns["fwd1"] = grp["return_1m"].shift(-1)
    r1 = grp["return_1m"].shift(-1)
    r2 = grp["return_1m"].shift(-2)
    r3 = grp["return_1m"].shift(-3)
    returns["fwd3"] = (1 + r1) * (1 + r2) * (1 + r3) - 1
    returns["mom12"] = grp["return_1m"].transform(
        lambda s: (1 + s).rolling(12, min_periods=12).apply(np.prod, raw=True) - 1
    )

    gpr = pd.read_parquet(gpr_path)
    gpr = gpr[gpr["variable"].eq("GPR")].copy()
    gpr["date"] = pd.to_datetime(gpr["date"])
    gpr = gpr.groupby(["country", "date"], as_index=False)["value"].mean()
    gpr = gpr.sort_values(["country", "date"])
    hist_mean = gpr.groupby("country")["value"].transform(
        lambda s: s.expanding(min_periods=60).mean().shift(1)
    )
    hist_std = gpr.groupby("country")["value"].transform(
        lambda s: s.expanding(min_periods=60).std(ddof=1).shift(1)
    )
    gpr["gpr_z"] = (gpr["value"] - hist_mean) / hist_std.replace(0, np.nan)
    # A monthly observation is not entitled until the following month.
    gpr["date"] = gpr["date"] + pd.offsets.MonthBegin(1)

    panel = returns.merge(gpr[["date", "country", "gpr_z"]], on=["date", "country"], how="inner")
    panel["gpr_cs"] = panel.groupby("date")["gpr_z"].transform(cs_rank)
    panel["ret1_cs"] = panel.groupby("date")["return_1m"].transform(cs_rank)
    panel["mom12_cs"] = panel.groupby("date")["mom12"].transform(cs_rank)
    panel["geo_reversal"] = panel["gpr_cs"] * (-panel["ret1_cs"])
    meta = {
        "rows": len(panel),
        "countries": int(panel["country"].nunique()),
        "country_list": sorted(panel["country"].unique().tolist()),
        "date_min": panel["date"].min().date().isoformat(),
        "date_max": panel["date"].max().date().isoformat(),
        "input_sha256": {ret_path.name: sha256(ret_path), gpr_path.name: sha256(gpr_path)},
    }
    return panel, meta


def ridge_predict(train: pd.DataFrame, test: pd.DataFrame, features: list[str], alpha: float = 10.0) -> np.ndarray:
    xtr = train[features].to_numpy(float)
    xte = test[features].to_numpy(float)
    y = train["target_cs"].to_numpy(float)
    mean = xtr.mean(axis=0)
    std = xtr.std(axis=0, ddof=1)
    std[std == 0] = 1.0
    xtr = (xtr - mean) / std
    xte = (xte - mean) / std
    xtr = np.column_stack([np.ones(len(xtr)), xtr])
    xte = np.column_stack([np.ones(len(xte)), xte])
    penalty = np.eye(xtr.shape[1]) * alpha
    penalty[0, 0] = 0.0
    beta = np.linalg.solve(xtr.T @ xtr + penalty, xtr.T @ y)
    return xte @ beta


def walk_forward(panel: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    d = panel.dropna(subset=["fwd1", "ret1_cs", "mom12_cs", "gpr_cs", "geo_reversal"]).copy()
    d["target_cs"] = d.groupby("date")["fwd1"].transform(cs_rank)
    years = sorted(d["date"].dt.year.unique())
    test_years = years[10:]
    rows = []
    for year in test_years:
        train = d[d["date"].dt.year < year]
        test = d[d["date"].dt.year == year].copy()
        if train["date"].nunique() < 60 or len(test) < 50:
            continue
        test["pred_base"] = ridge_predict(train, test, ["ret1_cs", "mom12_cs"])
        test["pred_aug"] = ridge_predict(
            train, test, ["ret1_cs", "mom12_cs", "gpr_cs", "geo_reversal"]
        )
        for date, g in test.groupby("date"):
            if len(g) < MIN_COUNTRIES:
                continue
            base = spearmanr(g["pred_base"], g["fwd1"]).statistic
            aug = spearmanr(g["pred_aug"], g["fwd1"]).statistic
            rows.append({"date": date, "year": year, "ic_base": base, "ic_aug": aug, "ic_diff": aug - base, "n": len(g)})
    wf = pd.DataFrame(rows)
    yearly = wf.groupby("year")["ic_diff"].mean() if not wf.empty else pd.Series(dtype=float)
    stats = {
        "months": len(wf),
        "test_years": int(wf["year"].nunique()) if not wf.empty else 0,
        "mean_ic_base": float(wf["ic_base"].mean()) if not wf.empty else None,
        "mean_ic_augmented": float(wf["ic_aug"].mean()) if not wf.empty else None,
        "mean_ic_improvement": float(wf["ic_diff"].mean()) if not wf.empty else None,
        "nw_t_improvement": nw_t(wf["ic_diff"], 6) if not wf.empty else None,
        "positive_year_fraction": float((yearly > 0).mean()) if len(yearly) else None,
    }
    t = stats["nw_t_improvement"]
    stats["proxy_pass"] = bool(
        stats["mean_ic_improvement"] is not None
        and stats["mean_ic_improvement"] > 0
        and t is not None and t >= 2.0
        and stats["positive_year_fraction"] is not None
        and stats["positive_year_fraction"] >= 0.60
    )
    return wf, stats


def exact_gap_audit() -> dict:
    sig = pd.read_parquet(SNAPSHOT / "predmkt_signals_daily.parquet")
    res = pd.read_parquet(SNAPSHOT / "predmkt_resolutions.parquet")
    sig["snapshot_date"] = pd.to_datetime(sig["snapshot_date"])
    dates = int(sig["snapshot_date"].nunique())
    names = sig["signal_name"].astype(str)
    has_constraint = bool(names.str.contains("constraint", case=False, regex=False).any())
    requirements = {
        "historical_constraint_probability": has_constraint,
        "market_probability_dates_at_least_60": dates >= 60,
        "resolved_markets_for_calibration": len(res) > 0,
    }
    return {
        "status": "READY" if all(requirements.values()) else "INSUFFICIENT",
        "requirements": requirements,
        "prediction_market_dates": dates,
        "date_min": sig["snapshot_date"].min().date().isoformat() if len(sig) else None,
        "date_max": sig["snapshot_date"].max().date().isoformat() if len(sig) else None,
        "resolved_market_rows": int(len(res)),
        "note": "GPR is not substituted for a historical constraint probability in this audit.",
    }


def fmt(x) -> str:
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "n/a"
    if isinstance(x, bool):
        return "PASS" if x else "FAIL"
    if isinstance(x, float):
        return f"{x:.4f}"
    return str(x)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    panel, panel_meta = build_panel()

    # Absolute return is the registered risk outcome; signed return is not used here.
    risk_panel = panel.copy()
    risk_panel["abs_fwd1"] = risk_panel["fwd1"].abs()
    risk_ic = monthly_ic(risk_panel, "gpr_cs", "abs_fwd1", "risk_abs_return")
    risk = {
        "months": len(risk_ic),
        "mean_ic": float(risk_ic["ic"].mean()) if len(risk_ic) else None,
        "nw_t": nw_t(risk_ic["ic"], 6) if len(risk_ic) else None,
    }
    risk["pass"] = bool(risk["mean_ic"] is not None and risk["mean_ic"] > 0 and risk["nw_t"] is not None and risk["nw_t"] >= 2.0)

    reversal_ic = monthly_ic(panel, "geo_reversal", "fwd3", "reversal_3m")
    reversal = {
        "months": len(reversal_ic),
        "mean_ic": float(reversal_ic["ic"].mean()) if len(reversal_ic) else None,
        "nw_t": nw_t(reversal_ic["ic"], 6) if len(reversal_ic) else None,
    }
    reversal["pass"] = bool(reversal["mean_ic"] is not None and reversal["mean_ic"] > 0 and reversal["nw_t"] is not None and reversal["nw_t"] >= 2.0)

    wf, incremental = walk_forward(panel)
    exact = exact_gap_audit()
    incremental["exact_gap_audit"] = exact
    incremental["pass"] = bool(incremental["proxy_pass"] and exact["status"] == "READY")

    summary = {
        "experiment_id": "M_20260826_001",
        "panel": panel_meta,
        "gate_1_risk": risk,
        "gate_2_reversal": reversal,
        "gate_3_incremental_alpha": incremental,
        "overall_verdict": "GRADUATED" if risk["pass"] and reversal["pass"] and incremental["pass"] else ("INSUFFICIENT" if exact["status"] == "INSUFFICIENT" else "DEAD"),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    diag = pd.concat([
        risk_ic,
        reversal_ic,
        wf.rename(columns={"ic_diff": "ic"}).assign(test="incremental_ic_diff")[["test", "date", "ic", "n"]],
    ], ignore_index=True)
    diag.to_csv(OUT / "monthly_diagnostics.csv", index=False)

    md = f"""# Results — Geopolitical alpha

**Methodology ledger:** `M_20260826_001`
**Overall verdict:** **{summary['overall_verdict']}**

The exact Marko Papic constraint-minus-market probability test is not currently identified by
ASADO's historical data. The GPR tests below are explicitly proxy diagnostics.

| Gate | Result | Mean IC / improvement | NW t | Other |
|---|---:|---:|---:|---|
| 1. Lagged GPR predicts absolute next-month return | {fmt(risk['pass'])} | {fmt(risk['mean_ic'])} | {fmt(risk['nw_t'])} | {risk['months']} months |
| 2. GPR x adverse-return predicts 3m reversal | {fmt(reversal['pass'])} | {fmt(reversal['mean_ic'])} | {fmt(reversal['nw_t'])} | {reversal['months']} months |
| 3a. Proxy features improve walk-forward rank IC | {fmt(incremental['proxy_pass'])} | {fmt(incremental['mean_ic_improvement'])} | {fmt(incremental['nw_t_improvement'])} | positive years {fmt(incremental['positive_year_fraction'])} |
| 3b. Exact constraint-market gap is test-ready | {exact['status']} | — | — | {exact['prediction_market_dates']} dates; {exact['resolved_market_rows']} resolutions |

## Interpretation

- The panel contains {panel_meta['rows']:,} observations across {panel_meta['countries']} countries,
  from {panel_meta['date_min']} through {panel_meta['date_max']}.
- Gate 1 tests risk prediction, not directional return alpha.
- Gate 2 is a frozen interaction proxy. It does not prove that a constraint forecast disagreed
  with the market; it only asks whether lagged GPR changes the usual adverse-return reversal.
- Gate 3a is expanding annual walk-forward and compares against returns-only controls. Gate 3b
  prevents that proxy from being relabeled as the exact Papic framework.
- Exact readiness failed because requirements were: {json.dumps(exact['requirements'], sort_keys=True)}.

## Reproduction

Run `run.py` with the ASADO production interpreter. Input hashes are recorded in `summary.json`.
"""
    (OUT / "RESULTS.md").write_text(md)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
