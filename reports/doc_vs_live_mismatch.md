# Doc-vs-Live Mismatch Report

**Generated:** 2026-06-10 by the Variable Registry Phase 0 pass
(`PRD_Semantic_Layer_Variable_Registry.md` §6 Phase 0).
**Method:** every number below was queried directly from the live
`Data/asado.duckdb` (3.5 GB, last written 2026-06-10 10:08) and compared
against the claims in the four agent-facing docs. **The live DB wins.**

---

## 1. Headline row/variable counts (the big ones)

| Object | Doc claim | Where claimed | Live (2026-06-10) | Verdict |
|---|---|---|---|---|
| `unified_panel` | 17.4M rows / 2,022 vars | `CLAUDE.md` (header, §schema, footer) | **2,567,172 rows / 428 vars** | **Stale by ~7x.** The 17.4M figure predates the commodity-split (commodity rows were removed from the union) and the GDELT deep-themes retirement. |
| `unified_panel` | ~12.1M rows / ~426 base vars | `README.md` §Layer-1 | 2,567,172 rows / 428 vars | Vars right, rows stale (~5x). Same root causes. |
| `feature_panel` | 31.6M rows / 3,048 vars | `CLAUDE.md` (header + footer) | **3,526,055 rows / 724 vars** | **Stale by ~9x / ~4x.** |
| `feature_panel` | ~3.3M rows / ~720 vars | `README.md` §Layer-1 | 3,526,055 / 724 | **Correct.** README was updated post-split; CLAUDE.md was not. |
| `normalized_panel` | 14,192,623 rows | `DATA_DICTIONARY.md` §tables | **958,883 rows / 296 vars** | **Stale by ~15x** (pre-commodity-split figure). |
| `variable_meta` | 654 rows | `CLAUDE.md`, `DATA_DICTIONARY.md`, `ASADO_DATABASE_MAP.md` | **286 rows** | All three stale. The 371 `wb_commodity` rows left `variable_meta` when the broadcast panel was dropped (286 = 111 t2 + 75 gdelt + 48 levels + 38 raw + 14 predmkt). |
| `t2_factors_daily` | 32.3M rows | `CLAUDE.md` | 35,614,660 | Benign growth drift. |
| `t2_levels_daily` | 13.7M rows | `CLAUDE.md` | 15,344,540 | Benign growth drift. |
| `gdelt_raw_daily` | 955K rows | `CLAUDE.md` | 967,364 | Benign growth drift. |
| `factor_returns_daily` | 178 factors | `CLAUDE.md`, `AGENTS.md` | 180 factors | Benign drift. |
| `factor_returns` (monthly) | — | (undocumented) | 390 factors / 106,036 rows | Add to docs. |

## 2. Objects that exist/don't exist — disagreements between the docs themselves

| Claim | Where | Live truth |
|---|---|---|
| "`feature_panel` and `normalized_panel` **DO NOT EXIST** in the live DB" | `ASADO_DATABASE_MAP.md` §⚠️ (written 2026-06-09 during the audit) | **They DO exist now** — both were restored after the commodity split (`feature_panel` VIEW, `normalized_panel` TABLE). The Alpha-Hunting-Loop PRD §3 already flags the DATABASE_MAP claim as stale; this report confirms it. |
| `wb_commodity_factor_panel` (9.6M rows, country-tiled) | `CLAUDE.md` §schema | **Dropped.** Replaced by `commodity_panel` (VIEW, 436,196 rows, 609 variable strings, date-keyed, **no country axis**). |
| `gdelt_panel` carries "1,323 theme_*/gcam_* variables" | `PRD_Semantic_Layer_Variable_Registry.md` §1, §6 Tier C | **Gone.** Live `gdelt_panel` = 93 variables; zero `theme_*`/`gcam_*` strings anywhere in `feature_panel`. The GDELT deep-themes tables were retired (see `monthly_update.py` comment "GDELT Deep DB stages — RETIRED"). **Tier C of the registry PRD is therefore moot** — the registry universe is 1,434 variables, not ~3,000. |
| `DATA_DICTIONARY.md` is the data dictionary | `CLAUDE.md` key-files table | Superseded. The dictionary is now **generated** from the registry → `docs/VARIABLE_DICTIONARY.md` (PRD §5c). `DATA_DICTIONARY.md` should be marked historical or deleted (your call — not touched). |

## 3. Date-range anomalies (found during the facts scan)

| Finding | Detail | Suggested handling |
|---|---|---|
| `feature_panel` max date = **2100-12-01** | All 12 `demographics_dip` variables (`DIP_*`) extend to 2100 — UN demographic projections. 34,047 rows sit beyond 2027. `DATA_DICTIONARY.md` claims the panel ends 2031-12-01. | Intentional (projections), but any "latest value" query that doesn't clamp `date <= CURRENT_DATE` will silently read the year 2100. The registry tags these rows `is_forecast` semantics in Phase 2; the access-guide guardrail ("constrain to dates on or before CURRENT_DATE") already covers it. Docs should state the real max date. |
| `imf_weo` rows extend ~2 years forward | Forecast vintages (known, flagged `is_forecast`) | Already handled by harness embargo defaults. |

## 4. Registry universe decision (PRD §8 Q1, decided this pass)

**1,434 distinct variables / 1,624 (variable, surface) pairs** across 8 surfaces:

| Surface | Vars | Notes |
|---|---|---|
| `feature_panel` | 724 | monthly raw + normalized union |
| `commodity_panel` | 609 | global, no country axis, `is_broadcast=true` |
| `t2_factors_daily` | 111 | 80 share strings with monthly t2 (same concept, daily grain) |
| `gdelt_factors_daily` | 75 | |
| `t2_levels_daily` | 48 | |
| `gdelt_raw_daily` | 35 | wide table → numeric columns treated as variables (249-country scope, flagged) |
| `predmkt_signals_daily` | 14 | |
| `graph_features_daily` | 7 | lives in the loop DB (`Data/loop/asado_loop.duckdb`) |

**Excluded** (documented, deliberate): `bilateral_portfolio_matrix` (different grain),
`event_log`, predmkt market-metadata tables, `wb_commodity_prices/indices/features`
(content already covered by the `commodity_panel` variable strings),
`factor_returns`/`factor_returns_daily` factor names (the factor IS the registry
variable; returns surfaces are tagged via `returns_role`, never input rows).

## 5. Recommended doc actions (none taken — your call)

1. **`CLAUDE.md`** — refresh the header/footer/table numbers (worst offender; agents read it every session).
2. **`ASADO_DATABASE_MAP.md`** — strike the "feature_panel does not exist" warning block; it now causes the opposite error.
3. **`DATA_DICTIONARY.md`** — mark as superseded by the generated `docs/VARIABLE_DICTIONARY.md`, or retire it.
4. **`PRD_Semantic_Layer_Variable_Registry.md`** — Tier C (1,323 GDELT crosswalk) can be struck; universe is 1,434.
5. README is broadly accurate post-split — only minor growth drift.
