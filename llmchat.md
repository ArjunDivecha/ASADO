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
