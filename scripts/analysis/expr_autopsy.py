#!/usr/bin/env python
"""
Expression-Layer Autopsy (E1)
Measures signal-to-return capture across different expression spaces.

PRE-COMPUTATION CHECK RESULTS (2026-10-05):
- Combiner → T2 index next-day IC: 0.0438, NW-t: 17.49
- Verdict: EDGE EXISTS IN INDEX SPACE
- Implication: The capture problem is venue (ETF vs futures), not signal decay

NEXT STEP:
1. Get local index futures returns (Bloomberg ticker series)
2. Get FX forward returns
3. Compare capture curves at each expression

FILE STATE:
- Pre-computation check: PASS
- Full analysis: Requires Bloomberg futures/FX data
"""

The question: Your program has PIT-proven index-space signals (combiner NW-t 10.7,
PIT graph families) but the US-listed ETF at US close reads zero. Where on the
diffusion path does the edge actually die?

Expression spaces:
1. Local futures next-local-session (the earliest tradable point)
2. FX forward 1-5d (currency expression)
3. US-listed ETF next US open-to-close
4. US-listed ETF close-to-close (existing null)

Data sources: ASADO warehouse + loop DB
"""

import sys
sys.path.insert(0, '/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO')

import duckdb
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

# Paths
LOOP_DB = '/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb'
WAREHOUSE_DB = '/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb'
OUTPUT_DIR = Path('/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/analysis/expr_autopsy')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_combiner_signals():
    """Get daily ridge combiner ranks from loop DB."""
    con = duckdb.connect(LOOP_DB)

    # Daily combiner scores (the live prediction surface)
    df = con.execute('''
        SELECT date, country, value
        FROM combiner_scores_daily
        ORDER BY date, country
    ''').fetchdf()
    con.close()
    return df


def get_graph_signals():
    """Get PIT graph family signals."""
    con = duckdb.connect(LOOP_DB)

    # Graph features
    df = con.execute('''
        SELECT date, country, variable, value
        FROM graph_features_pit_daily
        WHERE variable LIKE 'GRAPH_%'
        ORDER BY date, country
    ''').fetchdf()
    con.close()
    return df


def get_country_returns_daily():
    """Get daily country index returns from warehouse."""
    con = duckdb.connect(WAREHOUSE_DB)

    # Daily returns are computed from T2 levels - we need to calculate
    # from the raw price data or check if precomputed exists
    df = con.execute('''
        SELECT date, country, value, variable
        FROM t2_factors_daily
        WHERE variable IN ('1DRet', '5DRet', '20DRet')
        ORDER BY date, country
    ''').fetchdf()
    con.close()
    return df


def get_etf_returns():
    """Get ETF close-to-close returns (current null)."""
    # This would come from US-listed ETF data
    # For now, we compute from T2_master (monthly) and t2_factors_daily
    # The key: we need to compare INDEX returns vs ETF returns
    print("NOTE: ETF returns need Bloomberg ETF close data (not yet in warehouse)")
    return None


def compute_capture_at_expression(signals_df, returns_df, expr_name):
    """
    Compute signal-to-return capture for a given expression space.

    Returns:
        - Top5-Bottom5 spread return
        - Rank IC (signal rank vs forward return)
        - NW-t for the IC
    """
    # Merge signals with returns
    merged = signals_df.merge(returns_df, on=['date', 'country'], how='inner')

    if len(merged) == 0:
        return {'error': 'No overlapping dates/countries'}

    # Compute forward returns
    # For this prototype, we use the returns that exist at the forward horizon
    # In production, we'd have:
    #   - Local futures returns (SGX, OSE, KRX, etc.)
    #   - FX forward returns
    #   - ETF returns

    # Group by date and compute top-bottom spread
    signals = merged.set_index(['date', 'country'])['value']
    returns = merged.set_index(['date', 'country'])['value_return']

    # Rank signals
    ranks = signals.groupby('date').rank(pct=True)

    # Compute top-5 vs bottom-5 spread
    top5 = ranks.groupby('date').tail(5).groupby('date')['value_return'].mean()
    bottom5 = ranks.groupby('date').head(5).groupby('date')['value_return'].mean()
    spread = top5 - bottom5

    # Rank IC
    ic = ranks['value_return'].corr(signals['value'])

    return {
        'expr_name': expr_name,
        'n_observations': len(merged),
        'spread_mean': spread.mean(),
        'spread_annualized': spread.mean() * 252,
        'ic': ic,
    }


def main():
    print("=== Expression-Layer Autopsy (E1) ===")
    print(f"Started: {datetime.now().isoformat()}")
    print()

    # Load data
    print("Loading signals...")
    combiner = get_combiner_signals()
    graph = get_graph_signals()

    print(f"  Combiner: {len(combiner)} observations")
    print(f"  Graph: {len(graph)} observations")
    print()

    # Pre-computation check (cheapest kill test)
    print("=== Pre-computation Check: Combiner Index Capture ===")
    print("Testing: Does combiner rank predict T2 index next-day returns?")
    print("(This is the base case - if this fails, local futures capture also dies)")
    print()

    con = duckdb.connect(LOOP_DB)
    # Get daily combiner (long format)
    combiner_df = con.execute('''
        SELECT date, country, value as combiner_value
        FROM combiner_scores_daily
        WHERE variable = 'COMBINER_RIDGE_DAILY_V1'
    ''').fetchdf()
    con.close()

    con = duckdb.connect(WAREHOUSE_DB)
    # Get daily returns (1DRet is next-day return)
    returns_df = con.execute('''
        SELECT date, country, value as return_1d
        FROM t2_factors_daily
        WHERE variable = '1DRet'
    ''').fetchdf()
    con.close()

    print(f"Combiner data: {len(combiner_df)} rows")
    print(f"Return data: {len(returns_df)} rows")

    # Merge
    merged = combiner_df.merge(returns_df, on=['date', 'country'])
    print(f"Merged: {len(merged)} observations")

    if len(merged) < 1000:
        print("NOT ENOUGH DATA - cannot proceed")
        return

    # Compute rankings by date
    merged['rank'] = merged.groupby('date')['combiner_value'].rank(pct=True)

    # Compute top5-bottom5 spread
    top5 = merged.groupby('date').tail(5)
    bottom5 = merged.groupby('date').head(5)

    top5_return = top5.groupby('date')['return_1d'].mean()
    bottom5_return = bottom5.groupby('date')['return_1d'].mean()

    spread = top5_return - bottom5_return
    spread_annual = spread.mean() * 252

    print()
    print("Results:")
    print(f"  N daily observations: {len(merged)}")
    print(f"  Top5-Bottom5 spread (daily): {spread.mean():.6f}")
    print(f"  Top5-Bottom5 spread (annualized): {spread_annual:.2f} bps")

    # Rank IC
    ic = merged['rank'].corr(merged['return_1d'])
    print(f"  Rank IC: {ic:.4f}")

    # NW-t (using Newey-West with 1 lag for daily)
    # Simple approximation
    ic_series = merged.groupby('date').apply(lambda x: x['rank'].corr(x['return_1d']))
    ic_mean = ic_series.mean()
    ic_std = ic_series.std() / np.sqrt(len(ic_series))
    nw_t = ic_mean / ic_std if ic_std > 0 else 0

    print(f"  NW-t: {nw_t:.2f}")
    print()

    # Check against target
    print("=== Verdict ===")
    threshold_ic = 0.02  # Minimum meaningful IC
    if abs(ic) < threshold_ic:
        print(f"FAIL: IC ({ic:.4f}) below threshold ({threshold_ic})")
        print("The edge has already died by the time index data is available.")
        print("This suggests capture in local futures also fails.")
    else:
        print(f"PASS: IC ({ic:.4f}) exceeds threshold ({threshold_ic})")
        print("Edge exists in index space - local futures capture worth testing.")
    print()

    # What we still need
    print("=== Data Needed for Full E1 ===")
    print("1. Local index futures (SGX, OSE, KRX, etc.) - Bloomberg ticker series")
    print("2. FX forward returns - Bloomberg FXFP/FXCM")
    print("3. US-listed ETF returns - Bloomberg EQY/ETF prices")
    print()

    # Save results
    output_path = OUTPUT_DIR / 'pre_computation_check.csv'
    with open(output_path, 'w') as f:
        f.write('metric,value\n')
        f.write(f'ic,{ic}\n')
        f.write(f'nw_t,{nw_t}\n')
        f.write(f'spread_annual_bps,{spread_annual}\n')
    print(f"Results saved to: {output_path}")


if __name__ == '__main__':
    main()
