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

## Monitored families and rosters (v1, deterministic) — AUTHOR AMENDMENT 1

Roster is the committed data file `scripts/loop/family_ic_roster_v1.json` —
**frozen**, not re-resolved from the live ledger. Each family carries one or
more named rosters, persisted in the durable table's `roster` column so a
family's monitored series is **continuous** and changes only on a deliberate
re-issue (not on every live re-verdict, which would make the series
discontinuous). Two roles:

- `role: gate` (`book_2026_07_14`) — the Alpha Book v2 WATCH-tier variables
  frozen at Book publication. **This is the series the R-A gate runs on** and the
  status artifact reports.
- `role: inv4_reference` (`ref16_frozen`, network_spillover only) — a6's exact
  16 members, used **only** for the INV4 known-answer comparison.

| family | freq | horizon | gate roster (`book_2026_07_14`) |
|---|---|---|---|
| `network_spillover` | daily | 5d | `GRAPH_BANK_NBR_RET_GAP_21D`, `GRAPHP_TRADE_NBR_RET_GAP_21D`, `GRAPHP_KATZ_TRADE_GAP_21D`, `SIM_NBR_RET_GAP_21D`, `LL_LEADER_GAP_5D` |
| `eco_surprise` | monthly | 1m | `ECO_INFL_SURPRISE_Z` |
| `ml_combiner` | daily | 5d | `COMBINER_RIDGE_DAILY_V1` |

**Why ref16 is frozen (not re-resolved live):** the a6 known-answer was computed
on the 16 WEAK/WATCH members that existed on 2026-07-13, *before* the harness-v4
re-verdict (2026-07-14) demoted 4 to DEAD (the live post-v4 ledger now lists
only 12). Freezing to the a6-era 16 is the only way the backfill can reproduce
a6.

## Durable table & status artifact (INV3, INV6)

- Table `family_ic_nightly` in the **durable** loop DB
  (`Data/loop/asado_loop.duckdb`) — one row per `(family, roster, month)`,
  PRIMARY KEY `(family, roster, month)`, upsert via `ON CONFLICT ... DO UPDATE`
  (idempotent re-runs).
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

## INV4 known-answer — four amended clauses (AUTHOR AMENDMENT 1)

The backfill runs INV4 on network_spillover's **`ref16_frozen`** roster against
the flip-autopsy references. Four binding clauses (`ok` = AND of all four),
implemented in `inv4_comparison()`:

1. monthly corr ≥ `INV4_MIN_CORR` (0.95) vs the committed a2 monthly series;
2. per-year means within `INV4_PER_YEAR_TOL` (0.012) of a6's `lag1_per_year`;
3. 2012-2023 mean within `INV4_PRE_MEAN_TOL` (0.001) of a6's `lag1_pre_mean` (+0.0123);
4. post-2024 (≥2024) mean < 0 — the flip must reproduce.

**Why 0.012, not the originally-authored 0.005:** the a6 generating script was
never committed (commit `cdcd9a4` added only the JSON output + a `USER_FIX_LIST`
note). A faithful read-only reconstruction from the committed a2 machinery +
frozen snapshot establishes a6 is definitively **lag-1**, matches a6's aggregate
pre-2024 mean to 5 decimals (0.01231 vs 0.01228) and correlates **0.9517** with
a2 — but per-year worst |delta| vs a6 is ~**0.011** even on the identical
snapshot (a6's exact daily→monthly→yearly path is unrecoverable). The author
amended the per-year tolerance to 0.012 (measured independent-reconstruction
noise, not authored precision) and added the pre-mean and flip clauses so the
known-answer is both reproducible and meaningful. Thresholds are named,
adjustable module constants; the backfill prints the full per-year table
regardless. **Contract lesson: reference artifacts must be committed WITH their
generating script.**
