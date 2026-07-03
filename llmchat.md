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

## Session: Documentation cold-start hardening

### What Happened
- User asked whether the docs are clear enough for a cold Claude Code / Codex pickup.
- Audit found: very close, but three gaps worth fixing:
  1. No single index distinguishing canonical specs, generated reports, and
     historical snapshots in `docs/`.
  2. No explicit "first 5 minutes" checklist in the main README.
  3. Stale-looking top-level docs (`DATABASE_AUDIT_2026_06_09.md`, daily reports,
     morning/eod reports) could be mistaken for current specs.

### Fixes
- Created `docs/README.md` — canonical index with freshness flags:
  - **Start here:** README, CLAUDE.md, AGENTS.md, llmchat.md.
  - **Canonical specs:** PRD_Alpha_Hunting_Loop.md, extension status docs, etc.
  - **Generated reference:** factor_reference.md, VARIABLE_DICTIONARY.md.
  - **Historical snapshots:** all `*_YYYY_MM_DD.md` audit/report files.
- Added "Cold start for a new agent" section to main `README.md` (right under
  Quick start): read order, venv, service checks, smoke tests, loop DB location,
  and the `asado.duckdb` deletion warning.
- This entry and the docs files are committed/pushed.

### Gotchas Learned
- `Data/asado.duckdb` is rebuilt from scratch by `setup_duckdb.py` — never treat
  it as a place for persistent loop tables. Loop persistence is
  `Data/loop/asado_loop.duckdb` + parquet intermediates under `Data/work/loop/`.
- `docs/` mix specs and point-in-time reports; always check the filename date.

### What To Build Next
1. Forward-verify the daily combiner.
2. Per-country execution cost table if the strategy moves from research to
   implementation.
3. D6 predmkt detector still blocked on history accumulation.

---
SESSION END: 2026-06-12 15:55 PDT | Agent: Cursor (Fable 5)
---

---
SESSION START: 2026-06-15 20:00 PDT | Agent: Claude Code (Fable 5, run from the Memory workspace)
---

### Session Summary
Integrated the Jordà-Schularick-Taylor (JST) Macrohistory Database (R6, 1870-2020,
annual, 18 advanced economies) into ASADO as a long-cycle CALIBRATION CORPUS, to
close the once-in-a-century tail / regime-calibration gap (the modern ~2000+ sample
has only ~3 crises). NOTE: this work was done from a Claude Code session whose
working directory is the *Memory* workspace, not ASADO — so it will not appear as
an "ASADO session" anywhere; this llmchat entry is the handoff. All code was
committed to ASADO main (commit 3fd66e8) and pushed.

### Decisions Made
- JST is a CALIBRATION CORPUS, not a factor feed. It is annual and ends 2020. It
  loads into its OWN DuckDB table `jst_macrohistory` and is NEVER unioned into
  `unified_panel`/`feature_panel` and NEVER forward-filled to monthly (the
  deprecated `wb_commodity_factor_panel` mistake). Verified 0 jst rows in
  unified_panel.
- Scope = the 13 JST countries that are in the tradable 34-universe (AU, CA, DK,
  FR, DE, IT, JP, NL, ES, SE, CH, U.K., U.S.). Dropped the 5 JST-only DMs
  (Belgium, Finland, Ireland, Norway, Portugal). 65 banking-crisis onsets — ample.
- Explicit JST->T2 country map (USA -> 'U.S.', NOT the iso3-ambiguous
  'US SmallCap'/'NASDAQ').
- Rule-based regime tagger left UNCHANGED; JST is additive (priors/tail tables).
- A real HMM fit on JST is DEFERRED by decision (corpus makes it estimable later).
- Brief integration is read-only CONTEXT — no overlay on detector severity or
  trade sizing.

### Architecture / Design
- `scripts/collect_jst_macrohistory.py` — static ingest (NOT nightly; R6 is a
  static release; `--refresh-download` re-pulls). Raw xlsx in `Data/raw/jst/`
  (gitignored), tidy annual parquet `Data/processed/jst_macrohistory_panel.parquet`
  (gitignored). Regenerate both with one run of this script.
- `scripts/calibrate_jst_bearbottom.py` — real (CPI-deflated) forward 1/3/5y
  return distributions conditional on drawdown buckets / banking-crisis onset /
  post-crisis. Outputs `regime/calib/jst_bearbottom_conditional_returns.{parquet,json}`
  + `jst_calibration_report.md`.
- `scripts/setup_duckdb.py` — `load_jst_macrohistory()` isolated table loader
  (runs automatically if the panel parquet exists; never in unified_panel).
- `regime/calib/jst_calib.py` — read-only accessor: drawdown -> JST bucket ->
  forward-return distribution. The live layer reads THIS, never the raw 150y panel.
- `scripts/loop/build_dislocations.py` — new `_jst_tail_context_section()` adds a
  "Long-cycle tail context" block to the daily brief: deep-drawdown countries
  annotated with their JST forward-3y real-equity distribution. Current cyclical
  drawdown uses a trailing ~5y peak (not the all-time peak).
- Full design doc: `docs/JST_MACROHISTORY_CALIBRATION.md`.

### What To Build Next
1. Let the JST tail tables actually INFLUENCE sizing/severity (a real behavior
   change — design carefully; currently context-only).
2. The deferred HMM/Markov regime model fit on the 150y JST corpus.
3. (Optional) pooled robustness overlay adding the 5 JST-only DMs if any tail cell
   ever goes thin (none currently — min episodes per crisis cell = 65).

### Constraints & Gotchas
- Re-running the pipeline needs the JST data regenerated: `Data/raw/jst/` and
  `Data/processed/jst_macrohistory_panel.parquet` are gitignored — run
  `venv/bin/python scripts/collect_jst_macrohistory.py` then
  `venv/bin/python scripts/calibrate_jst_bearbottom.py` after a fresh clone.
- Live drawdown in the brief is NOMINAL (no live CPI deflation) and the JST
  distribution is a DM tail reference applied as context even to EM names —
  fine for context, not a trade signal.

### Context for Next Session
Commit 3fd66e8 on main holds all of it. Source: macrohistory.net/database (CC).

---
SESSION END: 2026-06-15 20:30 PDT | Agent: Claude Code (Fable 5)
---

---
SESSION START: 2026-06-16 | Agent: Claude Code (Fable 5)
---

### Session Summary
Did the two "use the JST corpus" items from the readiness review (the JST corpus
landed 2026-06-15, commit 3fd66e8; verified live: jst_macrohistory 83,725 rows
1870-2020, 13 DMs, 0 leak into unified_panel). Plumbing was ready; it was
context-only and applied DM tails to EM names unlabeled, and the brief section
had never rendered in a real brief (latest brief was 06-12, predates JST).

### What Was Built
1. **EM-analogy labeling (item 2).** Added `JST_DM_COUNTRIES` (the 13 in-scope
   DMs = collect_jst_macrohistory.JST_TO_T2.values()) + `is_jst_dm()` to the live
   accessor `regime/calib/jst_calib.py`. `build_dislocations.py::_jst_tail_context_section`
   now tags each deep-drawdown row `DM` vs `EM-analogy`, sorts DMs first. Verified
   render: Denmark=DM leads; Indonesia/ChinaA/ChinaH=EM-analogy.
2. **JST tail-risk report (item 3).** New read-only `scripts/loop/build_jst_risk_report.py`
   → dated `Data/loop/risk_reports/jst_tail_risk_YYYY_MM_DD.{xlsx,pdf}` (filename =
   DATA AS-OF / last returns date, not wall-clock). xlsx: 3 sheets (Country Tail Risk
   all 34 deepest-first w/ fwd1/3/5y real-equity median+p10+p90+P(neg)+n; full
   state×asset×horizon JST grid; Notes/Methodology w/ caveats + banking-crisis ref).
   pdf: light-mode forward-3y tail fan (p10–median–p90), DM blue / EM-analogy orange.
   Wired as nightly loop **step 33** (read-only, final, after calibration_report);
   ran clean via orchestrator `--only`.

### Verified / Caveats
- First real run: as-of 2026-06-12, 34 countries, 4 in >=20% drawdown
  (Indonesia -50%, Denmark -45%, ChinaA -22%, ChinaH -21%). Drawdowns sanity-checked
  (Denmark = Novo Nordisk collapse, real).
- Live drawdown is NOMINAL vs JST REAL; tail cells overlapping-window (n_obs overstates
  N, clean count = 65 banking crises); EM rows are DM-analogy. All baked into the report
  Notes sheet + brief note. Still CONTEXT ONLY — must clear evaluate_signal before it
  influences any trade/severity (the deferred "let it influence sizing" item is untouched).
- Docs synced: nightly job 32 -> 33 steps in README (step list + count), CLAUDE.md (3
  refs), loop_daily_job.py docstring; AGENTS.md got a new JST-usage fact line.

### What To Build Next (unchanged from the readiness review)
1. Let JST tail tables actually influence sizing/severity — register as a harness
   hypothesis (tail prior / drawdown-bucket scaling), not a bolt-on.
2. The deferred HMM/Markov regime fit on the 150y corpus (regime-for-RISK layer).
3. Operational: latest brief on disk is 06-12 — confirm the nightly loop is running
   (Monday 06-15 brief absent); the JST brief section + step 33 will first appear on
   the next successful loop run.

### Not Done (by design)
- No git commit (left for Arjun). Pre-existing uncommitted files untouched
  (.cursor/hooks/state/, brief_2026_06_12.md, thesis_ledger.jsonl, PRD_Triptych_*).

---
SESSION END: 2026-06-16 | Agent: Claude Code (Fable 5)
---

## 2026-06-17 — Ken French style factors + spanning harness

**Goal (Arjun):** "Is Ken French data useful to ASADO? Yes — build the collector
and the hooks to the system knowing what's there and how to use it."

**What was built (all tested end-to-end against live French files):**
- `scripts/collect_ff_factors.py` — downloads 30 FF zips (HEAD-verified manifest),
  parses → `Data/processed/ff_factors_panel.parquet`. FF 5 factors + momentum + RF
  for 8 FF regions, monthly+daily, USD, **percent** units. 539,920 rows; US to
  1926/63, six developed regions to 1990, Emerging monthly-only to 1989 (NO daily
  Emerging file exists — 404). Per-dataset try/except + 24h raw cache + backup.
- Design decision: FF is an **isolated, region-keyed benchmark** — NOT a return
  source, NOT broadcast to the 34 countries, NEVER unioned into unified/feature_panel
  (same rule as JST / deprecated wb_commodity_factor_panel). Country→region join is
  `config/ff_region_map.json`, applied on the fly at regression time.
- `setup_duckdb.load_ff_factors` (isolated table `ff_factors`, mirrors load_jst_macrohistory)
  + main() wiring; confirmed 0 rows leak into unified_panel.
- `monthly_update.py` Stage 1 "Program 5c" + `--skip-ff` flag.
- `scripts/harness/ff_spanning.py` — THE usage hook. Regresses any return series on a
  regional FF model (capm/ff3/carhart/ff5/ff5_mom) → alpha + Newey–West HAC t (Bartlett
  kernel = evaluate_signal.nw_tstat), betas, R². CLI `--country`, programmatic
  `style_spanning()`, `span_country_returns()`. Connects directly to DuckDB (no Neo4j dep).
- `db_bridge.ff_factor_series()` + `ff_region_of()`.
- Schema registry + `docs/factor_reference.md` regenerated (ff_factors auto-documented,
  line 42). README / CLAUDE.md / AGENTS.md updated.

**Validation (real, not simulated):** US country return spans FF US market β≈0.99,
R²≈0.996, α≈0 (t=−1.47) — perfect units/alignment sanity check. Brazil→Emerging
β=1.26 large-cap+value tilt; Germany→Europe β=1.17; Japan flagged UNSPANNED
(t=−5.53, persistent ETF-vs-factor gap). Daily path: US daily Mkt_RF spans US daily
ff5_mom at β=1.0, R²=1.0. `--check`/`--dry-run` verified.

**Live state:** `ff_factors` materialized into `Data/asado.duckdb` directly (idempotent;
next full `setup_duckdb.py` reproduces it). No git commit (left for Arjun).

---
SESSION END: 2026-06-17 | Agent: Claude Code (Opus 4.8 1M)
---

---
SESSION: 2026-06-19 | Agent: Claude Code (Opus 4.8 1M, Desktop)
---

## Two threads this session

### 1. Chief-of-Staff cockpit — Claude Design redesign + live data layer
- **Design brief** for a full Claude Design redesign of the cockpit:
  `cos_mockups/DESIGN_BRIEF.md`. §1 "Selection Intelligence" is the spine (the rules
  that decide WHAT is shown: 3-slot "Today" promotion, detector firing, harness-owned
  verdicts, governance=worst-dimension, intent→view routing). Seed Design with the
  brief + `cos_mockups/cockpit.html` (restyle, don't re-architect).
- **Live data layer (built + verified):**
  - `cos_mockups/build_cockpit_data.py` → reads loop DB + governance JSON + brief +
    thesis ledger + sovereign/valuation tables, applies §1 rules, writes
    `cockpit_data.json` (+ `cockpit_data.js` global). Read-only, per-source try/except,
    atomic write. Pulls per-country fundamentals (10Y/2s10s/CDS/CAPE-ERP pctile).
  - `cos_mockups/test_cockpit_selection.py` → 15 tests, ALL PASS. Locks the §1 rules.
  - `cos_mockups/make_live_cockpit.py` → generates `cockpit_live.html` from the mock,
    wired to real data. Headless-verified (Playwright), zero page errors.
  - Real data corrects the mock: combiner is WEAK (not WATCH); real WATCHes are
    momentum_sanity (diagnostic) + graph_trade_gap; Indonesia DD −33.8% (not −50%).
- **Next:** when Arjun has Claude Design comps, import via Vercel MCP
  `import-claude-design-from-url`, then bind to `window.COCKPIT_DATA` (field names
  already proven by the live prototype).

### 2. Nightly loop FAILURE → RECOVERED (Bloomberg logout)
- Symptom: governance overall RED. Root cause: Bloomberg Terminal was LOGGED OUT in
  Parallels → BLPAPI session couldn't start → all 7 *_bbg/*_bql collectors failed →
  run_manifest + liveness RED. NOT a code bug. No data lost (load_* reused prior parquet).
- Fix (done): Arjun logged into Bloomberg → connection verified (10/10 tickers) →
  re-ran all 7 collectors (`loop_daily_job.py --only <step>`, 7/7 OK) → re-ran 6 loaders
  (all OK) → rebuilt governance: **RED → AMBER** (the lone amber is cross_source_minimal,
  amber_by_design = healthy baseline). Cockpit data refreshed, 15/15 tests green.
- LESSON: when all *_bbg steps fail as a block but non-BBG steps pass, it's the
  Bloomberg login/connection, not code. Recovery = log in, re-run --only collectors +
  loaders, rebuild governance scorecard.

## App/sync note (NOT ASADO data — all data safe on disk)
- iOS app not showing this session. Cause is structural: a TRANSFERRED desktop session
  doesn't sync to iOS; quitting/restarting the desktop app drops live processes (iOS
  mirrors live local processes, not storage). Transcripts intact in
  ~/.claude/projects/-Users-...-ASADO/ (this session = d34fb50b-...jsonl).
- Workaround: resume from CLI (`claude --resume`) — reads on-disk transcript, comes up
  as a clean live process; pair Remote Control from the CLI (not the GUI). Don't quit
  the desktop app on a session you want to keep monitoring.

---
SESSION PAUSE: 2026-06-19 ~20:45 | governance AMBER (healthy), cockpit live data built
---

---
SESSION: 2026-06-20 | Agent: Claude Code (Opus 4.8 1M, Desktop)
---

## Loop hardening — MERGED TO MAIN (df9e6c1)

Triggered by the Friday loop failure. Multi-agent brittleness audit (50 agents,
21 rate-limited) -> docs/LOOP_HARDENING_REPORT_2026_06_20.md (19 confirmed findings).
Implemented + unit-tested + validated by a clean full-loop run (GREEN 7/7, exit 0):

- **cross_source_minimal -> STATUS-DRIVEN** (was hardwired amber-by-design). Green
  when checks pass AND coverage>=90%; amber on partial/pair; red on hard breach.
  Phase-C widens the check set but no longer gates green.
- **CRITICAL**: empty/truncated governance_contract.yaml now forces a RED
  scorecard (contract_degraded dim), was silently greening with zero checks.
- **All loop subprocesses bounded** (new scripts/loop/procutil.run_bounded): hard
  timeout + process-group kill (conda/python/bbcomm can't orphan). Wired into
  loop_daily_job._run_step, daily_update.run_step, gov tail, git calls, predmkt.
- **Dual-loop concurrency flock** (07:30 chained vs 11:30 launchd safety-net).
- **git-silent-green fixed**: _git returns None on failure; config_guard REDS.
- **Atomic writes**: brief prepend (+orphan-marker self-heal, conflicted-copy
  exclusion) and predmkt archive COPY (temp+rename).
- **predmkt**: BY NAME restore (schema-drift safe), _connect_retry on main DB.
- **heartbeat**: json.loads guarded so a corrupt manifest ALERTS, not crashes.
- **loopdb.loop_connection**: classify lock-vs-deterministic, close ATTACH leak.

**DEFERRED (in the report, need sign-off / other repos):** relocate loop DB off
Dropbox (#10), BBG handshake in OpusBloomberg/bbg.py (#11), caffeinate plists
(#17), missing-key + disk-space preflights, LOW items #12/#13.

**Branch claude/nightwatch-06-20-failures-37d4lv fast-forwarded into main via real
merge (-X theirs on regenerable brief artifacts; main-only commits were all
nightly auto-brief noise). Pushed.**

## Cockpit (cos_mockups/) — still UNTRACKED, unaffected
build_cockpit_data.py + cockpit_data.json, test_cockpit_selection.py (15 pass),
cockpit_live.html (real data), DESIGN_BRIEF.md, COCKPIT_DATA_CONTRACT.md. Waiting
on Claude Design comps -> import via Vercel MCP -> bind to window.COCKPIT_DATA.

---
SESSION END: 2026-06-20 | loop hardening merged to main, governance GREEN 7/7
---

---
SESSION START: 2026-06-25 | Agent: Fugu Ultra via Codex
---

## Session Summary
Created top-level `FuguPRD.md` to consolidate the decided ASADO Discovery Triage direction after Fugu/Codex/Opus critiques and the added Mythos-class model assumption.

## What Was Captured
- Current gap engine is the **Known Gap Monitor**, not final ASADO intelligence.
- Product center is **Mythos Discovery Lab**; disbelief is chain of custody.
- Mythos is treated as a quarantined research physicist, not an oracle.
- Model training cutoff is the real PIT boundary for LLM-generated ideas.
- Tool-outcome-blind context is necessary but not sufficient for clean certification.
- Pre-cutoff Mythos ideas route to prospective/post-cutoff evidence, not ordinary historical validation.
- Required components: tool-enforced context builder, research look ledger, model-cutoff provenance classifier, claim freezer, minimal triage battery, blind human ruling, prospective incubator, graveyard control arm, research desk cockpit.
- Optional prosecutors are deferred until the minimal triage workflow has real evidence.

## Files Written
- `FuguPRD.md` — 1,620-line consolidated PRD for ASADO Discovery Triage for Mythos-class models.

## Verification
- Confirmed the file exists at the ASADO repo root and includes the final corrected slogan: "Muse in quarantine. Measurement in code. Judgment under blindfold. Evidence accumulated forward."

---
SESSION END: 2026-06-25 | Agent: Fugu Ultra via Codex
---

---
SESSION START: 2026-07-01 | Agent: Cursor (Fable 5)
---

## Session Summary
Four-part audit requested by Arjun after the Jun-22→Jul-01 changes (gap engine,
discovery triage, live cockpit). All deliverables are docs — no code changed.

## Deliverables
1. `docs/PRD_Update_Pipeline_Correctness_Efficiency_2026_07_01.md` — daily/monthly
   audit + PRD (W1–W12). Highest findings: chained loop killed at 1200s parent
   timeout (observed 06-26); --resume skips by stage NAME only; monthly_update
   ALWAYS exits 0 and has no step timeouts; TRIPLE same-day BBG batch on 07-01
   (05:47/09:33/13:53 in bbg_quota_log.csv — no freshness gate);
   check_source_alignment.py built but wired to nothing.
2. `docs/AUDIT_DATA_STRUCTURES_2026_07_01.md` — verdict: ingestion/isolation
   strong (0 leaks verified live), consumption fragmented. R1–R6: unified PIT
   signal_panel_daily + forward_returns_daily join surface are the missing
   structures; feature_panel has 43 countries (caller-discipline filtering);
   variable registry barely covers loop signals.
3. `docs/AUDIT_FRONTEND_2026_07_01.md` — cockpit problems w/ file:line. Lead:
   tension_score_current is a COPY of tension_score_at_open
   (build_gap_episodes.py:565) so all 5 headline gaps are repriced_against yet
   still headline; "100% unabsorbed" shown alongside repriced_against; Tail +
   Brief views are 100%/partly mock; chat route() recites June mock numbers;
   setHor() dropped by make_live_cockpit (ReferenceError); warehouse-string XSS
   sinks remain; no refresh mechanism.
4. `docs/PRD_Frontend_Alpha_Rethink_2026_07_01.md` — content redesign around
   "what does the data know that price doesn't": Edge Board (live tension, all
   claim surfaces), Consensus Matrix (34 countries × validated families — the
   missing prediction surface), Gap Lifecycle strip, Strategic Desk (monthly
   clock: valuation/revisions/JST), Scoreboard (holdout/calibration/IC-since-
   registration/graveyard), conflict→Discovery-Lab bridge. Backend deltas §4.1–4.7
   (4.1 = fix live tension; 4.2 family_ranks_daily = first slice of R1).

## Verification notes
- Live browser session against 127.0.0.1:8800 confirmed bindings + defects.
- Loop DB queried read-only: 22 open gaps, 21/22 marks repriced_against,
  gap_holdout_daily 533 rows since 06-22, tally 1 WATCH/21 WEAK/16 INSUFF/20 DEAD.
- Schedules read from live LaunchAgents: predmkt 04:30, daily 05:30 wkdays,
  loop standalone 06:45, heartbeat 12:45 — docs say 06:30/07:30, both stale.
- Monthly full run today: all steps OK, 2671s.

## Not done (by design)
- No code fixes applied; no commit (left for Arjun). Recommended first fixes:
  pipeline W1/W2/W3 + front-end audit items 1–3 (live tension, absorption
  display, setHor).

---
SESSION END: 2026-07-01 | Agent: Cursor (Fable 5)
---

---
SESSION START: 2026-07-01 (PM) | Agent: Cursor (Fable 5)
---

## Session: implement the first three audits (pipeline + data structures + frontend)

Arjun: "implement the first three and let's have a discussion about the redesign."
All Phase-1 pipeline items, the frontend priority fixes, and the two small data-
structure items are implemented and verified; the redesign
(PRD_Frontend_Alpha_Rethink_2026_07_01.md) is deliberately untouched pending
discussion.

## Pipeline (PRD_Update_Pipeline_Correctness_Efficiency)
- W1 daily_update.py: chained loop stage now bounded at 7200s.
- W2 daily_update.py: --resume skips only if stage NAME + script sha1/mtime +
  argv all match the checkpoint (stage_fingerprint/resume_match; v1.2).
- W3a monthly_update.py: REAL exit codes — 0 OK / 1 step failed / 2 aborted
  (was: always 0). W3b: every step bounded via run_bounded (default 3600s,
  BBG 5400s, GDELT ingest 7200s); TIMEOUT is a distinct step status. v1.3.
- W6 render_dislocation_brief.py: atomic os.replace write + post-render
  marker self-assert (exactly-one START/END when section expected).
- W8 scripts/qa/check_source_alignment.py v1.1 (canonical Data/work paths;
  future-labeled GDELT month = WARN not FAIL; T2 sheet date-axis diff = WARN)
  wired into BOTH orchestrators as advisory stages — failures print WARN and
  never abort (calibration period).

## Gap engine (audit F1 — the content-correctness lead)
- gap_engine_common.py: new tension_current() — marks re-score tension live
  from open components + current expression/crowding/staleness/data-quality,
  scaled by absorption state; repriced_against hard-capped at 0.30 (below the
  0.35 promotion floor) and further scaled by |absorption_index|.
- build_gap_episodes.py calls it at mark time (tension_score_current was
  previously a COPY of tension_score_at_open). config gap_engine.yaml bumped
  to gap_engine_v2_2026_07_01 with mark_scoring block. 3 new unit tests.
- Verified live re-rank: repriced_against gaps now score ~0.10–0.19 and the
  U.K. unabsorbed gap (89%) headlines instead.

## Frontend (make_live_cockpit.py v1.1 — F2–F7, B2/B3/B5 from the audit)
- F2 absPhrase(): repriced_against never renders "N% unabsorbed" — shows the
  signed absorption index; gap detail view gets a "⚑ Repricing against" callout.
- F3 setHor() restored (was ReferenceError on horizon toggles).
- F4 Brief view: live as-of/row-count + live drawdown footer + brief-file
  pointer; Tail view: live drawdowns, fan labelled "static DM calibration
  shape", honest UNKNOWN/STALE caveat.
- F5 route()/openCountry(): tally from TALLY, pressure leaders from
  country_ranked, tail from live DRAW, "reflation" and "(prototype:
  scripted)" removed.
- F6 esc()/qs() on warehouse-string sinks + quote-safe onclick args.
- F7 neutral ribbon boot HTML; Return* staleness asterisk when returns lag
  gaps >35d; stale-tab poll (5min) shows a reload banner on new generated_ts.
- B3 INSUFF badge; B5 producer-error banner; B2 pluralization/rounding/title.
- Generator now FAILS LOUDLY on anchor drift (REQUIRED/FORBIDDEN token gate)
  + new cos_mockups/test_make_live_cockpit.py (17 tests: every onclick fn
  defined, no mock narration leaks, absPhrase ordering).
- F8 cos_chat_service.py: current_date now wall-clock (was hardcoded
  2026-06-24), data_as_of added, fallback=False on successful Opus answers;
  COCKPIT_DATA_CONTRACT.md v1.1 documents gap_engine + research_desk + error.

## Data structures (audit R3 + R5)
- R3: feature_panel_t2 view (feature_panel ∩ canonical 34; source of truth =
  loopdb.T2_UNIVERSE — country_mapping.json has 43 entries and is NOT the T2
  list). Built by build_normalized_panel.py v1.1 + created in the live DB now
  (3.32M rows/34 countries vs 3.55M/43). Documented default for consumers.
- R5: config/loop_schema_contract.yaml (30 tables, consumer-read columns,
  optional flags for BBG-fed) + scripts/qa/check_loop_schema.py (declared ⊆
  actual; exit 1 drift / 2 optional-missing / 0 ok; status JSON to
  Data/loop/governance/). New nightly step check_loop_schema after
  fold_ledgers; governance_contract.yaml v1.1 registers it (STEPS↔contract
  sync verified; step runs green via --only).

## Verification
- 145 tests pass (tests/loop + all cockpit suites). All touched scripts compile.
- Cockpit payload + page regenerated; live browser check on 127.0.0.1:8800:
  setHor works, feed shows "repriced against · index −0.45" style rows, brief/
  tail/gap views live, router narrations live, fallback honest.
- Chat service restarted under venv; /api/cos/chat deterministic route OK.
- NOTE: governance scorecard is RED on config_guard only — governance_contract
  .yaml edited and uncommitted (honest). Clears on commit.

## Not done (by design)
- The redesign (PRD_Frontend_Alpha_Rethink) — discussion opened with Arjun.
- R1/R2/R4/R6 (signal_panel_daily, forward_returns_daily, registry semantics)
  deferred: they ARE the redesign's backend and should follow that decision.

---
SESSION END: 2026-07-01 (PM) | Agent: Cursor (Fable 5)
---

---
SESSION START: 2026-07-02 00:15 PDT | Agent: Cursor (Fable 5)
---

### Session Summary
Built Frontend Alpha Rethink Phase 2 end-to-end: family_ranks_daily (R1 first
slice) → Consensus Matrix + Edge Board in the cockpit, plus the user-requested
"Fable's Desk" — a nightly NON-DETERMINISTIC claude-fable-5 pass over a
custody-scrubbed DuckDB+Neo4j evidence packet that emits CONJECTURE-tagged
cross-surface connections.

### Decisions Made
- Edge Board (P1) replaces "Today" as default focus view + chat answer of
  record when it has slots; legacy overview kept as fallback.
- Agreement votes count ONLY count_in_agreement families — combiner
  (outcome-trained) and ToT impulse (UNTESTED) render as context columns
  marked "°", never votes. Quintile = ceil(n*0.2) per registered universe.
- Fable output is CONJECTURE, a 4th epistemic tag (legend: "CONJECTURE
  quarantined"); read_fable() force-overwrites any tag in the artifact.
  Evidence packet scrubs combiner/factor_returns/forward-return keys (same
  regex family as C1) and drops packet_family_ranks' combiner column.
- Fable API call uses FORCED TOOL USE (record_connections tool, strict JSON
  schema) — free-form JSON from the model broke on unescaped quotes.
  MAX_OUTPUT_TOKENS 12000, timeout 600s, ≤1 call/night, skips if today's
  artifact exists; ASADO_SKIP_FABLE=1 or no key → exit 2 (optional step).

### Architecture / Design
- config/family_ranks.yaml — 8 families (combiner, leadlag, graph_twohop,
  graph_bank, twins, cpi_rev, etf_contra, tot_impulse) with verdict/IC/
  universe; tot_impulse recomputed in-builder from tot_trade_shares ×
  commodity_panel (z vs 36m, min 24 obs).
- scripts/loop/build_family_ranks.py → loop table family_ranks_daily
  (date, family, country, score, oriented_score, rank, universe_n; rank 1 =
  strongest LONG lean under the REGISTERED direction; <5-country dates drop).
- scripts/loop/build_fable_connections.py → Data/loop/fable/
  connections_YYYY_MM_DD.json + connections_latest.json (+ packet_*.json).
- build_cockpit_data.py v1.1: read_consensus / read_event_triggers /
  read_expiring_theses / build_edge_board / read_fable; map tiles carry
  edge/edge_votes/edge_conflict; payload sections consensus, edge_board, fable.
- make_live_cockpit.py v1.2: FVIEWS.edge/consensus/fable, Edge map layer
  (default when consensus fresh; "Signal" retitled "Lean"), desk tabs gain
  Edge Board/Consensus/Fable's Desk, router intents, chips, parity anchors.
- cos_chat_service.py: edge/consensus/fable views+layer validated; anchored
  nav intents; today-intent → Edge Board; evidence packet adds
  consensus_families/leaders/conflicts, country_family_ranks, edge_board,
  fable_conjectures_UNVALIDATED (system prompt: label it CONJECTURE).
- loop_daily_job.py v1.3 (37 steps): build_family_ranks (required, after
  build_combiner), build_fable_connections (optional, after JST), then
  refresh_cockpit_data + refresh_live_cockpit LAST so the page reflects
  tonight's run. governance_contract v1.2 + loop_schema_contract v1.1 synced.

### Verification
- 216 tests pass (18 new in tests/loop/test_phase2_frontend.py: rank
  orientation, voting exclusions, board selection/dedupe/cap, CONJECTURE
  forcing, scrub, chat intents).
- Live Fable run produced 7 connections (e.g. Netherlands melt-up vs −3.7σ
  inflation miss + dead-last family ranks; Indonesia model-consensus-long vs
  crowded-flow stop) — rendered in browser with falsifiable checks.
- Browser-verified on 127.0.0.1:8800: Edge Board default with governance-RED
  slot ①, matrix with votes/conflicts (10 conflicts), Fable cards, Edge map
  layer default with ▲/▼/✕ glyphs; chat intents return correct ui_actions.

### Constraints & Gotchas
- family_ranks check(): DuckDB reserves "rows" as an alias — use n_rows.
- pydantic + SourceFileLoader: register module in sys.modules BEFORE
  exec_module or UIAction forward refs fail (test _load helper does this).
- Governance stays RED on config_guard until the session's config edits are
  committed (honest, by design).

### What To Build Next
1. PRD Phase 2 remainder: live tension recompute (§4.1), lifecycle strip (P3),
   autopsy stats per gap class (§4.4), P2 conflict → Discovery Lab dossier.
2. Phase 3 (Strategic Desk P4, Scoreboard P5) still undiscussed with Arjun.
3. Consider a family-key → harness-registry-name map so matrix column headers
   can open the single-signal IC view directly.

---
SESSION END: 2026-07-02 00:45 PDT | Agent: Cursor (Fable 5)
---

---
SESSION START: 2026-07-02 01:15 PDT | Agent: Cursor (Fable 5)
Topic: Triptych Prediction Prior Layer — full ingestion (overnight, user-approved PRD)
---

### What Was Done
- Ported the Triptych visual tool's analytics kernel into ASADO
  (scripts/loop/triptych_kernel.py, line-verified vs the tool's core.js):
  Welford expanding z (population var), self-excluded cross-country z,
  linear-interp decile thresholds, PIT expanding-window bucketing
  (36-obs warm-up, insert-before-assign), overlap-adjusted bucket t / Spearman
  IC, bucket-run OLS. is_forbidden_signal() refuses the 1MRet family.
- New nightly step 29b build_triptych_scan.py (after render_dislocation_brief,
  before check_cross_source): DuckDB-fed sweep of all 52 t2_raw factors + 28
  config-declared warehouse variables (config/triptych_scan.yaml) x 34
  countries x 3 norms x 2 return modes x 6 horizons x BOTH threshold modes
  (pit = prior surface w/ PRD 7.3 confidence; full = descriptive, conf
  hard-zeroed). 165,642 rows / 81,582 PIT in ~10 s (ProcessPool, all cores).
  -> loop tables triptych_scan + triptych_review_queue (+ triptych_priors
  view), parquet-first in Data/loop/.
- Review queue (PRD 8): PIT-only gates (n>=60, cur-bucket n>=8, |IC-t|>=2,
  R2>=0.4, decile edge <=2 / >=9, conf>=0.2), per-(country,factor) dedupe,
  cap 25, priority = conf x |IC-t| x R2; Triptych deep links on t2 rows.
- Cockpit: read_triptych in build_cockpit_data (queue + top-3 by_country),
  "Triptych" desk tab + tripRow renderer + chat intent in make_live_cockpit,
  country letter gains "Conditional history" section. cos_chat_service:
  triptych view whitelisted, nav intent (anchored fullmatch), evidence packet
  gains triptych_priors_PIT with a PRIOR-labelling system rule.
- Fable: packet_triptych block (top 12 queue rows, custody-safe keys) +
  "triptych" added to the surfaces enum + system prompt mention.
- MCP: triptych_link / triptych_prior_snapshot(country) / triptych_queue.
- Contracts: governance v1.3 (build_triptych_scan required, 4 expected
  outputs), loop_schema_contract v1.2 (both tables). README nightly list.
- Worktree cleanup (user-approved): salvaged triptych_tool_link.py + workflow
  doc into main, archived the old xlsx-based opportunity scan + full patch in
  docs/salvage/, removed ASADO-Triptych worktree + empty ASADO_worktrees/.

### Verification
- Parity vs the live tool (India/REER PIT hz 12M rel, all history): decile 1,
  bucket n 20, avg fwd +25.5%, hit 100%, IC -0.41, spread -27.3% — all match.
- 20 new tests in tests/loop/test_triptych.py (PIT no-lookahead canaries incl.
  full-sample sensitivity control, core.js parity units, queue gates,
  full-sample conf=0 invariant, chat routing); 183 cockpit+loop tests green.
- loop_daily_job --only build_triptych_scan runs green through the
  orchestrator; browser-verified on 127.0.0.1:8799 (tab renders 25 queue rows,
  Taiwan letter shows 3 priors, route('triptych priors') -> view+message).

### Constraints & Gotchas
- The Triptych app's own slope_r2_scan.py xlsx is FULL-SAMPLE ONLY — never
  ingest it as a prior; the ASADO scan replaces it (PIT computed natively).
- Full-sample rows may NEVER carry confidence (finalize() hard-zeroes; queue
  filters threshold_mode='pit'; cockpit reader re-filters — defense in depth).
- Global-broadcast factors (VIX etc.): cross_var_pct skipped automatically
  (degenerate cross-section detector: per-date std < 1e-12 on >90% of dates).
- triptych_url only on t2_raw factors (the tool serves the T2 workbook).

### What To Build Next
1. Register the strongest scan families in the harness (Copper-z/Taiwan 6M
   rel; REER decile extremes) — NOT done: registration burns family trials,
   Arjun's call.
2. Consider a triptych_priors ablation in the combiner (PRD Phase 6).
3. Warehouse factor list in config/triptych_scan.yaml is a starter 28 —
   prune/extend to taste.

---
SESSION END: 2026-07-02 02:25 PDT | Agent: Cursor (Fable 5)
---

---
SESSION START: 2026-07-02 17:00 PDT | Agent: Cursor (Fable 5)
---

## Triptych queue rule: registered + harness-tested -> DEAD

User approved registering the queue-membership rule (option 1 from the
morning discussion: one hypothesis, the epistemically cleanest).

### What was built
- config/family_registry.yaml v1.1: new canonical family `triptych_prior`
  (prefix TRIPTYCH_) — trust-root edit, deliberate classification.
- scripts/loop/build_triptych_signal.py: walk-forward reconstruction of the
  review-queue rule. At each month T since 2004: records restricted to
  completed forward windows (record date <= T-h), running PIT thresholds
  (insert-then-assign, kernel-identical), current signal = latest factor obs
  <= T-1 (one-month availability embargo; factor labels are as-labeled, not
  as-published), live queue gates verbatim from config/triptych_scan.yaml,
  per-(country,factor) dedupe; country value = sum(direction x confidence).
  Global cap 25 deliberately NOT applied (review-workload device, pre-declared
  deviation). -> loop table triptych_signal_monthly
  (TRIPTYCH_QUEUE_LEAN + TRIPTYCH_QUEUE_N), parquet-first. ~2 min, 14 cores.
- No-lookahead canary: --truncate-input 2020-12 vs full run — overlapping
  values bit-identical (max abs diff 0.0).

### The verdict (FAIL IS FAIL)
- H_20260702_001, family triptych_prior, trial 1, primary horizon 1m,
  publication_lag_months=0 (spine is end-of-month market data; factor
  freshness embargoed inside the builder).
- DEAD. 1m mean IC -0.0034 (NW-t -0.24), 3m -0.0087 (-0.42), 6m -0.0039
  (-0.15); gross LS Sharpe -0.26; negative in 3 of 4 subperiods; 221 months,
  full 34-country coverage; breakeven cost negative.
- Reading: decile-conditional history extremes, aggregated exactly the way
  the live queue selects them, carry NO cross-sectional next-month edge
  2008-2026. The conditional histories are real descriptions of the past but
  do not generalize out-of-window at the aggregate-rule level.

### Consequences
- Triptych priors remain CONTEXT/PRIOR-tier everywhere (cockpit letter, Fable
  packet PRIOR label, MCP) — correct as built; nothing to demote.
- Do NOT add the lean to the combiner. Any re-test variant (different gates,
  confidence-weighted subset, single-family rules) = NEW trial charged to
  family triptych_prior.
- Ledger: hyp_register + hyp_verdict appended; result JSON in
  Data/loop/harness_runs/H_20260702_001_20260702_170758.json.

---
SESSION END: 2026-07-02 17:20 PDT | Agent: Cursor (Fable 5)
---
