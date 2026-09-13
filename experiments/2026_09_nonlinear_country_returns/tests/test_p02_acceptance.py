# =============================================================================
# FILE: experiments/2026_09_nonlinear_country_returns/tests/test_p02_acceptance.py
#
# P02 synthetic acceptance tests — T08..T13 + T27 from the PRD test battery.
# Fixtures are hand-built padded grids mimicking T2's weekend/holiday carry.
# Every fixture carries a BASELINE mark before the measured window because the
# first observed grid row has no prior mark and is therefore never a session.
# Run:  cd <repo-root> && venv/bin/python -m pytest \
#       experiments/2026_09_nonlinear_country_returns/tests -q
# =============================================================================
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from calendars import build_session_calendar, candidate_origins  # noqa: E402
from labels import build_labels, mark_unresolved  # noqa: E402


def padded_tri(market: str, session_values: dict[str, float],
               start="2024-01-01", end="2024-03-31") -> pd.DataFrame:
    """Daily-grid TRI for one market: sessions hold given marks on given
    dates; every other calendar day carries the previous mark (T2 padding)."""
    dates = pd.date_range(start, end, freq="D")
    vals, last = [], None
    sv = {pd.Timestamp(k): v for k, v in session_values.items()}
    for d in dates:
        if d in sv:
            last = sv[d]
        vals.append(last)
    return pd.DataFrame({"date": dates, "country": market, "value": vals})


# ---- T08: weekend padding must not invent sessions --------------------------
def test_t08_weekend_padding_no_sessions():
    sess = {"2024-01-05": 99,   # baseline Fri
            "2024-01-08": 100, "2024-01-09": 101, "2024-01-10": 102,
            "2024-01-11": 103, "2024-01-12": 104}
    cal = build_session_calendar(padded_tri("X", sess))
    assert len(cal) == 5                       # Mon-Fri only; baseline excluded
    assert (cal["date"].dt.dayofweek < 5).all()
    assert cal["date"].min() == pd.Timestamp("2024-01-08")


# ---- T09: newest calendar date retained without a forward return ------------
def test_t09_newest_date_retained():
    sess = {"2024-03-22": 74,   # baseline Fri
            **{f"2024-03-{d:02d}": 100 + d for d in range(25, 30)}}
    tri = padded_tri("X", sess, end="2024-03-31")  # grid runs to Sunday
    cal = build_session_calendar(tri)
    assert cal["date"].max() == pd.Timestamp("2024-03-29")
    lab = build_labels(cal, pd.Series([pd.Timestamp("2024-03-28")]), horizon=20)
    row = lab.iloc[0]
    assert row["entry_date"] == pd.Timestamp("2024-03-29")   # kept, immature
    assert row["outcome_status"] == "CENSORED_TAIL"


# ---- T10: cross-market holiday moves entry and exit correctly ---------------
def test_t10_holiday_shifts_entry_exit():
    m1 = padded_tri("M1", {"2024-01-05": 99,
                           "2024-01-08": 100, "2024-01-09": 101,
                           "2024-01-10": 102, "2024-01-11": 103,
                           "2024-01-12": 104})
    m2 = padded_tri("M2", {"2024-01-05": 199,
                           "2024-01-08": 200, "2024-01-10": 202,  # Tue holiday
                           "2024-01-11": 203, "2024-01-12": 204})
    cal = build_session_calendar(pd.concat([m1, m2]))
    lab = build_labels(cal, pd.Series([pd.Timestamp("2024-01-08")]), horizon=2)
    e1 = lab[lab.market == "M1"].iloc[0]
    e2 = lab[lab.market == "M2"].iloc[0]
    assert e1["entry_date"] == pd.Timestamp("2024-01-09")   # next session
    assert e1["exit_date"] == pd.Timestamp("2024-01-11")    # +2 sessions
    assert e2["entry_date"] == pd.Timestamp("2024-01-10")   # Tue holiday -> Wed
    assert e2["exit_date"] == pd.Timestamp("2024-01-12")    # +2 sessions
    assert e1["label"] == pytest.approx(103 / 101 - 1)
    assert e2["label"] == pytest.approx(204 / 202 - 1)


# ---- T11: close/DST mapping — entry is always the next session date ---------
def test_t11_close_mapping_date_only():
    # The origin is 23:59 UTC on D; a session ON D already closed, so entry
    # is strictly after D even though the market traded on D itself.
    sess = {"2024-01-05": 99,
            "2024-01-08": 100, "2024-01-09": 101, "2024-01-10": 102}
    cal = build_session_calendar(padded_tri("US", sess))
    lab = build_labels(cal, pd.Series([pd.Timestamp("2024-01-08")]), horizon=1)
    row = lab.iloc[0]
    assert row["entry_date"] == pd.Timestamp("2024-01-09")  # not the D session
    assert row["exit_date"] == pd.Timestamp("2024-01-10")


# ---- T12: USD TRI used once — label is a pure ratio of USD marks ------------
def test_t12_single_usd_conversion():
    sess = {"2024-01-05": 90,
            "2024-01-08": 100, "2024-01-09": 110, "2024-01-10": 121}
    cal = build_session_calendar(padded_tri("BR", sess))
    lab = build_labels(cal, pd.Series([pd.Timestamp("2024-01-08")]), horizon=1)
    # Marks are USD TRI; a second FX conversion would corrupt the ratio.
    assert lab.iloc[0]["label"] == pytest.approx(121 / 110 - 1)


# ---- T13: unknown terminal mark -> censored, never deleted or zero-filled ---
def test_t13_unknown_terminal_preserved():
    sess = {"2024-03-22": 99,
            "2024-03-25": 100, "2024-03-26": 101, "2024-03-27": 102}
    cal = build_session_calendar(padded_tri("X", sess, end="2024-03-27"))
    lab = build_labels(cal, pd.Series([pd.Timestamp("2024-03-25")]), horizon=20)
    assert len(lab) == 1                      # row preserved
    assert lab.iloc[0]["outcome_status"] == "CENSORED_TAIL"
    assert pd.isna(lab.iloc[0]["label"])      # not zero-filled


# ---- T27: whole-origin maturity — missing due mark blocks the row -----------
def test_t27_unresolved_mature_blocks():
    sess = {"2024-01-05": 99,
            **{f"2024-01-{d:02d}": 100 + d for d in range(8, 15)}}
    cal = build_session_calendar(padded_tri("X", sess, end="2024-01-31"))
    lab = build_labels(cal, pd.Series([pd.Timestamp("2024-01-05")]), horizon=2)
    assert lab.iloc[0]["outcome_status"] == "MATURE"
    lab.loc[0, "tri_exit"] = pd.NA            # mark missing though exit is due
    lab.loc[0, "label"] = pd.NA
    tagged = mark_unresolved(lab, pd.Timestamp("2024-02-01"))
    assert tagged.iloc[0]["outcome_status"] == "UNRESOLVED_MATURE"


# ---- origin floor: >=20 sessions on the UTC date ----------------------------
def test_origin_floor_requires_20_markets():
    mkts = [f"M{i:02d}" for i in range(21)]
    frames = [padded_tri(m, {"2024-01-05": 99, "2024-01-08": 100})
              for m in mkts[:-1]]   # 20 markets trade Monday 01-08
    # M21 trades only Tuesday -> Mon has 20 sessions (candidate), Tue has 1.
    frames.append(padded_tri("M20", {"2024-01-05": 50, "2024-01-09": 51}))
    cal = build_session_calendar(pd.concat(frames))
    cand = candidate_origins(cal, mkts, min_markets=20)
    mon = cand[cand["date"] == pd.Timestamp("2024-01-08")].iloc[0]
    tue = cand[cand["date"] == pd.Timestamp("2024-01-09")].iloc[0]
    assert mon["n_sessions"] == 20 and mon["is_candidate_origin"]
    assert tue["n_sessions"] == 1 and not tue["is_candidate_origin"]
