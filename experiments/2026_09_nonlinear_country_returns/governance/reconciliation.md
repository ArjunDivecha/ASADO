# P00 — Repository and Governance Reconciliation

**Study:** ASADO Nonlinear Country-Return Study (`ASADO_NL_20260913_V1`)
**Branch / worktree:** `exp/Nonlinear` at `ASADO-exp-Nonlinear` (base commit `a8a8699`)
**Date:** 2026-09-13
**Status at this checkpoint:** governance reconciled; nothing bound, registered, or evaluated.

This document records what the repository actually says versus what the agent-pack PRD
assumed, the prior-exposure record, and the registration path this study will use.
No outer IC, Sharpe, or model rankings appear here — none have been produced.

---

## 1. What the pack is (and is not)

`docs/ASADO_Nonlinear_Study_Agent_Pack` (vendored to `spec/` inside this experiment
directory) is a *specification handoff*: 14 phases, 56 dependency-linked tasks, 60
acceptance tests. Pack integrity validates clean; its `--require-registered` check
fails **by design** while the study is unbound. It claims no executed results.

The scientific question: does a pooled depth-2/≤4-leaf histogram-boosted model on a
fixed 16-input economic representation predict **20-local-session** USD total returns
better than independently tuned ridge models on the same point-in-time-safe sample —
with the comparison made only on a common panel, only after registration.

## 2. Document-authority map (what governs what)

| Document | Role | Trust |
|---|---|---|
| `CLAUDE.md` + `AGENTS.md` | operational hard rules | current, binding |
| `.agents/skills/asado-*` (8 skills) | governance detail | current, binding; loaded: research-protocol, graveyard, change-control |
| `docs/README.md` | doc-authority index | current |
| `scripts/harness/evaluate_signal.py` | the single-signal harness | code is truth (v4, 2026-07-14 execution embargo) |
| `scripts/loop/ledgers.py` | all three ledgers' API | code is truth |
| `config/family_registry.yaml` | single-signal families | binding for hypothesis-ledger trials only |
| `config/governance_contract.yaml` v1.4 | nightly step list + scorecard dimensions | binding; also documents the graph-PIT exclusion |
| `ledgers/*.jsonl` | append-only verdict record | binding; never hand-edited |
| `MacroStateModel.md`, `experiments/2026_09_macrostate/`, `docs/macrostate_2026_09_05/` | prior experiment artifacts | descriptive history (untracked in git) |
| External: `Investment Learnings/INDEX.md` + `Research-Agenda-2026-07-v2.md` | cross-project graveyard + Six Laws | binding as priors |

PRD-vs-repo conflicts found and resolved:

1. **Study home.** PRD proposes `research/nonlinear_country_returns/`; house convention
   is `experiments/<YYYY_MM>_<name>/` + `Data/work/experiments/<name>/` scratch. The PRD
   explicitly defers to conventions discovered in P00 → resolved to
   `experiments/2026_09_nonlinear_country_returns/`; the pack is vendored under `spec/`.
2. **Worktree has no live data.** `Data/` in the worktree contains only git-tracked
   files — no `asado.duckdb`, no `Data/loop/`, no `Data/work/`, and `loopdb.BASE_DIR`
   resolves per-worktree. All data access uses absolute main-tree paths; snapshots land
   in the main tree's `Data/work/experiments/nonlinear_country_returns/`. This is a
   property of worktrees generally, worth remembering for every phase.
3. **Native harness fit (P10 preview).** `evaluate_signal.py` evaluates *one registered
   variable* against next-period returns (NW-t ≥ 2.5, ≥60% positive-IC years, gross LS
   Sharpe > 0 with top-7 excess > 0, deflated Sharpe > 0 vs family trial count). It has
   no concept of an 8-model paired contest on overlapping 20-session labels. P10's
   "native harness binding" therefore means a **frozen-prediction adapter** (the study's
   pre-computed cross-sectional score presented as a signal column under an honest
   publication lag) or a documented "native qualification unresolved" report — the PRD
   anticipates exactly this. Decision deferred to P10; recorded now so nobody expects
   the harness to absorb the whole study.
4. **RR tenor.** `market_implied_daily` carries `FX_RR25_1M_PCT` only; the PRD's P11
   asks for a **3M** 25-delta risk reversal. Deferred to P01: amend-with-governance-note
   or mark UNVERIFIED/BLOCKED. No silent substitution.

## 3. Registration path (decided)

This is a **directory-level methodology experiment** → `ledgers/methodology_ledger.jsonl`
via `register_methodology_experiment()` + `attach_methodology_verdict()` in
`scripts/loop/ledgers.py` (change-control LAW 2). Registration happens at **P06**, before
any real outer evaluation, with `hypothesis_text` + the study's own gate ladder written
first (the function enforces ≥15-word hypothesis and validates the ladder).

The hypothesis ledger is *not* used: `register_hypothesis` requires a single variable
resolving to a family prefix (`UnclassifiedVariableError` otherwise), and charging a
whole-model contest to a family would corrupt that family's deflated-Sharpe trial count.

## 4. Prior-exposure record (graveyard protocol §1, all five sources)

This is the finding that most changes how the study must be written up.

| Source | Evidence | Relevance |
|---|---|---|
| Methodology ledger | `M_20260906_001` MacroState model contest, `M_20260906_002` bounded tree + neural comparison, `M_20260906_003` missingness-only control — all **WATCH**, 2026-09-06 | **Direct lineage.** Same idea family: compress economic inputs into states, test whether shallow nonlinearity beats linear. |
| `experiments/2026_09_macrostate/` + `MacroStateModel.md` | Monthly origins, 12M horizon, 14 primitives → 4 state composites; trees depth-3/7-leaf; annual-leader edge largely collapses under a missingness/US-sleeve control; authors state the nonlinear stage "was designed after earlier results were seen" | Prior exposure the PRD author could not see (untracked, same-week work). This study differs in contract — daily origins, 20-session labels, fixed 16-input S, fixed 12-config grid, nested PIT selection, paired block-bootstrap + Holm — so it is **not** a duplicate, but it is also **not fresh confirmation** of anything MacroState found. The missingness result is a live warning: the PRD's common-complete-case panel could re-import the same "data-availability as country label" artifact; P04's eligibility design must answer it. |
| Hypothesis ledger | 63 hypotheses, final verdicts: 26 DEAD / 11 WEAK / 16 INSUFFICIENT_COVERAGE / 10 WATCH | The study's primitives are individually dead as standalone signals (`bbg_skill_2026_06` DEAD×9 including `FX_RR25_Z252`, `FX_CARRY_Z252`, `SOV_2S10S_Z252`; `valuation_2026_06` DEAD×4; `consensus_ecfc` DEAD). Expected, not a conflict — the claim is about pooled nonlinear structure, per the graveyard's second-order law. |
| Experiment RESULTS.md | `regime/` DEAD (0/52 regime-conditional ICs), `regime_ew` DEAD gate 3, `regime_factor_selection` clean null (0/74), `momentum_fragility` DEAD gate 3 | No conflict; reinforces that first-order/conditioning structures on this universe die. |
| External graveyard | `LLM-1M Country Rotation` tabular arm: HGB on raw fields, walk-forward 1M horizon, OOS IC +0.027, WATCH but DSR −0.093; `T2 IPCA` factor-timing: ridge-L2 failed (OOS rank IC −0.017), listwise ~0.20 Sharpe | Prior pooled-model and trees-on-raw evidence at different horizons. The IPCA L2 failure is directionally consistent with this study's premise; neither is a duplicate. |

**Verdict on novelty:** the study is a *distinct, stricter contract* over a familiar idea
family. Proceed under a **new** methodology registration whose `hypothesis_text`
explicitly names the MacroState lineage — not an amendment (different gates, different
target), not a blocker (no DEAD verdict covers this contract).

## 5. Source-family reconnaissance (read-only, detail in `source_map.json`)

Schemas/row-counts observed without holding any DB connection:

- `asado.t2_factors_daily` — 36.0M rows; price/TRI source of truth. `1DRet` is a
  forward calendar-grid label; the audited path is `loopdb.daily_country_returns()`
  (backward-shifted, placeholder-dropped). Study labels are built independently from
  TRI levels — never from `20DRet` (forward, blacklisted).
- `market_implied_daily` — 23 variables incl. `FX_IMPVOL_1W/1M/3M`, `FX_RR25_1M_PCT`,
  `FX_CARRY_3M_PCT`, VIX/VIX3M/MOVE/DXY/BBDXY/HY/IG-OAS, 10 commodity generics (CO=Brent).
  The 1W-IV and carry gaps suspected at spec time **do not exist**; the RR-tenor
  question does (§2.4).
- `sovereign_daily` — 33 countries, `SOV_2Y_YIELD_PCT` **present** (suspected gap
  resolved), `SOV_10Y_YIELD_PCT`, `SOV_CDS_1Y/5Y_BP`. Known: no 10Y for HK/Vietnam.
- `consensus_daily` — `CONS_GDP_PCT`/`CONS_CPI_PCT` **with `target_year`** — fixed-target
  semantics bindable; per-series revision paths distinguish "unchanged" from "missing".
- `graph_features_pit_daily` — 1.86M rows, 10 `GRAPHP_*` variables. Only the PIT variant
  is admissible (v1 `graph_features_daily` was removed from the nightly for look-ahead
  L-05 per governance contract v1.4). `graph_edge_vintages` (93.8K rows,
  vintage_end/applies_from/focal/neighbor/weight) supports the PRD's
  `historical_edge_vintages_required=true` — direction/mass/self-edge audit is P01.
- `weo_vintages` — the repo's only true vintage table (36 vintages, 2008→2026);
  available as a vintage-correct fallback reference if needed.

## 6. Environment and verification

- Project venv (shared from main checkout): Python 3.14.3, **scikit-learn 1.8.0**
  (`HistGradientBoostingRegressor` present — API/semantics must still be verified in
  P05: `l2_regularization`, `early_stopping=False`, `max_bins=16` support),
  numpy 2.4.4, pandas 3.0.2, scipy 1.17.1, statsmodels 0.14.6, duckdb 1.5.1,
  pyarrow 23.0.1, pytest 9.0.3. Full freeze: `governance/environment.lock`.
- PIT/ledger safety tests: `test_harness_pit`, `test_pit_lag`,
  `test_methodology_ledger`, `test_ledger_integrity` — **46 passed**.
- Harness invariants confirmed in code: forward-return blacklist (:159-162);
  `MIN_DAILY_EXECUTION_EMBARGO_DAYS = 1` floor on every daily evaluation (:179);
  fail-closed `CONSERVATIVE_DAILY_LAG_DAYS = 1` absent a passing `pit_proof_registry`
  entry; gross-only verdict gates (cost gating retracted 2026-07-13 — consistent with
  the PRD's gross-only spec).

## 7. P00 gate

| Gate item | Result |
|---|---|
| Governance/harness reconciliation | DONE — §2–§3 |
| Prior-exposure check (graveyard §1, all 5 sources) | DONE — §4; MacroState lineage declared |
| Registration path | DECIDED — methodology ledger at P06 |
| Source-family reconnaissance | DONE — §5 + `source_map.json` |
| Environment pin | DONE — `environment.lock` |
| Conflicts/blockers | No blockers; 1 open tenor question (P11) + 1 deferred adapter decision (P10) |
| Outer results produced | **None** (as required) |

**P00 verdict: PASS — proceed to P01 read-only field-level audit.**
