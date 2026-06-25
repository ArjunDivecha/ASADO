<!--
=============================================================================
FILE: DESIGN_BRIEF.md
=============================================================================
PURPOSE:
  Complete redesign brief for the ASADO "Chief of Staff" cockpit, written to be
  pasted into Claude Design (claude.ai/design) as the source spec for a full
  redesign. It defines (1) the product intent, (2) the SELECTION INTELLIGENCE —
  the rules that decide what is shown, promoted, flagged, or hidden — (3) the
  visual system, (4) every panel and the 7 focus states, and (5) the data model
  each surface binds to after import.

INPUT FILES (the thing being redesigned):
  - /Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/cos_mockups/cockpit.html

OUTPUT / DOWNSTREAM:
  - A Claude Design canvas (static comps for all states)
  - Re-imported to repo via Vercel MCP `import-claude-design-from-url`, then
    re-wired to live ASADO tables by Claude Code.

DATA SOURCES THE LIVE VERSION BINDS TO (read-only):
  - Data/loop/asado_loop.duckdb : dislocation_daily, combiner_scores_daily,
    live signal registry + skeptic-harness verdicts, governance scorecard
  - Data/dislocations/brief_YYYY_MM_DD.md : the nightly brief
  - ledgers/thesis_ledger.jsonl : open theses (PAPER)
  - JST 1870–2020 tail distribution (banking-crisis onsets)

VERSION: 1.0   LAST UPDATED: 2026-06-18   AUTHOR: Arjun Divecha / Claude Code
=============================================================================
-->

# ASADO · Chief of Staff — Redesign Brief

## 0. One-sentence intent
A **standing intelligence brief you hold a conversation with** — not a dashboard.
A persistent cockpit (map + signals + dislocations + governance) on the left, a
single **focus panel that morphs** to answer whatever you ask or click on the
right, and a prominent **chat driver** along the bottom that narrates every move
and cites its sources. Editorial, light-mode, newspaper-of-record voice. Calm,
literate, disciplined — it tells you what matters and is honest about what it
doesn't know.

> **Hard constraint: LIGHT MODE ONLY.** Never produce a dark variant. Paper, ink,
> and restrained jewel tones. This is non-negotiable.

> **How to use the attached `cockpit.html`.** It is uploaded alongside this brief
> as the **architectural base — restyle and elevate it, do not re-architect it.**
> Preserve: the shell (ribbon / persistent-left / dynamic-focus / chat footer),
> the **7 focus states** and the intent→view routing (§1.6), the data model (§4),
> and — above all — the **Selection Intelligence (§1)**, which is logic, not
> decoration. You may freely upgrade typography, spacing, color application,
> hierarchy, the charts, and the editorial polish. You may **not** collapse the
> morphing focus panel back into a static dashboard, drop the epistemic tags, or
> turn verdicts into the CoS's own opinion. If a layout idea conflicts with a §1
> rule, the §1 rule wins.

---

## 1. THE SELECTION INTELLIGENCE (the spine — design *around* this)

The cockpit's value is **curation under discipline**. Every surface answers a
"what should be shown here, and why" question with an explicit rule. Design must
make these rules *legible* — the user should feel a point of view, ranked by
importance, with epistemic honesty visible on the surface.

### 1.1 The epistemic contract (applies everywhere, always visible)
Three tiers, shown as a persistent key and as inline tags:
- **FACT** — a cited, retrievable number/state. Always carries a source chip.
- **INFERENCE** — a model/analogy/judgment. Tagged `INFERENCE`; never stated bare.
- **UNKNOWN / STALE** — said *aloud*, not hidden. e.g. "live drawdown is nominal
  vs a real, DM-calibrated distribution — context only."
- **Nothing is a trade.** Anything actionable is **PAPER** until the skeptic
  harness clears it. The word "paper" appears on positions and fresh ideas.
- The Chief of Staff **never adjudicates a signal** — verdicts come *only* from
  the harness. Design should reinforce "I report the harness, I don't overrule it."

### 1.2 "Today" — the three-slot promotion rule (the focus panel's default)
Exactly **three** items earn the morning brief. Selection priority:
1. **Governance exception first.** If any governance dimension is not green,
   slot ① explains *why* (and whether it's "honest, not broken").
2. **The single best-standing signal.** The top harness verdict (a WATCH if one
   exists) — stated *with its caveat* (e.g. "in-sample → a ceiling, not proof").
3. **The freshest high-conviction dislocation.** Highest-|z| newly-fired detector
   that has **not yet repriced** (the unpriced impulse is the alpha).
Each slot is a card with: ordinal, headline, one-line "why it matters," a source
chip, and a click → routes the focus panel + posts a chat line. Ranking signal =
`severity × freshness × actionability`. If fewer than 3 qualify, show fewer — do
not pad.

### 1.3 The map — what gets ink
- Default layer = **dislocation** (where pressure is building), toggleable to
  **return** and **signal**.
- Tile color: diverging paper→teal (constructive) / paper→rust (stress), centered
  on neutral. Tabular values.
- **⚑ flag** on a tile = an active dislocation for that market (it's in tonight's
  brief). **Oxblood dot** = an active drawdown / tail watch. **Dashed gold ring**
  = a standing watch (e.g. sanctions-adjacent, structural).
- Selected market is outlined. Clicking any tile morphs the focus panel to that
  country's "letter."
- Market sleeves are **not** sovereigns: `ChinaA` = China proxy; `ChinaH`,
  `NASDAQ`, `US SmallCap` are sleeves. Group by region (Americas / Europe / MEA /
  Asia / Oceania).

### 1.4 Live Signals — ordering and verdicts
- Rows sorted by **NW-t descending** (or IC, toggle). Show the strongest first.
- Verdict badge is **harness-owned**: `WATCH` (teal), `WEAK` (amber), `DEAD`
  (oxblood), `INSUFF` (muted). Color encodes standing, not the CoS's opinion.
- Each row: name, `t · IC` subline, verdict. Click → single-signal IC view.
- A tally strip summarizes the whole registry (e.g. 2 WATCH · 39 WEAK · 31 DEAD ·
  16 INSUFF) so the user sees how rare a WATCH is.

### 1.5 Dislocations — detector firing logic
- Detectors **D1–D10** each test a specific disagreement (terms-of-trade impulse
  vs flat equity, return-gap spillover, attention spike with no price move, etc.).
- A detector **fires** when its z-score crosses threshold; rows sort by **|z|**.
- **Hot** styling (rust code-chip) when |z| is high. A code chip (D1…) +
  one-line mechanism + the z reading. Country-linked rows click → country letter;
  non-country rows (stewardship, basis) → an explainer.
- The brief has a fixed tail-risk footer (long-cycle JST) that is *context*, not a
  signal — it never promotes itself into a trade.

### 1.6 The focus panel — intent → view routing (the "intelligence to know what to show")
The chat router classifies the question and **morphs the one focus panel**:
| If the question is about… | Focus becomes |
|---|---|
| "what matters / today / brief me / priorities" | **Overview** (the 3 slots) |
| a country name (any of the 34) | **Country letter** |
| "the signals / registry / weak / dead / all" | **Signals registry** (table + tally) |
| a specific signal (e.g. "combiner") | **Single-signal IC** (chart + caveat) |
| "dislocations / nightly / fired / tonight" | **The brief** |
| "health / governance / scorecard / amber" | **Governance scorecard** |
| "downside / tail / drawdown / crash / falling" | **Long-cycle tail** (fan chart) |
| "where is pressure / map / flows" | Overview + set map to dislocation layer |
Unmatched → Overview with a gentle "try: …" prompt. Every route also **posts a
chat line** that names what it did and cites a source. A back-stack (‹) lets the
user retrace focus states.

### 1.7 Governance scorecard — the honesty rule
- Overall = **worst dimension** (so AMBER if any one is amber). The headline voice:
  AMBER means the system is being **honest, not broken**.
- Seven dimensions (run_manifest, liveness, ledger_integrity, family_registry,
  pit_lag_proof, cross_source_minimal, config_guard), each green/amber/red with a
  one-line reason. Pips render in the ribbon; full table in the focus panel.
- The amber is explained as *partial by design* — design should make "by design"
  feel intentional, not like a failure.

### 1.8 Country letter — conditional surfacing
- Lede in editorial voice + a drop cap. Stat line (10Y, 5Y CDS, equity 21d,
  2s10s). Valuation percentile bars (CAPE cheap / ERP rich, diverging color).
- Equity sparkline (trailing 21 sessions).
- **Conditionally**: a PAPER thesis chip if one is open for that country; a
  **JST tail keyrow only if that market has an active drawdown** (otherwise the
  row is absent — don't show an empty tail).

---

## 2. VISUAL SYSTEM (keep faithfully)
- **Palette (light):** paper `#F4EEE1` / `#FBF7EE` / `#EFE7D6`; ink `#221F18` /
  `#5B5345` / `#8C8474`; gold `#B8975A` / soft `#D8C49A`; oxblood `#7C2D2D`;
  rust `#B4521E`; teal `#2C7A6B`; status green `#3C7A4E` / amber `#B07A12` /
  red `#A23B2E`. Hairline rules in warm translucent brown.
- **Type:** display = *Fraunces* (optical, ital for accents); serif body =
  *Spectral* (italic for "voice"/asides); UI/labels = *Public Sans*. Small-caps
  region labels, uppercase letterspaced eyebrows, tabular-nums for all figures.
- **Texture:** faint paper grain (multiply, ~5% noise), soft radial warm glows in
  the corners, thin gold top-border on the chat to signal "the live wire."
- **Motion:** focus content rises/fades on each morph (≈0.5s ease). Tiles lift on
  hover. Nothing flashy — editorial restraint.
- **Density:** information-dense but airy; this is for a professional who reads.
  Drop caps, dot-leaders, a "No. 0617" folio, "a standing brief, in conversation"
  subtitle — newspaper-of-record cues.

---

## 3. LAYOUT & ALL PANEL STATES (produce a comp for each)
**Shell:** ribbon (masthead + governance chip with pips + as-of date) · cockpit
body (persistent left ~1.45fr / dynamic focus ~1fr) · chat footer (thread +
composer + quick-chips + epistemics key).

**Persistent left, always shown:**
- A1 — **Capital-flows map** (region-grouped tiles, layer toggle, compass, legend)
- A2 — **Live Signals** list (verdict badges)
- A3 — **The Dislocations** feed (D-code chips, z readings)

**Dynamic focus — 7 comps, one per state:**
- F1 **Overview / "Today"** — the three promotion-rule cards
- F2 **Country letter** — lede + stats + valuation bars + sparkline + conditional thesis/tail
- F3 **Signals registry** — sortable table + WATCH/WEAK/DEAD/INSUFF tally + "harness owns verdicts" note
- F4 **Single-signal IC** — IC line chart (21d/63d toggle), stat trio, caveat paragraph, source chip
- F5 **The brief** — full dislocation list + JST tail footer
- F6 **Governance scorecard** — 7-row honesty table
- F7 **Long-cycle tail** — p10/median/p90 fan over drawdown buckets, "context only" caveat

**Chat footer:** alternating You (italic serif) / Chief of Staff (serif, with
inline teal **source/citation chips**). Pill composer with placeholder examples.
Quick-chips: "What should I care about today?", "Where is pressure building?",
"The WEAK signals", "Brazil", "Downside if Indonesia keeps falling?". Right-aligned
epistemics key: **FACT** cited · **INFERENCE** labelled · **UNKNOWN/STALE** aloud.

---

## 4. DATA MODEL (for re-wiring after import — design with realistic placeholders)
- **Governance** = `[dimension, green|amber|red]` ×7; overall = worst.
- **Markets** = 34 T2 names grouped by region, each with `return`, optional
  `dislocation` label, optional `drawdown`.
- **Signals** = `[name, verdict, IC, NW-t, note]`; verdict ∈ {WATCH,WEAK,DEAD,INSUFF}.
- **Dislocations** = `[D-code, headline, mechanism, z, hot?, country?]`.
- **Country** = `{y10, cds, 2s10s, eq21d, cape_pctile, erp_pctile, regime, lede,
  sparkline[], optional thesis, optional drawdown}`.
- **IC series** = combiner rank-IC by horizon (21d / 63d).
- **Tail** = JST p10/median/p90 forward-3y by drawdown bucket.

---

## 5. WHAT "GOOD" LOOKS LIKE (acceptance)
- A first-time viewer immediately senses **a ranked point of view**, not a wall of
  equal-weight widgets.
- Every number is either sourced (FACT) or flagged (INFERENCE / UNKNOWN-STALE).
- The three "Today" cards visibly follow the promotion rule (§1.2).
- The focus panel clearly **morphs** to match the question; the back-stack works.
- It reads like a *brief written by a disciplined analyst*, in light mode, in the
  Fraunces/Spectral/Public Sans system — and it never pretends a signal is a trade.
