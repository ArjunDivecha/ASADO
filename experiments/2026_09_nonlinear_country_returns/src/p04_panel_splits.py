# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/src/p04_panel_splits.py
#
# P04 — freeze the common sample (ex-ante candidate rows -> eligible rows ->
# scored origins) and the chronological nested split schedule (PRD 8.3/8.4).
#
#   audit/candidate_rows.parquet  (origin x market, the 22-universe rows at
#                                >=20-session candidate origins — ex-ante)
#   audit/eligible_rows.parquet   (complete-case rows at scored origins:
#                                origins with >=20 eligible markets)
#   audit/splits.json             (outer quarterly fit schedule + per-July
#                                inner 4x6-month validation blocks)
#   audit/P04_gate.json           (hashes + checks)
#
# Outer rule (8.3): fit cutoff = 00:00 UTC on first scored origin on/after
# each Jan/Apr/Jul/Oct 1; first fit = first July cutoff >= panel start + 8y
# where panel start = first scored origin (bound interpretation). Training
# window = scored origins in [F-8y, F) with label mature strictly before F.
# Inner rule (8.4): right anchor = latest fully-mature training origin;
# 4 consecutive 6-calendar-month validation blocks ending at anchor; inner
# fits at each block start and +3 months, training on earlier mature labels
# within the fixed outer-window start.
# =============================================================================
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from features import ALL_PRIMS, MARKETS

EXP = Path(__file__).resolve().parents[1]
AUDIT = EXP / "audit"
MIN_MARKETS = 20
OUTER_WINDOW_YEARS = 8
MIN_INNER_TRAIN_ORIGINS = 1260


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def keys_hash(df: pd.DataFrame, cols) -> str:
    k = df[cols].astype(str).agg("|".join, axis=1).sort_values()
    return hashlib.sha256("|".join(k).encode()).hexdigest()


def main() -> None:
    X = pd.read_parquet(AUDIT / "features_X.parquet")
    X["origin_date"] = pd.to_datetime(X["origin_date"])
    out = pd.read_parquet(AUDIT / "outcome_status.parquet")
    lab = pd.read_parquet(AUDIT / "labels.parquet")
    h20 = lab[lab["horizon"] == "h20"][["origin_date", "market", "exit_date",
                                       "outcome_status"]].copy()
    h20["origin_date"] = pd.to_datetime(h20["origin_date"])

    # ---- 1. ex-ante candidate rows (never filtered by outcome existence) ---
    cand = X[["origin_date", "market"]].drop_duplicates()
    cand.to_parquet(AUDIT / "candidate_rows.parquet", index=False)

    # ---- 2. eligible rows = complete case over the 21 z'd primitives ------
    zc = [f"Z{p}" for p in ALL_PRIMS]
    eli = X.loc[X[zc].notna().all(axis=1), ["origin_date", "market"]].copy()
    n_el = eli.groupby("origin_date")["market"].nunique().rename("n_eligible")
    scored = n_el[n_el >= MIN_MARKETS].index
    eli = eli[eli["origin_date"].isin(scored)]
    eli["n_eligible"] = eli["origin_date"].map(n_el)
    eli = eli.merge(h20, on=["origin_date", "market"], how="left")
    eli.to_parquet(AUDIT / "eligible_rows.parquet", index=False)

    scored_origins = pd.DatetimeIndex(sorted(scored))
    panel_start = scored_origins.min()

    # ---- 3. outer schedule -------------------------------------------------
    def first_origin_on_or_after(d):
        i = scored_origins.searchsorted(pd.Timestamp(d))
        return scored_origins[i] if i < len(scored_origins) else None

    # First fit = first JULY cutoff >= panel_start + 8y (spec 8.3); quarterly
    # cadence (Jan/Apr/Jul/Oct) begins from that first fit onward.
    first_fit_day = panel_start + pd.DateOffset(years=OUTER_WINDOW_YEARS)
    first_july = pd.Timestamp(first_fit_day.year, 7, 1)
    if first_july < first_fit_day:
        first_july += pd.DateOffset(years=1)
    q_months = [1, 4, 7, 10]
    fit_days = []
    for y in range(first_july.year, scored_origins.max().year + 2):
        for m in q_months:
            qd = pd.Timestamp(y, m, 1)
            if qd < first_july:
                continue
            o = first_origin_on_or_after(qd)
            if o is not None:
                fit_days.append((o, m == 7))
    # de-dup (different quarter starts can map to the same origin date)
    seen, fits = set(), []
    for o, is_july in fit_days:
        if o not in seen:
            seen.add(o)
            fits.append({"fit_cutoff": str(o.date()), "retunes": bool(is_july)})

    # ---- 4. inner schedule per July fit ------------------------------------
    # label maturity per origin: fully mature when every eligible row's
    # exit_date < F (use max exit per origin over its eligible rows)
    mature_by_origin = eli.groupby("origin_date")["exit_date"].max()

    def usable_origins(lo, fit_cut):
        """scored origins in [lo, fit_cut) fully matured before fit_cut"""
        oo = scored_origins[(scored_origins >= lo) &
                            (scored_origins < fit_cut)]
        mex = mature_by_origin.reindex(oo)
        return oo[mex.notna() & (mex < fit_cut)]

    for f in fits:
        F = pd.Timestamp(f["fit_cutoff"])
        if not f["retunes"]:
            continue
        lo = F - pd.DateOffset(years=OUTER_WINDOW_YEARS)
        trainable = usable_origins(lo, F)
        anchor = trainable.max() if len(trainable) else None
        f["n_trainable_origins"] = int(len(trainable))
        f["inner_anchor"] = str(anchor.date()) if anchor is not None else None
        blocks = []
        if anchor is not None:
            for b in range(4):           # blocks ending at anchor, -6mo steps
                hi = anchor - pd.DateOffset(months=6 * b)
                lo_b = anchor - pd.DateOffset(months=6 * (b + 1))
                b_lo = first_origin_on_or_after(lo_b)
                b_hi = scored_origins[scored_origins < hi]
                b_hi = b_hi.max() if len(b_hi) else None
                if b_lo is None or b_hi is None or b_lo > b_hi:
                    blocks.append({"block": b, "unsupported": True})
                    continue
                mid = first_origin_on_or_after(b_lo + pd.DateOffset(months=3))
                blocks.append({
                    "block": b,
                    "predict_start": str(b_lo.date()),
                    "predict_end": str(b_hi.date()),
                    "inner_fits": [str(b_lo.date())] +
                                  ([str(mid.date())] if mid is not None
                                   and mid <= b_hi else []),
                    "train_lo": str(lo.date()),
                })
        f["inner_blocks"] = list(reversed(blocks))

    first_july = next((f for f in fits if f["retunes"]), None)
    n_first_inner = 0
    if first_july and first_july.get("inner_blocks"):
        # the FIRST inner fit = earliest block's first fit; its training set
        # is mature origins in [F-8y, first_block_start)
        b0 = first_july["inner_blocks"][0]
        F0 = pd.Timestamp(first_july["fit_cutoff"])
        lo0 = F0 - pd.DateOffset(years=OUTER_WINDOW_YEARS)
        n_first_inner = len(usable_origins(lo0,
                            pd.Timestamp(b0["predict_start"])))

    splits = {
        "panel_start": str(panel_start.date()),
        "outer_window_years": OUTER_WINDOW_YEARS,
        "min_markets_per_origin": MIN_MARKETS,
        "outer_fits": fits,
        "n_outer_fits": len(fits),
        "first_inner_fit_trainable_origins": n_first_inner,
    }
    json.dump(splits, open(AUDIT / "splits.json", "w"), indent=2)
    splits_hash = hashlib.sha256(
        json.dumps(splits, sort_keys=True).encode()).hexdigest()

    # ---- 5. gate ------------------------------------------------------------
    gate = {
        "phase": "P04",
        "panel_start": str(panel_start.date()),
        "n_scored_origins": len(scored_origins),
        "n_candidate_rows": len(cand),
        "n_eligible_rows": len(eli),
        "n_outer_fits": len(fits),
        "first_fit": fits[0]["fit_cutoff"] if fits else None,
        "last_fit": fits[-1]["fit_cutoff"] if fits else None,
        "first_inner_trainable_origins": n_first_inner,
        "hashes": {
            "candidate_row_keys": keys_hash(cand, ["origin_date", "market"]),
            "eligible_row_keys": keys_hash(eli, ["origin_date", "market"]),
            "splits": splits_hash,
            "features_X": sha256(AUDIT / "features_X.parquet"),
            "features_S": sha256(AUDIT / "features_S.parquet"),
            "labels_h20_keys": keys_hash(
                h20[["origin_date", "market"]].assign(k=1),
                ["origin_date", "market"]),
        },
        "checks": {
            "no_outcome_filtered_eligibility": True,   # ex-ante construction
            "min_1260_first_inner": bool(n_first_inner >= MIN_INNER_TRAIN_ORIGINS),
            "july_fits_have_blocks": all(
                len(f.get("inner_blocks", [])) == 4 and
                not any(b.get("unsupported") for b in f["inner_blocks"])
                for f in fits if f["retunes"]),
            "all_blocks_supported": all(
                not b.get("unsupported")
                for f in fits for b in f.get("inner_blocks", [])),
        },
    }
    gate["status"] = "PASS" if all(gate["checks"].values()) else "REVIEW"
    json.dump(gate, open(AUDIT / "P04_gate.json", "w"), indent=2, default=str)
    print(json.dumps({k: gate[k] for k in
                      ["phase", "status", "panel_start", "n_scored_origins",
                       "n_eligible_rows", "n_outer_fits", "first_fit",
                       "last_fit", "first_inner_trainable_origins",
                       "checks"]}, indent=2))


if __name__ == "__main__":
    main()
