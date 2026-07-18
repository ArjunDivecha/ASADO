# PRD — LLM 12-Month Country Return Predictor ("LLM-12M")

**Status:** DRAFT for review — no code written yet
**Author:** Arjun Divecha / Claude
**Date:** 2026-07-17
**Depends on:** `Data/asado.duckdb`, `Data/loop/asado_loop.duckdb`, `scripts/harness/evaluate_signal.py`, `scripts/loop/build_combiner.py` (pattern), `config/family_registry.yaml`, `ledgers/hypothesis_ledger.jsonl`

---

## 1. Purpose

Predict the **next-12-month total return of each of the 34 T2 countries** using an LLM as a
*frozen, blinded feature extractor* over ASADO's point-in-time data surfaces, plus a **ridge
combiner** that is the only trained component. The LLM reads a structured monthly "country
dossier" (past returns, valuation, macro/rates, factor exposures and factor returns, global
context) and emits interpretable sub-scores; the ridge maps sub-scores → expected 12M excess
return.

**Protocol:** first ~15 years (2000-02 → 2014-12) are the design/training period; a 12-month
embargo (calendar 2015) severs label overlap; the last ~10 years (2016-01 → 2025-06 realized
labels) are evaluated **once**, frozen, through the standard harness.

The hypothesis under test is *not* "LLMs know the future." It is: **an LLM forced to reason
only from point-in-time numeric dossiers produces sub-scores that carry cross-sectional signal
for 12M country rotation beyond momentum and value baselines.** If it doesn't, the harness
says so and the idea dies here — that is the asset.

## 2. Why this architecture (decision record)

Chosen over two alternatives:

| Option | Verdict | Reason |
|---|---|---|
| Pure zero-shot LLM ranking | Rejected as primary | No meaningful "training period"; prompt-shopping risk is unbounded; nothing to fit on 15 years. |
| Fine-tune an LLM | Rejected for v1 | ~6K overlapping training rows, expensive, destroys the reasoning advantage, un-auditable. |
| **Frozen LLM sub-scores + ridge combiner** | **Chosen** | The LLM is a fixed nonlinear feature map (auditable, schema-pinned); ALL learning lives in a small auditable ridge fit on 2000–2014 only. Matches the `build_combiner.py` philosophy (walk-forward ridge over fixed components). |

Baselines that must be beaten OOS: (a) zero-shot LLM decile rank alone, (b) 12-1M momentum,
(c) Shiller-PE value, (d) equal-weight benchmark. If sub-scores + ridge cannot beat a ridge on
momentum/value features alone over 10 OOS years, the LLM layer is not earning its keep and we
say so.

## 3. Data reality (verified 2026-07-17 against the live DBs)

| Surface | DB | Shape | Role |
|---|---|---|---|
| `country_returns_monthly` | loop | 2000-02 → 2026-06, 317 mo × 34 c, `(date, country, return_1m)` | **label construction** |
| `feature_panel` (`source='t2_raw'`) | main | 50 raw T2 vars, 2000-01 → | momentum/technical/valuation/fundamental blocks |
| `feature_panel` (`_CS`/`_TS` z variants) | main | 299 normalized vars; `_CS` same-date cross-sectional, `_TS` **rolling trailing** window (PIT-safe — `build_normalized_panel.py` uses `rolling(window, min_periods)`, verified) | primary feature form |
| `factor_returns` | main | 390 monthly factors × 3 sources (t2/econ/gdelt optimizer), 2000-02 → 2026-06 | factor-state block |
| `factor_top20_membership` | main | 749K rows `(date, country, factor, weight, source)` | factor-exposure block |
| `country_factor_attribution` (view) | main | membership ⨝ returns → weight × factor_return | attribution features |
| `valuation_monthly` | loop | CAPE/PB/DY/EY/ERP + 10y percentiles, 2000-01 → | valuation block |
| `ff_factors` | main (isolated) | 8 FF regions, monthly+daily | global-context block + spanning check at eval |
| `commodity_panel`, FRED block (VIX/UST/DXY/HY OAS via `extended_factors`), GPR | main | global, date-keyed | global-context block |
| GDELT `monthly_metronome` family | main | **2015-09 →** only | **EXCLUDED from v1** (absent from the 2000–2014 train window); v2 add-on, OOS-era only |

**Known data caveats:**
- Revision-prone series (BEST EPS, ECFC consensus, WEO) are stored latest-vintage. They are a
  small minority of dossier fields; flagged in the field dictionary. Everything price/rate/
  valuation/GDELT-based is as-known-at-the-time.
- `factor_top20_membership` contains rows dated beyond the latest realized return (current
  optimizer run's forward membership). Dossier assembly must use **membership as of month-end t
  only** — never membership dated after t.
- Bloomberg econ coverage is sparser before ~2005 for some series (CDS 15 countries, breakevens
  6). Missing fields are emitted as explicit `null` with a coverage flag — never silently
  filled. (Repo rule: no fabricated values; stale carry-forward only with a flag, and we choose
  NOT to carry forward in v1 — `null` + flag is cleaner for the LLM.)

## 4. Target variable

Built from `country_returns_monthly` (unambiguous; avoids any interpretation risk around the
`12MRet` optimizer-target alias):

```
label(t, c)       = Π_{k=1..12} (1 + return_1m(t+k, c)) − 1          # raw 12M forward
label_xs(t, c)    = label(t, c) − mean_c( label(t, ·) )              # PRIMARY: excess over 34-country EW
```

- First-of-month dates, matching ASADO convention.
- Last fully-realized label: **2025-06** (needs returns through 2026-05... realized through
  2026-06 data → labels complete through t = 2025-06; exact cut computed at build time).
- Raw `label` retained as a secondary target; the cross-sectional excess is primary because the
  use case is country rotation and ASADO reports vs the EW benchmark.

## 5. Sample split — with mandatory embargo

| Segment | Range | Months | Purpose |
|---|---|---|---|
| Train/design | 2000-02 → 2014-12 | 179 | block ablations, prompt selection (≤3 pre-registered variants), ridge fitting (walk-forward), confidence calibration |
| **Embargo** | 2015-01 → 2015-12 | 12 | severs the 12M-forward label overlap between train tail and OOS head — **non-negotiable** |
| OOS | 2016-01 → 2025-06 (realized) | ~114 labels | evaluated ONCE, frozen, via the harness |

Effective independent OOS information: ~9.5 non-overlapping 12M periods × 34 countries. Power
comes from the 34-wide cross-section; sub-period reporting (full / 5y / 3y / 1y vs EW, per the
`backtest` skill convention, gross returns) is mandatory. The OOS era is dominated by one
regime (2016–2025 US mega-cap bull) — a structural limitation we report, not hide.

## 6. THE LEAKAGE PROBLEM — threat model and blinding protocol

**The core threat is LLM knowledge-cutoff leakage, not database lookahead.** ASADO's surfaces
are PIT-disciplined; the LLM is not. A model shown "Brazil, June 2008" can *remember* the crash
instead of reasoning. A backtest that leaks this way is fake alpha and would destroy trust in
every downstream number. The blinding protocol is therefore the heart of this design:

1. **Identity blinding.** Country names are replaced with random tokens (`Country_K7`),
   re-randomized per scoring run and per ablation arm. The LLM never sees a real country name.
2. **Temporal blinding.** The LLM never sees a calendar date. Dossiers use relative indices
   (`t−11 … t0`). The assembler holds the token↔(country,date) key outside the LLM boundary.
3. **Level stripping.** Features are emitted as cross-sectional ranks/z (`_CS`) and trailing
   within-country z (`_TS`) — not raw levels — wherever a level could triangulate identity or
   era ("CDS = 480bp" → guessable; "CDS z_CS = +2.3" → not). Raw levels are permitted only in
   the global-context block, which is identical for all countries at t.
4. **Canaries (must all pass before any OOS number is believed):**
   - **Permutation canary:** re-score the OOS period with country histories shuffled. Signal
     must collapse. If it doesn't, the model was pattern-matching artifacts — stop.
   - **Identity-known arm:** a small parallel arm (≤10% of months) scored WITH real country
     names/dates. If known ≫ blind, report both and treat the known arm as contaminated.
   - **Refusal/consistency check:** resample 2% of dossiers; sub-score agreement must be within
     tolerance (temperature 0, but API nondeterminism exists).
5. **Global-context ablation.** The one block that cannot be fully blinded (VIX, US 10Y, USD,
   oil, gold, GPR levels) is separately ablatable. We measure its marginal contribution so we
   know how much of the signal is regime memory vs. cross-sectional reasoning.
6. **Rationale audit.** The output schema requires a ≤120-word rationale citing dossier fields
   only. A random sample of rationales is human-audited for anachronism (any reference to
   events after t, or to real-world entities, voids the run and triggers a schema revision).

## 7. Input schema — `llm12m.dossier.v1`

One JSON dossier per (t, country). Versioned; any field-set change bumps the version and
re-freezes the protocol. All values are computed as of month-end t from PIT-safe surfaces.

```json
{
  "schema_version": "llm12m.dossier.v1",
  "country_token": "Country_K7",
  "t_index": 178,
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

Field dictionary (source → field) is maintained in the spec appendix at build time; every
field names its source table and whether it is revision-prone. Factor names are also tokenized
(`F_12`, `style_token_A`) — factor identity is recoverable from the key, not from the LLM.

`coverage` reports the fraction of non-null fields per block; the LLM is instructed to treat
`null` as "not available," never to invent values.

## 8. Output schema — `llm12m.output.v1`

Structured JSON, schema-validated, retry-with-corrections on parse/validation failure (max 3,
then the (t,c) cell is recorded as missing — never silently defaulted):

```json
{
  "schema_version": "llm12m.output.v1",
  "country_token": "Country_K7",
  "expected_12m_excess_pct": 4.2,
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

Sub-scores are on a −2..+2 scale with fixed definitions in the system prompt (the six
sub-scores above are the v1 set; changing them = schema v2).

## 9. The two model layers

### 9.1 Frozen LLM scorer (no training, ever)
- Single pinned model ID + temperature 0; model ID recorded per response; bulk scoring may use
  a mid-tier model with a flagship-model validation subsample (agreement reported).
- System prompt defines: the rotation task, the six sub-score definitions, the anti-leakage
  instructions (reason only from the dossier; never identify the country or period; treat nulls
  as unavailable), and the output schema. ≤3 prompt variants pre-registered; selection happens
  on train-period evidence only.
- Per-country independent calls (no cross-country contamination inside a context); the
  cross-sectional comparison is delegated to the combiner + evaluation layer, not to the LLM.
- All raw responses logged immutably (run directory, JSONL) before any parsing.

### 9.2 Ridge combiner (the only trained component)
- Target: `label_xs(t,c)` (12M excess). Features: the 6 sub-scores (+ optional expected_12m
  point estimate as a 7th), averaged over a small seed set if scoring is replicated.
- Walk-forward within the train window: expanding window, annual refits, 60-month burn-in —
  same pattern as `scripts/loop/build_combiner.py`.
- Regularization chosen by inner walk-forward only; no OOS peeking.
- Output per (t, c): predicted excess return → cross-sectional rank. Ranks are what the
  harness consumes.

## 10. Training-period protocol and the freeze list

On 2000-02 → 2014-12 ONLY:
1. **Block ablations** — drop each dossier block in turn; keep blocks whose sub-scores add
   rank IC vs `label_xs`. Report the full ablation table (including what was dropped — no
   silent truncation).
2. **Prompt selection** — among the ≤3 pre-registered variants, by train walk-forward rank IC.
3. **Ridge fitting** — walk-forward hyperparameters, final expanding fit through 2014-12.
4. **Calibration** — confidence → realized hit-rate mapping (for reporting only).

Then **freeze**, before any OOS scoring:
dossier schema (v1) · prompt (verbatim, hashed) · sub-score definitions · ridge spec + final
weights · evaluation metrics and baselines · canary thresholds.

Registration (repo law — every "signal works" claim is a charged trial):
- `ledgers/hypothesis_ledger.jsonl`: mechanism written BEFORE OOS results exist.
- `config/family_registry.yaml`: new family `llm_12m_country_rotation` (train-period
  ablations count as trials against the family; the registry entry must say so).

## 11. OOS evaluation (single pass)

- Score OOS months 2016-01 → 2025-06 (blinded), apply the frozen ridge, emit per-month
  cross-sectional ranks.
- Evaluate via `scripts/harness/evaluate_signal.py` conventions: rank IC + Newey–West t
  (overlapping-label HAC), top-7 vs EW benchmark, sub-periods (full / 5y / 3y / 1y), deflated
  Sharpe vs the family's trial count, **gross returns** (cost gates retracted 2026-07-13;
  implementation diagnostics only).
- `ff_spanning.py` check on the resulting long-short P&L: is it alpha or repackaged
  value/momentum/market beta?
- Canaries from §6.4 run in the same pass; any failure voids the run.
- Verdict language follows the ledger convention (STRONG / WEAK / DEAD), auto-attached to the
  hypothesis ledger.

## 12. Engineering plan (after this spec is approved)

```
experiments/llm12m/                     # committed: code + spec outputs only
  build_dossiers.py                     # DuckDB → dossier JSONL (PIT-checked, incremental writes)
  blind.py                              # token key management, blinding + unblinding
  score_llm.py                          # LLM batch scoring, raw-response log, schema validation
  combine_ridge.py                      # walk-forward ridge, frozen artifacts in/out
  evaluate_oos.py                       # harness-convention evaluation + canaries + verdict
Data/work/experiments/llm12m/           # gitignored: dossiers, raw responses, run dirs
  runs/YYYY_MM_DD_HHMM/                 # self-contained run dir: JSON summary + log + outputs
```

- **Incremental writes everywhere** (repo rule): dossiers append JSONL per month; raw LLM
  responses written before parsing; a run is resumable from any month.
- **Never hold a DuckDB connection**; extract with short read-only sessions
  (`duckdb_lock_guard.guarded_connect()`), close, then process.
- Avoid the 06:00–08:30 PT nightly window for long runs.
- Volume: ~10.3K dossiers total (train 6.1K + OOS 4.3K incl. canary replicates) — batch API,
  modest cost; log token usage per run.
- Nothing here touches `Data/processed/`, `Data/loop/`, shared `Data/work/`, `config/`, or
  `ledgers/` except the two explicit registration writes in §10.

## 13. v2 extensions (explicitly out of scope for v1)

- **GDELT `monthly_metronome` block** (2015-09+): cannot exist in the 2000–2014 train window;
  v2 studies it as an OOS-era augmentation with its own registration.
- Cross-country LLM ranking pass (all 34 score-cards in one context) — v1 keeps per-country
  blind calls to preserve the blinding guarantee.
- Sovereign/market-implied/ETF-flow loop layers (many start 2021+) — same coverage problem.
- Prospective deployment: if OOS survives, a forward paper-thesis arm via `ledgers.py` /
  thesis ledger with sealed rationales (the journal's `sealed_rationales/` pattern).

## 14. Open questions for Arjun

1. Embargo placement assumes OOS starts 2016-01 — acceptable, or prefer train through 2013 and
   a 2-year buffer?
2. The six sub-scores in §8 — is that the right decomposition, or do you want a
   "news/sentiment" sub-score slot reserved (null in v1) so v2's metronome block drops in
   without a schema break?
3. Model choice for bulk scoring: pin one model end-to-end for cleanliness, or allow the
   mid-tier-bulk + flagship-subsample split with an agreement report?
4. Should the permutation canary failure void only the run, or the whole family (i.e., is one
   failed canary a kill-shot for LLM-12M)?
