# ASADO — Country Data Collection & Research Platform

ASADO assembles macro / governance / risk / climate / trade / market data for a **34-country
universe** from **~38 sources** and stores it in a **hybrid DuckDB + Neo4j** stack with a raw
warehouse, a canonical normalized feature layer, bilateral trade/banking/portfolio networks, a
**daily-frequency extension**, prediction-market & event surfaces, a **global commodity surface**,
and country-state vector embeddings.

It runs on **two cadences**, both self-generating (no hand-maintained spreadsheets in the loop):

- **Monthly** (`scripts/monthly_update.py`) — collects everything, rebuilds the warehouse + graph.
- **Daily** (`scripts/daily_update.py`) — the same factor pipeline on a daily metronome, for the two
  domains that move daily: **T2 prices** (Bloomberg-direct) and **GDELT news** (GKG-direct). Econ has
  no daily factors and is skipped.

**Returns are the outcome source of truth.** Country and factor-portfolio returns live in dedicated
return surfaces; macro, commodity, prediction-market, GDELT, Bloomberg, and graph layers are
*explanatory context* unless explicitly joined back to returns.

> Live, per-variable detail is auto-generated each rebuild — see **[`docs/factor_reference.md`](docs/factor_reference.md)**
> and the latest **[`docs/DATABASE_AUDIT_2026_06_09.md`](docs/DATABASE_AUDIT_2026_06_09.md)**.

---

## Quick start

```bash
cd ASADO
source venv/bin/activate

python scripts/monthly_update.py        # full monthly: collect → DuckDB → normalize → daily → Neo4j
python scripts/daily_update.py          # daily metronome: T2 + GDELT factors & returns
```

| Command | What it does | Runtime |
|---|---|---|
| `monthly_update.py` | All collectors, both Bloomberg pulls, warehouse + normalized + daily panels + optimizer returns + Neo4j + embeddings + schema | ~12–18 min |
| `daily_update.py` | Daily Bloomberg pull → T2 master/normalize/returns; GDELT normalize/returns | ~12–15 min |

**Prerequisites:** Bloomberg Terminal logged in on the Parallels Windows VM (for the live pulls);
Neo4j running (`brew services start neo4j`). Logs land in `Data/logs/`.

### Common options
```bash
python scripts/monthly_update.py --skip-bloomberg     # no Terminal — reuse existing Bloomberg data
python scripts/monthly_update.py --db-only            # rebuild DBs from existing panels (no collection)
python scripts/monthly_update.py --commodity-only     # commodity collector + DB/daily/schema refresh
python scripts/monthly_update.py --skip-neo4j         # skip graph + embeddings
python scripts/daily_update.py --skip-bloomberg       # reuse existing daily Bloomberg pull
python scripts/daily_update.py --t2-only              # T2 chain only (no GDELT / DB / graph)
```

---

## Architecture: two cadences, one warehouse

### Monthly pipeline (`monthly_update.py`)
1. **Collectors** — free sources (external, extended, IMF, bilateral, macrostructure, World Bank
   commodities) + **two live Bloomberg pulls**:
   - `collect_bloomberg.py` — the 28 Bloomberg **econ/market** variables (bonds, CDS, OIS, breakevens, WIRP, ECFC, PMI, M2, ETF passive flows).
   - `collect_t2_bloomberg.py` — the **T2 country index/price/MCAP/commodity/FX** workbook, pulled **direct from Bloomberg** (replaces the old hand-saved Excel dump).
2. **T2 master + benchmarks** (`build_t2_master.py`, `build_benchmark_rets.py`) — raw factors, returns, P2P.
3. **GDELT ingest** (`gdelt_ingest/`) — fetches new GKG days from `data.gdeltproject.org`, builds the monthly + daily signal workbooks in-repo.
4. **Econ workbook** (`build_econ_panel.py`) — Econ.xlsx from the warehouse.
5. **Normalize + optimizers** — T2 / GDELT / Econ `_CS`/`_TS` factors and top-20 factor-return portfolios; ingested to `factor_returns`.
6. **Warehouse** — `setup_duckdb.py` (raw union), `build_normalized_panel.py` (normalized + `feature_panel`), `build_daily_panels.py` (daily tables), prediction markets, event log.
7. **Graph + docs** — `setup_neo4j.py`, `build_embeddings.py`, `build_schema_registry.py`, `build_factor_reference.py`.

### Daily pipeline (`daily_update.py`)
The monthly factor flow at a **daily metronome** — 1/5/20/60/120-**day** returns instead of
1/3/6/9/12-month — for the two fast-moving domains. T2 prices come **direct from Bloomberg**
(`collect_t2_bloomberg.py --daily`, calendar-day grid); GDELT signals come from the GKG ingest.
Outputs land in `Data/work/t2_daily/` and `Data/work/gdelt_daily/`, then load into the DuckDB daily
tables. Designed to run unattended on a schedule with the Bloomberg connection kept alive.

### Self-contained work dirs
All intermediate artifacts are internalized under `Data/work/{t2,gdelt,econ,t2_daily,gdelt_daily}` —
ASADO generates everything it needs from Bloomberg + the free APIs + GKG; there are no
hand-maintained Excel files in the pipeline.

---

## Warehouse contents (current shape)

DuckDB at `Data/asado.duckdb` (~3.5 GB). **37 objects** (33 tables + 4 views) across five layers.
Tidy schema everywhere: `(date, country, value, variable, source)`.

### Layer 1 — collected sources (feed `unified_panel`)
~38 sources. Largest contributors (base variables): **t2** (111), **t2_raw** (53), **gdelt** (93),
**bloomberg** (28), plus the macro block — IMF (×7 datasets), BIS (×5), OECD (×5), ECB FX, World
Bank, FRED, GPR, EPU, ND-GAIN, FAOSTAT, ILOSTAT, UNDP, OFAC, demographics. (Full per-source
breakdown in the audit doc.)

### Layer 2 — query surfaces (country-keyed)
| Surface | Rows | Variables | Note |
|---|---:|---:|---|
| `unified_panel` (view) | ~12.1M | ~426 base | raw cross-source union |
| `normalized_panel` | ~0.8M | ~294 | `_CS` (cross-sectional) + `_TS` (time-series) z-scores |
| `feature_panel` (view) | ~3.3M | **~720** | primary query-facing union (raw + normalized) |

### Layer 3 — daily extension (fresh through the latest run)
| Table | Rows | Vars |
|---|---:|---:|
| `t2_factors_daily` | ~35.6M | 111 |
| `t2_levels_daily` | ~15.3M | 48 |
| `gdelt_factors_daily` | ~10.2M | 75 |
| `gdelt_raw_daily` | ~967K | 45-col (249-country bridge) |
| `daily_calendar` | ~328K | per-country trading days |

### Layer 4 — returns (outcome source of truth)
| Table | Factors | Sources |
|---|---:|---|
| `factor_returns` (monthly) | ~390 | `t2_optimizer`, `gdelt_optimizer`, `econ_optimizer` |
| `factor_returns_daily` | ~180 | `t2_optimizer_daily`, `gdelt_optimizer_daily` |
| `factor_top20_membership` | ~393 | sparse country membership per factor bucket |
| `country_factor_attribution` (view) | — | `membership ⨝ returns` = weight × factor_return |

### Layer 5 — knowledge graph (Neo4j)
~**1,174 nodes** (Factor, Country ×34, CentralBank ×31, DataSource, CrisisEvent, SanctionsProgram,
Commodity ×4) and ~**30K edges** (`HAS_FACTOR_EXPOSURE`, `TRADES_WITH`, `HAS_BANKING_EXPOSURE_TO`,
`HOLDS_PORTFOLIO`, `HAS_CRISIS_HISTORY`, `HAS_CENTRAL_BANK`, `SUBJECT_TO`, `EXPORT_EXPOSED_TO`,
`DATA_AVAILABLE_FROM`). 34-dim cosine `countryStateIndex` on `Country.state_embedding`.

### Global commodity surface (NOT country-tiled)
Commodities are **global series** — one value per date, not tied to a country. They live in:
- `commodity_panel` (view) — `WB_CMDTY_<SERIES>_<FEATURE>` for 87 series × 7 features (level, MOM, YOY, 3M/12M return, 12M vol, 36M z), date-keyed.
- `wb_commodity_prices` / `wb_commodity_indices` / `wb_commodity_features` / `wb_commodity_meta` — canonical Pink Sheet tables.

> Earlier builds *broadcast* commodities identically across all 34 countries into `feature_panel`
> (`wb_commodity_factor_panel`). That tiling is **deprecated** — it inflated the variable count and
> produced degenerate cross-sectional variants. Join `commodity_panel` to returns **on `date`**.

### Auxiliary
`bilateral_portfolio_matrix` (reporter–counterparty ownership), `predmkt_*` (Kalshi/Polymarket
snapshots + spillovers + composites), `event_log` (curated dated events), `variable_meta`
(structural metadata), `country_reference`.

---

## Returns source of truth

Anchor performance / winner-loser / attribution questions on these surfaces:

- **Country returns (T2, 34 countries):** monthly = `feature_panel` rows `source='t2'`, variables `1MRet/3MRet/6MRet/9MRet/12MRet`; daily = `t2_factors_daily`, `1DRet/5DRet/20DRet/60DRet/120DRet`. The `gdelt`-source return rows are bit-exact aliases of the T2 returns (the optimizer's dependent variable), not a second source.
- **Factor portfolio returns:** monthly `factor_returns` (`econ_/t2_/gdelt_optimizer`); daily `factor_returns_daily` (`t2_/gdelt_optimizer_daily`). These are top-20%-of-countries portfolio returns, not raw factor levels.
- **Attribution:** `country_factor_attribution` = `factor_top20_membership ⨝ factor_returns` → `weight × factor_return` per (country, factor, period).

**Cycle guardrail:** optimizer outputs (`factor_returns*`, `factor_top20_membership`,
`country_factor_attribution`) are never unioned into `feature_panel`/`unified_panel` — those are the
inputs the optimizer consumes. `scripts/qa/validate_returns_first.py` enforces this.

---

## Data resilience

Every collector is safe to re-run: load existing panel → fetch fresh → **source-level merge** (a
failed source keeps its prior data) → timestamped backup before overwrite → run-history JSON →
delta report. One source failing never breaks a run. The DB is fully rebuildable from the panels
(`--db-only`); rebuilds from an empty file shed any orphan tables.

---

## Variable families (reference)

- **Equity factors (T2, Bloomberg-direct):** `t2_master`/`t2_raw` — Best/Trailing PE, Earnings Yield, ROE, EPS, MCAP, 120MA Signal, RSI14, vol, momentum (1/3/6/9/12M returns + spreads), P2P.
- **External macro (`external_factors`, 7 src):** EPU, GPR (+Global GPR/Threat/Act), BIS Credit-GDP Gap, BIS Property, BIS REER, OECD CLI, World Bank governance/macro/demographics/reserves/climate.
- **Extended macro (`extended_factors`, 12 src):** BIS policy/debt-service rates, OECD BCI/CCI, ECB FX (24 pairs), ND-GAIN (score/vulnerability/readiness), ILOSTAT, UNDP HDI/IHDI/GDI/GII, OFAC, FAOSTAT, FRED (VIX, UST 2Y/10Y, curve, USD index, HY OAS), EIA.
- **IMF (`imf_factors`, 7 datasets):** CPI + YoY, WEO projections (→2031), BOP aggregates, money-market/discount/bond/T-bill rates, FX, employment, trade-in-goods.
- **Macrostructure (`macrostructure_factors`):** IMF FSI bank fragility, WB QPSD debt structure, OECD institutional depth, central-bank footprint (`MS_CentralBank_*`), reserve adequacy, swap-line access, policy backstop, investor-base fragility.
- **Bloomberg econ (`bloomberg_factors`, 28):** sovereign bonds (2/5/10/30Y), CDS 5Y, breakeven 10Y, OIS 10Y + Z-spread, WIRP implied rate, M2 YoY, PMI mfg/svcs, ECFC GDP/CPI consensus, debt/GDP, MIPD, yield-curve slope, and the ETF passive-flow family (`MS_*`).
- **GDELT (`gdelt_panel`, 93):** salient news signals — attention (fast/slow/shock/trend ±z), country news risk/sentiment/attention (raw + normalized, ±CS/TS). *(The 1,300+ deep theme/GCAM fields were retired.)*
- **Commodities (`commodity_panel`, 87 global series):** Pink Sheet prices + indices with level/MOM/YOY/3M/12M-return/vol/z features. Global, joined to returns on date.

---

## Country coverage notes
- 34-country T2 universe is always fully present. **9 extra countries** (Austria, Belgium, Finland, Greece, Ireland, New Zealand, Norway, Portugal, Russia) leak into the panels from multi-country feeds (ECB FX / OECD / IMF).
- Sparse-by-source: EPU ~21/34, OECD CLI/BCI/CCI ~20–22, BIS policy rates 26, CDS 15, breakevens 6.
- Annual/lagged sources sit a year+ back by nature (UNDP HDI, ND-GAIN → 2023; FAOSTAT, IMF BOP, portfolio ownership → 2024). **`eia` is dead at 2019-12** (broken collector — fix or drop).
- Forecast data is intentional: `imf_weo` → 2031, `demographics_dip` → 2100.

---

## Database access

### Python bridge (`scripts/db_bridge.py`)
```python
from scripts.db_bridge import AsadoDB
with AsadoDB() as db:
    df       = db.query_panel("SELECT * FROM feature_panel WHERE country='Brazil' LIMIT 10")
    records  = db.query_graph("MATCH (c:Country)-[:HAS_CRISIS_HISTORY]->(e) RETURN c.t2_name, e.name")
    profile  = db.country_profile("Turkey")           # factors + all graph relationships
    snapshot = db.factor_snapshot("BIS_Credit_GDP_Gap")
    similar  = db.query_graph("""MATCH (c:Country {t2_name:'Turkey'})
        CALL db.index.vector.queryNodes('countryStateIndex',6,c.state_embedding)
        YIELD node,score WHERE node<>c RETURN node.t2_name AS country, score ORDER BY score DESC""")
```

### Neo4j
`brew services start neo4j` · bolt://localhost:7687 · web http://localhost:7474 · creds `neo4j`/`mythos2026`.

### MCP server — query ASADO from Claude Desktop
`scripts/asado_mcp_server.py` is a stdio MCP server exposing a read-only tool surface. Register it in
`~/Library/Application Support/Claude/claude_desktop_config.json` under `mcpServers` using ASADO's
venv Python, then relaunch Claude Desktop:

```json
{ "mcpServers": { "asado": {
    "command": "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/venv/bin/python",
    "args": ["/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/scripts/asado_mcp_server.py"],
    "env": { "ANTHROPIC_API_KEY": "sk-ant-..." } } } }
```

Key tools: `ask_asado` (NL Q&A — needs `ANTHROPIC_API_KEY`), `get_schema_summary`, `run_duckdb_sql`,
`run_neo4j_cypher`, `get_country_profile`, `event_window` / `events_in_window`, `daily_factor_series`,
`country_returns`, `factor_return_series`, `country_factor_attribution`, `return_leaders`,
`predmkt_snapshot` / `country_signal_now` / `event_market_set`, `commodity_price_series`. DuckDB is
opened read-only; treat Cypher as read-only by convention. (ChatGPT Desktop isn't supported — it
needs a remote SSE endpoint; this server is stdio.)

Troubleshooting: `nc -z localhost 7687` (Neo4j up?); `./venv/bin/python scripts/build_schema_registry.py`
(refresh schema cache); check `~/Library/Logs/Claude/mcp*.log` if the server fails to start.

---

## Alpha-Hunting Loop (Layer 1 + validation infrastructure)

The research loop that sits on top of the warehouse (spec: `PRD_Alpha_Hunting_Loop.md`). All loop-owned
state lives in a **separate DuckDB** — `Data/loop/asado_loop.duckdb` — so monthly rebuilds of
`asado.duckdb` can never destroy it. The main DB is attached read-only as the `asado` schema.

### Nightly job (launchd, 06:45)
`scripts/loop/loop_daily_job.py` (`com.arjundivecha.asado-loop-daily`) runs, in order:
1. `collect_news_bridge.py` — accumulates portfolio holdings + 800-ticker ETF closes from the News repo
   (`portfolio_holdings_daily`, `portfolio_summary_daily`, `etf_prices_daily`, `etf_t2_map`).
2. `ledgers.py --mark` — auto-marks open theses from T2 daily returns; closes on invalidation/expiry.
3. `build_country_returns.py` — refreshes `country_returns_monthly` (canonical marking surface).
4. `build_graph_features.py` — Neo4j edges × T2 returns → `graph_features_daily`
   (trade/banking neighbor-return gaps, holder stress, two-hop propagation; 2008→present).
5. `build_dislocations.py` — detectors D2/D4/D5/D7/D8/D9 → `dislocation_daily` +
   the daily brief at `Data/dislocations/brief_YYYY_MM_DD.md` (the Layer 2 reading list).
6. `ledgers.py --rebuild` — folds the JSONL ledgers into loop-DB tables.

A second launchd job (`com.arjundivecha.asado-predmkt-daily`, 06:30) runs
`scripts/predmkt_daily_job.py`: restore-from-archive → collect prediction markets → re-archive to
`Data/loop/predmkt_archive/` (rebuild-proof).

### Validation discipline (the skeptic)
- **Hypothesis ledger** (`ledgers/hypothesis_ledger.jsonl`, git-tracked): mechanism written **before**
  results; every registration counts a trial against its family for the deflated Sharpe.
- **Harness** (`scripts/harness/evaluate_signal.py`, MCP `evaluate_signal`): PIT embargo inside the
  harness, rank IC + Newey–West t, top-7 vs EW with costs, sub-periods, deflated Sharpe vs family
  trial count. Forward-return variables (`1MRet` etc.) are hard-blacklisted as signals.
  Results → `Data/loop/harness_runs/` + `harness_results` table; verdicts auto-attach to the ledger.
- **Thesis ledger** (`ledgers/thesis_ledger.jsonl`): frozen entry thesis + probability + invalidation
  level; auto-marked daily; Brier calibration accumulates as theses resolve. Paper by default.
- PIT unit tests: `tests/loop/test_harness_pit.py` (alignment, lookahead canaries, NW-t, DSR).

MCP tools added to the server: `country_news` (live GDELT DOC 2.0 headlines), `register_hypothesis`,
`evaluate_signal`, `open_thesis`.

Monthly vintage snapshots: `scripts/snapshot_vintages.py` → `Data/vintages/{YYYY_MM}/` (wired into
`monthly_update.py`).

**Known v1 caveats:** graph features use *current* Neo4j edge weights over the whole backtest window
(slow-moving, but not point-in-time); daily harness mode is IC-only (no cost model yet); D4 needs the
`t2_levels_daily` staleness issue resolved (REER last changed 2026-04-30); GDELT DOC API rate-limits
aggressively — `country_news` fails loudly and recovers when the block lifts.

---

## Configuration & dependencies

- **Country mapping:** `config/country_mapping.json` (34-country ISO/OECD/BIS/WB/EPU/GPR codes).
- **Event registry:** `config/event_log_seed.yaml`.
- **API keys** (env or `/Users/arjundivecha/Dropbox/AAA Backup/.env.txt`): `FRED_API_KEY`, `EIA_API_KEY`. Missing keys → that source skips gracefully.
- **Python:** `pandas numpy requests openpyxl pyarrow wbgapi sdmx1 xlrd duckdb neo4j scikit-learn mcp[cli] cvxpy` (see `requirements.txt`).
- **Bloomberg:** separate OpusBloomberg conda env (`/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg/.venv`, has `blpapi`). Connection: macOS → TCP 8194 → Parallels Windows VM → bbcomm → Terminal (VM IP auto-detected).

---

## Architecture notes
- IMF: SDMX 3.0 REST at `api.imf.org` (no key); WEO carries forecasts to 2031; IMTS bilateral trade + BIS LBS banking feed the graph edges.
- BIS via SDMX (`data.bis.org`); OECD via `sdmx.oecd.org`; ECB FX via per-currency SDMX; ND-GAIN/UNDP/FAOSTAT via bulk download.
- Bloomberg: both the econ pull (`collect_bloomberg.py`) and the T2 pull (`collect_t2_bloomberg.py`) run live `blpapi`. The T2 pull batches by field (Excel-BDH-style) and supports a `--daily` calendar-day mode (matches Excel `BDH(...Per=D)` via `calendar_fill`). Derived signals (MIPD from CDS, Z-spread, curve slope) computed in-collector.
- GDELT: ingested from `data.gdeltproject.org` GKG v2 into in-repo panels + monthly/daily workbooks; the deep theme/GCAM layer is retired in favor of the salient signal set.
- Commodities: global Pink Sheet series; the country-broadcast (`wb_commodity_factor_panel`) is deprecated in favor of the global `commodity_panel`.
- Embeddings: PCA-compressed z-scored factor values on `Country` nodes with a cosine vector index.

---

## Skipped sources
| Source | Why skipped | Covered by |
|---|---|---|
| UN Comtrade | API registration broken | IMF IMTS bilateral trade, IMF ITG |
| ACLED | requires API key + registration | GPR index, GDELT signals |
| IPU Parline | 403 Forbidden | OFAC, WGI governance |
| WITS | 403 Forbidden | IMF trade, WB trade openness, BIS REER |

---

## Reference docs
- `docs/factor_reference.md` — auto-generated, every table/source/variable + the full graph map.
- `docs/DATABASE_AUDIT_2026_06_09.md` — latest full warehouse audit.
- `docs/DAILY_PIPELINE_REPORT_2026_06_09.md` — daily pipeline build + canonical validation.
- `CLAUDE.md` — agent/dev guidance and conventions.
