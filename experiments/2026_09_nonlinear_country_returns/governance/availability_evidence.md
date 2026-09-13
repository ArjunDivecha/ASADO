# P01 Availability Evidence — source-by-source audit notes

Snapshot: `Data/work/experiments/nonlinear_country_returns/snapshot_2026_09_13/`
(main checkout; content hashes in `audit/snapshot_manifest.json`). All evidence below
is computed from that frozen snapshot — no live DB connection was held.

## t2_levels_daily (main warehouse, `Tot Return Index` / `PX_LAST` / `Currency`)

- `Tot Return Index`: 34/34 T2 markets, 2000-01-01 → 2026-09-11, 9,751 obs each.
  Uniform calendar-day grid; per-market trading sessions are the non-zero-return
  days (see `daily_country_returns()` convention — backward-labeled, placeholder
  rows dropped). This is the source for P01–P04 own-market features and the
  label TRI marks.
- `PX_LAST`, `Currency`: same coverage. `Currency` = the FX series used in T2's
  USD conversion — needed at P02 to verify the USD-TRI construction claim.
- No vintages: index levels are not revised (exchange marks). Treated as
  VERIFIED_HISTORICAL_AVAILABILITY subject to the P02 close→UTC mapping audit.

## market_implied_daily (loop DB; source = bloomberg)

23 variables, 2006-01 → 2026-09-11. FX option surface variables
(`FX_IMPVOL_{1W,1M,3M}_PCT`, `FX_RR25_1M_PCT`, `FX_BF25_1M_PCT`): 29 markets —
all T2 minus {Denmark, Vietnam, U.S., NASDAQ, US SmallCap}. `FX_CARRY_3M_PCT`:
30 (adds Denmark via USDDKK forward-only). US complex absent structurally
(USD is the numeraire); Denmark/Vietnam skipped structurally (pegged/managed,
no liquid surface) per the collector docstring. Globals (`RISK_*`, `CMD_*`)
are keyed `country='GLOBAL'`.

Per-market late starts within the covered set: ChinaA/ChinaH FX surface from
2011-02-23, Saudi from 2008-06-25, Taiwan carry 2010-09-27, Indonesia/Philippines
IV from 2007-06/2008-04 — recorded per-market in `audit/coverage_by_feature_market.parquet`.

**P11 tenor gap**: collector pulls `[PAIR]25R1M` only; no 3M RR exists upstream.
Orientation already matches spec (positive = local depreciation premium after
the collector's per-pair sign normalization).

## sovereign_daily (loop DB; source = bloomberg)

`SOV_2Y_YIELD_PCT` 27 mkts, `SOV_10Y_YIELD_PCT` 32 mkts, `SOV_CDS_{1Y,5Y}_BP`
19–20 mkts (CDS not required by the 24 primitives). Late starts within covered
markets: Brazil 2Y 2010-07-01; Turkey 10Y 2010-01-27; Chile 10Y 2014-06;
Saudi 10Y 2021-06-23; Taiwan 10Y 2011-02-14.

## consensus_daily / consensus_revisions (loop DB; source = bloomberg_ecfc)

`CONS_GDP_PCT`, `CONS_CPI_PCT` × `target_year` (2008–2027), 34 markets,
2007-10-04 → 2026-09-11. Per-series revision paths are stored (year-specific
ECFC tickers), so a genuinely unchanged forecast and a missing feed are
distinguishable — the P17/P18 "signed sum over 21 sessions" and P19/P20
arrival/recency definitions are computable. Late starts: Netherlands GDP
2012-05-31 / CPI 2015-03-06 (!), Germany CPI 2009-08-25, Saudi GDP 2010-09-01,
Vietnam 2011-12-13. `consensus_revisions` (44,221 rows; `rev_1m`/`rev_3m`
precomputed) is a secondary check, not the binding source — the PRD's
21-local-session windows are derived from the daily path.

## graph_edge_vintages / graph_features_pit_daily (loop DB)

- `graph_edge_vintages`: (edge_type, vintage_end, applies_from, focal, neighbor,
  weight); 93,800 rows. `trade` 27 vintages 2000-04→2025-12 (30 focals);
  `bank` 109 vintages 1999-07→2026-03 (21 focals); `holder` 25 vintages
  1998-09→2024-12 (31 focals). ~30 distinct neighbors per focal — the ≥3-source
  / ≥80%-mass support rules are satisfiable where focals exist.
- Direction: feature attaches to the **focal** (focal's weighted neighbor
  return); confirmed in `build_graph_features_pit.py` (weights pivot
  focal × neighbor; `GRAPHP_*_NBR_RET_GAP_*` = weighted neighbor return minus own).
- The non-PIT `graph_features_daily` still exists in the loop DB but is
  **denied** for this study (governance contract v1.4 removed it from the
  nightly for look-ahead L-05). Bindings reference only `_pit_` variants and
  the edge vintages themselves.

## weo_vintages (loop DB)

True vintage table (vintage, vintage_date, country, target_year, variable,
value); 36 vintages 2008-04→2026-04. Not required by the current 24 primitives;
recorded here as the repo's only fully-vintaged macro source should an
amendment need vintage-correct macro levels.

## Known convention notes carried forward to P02

- Bloomberg 10Y generics (`GT{CCY}10Y Govt`) carry PRICE in PX_LAST — the
  stored `SOV_10Y_YIELD_PCT` is already YLD_YTM_MID-derived per the 2026-06-11
  re-audit; confirmed by the variable name, no action needed.
- `daily_calendar` (main DB) is a convenience calendar; the study builds
  independent per-market calendars from TRI marks and uses this only as a
  cross-check.
