# PRD - Bind Price-Discovery Gaps Into The Front End

| Field | Value |
|---|---|
| Project | ASADO |
| Product surface | Chief-of-Staff cockpit + current ASADO front end |
| Feature | Price-Discovery Gap front-end binding |
| Created | 2026-06-24 |
| Owner | Arjun Divecha |
| Status | Builder-ready draft |
| Depends on | `PRD_Price_Discovery_Gap_Engine.md`, `cos_mockups/DESIGN_BRIEF.md`, `cos_mockups/COCKPIT_DATA_CONTRACT.md` |
| Primary producer | `cos_mockups/build_cockpit_data.py` |
| Primary consumer | `cos_mockups/cockpit_live.html`, then the new front end |

---

## 1. Summary

ASADO now has the missing middle object for its north-star question: **what does the data know that price has not yet figured out?** The gap engine already emits durable gap episodes, daily marks, price-state surfaces, ETF expression metadata, and the brief's "Top Price-Discovery Gaps" section. The front end still mainly exposes raw dislocations, signal verdicts, country tiles, and governance.

This PRD binds the new gap engine into the front end by making `gap_episodes` plus latest `gap_episode_marks` the primary daily attention surface. Raw dislocations remain available as the detector substrate, but the user-facing cockpit should promote **price-discovery gaps** first: the ranked few places where world-state evidence and price-state absorption appear misaligned, with ETF expression, absorption state, and invalidation rules visible.

This enhances the existing system. It does not replace the pipeline, dislocation engine, skeptic harness, ledgers, daily brief, or new front-end work. It gives the new front end a better primary object to render.

---

## 2. Current State

### 2.1 Existing Front-End Surfaces

- `frontend/app.py` is the older Streamlit research dashboard. It has tabs for monthly update, dashboard, network views, factor explorer, Ask ASADO, and free query. It does not yet expose the gap engine.
- `frontend/perspective_lab/` is a separate analyst workbench. It builds successfully, but it is not the Chief-of-Staff cockpit.
- `cos_mockups/` is the relevant cockpit prototype. It already has a live data builder, static cockpit HTML, design brief, and tests.

### 2.2 Existing Cockpit Data Contract

`cos_mockups/COCKPIT_DATA_CONTRACT.md` currently defines these top-level keys:

```text
meta, governance, signals, dislocations, combiner, returns,
theses, countries, drawdowns, brief, map, today
```

The current `today` promotion rule is:

```text
governance exception -> best non-sanity WATCH signal -> freshest highest-severity country dislocation
```

That third slot is now too low-level. It should be driven by price-discovery gaps when fresh gap data exists.

### 2.3 Existing Gap Engine Tables

The current loop DB contains the required substrate:

- `price_state_daily`
- `price_state_surface`
- `gap_episodes`
- `gap_episode_marks`
- `gap_episode_expression`
- `gap_holdout_daily`

As of the latest checked run, these tables are populated through `2026-06-23`, and the latest brief already includes a "Top Price-Discovery Gaps (pilot)" section.

---

## 3. Problem

The front end still answers "what fired?" more readily than "what has price not absorbed?"

Raw dislocations are useful to engineers and researchers, but they are not the right first screen for the user. A detector row does not automatically say:

- which gap matters most today,
- whether price has ignored, partially absorbed, or overreacted,
- what ETF/proxy expresses the gap,
- whether that expression is liquid enough and clean enough,
- whether the gap is new, intensifying, stale, or closing,
- what would invalidate the mechanism,
- how it maps to the daily brief and country letter.

The front end should present a small ranked set of **gap episodes** first, then allow drilldown into dislocations and evidence.

---

## 4. Goals

1. Make price-discovery gaps the cockpit's primary opportunity surface.
2. Add a `gap_engine` payload to `cockpit_data.json` using real loop DB tables.
3. Replace the raw-dislocation Today card with a top-gap Today card when fresh gap marks exist.
4. Add a persistent "Price-Discovery Gaps" panel showing the top ranked gaps.
5. Bind country tiles and country letters to active gaps.
6. Preserve raw dislocations as drilldown evidence, not the main promotion object.
7. Carry ETF expression quality visibly without overemphasizing transaction cost.
8. Render stale or missing gap data honestly as `UNKNOWN` / `STALE`, never silently blank.
9. Keep the new front end aligned with the cockpit data contract, so the cockpit payload can be reused instead of rebuilt.

---

## 5. Non-Goals

- Do not build a new trading/order-entry system.
- Do not remove `dislocation_daily`.
- Do not replace the skeptic harness, ledgers, governance scorecard, or daily brief.
- Do not make LLM commentary a source of evidence.
- Do not hide governance status when gaps are compelling.
- Do not treat ETF transaction cost as the core bottleneck. The intended expressions are liquid ETFs; model expression quality, expense drag, ETF-vs-country basis, liquidity tier, currency basis, and crowding.
- Do not fake charts for series that are not persisted.
- Do not require Excel or CSV intermediates anywhere in this front-end path.

---

## 6. User Stories

### US1. Morning Triage

As Arjun, I want the first screen to show the few strongest price-discovery gaps, so I can immediately see where ASADO thinks data and price disagree.

Acceptance:

- The Today section includes the top current gap when fresh gap marks exist.
- The card headline includes country/entity, direction, preferred ETF/proxy, and absorption state.
- The card routes to the gap detail view.

### US2. Gap Detail

As Arjun, I want to click a gap and see why it exists, what price has absorbed, how to express it, and what invalidates it.

Acceptance:

- Detail view shows world-state summary, price-state summary, mechanism text, ETF expression, absorption mark, expected vs realized move, and invalidation rule.
- Raw source dislocations are visible as evidence links/rows.

### US3. Country Letter

As Arjun, I want a country page to answer whether that country currently has an active price-discovery gap.

Acceptance:

- Country letter has an "Active Gap" module when applicable.
- If multiple gaps exist for the country, show the highest `tension_score_current` first.
- If none exist, show no module rather than filler text.

### US4. Map Scan

As Arjun, I want the map to flag where active gaps exist, not merely where raw detectors fired.

Acceptance:

- Map tile flags come from latest gap marks when fresh.
- Tile tooltip shows direction, ticker, absorption state, and tension score.
- Raw dislocation flags remain available as a secondary layer or drilldown.

### US5. Front-End Reuse

As the builder of the new front end, I want a stable JSON contract so I can bind UI components without reimplementing SQL logic in React.

Acceptance:

- `cos_mockups/build_cockpit_data.py` remains the canonical payload generator until the production front end has its own API layer.
- The new front end can consume the same `cockpit_data.json` shape or a direct API wrapper with equivalent fields.

---

## 7. Data Contract Change

### 7.1 Add Top-Level `gap_engine`

Add a new top-level key to `cockpit_data.json`:

```jsonc
{
  "gap_engine": {
    "as_of": "2026-06-23",
    "status": "fresh",
    "config_version": "gap_engine_v1_2026_06_24",
    "config_hash": "5e4bab...",
    "top": [],
    "by_country": {},
    "counts": {},
    "holdout": {},
    "staleness": {}
  }
}
```

Status values:

- `fresh`: latest gap mark date is within the daily data as-of date.
- `stale`: gap tables exist but latest mark is older than the latest loop/dislocation date.
- `missing`: required tables do not exist or are unreadable.
- `empty`: required tables exist but no promoted/current gaps are available.

### 7.2 `gap_engine.top[]`

`top` contains the top 5 current gap marks, ordered by `tension_score_current` descending, then `days_active` ascending, then expression quality descending.

Each row:

```jsonc
{
  "gap_id": "54309152acb331767687",
  "episode_key": "Mexico|G2|short|21d|...",
  "date": "2026-06-23",
  "entity": "Japan",
  "direction": "short",
  "gap_class": "G3",
  "horizon_bucket": "21d",
  "status": "open",
  "preferred_ticker": "EWJ",
  "proxy_type": "single_country_etf",
  "currency_basis": "usd_unhedged_etf_vs_t2",
  "liquidity_tier": "high",
  "expense_ratio_bps": 50.0,
  "dollar_adv_21d": 123456789.0,
  "expression_quality": 0.84,
  "tension_score_current": 0.48,
  "tension_score_at_open": 0.43,
  "absorption_state": "partially_absorbed",
  "price_absorption_index": 0.39,
  "unabsorbed_fraction": 0.61,
  "expected_move": 0.014,
  "realized_move": 0.004,
  "expected_move_source": "severity_mapping",
  "realized_etf_return": -0.012,
  "realized_country_return": -0.008,
  "days_active": 2,
  "mechanism_text": "Graph-neighbor stress has not been fully absorbed...",
  "invalidation_rule": "Close if...",
  "world_state": {},
  "price_state": {},
  "source_dislocation_ids": ["abc123"],
  "source_freshness": {},
  "epistemic_tag": "INFERENCE",
  "notes": ["Absorption is provisional until horizon completes."]
}
```

Required joins:

- `gap_episode_marks` latest mark
- `gap_episodes` for lifecycle, mechanism, world/price state, scoring config, invalidation
- `gap_episode_expression` for ETF expression fields
- `price_state_daily` for current price summary and freshness where needed

### 7.3 `gap_engine.by_country`

Keyed by exact T2 country/entity name:

```jsonc
{
  "Japan": {
    "primary": { "...": "same shape as top row" },
    "all": []
  }
}
```

Rules:

- `primary` is the highest ranked open/current gap for that country.
- `all` includes every current gap for that country, ordered the same way as `top`.
- If an entity is not a country tile, it may remain in `top` but should not be inserted into `map` country tiles unless mapped.

### 7.4 `gap_engine.counts`

```jsonc
{
  "open": 24,
  "marked_today": 5,
  "by_class": { "G2": 7, "G3": 4 },
  "by_direction": { "long": 9, "short": 15 },
  "by_absorption": {
    "unabsorbed": 4,
    "partially_absorbed": 12,
    "absorbed": 6,
    "overabsorbed": 2
  }
}
```

### 7.5 `gap_engine.holdout`

Summarize the frozen holdout without overstating it:

```jsonc
{
  "as_of": "2026-06-23",
  "rows": 169,
  "promoted": 24,
  "eligible_unpromoted": 145,
  "note": "Forward holdout is accumulating; backfill is a plumbing smoke test."
}
```

### 7.6 Extend `today[]`

Allow:

```jsonc
{
  "kind": "gap",
  "headline": "Japan short gap: data tension remains partially absorbed",
  "why": "EWJ expression; G3 graph propagation; 61% unabsorbed; 21d horizon",
  "source": "gap_episode_marks + gap_episodes",
  "route": {
    "view": "gap",
    "gap_id": "..."
  }
}
```

New Today promotion rule:

```text
governance exception -> best non-sanity WATCH signal -> top fresh price-discovery gap
```

Fallback:

- If `gap_engine.status` is `missing`, `stale`, or `empty`, use the old dislocation card but label the gap engine condition explicitly.
- Never silently promote a raw dislocation while fresh gap marks exist.

### 7.7 Extend `map[]`

Each tile gains:

```jsonc
{
  "gap": "G3 short EWJ partially_absorbed",
  "gap_id": "...",
  "gap_direction": "short",
  "gap_tension": 0.48,
  "gap_absorption": "partially_absorbed",
  "gap_ticker": "EWJ"
}
```

Rules:

- The map's primary flag layer should use `gap`, not raw `dislocation`, when `gap_engine.status == "fresh"`.
- Preserve the existing `dislocation` field for secondary drilldown.
- All 34 country tiles must still render.

---

## 8. UI Requirements

### 8.1 Today Strip

The Today strip remains at most three cards.

Card 3 changes from "freshest high-severity dislocation" to "top price-discovery gap."

Gap card content:

- Entity + direction
- Preferred ticker
- Gap class
- Absorption state
- Unabsorbed fraction
- Horizon
- Epistemic tag

Example:

```text
Japan short via EWJ
G3 graph gap · partially absorbed · 61% unabsorbed · 21d
```

### 8.2 Persistent Left/Top Panel

Rename or add the main opportunity panel:

```text
Price-Discovery Gaps
```

Rows show:

- rank
- entity
- direction icon/text
- ticker
- gap class
- tension score
- absorption state
- days active
- expression quality/liquidity tier

Raw dislocations become:

- a nested "Detector Firings" tab, or
- a detail subsection under selected gap, or
- a secondary panel below the ranked gaps.

### 8.3 Gap Detail Panel

Selecting a gap opens a focused panel with:

- mechanism text
- world-state evidence summary
- price-state summary
- absorption mark: expected move, realized move, unabsorbed fraction
- ETF/proxy expression: ticker, proxy type, currency basis, expense ratio, ADV, liquidity tier, expression quality
- source dislocation IDs and detector class
- invalidation rule
- status and days active
- freshness warnings

### 8.4 Country Letter Integration

Country detail pages add an "Active Gap" module above raw dislocations.

Show:

- primary current gap
- ETF expression row
- absorption mini-timeline if marks are available for multiple days
- raw dislocation evidence below

### 8.5 Brief Integration

The brief panel should deep-link to the "Top Price-Discovery Gaps" section of the latest brief when possible.

If line anchors are not available, show the brief filename and render/extract the section by heading.

### 8.6 Chat / Ask ASADO Routing

Questions containing these intents should route to gap-aware context:

- "what does price not know"
- "top gaps"
- "price discovery"
- "absorption"
- "unabsorbed"
- "why [country] long/short"
- ticker-specific gap questions such as "why EWJ"

The answer context should include `gap_engine.top`, the relevant `by_country` entry, and raw dislocation evidence. It should not answer from raw dislocations alone when a current gap exists.

---

## 9. Implementation Plan

### Phase 0 - Snapshot Current Behavior

1. Regenerate current cockpit payload.
2. Run existing cockpit tests.
3. Save before/after payload shape diffs for review.

Commands:

```bash
venv/bin/python cos_mockups/build_cockpit_data.py --pretty
venv/bin/python cos_mockups/make_live_cockpit.py
venv/bin/python -m pytest cos_mockups/test_cockpit_selection.py -q
```

### Phase 1 - Add Gap Payload Producer

Modify `cos_mockups/build_cockpit_data.py`:

- Add `read_gap_engine()`.
- Detect required table availability.
- Read latest `gap_episode_marks.date`.
- Join latest marks to `gap_episodes` and `gap_episode_expression`.
- Add `gap_engine.top`, `gap_engine.by_country`, `gap_engine.counts`, `gap_engine.holdout`, `gap_engine.staleness`.
- Sanitize JSON fields and missing numeric values.
- Preserve current payload keys for compatibility.

### Phase 2 - Update Today Promotion

Modify `build_today()`:

- Keep governance card first when non-green.
- Keep best non-sanity WATCH signal second when available.
- Use `gap_engine.top[0]` for the third slot when `gap_engine.status == "fresh"`.
- Fall back to raw dislocation only when gaps are unavailable.
- Add route support for `{ "view": "gap", "gap_id": "..." }`.

### Phase 3 - Update Map Payload

Modify map tile construction:

- Merge `gap_engine.by_country[country].primary` onto the tile.
- Add gap fields without removing existing return/dislocation/combiner/drawdown fields.
- Ensure all 34 country tiles still exist.

### Phase 4 - Update Cockpit UI

Modify `cos_mockups/cockpit_live.html`:

- Add "Price-Discovery Gaps" list.
- Bind Today gap cards to gap detail view.
- Add gap route handling.
- Add country letter active-gap module.
- Render stale/missing/empty states.
- Preserve raw dislocation drilldown.

### Phase 5 - Bridge Into The New Front End

Use the cockpit payload as the front-end API contract.

Preferred short-term path:

- Keep `cos_mockups/build_cockpit_data.py` as the canonical read model.
- Serve the generated JSON to the new front end through the existing dev server or a thin local endpoint.
- Build the new front-end components against the `gap_engine` object, not direct DuckDB queries.

Preferred medium-term path:

- Move the read-model logic into a small backend endpoint.
- Keep the JSON shape compatible with this PRD.
- Retire static JSON only after the endpoint passes the same contract tests.

### Phase 6 - Main Streamlit Integration

For `frontend/app.py`, add a lightweight "Gap Cockpit" tab or link:

- show latest `gap_engine.top`,
- show the latest brief gap section,
- link/open the cockpit HTML,
- avoid rebuilding the full cockpit in Streamlit.

This keeps the older dashboard useful while the new front end matures.

---

## 10. Test Plan

### 10.1 Contract Tests

Add or extend cockpit tests:

- `gap_engine` exists.
- `gap_engine.status` is one of the allowed values.
- If status is `fresh`, `top` is non-empty and sorted correctly.
- Every `top` row has `gap_id`, `entity`, `direction`, `preferred_ticker`, `tension_score_current`, `absorption_state`, and `invalidation_rule`.
- `today` contains no raw dislocation card when fresh gaps exist.
- Map tiles still cover 34 countries.
- Countries with primary gaps have tile gap fields.
- Missing/stale gap tables produce an honest non-crashing state.

### 10.2 Data Validity Tests

Run:

```bash
venv/bin/python tests/loop/test_daily_pipeline.py --date 2026-06-23
venv/bin/python -m pytest tests/loop/test_gap_engine.py tests/loop/test_run_manifest.py tests/loop/test_ledger_integrity.py -q
```

### 10.3 Cockpit Tests

Run:

```bash
venv/bin/python cos_mockups/build_cockpit_data.py --pretty
venv/bin/python cos_mockups/make_live_cockpit.py
venv/bin/python -m pytest cos_mockups/test_cockpit_selection.py -q
```

### 10.4 Browser Smoke

Use a local server and browser check:

```bash
python -m http.server 8787 --directory cos_mockups
```

Verify:

- cockpit loads without console errors,
- Today gap card appears,
- selecting the gap opens detail,
- map tiles render,
- country gap module renders,
- stale-state fixtures do not crash.

---

## 11. Acceptance Criteria

The feature is complete when:

1. `cockpit_data.json` includes top-level `gap_engine`.
2. `gap_engine.top[0]` matches the same top gap shown in the latest brief or the same ranking SQL.
3. Today promotes a gap instead of a raw dislocation when fresh gap marks exist.
4. The cockpit has a visible "Price-Discovery Gaps" section.
5. Selecting a gap shows mechanism, world-state, price-state, ETF expression, absorption, and invalidation.
6. Country tiles and country letters display active gap context when available.
7. Raw dislocations remain available as evidence/drilldown.
8. Missing/stale gap data is labeled honestly and does not break rendering.
9. Existing cockpit tests pass plus new gap contract tests pass.
10. The older Streamlit front end has at least a lightweight Gap Cockpit entry point.

---

## 12. Design Principles

- **Gaps, not noise:** The front end promotes durable gap episodes, not every detector firing.
- **Evidence hierarchy:** Governance and harness verdicts keep their authority. The UI never upgrades an idea to "trade" status by presentation alone.
- **ETF realism:** Show expression quality, liquidity, expense ratio, ADV, currency basis, basis gap, and crowding. Do not make cost the dominant story.
- **Epistemic honesty:** Label facts, inferences, unknowns, stale data, and provisional absorption.
- **No duplicate brains:** The front end consumes a read model. It does not reimplement gap ranking logic in UI code.
- **Drilldown without drowning:** The first screen shows top gaps; raw dislocations and evidence sit one click deeper.

---

## 13. Open Questions

1. Should the first production binding live in `cos_mockups/cockpit_live.html`, the new front-end repo/path, or both?
2. Should `gap_engine.top` include only open episodes, or include recently closed episodes for postmortem visibility?
3. Should the map show only the primary country gap or badges for multiple active gaps?
4. Should the old Streamlit dashboard embed the cockpit HTML or only link to it?
5. Should Ask ASADO read the generated JSON file directly first, or query DuckDB through a small backend service?

Recommendation: implement the cockpit/read-model binding first, then bind the new front end to that contract. That avoids redoing front-end work around raw dislocations and gives the UI the right conceptual object from day one.
