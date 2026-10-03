"""Freeze existing ASADO files, reconstruct causal inputs, and audit coverage.
Inputs: --root/Data/work/{t2,loop} plus existing research return extracts.
Outputs: --scratch/{inputs,prepared}; no DB connections, network or production writes.
Run with the existing project Python; installs no packages. Version 1, 2026-09-06.
"""
from pathlib import Path
import argparse, ast, hashlib, json, shutil
import numpy as np
import pandas as pd


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def freeze(root, dest):
    dest.mkdir(parents=True, exist_ok=True)
    sources = {
        'monthly.xlsx': 'Data/work/t2/T2 Bloomberg Master.xlsx',
        'consensus.parquet': 'Data/work/loop/consensus_daily.parquet',
        'sovereign.parquet': 'Data/work/loop/sovereign_daily.parquet',
        'market.parquet': 'Data/work/loop/market_implied_daily.parquet',
        'bbg_manifest.json': 'scripts/config/t2_bbg_manifest.json',
        'country_mapping.json': 'config/country_mapping.json',
        'build_t2_master.py': 'scripts/build_t2_master.py',
        'canonical_returns.csv': 'docs/macrostate_2026_09_05/returns.csv',
    }
    manifest = {}
    for name, rel in sources.items():
        src, dst = root / rel, dest / name
        before = sha(src)
        if dst.exists() and sha(dst) != before:
            raise ValueError(f'Frozen input differs: {dst}; use a new scratch directory')
        if not dst.exists():
            shutil.copy2(src, dst)
        if sha(src) != before or sha(dst) != before:
            raise ValueError(f'Source changed while copying {src}')
        manifest[name] = {'source': str(src), 'sha256': before, 'bytes': dst.stat().st_size}
    (dest / 'manifest.json').write_text(json.dumps(manifest, indent=2))
    return manifest


def workbook_sheet(path, manifest, name, countries):
    specs = [s for s in manifest['sheets'] if s['sheet'].strip() == name]
    if len(specs) != 1:
        raise ValueError(f'Sheet definition {name}')
    spec = specs[0]
    raw = pd.read_excel(path, sheet_name=spec['sheet'], header=None)
    # Two metadata rows: ticker, then field. Verify against frozen collector manifest.
    columns = spec['columns']
    if len(columns) != len(countries):
        raise ValueError('Country count mismatch')
    for i, col in enumerate(columns, 1):
        if str(raw.iloc[0, i]).strip() != col['ticker'].strip():
            raise ValueError(f'Ticker order mismatch {name} {i}')
        if str(raw.iloc[1, i]).strip().lower() != col['field'].strip().lower():
            raise ValueError(f'Field mismatch {name} {i}')
    body = raw.iloc[2:].copy()
    dates = pd.to_datetime(body.iloc[:, 0], errors='raise').dt.to_period('M').dt.to_timestamp('M')
    out = body.iloc[:, 1:].apply(pd.to_numeric, errors='coerce')
    out.index, out.columns = dates, countries
    if out.index.duplicated().any():
        raise ValueError('Duplicate month in workbook')
    out = out.sort_index().reindex(pd.date_range(out.index.min(), out.index.max(), freq='ME'))
    return out.where(np.isfinite(out) & (out > 0))


def daily_monthly(raw, dates, countries, variable, target_year=None):
    d = raw[raw.variable.eq(variable)].copy()
    if target_year is not None:
        d = d[d.target_year.eq(target_year)]
    d['date'] = pd.to_datetime(d.date)
    if d.duplicated(['date', 'country']).any():
        raise ValueError(f'Duplicate daily keys: {variable}')
    values = pd.DataFrame(np.nan, index=dates, columns=countries)
    age = values.copy()
    for country, g in d.groupby('country'):
        if country not in countries:
            continue
        g = g.sort_values('date').dropna(subset=['value'])
        g = g[np.isfinite(g.value)]
        joined = pd.merge_asof(pd.DataFrame({'cutoff': dates}), g[['date', 'value']],
                               left_on='cutoff', right_on='date', direction='backward')
        ages = (joined.cutoff - joined.date).dt.days.to_numpy(dtype=float)
        values[country] = np.where(ages <= 10, joined.value, np.nan)
        age[country] = ages
    return values, age


def consensus_features(raw, dates, countries):
    result = {}
    for variable, prefix in [('CONS_GDP_PCT', 'gdp'), ('CONS_CPI_PCT', 'cpi')]:
        by_year = {int(y): daily_monthly(raw, dates, countries, variable, y)[0]
                   for y in raw.target_year.unique()}
        level = pd.DataFrame(np.nan, index=dates, columns=countries)
        revision = level.copy()
        for j, date in enumerate(dates):
            a, b = by_year.get(date.year), by_year.get(date.year + 1)
            if a is None or b is None:
                continue
            w = (12 - date.month) / 12
            # Both target-year legs required even when a calendar weight is zero.
            good = a.iloc[j].notna() & b.iloc[j].notna()
            level.loc[date] = (w * a.iloc[j] + (1-w) * b.iloc[j]).where(good)
            if j >= 3:
                prior = a.iloc[j-3].notna() & b.iloc[j-3].notna()
                revision.loc[date] = (w * (a.iloc[j]-a.iloc[j-3]) +
                                      (1-w) * (b.iloc[j]-b.iloc[j-3])).where(good & prior)
        result[prefix + '_expectation'] = level
        result[prefix + '_revision_3m'] = revision
    return result


def prior_z(frame):
    past = frame.shift(1).rolling(60, min_periods=36)
    mean, std = past.mean(), past.std()
    return ((frame - mean) / std.where(std > 1e-12)).clip(-3, 3)


def forward_returns(returns, horizon):
    # Explicit full calendar window; no dropping missing interior observations.
    stack = np.stack([returns.shift(-k).to_numpy() for k in range(horizon)])
    valid = np.isfinite(stack).all(axis=0)
    out = np.prod(1 + stack, axis=0) - 1
    return pd.DataFrame(np.where(valid, out, np.nan), index=returns.index, columns=returns.columns)


def mature_training_rows(origins, fit_origin, horizon=12):
    """Origins whose complete forward horizon is available by the new decision date."""
    origins = pd.DatetimeIndex(origins)
    if horizon <= 0 or any(d.day != 1 for d in origins):
        raise ValueError('Positive horizon and month-start origins required')
    available = origins + pd.offsets.MonthBegin(horizon)
    return available <= pd.Timestamp(fit_origin)


def prepare(inputs, output):
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((inputs/'bbg_manifest.json').read_text())
    # Freeze the canonical builder positional mapping and verify tickers/fields separately.
    spec = next(s for s in manifest['sheets'] if s['sheet'].strip() == 'Tot Return Index')
    tree = ast.parse((inputs/'build_t2_master.py').read_text())
    countries = next(ast.literal_eval(n.value)[1:] for n in tree.body
                     if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'COUNTRY_NAMES' for t in n.targets))
    if len(countries) != 34 or len(set(countries)) != 34:
        raise ValueError('Expected canonical 34 distinct market tokens')
    tri = workbook_sheet(inputs/'monthly.xlsx', manifest, 'Tot Return Index', countries)
    pb = workbook_sheet(inputs/'monthly.xlsx', manifest, 'Best PBK', countries).reindex(tri.index)
    returns = tri.div(tri.shift(1)).sub(1)
    # Observation at prior month-end is the next calendar month's input.
    cutoffs = tri.index
    f = consensus_features(pd.read_parquet(inputs/'consensus.parquet'), cutoffs, countries)
    sov = pd.read_parquet(inputs/'sovereign.parquet')
    market = pd.read_parquet(inputs/'market.parquet')
    ages = {}
    for key, raw, variable in [('yield_2y', sov, 'SOV_2Y_YIELD_PCT'),
                               ('yield_10y', sov, 'SOV_10Y_YIELD_PCT'),
                               ('cds_5y', sov, 'SOV_CDS_5Y_BP'),
                               ('fx_vol_1m', market, 'FX_IMPVOL_1M_PCT')]:
        f[key], ages[key] = daily_monthly(raw, cutoffs, countries, variable)
    f['curve_2s10s'] = f.pop('yield_10y') - f['yield_2y']
    for key in ['yield_2y', 'cds_5y', 'fx_vol_1m']:
        f[key.replace('_1m','') + '_change_3m'] = f[key] - f[key].shift(3)
    f['cheap_pb'] = -np.log(pb)
    f['momentum_12_1'] = tri.shift(1).div(tri.shift(12)).sub(1)
    f['return_vol_12m'] = returns.rolling(12, min_periods=12).std() * np.sqrt(12)
    origins = cutoffs + pd.offsets.MonthBegin(1)
    market_eligible = tri.notna() & returns.notna().rolling(12, min_periods=12).sum().eq(12)
    eligible = market_eligible & f['cheap_pb'].notna() & f['momentum_12_1'].notna()
    z = {name: prior_z(v) for name, v in f.items()}
    records = []
    for j, date in enumerate(origins):
        for country in countries:
            rec = {'date': date, 'cutoff': cutoffs[j], 'country': country,
                   'macro_identity': 'US' if country in ['U.S.', 'NASDAQ', 'US SmallCap'] else
                                     'China' if country in ['ChinaA', 'ChinaH'] else country,
                   'market_eligible': bool(market_eligible.iloc[j][country]),
                   'scored_eligible': bool(eligible.iloc[j][country])}
            for name in f:
                rec[name] = f[name].iloc[j][country]
                rec[name+'_z'] = z[name].iloc[j][country]
            for name in ages:
                rec[name+'_age_days'] = ages[name].iloc[j][country]
            records.append(rec)
    panel = pd.DataFrame(records)
    blocks = {'growth': ['gdp_expectation_z', 'gdp_revision_3m_z'],
              'inflation': ['cpi_expectation_z', 'cpi_revision_3m_z'],
              'policy_tightness': ['yield_2y_z', 'yield_2y_change_3m_z'],
              'financial_stress': ['cds_5y_z', 'fx_vol_1m_z']}
    for block, components in blocks.items():
        count = panel[components].notna().sum(axis=1)
        panel[block+'_component_count'] = count
        panel[block+'_state'] = panel[components].mean(axis=1).where(count.eq(2))
    # Preserve singleton stress channels as primitives, never call one a two-input composite.
    panel.to_parquet(output/'features.parquet', index=False)
    realized = returns.copy()
    realized.index = realized.index.to_period('M').to_timestamp()
    realized.to_parquet(output/'returns.parquet')
    targets = pd.concat({f'return_{h}m': forward_returns(realized, h) for h in [3,6,12]}, axis=1)
    targets.to_parquet(output/'targets.parquet')
    pd.DataFrame([{'origin': d, 'horizon_months': h,
                   'label_available_at': d + pd.offsets.MonthBegin(h)}
                  for d in realized.index for h in [3, 6, 12]]).to_csv(output/'label_clock.csv', index=False)
    coverage = []
    for date, g in panel.groupby('date'):
        row = {'date': date, 'market_eligible': int(g.market_eligible.sum()),
               'value_momentum_eligible': int(g.scored_eligible.sum())}
        macro = g.scored_eligible & g.gdp_revision_3m_z.notna() & g.cpi_revision_3m_z.notna()
        row['growth_inflation_controls'] = int(macro.sum())
        row['all_four_blocks_strict'] = int((macro & g.yield_2y_change_3m_z.notna() &
                                          (g.cds_5y_z.notna() | g.fx_vol_1m_z.notna())).sum())
        row['macro_identities'] = g.loc[macro, 'macro_identity'].nunique()
        row['all_four_composites'] = int((g.scored_eligible & g[[b+'_state' for b in blocks]].notna().all(axis=1)).sum())
        for name in f:
            row[name] = int(g[name].notna().sum())
        coverage.append(row)
    pd.DataFrame(coverage).to_csv(output/'coverage.csv', index=False)
    # Reconcile against previously frozen canonical returns: report differences, no alteration.
    canonical = pd.read_csv(inputs/'canonical_returns.csv', parse_dates=['date'])
    raw = realized.rename_axis('date').stack().rename('raw').reset_index()
    raw.columns = ['date','country','raw']
    joined = canonical.merge(raw, on=['date','country']).dropna()
    diff = abs(joined.return_1m-joined.raw)
    audit = {'monthly_last_observation': str(cutoffs.max().date()),
             'last_origin': str(origins.max().date()), 'features': list(f),
             'market_tokens': len(countries), 'macro_identities': panel.macro_identity.nunique(),
             'canonical_compared': len(joined), 'canonical_differences_gt_1e8': int((diff>1e-8).sum()),
             'canonical_max_difference': float(diff.max()),
             'source_status': 'CONDITIONAL_VENDOR_HISTORY; raw workbook values used without zero-fill or clipping',
             'statistical_significance_gate': False}
    (output/'audit.json').write_text(json.dumps(audit, indent=2))
    return audit

if __name__ == '__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--root',type=Path,required=True);ap.add_argument('--scratch',type=Path,required=True)
    args=ap.parse_args();freeze(args.root,args.scratch/'inputs');print(json.dumps(prepare(args.scratch/'inputs',args.scratch/'prepared'),indent=2))
