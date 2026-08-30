# PRE-REGISTRATION — capacity-changing vs signalling political events

**Status: PRE-REGISTERED, NOT YET RUN.** Written 2026-08-30, before any CAR was
computed and before the coding pass. Nothing below may be edited after the first
CAR is produced; changes require a dated amendment block appended at the end.

**Deliverable of this test:** a diagnostic CAR comparison. It is NOT a signal
registration, charges NO family trial, and cannot on its own promote anything to
the combiner. A signal built on a positive result is a separate, later
pre-registration that WILL charge a family.

---

## 1. Mechanism (stated without reference to any case study)

Governments continuously emit statements of intent, which are cheap to produce
and carry no commitment. Separately and less often, their actual capacity to act
changes — funding cost, reserves, parliamentary arithmetic, external programme
status. If the marginal investor cannot cheaply distinguish the two, then
announcements and capacity changes of comparable news salience will be priced
alike at impact, and only the capacity changes will still be priced weeks later.

**Deliberate exclusion (the guest-list rule):** this statement was written
without reference to any specific historical episode, and no episode from any
source text was consulted in choosing the buckets, horizons, or thresholds. Any
episode named in a secondary source about this mechanism lies inside the 1997–2026
sample and was selected by an author who knew its outcome; using such episodes to
motivate thresholds would be circular. The panel decides.

## 2. Data and the honest sample size

Source: `asado.event_log` — 146 curated events. The usable subset is far smaller
than 146 and this was measured BEFORE the test was designed:

- 98 of 146 rows are `is_global = true` with NULL `countries_affected`. The
  `event_study.py --preset event_log` path skips them by construction
  (`WHERE countries_affected IS NOT NULL`). They are **excluded**, not repaired.
- The remaining 48 events expand to **97 country-event pairs**, all 97 already
  inside `T2_UNIVERSE`, spanning 26 countries.
- Category composition of the 97: regulatory 23, trade_policy 19,
  financial_crisis 18, election 17, central_bank 10, geopolitical 10.
- Year clustering: 1997 (8), 2008 (2), 2013 (5), 2014 (1), 2017 (11), 2018 (2),
  2019 (12), 2020 (5), 2021 (12), 2022 (13), 2023 (7), 2024 (15), 2025 (4).

**Effective sample is 48 events, not 97 pairs.** Countries inside one event are
near-perfectly correlated, so 97 overstates independent information by roughly
2×. Split two ways this is ~24 events per bucket. This is a SMALL test and is
pre-registered as such.

## 3. The coding rule (mechanical, fixed here, applied blind)

Each of the 48 events is assigned exactly one bucket by the rule below. The rule
is applied to `label`, `description`, `category`, `subcategory` ONLY.

**CAPACITY** — the event changed a government's or central bank's realised
ability to act, in a way observable on the day:
executed policy-rate change; executed asset purchase/sale programme; FX peg
break or defence actually spent; sovereign default, bailout, bail-in, or IMF
programme entry; ratings action that moves funding cost; bank failure or
resolution; government/coalition collapse or formation that changes the seat
arithmetic; enacted law/tariff/export control that is in force on the day;
military action actually taken.

**SIGNALLING** — the event conveyed intent, position, or expectation without
changing capacity on the day:
speeches, guidance, and forward-looking central-bank communication with no rate
or balance-sheet action; announced-but-not-yet-in-force tariffs, deals, bans, or
policies; summit outcomes and communiqués; election *outcomes* (which reveal
future intent; the capacity change arrives at government formation); threats,
warnings, referendum results not yet implemented.

**Tie-break, fixed ex ante:** if an event both announces and enacts on the same
day, it is CAPACITY. If neither rule matches, it is dropped and counted as
UNCODED — the count is reported and the drops are listed.

**Blinding protocol.** The coder receives ONLY
`event_id, event_date, label, description, category, subcategory` — no returns,
no CAR, no `severity`, no `tags` (tags leak outcome language such as
"global_selloff"). Coding is written to
`Data/work/experiments/prereg_capacity_signalling/coding.csv` and **hashed and
committed before any CAR is computed**. The hash goes in the results file. If
the coding file changes after that hash, the run is void.

## 4. Prediction (joint, directional, fixed)

At equal news salience, over the post-event window:

- **P1** — CAPACITY events show larger absolute CAR than SIGNALLING at +21d.
- **P2** — SIGNALLING events mean-revert: their mean absolute CAR at +21d is a
  smaller fraction of their +1d absolute CAR than for CAPACITY events.
- **P3 (spanning)** — the CAPACITY-minus-SIGNALLING difference survives
  restricting to the 4 political categories only (geopolitical, election,
  trade_policy, financial_crisis = 64 pairs), i.e. it is not a repackaging of
  the central_bank subset.

Horizons: +1d, +5d, +21d, +63d. Anchor: `next_day` (the existing preset default),
which satisfies the ≥1-trading-day execution embargo by construction.

## 5. Inference (the arithmetic that killed comparable tests)

- Standard errors **clustered by event date**, never by country-event pair.
  Reporting a t-stat over 97 correlated pairs would be arithmetic, not evidence.
- A **stationary block bootstrap over event dates** (1,000 draws) is the primary
  inference; the clustered t is secondary.
- **Minimum n, fixed here:** if either bucket has < 15 distinct events after
  coding, the test is declared **INSUFFICIENT_EVENTS** and reports no verdict.
  No pooling, no horizon shopping, no bucket redefinition to reach 15.
- Horizons are reported in full. The headline is +21d, chosen here, in advance.

## 6. Kill criteria (pre-committed)

The framework is **NOT SUPPORTED** if any of:
- either bucket < 15 distinct events (INSUFFICIENT_EVENTS);
- P1 fails: CAPACITY |CAR| at +21d does not exceed SIGNALLING with bootstrap
  p < 0.10 (deliberately lenient — this is a screen, not a claim);
- P3 fails: the difference vanishes on the 4 political categories alone,
  i.e. the result is a central-bank-events finding wearing a political label;
- the CAPACITY-minus-SIGNALLING difference is explained by event-window
  realised volatility or by pre-event 21d return (both reported as controls) —
  i.e. it is a repackaged volatility or reversal effect.

## 7. What a pass does and does not license

A pass licenses ONE thing: a follow-up pre-registration for a **conditioning**
variable — does the response to news differ by mechanical capacity state. It
does **not** license a narrative-level factor. Standing record, unchanged by this
test: family `gdelt_narrative_v2` is 2× DEAD (H_20260727_001 IC −0.019 t −0.74
canary FAIL; H_20260727_002 IC −0.033 t −2.22 canary FAIL), a third trial
H_20260727_003 is registered and open, and the compendium's line is *"GDELT
first-order tone — dead; survives only as conditioning."* Any narrative-level
proposal must clear that record first.

Prior art checked 2026-08-30: Quantpedia mirror (1,312 strategies, 8 phrasings)
returns **no cousin**; nearest is #1261 *Geopolitical Risk in Currency Markets*
(UNSCREENED, no OOS tracked, paper Sharpe 0.39), which sorts on geopolitical
BETA — a risk-premium mechanism, not a mispricing one. ASADO ledger: zero
constraint/political/rhetoric hypotheses; the `event_log` event-study preset has
never been run (16 studies on disk, none of them `event_log`).

## 8. Files

- This pre-registration:
  `/Users/arjundivecha/Dropbox/AAA Backup/A Working/ASADO/docs/preregistrations/PREREG_2026-08-30_capacity_vs_signalling_events.md`
- Coding (blind, hashed before any CAR):
  `.../Data/work/experiments/prereg_capacity_signalling/coding.csv`
- Results (written once, by the runner):
  `.../Data/work/experiments/prereg_capacity_signalling/RESULTS.md`
- Runner: `scripts/loop/event_study.py --events-sql ...` (custom-events path;
  the built-in `event_log` preset has no bucket column, so the runner passes the
  coded buckets via `--events-sql` against a temp view over `coding.csv`).
