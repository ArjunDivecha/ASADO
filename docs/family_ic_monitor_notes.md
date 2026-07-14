# Family-IC Monitor — notes (contract FAMILY-IC-MONITOR-001)

Built on branch `exp/family-ic-monitor`. Module:
`scripts/loop/build_family_ic_monitor.py`; roster data: `scripts/loop/family_ic_roster_v1.json`;
tests: `tests/test_family_ic_monitor.py`; review audit: `tests/test_review_audit_monitor.py`.

## What it is

A nightly monitor that recomputes each research **family's** monthly Information
Coefficient (IC) on the **harness-v4 honest clock** and maintains the Alpha
Book's **R-A price gate** state per family. It exists because the
`network_spillover` family's IC went negative in ~April 2024 and was not
measured for ~15 months — family IC was only ever computed on-demand by the
skeptic harness (see `experiments/2026_07_flip_autopsy/results/RESULTS.md`).

The monitor **measures**; it never verdicts. It cannot promote or kill a signal
— only the skeptic harness assigns verdicts. Gate success proves the
implementation contract, not the product bet (that decay/re-arm events get
noticed and acted on within a day); that is evaluated only after shipping.

## Honest clock (INV1)

Member ICs are computed with alignment helpers **imported** from
`scripts/harness/evaluate_signal.py` (`align_daily`, `align_monthly`,
`rank_ic_series`, `effective_daily_lag_days`, `infer_publication_lag`) — never
reimplemented. Every daily member therefore carries an effective lag ≥ 1
trading day (the forward-return window opens strictly after the signal date,
including for ZERO_LAG_SOURCES). This is proven on the harness's own
planted-echo / planted-IC known-answer fixtures (reused verbatim in the tests).

## Family IC construction

`family_ic = ` equal-weight mean, across the members present in a month, of each
member's **sign-aligned** per-date cross-sectional rank IC, collapsed to a
first-of-month mean series. Daily families use their 5d horizon; monthly
families use their 1m horizon with the harness monthly publication embargo.

## Monitored families (v1, deterministic roster)

Roster is the committed data file `scripts/loop/family_ic_roster_v1.json` —
**frozen**, not re-resolved from the live ledger (see below).

| family | freq | horizon | members |
|---|---|---|---|
| `network_spillover` | daily | 5d | the 16 GRAPH*/GRAPHP*/LL_*/SIM_* variables that carried a WEAK/WATCH verdict in the flip autopsy (all `higher_is_better`) |
| `eco_surprise` | monthly | 1m | `ECO_INFL_SURPRISE_Z` |
| `ml_combiner` | daily | 5d | `COMBINER_RIDGE_DAILY_V1` |

**Why the roster is frozen to 16 (not re-resolved live):** the a6 known-answer
was computed on the 16 WEAK/WATCH members that existed on 2026-07-13, *before*
the harness-v4 re-verdict (2026-07-14) demoted 4 of them to DEAD. The live
post-v4 ledger now lists only 12. Freezing to the a6-era 16 is the only way the
backfill can reproduce the a6 reference; re-resolving from the live ledger would
make the known-answer unreproducible. When v2 of the monitor re-derives the
roster from current verdicts, the a6 tie-out is retired.

## Durable table & status artifact (INV3, INV6)

- Table `family_ic_nightly` in the **durable** loop DB
  (`Data/loop/asado_loop.duckdb`) — one row per `(family, month)`, PRIMARY KEY
  `(family, month)`, upsert via `ON CONFLICT ... DO UPDATE` (idempotent re-runs).
  Never the main warehouse (destroyed on every rebuild). Opened through
  `loop_connection()` → `guarded_connect()`; connections are never held.
- Status artifact `Data/work/loop/family_ic_status.json` (atomic temp-then-rename).
- The monitor writes **only** those two surfaces (statically scanned + a dynamic
  synthetic run confirms it).

## R-A price gate (INV5)

State machine over **completed** month-ends (the current partial month is
excluded): start `parked`; two CONSECUTIVE strictly-positive family-IC
month-ends re-arm the family; any non-positive month-end (≤ 0, including exactly
zero, or a missing value) **or a calendar gap** resets the consecutive counter
and re-parks a re-armed family. Transitions are persisted with their evidence
months. As of the 2026-06 month-end `network_spillover` is expected `parked`
with 0 consecutive positives (2025 and 2026H1 were negative).

## Entry points

- `--backfill` — full history + INV4 known-answer (gate **G3**, permissioned).
- default (no flag) — the fail-soft nightly incremental step the loop calls (gate **G4**).
- `--status` — print the status artifact.
- `--dry-run` — validate wiring/paths without opening any DB (used to confirm
  G3/G4 commands are well-formed without executing them).

## Loop wiring

One step, `family_ic_monitor`, is added to `scripts/loop/loop_daily_job.py`
`STEPS` after `build_family_ranks` (so `combiner_scores_daily` and the
graph/lead-lag/similarity feature tables it reads are built first). It is
**fail-soft**: `nightly_step` catches everything and returns exit 2 (PARTIAL),
never a hard exit 1, so a monitor crash is a warning that cannot take down the
loop.

## INV4 known-answer — important caveat (a6 reference)

The backfill compares the `network_spillover` monthly family IC against two
flip-autopsy references: per-year means vs `a6_lag1_family_ic.json` (±0.005) and
monthly correlation vs `a2_family_ic_monthly_recomputed.parquet` (≥0.95).

**The a6 generating script was never committed** (commit `cdcd9a4` added only
the JSON output + a `USER_FIX_LIST` note). A faithful reconstruction from the
committed a2 machinery + frozen snapshot, read-only, establishes:

- a6 is definitively a **lag-1** diagnostic (lag-0 is off by ~0.035/yr; the
  `USER_FIX_LIST` entry confirms pre-2024 mean +0.0123 / NW-t 2.2).
- The construction here matches a6's **aggregate** pre-2024 mean to 5 decimals
  (0.01231 vs 0.01228) and correlates **0.9517** with the committed a2 monthly
  series — the correlation clause passes (thinly).
- BUT the **per-year** worst |delta| vs a6 is ~**0.011** (≈12/27 years exceed
  ±0.005), even on the identical frozen snapshot — a6's exact daily→monthly→
  yearly path is unrecoverable (its monthly NW-t is 2.23 vs 1.89 here).

So the ±0.005 per-year clause **as literally written is not reproducible** from
the lost script. The comparison ships with the contract's literal thresholds as
documented, adjustable module constants (`INV4_PER_YEAR_TOL`, `INV4_MIN_CORR`);
the backfill prints the full per-year table + both correlations so the operator
sees exactly where live data lands. The thresholds are **not** silently
weakened. Author-side resolution pending (relax per-year tol to ~0.012, or make
the binding check the reproducible corr≥0.95 vs a2 with per-year vs a6 as a
diagnostic).
