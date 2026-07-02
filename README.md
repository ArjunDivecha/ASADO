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

### Cold start for a new agent (read this first)

If you just picked up this repo, do these five things in order before touching code:

1. **Read the docs in this order:** `README.md` (this file), `CLAUDE.md`
   (coding conventions), `AGENTS.md` (learned facts), `docs/README.md`
   (documentation index: canonical specs vs. generated reports vs. historical
   snapshots), and `llmchat.md` (recent session history).
2. **Activate the venv:** `source venv/bin/activate`. Bloomberg-only scripts run
   under the OpusBloomberg conda env; everything else uses this venv.
3. **Check services:** `brew services list | grep neo4j` must show `started` for
   any graph operation. Bloomberg Terminal must be logged in on the Parallels
   Windows VM for live Bloomberg pulls.
4. **Run the smoke tests:** `python -m pytest tests/loop/test_harness_pit.py -q`
   should pass. For a full health check:
   `python scripts/setup_duckdb.py --check && python scripts/setup_neo4j.py --check`.
5. **Verify the loop DB exists:** `Data/loop/asado_loop.duckdb` is where loop
   signals, returns, and harness results live. It is gitignored but essential.
   If it's missing, run `scripts/loop/loop_daily_job.py` (or the full
   `daily_update.py`) after the main DB is built.

**Never create persistent tables in `Data/asado.duckdb`** — `setup_duckdb.py`
deletes and recreates it. Loop data lives in `Data/loop/asado_loop.duckdb` and
parquet intermediates under `Data/work/loop/`. For the full source-of-truth map,
see `docs/README.md`.

| Command | What it does | Runtime |
|---|---|---|
| `monthly_update.py` | All collectors, both Bloomberg pulls, warehouse + normalized + daily panels + optimizer returns + Neo4j + embeddings + schema | ~12–18 min |
| `daily_update.py` | Daily Bloomberg pull → T2 master/normalize/returns; GDELT normalize/returns | ~12–15 min |

**Prerequisites:** Bloomberg Terminal logged in on the Parallels Windows VM (for the live pulls);
Neo4j running (`brew services start neo4j`). Logs land in `Data/logs/`.

**Automated morning run (2026-06-10):** launchd job `com.arjundivecha.asado-daily`
runs `scripts/run_asado_daily.sh` weekdays at 07:30. It auto-starts the Parallels
VM + bbcomm, runs a live Bloomberg data-pull preflight (iMessages once and
retries every 20 min until 11:00 if the Terminal needs a login), then runs
`daily_update.py --resume` with one auto-retry. `daily_update.py` is now
**fail-fast + resumable**: completed stages checkpoint to
`Data/logs/daily_update_progress_YYYY_MM_DD.json`, a failed stage aborts the
rest (no downstream stages on stale data), and `--resume` continues from the
failed stage without redoing the Bloomberg pull. The 07:00 NightWatch digest
(`A Working/NightWatch/`) reports the result each morning.

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

### Style-factor benchmark (Ken French — NOT country-tiled)
`ff_factors` holds the Fama-French **5 factors + momentum + RF** (`Mkt_RF, SMB, HML, RMW, CMA,
RF, WML`) for **8 FF regions** (US, Developed, Developed_ex_US, North_America, Europe, Japan,
Asia_Pacific_ex_Japan, Emerging), **monthly + daily**, USD, values in **percent**. US history
runs to 1926/1963, the developed regions to 1990, Emerging (monthly only) to 1989.

These are a **benchmark/explanatory** surface, not a return source — the question they answer is
"is a signal's P&L genuine alpha, or just repackaged value/size/momentum/quality/market beta?"
Like commodities, they are **isolated** (region-keyed, 8 series) and **never broadcast** to the
34 countries or unioned into `feature_panel`/`unified_panel`. The country→region link lives in
`config/ff_region_map.json` and is applied **on the fly** at regression time. Built by
`scripts/collect_ff_factors.py`; the spanning tool is `scripts/harness/ff_spanning.py` (below).

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
    ff       = db.ff_factor_series(country="Brazil", frequency="monthly", wide=True)  # → Emerging FF bundle
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
`scripts/loop/loop_daily_job.py` (`com.arjundivecha.asado-loop-daily`) runs 33 steps, in order
(each in its own subprocess; one failure never stops the rest, but any failure exits non-zero):

1. `collect_news_bridge.py` — portfolio holdings + 800-ticker ETF closes from the News repo
   (`portfolio_holdings_daily`, `portfolio_summary_daily`, `etf_prices_daily`, `etf_t2_map`).
2. `ledgers.py --mark` — auto-marks open theses from T2 daily returns; closes on invalidation/expiry.
3. `build_country_returns.py` — refreshes `country_returns_monthly` (canonical marking surface).
4. `build_tot_shares.py` — Comtrade commodity trade shares for D1 (slow-moving, fetch-failure-safe).
5. `build_graph_features.py` — Neo4j edges × T2 returns → `graph_features_daily`
   (trade/banking neighbor-return gaps, holder stress, two-hop propagation; 2008→present).
6. `build_forward_calendar.py` — curated forward catalysts (CB decisions, elections, index reviews).
7-8. `collect_foreign_flows_bbg.py` + `collect_foreign_flows.py` — Bloomberg exchange-sourced foreign
   equity flows (KR/TW/TH/PH/ID) + NSDL India → `foreign_flows_daily`.
9-10. `collect_sovereign_daily_bbg.py` + `load_sovereign_daily.py` — daily 5Y + 1Y CDS (20/18
   countries) + direct-pull 10Y + 2Y yields (32/27) → `sovereign_daily` (the D4 v2 cross-asset
   legs) + `sovereign_signals` (CDS curve slope 5Y−1Y — **inversion = imminent-distress
   pricing** — and the daily 2s10s govt slope, both with 252d z-scores).
11. `build_valuation_block.py` — month-end CAPE/PB/DY/EY/ERP + 10y percentiles → `valuation_monthly`.
12. `collect_weo_vintages.py` — IMF WEO vintage surface → `weo_vintages` / `weo_revisions` (D3 input).
13-14. `collect_etf_flows_bbg.py` + `load_etf_flows.py` — country-ETF shares-out/NAV/AUM →
   `etf_flows` + `etf_flow_signals` (positioning/crowding layer).
15-16. `collect_consensus_bbg.py` + `load_consensus.py` — Bloomberg ECFC consensus GDP/CPI forecast
   history → `consensus_daily` + `consensus_revisions`.
17. `collect_cot.py` — CFTC COT speculator positioning, 12 commodity futures (keyless Socrata).
18-19. `collect_market_implied_bbg.py` + `load_market_implied.py` — **market-implied stress layer**:
   FX ATM implied vol in THREE tenors (1W/1M/3M — the 1W−3M term slope inverts when stress is
   priced NOW), 25-delta risk reversals + butterflies, and 3M forward/NDF-implied carry for 25 T2
   currency pairs (30 countries, incl. the HKD/SAR peg surfaces and forward-only Denmark), the
   VIX/VIX3M/MOVE/HY-IG-OAS/DXY/BBDXY dashboard, and CL/CO/HG/GC/NG 1st+2nd futures generics
   (2006+) → `market_implied_daily` + `market_implied_signals` (252d z-scores, VIX term-structure
   ratio, vol term slope, carry z, curve shape). RR is sign-normalized: **positive = options
   premium on local-currency depreciation**; carry is sign-normalized: **positive = local rates
   above USD**. See `docs/MARKET_IMPLIED_EXTENSION_STATUS.md` +
   `docs/BBG_SKILL_ENHANCEMENTS_2026_06_12.md`.
20-21. `collect_sov_ratings_bql.py` + `load_sov_ratings.py` — **sovereign rating history via BQL**
   (ASADO's first BQL collector: `//blp/bqlsvc` + EXCEL unlock + the `issuerof()` hop, CDS-contract
   anchors): S&P/Moody's/Fitch monthly back to 2015, 33 countries, 21-pt numeric scale →
   `sov_ratings_monthly` + the dated `sov_rating_changes` event table (128 events).
22-23. `collect_eco_surprise_bbg.py` + `load_eco_surprise.py` — **economic surprise layer**:
   ACTUAL_RELEASE vs BN_SURVEY_MEDIAN on ECO release tickers (CPI YoY 31 countries, unemployment,
   GDP, Markit PMI) → `eco_surprise_monthly` + `eco_surprise_signals` (per-print surprise z,
   growth/inflation surprise composites).
24. `build_graph_features_pit.py` — **point-in-time graph features** (see "The graph machine"
   below): PIT trade/bank/twohop/holder gaps + Katz, hub-amplified and trade-bloc features from
   the stored edge vintages → `graph_features_pit_daily`.
25. `build_similarity_features.py` — **fundamental-twins map**: month-end factor vectors →
   top-5 cosine twins → twin-convergence gaps → `similarity_features_daily` + `similarity_twins`.
26. `build_leadlag_features.py` — **lead-lag network**: monthly lag-1 cross-correlation edges →
   leader-gap features → `leadlag_features_daily` + `leadlag_edges`.
27. `build_combiner.py` — **walk-forward ridge combiner** → `combiner_scores` (monthly, tested
   DEAD, kept for the record) + `combiner_scores_daily` (the live prediction surface).
28. `write_graph_discoveries.py` — pushes `SIMILAR_TO` / `LEADS` edges + combiner ranks into
   Neo4j for MCP/browser exploration.
29. `build_dislocations.py` — detectors **D1 D2 D3 D4 D5 D7 D8 D9 D10** → `dislocation_daily` +
   the daily brief at `Data/dislocations/brief_YYYY_MM_DD.md` (the Layer 2 reading list; includes
   forward-calendar, market-implied stress, sovereign-curves/ratings/surprises, foreign-flow,
   ETF-positioning and COT context sections). D10 (A10, live 2026-06-11) fires on
   FX-options-vs-equity conflicts: options stress unpriced by equity, or equity stress unconfirmed
   by options. D6 stays blocked until predmkt history accumulates.
29b. `build_triptych_scan.py` — **the Triptych prior layer** (2026-07-02, ASADO-native port of
   the Triptych visual tool's analytics kernel): exhaustive sweep of every `t2_raw` factor +
   the warehouse variables declared in `config/triptych_scan.yaml` × 34 countries ×
   3 normalizations (raw / expanding-z / cross-country-z) × 2 return modes (absolute/relative)
   × 6 horizons, in BOTH threshold modes — **pit** (point-in-time expanding deciles, no
   lookahead → the prior surface, PRD 7.3 confidence) and **full** (full-sample descriptive,
   confidence hard-zeroed). → `triptych_scan` + `triptych_review_queue` tables, `triptych_priors`
   view, parquets in `Data/loop/`. Kernel: `scripts/loop/triptych_kernel.py` (line-verified
   parity with the tool's core.js; PIT canaries in `tests/loop/test_triptych.py`). Surfaces:
   cockpit "Triptych" desk tab + country-letter priors, Fable packet block, MCP tools
   `triptych_link` / `triptych_prior_snapshot` / `triptych_queue`. Deep links into the visual
   tool (https://triptych-one.vercel.app) via `scripts/triptych_tool_link.py`. ~10 s, all cores.
30. `build_evidence_packs.py` — freezes GDELT headlines for tonight's fired dislocations.
31. `ledgers.py --rebuild` — folds the JSONL ledgers into loop-DB tables.
32. `calibration_report.py` — regenerates the current-month calibration report (PARTIAL-stamped
   until ≥ 10 closed theses).
33. `build_jst_risk_report.py` — dated JST long-cycle tail-risk report (xlsx + PDF) in
   `Data/loop/risk_reports/`: per-country current drawdown → JST 1870-2020 bucket → forward
   real-equity tail (the once-in-a-century p10 the modern sample can't see). Read-only; DM names
   are in-scope, EM names carry a DM-analogy label.

A second launchd job (`com.arjundivecha.asado-predmkt-daily`, 06:30) runs
`scripts/predmkt_daily_job.py`: restore-from-archive → collect prediction markets → re-archive to
`Data/loop/predmkt_archive/` (rebuild-proof). The curated registry (`config/predmkt_curated.yaml`)
was expanded to 152 live markets on 2026-06-11; `scripts/loop/discover_predmkt_candidates.py`
sweeps Kalshi + Polymarket for new candidates to curate.

### Validation discipline (the skeptic)
- **Hypothesis ledger** (`ledgers/hypothesis_ledger.jsonl`, git-tracked): mechanism written **before**
  results; every registration counts a trial against its family for the deflated Sharpe.
- **Harness** (`scripts/harness/evaluate_signal.py`, MCP `evaluate_signal`): PIT embargo inside the
  harness, rank IC + Newey–West t, top-7 vs EW with costs, sub-periods, deflated Sharpe vs family
  trial count. v2.1 (2026-06-12) adds a 1d/5d/21d hold-period grid, breakeven cost (bps), and a
  5 bps cost case for daily runs — see "The cost / holding-period model" below.
  Forward-return variables (`1MRet` etc.) are hard-blacklisted as signals.
  Results → `Data/loop/harness_runs/` + `harness_results` table; verdicts auto-attach to the ledger.
- **Thesis ledger** (`ledgers/thesis_ledger.jsonl`): frozen entry thesis + probability + invalidation
  level; auto-marked daily; Brier calibration accumulates as theses resolve. Paper by default.
- PIT unit tests: `tests/loop/test_harness_pit.py` (alignment, lookahead canaries, NW-t, DSR).

### Analysis tools (added 2026-06-12)
- **Batch sweep runner** (`scripts/harness/sweep_signals.py`): reads a YAML spec
  (`config/sweeps/*.yaml`), pre-registers each signal as a hypothesis (mechanism text is
  mandatory), runs the harness, and writes a sweep summary (JSON + xlsx) to
  `Data/loop/harness_runs/sweeps/`. Every entry is a trial charged against its family —
  re-specs and flipped re-registrations included. First family swept:
  `bbg_skill_2026_06` (15 trials across the six new Bloomberg layers; see
  `config/sweeps/new_bbg_layers_2026_06.yaml` and `..._round2_...yaml`).
  The 2026-06-12 systematic pass added 18 more trials over the previously
  untested loop families (valuation block, ETF flows/short interest, graph
  spillovers, consensus revision momentum, FX vol level — specs in
  `config/sweeps/`). Honest scoreboard: graph spillover family produced four
  WEAK verdicts with the strongest ICs in the warehouse so far
  (banking-claims neighbor gap nw_t 5.7, two-hop trade gap 4.5 — but graph
  edges are current-weights, not PIT, so promotion requires a vintage-edge
  robustness pass); CPI consensus revision momentum WEAK (nw_t 2.3, same
  reflation direction as the flipped inflation-surprise result); ETF flow
  momentum significant *against* its registered direction (contrarian,
  nw_t −2.2, would need a fresh flipped registration to claim); valuation
  percentiles and short interest DEAD cross-sectionally.
- **Event-study engine** (`scripts/loop/event_study.py`): cross-event CARs on T2 country
  returns around discrete events with market-adjusted abnormal returns, bootstrap CIs,
  next_day/next_month anchoring, and PDF/xlsx/JSON outputs to `Data/loop/event_studies/`.
  Presets: `rating_downgrade`, `rating_upgrade`, `cds_inversion`, `growth_hot`,
  `growth_cold`, `inflation_hot`, `dislocation` (filterable by detector), `event_log`
  (curated registry), or arbitrary `--events-sql`. Verified findings (2026-06-12):
  sovereign rating downgrades → −0.7% abnormal return in 5 trading days (t≈−2.0,
  73 events since 2008), drifting to −2.1% at 63 days; CDS 1Y/5Y curve inversions →
  −4.5% at 63 days (t≈−2.4, 41 events) — the 1Y CDS layer's payoff is event-conditional,
  not cross-sectional; rating *upgrades* also drift −2.4% at 63 days (t≈−2.2, hit rate
  0.31, n=45 — read cautiously); hot/cold growth surprises show no event drift. The
  `dislocation` preset correctly returns INSUFFICIENT_EVENTS until detector history
  accumulates a forward window (D1–D10 rows begin 2026-06-09).
- **Daily portfolio backtests** were already in harness v2 (`backtest_daily`); the harness
  now also scales its coverage gate and top-N proportionally when a sub-universe is
  declared (e.g. the 26-country FX-options universe).
- **Ken French style-spanning** (`scripts/harness/ff_spanning.py`, added 2026-06-17):
  regresses any return series on a regional Fama-French factor model
  (`capm`/`ff3`/`carhart`/`ff5`/`ff5_mom`) and reports the **alpha with a Newey–West HAC
  t-stat**, every factor beta, and R². The complement to IC/Sharpe: a signal whose raw
  Sharpe looks good but whose spanning alpha is insignificant is a known style tilt, not
  new alpha. Country→region via `config/ff_region_map.json` (Brazil→Emerging, Germany→
  Europe, U.S.→US, …). CLI: `python scripts/harness/ff_spanning.py --country Brazil
  --model ff5_mom`; programmatic: `style_spanning(ls_returns, country="Brazil")`. Data is
  the isolated `ff_factors` table (8 FF regions, monthly+daily). Use `subtract_rf=False`
  for a self-financing long-short P&L, `True` for a long-only total return.

MCP tools added to the server: `country_news` (live GDELT DOC 2.0 headlines), `register_hypothesis`,
`evaluate_signal`, `open_thesis`.

Monthly vintage snapshots: `scripts/snapshot_vintages.py` → `Data/vintages/{YYYY_MM}/` (wired into
`monthly_update.py`).

### The graph machine (added 2026-06-12)

The connection-finding layer built after the graph spillover family produced the strongest
results in the first systematic pass. Five new builders (all in the nightly job, steps 24-28):

- **Point-in-time edges** (`scripts/loop/collect_pit_edges.py`, run monthly via
  `monthly_update.py` step 4b): the FULL historical archive of bilateral weights — trade
  (IMF IMTS, 27 annual vintages 1999-2025), banking (BIS LBS, 108 quarterly vintages),
  portfolio holders (IMF PIP, 25 annual vintages) — each applied only after a conservative
  publication lag (trade +4m, bank +4m, holder +9m) → `graph_edge_vintages`. This removed
  the v1 "current-weights" lookahead caveat.
- **PIT graph features** (`build_graph_features_pit.py`): PIT versions of all seven v1
  features plus three new graph algorithms — Katz 3-hop propagation (decay 0.5), PageRank
  hub amplification, spectral trade blocs (k=4) → `graph_features_pit_daily` (GRAPHP_*).
- **Fundamental twins** (`build_similarity_features.py`): each month-end, countries become
  vectors of ~41 normalized fundamental factors (NO return/technical factors); top-5 cosine
  twins applied to the next month → `similarity_features_daily` + `similarity_twins`.
- **Lead-lag network** (`build_leadlag_features.py`): monthly re-estimated lag-1
  cross-correlation network (corr ≥ 0.15, ≥ 150 overlapping days; U.S. complex dominates as
  leader, exactly as timezone mechanics predict) → `leadlag_features_daily` + `leadlag_edges`.
- **Ridge combiner** (`build_combiner.py`): walk-forward ridge (expanding window, January
  refits, 60m burn-in) over the harness survivors → `combiner_scores` (monthly) +
  `combiner_scores_daily` (daily, 6 market-derived features, next-5d target).
- **Neo4j write-back** (`write_graph_discoveries.py`): latest twins → `SIMILAR_TO` edges
  (170), lead-lag → `LEADS` edges (192), combiner ranks → `Country.combiner_score/rank`.

**Scoreboard from the 2026-06-12 registration sweeps** (all charged trials, specs in
`config/sweeps/`): the **PIT re-test validated the whole graph family** — twohop t=4.4,
Katz t=4.25, trade-gap-21d t=4.1, hub t=4.0, bloc t=3.2, and the banking gap at IC 0.034 /
t=4.5 on the 17 stable-coverage countries since 2008 (current-weight vs PIT feature
correlation 0.988: the v1 result was structure, not lookahead). New families:
fundamental twins IC 0.028 / t=5.6; lead-lag 5d gap IC 0.057 / t=8.5 on the 16 structural
follower countries (1d version t=6.4 — both heavily timezone-channel, costs bite at this
turnover, DSR strongly negative everywhere). The **monthly combiner tested DEAD** (IC 0.017,
t=1.1 — month-end sampling throws away the days-to-weeks horizon where the components live);
the **daily combiner is the strongest signal in the ledger: IC 0.057, NW-t 10.7** on the 29
fully-covered countries since 2006 (verdict WEAK only because the deflated Sharpe charges the
whole family's trial count, and because the component list was itself selected in-sample this
month — the honest read is "ceiling, verify forward"). Conditioned event studies: the
downgrade drift is an **EM phenomenon** (EM −0.9%@5d t=−2.0, −2.8%@63d; DM flat) and
splits by regime (high-VIX downgrades hit immediately, low-VIX drift slowly).

### The cost / holding-period model (harness v2.1, 2026-06-12)

The answer to "do any daily signals survive costs?". `evaluate_signal.py` v2.1 adds, for every
daily run: a **hold-period grid** (the same daily ranks re-costed at 1d / 5d / 21d tranched
holds, `hold_period_grid` in the result JSON), a **breakeven cost** (`breakeven_cost_bps_ls` =
the one-way bps at which mean net LS return crosses zero given the strategy's own turnover),
and a **5 bps cost case** (liquid-futures / DM-ETF execution). Verdict gates are unchanged —
still keyed to the registered hold at net-25bps; the grid is a design diagnostic. All 29
verdicted daily hypotheses were re-measured in place (same hypothesis IDs, zero new trials).

**The quantified answer** (`Data/loop/harness_runs/cost_model_summary_2026_06_12.xlsx`):
nothing survives 25 bps one-way — that conclusion stands. But at **10 bps**, 4 signals clear
net LS Sharpe > 0.3: the daily ridge combiner (breakeven 14.2 bps, net Sharpe 0.99 @10bps /
2.15 @5bps at a 1-day hold), the PIT banking-claims neighbor gap (13.1 bps breakeven), and the
fundamental-twins + bank-gap 63d variants (~14 bps). At **5 bps** twelve signals clear the bar.
Two structural findings: the strong daily signals **decay fast** — gross Sharpe falls faster
with longer holds than turnover savings compensate, so 1-day holds win net for the top family
(slower 21d holds only rescue slow signals like SOV_2S10S, breakeven 15.8 bps); and the
implementation channel decides everything — these are futures/cheap-DM-ETF strategies, not
EM-ETF strategies. The graph family's economics: breakevens cluster at 8-14 bps, i.e. real but
thin edges that only an efficient execution stack can monetize.

**Known caveats:** v1 `graph_features_daily` still uses *current* Neo4j edge weights (kept for
continuity; the PIT table is the analytical surface); the headline DSR for daily signals is
still computed at net-25bps on the registered hold — conservative by construction (see the
hold-period grid for the 5/10 bps economics); GDELT DOC API rate-limits aggressively — `country_news` fails loudly and recovers
when the block lifts; D10 peg-currency rows (Hong Kong, Saudi Arabia) carry a peg note because
z-scores off a near-zero vol baseline run hot — read them as peg-risk repricing, not magnitude.
Bloomberg quota usage for the loop's nightly pulls is logged append-only to
`Data/work/loop/bbg_quota_log.csv`.

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
