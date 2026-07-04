# ASADO Trading Runbook — Paper → Live, One Coherent Book

**Date:** 2026-07-03
**Account:** IBKR, $100,000, long-only + cash, 34 US-listed country ETFs
**Operator:** Fable (autonomous), Arjun (owner, weekly review + kill authority)
**Parent document:** `docs/alpha_book_2026_07_02/ALPHA_BOOK_2026_07_02.md` (the evidence, sleeve designs, and skeptic verdicts). This runbook is the executable version.

---

## 1. The One Book

The eight strategies do not run as eight portfolios. They collapse into **one portfolio** built in four layers, where each layer is a transformation of the target-weight vector:

```
EW-34 base weights
  → sleeve tilts        (S1 combiner tilt, S2 slow composite)   [paper-only until gates pass]
  → event vetoes        (S3: zero out / haircut vetoed names)
  → cash dial           (S5: multiply invested fraction 100/70/50/30%)
  → execution layer     (M4 fair-value timing, auction-only orders)
= one net order file per trading decision
```

### Paper-phase capital map ($100k paper account)

| Layer | Weight | Contents | Status rationale |
|---|---|---|---|
| CORE (EW-34) | 60% | 34 ETFs equal-weight, ~$1,765 each | The null/carrier. Promotes to real money first. |
| S1 combiner tilt | 20% | Top-8 by `combiner_scores_daily` (29-country validated universe), ~$2,500 each | KILLED for real money; paper IS its shadow-measurement program (gate: 252td ETF-marked IC ≥ +0.015) |
| S2 slow composite | 10% | Top-8 by slow diffusion composite (twins-63 + PIT bank gap + twohop, z-averaged), ~$1,250 each, 21-bd staggered holds | KILLED at launch (own kill condition true); paper accrues the revival evidence (Gate R-A: trailing 252bd IC > 0 two consecutive month-ends) |
| Cash floor | 10% | USD | Structural minimum; grows when S5 dial de-risks |

S3 and S5 are **overlays** (no capital): S3 zeroes/haircuts names post-event; S5 scales the whole invested fraction. S4 is dead (its M4 fair-value filter survives inside the execution layer). S6 (Fable's Desk) runs as paper theses in the existing thesis ledger, 0–3/week, no account capital until its calibration gate passes. S7 (wildcards) is research only — harness trials, never orders.

**Real-money phase-in funds only CORE + overlays at first.** Tilts get real dollars only through their pre-registered gates. This means: paper trades the *aggressive* book (to generate evidence), real money starts as the *conservative* book, and the two converge as gates pass.

### Tilt construction rules (exact)

- **S1 tilt:** each evaluation day, rank the validated combiner universe. Hold top-8. **No-trade band:** a held name is sold only when it drops below rank 12; a new name is bought only when it enters top-8. Skip any name carrying an active D9 basis flag or an S3 veto. Whole shares, ~$2,500 target per slot, residual to cash.
- **S2 composite:** monthly, at turn-of-month: z-score each of SIM_NBR_RET_GAP_63D, GRAPHP_BANK_NBR_RET_GAP_21D, GRAPHP_TWOHOP_TRADE_GAP_21D cross-sectionally, average available z's (min 2), rank. Hold top-8 for 21 business days in two staggered tranches (half rebalanced each ~10 bd).
- **S3 vetoes (binding):** EM rating downgrade → name zero-weighted across ALL layers for 21 trading days from next close. Rating upgrade → 50% haircut on new buys for 63 td (never a block). CDS-inversion and flow signals are advisory-only until their re-runs clear.
- **S5 dial:** stress score from four inputs (VIX3M/VIX term ratio, HY OAS z, MOVE z, FX-implied-vol stress breadth). Score 0–1 → 100% of invested cap; 2–3 → 70%; 4–5 → 50%; ≥6 → 30%. De-risk after 2 confirming days (1 on the hard trigger VIX TS < 0.92, which runs on free CBOE data and never goes stale). Re-risk one step per 5 confirming days. **Paper-binding immediately; real-money-binding only after the mixed-lag re-run + naive vol-target duel** (whichever rule wins the duel is the one that goes live).

---

## 2. The Autonomous Daily Machine

All times ET. The nightly data machine already exists; this adds a decision + execution machine on top.

| Time | Step | Actor | What happens |
|---|---|---|---|
| ~06:30 | Prediction-market job | launchd (exists) | predmkt tables refresh |
| ~07:30 | `daily_update.py` → loop job (33 steps) | launchd (exists) | combiner, graph, dislocations, brief — all decision inputs |
| 08:45 | **Morning decision pass** | `scripts/live/decide.py` (new) | Health gates (below) → compute the four-layer target vector → diff vs current paper positions → write dated order file + decision log to `Data/live/` → Telegram summary to Arjun |
| 09:30–15:30 | No trading | — | The book never trades the open or midday. |
| 15:35 | **Execution pass** | `scripts/live/execute.py` (new) | Re-check dial hard trigger on live CBOE data; submit the order file: MOC for Tier-A names, LOC ±30bp (±50–75bp on stress days) for Tier-B/C; auto-transmit by 15:48; kill-switch = presence of `Data/live/HALT` file |
| 16:15 | **Reconciliation pass** | `scripts/live/reconcile.py` (new) | Pull fills via API → realized cost vs tier budget → sleeve-level attribution ledger (parquet, append-only) → Telegram fill report |
| Overnight | Fable supervision | scheduled Claude session | Read decision log + fills + governance scorecard; anomalies → HALT file + Telegram alert; weekly, write the review memo |

**Hard health gates — decide.py refuses to emit orders (holdings ride) if any fail:**
1. Governance scorecard not GREEN.
2. Combiner/graph surfaces older than T+2, or any decision input stale beyond its declared budget.
3. Any forward-return variable (`1MRet` family) detected in a live input (lookahead tripwire).
4. Realized month-to-date cost > 1.2× tier budget (falls back to monthly-rebalance-only mode).
5. `HALT` file present.

Missed day = nothing trades; the book is never in a state where silence causes damage.

**Execution pathway:** local Python engine (`ib_insync` or `ibapi`) against **IB Gateway paper (port 4002)** running on this Mac, launched by launchd like the existing jobs. The IBKR MCP connector stays as Fable's *supervision* channel (positions, balances, order status) — order placement goes through the API engine because MOC/LOC auction orders with auto-transmit and a kill-switch need deterministic code, not chat-tool calls. All engine state lives under `Data/live/` (gitignored like `Data/loop/`), never in the main DB.

### Trading calendar

- **Daily:** S1 tilt band check (most days: zero orders — the band means typical turnover is 0–2 names/day), S3 veto state, S5 dial state.
- **Turn-of-month window ([-1,+3] bd):** CORE rebalance + S2 tranche roll — the one predictably busy day (~15–30 orders).
- **Weekly (Monday):** Fable review memo; S6 paper theses; S7 registrations (≤1/week).
- **Month-end:** S2 revival Gate R-A check; cost ledger close; calibration report.

Expected order load: ~150–350/yr. Every order <0.35% of ADV — capacity is a non-issue.

---

## 3. Paper → Real Money: the Promotion Ladder

**Stage 0 — Build & dry-run (target: 2 weeks).** Build the three `scripts/live/` programs + launchd jobs; 5 consecutive days of order files generated with correct math and zero crashes, orders NOT transmitted (log-only mode).

**Stage 1 — Paper live (months 1–2).** Full book trades on the paper account. Exit criteria to Stage 2:
- 20 consecutive clean pipeline+decision days (health gates all green or correctly self-halted).
- ≥20 fills per spread tier with realized cost ≤ 1.2× tier budget.
- Zero order errors (wrong side, wrong size, unintended symbol) — one error resets the clock.
- Reconciliation ledger matches IBKR statements to the penny for a full month.

**Stage 2 — Real money, conservative book (month 3).** Real account funds **CORE + S3 + execution layer only**, at 50% size ($50k deployed, rest cash). Paper account keeps running the full book in parallel (the tilts' evidence clock keeps ticking). After one clean real-money monthly rebalance → full $100k CORE.

**Stage 3 — Real money, dial (month 4+).** S5 (or its duel-winning naive replacement) goes real-money-binding after the mixed-lag re-run and duel are published.

**Stage 4 — Tilts, only via gates.** S1 real money requires: 252td of paper/shadow ETF-marked top-8 IC ≥ +0.015 (corrected SEs) + measured tier-blend cost positive-net. S2 requires Gate R-A + the harness run of the composite + the sign-flip mechanism memo. Funded initially at ≤$20k carved from CORE. S6 Stage-1 ($5k) requires ≥40 closed paper theses with Brier ≤ 0.24. If nothing gates in by 2027-12: the book formally becomes EW + insurance + research, and we re-charter or wind down to passive.

**Program-level kills (real money, any one → full halt + owner review):** −20% from high-water mark; any lookahead discovered in a live input; cost >1.5× budget; scorecard non-GREEN >5 consecutive days; dial fails to cut the next ≥25% drawdown by ≥15% relative (dial dies permanently, book reverts to static 90/10).

---

## 4. What the Owner Sees

- **Daily Telegram:** one message after the 08:45 pass (book state, orders staged, any gate failures) and one after reconciliation (fills, cost vs budget).
- **Weekly memo (Mondays, committed to `docs/live_reports/`):** P&L vs EW-34 benchmark, per-sleeve attribution, veto/dial state changes, gate-clock progress (S1 shadow IC accrual, S2 R-A status), anything Fable halted and why.
- **Monthly:** the rebalance report + updated promotion-ladder status.
- **Owner controls:** create `Data/live/HALT` (or tell Fable) = no new orders until removed; weekly review is where sizing/gate decisions get ratified.

---

## 5. Build List (Stage 0 engineering, in order)

1. `scripts/live/book_config.yaml` — layers, weights, bands, tiers, cost budgets, gates (single source of truth).
2. `scripts/live/decide.py` — health gates → four-layer target vector → order file + decision log (pure function of the loop DB + config; unit-testable with PIT canaries like the harness).
3. `scripts/live/execute.py` — IB Gateway paper connection, MOC/LOC submission, HALT check, auto-transmit window.
4. `scripts/live/reconcile.py` — fills → attribution parquet ledger (append-only, per sleeve, vs EW-34).
5. launchd plists (08:45, 15:35, 16:15 ET) + Telegram wiring (reuse LoopPilot's channel).
6. `live_signals` registry reconciliation fix (pre-existing blocker: all 16 hypotheses show INSUFFICIENT_COVERAGE despite a green scorecard).
7. Paper account plumbing: IB Gateway installed, paper login, API enabled, port 4002, market-data subscriptions checked for all 34 tickers.

Owner-side prerequisites: IBKR paper account credentials available to the Mac's IB Gateway; decision on running Gateway 24/5 on this machine; confirm market-data entitlements cover the 34 ETFs (paper accounts share the live account's subscriptions).
