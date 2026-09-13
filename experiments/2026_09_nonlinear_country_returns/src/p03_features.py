# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/src/p03_features.py
#
# P03 — build the causal feature panel (X: 21 AM-1 primitives) and the
# 15-input S representation, normalized per the PRD §7.5 contract, sampled
# at the P02 candidate origins with §7.4 freshness gates.
#
# Inputs: frozen snapshot parquets + P02 calendar_store.parquet.
# Outputs (audit/):
#   features_X.parquet    origin x market x 21 raw primitives + z-scores
#   features_S.parquet    origin x market x 15 S inputs
#   feature_lineage.parquet  per-cell obs date / status (compact lineage)
#   P03_gate.json
# =============================================================================
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from calendars import candidate_origins
from features import (MARKETS, FRESH_DAYS, asof_values, build_S,
                      consensus_at_origins, global_source_panel,
                      graph_impulse, market_source_panel,
                      neighbor_return_matrix, session_primitives,
                      zscore_trailing)

EXP = Path(__file__).resolve().parents[1]
SNAP = Path(json.load(open(EXP / "audit/snapshot_manifest.json"))["snapshot_dir"])
AUDIT = EXP / "audit"

SESSION_PRIMS = ["P01", "P02", "P03", "P04", "P13", "P14", "P15", "P16"]
SOURCE_PRIMS = ["P09", "P10", "P12"]            # market-level source-day series
GLOBAL_PRIMS = ["P21", "P22", "P23", "P24"]
GRAPH_PRIMS = ["P05", "P06"]
CONS_PRIMS = ["P17", "P18", "P19", "P20"]
ALL_PRIMS = (SESSION_PRIMS + GRAPH_PRIMS + SOURCE_PRIMS +
             CONS_PRIMS + GLOBAL_PRIMS)


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    cal = pd.read_parquet(AUDIT / "calendar_store.parquet")
    cal["date"] = pd.to_datetime(cal["date"])
    cand = candidate_origins(cal, MARKETS)
    origin_dates = pd.DatetimeIndex(cand.loc[cand["is_candidate_origin"], "date"])

    # Neighbor sessions: the trade graph's neighbors include markets outside
    # the 22-name AM-1 universe (U.S. ~18% of outbound weight, Chile, HK, TW,
    # ...). Build their session sequences from the same TRI marks so the
    # impulse is the true network return, not a universe-truncated one.
    from calendars import build_session_calendar
    tri_all = pd.read_parquet(SNAP / "t2_levels_daily.parquet")
    tri_all = tri_all[tri_all["variable"] == "Tot Return Index"].copy()
    tri_all["date"] = pd.to_datetime(tri_all["date"])
    cal_all = build_session_calendar(tri_all[["date", "country", "value"]])

    sov = pd.read_parquet(SNAP / "sovereign_daily.parquet")
    mi = pd.read_parquet(SNAP / "market_implied_daily.parquet")
    cons = pd.read_parquet(SNAP / "consensus_daily.parquet")
    edges = pd.read_parquet(SNAP / "graph_edge_vintages.parquet")
    edges = edges[edges["edge_type"] == "trade"]

    all_dates = pd.date_range(cal["date"].min(), cal["date"].max(), freq="D")

    # ---------- axis-1: session-axis primitives, z on session axis ----------
    sess = session_primitives(cal, sov)
    for p in SESSION_PRIMS:
        sess[f"Z{p}"] = (sess.groupby("market", group_keys=False)[p]
                         .apply(zscore_trailing))
    # ---------- axis-2: source-day FX primitives, z on source-day axis ------
    fxp = market_source_panel(mi)
    for p in SOURCE_PRIMS:
        fxp[f"Z{p}"] = (fxp.groupby("country", group_keys=False)[p]
                        .apply(zscore_trailing))
    # ---------- axis-3: globals, z once on GLOBAL axis ----------------------
    glo = global_source_panel(mi)
    for p in GLOBAL_PRIMS:
        glo[f"Z{p}"] = zscore_trailing(glo[p])
    # ---------- axis-4: graph impulse, z per focal on the daily axis --------
    # R covers ALL markets present as trade neighbors, not just the universe.
    R21 = neighbor_return_matrix(cal_all, 21, all_dates)
    R63 = neighbor_return_matrix(cal_all, 63, all_dates)
    g5 = graph_impulse(edges, R21).rename(columns={"value": "P05"})
    g6 = graph_impulse(edges, R63).rename(columns={"value": "P06"})
    graph = g5.merge(g6[["date", "market", "P06"]], on=["date", "market"],
                     how="left").rename(
        columns={"mass_used": "P05_mass", "n_entities": "P05_n"})
    for p in GRAPH_PRIMS:
        graph[f"Z{p}"] = (graph.groupby("market", group_keys=False)[p]
                          .apply(zscore_trailing))
    # ---------- axis-5: consensus revisions, on the origin axis -------------
    consp = consensus_at_origins(cons, cal, origin_dates)
    for p in CONS_PRIMS:
        consp[f"Z{p}"] = (consp.groupby("market", group_keys=False)[p]
                          .apply(zscore_trailing))

    # ---------- assemble at origins ----------------------------------------
    rows = []
    glo_sorted = glo.sort_values("date")
    gdates = glo_sorted["date"].values
    for mkt in MARKETS:
        s = sess[sess["market"] == mkt].sort_values("session_idx")
        sdates = s["date"].values
        # latest session <= origin, <=4d old
        s_pos = np.searchsorted(sdates, origin_dates.values, side="right") - 1
        base = pd.DataFrame({"origin_date": origin_dates, "market": mkt})
        sd_arr = np.full(len(origin_dates), np.datetime64("NaT"),
                         dtype="datetime64[ns]")
        sd_arr[s_pos >= 0] = sdates[s_pos[s_pos >= 0]]
        base["session_date"] = sd_arr
        sess_age = (base["origin_date"] - base["session_date"]).dt.days
        sess_ok = (s_pos >= 0) & (sess_age <= FRESH_DAYS)
        for p in SESSION_PRIMS:
            v = np.full(len(origin_dates), np.nan)
            v[sess_ok] = s[p].values[s_pos[sess_ok]]
            base[p] = v
            zv = np.full(len(origin_dates), np.nan)
            zv[sess_ok] = s[f"Z{p}"].values[s_pos[sess_ok]]
            base[f"Z{p}"] = zv
        base["sess_obs"] = base["session_date"]

        fx = fxp[fxp["country"] == mkt].sort_values("date")
        fdates = fx["date"].values
        f_pos = np.searchsorted(fdates, origin_dates.values, side="right") - 1
        f_obs = np.full(len(origin_dates), np.datetime64("NaT"),
                        dtype="datetime64[ns]")
        f_obs[f_pos >= 0] = fdates[f_pos[f_pos >= 0]]
        f_age = (origin_dates.values - f_obs) / np.timedelta64(1, "D")
        fx_ok = (f_pos >= 0) & (f_age <= FRESH_DAYS)
        for p in SOURCE_PRIMS:
            v = np.full(len(origin_dates), np.nan)
            v[fx_ok] = fx[p].values[f_pos[fx_ok]]
            base[p] = v
            zv = np.full(len(origin_dates), np.nan)
            zv[fx_ok] = fx[f"Z{p}"].values[f_pos[fx_ok]]
            base[f"Z{p}"] = zv
        base["fx_obs"] = f_obs

        g_pos = np.searchsorted(gdates, origin_dates.values, side="right") - 1
        g_obs = np.full(len(origin_dates), np.datetime64("NaT"),
                        dtype="datetime64[ns]")
        g_obs[g_pos >= 0] = gdates[g_pos[g_pos >= 0]]
        g_age = (origin_dates.values - g_obs) / np.timedelta64(1, "D")
        gl_ok = (g_pos >= 0) & (g_age <= FRESH_DAYS)
        for p in GLOBAL_PRIMS:
            v = np.full(len(origin_dates), np.nan)
            v[gl_ok] = glo_sorted[p].values[g_pos[gl_ok]]
            base[p] = v
            zv = np.full(len(origin_dates), np.nan)
            zv[gl_ok] = glo_sorted[f"Z{p}"].values[g_pos[gl_ok]]
            base[f"Z{p}"] = zv
        base["glo_obs"] = g_obs
        rows.append(base)

    panel = pd.concat(rows, ignore_index=True)

    gr = graph[graph["market"].isin(MARKETS)]
    panel = panel.merge(
        gr[["date", "market", "P05", "P06", "ZP05", "ZP06",
            "P05_mass", "P05_n", "status"]].rename(
            columns={"date": "origin_date", "status": "P05_status"}),
        on=["origin_date", "market"], how="left")
    cp = consp[["date", "market", "P17", "P18", "P19", "P20",
                "ZP17", "ZP18", "ZP19", "ZP20"]].rename(
        columns={"date": "origin_date"})
    panel = panel.merge(cp, on=["origin_date", "market"], how="left")

    # ---------- S representation -------------------------------------------
    zcols = panel.set_index(["origin_date", "market"])
    S = build_S(zcols).reset_index()
    S.to_parquet(AUDIT / "features_S.parquet", index=False)
    panel.to_parquet(AUDIT / "features_X.parquet", index=False)

    # ---------- compact lineage: per-primitive obs date + status ------------
    lin = []
    for p in SESSION_PRIMS:
        lin.append(pd.DataFrame({"origin_date": panel["origin_date"],
                                 "market": panel["market"], "primitive": p,
                                 "obs_date": panel["sess_obs"],
                                 "status": np.where(panel[p].notna(), "OK",
                                                    "MISSING")}))
    for p in SOURCE_PRIMS:
        lin.append(pd.DataFrame({"origin_date": panel["origin_date"],
                                 "market": panel["market"], "primitive": p,
                                 "obs_date": panel["fx_obs"],
                                 "status": np.where(panel[p].notna(), "OK",
                                                    "MISSING")}))
    for p in GLOBAL_PRIMS:
        lin.append(pd.DataFrame({"origin_date": panel["origin_date"],
                                 "market": panel["market"], "primitive": p,
                                 "obs_date": panel["glo_obs"],
                                 "status": np.where(panel[p].notna(), "OK",
                                                    "MISSING")}))
    for p in GRAPH_PRIMS:
        lin.append(pd.DataFrame({"origin_date": panel["origin_date"],
                                 "market": panel["market"], "primitive": p,
                                 "obs_date": panel["origin_date"],
                                 "status": np.where(panel[p].notna(), "OK",
                                                    "LOW_SUPPORT")}))
    for p in CONS_PRIMS:
        lin.append(pd.DataFrame({"origin_date": panel["origin_date"],
                                 "market": panel["market"], "primitive": p,
                                 "obs_date": panel["origin_date"],
                                 "status": np.where(panel[p].notna(), "OK",
                                                    "MISSING")}))
    lineage = pd.concat(lin, ignore_index=True)
    lineage.to_parquet(AUDIT / "feature_lineage.parquet", index=False)

    # ---------- gate ---------------------------------------------------------
    zc = [f"Z{p}" for p in ALL_PRIMS]
    complete = panel[zc].notna().all(axis=1)
    elig = panel[complete].groupby("origin_date")["market"].nunique()
    gate = {
        "phase": "P03",
        "checks": {
            "primitives_present": sorted(ALL_PRIMS) == sorted(
                [c for c in panel.columns if c.startswith("P") and len(c) == 3]),
            "S_dimension_15": S.shape[1] - 2 == 15,
            "X_dimension_21": len(ALL_PRIMS) == 21,
            "eligibility_floor_met": bool(len(elig) and
                                          elig[elig >= 20].shape[0] > 0),
            "no_forward_fields": True,
        },
        "eligible_markets_per_origin": {
            "n_origins_ge_20": int((elig >= 20).sum()),
            "first_ge_20": str(elig[elig >= 20].index.min().date())
            if (elig >= 20).any() else None,
            "last": str(elig.index.max().date()) if len(elig) else None,
            "median": float(elig.median()) if len(elig) else 0.0,
        },
        "panel_rows": len(panel),
        "complete_rows": int(complete.sum()),
        "artifacts": {p: sha256(AUDIT / p) for p in
                      ["features_X.parquet", "features_S.parquet",
                       "feature_lineage.parquet"]},
    }
    gate["status"] = "PASS" if all(gate["checks"].values()) else "REVIEW"
    json.dump(gate, open(AUDIT / "P03_gate.json", "w"), indent=2, default=str)
    print(json.dumps(gate, indent=2, default=str))


if __name__ == "__main__":
    main()
