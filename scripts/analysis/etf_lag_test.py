#!/usr/bin/env python
"""
ETF Lag Test: Big Local Moves Create Exploitable Gaps

The hypothesis: When the local market has a big move, the US-listed ETF
doesn't respond immediately, creating an exploitable gap.

Uses yfinance for ETF data (no Bloomberg needed).
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

# Paths
WAREHOUSE_DB = '/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb'
LOOP_DB = '/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb'
OUTPUT_DIR = Path('/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/analysis/etf_lag')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# ETF mapping: country → yfinance ticker
ETF_TICKERS = {
    'U.S.': 'SPY',  # US benchmark
    'Canada': 'EWC',
    'Mexico': 'EWW',
    'Brazil': 'EWZ',
    'Argentina': 'ARSN',  # May not be liquid
    'Chile': 'ECH',
    'Peru': 'EPU',
    'UK': 'EWU',
    'Germany': 'EWG',
    'France': 'EWQ',
    'Italy': 'EWI',
    'Spain': 'EPP',
    'Netherlands': 'EEX',
    'Switzerland': 'EWL',
    'Sweden': 'EWD',
    'Poland': 'EPOL',
    'Japan': 'EWJ',
    'ChinaA': 'FXI',  # Large cap China
    'ChinaH': 'KWEB',  # HK/China internet
    'Hong Kong': 'EWH',
    'Taiwan': 'EWT',
    'Korea': 'EWY',
    'India': 'INDA',
    'Indonesia': 'EIDO',
    'Malaysia': 'EWM',
    'Philippines': 'EPHE',
    'Thailand': 'THD',
    'Vietnam': 'VNM',
    'Australia': 'EWA',
    'New Zealand': 'ENZL',
    'Singapore': 'EWS',
    'Russia': 'RSX',
}


def get_etf_returns(tickers, start_date='2015-01-01', end_date=None):
    """Get daily ETF returns from yfinance."""
    if end_date is None:
        end_date = (datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d')

    print(f"Downloading ETF data: {start_date} to {end_date}")

    all_data = {}
    for country, ticker in tickers.items():
        try:
            print(f"  {country}: {ticker}", end='', flush=True)
            df = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if 'Close' in df.columns and len(df) > 0:
                df = df[['Close']].copy()
                df.columns = ['etf_close']
                df.index = pd.to_datetime(df.index).date
                all_data[country] = df
                print(f" OK ({len(df)} days)")
            else:
                print(f" FAILED (no data)")
        except Exception as e:
            print(f" ERROR: {e}")

    return all_data


def merge_etf_with_local(etf_data):
    """Convert ETF dict to merged DataFrame."""
    dfs = []
    for country, df in etf_data.items():
        df = df.copy()
        df['country'] = country
        df.index.name = 'date'
        df = df.reset_index()
        df['date'] = pd.to_datetime(df['date']).dt.date
        dfs.append(df)

    if len(dfs) == 0:
        return None

    merged = pd.concat(dfs, ignore_index=True)
    merged['return_1d'] = merged.groupby('country')['etf_close'].pct_change()
    merged['return_5d'] = merged.groupby('country')['etf_close'].pct_change(periods=5)

    return merged


def identify_big_moves(df, col='return_1d', percentile=90):
    """Identify days/countries with big moves."""
    df = df.copy()
    df['abs_return'] = df[col].abs()
    threshold = df['abs_return'].quantile(percentile / 100)
    big_moves = df[df['abs_return'] >= threshold].copy()
    return big_moves, threshold


def test_etf_lag(combiner_df, local_returns_df, etf_returns_df):
    """
    Test whether ETF lags local moves.

    Returns gap analysis.
    """
    print("\n=== Testing ETF Lag ===\n")

    # Merge all three
    merged = local_returns_df.merge(combiner_df, on=['date', 'country'])
    merged = merged.merge(etf_returns_df, on=['date', 'country'], suffixes=('_local', '_etf'))

    # Compute gap: local - ETF (positive = ETF behind)
    merged['gap_1d'] = merged['return_1d_local'] - merged['return_1d_etf']

    # Big moves
    big_moves, threshold = identify_big_moves(merged, col='return_1d_local')
    big_moves = big_moves.copy()

    print(f"Big move threshold: {threshold:.4f} ({threshold*100:.1f}% daily)")
    print(f"N big moves: {len(big_moves)}")

    # Gap statistics
    print(f"\nGap on big moves (local - ETF):")
    print(f"  Mean: {big_moves['gap_1d'].mean():.4f}")
    print(f"  Std: {big_moves['gap_1d'].std():.4f}")
    print(f"  Positive gaps: {(big_moves['gap_1d'] > 0).mean()*100:.1f}%")

    # Predictability: does combiner predict the gap?
    ic_gap = big_moves['signal'].corr(big_moves['gap_1d'])
    print(f"\nCan combiner predict the gap? (IC): {ic_gap:.4f}")

    # Exploitability: does predicting the gap work?
    # Strategy: go long where combiner says gap will be positive
    big_moves['rank'] = big_moves.groupby('date')['signal'].rank(pct=True)

    # If we predict gap direction, does it materialize?
    # This is the test: does combiner signal predict next-day ETF return
    # that differs from local return?
    print(f"\nCan we capture the lag?")
    ic_local = merged.groupby('date').apply(lambda x: x['signal'].corr(x['return_1d_local'])).mean()
    print(f"  IC on local returns: {ic_local:.4f}")

    if 'return_1d_etf' in merged.columns:
        ic_etf = merged.groupby('date').apply(lambda x: x['signal'].corr(x['return_1d_etf'])).mean()
        print(f"  IC on ETF returns: {ic_etf:.4f}")

        # Key test: if IC_etf < IC_local, ETF lags
        if ic_etf < ic_local:
            print(f"  → ETF IC is LOWER than local IC ({ic_local - ic_etf:+.4f})")
            print(f"  → This suggests ETF lag is exploitable")
        else:
            print(f"  → ETF IC is similar/higher - lag may not exist")


def main():
    print("=" * 70)
    print("ETF LAG TEST (using yfinance)")
    print("=" * 70)

    # Get local data
    print("\nLoading local data...")
    con = duckdb.connect(LOOP_DB)
    combiner_df = con.execute('''
        SELECT date, country, value as signal
        FROM combiner_scores_daily
        WHERE variable = 'COMBINER_RIDGE_DAILY_V1'
    ''').fetchdf()
    con.close()
    combiner_df['date'] = pd.to_datetime(combiner_df['date']).dt.date

    con = duckdb.connect(WAREHOUSE_DB)
    local_returns_df = con.execute('''
        SELECT date, country, value as return_1d
        FROM t2_factors_daily
        WHERE variable = '1DRet'
    ''').fetchdf()
    con.close()
    local_returns_df['date'] = pd.to_datetime(local_returns_df['date']).dt.date

    print(f"  Combiner: {len(combiner_df)} observations")
    print(f"  Local returns: {len(local_returns_df)} observations")

    # Get ETF data
    print("\nFetching ETF data from yfinance...")
    etf_data = get_etf_returns(ETF_TICKERS)

    if len(etf_data) == 0:
        print("FAILED to get ETF data. Check tickers/Internet connection.")
        return

    etf_returns_df = merge_etf_with_local(etf_data)

    if etf_returns_df is None:
        print("FAILED to merge ETF data.")
        return

    print(f"  ETF data: {len(etf_returns_df)} observations")
    print(f"  Countries: {etf_returns_df['country'].nunique()}")

    # Run test
    test_etf_lag(combiner_df, local_returns_df, etf_returns_df)

    # Save results
    output_path = OUTPUT_DIR / 'etf_lag_results.csv'
    etf_returns_df.to_csv(output_path, index=False)
    print(f"\n\nETF data saved to: {output_path}")


if __name__ == '__main__':
    main()
