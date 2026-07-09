---
name: asado-graveyard
description: >-
  The record of ASADO research battles that are already SETTLED — ideas tested and killed — so no one re-fights them. READ THIS AND RUN ITS PROTOCOL BEFORE proposing, registering, or building ANY new research idea, signal, factor, regime scheme, or combiner in this repo (triggers: "let's try...", "what if we test...", "new signal/factor idea", "regime conditioning", "ML combiner", "should we backtest X"). It answers "has this already been killed, and what did we learn?" and gives the exact check-before-proposing order. Do NOT use this skill for operational/code failures (a job crashed, a DB lock, a launchd job failing) — that is asado-debugging-playbook. Do NOT use it to learn HOW to run an experiment or the harness lifecycle — that is asado-research-protocol. This skill records RESEARCH verdicts, not bugs.
---

# ASADO Graveyard — Settled Battles

Everything here is light-mode plain markdown. This is a **read-before-you-propose** reference. It records research ideas that were tested and are dead (or explicitly not-yet-settled), with the evidence file and the one-line lesson from each.

> **Why this skill exists.** Re-proposing a dead end is the fastest way to lose the user's trust (CLAUDE.md "Quant Research Guardrail"). Autonomous agents in this repo have a documented habit of re-deriving things the record already settled, and of "discovering" passes that don't survive honest re-derivation. Check the record first.

---

## 1. THE PROTOCOL — run this before proposing ANY research idea

Before you propose, register, or build a new signal / factor / regime scheme / combiner, check **all four** sources, in this order. Do not stop at the first.

**(a) This skill's graveyard table** (§2 below). Scan for the mechanism you're about to propose. If it's there and marked DEAD, STOP — do not re-propose it. If you believe you have new evidence that overturns a DEAD verdict, that is allowed, but you must say so explicitly to the user and treat the old verdict as the prior to beat.

**(b) The hypothesis ledger** — `ledgers/hypothesis_ledger.jsonl`. This is the append-only event log of every registered hypothesis and its harness verdict. List the final verdict per hypothesis with this jq-free, grep-free one-liner (only stdlib `python3`; it reads the JSONL data file, runs no repo code, opens no DuckDB):

```bash
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO" && python3 -c '
import json, collections
last = {}
for line in open("ledgers/hypothesis_ledger.jsonl"):
    line = line.strip()
    if not line:
        continue
    o = json.loads(line)
    if o.get("event") == "hyp_verdict":
        vj = o.get("verdict_json", {})
        last[o["hypothesis_id"]] = (o.get("verdict"), vj.get("family_key", ""), vj.get("deflated_sharpe"))
print("hypotheses with a verdict:", len(last))
print("counts:", dict(collections.Counter(v for v, _, _ in last.values())))
for hid, (v, fam, dsr) in sorted(last.items()):
    print(f"{v:22} {fam:24} dsr={dsr}  {hid}")
'
```

**Expected output (verified 2026-07-08):** `hypotheses with a verdict: 59` and `counts: {'WATCH': 1, 'DEAD': 21, 'WEAK': 21, 'INSUFFICIENT_COVERAGE': 16}`. If your run returns different totals, the ledger has grown since this skill was written — trust the ledger, not this number, and update §2/§3.

> **CRITICAL — why you MUST dedupe to the last verdict per hypothesis.** A hypothesis gets a *fresh* `hyp_verdict` event on every re-run, so a naive count of all `hyp_verdict` events returns **89** (32 DEAD, 39 WEAK, 16 INSUFFICIENT, 2 WATCH) — wrong. The canonical number is the **final** verdict per `hypothesis_id`, which is 59. Any one-liner you write or copy must keep only the last verdict per id.

Ledger schema (verified `ledgers/hypothesis_ledger.jsonl:1-3`): each line is one JSON object with an `event` field ∈ {`hyp_register`, `hyp_verdict`, `hyp_status`}. Registration carries `family_key`, `mechanism_text`, `signal_spec.{table,variable,source}`. Verdicts carry `verdict` ∈ {WATCH, WEAK, DEAD, INSUFFICIENT_COVERAGE} and `verdict_json.deflated_sharpe`. `hyp_status` events carry a free-text `note` (this is where leakage retractions and blacklistings are recorded).

**(c) Experiment-directory RESULTS.md files.** Some kills live ONLY as an experiment write-up and never got a ledger row (see the law below). Check:
```bash
cd "/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO" && find . -maxdepth 3 -iname "RESULTS.md" -not -path "*/node_modules/*" 2>/dev/null; ls regime2.md docs/strategy/lessons.md 2>/dev/null
```

**(d) The external "Investment Learnings" graveyard** (the book's cross-project ledger, outside this repo):
- `/Users/arjundivecha/Dropbox/AAA Backup/A Complete/Investment Learnings/INDEX.md` — one-line-per-project tested-and-rejected ledger.
- `/Users/arjundivecha/Dropbox/AAA Backup/A Complete/Investment Learnings/Research-Agenda-2026-07-v2.md` — **the latest version governs** (`-v2` supersedes the un-suffixed `-2026-07.md`). Its §0.2 lists dead mechanisms; §0.3 is "The Six Laws" (reproduced in §4 below).

### THE LAW that makes all four steps mandatory

**The ledger alone is NOT the graveyard.** `regime_ew` died at Gate 3 (walk-forward own-country lead) with **no hypothesis-ledger entry at all** — its death is recorded only in `regime_ew/results/RESULTS.md:5-11`. If you check only the ledger (step b) you will miss it and can waste days rebuilding it. The canonical graveyard = **ledger + experiment RESULTS.md + `docs/strategy/lessons.md` + Investment Learnings**. (Evidence: git-archaeologist read of `origin/claude/nightwatch-06-20-failures-37d4lv`; RESULTS.md verified present, no matching ledger id found by the one-liner above.)

**Companion law — DISTRUST A SEARCHED PASS.** Any PASS that an autonomous tuning/optimization loop *found* is presumed false until it is re-derived from pre-registered, corrected inputs. See `regime` v1 in the table: a v1 "PASS" flipped to DEAD once the inputs were fixed. A green metric that a search process optimized toward is not evidence; it is the thing the search was gaming.

---

## 2. The Graveyard Table — settled RESEARCH battles

All verdicts and DSRs below were re-verified against the cited files on 2026-07-08. DSR = deflated Sharpe. "Ledger id" columns point to `ledgers/hypothesis_ledger.jsonl` (query by id with the one-liner in §1b).

**What "Gate N" means in this table (read before interpreting verdicts).** Each directory
experiment pre-registers its OWN numbered gate ladder in its PRD, and "died at Gate N"
refers to *that experiment's* ladder — e.g. `regime_ew`'s ladder was Gate 1 = states are
persistent, Gate 2 = states are not just a volatility proxy, Gate 3 = states lead
own-country returns walk-forward out-of-sample (`regime_ew/results/RESULTS.md`). There is
no universal ladder. In particular, do NOT confuse these per-experiment gates with (a) the
harness verdict gates in **asado-research-protocol** STEP 6, or (b) the leakage campaign's
G1–G5 in **asado-leakage-guard-campaign** — three unrelated numbering schemes. The common
pattern worth internalizing: the *last* gate is almost always "does it hold walk-forward
out-of-sample?", and it is where most experiments die after full-sample fits looked good.

### Directory experiments (the big builds)

| # | Name | Hypothesis (what was tested) | Verdict | Evidence | Date | One-line lesson |
|---|------|------------------------------|---------|----------|------|-----------------|
| 1 | `regime/` (v2) | Do factor ICs vary across global macro regimes enough to condition on? | **DEAD** | `regime2.md:12-18` — H1 persistence 0.729 (FAIL, need ≥0.75); H2 **0/52** factors significant post-BH-FDR; H3 Sharpe Δ +0.078, only 7.1% of 5y windows beat baseline | 2026-05-23 | Global macro regimes can't reorder cross-sectional country ranking. |
| 1a | `regime/` **v1 provenance** | Same idea, earlier run that reported a **PASS**. | **PASS WAS FALSE** | `regime2.md:22-30` documents v1 (`regime.md`, now superseded; last in history at commit `83e03a7`) was overturned by data-sourcing + logic corrections. Contract canon links the false pass to `regime_loop` autonomous tuning. | superseded 2026-05-23 | A pass a search loop found is presumed false until pre-registered re-derivation. **[provenance: the corrections are documented in regime2.md; the causal attribution to `regime_loop` gaming is the handover's synthesis — treat as the house law, not a quote from regime2.md.]** |
| 2 | `regime_loop/` | Autonomous loop that tunes a regime scheme until it "passes". | **DEAD (self-defeating)** | `regime_loop/output/state.json`: `best_metrics.all_pass = 0.0`, `best_primary_metric = 0.0`, `loop_status = "error"` — **zero honest successes** | 2026-05-25 run | An optimizer pointed at the pass/fail metric games the metric; the loop produced no real win. **[the "0 successes / 13 attempts, agents modified forbidden files" figure is from the miner's read of run history; the current state.json shows all_pass=0.0 and loop_status=error but retires=0 — 0-successes is verified, the "13 attempts / gaming" count is UNVERIFIED from this snapshot.]** |
| 3 | `regime_ew/` | Per-country HMM regime as an early-warning signal with walk-forward own-country return lead. | **DEAD (Gate 3)** | `regime_ew/results/RESULTS.md:5-11` — Gate 3 own-country lead FAIL: **17/34** countries negative (need ≥23), median ρ −0.003 (need ≤−0.10), spread −0.68%/mo | 2026-06-21 | Full-sample fit looked significant = look-ahead artifact caught by the walk-forward gate. **Has NO ledger entry — the founding example of the law above.** |
| 4 | `regime_factor_selection/` | Conditioned on each country's own IP regime, does any T2 factor's rank-IC differ by regime? | **DEAD (clean null)** | `regime_factor_selection/results/RESULTS.md:5-13` — **0 of 74** factors clear FDR (α=0.10); placebo (shuffled labels) collapses raw hits 18→8, confirming machinery is calibrated | 2026-07-05 | A pre-registered, placebo-confirmed null — the *cleanest* kind of dead end. Untracked dir. |
| 5 | `momentum_fragility/` | Within hot-momentum names, does higher "fragility" predict lower forward return? | **DEAD (Gate 3, both variants)** | `momentum_fragility/results/RESULTS.md:5-13` — core ρ=−0.0135 spread −11.4bp (n=2108); full ρ=**+0.0301** (wrong sign) spread −93bp; need ρ≤−0.10 | 2026-07-05 | Fragility-conditioned reversal doesn't exist at monthly horizon. Untracked dir. |
| 6 | Strategy #1 — PCA-stacked cross-section regime analogs | Build worldstate→PCA→analog→aggregate→backtest to pick countries. | **DEAD (NO-GO)** | `docs/strategy/lessons.md:1-20` (memo `analogs/v1/go_no_go.md`); killed in ~5h at commit `fbef913` | 2026-05-08 | PCA is misspecified when features (~2,900-dim flat vector) ≫ samples; sticky-basis, IC≈0. Kept 5 reusable primitives, trimmed the rest. |

### Ledger DEAD families (killed on negative/near-zero deflated Sharpe)

Query any id with the §1b one-liner. All DSRs verified in-ledger 2026-07-08.

| Family / signal | Hypothesis | Verdict | Ledger evidence | Lesson |
|-----------------|-----------|---------|-----------------|--------|
| `momentum_sanity` — `12-1MTR_CS` | 12-minus-1-month country momentum should positively predict next month. | **DEAD** | DSR **−0.1296** (id `H_20260610_002`) | Even the "well-documented" cross-sectional momentum effect is dead net of the harness's DSR haircut on this universe. |
| `bbg_skill_2026_06` (**9 killed**) | Bloomberg-sourced macro/FX signals: FX carry level (`FX_CARRY_3M_PCT` −0.058) & change (`FX_CARRY_Z252` −0.077), inflation surprise (`ECO_INFL_SURPRISE_Z` −0.541), FX implied-vol term (`FX_VOL_TERM_Z252` −0.154) & level (`FX_IMPVOL_Z252` −0.107), risk-reversal (`FX_RR25_Z252` −0.096), butterfly (`FX_BF25_Z252` −0.116), 2s10s slope (`SOV_2S10S_Z252` −0.062), growth surprise (`ECO_GROWTH_SURPRISE_Z` −0.394). | **DEAD ×9** | family `bbg_skill_2026_06` (also 6 INSUFFICIENT, 1 WEAK) | First-order FX/rates/macro-surprise signals die on this universe (matches external Law 3). |
| `valuation_2026_06` (**4 killed**) | Country valuation percentiles mean-revert: CAPE (`VAL_CAPE_PCTILE_10Y` −0.139), ERP (`VAL_ERP_PCT_PCTILE_10Y` −0.188), dividend-yield (`VAL_DY_PCT_PCTILE_10Y` −0.112), raw earnings-yield rank (`VAL_EY_PCT` −0.068). | **DEAD ×4** | family `valuation_2026_06` | Own-history valuation percentiles do not time country returns. |
| `etf_flows_2026_06` (**2 killed**) | ETF flow z-score / short-interest ratio predict country returns. | **DEAD ×2** | family `etf_flows_2026_06` | Flow/positioning signals dead here (external agenda: ETF-flow contrarian only t −2.2). |
| `graph_trade_gap` (**2 killed**) | Trade-network fire-sale / neighbor-drawdown contagion. | **DEAD ×2** (12 WEAK) | family `graph_trade_gap` | At daily horizon, gross LS Sharpe 0.57 → net −1.03 at 25bp (external agenda §0.2) — turnover eats it. |
| `consensus_ecfc_2026_06` | GDP consensus / revision-momentum cross-sectional. | **DEAD ×1** | family `consensus_ecfc_2026_06` | Consensus-revision momentum does not survive. |
| `ml_combiner_2026_06` — `COMBINER_RIDGE_V1` | Walk-forward ridge over the **seven harness survivors**. | **DEAD** | DSR **−0.1881** (family `ml_combiner_2026_06`) | A combiner built only from prior survivors inherits an in-sample selection ceiling — combining survivors ≠ new alpha. |
| `triptych_prior_2026_07` — `TRIPTYCH_QUEUE_LEAN` | PIT conditional-history "queue lean" rule as a hard signal. | **DEAD → demoted** | DSR **−0.1935** (id `H_20260702_001`) | The one **graceful downgrade**: killed as a standalone signal, kept as a *context/prior-tier* input only (external agenda §0.2: "Triptych queue lean (context tier only)"). Cleanest pre-register→test→kill workflow (built `2d2ecb5`, dead `ce15611`, ~15h). |

### Governance-caught leaks (not "ideas", but load-bearing kills)

| What | What happened | Evidence | Lesson |
|------|---------------|----------|--------|
| 12MRet leakage | `momentum_sanity` first trial (`H_20260610_001`) posted a WATCH with IC 0.25 / NW-t 15.4 — then retired: `12MRet` is a forward return labeled at window start (an optimizer TARGET). | `ledgers/hypothesis_ledger.jsonl:1-3` (`hyp_status` note "LEAK … now blacklisted") | A too-good IC is a leak signal, not a discovery. Forward-return family (`NMRet`/`12MRet` etc.) is permanently blacklisted as a predictor. |
| Taiwan short thesis | `T_20260610_003` killed same-day on a calendar-misalignment bug (gap_z −2.28 → −1.11). | miner finding (thesis ledger) | A live thesis can die to a data-alignment bug, not a market view — always check the input pipeline before trusting the score. |

---

## 3. External earned laws — the six that govern all new proposals

These live outside the repo, in `Research-Agenda-2026-07-v2.md:57-67` (§0.3 "The Six Laws"). **The v2 file is the governing latest.** Reproduced faithfully; read the source for the full framing:

1. **The cost law.** In the country-ETF ledger, **nothing survives 25bp one-way**; only 4 signals clear 10bp; 12 clear 5bp. The flagship combiner's own habitat costs 9.4–10bp. → New ideas must be near-zero-turnover, be *paid for* providing liquidity (premia), or move to venues costing 1–3bp (futures, FX).
2. **The expression law.** Index-space alpha ≈ **zero in the US-listed ETF at the US close**. US-hours market makers embed cross-market public info; the opening auction prints overnight info. → The venue and the clock are first-class research variables.
3. **The second-order law.** First-order macro signals die in the harness (**31 DEAD**, disproportionately first-order); what survives is *delayed second-order propagation* (graph, lead-lag, similarity twins, combiner) — in index space, with a 2024–26 sign flip currently unexplained.
4. **The hit-rate law.** Per-mechanism true-positive rate is **~15–20%**. Family-count DSR haircuts are mandatory; a WATCH verdict is a lottery ticket, not a sleeve.
5. **The real-engine law.** Proxy engines lie (AA/HTP false positive; QC corrupt opens; Corwin-Schultz inflates). Signal swaps are tested in the production stack or not at all.
6. **The arithmetic law.** The only edges that never decay are guaranteed by arithmetic or statute: execution quality, netting, financing, tax. They compound and cannot crowd.

Also in `Investment Learnings/INDEX.md` (verified): naive 13F cloning DEAD post-2015; 200-week-quality does NOT transfer to international; JKX-2023 CNN candlestick pattern has **no surviving ETF deployment path**; T2 130-30 short side abandoned (costs eat ~60%); ElasticNet/IPCA-ridge PIT audits fabricated their alpha; residual forecasting DESTROYED the strategy (common component *is* the alpha); TabFM zero-shot KILL.

---

## 4. The living frontier — what is NOT settled (do not put these in the graveyard)

So a reader doesn't mistake open work for dead work:

- **Daily combiner** — LIVE, but carries a known **in-sample ceiling caveat** (see `ml_combiner` lesson: a combiner over survivors can't manufacture new alpha). Improving it is open; assuming it's clean is not.
- **`Demographics_Inflation_Factor/`** — BUILT (UN WPP + BIS coefficients; `build_dip_factor.py`, `ASADO_DIP_factor.xlsx`, panel CSVs present) but **never backtested**. Genuinely open candidate — no verdict exists yet, so do not cite it as either alive or dead.
- **Brier Gate** (Polymarket/US prediction-market conditioning) — **ON HOLD**.
- **DeepSeek shadow** — parallel shadow eval, open.
- **Open theses:** Indonesia long, Hong Kong long — both open, with a **double-counting risk** flagged (they may overlap existing exposures; verify before staking).
- **WEAK tier — 21 entries.** Not dead, but not promising. A WEAK verdict failed to clear WATCH (which requires ALL of: NW-t ≥ 2.5, ≥60% positive-IC years, net-25bps LS Sharpe > 0, deflated Sharpe > 0). Treat WEAK as "parked, needs a materially better formulation," not "kill" and not "green."
- **INSUFFICIENT_COVERAGE — 16 entries.** Undecided for lack of data span, not a verdict on the idea.

The lone **WATCH** (`H_20260610_003` graph_trade_gap variant) is a lottery ticket per Law 4 — not a sleeve.

---

## 5. How to add a new grave (do it properly)

When something dies, record it so the *next* reader's protocol (§1) catches it. Follow `asado-research-protocol` for the full lifecycle; the minimum for a durable kill is **all three**:

1. **Ledger event.** Append a `hyp_verdict` with `verdict: "DEAD"` (and, if a leak/retraction, a `hyp_status` event with a `note`) to `ledgers/hypothesis_ledger.jsonl`. Never hand-edit prior lines — it's append-only.
2. **Experiment RESULTS.md.** If the idea had its own directory, write/finish `<dir>/results/RESULTS.md` with the executive verdict and the decisive gate. This is what saves ideas the ledger misses (the `regime_ew` law).
3. **The one-line lesson.** Add a row to §2 of this skill (name, hypothesis, verdict, evidence file:line or ledger id, date, lesson) — and, if it's a cross-project learning, a line in `Investment Learnings/INDEX.md`.

Per the user's global **FAIL IS FAIL** rule: do not simulate a kill or a pass. A verdict is only real if the harness produced it on honest, pre-registered inputs. If a fix to the collector or T2 feed is needed to run the test, append to `docs/USER_FIX_LIST.md` and ask before fixing — see `asado-research-protocol` and `asado-change-control`.

---

## 6. When NOT to use this skill

- **An operational thing broke** (a job crashed, DuckDB lock, launchd job exit 1, Neo4j down, a NameError in the nightly loop) → use **asado-debugging-playbook**. This skill records research verdicts, not code bugs. A wrong runbook is worse than none.
- **You need to RUN an experiment / understand the harness→ledger lifecycle** → use **asado-research-protocol**.
- **You're orienting in the repo / need the doc-authority router** → use **asado-start-here**.
- **You need the data contracts, invariants, or weak points** → use **asado-architecture-contract**; **how changes are gated + the house-law incidents** → **asado-change-control**.
- **A DEAD entry looks overturnable.** Allowed — but say so explicitly to the user, treat the prior verdict as the bar to beat, and re-derive from pre-registered inputs (the "distrust a searched pass" law). Never quietly re-propose a dead idea as if it were new.

---

### Cross-references
`asado-research-protocol` · `asado-change-control` · `asado-debugging-playbook` · `asado-start-here` · `asado-architecture-contract`
