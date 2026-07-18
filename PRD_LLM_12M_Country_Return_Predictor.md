# PRD — LLM Country Return Predictor, 1-Month Walk-Forward ("LLM-1M")

**Status:** DRAFT v2 for review — no code written yet
**Author:** Arjun Divecha / Claude
**Date:** 2026-07-17 (v2: horizon switched 12M → 1M; static split → expanding walk-forward)
**Depends on:** `Data/asado.duckdb`, `Data/loop/asado_loop.duckdb`, `scripts/harness/evaluate_signal.py`, `scripts/loop/build_combiner.py` (pattern), `config/family_registry.yaml`, `ledgers/hypothesis_ledger.jsonl`

---

## 1. Purpose

Predict the **next-1-month total return of each of the 34 T2 countries** using an LLM as a
*frozen, blinded feature extractor* over ASADO's point-in-time data surfaces, plus a **ridge
combiner** (the only trained component) refit on an **expanding walk-forward window**. The LLM
reads a structured monthly "country dossier" (past returns, valuation, macro/rates, factor
exposures and factor returns, global context) and emits interpretable sub-scores; the ridge
maps sub-scores → expected next-month excess return.

**Protocol:** the first ~10 years (2000-02 → 2009-12) are the burn-in/design period — block
ablations, prompt selection, and ridge-spec choices happen **only** there. From 2010-02 the
window expands mechanically: to predict month m+1 at month-end m, the ridge is fit on all rows
through m−1, on a pre-registered refit cadence. Every prediction from 2010-02 to 2026-05 is
genuine out-of-sample: **~196 months × 34 countries ≈ 6,700 OOS predictions**.

The hypothesis under test is *not* "LLMs know the future." It is: **an LLM forced to reason
only from point-in-time numeric dossiers produces sub-scores that carry cross-sectional signal
for monthly country rotation beyond momentum and value baselines.** If it doesn't, the harness
says so and the idea dies here — that is the asset.

## 2. Why this architecture (decision record)

| Option | Verdict | Reason |
|---|---|---|
| Pure zero-shot LLM ranking | Rejected as primary | No trained layer → prompt-shopping risk unbounded; nothing for the expanding window to fit. |
| Fine-tune an LLM | Rejected for v1 | Expensive, un-auditable, destroys the reasoning advantage; monthly walk-forward fine-tuning is operationally absurd here. |
| **Frozen LLM sub-scores + walk-forward ridge** | **Chosen** | The LLM is a fixed nonlinear feature map (auditable, schema-pinned); ALL learning lives in a small auditable ridge refit mechanically on the expanding window. Matches the `build_combiner.py` philosophy exactly (expanding window, scheduled refits). |

**v1 → v2 change (2026-07-17, Arjun's directive):** horizon switched from 12M-forward with a
static 15y/embargo/10y split to **1M-forward with an expanding walk-forward** after a 10-year
burn-in. Reasons: (a) statistical power — 1M labels are non-overlapping, giving ~196 genuine
OOS months vs ~9.5 independent 12M periods; (b) no embargo needed (a 1M-forward label overlaps
nothing beyond its own month; the walk-forward's mechanical one-month gap handles it); (c) the
12M version's dominant-regime concern is diluted over 16+ OOS years spanning multiple regimes
(2011 euro crisis, 2013 taper, 2015 China, 2018 vol, 2020 COVID, 2022 rates, 2024–26). The
dossier schema is horizon-agnostic; a 12M-horizon companion run can reuse the same dossiers
with a re-worded prompt later (v2 extension, §13).

Baselines that must be beaten OOS: (a) zero-shot LLM decile rank alone (no ridge), (b) 1M
reversal / 12-1M momentum ridge, (c) Shiller-PE value, (d) equal-weight benchmark. If
sub-scores + ridge cannot beat a ridge on the same count of classical features over 16 OOS
years, the LLM layer is not earning its keep and we say so.

## 3. Data reality (verified 2026-07-17 against the live DBs)

| Surface | DB | Shape | Role |
|---|---|---|---|
| `country_returns_monthly` | loop | 2000-02 → 2026-06, 317 mo × 34 c, `(date, country, return_1m)` | **label + trailing-return features** |
| `feature_panel` (`source='t2_raw'`) | main | 50 raw T2 vars, 2000-01 → | momentum/technical/valuation/fundamental blocks |
| `feature_panel` (`_CS`/`_TS` z variants) | main | 299 normalized vars; `_CS` same-date cross-sectional, `_TS` **rolling trailing** window (PIT-safe — `build_normalized_panel.py` uses `rolling(window, min_periods)`, verified) | primary feature form |
| `factor_returns` | main | 390 monthly factors × 3 sources (t2/econ/gdelt optimizer), 2000-02 → 2026-06 | factor-state block |
| `factor_top20_membership` | main | 749K rows `(date, country, factor, weight, source)` | factor-exposure block |
| `country_factor_attribution` (view) | main | membership ⨝ returns → weight × factor_return | attribution features |
| `valuation_monthly` | loop | CAPE/PB/DY/EY/ERP + 10y percentiles, 2000-01 → | valuation block |
| `ff_factors` | main (isolated) | 8 FF regions, monthly+daily | global-context block + spanning check at eval |
| `commodity_panel`, FRED block (VIX/UST/DXY/HY OAS via `extended_factors`), GPR | main | global, date-keyed | global-context block |
| GDELT `monthly_metronome` family | main | **2015-09 →** only | **EXCLUDED from v1** (see §13 — walk-forward makes it a clean v2 add at a pre-registered refit date) |

**Date-label semantics of `country_returns_monthly`** (verified empirically by
`build_country_returns.py`, quoted from its header): `date` is the FIRST OF THE MONTH the
return was earned **IN** — `date=2026-04-01, return_1m=0.1049` means April 2026 returned
+10.49%. Values are decimal fractions. The current incomplete month is excluded upstream. **PIT
rule: at a decision date inside month M, the last knowable row is month M−1.**

**Known data caveats:**
- Revision-prone series (BEST EPS, ECFC consensus, WEO) are stored latest-vintage. Small
  minority of dossier fields; flagged in the field dictionary. Everything price/rate/valuation/
  GDELT-based is as-known-at-the-time.
- `factor_top20_membership` contains rows dated beyond the latest realized return (current
  optimizer run's forward membership). Dossier assembly uses **membership as of month-end t
  only**.
- Bloomberg econ coverage is sparser before ~2005 for some series (CDS 15 countries,
  breakevens 6). Missing fields are emitted as explicit `null` with a per-block coverage flag —
  never silently filled, never carried forward in v1.

## 4. Target variable

From `country_returns_monthly`, for a dossier assembled at month-end of month m:

```
label(m, c)    = return_1m(m+1, c)                            # return earned IN month m+1
label_xs(m, c) = label(m, c) − mean_c( label(m, ·) )          # PRIMARY: excess over 34-country EW
```

- Labels are **non-overlapping** (consecutive months) — the statistical property that makes
  this design well-powered.
- Last realized label: the table runs through 2026-06 (June 2026 complete) → last feature
  month with a realized label is **2026-05**; last OOS label month is 2026-06.
- Raw `label` retained as secondary; excess-over-EW is primary (country rotation use case;
  ASADO reports vs the EW benchmark, gross returns).

## 5. Sample scheme — burn-in + expanding walk-forward (no embargo)

| Segment | Range | Months | Purpose |
|---|---|---|---|
| Burn-in / design | 2000-02 → 2009-12 | 119 | block ablations, prompt selection (≤3 pre-registered variants), ridge-spec selection, calibration — **all design freedom lives here** |
| Walk-forward OOS | predictions for 2010-02 → 2026-06 (feature months 2010-01 → 2026-05) | 196 | mechanical expanding-window evaluation; no design decisions |

**Walk-forward mechanics (pre-registered, not hand-tuned):**
- To predict month m+1 at month-end m: fit the ridge on rows (t, label(t)) for **t ≤ m−1**
  (every such label is realized by month-end m — clean, no overlap, no embargo needed).
- **Refit cadence: annual, each January** (expanding window; weights frozen between refits) —
  mirrors `build_combiner.py`'s January-refit pattern. A monthly-refit sensitivity arm is run
  once as a robustness check, pre-registered.
- First OOS prediction: features at month-end 2010-01, fit on 2000-02 → 2009-12, predict
  2010-02.
- The LLM scorer is frozen and run **once** over all dossiers 2000-02 → 2026-05 (~316 mo ×
  34 ≈ 10.7K dossiers); the walk-forward consumes its outputs mechanically. The LLM is never
  refit, re-prompted, or adjusted after the burn-in freeze.

## 6. THE LEAKAGE PROBLEM — threat model and blinding protocol

**The core threat is LLM knowledge-cutoff leakage, not database lookahead.** ASADO's surfaces
are PIT-disciplined; the LLM is not. A model shown "Brazil, June 2008" can *remember* the crash
instead of reasoning. A backtest that leaks this way is fake alpha and would destroy trust in
every downstream number. The blinding protocol is therefore the heart of this design:

1. **Identity blinding.** Country names → random tokens (`Country_K7`), re-randomized per
   scoring run and per ablation arm. The LLM never sees a real country name.
2. **Temporal blinding.** The LLM never sees a calendar date — relative indices only
   (`t−11 … t0`). The assembler holds the token↔(country, date) key outside the LLM boundary.
3. **Level stripping.** Features are cross-sectional ranks/z (`_CS`) and trailing within-country
   z (`_TS`), not raw levels, wherever a level could triangulate identity or era ("CDS =
   480bp" → guessable; "CDS z_CS = +2.3" → not). Raw levels permitted only in the
   global-context block, identical for all countries at t.
4. **Canaries (must all pass before any OOS number is believed):**
   - **Permutation canary:** re-score a sample of OOS months with country histories shuffled.
     Signal must collapse. If it doesn't — stop; the model was pattern-matching artifacts.
   - **Identity-known arm:** a small parallel arm (≤10% of months) scored WITH real country
     names/dates. If known ≫ blind, report both and treat the known arm as contaminated.
   - **Consistency check:** rescore 2% of dossiers; sub-score agreement within tolerance
     (temperature 0, but API nondeterminism exists).
5. **Global-context ablation.** The one block that cannot be fully blinded (VIX, US 10Y, USD,
   oil, gold, GPR levels) is separately ablatable; its marginal contribution is reported so we
   know how much of the signal is regime memory vs cross-sectional reasoning.
6. **Rationale audit.** The output schema requires a ≤120-word rationale citing dossier fields
   only. A random sample is human-audited for anachronism (any reference to events after t, or
   to real-world entities, voids the run and triggers a schema revision).

## 7. Input schema — `llm1m.dossier.v1`

One JSON dossier per (month-end t, country). Versioned; any field-set change bumps the version
and re-freezes the protocol. All values as of month-end t from PIT-safe surfaces.

```json
{
  "schema_version": "llm1m.dossier.v1",
  "country_token": "Country_K7",
  "t_index": 118,
  "coverage": {"macro_rates": 0.82, "factor_state": 1.0, "valuation": 1.0},
  "blocks": {
    "price_momentum": {
      "trail_ret_1m_zCS": -0.4, "trail_ret_3m_zCS": -0.7, "trail_ret_12m_zCS": 0.3,
      "mom_12_1_zCS": 0.5, "rsi14_zTS": -1.1, "dist_from_120ma_zTS": -0.8,
      "vol_20d_zCS": 1.4, "vol_360d_zTS": 0.9, "drawdown_from_peak_pct": -18.2
    },
    "valuation": {
      "shiller_pe_zCS": -1.2, "shiller_pe_pctile_10y": 12, "trail_pe_zCS": -0.9,
      "earnings_yield_zCS": 1.1, "pb_zCS": -0.6, "div_yield_zCS": 0.8,
      "best_eps_rev_3m_zTS": 0.4, "lt_growth_zCS": 0.2
    },
    "macro_rates": {
      "govt_10y_zTS": 1.8, "curve_10y2y_zTS": -0.6, "cds_5y_zCS": 2.3,
      "cds_5y_chg_3m_zTS": 1.9, "breakeven_zTS": 0.7, "wirp_implied_zTS": 1.2,
      "pmi_mfg_zTS": -1.4, "m2_yoy_zTS": -0.5, "ecfc_gdp_cons_zCS": -0.8,
      "inflation_zTS": 2.2, "current_account_zCS": -1.1, "debt_gdp_zCS": 0.9
    },
    "factor_state": {
      "top_factor_bets": [
        {"factor_token": "F_12", "weight": 0.22, "ret_1m": -0.031, "ret_12m": 0.084}
      ],
      "attribution_12m": {"style_token_A": 0.042, "style_token_B": -0.018},
      "factor_crowding_zCS": 0.7
    },
    "global_context": {
      "vix_zTS": 1.6, "us_10y_chg_3m": 0.55, "usd_zTS": 0.8,
      "oil_12m_ret": 0.34, "gold_12m_ret": 0.12, "gpr_zTS": 1.1
    }
  }
}
```

The field dictionary (source table → field, revision-prone flag) is maintained as a spec
appendix at build time. Factor names are tokenized (`F_12`, `style_token_A`); identity is
recoverable from the key, never from the LLM. `coverage` reports the non-null fraction per
block; the LLM is instructed to treat `null` as "not available," never to invent values.

## 8. Output schema — `llm1m.output.v1`

Structured JSON, schema-validated, retry-with-corrections on parse/validation failure (max 3,
then the (t,c) cell is recorded missing — never silently defaulted):

```json
{
  "schema_version": "llm1m.output.v1",
  "country_token": "Country_K7",
  "expected_1m_excess_pct": 0.8,
  "decile_1_to_10": 8,
  "confidence_0_to_1": 0.55,
  "subscores": {
    "valuation": 1.5, "momentum_quality": -0.5, "macro_risk": -1.0,
    "credit_stress": -1.5, "policy_trajectory": 0.0, "factor_alignment": 0.5
  },
  "key_risks": ["credit spreads widening from elevated level", "PMI rolling over"],
  "rationale": "<=120 words; must cite dossier fields only"
}
```

Sub-scores on a −2..+2 scale with fixed definitions in the system prompt (the six above are
the v1 set; changing them = schema v2). The prompt frames every judgment as **next month**,
not next year — the LLM is explicitly told the horizon.

## 9. The two model layers

### 9.1 Frozen LLM scorer (no training, ever)
- Single pinned model ID + temperature 0; model ID logged per response; bulk scoring may use a
  mid-tier model with a flagship validation subsample (agreement reported).
- System prompt defines: the monthly rotation task, the six sub-score definitions, the
  anti-leakage instructions (reason only from the dossier; never identify the country or
  period; nulls = unavailable), and the output schema. ≤3 prompt variants pre-registered;
  selection on burn-in evidence only.
- Per-country independent calls (no cross-country contamination inside a context);
  cross-sectional comparison happens in the ridge + evaluation layer, not in the LLM.
- All raw responses logged immutably (run directory, JSONL) before any parsing.

### 9.2 Walk-forward ridge combiner (the only trained component)
- Target: `label_xs(m,c)` (next-month excess). Features: the 6 sub-scores (+ the
  expected_1m point estimate as an optional 7th, decided in burn-in).
- Expanding window, annual January refits, burn-in 119 months — per §5. Regularization fixed
  by burn-in walk-forward, then frozen.
- Output per (m, c): predicted next-month excess return → cross-sectional rank. Ranks are what
  the harness consumes.

## 10. Burn-in protocol and the freeze list

On 2000-02 → 2009-12 ONLY:
1. **Block ablations** — drop each dossier block in turn; keep blocks whose sub-scores add
   rank IC vs `label_xs`. Report the full ablation table (including drops — no silent
   truncation).
2. **Prompt selection** — among the ≤3 pre-registered variants, by burn-in walk-forward
   rank IC.
3. **Ridge spec** — feature set (6 vs 7 inputs), regularization, refit cadence confirmed.
4. **Calibration** — confidence → realized hit-rate mapping (reporting only).

Then **freeze**, before any post-2009 scoring: dossier schema (v1) · prompt (verbatim, hashed)
· sub-score definitions · ridge spec · refit cadence · evaluation metrics and baselines ·
canary thresholds.

Registration (repo law — every "signal works" claim is a charged trial):
- `ledgers/hypothesis_ledger.jsonl`: mechanism written BEFORE OOS results exist.
- `config/family_registry.yaml`: new family `llm_1m_country_rotation` (burn-in ablations count
  as trials against the family; the registry entry must say so).

## 11. OOS evaluation

- Score all dossiers 2010-01 → 2026-05 (blinded), run the mechanical expanding walk-forward,
  emit per-month cross-sectional ranks for 2010-02 → 2026-06 label months.
- Evaluate via `scripts/harness/evaluate_signal.py` conventions: rank IC + Newey–West t,
  top-7 vs EW benchmark (monthly rebalanced), sub-periods (full / 5y / 3y / 1y), deflated
  Sharpe vs family trial count, **gross returns** (cost gates retracted 2026-07-13;
  implementation diagnostics only). Labels are non-overlapping, but cross-sectional correlation
  within a month is real — inference follows the harness's existing conventions.
- `ff_spanning.py` on the resulting long-short P&L: alpha or repackaged value/momentum/market
  beta?
- Expectation-setting: monthly cross-sectional ICs will be small (this horizon is noisy);
  success = positive mean IC with a real NW-t AND a top-minus-bottom spread that beats the
  classical baselines in §2 — not a large raw IC.
- Canaries from §6.4 run in the same pass; any failure voids the run.
- Verdict language follows the ledger convention (STRONG / WEAK / DEAD), auto-attached.

## 12. Engineering plan (after this spec is approved)

```
experiments/llm1m/                      # committed: code + spec outputs only
  build_dossiers.py                     # DuckDB → dossier JSONL (PIT-checked, incremental writes)
  blind.py                              # token key management, blinding + unblinding
  score_llm.py                          # LLM batch scoring, raw-response log, schema validation
  combine_ridge.py                      # expanding walk-forward ridge, frozen artifacts in/out
  evaluate_oos.py                       # harness-convention evaluation + canaries + verdict
Data/work/experiments/llm1m/            # gitignored: dossiers, raw responses, run dirs
  runs/YYYY_MM_DD_HHMM/                 # self-contained run dir: JSON summary + log + outputs
```

- **Incremental writes everywhere** (repo rule): dossiers append JSONL per month; raw LLM
  responses written before parsing; runs resumable from any month.
- **Never hold a DuckDB connection**; short read-only sessions
  (`duckdb_lock_guard.guarded_connect()`), close, then process.
- Avoid the 06:00–08:30 PT nightly window for long runs.
- Volume: ~10.7K dossiers (burn-in 4.0K + OOS 6.7K incl. canary replicates) — batch API,
  modest cost; token usage logged per run.
- Nothing touches `Data/processed/`, `Data/loop/`, shared `Data/work/`, `config/`, or
  `ledgers/` except the two explicit registration writes in §10.

## 13. v2 extensions (explicitly out of scope for v1)

- **GDELT `monthly_metronome` block** (2015-09+): the walk-forward makes this clean — add the
  block at a pre-registered refit date (e.g. January 2017, giving ~16 months of metronome
  history), with the ridge gaining features only from that refit onward. Own registration.
- **12M-horizon companion run**: same dossiers, re-worded prompt (next year, not next month),
  labels `Π(1+r)−1` over m+1..m+12 with the embargo logic from v1 of this PRD.
- Cross-country LLM ranking pass (all 34 score-cards in one context) — v1 keeps per-country
  blind calls to preserve the blinding guarantee.
- Sovereign/market-implied/ETF-flow loop layers (many start 2021+) — same coverage problem as
  GDELT; walk-forward add-on candidates.
- Prospective deployment: if OOS survives, a forward paper-thesis arm via `ledgers.py` /
  thesis ledger with sealed rationales (the journal's `sealed_rationales/` pattern).

## 14. Open questions for Arjun

1. Refit cadence: annual January refits (chosen, mirrors `build_combiner.py`) — or quarterly?
   (A monthly-refit sensitivity arm is already pre-registered as a robustness check.)
2. The six sub-scores in §8 — right decomposition? Option: reserve a 7th "news_sentiment"
   sub-score slot (null in v1) so the v2 metronome block drops in without a schema break.
3. Model choice for bulk scoring: pin one model end-to-end for cleanliness, or allow
   mid-tier-bulk + flagship-subsample with an agreement report?
4. Permutation-canary failure: voids only the run, or kills the whole `llm_1m` family?
