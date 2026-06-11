# ASADO Database Audit — 2026-06-09 (post fresh rebuild)

Authoritative inventory queried live from `Data/asado.duckdb` + Neo4j. **37 DuckDB objects**
(33 tables + 4 views) and a 7-label knowledge graph.

> **UPDATE (commodity dual-surface split, applied after this audit):** Commodities are no longer
> broadcast/tiled into the country panels. `wb_commodity_factor_panel` was dropped; `feature_panel`
> went **1,833 → ~720 variables**, `unified_panel` 797 → ~426, `normalized_panel` 1,036 → ~294. The
> commodity data now lives in the GLOBAL **`commodity_panel`** view (87 series × 7 features,
> date-keyed, no country). Figures below that mention the commodity broadcast / the 1,833 count are
> pre-split. Also: the `eia` source (flagged dead at 2019) was fixed and now runs to 2025.

## Layer 1 — Raw monthly panels (the collected inputs)

Tidy schema `(date, country, value, variable, source)`. These feed `unified_panel`. Variable
counts are **base concepts** (pre-normalization). "Latest" exposes freshness.

| Source | vars | ctry | range | latest | notes |
|---|---|---|---|---|---|
| wb_commodity | 371 | 34 | 1960→ | **2026-05** | World Bank Pink Sheet broadcast |
| t2 | 111 | 34 | 2000→ | **2026-06** | T2 factors (Bloomberg-direct) |
| t2_raw | 53 | 34 | 2000→ | **2026-06** | T2 raw levels |
| gdelt | 93 | 34 | 2015→ | **2026-07** | news tone/attention/risk |
| bloomberg | 28 | 34 | 1975→ | **2026-06** | bonds/CDS/OIS/PMI/M2/flows |
| gpr | 4 | 34 | 1985→ | 2026-05 | geopolitical risk |
| fred | 6 | 34 | 2000→ | 2026-05 | |
| imf_itg | 8 | 34 | 2000→ | 2026-03 | trade |
| macrostructure_derived | 5 | 34 | 1997→ | 2026-06 | |
| worldbank | 26 | 33 | 2000→ | 2025-12 | WDI/WGI (annual) |
| demographics_dip | 4 | 34 | 1950→ | **2100** | projections |
| imf_cpi / imf_mfs_ir / imf_mfs_cbs / imf_er / imf_fsi / imf_weo | 2–6 | 25–34 | varies | 2024–2031 | imf_weo→2031 (forecast) |
| ecb_fx | 24 | 31 | 2000→ | 2026-05 | |
| bis_reer / bis_policy_rate / bis_credit / bis_property / bis_debt_service | 1 ea | 26–33 | 2000→ | 2025-09…2026-06 | BIS (quarterly lag) |
| oecd / oecd_bci / oecd_cci / oecd_household / oecd_institutional | 1–2 | 20–22 | 2000→ | 2025-12…2026-05 | |
| epu | 1 | 21 | 1985→ | 2025-11 | |
| undp_hdi | 4 | 33 | 1990→ | **2023-12** | annual, lagged |
| ndgain | 3 | 32 | 1995→ | **2023-12** | annual |
| faostat | 5 | 33 | 2010→ | **2024-12** | annual |
| imf_bop | 4 | 34 | 2005→ | **2024-12** | |
| portfolio_ownership | 1 | 34 | 1997→ | **2024-12** | |
| ilostat | 2 | 34 | 2000→ | 2025-12 | |
| **eia** | 1 | 34 | 2000→ | **2019-12** | ⚠ DEAD (6.5y stale) |
| ofac | 2 | 34 | 2026-06 | 2026-06 | sanctions snapshot |

**38 distinct sources** feed `unified_panel`.

## Layer 2 — Union surfaces (query-facing)
| View/table | rows | base vars | w/ norm variants | countries |
|---|---|---|---|---|
| `unified_panel` (raw union) | 12.1M | 797 | — | 43 |
| `normalized_panel` (_CS/_TS) | 14.2M | — | 1,036 | 43 |
| `feature_panel` (union, query-facing) | 26.3M | — | **1,833** | 43 |

`wb_commodity` dominates: 371 base → **1,113** variants (61% of `feature_panel`).

## Layer 3 — Daily extension (now internalized & fresh through today)
| Table | rows | vars | latest |
|---|---|---|---|
| `t2_factors_daily` | 35.6M | 111 | **2026-06-09** |
| `t2_levels_daily` | 15.3M | 48 | 2026-06-09 |
| `gdelt_factors_daily` | 10.2M | 75 | 2026-06-08 |
| `gdelt_raw_daily` | 967K | 45-col | 2026-06-09 |
| `daily_calendar` | 328K | — | 2026-06-09 |

## Layer 4 — Returns surfaces (outcome "source of truth")
| Table | sources | factors | latest |
|---|---|---|---|
| `factor_returns` (monthly) | t2_optimizer (82), gdelt_optimizer (92), econ_optimizer (216) | 390 | 2026-05 |
| `factor_returns_daily` | t2_optimizer_daily (106), gdelt_optimizer_daily (74) | 180 | 2026-06-09 / 06-08 |
| `factor_top20_membership` | 3 optimizers | 393 | 2026-07 |
| `country_factor_attribution` (view) | 3 | 384 | 2026-05 |

## Layer 5 — Knowledge graph (Neo4j)
**Nodes (1,174):** Factor 1,045 · DataSource 39 · Country 34 · CentralBank 31 · CrisisEvent 15 ·
SanctionsProgram 6 · Commodity 4.
**Relationships (30,366):** HAS_FACTOR_EXPOSURE 25,459 · HOLDS_PORTFOLIO 1,960 ·
DATA_AVAILABLE_FROM 1,048 · TRADES_WITH 928 · HAS_BANKING_EXPOSURE_TO 584 ·
HAS_CRISIS_HISTORY 297 · HAS_CENTRAL_BANK 31 · SUBJECT_TO 31 · EXPORT_EXPOSED_TO 28.

## Layer 6 — Auxiliary / reference
- Commodity raw: `wb_commodity_prices` (50K), `wb_commodity_features` (436K), `wb_commodity_indices` (13K), `wb_commodity_meta` (87).
- `bilateral_portfolio_matrix` 56.9K (1997→2026-03).
- Prediction markets: `predmkt_daily` (20), `predmkt_signals_daily` (36), `predmkt_country_spillover` (49), `predmkt_market_meta` (10), `predmkt_outcome_meta` (20), `predmkt_resolutions` (0). Sparse/recent.
- `event_log` 146 curated events.
- `variable_meta` 657 rows — metadata: source_table, native_frequency, monthly_equivalent, is_normalized, category, is_optimizer_selected, freshness_expectation. (No deep semantics — units/sign/PIT/mechanism — per the Semantic-Layer PRD.) *Update 2026-06-10: `is_optimizer_selected` has since been removed — stale Fuzzy Daily artifact.*
- `country_reference` 31.

## Coverage notes & anomalies
1. **43 countries, not 34**, in the union panels. The 34 T2 universe is fully present; **9 extras**
   leak in from multi-country sources (ECB FX / OECD / IMF): Austria, Belgium, Finland, Greece,
   Ireland, New Zealand, Norway, Portugal, Russian Federation.
2. **Far-future (forecast) data** — intentional: `demographics_dip` → 2100, `imf_weo` → 2031. These
   set the `2100-12-01` max on the union panels.
3. **Stale / dead sources** (latest << today, beyond normal lag): **`eia` ends 2019-12 (dead)**;
   `undp_hdi`/`ndgain` 2023; `faostat`/`imf_bop`/`portfolio_ownership` 2024. Annual sources (HDI,
   ND-GAIN, FAOSTAT, WDI) are *expected* to lag; `eia` is a genuine broken collector.
4. **Commodity dominance:** 61% of `feature_panel` is the WB commodity broadcast.
5. `predmkt_resolutions` is empty (0 rows).

## One-line summary
34-country macro universe: **38 collected sources** → 797 raw / 1,833 normalized variables in the
warehouse, a **daily extension** (T2 + GDELT, fresh through today), **390 monthly + 180 daily factor
return series**, and a **1,174-node / 30K-edge** knowledge graph. Everything is process-built (no
orphan crud); the only data-quality flags are `eia` (dead) and a few annual sources at their normal lag.
