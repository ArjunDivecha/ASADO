<!--
=============================================================================
FILE: docs/PRD_Frontend_Alpha_Rethink_2026_07_01.md
=============================================================================
PURPOSE:
  Product requirements for rethinking the CONTENT of the Chief-of-Staff
  cockpit around the project's single question:

      "In picking country equity markets — daily and long-term —
       what does the data know that is NOT embedded in the price?"

  This is a content redesign, not a restyle. The visual system, the shell
  (map / persistent left / morphing focus / chat), and the epistemic contract
  from cos_mockups/DESIGN_BRIEF.md all survive. What changes is WHAT the
  surfaces say and WHICH objects get ink.

INPUT FILES (context, none modified):
  - docs/ASADO_PRICE_DISCOVERY_GAP_MACHINE_2026_06_22.md   (the north star)
  - docs/PRD_Gap_Engine_Frontend_Binding_2026_06_24.md      (gap binding v1)
  - docs/AUDIT_FRONTEND_2026_07_01.md                       (companion audit)
  - docs/AUDIT_DATA_STRUCTURES_2026_07_01.md                (companion audit; R1-R6)
  - cos_mockups/{DESIGN_BRIEF.md, COCKPIT_DATA_CONTRACT.md, build_cockpit_data.py}
  - Live loop DB state on 2026-07-01 (gap engine, harness registry, holdout)

OUTPUT FILES:
  - This document. Implementation will modify build_cockpit_data.py,
    cockpit_live.html generation, and add loop-DB read-model builders.

VERSION: 1.0    LAST UPDATED: 2026-07-01    AUTHOR: Claude (Fable 5) session
=============================================================================
-->

# PRD — The Alpha-First Cockpit (Front-End Content Rethink)

## 0. The problem with the current content

The cockpit today is honest, disciplined, and **organized around the
machinery rather than the question**. It shows: a map, the harness registry,
the gap feed, dislocations, governance, and a research desk. A first-time
viewer learns *what the system is* but not *where the edge is*.

Concrete evidence from the live page (2026-07-01):

1. **The prediction surface is invisible.** The daily ridge combiner — the
   single strongest registered signal (IC 0.057, NW-t 10.7) — appears only as
   an unlabeled map color layer. Lead-lag, graph-spillover, similarity-twins
   (the validated propagation family) appear only as registry rows with
   t-stats — never as *today's country ranking*. The system computes an
   answer to "which countries does the data favor today" every night and the
   front end never shows it.
2. **The headline object is broken.** All 5 "Top Gaps" are `repriced_against`
   — price has already run over the mechanism — but they still headline
   because tension is frozen at open (audit item A1). The page's best real
   estate is spent on stale, falsified tension.
3. **The long-term clock is missing.** The user's question is explicitly
   "daily AND long term." The warehouse has 730 monthly variables, valuation
   percentiles, WEO revision momentum, JST 150-year tails — and the cockpit
   has no strategic view at all.
4. **There is no self-scoring.** `gap_holdout_daily` tracks promoted vs
   ignored gaps; thesis marks and a calibration report exist; the graveyard
   is a designed control arm. None of it is on the page. A cockpit that
   claims to find unpriced edges must show whether its past claims worked.
5. **The "unusual/nonlinear" hunt has no surface.** The Discovery Lab tab
   shows LLM draft cards, but there is no place where cross-family
   DISAGREEMENT (the raw material of nonlinear insight) is made visible, and
   no conditional/interaction signal results exist to display.

## 1. The one question, decomposed

Every panel must answer one of these five sub-questions. Content that answers
none of them is removed or demoted to drilldown.

| Q | Sub-question | Horizon |
|---|---|---|
| Q1 | Where does the data disagree with price **today**, and by how much? | days–weeks |
| Q2 | What do the **validated** signal families jointly say about every country today? | days–weeks |
| Q3 | Where should I lean **structurally** (12–36 months), and what is the tail? | months–years |
| Q4 | Are the system's claims **actually working** (live, out of sample)? | rolling |
| Q5 | What **new, unusual** mechanisms are being hunted, and how are past hunts scoring? | rolling |

The current cockpit answers Q1 (badly, per audit A1/A2), gestures at Q5, and
ignores Q2, Q3, Q4.

## 2. Content principles (the edict, operationalized)

1. **Rank countries, not tables.** The atomic display unit is the country-
   with-a-claim: direction, horizon, edge size, family agreement, expression,
   invalidation. Machinery (detector codes, table names) is drilldown.
2. **Price-state is a first-class citizen.** Every claim is shown NET of what
   price already knows: "ToT z=-2.4" alone is banned; "ToT z=-2.4 while
   equity 21d z=-0.1 → gap 2.3σ" is the unit of content.
3. **Two clocks, visibly separate.** A Daily desk (gaps, flows, family
   ranks) and a Strategic desk (valuation, revisions, tails). Never blend
   the horizons in one ranking.
4. **Disagreement is content.** When orthogonal families conflict on a
   country (e.g. graph says long, flows say crowded short), that conflict is
   surfaced as a named object — it is exactly where nonlinear structure
   lives, and exactly what to hand the Discovery Lab.
5. **Self-scoring or silence.** Any surface that makes forward claims must
   display its own live track record next to the claim.
6. **Epistemic contract unchanged.** FACT/INFERENCE/UNKNOWN tags, harness-
   owned verdicts, PAPER until cleared. Nothing below weakens this.

## 3. The redesigned content, panel by panel

### P1 — The Edge Board (replaces "Today")   [Q1]

At most five cards, ranked by **live** edge, drawn from ALL claim surfaces —
not just gap episodes:

- gap episodes (with tension **recomputed at mark time** — see §4.1),
- family-consensus extremes (a country at the top/bottom of ≥3 orthogonal
  family rankings — see P2),
- fresh event-window opportunities (rating changes, CDS inversions — the
  event studies that validated: downgrade −0.9%@5d EM, inversion −4.5%@63d),
- open theses approaching invalidation or horizon.

Card anatomy (one glance = the whole claim):

```
① JAPAN — SHORT via EWJ · 21d                        [INFERENCE]
   Edge: ToT impulse −2.4σ vs equity 21d −0.1σ → 2.3σ unpriced
   Agreement: 2 of 6 families lean short · flows neutral · options quiet
   Live tension 0.31 (opened 0.50, decaying) · day 8 of 21
   Wrong if: equity reprices −3% or ToT z recovers above −1.5
   This class historically: 41 episodes, 58% absorbed, median t½ 9d
```

The last line is the self-scoring hook (autopsy stats per gap class, §4.4).
A `repriced_against` episode can never occupy a card; it moves to the
lifecycle strip (P3).

### P2 — The Consensus Matrix (new; the missing prediction surface)   [Q2]

A 34-row board — countries × the validated signal families — showing each
family's **current cross-sectional rank** for each country, plus:

- **Lean**: the combiner score (labeled for what it is: outcome-trained,
  in-sample-selected, a ceiling),
- **Agreement**: how many families independently rank the country in their
  top/bottom quintile,
- **Conflict flag**: families in *opposite* extremes on the same country.

Columns v1 (all already computed nightly, none new): ridge combiner,
lead-lag 5d gap, PIT graph two-hop trade gap, PIT bank-neighbor gap,
similarity-twin divergence, ECFC CPI revision (reflation direction),
ETF-flow contrarian z, ToT impulse. Each column header carries its harness
verdict chip (WEAK/WATCH) and its registered IC — the user should *feel*
that these are thin, real edges, not oracle output.

Interaction: click a cell → single-signal view (existing F4) scoped to that
country; click a conflict flag → a "disagreement dossier" (the two series
overlaid + a one-click "send to Discovery Lab" that files the conflict as a
candidate look, via the existing custody path).

This panel is the single most direct answer to "what does the data know" —
it is the system's live opinion, with its confidence stated honestly.

### P3 — Gap Lifecycle Strip (demoted from headline)   [Q1]

The current "Known Gaps" list becomes a lifecycle view: OPEN (unabsorbed) →
ABSORBING → REPRICED-AGAINST → CLOSED/AUTOPSIED, with live tension decay per
§4.1. `repriced_against` rows render struck-through with the signed
absorption index — they are *lessons in progress*, labeled as such.

### P4 — The Strategic Desk (new; the missing long-term clock)   [Q3]

Monthly cadence, explicitly labeled with its own as-of date. One row per
country:

- **Valuation**: CAPE/ERP own-decade percentile (exists: `valuation_monthly`),
- **Slow revisions**: WEO GDP revision momentum (D3 substrate), ECFC 12m
  blend, demographic drift (`demographics_dip`),
- **Structural flow**: ToT trade-share trend, bilateral-graph centrality
  change (PIT edges, annual vintages),
- **Tail**: trailing drawdown → JST bucket → forward-3y real p10/median/P(neg)
  (exists: JST risk report tables) — DM vs EM-analogy labeled,
- **Strategic lean**: rich/cheap × improving/deteriorating quadrant, with the
  explicit caption that this layer is context + valuation, not a harnessed
  signal, until the strategic sweep (§4.5) clears it.

This replaces the mock Tail view (audit A3) with real content and gives the
page its second clock.

### P5 — The Scoreboard (new; the honesty engine)   [Q4]

One panel, four live series, all from existing tables:

1. **Gap holdout**: promoted vs ignored dislocations, cumulative net return
   in the registered ETF expressions (`gap_holdout_daily` — 533 rows
   accumulating since 06-22; the falsification test from the Sakana doc,
   made visible),
2. **Thesis calibration**: Brier/hit-rate by archetype from the calibration
   report (currently a nightly xlsx nobody sees),
3. **Family IC since registration**: each P2 column's rank-IC measured ONLY
   on post-registration data vs its registered in-sample IC — decay made
   visible (`harness_ic_series` + registration dates in the ledger),
4. **Graveyard vs promoted**: forward returns of killed claims vs promoted
   ones (the discovery-triage control arm, once rosters populate).

Rule: if a series is too young to mean anything, show it anyway with its n —
"n=7 days, not yet meaningful" is on-brand honesty.

### P6 — Research Desk (kept, refocused)   [Q5]

Keep the six tabs. Two content changes:

- **Prospective queue becomes the headline tab** once forward-tracking has
  rows: each Lab claim shows days-in-queue, forward window completed, and
  the tracking readout — the "unusual alpha" pipeline made visible as a
  scoreboard rather than a card gallery.
- **Feed the Lab from P2 conflicts.** The disagreement dossier (P2) files
  structured conflict cards into the Lab's candidate looks. Today the Lab
  fishes from raw surfaces; pointing it at *live cross-family disagreements*
  aims the expensive model at exactly the nonlinear seams the user wants
  mined. (Custody unchanged: outcome-blind surfaces, same schemas, same
  docket caps.)

### Map, chat, governance (kept with edits)

- Map layers become: **Edge** (P2 agreement score, the new default),
  **Gap** (live tension), **Return** (with a staleness badge — audit A7),
  **Tail** (drawdown dots). The combiner-colored "Signal" layer is absorbed
  into Edge.
- Chat: the deterministic router learns the new intents ("who do the
  families like", "show the scoreboard", "why is Japan on the board",
  "what conflicts today"); the Opus path gets the P2 matrix + scoreboard in
  its evidence packet (extending the existing `_evidence_packet`).
- Governance stays a ribbon chip + F6 view; a governance exception still
  claims Edge Board slot ①.

## 4. Backend deltas required (ranked, with owners in the existing codebase)

### 4.1 Live tension (fixes the broken headline) — S
`build_gap_episodes.py`: compute `tension_score_current` at mark time —
decay the open score by `staleness_penalty(days_active)` and by realized
absorption (`|price_absorption_index|` capped), floor at 0. A
`repriced_against` mark forces tension below the promotion floor. This one
change re-sorts the entire attention surface correctly. (Audit item A1;
config-versioned so the holdout stays interpretable — freeze as
`gap_engine_v2`, keep v1 scoring in the config history.)

### 4.2 `family_ranks_daily` (powers P2) — M
New nightly builder: for each P2 family, today's cross-sectional rank per
country from its existing table, written to one tidy loop table
`(date, country, family, rank, score, universe_n)`. Prerequisite for the
consensus/agreement/conflict computations. This is a thin slice of the
`signal_panel_daily` recommendation (R1) in the data-structure audit — build
it as the first increment of R1, not as a separate one-off.

### 4.3 `edge_board` selector (powers P1) — S
In `build_cockpit_data.py`: merge candidates from gap marks (live tension),
P2 agreement extremes, event triggers, thesis states; dedupe by
entity|direction; rank by live edge × freshness × expression quality; cap 5.
Keep the existing promotion-rule tests, extend for the new sources.

### 4.4 Autopsy stats per gap class (powers P1's last line) — S
Aggregate `gap_episode_autopsy` (11 rows and growing): per gap class —
n, absorbed %, median half-life, hit rate. Trivial query, high trust value.

### 4.5 Strategic surface + sweep (powers P4) — M
Read-model joining `valuation_monthly` + WEO revisions + ToT shares + JST
buckets into one monthly table `strategic_state_monthly`. Simultaneously
pre-register the strategic composite in the harness at the 6–12m horizon
(monthly sweep spec, honest universe) so P4's "lean" column can eventually
carry a verdict chip instead of a "context only" caption.

### 4.6 Scoreboard read-models (powers P5) — S/M
- holdout equity curves: aggregate `gap_holdout_daily` promoted vs ignored,
- family IC-since-registration: filter `harness_ic_series` by ledger
  registration dates,
- surface the calibration xlsx numbers as JSON.

### 4.7 Conflict → Lab bridge (powers P6) — S
A writer that turns a P2 conflict into a structured candidate look (existing
`record_look` custody path, outcome-blind fields only). No new API spend —
it queues candidates for the existing nightly docket cap.

## 5. What is explicitly NOT changing

- No new data sources. The Sakana review's conclusion stands: the repo does
  not need more data, it needs a sharper answer to "which gap deserves
  attention today."
- No weakening of custody: harness owns verdicts; Lab stays outcome-blind;
  combiner stays out of Lab context; optimizer outputs stay out of the
  panels' input surfaces.
- No fake charts (ic_series stays null where nothing is persisted), no
  padded slots, no dark mode, no "n/a" (stale values carry `*`).
- The Streamlit app and Perspective Lab are untouched — this PRD is the
  cockpit only.

## 6. Phasing

| Phase | Scope | Contents |
|---|---|---|
| 1 (correctness) | §4.1, audit fixes 1–7 | live tension, absorption display, setHor, live Brief/Tail bindings, router copy, escaping |
| 2 (the answer) | §4.2, §4.3, P1+P2 | family ranks, consensus matrix, edge board |
| 3 (the clocks) | §4.5, P4 | strategic desk + strategic sweep pre-registration |
| 4 (the mirror) | §4.4, §4.6, P5 | autopsy stats, scoreboard |
| 5 (the hunt) | §4.7, P6 | conflict→Lab bridge, prospective scoreboard |

Each phase ships with contract tests extending `test_cockpit_selection.py`
and one Playwright smoke (closing red-team AC13).

## 7. Acceptance (what "good" looks like)

A first-time viewer, in 30 seconds, can answer: *"Where does the data
disagree with price today, how strongly, is the machine's judgment currently
earning its keep, and what long-term leans does the data support?"* — and
every one of those answers carries its source, its verdict chip, and its
falsification condition. A `repriced_against` gap never headlines. The
combiner's opinion is visible, labeled, and accompanied by its live
out-of-sample IC. The page scores itself in public.
