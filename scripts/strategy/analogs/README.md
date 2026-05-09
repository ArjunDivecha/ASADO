# Strategy #1 — World-State Analogs (v1: NO-GO)

v1 of the PCA-stacked-cross-section analog strategy reached **no-go** after
backtesting showed no edge outside the 2008–2012 GFC window. The core
methodology scripts (`build_worldstate`, `analog_search`, `aggregate`,
`backtest`, `report`, `run_v1`) have been removed.

**Full post-mortem:** [`docs/strategy/analogs/v1/go_no_go.md`](../../../docs/strategy/analogs/v1/go_no_go.md)  
**Lessons learned:** [`docs/strategy/lessons.md`](../../../docs/strategy/lessons.md)

## Reusable primitives (kept)

| Script | Purpose |
|--------|---------|
| `build_returns.py` | Builds `country_returns_monthly` from T2 optimizer data. Useful for any country-rotation strategy. |
| `pit_audit.py` | Point-in-time vintage-safety classification for all variables. Reusable for any future strategy. |
| `baselines.py` | Equal-weight benchmark machinery and return aggregation utilities. |
| `config.py` | Constants (T2_COUNTRIES, paths, seeds). Template for future strategy modules. |
| `tests/test_pit.py` | 8 PIT discipline tests. Template for future strategy test suites. |
