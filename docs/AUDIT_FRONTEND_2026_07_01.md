<!--
=============================================================================
FILE: docs/AUDIT_FRONTEND_2026_07_01.md
=============================================================================
PURPOSE:
  Complete problem audit of the new Chief-of-Staff cockpit front end
  (cos_mockups/cockpit_live.html served at http://127.0.0.1:8800 by
  cos_mockups/cos_chat_service.py, payload from build_cockpit_data.py).
  Every finding was verified against the live running page and/or exact
  file:line evidence on 2026-07-01.

INPUT FILES (read-only; nothing was modified):
  - cos_mockups/cockpit_live.html          (the generated live page)
  - cos_mockups/make_live_cockpit.py       (mock -> live generator)
  - cos_mockups/build_cockpit_data.py      (payload producer)
  - cos_mockups/cos_chat_service.py        (FastAPI server + chat)
  - cos_mockups/cockpit_data.json          (live payload, generated 2026-07-01T09:30)
  - cos_mockups/COCKPIT_DATA_CONTRACT.md, DESIGN_BRIEF.md
  - docs/REDTEAM_DISCOVERY_TRIAGE_2026_06_26.md
  - Live browser session against http://127.0.0.1:8800/cockpit_live.html

OUTPUT FILES:
  - This document.

VERSION: 1.0    LAST UPDATED: 2026-07-01    AUTHOR: Claude (Fable 5) session
=============================================================================
-->

# Cockpit Front-End Audit — 2026-07-01

## Architecture (context)

```
nightly loop (steps ~190-191)
  build_cockpit_data.py  -> cockpit_data.json + cockpit_data.js (window.COCKPIT_DATA)
  make_live_cockpit.py   -> cockpit_live.html   (string surgery on the cockpit.html mock)

browser @ 127.0.0.1:8800  <- uvicorn cos_chat_service:app
  StaticFiles("/") serves the page + data
  POST /api/cos/chat  (deterministic router first, Opus for research questions)
  GET  /api/cos/health (verified live: opus_available=true, model claude-opus-4-8)
```

Payload freshness at audit time: `meta.generated_ts 2026-07-01T09:30`,
gap engine `fresh` as-of 2026-06-30, governance GREEN, page binds correctly
(verified in the running browser).

---

## A. Content correctness problems (the important ones)

**A1 — The headline ranking is stale by construction.**
`gap_episode_marks.tension_score_current` is set to `tension_score_at_open`
(`scripts/loop/build_gap_episodes.py:565`). The "Known Gaps" panel, the map
gap layer, and the Today card all rank by a score frozen at episode open.
Live consequence (verified): **all 5 headline gaps are in
`repriced_against` state** — price has already moved against the mechanism —
yet they still headline because their open-time tension never decays. 21 of
22 current marks are `repriced_against`. The front page is effectively a
museum of gaps being falsified in real time, presented as today's best
opportunities.

**A2 — "100% unabsorbed" contradicts `repriced_against` on the same card.**
Verified live: the Japan Today card reads "repriced_against · 100% unabsorbed".
`unabsorbed_fraction` is clamped to [0,1] while the absorption index is
negative (−0.36), so a gap moving the wrong way renders as maximally
"unabsorbed" — which reads as maximally attractive. Misleading at the exact
point of highest attention.

**A3 — The Tail focus view is 100% mock.** `cockpit_live.html:447–451` +
`fan()` at :487 render hardcoded arrays and fixed copy ("Indonesia −50%",
"Denmark −45%") regardless of live drawdowns (Indonesia is actually −33.8%).
Real JST data exists (`Data/loop/risk_reports/`, drawdowns in payload) but is
not wired. This violates the page's own epistemic contract.

**A4 — The Brief view is partly mock.** `:437` hardcodes "As-of 16 Jun · 79
rows" (live: 2026-06-30, 58 rows); the JST footer `:439–441` is hardcoded;
the `brief.file` pointer in the payload is never rendered — the real nightly
brief (the richest artifact the system produces) is unreachable from the UI.

**A5 — The chat router lies with stale numbers.** `route()` `:556` answers
"2 WATCH · 39 WEAK · 31 DEAD" (live tally: 1/21/20/16); `:565` hardcodes
pressure countries "Chile, Korea, Indonesia"; `:566` still says
"(prototype: scripted)"; `openCountry()` `:496` appends "reflation" to every
country regardless of state. The panels show real data while the narrator
recites June's mock — trust-destroying in a product whose brand is honesty.

**A6 — Ribbon initial HTML is mock.** `:197–198` hardcode "AMBER" and
"16 Jun 2026 · refreshed 07:32" before the boot script overwrites them —
a flash of wrong state, and permanently wrong if JS fails.

**A7 — Returns layer is ~2 months stale with no flag.** `returns.as_of
2026-05-01` vs gaps 2026-06-30. The map "Return" layer renders it with no
staleness badge (contract requires STALE aloud).

**A8 — No refresh mechanism.** No polling/reload; a tab left open serves
yesterday's world forever, while the chat API reads fresh JSON — the panels
and the narrator can silently diverge. Minimum fix: compare
`meta.generated_ts` on an interval and show a "data refreshed — reload"
banner.

## B. Bugs

**B1 — `setHor()` is called but never defined.** `:398` emits
`onclick="setHor('…')"`; the function exists in the mock (`cockpit.html:379`)
but `make_live_cockpit.py` dropped it when replacing the signal view. Any
click on a horizon toggle for a multi-horizon signal throws ReferenceError.
(Confirmed: no `function setHor` anywhere in cockpit_live.html.)

**B2 — Grammar/precision defects at the top of the page.** "1 things worth
your attention" (`:362` uses raw length); "ERP percentile 81.667" (`:298`
no rounding); Brazil country title renders "Brazil · —" because `reg` is
overloaded (`:297` sets `reg` to "gap"/"dislocation"/"—" — it's the routing
regime, not the region — and the title template at `:371` uses it as if it
were the region).

**B3 — Sidebar verdict badge omits INSUFF.** `:334` `vmap` maps only
WATCH/WEAK/DEAD; an INSUFFICIENT_COVERAGE row gets no badge class.

**B4 — Dead code:** `spark()` defined never called (`:485` — the design
brief's country sparkline was dropped in generation); `GOV_DETAIL` computed
never used (`:259`).

**B5 — No UI handling of a producer error payload.** When the loop DB is
unavailable, `build_cockpit_data.py:1066–1068` writes an `error` key; the
page renders silently empty panels.

## C. Security / XSS residuals

The user-message XSS fix (commit f0ecb52) is in place (`esc()` in `pushMsg`,
`:491`). Remaining injection vectors are all *warehouse-string → innerHTML*
paths — lower risk (data is self-produced) but inconsistent with the red-team
posture:

- Today cards `ocard()` `:364–367`: `headline`, `why`, `source` unescaped.
- Gap detail `:420`: `mechanism_text` unescaped.
- Country lede `:377`/`:298`: built from data strings, unescaped.
- `onclick="openSignal('${s[0]}')"` / `openCountry('${n}')`: breaks (and is
  injectable) if a name ever contains a quote.
- Chat: `bub.innerHTML = payload.answer_html …` (`:542`) — server escapes
  Opus text but the cite span's model/agent fields are trusted.

Chat service: no auth on `/api/cos/chat` (any localhost process can spend
Opus tokens); `_evidence_packet` hardcodes `current_date: "2026-06-24"`
(`cos_chat_service.py:472`) — the Opus context says June while the payload
says July; `fallback: true` is set on *successful* Opus responses (`:582`).

## D. Contract / doc drift

- `COCKPIT_DATA_CONTRACT.md` documents 12 top-level keys; the producer emits
  14 (`gap_engine`, `research_desk` undocumented). The contract file is the
  declared source of truth for the UI binding — update it.
- DESIGN_BRIEF still says slot 3 = "freshest dislocation" and default map
  layer = dislocation; live behavior (gap-first) follows the newer Gap Engine
  PRD. Fine — but one of the two documents must win explicitly.
- Payload keys produced but never displayed: `gap_engine.raw_top/holdout/
  staleness/selection_note/config_*`, `combiner.leaders`, `governance.
  repo_dirty` + `dimensions[].evidence`, full `dislocations.rows`, thesis
  full text. Several of these are precisely the "honesty" metadata the design
  brief wants surfaced.

## E. Test coverage gaps

Covered: payload selection rules (`test_cockpit_selection.py`, 15 tests),
chat service routing/scrub (`test_cos_chat_service.py`), research-desk
readers. Not covered: any DOM/E2E test of the generated page (the missing
`setHor` proves the gap — AC13 from the red-team is still open), generation
parity of `make_live_cockpit.py` (no test that live output contains required
functions), XSS from warehouse strings, stale-tab behavior, error-payload
rendering, INSUFF badge.

## F. Priority fix list

| # | Fix | Where |
|---|---|---|
| 1 | Recompute `tension_score_current` at mark time (decay by absorption/staleness) instead of copying open score; demote `repriced_against` gaps from headline slots | `build_gap_episodes.py:565`, `build_cockpit_data.py` gap ranking |
| 2 | Reconcile absorption display: never show "N% unabsorbed" when state is `repriced_against`; show signed absorption index instead | `cockpit_live.html:266`, gap card templates |
| 3 | Restore `function setHor(h){ICHOR=h;renderFocus()}` + add generation-parity test | `make_live_cockpit.py` |
| 4 | Bind Brief view to live `dislocations.as_of/total` + render `brief.file` markdown; bind Tail view to live drawdowns/JST or label STALE | `cockpit_live.html:436–451` |
| 5 | Fix `route()` narrations to read `TALLY`/live leaders; remove "(prototype: scripted)"; fix `openCountry` "reflation" | `cockpit_live.html:550–566` |
| 6 | `esc()` all warehouse-string HTML sinks; quote-safe onclick args | multiple, see §C |
| 7 | Stale-data banner comparing `meta.generated_ts`; fix ribbon initial HTML | `cockpit_live.html:197–198` + boot |
| 8 | Update `COCKPIT_DATA_CONTRACT.md` (gap_engine, research_desk); fix chat service `current_date`, `fallback` flag | contract + `cos_chat_service.py:472,582` |
| 9 | Playwright smoke in CI (page loads, no console errors, one route per view) — closes red-team AC13 | new test |

Items 1–2 are content-correctness (they change what you *believe* looking at
the page); 3–5 are functional; 6–9 are hygiene. The deeper content redesign is
in `PRD_Frontend_Alpha_Rethink_2026_07_01.md`.
