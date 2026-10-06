#!/usr/bin/env python
"""
==============================================================================
SCRIPT NAME: intraday_execution.py
VERSION:     1.0  (2026-10-05)
==============================================================================

DESCRIPTION
-----------
Rebuilds the implementable one-day country-ETF reversal test from Bloomberg
1-minute data (2026-04-06 -> 2026-10-02, ~125 US sessions; all US daylight
time, so 19:29 UTC = 15:29 ET) and compares execution methods.  Answers:

  1. LEAKAGE CHECK (GPT-5.6 review item 1): the earlier E5 test used Yahoo's
     60-minute bar "open" stamped 15:30 - the first trade anywhere in
     15:30-16:00, which for thin ETFs can be much later than 15:30.  Here the
     signal uses the 15:29 NBBO midpoint (close of the 15:29 BID and ASK
     1-minute bars).  Same days, both signals, compared head to head.
  2. EXECUTION: entry on day T and exit on day T+1 by the same method:
       MOC        official closing price (Bloomberg PX_LAST, unadjusted)
       TWAP_mid   average 1-minute NBBO midpoint 15:45-15:59 (optimistic:
                  assumes passive fills at mid)
       TWAP_cross average ask (buys) / bid (sells) 15:45-15:59 (pessimistic:
                  crosses the spread every minute)
       VWAP_1558  trade VWAP of 15:45-15:58 bars (excludes the 15:59 bar, which
                  contains the closing cross)
  3. SLIPPAGE per trade vs the closing price, for the names actually picked,
     and the price drift from 15:29 to the close for picked losers.
  4. LIQUIDITY: median $ traded in the final minute (closing cross included)
     vs in 15:45-15:58, per ETF.

Books: 7-name long-only losers (vs equal-weight at MOC), 7-name long-short,
1-name raw, 1-name relative-vol ("vol-scaled": (r - xs mean)/own 60d std).
Dividends: on an ex-date the dividend is added back to the signal price
(price already ex) and paid to whoever held into the ex-date; it is NOT paid
on a same-day entry (fixes the bug GPT found in etf_gap_fill_intraday.py).
Eligibility uses only information known at T.  Gross of costs except where
the method itself embeds them (TWAP_cross).  ~125 days: Sharpes are noisy;
the per-trade slippage numbers are the robust output.

INPUT FILES
-----------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/bbg_auction/intraday/<TICKER>_<TRADE|BID|ASK>.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/bbg_auction/daily.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_daily_unadj.parquet   (Yahoo dividends)
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_hourly.parquet        (Yahoo 15:30 bar, for the leakage comparison)
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_ohlcv_34.parquet      (trailing vol)

OUTPUT FILES
------------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/runs/execution_<timestamp>/
      execution_results.xlsx, execution_report.pdf (+ PNG renders),
      panel.parquet, summary.json, log.txt

DEPENDENCIES
------------
  pandas, numpy, statsmodels, matplotlib, openpyxl (project venv); pdftoppm

USAGE
-----
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
  venv/bin/python experiments/2026_10_etf_gap_fill/intraday_execution.py
==============================================================================
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd
import statsmodels.api as sm

sys.path.insert(0, str(Path(__file__).parent))
import etf_reversal_sweep as sw  # noqa: E402

EXP = sw.EXP
BB = EXP / 'data/bbg_auction'
TICK = sw.UNIVERSE


class Tee(sw.Tee):
    pass


def minute_tables():
    """Return dict of DataFrames indexed by date x ticker."""
    recs = {k: {} for k in ['mid1529', 'bid1529', 'ask1529', 'last1529', 'twap_mid', 'twap_ask', 'twap_bid',
                            'vwap1558', 'val_1545_1558', 'val_final_min', 'spread_1545_1559_bp']}
    for t in TICK:
        try:
            tr = pd.read_parquet(BB / 'intraday' / f'{t}_TRADE.parquet')
        except FileNotFoundError:
            print(f"  missing intraday TRADE for {t}")
            continue
        try:
            bd = pd.read_parquet(BB / 'intraday' / f'{t}_BID.parquet')
            ak = pd.read_parquet(BB / 'intraday' / f'{t}_ASK.parquet')
        except FileNotFoundError:
            # QQQ/SPY/IWM: quote bars not collected (spread ~0.3bp); use the minute's last
            # trade as both bid and ask, i.e. mid = last trade, zero quoted spread
            print(f"  {t}: no quote bars, using trade prices as mid")
            bd = tr[['time', 'close']].copy()
            ak = tr[['time', 'close']].copy()
        for df in (tr, bd, ak):
            df['date'] = df['time'].dt.normalize()
            df['hm'] = df['time'].dt.strftime('%H:%M')
        q = pd.merge(bd[['time', 'date', 'hm', 'close']].rename(columns={'close': 'bid'}),
                     ak[['time', 'close']].rename(columns={'close': 'ask'}), on='time', how='outer').sort_values('time')
        q['date'] = q['time'].dt.normalize()
        q['hm'] = q['time'].dt.strftime('%H:%M')
        # carry last quote forward within a day (a bar exists only if the quote changed)
        q[['bid', 'ask']] = q.groupby('date')[['bid', 'ask']].ffill()
        q = q[(q.ask >= q.bid) & (q.bid > 0)]   # >= keeps trade-as-mid rows (QQQ/SPY/IWM)
        q['mid'] = (q.bid + q.ask) / 2
        # 15:29 quote = last quote at or before the 19:29 bar
        pre = q[q.hm <= '19:29'].groupby('date').last()
        recs['mid1529'][t] = pre['mid']
        recs['bid1529'][t] = pre['bid']
        recs['ask1529'][t] = pre['ask']
        # minute grid 15:45-15:59 with forward-filled quotes
        w = q[(q.hm >= '19:45') & (q.hm <= '19:59')]
        g = w.groupby('date')
        recs['twap_mid'][t] = g['mid'].mean()
        recs['twap_ask'][t] = g['ask'].mean()
        recs['twap_bid'][t] = g['bid'].mean()
        recs['spread_1545_1559_bp'][t] = ((w.ask - w.bid) / w.mid * 1e4).groupby(w.date).median()
        trw = tr[(tr.hm >= '19:45') & (tr.hm <= '19:58')]
        gt = trw.groupby('date')
        recs['vwap1558'][t] = gt['value'].sum() / gt['volume'].sum().replace(0, np.nan)
        recs['val_1545_1558'][t] = gt['value'].sum()
        recs['val_final_min'][t] = tr[tr.hm == '19:59'].groupby('date')['value'].sum()
        lt = tr[(tr.hm <= '19:29') & (tr.volume > 0)].groupby('date').last()
        recs['last1529'][t] = lt['close']
    return {k: pd.DataFrame(v).reindex(columns=TICK) for k, v in recs.items()}


def main():
    run = EXP / 'runs' / ('execution_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    run.mkdir(parents=True)
    sys.stdout = Tee(run / 'log.txt')
    print(f"Run dir: {run}")
    m = minute_tables()
    days = m['mid1529'].dropna(how='all').index.sort_values()
    print(f"Intraday days: {len(days)} ({days.min().date()} -> {days.max().date()}), "
          f"tickers with data: {m['mid1529'].notna().any().sum()}")

    d = pd.read_parquet(BB / 'daily.parquet')
    d['date'] = pd.to_datetime(d['date'])
    close_all = d[d.field == 'PX_LAST'].pivot(index='date', columns='ticker', values='value').reindex(columns=TICK)
    du = pd.read_parquet(EXP / 'data/etf_daily_unadj.parquet')
    div_all = du['div'].reindex(columns=TICK).fillna(0.0)
    div_all.index = pd.to_datetime(div_all.index)
    e1, _ = sw.load()
    sd_all = e1['sd']

    close = close_all.reindex(days)
    prev_close = close_all.shift(1).reindex(days)          # previous US trading day's official close
    div = div_all.reindex(days).fillna(0.0)
    sd = sd_all.reindex(days)

    # signals
    sig_bbg = (m['mid1529'] + div) / prev_close - 1
    hourly = pd.read_parquet(EXP / 'data/etf_hourly.parquet')
    y1530 = hourly[hourly.index.time == pd.Timestamp('15:30').time()].reindex(columns=TICK)
    y1530.index = y1530.index.normalize()
    cu_y = du['close'].reindex(columns=TICK)
    cu_y.index = pd.to_datetime(cu_y.index)
    sig_yahoo = (y1530.reindex(days) + div) / cu_y.shift(1).reindex(days) - 1
    for s in (sig_bbg, sig_yahoo):
        s[s.abs() > 0.3] = np.nan

    # execution prices on day t: entry/exit price by method
    px = {'MOC': close, 'TWAP_mid': m['twap_mid'].reindex(days), 'VWAP_1558': m['vwap1558'].reindex(days)}
    # forward returns by method: enter at P_t, exit at P_t+1; dividend on t+1 ex-date paid to the holder
    nxt_div = div.shift(-1).fillna(0.0)

    def fwd(entry, exit_):
        return (exit_.shift(-1) + nxt_div) / entry - 1
    F = {k: fwd(v, v) for k, v in px.items()}
    F['TWAP_cross'] = fwd(m['twap_ask'].reindex(days), m['twap_bid'].reindex(days))   # buy at ask, sell at bid
    for k in F:
        F[k] = F[k].where(F[k].abs() < 0.3)
    ew_moc = F['MOC'].mean(axis=1)

    def build(sig, kind, n, ls=False):
        ok = sig.notna() & sd.notna() & close.notna()
        s, sdd = sig.where(ok), sd.where(ok)
        valid = ok.sum(axis=1) >= 10
        rank_m, size_m = sw.measure(s, sdd, kind)
        wl, _ = sw.select(rank_m, size_m, 0, n, -1)
        ws = sw.select(rank_m, size_m, 0, n, +1)[0] if ls else None
        return wl[valid], (ws[valid] if ls else None)

    def stats(x):
        x = x.dropna()
        t = sm.OLS(x.values, np.ones(len(x))).fit(cov_type='HAC', cov_kwds={'maxlags': 5}).tvalues[0]
        return x.mean() * 252, x.mean() / x.std() * np.sqrt(252), t, len(x)

    books = [('7-name long-only', 'raw', 7, False), ('7-name long-short', 'raw', 7, True),
             ('1-name raw', 'raw', 1, False), ('1-name vol-scaled', 'z_rel', 1, False)]
    rows, picks_store = [], {}
    for sname, sig in [('Bloomberg 15:29 mid', sig_bbg), ('Yahoo 15:30-bar open', sig_yahoo)]:
        for bname, kind, n, ls in books:
            wl, ws = build(sig, kind, n, ls)
            picks_store[(sname, bname)] = (wl, ws)
            for meth, Fm in F.items():
                f = Fm.reindex(wl.index)
                lo = (wl * f.fillna(0)).sum(axis=1)
                act = lo - ew_moc.reindex(wl.index)
                if ls:
                    act = lo - (ws * f.fillna(0)).sum(axis=1)
                a, sh, t, nd = stats(act.iloc[:-1])
                rows.append({'signal': sname, 'book': bname, 'execution': meth, 'ann_active': a,
                             'sharpe': sh, 'nw_t': t, 'days': nd})
    res = pd.DataFrame(rows)
    pd.set_option('display.width', 250)
    print("\n=== 1. LEAKAGE CHECK: same days, MOC execution, Bloomberg 15:29 mid vs Yahoo 15:30-bar signal ===")
    print(res[res.execution == 'MOC'].pivot(index='book', columns='signal', values='sharpe').round(2).to_string())
    print("\n=== 2. EXECUTION METHODS (signal = Bloomberg 15:29 mid) ===")
    print(res[res.signal == 'Bloomberg 15:29 mid'].pivot(index='book', columns='execution', values='ann_active').round(3).to_string())
    print("Sharpe:")
    print(res[res.signal == 'Bloomberg 15:29 mid'].pivot(index='book', columns='execution', values='sharpe').round(2).to_string())

    # 3. slippage per trade vs close for picked names (entries = buys of losers)
    slip = []
    for bname in ['7-name long-only', '1-name raw', '1-name vol-scaled']:
        wl, _ = picks_store[('Bloomberg 15:29 mid', bname)]
        entries = (wl > 0) & ~(wl.shift(1) > 0)          # new buys
        exits = ~(wl > 0) & (wl.shift(1) > 0)            # sells
        for meth, P in [('TWAP_mid', m['twap_mid']), ('VWAP_1558', m['vwap1558']), ('TWAP_cross', None)]:
            Pb = m['twap_ask'] if meth == 'TWAP_cross' else P
            Ps = m['twap_bid'] if meth == 'TWAP_cross' else P
            buy_slip = ((Pb.reindex(days) - close) / close * 1e4).where(entries.reindex(days, fill_value=False)).stack().dropna()
            sell_slip = ((close - Ps.reindex(days)) / close * 1e4).where(exits.reindex(days, fill_value=False)).stack().dropna()
            slip.append({'book': bname, 'execution': meth, 'buy_vs_close_bp_mean': buy_slip.mean(),
                         'buy_vs_close_bp_median': buy_slip.median(), 'n_buys': len(buy_slip),
                         'sell_vs_close_bp_mean': sell_slip.mean(), 'sell_vs_close_bp_median': sell_slip.median(),
                         'n_sells': len(sell_slip)})
        # drift 15:29 mid -> close for picked losers
        dr = ((close - m['mid1529'].reindex(days)) / m['mid1529'].reindex(days) * 1e4).where(wl.reindex(days, fill_value=0) > 0).stack().dropna()
        slip.append({'book': bname, 'execution': 'drift 15:29 mid -> close (picked losers)',
                     'buy_vs_close_bp_mean': dr.mean(), 'buy_vs_close_bp_median': dr.median(), 'n_buys': len(dr)})
    slip = pd.DataFrame(slip)
    print("\n=== 3. SLIPPAGE vs CLOSE (bp; positive = worse than the close for us) ===")
    print(slip.round(1).to_string(index=False))

    # 4. liquidity
    liq = pd.DataFrame({'final_minute_usd_median': m['val_final_min'].median(),
                        'usd_1545_1558_median': m['val_1545_1558'].median(),
                        'spread_1545_1559_bp_median': m['spread_1545_1559_bp'].median(),
                        'spread_at_1529_bp_median': ((m['ask1529'] - m['bid1529']) / m['mid1529'] * 1e4).median()})
    liq['window_vs_final_minute'] = liq['usd_1545_1558_median'] / liq['final_minute_usd_median']
    print("\n=== 4. LIQUIDITY near the close (median per day) ===")
    print(liq.sort_values('final_minute_usd_median').round(1).to_string())

    # charts
    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False})
    pdfp = run / 'execution_report.pdf'
    with PdfPages(pdfp) as pdf:
        fig, axes = plt.subplots(1, 3, figsize=(13, 4.2), sharey=True)
        for ax, bname in zip(axes, ['7-name long-only', '1-name raw', '1-name vol-scaled']):
            wl, _ = picks_store[('Bloomberg 15:29 mid', bname)]
            for meth, col in [('MOC', '#1f5fa8'), ('TWAP_mid', '#7a9a01'), ('VWAP_1558', '#e69f00'), ('TWAP_cross', '#c0504d')]:
                f = F[meth].reindex(wl.index)
                act = ((wl * f.fillna(0)).sum(axis=1) - ew_moc.reindex(wl.index)).iloc[:-1]
                ax.plot(act.index, act.cumsum(), color=col, lw=1.1, label=meth)
            ax.axhline(0, color='black', lw=0.4)
            ax.set_title(bname, loc='left')
            ax.tick_params(axis='x', rotation=45)
        axes[0].legend(frameon=False, fontsize=8)
        axes[0].set_ylabel('cumulative active return vs EW')
        fig.suptitle('Execution method comparison, signal = Bloomberg 15:29 midpoint (2026-04 to 2026-10)', x=0.01, ha='left')
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(12, 5))
        s = liq.sort_values('final_minute_usd_median')
        x = np.arange(len(s))
        ax.bar(x - 0.2, s['final_minute_usd_median'] / 1e3, 0.4, color='#c0504d', label='final minute incl. closing cross')
        ax.bar(x + 0.2, s['usd_1545_1558_median'] / 1e3, 0.4, color='#1f5fa8', label='15:45-15:58 continuous trading')
        ax.set_yscale('log')
        ax.set_xticks(x, s.index, rotation=90, fontsize=8)
        ax.set_ylabel('median $ traded per day (thousands, log scale)')
        ax.set_title('Liquidity near the close by ETF', loc='left')
        ax.legend(frameon=False, fontsize=8)
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)
    subprocess.run(['pdftoppm', '-png', '-r', '100', str(pdfp), str(run / 'execution_report')], check=True)

    with pd.ExcelWriter(run / 'execution_results.xlsx') as w:
        res.to_excel(w, sheet_name='books_by_execution', index=False)
        slip.to_excel(w, sheet_name='slippage', index=False)
        liq.to_excel(w, sheet_name='liquidity')
    json.dump({'run_dir': str(run), 'days': len(days), 'results': res.round(4).to_dict(orient='records'),
               'slippage': slip.round(2).to_dict(orient='records')},
              open(run / 'summary.json', 'w'), indent=2, default=str)
    print(f"\nDone. {run}")


if __name__ == '__main__':
    main()
