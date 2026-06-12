# llmchat.md - Project Context Log

This file is the shared memory between project sessions and agents.
It is append-only. Do not edit existing entries unless explicitly asked.
Each session appends a timestamped block at the bottom.

---

---
SESSION START: 2026-05-14 11:54 PDT | Agent: Codex
---

### Session Summary
Created the initial ASADO `llmchat.md` context log and seeded it with a detailed cross-session handoff. This entry consolidates the current repo instructions, live repo docs, and prior Codex memory for ASADO so future agents can start from the actual project state instead of rediscovering the stack.

### Decisions Made
- `llmchat.md` now lives at the ASADO repo root: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/llmchat.md`.
- Treat this file as append-only shared context for Codex/Claude handoff; do not rewrite old entries unless Arjun explicitly asks for cleanup.
- The current repo state has unrelated existing changes: `.cursor/hooks/state/continual-learning-index.json`, `AGENTS.md`, and untracked `PRD_Stage3_Tracked_Handle_Social_Events.md`. Do not sweep those into commits unless Arjun asks.
- ASADO answers and future implementation should stay grounded in the return surfaces. Country and factor returns are the analytical source of truth; explanatory layers are valuable because they help explain or anticipate those outcomes.

### Architecture / Design
ASADO is a hybrid country-data, factor, graph, and event research platform for the 34-country T2 universe. The core split is deliberate: DuckDB is the heavy analytical/time-series warehouse, Neo4j is the compact semantic/network/latest-snapshot graph layer, and `scripts/db_bridge.py` is the unified query bridge. Do not replace DuckDB time-series queries with Neo4j graph patterns.

Repo root: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO`. Canonical upstream T2 inputs are outside this repo at `/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/Normalized_T2_MasterCSV.csv` and `/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 Factor Timing Fuzzy/T2 Master.xlsx`. GDELT prefers `/Users/arjundivecha/Dropbox/AAA Backup/A Complete/T2 GDELT/GDELT_Factors_MasterCSV.csv` when present and otherwise uses the repo-local `Data/processed/gdelt_panel_snapshot.parquet`.

Monthly pipeline: `python scripts/monthly_update.py` from the repo root. It runs collectors, DuckDB rebuild, normalized/feature layer rebuild, daily panels, prediction-market panels, event log, Neo4j, embeddings, and schema registry. It is intended to be rerunnable on a recurring schedule with source-level merge, 24h cache, timestamped backups, and run-history metadata.

Collectors and loaders:
- `collect_external.py`: core free sources including EPU, GPR, BIS, OECD, World Bank, BIS REER.
- `collect_extended.py`: extended macro/risk sources including BIS rates, OECD BCI/CCI, ECB, ILOSTAT, FRED, EIA, sanctions, FAOSTAT, UNDP.
- `collect_imf.py`: IMF SDMX 3.0 at `api.imf.org`; no IMF API key. Do not use the defunct `dataservices.imf.org`.
- `collect_bilateral.py`: bilateral trade, banking, and portfolio ownership matrices.
- `collect_macrostructure.py`: fragility, sticky-capital, central-bank footprint, and backstop variables.
- `collect_bloomberg.py`: Bloomberg Terminal ingestion through the user's OpusBloomberg path, not a substitute Bloomberg setup.
- `setup_duckdb.py`, `build_normalized_panel.py`, `setup_neo4j.py`, `build_embeddings.py`, `build_schema_registry.py`: rebuild warehouse, features, graph, vector index, and query-assistant cache.

Bloomberg integration is Mac Python -> TCP:8194 -> Parallels Windows 11 VM -> `bbcomm.exe` -> Bloomberg Terminal, using `/Users/arjundivecha/Dropbox/AAA Backup/A Working/OpusBloomberg`. `collect_bloomberg.py` has multi-phase coverage for bonds, CDS, breakevens, OIS, WIRP, ECFC/EHGD consensus, PMI, M2, derived spreads/default probabilities, and passive/ETF flow signals. Important ticker quirks: ECFC tries `ECGD[CC]` then `EHGD[CC]Y`, Switzerland is `ECGDSW` not `ECGDCH`, PMI uses `MPMI[CC]MA/SA`, Japan uses `JA` not `JN`, and M2 has multiple candidate tickers per country.

Daily extension is implemented by `scripts/build_daily_panels.py` and documented in `docs/DAILY_EXTENSION_STATUS.md`. It adds daily T2 factors/levels, GDELT factors/raw daily, daily factor returns, variable metadata, and a daily trading calendar. MCP tools `event_window` and `daily_factor_series` expose daily event-study and series extraction. Neo4j `Factor` nodes are enriched from `factor_returns_daily` with 30d/252d performance, Sharpe, volatility, max drawdown, cumulative return, source, and optimizer-selected flags.

Prediction-market Stage 2 is implemented by `scripts/build_predmkt_panel.py` from `config/predmkt_curated.yaml` and documented in `docs/PREDMKT_EXTENSION_STATUS.md`. DuckDB tables include `predmkt_daily`, `predmkt_market_meta`, `predmkt_outcome_meta`, `predmkt_country_spillover`, `predmkt_resolutions`, and `predmkt_signals_daily`. MCP exposes `predmkt_snapshot`, `country_signal_now`, and `event_market_set`. Current caveat: Kalshi requests returned HTTP 401 in local runs, so current composites mostly reflect available Polymarket coverage.

Returns-first PRD is drafted in `PRD_Returns_First_Source_Of_Truth.md`. It says most ASADO answers should route through returns: country returns, factor returns, attribution, and event-window return evidence first; explanatory surfaces second. Canonical return surfaces are monthly country returns in `feature_panel`/`unified_panel` with T2 source variables (`1MRet`, `3MRet`, `6MRet`, `9MRet`, `12MRet`), daily country returns in `t2_factors_daily`, monthly factor portfolio returns in `factor_returns`, daily factor portfolio returns in `factor_returns_daily`, bucket membership in `factor_top20_membership`, and country contribution in `country_factor_attribution`. Do not union optimizer outputs back into `feature_panel` or `unified_panel`; that creates a modeling cycle.

Natural-language/query layer: schema cache and access-guide artifacts live under `Data/cache/query_assistant/`. `build_schema_registry.py` refreshes them. For temp worktrees, use `ASADO_BASE_DIR` to point cache generation at the canonical workspace root. Earlier ASADO validation found the SQL planner must handle multi-CTE `WITH` clauses and expose exact low-cardinality categorical values for tables like `bilateral_portfolio_matrix` so the planner does not guess invalid labels.

Monthly-update UI/operator surface: a prior session wrote a desktop-first PRD, then integrated an actual Streamlit tab plus FastAPI/SSE backend. The live UI model is stage-by-stage operator control, not a generic dashboard: preflight, collectors, DuckDB rebuild, Neo4j rebuild, embeddings rebuild, final validation, per-stage details, live logs, run summary, and run history. The Streamlit app embeds `frontend/monthly_update.html`, and `scripts/update_server.py` launches `scripts/monthly_update.py`; the path fix was `BASE_DIR = Path(__file__).resolve().parent.parent`. Required deps added to the repo venv were `fastapi`, `uvicorn`, and `sse-starlette`.

Macrostructure implementation history: the Phase 3 central-bank footprint layer was implemented in an isolated worktree/branch, then merged/published to `main` as commit `cb17276` (`Add central-bank macrostructure footprint layer`). The durable source fallback path used IMF/WEO/QPSD/PIP/FSIC rather than stalling on unavailable Bloomberg coverage. The layer added `MS_CentralBank_BalanceSheet_GDP`, `MS_CentralBank_Claims_on_Government_Pct_GDP`, and `MS_CentralBank_SovDebt_Share`. Post-rebuild sanity counts from that run: `macrostructure_factors` 75,120 rows / 26 variables; `unified_panel` 2,561,094 raw rows / 421 variables; `normalized_panel` 778,984 rows / 285 generated variables; `feature_panel` 3,340,078 rows / 706 variables; Neo4j 421 factor nodes and 12,359 `HAS_FACTOR_EXPOSURE` edges; `countryStateIndex` recreated and online.

Monthly-update live-run history: a real full update successfully ran external, extended, IMF, bilateral trade/banking, DuckDB rebuild, and Neo4j rebuild. Bloomberg failed because Bloomberg returned `LIMIT` / `WORKFLOW_REVIEW_NEEDED`, an upstream Bloomberg workflow/entitlement blocker rather than an ASADO code/config bug. Embeddings initially failed due to `inf` / `-inf` values in commodity cross-sectional columns such as `Oil_CS`, `Gold_CS`, and `Copper_CS`; the durable fix was to convert infinities to `NaN` before coverage filtering and validate finite values before `StandardScaler`.

Regime-knowledge branch history: a later research sprint created an isolated `Regime` worktree/branch for EF/HMM regime clustering and a go/no-go evaluation. It wired branch-local outputs such as `regime_country_returns_daily`, `regime_ef_coefficients_monthly`, `regime_global_assignments_monthly`, `regime_country_hmm_states_monthly`, and `regime_country_composite_monthly`, and added `monthly_update.py --regime-only` / `--skip-regime-knowledge` in that branch. The branch failed as a direct next-month alpha forecaster: global stress probability AUC for next-month negative equal-weight return was below random (`0.4638-0.4693`) and country risk had slightly positive correlation with next-month return (`~0.043-0.044`). The useful surviving signal is descriptive/risk-oriented: same-month stress classification, next-month volatility/drawdown, rebound behavior inside constructive global regimes, and possible regime-conditioned factor timing. Keep this unmerged unless a future empirical sprint changes the evidence.

Earlier KG/Obsidian discussion: ASADO should not import generic RDF/triple-store optimization ideas just because they sound sophisticated. DuckDB already serves the large analytical store; Neo4j has compact relationships, uniqueness constraints, `HAS_FACTOR_EXPOSURE`, and `countryStateIndex`. Obsidian was discussed only as a human research/synthesis layer for country dossiers, research memos, query cookbooks, and decision logs. It was not implemented and is not a source of truth.

### What To Build Next
1. Implement the returns-first PRD: deterministic MCP tools for country returns, factor returns, factor return series, attribution, and event return summaries; planner rules that route performance/event/leader-laggard questions through return surfaces; and smoke tests that prove the routing.
2. Keep prediction-market Stage 2 healthy: resolve Kalshi auth/401 if Kalshi coverage matters, expand curated markets carefully, and preserve the sign convention that `predmkt_country_risk_composite > 0` means downside risk while `predmkt_country_opportunity_composite > 0` means upside.
3. For any future regime work, test regime-conditioned factor timing rather than direct country-return forecasting. Treat the old Regime branch as evidence and artifact inventory, not merge-ready code.
4. Run future monthly updates with explicit stage outcomes. Use `--skip-bloomberg` when Bloomberg Terminal/workflow is unavailable; do not confuse a healthy Bloomberg transport connection with available request entitlement.
5. Keep schema/query-assistant cache fresh after structural table changes with `python scripts/build_schema_registry.py --duck-only`, and use `ASADO_BASE_DIR` when operating from a temp worktree.

### Constraints & Gotchas
- Use the repo venv for ASADO checks. For Streamlit UI verification, run `./venv/bin/python -m streamlit run frontend/app.py ...`; the ambient `streamlit` binary previously loaded the wrong environment and failed on `duckdb`.
- Bare `python` may not be reliable on PATH in this workspace. Prefer `./venv/bin/python` or activate `venv`.
- Start Neo4j before graph work with `brew services start neo4j`; Neo4j endpoint is `bolt://localhost:7687`.
- Keep ASADO code, data outputs, and artifacts under the ASADO workspace root unless Arjun explicitly directs otherwise.
- Do not commit `.cursor/hooks/state/` files such as `continual-learning-index.json` unless Arjun explicitly asks.
- For implementation plans in this repo, do not edit the attached plan file unless asked; use existing to-dos and build from them.
- FRED and EIA credentials are expected in the project `.env`; use `oprun`/`opinject` for commands that may need credentials.
- IMF uses `api.imf.org` SDMX 3.0 and no API key. Treat old IMF endpoint examples as stale.
- Bloomberg ingestion must use the configured OpusBloomberg path and Parallels/Terminal route. Do not substitute a generic BLPAPI connectivity plan.
- When using isolated worktrees, do not regenerate schema-cache files into the temp tree by accident; point back to canonical ASADO with `ASADO_BASE_DIR`.
- Do not overclaim "done" for UI or web links unless the rendered page/browser flow was actually checked.

### Open Questions
- Has the returns-first PRD been implemented after the 2026-05-12 draft, or is it still pending?
- Is the Kalshi 401 a missing credential/session issue, a changed endpoint requirement, or an intentional no-Kalshi local state?
- Has Bloomberg `WORKFLOW_REVIEW_NEEDED` been cleared upstream since the prior full monthly update?
- Should the Regime worktree remain archived as an experimental branch, or should selected docs/artifacts be copied into main without code?
- Should Obsidian remain purely optional/human-facing, or does Arjun now want a real repo-managed note/synthesis layer?

### Context for Next Session
Read this file first, then read `AGENTS.md`, `README.md`, `docs/DAILY_EXTENSION_STATUS.md`, `docs/PREDMKT_EXTENSION_STATUS.md`, and `PRD_Returns_First_Source_Of_Truth.md` if the next task touches query behavior, data refresh, daily/event tooling, prediction markets, or returns. For repo-specific commands, prefer `./venv/bin/python` and verify behavior end to end before saying it is done. Current session only created this context log; no pipeline, DB rebuild, browser UI flow, or git commit was performed.

---
SESSION END: 2026-05-14 11:54 PDT | Agent: Codex
---

---
SESSION START: 2026-05-16 23:56 PDT | Agent: Codex
---

### Session Summary
Implemented the World Bank Commodity Price Intelligence layer, wired it into the ASADO update/query surfaces, restored additive daily/prediction/event tables after a commodity-only rebuild, updated the operational docs and data dictionary to match the live warehouse, and pushed the changes to `main`.

### Decisions Made
- The official World Bank Commodity Markets Pink Sheet workbook is the canonical commodity source. Kaggle remains only a research lead, not an upstream dependency.
- Commodity variables are explanatory context, not outcomes. For questions such as oil/copper impact by country, use commodity context together with the returns source-of-truth surfaces before making performance claims.
- The daily/monthly updater now includes World Bank commodity collection by default, with explicit controls to skip or run commodity-only refreshes.
- `feature_panel`/schema catalog counts should be labeled as the query-facing catalog, not as raw `unified_panel` variable counts.

### Architecture / Design
New commodity collector and processed outputs:
- `scripts/collect_wb_commodity_prices.py`
- `Data/processed/wb_commodity_prices.parquet`
- `Data/processed/wb_commodity_indices.parquet`
- `Data/processed/wb_commodity_features.parquet`
- `Data/processed/wb_commodity_factor_panel.parquet`
- `Data/processed/wb_commodity_variable_catalog.csv`
- `Data/processed/wb_commodity_manifest.json`

DuckDB commodity tables:
- `wb_commodity_prices`: 50,099 rows, 71 price series, 1960-01-01 to 2026-04-01
- `wb_commodity_indices`: 12,736 rows, 16 index series, 1960-01-01 to 2026-04-01
- `wb_commodity_features`: 435,618 rows, trailing features (`level`, `mom_pct`, `yoy_pct`, `ret_3m_pct`, `ret_12m_pct`, `vol_12m`, `z_36m`)
- `wb_commodity_meta`: 87 metadata rows
- `wb_commodity_factor_panel`: 9,600,274 rows, 371 selected global-broadcast variables aligned to the 34-country ASADO factor-panel shape with `source='wb_commodity'`

Updater/query integration:
- `scripts/monthly_update.py` supports `--skip-wb-commodity` and `--commodity-only`.
- `scripts/setup_duckdb.py`, `scripts/build_normalized_panel.py`, `scripts/build_schema_registry.py`, and `scripts/build_factor_reference.py` now account for commodity surfaces.
- MCP/query layer includes `commodity_price_series` and return-oriented tools (`country_returns`, `factor_return_series`, `return_leaders`, etc.) so MCP answers can bring explanatory commodity data back to country/factor returns.
- `scripts/build_factor_reference.py` now labels the generated count as distinct variables in the `feature_panel` catalog rather than “unified_panel.”

Restored live DB after commodity rebuild:
- `build_predmkt_panel.py --stats`
- `build_event_log.py --stats`
- `build_schema_registry.py --duck-only`
- `build_factor_reference.py`

Live DuckDB verification after restore:
- 36 DuckDB tables/views
- `unified_panel`: 17,392,079 rows, 2,022 distinct variables
- `feature_panel`: 31,584,702 rows
- `normalized_panel`: 14,192,623 rows
- `t2_master`: 1,192,584 rows
- `gdelt_panel`: 5,622,818 rows
- `factor_returns_daily`: 1,293,492 rows
- `variable_meta`: 654 rows
- `predmkt_daily`: 30 rows, snapshot date 2026-05-17
- `predmkt_signals_daily`: 42 rows, 14 signal names
- `event_log`: 146 rows, 1997-07-02 to 2026-05-01

Docs updated:
- `README.md`
- `DATA_DICTIONARY.md`
- `CLAUDE.md`
- `CLAUDE_CODE_BRIEF.md`
- `docs/DAILY_EXTENSION_STATUS.md`
- `docs/PREDMKT_EXTENSION_STATUS.md`
- `docs/LOCAL_CLAUDE_MCP_SETUP.md`
- `docs/factor_reference.md`
- `docs/gdelt_deep_ingest_plan.md`
- `docs/WB_COMMODITY_EXTENSION_STATUS.md`

### Context for Next Session
Recent commits on `main`:
- `d47933e Add World Bank commodity intelligence pipeline`
- `330aea0 Add social events PRD and ASADO context log`
- `37a131c Update ASADO warehouse docs`

Current uncommitted files after the final push are pre-existing/local-state items and were intentionally left out of the docs commit:
- `.cursor/hooks/state/continual-learning-index.json`
- `AGENTS.md`

Important gotcha: `setup_duckdb.py` recreates `Data/asado.duckdb`. Any narrow updater path that calls it, including commodity/db-only work, must restore additive daily/event/prediction tables afterward or run the full daily/prediction/event rebuild chain before reporting a complete live warehouse.

---
SESSION END: 2026-05-16 23:56 PDT | Agent: Codex
---

---
SESSION START: 2026-06-12 08:55 PDT | Agent: Cursor (Fable 5)
---

### Session Summary
Catch-up entry: the last llmchat block (2026-05-16) predates the entire **Alpha-Hunting
Loop** era. Everything below is the state of play as of 2026-06-12 so Claude Code / Codex
can start cold. Latest commit: `95384d4` (six new Bloomberg data layers).

### Decisions Made
- **Alpha-Hunting Loop built (June 2026, `PRD_Alpha_Hunting_Loop.md`):** daily dislocation
  engine on top of the warehouse. Detectors D1–D10 find subsystem disagreements →
  `dislocation_daily` + nightly brief `Data/dislocations/brief_YYYY_MM_DD.md`; hypotheses/
  theses live in append-only JSONL ledgers (`ledgers/`, git-tracked); skeptic harness
  `scripts/harness/evaluate_signal.py` (PIT embargo, NW-t, deflated Sharpe) gates promotion.
- **Loop DB is separate:** `Data/loop/asado_loop.duckdb`. `setup_duckdb.py` DELETES and
  recreates the main `Data/asado.duckdb` — never put persistent tables there.
- **Bloomberg collectors use the conda/venv split:** `scripts/loop/collect_*_bbg.py` run
  under the OpusBloomberg conda env (absolute conda path — launchd PATH has no
  /opt/homebrew/bin) and write parquet only; paired `load_*.py` run in the project venv.
- **2026-06-11: monthly Bloomberg ticker map fully re-audited** (Saudi `GSAB*` was South
  African data for years; many dead EM generics → `GT[CCY]*Y Govt` + `YLD_YTM_MID`).
  T2 "10Yr Bond" sheet USD-override bug also fixed. See `docs/USER_FIX_LIST.md` (all done).
- **2026-06-12 (commit `95384d4`): six new Bloomberg layers** mined from the rebuilt
  bloomberg-skill: (1) FX vol 1W/3M tenors + 25Δ butterflies + vol term slope;
  (2) 1Y CDS → CDS curve slope (inversion = imminent-distress); (3) daily 2s10s;
  (4) **BQL historical sovereign ratings** — first BQL collector, `issuerof()` on CDS-contract
  anchors, S&P/Moody's/Fitch monthly 2015+, 33 countries, `sov_rating_changes` event table;
  (5) 3M forward/NDF-implied carry (PX_LAST on `[ROOT]3M Curncy` is the OUTRIGHT);
  (6) economic surprise layer (ACTUAL_RELEASE vs BN_SURVEY_MEDIAN, CPI/UNEMP/GDP/PMI,
  growth+inflation surprise composites). Full doc: `docs/BBG_SKILL_ENHANCEMENTS_2026_06_12.md`.

### Architecture / Design
- Nightly cadence: predmkt launchd 06:30 → `daily_update.py` (~07:30, T2+GDELT+daily panels,
  chains the loop as its final stage) → loop launchd safety net 11:30. Loop job =
  `scripts/loop/loop_daily_job.py`, **27 steps** (README "Nightly job" has the list).
- Loop data layers live: foreign flows, sovereign daily (CDS 5Y/1Y, yields 10Y/2Y →
  `sovereign_signals`), valuation, WEO vintages, ETF flows/short interest, ECFC consensus,
  COT, market-implied stress (`market_implied_signals`), sov ratings, eco surprises,
  graph features, prediction markets (152 curated markets).
- Returns are the outcome source of truth: `country_returns_monthly` for marking;
  `1MRet`-style variables are FORWARD optimizer targets — hard-blacklisted as signals.

### What To Build Next
1. D6 (predmkt detector) stays blocked until prediction-market history accumulates.
2. Run new signals (carry z, CDS slope, rating changes, surprise composites) through the
   harness as registered hypotheses — none have been formally evaluated yet.
3. Watch today's 11:30 loop safety-net run: Thursday's run failed on bare `conda` (fixed
   14:39 Thu in `ecf1da7` + plist PATH; launchd confirmed reloaded). NightWatch's Fri-morning
   FAIL was that stale Thursday log; Friday-morning chained loop ran all 27 steps clean.

### Constraints & Gotchas
- FAIL IS FAIL: no silent fallbacks; collectors abort on unit-error-scale bad prints.
- Exact T2 country names; first-of-month dates for monthly panels; tidy long format.
- BQL needs raw blpapi + `clientContext.appName="EXCEL"`; response messageType IS `result`.
- AGENTS.md carries the densest operational gotchas (ticker quirks, dead tickers, API
  endpoints); the bloomberg-skill `references/` (lessons.md, proven-tickers.md) is the
  cross-repo ticker knowledge base — both were updated through 2026-06-12.
- Heavy data dirs are gitignored (`T2 Daily Update/`, `Data/loop/`); ledgers + briefs ARE
  committed. `.cursor/hooks/state/` stays out of commits.

### Context for Next Session
Recent commits: `95384d4` six Bloomberg layers; `ad93459` T2 10Y bond fix; `5490378`
market-implied layer + D10; `4b99853` ticker-map re-audit + predmkt expansion; `ecf1da7`
overnight reliability + loop P7–P11 collectors. Docs refreshed today: CLAUDE.md (now has a
loop section + key-files rows), README (27-step job list), AGENTS.md, this file.

---
SESSION END: 2026-06-12 08:57 PDT | Agent: Cursor (Fable 5)
---

---
SESSION START: 2026-06-12 13:30 PDT | Agent: Cursor (Fable 5)
---

## Session: The Graph Machine — PIT edges, new graph surfaces, the combiner

### What Happened
Arjun asked how much of Neo4j's power we were actually using (answer: ~25% — three edge
types feeding seven features, current-weights only), then said "build ALL" of the
enhancements. Built in one session, everything registered through the harness:

1. **PIT edge vintages** (`scripts/loop/collect_pit_edges.py`, monthly_update step 4b):
   trade 27 annual vintages 1999-2025 (IMF IMTS returns all years; the old collector kept
   only the latest), bank 108 quarterly vintages (BIS LBS startPeriod=1999), holder 25
   annual vintages (warehouse imf_pip). Publication lags +4m/+4m/+9m → `graph_edge_vintages`.
2. **PIT graph features** (`build_graph_features_pit.py` → `graph_features_pit_daily`,
   GRAPHP_*): PIT versions of all v1 features + Katz 3-hop, PageRank hub gap, spectral
   trade-bloc gap.
3. **Fundamental twins** (`build_similarity_features.py`): top-5 cosine twins from ~41
   month-end fundamental _CS factors → `similarity_features_daily` + `similarity_twins`.
4. **Lead-lag network** (`build_leadlag_features.py`): monthly lag-1 cross-corr edges
   (≥0.15) → `leadlag_features_daily` + `leadlag_edges`. U.S. complex dominates as leader.
5. **Ridge combiner** (`build_combiner.py`): walk-forward (Jan refits, 60m burn-in).
   Monthly version DEAD. Daily version (6 market-derived survivors, next-5d target) is the
   strongest signal in the ledger.
6. **Neo4j write-back** (`write_graph_discoveries.py`): SIMILAR_TO (170) + LEADS (192)
   edges + Country.combiner_score/rank now live in the graph.
Nightly loop job: 27 → 32 steps (v1.2). All five builders wired in after load_eco_surprise.

### Scoreboard (all registered trials, specs in config/sweeps/)
- **PIT re-test validated the graph family**: twohop t=4.4, Katz 4.25, trade-21d 4.1,
  hub 4.0, bloc 3.2, bank gap ic 0.034 t=4.5 (17 stable countries, 2008+). PIT-vs-current
  corr 0.988 — v1's result was structure, not lookahead.
- **Lead-lag**: 5d gap ic 0.057 t=8.5 (16 structural followers). Timezone channel is real
  but turnover is brutal; DSR negative.
- **Fundamental twins**: ic 0.028 t=5.6. Brand-new surface, second-strongest single family.
- **Daily combiner: ic 0.057, NW-t 10.7** (29 countries, 2006+) — WEAK verdict only via
  family DSR charging; explicitly labeled a CEILING (components selected in-sample this
  month). Monthly combiner DEAD (month-end sampling discards the days-to-weeks horizon).
- ETF flow contrarian flip registered + confirmed (t=−2.2). Downgrade drift is an EM
  phenomenon (EM −2.8%@63d, DM flat); crisis-history edges useless for conditioning
  (all countries share the same 9-11 global crises).

### Gotchas Learned
- `infer_publication_lag` gives monthly non-whitelisted sources a 1-month lag — the
  combiner first tested DEAD-stale until `publication_lag_months: 0` was set in the spec.
- Sweep dedupe hash excludes start_date/universe; coverage re-specs need new name + --force.
- Some t2 `_CS` values are ±inf — replace before cosine norms (`NaN <= 0` is False!).
- BIS reporter coverage GROWS (9 countries 2000 → 21 by 2017): bank-gap universes must be
  declared on the 17 stable reporters from 2008.

### What To Build Next
1. Watch the daily combiner forward — it's the live prediction surface
   (`combiner_scores_daily`, Korea ranked #1 at build time).
2. Cost model for daily harness mode (every daily DSR is negative at assumed costs;
   the binding question is netting/holding-period design, e.g. 5d tranches).
3. D6 predmkt detector still blocked on history accumulation.

---
SESSION END: 2026-06-12 13:35 PDT | Agent: Cursor (Fable 5)
---

## Session: Cost / Holding-Period Model (harness v2.1) — the net-of-cost answer

### What Happened
- `scripts/harness/evaluate_signal.py` → v2.1. Three additions, all diagnostic
  (verdict gates unchanged, still net-25bps at the registered hold):
  1. `hold_period_grid`: every daily run re-costs the SAME ranks at 1d/5d/21d
     tranched holds (compact per-hold summary in the result JSON).
  2. `breakeven_cost_bps_ls`: one-way bps where mean net LS return crosses zero,
     given the strategy's own turnover (monthly + daily).
  3. 5 bps cost case added (liquid futures / DM ETF execution leg).
- All 29 verdicted daily hypotheses re-measured IN PLACE: `evaluate_signal` called
  directly with the existing hypothesis_id + the stored run params from each result
  JSON. Re-verdict events append to the ledger; fold keeps latest; ZERO new
  registrations, so family trial counts (and DSR penalties) are untouched.
  IMPORTANT: `sweep_signals.py --force` is NOT the tool for this — it registers a
  brand-new hypothesis (a new charged trial). One duplicate (H_20260612_055,
  leadlag) was created learning that; it's harmless (conservative) but don't repeat.

### The Answer (Data/loop/harness_runs/cost_model_summary_2026_06_12.xlsx)
- At 25 bps one-way: NOTHING survives. The earlier conclusion stands.
- At 10 bps: 4 signals clear net LS Sharpe > 0.3 — daily ridge combiner
  (breakeven 14.2 bps, net Sharpe 0.99 @10 / 2.15 @5, 1d hold), GRAPHP bank
  neighbor gap (13.1), SIM twins 63d (14.1), GRAPH bank 63d (13.7).
- At 5 bps: 12 of 30 signals clear.
- Structural: the strong daily signals DECAY FAST — gross Sharpe falls faster with
  hold length than turnover savings compensate, so 1-day holds win net for the top
  family. Slow holds (21d) only rescue slow signals (SOV_2S10S breakeven 15.8 bps).
- Implication: graph-family edges are real but thin (breakevens 8–14 bps one-way).
  This is a futures / cheap-DM-ETF implementation, not an EM-ETF one.

### What To Build Next
1. Forward-verify the daily combiner (live surface `combiner_scores_daily`).
2. If implementation gets serious: per-country cost table (DM futures ~2-5 bps vs
   EM ETF 15-40 bps) instead of flat cases — the harness takes cost cases as a
   parameter already.
3. D6 predmkt detector still blocked on history accumulation.

---
SESSION END: 2026-06-12 14:15 PDT | Agent: Cursor (Fable 5)
---
