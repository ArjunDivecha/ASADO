<!--
=============================================================================
FILE: docs/AUDIT_DATA_STRUCTURES_2026_07_01.md
=============================================================================
PURPOSE:
  Complete audit of ASADO's data structures (main DuckDB warehouse, loop
  DuckDB, parquet/JSONL stores, Neo4j-adjacent surfaces) answering two
  questions: (1) do the structures correctly serve the data, and (2) are they
  positioned to serve the project's ultimate goal — finding alpha in country
  equity selection that is NOT already embedded in price.

INPUT FILES (read-only; nothing was modified):
  - /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/asado.duckdb
  - /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Data/loop/asado_loop.duckdb
  - scripts/setup_duckdb.py, scripts/build_daily_panels.py,
    scripts/build_normalized_panel.py, scripts/loop/loopdb.py,
    scripts/loop/build_country_returns.py, scripts/harness/evaluate_signal.py,
    scripts/discovery_triage/{surface_loader,jsonl_store,paths,schemas}.py,
    cos_mockups/build_cockpit_data.py, ledgers/*.jsonl

OUTPUT FILES:
  - This document.

VERSION: 1.0    LAST UPDATED: 2026-07-01    AUTHOR: Claude (Fable 5) session
=============================================================================
-->

# ASADO Data Structure Audit — 2026-07-01

All row counts below were taken live (read-only) on 2026-07-01.

## Verdict in one paragraph

The **ingestion side is in good shape**: tidy long format is consistent across
monthly collectors, isolation rules (optimizer outputs, JST, Ken French,
predmkt) are real and verified live (0 optimizer rows in `unified_panel`,
0 predmkt rows in `feature_panel`), the harness has hard forward-return
blacklists, and there is now a PIT graph path. The **consumption side is the
weak half**: country-level daily signals are fragmented across ~15 loop tables
plus main-DB daily tables with three different schemas, there is no single
point-in-time signal panel, no forward-return join surface, and every consumer
(harness, cockpit, combiner, Discovery Lab) re-joins the same data in its own
dialect. For the stated goal — systematically finding what the data knows that
price doesn't — the missing structure is a **unified, PIT-stamped signal
panel with a paired forward-return surface**. That is the single highest-value
structural addition.

---

## 1. Inventory (live counts, 2026-07-01)

### 1a. Main DB `Data/asado.duckdb` — 42 tables/views

Rebuild behavior: `setup_duckdb.py` **deletes and recreates the whole file**
every monthly run (line ~1129). Only what the pipeline reloads survives.
`build_daily_panels.py` / `build_normalized_panel.py` append afterward;
predmkt survives via a backup/restore dance.

| Surface | Rows | Notes |
|---|---:|---|
| `t2_master` | 1,078,310 | monthly normalized T2, 111 vars |
| `t2_raw` | 474,420 | raw workbook levels, 53 vars |
| `external_factors` | 137,322 | Program 1 |
| `extended_factors` | 115,224 | Program 2 |
| `imf_factors` | 132,010 | Program 3 (incl. WEO projections to 2031) |
| `gdelt_panel` | 414,188 | monthly GDELT |
| `macrostructure_factors` | 96,120 | Program 5 |
| `bloomberg_factors` | 105,307 | Program 6 |
| `normalized_panel` | 970,866 | ASADO-generated `_CS`/`_TS`, 299 vars |
| `t2_factors_daily` | 35,691,058 | daily normalized T2 — **no `source` column** |
| `t2_levels_daily` | 15,377,384 | daily raw levels |
| `gdelt_factors_daily` | 5,112,478 | daily GDELT |
| `gdelt_raw_daily` | 956,234 | **wide** 249-ISO3 bridge (only wide table) |
| `factor_returns_daily` | 1,172,456 | isolated (cycle protection) |
| `variable_meta` | 243 | covers only 5 daily source tables |
| `jst_macrohistory` / `ff_factors` | 83,725 / 539,920 | isolated corpora |
| `predmkt_*` (6) | 503–4,614 | isolated, backup/restore pattern |
| `unified_panel` (view) | 2,572,927 | 431 vars, 38 sources |
| `feature_panel` (view) | 3,543,793 | **730 vars**, **43 countries** |
| `country_reference` | 40 | not 34 — see §4.2 |

### 1b. Loop DB `Data/loop/asado_loop.duckdb` — 54 tables (persists across rebuilds)

Signal-bearing families (all tidy long unless noted): `sovereign_daily`/
`sovereign_signals` (455K/373K), `market_implied_daily`/`_signals`
(989K/983K), `etf_flows`/`etf_flow_signals` (416K/546K), `consensus_*`
(923K/44K/14K), `eco_surprise_*` (33K/28K), `sov_ratings_monthly` +
`sov_rating_changes` (13K/128), `valuation_monthly` (129K), `weo_*`
(17K/15K), `foreign_flows_daily` (58K), `cot_*` (38K/13K),
`graph_features_daily` (1.33M, **non-PIT**), `graph_features_pit_daily`
(1.84M), `similarity_features_daily` (453K), `leadlag_features_daily`
(358K), `combiner_scores_daily` (167K), `dislocation_daily` (1,075, event
rows), gap engine tables (`gap_episodes` 33, `gap_episode_marks` 136,
`price_state_daily` 34, `price_state_surface` 272 — JSON-blob columns,
`gap_holdout_daily` 533), ledger folds (`hypothesis_ledger` 58,
`thesis_ledger` 3, `live_signals` view 16), `harness_ic_series` (1.15M),
`country_returns_monthly` (10,487 — the returns source of truth),
news-bridge tables (`portfolio_holdings_daily` 1,032, `etf_prices_daily`
214K).

### 1c. Files

- Parquet-first pattern for all Bloomberg loop collectors (`Data/work/loop/`)
  with idempotent `load_*.py` DROP+CREATE — good.
- Append-only JSONL ledgers (`ledgers/*.jsonl`, git-tracked) with
  flock+fsync (`scripts/discovery_triage/jsonl_store.py:52–68`) — good.
- Discovery Triage journal under `journal/` (looks/drafts/claims), path root
  overridable via `ASADO_DATA_ROOT` (`scripts/discovery_triage/paths.py`).
- `config/variable_registry_seed.yaml` ~31,700 lines → 1,440 registry rows.

---

## 2. What is deliberately isolated (and verified holding)

| Corpus | Rule | Verified |
|---|---|---|
| Optimizer outputs (`factor_returns*`, `factor_top20_membership`) | never unioned into `unified_panel`/`feature_panel` (cycle protection) | 0 rows leak |
| `combiner_scores_daily` | forbidden to the Discovery Lab (`surface_loader.py` default-deny + C1 remediation) | scrub tested |
| JST, Ken French | isolated calibration/benchmark corpora, never country-tiled | 0 rows leak |
| Predmkt | main-DB tables, not in `feature_panel` | 0 rows leak |
| Forward returns (`1MRet`…, `1DRet`…) | harness hard blacklist (`evaluate_signal.py:146–149`) | enforced |

This discipline is the repo's crown jewel. Nothing below proposes weakening it.

---

## 3. Structural strengths

1. Uniform tidy monthly schema `(date, country, value, variable, source)` with
   indexes on `(country, date)` and `variable`.
2. A real returns source of truth: `country_returns_monthly` (decimal,
   realized-in-month labels) and `loopdb.daily_country_returns()` (backward-
   labeled `1DRet` with the forward-label fix).
3. Normalization discipline (`_CS`/`_TS`) with documented (if inconsistent —
   see §4.3) sign semantics.
4. The semantic layer (`variable_registry`, 1,440 rows; `docs/factor_reference.md`
   auto-regenerated) is unusually strong for a research warehouse.
5. Parquet-first + idempotent loaders means Bloomberg data survives any DB
   accident.
6. Append-only ledgers + harness give a real audit trail from idea to verdict.

---

## 4. Structural problems

### 4.1 Fragmentation: no unified signal panel (the #1 issue)

Country-day signals live in ≥15 loop tables + 2 main-DB daily tables with
three schema dialects:

- main daily: `(date, country, value, variable)` — **no source column**
- loop signals: `(date, country, value, variable, source)`
- special shapes: `dislocation_daily` (event rows), `price_state_surface`
  (JSON blobs), `predmkt_signals_daily` (own grain), `gdelt_raw_daily` (wide)

Consequences observed in code:

- The cockpit producer runs 6+ separate hand-written queries with per-table
  correlated "latest value per (country, variable)" subqueries
  (`cos_mockups/build_cockpit_data.py:268–520`).
- The harness evaluates one `(table, variable)` pair per trial; cross-family
  interaction signals (the "nonlinear linkages" the project wants) cannot be
  expressed without bespoke SQL per trial.
- The combiner hand-picks 6 survivors; adding a 7th input is code, not data.
- The Discovery Lab has its own hard-coded 8-table allowlist.

**Recommendation R1 — build `signal_panel_daily` (and `_monthly`).** One
loop-DB table (parquet-first), schema:
`(as_of_date, country, variable, value, source, frequency, pit_lag_days,
first_knowable_ts)`, unioning the loop `*_signals` tables + selected
`feature_panel` variables, with publication lags stamped **at build time**
(reuse `infer_publication_lag` + the sweep-spec overrides). Explicitly
EXCLUDE optimizer outputs and forward returns — the existing isolation rules
apply to the panel too. This is a read-model, not a new source of truth.

**Recommendation R2 — build `forward_returns_daily` join surface.** One
table `(date, country, fwd_1d, fwd_5d, fwd_21d, fwd_63d)` derived from the
canonical daily returns, embargoed/labeled exactly like the harness does
internally. Keep it in the loop DB, blacklist it from the Lab's allowlist
(same class as `combiner_scores_daily`). Every study, sweep, and any future
ML layer then joins `signal_panel_daily × forward_returns_daily` identically,
instead of five bespoke implementations of the same join.

### 4.2 Country-key drift

- `loopdb.T2_UNIVERSE` = 34 (canonical)
- `country_reference` = 40 rows
- `feature_panel` = **43 distinct countries** (verified live) — multi-country
  sources leak Austria/Greece/etc.; filtering is caller discipline, not
  structure.

**Recommendation R3:** add a `feature_panel_t2` view (feature_panel ∩ the 34)
and make it the documented default for consumers; keep raw `feature_panel`
for coverage QA.

### 4.3 Semantics traps (documented but structural)

- **Percent vs decimal:** country returns decimal; `ff_factors` percent;
  sovereign yields percent. Registry knows this; joins do not enforce it.
- **Sign conventions:** T2 `_CS`/`_TS` sign-flipped at construction; econ
  `_CS`/`_TS` inherit raw sign. Cross-source IC comparisons are silently
  fragile.
- **Date conventions:** first-of-month monthly vs trading-day daily vs print
  dates (WEO/ECFC) vs `snapshot_date` (predmkt).

**Recommendation R4:** stamp `units`, `sign_convention`, `date_convention`
columns into `variable_registry` for the loop-signal families (they're mostly
missing — registry covers the warehouse well but loop signals barely), and
have the `signal_panel_daily` builder read/normalize from the registry so the
panel is uniform (decimal, positive = "good for country," as-of trading day).

### 4.4 Lookahead residuals

| Risk | Status |
|---|---|
| `graph_features_daily` (non-PIT, current-weight edges), 1.33M rows | still built nightly alongside the PIT table; harness history included non-PIT trials. Retire or clearly quarantine. |
| `combiner_scores_daily` in the cockpit | intentional (it's a registered signal), but it is outcome-trained; the front end should always caption it as such |
| WEO/consensus target years to 2031; `demographics_dip` to 2100 | projections in the warehouse — fine, but unclamped "latest value" queries read the future; `signal_panel_daily` must clamp to vintage/print dates |
| `gap_episode_marks.tension_score_current` | **is a copy of `tension_score_at_open`** (`scripts/loop/build_gap_episodes.py:565`) — not lookahead but staleness masquerading as liveness; see front-end audit |

### 4.5 Rebuild fragility

- Anything hand-created in the main DB dies monthly (by design — but predmkt's
  backup/restore dance shows the pattern is easy to get wrong).
- Loop tables are DROP+CREATE per loader with no schema versioning; a loader
  edit silently changes a schema consumers rely on.

**Recommendation R5 (light-touch):** a `loop_schema_version` row per table in
`loop_variable_meta` (currently 7 rows, essentially unused) + a nightly QA
check that consumer-declared columns exist. Cheap, catches drift early.

### 4.6 `variable_meta` / registry coverage gap

`variable_meta` (243 rows) covers only 5 daily source tables. The loop signal
families — the alpha-bearing data — are essentially unregistered. The
Discovery Lab, the sweeps, and any future interaction miner all need machine-
readable metadata (units/sign/lag/universe) for exactly these variables.

**Recommendation R6:** extend the registry builder to enumerate loop `*_signals`
tables (they are small and stable) — this is the prerequisite for R1/R4.

---

## 5. Positioning vs the ultimate goal

Goal: *"What does the data know that is NOT embedded in the price?"* — daily
and long-term country selection.

What the structures already support well:
- **Long-horizon cross-section:** `feature_panel` (730 vars) + valuation
  percentiles + JST tails is a solid strategic layer.
- **Skeptical validation:** harness + ledgers + governance is exactly the
  right custody chain for claims.
- **Propagation family:** PIT graph, lead-lag, similarity twins — the
  strongest validated families — have proper PIT structure.

What the structures do NOT yet support (gap list, priority order):

1. **A price-state vector vs world-state vector join** exists only inside the
   gap engine as JSON blobs (`price_state_surface`). Neither vector is
   queryable as tidy data. If "gap = world-state − price-state" is the atomic
   unit, both sides should be first-class tidy surfaces, not JSON.
2. **No interaction/conditional signal substrate.** Nonlinear linkages
   (signal X conditional on regime Y, X×Z interactions) require the unified
   panel (R1) + forward-return surface (R2) so that a sweep can enumerate
   pairs mechanically through the existing harness.
3. **No analog/feature-vector store.** The analog shelf retrieval exists in
   code (`retrieve_analogs.py`, now PIT-cut) but has no production feature
   store; `state_embedding` lives only in Neo4j. A monthly country-state
   matrix (the ~41 `_CS` factors already used by similarity twins) persisted
   as a versioned table would power analogs, regime conditioning, and the
   front end's "what does today rhyme with" view from one substrate.
4. **Forward-tracking outcomes are scattered** (gap holdout, thesis marks,
   graveyard rosters, harness IC series). A single `forward_outcomes` view —
   claim id → entry date → horizon → realized return — would let the front
   end show live calibration for every surface with one query.

---

## 6. Priority summary

| # | Change | Size | Payoff |
|---|---|---|---|
| R1 | `signal_panel_daily`/`_monthly` unified PIT signal panel | M | unlocks interaction mining, one-query consumers |
| R2 | `forward_returns_daily` embargoed join surface | S | kills 5 bespoke join implementations |
| R3 | `feature_panel_t2` 34-country view | XS | removes caller-discipline filtering |
| R4 | units/sign/date registry columns for loop signals | S | makes R1 semantically uniform |
| R5 | loop schema-version + consumer-column QA check | XS | catches loader drift |
| R6 | registry coverage of loop `*_signals` | S | prerequisite for R1/R4 |

None of these touch the isolation rules; all are additive read-models in the
loop DB (parquet-first), consistent with "never create persistent tables in
the main DB."
