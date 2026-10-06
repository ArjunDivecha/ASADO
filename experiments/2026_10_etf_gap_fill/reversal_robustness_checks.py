#!/usr/bin/env python
"""
==============================================================================
SCRIPT NAME: reversal_robustness_checks.py
VERSION:     1.0  (2026-10-05)
==============================================================================

DESCRIPTION
-----------
Persists two robustness checks of the one-day country-ETF reversal that were
first run ad hoc in the 2026-10-05 session and quoted in the README, so they
are reproducible (GPT-5.6 review flagged them as untested because they lived
only in the session):

  A. REGIONAL SPLIT OF THE OVERNIGHT LEG.  Long losers / short winners quintile
     (signal = close-to-close return on day T), contribution of each region's
     ETFs to the overnight return close T -> open T+1 and to the next-day
     intraday return open T+1 -> close T+1.  Full sample and since 2021.
  B. LEAVE-ONE-ETF-OUT for the close-entry (E1) long-short book, last 5 years,
     and for the next-open (E3) book, so both numbers sit side by side.

Universe eligibility uses only information known at T (no future-
availability filter).  Gross returns.

INPUT FILES
-----------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_ohlcv_34.parquet

OUTPUT FILES
------------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/runs/robustness_<timestamp>/
      robustness_results.xlsx, log.txt

DEPENDENCIES
------------
  pandas, numpy, openpyxl (project venv)

USAGE
-----
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
  venv/bin/python experiments/2026_10_etf_gap_fill/reversal_robustness_checks.py
==============================================================================
"""
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import etf_reversal_1d as m  # noqa: E402


def weights(sig, q=0.2, min_n=10):
    n = sig.notna().sum(axis=1)
    r = sig.rank(axis=1, pct=True)
    lo = (r > 1 - q).astype(float)
    sh = (r <= q).astype(float)
    ok = n >= min_n
    lo = lo.div(lo.sum(axis=1).replace(0, np.nan), axis=0).where(ok, 0).fillna(0)
    sh = sh.div(sh.sum(axis=1).replace(0, np.nan), axis=0).where(ok, 0).fillna(0)
    return lo - sh, ok


def sharpe(x):
    x = x.dropna()
    return x.mean() / x.std() * np.sqrt(252)


def main():
    run = m.EXP / 'runs' / ('robustness_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    run.mkdir(parents=True)
    sys.stdout = m.Tee(run / 'log.txt')
    print(f"Run dir: {run}")
    px = m.load_ohlcv(False)
    U = m.UNIVERSE
    O, C, V = px['Open'][U], px['Close'][U], px['Volume'][U]
    good = (V > 0) & C.notna() & (O > 0)
    Cg, Og = C.where(good), O.where(good)
    rc = Cg / Cg.shift(1) - 1
    sig = -rc
    w, ok = weights(sig)
    ON = (Og.shift(-1) / Cg - 1)
    DAY = (Cg.shift(-1) / Og.shift(-1) - 1)
    R1 = rc.shift(-1)
    R3 = Og.shift(-2) / Og.shift(-1) - 1
    regions = {'Asia-Pacific': sorted(m.ASIA), 'Americas': sorted(m.AMER),
               'Europe/Africa/ME': [t for t in U if t not in m.ASIA | m.AMER]}
    rows = []
    for leg, R in [('overnight close T -> open T+1', ON), ('intraday open T+1 -> close T+1', DAY)]:
        contrib = w * R.where(R.abs() < 0.4).fillna(0)
        for reg, tk in regions.items():
            c = contrib[tk].sum(axis=1)[ok.cummax()]
            rows.append({'leg': leg, 'region': reg, 'ann_contrib_full': c.mean() * 252,
                         'ann_contrib_since_2021': c['2021':].mean() * 252})
    reg = pd.DataFrame(rows)
    pd.set_option('display.width', 200)
    print("\n=== A. Long-short contribution by region and leg (annualised, gross) ===")
    print(reg.round(3).to_string(index=False))

    jk = []
    for t in U:
        tk = [u for u in U if u != t]
        ww, okk = weights(sig[tk])
        row = {'dropped': t}
        for lab, R in [('E1_close_close', R1), ('E3_open_open', R3)]:
            x = (ww * R[tk].where(R[tk].abs() < 0.4).fillna(0)).sum(axis=1)[okk.cummax()]
            x5 = x[x.index > x.index.max() - pd.DateOffset(years=5)]
            row[f'{lab}_sharpe_5y'] = sharpe(x5)
        jk.append(row)
    jk = pd.DataFrame(jk)
    print("\n=== B. Leave-one-ETF-out, long-short Sharpe over the last 5 years ===")
    for c in ['E1_close_close_sharpe_5y', 'E3_open_open_sharpe_5y']:
        print(f"{c}: min {jk[c].min():.2f} ({jk.loc[jk[c].idxmin(), 'dropped']}), max {jk[c].max():.2f}")
    with pd.ExcelWriter(run / 'robustness_results.xlsx') as xw:
        reg.to_excel(xw, sheet_name='regional_legs', index=False)
        jk.to_excel(xw, sheet_name='leave_one_out', index=False)
    print(f"\nDone. {run}")


if __name__ == '__main__':
    main()
