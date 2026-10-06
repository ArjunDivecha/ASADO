#!/usr/bin/env python
"""
==============================================================================
SCRIPT NAME: etf_gap_fill.py
VERSION:     1.0  (2026-10-05)
==============================================================================

DESCRIPTION
-----------
Corrected test of the "ETF gap-fill" idea: when a country's local equity index
moves and its US-listed country ETF moves by a different amount on the same
day, does the ETF "catch up" over the following 1-5 US trading days?  If so,
buying ETFs whose local market outran them (and selling the reverse) should
make money.

This replaces scripts/analysis/etf_lag_full_test.py (another session,
2026-10-05), which had three fatal flaws:
  1. It used T2 `1DRet` as the same-day local return.  `1DRet` is a FORWARD
     return: the row dated D holds the return realised on the next trading
     day (e.g. the row dated Sun 2024-08-04 holds Japan's -10% of Mon
     2024-08-05).  So its "same-day gap" compared tomorrow's local move with
     today's ETF move.
  2. Its T+1 / T+5 ETF returns were computed after filtering to big-move days
     only, so "the next day" was the next BIG-MOVE day (often weeks later).
  3. Its "gap closes" test counted an ETF move of half the gap in EITHER
     direction as closing.
  (Also: wrong tickers - EPP for Spain, FXI for ChinaA, 'UK' not 'U.K.'.)

Method here
  * Local return actually realised on calendar day d = 1DRet dated d-1
    (calendar-daily rows, weekends/holidays carry 0).  T2 returns are USD.
  * Local returns are COMPOUNDED over exactly the interval spanned by each US
    ETF close-to-close return (prev US trading date, T], so US holidays and
    local holidays are handled.
  * gap_T = local_T - ETF_T (positive = local outran the ETF).
  * Tests:
      A. Alignment: corr(ETF_T, local_{T+k}) and corr(local_T, ETF_{T+k}) for
         k = -1, 0, +1 -- tells us WHICH side lags.
      B. Predictive: Fama-MacBeth cross-sectional slope of ETF fwd 1d / 5d on
         gap_T (Newey-West t), and per-country time-series slopes.
      C. Event study (the other session's intent, done right): days with
         |local_T| > 2%; mean of sign(gap_T) * ETF return T+1..T+5.
      D. Reverse direction: does (ETF_T - local_T) predict local_{T+1}?
      E. Strategy (gross, no costs per house rules): each day long the
         top-quintile gap ETFs / short the bottom quintile, hold 1 day; plus
         long-only top quintile vs the equal-weight ETF benchmark.  Reported
         Full / 5y / 3y / 1y.
  Groups: Asia-Pacific (local close well before US open), Europe/Africa/ME
  (local close mid US session), Americas (near-simultaneous close; control).
  U.S., NASDAQ and US SmallCap are excluded (ETF is the same market).

INPUT FILES
-----------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
      table t2_factors_daily, variable '1DRet' (read-only, connection opened
      once and closed immediately; result cached to the parquet below)
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/config/etf_t2_map.json
      canonical country -> US ETF map
  Yahoo Finance (network, via yfinance): adjusted daily closes for the ETFs

OUTPUT FILES (all under the run directory)
------------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/local_1dret.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_prices.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/runs/<timestamp>/
      panel.parquet            aligned daily panel (date, country, local, etf, gap, fwd)
      alignment.xlsx           test A
      predictive.xlsx          tests B and D (Fama-MacBeth + per-country)
      event_study.xlsx         test C
      strategy.xlsx            test E (daily returns + window stats)
      summary.json             headline numbers
      log.txt                  stdout copy

DEPENDENCIES
------------
  pandas, numpy, duckdb, yfinance, statsmodels, openpyxl (project venv)

USAGE
-----
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
  venv/bin/python experiments/2026_10_etf_gap_fill/etf_gap_fill.py [--refresh]

NOTES
-----
  * Gross returns only; no cost or turnover penalties (25bp law retracted).
  * Strategy assumes the gap is observable at the ETF close (local close is
    hours earlier for Asia/Europe; ETF uses its own close - in practice a
    15:50 ET print, a small idealisation).
==============================================================================
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path('/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO')
EXP = ROOT / 'experiments/2026_10_etf_gap_fill'
DATA = EXP / 'data'
DB = ROOT / 'Data/asado.duckdb'
MAP = ROOT / 'config/etf_t2_map.json'

EXCLUDE = {'U.S.', 'NASDAQ', 'US SmallCap'}
ASIA = {'Australia', 'ChinaA', 'ChinaH', 'Hong Kong', 'India', 'Indonesia', 'Japan', 'Korea',
        'Malaysia', 'Philippines', 'Singapore', 'Taiwan', 'Thailand', 'Vietnam'}
# Large, liquid, long-history country ETFs (closing print close to NAV)
LIQUID = {'EWJ', 'EWZ', 'EWG', 'EWT', 'EWY', 'MCHI', 'INDA', 'EWU', 'EWC', 'EWA', 'EWH', 'EWW', 'EWQ', 'EWL'}
AMERICAS = {'Brazil', 'Canada', 'Chile', 'Mexico'}


def region(c):
    return 'Asia-Pacific' if c in ASIA else ('Americas' if c in AMERICAS else 'Europe/Africa/ME')


class Tee:
    def __init__(self, path):
        self.f = open(path, 'w')
        self.out = sys.stdout

    def write(self, s):
        self.f.write(s)
        self.out.write(s)

    def flush(self):
        self.f.flush()
        self.out.flush()


def load_local(refresh):
    p = DATA / 'local_1dret.parquet'
    if p.exists() and not refresh:
        return pd.read_parquet(p)
    con = duckdb.connect(str(DB), read_only=True)
    try:
        df = con.execute("SELECT date, country, value FROM t2_factors_daily WHERE variable='1DRet'").fetchdf()
    finally:
        con.close()
    df['date'] = pd.to_datetime(df['date'])
    df.to_parquet(p)
    return df


def load_etfs(tickers, refresh):
    p = DATA / 'etf_prices.parquet'
    if p.exists() and not refresh:
        return pd.read_parquet(p)
    import yfinance as yf
    px = yf.download(sorted(set(tickers)), start='1999-12-01', auto_adjust=True, progress=False)['Close']
    px.index = pd.to_datetime(px.index).tz_localize(None)
    px.to_parquet(p)
    return px


def build_panel(local, px, cmap):
    # Realised local return on calendar day d = 1DRet dated d-1
    loc = local.pivot(index='date', columns='country', values='value').sort_index()
    loc.index = loc.index + pd.Timedelta(days=1)
    loc = loc.fillna(0.0)
    cum = np.log1p(loc).cumsum()

    rows = []
    for country, etf in cmap.items():
        if country in EXCLUDE or country not in loc.columns or etf not in px.columns:
            continue
        s = px[etf].dropna()
        s = s[s > 0]
        dates = s.index
        dates = dates[(dates > cum.index[0]) & (dates <= cum.index[-1])]
        if len(dates) < 300:
            continue
        lc = cum[country].reindex(dates, method='ffill')
        d = pd.DataFrame({'date': dates, 'country': country, 'etf_ticker': etf})
        d['etf'] = s.reindex(dates).pct_change().values
        d['local'] = np.expm1(lc.diff()).values
        # local_traded: did local actually move over the interval (0 => holiday/no data)
        d['local_traded'] = d['local'].abs() > 1e-12
        d['gap'] = d['local'] - d['etf']
        e = d['etf'].values
        d['etf_f1'] = np.r_[e[1:], np.nan]
        lp = np.log1p(d['etf'])
        d['etf_f5'] = np.expm1(lp[::-1].rolling(5).sum()[::-1].shift(-1)).values
        d['etf_lag1'] = d['etf'].shift(1)
        d['etf_f2'] = d['etf'].shift(-2)  # return on T+2: signal at T, enter at T+1 close
        d['local_f1'] = d['local'].shift(-1)
        d['local_lag1'] = d['local'].shift(1)
        d['region'] = region(country)
        rows.append(d.iloc[1:])
    panel = pd.concat(rows, ignore_index=True)
    # Drop absurd prints (data errors) rather than let them drive slopes
    bad = (panel['etf'].abs() > 0.4) | (panel['local'].abs() > 0.4)
    print(f"Dropping {bad.sum()} rows with |return| > 40% (data errors)")
    return panel[~bad].reset_index(drop=True)


def nw_t(x, lags):
    x = pd.Series(x).dropna()
    if len(x) < 30:
        return np.nan, np.nan, len(x)
    m = sm.OLS(x.values, np.ones(len(x))).fit(cov_type='HAC', cov_kwds={'maxlags': lags})
    return m.params[0], m.tvalues[0], len(x)


def test_alignment(panel):
    out = []
    for c, g in panel.groupby('country'):
        g = g[g['local_traded']]
        out.append({
            'country': c, 'region': region(c), 'n': len(g),
            'corr_etf_t__local_t-1': g['etf'].corr(g['local_lag1']),
            'corr_etf_t__local_t': g['etf'].corr(g['local']),
            'corr_etf_t__local_t+1 (ETF leads)': g['etf'].corr(g['local_f1']),
            'corr_local_t__etf_t+1 (local leads)': g['local'].corr(g['etf_f1']),
            'beta_etf_on_local_same_day': np.polyfit(g['local'], g['etf'], 1)[0] if len(g) > 50 else np.nan,
        })
    return pd.DataFrame(out).sort_values(['region', 'country'])


def fama_macbeth(panel, y, x, lags, min_n=8):
    sl = []
    for dt, g in panel.groupby('date'):
        g = g[[y, x]].dropna()
        if len(g) < min_n or g[x].std() == 0:
            continue
        xs = g[x] - g[x].mean()
        sl.append(((xs * (g[y] - g[y].mean())).sum() / (xs ** 2).sum()))
    return nw_t(sl, lags)


def fama_macbeth_multi(panel, y, xs, lags, min_n=8):
    coefs = []
    for dt, g in panel.groupby('date'):
        g = g[[y] + xs].dropna()
        if len(g) < min_n + len(xs):
            continue
        X = g[xs] - g[xs].mean()
        try:
            b = np.linalg.lstsq(X.values, (g[y] - g[y].mean()).values, rcond=None)[0]
        except np.linalg.LinAlgError:
            continue
        coefs.append(b)
    c = pd.DataFrame(coefs, columns=xs)
    out = {'n_days': len(c)}
    for x in xs:
        m, t, _ = nw_t(c[x], lags)
        out[f'b_{x}'] = m
        out[f't_{x}'] = t
    return out


def ts_slopes(panel, y, x, lags):
    out = []
    for c, g in panel.groupby('country'):
        g = g[[y, x]].dropna()
        if len(g) < 250:
            continue
        m = sm.OLS(g[y], sm.add_constant(g[x])).fit(cov_type='HAC', cov_kwds={'maxlags': lags})
        out.append({'country': c, 'region': region(c), 'n': len(g),
                    'slope': m.params[x], 't': m.tvalues[x]})
    return pd.DataFrame(out).sort_values(['region', 'country'])


def window_stats(r, label):
    r = r.dropna()
    end = r.index.max()
    res = []
    for name, start in [('Full', r.index.min()), ('5y', end - pd.DateOffset(years=5)),
                        ('3y', end - pd.DateOffset(years=3)), ('1y', end - pd.DateOffset(years=1))]:
        x = r[r.index > start] if name != 'Full' else r
        ann = x.mean() * 252
        vol = x.std() * np.sqrt(252)
        res.append({'series': label, 'window': name, 'start': x.index.min().date(),
                    'ann_return': ann, 'ann_vol': vol, 'sharpe': ann / vol if vol > 0 else np.nan,
                    't_stat': x.mean() / x.std() * np.sqrt(len(x)) if x.std() > 0 else np.nan,
                    'days': len(x)})
    return res


def strategy(panel, mask=None, min_n=10, sig='gap', fwd='etf_f1'):
    p = panel[panel['local_traded']] if mask is None else panel[panel['local_traded'] & mask]
    ls, lo, ew = {}, {}, {}
    for dt, g in p.groupby('date'):
        g = g.dropna(subset=[sig, fwd])
        if len(g) < min_n:
            continue
        q = g[sig].rank(pct=True)
        top, bot = g[q > 0.8], g[q <= 0.2]
        ls[dt] = top[fwd].mean() - bot[fwd].mean()
        lo[dt] = top[fwd].mean()
        ew[dt] = g[fwd].mean()
    s = pd.DataFrame({'long_short': ls, 'long_top_quintile': lo, 'ew_benchmark': ew})
    s['long_minus_ew'] = s['long_top_quintile'] - s['ew_benchmark']
    return s


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--refresh', action='store_true')
    args = ap.parse_args()

    DATA.mkdir(parents=True, exist_ok=True)
    run = EXP / 'runs' / datetime.now().strftime('%Y%m%d_%H%M%S')
    run.mkdir(parents=True)
    sys.stdout = Tee(run / 'log.txt')
    print(f"Run dir: {run}")

    cmap = {k: v['primary'] for k, v in json.load(open(MAP))['map'].items()}
    local = load_local(args.refresh)
    print(f"Local 1DRet rows: {len(local):,}  {local['date'].min().date()} -> {local['date'].max().date()}")
    px = load_etfs([v for k, v in cmap.items() if k not in EXCLUDE], args.refresh)
    print(f"ETF prices: {px.shape[1]} tickers, {px.index.min().date()} -> {px.index.max().date()}")

    # Sanity check of the 1DRet realignment on the 2024-08-05 Japan crash
    jp = local[(local.country == 'Japan') & (local.date.between('2024-08-01', '2024-08-06'))]
    print("1DRet Japan (as stored, dated d):\n", jp[['date', 'value']].to_string(index=False))

    panel = build_panel(local, px, cmap)
    panel.to_parquet(run / 'panel.parquet')
    print(f"Panel: {len(panel):,} rows, {panel.country.nunique()} countries, "
          f"{panel.date.min().date()} -> {panel.date.max().date()}")
    chk = panel[(panel.country == 'Japan') & panel.date.between('2024-08-01', '2024-08-07')]
    print("Aligned Japan around the crash:\n", chk[['date', 'local', 'etf', 'gap', 'etf_f1']].to_string(index=False))

    summary = {'run_dir': str(run)}

    # A. alignment
    al = test_alignment(panel)
    al.to_excel(run / 'alignment.xlsx', index=False)
    print("\n=== A. WHO LAGS WHOM (correlations) ===")
    print(al.groupby('region')[[c for c in al.columns if c.startswith('corr') or c.startswith('beta')]].median().round(3).to_string())

    # B/D. predictive
    pt = panel[panel['local_traded']]
    print("\n=== B. DOES THE GAP PREDICT THE ETF? (Fama-MacBeth slope, NW t) ===")
    fm_rows = []
    for reg in ['ALL', 'Asia-Pacific', 'Europe/Africa/ME', 'Americas']:
        sub = pt if reg == 'ALL' else pt[pt.region == reg]
        mn = 8 if reg == 'ALL' else 4
        for y, lags in [('etf_f1', 5), ('etf_f5', 10), ('local_f1', 5)]:
            x = 'gap'
            b, t, n = fama_macbeth(sub, y, x, lags, mn)
            fm_rows.append({'universe': reg, 'y': y, 'x': x, 'slope': b, 'nw_t': t, 'n_days': n})
    fm = pd.DataFrame(fm_rows)
    print(fm.round(4).to_string(index=False))
    print("\n=== B2. DECOMPOSITION: is it gap-fill or plain ETF reversal? ===")
    dec = []
    for reg in ['ALL', 'Asia-Pacific', 'Europe/Africa/ME', 'Americas']:
        sub = pt if reg == 'ALL' else pt[pt.region == reg]
        mn = 8 if reg == 'ALL' else 4
        for y in ['etf_f1', 'etf_f2']:
            r = fama_macbeth_multi(sub, y, ['local', 'etf'], 5, mn)
            r.update({'universe': reg, 'y': y, 'model': 'y ~ local + etf'})
            dec.append(r)
            b, t, n = fama_macbeth(sub, y, 'gap', 5, mn)
            dec.append({'universe': reg, 'y': y, 'model': 'y ~ gap', 'b_gap': b, 't_gap': t, 'n_days': n})
            b, t, n = fama_macbeth(sub, y, 'etf', 5, mn)
            dec.append({'universe': reg, 'y': y, 'model': 'y ~ etf (pure reversal)', 'b_etf': b, 't_etf': t, 'n_days': n})
            b, t, n = fama_macbeth(sub, y, 'local', 5, mn)
            dec.append({'universe': reg, 'y': y, 'model': 'y ~ local only', 'b_local': b, 't_local': t, 'n_days': n})
    dec = pd.DataFrame(dec)
    print(dec.round(4).to_string(index=False))
    ts1 = ts_slopes(pt, 'etf_f1', 'gap', 5)
    ts5 = ts_slopes(pt, 'etf_f5', 'gap', 10)
    tsl = ts_slopes(pt, 'local_f1', 'gap', 5)
    with pd.ExcelWriter(run / 'predictive.xlsx') as w:
        fm.to_excel(w, sheet_name='fama_macbeth', index=False)
        dec.to_excel(w, sheet_name='decomposition', index=False)
        ts1.to_excel(w, sheet_name='ts_etf_f1_on_gap', index=False)
        ts5.to_excel(w, sheet_name='ts_etf_f5_on_gap', index=False)
        tsl.to_excel(w, sheet_name='ts_local_f1_on_gap', index=False)
    print("\nPer-country slope of ETF next-day return on gap (region medians, count t>2 / t<-2):")
    for nm, t_ in [('etf_f1', ts1), ('etf_f5', ts5), ('local_f1', tsl)]:
        g = t_.groupby('region').agg(median_slope=('slope', 'median'),
                                     n_t_gt2=('t', lambda s: (s > 2).sum()),
                                     n_t_lt_m2=('t', lambda s: (s < -2).sum()), n=('t', 'size'))
        print(f"-- {nm}\n{g.round(3).to_string()}")

    # C. event study
    print("\n=== C. BIG LOCAL MOVES (|local|>2%): signed ETF follow-through ===")
    ev = pt[pt['local'].abs() > 0.02].copy()
    sg = np.sign(ev['gap'])
    ev['signed_gap'] = ev['gap'].abs()
    ev['signed_f1'] = sg * ev['etf_f1']
    ev['signed_f5'] = sg * ev['etf_f5']
    ev['fill_frac_5d'] = ev['signed_f5'] / ev['signed_gap']
    evs = ev.groupby('region').agg(n=('gap', 'size'),
                                   mean_abs_gap=('signed_gap', 'mean'),
                                   mean_signed_f1=('signed_f1', 'mean'),
                                   mean_signed_f5=('signed_f5', 'mean'),
                                   pct_f5_toward_gap=('signed_f5', lambda s: (s > 0).mean()))
    allrow = pd.DataFrame([{'n': len(ev), 'mean_abs_gap': ev['signed_gap'].mean(),
                            'mean_signed_f1': ev['signed_f1'].mean(), 'mean_signed_f5': ev['signed_f5'].mean(),
                            'pct_f5_toward_gap': (ev['signed_f5'] > 0).mean()}], index=['ALL'])
    evs = pd.concat([evs, allrow])
    # t-stats clustered crudely by date (average per date first)
    for col in ['signed_f1', 'signed_f5']:
        m, t, n = nw_t(ev.groupby('date')[col].mean(), 5 if col == 'signed_f1' else 10)
        evs.loc['ALL', f't_{col}'] = t
    print((evs * 1).round(4).to_string())
    with pd.ExcelWriter(run / 'event_study.xlsx') as w:
        evs.to_excel(w, sheet_name='summary')
        ev.to_excel(w, sheet_name='events', index=False)

    # E. strategy
    print("\n=== E. STRATEGY (gross, daily, hold 1 day) ===")
    panel['neg_etf'] = -panel['etf']
    liquid = panel['etf_ticker'].isin(LIQUID)
    strat_all = strategy(panel)
    strat_asia = strategy(panel, panel.region == 'Asia-Pacific', min_n=6)
    variants = {
        'gap_hold1': strat_all,
        'gap_asia_hold1': strat_asia,
        'gap_DELAY1 (enter T+1 close)': strategy(panel, fwd='etf_f2'),
        'pure_etf_reversal_hold1': strategy(panel, sig='neg_etf'),
        'local_only_hold1': strategy(panel, sig='local'),
        'gap_liquid_only_hold1': strategy(panel, liquid, min_n=6),
        'gap_thin_only_hold1': strategy(panel, ~liquid, min_n=6),
    }
    stats = []
    for nm, s in variants.items():
        cols = ['long_short', 'long_minus_ew'] if nm != 'gap_hold1' else ['long_short', 'long_minus_ew', 'long_top_quintile', 'ew_benchmark']
        for col in cols:
            stats += window_stats(s[col], f'{nm}:{col}')
    st = pd.DataFrame(stats)
    print(st.round(3).to_string(index=False))
    with pd.ExcelWriter(run / 'strategy.xlsx') as w:
        st.to_excel(w, sheet_name='window_stats', index=False)
        strat_all.to_excel(w, sheet_name='daily_all')
        for nm, v in variants.items():
            v.to_excel(w, sheet_name=nm.split(' ')[0][:31])

    # yearly long-short for stability
    yr = strat_all['long_short'].groupby(strat_all.index.year).agg(lambda x: x.mean() * 252)
    print("\nLong-short annualised return by year (ALL):\n", yr.round(3).to_string())

    summary.update({
        'alignment_region_medians': al.groupby('region')[[c for c in al.columns if c.startswith('corr')]].median().round(4).to_dict(),
        'fama_macbeth': fm.round(5).to_dict(orient='records'),
        'event_study_all': evs.loc['ALL'].round(5).to_dict(),
        'strategy_stats': st.round(4).astype({'start': str}).to_dict(orient='records'),
    })
    json.dump(summary, open(run / 'summary.json', 'w'), indent=2, default=str)
    print(f"\nDone. {run}")


if __name__ == '__main__':
    main()
