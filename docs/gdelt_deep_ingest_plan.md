# GDELT Deep — Warehouse Ingest Plan

**Status:** PLAN ONLY — do NOT execute. Deep panel still being downloaded /
backfilled in the GDELT working repo (~55% as of 2026-04-27).
Source: `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/Deep.md`.
**Last updated:** 2026-04-27

## Goal

Land the 1,130 new GDELT Deep features (themes / GCAM / events) in the ASADO
warehouse as **first-class but separately-tagged** data, then run them
through the existing PIT and normalization machinery so any future strategy
can consume them on equal footing with ASADO's existing GDELT variables.

## What this plan does NOT do

- It does **not** add Deep variables to Strategy #1 v1's worldstate.
  v1 is closed at NO-GO; rerunning that harness is a separate v2 conversation.
- It does **not** modify `feature_panel` automatically until normalization
  is verified. Deep variables stay in their own table until then.
- It does **not** rebuild Neo4j Factor nodes / embeddings until after the
  warehouse layer is verified.

## Preconditions (verify before starting)

1. Backfill is finished. Check:
   ```
   /Users/arjundivecha/Dropbox/AAA Backup/A Working/GDELT/Deep/data/features/country_signal_monthly_deep_treated.parquet
   ```
   - Expected shape: ~32,067 rows × 1,221 columns
   - Expected ISO3 coverage: at least the 31 ISO3 codes that map to T2 (USA, CHN, GBR, DEU, JPN, FRA, ITA, ESP, CAN, AUS, BRA, CHE, SWE, NLD, DNK, KOR, IND, MEX, IDN, TUR, ZAF, SAU, SGP, HKG, TWN, THA, MYS, PHL, POL, CHL, VNM)
   - Expected date range: month-end dates 2015-01 through current month

2. Schema yamls present:
   ```
   /Users/arjundivecha/Dropbox/AAA Backup/A Working/GDELT/Deep/scripts/schema/{gcam_dimensions,gdelt_themes,cameo_codes}.yaml
   ```

3. ASADO DuckDB and Neo4j are reachable (not strictly required for steps 1-2,
   but needed before any Neo4j follow-up).

## Step-by-step plan

### Step 1 — Add the Deep source mapping to country_mapping.json

The existing 34-country mapping is keyed by source-specific codes (BIS, OECD,
WB, EPU, GPR, etc.). Deep is keyed by ISO3, but with two fan-outs:

- `USA → [U.S., NASDAQ, US SmallCap]` (3 T2 buckets)
- `CHN → [ChinaA, ChinaH]` (2 T2 buckets)

Action: extend `config/country_mapping.json` with a `gdelt_deep` field per
T2 row (ISO3 string), and add a one-to-many fan-out helper in
`scripts/db_bridge.py` (or a new util) that returns the list of T2 names for a
given ISO3.

**Acceptance:** all 34 T2 names map to at least one ISO3; ISO3 coverage in
the panel matches the 31 unique codes above (HK, TW, etc. all present).

### Step 2 — Write `scripts/collect_gdelt_deep.py`

A new collector following the existing project conventions
(`scripts/collect_*.py`, mandatory header, per-source try/except, backup
before overwrite, run_history.json metadata).

Responsibilities:
1. Load `country_signal_monthly_deep_treated.parquet`.
2. Validate columns against the expected three families (theme_*, gcam_*,
   event_*) plus the existing tone-derived core variables.
3. **Drop tone-family duplicates**: any column that already exists in
   `gdelt_panel` (the 92 existing tone vars) — Deep ships these for
   completeness; we don't want two copies.
4. Map `country_iso3 → t2_name(s)` using the helper from step 1; emit one
   row per T2 fan-out target. **Critical:** USA rows must be triplicated for
   U.S. / NASDAQ / US SmallCap; CHN rows duplicated for ChinaA / ChinaH —
   matching the existing convention in `collect_external.py` and
   `collect_imf.py`.
5. Convert to first-of-month dates (the panel uses month-end; project
   convention is first-of-month).
6. Melt to tidy long format: `(date, country, value, variable, source)`
   where `source ∈ {gdelt_deep_theme, gdelt_deep_gcam, gdelt_deep_event}`.
7. Save to `Data/processed/gdelt_deep_panel.parquet` with timestamped backup
   to `Data/backups/{ts}/`.
8. Append a row to `Data/processed/run_history.json` per the existing
   resilience pattern.

**Acceptance:** parquet exists, ~400k–500k rows expected (1,130 vars × ~130
months × ~36 T2 fan-out countries minus missing cells), no duplicate
`(date, country, variable)` triples, date range 2015-01-01 to current month,
all 34 T2 names present.

CLI:
```
python scripts/collect_gdelt_deep.py            # normal run
python scripts/collect_gdelt_deep.py --force    # re-ingest, ignore mtime cache
python scripts/collect_gdelt_deep.py --dry-run  # validate only, no writes
```

### Step 3 — Load into DuckDB as a separate table

Extend `scripts/setup_duckdb.py` with a new stage that loads
`gdelt_deep_panel.parquet` into a DuckDB table named `gdelt_deep_factors`.

**Important:** do NOT add it to the `feature_panel` view yet. Until the
normalization story is decided (step 5 below), it stays a sibling table.

```sql
CREATE OR REPLACE TABLE gdelt_deep_factors AS
SELECT date, country, value, variable, source
FROM read_parquet('Data/processed/gdelt_deep_panel.parquet');

CREATE INDEX IF NOT EXISTS idx_gdelt_deep_dcv
  ON gdelt_deep_factors(date, country, variable);
```

**Acceptance:** `python scripts/setup_duckdb.py --check` returns the new
table with expected row count, date range, and unique variable count.

### Step 4 — PIT-audit the Deep variables

Re-run the existing PIT audit framework over the new tag set, not the `_CS`
suffix. Two options:

(a) **Preferred:** generalize `scripts/strategy/analogs/pit_audit.py` to take
a `--source` filter in addition to `--prefix`, and run it with
`--source gdelt_deep_theme`, `--source gdelt_deep_gcam`,
`--source gdelt_deep_event`. Output: append rows to the existing
`pit_audit.csv` so the audit covers everything in one file.

(b) **Alternative:** keep `pit_audit.py` strategy-scoped and write a thin
wrapper at `scripts/qa/pit_audit_gdelt_deep.py` that uses the same exclusion
rules. Cleaner separation but duplicates code.

**Expected outcome:** missingness filter (>40%) will cull a large chunk of
pre-2015 vars automatically (Deep starts ~2015, but many themes don't have
universal coverage). That's the correct behavior — don't relax the threshold
without a written reason.

The `gdelt_partial_month_caveat` flag is already in the audit; Deep's
month-end snapshot is its own convention so the GDELT partial-month rule
may need a small revisit. Note in audit code if so.

**Acceptance:** every Deep variable has a row in `pit_audit.csv` with
`vintage_safe`, `exclusion_reason`, and `notes` populated. Total row count
~1,355 (existing 229 + 1,130 new minus tone duplicates handled in step 2).

### Step 5 — Decide normalization (BEFORE adding to feature_panel)

Deep already ships its own time-series treatments (fast/slow/trend/z, fast_z)
which are trailing-window WITHIN-COUNTRY z-scores. These are roughly
equivalent to ASADO's `_TS` family, NOT `_CS`.

The existing strategy harness (Strategy #1 v1, and any future v2) uses `_CS`.
We need to choose:

- **Option A:** Run Deep raw values through
  `scripts/build_normalized_panel.py::_build_cross_sectional` to produce
  `_CS` variants. PIT-safe because `_CS` z-scores group by
  `(variable, source, date)` — confirmed in v1's PIT audit.
- **Option B:** Keep Deep's native trailing z-scores and treat them as the
  `_TS` analog, exposing them to strategies that want time-series form.
- **Option C:** Both — produce `_CS` for cross-sectional models and keep
  `_TS` (Deep's native) for time-series models.

Recommendation: **Option C**. Cost is one pass through `_build_cross_sectional`
on the raw Deep features (cheap), payoff is symmetry with the rest of the
warehouse. Does not require any change to existing `_CS` naming convention.

**Acceptance:** `normalized_panel` contains `<varname>_CS` rows for every
Deep raw variable; `feature_panel` view union includes `gdelt_deep_factors`
PLUS the new normalized rows.

### Step 6 — Smoke tests

After steps 1–5, before considering this done:

1. `python scripts/setup_duckdb.py --check` passes.
2. SQL spot check: pull `EPU_POLICY` theme share for Brazil 2020-03 and verify
   it spikes vs Brazil's trailing 24m. (Pandemic onset.)
3. SQL spot check: `event_n_quad4` (material conflict) for Russia / Ukraine /
   Saudi Arabia 2022-02 should be elevated. (We don't have Russia in T2 so
   verify on Saudi Arabia / Turkey / Poland which are.)
4. Country fan-out sanity: `SELECT COUNT(*) FROM gdelt_deep_factors
   WHERE country IN ('U.S.','NASDAQ','US SmallCap') GROUP BY country`
   returns identical counts (USA fanned out 3x).
5. PIT spot check: pick any (date, country, variable) row and confirm its
   numerical value did not change after the audit was applied (audit only
   flags, never overwrites).

### Step 7 — Neo4j Factor nodes (deferred)

Only after warehouse layer is verified. Spec roughly per Deep.md §5:

- `MERGE (f:Factor {name: <varname>})` with `category` = source tag and
  `family` ∈ {THEME ATTENTION, GCAM EMOTIONAL DIMENSIONS, EVENT AGGREGATES}.
- `MERGE (c:Country)-[:HAS_DEEP_FACTOR]->(f)` for the 31 active ISO3s,
  fanned out to 34 T2 names.
- Do NOT rebuild `state_embedding` from Country nodes yet — embedding
  refit is a strategy-level decision tied to whether v2 actually uses Deep.

## Out of scope / explicitly later

- v2 of Strategy #1 worldstate (separate spec; depends on a Deep
  feature-curation conversation, not the bulk warehouse load).
- Recomputing `country_state_embedding` over the expanded feature set.
- Any modification to `monthly_update.py` (orchestrator) until after
  steps 1–6 land manually and have run cleanly twice.

## Files that will be created or touched

| File | Action |
|---|---|
| `config/country_mapping.json` | extend each T2 row with `gdelt_deep` ISO3 field |
| `scripts/collect_gdelt_deep.py` | NEW — collector for Deep panel |
| `scripts/setup_duckdb.py` | extend — add `gdelt_deep_factors` table load |
| `scripts/strategy/analogs/pit_audit.py` (or new wrapper) | extend — accept `--source` filter |
| `scripts/build_normalized_panel.py` | extend — produce `_CS` variants for Deep raw vars |
| `Data/processed/gdelt_deep_panel.parquet` | NEW (generated) |
| `Data/asado.duckdb` | adds `gdelt_deep_factors` table |
| `Data/strategy/analogs/v1/pit_audit.csv` | extended rows |

## Estimated effort

Once the Deep parquet is final and stable:
- Step 1: ~30 min (mapping config + helper)
- Step 2: ~2 hours (collector with the project's standard resilience pattern)
- Step 3: ~30 min (DuckDB load)
- Step 4: ~1 hour (PIT audit generalization)
- Step 5: ~1 hour (cross-sectional treatment + view update)
- Step 6: ~30 min (smoke tests)
- **Total: ~5–6 hours of focused work, single PR.**

Step 7 (Neo4j) adds another ~2 hours; separate PR.

## Trigger

Resume when the user confirms backfill is complete and
`country_signal_monthly_deep_treated.parquet` is finalized.
