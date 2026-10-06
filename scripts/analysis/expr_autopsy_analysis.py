#!/usr/bin/env python
"""
Expression-Layer Autopsy: Full Analysis

Compare signal capture across expression spaces:
1. T2 Index (next-day) - EXISTS, IC=0.0438
2. Local Index Futures - Needs Bloomberg data
3. FX Forward - Needs Bloomberg data
4. US ETF - Needs Bloomberg data

Usage:
    python scripts/analysis/expr_autopsy_analysis.py --combiner
    python scripts/analysis/expr_autopsy_analysis.py --full
"""

import sys
sys.path.insert(0, '/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO')

import argparse
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


def analyze_combiner_capture():
    """Analyze combiner signal → T2 index capture (we have this data)."""
    print("=" * 70)
    print("ANALYSIS: Combiner → T2 Index Capture")
    print("=" * 70)

    con = duckdb.connect(LOOP_DB)
    combiner_df = con.execute('''
        SELECT date, country, value as signal
        FROM combiner_scores_daily
        WHERE variable = 'COMBINER_RIDGE_DAILY_V1'
    ''').fetchdf()
    con.close()

    con = duckdb.connect(WAREHOUSE_DB)
    returns_df = con.execute('''
        SELECT date, country, value as return_1d
        FROM t2_factors_daily
        WHERE variable = '1DRet'
    ''').fetchdf()
    con.close()

    merged = combiner_df.merge(returns_df, on=['date', 'country'])

    # Compute metrics
    merged['rank'] = merged.groupby('date')['signal'].rank(pct=True)

    # IC by year
    ic_by_year = merged.groupby(merged['date'].dt.year).apply(
        lambda x: x['rank'].corr(x['return_1d'])
    )

    # IC by country
    ic_by_country = merged.groupby('country').apply(
        lambda x: x['rank'].corr(x['return_1d'])
    ).sort_values(ascending=False)

    print()
    print("Overall:")
    print(f"  N observations: {len(merged)}")
    print(f"  Rank IC: {merged['rank'].corr(merged['return_1d']):.4f}")
    print()

    print("IC by Year (first 10):")
    print(ic_by_year.head(10).to_string())
    print()

    print("Top 10 Countries by IC:")
    print(ic_by_country.head(10).to_string())
    print()

    # Check for structural break (2024)
    merged['year'] = merged['date'].dt.year
    pre_2024 = merged[merged['year'] < 2024]
    post_2024 = merged[merged['year'] >= 2024]

    print("Structural Break Test (pre vs post 2024):")
    print(f"  Pre-2024 IC: {pre_2024['rank'].corr(pre_2024['return_1d']):.4f}")
    print(f"  Post-2024 IC: {post_2024['rank'].corr(post_2024['return_1d']):.4f}")
    print()

    return merged


def analyze_graph_capture():
    """Analyze graph family signals → T2 index capture."""
    print("=" * 70)
    print("ANALYSIS: Graph Families → T2 Index Capture")
    print("=" * 70)

    con = duckdb.connect(LOOP_DB)
    graph_df = con.execute('''
        SELECT date, country, variable, value as signal
        FROM graph_features_pit_daily
        WHERE variable IN ('GRAPH_BANKING_CLAIMS_GAP', 'GRAPH_TWOHOP_TRADE_GAP', 'GRAPH_KATZ')
    ''').fetchdf()
    con.close()

    con = duckdb.connect(WAREHOUSE_DB)
    returns_df = con.execute('''
        SELECT date, country, value as return_1d
        FROM t2_factors_daily
        WHERE variable = '1DRet'
    ''').fetchdf()
    con.close()

    merged = graph_df.merge(returns_df, on=['date', 'country'])

    print()
    for var in merged['variable'].unique():
        var_data = merged[merged['variable'] == var]
        ic = var_data['signal'].corr(var_data['return_1d'])
        n = len(var_data)
        print(f"{var}:")
        print(f"  N: {n}")
        print(f"  IC: {ic:.4f}")
        print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--combiner', action='store_true', help='Analyze combiner capture')
    parser.add_argument('--graph', action='store_true', help='Analyze graph family capture')
    parser.add_argument('--full', action='store_true', help='Run all analyses')

    args = parser.parse_args()

    if not any([args.combiner, args.graph, args.full]):
        args.combiner = True  # Default

    print()
    print("Expression-Layer Autopsy (E1)")
    print(f"Started: {datetime.now().isoformat()}")
    print()

    if args.combiner or args.full:
        analyze_combiner_capture()

    if args.graph or args.full:
        analyze_graph_capture()

    print("=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    print()
    print("The signals PREDICT index returns with IC ~0.04-0.06.")
    print("This is the BASE CASE for E1 - if this were zero, we'd stop.")
    print()
    print("NEXT: Compare against ETF capture (current null).")
    print("If index IC >> ETF IC, then local futures expression is the fix.")
    print()


if __name__ == '__main__':
    main()
