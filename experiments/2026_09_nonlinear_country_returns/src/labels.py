# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/src/labels.py
#
# P02 — entry/exit and USD total-return labels, independent of the harness's
# forward-return fields. Labels are built ONLY from 'Tot Return Index' marks
# (already USD-denominated — verified 2026-09-13: Turkey TRI grew 1.7x while
# TRY/USD moved 0.54 -> 48.6; never multiply by 'Currency' again — T12).
#
# Contract (spec):
#   origin    = 23:59:00 UTC on UTC date D
#   entry     = first local session strictly after D   (entry is session zero)
#   exit      = the H-th session after entry           (H in {5, 20, 63})
#   label     = TRI_USD(exit) / TRI_USD(entry) - 1
#   maturity  = label available once the exit session's close has occurred;
#               conservative proxy label_available_date = exit date
#
# Censoring (spec P02-03): rows whose exit lies beyond the observed session
# history keep outcome_status='CENSORED_TAIL'; they are never dropped, and a
# missing-but-due outcome is 'UNRESOLVED_MATURE' which blocks primary
# inference rather than silently deleting the row.
# =============================================================================
from __future__ import annotations

import pandas as pd

HORIZONS = {"h5": 5, "h20": 20, "h63": 63}


def build_labels(cal: pd.DataFrame, origins: pd.Series,
                 horizon: int = 20) -> pd.DataFrame:
    """For every (origin_date, market): entry/exit session dates + label.

    cal: session calendar from calendars.build_session_calendar
    origins: UTC dates (Timestamps or date-like) — candidate origin dates.
    Returns long frame:
      origin_date, market, entry_date, exit_date, tri_entry, tri_exit,
      label, outcome_status
    """
    origins = pd.to_datetime(pd.Series(origins)).sort_values().unique()
    out = []
    for mkt, g in cal.groupby("market"):
        g = g.sort_values("session_idx").reset_index(drop=True)
        dates = g["date"].values          # datetime64 array, sorted
        vals = g["tri_close"].values
        n = len(g)
        for od in origins:
            # entry = first session strictly after the origin UTC date
            i = dates.searchsorted(od + pd.Timedelta(days=1))
            if i >= n:
                rec = {"origin_date": od, "market": mkt,
                       "entry_date": pd.NaT, "exit_date": pd.NaT,
                       "tri_entry": pd.NA, "tri_exit": pd.NA,
                       "label": pd.NA, "outcome_status": "NO_FUTURE_SESSION"}
                out.append(rec)
                continue
            j = i + horizon
            if j < n:
                status = "MATURE"
            else:
                status = "CENSORED_TAIL"
            out.append({
                "origin_date": od, "market": mkt,
                "entry_date": g["date"].iloc[i],
                "exit_date": g["date"].iloc[j] if j < n else pd.NaT,
                "tri_entry": vals[i],
                "tri_exit": vals[j] if j < n else pd.NA,
                "label": (vals[j] / vals[i] - 1.0) if j < n else pd.NA,
                "outcome_status": status,
            })
    df = pd.DataFrame(out)
    return df.sort_values(["origin_date", "market"]).reset_index(drop=True)


def mark_unresolved(labels: pd.DataFrame, asof: pd.Timestamp) -> pd.DataFrame:
    """Re-tag: a MATURE row whose mark is later found missing becomes
    UNRESOLVED_MATURE (blocks primary inference; never deleted). Censored
    rows whose exit is still in the future relative to `asof` stay
    CENSORED_TAIL. `asof` = data watermark (last observed session date).
    """
    df = labels.copy()
    due = df["exit_date"].notna() & (df["exit_date"] <= asof)
    missing_mark = df["tri_exit"].isna() | df["tri_entry"].isna()
    df.loc[due & missing_mark, "outcome_status"] = "UNRESOLVED_MATURE"
    return df
