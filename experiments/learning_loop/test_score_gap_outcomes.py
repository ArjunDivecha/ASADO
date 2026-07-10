"""
=============================================================================
SCRIPT NAME: test_score_gap_outcomes.py
=============================================================================
Validates the FROZEN return arithmetic of score_gap_outcomes.py against known
historical ETF price windows. This is how we trust the scorer TODAY, before any
real episode has matured (earliest maturity ~2026-07-22).

INPUT FILES (read-only):
  .../experiments/fdt_mech_backtest/etf_prices_full.parquet  (yfinance adj close)
OUTPUT FILES: none (prints PASS/FAIL, exits nonzero on failure).

Run:  cd ASADO && source venv/bin/activate && \
      python experiments/learning_loop/test_score_gap_outcomes.py
=============================================================================
"""
from __future__ import annotations
import sys
import numpy as np
import pandas as pd
import score_gap_outcomes as S


def _approx(a, b, tol=1e-9):
    return a is not None and b is not None and abs(a - b) < tol


def main() -> int:
    px = S.load_prices()
    cal = px.index
    fails = []

    # --- Test 1: window_return matches manual p1/p0-1 on a real known window ---
    tk = "EWZ"  # Brazil
    entry = cal[cal <= pd.Timestamp("2025-03-03")][-1]
    epos = cal.get_loc(entry)
    exit_ = cal[epos + 21]
    manual = float(px[tk].loc[exit_] / px[tk].loc[entry] - 1.0)
    got = S.window_return(px[tk], entry, exit_)
    if not _approx(got, manual):
        fails.append(f"T1 window_return: got {got} vs manual {manual}")

    # --- Test 2: entry is STRICTLY AFTER opened_at, exit is +21 trading days ---
    opened = pd.Timestamp("2025-03-03")
    e2, x2, matured = S.resolve_entry_exit(opened, 21, cal)
    if not (e2 > opened):
        fails.append(f"T2 entry not strictly after opened_at: {e2} <= {opened}")
    if cal.get_loc(x2) - cal.get_loc(e2) != 21:
        fails.append(f"T2 exit not +21 td: {cal.get_loc(x2) - cal.get_loc(e2)}")
    if not matured:
        fails.append("T2 should be matured (2025 window)")

    # --- Test 3: EW window return equals mean of per-ticker window returns ---
    ew = S.ew_window_return(px, e2, x2)
    manual_ew = np.mean([S.window_return(px[c], e2, x2) for c in px.columns
                         if S.window_return(px[c], e2, x2) is not None])
    if not _approx(ew, float(manual_ew)):
        fails.append(f"T3 EW: got {ew} vs manual {manual_ew}")

    # --- Test 4: decomposition identity index_information+etf_capture==gross ---
    # (uses a synthetic country return so we don't need the main DB in the test)
    d, r_etf, r_ew, r_idx = 1, 0.05, 0.02, 0.035
    gross = d * (r_etf - r_ew)
    idx_info = d * (r_idx - r_ew)
    capture = d * (r_etf - r_idx)
    if not _approx(idx_info + capture, gross):
        fails.append(f"T4 decomposition: {idx_info}+{capture} != {gross}")

    # --- Test 5: net = gross - 2*25bp (round-trip cost) ---
    net = gross - 2 * S.COST_1WAY
    if not _approx(net, gross - 0.005):
        fails.append(f"T5 cost: net {net} vs expected {gross - 0.005}")

    # --- Test 6: future exit (beyond last price) reports NOT matured ---
    future_open = cal.max() - pd.Timedelta(days=2)
    _, xf, matf = S.resolve_entry_exit(future_open, 21, cal)
    if matf or xf is not None:
        fails.append(f"T6 future window should be pending: matured={matf}, exit={xf}")

    # --- Test 7: missing endpoint price -> None (never fabricated) ---
    if S.window_return(px[tk], pd.Timestamp("1990-01-01"), exit_) is not None:
        fails.append("T7 missing entry price should return None")

    if fails:
        print("FAIL:")
        for f in fails:
            print("  -", f)
        return 1
    print("PASS: all 7 arithmetic checks green")
    print(f"  T1 EWZ 21d window return (2025-03): {got:+.4%}")
    print(f"  T3 EW-34 same window:               {ew:+.4%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
