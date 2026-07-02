<!--
=============================================================================
FILE: COCKPIT_DATA_CONTRACT.md
=============================================================================
PURPOSE:
  The canonical field-by-field contract for cockpit_data.json — the single
  payload the Chief-of-Staff cockpit binds to. The imported Claude Design code
  and the data layer (build_cockpit_data.py) MUST agree on these names/types.
  If you rename a field here, change it in BOTH build_cockpit_data.py and the
  UI binding, and update test_cockpit_selection.py.

PRODUCER: cos_mockups/build_cockpit_data.py
CONSUMERS: cos_mockups/cockpit_live.html (window.COCKPIT_DATA), the imported
           Claude Design cockpit, test_cockpit_selection.py
VERSION: 1.1   LAST UPDATED: 2026-07-01
  v1.1: documented the two previously-undocumented producer keys
  (`gap_engine`, `research_desk`) — audit D1, 2026-07-01.
=============================================================================
-->

# cockpit_data.json — field contract

Top-level keys: `meta`, `governance`, `signals`, `dislocations`, `combiner`,
`returns`, `theses`, `countries`, `drawdowns`, `brief`, `map`, `today`,
`gap_engine`, `research_desk`. On producer failure an extra `error` string key
is present (e.g. `"loop DB unavailable"`) — the UI must surface it, not render
silently empty panels.

Conventions: dates are `YYYY-MM-DD` strings. Missing numbers are `null` (never
`NaN` — the producer sanitizes). Percentiles are 0–100. Returns are **percent**
(e.g. `-9.09` = −9.09%). Severity / NW-t / IC are raw numbers.

---

## meta
```jsonc
{ "generated_ts": "2026-06-19T20:30:58",
  "generator": "cos_mockups/build_cockpit_data.py 1.0",
  "epistemic_contract": "FACT cited · INFERENCE labelled · UNKNOWN/STALE aloud · nothing is a trade until the harness clears it" }
```

## governance  → ribbon pips + F6 scorecard
```jsonc
{ "overall": "amber",            // "green" | "amber" | "red" = worst dimension
  "as_of": "2026-06-19T20:30:58",
  "repo_dirty": true,
  "dimensions": [
    { "name": "run_manifest", "status": "green",  // green|amber|red
      "amber_by_design": false, "detail": "all steps ok/fresh", "evidence": "run_manifest.json" }
    // ...7 dimensions
  ] }
```
UI rule: overall colour = worst `status`. A dimension with `amber_by_design:true`
is "honest, not broken" — render it amber but not alarming.

## signals  → A2 Live Signals list + F3 registry + tally
```jsonc
{ "registry": [   // sorted: verdict rank (WATCH<WEAK<INSUFF<DEAD) then NW-t desc
    { "id": "H_20260610_003", "name": "graph_trade_gap",
      "verdict": "WATCH",                 // WATCH|WEAK|DEAD|INSUFFICIENT_COVERAGE
      "horizon": "5d", "ic": 0.027, "nw_t": 7.1,
      "deflated_sharpe": null, "is_sanity": false } ],   // is_sanity → not promotable
  "tally": { "WATCH": 2, "WEAK": 39, "INSUFFICIENT_COVERAGE": 16, "DEAD": 31 } }
```
UI rule: verdict badge colour is harness-owned — WATCH teal, WEAK amber, DEAD/INSUFF
oxblood/muted. The CoS never overrides it. For a name with duplicate rows, keep the
FIRST (best) — registry is pre-sorted.

## dislocations  → A3 feed + F5 brief + map flags
```jsonc
{ "as_of": "2026-06-16", "total": 79,
  "counts": { "D1": 10, "D2": 7, "D8": 36, "D9": 17 },   // by detector
  "rows": [ /* all firings */ ],
  "country_ranked": [   // is_country rows, sorted -|severity| then days_active asc
    { "id": "...", "detector": "D2", "archetype": "A2", "entity": "Netherlands",
      "direction": "short", "severity": -2.82, "abs_severity": 2.82,
      "days_active": 6, "first_seen": "2026-06-10", "status": "persisting",
      "reading": "country outran neighbors", "is_country": true } ] }
```
UI rule: map ⚑ flag + A3 rows come from `country_ranked`. Structural detectors
(D8/D9/D10) are `is_country:false` — never promote them to a country tile.

## combiner  → map 'signal' layer + leaders
```jsonc
{ "as_of": "2026-06-16",
  "scores": { "ChinaA": 0.00211, "Brazil": 0.00204, /* ...34 */ },
  "leaders": [ { "country": "ChinaA", "score": 0.00211 } ],   // top 5
  "ic_series": null,        // §1.1: no time series persisted — DO NOT fake a chart
  "ic_series_note": "..." }
```

## returns  → map 'return' layer
```jsonc
{ "as_of": "2026-05-01", "by_country": { "Brazil": -9.09, /* percent, 34 */ } }
```

## countries  → F2 country letter (only countries with ≥1 fundamental)
```jsonc
{ "Brazil": { "y10": 14.592, "cds": 124.578, "s210": -0.11,
              "cape_pctile": null, "erp_pctile": 83.333 } }
```
UI rule: any field may be absent/null — render "—", don't crash. `s210` = 10Y−2Y.

## theses  → F2 PAPER chip (keyed by entity)
```jsonc
{ "Indonesia": [ { "id": "T_20260610_001", "direction": "long", "paper": true,
                   "probability": 0.58, "horizon_days": 21,
                   "thesis": "A2 graph propagation...", "open_date": "..." } ] }
```
UI rule: show the chip only if the country has an entry; tag PAPER vs LIVE from `paper`.

## drawdowns  → map tail dots + F2 tail keyrow
```jsonc
{ "Indonesia": -33.8, "ChinaH": -19.4 }   // only material (< -15%), trailing 252d
```

## brief  → A3 "Brief ›" pointer
```jsonc
{ "file": "/abs/path/Data/dislocations/brief_2026_06_16.md", "name": "brief_2026_06_16.md" }
```

## today  → F1 "Today" (the §1.2 three-slot promotion, ≤3 items, ordered)
```jsonc
[ { "kind": "governance",                 // governance | signal | dislocation
    "headline": "Governance is AMBER — honest, not broken",
    "why": "cross_source_minimal: ...",
    "source": "governance_scorecard.json",
    "route": { "view": "health" } } ]      // route.view: health|signal|country
```
Slot order is fixed by the promotion rule: governance exception → best non-sanity
WATCH → freshest highest-|σ| country dislocation. Render in array order; if fewer
than 3, show fewer (don't pad).

## gap_engine  → Known Gaps feed + gap map layer + gap detail view
```jsonc
{ "status": "fresh",              // "fresh" | "stale" | "missing" — gates the gap-first UI
  "as_of": "2026-06-30",
  "config_version": "gap_engine_v2_2026_07_01", "config_hash": "…",
  "counts": { /* episodes by state */ },
  "staleness": { /* per-source freshness the selector saw */ },
  "selection_note": "…",          // how the top-5 was chosen
  "raw_top": [ /* pre-filter ranking, for audit */ ],
  "holdout": [ /* held-out episodes, for audit */ ],
  "top": [                        // ≤5 headline gaps, ranked by tension_score_current
    { "gap_id": "…", "episode_key": "…", "entity": "Japan", "gap_class": "G2",
      "direction": "long", "status": "open", "date": "2026-06-30",
      "days_active": 4, "horizon_bucket": "21d",
      "mechanism_text": "…", "world_state": "…", "price_state": "…", "notes": "…",
      "tension_score_at_open": 0.61,
      "tension_score_current": 0.18,   // re-scored at mark time (v2) — decays with absorption/staleness
      "absorption_state": "repriced_against",  // unabsorbed|partially_absorbed|absorbed|repriced_against|decayed|insufficient_signal
      "price_absorption_index": -0.36,         // signed; negative = price moved AGAINST the mechanism
      "unabsorbed_fraction": 1.0,              // clamped [0,1] — MEANINGLESS under repriced_against (UI: show the index instead)
      "expected_move": 0.021, "expected_move_source": "…", "realized_move": -0.007,
      "realized_country_return": null, "realized_etf_return": null,
      "preferred_ticker": "EWJ", "proxy_type": "etf", "currency_basis": "USD",
      "expression_quality": 0.9, "liquidity_tier": "tier1",
      "dollar_adv_21d": 4.1e8, "expense_ratio_bps": 50,
      "invalidation_rule": "…", "source_dislocation_ids": ["…"],
      "source_freshness": { /* per-source dates */ },
      "epistemic_tag": "INFERENCE",
      "scoring_config_version": "…", "scoring_config_hash": "…" } ],
  "by_country": { "Japan": { "primary": { /* same shape as top[] */ },
                              "all": [ /* every open episode */ ] } } }
```
UI rules: gap-first behavior (default map layer `gap`, feed shows gaps) only
when `status === "fresh"`. NEVER render "N% unabsorbed" for a
`repriced_against` gap — show `price_absorption_index` instead (audit F2).

## research_desk  → Research Desk tabs (chain-of-custody journal surfaces)
```jsonc
{ "discovery_lab": [   // LLM-proposed detector families, outcome-blind
    { "id": "…", "kind": "…", "title": "…", "subtitle": "…", "status": "…",
      "route": "…", "route_label": "…", "labels": ["…"], "recorded_ts": "…",
      "source": "…", "members": [ /* proposed relationships */ ],
      "falsification": { "fatal_if": ["…"], "must_check": ["…"] },
      "self_falsification": { "strongest_counterargument": "…",
                              "what_would_change_my_mind": ["…"] } } ],
  "analog_shelf": [ /* frozen metric sets */ ],
  "under_triage": [ /* frozen claims */ ],
  "blind_rulings": [ /* blind packets only */ ],
  "prospective": [ /* forward incubation */ ],
  "graveyard": [ /* killed/quarantined, still tracked */ ],
  "counts": { "discovery_lab": { "raw": 50, "shown": 10, "dropped": 40 } } }
```
UI rule: cards are journal records under custody, not alpha; ranking/caps are
applied in `build_cockpit_data.py`, never in the browser.

## map  → A1 capital-flows map (region-grouped, all 34)
```jsonc
[ { "region": "Americas",
    "tiles": [ { "country": "Brazil", "iso": "BRA",
                 "return": -9.09,                 // null-safe
                 "dislocation": "D2 short -2.82σ", // null if none → no ⚑
                 "combiner": 0.00204, "drawdown": -17.5 } ] } ]   // drawdown null → no dot
```
Layers: `return` (diverging teal/rust), `dislocation` (⚑ where non-null),
`signal` (combiner score). Drawdown drives the oxblood dot.

---

### Regeneration
`python cos_mockups/build_cockpit_data.py` (read-only on the loop DB; safe anytime).
Run after each nightly loop to refresh. `test_cockpit_selection.py` guards the
invariants above — run it after any change to the producer.
