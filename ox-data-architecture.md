# ox-data-architecture.md — ASADO data architecture deep dive

| Field | Value |
|---|---|
| **Date** | 2026-08-21 |
| **Author** | Session "ox-alpha" (Claude Code), at Arjun's request |
| **What this is** | Full deep dive into ASADO's data architecture and its effectiveness for the platform's tasks: collectors → warehouse → query surfaces → consumers. Findings and recommendations only — nothing here has been implemented. Companion to [ox.md](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/ox.md) (Alpha-Hunting Loop improvement ideas, same day). |
| **How produced** | Main session read: `ASADO_DATA_AUDIT.md`, `ASADO_LEAKAGE_AUDIT.md`, `ASADO_DATABASE_MAP.md` (gotchas section), plus verification queries. Four read-only subagent sweeps: DuckDB internals + disk usage, pipeline build architecture, collector layer + source coverage, Neo4j + query/consumption layers. One subagent claim (no external consumers) was **disproven by verification** — see §3.G. |
| **Status** | Proposal document. |

**Repo root for every path below:** `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/`

Key files referenced:

- [scripts/setup_duckdb.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/setup_duckdb.py) — delete-and-rebuild warehouse builder
- [scripts/monthly_update.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/monthly_update.py) / [scripts/daily_update.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/daily_update.py) — the two orchestrators
- [scripts/build_normalized_panel.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/build_normalized_panel.py) / [scripts/build_daily_panels.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/build_daily_panels.py) / [scripts/build_t2_master.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/build_t2_master.py)
- [scripts/collect_external.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/collect_external.py) / [collect_extended.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/collect_extended.py) / [collect_bloomberg.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/collect_bloomberg.py) / [collect_t2_bloomberg.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/collect_t2_bloomberg.py)
- [scripts/db_bridge.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/db_bridge.py) / [scripts/duckdb_lock_guard.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/duckdb_lock_guard.py) / [scripts/setup_neo4j.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/setup_neo4j.py) / [scripts/build_embeddings.py](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/scripts/build_embeddings.py)
- [Data/asado.duckdb](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/asado.duckdb) / [Data/loop/asado_loop.duckdb](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/Data/loop/asado_loop.duckdb) — inspected read-only 2026-08-21

---

## Bottom line

**The architecture is fundamentally sound for the job it actually does nightly — tidy long schema, zero duplication, fast queries, fully rebuildable — but it has three structural weaknesses:**

1. **Reliability by convention, not construction.** Delete-and-rebuild with no completeness gate means partial warehouses are silently consumable. The 2026-08-11 incident (`factor_returns_daily` left empty for days) was a design feature, not an accident — "upstream failed" becomes "table exists with 0 rows" on four separate code paths.
2. **A PIT gap that makes the warehouse unfit for its own stated ML ambition.** No `available_at` anywhere except two specialized tables; all 1,440 registry rows blank on publication lag; and the monthly T2 spine — the optimizer's own inputs — is winsorized with full-sample statistics including future rows.
3. **~30 GB of pure waste plus silently-dead subsystems.** A 4.8×-bloated DB file, 27 GB of unbounded backups, a 1.7 GB CSV regenerated daily — while embeddings have zero rows right now and ND-GAIN has contributed nothing since July with no alert.

## 1. What the architecture is

Three stores, one direction of flow:

- **asado.duckdb** (3.19 GiB, 43 objects) — 100% derived, deleted (`unlink()`, setup_duckdb.py:1134) and rebuilt from scratch **twice per monthly run**. Live data inside: only ~663 MB.
- **asado_loop.duckdb** (~258 MB, 68 objects) — the durable store: ledgers, harness results, loop signals, `graph_edge_vintages`. This split is the architecture's best decision: the rebuildable warehouse can be destroyed freely because everything precious lives elsewhere.
- **Neo4j** (810 nodes / 21,473 edges) — wiped (`MATCH (n) DETACH DELETE n`, setup_neo4j.py:369-372) and rebuilt whole every monthly run.

Flow: ~38 sources → collectors → `Data/processed/*.parquet` → DuckDB rebuild → views (`unified_panel` = 9-way UNION ALL, 2,586,851 rows; `feature_panel` = raw ∪ normalized, 3,551,786) → daily extension (t2_factors_daily 35.9M rows, fresh to 2026-08-20) → optimizer chain **via Excel workbooks** (each written to 3 directories, copied between others) → factor returns → Neo4j + embeddings + schema cache. GDELT lives in a separate 23 GB repo (`/Users/arjundivecha/Dropbox/AAA Backup/A Working/GDELT`) with its own 4-stage pipeline (GKG ZIP fetch → country-day parquet → trailing z signals → metronomes); ASADO holds a 2.4 GB *stale copy* (ends 08-09) off the live path.

Monthly run timing (2026-08-09 log, 2,084s total): collectors dominate (bilateral 390s, GDELT ingest 329s, Bloomberg 153s); the DB rebuilds themselves are 6-7s each; daily panels 75s.

## 2. What is genuinely good

- **Schema discipline.** Tidy long `(date, country, value, variable[, source])` everywhere; zero key duplication across the panel stack (verified: `unified_panel` ∩ `normalized_panel` key overlap = 0; internal dups 0.35% of unified); every date column is a real DATE/TIMESTAMP — no VARCHAR dates, no NaT strings.
- **Query performance is a non-issue.** Latest-value window scans over 2.6M rows: 0.01s. Event-window patterns on the 35.9M-row daily table: 0.01s. No indexes needed at this scale.
- **Full derivability.** The warehouse can always be rebuilt from parquets — bold changes are cheap.
- **Collector resilience pattern works** (source-level merge: a failed source keeps its prior rows), with 24h caching, urllib3 retries on 429/5xx, and per-source status tracking.
- **The lock guard is careful** (lsof-verified PID check before kill, SIGTERM→SIGKILL escalation, anti-PID-reuse), and daily runs are fail-fast with sha1/argv-fingerprinted resume checkpoints.
- **`graph_edge_vintages`** (161 vintages: trade 27 annual, bank 109 quarterly, holder 25, each with embedded publication lag via `applies_from`) is the best-designed object in the repo — genuinely PIT.
- **The returns-first guardrail** (optimizer outputs never unioned into input surfaces) is enforced structurally.

## 3. Findings

### A. Reliability is conventional, not constructed — the core weakness

- **No completeness gate on the main warehouse.** `verify_duckdb` (monthly_update.py:387-464) prints counts and gates nothing; `qa/check_source_alignment.py` is advisory, downgraded to WARN in both orchestrators; the governance run-manifest covers only loop-contract tables. No consumer checks build health before reading.
- **"Upstream failed" becomes "table exists with 0 rows" by design** — setup_duckdb empty-table fallbacks at :487-499, :842-852, :879-890, :1193-1203. Exact incident mechanism: `daily_update.py --rebuild --no-backup` → build_daily_panels drops and recreates `factor_returns_daily`, crashes on the optimizer's `KeyError: 'Date'` (schema-less xlsx), and the restore path is disabled by `--no-backup`. Repeated Aug 11-13, repaired Aug 17.
- **Non-atomic at every level except one.** Only build_t2_master.py:586-597 uses tmp→rename. The DB is deleted then built incrementally; Neo4j is wiped then repopulated (crash mid-way = partial graph); the 6 schema-cache JSONs are rewritten in place.
- **A run-history collision is actively destroying data:** collect_external.py:179 and collect_optimizer_returns.py:103 both write `Data/processed/run_history.json` with different schemas. The optimizer clobbered the external history on 08-09 — trend history for 20+ free sources now has exactly 1 entry.
- **Silent staleness is designed behavior.** ND-GAIN returned NO DATA in both recent monthly runs (run-history JSONs 07-01 and 08-09); the panel carries 2023-12 rows forever; nothing alerts. `merge_panels` only logs "KEPT n existing rows".
- **The schema cache never expires.** MCP validates against JSONs generated 08-09; `load_schema_cache` auto-builds only when files are *missing*, never on age (build_schema_registry.py:1501-1524) — a table added since then is rejected as "Unknown DuckDB table".
- **db_bridge.py:77 holds a long-lived read-only connection** for the AsadoDB object's lifetime and does NOT use duckdb_lock_guard — it is the squatter class the guard was built to kill.

### B. The PIT gap (fitness for the ML task)

Confirmed per the Milestone-0 audit, mechanism verified:

- No `available_at`/vintage fields outside `weo_vintages` and `graph_edge_vintages`; all 1,440 `variable_registry` rows blank on publication lag / revision / vintage.
- **The monthly T2 spine is cleaned with full-sample statistics**: `_winsorize` (median/MAD over the ENTIRE series, build_t2_master.py:249-255) and `_check_local_outliers` (centered ±20 window including FUTURE rows, :227-246). These cleaned factors are the optimizer's inputs — so `factor_returns`, `factor_top20_membership`, and the attribution view inherit the contamination. (Forward-return targets are derived from TRI *before* cleaning, so the target itself is clean — reconciled to 1.56e-15.)
- The **daily** builder is clean by contrast (same-date `_CS`, expanding `_TS` at t2_normalize_daily.py:75-85) — the correct pattern already exists in the codebase; the monthly chain just doesn't use it.
- **Two normalization systems** with different rules: t2_normalize.py (T2 `_CS`/expanding `_TS`) vs build_normalized_panel.py (rolling windows 252d/60m/20q/10y). And `_CS` for non-T2 sources is computed over up to **43 countries** before `feature_panel_t2` filters to 34.

### C. Data-integrity defects in the live DB (2026-08-21)

- **±Infinity used as missing:** 1,126,590 rows (3.1%) of `t2_factors_daily` and 17,782 of `t2_master` — concentrated in commodity `_CS` z-scores (Copper_CS 148.5K, Agriculture_CS 144.4K), almost certainly zero-dispersion division. Half +inf / half −inf, so they poison min/max/mean too. `t2_master` also mixes 113,226 true NULLs with the infs.
- **Projections pollute the panels:** 22,698 `normalized_panel` rows dated 2027-12→**2100-12** (`DIP_*` demographics) flow into `unified_panel` (11,349) and `feature_panel`, making `max(date)` meaningless; `gdelt_panel` (3,128 rows) and `factor_top20_membership` (736) carry **pre-created 2026-09-01 rows**; `extended_factors` has stray 2026-12 ILO forecast rows.
- **Degenerate transforms of weak sources:** OFAC is a single-date snapshot (68 rows, 2026-08-01) yet reaches `feature_panel` as `_CS`/`_TS` variants; EIA annual data gets monthly-tiled transforms — 42 weak-source variables total inflate the discovery surface (and the future multiple-testing bill).
- **Concept duplication across sources** (all flowing into the panel as if independent): inflation ×3 (WB annual stale / IMF CPI monthly / IMF WEO), FX ×3 (ECB per-EUR / IMF LCU-per-USD / Bloomberg), policy rates ×3, current account ×3, GDP growth ×2, unemployment ×2, gov debt ×2, population ×2, UST 2Y/10Y in both FRED and Bloomberg.
- Known documented parse errors persist (UNDP_HDI 93-130 for several EMs; `BBG_M2_YoY` Vietnam 110,003), plus the 9 non-universe countries silently present in 3.51% of `unified_panel` rows (90,692 rows: Ireland, Greece, Norway, Russia, Portugal, Austria, Belgium, NZ, Finland).
- Source provenance is lossy: the `bloomberg` source tag can't distinguish raw `BBG_*` from derived `MS_*` variables except by name prefix.

### D. Storage: ~30 GB of waste on a 43 GB repo

| Item | Size | Verdict |
|---|---|---|
| Dead space inside asado.duckdb | **~2.5 GB** | DuckDB never shrinks on checkpoint; delete-rebuild cycles left the file 4.8× its ~663 MB of live segments (PRAGMA database_size: 9,148 used / 3,907 free blocks). A COPY-to-fresh-file rebuild reclaims ~80%. |
| Data/backups | **27 GB (73% of Data/)** | Unbounded retention: 287 entries back to April, **9 full DB snapshots** (~25.2 GB), ~3.4 GB/month accruing — each snapshot itself bloated. No pruning policy. |
| `Data/work/t2_daily/Normalized_T2_MasterCSV.csv` | **1.7 GB, regenerated daily** | Sits beside the 272 MB parquet with the same content; no obvious consumer of the CSV. |
| Stale ASADO `Data/gdelt` copy | 2.4 GB | Partial duplicate of the 23 GB GDELT repo, ends 08-09, off the live path. |
| .git | 1.9 GB | Committed data files: a 5.5 MB regime parquet blob; `cos_mockups/cockpit_data.json` re-committed many times (~3.4 MB/version). |

Storage efficiency *inside* the schema is exemplary (tidy long, compression eats most repeats — the daily layer is 583 MB live for 57M rows). All the waste is operational accretion.

### E. Neo4j is not earning its keep analytically

- Every analytical consumer uses the graph as **three 34×34 weight matrices** (trade/banking/portfolio) — which already exist as upstream parquet (`Data/processed/bilateral_{trade,banking,portfolio}_matrix.parquet`). build_graph_features.py pulls exactly 3 edge queries and does two-hop propagation in numpy, not Cypher. No GDS usage anywhere. collect_pit_edges.py uses Neo4j only as an iso3→name map with a JSON fallback.
- `HAS_FACTOR_EXPOSURE` is 13,759 of 21,473 edges (64%) — a materialized latest-value cache regenerable by one DuckDB window query over `unified_panel`.
- The "now" surface is currently broken three ways: **embeddings are DEAD** (the daily graph refresh wipes them and only the monthly job rebuilds — 0 Country nodes carry `state_embedding`; the `countryStateIndex` vector index is online with zero entries, so "find similar countries" silently returns nothing); **`SUBJECT_TO` is misleading** (each sanctioned country assigned to an arbitrary program via `collect(s)[0]`, setup_neo4j.py:1038-1043); and `AsadoDB.__init__` requires Neo4j connectivity (db_bridge.py:79-80), so MCP `run_duckdb_sql` and the Streamlit app hard-fail on pure-DuckDB work when Neo4j is down — contradicting the loop's optional-Neo4j governance contract.
- Also misleading: `HAS_FACTOR_EXPOSURE` edge dates run to 2100 (DIP_* projections read as "latest"); 43 Country nodes include the 9 non-T2 names.
- Genuine remaining value: browser/LLM traversal UX (MCP `run_neo4j_cypher`, `get_country_profile`, Streamlit similarity page, Fable packet context).
- `refresh_factor_edges` (db_bridge.py:317-350) is dead code AND a footgun: it would rebuild edges from a single date, cutting 13,759 edges to ~34 if ever called.

### F. Excel is load-bearing — the biggest evolution blocker

The optimizer chain serializes through `.xlsx`: schema-less, type-less, 31-char sheet-name truncation producing baked-in mangled names (`MS_ETF_Creation_Unit_Size__d549`), each workbook written to 3 directories and copied between others (T2 Master.xlsx ×3, Normalized CSV ×3, Portfolio_Data.xlsx ×3). This is the source of the KeyError failure class and the triple-copy hotspots, and it makes every schema evolution fragile.

### G. Consumer inventory (verified)

- **Fable Daily Trading** (`/Users/arjundivecha/Dropbox/AAA Backup/A Complete/Fable Daily Trading/`) reads `asado_loop.duckdb` READ-ONLY from at least five modules (src/desk.py, layers.py, data_access.py, decide.py, performance.py) — **the loop DB is a production dependency of a downstream trading process.** This is why `qa/check_loop_schema.py` exists; loop-DB schema changes deserve API-change discipline. (A subagent initially reported no external consumers — disproven by direct verification; it had only searched `A Working/`.)
- 203 files reference the .duckdb paths: scripts/ 85, experiments 7, tests 6, regime* 12, cos_mockups 2, frontend 1, run.py.
- Cockpit (`cos_mockups/build_cockpit_data.py`) reads loop DB + JSON artifacts only — never Neo4j, never the main DB.
- dashboard.py is a log tailer; it reads no DB at all.
- MCP exposes 23 tools; note the docstring's "read-only tool surface" is not literally true — `register_hypothesis`/`evaluate_signal`/`open_thesis` write loop ledgers (by design, but say so). Read-only enforcement is regex-by-convention with a substring blocklist whose "set" pattern false-positives on "asset"/"offset"/"subset".

### H. Collector-layer specifics

- The collector skeleton (load existing → fetch → source-level merge → timestamped backup → run history → delta) is **copy-pasted, not shared** — identical infra blocks in collect_external.py and collect_extended.py. collect_bilateral.py has NO backup, NO run history, NO dry-run. collect_imf.py merges by inferred source set with a bare run-history list.
- **eia is NOT dead** (correcting the README): the collector was fixed (collect_extended.py:1246-1248) and is now annual petroleum consumption 2000-2025 — it *looks* stale but is annual-by-design.
- ACLED and UN Comtrade collectors exist but are commented out of the run list, and their API keys are absent from `.env.txt`. WITS and IPU were never built.
- Bloomberg pulls: manifest-driven (38 sheets / 1,292 ticker-field pairs monthly; 36 / 1,224 daily), batched by field into ~24-30 requests; "10Yr Bond" correctly pulled in LOCAL terms (USD override divides yields — the GTBRL10YR 14.46→2.81 example). Each full-history series = 1 quota cap hit. The OpusBloomberg conda env has blpapi but no duckdb — hence the parquet-only/venv-loader split, which is sound.
- Free-source collectors run sequentially by design (a parallel attempt caused ECB/BIS/OECD/FRED rate-limit collisions).
- Twelve-day cadence gap: monthly collectors last ran 08-09; the daily pipeline covers only T2/GDELT/loop — 20+ free sources sit still for a month at a time.

## 4. Effectiveness verdict by task

| Task | Verdict |
|---|---|
| Nightly loop feature supply (daily cross-sections) | **Effective.** Fresh to 08-20, tidy, fast, resilient collectors. |
| Ad-hoc research / harness / MCP | **Effective with sharp edges** — stale schema cache, Neo4j-up coupling, projection-polluted date ranges. |
| ML training (Milestone 1 ambition) | **Not yet fit** — the PIT gap is the binding constraint (already planned in ASADO_ML_ARCHITECTURE_PLAN.md, unfunded). |
| Human browsing/exploration | **Weak** — Streamlit + Neo4j surfaces partially broken (dead embeddings), generated docs stale (DATABASE_MAP row counts off ~6.7×; factor_reference generated 08-09 predates the 08-11/13 rebuilds). |
| Operational risk | **Medium**: single machine, strictly serial, no gates — but small blast radius thanks to full derivability and the loop-DB separation. |

## 5. Recommendations, ranked

1. **Make builds atomic at the file level: rebuild into a fresh DB file, then rename over the old one.** One change simultaneously fixes the partial-warehouse incident class, reclaims ~2.5 GB, and makes backups cheap. Same pattern for Neo4j (build under a temporary label, swap).
2. **Write a build manifest and make consumers gate on it** — per-table row counts, max dates, source run-ids, git sha, overall ok/PARTIAL stamp. Consumers: loop job, MCP, cockpit, and Fable Daily Trading. Convert the four empty-table fallbacks into loud PARTIAL stamps.
3. **Backup retention policy:** keep last 3 full snapshots + the monthly vintage dirs; prune the rest (27 GB → ~7 GB, less after fix 1).
4. **±Inf → NULL migration** in `t2_factors_daily`/`t2_master`, plus a zero-dispersion guard in the commodity z-scoring that emits them.
5. **Separate projections from observations:** `is_forecast` flag or separate tables for `DIP_*`/WEO; stop pre-creating next-month rows; then `max(date)` becomes a usable freshness signal.
6. **Fix the run-history collision** (one file per collector) and add **staleness alerting**: per-source expected cadence, alert on two consecutive NO DATA runs (would have caught ND-GAIN in July).
7. **Retire Excel from the pipeline path** incrementally — optimizer chain on parquet; xlsx only as final human artifacts. Kills the KeyError class and the triple-copy hotspots.
8. **Decide Neo4j's role explicitly.** Either demote to an optional presentation layer (fix the AsadoDB connectivity coupling, regenerate embeddings after wipes or move them to DuckDB, fix `SUBJECT_TO`) or retire it — analytically nothing is lost; the three adjacency matrices live in parquet.
9. **One normalization system, universe-correct `_CS`:** merge the t2_normalize and build_normalized_panel rules, restrict cross-sectional scoring to the declared 34, and adopt the daily builder's causal (expanding/rolling) cleaning for the monthly T2 spine — the cheapest large piece of the Milestone-1 PIT program.
10. **Curate the variable surface:** a canonical-variable map choosing one source per duplicated concept (inflation, FX, policy rates, …), and gate weak sources (single-snapshot OFAC, annual EIA) out of `_CS`/`_TS` transform generation — shrinking `feature_panel`'s 720+ variables to ones that can carry signal.
11. **Hygiene batch:** expire-or-refresh the schema cache on age; extract the copy-pasted collector skeleton into one shared module; add backup/run-history to collect_bilateral; gitignore the committed data files; kill the daily 1.7 GB CSV and the stale GDELT copy; move the hardcoded Neo4j credentials (7 files) to env.

Items 1–6 are days of work and eliminate most observed failure modes; 7–9 are the structural payoffs; 10–11 are compounding hygiene. Recommendation 9's causal re-clean of the T2 spine is also the prerequisite for trusting any future harness verdict on monthly T2-derived signals.
