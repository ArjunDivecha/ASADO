#!/usr/bin/env python
"""
ETF LAG FULL TEST

When local markets have big moves, does the ETF eventually catch up?
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
OUTPUT_DIR = Path('/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/analysis/etf_lag_full')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

ETF_TICKERS = {
    'Japan': 'EWJ', 'Taiwan': 'EWT', 'Korea': 'EWY', 'India': 'INDA',
    'ChinaA': 'FXI', 'Hong Kong': 'EWH', 'Australia': 'EWA', 'Brazil': 'EWZ',
    'Germany': 'EWG', 'UK': 'EWU', 'France': 'EWQ', 'Italy': 'EWI',
    'Spain': 'EPP', 'Switzerland': 'EWL', 'Sweden': 'EWD',
}


def get_etf_returns(tickers, start='2015-01-01'):
    """Get daily ETF returns."""
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
                print(f"  {country}: {ticker} OK ({len(df)} days)")
        except Exception as e:
            print(f"  {country}: {ticker} ERROR")

    return pd.concat(list(all_data.values()), ignore_index=True) if all_data else None


def main():
    print("=" * 70)
    print("ETF LAG FULL TEST: Does ETF Catch Up?")
    print("=" * 70)

    # Get local data
    print("\nLoading local data...")
    con = duckdb.connect(WAREHOUSE_DB)
    local_df = con.execute('''
        SELECT date, country, value as local_return
        FROM t2_factors_daily
        WHERE variable = '1DRet'
    ''').fetchdf()
    con.close()
    local_df['date'] = pd.to_datetime(local_df['date']).dt.date
    print(f"Local data: {len(local_df)} observations")

    # Get ETF data
    print("\nFetching ETF data from yfinance...")
    etf_df = get_etf_returns(ETF_TICKERS)

    if etf_df is None:
        print("FAILED to get ETF data")
        return

    print(f"ETF data: {len(etf_df)} observations")

    # Merge
    print("\nMerging...")
    merged = local_df.merge(etf_df, on=['date', 'country'], how='inner')
    print(f"Merged: {len(merged)} observations")

    # Identify big local moves
    print("\nIdentifying big local moves (|return| > 2%)...")
    merged['abs_local'] = merged['local_return'].abs()
    big_moves = merged[merged['abs_local'] > 0.02].copy()
    print(f"Big moves: {len(big_moves)} observations")

    if len(big_moves) < 100:
        print("Not enough big moves")
        return

    # Sort by country and date
    big_moves = big_moves.sort_values(['country', 'date']).reset_index(drop=True)

    # Compute forward ETF returns
    print("\nComputing forward ETF returns...")

    for country in big_moves['country'].unique():
        mask = big_moves['country'] == country
        idx = big_moves[mask].index

        # Get forward returns
        etf_returns = big_moves.loc[idx, 'etf_return'].values

        # T+0 = same day
        big_moves.loc[idx, 'etf_return_0d'] = etf_returns

        # T+1 = next day
        t1 = np.roll(etf_returns, -1)
        big_moves.loc[idx[:-1], 'etf_return_1d'] = t1[:-1]
        big_moves.loc[idx[-1], 'etf_return_1d'] = 0

        # T+5 = 5-day cumulative
        t5 = np.zeros(len(etf_returns))
        for i in range(len(etf_returns) - 5):
            t5[i] = etf_returns[i:i+5].sum()
        big_moves.loc[idx[:-5], 'etf_return_5d'] = t5[:-5]
        big_moves.loc[idx[-5:], 'etf_return_5d'] = 0

    # Analysis
    print("\n" + "=" * 70)
    print("ANALYSIS: Does ETF Catch Up?")
    print("=" * 70)

    # On big move day
    print("\nBIG MOVE DAY (T+0):")
    print(f"  Mean local return: {big_moves['local_return'].mean()*100:.2f}%")
    print(f"  Mean ETF return:   {big_moves['etf_return_0d'].mean()*100:.2f}%")
    print(f"  Mean gap (local - ETF): { (big_moves['local_return'] - big_moves['etf_return_0d']).mean()*100:.2f}%")

    # After big move
    print("\nETF AFTER BIG MOVE (did it catch up?):")
    print(f"  ETF T+1 return: {big_moves['etf_return_1d'].mean()*100:.2f}%")
    print(f"  ETF T+5 return: {big_moves['etf_return_5d'].mean()*100:.2f}%")

    # Check if gap closes
    gap = big_moves['local_return'] - big_moves['etf_return_0d']
    etf_5d = big_moves['etf_return_5d']

    # If ETF moves more than 50% of the gap in 5 days, gap is closing
    catch_up = (etf_5d.abs() > gap.abs() * 0.5).mean()
    print(f"\n  Gap closes by 50%+ in 5 days: {catch_up*100:.1f}%")

    # Directional split
    up = big_moves[big_moves['local_return'] > 0]
    down = big_moves[big_moves['local_return'] < 0]

    print("\nUP MOVES (local > 0):")
    print(f"  Mean local: {up['local_return'].mean()*100:.2f}%")
    print(f"  Mean ETF T+0: {up['etf_return_0d'].mean()*100:.2f}%")
    print(f"  Mean gap: {(up['local_return'] - up['etf_return_0d']).mean()*100:.2f}%")

    print("\nDOWN MOVES (local < 0):")
    print(f"  Mean local: {down['local_return'].mean()*100:.2f}%")
    print(f"  Mean ETF T+0: {down['etf_return_0d'].mean()*100:.2f}%")
    print(f"  Mean gap: {(down['local_return'] - down['etf_return_0d']).mean()*100:.2f}%")

    # Save
    output_path = OUTPUT_DIR / 'full_test_results.csv'
    big_moves.to_csv(output_path, index=False)
    print(f"\n\nResults saved to: {output_path}")


if __name__ == '__main__':
    main()
