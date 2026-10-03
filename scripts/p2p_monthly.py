"""P2P v2: completed adjusted monthly closes, available at next month start."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
from scipy.stats import linregress

VERSION = 'p2p-v2-completed-month-explicit-country'
MAPPING_PATH = Path(__file__).resolve().parents[1] / 'config/p2p_country_etfs.json'


def country_etfs():
    return json.loads(MAPPING_PATH.read_text())


def score_window(prices):
    # Preserve the original formula: 13 closes for the regression, 12 for peak.
    slope, _, correlation, _, _ = linregress(np.arange(len(prices)), prices)
    return float(prices.iloc[-1] / prices.iloc[-12:].max() * correlation**2
                 * (1 if slope > 0 else -1))


def compute_scores(prices, tickers, as_of=None):
    as_of = pd.Timestamp(as_of if as_of is not None else pd.Timestamp.now())
    if as_of.tzinfo is not None:
        as_of = as_of.tz_localize(None)
    current_month = as_of.to_period('M')
    frame = prices.copy()
    idx = pd.DatetimeIndex(frame.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    months = idx.to_period('M')
    if months.duplicated().any():
        raise ValueError('Duplicate monthly P2P bars')
    frame.index = months
    frame = frame.loc[frame.index < current_month].sort_index()
    if frame.empty:
        raise ValueError('No completed monthly P2P prices')
    frame = frame.reindex(pd.period_range(frame.index.min(), current_month - 1, freq='M'))
    frame = frame.reindex(columns=tickers).apply(pd.to_numeric, errors='coerce')
    if frame.iloc[-1].isna().any() or not np.isfinite(frame.iloc[-1]).all():
        raise ValueError('Missing latest completed P2P prices: ' + str(frame.columns[frame.iloc[-1].isna()].tolist()))
    result = pd.DataFrame(index=frame.index, columns=tickers, dtype=float)
    for i in range(12, len(frame)):
        for ticker in tickers:
            window = frame[ticker].iloc[i-12:i+1]
            if window.notna().all() and np.isfinite(window).all() and (window > 0).all():
                result.loc[frame.index[i], ticker] = score_window(window)
    # Historical production starts with January 2000 observations.
    result = result.loc[result.index >= pd.Period('2000-01', freq='M')]
    if result.empty or result.iloc[-1].isna().any():
        raise ValueError('Insufficient completed history for latest P2P score')
    result.index = (result.index + 1).to_timestamp()
    result.index.name = 'date'
    result.attrs['p2p_contract'] = {
        'version': VERSION, 'source': 'Yahoo Finance via yfinance',
        'adjustment': 'auto_adjust=True adjusted Close; snapshot, not historical vintages',
        'observation_month': 'M', 'availability_label': 'first day of M+1',
        'as_of': str(as_of), 'latest_complete_observation_month': str(current_month-1),
        'formula': '(last close / last-12-close peak) * R-squared(13 closes) * sign(slope)',
    }
    return result.reset_index()


def save_scores(scores, path, raw_path=None):
    path = Path(path)
    contract = dict(scores.attrs.get('p2p_contract', {}))
    if contract.get('version') != VERSION:
        raise ValueError('P2P v2 contract required')
    if raw_path is not None:
        raw_path = Path(raw_path)
        contract['raw_path'] = str(raw_path)
        contract['raw_sha256'] = hashlib.sha256(raw_path.read_bytes()).hexdigest()
    temp = path.with_name(path.stem+'.tmp.xlsx')
    with pd.ExcelWriter(temp, engine='xlsxwriter') as writer:
        scores.to_excel(writer, sheet_name='Sheet1', index=False)
        pd.DataFrame(list(contract.items()), columns=['key','value']).to_excel(writer, sheet_name='_P2P_contract', index=False)
    temp.replace(path)


def load_scores(path, as_of=None):
    path = Path(path)
    try:
        meta = pd.read_excel(path, sheet_name='_P2P_contract')
        contract = dict(zip(meta['key'], meta['value']))
    except (ValueError, KeyError) as exc:
        raise ValueError('Legacy/unversioned P2P cache: regenerate from monthly prices; do not relabel') from exc
    if contract.get('version') != VERSION:
        raise ValueError('Unsupported P2P timing contract')
    frame = pd.read_excel(path, sheet_name='Sheet1')
    dates = pd.to_datetime(frame.iloc[:, 0], errors='raise')
    cutoff = pd.Timestamp(as_of if as_of is not None else pd.Timestamp.now()).to_period('M').to_timestamp()
    if dates.duplicated().any() or not (dates.dt.day == 1).all() or dates.max() != cutoff:
        raise ValueError('P2P availability labels are duplicate, incomplete or stale')
    mapping = country_etfs()
    if set(frame.columns[1:]) != set(mapping.values()):
        raise ValueError('P2P ticker set differs from explicit country mapping')
    if frame.iloc[-1, 1:].isna().any():
        raise ValueError('Latest completed P2P scores are missing')
    # Select by ticker, never by first-valid-data insertion order or position.
    output = pd.DataFrame({'Country': dates})
    for country, ticker in mapping.items():
        output[country] = frame[ticker]
    return output
