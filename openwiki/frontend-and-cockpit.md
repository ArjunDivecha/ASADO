# Frontend and cockpit

ASADO's Chief-of-Staff cockpit is a data product, not just a UI. The cockpit payload is built from loop-DB state, governance artifacts, research surfaces, and a small number of curated pointers into nightly reports.

## The payload contract

`cos_mockups/COCKPIT_DATA_CONTRACT.md` is the canonical field contract for `cockpit_data.json`. It says the payload contains top-level sections such as:
- governance
- signals
- dislocations
- combiner
- returns
- theses
- countries
- drawdowns
- brief
- map
- today
- gap_engine
- research_desk

It also states that missing values are sanitized to `null`, returns are stored as percent, and the UI must surface producer errors rather than render a silent empty state.

## Payload generation

`cos_mockups/build_cockpit_data.py` is the producer. Its docstring is valuable because it tells you exactly what the cockpit is reading and why:
- dislocation rows from the loop DB,
- harness verdict summaries,
- combiner and family-rank surfaces,
- governance scorecards,
- thesis ledgers,
- Triptych priors,
- optional ETF tail context,
- and the latest brief pointer.

The producer is intentionally resilient: each source is wrapped in error handling so one failure does not blank the whole cockpit.

## Frontend binding logic

The cockpit redesign work in `docs/PRD_Frontend_Alpha_Rethink_2026_07_01.md` and the tests in `tests/loop/test_phase2_frontend.py` show the binding logic is not trivial presentation glue. The current Phase 2 concepts include:
- family rank orientation,
- consensus voting rules,
- Edge Board selection logic,
- Fable connections relabelled as conjecture,
- and deterministic chat intents that route to new views.

## Why this matters

The cockpit is where multiple research layers converge. Future changes should preserve the distinction between:
- verified signals vs conjecture,
- country-level rows vs structural rows,
- governance exception items vs ranked signal feeds,
- and live data vs dated brief pointers.

## Source references

- `cos_mockups/COCKPIT_DATA_CONTRACT.md`
- `cos_mockups/build_cockpit_data.py`
- `cos_mockups/cos_chat_service.py`
- `cos_mockups/make_live_cockpit.py`
- `cos_mockups/cockpit_live.html`
- `tests/loop/test_phase2_frontend.py`
- `docs/PRD_Frontend_Alpha_Rethink_2026_07_01.md`
- `docs/AUDIT_FRONTEND_2026_07_01.md`

## Where to go next

- [Architecture overview](architecture.md)
- [Loop and research workflows](loop-and-research.md)
- [Prediction markets and Brier Gate](prediction-markets.md)
