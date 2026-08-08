# Boundaries-of-TSM — schema audit + step-zero prior art

**Date:** 2026-08-08 · **Status:** audit COMPLETE · panel BUILT (experiment-scoped, see §6b) · replication not started
**Hand-off:** `llmchat-session-2026-08-08-boundaries-tsm.md` (Claude.ai, 2026-08-08 00:28 PST)
**Scripts:** `schema_audit.py` (read-only) · `build_boundaries_panel.py`
**Artifacts:** `results/schema_audit.xlsx`, `results/coverage_long.parquet`, `results/schema_audit_summary.json`

---

## 1. Headline

**All 50 audited variables exist. Nothing needs to be fetched. But the usable sample is
roughly half what the hand-off assumed, and two of the program's first-choice variables sit
on a documented look-ahead landmine.** The return basis is USD — the same as the traded
ETFs — which removes what looked like the program's biggest measurement decision.

---

## 2. The six audit questions

| # | Question | Answer |
|---|---|---|
| a | Short rate for 10y−3m? | **YES.** `BIS_Policy_Rate` (30 ctry), `IMF_TBill_Rate` (20), `IMF_Money_Market_Rate` (26), `IMF_Discount_Rate` (10) — **28 of 34** T2 countries have at least one. Long leg: `BBG_Govt_Bond_10Y` (32), `10Yr Bond` t2 (33). `BBG_Govt_Bond_2Y` covers only **27**. Build **both** 10y−3m and 10y−2y; 10y−3m actually has *better* country coverage than 10y−2y. No short rate at all: France, Germany, Netherlands, Singapore, Taiwan, Vietnam. |
| b | REER present? | **YES, twice.** `BIS_REER` (external_factors, 33 of 34) and `REER` (t2_raw, 34). **No BIS fetch needed.** But see §4 — the duplication is a hazard, not a bonus. |
| c | Local-currency returns? | **T2 returns are natively USD** (owner-confirmed, then independently verified — see §4c). The **local** leg is the one that must be constructed, via the `Currency` series. Either way idea #8 is a query, not a Bloomberg pull. |
| d | Valuation fields | **Rich.** `Shiller PE` (a real CAPE analog, 29 ctry) — strictly better than the paper's dividend-yield-only international leg. Plus `Trailing PE`, `Best PE`, `Positive PE`, `Earnings Yield`, `Best Div Yield`, `Best Price Sales`, `Best PBK`, `Best Cash Flow`, `EV to EBITDA`. |
| e | Current account / reserves | **YES.** `IMF_BOP_Current_Account`, `WB_Current_Account_GDP`, `Current Account` (t2); reserves via `WB_FX_Reserves`, `WB_Import_Cover_Months`, `MS_Reserve_Adequacy`. **Do not use `IMF_WEO_CA_GDP`** — see §4. |
| f | Effective start after 10y window | See §3 and the `coverage_effective_start` sheet. |

Also answered (open question 5): `predmkt_market_meta` category coverage is in the
`predmkt_coverage` sheet; `predmkt_daily` is thin (10,258 rows) — idea #9's ex-ante policy-odds
leg is DM-only at best, as the hand-off suspected.

---

## 3. The binding constraint: the warehouse floors at 2000

This is the most consequential finding and it is worse than the hand-off assumed (it
budgeted the paper's 1989–2024, ~35 years).

| Normalization choice | Sample starts | Usable span to 2026-07 |
|---|---|---|
| Own-history 10y window on momentum (`12MTR` starts 2001-02) | **2011-02** | **~15.4 years** |
| Peer-relative (cross-sectional) — no history burned | **2001-02** | **~25.4 years** |
| Own-history 10y on the forward-estimate valuation fields (`Best *` start 2005-06) | **2016-03** | **~10.4 years** |

Consequences:

1. **Peer-relative normalization (hand-off idea #3) is worth ~+10 years, i.e. ~65% more
   sample.** The hand-off's instinct to build it first-class rather than as a robustness
   check is now quantified and correct. It is the single highest-leverage design decision.
2. **Prefer `Shiller PE` / `Earnings Yield` / `Trailing PE` (start 2000-02) over the `Best *`
   forward-estimate family (start 2005-06)** for the valuation leg. Using `Best Div Yield`
   would cost ~6 more years on top of everything else.
3. With ~15 years of *overlapping* 12-month returns there are only ~15 independent
   observations per country. **13 hypotheses against that is severely
   underpowered.** Pre-registration and a hard shortlist matter more than the hand-off
   assumed — this is not a "run all 13 and see" program.

---

## 4. Two landmines (both verified this session, not merely cited)

### 4a. `IMF_WEO_*` are future-dated to 2031 and are BANNED

Investment Learnings *T2 Factor Timing Fuzzy ElasticNet PIT Audit* requires "total exclusion
of IMF WEO forecast variables (forward values to 2031 with no vintage tracking — unfixable
by lagging)". **Confirmed live in the warehouse right now:**

```
IMF_WEO_CA_GDP      1980-12-01 -> 2031-12-01   FUTURE-DATED: True
IMF_WEO_Debt_GDP    1980-12-01 -> 2031-12-01   FUTURE-DATED: True
IMF_WEO_GDP_Growth  1980-12-01 -> 2031-12-01   FUTURE-DATED: True
```

The trap is that **`IMF_WEO_CA_GDP` looked like the single best variable in the whole
audit** — history to 1980, effective start 1990, 43 countries, by far the longest series
available. It is poisoned. Any panel that reaches for "the longest current-account history"
picks it up automatically. **Excluded.**

### 4b. REER exists in BOTH date conventions — the exact documented smoking gun

The same Investment Learnings entry records that a 1-month date-convention look-ahead in
`feature_panel` **fabricated +5.1%/yr, +0.28 Sharpe and +0.82 active IR**, and that the
smoking gun was "Australia REER existing in both conventions offset by exactly one month".

**Reproduced exactly, this session, on Australia:**

```
aligned same-date corr : 0.9824   (n=316)
BIS shifted +1 month   : 0.9982   (n=317)    <-- the +1m shift is the better fit
```

T2/Bloomberg stamps **first-of-NEXT-month** (PIT-safe); BIS/IMF/OECD/WB/EPU stamp the
**reference period**. At any shared date the non-T2 copy is one month more current.

This matters more here than in any prior project because **REER is the program's
first-choice boundary variable** (idea #1's prior is "REER + credit gap beat valuation";
idea #8 calls REER extremes "the cleanest boundary in finance"). The panel as specced would
join *both* copies, and the ElasticNet audit found the regularized model "loaded hardest on
the look-ahead copies".

**Required:** per-source lag dict (convention +1 **plus** publication lag: BIS/IMF/OECD 3,
EPU 2, WB QPSD 5, BBG-direct 1), and never both REER copies in one design matrix.

---

### 4c. Currency basis: T2 is USD — and how an earlier claim here got it backwards

**T2 returns are USD.** Owner-confirmed 2026-08-08, then verified against an independent
source: T2 monthly returns vs the US-listed country ETFs in FDT's `fdt_prices.duckdb`
(unambiguously USD), after shifting T2 back one month to undo its first-of-next-month
stamping. **T2 as-is beat the de-FX'd version in 5 of 6 countries:**

| | T2 as-is vs ETF | T2 de-FX vs ETF |
|---|---|---|
| Brazil | **0.9870** | 0.9737 |
| Mexico | **0.9679** | 0.9508 |
| Turkey | 0.9722 | 0.9722 (tie) |
| Japan | **0.9343** | 0.9117 |
| South Africa | **0.9351** | 0.9280 |
| Korea | **0.8376** | 0.8336 |

An earlier version of this document claimed the opposite ("T2 is natively local") and called
it empirically verified. **It was not.** That test compared `12MTR` against `pct_change(Tot
Return Index)` and against a currency-converted version of the *same* series — both branches
shared TRI as their base, so the test could only establish that `12MTR = pct_change(TRI)`.
It was structurally incapable of identifying the currency basis. The "local" label came
entirely from `variable_registry_full`, whose `review_status` is **`model_drafted`** —
LLM-written, never human-verified — which this document had already flagged as untrustworthy
and then relied on anyway.

Two lessons worth keeping:
- **`model_drafted` registry metadata is not evidence.** Roughly 1,587 rows of
  `variable_registry_full` carry that status. Treat every one as a hypothesis.
- **Identifying a currency basis requires an EXTERNAL reference.** No amount of internal
  consistency-checking between T2 columns can do it, because they share the same base series.

A side benefit: this exercise independently confirmed the **first-of-next-month stamping**.
Correlations against the ETFs were ~0.0 on the raw dates and jumped to 0.84–0.99 once T2 was
shifted back one month — the same convention the ElasticNet PIT Audit documents, now
observable in the returns themselves.

**Implication for idea #8:** the FX decomposition still costs nothing, but the direction
flips — `local = (1 + r_usd) × (1 + ΔFX)`. The panel carries both, and the U.S. sanity check
returns exactly 0.0000 difference (FX ≡ 1), as it must.

---

## 5. Why the panel was NOT written to the warehouse

**The hand-off specifies an unsafe home.** It says "`boundaries_panel` in `asado.duckdb`,
strictly additive". `setup_duckdb.py` **deletes and recreates `Data/asado.duckdb`** — a
persistent table there is destroyed on the next monthly rebuild. The hand-off was written
without repo access; this is not a criticism of it, but it must not be followed as written.

The panel is therefore built as **experiment-scoped parquet** under
`experiments/2026_08_boundaries_tsm/results/`, which is the sanctioned location and needs no
change-control decision. Promoting it to a durable warehouse home (loop DB, or a builder
script the monthly rebuild re-runs) is a separate, deliberate step — and Arjun's call.

---

## 6. Prior art (step zero) — no kill, one strong caution

**Quantpedia mirror (1,312 strategies, synced 2026-08-04), five phrasings: no `DIES_BOTH`.**

- `#0862` *Switching Between Momentum and Reversal Based on Market Volatility* — **OURS_ONLY,
  screen rank 1/97**, IR 0.65 full, net +8.56%/yr. Structurally the closest analog to
  Boundaries (switch momentum↔reversal on a state variable) and it is our **best-ranked
  screened strategy**. Encouraging, but OURS_ONLY = "treat with the same skepticism as any
  surprisingly-good backtest".
- `#0342` *Global Cross-Asset TSMOM* — **by Suominen himself**; tracked OOS Sharpe 0.50
  inception / 0.52 5y, +3.80%/yr. Same author's prior TSMOM work has a real, modest OOS record.
- `#0015` *Momentum in Country Equity Indexes* — OURS_ONLY, rank 28/97, IR 0.14 (weak);
  `#0404` *Alpha Momentum in Country Indexes* — OURS_ONLY, rank 19/97, IR 0.22.
- `#0118` *Time Series Momentum* (Moskowitz-Ooi-Pedersen, the MOP index the paper uses):
  **UNSCREENED** — never run through our country-ETF screen.

**Investment Learnings — the caution that matters:**

*Regime EW* records that "**regime TIMING is not alpha in this stack**" (macro-regime tagger
passed persistence 0.793 and conditional-IC but failed strategy value, 47.2% vs a 60% bar),
that "**regime taxonomies do not reorder the cross-section**" (Alpha Book v2 graveyard), that
cross-sectional ranking of independently-fitted HMM posteriors **loses money**, and
`regime_factor_selection` was 0/74 on placebo. Own-history *time-series* calibration is the
one thing that worked (gross Sharpe ~0.72 contrarian overlay).

This is a genuine prior against ideas #5 and #13 — but it is **not** a kill, for a specific
reason the record itself supplies: that entry's open question is whether the failure is the
independence assumption, and it notes HMMs are return-driven. Boundaries conditions on
**valuation/REER LEVELS**, which return-driven HMMs are structurally blind to. That is
precisely hand-off idea #13's hypothesis. The prior does say the burden of proof is high and
that the *time-series* expression is the one with a track record here — which argues for
sequencing the TS-conditioning tests ahead of the cross-sectional ones (#5).

---

## 6b. The panel is built (experiment-scoped) — and it settles the normalization question

`build_boundaries_panel.py` → `results/boundaries_panel.parquet`
**12,779 rows × 74 columns, 34 countries.** Three normalizations per state variable
(`__own_pct`, `__peer_pct`, `__paper_pm1`), both return bases (local + constructed USD),
and the paper's Boundaries variable built to its exact spec (12m MA → [−1,1] vs trailing
10y min/max → sum of squares), plus its footnote-2 absolute-value variant.

**The paper's own method is the most expensive choice available, by a wide margin:**

| Boundaries construction | Obs | Countries | Starts |
|---|---|---|---|
| Paper exact (10y2y + CAPE) | 2,704 | **18 of 34** | 2010-12 |
| Paper exact (10y3m + CAPE) | 2,243 | 17 | 2011-02 |
| Paper exact (10y2y + Div Yield) | 2,212 | 22 | 2016-03 |
| **Peer-relative (10y2y + CAPE)** | **6,060** | **23** | **2001-02** |

Peer-relative delivers **2.24× the observations, +5 countries and +10 years**. On this
warehouse the paper's trailing-min/max method reduces a 34-country study to an 18-country
one. Hand-off idea #3 is not a robustness check — it is the only construction with enough
data to support 13 hypotheses.

**A defect found and fixed in the build:** BIS credit gap and property prices are
*quarterly*, WB reserves *annual*. On a monthly grid a 120-**month** rolling window never
reaches `min_periods`, so those variables silently produced **zero** usable observations
under both own-history and the paper's normalization — including `credit_gap`, one of idea
#1's two prior favourites ("REER + credit gap beat valuation"). Forward-filling each
low-frequency series (cap 11 months — which is also what a live user genuinely knows: last
quarter's print stands until the next) restored four variables:

| State var | Before | After (own_pct) |
|---|---|---|
| `credit_gap` | 0 obs / 0 countries | 5,981 / 31 |
| `property_price` | 0 / 0 | 5,355 / 31 |
| `current_account` | 0 / 0 | 6,135 / 33 |
| `fx_reserves` | 0 / 0 | 5,873 / 33 |

Anyone building this panel without noticing would have concluded the credit-gap hypothesis
was untestable, when it is merely quarterly.

**Not built:** the DIP-anchored ("moving anchor", idea #4) normalization. It needs a
demographic fair-value model that does not exist yet; a placeholder would be worse than its
absence. Recorded as open.

---

## 7. Recommended next actions (for Arjun's call)

1. **Decide the panel's home** (loop DB vs experiment parquet vs regenerated builder) — blocks the build.
2. **Return basis — RESOLVED: T2 is USD**, the same basis as the traded ETFs, so the
   default requires no conversion and no decision. The panel also carries a constructed
   local leg for idea #8 (Brazil differs by 15.8pp on average, Turkey 12.3pp, Japan 8.1pp,
   U.S. 0.0000pp).
3. **Pre-register a shortlist** far smaller than 13, given ~15 independent 12m observations.
4. Then replication (sequencing step 1) via `asado-research-protocol` — snapshot + pre-registration,
   not ad hoc.

## 8. Gotcha for whoever writes the panel

`12MRet / 1MRet / 3MRet / 6MRet / 9MRet` are **FORWARD** returns (optimizer targets, labeled
at window start) and are hard-blacklisted — `evaluate_signal.py` raises on them. The paper's
"past 12-month return" is **`12MTR`** (or `12-1MTR` for the skip-month version). The names
are one character apart and grabbing the wrong one is silent look-ahead.
