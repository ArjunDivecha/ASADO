# ox-review.md — verification of `ox-data-architecture.md`

| Field | Value |
|---|---|
| **Date** | 2026-08-21 |
| **Reviewer** | Claude Code (Opus 5), at Arjun's request |
| **Subject** | [ox-data-architecture.md](file:///Users/arjundivecha/Dropbox/AAA%20Backup/A%20Working/ASADO/ox-data-architecture.md) — commit b41bf16 |
| **Method** | Independent re-derivation of every load-bearing claim: 33 checks against the live DB, Neo4j, and source at the cited line numbers. Nothing accepted on assertion. |

---

## Verdict: competent, and unusually so — with two errors that matter

**33 of 33 factual claims I re-derived came back correct, most exact to the row.** Ox ran the
queries; it did not pattern-match. Evidence: `t2_factors_daily` infinities **1,126,590**
(claimed 1,126,590), `t2_master` infinities **17,782** (17,782), NULLs **113,226** (113,226),
`unified_panel` **2,586,851** (2,586,851), `feature_panel` **3,551,786** (3,551,786), Neo4j
**810 nodes / 21,473 edges** (810 / 21,473), `HAS_FACTOR_EXPOSURE` **13,759 = 64%** (13,759 =
64%), `PRAGMA database_size` **9,148 used / 3,907 free** (9,148 / 3,907). Every cited line
number (`setup_duckdb.py:1134`, the four empty-table fallbacks at 487/842/879/1193,
`build_t2_master.py:227-255`, `db_bridge.py:77-80`, `setup_neo4j.py:369-372`, `:1038-1043`)
resolves to exactly the code described.

Three qualitative markers of real competence:

1. **It caught and corrected its own subagent.** A sweep reported "no external consumers"; Ox
   disproved it by direct verification and named the five Fable Daily Trading modules. I
   confirmed all five (`desk.py`, `data_access.py`, `decide.py`, `layers.py`,
   `performance.py`, `read_only=True`). An incompetent reviewer accepts its own tooling.
2. **It reconciled a subtle exculpatory fact against its own thesis.** It argues the T2 spine
   is contaminated by full-sample cleaning, then notes the *targets* escape because forward
   returns are derived from raw TRI before cleaning. Verified: `_forward_returns` at line 422
   consumes `tot_ret` loaded at 418; `_clean_sheet` only runs in the separate loop at 471.
   Correct, and it weakens Ox's own headline — it reported it anyway.
3. **It corrected the repo's own README** (eia is annual-by-design, not dead) rather than
   inheriting a documented error.

One place *I* was wrong and Ox was right: I spot-checked the non-universe countries with
`'Russia'` and got 80,362. The actual name is `Russian Federation`; the correct figure is
**90,692 = 3.51%**, exactly as Ox stated.

### Error 1 — the storage headline is overstated ~2.5x (affects recommendation #1)

Ox: "~2.5 GB dead space… the file 4.8x its **~663 MB** of live segments (PRAGMA: 9,148 used /
3,907 free)… reclaims ~80%."

This is **self-contradicting**: 9,148 used blocks x 256 KB = **2.29 GB**, not 663 MB. The free
blocks (3,907 x 256 KB = 1.02 GB) are the dead space.

Tested directly — `COPY FROM DATABASE` into a fresh file:

| | |
|---|---|
| Current `asado.duckdb` | **3.19 GB** |
| Fresh rebuilt copy | **2.21 GB** |
| Actually reclaimable | **~1.0 GB (31%)** — not ~2.5 GB (80%) |
| Rebuild wall time | **30 seconds** |

The recommendation survives, but must be justified on **atomicity**, not space. The 30-second
figure is the real argument: a full atomic rebuild is nearly free.

### Error 2 — recommendation #11 would break the daily pipeline

Ox: "`Data/work/t2_daily/Normalized_T2_MasterCSV.csv` — 1.7 GB, regenerated daily… **no
obvious consumer of the CSV**… kill the daily 1.7 GB CSV."

It has a consumer. `scripts/t2_optimizer_daily.py:52` sets
`DEFAULT_CSV = T2_DAILY_DIR / "Normalized_T2_MasterCSV.csv"` and line 94 does
`pd.read_csv(csv_path)` — every day. Deleting the CSV breaks the daily optimizer.

The waste is real (`t2_normalize_daily.py:141-142` writes CSV **and** parquet with identical
content), but the fix is ordered: **switch the consumer to parquet first, then stop writing
the CSV.** As written the recommendation is a footgun.

Minor drift: loop DB stated "~258 MB", actually 180 MB.

---

## What Ox did not do — severity is never sized

Every finding is asserted true/false; none is quantified. The report cannot be used to
prioritise as-is. Two examples where I supplied the missing number:

**The PIT look-ahead — how much does it actually move?** Re-implementing both mechanisms
verbatim against `t2_raw` (1,686 series, 475,567 observations):

| Mechanism | Effect |
|---|---|
| `_winsorize` (full-sample median/MAD bounds) | **0.642%** of points clipped; 21.9% of series affected |
| `_check_local_outliers` (centred window incl. future) | **0.083%** of points replaced |
| **Combined** | **~0.72% of observations** |

Worst-hit are exactly the factor-bearing series: Trailing EPS 36 (4.6%), Trailing PE (2.6%),
LT Growth (2.6%), Best Div Yield (2.2%), Earnings Yield (2.1%).

So the leak is **real but small**. For calibration, this repo's documented ElasticNet PIT
incident (a 1-month date-convention error) fabricated **+5.1%/yr and +0.28 Sharpe**. This is
not that. It is a correctness defect that can flip a marginal verdict, not one that
manufactures a large alpha.

**But it reaches further than Ox says.** Ox scopes the contamination to the optimizer chain
(`factor_returns`, `factor_top20_membership`, attribution). It also reaches the research
surface: `unified_panel` unions `t2_master` as `source='t2'` — **1,085,246 rows = 30.6% of
`feature_panel`**, the harness's primary feature surface. Harness verdicts on T2-derived
variables therefore inherit it, and verdicts are permanent (ledgers, Investment Learnings).
That is the urgency argument, and it is missing from the report.

**Also unmentioned: sync cost.** `Data/` (37 GB) sits inside Dropbox. 27 GB of unbounded
backups, a 3.2 GB DB rewritten twice per monthly run, and a 1.7 GB CSV rewritten daily are all
continuously re-synced. Dropbox was observed holding `asado.duckdb` open during this session.
The waste is not just disk; it is bandwidth and CPU, every day.

---

## Re-ranked action list

Ox's ranking optimises for structural elegance. Mine optimises for "what is losing data or
breaking rules right now".

### Tier 0 — actively wrong today (hours)

1. **`run_history.json` collision — actively destroying data every run.**
   `collect_external.py:179` and `collect_optimizer_returns.py:103` write the same path with
   incompatible schemas (Dict vs list). The file today is a **1-entry list** written by the
   optimizer; `collect_external.load_run_history()` expects a Dict. The staleness history for
   20+ free sources is gone and is re-destroyed monthly. Fix: one file per collector. *(Ox
   ranked this #6 — too low for a live data-loss bug.)*
2. **`db_bridge.py:77` violates the repo's own first safety law.** It holds a lifetime
   read-only DuckDB connection and does **not** use `duckdb_lock_guard` (confirmed: zero
   references in the file). This is precisely the squatter class that caused the 2026-07-02/03
   pipeline failures. *(Ox identifies it in §3.A but gives it no recommendation number at all
   — the single biggest prioritisation miss in the report.)* Fix: short-lived
   `guarded_connect()` per query, and drop the `verify_connectivity()` hard-coupling at 79-80
   so pure-DuckDB work survives Neo4j being down.

### Tier 1 — correctness reaching recorded verdicts (days)

3. **±Inf → NULL** in `t2_factors_daily` (1,126,590 rows) and `t2_master` (17,782), plus a
   zero-dispersion guard in the commodity `_CS` z-scoring that emits them. These poison
   min/max/mean wherever they are aggregated. *(Ox #4 — agree.)*
4. **Separate projections from observations.** `max(date)` on `unified_panel` is **2100-12-01**
   because of `DIP_*`; freshness monitoring is impossible until this is fixed. Add
   `is_forecast`, stop pre-creating next-month rows. *(Ox #5 — agree.)*
5. **Make the T2 spine causal** — adopt the daily builder's expanding-window pattern, which
   already exists correctly in this codebase (`t2_normalize_daily.py:75-85`). Given the 0.72%
   magnitude this is important-not-urgent; it is a prerequisite for trusting future harness
   verdicts on T2 variables, not a reason to distrust the live book. *(Ox #9.)*

### Tier 2 — reliability (days)

6. **Atomic rebuild (build to temp file, rename)** — justified by the 30-second rebuild and
   the partial-warehouse incident class, **not** by the overstated space saving. *(Ox #1.)*
7. **Build manifest + consumer gating**, converting the four silent empty-table fallbacks into
   loud PARTIAL stamps. Fable Daily Trading is a live consumer, so this deserves API
   discipline. *(Ox #2 — agree, well-argued.)*
8. **Staleness alerting** — ND-GAIN is frozen at **2023-12-01** and nothing fires. *(Ox #6.)*

### Tier 3 — waste (hours, high ratio)

9. **Backup retention policy** — the single biggest real win: ~27 GB → ~7 GB, and it reduces
   Dropbox sync churn as well as disk.
10. **CSV → parquet**: repoint `t2_optimizer_daily.py:94` at the existing parquet, *then* drop
    the CSV write. **Do not delete the CSV first** (see Error 2). Saves 1.7 GB of daily churn.
11. Schema-cache expiry (12 days stale), stale 2.4 GB `Data/gdelt` copy, gitignore committed
    data files.

### Endorsed but lower confidence

Ox's Excel-retirement (#7) and Neo4j-decision (#8) are correctly reasoned — Neo4j genuinely
carries no analytical load (three adjacency matrices already exist as parquet; embeddings are
**0 of 43** and the vector index is empty). But both are large refactors of working systems;
they should follow Tiers 0-2, not precede them.

---

## Bottom line on Ox

Competent, and I would trust its factual claims by default after this — with the caveat that
it **does not size what it finds** and **did not verify that its own deletion advice was
safe**. Use its findings; re-derive its numbers before spending money on them; do not action
recommendation #11 as written.
