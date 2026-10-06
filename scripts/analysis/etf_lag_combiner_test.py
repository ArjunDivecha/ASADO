#!/usr/bin/env python
"""
ETF LAG TEST: Does the Combiner Predict Which Gaps Close?

The question: Not all ETF gaps close. Does the combiner signal help us
identify which gaps are safe to take?

Test:
1. Identify big local moves with gaps
2. Check combiner signal on those days
3. See if high combiner predicts gap closing
"""

import sys
sys.path.insert(0, '/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO')

import duckdb
import pandas as pd
import numpy as np
import yfinance as yf
from pathlib import Path
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')

WAREHOUSE_DB = '/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb'
LOOP_DB = '/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb'
OUTPUT_DIR = Path('/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/analysis/etf_lag_combiner')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ETF_TICKERS = {
    'Japan': 'EWJ', 'Taiwan': 'EWT', 'Korea': 'EWY', 'India': 'INDA',
    'ChinaA': 'FXI', 'Hong Kong': 'EWH', 'Australia': 'EWA', 'Brazil': 'EWZ',
    'Germany': 'EWG', 'UK': 'EWU', 'France': 'EWQ', 'Italy': 'EWI',
    'Spain': 'EPP', 'Switzerland': 'EWL', 'Sweden': 'EWD',
}


def get_etf_returns(tickers, start='2015-01-01'):
    end = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')
    all_data = {}

    for country, ticker in tickers.items():
        try:
            df = yf.download(ticker, start=start, end=end, progress=False)
            if 'Close' in df.columns and len(df) > 0:
                df = df[['Close']].copy()
                df.index = pd.to_datetime(df.index).date
                df = df.reset_index()
                df.columns = ['date', 'etf_close']
                df['country'] = country
                df['etf_return'] = df['etf_close'].pct_change()
                all_data[country] = df[['date', 'country', 'etf_return']]
        except Exception as e:
            pass

    return pd.concat(list(all_data.values()), ignore_index=True) if all_data else None


def main():
    print("=" * 70)
    print("ETF LAG TEST: Does Combiner Predict Gap Closing?")
    print("=" * 70)

    # Get local data
    print("\nLoading data...")
    con = duckdb.connect(WAREHOUSE_DB)
    local_df = con.execute('''
        SELECT date, country, value as local_return
        FROM t2_factors_daily
        WHERE variable = '1DRet'
    ''').fetchdf()
    con.close()
    local_df['date'] = pd.to_datetime(local_df['date']).dt.date

    # Get combiner
    con = duckdb.connect(LOOP_DB)
    combiner_df = con.execute('''
        SELECT date, country, value as signal
        FROM combiner_scores_daily
        WHERE variable = 'COMBINER_RIDGE_DAILY_V1'
    ''').fetchdf()
    con.close()
    combiner_df['date'] = pd.to_datetime(combiner_df['date']).dt.date

    print(f"Local data: {len(local_df)}")
    print(f"Combiner data: {len(combiner_df)}")

    # Get ETF
    etf_df = get_etf_returns(ETF_TICKERS)
    if etf_df is None:
        print("FAILED to get ETF data")
        return

    print(f"ETF data: {len(etf_df)}")

    # Merge
    print("\nMerging...")
    merged = local_df.merge(combiner_df, on=['date', 'country'], how='inner')
    merged = merged.merge(etf_df, on=['date', 'country'], how='inner')
    print(f"Merged: {len(merged)}")

    # Compute forward returns
    merged = merged.sort_values(['country', 'date']).reset_index(drop=True)

    for country in merged['country'].unique():
        mask = merged['country'] == country
        idx = merged[mask].index
        etf_rets = merged.loc[idx, 'etf_return'].values

        # T+5 forward return
        t5 = np.zeros(len(etf_rets))
        for i in range(len(etf_rets) - 5):
            t5[i] = etf_rets[i:i+5].sum()
        merged.loc[idx[:-5], 'etf_return_5d'] = t5[:-5]
        merged.loc[idx[-5:], 'etf_return_5d'] = 0

    # Identify big moves with gaps
    print("\nIdentifying big moves with gaps...")
    merged['abs_local'] = merged['local_return'].abs()
    big_moves = merged[merged['abs_local'] > 0.02].copy()

    # Gap = local - ETF (positive = ETF under-reacted)
    big_moves['gap'] = big_moves['local_return'] - big_moves['etf_return']
    big_moves['gap_closed'] = (big_moves['etf_return_5d'].abs() > big_moves['gap'].abs() * 0.5).astype(int)

    print(f"Big moves with gaps: {len(big_moves)}")

    # Key analysis
    print("\n" + "=" * 70)
    print("ANALYSIS: Does Combiner Predict Gap Closing?")
    print("=" * 70)

    # IC of combiner predicting gap closure
    print("\n1. Combiner predicting gap CLOSURE (binary):")
    closure_ic = big_moves['signal'].corr(big_moves['gap_closed'])
    print(f"   IC: {closure_ic:.4f}")

    # IC of combiner predicting gap magnitude
    print("\n2. Combiner predicting gap SIZE:")
    gap_ic = big_moves['signal'].corr(big_moves['gap'])
    print(f"   IC: {gap_ic:.4f}")

    # IC of combiner predicting ETF T+5 return
    print("\n3. Combiner predicting ETF return in 5 days:")
    etf5_ic = big_moves['signal'].corr(big_moves['etf_return_5d'])
    print(f"   IC: {etf5_ic:.4f}")

    # Compare to local return IC (the baseline)
    print("\n4. Combiner predicting LOCAL return (baseline):")
    local_ic = big_moves['signal'].corr(big_moves['local_return'])
    print(f"   IC: {local_ic:.4f}")

    # Sort by combiner decile (global, not by date)
    print("\n5. Gap closure rate by combiner decile:")
    big_moves['decile'] = pd.qcut(big_moves['signal'].rank(method='first'), 10, labels=False)

    decile_stats = big_moves.groupby('decile').agg({
        'gap_closed': 'mean',
        'gap': 'mean',
    }).rename(columns={'gap_closed': 'closure_rate', 'gap': 'avg_gap'})

    for decile in sorted(decile_stats.index):
        row = decile_stats.loc[decile]
        print(f"   Decile {decile:.0f}: closure={row['closure_rate']*100:.1f}%, gap={row['avg_gap']*100:.2f}%")

    # Save
    output_path = OUTPUT_DIR / 'combiner_test_results.csv'
    big_moves.to_csv(output_path, index=False)
    print(f"\n\nResults saved to: {output_path}")


if __name__ == '__main__':
    main()
