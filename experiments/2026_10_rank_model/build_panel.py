#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: experiments/2026_10_rank_model/build_panel.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_rank_model/results/screen_20261007_100004/factor_screen.parquet
    The univariate screen (factor_screen.py): one row per factor with its
    t-stat, publication lag and duplicate-group ids. Defines the candidate list.
    Override with --screen.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/snapshot_2026_10_07/feature_panel_observed.parquet
    Frozen `feature_panel_observed`: factor z-scores and the target `1MRet`.

OUTPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_rank_model/factor_set_<version>.json
    The selected factor list with the rules that produced it (committed config).
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model/panel_<version>/feature_panel_<version>.parquet
    Model-ready panel, one row per (date, country): every selected factor as a
    column with its publication lag already applied, plus the target columns
    fwd_ret (1MRet), bench_ret (equal-weight mean of all countries that month)
    and fwd_excess = fwd_ret - bench_ret.
- .../panel_<version>/factor_set_<version>.xlsx       the factor list, for eyeballing
- .../panel_<version>/panel_manifest.json             shape, coverage, lags, inputs
- .../panel_<version>/build.log

VERSION: 1.0
LAST UPDATED: 2026-10-07
AUTHOR: Claude (Fable 5.1) for Arjun Divecha

DESCRIPTION:
Turns Arjun's factor selection into a frozen modelling panel.

Selection rules (v1, Arjun 2026-10-07): keep every factor the screen could
score (a t-stat exists: >= 24 usable months with >= 20 countries), then drop
the price-level and market-cap series PX_LAST, MCAP and MCAP Adj in both
normalizations, keeping Mcap Weights.

Lag convention (matches factor_screen.py and the harness): a factor from a
zero-lag source (t2, gdelt) is used as stored; a factor from any other source
is shifted forward by its publication lag so that the row for month D holds
the value that was available at D. The target for row D is the return over
the month after D. That makes every row "information at D -> return after D"
and the model script never has to think about lags again.

Nothing is imputed, clipped or scaled here; the panel keeps NaN where the
source has no value so each model can treat missingness its own way.

DEPENDENCIES: pandas, numpy, pyarrow, xlsxwriter (ASADO venv is enough)

USAGE:
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
  ./venv/bin/python experiments/2026_10_rank_model/build_panel.py
  ./venv/bin/python experiments/2026_10_rank_model/build_panel.py --version v2 --drop-bases "PX_LAST,MCAP"
=============================================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

EXP_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_rank_model")
WORK_DIR = Path("/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/work/experiments/2026_10_rank_model")
SNAPSHOT = WORK_DIR / "snapshot_2026_10_07" / "feature_panel_observed.parquet"
DEFAULT_SCREEN = EXP_DIR / "results" / "screen_20261007_100004" / "factor_screen.parquet"
RETURN_VARIABLE, RETURN_SOURCE = "1MRet", "t2"

log = logging.getLogger("build_panel")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--screen", type=Path, default=DEFAULT_SCREEN)
    ap.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    ap.add_argument("--version", default="v1")
    ap.add_argument("--drop-bases", default="PX_LAST,MCAP,MCAP Adj",
                    help="comma-separated base_variable names to drop (both _CS and _TS)")
    args = ap.parse_args()

    t0 = time.time()
    out_dir = WORK_DIR / f"panel_{args.version}"
    out_dir.mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    log.setLevel(logging.INFO)
    for h in (logging.StreamHandler(sys.stdout), logging.FileHandler(out_dir / "build.log", mode="w")):
        h.setFormatter(fmt)
        log.addHandler(h)

    # ── 1. factor selection ────────────────────────────────────────────────
    screen = pd.read_parquet(args.screen)
    drop_bases = [b.strip() for b in args.drop_bases.split(",") if b.strip()]
    scored = screen[screen["fm_t"].notna()]
    dropped = scored[scored["base_variable"].isin(drop_bases)]
    selected = scored[~scored["base_variable"].isin(drop_bases)].copy()
    log.info("screen rows=%d scored=%d dropped(by base %s)=%d selected=%d",
             len(screen), len(scored), drop_bases, len(dropped), len(selected))
    log.info("dropped: %s", dropped["variable"].tolist())
    cl80 = next((c for c in selected.columns if c.startswith("cluster_abs_rho_ge_0.80")), None)
    keep_cols = ["rank_by_abs_t", "variable", "base_variable", "normalization", "source", "lag_months",
                 "n_months", "mean_n_countries", "fm_t", "rank_ic_t", "top8_excess_ann_pct", "top8_hit_rate"]
    if cl80:
        keep_cols.append(cl80)
    selected = selected[keep_cols].sort_values("rank_by_abs_t").reset_index(drop=True)

    factor_set = {
        "version": args.version,
        "created": datetime.now().isoformat(timespec="seconds"),
        "screen_run": str(args.screen),
        "snapshot": str(args.snapshot),
        "rules": [
            "keep every factor with a screen t-stat (>= 24 usable months of >= 20 countries)",
            f"drop base variables {drop_bases} in both _CS and _TS",
        ],
        "n_factors": int(len(selected)),
        "by_source": selected["source"].value_counts().to_dict(),
        "by_normalization": selected["normalization"].value_counts().to_dict(),
        "by_lag_months": {str(k): int(v) for k, v in selected["lag_months"].value_counts().items()},
        "dropped": dropped["variable"].tolist(),
        "factors": selected.to_dict("records"),
    }
    p_json = EXP_DIR / f"factor_set_{args.version}.json"
    p_json.write_text(json.dumps(factor_set, indent=2, default=str))
    selected.to_excel(out_dir / f"factor_set_{args.version}.xlsx", index=False, na_rep="—")
    log.info("factor set: %d factors -> %s", len(selected), p_json)

    # ── 2. target ──────────────────────────────────────────────────────────
    df = pd.read_parquet(args.snapshot, columns=["date", "country", "value", "variable", "source"])
    df["date"] = pd.to_datetime(df["date"])
    ret = df[(df["variable"] == RETURN_VARIABLE) & (df["source"] == RETURN_SOURCE)]
    R = ret.pivot_table(index="date", columns="country", values="value").sort_index()
    countries = list(R.columns)
    full_idx = pd.date_range(R.index.min(), df["date"].max(), freq="MS")
    R = R.reindex(full_idx)
    bench = R.mean(axis=1)
    E = R.sub(bench, axis=0)
    log.info("target: %s months with returns, %d countries, %s -> %s",
             int(R.notna().any(axis=1).sum()), len(countries), R.index.min().date(), R.index.max().date())

    # ── 3. features with lag applied ───────────────────────────────────────
    lag_of = dict(zip(selected["variable"], selected["lag_months"].astype(int)))
    feats = df[df["variable"].isin(lag_of)]
    # the gdelt panel carries its own copy of some t2 names; keep one row per (date, country, variable)
    dup = feats.duplicated(["date", "country", "variable"]).sum()
    if dup:
        log.warning("%d duplicate (date,country,variable) rows in features -- averaging", dup)
    wide = feats.pivot_table(index="date", columns=["variable", "country"], values="value", aggfunc="mean")
    wide = wide.reindex(full_idx)

    blocks = {}
    for v, lag in lag_of.items():
        Z = wide[v].reindex(columns=countries) if v in wide.columns.get_level_values(0) else pd.DataFrame(np.nan, index=full_idx, columns=countries)
        blocks[v] = Z.shift(lag) if lag else Z   # row D now holds the value available at D
    X = pd.concat(blocks, axis=1)                 # columns: (variable, country)
    X = X.stack(level=1, future_stack=True)       # index: (date, country), columns: variable
    X.index.names = ["date", "country"]

    tgt = pd.DataFrame({
        "fwd_ret": R.stack(future_stack=True),
        "bench_ret": bench.reindex(R.index).repeat(len(countries)).values if False else np.repeat(bench.values, len(countries)),
        "fwd_excess": E.stack(future_stack=True),
    })
    tgt.index.names = ["date", "country"]
    tgt["n_countries_ret"] = np.repeat(R.notna().sum(axis=1).values, len(countries))

    panel = tgt.join(X, how="left")
    panel = panel[panel["fwd_ret"].notna()].sort_index()
    feat_cols = list(lag_of)
    panel["n_features_present"] = panel[feat_cols].notna().sum(axis=1)
    panel = panel.reset_index()

    # ── 4. coverage report ─────────────────────────────────────────────────
    cov = panel[feat_cols].notna().mean().sort_values()
    by_year = panel.groupby(panel["date"].dt.year)["n_features_present"].mean().round(1)
    log.info("panel: %d rows (date,country), %d features, %s -> %s",
             len(panel), len(feat_cols), panel["date"].min().date(), panel["date"].max().date())
    log.info("feature coverage: median %.2f, min %.2f (%s), max %.2f", cov.median(), cov.min(), cov.idxmin(), cov.max())
    log.info("mean features present per row by year: %s", by_year.to_dict())

    p_panel = out_dir / f"feature_panel_{args.version}.parquet"
    panel.to_parquet(p_panel, index=False)
    manifest = {
        "version": args.version,
        "created": datetime.now().isoformat(timespec="seconds"),
        "factor_set": str(p_json),
        "snapshot": str(args.snapshot),
        "panel": str(p_panel),
        "rows": int(len(panel)),
        "n_features": len(feat_cols),
        "countries": countries,
        "date_min": str(panel["date"].min().date()),
        "date_max": str(panel["date"].max().date()),
        "target": {"fwd_ret": f"{RETURN_VARIABLE} ({RETURN_SOURCE}) = return over the month after `date`",
                   "bench_ret": "equal-weight mean fwd_ret over all countries with a return that month",
                   "fwd_excess": "fwd_ret - bench_ret"},
        "lag_rule": "features from non-t2/gdelt sources shifted forward by lag_months so row D holds the value available at D",
        "features_by_lag": {str(k): int(v) for k, v in pd.Series(lag_of).value_counts().items()},
        "feature_coverage": cov.round(4).to_dict(),
        "mean_features_present_by_year": {str(k): float(v) for k, v in by_year.items()},
        "elapsed_s": round(time.time() - t0, 1),
    }
    (out_dir / "panel_manifest.json").write_text(json.dumps(manifest, indent=2))
    log.info("wrote %s", p_panel)
    log.info("done in %.1fs", time.time() - t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
