#!/usr/bin/env python
"""
==============================================================================
SCRIPT NAME: auction_cost_analysis.py
VERSION:     1.1  (2026-10-06)
==============================================================================

DESCRIPTION
-----------
Implementation-cost study for the one-day country-ETF reversal trade executed
market-on-close (signal at 15:30 ET, enter at the close, exit next close).
This is the implementation-time cost question Arjun asked for explicitly; it
is reported separately from the (gross) research verdict.

Framing: the backtest already fills every trade at the official closing
(auction) price, so a MOC order does NOT pay a quoted spread relative to the
backtest.  The incremental cost of actually trading is
  (a) how far our own order pushes the auction price - for a small order that
      becomes the auction imbalance, roughly the half-spread market makers
      demand to absorb it; for larger orders, more (square-root impact);
  (b) commissions/fees.
Cost model per trade, per side, in bp of traded notional (v1.1, spread only):
    cost = k_spread * half_spread_preclose(i, t) + commission $/share / price
  (v1.0 also had a square-root impact term on ETF ADV; it was dropped because
  it contradicted the measured closing-window slippage - see the comment in
  main().  Size is reported instead as participation in the actual
  15:45-16:00 dollar volume.)
  half_spread_preclose(i,t) = 0.5 * TWAS(i,t) * ratio_i, where TWAS is
  Bloomberg's daily time-weighted average quoted spread and ratio_i is the
  ETF's median (pre-close quoted spread / TWAS) measured from 1-minute BID/ASK
  bars 15:50-15:58 ET over 2026-07..2026-10.  Daily TWAS lets spreads widen
  on volatile days (which is exactly when this trade picks a name).
  Scenarios: no cost; commission only; half pre-close spread (base); full
  pre-close spread; half the 15:59 'at the bell' spread.  Commission
  $0.0035/share.

Books (E5 timing; same construction as etf_reversal_sweep.py):
  7-name long-only losers vs EW, 7-name long-short, 1-name raw,
  1-name vol-scaled (rank on (r - xs mean)/own 60d std).  Costs are charged on
  |change in weight| each day for the strategy (the EW benchmark is treated as
  costless buy-and-hold).  Borrow costs for shorts are NOT modelled (noted).
  Account sizes: $1M, $5M, $25M, $100M.

INPUT FILES
-----------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/bbg_auction/daily.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/bbg_auction/ref.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/bbg_auction/intraday/<TICKER>_<EVENT>.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_ohlcv_34.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_hourly.parquet
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/data/etf_daily_unadj.parquet

OUTPUT FILES
------------
  /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/experiments/2026_10_etf_gap_fill/runs/costs_<timestamp>/
      cost_results.xlsx   per-ETF liquidity/spread table, net-of-cost scorecards,
                          sensitivities, capacity table
      cost_report.pdf     charts (spreads by ETF, gross vs net by account size)
      cost_report-<n>.png renders
      summary.json, log.txt

DEPENDENCIES
------------
  pandas, numpy, matplotlib, openpyxl (project venv); pdftoppm

USAGE
-----
  cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO"
  venv/bin/python experiments/2026_10_etf_gap_fill/auction_cost_analysis.py
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

sys.path.insert(0, str(Path(__file__).parent))
import etf_reversal_sweep as sw  # noqa: E402

EXP = sw.EXP
BB = EXP / 'data/bbg_auction'
TICK = sw.UNIVERSE
AUMS = [1e6, 5e6, 25e6, 100e6]
COMM = 0.0035


class Tee(sw.Tee):
    pass


def load_bbg():
    d = pd.read_parquet(BB / 'daily.parquet')
    d['date'] = pd.to_datetime(d['date'])
    wide = {f: d[d.field == f].pivot(index='date', columns='ticker', values='value').reindex(columns=TICK)
            for f in d.field.unique()}
    ref = pd.read_parquet(BB / 'ref.parquet').set_index('ticker')
    intra = {}
    for t in TICK:
        for ev in ['TRADE', 'BID', 'ASK']:
            p = BB / 'intraday' / f'{t}_{ev}.parquet'
            if p.exists():
                intra[(t, ev)] = pd.read_parquet(p)
    return wide, ref, intra


def preclose_spreads(intra):
    """Median quoted spread (bp of mid) 15:50-15:58 ET and at 15:59, plus final-minute $ volume."""
    rows = []
    for t in TICK:
        if (t, 'BID') not in intra or (t, 'ASK') not in intra:
            rows.append({'ticker': t})
            continue
        b = intra[(t, 'BID')].set_index('time')['close']
        a = intra[(t, 'ASK')].set_index('time')['close']
        q = pd.concat({'bid': b, 'ask': a}, axis=1).dropna()
        q = q[(q.ask > q.bid) & (q.bid > 0)]
        q['sp_bp'] = (q.ask - q.bid) / ((q.ask + q.bid) / 2) * 1e4
        hm = q.index.strftime('%H:%M')
        pre = q[(hm >= '19:50') & (hm <= '19:58')]
        bell = q[hm == '19:59']
        pre_daily = pre.groupby(pre.index.date)['sp_bp'].median()
        tr = intra.get((t, 'TRADE'))
        lastmin_val = np.nan
        if tr is not None and not tr.empty:
            tr = tr.set_index('time')
            lm = tr[tr.index.strftime('%H:%M') == '19:59']
            lastmin_val = lm['value'].median()
        rows.append({'ticker': t, 'preclose_spread_bp': pre_daily.median(),
                     'preclose_spread_bp_p90': pre_daily.quantile(0.9),
                     'bell_spread_bp': bell['sp_bp'].median(),
                     'final_minute_usd_median': lastmin_val, 'intraday_days': len(pre_daily),
                     '_pre_daily': pre_daily})
    return rows


def books_e5():
    e1, e5 = sw.load()
    ret, fwd, sd = e5['sig'], e5['fwd'], e5['sd']
    ok = ret.notna() & sd.notna()   # eligibility known at T (no future-availability filter)
    ret, fwd, sd = ret.where(ok), fwd.where(ok), sd.where(ok)
    valid = ok.sum(axis=1) >= 10
    f = fwd.fillna(0.0)
    ew = fwd.mean(axis=1)
    out = {}
    for name, kind, n, ls in [('7-name long-only', 'raw', 7, False), ('7-name long-short', 'raw', 7, True),
                              ('1-name raw', 'raw', 1, False), ('1-name vol-scaled', 'z_rel', 1, False)]:
        rank_m, size_m = sw.measure(ret, sd, kind)
        wl, _ = sw.select(rank_m, size_m, 0, n, -1)
        w = wl.copy()
        gross = (wl * f).sum(axis=1) - ew
        if ls:
            ws, _ = sw.select(rank_m, size_m, 0, 7 if n == 7 else n, +1)
            gross = gross + (ew - (ws * f).sum(axis=1))
            w = wl - ws
        out[name] = {'w': w[valid], 'gross': gross[valid]}
    return out, sd


def main():
    run = EXP / 'runs' / ('costs_' + datetime.now().strftime('%Y%m%d_%H%M%S'))
    run.mkdir(parents=True)
    sys.stdout = Tee(run / 'log.txt')
    print(f"Run dir: {run}")
    wide, ref, intra = load_bbg()
    print(f"Bloomberg daily {wide['PX_LAST'].index.min().date()} -> {wide['PX_LAST'].index.max().date()}; "
          f"intraday series loaded: {len(intra)}/{len(TICK) * 3}")

    twas_bp = wide['TIME_WAVG_BID_ASK_SPREAD_PCT'] * 100          # percent -> bp
    adv_usd = wide['TURNOVER'].rolling(60, min_periods=20).median().shift(1)
    price = wide['PX_LAST']

    pc = preclose_spreads(intra)
    liq = []
    for r in pc:
        t = r['ticker']
        tw = twas_bp[t]
        row = {k: v for k, v in r.items() if not k.startswith('_')}
        row['twas_bp_median_full'] = tw.loc['2023-11-01':].median()
        if '_pre_daily' in r and len(r['_pre_daily']) > 10:
            pdx = r['_pre_daily']
            pdx.index = pd.to_datetime(pdx.index)
            tw_ov = tw.reindex(pdx.index)
            row['ratio_preclose_to_twas'] = (pdx / tw_ov).replace([np.inf, -np.inf], np.nan).median()
            row['twas_bp_median_overlap'] = tw_ov.median()
        row['adv_usd_median_1y'] = wide['TURNOVER'][t].iloc[-252:].median()
        row['price_last'] = price[t].dropna().iloc[-1]
        row['exchange'] = ref.loc[t, 'PRIMARY_EXCHANGE_NAME'] if t in ref.index else ''
        row['aum_usd'] = pd.to_numeric(ref.loc[t, 'FUND_TOTAL_ASSETS'], errors='coerce') if t in ref.index else np.nan
        liq.append(row)
    liq = pd.DataFrame(liq).set_index('ticker')
    med_ratio = liq['ratio_preclose_to_twas'].median()
    liq['ratio_used'] = liq['ratio_preclose_to_twas'].fillna(med_ratio).clip(lower=0.5)
    pd.set_option('display.width', 250)
    print("\n=== PER-ETF SPREADS AND LIQUIDITY (spreads in bp of price, full quoted spread) ===")
    show = ['exchange', 'preclose_spread_bp', 'preclose_spread_bp_p90', 'bell_spread_bp', 'twas_bp_median_full',
            'ratio_preclose_to_twas', 'final_minute_usd_median', 'adv_usd_median_1y', 'price_last']
    print(liq[show].sort_values('preclose_spread_bp').round(1).to_string())
    print(f"Median pre-close/TWAS ratio across ETFs: {med_ratio:.2f}")

    books, sd = books_e5()
    days = books['1-name raw']['w'].index
    # per-ETF per-day half spread (bp) at the close, using daily TWAS x ETF ratio
    half_sp = (0.5 * twas_bp.reindex(days).ffill() * liq['ratio_used']).reindex(columns=TICK)
    sigma = sd.reindex(days)                                          # daily std (decimal)
    adv = adv_usd.reindex(days).ffill()
    px = price.reindex(days).ffill()

    # how wide are spreads on the days a name is picked vs typical?
    pick1 = books['1-name raw']['w'] > 0
    hp = half_sp.where(pick1).stack().dropna()
    rel = hp / half_sp.median().reindex(hp.index.get_level_values(1)).values
    print(f"\nOn days a name is the 1-name pick, its half-spread is {rel.median():.2f}x its own median (median across picks)")

    # Spread-only cost model (v1.1).  v1.0's square-root impact term on ETF ADV was
    # dropped: ETF liquidity is not bounded by printed volume (creation/redemption,
    # market makers), and that term priced a 0.7%-of-ADV order at ~12bp, contradicting
    # the measured 15:45-15:59 slippage (intraday_execution.py).  Size is handled
    # separately as participation in the actual closing-window volume.
    bell_hs = pd.DataFrame(np.tile((0.5 * liq['bell_spread_bp'].reindex(TICK)).values, (len(days), 1)),
                           index=days, columns=TICK)
    bell_hs = bell_hs.fillna(half_sp)                                  # QQQ/SPY/IWM: no quote bars
    comm_bp = (COMM / px) * 1e4

    def net_series(b, k_spread=1.0, which='preclose'):
        w = b['w']
        dw = w.diff().abs().fillna(w.abs())                            # traded weight per name
        hs = half_sp if which == 'preclose' else bell_hs
        cost_bp = (k_spread * hs).fillna(half_sp.median().median()) + comm_bp.fillna(1.0)
        cost = (dw * cost_bp / 1e4).sum(axis=1)
        return b['gross'] - cost, cost, dw.sum(axis=1)

    def st(x):
        return x.mean() * 252, x.mean() / x.std() * np.sqrt(252)

    SCEN = [('backtest: fill at the close, no cost', 0.0, 'preclose', False),
            ('commission only', 0.0, 'preclose', True),
            ('half the pre-close spread + commission (base)', 1.0, 'preclose', True),
            ('full pre-close spread + commission', 2.0, 'preclose', True),
            ('half the 15:59 spread + commission', 1.0, 'bell', True)]
    rows = []
    for name, b in books.items():
        ga, gs = st(b['gross'])
        for lab, k, which, comm in SCEN:
            if comm or k > 0:
                n, c, to = net_series(b, k, which)
                if not comm:
                    pass
            else:
                n, c, to = b['gross'], b['gross'] * 0, net_series(b)[2]
            if lab == 'commission only':
                w = b['w']
                dw = w.diff().abs().fillna(w.abs())
                c = (dw * comm_bp.fillna(1.0) / 1e4).sum(axis=1)
                n = b['gross'] - c
            na, ns = st(n)
            rows.append({'book': name, 'scenario': lab, 'gross_ann_active': ga, 'gross_sharpe': gs,
                         'cost_ann': c.mean() * 252, 'net_ann_active': na, 'net_sharpe': ns,
                         'turnover_per_day': to.mean(),
                         'avg_cost_bp_per_dollar_traded': c.sum() / to.sum() * 1e4,
                         'breakeven_cost_bp_per_dollar': b['gross'].sum() / to.sum() * 1e4})
    res = pd.DataFrame(rows)
    base = res[res.scenario == 'half the pre-close spread + commission (base)']
    print("\n=== GROSS vs NET, spread-only cost model, E5 15:30 signal MOC, 2023-11 -> 2026-10 ===")
    print(res[['book', 'scenario', 'net_ann_active', 'net_sharpe', 'avg_cost_bp_per_dollar_traded',
               'breakeven_cost_bp_per_dollar']].round(3).to_string(index=False))

    # capacity: order size vs the actual closing-window $ volume (15:45-15:58 + final minute)
    win_usd = {}
    for t in TICK:
        p = BB / 'intraday' / f'{t}_TRADE.parquet'
        if p.exists():
            tr = pd.read_parquet(p)
            hm = tr['time'].dt.strftime('%H:%M')
            v = tr[(hm >= '19:45') & (hm <= '19:59')].groupby(tr['time'].dt.normalize())['value'].sum()
            win_usd[t] = v.median()
    win_usd = pd.Series(win_usd)
    liq['window_1545_1600_usd_median'] = win_usd
    cap = []
    for aum in AUMS:
        for name in ['7-name long-only', '7-name long-short', '1-name raw', '1-name vol-scaled']:
            w = books[name]['w']
            dw = w.diff().abs().fillna(w.abs())
            orders = (dw * aum).where(dw > 0).stack().dropna()
            tick = orders.index.get_level_values(1)
            part = orders.values / win_usd.reindex(tick).values
            ad = adv.stack().reindex(orders.index).values
            cap.append({'book': name, 'aum': aum, 'median_order_usd': np.median(orders.values),
                        'median_pct_of_last15min_volume': np.nanmedian(part) * 100,
                        'p90_pct_of_last15min_volume': np.nanpercentile(part, 90) * 100,
                        'share_of_orders_over_10pct_of_window': np.nanmean(part > 0.10),
                        'median_pct_of_ADV': np.nanmedian(orders.values / ad) * 100})
    cap = pd.DataFrame(cap)
    print("\n=== CAPACITY: order size vs actual 15:45-16:00 $ volume (incl. closing cross) ===")
    print(cap.round(2).to_string(index=False))

    # charts
    plt.rcParams.update({'font.size': 9, 'axes.spines.top': False, 'axes.spines.right': False})
    pdfp = run / 'cost_report.pdf'
    with PdfPages(pdfp) as pdf:
        fig, ax = plt.subplots(figsize=(12, 5))
        s = liq.sort_values('preclose_spread_bp')
        x = np.arange(len(s))
        ax.bar(x - 0.2, s['preclose_spread_bp'], 0.4, color='#1f5fa8', label='pre-close quoted spread (15:50-15:58, median)')
        ax.bar(x + 0.2, s['bell_spread_bp'], 0.4, color='#c0504d', label='at 15:59 (median)')
        ax.plot(x, s['twas_bp_median_full'], 'k.', label='full-day time-weighted spread (2023-26 median)')
        ax.set_xticks(x, s.index, rotation=90, fontsize=8)
        ax.set_ylabel('full quoted spread, bp of price')
        ax.set_title('Quoted spreads near the close, by ETF (one-way cost is about half of this)', loc='left')
        ax.legend(frameon=False, fontsize=8)
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        fig, axes = plt.subplots(1, 4, figsize=(15, 4.6), sharey=True)
        labs = ['no cost', 'commission', 'half spread', 'full spread', 'half 15:59 spr']
        for ax, name in zip(axes, books):
            sub = res[res.book == name]
            ax.bar(labs, sub.net_ann_active.values, color=['#9a9a9a', '#6baed6', '#1f5fa8', '#c0504d', '#e69f00'])
            ax.axhline(0, color='black', lw=0.5)
            ax.set_title(name, loc='left')
            ax.tick_params(axis='x', rotation=45)
        axes[0].set_ylabel('annual active return vs equal-weight')
        fig.suptitle('Net of measured spreads + $0.0035/share commission (E5, 2023-11 to 2026-10; small size)', x=0.01, ha='left')
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(10, 4.5))
        for name, col in zip(books, ['#9a9a9a', '#c0504d', '#6baed6', '#1f5fa8']):
            b = books[name]
            n, _, _ = net_series(b, 1.0, 'preclose')
            ax.plot(n.index, n.cumsum(), color=col, label=f'{name}, net of half spread + commission')
            ax.plot(b['gross'].index, b['gross'].cumsum(), color=col, lw=0.7, ls=':')
        ax.axhline(0, color='black', lw=0.5)
        ax.set_title('Cumulative active return: gross (dotted) vs net (solid)', loc='left')
        ax.legend(frameon=False, fontsize=8)
        fig.tight_layout()
        pdf.savefig(fig)
        plt.close(fig)
    subprocess.run(['pdftoppm', '-png', '-r', '100', str(pdfp), str(run / 'cost_report')], check=True)

    with pd.ExcelWriter(run / 'cost_results.xlsx') as w:
        liq.drop(columns=[c for c in liq.columns if c.startswith('_')], errors='ignore').to_excel(w, sheet_name='etf_liquidity')
        res.to_excel(w, sheet_name='gross_vs_net', index=False)
        cap.to_excel(w, sheet_name='capacity', index=False)
    json.dump({'run_dir': str(run), 'scenarios': res.round(4).to_dict(orient='records'),
               'capacity': cap.round(4).to_dict(orient='records'),
               'model': {'cost': 'k x half quoted spread + commission; no impact term (v1.1)', 'commission_per_share': COMM,
                         'median_preclose_to_twas_ratio': float(med_ratio)}},
              open(run / 'summary.json', 'w'), indent=2, default=str)
    print(f"\nDone. {run}")


if __name__ == '__main__':
    main()
