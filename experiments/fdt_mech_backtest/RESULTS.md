# FDT Mechanical Backtest — ETF-space translation of ASADO signals

**Registered:** 2026-07-10 (was untracked; registered per GPT-5.6 review recommendation).
**Question:** Do ASADO's stored signals produce positive net-of-cost active return when
applied to the *actual US-listed country-ETF expressions* (not index space)?

## Method
- Universe: US-listed country ETFs (`etf_t2_map`), benchmarked vs the **EW-34 equal-weight**.
- Three strategies, top-5 equal-weight, monthly metronome rebalance at month-end close,
  positions held one month:
  - **S1** — top-5 by `combiner_scores_daily` (walk-forward ridge).
  - **S2** — top-5 by the z-averaged slow-diffusion composite.
  - **BLEND** — 2:1 S1:S2 (the FDT book's 30%/15% sleeve ratio, renormalized).
- Signals lagged **one trading day** (decide at t close using scores as-of t−1).
- Costs: **25 bp one-way** on traded weight (house law).
- Code: `backtest_fdt_layers.py`; outputs `results.xlsx`, `report.pdf` (data, gitignored).

## Result — active return vs EW-34 (annualized)
| Strategy | Full | 5y | 3y | 1y |
|---|---|---|---|---|
| Combiner top-5 | −2.25% | −6.77% | −12.75% | −11.13% |
| Slow-diffusion top-5 | −4.20% | −7.72% | −8.78% | −4.12% |
| 2:1 blend | −2.67% | −6.83% | −11.21% | −8.53% |

## Verdict
**NEGATIVE in ETF space at every horizon.** The index-space diffusion edge does **not**
survive translation to US-listed ETF expressions net of 25 bp one-way costs. This
**corroborates the standing Alpha Book law** ("diffusion dies at the ETF close";
`~/Dropbox/AAA Backup/A Complete/Investment Learnings/INDEX.md` and the Alpha Book
`docs/alpha_book_2026_07_02/`) — it is confirmation, not a new dead end.

## Status / caveats
- This is a *mechanical* backtest of stored signals, not a harness-registered signal
  family, so it is recorded here (experiment RESULTS) rather than in
  `hypothesis_ledger.jsonl` / `config/family_registry.yaml`.
- Provisional in the sense that it is not a live-traded result; it is a measurement of
  what the signals would have captured in ETF space historically.
- It is the ex-ante motivation for the learning loop: the loop's job is to find, forward
  and net-of-cost, whether any promoted gap beats this negative baseline — see
  `docs/LEARNING_LOOP_DESIGN_2026_07_10.md`.
