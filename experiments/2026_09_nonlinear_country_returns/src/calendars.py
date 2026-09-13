# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/src/calendars.py
#
# P02 — independent per-market session calendars for the nonlinear study.
#
# Session definition (repo-audited convention, loopdb.daily_country_returns):
#   the T2 daily grid is a PADDED calendar-day grid — weekends and holidays
#   carry the previous TRI mark unchanged. A "session" is a date where the
#   TRI level CHANGED (value.diff() != 0). Consequence, shared with the repo
#   convention and documented: a genuinely flat session is indistinguishable
#   from padding and is dropped (0.4% of weekdays — shifts a session count,
#   not the marks).
#
# Independence: sessions are derived from OBSERVED MARKS (inputs knowable at
# the 23:59 UTC origin), never from forward returns or labels. asado's
# daily_calendar table is used only as a cross-check flag — it is a
# data-presence calendar that also marks weekend placeholder rows True and
# is therefore NOT a session authority.
#
# Origin/clock rule (from spec + verified against close times):
#   origin = 23:59:00 UTC on date D. Every covered exchange's local close
#   precedes 23:59 UTC (latest: Americas ~21:00 UTC), so on ANY origin date,
#   that day's session close is already observable, and the entry close is
#   always the market's FIRST SESSION STRICTLY AFTER D. This makes the
#   entry rule a pure date comparison — DST moves closes within a UTC day,
#   never across the origin boundary (see utc_close_hours table).
# =============================================================================
from __future__ import annotations

import pandas as pd

# Approximate local-close -> UTC hour ranges (standard / DST where applicable).
# Documentation for the T11 close-mapping audit. The study's clock only needs
# the invariant "close < 23:59 UTC on its date"; every market satisfies it.
UTC_CLOSE_HOURS = {
    "Australia": "05:00-06:00",   # ASX 16:00 AEST/AEDT
    "Brazil": "19:00-20:00",      # B3 ~17:00 BRT (no DST since 2019)
    "Canada": "20:00-21:00",      # TSX 16:00 ET
    "Chile": "20:00-21:00",       # SSE 16:00 CLT/CLST
    "ChinaA": "07:00",            # SSE 15:00 CST
    "ChinaH": "08:00",            # HKEX 16:00 HKT
    "Denmark": "15:30-16:30",     # Nasdaq CPH 16:55 CET/CEST (~)
    "France": "15:30-16:30",      # Euronext 17:30 CET/CEST
    "Germany": "15:30-16:30",
    "Hong Kong": "08:00",
    "India": "10:00",             # NSE 15:30 IST
    "Indonesia": "08:00-09:00",   # IDX ~15:50 WIB
    "Italy": "15:30-16:30",
    "Japan": "06:00",             # TSE 15:00 JST
    "Korea": "06:30",             # KRX 15:30 KST
    "Malaysia": "09:00",          # Bursa 17:00 MYT
    "Mexico": "20:00-21:00",      # BMV ~15:00 CT (post-2022 fixed)
    "NASDAQ": "20:00-21:00",
    "Netherlands": "15:30-16:30",
    "Philippines": "07:30",       # PSE 15:30 PHT
    "Poland": "15:50-16:50",      # GPW 16:50 CET/CEST
    "Saudi Arabia": "12:00",      # Tadawul 15:00 AST; Sun-Thu week
    "Singapore": "09:00",         # SGX 17:00 SGT
    "South Africa": "15:00",      # JSE 17:00 SAST
    "Spain": "15:30-16:30",
    "Sweden": "15:30-16:30",
    "Switzerland": "15:30-16:30",
    "Taiwan": "05:30",            # TWSE 13:30 TST
    "Thailand": "09:30",          # SET 16:30 ICT
    "Turkey": "15:10",            # BIST 18:10 TRT(+3, no DST since 2016)
    "U.K.": "15:30-16:30",        # LSE 16:30 London
    "U.S.": "20:00-21:00",
    "US SmallCap": "20:00-21:00",
    "Vietnam": "08:00",           # HOSE ~15:00 ICT
}


def build_session_calendar(tri: pd.DataFrame) -> pd.DataFrame:
    """(market, date, session_idx, tri_close) sessions = days the TRI moved.

    tri: long frame with columns [date, country, value] for variable
    'Tot Return Index'. The first row per market has no prior mark and is
    not a session (its return is unknowable).
    """
    frames = []
    for mkt, g in tri.groupby("country"):
        g = g.sort_values("date").copy()
        g["date"] = pd.to_datetime(g["date"])
        # Weekends are never sessions for the AM-1 universe (all Mon-Fri
        # markets; Saudi's Sun-Thu week is out of scope — revisit if the
        # universe changes). Weekend mark changes are late Bloomberg
        # revisions (they cluster in Mar-2020/Oct-2008 stress); dropping the
        # rows folds the revision into the next weekday's return, which is
        # where it becomes observable on the grid.
        g = g[g["date"].dt.dayofweek < 5]
        chg = g["value"].diff()
        sess = g[chg.ne(0) & chg.notna()][["country", "date", "value"]].copy()
        sess.columns = ["market", "date", "tri_close"]
        sess["session_idx"] = range(len(sess))
        frames.append(sess)
    cal = pd.concat(frames, ignore_index=True).sort_values(["market", "date"])
    cal["utc_close_window"] = cal["market"].map(UTC_CLOSE_HOURS)
    return cal.reset_index(drop=True)


def candidate_origins(cal: pd.DataFrame, mapped_markets: list[str],
                      min_markets: int = 20) -> pd.DataFrame:
    """UTC dates with >= min_markets mapped-market sessions that UTC date.

    A session's close precedes 23:59 UTC of its date (invariant above), so a
    market contributes to origin D iff it has a session on D.
    """
    d = cal[cal["market"].isin(mapped_markets)]
    n = d.groupby("date")["market"].nunique().rename("n_sessions")
    # Reindex over the full UTC date span so non-candidate dates are visible
    # (a date with 0 sessions must appear as 0, not silently vanish).
    full = pd.date_range(n.index.min(), n.index.max(), freq="D")
    n = n.reindex(full, fill_value=0).rename_axis("date").reset_index()
    n["is_candidate_origin"] = n["n_sessions"] >= min_markets
    return n
