# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/src/pseudolabels.py
#
# PRD 11.2 — conditional-forecasting pseudo-labels for the P07 control
# studies. Parameters are FROZEN at P06 (protocol.lock.json
# .synthetic_generators); the generator reads features, the frozen
# parameters, and the real clock/maturity metadata — it NEVER reads a real
# label value (T46).
#
#   y_sim(t,m) = mu(t,m) + noise(t,m) + gamma * h(t,m)
#
#   mu    = a + X_raw @ beta_raw            (frozen dev-window ridge)
#   noise = overlapping 20-local-session sums of common AR(0.8) + idio
#           AR(0.3) shocks, 50/50 variance share, scaled to sigma_noise
#   h     = C04*C06 - dev projection on [1, X_raw]   (frozen projection)
#   gamma = sqrt(q/(1-q)) * sigma_noise / sd_dev(h)  (q from the locked grid)
# =============================================================================
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

EXP = Path(__file__).resolve().parents[1]
AUDIT = EXP / "audit"
GOV = EXP / "governance"

P_COLS = ["P01", "P02", "P03", "P04", "P05", "P06", "P09", "P10", "P12",
          "P13", "P14", "P15", "P16", "P17", "P18", "P19", "P20",
          "P21", "P22", "P23", "P24"]


def _lock() -> dict:
    return json.loads((GOV / "protocol.lock.json").read_text())


def gen_seed(rep: int, q_index: int, master: int) -> int:
    return (master + 1_000_003 * q_index + rep) % (2 ** 31)


def _ar1(n: int, phi: float, rng: np.random.RandomState) -> np.ndarray:
    """Stationary unit-variance AR(1) of length n."""
    e = np.empty(n)
    e[0] = rng.randn()
    sd_u = np.sqrt(1 - phi ** 2)
    for t in range(1, n):
        e[t] = phi * e[t - 1] + sd_u * rng.randn()
    return e


def generate(q: float, rep: int, out_path: str | Path | None = None
             ) -> pd.DataFrame:
    """Build a pseudo-label frame with the real labels' schema:
    (origin_date, market, entry_date, exit_date, tri_entry, tri_exit,
     label, outcome_status, horizon). horizon='h20' only — controls run the
    20-session contract. Label values are synthetic; all timing metadata is
    real (the maturity structure is part of the contract)."""
    lock = _lock()
    g = lock["synthetic_generators"]
    master = lock["selection"]["master_seed"]
    rng = np.random.RandomState(gen_seed(rep, int(round(q * 1000)), master))

    X = pd.read_parquet(AUDIT / "features_X.parquet")
    S = pd.read_parquet(AUDIT / "features_S.parquet")
    lab = pd.read_parquet(AUDIT / "labels.parquet")
    for df in (X, S, lab):
        df["origin_date"] = pd.to_datetime(df["origin_date"])
    lab = lab[lab["horizon"] == "h20"].copy()
    lab["exit_date"] = pd.to_datetime(lab["exit_date"])
    lab["entry_date"] = pd.to_datetime(lab["entry_date"])

    df = (lab[["origin_date", "market", "entry_date", "exit_date",
               "outcome_status"]]
          .merge(X[["origin_date", "market"] + P_COLS],
                 on=["origin_date", "market"], how="left")
          .merge(S[["origin_date", "market", "C04", "C06"]],
                 on=["origin_date", "market"], how="left"))

    # fixed linear mean on raw primitives
    Xr = df[P_COLS].to_numpy()
    mu = g["linear_mean_intercept_raw"] + \
        Xr @ np.asarray(g["linear_mean_beta_raw"])
    mu = np.where(np.isfinite(mu), mu, 0.0)

    # interaction term, orthogonalized by the frozen projection
    h_raw = df["C04"].to_numpy() * df["C06"].to_numpy()
    proj = np.asarray(g["h_projection_coef"])
    Ah = np.column_stack([np.ones(len(df)), np.nan_to_num(Xr)])
    h_orth = np.nan_to_num(h_raw) - Ah @ proj
    h_orth = np.where(np.isfinite(h_orth), h_orth, 0.0)
    gamma = (np.sqrt(q / (1 - q)) * g["sigma_noise"] / g["h_orth_sd"]
             if q > 0 else 0.0)

    # ---- shocks on a daily calendar axis covering every label session ---
    day0 = df["entry_date"].min()
    day1 = df["exit_date"].max() + pd.Timedelta(days=10)
    days = pd.date_range(day0, day1, freq="D")
    didx = {d: i for i, d in enumerate(days)}
    n = len(days)
    e_c = _ar1(n, g["ar_coef_common"], rng)                 # common
    markets = np.sort(df["market"].unique())
    e_i = {m: _ar1(n, g["ar_coef_idio"], rng) for m in markets}  # idio

    # noise(t,m) = sum over the 20 label sessions of e_c + e_i.
    # The label's 20 local sessions are entry..exit on the market's session
    # calendar; the calendar store gives each market's real sessions.
    cal = pd.read_parquet(AUDIT / "calendar_store.parquet")
    cal["date"] = pd.to_datetime(cal["date"])
    sess = {m: np.sort(cal.loc[cal["market"] == m, "date"].unique())
            for m in markets}

    noise = np.zeros(len(df))
    for m in markets:
        idx = df.index[df["market"] == m]
        sess_m = sess[m]
        pos = np.searchsorted(sess_m, df.loc[idx, "entry_date"].to_numpy())
        for i, p0 in zip(idx, pos):
            win = sess_m[p0:p0 + 20]
            if len(win) == 0:
                continue
            di = np.array([didx[d] for d in win])
            noise[i] = e_c[di].sum() + e_i[m][di].sum()

    # equal variance shares -> each of common/idio contributes ~half of the
    # raw noise variance; scale the total to sigma_noise on the dev window
    dev_lo, dev_hi = (pd.Timestamp(g["dev_window"][0]),
                      pd.Timestamp(g["dev_window"][1]))
    dev_mask = ((df["origin_date"] >= dev_lo) &
                (df["origin_date"] < dev_hi)).to_numpy()
    sd_raw = noise[dev_mask].std()
    noise *= g["sigma_noise"] / sd_raw

    out = lab.copy()
    out["label"] = mu + noise + gamma * h_orth
    out["tri_entry"] = np.nan
    out["tri_exit"] = np.nan
    out = out[["origin_date", "market", "entry_date", "exit_date",
               "tri_entry", "tri_exit", "label", "outcome_status", "horizon"]]
    if out_path:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        out.to_parquet(out_path, index=False)
    return out


if __name__ == "__main__":
    import sys
    q = float(sys.argv[1]) if len(sys.argv) > 1 else 0.0
    rep = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    out = sys.argv[3] if len(sys.argv) > 3 else None
    df = generate(q, rep, out)
    print(f"q={q} rep={rep} rows={len(df)} label_sd={df.label.std():.4f}")
