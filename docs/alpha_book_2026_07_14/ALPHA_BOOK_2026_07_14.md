# ALPHA BOOK v2 — 2026-07-14

**Status:** the governing Alpha Book. Supersedes `docs/alpha_book_2026_07_02/` (v1), whose
*measured numbers* are void — see §1. Its design thinking (S1–S8) remains referenced where still valid.
**Provenance rule (non-negotiable):** every performance number in this book cites a harness-v4
result JSON (`Data/loop/harness_runs/*_20260714_*.json`, each self-describing via its
`execution_convention` block) or the re-verdict summary
(`Data/loop/harness_runs/reverdict_v4_2026-07-14/summary.parquet`). Numbers without v4 provenance
do not enter this book.

---

## 0. Bottom line

The honest ledger contains **seven distinct mechanisms (eight WATCH registrations)** with genuine
long-sample edge at the honest execution clock — **and every one of them is negative in 2025–26.**
The book's live position is therefore: **nothing deploys today.** The book's live *work* is
(a) the monitoring layer that detects re-arming, (b) the re-arm playbook per mechanism, and
(c) the central research question — why did every mechanism in the ledger decay together in
2024–25?

## 1. Why v1's numbers are void (the measurement reform)

Between 2026-07-13 and 07-14 two defects in the measurement layer were found and fixed
(contract `HARNESS-V4-HONEST-LEDGER-001`, spec at repo root, all gates green, merged `8a1aa6e`):

1. **The clock.** For "zero-lag" daily sources the forward-return window opened at the signal's
   OWN close — same-close execution plus a timezone echo across 34 asynchronous markets. Roughly
   half of measured daily IC was echo (family lag-0 pre-2024 IC +0.023/NW-t 4.0 → lag-1 +0.012/2.2).
   v4 enforces a ≥1-trading-day execution embargo for ALL daily signals and proved the fix on
   known-answer fixtures: a planted pure-echo signal scores IC 0.42 at lag-0 and **0.0016** at v4;
   a planted IC 0.05 is recovered at 0.0521 (`tests/test_harness_v4.py`).
2. **The gate basis.** v3 (2026-07-13) re-keyed verdicts from net-25bp to GROSS metrics (cost
   retraction, Arjun's directive); the deflated Sharpe now runs on the gross LS series.

All 59 pre-registered hypotheses were re-verdicted through the front door with existing ids
(zero new registrations; family deflated-Sharpe accounting preserved; integrity machine-checked).
Migration: WATCH 1→8 (the old lone "WATCH" was the 12MRet leak, now `REFUSED_BLACKLIST`),
WEAK 21→10, DEAD 21→24.

## 2. The honest tier — and its status stamps

All stats at the registered primary horizon, honest clock (daily = signal at t, window opens t+1
close), gross. **Read the right-hand columns first: the tier is uniformly broken right now.**

| Mechanism | Variable (universe) | NW-t | mean IC | DSR | Gross LS Sharpe | IC 2023 | 2024 | 2025 | 2026H1 |
|---|---|---|---|---|---|---|---|---|---|
| Inflation surprise (monthly, cross-sectional) | `ECO_INFL_SURPRISE_Z` (34) | 3.04 | 0.036 | 0.092 | 0.56 | +0.124 | +0.048 | +0.009 | **−0.111** |
| Bank-claims propagation 21d | `GRAPH_BANK_NBR_RET_GAP_21D` (21) | 3.25 | 0.019 | 0.006 | 0.46 | +0.056 | +0.009 | −0.015 | **−0.053** |
| Trade-gap propagation 21d (PIT) | `GRAPHP_TRADE_NBR_RET_GAP_21D` (31) | 2.56 | 0.014 | 0.000 | 0.38 | +0.017 | −0.002 | −0.016 | **−0.022** |
| Katz all-paths propagation 21d (PIT) | `GRAPHP_KATZ_TRADE_GAP_21D` (31) | 2.51 | 0.014 | 0.000 | 0.38 | +0.016 | −0.000 | −0.013 | **−0.022** |
| Fundamental twins 21d | `SIM_NBR_RET_GAP_21D` (34) | 3.10 | 0.015 | 0.011 | 0.55 | +0.012 | +0.007 | −0.014 | **−0.049** |
| Leader–follower weekly gap | `LL_LEADER_GAP_5D` (16 followers; 2 registrations) | 4.56 | 0.030 | 0.025 | 0.79 | +0.011 | +0.021 | −0.034 | **−0.055** |
| Daily ridge combiner | `COMBINER_RIDGE_DAILY_V1` (29) | 5.73 | 0.030 | 0.047 | 0.98 | +0.038 | +0.026 | +0.027 | **−0.057** |

Provenance: `H_20260612_{015,023,036,038,042,049,054,055}_20260714_*.json`.

**Interpretive stamps:**
- **Hit-rate law:** per-mechanism true-positive rate in this shop is 15–20%. Eight WATCH
  registrations ≈ expect one to two genuinely real. A WATCH is a lottery ticket, not a sleeve.
- **Combiner ceiling:** `COMBINER_RIDGE_DAILY_V1` blends in-sample-selected survivors; its stats
  are a ceiling, not an estimate (the `ml_combiner` monthly variant re-verdicted DEAD again).
- **Two `LL_LEADER_GAP_5D` rows are one mechanism** (sub-universe re-tests), not two discoveries.
- **The expression law still stands** (it is about price discovery, not fees, and predates the
  cost retraction): index-space alpha at the US-listed ETF close ≈ 0. v4 verdicts are measured at
  local closes with a 1-day embargo — the implementable analogues are local-market/futures/open
  expressions (v1's S2/E-series capture designs remain the reference for HOW, minus their numbers).

## 3. Parked: the re-arm gates (what would change our minds)

Everything in §2 sits behind the **R-A price gate**: a mechanism re-arms after **two consecutive
positive family month-ends** on its nightly-tracked IC (family = `network_spillover` as one unit;
`eco_surprise` separately; combiner follows its components). Until a re-arm fires, no expression
work, no sizing, no thesis staking on these mechanisms. On re-arm: start at the smallest sleeve,
futures/local-venue expression only, and re-read §4 first.

## 4. The central research question (open): the 2024–25 broad decay

The G1 flip autopsy (`experiments/2026_07_flip_autopsy/results/RESULTS.md`, 2026-07-13) established
for the network family: the decay is real at the honest clock, **not** construction drift, **not**
explained by the four pre-registered regime axes (the environment looked *favorable*; the pre-2024
IC was state-independent), and **not** classic crowding (no ownership build-up fingerprint; losses
broad, not concentrated). Break date ≈ 2024-04; slow horizons died first; the adaptive combiner
died last (2026H1).

The v4 re-verdict adds a decisive fact: **the decay is not family-specific.** The monthly
inflation-surprise mechanism — different data, different frequency, different economic channel —
collapsed on the same timeline (2023 +0.124 → 2026H1 −0.111). Working hypothesis (interpretation,
unproven): **absorption-speed compression** — cross-market/macro information is being priced into
country indices faster than any of our 5-day-to-1-month harvesting windows. Falsifiable
implications worth testing next: (i) edge should survive better at shorter capture horizons in
*non-US-close* venues; (ii) the decay should show in OTHER shops' published country-rotation
factors post-2024; (iii) intraday/open-auction expressions of the same mechanisms should retain
more. This question gates the whole book: if absorption is the answer, re-arming may never fire
at these horizons and the venue/clock work (v1's T-EXPR territory) becomes the book's main axis.

## 5. Dead and settled (do not reopen without new evidence)

- **`LL_LEADER_RET_1D`** — NW-t 6.4 → **0.32** at the honest clock. Its entire edge was the
  timezone echo. The cleanest single validation of the v4 reform.
- **All 63-day propagation variants** (trade ×2, bank, PIT-trade) — DEAD at honest clock.
- **12MRet "WATCH"** — was the forward-return leak; now formally `REFUSED_BLACKLIST`.
- **Settled house lessons feeding this book:** lag-0 portfolio levels are never results (the
  "3-Sharpe incident", `docs/strategy/lessons.md`); inverse-state gross throttles on
  positively-skewed LS books sell convexity for nothing (R1, `ME_20260713_002`); a combiner of
  in-sample survivors reports a ceiling; regime taxonomies do not reorder this cross-section
  (2026-05/07 regime graveyard).

## 6. The live spine (what actually runs from today)

1. **Nightly family-IC monitor** — the follow-up Divecha contract (next in queue): per-family
   honest-clock IC written nightly to the loop DB, R-A price gates evaluated automatically,
   surfaced in the brief. Nothing in this book is trustworthy without it; the 2024–26 decay went
   unmeasured for ~15 months because this didn't exist.
2. **JST tail-risk calibration layer** — unchanged, live, context-tier only.
3. **The harness itself (v4)** — the only path from idea to evidence; every future result JSON
   self-describes its clock; known-answer suite in CI (`tests/test_harness_v4.py`).
4. **Governance:** hypothesis ledger (59 registrations, append-only, front-door writes only);
   methodology ledger (directory experiments); `docs/strategy/lessons.md`; the graveyard protocol.

## 7. Provenance appendix

- Full 59-row migration table: `Data/loop/harness_runs/reverdict_v4_2026-07-14/summary.parquet`
  (+ `.xlsx`), manifest with per-run result files: `.../manifest.json`.
- Contract + build record: `harness_v4_honest_ledger.spec.md` (repo root, `DIVECHA_CONTRACT_VALID`),
  `implementation-notes.md`, `docs/harness_v4_notes.md`.
- Measurement-defect evidence trail: `experiments/2026_07_dispersion_throttle/results/RESULTS.md`
  (correction block), `experiments/2026_07_flip_autopsy/results/a6_lag1_family_ic.json`.
- v1 book (numbers void, designs referenced): `docs/alpha_book_2026_07_02/`.
