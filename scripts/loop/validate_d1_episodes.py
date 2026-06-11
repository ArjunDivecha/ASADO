#!/usr/bin/env python3
"""
=============================================================================
SCRIPT NAME: scripts/loop/validate_d1_episodes.py
=============================================================================

INPUT FILES:
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
    Table `tot_trade_shares` — WDI/WITS commodity trade-composition shares.
- /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
    Table `commodity_panel` (attached read-only as `asado`) — Pink Sheet
    aggregate 3-month index returns used by the D1 basket.

OUTPUT FILES:
- (none on disk) Prints a PASS/FAIL table to stdout. This is the Phase 3
  acceptance test from PRD_Alpha_Hunting_Loop.md §11: "D1 v1 basket
  validated against 3 known episodes".

VERSION: 1.0
LAST UPDATED: 2026-06-11
AUTHOR: Arjun Divecha (built by agent session, Alpha-Hunting Loop Phase 3)

DESCRIPTION:
Rebuilds the exact D1 terms-of-trade impulse series (same shares, same
Pink Sheet aggregates, same 36m rolling z as build_dislocations.d1_tot_impulse)
for the FULL history, then checks it tells the right story in three episodes
where the ground truth is known:

  1. Saudi Arabia, Apr 2020 — oil collapsed (COVID + OPEC price war).
     A net fuel exporter's ToT impulse must be deeply NEGATIVE.
  2. Chile, Apr 2021 — copper ripped to all-time highs in the reflation
     trade. A net metals exporter's ToT impulse must be strongly POSITIVE.
  3. Chile, May 2024 — copper squeezed to a record ~$11k/t.
     ToT impulse must again be POSITIVE.

Each episode passes when (a) the impulse SIGN is right in the episode month
and (b) the rolling 36m z reaches |z| >= 1 somewhere inside the episode
window (the repricing-gate part of D1 is run-date-only and not re-tested
here — this validates the BASKET, which is what the acceptance criterion
names). A 10th grader's version: we know oil crashed in 2020 and copper
boomed in 2021/2024 — does our formula actually scream in those months?

DEPENDENCIES:
- duckdb, pandas, numpy (project venv)

USAGE:
  python scripts/loop/validate_d1_episodes.py

NOTES:
- Imports D1_INDEX_MAP from build_dislocations so the test can never drift
  from the production basket definition.
- Trade shares are the LATEST WDI/WITS year applied statically across
  history (exactly what production D1 does, v0.9 behavior) — so this also
  validates that the static-share approximation is good enough in the
  episodes that matter.
=============================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from scripts.loop.build_dislocations import D1_INDEX_MAP  # noqa: E402
from scripts.loop.loopdb import loop_connection  # noqa: E402

ZWIN, ZMIN_OBS = 36, 24

# (label, country, episode window, expected sign, narrative ground truth)
EPISODES = [
    ("Saudi/oil 2020", "Saudi Arabia", "2020-02-01", "2020-06-30", -1,
     "COVID + OPEC price war: Brent -65% in 3m"),
    ("Chile/copper 2021", "Chile", "2021-02-01", "2021-06-30", +1,
     "reflation trade: copper to then-record ~$10.7k/t"),
    ("Chile/copper 2024", "Chile", "2024-03-01", "2024-06-30", +1,
     "squeeze to record ~$11k/t in May 2024"),
]


def basket_series(con, country: str) -> pd.Series:
    """The production D1 basket: static net shares x Pink Sheet 3m returns."""
    shares = con.execute(
        "SELECT category, net_share FROM tot_trade_shares WHERE country = ?", [country]
    ).fetchdf().set_index("category")["net_share"]
    if shares.empty:
        raise RuntimeError(f"no trade shares for {country} — run build_tot_shares.py")
    cm = con.execute(
        f"""SELECT date, variable, value FROM asado.commodity_panel
            WHERE variable IN ({','.join('?' for _ in D1_INDEX_MAP)}) AND value IS NOT NULL""",
        list(D1_INDEX_MAP.values()),
    ).fetchdf()
    cm["date"] = pd.to_datetime(cm["date"])
    piv = cm.pivot_table(index="date", columns="variable", values="value").sort_index() / 100.0
    basket = pd.Series(0.0, index=piv.index)
    for cat, var in D1_INDEX_MAP.items():
        w = shares.get(cat)
        if w is None or pd.isna(w):
            continue
        basket = basket + float(w) * piv[var].fillna(0.0)
    return basket


def rolling_z(s: pd.Series) -> pd.Series:
    mu = s.rolling(ZWIN, min_periods=ZMIN_OBS).mean()
    sd = s.rolling(ZWIN, min_periods=ZMIN_OBS).std()
    return (s - mu) / sd.replace(0.0, np.nan)


def main() -> int:
    con = loop_connection(read_only=True)
    failures = 0
    try:
        print("D1 basket validation — PRD Phase 3 acceptance (3 known episodes)")
        print("=" * 78)
        for label, country, lo, hi, want_sign, truth in EPISODES:
            basket = basket_series(con, country)
            z = rolling_z(basket)
            win_b = basket.loc[lo:hi]
            win_z = z.loc[lo:hi]
            if win_b.empty:
                print(f"FAIL  {label}: no basket data in window {lo}..{hi}")
                failures += 1
                continue
            # peak month in the expected direction
            peak_idx = win_b.idxmax() if want_sign > 0 else win_b.idxmin()
            peak_b, peak_z = win_b.loc[peak_idx], win_z.loc[peak_idx]
            sign_ok = np.sign(peak_b) == want_sign
            z_ok = (not np.isnan(peak_z)) and abs(peak_z) >= 1.0 and np.sign(peak_z) == want_sign
            status = "PASS" if (sign_ok and z_ok) else "FAIL"
            if status == "FAIL":
                failures += 1
            print(f"{status}  {label:<20} {country:<13} peak {peak_idx.date()}: "
                  f"impulse {peak_b:+.4f}, z {peak_z:+.2f} (want sign {'+' if want_sign > 0 else '-'})")
            print(f"      ground truth: {truth}")
    finally:
        con.close()
    print("=" * 78)
    print("OVERALL:", "PASS — D1 basket reproduces all 3 episodes" if failures == 0
          else f"FAIL — {failures} episode(s) not reproduced")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
